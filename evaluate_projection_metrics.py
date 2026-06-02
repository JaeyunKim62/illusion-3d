"""Evaluate canonical projection consistency for the dense SDF point cloud."""

import argparse
import json
import os

import numpy as np

from train_sdf import load_mask_and_color


def normalized_to_pixels(points: np.ndarray, size: int):
    x = points[:, 0]
    y = points[:, 1]
    z = points[:, 2]
    col_x = np.clip(np.rint((x + 1) / 2 * (size - 1)).astype(np.int32), 0, size - 1)
    row_y = np.clip(np.rint((1 - (y + 1) / 2) * (size - 1)).astype(np.int32), 0, size - 1)
    col_z = np.clip(np.rint((z + 1) / 2 * (size - 1)).astype(np.int32), 0, size - 1)
    row_z = np.clip(np.rint((1 - (z + 1) / 2) * (size - 1)).astype(np.int32), 0, size - 1)
    return col_x, row_y, col_z, row_z


def metric(projected: np.ndarray, target: np.ndarray):
    projected = projected.astype(bool)
    target = target.astype(bool)
    intersection = projected & target
    union = projected | target
    leakage = projected & ~target
    missing = target & ~projected
    projected_active = int(projected.sum())
    target_active = int(target.sum())
    intersection_active = int(intersection.sum())
    leakage_active = int(leakage.sum())
    missing_active = int(missing.sum())
    return {
        "targetActive": target_active,
        "projectedActive": projected_active,
        "intersection": intersection_active,
        "missing": missing_active,
        "leakage": leakage_active,
        "recall": intersection_active / max(1, target_active),
        "precision": intersection_active / max(1, projected_active),
        "iou": int(union.sum()) and intersection_active / int(union.sum()) or 0.0,
        "leakageRatio": leakage_active / max(1, projected_active),
        "missingRatio": missing_active / max(1, target_active),
    }


def active_constraint_distribution(values):
    arr = np.asarray(values, dtype=np.int32)
    total = max(1, arr.size)
    labels = ["front", "side", "top"]
    return {
        labels[i]: {
            "count": int((arr == i).sum()),
            "ratio": float((arr == i).sum() / total),
        }
        for i in range(3)
    }


def main():
    p = argparse.ArgumentParser(description="Evaluate dense SDF projection metrics")
    p.add_argument("--front", default="img/bird.png")
    p.add_argument("--side", default="img/airplane.png")
    p.add_argument("--top", default="img/Tower.png")
    p.add_argument("--points", default="data/points-sdf.json")
    p.add_argument("--output", default="data/projection-metrics.json")
    p.add_argument("--size", type=int, default=256)
    args = p.parse_args()

    with open(args.points, "r") as f:
        data = json.load(f)

    points = np.asarray(data["points"], dtype=np.float32)
    mask_f, _ = load_mask_and_color(args.front, args.size)
    mask_s, _ = load_mask_and_color(args.side, args.size)
    mask_t, _ = load_mask_and_color(args.top, args.size)

    col_x, row_y, col_z, row_z = normalized_to_pixels(points, args.size)
    proj_f = np.zeros((args.size, args.size), dtype=bool)
    proj_s = np.zeros((args.size, args.size), dtype=bool)
    proj_t = np.zeros((args.size, args.size), dtype=bool)
    proj_f[row_y, col_x] = True
    proj_s[row_y, col_z] = True
    proj_t[row_z, col_x] = True

    sdf_max = np.asarray(data.get("sdfMax", []), dtype=np.float32)
    positive = sdf_max > 1e-5 if sdf_max.size else np.asarray([], dtype=bool)
    report = {
        "schema": "sdf-projection-metrics/v1",
        "pointCloud": {
            "points": int(points.shape[0]),
            "source": args.points,
        },
        "projectionDefinition": {
            "front": "(x,y)",
            "side": "(z,y)",
            "top": "(x,z)",
        },
        "metrics": {
            "front": metric(proj_f, mask_f),
            "side": metric(proj_s, mask_s),
            "top": metric(proj_t, mask_t),
        },
        "sdfValidity": {
            "hasSdfMax": bool(sdf_max.size),
            "positiveSdfCount": int(positive.sum()) if sdf_max.size else None,
            "positiveSdfRatio": float(positive.sum() / max(1, sdf_max.size)) if sdf_max.size else None,
            "maxPositiveSdf": float(sdf_max.max()) if sdf_max.size else None,
            "meanSdfMax": float(sdf_max.mean()) if sdf_max.size else None,
        },
        "activeConstraintDistribution": active_constraint_distribution(data.get("sdfActiveConstraint", [])),
    }
    report["summary"] = {
        "minRecall": min(v["recall"] for v in report["metrics"].values()),
        "minPrecision": min(v["precision"] for v in report["metrics"].values()),
        "maxLeakageRatio": max(v["leakageRatio"] for v in report["metrics"].values()),
        "meanIoU": sum(v["iou"] for v in report["metrics"].values()) / 3,
    }

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)

    print(f"wrote {args.output}")
    print(
        "recall F/S/T: "
        f"{report['metrics']['front']['recall']:.3f} / "
        f"{report['metrics']['side']['recall']:.3f} / "
        f"{report['metrics']['top']['recall']:.3f}"
    )
    print(
        "precision F/S/T: "
        f"{report['metrics']['front']['precision']:.3f} / "
        f"{report['metrics']['side']['precision']:.3f} / "
        f"{report['metrics']['top']['precision']:.3f}"
    )
    print(f"max leakage ratio: {report['summary']['maxLeakageRatio']:.3f}")


if __name__ == "__main__":
    main()
