"""Scan source image triples for 3-view visual-hull compatibility.

This evaluates the theoretical mask-level coverage before neural SDF training.
It answers whether low projection recall is caused by sampling density or by an
incompatible front/side/top silhouette choice.
"""

import argparse
import itertools
import json
import os

import numpy as np

from train_sdf import load_mask_and_color


def feasible_masks(front: np.ndarray, side: np.ndarray, top: np.ndarray):
    # Shapes are all (size, size). Interpret axes as:
    # front[y, x], side[y, z], top[z, x].
    front_i = front.astype(np.uint16)
    side_i = side.astype(np.uint16)
    top_i = top.astype(np.uint16)
    front_feasible = front & ((side_i @ top_i) > 0)
    side_feasible = side & ((front_i @ top_i.T) > 0)
    top_feasible = top & ((side_i.T @ front_i) > 0)
    return front_feasible, side_feasible, top_feasible


def recall(feasible: np.ndarray, target: np.ndarray):
    target_count = int(target.sum())
    feasible_count = int((feasible & target).sum())
    return feasible_count / max(1, target_count)


def mask_stats(mask: np.ndarray):
    return {
        "active": int(mask.sum()),
        "total": int(mask.size),
        "ratio": float(mask.sum() / max(1, mask.size)),
    }


def pack_mask(mask: np.ndarray):
    return np.packbits(mask.reshape(-1))


def packed_intersection_count(a: np.ndarray, b: np.ndarray):
    return int(np.unpackbits(np.bitwise_and(a, b)).sum())


def front_pair_compat(side: np.ndarray, top: np.ndarray):
    # For each front pixel (y,x), ask whether any z satisfies side[y,z] and top[z,x].
    out = np.zeros_like(top, dtype=bool)
    for y in range(side.shape[0]):
        zs = np.flatnonzero(side[y])
        if zs.size:
            out[y] = top[zs].any(axis=0)
    return out


def side_pair_compat(front: np.ndarray, top: np.ndarray):
    # For each side pixel (y,z), ask whether any x satisfies front[y,x] and top[z,x].
    out = np.zeros_like(front, dtype=bool)
    for y in range(front.shape[0]):
        xs = np.flatnonzero(front[y])
        if xs.size:
            out[y] = top[:, xs].any(axis=1)
    return out


def top_pair_compat(side: np.ndarray, front: np.ndarray):
    # For each top pixel (z,x), ask whether any y satisfies side[y,z] and front[y,x].
    out = np.zeros((side.shape[1], front.shape[1]), dtype=bool)
    for z in range(side.shape[1]):
        ys = np.flatnonzero(side[:, z])
        if ys.size:
            out[z] = front[ys].any(axis=0)
    return out


def image_files(img_dir):
    allowed = {".png", ".jpg", ".jpeg", ".webp"}
    return sorted(
        name for name in os.listdir(img_dir)
        if os.path.splitext(name.lower())[1] in allowed
    )


def semantic_group(label):
    stem = os.path.splitext(os.path.basename(label).lower())[0]
    if stem.startswith("nub"):
        return "nub"
    if "bird" in stem:
        return "bird"
    if "airplane" in stem or "plane" in stem:
        return "airplane"
    if "tower" in stem:
        return "tower"
    if stem.startswith("geom_") or stem.startswith("obj_"):
        return stem
    return stem.split("_")[0]


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


def main():
    p = argparse.ArgumentParser(description="Evaluate feasible recall for image triples")
    p.add_argument("--img-dir", action="append", default=None)
    p.add_argument("--size", type=int, default=256)
    p.add_argument("--output", default="image-triple-feasibility.json")
    p.add_argument("--allow-repeat", action="store_true")
    p.add_argument("--exclude-label-prefix", action="append", default=[])
    p.add_argument("--require-label", action="append", default=[])
    p.add_argument("--exactly-one-group", action="append", default=[])
    args = p.parse_args()

    img_dirs = args.img_dir or ["img"]
    entries = image_entries(img_dirs, args.exclude_label_prefix)
    masks = {}
    groups = {}
    packed_masks = {}
    active_counts = {}
    for entry in entries:
        mask, _ = load_mask_and_color(entry["path"], args.size)
        masks[entry["label"]] = mask.astype(bool)
        groups[entry["label"]] = entry["group"]
        packed_masks[entry["label"]] = pack_mask(masks[entry["label"]])
        active_counts[entry["label"]] = int(masks[entry["label"]].sum())

    labels = [entry["label"] for entry in entries]
    front_compat = {}
    side_compat = {}
    top_compat = {}
    for a in labels:
        for b in labels:
            front_compat[(a, b)] = pack_mask(front_pair_compat(masks[a], masks[b]))
            side_compat[(a, b)] = pack_mask(side_pair_compat(masks[a], masks[b]))
            top_compat[(a, b)] = pack_mask(top_pair_compat(masks[a], masks[b]))

    triples = itertools.product(labels, repeat=3) if args.allow_repeat else itertools.permutations(labels, 3)
    results = []
    for front_name, side_name, top_name in triples:
        label_names = [front_name, side_name, top_name]
        group_names = [groups[front_name], groups[side_name], groups[top_name]]
        if any(required not in label_names for required in args.require_label):
            continue
        if any(group_names.count(group) != 1 for group in args.exactly_one_group):
            continue
        front_count = active_counts[front_name]
        side_count = active_counts[side_name]
        top_count = active_counts[top_name]
        front_f_count = packed_intersection_count(
            packed_masks[front_name],
            front_compat[(side_name, top_name)],
        )
        side_f_count = packed_intersection_count(
            packed_masks[side_name],
            side_compat[(front_name, top_name)],
        )
        top_f_count = packed_intersection_count(
            packed_masks[top_name],
            top_compat[(side_name, front_name)],
        )
        recalls = {
            "front": front_f_count / max(1, front_count),
            "side": side_f_count / max(1, side_count),
            "top": top_f_count / max(1, top_count),
        }
        min_recall = min(recalls.values())
        mean_recall = sum(recalls.values()) / 3
        active_sum = int(front_count + side_count + top_count)
        # Prefer compatible, readable masks but avoid nearly-full silhouettes.
        score = min_recall * 4.0 + mean_recall * 1.5 + min(active_sum / (args.size * args.size * 0.8), 1.0)
        results.append({
            "front": front_name,
            "side": side_name,
            "top": top_name,
            "groups": {
                "front": group_names[0],
                "side": group_names[1],
                "top": group_names[2],
            },
            "distinctSemanticGroups": len(set(group_names)) == 3,
            "recall": recalls,
            "minRecall": min_recall,
            "meanRecall": mean_recall,
            "score": score,
            "active": {
                "front": mask_stats(masks[front_name]),
                "side": mask_stats(masks[side_name]),
                "top": mask_stats(masks[top_name]),
            },
            "feasibleActive": {
                "front": front_f_count,
                "side": side_f_count,
                "top": top_f_count,
            },
        })

    results.sort(key=lambda item: item["score"], reverse=True)
    diverse_results = [item for item in results if item["distinctSemanticGroups"]]
    current = next(
        (
            item for item in results
            if item["front"] == "bird.png"
            and item["side"] == "airplane.png"
            and item["top"] == "Tower.png"
        ),
        None,
    )
    report = {
        "schema": "sdf-image-triple-feasibility/v1",
        "size": args.size,
        "imageDirs": img_dirs,
        "imageFiles": labels,
        "filters": {
            "excludeLabelPrefix": args.exclude_label_prefix,
            "requireLabel": args.require_label,
            "exactlyOneGroup": args.exactly_one_group,
        },
        "definition": {
            "front": "front[y,x] is feasible iff exists z with side[y,z] and top[z,x]",
            "side": "side[y,z] is feasible iff exists x with front[y,x] and top[z,x]",
            "top": "top[z,x] is feasible iff exists y with front[y,x] and side[y,z]",
        },
        "currentBirdAirplaneTower": current,
        "topCandidates": results[:24],
        "topDistinctSemanticCandidates": diverse_results[:24],
        "allCandidates": results,
    }

    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)

    print(f"wrote {args.output}")
    if current:
        r = current["recall"]
        print(f"current bird/airplane/Tower feasible recall F/S/T: {r['front']:.3f} / {r['side']:.3f} / {r['top']:.3f}")
    print("top 8 candidates:")
    for item in results[:8]:
        r = item["recall"]
        print(
            f"- {item['front']} | {item['side']} | {item['top']} "
            f"min={item['minRecall']:.3f} mean={item['meanRecall']:.3f} "
            f"F/S/T={r['front']:.3f}/{r['side']:.3f}/{r['top']:.3f}"
        )
    print("top 8 semantically distinct candidates:")
    for item in diverse_results[:8]:
        r = item["recall"]
        print(
            f"- {item['front']} | {item['side']} | {item['top']} "
            f"min={item['minRecall']:.3f} mean={item['meanRecall']:.3f} "
            f"F/S/T={r['front']:.3f}/{r['side']:.3f}/{r['top']:.3f}"
        )


if __name__ == "__main__":
    main()
