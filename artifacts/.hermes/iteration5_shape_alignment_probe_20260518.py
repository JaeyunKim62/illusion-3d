#!/usr/bin/env python3
"""Iteration 5 throwaway probe.

Adds two missing pieces from iteration 4:
1) top recognizability morphology metrics, not only IoU/recall;
2) integer row-alignment sweep to test whether active-bound row mismatch is a major cause.

Writes only under artifacts/algorithm-exploration. Does not touch production files.
"""
from __future__ import annotations

from pathlib import Path
from PIL import Image
from collections import deque
import json, math

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "algorithm-exploration" / "iteration-5-shape-alignment-probe-20260518.json"

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


def shift_rows(rows, dy):
    shifted = [set() for _ in range(ROW_COUNT)]
    for y, xs in enumerate(rows):
        yy = y + dy
        if 0 <= yy < ROW_COUNT:
            shifted[yy] |= set(xs)
    return shifted


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


def two_view_upper(front_bins, side_bins):
    A = {(x, y) for y, xs in enumerate(front_bins) for x in xs}
    B = {(z, y) for y, zs in enumerate(side_bins) for z in zs}
    front_in = {(x, y) for (x, y) in A if side_bins[y]}
    side_in = {(z, y) for (z, y) in B if front_bins[y]}
    return {
        "front": len(front_in) / max(1, len(A)),
        "side": len(side_in) / max(1, len(B)),
        "harmonic": 2 * (len(front_in) / max(1, len(A))) * (len(side_in) / max(1, len(B))) / max(1e-9, (len(front_in) / max(1, len(A))) + (len(side_in) / max(1, len(B))))
    }


def row_alignment_sweep(front_bins, side_bins, radius=30):
    rows = []
    for dy in range(-radius, radius + 1):
        m = two_view_upper(front_bins, shift_rows(side_bins, dy))
        rows.append({"side_row_shift": dy, "front_upper": round(m["front"], 6), "side_upper": round(m["side"], 6), "harmonic_upper": round(m["harmonic"], 6)})
    best_h = max(rows, key=lambda r: r["harmonic_upper"])
    best_min = max(rows, key=lambda r: min(r["front_upper"], r["side_upper"]))
    baseline = next(r for r in rows if r["side_row_shift"] == 0)
    return {"baseline": baseline, "best_harmonic": best_h, "best_minimum": best_min, "sweep": rows}


def envelope(front_bins, side_bins):
    S = set()
    for y in range(ROW_COUNT):
        for x in front_bins[y]:
            for z in side_bins[y]:
                S.add((x, z))
    return S


def greedy_cover_top(front_bins, side_bins, preferred):
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


def shape_metrics(points, w=GRAPH_W, h=GRAPH_W):
    pts = set(points)
    if not pts:
        return {"pixels": 0, "component_count": 0, "largest_component_ratio": 0, "isolated_pixel_ratio": 0, "mean_8neighbor_count": 0, "endpoint_count": 0, "branchpoint_count": 0, "bbox_fill_ratio": 0}
    seen = set()
    comps = []
    for p in pts:
        if p in seen:
            continue
        q = deque([p]); seen.add(p); comp = []
        while q:
            x, y = q.popleft(); comp.append((x, y))
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    n = (x + dx, y + dy)
                    if n in pts and n not in seen:
                        seen.add(n); q.append(n)
        comps.append(comp)
    neigh_counts = []
    for x, y in pts:
        c = 0
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                if (x + dx, y + dy) in pts:
                    c += 1
        neigh_counts.append(c)
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    bbox_area = max(1, (max(xs) - min(xs) + 1) * (max(ys) - min(ys) + 1))
    return {
        "pixels": len(pts),
        "component_count": len(comps),
        "largest_component_ratio": round(max(len(c) for c in comps) / len(pts), 6),
        "isolated_pixel_ratio": round(sum(1 for c in neigh_counts if c == 0) / len(pts), 6),
        "mean_8neighbor_count": round(sum(neigh_counts) / len(neigh_counts), 6),
        "endpoint_count": sum(1 for c in neigh_counts if c == 1),
        "branchpoint_count": sum(1 for c in neigh_counts if c >= 4),
        "bbox_fill_ratio": round(len(pts) / bbox_area, 6),
    }


def compare_shape(candidate, target):
    cm = shape_metrics(candidate)
    tm = shape_metrics(target)
    return {
        "candidate": cm,
        "target": tm,
        "component_count_ratio_vs_target": round(cm["component_count"] / max(1, tm["component_count"]), 6),
        "largest_component_ratio_delta": round(cm["largest_component_ratio"] - tm["largest_component_ratio"], 6),
        "isolated_pixel_ratio_delta": round(cm["isolated_pixel_ratio"] - tm["isolated_pixel_ratio"], 6),
        "mean_neighbor_delta": round(cm["mean_8neighbor_count"] - tm["mean_8neighbor_count"], 6),
        "bbox_fill_ratio_delta": round(cm["bbox_fill_ratio"] - tm["bbox_fill_ratio"], 6),
    }


def top_shape_recognizability(front_bins, side_bins, target):
    S = envelope(front_bins, side_bins)
    c_intersection = target & S
    c_cover = greedy_cover_top(front_bins, side_bins, c_intersection)
    return {
        "target_inside_S_ratio": round(len(c_intersection) / max(1, len(target)), 6),
        "target_shape": shape_metrics(target),
        "candidate_target_intersection_S": {
            "iou_vs_target": round(iou(c_intersection, target), 6),
            "precision_vs_target": round(len(c_intersection & target) / max(1, len(c_intersection)), 6),
            "recall_vs_target": round(len(c_intersection & target) / max(1, len(target)), 6),
            "shape_compare": compare_shape(c_intersection, target),
        },
        "candidate_greedy_cover": {
            "iou_vs_target": round(iou(c_cover, target), 6),
            "precision_vs_target": round(len(c_cover & target) / max(1, len(c_cover)), 6),
            "recall_vs_target": round(len(c_cover & target) / max(1, len(target)), 6),
            "shape_compare": compare_shape(c_cover, target),
        },
    }


def main():
    refs = {
        "goose": ROOT / "artifacts/reference-image/goose.png",
        "nubzuki": ROOT / "artifacts/reference-image/nubzuki.png",
        "cake": ROOT / "artifacts/reference-image/cake.png",
        "phoenix": ROOT / "artifacts/reference-image/phoenix.png",
        "kumdori": ROOT / "artifacts/reference-image/kumdori.png",
    }
    front = bin_rows(extract_rows_production_like(refs["goose"]))
    sides = {name: bin_rows(extract_rows_production_like(refs[name])) for name in ["nubzuki", "cake"]}
    tops = {name: top_mask_binned(refs[name]) for name in ["phoenix", "kumdori"]}

    out = {
        "note": "throwaway iteration 5; production files not modified; PIL proxy using production constants",
        "extraction": {"mask_width": MASK_WIDTH, "mask_height": MASK_HEIGHT, "row_count": ROW_COUNT, "alpha_threshold": ALPHA_THRESHOLD, "margin": MARGIN, "graph_w": GRAPH_W},
        "row_alignment_sweep": [],
        "top_shape_recognizability": [],
    }
    for side_name, side in sides.items():
        out["row_alignment_sweep"].append({"front": "goose", "side": side_name, **row_alignment_sweep(front, side, 30)})
        for top_name, top in tops.items():
            out["top_shape_recognizability"].append({"front": "goose", "side": side_name, "top": top_name, **top_shape_recognizability(front, side, top)})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
