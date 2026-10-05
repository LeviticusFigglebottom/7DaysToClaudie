"""Ashen watch camp props (Larch Hollow outskirts): the palisade (2 m and 1 m sections, the barred
gate, the burnt breach), effigies and bone totems, the bone chimes, a burial platform, pit huts, the
pyre, a hide frame, antler heaps, a stone fire pit, hide beds, the cache and hide bundles, and the
shells that dress the camp's kit rooms (longhouse, smoke hut, lean-to), plus the plank door leaf
(models/kit/door_plank*) those rooms hang in their doorways.

The Ashen built from what the valley gave them: bark-on fir stakes and poles, bark slabs and sod,
hide, sinew, bone, antler, river stone and lichen-ash smeared over all of it.

Conventions (docs/ASSET_PIPELINE.md): metres, Z up, front -Y, origin bottom centre. Palisade
sections face -Y into the compound (their rails and lashings are on that side); the gate faces -Y
out toward the approach (the bar is on +Y, inside). Shells: origin at the kit room's plan centre on
the ground (lib.props_outskirts_parts.Room). 'clean' is the camp as the Ashen kept it, 'worn' after
a season of neglect, 'destroyed' burnt or collapsed.
"""
from __future__ import annotations

import math
import random

from mathutils import Vector

from lib import props_ext_kit as K
from lib import props_ext_parts as P
from lib import props_outskirts_parts as O
from lib import props_wild_parts as W


def _soot(level: float, inward: Vector):
    """Vertex-wear term darkening faces that look into a room (smoke and soot inside)."""
    def f(co, n):
        return level if n.dot(inward) > 0.3 else 0.0
    return f


# ============================================================================================
# Palisade
# ============================================================================================

def _palisade(ctx: K.Ctx, L: float) -> None:
    """Bark-on fir stakes set in an earth berm, two split rails lashed on the inside (-Y)."""
    r = ctx.rnd("pal")
    stakes = []
    x = -L / 2 + 0.12
    while x < L / 2 - 0.08:
        rad = r.uniform(0.11, 0.145)
        stakes.append([x + rad, rad])
        x += rad * 2 * 0.94
    scale = (L - 0.06) / max(0.1, (stakes[-1][0] + stakes[-1][1]) - (stakes[0][0] - stakes[0][1]))
    x0 = stakes[0][0] - stakes[0][1]
    for s in stakes:
        s[0] = -L / 2 + 0.03 + (s[0] - x0) * scale
    burnt = ctx.destroyed
    for k, (sx, rad) in enumerate(stakes):
        seed = ctx.seed * 31 + k
        h = r.uniform(2.95, 3.42)
        lean = (r.uniform(-1.5, 1.5), r.uniform(-1.5, 1.5))
        dr = ctx.drnd(f"st{k}")
        if ctx.worn and not burnt and dr.random() < 0.18:
            lean = (dr.uniform(-5, 5), dr.uniform(-3, 3))
        if burnt:
            st = O.stake_obj(f"stake{k}", h, rad, seed, char=1.0 if dr.random() < 0.7 else 0.0)
            cut = dr.uniform(0.5, 2.7) if dr.random() < 0.75 else h + 1
            if cut < h:
                K.cut_plane(st, (0, 0, cut), Vector((dr.uniform(-0.5, 0.5), dr.uniform(-0.5, 0.5), 1)).normalized(),
                            keep="below")
            K.place(st, (sx, r.uniform(-0.03, 0.03), 0), (lean[0] + dr.uniform(-4, 4), lean[1] + dr.uniform(-6, 6), 0))
            ctx.add(st, None, uv=None, smooth=48, patches=0.6, edge=1.0, low=0.8, low_h=0.6)
        else:
            O.add_stake(ctx, f"stake{k}", sx, r.uniform(-0.03, 0.03), h, rad, seed, lean=lean,
                        moss=0.5 if ctx.worn else 0.25)
    if not burnt:
        for k, z in enumerate((0.95, 2.36)):
            a = Vector((-L / 2 + 0.02, -0.19, z + r.uniform(-0.03, 0.03)))
            b = Vector((L / 2 - 0.02, -0.19, z + r.uniform(-0.03, 0.03)))
            O.add_log_between(ctx, f"rail{k}", a, b, 0.065, ctx.seed + 40 + k, sides=8, rings=3, moss=0.2)
            for j, (sx, rad) in enumerate(stakes):
                if j % 2 == (k % 2):
                    p = a.lerp(b, (sx - a.x) / (b.x - a.x)) + Vector((0, 0.05, 0))
                    O.lash(ctx, f"lash{k}_{j}", p, (0, 0, 1), 0.07, turns=2, width=0.07, seed=ctx.seed + j)
    else:
        # A burnt rail end fallen against the stakes, ash in the berm.
        lg = W.log_obj("fallen_rail", L * 0.7, 0.06, ctx.seed + 7, sides=7, rings=3, bark="wood_charred",
                       end="wood_charred")
        K.place(lg, (r.uniform(-0.2, 0.2), -0.35, 0.18), (0, r.uniform(-14, -8), r.uniform(-6, 6)))
        ctx.add(lg, None, uv=None, smooth=40, patches=0.6)
    # The earth berm the stakes stand in: a long low mound both sides.
    for side in (-1, 1):
        rings = []
        for i in range(7):
            t = i / 6
            x = -L / 2 + L * t
            w = 0.24 + 0.03 * math.sin(t * 9 + side)
            rings.append([(x, side * (0.12 + w * u), 0.11 * (1 - u * u) + 0.005) for u in (0.0, 0.45, 0.8, 1.0)])
        berm = K.loft(f"berm{side}", [[*ring, (ring[-1][0], ring[0][1], 0.0)] for ring in rings], closed_ring=False,
                      cap_start=False, cap_end=False, recalc=False)
        K.noise_disp(berm, 0.025, scale=4.0, seed=ctx.seed + side)
        ctx.add(berm, "out_earth", uv="box", uv_scale=1.2, smooth=50, patches=0.2,
                moss=0.6 if ctx.worn else 0.35, base=0.4 if burnt else 0.0)
    if burnt:
        for k in range(5):
            c = K.chunk(f"char{k}", r.uniform(0.08, 0.16), r, n=10, flat=0.5)
            K.place(c, (r.uniform(-L / 2, L / 2), r.uniform(-0.6, 0.2), 0.03))
            ctx.add(c, "wood_charred", uv="box", uv_scale=2.0, patches=0.3)
    ctx.col_box((-L / 2, -0.26, 0), (L / 2, 0.22, 3.0 if not burnt else 1.6))


def out_palisade(ctx: K.Ctx) -> None:
    """Two metres of palisade (see _palisade). Destroyed: burnt, stakes snapped and charred."""
    _palisade(ctx, 2.0)


def out_palisade_half(ctx: K.Ctx) -> None:
    """One metre of palisade, to close a run."""
    _palisade(ctx, 1.0)


def out_palisade_gate(ctx: K.Ctx) -> None:
    """Double gate between two heavy posts under a lintel: split-log leaves with battens and a brace
    on the inside (+Y), a squared bar across them in forked brackets, an elk skull with its antlers
    over the gate, two deer skulls and strings of bone from the lintel (all facing -Y, outward)."""
    r = ctx.rnd("gate")
    for sx in (-1, 1):
        O.add_stake(ctx, f"post{sx}", sx * 1.58, 0.0, 3.95, 0.2, ctx.seed + sx, moss=0.3)
    lintel_a, lintel_b = Vector((-1.95, -0.02, 3.38)), Vector((1.95, 0.0, 3.4))
    O.add_log_between(ctx, "lintel", lintel_a, lintel_b, 0.15, ctx.seed + 3, sides=10, moss=0.3)
    for sx in (-1, 1):
        O.lash(ctx, f"lintel_lash{sx}", (sx * 1.58, -0.02, 3.39), (0, 1, 0), 0.2, turns=3, width=0.12, seed=sx)
    sag = 2.5 if ctx.worn else 0.0
    for side in (-1, 1):
        hinge_x = side * 1.36
        leaf = []
        n = 5
        for k in range(n):
            x = hinge_x - side * (0.14 + k * 0.265)
            h = 2.95 + r.uniform(-0.08, 0.06)
            # A half log, round side out (-Y), split face in (+Y) where the battens are nailed.
            pts = [(0.14 * r.uniform(0.94, 1.04) * math.cos(math.pi * i / 6), 0.14 * r.uniform(0.94, 1.04)
                    * math.sin(math.pi * i / 6)) for i in range(7)]
            lg = K.prism(f"leaf{side}{k}", pts, h, plane="YZ")
            K.place(lg, rot=(0, -90, 90))
            K.place(lg, (x, 0.04, 0.12 + h / 2))
            leaf.append(ctx.add(lg, "out_bark_ash", uv="box", uv_scale=1.0, smooth=45, patches=0.5, edge=1.0,
                                moss=0.35))
            tip = K.lathe(f"tip{side}{k}", [(0.13, 0.0), (0.0, 0.32)], segs=6, cap_bottom=False)
            K.place(tip, (x, 0.02, 0.12 + h))
            leaf.append(ctx.add(tip, "out_log_peeled", uv="box", uv_scale=1.5, patches=0.4))
        x_in, x_out = hinge_x - side * 0.04, hinge_x - side * 1.3
        for z in (0.55, 2.55):
            leaf.append(W.bar(ctx, f"batten{side}{z}", (x_in, 0.16, z), (x_out, 0.16, z), 0.16, 0.07, "out_log_peeled",
                              up=(0, 1, 0), bevel=0.01))
        leaf.append(W.bar(ctx, f"brace{side}", (x_in, 0.17, 0.62), (x_out, 0.17, 2.48), 0.14, 0.06, "out_log_peeled",
                          up=(0, 1, 0), bevel=0.01))
        for z in (0.55, 2.55):
            leaf.append(O.lash(ctx, f"hinge{side}{z}", (hinge_x + side * 0.12, 0.05, z), (0, 0, 1), 0.2, turns=2,
                               width=0.1, seed=int(z * 10)))
        if sag and side < 0:
            K.kink(leaf, (hinge_x, 0, 0), (0, sag * side, 0), axis=2, blend=0.01)
    # The bar in its forked brackets (inside), lashed hooks on both posts.
    W.bar(ctx, "bar", (-1.72, 0.33, 1.28), (1.72, 0.33, 1.3), 0.17, 0.2, "out_log_peeled", up=(0, 0, 1), bevel=0.015)
    for sx in (-1, 1):
        fork = [Vector((sx * 1.58, 0.16, 1.05)), Vector((sx * 1.6, 0.32, 1.16)), Vector((sx * 1.6, 0.45, 1.45))]
        W.pole(ctx, f"fork{sx}", fork, 0.035, "out_bark_ash", r_end=0.025, seed=5 + sx)
        W.pole(ctx, f"fork{sx}b", [fork[1], fork[1] + Vector((0, -0.02, 0.32))], 0.03, "out_bark_ash", r_end=0.02, seed=7 + sx)
        O.lash(ctx, f"forklash{sx}", (sx * 1.58, 0.1, 1.12), (0, 0, 1), 0.21, turns=3, width=0.1, seed=sx + 9)
    # Skulls and antlers over the gate; bone strings from the lintel.
    O.add_skull(ctx, "elk", (0.0, -0.22, 3.62), (8, 0, 0), 0.34, ctx.seed + 11, kind="elk", tines=5, ash=0.6,
                broken_tine=ctx.worn)
    for sx in (-1, 1):
        O.add_skull(ctx, f"deer{sx}", (sx * 0.95, -0.2, 3.58), (6, 0, sx * 8), 0.22, ctx.seed + 20 + sx, tines=3,
                    ash=0.3 if sx > 0 else 0.8)
    xs = (-1.2, -0.5, 0.45, 1.15) if not ctx.worn else (-1.2, 0.45, 1.15)
    for k, x in enumerate(xs):
        O.bone_string(ctx, f"str{k}", (x, -0.16, 3.25), r.uniform(0.45, 0.8), ctx.seed + 50 + k, n=4)
    ctx.col_box((-1.8, -0.2, 0), (1.8, 0.3, 3.4))


def out_palisade_breach(ctx: K.Ctx) -> None:
    """Burnt-through palisade: charred stumps at the gap's edges, two stakes fallen inward (-Y),
    ash, charcoal and scorched earth. Walk-through."""
    r = ctx.rnd("breach")
    for k, (x, h) in enumerate(((-0.46, 0.55), (-0.2, 0.14), (0.12, 0.09), (0.44, 0.48))):
        st = O.stake_obj(f"stump{k}", 1.5, r.uniform(0.11, 0.14), ctx.seed + k, char=1.0)
        K.cut_plane(st, (0, 0, h), Vector((r.uniform(-0.6, 0.6), r.uniform(-0.6, 0.6), 1)).normalized(), keep="below")
        K.place(st, (x, r.uniform(-0.03, 0.03), 0))
        ctx.add(st, None, uv=None, smooth=45, patches=0.6, edge=1.2)
    for k, (x, ang, L) in enumerate(((-0.25, -12, 2.1), (0.3, 18, 1.6))):
        lg = W.log_obj(f"fallen{k}", L, 0.12, ctx.seed + 30 + k, sides=8, rings=4, bark="wood_charred", end="wood_charred")
        K.place(lg, rot=(0, 0, 90 + ang))
        K.place(lg, (x, -L / 2 - 0.1, 0.11 + 0.02 * k), (r.uniform(-3, 3), 0, 0))
        ctx.add(lg, None, uv=None, smooth=45, patches=0.6, edge=1.0)
    ash = K.blob("ash", 0.6, subdiv=2, scale=(1.3, 1.2, 0.04), center=(0.0, -0.35, 0.0), rough=0.25, seed=ctx.seed)
    ctx.add(ash, "ash_burnt", uv="box", uv_scale=1.5, smooth=60, patches=0.2)
    for k in range(9):
        c = K.chunk(f"coal{k}", r.uniform(0.05, 0.12), r, n=9, flat=0.6)
        K.place(c, (r.uniform(-0.55, 0.55), r.uniform(-1.0, 0.25), 0.02))
        ctx.add(c, "wood_charred", uv="box", uv_scale=2.0, patches=0.3)
    berm = K.blob("berm", 0.5, subdiv=2, scale=(1.2, 0.5, 0.12), center=(0, 0.1, 0.0), rough=0.3, seed=ctx.seed + 2)
    ctx.add(berm, "out_earth", uv="box", uv_scale=1.2, smooth=55, base=0.45, moss=0.2)


# ============================================================================================
# Effigies, totems, chimes
# ============================================================================================

def _cairn(ctx, n, rad, seed, *, z=0.0, at=(0.0, 0.0)):
    """River stones heaped round a pole's foot at `at` (x, y)."""
    rr = random.Random(seed)
    for k in range(n):
        a = math.tau * k / n + rr.uniform(-0.3, 0.3)
        O.add_stone(ctx, f"cairn{k}", (at[0] + math.cos(a) * rad, at[1] + math.sin(a) * rad, z + 0.04),
                    rr.uniform(0.14, 0.24), seed + k, flat=0.55)
    for k in range(max(2, n // 3)):
        a = rr.uniform(0, math.tau)
        O.add_stone(ctx, f"cairn_top{k}", (at[0] + math.cos(a) * rad * 0.4, at[1] + math.sin(a) * rad * 0.4, z + 0.13),
                    rr.uniform(0.12, 0.18), seed + 40 + k, flat=0.6)


def out_effigy(ctx: K.Ctx) -> None:
    """An Ashen effigy: a pole with a shoulder bar and crooked branch arms, an elk skull and antlers
    for a head, a ribcage hung on the spine, a cape of ash-smeared hide down its back, a necklace of
    teeth and vertebrae, bone strings from the hands, a cairn at its foot. Worn: the cape in rags, a
    tine broken off, the whole figure leaning."""
    r = ctx.rnd("effigy")
    parts_before = len(ctx.parts)
    W.pole(ctx, "spine", [(0, 0.02, -0.05), (0.01, 0.02, 1.4), (0, 0.02, 2.78)], 0.07, "out_log_peeled", r_end=0.05,
           seed=ctx.seed, wobble=0.01, moss=0.15)
    W.pole(ctx, "shoulders", [(-0.58, 0.02, 2.14), (0, 0.0, 2.2), (0.58, 0.02, 2.16)], 0.05, "out_log_peeled",
           r_end=0.04, seed=ctx.seed + 1)
    O.lash(ctx, "shoulder_lash", (0, 0.0, 2.18), (1, 0, 0), 0.075, turns=3, width=0.1, seed=3)
    for side in (-1, 1):
        arm = [Vector((side * 0.56, 0.0, 2.16)), Vector((side * 0.78, -0.08, 1.72)), Vector((side * 0.8, -0.2, 1.24)),
               Vector((side * 0.72, -0.26, 1.02))]
        W.pole(ctx, f"arm{side}", arm, 0.035, "out_bark_ash", r_end=0.018, seed=ctx.seed + 4 + side, wobble=0.02)
        for f in range(3):
            tip = arm[-1] + Vector((side * r.uniform(-0.05, 0.08), r.uniform(-0.12, 0.0), -r.uniform(0.12, 0.22)))
            W.pole(ctx, f"finger{side}{f}", [arm[-1], tip], 0.012, "out_bark_ash", r_end=0.004, seed=f)
        O.bone_string(ctx, f"hand_str{side}", arm[2] + Vector((0, -0.02, -0.02)), r.uniform(0.35, 0.55),
                      ctx.seed + 60 + side, n=3)
    O.add_skull(ctx, "head", (0.0, -0.04, 2.92), (12, 0, r.uniform(-6, 6)), 0.33, ctx.seed + 9, kind="elk", tines=5,
                ash=0.8, broken_tine=ctx.worn)
    for k in range(6):
        z = 1.95 - k * 0.11
        rr = 0.21 - 0.012 * k
        for side in (-1, 1):
            rib = O.rib_obj(f"rib{k}{side}", rr, ctx.seed + k * 3 + side, arc=150, side=side)
            K.place(rib, rot=(0, 0, 90))
            K.place(rib, (0, -0.02 - rr * 0.6, z), (0, -8, 0))
            ctx.add(rib, "out_bone", uv="box", uv_scale=4.0, smooth=50, patches=0.4)
    # The cape: a hide hanging from the shoulder bar down the back, ragged at the hem.
    cape = O.hide_obj("cape", 1.25, 1.35, ctx.seed + 2, nx=12, ny=12, ragged=0.22 if ctx.worn else 0.1)
    K.map_verts(cape, lambda co: Vector((co.x * (1.0 + 0.25 * max(0.0, -co.z) / 0.7),
                                         0.1 + 0.05 * math.sin(co.x * 7) + 0.18 * max(0.0, -co.z) / 0.7, co.z)))
    K.place(cape, (0, 0.06, 2.12 - 0.66))
    if ctx.worn:
        K.jagged_hole(cape, (0.2, 0.15, 1.65), 0.18, ctx.seed, axis=1, jag=0.5)
    K.solidify(cape, 0.008, offset=-1.0, even=False)
    ctx.add(cape, "out_hide_ash", uv=None, smooth=50, patches=0.5, edge=0.6)
    # Necklace across the chest.
    pts = [Vector((-0.42, -0.12, 2.12)), Vector((-0.2, -0.24, 1.92)), Vector((0, -0.28, 1.86)),
           Vector((0.2, -0.24, 1.92)), Vector((0.42, -0.12, 2.12))]
    cord = K.tube("neck_cord", pts, 0.004, segs=4)
    ctx.add(cord, "out_sinew", uv="cyl", uv_axis=0, smooth=40)
    for k in range(9):
        t = (k + 0.5) / 9
        i = min(3, int(t * 4))
        p = pts[i].lerp(pts[i + 1], t * 4 - i)
        o = O.tooth_obj(f"neck_t{k}", 0.04, ctx.seed + k) if k % 3 else O.vertebra_obj(f"neck_v{k}", 0.045, k)
        if k % 3:
            K.place(o, rot=(180, 0, 0))
        K.place(o, p - Vector((0, 0, 0.02)))
        ctx.add(o, "out_bone", uv="box", uv_scale=6.0, smooth=50, patches=0.4)
    _cairn(ctx, 9, 0.32, ctx.seed + 70)
    for k in range(2):
        O.add_bone(ctx, f"foot_bone{k}", (r.uniform(-0.6, -0.3), r.uniform(-0.5, -0.2), 0.04),
                   (r.uniform(0.1, 0.4), r.uniform(-0.6, -0.3), 0.05), 0.022, ctx.seed + 80 + k)
    if ctx.worn:
        K.kink(ctx.parts[parts_before:], (0, 0, 0.05), (r.uniform(2, 4), r.uniform(-3, 3), 0), axis=2, blend=0.3)
    ctx.col_box((-0.25, -0.25, 0), (0.25, 0.25, 2.8))


def out_bone_totem(ctx: K.Ctx) -> None:
    """A peeled pole with a deer skull and antlers lashed near the top, a fork of shed antler above
    it, three strings of bone from a little cross-stick and a band of ash-paint; a cairn at its foot."""
    r = ctx.rnd("totem")
    W.pole(ctx, "pole", [(0, 0, -0.05), (0.01, 0.01, 1.2), (0, 0, 2.25)], 0.055, "out_log_peeled", r_end=0.04,
           seed=ctx.seed, wobble=0.01, extra=lambda co, n: 0.55 if 1.1 < co.z < 1.35 else 0.0)
    O.add_skull(ctx, "skull", (0.0, -0.1, 1.9), (10, 0, 0), 0.22, ctx.seed + 3, tines=3, ash=0.5,
                broken_tine=ctx.worn)
    O.lash(ctx, "skull_lash", (0, -0.02, 1.86), (0, 0, 1), 0.06, turns=3, width=0.08, seed=1)
    a = O.antler_obj("fork", 0.5, ctx.seed + 5, side=1, tines=2)
    K.place(a, (0.0, 0.0, 2.05), (0, -20, 30))
    ctx.add(a, "out_antler", uv="box", uv_scale=3.0, smooth=50, patches=0.5)
    W.pole(ctx, "cross", [(-0.28, -0.02, 1.62), (0.28, -0.02, 1.64)], 0.022, "out_bark_ash", r_end=0.018, seed=4)
    for k, x in enumerate((-0.22, 0.02, 0.24)):
        if ctx.worn and k == 1:
            continue
        O.bone_string(ctx, f"str{k}", (x, -0.03, 1.6), r.uniform(0.35, 0.6), ctx.seed + 20 + k, n=3)
    _cairn(ctx, 7, 0.22, ctx.seed + 30)
    ctx.col_box((-0.2, -0.2, 0), (0.2, 0.2, 2.2))


def out_bone_chime(ctx: K.Ctx) -> None:
    """A forked post with an arm reaching over a passage (along -X from the post at +0.6 m), hung
    with strings of bone, antler tines and teeth. The arm's underside is at 2.73 m, where the POI's
    bell-style alarm hangs its trap bell among the bones (x = 0 is left clear for it)."""
    r = ctx.rnd("chime")
    W.pole(ctx, "post", [(0.62, 0, -0.05), (0.61, 0.01, 1.4), (0.62, 0, 2.95)], 0.065, "out_log_peeled", r_end=0.05,
           seed=ctx.seed, wobble=0.01, moss=0.2)
    W.pole(ctx, "fork", [(0.62, 0, 2.7), (0.68, 0.0, 3.0), (0.72, 0, 3.08)], 0.03, "out_log_peeled", r_end=0.02,
           seed=ctx.seed + 1)
    W.pole(ctx, "arm", [(0.78, 0, 2.78), (0.0, 0.0, 2.77), (-0.78, 0.0, 2.8)], 0.04, "out_bark_ash", r_end=0.03,
           seed=ctx.seed + 2)
    O.lash(ctx, "arm_lash", (0.62, 0, 2.78), (1, 0, 0), 0.07, turns=3, width=0.09, seed=2)
    O.add_skull(ctx, "post_skull", (0.62, -0.08, 3.12), (6, 0, 10), 0.18, ctx.seed + 4, tines=2, ash=0.6)
    xs = (-0.7, -0.5, -0.3, 0.2, 0.36, 0.5) if not ctx.worn else (-0.7, -0.3, 0.2, 0.5)
    for k, x in enumerate(xs):
        O.bone_string(ctx, f"str{k}", (x, r.uniform(-0.04, 0.04), 2.74), r.uniform(0.45, 0.95), ctx.seed + 10 + k,
                      n=r.randint(3, 6))
    _cairn(ctx, 6, 0.2, ctx.seed + 30, at=(0.62, 0.0))


# ============================================================================================
# Burial platform, pit hut, pyre, hide frame, antler heap, fire pit
# ============================================================================================

def _body_bundle(ctx, name, L, w, h, at, rot, seed):
    """A body wrapped in hide and lashed: a lofted bundle along X, head end rounder."""
    rings = []
    for i in range(9):
        t = i / 8
        x = -L / 2 + L * t
        k = math.sin(math.pi * (0.06 + 0.88 * t)) ** 0.55 * (1.0 if t > 0.25 else 0.85 + 0.6 * t)
        ring = []
        for j in range(10):
            a = math.tau * j / 10
            ring.append((x, math.cos(a) * w * 0.5 * k, math.sin(a) * h * 0.5 * k * (0.75 if math.sin(a) < 0 else 1.0)))
        rings.append(ring)
    o = K.loft(name, rings)
    K.noise_disp(o, 0.012, scale=6.0, seed=seed)
    K.place(o, at, rot)
    out = [ctx.add(o, "out_hide", uv="box", uv_scale=1.5, smooth=50, patches=0.5, edge=0.6)]
    for k in range(4):
        x = -L * 0.32 + k * L * 0.22
        c = Vector(at) + Vector((x, 0, 0))
        ring = []
        for j in range(10):
            a = math.tau * j / 10
            ring.append(Vector((x, math.cos(a) * w * 0.52, math.sin(a) * h * 0.5)))
        cord = K.tube(f"{name}_tie{k}", ring, 0.008, segs=4, closed=True)
        K.place(cord, at, rot)
        out.append(ctx.add(cord, "out_rawhide", uv="box", uv_scale=4.0, smooth=40))
        _ = c
    return out


def out_burial_platform(ctx: K.Ctx) -> None:
    """Four forked poles carrying a lashed platform at two metres, a hide-wrapped body on it; antlers
    on two post tops, a skull on a third, bones hung from the side beams, a rawhide thong on the
    south-west post (-X, -Y) at 1.45 m where the cache key hangs."""
    r = ctx.rnd("platform")
    posts = [(-1.1, -0.8), (1.1, -0.8), (-1.1, 0.8), (1.1, 0.8)]
    for k, (x, y) in enumerate(posts):
        W.pole(ctx, f"post{k}", [(x, y, -0.05), (x + r.uniform(-0.02, 0.02), y, 1.4), (x, y, 2.62)], 0.08,
               "out_bark_ash", r_end=0.065, seed=ctx.seed + k, wobble=0.015, moss=0.3)
    for k, y in enumerate((-0.8, 0.8)):
        W.pole(ctx, f"beam{k}", [(-1.32, y, 1.96), (0, y, 1.94), (1.32, y, 1.97)], 0.065, "out_bark_ash", r_end=0.06,
               seed=ctx.seed + 10 + k)
        for x in (-1.1, 1.1):
            O.lash(ctx, f"beam_lash{k}{x}", (x, y, 1.96), (0, 0, 1), 0.1, turns=3, width=0.1, seed=k)
    n = 13
    for i in range(n):
        x = -1.05 + 2.1 * i / (n - 1)
        if ctx.worn and i in (3, 4):
            continue
        W.pole(ctx, f"deck{i}", [(x, -0.98, 2.05), (x + 0.01, 0, 2.06), (x, 0.98, 2.05)], 0.04, "out_log_peeled",
               r_end=0.035, seed=ctx.seed + 20 + i)
    _body_bundle(ctx, "body", 1.75, 0.46, 0.32, (0.05, 0.0, 2.27), (0, 0, r.uniform(-4, 4)), ctx.seed + 5)
    for k, (x, y) in enumerate(posts[:2]):
        a = O.antler_obj(f"post_antler{k}", 0.65, ctx.seed + 40 + k, side=1 if x > 0 else -1, tines=3)
        K.place(a, (x, y, 2.55), (0, 0, 180 if x < 0 else 0))
        ctx.add(a, "out_antler", uv="box", uv_scale=3.0, smooth=50, patches=0.5)
    O.add_skull(ctx, "post_skull", (-1.1, 0.72, 2.72), (8, 0, 180), 0.2, ctx.seed + 50, tines=2, ash=0.7)
    for k, x in enumerate((-0.7, -0.15, 0.45, 0.9)):
        y = -0.82 if k % 2 else 0.82
        O.bone_string(ctx, f"str{k}", (x, y, 1.9), r.uniform(0.35, 0.6), ctx.seed + 60 + k, n=4)
    # The key's thong on the south-west post.
    thong = K.tube("thong", [(-1.1, -0.9, 1.62), (-1.12, -0.93, 1.52), (-1.1, -0.92, 1.42)], 0.005, segs=4)
    ctx.add(thong, "out_rawhide", uv="cyl", uv_axis=2, smooth=40)
    O.lash(ctx, "thong_tie", (-1.1, -0.8, 1.62), (0, 0, 1), 0.085, turns=2, width=0.04, seed=8)
    for k in range(3):
        O.add_stone(ctx, f"offer{k}", (r.uniform(-0.6, 0.6), r.uniform(-0.6, 0.6), 0.04), 0.18, ctx.seed + 70 + k)
    ctx.col_box((-1.25, -0.95, 0), (1.25, 0.95, 2.4))


def out_pit_hut(ctx: K.Ctx) -> None:
    """A pit hut: an earth rim round a dug floor, a cone of poles tied at the top, covered in bark
    slabs with sod over their lower courses and a hide flap over the entrance (-Y). Worn: slabs
    slipped and gaps in the cover. Destroyed: burnt to a charred frame, half fallen, ash in the pit."""
    r = ctx.rnd("pithut")
    burnt = ctx.destroyed
    rim = K.lathe("rim", [(0.92, 0.0), (1.0, 0.18), (1.18, 0.3), (1.4, 0.2), (1.55, 0.0)], segs=18, cap_bottom=False,
                  cap_top=False)
    K.noise_disp(rim, 0.04, scale=3.0, seed=ctx.seed)
    ctx.add(rim, "out_earth", uv="box", uv_scale=1.0, smooth=55, moss=0.0 if burnt else 0.55, patches=0.3)
    pit = K.cyl("pit", 0.95, 0.02, segs=18, center=(0, 0, 0.01))
    ctx.add(pit, "ash_burnt" if burnt else "out_earth", uv="box", uv_scale=1.0, base=0.6, patches=0.2)
    apex = Vector((r.uniform(-0.05, 0.05), r.uniform(-0.05, 0.05), 2.45))
    n = 10
    poles = []
    for k in range(n):
        a = math.tau * (k + 0.5) / n - math.pi / 2
        base = Vector((math.cos(a) * 1.08, math.sin(a) * 1.08, 0.22))
        top = apex + (apex - base).normalized() * r.uniform(0.15, 0.32)
        if burnt and ctx.drnd(f"p{k}").random() < 0.4:
            top = base.lerp(top, ctx.drnd(f"q{k}").uniform(0.3, 0.6))
        poles.append((base, top))
        W.pole(ctx, f"pole{k}", [base, base.lerp(top, 0.5), top], 0.045, "wood_charred" if burnt else "out_log_peeled",
               r_end=0.03, seed=ctx.seed + k)
    if not burnt:
        O.lash(ctx, "apex_lash", apex - Vector((0, 0, 0.05)), (0, 0, 1), 0.11, turns=4, width=0.12, seed=4)
        rows = 5
        for i in range(rows):
            t0 = i / rows
            for k in range(14):
                a = math.tau * (k + 0.5 * (i % 2)) / 14 - math.pi / 2
                if abs(math.atan2(math.sin(a + math.pi / 2), math.cos(a + math.pi / 2))) < 0.42:
                    continue  # the entrance (-Y)
                if ctx.worn and ctx.drnd(f"s{i}{k}").random() < 0.2:
                    continue
                rad0 = 1.1 * (1 - t0 * 0.92)
                z0 = 0.22 + 2.2 * t0
                slab = K.box(f"slab{i}{k}", (0.42 * (1 - t0 * 0.6), 0.55, 0.035), cuts=(2, 2, 0))
                K.noise_disp(slab, 0.012, scale=5.0, seed=i * 31 + k)
                tilt = math.degrees(math.atan2(2.2, 1.1 * 0.92))
                K.place(slab, rot=(-(90 - tilt) + r.uniform(-4, 4), r.uniform(-4, 4), 0))
                K.place(slab, (0, 0, 0), (0, 0, math.degrees(a) - 90))
                p = Vector((math.cos(a) * (rad0 + 0.06), math.sin(a) * (rad0 + 0.06), z0 + 0.25))
                K.place(slab, p)
                ctx.add(slab, "out_bark_slab", long_axis=1, uv_scale=1.0, patches=0.5,
                        moss=0.7 if ctx.worn else 0.45)
        for k in range(10):
            a = math.tau * k / 10 - math.pi / 2
            if abs(math.atan2(math.sin(a + math.pi / 2), math.cos(a + math.pi / 2))) < 0.5:
                continue
            sod = K.blob(f"sod{k}", 0.32, subdiv=2, scale=(1.4, 0.7, 0.35), rough=0.3, seed=ctx.seed + k)
            K.place(sod, rot=(0, 0, math.degrees(a) + 90))
            K.place(sod, (math.cos(a) * 1.02, math.sin(a) * 1.02, 0.5), (0, 0, 0))
            ctx.add(sod, "out_sod", uv="box", uv_scale=1.0, smooth=55, patches=0.2, moss=0.9)
        flap = O.hide_obj("flap", 0.7, 1.3, ctx.seed + 3, ragged=0.08)
        K.place(flap, (0.0, -0.98, 0.95), (12, 0, 0))
        K.solidify(flap, 0.006, offset=-1.0, even=False)
        ctx.add(flap, "out_hide", uv=None, smooth=50, patches=0.4)
    else:
        for k in range(3):
            lg = W.log_obj(f"fallen{k}", r.uniform(1.0, 1.8), 0.045, ctx.seed + 30 + k, sides=7, rings=3,
                           bark="wood_charred", end="wood_charred")
            K.place(lg, (r.uniform(-0.6, 0.6), r.uniform(-0.6, 0.6), 0.1), (r.uniform(-10, 10), 0, r.uniform(0, 180)))
            ctx.add(lg, None, uv=None, smooth=45, patches=0.5)
        ash = K.blob("ash", 0.8, subdiv=2, scale=(1.0, 1.0, 0.06), center=(0, 0, 0.02), rough=0.3, seed=ctx.seed)
        ctx.add(ash, "ash_burnt", uv="box", uv_scale=1.5, smooth=60)
    ctx.col_box((-0.95, -0.95, 0), (0.95, 0.95, 2.1))


def out_pyre(ctx: K.Ctx) -> None:
    """Clean: a crib of split logs four courses high with kindling inside and a hide-wrapped body on
    top, waiting; old ash and charred bone round it. Worn: burnt down to charcoal, ash and bone."""
    r = ctx.rnd("pyre")
    ash = K.blob("ash_ring", 1.35, subdiv=3, scale=(1.0, 1.0, 0.035), center=(0, 0, 0.0), rough=0.25, seed=ctx.seed)
    ctx.add(ash, "ash_burnt", uv="box", uv_scale=1.2, smooth=60, patches=0.2)
    if ctx.clean:
        for layer in range(4):
            along_x = layer % 2 == 0
            for k in range(4):
                off = -0.72 + k * 0.48
                L = 2.1 + r.uniform(-0.1, 0.1)
                lg = P.log_split(f"crib{layer}{k}", L, 0.09, r, kind="half" if (layer + k) % 2 else "quarter")
                K.place(lg, rot=(r.uniform(0, 360), 0, 0 if along_x else 90))
                K.place(lg, (0 if along_x else off, off if along_x else 0, 0.1 + layer * 0.17))
                ctx.add(lg, "out_log_peeled", uv="box", uv_scale=1.0, smooth=40, patches=0.5, edge=1.0)
        for k in range(10):
            a = r.uniform(0, math.tau)
            p = Vector((math.cos(a) * 0.3, math.sin(a) * 0.3, 0.3))
            W.pole(ctx, f"kindling{k}", [p, p + Vector((r.uniform(-0.2, 0.2), r.uniform(-0.2, 0.2), 0.3))], 0.02,
                   "out_bark_ash", r_end=0.012, seed=k)
        _body_bundle(ctx, "body", 1.6, 0.42, 0.28, (0.0, 0.0, 0.88), (0, 0, 12), ctx.seed + 3)
        for k in range(3):
            lg = W.log_obj(f"spare{k}", r.uniform(1.4, 2.0), 0.09, ctx.seed + 20 + k, sides=8, rings=3, bark="out_bark_ash")
            K.place(lg, (1.25 + k * 0.08, r.uniform(-0.6, 0.6), 0.09 + k * 0.05), (0, 0, 80 + r.uniform(-10, 10)))
            ctx.add(lg, None, uv=None, smooth=45, patches=0.4)
    else:
        heap = K.blob("heap", 0.85, subdiv=3, scale=(1.1, 1.0, 0.28), center=(0, 0, 0.0), rough=0.35, seed=ctx.seed + 1)
        ctx.add(heap, "ash_burnt", uv="box", uv_scale=1.5, smooth=55, patches=0.3)
        for k in range(8):
            lg = W.log_obj(f"char{k}", r.uniform(0.5, 1.1), r.uniform(0.05, 0.08), ctx.seed + 30 + k, sides=7, rings=3,
                           bark="wood_charred", end="wood_charred")
            a = math.tau * k / 8
            K.place(lg, (math.cos(a) * 0.55, math.sin(a) * 0.55, 0.12), (r.uniform(-15, 15), r.uniform(-15, 15),
                                                                            math.degrees(a) + r.uniform(-30, 30)))
            ctx.add(lg, None, uv=None, smooth=45, patches=0.5)
    for k in range(6):
        a = r.uniform(0, math.tau)
        d = r.uniform(0.9, 1.3) if ctx.clean else r.uniform(0.1, 0.7)
        p = Vector((math.cos(a) * d, math.sin(a) * d, 0.04))
        O.add_bone(ctx, f"bone{k}", p, p + Vector((r.uniform(-0.2, 0.2), r.uniform(-0.2, 0.2), 0.01)), 0.016,
                   ctx.seed + 50 + k, mat="out_bone_ash")
    if not ctx.clean:
        sk = O.skull_obj("burnt_skull", 0.13, ctx.seed + 60, kind="deer")
        K.place(sk, (0.25, -0.2, 0.2), (40, 10, 30))
        ctx.add(sk, "out_bone_ash", uv="box", uv_scale=4.0, smooth=50, base=0.5)
    ctx.col_box((-1.1, -1.1, 0), (1.1, 1.1, 1.0 if ctx.clean else 0.3))


def out_hide_frame(ctx: K.Ctx) -> None:
    """A hide laced into a pole frame with sinew, propped on two back legs, ash-smeared."""
    r = ctx.rnd("hideframe")
    for sx in (-1, 1):
        W.pole(ctx, f"upright{sx}", [(sx * 0.75, 0.0, -0.03), (sx * 0.74, 0.05, 1.1), (sx * 0.73, 0.1, 2.12)], 0.045,
               "out_log_peeled", r_end=0.035, seed=ctx.seed + sx, wobble=0.01)
        W.pole(ctx, f"leg{sx}", [(sx * 0.7, 0.55, -0.02), (sx * 0.72, 0.1, 1.95)], 0.035, "out_bark_ash", r_end=0.03,
               seed=ctx.seed + 4 + sx)
    for k, z in enumerate((0.35, 1.98)):
        W.pole(ctx, f"cross{k}", [(-0.88, 0.02 + 0.08 * (z > 1), z), (0.88, 0.02 + 0.08 * (z > 1), z + 0.02)], 0.035,
               "out_log_peeled", r_end=0.03, seed=ctx.seed + 10 + k)
    hide = O.hide_obj("hide", 1.25, 1.42, ctx.seed + 3, ragged=0.1)
    if ctx.worn:
        K.jagged_hole(hide, (0.15, 0.0, 0.2), 0.16, ctx.seed, axis=1, jag=0.6)
    K.place(hide, (0, 0.05, 1.16), (-2, 0, 0))
    K.solidify(hide, 0.006, offset=-1.0, even=False)
    ctx.add(hide, "out_hide_ash", uv=None, smooth=50, patches=0.5)
    for k in range(14):
        t = k / 14
        if k < 4:
            a, b = Vector((-0.55 + t * 4 * 0.37, 0.06, 1.82)), Vector((-0.55 + t * 4 * 0.37, 0.09, 1.97))
        elif k < 8:
            a, b = Vector((-0.55 + (t * 14 - 4) * 0.37, 0.04, 0.5)), Vector((-0.55 + (t * 14 - 4) * 0.37, 0.03, 0.36))
        elif k < 11:
            z = 0.7 + (k - 8) * 0.38
            a, b = Vector((-0.6, 0.05, z)), Vector((-0.74, 0.05 + 0.04 * z / 2, z))
        else:
            z = 0.7 + (k - 11) * 0.38
            a, b = Vector((0.6, 0.05, z)), Vector((0.74, 0.05 + 0.04 * z / 2, z))
        cord = K.tube(f"lace{k}", [a, b], 0.004, segs=4)
        ctx.add(cord, "out_sinew", uv="cyl", uv_axis=2, smooth=40)
    ctx.col_box((-0.8, -0.1, 0), (0.8, 0.35, 2.0))


def out_antler_pile(ctx: K.Ctx) -> None:
    """Shed antlers heaped against a short post with two skulls and a few long bones."""
    r = ctx.rnd("antlers")
    W.pole(ctx, "post", [(0.0, 0.35, -0.03), (0.02, 0.36, 0.72)], 0.07, "out_bark_ash", r_end=0.06, seed=ctx.seed)
    for k in range(10):
        a = O.antler_obj(f"antler{k}", r.uniform(0.45, 0.8), ctx.seed + k, side=1 if k % 2 else -1, tines=r.randint(2, 4))
        K.place(a, (r.uniform(-0.45, 0.45), r.uniform(-0.3, 0.3), r.uniform(0.0, 0.12)),
                (r.uniform(-80, 80), r.uniform(-50, 50), r.uniform(0, 360)))
        K.lift_min(a, 0.0)
        ctx.add(a, "out_antler", uv="box", uv_scale=3.0, smooth=50, patches=0.5, moss=0.3)
    for k in range(2):
        sk = O.skull_obj(f"skull{k}", r.uniform(0.18, 0.24), ctx.seed + 20 + k)
        K.place(sk, (r.uniform(-0.35, 0.35), r.uniform(-0.25, 0.15), 0.1), (r.uniform(-20, 20), r.uniform(-30, 30),
                                                                            r.uniform(0, 360)))
        K.lift_min(sk, 0.0)
        ctx.add(sk, "out_bone", uv="box", uv_scale=4.0, smooth=55, patches=0.5)
    for k in range(4):
        p = Vector((r.uniform(-0.5, 0.4), r.uniform(-0.35, 0.3), 0.03))
        O.add_bone(ctx, f"bone{k}", p, p + Vector((r.uniform(0.2, 0.4), r.uniform(-0.2, 0.2), 0.02)), 0.02,
                   ctx.seed + 40 + k)


def out_stone_fire_pit(ctx: K.Ctx) -> None:
    """River stones in a ring round old ash and charcoal, half-burnt sticks, and (clean) a green-wood
    spit on two forked sticks."""
    r = ctx.rnd("firepit")
    n = 15
    for k in range(n):
        a = math.tau * k / n + r.uniform(-0.08, 0.08)
        O.add_stone(ctx, f"stone{k}", (math.cos(a) * 0.55, math.sin(a) * 0.55, 0.05), r.uniform(0.16, 0.24),
                    ctx.seed + k, flat=0.55)
    ash = K.blob("ash", 0.45, subdiv=2, scale=(1.0, 1.0, 0.07), center=(0, 0, 0.0), rough=0.3, seed=ctx.seed)
    ctx.add(ash, "ash_burnt", uv="box", uv_scale=1.5, smooth=60, patches=0.2)
    for k in range(7):
        c = K.chunk(f"coal{k}", r.uniform(0.05, 0.1), r, n=9, flat=0.6)
        K.place(c, (r.uniform(-0.3, 0.3), r.uniform(-0.3, 0.3), 0.04))
        ctx.add(c, "wood_charred", uv="box", uv_scale=2.0)
    for k in range(3):
        lg = W.log_obj(f"stick{k}", r.uniform(0.45, 0.7), 0.035, ctx.seed + 10 + k, sides=6, rings=3, bark="out_bark_ash",
                       end="wood_charred")
        K.place(lg, (r.uniform(-0.1, 0.1), r.uniform(-0.1, 0.1), 0.08), (r.uniform(-10, 10), r.uniform(-12, 12),
                                                                          r.uniform(0, 180)))
        ctx.add(lg, None, uv=None, smooth=40, patches=0.4)
    if ctx.clean:
        for sx in (-1, 1):
            a = Vector((sx * 0.62, 0, -0.03))
            b = Vector((sx * 0.6, 0.0, 0.78))
            W.pole(ctx, f"fork{sx}", [a, b], 0.022, "out_bark_ash", r_end=0.016, seed=sx)
            W.pole(ctx, f"forkb{sx}", [b - Vector((0, 0, 0.12)), b + Vector((sx * 0.08, 0.0, 0.1))], 0.016, "out_bark_ash",
                   r_end=0.01, seed=sx + 3)
        W.pole(ctx, "spit", [(-0.72, 0, 0.76), (0, 0.01, 0.75), (0.72, 0, 0.77)], 0.014, "out_log_peeled", r_end=0.012,
               seed=9)


def out_hide_bed(ctx: K.Ctx) -> None:
    """Spruce boughs under a smoked hide, a fur at the foot and a rolled hide for a pillow (-Y is
    the foot, +Y the head)."""
    r = ctx.rnd("hidebed")
    mat = K.box("boughs", (0.86, 1.95, 0.1), center=(0, 0, 0.05), cuts=(4, 8, 1))
    K.noise_disp(mat, 0.025, scale=5.0, seed=ctx.seed)
    K.map_verts(mat, lambda co: Vector((co.x, co.y, max(0.0, co.z * (1.0 - 0.6 * (abs(co.x) / 0.43) ** 3)))))
    ctx.add(mat, "out_boughs", uv="box", uv_scale=2.0, smooth=50, patches=0.3)
    sheet = K.grid("hide", 0.82, 1.82, 10, 16)
    K.uv_planar(sheet, 2, scale=1.0)

    def drape(co):
        ax = abs(co.x)
        z = 0.115 if ax < 0.36 else 0.115 - (ax - 0.36) * 1.6
        return Vector((co.x, co.y, max(0.01, z)))
    K.map_verts(sheet, drape)
    K.crumple(sheet, 0.012, scale=5.0, seed=ctx.seed + 1)
    K.solidify(sheet, 0.008, offset=-1.0, even=False)
    ctx.add(sheet, "out_hide", uv=None, smooth=50, patches=0.5 if ctx.worn else 0.3)
    fur = K.grid("fur", 0.74, 0.7, 8, 8)
    K.uv_planar(fur, 2, scale=1.0)
    K.map_verts(fur, lambda co: Vector((co.x, co.y - 0.55, 0.14 + 0.02 * math.sin(co.x * 9) - max(0, abs(co.x) - 0.33) * 1.2)))
    K.crumple(fur, 0.015, scale=5.0, seed=ctx.seed + 2)
    K.solidify(fur, 0.03, offset=-1.0, even=False)
    ctx.add(fur, "wild_fur_brown", uv=None, smooth=55, patches=0.3)
    pillow = K.cyl("pillow", 0.075, 0.5, segs=10, center=(0, 0.78, 0.17), axis="X")
    K.noise_disp(pillow, 0.008, scale=8.0, seed=3)
    ctx.add(pillow, "out_hide", uv="cyl", uv_axis=0, smooth=55, patches=0.3)
    _ = r


def out_ashen_cache(ctx: K.Ctx) -> None:
    """A steel ammunition locker (olive paint, pressed ribs, lid seam, end handles, a hasp and
    padlock on the front) wrapped in two hide straps and ash-painted; an antler tine tied on top."""
    W_, D_, H_ = 0.92, 0.48, 0.5
    body = K.box("body", (W_, D_, H_ * 0.82), center=(0, 0, H_ * 0.41 + 0.03), bevel=0.012, bevel_segs=2)
    ctx.add(body, "out_ammo_green", uv="box", uv_scale=2.0, smooth=35, edge=1.4, patches=0.6,
            extra=lambda co, n: 0.35 if (abs(n.y) > 0.8 and abs(co.x) < 0.15 and 0.15 < co.z < 0.35) else 0.0)
    lid = K.box("lid", (W_ + 0.02, D_ + 0.02, H_ * 0.18), center=(0, 0, H_ * 0.82 + 0.03 + H_ * 0.09), bevel=0.014,
                bevel_segs=2)
    ctx.add(lid, "out_ammo_green", uv="box", uv_scale=2.0, smooth=35, edge=1.4, patches=0.6)
    for k, x in enumerate((-0.3, -0.1, 0.1, 0.3)):
        for sy in (-1, 1):
            rib = K.box(f"rib{k}{sy}", (0.035, 0.012, H_ * 0.6), center=(x, sy * (D_ / 2 + 0.004), H_ * 0.4), bevel=0.004)
            ctx.add(rib, "out_ammo_green", uv="box", uv_scale=2.0, edge=1.5, patches=0.6)
    for sx in (-1, 1):
        h = K.tube(f"handle{sx}", [(sx * (W_ / 2 + 0.01), -0.08, 0.3), (sx * (W_ / 2 + 0.05), -0.06, 0.28),
                                   (sx * (W_ / 2 + 0.05), 0.06, 0.28), (sx * (W_ / 2 + 0.01), 0.08, 0.3)], 0.007, segs=5)
        ctx.add(h, "trap_steel", uv="box", uv_scale=3.0, smooth=40, edge=1.2)
    hasp = K.box("hasp", (0.05, 0.012, 0.11), center=(0, -D_ / 2 - 0.012, 0.42), bevel=0.003)
    ctx.add(hasp, "trap_steel", uv="box", uv_scale=3.0, edge=1.2)
    lock = K.box("lock", (0.05, 0.022, 0.055), center=(0, -D_ / 2 - 0.03, 0.34), bevel=0.006, bevel_segs=2)
    ctx.add(lock, "lock_steel", uv="box", uv_scale=3.0, smooth=35, edge=1.4)
    shackle = K.tube("shackle", [(-0.015, -D_ / 2 - 0.03, 0.365), (-0.015, -D_ / 2 - 0.03, 0.4), (0.015, -D_ / 2 - 0.03, 0.4),
                                 (0.015, -D_ / 2 - 0.03, 0.365)], 0.004, segs=5)
    ctx.add(shackle, "lock_steel", uv="box", uv_scale=3.0, smooth=40)
    # Two hide straps hugging the box: a rounded rectangle round its cross-section (y, z).
    hy, z0, z1, rc = D_ / 2 + 0.008, 0.035, H_ + 0.012, 0.025
    corners = [(hy - rc, z1 - rc, 0.0), (-hy + rc, z1 - rc, 90.0), (-hy + rc, z0 + rc, 180.0), (hy - rc, z0 + rc, 270.0)]
    loop = []
    for cy, cz, a0 in corners:
        for i in range(4):
            a = math.radians(a0 + 90.0 * i / 3)
            loop.append((cy + math.cos(a) * rc, cz + math.sin(a) * rc))
    for k, x in enumerate((-0.28, 0.3)):
        pts = [Vector((x, py, pz)) for py, pz in loop]
        strap = K.sweep(f"strap{k}", pts + [pts[0]], [(-0.035, -0.003), (0.035, -0.003), (0.035, 0.003), (-0.035, 0.003)],
                        up=(1, 0, 0), caps=False)
        ctx.add(strap, "out_hide", uv="box", uv_scale=3.0, smooth=45, patches=0.4)
    tine = K.tube("tine", [(-0.2, 0.05, H_ + 0.06), (0.05, 0.08, H_ + 0.07), (0.25, 0.02, H_ + 0.1)], [0.018, 0.013, 0.004],
                  segs=6)
    ctx.add(tine, "out_antler", uv="box", uv_scale=3.0, smooth=50)
    ctx.col_box((-W_ / 2, -D_ / 2, 0), (W_ / 2, D_ / 2, H_ + 0.06))


def out_ashen_bundle(ctx: K.Ctx) -> None:
    """A rolled hide bundle tied with sinew, a bone toggle on the knot, ash-smeared."""
    r = ctx.rnd("bundle")
    prof = [(0.0, -0.34), (0.1, -0.33), (0.145, -0.25), (0.155, 0.0), (0.145, 0.25), (0.1, 0.33), (0.0, 0.34)]
    o = K.lathe("roll", prof, segs=14)
    K.map_verts(o, lambda co: Vector((co.x * (1.0 + 0.05 * math.sin(co.z * 20 + math.atan2(co.y, co.x) * 2)), co.y * 0.82, co.z)))
    K.noise_disp(o, 0.008, scale=8.0, seed=ctx.seed)
    K.place(o, rot=(0, 90, 0))
    K.place(o, (0, 0, 0.13))
    ctx.add(o, "out_hide_ash" if ctx.worn else "out_hide", uv="box", uv_scale=2.0, smooth=55, patches=0.5)
    for k, x in enumerate((-0.17, 0.17)):
        ring = [Vector((x, math.cos(a) * 0.132, 0.13 + math.sin(a) * 0.11)) for a in [math.tau * i / 10 for i in range(10)]]
        cord = K.tube(f"tie{k}", ring, 0.006, segs=4, closed=True)
        ctx.add(cord, "out_sinew", uv="box", uv_scale=4.0, smooth=40)
    tog = O.long_bone_obj("toggle", 0.09, 0.008, ctx.seed + 2)
    K.place(tog, (0.17, -0.13, 0.17), (0, 0, 80))
    ctx.add(tog, "out_bone", uv="box", uv_scale=6.0, smooth=50)
    _ = r
    ctx.col_box((-0.35, -0.15, 0), (0.35, 0.15, 0.25))


# ============================================================================================
# Shells over the kit rooms
# ============================================================================================

def _pole_wall(ctx, room, side, openings, *, r=0.15, pitch=0.24, top=3.13, top2=None, seed=0, mat="out_log_peeled",
               sharpen=False, soot=0.0, corner_ext=0.0):
    """Vertical poles centred on a side's edge line (they enclose the kit wall inside and out), cut
    around the side's openings (jambs left as hewn posts). top2: height at the side's far end (a
    sloping wall under a lean-to roof)."""
    rr = random.Random(seed)
    start, along, out = room.side_line(side, 0.0)
    L = room.length(side)
    holes = O.holes_on(side, openings, floor=room.floor)
    n = max(2, int(round((L + 2 * corner_ext) / pitch)) + 1)
    inward = -out
    for i in range(n):
        t = -corner_ext + (L + 2 * corner_ext) * i / (n - 1)
        h_top = top if top2 is None else top + (top2 - top) * (t / L)
        h_top += rr.uniform(-0.04, 0.04)
        for z0, z1 in O.clip_vertical(-0.05, h_top, t, r * 0.8, holes):
            base = start + along * t + out * rr.uniform(-0.01, 0.01)
            if sharpen and z1 >= h_top - 0.01:
                o = O.stake_obj(f"{side}pole{i}", z1 - z0, r * rr.uniform(0.9, 1.05), seed * 97 + i)
                K.place(o, (base.x, base.y, z0))
                ctx.add(o, None, uv=None, smooth=48, patches=0.45, edge=0.9, moss=0.3,
                        extra=_soot(soot, inward) if soot else None)
            else:
                o = W.rod_obj(f"{side}pole{i}_{int(z0 * 10)}", (base.x, base.y, z0), (base.x, base.y, z1),
                              r * rr.uniform(0.92, 1.05), segs=8, r2=r * 0.95)
                ctx.add(o, mat, uv="cyl", uv_axis=0, uv_scale=1.0, smooth=50, patches=0.5, edge=0.8, moss=0.25,
                        low=0.5, low_h=0.4, extra=_soot(soot, inward) if soot else None)
    # Hewn jambs and lintels round each opening, lashed rails along the wall outside.
    for (a, b, z0, z1) in holes:
        if z0 < -0.5 and z1 > 5:
            continue
        for t in (a - 0.06, b + 0.06):
            p = start + along * t
            W.bar(ctx, f"{side}jamb{t:.2f}", (p.x, p.y, max(0.0, z0) - 0.02), (p.x, p.y, min(z1 + 0.12, top - 0.05)),
                  0.13, 0.2, "out_log_peeled", up=tuple(out), bevel=0.01)
        pa, pb = start + along * (a - 0.15), start + along * (b + 0.15)
        W.bar(ctx, f"{side}lintel{a:.2f}", (pa.x, pa.y, z1 + 0.06), (pb.x, pb.y, z1 + 0.06), 0.14, 0.16, "out_log_peeled",
              up=(0, 0, 1), bevel=0.01)
        if z0 > 0.2:
            W.bar(ctx, f"{side}sill{a:.2f}", (pa.x, pa.y, z0 - 0.05), (pb.x, pb.y, z0 - 0.05), 0.14, 0.1, "out_log_peeled",
                  up=(0, 0, 1), bevel=0.01)
    for z in (0.7, 2.3):
        for s0, s1 in O.clip_spans(-corner_ext, L + corner_ext, z - 0.05, z + 0.05, holes):
            pa = start + along * s0 + out * (r + 0.05)
            pb = start + along * s1 + out * (r + 0.05)
            W.pole(ctx, f"{side}rail{z}{s0:.1f}", [pa + Vector((0, 0, z)), pb + Vector((0, 0, z + 0.02))], 0.045,
                   "out_bark_ash", r_end=0.04, seed=seed + int(z * 10))


def _log_wall(ctx, room, side, openings, *, r=0.16, pitch=0.25, z_top=3.13, seed=0, notch_ext=0.28, odd=0):
    """Horizontal logs stacked on a side's edge line (cabin fashion, saddle-notched corners: every
    other course runs past the corner), cut at the side's openings, moss chinking in the seams."""
    rr = random.Random(seed)
    start, along, out = room.side_line(side, 0.0)
    L = room.length(side)
    holes = O.holes_on(side, openings, floor=room.floor)
    k = 0
    z = r * 0.85
    while z < z_top:
        ext = notch_ext if (k + odd) % 2 == 0 else -0.02
        for s0, s1 in O.clip_spans(-ext, L + ext, z - r * 0.6, z + r * 0.6, holes):
            a = start + along * s0 + Vector((0, 0, z))
            b = start + along * s1 + Vector((0, 0, z))
            O.add_log_between(ctx, f"{side}log{k}_{s0:.1f}", a, b, r * rr.uniform(0.94, 1.04), seed * 131 + k * 7,
                              mat_bark="out_bark_ash", sides=10, rings=4, taper=0.04, moss=0.35)
            for sgn in (1, -1):
                pa, pb = a + out * sgn * (r * 0.6) + Vector((0, 0, pitch / 2)), b + out * sgn * (r * 0.6) + Vector((0, 0, pitch / 2))
                if z + pitch < z_top:
                    ch = K.tube(f"{side}chink{k}{sgn}{s0:.1f}", [pa, pb], 0.035, segs=5, caps=False)
                    ctx.add(ch, "out_chinking", uv="box", uv_scale=2.0, smooth=50, moss=0.7)
        k += 1
        z += pitch
    for (a, b, z0, z1) in holes:
        for t in (a - 0.07, b + 0.07):
            p = start + along * t
            W.bar(ctx, f"{side}jamb{t:.2f}", (p.x, p.y, max(0.0, z0)), (p.x, p.y, min(z_top - 0.1, z1 + 0.1)), 0.12, 0.36,
                  "out_log_peeled", up=tuple(out), bevel=0.012)


def _inner_ceiling(ctx, room, z_poles, z_bark, *, seed=0, holes=()):
    """Cross poles and a bark layer just under the kit ceiling slab (it sits at floor + 2.8 m)."""
    rr = random.Random(seed)
    hw, hd = room.w / 2 - 0.12, room.d / 2 - 0.12
    n = max(2, int(room.w / 0.62))
    for i in range(n):
        x = -hw + 2 * hw * i / (n - 1)
        W.pole(ctx, f"ceil_pole{i}", [(x, -hd, z_poles), (x + rr.uniform(-0.03, 0.03), 0, z_poles - 0.02), (x, hd, z_poles)],
               0.05, "out_log_smoked", r_end=0.045, seed=seed + i)
    slab = K.box("ceil_bark", (2 * hw, 2 * hd, 0.02), center=(0, 0, z_bark), cuts=(6, 4, 0))
    K.noise_disp(slab, 0.01, scale=4.0, seed=seed)
    ctx.add(slab, "out_bark_slab", uv="box", uv_scale=1.0, patches=0.4, base=0.4, ao=False)


def _floor_liner(ctx, room, z, *, skip=(), seed=0, mat="out_earth"):
    """Packed earth over the kit floor (a hair above it), with holes left over the hatch cells
    `skip` (plan-cell offsets (col, row) from the room's north-west corner)."""
    hw, hd = room.w / 2, room.d / 2
    o = K.grid("floor_liner", room.w - 0.24, room.d - 0.24, room.w * 2, room.d * 2, center=(0, 0, z))
    K.uv_planar(o, 2, scale=1.0)

    def in_skip(p, _n):
        for (c, rw) in skip:
            x0, x1 = -hw + c, -hw + c + 1
            y1, y0 = hd - rw, hd - rw - 1
            if x0 - 0.02 <= p.x <= x1 + 0.02 and y0 - 0.02 <= p.y <= y1 + 0.02:
                return True
        return False
    K.delete_faces(o, in_skip)
    K.noise_disp(o, 0.003, scale=3.0, seed=seed, along_normal=False)
    ctx.add(o, mat, uv=None, smooth=None, patches=0.5, ao=True)


def _bark_gable_roof(ctx, room, z_eave, rise, *, over=0.45, gable_over=0.35, seed=0, smoke_hole=True, sod=0.5,
                     axis="x", z_floor_ceiling=3.08):
    """A gable roof of poles, overlapping bark slabs and sod over the room (ridge along `axis`), with a
    smoke hole and its little hood near the middle of the ridge and bark-slab gable infill."""
    rr = random.Random(seed)
    if axis == "x":
        L, half = room.w / 2 + gable_over, room.d / 2 + over
    else:
        L, half = room.d / 2 + gable_over, room.w / 2 + over
    ridge_z = z_eave + rise + over * rise / (half - over)
    slope = math.atan2(ridge_z - z_eave, half)

    def P2(u, v, z):  # u along the ridge, v across
        return Vector((u, v, z)) if axis == "x" else Vector((v, u, z))
    # Ridge pole and rafters.
    W.pole(ctx, "ridge", [P2(-L - 0.1, 0, ridge_z), P2(0, 0, ridge_z + 0.02), P2(L + 0.1, 0, ridge_z)], 0.07, "out_bark_ash",
           r_end=0.06, seed=seed)
    n_raf = max(3, int(2 * L / 0.75))
    for i in range(n_raf):
        u = -L + 2 * L * i / (n_raf - 1)
        for sv in (-1, 1):
            W.pole(ctx, f"rafter{i}{sv}", [P2(u, sv * (half + 0.15), z_eave - 0.12), P2(u, 0, ridge_z + 0.04)], 0.045,
                   "out_bark_ash", r_end=0.04, seed=seed + i * 2 + sv)
    # Bark slabs in courses on both slopes.
    courses = max(3, int(half / 0.42))
    hole_u = (-0.35, 0.35) if smoke_hole else (0, 0)
    for sv in (-1, 1):
        for c in range(courses):
            t0 = c / courses
            v = sv * half * (1 - t0) - sv * half / courses / 2
            z = z_eave + (ridge_z - z_eave) * (1 - abs(v) / half) + 0.07
            m = max(4, int(2 * L / 0.5))
            for j in range(m):
                u = -L + (j + 0.5 + 0.5 * (c % 2)) * 2 * L / m
                if abs(u) > L:
                    continue
                if smoke_hole and c == courses - 1 and hole_u[0] < u < hole_u[1]:
                    continue
                sl = K.box(f"slab{sv}{c}{j}", (2 * L / m + 0.12, half / courses + 0.2, 0.03), cuts=(2, 2, 0))
                K.noise_disp(sl, 0.012, scale=5.0, seed=seed + c * 41 + j)
                K.place(sl, rot=(math.degrees(slope) * -sv + rr.uniform(-2, 2), rr.uniform(-1.5, 1.5), 0))
                if axis != "x":
                    K.place(sl, rot=(0, 0, 90))
                K.place(sl, P2(u, v, z))
                ctx.add(sl, "out_bark_slab", long_axis=1 if axis == "x" else 0, uv_scale=1.0, patches=0.5,
                        moss=0.6, edge=0.8)
            if sod > 0 and c < courses - 1:
                for j in range(max(2, int(L * 1.2))):
                    if rr.random() > sod:
                        continue
                    u = rr.uniform(-L + 0.2, L - 0.2)
                    so = K.blob(f"sod{sv}{c}{j}", rr.uniform(0.25, 0.42), subdiv=2, scale=(1.3, 0.8, 0.22), rough=0.35,
                                seed=seed + c * 7 + j)
                    K.place(so, rot=(math.degrees(slope) * -sv, 0, 0 if axis == "x" else 90))
                    K.place(so, P2(u, v, z + 0.06))
                    ctx.add(so, "out_sod", uv="box", uv_scale=1.0, smooth=55, patches=0.2, moss=0.9)
    if smoke_hole:
        for sv in (-1, 1):
            W.pole(ctx, f"hood_post{sv}", [P2(sv * 0.3, -0.25, ridge_z - 0.1), P2(sv * 0.3, -0.25, ridge_z + 0.42)], 0.03,
                   "out_bark_ash", r_end=0.025, seed=seed + 70 + sv)
        hood = K.box("hood", (0.85, 0.7, 0.03), cuts=(2, 2, 0))
        K.noise_disp(hood, 0.01, scale=5.0, seed=seed + 2)
        K.place(hood, rot=(12, 0, 0 if axis == "x" else 90))
        K.place(hood, P2(0, -0.05, ridge_z + 0.45))
        ctx.add(hood, "out_bark_slab", uv="box", uv_scale=1.0, patches=0.5, moss=0.4)
    # Gable ends: vertical bark slabs from the wall top to the roof line.
    for su in (-1, 1):
        k = 0
        v = -half + over
        while v < half - over:
            h = (ridge_z - z_eave) * (1 - abs(v) / half) + (z_eave - (z_floor_ceiling - 0.05))
            if h > 0.06:
                sl = K.box(f"gable{su}{k}", (0.03, 0.26, h), center=(0, 0, h / 2), cuts=(0, 1, 2))
                K.noise_disp(sl, 0.008, scale=6.0, seed=seed + k)
                if axis != "x":
                    K.place(sl, rot=(0, 0, 90))
                K.place(sl, P2(su * (L - gable_over + 0.17), v + 0.13, z_floor_ceiling - 0.05))
                ctx.add(sl, "out_bark_slab", uv="box", uv_scale=1.0, patches=0.5, moss=0.4)
            v += 0.27
            k += 1
    return ridge_z


def out_longhouse_shell(ctx: K.Ctx) -> None:
    """The watch camp's longhouse over its 8 x 4 m kit room (plan cols 13..20, rows 3..6): pole
    walls standing on the room's edge lines, cut for the back door (N, cell 1), the barred front
    door (S, cell 4) and the clawed-out breach (E, cell 2) with broken poles round it; a gable roof
    of poles, bark slabs and sod with a smoke hole and hood; antlers on the east gable; inside,
    soot on the poles, a ceiling of poles and bark under the kit ceiling and a packed-earth floor
    with a hole over the cache-pit hatch (cell 1, 3)."""
    fh = float(ctx.param("floor", 0.08))
    room = O.Room(8, 4, fh)
    ops = [("N", 1, "door"), ("S", 4, "door"), ("E", 2, "breach")]
    for k, side in enumerate(("N", "S", "E", "W")):
        _pole_wall(ctx, room, side, ops, top=fh + 3.05, seed=ctx.seed + k * 13, soot=0.45, corner_ext=0.0)
    r = ctx.rnd("longhouse")
    # Broken poles leaning out of the breach.
    start, along, out = room.side_line("E", 0.0)
    for k in range(3):
        p = start + along * (2.5 + r.uniform(-0.35, 0.35))
        lg = W.log_obj(f"breach_pole{k}", r.uniform(0.6, 1.4), 0.13, ctx.seed + 90 + k, sides=8, rings=3, bark="out_log_peeled")
        K.place(lg, (p.x + 0.5, p.y, 0.15 + k * 0.1), (r.uniform(-20, 20), r.uniform(-25, -5), r.uniform(-30, 30)))
        ctx.add(lg, None, uv=None, smooth=45, patches=0.5)
    _bark_gable_roof(ctx, room, fh + 3.12, 1.3, over=0.5, gable_over=0.4, seed=ctx.seed + 5, sod=0.55,
                     z_floor_ceiling=fh + 3.0)
    for side in (-1, 1):
        a = O.antler_obj(f"gable_antler{side}", 0.85, ctx.seed + 30 + side, side=side, tines=5)
        K.place(a, (4.28, side * 0.12, fh + 3.4), (0, 0, 90))
        ctx.add(a, "out_antler", uv="box", uv_scale=3.0, smooth=50, patches=0.5)
    O.add_skull(ctx, "gable_skull", (4.32, 0.0, fh + 3.35), (8, 0, 90), 0.3, ctx.seed + 33, kind="elk", antlers=False, ash=0.8)
    _inner_ceiling(ctx, room, fh + 2.7, fh + 2.785, seed=ctx.seed + 7)
    _floor_liner(ctx, room, fh + 0.006, skip=[(1, 3)], seed=ctx.seed + 8)
    # Hides hanging on the inner walls.
    for k, (x, y, rot) in enumerate(((-2.6, 1.78, 0), (1.6, 1.78, 0), (3.78, -0.6, 90))):
        h = O.hide_obj(f"wall_hide{k}", 0.8, 1.0, ctx.seed + 40 + k)
        K.place(h, (0, 0, 0), (0, 0, rot))
        K.place(h, (x, y, fh + 1.55))
        K.solidify(h, 0.006, offset=-1.0, even=False)
        ctx.add(h, "out_hide", uv=None, smooth=50, patches=0.4)


def out_smoke_hut_shell(ctx: K.Ctx) -> None:
    """A squat smoke hut of stacked, saddle-notched logs (r 0.16) over its 3 x 3 m kit room, moss
    chinking in the seams, cut for its door (W, cell 1); a low sod roof with a stone-and-bark smoke
    hole; inside, smoked poles and bark under the kit ceiling and an earth floor."""
    fh = float(ctx.param("floor", 0.08))
    room = O.Room(3, 3, fh)
    ops = [("W", 1, "door")]
    for k, side in enumerate(("N", "S", "E", "W")):
        _log_wall(ctx, room, side, ops, z_top=fh + 3.1, seed=ctx.seed + k * 7, odd=0 if side in ("N", "S") else 1)
    _bark_gable_roof(ctx, room, fh + 3.12, 0.55, over=0.4, gable_over=0.45, seed=ctx.seed + 3, sod=0.9,
                     z_floor_ceiling=fh + 3.0)
    _inner_ceiling(ctx, room, fh + 2.7, fh + 2.785, seed=ctx.seed + 4)
    _floor_liner(ctx, room, fh + 0.006, seed=ctx.seed + 5)


def out_lean_to_shell(ctx: K.Ctx) -> None:
    """A lean-to against the palisade over its 2 x 4 m kit room (plan cols 3..4, rows 13..16): the back
    wall (W) is sharpened palisade stakes, the north and south ends poles under the slope, the east
    side open; a single-slope roof of poles and bark from 3.65 m at the back to 3.2 m at the front;
    hides hung at the open corners; earth floor and a bark ceiling inside."""
    fh = float(ctx.param("floor", 0.08))
    room = O.Room(2, 4, fh)
    ops = []
    _pole_wall(ctx, room, "W", ops, top=fh + 3.35, seed=ctx.seed + 1, sharpen=True, soot=0.3)
    _pole_wall(ctx, room, "N", ops, top=fh + 3.4, top2=fh + 3.12, seed=ctx.seed + 2, soot=0.3)
    _pole_wall(ctx, room, "S", ops, top=fh + 3.4, top2=fh + 3.12, seed=ctx.seed + 3, soot=0.3)
    r = ctx.rnd("leanto")
    for sy in (-1, 1):
        W.pole(ctx, f"front_post{sy}", [(1.0, sy * 2.0, -0.05), (1.01, sy * 2.0, 1.6), (1.0, sy * 2.0, fh + 3.15)], 0.12,
               "out_bark_ash", r_end=0.1, seed=ctx.seed + 5 + sy)
    W.pole(ctx, "front_beam", [(1.0, -2.45, fh + 3.18), (1.02, 0, fh + 3.16), (1.0, 2.45, fh + 3.18)], 0.09, "out_bark_ash",
           r_end=0.08, seed=ctx.seed + 7)
    z_back, z_front = fh + 3.7, fh + 3.24
    for i in range(8):
        y = -2.3 + 4.6 * i / 7
        W.pole(ctx, f"rafter{i}", [(-1.25, y, z_back + 0.03), (1.65, y, z_front - (z_back - z_front) * 0.55 / 2.25)], 0.045,
               "out_bark_ash", r_end=0.04, seed=ctx.seed + 10 + i)
    ang = math.degrees(math.atan2(z_back - z_front, 2.25))
    for c in range(5):
        x = -1.15 + c * 0.62
        z = z_back - (x + 1.15) * (z_back - z_front) / 2.25 + 0.08
        for j in range(9):
            y = -2.4 + (j + 0.5 * (c % 2)) * 0.56
            if abs(y) > 2.45:
                continue
            sl = K.box(f"slab{c}{j}", (0.8, 0.62, 0.03), cuts=(2, 2, 0))
            K.noise_disp(sl, 0.012, scale=5.0, seed=c * 13 + j)
            K.place(sl, rot=(r.uniform(-2, 2), ang + r.uniform(-2, 2), 0))
            K.place(sl, (x, y, z))
            ctx.add(sl, "out_bark_slab", uv="box", uv_scale=1.0, patches=0.5, moss=0.55)
    for k, sy in enumerate((-1, 1)):
        h = O.hide_obj(f"door_hide{k}", 0.75, 1.7, ctx.seed + 20 + k, ragged=0.1)
        K.place(h, (0, 0, 0), (0, 0, 90))
        K.place(h, (1.12, sy * 1.62, fh + 1.95))
        K.solidify(h, 0.006, offset=-1.0, even=False)
        ctx.add(h, "out_hide", uv=None, smooth=50, patches=0.4)
    _inner_ceiling(ctx, room, fh + 2.7, fh + 2.785, seed=ctx.seed + 30)
    _floor_liner(ctx, room, fh + 0.006, seed=ctx.seed + 31)


# ============================================================================================
# The plank door leaf (models/kit/door_plank*)
# ============================================================================================

def door_plank(ctx: K.Ctx) -> None:
    """A ledged and braced plank door for the camp's doorways (the POI kit door contract: hinged on
    its left edge seen from -Y, origin at the bottom of the hinge edge, x 0..0.82, y +-0.02,
    z 0..2.05): five planks, two ledges and a brace on the back (+Y), rawhide strap hinges and a
    pull loop on the front. broken: split planks, one gone, the brace snapped."""
    ctx.ground_clamp = False
    broken = bool(ctx.param("broken", False))
    r = ctx.rnd("doorplank")
    Wd, H = 0.82, 2.05
    n = 5
    for k in range(n):
        x = (k + 0.5) * Wd / n
        if broken and k == 3:
            continue
        top = H - (r.uniform(0.25, 0.7) if broken and k in (2, 4) else 0.0)
        pl = P.plank(f"plank{k}", top - 0.01, Wd / n - 0.006, 0.032, bevel=0.004, cuts=3)
        K.place(pl, rot=(90, -90, 0))  # length up, width across the door, thickness through it
        K.place(pl, (x, -0.004, top / 2))
        if broken and top < H:
            P.break_end(pl, top - 0.08, ctx.drnd(f"b{k}"), side=1, depth=0.12, axis=2)
        ctx.add(pl, "wood_weathered", long_axis=2, uv_scale=1.0, patches=0.6, edge=1.2, moss=0.2)
    for z in (0.32, 1.72):
        W.bar(ctx, f"ledge{z}", (0.04, 0.025, z), (Wd - 0.04, 0.025, z), 0.14, 0.024, "wood_weathered", up=(0, 1, 0),
              bevel=0.004)
    if not broken:
        W.bar(ctx, "brace", (0.1, 0.025, 0.42), (Wd - 0.1, 0.025, 1.62), 0.12, 0.022, "wood_weathered", up=(0, 1, 0),
              bevel=0.004)
    for z in (0.32, 1.72):
        strap = K.box(f"strap{z}", (0.42, 0.006, 0.05), center=(0.2, -0.023, z), bevel=0.002)
        ctx.add(strap, "out_rawhide", uv="box", uv_scale=4.0, patches=0.4)
    loop = K.tube("pull", [(0.7, -0.022, 1.06), (0.71, -0.06, 1.0), (0.7, -0.022, 0.94)], 0.006, segs=5)
    ctx.add(loop, "out_rawhide", uv="box", uv_scale=4.0, smooth=40)


BUILDERS = {
    "out_palisade": out_palisade,
    "out_palisade_half": out_palisade_half,
    "out_palisade_gate": out_palisade_gate,
    "out_palisade_breach": out_palisade_breach,
    "out_effigy": out_effigy,
    "out_bone_totem": out_bone_totem,
    "out_bone_chime": out_bone_chime,
    "out_burial_platform": out_burial_platform,
    "out_pit_hut": out_pit_hut,
    "out_pyre": out_pyre,
    "out_hide_frame": out_hide_frame,
    "out_antler_pile": out_antler_pile,
    "out_stone_fire_pit": out_stone_fire_pit,
    "out_hide_bed": out_hide_bed,
    "out_ashen_cache": out_ashen_cache,
    "out_ashen_bundle": out_ashen_bundle,
    "out_longhouse_shell": out_longhouse_shell,
    "out_smoke_hut_shell": out_smoke_hut_shell,
    "out_lean_to_shell": out_lean_to_shell,
    "door_plank": door_plank,
}


def build(params: dict, outputs: list[str]) -> None:
    K.run(params, outputs, BUILDERS)
