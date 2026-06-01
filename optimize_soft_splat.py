"""SDF-constrained differentiable soft-splat refinement.

This is an offline optimizer for the contest point set. It keeps one fixed-size
3D point cloud, starts from an existing points.json, and refines point positions
and splat radii with differentiable multi-view silhouette losses.

Default views follow the current windmill/airplane/Tower experiment:
  front: (x, y) -> design_windmill
  side:  (z, y) -> airplane
  top:   (x, z) -> Tower
"""

import argparse
import json
import math
import os
import time

import numpy as np
import torch
import torch.nn.functional as F

from train_sdf import compute_sdf_gt, load_mask_and_color


def world_delta_from_pixels(px: float, size: int) -> float:
    return float(px) * 2.0 / max(1, size - 1)


def normalized_to_pixels(points: np.ndarray, size: int):
    x = points[:, 0]
    y = points[:, 1]
    z = points[:, 2]
    col_x = np.clip(np.rint((x + 1) / 2 * (size - 1)).astype(np.int32), 0, size - 1)
    row_y = np.clip(np.rint((1 - (y + 1) / 2) * (size - 1)).astype(np.int32), 0, size - 1)
    col_z = np.clip(np.rint((z + 1) / 2 * (size - 1)).astype(np.int32), 0, size - 1)
    row_z = np.clip(np.rint((1 - (z + 1) / 2) * (size - 1)).astype(np.int32), 0, size - 1)
    return col_x, row_y, col_z, row_z


def projection_metrics(points: np.ndarray, masks: dict, size: int):
    col_x, row_y, col_z, row_z = normalized_to_pixels(points, size)
    projections = {
        "front": np.zeros((size, size), dtype=bool),
        "side": np.zeros((size, size), dtype=bool),
        "top": np.zeros((size, size), dtype=bool),
    }
    projections["front"][row_y, col_x] = True
    projections["side"][row_y, col_z] = True
    projections["top"][row_z, col_x] = True

    out = {}
    for name, proj in projections.items():
        target = masks[name].astype(bool)
        inter = proj & target
        leakage = proj & ~target
        union = proj | target
        out[name] = {
            "targetActive": int(target.sum()),
            "projectedActive": int(proj.sum()),
            "intersection": int(inter.sum()),
            "recall": float(inter.sum() / max(1, target.sum())),
            "precision": float(inter.sum() / max(1, proj.sum())),
            "iou": float(inter.sum() / max(1, union.sum())),
            "leakageRatio": float(leakage.sum() / max(1, proj.sum())),
        }
    out["summary"] = {
        "minRecall": min(out[k]["recall"] for k in ("front", "side", "top")),
        "minPrecision": min(out[k]["precision"] for k in ("front", "side", "top")),
        "maxLeakageRatio": max(out[k]["leakageRatio"] for k in ("front", "side", "top")),
        "meanIoU": sum(out[k]["iou"] for k in ("front", "side", "top")) / 3.0,
    }
    return out


def target_tensor(mask: np.ndarray, render_size: int, device: torch.device):
    src = torch.from_numpy(mask.astype(np.float32))[None, None].to(device)
    return F.interpolate(src, size=(render_size, render_size), mode="area")[0, 0].clamp(0, 1)


def sdf_tensor(mask: np.ndarray, device: torch.device):
    sdf = compute_sdf_gt(mask).astype(np.float32)
    return torch.from_numpy(sdf)[None, None].to(device)


def project(points: torch.Tensor, view: str, render_size: int):
    x, y, z = points[:, 0], points[:, 1], points[:, 2]
    if view == "front":
        u_world, v_world = x, y
    elif view == "side":
        u_world, v_world = z, y
    elif view == "top":
        u_world, v_world = x, z
    else:
        raise ValueError(f"unknown view: {view}")
    u = (u_world + 1.0) * 0.5 * (render_size - 1)
    v = (1.0 - (v_world + 1.0) * 0.5) * (render_size - 1)
    return u, v


def soft_splat(
    points: torch.Tensor,
    radius: torch.Tensor,
    view: str,
    render_size: int,
    kernel_radius: int,
    opacity: float,
    offsets: torch.Tensor,
):
    u, v = project(points, view, render_size)
    base_u = torch.floor(u).long()
    base_v = torch.floor(v).long()
    ox = offsets[:, 0]
    oy = offsets[:, 1]

    px = base_u[:, None] + ox[None, :]
    py = base_v[:, None] + oy[None, :]
    valid = (px >= 0) & (px < render_size) & (py >= 0) & (py < render_size)
    px = px.clamp(0, render_size - 1)
    py = py.clamp(0, render_size - 1)

    du = u[:, None] - px.float()
    dv = v[:, None] - py.float()
    r = radius[:, None].clamp_min(1e-3)
    weights = torch.exp(-(du * du + dv * dv) / (2.0 * r * r)) * float(opacity)
    weights = torch.where(valid, weights, torch.zeros_like(weights))

    idx = (py * render_size + px).reshape(-1)
    accum = torch.zeros(render_size * render_size, device=points.device, dtype=points.dtype)
    accum.scatter_add_(0, idx, weights.reshape(-1))
    accum = accum.reshape(render_size, render_size)
    return 1.0 - torch.exp(-accum)


def bce_dice_loss(render: torch.Tensor, target: torch.Tensor, pos_weight: float, dice_weight: float):
    eps = 1e-5
    weight = torch.where(target > 0.5, torch.full_like(target, pos_weight), torch.ones_like(target))
    bce = F.binary_cross_entropy(render.clamp(eps, 1.0 - eps), target, weight=weight)
    inter = (render * target).sum()
    dice = 1.0 - (2.0 * inter + 1.0) / (render.sum() + target.sum() + 1.0)
    return bce + float(dice_weight) * dice


def sample_sdf(sdf: torch.Tensor, u_world: torch.Tensor, v_world: torch.Tensor):
    # grid_sample coordinates: x=-1 left, y=-1 top. World v=+1 maps to image top.
    grid = torch.stack([u_world, -v_world], dim=-1)[None, :, None, :]
    return F.grid_sample(sdf, grid, mode="bilinear", padding_mode="border", align_corners=True)[0, 0, :, 0]


def sdf_values(points: torch.Tensor, sdfs: dict):
    x, y, z = points[:, 0], points[:, 1], points[:, 2]
    front = sample_sdf(sdfs["front"], x, y)
    side = sample_sdf(sdfs["side"], z, y)
    top = sample_sdf(sdfs["top"], x, z)
    stacked = torch.stack([front, side, top], dim=1)
    return stacked, stacked.max(dim=1).values


def clamp_points(points: torch.Tensor):
    return points.clamp(-1.0, 1.0)


def recolor(data: dict, points: np.ndarray, rgbs: dict, size: int):
    col_x, row_y, col_z, row_z = normalized_to_pixels(points, size)
    data["colorFront"] = rgbs["front"][row_y, col_x].astype(np.uint8).tolist()
    data["colorSide"] = rgbs["side"][row_y, col_z].astype(np.uint8).tolist()
    data["colorTop"] = rgbs["top"][row_z, col_x].astype(np.uint8).tolist()


def sigmoid_inv(x: float):
    x = min(max(x, 1e-5), 1.0 - 1e-5)
    return math.log(x / (1.0 - x))


def main():
    p = argparse.ArgumentParser(description="Refine one fixed point set with SDF-constrained soft splat losses")
    p.add_argument("--front", default="img_candidates/design_windmill.png")
    p.add_argument("--side", default="img/airplane.png")
    p.add_argument("--top", default="img/Tower.png")
    p.add_argument("--points", default="data/points.json")
    p.add_argument("--output", default="data/points-softsplat.json")
    p.add_argument("--report", default="data/softsplat-report.json")
    p.add_argument("--size", type=int, default=256)
    p.add_argument("--render-size", type=int, default=128)
    p.add_argument("--steps", type=int, default=500)
    p.add_argument("--lr", type=float, default=2e-2)
    p.add_argument("--device", default="cuda")
    p.add_argument("--max-delta-px", type=float, default=2.0)
    p.add_argument("--max-y-delta-px", type=float, default=0.0)
    p.add_argument("--radius-init", type=float, default=1.12)
    p.add_argument("--radius-min", type=float, default=0.65)
    p.add_argument("--radius-max", type=float, default=2.30)
    p.add_argument("--kernel-radius", type=int, default=4)
    p.add_argument("--opacity", type=float, default=0.85)
    p.add_argument("--pos-weight", type=float, default=4.0)
    p.add_argument("--dice-weight", type=float, default=0.30)
    p.add_argument("--lambda-side", type=float, default=1.0)
    p.add_argument("--lambda-top", type=float, default=0.65)
    p.add_argument("--lambda-inside", type=float, default=8.0)
    p.add_argument("--lambda-surface", type=float, default=0.035)
    p.add_argument("--lambda-displace", type=float, default=0.050)
    p.add_argument("--lambda-radius", type=float, default=0.030)
    p.add_argument("--log-every", type=int, default=50)
    p.add_argument("--no-recolor", action="store_true")
    args = p.parse_args()

    if args.device == "cuda" and not torch.cuda.is_available():
        print("cuda requested but unavailable; falling back to cpu")
        args.device = "cpu"
    device = torch.device(args.device)

    with open(args.points, "r") as f:
        data = json.load(f)
    p0_np = np.asarray(data["points"], dtype=np.float32)
    n = p0_np.shape[0]

    masks = {}
    rgbs = {}
    for name, path in (("front", args.front), ("side", args.side), ("top", args.top)):
        mask, rgb = load_mask_and_color(path, args.size)
        masks[name] = mask.astype(bool)
        rgbs[name] = rgb

    before_metrics = projection_metrics(p0_np, masks, args.size)

    targets = {k: target_tensor(v, args.render_size, device) for k, v in masks.items()}
    sdfs = {k: sdf_tensor(v, device) for k, v in masks.items()}
    p0 = torch.from_numpy(p0_np).to(device)

    max_dx = world_delta_from_pixels(args.max_delta_px, args.size)
    max_dy = world_delta_from_pixels(args.max_y_delta_px, args.size)
    delta_xz_raw = torch.zeros((n, 2), device=device, requires_grad=True)
    params = [delta_xz_raw]

    if max_dy > 0:
        delta_y_raw = torch.zeros(n, device=device, requires_grad=True)
        params.append(delta_y_raw)
    else:
        delta_y_raw = None

    radius_ratio = (args.radius_init - args.radius_min) / max(1e-6, args.radius_max - args.radius_min)
    radius_raw = torch.full((n,), sigmoid_inv(radius_ratio), device=device, requires_grad=True)
    params.append(radius_raw)

    offsets = torch.tensor(
        [(i, j) for j in range(-args.kernel_radius, args.kernel_radius + 1)
         for i in range(-args.kernel_radius, args.kernel_radius + 1)],
        dtype=torch.long,
        device=device,
    )
    optim = torch.optim.Adam(params, lr=args.lr)
    t0 = time.time()
    history = []

    for step in range(1, args.steps + 1):
        optim.zero_grad(set_to_none=True)

        delta_xz = torch.tanh(delta_xz_raw) * max_dx
        points = p0.clone()
        points[:, 0] = points[:, 0] + delta_xz[:, 0]
        points[:, 2] = points[:, 2] + delta_xz[:, 1]
        if delta_y_raw is not None:
            points[:, 1] = points[:, 1] + torch.tanh(delta_y_raw) * max_dy
        points = clamp_points(points)

        radius = args.radius_min + torch.sigmoid(radius_raw) * (args.radius_max - args.radius_min)
        render_f = soft_splat(points, radius, "front", args.render_size, args.kernel_radius, args.opacity, offsets)
        render_s = soft_splat(points, radius, "side", args.render_size, args.kernel_radius, args.opacity, offsets)
        render_t = soft_splat(points, radius, "top", args.render_size, args.kernel_radius, args.opacity, offsets)

        loss_f = bce_dice_loss(render_f, targets["front"], args.pos_weight, args.dice_weight)
        loss_s = bce_dice_loss(render_s, targets["side"], args.pos_weight, args.dice_weight)
        loss_t = bce_dice_loss(render_t, targets["top"], args.pos_weight, args.dice_weight)

        sdf_stack, sdf_max = sdf_values(points, sdfs)
        inside_loss = F.relu(sdf_max).pow(2).mean()
        surface_loss = sdf_max.abs().mean()
        disp_loss = (delta_xz / max(max_dx, 1e-6)).pow(2).mean()
        if delta_y_raw is not None:
            disp_loss = disp_loss + (torch.tanh(delta_y_raw)).pow(2).mean()
        radius_loss = ((radius - args.radius_init) / max(1e-6, args.radius_init)).pow(2).mean()

        loss = (
            loss_f
            + args.lambda_side * loss_s
            + args.lambda_top * loss_t
            + args.lambda_inside * inside_loss
            + args.lambda_surface * surface_loss
            + args.lambda_displace * disp_loss
            + args.lambda_radius * radius_loss
        )
        loss.backward()
        optim.step()

        if step == 1 or step % args.log_every == 0 or step == args.steps:
            item = {
                "step": step,
                "loss": float(loss.detach().cpu()),
                "front": float(loss_f.detach().cpu()),
                "side": float(loss_s.detach().cpu()),
                "top": float(loss_t.detach().cpu()),
                "inside": float(inside_loss.detach().cpu()),
                "surface": float(surface_loss.detach().cpu()),
                "radiusMean": float(radius.detach().mean().cpu()),
                "radiusMax": float(radius.detach().max().cpu()),
                "elapsedSec": time.time() - t0,
            }
            history.append(item)
            print(
                f"[{step:>4}/{args.steps}] loss={item['loss']:.4f} "
                f"F/S/T={item['front']:.4f}/{item['side']:.4f}/{item['top']:.4f} "
                f"inside={item['inside']:.6f} r={item['radiusMean']:.3f}/{item['radiusMax']:.3f} "
                f"({item['elapsedSec']:.1f}s)"
            )

    with torch.no_grad():
        delta_xz = torch.tanh(delta_xz_raw) * max_dx
        points = p0.clone()
        points[:, 0] = points[:, 0] + delta_xz[:, 0]
        points[:, 2] = points[:, 2] + delta_xz[:, 1]
        if delta_y_raw is not None:
            points[:, 1] = points[:, 1] + torch.tanh(delta_y_raw) * max_dy
        points = clamp_points(points)
        radius = args.radius_min + torch.sigmoid(radius_raw) * (args.radius_max - args.radius_min)
        sdf_stack, sdf_max = sdf_values(points, sdfs)

    out_points = points.detach().cpu().numpy().astype(np.float32)
    out_radius = radius.detach().cpu().numpy().astype(np.float32)
    out_sdf = sdf_stack.detach().cpu().numpy().astype(np.float32)
    out_sdf_max = sdf_max.detach().cpu().numpy().astype(np.float32)
    displacement = np.linalg.norm(out_points - p0_np, axis=1)
    after_metrics = projection_metrics(out_points, masks, args.size)

    out = dict(data)
    out["points"] = np.round(out_points, 6).tolist()
    if not args.no_recolor:
        recolor(out, out_points, rgbs, args.size)
    out["radius"] = np.round(out_radius, 6).tolist()
    out["splatRadius"] = np.round(out_radius / max(args.radius_init, 1e-6), 6).tolist()
    out["sdf"] = {
        "source": "EDT annotations from optimize_soft_splat.py",
        "convention": "negative inside, zero boundary, positive outside",
        "front": np.round(out_sdf[:, 0], 6).tolist(),
        "side": np.round(out_sdf[:, 1], 6).tolist(),
        "top": np.round(out_sdf[:, 2], 6).tolist(),
    }
    out["sdfMax"] = np.round(out_sdf_max, 6).tolist()
    out["sdfActiveConstraint"] = out_sdf.argmax(axis=1).astype(np.int32).tolist()
    out["sdfBoundaryStrength"] = np.round(1.0 - np.clip(np.abs(out_sdf_max) / 0.18, 0.0, 1.0), 6).tolist()
    out["softSplatOptimization"] = {
        "algorithm": "SDF-constrained differentiable soft-splat refinement",
        "invariant": "single fixed-cardinality point set; no view-specific geometry or opacity gates",
        "input": args.points,
        "front": args.front,
        "side": args.side,
        "top": args.top,
        "pointCount": int(n),
        "optimizedVariables": ["x", "z", "radius"] + (["y"] if delta_y_raw is not None else []),
        "maxDeltaPx": args.max_delta_px,
        "maxYDeltaPx": args.max_y_delta_px,
        "renderSize": args.render_size,
        "steps": args.steps,
        "radius": {
            "min": float(out_radius.min()),
            "mean": float(out_radius.mean()),
            "max": float(out_radius.max()),
        },
        "displacement": {
            "mean": float(displacement.mean()),
            "p95": float(np.percentile(displacement, 95)),
            "max": float(displacement.max()),
        },
    }

    report = {
        "schema": "sdf-soft-splat-optimization-report/v1",
        "config": vars(args),
        "before": before_metrics,
        "after": after_metrics,
        "history": history,
        "radius": out["softSplatOptimization"]["radius"],
        "displacement": out["softSplatOptimization"]["displacement"],
        "sdfValidity": {
            "positiveSdfCount": int((out_sdf_max > 1e-5).sum()),
            "positiveSdfRatio": float((out_sdf_max > 1e-5).mean()),
            "maxPositiveSdf": float(out_sdf_max.max()),
            "meanSdfMax": float(out_sdf_max.mean()),
        },
    }

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    with open(args.report, "w") as f:
        json.dump(report, f, indent=2)

    print(f"wrote {args.output}")
    print(f"wrote {args.report}")
    print(
        "before recall F/S/T: "
        f"{before_metrics['front']['recall']:.3f} / "
        f"{before_metrics['side']['recall']:.3f} / "
        f"{before_metrics['top']['recall']:.3f}"
    )
    print(
        "after  recall F/S/T: "
        f"{after_metrics['front']['recall']:.3f} / "
        f"{after_metrics['side']['recall']:.3f} / "
        f"{after_metrics['top']['recall']:.3f}"
    )
    print(
        "after precision F/S/T: "
        f"{after_metrics['front']['precision']:.3f} / "
        f"{after_metrics['side']['precision']:.3f} / "
        f"{after_metrics['top']['precision']:.3f}"
    )
    print(f"after max leakage ratio: {after_metrics['summary']['maxLeakageRatio']:.3f}")
    print(f"radius mean/max: {out_radius.mean():.3f} / {out_radius.max():.3f}")


if __name__ == "__main__":
    main()
