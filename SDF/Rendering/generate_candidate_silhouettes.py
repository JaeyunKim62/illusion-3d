"""Generate license-clean silhouette candidates for SDF triple search."""

import os
from PIL import Image, ImageDraw


SIZE = 256
OUT_DIR = "img_candidates"
REMOVED_PREFIXES = ("geom_",)
REMOVED_NAMES = {"motif_compass.png"}


def save(name, draw_fn):
    os.makedirs(OUT_DIR, exist_ok=True)
    img = Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    draw_fn(draw)
    img.save(os.path.join(OUT_DIR, name))


def remove_stale_candidates():
    if not os.path.isdir(OUT_DIR):
        return
    for name in os.listdir(OUT_DIR):
        if name.startswith(REMOVED_PREFIXES) or name in REMOVED_NAMES:
            os.remove(os.path.join(OUT_DIR, name))


def ellipse(draw, box):
    draw.ellipse(box, fill=(20, 20, 20, 255))


def rect(draw, box):
    draw.rounded_rectangle(box, radius=10, fill=(20, 20, 20, 255))


def polygon(draw, pts):
    draw.polygon(pts, fill=(20, 20, 20, 255))


def generate():
    remove_stale_candidates()
    save("obj_tower_simple.png", lambda d: (
        polygon(d, [(128, 26), (158, 220), (98, 220)]),
        rect(d, (82, 92, 174, 112)),
        rect(d, (66, 160, 190, 184)),
    ))
    save("obj_keyhole.png", lambda d: (
        ellipse(d, (78, 34, 178, 134)),
        polygon(d, [(108, 118), (148, 118), (170, 222), (86, 222)]),
    ))
    save("obj_vase.png", lambda d: polygon(d, [
        (92, 36), (164, 36), (154, 86), (184, 136),
        (172, 216), (84, 216), (72, 136), (102, 86),
    ]))
    save("obj_anchor.png", lambda d: (
        rect(d, (116, 54, 140, 198)),
        ellipse(d, (104, 28, 152, 76)),
        rect(d, (72, 112, 184, 136)),
        polygon(d, [(54, 156), (88, 220), (118, 186), (104, 172), (88, 196), (68, 150)]),
        polygon(d, [(202, 156), (168, 220), (138, 186), (152, 172), (168, 196), (188, 150)]),
    ))
    save("obj_leaf.png", lambda d: (
        ellipse(d, (42, 58, 214, 184)),
        polygon(d, [(56, 158), (206, 74), (78, 196)]),
    ))
    save("obj_flame.png", lambda d: polygon(d, [
        (128, 24), (160, 80), (148, 112), (196, 154),
        (164, 224), (92, 224), (60, 154), (104, 108),
    ]))
    save("obj_bell.png", lambda d: (
        ellipse(d, (86, 42, 170, 98)),
        polygon(d, [(78, 82), (178, 82), (210, 198), (46, 198)]),
        ellipse(d, (106, 184, 150, 228)),
    ))
    save("obj_arrow.png", lambda d: polygon(d, [
        (128, 34), (222, 128), (172, 128), (172, 212),
        (84, 212), (84, 128), (34, 128),
    ]))
    save("obj_ribbon.png", lambda d: polygon(d, [
        (70, 38), (186, 38), (186, 218), (128, 176), (70, 218),
    ]))
    save("obj_goblet.png", lambda d: (
        polygon(d, [(62, 42), (194, 42), (174, 134), (82, 134)]),
        rect(d, (116, 132, 140, 198)),
        rect(d, (80, 198, 176, 222)),
    ))
    save("icon_lighthouse.png", lambda d: (
        polygon(d, [(116, 34), (140, 34), (166, 222), (90, 222)]),
        rect(d, (96, 74, 160, 94)),
        rect(d, (84, 218, 172, 232)),
        polygon(d, [(92, 58), (164, 58), (148, 28), (108, 28)]),
        polygon(d, [(86, 60), (36, 36), (86, 84)]),
        polygon(d, [(170, 60), (220, 36), (170, 84)]),
    ))
    save("icon_castle.png", lambda d: (
        rect(d, (54, 92, 202, 222)),
        rect(d, (46, 62, 82, 222)),
        rect(d, (110, 48, 146, 222)),
        rect(d, (174, 62, 210, 222)),
        polygon(d, [(46, 62), (64, 34), (82, 62)]),
        polygon(d, [(110, 48), (128, 20), (146, 48)]),
        polygon(d, [(174, 62), (192, 34), (210, 62)]),
        d.rounded_rectangle((108, 164, 148, 222), radius=18, fill=(255, 255, 255, 0)),
    ))
    save("icon_rocket.png", lambda d: (
        ellipse(d, (92, 24, 164, 112)),
        rect(d, (92, 70, 164, 178)),
        polygon(d, [(92, 134), (50, 198), (102, 180)]),
        polygon(d, [(164, 134), (206, 198), (154, 180)]),
        polygon(d, [(106, 174), (128, 232), (150, 174)]),
        ellipse(d, (112, 76, 144, 108)),
    ))
    save("icon_guitar.png", lambda d: (
        ellipse(d, (52, 118, 138, 218)),
        ellipse(d, (88, 78, 162, 154)),
        rect(d, (142, 36, 164, 130)),
        polygon(d, [(152, 34), (210, 22), (214, 54), (160, 62)]),
        ellipse(d, (96, 126, 124, 154)),
    ))
    save("icon_camera.png", lambda d: (
        rect(d, (46, 82, 210, 190)),
        rect(d, (82, 58, 130, 86)),
        ellipse(d, (90, 92, 166, 168)),
        ellipse(d, (112, 114, 144, 146)),
        rect(d, (166, 58, 198, 84)),
    ))
    save("icon_sailboat.png", lambda d: (
        polygon(d, [(46, 174), (210, 174), (176, 218), (78, 218)]),
        rect(d, (124, 42, 134, 178)),
        polygon(d, [(134, 48), (206, 164), (134, 164)]),
        polygon(d, [(122, 64), (58, 164), (122, 164)]),
    ))
    save("icon_crown.png", lambda d: (
        polygon(d, [(44, 92), (86, 142), (128, 52), (170, 142), (212, 92), (190, 210), (66, 210)]),
        ellipse(d, (34, 80, 58, 104)),
        ellipse(d, (116, 40, 140, 64)),
        ellipse(d, (198, 80, 222, 104)),
    ))
    save("icon_umbrella.png", lambda d: (
        polygon(d, [(28, 132), (64, 76), (128, 48), (192, 76), (228, 132)]),
        ellipse(d, (28, 68, 228, 168)),
        rect(d, (122, 126, 134, 202)),
        d.arc((100, 174, 156, 230), 0, 180, fill=(20, 20, 20, 255), width=14),
    ))
    save("icon_hotair_balloon.png", lambda d: (
        ellipse(d, (58, 28, 198, 162)),
        polygon(d, [(74, 132), (182, 132), (152, 184), (104, 184)]),
        rect(d, (100, 184, 156, 224)),
        rect(d, (88, 172, 106, 196)),
        rect(d, (150, 172, 168, 196)),
    ))
    save("icon_teapot.png", lambda d: (
        ellipse(d, (72, 88, 178, 182)),
        rect(d, (98, 66, 154, 104)),
        ellipse(d, (104, 54, 148, 84)),
        polygon(d, [(172, 110), (224, 88), (184, 132)]),
        d.arc((34, 94, 94, 170), 90, 270, fill=(20, 20, 20, 255), width=18),
        rect(d, (92, 176, 160, 204)),
    ))
    save("icon_key.png", lambda d: (
        ellipse(d, (38, 88, 118, 168)),
        ellipse(d, (62, 112, 94, 144)),
        rect(d, (112, 118, 218, 138)),
        rect(d, (178, 136, 198, 172)),
        rect(d, (204, 136, 224, 158)),
    ))
    save("motif_cathedral.png", lambda d: (
        rect(d, (54, 98, 202, 224)),
        rect(d, (42, 70, 84, 224)),
        rect(d, (108, 52, 148, 224)),
        rect(d, (172, 70, 214, 224)),
        polygon(d, [(42, 70), (64, 28), (84, 70)]),
        polygon(d, [(108, 52), (128, 18), (148, 52)]),
        polygon(d, [(172, 70), (192, 28), (214, 70)]),
        polygon(d, [(84, 98), (128, 70), (172, 98)]),
    ))
    save("motif_pagoda.png", lambda d: (
        rect(d, (78, 102, 178, 222)),
        rect(d, (92, 64, 164, 112)),
        rect(d, (108, 32, 148, 76)),
        polygon(d, [(38, 112), (218, 112), (184, 86), (72, 86)]),
        polygon(d, [(58, 76), (198, 76), (166, 52), (90, 52)]),
        polygon(d, [(86, 42), (170, 42), (148, 22), (108, 22)]),
    ))
    save("motif_starship.png", lambda d: (
        polygon(d, [(128, 28), (166, 116), (226, 150), (168, 168), (148, 224), (128, 188), (108, 224), (88, 168), (30, 150), (90, 116)]),
        rect(d, (94, 114, 162, 164)),
        polygon(d, [(78, 166), (30, 224), (110, 198)]),
        polygon(d, [(178, 166), (226, 224), (146, 198)]),
    ))
    save("motif_gate.png", lambda d: (
        rect(d, (40, 82, 216, 224)),
        rect(d, (70, 44, 104, 224)),
        rect(d, (152, 44, 186, 224)),
        polygon(d, [(30, 84), (226, 84), (190, 44), (66, 44)]),
        d.rounded_rectangle((98, 132, 158, 224), radius=28, fill=(255, 255, 255, 0)),
    ))
    save("motif_orbit.png", lambda d: (
        ellipse(d, (78, 78, 178, 178)),
        d.arc((28, 68, 228, 188), 10, 350, fill=(20, 20, 20, 255), width=20),
        d.arc((68, 28, 188, 228), 100, 440, fill=(20, 20, 20, 255), width=20),
        ellipse(d, (184, 54, 218, 88)),
        ellipse(d, (38, 168, 72, 202)),
    ))
    save("motif_mask.png", lambda d: (
        polygon(d, [(54, 58), (202, 58), (224, 132), (178, 220), (128, 190), (78, 220), (32, 132)]),
        ellipse(d, (70, 102, 112, 136)),
        ellipse(d, (144, 102, 186, 136)),
        polygon(d, [(112, 150), (144, 150), (128, 174)]),
    ))
    save("motif_fountain.png", lambda d: (
        polygon(d, [(128, 28), (170, 96), (148, 96), (148, 150), (108, 150), (108, 96), (86, 96)]),
        ellipse(d, (54, 116, 202, 186)),
        rect(d, (76, 164, 180, 214)),
        rect(d, (58, 210, 198, 232)),
        polygon(d, [(56, 120), (24, 82), (92, 112)]),
        polygon(d, [(200, 120), (232, 82), (164, 112)]),
    ))


if __name__ == "__main__":
    generate()
    print(f"wrote silhouettes to {OUT_DIR}/")
