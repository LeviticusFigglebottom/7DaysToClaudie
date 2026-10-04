"""Readables and keys: folded schematic sheets, trade magazines, torn notes, the ranger logbook, the
Remand field manual and keys on a lanyard / evidence tag. Origin bottom centre. params: kind, name, seed."""
from __future__ import annotations

import math

from mathutils import Matrix, Vector, noise

from lib import common, item_kit as K


def schematic(p):
    """Letter sheet folded in half (vertical crease), laid open as a shallow tent, horizontal crease too."""
    seed = int(p["seed"])
    r = common.rng(seed)
    noise.seed_set(seed)
    W, H = 0.216, 0.279
    lift = math.radians(r.uniform(7, 11))
    curl = r.uniform(0.004, 0.009)

    def pos(u, v):
        x = (u - 0.5) * W
        dx = abs(x)
        z = (W / 2 - dx) * math.sin(lift) * 0.9
        z += 0.0035 * (1 - abs(v - 0.5) * 2) ** 2                     # horizontal crease ridge
        z += curl * max(0.0, (dx / (W / 2)) - 0.75) ** 2 * 16          # outer edges curl up
        z += 0.0015 * noise.noise(Vector((u * 3, v * 3, 0.3)))
        return Vector((x * math.cos(lift), (v - 0.5) * H, z + 0.001))
    mb = K.MB()
    K.sheet(mb, 12, 10, pos, thickness=0.0003, mat_top=p["sheet"], mat_bottom="item_paper", mat_edge="item_paper",
            uv_bottom=lambda u, v: (u * W, v * H))
    return [mb.build(p["name"], sharp_deg=None)], {"settle": None}


def magazine(p):
    seed = int(p["seed"])
    noise.seed_set(seed)
    W, H, T = 0.21, 0.275, 0.0042

    def pos(u, v):
        x = (u - 0.5) * W
        y = (v - 0.5) * H
        z = T / 2 + 0.006 * max(0.0, u - 0.8) ** 2 * 25 + 0.0012 * noise.noise(Vector((u * 2, v * 2, 1.0)))
        # dog-eared top-right corner
        if u > 0.82 and v > 0.84:
            z += 0.012 * ((u - 0.82) / 0.18) * ((v - 0.84) / 0.16)
        return Vector((x, y, z))
    mb = K.MB()
    K.sheet(mb, 10, 10, pos, thickness=T, mat_top=p["cover"], mat_bottom="item_magazine_back", mat_edge="item_paper_edge",
            uv_bottom=lambda u, v: (u, v))
    # rounded spine fold on the left
    spine = [Vector((-W / 2, -H / 2 + H * i / 9, T / 2)) for i in range(10)]
    K.tube(mb, spine, (T * 0.55, T * 0.55), sides=8, mat=p["cover"], caps=(False, False), u_tile=0.02, v_scale=1.0 / H)
    return [mb.build(p["name"], sharp_deg=None)], {"settle": None}


def note(p):
    seed = int(p["seed"])
    r = common.rng(seed)
    noise.seed_set(seed)
    W, H = 0.148, 0.205
    flat = bool(p.get("flat", False))
    tear = [r.uniform(0.0, 0.006) for _ in range(30)]

    def pos(u, v):
        x = (u - 0.5) * W
        y = (v - 0.5) * H
        if v >= 1.0:   # torn / perforated top edge
            y -= tear[int(u * 29)]
        if flat:
            z = 0.0012 + 0.002 * noise.noise(Vector((u * 3, v * 3, 0.3)))
        else:
            z = 0.001 + 0.012 * abs(v - 0.5) ** 1.5 * 2 + 0.003 * math.sin(u * math.pi)
        return Vector((x, y, z))
    mb = K.MB()
    K.sheet(mb, 10, 12, pos, thickness=0.00025, mat_top=p["sheet"], mat_bottom="item_paper", mat_edge="item_paper",
            uv_bottom=lambda u, v: (u * W, v * H))
    return [mb.build(p["name"], sharp_deg=None)], {"settle": None}


def logbook(p):
    mb = K.MB()
    W, H, T, c = 0.152, 0.21, 0.019, 0.0022
    # page block
    K.box(mb, (W - 0.006, H - 0.008, T - 2 * c), (0.002, 0, T / 2), mat="item_paper_edge")
    # boards + spine (bookcloth), white label panel
    K.box(mb, (W, H, c), (0, 0, c / 2), mat="item_bookcloth", bevel=0.0008)
    K.box(mb, (W, H, c), (0, 0, T - c / 2), mat="item_bookcloth", bevel=0.0008)
    spine = [Vector((-W / 2 + 0.001, -H / 2 + H * i / 5, T / 2)) for i in range(6)]
    K.tube(mb, spine, (T / 2, 0.006), sides=10, mat="item_bookcloth", caps=(True, True), up=Vector((0, 0, 1)))
    mb.push(Matrix.Translation((0.008, 0.035, T)))
    K.extrude(mb, [(-0.045, -0.02), (0.045, -0.02), (0.045, 0.02), (-0.045, 0.02)], 0.0004, mat="item_paper_ledger",
              uv_rect=(0.08, 0.72, 0.9, 0.9))
    mb.pop()
    return [mb.build("note_ranger_log", sharp_deg=40)], {"settle": None}


def manual(p):
    seed = int(p["seed"])
    r = common.rng(seed)
    mb = K.MB()
    W, H, T = 0.15, 0.21, 0.017
    K.box(mb, (W - 0.004, H - 0.004, T - 0.0016), (0.001, 0, T / 2), mat="item_paper_edge")
    # soft covers (printed front, plain olive back) and a square spine
    mb.push(Matrix.Translation((0, 0, T - 0.0004)))
    K.extrude(mb, [(-W / 2, -H / 2), (W / 2, -H / 2), (W / 2, H / 2), (-W / 2, H / 2)], 0.0008, mat="item_manual_cover",
              side_mat="item_canvas_olive", uv_rect=(0.0, 0.0, 1.0, 1.0))
    mb.pop()
    mb.push(Matrix.Translation((0, 0, 0.0004)))
    K.extrude(mb, [(-W / 2, -H / 2), (W / 2, -H / 2), (W / 2, H / 2), (-W / 2, H / 2)], 0.0008, mat="item_canvas_olive",
              uv_scale=1.0)
    mb.pop()
    K.box(mb, (0.0012, H, T), (-W / 2 - 0.0002, 0, T / 2), mat="item_canvas_olive")
    # loose papers and a string bookmark sticking out
    for k, (y, w, mat) in enumerate(((0.03, 0.05, "item_paper_note"), (-0.05, 0.045, "item_paper_ledger"))):
        mb.push(Matrix.Translation((W / 2 - 0.02, y, T * (0.45 + 0.2 * k))) @ Matrix.Rotation(r.uniform(-0.15, 0.15), 4, "Z"))
        K.extrude(mb, [(0.0, -w / 2), (0.05, -w / 2), (0.05, w / 2), (0.0, w / 2)], 0.0003, mat=mat, side_mat="item_paper",
                  uv_rect=(0.1, 0.2 + k * 0.3, 0.6, 0.5 + k * 0.3))
        mb.pop()
    cord = K.bezier((0.0, H / 2 - 0.004, T * 0.6), (0.01, H / 2 + 0.02, T * 0.6), (0.02, H / 2 + 0.04, 0.002), (0.03, H / 2 + 0.07, 0.0012), 8)
    K.tube(mb, cord, 0.0012, sides=4, mat="item_paint_stripe")
    return [mb.build("field_manual", sharp_deg=40)], {"settle": None}


KEY_BOW_X, KEY_BOW_R = -0.0115, 0.0125


def _key_outline(r, length=0.055):
    """Pin-tumbler key in XY: blade along +X with V bitting on the -Y edge, round bow centred at
    (KEY_BOW_X, 0). One simple polygon (extrude fixes the winding)."""
    cx, R = KEY_BOW_X, KEY_BOW_R
    pts = [(0.0, 0.0056), (0.0042, 0.0056), (0.0048, 0.0042), (length - 0.003, 0.0042), (length, 0.0018), (length, -0.0016)]
    x = length - 0.003
    for _ in range(5):
        d = r.uniform(0.0008, 0.0030)
        pts += [(x, -0.0045), (x - 0.0028, -0.0045 + d), (x - 0.0056, -0.0045)]
        x -= 0.0062
    pts += [(0.0048, -0.0045), (0.0042, -0.0058), (0.0, -0.0058)]
    for k in range(18):
        a = -0.48 - (2 * math.pi - 0.96) * k / 17
        pts.append((cx + R * math.cos(a), R * math.sin(a)))
    return pts


def key(p):
    seed = int(p["seed"])
    r = common.rng(seed)
    mb = K.MB()
    metal = p.get("metal", "item_brass")
    outline = _key_outline(r)
    hole = [(math.cos(2 * math.pi * k / 12) * 0.0034 + KEY_BOW_X - 0.002, math.sin(2 * math.pi * k / 12) * 0.0034) for k in range(12)]
    mb.push(Matrix.Translation((0, 0, 0.0011)))
    K.extrude(mb, outline, 0.0021, holes=[hole], mat=metal, chamfer=0.0004, uv_scale=8.0)
    mb.pop()
    # groove along the blade
    K.box(mb, (0.04, 0.0012, 0.0004), (0.03, 0.0008, 0.0022), mat="item_steel_dark")
    # split ring through the bow hole (lying almost flat)
    ring_c = Vector((KEY_BOW_X - 0.002 - 0.0115, 0.0, 0.0018))
    loop = [ring_c + Vector((math.cos(a) * 0.0125, math.sin(a) * 0.0125, 0.0006 * math.sin(a * 2))) for a in [2 * math.pi * k / 24 for k in range(24)]]
    K.tube(mb, loop, 0.0011, sides=6, mat="item_steel_tool", closed=True)
    if p.get("tag") == "lanyard":
        # short red lanyard loop
        lc = ring_c + Vector((-0.045, 0.004, 0.0))
        lan = []
        for k in range(26):
            a = 2 * math.pi * k / 26
            lan.append(lc + Vector((math.cos(a) * 0.034, math.sin(a) * 0.011, 0.0016)))
        K.tube(mb, lan, (0.0055, 0.0007), profile=K.rect_profile(1, 1, 0.3), mat="item_plastic_red", closed=True, up=Vector((0, 0, 1)))
        K.box(mb, (0.012, 0.006, 0.004), (ring_c.x - 0.012, 0.0, 0.002), mat="item_steel_dark", bevel=0.0008)
    else:
        # manila evidence tag on a string
        mb.push(Matrix.Translation((ring_c.x - 0.075, -0.012, 0.0004)) @ Matrix.Rotation(0.25, 4, "Z"))
        tag = [(-0.04, -0.018), (0.028, -0.018), (0.04, -0.006), (0.04, 0.006), (0.028, 0.018), (-0.04, 0.018)]
        thole = [(math.cos(2 * math.pi * k / 10) * 0.0025 + 0.031, math.sin(2 * math.pi * k / 10) * 0.0025) for k in range(10)]
        K.extrude(mb, tag, 0.0005, holes=[thole], mat="item_tag_print", side_mat="item_paper", uv_rect=(0.0, 0.0, 1.0, 1.0))
        mb.pop()
        s = K.bezier(ring_c + Vector((-0.012, 0, 0.0)), ring_c + Vector((-0.02, -0.006, 0.001)), ring_c + Vector((-0.032, -0.006, 0.001)),
                     Vector((ring_c.x - 0.075 + 0.03 * math.cos(0.25), -0.012 + 0.03 * math.sin(0.25), 0.0008)), 8)
        K.tube(mb, s, 0.0007, sides=4, mat="item_cordage")
    return [mb.build(p["name"], sharp_deg=40)], {"settle": None}


BUILDERS = {"schematic": schematic, "magazine": magazine, "note": note, "logbook": logbook, "manual": manual, "key": key}


def build(params: dict, outputs: list[str]) -> None:
    parts, opts = BUILDERS[params["kind"]](params)
    K.publish(outputs, name=params.get("name", params["kind"]), parts=parts, seed=int(params["seed"]),
              ground_rot=opts.get("ground"), settle_deg=opts.get("settle", 20.0))
