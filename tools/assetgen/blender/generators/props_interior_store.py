"""Interior props - general store / pharmacy / hardware: double-sided gondola shelving with generic goods,
grocery checkout lane, 90s cash register, chest freezer, pharmacy counter, pegboard tool wall (wall),
paint can stack, lumber stack, feed sacks. All packaging is generic art (no brands / text).

params: prop (id), seed, variants, mount, budget (see blender_catalogs/props_interior.py).
"""
from __future__ import annotations

import math

from lib import props_int_core as core
from lib import props_int_furn as F
from lib import props_int_mesh as G
from lib.props_int_core import M, Prop


def _stock_row(p: Prop, x0: float, x1: float, y_edge: float, z: float, depth: float, max_h: float, facing: int, key: str,
               loot: float = 0.0, kinds=("box", "can", "jar")) -> list:
    """Products standing on a shelf in facings (front at y_edge, going back by `depth`; facing=-1 faces -Y)."""
    r = p.rng(key)
    vr = p.vrng(key)
    out = []
    x = x0 + 0.01
    while x < x1 - 0.05:
        kind = kinds[r.randrange(len(kinds))]
        cell = r.randrange(14)
        if kind == "box":
            w, d, h = r.uniform(0.06, 0.2), r.uniform(0.05, 0.08), min(max_h, r.uniform(0.15, 0.3))
        elif kind == "can":
            w = d = 0.075
            h = min(max_h, r.choice([0.11, 0.12, 0.16]))
        else:
            w = d = 0.07
            h = min(max_h, 0.14)
        if x + w > x1:
            break
        rows = max(1, int(depth / (d + 0.01)))
        for k in range(rows):
            if loot and vr.random() < loot * (1.2 - k / rows * 0.5):
                continue
            yy = y_edge - facing * (0.012 + d / 2 + k * (d + 0.008))
            tilt = 0.0
            if loot and vr.random() < 0.15:  # knocked over
                tilt = 90.0
            if kind == "box":
                rot = (tilt * facing, 0, 0 if facing < 0 else 180)
                part = F.package_box(p, (w, d, h), (x + w / 2, yy, z + (h / 2 if not tilt else d / 2)), cell, rot=rot)
            elif kind == "can":
                part = F.can(p, 0.037, h, (x + w / 2, yy, z + (h / 2 if not tilt else 0.037)), cell, segs=8,
                             rot=(tilt, 0, 0))
            else:
                part = p.lathe([(0.03, 0.0), (0.035, 0.01), (0.035, h * 0.75), (0.022, h * 0.85), (0.022, h), (0.0, h)],
                               (x + w / 2, yy, z), M.GLASS, segs=8)
            out.append(part)
        x += w + r.uniform(0.004, 0.012)
    return out


def store_shelf_gondola(p: Prop) -> None:
    """Double-sided gondola 1.22 x 0.92 x 1.6: steel back panel, 4 shelves per side with price strips,
    stocked with generic cartons, cans and jars. Worn = picked over; destroyed = collapsed and looted."""
    W, D, H = 1.22, 0.92, 1.6
    steel = M.STEEL_WHITE
    p.box((W - 0.02, 0.05, H - 0.1), (0, 0, 0.1 + (H - 0.1) / 2), M.PEGBOARD, bevel=0.002, uv_scale=1.0)
    for sx in (-1, 1):
        p.box((0.04, 0.06, H), (sx * (W / 2 - 0.02), 0, H / 2), steel, bevel=0.004, grain="Z")
        p.box((0.05, D - 0.02, 0.05), (sx * (W / 2 - 0.025), 0, 0.025), steel, bevel=0.004, grain="Y")
    p.box((W, 0.08, 0.06), (0, 0, H + 0.03), M.STEEL_RED, bevel=0.004, grain="X")
    loot = {"clean": 0.0, "worn": 0.45, "destroyed": 0.75}[p.cond]
    shelves = {}
    goods = {}
    for side in (-1, 1):
        p.box((W - 0.02, D / 2 - 0.03, 0.1), (0, side * (D / 4 + 0.01), 0.05), steel, bevel=0.003, grain="X")
        levels = [0.1, 0.45, 0.8, 1.15]
        for i, z in enumerate(levels):
            if i == 0:
                shelf = []
            else:
                shelf = [p.box((W - 0.06, 0.38, 0.02), (0, side * (0.025 + 0.19), z - 0.01), steel, bevel=0.002, grain="X")]
                shelf.append(p.box((W - 0.06, 0.012, 0.035), (0, side * (0.405 + 0.006), z - 0.005), M.PL_WHITE, bevel=0.002,
                                   grain="X"))
            shelves[(side, i)] = shelf
            zl = levels[i + 1] - 0.03 if i + 1 < len(levels) else H - 0.05
            front = side * (0.025 + 0.38) if i > 0 else side * (D / 2 - 0.03)
            goods[(side, i)] = _stock_row(p, -W / 2 + 0.05, W / 2 - 0.05, front, z + (0.0 if i else 0.0), 0.34,
                                          zl - z, side, f"row{side}{i}", loot=loot)
    if p.destroyed:
        r = p.vrng("wreck")
        # front-side top shelf tore out of the uprights: hangs diagonally, its stock dumped on the floor
        sh = shelves[(-1, 3)]
        p.rotate(sh, rot=(0, 18, 0), pivot=(-W / 2, 0, 1.15))
        p.rotate(sh, rot=(-25, 0, 0), pivot=(0, -0.025, 1.15))
        spill = goods[(-1, 3)] + goods[(-1, 2)][::2]
        for i, it in enumerate(spill):
            p.lay_on_floor([it], rot=(r.uniform(-90, 90), r.choice([0, 90, 180]), 0),
                           at=(r.uniform(-0.8, 0.8), -D / 2 - 0.15 - r.uniform(0, 0.6)), yaw=r.uniform(0, 180))
    p.collider((0, 0, H / 2), (W, D, H))


def _register(p: Prop, c, yaw: float = 0.0, broken: bool = False, drawer_open: float = 0.0) -> list:
    """90s electronic cash register (~0.42 x 0.45 x 0.32) centred at c (base on c.z), facing -Y."""
    x, y, z = c
    out = []
    base = p.rbox((0.42, 0.42, 0.11), (x, y, z + 0.055), M.PL_BEIGE, radius=0.012, inner=(2, 2, 1), edge_deg=30)
    out.append(base)
    drw = [p.box((0.38, 0.38, 0.08), (x, y - 0.03, z + 0.05), M.PL_GREY, bevel=0.004)]
    drw.append(p.box((0.12, 0.012, 0.02), (x, y - 0.225, z + 0.06), M.PL_BLACK, bevel=0.003))
    if drawer_open:
        tray = p.hollow((0.34, 0.3, 0.05), (x, y - 0.06, z + 0.07), M.PL_BLACK, wall=0.006, open_face="+Z", bevel=0.0)
        drw.append(tray)
        for i in range(4):
            drw.append(p.box((0.006, 0.28, 0.04), (x - 0.12 + i * 0.08, y - 0.06, z + 0.07), M.PL_BLACK, bevel=0.0))
        p.move(drw, (0, -drawer_open, 0))
    out += drw
    body = p.rbox((0.4, 0.3, 0.12), (x, y + 0.04, z + 0.11 + 0.06), M.PL_BEIGE, radius=0.012, inner=(2, 1, 1),
                  taper_top=0.08, edge_deg=30)
    G.xform(body.obj, rot=(12, 0, 0), pivot=(x, y + 0.04, z + 0.11))
    out.append(body)
    keys = p.box((0.3, 0.16, 0.006), (x - 0.02, y - 0.02, z + 0.205), M.PL_GREY, bevel=0.0015)
    G.xform(keys.obj, rot=(12, 0, 0), pivot=(x, y + 0.04, z + 0.11))
    out.append(keys)
    for i in range(4):
        for j in range(4):
            k = p.box((0.03, 0.026, 0.01), (x - 0.12 + i * 0.045, y - 0.07 + j * 0.035, z + 0.21), M.PL_WHITE if (i + j) % 3 else M.PL_RED,
                      bevel=0.002, tags=("knob",))
            G.xform(k.obj, rot=(12, 0, 0), pivot=(x, y + 0.04, z + 0.11))
            out.append(k)
    disp = [p.box((0.03, 0.03, 0.12), (x + 0.12, y + 0.12, z + 0.29), M.PL_BEIGE, bevel=0.005)]
    disp.append(p.box((0.16, 0.05, 0.06), (x + 0.12, y + 0.12, z + 0.37), M.PL_BEIGE, bevel=0.008))
    disp.append(p.box((0.12, 0.004, 0.03), (x + 0.12, y + 0.094, z + 0.37), M.GLASS, bevel=0.0))
    out += disp
    if broken:
        p.rotate(disp, rot=(0, 75, 0), pivot=(x + 0.12, y + 0.12, z + 0.23))
    if yaw:
        p.rotate(out, rot=(0, 0, yaw), pivot=(x, y, z))
    return out


def cash_register(p: Prop) -> None:
    """Stand-alone 90s electronic cash register for shop / diner counters."""
    opn = 0.0 if p.cond == "clean" else (0.14 if p.cond == "worn" else 0.2)
    _register(p, (0, 0.02, 0.0), broken=p.destroyed, drawer_open=opn)
    if p.destroyed:
        r = p.vrng("wreck")
        # pried and shoved over on its side
        p.rotate(list(p.parts), rot=(0, -80, 0), pivot=(0, 0, 0))
        lo, hi = p.bounds()
        p.move(list(p.parts), (0, 0, -lo.z))
        for i in range(5):
            p.cyl(0.012, 0.002, (r.uniform(-0.3, 0.3), r.uniform(-0.45, -0.2), 0.001), M.TIN, segs=8)
    p.collider((0, 0, 0.2), (0.45, 0.5, 0.4))


def checkout_counter(p: Prop) -> None:
    """Grocery checkout lane 1.8 x 0.8 x 0.9: laminate body with steel trim, conveyor belt, scanner window,
    bagging well and an integrated register on a stand (customer side -Y)."""
    W, D, H = 1.8, 0.8, 0.9
    p.box((W, D - 0.1, H - 0.04), (0, 0.05, (H - 0.04) / 2), M.LAM_WOOD, bevel=0.004, grain="X")
    p.box((W, 0.03, 0.08), (0, -D / 2 + 0.065, 0.04), M.PL_BLACK, bevel=0.003)
    p.box((W + 0.01, D - 0.08, 0.04), (0, 0.04, H - 0.02), M.LAMINATE, bevel=0.005, grain="X")
    for sy in (-1, 1):
        p.box((W + 0.012, 0.012, 0.045), (0, 0.04 + sy * (D - 0.08) / 2, H - 0.02), M.CHROME, bevel=0.003)
    # conveyor
    belt = p.box((0.95, 0.42, 0.015), (-0.4, 0.05, H + 0.008), M.RUBBER, bevel=0.003, uv_scale=2.0)
    p.cyl(0.03, 0.44, (0.1, 0.05, H + 0.0), M.CHROME, axis="Y", segs=10)
    for sy in (-1, 1):
        p.box((0.97, 0.025, 0.05), (-0.4, 0.05 + sy * 0.235, H + 0.02), M.STEEL_GREY, bevel=0.004)
    p.box((0.25, 0.25, 0.004), (0.3, 0.05, H + 0.002), M.GLASS, bevel=0.0)
    p.hollow((0.45, 0.45, 0.2), (0.62, 0.05, H - 0.1 + 0.0), M.STEEL_GREY, wall=0.01, open_face="+Z", bevel=0.0)
    # register on a short stand at the cashier end (+Y side faces the cashier)
    p.cyl(0.03, 0.12, (0.3, 0.33, H + 0.06), M.STEEL_GREY, segs=8)
    opn = 0.0 if p.cond == "clean" else 0.15
    _register(p, (0.3, 0.33, H + 0.12), yaw=180, broken=p.destroyed, drawer_open=opn)
    r = p.rng("impulse")
    p.box((0.04, 0.4, 0.6), (-W / 2 + 0.05, -D / 2 - 0.05, 0.3 + 0.3), M.STEEL_GREY, bevel=0.003)
    for i in range(3):
        for j in range(3):
            F.package_box(p, (0.025, 0.1, 0.14), (-W / 2 + 0.085, -D / 2 - 0.18 + j * 0.12, 0.42 + i * 0.17), r.randrange(14),
                          rot=(0, 0, 90))
    if p.destroyed:
        rr = p.vrng("wreck")
        p.remove([belt])
        torn = p.rbox((0.6, 0.42, 0.015), (0, 0, 0), M.RUBBER, radius=0.004, inner=(4, 2, 1), wrinkle=0.04, seed=p.seed)
        p.lay_on_floor([torn], at=(-0.6, -0.75), yaw=rr.uniform(-30, 30))
    p.collider((0, 0.05, H / 2), (W, D - 0.1, H))


def store_freezer(p: Prop) -> None:
    """White enamel chest freezer 1.5 x 0.8 x 0.85 with two sliding glass lids and food inside."""
    W, D, H = 1.5, 0.8, 0.85
    body = p.hollow((W, D, H - 0.06), (0, 0, 0.06 + (H - 0.06) / 2), M.STEEL_WHITE, wall=0.07, open_face="+Z", bevel=0.015,
                    back=0.1, grain="X")
    body.floor_wear = 0.8
    p.box((W - 0.04, D - 0.04, 0.06), (0, 0, 0.03), M.PL_BLACK, bevel=0.0)
    for i in range(10):
        p.box((0.6, 0.004, 0.012), (0.35, -D / 2 - 0.001, 0.12 + i * 0.022), M.PL_GREY, bevel=0.0)
    r = p.rng("frozen")
    for i in range(16):
        F.package_box(p, (r.uniform(0.15, 0.3), r.uniform(0.12, 0.2), r.uniform(0.04, 0.08)),
                      (r.uniform(-0.55, 0.55), r.uniform(-0.22, 0.22), 0.5 + (i % 4) * 0.06), r.randrange(14),
                      rot=(0, 0, r.uniform(-30, 30)))
    lids = []
    for i, sx in enumerate((-1, 1)):
        grp = [p.box((W / 2 + 0.02, D - 0.1, 0.03), (sx * (W / 4 - 0.01), 0, H + 0.015 + i * 0.02), M.CHROME, bevel=0.006)]
        grp.append(p.box((W / 2 - 0.06, D - 0.18, 0.006), (sx * (W / 4 - 0.01), 0, H + 0.032 + i * 0.02), M.GLASS, bevel=0.0))
        lids.append(grp)
    if p.cond == "worn":
        p.move(lids[1], (-0.45, 0, 0))
    if p.destroyed:
        rr = p.vrng("wreck")
        p.remove(lids[1][1:])
        F.shatter_pane(p, W / 2 - 0.06, D - 0.18, (W / 4 - 0.01, 0, H + 0.052), M.GLASS, t=0.005, plane="XY", spokes=9,
                       rings=2, key="lid", missing_inner=0.9, missing_outer=0.3, floor_shards=5, floor_at=(0.3, -0.75))
        p.lay_on_floor(lids[0], rot=(0, 0, 0), at=(-0.7, -0.8), yaw=rr.uniform(-25, 25))
        for i in range(4):
            p.rbox((0.12, 0.1, 0.05), (rr.uniform(-0.5, 0.5), rr.uniform(-0.2, 0.2), 0.45), M.MOLD, radius=0.03, inner=(1, 1, 1),
                   wrinkle=0.01, seed=rr.randrange(999))
    p.collider((0, 0, H / 2), (W, D, H))


def pharmacy_counter(p: Prop) -> None:
    """Pharmacy dispensing counter 1.8 x 0.6 x 1.0: laminate front and top (customer side -Y); open shelving
    on the staff side (+Y) stocked with medicine boxes and bottles."""
    W, D, H = 1.8, 0.6, 1.0
    yf = -D / 2
    front = p.panel(W, H - 0.04, 0.025, (0, yf + 0.0125, (H - 0.04) / 2), M.LAM_WOOD, style="groove", frame=0.1,
                    tags=("panel",))
    p.box((W + 0.03, D + 0.03, 0.035), (0, 0.0, H - 0.0175), M.LAMINATE, bevel=0.005, grain="X")
    for sx in (-1, 1):
        p.box((0.025, D - 0.03, H - 0.035), (sx * (W / 2 - 0.0125), 0.0, (H - 0.035) / 2), M.LAM_WOOD, bevel=0.003, grain="Z")
    p.box((W - 0.05, 0.015, H - 0.04), (0, yf + 0.06, (H - 0.04) / 2), M.LAM_WOOD, bevel=0.0)
    levels = (0.06, 0.36, 0.66)
    loot = {"clean": 0.0, "worn": 0.4, "destroyed": 0.85}[p.cond]
    rows = []
    for i, z in enumerate(levels):
        p.box((W - 0.05, D - 0.1, 0.02), (0, 0.04, z - 0.01), M.LAM_WOOD, bevel=0.002, grain="X")
        rows.append(_stock_row(p, -W / 2 + 0.04, W / 2 - 0.04, D / 2 - 0.02, z, 0.38, 0.25, 1, f"rx{i}", loot=loot,
                               kinds=("box", "box", "jar")))
    p.box((0.32, 0.25, 0.008), (-0.4, -0.1, H + 0.004), M.RUBBER, bevel=0.0)
    if p.worn:
        r = p.rng("counter")
        for i in range(3):
            F.package_box(p, (0.1, 0.06, 0.04), (r.uniform(-0.5, 0.5), r.uniform(-0.2, 0.15), H + 0.02), r.randrange(14),
                          rot=(0, 0, r.uniform(0, 90)))
    if p.destroyed:
        rr = p.vrng("wreck")
        spill = rows[2][::2] + rows[1][::3]
        for it in spill:
            p.lay_on_floor([it], rot=(rr.uniform(-90, 90), 0, 0), at=(rr.uniform(-0.8, 0.8), D / 2 + 0.15 + rr.uniform(0, 0.5)),
                           yaw=rr.uniform(0, 180))
        p.remove([front])
        h1, h2 = F.split_panel(p, W, H - 0.04, 0.025, (0, yf + 0.0125, (H - 0.04) / 2), M.LAM_WOOD, (0.2, -0.48), (-0.15, 0.48),
                               plane="XZ", key="front", teeth=8, amp=0.04)
        p.rotate([h1], rot=(-18, 0, 0), pivot=(0, yf, 0))
    p.collider((0, 0, H / 2), (W + 0.03, D + 0.03, H))


def _tool(p: Prop, kind: str, x: float, z: float, y: float, r) -> list:
    """Hand tools hanging on pegboard hooks (front face -Y at y)."""
    out = [p.tube([(x, y, z), (x, y - 0.06, z + 0.012)], 0.0025, M.CHROME, segs=4)]
    if kind == "hammer":
        out.append(p.cyl(0.013, 0.3, (x, y - 0.03, z - 0.17), M.WOOD_RAW, segs=8))
        out.append(p.box((0.11, 0.028, 0.028), (x, y - 0.03, z - 0.02), M.CAST_IRON, bevel=0.004))
    elif kind == "saw":
        out.append(p.prism([(-0.04, 0.0), (0.04, 0.0), (0.03, -0.42), (-0.02, -0.42)], 0.002, M.STAINLESS, plane="XZ",
                           offset=-0.001))
        G.xform(out[-1].obj, loc=(x, y - 0.02, z - 0.1))
        out.append(p.rbox((0.1, 0.03, 0.12), (x, y - 0.02, z - 0.06), M.WOOD_RAW, radius=0.012, inner=(1, 1, 1), edge_deg=30))
    elif kind == "wrench":
        for i, ln in enumerate((0.15, 0.2, 0.25)):
            out.append(p.box((0.018, 0.006, ln), (x - 0.03 + i * 0.03, y - 0.015, z - ln / 2), M.CHROME, bevel=0.002))
    elif kind == "driver":
        for i in range(3):
            out.append(p.cyl(0.012, 0.1, (x - 0.03 + i * 0.03, y - 0.02, z - 0.06), [M.PL_RED, M.PL_BLUE, M.PL_BLACK][i], segs=6))
            out.append(p.cyl(0.003, 0.12, (x - 0.03 + i * 0.03, y - 0.02, z - 0.17), M.CHROME, segs=4))
    elif kind == "rope":
        out.append(p.tube([(x + 0.1 * math.cos(a), y - 0.03, z - 0.12 + 0.1 * math.sin(a)) for a in
                           [i * math.pi / 6 for i in range(13)]], 0.012, M.BURLAP, segs=5, closed=True))
    elif kind == "pack":
        for i in range(2):
            out.append(F.package_box(p, (0.1, 0.02, 0.16), (x, y - 0.02 - i * 0.02, z - 0.08), r.randrange(14)))
    elif kind == "tape":
        out.append(p.rbox((0.07, 0.04, 0.07), (x, y - 0.03, z - 0.04), M.PL_RED, radius=0.015, inner=(1, 1, 1), edge_deg=30))
    return out


def pegboard_wall(p: Prop) -> None:
    """Hardware-store pegboard panel 1.2 x 1.2 (wall, origin on the wall plane, bottom centre) with hand tools,
    rope and blister packs on hooks."""
    W, H = 1.2, 1.2
    p.box((W - 0.05, 0.006, H - 0.05), (0, -0.025, H / 2), M.PEGBOARD, bevel=0.0, uv_scale=1.0)
    for sx in (-1, 1):
        p.box((0.025, 0.04, H), (sx * (W / 2 - 0.0125), -0.02, H / 2), M.WOOD_RAW, bevel=0.003, grain="Z")
    for sz in (0, 1):
        p.box((W, 0.04, 0.025), (0, -0.02, 0.0125 + sz * (H - 0.025)), M.WOOD_RAW, bevel=0.003, grain="X")
    r = p.rng("tools")
    kinds = ["hammer", "saw", "wrench", "driver", "rope", "pack", "tape", "pack", "hammer", "pack", "driver", "rope"]
    y = -0.028
    i = 0
    for row, z in enumerate((1.07, 0.7, 0.33)):
        for col in range(4):
            x = -W / 2 + 0.17 + col * 0.29
            k = kinds[i % len(kinds)]
            i += 1
            if p.worn and p.chance(f"looted{row}{col}", 0.45):
                p.tube([(x, y, z), (x, y - 0.06, z + 0.012)], 0.0025, M.CHROME, segs=4)
                continue
            _tool(p, k, x, z, y, r)
    p.collider((0, -0.03, H / 2), (W, 0.08, H))


def paint_can_stack(p: Prop) -> None:
    """Gallon paint cans stacked 3-2-1 beside two 5-gallon buckets (~0.75 x 0.4 x 0.6)."""
    r = p.rng("paint")
    cans = []
    rad, hh = 0.085, 0.19
    for level, n in enumerate((3, 2, 1)):
        for i in range(n):
            x = -0.18 + (i - (n - 1) / 2) * (2 * rad + 0.004)
            c = F.can(p, rad, hh, (x, 0.0, level * (hh + 0.004) + hh / 2), r.randrange(14), segs=12, mat=M.CARDBOARD)
            p.cyl(rad * 0.97, 0.004, (x, 0.0, level * (hh + 0.004) + hh + 0.002), M.TIN, segs=12)
            cans.append(c)
    for i in range(2):
        bx = 0.2 + i * 0.12
        by = -0.05 + i * 0.12
        p.lathe([(0.14, 0.0), (0.15, 0.36), (0.155, 0.37), (0.15, 0.375), (0.0, 0.38)], (bx, by, 0.0), M.PL_WHITE, segs=14)
        p.tube([(bx - 0.15, by, 0.33), (bx - 0.1, by, 0.45), (bx + 0.1, by, 0.45), (bx + 0.15, by, 0.33)], 0.003, M.CHROME,
               segs=4, fillet_r=0.05, steps=3)
    if p.worn:
        rr = p.vrng("tip")
        top = cans[-1]
        p.lay_on_floor([top], rot=(90, 0, 0), at=(-0.35, -0.3), yaw=rr.uniform(0, 90))
        p.cyl(0.12, 0.003, (-0.45, -0.35, 0.0015), M.PL_RED, segs=10)  # dried spill
    p.collider((0, 0.0, 0.3), (0.75, 0.4, 0.6))


def lumber_stack(p: Prop) -> None:
    """Stack of 2x4 studs (2.44 m) on spacer blocks, 4 layers with stickers between layers."""
    L = 2.44
    bw, bh = 0.089, 0.038
    r = p.rng("lumber")
    z = 0.0
    for sy in (-0.9, 0.0, 0.9):
        p.box((0.6, 0.09, 0.09), (0.0, sy, 0.045), M.WOOD_RAW, bevel=0.003, grain="X")
    z = 0.09
    for layer in range(4):
        n = 6 if layer < 3 else 4
        for i in range(n):
            if p.worn and layer == 3 and p.chance(f"gone{i}", 0.5):
                continue
            x = -0.27 + i * (bw + 0.008)
            yy = r.uniform(-0.03, 0.03)
            b = p.box((bw, L, bh), (x + (r.uniform(-0.01, 0.01)), yy, z + bh / 2), M.WOOD_RAW, bevel=0.002, grain="Y")
            if p.worn and r.random() < 0.3:
                G.xform(b.obj, rot=(0, 0, r.uniform(-4, 4)), pivot=(x, yy, z))
        z += bh
        if layer < 3:
            for sy in (-0.9, 0.0, 0.9):
                p.box((0.6, 0.03, 0.02), (0.0, sy, z + 0.01), M.WOOD_RAW, bevel=0.002, grain="X")
            z += 0.02
    p.collider((0, 0, z / 2), (0.6, L, z))


def feed_sacks(p: Prop) -> None:
    """Pile of five 50-lb woven feed sacks, stacked crosswise (~0.9 x 0.8 x 0.45)."""
    r = p.rng("sacks")

    def sack(c, yaw, seed):
        def pinch(v):
            # gathered, sewn ends: pinch toward the seam at both y ends
            t = abs(v.y) / 0.36
            k = max(0.0, (t - 0.75) / 0.25)
            v.z *= 1.0 - 0.55 * k
            v.x *= 1.0 - 0.15 * k
            return v
        s = p.rbox((0.46, 0.74, 0.14), (0, 0, 0), M.BURLAP, radius=0.05, inner=(3, 5, 1), bulge=(0.01, 0.0, 0.03),
                   wrinkle=0.008, seed=seed, squash=pinch, edge_deg=40)
        G.xform(s.obj, rot=(0, 0, yaw), loc=c)
        return s

    sacks = [sack((-0.2, 0.0, 0.07), 0, 1), sack((0.27, 0.0, 0.07), 0, 2), sack((0.03, 0.0, 0.2), 90, 3),
             sack((0.0, 0.05, 0.33), r.uniform(-15, 15), 4)]
    if not p.worn:
        sacks.append(sack((0.05, -0.08, 0.45), 90 + r.uniform(-10, 10), 5))
    else:
        rr = p.vrng("torn")
        s = sack((0, 0, 0), 0, 6)
        p.lay_on_floor([s], rot=(0, 0, 0), at=(0.55, -0.55), yaw=rr.uniform(20, 60))
        F.slash(p, (0.55, -0.55, 0.13), 0.2, 30, key="tear")
        p.rbox((0.4, 0.3, 0.05), (0.65, -0.85, 0.02), M.WOOD_RAW, radius=0.03, inner=(2, 2, 1), wrinkle=0.012, seed=p.seed,
               edge_deg=40)
    p.collider((0.05, 0.0, 0.25), (0.9, 0.8, 0.5))


BUILDERS = {
    "store_shelf_gondola": store_shelf_gondola,
    "checkout_counter": checkout_counter,
    "cash_register": cash_register,
    "store_freezer": store_freezer,
    "pharmacy_counter": pharmacy_counter,
    "pegboard_wall": pegboard_wall,
    "paint_can_stack": paint_can_stack,
    "lumber_stack": lumber_stack,
    "feed_sacks": feed_sacks,
}


def build(params: dict, outputs: list[str]) -> None:
    core.build_variants(params, outputs, BUILDERS[params["prop"]])
