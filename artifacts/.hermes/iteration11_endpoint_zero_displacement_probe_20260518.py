from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import mean, median

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "algorithm-exploration" / "iteration-11-endpoint-zero-displacement-probe-20260518.json"
IMG = ROOT / "artifacts" / "reference-image" / "goose.png"
W, H = 160, 120


def load_mask(path: Path) -> set[tuple[int, int]]:
    img = Image.open(path).convert("RGBA").resize((W, H), Image.Resampling.LANCZOS)
    pix = img.load()
    pts: set[tuple[int, int]] = set()
    for y in range(H):
        for x in range(W):
            r, g, b, a = pix[x, y]
            # Treat alpha as primary; fall back to non-white/non-dark content if alpha is opaque.
            if a > 32 and (a < 250 or (r, g, b) != (255, 255, 255)):
                # Ignore nearly transparent/white antialias background.
                if a > 80 and not (r > 245 and g > 245 and b > 245):
                    pts.add((x, y))
    if not pts:
        raise RuntimeError(f"empty mask from {path}")
    return pts


def shift_region(base: set[tuple[int, int]], region: set[tuple[int, int]], dx: int, dy: int) -> set[tuple[int, int]]:
    fixed = base - region
    moved = set()
    for x, y in region:
        nx, ny = x + dx, y + dy
        if 0 <= nx < W and 0 <= ny < H:
            moved.add((nx, ny))
    return fixed | moved


def nearest_stats(a: set[tuple[int, int]], b: set[tuple[int, int]]) -> dict:
    if not a:
        return {"count": 0, "mean": 0.0, "median": 0.0, "p95": 0.0, "max": 0.0}
    bl = list(b)
    ds = []
    for ax, ay in a:
        best2 = min((ax - bx) ** 2 + (ay - by) ** 2 for bx, by in bl)
        ds.append(math.sqrt(best2))
    ds.sort()
    p95 = ds[min(len(ds) - 1, int(round(0.95 * (len(ds) - 1))))]
    return {"count": len(ds), "mean": round(mean(ds), 4), "median": round(median(ds), 4), "p95": round(p95, 4), "max": round(ds[-1], 4)}


def sym_metrics(base: set[tuple[int, int]], target: set[tuple[int, int]]) -> dict:
    create = target - base
    erase = base - target
    inter = len(base & target)
    union = len(base | target)
    return {
        "target_pixels": len(target),
        "create_pixels": len(create),
        "erase_pixels": len(erase),
        "create_ratio_vs_target": round(len(create) / max(1, len(target)), 6),
        "erase_ratio_vs_base": round(len(erase) / max(1, len(base)), 6),
        "symdiff_ratio_vs_union": round((len(create) + len(erase)) / max(1, union), 6),
        "iou": round(inter / max(1, union), 6),
        "create_nearest_base": nearest_stats(create, base),
        "erase_nearest_target": nearest_stats(erase, target),
    }


def endpoint_zero_basis_stats(dx: int, dy: int, step_deg: int = 5) -> dict:
    # b(theta)=sin(2theta), theta in [0,90]. b(0)=b(90)=0, b(45)=1.
    amp = math.sqrt(dx * dx + dy * dy)
    vals = []
    prev = None
    jumps = []
    for deg in range(0, 91, step_deg):
        b = math.sin(math.radians(2 * deg))
        disp = amp * b
        vals.append((deg, disp))
        if prev is not None:
            jumps.append(abs(disp - prev))
        prev = disp
    return {
        "basis": "sin(2theta), endpoint-zero, max at 45deg",
        "requested_mid_displacement_px": round(amp, 4),
        "canonical_front_displacement_px": 0.0,
        "canonical_right_displacement_px": 0.0,
        "max_5deg_displacement_jump_px": round(max(jumps), 4),
        "mean_5deg_displacement_jump_px": round(mean(jumps), 4),
        "midpoint_velocity_px_per_degree_approx": round(amp * 2 * math.pi / 180, 4),
        "sample_displacements": [{"deg": d, "disp_px": round(v, 4)} for d, v in vals],
    }


def classify_constructive(region_ratio: float, m: dict, basis: dict) -> str:
    p95 = max(m["create_nearest_base"]["p95"], m["erase_nearest_target"]["p95"])
    changed = m["symdiff_ratio_vs_union"]
    jump = basis["max_5deg_displacement_jump_px"]
    if m["create_ratio_vs_target"] <= 0.01 and m["erase_ratio_vs_base"] <= 0.01:
        return "color_only_feasible"
    if p95 <= 2.0 and changed <= 0.15 and region_ratio <= 0.30 and jump <= 0.4:
        return "endpoint_zero_micro_displacement_strong_candidate"
    if p95 <= 4.0 and changed <= 0.30 and region_ratio <= 0.35 and jump <= 0.8:
        return "endpoint_zero_micro_displacement_borderline_research_only"
    return "geometry_needed_or_defer"


def main() -> None:
    base = load_mask(IMG)
    xs = sorted(x for x, _ in base)
    q75 = xs[int(0.75 * (len(xs) - 1))]
    right_tail = {(x, y) for x, y in base if x >= q75}
    cases = []
    for name, dx, dy in [
        ("right_tail_right_1px", 1, 0),
        ("right_tail_right_2px", 2, 0),
        ("right_tail_right_4px", 4, 0),
        ("right_tail_down_2px", 0, 2),
        ("right_tail_down_4px", 0, 4),
        ("right_tail_diag_2_2px", 2, 2),
        ("right_tail_diag_4_2px", 4, 2),
    ]:
        target = shift_region(base, right_tail, dx, dy)
        metrics = sym_metrics(base, target)
        basis = endpoint_zero_basis_stats(dx, dy)
        region_ratio = len(right_tail) / len(base)
        cases.append({
            "case": name,
            "dx": dx,
            "dy": dy,
            "moved_region_pixels": len(right_tail),
            "moved_region_ratio_vs_base": round(region_ratio, 6),
            "support_metrics": metrics,
            "endpoint_zero_basis": basis,
            "classification": classify_constructive(region_ratio, metrics, basis),
        })
    result = {
        "probe": "iteration11_endpoint_zero_displacement",
        "source_image": str(IMG.relative_to(ROOT)),
        "proxy_resolution": [W, H],
        "base_pixels": len(base),
        "right_tail_quantile_x_min": q75,
        "right_tail_pixels": len(right_tail),
        "right_tail_ratio_vs_base": round(len(right_tail) / len(base), 6),
        "interpretation_note": "This is a constructive endpoint-zero morph triage: color-only support test + localized support change + sin(2theta) canonical-zero displacement smoothness. It is not a renderer pass and does not permit opacity gating or projection-only points.",
        "cases": cases,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
