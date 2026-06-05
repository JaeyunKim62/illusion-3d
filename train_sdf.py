"""
Neural SDF: learn per-view SDFs with SIREN, sample from their intersection.

Pipeline:
  1. Load silhouette images → ground-truth SDFs via EDT (supervision signal)
  2. Train 3 SIREN networks concurrently: f_front(x,y), f_side(z,y), f_top(x,z)
     (Iterating one step for each model sequentially in a single loop)
  3. Sample 3D points where   max(f_front, f_side, f_top) ≤ 0
  4. Output points.json for the Three.js viewer
"""

import argparse
import json
import os
import time

import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from scipy.ndimage import distance_transform_edt, binary_fill_holes

from eval.metrics import open_training_metrics_log, training_monitor_snapshot, write_training_metrics_step


# ── SIREN architecture ─────────────────────────────────────────────────────────

class SirenLayer(nn.Module):
    """Sinusoidal activation layer (Sitzmann et al., 2020)."""

    def __init__(self, in_f, out_f, omega=30.0, is_first=False):
        super().__init__()
        self.omega = omega
        self.linear = nn.Linear(in_f, out_f)
        with torch.no_grad():
            n = in_f
            if is_first:
                self.linear.weight.uniform_(-1 / n, 1 / n)
            else:
                self.linear.weight.uniform_(
                    -np.sqrt(6 / n) / omega,
                     np.sqrt(6 / n) / omega,
                )

    def forward(self, x):
        return torch.sin(self.omega * self.linear(x))


class SirenSDF(nn.Module):
    """2D → 1D SIREN that regresses a signed distance field."""

    def __init__(self, hidden=128, n_layers=3, omega=30.0):
        super().__init__()
        layers = [SirenLayer(2, hidden, omega, is_first=True)]
        for _ in range(n_layers - 1):
            layers.append(SirenLayer(hidden, hidden, omega))
        self.net = nn.Sequential(*layers)
        self.head = nn.Linear(hidden, 1)
        with torch.no_grad():
            b = np.sqrt(6 / hidden) / omega
            self.head.weight.uniform_(-b, b)

    def forward(self, uv):
        """uv: (B, 2) in [-1, 1]² → (B,) SDF values."""
        return self.head(self.net(uv)).squeeze(-1)


# ── Image / SDF utilities ──────────────────────────────────────────────────────

def load_mask_and_color(path: str, size: int):
    img = Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)
    arr = np.array(img, dtype=np.uint8)
    alpha = arr[:, :, 3]
    rgb = arr[:, :, :3].astype(np.float32)
    not_transparent = alpha > 64
    sat = rgb.max(axis=2) - rgb.min(axis=2)
    not_white = ~((rgb.min(axis=2) > 220) & (sat < 30))
    mask = not_transparent & not_white
    mask = binary_fill_holes(mask)
    return mask, arr[:, :, :3]


def compute_sdf_gt(mask: np.ndarray) -> np.ndarray:
    """EDT-based ground-truth SDF (negative inside, positive outside),
    normalized to roughly [-1, 1] by dividing by half the grid size."""
    inside = distance_transform_edt(mask).astype(np.float32)
    outside = distance_transform_edt(~mask).astype(np.float32)
    sdf = outside - inside
    sdf /= (mask.shape[0] / 2.0)
    return sdf


def uv_to_pixel(uv: torch.Tensor, size: int):
    """Map (u, v) in [-1,1]² to pixel (col, row).
    u → col (left-to-right),  v → row (y-flip: v=+1 is top → row 0)."""
    col = ((uv[:, 0] + 1) / 2 * (size - 1)).long().clamp(0, size - 1)
    row = ((1 - (uv[:, 1] + 1) / 2) * (size - 1)).long().clamp(0, size - 1)
    return row, col


# ── Concurrent Training ─────────────────────────────────────────────────────────

def train_concurrent_sdfs(
    masks_dict: dict[str, np.ndarray],
    device: torch.device,
    n_iters: int = 2000,
    batch_size: int = 8192,
    lr: float = 5e-4,
    hidden: int = 128,
    n_layers: int = 3,
    eikonal_weight: float = 0.1,
    metrics_output: str | None = None,
    metrics_interval: int = 500,
    metrics_samples: int = 30000,
) -> dict[str, SirenSDF]:
    """세 개의 SIREN 모델(front, side, top)을 루프 내에서 동시에 교대로 학습합니다."""
    
    models = {}
    optimizers = {}
    schedulers = {}
    sdf_tensors = {}
    sdf_arrays = {}
    sizes = {}

    # 각 뷰어(View)별로 모델, 옵티마이저, 스케줄러, GT 데이터 초기화
    for name, mask in masks_dict.items():
        sizes[name] = mask.shape[0]
        sdf_gt = compute_sdf_gt(mask)
        sdf_arrays[name] = sdf_gt
        sdf_tensors[name] = torch.from_numpy(sdf_gt).to(device)

        model = SirenSDF(hidden=hidden, n_layers=n_layers).to(device)
        optim = torch.optim.Adam(model.parameters(), lr=lr)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(optim, T_max=n_iters)
        
        models[name] = model
        optimizers[name] = optim
        schedulers[name] = sched

    t0 = time.time()
    metrics_fp = open_training_metrics_log(
        metrics_output,
        n_iters=n_iters,
        batch_size=batch_size,
        lr=lr,
        hidden=hidden,
        n_layers=n_layers,
        eikonal_weight=eikonal_weight,
        metrics_interval=metrics_interval,
        metrics_samples=metrics_samples,
    )

    # 하나의 메인 루프에서 'front -> side -> top'을 1스텝씩 반복 수행
    for step in range(1, n_iters + 1):
        log_str = f"  Step {step:>4}/{n_iters} "
        print_log = step % 500 == 0 or step == 1
        step_losses = {}

        for name in masks_dict.keys():
            model = models[name]
            optim = optimizers[name]
            sched = schedulers[name]
            sdf_tensor = sdf_tensors[name]
            size = sizes[name]

            # 데이터 샘플링
            uv = torch.rand(batch_size, 2, device=device) * 2 - 1
            row, col = uv_to_pixel(uv, size)
            gt = sdf_tensor[row, col]

            # 예측 및 Boundary-weighted MSE
            pred = model(uv)
            weight = 1.0 + 8.0 * torch.exp(-10.0 * gt.abs())
            mse = (weight * (pred - gt) ** 2).mean()

            # Eikonal loss
            uv_g = uv.detach().clone().requires_grad_(True)
            pred_g = model(uv_g)
            grad = torch.autograd.grad(pred_g.sum(), uv_g, create_graph=True)[0]
            eikonal = ((grad.norm(dim=-1) - 1) ** 2).mean()

            loss = mse + eikonal_weight * eikonal

            # 역전파 및 최적화
            optim.zero_grad()
            loss.backward()
            optim.step()
            sched.step()

            step_losses[name] = {
                "mse": float(mse.detach().cpu()),
                "eikonal": float(eikonal.detach().cpu()),
                "loss": float(loss.detach().cpu()),
            }
            if print_log:
                log_str += f" | [{name}] mse={mse.item():.4f} eik={eikonal.item():.3f}"

        if print_log:
            elapsed = time.time() - t0
            cur_lr = schedulers["front"].get_last_lr()[0] # 대표로 front의 LR 출력
            print(f"{log_str} | lr={cur_lr:.1e} ({elapsed:.1f}s)")

        if metrics_fp and (step == 1 or step % metrics_interval == 0 or step == n_iters):
            snapshot = training_monitor_snapshot(
                models, masks_dict, sdf_arrays, device, metrics_samples
            )
            write_training_metrics_step(
                metrics_fp,
                step=step,
                elapsed_sec=time.time() - t0,
                lr=schedulers["front"].get_last_lr()[0],
                losses=step_losses,
                monitor=snapshot,
            )
            r = snapshot["projection"]
            print(
                "  metrics "
                f"minRecall={snapshot['summary']['minRecall']:.3f} "
                f"meanIoU={snapshot['summary']['meanIoU']:.3f} "
                f"outside={snapshot['sdfOutsideRatio']:.3f} "
                f"recall F/S/T={r['front']['recall']:.3f}/"
                f"{r['side']['recall']:.3f}/{r['top']['recall']:.3f}"
            )

    if metrics_fp:
        metrics_fp.close()

    return models


# ── Sampling ────────────────────────────────────────────────────────────────────

def compute_bbox(masks: list[np.ndarray], pad: float = 0.05):
    """Compute tight 3D bounding box from the silhouette masks."""
    mask_f, mask_s, mask_t = masks
    size = mask_f.shape[0]

    def axis_range(mask, axis):
        proj = mask.any(axis=axis)
        idx  = np.where(proj)[0]
        if len(idx) == 0:
            return -1.0, 1.0
        lo = idx[0] / (size - 1) * 2 - 1
        hi = idx[-1] / (size - 1) * 2 - 1
        return lo - pad, hi + pad

    x_lo, x_hi = axis_range(mask_f, 0)
    y_lo_f, y_hi_f = axis_range(mask_f, 1)
    y_lo_f, y_hi_f = -y_hi_f, -y_lo_f

    z_lo, z_hi = axis_range(mask_s, 0)
    y_lo_s, y_hi_s = axis_range(mask_s, 1)
    y_lo_s, y_hi_s = -y_hi_s, -y_lo_s

    x_lo2, x_hi2 = axis_range(mask_t, 0)
    z_lo2, z_hi2 = axis_range(mask_t, 1)
    z_lo2, z_hi2 = -z_hi2, -z_lo2

    lo = np.array([max(x_lo, x_lo2), max(y_lo_f, y_lo_s), max(z_lo, z_lo2)],
                  dtype=np.float32).clip(-1, 1)
    hi = np.array([min(x_hi, x_hi2), min(y_hi_f, y_hi_s), min(z_hi, z_hi2)],
                  dtype=np.float32).clip(-1, 1)
    return lo, hi


def _eval_sdf_batched(model_f, model_s, model_t, xyz, batch=50_000):
    x, y, z = xyz[:, 0], xyz[:, 1], xyz[:, 2]
    d_parts = []
    for i in range(0, len(x), batch):
        sl = slice(i, i + batch)
        fa = model_f(torch.stack([x[sl], y[sl]], dim=1))
        fb = model_s(torch.stack([z[sl], y[sl]], dim=1))
        fc = model_t(torch.stack([x[sl], z[sl]], dim=1))
        d_parts.append(torch.maximum(torch.maximum(fa, fb), fc))
    return torch.cat(d_parts)


@torch.no_grad()
def rejection_sample(models, masks, n_points, sharpness, surface_ratio, device):
    model_f, model_s, model_t = models
    lo, hi = compute_bbox(masks)
    vol = np.prod(hi - lo)
    print(f"  Bounding box: x[{lo[0]:.2f},{hi[0]:.2f}] "
          f"y[{lo[1]:.2f},{hi[1]:.2f}] z[{lo[2]:.2f},{hi[2]:.2f}]  "
          f"(vol={vol:.3f} vs 8.000)")

    grid_res = 64
    xs = torch.linspace(float(lo[0]), float(hi[0]), grid_res, device=device)
    ys = torch.linspace(float(lo[1]), float(hi[1]), grid_res, device=device)
    zs = torch.linspace(float(lo[2]), float(hi[2]), grid_res, device=device)
    gx, gy, gz = torch.meshgrid(xs, ys, zs, indexing="ij")
    grid_xyz = torch.stack([gx.flatten(), gy.flatten(), gz.flatten()], dim=1)

    d_grid = _eval_sdf_batched(model_f, model_s, model_t, grid_xyz)

    surface_margin = (hi - lo).max() / grid_res * 1.5
    occ_mask = d_grid <= surface_margin
    occ_idx  = torch.where(occ_mask)[0]
    occ_frac = len(occ_idx) / grid_res ** 3 * 100
    print(f"  Coarse grid ({grid_res}³): {len(occ_idx)} / {grid_res**3} voxels "
          f"occupied ({occ_frac:.1f}%)  → sampling inside these only")

    if len(occ_idx) == 0:
        raise RuntimeError("No occupied voxels found — check SDF training or input masks.")

    occ_centers = grid_xyz[occ_idx].cpu().numpy()
    vox_half = (hi - lo) / grid_res / 2.0

    n_surface  = int(n_points * surface_ratio)
    n_interior = n_points - n_surface
    batch = 100_000

    all_pts = []
    for phase, target in [("surface", n_surface), ("interior", n_interior)]:
        pts = []
        n_got = 0
        total_sampled = 0
        while n_got < target:
            vi  = np.random.randint(0, len(occ_centers), size=batch)
            jit = np.random.uniform(-1, 1, size=(batch, 3)) * vox_half
            xyz_np = occ_centers[vi] + jit
            xyz = torch.tensor(xyz_np, dtype=torch.float32, device=device)

            d = _eval_sdf_batched(model_f, model_s, model_t, xyz)

            if phase == "surface":
                accept = (d <= 0) & (torch.rand(len(d), device=device) < torch.exp(sharpness * d))
            else:
                accept = d <= 0

            idx = torch.where(accept)[0][:target - n_got]
            if len(idx) > 0:
                pts.append(xyz[idx].cpu().numpy())
                n_got += len(idx)

            total_sampled += batch
            if total_sampled % (batch * 5) == 0:
                rate = n_got / total_sampled * 100
                print(f"    {phase}: {n_got}/{target}  "
                      f"(accept {rate:.1f}%, {total_sampled//1000}k sampled)")

        pts_np = np.concatenate(pts, axis=0)[:target]
        all_pts.append(pts_np)
        print(f"  {phase}: {len(pts_np)} points")

    return np.concatenate(all_pts, axis=0)


def lookup_view_colors(points_np: np.ndarray, colors: list[np.ndarray], size: int):
    color_f, color_s, color_t = colors
    x = points_np[:, 0]
    y = points_np[:, 1]
    z = points_np[:, 2]

    col_x = np.clip(((x + 1) / 2 * (size - 1)).astype(int), 0, size - 1)
    row_y = np.clip(((1 - (y + 1) / 2) * (size - 1)).astype(int), 0, size - 1)
    col_z = np.clip(((z + 1) / 2 * (size - 1)).astype(int), 0, size - 1)
    row_z = np.clip(((1 - (z + 1) / 2) * (size - 1)).astype(int), 0, size - 1)

    cf = color_f[row_y, col_x]
    cs = color_s[row_y, col_z]
    ct = color_t[row_z, col_x]
    return cf, cs, ct


def sample_from_intersection(models, colors, masks, size, n_points, sharpness, surface_ratio, device):
    print("  Rejection sampling ...")
    points = rejection_sample(models, masks, n_points, sharpness, surface_ratio, device)

    print(f"  Looking up colors for {len(points)} points ...")
    cf, cs, ct = lookup_view_colors(points, colors, size)

    return {
        "points":     [p.tolist() for p in points],
        "colorFront": [c.tolist() for c in cf],
        "colorSide":  [c.tolist() for c in cs],
        "colorTop":   [c.tolist() for c in ct],
    }


# ── Main ────────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="Neural SDF point cloud generator")
    p.add_argument("--front",   default="img/airplane.png")
    p.add_argument("--side",    default="img/bird.png")
    p.add_argument("--top",     default="img/Tower.png")
    p.add_argument("--n",       type=int,   default=30000)
    p.add_argument("--size",    type=int,   default=256)
    p.add_argument("--iters",   type=int,   default=5000)
    p.add_argument("--hidden",  type=int,   default=256)
    p.add_argument("--layers",  type=int,   default=3)
    p.add_argument("--lr",      type=float, default=1e-4)
    p.add_argument("--sharpness",     type=float, default=6.0)
    p.add_argument("--surface-ratio", type=float, default=0.4)
    p.add_argument("--device",  default=None)
    p.add_argument("--retrain", action="store_true", help="Force retrain even if learned_sdfs.pt exists")
    p.add_argument("--metrics-output", default="data/training-metrics.jsonl")
    p.add_argument("--metrics-interval", type=int, default=500)
    p.add_argument("--metrics-samples", type=int, default=30000)
    p.add_argument("--output",  default="data/points.json")
    args = p.parse_args()

    if args.device:
        device = torch.device(args.device)
    elif torch.cuda.is_available():
        device = torch.device("cuda")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")
    print(f"Device: {device}")

    print("Loading images ...")
    mask_f, color_f = load_mask_and_color(args.front, args.size)
    mask_s, color_s = load_mask_and_color(args.side,  args.size)
    mask_t, color_t = load_mask_and_color(args.top,   args.size)
    print(f"  front {args.front}: {mask_f.sum()/mask_f.size*100:.1f}% coverage")
    print(f"  side  {args.side}:  {mask_s.sum()/mask_s.size*100:.1f}% coverage")
    print(f"  top   {args.top}:   {mask_t.sum()/mask_t.size*100:.1f}% coverage")

    ckpt_path = "learned_sdfs.pt"

    if os.path.exists(ckpt_path) and not args.retrain:
        print(f"\nFound {ckpt_path} — loading learned SDFs (use --retrain to force)")
        ckpt = torch.load(ckpt_path, map_location=device, weights_only=True)
        cfg = ckpt["config"]
        model_f = SirenSDF(hidden=cfg["hidden"], n_layers=cfg["layers"]).to(device)
        model_s = SirenSDF(hidden=cfg["hidden"], n_layers=cfg["layers"]).to(device)
        model_t = SirenSDF(hidden=cfg["hidden"], n_layers=cfg["layers"]).to(device)
        model_f.load_state_dict(ckpt["front"])
        model_s.load_state_dict(ckpt["side"])
        model_t.load_state_dict(ckpt["top"])
        model_f.eval(); model_s.eval(); model_t.eval()
        print("  Loaded ✓")
    else:
        print(f"\n{'='*50}")
        print(f"Training SIREN SDFs Concurrently (hidden={args.hidden}, layers={args.layers}, iters={args.iters})")
        print(f"{'='*50}\n")

        masks_dict = {"front": mask_f, "side": mask_s, "top": mask_t}
        
        # 교대 반복 학습 실행
        trained_models = train_concurrent_sdfs(
            masks_dict, device, args.iters,
            hidden=args.hidden, n_layers=args.layers, lr=args.lr,
            metrics_output=args.metrics_output,
            metrics_interval=args.metrics_interval,
            metrics_samples=args.metrics_samples,
        )
        
        model_f = trained_models["front"]
        model_s = trained_models["side"]
        model_t = trained_models["top"]

        torch.save({
            "front": model_f.state_dict(),
            "side":  model_s.state_dict(),
            "top":   model_t.state_dict(),
            "config": {"hidden": args.hidden, "layers": args.layers},
        }, ckpt_path)
        print(f"\nSaved models → {ckpt_path}")

    print(f"\n{'='*50}")
    print(f"Sampling {args.n} points from learned SDF intersection ...")
    print(f"{'='*50}")

    data = sample_from_intersection(
        [model_f, model_s, model_t],
        [color_f, color_s, color_t],
        [mask_f, mask_s, mask_t],
        args.size, args.n, args.sharpness, args.surface_ratio, device,
    )

    with open(args.output, "w") as f:
        json.dump(data, f, separators=(",", ":"))

    total = len(data["points"])
    kb = os.path.getsize(args.output) / 1024
    print(f"\n{total} points → {args.output} ({kb:.0f} KB)")


if __name__ == "__main__":
    main()