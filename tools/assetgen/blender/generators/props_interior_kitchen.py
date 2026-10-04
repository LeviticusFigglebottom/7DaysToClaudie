"""Interior props - kitchen: base cabinets, sink base, wall cabinet, fridge, stove, microwave, table,
chair, trash can, dish clutter. 1990s small-town kitchens: golden-oak raised-panel cabinets, beige
laminate worktops, almond enamel appliances.

params: prop (id), seed, variants [clean, worn, destroyed?], mount, budget. See blender_catalogs/props_interior.py.
"""
from __future__ import annotations

import math

from lib import props_int_core as core
from lib import props_int_furn as F
from lib import props_int_mesh as G
from lib.props_int_core import M, Prop

# Base cabinet standard: 0.9 m worktop height, 0.6 m deep incl. doors, 0.1 m toe kick.
H_TOP = 0.9
T_TOP = 0.032
Y_BACK = 0.3
CAR_D = 0.56
Y_FACE = Y_BACK - CAR_D  # -0.26 front of the face frame
T_DOOR = 0.019


def _base_carcass(p: Prop, W: float, wood: str, *, top: bool = True) -> dict:
    kick = 0.1
    ztop = H_TOP - T_TOP
    p.box((W - 0.012, CAR_D - 0.075, kick), (0, Y_BACK - (CAR_D - 0.075) / 2, kick / 2), M.DARK, bevel=0.002, grain="X")
    parts = F.carcass(p, W, Y_FACE, Y_BACK, kick, ztop, wood, top=top, rails=((0.67, 0.05),))
    p.box((W - 0.06, CAR_D - 0.06, 0.016), (0, Y_BACK - CAR_D / 2 + 0.02, 0.4), M.PARTICLE, bevel=0.001, wear=0.3)
    if not top:  # sink base: front and back stretchers only
        p.box((W - 0.04, 0.08, 0.018), (0, Y_BACK - 0.05, ztop - 0.009), wood, bevel=0.001, grain="X")
    return parts


def _worktop(p: Prop, W: float, *, hole=None, broken: bool = False) -> None:
    """Post-formed laminate top (rounded front edge) + backsplash. hole = (x0, y0, x1, y1) sink cut-out."""
    D = 0.625
    y0, y1 = Y_BACK - D, Y_BACK
    zc = H_TOP - T_TOP / 2
    if hole is None and not broken:
        p.rbox((W, D, T_TOP), (0, (y0 + y1) / 2, zc), M.LAMINATE, radius=0.01, inner=(4, 3, 1), rs=1, edge_deg=30,
               uv_scale=1.0)
    elif hole is not None:
        hx0, hy0, hx1, hy1 = hole
        p.rbox((W, hy0 - y0, T_TOP), (0, (y0 + hy0) / 2, zc), M.LAMINATE, radius=0.01, inner=(3, 1, 1), rs=1, edge_deg=30)
        for (a, b, c, d) in ((-W / 2, hy1, W / 2, y1), (-W / 2, hy0, hx0, hy1), (hx1, hy0, W / 2, hy1)):
            p.box((c - a, d - b, T_TOP), ((a + c) / 2, (b + d) / 2, zc), M.LAMINATE, bevel=0.004)
    else:
        # broken: front-left corner snapped off, particleboard core showing
        poly_w, poly_d = W, D
        a = (-W / 2, -D / 2 + 0.24)
        b = (-W / 2 + 0.32, -D / 2)
        q1, q2, b1, b2 = G.jagged_split(poly_w, poly_d, a, b, teeth=7, amp=0.02, seed=p.seed + 5)
        keep, keep_b = (q1, b1) if len(q1) >= len(q2) else (q2, b2)
        part = p.prism(keep, T_TOP, M.LAMINATE, plane="XY", offset=H_TOP - T_TOP, inner_mat=M.PARTICLE,
                       inner_edges=keep_b, bevel=0.002)
        G.xform(part.obj, loc=(0, (y0 + y1) / 2, 0))
        other, other_b = (q2, b2) if keep is q1 else (q1, b1)
        chunk = p.prism(other, T_TOP, M.LAMINATE, plane="XY", offset=0.0, inner_mat=M.PARTICLE, inner_edges=other_b,
                        bevel=0.002, tags=("debris",))
        p.lay_on_floor([chunk], rot=(0, 0, 0), at=(-W / 2 + 0.05, y0 - 0.32), yaw=p.rng("chunk").uniform(10, 40))
        p.rotate([chunk], rot=(8, -6, 0), pivot=tuple(p.bounds([chunk])[0]))
    p.box((W, 0.012, 0.1), (0, Y_BACK - 0.006, H_TOP + 0.05), M.LAMINATE, bevel=0.003, grain="X")


def _base_fronts(p: Prop, W: float, wood: str, *, drawer: bool = True, false_front: bool = False) -> dict:
    """Two raised-panel doors + one drawer on a face frame. Variant-dependent poses."""
    parts = {}
    zd0, zd1 = 0.125, 0.655
    zr0, zr1 = 0.685, 0.845
    # face frame centre stile (visible in the gap between the partial-overlay doors)
    p.box((0.05, 0.02, zd1 - zd0 + 0.02), (0, Y_FACE + 0.01, (zd0 + zd1) / 2), wood, bevel=0.002, grain="Z")
    yf = Y_FACE - T_DOOR
    open_l = open_r = 0.0
    if p.cond == "worn":
        open_l = p.vrng("door_l").choice([0.0, 4.0, 12.0])
        open_r = p.vrng("door_r").choice([0.0, 0.0, 18.0, 35.0])
    left = F.door(p, -W / 2 + 0.015, zd0, -0.012, zd1, yf, wood, hinge="left", open_deg=open_l, key="door_l",
                  style="raised", frame=0.06)
    right = F.door(p, 0.012, zd0, W / 2 - 0.015, zd1, yf, wood, hinge="right", open_deg=open_r, key="door_r",
                   style="raised", frame=0.06)
    parts["left"], parts["right"] = left, right
    if drawer:
        pull = 0.0
        if p.cond == "worn":
            pull = p.vrng("drawer").choice([0.0, 0.05, 0.11])
        if false_front:
            parts["drawer"] = [p.panel(W - 0.03, zr1 - zr0, T_DOOR, (0, yf + T_DOOR / 2, (zr0 + zr1) / 2), wood,
                                       style="raised", frame=0.035, tags=("drawer",))]
        else:
            parts["drawer"] = F.drawer(p, -W / 2 + 0.015, zr0, W / 2 - 0.015, zr1, yf, 0.45, wood, pull=pull, knobs=2,
                                       frame=0.035, key="drawer")
    return parts


def _destroy_fronts(p: Prop, parts: dict, W: float) -> None:
    """Destroyed base cabinet: left door torn off onto the floor, right door hanging from one hinge,
    drawer yanked out and dumped."""
    r = p.vrng("wreck")
    F.lay_flat(p, parts["left"], at=(-0.25 + r.uniform(-0.1, 0.1), Y_FACE - 0.45), yaw=r.uniform(-25, 25))
    F.hang(p, parts["right"], W / 2 - 0.015, Y_FACE, 0.62, open_deg=r.uniform(65, 95), sag_deg=r.uniform(6, 11),
           hinge="right")
    if "drawer" in parts and len(parts["drawer"]) > 1:
        p.lay_on_floor(parts["drawer"], rot=(r.uniform(-8, 8), 180 if r.random() < 0.5 else 0, r.uniform(-30, 30)),
                       at=(0.35, Y_FACE - 0.75))


def kitchen_counter(p: Prop) -> None:
    W = 1.0
    wood = M.OAK
    _base_carcass(p, W, wood)
    parts = _base_fronts(p, W, wood)
    if p.destroyed:
        # make the drawer pullable so it has a box to dump
        p.remove(parts["drawer"])
        parts["drawer"] = F.drawer(p, -W / 2 + 0.015, 0.685, W / 2 - 0.015, 0.845, Y_FACE - T_DOOR, 0.45, wood, pull=0.3,
                                   knobs=2, frame=0.035, key="drawer")
        _destroy_fronts(p, parts, W)
        _worktop(p, W, broken=True)
    else:
        _worktop(p, W)
    p.collider((0, 0.0, H_TOP / 2), (W, 0.6, H_TOP))


def kitchen_counter_sink(p: Prop) -> None:
    W = 1.0
    wood = M.OAK
    _base_carcass(p, W, wood, top=False)
    parts = _base_fronts(p, W, wood, false_front=True)
    hole = (-0.27, -0.21, 0.27, 0.18)
    _worktop(p, W, hole=hole)
    # stainless single bowl with rolled rim
    bx, by = 0.0, (hole[1] + hole[3]) / 2
    bw, bd = hole[2] - hole[0], hole[3] - hole[1]
    p.hollow((bw - 0.01, bd - 0.01, 0.19), (bx, by, H_TOP - 0.095), M.STAINLESS, wall=0.006, open_face="+Z", bevel=0.0,
             uv_scale=1.0, wear=0.3)
    rim = 0.03
    for (cx, cy, sx, sy) in ((bx, hole[1] - rim / 2 + 0.006, bw + 2 * rim, rim), (bx, hole[3] + rim / 2 - 0.006, bw + 2 * rim, rim),
                             (hole[0] - rim / 2 + 0.006, by, rim, bd), (hole[2] + rim / 2 - 0.006, by, rim, bd)):
        p.box((sx, sy, 0.006), (cx, cy, H_TOP + 0.003), M.STAINLESS, bevel=0.002, wear=0.4)
    p.cyl(0.035, 0.004, (bx, by + 0.03, H_TOP - 0.188), M.CHROME, segs=12, wear=0.3)
    p.cyl(0.02, 0.003, (bx, by + 0.03, H_TOP - 0.186), M.PL_BLACK, segs=10)
    # P-trap and supply lines under the bowl (seen through open doors)
    trap = [(bx, by + 0.03, H_TOP - 0.19), (bx, by + 0.03, 0.5), (bx, by - 0.02, 0.44), (bx, by + 0.06, 0.4),
            (bx, by + 0.12, 0.47), (bx, Y_BACK, 0.47)]
    p.tube(trap, 0.019, M.PL_WHITE, segs=6, fillet_r=0.05, steps=2, wear=0.4)
    for sx in (-0.07, 0.07):
        p.tube([(sx, hole[3] + 0.035, H_TOP - 0.03), (sx, hole[3] + 0.035, 0.45), (sx, Y_BACK, 0.4)], 0.005, M.CHROME,
               segs=6, fillet_r=0.05, steps=2)
    # two-handle faucet on a deck plate behind the bowl
    fy = hole[3] + 0.035
    faucet = []
    faucet.append(p.box((0.2, 0.05, 0.03), (0, fy, H_TOP + 0.015), M.CHROME, bevel=0.01, segs=2, wear=0.5))
    for sx in (-0.07, 0.07):
        faucet.append(p.lathe([(0.012, 0), (0.014, 0.012), (0.022, 0.026), (0.016, 0.04), (0.0, 0.043)],
                              (sx, fy, H_TOP + 0.03), M.CHROME, segs=8, tags=("knob",)))
    spout = [(0, fy, H_TOP + 0.03), (0, fy, H_TOP + 0.085), (0, fy - 0.16, H_TOP + 0.085), (0, fy - 0.16, H_TOP + 0.06)]
    faucet.append(p.tube(spout, 0.01, M.CHROME, segs=8, fillet_r=0.035, steps=3, wear=0.6))
    if p.worn:
        # a rag hanging over the bowl edge and a forgotten pot
        p.rbox((0.22, 0.12, 0.012), (0.12, hole[1] + 0.02, H_TOP + 0.004), M.TOWEL, radius=0.004, inner=(4, 2, 1),
               wrinkle=0.006, seed=p.seed, tags=("cloth",))
    if p.destroyed:
        r = p.vrng("wreck")
        F.lay_flat(p, parts["left"], at=(-0.2, Y_FACE - 0.4), yaw=r.uniform(-25, 25))
        F.hang(p, parts["right"], W / 2 - 0.015, Y_FACE, 0.62, open_deg=85, sag_deg=9, hinge="right")
        # spout snapped off and lying in the bowl
        spout_part = faucet[-1]
        p.rotate([spout_part], rot=(70, 0, 25), pivot=(0, fy, H_TOP + 0.03))
        p.move([spout_part], (0.05, -0.12, -0.13))
    p.collider((0, 0.0, H_TOP / 2), (W, 0.6, H_TOP))


def kitchen_wall_cabinet(p: Prop) -> None:
    """Wall-hung (origin on the wall plane, bottom centre): 0.8 x 0.32 x 0.7, two doors, knobs low."""
    W, Dc, H = 0.8, 0.3, 0.7
    wood = M.OAK
    p.hollow((W, Dc, H), (0, -Dc / 2, H / 2), wood, wall=0.028, open_face="-Y", bevel=0.003, grain="Z")
    yf = -Dc - T_DOOR
    for z in (0.24, 0.47):
        p.box((W - 0.06, Dc - 0.04, 0.016), (0, -Dc / 2 + 0.01, z), M.PARTICLE, bevel=0.001, wear=0.3)
    # shelf contents (visible through open doors)
    r = p.rng("contents")
    for zi, z in enumerate((0.028, 0.248, 0.478)):
        x = -W / 2 + 0.06
        while x < W / 2 - 0.12:
            kind = r.random()
            if kind < 0.45:
                h = r.uniform(0.09, 0.2)
                F.package_box(p, (r.uniform(0.05, 0.08), r.uniform(0.06, 0.16), h), (x + 0.04, -Dc / 2 + r.uniform(-0.03, 0.03), z + h / 2),
                              r.randrange(14))
                x += 0.1
            elif kind < 0.8:
                F.can(p, 0.038, 0.11, (x + 0.04, -Dc / 2 + r.uniform(-0.05, 0.05), z + 0.055), r.randrange(14))
                x += 0.09
            else:
                x += r.uniform(0.05, 0.15)
    open_l = open_r = 0.0
    if p.cond == "worn":
        open_l = p.vrng("dl").choice([0.0, 8.0, 25.0])
        open_r = p.vrng("dr").choice([0.0, 14.0, 48.0])
    left = F.door(p, -W / 2 + 0.012, 0.012, -0.004, H - 0.012, yf, wood, hinge="left", open_deg=open_l, key="door_l",
                  handle_at="bottom", frame=0.055)
    right = F.door(p, 0.004, 0.012, W / 2 - 0.012, H - 0.012, yf, wood, hinge="right", open_deg=open_r, key="door_r",
                   handle_at="bottom", frame=0.055)
    if p.destroyed:
        p.remove(left)
        F.hang(p, right, W / 2 - 0.012, -Dc, H - 0.08, open_deg=100, sag_deg=12, hinge="right")
    p.collider((0, -(Dc + T_DOOR) / 2, H / 2), (W, Dc + T_DOOR, H))


# ------------------------------------------------------------------------------------------------
# appliances
# ------------------------------------------------------------------------------------------------


def _magnet_papers(p: Prop, x0: float, x1: float, z0: float, z1: float, y: float, key: str) -> list:
    """Papers held by magnets on an appliance door (child's drawing, notes). Returns the parts."""
    r = p.rng(key)
    out = []
    for i in range(r.randint(2, 3)):
        w, h = r.uniform(0.13, 0.2), r.uniform(0.16, 0.24)
        cx, cz = r.uniform(x0 + w / 2, x1 - w / 2), r.uniform(z0 + h / 2, z1 - h / 2)
        cell = [3, 0, 2, 1][i % 4]
        part = p.box((w, 0.0015, h), (0, 0, 0), M.PAPER, bevel=0.0, uv="keep", tags=("paper",), wear=0.2, ring=0)
        core.set_face_uvs(part.obj, lambda poly, c=cell: (*core.note_rect(c), 0, 2, poly.normal.y > 0))
        G.xform(part.obj, rot=(0, r.uniform(-8, 8), 0), loc=(cx, y - 0.001, cz))
        out.append(part)
        mz = cz + h / 2 - 0.02
        out.append(p.cyl(0.012, 0.008, (cx + r.uniform(-0.03, 0.03), y - 0.006, mz), [M.PL_RED, M.PL_BLUE, M.PL_WHITE][i % 3],
                         axis="Y", segs=8, tags=("knob",)))
    return out


def fridge_old(p: Prop) -> None:
    """Almond top-freezer refrigerator (0.76 x 0.74 x 1.68), hinged right."""
    W, y_f, y_b, z0, z1 = 0.76, -0.28, 0.36, 0.03, 1.68
    D = y_b - y_f
    body = p.hollow((W, D, z1 - z0), (0, (y_f + y_b) / 2, (z0 + z1) / 2), M.ENAMEL, wall=0.045, bevel=0.012, grain="Z")
    body.floor_wear = 0.6
    for sx in (-0.33, 0.33):
        p.cyl(0.016, z0, (sx, y_f + 0.05, z0 / 2), M.RUBBER, segs=8)
    p.box((W - 0.09, D - 0.08, 0.05), (0, (y_f + y_b) / 2 + 0.02, 1.215), M.ENAMEL, bevel=0.01, wear=0.3)
    for z in (0.62, 0.93):
        p.box((W - 0.1, D - 0.12, 0.008), (0, (y_f + y_b) / 2 + 0.03, z), M.CHROME, bevel=0.0, wear=0.4, ring=0)
    for sx in (-0.17, 0.17):
        p.hollow((0.32, D - 0.16, 0.18), (sx, (y_f + y_b) / 2 + 0.04, z0 + 0.045 + 0.09), M.PL_WHITE, wall=0.006,
                 open_face="+Z", bevel=0.0, wear=0.3)
    # toe grille
    p.box((W - 0.08, 0.02, 0.09), (0, y_f + 0.02, z0 + 0.045), M.PL_BLACK, bevel=0.002)
    for i in range(4):
        p.box((W - 0.12, 0.01, 0.008), (0, y_f + 0.008, z0 + 0.012 + i * 0.022), M.PL_BLACK, bevel=0.0, ring=0)
    # gasket line
    p.box((W - 0.02, 0.008, z1 - 0.15), (0, y_f - 0.004, (0.14 + z1) / 2), M.RUBBER, bevel=0.0, ring=0)
    # food (seen when the doors are open)
    r = p.rng("food")
    for zs in (z0 + 0.235, 0.624, 0.934):
        x = -W / 2 + 0.09
        while x < W / 2 - 0.12:
            k = r.random()
            if k < 0.3:
                F.package_box(p, (0.07, 0.07, 0.2), (x, r.uniform(-0.1, 0.12), zs + 0.1), r.randrange(14))
            elif k < 0.6:
                F.can(p, 0.033, 0.12, (x, r.uniform(-0.1, 0.12), zs + 0.06), r.randrange(14))
            elif k < 0.8:
                p.rbox((r.uniform(0.08, 0.14), r.uniform(0.08, 0.12), r.uniform(0.03, 0.06)), (x, r.uniform(-0.08, 0.1), zs + 0.025),
                       M.MOLD, radius=0.02, inner=(2, 2, 1), wrinkle=0.008, seed=r.randrange(999), tags=("food",))
            x += r.uniform(0.11, 0.18)
    dy = -0.0575
    yd = y_f - 0.007
    fz_open = rz_open = 0.0
    if p.cond == "worn":
        fz_open = p.vrng("fz").choice([0.0, 3.0, 9.0])
        rz_open = p.vrng("rz").choice([0.0, 6.0, 14.0])
    wr = 0.0 if p.cond == "clean" else (0.004 if p.cond == "worn" else 0.009)
    frz = [p.rbox((W, 0.055, 0.43), (0, yd + dy / 2, 1.465), M.ENAMEL, radius=0.016, inner=(3, 1, 3),
                  wrinkle=wr, wrinkle_scale=5.0, seed=p.seed + 1, edge_deg=30)]
    hx = -W / 2 + 0.06
    frz.append(p.tube([(hx, yd + dy, 1.29), (hx, yd + dy - 0.035, 1.31), (hx, yd + dy - 0.035, 1.42), (hx, yd + dy, 1.44)],
                      0.011, M.PL_BEIGE, segs=6, fillet_r=0.02, steps=2, tags=("knob",), wear=1.5))
    frs = [p.rbox((W, 0.055, 1.07), (0, yd + dy / 2, 0.68), M.ENAMEL, radius=0.016, inner=(3, 1, 6),
                  wrinkle=wr, wrinkle_scale=4.0, seed=p.seed + 2, edge_deg=30)]
    frs.append(p.tube([(hx, yd + dy, 0.95), (hx, yd + dy - 0.035, 0.97), (hx, yd + dy - 0.035, 1.16), (hx, yd + dy, 1.18)],
                      0.011, M.PL_BEIGE, segs=6, fillet_r=0.02, steps=2, tags=("knob",), wear=1.5))
    # door shelves on the inner face of the fresh-food door
    for z in (0.45, 0.8):
        frs.append(p.hollow((W - 0.14, 0.09, 0.07), (0, y_f - 0.06 - 0.045 + 0.0, z), M.PL_WHITE, wall=0.005, open_face="+Z",
                            bevel=0.0, wear=0.3))
        p.move(frs[-1:], (0, 0.115, 0))
    frs += _magnet_papers(p, -0.25, 0.3, 0.75, 1.15, yd + dy, "fridge_papers")
    hinge_x = W / 2
    if fz_open:
        F.swing(p, frz, hinge_x, y_f, fz_open)
    if rz_open:
        F.swing(p, frs, hinge_x, y_f, rz_open)
    if p.destroyed:
        r = p.vrng("wreck")
        F.hang(p, frz, hinge_x, y_f, 1.64, open_deg=r.uniform(95, 115), sag_deg=r.uniform(5, 9), hinge="right")
        p.lay_on_floor(frs, rot=(90, 0, 0), at=(-0.15, y_f - 0.9), yaw=r.uniform(-20, 20))
    for i in range(2):
        F.package_box(p, (0.19, 0.07, 0.28), (-0.15 + i * 0.22, 0.05 + i * 0.03, z1 + 0.14), [4, 9][i],
                      rot=(0, 0, p.rng("top").uniform(-12, 12)))
    p.collider((0, (y_f - 0.06 + y_b) / 2, z1 / 2), (W, D + 0.06, z1))


def _burner(p: Prop, x: float, y: float, z: float, r: float) -> None:
    p.lathe([(r * 1.25, 0.0), (r * 1.3, 0.004), (r * 1.1, 0.012), (0.0, 0.0)], (x, y, z), M.CHROME, segs=12,
            cap_bottom=False, cap_top=False, wear=0.8, ring=0)
    prof = [(0.012, 0.0)]
    for i in range(3):
        rr = 0.02 + (r - 0.025) * i / 2
        prof += [(rr, 0.006), (rr + 0.008, 0.012), (rr + 0.016, 0.006)]
    prof += [(r + 0.012, 0.0)]
    p.lathe(prof, (x, y, z + 0.006), M.CAST_IRON, segs=12, cap_bottom=True, cap_top=False, wear=0.6, ring=0)


def stove_old(p: Prop) -> None:
    """Almond freestanding electric range: 4 coil burners, backguard with knobs + clock, oven door with
    window (hinged at the bottom), storage drawer. 0.76 x 0.68 x 0.91 (backguard to 1.13)."""
    W, y_f, y_b = 0.76, -0.3, 0.34
    D = y_b - y_f
    body = p.hollow((W, D, 0.82), (0, (y_f + y_b) / 2, 0.06 + 0.41), M.ENAMEL, wall=0.04, bevel=0.006, grain="Z")
    body.floor_wear = 0.6
    p.box((W - 0.04, D - 0.06, 0.06), (0, (y_f + y_b) / 2 + 0.03, 0.03), M.PL_BLACK, bevel=0.0, ring=0)
    # oven liner + racks + floor divider
    p.hollow((W - 0.1, D - 0.1, 0.5), (0, (y_f + y_b) / 2 + 0.01, 0.48), M.CAST_IRON, wall=0.01, bevel=0.0, wear=0.3)
    p.box((W - 0.08, D - 0.06, 0.03), (0, (y_f + y_b) / 2 + 0.02, 0.215), M.ENAMEL, bevel=0.0, ring=0)
    for z in (0.38, 0.55):
        p.box((W - 0.12, D - 0.14, 0.006), (0, (y_f + y_b) / 2 + 0.02, z), M.CHROME, bevel=0.0, ring=0, wear=0.6)
    # cooktop + burners
    p.box((W, D + 0.02, 0.025), (0, (y_f + y_b) / 2 - 0.01, 0.8925 + 0.0125), M.ENAMEL, bevel=0.006, grain="X")
    zt = 0.905
    missing = p.vrng("burner_missing").randrange(4) if p.worn else -1
    for i, (bx, by, br) in enumerate(((-0.19, -0.13, 0.085), (0.19, -0.13, 0.065), (-0.19, 0.12, 0.065), (0.19, 0.12, 0.085))):
        if i == missing:
            p.cyl(br * 1.25, 0.004, (bx, by, zt + 0.002), M.CAST_IRON, segs=12, wear=0.2)
            continue
        _burner(p, bx, by, zt, br)
    # backguard: clock window and four knobs
    p.box((W, 0.07, 0.2), (0, y_b - 0.035, zt + 0.1), M.ENAMEL, bevel=0.008, grain="X")
    p.box((0.32, 0.004, 0.08), (0, y_b - 0.071, zt + 0.1), M.GLASS, bevel=0.0, ring=0)
    p.box((0.09, 0.003, 0.03), (0.0, y_b - 0.074, zt + 0.1), M.PL_GREY, bevel=0.0, ring=0)
    for i, kx in enumerate((-0.32, -0.24, 0.24, 0.32)):
        if p.worn and p.chance(f"sknob{i}", 0.25):
            continue
        p.lathe([(0.02, 0.0), (0.021, 0.012), (0.017, 0.024), (0.0, 0.026)], (kx, y_b - 0.07, zt + 0.1), M.PL_BLACK,
                segs=10, axis="-Y", tags=("knob",), wear=1.4)
    yd = y_f - 0.045
    door = [p.panel(W - 0.02, 0.5, 0.045, (0, y_f - 0.0225, 0.49), M.ENAMEL, style="slab", bevel=0.006, tags=("door",))]
    door.append(p.box((0.5, 0.006, 0.25), (0, yd - 0.001, 0.52), M.PL_BLACK, bevel=0.002, ring=0))
    if not p.destroyed:
        door.append(p.box((0.44, 0.004, 0.19), (0, yd - 0.004, 0.52), M.GLASS, bevel=0.0, ring=0))
    else:
        door += F.shatter_pane(p, 0.44, 0.19, (0, yd - 0.004, 0.52), M.GLASS, t=0.004, spokes=8, rings=2, key="oven_glass",
                               missing_inner=0.9, missing_outer=0.4)
    door.append(p.tube([(-0.3, yd, 0.7), (-0.3, yd - 0.04, 0.705), (0.3, yd - 0.04, 0.705), (0.3, yd, 0.7)], 0.011, M.CHROME,
                       segs=8, fillet_r=0.02, steps=2, tags=("knob",), wear=1.3))
    drawer = [p.panel(W - 0.02, 0.15, 0.03, (0, y_f - 0.015, 0.145), M.ENAMEL, style="slab", bevel=0.005, tags=("drawer",))]
    drawer.append(p.box((0.3, 0.012, 0.02), (0, y_f - 0.031, 0.19), M.PL_BLACK, bevel=0.003, ring=0))
    if p.cond == "worn":
        ang = p.vrng("oven").choice([0.0, 6.0, 15.0])
        if ang:
            p.rotate(door, rot=(ang, 0, 0), pivot=(0, y_f, 0.24))
    if p.destroyed:
        r = p.vrng("wreck")
        p.rotate(door, rot=(84, 0, 0), pivot=(0, y_f, 0.24))
        p.rotate(door, rot=(0, r.uniform(-6, 6), 0), pivot=(0, y_f, 0.24))
        p.move(drawer, (0, -0.32, 0))
        p.rotate(drawer, rot=(0, 0, r.uniform(-12, 12)), pivot=(0, y_f - 0.3, 0.1))
    p.collider((0, (y_f - 0.05 + y_b) / 2, 0.565), (W, D + 0.05, 1.13))


def microwave(p: Prop) -> None:
    """Early-90s countertop microwave: almond case, dark window door (hinged left), keypad. 0.5 x 0.37 x 0.3."""
    W, D, H = 0.5, 0.37, 0.29
    y_f = -D / 2 + 0.01
    p.hollow((W, D - 0.02, H), (0, 0.01, H / 2 + 0.008), M.PL_BEIGE, wall=0.012, bevel=0.008, grain="X")
    for sx in (-0.21, 0.21):
        for sy in (-0.13, 0.13):
            p.cyl(0.01, 0.008, (sx, sy, 0.004), M.RUBBER, segs=6)
    p.box((0.012, D - 0.04, H - 0.03), (0.105, 0.01, H / 2 + 0.008), M.PL_BEIGE, bevel=0.0, ring=0)
    p.box((0.125, 0.012, H - 0.024), (0.17, y_f + 0.004, H / 2 + 0.008), M.PL_GREY, bevel=0.003)
    p.box((0.09, 0.004, 0.035), (0.17, y_f - 0.004, H - 0.04), M.GLASS, bevel=0.0, ring=0)
    for row in range(4):
        for col in range(3):
            p.box((0.022, 0.006, 0.016), (0.143 + col * 0.027, y_f - 0.004, 0.17 - row * 0.024), M.PL_WHITE, bevel=0.001,
                  ring=0, tags=("knob",))
    p.box((0.08, 0.01, 0.025), (0.17, y_f - 0.005, 0.045), M.PL_BLACK, bevel=0.002, ring=0)
    p.cyl(0.13, 0.006, (-0.055, 0.0, 0.03), M.GLASS, segs=16, wear=0.1)
    door = [p.panel(0.355, H - 0.02, 0.022, (-0.07, y_f - 0.011, H / 2 + 0.008), M.PL_BEIGE, style="slab", bevel=0.004,
                    tags=("door",))]
    door.append(p.box((0.018, 0.01, 0.2), (0.085, y_f - 0.026, H / 2 + 0.008), M.PL_GREY, bevel=0.003, tags=("knob",)))
    if not p.destroyed:
        door.append(p.box((0.27, 0.004, 0.17), (-0.085, y_f - 0.023, H / 2 + 0.008), M.GLASS, bevel=0.0, ring=0))
    else:
        door += F.shatter_pane(p, 0.27, 0.17, (-0.085, y_f - 0.023, H / 2 + 0.008), M.GLASS, t=0.003, spokes=7, rings=2,
                               key="mw", missing_inner=0.95, missing_outer=0.3)
    if p.cond == "worn":
        ang = p.vrng("door").choice([0.0, 12.0, 30.0])
        if ang:
            F.swing(p, door, -W / 2 + 0.003, y_f, -ang)
    if p.destroyed:
        F.swing(p, door, -W / 2 + 0.003, y_f, -100)
        p.rotate(door, rot=(0, -12, 0), pivot=(-W / 2, y_f, H))
    p.collider((0, 0, H / 2 + 0.004), (W, D, H + 0.008))


# ------------------------------------------------------------------------------------------------
# dining
# ------------------------------------------------------------------------------------------------


def kitchen_table(p: Prop) -> None:
    """Oak dinette table 1.2 x 0.8, top at 0.76, turned legs and aprons."""
    W, D, H, T = 1.2, 0.8, 0.76, 0.03
    lx, ly = W / 2 - 0.07, D / 2 - 0.07
    p.prism(F.rounded_rect(W, D, 0.05), T, M.OAK, plane="XY", offset=H - T, bevel=0.004, grain="X")
    for sy in (-1, 1):
        p.box((2 * lx - 0.04, 0.02, 0.09), (0, sy * (ly - 0.005), H - T - 0.045), M.OAK, bevel=0.002, grain="X")
    for sx in (-1, 1):
        p.box((0.02, 2 * ly - 0.04, 0.09), (sx * (lx - 0.005), 0, H - T - 0.045), M.OAK, bevel=0.002, grain="Y")
    legs = {}
    for sx in (-1, 1):
        for sy in (-1, 1):
            legs[(sx, sy)] = F.turned_leg(p, sx * lx, sy * ly, 0.0, H - T, 0.03, M.OAK, key=f"leg{sx}{sy}")
    if p.worn:
        r = p.rng("clutter")
        # placemat, a glass, a mug and some mail left on the table
        p.box((0.42, 0.3, 0.003), (-0.25, -0.15, H + 0.0015), M.TOWEL, bevel=0.0, ring=0)
        p.lathe([(0.03, 0.0), (0.035, 0.12), (0.031, 0.12), (0.027, 0.006), (0.0, 0.006)], (0.1, 0.12, H), M.GLASS, segs=10,
                cap_top=False)
        p.lathe([(0.034, 0.0), (0.038, 0.095), (0.034, 0.095), (0.031, 0.008), (0.0, 0.008)], (0.32, -0.1, H), M.CERAMIC,
                segs=12, cap_top=False)
        p.tube([(0.355, -0.1, H + 0.075), (0.385, -0.1, H + 0.07), (0.385, -0.1, H + 0.03), (0.355, -0.1, H + 0.025)], 0.0055,
               M.CERAMIC, segs=6, fillet_r=0.012, steps=2)
        for i in range(3):
            env = p.box((0.22, 0.11, 0.002), (0, 0, 0), M.PAPER, bevel=0.0, ring=0, uv="keep")
            core.set_face_uvs(env.obj, lambda poly, c=i: (*core.note_rect(c), 0, 1, False))
            G.xform(env.obj, rot=(0, 0, r.uniform(-30, 30)),
                    loc=(0.15 + r.uniform(-0.05, 0.05), 0.2 + r.uniform(-0.04, 0.04), H + 0.002 + i * 0.002))
    if p.destroyed:
        r = p.vrng("wreck")
        side = -1
        for sy in (-1, 1):
            F.break_off(p, legs[(side, sy)], r.uniform(0.18, 0.42), jag=0.025, key=f"legbreak{sy}",
                        piece_at=(side * (W / 2 + 0.25), sy * 0.3 + r.uniform(-0.1, 0.1)), piece_yaw=r.uniform(0, 180))
        frame_parts = [q for q in p.parts if "debris" not in q.tags]
        p.settle(frame_parts, pivot=(-side * lx, 0, 0), axis=(0, side, 0), max_deg=40)
    p.collider((0, 0, H / 2), (W, D, H))


def kitchen_chair(p: Prop) -> None:
    """Oak spindle-back kitchen chair: saddle seat at 0.46, splayed turned legs, H stretcher."""
    sh = 0.46
    p.rbox((0.42, 0.4, 0.035), (0, 0, sh - 0.0175), M.OAK, radius=0.012, inner=(3, 3, 1), sag=0.012, sag_at=(0, 0.02),
           sag_r=0.16, edge_deg=25, grain="X")
    legs = []
    for sx, sy, k in ((-1, -1, "fl"), (1, -1, "fr"), (-1, 1, "bl"), (1, 1, "br")):
        x, y = sx * 0.17, sy * 0.15
        leg = F.turned_leg(p, x, y, 0.0, sh - 0.035, 0.019, M.OAK, key=k, style="spindle", segs=8)
        G.xform(leg.obj, rot=(sy * 4, -sx * 4, 0), pivot=(x, y, sh - 0.035))
        legs.append(leg)
    for sx in (-1, 1):
        p.cyl(0.011, 0.33, (sx * 0.185, 0, 0.17), M.OAK, axis="Y", segs=8, tags=("stretcher",))
    p.cyl(0.011, 0.37, (0, 0.0, 0.2), M.OAK, axis="X", segs=8, tags=("stretcher",))
    back = []
    for sx in (-1, 1):
        post = p.lathe([(0.017, 0.0), (0.016, 0.2), (0.014, 0.44), (0.012, 0.46)], (sx * 0.165, 0.165, sh - 0.035), M.OAK,
                       segs=8, tags=("back",))
        G.xform(post.obj, rot=(-9, 0, 0), pivot=(0, 0.165, sh - 0.035))
        back.append(post)
    crest = p.rbox((0.38, 0.028, 0.075), (0, 0.235, sh + 0.385), M.OAK, radius=0.01, inner=(4, 1, 1), bulge=(0, 0.02, 0),
                   edge_deg=25, grain="X", tags=("back",))
    G.xform(crest.obj, rot=(-9, 0, 0), pivot=(0, 0.235, sh + 0.385))
    spindles = []
    for i in range(4):
        x = -0.105 + i * 0.07
        sp = p.lathe([(0.01, 0.0), (0.012, 0.15), (0.009, 0.36)], (x, 0.17, sh - 0.01), M.OAK, segs=6, tags=("back", "spindle"))
        G.xform(sp.obj, rot=(-9, 0, 0), pivot=(0, 0.17, sh - 0.01))
        spindles.append(sp)
    if p.destroyed:
        r = p.vrng("wreck")
        # snapped back leg + two spindles, crest rail torn off, chair lying on its side
        F.break_off(p, legs[2], r.uniform(0.12, 0.25), jag=0.02, key="legb", keep_piece=False)
        for sp in spindles[1:3]:
            F.break_off(p, sp, sh + r.uniform(0.1, 0.22), jag=0.015, key="spb", keep_piece=False)
        p.remove([crest])
        whole = list(p.parts)
        p.rotate(whole, rot=(0, 90, 0), pivot=(0, 0, 0))
        lo, hi = p.bounds(whole)
        p.move(whole, (0, 0, -lo.z))
        p.rotate(whole, rot=(0, 0, r.uniform(-25, 25)), pivot=(0, 0, 0))
        crest2 = p.rbox((0.38, 0.028, 0.075), (0, 0, 0), M.OAK, radius=0.01, inner=(4, 1, 1), bulge=(0, 0.02, 0),
                        edge_deg=25, grain="X", tags=("debris",))
        p.lay_on_floor([crest2], rot=(85, 0, 0), at=(0.45, -0.35), yaw=r.uniform(0, 90))
        p.collider((0, 0, 0.21), (0.9, 0.5, 0.42))
    else:
        p.collider((0, 0.03, 0.47), (0.44, 0.5, 0.94))


# ------------------------------------------------------------------------------------------------
# small stuff
# ------------------------------------------------------------------------------------------------


def crumple(p: Prop, c, s: float, mat: str, seed: int):
    """Crumpled paper / plastic ball."""
    from lib import primitives
    obj = G.box(p._name("crumple"), (s, s * 0.9, s * 0.8), (0, 0, 0))
    primitives.subdivide(obj, cuts=1)
    primitives.displace(obj, s * 0.25, scale=1.2 / s, seed=seed)
    G.xform(obj, loc=c)
    return p.add(obj, mat, tags=("trash",), edge_deg=40, ring=0, wear=0.3)


def trash_can_kitchen(p: Prop) -> None:
    """Tall almond plastic swing-top kitchen bin (0.3 x 0.26 x 0.66) with a black bag."""
    W, D, H = 0.3, 0.26, 0.58
    body = p.add(G.hollow_box(p._name("bin"), (W, D, H), (0, 0, H / 2), 0.006, "+Z", 0.0), M.PL_BEIGE, edge_deg=30, ring=0)
    for v in body.obj.data.vertices:  # widen toward the top
        t = v.co.z / H
        v.co.x *= 0.88 + 0.12 * t
        v.co.y *= 0.88 + 0.12 * t
    bag = p.rbox((W - 0.03, D - 0.03, 0.08), (0, 0, H - 0.07), M.PL_BLACK, radius=0.03, inner=(2, 2, 1), wrinkle=0.012,
                 seed=p.seed, tags=("bag",), edge_deg=40)
    lid = [p.rbox((W + 0.014, D + 0.014, 0.075), (0, 0, H + 0.03), M.PL_BEIGE, radius=0.02, inner=(3, 3, 1),
                  bulge=(0, 0, 0.025), edge_deg=30)]
    lid.append(p.panel(0.2, 0.065, 0.006, (0, -(D + 0.014) / 2 - 0.004, H + 0.035), M.PL_BEIGE, style="slab", bevel=0.002,
                       tags=("flap",)))
    p.rotate(lid[1:], rot=(-8, 0, 0), pivot=(0, -(D + 0.014) / 2, H + 0.07))
    if p.cond == "worn":
        p.rotate(lid, rot=(0, 0, p.vrng("lid").uniform(-12, 12)), pivot=(0, 0, 0))
        p.move(lid, (p.vrng("lid2").uniform(-0.03, 0.03), 0.02, 0.0))
    if p.destroyed:
        r = p.vrng("wreck")
        whole = [body, bag]
        p.rotate(whole, rot=(90, 0, 0), pivot=(0, 0, 0))
        lo, hi = p.bounds(whole)
        p.move(whole, (0, 0, -lo.z))
        p.rotate(whole, rot=(0, 0, r.uniform(-20, 20)), pivot=(0, 0, 0))
        p.move([bag], (0, -0.33, -0.04))
        p.lay_on_floor(lid, rot=(0, 160, 0), at=(0.35, 0.1), yaw=r.uniform(0, 90))
        for i in range(7):
            crumple(p, (r.uniform(-0.3, 0.3), -0.45 - r.uniform(0, 0.35), 0.03), r.uniform(0.05, 0.09),
                    [M.PAPER, M.CARDBOARD, M.PL_WHITE][i % 3], seed=r.randrange(9999))
        F.can(p, 0.033, 0.12, (0.2, -0.6, 0.033), 3, rot=(90, 0, 40))
        p.collider((0, 0, 0.15), (0.35, 0.65, 0.3))
    else:
        p.collider((0, 0, (H + 0.07) / 2), (W + 0.02, D + 0.02, H + 0.07))


def dish_clutter(p: Prop) -> None:
    """Dirty dishes for a counter: plate stack, pot with lid askew, mugs, bowl, glass, cutlery (~0.6 x 0.4)."""
    r = p.rng("dishes")
    plate = [(0.0, 0.0), (0.065, 0.0), (0.075, 0.004), (0.11, 0.016), (0.118, 0.02), (0.112, 0.021), (0.07, 0.008),
             (0.0, 0.007)]
    for i in range(4):
        p.lathe(plate, (-0.17 + r.uniform(-0.01, 0.01), -0.02 + r.uniform(-0.01, 0.01), i * 0.009), M.CERAMIC, segs=12,
                cap_bottom=False, cap_top=False, ring=0)
    p.cyl(0.06, 0.004, (-0.165, -0.02, 0.04), M.MOLD, segs=10)
    pot = [(0.0, 0.0), (0.105, 0.0), (0.11, 0.01), (0.11, 0.13), (0.116, 0.135), (0.104, 0.135), (0.104, 0.008), (0.0, 0.008)]
    p.lathe(pot, (0.13, 0.05, 0.0), M.STAINLESS, segs=12, cap_bottom=False, cap_top=False, ring=0)
    p.cyl(0.098, 0.004, (0.13, 0.05, 0.06), M.MOLD, segs=12)
    p.tube([(0.24, 0.05, 0.11), (0.38, 0.05, 0.12)], 0.01, M.PL_BLACK, segs=6)
    lid = p.lathe([(0.0, 0.03), (0.04, 0.026), (0.113, 0.004), (0.116, 0.0)], (0, 0, 0), M.STAINLESS, segs=12,
                  cap_bottom=True, cap_top=False, ring=0)
    knob = p.lathe([(0.012, 0.0), (0.014, 0.015), (0.0, 0.02)], (0, 0, 0.03), M.PL_BLACK, segs=8)
    G.xform(lid.obj, rot=(18, 0, 0), loc=(0.13, 0.03, 0.14))
    G.xform(knob.obj, rot=(18, 0, 0), loc=(0.13, 0.03, 0.14))
    mug = [(0.034, 0.0), (0.038, 0.095), (0.034, 0.095), (0.031, 0.008), (0.0, 0.008)]
    for i, (mx, my, rz) in enumerate(((-0.02, 0.12, 30), (0.05, -0.12, -60))):
        mm = M.CERAMIC if i == 0 else M.PL_RED
        p.lathe(mug, (mx, my, 0.0), mm, segs=10, cap_bottom=True, cap_top=False, ring=0)
        a = math.radians(rz)
        hx, hy = mx + math.cos(a) * 0.036, my + math.sin(a) * 0.036
        ox, oy = math.cos(a) * 0.028, math.sin(a) * 0.028
        p.tube([(hx, hy, 0.075), (hx + ox, hy + oy, 0.07), (hx + ox, hy + oy, 0.03), (hx, hy, 0.025)], 0.0055, mm, segs=6,
               fillet_r=0.012, steps=2)
    bowl = [(0.0, 0.0), (0.035, 0.0), (0.07, 0.04), (0.074, 0.05), (0.068, 0.05), (0.032, 0.007), (0.0, 0.007)]
    p.lathe(bowl, (-0.24, 0.13, 0.0), M.CERAMIC, segs=12, cap_bottom=False, cap_top=False, ring=0)
    p.lathe([(0.03, 0.0), (0.035, 0.12), (0.031, 0.12), (0.027, 0.006), (0.0, 0.006)], (0.26, -0.1, 0.0), M.GLASS, segs=10,
            cap_bottom=True, cap_top=False, ring=0)
    for i in range(3):
        c = p.box((0.18, 0.012, 0.003), (0, 0, 0), M.CHROME, bevel=0.0, ring=0)
        G.xform(c.obj, rot=(0, 0, r.uniform(-40, 40)), loc=(-0.05 + r.uniform(-0.05, 0.05), -0.15 + i * 0.02, 0.0015 + i * 0.001))
    if p.worn:
        # a broken plate next to the stack
        q1, q2, b1, b2 = G.jagged_split(0.2, 0.2, (-0.1, -0.03), (0.1, 0.05), teeth=5, amp=0.015, seed=p.seed)
        for poly, dx in ((q1, 0.0), (q2, 0.05)):
            part = p.prism(poly, 0.006, M.CERAMIC, plane="XY", offset=0.0, tags=("shard",))
            G.xform(part.obj, rot=(0, 0, r.uniform(0, 90)), loc=(-0.3 + dx, -0.15, 0.0))
    lo, hi = p.bounds()
    p.collider(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, hi.z / 2), (hi.x - lo.x, hi.y - lo.y, hi.z))


BUILDERS = {
    "kitchen_counter": kitchen_counter,
    "kitchen_counter_sink": kitchen_counter_sink,
    "kitchen_wall_cabinet": kitchen_wall_cabinet,
    "fridge_old": fridge_old,
    "stove_old": stove_old,
    "microwave": microwave,
    "kitchen_table": kitchen_table,
    "kitchen_chair": kitchen_chair,
    "trash_can_kitchen": trash_can_kitchen,
    "dish_clutter": dish_clutter,
}


def build(params: dict, outputs: list[str]) -> None:
    core.build_variants(params, outputs, BUILDERS[params["prop"]])
