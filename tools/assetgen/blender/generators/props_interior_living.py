"""Interior props - living room: floral sofa + armchair, velour recliner, oak coffee / end tables, CRT TV on
a stand, bookshelf with books, floor lamp, braided oval rug and rectangular area rug.

params: prop (id), seed, variants, mount, budget (see blender_catalogs/props_interior.py).
"""
from __future__ import annotations

import math

from lib import props_int_core as core
from lib import props_int_furn as F
from lib import props_int_mesh as G
from lib.props_int_core import M, Prop


# ------------------------------------------------------------------------------------------------
# upholstery helpers
# ------------------------------------------------------------------------------------------------


def _sofa(p: Prop, seats: int, fabric: str, *, W: float | None = None) -> dict:
    """Rolled-arm upholstered sofa / armchair. Seat 0.46, arms 0.63, back 0.88. Returns part groups."""
    cw = 0.6 if seats > 1 else 0.58
    arm_w = 0.21
    W = W or seats * cw + 2 * arm_w
    D = 0.9
    y0, y1 = -D / 2, D / 2
    deck = 0.33
    parts: dict = {"feet": [], "seat": [], "back": [], "arms": []}
    wr = 0.003 if p.cond == "clean" else 0.006
    # base / deck with welt
    parts["base"] = p.rbox((W - 0.02, D - 0.06, deck - 0.1), (0, 0.01, 0.1 + (deck - 0.1) / 2), fabric, radius=0.03,
                           inner=(5, 2, 1), bulge=(0, 0.01, 0), wrinkle=wr * 0.5, seed=p.seed + 3)
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts["feet"].append(F.bun_foot(p, sx * (W / 2 - 0.08), sy * (D / 2 - 0.1), key=f"foot{sx}{sy}"))
    # rolled arms
    for sx in (-1, 1):
        arm = p.rbox((arm_w, D - 0.02, 0.53), (sx * (W / 2 - arm_w / 2), 0.0, 0.1 + 0.265), fabric, radius=0.085,
                     inner=(1, 4, 2), bulge=(0.012, 0, 0.01), wrinkle=wr, seed=p.seed + 10 + sx)
        parts["arms"].append(arm)
    # back frame (raked)
    back = p.rbox((W - 0.02, 0.22, 0.6), (0, y1 - 0.12, 0.3 + 0.3), fabric, radius=0.06, inner=(5, 1, 2),
                  bulge=(0, 0.01, 0.02), wrinkle=wr, seed=p.seed + 20)
    G.xform(back.obj, rot=(-6, 0, 0), pivot=(0, y1 - 0.12, 0.3))
    parts["back_frame"] = back
    inner_w = W - 2 * arm_w
    sw = inner_w / seats
    for i in range(seats):
        cx = -inner_w / 2 + sw * (i + 0.5)
        sag = 0.0 if p.cond == "clean" else p.vrng(f"sag{i}").uniform(0.01, 0.03)
        cush = p.rbox((sw - 0.005, 0.66, 0.15), (cx, -0.07, deck + 0.075), fabric, radius=0.045, inner=(3, 3, 1),
                      bulge=(0.006, 0.01, 0.016), sag=sag, sag_at=(0, 0.05), sag_r=0.2, wrinkle=wr,
                      seed=p.seed + 30 + i, tags=("cushion",))
        parts["seat"].append(cush)
        bc = p.rbox((sw - 0.01, 0.2, 0.44), (cx, y1 - 0.25, deck + 0.15 + 0.2), fabric, radius=0.07, inner=(3, 1, 3),
                    bulge=(0, 0.035, 0.01), wrinkle=wr * 1.4, seed=p.seed + 40 + i, tags=("cushion",))
        G.xform(bc.obj, rot=(-12, 0, 0), pivot=(cx, y1 - 0.25, deck + 0.15))
        parts["back"].append(bc)
    if p.worn:
        # shifted cushions, a throw pillow and an afghan over one arm
        r = p.vrng("mess")
        for i, cush in enumerate(parts["seat"]):
            p.move([cush], (r.uniform(-0.02, 0.02), r.uniform(-0.05, 0.01), 0))
            p.rotate([cush], rot=(0, 0, r.uniform(-3, 3)), pivot=(0, 0, 0))
        pil = p.rbox((0.4, 0.13, 0.38), (0, 0, 0), M.BROWN, radius=0.06, inner=(2, 1, 2), bulge=(0, 0.04, 0),
                     taper_top=0.05, wrinkle=0.004, seed=p.seed + 50, tags=("cushion",))
        G.xform(pil.obj, rot=(-25, 0, 35 if seats > 1 else 15), loc=(-inner_w / 2 + 0.22, 0.05, deck + 0.3))
        parts["pillow"] = pil
    return {**parts, "W": W, "D": D, "deck": deck, "inner_w": inner_w}


def _wreck_sofa(p: Prop, parts: dict, seats: int) -> None:
    r = p.vrng("wreck")
    W, deck = parts["W"], parts["deck"]
    # one seat cushion dragged onto the floor, a back cushion fallen forward onto the deck
    k = r.randrange(len(parts["seat"]))
    cush = parts["seat"][k]
    p.lay_on_floor([cush], rot=(r.uniform(-6, 6), r.uniform(-8, 8), 0), at=(r.uniform(-0.4, 0.4), -0.95),
                   yaw=r.uniform(-30, 30))
    bk = parts["back"][(k + 1) % len(parts["back"])]
    p.rotate([bk], rot=(50, 0, r.uniform(-10, 10)), pivot=(0, 0.2, deck + 0.15))
    p.move([bk], (0, -0.12, -0.08))
    # slash the cushions (where they now lie) and some back cushions
    for i, c_ in enumerate(parts["seat"]):
        lo, hi = p.bounds([c_])
        c = ((lo.x + hi.x) / 2 + r.uniform(-0.08, 0.08), (lo.y + hi.y) / 2 + r.uniform(-0.12, 0.08), hi.z - 0.012)
        F.slash(p, c, r.uniform(0.18, 0.3), r.uniform(-50, 50), key=f"seatslash{i}")
    n_back = 0
    for i, bc in enumerate(parts["back"]):
        if bc is not bk and n_back < 2 and r.random() < 0.7:
            n_back += 1
            lo, hi = p.bounds([bc])
            F.slash(p, ((lo.x + hi.x) / 2, lo.y + 0.03, (lo.z + hi.z) / 2 + 0.05), r.uniform(0.15, 0.25),
                  r.uniform(-60, 60), up=(0, -1, 0), key=f"backslash{i}")
    # stuffing tufts on the floor
    for i in range(3):
        F.stuffing(p, (r.uniform(-W / 2, W / 2), -0.6 - r.uniform(0, 0.5), 0.02), r.uniform(0.06, 0.12), key=f"tuft{i}")
    # snapped front foot: sofa slumps toward that corner
    foot = parts["feet"][0]
    F.break_off(p, foot, 0.055, jag=0.012, key="footbreak", keep_piece=False)
    body = [q for q in p.parts if "debris" not in q.tags and q is not cush and p.bounds([q])[0].y > -0.62]
    p.settle(body, pivot=(W / 2 - 0.08, 0.0, 0.0), axis=(-0.6, 1.0, 0.0), max_deg=4)


def couch(p: Prop) -> None:
    parts = _sofa(p, 3, M.FLORAL)
    if p.destroyed:
        _wreck_sofa(p, parts, 3)
        p.collider((0, 0.0, 0.44), (parts["W"], 0.9, 0.88))
        p.collider((0, -0.95, 0.08), (0.7, 0.7, 0.16))
    else:
        p.collider((0, 0.0, 0.25), (parts["W"], 0.9, 0.5))
        p.collider((0, 0.33, 0.6), (parts["W"], 0.24, 0.56))


def armchair(p: Prop) -> None:
    parts = _sofa(p, 1, M.FLORAL)
    if p.destroyed:
        _wreck_sofa(p, parts, 1)
        p.collider((0, 0.0, 0.44), (parts["W"], 0.9, 0.88))
    else:
        p.collider((0, 0.0, 0.25), (parts["W"], 0.9, 0.5))
        p.collider((0, 0.33, 0.6), (parts["W"], 0.24, 0.56))


def recliner(p: Prop) -> None:
    """Early-90s velour recliner: pillow arms, three-tier waterfall back, seat cushion, folded footrest."""
    fab = M.TAN
    W, D = 0.92, 0.95
    wr = 0.003 if p.cond == "clean" else 0.007
    p.rbox((W - 0.04, D - 0.1, 0.24), (0, 0.02, 0.14), fab, radius=0.03, inner=(3, 3, 1), wrinkle=wr * 0.4,
                  seed=p.seed)
    p.box((W - 0.12, D - 0.2, 0.03), (0, 0.04, 0.015), M.PL_BLACK, bevel=0.004)
    arms = []
    for sx in (-1, 1):
        arms.append(p.rbox((0.2, D - 0.05, 0.42), (sx * (W / 2 - 0.1), 0.0, 0.03 + 0.21 + 0.18), fab, radius=0.09,
                           inner=(1, 4, 2), bulge=(0.02, 0, 0.02), wrinkle=wr, seed=p.seed + sx))
    p.rbox((W - 0.4, 0.66, 0.16), (0, -0.07, 0.4 + 0.08), fab, radius=0.05, inner=(2, 3, 1), bulge=(0, 0.01, 0.02),
                  sag=0.0 if p.cond == "clean" else 0.03, sag_at=(0, 0.05), sag_r=0.2, wrinkle=wr, seed=p.seed + 3,
                  tags=("cushion",))
    back = []
    recl = 0.0 if not p.destroyed else 22.0
    for i in range(3):
        z = 0.5 + i * 0.19
        bc = p.rbox((W - 0.36, 0.22 - i * 0.02, 0.21), (0, D / 2 - 0.16 + i * 0.015, z + 0.1), fab, radius=0.08,
                    inner=(2, 1, 1), bulge=(0, 0.04, 0.02), wrinkle=wr, seed=p.seed + 10 + i, tags=("cushion", "back"))
        back.append(bc)
    bframe = p.rbox((W - 0.2, 0.16, 0.66), (0, D / 2 - 0.06, 0.48 + 0.33), fab, radius=0.07, inner=(3, 1, 2),
                    wrinkle=wr, seed=p.seed + 20, tags=("back",))
    back.append(bframe)
    for q in back:
        G.xform(q.obj, rot=(-8 - recl, 0, 0), pivot=(0, D / 2 - 0.2, 0.45))
    # footrest: folded under the seat front (clean) / half out (worn) / hanging loose (destroyed)
    foot = p.rbox((W - 0.4, 0.07, 0.3), (0, -D / 2 + 0.035, 0.2), fab, radius=0.03, inner=(2, 1, 2), wrinkle=wr,
                  seed=p.seed + 30, tags=("footrest",))
    lever = p.box((0.02, 0.12, 0.03), (W / 2 + 0.01, -0.12, 0.35), M.DARK, bevel=0.006, tags=("knob",))
    if p.cond == "worn":
        p.rotate([foot], rot=(-55, 0, 0), pivot=(0, -D / 2 + 0.035, 0.36))
        p.move([foot], (0, -0.05, 0.0))
    if p.destroyed:
        r = p.vrng("wreck")
        p.rotate([foot], rot=(-95, 0, 8), pivot=(0, -D / 2 + 0.035, 0.36))
        p.move([foot], (0, -0.12, -0.05))
        F.slash(p, (0.0, -0.1, 0.565), 0.3, 35, key="seat")
        lo, hi = p.bounds([back[1]])
        F.slash(p, ((lo.x + hi.x) / 2, lo.y + 0.03, (lo.z + hi.z) / 2), 0.25, -20, up=(0, -1, 0), key="back")
        for i in range(3):
            F.stuffing(p, (r.uniform(-0.4, 0.4), -0.7 - r.uniform(0, 0.3), 0.02), r.uniform(0.05, 0.1), key=f"tuft{i}")
        p.remove([lever])
    p.collider((0, 0.0, 0.28), (W, D, 0.56))
    p.collider((0, D / 2 - 0.12, 0.75), (W, 0.25, 0.6))


# ------------------------------------------------------------------------------------------------
# tables
# ------------------------------------------------------------------------------------------------


def _magazines(p: Prop, c, n: int, key: str) -> None:
    r = p.rng(key)
    for i in range(n):
        m = p.box((0.21, 0.28, 0.004), (0, 0, 0), M.CARDBOARD, bevel=0.0, uv="keep", tags=("paper",))
        cell = r.randrange(14)
        core.set_face_uvs(m.obj, lambda poly, k=cell: (*core.card_rect(k), 0, 1, False) if abs(poly.normal.z) > 0.9
                          else (*core.card_rect(14), 0, 2, False))
        G.xform(m.obj, rot=(0, 0, r.uniform(-25, 25)), loc=(c[0] + r.uniform(-0.03, 0.03), c[1] + r.uniform(-0.03, 0.03),
                                                           c[2] + 0.002 + i * 0.0045))


def coffee_table(p: Prop) -> None:
    """Oak coffee table 1.1 x 0.6 x 0.45 with a lower shelf and tapered legs."""
    W, D, H, T = 1.1, 0.6, 0.45, 0.028
    lx, ly = W / 2 - 0.06, D / 2 - 0.06
    top_poly = F.rounded_rect(W, D, 0.03)
    legs = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            legs.append(F.tapered_leg(p, sx * lx, sy * ly, 0.0, H - T, 0.05, 0.032, M.OAK, key=f"leg{sx}{sy}"))
    aprons = []
    for sy in (-1, 1):
        aprons.append(p.box((2 * lx - 0.05, 0.02, 0.07), (0, sy * (ly - 0.004), H - T - 0.035), M.OAK, bevel=0.002, grain="X"))
    for sx in (-1, 1):
        aprons.append(p.box((0.02, 2 * ly - 0.05, 0.07), (sx * (lx - 0.004), 0, H - T - 0.035), M.OAK, bevel=0.002, grain="Y"))
    p.box((2 * lx - 0.04, 2 * ly - 0.04, 0.018), (0, 0, 0.1), M.OAK, bevel=0.002, grain="X")
    if not p.destroyed:
        p.prism(top_poly, T, M.OAK, plane="XY", offset=H - T, bevel=0.004, grain="X")
        if p.worn:
            _magazines(p, (-0.25, 0.02, H), 3, "mags")
            _magazines(p, (0.1, 0.0, 0.109), 4, "mags2")
            p.box((0.05, 0.17, 0.022), (0.3, -0.1, H + 0.011), M.PL_BLACK, bevel=0.006)  # remote
            p.lathe([(0.034, 0.0), (0.038, 0.095), (0.034, 0.095), (0.031, 0.008), (0.0, 0.008)], (0.38, 0.12, H),
                    M.CERAMIC, segs=12, cap_top=False)
        p.collider((0, 0, H / 2), (W, D, H))
        return
    # destroyed: top split lengthwise, one half dropped onto the shelf, a leg snapped
    r = p.vrng("wreck")
    a, b = (-0.08, -D / 2), (0.12, D / 2)
    h1, h2 = F.split_panel(p, W, D, T, (0, 0, H - T / 2), M.OAK, a, b, plane="XY", inner=M.WOOD_RAW, teeth=9, amp=0.03,
                           key="top")
    # smashed in the middle: both halves fold into a V, their broken edges resting on the lower shelf
    for half, ang in ((h1, 14.0), (h2, 11.0)):
        lo, hi = p.bounds([half])
        left = (lo.x + hi.x) / 2 < 0
        end = -W / 2 if left else W / 2
        p.rotate([half], rot=(0, ang if left else -ang, 0), pivot=(end, 0, H - T))
    F.break_off(p, legs[2], 0.16, jag=0.02, key="legb", piece_at=(0.8, -0.35), piece_yaw=r.uniform(0, 180))
    p.collider((0, 0, H / 2), (W, D, H))


def side_table(p: Prop) -> None:
    """Oak end table 0.55 x 0.55 x 0.6: drawer, lower shelf, turned legs."""
    W, D, H, T = 0.55, 0.55, 0.6, 0.025
    lx = W / 2 - 0.045
    legs = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            legs.append(F.turned_leg(p, sx * lx, sy * lx, 0.0, H - T, 0.024, M.OAK, key=f"leg{sx}{sy}", segs=8))
    p.prism(F.rounded_rect(W, D, 0.02, 3), T, M.OAK, plane="XY", offset=H - T, bevel=0.004, grain="X")
    p.box((2 * lx - 0.04, 2 * lx - 0.04, 0.016), (0, 0, 0.14), M.OAK, bevel=0.002, grain="X")
    for sx in (-1, 1):
        p.box((0.018, 2 * lx - 0.04, 0.11), (sx * (lx - 0.003), 0, H - T - 0.055), M.OAK, bevel=0.002, grain="Y")
    p.box((2 * lx - 0.04, 0.018, 0.11), (0, lx - 0.003, H - T - 0.055), M.OAK, bevel=0.002, grain="X")
    pull = 0.0 if p.cond == "clean" else p.vrng("drawer").choice([0.0, 0.04, 0.08])
    drw = F.drawer(p, -lx + 0.02, H - T - 0.105, lx - 0.02, H - T - 0.008, -lx - 0.009, 0.38, M.OAK, pull=pull,
                   frame=0.025, key="drawer", style="raised")
    if p.worn and not p.destroyed:
        # lamp-less doily + ashtray
        p.cyl(0.13, 0.002, (0.02, 0.0, H + 0.001), M.LINEN, segs=16, uv="box")
        p.lathe([(0.06, 0.0), (0.065, 0.018), (0.055, 0.02), (0.045, 0.006), (0.0, 0.006)], (0.1, -0.08, H + 0.002),
                M.GLASS, segs=12, cap_top=False)
    if p.destroyed:
        r = p.vrng("wreck")
        p.remove(drw)
        F.break_off(p, legs[1], 0.25, jag=0.02, key="legb", piece_at=(0.5, -0.3), piece_yaw=r.uniform(0, 180))
        whole = [q for q in p.parts if "debris" not in q.tags]
        p.rotate(whole, rot=(0, -90, 0), pivot=(0, 0, 0))
        lo, hi = p.bounds(whole)
        p.move(whole, (-lo.x - 0.3 + 0.0, 0, -lo.z))
        p.rotate(whole, rot=(0, 0, r.uniform(-20, 20)), pivot=(0, 0, 0))
        dr = F.drawer(p, -0.21, 0.0, 0.21, 0.09, 0.0, 0.3, M.OAK, pull=0.01, frame=0.025, key="drawer2", style="raised")
        p.lay_on_floor(dr, rot=(0, 180, 0), at=(0.45, -0.25), yaw=r.uniform(0, 60))
        p.collider((0, 0, 0.28), (0.65, 0.6, 0.56))
    else:
        p.collider((0, 0, H / 2), (W, D, H))


# ------------------------------------------------------------------------------------------------
# TV, bookshelf, lamp, rugs
# ------------------------------------------------------------------------------------------------


def tv_crt(p: Prop) -> None:
    """27-inch CRT television on a woodgrain-laminate stand with a VCR and tapes; rabbit-ear antenna."""
    SW, SD, SH = 0.86, 0.45, 0.5
    # stand
    F.carcass(p, SW, -SD / 2, SD / 2, 0.04, SH, M.LAM_WOOD, frame=False, back=True, top=True, t=0.02,
                   inner=M.LAM_WOOD)
    p.box((SW - 0.06, SD - 0.06, 0.04), (0, 0.0, 0.02), M.PL_BLACK, bevel=0.003)
    p.box((SW - 0.04, SD - 0.05, 0.018), (0, 0.01, 0.25), M.LAM_WOOD, bevel=0.002, grain="X")
    p.box((0.42, 0.3, 0.09), (-0.15, 0.0, 0.25 + 0.009 + 0.045), M.PL_BLACK, bevel=0.004)  # VCR
    p.box((0.2, 0.004, 0.012), (-0.15, -0.151, 0.31), M.PL_GREY, bevel=0.0)
    p.box((0.08, 0.004, 0.02), (-0.02, -0.151, 0.3), M.GLASS, bevel=0.0)
    r = p.rng("tapes")
    for i in range(6):
        F.package_box(p, (0.025, 0.19, 0.105), (0.16 + i * 0.027, 0.0, 0.25 + 0.009 + 0.0525), r.randrange(14))
    for i in range(3):
        F.package_box(p, (0.19, 0.105, 0.025), (0.24, -0.03, 0.06 + 0.0125 + i * 0.026), r.randrange(14),
                      rot=(0, 0, r.uniform(-8, 8)))
    # television
    ty = -0.02
    z0 = SH
    tv = []
    tv.append(p.rbox((0.7, 0.3, 0.54), (0, ty - 0.03, z0 + 0.27), M.PL_BLACK, radius=0.025, inner=(3, 1, 3), edge_deg=30))
    rear = p.lathe([(0.0, 0.0), (0.27, 0.0), (0.2, 0.16), (0.08, 0.22), (0.0, 0.225)], (0, ty + 0.11, z0 + 0.27),
                   M.PL_BLACK, segs=4, axis="Y", cap_bottom=False)
    G.xform(rear.obj, rot=(0, 45, 0), pivot=(0, ty + 0.11, z0 + 0.27))
    tv.append(rear)
    yb = ty - 0.18
    tv.append(p.box((0.62, 0.02, 0.44), (-0.02, yb + 0.01, z0 + 0.29), M.PL_GREY, bevel=0.012, segs=2))
    screen_c = (-0.04, yb - 0.004, z0 + 0.3)
    if p.destroyed:
        tv.append(p.box((0.5, 0.01, 0.37), (screen_c[0], yb + 0.03, screen_c[2]), M.PL_BLACK, bevel=0.0))
        tv += F.shatter_pane(p, 0.5, 0.37, (screen_c[0], yb - 0.002, screen_c[2]), M.CRT, t=0.006, impact=(0.04, -0.03),
                             spokes=11, rings=3, key="screen", missing_inner=0.95, missing_outer=0.25, floor_shards=6,
                             floor_at=(0.0, -0.75))
    else:
        scr = p.rbox((0.5, 0.03, 0.37), screen_c, M.CRT, radius=0.02, inner=(4, 1, 3), bulge=(0, 0.018, 0), uv="planar",
                     uv_axis="Y", edge_deg=40)
        tv.append(scr)
    for i in range(4):
        tv.append(p.box((0.022, 0.006, 0.012), (0.29, yb - 0.003, z0 + 0.45 - i * 0.03), M.PL_GREY, bevel=0.001,
                        tags=("knob",)))
    for i in range(7):
        tv.append(p.box((0.04, 0.004, 0.006), (0.29, yb - 0.001, z0 + 0.2 - i * 0.016), M.PL_BLACK, bevel=0.0))
    # rabbit ears
    ant = [p.cyl(0.035, 0.03, (0.0, ty + 0.06, z0 + 0.555), M.PL_BLACK, segs=10)]
    for sx in (-1, 1):
        a = p.cyl(0.003, 0.5, (0, 0, 0.25), M.CHROME, segs=5)
        G.xform(a.obj, rot=(0, sx * 28, sx * 10), loc=(sx * 0.01, ty + 0.06, z0 + 0.565))
        ant.append(a)
    tv += ant
    if p.cond == "worn":
        p.rotate(tv, rot=(0, 0, p.vrng("tv").uniform(-6, 6)), pivot=(0, 0, z0))
    if p.destroyed:
        r = p.vrng("wreck")
        p.rotate(tv, rot=(0, 0, r.uniform(8, 16)), pivot=(0, 0, z0))
        p.move(tv, (0.06, -0.04, 0))
        p.rotate(ant[1:], rot=(0, 40, 0), pivot=(0, ty + 0.06, z0 + 0.565))
    p.collider((0, 0, SH / 2), (SW, SD, SH))
    p.collider((0, 0.0, SH + 0.28), (0.72, 0.5, 0.56))


def bookshelf(p: Prop) -> None:
    """Dark-wood bookcase 0.9 x 0.3 x 1.8 with five shelves of books."""
    W, D, H = 0.9, 0.3, 1.8
    wood = M.DARK
    car = F.carcass(p, W, -D / 2, D / 2, 0.0, H, wood, frame=False, back=True, top=True, bottom=True, t=0.02, inner=wood)
    p.box((W - 0.04, 0.02, 0.07), (0, -D / 2 + 0.01, 0.035), wood, bevel=0.002, grain="X")
    p.box((W + 0.02, D + 0.02, 0.025), (0, 0.0, H - 0.0125), wood, bevel=0.004, grain="X")
    shelves = []
    zs = [0.07, 0.43, 0.77, 1.1, 1.43]
    for z in zs[1:]:
        shelves.append(p.box((W - 0.04, D - 0.02, 0.02), (0, 0.005, z - 0.01), wood, bevel=0.002, grain="X"))
    tops = [0.07 + 0.0] + [z for z in zs[1:]]
    limits = zs[1:] + [H - 0.025]
    rows = []
    for i, (z, zl) in enumerate(zip(tops, limits)):
        rows.append(F.book_row(p, -W / 2 + 0.03, W / 2 - 0.03, -D / 2 + 0.025, z, zl - z - 0.02, D - 0.04, key=f"row{i}",
                               fill=0.9 if i != 2 else 0.6))
    if p.worn and not p.destroyed:
        p.lathe([(0.045, 0.0), (0.05, 0.12), (0.03, 0.18), (0.035, 0.2), (0.0, 0.2)], (0.33, 0.0, 0.77), M.CERAMIC,
                segs=10)
        p.box((0.18, 0.02, 0.23), (0.25, 0.05, 1.1 + 0.115), M.DARK, bevel=0.004)  # photo frame
    if p.destroyed:
        r = p.vrng("wreck")
        # the third shelf has collapsed at its right end: books slid down, others spilled on the floor
        sh = shelves[1]
        p.rotate([sh] + rows[2], rot=(0, 16, 0), pivot=(-W / 2 + 0.02, 0, zs[2]))
        spill = rows[3][: len(rows[3]) // 2] + rows[1][-len(rows[1]) // 3:]
        for i, b in enumerate(spill):
            p.lay_on_floor([b], rot=(r.uniform(-90, 90), r.choice([0, 90, 180]), 0),
                           at=(r.uniform(-0.6, 0.6), -0.35 - r.uniform(0, 0.55)), yaw=r.uniform(0, 180),
                           z=0.0 if i < 10 else r.uniform(0.0, 0.04))
        split = car["left"]
        p.remove([split])
        a1, a2 = F.split_panel(p, 0.3, 1.8, 0.02, (0, 0, 0), wood, (-0.15, 0.55), (0.15, 0.9), plane="YZ", key="side",
                               teeth=7, amp=0.03)
        for half in (a1, a2):
            G.xform(half.obj, loc=(-W / 2 + 0.01, 0, 0.9))
        p.rotate([a2], rot=(0, 0, -6), pivot=(-W / 2, D / 2, 1.2))
    p.collider((0, 0, H / 2), (W, D, H))


def floor_lamp(p: Prop) -> None:
    """Brass floor lamp 1.6 m: weighted base, pole with turned collars, pleated-drum fabric shade."""
    base = [p.lathe([(0.15, 0.0), (0.155, 0.008), (0.14, 0.022), (0.06, 0.04), (0.03, 0.05), (0.0, 0.05)], (0, 0, 0),
                    M.BRASS, segs=16, cap_top=False)]
    base.append(p.cyl(0.011, 1.3, (0, 0, 0.05 + 0.65), M.BRASS, segs=8))
    for z in (0.5, 1.0):
        base.append(p.lathe([(0.013, 0), (0.02, 0.012), (0.013, 0.024)], (0, 0, z), M.BRASS, segs=8, cap_bottom=False,
                            cap_top=False))
    base.append(p.lathe([(0.012, 0.0), (0.03, 0.02), (0.02, 0.06), (0.012, 0.07)], (0, 0, 1.35), M.BRASS, segs=8))
    base.append(p.lathe([(0.0, 0.0), (0.03, 0.01), (0.032, 0.06), (0.015, 0.1), (0.0, 0.105)], (0, 0, 1.42), M.GLASS_FROST,
                        segs=10))
    # shade: tapered drum with a visible inside (two shells) and harp
    shade_prof = [(0.23, 0.0), (0.225, 0.004), (0.16, 0.3), (0.152, 0.302), (0.212, 0.004)]
    pleats = 16
    shade = p.lathe(shade_prof, (0, 0, 1.3), M.SHADE, segs=pleats * 2, cap_bottom=False, cap_top=False, edge_deg=50)
    for i, v in enumerate(shade.obj.data.vertices):  # pleats: alternate verts pushed in
        ang = math.atan2(v.co.y, v.co.x)
        k = round((ang % (2 * math.pi)) / (2 * math.pi) * pleats * 2)
        if k % 2:
            rr = math.hypot(v.co.x, v.co.y)
            f = (rr - 0.008) / max(rr, 1e-6)
            v.co.x *= f
            v.co.y *= f
    harp = p.tube([(-0.16, 0, 1.58), (0, 0, 1.63), (0.16, 0, 1.58)], 0.003, M.BRASS, segs=5, fillet_r=0.05, steps=3)
    bulb = base[-1]
    p.tube([(0.03, 0, 1.4), (0.03, 0, 1.3)], 0.0015, M.BRASS, segs=4)  # pull chain
    if p.destroyed:
        r = p.vrng("wreck")
        # knocked over: lying on the floor, bulb smashed, shade crushed and rolled away
        p.remove([bulb])
        shade_parts = [shade, harp]
        for v in shade.obj.data.vertices:  # dent the shade
            if v.co.x > 0.05:
                v.co.x -= (v.co.x - 0.05) * 0.5
        lamp = [q for q in p.parts if q not in shade_parts]
        p.rotate(lamp, rot=(0, 88, 0), pivot=(0, 0, 0.0))
        lo, hi = p.bounds(lamp)
        p.move(lamp, (0, 0, -lo.z))
        p.rotate(lamp, rot=(0, 0, r.uniform(-30, 30)), pivot=(0, 0, 0))
        p.lay_on_floor(shade_parts, rot=(80, 0, 0), at=(r.uniform(1.0, 1.3), r.uniform(-0.4, 0.4)), yaw=r.uniform(0, 90))
        p.collider((0.7, 0, 0.12), (1.5, 0.35, 0.24))
    else:
        p.collider((0, 0, 0.8), (0.46, 0.46, 1.6))


def rug_oval(p: Prop) -> None:
    """Braided oval rag rug 1.8 x 1.2 (concentric braids: V = distance from the rim)."""
    a, b = 0.9, 0.6
    rings, segs = 7, 36
    import bmesh
    bm = bmesh.new()
    rows = []
    for k in range(rings + 1):
        t = k / rings
        ring = []
        for i in range(segs):
            ang = 2 * math.pi * i / segs
            x, y = a * t * math.cos(ang), b * t * math.sin(ang)
            z = 0.012 if k < rings else 0.004
            ring.append(bm.verts.new((x, y, z)))
        rows.append(ring)
    centre = bm.verts.new((0, 0, 0.012))
    faces = []
    for i in range(segs):
        faces.append((bm.faces.new((centre, rows[1][i], rows[1][(i + 1) % segs])), 1))
    for k in range(1, rings):
        for i in range(segs):
            j = (i + 1) % segs
            faces.append((bm.faces.new((rows[k][i], rows[k + 1][i], rows[k + 1][j], rows[k][j])), k + 1))
    # underside
    under = [bm.verts.new((v.co.x, v.co.y, 0.0)) for v in rows[rings]]
    for i in range(segs):
        j = (i + 1) % segs
        bm.faces.new((rows[rings][j], rows[rings][i], under[i], under[j]))
    bm.faces.new(list(reversed(under)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    uvl = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        for loop in f.loops:
            co = loop.vert.co
            ang = math.atan2(co.y / b, co.x / a)
            rr = math.hypot(co.x / a, co.y / b)
            d = (1.0 - rr) * b  # metres from the rim (approx)
            loop[uvl].uv = ((ang / (2 * math.pi) + 0.5) * 4.6, d * 1.0)
    obj = G._obj(p._name("rug"), bm)
    rug = p.add(obj, M.RUG_BRAIDED, uv="keep", edge_deg=40, wear=0.6)
    if p.worn:
        # a curled, dirtier patch at one end
        for v in rug.obj.data.vertices:
            if v.co.x > 0.72 and v.co.y < -0.1:
                v.co.z += (v.co.x - 0.72) * 0.25
    p.collider((0, 0, 0.006), (1.8, 1.2, 0.012))


def rug_rect(p: Prop) -> None:
    """Rectangular oriental-style area rug 2.0 x 1.4 with fringes on the short ends."""
    W, D = 2.0, 1.4
    nx, ny = 10, 7
    import bmesh
    bm = bmesh.new()
    grid = [[bm.verts.new((-W / 2 + W * i / nx, -D / 2 + D * j / ny, 0.008)) for j in range(ny + 1)] for i in range(nx + 1)]
    for i in range(nx):
        for j in range(ny):
            bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
    # edges down to the floor
    for i in range(nx):
        for j in (0, ny):
            a, b = grid[i][j], grid[i + 1][j]
            a2, b2 = bm.verts.new((a.co.x, a.co.y, 0.0)), bm.verts.new((b.co.x, b.co.y, 0.0))
            bm.faces.new((a, b, b2, a2) if j == 0 else (b, a, a2, b2))
    for j in range(ny):
        for i in (0, nx):
            a, b = grid[i][j], grid[i][j + 1]
            a2, b2 = bm.verts.new((a.co.x, a.co.y, 0.0)), bm.verts.new((b.co.x, b.co.y, 0.0))
            bm.faces.new((b, a, a2, b2) if i == 0 else (a, b, b2, a2))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = G._obj(p._name("rug"), bm)
    if p.worn:
        # flipped-over corner + rucked wave
        for v in obj.data.vertices:
            if v.co.x > 0.55 and v.co.y > 0.3:
                d = (v.co.x - 0.55) + (v.co.y - 0.3)
                if d > 0.35:
                    v.co.z += min(0.25, (d - 0.35) * 0.7)
            if -0.4 < v.co.x < -0.1:
                v.co.z += 0.03 * math.sin((v.co.x + 0.4) / 0.3 * math.pi)
    p.add(obj, M.RUG, uv="planar", uv_axis="Z", edge_deg=40, wear=0.5)
    for sx in (-1, 1):
        p.box((0.06, D - 0.04, 0.003), (sx * (W / 2 + 0.03), 0, 0.0015), M.LINEN, bevel=0.0, grain="X")
    p.collider((0, 0, 0.004), (W, D, 0.008))


BUILDERS = {
    "couch": couch,
    "armchair": armchair,
    "recliner": recliner,
    "coffee_table": coffee_table,
    "side_table": side_table,
    "tv_crt": tv_crt,
    "bookshelf": bookshelf,
    "floor_lamp": floor_lamp,
    "rug_oval": rug_oval,
    "rug_rect": rug_rect,
}


def build(params: dict, outputs: list[str]) -> None:
    core.build_variants(params, outputs, BUILDERS[params["prop"]])
