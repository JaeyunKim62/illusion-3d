"""Generate identity-first tri-view targets for SDF rendering.

Unlike the earlier candidate search, these images are designed as projections of
one sculptural object. The goal is immediate recognition before optimization.
"""

import os
from PIL import Image, ImageDraw, ImageFont


SIZE = 256
OUT_DIR = "img_identity"
PREVIEW_DIR = "candidate_previews"
INK = (18, 18, 18, 255)
PAPER = (255, 255, 255, 0)
WHITE = (255, 255, 255, 255)


def save(name, draw_fn):
    os.makedirs(OUT_DIR, exist_ok=True)
    img = Image.new("RGBA", (SIZE, SIZE), PAPER)
    draw = ImageDraw.Draw(img)
    draw_fn(draw)
    img.save(os.path.join(OUT_DIR, name))


def ellipse(draw, box, fill=INK):
    draw.ellipse(box, fill=fill)


def rect(draw, box, radius=8, fill=INK):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def polygon(draw, pts, fill=INK):
    draw.polygon(pts, fill=fill)


def line(draw, pts, width=12, fill=INK):
    draw.line(pts, fill=fill, width=width, joint="curve")


def cut_ellipse(draw, box):
    draw.ellipse(box, fill=WHITE)


def cut_rect(draw, box, radius=6):
    draw.rounded_rectangle(box, radius=radius, fill=WHITE)


def robot_front(draw):
    rect(draw, (58, 56, 198, 188), radius=24)
    rect(draw, (84, 34, 172, 66), radius=10)
    line(draw, [(128, 34), (128, 16)], width=9)
    ellipse(draw, (116, 6, 140, 30))
    rect(draw, (34, 92, 62, 148), radius=12)
    rect(draw, (194, 92, 222, 148), radius=12)
    cut_rect(draw, (82, 88, 116, 122), radius=8)
    cut_rect(draw, (140, 88, 174, 122), radius=8)
    rect(draw, (88, 148, 168, 164), radius=4, fill=WHITE)
    rect(draw, (74, 188, 182, 224), radius=10)


def robot_side(draw):
    rect(draw, (72, 58, 178, 188), radius=22)
    polygon(draw, [(176, 94), (222, 116), (176, 138)])
    rect(draw, (98, 34, 166, 66), radius=10)
    line(draw, [(132, 34), (132, 16)], width=9)
    ellipse(draw, (120, 6, 144, 30))
    cut_rect(draw, (132, 88, 164, 122), radius=8)
    rect(draw, (108, 148, 176, 164), radius=4, fill=WHITE)
    rect(draw, (88, 188, 172, 224), radius=10)


def robot_top(draw):
    rect(draw, (58, 58, 198, 198), radius=28)
    rect(draw, (102, 20, 154, 66), radius=12)
    rect(draw, (22, 104, 66, 152), radius=14)
    rect(draw, (190, 104, 234, 152), radius=14)
    polygon(draw, [(198, 108), (238, 128), (198, 148)])
    cut_rect(draw, (86, 92, 116, 122), radius=8)
    cut_rect(draw, (140, 92, 170, 122), radius=8)
    rect(draw, (94, 154, 162, 170), radius=4, fill=WHITE)


def trophy_front(draw):
    polygon(draw, [(82, 42), (174, 42), (160, 132), (96, 132)])
    ellipse(draw, (72, 28, 184, 88))
    line(draw, [(82, 76), (34, 104), (54, 146), (94, 116)], width=16)
    line(draw, [(174, 76), (222, 104), (202, 146), (162, 116)], width=16)
    rect(draw, (112, 130, 144, 188), radius=8)
    rect(draw, (78, 186, 178, 214), radius=10)
    rect(draw, (58, 212, 198, 234), radius=8)
    cut_ellipse(draw, (102, 64, 122, 84))
    cut_ellipse(draw, (134, 64, 154, 84))
    rect(draw, (104, 104, 152, 116), radius=4, fill=WHITE)


def trophy_side(draw):
    polygon(draw, [(96, 42), (164, 42), (152, 132), (108, 132)])
    ellipse(draw, (88, 28, 176, 86))
    line(draw, [(160, 78), (220, 108), (196, 148), (154, 116)], width=16)
    rect(draw, (116, 130, 146, 188), radius=8)
    rect(draw, (82, 186, 178, 214), radius=10)
    rect(draw, (60, 212, 196, 234), radius=8)
    cut_ellipse(draw, (128, 64, 150, 86))
    rect(draw, (116, 104, 158, 116), radius=4, fill=WHITE)


def trophy_top(draw):
    ellipse(draw, (58, 58, 198, 178))
    cut_ellipse(draw, (92, 84, 164, 150))
    rect(draw, (44, 108, 82, 144), radius=12)
    rect(draw, (174, 108, 212, 144), radius=12)
    rect(draw, (98, 174, 158, 218), radius=12)
    rect(draw, (76, 214, 180, 236), radius=8)
    cut_ellipse(draw, (104, 104, 122, 122))
    cut_ellipse(draw, (134, 104, 152, 122))


def sign_front(draw):
    rect(draw, (46, 44, 210, 154), radius=18)
    polygon(draw, [(76, 154), (180, 154), (160, 216), (96, 216)])
    rect(draw, (70, 212, 186, 234), radius=8)
    cut_rect(draw, (74, 72, 114, 110), radius=10)
    cut_rect(draw, (142, 72, 182, 110), radius=10)
    line(draw, [(94, 132), (128, 142), (162, 132)], width=10, fill=WHITE)


def sign_side(draw):
    rect(draw, (78, 48, 174, 158), radius=18)
    polygon(draw, [(174, 78), (226, 102), (174, 128)])
    polygon(draw, [(96, 158), (164, 158), (152, 216), (108, 216)])
    rect(draw, (78, 212, 182, 234), radius=8)
    cut_rect(draw, (126, 76, 160, 110), radius=10)
    line(draw, [(118, 134), (168, 132)], width=9, fill=WHITE)


def sign_top(draw):
    rect(draw, (52, 58, 204, 184), radius=22)
    polygon(draw, [(204, 98), (238, 122), (204, 146)])
    rect(draw, (94, 184, 162, 228), radius=12)
    cut_rect(draw, (78, 86, 116, 122), radius=10)
    cut_rect(draw, (140, 86, 178, 122), radius=10)
    line(draw, [(92, 152), (128, 164), (164, 152)], width=9, fill=WHITE)


SETS = [
    ("identity_robot", robot_front, robot_side, robot_top),
    ("identity_trophy", trophy_front, trophy_side, trophy_top),
    ("identity_sign", sign_front, sign_side, sign_top),
]


def load_font(size):
    for name in ("arial.ttf", "Arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def make_preview():
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    tile = 160
    pad = 18
    label_h = 38
    width = pad * 4 + tile * 3
    height = pad + len(SETS) * (tile + label_h + pad)
    sheet = Image.new("RGB", (width, height), (248, 248, 246))
    draw = ImageDraw.Draw(sheet)
    font = load_font(15)
    for row, (prefix, *_fns) in enumerate(SETS):
        y = pad + row * (tile + label_h + pad)
        for col, view in enumerate(("front", "side", "top")):
            x = pad + col * (tile + pad)
            path = os.path.join(OUT_DIR, f"{prefix}_{view}.png")
            img = Image.open(path).convert("RGBA").resize((tile, tile), Image.LANCZOS)
            panel = Image.new("RGBA", (tile, tile), (255, 255, 255, 255))
            panel.alpha_composite(img)
            sheet.paste(panel.convert("RGB"), (x, y))
            draw.rectangle((x, y, x + tile - 1, y + tile - 1), outline=(180, 180, 180), width=1)
            draw.text((x, y + tile + 6), f"{prefix} {view}", fill=(24, 24, 24), font=font)
    sheet.save(os.path.join(PREVIEW_DIR, "identity-targets-20260601.png"), quality=95)


def main():
    for prefix, front, side, top in SETS:
        save(f"{prefix}_front.png", front)
        save(f"{prefix}_side.png", side)
        save(f"{prefix}_top.png", top)
    make_preview()
    print(f"wrote identity targets to {OUT_DIR}/")
    print(f"wrote {PREVIEW_DIR}/identity-targets-20260601.png")


if __name__ == "__main__":
    main()
