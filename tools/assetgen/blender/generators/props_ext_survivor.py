"""Exterior props family — survivor camps and failed last stands: sleeping bag, camp stove, candle
cluster, propane lantern, mattress barricade, leaning plywood, crude painted sign, human remains,
bloody bandages, burnt-out oil-drum fire.

Light sources glow through std_surface emission while the prop's light burns (ADR-0023): candle
flames ("flame_glow") exist only then, the lantern mantle ("mantle_glow") and the barrel's coals
("ember_glow") show cold when unlit. The light itself comes from PropDef.light (see
game/data/props/exterior.json), lit where a POI's story says so.
Remains are desiccated and clothed — grim, never gory."""
from __future__ import annotations

import math

import bmesh
from mathutils import Matrix, Vector

from lib import props_ext_kit as K
from lib import props_ext_parts as P


# ============================================================================================
# Sleeping bag
# ============================================================================================

def _quilted_pad(name, L, W, T, nx, ny, *, baffle=0.25, puff=1.0):
    """Puffy quilted slab along X lying on the floor (bags, mattresses)."""
    o = K.box(name, (L, W, T), center=(0, 0, T / 2), bevel=min(0.02, T * 0.4), bevel_segs=2, cuts=(nx, ny, 0))

    def quilt(co):
        if co.z > T * 0.55:
            ex = max(0.0, 1 - (2 * abs(co.y) / W) ** 6) * max(0.0, 1 - (2 * abs(co.x) / L) ** 8)
            ch = 0.5 + 0.5 * math.cos(2 * math.pi * co.x / baffle)
            co.z = T * 0.55 + (co.z - T * 0.55) * (0.55 + 0.6 * puff * ex * (0.35 + 0.65 * ch))
        return co
    K.map_verts(o, quilt)
    return o


def sleeping_bag(ctx: K.Ctx) -> None:
    """Rectangular nylon bag laid out on the floor, top corner turned back over the lining, a
    rolled jacket as pillow. Worn: rumpled, filthy, half kicked open, empty cans beside it."""
    r = ctx.rnd("bag")
    L, W = 1.95, 0.78
    # Bottom half: low quilted pad.
    base = _quilted_pad("base", L, W, 0.035, 18, 4, baffle=0.24)
    ctx.add(base, "nylon_navy", uv_scale=1.0, smooth=50, patches=0.0, edge=0.3)
    # Top half: puffy quilted layer; its underside carries the plaid flannel lining (solidify
    # material offset). The foot-side corner is folded back over itself (a 180 deg turn about the
    # fold line), so the lining shows on top.
    top = K.grid("top", L - 0.02, W - 0.02, 18, 7)
    K.uv_planar(top, 2, scale=1.0)
    th = 0.035
    baffle = 0.24

    def quilt(co):
        ex = max(0.0, 1 - (2 * abs(co.y) / W) ** 4) * max(0.0, 1 - (2 * abs(co.x) / L) ** 6)
        ch = 0.5 + 0.5 * math.cos(2 * math.pi * co.x / baffle)
        co.z = 0.035 + 0.006 + th * ex * (0.45 + 0.55 * ch)
        return co
    K.map_verts(top, quilt)
    from lib import materials as M
    M.assign(top, "nylon_navy")
    M.assign(top, "flannel_red")
    K.solidify(top, 0.012, offset=-1.0, mat_offset=1)
    p0 = Vector((L / 2 - (0.75 if ctx.clean else 1.15), -W / 2, 0.0))
    p1 = Vector((L / 2 - (0.2 if ctx.clean else 0.35), W / 2, 0.0))
    d = (p1 - p0).normalized()
    nrm = Vector((d.y, -d.x, 0.0))
    if nrm.dot(Vector((1, 0, 0))) < 0:
        nrm = -nrm
    hinge_z = 0.035 + th + 0.02

    def fold(co):
        s = (co - p0).dot(nrm)
        if s <= 1e-5:  # on or behind the crease: stays put
            return co
        # Rotate 180 deg about the fold line at hinge height: mirror in-plane, flip vertically.
        flat = co - nrm * (2 * s)
        z = 2 * hinge_z - co.z + 0.004 + 0.01 * min(1.0, s / 0.1)
        return Vector((flat.x, flat.y, z))
    K.bisect(top, p0, nrm)  # straight crease: vertices exactly on the fold line
    K.map_verts(top, fold)
    K.crumple(top, 0.008 if ctx.clean else 0.02, scale=4.0, seed=r.randint(0, 999))
    ctx.add(top, None, uv=None, smooth=50, patches=0.0, edge=0.3)
    zipper = K.box("zip", (L - 0.25, 0.012, 0.008), center=(-0.1, W / 2 - 0.006, 0.05), cuts=(6, 0, 0))
    ctx.add(zipper, "plastic_black", uv_scale=1.0, wear=0.2)
    pillow = K.blob("pillow", 0.5, subdiv=2, scale=(0.32, 0.55, 0.16), rough=0.25, seed=r.randint(0, 999),
                    center=(-L / 2 - 0.02, 0.0, 0.07))
    ctx.add(pillow, "canvas_olive", uv_scale=1.0, smooth=55, patches=0.0, edge=0.3)
    if ctx.worn:
        P.add_litter(ctx, ctx.drnd("cans"), 4, extent=(0.25, 0.15), center=(0.2, -0.65), kinds=("can", "wad", "can", "paper"))
    ctx.col_box((-L / 2 - 0.2, -W / 2, 0), (L / 2, W / 2, 0.12))


# ============================================================================================
# Camp stove
# ============================================================================================

def camp_stove(ctx: K.Ctx) -> None:
    """Two-burner suitcase camp stove with lid and wind baffles open, grate, burners, 1 lb propane
    bottle on a regulator, dented pot. Worn: rusted, soot-blackened, bottle gone, pot tipped."""
    r = ctx.rnd("stove")
    L, Dp, H = 0.55, 0.3, 0.1
    paint = "paint_green"
    base = K.box("base", (L, Dp, H), center=(0, 0, H / 2), bevel=0.01, cuts=(2, 1, 0))
    tray = K.box("tray", (L - 0.04, Dp - 0.04, 0.01), center=(0, 0, H - 0.012))
    lid = K.box("lid", (L, 0.012, Dp), center=(0, Dp / 2 + 0.006, H + Dp / 2), bevel=0.004)
    wings = []
    for s in (-1, 1):
        w = K.box("wing", (0.012, Dp, 0.14), center=(s * (L / 2 + 0.006), 0.0, H + 0.07), bevel=0.003)
        wings.append(w)
    if ctx.worn:
        K.place(lid, (0, -(Dp / 2), -H))
        K.place(lid, rot=(-18, 0, 4))
        K.place(lid, (0, Dp / 2, H))
        K.dent(lid, (0.1, Dp / 2, H + 0.2), 0.12, 0.02)
    grate = []
    for k in range(5):
        grate.append(K.tube("gr", [(-L / 2 + 0.03, -0.12 + k * 0.06, H + 0.025), (L / 2 - 0.03, -0.12 + k * 0.06, H + 0.025)],
                            0.003, segs=3))
    burners = []
    for x in (-0.13, 0.13):
        ring = K.tube("burner", [(x + math.cos(a) * 0.045, math.sin(a) * 0.045, H + 0.012) for a in [i * math.tau / 12 for i in range(12)]],
                      0.008, segs=5, closed=True)
        cap = K.cyl("bcap", 0.03, 0.012, segs=10, center=(x, 0, H + 0.012))
        burners += [ring, cap]
    knobs = [K.cyl("knob", 0.016, 0.02, segs=8, axis="Y", center=(x, -Dp / 2 - 0.01, H * 0.55)) for x in (-0.13, 0.13)]
    reg = K.cyl("regulator", 0.018, 0.08, segs=8, axis="X", center=(L / 2 + 0.04, -0.06, H * 0.5))
    parts_metal = grate + burners
    for o in [base, lid] + wings:
        ctx.add(o, paint, uv_scale=1.0, patches=0.6, edge=1.2)
    ctx.add(tray, "car_burnt" if ctx.worn else "chrome_pitted", uv_scale=1.0, wear=0.5)
    for o in parts_metal:
        ctx.add(o, "car_burnt" if ctx.worn else "chrome_pitted", uv_scale=1.0, smooth=40, wear=0.6)
    for o in knobs:
        ctx.add(o, "plastic_black", uv_scale=1.0, smooth=40)
    ctx.add(reg, "chrome_pitted", uv="cyl", uv_axis=0, uv_scale=1.0, smooth=40)
    if ctx.clean:
        bottle = K.lathe("bottle", [(0.0, 0.0), (0.05, 0.0), (0.055, 0.01), (0.055, 0.17), (0.04, 0.2), (0.012, 0.21),
                                    (0.012, 0.225), (0.0, 0.225)], segs=12)
        K.place(bottle, rot=(0, 90, 0))
        K.place(bottle, (L / 2 + 0.08, -0.06, H * 0.5))
        K.lift_min(bottle)
        ctx.add(bottle, "paint_olive", uv="cyl", uv_axis=0, uv_scale=1.0, smooth=45, patches=0.4)
    pot = K.lathe("pot", [(0.0, 0.0), (0.085, 0.0), (0.09, 0.01), (0.09, 0.11), (0.094, 0.115), (0.088, 0.115),
                          (0.084, 0.012), (0.0, 0.012)], segs=14)
    handle = K.tube("pothandle", [(-0.09, 0, 0.1), (-0.12, 0, 0.13), (-0.16, 0, 0.12)], 0.005, segs=4)
    if ctx.worn:
        for o in (pot, handle):
            K.place(o, rot=(0, 95, 30))
            K.place(o, (-0.05, -0.32, 0.0))
            K.lift_min(o)
        K.dent(pot, (-0.05, -0.32, 0.09), 0.05, 0.015)
    else:
        for o in (pot, handle):
            K.place(o, (-0.13, 0.0, H + 0.03))
    ctx.add(pot, "metal_galvanized", uv="cyl", uv_scale=1.0, smooth=40, patches=0.6)
    ctx.add(handle, "plastic_black", uv_scale=1.0)
    ctx.col_box((-L / 2 - 0.02, -Dp / 2, 0), (L / 2 + 0.25, Dp / 2 + 0.02, H + Dp))


# ============================================================================================
# Candles (light)
# ============================================================================================

def _candle(name, r, h, rad, *, lit, melt):
    prof = [(0.0, 0.0), (rad * 1.02, 0.0)]
    n = 3
    for k in range(1, n):
        z = h * k / n
        prof.append((rad * (1.0 + r.uniform(-0.04, 0.04)), z))
    crater = rad * (0.55 + 0.3 * melt)
    prof += [(rad * 1.04, h), (rad * 0.9, h + 0.004), (crater, h - 0.004 - 0.012 * melt), (0.0, h - 0.008 - 0.012 * melt)]
    c = K.lathe(name, prof, segs=8)
    drips = []
    for k in range(r.randint(1, 3)):
        a = r.uniform(0, math.tau)
        dl = r.uniform(0.015, 0.05) * (0.5 + melt)
        drips.append(K.tube(name + "_drip", [(math.cos(a) * rad * 1.02, math.sin(a) * rad * 1.02, h + 0.002),
                                             (math.cos(a) * rad * 1.08, math.sin(a) * rad * 1.08, h - dl * 0.5),
                                             (math.cos(a) * rad * 1.06, math.sin(a) * rad * 1.06, h - dl)],
                            [0.005, 0.006, 0.004], segs=4))
    wick = K.cyl(name + "_wick", 0.0015, 0.014, segs=4, center=(0, 0, h + 0.002))
    flame = None
    if lit:
        flame = K.lathe(name + "_flame", [(0.0, 0.0), (0.006, 0.004), (0.008, 0.012), (0.006, 0.022), (0.003, 0.03),
                                          (0.0, 0.036)], segs=6)
        K.place(flame, (0, 0, h + 0.008))
    return c, drips, wick, flame


def candle_cluster(ctx: K.Ctx) -> None:
    """Pillar and taper candles melted onto a chipped saucer and the floor, most still burning.
    Worn: burnt down to stubs in wide wax puddles, only two flames left."""
    r = ctx.rnd("candles")
    saucer = K.lathe("saucer", [(0.0, 0.0), (0.06, 0.0), (0.09, 0.008), (0.1, 0.014), (0.095, 0.016), (0.085, 0.01),
                                (0.0, 0.007)], segs=16)
    K.place(saucer, (-0.03, 0.02, 0))
    ctx.add(saucer, "plastic_white", uv_scale=1.0, smooth=40, patches=0.4)
    specs = [((-0.04, 0.03, 0.009), 0.16, 0.03), ((0.02, -0.01, 0.009), 0.11, 0.028), ((-0.075, -0.03, 0.009), 0.07, 0.025),
             ((0.12, 0.06, 0.0), 0.2, 0.012), ((0.1, -0.08, 0.0), 0.06, 0.035), ((-0.14, 0.09, 0.0), 0.13, 0.026)]
    for i, (pos, h, rad) in enumerate(specs):
        rr = ctx.rnd(f"c{i}")
        hh = h * (0.35 if ctx.worn else 1.0)
        lit = (i in (0, 3)) if ctx.worn else (i != 4)
        c, drips, wick, flame = _candle(f"candle{i}", rr, hh, rad, lit=lit, melt=0.9 if ctx.worn else 0.4)
        for o in [c, wick] + drips + ([flame] if flame else []):
            K.place(o, pos)
        ctx.add(c, "candle_wax", uv="cyl", uv_scale=1.0, smooth=50, patches=0.0, edge=0.3)
        for d in drips:
            ctx.add(d, "candle_wax", uv_scale=1.0, smooth=50, patches=0.0)
        ctx.add(wick, "plastic_black", uv_scale=1.0)
        if flame:
            ctx.add(flame, "flame_glow", uv_scale=1.0, smooth=60, wear=0.0, ao=False)
        # Wax puddle.
        pr = rad * (1.6 if ctx.clean else 2.6)
        pud = K.cyl(f"puddle{i}", pr, 0.004, segs=8, center=(pos[0], pos[1], pos[2] + 0.002))
        K.noise_disp(pud, pr * 0.25, scale=30.0, seed=rr.randint(0, 999), along_normal=False,
                     mask=lambda co: 1.0 if abs(co.z - pos[2] - 0.002) < 0.003 else 0.0)
        K.map_verts(pud, lambda co, z0=pos[2]: Vector((co.x, co.y, max(z0, co.z))))
        ctx.add(pud, "candle_wax", uv_scale=1.0, smooth=50, patches=0.0)


# ============================================================================================
# Propane lantern (light)
# ============================================================================================

def lantern_camping(ctx: K.Ctx) -> None:
    """Propane mantle lantern on a 1 lb cylinder: base cap, valve knob, clear glass globe round a
    mantle that glows white-hot when lit, vented hood, wire bail. Worn: globe cracked out on one side,
    rusted hood. Destroyed: knocked over, globe shattered across the floor, the mantle crushed."""
    r = ctx.rnd("lantern")
    cyl = K.lathe("bottle", [(0.0, 0.0), (0.05, 0.0), (0.055, 0.012), (0.055, 0.17), (0.042, 0.2), (0.015, 0.21), (0.0, 0.212)],
                  segs=14)
    stand = K.lathe("stand", [(0.0, 0.0), (0.075, 0.0), (0.075, 0.012), (0.06, 0.02), (0.0, 0.02)], segs=12)
    collar = K.lathe("collar", [(0.0, 0.205), (0.03, 0.205), (0.05, 0.225), (0.05, 0.245), (0.0, 0.245)], segs=12)
    knob = K.cyl("knob", 0.014, 0.03, segs=8, axis="X", center=(0.06, 0, 0.232))
    globe = K.lathe("globe", [(0.0, 0.245), (0.045, 0.245), (0.047, 0.3), (0.045, 0.34), (0.0, 0.34)], segs=14)
    frame = [K.tube("post", [(math.cos(a) * 0.05, math.sin(a) * 0.05, 0.245), (math.cos(a) * 0.05, math.sin(a) * 0.05, 0.345)],
                    0.003, segs=4) for a in (0.4, 0.4 + math.tau / 3, 0.4 + 2 * math.tau / 3)]
    hood = K.lathe("hood", [(0.0, 0.36), (0.06, 0.34), (0.065, 0.348), (0.04, 0.375), (0.022, 0.39), (0.022, 0.4), (0.0, 0.402)],
                   segs=14)
    bail = K.tube("bail", [(-0.06, 0, 0.36)] + [(-0.06 * math.cos(a), 0, 0.36 + 0.07 * math.sin(a)) for a in
                                                [k * math.pi / 8 for k in range(1, 8)]] + [(0.06, 0, 0.36)], 0.0025, segs=4)
    allp = [cyl, stand, collar, knob, globe, hood, bail] + frame
    shards = []
    if ctx.worn:
        K.dent(hood, (0.04, 0.0, 0.36), 0.04, 0.008)
        K.cut_plane(globe, (0.02, -0.02, 0.0), (0.7, -0.7, 0.0), keep="below")
    if ctx.destroyed:
        globe = None
        allp = [cyl, stand, collar, knob, hood, bail] + frame
        for o in allp:
            K.place(o, rot=(84, 0, 35))
        zmin = min(min(v.co.z for v in o.data.vertices) for o in allp)
        for o in allp:
            K.place(o, (0, 0, -zmin))
        for k in range(9):
            s = r.uniform(0.008, 0.025)
            pts = [(math.cos(a) * s * r.uniform(0.5, 1.0), math.sin(a) * s * r.uniform(0.5, 1.0)) for a in
                   [j * math.tau / 3 + r.uniform(-0.3, 0.3) for j in range(3)]]
            sh = K.prism(f"shard{k}", pts, 0.002, plane="XY")
            K.place(sh, (r.uniform(-0.25, 0.25), r.uniform(-0.25, 0.1), 0.0), (0, 0, r.uniform(0, 360)))
            shards.append(sh)
    ctx.add(cyl, "paint_olive", uv="cyl", uv_scale=1.0, smooth=45, patches=0.5)
    ctx.add(stand, "paint_black", uv_scale=1.0, smooth=40, patches=0.5)
    for o in (collar, hood):
        ctx.add(o, "paint_green", uv="cyl", uv_scale=1.0, smooth=40, patches=0.6, edge=1.2)
    ctx.add(knob, "plastic_black", uv_scale=1.0, smooth=40)
    for o in frame + [bail]:
        ctx.add(o, "chrome_pitted", uv_scale=1.0, smooth=40)
    if globe is not None:
        # Clear globe round the mantle (a sock of ash on the burner tube) that glows when lit.
        ctx.add(globe, "glass_clear", uv_scale=1.0, smooth=50, wear=0.0, ao=False)
        tube = K.cyl("tube", 0.006, 0.03, segs=6, center=(0.0, 0.0, 0.26))
        ctx.add(tube, "chrome_pitted", uv_scale=1.0, smooth=40)
        mantle = K.blob("mantle", 0.017, subdiv=2, scale=(1, 1, 1.35), center=(0.0, 0.0, 0.292))
        ctx.add(mantle, "mantle_glow", uv_scale=1.0, smooth=50, wear=0.0, ao=False)
    for s in shards:
        ctx.add(s, "glass_clear", uv_scale=1.0, wear=0.0)
    ctx.col_hull(allp, max_points=24)


# ============================================================================================
# Mattress barricade
# ============================================================================================

def barricade_mattress(ctx: K.Ctx) -> None:
    """Twin mattress stood on end against a doorway/window (back = +Y), two planks nailed across
    and a board wedged against the floor. Worn: stained, torn open (foam showing), a plank gone.
    Destroyed: knocked down flat, torn, boards scattered."""
    r = ctx.rnd("mattress")
    Wm, Hm, Tm = 0.99, 1.9, 0.2
    m = K.box("mattress", (Wm, Tm, Hm), center=(0, 0, Hm / 2), bevel=0.05, bevel_segs=2, cuts=(5, 0, 9))
    K.noise_disp(m, 0.015, scale=2.0, seed=r.randint(0, 999))

    def bow(co):
        t = co.z / Hm
        co.y += 0.12 * t * t - 0.05 * math.sin(math.pi * t)  # top leans back into the opening
        return co
    K.map_verts(m, bow)
    foam = None
    if ctx.worn:
        K.jagged_hole(m, (0.15, -Tm / 2, 1.05), 0.22, r.randint(0, 999), axis=1, jag=0.5)
        foam = K.blob("foam", 0.5, subdiv=2, scale=(0.38, 0.12, 0.38), rough=0.3, center=(0.15, -0.02, 1.05), seed=5)
    planks = []
    plank_specs = [(1.35, 8.0), (0.65, -6.0)] if ctx.clean else [(1.35, 8.0)]
    for k, (z, ang) in enumerate(plank_specs):
        pl = P.plank(f"bar{k}", 1.3, 0.14, 0.022, cuts=2)
        K.orient(pl, "x", "-y", (0, 0, 0))
        K.place(pl, rot=(0, ang, 0))
        y_front = -Tm / 2 - 0.011 + (0.12 * (z / Hm) ** 2 - 0.05 * math.sin(math.pi * z / Hm))
        K.place(pl, (0, y_front, z))
        planks.append(pl)
    brace = P.plank("brace", 1.25, 0.14, 0.03, cuts=2)
    K.orient(brace, (0, 0.62, 0.78), (0, -0.78, 0.62), (0.18, -0.55, 0.48))
    allm = [m] + ([foam] if foam else [])
    if ctx.destroyed:
        for o in allm + planks + [brace]:
            K.place(o, rot=(-87, 0, 6))
        zmin = min(min(v.co.z for v in o.data.vertices) for o in allm)
        for o in allm:
            K.place(o, (0, 0.2, -zmin))
        for k, o in enumerate(planks + [brace]):
            K.drop_to_ground(o)
            K.place(o, (0.6 - 1.1 * k, -1.2 - 0.3 * k, 0), (0, 0, 30 * k))
        K.crumple(m, 0.03, scale=2.0, seed=r.randint(0, 999))
    ctx.add(m, "ext_mattress_ticking", uv_scale=1.0, smooth=45, patches=0.0, edge=0.3)
    if foam:
        ctx.add(foam, "foam_yellow", uv_scale=1.0, smooth=50, patches=0.0)
    for o in planks + [brace]:
        ctx.add(o, "wood_weathered", uv="box", long_axis=None, patches=0.4)
    if ctx.destroyed:
        ctx.col_box((-0.55, -1.8, 0), (0.55, 0.3, 0.25))
    else:
        ctx.col_box((-Wm / 2, -0.6, 0), (Wm / 2, 0.3, Hm))


# ============================================================================================
# Plywood
# ============================================================================================

def _ply_sheet(name, w, h, t, rect):
    """Plywood sheet in the XZ plane (face -Y), bottom centre at the origin. The face is two
    mirrored halves of the atlas cell (stretch-free on a 1:2 sheet); back/edges are raw ply."""
    face_parts = []
    for k in range(2):
        z0, z1 = k * h / 2, (k + 1) * h / 2
        f = K.quad_sheet(f"{name}_f{k}", (-w / 2, -t / 2 - 0.0005, z0), (w / 2, -t / 2 - 0.0005, z0),
                         (w / 2, -t / 2 - 0.0005, z1), (-w / 2, -t / 2 - 0.0005, z1), 4, 4)
        u0, v0, u1, v1 = rect
        if k == 1:
            K.uv_planar(f, 1, rect=(u0, v1, u1, v0))  # top half mirrored: clean rows meet at the seam
        else:
            K.uv_planar(f, 1, rect=rect)
        face_parts.append(f)
    body = K.box(f"{name}_core", (w, t, h), center=(0, 0, h / 2), cuts=(3, 0, 6))
    return face_parts, body


def plywood_leaning(ctx: K.Ctx) -> None:
    """4x8 ft exterior plywood sheet leaning against a wall. Origin on the wall plane (top edge
    touches y=0), bottom centre; the sheet foot sits 0.63 m out from the wall (-Y).
    Worn: delaminated foot corner, warped, water-stained. Destroyed: snapped; top half on the floor."""
    w, h, t = 1.22, 2.44, 0.012
    ang = 75.0
    faces, core = _ply_sheet("ply", w, h, t, K.ATLAS_PLY["plain"])
    parts = faces + [core]
    if ctx.worn:
        for o in parts:
            K.map_verts(o, lambda co: Vector((co.x, co.y - 0.03 * math.sin(math.pi * co.z / h), co.z)))
        for o in parts:
            K.delete_faces(o, lambda c, n: c.x > w / 2 - 0.2 and c.z < 0.35 and (c.x - (w / 2 - 0.2)) * 1.4 > c.z)
    top_parts = []
    if ctx.destroyed:
        dr = ctx.drnd("snap")
        cut_z = dr.uniform(1.1, 1.3)
        top_parts = [K.duplicate(o, o.name + "_top") for o in parts]
        for o in parts:
            K.cut_plane(o, (0, 0, cut_z), (dr.uniform(-0.3, 0.3), 0, 1), keep="below")
        for o in top_parts:
            K.cut_plane(o, (0, 0, cut_z), (dr.uniform(-0.3, 0.3), 0, -1), keep="below")
        for lst in (parts, top_parts, faces):
            for o in [o for o in lst if len(o.data.vertices) == 0]:
                lst.remove(o)
        faces = [o for o in faces if o in parts]
        for o in top_parts:
            K.place(o, (0, 0, -cut_z))
            K.place(o, rot=(-92, 0, 14))
            K.place(o, (0.15, -0.75, 0.0))
            K.lift_min(o)
        ang = 62.0
    # Lean: rotate about the bottom edge so the top rests on the wall at y = 0.
    for o in parts:
        K.place(o, rot=(-(90 - ang), 0, 0))  # top tips back towards the wall (+Y)
    hh = (h if not ctx.destroyed else cut_z)
    run = hh * math.cos(math.radians(ang))
    for o in parts:
        K.place(o, (0, -run, 0))
    for o in top_parts:
        K.place(o, (0, -run, 0))
    for f in faces + [o for o in top_parts if "_f" in o.name]:
        ctx.add(f, "plywood_marks", uv=None, patches=0.0, edge=0.0)
    for o in [core] + [o for o in top_parts if "_core" in o.name]:
        ctx.add(o, "wood_fresh", uv_scale=1.0, patches=0.3, edge=0.8)
    if ctx.destroyed:
        ctx.col_hull(parts, max_points=16)
        ctx.col_box((-0.75, -2.0, 0), (0.75, -0.6, 0.05))
    else:
        ctx.col_hull(parts, max_points=16)


def sign_plywood_painted(ctx: K.Ctx) -> None:
    """Crude survivor sign: plywood board on two stakes, spray-painted arrow (clean) or red X
    (worn, weathered). Destroyed: board split, a stake snapped, lying in the dirt (tally marks)."""
    w, h, t = 1.2, 0.9, 0.012
    cell = {"clean": "arrow", "worn": "x", "destroyed": "tally"}[ctx.cond]
    u0, v0, u1, v1 = K.ATLAS_PLY[cell]
    crop = (v1 - v0) * 0.125
    rect = (u0, v0 + crop, u1, v1 - crop)
    face = K.quad_sheet("face", (-w / 2, -t / 2 - 0.0005, 0), (w / 2, -t / 2 - 0.0005, 0), (w / 2, -t / 2 - 0.0005, h),
                        (-w / 2, -t / 2 - 0.0005, h), 4, 3)
    K.uv_planar(face, 1, rect=rect)
    core = K.box("core", (w, t, h), center=(0, 0, h / 2), cuts=(3, 0, 2))
    board = [face, core]
    z_bottom = 0.75
    for o in board:
        K.place(o, (0, 0, z_bottom))
    stakes = []
    for x in (-0.42, 0.42):
        s = P.plank("stake", 1.75, 0.045, 0.045, cuts=2)
        K.orient(s, "z", "-y", (x, 0.03, 1.75 / 2 - 0.05))
        stakes.append(s)
    nails = [K.cyl("nail", 0.006, 0.006, segs=5, axis="Y", center=(x, -t / 2 - 0.002, z_bottom + dz)) for x in (-0.42, 0.42)
             for dz in (0.15, h - 0.15)]
    allp = board + stakes + nails
    if ctx.worn:
        lean_m = K.rot_matrix((-7, 4, 0))
        for o in allp:
            o.data.transform(lean_m)
            o.data.update()
    if ctx.destroyed:
        dr = ctx.drnd("break")
        P.break_end(stakes[1], 0.35, dr, side=1, depth=0.06, axis=2)
        stub = P.plank("stake_top", 1.2, 0.045, 0.045, cuts=1)
        P.break_end(stub, -0.5, dr, side=-1, depth=0.06)
        ctx.add(stub, "wood_weathered", uv="box", long_axis=0, patches=0.4, at=((0.55, -0.9, 0.023), (0, 0, 70)))
        for o in board + nails:
            K.place(o, (0, 0, -z_bottom))
            K.place(o, rot=(-88, 0, 18))  # fell backwards off its stakes, face up: the marks still read
            K.place(o, (0.1, 0.26, 0.0))
        lift = -min(v.co.z for o in board + nails for v in o.data.vertices)  # one offset: face stays on top
        for o in board + nails:
            K.place(o, (0, 0, lift))
        K.kink([stakes[0]], (0, 0, 0.2), (-30, 0, 0))
    ctx.add(face, "plywood_marks", uv=None, patches=0.0, edge=0.0)
    ctx.add(core, "wood_fresh", uv_scale=1.0, patches=0.3, edge=0.8)
    for s in stakes:
        ctx.add(s, "wood_weathered", uv="box", long_axis=2, patches=0.4, moss=0.3)
    for n in nails:
        ctx.add(n, "car_rust", uv_scale=1.0)
    if ctx.destroyed:
        ctx.col_hull([core], max_points=16)
    else:
        ctx.col_box((-w / 2, -0.05, 0), (w / 2, 0.06, z_bottom + h))


# ============================================================================================
# Human remains (container: zombie_corpse)
# ============================================================================================

def _head(gone: bool, seed: int):
    """Desiccated head in a local frame (face -Y, crown +Z): cranium with sunken temples, eye
    sockets, nose cavity, retracted lips showing teeth, ears and a patchy hair cap."""
    cran = K.blob("cranium", 1.0, subdiv=3, scale=(0.072, 0.095, 0.085), rough=0.04, seed=seed, center=(0, 0.01, 0.03))
    for sx in (-1, 1):
        K.dent(cran, (sx * 0.033, -0.08, 0.018), 0.026, 0.02)          # eye sockets
        K.dent(cran, (sx * 0.07, -0.03, 0.035), 0.032, 0.009)          # sunken temples
        K.dent(cran, (sx * 0.05, -0.07, -0.008), 0.026, -0.006)        # cheekbones stand out
    K.dent(cran, (0.0, -0.09, -0.012), 0.016, 0.013)                    # nose cavity
    jaw = K.blob("jaw", 1.0, subdiv=2, scale=(0.05, 0.05, 0.028), rough=0.05, seed=seed + 1, center=(0, -0.052, -0.06))
    K.place(jaw, (0, 0.03, 0.05))
    K.place(jaw, rot=(9 if gone else 4, 0, 0))  # slack jaw
    K.place(jaw, (0, -0.03, -0.05))
    teeth = K.box("teeth", (0.036, 0.01, 0.011), center=(0, -0.088, -0.038), bevel=0.003)
    ears = [K.blob("ear", 1.0, subdiv=1, scale=(0.008, 0.022, 0.03), center=(sx * 0.071, 0.0, 0.0)) for sx in (-1, 1)]
    hair = K.blob("hair", 1.0, subdiv=3, scale=(0.077, 0.1, 0.089), rough=0.12, seed=seed + 2, center=(0, 0.012, 0.032))
    K.delete_faces(hair, lambda c, n: c.z < 0.005 or c.y < -0.055 or (math.sin(c.x * 140) * math.cos(c.y * 120) > 0.55))
    return cran, jaw, teeth, ears, hair


def _to_world_head(objs, center):
    """Face-down body, head on its left cheek: local X -> +Z, local Z (crown) -> -Y, face -> +X."""
    m = Matrix(((0.0, -1.0, 0.0, center[0]),
                (0.0, 0.0, -1.0, center[1]),
                (1.0, 0.0, 0.0, center[2]),
                (0.0, 0.0, 0.0, 1.0)))
    for o in objs:
        o.data.transform(m)
        o.data.update()


def corpse_remains(ctx: K.Ctx) -> None:
    """Long-dead man lying face down in a red flannel shirt, belted jeans and work boots: head
    turned on its cheek, one arm reaching ahead with clawed fingers above a dried drag smear —
    desiccated skin over bone, old blood. Worn: further gone — bare skull and bone hands,
    clothes collapsed flat, wider stain. Grim, never gory."""
    r = ctx.rnd("corpse")
    gone = ctx.worn
    thin = 0.86 if gone else 1.0
    skin = "corpse_bone" if gone else "corpse_skin"
    # Torso: emaciated, flattened against the floor (head at -Y).
    rings = []
    for y, w, h in [(-0.64, 0.11, 0.065), (-0.58, 0.2, 0.1), (-0.46, 0.215, 0.115), (-0.3, 0.2, 0.105),
                    (-0.12, 0.165, 0.095), (0.02, 0.175, 0.105), (0.12, 0.165, 0.095)]:
        ring = []
        for k in range(12):
            a = k * math.tau / 12
            z = math.sin(a) * h * thin
            ring.append((math.cos(a) * w * thin, y, (z * 0.3 if z < 0 else z) + h * 0.3 * thin))
        rings.append(ring)
    torso = K.loft("torso", rings)
    K.crumple(torso, 0.014, scale=7.0, seed=r.randint(0, 999))
    belt = K.tube("belt", [(math.cos(a) * 0.178 * thin, 0.0, (math.sin(a) * 0.105 * thin * (0.3 if math.sin(a) < 0 else 1.0)
                                                            + 0.032 * thin)) for a in [k * math.tau / 12 for k in range(12)]],
                  0.012, segs=4, closed=True, flat=(0.4, 1.0))
    neck = K.tube("neck", [(0.0, -0.62, 0.06), (0.01, -0.69, 0.065)], 0.034 * thin, segs=8)
    # Legs: left straight, right bent out at the knee.
    legs = [K.tube("leg", [(-0.085, 0.1, 0.065), (-0.11, 0.3, 0.06), (-0.125, 0.52, 0.055), (-0.135, 0.72, 0.05),
                           (-0.14, 0.9, 0.045)], [r_ * thin for r_ in (0.085, 0.075, 0.062, 0.056, 0.05)], segs=8),
            K.tube("leg", [(0.085, 0.1, 0.065), (0.15, 0.3, 0.06), (0.22, 0.48, 0.055), (0.235, 0.68, 0.05),
                           (0.24, 0.86, 0.045)], [r_ * thin for r_ in (0.085, 0.075, 0.062, 0.056, 0.05)], segs=8)]
    boots = []
    for (x, y, roll, yaw) in ((-0.15, 0.98, -78.0, -14.0), (0.26, 0.94, 82.0, 22.0)):
        b = K.box("boot", (0.1, 0.27, 0.12), center=(0, 0.06, 0.0), bevel=0.03, bevel_segs=2, cuts=(0, 4, 0))

        def boot_shape(co):
            # Tall shaft at the heel, lower toe box, narrowed and rounded toe (+Y).
            t = K.clamp((co.y + 0.075) / 0.27)
            top = 1.0 - 0.38 * K.smooth01(0.3, 1.0, t)
            co.z = -0.06 + (co.z + 0.06) * top
            co.x *= 1.0 - 0.22 * K.smooth01(0.6, 1.0, t)
            co.y -= 0.035 * (2.0 * abs(co.x) / 0.1) ** 2 * K.smooth01(0.75, 1.0, t)
            return co
        K.map_verts(b, boot_shape)
        sole = K.box("sole", (0.105, 0.28, 0.025), center=(0, 0.06, -0.07), cuts=(0, 4, 0))
        K.map_verts(sole, lambda co: Vector((co.x * (1.0 - 0.2 * K.smooth01(0.6, 1.0, (co.y + 0.08) / 0.28)),
                                             co.y - 0.03 * (2.0 * abs(co.x) / 0.105) ** 2
                                             * K.smooth01(0.75, 1.0, (co.y + 0.08) / 0.28), co.z)))
        for o in (b, sole):
            K.place(o, rot=(0, roll, yaw))
            K.place(o, (x, y, 0.06))
        boots += [b, sole]
    # Arms: right reaching ahead past the head, left bent back towards the hip.
    arms = [K.tube("arm", [(0.18, -0.55, 0.065), (0.27, -0.72, 0.055), (0.31, -0.86, 0.045), (0.28, -1.06, 0.035)],
                   [r_ * thin for r_ in (0.05, 0.045, 0.04, 0.032)], segs=8),
            K.tube("arm", [(-0.19, -0.52, 0.065), (-0.3, -0.38, 0.05), (-0.34, -0.24, 0.042), (-0.29, -0.06, 0.03)],
                   [r_ * thin for r_ in (0.05, 0.045, 0.04, 0.032)], segs=8)]
    hands = []
    for (hx, hy, rot, spread) in ((0.275, -1.1, -8.0, 1.0), (-0.28, -0.02, 190.0, 0.5)):
        palm = K.blob("palm", 1.0, subdiv=2, scale=(0.03, 0.04, 0.011), center=(0, 0, 0.012))
        parts = [palm]
        for k, dx in enumerate((-0.022, -0.007, 0.008, 0.022)):
            ln = 0.075 + 0.01 * (1 - abs(k - 1.5) / 1.5)
            ang = dx * 6 * spread
            tip = Vector((dx + math.sin(ang) * ln, 0.03 + math.cos(ang) * ln, 0.004))
            mid = Vector((dx + math.sin(ang) * ln * 0.55, 0.03 + math.cos(ang) * ln * 0.55, 0.018))
            parts.append(K.tube("finger", [(dx, 0.03, 0.012), mid, tip], [0.0062, 0.0055, 0.0045], segs=4))
        parts.append(K.tube("thumb", [(0.028, 0.0, 0.012), (0.05, 0.025, 0.012), (0.06, 0.05, 0.005)], 0.006, segs=4))
        hand = K.merge_parts(parts, "hand")
        K.place(hand, (hx, hy, 0.0), (0, 0, rot))
        K.lift_min(hand)
        hands.append(hand)
    cran, jaw, teeth, ears, hair = _head(gone, r.randint(0, 999))
    head = [cran, jaw, teeth] + ears + ([hair] if not gone else [])
    _to_world_head(head, (0.01, -0.775, 0.071))
    for o in head:
        K.lift_min(o)
    # Old blood: dried pool under head and chest, drag smear ahead of the reaching hand.
    pool_pts = []
    for k in range(16):
        a = k * math.tau / 16
        rr = r.uniform(0.75, 1.15) * (0.44 if gone else 0.34)
        pool_pts.append((math.cos(a) * rr * 1.15, math.sin(a) * rr * 0.85))
    pool = K.prism("pool", pool_pts, 0.002, plane="XY", offset=0.0005)
    K.place(pool, (0.06, -0.66, 0))
    smear = K.prism("smear", [(-0.06, 0.0), (0.06, 0.0), (0.035, -0.5), (0.0, -0.56), (-0.045, -0.47)], 0.002, plane="XY",
                    offset=0.0005)
    K.place(smear, (0.27, -0.95, 0), (0, 0, 6))
    blood_g = (lambda co, n: 0.65 * max(0.0, math.sin(co.x * 13.0 + 1.3) * math.cos(co.y * 9.0)) +
               (0.55 if co.y < -0.4 else 0.0))
    ctx.add(torso, "flannel_bloody", uv_scale=1.0, smooth=50, patches=0.0, edge=0.2, extra=blood_g)
    for o in arms:
        ctx.add(o, "flannel_bloody", uv_scale=1.0, smooth=50, patches=0.0, edge=0.2, extra=blood_g)
    ctx.add(belt, "leather_dark", uv_scale=1.0, smooth=40, patches=0.4)
    for o in legs:
        ctx.add(o, "denim_bloody", uv_scale=1.0, smooth=50, patches=0.0, edge=0.2,
                extra=lambda co, n: 0.45 * max(0.0, math.sin(co.y * 11.0) * math.cos(co.x * 17.0)))
    for o in boots:
        ctx.add(o, "leather_dark" if o.name.startswith("boot") else "rubber_black", uv_scale=1.0, smooth=40, patches=0.3)
    ctx.add(neck, skin, uv_scale=1.0, smooth=45, patches=0.0)
    for o in hands:
        ctx.add(o, skin, uv_scale=1.0, smooth=40, patches=0.0, edge=0.3)
    ctx.add(cran, skin, uv_scale=1.0, smooth=45, patches=0.0, edge=0.4)
    ctx.add(jaw, "corpse_bone" if gone else "corpse_skin", uv_scale=1.0, smooth=45, patches=0.0)
    ctx.add(teeth, "corpse_bone", uv_scale=1.0, smooth=40, patches=0.0)
    for o in ears:
        ctx.add(o, skin, uv_scale=1.0, smooth=45, patches=0.0)
    if not gone:
        ctx.add(hair, "corpse_hair", uv_scale=1.0, smooth=50, patches=0.0)
    ctx.add(pool, "blood_dried", uv_scale=1.0, wear=0.0)
    ctx.add(smear, "blood_dried", uv_scale=1.0, wear=0.0)
    ctx.col_box((-0.42, -1.2, 0), (0.45, 1.12, 0.2))


# ============================================================================================
# Bloody bandages
# ============================================================================================

def bloody_bandages(ctx: K.Ctx) -> None:
    """Field-dressing debris: used bandage strips, a half-unrolled roll, gauze pads, an empty pill
    bottle and a dried smear — someone patched a bite here (~0.6 x 0.5 m, no collision)."""
    r = ctx.rnd("bandage")
    stain = lambda co, n: 0.75 * max(0.0, math.sin(co.x * 23.0 + 0.7) * math.cos(co.y * 19.0)) + 0.25  # noqa: E731
    for i in range(4):
        L = r.uniform(0.25, 0.5)
        pts = []
        x, y, a = r.uniform(-0.2, 0.2), r.uniform(-0.15, 0.15), r.uniform(0, math.tau)
        for k in range(8):
            pts.append((x, y, 0.004 + 0.006 * abs(math.sin(k * 1.7))))
            a += r.uniform(-0.7, 0.7)
            x += math.cos(a) * L / 7
            y += math.sin(a) * L / 7
        strip = K.sweep(f"strip{i}", pts, [(-0.025, -0.0015), (0.025, -0.0015), (0.025, 0.0015), (-0.025, 0.0015)])
        K.crumple(strip, 0.004, scale=20.0, seed=r.randint(0, 999))
        ctx.add(strip, "bandage_bloody", uv_scale=1.0, smooth=50, patches=0.0, edge=0.0, extra=stain)
    roll = K.cyl("roll", 0.03, 0.05, segs=12, axis="X", center=(0.18, 0.12, 0.03))
    tail = K.sweep("tail", [(0.18, 0.09, 0.004), (0.12, 0.0, 0.003), (0.05, -0.08, 0.004), (-0.02, -0.12, 0.003)],
                   [(-0.025, -0.0012), (0.025, -0.0012), (0.025, 0.0012), (-0.025, 0.0012)])
    ctx.add(roll, "bandage_bloody", uv="cyl", uv_axis=0, uv_scale=1.0, smooth=50, patches=0.0,
            extra=lambda co, n: 0.2)
    ctx.add(tail, "bandage_bloody", uv_scale=1.0, smooth=50, patches=0.0, extra=stain)
    for k in range(3):
        pad = K.box("pad", (0.08, 0.08, 0.006), center=(0, 0, 0.003), cuts=(1, 1, 0))
        K.crumple(pad, 0.004, scale=30.0, seed=r.randint(0, 999))
        K.place(pad, (r.uniform(-0.25, 0.25), r.uniform(-0.2, 0.2), 0), (0, 0, r.uniform(0, 90)))
        K.lift_min(pad)
        ctx.add(pad, "bandage_bloody", uv_scale=1.0, smooth=40, patches=0.0, extra=lambda co, n: 0.6)
    bottle = K.lathe("pills", [(0.0, 0.0), (0.017, 0.0), (0.018, 0.005), (0.018, 0.06), (0.0, 0.06)], segs=10)
    cap = K.cyl("pillcap", 0.02, 0.014, segs=10, center=(0.0, 0.0, 0.067))
    for o in (bottle, cap):
        K.place(o, rot=(90, 0, 40))
    K.place(bottle, (-0.22, 0.17, 0.0))
    K.place(cap, (-0.16, 0.25, 0.0))
    K.lift_min(bottle)
    K.lift_min(cap)
    ctx.add(bottle, "plastic_orange", uv="cyl", uv_scale=1.0, smooth=40)
    ctx.add(cap, "plastic_white", uv="cyl", uv_scale=1.0, smooth=40)
    pts = [(math.cos(a) * r.uniform(0.06, 0.12) * 1.5, math.sin(a) * r.uniform(0.06, 0.12)) for a in [k * math.tau / 10 for k in range(10)]]
    smear = K.prism("smear", pts, 0.0015, plane="XY", offset=0.0003)
    K.place(smear, (0.02, -0.02, 0), (0, 0, 30))
    ctx.add(smear, "blood_dried", uv_scale=1.0, wear=0.0)


# ============================================================================================
# Oil-drum fire
# ============================================================================================

def _drum_open_profile():
    """Lid-less drum (fewer rings than barrel_metal: the shell is solidified)."""
    R = 0.286
    pts = [(0.0, 0.014), (0.27, 0.004), (0.293, 0.012), (R, 0.04), (R, 0.09), (R, 0.14), (R, 0.19), (R, 0.268),
           (0.297, 0.285), (R, 0.302), (R, 0.43), (R, 0.556), (0.297, 0.573), (R, 0.59), (R, 0.72), (R, 0.82),
           (0.294, 0.845), (0.282, 0.862)]
    return pts


def oil_drum_fire(ctx: K.Ctx) -> None:
    """Burn barrel: 55 gal drum with the lid cut out and air holes punched round the base,
    scorched and rusted, a bed of coals and charred planks poking out; lit, the coals glow and
    PropLights adds the flames. Worn: burning low — dented, rusted through, ash spilled round the
    foot, a few coals left in the ash."""
    r = ctx.rnd("drum")
    d = K.lathe("drum", _drum_open_profile(), segs=14)
    # Air holes: punch out faces in the low band at alternating segments.
    K.delete_faces(d, lambda c, n: 0.09 < c.z < 0.19 and abs(n.z) < 0.3 and int((math.atan2(c.y, c.x) + math.pi) / (math.tau / 14)) % 2 == 0)
    if ctx.worn:
        dr = ctx.drnd("dents")
        for k in range(3):
            a = dr.uniform(0, math.tau)
            K.dent(d, (math.cos(a) * 0.29, math.sin(a) * 0.29, dr.uniform(0.3, 0.75)), dr.uniform(0.08, 0.15), dr.uniform(0.015, 0.03))
        K.delete_faces(d, lambda c, n: 0.43 < c.z < 0.556 and 0.4 < math.atan2(c.y, c.x) < 0.75)  # rusted-through hole
    K.solidify(d, 0.003, offset=-1.0)
    ctx.add(d, "car_burnt", uv="cyl", uv_scale=1.0, smooth=50, patches=0.6, low=0.4, low_h=0.3,
            extra=lambda co, n: 0.5 if co.z > 0.6 else 0.0)
    ash = K.blob("ash", 0.5, subdiv=2, scale=(0.5, 0.5, 0.16), rough=0.2, seed=r.randint(0, 999), center=(0, 0, 0.5))
    ctx.add(ash, "ash_burnt", uv_scale=1.0, smooth=50, patches=0.0, edge=0.2)
    for k in range(6):
        rr = ctx.rnd(f"char{k}")
        L = rr.uniform(0.35, 0.6)
        pl = P.plank(f"char{k}", L, rr.uniform(0.05, 0.09), rr.uniform(0.02, 0.04), cuts=1)
        P.break_end(pl, L / 2 - 0.05, rr, side=1, depth=0.06)
        K.noise_disp(pl, 0.006, scale=12.0, seed=rr.randint(0, 999))
        a = k * math.tau / 6 + rr.uniform(-0.3, 0.3)
        K.place(pl, rot=(0, -rr.uniform(35, 65), math.degrees(a)))
        K.place(pl, (math.cos(a) * 0.1, math.sin(a) * 0.1, 0.74))
        ctx.add(pl, "wood_charred", uv="box", long_axis=None, patches=0.0, edge=0.4)
    # Coals in the ash: cold charcoal unless the barrel burns (ember_glow). A fed fire has a deep
    # bed and glowing log ends; one burning low only a few coals.
    er = ctx.rnd("embers")
    for k in range(16 if ctx.clean else 7):
        a, d = er.uniform(0, math.tau), 0.2 * math.sqrt(er.random())
        z = 0.5 + 0.08 * math.sqrt(max(0.0, 1.0 - (d / 0.25) ** 2))  # on the ash dome, half sunk
        e = K.blob(f"ember{k}", er.uniform(0.014, 0.03), subdiv=1, rough=0.3, seed=er.randint(0, 999),
                   scale=(1.0, 1.0, 0.6), center=(math.cos(a) * d, math.sin(a) * d, z - 0.004))
        ctx.add(e, "ember_glow", uv_scale=1.0, wear=0.0, ao=False)
    if ctx.clean:
        for k in range(3):
            a = k * math.tau / 3 + er.uniform(-0.3, 0.3)
            end = K.cyl(f"logend{k}", er.uniform(0.025, 0.035), 0.012, segs=8)
            K.place(end, (math.cos(a) * 0.1, math.sin(a) * 0.1, 0.6), (er.uniform(-20, 20), er.uniform(-20, 20), 0))
            ctx.add(end, "ember_glow", uv_scale=1.0, wear=0.0, ao=False)
    else:
        spill = K.blob("spill", 0.5, subdiv=2, scale=(0.5, 0.35, 0.04), rough=0.3, seed=r.randint(0, 999), center=(0.25, -0.28, 0.0))
        K.cut_plane(spill, (0, 0, 0.001), (0, 0, -1), keep="below", fill=False)
        ctx.add(spill, "ash_burnt", uv_scale=1.0, smooth=50, patches=0.0)
    pts = [(math.cos(a) * 0.297, math.sin(a) * 0.297, z) for a in [i * math.tau / 12 for i in range(12)] for z in (0.0, 0.86)]
    ctx.col_hull(pts)


BUILDERS = {
    "sleeping_bag": sleeping_bag,
    "camp_stove": camp_stove,
    "candle_cluster": candle_cluster,
    "lantern_camping": lantern_camping,
    "barricade_mattress": barricade_mattress,
    "plywood_leaning": plywood_leaning,
    "sign_plywood_painted": sign_plywood_painted,
    "corpse_remains": corpse_remains,
    "bloody_bandages": bloody_bandages,
    "oil_drum_fire": oil_drum_fire,
}


def build(params: dict, outputs: list[str]) -> None:
    K.run(params, outputs, BUILDERS)
