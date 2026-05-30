"""Annotate a sampled SDF point cloud with per-view signed-distance values.

The renderer uses these fields only as a mathematical reveal layer. Geometry is
still the same fixed point set sampled from the neural SDF intersection.
"""

import argparse
import json
import os

import numpy as np

from train_sdf import compute_sdf_gt, load_mask_and_color


def normalized_to_pixels(points: np.ndarray, size: int):
    x = points[:, 0]
    y = points[:, 1]
    z = points[:, 2]
    col_x = np.clip(((x + 1) / 2 * (size - 1)).astype(np.int32), 0, size - 1)
    row_y = np.clip(((1 - (y + 1) / 2) * (size - 1)).astype(np.int32), 0, size - 1)
    col_z = np.clip(((z + 1) / 2 * (size - 1)).astype(np.int32), 0, size - 1)
    row_z = np.clip(((1 - (z + 1) / 2) * (size - 1)).astype(np.int32), 0, size - 1)
    return col_x, row_y, col_z, row_z


def main():
    p = argparse.ArgumentParser(description="Add EDT SDF annotations to points.json")
    p.add_argument("--front", default="img/bird.png")
    p.add_argument("--side", default="img/airplane.png")
    p.add_argument("--top", default="img/Tower.png")
    p.add_argument("--points", default="points.json")
    p.add_argument("--output", default="points-sdf.json")
    p.add_argument("--size", type=int, default=256)
    args = p.parse_args()

    with open(args.points, "r") as f:
        data = json.load(f)

    points = np.asarray(data["points"], dtype=np.float32)
    mask_f, _ = load_mask_and_color(args.front, args.size)
    mask_s, _ = load_mask_and_color(args.side, args.size)
    mask_t, _ = load_mask_and_color(args.top, args.size)
    sdf_f = compute_sdf_gt(mask_f)
    sdf_s = compute_sdf_gt(mask_s)
    sdf_t = compute_sdf_gt(mask_t)

    col_x, row_y, col_z, row_z = normalized_to_pixels(points, args.size)
    front_values = sdf_f[row_y, col_x]
    side_values = sdf_s[row_y, col_z]
    top_values = sdf_t[row_z, col_x]
    sdf_values = np.stack([front_values, side_values, top_values], axis=1)
    sdf_max = sdf_values.max(axis=1)
    active_constraint = sdf_values.argmax(axis=1).astype(np.int32)
    boundary_strength = 1.0 - np.clip(np.abs(sdf_max) / 0.18, 0.0, 1.0)

    data["sdf"] = {
        "source": "EDT annotations from the three source silhouettes",
        "convention": "negative inside, zero boundary, positive outside",
        "front": front_values.round(6).tolist(),
        "side": side_values.round(6).tolist(),
        "top": top_values.round(6).tolist(),
    }
    data["sdfMax"] = sdf_max.round(6).tolist()
    data["sdfActiveConstraint"] = active_constraint.tolist()
    data["sdfBoundaryStrength"] = boundary_strength.round(6).tolist()
    data["sdfAnnotation"] = {
        "algorithm": "per-point lookup into EDT SDFs of front/side/top silhouettes",
        "implicitIntersection": "max(f_front(x,y), f_side(z,y), f_top(x,z)) <= 0",
        "pointCount": int(points.shape[0]),
        "maxPositiveSdf": float(sdf_max.max()),
        "maxInsideViolationCount": int((sdf_max > 1e-5).sum()),
    }

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(data, f, separators=(",", ":"))

    print(f"wrote {args.output}")
    print(f"points: {points.shape[0]}")
    print(f"max positive sdf: {sdf_max.max():.6f}")
    print(f"outside/violation samples: {(sdf_max > 1e-5).sum()}")


if __name__ == "__main__":
    main()
