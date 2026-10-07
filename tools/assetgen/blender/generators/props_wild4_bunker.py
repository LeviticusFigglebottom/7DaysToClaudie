"""Forest set pieces, round 4 (ADR-0053): props of the Kell Shelter (w4_hillside_bunker), a prepper's hillside
cabin over a two-level concrete bunker.

The bunker: an NBC air filtration unit (its cartridges furred white with Bloom when worn), a skid-mounted diesel
generator with a run lamp, blue water drums with hand pumps, a decontamination shower stall, the ham radio desk,
steel shelving stacked with tins, and the map wall in the comms room. The yard: a solar panel on a pole with its
battery box, a chicken coop with its run, an oak rain barrel on cinder blocks and an open pole woodshed.

Conventions (docs/ASSET_PIPELINE.md): metres, Z up, front -Y, origin bottom centre; floor props have their depth
centred on the origin (PoiBuilder's collision box is the def's size centred there). The map wall hangs with its
origin on the wall plane, bottom centre, reaching out toward -Y. Only shared materials are used.
'clean' is the shelter as Gideon kept it, 'worn' a winter after the filters failed, 'destroyed' looted.
"""
from __future__ import annotations

import math

from mathutils import Vector

from lib import props_ext_kit as K
from lib import props_ext_parts as P
from lib import props_wild_parts as W

STEEL = "lab_cabinet_grey"
STEEL_DARK = "road_steel_dark"
GALV = "metal_galvanized"
SHELF = "metal_shelf_grey"



def _bx(ctx, name, size, center, mat, *, bevel=0.006, uv_scale=2.0, **kw):
    return ctx.add(K.box(name, size, center=center, bevel=bevel), mat, uv="box", uv_scale=uv_scale, **kw)


def _cy(ctx, name, r, h, center, mat, *, axis="Z", segs=12, r_top=None, uv_scale=2.0, **kw):
    o = K.cyl(name, r, h, segs=segs, center=center, axis=axis, r_top=r_top)
    return ctx.add(o, mat, uv="box", uv_scale=uv_scale, smooth=40, **kw)


def _centre_depth(ctx) -> None:
    """Moves every part so the model's depth (Blender Y) is centred on the origin, as PoiBuilder centres the
    def's collision box there."""
    lo, hi = 1e9, -1e9
    for o in ctx.parts:
        for v in o.data.vertices:
            lo = min(lo, v.co.y)
            hi = max(hi, v.co.y)
    for o in ctx.parts:
        K.place(o, (0, -(lo + hi) * 0.5, 0))


def _tin(ctx, name, x, y, z, r, label_idx, *, lying=False, crushed=0.0):
    o = K.cyl(name, 0.042, 0.12, segs=8, center=(0, 0, 0.06))
    if crushed > 0.0:
        K.place(o, (0, 0, 0), scale=(1.0 + crushed * 0.25, 1.0 - crushed * 0.3, 1.0 - crushed * 0.5))
    if lying:
        K.place(o, (0, 0, 0), (90, 0, r.uniform(0, 180)))
        K.place(o, (x, y, z + 0.042))
    else:
        K.place(o, (x, y, z))
    lab = ["item_can_label_a", "item_can_label_b", "item_can_label_c", "item_can_label_d"][label_idx % 4]
    return ctx.add(o, lab, uv="cyl", uv_axis=2, smooth=40, patches=0.3, ao=False)


# ============================================================================================
# The bunker
# ============================================================================================

def w4_bunker_air_filter(ctx: K.Ctx) -> None:
    """An NBC filtration cabinet: a grey steel box on feet, a hand-crank blower on its face, a pressure gauge,
    two cartridge housings on top with clamped lids and the ducts rising to the ceiling. Worn: one housing open,
    its cartridge furred white with Bloom, spore fuzz round the seams."""
    r = ctx.rnd("filter")
    Wd, D, H = 1.1, 0.42, 1.1
    _bx(ctx, "cabinet", (Wd, D, H), (0, 0, 0.08 + H / 2), STEEL, bevel=0.012, patches=0.5)
    for sx in (-1, 1):
        for sy in (-1, 1):
            _bx(ctx, f"foot{sx}{sy}", (0.06, 0.06, 0.08), (sx * (Wd / 2 - 0.06), sy * (D / 2 - 0.06), 0.04), STEEL_DARK)
    # Blower housing and its crank on the face.
    bl = K.cyl("blower", 0.22, 0.08, segs=20, center=(-0.22, -D / 2 - 0.04, 0.62), axis="Y")
    ctx.add(bl, "road_paint_grey", uv="box", uv_scale=2.0, smooth=40, patches=0.5)
    W.rod(ctx, "crank_arm", (-0.22, -D / 2 - 0.09, 0.62), (-0.22 + 0.16, -D / 2 - 0.09, 0.5), 0.012, STEEL_DARK, segs=6)
    W.rod(ctx, "crank_grip", (-0.06, -D / 2 - 0.09, 0.5), (-0.06, -D / 2 - 0.17, 0.5), 0.018, "plastic_black", segs=8)
    g = K.cyl("gauge", 0.07, 0.04, segs=16, center=(0.28, -D / 2 - 0.02, 0.86), axis="Y")
    ctx.add(g, "road_chrome", uv="box", uv_scale=4.0, smooth=40)
    face = K.cyl("gauge_face", 0.06, 0.004, segs=16, center=(0.28, -D / 2 - 0.042, 0.86), axis="Y")
    ctx.add(face, "ceramic_white", uv="box", uv_scale=4.0, ao=False)
    _bx(ctx, "plate", (0.3, 0.004, 0.12), (0.28, -D / 2 - 0.002, 0.62), "road_paint_yellow", bevel=0.0)
    # Cartridge housings on top.
    top = 0.08 + H
    for k, x in enumerate((-0.28, 0.28)):
        _cy(ctx, f"housing{k}", 0.17, 0.42, (x, 0.0, top + 0.21), "road_paint_grey", segs=18, patches=0.5)
        opened = ctx.worn and k == 0
        if opened:
            lid = K.cyl(f"lid{k}", 0.18, 0.03, segs=18, center=(0, 0, 0))
            K.place(lid, (0, 0, 0), (0, 70, 0))
            K.place(lid, (x - 0.2, 0.0, top + 0.5))
            ctx.add(lid, "road_paint_grey", uv="box", uv_scale=2.0, smooth=40)
            cart = K.cyl(f"cart{k}", 0.14, 0.36, segs=16, center=(x, 0.0, top + 0.28))
            ctx.add(cart, "bloom_felt", uv="box", uv_scale=3.0, smooth=50)
            for j in range(5):
                fz = K.blob(f"fuzz{k}{j}", 0.06, subdiv=1, scale=(1.4, 1.4, 0.6),
                            center=(x + r.uniform(-0.12, 0.12), r.uniform(-0.12, 0.12), top + 0.44 + r.uniform(0, 0.03)),
                            rough=0.4, seed=j)
                ctx.add(fz, "bloom_growth", uv="box", uv_scale=4.0, smooth=50)
        else:
            _cy(ctx, f"lid{k}", 0.18, 0.03, (x, 0.0, top + 0.435), STEEL_DARK, segs=18)
            for a in range(3):
                ang = a / 3 * math.tau
                _bx(ctx, f"clamp{k}{a}", (0.03, 0.03, 0.08),
                    (x + math.cos(ang) * 0.175, math.sin(ang) * 0.175, top + 0.4), GALV, bevel=0.0)
        # Duct from the housing to the ceiling.
        W.rod(ctx, f"duct{k}", (x, 0.08, top + 0.45), (x, 0.08, 2.3), 0.07, GALV, segs=12)
        for z in (1.9, 2.2):
            W.rod(ctx, f"band{k}{z}", (x, 0.08, z), (x, 0.08, z + 0.03), 0.075, STEEL_DARK, segs=12)
    if ctx.worn:
        for j in range(8):
            side = r.choice((-1, 1))
            fz = K.blob(f"seam{j}", 0.035, subdiv=1, scale=(1.6, 0.5, 1.0),
                        center=(side * Wd / 2 * r.uniform(0.2, 0.95), -D / 2 - 0.01, r.uniform(0.2, 1.15)), rough=0.5, seed=j)
            ctx.add(fz, "bloom_growth", uv="box", uv_scale=4.0, smooth=50)
    _centre_depth(ctx)


def w4_bunker_generator(ctx: K.Ctx) -> None:
    """A small diesel generator set on a steel skid: the engine block, the alternator drum, a radiator, the
    control box with its green run lamp, a day tank and the exhaust pipe bent up to the ceiling. Worn: the lamp
    dead (a dark lens) and the tank cap off."""
    Wd, D = 1.6, 0.8
    for sy in (-1, 1):
        W.section(ctx, f"rail{sy}", (-Wd / 2, sy * (D / 2 - 0.05), 0.05), (Wd / 2, sy * (D / 2 - 0.05), 0.05),
                  W.prof_c(0.1, 0.05, 0.006), STEEL_DARK)
    _bx(ctx, "deck", (Wd - 0.05, D - 0.1, 0.02), (0, 0, 0.11), STEEL_DARK, bevel=0.0)
    _bx(ctx, "engine", (0.62, 0.52, 0.55), (-0.3, 0.02, 0.4), "lab_genset_yellow", bevel=0.02, patches=0.6)
    _bx(ctx, "head", (0.5, 0.36, 0.14), (-0.3, 0.02, 0.74), "road_steel", bevel=0.01)
    alt = K.cyl("alternator", 0.22, 0.5, segs=20, center=(0.25, 0.02, 0.38), axis="X")
    ctx.add(alt, "lab_genset_yellow", uv="box", uv_scale=2.0, smooth=40, patches=0.6)
    _bx(ctx, "radiator", (0.1, 0.56, 0.6), (-0.68, 0.02, 0.42), STEEL_DARK, bevel=0.005)
    for k in range(7):
        _bx(ctx, f"fin{k}", (0.012, 0.5, 0.012), (-0.735, 0.02, 0.18 + k * 0.08), GALV, bevel=0.0)
    # Control box on a post, the run lamp facing the front.
    W.rod(ctx, "ctl_post", (0.55, 0.25, 0.12), (0.55, 0.25, 0.85), 0.025, STEEL_DARK, segs=6)
    _bx(ctx, "ctl_box", (0.34, 0.16, 0.3), (0.55, 0.2, 0.98), "road_paint_grey", bevel=0.01)
    lamp_mat = "road_steel_dark" if ctx.worn else "lab_glow_green"
    lens = K.cyl("run_lamp", 0.025, 0.02, segs=10, center=(0.55, 0.11, 1.05), axis="Y")
    ctx.add(lens, lamp_mat, uv="box", uv_scale=4.0, ao=False)
    for k, x in enumerate((0.47, 0.63)):
        sw = K.box(f"switch{k}", (0.03, 0.03, 0.04), center=(x, 0.11, 0.94))
        ctx.add(sw, "plastic_black", uv="box", uv_scale=4.0)
    # Day tank on the far end, exhaust up the back.
    _bx(ctx, "tank", (0.36, 0.5, 0.32), (0.62, -0.05, 0.28), "road_paint_red", bevel=0.02, patches=0.6)
    cap_z = 0.46 if not ctx.worn else 0.45
    cap = K.cyl("cap", 0.04, 0.03, segs=10, center=(0.68 if not ctx.worn else 0.78, -0.15, cap_z))
    ctx.add(cap, "plastic_black", uv="box", uv_scale=4.0)
    ex = K.tube("exhaust", [(-0.3, 0.2, 0.7), (-0.3, 0.34, 0.85), (-0.3, 0.36, 1.1), (-0.3, 0.36, 1.3)], 0.035, segs=8)
    ctx.add(ex, "road_rust", uv="box", uv_scale=3.0, smooth=40)


def w4_bunker_water_drum(ctx: K.Ctx) -> None:
    """A blue 55-gallon plastic water drum with a hand pump in the bung and the rotation date in marker on a
    strip of tape. Worn: the pump handle down, the drum scuffed."""
    prof = [(0.0, 0.0), (0.27, 0.0), (0.29, 0.03), (0.29, 0.3), (0.3, 0.32), (0.29, 0.34), (0.29, 0.62), (0.3, 0.64),
            (0.29, 0.66), (0.29, 0.86), (0.27, 0.89), (0.0, 0.89)]
    drum = K.lathe("drum", prof, segs=20)
    ctx.add(drum, "plastic_blue", uv="cyl", uv_axis=2, smooth=40, patches=0.5)
    _bx(ctx, "tape", (0.2, 0.004, 0.05), (0.0, -0.293, 0.75), "packing_tape", bevel=0.0, ao=False)
    W.rod(ctx, "pump_tube", (0.12, 0.0, 0.89), (0.12, 0.0, 1.06), 0.022, "plastic_white", segs=8)
    W.rod(ctx, "spout", (0.12, 0.0, 1.0), (0.12, -0.16, 0.97), 0.012, "plastic_white", segs=6)
    hz = 1.08 if not ctx.worn else 1.0
    W.rod(ctx, "handle", (0.12, 0.0, 1.06), (-0.12, 0.02, hz + 0.08), 0.012, "plastic_black", segs=6)
    _cy(ctx, "bung", 0.03, 0.02, (-0.12, 0.08, 0.9), "plastic_black", segs=8)


def w4_bunker_decon_shower(ctx: K.Ctx) -> None:
    """A decontamination stall: a square steel shower pan, a galvanized pipe frame, a rain head with a pull
    chain, a heavy clear plastic curtain on rings round three sides (open at the front) and a scrub brush on a
    hook. Worn: the curtain torn half off its rings and grime in the pan."""
    Wd, D, H = 1.0, 0.92, 2.25
    hw, hd = Wd / 2, D / 2
    pan = K.box("pan", (Wd, D, 0.1), center=(0, 0, 0.05), bevel=0.02)
    K.delete_faces(pan, lambda c, n: n.z > 0.9)
    ctx.add(pan, "road_stainless", uv="box", uv_scale=1.5, patches=0.6)
    _bx(ctx, "pan_floor", (Wd - 0.06, D - 0.06, 0.01), (0, 0, 0.03), "road_stainless", bevel=0.0, patches=0.7)
    _cy(ctx, "drain", 0.04, 0.005, (0, 0, 0.037), "road_steel_dark", segs=12, ao=False)
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.rod(ctx, f"leg{sx}{sy}", (sx * hw, sy * hd, 0.08), (sx * hw, sy * hd, H), 0.022, GALV, segs=8)
        W.rod(ctx, f"top_y{sx}", (sx * hw, -hd, H), (sx * hw, hd, H), 0.022, GALV, segs=8)
    for sy in (-1, 1):
        W.rod(ctx, f"top_x{sy}", (-hw, sy * hd, H), (hw, sy * hd, H), 0.022, GALV, segs=8)
    W.rod(ctx, "feed", (0.0, hd, H), (0.0, 0.0, H - 0.05), 0.018, GALV, segs=8)
    _cy(ctx, "rain_head", 0.13, 0.04, (0, 0, H - 0.08), "road_chrome", segs=18)
    W.rod(ctx, "chain", (0.12, 0.0, H - 0.04), (0.12, -0.02, 1.55), 0.004, GALV, segs=4)
    _cy(ctx, "chain_grip", 0.012, 0.08, (0.12, -0.02, 1.52), "plastic_black", segs=6)
    # Curtain: back and two sides (the front stays open).
    sheets = [
        ((-hw, hd, 0.2), (hw, hd, 0.2), (hw, hd, H - 0.06), (-hw, hd, H - 0.06)),
        ((-hw, -hd, 0.2), (-hw, hd, 0.2), (-hw, hd, H - 0.06), (-hw, -hd, H - 0.06)),
        ((hw, hd, 0.2), (hw, -hd, 0.2), (hw, -hd, H - 0.06), (hw, hd, H - 0.06)),
    ]
    for k, q in enumerate(sheets):
        cur = K.quad_sheet(f"curtain{k}", *q, 10, 8)
        for v in cur.data.vertices:
            n = 0.03 * math.sin(v.co.x * 11.0 + v.co.y * 9.0 + k)
            if k == 0:
                v.co.y += n
            else:
                v.co.x += n
        if ctx.worn and k == 2:
            K.delete_faces(cur, lambda c, nn: c.z > 1.3 and c.y < 0.1)
        K.solidify(cur, 0.003, offset=0.0, even=False)
        ctx.add(cur, "road_bag_clear", uv="box", uv_scale=1.0, smooth=40, patches=0.6)
    W.rod(ctx, "hook", (-hw, -hd + 0.15, 1.4), (-hw + 0.06, -hd + 0.15, 1.38), 0.006, GALV, segs=4)
    _bx(ctx, "brush", (0.05, 0.2, 0.05), (-hw + 0.07, -hd + 0.15, 1.3), "wood_raw", bevel=0.01)
    if ctx.worn:
        g = K.grid("grime", Wd - 0.1, D - 0.1, 4, 4, center=(0, 0, 0.037))
        ctx.add(g, "bloom_felt", uv="box", uv_scale=2.0, patches=0.3, ao=False)


def w4_bunker_radio_desk(ctx: K.Ctx) -> None:
    """A plywood ham radio desk: an HF transceiver, its power supply and an SWR meter on a shelf over the
    desktop, a desk microphone, a clock on UTC, the logbook open and a frequency list taped to the shelf.
    Worn: the desk grimed, the logbook shut, papers on the floor."""
    r = ctx.rnd("radio")
    Wd, D, H = 1.6, 0.72, 0.76
    _bx(ctx, "top", (Wd, D, 0.03), (0, 0, H - 0.015), "road_plywood", bevel=0.004, uv_scale=1.0, patches=0.5)
    for sx in (-1, 1):
        _bx(ctx, f"side{sx}", (0.03, D - 0.02, H - 0.03), (sx * (Wd / 2 - 0.015), 0, (H - 0.03) / 2), "road_plywood",
            bevel=0.003, uv_scale=1.0)
    _bx(ctx, "modesty", (Wd - 0.06, 0.02, 0.4), (0, D / 2 - 0.02, H - 0.25), "road_plywood", bevel=0.003, uv_scale=1.0)
    # Riser shelf at the back.
    for sx in (-1, 1):
        _bx(ctx, f"riser{sx}", (0.025, 0.28, 0.32), (sx * (Wd / 2 - 0.05), D / 2 - 0.16, H + 0.16), "road_plywood", bevel=0.003)
    _bx(ctx, "shelf", (Wd - 0.08, 0.3, 0.025), (0, D / 2 - 0.16, H + 0.33), "road_plywood", bevel=0.003)
    # Transceiver, power supply, SWR meter.
    _bx(ctx, "rig", (0.36, 0.3, 0.12), (-0.2, D / 2 - 0.2, H + 0.06), "furn_plastic_black", bevel=0.008)
    _bx(ctx, "rig_face", (0.34, 0.004, 0.1), (-0.2, D / 2 - 0.352, H + 0.06), "wild_radio_face", bevel=0.0, ao=False)
    kn = K.cyl("vfo", 0.03, 0.03, segs=14, center=(-0.12, D / 2 - 0.365, H + 0.055), axis="Y")
    ctx.add(kn, "road_chrome", uv="box", uv_scale=4.0, smooth=40)
    _bx(ctx, "psu", (0.24, 0.26, 0.12), (0.22, D / 2 - 0.2, H + 0.06), "road_paint_grey", bevel=0.006)
    _bx(ctx, "swr", (0.2, 0.14, 0.1), (-0.25, D / 2 - 0.16, H + 0.395), "furn_plastic_black", bevel=0.006)
    _bx(ctx, "swr_face", (0.16, 0.004, 0.06), (-0.25, D / 2 - 0.232, H + 0.4), "ceramic_white", bevel=0.0, ao=False)
    clk = K.cyl("clock", 0.08, 0.04, segs=18, center=(0.3, D / 2 - 0.12, H + 0.43), axis="Y")
    ctx.add(clk, "furn_plastic_black", uv="box", uv_scale=3.0, smooth=40)
    cf = K.cyl("clock_face", 0.07, 0.004, segs=18, center=(0.3, D / 2 - 0.142, H + 0.43), axis="Y")
    ctx.add(cf, "ceramic_white", uv="box", uv_scale=3.0, ao=False)
    _bx(ctx, "freq_list", (0.2, 0.003, 0.14), (0.0, D / 2 - 0.312, H + 0.26), "item_paper_ledger", bevel=0.0, ao=False)
    # Desk mic and its cable.
    _cy(ctx, "mic_base", 0.06, 0.02, (0.0, -0.05, H + 0.01), "furn_plastic_black", segs=14)
    W.rod(ctx, "mic_stem", (0.0, -0.05, H + 0.02), (0.0, -0.03, H + 0.2), 0.008, "road_chrome", segs=6)
    _cy(ctx, "mic_head", 0.03, 0.09, (0.0, -0.04, H + 0.24), "furn_plastic_black", segs=12)
    cab = K.tube("mic_cable", [(0.0, -0.02, H + 0.01), (0.05, 0.1, H + 0.005), (-0.15, D / 2 - 0.36, H + 0.03)], 0.004, segs=4)
    ctx.add(cab, "plastic_black", uv="box", uv_scale=4.0, smooth=40)
    # The logbook.
    if ctx.worn:
        _bx(ctx, "log_shut", (0.22, 0.3, 0.025), (0.45, -0.1, H + 0.013), "item_bookcloth", bevel=0.003)
        for k in range(4):
            sh = K.box(f"sheet{k}", (0.21, 0.28, 0.002), center=(0, 0, 0))
            K.place(sh, (r.uniform(-0.55, 0.55), r.uniform(-0.2, 0.05), 0.003 + k * 0.002), (0, 0, r.uniform(0, 180)))
            ctx.add(sh, "item_paper_ledger", uv="planar", uv_scale=1.0, ao=False)
    else:
        for sx in (-1, 1):
            pg = K.box(f"log_page{sx}", (0.21, 0.3, 0.012), center=(0.45 + sx * 0.106, -0.1, H + 0.006))
            ctx.add(pg, "item_paper_ledger", uv="planar", uv_scale=1.0)
        W.rod(ctx, "pencil", (0.3, -0.25, H + 0.008), (0.42, -0.31, H + 0.008), 0.004, "road_paint_yellow", segs=6)


# ============================================================================================
# Shelving and tins
# ============================================================================================

def w4_bunker_shelf_cans(ctx: K.Ctx) -> None:
    """Grey steel shelving five shelves high with labelled tins stacked in rows and white mylar buckets on the
    bottom shelf. Worn: half the tins gone; destroyed: tipped over on its back and stripped, empties on the
    floor."""
    r = ctx.rnd("shelf")
    dr = ctx.drnd("shelf")
    Wd, D, H = 1.2, 0.42, 1.98
    parts: list = []
    shelf_z = [0.08, 0.5, 0.9, 1.3, 1.7]
    if ctx.destroyed:
        # Tipped over backwards against the wall it stood on: the frame lies on its back, 0.45 deep.
        for sx in (-1, 1):
            for z in (0.0, D):
                W.bar(ctx, f"post{sx}{z}", (sx * (Wd / 2 - 0.02), -0.2, z * 0.5 + 0.02), (sx * (Wd / 2 - 0.02), 0.2, z * 0.5 + 0.02),
                      0.03, 0.03, SHELF)
        for k in range(4):
            _bx(ctx, f"shelf{k}", (Wd - 0.04, 0.02, D), (0, -0.2 + k * 0.13, D / 2 + 0.02), SHELF, bevel=0.003)
        for k in range(14):
            _tin(ctx, f"empty{k}", dr.uniform(-0.6, 0.6), dr.uniform(-0.22, 0.22), 0.0, dr, k, lying=True,
                 crushed=dr.uniform(0.0, 0.7))
        return
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.bar(ctx, f"post{sx}{sy}", (sx * (Wd / 2 - 0.015), sy * (D / 2 - 0.015), 0.0),
                  (sx * (Wd / 2 - 0.015), sy * (D / 2 - 0.015), H), 0.03, 0.03, SHELF, up=(0, 1, 0))
    for k, z in enumerate(shelf_z):
        _bx(ctx, f"shelf{k}", (Wd - 0.02, D - 0.02, 0.02), (0, 0, z), SHELF, bevel=0.003)
    # Buckets on the bottom shelf.
    for k, x in enumerate((-0.35, 0.0, 0.35)):
        if ctx.worn and k == 1:
            continue
        b = P.bucket(f"bucket{k}", top_r=0.15, bot_r=0.13, h=0.36, segs=14)
        K.place(b, (x, 0.0, 0.09))
        ctx.add(b, "plastic_white", uv="cyl", uv_axis=2, smooth=40, patches=0.4)
    keep = 0.45 if ctx.worn else 1.0
    n = 0
    for k, z in enumerate(shelf_z[1:]):
        for row in (-0.1, 0.1):
            for i in range(9):
                if r.random() > keep:
                    continue
                x = -Wd / 2 + 0.1 + i * 0.125
                stack = 2 if (k < 3 and r.random() < 0.5) else 1
                for s in range(stack):
                    _tin(ctx, f"tin{n}", x, row, z + 0.01 + s * 0.122, r, k + i)
                    n += 1
    if ctx.worn:
        for k in range(3):
            _tin(ctx, f"floor{k}", dr.uniform(-0.5, 0.5), dr.uniform(-0.18, 0.18), 0.0, dr, k, lying=True, crushed=0.6)
    _ = parts


# ============================================================================================
# The yard
# ============================================================================================

def w4_bunker_solar_pole(ctx: K.Ctx) -> None:
    """A solar panel tilted south (to the front) on a steel pole set in a concrete collar, a junction box under
    the panel, the cable taped down the pole to a grey battery box at its foot. Worn: the glass cracked, the box
    lid hanging open."""
    pole_h = 2.7
    _cy(ctx, "collar", 0.22, 0.12, (0, 0.25, 0.06), "concrete", segs=16)
    W.rod(ctx, "pole", (0, 0.25, 0.0), (0, 0.25, pole_h), 0.05, GALV, segs=12)
    _bx(ctx, "mount", (0.3, 0.12, 0.1), (0, 0.25, pole_h + 0.03), STEEL_DARK)
    # Panel 1.6 x 1.0 tilted 35 degrees, facing -Y (the front, south).
    tilt = 35.0
    pw, ph = 1.58, 1.0
    frame = K.box("panel_frame", (pw, ph, 0.04), center=(0, 0, 0), bevel=0.004)
    K.place(frame, (0, 0, 0), (-tilt, 0, 0))
    K.place(frame, (0, 0.2, pole_h + 0.36))
    ctx.add(frame, "road_alu", uv="box", uv_scale=2.0, patches=0.4)
    cells = K.grid("panel_cells", pw - 0.06, ph - 0.06, 6, 4, center=(0, 0, 0.0205))
    K.place(cells, (0, 0, 0), (-tilt, 0, 0))
    K.place(cells, (0, 0.2, pole_h + 0.36))
    ctx.add(cells, "furn_crt_screen", uv="box", uv_scale=1.0, ao=False)
    if ctx.worn:
        cr = K.grid("crack", 0.5, 0.3, 2, 2, center=(0.3, 0.15, 0.022))
        K.place(cr, (0, 0, 0), (-tilt, 0, 0))
        K.place(cr, (0, 0.2, pole_h + 0.36))
        ctx.add(cr, "glass_clear", uv="box", uv_scale=4.0, ao=False)
    W.rod(ctx, "brace", (0, 0.25, pole_h - 0.4), (0, 0.45, pole_h + 0.2), 0.02, STEEL_DARK, segs=6)
    _bx(ctx, "jbox", (0.14, 0.08, 0.12), (0, 0.33, pole_h - 0.1), "road_paint_grey")
    cab = K.tube("cable", [(0.05, 0.31, pole_h - 0.15), (0.06, 0.3, 1.0), (0.07, 0.3, 0.35), (0.3, 0.3, 0.3)], 0.008, segs=5)
    ctx.add(cab, "plastic_black", uv="box", uv_scale=4.0, smooth=40)
    for k, z in enumerate((2.2, 1.4, 0.7)):
        _bx(ctx, f"tape{k}", (0.11, 0.11, 0.04), (0.02, 0.25, z), "plastic_black", bevel=0.0)
    _bx(ctx, "battery_box", (0.6, 0.36, 0.42), (0.45, 0.25, 0.21), "road_paint_grey", bevel=0.015, patches=0.6)
    lid = K.box("battery_lid", (0.62, 0.38, 0.03), center=(0, 0, 0), bevel=0.006)
    if ctx.worn:
        K.place(lid, (0, 0, 0), (-75, 0, 0))
        K.place(lid, (0.45, 0.07, 0.42))
    else:
        K.place(lid, (0.45, 0.25, 0.435))
    ctx.add(lid, "road_paint_grey", uv="box", uv_scale=2.0, patches=0.6)


def w4_bunker_chicken_coop(ctx: K.Ctx) -> None:
    """A board chicken coop on four legs with a tin lean-to roof, a nest box, a cleated ramp down to a chicken
    wire run beside it and a feeder can. Worn: the wire torn open and feathers in the run."""
    r = ctx.drnd("coop")
    # The coop box on the left half, the run on the right.
    cx, cw, cd, c0, ch = -0.45, 1.1, 1.2, 0.45, 0.75
    for sx in (-1, 1):
        for sy in (-1, 1):
            _bx(ctx, f"leg{sx}{sy}", (0.07, 0.07, c0 + ch + 0.1), (cx + sx * (cw / 2 - 0.04), sy * (cd / 2 - 0.04), (c0 + ch + 0.1) / 2),
                "wood_weathered", bevel=0.003)
    box = K.box("coop", (cw, cd, ch), center=(cx, 0, c0 + ch / 2), bevel=0.01, cuts=(3, 3, 2))
    ctx.add(box, "farm_wood_barn_red", uv="box", uv_scale=1.0, patches=0.7, moss=0.2)
    _bx(ctx, "door", (0.3, 0.02, 0.32), (cx + 0.25, -cd / 2 - 0.01, c0 + 0.2), "wood_weathered")
    nest = K.box("nest", (0.4, 0.36, 0.3), center=(cx - cw / 2 - 0.12, 0, c0 + 0.3), bevel=0.01)
    ctx.add(nest, "farm_wood_barn_red", uv="box", uv_scale=1.0, patches=0.7)
    roof = K.box("roof", (cw + 0.4, cd + 0.24, 0.02), center=(0, 0, 0))
    K.place(roof, (0, 0, 0), (0, -14, 0))
    K.place(roof, (cx - 0.1, 0, c0 + ch + 0.12))
    ctx.add(roof, "farm_corrugated_galv" if not ctx.worn else "farm_corrugated_rust", uv="box", uv_scale=1.0, patches=0.6)
    # Ramp from the pop hole into the run.
    ramp = P.plank("ramp", 0.7, 0.2, 0.02)
    K.place(ramp, (0, 0, 0), (0, 30, 0))
    K.place(ramp, (cx + cw / 2 + 0.28, 0.0, c0 * 0.5))
    ctx.add(ramp, "wood_weathered", long_axis=0, patches=0.6)
    # The run: a pole frame with chicken wire.
    rx0, rx1, rd, rh = cx + cw / 2, 1.2, 0.76, 1.0
    for x in (rx0 + 0.02, rx1):
        for sy in (-1, 1):
            W.rod(ctx, f"rpost{x}{sy}", (x, sy * rd, 0.0), (x, sy * rd, rh), 0.025, "out_log_peeled", segs=6)
    for sy in (-1, 1):
        W.rod(ctx, f"rtop{sy}", (rx0, sy * rd, rh), (rx1, sy * rd, rh), 0.02, "out_log_peeled", segs=6)
    W.rod(ctx, "rtop_end", (rx1, -rd, rh), (rx1, rd, rh), 0.02, "out_log_peeled", segs=6)
    walls = [
        ((rx0, -rd, 0.0), (rx1, -rd, 0.0), (rx1, -rd, rh), (rx0, -rd, rh)),
        ((rx1, -rd, 0.0), (rx1, rd, 0.0), (rx1, rd, rh), (rx1, -rd, rh)),
        ((rx1, rd, 0.0), (rx0, rd, 0.0), (rx0, rd, rh), (rx1, rd, rh)),
    ]
    for k, q in enumerate(walls):
        sh = K.quad_sheet(f"wire{k}", *q, 6, 4)
        if ctx.worn and k == 0:
            K.delete_faces(sh, lambda c, n: c.z < 0.6 and c.x > rx0 + 0.3)
        ctx.add(sh, "farm_chicken_wire", uv="box", uv_scale=1.0, ao=False)
    _cy(ctx, "feeder", 0.12, 0.3, (rx1 - 0.3, 0.3, 0.15), GALV, segs=14)
    if ctx.worn:
        for k in range(10):
            f = K.box(f"feather{k}", (0.06, 0.02, 0.003), center=(0, 0, 0))
            K.place(f, (r.uniform(rx0 + 0.1, rx1 - 0.1), r.uniform(-rd + 0.1, rd - 0.1), 0.004), (0, 0, r.uniform(0, 180)))
            ctx.add(f, "farm_feathers", uv="box", uv_scale=8.0, ao=False)


def w4_bunker_rain_barrel(ctx: K.Ctx) -> None:
    """An oak rain barrel on two cinder blocks: hoops, a fly screen over its open head, a brass spigot near the
    foot and a galvanized watering can beside it. Worn: the screen torn, a hoop slipped."""
    blk = 0.2
    for sx in (-1, 1):
        _bx(ctx, f"block{sx}", (0.2, 0.4, blk), (sx * 0.13, 0.0, blk / 2), "concrete_barrier", bevel=0.005)
    prof = [(0.0, 0.0), (0.24, 0.0), (0.27, 0.15), (0.29, 0.42), (0.27, 0.7), (0.24, 0.84), (0.21, 0.84), (0.0, 0.8)]
    bar = K.lathe("barrel", prof, segs=20)
    K.place(bar, (0, 0, blk))
    ctx.add(bar, "wood_stained", uv="cyl", uv_axis=2, smooth=40, patches=0.6, moss=0.3)
    for k, z in enumerate((0.1, 0.32, 0.52 if not ctx.worn else 0.47, 0.74)):
        rr = 0.255 + 0.035 * math.sin(min(z / 0.84, 1.0) * math.pi)
        hp = K.cyl(f"hoop{k}", rr + 0.006, 0.035, segs=20, center=(0, 0, blk + z), caps=False)
        ctx.add(hp, "road_rust", uv="box", uv_scale=3.0, smooth=40)
    scr = K.grid("screen", 0.42, 0.42, 3, 3, center=(0, 0, blk + 0.83))
    if ctx.worn:
        K.delete_faces(scr, lambda c, n: c.x > 0.05 and c.y < 0.0)
    ctx.add(scr, "farm_chicken_wire", uv="box", uv_scale=2.0, ao=False)
    W.rod(ctx, "spigot", (0, -0.26, blk + 0.12), (0, -0.33, blk + 0.12), 0.012, "road_brass", segs=6)
    W.rod(ctx, "spigot_tap", (0, -0.32, blk + 0.12), (0, -0.32, blk + 0.17), 0.006, "road_brass", segs=4)
    can = K.lathe("can", [(0.0, 0.0), (0.09, 0.0), (0.09, 0.24), (0.06, 0.26), (0.0, 0.26)], segs=12)
    K.place(can, (0.18, -0.2, 0.0))
    ctx.add(can, GALV, uv="cyl", uv_axis=2, smooth=40, patches=0.5)
    W.rod(ctx, "can_spout", (0.2, -0.27, 0.06), (0.22, -0.34, 0.25), 0.01, GALV, segs=6)


def w4_bunker_woodshed(ctx: K.Ctx) -> None:
    """An open-fronted pole woodshed, 3 x 1.8 m: four peeled posts, a tin lean-to roof sloping to the back, a
    board back wall and split firewood stacked to the rafters on a pallet floor, a maul leant on the end post.
    Worn: half the wood burnt through the winter, the roof rusted."""
    r = ctx.rnd("shed")
    Wd, D = 2.9, 1.6
    hf, hb = 2.35, 1.95
    hw, hd = Wd / 2, D / 2
    for sx in (-1, 1):
        W.rod(ctx, f"post_f{sx}", (sx * hw, -hd, 0.0), (sx * hw, -hd, hf), 0.06, "out_log_peeled", segs=8)
        W.rod(ctx, f"post_b{sx}", (sx * hw, hd, 0.0), (sx * hw, hd, hb), 0.06, "out_log_peeled", segs=8)
        W.rod(ctx, f"rafter{sx}", (sx * hw, -hd - 0.1, hf), (sx * hw, hd + 0.1, hb), 0.045, "out_log_peeled", segs=6)
    W.rod(ctx, "plate_f", (-hw - 0.1, -hd, hf - 0.03), (hw + 0.1, -hd, hf - 0.03), 0.05, "out_log_peeled", segs=6)
    W.rod(ctx, "plate_b", (-hw - 0.1, hd, hb - 0.03), (hw + 0.1, hd, hb - 0.03), 0.05, "out_log_peeled", segs=6)
    slope = math.degrees(math.atan2(hf - hb, D))
    roof = K.box("roof", (Wd + 0.1, D + 0.2, 0.02), center=(0, 0, 0), cuts=(3, 2, 0))
    K.place(roof, (0, 0, 0), (-slope, 0, 0))
    K.place(roof, (0, 0, (hf + hb) / 2 + 0.06))
    ctx.add(roof, "farm_corrugated_rust" if ctx.worn else "farm_corrugated_galv", uv="box", uv_scale=1.0, patches=0.6)
    for k in range(9):
        z = 0.1 + k * 0.2
        ctx.add(P.plank(f"back{k}", Wd, 0.18, 0.025), "wood_weathered", long_axis=0, patches=0.6, moss=0.3,
                at=((0, hd + 0.03, z), (90, 0, 0)))
    for k in range(5):
        ctx.add(P.plank(f"floor{k}", Wd - 0.1, 0.12, 0.03), "wood_weathered", long_axis=0, patches=0.6,
                at=((0, -hd + 0.2 + k * 0.3, 0.05), (0, 0, 0)))
    # Split wood: rows of half-logs end-on to the front.
    top = 1.1 if ctx.worn else 1.85
    logs = []
    z = 0.12
    row = 0
    while z < top:
        x = -hw + 0.12 + (0.06 if row % 2 else 0.0)
        while x < hw - 0.1:
            if not (ctx.worn and x > 0.4 and z > 0.6):
                lg = P.log_split(f"w{row}_{len(logs)}", D - 0.25, r.uniform(0.07, 0.09), r, kind="half", segs=6)
                K.place(lg, (0, 0, 0), (r.uniform(-4, 4), 0, 90 + r.uniform(-3, 3)))
                K.place(lg, (x, 0.05, z + 0.07))
                logs.append(lg)
            x += 0.18
        z += 0.16
        row += 1
    if logs:
        ctx.add(K.merge_parts(logs, "woodstack"), "bark_firewood", uv="box", uv_scale=2.0, patches=0.5)
    W.rod(ctx, "maul_handle", (hw + 0.12, -hd - 0.05, 0.02), (hw + 0.05, -hd - 0.15, 0.85), 0.017, "item_wood_handle", segs=6)
    _bx(ctx, "maul_head", (0.08, 0.2, 0.08), (hw + 0.05, -hd - 0.15, 0.88), "road_steel_dark", bevel=0.01)


def w4_bunker_map_wall(ctx: K.Ctx) -> None:
    """Map sheets pinned edge to edge on a cork board (origin on the wall plane, bottom centre, out toward -Y):
    topographic sheets, the roads off the mountain struck through in red string pinned between checkpoints,
    a frequency list down the margin. Worn: a sheet peeled and hanging."""
    r = ctx.rnd("map")
    Wd, H, T = 1.6, 1.1, 0.025
    _bx(ctx, "board", (Wd, T, H), (0, -T / 2, H / 2), "furn_cork", bevel=0.004, uv_scale=2.0)
    for sx in (-1, 1):
        _bx(ctx, f"frame_v{sx}", (0.03, T + 0.01, H), (sx * (Wd / 2 - 0.015), -T / 2 - 0.005, H / 2), "wood_stained", bevel=0.003)
    for sz in (0, 1):
        _bx(ctx, f"frame_h{sz}", (Wd, T + 0.01, 0.03), (0, -T / 2 - 0.005, 0.015 + sz * (H - 0.03)), "wood_stained", bevel=0.003)
    sheets = [(-0.38, 0.6, 0.62, 0.86), (0.25, 0.6, 0.62, 0.86)]
    for k, (x, z, w, h) in enumerate(sheets):
        sh = K.quad_sheet(f"sheet{k}", (x - w / 2, 0, z - h / 2), (x + w / 2, 0, z - h / 2), (x + w / 2, 0, z + h / 2),
                          (x - w / 2, 0, z + h / 2), 3, 3)
        K.place(sh, (0, -T - 0.002 - k * 0.001, 0))
        if ctx.worn and k == 1:
            for v in sh.data.vertices:
                if v.co.z < z - h * 0.1:
                    t = (z - h * 0.1 - v.co.z) / (h * 0.4)
                    v.co.y -= 0.06 * t * t
        ctx.add(sh, "wild_map_disc", uv="planar", uv_axis=1, uv_scale=0.8, smooth=40, patches=0.3, ao=False)
    _bx(ctx, "freqs", (0.12, 0.002, 0.5), (Wd / 2 - 0.1, -T - 0.002, 0.55), "item_paper_ledger", bevel=0.0, ao=False)
    # Red strings between pins: the closed roads.
    pins = [Vector((r.uniform(-0.65, 0.55), -T - 0.012, r.uniform(0.25, 1.0))) for _ in range(7)]
    for k, p in enumerate(pins):
        _cy(ctx, f"pin{k}", 0.008, 0.02, tuple(p), "plastic_red", axis="Y", segs=6)
    for k in range(0, len(pins) - 1, 2):
        W.rod(ctx, f"string{k}", pins[k], pins[k + 1], 0.002, "paint_red", segs=4)
    for k in range(3):
        x, z = r.uniform(-0.6, 0.4), r.uniform(0.3, 0.95)
        W.rod(ctx, f"cross_a{k}", (x - 0.04, -T - 0.004, z - 0.04), (x + 0.04, -T - 0.004, z + 0.04), 0.003, "paint_red", segs=4)
        W.rod(ctx, f"cross_b{k}", (x - 0.04, -T - 0.004, z + 0.04), (x + 0.04, -T - 0.004, z - 0.04), 0.003, "paint_red", segs=4)


BUILDERS = {
    "w4_bunker_air_filter": w4_bunker_air_filter,
    "w4_bunker_generator": w4_bunker_generator,
    "w4_bunker_water_drum": w4_bunker_water_drum,
    "w4_bunker_decon_shower": w4_bunker_decon_shower,
    "w4_bunker_radio_desk": w4_bunker_radio_desk,
    "w4_bunker_solar_pole": w4_bunker_solar_pole,
    "w4_bunker_chicken_coop": w4_bunker_chicken_coop,
    "w4_bunker_shelf_cans": w4_bunker_shelf_cans,
    "w4_bunker_rain_barrel": w4_bunker_rain_barrel,
    "w4_bunker_woodshed": w4_bunker_woodshed,
    "w4_bunker_map_wall": w4_bunker_map_wall,
}


def build(params: dict, outputs: list[str]) -> None:
    K.run(params, outputs, BUILDERS)
