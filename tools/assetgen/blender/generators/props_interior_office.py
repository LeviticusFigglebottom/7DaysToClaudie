"""Interior props - office / civic (town hall, sheriff's office, clinic): steel tanker desk with a 90s
computer, swivel office chair, 4-drawer filing cabinet, boltless steel shelving, steel weapons locker with a
padlocked hasp, small floor safe, cork board (wall), bottled water cooler, reception counter.

params: prop (id), seed, variants, mount, budget (see blender_catalogs/props_interior.py).
"""
from __future__ import annotations

import math

from lib import props_int_core as core
from lib import props_int_furn as F
from lib import props_int_mesh as G
from lib.props_int_core import M, Prop


def _papers(p: Prop, c, n: int, spread: float, key: str, z_step: float = 0.0012, floor: bool = False) -> None:
    r = p.rng(key)
    for i in range(n):
        sh = p.box((0.215, 0.28, 0.0012), (0, 0, 0), M.PAPER, bevel=0.0, uv="keep", tags=("paper",))
        core.set_face_uvs(sh.obj, lambda poly, k=r.randrange(4): (*core.note_rect(k), 0, 1, False))
        rx = r.uniform(-4, 4) if floor else 0.0
        G.xform(sh.obj, rot=(rx, 0, r.uniform(-40, 40)),
                loc=(c[0] + r.uniform(-spread, spread), c[1] + r.uniform(-spread, spread), c[2] + 0.0006 + i * z_step))


def _crt_monitor(p: Prop, c, yaw: float = 0.0, broken: bool = False) -> list:
    """Beige 14-inch CRT monitor + keyboard."""
    x, y, z = c
    out = [p.rbox((0.36, 0.3, 0.32), (x, y, z + 0.17), M.PL_BEIGE, radius=0.02, inner=(2, 1, 2), edge_deg=30)]
    rear = p.lathe([(0.0, 0.0), (0.21, 0.0), (0.15, 0.1), (0.06, 0.13), (0.0, 0.135)], (x, y + 0.14, z + 0.17), M.PL_BEIGE,
                   segs=4, axis="Y", cap_bottom=False)
    G.xform(rear.obj, rot=(0, 45, 0), pivot=(x, y + 0.14, z + 0.17))
    out.append(rear)
    out.append(p.box((0.22, 0.2, 0.02), (x, y + 0.02, z + 0.01), M.PL_BEIGE, bevel=0.006))
    if broken:
        out += F.shatter_pane(p, 0.27, 0.21, (x, y - 0.152, z + 0.18), M.CRT, t=0.004, spokes=9, rings=2, key="mon",
                              missing_inner=0.95, missing_outer=0.3)
        out.append(p.box((0.27, 0.01, 0.21), (x, y - 0.13, z + 0.18), M.PL_BLACK, bevel=0.0))
    else:
        out.append(p.rbox((0.27, 0.02, 0.21), (x, y - 0.15, z + 0.18), M.CRT, radius=0.012, inner=(3, 1, 2),
                          bulge=(0, 0.008, 0), uv="planar", uv_axis="Y", edge_deg=40))
    out.append(p.box((0.03, 0.004, 0.012), (x + 0.13, y - 0.151, z + 0.05), M.PL_GREY, bevel=0.0, tags=("knob",)))
    kb = p.box((0.44, 0.16, 0.03), (x, y - 0.32, z + 0.015), M.PL_BEIGE, bevel=0.006)
    keys = p.box((0.4, 0.12, 0.006), (x, y - 0.32, z + 0.032), M.PL_GREY, bevel=0.0015)
    out += [kb, keys]
    if yaw:
        p.rotate(out, rot=(0, 0, yaw), pivot=(x, y, z))
    return out


def _desk_phone(p: Prop, c, yaw: float = 0.0) -> list:
    x, y, z = c
    out = [p.rbox((0.2, 0.22, 0.07), (x, y, z + 0.035), M.PL_BEIGE, radius=0.02, inner=(2, 2, 1), taper_top=0.1, edge_deg=30)]
    hand = p.rbox((0.22, 0.055, 0.045), (x, y + 0.04, z + 0.09), M.PL_BEIGE, radius=0.02, inner=(3, 1, 1), edge_deg=30)
    out.append(hand)
    out.append(p.box((0.1, 0.08, 0.004), (x, y - 0.05, z + 0.071), M.PL_GREY, bevel=0.0))
    p.rotate(out, rot=(0, 0, yaw), pivot=(x, y, z))
    return out


def office_desk(p: Prop) -> None:
    """Steel double-pedestal 'tanker' desk 1.5 x 0.76 x 0.75: putty enamel, woodgrain laminate top,
    two 3-drawer pedestals + centre drawer, beige CRT computer and desk phone."""
    W, D, H = 1.5, 0.76, 0.75
    steel = M.STEEL_BEIGE
    yf = -D / 2 + 0.02
    p.box((W, D, 0.03), (0, 0, H - 0.015), M.LAM_WOOD, bevel=0.004, grain="X")
    p.box((W + 0.004, D + 0.004, 0.012), (0, 0, H - 0.036), M.CHROME, bevel=0.002)
    pw = 0.4
    drawers = []
    for side in (-1, 1):
        px = side * (W / 2 - pw / 2)
        body = p.hollow((pw, D - 0.02, H - 0.05), (px, 0.01, (H - 0.05) / 2 + 0.008), steel, wall=0.015, bevel=0.006,
                        grain="Z")
        body.floor_wear = 0.6
        p.box((pw - 0.02, D - 0.06, 0.06), (px, 0.02, 0.03), M.PL_BLACK, bevel=0.0)
        for i, (za, zb) in enumerate(((0.46, 0.68), (0.25, 0.44), (0.07, 0.235))):
            k = f"p{side}{i}"
            pull = 0.0
            if p.cond == "worn":
                pull = p.vrng(k).choice([0.0, 0.0, 0.05, 0.12])
            if p.destroyed:
                pull = p.vrng(k).choice([0.0, 0.2, 0.32])
            drawers.append(F.drawer(p, px - pw / 2 + 0.012, za, px + pw / 2 - 0.012, zb, yf - 0.016, D - 0.1, steel,
                                    t=0.016, style="slab", handle="bar", handle_mat=M.CHROME, pull=pull, key=k,
                                    box_mat=steel))
    pull = 0.0 if p.cond == "clean" else 0.06
    drawers.append(F.drawer(p, -W / 2 + pw + 0.02, H - 0.13, W / 2 - pw - 0.02, H - 0.045, yf - 0.016, D - 0.1, steel,
                            t=0.016, style="slab", handle="bar", handle_mat=M.CHROME, pull=pull, key="centre", box_mat=steel))
    p.box((W - 2 * pw, 0.015, 0.4), (0, D / 2 - 0.03, H - 0.05 - 0.2 - 0.08), steel, bevel=0.003, grain="X")
    if not p.destroyed:
        _crt_monitor(p, (-0.35, 0.12, H))
        _desk_phone(p, (0.45, 0.15, H), yaw=-15)
    if p.worn:
        _papers(p, (0.15, -0.12, H), 6 if p.cond == "worn" else 3, 0.12, "desk_papers")
        p.lathe([(0.034, 0.0), (0.038, 0.095), (0.034, 0.095), (0.031, 0.008), (0.0, 0.008)], (0.62, -0.15, H), M.CERAMIC,
                segs=12, cap_top=False)
    if p.destroyed:
        r = p.vrng("wreck")
        p.lay_on_floor(drawers[0], rot=(0, 180, 0), at=(-0.55, -0.95), yaw=r.uniform(-30, 30))
        p.lay_on_floor(drawers[4], rot=(8, 0, 0), at=(0.5, -0.9), yaw=r.uniform(-40, 40))
        _papers(p, (0.0, -0.9, 0.0), 14, 0.55, "floor_papers", z_step=0.0015, floor=True)
        mon = _crt_monitor(p, (0, 0, 0), broken=True)
        p.lay_on_floor(mon, rot=(-88, 0, 0), at=(0.15, -1.25), yaw=r.uniform(-20, 20))
        _desk_phone(p, (-0.2, -1.5, 0.0), yaw=r.uniform(0, 180))
    p.collider((0, 0, H / 2), (W, D, H))


def office_chair(p: Prop) -> None:
    """90s task chair: 5-star base on casters, gas lift, black fabric-vinyl seat and back, loop arms."""
    seat_z = 0.47
    parts = {"base": [], "seat": [], "back": [], "arms": []}
    for i in range(5):
        a = 2 * math.pi * i / 5 + 0.3
        leg = p.box((0.3, 0.05, 0.035), (0.15, 0, 0.075), M.PL_BLACK, bevel=0.008, segs=2)
        G.xform(leg.obj, rot=(0, -6, math.degrees(a)), pivot=(0, 0, 0.075))
        parts["base"].append(leg)
        cx, cy = math.cos(a) * 0.3, math.sin(a) * 0.3
        if not (p.destroyed and i == 2):
            wheel = p.cyl(0.026, 0.032, (cx, cy, 0.026), M.PL_BLACK, axis="X", segs=10, tags=("caster",))
            G.xform(wheel.obj, rot=(0, 0, math.degrees(a)), pivot=(cx, cy, 0.026))
            parts["base"].append(wheel)
            parts["base"].append(p.box((0.02, 0.04, 0.03), (cx, cy, 0.055), M.PL_BLACK, bevel=0.003))
    parts["base"].append(p.cyl(0.045, 0.06, (0, 0, 0.08), M.PL_BLACK, segs=12))
    parts["base"].append(p.cyl(0.025, 0.24, (0, 0, 0.22), M.CHROME, segs=10))
    parts["base"].append(p.box((0.22, 0.2, 0.03), (0, 0.01, 0.36), M.PL_BLACK, bevel=0.006))
    fab = M.VINYL_BLACK
    wr = 0.003 if p.cond == "clean" else 0.007
    seat = p.rbox((0.48, 0.46, 0.09), (0, -0.01, seat_z - 0.045 + 0.02), fab, radius=0.035, inner=(2, 2, 1),
                  bulge=(0, 0, 0.012), wrinkle=wr, seed=p.seed, edge_deg=30, tags=("cushion",))
    parts["seat"].append(seat)
    parts["seat"].append(p.box((0.44, 0.42, 0.02), (0, -0.01, seat_z - 0.055), M.PL_BLACK, bevel=0.004))
    bar = p.box((0.06, 0.04, 0.4), (0, 0.27, seat_z + 0.1), M.PL_BLACK, bevel=0.006)
    G.xform(bar.obj, rot=(-8, 0, 0), pivot=(0, 0.27, seat_z - 0.05))
    parts["back"].append(bar)
    back = p.rbox((0.44, 0.08, 0.46), (0, 0.29, seat_z + 0.37), fab, radius=0.035, inner=(2, 1, 2), bulge=(0, 0.02, 0),
                  wrinkle=wr, seed=p.seed + 1, edge_deg=30, tags=("cushion",))
    G.xform(back.obj, rot=(-10, 0, 0), pivot=(0, 0.29, seat_z + 0.15))
    parts["back"].append(back)
    for sx in (-1, 1):
        loop = p.tube([(sx * 0.2, -0.05, seat_z - 0.04), (sx * 0.26, -0.05, seat_z + 0.2), (sx * 0.26, 0.15, seat_z + 0.2),
                       (sx * 0.22, 0.17, seat_z - 0.04)], 0.012, M.PL_BLACK, segs=6, fillet_r=0.05, steps=3)
        pad = p.rbox((0.06, 0.22, 0.03), (sx * 0.26, 0.05, seat_z + 0.215), M.PL_BLACK, radius=0.012, inner=(1, 2, 1),
                     edge_deg=30)
        parts["arms"] += [loop, pad]
    if p.cond == "worn":
        whole = list(p.parts)
        p.rotate([q for q in whole if q not in parts["base"]], rot=(0, 0, p.vrng("swivel").uniform(-35, 35)), pivot=(0, 0, 0))
    if p.destroyed:
        r = p.vrng("wreck")
        F.slash(p, (0.0, -0.05, seat_z + 0.035), 0.24, 30, key="seat")
        # backrest snapped off and lying apart, the chair tipped over on its side
        p.remove(parts["back"][:1])
        p.lay_on_floor(parts["back"][1:], rot=(-80, 0, 0), at=(0.7, 0.4), yaw=r.uniform(0, 90))
        rest = [q for q in p.parts if q not in parts["back"][1:]]
        p.rotate(rest, rot=(0, 95, 0), pivot=(0, 0, 0))
        lo, hi = p.bounds(rest)
        p.move(rest, (0, 0, -lo.z))
        p.collider((0.0, 0.0, 0.3), (0.95, 0.65, 0.6))
    else:
        p.collider((0, 0.03, 0.5), (0.62, 0.62, 1.0))


def filing_cabinet(p: Prop) -> None:
    """Putty steel 4-drawer vertical file 0.38 x 0.7 x 1.32: recessed pulls, card holders, lock."""
    W, D, H = 0.38, 0.7, 1.32
    steel = M.STEEL_BEIGE
    yf = -D / 2 + 0.015
    wr = 0.0 if p.cond == "clean" else (0.004 if p.cond == "worn" else 0.01)
    body = p.rbox((W, D - 0.015, H - 0.02), (0, 0.0075, H / 2 + 0.01), steel, radius=0.006, inner=(1, 3, 4), wrinkle=wr,
                  wrinkle_scale=4.0, seed=p.seed, edge_deg=25)
    body.floor_wear = 0.6
    p.box((W - 0.02, D - 0.04, 0.02), (0, 0.0, 0.01), M.PL_BLACK, bevel=0.0)
    p.cyl(0.012, 0.012, (0.14, yf - 0.002, H - 0.035), M.CHROME, axis="Y", segs=10, tags=("knob",))
    drawers = []
    dh = (H - 0.06) / 4
    for i in range(4):
        za, zb = 0.03 + i * dh + 0.006, 0.03 + (i + 1) * dh - 0.006
        k = f"f{i}"
        pull = 0.0
        if p.cond == "worn":
            pull = p.vrng(k).choice([0.0, 0.0, 0.0, 0.07])
        if p.destroyed:
            pull = [0.12, 0.4, 0.0, 0.25][i]
        grp = F.drawer(p, -W / 2 + 0.008, za, W / 2 - 0.008, zb, yf - 0.018, D - 0.08, steel, t=0.018, style="slab",
                       handle="none", pull=pull, key=k, box_mat=steel, contents=False)
        cz = (za + zb) / 2 + 0.05
        hz = (za + zb) / 2 - 0.02
        y0 = yf - 0.018 - pull
        grp.append(p.box((0.1, 0.008, 0.035), (0, y0 - 0.002, hz), M.PL_BLACK, bevel=0.002))
        grp.append(p.tube([(-0.06, y0, hz + 0.018), (-0.06, y0 - 0.02, hz + 0.01), (0.06, y0 - 0.02, hz + 0.01),
                           (0.06, y0, hz + 0.018)], 0.006, M.CHROME, segs=6, fillet_r=0.01, steps=2, tags=("knob",)))
        grp.append(p.box((0.075, 0.004, 0.035), (0, y0 - 0.002, cz), M.CHROME, bevel=0.0015))
        card = p.box((0.065, 0.002, 0.027), (0, y0 - 0.0045, cz), M.PAPER, bevel=0.0, uv="keep")
        core.set_face_uvs(card.obj, lambda poly: (*core.note_rect(0), 0, 2, False))
        grp.append(card)
        if pull > 0.1:  # hanging folders inside
            for j in range(5):
                grp.append(p.box((W - 0.06, 0.004, dh - 0.06), (0, y0 + 0.06 + j * 0.05, za + (dh - 0.06) / 2 + 0.02),
                                 M.CARDBOARD, bevel=0.0, uv="keep", tags=("paper",)))
                core.set_face_uvs(grp[-1].obj, lambda poly: (*core.card_rect(14), 0, 2, False))
        drawers.append(grp)
    if p.destroyed:
        r = p.vrng("wreck")
        p.lay_on_floor(drawers[3], rot=(r.uniform(-8, 8), 0, 0), at=(0.45, -0.85), yaw=r.uniform(40, 80))
        _papers(p, (0.1, -0.95, 0.0), 12, 0.45, "spill", z_step=0.0015, floor=True)
    p.collider((0, 0, H / 2), (W, D, H))


def metal_shelf(p: Prop) -> None:
    """Grey boltless steel shelving 0.92 x 0.45 x 1.83: angle posts, 5 lipped shelves, boxes and cans."""
    W, D, H = 0.92, 0.45, 1.83
    steel = M.STEEL_GREY
    posts = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * (W / 2 - 0.02), sy * (D / 2 - 0.02)
            a = p.box((0.04, 0.003, H), (x, y + sy * 0.0185, H / 2), steel, bevel=0.0, grain="Z", tags=("post",))
            b = p.box((0.003, 0.04, H), (x + sx * 0.0185, y, H / 2), steel, bevel=0.0, grain="Z", tags=("post",))
            posts += [a, b]
    zs = [0.1, 0.5, 0.9, 1.3, 1.78]
    shelves = []
    for z in zs:
        sh = [p.box((W - 0.01, D - 0.01, 0.004), (0, 0, z), steel, bevel=0.0, grain="X")]
        for sy in (-1, 1):
            sh.append(p.box((W - 0.01, 0.003, 0.035), (0, sy * (D / 2 - 0.006), z - 0.016), steel, bevel=0.0, grain="X"))
        for sx in (-1, 1):
            sh.append(p.box((0.003, D - 0.01, 0.035), (sx * (W / 2 - 0.006), 0, z - 0.016), steel, bevel=0.0, grain="Y"))
        shelves.append(sh)
    r = p.rng("stock")
    goods = {}
    for si, z in enumerate(zs[:-1]):
        items = []
        x = -W / 2 + 0.04
        while x < W / 2 - 0.12:
            k = r.random()
            if k < 0.5:
                w, d, h = r.uniform(0.18, 0.32), r.uniform(0.25, 0.38), r.uniform(0.15, 0.3)
                if x + w > W / 2 - 0.03:
                    break
                bx = F.package_box(p, (w, d, h), (x + w / 2, r.uniform(-0.02, 0.02), z + 0.002 + h / 2),
                                   14 if r.random() < 0.6 else r.randrange(14), rot=(0, 0, r.uniform(-4, 4)))
                items.append(bx)
                x += w + r.uniform(0.01, 0.04)
            elif k < 0.8:
                for j in range(r.randint(1, 3)):
                    items.append(F.can(p, 0.085, 0.19, (x + 0.09, -0.08 + j * 0.0, z + 0.097 + j * 0.0), r.randrange(14),
                                       mat=M.TIN if r.random() < 0.3 else M.CARDBOARD))
                    x += 0.18
                    if x > W / 2 - 0.12:
                        break
            else:
                x += r.uniform(0.08, 0.2)
        goods[si] = items
    if p.destroyed:
        rr = p.vrng("wreck")
        # third shelf's clips gave way at one end: it hangs diagonally, its load on the floor
        sh = shelves[2]
        p.rotate(sh, rot=(0, 24, 0), pivot=(-W / 2, 0, zs[2]))
        for i, it in enumerate(goods[2] + goods[3][: len(goods[3]) // 2]):
            p.lay_on_floor([it], rot=(rr.uniform(-90, 90), rr.choice([0, 90]), 0),
                           at=(rr.uniform(-0.7, 0.7), -0.45 - rr.uniform(0, 0.5)), yaw=rr.uniform(0, 180))
        # the whole unit racks sideways (parallelogram) a few degrees
        frame = [q for q in p.parts if "debris" not in q.tags and p.bounds([q])[0].y > -0.4]
        for q in frame:
            for v in q.obj.data.vertices:
                v.co.x += v.co.z * 0.06
            q.obj.data.update()
    p.collider((0, 0, H / 2), (W, D, H))


def weapons_locker(p: Prop) -> None:
    """Olive-drab steel weapons locker 0.9 x 0.5 x 1.8: louvred double doors, 3-point handle, padlocked
    hasp; rifle rack and ammo shelf inside."""
    W, D, H = 0.9, 0.5, 1.8
    steel = M.STEEL_GREEN
    yf = -D / 2
    body = p.hollow((W, D, H - 0.05), (0, 0, 0.05 + (H - 0.05) / 2), steel, wall=0.02, bevel=0.006, grain="Z")
    body.floor_wear = 0.7
    p.box((W - 0.02, D - 0.04, 0.05), (0, 0.01, 0.025), M.PL_BLACK, bevel=0.0)
    # interior: rifle rack (slotted rail + butt tray) and ammo shelf
    p.box((W - 0.06, 0.08, 0.03), (0, -0.05, 1.1), steel, bevel=0.003)
    for i in range(8):
        p.box((0.01, 0.06, 0.035), (-W / 2 + 0.09 + i * 0.1, -0.08, 1.11), M.RUBBER, bevel=0.0)
    p.box((W - 0.06, D - 0.08, 0.02), (0, 0.0, 1.45), steel, bevel=0.002)
    if not p.destroyed:
        for i in range(5):
            F.package_box(p, (0.14, 0.08, 0.09), (-0.3 + i * 0.15, 0.02, 1.46 + 0.045), [5, 13, 1][i % 3])
    p.box((W - 0.06, 0.25, 0.04), (0, -0.02, 0.07), steel, bevel=0.003)
    doors = {}
    zt, zb = H - 0.03, 0.08
    for side in (-1, 1):
        x0, x1 = (-W / 2 + 0.005, -0.004) if side < 0 else (0.004, W / 2 - 0.005)
        grp = [p.box((x1 - x0, 0.02, zt - zb), ((x0 + x1) / 2, yf - 0.01, (zt + zb) / 2), steel, bevel=0.004, grain="Z",
                     tags=("door",))]
        for zl in (zt - 0.18, zb + 0.08):  # louvres
            for j in range(5):
                grp.append(p.box(((x1 - x0) * 0.55, 0.012, 0.012), ((x0 + x1) / 2, yf - 0.022, zl + j * 0.022), steel,
                                 bevel=0.003))
        doors[side] = grp
    # handle + hasp on the right door edge
    hx = 0.06
    doors[1].append(p.box((0.04, 0.03, 0.16), (hx, yf - 0.035, 1.0), M.CHROME, bevel=0.006, tags=("knob",)))
    doors[-1].append(p.box((0.05, 0.012, 0.09), (-0.025, yf - 0.026, 0.84), M.CHROME, bevel=0.002))
    hasp = [p.box((0.07, 0.012, 0.035), (0.02, yf - 0.03, 0.84), M.CHROME, bevel=0.002)]
    lock = [p.rbox((0.05, 0.022, 0.05), (0.04, yf - 0.05, 0.79), M.BRASS, radius=0.008, inner=(1, 1, 1), edge_deg=30)]
    lock.append(p.tube([(0.025, yf - 0.05, 0.81), (0.025, yf - 0.05, 0.85), (0.055, yf - 0.05, 0.85), (0.055, yf - 0.05, 0.81)],
                       0.004, M.CHROME, segs=6, fillet_r=0.012, steps=2))
    doors[1] += hasp
    if p.destroyed:
        rr = p.vrng("wreck")
        # pried open: right door bent wide open, left door sprung ajar, padlock cut and on the floor
        p.lay_on_floor(lock, rot=(90, 0, 0), at=(0.35, -0.6), yaw=rr.uniform(0, 180))
        F.swing(p, doors[1], W / 2 - 0.005, yf, 115)
        for v in doors[1][0].obj.data.vertices:  # crowbar bend in the free edge
            if v.co.z > 0.7 and v.co.z < 1.2:
                v.co.y -= 0.03 * math.sin((v.co.z - 0.7) / 0.5 * math.pi)
        F.swing(p, doors[-1], -W / 2 + 0.005, yf, -24)
    elif p.cond == "worn":
        ang = p.vrng("ajar").choice([0.0, 0.0, 4.0])
        if ang:
            F.swing(p, doors[-1], -W / 2 + 0.005, yf, -ang)
    p.collider((0, 0, H / 2), (W, D, H))


def safe_small(p: Prop) -> None:
    """Small floor safe 0.45 x 0.45 x 0.55: thick black steel body, recessed door, dial and lever handle."""
    W, D, H = 0.45, 0.45, 0.55
    steel = M.STEEL_BLACK
    yf = -D / 2
    p.hollow((W, D, H - 0.03), (0, 0, 0.03 + (H - 0.03) / 2), steel, wall=0.06, bevel=0.012, grain="Z", back=0.06)
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.box((0.06, 0.06, 0.03), (sx * (W / 2 - 0.05), sy * (D / 2 - 0.05), 0.015), M.PL_BLACK, bevel=0.004)
    if not p.destroyed:
        F.package_box(p, (0.16, 0.12, 0.05), (0.0, 0.0, 0.09 + 0.025), 7)
    _papers(p, (0, 0.02, 0.09), 3, 0.03, "safe_papers")
    door = [p.box((W - 0.07, 0.07, H - 0.1), (0, yf + 0.03, 0.03 + (H - 0.03) / 2), steel, bevel=0.008, grain="Z", tags=("door",))]
    dc = (0.04, yf - 0.006, 0.36)
    dial = [p.lathe([(0.05, 0.0), (0.052, 0.01), (0.045, 0.018), (0.038, 0.025), (0.0, 0.026)], dc, M.CHROME, segs=16,
                    axis="-Y", tags=("knob",))]
    dial.append(p.lathe([(0.028, 0.0), (0.03, 0.02), (0.022, 0.03), (0.0, 0.031)], (dc[0], dc[1] - 0.025, dc[2]), M.PL_BLACK,
                        segs=10, axis="-Y", tags=("knob",)))
    door += dial
    hub = p.cyl(0.02, 0.03, (0.04, yf - 0.02, 0.2), M.CHROME, axis="Y", segs=10)
    lever = p.box((0.13, 0.02, 0.025), (0.1, yf - 0.035, 0.2), M.CHROME, bevel=0.006, tags=("knob",))
    door += [hub, lever]
    for z in (0.12, 0.42):
        p.cyl(0.018, 0.08, (-W / 2 + 0.04, yf - 0.012, z), M.STEEL_BLACK, segs=8)
    if p.destroyed:
        rr = p.vrng("wreck")
        p.remove(dial)
        door = [q for q in door if q not in dial]
        stub = p.cyl(0.012, 0.03, dc, M.CHROME, axis="Y", segs=6)
        door.append(stub)
        F.swing(p, door, -W / 2 + 0.035, yf + 0.06, -rr.uniform(70, 100))
        knob = p.lathe([(0.05, 0.0), (0.052, 0.01), (0.045, 0.018), (0.038, 0.025), (0.0, 0.026)], (0, 0, 0), M.CHROME,
                       segs=16, tags=("knob", "debris"))
        p.lay_on_floor([knob], at=(0.35, -0.5), yaw=0)
    p.collider((0, 0, H / 2), (W, D, H))


def cork_board(p: Prop) -> None:
    """Wall cork board 0.9 x 0.6 (origin on the wall plane): oak frame, pinned notices and push pins."""
    W, H, T = 0.9, 0.6, 0.012
    fw = 0.03
    p.box((W - 2 * fw, T, H - 2 * fw), (0, -T / 2, H / 2), M.CORK, bevel=0.0, uv_scale=1.0)
    for sx in (-1, 1):
        p.box((fw, 0.022, H), (sx * (W / 2 - fw / 2), -0.011, H / 2), M.OAK, bevel=0.004, grain="Z")
    for sz in (-1, 1):
        p.box((W - 2 * fw, 0.022, fw), (0, -0.011, H / 2 + sz * (H / 2 - fw / 2)), M.OAK, bevel=0.004, grain="X")
    r = p.rng("notes")
    spots = [(-0.27, 0.36), (-0.02, 0.4), (0.25, 0.38), (-0.25, 0.17), (0.05, 0.16), (0.3, 0.15)]
    for i, (x, z) in enumerate(spots):
        if p.worn and p.chance(f"gone{i}", 0.3):
            continue
        w, h = r.uniform(0.13, 0.2), r.uniform(0.15, 0.22)
        sh = p.box((w, 0.0015, h), (0, 0, 0), M.PAPER, bevel=0.0, uv="keep", tags=("paper",))
        core.set_face_uvs(sh.obj, lambda poly, k=r.randrange(4): (*core.note_rect(k), 0, 2, False))
        tilt = r.uniform(-6, 6) + (r.uniform(-25, 25) if p.worn else 0.0)
        G.xform(sh.obj, rot=(0, tilt, 0), loc=(x, -T - 0.001 - i * 0.0004, z))
        p.cyl(0.006, 0.012, (x + r.uniform(-0.02, 0.02), -T - 0.006, z + h / 2 - 0.02),
              [M.PL_RED, M.PL_BLUE, M.PL_WHITE, M.BRASS][i % 4], axis="Y", segs=6, tags=("knob",))
    p.collider((0, -0.011, H / 2), (W, 0.022, H))


def water_cooler(p: Prop) -> None:
    """Bottled water cooler: beige plastic cabinet 0.32 x 0.32 x 0.95 with taps and drip tray, 5-gallon
    blue bottle upside down on top."""
    W, H = 0.32, 0.95
    p.rbox((W, W, H), (0, 0, H / 2), M.PL_BEIGE, radius=0.02, inner=(1, 1, 3), edge_deg=30)
    p.box((0.2, 0.05, 0.2), (0, -W / 2 - 0.005, 0.72), M.PL_GREY, bevel=0.008)
    for sx, mat in ((-0.05, M.PL_BLUE), (0.05, M.PL_RED)):
        p.box((0.03, 0.04, 0.035), (sx, -W / 2 - 0.045, 0.76), mat, bevel=0.006, tags=("knob",))
    p.box((0.18, 0.08, 0.02), (0, -W / 2 - 0.03, 0.6), M.PL_GREY, bevel=0.004)
    bottle_prof = [(0.03, 0.0), (0.03, 0.06), (0.09, 0.1), (0.13, 0.15), (0.135, 0.22), (0.13, 0.3), (0.135, 0.38),
                   (0.13, 0.44), (0.1, 0.48), (0.0, 0.49)]
    bottle = p.lathe(bottle_prof, (0, 0, H - 0.03), M.PL_BLUE, segs=16, cap_bottom=True, edge_deg=45)
    if p.destroyed:
        r = p.vrng("wreck")
        # bottle knocked off, split open on the floor
        G.splinter_cut(bottle.obj, (0, 0, H + 0.33), (0.3, 0.1, 1.0), jag=0.03, seed=p.seed)
        p.lay_on_floor([bottle], rot=(90, 0, 0), at=(0.45, -0.3), yaw=r.uniform(0, 90))
    p.collider((0, 0, (H + 0.46) / 2), (W, W, H + 0.46))


def counter_reception(p: Prop) -> None:
    """Reception / front-office counter 1.8 x 0.75 x 1.05: woodgrain-laminate front with raised transaction
    ledge, staff desk surface at 0.74 behind (toward +Y) with a drawer pedestal."""
    W, D = 1.8, 0.75
    lam = M.LAM_WOOD
    yf = -D / 2
    front = p.panel(W, 1.0, 0.03, (0, yf + 0.015, 0.5), lam, style="groove", frame=0.12, recess=0.004, tags=("panel",))
    p.box((W, 0.05, 0.08), (0, yf + 0.04, 0.04), M.PL_BLACK, bevel=0.003)
    ledge = p.box((W + 0.02, 0.32, 0.032), (0, yf + 0.12, 1.05 - 0.016), M.LAMINATE, bevel=0.005, grain="X")
    for sx in (-1, 1):
        p.box((0.025, D - 0.03, 1.02), (sx * (W / 2 - 0.0125), 0.0, 0.51), lam, bevel=0.003, grain="Z")
    p.box((W - 0.05, D - 0.06, 0.03), (0, 0.04, 0.74 - 0.015), lam, bevel=0.004, grain="X")
    p.box((W - 0.05, 0.03, 0.3), (0, yf + 0.06, 0.9), lam, bevel=0.003, grain="X")
    # staff-side pedestal (drawers face +Y)
    px = W / 2 - 0.25
    p.box((0.42, 0.5, 0.68), (px, 0.08, 0.36), lam, bevel=0.003, grain="Z")
    for i, (za, zb) in enumerate(((0.47, 0.69), (0.05, 0.45))):
        k = f"rd{i}"
        pull = 0.0 if p.cond == "clean" else p.vrng(k).choice([0.0, 0.08])
        # built facing -Y at the mirrored position, then turned 180 deg to face the staff side (+Y)
        grp = F.drawer(p, px - 0.2, za, px + 0.2, zb, -(0.33 + 0.019), 0.4, lam, pull=pull, handle="bar", key=k,
                       style="slab", contents=False)
        p.rotate(grp, rot=(0, 0, 180), pivot=(px, 0.0, 0))
    # counter top clutter: bell, pamphlet rack, phone
    p.lathe([(0.045, 0.0), (0.045, 0.01), (0.04, 0.03), (0.02, 0.05), (0.006, 0.055), (0.006, 0.065), (0.0, 0.066)],
            (-0.55, yf + 0.12, 1.05), M.BRASS, segs=12)
    p.hollow((0.3, 0.08, 0.18), (0.4, yf + 0.14, 1.05 + 0.09), M.PL_WHITE, wall=0.004, open_face="+Z", bevel=0.0)
    r = p.rng("pamph")
    for i in range(3):
        pm = p.box((0.09, 0.006, 0.2), (0.3 + i * 0.1, yf + 0.14, 1.05 + 0.11), M.CARDBOARD, bevel=0.0, uv="keep")
        core.set_face_uvs(pm.obj, lambda poly, k=r.randrange(14): (*core.card_rect(k), 0, 2, poly.normal.y > 0))
    _desk_phone(p, (-0.3, 0.2, 0.74), yaw=170)
    if p.worn:
        _papers(p, (0.1, 0.2, 0.74), 7, 0.25, "staff_papers")
    if p.destroyed:
        p.remove([front])
        h1, h2 = F.split_panel(p, W, 1.0, 0.03, (0, yf + 0.015, 0.5), lam, (-0.25, -0.5), (0.1, 0.5), plane="XZ",
                               key="front", teeth=9, amp=0.04)
        lo, hi = p.bounds([h2])
        right = (lo.x + hi.x) / 2 > 0
        p.rotate([h2], rot=(-25, 0, 0), pivot=(0, yf, 0.0))
        p.rotate([h2], rot=(0, 0, 8 if right else -8), pivot=(W / 2 if right else -W / 2, yf, 0))
        p.rotate([ledge], rot=(0, -5, 0), pivot=(-W / 2, 0, 1.03))
        _papers(p, (0.0, -0.75, 0.0), 12, 0.6, "lobby_papers", z_step=0.0015, floor=True)
    p.collider((0, 0, 0.525), (W, D, 1.05))


BUILDERS = {
    "office_desk": office_desk,
    "office_chair": office_chair,
    "filing_cabinet": filing_cabinet,
    "metal_shelf": metal_shelf,
    "weapons_locker": weapons_locker,
    "safe_small": safe_small,
    "cork_board": cork_board,
    "water_cooler": water_cooler,
    "counter_reception": counter_reception,
}


def build(params: dict, outputs: list[str]) -> None:
    core.build_variants(params, outputs, BUILDERS[params["prop"]])
