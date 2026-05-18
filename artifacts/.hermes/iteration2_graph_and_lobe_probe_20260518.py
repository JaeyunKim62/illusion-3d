#!/usr/bin/env python3
"""Iteration 2 throwaway probe: real top-candidate 3-view row graph certificates and directional lobe sweep.
Writes only under artifacts/algorithm-exploration. Does not touch production files.
"""
from __future__ import annotations
from pathlib import Path
from PIL import Image
from collections import defaultdict
import json, math, statistics

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "algorithm-exploration" / "iteration-2-graph-and-lobe-probe-20260518.json"
W = 96   # x/z resolution for graph feasibility
Y = 80   # row resolution
ALPHA_THRESHOLD = 16
LUMA_THRESHOLD = 245  # fallback if image has no alpha cutout


def active_mask(path: Path, width: int, height: int):
    im = Image.open(path).convert("RGBA")
    im.thumbnail((width, height), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    canvas.alpha_composite(im, ((width - im.width) // 2, (height - im.height) // 2))
    pix = canvas.load()
    alpha_any = any(pix[x, y][3] > ALPHA_THRESHOLD for y in range(height) for x in range(width))
    mask = set()
    for y in range(height):
        for x in range(width):
            r, g, b, a = pix[x, y]
            if alpha_any:
                active = a > ALPHA_THRESHOLD
            else:
                # conservative fallback for opaque white-background references
                active = (r + g + b) / 3 < LUMA_THRESHOLD
            if active:
                mask.add((x, y))
    return mask


def normalize_rows(mask, width, height):
    if not mask:
        return defaultdict(set)
    miny = min(y for _, y in mask); maxy = max(y for _, y in mask)
    denom = max(1, maxy - miny + 1)
    rows = defaultdict(set)
    for x, y in mask:
        ny = min(height - 1, max(0, int((y - miny) * height / denom)))
        rows[ny].add(x)
    return rows


def load_xy_rows(path: Path):
    return normalize_rows(active_mask(path, W, Y), W, Y)


def load_xz_mask(path: Path):
    # top image is interpreted as x-z support; normalize active vertical extent into z axis.
    rows = normalize_rows(active_mask(path, W, W), W, W)
    return {(x, z) for z, xs in rows.items() for x in xs}


def pct(values, p):
    if not values:
        return 0
    s = sorted(values)
    return s[min(len(s)-1, int((len(s)-1) * p))]


def iou(a, b):
    return len(a & b) / max(1, len(a | b))


def graph_certificate(front_rows, side_rows, top_mask):
    A = {(x, y) for y, xs in front_rows.items() for x in xs}
    B = {(z, y) for y, zs in side_rows.items() for z in zs}
    C = set(top_mask)
    projA, projB, projC = set(), set(), set()
    row_edge_counts = []
    row_edge_density = []
    front_isolated = 0
    side_isolated = 0
    supported_top = set()
    voxel_count = 0
    for y in range(Y):
        xs = front_rows.get(y, set())
        zs = side_rows.get(y, set())
        if not xs or not zs:
            continue
        deg_x = {x: 0 for x in xs}
        deg_z = {z: 0 for z in zs}
        edge_count = 0
        for x in xs:
            for z in zs:
                if (x, z) in C:
                    edge_count += 1
                    voxel_count += 1
                    deg_x[x] += 1
                    deg_z[z] += 1
                    projA.add((x, y)); projB.add((z, y)); projC.add((x, z)); supported_top.add((x, z))
        row_edge_counts.append(edge_count)
        row_edge_density.append(edge_count / max(1, len(xs) * len(zs)))
        front_isolated += sum(1 for x, d in deg_x.items() if d == 0)
        side_isolated += sum(1 for z, d in deg_z.items() if d == 0)
    missingA = A - projA; missingB = B - projB; missingC = C - projC
    return {
        "resolution": {"x": W, "y": Y, "z": W},
        "front_active": len(A), "side_active": len(B), "top_active": len(C),
        "voxels_in_H": voxel_count,
        "front_iou": round(iou(projA, A), 6),
        "side_iou": round(iou(projB, B), 6),
        "top_iou": round(iou(projC, C), 6),
        "missing_front": len(missingA), "missing_side": len(missingB), "missing_top": len(missingC),
        "extra_front": len(projA - A), "extra_side": len(projB - B), "extra_top": len(projC - C),
        "front_isolated_ratio": round(front_isolated / max(1, len(A)), 6),
        "side_isolated_ratio": round(side_isolated / max(1, len(B)), 6),
        "unsupported_top_ratio": round(len(missingC) / max(1, len(C)), 6),
        "row_edge_count_p50": pct(row_edge_counts, .50),
        "row_edge_count_p95": pct(row_edge_counts, .95),
        "row_edge_count_max": max(row_edge_counts) if row_edge_counts else 0,
        "row_edge_density_mean": round(sum(row_edge_density)/len(row_edge_density), 6) if row_edge_density else 0,
        "row_edge_density_p05": round(pct(row_edge_density, .05), 6),
        "exact_pass_098": (iou(projA, A) >= .98 and iou(projB, B) >= .98 and iou(projC, C) >= .98 and not (projA-A) and not (projB-B) and not (projC-C)),
    }


def lobe_weights(theta_deg, basis, sharpness=4, temperature=0.2):
    th = math.radians(theta_deg)
    cf = max(0.0, math.cos(th))
    cr = max(0.0, math.sin(th))
    if basis == "normalized_cosine_power":
        f = cf ** sharpness; r = cr ** sharpness
    elif basis == "angular_gaussian":
        sigma = max(1e-6, temperature)
        f = math.exp(-0.5 * (th / sigma) ** 2)
        r = math.exp(-0.5 * ((math.pi/2 - th) / sigma) ** 2)
    elif basis == "softmax_cosine":
        # smoother than high-power lobes, but leaks at endpoints depending temperature.
        f = math.exp(cf / max(1e-6, temperature)); r = math.exp(cr / max(1e-6, temperature))
    else:
        raise ValueError(basis)
    s = max(1e-12, f + r)
    return f / s, r / s


def lobe_sweep():
    # Target path is assumed linear blend between endpoint colors. Endpoint leakage and temporal pop are basis-only.
    configs = []
    for basis in ["normalized_cosine_power", "angular_gaussian", "softmax_cosine"]:
        if basis == "normalized_cosine_power":
            params = [{"sharpness": s} for s in [1, 2, 4, 8, 16]]
        elif basis == "angular_gaussian":
            params = [{"temperature": t} for t in [0.25, 0.35, 0.50, 0.75, 1.00]]
        else:
            params = [{"temperature": t} for t in [0.10, 0.15, 0.20, 0.35, 0.50]]
        for param in params:
            weights = []
            errs = []
            jumps = []
            accels = []
            prev = None; prev_jump = None
            for deg in range(0, 91, 5):
                wf, wr = lobe_weights(deg, basis, **param)
                target_right = deg / 90.0
                # worst-case color distance scales with |wr-target| if endpoint colors differ by 1.
                err = abs(wr - target_right)
                weights.append((deg, wf, wr)); errs.append(err)
                if prev is not None:
                    jump = abs(wr - prev)
                    jumps.append(jump)
                    if prev_jump is not None:
                        accels.append(abs(jump - prev_jump))
                    prev_jump = jump
                prev = wr
            configs.append({
                "basis": basis,
                **param,
                "endpoint_wrong_lobe_front": round(weights[0][2], 6),
                "endpoint_wrong_lobe_right": round(weights[-1][1], 6),
                "linear_path_rmse": round(math.sqrt(sum(e*e for e in errs)/len(errs)), 6),
                "max_abs_linear_error": round(max(errs), 6),
                "max_5deg_weight_jump": round(max(jumps), 6),
                "mean_5deg_weight_jump": round(sum(jumps)/len(jumps), 6),
                "max_accel": round(max(accels) if accels else 0, 6),
                "weights_0_30_45_60_90": [[d, round(wf,4), round(wr,4)] for d,wf,wr in weights if d in [0,30,45,60,90]],
            })
    return configs


def main():
    fronts = {"goose": ROOT/"artifacts/reference-image/goose.png"}
    sides = {"nubzuki": ROOT/"artifacts/reference-image/nubzuki.png", "cake": ROOT/"artifacts/reference-image/cake.png"}
    tops = {"phoenix": ROOT/"artifacts/reference-image/phoenix.png", "kumdori": ROOT/"artifacts/reference-image/kumdori.png"}
    front_rows = {k: load_xy_rows(v) for k, v in fronts.items()}
    side_rows = {k: load_xy_rows(v) for k, v in sides.items()}
    top_masks = {k: load_xz_mask(v) for k, v in tops.items()}
    graph = []
    for fn, fr in front_rows.items():
        for sn, sr in side_rows.items():
            for tn, tm in top_masks.items():
                cert = graph_certificate(fr, sr, tm)
                graph.append({"front": fn, "side": sn, "top": tn, **cert})
    data = {
        "note": "research proxy; alpha-mask resized/normalized. 3-view graph uses real reference images but not production renderer.",
        "graph_certificates": graph,
        "directional_lobe_sweep": lobe_sweep(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(OUT)

if __name__ == "__main__":
    main()
