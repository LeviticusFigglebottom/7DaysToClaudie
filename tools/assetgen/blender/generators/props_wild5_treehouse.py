"""Wilderness set pieces, round 5: props of the Treehouse Holdout (w5_treehouse_holdout), where a family lived up in
three big firs on plank platforms until hunger brought them down.

The trees: a big fir whose trunk rises through the POI's kit decks (a flared, root-buttressed bole with ledger
blocks bolted on where the decks bear, dead stubs below and a drooping crown of bough tiers far above the huts),
the peeled-pole stilts with their knee braces under the deck corners, the decks' pole railings, the rope bridges'
handlines and the plank-and-rope decking laid over their floors, the front ladder pulled up and lying on its deck,
the pulley lift with its basket on the ground, rain barrels under tarp catches, and the family's stores chest. On
the ground: raised garden beds gone to frost, the stick-and-wire deer fence round them, and the charred rafters
fallen into the burned-out cabin.

Conventions (docs/ASSET_PIPELINE.md): metres, Z up, front -Y, origin bottom centre; floor props have their depth
centred on the origin (PoiBuilder's collision box is the def's size centred there). The trunk's origin is the foot
of the bole (its collision box is the bole only; roots and crown are visual). Railings and the pulley lift stand on
their deck with their back (+Y) toward the open edge; the pulley's rope and basket and the bridge decking's rigging
hang below their deck floor (no ground clamp). Only shared materials are used. 'clean' is the treehouse while the
family kept it, 'worn' the winter after.
"""
from __future__ import annotations

import math

from mathutils import Vector

from lib import props_ext_kit as K
from lib import props_wild_parts as W

BARK = "wild_log_bark"
PEELED = "out_log_peeled"
PLANK = "wood_weathered"
LUMBER = "wild_lumber_weathered"
FRESH = "wild_lumber_fresh"
ROPE = "road_rope"
TWINE = "farm_twine"
BOUGH = "out_boughs"
CHAR = "wood_charred"
ASH = "ash_burnt"
STEEL = "road_steel_dark"
RUST = "road_rust"
STONE = "stone_river"
STAVE = "wood_stained"
TARP = "tarp_blue"
SOIL = "garden_soil"
STALK = "garden_dead_stalk"
WIRE = "farm_chicken_wire"

DECK = 3.15          # a level-1 deck's floor top (floor_height 0.15)
SLAB = 0.2           # kit floor slab depth


def _bx(ctx, name, size, center, mat, *, bevel=0.006, uv_scale=2.0, **kw):
    return ctx.add(K.box(name, size, center=center, bevel=bevel), mat, uv="box", uv_scale=uv_scale, **kw)


def _cy(ctx, name, r, h, center, mat, *, axis="Z", segs=12, r_top=None, uv_scale=2.0, **kw):
    o = K.cyl(name, r, h, segs=segs, center=center, axis=axis, r_top=r_top)
    return ctx.add(o, mat, uv="box", uv_scale=uv_scale, smooth=40, **kw)


def _rope(ctx, name, pts, r=0.012, mat=ROPE, **kw):
    return ctx.add(K.tube(name, pts, r, segs=5), mat, uv="box", uv_scale=4.0, smooth=50, ao=False, **kw)


def _sag(a, b, sag, n=6):
    """Points of a rope hanging from a to b, `sag` metres low in the middle."""
    a, b = Vector(a), Vector(b)
    return [a.lerp(b, i / n) - Vector((0, 0, sag * math.sin(math.pi * i / n))) for i in range(n + 1)]


def _lash(ctx, name, at, r, axis="Z"):
    """A few turns of rope round a member at `at` (a lashing)."""
    for k in range(3):
        off = (k - 1) * 0.025
        c = Vector(at) + (Vector((0, 0, off)) if axis == "Z" else Vector((off, 0, 0)) if axis == "X" else Vector((0, off, 0)))
        pts = []
        for i in range(10):
            a = math.tau * i / 10
            if axis == "Z":
                pts.append(c + Vector((math.cos(a) * r, math.sin(a) * r, 0)))
            elif axis == "X":
                pts.append(c + Vector((0, math.cos(a) * r, math.sin(a) * r)))
            else:
                pts.append(c + Vector((math.cos(a) * r, 0, math.sin(a) * r)))
        ctx.add(K.tube(f"{name}{k}", pts, 0.008, segs=4, closed=True), ROPE, uv="box", uv_scale=4.0, ao=False)


# ============================================================================================
# The tree
# ============================================================================================

TRUNK_H = 18.0
CROWN_BASE = 10.8


def _trunk_r(z: float) -> float:
    """Bole radius: 0.44 m at the foot tapering to 0.13 at the top, plus the root flare."""
    return max(0.06, 0.44 - 0.0175 * z) + 0.2 * math.exp(-z / 0.45)


def w5_treehouse_trunk(ctx: K.Ctx) -> None:
    """A big grey fir the decks are built round: a flared bole with five root buttresses, ledger blocks lag-bolted
    on under each deck height (2.85 m and 5.85 m), a few dead stubs low down, then nothing until a drooping crown
    of bough tiers from 10.8 m to the leader at 18 m (above the highest hut's roof). Worn: the bark clawed off in
    long gouges up to two metres where the Hollowed stood and waited, a dead branch snapped and hanging."""
    zs = [0.0, 0.25, 0.5, 0.9, 1.5] + [float(z) for z in range(2, int(TRUNK_H) + 1)]
    r = ctx.rnd("bole")
    pts = [Vector((r.uniform(-0.02, 0.02) * min(z, 4) / 4, r.uniform(-0.02, 0.02) * min(z, 4) / 4, z)) for z in zs]
    pts[0] = Vector((0, 0, -0.05))
    radii = [_trunk_r(z) for z in zs]
    radii[-1] = 0.05
    bole = K.tube("bole", pts, radii, segs=16)
    K.noise_disp(bole, 0.018, scale=3.0, seed=ctx.seed)
    ctx.add(bole, BARK, uv="cyl", uv_axis=2, uv_scale=1.0, cyl_repeats=3.0, smooth=60, moss=0.5, patches=0.3)
    # Root buttresses.
    for k in range(5):
        phi = k * math.tau / 5 + r.uniform(-0.3, 0.3)
        d = Vector((math.cos(phi), math.sin(phi), 0))
        W.pole(ctx, f"root{k}", [d * 0.3 + Vector((0, 0, 0.55)), d * 0.65 + Vector((0, 0, 0.12)), d * 1.05 + Vector((0, 0, -0.04))],
               0.17, BARK, r_end=0.05, segs=8, moss=0.6)
    # Ledger blocks bolted on under the decks: the slab's underside is at 2.95 (level 1) and 5.95 (level 2).
    for z in (2.85, 5.85):
        rz = _trunk_r(z)
        for k in range(4):
            phi = k * math.pi / 2 + math.pi / 4
            d = Vector((math.cos(phi), math.sin(phi), 0))
            c = d * (rz + 0.04) + Vector((0, 0, z - 0.05))
            W.bar(ctx, f"ledger{z}_{k}", c - Vector((0, 0, 0.12)), c + Vector((0, 0, 0.1)),
                  0.16, 0.08, LUMBER, up=(d.x, d.y, 0.0))
            _cy(ctx, f"lag{z}_{k}", 0.018, 0.03, d * (rz + 0.09) + Vector((0, 0, z - 0.05)), STEEL, axis="X" if abs(d.x) > 0.5 else "Y", segs=6)
    # Dead stubs, low down only (decks and huts are built round the bole above 2.4 m).
    for k in range(7):
        z = r.uniform(0.9, 2.3)
        phi = r.uniform(0, math.tau)
        d = Vector((math.cos(phi), math.sin(phi), r.uniform(-0.1, 0.25)))
        base = Vector((0, 0, z)) + Vector((d.x, d.y, 0)) * _trunk_r(z) * 0.8
        W.rod(ctx, f"stub{k}", base, base + d.normalized() * r.uniform(0.18, 0.4), 0.035, BARK, r2=0.012, segs=6)
    # The crown: whorls of drooping branches with bough sprays along them.
    z = CROWN_BASE
    w = 0
    while z < TRUNK_H - 0.6:
        t = (z - CROWN_BASE) / (TRUNK_H - CROWN_BASE)
        L = 2.7 * (1 - t) + 0.45
        n = 6 if t < 0.6 else 5
        for k in range(n):
            phi = k * math.tau / n + w * 0.55 + r.uniform(-0.2, 0.2)
            d = Vector((math.cos(phi), math.sin(phi), 0))
            start = Vector((0, 0, z)) + d * _trunk_r(z) * 0.7
            mid = start + d * L * 0.55 + Vector((0, 0, 0.05))
            end = start + d * L + Vector((0, 0, -0.35 * L))
            if ctx.worn and w == 1 and k == 2:
                # A dead branch snapped at the bole and hanging by its bark.
                W.pole(ctx, f"snapped{w}_{k}", [start, start + d * 0.3 + Vector((0, 0, -0.6)), start + d * 0.45 + Vector((0, 0, -2.0))],
                       0.04, BARK, r_end=0.012, segs=5)
                continue
            W.pole(ctx, f"br{w}_{k}", [start, mid, end], 0.045 * (1 - t) + 0.015, BARK, r_end=0.01, segs=5)
            for j, s in enumerate((0.35, 0.68, 0.95)):
                c = start.lerp(mid, s * 1.6) if s < 0.6 else mid.lerp(end, (s - 0.5) / 0.5)
                sz = (0.55 * (1 - t) + 0.28) * (1.0 - 0.25 * j)
                b = K.blob(f"bough{w}_{k}_{j}", sz, subdiv=1, scale=(1.0, 0.75, 0.28), center=(0, 0, 0),
                           rough=0.25, seed=ctx.seed + w * 31 + k * 7 + j)
                K.place(b, c - Vector((0, 0, 0.06)), (r.uniform(-12, 12), r.uniform(5, 18), math.degrees(phi)))
                ctx.add(b, BOUGH, uv="box", uv_scale=2.0, smooth=50, patches=0.2, ao=False)
        z += 0.85 - 0.25 * t
        w += 1
    top = K.cyl("leader_tuft", 0.35, 1.4, segs=8, r_top=0.02, center=(0, 0, TRUNK_H - 0.3))
    ctx.add(top, BOUGH, uv="box", uv_scale=2.0, smooth=50, patches=0.2, ao=False)
    if ctx.worn:
        # The bark clawed off in long gouges to two metres where they stood round the foot.
        rr = ctx.drnd("claws")
        for k in range(9):
            phi = rr.uniform(0, math.tau)
            z0 = rr.uniform(0.6, 1.1)
            z1 = z0 + rr.uniform(0.5, 1.0)
            d = Vector((math.cos(phi), math.sin(phi), 0))
            a = d * (_trunk_r(z0) + 0.004) + Vector((0, 0, z0))
            b = d * (_trunk_r(z1) + 0.004) + Vector((0, 0, z1))
            W.bar(ctx, f"gouge{k}", a, b, 0.05, 0.012, FRESH, up=(d.x, d.y, 0.0))


def w5_treehouse_stilt(ctx: K.Ctx) -> None:
    """A peeled pole stilt under a deck corner, 2.95 m to the slab's underside: a flat footing stone, the pole, a
    bearer block on top and two knee braces running in under the deck (+X and -Y) above head height. Worn: moss
    up the north side, one brace split and hanging off its nail."""
    H = DECK - SLAB
    stone = K.blob("footing", 0.22, subdiv=2, scale=(1.2, 1.0, 0.35), center=(0, 0, 0.04), rough=0.2, seed=ctx.seed)
    ctx.add(stone, STONE, uv="box", uv_scale=2.0, smooth=40, moss=0.5)
    W.pole(ctx, "post", [(0, 0, 0.05), (0.01, -0.01, 1.4), (0, 0, H)], 0.105, PEELED, r_end=0.09, segs=10, moss=0.4)
    _bx(ctx, "bearer", (0.28, 0.28, 0.12), (0, 0, H - 0.06), LUMBER, bevel=0.01, uv_scale=1.0)
    for k, d in enumerate((Vector((1, 0, 0)), Vector((0, -1, 0)))):
        a = d * 0.09 + Vector((0, 0, 2.15))
        b = d * 0.62 + Vector((0, 0, H - 0.04))
        if ctx.worn and k == 1:
            W.bar(ctx, f"brace{k}", a, a + Vector((0, 0, -0.75)) + d * 0.12, 0.09, 0.05, LUMBER, up=(0, 0, 1) if d.x else (1, 0, 0))
            continue
        W.bar(ctx, f"brace{k}", a, b, 0.09, 0.05, LUMBER, up=(-d.y, d.x, 0))
        W.bolts(ctx, f"nails{k}", [(a + (b - a) * 0.04, d), (b - (b - a) * 0.04, d)], STEEL, r=0.008, h=0.006)


# ============================================================================================
# Railings, bridges, the pulled-up ladder
# ============================================================================================

def w5_treehouse_rail(ctx: K.Ctx) -> None:
    """1 m of deck railing along an open edge: a peeled post at the left end and a sapling top rail at 1.0 m and
    a mid rail at 0.5 m lashed to it, overlapping the next metre's. Worn: the mid rail snapped and hanging."""
    W.pole(ctx, "post", [(-0.44, 0, 0.0), (-0.44, 0, 1.06)], 0.045, PEELED, r_end=0.04, segs=8)
    W.pole(ctx, "top", [(-0.53, 0, 1.0), (0, 0.004, 1.005), (0.53, 0, 1.0)], 0.038, PEELED, r_end=0.034, segs=8,
           seed=ctx.seed, wobble=0.004)
    if ctx.worn:
        W.pole(ctx, "mid_a", [(-0.53, 0, 0.5), (-0.1, 0, 0.47), (0.02, 0.02, 0.2)], 0.03, PEELED, r_end=0.026, segs=7)
        W.pole(ctx, "mid_b", [(0.53, 0, 0.5), (0.25, 0.01, 0.38), (0.12, 0.02, 0.1)], 0.03, PEELED, r_end=0.026, segs=7)
    else:
        W.pole(ctx, "mid", [(-0.53, 0, 0.5), (0.53, 0, 0.5)], 0.03, PEELED, r_end=0.028, segs=7, seed=ctx.seed + 1, wobble=0.004)
    _lash(ctx, "lash_top", (-0.44, 0, 1.0), 0.05)
    _lash(ctx, "lash_mid", (-0.44, 0, 0.5), 0.05)


def w5_treehouse_rope_rail(ctx: K.Ctx) -> None:
    """1 m of a rope bridge's side: a thin post at the left end, a sagging hand line at 1.0 m and a lower line at
    0.5 m, with cord drops netting them down to the deck edge every quarter metre. Worn: the lower line parted and
    trailing, half the cords gone."""
    W.pole(ctx, "post", [(-0.46, 0, 0.0), (-0.46, 0, 1.06)], 0.035, PEELED, r_end=0.03, segs=8)
    hand = _sag((-0.52, 0, 1.0), (0.52, 0, 1.0), 0.05)
    _rope(ctx, "hand", hand, 0.016)
    if ctx.worn:
        _rope(ctx, "low_a", [(-0.52, 0, 0.5), (-0.2, 0, 0.44), (0.0, 0.03, 0.08)], 0.013)
        _rope(ctx, "low_b", [(0.52, 0, 0.5), (0.35, 0.02, 0.3), (0.3, 0.05, 0.02)], 0.013)
        cords = (-0.25, 0.25)
    else:
        _rope(ctx, "low", _sag((-0.52, 0, 0.5), (0.52, 0, 0.5), 0.04), 0.013)
        cords = (-0.25, 0.0, 0.25, 0.5)
    for k, x in enumerate(cords):
        top = 1.0 - 0.05 * math.sin(math.pi * (x + 0.52) / 1.04)
        _rope(ctx, f"cord{k}", [(x, 0, top), (x, 0, 0.02)], 0.006, TWINE)
    _lash(ctx, "lash_hand", (-0.46, 0, 1.0), 0.04)


def w5_treehouse_bridge_planks(ctx: K.Ctx) -> None:
    """1 m of rope-bridge decking laid over a bridge cell's floor: split planks across the way with gaps between,
    two rope stringers along the edges lashed down at every plank, and under the floor the two sagging foot ropes
    the bridge hangs from, wrapped round the slab. Worn: a plank missing and one cracked through."""
    ctx.ground_clamp = False
    r = ctx.rnd("planks")
    n = 6
    for k in range(n):
        y = -0.5 + (k + 0.5) / n
        if ctx.worn and k == 2:
            continue
        w = 0.13 + r.uniform(-0.01, 0.01)
        ang = r.uniform(-3, 3)
        p = K.box(f"plank{k}", (0.98, w, 0.028), center=(0, 0, 0), bevel=0.004)
        K.place(p, (r.uniform(-0.02, 0.02), y, 0.014), (0, 0, ang))
        ctx.add(p, PLANK if k % 2 else LUMBER, uv="box", uv_scale=1.0, long_axis=0, patches=0.5)
        if ctx.worn and k == 4:
            K.dent(p, (0, y, 0.03), 0.2, 0.02)
    for sx in (-1, 1):
        _rope(ctx, f"stringer{sx}", [(sx * 0.44, -0.5, 0.035), (sx * 0.44, 0.5, 0.035)], 0.014)
        for k in range(n):
            y = -0.5 + (k + 0.5) / n
            _rope(ctx, f"tie{sx}{k}", [(sx * 0.44, y, 0.05), (sx * 0.51, y, 0.0), (sx * 0.51, y, -SLAB - 0.02),
                                        (sx * 0.47, y, -SLAB - 0.05)], 0.006, TWINE)
        _rope(ctx, f"foot{sx}", [(sx * 0.47, -0.5, -SLAB - 0.05), (sx * 0.47, 0.5, -SLAB - 0.05)], 0.02)


def w5_treehouse_ladder_pulled(ctx: K.Ctx) -> None:
    """The front ladder, pulled up for the last time and left lying on its deck: two peeled rails 2.8 m long with
    lashed rungs every 0.3 m, the hauling rope still tied to the top rung and coiled beside it, its end cut. Worn:
    a rung broken, the coil kicked loose."""
    L = 2.8
    for sx in (-1, 1):
        W.pole(ctx, f"rail{sx}", [(sx * 0.22, -L / 2, 0.045), (sx * 0.22, L / 2, 0.042)], 0.042, PEELED, r_end=0.036, segs=8)
    for k in range(9):
        y = -L / 2 + 0.2 + k * 0.3
        if ctx.worn and k == 5:
            W.rod(ctx, f"rung{k}a", (-0.22, y, 0.045), (-0.03, y + 0.04, 0.05), 0.022, PEELED, segs=6)
            W.rod(ctx, f"rung{k}b", (0.22, y, 0.045), (0.06, y - 0.05, 0.03), 0.022, PEELED, segs=6)
            continue
        W.rod(ctx, f"rung{k}", (-0.24, y, 0.045), (0.24, y, 0.045), 0.022, PEELED, segs=6)
    ytop = L / 2 - 0.1
    _rope(ctx, "haul", [(0.0, ytop, 0.07), (0.15, ytop - 0.1, 0.03), (0.38, ytop - 0.35, 0.015)], 0.012)
    cx, cy = 0.42, ytop - 0.7
    turns = 3 if not ctx.worn else 1
    pts = []
    for i in range(turns * 14 + 1):
        a = math.tau * i / 14
        rr = 0.2 - 0.012 * (i / 14)
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a) * 1.2, 0.015 + 0.012 * (i / 14)))
    _rope(ctx, "coil", pts, 0.012)
    if ctx.worn:
        _rope(ctx, "loose", [(cx + 0.2, cy, 0.02), (cx + 0.1, cy - 0.5, 0.015), (cx - 0.15, cy - 0.9, 0.015)], 0.012)
    # The cut end, frayed.
    _cy(ctx, "fray", 0.016, 0.04, (cx - 0.15, cy - 0.95 if ctx.worn else cy + 0.2, 0.02), TWINE, axis="Y", segs=6)


def w5_treehouse_pulley_lift(ctx: K.Ctx) -> None:
    """The pulley lift on a deck's edge: a peeled gallows post with an arm reaching out over the railing (+Y,
    behind the prop), its iron sheave, the rope down 3.15 m to a bushel basket waiting on the ground and back up to
    a cleat on the post, the slack coiled on the deck. Worn: the basket tipped over on the ground and the rope cut a
    metre under the arm, swinging."""
    ctx.ground_clamp = False
    H = 2.55
    W.pole(ctx, "post", [(0, 0, 0.0), (0, 0, H)], 0.07, PEELED, r_end=0.06, segs=10)
    W.bar(ctx, "arm", (0, -0.12, H - 0.18), (0, 1.1, H - 0.18), 0.09, 0.11, LUMBER, up=(0, 0, 1))
    W.bar(ctx, "strut", (0, 0.02, H - 0.95), (0, 0.6, H - 0.24), 0.07, 0.06, LUMBER, up=(1, 0, 0))
    W.bolts(ctx, "bolts", [((0, 0.07, H - 0.18), (0, 1, 0)), ((0, 0.07, H - 0.95), (0, 1, 0))], STEEL)
    sheave = K.cyl("sheave", 0.11, 0.05, segs=16, axis="X", center=(0, 1.0, H - 0.36))
    ctx.add(sheave, RUST, uv="box", uv_scale=3.0, smooth=40)
    for sx in (-1, 1):
        _bx(ctx, f"cheek{sx}", (0.012, 0.24, 0.16), (sx * 0.04, 1.0, H - 0.31), STEEL, bevel=0.002)
    ground = -DECK
    if ctx.worn:
        _rope(ctx, "fall", [(0, 1.11, H - 0.36), (0.0, 1.12, H - 1.3), (0.05, 1.1, H - 1.45)], 0.012)
        bk = (0.35, 1.3, ground)
        basket = K.lathe("basket", [(0.17, 0.0), (0.2, 0.05), (0.24, 0.32), (0.25, 0.34), (0.23, 0.34), (0.215, 0.05), (0.0, 0.05)], segs=14)
        K.place(basket, (bk[0], bk[1], bk[2] + 0.24), (90, 0, 30))
        ctx.add(basket, LUMBER, uv="box", uv_scale=3.0, smooth=40)
        _rope(ctx, "fallen_end", [(0.2, 1.2, ground + 0.02), (-0.1, 1.0, ground + 0.02), (-0.3, 1.4, ground + 0.02)], 0.012)
    else:
        _rope(ctx, "fall", [(0, 1.11, H - 0.36), (0, 1.11, ground + 0.55)], 0.012)
        for k in range(3):
            a = k * math.tau / 3
            _rope(ctx, f"bridle{k}", [(0, 1.11, ground + 0.55), (0.2 * math.cos(a), 1.11 + 0.2 * math.sin(a), ground + 0.33)], 0.008)
        basket = K.lathe("basket", [(0.17, 0.0), (0.2, 0.05), (0.24, 0.32), (0.25, 0.34), (0.23, 0.34), (0.215, 0.05), (0.0, 0.05)], segs=14)
        K.place(basket, (0, 1.11, ground))
        ctx.add(basket, LUMBER, uv="box", uv_scale=3.0, smooth=40)
    _rope(ctx, "haul", [(0, 0.89, H - 0.36), (0, 0.1, 1.15)], 0.012)
    _bx(ctx, "cleat", (0.05, 0.05, 0.22), (0, -0.08, 1.1), LUMBER, bevel=0.005, uv_scale=3.0)
    pts = []
    for i in range(29):
        a = math.tau * i / 14
        pts.append((0.08 + 0.17 * math.cos(a), -0.25 + 0.15 * math.sin(a), 0.015 + 0.01 * i / 14))
    _rope(ctx, "coil", pts, 0.012)
    _rope(ctx, "to_coil", [(0, -0.1, 1.1), (0.04, -0.2, 0.5), (0.1, -0.25, 0.03)], 0.012)


# ============================================================================================
# Water, the garden, the burned cabin, the stores
# ============================================================================================

def w5_treehouse_rain_barrel(ctx: K.Ctx) -> None:
    """A stave rain barrel under a tarp catch: three iron hoops, half a lid, a wooden spigot with a tin cup on a
    nail, and above it a blue tarp lashed to four poles and sagging to a hole over the bung. Worn: the tarp torn
    away to one corner and flapping, a hoop slipped, the staves green."""
    prof = [(0.27, 0.0), (0.31, 0.2), (0.33, 0.45), (0.31, 0.7), (0.28, 0.9)]
    staves = K.lathe("staves", prof, segs=18, cap_bottom=True, cap_top=False)
    K.solidify(staves, 0.025, offset=-1.0)
    ctx.add(staves, STAVE, uv="cyl", uv_axis=2, uv_scale=1.0, cyl_repeats=3.0, smooth=40, moss=0.6 if ctx.worn else 0.2)
    water = K.cyl("water", 0.31, 0.01, segs=18, center=(0, 0, 0.78))
    ctx.add(water, "road_water_film", uv="box", uv_scale=2.0, ao=False)
    for k, (z, rr) in enumerate(((0.1, 0.302), (0.45, 0.335), (0.8, 0.302))):
        if ctx.worn and k == 2:
            z, rr = 0.66, 0.318
        ring = [(rr * math.cos(a), rr * math.sin(a), z) for a in [i * math.tau / 20 for i in range(20)]]
        ctx.add(K.tube(f"hoop{k}", ring, 0.012, segs=4, closed=True, flat=(0.4, 1.0)), RUST, uv="box", uv_scale=3.0)
    lid = K.cyl("lid", 0.29, 0.03, segs=18, center=(0, 0, 0.9))
    K.cut_plane(lid, Vector((0, 0.02, 0)), Vector((0, 1, 0)), keep="below")
    ctx.add(lid, LUMBER, uv="box", uv_scale=1.5)
    _cy(ctx, "spigot", 0.025, 0.12, (0, -0.36, 0.15), LUMBER, axis="Y", segs=8)
    _cy(ctx, "tap", 0.012, 0.06, (0, -0.4, 0.18), LUMBER, segs=6)
    cup = K.lathe("cup", [(0.035, 0.0), (0.04, 0.09), (0.036, 0.09), (0.031, 0.004), (0.0, 0.004)], segs=10)
    K.place(cup, (0.16, -0.33, 0.42))
    ctx.add(cup, "metal_galvanized", uv="box", uv_scale=4.0, smooth=40)
    # The tarp catch.
    corners = [(-0.6, -0.55), (0.6, -0.55), (0.6, 0.55), (-0.6, 0.55)]
    for k, (x, y) in enumerate(corners):
        W.pole(ctx, f"catch_pole{k}", [(x, y, 0.0), (x * 0.98, y * 0.98, 1.75)], 0.025, PEELED, r_end=0.02, segs=6)
    n = 8
    grid = K.grid("tarp", 1.2, 1.1, n, n, center=(0, 0, 0))
    for v in grid.data.vertices:
        d = max(abs(v.co.x) / 0.6, abs(v.co.y) / 0.55)
        v.co.z = 1.72 - 0.75 * max(0.0, 1.0 - d) ** 1.6
    if ctx.worn:
        K.delete_faces(grid, lambda c, n_: c.x > -0.25 or c.y < -0.1)
        for v in grid.data.vertices:
            v.co.z -= 0.6 * max(0.0, -v.co.x - 0.3)
    K.solidify(grid, 0.004, offset=0.0)
    ctx.add(grid, TARP, uv="box", uv_scale=1.0, smooth=40, ao=False)
    for k, (x, y) in enumerate(corners if not ctx.worn else corners[3:]):
        _lash(ctx, f"tarp_lash{k}", (x * 0.98, y * 0.98, 1.7), 0.035)


def w5_treehouse_garden_bed(ctx: K.Ctx) -> None:
    """A raised garden bed of split logs, 2.4 x 1.0 m and 0.35 high, filled with dark soil: rows of frost-killed
    stalks, two bean teepees of thin poles tied at the top with twine and the dead vines still wound up them, and a
    rotten squash. Worn: a teepee pushed over across the bed, the soil scratched up."""
    for k, (cx, cy, L, rot) in enumerate(((0, -0.45, 2.4, 0), (0, 0.45, 2.4, 0), (-1.12, 0, 0.8, 90), (1.12, 0, 0.8, 90))):
        W.add_log(ctx, f"side{k}", L, 0.11, ctx.seed + k, at=(cx, cy, 0.11), rot=(0, 0, rot), moss=0.4)
        W.add_log(ctx, f"side_top{k}", L * 0.98, 0.09, ctx.seed + 10 + k, at=(cx, cy, 0.3), rot=(0, 0, rot), moss=0.4)
    soil = K.box("soil", (2.15, 0.82, 0.3), center=(0, 0, 0.15))
    K.noise_disp(soil, 0.02, scale=4.0, seed=ctx.seed)
    ctx.add(soil, SOIL, uv="box", uv_scale=1.0)
    r = ctx.rnd("stalks")
    for k in range(26):
        x = -0.95 + (k % 13) * 0.16 + r.uniform(-0.03, 0.03)
        y = -0.2 if k < 13 else 0.2
        h = r.uniform(0.15, 0.45)
        W.rod(ctx, f"stalk{k}", (x, y, 0.3), (x + r.uniform(-0.1, 0.1), y + r.uniform(-0.1, 0.1), 0.3 + h), 0.008, STALK, r2=0.003, segs=4)
    for t, tx in enumerate((-0.6, 0.6)):
        top = Vector((tx, 0, 1.75))
        if ctx.worn and t == 1:
            top = Vector((tx - 0.2, -0.9, 0.55))
        feet = [Vector((tx + 0.3 * math.cos(a), 0.3 * math.sin(a), 0.3)) for a in (0.3, 2.4, 4.4)]
        for j, f in enumerate(feet):
            W.rod(ctx, f"pole{t}{j}", f, top + (f - top) * -0.08, 0.014, PEELED, segs=5)
            # The dead vine wound up the pole.
            vine = [f.lerp(top, s) + Vector((0.025 * math.cos(s * 30), 0.025 * math.sin(s * 30), 0)) for s in [i / 16 * 0.85 for i in range(17)]]
            ctx.add(K.tube(f"vine{t}{j}", vine, 0.006, segs=4), STALK, uv="box", uv_scale=4.0, ao=False)
        _lash(ctx, f"tie{t}", top + Vector((0, 0, -0.06)), 0.03)
    sq = K.blob("squash", 0.13, subdiv=2, scale=(1.3, 1.0, 0.8), center=(0.15, 0.22, 0.38), rough=0.15, seed=ctx.seed)
    ctx.add(sq, "farm_preserve_spoiled", uv="box", uv_scale=2.0, smooth=40)


def w5_treehouse_garden_fence(ctx: K.Ctx) -> None:
    """2 m of stick-and-wire deer fence round the garden: two peeled posts, a top pole, chicken wire stapled from a
    bottom board to the top at 1.6 m. Worn: a post leaning out and the wire sagging off it."""
    lean = 8.0 if ctx.worn else 0.0
    for k, x in enumerate((-1.0, 1.0)):
        top = Vector((x, 0, 1.65))
        if k == 1 and ctx.worn:
            top = Vector((x - 0.05, -math.sin(math.radians(lean)) * 1.65, 1.65 * math.cos(math.radians(lean))))
        W.pole(ctx, f"post{k}", [(x, 0, 0.0), top], 0.06, PEELED, r_end=0.05, segs=8, moss=0.3)
    W.pole(ctx, "top", [(-1.04, 0, 1.6), (1.04, -0.2 if ctx.worn else 0, 1.58 if ctx.worn else 1.6)], 0.03, PEELED, r_end=0.028, segs=6)
    _bx(ctx, "board", (2.0, 0.025, 0.16), (0, 0.03, 0.08), LUMBER, bevel=0.004, uv_scale=1.0)
    sag = 0.2 if ctx.worn else 0.0
    wire = K.quad_sheet("wire", (-0.98, 0.0, 0.1), (0.98, -sag, 0.1), (0.98, -sag * 1.4, 1.58 - sag), (-0.98, 0.0, 1.58), nu=4, nv=4)
    ctx.add(wire, WIRE, uv="box", uv_scale=1.5, ao=False)


def w5_treehouse_fallen_rafters(ctx: K.Ctx) -> None:
    """Charred rafters and roof boards that fell into the cabin when it burned: four rafters lying crossed at angles,
    the highest leaning up to 1.25 m, shingle boards black and split, and a heap of ash and nails. Worn: broken
    shorter, the ash rained down flat."""
    r = ctx.rnd("rafters")
    raft = [((-1.2, -0.6, 0.06), (1.1, 0.4, 1.2)), ((-1.0, 0.7, 0.05), (1.2, -0.2, 0.4)), ((-0.4, -0.85, 0.05), (0.3, 0.85, 0.75)),
            ((0.6, -0.8, 0.05), (1.25, 0.7, 0.08))]
    for k, (a, b) in enumerate(raft):
        if ctx.worn and k == 0:
            b = (0.2, 0.0, 0.7)
        bar = W.bar_obj(f"rafter{k}", a, b, 0.06, 0.15, up=(0, 0, 1))
        K.noise_disp(bar, 0.01, scale=6.0, seed=ctx.seed + k)
        ctx.add(bar, CHAR, uv="box", uv_scale=1.5)
    for k in range(6):
        x, y = r.uniform(-1.0, 1.0), r.uniform(-0.7, 0.7)
        p = K.box(f"board{k}", (0.9, 0.14, 0.02), bevel=0.003)
        K.place(p, (x, y, 0.02 + k * 0.01), (r.uniform(-8, 8), r.uniform(-8, 8), r.uniform(0, 180)))
        ctx.add(p, CHAR if k % 2 else "wood_weathered", uv="box", uv_scale=1.5, patches=0.9)
    heap = K.blob("ash", 0.6, subdiv=2, scale=(1.4, 1.0, 0.15 if ctx.worn else 0.25), center=(-0.2, 0.1, 0.0), rough=0.3, seed=ctx.seed)
    ctx.add(heap, ASH, uv="box", uv_scale=1.0)


def w5_treehouse_stores_chest(ctx: K.Ctx) -> None:
    """The family's stores chest: a plank box on runners, rope handles at the ends, a hinged lid with a hasp and an
    open padlock hanging, STORES in white paint on the front and a tally of jars scratched beside it. Worn: the lid
    split along a board, the paint flaked."""
    Wd, Dp, Hh = 1.1, 0.58, 0.5
    for k in range(4):
        z = 0.06 + k * 0.11 + 0.055
        _bx(ctx, f"front{k}", (Wd, 0.025, 0.105), (0, -Dp / 2 + 0.0125, z), LUMBER, bevel=0.004, uv_scale=1.0, long_axis=0)
        _bx(ctx, f"back{k}", (Wd, 0.025, 0.105), (0, Dp / 2 - 0.0125, z), LUMBER, bevel=0.004, uv_scale=1.0, long_axis=0)
    for sx in (-1, 1):
        _bx(ctx, f"end{sx}", (0.025, Dp - 0.05, 0.44), (sx * (Wd / 2 - 0.0125), 0, 0.28), PLANK, bevel=0.004, uv_scale=1.0)
        _bx(ctx, f"runner{sx}", (0.08, Dp, 0.06), (sx * (Wd / 2 - 0.1), 0, 0.03), LUMBER, bevel=0.006, uv_scale=1.0)
        _rope(ctx, f"handle{sx}", [(sx * (Wd / 2 + 0.005), -0.1, 0.36), (sx * (Wd / 2 + 0.06), 0.0, 0.32), (sx * (Wd / 2 + 0.005), 0.1, 0.36)], 0.012)
    _bx(ctx, "bottom", (Wd - 0.05, Dp - 0.05, 0.03), (0, 0, 0.075), PLANK, bevel=0.0, uv_scale=1.0)
    lid_parts = []
    for k in range(3):
        y = -Dp / 2 + (k + 0.5) * Dp / 3
        lid_parts.append(K.box(f"lid{k}", (Wd + 0.03, Dp / 3 - 0.004, 0.03), center=(0, y, Hh + 0.015), bevel=0.004))
    for k, p in enumerate(lid_parts):
        if ctx.worn and k == 1:
            K.dent(p, (0.2, 0, Hh + 0.03), 0.25, 0.03)
        ctx.add(p, LUMBER, uv="box", uv_scale=1.0, long_axis=0)
    _bx(ctx, "cleat_l", (0.06, Dp, 0.02), (-0.4, 0, Hh + 0.04), LUMBER, bevel=0.003, uv_scale=1.0)
    _bx(ctx, "cleat_r", (0.06, Dp, 0.02), (0.4, 0, Hh + 0.04), LUMBER, bevel=0.003, uv_scale=1.0)
    _bx(ctx, "hasp", (0.05, 0.006, 0.12), (0, -Dp / 2 - 0.004, Hh - 0.04), STEEL, bevel=0.002)
    lock = K.box("padlock", (0.05, 0.02, 0.06), center=(0.0, -Dp / 2 - 0.02, Hh - 0.13), bevel=0.006)
    ctx.add(lock, "road_brass", uv="box", uv_scale=4.0)
    W.rod(ctx, "shackle", (-0.015, -Dp / 2 - 0.02, Hh - 0.1), (-0.015, -Dp / 2 - 0.02, Hh - 0.06), 0.004, STEEL, segs=5)
    _bx(ctx, "paint", (0.5 if not ctx.worn else 0.36, 0.003, 0.07), (-0.2, -Dp / 2 - 0.002, 0.3), "paint_white", bevel=0.0, ao=False)
    for k in range(7):
        _bx(ctx, f"tally{k}", (0.006, 0.003, 0.06), (0.22 + k * 0.025 if k < 4 else 0.31, -Dp / 2 - 0.002, 0.18 if k < 4 else 0.18),
            "wild_lumber_fresh", bevel=0.0, ao=False)


BUILDERS = {
    "w5_treehouse_trunk": w5_treehouse_trunk,
    "w5_treehouse_stilt": w5_treehouse_stilt,
    "w5_treehouse_rail": w5_treehouse_rail,
    "w5_treehouse_rope_rail": w5_treehouse_rope_rail,
    "w5_treehouse_bridge_planks": w5_treehouse_bridge_planks,
    "w5_treehouse_ladder_pulled": w5_treehouse_ladder_pulled,
    "w5_treehouse_pulley_lift": w5_treehouse_pulley_lift,
    "w5_treehouse_rain_barrel": w5_treehouse_rain_barrel,
    "w5_treehouse_garden_bed": w5_treehouse_garden_bed,
    "w5_treehouse_garden_fence": w5_treehouse_garden_fence,
    "w5_treehouse_fallen_rafters": w5_treehouse_fallen_rafters,
    "w5_treehouse_stores_chest": w5_treehouse_stores_chest,
}


def build(params: dict, outputs: list[str]) -> None:
    K.run(params, outputs, BUILDERS)
