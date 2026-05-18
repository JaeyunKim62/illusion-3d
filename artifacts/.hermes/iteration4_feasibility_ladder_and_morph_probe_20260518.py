#!/usr/bin/env python3
"""Iteration 4 throwaway probe.

Adds two missing pieces from iteration 3:
1) explicit 2-view row-support upper-bound certificate + top support trade-off sweep;
2) angular morph support-difference decision test: color-only vs geometry-needed.

Writes only under artifacts/algorithm-exploration. Does not touch production files.
"""
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageChops, ImageFilter
from collections import deque
import json, math

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "algorithm-exploration" / "iteration-4-feasibility-ladder-and-morph-probe-20260518.json"

MASK_WIDTH = 960
MASK_HEIGHT = 280
ROW_COUNT = 190
SAMPLE_STRIDE = 1
ALPHA_THRESHOLD = 64
MARGIN = 28
GRAPH_W = 96


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def load_canvas(path: Path, width=MASK_WIDTH, height=MASK_HEIGHT, margin=MARGIN):
    im = Image.open(path).convert("RGBA")
    sw, sh = im.size
    scale = min((width - margin * 2) / sw, (height - margin * 2) / sh)
    nw, nh = max(1, round(sw * scale)), max(1, round(sh * scale))
    resized = im.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    canvas.alpha_composite(resized, ((width - nw) // 2, (height - nh) // 2))
    return canvas


def extract_rows_production_like(path: Path):
    canvas = load_canvas(path)
    pix = canvas.load()
    active_pixels = []
    min_y = MASK_HEIGHT - 1
    max_y = 0
    for py in range(0, MASK_HEIGHT, SAMPLE_STRIDE):
        for px in range(0, MASK_WIDTH, SAMPLE_STRIDE):
            r, g, b, a = pix[px, py]
            if a < ALPHA_THRESHOLD:
                continue
            min_y = min(min_y, py)
            max_y = max(max_y, py)
            active_pixels.append((px, py))
    rows = [[] for _ in range(ROW_COUNT)]
    if not active_pixels:
        return rows
    active_height = max(1, max_y - min_y)
    for px, py in active_pixels:
        row = clamp(math.floor(((py - min_y) / active_height) * (ROW_COUNT - 1)), 0, ROW_COUNT - 1)
        rows[row].append(px)
    return rows


def bin_rows(rows):
    out = []
    for row in rows:
        out.append({clamp(int(px * GRAPH_W / MASK_WIDTH), 0, GRAPH_W - 1) for px in row})
    return out


def top_mask_binned(path: Path):
    canvas = load_canvas(path)
    pix = canvas.load()
    active = []
    min_y = MASK_HEIGHT - 1
    max_y = 0
    for py in range(MASK_HEIGHT):
        for px in range(MASK_WIDTH):
            if pix[px, py][3] < ALPHA_THRESHOLD:
                continue
            min_y = min(min_y, py)
            max_y = max(max_y, py)
            active.append((px, py))
    if not active:
        return set()
    active_height = max(1, max_y - min_y)
    out = set()
    for px, py in active:
        x = clamp(int(px * GRAPH_W / MASK_WIDTH), 0, GRAPH_W - 1)
        z = clamp(math.floor(((py - min_y) / active_height) * (GRAPH_W - 1)), 0, GRAPH_W - 1)
        out.add((x, z))
    return out


def iou(a, b):
    return len(a & b) / max(1, len(a | b))


def pct(values, p):
    if not values:
        return 0
    s = sorted(values)
    return s[min(len(s) - 1, int((len(s) - 1) * p))]


def two_view_row_support(front_bins, side_bins):
    A = {(x, y) for y, xs in enumerate(front_bins) for x in xs}
    B = {(z, y) for y, zs in enumerate(side_bins) for z in zs}
    front_in_matched = {(x, y) for (x, y) in A if side_bins[y]}
    side_in_matched = {(z, y) for (z, y) in B if front_bins[y]}
    front_only_rows = [y for y in range(ROW_COUNT) if front_bins[y] and not side_bins[y]]
    side_only_rows = [y for y in range(ROW_COUNT) if side_bins[y] and not front_bins[y]]
    return {
        "front_pixels": len(A),
        "side_pixels": len(B),
        "front_pixels_in_matched_rows_ratio": round(len(front_in_matched) / max(1, len(A)), 6),
        "side_pixels_in_matched_rows_ratio": round(len(side_in_matched) / max(1, len(B)), 6),
        "front_only_row_count": len(front_only_rows),
        "side_only_row_count": len(side_only_rows),
        "front_only_rows_first10": front_only_rows[:10],
        "side_only_rows_first10": side_only_rows[:10],
        "matched_row_count": sum(1 for y in range(ROW_COUNT) if front_bins[y] and side_bins[y]),
    }


def graph_certificate(front_bins, side_bins, C):
    A = {(x, y) for y, xs in enumerate(front_bins) for x in xs}
    B = {(z, y) for y, zs in enumerate(side_bins) for z in zs}
    projA, projB, projC = set(), set(), set()
    edge_counts = []
    voxels = 0
    for y in range(ROW_COUNT):
        xs, zs = front_bins[y], side_bins[y]
        count = 0
        if xs and zs:
            for x in xs:
                for z in zs:
                    if (x, z) in C:
                        voxels += 1
                        count += 1
                        projA.add((x, y)); projB.add((z, y)); projC.add((x, z))
        if count:
            edge_counts.append(count)
    return {
        "top_pixels": len(C),
        "voxels_in_H": voxels,
        "front_iou": round(iou(projA, A), 6),
        "side_iou": round(iou(projB, B), 6),
        "top_iou_self": round(iou(projC, C), 6),
        "missing_front": len(A - projA),
        "missing_side": len(B - projB),
        "missing_top_self": len(C - projC),
        "row_edge_count_p50": pct(edge_counts, 0.50),
        "row_edge_count_p95": pct(edge_counts, 0.95),
        "row_edge_count_max": max(edge_counts) if edge_counts else 0,
    }


def dilate_edges(edges, r):
    if r <= 0:
        return set(edges)
    out = set()
    for x, z in edges:
        for dx in range(-r, r + 1):
            for dz in range(-r, r + 1):
                if abs(dx) + abs(dz) <= r:
                    xx, zz = x + dx, z + dz
                    if 0 <= xx < GRAPH_W and 0 <= zz < GRAPH_W:
                        out.add((xx, zz))
    return out


def envelope(front_bins, side_bins):
    S = set()
    for y in range(ROW_COUNT):
        for x in front_bins[y]:
            for z in side_bins[y]:
                S.add((x, z))
    return S


def greedy_cover_top(front_bins, side_bins, preferred):
    # Cover active x/z per matched row; choose preferred edges first, then nearest preferred.
    pref = set(preferred)
    pref_list = list(pref) or [(GRAPH_W // 2, GRAPH_W // 2)]
    dist_cache = {}
    def dist(e):
        if e in pref:
            return 0
        if e not in dist_cache:
            x, z = e
            dist_cache[e] = min(abs(x - tx) + abs(z - tz) for tx, tz in pref_list)
        return dist_cache[e]
    chosen = set()
    for y in range(ROW_COUNT):
        xs, zs = sorted(front_bins[y]), sorted(side_bins[y])
        if not xs or not zs:
            continue
        covered_x, covered_z = set(), set()
        candidates = sorted(((x, z) for x in xs for z in zs), key=lambda e: (0 if e in pref else 1, dist(e), e[0] + e[1]))
        for e in candidates:
            x, z = e
            if e in pref and (x not in covered_x or z not in covered_z):
                chosen.add(e); covered_x.add(x); covered_z.add(z)
            if len(covered_x) == len(xs) and len(covered_z) == len(zs):
                break
        for x in xs:
            if x not in covered_x:
                e = min(((x, z) for z in zs), key=dist)
                chosen.add(e); covered_x.add(x); covered_z.add(e[1])
        for z in zs:
            if z not in covered_z:
                e = min(((x, z) for x in xs), key=dist)
                chosen.add(e); covered_x.add(e[0]); covered_z.add(z)
    return chosen


def top_tradeoff(front_bins, side_bins, target):
    S = envelope(front_bins, side_bins)
    results = []
    for r in [0, 1, 2, 4, 8]:
        preferred = dilate_edges(target, r) & S
        c_intersection = preferred
        c_cover = greedy_cover_top(front_bins, side_bins, preferred)
        for mode, C in [("target_dilation_intersection", c_intersection), ("cover_greedy_biased_to_dilated_target", c_cover)]:
            cert = graph_certificate(front_bins, side_bins, C)
            results.append({
                "mode": mode,
                "target_dilation_radius": r,
                "preferred_inside_S_ratio_vs_target": round(len(preferred & target) / max(1, len(target)), 6),
                "top_vs_original_target_iou": round(iou(C, target), 6),
                "top_precision_against_original_target": round(len(C & target) / max(1, len(C)), 6),
                "top_recall_against_original_target": round(len(C & target) / max(1, len(target)), 6),
                **cert,
            })
    return {
        "coactivity_envelope_pixels": len(S),
        "target_top_pixels": len(target),
        "target_inside_S_ratio": round(len(target & S) / max(1, len(target)), 6),
        "sweep": results,
    }


def alpha_mask(path: Path):
    canvas = load_canvas(path)
    alpha = canvas.getchannel("A")
    return alpha.point(lambda a: 255 if a >= ALPHA_THRESHOLD else 0).convert("1")


def shift_mask(mask, dx, dy):
    return ImageChops.offset(mask.convert("L"), dx, dy).point(lambda v: 255 if v else 0).convert("1")


def dilate_mask(mask, radius):
    if radius <= 0:
        return mask.convert("1")
    # MaxFilter size must be odd; approximates L_inf dilation, conservative for support tolerance.
    return mask.convert("L").filter(ImageFilter.MaxFilter(radius * 2 + 1)).point(lambda v: 255 if v else 0).convert("1")


def mask_set(mask):
    pix = mask.load()
    return {(x, y) for y in range(mask.height) for x in range(mask.width) if pix[x, y]}


def support_compare(canon, target, tolerance):
    A, B = mask_set(canon), mask_set(target)
    Ad = mask_set(dilate_mask(canon, tolerance))
    Bd = mask_set(dilate_mask(target, tolerance))
    outside_target = len(B - Ad)
    outside_canon = len(A - Bd)
    sym = len(A ^ B)
    return {
        "tolerance_px": tolerance,
        "canonical_pixels": len(A),
        "target_pixels": len(B),
        "raw_iou": round(iou(A, B), 6),
        "symmetric_difference_ratio": round(sym / max(1, len(A | B)), 6),
        "target_pixels_outside_canonical_dilation_ratio": round(outside_target / max(1, len(B)), 6),
        "canonical_pixels_outside_target_dilation_ratio": round(outside_canon / max(1, len(A)), 6),
        "color_only_pass": outside_target == 0 and outside_canon == 0,
    }


def morph_decision(mask):
    cases = []
    # Synthetic color-only: same support.
    cases.append({"case": "same_support_color_only", "dx": 0, "dy": 0, "comparisons": [support_compare(mask, mask, t) for t in [0, 1, 2, 4]]})
    for dx in [2, 4, 8, 16]:
        shifted = shift_mask(mask, dx, 0)
        comparisons = [support_compare(mask, shifted, t) for t in [0, 1, 2, 4, 8]]
        first_pass = next((c["tolerance_px"] for c in comparisons if c["color_only_pass"]), None)
        cases.append({"case": f"whole_support_shift_{dx}px", "dx": dx, "dy": 0, "first_tolerance_that_covers_both_supports": first_pass, "comparisons": comparisons})
    return cases


def main():
    refs = {
        "goose": ROOT / "artifacts/reference-image/goose.png",
        "nubzuki": ROOT / "artifacts/reference-image/nubzuki.png",
        "cake": ROOT / "artifacts/reference-image/cake.png",
        "phoenix": ROOT / "artifacts/reference-image/phoenix.png",
        "kumdori": ROOT / "artifacts/reference-image/kumdori.png",
    }
    front = bin_rows(extract_rows_production_like(refs["goose"]))
    side_sets = {"nubzuki": bin_rows(extract_rows_production_like(refs["nubzuki"])), "cake": bin_rows(extract_rows_production_like(refs["cake"]))}
    top_masks = {"phoenix": top_mask_binned(refs["phoenix"]), "kumdori": top_mask_binned(refs["kumdori"])}

    pairs = []
    for side_name, side in side_sets.items():
        entry = {"front": "goose", "side": side_name, "two_view_row_support_upper_bound": two_view_row_support(front, side), "top_tradeoffs": []}
        for top_name, top in top_masks.items():
            entry["top_tradeoffs"].append({"top": top_name, **top_tradeoff(front, side, top)})
        pairs.append(entry)

    data = {
        "note": "throwaway iteration 4; production files not modified; PIL proxy using production constants",
        "extraction": {"mask_width": MASK_WIDTH, "mask_height": MASK_HEIGHT, "row_count": ROW_COUNT, "alpha_threshold": ALPHA_THRESHOLD, "margin": MARGIN, "graph_w": GRAPH_W},
        "feasibility_ladder": pairs,
        "angular_morph_support_test": {"front": "goose", "cases": morph_decision(alpha_mask(refs["goose"]))},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
