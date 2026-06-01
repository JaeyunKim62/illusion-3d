"""
Neural SDF: learn per-view SDFs with SIREN, sample from their intersection.

Pipeline:
  1. Load silhouette images → ground-truth SDFs via EDT (supervision signal)
  2. Train 3 SIREN networks:  f_front(x,y),  f_side(z,y),  f_top(x,z)
  3. Sample 3D points where   max(f_front, f_side, f_top) ≤ 0
  4. Output points.json for the Three.js viewer

Usage:
  python train_sdf.py --front img/bird.png --side img/airplane.png --top img/Tower.png
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


# ── Training ────────────────────────────────────────────────────────────────────

def train_one_sdf(
    name: str,
    mask: np.ndarray,
    device: torch.device,
    n_iters: int = 2000,
    batch_size: int = 8192,
    lr: float = 5e-4,
    hidden: int = 128,
    n_layers: int = 3,
    eikonal_weight: float = 0.1,
) -> SirenSDF:
    """Train a SIREN to regress the SDF of a 2D silhouette.

    Loss = boundary-weighted MSE  +  eikonal (|∇f| ≈ 1)
    LR schedule: cosine annealing → 0
    """
    size = mask.shape[0]
    sdf_gt = compute_sdf_gt(mask)
    sdf_tensor = torch.from_numpy(sdf_gt).to(device)

    model = SirenSDF(hidden=hidden, n_layers=n_layers).to(device)
    optim = torch.optim.Adam(model.parameters(), lr=lr)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(optim, T_max=n_iters)

    t0 = time.time()
    for step in range(1, n_iters + 1):
        uv = torch.rand(batch_size, 2, device=device) * 2 - 1
        row, col = uv_to_pixel(uv, size)
        gt = sdf_tensor[row, col]

        pred = model(uv)

        # Boundary-weighted MSE: higher weight near the surface (|SDF| ≈ 0)
        weight = 1.0 + 8.0 * torch.exp(-10.0 * gt.abs())
        mse = (weight * (pred - gt) ** 2).mean()

        # Eikonal: encourage |∇f| = 1 for a proper SDF
        uv_g = uv.detach().clone().requires_grad_(True)
        pred_g = model(uv_g)
        grad = torch.autograd.grad(
            pred_g.sum(), uv_g, create_graph=True,
        )[0]
        eikonal = ((grad.norm(dim=-1) - 1) ** 2).mean()

        loss = mse + eikonal_weight * eikonal

        optim.zero_grad()
        loss.backward()
        optim.step()
        sched.step()

        if step % 500 == 0 or step == 1:
            elapsed = time.time() - t0
            cur_lr = sched.get_last_lr()[0]
            print(f"  [{name}] step {step:>4}/{n_iters}  "
                  f"mse={mse.item():.6f}  eik={eikonal.item():.4f}  "
                  f"lr={cur_lr:.1e}  ({elapsed:.1f}s)")

    return model


# ── Sampling ────────────────────────────────────────────────────────────────────

def compute_bbox(masks: list[np.ndarray], pad: float = 0.05):
    """Compute tight 3D bounding box from the silhouette masks.
    Front mask constrains (x, y), side constrains (z, y), top constrains (x, z).
    Returns (lo, hi) each of shape (3,) in [-1, 1] world coords."""
    mask_f, mask_s, mask_t = masks
    size = mask_f.shape[0]

    def axis_range(mask, axis):
        proj = mask.any(axis=axis)          # collapse one axis
        idx  = np.where(proj)[0]
        if len(idx) == 0:
            return -1.0, 1.0
        lo = idx[0] / (size - 1) * 2 - 1
        hi = idx[-1] / (size - 1) * 2 - 1
        return lo - pad, hi + pad

    # front mask (rows=y inverted, cols=x)
    x_lo, x_hi = axis_range(mask_f, 0)             # collapse rows → x range
    y_lo_f, y_hi_f = axis_range(mask_f, 1)          # collapse cols → y range (inverted)
    y_lo_f, y_hi_f = -y_hi_f, -y_lo_f              # un-invert

    # side mask (rows=y inverted, cols=z)
    z_lo, z_hi = axis_range(mask_s, 0)
    y_lo_s, y_hi_s = axis_range(mask_s, 1)
    y_lo_s, y_hi_s = -y_hi_s, -y_lo_s

    # top mask (rows=z inverted, cols=x) — tighten x and z further
    x_lo2, x_hi2 = axis_range(mask_t, 0)
    z_lo2, z_hi2 = axis_range(mask_t, 1)
    z_lo2, z_hi2 = -z_hi2, -z_lo2

    lo = np.array([max(x_lo, x_lo2), max(y_lo_f, y_lo_s), max(z_lo, z_lo2)],
                  dtype=np.float32).clip(-1, 1)
    hi = np.array([min(x_hi, x_hi2), min(y_hi_f, y_hi_s), min(z_hi, z_hi2)],
                  dtype=np.float32).clip(-1, 1)
    return lo, hi


@torch.no_grad()
def rejection_sample(models, masks, n_points, sharpness, surface_ratio, device):
    """Collect 3D points inside the learned SDF intersection.
    Uses mask bounding box to avoid sampling in empty space."""
    model_f, model_s, model_t = models
    lo, hi = compute_bbox(masks)
    vol = np.prod(hi - lo)
    print(f"  Bounding box: x[{lo[0]:.2f},{hi[0]:.2f}] "
          f"y[{lo[1]:.2f},{hi[1]:.2f}] z[{lo[2]:.2f},{hi[2]:.2f}]  "
          f"(vol={vol:.3f} vs 8.000)")

    lo_t = torch.tensor(lo, device=device)
    hi_t = torch.tensor(hi, device=device)

    n_surface  = int(n_points * surface_ratio)
    n_interior = n_points - n_surface
    batch = 100_000

    all_pts = []
    for phase, target in [("surface", n_surface), ("interior", n_interior)]:
        pts = []
        n_got = 0
        total_sampled = 0
        while n_got < target:
            # Sample within bounding box only
            xyz = torch.rand(batch, 3, device=device) * (hi_t - lo_t) + lo_t
            x, y, z = xyz[:, 0], xyz[:, 1], xyz[:, 2]

            fa = model_f(torch.stack([x, y], dim=1))
            fb = model_s(torch.stack([z, y], dim=1))
            fc = model_t(torch.stack([x, z], dim=1))
            d  = torch.maximum(torch.maximum(fa, fb), fc)

            if phase == "surface":
                accept = (d <= 0) & (torch.rand(batch, device=device) < torch.exp(sharpness * d))
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


def lookup_view_colors(
    points_np: np.ndarray,
    colors: list[np.ndarray],
    size: int,
):
    """For each point, look up the color from each view image.
    Returns (colorFront, colorSide, colorTop) each shape (N, 3) uint8."""
    color_f, color_s, color_t = colors
    x = points_np[:, 0]
    y = points_np[:, 1]
    z = points_np[:, 2]

    col_x = np.clip(((x + 1) / 2 * (size - 1)).astype(int), 0, size - 1)
    row_y = np.clip(((1 - (y + 1) / 2) * (size - 1)).astype(int), 0, size - 1)
    col_z = np.clip(((z + 1) / 2 * (size - 1)).astype(int), 0, size - 1)
    row_z = np.clip(((1 - (z + 1) / 2) * (size - 1)).astype(int), 0, size - 1)

    cf = color_f[row_y, col_x]  # (N, 3)
    cs = color_s[row_y, col_z]
    ct = color_t[row_z, col_x]
    return cf, cs, ct


def sample_from_intersection(
    models, colors, masks, size, n_points, sharpness, surface_ratio, device,
):
    """Full pipeline: rejection sample → look up per-view colors."""
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
    p.add_argument("--output",  default="data/points.json")
    args = p.parse_args()

    # Device
    if args.device:
        device = torch.device(args.device)
    elif torch.cuda.is_available():
        device = torch.device("cuda")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")
    print(f"Device: {device}")

    # Load images
    print("Loading images ...")
    mask_f, color_f = load_mask_and_color(args.front, args.size)
    mask_s, color_s = load_mask_and_color(args.side,  args.size)
    mask_t, color_t = load_mask_and_color(args.top,   args.size)
    print(f"  front {args.front}: {mask_f.sum()/mask_f.size*100:.1f}% coverage")
    print(f"  side  {args.side}:  {mask_s.sum()/mask_s.size*100:.1f}% coverage")
    print(f"  top   {args.top}:   {mask_t.sum()/mask_t.size*100:.1f}% coverage")

    # Train or load SDFs
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
        print(f"Training SIREN SDFs  (hidden={args.hidden}, layers={args.layers}, "
              f"iters={args.iters})")
        print(f"{'='*50}")

        print(f"\n[1/3] Front SDF ...")
        model_f = train_one_sdf("front", mask_f, device,
                                args.iters, hidden=args.hidden,
                                n_layers=args.layers, lr=args.lr)

        print(f"\n[2/3] Side SDF ...")
        model_s = train_one_sdf("side", mask_s, device,
                                args.iters, hidden=args.hidden,
                                n_layers=args.layers, lr=args.lr)

        print(f"\n[3/3] Top SDF ...")
        model_t = train_one_sdf("top", mask_t, device,
                                args.iters, hidden=args.hidden,
                                n_layers=args.layers, lr=args.lr)

        # Save learned models
        torch.save({
            "front": model_f.state_dict(),
            "side":  model_s.state_dict(),
            "top":   model_t.state_dict(),
            "config": {"hidden": args.hidden, "layers": args.layers},
        }, ckpt_path)
        print(f"Saved models → {ckpt_path}")

    # Sample from intersection
    print(f"\n{'='*50}")
    print(f"Sampling {args.n} points from learned SDF intersection ...")
    print(f"{'='*50}")

    data = sample_from_intersection(
        [model_f, model_s, model_t],
        [color_f, color_s, color_t],
        [mask_f, mask_s, mask_t],
        args.size, args.n, args.sharpness, args.surface_ratio, device,
    )

    # Save points
    with open(args.output, "w") as f:
        json.dump(data, f, separators=(",", ":"))

    total = len(data["points"])
    kb = os.path.getsize(args.output) / 1024
    print(f"\n{total} points → {args.output} ({kb:.0f} KB)")


if __name__ == "__main__":
    main()
