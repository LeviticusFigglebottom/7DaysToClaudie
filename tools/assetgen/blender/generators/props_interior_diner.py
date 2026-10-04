"""Interior props - roadside diner: red vinyl booth bench, laminate pedestal table, lunch counter, chrome
counter stool, commercial coffee brewer, countertop griddle, wall menu chalkboard.

params: prop (id), seed, variants, mount, budget (see blender_catalogs/props_interior.py).
"""
from __future__ import annotations

import math

from lib import props_int_core as core
from lib import props_int_furn as F
from lib import props_int_mesh as G
from lib.props_int_core import M, Prop


def _channels(part: core.Part, axis: int, n: int, depth: float, face_sign: float, face_axis: int, lo: float, hi: float) -> None:
    """Channel tufting: pulls vertices on the given face inward along n evenly spaced lines (axis = line spacing axis)."""
    me = part.obj.data
    span = hi - lo
    bl, bh = G.bounds([part.obj])
    centre = (bl[face_axis] + bh[face_axis]) * 0.5
    for v in me.vertices:
        if (v.co[face_axis] - centre) * face_sign <= 0:
            continue
        t = (v.co[axis] - lo) / span * n
        d = abs(t - round(t))
        if 0 < round(t) < n and d < 0.18:
            v.co[face_axis] -= face_sign * depth * (1 - d / 0.18)
    me.update()


def diner_booth(p: Prop) -> None:
    """Single-sided diner booth bench 1.2 x 0.62 x 1.05: red channel-tufted vinyl back, seat cushion, chrome
    trim; laminate back panel on the rear (+Y)."""
    W, D = 1.2, 0.62
    vin = M.VINYL_RED
    wr = 0.002 if p.cond == "clean" else 0.005
    p.box((W, D - 0.08, 0.32), (0, 0.03, 0.16), M.LAM_WOOD, bevel=0.004, grain="X")
    p.box((W + 0.004, 0.012, 0.06), (0, -D / 2 + 0.07, 0.03), M.STAINLESS, bevel=0.002, grain="X")
    p.rbox((W - 0.02, D - 0.14, 0.13), (0, -0.04, 0.32 + 0.065), vin, radius=0.035, inner=(6, 3, 1),
                  bulge=(0, 0.01, 0.012), wrinkle=wr, seed=p.seed, edge_deg=30, tags=("cushion",))
    back = p.rbox((W - 0.02, 0.14, 0.62), (0, D / 2 - 0.1, 0.44 + 0.31), vin, radius=0.04, inner=(8, 1, 3),
                  bulge=(0, 0.02, 0), wrinkle=wr, seed=p.seed + 1, edge_deg=30, tags=("cushion",))
    _channels(back, 0, 6, 0.018, -1.0, 1, -W / 2, W / 2)
    G.xform(back.obj, rot=(-7, 0, 0), pivot=(0, D / 2 - 0.1, 0.44))
    p.box((W, 0.03, 0.72), (0, D / 2 - 0.015, 0.36 + 0.36 + 0.0), M.LAM_WOOD, bevel=0.004, grain="X")
    p.tube([(-W / 2, D / 2 - 0.03, 1.08), (W / 2, D / 2 - 0.03, 1.08)], 0.012, M.CHROME, segs=8)
    for sx in (-1, 1):
        p.box((0.02, D - 0.04, 0.9), (sx * (W / 2 + 0.01), 0.0, 0.45), M.LAM_WOOD, bevel=0.003, grain="Z")
    if p.destroyed:
        r = p.vrng("wreck")
        for i in range(3):
            F.slash(p, (r.uniform(-0.45, 0.45), -0.06 + r.uniform(-0.1, 0.1), 0.452), r.uniform(0.18, 0.3), r.uniform(-60, 60),
                    key=f"s{i}")
        for i in range(2):
            lo, hi = p.bounds([back])
            F.slash(p, (r.uniform(-0.4, 0.4), lo.y + 0.05, r.uniform(0.6, 0.95)), 0.25, r.uniform(-70, 70), up=(0, -1, 0),
                    key=f"b{i}")
        for i in range(3):
            F.stuffing(p, (r.uniform(-0.5, 0.5), -D / 2 - 0.2 - r.uniform(0, 0.3), 0.02), r.uniform(0.05, 0.09), key=f"t{i}")
    p.collider((0, 0.0, 0.22), (W, D, 0.44))
    p.collider((0, D / 2 - 0.08, 0.75), (W, 0.16, 0.62))


def diner_table(p: Prop) -> None:
    """Diner table 1.1 x 0.75 x 0.76: mint boomerang-free speckle laminate top, ribbed chrome edge band, chrome
    pedestal on a cast four-prong foot."""
    W, D, H = 1.1, 0.75, 0.76
    top = [p.prism(F.rounded_rect(W, D, 0.04), 0.03, M.LAMINATE_DINER, plane="XY", offset=H - 0.03, bevel=0.002, grain="X")]
    edge = G.rrect_ring(W + 0.006, D + 0.006, 0.043, H - 0.032, n=4)
    edge2 = [(x, y, H + 0.002) for x, y, _ in edge]
    band = p.add(G.loft(p._name("band"), [edge, edge2], cap_bottom=False), M.CHROME, edge_deg=50)
    top.append(band)
    col = [p.cyl(0.04, H - 0.08, (0, 0, 0.04 + (H - 0.08) / 2), M.CHROME, segs=12)]
    col.append(p.box((0.3, 0.3, 0.02), (0, 0, H - 0.045), M.CAST_IRON, bevel=0.004))
    for i in range(4):
        a = math.radians(45 + 90 * i)
        prong = p.box((0.34, 0.06, 0.04), (0.17, 0, 0.02), M.CAST_IRON, bevel=0.008)
        G.xform(prong.obj, rot=(0, 0, math.degrees(a)))
        col.append(prong)
    if p.worn and not p.destroyed:
        p.lathe([(0.025, 0.0), (0.028, 0.07), (0.022, 0.09), (0.016, 0.1), (0.0, 0.105)], (0.35, 0.2, H), M.GLASS, segs=8)
        p.lathe([(0.024, 0.0), (0.024, 0.02), (0.0, 0.026)], (0.35, 0.2, H + 0.105), M.CHROME, segs=8)
        p.lathe([(0.03, 0.0), (0.035, 0.15), (0.015, 0.2), (0.0, 0.205)], (0.42, 0.22, H), M.PL_RED, segs=8)
        p.box((0.1, 0.07, 0.12), (0.4, 0.3, H + 0.06), M.CHROME, bevel=0.008)
    if p.destroyed:
        # knocked over: lying on its edge
        whole = list(p.parts)
        p.rotate(whole, rot=(80, 0, 0), pivot=(0, -D / 2, H))
        lo, hi = p.bounds(whole)
        p.move(whole, (0, 0, -lo.z))
        p.collider((0, 0.2, 0.37), (W, 0.8, 0.74))
    else:
        p.collider((0, 0, H / 2), (W, D, H))


def diner_counter(p: Prop) -> None:
    """Lunch counter section 2.0 x 0.7 x 1.05: laminate top with chrome edge, red vinyl-panelled front with
    chrome strips, stainless kick plate; condiments and a napkin dispenser."""
    W, D, H = 2.0, 0.7, 1.05
    yf = -D / 2
    p.box((W, D - 0.12, H - 0.05), (0, 0.06, (H - 0.05) / 2), M.LAM_WOOD, bevel=0.004, grain="X")
    front = p.rbox((W, 0.05, 0.72), (0, yf + 0.11, 0.16 + 0.36), M.VINYL_RED, radius=0.012, inner=(12, 1, 2), edge_deg=30,
                   tags=("panel",))
    _channels(front, 0, 10, 0.012, -1.0, 1, -W / 2, W / 2)
    for z in (0.16, 0.88):
        p.box((W + 0.004, 0.012, 0.03), (0, yf + 0.08, z), M.CHROME, bevel=0.003, grain="X")
    p.box((W, 0.02, 0.15), (0, yf + 0.13, 0.075), M.STAINLESS, bevel=0.002, grain="X")
    p.box((W, D, 0.04), (0, 0.0, H - 0.02), M.LAMINATE_DINER, bevel=0.003, grain="X")
    p.box((W + 0.006, 0.014, 0.045), (0, yf - 0.002, H - 0.02), M.CHROME, bevel=0.003, grain="X")
    items = []
    for i, x in enumerate((-0.7, 0.05, 0.75)):
        items.append(p.box((0.1, 0.07, 0.12), (x, 0.05, H + 0.06), M.CHROME, bevel=0.008))
        items.append(p.lathe([(0.025, 0.0), (0.028, 0.07), (0.022, 0.09), (0.016, 0.1), (0.0, 0.105)], (x + 0.09, 0.08, H),
                             M.GLASS, segs=8))
        items.append(p.lathe([(0.03, 0.0), (0.035, 0.15), (0.015, 0.2), (0.0, 0.205)], (x + 0.16, 0.06, H), M.PL_RED, segs=8))
    if p.worn:
        p.lathe([(0.034, 0.0), (0.038, 0.095), (0.034, 0.095), (0.031, 0.008), (0.0, 0.008)], (-0.3, -0.1, H), M.CERAMIC,
                segs=12, cap_top=False)
        p.lathe([(0.0, 0.0), (0.07, 0.0), (0.11, 0.016), (0.118, 0.02), (0.07, 0.008), (0.0, 0.007)], (0.4, -0.12, H),
                M.CERAMIC, segs=14, cap_bottom=False, cap_top=False)
    if p.destroyed:
        rr = p.vrng("wreck")
        for it in items[1::3] + items[2::3]:
            p.lay_on_floor([it], rot=(90, 0, 0), at=(rr.uniform(-0.9, 0.9), -D / 2 - 0.2 - rr.uniform(0, 0.4)),
                           yaw=rr.uniform(0, 180))
        for v in front.obj.data.vertices:  # kicked-in front panel
            d = math.hypot(v.co.x - 0.3, v.co.z - 0.4)
            if d < 0.3 and v.co.y < yf + 0.11:
                v.co.y += 0.04 * (1 - d / 0.3)
        F.slash(p, (-0.5, yf + 0.08, 0.6), 0.3, 40, up=(0, -1, 0), key="front")
    p.collider((0, 0, H / 2), (W, D, H))


def diner_stool(p: Prop) -> None:
    """Chrome pedestal counter stool (bolted), 0.76 high: red vinyl seat with chrome band, foot ring."""
    H = 0.76
    base = [p.lathe([(0.2, 0.0), (0.2, 0.012), (0.12, 0.03), (0.06, 0.06), (0.04, 0.08)], (0, 0, 0), M.CHROME, segs=16,
                    cap_top=False)]
    base.append(p.cyl(0.032, H - 0.15, (0, 0, 0.08 + (H - 0.15) / 2), M.CHROME, segs=12))
    ring = [(0.2 * math.cos(a), 0.2 * math.sin(a), 0.3) for a in [i * math.pi / 8 for i in range(16)]]
    base.append(p.tube(ring, 0.011, M.CHROME, segs=6, closed=True))
    for i in range(4):
        a = math.radians(45 + 90 * i)
        sp = p.tube([(0.03 * math.cos(a), 0.03 * math.sin(a), 0.32), (0.19 * math.cos(a), 0.19 * math.sin(a), 0.3)], 0.007,
                    M.CHROME, segs=5)
        base.append(sp)
    seat = [p.lathe([(0.19, 0.0), (0.195, 0.05), (0.19, 0.055), (0.0, 0.056)], (0, 0, H - 0.07), M.CHROME, segs=20,
                    cap_bottom=True)]
    seat.append(p.lathe([(0.185, 0.0), (0.188, 0.03), (0.17, 0.055), (0.1, 0.07), (0.0, 0.074)], (0, 0, H - 0.02),
                        M.VINYL_RED, segs=20, cap_bottom=False, edge_deg=45))
    if p.destroyed:
        r = p.vrng("wreck")
        p.lay_on_floor(seat, rot=(r.uniform(60, 100), 0, 0), at=(0.45, -0.3), yaw=r.uniform(0, 180))
        F.stuffing(p, (0.4, -0.05, 0.03), 0.08, key="t0")
        p.collider((0, 0, 0.35), (0.42, 0.42, 0.7))
    else:
        if p.cond == "worn":
            p.rotate(seat, rot=(0, 0, p.vrng("spin").uniform(0, 90)), pivot=(0, 0, 0))
        p.collider((0, 0, H / 2), (0.42, 0.42, H))


def coffee_machine(p: Prop) -> None:
    """Commercial pour-over coffee brewer 0.22 x 0.42 x 0.5 (stainless), brew funnel, top and base warmers with
    glass decanters."""
    W, D = 0.22, 0.42
    p.box((W, D, 0.06), (0, 0, 0.03), M.STAINLESS, bevel=0.004, grain="Y")
    p.box((W, 0.12, 0.5), (0, D / 2 - 0.06, 0.25), M.STAINLESS, bevel=0.004, grain="Z")
    p.box((W, D - 0.06, 0.08), (0, 0.03, 0.46), M.STAINLESS, bevel=0.004, grain="Y")
    p.box((0.05, 0.004, 0.03), (0.0, -D / 2 + 0.028, 0.47), M.PL_BLACK, bevel=0.0)
    p.cyl(0.08, 0.008, (0, -0.06, 0.064), M.CAST_IRON, segs=14)
    p.cyl(0.075, 0.006, (0, 0.08, 0.503), M.CAST_IRON, segs=14)
    funnel = p.lathe([(0.03, 0.0), (0.09, 0.07), (0.095, 0.085), (0.0, 0.086)], (0, -0.06, 0.32), M.PL_BLACK, segs=12)
    p.box((0.06, 0.13, 0.025), (0, -0.09, 0.4), M.PL_BLACK, bevel=0.006)
    deck = [(0.03, 0.0), (0.085, 0.02), (0.088, 0.12), (0.05, 0.17), (0.045, 0.19), (0.0, 0.19)]

    def decanter(c, broken=False):
        out = [p.lathe(deck, c, M.GLASS, segs=12)]
        x, y, z = c
        out.append(p.lathe([(0.046, 0.0), (0.05, 0.02), (0.035, 0.03), (0.0, 0.032)], (x, y, z + 0.18), M.PL_BLACK, segs=10))
        out.append(p.tube([(x + 0.07, y, z + 0.16), (x + 0.12, y, z + 0.14), (x + 0.12, y, z + 0.06), (x + 0.08, y, z + 0.05)],
                          0.008, M.PL_BLACK, segs=5, fillet_r=0.02, steps=2))
        if broken:
            G.splinter_cut(out[0].obj, (x, y, z + 0.07), (0.2, -0.3, 1.0), jag=0.02, seed=p.seed)
        return out

    decanter((0, -0.06, 0.068), broken=p.destroyed)
    d2 = decanter((0, 0.08, 0.506))
    if p.destroyed:
        r = p.vrng("wreck")
        p.lay_on_floor(d2, rot=(90, 0, 0), at=(0.3, -0.25), yaw=r.uniform(0, 90))
        p.lay_on_floor([funnel], rot=(150, 0, 0), at=(-0.25, -0.2), yaw=0)
    p.collider((0, 0, 0.35), (W, D, 0.7))


def griddle(p: Prop) -> None:
    """Countertop gas griddle 0.9 x 0.62 x 0.4: stainless body on short legs, thick steel plate, splash guards,
    grease trough, four knobs, a spatula."""
    W, D = 0.9, 0.62
    p.box((W, D - 0.04, 0.2), (0, 0.02, 0.1 + 0.1), M.STAINLESS, bevel=0.004, grain="X")
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.cyl(0.02, 0.1, (sx * (W / 2 - 0.05), sy * (D / 2 - 0.07), 0.05), M.STAINLESS, segs=8)
    plate = p.box((W - 0.02, D - 0.12, 0.025), (0, 0.04, 0.3 + 0.0125), M.CAST_IRON, bevel=0.003, grain="X")
    plate.floor_wear = 0.0
    p.box((W, 0.02, 0.12), (0, D / 2 - 0.01, 0.3 + 0.06), M.STAINLESS, bevel=0.003, grain="X")
    for sx in (-1, 1):
        p.box((0.02, D - 0.1, 0.08), (sx * (W / 2 - 0.01), 0.04, 0.3 + 0.04), M.STAINLESS, bevel=0.003, grain="Y")
    p.hollow((W - 0.08, 0.06, 0.04), (0, -D / 2 + 0.06, 0.3), M.STAINLESS, wall=0.003, open_face="+Z", bevel=0.0)
    for i in range(4):
        p.lathe([(0.022, 0.0), (0.024, 0.018), (0.016, 0.03), (0.0, 0.032)], (-0.3 + i * 0.2, -D / 2 + 0.02, 0.17), M.PL_BLACK,
                segs=8, axis="-Y", tags=("knob",))
    sp = [p.box((0.1, 0.12, 0.002), (0.18, 0.05, 0.3 + 0.026), M.STAINLESS, bevel=0.0)]
    sp.append(p.cyl(0.012, 0.16, (0.18, -0.08, 0.3 + 0.04), M.WOOD_RAW, axis="Y", segs=6))
    p.rotate(sp, rot=(0, 0, 25), pivot=(0.18, 0.05, 0.3))
    if p.worn:
        p.rbox((0.25, 0.15, 0.012), (-0.2, 0.05, 0.3 + 0.03), M.MOLD, radius=0.005, inner=(2, 2, 1), wrinkle=0.004, seed=p.seed)
    p.collider((0, 0.0, 0.21), (W, D, 0.42))


def menu_board(p: Prop) -> None:
    """Wall menu chalkboard 0.9 x 1.2 (origin on the wall plane, bottom centre): oak frame, slate with
    smudged chalk 'menu' strokes, chalk tray with chalk."""
    W, H = 0.9, 1.2
    fw = 0.045
    board = p.box((W - 2 * fw + 0.01, 0.012, H - 2 * fw + 0.01), (0, -0.008, H / 2), M.CHALK, bevel=0.0, uv="planar",
                  uv_axis="Y", tags=("panel",))
    frame = []
    for sx in (-1, 1):
        frame.append(p.box((fw, 0.03, H), (sx * (W / 2 - fw / 2), -0.015, H / 2), M.OAK, bevel=0.004, grain="Z"))
    for sz in (0, 1):
        frame.append(p.box((W - 2 * fw, 0.03, fw), (0, -0.015, fw / 2 + sz * (H - fw)), M.OAK, bevel=0.004, grain="X"))
    tray = p.box((W - 0.1, 0.06, 0.015), (0, -0.045, fw + 0.0), M.OAK, bevel=0.003, grain="X")
    chalk = []
    r = p.rng("chalk")
    for i in range(3):
        c = p.cyl(0.005, 0.07, (0, 0, 0), M.PL_WHITE, axis="X", segs=6)
        G.xform(c.obj, rot=(0, 0, r.uniform(-30, 30)), loc=(-0.25 + i * 0.12, -0.05, fw + 0.013))
        chalk.append(c)
    if p.destroyed:
        p.remove([board])
        h1, h2 = F.split_panel(p, W - 2 * fw + 0.01, H - 2 * fw + 0.01, 0.012, (0, -0.008, H / 2), M.CHALK,
                               (-0.42, 0.15), (0.42, -0.05), plane="XZ", inner=M.WOOD_RAW, key="slate", teeth=9, amp=0.05)
        for half in (h1, h2):
            G.xform(half.obj, rot=(0, 0, 0))
        lo, hi = p.bounds([h2])
        p.rotate([h2], rot=(0, 9 if (lo.z + hi.z) / 2 < H / 2 else -6, 0), pivot=(-W / 2 + fw, -0.008, H / 2))
        p.move([h2], (0, -0.012, -0.02))
        p.remove([tray] + chalk)
    p.collider((0, -0.02, H / 2), (W, 0.04, H))


BUILDERS = {
    "diner_booth": diner_booth,
    "diner_table": diner_table,
    "diner_counter": diner_counter,
    "diner_stool": diner_stool,
    "coffee_machine": coffee_machine,
    "griddle": griddle,
    "menu_board": menu_board,
}


def build(params: dict, outputs: list[str]) -> None:
    core.build_variants(params, outputs, BUILDERS[params["prop"]])
