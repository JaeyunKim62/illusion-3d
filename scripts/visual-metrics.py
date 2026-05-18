#!/usr/bin/env python3
"""Lightweight screenshot metrics for the illusion-3d point-cloud viewer.

The metrics are intentionally heuristic. They are not acceptance gates; they give a
repeatable sanity signal for front/right screenshots while browser vision remains
the perceptual authority.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean, median

from PIL import Image


def luminance(pixel: tuple[int, int, int]) -> float:
    r, g, b = pixel[:3]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def analyze(path: Path, crop: str | None = None) -> dict:
    img = Image.open(path).convert("RGB")
    w, h = img.size
    if crop:
        x0, y0, x1, y1 = [float(v) for v in crop.split(",")]
        if max(x0, y0, x1, y1) <= 1.0:
            box = (int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h))
        else:
            box = (int(x0), int(y0), int(x1), int(y1))
    else:
        # Left rendering area; avoid right text panel and top/bottom overlays.
        box = (0, int(0.08 * h), int(0.66 * w), int(0.88 * h))
    crop_img = img.crop(box)
    cw, ch = crop_img.size
    pix = crop_img.load()

    # Estimate local background from crop corners. The viewer canvas/page uses a
    # light neutral background; points and labels are the outliers.
    corner_samples = []
    corner_windows = [
        (0, 0),
        (max(0, cw - 24), 0),
        (0, max(0, ch - 24)),
        (max(0, cw - 24), max(0, ch - 24)),
    ]
    for sx, sy in corner_windows:
        for yy in range(sy, min(ch, sy + 24)):
            for xx in range(sx, min(cw, sx + 24)):
                corner_samples.append(pix[xx, yy])
    bg = tuple(int(median([p[i] for p in corner_samples])) for i in range(3)) if corner_samples else (238, 238, 238)

    # Foreground is dark/colored point cloud against the pale page/canvas.
    row_counts = []
    row_dark = []
    row_luma_mean = []
    total_fg = 0
    for y in range(ch):
        dark_vals = []
        count = 0
        for x in range(cw):
            lum = luminance(pix[x, y])
            r, g, b = pix[x, y]
            sat = max(r, g, b) - min(r, g, b)
            bg_dist = ((r - bg[0]) ** 2 + (g - bg[1]) ** 2 + (b - bg[2]) ** 2) ** 0.5
            # Include colored/dark points; reject the estimated light background.
            if bg_dist > 28 and (lum < 248 or sat > 30):
                count += 1
                dark_vals.append(255 - lum)
        row_counts.append(count)
        total_fg += count
        row_dark.append(mean(dark_vals) if dark_vals else 0.0)
        row_luma_mean.append(mean(dark_vals) if dark_vals else 0.0)

    active_rows = [c for c in row_counts if c > max(8, cw * 0.005)]
    if active_rows:
        med_count = median(active_rows)
        row_cv = (sum((c - mean(active_rows)) ** 2 for c in active_rows) / len(active_rows)) ** 0.5 / max(1, mean(active_rows))
        gap_ratio = sum(1 for c in row_counts if c < med_count * 0.18) / len(row_counts)
    else:
        med_count = 0
        row_cv = 0
        gap_ratio = 1

    # Alternating-row energy: high values usually mean scanline/banding.
    if len(row_dark) > 2:
        alt_energy = mean(abs(row_dark[i] - row_dark[i - 1]) for i in range(1, len(row_dark)))
        smooth_energy = mean(abs(row_dark[i] - row_dark[i - 2]) for i in range(2, len(row_dark)))
        banding_index = alt_energy / max(1e-6, smooth_energy)
    else:
        alt_energy = smooth_energy = banding_index = 0

    # Edge continuity proxy: among active rows, how many have nontrivial coverage.
    active_row_ratio = len(active_rows) / max(1, len(row_counts))
    fill_ratio = total_fg / max(1, cw * ch)

    return {
        "path": str(path),
        "imageSize": {"width": w, "height": h},
        "cropBox": box,
        "estimatedBackgroundRgb": bg,
        "foregroundFillRatio": round(fill_ratio, 4),
        "activeRowRatio": round(active_row_ratio, 4),
        "rowForegroundMedian": round(med_count, 2),
        "rowCountCv": round(row_cv, 4),
        "rowGapRatio": round(gap_ratio, 4),
        "adjacentRowEnergy": round(alt_energy, 4),
        "twoRowEnergy": round(smooth_energy, 4),
        "bandingIndex": round(banding_index, 4),
        "interpretation": {
            "lowerRowGapRatio": "usually more solid projection",
            "lowerBandingIndex": "usually less alternating scanline energy; compare only similar screenshots",
            "browserVisionStillRequired": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("images", nargs="+", help="PNG/JPG screenshots to analyze")
    parser.add_argument("--crop", help="x0,y0,x1,y1 absolute pixels or 0..1 fractions")
    parser.add_argument("--out", help="write JSON report")
    args = parser.parse_args()

    report = {"metricsVersion": 1, "images": [analyze(Path(p), args.crop) for p in args.images]}
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
