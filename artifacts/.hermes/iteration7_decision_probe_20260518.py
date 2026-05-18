#!/usr/bin/env python3
"""Iteration 7 throwaway decision probe.

No production files are modified. This script reuses the production-like PIL extraction
from prior iterations and adds a decision-grade scoring layer:
- row materialization acceptance deltas for current vs quantile
- fixed-blend endpoint error baseline
- directional color actual-pair pop metrics for goose+nubzuki and goose+cake
- pass/fail against provisional gates from iteration 6
"""
from __future__ import annotations
from pathlib import Path
from PIL import Image
import json, math, random

ROOT = Path(__file__).resolve().parents[2]
OUT_JSON = ROOT / "artifacts/algorithm-exploration/iteration-7-decision-probe-20260518.json"

MASK_WIDTH = 960
MASK_HEIGHT = 280
ROW_COUNT = 190
SAMPLE_STRIDE = 1
ALPHA_THRESHOLD = 64
MARGIN = 28
RNG_SEED = 4792026

ROW_GATES = {
    "min_front_iou_delta_vs_current": -0.005,
    "min_side_iou_delta_vs_current": -0.005,
    "max_direction_flip_ratio_mean": 0.01,
    "max_z_jump_gt25_ratio": 0.01,
}
DIR_GATES = {
    "endpoint_rmse_fraction_of_fixed_blend": 0.25,
    "max_5deg_step_rmse_mean": 0.04,
    "max_5deg_step_pair_p99": 0.10,
    "max_accel_rmse_mean": 0.01,
    "max_wrong_lobe_endpoint": 0.06,
}


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def pct(xs, p):
    if not xs:
        return 0.0
    s = sorted(xs)
    return s[min(len(s) - 1, int((len(s) - 1) * p))]


def rgb_dist(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)) / 3)


def load_canvas(path: Path):
    im = Image.open(path).convert("RGBA")
    sw, sh = im.size
    scale = min((MASK_WIDTH - MARGIN * 2) / sw, (MASK_HEIGHT - MARGIN * 2) / sh)
    nw, nh = max(1, round(sw * scale)), max(1, round(sh * scale))
    resized = im.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (MASK_WIDTH, MASK_HEIGHT), (0, 0, 0, 0))
    canvas.alpha_composite(resized, ((MASK_WIDTH - nw) // 2, (MASK_HEIGHT - nh) // 2))
    return canvas


def extract_rows(path: Path):
    canvas = load_canvas(path)
    pix = canvas.load()
    active = []
    min_y = MASK_HEIGHT - 1
    max_y = 0
    for py in range(0, MASK_HEIGHT, SAMPLE_STRIDE):
        for px in range(0, MASK_WIDTH, SAMPLE_STRIDE):
            r, g, b, a = pix[px, py]
            if a < ALPHA_THRESHOLD:
                continue
            min_y = min(min_y, py)
            max_y = max(max_y, py)
            active.append((px, py, (r / 255.0, g / 255.0, b / 255.0)))
    rows = [[] for _ in range(ROW_COUNT)]
    if not active:
        return rows
    active_height = max(1, max_y - min_y)
    for px, py, color in active:
        row = clamp(math.floor(((py - min_y) / active_height) * (ROW_COUNT - 1)), 0, ROW_COUNT - 1)
        rows[row].append({"px": px, "color": color})
    return rows


def seeded_shuffle(items, rng):
    arr = list(items)
    for i in range(len(arr) - 1, 0, -1):
        j = int(rng.random() * (i + 1))
        arr[i], arr[j] = arr[j], arr[i]
    return arr


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
        return [(xs2[min(len(xs2) - 1, int((i + 0.5) * len(xs2) / n))],
                 zs2[min(len(zs2) - 1, int((i + 0.5) * len(zs2) / n))]) for i in range(n)]
    raise ValueError(policy)


def all_pairs(front_rows, side_rows, policy):
    rng = random.Random(RNG_SEED)
    out = []
    per_row = {}
    for y in range(ROW_COUNT):
        pairs = materialize(front_rows[y], side_rows[y], policy, rng)
        if pairs:
            per_row[y] = pairs
            for fs, ss in pairs:
                out.append((y, fs, ss))
    return out, per_row


def row_pairing_metrics(front_rows, side_rows, policy):
    pairs, per_row = all_pairs(front_rows, side_rows, policy)
    target_f = {(s["px"], y) for y, row in enumerate(front_rows) for s in row}
    target_s = {(s["px"], y) for y, row in enumerate(side_rows) for s in row}
    proj_f = {(fs["px"], y) for y, fs, ss in pairs}
    proj_s = {(ss["px"], y) for y, fs, ss in pairs}
    jumps = []
    big_jump_25 = []
    big_jump_50 = []
    direction_flips = []
    conflicts = []
    fixed_endpoint_errs = []
    for y, row_pairs in per_row.items():
        zseq = [ss["px"] for fs, ss in row_pairs]
        if len(zseq) > 1:
            local = [abs(zseq[i] - zseq[i-1]) for i in range(1, len(zseq))]
            jumps.extend(local)
            big_jump_25.extend([1 if j > 25 else 0 for j in local])
            big_jump_50.extend([1 if j > 50 else 0 for j in local])
            signs = []
            for i in range(1, len(zseq)):
                d = zseq[i] - zseq[i-1]
                if d != 0:
                    signs.append(1 if d > 0 else -1)
            flips = sum(1 for i in range(1, len(signs)) if signs[i] != signs[i-1])
            direction_flips.append(flips / max(1, len(signs)-1))
        for fs, ss in row_pairs:
            conflict = rgb_dist(fs["color"], ss["color"])
            conflicts.append(conflict)
            # Any 50/50 fixed blend has equal endpoint error = 0.5 * color distance.
            fixed_endpoint_errs.append(0.5 * conflict)
    def iou(a, b):
        return len(a & b) / max(1, len(a | b))
    return {
        "policy": policy,
        "points": len(pairs),
        "front_iou": round(iou(proj_f, target_f), 6),
        "side_iou": round(iou(proj_s, target_s), 6),
        "z_jump_mean": round(mean(jumps), 6),
        "z_jump_p95": round(pct(jumps, 0.95), 6),
        "z_jump_gt25_ratio": round(mean(big_jump_25), 6),
        "z_jump_gt50_ratio": round(mean(big_jump_50), 6),
        "direction_flip_ratio_mean": round(mean(direction_flips), 6),
        "pair_color_conflict_mean": round(mean(conflicts), 6),
        "pair_color_conflict_p95": round(pct(conflicts, .95), 6),
        "fixed_blend_endpoint_rmse_mean": round(mean(fixed_endpoint_errs), 6),
    }


def lobe_weight(theta_deg, basis):
    th = math.radians(theta_deg)
    cf, cr = max(0.0, math.cos(th)), max(0.0, math.sin(th))
    if basis == "cosine_s1":
        f, r = cf, cr
    elif basis == "cosine_s2":
        f, r = cf ** 2, cr ** 2
    elif basis == "cosine_s8":
        f, r = cf ** 8, cr ** 8
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


def directional_metrics(front_rows, side_rows, policy="quantile_max"):
    pairs, _ = all_pairs(front_rows, side_rows, policy)
    bases = ["cosine_s1", "cosine_s2", "cosine_s8", "softmax_tau035", "gaussian_sigma05"]
    angles = list(range(0, 91, 5))
    fixed_blend = mean([0.5 * rgb_dist(fs["color"], ss["color"]) for _, fs, ss in pairs])
    out = {}
    for basis in bases:
        per_angle_colors = []
        endpoint_front = []
        endpoint_side = []
        linear_errs = []
        for theta in angles:
            wf, wr = lobe_weight(theta, basis)
            cols = [tuple(wf * fs["color"][k] + wr * ss["color"][k] for k in range(3)) for _, fs, ss in pairs]
            per_angle_colors.append(cols)
            linear_wr = theta / 90.0
            linear_wf = 1.0 - linear_wr
            linear_cols = [tuple(linear_wf * fs["color"][k] + linear_wr * ss["color"][k] for k in range(3)) for _, fs, ss in pairs]
            linear_errs.extend(rgb_dist(a, b) for a, b in zip(cols, linear_cols))
            if theta == 0:
                endpoint_front.extend(rgb_dist(c, fs["color"]) for c, (_, fs, ss) in zip(cols, pairs))
            if theta == 90:
                endpoint_side.extend(rgb_dist(c, ss["color"]) for c, (_, fs, ss) in zip(cols, pairs))
        steps = []
        p99_steps = []
        for ai in range(1, len(angles)):
            ds = [rgb_dist(per_angle_colors[ai][i], per_angle_colors[ai-1][i]) for i in range(len(pairs))]
            steps.append(mean(ds))
            p99_steps.append(pct(ds, .99))
        accels = []
        for ai in range(1, len(angles)-1):
            vals = []
            for i in range(len(pairs)):
                a = per_angle_colors[ai-1][i]
                b = per_angle_colors[ai][i]
                c = per_angle_colors[ai+1][i]
                vals.append(math.sqrt(sum((c[k] - 2*b[k] + a[k])**2 for k in range(3)) / 3))
            accels.append(mean(vals))
        endpoint = (mean(endpoint_front) + mean(endpoint_side)) / 2
        wrong = max(lobe_weight(0, basis)[1], lobe_weight(90, basis)[0])
        metrics = {
            "endpoint_rmse_mean": round(endpoint, 6),
            "endpoint_fraction_of_fixed_blend": round(endpoint / max(1e-12, fixed_blend), 6),
            "linear_path_rmse_mean": round(mean(linear_errs), 6),
            "max_5deg_step_rmse_mean": round(max(steps) if steps else 0, 6),
            "max_5deg_step_pair_p99": round(max(p99_steps) if p99_steps else 0, 6),
            "max_accel_rmse_mean": round(max(accels) if accels else 0, 6),
            "max_wrong_lobe_endpoint": round(wrong, 6),
        }
        metrics["passes_provisional_gate"] = (
            metrics["endpoint_fraction_of_fixed_blend"] <= DIR_GATES["endpoint_rmse_fraction_of_fixed_blend"] and
            metrics["max_5deg_step_rmse_mean"] <= DIR_GATES["max_5deg_step_rmse_mean"] and
            metrics["max_5deg_step_pair_p99"] <= DIR_GATES["max_5deg_step_pair_p99"] and
            metrics["max_accel_rmse_mean"] <= DIR_GATES["max_accel_rmse_mean"] and
            metrics["max_wrong_lobe_endpoint"] <= DIR_GATES["max_wrong_lobe_endpoint"]
        )
        out[basis] = metrics
    return {"fixed_blend_endpoint_rmse_mean": round(fixed_blend, 6), "basis_metrics": out}


def row_decision(current, quantile):
    deltas = {
        "front_iou_delta": round(quantile["front_iou"] - current["front_iou"], 6),
        "side_iou_delta": round(quantile["side_iou"] - current["side_iou"], 6),
        "z_jump_gt25_delta": round(quantile["z_jump_gt25_ratio"] - current["z_jump_gt25_ratio"], 6),
        "direction_flip_delta": round(quantile["direction_flip_ratio_mean"] - current["direction_flip_ratio_mean"], 6),
        "color_conflict_mean_delta": round(quantile["pair_color_conflict_mean"] - current["pair_color_conflict_mean"], 6),
    }
    passes = (
        deltas["front_iou_delta"] >= ROW_GATES["min_front_iou_delta_vs_current"] and
        deltas["side_iou_delta"] >= ROW_GATES["min_side_iou_delta_vs_current"] and
        quantile["direction_flip_ratio_mean"] <= ROW_GATES["max_direction_flip_ratio_mean"] and
        quantile["z_jump_gt25_ratio"] <= ROW_GATES["max_z_jump_gt25_ratio"]
    )
    return {"deltas_quantile_minus_current": deltas, "quantile_passes_row_gate": passes}


def main():
    refs = {
        "goose": ROOT / "artifacts/reference-image/goose.png",
        "nubzuki": ROOT / "artifacts/reference-image/nubzuki.png",
        "cake": ROOT / "artifacts/reference-image/cake.png",
    }
    front_rows = extract_rows(refs["goose"])
    data = {
        "note": "throwaway iteration 7 decision probe; production-like PIL extraction; no production files modified",
        "extraction": {"mask_width": MASK_WIDTH, "mask_height": MASK_HEIGHT, "row_count": ROW_COUNT, "alpha_threshold": ALPHA_THRESHOLD, "margin": MARGIN},
        "row_gates": ROW_GATES,
        "directional_gates": DIR_GATES,
        "cases": []
    }
    for side_name in ["nubzuki", "cake"]:
        side_rows = extract_rows(refs[side_name])
        cur = row_pairing_metrics(front_rows, side_rows, "current_shuffled_max_reuse")
        q = row_pairing_metrics(front_rows, side_rows, "quantile_max")
        data["cases"].append({
            "front": "goose",
            "side": side_name,
            "row_pairing": [cur, q],
            "row_decision": row_decision(cur, q),
            "directional_color_on_quantile_pairs": directional_metrics(front_rows, side_rows, "quantile_max"),
        })
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(OUT_JSON)


if __name__ == "__main__":
    main()
