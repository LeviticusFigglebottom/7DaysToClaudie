"""Wilderness props family — the Tamsin logging camp, the trapper's cabin and the Cedar Ridge fire
lookout: steel bunks, a box stove and a cookhouse range, mess tables and benches, locker banks,
footlockers, tool chests, ammo cans, the foreman's safe, a canvas cot, kerosene lanterns, a wash
stand, enamel dishes, split firewood and calk boots (camp); a gun rack, a pelt board with
stretched furs and leg-hold traps, a smoking rack, a chopping block with its axe, a wood-canvas
canoe, a crosscut saw on pegs, a loose trap, an outhouse and a smokehouse (cabin); an Osborne-type
fire finder on its stand, a base-station radio and the timber tower frame (lookout).

Conventions (docs/ASSET_PIPELINE.md): metres, Z up, front -Y, origin bottom centre (wall props:
origin on the wall plane, bottom centre, front -Y). Built with lib.props_ext_kit (Ctx, finalize,
one GLB per condition) and lib.props_wild_parts. Every prop is abandoned and Pacific-Northwest
damp: 'clean' is still in use the day it was left, 'worn' months later (rust, rot, moss),
'destroyed' wrecked. No text, logos or brand marks anywhere.
"""
from __future__ import annotations

import math

from mathutils import Matrix, Vector

from lib import props_ext_kit as K
from lib import props_ext_parts as P
from lib import props_wild_parts as W


# ============================================================================================
# Small helpers
# ============================================================================================

def _rot_about(objs, pivot, rot) -> None:
    """Rigidly rotates already-registered parts about a pivot (Euler degrees)."""
    p = Vector(pivot)
    m = Matrix.Translation(p) @ K.rot_matrix(rot) @ Matrix.Translation(-p)
    for o in objs if isinstance(objs, (list, tuple)) else [objs]:
        if o is None:
            continue
        o.data.transform(m)
        o.data.update()


def _move(objs, delta) -> None:
    m = Matrix.Translation(Vector(delta))
    for o in objs if isinstance(objs, (list, tuple)) else [objs]:
        if o is not None:
            o.data.transform(m)
            o.data.update()


def _plate(ctx, r, x, y, z, mat, rot=0.0):
    """Enamel mess plate (lathe) resting at z."""
    pr = [(0.0, 0.0), (0.075, 0.0), (0.09, 0.006), (0.112, 0.02), (0.121, 0.026), (0.118, 0.028), (0.108, 0.022),
          (0.086, 0.01), (0.0, 0.007)]
    o = K.lathe("plate", pr, segs=18)
    K.place(o, (x, y, z), (0, 0, rot))
    return ctx.add(o, mat, uv_scale=2.0, smooth=50, patches=0.4, edge=1.4)


def _cup(ctx, r, x, y, z, mat, rot=0.0, tipped=False):
    pr = [(0.0, 0.0), (0.038, 0.0), (0.041, 0.004), (0.043, 0.078), (0.046, 0.082), (0.041, 0.083), (0.039, 0.006),
          (0.0, 0.006)]
    body = K.lathe("cup", pr, segs=14)
    hd = K.tube("cuph", [(0.043, 0, 0.068), (0.068, 0, 0.064), (0.07, 0, 0.034), (0.043, 0, 0.022)], 0.006, segs=5)
    parts = [body, hd]
    for o in parts:
        if tipped:
            K.place(o, rot=(90, 0, 0))
            K.place(o, (0, 0, 0.046))
        K.place(o, (x, y, z), (0, 0, rot))
    ctx.add(body, mat, uv_scale=2.0, smooth=50, patches=0.4, edge=1.4)
    ctx.add(hd, mat, uv_scale=2.0, smooth=50, patches=0.4)
    return parts


def _coffee_pot(ctx, x, y, z, mat, rot=0.0, scale=1.0):
    pr = [(0.0, 0.0), (0.075, 0.0), (0.08, 0.01), (0.078, 0.12), (0.06, 0.17), (0.045, 0.19), (0.048, 0.2), (0.0, 0.2)]
    body = K.lathe("pot", pr, segs=16)
    spout = K.tube("spout", [(0.07, 0, 0.04), (0.1, 0, 0.1), (0.125, 0, 0.16), (0.135, 0, 0.17)], [0.018, 0.014, 0.01, 0.009],
                   segs=6)
    handle = K.tube("poth", [(-0.07, 0, 0.16), (-0.11, 0, 0.15), (-0.115, 0, 0.08), (-0.077, 0, 0.04)], 0.008, segs=5)
    knob = K.lathe("knob", [(0.0, 0.2), (0.012, 0.2), (0.016, 0.215), (0.0, 0.225)], segs=8)
    parts = [body, spout, handle, knob]
    for o in parts:
        K.place(o, scale=scale)
        K.place(o, (x, y, z), (0, 0, rot))
        ctx.add(o, mat, uv_scale=2.0, smooth=50, patches=0.5, edge=1.4)
    return parts


# ============================================================================================
# Steel bunk bed
# ============================================================================================

def wild_bunk_steel(ctx: K.Ctx) -> None:
    """Two-tier steel camp bunk (square tube, olive enamel): strap spring decks, thin ticking
    mattresses with wool blankets turned down, pillows, a three-rung ladder at the foot.
    Worn: rust, blankets kicked about, the lower one half on the floor. Destroyed: the upper deck
    has dropped at the foot end onto the lower bunk."""
    r = ctx.rnd("bunk")
    L, D, H = 2.0, 0.92, 1.72
    paint = "steel_locker_green"
    hx, hy = L / 2 - 0.02, D / 2 - 0.02
    t = 0.036
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.bar(ctx, f"post{sx}{sy}", (sx * hx, sy * hy, 0.018), (sx * hx, sy * hy, H), t, t, paint, bevel=0.004,
                  low=0.6, low_h=0.35)
            cap = K.box("cap", (t + 0.006, t + 0.006, 0.012), center=(sx * hx, sy * hy, H + 0.006), bevel=0.003)
            ctx.add(cap, "rubber_black", uv_scale=2.0, wear=0.3)
            foot = K.box("foot", (0.05, 0.05, 0.018), center=(sx * hx, sy * hy, 0.009), bevel=0.003)
            ctx.add(foot, "rubber_black", uv_scale=2.0, wear=0.3)
    decks = {}
    for tag, z in (("lo", 0.34), ("hi", 1.27)):
        parts = []
        for sy in (-1, 1):
            parts.append(W.bar(ctx, f"rail{tag}{sy}", (-hx, sy * hy, z), (hx, sy * hy, z), t * 0.9, t, paint, bevel=0.003))
        for sx in (-1, 1):
            parts.append(W.bar(ctx, f"end{tag}{sx}", (sx * hx, -hy, z), (sx * hx, hy, z), t * 0.9, t, paint, bevel=0.003))
            for dz in (0.22, 0.4):  # head / foot frame bars
                if tag == "hi" and dz > 0.3:
                    continue
                parts.append(W.rod(ctx, f"hb{tag}{sx}{dz}", (sx * hx, -hy, z + dz), (sx * hx, hy, z + dz), 0.011, paint,
                                   segs=6))
        for k in range(10):  # flat spring straps across, two along
            x = -hx + 0.1 + k * (2 * hx - 0.2) / 9
            parts.append(W.bar(ctx, f"strap{tag}{k}", (x, -hy, z + 0.006), (x, hy, z + 0.006), 0.03, 0.003, "chrome_pitted",
                               patches=0.5))
        for sy in (-0.18, 0.18):
            parts.append(W.bar(ctx, f"lstrap{tag}{sy}", (-hx, sy, z + 0.009), (hx, sy, z + 0.009), 0.025, 0.003,
                               "chrome_pitted", patches=0.5))
        mat = K.box(f"mat{tag}", (1.9, 0.84, 0.1), center=(0, 0, z + 0.06), bevel=0.035, bevel_segs=2, cuts=(8, 3, 0))
        sag = 0.02 if ctx.clean else 0.04
        K.map_verts(mat, lambda co, s=sag: Vector((co.x, co.y, co.z - s * (1 - (co.x / 0.95) ** 2) * (1 - (co.y / 0.42) ** 2))))
        K.noise_disp(mat, 0.008 if ctx.clean else 0.016, scale=3.0, seed=r.randint(0, 999))
        parts.append(ctx.add(mat, "mattress_ticking", uv_scale=1.0, smooth=50, patches=0.5, edge=0.5))
        top = z + 0.105 - sag * 0.6
        bl = W.drape_obj(f"blanket{tag}", 1.55, 1.25, top, 0.42, hang=0.15, fold_at=0.55, seed=r.randint(0, 999),
                         rumple=0.012 if ctx.clean else 0.03)
        K.place(bl, rot=(0, 0, 180))
        K.place(bl, (0.18, 0, 0))
        if ctx.worn and tag == "lo":
            # Kicked half off the bunk onto the floor on the open side.
            K.map_verts(bl, lambda co, zz=z: Vector((co.x, co.y - 0.25 * max(0.0, -co.y) / 0.6,
                                                     co.z - (zz + 0.08) * min(1.0, max(0.0, -co.y - 0.3) * 3.0))))
        parts.append(ctx.add(bl, "wild_wool_grey" if tag == "lo" else "wild_wool_red", uv=None, smooth=60, patches=0.0,
                             edge=0.3))
        pil = K.blob(f"pillow{tag}", 0.5, subdiv=2, scale=(0.3, 0.56, 0.1), rough=0.25, seed=r.randint(0, 999),
                     center=(-0.76, r.uniform(-0.05, 0.05), top + 0.04))
        parts.append(ctx.add(pil, "furn_linen", uv_scale=1.0, smooth=60, patches=0.0, edge=0.3))
        decks[tag] = parts
    for k, z in enumerate((0.62, 0.86, 1.08)):  # ladder rungs at the foot end
        W.rod(ctx, f"rung{k}", (hx, -hy, z), (hx, hy, z), 0.012, paint, segs=6)
    if ctx.destroyed:
        _rot_about(decks["hi"], (-hx, 0, 1.27), (0, 24, 0))
    ctx.col_box((-L / 2, -D / 2, 0), (L / 2, D / 2, H))


# ============================================================================================
# Box stove and cookhouse range
# ============================================================================================

def _stovepipe(ctx, x, y, z0, z1, *, r=0.075, damper_z=None, fallen=False):
    """Black stovepipe from z0 to the ceiling (z1) with crimped joints, a damper and a ceiling
    thimble plate. fallen: the upper run lies on the floor beside the stove."""
    parts = []
    top = z1 if not fallen else z0 + 0.45
    pipe = K.cyl("pipe", r, top - z0, segs=14, center=(x, y, (z0 + top) / 2), caps=False)
    parts.append(ctx.add(pipe, "paint_black", uv="cyl", uv_axis=2, uv_scale=1.0, smooth=50, patches=0.7, edge=0.8))
    z = z0 + 0.6
    while z < top - 0.05:
        band = W.ring_obj("band", r - 0.004, r + 0.006, 0.035, segs=14)
        K.place(band, (x, y, z))
        parts.append(ctx.add(band, "paint_black", uv_scale=2.0, smooth=50, patches=0.8))
        z += 0.61
    if damper_z is not None and damper_z < top:
        W.rod(ctx, "damper", (x - r - 0.06, y, damper_z), (x + r + 0.01, y, damper_z), 0.005, "chrome_pitted", segs=5)
        h = K.tube("dh", [(x - r - 0.06 + 0.02 * math.cos(a), y + 0.02 * math.sin(a), damper_z) for a in
                          [k * math.tau / 10 for k in range(11)]], 0.0035, segs=4)
        ctx.add(h, "chrome_pitted", uv_scale=2.0, smooth=40)
    if not fallen:
        thim = K.box("thimble", (0.3, 0.3, 0.012), center=(x, y, z1 - 0.006), bevel=0.003)
        ctx.add(thim, "metal_galvanized", uv_scale=1.0, patches=0.6)
    else:
        lie = K.cyl("pipe2", r, 1.6, segs=14, axis="X", caps=False)
        K.place(lie, (0, 0, r), (0, 0, 0))
        K.dent(lie, (0.3, -r, r), 0.12, 0.03)
        K.place(lie, (x + 0.55, y - 0.5, 0), (0, 0, 35))
        ctx.add(lie, "paint_black", uv="cyl", uv_axis=0, uv_scale=1.0, smooth=50, patches=0.9)
    return parts


def wild_wood_stove(ctx: K.Ctx) -> None:
    """Cast-iron box stove on curved legs: moulded ribs, two cooking lids, a loading door with a
    mica window (glows when the stove is lit), spin draft and latch, ash lip, and a black
    stovepipe with a damper up to the ceiling thimble. A granite-ware coffee pot on top.
    Worn: rust bloom, pot gone cold. Destroyed: door hanging off one hinge, pipe down."""
    r = ctx.rnd("stove")
    BL, BD, BH = 0.7, 0.46, 0.42
    z0 = 0.2
    iron = "wild_cast_iron" if ctx.clean else "wild_cast_iron_rust"
    body = K.box("body", (BL, BD, BH), center=(0, 0, z0 + BH / 2), bevel=0.012, cuts=(3, 2, 2))
    if ctx.destroyed:
        K.dent(body, (0.2, -BD / 2, z0 + 0.12), 0.12, 0.02)
    ctx.add(body, iron, uv_scale=1.0, patches=0.5, edge=1.2)
    for zz in (z0 + 0.035, z0 + BH - 0.035):
        rib = K.box("rib", (BL + 0.018, BD + 0.018, 0.024), center=(0, 0, zz), bevel=0.006)
        ctx.add(rib, iron, uv_scale=1.0, patches=0.5, edge=1.5)
    for sx in (-1, 1):  # vertical corner beads
        for sy in (-1, 1):
            W.bar(ctx, "bead", (sx * BL / 2, sy * BD / 2, z0 + 0.02), (sx * BL / 2, sy * BD / 2, z0 + BH - 0.02), 0.022, 0.022,
                  iron, bevel=0.006)
    top = K.box("top", (BL + 0.06, BD + 0.05, 0.03), center=(0, 0, z0 + BH + 0.015), bevel=0.006)
    ctx.add(top, iron, uv_scale=1.0, patches=0.4, edge=1.5)
    zt = z0 + BH + 0.03
    for x in (-0.16, 0.16):
        lid = K.cyl("lid", 0.1, 0.012, segs=18, center=(x, -0.02, zt + 0.003))
        ctx.add(lid, iron, uv_scale=1.0, smooth=40, patches=0.4, edge=1.6)
        slot = K.box("slot", (0.05, 0.012, 0.006), center=(x, -0.02, zt + 0.011))
        ctx.add(slot, "paint_black", uv_scale=2.0)
    for sx in (-1, 1):
        for sy in (-1, 1):
            pts = [(sx * (BL / 2 - 0.06), sy * (BD / 2 - 0.06), z0 + 0.01), (sx * (BL / 2 - 0.03), sy * (BD / 2 - 0.03), z0 * 0.55),
                   (sx * (BL / 2 + 0.005), sy * (BD / 2 + 0.005), 0.04), (sx * (BL / 2 + 0.02), sy * (BD / 2 + 0.02), 0.0)]
            leg = K.tube("leg", pts, [0.03, 0.022, 0.02, 0.028], segs=6)
            ctx.add(leg, iron, uv_scale=2.0, smooth=45, patches=0.5)
    # Loading door on the front: mica window, spin draft, hinges on the left, latch on the right.
    dz = z0 + BH / 2
    dy = -BD / 2 - 0.012
    door_parts = []
    door = K.box("door", (0.36, 0.02, 0.27), center=(0, dy, dz), bevel=0.006)
    door_parts.append(ctx.add(door, iron, uv_scale=1.0, patches=0.4, edge=1.6))
    frame = K.box("dframe", (0.26, 0.012, 0.12), center=(0.02, dy - 0.012, dz + 0.04), bevel=0.003)
    door_parts.append(ctx.add(frame, iron, uv_scale=1.0, patches=0.4, edge=1.6))
    mica = K.box("mica", (0.22, 0.004, 0.085), center=(0.02, dy - 0.019, dz + 0.04))
    door_parts.append(ctx.add(mica, "mica_glow", uv_scale=1.0, wear=0.0, ao=False))
    draft = K.cyl("draft", 0.045, 0.012, segs=16, axis="Y", center=(0.0, dy - 0.016, dz - 0.07))
    door_parts.append(ctx.add(draft, iron, uv_scale=2.0, smooth=40, patches=0.4, edge=1.5))
    knob = K.cyl("dknob", 0.012, 0.03, segs=8, axis="Y", center=(0.0, dy - 0.035, dz - 0.07))
    door_parts.append(ctx.add(knob, "chrome_pitted", uv_scale=2.0, smooth=40))
    latch = W.bar(ctx, "latch", (0.15, dy - 0.03, dz - 0.04), (0.2, dy - 0.03, dz + 0.02), 0.014, 0.012, "chrome_pitted",
                  up=(0, -1, 0))
    door_parts.append(latch)
    hinges = []
    for zz in (dz - 0.08, dz + 0.08):
        h = K.cyl("hinge", 0.01, 0.05, segs=8, center=(-0.185, dy - 0.006, zz))
        hinges.append(ctx.add(h, iron, uv_scale=2.0, smooth=40))
    lip = K.box("lip", (0.4, 0.07, 0.012), center=(0, -BD / 2 - 0.035, z0 + 0.03), bevel=0.003)
    K.place(lip, rot=(-12, 0, 0))
    ctx.add(lip, iron, uv_scale=1.0, patches=0.5)
    if ctx.destroyed:
        # Torn from the top hinge: swung open and sagging forward.
        _rot_about(door_parts, (-0.185, dy, dz - 0.08), (0, 0, -100))
        _rot_about(door_parts, (-0.185, dy, dz - 0.08), (0, 25, 0))
    # Flue collar + pipe.
    collar = K.cyl("collar", 0.085, 0.06, segs=14, center=(0.18, 0.1, zt + 0.03))
    ctx.add(collar, iron, uv="cyl", uv_axis=2, smooth=45, patches=0.5)
    _stovepipe(ctx, 0.18, 0.1, zt + 0.055, 2.75, damper_z=1.05, fallen=ctx.destroyed)
    if not ctx.destroyed:
        _coffee_pot(ctx, -0.16, -0.02, zt + 0.012, "wild_enamel_blue", rot=30 if ctx.clean else 140)
    ctx.col_box((-BL / 2 - 0.04, -BD / 2 - 0.06, 0), (BL / 2 + 0.04, BD / 2 + 0.03, 2.75 if not ctx.destroyed else 1.0))


def wild_cook_range(ctx: K.Ctx) -> None:
    """Cookhouse wood range: cast-iron body on short legs, six lids, firebox and ash doors on the
    left, a big oven door with nickel bar and heat dial on the right, a hot-water reservoir at
    the end, nickel towel rail, a high warming closet on brackets, stovepipe to the ceiling.
    Worn: rust, a door ajar. Destroyed: reservoir lid gone, oven door hanging, pipe down."""
    r = ctx.rnd("range")
    L, D = 1.42, 0.66
    z0, H = 0.12, 0.7
    iron = "wild_cast_iron" if ctx.clean else "wild_cast_iron_rust"
    nickel = "chrome_pitted"
    body = K.box("body", (L, D, H), center=(0, 0, z0 + H / 2), bevel=0.01, cuts=(4, 2, 2))
    ctx.add(body, iron, uv_scale=1.0, patches=0.5, edge=1.2)
    top = K.box("top", (L + 0.05, D + 0.04, 0.035), center=(0, 0, z0 + H + 0.017), bevel=0.006)
    ctx.add(top, iron, uv_scale=1.0, patches=0.4, edge=1.5)
    zt = z0 + H + 0.035
    for i, x in enumerate((-0.5, -0.2, 0.1)):
        for y in (-0.15, 0.15):
            lid = K.cyl("lid", 0.095, 0.01, segs=16, center=(x, y, zt + 0.004))
            ctx.add(lid, iron, uv_scale=1.0, smooth=40, patches=0.4, edge=1.6)
    trim = K.box("trim", (L + 0.06, 0.02, 0.03), center=(0, -D / 2 - 0.022, zt - 0.02), bevel=0.004)
    ctx.add(trim, nickel, uv_scale=1.0, patches=0.6)
    for sx in (-1, 1):
        for sy in (-1, 1):
            leg = K.tube("leg", [(sx * (L / 2 - 0.06), sy * (D / 2 - 0.06), z0), (sx * (L / 2 - 0.04), sy * (D / 2 - 0.04), 0.05),
                                 (sx * (L / 2 - 0.03), sy * (D / 2 - 0.03), 0.0)], [0.035, 0.028, 0.034], segs=6)
            ctx.add(leg, iron, uv_scale=2.0, smooth=45, patches=0.5)
    fy = -D / 2 - 0.012
    # Firebox (left): small door with draft, ash door below.
    fd = K.box("firedoor", (0.3, 0.02, 0.2), center=(-0.5, fy, z0 + 0.5), bevel=0.006)
    ctx.add(fd, iron, uv_scale=1.0, patches=0.4, edge=1.6)
    mica = K.box("mica", (0.16, 0.004, 0.06), center=(-0.5, fy - 0.012, z0 + 0.52))
    ctx.add(mica, "mica_glow", uv_scale=1.0, wear=0.0, ao=False)
    ad = K.box("ashdoor", (0.3, 0.02, 0.12), center=(-0.5, fy, z0 + 0.17), bevel=0.006)
    ctx.add(ad, iron, uv_scale=1.0, patches=0.4, edge=1.6)
    for zz in (z0 + 0.5, z0 + 0.17):
        k = K.cyl("knob", 0.012, 0.035, segs=8, axis="Y", center=(-0.38, fy - 0.025, zz))
        ctx.add(k, nickel, uv_scale=2.0, smooth=40)
    # Oven (right).
    oven_parts = []
    od = K.box("ovendoor", (0.55, 0.025, 0.44), center=(0.2, fy, z0 + 0.36), bevel=0.008, cuts=(2, 0, 2))
    oven_parts.append(ctx.add(od, iron, uv_scale=1.0, patches=0.4, edge=1.6))
    panel = K.box("ovenpanel", (0.42, 0.012, 0.3), center=(0.2, fy - 0.016, z0 + 0.36), bevel=0.01)
    oven_parts.append(ctx.add(panel, iron, uv_scale=1.0, patches=0.5, edge=1.8))
    bar = W.rod(ctx, "ovenbar", (0.0, fy - 0.05, z0 + 0.55), (0.4, fy - 0.05, z0 + 0.55), 0.01, nickel, segs=8)
    oven_parts.append(bar)
    dial = K.cyl("dial", 0.045, 0.012, segs=16, axis="Y", center=(0.2, fy - 0.026, z0 + 0.45))
    oven_parts.append(ctx.add(dial, nickel, uv_scale=2.0, smooth=40))
    if ctx.worn:
        _rot_about(oven_parts, (0.2, fy, z0 + 0.14), (-35 if not ctx.destroyed else -80, 0, 0))
    # Reservoir at the right end.
    res = K.box("reservoir", (0.24, D - 0.04, 0.5), center=(L / 2 + 0.12, 0, z0 + 0.45), bevel=0.01)
    ctx.add(res, iron, uv_scale=1.0, patches=0.5, edge=1.2)
    if not ctx.destroyed:
        rl = K.box("reslid", (0.26, D - 0.02, 0.02), center=(L / 2 + 0.12, 0, z0 + 0.71), bevel=0.005)
        ctx.add(rl, nickel, uv_scale=1.0, patches=0.6)
    # Towel rail on brackets.
    W.rod(ctx, "rail", (-L / 2, -D / 2 - 0.09, z0 + 0.62), (L / 2 + 0.2, -D / 2 - 0.09, z0 + 0.62), 0.009, nickel, segs=8)
    for x in (-L / 2 + 0.02, L / 2 + 0.18):
        W.bar(ctx, "rb", (x, -D / 2, z0 + 0.62), (x, -D / 2 - 0.09, z0 + 0.62), 0.012, 0.012, nickel)
    # Warming closet on brackets.
    wz = 1.38
    wc = K.box("warmer", (1.1, 0.28, 0.28), center=(0.15, 0.18, wz + 0.14), bevel=0.008)
    ctx.add(wc, iron, uv_scale=1.0, patches=0.5, edge=1.3)
    for x in (-0.15, 0.45):
        dd = K.box("wdoor", (0.28, 0.012, 0.18), center=(x, 0.18 - 0.146, wz + 0.14), bevel=0.004)
        ctx.add(dd, iron, uv_scale=1.0, patches=0.4, edge=1.6)
        kk = K.cyl("wk", 0.01, 0.02, segs=8, axis="Y", center=(x + 0.1, 0.18 - 0.16, wz + 0.14))
        ctx.add(kk, nickel, uv_scale=2.0, smooth=40)
    for x in (-0.35, 0.65):
        br = K.tube("bracket", [(x, 0.3, zt), (x, 0.28, wz - 0.1), (x, 0.2, wz)], 0.014, segs=5, flat=(1.0, 0.5))
        ctx.add(br, iron, uv_scale=2.0, smooth=40)
    collar = K.cyl("collar", 0.085, 0.06, segs=14, center=(-0.56, 0.2, zt + 0.03))
    ctx.add(collar, iron, uv="cyl", uv_axis=2, smooth=45, patches=0.5)
    _stovepipe(ctx, -0.56, 0.2, zt + 0.055, 2.75, damper_z=1.25, fallen=ctx.destroyed)
    if not ctx.destroyed:
        _coffee_pot(ctx, 0.1, -0.15, zt + 0.01, "wild_enamel_blue", rot=r.uniform(0, 360))
        pan = K.lathe("pan", [(0.0, 0.0), (0.13, 0.0), (0.14, 0.05), (0.135, 0.05), (0.125, 0.006), (0.0, 0.006)], segs=16)
        K.place(pan, (-0.2, 0.15, zt + 0.01))
        ctx.add(pan, iron, uv_scale=1.0, smooth=45, patches=0.6)
        W.bar(ctx, "panh", (-0.06, 0.15, zt + 0.05), (0.14, 0.2, zt + 0.06), 0.02, 0.008, iron)
    ctx.col_box((-L / 2 - 0.03, -D / 2 - 0.1, 0), (L / 2 + 0.24, D / 2 + 0.02, 2.75 if not ctx.destroyed else 1.7))
    _move(ctx.parts + ctx.cols, (-0.105, 0.04, 0.0))  # centre the footprint (reservoir end, towel rail)


# ============================================================================================
# Mess table and bench
# ============================================================================================

def wild_mess_table(ctx: K.Ctx) -> None:
    """Cookhouse mess table: five rough planks with gaps on two trestles and a stretcher, a
    granite-ware setting (plates, cups, coffee pot). Worn: plates pushed about, a cup tipped.
    Destroyed: one trestle kicked out, the top slumped to the floor, dishes scattered."""
    r = ctx.rnd("mess")
    L, D, H = 2.4, 0.86, 0.76
    wood = "wild_lumber_dark"
    n = 5
    pw = (D - 0.008 * (n - 1)) / n
    top_parts = []
    for i in range(n):
        y = -D / 2 + pw / 2 + i * (pw + 0.008)
        pl = P.plank(f"top{i}", L - r.uniform(0.0, 0.03), pw, 0.04, cuts=5, cup=0.003, bow=r.uniform(0.0, 0.005))
        K.place(pl, (r.uniform(-0.012, 0.012), y, H - 0.02))
        top_parts.append(ctx.add(pl, wood, long_axis=0, patches=0.5, edge=1.3))
    for x in (-0.82, 0.82):
        top_parts.append(W.bar(ctx, "cleat", (x, -D / 2 + 0.04, H - 0.07), (x, D / 2 - 0.04, H - 0.07), 0.08, 0.06, wood))
    leg_parts = {}
    for side, x in ((-1, -0.82), (1, 0.82)):
        ps = []
        for sy in (-1, 1):
            ps.append(W.bar(ctx, "leg", (x, sy * 0.3, 0.03), (x, sy * 0.15, H - 0.1), 0.09, 0.06, wood, up=(1, 0, 0)))
        ps.append(W.bar(ctx, "foot", (x, -0.36, 0.035), (x, 0.36, 0.035), 0.09, 0.07, wood))
        ps.append(W.bar(ctx, "brace", (x, -0.24, 0.32), (x, 0.24, 0.32), 0.07, 0.04, wood))
        leg_parts[side] = ps
    stretch = W.bar(ctx, "stretcher", (-0.82, 0, 0.3), (0.82, 0, 0.3), 0.1, 0.05, wood, ext=0.04)
    dish = "wild_enamel_white" if r.random() < 0.5 else "wild_enamel_blue"
    dishes = []
    if not ctx.destroyed:
        places = [(-0.75, -0.24), (-0.2, -0.26), (0.45, -0.25), (-0.5, 0.25), (0.3, 0.26)]
        for k, (x, y) in enumerate(places):
            jx, jy = (r.uniform(-0.05, 0.05), r.uniform(-0.03, 0.03)) if ctx.clean else (r.uniform(-0.2, 0.2), r.uniform(-0.1, 0.1))
            dishes.append(_plate(ctx, r, x + jx, y + jy, H, dish if k % 2 else "wild_enamel_blue", rot=r.uniform(0, 360)))
            if k < 3:
                dishes += _cup(ctx, r, x + jx + 0.17, y + jy + 0.1, H, "wild_enamel_blue", rot=r.uniform(0, 360),
                               tipped=ctx.worn and k == 1)
        dishes += _coffee_pot(ctx, 0.95, 0.05, H, "wild_enamel_blue", rot=r.uniform(0, 360))
    else:
        _rot_about(top_parts + [stretch], (-0.82, 0, H), (0, 21, 0))
        _rot_about(leg_parts[1], (0.82, 0.36, 0.0), (80, 0, 0))
        _move(leg_parts[1], (0.25, 0.12, 0.0))
        for k in range(4):
            dishes.append(_plate(ctx, r, r.uniform(-0.6, 1.4), r.uniform(-0.9, -0.5), 0.0, "wild_enamel_white",
                                 rot=r.uniform(0, 360)))
        _cup(ctx, r, 0.6, -0.7, 0.0, "wild_enamel_blue", rot=40, tipped=True)
    ctx.col_box((-L / 2, -D / 2, 0), (L / 2, D / 2, H))


def wild_mess_bench(ctx: K.Ctx) -> None:
    """Plank bench for the mess table: two-board seat on splayed board legs with a stretcher.
    Destroyed: snapped at one leg and tipped onto its side."""
    r = ctx.rnd("bench")
    L, D, H = 2.2, 0.3, 0.45
    wood = "wild_lumber_dark"
    parts = []
    for i, y in enumerate((-0.072, 0.072)):
        pl = P.plank(f"seat{i}", L - r.uniform(0, 0.03), 0.138, 0.04, cuts=4, bow=r.uniform(0.0, 0.006))
        K.place(pl, (0, y, H - 0.02))
        parts.append(ctx.add(pl, wood, long_axis=0, patches=0.5, edge=1.3))
    for x in (-0.78, 0.78):
        lg = K.prism("legboard", [(-0.13, 0.0), (-0.04, 0.0), (0.0, 0.05), (0.04, 0.0), (0.13, 0.0), (0.12, H - 0.04),
                                  (-0.12, H - 0.04)], 0.038, plane="YZ")
        K.place(lg, (x, 0, 0))
        parts.append(ctx.add(lg, wood, uv_scale=1.0, patches=0.5, edge=1.3))
        parts.append(W.bar(ctx, "cleat", (x - 0.03, -0.13, H - 0.06), (x + 0.03, -0.13, H - 0.06), 0.04, 0.04, wood))
    parts.append(W.bar(ctx, "stretcher", (-0.78, 0, 0.15), (0.78, 0, 0.15), 0.08, 0.04, wood, ext=0.02))
    if ctx.destroyed:
        _rot_about(parts, (0, 0.15, 0), (-90, 0, 0))
        _move(parts, (0, 0, 0.0))
        lo = min(min(v.co.z for v in o.data.vertices) for o in parts)
        _move(parts, (0, 0, -lo))
    ctx.col_box((-L / 2, -D / 2, 0), (L / 2, D / 2, H))


# ============================================================================================
# Lockers, footlocker, tool chest, ammo can, floor safe
# ============================================================================================

def wild_locker_steel(ctx: K.Ctx) -> None:
    """Bank of two steel crew lockers: louvred doors, lift handles, padlock hasps, blank brass
    number plates, kick plate, hat shelf and hooks inside. Worn: the right door hangs open on a
    flannel shirt and a pair of boots. Destroyed: dented, the left door torn off on the floor."""
    r = ctx.rnd("locker")
    Wd, D, H = 0.76, 0.46, 1.82
    paint = "steel_locker_green"
    t = 0.012
    shell = [K.box("back", (Wd, t, H), center=(0, D / 2 - t / 2, H / 2)),
             K.box("top", (Wd, D, t), center=(0, 0, H - t / 2), bevel=0.003),
             K.box("bottom", (Wd - 2 * t, D - t, t), center=(0, 0, 0.11)),
             K.box("div", (t, D - t, H - 0.12), center=(0, 0, 0.12 + (H - 0.12) / 2))]
    for sx in (-1, 1):
        shell.append(K.box("side", (t, D, H), center=(sx * (Wd / 2 - t / 2), 0, H / 2)))
    for k, o in enumerate(shell):
        if ctx.destroyed and k == 4:
            K.dent(o, (-Wd / 2, -0.05, 0.9), 0.25, 0.04, direction=(1, 0, 0))
        ctx.add(o, paint, uv_scale=1.0, patches=0.22, edge=0.45, low=0.5, low_h=0.25)
    kick = K.box("kick", (Wd, 0.02, 0.1), center=(0, -D / 2 + 0.01, 0.05))
    ctx.add(kick, paint, uv_scale=1.0, patches=0.35, edge=0.6, low=0.8, low_h=0.12)
    for x in (-Wd / 4, Wd / 4):
        shelf = K.box("shelf", (Wd / 2 - 0.03, D - 0.04, 0.01), center=(x, 0.0, 1.52))
        ctx.add(shelf, paint, uv_scale=1.0, patches=0.2, edge=0.5)
        hook = K.tube("hook", [(x, D / 2 - t, 1.4), (x, D / 2 - 0.06, 1.4), (x, D / 2 - 0.08, 1.43)], 0.005, segs=5)
        ctx.add(hook, "chrome_pitted", uv_scale=2.0, smooth=40)
    doors = {}
    dw, dh = Wd / 2 - 0.02, H - 0.2
    for side, xc, hinge_x in (("L", -Wd / 4, -Wd / 2 + 0.008), ("R", Wd / 4, Wd / 2 - 0.008)):
        ps = []
        dy = -D / 2 - 0.006
        door = K.box(f"door{side}", (dw, 0.012, dh), center=(xc, dy, 0.12 + dh / 2), bevel=0.003, cuts=(1, 0, 3))
        if ctx.destroyed:
            K.dent(door, (xc + 0.05, dy, 0.9), 0.2, 0.03, direction=(0, 1, 0))
        ps.append(ctx.add(door, paint, uv_scale=1.0, patches=0.25, edge=0.5))
        for zb in (0.2, 1.55):
            for k in range(6):
                lv = K.box("louvre", (dw * 0.6, 0.006, 0.016))
                K.place(lv, rot=(-35, 0, 0))
                K.place(lv, (xc, dy - 0.009, zb + k * 0.032))
                ps.append(ctx.add(lv, paint, uv_scale=2.0, patches=0.25, edge=0.8))
        hx = xc + (dw / 2 - 0.05) * (1 if side == "L" else -1)
        hd = K.box("handle", (0.03, 0.025, 0.12), center=(hx, dy - 0.016, 1.0), bevel=0.004)
        ps.append(ctx.add(hd, "chrome_pitted", uv_scale=2.0))
        hasp = K.tube("hasp", [(hx, dy - 0.02, 1.08), (hx, dy - 0.045, 1.09), (hx, dy - 0.045, 1.12), (hx, dy - 0.02, 1.13)],
                      0.004, segs=4)
        ps.append(ctx.add(hasp, "chrome_pitted", uv_scale=2.0, smooth=40))
        plate = K.box("numplate", (0.07, 0.004, 0.035), center=(xc, dy - 0.008, 1.46), bevel=0.002)
        ps.append(ctx.add(plate, "furn_brass", uv_scale=2.0, patches=0.5))
        doors[side] = (ps, hinge_x, dy)
    # Padlock on the closed left locker.
    if not ctx.destroyed:
        hx = -Wd / 4 + (dw / 2 - 0.05)
        body = K.box("padlock", (0.04, 0.02, 0.045), center=(hx, -D / 2 - 0.06, 1.06), bevel=0.006)
        ctx.add(body, "furn_brass", uv_scale=2.0, patches=0.5)
        sh = K.tube("shackle", [(hx - 0.012, -D / 2 - 0.06, 1.08), (hx - 0.012, -D / 2 - 0.05, 1.105), (hx + 0.012, -D / 2 - 0.05, 1.105),
                                (hx + 0.012, -D / 2 - 0.06, 1.08)], 0.004, segs=4)
        ctx.add(sh, "chrome_pitted", uv_scale=2.0, smooth=40)
    if ctx.worn:
        ps, hxr, dy = doors["R"]
        _rot_about(ps, (hxr, dy, 0), (0, 0, -100 if not ctx.destroyed else -60))
        shirt = K.grid("shirt", 0.42, 0.72, 6, 8)
        K.uv_planar(shirt, 2, scale=1.0)
        K.map_verts(shirt, lambda co: Vector((co.x * (1.0 - 0.35 * max(0.0, (co.y + 0.36) / 0.72)), 0.0,
                                               1.4 - (0.36 - co.y) * 0.95)))
        K.crumple(shirt, 0.03, scale=4.0, seed=r.randint(0, 999))
        K.solidify(shirt, 0.01, even=False)
        K.place(shirt, (Wd / 4, D / 2 - 0.1, 0))
        ctx.add(shirt, "flannel_red", uv=None, smooth=60, patches=0.0)
        for k in range(2):
            bt = _boot(ctx, r, f"lboot{k}")
            if k == 1:
                _rot_about(bt, (0, 0, 0), (0, 0, 8))
            _move(bt, (Wd / 4 + (k - 0.5) * 0.115, 0.01, 0.117))
    if ctx.destroyed:
        ps, hxl, dy = doors["L"]
        _rot_about(ps, (hxl, dy, 0.12), (-90, 0, 0))
        _move(ps, (0.05, -0.12, -0.11))
    ctx.col_box((-Wd / 2, -D / 2, 0), (Wd / 2, D / 2, H))


def wild_footlocker(ctx: K.Ctx) -> None:
    """Painted plywood footlocker: brass corner caps, edge strapping, rope handles on cleats, a
    hasp with a padlock. Worn: unlocked, lid propped open on a tray of folded wool and tins.
    Destroyed: lid wrenched off and lying alongside, contents rummaged."""
    r = ctx.rnd("footlocker")
    L, D, Hb, Hl = 0.8, 0.42, 0.3, 0.1
    wood = "wood_painted_green"
    body = K.box("body", (L, D, Hb), center=(0, 0, Hb / 2), bevel=0.006, cuts=(2, 1, 1))
    ctx.add(body, wood, uv_scale=1.0, patches=0.2, edge=0.45, low=0.4, low_h=0.1)
    lid_parts = [ctx.add(K.box("lid", (L + 0.006, D + 0.006, Hl), center=(0, 0, Hb + Hl / 2), bevel=0.006), wood,
                         uv_scale=1.0, patches=0.2, edge=0.45)]
    corners = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for z, top in ((0.0, False), (Hb + Hl, True)):
                cz = z + (0.03 if not top else -0.03)
                c = K.box("corner", (0.06, 0.06, 0.06), center=(sx * (L / 2 - 0.027), sy * (D / 2 - 0.027), cz), bevel=0.008)
                corners.append((c, top))
    for c, top in corners:
        o = ctx.add(c, "furn_brass", uv_scale=2.0, patches=0.6, edge=1.5)
        if top:
            lid_parts.append(o)
    for sy in (-1, 1):
        W.bar(ctx, "strapb", (-L / 2 + 0.06, sy * (D / 2 + 0.002), Hb - 0.02), (L / 2 - 0.06, sy * (D / 2 + 0.002), Hb - 0.02),
              0.004, 0.025, "furn_brass", up=(0, sy, 0))
        lid_parts.append(W.bar(ctx, "strapl", (-L / 2 + 0.06, sy * (D / 2 + 0.005), Hb + 0.02),
                               (L / 2 - 0.06, sy * (D / 2 + 0.005), Hb + 0.02), 0.004, 0.025, "furn_brass", up=(0, sy, 0)))
    for sx in (-1, 1):
        for sy in (-0.1, 0.1):
            cl = K.box("cleat", (0.025, 0.04, 0.04), center=(sx * (L / 2 + 0.012), sy, Hb * 0.62))
            ctx.add(cl, "wood_stained", uv_scale=2.0)
        rope = K.tube("rope", [(sx * (L / 2 + 0.02), -0.1, Hb * 0.62), (sx * (L / 2 + 0.05), -0.08, Hb * 0.5),
                               (sx * (L / 2 + 0.055), 0.0, Hb * 0.47), (sx * (L / 2 + 0.05), 0.08, Hb * 0.5),
                               (sx * (L / 2 + 0.02), 0.1, Hb * 0.62)], 0.009, segs=6)
        ctx.add(rope, "item_rope", uv_scale=3.0, smooth=50, patches=0.2)
    hasp = K.box("hasp", (0.04, 0.006, 0.09), center=(0, -D / 2 - 0.004, Hb + 0.01), bevel=0.002)
    lid_parts.append(ctx.add(hasp, "chrome_pitted", uv_scale=2.0))
    staple = K.box("staple", (0.03, 0.012, 0.02), center=(0, -D / 2 - 0.008, Hb - 0.035))
    ctx.add(staple, "chrome_pitted", uv_scale=2.0)
    if ctx.clean:
        pl = K.box("padlock", (0.045, 0.022, 0.05), center=(0, -D / 2 - 0.028, Hb - 0.07), bevel=0.006)
        ctx.add(pl, "furn_brass", uv_scale=2.0, patches=0.5)
        sh = K.tube("shackle", [(-0.012, -D / 2 - 0.028, Hb - 0.045), (-0.012, -D / 2 - 0.018, Hb - 0.02),
                                (0.012, -D / 2 - 0.018, Hb - 0.02), (0.012, -D / 2 - 0.028, Hb - 0.045)], 0.004, segs=4)
        ctx.add(sh, "chrome_pitted", uv_scale=2.0, smooth=40)
    if ctx.worn:
        tray = K.box("tray", (L - 0.05, D - 0.05, 0.02), center=(0, 0, Hb - 0.035))
        ctx.add(tray, "wood_stained", uv_scale=1.0, patches=0.5)
        fold = K.box("wool", (0.36, 0.3, 0.07), center=(-0.16, 0.0, Hb - 0.0), bevel=0.025, bevel_segs=2, cuts=(2, 2, 1))
        K.noise_disp(fold, 0.01, scale=4.0, seed=r.randint(0, 99))
        ctx.add(fold, "wild_wool_grey", uv_scale=1.0, smooth=50, patches=0.0)
        for k in range(3):
            tin = K.lathe("tin", [(0.0, 0.0), (0.04, 0.0), (0.04, 0.09), (0.0, 0.09)], segs=10)
            K.place(tin, (0.12 + k * 0.09, r.uniform(-0.08, 0.08), Hb - 0.025))
            ctx.add(tin, "furn_tin", uv="cyl", uv_scale=2.0, smooth=40, patches=0.6)
        if ctx.destroyed:
            _rot_about(lid_parts, (0, D / 2, Hb), (0, 0, 0))
            _move(lid_parts, (0, 0, -Hb))
            _rot_about(lid_parts, (0, 0, 0), (0, 0, 28))
            _move(lid_parts, (0.25, -0.62, 0))
        else:
            _rot_about(lid_parts, (0, D / 2, Hb), (-105, 0, 0))
    ctx.col_box((-L / 2 - 0.06, -D / 2, 0), (L / 2 + 0.06, D / 2, Hb + Hl))


def wild_tool_chest(ctx: K.Ctx) -> None:
    """Logger's tool chest: board box with iron strapping and drop handles, a lid with a till.
    Clean: closed and hasped. Worn: lid thrown back on a till of files, wedges and a hand saw.
    Destroyed: lid torn off beside it, a side board split."""
    r = ctx.rnd("toolchest")
    L, D, H = 0.94, 0.5, 0.42
    wood = "wood_creosote" if not ctx.clean else "wood_stained"
    t = 0.022
    boards = [K.box("bottom", (L, D, t), center=(0, 0, t / 2)),
              K.box("front", (L, t, H), center=(0, -D / 2 + t / 2, H / 2)),
              K.box("back", (L, t, H), center=(0, D / 2 - t / 2, H / 2)),
              K.box("left", (t, D - 2 * t, H), center=(-L / 2 + t / 2, 0, H / 2)),
              K.box("right", (t, D - 2 * t, H), center=(L / 2 - t / 2, 0, H / 2))]
    for k, b in enumerate(boards):
        if ctx.destroyed and k == 4:
            K.cut_plane(b, (L / 2, 0.05, 0.25), (0.0, 0.6, 1.0), keep="below")
        ctx.add(b, wood, long_axis=0 if k < 3 else 1, patches=0.6, edge=1.4, low=0.6, low_h=0.1)
    for z in (0.08, H - 0.08):  # iron bands round the box
        for sy in (-1, 1):
            W.bar(ctx, "band", (-L / 2, sy * (D / 2 + 0.003), z), (L / 2, sy * (D / 2 + 0.003), z), 0.005, 0.035,
                  "item_iron_strap", up=(0, sy, 0))
        for sx in (-1, 1):
            W.bar(ctx, "bandx", (sx * (L / 2 + 0.003), -D / 2, z), (sx * (L / 2 + 0.003), D / 2, z), 0.005, 0.035,
                  "item_iron_strap", up=(sx, 0, 0))
    for sx in (-1, 1):
        plate = K.box("hplate", (0.006, 0.12, 0.06), center=(sx * (L / 2 + 0.006), 0, H * 0.7))
        ctx.add(plate, "item_iron_strap", uv_scale=2.0)
        hd = K.tube("handle", [(sx * (L / 2 + 0.01), -0.06, H * 0.72), (sx * (L / 2 + 0.035), -0.05, H * 0.58),
                               (sx * (L / 2 + 0.04), 0.0, H * 0.55), (sx * (L / 2 + 0.035), 0.05, H * 0.58),
                               (sx * (L / 2 + 0.01), 0.06, H * 0.72)], 0.007, segs=5)
        ctx.add(hd, "item_iron_strap", uv_scale=2.0, smooth=40)
    lid = [ctx.add(K.box("lid", (L + 0.02, D + 0.02, 0.035), center=(0, 0, H + 0.0175), bevel=0.005, cuts=(2, 0, 0)), wood,
                   long_axis=0, patches=0.6, edge=1.5)]
    for x in (-L / 2 + 0.12, L / 2 - 0.12):
        lid.append(W.bar(ctx, "lidband", (x, -D / 2 - 0.012, H + 0.036), (x, D / 2 + 0.012, H + 0.036), 0.035, 0.005,
                         "item_iron_strap"))
    lid.append(ctx.add(K.box("hasp", (0.04, 0.006, 0.08), center=(0, -D / 2 - 0.014, H - 0.01), bevel=0.002),
                       "item_iron_strap", uv_scale=2.0))
    if ctx.worn:
        till = K.box("till", (L - 0.06, 0.16, 0.08), center=(0, D / 2 - 0.11, H - 0.06))
        ctx.add(till, "wood_stained", uv_scale=1.0, patches=0.6)
        for k in range(5):  # file and chisel handles in the till
            x = -0.36 + k * 0.17 + r.uniform(-0.03, 0.03)
            W.rod(ctx, f"fh{k}", (x, D / 2 - 0.16, H - 0.01), (x + r.uniform(-0.04, 0.04), D / 2 - 0.06, H + 0.0), 0.012,
                  "item_wood_handle", segs=6)
        for k in range(2):  # felling wedges
            wdg = K.prism("wedge", [(0.0, 0.0), (0.2, 0.0), (0.2, 0.025)], 0.06, plane="XZ")
            K.place(wdg, (-0.3 + k * 0.25, -0.08, 0.03), (0, 0, r.uniform(-20, 20)))
            ctx.add(wdg, "wild_saw_steel_rust", uv_scale=2.0, patches=0.5)
        saw = W.saw_plate_obj("handsaw", W.saw_outline(0.6, 0.12, 0.012, 0.006, back_curve=-0.03), 0.0015)
        K.place(saw, (0.0, 0.0, 0.0), (0, 0, 0))
        K.place(saw, (0.05, -0.05, 0.05), (78, 0, 8))
        ctx.add(saw, "wild_saw_steel_rust", uv_scale=1.0, patches=0.5)
        sh = K.box("sawhandle", (0.14, 0.025, 0.11), center=(-0.3, -0.05, 0.08), bevel=0.01)
        ctx.add(sh, "item_wood_handle", uv_scale=2.0)
        if ctx.destroyed:
            _rot_about(lid, (0, D / 2, H), (0, 0, 0))
            _move(lid, (0, 0, -H))
            _rot_about(lid, (0, 0, 0), (0, 0, -24))
            _move(lid, (-0.3, -0.65, 0))
        else:
            _rot_about(lid, (0, D / 2 + 0.01, H + 0.02), (-108, 0, 0))
    ctx.col_box((-L / 2 - 0.04, -D / 2, 0), (L / 2 + 0.04, D / 2, H + 0.04))


def wild_ammo_box(ctx: K.Ctx) -> None:
    """Army surplus ammo can: pressed ribs, hinged lid with gasket, cam latch lever on the end,
    folding carry handle. Worn: rusted, lid unlatched and ajar. Destroyed: crushed, lid off."""
    r = ctx.rnd("ammo")
    L, D, H = 0.28, 0.145, 0.165
    paint = "paint_olive"
    body = K.box("body", (L, D, H), center=(0, 0, H / 2), bevel=0.008, cuts=(2, 1, 2))
    if ctx.destroyed:
        K.dent(body, (0.08, -D / 2, 0.1), 0.09, 0.03)
        K.dent(body, (-0.1, D / 2, 0.12), 0.07, 0.02)
    ctx.add(body, paint, uv_scale=2.0, patches=0.6, edge=1.5, low=0.5, low_h=0.05)
    for z in (0.04, 0.12):
        rib = K.box("rib", (L + 0.006, D + 0.006, 0.012), center=(0, 0, z), bevel=0.003)
        ctx.add(rib, paint, uv_scale=2.0, patches=0.6, edge=1.8)
    lid = [ctx.add(K.box("lid", (L + 0.01, D + 0.01, 0.028), center=(0, 0, H + 0.014), bevel=0.006), paint, uv_scale=2.0,
                   patches=0.6, edge=1.6)]
    hd = K.tube("handle", [(-0.07, 0.0, H + 0.03), (-0.06, 0.0, H + 0.037), (0.06, 0.0, H + 0.037), (0.07, 0.0, H + 0.03)],
                0.005, segs=5)
    lid.append(ctx.add(hd, "chrome_pitted", uv_scale=2.0, smooth=40))
    lever = K.box("lever", (0.012, 0.06, 0.12), center=(-L / 2 - 0.012, 0, H - 0.04), bevel=0.003)
    ctx.add(lever, paint, uv_scale=2.0, patches=0.7, edge=1.8)
    hinge = K.cyl("hinge", 0.006, L - 0.04, segs=6, axis="X", center=(0, D / 2 + 0.004, H))
    ctx.add(hinge, paint, uv_scale=2.0, smooth=40)
    if ctx.destroyed:
        _rot_about(lid, (0, D / 2, H), (0, 0, 0))
        _move(lid, (0, 0, -H))
        _rot_about(lid, (0, 0, 0), (180, 0, 30))
        _move(lid, (0.25, -0.15, 0.04))
    elif ctx.worn:
        _rot_about(lid, (0, D / 2 + 0.004, H), (-24, 0, 0))
    ctx.col_box((-L / 2 - 0.02, -D / 2, 0), (L / 2, D / 2, H + 0.04))


def wild_safe_floor(ctx: K.Ctx) -> None:
    """The foreman's floor safe: heavy rounded steel body on a plinth with casters, inset door
    with a brass pinstripe, combination dial, three-spoke handle and barrel hinges.
    Destroyed: the door has been jemmied open on an empty shelf."""
    r = ctx.rnd("safe")
    Wd, D, H = 0.62, 0.6, 0.9
    paint = "steel_safe_black"
    body = K.box("body", (Wd, D, H - 0.07), center=(0, 0, 0.07 + (H - 0.07) / 2), bevel=0.03, bevel_segs=2, cuts=(1, 1, 2))
    ctx.add(body, paint, uv_scale=1.0, patches=0.6, edge=1.3)
    plinth = K.box("plinth", (Wd + 0.03, D + 0.03, 0.05), center=(0, 0, 0.045), bevel=0.008)
    ctx.add(plinth, paint, uv_scale=1.0, patches=0.7, low=0.8, low_h=0.1)
    for sx in (-1, 1):
        for sy in (-1, 1):
            cw = K.cyl("caster", 0.022, 0.018, segs=10, axis="X", center=(sx * (Wd / 2 - 0.04), sy * (D / 2 - 0.04), 0.022))
            ctx.add(cw, "wild_cast_iron", uv_scale=2.0, smooth=40)
    dy = -D / 2 - 0.004
    if ctx.destroyed:
        cav = K.box("cavity", (Wd - 0.12, 0.01, H - 0.24), center=(0, dy + 0.012, 0.07 + (H - 0.07) / 2))
        ctx.add(cav, "paint_black", uv_scale=1.0, wear=0.2)
        shelf = K.box("shelf", (Wd - 0.12, 0.08, 0.012), center=(0, dy - 0.02, 0.5))
        ctx.add(shelf, paint, uv_scale=1.0)
    door = [ctx.add(K.box("door", (Wd - 0.1, 0.05, H - 0.22), center=(0, dy - 0.02, 0.07 + (H - 0.07) / 2), bevel=0.012),
                    paint, uv_scale=1.0, patches=0.6, edge=1.5)]
    zc = 0.07 + (H - 0.07) / 2
    fw, fh = Wd - 0.2, H - 0.32
    for a, b in (((-fw / 2, zc - fh / 2), (fw / 2, zc - fh / 2)), ((-fw / 2, zc + fh / 2), (fw / 2, zc + fh / 2)),
                 ((-fw / 2, zc - fh / 2), (-fw / 2, zc + fh / 2)), ((fw / 2, zc - fh / 2), (fw / 2, zc + fh / 2))):
        door.append(W.bar(ctx, "pin", (a[0], dy - 0.046, a[1]), (b[0], dy - 0.046, b[1]), 0.006, 0.002, "furn_brass",
                          up=(0, -1, 0)))
    dial = K.cyl("dial", 0.05, 0.025, segs=24, axis="Y", center=(0.06, dy - 0.058, zc + 0.12))
    door.append(ctx.add(dial, "furn_brass", uv_scale=2.0, smooth=40, patches=0.4))
    ring = W.ring_obj("dialring", 0.052, 0.062, 0.01, segs=24)
    K.place(ring, (0.06, dy - 0.05, zc + 0.12), (90, 0, 0))
    door.append(ctx.add(ring, "chrome_pitted", uv_scale=2.0, smooth=40))
    hub = K.cyl("hub", 0.022, 0.04, segs=10, axis="Y", center=(0.06, dy - 0.064, zc - 0.08))
    door.append(ctx.add(hub, "chrome_pitted", uv_scale=2.0, smooth=40))
    for k in range(3):
        a = math.radians(90 + 120 * k)
        p0 = Vector((0.06, dy - 0.07, zc - 0.08))
        p1 = p0 + Vector((math.cos(a), 0, math.sin(a))) * 0.08
        door.append(W.rod(ctx, f"spoke{k}", p0, p1, 0.007, "chrome_pitted", segs=6))
        ball = K.blob("ball", 0.014, subdiv=1, center=tuple(p1))
        door.append(ctx.add(ball, "chrome_pitted", uv_scale=2.0, smooth=50))
    for zz in (zc - 0.2, zc + 0.2):
        h = K.cyl("hinge", 0.018, 0.09, segs=10, center=(-Wd / 2 + 0.035, dy - 0.02, zz))
        ctx.add(h, paint, uv_scale=2.0, smooth=40, patches=0.6)
    if ctx.destroyed:
        _rot_about(door, (-Wd / 2 + 0.035, dy - 0.02, 0), (0, 0, -68))
        scars = K.box("scar", (0.012, 0.01, 0.25), center=(Wd / 2 - 0.06, dy - 0.004, zc))
        ctx.add(scars, "chrome_pitted", uv_scale=2.0)
    ctx.col_box((-Wd / 2 - 0.02, -D / 2 - 0.06, 0), (Wd / 2 + 0.02, D / 2 + 0.02, H))


# ============================================================================================
# Canvas cot
# ============================================================================================

def wild_cot_canvas(ctx: K.Ctx) -> None:
    """Folding canvas camp cot: two wooden side poles, sagging olive canvas, three pairs of
    crossed steel legs, end stretchers, a folded wool blanket at the foot.
    Destroyed: canvas split down the middle and the head end collapsed to the floor."""
    r = ctx.rnd("cot")
    L, Wd, H = 1.9, 0.66, 0.42
    parts = []
    for sy in (-1, 1):
        parts.append(W.rod(ctx, f"pole{sy}", (-L / 2, sy * Wd / 2, H), (L / 2, sy * Wd / 2, H), 0.017, "wood_stained", segs=8,
                           patches=0.5))
    for sx in (-1, 1):
        parts.append(W.rod(ctx, f"end{sx}", (sx * (L / 2 - 0.04), -Wd / 2, H - 0.005), (sx * (L / 2 - 0.04), Wd / 2, H - 0.005),
                           0.01, "paint_olive", segs=6))
    can = K.grid("canvas", L - 0.1, Wd + 0.04, 14, 6)
    K.uv_planar(can, 2, scale=1.0)
    sag = 0.06 if not ctx.destroyed else 0.1

    def cshape(co):
        u = co.x / ((L - 0.1) / 2)
        v = co.y / ((Wd + 0.04) / 2)
        z = H - sag * (1 - u ** 4) * (1 - v * v) + 0.012
        y = co.y
        if abs(v) > 0.92:  # wraps over the poles
            y = math.copysign(Wd / 2 + 0.005, co.y)
            z = H + 0.016
        return Vector((co.x, y, z))
    K.map_verts(can, cshape)
    if ctx.destroyed:
        K.jagged_hole(can, (0.1, 0.0, H), 0.22, r.randint(0, 999), axis=2, jag=0.5)
    K.crumple(can, 0.006, scale=6.0, seed=r.randint(0, 999))
    K.solidify(can, 0.003, even=False)
    parts.append(ctx.add(can, "canvas_olive", uv=None, smooth=60, patches=0.0, edge=0.3))
    for k, x in enumerate((-0.72, 0.0, 0.72)):
        for sy in (-1, 1):
            parts.append(W.rod(ctx, f"leg{k}{sy}", (x, -sy * (Wd / 2 - 0.02), 0.01), (x, sy * (Wd / 2 - 0.01), H - 0.02), 0.008,
                               "paint_olive", segs=5))
        bolt = K.cyl("pivot", 0.012, 0.03, segs=8, axis="X", center=(x, 0, H / 2))
        parts.append(ctx.add(bolt, "chrome_pitted", uv_scale=2.0, smooth=40))
    bl = K.box("blanket", (0.42, Wd - 0.06, 0.07), center=(L / 2 - 0.3, 0, H - 0.01), bevel=0.025, bevel_segs=2,
               cuts=(2, 2, 1))
    K.noise_disp(bl, 0.01, scale=4.0, seed=r.randint(0, 99))
    parts.append(ctx.add(bl, "wild_wool_grey", uv_scale=1.0, smooth=50, patches=0.0))
    if ctx.destroyed:
        _rot_about(parts, (L / 2, 0, 0.0), (0, -12, 0))
        lo = min(min(v.co.z for v in o.data.vertices) for o in parts)
        _move(parts, (0, 0, -lo))
    ctx.col_box((-L / 2, -Wd / 2 - 0.02, 0), (L / 2, Wd / 2 + 0.02, H + 0.05))


# ============================================================================================
# Kerosene lanterns
# ============================================================================================

def _lantern(ctx, *, hanging=False):
    """Tubular hurricane lantern built upright with its base at z = 0; returns (parts, glass)."""
    paint = "paint_red"
    parts = []
    fount = K.lathe("fount", [(0.0, 0.0), (0.072, 0.0), (0.078, 0.008), (0.078, 0.042), (0.07, 0.056), (0.035, 0.066),
                              (0.0, 0.066)], segs=16)
    if ctx.worn:
        K.dent(fount, (0.07, -0.03, 0.03), 0.04, 0.008)
    parts.append(ctx.add(fount, paint, uv_scale=2.0, smooth=45, patches=0.6, edge=1.4))
    parts.append(ctx.add(K.cyl("filler", 0.012, 0.012, segs=8, center=(0.048, 0.0, 0.066)), "furn_brass", uv_scale=2.0,
                         smooth=40))
    burner = K.lathe("burner", [(0.0, 0.064), (0.034, 0.064), (0.036, 0.078), (0.046, 0.086), (0.046, 0.092), (0.0, 0.092)],
                     segs=12)
    parts.append(ctx.add(burner, "furn_brass", uv_scale=2.0, smooth=40, patches=0.5))
    parts.append(ctx.add(K.cyl("wick", 0.009, 0.012, segs=8, axis="Y", center=(0.026, -0.04, 0.075)), "furn_brass",
                         uv_scale=2.0, smooth=40))
    glass = []
    if not ctx.destroyed:
        globe = K.lathe("globe", [(0.0, 0.092), (0.034, 0.092), (0.05, 0.115), (0.058, 0.15), (0.056, 0.186), (0.046, 0.21),
                                  (0.031, 0.228), (0.0, 0.228)], segs=14)
        # Clear globe: the flame inside (drawn only while the lantern burns) shows through it.
        glass.append(ctx.add(globe, "glass_clear", uv_scale=1.0, smooth=50, wear=0.0, ao=False))
        flame = K.blob("flame", 0.011, subdiv=1, scale=(1.0, 1.0, 1.9), center=(0.0, 0.0, 0.113))
        glass.append(ctx.add(flame, "flame_glow", uv_scale=1.0, smooth=50, wear=0.0, ao=False))
    for k in range(4):
        a = math.tau * k / 4 + math.pi / 4
        pts = [(rr * math.cos(a), rr * math.sin(a), z) for z, rr in ((0.094, 0.045), (0.13, 0.066), (0.17, 0.072),
                                                                      (0.205, 0.062), (0.228, 0.046))]
        parts.append(ctx.add(K.tube("guard", pts, 0.0022, segs=4), "metal_galvanized", uv_scale=2.0, smooth=40))
    for z, rr in ((0.15, 0.07), (0.205, 0.063)):
        ring = K.tube("gring", [(rr * math.cos(t), rr * math.sin(t), z) for t in [i * math.tau / 16 for i in range(16)]],
                      0.0022, segs=4, closed=True)
        parts.append(ctx.add(ring, "metal_galvanized", uv_scale=2.0, smooth=40))
    for sx in (-1, 1):
        tube = K.tube("airtube", [(sx * 0.074, 0.0, 0.05), (sx * 0.077, 0.0, 0.236), (sx * 0.062, 0.0, 0.258)], 0.0075,
                      segs=6)
        parts.append(ctx.add(tube, paint, uv_scale=2.0, smooth=45, patches=0.6))
    top = K.lathe("top", [(0.0, 0.228), (0.064, 0.236), (0.068, 0.246), (0.05, 0.258), (0.03, 0.272), (0.028, 0.285),
                          (0.0, 0.287)], segs=14)
    parts.append(ctx.add(top, paint, uv_scale=2.0, smooth=45, patches=0.6, edge=1.4))
    bail = K.tube("bail", [(-0.066 * math.cos(math.pi * k / 10), 0.0, 0.25 + 0.115 * math.sin(math.pi * k / 10))
                           for k in range(11)], 0.0025, segs=4)
    parts.append(ctx.add(bail, "metal_galvanized", uv_scale=2.0, smooth=40))
    if hanging:
        wire = K.tube("wire", [(0.0, 0.0, 0.365), (0.0, 0.0, 0.66)], 0.002, segs=4)
        parts.append(ctx.add(wire, "metal_galvanized", uv_scale=2.0))
        hook = K.tube("hook", [(0.0, 0.0, 0.66)] + [(0.022 * math.sin(math.pi * k / 6), 0.0, 0.682 - 0.022 * math.cos(math.pi * k / 6))
                                                     for k in range(1, 8)] + [(-0.012, 0.0, 0.69)], 0.003, segs=4)
        parts.append(ctx.add(hook, "metal_galvanized", uv_scale=2.0, smooth=40))
    return parts, glass


def _shards(ctx, r, n, spread=0.25):
    for k in range(n):
        s = r.uniform(0.008, 0.026)
        pts = [(math.cos(a) * s * r.uniform(0.5, 1.0), math.sin(a) * s * r.uniform(0.5, 1.0)) for a in
               [j * math.tau / 3 + r.uniform(-0.3, 0.3) for j in range(3)]]
        sh = K.prism(f"shard{k}", pts, 0.002, plane="XY")
        K.place(sh, (r.uniform(-spread, spread), r.uniform(-spread, spread * 0.5), 0.0), (0, 0, r.uniform(0, 360)))
        ctx.add(sh, "glass_clear", uv_scale=1.0, wear=0.0)


def wild_oil_lantern(ctx: K.Ctx) -> None:
    """Red tubular kerosene lantern: fount, brass burner and wick wheel, glass globe with a flame
    (both glow when the lantern is lit), wire guard, air tubes, chimney cap and bail.
    Worn: dented and rusty. Destroyed: knocked over, globe smashed across the floor."""
    r = ctx.rnd("lantern")
    parts, _glass = _lantern(ctx)
    if ctx.destroyed:
        _rot_about(parts, (0, 0, 0), (88, 0, 35))
        lo = min(min(v.co.z for v in o.data.vertices) for o in parts)
        _move(parts, (0, 0, -lo))
        _shards(ctx, r, 9)
    ctx.col_box((-0.08, -0.08, 0), (0.08, 0.08, 0.36))


def wild_oil_lantern_hanging(ctx: K.Ctx) -> None:
    """The same lantern hung from a wire and an S-hook (origin at the lantern's base; place it
    with a 'y' offset so the hook meets a beam or the ceiling)."""
    _lantern(ctx, hanging=True)


# ============================================================================================
# Wash stand, enamel dishes, firewood, boots
# ============================================================================================

def wild_washstand(ctx: K.Ctx) -> None:
    """Bunkhouse wash stand: plank top with splash board, lower shelf, towel rail, an enamel
    basin, a pitcher on the shelf, a cracked mirror and a bar of soap."""
    r = ctx.rnd("wash")
    L, D, H = 0.6, 0.42, 0.78
    wood = "wild_lumber_weathered"
    ctx.add(P.plank("top", L, D, 0.03, cuts=2), wood, long_axis=0, at=((0, 0, H - 0.015),), patches=0.6, edge=1.3)
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.bar(ctx, "leg", (sx * (L / 2 - 0.04), sy * (D / 2 - 0.04), 0.0), (sx * (L / 2 - 0.04), sy * (D / 2 - 0.04), H - 0.03),
                  0.04, 0.04, wood, low=0.6, low_h=0.2)
    ctx.add(P.plank("shelf", L - 0.06, D - 0.06, 0.02), wood, long_axis=0, at=((0, 0, 0.18),), patches=0.6)
    ctx.add(P.plank("splash", L, 0.02, 0.22), wood, long_axis=0, at=((0, D / 2 - 0.01, H + 0.11),), patches=0.6)
    W.rod(ctx, "towelbar", (L / 2 + 0.035, -0.15, H - 0.06), (L / 2 + 0.035, 0.15, H - 0.06), 0.009, "wood_stained", segs=6)
    for y in (-0.15, 0.15):
        W.bar(ctx, "tb", (L / 2, y, H - 0.06), (L / 2 + 0.04, y, H - 0.06), 0.02, 0.03, wood)
    basin = K.lathe("basin", [(0.0, 0.0), (0.08, 0.0), (0.12, 0.04), (0.16, 0.085), (0.175, 0.095), (0.17, 0.098),
                              (0.155, 0.088), (0.112, 0.046), (0.075, 0.008), (0.0, 0.008)], segs=20)
    K.place(basin, (0, -0.03, H))
    ctx.add(basin, "wild_enamel_white", uv_scale=1.5, smooth=50, patches=0.5, edge=1.4)
    pitcher = K.lathe("pitcher", [(0.0, 0.0), (0.07, 0.0), (0.075, 0.01), (0.08, 0.1), (0.06, 0.18), (0.065, 0.24),
                                  (0.06, 0.24), (0.055, 0.18), (0.074, 0.1), (0.069, 0.012), (0.0, 0.012)], segs=16)
    K.place(pitcher, (0.12, 0.02, 0.19))
    ctx.add(pitcher, "wild_enamel_white", uv_scale=1.5, smooth=50, patches=0.5, edge=1.4)
    ph = K.tube("ph", [(0.05, 0.02, 0.4), (0.0, 0.02, 0.38), (-0.005, 0.02, 0.3), (0.05, 0.02, 0.25)], 0.008, segs=5)
    ctx.add(ph, "wild_enamel_white", uv_scale=2.0, smooth=50)
    mirror = K.box("mirror", (0.2, 0.006, 0.16), center=(0, D / 2 - 0.024, H + 0.13))
    if not ctx.clean:
        K.cut_plane(mirror, (0.05, 0, H + 0.13), (0.7, 0.0, 0.7), keep="below")
    ctx.add(mirror, "mirror_dirty", uv_scale=1.0, wear=0.0)
    soap = K.box("soap", (0.08, 0.05, 0.025), center=(-0.2, -0.1, H + 0.0125), bevel=0.008)
    ctx.add(soap, "candle_wax", uv_scale=2.0, smooth=40)
    ctx.col_box((-L / 2, -D / 2, 0), (L / 2 + 0.05, D / 2, H + 0.22))


def wild_enamel_dishes(ctx: K.Ctx) -> None:
    """Granite-ware on a table: a stack of plates, cups, a coffee pot and a can of spoons
    (surface prop: place it with the table height as 'y')."""
    r = ctx.rnd("dishes")
    for k in range(4):
        _plate(ctx, r, r.uniform(-0.01, 0.01) - 0.1, r.uniform(-0.01, 0.01), 0.008 * k, "wild_enamel_white" if k % 2 else "wild_enamel_blue",
               rot=r.uniform(0, 360))
    _cup(ctx, r, 0.07, -0.08, 0.0, "wild_enamel_blue", rot=r.uniform(0, 360))
    _cup(ctx, r, 0.16, 0.0, 0.0, "wild_enamel_white", rot=r.uniform(0, 360), tipped=not ctx.clean)
    _coffee_pot(ctx, 0.1, 0.1, 0.0, "wild_enamel_blue", rot=r.uniform(0, 360), scale=0.85)
    tin = K.lathe("tin", [(0.0, 0.0), (0.035, 0.0), (0.035, 0.1), (0.0, 0.1)], segs=10)
    K.place(tin, (-0.14, 0.11, 0.0))
    ctx.add(tin, "furn_tin", uv="cyl", uv_scale=2.0, smooth=40, patches=0.6)
    for k in range(4):
        a = math.tau * k / 4 + 0.3
        W.rod(ctx, f"spoon{k}", (-0.14 + 0.01 * math.cos(a), 0.11 + 0.01 * math.sin(a), 0.02),
              (-0.14 + 0.04 * math.cos(a), 0.11 + 0.04 * math.sin(a), 0.17), 0.004, "furn_tin", segs=4)
    ctx.col_box((-0.25, -0.15, 0), (0.25, 0.2, 0.22))


def _split_piece(ctx, name, L, R, seed, kind, at, rot):
    """Split firewood: a half or quarter round with bark, end grain and fresh split faces."""
    o = W.log_obj(name, L, R, seed, sides=8, rings=2, taper=0.0, bow=0.0, cut_face=((0, 0, 1), 0.0 if kind == "half" else 0.0))
    if kind == "quarter":
        o2 = o
        K.cut_plane(o2, (0, 0, 0), (0, 1, 0), keep="below", fill=True)
        me = o2.data
        uvd = me.uv_layers.active.data
        for p in me.polygons:
            if p.normal.y > 0.95:
                p.material_index = 2
                for li in p.loop_indices:
                    co = me.vertices[me.loops[li].vertex_index].co
                    uvd[li].uv = (co.x, co.z)
    K.place(o, at, rot)
    return ctx.add(o, None, uv=None, smooth=None, patches=0.3, edge=0.8)


def wild_firewood_stack(ctx: K.Ctx) -> None:
    """Split fir stacked against a wall in three courses, end grain to the room."""
    r = ctx.rnd("firewood")
    k = 0
    for row, (n, z) in enumerate(((5, 0.0), (4, 0.15), (3, 0.29))):
        for i in range(n):
            x = -0.36 + (i + 0.5 * row) * 0.18 + r.uniform(-0.02, 0.02)
            R = r.uniform(0.07, 0.095)
            kind = "half" if r.random() < 0.6 else "quarter"
            _split_piece(ctx, f"fw{k}", r.uniform(0.36, 0.4), R, r.randint(0, 9999), kind,
                         (x, r.uniform(-0.02, 0.02), z + R * 0.75), (r.uniform(-180, 180), 0, 90 + r.uniform(-6, 6)))
            k += 1
    ctx.col_box((-0.45, -0.21, 0), (0.45, 0.21, 0.45))


def _boot_ring(z, yf, yb, wx, n=18):
    """Horizontal section of a boot at height z: an egg outline from the toe (yf, -Y) to the
    heel (yb), widest toward the ball of the foot."""
    mid, half = (yf + yb) / 2, (yb - yf) / 2
    pts = []
    for i in range(n):
        t = math.tau * i / n
        s_ = math.sin(t)
        x = wx * math.cos(t) * (1.0 + 0.16 * max(0.0, -s_))
        pts.append((x, mid + half * s_, z))
    return pts


# Boot sections (z, toe y, heel y, half width): sole top, toe box, instep, ankle, shaft, flared top.
_BOOT_LEVELS = [(0.022, -0.165, 0.135, 0.05), (0.045, -0.166, 0.137, 0.053), (0.068, -0.152, 0.138, 0.052),
                (0.088, -0.118, 0.137, 0.049), (0.108, -0.07, 0.133, 0.047), (0.132, -0.025, 0.128, 0.046),
                (0.17, -0.004, 0.124, 0.046), (0.25, 0.0, 0.122, 0.049), (0.33, -0.006, 0.126, 0.053),
                (0.37, -0.01, 0.128, 0.055)]


def _boot(ctx, r, name):
    """A tall laced logger's boot standing at the origin, toe toward -Y."""
    parts = []
    rings = [_boot_ring(*lv) for lv in _BOOT_LEVELS]
    upper = K.loft(name + "upper", rings, cap_start=True, cap_end=False)
    K.solidify(upper, 0.005, even=False)
    parts.append(ctx.add(upper, "leather_dark", uv="cyl", uv_scale=2.0, smooth=55, patches=0.35, edge=0.6, low=0.6, low_h=0.1))
    collar = K.tube(name + "collar", [p for p in _boot_ring(0.366, -0.012, 0.13, 0.057)], 0.006, segs=5, closed=True)
    parts.append(ctx.add(collar, "item_leather", uv_scale=2.0, smooth=50))
    # Sole (with a stacked heel) following the footprint, a welt line around it.
    base = _boot_ring(0.0, -0.172, 0.142, 0.054)
    sole = K.loft(name + "sole", [base, [(x, y, 0.024) for x, y, _ in base]])
    parts.append(ctx.add(sole, "rubber_black", uv_scale=2.0, smooth=40, patches=0.3))
    heel = K.loft(name + "heel", [_boot_ring(-0.025, 0.05, 0.142, 0.045, 12), _boot_ring(0.001, 0.05, 0.142, 0.045, 12)])
    parts.append(ctx.add(heel, "rubber_black", uv_scale=2.0, smooth=40))
    # Lacing up the front: zigzag between two rows of hooks.
    def front_y(z):
        for (z0, y0, _b0, _w0), (z1, y1, _b1, _w1) in zip(_BOOT_LEVELS, _BOOT_LEVELS[1:]):
            if z0 <= z <= z1:
                return y0 + (y1 - y0) * (z - z0) / (z1 - z0)
        return _BOOT_LEVELS[-1][1]
    lace_pts, hooks = [], []
    for k in range(12):
        z = 0.1 + k * 0.022
        x = 0.022 * (1 if k % 2 else -1)
        lace_pts.append((x, front_y(z) + 0.012 - 0.004, z))
        hooks.append((x * 1.15, front_y(z) + 0.012, z))
    lace = K.tube(name + "lace", lace_pts, 0.004, segs=4)
    parts.append(ctx.add(lace, "item_leather", uv_scale=2.0, smooth=40))
    for k, hp in enumerate(hooks):
        hk = K.cyl(name + f"hook{k}", 0.004, 0.008, segs=6, axis="Y", center=(hp[0], hp[1] - 0.004, hp[2]))
        parts.append(ctx.add(hk, "chrome_pitted", uv_scale=2.0))
    pull = K.tube(name + "pull", [(0.0, 0.126, 0.33), (0.0, 0.14, 0.38), (0.0, 0.126, 0.4)], 0.006, segs=5, flat=(1.0, 0.4))
    parts.append(ctx.add(pull, "item_leather", uv_scale=2.0, smooth=40))
    return parts


def wild_caulk_boots(ctx: K.Ctx) -> None:
    """A pair of tall calked logging boots: one standing, one fallen on its side."""
    r = ctx.rnd("boots")
    a = _boot(ctx, r, "a")
    _move(a, (-0.08, 0.0, 0.0))
    b = _boot(ctx, r, "b")
    _rot_about(b, (0, 0, 0), (0, 82, 0))
    _rot_about(b, (0, 0, 0), (0, 0, 35))
    lo = min(min(v.co.z for v in o.data.vertices) for o in b)
    _move(b, (0.17, 0.02, -lo))
    ctx.col_box((-0.2, -0.2, 0), (0.25, 0.2, 0.36))


# ============================================================================================
# Lookout: fire finder, radio set
# ============================================================================================

def _uv_disc(obj, radius, uv_r=W.MAP_DISC_R):
    me = obj.data
    uvl = me.uv_layers.active if me.uv_layers else me.uv_layers.new(name="UVMap")
    k = uv_r / radius
    for li, loop in enumerate(me.loops):
        co = me.vertices[loop.vertex_index].co
        uvl.data[li].uv = (0.5 + co.x * k, 0.5 + co.y * k)


def wild_fire_finder(ctx: K.Ctx) -> None:
    """Osborne-type fire finder on its four-legged stand: round table with the map disc (contour
    map, degree ring, pencilled bearings), the brass azimuth ring with a front sight (hair wire in
    a frame) and a rear peep sight, two ring handles. Worn: tarnished, the map water-stained."""
    r = ctx.rnd("finder")
    H = 1.1
    wood = "wood_stained"
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.bar(ctx, "leg", (sx * 0.3, sy * 0.3, 0.0), (sx * 0.19, sy * 0.19, H - 0.05), 0.055, 0.055, wood, bevel=0.004,
                  low=0.5, low_h=0.3)
    for z, s in ((0.28, 0.27), (0.82, 0.215)):
        for a, b in (((-s, -s), (s, -s)), ((s, -s), (s, s)), ((s, s), (-s, s)), ((-s, s), (-s, -s))):
            W.bar(ctx, "rail", (a[0], a[1], z), (b[0], b[1], z), 0.035, 0.05, wood, ext=0.02)
    apron = K.cyl("apron", 0.3, 0.06, segs=24, center=(0, 0, H - 0.07))
    ctx.add(apron, wood, uv="cyl", uv_scale=1.0, smooth=40, patches=0.5)
    table = K.cyl("table", 0.44, 0.04, segs=36, center=(0, 0, H - 0.02))
    ctx.add(table, wood, uv_scale=1.0, smooth=35, patches=0.5, edge=1.3)
    disc = K.cyl("map", 0.39, 0.004, segs=48, center=(0, 0, H + 0.002))
    _uv_disc(disc, 0.39)
    ctx.add(disc, "wild_map_disc", uv=None, smooth=None, wear=0.0 if ctx.clean else 0.4, patches=0.0, edge=0.0)
    ring = W.ring_obj("azimuth", 0.392, 0.428, 0.012, segs=48, bevel=0.003)
    K.place(ring, (0, 0, H + 0.008))
    ctx.add(ring, "furn_brass", uv_scale=2.0, smooth=40, patches=0.5, edge=1.4)
    ang = math.radians(r.uniform(0, 360))
    ca, sa = math.cos(ang), math.sin(ang)

    def at(rad, z, along=0.0):
        return Vector((ca * rad - sa * along, sa * rad + ca * along, z))
    base = K.box("fbase", (0.05, 0.05, 0.015), center=(0, 0, 0.0075))
    K.place(base, at(0.41, H + 0.014), (0, 0, math.degrees(ang)))
    ctx.add(base, "furn_brass", uv_scale=2.0)
    for s in (-1, 1):
        W.bar(ctx, "fpost", at(0.41, H + 0.02, s * 0.02), at(0.41, H + 0.21, s * 0.02), 0.006, 0.006, "furn_brass")
    W.bar(ctx, "ftop", at(0.41, H + 0.21, -0.023), at(0.41, H + 0.21, 0.023), 0.008, 0.006, "furn_brass")
    W.rod(ctx, "hair", at(0.41, H + 0.025, 0.0), at(0.41, H + 0.205, 0.0), 0.0008, "chrome_pitted", segs=3)
    rb = K.box("rbase", (0.05, 0.05, 0.015), center=(0, 0, 0.0075))
    K.place(rb, at(-0.41, H + 0.014), (0, 0, math.degrees(ang)))
    ctx.add(rb, "furn_brass", uv_scale=2.0)
    peep = K.box("peep", (0.004, 0.045, 0.12), center=(0, 0, 0.06))
    K.place(peep, at(-0.41, H + 0.02), (0, 0, math.degrees(ang)))
    ctx.add(peep, "furn_brass", uv_scale=2.0, patches=0.5)
    hole = W.ring_obj("peephole", 0.004, 0.009, 0.006, segs=10)
    K.place(hole, rot=(0, 90, 0))
    K.place(hole, at(-0.412, H + 0.12), (0, 0, math.degrees(ang)))
    ctx.add(hole, "chrome_pitted", uv_scale=2.0)
    for s in (-1, 1):
        kn = K.cyl("handle", 0.012, 0.035, segs=8, center=(0, 0, 0.0175))
        K.place(kn, at(0.0, H + 0.014, s * 0.41))
        ctx.add(kn, "wood_stained", uv_scale=2.0, smooth=40)
    ctx.col_box((-0.45, -0.45, 0), (0.45, 0.45, H + 0.04))


def _helix_cord(a, b, n=56, turns=14, rad=0.008):
    a, b = Vector(a), Vector(b)
    d = (b - a)
    t = d.normalized()
    p1 = t.orthogonal().normalized()
    p2 = t.cross(p1).normalized()
    pts = []
    for i in range(n + 1):
        s = i / n
        sag = Vector((0, 0, -0.04 * math.sin(math.pi * s)))
        ang = math.tau * turns * s
        pts.append(a + d * s + sag + (p1 * math.cos(ang) + p2 * math.sin(ang)) * rad)
    return pts


def wild_radio_set(ctx: K.Ctx) -> None:
    """Forestry base-station transceiver on a desk: grey case with a dial window, meter, speaker
    grille and switch plate on the front panel, three knobs and toggles, front handles, a palm
    microphone on a coiled cord, a power supply and the antenna coax leading off the back.
    Surface prop (place it at the desk height with 'y'). Destroyed: case caved in, mic gone."""
    r = ctx.rnd("radio")
    ctx.ground_clamp = False
    L, D, H = 0.44, 0.3, 0.16
    case = K.box("case", (L, D, H), center=(0, 0.0, H / 2 + 0.012), bevel=0.008, cuts=(1, 1, 0))
    if ctx.destroyed:
        K.dent(case, (0.05, 0.0, H + 0.012), 0.16, 0.04)
    ctx.add(case, "wild_paint_mill_grey", uv_scale=1.5, patches=0.3, edge=0.6)
    panel = K.box("panel", (L - 0.012, 0.006, H - 0.012), center=(0, -D / 2 - 0.003, H / 2 + 0.012))
    ctx.add(panel, "wild_radio_face", uv="planar", uv_axis=1, rect=W.RADIO_RECT, patches=0.0, edge=0.5)
    fy = -D / 2 - 0.006

    def panel_xz(fu, fv):
        return -L / 2 + 0.006 + fu * (L - 0.012), 0.012 + 0.006 + (1.0 - fv) * (H - 0.012)
    for fu in (0.12, 0.27, 0.42):
        x, z = panel_xz(fu, 0.76)
        sk = K.cyl("skirt", 0.02, 0.005, segs=14, axis="Y", center=(x, fy - 0.0025, z))
        ctx.add(sk, "plastic_black", uv_scale=2.0, smooth=40)
        kn = K.cyl("knob", 0.014, 0.022, segs=12, axis="Y", center=(x, fy - 0.016, z), r_top=0.012)
        ctx.add(kn, "plastic_black", uv_scale=2.0, smooth=40, patches=0.3)
    for fu in (0.6, 0.66, 0.72):
        x, z = panel_xz(fu, 0.74)
        W.rod(ctx, "toggle", (x, fy, z), (x, fy - 0.022, z + 0.008), 0.0025, "chrome_pitted", segs=5)
    for sx in (-1, 1):
        hd = K.tube("fhandle", [(sx * (L / 2 - 0.012), fy, 0.03), (sx * (L / 2 - 0.012), fy - 0.03, 0.04),
                                (sx * (L / 2 - 0.012), fy - 0.03, 0.14), (sx * (L / 2 - 0.012), fy, 0.15)], 0.006, segs=6)
        ctx.add(hd, "chrome_pitted", uv_scale=2.0, smooth=40)
    for sx in (-1, 1):
        for sy in (-1, 1):
            ft = K.cyl("foot", 0.012, 0.012, segs=8, center=(sx * (L / 2 - 0.03), sy * (D / 2 - 0.03), 0.006))
            ctx.add(ft, "rubber_black", uv_scale=2.0, smooth=40)
    psu = K.box("psu", (0.14, 0.2, 0.11), center=(L / 2 + 0.11, 0.03, 0.055), bevel=0.006)
    ctx.add(psu, "paint_black", uv_scale=1.5, patches=0.6, edge=1.3)
    for k in range(6):
        sl = K.box("vent", (0.002, 0.12, 0.006), center=(L / 2 + 0.04 - 0.0 + 0.0, 0.03, 0.03 + k * 0.013))
        K.place(sl, (0.14 + 0.001, 0, 0))
        ctx.add(sl, "plastic_black", uv_scale=2.0)
    pl = K.cyl("pilot", 0.006, 0.006, segs=8, axis="Y", center=(L / 2 + 0.15, -0.07 - 0.003, 0.08))
    ctx.add(pl, "lens_red", uv_scale=2.0, smooth=40)
    cable = K.tube("pwr", [(L / 2 + 0.11, 0.13, 0.03), (L / 2 + 0.08, 0.2, 0.02), (L / 2 - 0.05, 0.19, 0.02), (L / 2 - 0.08, D / 2, 0.05)],
                   0.004, segs=5)
    ctx.add(cable, "rubber_black", uv_scale=2.0, smooth=50)
    coax = K.tube("coax", [(-0.1, D / 2, 0.1), (-0.11, D / 2 + 0.06, 0.08), (-0.14, D / 2 + 0.1, 0.0), (-0.17, D / 2 + 0.11, -0.3)],
                  0.005, segs=5)
    ctx.add(coax, "rubber_black", uv_scale=2.0, smooth=50)
    if not ctx.destroyed:
        mic = K.box("mic", (0.06, 0.035, 0.09), center=(0, 0, 0.0), bevel=0.014, bevel_segs=2)
        K.place(mic, rot=(90, 0, 0))
        K.place(mic, (0.24, -0.26, 0.0175), (0, 0, r.uniform(-30, 30)))
        ctx.add(mic, "plastic_black", uv_scale=2.0, smooth=50, patches=0.3)
        ptt = K.box("ptt", (0.008, 0.03, 0.012), center=(0.27, -0.26, 0.035))
        ctx.add(ptt, "rubber_black", uv_scale=2.0)
        cord = K.tube("cord", _helix_cord((0.24, -0.22, 0.02), (0.15, fy, 0.03)), 0.0022, segs=4)
        ctx.add(cord, "plastic_black", uv_scale=2.0, smooth=50)
    ctx.col_box((-L / 2, -D / 2 - 0.04, 0), (L / 2 + 0.19, D / 2, H + 0.02))
    _move(ctx.parts + ctx.cols, (-0.095, 0.0, 0.0))  # centre the footprint (power supply on the right)


# ============================================================================================
# Cabin walls: gun rack, pelt board, crosscut saw; loose trap
# ============================================================================================

def _long_gun(ctx, x, z0, kind, lean=0.0):
    """Long gun standing butt-down in the rack, side to the room (-Y), barrel up."""
    parts = []
    stock = [(-0.055, 0.0), (0.06, 0.0), (0.05, 0.03), (0.025, 0.25), (0.02, 0.33), (0.022, 0.62 if kind == "rifle" else 0.5),
             (0.012, 0.66 if kind == "rifle" else 0.54), (-0.012, 0.66 if kind == "rifle" else 0.54), (-0.018, 0.4),
             (-0.025, 0.3), (-0.05, 0.08)]
    st = K.prism("stock", stock, 0.04, plane="XZ")
    parts.append(ctx.add(st, "item_wood_handle", uv_scale=2.0, patches=0.5, edge=1.3))
    bp = K.box("buttplate", (0.12, 0.042, 0.008), center=(0.0, 0.0, 0.004))
    parts.append(ctx.add(bp, "rubber_black", uv_scale=2.0))
    if kind == "rifle":
        parts.append(ctx.add(K.box("receiver", (0.03, 0.03, 0.18), center=(0.0, 0.0, 0.42), bevel=0.004), "item_steel_dark",
                             uv_scale=2.0, patches=0.5))
        parts.append(W.rod(ctx, "barrel", (0.0, 0.0, 0.5), (0.0, 0.0, 1.08), 0.0095, "item_steel_dark", r2=0.008, segs=8))
        parts.append(W.rod(ctx, "bolt", (0.0, -0.016, 0.47), (0.0, -0.06, 0.45), 0.004, "item_steel_dark", segs=5))
        parts.append(ctx.add(K.blob("knob", 0.009, subdiv=1, center=(0.0, -0.062, 0.45)), "item_steel_dark", uv_scale=2.0,
                             smooth=50))
        parts.append(ctx.add(K.box("scope", (0.03, 0.03, 0.02), center=(0.0, 0.0, 1.06)), "item_steel_dark", uv_scale=2.0))
    else:
        parts.append(ctx.add(K.box("action", (0.035, 0.034, 0.12), center=(0.0, 0.0, 0.4), bevel=0.006), "item_steel_dark",
                             uv_scale=2.0, patches=0.5))
        for s in (-1, 1):
            parts.append(W.rod(ctx, f"bbl{s}", (s * 0.0095, 0.0, 0.46), (s * 0.0095, 0.0, 1.12), 0.0095, "item_steel_dark", segs=8))
        parts.append(ctx.add(K.box("foreend", (0.026, 0.036, 0.16), center=(0.0, 0.0, 0.56), bevel=0.006), "item_wood_handle",
                             uv_scale=2.0))
    if lean:
        _rot_about(parts, (0, 0, 0), (0, lean, 0))
    _move(parts, (x, -0.075, z0))
    return parts


def wild_gun_rack(ctx: K.Ctx) -> None:
    """Wall gun rack: stained back board, a butt rest with three cups and a notched barrel bar.
    Clean: a bolt rifle and a side-by-side shotgun, one slot empty. Worn: only the shotgun is
    left. Destroyed: barrel bar split off, rack empty. Wall prop (origin on the wall plane)."""
    r = ctx.rnd("gunrack")
    wood = "wood_stained"
    ctx.add(K.box("back", (0.9, 0.022, 1.0), center=(0, -0.011, 0.5), bevel=0.006), wood, uv_scale=1.0, patches=0.5,
            edge=1.3)
    rest = K.box("rest", (0.86, 0.13, 0.06), center=(0, -0.075, 0.12), bevel=0.008)
    ctx.add(rest, wood, long_axis=0, patches=0.5, edge=1.4)
    for x in (-0.28, 0.0, 0.28):
        cup = K.box("cup", (0.1, 0.11, 0.03), center=(x, -0.08, 0.165), bevel=0.01)
        ctx.add(cup, "leather_dark", uv_scale=2.0, smooth=40)
    top_parts = []
    xs = [-0.43, -0.33, -0.23, -0.05, 0.05, 0.23, 0.33, 0.43]
    for a, b in ((xs[0], xs[1]), (xs[2], xs[3]), (xs[4], xs[5]), (xs[6], xs[7])):
        top_parts.append(ctx.add(K.box("bar", (b - a, 0.1, 0.05), center=((a + b) / 2, -0.06, 0.86), bevel=0.006), wood,
                                 long_axis=0, patches=0.5, edge=1.4))
    for x in (-0.38, 0.38):
        top_parts.append(W.bolts(ctx, "lag", [((x, -0.11, 0.86), (0, -1, 0))], "chrome_pitted", r=0.009, h=0.006))
    if ctx.clean:
        _long_gun(ctx, -0.28, 0.135, "rifle")
        _long_gun(ctx, 0.0, 0.135, "shotgun")
    elif not ctx.destroyed:
        _long_gun(ctx, 0.0, 0.135, "shotgun", lean=4)
    else:
        _rot_about(top_parts, (0.43, -0.01, 0.86), (0, 32, 0))
    shells = K.box("shells", (0.1, 0.06, 0.05), center=(0.33, -0.1, 0.175), bevel=0.003)
    ctx.add(shells, "cardboard", uv_scale=2.0, patches=0.6)
    ctx.col_box((-0.45, -0.15, 0.08), (0.45, 0.0, 1.0))


def _leg_trap(ctx, *, sprung=False, chain_len=0.3, seed=0):
    """Double long-spring leg-hold trap lying flat at the origin (jaws open unless sprung);
    returns its registered parts. Chain runs off toward -Y to a ring."""
    import random as _r
    rr = _r.Random(seed)
    steel = "item_iron_strap"
    parts = []
    parts.append(W.bar(ctx, "base", (-0.075, 0, 0.004), (0.075, 0, 0.004), 0.022, 0.006, steel))
    parts.append(W.bar(ctx, "cross", (0, -0.05, 0.004), (0, 0.05, 0.004), 0.018, 0.006, steel))
    jr = 0.062
    for s in (-1, 1):
        if sprung:
            pts = [(jr * math.cos(a), s * 0.003, 0.012 + jr * math.sin(a)) for a in [math.pi * k / 10 for k in range(11)]]
        else:
            pts = [(jr * math.cos(a), s * jr * math.sin(a), 0.01) for a in [math.pi * k / 10 for k in range(11)]]
        parts.append(ctx.add(K.tube(f"jaw{s}", pts, 0.0055, segs=6), steel, uv_scale=3.0, smooth=40, patches=0.7))
    parts.append(ctx.add(K.cyl("pan", 0.034, 0.004, segs=14, center=(0, 0, 0.014)), steel, uv_scale=3.0, smooth=40))
    parts.append(W.bar(ctx, "dog", (0, 0.0, 0.016), (0, 0.06 if not sprung else 0.02, 0.012), 0.008, 0.003, steel))
    # Long springs: a flat leaf folded back on itself at the far end (tight bend), the upper leaf
    # ending in an eye around the jaw posts. Set: pressed flat; sprung: the eye rides up the jaws.
    eye_z = 0.05 if sprung else 0.014
    for sx in (-1, 1):
        x0, x1, br = sx * 0.07, sx * 0.2, 0.009
        parts.append(W.bar(ctx, f"leafl{sx}", (x0, 0.0, 0.004), (x1, 0.0, 0.004), 0.02, 0.005, steel, patches=0.6))
        prev = None
        for k in range(7):
            ang = -math.pi / 2 + math.pi * k / 6
            pt = (x1 + sx * br * math.cos(ang), 0.0, 0.004 + br + br * math.sin(ang))
            if prev is not None:
                mid = ((prev[0] + pt[0]) / 2 - x1, (prev[2] + pt[2]) / 2 - 0.004 - br)
                parts.append(W.bar(ctx, f"bend{sx}{k}", prev, pt, 0.02, 0.005, steel, up=(mid[0], 0.0, mid[1]), ext=0.001))
            prev = pt
        parts.append(W.bar(ctx, f"leafu{sx}", prev, (sx * 0.085, 0.0, eye_z), 0.02, 0.005, steel, patches=0.6))
        eye = W.ring_obj("eye", 0.017, 0.024, 0.014, segs=12)
        K.place(eye, (sx * 0.066, 0, eye_z))
        parts.append(ctx.add(eye, steel, uv_scale=3.0, smooth=40))
        post = K.box("post", (0.012, 0.03, 0.03), center=(sx * 0.064, 0.0, 0.015))
        parts.append(ctx.add(post, steel, uv_scale=3.0))
    pts = [(0.0, -0.02, 0.005)]
    for k in range(1, 6):
        pts.append((rr.uniform(-0.03, 0.03), -0.02 - chain_len * k / 5, 0.006))
    parts.append(ctx.add(W.chain_obj("chain", pts, link=0.04, wire=0.0035), steel, uv_scale=3.0, smooth=40, patches=0.8))
    ring = W.ring_obj("ring", 0.022, 0.03, 0.006, segs=10)
    K.place(ring, (pts[-1][0], pts[-1][1] - 0.03, 0.004))
    parts.append(ctx.add(ring, steel, uv_scale=3.0, smooth=40))
    return parts


def wild_leg_trap(ctx: K.Ctx) -> None:
    """A loose leg-hold trap with its chain, set (clean) or sprung (worn), on the floor."""
    _leg_trap(ctx, sprung=not ctx.clean, seed=ctx.seed)
    ctx.col_box((-0.22, -0.36, 0), (0.22, 0.07, 0.05))


def _fur_tube(name, length, r0, r1, flat=0.35, segs=10):
    """Cased pelt: a flattened fur tube tapering from the rump (r0) to the nose (r1) along +Z."""
    prof = [(0.0, 0.0), (r0 * 0.9, 0.0)]
    for i in range(1, 8):
        s = i / 7
        prof.append((r0 + (r1 - r0) * s ** 0.8, length * s))
    prof.append((0.0, length + 0.02))
    o = K.lathe(name, prof, segs=segs)
    K.map_verts(o, lambda co: Vector((co.x, co.y * flat, co.z)))
    return o


def wild_pelt_board(ctx: K.Ctx) -> None:
    """Trapper's wall board: three weathered planks with cleats, a beaver pelt laced into a willow
    hoop, a fox and a marten cased on stretcher boards, two traps hung by their chains and a coil
    of snare wire, all on nails. Worn: pelts faded, one trap gone. Wall prop."""
    r = ctx.rnd("pelts")
    wood = "wood_weathered"
    for i in range(3):
        x = -0.52 + i * 0.52
        ctx.add(P.plank(f"board{i}", 1.4, 0.022, 0.5, cuts=3), wood, long_axis=0, at=((x, -0.011, 0.7), (0, 90, 0)),
                patches=0.6, edge=1.3)
    for z in (0.12, 1.28):
        W.bar(ctx, "cleat", (-0.8, -0.03, z), (0.8, -0.03, z), 0.035, 0.07, wood, up=(0, -1, 0))
    nails = []
    # Beaver on a hoop (left).
    bx, bz = -0.42, 0.75
    pelt = K.lathe("beaver", [(0.0, 0.028), (0.12, 0.026), (0.2, 0.02), (0.26, 0.01), (0.28, 0.0)], segs=20)
    K.map_verts(pelt, lambda co: Vector((co.x * 0.85, co.y, co.z)))
    K.noise_disp(pelt, 0.006, scale=8.0, seed=r.randint(0, 99))
    K.place(pelt, rot=(90, 0, 0))
    K.place(pelt, (bx, -0.045, bz))
    ctx.add(pelt, "wild_fur_dark" if ctx.clean else "wild_fur_brown", uv_scale=2.0, smooth=55, patches=0.0, edge=0.2)
    hoop = K.tube("hoop", [(bx + 0.33 * 0.85 * math.cos(a), -0.05, bz + 0.33 * math.sin(a)) for a in
                           [k * math.tau / 20 for k in range(20)]], 0.008, segs=5, closed=True)
    ctx.add(hoop, "wood_stained", uv_scale=2.0, smooth=50)
    for k in range(14):
        a = k * math.tau / 14
        p0 = (bx + 0.275 * 0.85 * math.cos(a), -0.048, bz + 0.275 * math.sin(a))
        p1 = (bx + 0.33 * 0.85 * math.cos(a + 0.12), -0.05, bz + 0.33 * math.sin(a + 0.12))
        W.rod(ctx, f"lace{k}", p0, p1, 0.0018, "item_rope", segs=3, smooth=None)
    nails.append(((bx, -0.02, bz + 0.34), (0, -1, 0)))
    # Fox (centre) and marten (right) cased on boards, nose up.
    for name, x, z0, L, r0, r1, mat, tail in (("fox", 0.12, 0.28, 0.82, 0.085, 0.018, "wild_fur_fox", 0.36),
                                              ("marten", 0.48, 0.55, 0.55, 0.05, 0.012, "wild_fur_dark", 0.2)):
        board = K.prism(f"{name}board", [(-r0 * 0.9, 0.0), (r0 * 0.9, 0.0), (r1 * 0.9, L + 0.12), (-r1 * 0.9, L + 0.12)],
                        0.01, plane="XZ")
        K.place(board, (x, -0.035, z0))
        ctx.add(board, "wood_fresh", uv_scale=1.0)
        fur = _fur_tube(name, L, r0, r1)
        K.noise_disp(fur, 0.006, scale=10.0, seed=r.randint(0, 99))
        K.place(fur, (x, -0.035, z0 + 0.04))
        if ctx.worn and name == "marten":
            continue
        ctx.add(fur, mat, uv="cyl", uv_axis=2, uv_scale=2.0, smooth=55, patches=0.0, edge=0.2)
        tl = K.tube(f"{name}tail", [(x + 0.01, -0.06, z0 + 0.05), (x + 0.03, -0.065, z0 - tail * 0.5), (x + 0.02, -0.06, z0 - tail)],
                    [r0 * 0.45, r0 * 0.4, r0 * 0.15], segs=7)
        ctx.add(tl, mat, uv_scale=2.0, smooth=55, patches=0.0)
        nails.append(((x, -0.02, z0 + L + 0.1), (0, -1, 0)))
    # Two traps hanging by their chains (sprung), a wire coil.
    for k, (x, z) in enumerate(((-0.57, 0.32), (0.6, 0.3))):
        if ctx.worn and k == 1:
            continue
        tp = _leg_trap(ctx, sprung=True, chain_len=0.18, seed=r.randint(0, 999))
        _rot_about(tp, (0, 0, 0), (-90, 0, 0))
        _rot_about(tp, (0, 0, 0), (0, 0, 180))
        _move(tp, (x, -0.06, z))
        nails.append(((x, -0.02, z + 0.27), (0, -1, 0)))
    coil = K.tube("coil", [(0.62 + 0.09 * math.cos(a), -0.04 - 0.004 * (a / math.tau), 1.05 + 0.09 * math.sin(a))
                           for a in [k * math.tau / 18 for k in range(40)]], 0.0022, segs=4)
    ctx.add(coil, "metal_galvanized", uv_scale=2.0, smooth=40)
    nails.append(((0.62, -0.02, 1.14), (0, -1, 0)))
    W.bolts(ctx, "nails", nails, "item_iron_strap", r=0.006, h=0.02, segs=6)
    ctx.col_box((-0.8, -0.12, 0.0), (0.8, 0.0, 1.4))


def wild_crosscut_saw(ctx: K.Ctx) -> None:
    """Two-man felling saw resting teeth-up on wall pegs (M-teeth with rakers, upright handles),
    and a single-bit felling axe across two nails below. Wall prop."""
    r = ctx.rnd("crosscut")
    for x in (-0.62, 0.62):
        W.rod(ctx, "peg", (x, 0.0, 0.4), (x, -0.11, 0.42), 0.018, "wood_weathered", segs=8)
    outline = W.saw_outline(1.7, 0.08, 0.028, 0.022, belly=0.07, raker_every=5)
    plate = W.saw_plate_obj("plate", [(x, -z) for x, z in outline], 0.0018)
    zmin = min(v.co.z for v in plate.data.vertices)
    K.place(plate, (0, -0.07, 0.432 - zmin))
    ctx.add(plate, "wild_saw_steel_rust" if not ctx.clean else "wild_saw_steel", uv_scale=1.0, patches=0.5, edge=0.8)
    for sx in (-1, 1):
        x = sx * 0.88
        W.bar(ctx, "clip", (x - sx * 0.05, -0.07, 0.47), (x, -0.07, 0.47), 0.012, 0.05, "item_iron_strap", up=(0, -1, 0))
        W.rod(ctx, "handle", (x, -0.07, 0.4), (x, -0.07, 0.6), 0.016, "item_wood_handle", r2=0.014, segs=8)
    # Felling axe on two nails.
    hz = 0.14
    handle = K.tube("axehandle", [(-0.42, -0.04, hz), (-0.1, -0.04, hz + 0.004), (0.2, -0.04, hz), (0.38, -0.04, hz - 0.01)],
                    [0.016, 0.014, 0.015, 0.017], segs=8)
    ctx.add(handle, "item_wood_handle", uv_scale=2.0, smooth=50, patches=0.4)
    head = K.prism("axehead", [(0.0, -0.03), (0.06, -0.034), (0.16, -0.065), (0.175, 0.0), (0.16, 0.065), (0.06, 0.034),
                               (0.0, 0.03)], 0.04, plane="XZ")
    K.map_verts(head, lambda co: Vector((co.x, co.y * (1.0 - 0.85 * max(0.0, co.x - 0.05) / 0.125), co.z)))
    K.place(head, rot=(0, -90, 0))
    K.place(head, (0.4, -0.04, hz - 0.02))
    ctx.add(head, "wild_saw_steel_rust", uv_scale=2.0, patches=0.6)
    W.bolts(ctx, "nails", [((-0.3, 0.0, hz - 0.03), (0, -1, 0)), ((0.18, 0.0, hz - 0.03), (0, -1, 0))], "item_iron_strap",
            r=0.005, h=0.06)
    ctx.col_box((-0.9, -0.12, 0.05), (0.9, 0.0, 0.66))


# ============================================================================================
# Cabin yard: smoking rack, chopping block, canoe
# ============================================================================================

def wild_smoking_rack(ctx: K.Ctx) -> None:
    """Bark-on pole drying/smoking rack lashed with rope: cross sticks hung with strips of meat
    and split, smoked fish over a ring of stones and a smudge of ash and charred sticks.
    Worn: picked over, strips on the ground, a post leaning."""
    r = ctx.rnd("smokerack")
    L, D, H = 2.0, 0.8, 1.55
    bark = "wild_log_bark"
    posts = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            lean = 0.12 if (ctx.worn and sx > 0 and sy > 0) else 0.0
            posts.append(W.pole(ctx, f"post{sx}{sy}", [(sx * L / 2, sy * D / 2, -0.02), (sx * (L / 2 - 0.02), sy * (D / 2 - 0.01), H * 0.5),
                                                      (sx * (L / 2 - 0.04) + lean, sy * (D / 2 - 0.02), H + 0.06)], 0.042, bark,
                                r_end=0.032, seed=r.randint(0, 999), wobble=0.025, moss=0.4))
    for sy in (-1, 1):
        W.pole(ctx, f"rail{sy}", [(-L / 2 - 0.12, sy * (D / 2 - 0.02), H - 0.03), (0.0, sy * (D / 2 - 0.02) + r.uniform(-0.02, 0.02), H - 0.06),
                                  (L / 2 + 0.12, sy * (D / 2 - 0.02), H - 0.03)], 0.03, bark, r_end=0.025, seed=r.randint(0, 999))
        for sx in (-1, 1):
            for k in range(2):
                c = (sx * (L / 2 - 0.03), sy * (D / 2 - 0.02), H - 0.04 - 0.03 * k)
                lash = K.tube("lash", [(c[0] + 0.045 * math.cos(a), c[1] + 0.045 * math.sin(a), c[2] + 0.01 * math.sin(2 * a))
                                       for a in [j * math.tau / 10 for j in range(10)]], 0.006, segs=4, closed=True)
                ctx.add(lash, "item_rope", uv_scale=3.0, smooth=50)
    xs = [-0.8 + i * 0.32 for i in range(6)]
    for i, x in enumerate(xs):
        W.pole(ctx, f"stick{i}", [(x, -D / 2 - 0.06, H + 0.0), (x + r.uniform(-0.02, 0.02), D / 2 + 0.06, H + 0.01)], 0.013,
               "wood_weathered", r_end=0.011, seed=i)
    k = 0
    for i, x in enumerate(xs):
        for j, y in enumerate((-0.25, 0.0, 0.25)):
            if r.random() < (0.15 if ctx.clean else 0.5):
                continue
            fish = (i + j) % 3 == 0
            if fish:
                out = [(0.0, 0.0), (0.055, -0.08), (0.068, -0.28), (0.03, -0.4), (0.045, -0.47), (0.0, -0.43), (-0.045, -0.47),
                       (-0.03, -0.4), (-0.068, -0.28), (-0.055, -0.08)]
                o = K.prism(f"fish{k}", out, 0.012, plane="XZ")
                K.place(o, rot=(0, 0, 90))
                K.place(o, (x, y, H - 0.01))
                ctx.add(o, "wild_fish_smoked", uv_scale=2.0, patches=0.3, edge=0.6)
            else:
                Ls = r.uniform(0.22, 0.38)
                o = K.box(f"strip{k}", (0.045, 0.007, Ls), center=(0, 0, -Ls / 2), cuts=(0, 0, 4))
                bend = r.uniform(-0.04, 0.04)
                K.map_verts(o, lambda co, b=bend, ls=Ls: Vector((co.x + b * (co.z / ls) ** 2, co.y + 0.01 * math.sin(co.z * 20), co.z)))
                K.place(o, (x, y, H - 0.005), (0, 0, 90 + r.uniform(-15, 15)))
                ctx.add(o, "wild_jerky", uv_scale=3.0, patches=0.3, edge=0.6)
            k += 1
    if ctx.worn:
        for m in range(3):
            o = K.box(f"fallen{m}", (0.045, 0.3, 0.007), center=(0, 0, 0.004))
            K.place(o, (r.uniform(-0.8, 0.8), r.uniform(-0.6, 0.6), 0.0), (0, 0, r.uniform(0, 360)))
            ctx.add(o, "wild_jerky", uv_scale=3.0, patches=0.5)
    for m in range(9):
        a = m * math.tau / 9 + r.uniform(-0.1, 0.1)
        st = K.chunk(f"stone{m}", r.uniform(0.13, 0.19), r, n=10, flat=0.65)
        K.place(st, (0.34 * math.cos(a), 0.3 * math.sin(a), 0.04), (0, 0, r.uniform(0, 360)))
        ctx.add(st, "rock_granite", uv_scale=1.5, smooth=30, patches=0.2, moss=0.3)
    ash = K.blob("ash", 0.5, subdiv=2, scale=(0.5, 0.45, 0.05), rough=0.3, seed=3, center=(0, 0, 0.0))
    ctx.add(ash, "ash_burnt", uv_scale=1.5, smooth=40, patches=0.0)
    for m in range(4):
        a = r.uniform(0, math.tau)
        W.rod(ctx, f"brand{m}", (0.2 * math.cos(a), 0.2 * math.sin(a), 0.03), (-0.1 * math.cos(a + 0.5), -0.1 * math.sin(a + 0.5), 0.05),
              0.022, "wood_charred", segs=6)
    ctx.col_box((-L / 2 - 0.1, -D / 2 - 0.05, 0), (L / 2 + 0.1, D / 2 + 0.05, H + 0.05))


def wild_chopping_block(ctx: K.Ctx) -> None:
    """Fir round used as a chopping block, top scarred by years of splitting, a single-bit axe
    sunk in it, split pieces and chips around its foot."""
    r = ctx.rnd("chop")
    R, Hb = 0.27, 0.5
    blk = W.log_obj("block", Hb, R, r.randint(0, 9999), sides=14, rings=3, taper=0.0, bow=0.0)
    K.place(blk, rot=(0, -90, 0))
    K.place(blk, (0, 0, Hb / 2))
    for k in range(5):
        a = r.uniform(0, math.tau)
        K.dent(blk, (0.12 * math.cos(a), 0.12 * math.sin(a), Hb), 0.08, 0.012)
    ctx.add(blk, None, uv=None, smooth=50, patches=0.3, edge=0.7, moss=0.3)
    axe = []
    head = K.prism("head", [(0.0, -0.03), (0.06, -0.034), (0.16, -0.065), (0.175, 0.0), (0.16, 0.065), (0.06, 0.034), (0.0, 0.03)],
                   0.04, plane="XZ")
    K.map_verts(head, lambda co: Vector((co.x, co.y * (1.0 - 0.85 * max(0.0, co.x - 0.05) / 0.125), co.z)))
    K.place(head, rot=(90, 0, 0))
    axe.append(ctx.add(head, "wild_saw_steel_rust" if ctx.worn else "item_steel_tool", uv_scale=2.0, patches=0.6))
    hd = K.tube("handle", [(0.02, 0.0, 0.0), (0.02, -0.25, 0.0), (0.012, -0.55, 0.0), (0.024, -0.76, 0.0)],
                [0.017, 0.014, 0.015, 0.018], segs=8)
    axe.append(ctx.add(hd, "item_wood_handle", uv_scale=2.0, smooth=50, patches=0.4))
    # Head built with the bit along +X and the handle along -Y: tip the bit down into the wood.
    _rot_about(axe, (0, 0, 0), (-28, 0, 0))
    _rot_about(axe, (0, 0, 0), (0, 70, 0))
    _rot_about(axe, (0, 0, 0), (0, 0, r.uniform(-40, 40)))
    tip = max((v.co.copy() for o in axe[:1] for v in o.data.vertices), key=lambda v: -v.z)
    _move(axe, (0.03 - tip.x, 0.0 - tip.y, Hb - 0.05 - tip.z))
    for k in range(4):
        a = r.uniform(0, math.tau)
        d = r.uniform(0.45, 0.65)
        _split_piece(ctx, f"split{k}", r.uniform(0.34, 0.42), r.uniform(0.07, 0.1), r.randint(0, 9999),
                     "half" if k % 2 else "quarter", (d * math.cos(a), d * math.sin(a), 0.06), (r.uniform(0, 360), 0, r.uniform(0, 360)))
    for k in range(16):
        a = r.uniform(0, math.tau)
        d = r.uniform(0.3, 0.85)
        ch = K.box(f"chip{k}", (r.uniform(0.03, 0.06), r.uniform(0.015, 0.03), 0.004))
        K.place(ch, (d * math.cos(a), d * math.sin(a), 0.002), (r.uniform(-8, 8), r.uniform(-8, 8), r.uniform(0, 360)))
        ctx.add(ch, "wild_lumber_fresh", uv_scale=2.0, patches=0.2)
    ctx.col_box((-R, -R, 0), (R, R, Hb))


def _canoe_rings(L, B, sheer, n, m):
    rings = []
    for i in range(n):
        s = i / (n - 1)
        x = -L / 2 + L * s
        u = 2 * x / L
        b = max(0.006, B / 2 * max(0.0, 1 - abs(u) ** 2.3) ** 0.75)
        bottom = 0.035 * u * u
        sh = sheer + 0.17 * u ** 4
        ring = []
        for k in range(-m, m + 1):
            th = abs(k) / m * math.pi / 2
            y = math.copysign(b * math.sin(th) ** 0.55, k) if k else 0.0
            z = bottom + (sh - bottom) * (1 - math.cos(th) ** 0.5)
            ring.append((x, y, z))
        rings.append(ring)
    return rings


def wild_canoe(ctx: K.Ctx) -> None:
    """Wood-and-canvas canoe: green painted canvas over cedar planking and ribs, keel strip,
    gunwales, bow and stern decks, two cane seats and a centre thwart. Clean: right side up with
    two paddles in it. Worn: turned over on the grass, mossy. Destroyed: overturned and holed."""
    r = ctx.rnd("canoe")
    L, B, SH = 4.9, 0.88, 0.33
    n, m = 25, 6
    rings = _canoe_rings(L, B, SH, n, m)
    hull = K.loft("hull", rings, closed_ring=False, cap_start=False, cap_end=False, recalc=False)
    me = hull.data
    import bmesh as _bm
    keel_face = min(me.polygons, key=lambda p: p.center.z + abs(p.center.x) * 0.01)
    if keel_face.normal.z > 0:
        bm = _bm.new()
        bm.from_mesh(me)
        _bm.ops.reverse_faces(bm, faces=bm.faces)
        K.write_bm(bm, hull)
    from lib import materials as MM
    MM.assign(hull, "wild_canvas_green")
    MM.assign(hull, "wild_cedar")
    K.solidify(hull, 0.01, offset=-1.0, mat_offset=1, mat_offset_rim=1)
    if ctx.destroyed:
        K.jagged_hole(hull, (0.6, 0.18, 0.0), 0.24, r.randint(0, 999), axis=2, jag=0.5)
    parts = [ctx.add(hull, None, long_axis=0, uv_scale=1.0, smooth=50, patches=0.5, edge=1.2, moss=0.6 if ctx.worn else 0.0)]
    keel = K.sweep("keel", [ring[m] for ring in rings[1:-1]], [(-0.012, -0.012), (0.012, -0.012), (0.012, 0.0), (-0.012, 0.0)])
    parts.append(ctx.add(keel, "wood_stained", long_axis=0, smooth=40, patches=0.6))
    for side in (0, -1):
        pts = [ring[side] for ring in rings]
        gw = K.sweep(f"gunwale{side}", pts, [(-0.02, -0.024), (0.02, -0.024), (0.02, 0.006), (-0.02, 0.006)])
        parts.append(ctx.add(gw, "wood_stained", long_axis=0, smooth=40, patches=0.6, edge=1.4))
    for i in range(2, n - 2, 2):
        ring = rings[i]
        x = ring[0][0]
        pts = []
        for k in range(1, 2 * m):
            px, py, pz = ring[k]
            pts.append((px, py * 0.97, pz + 0.012))
        if ctx.destroyed and abs(x - 0.6) < 0.3:
            continue
        rib = K.sweep(f"rib{i}", pts, [(-0.004, -0.02), (0.004, -0.02), (0.004, 0.02), (-0.004, 0.02)], up=(1, 0, 0))
        parts.append(ctx.add(rib, "wild_cedar", uv_scale=2.0, smooth=40, patches=0.4))

    def beam_at(x):
        u = 2 * x / L
        return max(0.006, B / 2 * max(0.0, 1 - abs(u) ** 2.3) ** 0.75), SH + 0.17 * u ** 4
    for xs in (-1.45, 1.6):
        b, sh = beam_at(xs)
        z = sh - 0.13
        for dx in (-0.12, 0.12):
            bb, _ = beam_at(xs + dx)
            parts.append(W.bar(ctx, "seatbar", (xs + dx, -bb * 0.9, z), (xs + dx, bb * 0.9, z), 0.03, 0.022, "wood_stained"))
        cane = K.box("cane", (0.22, b * 1.6, 0.006), center=(xs, 0, z + 0.012))
        parts.append(ctx.add(cane, "furn_burlap", uv_scale=4.0, patches=0.4))
    b0, sh0 = beam_at(0.0)
    parts.append(W.bar(ctx, "thwart", (0.0, -b0, sh0 - 0.03), (0.0, b0, sh0 - 0.03), 0.07, 0.025, "wood_stained"))
    for sx in (-1, 1):
        xd = sx * (L / 2 - 0.42)
        bd, shd = beam_at(xd)
        deck = K.prism("deck", [(xd, -bd), (sx * (L / 2 - 0.05), 0.0), (xd, bd)], 0.016, plane="XY", offset=shd - 0.012)
        parts.append(ctx.add(deck, "wood_stained", long_axis=0, patches=0.5))
    if ctx.clean:
        for k, y in enumerate((-0.12, 0.1)):
            x0 = r.uniform(-0.6, -0.3)
            z = 0.06
            W.rod(ctx, f"shaft{k}", (x0, y, z), (x0 + 1.05, y + 0.03, z + 0.02), 0.015, "wood_fresh", segs=8)
            blade = K.prism(f"blade{k}", [(0.0, -0.08), (0.12, -0.09), (0.45, -0.07), (0.53, 0.0), (0.45, 0.07), (0.12, 0.09),
                                          (0.0, 0.08)], 0.012, plane="XY")
            K.place(blade, (x0 - 0.5, y - 0.005, z - 0.006))
            ctx.add(blade, "wood_fresh", long_axis=0, patches=0.3)
            grip = K.box(f"grip{k}", (0.03, 0.1, 0.03), center=(x0 + 1.07, y + 0.03, z + 0.02), bevel=0.01)
            ctx.add(grip, "wood_fresh", uv_scale=2.0, smooth=40)
    else:
        _rot_about(parts, (0, 0, SH * 0.5), (180, 0, 0))
        lo = min(min(v.co.z for v in o.data.vertices) for o in parts)
        _move(parts, (0, 0, -lo))
    ctx.col_box((-L / 2, -B / 2 - 0.03, 0), (L / 2, B / 2 + 0.03, SH + 0.17 if ctx.clean else SH))


# ============================================================================================
# Outhouse, smokehouse
# ============================================================================================

def _board_wall(ctx, name, a, b, z0, ztop_fn, normal, *, board=0.15, gap=0.006, wood="wood_weathered", battens=True,
                skip=(), r=None):
    """Vertical boards along the line a->b (floor-level points), each from z0 up to ztop_fn(t)
    (t = 0..1 along the wall), thickness along `normal`, with battens over the joints."""
    a, b = Vector(a), Vector(b)
    span = (b - a).length
    n = max(1, int(round(span / (board + gap))))
    w = span / n - gap
    nrm = Vector(normal).normalized()
    out = []
    for i in range(n):
        if i in skip:
            continue
        t = (i + 0.5) / n
        p = a.lerp(b, t)
        zt = ztop_fn(t) + (r.uniform(-0.015, 0.015) if r else 0.0)
        out.append(W.bar(ctx, f"{name}{i}", (p.x, p.y, z0), (p.x, p.y, zt), w, 0.018, wood, up=tuple(nrm), patches=0.6,
                         edge=1.2, low=0.6, low_h=0.3, moss=0.3))
        if battens and i < n - 1:
            q = a.lerp(b, (i + 1) / n) + nrm * 0.016
            out.append(W.bar(ctx, f"{name}b{i}", (q.x, q.y, z0 + 0.02), (q.x, q.y, min(zt, ztop_fn((i + 1) / n)) - 0.02), 0.05,
                             0.014, wood, up=tuple(nrm), patches=0.6, edge=1.3))
    return out


def wild_outhouse(ctx: K.Ctx) -> None:
    """Board-and-batten outhouse on log skids: shed roof of tarpaper over boards, a vent stack,
    a ledged door with strap hinges and a crescent cut, a one-hole bench inside.
    Worn: door hanging open, a side board missing, moss on the roof."""
    r = ctx.rnd("outhouse")
    Wd, D, Hf, Hb, z0 = 1.1, 1.15, 2.22, 1.96, 0.17
    wood = "wood_weathered"
    for sx in (-1, 1):
        lg = W.log_obj("skid", 1.35, 0.075, r.randint(0, 999), sides=8, rings=3, taper=0.05, bow=0.01)
        K.place(lg, (sx * 0.4, 0, 0.07), (0, 0, 90))
        ctx.add(lg, None, uv=None, smooth=50, patches=0.4, moss=0.5)
    for i in range(7):
        y = -D / 2 + (i + 0.5) * D / 7
        ctx.add(P.plank(f"floor{i}", Wd + 0.04, D / 7 - 0.006, 0.03), wood, long_axis=0, at=((0, y, z0 - 0.015),), patches=0.6)

    def roof_z(y):
        return Hb + (Hf - Hb) * (D / 2 - y) / D
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.bar(ctx, "post", (sx * (Wd / 2 - 0.035), sy * (D / 2 - 0.035), z0), (sx * (Wd / 2 - 0.035), sy * (D / 2 - 0.035), roof_z(sy * D / 2) - 0.03),
                  0.07, 0.07, wood)
    _board_wall(ctx, "back", (-Wd / 2, D / 2 + 0.01, 0), (Wd / 2, D / 2 + 0.01, 0), z0 - 0.04, lambda t: Hb, (0, 1, 0), r=r)
    for sx in (-1, 1):
        skip = (2,) if (ctx.worn and sx > 0) else ()
        _board_wall(ctx, f"side{sx}", (sx * (Wd / 2 + 0.01), -D / 2, 0), (sx * (Wd / 2 + 0.01), D / 2, 0), z0 - 0.04,
                    lambda t: roof_z(-D / 2 + D * t), (sx, 0, 0), r=r, skip=skip)
    dw = 0.62
    for sx in (-1, 1):
        _board_wall(ctx, f"front{sx}", (sx * dw / 2, -D / 2 - 0.01, 0), (sx * Wd / 2, -D / 2 - 0.01, 0), z0 - 0.04, lambda t: Hf,
                    (0, -1, 0), battens=False, r=r)
    W.bar(ctx, "header", (-dw / 2, -D / 2 - 0.01, Hf - 0.25), (dw / 2, -D / 2 - 0.01, Hf - 0.25), 0.25, 0.018, wood, up=(0, -1, 0))
    door = []
    dh = Hf - 0.3 - z0
    for i in range(4):
        x = -dw / 2 + (i + 0.5) * dw / 4
        door.append(W.bar(ctx, f"door{i}", (x, -D / 2 - 0.03, z0 + 0.01), (x, -D / 2 - 0.03, z0 + dh), dw / 4 - 0.006, 0.018, wood,
                          up=(0, -1, 0), patches=0.6, edge=1.3))
    for z in (z0 + 0.25, z0 + dh - 0.25):
        door.append(W.bar(ctx, "ledger", (-dw / 2 + 0.04, -D / 2 - 0.01, z), (dw / 2 - 0.04, -D / 2 - 0.01, z), 0.11, 0.02, wood,
                          up=(0, -1, 0)))
    door.append(W.bar(ctx, "brace", (-dw / 2 + 0.06, -D / 2 - 0.01, z0 + 0.3), (dw / 2 - 0.06, -D / 2 - 0.01, z0 + dh - 0.3), 0.1,
                      0.02, wood, up=(0, -1, 0)))
    for z in (z0 + 0.25, z0 + dh - 0.25):
        door.append(W.bar(ctx, "strap", (-dw / 2 - 0.02, -D / 2 - 0.042, z), (-dw / 2 + 0.22, -D / 2 - 0.042, z), 0.03, 0.005,
                          "paint_black", up=(0, -1, 0)))
    cres = []
    for k in range(13):
        a = math.radians(40 + 280 * k / 12)
        cres.append((0.075 * math.cos(a), 0.075 * math.sin(a)))
    for k in range(12, -1, -1):
        a = math.radians(55 + 250 * k / 12)
        cres.append((0.03 + 0.06 * math.cos(a), 0.06 * math.sin(a)))
    moon = K.prism("crescent", cres, 0.006, plane="XZ")
    K.place(moon, rot=(0, 0, 0))
    K.place(moon, (0.05, -D / 2 - 0.042, z0 + dh - 0.22))
    door.append(ctx.add(moon, "paint_black", uv_scale=2.0, wear=0.0))
    if ctx.worn:
        _rot_about(door, (-dw / 2, -D / 2 - 0.03, 0), (0, 0, -78))
    bench = K.box("bench", (Wd - 0.06, 0.5, 0.45), center=(0, D / 2 - 0.27, z0 + 0.225))
    ctx.add(bench, wood, uv_scale=1.0, patches=0.6)
    hole = K.cyl("hole", 0.12, 0.004, segs=14, center=(0, D / 2 - 0.3, z0 + 0.452))
    ctx.add(hole, "paint_black", uv_scale=1.0, wear=0.0)
    ang = math.degrees(math.atan2(Hf - Hb, D))
    zc = (Hf + Hb) / 2 + 0.03
    deck = K.box("roofdeck", (Wd + 0.3, D / math.cos(math.radians(ang)) + 0.3, 0.025))
    K.place(deck, rot=(-ang, 0, 0))
    K.place(deck, (0, 0, zc))
    ctx.add(deck, wood, long_axis=0, patches=0.6)
    tar = K.box("tar", (Wd + 0.32, D / math.cos(math.radians(ang)) + 0.32, 0.006), cuts=(2, 2, 0))
    K.place(tar, rot=(-ang, 0, 0))
    K.place(tar, (0, 0, zc + 0.016))
    ctx.add(tar, "wild_tarpaper", uv_scale=1.0, patches=0.4, moss=0.6 if ctx.worn else 0.2)
    W.rod(ctx, "vent", (0.35, D / 2 - 0.18, z0 + 0.4), (0.35, D / 2 - 0.18, Hb + 0.6), 0.05, "metal_galvanized", segs=10)
    cap = K.lathe("cap", [(0.0, 0.0), (0.09, 0.0), (0.0, 0.07)], segs=10)
    K.place(cap, (0.35, D / 2 - 0.18, Hb + 0.64))
    ctx.add(cap, "metal_galvanized", uv_scale=2.0)
    ctx.col_box((-Wd / 2 - 0.05, -D / 2 - 0.05, 0), (Wd / 2 + 0.05, D / 2 + 0.05, Hf))


def wild_smokehouse(ctx: K.Ctx) -> None:
    """Small plank smokehouse with a cedar-shake gable roof and ridge vent, gappy smoke-stained
    boards on log sills, a low ledged door, and a cut-down oil drum firebox outside feeding a
    pipe through the side wall. Through the door: a rack of split fish in the dark.
    Worn: door ajar, roof mossy."""
    r = ctx.rnd("smokehouse")
    Wd, D, He, Hr = 1.6, 1.6, 1.85, 2.45
    wall = "wood_creosote"
    for sy in (-1, 1):
        lg = W.log_obj("sill", Wd + 0.3, 0.09, r.randint(0, 999), sides=8, rings=3, taper=0.04, bow=0.01)
        K.place(lg, (0, sy * D / 2, 0.08))
        ctx.add(lg, None, uv=None, smooth=50, patches=0.4, moss=0.5)
    for sx in (-1, 1):
        lg = W.log_obj("sillx", D, 0.085, r.randint(0, 999), sides=8, rings=3, taper=0.04, bow=0.01)
        K.place(lg, (sx * Wd / 2, 0, 0.17), (0, 0, 90))
        ctx.add(lg, None, uv=None, smooth=50, patches=0.4, moss=0.5)

    def gable(t):
        x = -Wd / 2 + Wd * t
        return He + (Hr - He) * (1 - abs(x) / (Wd / 2)) - 0.04
    _board_wall(ctx, "back", (-Wd / 2, D / 2 + 0.01, 0), (Wd / 2, D / 2 + 0.01, 0), 0.12, gable, (0, 1, 0), wood=wall,
                battens=False, gap=0.014, r=r)
    for sx in (-1, 1):
        _board_wall(ctx, f"side{sx}", (sx * (Wd / 2 + 0.01), -D / 2, 0), (sx * (Wd / 2 + 0.01), D / 2, 0), 0.2, lambda t: He,
                    (sx, 0, 0), wood=wall, battens=False, gap=0.014, r=r)
    dw = 0.66
    for sx in (-1, 1):
        _board_wall(ctx, f"front{sx}", (sx * dw / 2, -D / 2 - 0.01, 0), (sx * Wd / 2, -D / 2 - 0.01, 0), 0.12,
                    lambda t, s=sx: He + (Hr - He) * (1 - abs(s * (dw / 2 + (Wd / 2 - dw / 2) * t)) / (Wd / 2)) - 0.04,
                    (0, -1, 0), wood=wall, battens=False, gap=0.014, r=r)
    W.bar(ctx, "lintel", (-dw / 2, -D / 2 - 0.01, 1.68), (dw / 2, -D / 2 - 0.01, 1.68), 0.1, 0.02, wall, up=(0, -1, 0))
    _board_wall(ctx, "gablefront", (-dw / 2, -D / 2 - 0.01, 0), (dw / 2, -D / 2 - 0.01, 0), 1.73,
                lambda t: He + (Hr - He) * (1 - abs(-dw / 2 + dw * t) / (Wd / 2)) - 0.04, (0, -1, 0), wood=wall, battens=False,
                gap=0.014, r=r)
    door = []
    for i in range(4):
        x = -dw / 2 + (i + 0.5) * dw / 4
        door.append(W.bar(ctx, f"door{i}", (x, -D / 2 - 0.03, 0.14), (x, -D / 2 - 0.03, 1.62), dw / 4 - 0.008, 0.02, "wood_weathered",
                          up=(0, -1, 0), patches=0.6, edge=1.3))
    for z in (0.4, 1.35):
        door.append(W.bar(ctx, "ledger", (-dw / 2 + 0.04, -D / 2 - 0.01, z), (dw / 2 - 0.04, -D / 2 - 0.01, z), 0.1, 0.02,
                          "wood_weathered", up=(0, -1, 0)))
    door.append(ctx.add(K.box("button", (0.03, 0.03, 0.1), center=(dw / 2 + 0.05, -D / 2 - 0.04, 0.95)), "wood_weathered",
                        uv_scale=2.0))
    if ctx.worn:
        _rot_about(door, (-dw / 2, -D / 2 - 0.03, 0), (0, 0, -42))
    W.bar(ctx, "fishbar", (-0.55, -0.1, 1.6), (0.55, -0.1, 1.6), 0.03, 0.03, "wood_weathered")
    for k in range(5):
        x = -0.4 + k * 0.2
        out = [(0.0, 0.0), (0.05, -0.08), (0.06, -0.26), (0.025, -0.37), (0.04, -0.43), (0.0, -0.4), (-0.04, -0.43),
               (-0.025, -0.37), (-0.06, -0.26), (-0.05, -0.08)]
        o = K.prism(f"fish{k}", out, 0.012, plane="XZ")
        K.place(o, (x, -0.1, 1.58))
        ctx.add(o, "wild_fish_smoked", uv_scale=2.0, patches=0.3)
    # Shake roof: the ridge runs front to back (gables carry the door and the back wall), two
    # slopes of overlapping courses falling to the side eaves, ridge boards, a louvred vent.
    ang = math.atan2(Hr - He, Wd / 2)
    slope_len = (Wd / 2) / math.cos(ang) + 0.25
    gone = {(1, 2), (1, 3), (-1, 4)} if ctx.worn else set()
    for sx in (-1, 1):
        for k in range(6):
            sk = (k + 0.5) * (slope_len / 6)
            xx = sx * (Wd / 2 + 0.25 - sk * math.cos(ang))
            zz = He - 0.25 * math.tan(ang) + sk * math.sin(ang) + 0.045 + 0.01 * k
            if (sx, k) in gone:
                # A few shakes blown off: the course is split around a gap showing the dark lath.
                gy = r.uniform(-0.3, 0.3)
                spans = [(-D / 2 - 0.18, gy - 0.13), (gy + 0.13, D / 2 + 0.18)]
            else:
                spans = [(-D / 2 - 0.18, D / 2 + 0.18)]
            for j, (y0, y1) in enumerate(spans):
                sh = K.box(f"shake{sx}{k}{j}", (slope_len / 6 + 0.12, y1 - y0, 0.022), cuts=(0, 6, 0))
                K.noise_disp(sh, 0.006, scale=6.0, seed=k + (sx > 0) * 10 + j * 20)
                K.place(sh, rot=(0, math.degrees(ang) * sx, 0))
                K.place(sh, (xx, (y0 + y1) / 2 + r.uniform(-0.02, 0.02), zz))
                ctx.add(sh, "wood_weathered", long_axis=0, uv_scale=1.0, patches=0.6, moss=0.7 if ctx.worn else 0.35)
    for sx in (-1, 1):
        rb = K.box("ridge", (0.16, D + 0.4, 0.022))
        K.place(rb, rot=(0, sx * 45, 0))
        K.place(rb, (sx * 0.05, 0, Hr + 0.08))
        ctx.add(rb, "wood_weathered", long_axis=1, patches=0.6, moss=0.4)
    vent = K.box("vent", (0.3, 0.26, 0.18), center=(0, 0, Hr + 0.18), bevel=0.01)
    ctx.add(vent, "wood_creosote", uv_scale=1.0, patches=0.6)
    # Firebox: a cut-down drum lying on chock stones against the east wall, its door facing out
    # and a short flue stub straight into the wall low down, so the smoke reaches the fish cool.
    fx = Wd / 2 + 0.42
    drum = K.cyl("drum", 0.27, 0.55, segs=16, axis="X", center=(fx, 0.15, 0.31), cuts=2)
    ctx.add(drum, "car_rust", uv="cyl", uv_axis=0, smooth=45, patches=0.5)
    for dx in (-0.2, 0.2):
        hoop = W.ring_obj("hoop", 0.268, 0.282, 0.025, segs=16)
        K.place(hoop, (fx + dx, 0.15, 0.31), (0, 90, 0))
        ctx.add(hoop, "car_rust", uv_scale=2.0, smooth=45)
    fd = K.box("firedoor", (0.012, 0.24, 0.2), center=(fx + 0.283, 0.15, 0.3), bevel=0.004)
    if ctx.worn:
        _rot_about([fd], (fx + 0.283, 0.03, 0.3), (0, 0, 70))
    ctx.add(fd, "car_rust", uv_scale=1.5)
    latch = K.box("latch", (0.02, 0.05, 0.02), center=(fx + 0.29, 0.25, 0.3))
    ctx.add(latch, "car_rust", uv_scale=2.0)
    pipe = K.cyl("fpipe", 0.065, 0.3, segs=10, axis="X", center=(Wd / 2 + 0.05, 0.15, 0.36))
    ctx.add(pipe, "paint_black", uv="cyl", uv_axis=0, uv_scale=1.0, smooth=50, patches=0.5)
    collar = K.cyl("collar", 0.085, 0.03, segs=10, axis="X", center=(Wd / 2 + 0.03, 0.15, 0.36))
    ctx.add(collar, "car_rust", uv="cyl", uv_axis=0, uv_scale=2.0, smooth=50)
    for dx in (-0.17, 0.17):
        for dy in (-0.2, 0.2):
            stone = K.chunk("drumstone", 0.09, r, n=10, flat=0.7)
            K.place(stone, (fx + dx, 0.15 + dy, 0.04))
            ctx.add(stone, "rock_granite", uv_scale=1.5, smooth=30)
    ash = K.blob("ash", 0.5, subdiv=2, scale=(0.3, 0.22, 0.03), rough=0.3, seed=7, center=(fx + 0.45, 0.12, 0.0))
    ctx.add(ash, "ash_burnt", uv_scale=1.5, smooth=40, patches=0.0)
    ctx.col_box((-Wd / 2 - 0.2, -D / 2 - 0.2, 0), (Wd / 2 + 0.75, D / 2 + 0.2, Hr + 0.25))


# ============================================================================================
# Lookout tower frame
# ============================================================================================

def wild_lookout_tower(ctx: K.Ctx) -> None:
    """Creosoted timber frame of the Cedar Ridge lookout: four battered legs on concrete piers
    with steel shoes, girts and bolted X-bracing in three bays, beams carrying the two stair
    landings, joists under the 7 x 7 m cab and a lightning cable to a ground rod. The building
    kit supplies the stair house, landings and cab; the frame's origin is the cab's centre at
    ground level (no collision: the stairs are inside)."""
    r = ctx.rnd("tower")
    SB, ST, HT = 3.7, 3.22, 8.88
    tim = "wood_creosote"

    def leg(sx, sy, z):
        s = SB + (ST - SB) * (z / HT)
        return Vector((sx * s, sy * s, z))
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.bar(ctx, "leg", leg(sx, sy, 0.22), leg(sx, sy, HT), 0.24, 0.24, tim, up=(sx, -sy, 0), patches=0.5, edge=1.2,
                  moss=0.3)
            pier = K.box("pier", (0.62, 0.62, 0.45), center=(sx * SB, sy * SB, 0.0), bevel=0.02)
            ctx.add(pier, "concrete_barrier", uv_scale=1.0, patches=0.5, moss=0.4)
            for k in range(4):
                a = k * math.pi / 2
                n = Vector((math.cos(a), math.sin(a), 0))
                c = leg(sx, sy, 0.45) + n * 0.13
                pl = K.box("shoe", (0.012, 0.22, 0.45))
                K.place(pl, rot=(0, 0, math.degrees(a)))
                K.place(pl, (c.x, c.y, 0.45))
                ctx.add(pl, "item_iron_strap", uv_scale=2.0, patches=0.6)
            W.bolts(ctx, "shoebolts", [(leg(sx, sy, 0.35 + 0.15 * j) + Vector((sx * 0.14, 0, 0)), (sx, 0, 0)) for j in range(2)] +
                    [(leg(sx, sy, 0.35 + 0.15 * j) + Vector((0, sy * 0.14, 0)), (0, sy, 0)) for j in range(2)],
                    "chrome_pitted", r=0.016, h=0.012)
    levels = [0.4, 2.76, 5.76, HT - 0.12]
    for z in levels[1:]:
        for sy in (-1, 1):
            W.bar(ctx, "girt", leg(-1, sy, z) + Vector((0, sy * 0.14, 0)), leg(1, sy, z) + Vector((0, sy * 0.14, 0)), 0.1, 0.22, tim,
                  up=(0, sy, 0), ext=0.12, patches=0.5)
        for sx in (-1, 1):
            W.bar(ctx, "girt", leg(sx, -1, z) + Vector((sx * 0.14, 0, 0)), leg(sx, 1, z) + Vector((sx * 0.14, 0, 0)), 0.1, 0.22, tim,
                  up=(sx, 0, 0), ext=0.12, patches=0.5)
    bolts = []
    for za, zb in zip(levels[:-1], levels[1:]):
        for sy in (-1, 1):
            off = Vector((0, sy * 0.2, 0))
            W.bar(ctx, "brace", leg(-1, sy, za) + off, leg(1, sy, zb) + off, 0.09, 0.16, tim, up=(0, sy, 0), patches=0.5)
            W.bar(ctx, "brace", leg(1, sy, za) + off * 1.6, leg(-1, sy, zb) + off * 1.6, 0.09, 0.16, tim, up=(0, sy, 0), patches=0.5)
            zc = (za + zb) / 2
            bolts.append((Vector((0, sy * (SB + (ST - SB) * zc / HT) + sy * 0.4, zc)), (0, sy, 0)))
        for sx in (-1, 1):
            off = Vector((sx * 0.2, 0, 0))
            W.bar(ctx, "brace", leg(sx, -1, za) + off, leg(sx, 1, zb) + off, 0.09, 0.16, tim, up=(sx, 0, 0), patches=0.5)
            W.bar(ctx, "brace", leg(sx, 1, za) + off * 1.6, leg(sx, -1, zb) + off * 1.6, 0.09, 0.16, tim, up=(sx, 0, 0), patches=0.5)
            zc = (za + zb) / 2
            bolts.append((Vector((sx * (SB + (ST - SB) * zc / HT) + sx * 0.4, 0, zc)), (sx, 0, 0)))
    W.bolts(ctx, "xbolts", bolts, "chrome_pitted", r=0.03, h=0.02)
    # Beams under the stair core's landings (core: x -1.5..0.5, y -2.5..2.5 about the cab centre).
    for z in (2.78, 5.78):
        s = SB + (ST - SB) * (z / HT)
        for x in (-1.42, 0.42):
            W.bar(ctx, "landbeam", (x, -s - 0.1, z), (x, s + 0.1, z), 0.16, 0.24, tim, patches=0.5)
    for y in (-3.0, -1.0, 1.0, 3.0):
        W.bar(ctx, "joist", (-ST - 0.2, y, HT - 0.0), (ST + 0.2, y, HT - 0.0), 0.16, 0.24, tim, patches=0.5)
    W.rod(ctx, "lightning", leg(1, 1, HT) + Vector((0.14, 0.14, 0)), leg(1, 1, 0.3) + Vector((0.14, 0.14, 0)), 0.006,
          "furn_brass", segs=4, smooth=None)
    W.rod(ctx, "groundrod", leg(1, 1, 0.3) + Vector((0.3, 0.3, 0)), leg(1, 1, 0.3) + Vector((0.3, 0.3, -0.25)), 0.01, "furn_brass",
          segs=5)


# ============================================================================================
# Trapper's yard: lean-to, meat cache
# ============================================================================================

def wild_lean_to(ctx: K.Ctx) -> None:
    """Pole lean-to built against a cabin wall (back edge at +Y, against the wall): three bark-on
    posts carrying a front plate, rafters sloping up to a ledger on the wall, a roof of split
    shakes and bark slabs, a little stacked firewood and a sawbuck. Walk-through (no collision)."""
    r = ctx.rnd("leanto")
    L, D, Hf, Hb = 4.0, 2.1, 1.95, 2.55
    bark = "wild_log_bark"
    for i, x in enumerate((-L / 2 + 0.1, 0.0, L / 2 - 0.1)):
        W.pole(ctx, f"post{i}", [(x, -D / 2, -0.02), (x + r.uniform(-0.02, 0.02), -D / 2 + 0.01, Hf * 0.5), (x, -D / 2, Hf)], 0.055,
               bark, r_end=0.045, seed=r.randint(0, 999), wobble=0.015, moss=0.3)
    W.pole(ctx, "plate", [(-L / 2 - 0.15, -D / 2, Hf + 0.03), (0.0, -D / 2 + 0.01, Hf + 0.01), (L / 2 + 0.15, -D / 2, Hf + 0.03)], 0.05,
           bark, r_end=0.045, seed=r.randint(0, 999))
    W.bar(ctx, "ledger", (-L / 2 - 0.1, D / 2 - 0.04, Hb), (L / 2 + 0.1, D / 2 - 0.04, Hb), 0.07, 0.15, "wood_weathered",
          up=(0, 1, 0))
    ang = math.atan2(Hb - Hf, D)
    for k in range(6):
        x = -L / 2 + 0.05 + k * (L - 0.1) / 5
        W.pole(ctx, f"rafter{k}", [(x, -D / 2 - 0.25, Hf + 0.02 - 0.25 * math.tan(ang)), (x, D / 2 - 0.05, Hb + 0.05)], 0.035,
               bark, r_end=0.03, seed=k)
    rows = 5
    span = D / math.cos(ang) + 0.3
    for k in range(rows):
        sk = (k + 0.5) * span / rows
        yy = -D / 2 - 0.3 + sk * math.cos(ang)
        zz = Hf - 0.3 * math.tan(ang) + sk * math.sin(ang) + 0.06 + 0.012 * k
        for j in range(6):
            w = (L + 0.4) / 6
            sh = K.box(f"shake{k}{j}", (w - 0.02, span / rows + 0.14, 0.022), cuts=(2, 0, 0))
            K.noise_disp(sh, 0.008, scale=6.0, seed=k * 7 + j)
            K.place(sh, rot=(math.degrees(ang) + r.uniform(-2, 2), r.uniform(-3, 3), r.uniform(-2, 2)))
            K.place(sh, (-L / 2 - 0.2 + (j + 0.5) * w, yy, zz))
            ctx.add(sh, "wood_weathered" if (j + k) % 3 else "wild_log_bark", long_axis=1, patches=0.6,
                    moss=0.75 if ctx.worn else 0.45)
    k = 0
    for row, (n, z) in enumerate(((7, 0.0), (6, 0.16), (5, 0.31))):
        for i in range(n):
            x = -1.6 + (i + 0.5 * row) * 0.2
            _split_piece(ctx, f"cord{k}", r.uniform(0.4, 0.45), r.uniform(0.07, 0.09), r.randint(0, 9999),
                         "half" if r.random() < 0.6 else "quarter", (x, D / 2 - 0.3, z + 0.07), (r.uniform(-180, 180), 0, 90))
            k += 1
    for s in (-1, 1):  # sawbuck
        W.bar(ctx, "buckleg", (0.9 + s * 0.25, -0.2, 0.0), (0.9 - s * 0.05, -0.2, 0.85), 0.06, 0.06, "wood_weathered",
              up=(0, 1, 0))
        W.bar(ctx, "buckleg2", (0.9 + s * 0.25, 0.3, 0.0), (0.9 - s * 0.05, 0.3, 0.85), 0.06, 0.06, "wood_weathered",
              up=(0, 1, 0))
    W.bar(ctx, "buckrail", (0.9, -0.25, 0.4), (0.9, 0.35, 0.4), 0.05, 0.05, "wood_weathered")


def wild_meat_cache(ctx: K.Ctx) -> None:
    """Trapper's raised cache: a plank box-house on four peeled poles wrapped in tin against
    climbing animals, a little shed roof, a door at the top of a pole ladder leaning on it."""
    r = ctx.rnd("cache")
    S, Z0 = 1.3, 2.6
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.pole(ctx, f"stilt{sx}{sy}", [(sx * 0.55, sy * 0.55, -0.02), (sx * 0.56, sy * 0.54, Z0 * 0.5), (sx * 0.55, sy * 0.55, Z0 + 0.05)],
                   0.075, "wood_weathered", r_end=0.065, seed=r.randint(0, 999), wobble=0.02, moss=0.3)
            tin = K.cyl("tin", 0.09, 0.6, segs=12, center=(sx * 0.55, sy * 0.55, 1.2), caps=False)
            ctx.add(tin, "metal_galvanized", uv="cyl", uv_scale=1.5, smooth=40, patches=0.6)
    for sy in (-1, 1):
        W.bar(ctx, "sill", (-0.75, sy * 0.55, Z0), (0.75, sy * 0.55, Z0), 0.12, 0.12, "wood_weathered")
    floor = K.box("floor", (S + 0.1, S + 0.1, 0.05), center=(0, 0, Z0 + 0.085))
    ctx.add(floor, "wood_weathered", long_axis=0, patches=0.6)

    def top(t):
        return Z0 + 1.15 + 0.2 * t
    sides = [((-S / 2, -S / 2 - 0.01, 0), (S / 2, -S / 2 - 0.01, 0), (0, -1, 0), lambda t: top(0.0)),
             ((-S / 2, S / 2 + 0.01, 0), (S / 2, S / 2 + 0.01, 0), (0, 1, 0), lambda t: top(1.0)),
             ((-S / 2 - 0.01, -S / 2, 0), (-S / 2 - 0.01, S / 2, 0), (-1, 0, 0), top),
             ((S / 2 + 0.01, -S / 2, 0), (S / 2 + 0.01, S / 2, 0), (1, 0, 0), top)]
    for k, (a, b, n, fn) in enumerate(sides):
        _board_wall(ctx, f"wall{k}", a, b, Z0 + 0.1, fn, n, r=r, skip=(3, 4) if k == 0 else ())
    door = []
    for i in range(2):
        x = -0.08 + i * 0.16
        door.append(W.bar(ctx, f"door{i}", (x, -S / 2 - 0.035, Z0 + 0.12), (x, -S / 2 - 0.035, Z0 + 1.0), 0.15, 0.02, "wood_weathered",
                          up=(0, -1, 0)))
    if ctx.worn:
        _rot_about(door, (-0.16, -S / 2 - 0.035, 0), (0, 0, -60))
    ang = math.degrees(math.atan2(0.2, S))
    roof = K.box("roof", (S + 0.5, S + 0.5, 0.03))
    K.place(roof, rot=(-ang * -1, 0, 0))
    K.place(roof, (0, 0, top(0.5) + 0.06))
    ctx.add(roof, "wild_tarpaper", uv_scale=1.0, patches=0.4, moss=0.6 if ctx.worn else 0.3)
    for s in (-1, 1):
        W.pole(ctx, f"rail{s}", [(s * 0.22, -S / 2 - 1.3, 0.0), (s * 0.2, -S / 2 - 0.08, Z0 + 0.4)], 0.035, "wood_weathered",
               r_end=0.03, seed=s + 3)
    for k in range(7):
        z = 0.35 + k * 0.38
        t = z / (Z0 + 0.4)
        y = -S / 2 - 1.3 + (1.3 - 0.08) * t
        W.rod(ctx, f"rung{k}", (-0.22, y, z), (0.22, y, z), 0.018, "wood_weathered", segs=6)
    ctx.col_box((-0.65, -0.65, 0), (0.65, 0.65, Z0 + 1.4))


BUILDERS = {
    "wild_bunk_steel": wild_bunk_steel,
    "wild_wood_stove": wild_wood_stove,
    "wild_cook_range": wild_cook_range,
    "wild_mess_table": wild_mess_table,
    "wild_mess_bench": wild_mess_bench,
    "wild_locker_steel": wild_locker_steel,
    "wild_footlocker": wild_footlocker,
    "wild_tool_chest": wild_tool_chest,
    "wild_ammo_box": wild_ammo_box,
    "wild_safe_floor": wild_safe_floor,
    "wild_cot_canvas": wild_cot_canvas,
    "wild_oil_lantern": wild_oil_lantern,
    "wild_oil_lantern_hanging": wild_oil_lantern_hanging,
    "wild_washstand": wild_washstand,
    "wild_enamel_dishes": wild_enamel_dishes,
    "wild_firewood_stack": wild_firewood_stack,
    "wild_caulk_boots": wild_caulk_boots,
    "wild_fire_finder": wild_fire_finder,
    "wild_radio_set": wild_radio_set,
    "wild_gun_rack": wild_gun_rack,
    "wild_leg_trap": wild_leg_trap,
    "wild_pelt_board": wild_pelt_board,
    "wild_crosscut_saw": wild_crosscut_saw,
    "wild_smoking_rack": wild_smoking_rack,
    "wild_chopping_block": wild_chopping_block,
    "wild_canoe": wild_canoe,
    "wild_outhouse": wild_outhouse,
    "wild_smokehouse": wild_smokehouse,
    "wild_lookout_tower": wild_lookout_tower,
    "wild_lean_to": wild_lean_to,
    "wild_meat_cache": wild_meat_cache,
}


def build(params: dict, outputs: list[str]) -> None:
    K.run(params, outputs, BUILDERS)
