#!/usr/bin/env python3
"""Iteration 8 throwaway probe: rendered endpoint color + quantile rounding certificates.

Writes only under artifacts/algorithm-exploration. Does not touch production files.
This is still a PIL proxy for browser canvas extraction, but mirrors main.ts constants.
"""
from __future__ import annotations

import json, math, random
from collections import defaultdict
from pathlib import Path
from statistics import mean, median
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "algorithm-exploration" / "iteration-8-rendered-endpoint-and-rounding-probe-20260518.json"
REF = ROOT / "artifacts" / "reference-image"

MASK_WIDTH = 960
MASK_HEIGHT = 280
ROW_COUNT = 190
SAMPLE_STRIDE = 1
MARGIN = 28
ALPHA_THRESHOLD = 64

PAIRS = [("goose", "nubzuki"), ("goose", "cake")]


def draw_reference(name: str) -> Image.Image:
    src = Image.open(REF / f"{name}.png").convert("RGBA")
    canvas = Image.new("RGBA", (MASK_WIDTH, MASK_HEIGHT), (0, 0, 0, 0))
    sw, sh = src.size
    scale = min((MASK_WIDTH - MARGIN * 2) / sw, (MASK_HEIGHT - MARGIN * 2) / sh)
    w, h = int(round(sw * scale)), int(round(sh * scale))
    resized = src.resize((w, h), Image.Resampling.BICUBIC)
    canvas.alpha_composite(resized, ((MASK_WIDTH - w) // 2, (MASK_HEIGHT - h) // 2))
    return canvas


def extract_rows(img: Image.Image):
    pix = img.load()
    rows = [[] for _ in range(ROW_COUNT)]
    min_y, max_y, has = MASK_HEIGHT - 1, 0, False
    for y in range(0, MASK_HEIGHT, SAMPLE_STRIDE):
        for x in range(0, MASK_WIDTH, SAMPLE_STRIDE):
            if pix[x, y][3] < ALPHA_THRESHOLD:
                continue
            min_y = min(min_y, y)
            max_y = max(max_y, y)
            has = True
    if not has:
        return rows
    active_h = max(1, max_y - min_y)
    for y in range(0, MASK_HEIGHT, SAMPLE_STRIDE):
        row = max(0, min(ROW_COUNT - 1, int(math.floor(((y - min_y) / active_h) * (ROW_COUNT - 1)))))
        for x in range(0, MASK_WIDTH, SAMPLE_STRIDE):
            r, g, b, a = pix[x, y]
            if a < ALPHA_THRESHOLD:
                continue
            rows[row].append({"px": x, "rgb": (r / 255.0, g / 255.0, b / 255.0)})
    return rows


def chroma(c): return max(c) - min(c)
def darkness(c): return 1.0 - sum(c) / 3.0
def clamp(v, lo, hi): return max(lo, min(hi, v))

def blend_reference(front, side, rng):
    front_signal = chroma(front) * 1.45 + darkness(front) * 1.2
    side_signal = chroma(side) * 1.25 + darkness(side) * 0.9
    front_weight = clamp(0.48 + (front_signal - side_signal) * 0.42, 0.24, 0.76)
    jitter = (rng.random() - 0.5) * 0.045
    w = clamp(front_weight + jitter, 0.22, 0.78)
    gamma = 1.35
    return tuple(((front[i] ** gamma) * w + (side[i] ** gamma) * (1 - w)) ** (1 / gamma) for i in range(3))


def quantile_idx(k, src_len, n):
    return max(0, min(src_len - 1, int(math.floor(((k + 0.5) * src_len) / n))))


def materialize(front_rows, side_rows, policy, seed=18260518):
    rng = random.Random(seed)
    pairs = []
    row_certs = []
    for row in range(ROW_COUNT):
        X = list(front_rows[row])
        Z = list(side_rows[row])
        if not X or not Z:
            continue
        if policy == "current_shuffled_max_reuse":
            rng.shuffle(X); rng.shuffle(Z)
            n = max(len(X), len(Z))
            row_pairs = [(X[k % len(X)], Z[k % len(Z)], row) for k in range(n)]
        elif policy == "quantile_max":
            X.sort(key=lambda s: s["px"]); Z.sort(key=lambda s: s["px"])
            n = max(len(X), len(Z))
            row_pairs = [(X[quantile_idx(k, len(X), n)], Z[quantile_idx(k, len(Z), n)], row) for k in range(n)]
        else:
            raise ValueError(policy)
        pairs.extend(row_pairs)
        fx = defaultdict(int); sz = defaultdict(int)
        for f, s, _ in row_pairs:
            fx[f["px"]] += 1; sz[s["px"]] += 1
        # For max/quantile materialization the shorter marginal must be duplicated.
        row_certs.append({
            "row": row,
            "front_count": len(X),
            "side_count": len(Z),
            "n": n,
            "front_covered_ratio": len(fx) / len(set(v["px"] for v in X)),
            "side_covered_ratio": len(sz) / len(set(v["px"] for v in Z)),
            "front_mult_max": max(fx.values()),
            "side_mult_max": max(sz.values()),
            "front_mult_spread": max(fx.values()) - min(fx.values()),
            "side_mult_spread": max(sz.values()) - min(sz.values()),
        })
    return pairs, row_certs


def rmse(values):
    if not values: return None
    return math.sqrt(sum(v*v for v in values) / len(values))

def l2(a,b):
    return math.sqrt(sum((a[i]-b[i])**2 for i in range(3)))


def rendered_endpoint_metrics(pairs, policy):
    # Accumulate target and rendered colors at unique projection samples.
    # fixed blend uses production-like single RGB; directional endpoints use front/side colors.
    rng = random.Random(771823 if policy.startswith("current") else 771824)
    accum = {
        "front_fixed": defaultdict(list), "side_fixed": defaultdict(list),
        "front_dir": defaultdict(list), "side_dir": defaultdict(list),
        "front_target": {}, "side_target": {},
    }
    for f, s, row in pairs:
        fixed = blend_reference(f["rgb"], s["rgb"], rng)
        fk = (row, f["px"]); sk = (row, s["px"])
        accum["front_fixed"][fk].append(fixed)
        accum["side_fixed"][sk].append(fixed)
        accum["front_dir"][fk].append(f["rgb"])
        accum["side_dir"][sk].append(s["rgb"])
        accum["front_target"][fk] = f["rgb"]
        accum["side_target"][sk] = s["rgb"]
    def avg(cs): return tuple(sum(c[i] for c in cs)/len(cs) for i in range(3))
    out = {}
    for view in ["front", "side"]:
        target = accum[f"{view}_target"]
        fixed_err = []
        dir_err = []
        dup_counts = []
        for k, t in target.items():
            fixed_err.append(l2(avg(accum[f"{view}_fixed"][k]), t))
            dir_err.append(l2(avg(accum[f"{view}_dir"][k]), t))
            dup_counts.append(len(accum[f"{view}_fixed"][k]))
        out[f"{view}_unique_projected_pixels"] = len(target)
        out[f"{view}_fixed_rendered_rmse"] = rmse(fixed_err)
        out[f"{view}_directional_endpoint_rmse"] = rmse(dir_err)
        out[f"{view}_fixed_err_p95"] = sorted(fixed_err)[int(0.95*(len(fixed_err)-1))] if fixed_err else None
        out[f"{view}_duplicate_mean"] = mean(dup_counts) if dup_counts else 0
        out[f"{view}_duplicate_p95"] = sorted(dup_counts)[int(0.95*(len(dup_counts)-1))] if dup_counts else 0
        out[f"{view}_duplicate_max"] = max(dup_counts) if dup_counts else 0
    return out


def summarize_certs(certs):
    def vals(k): return [c[k] for c in certs]
    if not certs: return {}
    return {
        "row_count": len(certs),
        "front_coverage_min": min(vals("front_covered_ratio")),
        "side_coverage_min": min(vals("side_covered_ratio")),
        "front_mult_spread_max": max(vals("front_mult_spread")),
        "side_mult_spread_max": max(vals("side_mult_spread")),
        "front_mult_max_p95": sorted(vals("front_mult_max"))[int(0.95*(len(certs)-1))],
        "side_mult_max_p95": sorted(vals("side_mult_max"))[int(0.95*(len(certs)-1))],
        "front_count_median": median(vals("front_count")),
        "side_count_median": median(vals("side_count")),
    }


def main():
    results = {"note": "PIL proxy; production files untouched; endpoint color is projection-pixel averaged, not real WebGL splat capture.", "pairs": {}}
    for front_name, side_name in PAIRS:
        front_rows = extract_rows(draw_reference(front_name))
        side_rows = extract_rows(draw_reference(side_name))
        key = f"{front_name}+{side_name}"
        results["pairs"][key] = {}
        for policy in ["current_shuffled_max_reuse", "quantile_max"]:
            pairs, certs = materialize(front_rows, side_rows, policy)
            metrics = rendered_endpoint_metrics(pairs, policy)
            metrics.update({"points": len(pairs), "rounding_certificate": summarize_certs(certs)})
            # Certificate assertions for quantile: full coverage of matched-row marginals and spread <=1.
            metrics["integer_materialization_gate"] = {
                "all_matched_front_pixels_covered": metrics["rounding_certificate"].get("front_coverage_min") == 1.0,
                "all_matched_side_pixels_covered": metrics["rounding_certificate"].get("side_coverage_min") == 1.0,
                "front_multiplicity_spread_lte1": metrics["rounding_certificate"].get("front_mult_spread_max", 9) <= 1,
                "side_multiplicity_spread_lte1": metrics["rounding_certificate"].get("side_mult_spread_max", 9) <= 1,
            }
            results["pairs"][key][policy] = metrics
        # Deltas: fixed blend rendered error vs directional endpoint on quantile.
        q = results["pairs"][key]["quantile_max"]
        results["pairs"][key]["directional_vs_fixed_on_quantile"] = {
            "front_rmse_reduction_fraction": 1 - (q["front_directional_endpoint_rmse"] / max(1e-9, q["front_fixed_rendered_rmse"])),
            "side_rmse_reduction_fraction": 1 - (q["side_directional_endpoint_rmse"] / max(1e-9, q["side_fixed_rendered_rmse"])),
        }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(OUT)

if __name__ == "__main__":
    main()
