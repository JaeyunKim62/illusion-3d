#!/usr/bin/env python3
"""Iteration 6 throwaway probe.

Adds visual/contact-sheet evidence and actual paired-color directional pop metrics.
Writes only under artifacts/algorithm-exploration. Production files are not touched.
"""
from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageDraw
from collections import Counter
import json, math, random

ROOT = Path(__file__).resolve().parents[2]
OUT_JSON = ROOT / "artifacts/algorithm-exploration/iteration-6-visual-directional-probe-20260518.json"
OUT_CONTACT = ROOT / "artifacts/algorithm-exploration/iteration-6-row-pairing-contact-sheet-20260518.png"
OUT_COLOR = ROOT / "artifacts/algorithm-exploration/iteration-6-directional-color-contact-sheet-20260518.png"

MASK_WIDTH = 960
MASK_HEIGHT = 280
ROW_COUNT = 190
SAMPLE_STRIDE = 1
ALPHA_THRESHOLD = 64
MARGIN = 28
RNG_SEED = 4792026


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


def color_to_rgb(c):
    return tuple(int(clamp(round(x * 255), 0, 255)) for x in c)


def load_canvas(path: Path, width=MASK_WIDTH, height=MASK_HEIGHT, margin=MARGIN):
    im = Image.open(path).convert("RGBA")
    sw, sh = im.size
    scale = min((width - margin * 2) / sw, (height - margin * 2) / sh)
    nw, nh = max(1, round(sw * scale)), max(1, round(sh * scale))
    resized = im.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    canvas.alpha_composite(resized, ((width - nw) // 2, (height - nh) // 2))
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
    normalized_tvs = []
    big_jump_25 = []
    big_jump_50 = []
    direction_flips = []
    conflicts = []
    for y, row_pairs in per_row.items():
        zseq = [ss["px"] for fs, ss in row_pairs]
        xseq = [fs["px"] for fs, ss in row_pairs]
        if len(zseq) > 1:
            local = [abs(zseq[i] - zseq[i-1]) for i in range(1, len(zseq))]
            jumps.extend(local)
            zrange = max(1, max(zseq) - min(zseq))
            normalized_tvs.append(sum(local) / max(1, zrange * (len(zseq)-1)))
            big_jump_25.extend([1 if j > 25 else 0 for j in local])
            big_jump_50.extend([1 if j > 50 else 0 for j in local])
            # Count sign changes in side sequence derivative as row-order chaos proxy.
            signs = []
            for i in range(1, len(zseq)):
                d = zseq[i] - zseq[i-1]
                if d != 0:
                    signs.append(1 if d > 0 else -1)
            flips = sum(1 for i in range(1, len(signs)) if signs[i] != signs[i-1])
            direction_flips.append(flips / max(1, len(signs)-1))
        for fs, ss in row_pairs:
            conflicts.append(rgb_dist(fs["color"], ss["color"]))
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
        "normalized_total_variation_mean": round(mean(normalized_tvs), 6),
        "direction_flip_ratio_mean": round(mean(direction_flips), 6),
        "pair_color_conflict_mean": round(mean(conflicts), 6),
        "pair_color_conflict_p95": round(pct(conflicts, .95), 6),
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


def mix_color(cf, cs, w):
    return tuple(w * cf[k] + (1 - w) * cs[k] for k in range(3))


def directional_metrics(front_rows, side_rows, policy="quantile_max"):
    pairs, _ = all_pairs(front_rows, side_rows, policy)
    # Use all pairs for metrics; contact sheet samples the high-conflict tail.
    bases = ["cosine_s1", "cosine_s2", "cosine_s8", "softmax_tau035", "gaussian_sigma05"]
    angles = list(range(0, 91, 5))
    out = {}
    for basis in bases:
        per_angle_colors = []
        linear_errs = []
        endpoint_front = []
        endpoint_side = []
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
        max_pair_steps = []
        for ai in range(1, len(angles)):
            ds = [rgb_dist(per_angle_colors[ai][i], per_angle_colors[ai-1][i]) for i in range(len(pairs))]
            steps.append(mean(ds))
            max_pair_steps.append(pct(ds, .99))
        accels = []
        for ai in range(1, len(angles)-1):
            vals = []
            for i in range(len(pairs)):
                a = per_angle_colors[ai-1][i]
                b = per_angle_colors[ai][i]
                c = per_angle_colors[ai+1][i]
                vals.append(math.sqrt(sum((c[k] - 2*b[k] + a[k])**2 for k in range(3)) / 3))
            accels.append(mean(vals))
        out[basis] = {
            "endpoint_rmse_mean": round((mean(endpoint_front) + mean(endpoint_side)) / 2, 6),
            "linear_path_rmse_mean": round(mean(linear_errs), 6),
            "max_5deg_step_rmse_mean": round(max(steps) if steps else 0, 6),
            "max_5deg_step_pair_p99": round(max(max_pair_steps) if max_pair_steps else 0, 6),
            "max_accel_rmse_mean": round(max(accels) if accels else 0, 6),
            "front_wrong_lobe_weight": round(lobe_weight(0, basis)[1], 6),
            "right_wrong_lobe_weight": round(lobe_weight(90, basis)[0], 6),
        }
    return out


def draw_row_contact(all_case_rows):
    # all_case_rows: list of (title, current_per_row, quantile_per_row)
    W, H = 1200, 900
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    x0, y0 = 20, 30
    d.text((x0, 5), "Iteration 6 row pairing contact sheet: side-z sequence per row; red=current shuffle, blue=quantile", fill=(0,0,0))
    panel_w = 560
    panel_h = 190
    gap_x = 30
    gap_y = 35
    for ci, (title, cur_rows, q_rows) in enumerate(all_case_rows):
        base_y = y0 + ci * (panel_h * 2 + gap_y)
        for pi, (label, rows, color) in enumerate([("current", cur_rows, (220,40,40)), ("quantile", q_rows, (30,90,220))]):
            px = x0 + pi * (panel_w + gap_x)
            py = base_y
            d.rectangle([px, py, px+panel_w, py+panel_h], outline=(0,0,0))
            d.text((px+4, py+4), f"{title} / {label}", fill=(0,0,0))
            candidate_rows = sorted(rows.keys(), key=lambda y: len(rows[y]), reverse=True)[:4]
            for ri, y in enumerate(candidate_rows):
                pairs = rows[y]
                zseq = [ss["px"] for fs, ss in pairs]
                if len(zseq) < 2:
                    continue
                minz, maxz = min(zseq), max(zseq)
                yr0 = py + 30 + ri * 38
                d.text((px+4, yr0), f"row {y} n={len(zseq)}", fill=(60,60,60))
                pts = []
                for i, z in enumerate(zseq):
                    xx = px + 90 + int(i / max(1, len(zseq)-1) * (panel_w-110))
                    yy = yr0 + 30 - int((z - minz) / max(1, maxz-minz) * 28)
                    pts.append((xx, yy))
                if len(pts) >= 2:
                    d.line(pts, fill=color, width=1)
    OUT_CONTACT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT_CONTACT)


def draw_directional_contact(front_rows, side_rows):
    pairs, _ = all_pairs(front_rows, side_rows, "quantile_max")
    # sample high-conflict pairs to make color transition/popping visible.
    pairs_sorted = sorted(pairs, key=lambda p: rgb_dist(p[1]["color"], p[2]["color"]), reverse=True)[:80]
    bases = ["cosine_s1", "cosine_s2", "cosine_s8", "softmax_tau035", "gaussian_sigma05"]
    angles = list(range(0, 91, 15))
    cell = 8
    left = 160
    top = 30
    W = left + len(pairs_sorted) * cell + 20
    H = top + len(bases) * len(angles) * cell + 60
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((10, 5), "Directional color contact sheet on high-conflict quantile pairs (goose+nubzuki)", fill=(0,0,0))
    y = top
    for basis in bases:
        for theta in angles:
            d.text((8, y), f"{basis} {theta:02d}deg", fill=(0,0,0))
            wf, wr = lobe_weight(theta, basis)
            for i, (_, fs, ss) in enumerate(pairs_sorted):
                c = tuple(wf * fs["color"][k] + wr * ss["color"][k] for k in range(3))
                x = left + i * cell
                d.rectangle([x, y, x+cell-1, y+cell-1], fill=color_to_rgb(c))
            y += cell
        y += 8
    img.save(OUT_COLOR)


def main():
    refs = {
        "goose": ROOT / "artifacts/reference-image/goose.png",
        "nubzuki": ROOT / "artifacts/reference-image/nubzuki.png",
        "cake": ROOT / "artifacts/reference-image/cake.png",
    }
    front_rows = extract_rows(refs["goose"])
    side_rows_map = {name: extract_rows(refs[name]) for name in ["nubzuki", "cake"]}
    cases = []
    contact_rows = []
    for side_name, side_rows in side_rows_map.items():
        metrics = [row_pairing_metrics(front_rows, side_rows, p) for p in ["current_shuffled_max_reuse", "quantile_max"]]
        cur_pairs, cur_per = all_pairs(front_rows, side_rows, "current_shuffled_max_reuse")
        q_pairs, q_per = all_pairs(front_rows, side_rows, "quantile_max")
        cases.append({"front": "goose", "side": side_name, "row_pairing": metrics})
        contact_rows.append((f"goose+{side_name}", cur_per, q_per))
    draw_row_contact(contact_rows)
    dir_metrics = directional_metrics(front_rows, side_rows_map["nubzuki"], "quantile_max")
    draw_directional_contact(front_rows, side_rows_map["nubzuki"])
    data = {
        "note": "throwaway iteration 6; production-like PIL extraction; no production files modified",
        "extraction": {"mask_width": MASK_WIDTH, "mask_height": MASK_HEIGHT, "row_count": ROW_COUNT, "alpha_threshold": ALPHA_THRESHOLD, "margin": MARGIN},
        "row_pairing_visual_metrics": cases,
        "directional_color_actual_pair_pop_metrics": {"front": "goose", "side": "nubzuki", "policy": "quantile_max", "metrics": dir_metrics},
        "contact_sheets": {"row_pairing": str(OUT_CONTACT), "directional_color": str(OUT_COLOR)},
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(OUT_JSON)
    print(OUT_CONTACT)
    print(OUT_COLOR)


if __name__ == "__main__":
    main()
