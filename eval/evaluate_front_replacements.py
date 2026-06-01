"""Rank front-image replacements for a fixed side/top SDF setup."""

import argparse
import json
import os

import numpy as np

from eval.evaluate_image_triple_feasibility import capacity_stats, mask_stats
from train_sdf import load_mask_and_color


def image_files(img_dir):
    allowed = {".png", ".jpg", ".jpeg", ".webp"}
    return sorted(
        name for name in os.listdir(img_dir)
        if os.path.splitext(name.lower())[1] in allowed
    )


def image_entries(img_dirs, exclude_label_prefixes):
    entries = []
    seen = set()
    for img_dir in img_dirs:
        for name in image_files(img_dir):
            label = name if img_dir == "img" else f"{img_dir}/{name}"
            if any(label.startswith(prefix) for prefix in exclude_label_prefixes):
                continue
            if label in seen:
                continue
            seen.add(label)
            entries.append((label, os.path.join(img_dir, name)))
    return entries


def sampleability_score(capacities, recalls, expected):
    min_recall = min(recalls.values())
    min_expected = min(expected.values())
    mean_expected = sum(expected.values()) / 3
    low_capacity_mean = sum(
        capacities[label]["lowCapacityRatio"]
        for label in ("front", "side", "top")
    ) / 3
    capacity_p10_min = min(
        capacities[label]["p10"]
        for label in ("front", "side", "top")
    )
    return (
        min_expected * 5.0
        + mean_expected * 2.0
        + min_recall * 1.25
        + min(capacity_p10_min / 12.0, 1.0) * 0.75
        - low_capacity_mean * 1.5
    )


def main():
    p = argparse.ArgumentParser(description="Rank front replacements for fixed side/top images")
    p.add_argument("--img-dir", action="append", default=None)
    p.add_argument("--side", default="airplane.png")
    p.add_argument("--top", default="Tower.png")
    p.add_argument("--size", type=int, default=256)
    p.add_argument("--sample-budget", type=int, default=30000)
    p.add_argument("--low-capacity-threshold", type=int, default=4)
    p.add_argument("--exclude-label-prefix", action="append", default=["img_candidates/geom_"])
    p.add_argument("--output", default="data/front-replacement-airplane-tower-20260601.json")
    args = p.parse_args()

    img_dirs = args.img_dir or ["img", "img_candidates"]
    entries = image_entries(img_dirs, args.exclude_label_prefix)
    masks = {}
    for label, path in entries:
        mask, _ = load_mask_and_color(path, args.size)
        masks[label] = mask.astype(bool)

    if args.side not in masks:
        raise SystemExit(f"side image not found in loaded entries: {args.side}")
    if args.top not in masks:
        raise SystemExit(f"top image not found in loaded entries: {args.top}")

    side = masks[args.side]
    top = masks[args.top]
    front_capacity_base = side.astype(np.uint16) @ top.astype(np.uint16)
    results = []

    for front_name, _path in entries:
        front = masks[front_name]
        capacities = {
            "front": capacity_stats(
                front_capacity_base,
                front,
                args.sample_budget,
                args.low_capacity_threshold,
            ),
            "side": capacity_stats(
                front.astype(np.uint16) @ top.astype(np.uint16).T,
                side,
                args.sample_budget,
                args.low_capacity_threshold,
            ),
            "top": capacity_stats(
                side.astype(np.uint16).T @ front.astype(np.uint16),
                top,
                args.sample_budget,
                args.low_capacity_threshold,
            ),
        }
        recalls = {
            label: capacities[label]["feasibleRecall"]
            for label in ("front", "side", "top")
        }
        expected = {
            label: capacities[label]["expectedCoverage"]
            for label in ("front", "side", "top")
        }
        min_recall = min(recalls.values())
        mean_recall = sum(recalls.values()) / 3
        min_expected = min(expected.values())
        mean_expected = sum(expected.values()) / 3
        results.append({
            "front": front_name,
            "side": args.side,
            "top": args.top,
            "recall": recalls,
            "minRecall": min_recall,
            "meanRecall": mean_recall,
            "expectedCoverage": expected,
            "minExpectedCoverage": min_expected,
            "meanExpectedCoverage": mean_expected,
            "capacity": capacities,
            "capacityP10Min": min(
                capacities[label]["p10"]
                for label in ("front", "side", "top")
            ),
            "lowCapacityRatioMean": sum(
                capacities[label]["lowCapacityRatio"]
                for label in ("front", "side", "top")
            ) / 3,
            "sampleabilityScore": sampleability_score(capacities, recalls, expected),
            "active": {
                "front": mask_stats(front),
                "side": mask_stats(side),
                "top": mask_stats(top),
            },
        })

    results.sort(key=lambda item: item["sampleabilityScore"], reverse=True)
    report = {
        "schema": "sdf-front-replacement-feasibility/v1",
        "size": args.size,
        "side": args.side,
        "top": args.top,
        "sampleBudget": args.sample_budget,
        "definition": {
            "front": "front[y,x] is feasible iff exists z with side[y,z] and top[z,x]",
            "side": "side[y,z] is feasible iff exists x with front[y,x] and top[z,x]",
            "top": "top[z,x] is feasible iff exists y with side[y,z] and front[y,x]",
            "expectedCoverage": "mean per-target-pixel hit probability under sampleBudget uniform samples over visual-hull support",
        },
        "topCandidates": results[:24],
        "allCandidates": results,
    }

    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)

    print(f"wrote {args.output}")
    print(f"fixed side/top: {args.side} / {args.top}")
    print("top 12 front replacements:")
    for item in results[:12]:
        r = item["recall"]
        e = item["expectedCoverage"]
        print(
            f"- {item['front']} "
            f"score={item['sampleabilityScore']:.3f} "
            f"min/mean={item['minRecall']:.3f}/{item['meanRecall']:.3f} "
            f"exp={item['minExpectedCoverage']:.3f}/{item['meanExpectedCoverage']:.3f} "
            f"F/S/T={r['front']:.3f}/{r['side']:.3f}/{r['top']:.3f} "
            f"E={e['front']:.3f}/{e['side']:.3f}/{e['top']:.3f}"
        )


if __name__ == "__main__":
    main()
