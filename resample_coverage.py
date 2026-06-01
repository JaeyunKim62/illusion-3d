"""Coverage-aware post-resampling for SDF visual-hull point clouds.

This script keeps the same physical rule as train_sdf.py: every accepted point
must lie inside the three silhouette constraints. It then fills under-covered
projection pixels and, when requested, replaces low-utility existing samples so
the final point budget can remain fixed.
"""

import argparse
import json
import os
from dataclasses import dataclass

import numpy as np

from train_sdf import compute_sdf_gt, load_mask_and_color, lookup_view_colors

PIXEL_BIAS = 0.25


@dataclass
class Candidate:
    point: tuple[float, float, float]
    gain: int
    leakage: int
    sdf_max: float
    source: str


def normalized_to_pixels(points: np.ndarray, size: int):
    x = points[:, 0]
    y = points[:, 1]
    z = points[:, 2]
    col_x = np.clip(np.rint((x + 1) / 2 * (size - 1)).astype(np.int32), 0, size - 1)
    row_y = np.clip(np.rint((1 - (y + 1) / 2) * (size - 1)).astype(np.int32), 0, size - 1)
    col_z = np.clip(np.rint((z + 1) / 2 * (size - 1)).astype(np.int32), 0, size - 1)
    row_z = np.clip(np.rint((1 - (z + 1) / 2) * (size - 1)).astype(np.int32), 0, size - 1)
    return col_x, row_y, col_z, row_z


def pix_x(col: int, size: int) -> float:
    sample = min(size - 1, col + PIXEL_BIAS)
    return float(sample / (size - 1) * 2 - 1)


def pix_y(row: int, size: int) -> float:
    sample = min(size - 1, row + PIXEL_BIAS)
    return float(1 - sample / (size - 1) * 2)


def build_counts(points: np.ndarray, size: int):
    col_x, row_y, col_z, row_z = normalized_to_pixels(points, size)
    counts = [np.zeros((size, size), dtype=np.int32) for _ in range(3)]
    np.add.at(counts[0], (row_y, col_x), 1)
    np.add.at(counts[1], (row_y, col_z), 1)
    np.add.at(counts[2], (row_z, col_x), 1)
    pixels = np.stack([col_x, row_y, col_z, row_z], axis=1)
    return counts, pixels


def projection_metric(counts: np.ndarray, target: np.ndarray):
    projected = counts > 0
    target = target.astype(bool)
    inter = projected & target
    leakage = projected & ~target
    missing = target & ~projected
    active = int(target.sum())
    projected_count = int(projected.sum())
    return {
        "targetActive": active,
        "projectedActive": projected_count,
        "intersection": int(inter.sum()),
        "missing": int(missing.sum()),
        "leakage": int(leakage.sum()),
        "recall": float(inter.sum() / max(1, active)),
        "precision": float(inter.sum() / max(1, projected_count)),
        "leakageRatio": float(leakage.sum() / max(1, projected_count)),
    }


def all_metrics(counts, masks):
    names = ["front", "side", "top"]
    report = {name: projection_metric(counts[i], masks[i]) for i, name in enumerate(names)}
    return {
        "metrics": report,
        "summary": {
            "minRecall": min(v["recall"] for v in report.values()),
            "meanRecall": sum(v["recall"] for v in report.values()) / 3,
            "minPrecision": min(v["precision"] for v in report.values()),
            "maxLeakageRatio": max(v["leakageRatio"] for v in report.values()),
        },
    }


def point_utility(pixels: np.ndarray, counts, masks, sdfs, leakage_weight: int, sdf_weight: int):
    col_x, row_y, col_z, row_z = pixels.T
    coords = [(row_y, col_x), (row_y, col_z), (row_z, col_x)]
    utility = np.zeros(pixels.shape[0], dtype=np.int32)
    leakage = np.zeros(pixels.shape[0], dtype=np.int32)
    for i, (rows, cols) in enumerate(coords):
        active = masks[i][rows, cols]
        unique = (counts[i][rows, cols] == 1) & active
        outside = ~active
        utility += unique.astype(np.int32)
        leakage += outside.astype(np.int32)
    sdf_max = np.maximum.reduce([sdfs[i][rows, cols] for i, (rows, cols) in enumerate(coords)])
    sdf_penalty = (sdf_max > 1e-5).astype(np.int32)
    return utility - leakage_weight * leakage - sdf_weight * sdf_penalty


def candidate_score(cx, ry, cz, rz, counts, masks, sdfs):
    coords = [(ry, cx), (ry, cz), (rz, cx)]
    gain = 0
    leakage = 0
    sdf_values = []
    for i, (row, col) in enumerate(coords):
        inside = bool(masks[i][row, col])
        gain += int(inside and counts[i][row, col] == 0)
        leakage += int(not inside)
        sdf_values.append(float(sdfs[i][row, col]))
    return gain, leakage, max(sdf_values)


def add_to_counts(counts, point, size):
    cx, ry, cz, rz = normalized_to_pixels(np.asarray([point], dtype=np.float32), size)
    counts[0][ry[0], cx[0]] += 1
    counts[1][ry[0], cz[0]] += 1
    counts[2][rz[0], cx[0]] += 1


def best_for_front(row_y, col_x, counts, masks, sdfs, size, eps):
    z_cols = np.where(masks[1][row_y] & masks[2][:, col_x][::-1])[0]
    best = None
    for col_z in z_cols:
        z = pix_x(int(col_z), size)
        row_z = int(np.rint((1 - (z + 1) / 2) * (size - 1)))
        gain, leakage, sdf_max = candidate_score(col_x, row_y, int(col_z), row_z, counts, masks, sdfs)
        if sdf_max <= eps:
            cand = Candidate((pix_x(col_x, size), pix_y(row_y, size), z), gain, leakage, sdf_max, "front")
            best = choose_better(best, cand)
    return best


def best_for_side(row_y, col_z, counts, masks, sdfs, size, eps):
    z = pix_x(col_z, size)
    row_z = int(np.rint((1 - (z + 1) / 2) * (size - 1)))
    x_cols = np.where(masks[0][row_y] & masks[2][row_z])[0]
    best = None
    for col_x in x_cols:
        gain, leakage, sdf_max = candidate_score(int(col_x), row_y, col_z, row_z, counts, masks, sdfs)
        if sdf_max <= eps:
            cand = Candidate((pix_x(int(col_x), size), pix_y(row_y, size), z), gain, leakage, sdf_max, "side")
            best = choose_better(best, cand)
    return best


def best_for_top(row_z, col_x, counts, masks, sdfs, size, eps):
    z = pix_y(row_z, size)
    col_z = int(np.rint((z + 1) / 2 * (size - 1)))
    y_rows = np.where(masks[0][:, col_x] & masks[1][:, col_z])[0]
    best = None
    for row_y in y_rows:
        gain, leakage, sdf_max = candidate_score(col_x, int(row_y), col_z, row_z, counts, masks, sdfs)
        if sdf_max <= eps:
            cand = Candidate((pix_x(col_x, size), pix_y(int(row_y), size), z), gain, leakage, sdf_max, "top")
            best = choose_better(best, cand)
    return best


def choose_better(current, cand):
    if current is None:
        return cand
    cur_key = (current.gain - current.leakage * 3, -current.leakage, -current.sdf_max)
    new_key = (cand.gain - cand.leakage * 3, -cand.leakage, -cand.sdf_max)
    return cand if new_key > cur_key else current


def missing_pixels(counts, mask):
    rows, cols = np.where(mask & (counts == 0))
    return list(zip(rows.tolist(), cols.tolist()))


def generate_candidates(counts, masks, sdfs, size, eps, max_new, rng):
    candidates = []
    seen = set()
    builders = [best_for_front, best_for_side, best_for_top]
    names = ["front", "side", "top"]

    while len(candidates) < max_new:
        metrics = all_metrics(counts, masks)["metrics"]
        order = sorted(range(3), key=lambda i: metrics[names[i]]["recall"])
        made_progress = False
        for view in order:
            miss = missing_pixels(counts[view], masks[view])
            if not miss:
                continue
            rng.shuffle(miss)
            for row, col in miss[: max(64, min(1024, len(miss)))]:
                cand = builders[view](row, col, counts, masks, sdfs, size, eps)
                if cand is None or cand.gain <= cand.leakage:
                    continue
                key = tuple(round(v, 6) for v in cand.point)
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(cand)
                add_to_counts(counts, cand.point, size)
                made_progress = True
                break
            if len(candidates) >= max_new:
                break
        if not made_progress:
            break
    return candidates


def merge_points(data, candidates, masks, colors, sdfs, size, target_count, replace, leakage_weight, sdf_weight):
    points = np.asarray(data["points"], dtype=np.float32)
    new_points = np.asarray([c.point for c in candidates], dtype=np.float32)
    if new_points.size == 0:
        selected = points
        selected_new = np.zeros((0, 3), dtype=np.float32)
        boost = np.zeros(len(selected), dtype=np.float32)
    elif replace and target_count <= len(points):
        counts, pixels = build_counts(points, size)
        util = point_utility(pixels, counts, masks, sdfs, leakage_weight, sdf_weight)
        replace_count = min(len(new_points), max(0, len(points) - target_count + len(new_points)))
        replace_count = min(replace_count, len(points))
        drop = np.argsort(util)[:replace_count]
        keep = np.ones(len(points), dtype=bool)
        keep[drop] = False
        selected_new = new_points[:replace_count]
        selected = np.concatenate([points[keep], selected_new], axis=0)
        boost = np.concatenate([
            np.zeros(int(keep.sum()), dtype=np.float32),
            np.ones(len(selected_new), dtype=np.float32),
        ])
    else:
        selected = np.concatenate([points, new_points], axis=0) if new_points.size else points
        selected_new = new_points
        boost = np.concatenate([
            np.zeros(len(points), dtype=np.float32),
            np.ones(len(new_points), dtype=np.float32),
        ]) if new_points.size else np.zeros(len(points), dtype=np.float32)
        if target_count and len(selected) > target_count:
            selected = selected[:target_count]
            boost = boost[:target_count]

    cf, cs, ct = lookup_view_colors(selected, colors, size)
    out = {
        "points": selected.astype(float).tolist(),
        "colorFront": cf.tolist(),
        "colorSide": cs.tolist(),
        "colorTop": ct.tolist(),
        "coverageBoost": boost.round(3).tolist(),
        "resampling": {
            "algorithm": "coverage-aware SDF visual-hull resampling",
            "candidateCount": int(len(candidates)),
            "insertedCount": int(len(selected_new)),
            "replaceMode": bool(replace),
            "targetCount": int(target_count or len(selected)),
        },
    }
    return out


def main():
    p = argparse.ArgumentParser(description="Coverage-aware SDF point resampling")
    p.add_argument("--front", default="img/bird.png")
    p.add_argument("--side", default="img/airplane.png")
    p.add_argument("--top", default="img/Tower.png")
    p.add_argument("--points", default="data/points.json")
    p.add_argument("--output", default="data/points-resampled.json")
    p.add_argument("--report", default="data/resampling-report.json")
    p.add_argument("--size", type=int, default=256)
    p.add_argument("--target-count", type=int, default=30000)
    p.add_argument("--max-new", type=int, default=5000)
    p.add_argument("--eps", type=float, default=0.005)
    p.add_argument("--replace", action="store_true")
    p.add_argument("--seed", type=int, default=31)
    p.add_argument("--leakage-weight", type=int, default=4)
    p.add_argument("--sdf-weight", type=int, default=3)
    args = p.parse_args()

    with open(args.points, "r") as f:
        data = json.load(f)

    masks = []
    colors = []
    for path in [args.front, args.side, args.top]:
        mask, color = load_mask_and_color(path, args.size)
        masks.append(mask)
        colors.append(color)
    sdfs = [compute_sdf_gt(mask) for mask in masks]

    points = np.asarray(data["points"], dtype=np.float32)
    before_counts, _ = build_counts(points, args.size)
    before = all_metrics(before_counts, masks)

    work_counts = [c.copy() for c in before_counts]
    rng = np.random.default_rng(args.seed)
    candidates = generate_candidates(work_counts, masks, sdfs, args.size, args.eps, args.max_new, rng)
    output_data = merge_points(
        data,
        candidates,
        masks,
        colors,
        sdfs,
        args.size,
        args.target_count,
        args.replace,
        args.leakage_weight,
        args.sdf_weight,
    )

    final_points = np.asarray(output_data["points"], dtype=np.float32)
    after_counts, _ = build_counts(final_points, args.size)
    after = all_metrics(after_counts, masks)

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(output_data, f, separators=(",", ":"))

    report = {
        "schema": "sdf-coverage-resampling/v1",
        "inputs": {
            "front": args.front,
            "side": args.side,
            "top": args.top,
            "points": args.points,
        },
        "parameters": {
            "size": args.size,
            "targetCount": args.target_count,
            "maxNew": args.max_new,
            "eps": args.eps,
            "replace": args.replace,
            "seed": args.seed,
            "leakageWeight": args.leakage_weight,
            "sdfWeight": args.sdf_weight,
        },
        "before": before,
        "after": after,
        "candidates": {
            "generated": len(candidates),
            "bySource": {
                name: int(sum(c.source == name for c in candidates))
                for name in ["front", "side", "top"]
            },
        },
    }
    os.makedirs(os.path.dirname(args.report) or ".", exist_ok=True)
    with open(args.report, "w") as f:
        json.dump(report, f, indent=2)

    print(f"wrote {args.output}")
    print(f"wrote {args.report}")
    print(f"points: {len(points)} -> {len(final_points)}")
    print(
        "min recall: "
        f"{before['summary']['minRecall']:.3f} -> {after['summary']['minRecall']:.3f}"
    )
    print(
        "mean recall: "
        f"{before['summary']['meanRecall']:.3f} -> {after['summary']['meanRecall']:.3f}"
    )
    print(
        "max leakage: "
        f"{before['summary']['maxLeakageRatio']:.3f} -> {after['summary']['maxLeakageRatio']:.3f}"
    )


if __name__ == "__main__":
    main()
