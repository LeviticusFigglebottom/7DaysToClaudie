"""Living Ashen camp props (ADR-0048, the Ashen highcamp): the war drum, a spear rack, the clay pots
of lichen-ash the Ashen smear on themselves, a drying rack of meat strips and hides, and a fed camp
fire. The watch camp's kit (palisade, longhouse, pyre, effigies...) is props_outskirts_ashen.py; these
sit beside it and use its materials (out_*), plus a few of their own (ashen_*,
game/data/materials/props_ashen_camp.json).

Unlike the watch camp's things these are in use: 'clean' is the camp as its people keep it (the
drum taut, the racks full, the fire fed), 'worn' a season on (a slack head, spears gone, a fire
burning low).

Conventions (docs/ASSET_PIPELINE.md): metres, Z up, front -Y, origin bottom centre. The camp fire's
embers and log ends are `ember_glow` (light_source: they glow only while PropLights burns the prop;
its def adds the flames).
"""
from __future__ import annotations

import math
import random

from mathutils import Matrix, Vector

from lib import props_ext_kit as K
from lib import props_outskirts_parts as O
from lib import props_wild_parts as W


def _tilt(v: Vector, deg_x: float) -> Vector:
    """Rotates a point about the X axis (degrees)."""
    return Matrix.Rotation(math.radians(deg_x), 3, "X") @ v


# ============================================================================================
# War drum
# ============================================================================================

def ashen_war_drum(ctx: K.Ctx) -> None:
    """A big drum hollowed from a log section, a rawhide head laced to a second skin underneath with
    sinew zig-zagging down its sides, ash-painted rings; it sits tilted towards the player (-Y) in a
    cradle of two crossed-pole frames lashed with rawhide, an elk skull and antlers on the frame
    behind it, two bone-knobbed beaters leaning on it. Worn: the head slack and split, one beater
    gone."""
    r = ctx.rnd("drum")
    R, L = 0.36, 0.56
    tilt = -24.0                      # top head leans towards -Y
    centre = Vector((0.0, 0.0, 0.72))
    axis = _tilt(Vector((0, 0, 1)), tilt)
    # The shell: a bark-on log section along X, stood up along the drum axis.
    shell = W.log_obj("shell", L, R, ctx.seed, sides=18, rings=4, taper=0.0, bow=0.0, bark="out_bark_ash",
                      end="out_log_smoked", knots=0)
    K.orient(shell, axis, _tilt(Vector((0, -1, 0)), tilt), centre)
    ctx.add(shell, None, uv=None, smooth=50, patches=0.4, edge=0.6)
    # Painted bands round the shell: thin hide straps (ash paint stands in as pale rawhide).
    for k, t in enumerate((-0.18, 0.18)):
        ring = [centre + axis * t + _tilt(Vector((math.cos(a) * (R + 0.012), math.sin(a) * (R + 0.012), 0)), tilt)
                for a in [math.tau * i / 20 for i in range(20)]]
        band = K.tube(f"band{k}", ring, 0.009, segs=4, closed=True)
        ctx.add(band, "out_rawhide", uv="box", uv_scale=4.0, smooth=40, patches=0.3)
    # The heads: rawhide discs a little proud of both ends, the top one with a turned rim.
    for k, sgn in enumerate((1, -1)):
        head = K.cyl(f"head{k}", R + 0.022, 0.016, segs=24, bevel=0.006)
        if not ctx.clean and sgn > 0:
            K.jagged_hole(head, (0.08, -0.05, 0.0), 0.09, ctx.seed + 3, axis=2, jag=0.5)
            K.map_verts(head, lambda co: Vector((co.x, co.y, co.z - 0.018 * max(0.0, 1 - (co.x ** 2 + co.y ** 2) / R ** 2))))
        K.orient(head, _tilt(Vector((1, 0, 0)), tilt), axis, centre + axis * sgn * (L / 2 + 0.004))
        ctx.add(head, "ashen_drum_hide", uv="planar", uv_axis=2, uv_scale=1.6, smooth=45, patches=0.35)
    # Lacing: sinew zig-zag between the two heads' rims.
    n = 14
    pts = []
    for i in range(n * 2 + 1):
        a = math.tau * i / (n * 2)
        z = L / 2 - 0.01 if i % 2 == 0 else -L / 2 + 0.01
        pts.append(centre + axis * z + _tilt(Vector((math.cos(a) * (R + 0.016), math.sin(a) * (R + 0.016), 0)), tilt))
    lace = K.tube("lace", pts, 0.0045, segs=4)
    ctx.add(lace, "out_sinew", uv="box", uv_scale=4.0, smooth=35)
    # The cradle: two X frames of poles either side (in the YZ plane), lashed where they cross and
    # joined by a rail under the drum.
    for sx in (-1, 1):
        x = sx * (R + 0.16)
        a0, a1 = Vector((x, -0.42, -0.03)), Vector((x, 0.36, 1.12))
        b0, b1 = Vector((x, 0.42, -0.03)), Vector((x, -0.3, 1.0))
        W.pole(ctx, f"leg_a{sx}", [a0, a0.lerp(a1, 0.5), a1], 0.042, "out_bark_ash", r_end=0.032, seed=ctx.seed + 10 + sx,
               wobble=0.012)
        W.pole(ctx, f"leg_b{sx}", [b0, b0.lerp(b1, 0.5), b1], 0.04, "out_bark_ash", r_end=0.03, seed=ctx.seed + 20 + sx,
               wobble=0.012)
        O.lash(ctx, f"cross_lash{sx}", (x, 0.0, 0.52), (1, 0, 0), 0.045, turns=3, width=0.07, seed=ctx.seed + sx)
    for k, (y, z) in enumerate(((-0.25, 0.32), (0.27, 0.36))):
        W.pole(ctx, f"rail{k}", [(-(R + 0.26), y, z), (0.0, y + 0.01, z + 0.01), (R + 0.26, y, z)], 0.035, "out_log_peeled",
               r_end=0.03, seed=ctx.seed + 30 + k)
    # A rawhide sling under the drum from rail to rail.
    sling = [Vector((sx * 0.12, y, z)) for sx in (-1, 1) for (y, z) in ((-0.25, 0.36), (0.0, 0.42), (0.27, 0.4))]
    for k in range(2):
        s = sling[k * 3:(k + 1) * 3]
        o = K.tube(f"sling{k}", s, 0.012, segs=4, flat=(1.0, 0.35))
        ctx.add(o, "out_rawhide", uv="box", uv_scale=3.0, smooth=40)
    # The skull on a stake behind (+Y), facing the player over the drum.
    W.pole(ctx, "skull_post", [(0.0, 0.5, -0.03), (0.01, 0.52, 0.7), (0.0, 0.53, 1.36)], 0.035, "out_bark_ash",
           r_end=0.028, seed=ctx.seed + 40)
    O.add_skull(ctx, "skull", (0.0, 0.53, 1.42), (-8, 0, 0), 0.3, ctx.seed + 41, kind="elk", tines=5, ash=0.6,
                broken_tine=not ctx.clean)
    O.bone_string(ctx, "charms", Vector((0.0, 0.46, 1.32)), 0.32, ctx.seed + 42, n=4)
    # Beaters: a stick with a hide-wrapped knob, leaning against the frame.
    for k in range(2 if ctx.clean else 1):
        sx = -1 if k == 0 else 1
        base = Vector((sx * 0.62, -0.18 - 0.08 * k, 0.0))
        top = Vector((sx * (R + 0.2), -0.12, 0.62))
        W.pole(ctx, f"beater{k}", [base, top], 0.016, "out_log_peeled", r_end=0.014, seed=ctx.seed + 50 + k)
        knob = K.blob(f"knob{k}", 0.045, subdiv=2, scale=(1.0, 1.0, 1.25), rough=0.1, seed=ctx.seed + k,
                      center=tuple(top + (top - base).normalized() * 0.03))
        ctx.add(knob, "out_hide", uv="box", uv_scale=4.0, smooth=55)
    _ = r
    ctx.col_box((-0.68, -0.5, 0), (0.68, 0.5, 1.2))


# ============================================================================================
# Spear rack
# ============================================================================================

def _spear(ctx, name, base: Vector, top: Vector, seed: int, *, head: str = "flint") -> None:
    """A fire-hardened ash shaft with a knapped flint (or bone) head bound on with sinew, a grip
    wrap of rawhide below the balance point."""
    d = (top - base).normalized()
    L = (top - base).length
    W.pole(ctx, f"{name}_shaft", [base, base.lerp(top, 0.5), top], 0.017, "out_log_peeled", r_end=0.012, seed=seed)
    # The head: a leaf-shaped blade (flattened double cone) beyond the top.
    prof = [(0.0, 0.0), (0.012, 0.01), (0.028, 0.06), (0.024, 0.11), (0.0, 0.17)]
    o = K.lathe(f"{name}_head", prof, segs=6)
    K.map_verts(o, lambda co: Vector((co.x, co.y * 0.32, co.z)))
    K.noise_disp(o, 0.0015, scale=40.0, seed=seed)
    K.place(o, rot=(0, 90, 0))       # the lathe runs along Z; orient() wants the part along X
    K.orient(o, d, W.up_for(d), top - d * 0.03)
    ctx.add(o, "ashen_flint" if head == "flint" else "out_bone", uv="box", uv_scale=6.0, smooth=25, patches=0.2)
    O.lash(ctx, f"{name}_bind", top - d * 0.02, d, 0.014, turns=3, width=0.05, mat="out_sinew", seed=seed)
    O.lash(ctx, f"{name}_grip", base + d * L * 0.55, d, 0.017, turns=4, width=0.16, mat="out_rawhide", seed=seed + 1)


def ashen_spear_rack(ctx: K.Ctx) -> None:
    """Two forked uprights in stone cairns carrying a lashed crossbar; spears lean against it from
    the front (-Y), heads up, a few with bone points; a hide quiver of throwing sticks hangs off one
    post. Worn: half the spears gone, one fallen across the cairn."""
    r = ctx.rnd("rack")
    for k, sx in enumerate((-1, 1)):
        x = sx * 0.92
        W.pole(ctx, f"post{k}", [(x, 0.05, -0.05), (x + 0.01, 0.06, 0.9), (x, 0.05, 1.62)], 0.055, "out_bark_ash",
               r_end=0.045, seed=ctx.seed + k, wobble=0.01)
        W.pole(ctx, f"fork{k}", [(x, 0.05, 1.45), (x - sx * 0.12, 0.06, 1.72)], 0.03, "out_bark_ash", r_end=0.022,
               seed=ctx.seed + 4 + k)
        for j in range(5):
            a = math.tau * j / 5 + r.uniform(-0.2, 0.2)
            O.add_stone(ctx, f"cairn{k}{j}", (x + math.cos(a) * 0.17, 0.05 + math.sin(a) * 0.17, 0.05), r.uniform(0.13, 0.18),
                        ctx.seed + 10 * k + j, flat=0.6)
    bar = W.pole(ctx, "crossbar", [(-1.08, 0.06, 1.55), (0.0, 0.05, 1.53), (1.08, 0.06, 1.56)], 0.04, "out_log_peeled",
                 r_end=0.036, seed=ctx.seed + 9)
    del bar
    for k, sx in enumerate((-1, 1)):
        O.lash(ctx, f"bar_lash{k}", (sx * 0.92, 0.06, 1.55), (1, 0, 0), 0.04, turns=3, width=0.06, seed=ctx.seed + 20 + k)
    n = 7
    keep = range(n) if ctx.clean else [0, 2, 5]
    for i in keep:
        x = -0.72 + i * 1.44 / (n - 1) + r.uniform(-0.04, 0.04)
        base = Vector((x + r.uniform(-0.05, 0.05), -0.42 + r.uniform(-0.05, 0.05), 0.0))
        top = Vector((x + r.uniform(-0.06, 0.06), 0.15, 2.05 + r.uniform(-0.12, 0.08)))
        _spear(ctx, f"spear{i}", base, top, ctx.seed + 100 + i, head="bone" if i % 3 == 1 else "flint")
    if not ctx.clean:
        _spear(ctx, "fallen", Vector((-1.1, -0.55, 0.05)), Vector((0.75, -0.3, 0.12)), ctx.seed + 200)
    # A hide quiver of short throwing sticks on the right post.
    q = K.cyl("quiver", 0.07, 0.55, segs=10, r_top=0.085, center=(0.0, 0.0, 0.0))
    K.noise_disp(q, 0.008, scale=6.0, seed=ctx.seed + 30)
    K.place(q, (0.0, 0.0, 0.0), (0, 8, 0))
    K.place(q, (1.04, 0.02, 0.98))
    ctx.add(q, "out_hide_ash", uv="cyl", uv_axis=2, uv_scale=2.0, smooth=50, patches=0.4)
    for j in range(4):
        a = math.tau * j / 4
        p0 = Vector((1.04 + math.cos(a) * 0.035, 0.02 + math.sin(a) * 0.035, 1.0))
        W.pole(ctx, f"dart{j}", [p0, p0 + Vector((0.06 + 0.02 * j, 0.0, 0.42))], 0.01, "out_log_peeled", r_end=0.008,
               seed=ctx.seed + 40 + j)
    O.lash(ctx, "quiver_tie", (1.0, 0.04, 1.2), (0, 0, 1), 0.06, turns=2, width=0.03, seed=ctx.seed + 31)
    ctx.col_box((-1.12, -0.5, 0), (1.12, 0.3, 2.1))


# ============================================================================================
# Ash pots
# ============================================================================================

def _pot(ctx, name, at, h, rb, seed, *, ash: bool = True, cracked: bool = False, cover: bool = False, rot=0.0) -> None:
    """A coil-built clay pot: round belly, narrow neck and a rolled lip, open (the profile turns over
    the lip and down inside to the fill level); grey-green lichen-ash mounded in it."""
    rr = random.Random(seed)
    neck = rb * rr.uniform(0.62, 0.75)
    fill = h * 0.8
    prof = [(0.0, 0.0), (rb * 0.55, 0.0), (rb * 0.92, h * 0.16), (rb, h * 0.42), (rb * 0.9, h * 0.68),
            (neck, h * 0.86), (neck * 1.08, h * 0.97), (neck * 1.1, h), (neck * 0.94, h), (neck * 0.9, h * 0.94),
            (neck * 0.86, fill), (0.0, fill - 0.004)]
    o = K.lathe(f"{name}", prof, segs=16)
    K.noise_disp(o, 0.004, scale=9.0, seed=seed)
    if cracked:
        K.cut_plane(o, (0, 0, h * 0.55), Vector((0.5, 0.2, 1.0)).normalized(), keep="below", fill=False)
    K.place(o, at, (0, 0, rot))
    ctx.add(o, "ashen_clay", uv="cyl", uv_axis=2, uv_scale=3.0, smooth=55, patches=0.5, low=0.4, low_h=0.12)
    if ash and not cracked:
        mound = K.blob(f"{name}_ash", neck * 0.92, subdiv=2, scale=(1.0, 1.0, 0.35), rough=0.25, seed=seed + 1,
                       center=(0, 0, fill))
        K.place(mound, at, (0, 0, rot))
        ctx.add(mound, "ashen_lichen_ash", uv="box", uv_scale=3.0, smooth=60, patches=0.2)
    if cover:
        lid = K.blob(f"{name}_cover", neck * 1.5, subdiv=2, scale=(1.0, 1.0, 0.18), rough=0.15, seed=seed + 2,
                     center=(0, 0, h + 0.008))
        K.map_verts(lid, lambda co: Vector((co.x, co.y, max(h - 0.06, co.z - 0.25 * max(0.0, (co.x ** 2 + co.y ** 2) ** 0.5 - neck)))))
        K.place(lid, at, (0, 0, rot))
        ctx.add(lid, "out_hide", uv="box", uv_scale=3.0, smooth=50, patches=0.4)
        tie = K.tube(f"{name}_tie", [Vector((math.cos(a) * neck * 1.06, math.sin(a) * neck * 1.06, h * 0.9))
                                     for a in [math.tau * i / 12 for i in range(12)]], 0.004, segs=4, closed=True)
        K.place(tie, at, (0, 0, rot))
        ctx.add(tie, "out_sinew", uv="box", uv_scale=4.0, smooth=40)


def ashen_ash_pots(ctx: K.Ctx) -> None:
    """Clay pots of lichen-ash by a flat grinding stone: a big storage jar with a hide cover tied
    over its mouth, three smaller open pots of grey-green ash, a wooden scoop in one, ash smeared and
    spilled round them and handprints of it on the stone. Worn: one pot cracked open, its ash spilt."""
    r = ctx.rnd("pots")
    _pot(ctx, "jar", (-0.22, 0.12, 0.0), 0.62, 0.21, ctx.seed + 1, ash=False, cover=True, rot=20)
    _pot(ctx, "pot_a", (0.2, 0.16, 0.0), 0.36, 0.15, ctx.seed + 2, rot=70)
    _pot(ctx, "pot_b", (0.05, -0.2, 0.0), 0.28, 0.12, ctx.seed + 3, rot=10)
    _pot(ctx, "pot_c", (0.42, -0.12, 0.0), 0.24, 0.11, ctx.seed + 4, cracked=not ctx.clean, rot=-40)
    # The grinding stone, ash ground into its hollow.
    O.add_stone(ctx, "quern", (-0.3, -0.25, 0.03), 0.36, ctx.seed + 5, flat=0.35)
    smear = K.blob("smear", 0.11, subdiv=2, scale=(1.3, 1.0, 0.12), rough=0.3, seed=ctx.seed + 6, center=(-0.3, -0.25, 0.085))
    ctx.add(smear, "ashen_lichen_ash", uv="box", uv_scale=3.0, smooth=60)
    O.add_stone(ctx, "muller", (-0.12, -0.36, 0.03), 0.1, ctx.seed + 7, flat=0.7)
    # Spilled ash round the foot.
    spill = K.blob("spill", 0.32, subdiv=3, scale=(1.6, 1.0, 0.03), rough=0.4, seed=ctx.seed + 8,
                   center=(0.15 if ctx.clean else 0.42, -0.1, 0.0))
    K.cut_plane(spill, (0, 0, 0.001), (0, 0, -1), keep="below", fill=False)
    ctx.add(spill, "ashen_lichen_ash", uv="box", uv_scale=2.0, smooth=60, patches=0.1)
    # A wooden scoop standing in pot_a.
    W.pole(ctx, "scoop", [(0.2, 0.16, 0.22), (0.24, 0.2, 0.52)], 0.009, "out_log_peeled", r_end=0.008, seed=ctx.seed + 9)
    bowl = K.blob("scoop_bowl", 0.035, subdiv=2, scale=(1.0, 0.8, 0.45), seed=ctx.seed + 10, center=(0.195, 0.155, 0.235))
    ctx.add(bowl, "out_log_peeled", uv="box", uv_scale=4.0, smooth=55)
    _ = r
    ctx.col_box((-0.55, -0.48, 0), (0.58, 0.4, 0.66))


# ============================================================================================
# Drying rack
# ============================================================================================

def ashen_drying_rack(ctx: K.Ctx) -> None:
    """Two A-frames of poles carrying a ridge pole and a lower rail: strips of meat hang from the
    ridge on sinew, darkening as they dry; a scraped hide is thrown over the lower rail and a second
    stretched on a hoop leaning on the end. Worn: a few strips left, the hide torn and fallen half off."""
    r = ctx.rnd("rack")
    for k, sx in enumerate((-1, 1)):
        x = sx * 1.12
        for sy in (-1, 1):
            W.pole(ctx, f"a{k}{sy}", [(x, sy * 0.48, -0.04), (x, sy * 0.24, 0.9), (x, -sy * 0.02, 1.86)], 0.04,
                   "out_bark_ash", r_end=0.03, seed=ctx.seed + k * 3 + sy, wobble=0.01)
        O.lash(ctx, f"apex{k}", (x, 0.0, 1.74), (1, 0, 0), 0.05, turns=3, width=0.06, seed=ctx.seed + 10 + k)
    W.pole(ctx, "ridge", [(-1.3, 0.0, 1.76), (0.0, 0.01, 1.73), (1.3, 0.0, 1.76)], 0.035, "out_log_peeled", r_end=0.032,
           seed=ctx.seed + 20)
    W.pole(ctx, "rail", [(-1.22, -0.22, 0.95), (0.0, -0.22, 0.93), (1.22, -0.22, 0.95)], 0.03, "out_log_peeled",
           r_end=0.028, seed=ctx.seed + 21)
    n = 14 if ctx.clean else 5
    for i in range(n):
        x = -0.95 + 1.9 * (i + 0.5) / n + r.uniform(-0.03, 0.03)
        L = r.uniform(0.32, 0.55)
        w = r.uniform(0.045, 0.075)
        top = Vector((x, r.uniform(-0.02, 0.02), 1.7))
        cord = K.tube(f"cord{i}", [top + Vector((0, 0, 0.04)), top], 0.0035, segs=4)
        ctx.add(cord, "out_sinew", uv="box", uv_scale=4.0, smooth=40)
        strip = K.box(f"strip{i}", (w, 0.012, L), center=(0, 0, -L / 2), cuts=(1, 0, 4))
        K.map_verts(strip, lambda co, rr=r.uniform(-1, 1): Vector((co.x + 0.02 * math.sin(co.z * 9 + rr) - co.x * 0.4 * (-co.z / L),
                                                                    co.y + 0.012 * math.sin(co.z * 7 + rr * 2), co.z)))
        K.crumple(strip, 0.004, scale=12.0, seed=ctx.seed + 30 + i)
        K.place(strip, top, (r.uniform(-4, 4), 0, r.uniform(-30, 30)))
        ctx.add(strip, "ashen_meat_dried", uv="box", uv_scale=4.0, smooth=45, patches=0.3)
    # The hide over the rail (draped both sides).
    hide = O.hide_obj("hide", 1.05, 1.2, ctx.seed + 40, ragged=0.08)
    K.place(hide, rot=(-90, 0, 0))   # flat in XY
    K.map_verts(hide, lambda co: Vector((co.x, -0.22 + math.sin(max(-1.4, min(1.4, co.y / 0.42))) * 0.2,
                                         0.95 - 0.55 * (1 - math.cos(max(-1.4, min(1.4, co.y / 0.42)))) - 0.12 * abs(co.y))))
    K.place(hide, (-0.35, 0.0, 0.0) if ctx.clean else (0.75, -0.05, -0.12), None if ctx.clean else (0, 18, 0))
    K.solidify(hide, 0.006, offset=-1.0, even=False)
    ctx.add(hide, "out_hide_ash", uv=None, smooth=50, patches=0.5)
    # A hide stretched on a sapling hoop, leaning on the right A-frame.
    c = Vector((1.38, -0.15, 0.62))
    hoop_pts = [c + Matrix.Rotation(math.radians(-14), 3, "Y") @ Vector((0.0, math.cos(a) * 0.5, math.sin(a) * 0.58))
                for a in [math.tau * i / 16 for i in range(16)]]
    hoop = K.tube("hoop", hoop_pts, 0.016, segs=5, closed=True)
    ctx.add(hoop, "out_bark_ash", uv="box", uv_scale=3.0, smooth=50)
    sheet = O.hide_obj("hoop_hide", 0.92, 1.05, ctx.seed + 41, ragged=0.04)
    K.place(sheet, rot=(0, 0, 90))
    K.place(sheet, (0, 0, 0), (0, -14, 0))
    K.place(sheet, c)
    K.solidify(sheet, 0.005, offset=-1.0, even=False)
    ctx.add(sheet, "out_rawhide", uv=None, smooth=50, patches=0.4)
    ctx.col_box((-1.3, -0.55, 0), (1.55, 0.55, 1.85))


# ============================================================================================
# Camp fire (lit)
# ============================================================================================

def ashen_camp_fire(ctx: K.Ctx) -> None:
    """A fed fire: a ring of river stones round a deep bed of ash and coals, split logs stood in a
    cone over it (their feet charred and glowing), more wood stacked by the ring, a green-wood spit
    on forked sticks and a clay pot in the ashes. The coals and log ends are ember_glow: they glow
    only while the prop burns (its light and flames come from the def's light, fx "fire"). Worn:
    burning low, the cone fallen in to a heap of glowing ends."""
    r = ctx.rnd("fire")
    n = 13
    for k in range(n):
        a = math.tau * k / n + r.uniform(-0.08, 0.08)
        O.add_stone(ctx, f"stone{k}", (math.cos(a) * 0.56, math.sin(a) * 0.56, 0.05), r.uniform(0.17, 0.25), ctx.seed + k,
                    flat=0.55, mat="rock_sooted" if k % 3 else "stone_river")
    bed = K.blob("ash", 0.48, subdiv=3, scale=(1.0, 1.0, 0.11), rough=0.3, seed=ctx.seed, center=(0, 0, 0.0))
    ctx.add(bed, "ash_burnt", uv="box", uv_scale=1.5, smooth=60, patches=0.2)
    er = ctx.rnd("embers")
    for k in range(22 if ctx.clean else 12):
        a, d = er.uniform(0, math.tau), 0.32 * math.sqrt(er.random())
        z = 0.048 * math.sqrt(max(0.0, 1.0 - (d / 0.48) ** 2))
        if k % 3 == 0:
            c = K.chunk(f"coal{k}", er.uniform(0.04, 0.08), er, n=9, flat=0.6)
            K.place(c, (math.cos(a) * d, math.sin(a) * d, z + 0.01))
            ctx.add(c, "wood_charred", uv="box", uv_scale=2.0)
        else:
            e = K.blob(f"ember{k}", er.uniform(0.018, 0.035), subdiv=1, rough=0.3, seed=er.randint(0, 999),
                       scale=(1.0, 1.0, 0.6), center=(math.cos(a) * d, math.sin(a) * d, z))
            ctx.add(e, "ember_glow", uv_scale=1.0, wear=0.0, ao=False)
    logs = 7 if ctx.clean else 5
    for k in range(logs):
        a = math.tau * k / logs + r.uniform(-0.15, 0.15)
        foot = Vector((math.cos(a) * 0.3, math.sin(a) * 0.3, 0.04))
        if ctx.clean:
            head = Vector((math.cos(a + 0.3) * 0.04, math.sin(a + 0.3) * 0.04, 0.78 + r.uniform(-0.06, 0.06)))
        else:
            head = Vector((math.cos(a + 0.6) * 0.12, math.sin(a + 0.6) * 0.12, 0.2 + r.uniform(0.0, 0.1)))
        d = head - foot
        lg = W.log_obj(f"log{k}", d.length, r.uniform(0.04, 0.06), ctx.seed + 20 + k, sides=7, rings=3,
                       bark="out_bark_ash" if k % 2 else "wood_charred", end="wood_charred")
        K.orient(lg, d.normalized(), W.up_for(d), (foot + head) / 2)
        ctx.add(lg, None, uv=None, smooth=45, patches=0.5, low=1.0, low_h=0.35)
        # the foot burning: a glowing cap on the log's end in the coals
        cap = K.blob(f"glow{k}", 0.05, subdiv=1, scale=(1.0, 1.0, 0.8), rough=0.3, seed=ctx.seed + 40 + k,
                     center=tuple(foot + d.normalized() * 0.02))
        ctx.add(cap, "ember_glow", uv_scale=1.0, wear=0.0, ao=False)
    # Wood waiting by the ring.
    for k in range(3 if ctx.clean else 1):
        lg = W.log_obj(f"spare{k}", r.uniform(0.7, 0.95), 0.06, ctx.seed + 60 + k, sides=8, rings=3, bark="out_bark_ash")
        K.place(lg, (0.95 + k * 0.03, r.uniform(-0.35, 0.35), 0.06 + k * 0.1), (0, 0, 80 + r.uniform(-10, 10)))
        ctx.add(lg, None, uv=None, smooth=45, patches=0.4)
    # Spit on forked sticks across the fire, a clay pot in the edge of the coals.
    for sx in (-1, 1):
        a = Vector((sx * 0.66, -0.02, -0.03))
        b = Vector((sx * 0.64, -0.02, 0.86))
        W.pole(ctx, f"fork{sx}", [a, b], 0.022, "out_bark_ash", r_end=0.016, seed=ctx.seed + 70 + sx)
        W.pole(ctx, f"forkb{sx}", [b - Vector((0, 0, 0.12)), b + Vector((sx * 0.08, 0.0, 0.1))], 0.016, "out_bark_ash",
               r_end=0.01, seed=ctx.seed + 73 + sx)
    W.pole(ctx, "spit", [(-0.76, -0.02, 0.84), (0, -0.01, 0.83), (0.76, -0.02, 0.85)], 0.014, "out_log_smoked", r_end=0.012,
           seed=ctx.seed + 75)
    _pot(ctx, "cookpot", (0.3, -0.34, 0.0), 0.2, 0.1, ctx.seed + 80, ash=False, rot=30)
    ctx.col_box((-0.72, -0.72, 0), (0.72, 0.72, 0.3))


BUILDERS = {
    "ashen_war_drum": ashen_war_drum,
    "ashen_spear_rack": ashen_spear_rack,
    "ashen_ash_pots": ashen_ash_pots,
    "ashen_drying_rack": ashen_drying_rack,
    "ashen_camp_fire": ashen_camp_fire,
}


def build(params: dict, outputs: list[str]) -> None:
    K.run(params, outputs, BUILDERS)
