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


def line(draw, pts, width=12):
    draw.line(pts, fill=(20, 20, 20, 255), width=width, joint="curve")


def cut_ellipse(draw, box):
    draw.ellipse(box, fill=(255, 255, 255, 0))


def cut_rect(draw, box):
    draw.rounded_rectangle(box, radius=6, fill=(255, 255, 255, 0))


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
    save("design_space_shuttle.png", lambda d: (
        polygon(d, [(128, 18), (164, 104), (158, 176), (128, 234), (98, 176), (92, 104)]),
        polygon(d, [(92, 118), (34, 190), (104, 168)]),
        polygon(d, [(164, 118), (222, 190), (152, 168)]),
        polygon(d, [(110, 178), (74, 226), (120, 204)]),
        polygon(d, [(146, 178), (182, 226), (136, 204)]),
        ellipse(d, (108, 70, 148, 110)),
    ))
    save("design_suspension_bridge.png", lambda d: (
        rect(d, (28, 160, 228, 184)),
        rect(d, (58, 72, 78, 220)),
        rect(d, (178, 72, 198, 220)),
        line(d, [(54, 78), (84, 104), (108, 126), (128, 138), (148, 126), (172, 104), (202, 78)], 10),
        line(d, [(62, 102), (62, 160)], 5),
        line(d, [(86, 114), (86, 160)], 5),
        line(d, [(110, 132), (110, 160)], 5),
        line(d, [(146, 132), (146, 160)], 5),
        line(d, [(170, 114), (170, 160)], 5),
        line(d, [(194, 102), (194, 160)], 5),
    ))
    save("design_windmill.png", lambda d: (
        polygon(d, [(108, 92), (148, 92), (166, 226), (90, 226)]),
        ellipse(d, (104, 84, 152, 132)),
        polygon(d, [(126, 30), (142, 96), (114, 96)]),
        polygon(d, [(226, 108), (144, 124), (144, 94)]),
        polygon(d, [(130, 226), (114, 120), (144, 120)]),
        polygon(d, [(30, 108), (112, 94), (112, 124)]),
    ))
    save("design_satellite.png", lambda d: (
        rect(d, (104, 94, 152, 150)),
        polygon(d, [(28, 70), (96, 92), (86, 154), (18, 132)]),
        polygon(d, [(228, 70), (160, 92), (170, 154), (238, 132)]),
        line(d, [(128, 94), (128, 42)], 8),
        ellipse(d, (116, 28, 140, 52)),
        line(d, [(128, 150), (128, 224)], 8),
        polygon(d, [(100, 222), (156, 222), (128, 190)]),
    ))
    save("design_helicopter.png", lambda d: (
        ellipse(d, (54, 102, 176, 164)),
        polygon(d, [(166, 118), (226, 100), (226, 132), (170, 146)]),
        line(d, [(88, 92), (178, 92)], 9),
        line(d, [(132, 92), (132, 62)], 8),
        rect(d, (48, 174, 172, 186)),
        line(d, [(70, 164), (64, 178)], 7),
        line(d, [(154, 164), (160, 178)], 7),
        line(d, [(210, 88), (238, 118)], 6),
        line(d, [(238, 88), (210, 118)], 6),
    ))
    save("design_ferris_wheel.png", lambda d: (
        ellipse(d, (42, 28, 214, 200)),
        cut_ellipse(d, (68, 54, 188, 174)),
        ellipse(d, (112, 98, 144, 130)),
        line(d, [(128, 114), (128, 28)], 7),
        line(d, [(128, 114), (214, 114)], 7),
        line(d, [(128, 114), (128, 200)], 7),
        line(d, [(128, 114), (42, 114)], 7),
        line(d, [(128, 114), (188, 54)], 7),
        line(d, [(128, 114), (68, 54)], 7),
        line(d, [(128, 114), (188, 174)], 7),
        line(d, [(128, 114), (68, 174)], 7),
        polygon(d, [(102, 202), (154, 202), (184, 232), (72, 232)]),
    ))
    save("design_crane.png", lambda d: (
        rect(d, (70, 48, 94, 226)),
        rect(d, (48, 218, 136, 236)),
        polygon(d, [(82, 48), (216, 66), (212, 88), (82, 72)]),
        line(d, [(94, 54), (138, 222)], 6),
        line(d, [(70, 82), (120, 222)], 6),
        line(d, [(210, 86), (210, 150)], 5),
        rect(d, (196, 150, 224, 178)),
    ))
    save("design_cable_car.png", lambda d: (
        line(d, [(24, 52), (232, 38)], 7),
        line(d, [(128, 46), (128, 84)], 8),
        rect(d, (74, 82, 182, 178)),
        polygon(d, [(90, 178), (166, 178), (150, 216), (106, 216)]),
        cut_rect(d, (92, 102, 118, 132)),
        cut_rect(d, (138, 102, 164, 132)),
        rect(d, (104, 68, 152, 88)),
    ))
    save("design_locomotive.png", lambda d: (
        rect(d, (62, 112, 198, 174)),
        rect(d, (134, 72, 188, 116)),
        rect(d, (66, 84, 102, 116)),
        rect(d, (42, 150, 220, 182)),
        rect(d, (84, 62, 104, 88)),
        polygon(d, [(36, 142), (62, 126), (62, 174), (36, 174)]),
        ellipse(d, (56, 166, 104, 214)),
        ellipse(d, (122, 166, 170, 214)),
        ellipse(d, (178, 170, 214, 206)),
        line(d, [(78, 190), (146, 190), (196, 188)], 6),
    ))
    save("design_bicycle.png", lambda d: (
        ellipse(d, (30, 132, 104, 206)),
        cut_ellipse(d, (48, 150, 86, 188)),
        ellipse(d, (152, 132, 226, 206)),
        cut_ellipse(d, (170, 150, 208, 188)),
        line(d, [(67, 170), (118, 106), (189, 170), (102, 170), (67, 170)], 9),
        line(d, [(102, 170), (118, 106)], 9),
        line(d, [(118, 106), (148, 96)], 8),
        line(d, [(188, 170), (166, 102)], 8),
        line(d, [(154, 98), (182, 96)], 7),
        line(d, [(112, 102), (100, 82)], 7),
        rect(d, (84, 76, 120, 88)),
    ))
    save("design_radio_telescope.png", lambda d: (
        polygon(d, [(72, 78), (194, 36), (204, 144), (104, 154)]),
        cut_ellipse(d, (104, 58, 192, 132)),
        line(d, [(122, 144), (88, 224)], 12),
        line(d, [(150, 140), (184, 224)], 12),
        rect(d, (62, 218, 210, 236)),
        line(d, [(150, 70), (220, 28)], 6),
        ellipse(d, (214, 20, 232, 38)),
    ))
    save("design_zeppelin.png", lambda d: (
        ellipse(d, (28, 72, 224, 152)),
        polygon(d, [(208, 86), (238, 64), (232, 112)]),
        polygon(d, [(210, 138), (238, 166), (218, 142)]),
        rect(d, (94, 148, 166, 174)),
        line(d, [(80, 160), (180, 160)], 6),
        ellipse(d, (64, 94, 94, 124)),
    ))
    save("design_roller_coaster.png", lambda d: (
        line(d, [(26, 174), (58, 140), (94, 94), (132, 88), (174, 132), (228, 88)], 11),
        line(d, [(32, 198), (68, 154), (104, 118), (134, 118), (178, 154), (228, 118)], 7),
        line(d, [(58, 150), (58, 224)], 7),
        line(d, [(100, 110), (100, 224)], 7),
        line(d, [(146, 116), (146, 224)], 7),
        line(d, [(190, 124), (190, 224)], 7),
        rect(d, (128, 76, 172, 96)),
        ellipse(d, (132, 92, 146, 106)),
        ellipse(d, (154, 92, 168, 106)),
    ))
    save("design_sailing_ship.png", lambda d: (
        polygon(d, [(36, 166), (226, 166), (190, 218), (78, 218)]),
        line(d, [(118, 44), (118, 170)], 9),
        line(d, [(166, 62), (166, 170)], 8),
        polygon(d, [(122, 52), (184, 150), (122, 150)]),
        polygon(d, [(114, 64), (58, 150), (114, 150)]),
        polygon(d, [(170, 72), (216, 152), (170, 152)]),
        line(d, [(58, 150), (218, 150)], 6),
    ))
    save("design_observation_tower.png", lambda d: (
        polygon(d, [(118, 34), (138, 34), (172, 226), (84, 226)]),
        ellipse(d, (74, 70, 182, 112)),
        cut_ellipse(d, (96, 82, 160, 100)),
        rect(d, (56, 114, 200, 132)),
        line(d, [(102, 74), (154, 226)], 5),
        line(d, [(154, 74), (102, 226)], 5),
        ellipse(d, (110, 20, 146, 56)),
    ))
    save("landmark_clock_tower.png", lambda d: (
        rect(d, (88, 72, 168, 226)),
        polygon(d, [(82, 72), (128, 24), (174, 72)]),
        rect(d, (104, 52, 152, 84)),
        ellipse(d, (100, 92, 156, 148)),
        cut_ellipse(d, (114, 106, 142, 134)),
        rect(d, (70, 210, 186, 234)),
        cut_rect(d, (106, 166, 126, 206)),
        cut_rect(d, (134, 166, 154, 206)),
    ))
    save("landmark_tower_bridge.png", lambda d: (
        rect(d, (48, 70, 86, 226)),
        rect(d, (170, 70, 208, 226)),
        polygon(d, [(44, 70), (67, 28), (90, 70)]),
        polygon(d, [(166, 70), (189, 28), (212, 70)]),
        rect(d, (24, 150, 232, 174)),
        line(d, [(68, 78), (128, 134), (188, 78)], 8),
        line(d, [(68, 150), (128, 108), (188, 150)], 6),
        cut_rect(d, (56, 92, 78, 128)),
        cut_rect(d, (178, 92, 200, 128)),
    ))
    save("landmark_liberty.png", lambda d: (
        polygon(d, [(116, 74), (140, 74), (164, 218), (92, 218)]),
        ellipse(d, (104, 48, 152, 92)),
        polygon(d, [(102, 48), (128, 18), (154, 48)]),
        line(d, [(142, 80), (198, 38)], 13),
        polygon(d, [(190, 24), (218, 32), (198, 52)]),
        line(d, [(108, 86), (70, 140)], 12),
        rect(d, (76, 216, 180, 236)),
    ))
    save("landmark_space_needle.png", lambda d: (
        ellipse(d, (68, 68, 188, 102)),
        cut_ellipse(d, (96, 76, 160, 94)),
        polygon(d, [(120, 28), (136, 28), (144, 72), (112, 72)]),
        polygon(d, [(122, 96), (134, 96), (166, 226), (90, 226)]),
        line(d, [(118, 104), (86, 226)], 6),
        line(d, [(138, 104), (170, 226)], 6),
        rect(d, (74, 222, 182, 236)),
    ))
    save("landmark_arch.png", lambda d: (
        rect(d, (54, 110, 92, 224)),
        rect(d, (164, 110, 202, 224)),
        ellipse(d, (54, 36, 202, 184)),
        cut_ellipse(d, (86, 70, 170, 190)),
        rect(d, (56, 176, 92, 224)),
        rect(d, (164, 176, 200, 224)),
        rect(d, (42, 218, 214, 236)),
    ))
    save("landmark_chrysler_spire.png", lambda d: (
        polygon(d, [(128, 18), (154, 82), (144, 226), (112, 226), (102, 82)]),
        ellipse(d, (88, 64, 168, 108)),
        cut_ellipse(d, (102, 76, 154, 98)),
        ellipse(d, (78, 96, 178, 144)),
        cut_ellipse(d, (96, 110, 160, 132)),
        rect(d, (72, 220, 184, 236)),
    ))


if __name__ == "__main__":
    generate()
    print(f"wrote silhouettes to {OUT_DIR}/")
