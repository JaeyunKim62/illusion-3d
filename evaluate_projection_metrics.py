"""Evaluate canonical projection consistency for the dense SDF point cloud."""

import argparse
import json
import os

import numpy as np

from eval.metrics import projection_report
from train_sdf import load_mask_and_color


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
    masks = {"front": mask_f, "side": mask_s, "top": mask_t}
    report = projection_report(points, masks, args.points, data, args.size)

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
