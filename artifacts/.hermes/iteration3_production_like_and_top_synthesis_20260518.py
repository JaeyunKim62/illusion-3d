#!/usr/bin/env python3
"""Iteration 3 throwaway probe.

Goals:
- Mirror src/main.ts image extraction more closely than prior probes.
- Compare current shuffled max+reuse with quantile/local-color materialization on real images.
- Quantify fixed-blend vs directional-color endpoint error on actual paired colors.
- Generate an exact-feasible top support from the front/side coactivity envelope and measure how recognizable it remains against real top candidates.

Writes only under artifacts/algorithm-exploration. Does not touch production files.
"""
from __future__ import annotations

from pathlib import Path
from PIL import Image
from collections import Counter, defaultdict
import json, math, random

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "algorithm-exploration" / "iteration-3-production-like-and-top-synthesis-20260518.json"

MASK_WIDTH = 960
MASK_HEIGHT = 280
ROW_COUNT = 190
SAMPLE_STRIDE = 1
ALPHA_THRESHOLD = 64  # src/main.ts: transparent if a < 64, active otherwise
MARGIN = 28
RNG_SEED = 4792026
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
            active_pixels.append((px, py, (r / 255.0, g / 255.0, b / 255.0)))
    rows = [[] for _ in range(ROW_COUNT)]
    if not active_pixels:
        return rows
    active_height = max(1, max_y - min_y)  # exactly mirrors main.ts activeHeight without +1
    for px, py, color in active_pixels:
        normalized_y = (py - min_y) / active_height
        row = clamp(math.floor(normalized_y * (ROW_COUNT - 1)), 0, ROW_COUNT - 1)
        # coord in production is scaled float; for discrete metrics keep source px too.
        coord = ((px / (MASK_WIDTH - 1)) - 0.5) * 3.3
        rows[row].append({"px": px, "coord": coord, "color": color})
    return rows


def extract_top_mask_binned(path: Path):
    # Top proxy: same production-like draw, then x from canvas x, z from normalized active y.
    canvas = load_canvas(path, width=MASK_WIDTH, height=MASK_HEIGHT, margin=MARGIN)
    pix = canvas.load()
    active = []
    min_y = MASK_HEIGHT - 1
    max_y = 0
    for py in range(MASK_HEIGHT):
        for px in range(MASK_WIDTH):
            r, g, b, a = pix[px, py]
            if a < ALPHA_THRESHOLD:
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


def seeded_shuffle(items, rng):
    # Python equivalent of Fisher-Yates using a deterministic RNG. Not bit-identical to JS LCG, but same policy class.
    arr = list(items)
    for i in range(len(arr) - 1, 0, -1):
        j = int(rng.random() * (i + 1))
        arr[i], arr[j] = arr[j], arr[i]
    return arr


def color_chroma(c):
    return max(c) - min(c)


def color_darkness(c):
    return 1 - sum(c) / 3


def blend_reference_colors(front, side, rng):
    # Mirrors src/main.ts blendReferenceColors.
    front_signal = color_chroma(front) * 1.45 + color_darkness(front) * 1.2
    side_signal = color_chroma(side) * 1.25 + color_darkness(side) * 0.9
    front_weight = clamp(0.48 + (front_signal - side_signal) * 0.42, 0.24, 0.76)
    jitter = (rng.random() - 0.5) * 0.045
    w = clamp(front_weight + jitter, 0.22, 0.78)
    gamma = 1.35
    def mix(a, b):
        return (a ** gamma * w + b ** gamma * (1 - w)) ** (1 / gamma)
    return tuple(min(1, mix(front[k], side[k]) * 1.07) for k in range(3))


def rgb_dist(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)) / 3)


def pct(values, p):
    if not values:
        return 0
    s = sorted(values)
    return s[min(len(s) - 1, int((len(s) - 1) * p))]


def mean(values):
    return sum(values) / len(values) if values else 0


def materialize(xs, zs, policy, rng):
    if not xs or not zs:
        return []
    if policy == "current_shuffled_max_reuse":
        xs2 = seeded_shuffle(xs, rng)
        zs2 = seeded_shuffle(zs, rng)
        n = max(len(xs2), len(zs2))
        return [(xs2[i % len(xs2)], zs2[i % len(zs2)]) for i in range(n)]
    if policy == "quantile_max":
        xs2 = sorted(xs, key=lambda s: s["px"])
        zs2 = sorted(zs, key=lambda s: s["px"])
        n = max(len(xs2), len(zs2))
        return [(xs2[min(len(xs2) - 1, int((i + 0.5) * len(xs2) / n))], zs2[min(len(zs2) - 1, int((i + 0.5) * len(zs2) / n))]) for i in range(n)]
    if policy == "local_color_quantile":
        xs2 = sorted(xs, key=lambda s: s["px"])
        zs2 = sorted(zs, key=lambda s: s["px"])
        n = max(len(xs2), len(zs2))
        used = Counter()
        pairs = []
        window = max(3, min(32, int(0.04 * max(len(xs2), len(zs2)))))
        for i in range(n):
            xi = xs2[min(len(xs2) - 1, int((i + 0.5) * len(xs2) / n))]
            qz = min(len(zs2) - 1, int((i + 0.5) * len(zs2) / n))
            lo, hi = max(0, qz - window), min(len(zs2), qz + window + 1)
            best = min(range(lo, hi), key=lambda j: 0.62 * abs(j - qz) / max(1, window) + 0.30 * rgb_dist(xi["color"], zs2[j]["color"]) + 0.08 * used[j])
            used[best] += 1
            pairs.append((xi, zs2[best]))
        return pairs
    raise ValueError(policy)


def lobe_weights(theta_deg, basis):
    th = math.radians(theta_deg)
    cf = max(0.0, math.cos(th))
    cr = max(0.0, math.sin(th))
    if basis == "fixed_blend":
        return None
    if basis == "cosine_s1":
        f, r = cf, cr
    elif basis == "cosine_s2":
        f, r = cf ** 2, cr ** 2
    elif basis == "softmax_tau035":
        tau = 0.35
        f, r = math.exp(cf / tau), math.exp(cr / tau)
    elif basis == "gaussian_sigma05":
        sigma = 0.50
        f = math.exp(-0.5 * (th / sigma) ** 2)
        r = math.exp(-0.5 * ((math.pi / 2 - th) / sigma) ** 2)
    else:
        raise ValueError(basis)
    s = max(1e-12, f + r)
    return f / s, r / s


def row_policy_metrics(front_rows, side_rows, policy):
    target_f = {(s["px"], y) for y, row in enumerate(front_rows) for s in row}
    target_s = {(s["px"], y) for y, row in enumerate(side_rows) for s in row}
    proj_f, proj_s = set(), set()
    count_f, count_s = Counter(), Counter()
    conflicts = []
    fixed_f_err = []
    fixed_s_err = []
    directional = {k: {"front": [], "side": []} for k in ["cosine_s1", "cosine_s2", "softmax_tau035", "gaussian_sigma05"]}
    row_counts = []
    z_jumps = []
    rng = random.Random(RNG_SEED)
    total = 0
    for y in range(ROW_COUNT):
        pairs = materialize(front_rows[y], side_rows[y], policy, rng)
        if not pairs:
            continue
        row_counts.append(len(pairs))
        prev_z = None
        for fs, ss in pairs:
            total += 1
            proj_f.add((fs["px"], y)); proj_s.add((ss["px"], y))
            count_f[(fs["px"], y)] += 1; count_s[(ss["px"], y)] += 1
            cf, cs = fs["color"], ss["color"]
            conflicts.append(rgb_dist(cf, cs))
            blended = blend_reference_colors(cf, cs, rng)
            fixed_f_err.append(rgb_dist(blended, cf))
            fixed_s_err.append(rgb_dist(blended, cs))
            for basis in directional:
                wf0, wr0 = lobe_weights(0, basis)
                wf90, wr90 = lobe_weights(90, basis)
                c0 = tuple(wf0 * cf[k] + wr0 * cs[k] for k in range(3))
                c90 = tuple(wf90 * cf[k] + wr90 * cs[k] for k in range(3))
                directional[basis]["front"].append(rgb_dist(c0, cf))
                directional[basis]["side"].append(rgb_dist(c90, cs))
            if prev_z is not None:
                z_jumps.append(abs(ss["px"] - prev_z))
            prev_z = ss["px"]
    def iou(a, b):
        return len(a & b) / max(1, len(a | b))
    dup_f = [c for c in count_f.values() if c > 1]
    dup_s = [c for c in count_s.values() if c > 1]
    fixed_endpoint = (mean(fixed_f_err) + mean(fixed_s_err)) / 2
    dir_summary = {}
    for basis, vals in directional.items():
        endpoint = (mean(vals["front"]) + mean(vals["side"])) / 2
        dir_summary[basis] = {
            "endpoint_rmse_mean": round(endpoint, 6),
            "improvement_vs_fixed_pct": round((fixed_endpoint - endpoint) / max(1e-9, fixed_endpoint) * 100, 2),
            "front_rmse": round(mean(vals["front"]), 6),
            "side_rmse": round(mean(vals["side"]), 6),
        }
    return {
        "policy": policy,
        "points": total,
        "rows_used": sum(1 for y in range(ROW_COUNT) if front_rows[y] and side_rows[y]),
        "front_iou": round(iou(proj_f, target_f), 6),
        "side_iou": round(iou(proj_s, target_s), 6),
        "front_coverage": round(len(proj_f) / max(1, len(target_f)), 6),
        "side_coverage": round(len(proj_s) / max(1, len(target_s)), 6),
        "duplicate_front_pixels": len(dup_f),
        "duplicate_side_pixels": len(dup_s),
        "duplicate_front_max": max(dup_f) if dup_f else 1,
        "duplicate_side_max": max(dup_s) if dup_s else 1,
        "row_count_p50": pct(row_counts, 0.50),
        "row_count_p95": pct(row_counts, 0.95),
        "z_continuity_jump_mean": round(mean(z_jumps), 3),
        "z_continuity_jump_p95": pct(z_jumps, 0.95),
        "pair_color_conflict_mean": round(mean(conflicts), 6),
        "pair_color_conflict_p95": round(pct(conflicts, 0.95), 6),
        "fixed_blend_endpoint_rmse_mean": round(fixed_endpoint, 6),
        "directional_endpoint": dir_summary,
    }


def bin_rows(rows):
    binned = []
    for row in rows:
        bins = set()
        for s in row:
            bins.add(clamp(int(s["px"] * GRAPH_W / MASK_WIDTH), 0, GRAPH_W - 1))
        binned.append(bins)
    return binned


def graph_certificate(front_bins, side_bins, top_mask):
    A = {(x, y) for y, xs in enumerate(front_bins) for x in xs}
    B = {(z, y) for y, zs in enumerate(side_bins) for z in zs}
    C = set(top_mask)
    projA, projB, projC = set(), set(), set()
    vox = 0
    for y in range(ROW_COUNT):
        xs, zs = front_bins[y], side_bins[y]
        if not xs or not zs:
            continue
        for x in xs:
            for z in zs:
                if (x, z) in C:
                    vox += 1
                    projA.add((x, y)); projB.add((z, y)); projC.add((x, z))
    def iou(a, b):
        return len(a & b) / max(1, len(a | b))
    return {
        "voxels_in_H": vox,
        "front_iou": round(iou(projA, A), 6),
        "side_iou": round(iou(projB, B), 6),
        "top_iou_self": round(iou(projC, C), 6),
        "missing_front": len(A - projA),
        "missing_side": len(B - projB),
        "missing_top_self": len(C - projC),
        "exact_pass_self_098": iou(projA, A) >= .98 and iou(projB, B) >= .98 and iou(projC, C) >= .98,
    }


def synthesize_exact_top(front_bins, side_bins, target_top):
    # Construct C_gen by choosing per-row edges that cover every active x and z where possible.
    # Preference order: edges inside target_top, then nearest-to-target by Manhattan distance.
    target = set(target_top)
    if target:
        target_list = list(target)
    else:
        target_list = [(GRAPH_W // 2, GRAPH_W // 2)]
    dist_cache = {}
    def dist_to_target(edge):
        if edge in target:
            return 0
        if edge not in dist_cache:
            x, z = edge
            # Downsampled target is small enough for brute-force nearest distance.
            dist_cache[edge] = min(abs(x - tx) + abs(z - tz) for tx, tz in target_list)
        return dist_cache[edge]
    chosen = set()
    row_edge_counts = []
    target_hits = 0
    for y in range(ROW_COUNT):
        xs = sorted(front_bins[y])
        zs = sorted(side_bins[y])
        if not xs or not zs:
            continue
        covered_x, covered_z = set(), set()
        # First use target edges available in this row.
        candidates = sorted([(x, z) for x in xs for z in zs], key=lambda e: (0 if e in target else 1, dist_to_target(e), e[0] + e[1]))
        for e in candidates:
            x, z = e
            if e in target and (x not in covered_x or z not in covered_z):
                chosen.add(e); covered_x.add(x); covered_z.add(z); target_hits += 1
            if len(covered_x) == len(xs) and len(covered_z) == len(zs):
                break
        # Then cover remaining x with best z.
        for x in xs:
            if x in covered_x:
                continue
            best = min(((x, z) for z in zs), key=dist_to_target)
            chosen.add(best); covered_x.add(x); covered_z.add(best[1])
        # Then cover remaining z with best x.
        for z in zs:
            if z in covered_z:
                continue
            best = min(((x, z) for x in xs), key=dist_to_target)
            chosen.add(best); covered_x.add(best[0]); covered_z.add(z)
        row_edge_counts.append(len(covered_x) + len(covered_z))
    return chosen, {
        "row_cover_edge_proxy_p50": pct(row_edge_counts, .50),
        "row_cover_edge_proxy_p95": pct(row_edge_counts, .95),
        "target_edge_hits_during_greedy": target_hits,
    }


def top_synthesis_metrics(front_rows, side_rows, top_name, top_path):
    fb = bin_rows(front_rows); sb = bin_rows(side_rows)
    target = extract_top_mask_binned(top_path)
    # Coactivity envelope S = union_y X_y x Z_y, computed without materializing full large high-res set.
    S = set()
    for y in range(ROW_COUNT):
        for x in fb[y]:
            for z in sb[y]:
                S.add((x, z))
    target_in_S = target & S
    cgen, extra = synthesize_exact_top(fb, sb, target)
    cert = graph_certificate(fb, sb, cgen)
    def iou(a, b):
        return len(a & b) / max(1, len(a | b))
    return {
        "top": top_name,
        "graph_resolution": {"x": GRAPH_W, "y": ROW_COUNT, "z": GRAPH_W},
        "target_top_pixels": len(target),
        "coactivity_envelope_pixels": len(S),
        "target_inside_S_ratio": round(len(target_in_S) / max(1, len(target)), 6),
        "target_vs_S_iou": round(iou(target, S), 6),
        "generated_top_pixels": len(cgen),
        "generated_vs_target_iou": round(iou(cgen, target), 6),
        "generated_target_precision": round(len(cgen & target) / max(1, len(cgen)), 6),
        "generated_target_recall": round(len(cgen & target) / max(1, len(target)), 6),
        **extra,
        **cert,
    }


def main():
    refs = {
        "goose": ROOT / "artifacts/reference-image/goose.png",
        "nubzuki": ROOT / "artifacts/reference-image/nubzuki.png",
        "cake": ROOT / "artifacts/reference-image/cake.png",
        "phoenix": ROOT / "artifacts/reference-image/phoenix.png",
        "kumdori": ROOT / "artifacts/reference-image/kumdori.png",
    }
    front_rows = extract_rows_production_like(refs["goose"])
    side_sets = {"nubzuki": extract_rows_production_like(refs["nubzuki"]), "cake": extract_rows_production_like(refs["cake"])}
    row_results = []
    top_results = []
    for side_name, side_rows in side_sets.items():
        row_results.append({
            "front": "goose",
            "side": side_name,
            "extraction": {"mask_width": MASK_WIDTH, "mask_height": MASK_HEIGHT, "row_count": ROW_COUNT, "alpha_threshold": ALPHA_THRESHOLD, "margin": MARGIN},
            "front_active_pixels": sum(len(r) for r in front_rows),
            "side_active_pixels": sum(len(r) for r in side_rows),
            "policies": [row_policy_metrics(front_rows, side_rows, p) for p in ["current_shuffled_max_reuse", "quantile_max", "local_color_quantile"]],
        })
        for top_name in ["phoenix", "kumdori"]:
            top_results.append({"front": "goose", "side": side_name, **top_synthesis_metrics(front_rows, side_rows, top_name, refs[top_name])})
    data = {
        "note": "throwaway iteration 3; production-like extraction constants mirrored from src/main.ts; no production files modified",
        "row_policy_and_directional_color": row_results,
        "exact_feasible_top_synthesis": top_results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
