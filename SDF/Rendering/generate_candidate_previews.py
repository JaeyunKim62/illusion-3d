"""Generate contact sheets for selected SDF image triples."""

import os
from PIL import Image, ImageDraw, ImageFont


OUT_DIR = "candidate_previews"
TRIPLES = [
    (
        "legacy-bird-airplane-tower.png",
        [
            ("front", "img/bird.png"),
            ("side", "img/airplane.png"),
            ("top", "img/Tower.png"),
        ],
    ),
    (
        "nub-umbrella-airplane.png",
        [
            ("front", "img_candidates/icon_umbrella.png"),
            ("side", "img/airplane.png"),
            ("top", "img/nub.png"),
        ],
    ),
    (
        "nub-rocket-lighthouse.png",
        [
            ("front", "img_candidates/icon_rocket.png"),
            ("side", "img/nub.png"),
            ("top", "img_candidates/icon_lighthouse.png"),
        ],
    ),
    (
        "nub-orbit-airplane.png",
        [
            ("front", "img_candidates/motif_orbit.png"),
            ("side", "img/airplane.png"),
            ("top", "img/nub.png"),
        ],
    ),
    (
        "nub-cathedral-fountain.png",
        [
            ("front", "img_candidates/motif_cathedral.png"),
            ("side", "img/nub.png"),
            ("top", "img_candidates/motif_fountain.png"),
        ],
    ),
]


def load_font(size):
    for name in ("arial.ttf", "Arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def make_preview(name, entries):
    os.makedirs(OUT_DIR, exist_ok=True)
    tile = 256
    pad = 24
    label_h = 48
    width = tile * 3 + pad * 4
    height = tile + label_h + pad * 2
    sheet = Image.new("RGB", (width, height), (248, 248, 246))
    draw = ImageDraw.Draw(sheet)
    font = load_font(18)
    small = load_font(13)

    for i, (view, path) in enumerate(entries):
        x = pad + i * (tile + pad)
        img = Image.open(path).convert("RGBA").resize((tile, tile), Image.LANCZOS)
        panel = Image.new("RGBA", (tile, tile), (255, 255, 255, 255))
        panel.alpha_composite(img)
        sheet.paste(panel.convert("RGB"), (x, pad))
        draw.rectangle((x, pad, x + tile - 1, pad + tile - 1), outline=(190, 190, 190), width=1)
        draw.text((x, pad + tile + 9), f"{view}: {os.path.basename(path)}", fill=(24, 24, 24), font=font)
        draw.text((x, pad + tile + 31), path, fill=(92, 92, 92), font=small)

    sheet.save(os.path.join(OUT_DIR, name), quality=95)


def main():
    for name, entries in TRIPLES:
        make_preview(name, entries)
        print(f"wrote {os.path.join(OUT_DIR, name)}")


if __name__ == "__main__":
    main()
