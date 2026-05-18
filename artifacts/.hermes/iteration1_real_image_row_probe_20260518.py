#!/usr/bin/env python3
"""Iteration 1 throwaway probe: real reference-image row matching metrics.
Writes JSON only under artifacts/algorithm-exploration. Does not touch production files.
"""
from __future__ import annotations
from PIL import Image
from pathlib import Path
from collections import defaultdict, Counter
import json, math

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "algorithm-exploration" / "iteration-1-real-image-row-probe-20260518.json"
W = 192
ROW_COUNT = 96
ALPHA_THRESHOLD = 16


def load_rows(path: Path):
    im = Image.open(path).convert("RGBA")
    # Preserve aspect ratio in square-ish canvas; production uses canvas extraction, this is a research proxy.
    im.thumbnail((W, ROW_COUNT), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (W, ROW_COUNT), (0, 0, 0, 0))
    canvas.alpha_composite(im, ((W - im.width)//2, (ROW_COUNT - im.height)//2))
    pix = canvas.load()
    active = []
    for y in range(ROW_COUNT):
        for x in range(W):
            r,g,b,a = pix[x,y]
            if a > ALPHA_THRESHOLD:
                active.append((x,y))
    if not active:
        raise RuntimeError(f"no active pixels in {path}")
    miny = min(y for _,y in active); maxy = max(y for _,y in active)
    # Normalize active vertical extent to ROW_COUNT rows, similar to existing implementation's active bounds idea.
    rows = defaultdict(list)
    denom = max(1, maxy-miny+1)
    for x,y in active:
        nr = min(ROW_COUNT-1, max(0, int((y-miny) * ROW_COUNT / denom)))
        rows[nr].append((x, pix[x,y][:3]))
    for y in rows:
        # collapse multiple source pixels at same x by average color
        byx = defaultdict(list)
        for x,c in rows[y]: byx[x].append(c)
        rows[y] = [(x, tuple(round(sum(c[k] for c in cs)/len(cs)) for k in range(3))) for x,cs in byx.items()]
        rows[y].sort(key=lambda t:t[0])
    return rows


def rgb_dist(a,b):
    return math.sqrt(sum((a[i]-b[i])**2 for i in range(3))/3)/255.0


def materialize_pairs(xs, zs, policy):
    if not xs or not zs: return []
    if policy == "min_quantile":
        n = min(len(xs), len(zs))
        return [(xs[min(len(xs)-1, int((i+0.5)*len(xs)/n))], zs[min(len(zs)-1, int((i+0.5)*len(zs)/n))]) for i in range(n)]
    n = max(len(xs), len(zs))
    if policy == "current_modulo":
        return [(xs[i % len(xs)], zs[i % len(zs)]) for i in range(n)]
    if policy == "quantile_max":
        return [(xs[min(len(xs)-1, int((i+0.5)*len(xs)/n))], zs[min(len(zs)-1, int((i+0.5)*len(zs)/n))]) for i in range(n)]
    if policy == "color_aware_local":
        # Quantile anchor plus small local color search. Not a full OT solver; intended to test whether
        # real image colors contain exploitable pairing signal without changing coverage.
        pairs = []
        used_z = Counter()
        window = max(2, min(12, int(0.08 * max(len(xs), len(zs)))))
        for i in range(n):
            qz = min(len(zs)-1, int((i+0.5)*len(zs)/n))
            xi = xs[min(len(xs)-1, int((i+0.5)*len(xs)/n))]
            lo, hi = max(0, qz-window), min(len(zs), qz+window+1)
            # penalty keeps z ordering/materialization close to quantile and discourages overusing one z.
            best = min(range(lo,hi), key=lambda j: 0.65*abs(j-qz)/max(1,window) + 0.30*rgb_dist(xi[1], zs[j][1]) + 0.05*used_z[j])
            used_z[best] += 1
            pairs.append((xi, zs[best]))
        return pairs
    raise ValueError(policy)


def policy_metrics(front_rows, side_rows, policy):
    targetF = {(x,y) for y,row in front_rows.items() for x,_ in row}
    targetS = {(z,y) for y,row in side_rows.items() for z,_ in row}
    projF, projS = set(), set()
    countsF, countsS = Counter(), Counter()
    row_counts = []
    conflicts = []
    blend_f_err = []
    blend_s_err = []
    continuity_jumps = []
    total_pairs = 0
    rows_used = 0
    for y in range(ROW_COUNT):
        xs = front_rows.get(y, [])
        zs = side_rows.get(y, [])
        pairs = materialize_pairs(xs, zs, policy)
        if not pairs: continue
        rows_used += 1
        row_counts.append(len(pairs))
        prev = None
        for (x,cf),(z,cs) in pairs:
            total_pairs += 1
            projF.add((x,y)); projS.add((z,y))
            countsF[(x,y)] += 1; countsS[(z,y)] += 1
            conflicts.append(rgb_dist(cf,cs))
            blend = tuple((cf[k]+cs[k])/2 for k in range(3))
            blend_f_err.append(rgb_dist(blend, cf))
            blend_s_err.append(rgb_dist(blend, cs))
            if prev is not None:
                continuity_jumps.append(abs(z-prev))
            prev = z
    def iou(a,b): return len(a & b) / max(1, len(a | b))
    def mean(v): return sum(v)/len(v) if v else 0
    def percentile(v,p):
        if not v: return 0
        s=sorted(v); return s[min(len(s)-1, int((len(s)-1)*p))]
    dupF = [c for c in countsF.values() if c>1]
    dupS = [c for c in countsS.values() if c>1]
    return {
        "policy": policy,
        "points": total_pairs,
        "rows_used": rows_used,
        "front_iou": round(iou(projF, targetF), 6),
        "side_iou": round(iou(projS, targetS), 6),
        "front_coverage": round(len(projF)/max(1,len(targetF)), 6),
        "side_coverage": round(len(projS)/max(1,len(targetS)), 6),
        "duplicate_front_pixels": len(dupF),
        "duplicate_side_pixels": len(dupS),
        "duplicate_front_max": max(dupF) if dupF else 1,
        "duplicate_side_max": max(dupS) if dupS else 1,
        "row_count_mean": round(mean(row_counts), 3),
        "row_count_p95": percentile(row_counts, .95),
        "pair_color_conflict_mean": round(mean(conflicts), 6),
        "pair_color_conflict_p95": round(percentile(conflicts,.95), 6),
        "fixed_blend_front_rmse_proxy": round(mean(blend_f_err), 6),
        "fixed_blend_side_rmse_proxy": round(mean(blend_s_err), 6),
        "z_continuity_jump_mean": round(mean(continuity_jumps), 3),
        "z_continuity_jump_p95": percentile(continuity_jumps, .95),
    }


def main():
    pairs = [
        ("goose", ROOT/"artifacts/reference-image/goose.png", "nubzuki", ROOT/"artifacts/reference-image/nubzuki.png"),
        ("goose", ROOT/"artifacts/reference-image/goose.png", "cake", ROOT/"artifacts/reference-image/cake.png"),
    ]
    results = []
    for fname, fpath, sname, spath in pairs:
        fr = load_rows(fpath); sr = load_rows(spath)
        policies = ["min_quantile", "current_modulo", "quantile_max", "color_aware_local"]
        results.append({
            "front": fname,
            "side": sname,
            "width": W,
            "rows": ROW_COUNT,
            "front_active_pixels": sum(len(v) for v in fr.values()),
            "side_active_pixels": sum(len(v) for v in sr.values()),
            "policies": [policy_metrics(fr, sr, p) for p in policies]
        })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"note":"real image proxy; alpha mask resized/normalized, not production renderer", "results":results}, indent=2), encoding="utf-8")
    print(OUT)

if __name__ == "__main__":
    main()
