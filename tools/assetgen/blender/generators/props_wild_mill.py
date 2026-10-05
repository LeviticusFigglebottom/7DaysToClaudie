"""Wilderness props family — the Larch Hollow sawmill and its yard: a band headrig, the log
carriage on its track, live roller tables, an edger, a waste drag conveyor and a belt drive
from the basement, sawdust heaps, stickered lumber, a cold log deck, a chain hoist on its beam,
the saw filer's bench, loose band and circle saw blades, a peavey, a choker cable and a wrecked
rubber-tyred skidder.

Mill machines read from the floor at eye height: frames, guards, belts, chains, bolts and saw
teeth are modelled, not painted. Conventions (docs/ASSET_PIPELINE.md): metres, Z up, front -Y,
origin bottom centre. The headrig's cutting span faces -Y (the carriage); the carriage's knees
face +Y (the saw): place the carriage 1.36 m in front of the headrig (see game/data/props/wild.json).
"""
from __future__ import annotations

import math

from mathutils import Matrix, Vector

from lib import props_ext_kit as K
from lib import props_ext_parts as P
from lib import props_wild_parts as W


def _rot_about(objs, pivot, rot) -> None:
    p = Vector(pivot)
    m = Matrix.Translation(p) @ K.rot_matrix(rot) @ Matrix.Translation(-p)
    for o in objs if isinstance(objs, (list, tuple)) else [objs]:
        if o is not None:
            o.data.transform(m)
            o.data.update()


def _move(objs, delta) -> None:
    m = Matrix.Translation(Vector(delta))
    for o in objs if isinstance(objs, (list, tuple)) else [objs]:
        if o is not None:
            o.data.transform(m)
            o.data.update()


def _dust(ctx, r, n, area, z=0.0, mat="wild_sawdust", h=0.05):
    """Low drifts of sawdust on a machine base or the floor."""
    (x0, y0, x1, y1) = area
    for k in range(n):
        d = K.blob(f"dust{k}", 0.5, subdiv=2, scale=(r.uniform(0.25, 0.6), r.uniform(0.2, 0.45), h * 2), rough=0.35,
                   seed=r.randint(0, 999), center=(r.uniform(x0, x1), r.uniform(y0, y1), z))
        K.cut_plane(d, (0, 0, z + 0.002), (0, 0, -1), keep="below")
        ctx.add(d, mat, uv_scale=1.0, smooth=50, patches=0.0, edge=0.0)


def _toothed_disc(name, R, teeth, depth, t, hook=0.35):
    """Circular saw outline (XZ plane, thickness t along Y): hook teeth around radius R."""
    pts = []
    for k in range(teeth):
        a0 = math.tau * k / teeth
        a1 = math.tau * (k + 1) / teeth
        pts.append(((R - depth) * math.cos(a0), (R - depth) * math.sin(a0)))
        am = a0 + (a1 - a0) * (1 - hook)
        pts.append((R * math.cos(am), R * math.sin(am)))
    return K.prism(name, pts, t, plane="XZ")


# ============================================================================================
# Band headrig
# ============================================================================================

def wild_headrig_saw(ctx: K.Ctx) -> None:
    """Vertical band headrig: cast bed plate, twin columns carrying the upper wheel (spoked, rubber
    tyre, guarded at the back), the lower wheel inside a sheet-steel housing, the band with its
    toothed cutting span facing the carriage (-Y) and the slack back span, upper guide arm with a
    handwheel, strain lever and counterweight, a sawdust chute, the sawyer's levers.
    Worn: rust, the band snapped and curled off the guides, sawdust drifted on the bed."""
    r = ctx.rnd("headrig")
    green = "wild_paint_mill_green"
    iron = "wild_cast_iron" if ctx.clean else "wild_cast_iron_rust"
    R, ZU, ZL = 0.72, 2.0, 0.36
    bed = K.box("bed", (0.95, 2.0, 0.12), center=(0, 0, 0.06), bevel=0.01, cuts=(1, 3, 0))
    ctx.add(bed, iron, uv_scale=1.0, patches=0.5, low=0.6, low_h=0.12)
    W.bolts(ctx, "bedbolts", [((sx * 0.42, sy * 0.92, 0.12), (0, 0, 1)) for sx in (-1, 1) for sy in (-1, -0.3, 0.3, 1)],
            "chrome_pitted", r=0.02, h=0.016)
    for sx in (-1, 1):
        col = K.box("column", (0.18, 0.32, ZU + 0.18 - 0.12), center=(sx * 0.34, 0.06, 0.12 + (ZU + 0.18 - 0.12) / 2), bevel=0.02,
                    cuts=(0, 0, 3))
        ctx.add(col, green, uv_scale=1.0, patches=0.33, edge=0.7, low=0.5, low_h=0.5)
        for z in (ZU, ZL + 0.5):
            brg = K.box("bearing", (0.22, 0.34, 0.2), center=(sx * 0.34, 0.0, z), bevel=0.025)
            ctx.add(brg, iron, uv_scale=1.0, patches=0.5, edge=1.4)
            W.bolts(ctx, "capbolts", [((sx * 0.34 + dx, -0.17, z + 0.06), (0, -1, 0)) for dx in (-0.06, 0.06)], "chrome_pitted",
                    r=0.014, h=0.012)
    W.rod(ctx, "axle", (-0.46, 0.0, ZU), (0.46, 0.0, ZU), 0.045, "wild_saw_steel", segs=12)
    # Upper wheel (plane YZ, axle X).
    rim = W.ring_obj("rim", R - 0.07, R - 0.01, 0.2, segs=36, bevel=0.01)
    tyre = W.ring_obj("tyre", R - 0.012, R + 0.012, 0.19, segs=36, bevel=0.006)
    spokes = W.spokes_obj("spokes", 0.12, R - 0.06, 6, 0.08, 0.05, phase=r.uniform(0, 1), curve=0.18)
    hub = K.cyl("hub", 0.13, 0.26, segs=16)
    for o in (rim, tyre, spokes, hub):
        K.place(o, rot=(0, 90, 0))
        K.place(o, (0, 0, ZU))
    ctx.add(rim, iron, uv_scale=1.5, smooth=40, patches=0.5, edge=1.4)
    ctx.add(tyre, "rubber_black", uv_scale=2.0, smooth=40, patches=0.3)
    ctx.add(spokes, iron, uv_scale=1.5, smooth=40, patches=0.5)
    ctx.add(hub, iron, uv="cyl", uv_axis=0, uv_scale=1.5, smooth=40, patches=0.5)
    # Upper guard: curved sheet band over the back half plus side plates.
    a0, a1 = math.radians(-70), math.radians(115)
    band_pts = []
    for k in range(13):
        a = a0 + (a1 - a0) * k / 12
        band_pts.append((math.cos(a), math.sin(a)))
    guard = K.grid("guard", 1.0, 1.0, 12, 2)
    gme = guard.data
    for v in gme.vertices:
        u = (v.co.x + 0.5)
        w = (v.co.y + 0.5)
        a = a0 + (a1 - a0) * u
        v.co = Vector(((w - 0.5) * 0.3, (R + 0.07) * math.cos(a), ZU + (R + 0.07) * math.sin(a)))
    gme.update()
    K.uv_planar(guard, 0, scale=1.0)
    K.solidify(guard, 0.006, even=False)
    ctx.add(guard, green, uv=None, smooth=40, patches=0.33, edge=0.7)
    for sx in (-1, 1):
        out = [(0.0, 0.0)] + [((R + 0.07) * math.cos(a0 + (a1 - a0) * k / 12), (R + 0.07) * math.sin(a0 + (a1 - a0) * k / 12))
                              for k in range(13)]
        side = K.prism("guardside", out, 0.006, plane="YZ")
        K.place(side, (sx * 0.15, 0.0, ZU))
        ctx.add(side, green, uv_scale=1.0, patches=0.33, edge=0.7)
    # Lower wheel housing (the lower wheel turns inside, half in the pit).
    hous = K.box("housing", (0.34, 1.66, 1.0), center=(0, 0, 0.12 + 0.5), bevel=0.05, bevel_segs=2)
    ctx.add(hous, green, uv_scale=1.0, patches=0.33, edge=0.7, low=0.6, low_h=0.4)
    door = K.box("hdoor", (0.012, 0.8, 0.55), center=(0.176, 0.0, 0.62), bevel=0.01)
    ctx.add(door, green, uv_scale=1.0, patches=0.39, edge=0.7)
    W.bolts(ctx, "doorbolts", [((0.184, y, z), (1, 0, 0)) for y in (-0.36, 0.36) for z in (0.4, 0.85)], "chrome_pitted", r=0.012,
            h=0.01)
    # Band: cutting span (teeth toward -X, the incoming log), back span, the run over the wheel.
    yb = -(R + 0.014)
    span = []
    n = 34
    for k in range(n + 1):
        z = 1.12 + (ZU - 1.12) * k / n
        span.append((-0.1 - (0.02 if k % 2 else 0.0), z))
    span += [(0.07, ZU), (0.07, 1.12)]
    cut = K.prism("band", span, 0.002, plane="XZ")
    K.place(cut, (0, yb, 0))
    band_parts = [ctx.add(cut, "wild_saw_steel", uv_scale=1.0, patches=0.3, edge=0.5)]
    back = K.box("bandback", (0.17, 0.002, ZU - 1.12), center=(-0.015, R + 0.014, (ZU + 1.12) / 2))
    band_parts.append(ctx.add(back, "wild_saw_steel", uv_scale=1.0, patches=0.3))
    top = K.grid("bandtop", 1.0, 1.0, 14, 1)
    tme = top.data
    for v in tme.vertices:
        u = v.co.x + 0.5
        w = v.co.y + 0.5
        a = math.pi - math.pi * u
        v.co = Vector((-0.1 + 0.17 * w, (R + 0.014) * math.cos(a), ZU + (R + 0.014) * math.sin(a)))
    tme.update()
    K.uv_planar(top, 0, scale=1.0)
    K.solidify(top, 0.002, even=False)
    band_parts.append(ctx.add(top, "wild_saw_steel", uv=None, smooth=40, patches=0.3))
    if ctx.worn:
        # Snapped: the cutting span hangs in a curl off the guides.
        K.map_verts(cut, lambda co: co if co.z > 1.6 else Vector((co.x, co.y - 0.35 * ((1.6 - co.z) / 0.48) ** 2,
                                                                     1.6 - (1.6 - co.z) * 0.7)))
    # Guide arm with guide blocks and a handwheel, strain lever with counterweight.
    W.bar(ctx, "guidebar", (-0.3, yb + 0.02, 1.25), (-0.3, yb + 0.02, 2.62), 0.08, 0.08, green)
    W.bar(ctx, "guidearm", (-0.3, yb + 0.02, 1.3), (-0.02, yb + 0.02, 1.3), 0.06, 0.07, green)
    for s in (-1, 1):
        gb = K.box("guideblock", (0.1, 0.03, 0.08), center=(-0.03, yb + s * 0.018, 1.3), bevel=0.004)
        ctx.add(gb, iron, uv_scale=2.0)
    W.bar(ctx, "guidebracket", (-0.3, yb + 0.02, 2.4), (-0.3, 0.0, 2.4), 0.06, 0.06, green)
    hw = W.ring_obj("handwheel", 0.11, 0.13, 0.025, segs=18)
    K.place(hw, (-0.3, yb + 0.02, 2.66))
    ctx.add(hw, iron, uv_scale=2.0, smooth=40)
    ctx.add(W.spokes_obj("hwspokes", 0.0, 0.115, 4, 0.015, 0.015), iron, uv_scale=2.0, at=((-0.3, yb + 0.02, 2.66),))
    lever = W.bar(ctx, "strain", (0.42, 0.0, ZU - 0.2), (0.42, 1.05, ZU - 0.55), 0.06, 0.08, iron)
    wt = K.cyl("weight", 0.16, 0.22, segs=16, center=(0.42, 1.0, ZU - 0.85))
    ctx.add(wt, iron, uv="cyl", uv_scale=1.5, smooth=40, patches=0.5)
    W.rod(ctx, "weightrod", (0.42, 1.0, ZU - 0.55), (0.42, 1.0, ZU - 0.74), 0.015, "chrome_pitted", segs=6)
    # Sawdust chute under the cutting span, levers on the +X column.
    chute = K.prism("chute", [(-0.95 * 0.0 - 0.0, 0.0), (0.3, 0.0), (0.3, 0.02), (0.02, 0.32), (0.0, 0.32)], 0.3, plane="YZ")
    K.place(chute, (-0.02, yb - 0.04, 0.0))
    _rot_about(chute, (-0.02, yb, 0.0), (0, 0, 0))
    ctx.add(chute, green, uv_scale=1.0, patches=0.39)
    for k in range(2):
        W.rod(ctx, f"lever{k}", (0.45, -0.25 + k * 0.12, 0.95), (0.6, -0.3 + k * 0.12, 1.45), 0.012, "chrome_pitted", segs=6)
        kn = K.blob("knob", 0.025, subdiv=1, center=(0.6, -0.3 + k * 0.12, 1.47))
        ctx.add(kn, "plastic_black", uv_scale=2.0, smooth=50)
    W.bar(ctx, "leverbox", (0.43, -0.32, 0.95), (0.43, -0.08, 0.95), 0.08, 0.08, iron)
    _dust(ctx, r, 3 if ctx.clean else 6, (-0.45, -1.0, 0.45, 0.9), z=0.12, h=0.04)
    ctx.col_box((-0.48, -1.0, 0), (0.48, 1.0, 2.8))


# ============================================================================================
# Log carriage on its track
# ============================================================================================

def wild_log_carriage(ctx: K.Ctx) -> None:
    """Sawmill carriage on a 6 m track (rails on creosoted ties): channel frame on flanged wheels,
    three head blocks with knees and dogs facing the saw (+Y), the setworks shaft and ratchet, the
    rider's platform with a railing and levers at -X, and a fir log dogged on the blocks with one
    face sawn. Worn: rust on everything, sawdust in the frame, the dogs thrown open."""
    r = ctx.rnd("carriage")
    iron = "wild_cast_iron" if ctx.clean else "wild_cast_iron_rust"
    steel = "wild_paint_red_oxide"
    for i in range(11):
        x = -2.9 + i * 0.58
        tie = K.box("tie", (0.18, 1.3, 0.1), center=(x, 0, 0.05), bevel=0.008)
        ctx.add(tie, "wood_creosote", long_axis=1, patches=0.5, moss=0.2)
    rail_prof = [(-0.035, 0.0), (0.035, 0.0), (0.035, 0.01), (0.008, 0.016), (0.008, 0.06), (0.018, 0.064), (0.018, 0.085),
                 (-0.018, 0.085), (-0.018, 0.064), (-0.008, 0.06), (-0.008, 0.016), (-0.035, 0.01)]
    for sy in (-1, 1):
        W.section(ctx, f"rail{sy}", (-3.0, sy * 0.35, 0.1), (3.0, sy * 0.35, 0.1), rail_prof, "wild_saw_steel_rust",
                  patches=0.5)
        W.bolts(ctx, f"spikes{sy}", [((-2.9 + i * 0.58, sy * 0.35 + s * 0.05, 0.1), (0, 0, 1)) for i in range(11) for s in (-1, 1)],
                "item_iron_strap", r=0.012, h=0.012, segs=4)
    zf = 0.44
    for sy in (-1, 1):
        W.section(ctx, f"beam{sy}", (-1.4, sy * 0.35, zf + 0.08), (1.4, sy * 0.35, zf + 0.08), W.prof_c(0.16, 0.08, 0.012),
                  steel, patches=0.6, edge=1.3)
    for x in (-1.3, -0.45, 0.45, 1.3):
        W.bar(ctx, "cross", (x, -0.42, zf + 0.08), (x, 0.42, zf + 0.08), 0.1, 0.14, steel, patches=0.6)
    for sx in (-1, 1):
        for sy in (-1, 1):
            wh = K.lathe("wheel", [(0.0, -0.04), (0.12, -0.04), (0.12, 0.03), (0.148, 0.036), (0.148, 0.046), (0.0, 0.046)], segs=18)
            K.place(wh, rot=(-90 * sy, 0, 0))
            K.place(wh, (sx * 1.05, sy * 0.35, 0.185 + 0.12))
            ctx.add(wh, iron, uv_scale=1.5, smooth=40, patches=0.5)
            box = K.box("axlebox", (0.22, 0.12, 0.14), center=(sx * 1.05, sy * 0.35, zf - 0.02), bevel=0.012)
            ctx.add(box, iron, uv_scale=1.5, patches=0.5)
    deck = []
    for x in (-0.9, 0.0, 0.9):
        hb = K.box("headblock", (0.26, 0.72, 0.18), center=(x, 0.12, zf + 0.25), bevel=0.015)
        ctx.add(hb, iron, uv_scale=1.0, patches=0.5, edge=1.4)
        knee = K.box("knee", (0.2, 0.07, 0.8), center=(x, 0.02, zf + 0.34 + 0.4), bevel=0.01)
        ctx.add(knee, "wild_saw_steel_rust", uv_scale=1.0, patches=0.5, edge=1.2)
        dog_z = zf + 1.12 if ctx.clean else zf + 1.22
        dog = K.tube("dog", [(x, 0.06, zf + 1.0), (x, 0.12, dog_z), (x, 0.24, dog_z + 0.04), (x, 0.32, dog_z - 0.02)],
                     0.022, segs=6, flat=(1.0, 0.6))
        ctx.add(dog, "wild_saw_steel_rust", uv_scale=2.0, smooth=40, patches=0.6)
        W.rod(ctx, "dogslide", (x, 0.0, zf + 0.4), (x, 0.0, zf + 1.18), 0.018, "chrome_pitted", segs=6)
    W.rod(ctx, "setshaft", (-1.5, -0.32, zf + 0.3), (1.2, -0.32, zf + 0.3), 0.035, "wild_saw_steel", segs=10)
    ratchet = _toothed_disc("ratchet", 0.16, 24, 0.025, 0.04, hook=0.5)
    K.place(ratchet, rot=(0, 0, 90))
    K.place(ratchet, (-1.45, -0.32, zf + 0.3))
    ctx.add(ratchet, iron, uv_scale=1.5, patches=0.5)
    # Rider's platform at -X.
    for k in range(5):
        y = -0.5 + k * 0.25
        pl = P.plank(f"deck{k}", 0.9, 0.23, 0.04)
        K.place(pl, (-1.75, y, zf + 0.18))
        ctx.add(pl, "wild_lumber_weathered", long_axis=0, patches=0.6)
    for y in (-0.55, 0.5):
        W.bar(ctx, "railpost", (-2.15, y, zf + 0.2), (-2.15, y, zf + 1.15), 0.05, 0.05, steel)
    W.rod(ctx, "railtop", (-2.15, -0.55, zf + 1.15), (-2.15, 0.5, zf + 1.15), 0.02, steel, segs=8)
    for k in range(3):
        W.rod(ctx, f"rlever{k}", (-1.55, -0.35 + k * 0.12, zf + 0.25), (-1.65, -0.4 + k * 0.12, zf + 1.05), 0.012, "chrome_pitted",
              segs=6)
        kn = K.blob("knob", 0.024, subdiv=1, center=(-1.65, -0.4 + k * 0.12, zf + 1.07))
        ctx.add(kn, "plastic_black", uv_scale=2.0, smooth=50)
    # The log: dogged against the knees, the saw-side face cut flat.
    log = W.log_obj("log", 3.4, 0.32, r.randint(0, 9999), sides=16, rings=9, taper=0.1, bow=0.03,
                    cut_face=((0, 1, 0), 0.22), knots=3)
    K.place(log, (0.1, 0.07 + 0.32, zf + 0.34 + 0.32))
    ctx.add(log, None, uv=None, smooth=50, patches=0.3, edge=0.6, moss=0.0 if ctx.clean else 0.2)
    if ctx.worn:
        _dust(ctx, r, 5, (-2.5, -0.5, 2.5, 0.5), z=0.1, h=0.03)
    ctx.col_box((-3.0, -0.7, 0), (3.0, 0.72, 1.45))


# ============================================================================================
# Live rolls, waste conveyor, belt drive
# ============================================================================================

def wild_roller_conveyor(ctx: K.Ctx) -> None:
    """Live roll table section: channel side frames on angle legs, eight steel rolls with
    sprockets and a chain guard on the +Y side. Worn: rust, a few boards left across the rolls."""
    r = ctx.rnd("rolls")
    L, Wd, Z = 2.0, 0.76, 0.8
    green = "wild_paint_mill_green"
    for sy in (-1, 1):
        W.section(ctx, f"side{sy}", (-L / 2, sy * Wd / 2, Z - 0.06), (L / 2, sy * Wd / 2, Z - 0.06), W.prof_c(0.15, 0.06, 0.008),
                  green, patches=0.33, edge=0.7)
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.section(ctx, "leg", (sx * (L / 2 - 0.12), sy * (Wd / 2 - 0.02), 0.0), (sx * (L / 2 - 0.12), sy * (Wd / 2 - 0.02), Z - 0.13),
                      W.prof_l(0.05, 0.006), green, up=(sx, 0, 0), patches=0.33, low=0.8, low_h=0.3)
            foot = K.box("foot", (0.1, 0.1, 0.01), center=(sx * (L / 2 - 0.12), sy * (Wd / 2 - 0.02), 0.005))
            ctx.add(foot, green, uv_scale=2.0)
        W.bar(ctx, "brace", (sx * (L / 2 - 0.12), -Wd / 2, 0.3), (sx * (L / 2 - 0.12), Wd / 2, 0.3), 0.04, 0.04, green)
    for i in range(8):
        x = -L / 2 + 0.125 + i * 0.25
        roll = K.cyl("roll", 0.06, Wd - 0.06, segs=14, axis="Y", center=(x, 0, Z))
        ctx.add(roll, "wild_saw_steel_rust" if not ctx.clean else "wild_saw_steel", uv="cyl", uv_axis=1, uv_scale=1.5, smooth=40,
                patches=0.5)
        W.rod(ctx, f"stub{i}", (x, -Wd / 2 - 0.02, Z), (x, Wd / 2 + 0.06, Z), 0.018, "chrome_pitted", segs=6)
        sp = _toothed_disc(f"sprocket{i}", 0.075, 14, 0.012, 0.01)
        K.place(sp, rot=(0, 0, 0))
        K.place(sp, (x, Wd / 2 + 0.04, Z))
        ctx.add(sp, "wild_cast_iron", uv_scale=2.0, patches=0.5)
    guard = K.box("chainguard", (L, 0.06, 0.24), center=(0, Wd / 2 + 0.09, Z), bevel=0.01)
    ctx.add(guard, "wild_paint_skidder_yellow", uv_scale=1.0, patches=0.39, edge=0.7)
    if ctx.worn:
        for k in range(3):
            b = P.plank(f"board{k}", r.uniform(1.6, 2.4), 0.19, 0.045, cuts=3, bow=r.uniform(0.0, 0.02))
            K.place(b, (r.uniform(-0.3, 0.3), r.uniform(-0.2, 0.2), Z + 0.085 + 0.046 * k), (0, 0, r.uniform(-12, 12)))
            ctx.add(b, "wild_lumber_weathered", long_axis=0, patches=0.6)
    ctx.col_box((-L / 2, -Wd / 2 - 0.05, 0), (L / 2, Wd / 2 + 0.13, Z + 0.07))


def wild_waste_conveyor(ctx: K.Ctx) -> None:
    """Basement drag conveyor: a steel trough on legs carrying slabs, bark and sawdust to the
    burner, the flighted drag chain in the trough and its return run below, a head sprocket and
    guard. Worn: choked with sawdust, rusted through at the bottom."""
    r = ctx.rnd("waste")
    L, Wd, Z = 3.0, 0.52, 0.8
    paint = "wild_paint_mill_grey"
    trough = K.prism("trough", [(-Wd / 2, 0.0), (Wd / 2, 0.0), (Wd / 2, 0.36), (Wd / 2 - 0.008, 0.36), (Wd / 2 - 0.008, 0.008),
                                (-Wd / 2 + 0.008, 0.008), (-Wd / 2 + 0.008, 0.36), (-Wd / 2, 0.36)], L, plane="YZ")
    K.place(trough, (0, 0, Z - 0.36))
    ctx.add(trough, paint, long_axis=0, patches=0.39, edge=0.7)
    for x in (-1.3, -0.4, 0.5, 1.3):
        for sy in (-1, 1):
            W.bar(ctx, "leg", (x, sy * (Wd / 2 + 0.03), 0.0), (x, sy * (Wd / 2 + 0.03), Z - 0.3), 0.06, 0.06, paint, low=0.8,
                  low_h=0.3)
        W.bar(ctx, "saddle", (x, -Wd / 2 - 0.06, Z - 0.37), (x, Wd / 2 + 0.06, Z - 0.37), 0.06, 0.04, paint)
    pts = [(-L / 2 + 0.1, 0.0, Z - 0.34), (L / 2 - 0.1, 0.0, Z - 0.34)]
    ctx.add(W.chain_obj("drag", pts, link=0.12, wire=0.009, sides=3), "item_iron_strap", uv_scale=3.0, smooth=40, patches=0.7)
    ret = [(-L / 2 + 0.1, 0.0, Z - 0.48), (L / 2 - 0.1, 0.0, Z - 0.48)]
    ctx.add(W.chain_obj("return", ret, link=0.12, wire=0.009, sides=3), "item_iron_strap", uv_scale=3.0, smooth=40, patches=0.7)
    for k in range(7):
        x = -L / 2 + 0.3 + k * 0.4
        fl = K.box("flight", (0.012, Wd - 0.04, 0.08), center=(x, 0, Z - 0.3))
        ctx.add(fl, "item_iron_strap", uv_scale=2.0, patches=0.6)
    for sx in (-1, 1):
        sp = _toothed_disc("headsprocket", 0.13, 12, 0.02, 0.03)
        K.place(sp, (sx * (L / 2 - 0.05), 0.0, Z - 0.41))
        ctx.add(sp, "wild_cast_iron", uv_scale=2.0, patches=0.5)
        W.rod(ctx, "shaft", (sx * (L / 2 - 0.05), -Wd / 2 - 0.1, Z - 0.41), (sx * (L / 2 - 0.05), Wd / 2 + 0.1, Z - 0.41), 0.03,
              "chrome_pitted", segs=8)
    fill = K.blob("fill", 0.5, subdiv=3, scale=(L - 0.3, Wd - 0.06, 0.4 if ctx.worn else 0.2), rough=0.25, seed=r.randint(0, 99),
                  center=(0, 0, Z - 0.35))
    K.cut_plane(fill, (0, 0, Z - 0.35), (0, 0, -1), keep="below")
    ctx.add(fill, "wild_sawdust_old" if ctx.worn else "wild_sawdust", uv_scale=1.0, smooth=50, patches=0.0, edge=0.0)
    for k in range(4):
        sl = K.box(f"slab{k}", (r.uniform(0.5, 0.9), 0.12, 0.03), center=(r.uniform(-1.0, 1.0), r.uniform(-0.1, 0.1),
                                                                           Z - 0.2 + 0.03 * k), cuts=(3, 0, 0))
        K.place(sl, rot=(0, 0, 0))
        ctx.add(sl, "wild_log_bark", uv_scale=1.0, patches=0.3)
    ctx.col_box((-L / 2, -Wd / 2 - 0.1, 0), (L / 2, Wd / 2 + 0.1, Z))


def wild_belt_drive(ctx: K.Ctx) -> None:
    """Basement belt drive: a ribbed electric motor on a concrete pad turning a flat leather belt
    up through a rough guard to a line-shaft pulley hung from the ceiling joists (2.75 m).
    Worn: belt thrown off and hanging slack."""
    r = ctx.rnd("beltdrive")
    pad = K.box("pad", (0.9, 0.62, 0.15), center=(0, 0, 0.075), bevel=0.02)
    ctx.add(pad, "concrete_barrier", uv_scale=1.0, patches=0.5)
    mz = 0.15 + 0.22
    motor = K.cyl("motor", 0.2, 0.46, segs=20, axis="X", center=(-0.05, 0, mz))
    ctx.add(motor, "wild_paint_mill_grey", uv="cyl", uv_axis=0, uv_scale=1.5, smooth=45, patches=0.33, edge=0.7)
    for k in range(8):
        rib = W.ring_obj("rib", 0.19, 0.225, 0.012, segs=20)
        K.place(rib, rot=(0, 90, 0))
        K.place(rib, (-0.24 + k * 0.055, 0, mz))
        ctx.add(rib, "wild_paint_mill_grey", uv_scale=2.0, smooth=40, patches=0.33)
    for sx in (-1, 1):
        bell = K.lathe("bell", [(0.0, 0.0), (0.2, 0.0), (0.17, 0.06), (0.06, 0.08), (0.0, 0.08)], segs=18)
        K.place(bell, rot=(0, 90 * sx, 0))
        K.place(bell, (-0.05 + sx * 0.23, 0, mz))
        ctx.add(bell, "wild_cast_iron", uv_scale=1.5, smooth=40, patches=0.5)
    for sy in (-1, 1):
        foot = K.box("mfoot", (0.4, 0.06, 0.16), center=(-0.05, sy * 0.15, 0.15 + 0.08))
        ctx.add(foot, "wild_cast_iron", uv_scale=1.5)
    W.rod(ctx, "mshaft", (0.18, 0, mz), (0.42, 0, mz), 0.025, "wild_saw_steel", segs=8)
    pul = K.cyl("pulley", 0.13, 0.13, segs=18, axis="X", center=(0.34, 0, mz))
    ctx.add(pul, "wild_cast_iron", uv="cyl", uv_axis=0, uv_scale=1.5, smooth=40)
    zt = 2.62
    W.rod(ctx, "lineshaft", (-0.6, 0.0, zt), (0.9, 0.0, zt), 0.035, "wild_saw_steel_rust", segs=10)
    tp = K.cyl("toppulley", 0.18, 0.15, segs=20, axis="X", center=(0.34, 0, zt))
    ctx.add(tp, "wild_cast_iron", uv="cyl", uv_axis=0, uv_scale=1.5, smooth=40)
    for x in (-0.45, 0.75):
        W.bar(ctx, "hanger", (x, 0, zt), (x, 0, 2.8), 0.06, 0.05, "wild_cast_iron")
        brg = K.box("hbearing", (0.1, 0.12, 0.1), center=(x, 0, zt))
        ctx.add(brg, "wild_cast_iron", uv_scale=1.5)
    if ctx.clean:
        for sy in (-1, 1):
            W.bar(ctx, "belt", (0.34, sy * 0.0 + 0.0, mz), (0.34, 0.0, zt), 0.12, 0.006, "leather_dark", up=(0, 1, 0))
        for sy in (-1, 1):
            b = W.bar(ctx, "beltrun", (0.34, sy * 0.14, mz), (0.34, sy * 0.18, zt), 0.12, 0.006, "leather_dark", up=(0, 1, 0))
    else:
        pts = [(0.34, 0.18, zt), (0.36, 0.25, 1.9), (0.4, 0.2, 1.1), (0.38, 0.1, 0.4), (0.3, -0.1, 0.17), (0.2, -0.3, 0.16)]
        belt = K.tube("slack", pts, 0.05, segs=4, flat=(1.0, 0.08))
        ctx.add(belt, "leather_dark", uv_scale=2.0, smooth=50)
    for sy in (-1, 1):
        W.bar(ctx, "guardpost", (0.55, sy * 0.3, 0.15), (0.55, sy * 0.3, 1.6), 0.04, 0.04, "wild_paint_skidder_yellow")
    mesh = K.box("guardmesh", (0.006, 0.6, 1.4), center=(0.56, 0, 0.88))
    ctx.add(mesh, "chainlink", uv="planar", uv_axis=0, uv_scale=2.0, wear=0.0)
    ctx.col_box((-0.45, -0.31, 0), (0.6, 0.31, 2.8))


# ============================================================================================
# Edger
# ============================================================================================

def wild_edger(ctx: K.Ctx) -> None:
    """Board edger: cast base frame, roll-case infeed and outfeed tables, rubber feed rolls, two
    circle saws on an arbor under a rounded sheet hood, setting levers on the front, the motor and
    V-belt guard at the back. Worn: rust, a jammed board half through, sawdust everywhere."""
    r = ctx.rnd("edger")
    green = "wild_paint_mill_green"
    iron = "wild_cast_iron" if ctx.clean else "wild_cast_iron_rust"
    TZ = 0.8
    base = K.box("base", (1.1, 1.2, TZ - 0.05), center=(0, 0.05, (TZ - 0.05) / 2), bevel=0.03, cuts=(2, 2, 2))
    ctx.add(base, iron, uv_scale=1.0, patches=0.5, edge=1.3, low=0.6, low_h=0.3)
    top = K.box("table", (1.2, 1.0, 0.05), center=(0, -0.05, TZ - 0.025), bevel=0.008)
    ctx.add(top, iron, uv_scale=1.0, patches=0.4, edge=1.5)
    for sx in (-1, 1):
        x0 = sx * 0.6
        for sy in (-1, 1):
            W.section(ctx, "rollside", (x0, sy * 0.45, TZ - 0.06), (x0 + sx * 0.7, sy * 0.45, TZ - 0.06), W.prof_c(0.12, 0.05, 0.006),
                      green, patches=0.33)
            W.bar(ctx, "rleg", (x0 + sx * 0.6, sy * 0.45, 0.0), (x0 + sx * 0.6, sy * 0.45, TZ - 0.12), 0.05, 0.05, green, low=0.8,
                  low_h=0.3)
        for i in range(3):
            x = x0 + sx * (0.12 + i * 0.22)
            ctx.add(K.cyl("roll", 0.05, 0.86, segs=12, axis="Y", center=(x, 0.0, TZ - 0.02)), "wild_saw_steel_rust", uv="cyl",
                    uv_axis=1, uv_scale=1.5, smooth=40, patches=0.5)
    for x in (-0.45, 0.45):
        fr = K.cyl("feedroll", 0.075, 0.9, segs=16, axis="Y", center=(x, -0.05, TZ + 0.12))
        ctx.add(fr, "rubber_black", uv="cyl", uv_axis=1, uv_scale=2.0, smooth=40, patches=0.3)
        for sy in (-1, 1):
            arm = K.box("rollarm", (0.12, 0.05, 0.3), center=(x, sy * 0.5, TZ + 0.18), bevel=0.01)
            ctx.add(arm, iron, uv_scale=1.5)
    hood = K.lathe("hood", [(0.0, -0.5), (0.36, -0.5), (0.38, -0.48), (0.38, 0.5), (0.0, 0.5)], segs=24, arc=math.pi,
                   angle0=0.0, cap_bottom=False, cap_top=False)
    K.place(hood, rot=(90, 0, 0))
    K.place(hood, (0, -0.05, TZ))
    K.solidify(hood, 0.008, even=False)
    ctx.add(hood, green, uv_scale=1.0, smooth=40, patches=0.33, edge=0.7)
    for k, y in enumerate((-0.3, 0.18)):
        saw = _toothed_disc(f"saw{k}", 0.3, 36, 0.025, 0.004)
        K.place(saw, (0, y, TZ - 0.04))
        ctx.add(saw, "wild_saw_steel", uv_scale=1.0, patches=0.3)
        col = K.cyl(f"collar{k}", 0.07, 0.05, segs=12, axis="Y", center=(0, y, TZ - 0.04))
        ctx.add(col, iron, uv_scale=2.0, smooth=40)
    W.rod(ctx, "arbor", (0, -0.62, TZ - 0.04), (0, 0.75, TZ - 0.04), 0.035, "wild_saw_steel", segs=10)
    for k in range(3):
        W.rod(ctx, f"setlever{k}", (-0.3 + k * 0.25, -0.62, TZ - 0.1), (-0.32 + k * 0.25, -0.78, TZ + 0.35), 0.013, "chrome_pitted",
              segs=6)
        kn = K.blob("knob", 0.026, subdiv=1, center=(-0.32 + k * 0.25, -0.79, TZ + 0.37))
        ctx.add(kn, "plastic_black", uv_scale=2.0, smooth=50)
    motor = K.cyl("motor", 0.2, 0.45, segs=18, axis="X", center=(0.1, 0.85, 0.42))
    ctx.add(motor, "wild_paint_mill_grey", uv="cyl", uv_axis=0, uv_scale=1.5, smooth=45, patches=0.33)
    mb = K.box("motorbase", (0.6, 0.4, 0.2), center=(0.1, 0.85, 0.1))
    ctx.add(mb, iron, uv_scale=1.5)
    bg = K.box("beltguard", (0.2, 0.5, 0.75), center=(0.45, 0.7, 0.62), bevel=0.04)
    ctx.add(bg, "wild_paint_skidder_yellow", uv_scale=1.0, patches=0.39, edge=0.7)
    if ctx.worn:
        b = P.plank("jam", 2.4, 0.24, 0.05, cuts=3, bow=0.03)
        K.place(b, (0.2, -0.05, TZ + 0.035), (0, 0, 4))
        ctx.add(b, "wild_lumber_fresh", long_axis=0, patches=0.5)
    _dust(ctx, r, 4 if ctx.clean else 8, (-1.2, -0.7, 1.2, 0.7), z=0.0, h=0.04)
    ctx.col_box((-1.3, -0.8, 0), (1.3, 1.1, TZ + 0.42))


# ============================================================================================
# Sawdust, lumber, logs
# ============================================================================================

def wild_sawdust_pile(ctx: K.Ctx) -> None:
    """Heap of sawdust and shavings under a chute, with bark strips and lumber offcuts half
    buried. Worn: old, grey and caked, moss on the slopes."""
    r = ctx.rnd("sawdust")
    pile = K.blob("pile", 0.5, subdiv=4, scale=(2.0, 1.55, 1.6), rough=0.18, seed=r.randint(0, 999), noise_scale=2.5)
    K.cut_plane(pile, (0, 0, 0.0), (0, 0, -1), keep="below")
    K.map_verts(pile, lambda co: Vector((co.x, co.y, max(0.0, co.z) ** 1.15 * 0.95)))
    K.noise_disp(pile, 0.03, scale=4.0, seed=r.randint(0, 999))
    ctx.add(pile, "wild_sawdust_old" if ctx.worn else "wild_sawdust", uv_scale=1.0, smooth=60, patches=0.0, edge=0.0,
            moss=0.4 if ctx.worn else 0.0)
    for k in range(6):
        a = r.uniform(0, math.tau)
        d = r.uniform(0.35, 0.8)
        z = 0.75 * max(0.0, 1 - (d / 0.95) ** 2) ** 0.8 * 0.9
        if k % 2:
            o = P.plank(f"offcut{k}", r.uniform(0.2, 0.5), r.uniform(0.08, 0.18), 0.04)
            mat = "wild_lumber_fresh" if ctx.clean else "wild_lumber_weathered"
        else:
            o = K.box(f"bark{k}", (r.uniform(0.3, 0.6), 0.1, 0.015), cuts=(3, 0, 0))
            K.map_verts(o, lambda co: Vector((co.x, co.y, co.z + 0.02 * math.sin(co.x * 8))))
            mat = "wild_log_bark"
        K.place(o, (d * math.cos(a), d * math.sin(a) * 0.8, z - 0.02), (r.uniform(-25, 25), r.uniform(-25, 25), r.uniform(0, 360)))
        ctx.add(o, mat, long_axis=0, patches=0.4)
    ctx.col_box((-0.95, -0.75, 0), (0.95, 0.75, 0.6))


def wild_lumber_stack(ctx: K.Ctx) -> None:
    """Stickered stack of rough-sawn 2x8s on timber bunks, banded with steel strapping.
    Worn: grey and weathered, a band burst, the top course slid askew."""
    r = ctx.rnd("lumber")
    wood = "wild_lumber_fresh" if ctx.clean else "wild_lumber_weathered"
    L, bw, bt = 2.44, 0.19, 0.045
    n_across, n_layers = 8, 7
    for x in (-0.95, 0.0, 0.95):
        W.bar(ctx, "bunk", (x, -0.85, 0.045), (x, 0.85, 0.045), 0.09, 0.09, "wood_creosote", patches=0.5)
    z = 0.09
    for layer in range(n_layers):
        skew = (r.uniform(-6, 6) if (ctx.worn and layer == n_layers - 1) else 0.0)
        for i in range(n_across):
            y = -0.8 + i * 0.2 + bw / 2 - 0.005
            top_course = layer == n_layers - 1
            b = P.plank(f"b{layer}_{i}", L + r.uniform(-0.02, 0.02), bw, bt, bevel=0.0, cuts=2 if top_course else 0,
                        bow=r.uniform(0.0, 0.008) if top_course else 0.0)
            K.place(b, (r.uniform(-0.03, 0.03), y, z + bt / 2), (0, 0, skew))
            ctx.add(b, wood, long_axis=0, patches=0.6, edge=1.2, moss=0.3 if ctx.worn and layer == n_layers - 1 else 0.0)
        z += bt
        if layer < n_layers - 1:
            for x in (-1.0, 0.0, 1.0):
                W.bar(ctx, "sticker", (x, -0.82, z + 0.0125), (x, 0.82, z + 0.0125), 0.035, 0.025, "wild_lumber_weathered")
            z += 0.025
    for k, x in enumerate((-0.6, 0.6)):
        if ctx.worn and k == 1:
            W.bar(ctx, "bandloose", (x, -0.83, z + 0.003), (x + 0.3, -1.1, 0.01), 0.02, 0.0015, "metal_galvanized")
            continue
        for a, b in (((x, -0.81, 0.09), (x, -0.81, z + 0.002)), ((x, 0.81, 0.09), (x, 0.81, z + 0.002)),
                     ((x, -0.81, z + 0.002), (x, 0.81, z + 0.002))):
            W.bar(ctx, "band", a, b, 0.02, 0.0015, "metal_galvanized", up=(0, -1, 0) if a[1] == b[1] and a[1] < 0 else (0, 1, 0)
                  if a[1] == b[1] else (0, 0, 1))
    ctx.col_box((-L / 2 - 0.03, -0.85, 0), (L / 2 + 0.03, 0.85, z + 0.01))


def wild_log_deck(ctx: K.Ctx) -> None:
    """Cold deck of fir and larch logs waiting for the mill: three courses on two skid logs,
    ends sawn and staggered, chock blocks and loose bark. Worn: checked ends, moss on the top."""
    r = ctx.rnd("logdeck")
    for sx in (-1, 1):
        sk = W.log_obj("skid", 3.0, 0.16, r.randint(0, 999), sides=10, rings=4, taper=0.05)
        K.place(sk, (sx * 2.0, 0, 0.15), (0, 0, 90))
        ctx.add(sk, None, uv=None, smooth=50, patches=0.4, moss=0.5)
    rows = [(4, 0.3, 0.0), (3, 0.29, 0.0), (2, 0.27, 0.0)]
    base_z = 0.3
    prev = None
    for ri, (n, R, _) in enumerate(rows):
        ys = [(-((n - 1) / 2) + i) * (2 * R + 0.02) for i in range(n)]
        z = base_z + R if ri == 0 else prev + R * 1.65
        for i, y in enumerate(ys):
            Rl = R * r.uniform(0.9, 1.08)
            bark = "wild_log_bark_larch" if r.random() < 0.35 else "wild_log_bark"
            lg = W.log_obj(f"log{ri}{i}", r.uniform(5.4, 6.0), Rl, r.randint(0, 99999), sides=14, rings=9, taper=0.12, bow=0.04,
                           bark=bark)
            K.place(lg, (r.uniform(-0.2, 0.2), y, z - (R - Rl)), (r.uniform(-2, 2), 0, r.uniform(-1.5, 1.5) + (180 if r.random() < 0.5 else 0)))
            ctx.add(lg, None, uv=None, smooth=50, patches=0.3, edge=0.6, moss=0.6 if (ctx.worn and ri == len(rows) - 1) else 0.15)
        prev = z
    for sy in (-1, 1):
        ch = K.prism("chock", [(0.0, 0.0), (0.3, 0.0), (0.0, 0.22)], 0.2, plane="YZ")
        K.place(ch, (0.0, 0, 0))
        K.place(ch, (-2.0, sy * 1.45, 0.3), (0, 0, 0 if sy > 0 else 180))
        ctx.add(ch, "wood_weathered", uv_scale=1.0, patches=0.5)
    for k in range(5):
        b = K.box(f"bark{k}", (r.uniform(0.4, 0.9), r.uniform(0.12, 0.25), 0.02), cuts=(3, 1, 0))
        K.map_verts(b, lambda co: Vector((co.x, co.y, co.z + 0.03 * math.cos(co.y * 10))))
        K.place(b, (r.uniform(-2.8, 2.8), r.uniform(-1.8, 1.8), 0.012), (0, 0, r.uniform(0, 360)))
        ctx.add(b, "wild_log_bark", uv_scale=1.0, patches=0.4, moss=0.4)
    ctx.col_box((-3.0, -1.5, 0), (3.0, 1.5, 1.85))


# ============================================================================================
# Chain hoist, filing bench, loose blades and tools
# ============================================================================================

def wild_chain_hoist(ctx: K.Ctx) -> None:
    """Hand chain hoist on a beam trolley: an I-beam under the ceiling (top at 2.8 m), the trolley
    riding its lower flange, the geared hoist block with its hand wheel and chain loop, the load
    chain and a latched hook. Origin on the floor under the hook. Worn: hook run down low."""
    r = ctx.rnd("hoist")
    ZB = 2.7
    W.section(ctx, "ibeam", (-0.7, 0.0, ZB), (0.7, 0.0, ZB), W.prof_i(0.2, 0.11, 0.012, 0.008), "wild_paint_red_oxide",
              patches=0.6)
    for sy in (-1, 1):
        plate = K.box("trolleyplate", (0.18, 0.01, 0.16), center=(0, sy * 0.07, ZB - 0.12), bevel=0.004)
        ctx.add(plate, "wild_paint_mill_grey", uv_scale=2.0, patches=0.33)
        for x in (-0.06, 0.06):
            wh = K.cyl("twheel", 0.03, 0.02, segs=10, axis="Y", center=(x, sy * 0.045, ZB - 0.07))
            ctx.add(wh, "wild_cast_iron", uv_scale=2.0, smooth=40)
    W.rod(ctx, "trolleybolt", (0, -0.09, ZB - 0.18), (0, 0.09, ZB - 0.18), 0.012, "chrome_pitted", segs=6)
    hook_top = K.tube("tophook", [(0, 0, ZB - 0.18), (0, 0, ZB - 0.24), (0.03, 0, ZB - 0.28), (0, 0, ZB - 0.31)], 0.012, segs=6)
    ctx.add(hook_top, "item_iron_strap", uv_scale=2.0, smooth=40)
    zb = ZB - 0.62
    body = K.box("hoistbody", (0.22, 0.16, 0.28), center=(0, 0, zb + 0.14), bevel=0.04, bevel_segs=2)
    ctx.add(body, "paint_red", uv_scale=1.5, smooth=40, patches=0.33, edge=0.7)
    ring = W.ring_obj("handwheel", 0.13, 0.15, 0.02, segs=20)
    K.place(ring, rot=(90, 0, 0))
    K.place(ring, (0, 0.12, zb + 0.14))
    ctx.add(ring, "wild_cast_iron", uv_scale=2.0, smooth=40)
    W.rod(ctx, "eye", (0, 0, zb + 0.28), (0, 0, ZB - 0.3), 0.012, "item_iron_strap", segs=6)
    low = 1.2 if ctx.clean else 0.8
    for sx in (-1, 1):
        pts = [(sx * 0.14, 0.12, zb + 0.12), (sx * 0.14, 0.12, low + 0.25)]
        ctx.add(W.chain_obj(f"handchain{sx}", pts, link=0.065, wire=0.0045, sides=3), "metal_galvanized", uv_scale=3.0, smooth=40)
    loop = [(0.14 * math.cos(math.pi * k / 6), 0.12, low + 0.25 - 0.14 * math.sin(math.pi * k / 6)) for k in range(7)]
    ctx.add(W.chain_obj("handloop", loop, link=0.065, wire=0.0045, sides=3), "metal_galvanized", uv_scale=3.0, smooth=40)
    lc = [(0.0, 0.0, zb), (0.0, 0.0, low + 0.18)]
    ctx.add(W.chain_obj("loadchain", lc, link=0.075, wire=0.0075, sides=3), "item_iron_strap", uv_scale=3.0, smooth=40, patches=0.7)
    blk = K.box("bottomblock", (0.08, 0.06, 0.12), center=(0, 0, low + 0.12), bevel=0.012)
    ctx.add(blk, "paint_red", uv_scale=2.0, patches=0.33)
    hook = K.tube("hook", [(0, 0, low + 0.06), (0, 0, low - 0.02), (0.02, 0, low - 0.08), (0.06, 0, low - 0.1), (0.1, 0, low - 0.08),
                           (0.11, 0, low - 0.03), (0.095, 0, low)], [0.022, 0.022, 0.02, 0.018, 0.015, 0.012, 0.01], segs=8)
    ctx.add(hook, "item_steel_dark", uv_scale=2.0, smooth=45, patches=0.6)
    latch = W.bar(ctx, "latch", (0.0, 0.0, low - 0.01), (0.09, 0.0, low + 0.0), 0.012, 0.004, "chrome_pitted")


def wild_filing_bench(ctx: K.Ctx) -> None:
    """The saw filer's bench: oil-black plank top on timber legs with a shelf, a long saw vise
    clamping a section of band blade teeth-up, an automatic sharpener with its grinding wheel and
    motor at the end, files, a file card and an oil can."""
    r = ctx.rnd("filing")
    L, D, H = 2.0, 0.72, 0.86
    wood = "wood_creosote"
    for i in range(4):
        y = -D / 2 + (i + 0.5) * D / 4
        ctx.add(P.plank(f"top{i}", L, D / 4 - 0.006, 0.06, cuts=3), wood, long_axis=0, at=((0, y, H - 0.03),), patches=0.6, edge=1.3)
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.bar(ctx, "leg", (sx * (L / 2 - 0.08), sy * (D / 2 - 0.08), 0.0), (sx * (L / 2 - 0.08), sy * (D / 2 - 0.08), H - 0.06),
                  0.1, 0.1, wood, low=0.6, low_h=0.3)
    ctx.add(P.plank("shelf", L - 0.2, D - 0.16, 0.03), wood, long_axis=0, at=((0, 0, 0.25),), patches=0.6)
    for sy in (-1, 1):
        W.bar(ctx, "apron", (-L / 2 + 0.08, sy * (D / 2 - 0.03), H - 0.12), (L / 2 - 0.08, sy * (D / 2 - 0.03), H - 0.12), 0.1, 0.04,
              wood, up=(0, sy, 0))
    vz = H + 0.02
    for x in (-0.55, 0.45):
        post = K.box("visepost", (0.08, 0.1, 0.22), center=(x, -D / 2 + 0.08, vz + 0.11), bevel=0.01)
        ctx.add(post, "wild_cast_iron", uv_scale=1.5, patches=0.5)
        W.rod(ctx, "visescrew", (x, -D / 2 - 0.05, vz + 0.2), (x, -D / 2 + 0.12, vz + 0.2), 0.012, "chrome_pitted", segs=6)
        W.rod(ctx, "tommy", (x - 0.08, -D / 2 - 0.05, vz + 0.2), (x + 0.08, -D / 2 - 0.05, vz + 0.2), 0.007, "chrome_pitted", segs=5)
    for s in (-1, 1):
        jaw = K.box("jaw", (1.3, 0.03, 0.09), center=(-0.05, -D / 2 + 0.08 + s * 0.018, vz + 0.27), bevel=0.006)
        ctx.add(jaw, "wood_stained", long_axis=0, patches=0.5)
    blade = W.saw_plate_obj("bandsection", W.saw_outline(1.5, 0.16, 0.045, 0.02), 0.0016)
    K.place(blade, (-0.05, -D / 2 + 0.08, vz + 0.18))
    ctx.add(blade, "wild_saw_steel", uv_scale=1.0, patches=0.3)
    # Automatic sharpener at the +X end.
    gx = L / 2 - 0.3
    gb = K.box("grinderbase", (0.36, 0.32, 0.22), center=(gx, 0.08, H + 0.11), bevel=0.02)
    ctx.add(gb, "wild_paint_mill_grey", uv_scale=1.5, patches=0.33, edge=0.7)
    mot = K.cyl("gmotor", 0.075, 0.24, segs=14, axis="Y", center=(gx, 0.18, H + 0.33))
    ctx.add(mot, "wild_paint_mill_grey", uv="cyl", uv_axis=1, uv_scale=1.5, smooth=40, patches=0.33)
    arm = W.bar(ctx, "garm", (gx, 0.05, H + 0.3), (gx - 0.05, -0.2, H + 0.38), 0.06, 0.05, "wild_cast_iron")
    wheel = K.cyl("gwheel", 0.1, 0.018, segs=20, axis="Y", center=(gx - 0.05, -0.23, H + 0.38))
    ctx.add(wheel, "concrete_barrier", uv_scale=2.0, smooth=40, patches=0.3)
    wg = K.lathe("wguard", [(0.0, 0.0), (0.115, 0.0), (0.115, 0.03), (0.0, 0.03)], segs=16, arc=math.pi * 1.2, angle0=-0.1,
                 cap_bottom=False, cap_top=False)
    K.place(wg, rot=(90, 0, 0))
    K.place(wg, (gx - 0.05, -0.215, H + 0.38))
    ctx.add(wg, "wild_paint_mill_grey", uv_scale=2.0, smooth=40)
    for k in range(3):
        y = 0.12 + k * 0.05
        W.rod(ctx, f"file{k}", (-0.7 + k * 0.08, y, H + 0.012), (-0.4 + k * 0.08, y + 0.02, H + 0.012), 0.006, "item_steel_dark",
              segs=4)
        W.rod(ctx, f"fhandle{k}", (-0.82 + k * 0.08, y - 0.004, H + 0.016), (-0.7 + k * 0.08, y, H + 0.016), 0.014, "item_wood_handle",
              segs=7)
    can = K.lathe("oilcan", [(0.0, 0.0), (0.06, 0.0), (0.065, 0.01), (0.065, 0.05), (0.03, 0.09), (0.01, 0.1), (0.0, 0.1)], segs=12)
    K.place(can, (0.15, 0.2, H))
    ctx.add(can, "paint_red", uv_scale=2.0, smooth=40, patches=0.33)
    W.rod(ctx, "spout", (0.15, 0.2, H + 0.1), (0.22, 0.12, H + 0.25), 0.005, "furn_brass", r2=0.003, segs=5)
    ctx.col_box((-L / 2, -D / 2 - 0.08, 0), (L / 2, D / 2, H + 0.45))


def wild_band_blade_coil(ctx: K.Ctx) -> None:
    """A spare band saw blade folded into three loops, lying on the floor."""
    r = ctx.rnd("coil")
    for k in range(3):
        a = k * math.tau / 3
        cx, cy = 0.04 * math.cos(a), 0.04 * math.sin(a)
        band = K.lathe(f"loop{k}", [(0.31, 0.0), (0.31, 0.11)], segs=36, cap_bottom=False, cap_top=False)
        K.solidify(band, 0.0016, even=False)
        K.place(band, (cx, cy, 0.0005 + 0.002 * k), (r.uniform(-1.5, 1.5), r.uniform(-1.5, 1.5), 0))
        ctx.add(band, "wild_saw_steel_rust" if not ctx.clean else "wild_saw_steel", uv="cyl", uv_scale=1.0, smooth=40, patches=0.4)
    ctx.col_box((-0.36, -0.36, 0), (0.36, 0.36, 0.12))


def wild_saw_blade_circular(ctx: K.Ctx) -> None:
    """A worn-out circle saw blade leaning against a wall (back toward +Y), arbor collar on."""
    r = ctx.rnd("circle")
    R = 0.45
    disc = _toothed_disc("blade", R, 40, 0.035, 0.005, hook=0.4)
    collar = K.cyl("collar", 0.09, 0.03, segs=16, axis="Y")
    hole = K.cyl("arbor", 0.04, 0.034, segs=12, axis="Y")
    parts = []
    for o, mat in ((disc, "wild_saw_steel_rust" if not ctx.clean else "wild_saw_steel"), (collar, "wild_cast_iron"),
                   (hole, "paint_black")):
        K.place(o, (0, 0, R))
        parts.append(ctx.add(o, mat, uv_scale=1.0, smooth=40 if o is not disc else None, patches=0.5))
    _rot_about(parts, (0, 0, 0), (-14, 0, 0))
    lo = min(min(v.co.z for v in o.data.vertices) for o in parts)
    _move(parts, (0, -0.06, -lo))
    ctx.col_box((-R, -0.15, 0), (R, 0.15, 2 * R))


def wild_peavey(ctx: K.Ctx) -> None:
    """Logger's peavey lying on the floor: ash handle, steel socket and pike, hinged hook."""
    r = ctx.rnd("peavey")
    W.rod(ctx, "handle", (-0.7, 0.0, 0.022), (0.55, 0.0, 0.028), 0.022, "item_wood_handle", r2=0.026, segs=10)
    W.rod(ctx, "socket", (0.55, 0.0, 0.03), (0.75, 0.0, 0.03), 0.031, "item_steel_dark", segs=10)
    W.rod(ctx, "pike", (0.75, 0.0, 0.03), (0.88, 0.0, 0.03), 0.02, "item_steel_dark", r2=0.003, segs=8)
    for s in (-1, 1):
        cl = K.box("clevis", (0.06, 0.008, 0.06), center=(0.62, s * 0.034, 0.03))
        ctx.add(cl, "item_steel_dark", uv_scale=2.0)
    hook = K.tube("hook", [(0.62, 0.0, 0.03), (0.55, 0.12, 0.03), (0.42, 0.19, 0.03), (0.3, 0.17, 0.03), (0.26, 0.12, 0.03)],
                  [0.016, 0.015, 0.013, 0.01, 0.006], segs=6, flat=(1.0, 0.7))
    ctx.add(hook, "item_steel_dark", uv_scale=2.0, smooth=40, patches=0.6)
    ctx.col_box((-0.72, -0.05, 0), (0.9, 0.22, 0.06))


def wild_choker_cable(ctx: K.Ctx) -> None:
    """Coiled steel choker cable on the ground with its bell and hook."""
    r = ctx.rnd("choker")
    pts = []
    for k in range(70):
        a = k * math.tau * 3 / 70
        rr = 0.26 + 0.03 * math.sin(a * 0.7) + 0.01 * k / 70
        pts.append((rr * math.cos(a) + 0.03 * k / 70, rr * math.sin(a), 0.014 + 0.012 * (k / 70)))
    pts += [(0.33, -0.05, 0.015), (0.42, -0.12, 0.012)]
    ctx.add(K.tube("cable", pts, 0.011, segs=6), "item_iron_strap", uv_scale=4.0, smooth=50, patches=0.6)
    bell = K.lathe("bell", [(0.0, 0.0), (0.035, 0.0), (0.03, 0.09), (0.016, 0.1), (0.0, 0.1)], segs=10)
    K.place(bell, rot=(0, 90, 0))
    K.place(bell, (0.42, -0.12, 0.035))
    ctx.add(bell, "item_steel_dark", uv_scale=2.0, smooth=40)
    hook = K.tube("chokerhook", [(0.52, -0.12, 0.03), (0.6, -0.12, 0.03), (0.66, -0.08, 0.03), (0.66, -0.02, 0.03)], 0.016, segs=6)
    ctx.add(hook, "item_steel_dark", uv_scale=2.0, smooth=40)
    ctx.col_box((-0.32, -0.32, 0), (0.68, 0.32, 0.06))


# ============================================================================================
# Skidder wreck
# ============================================================================================

def _lugged_tyre(ctx, name, x, y, z, r_out, r_rim, width, flat, seed):
    """Big logging tyre with chevron lugs and a steel rim, axle along X, flattened at the bottom."""
    t = P.tyre(name, r_out - 0.05, r_rim, width, segs=20)
    K.place(t, (x, y, z))
    P.flatten_tyre(t, z, r_out - 0.05, amount=flat, ground=0.0)
    ctx.add(t, "tyre_rubber", uv_scale=1.5, smooth=40, patches=0.3, low=0.6, low_h=0.5)
    lugs = []
    n = 14
    for k in range(n):
        a = math.tau * k / n
        for s in (-1, 1):
            lug = K.box(f"{name}lug{k}{s}", (width * 0.42, 0.13, 0.06))
            K.place(lug, rot=(0, 0, s * 28))
            K.place(lug, (s * width * 0.22, 0.0, r_out - 0.06))
            K.place(lug, rot=(math.degrees(a) + s * 6, 0, 0))
            K.place(lug, (x, y, z))
            lugs.append(lug)
    lg = K.merge_parts(lugs, name + "lugs")
    for v in lg.data.vertices:
        if v.co.z < 0.0:
            v.co.z = 0.0
    lg.data.update()
    ctx.add(lg, "tyre_rubber", uv_scale=1.5, smooth=None, patches=0.3, low=0.6, low_h=0.5)
    rim = P.steel_rim(name + "rim", r_rim + 0.02, width * 0.85, segs=16)
    K.place(rim, rot=(0, 0, 0 if x > 0 else 180))
    K.place(rim, (x, y, z))
    ctx.add(rim, "wild_paint_skidder_yellow", uv_scale=1.5, smooth=40, patches=0.39, edge=0.7)


def wild_skidder_wreck(ctx: K.Ctx) -> None:
    """Wrecked articulated cable skidder (front faces -Y): front dozer blade on push arms, engine
    hood with louvres, grille, air cleaner and exhaust stack, fenders over four lugged tyres gone
    flat, the articulation pivot and steering rams, the operator's deck with seat, wheel and
    levers inside a ROPS cage with a mesh screen, the winch drum with cable over the fairlead
    rollers to a choker on the ground. Yellow enamel gone chalky; worn: rust-eaten, hood side gone."""
    r = ctx.rnd("skidder")
    paint = "wild_paint_skidder_yellow"
    iron = "wild_cast_iron_rust"
    YF, YR, ZA = -1.9, 1.6, 0.7
    RO, RR, TW, TX = 0.8, 0.42, 0.62, 1.02
    for y in (YF, YR):
        for sx in (-1, 1):
            _lugged_tyre(ctx, f"t{y}{sx}", sx * TX, y, ZA, RO, RR, TW, 0.32 if ctx.worn else 0.22, r.randint(0, 999))
        W.rod(ctx, "axle", (-TX + 0.25, y, ZA), (TX - 0.25, y, ZA), 0.11, iron, segs=12)
        diff = K.blob("diff", 0.5, subdiv=2, scale=(0.5, 0.42, 0.42), center=(0, y, ZA))
        ctx.add(diff, iron, uv_scale=1.5, smooth=40, patches=0.6)
    ff = K.box("frontframe", (0.95, 2.5, 0.42), center=(0, -1.95, 0.95), bevel=0.03)
    ctx.add(ff, paint, uv_scale=1.0, patches=0.39, edge=0.7)
    rf = K.box("rearframe", (1.05, 2.4, 0.45), center=(0, 1.0, 0.98), bevel=0.03)
    ctx.add(rf, paint, uv_scale=1.0, patches=0.39, edge=0.7)
    pivot = K.cyl("pivot", 0.2, 0.55, segs=14, center=(0, -0.55, 1.0))
    ctx.add(pivot, iron, uv="cyl", uv_scale=1.5, smooth=40, patches=0.6)
    for sx in (-1, 1):
        W.rod(ctx, "steerram", (sx * 0.4, -1.1, 1.0), (sx * 0.42, 0.0, 0.95), 0.05, paint, segs=10)
        W.rod(ctx, "steerrod", (sx * 0.41, -0.55, 0.98), (sx * 0.42, 0.0, 0.95), 0.025, "chrome_pitted", segs=8)
    hood = K.box("hood", (1.3, 1.95, 0.85), center=(0, -2.05, 1.6), bevel=0.06, bevel_segs=2, cuts=(2, 3, 1))
    if ctx.worn:
        K.dent(hood, (0.4, -2.4, 2.05), 0.35, 0.06)
        K.delete_faces(hood, lambda c, n: n.x > 0.9 and c.y > -2.6 and c.y < -1.5 and c.z < 1.9)
    ctx.add(hood, paint, uv_scale=1.0, smooth=35, patches=0.39, edge=0.7)
    for sx in (-1, 1):
        for k in range(6):
            lv = K.box("louvre", (0.02, 0.05, 0.42), center=(sx * 0.66, -2.6 + k * 0.1, 1.55))
            K.place(lv, rot=(0, 0, 0))
            if ctx.worn and sx > 0:
                continue
            ctx.add(lv, paint, uv_scale=2.0, patches=0.33, edge=0.7)
    if ctx.worn:
        eng = K.box("engine", (0.9, 1.4, 0.6), center=(0, -2.05, 1.45), bevel=0.05)
        ctx.add(eng, iron, uv_scale=1.0, patches=0.6)
    grille = K.box("grillframe", (1.2, 0.06, 0.75), center=(0, -3.05, 1.55), bevel=0.02)
    ctx.add(grille, paint, uv_scale=1.0, patches=0.39)
    for k in range(9):
        W.bar(ctx, "grillebar", (-0.52, -3.09, 1.24 + k * 0.075), (0.52, -3.09, 1.24 + k * 0.075), 0.025, 0.02, "wild_paint_mill_grey")
    W.rod(ctx, "stack", (0.42, -2.3, 2.0), (0.42, -2.3, 2.85), 0.065, "car_rust", segs=10)
    flap = K.cyl("flap", 0.075, 0.008, segs=10, center=(0.42, -2.3, 2.86))
    K.place(flap, rot=(0, 0, 0))
    ctx.add(flap, "car_rust", uv_scale=2.0)
    ac = K.cyl("aircleaner", 0.13, 0.42, segs=14, center=(-0.38, -1.5, 2.2))
    ctx.add(ac, paint, uv="cyl", uv_scale=1.0, smooth=40, patches=0.39)
    # Blade on push arms with a ram.
    prof = [(-0.15, 0.0), (0.02, 0.0), (0.08, 0.25), (0.1, 0.55), (0.05, 0.8), (-0.05, 0.86), (-0.06, 0.8), (-0.01, 0.55),
            (-0.03, 0.25), (-0.16, 0.04)]
    blade = K.prism("blade", [(p[0], p[1]) for p in prof], 2.6, plane="YZ")
    K.place(blade, (0, -3.55, 0.12 if not ctx.worn else 0.0))
    ctx.add(blade, paint, uv_scale=1.0, patches=0.44, edge=0.7, low=0.8, low_h=0.4)
    edge = K.box("cutedge", (2.6, 0.04, 0.06), center=(0, -3.62, 0.15 if not ctx.worn else 0.03))
    ctx.add(edge, "wild_saw_steel_rust", uv_scale=1.0, patches=0.6)
    for sx in (-1, 1):
        W.bar(ctx, "pusharm", (sx * 0.85, -3.45, 0.45), (sx * 0.5, -2.4, 0.8), 0.14, 0.14, paint)
        W.rod(ctx, "bladeram", (sx * 0.3, -3.4, 0.75), (sx * 0.3, -2.9, 1.15), 0.05, paint, segs=10)
    # Fenders.
    for y in (YF, YR):
        for sx in (-1, 1):
            pts = [(sx * TX, y + 0.95 * math.cos(a), ZA + 0.95 * math.sin(a)) for a in [math.radians(d) for d in (20, 50, 80, 110, 140, 160)]]
            fd = K.sweep("fender", pts, [(-0.36, -0.005), (0.36, -0.005), (0.36, 0.005), (-0.36, 0.005)], up=(1, 0, 0))
            ctx.add(fd, paint, uv_scale=1.0, smooth=40, patches=0.44, edge=0.7)
    # Operator's deck, seat, wheel, levers, ROPS.
    dz = 1.28
    deck = K.box("deck", (1.7, 1.5, 0.05), center=(0, 0.3, dz), bevel=0.01)
    ctx.add(deck, paint, uv_scale=1.0, patches=0.44, low=0.8, low_h=0.3)
    seatb = K.box("seat", (0.5, 0.48, 0.12), center=(0, 0.55, dz + 0.42), bevel=0.04, bevel_segs=2)
    ctx.add(seatb, "car_upholstery", uv_scale=1.0, smooth=50, patches=0.6)
    seatr = K.box("backrest", (0.5, 0.1, 0.45), center=(0, 0.8, dz + 0.7), bevel=0.04, bevel_segs=2)
    K.place(seatr, rot=(0, 0, 0))
    ctx.add(seatr, "car_upholstery", uv_scale=1.0, smooth=50, patches=0.6)
    ctx.add(K.box("seatbase", (0.36, 0.36, 0.36), center=(0, 0.55, dz + 0.18)), paint, uv_scale=1.0, patches=0.39)
    col = W.rod(ctx, "column", (0, -0.25, dz), (0, 0.05, dz + 0.75), 0.04, "wild_paint_mill_grey", segs=8)
    wheel = W.ring_obj("wheel", 0.17, 0.2, 0.03, segs=18)
    K.place(wheel, rot=(-30, 0, 0))
    K.place(wheel, (0, 0.07, dz + 0.78))
    ctx.add(wheel, "plastic_black", uv_scale=2.0, smooth=40)
    for k in range(4):
        W.rod(ctx, f"lever{k}", (0.32 + 0.06 * k, 0.2, dz), (0.34 + 0.06 * k, 0.1, dz + 0.65), 0.012, "chrome_pitted", segs=6)
    for sx in (-1, 1):
        for y in (-0.4, 1.0):
            W.bar(ctx, "rops", (sx * 0.78, y, dz), (sx * 0.74, y, 2.85), 0.11, 0.11, paint, patches=0.39)
    roof = K.box("roof", (1.75, 1.65, 0.07), center=(0, 0.3, 2.88), bevel=0.02, cuts=(2, 2, 0))
    if ctx.worn:
        K.dent(roof, (0.5, 0.0, 2.92), 0.5, 0.12)
    ctx.add(roof, paint, uv_scale=1.0, patches=0.44, edge=0.7, moss=0.5 if ctx.worn else 0.2)
    screen = K.box("screen", (1.5, 0.006, 1.3), center=(0, 1.05, dz + 0.95))
    ctx.add(screen, "chainlink", uv="planar", uv_axis=1, uv_scale=2.0, wear=0.0)
    # Winch, fairlead arch and cable to a choker on the ground.
    wd = K.cyl("drum", 0.26, 0.8, segs=18, axis="X", center=(0, 2.0, 1.45))
    ctx.add(wd, "car_rust", uv="cyl", uv_axis=0, uv_scale=2.0, smooth=40, patches=0.6)
    for sx in (-1, 1):
        fl = K.cyl("flange", 0.38, 0.04, segs=18, axis="X", center=(sx * 0.42, 2.0, 1.45))
        ctx.add(fl, paint, uv_scale=1.5, smooth=40, patches=0.39)
        W.bar(ctx, "arch", (sx * 0.5, 2.2, 1.0), (sx * 0.45, 2.45, 2.25), 0.12, 0.12, paint)
    W.bar(ctx, "archtop", (-0.5, 2.45, 2.25), (0.5, 2.45, 2.25), 0.14, 0.14, paint)
    for k in range(2):
        rl = K.cyl("fairlead", 0.08, 0.5, segs=12, axis="X", center=(0, 2.55, 2.05 - 0.16 * k))
        ctx.add(rl, "wild_saw_steel_rust", uv="cyl", uv_axis=0, uv_scale=2.0, smooth=40)
    cable = [(0, 2.0, 1.72), (0, 2.6, 2.0), (0, 2.75, 1.4), (0.2, 3.1, 0.35), (0.5, 3.6, 0.03), (0.9, 4.2, 0.03)]
    ctx.add(K.tube("cable", cable, 0.014, segs=6), "item_iron_strap", uv_scale=4.0, smooth=50, patches=0.6)
    hook = K.tube("chokerhook", [(0.9, 4.2, 0.03), (1.0, 4.35, 0.03), (1.05, 4.45, 0.08)], 0.02, segs=6)
    ctx.add(hook, "item_steel_dark", uv_scale=2.0, smooth=40)
    bumper = K.box("bumper", (1.3, 0.25, 0.4), center=(0, 2.3, 0.75), bevel=0.03)
    ctx.add(bumper, paint, uv_scale=1.0, patches=0.44, edge=0.7)
    ctx.col_box((-1.35, -3.7, 0), (1.35, 2.6, 2.95))


BUILDERS = {
    "wild_headrig_saw": wild_headrig_saw,
    "wild_log_carriage": wild_log_carriage,
    "wild_roller_conveyor": wild_roller_conveyor,
    "wild_waste_conveyor": wild_waste_conveyor,
    "wild_belt_drive": wild_belt_drive,
    "wild_edger": wild_edger,
    "wild_sawdust_pile": wild_sawdust_pile,
    "wild_lumber_stack": wild_lumber_stack,
    "wild_log_deck": wild_log_deck,
    "wild_chain_hoist": wild_chain_hoist,
    "wild_filing_bench": wild_filing_bench,
    "wild_band_blade_coil": wild_band_blade_coil,
    "wild_saw_blade_circular": wild_saw_blade_circular,
    "wild_peavey": wild_peavey,
    "wild_choker_cable": wild_choker_cable,
    "wild_skidder_wreck": wild_skidder_wreck,
}


def build(params: dict, outputs: list[str]) -> None:
    K.run(params, outputs, BUILDERS)
