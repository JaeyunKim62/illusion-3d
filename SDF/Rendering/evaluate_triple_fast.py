"""Fast capacity-aware ranking for all SDF image triples."""

import argparse
import itertools
import json
import os

import numpy as np

from evaluate_image_triple_feasibility import capacity_stats, mask_stats, semantic_group
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
            entries.append({
                "label": label,
                "path": os.path.join(img_dir, name),
                "group": semantic_group(label),
            })
    return entries


def score_item(capacities, recalls, expected):
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
    p = argparse.ArgumentParser(description="Fast capacity-aware image triple ranking")
    p.add_argument("--img-dir", action="append", default=None)
    p.add_argument("--size", type=int, default=256)
    p.add_argument("--sample-budget", type=int, default=30000)
    p.add_argument("--low-capacity-threshold", type=int, default=4)
    p.add_argument("--exclude-label-prefix", action="append", default=["img_candidates/geom_"])
    p.add_argument("--require-label", action="append", default=[])
    p.add_argument("--exactly-one-group", action="append", default=[])
    p.add_argument("--avoid-same-group", action="store_true")
    p.add_argument("--output", default="image-triple-fast-ranking-20260601.json")
    args = p.parse_args()

    img_dirs = args.img_dir or ["img", "img_candidates"]
    entries = image_entries(img_dirs, args.exclude_label_prefix)
    masks = {}
    groups = {}
    active = {}
    for entry in entries:
        mask, _ = load_mask_and_color(entry["path"], args.size)
        masks[entry["label"]] = mask.astype(bool)
        groups[entry["label"]] = entry["group"]
        active[entry["label"]] = mask_stats(masks[entry["label"]])

    labels = [entry["label"] for entry in entries]
    capacities = {}
    for a in labels:
        a_i = masks[a].astype(np.uint16)
        for b in labels:
            b_i = masks[b].astype(np.uint16)
            capacities[("front", a, b)] = a_i @ b_i
            capacities[("side", a, b)] = a_i @ b_i.T
            capacities[("top", a, b)] = a_i.T @ b_i

    results = []
    for front, side, top in itertools.permutations(labels, 3):
        label_names = [front, side, top]
        group_names = [groups[front], groups[side], groups[top]]
        if any(required not in label_names for required in args.require_label):
            continue
        if any(group_names.count(group) != 1 for group in args.exactly_one_group):
            continue
        if args.avoid_same_group and len(set(group_names)) != 3:
            continue

        caps = {
            "front": capacity_stats(
                capacities[("front", side, top)],
                masks[front],
                args.sample_budget,
                args.low_capacity_threshold,
            ),
            "side": capacity_stats(
                capacities[("side", front, top)],
                masks[side],
                args.sample_budget,
                args.low_capacity_threshold,
            ),
            "top": capacity_stats(
                capacities[("top", side, front)],
                masks[top],
                args.sample_budget,
                args.low_capacity_threshold,
            ),
        }
        recalls = {
            label: caps[label]["feasibleRecall"]
            for label in ("front", "side", "top")
        }
        expected = {
            label: caps[label]["expectedCoverage"]
            for label in ("front", "side", "top")
        }
        results.append({
            "front": front,
            "side": side,
            "top": top,
            "groups": {"front": group_names[0], "side": group_names[1], "top": group_names[2]},
            "distinctSemanticGroups": len(set(group_names)) == 3,
            "recall": recalls,
            "minRecall": min(recalls.values()),
            "meanRecall": sum(recalls.values()) / 3,
            "expectedCoverage": expected,
            "minExpectedCoverage": min(expected.values()),
            "meanExpectedCoverage": sum(expected.values()) / 3,
            "capacityP10Min": min(caps[label]["p10"] for label in ("front", "side", "top")),
            "lowCapacityRatioMean": sum(caps[label]["lowCapacityRatio"] for label in ("front", "side", "top")) / 3,
            "sampleabilityScore": score_item(caps, recalls, expected),
            "active": {"front": active[front], "side": active[side], "top": active[top]},
        })

    results.sort(key=lambda item: item["sampleabilityScore"], reverse=True)
    current = next(
        (
            item for item in results
            if item["front"] == "bird.png"
            and item["side"] == "airplane.png"
            and item["top"] == "Tower.png"
        ),
        None,
    )
    visually_distinct = [
        item for item in results
        if item["distinctSemanticGroups"]
        and not any(name.startswith("img_candidates/obj_tower") for name in (item["front"], item["side"], item["top"]))
    ]
    report = {
        "schema": "sdf-image-triple-fast-ranking/v1",
        "size": args.size,
        "filters": {
            "requireLabel": args.require_label,
            "exactlyOneGroup": args.exactly_one_group,
            "avoidSameGroup": args.avoid_same_group,
            "sampleBudget": args.sample_budget,
        },
        "currentBirdAirplaneTower": current,
        "topCandidates": results[:40],
        "topVisuallyDistinctCandidates": visually_distinct[:40],
        "allCandidates": results,
    }

    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)

    print(f"wrote {args.output}")
    if current:
        r = current["recall"]
        e = current["expectedCoverage"]
        print(
            "current bird/airplane/Tower: "
            f"score={current['sampleabilityScore']:.3f} "
            f"min/mean={current['minRecall']:.3f}/{current['meanRecall']:.3f} "
            f"exp={current['minExpectedCoverage']:.3f}/{current['meanExpectedCoverage']:.3f} "
            f"F/S/T={r['front']:.3f}/{r['side']:.3f}/{r['top']:.3f} "
            f"E={e['front']:.3f}/{e['side']:.3f}/{e['top']:.3f}"
        )
    print("top 12 visually distinct candidates:")
    for item in visually_distinct[:12]:
        r = item["recall"]
        e = item["expectedCoverage"]
        print(
            f"- {item['front']} | {item['side']} | {item['top']} "
            f"score={item['sampleabilityScore']:.3f} "
            f"min/mean={item['minRecall']:.3f}/{item['meanRecall']:.3f} "
            f"exp={item['minExpectedCoverage']:.3f}/{item['meanExpectedCoverage']:.3f} "
            f"F/S/T={r['front']:.3f}/{r['side']:.3f}/{r['top']:.3f} "
            f"E={e['front']:.3f}/{e['side']:.3f}/{e['top']:.3f}"
        )


if __name__ == "__main__":
    main()
