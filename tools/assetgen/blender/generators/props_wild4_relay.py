"""Forest set pieces, round 4 (ADR-0053): props of the Ridge Relay Hut (w4_ridge_relay_hut), an unmanned microwave
relay hut on a forested ridge the Cordon used to pass its orders on.

The tower: a 20 m guyed lattice tower round the POI's kit platforms (2.2 m square to the top platform, tapering
above it to the antenna whip and a dead beacon, four guys to concrete anchors 6.5 m out), microwave dishes under
fabric radomes on pipe mounts, the platforms' galvanised railings and a spare tower section lying in the yard. The
shelter: 19-inch equipment racks, the standby battery bank and the propane generator. The compound: a 500-gallon
propane tank, a corrugated fuel shed, the chain-link gate swung open, a cable reel, the helipad and its windsock,
and the Cordon's field radio on the top platform.

Conventions (docs/ASSET_PIPELINE.md): metres, Z up, front -Y, origin bottom centre; floor props have their depth
centred on the origin (PoiBuilder's collision box is the def's size centred there). The tower's origin is at the
platforms' centre on the ground; the dish's at the foot of its mount pipe (the dish hangs out toward -Y). Only
shared materials are used. 'clean' is the hut as the phone company kept it, 'worn' a winter after the propane ran
out, 'destroyed' (the racks) gutted.
"""
from __future__ import annotations

import math

from mathutils import Vector

from lib import props_ext_kit as K
from lib import props_wild_parts as W

GALV = "metal_galvanized"
STEEL_DARK = "road_steel_dark"
GREY = "road_paint_grey"
RUST = "road_rust"


def _bx(ctx, name, size, center, mat, *, bevel=0.006, uv_scale=2.0, **kw):
    return ctx.add(K.box(name, size, center=center, bevel=bevel), mat, uv="box", uv_scale=uv_scale, **kw)


def _cy(ctx, name, r, h, center, mat, *, axis="Z", segs=12, r_top=None, uv_scale=2.0, **kw):
    o = K.cyl(name, r, h, segs=segs, center=center, axis=axis, r_top=r_top)
    return ctx.add(o, mat, uv="box", uv_scale=uv_scale, smooth=40, **kw)


def _rods(ctx, name, segs_list, r, mat, *, segs=6, **kw):
    """Many straight members merged into one part: segs_list = [(a, b), ...]."""
    objs = [W.rod_obj(f"{name}{k}", a, b, r, segs=segs) for k, (a, b) in enumerate(segs_list) if (Vector(b) - Vector(a)).length > 1e-4]
    if not objs:
        return None
    return ctx.add(K.merge_parts(objs, name), mat, uv="box", uv_scale=2.0, smooth=50, **kw)


def _centre_depth(ctx) -> None:
    """Moves every part so the model's depth (Blender Y) is centred on the origin."""
    lo, hi = 1e9, -1e9
    for o in ctx.parts:
        for v in o.data.vertices:
            lo = min(lo, v.co.y)
            hi = max(hi, v.co.y)
    for o in ctx.parts:
        K.place(o, (0, -(lo + hi) * 0.5, 0))


def _lattice(ctx, name, z0, z1, h0, h1, bays, mat, *, leg_r=0.045, brace_r=0.016, skip=None):
    """A square lattice from z0 (half-width h0) to z1 (half-width h1): legs, a girt at every bay's top and an X
    brace on every face. skip(face, bay) -> True leaves that face's brace out (a hanging brace)."""
    legs, girts, braces = [], [], []

    def corner(sx, sy, z):
        t = (z - z0) / (z1 - z0)
        h = h0 + (h1 - h0) * t
        return (sx * h, sy * h, z)

    corners = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
    for sx, sy in corners:
        legs.append((corner(sx, sy, z0), corner(sx, sy, z1)))
    for b in range(bays):
        za = z0 + (z1 - z0) * b / bays
        zb = z0 + (z1 - z0) * (b + 1) / bays
        for f in range(4):
            a, c = corners[f], corners[(f + 1) % 4]
            girts.append((corner(*a, zb), corner(*c, zb)))
            if skip is not None and skip(f, b):
                continue
            braces.append((corner(*a, za), corner(*c, zb)))
            braces.append((corner(*c, za), corner(*a, zb)))
    _rods(ctx, f"{name}_legs", legs, leg_r, mat, segs=8, patches=0.5)
    _rods(ctx, f"{name}_girts", girts, brace_r * 1.3, mat, segs=5, patches=0.5)
    _rods(ctx, f"{name}_braces", braces, brace_r, mat, segs=5, patches=0.5)


# ============================================================================================
# The tower
# ============================================================================================

TOWER_H = 18.0
TOWER_HS = 1.1          # half the face: the legs stand just outside the 2 x 2 m kit platforms
PLATFORM_TOP = 12.15    # the top platform's floor (level 4 at floor_height 0.15)
ANCHOR = 6.5


def w4_relay_tower(ctx: K.Ctx) -> None:
    """A 20 m guyed lattice tower: 2.2 m square from the ground to the top platform, tapering above it to a
    0.5 m head with the antenna whip and a dead red beacon; platform frames under every kit platform (the decks
    are the POI's floors), a feeder-cable run down the north-east leg, four guys from three heights to concrete
    anchors 6.5 m out on the axes. Worn: rust-streaked, a brace hanging, the west top guy slack and coiled on
    the ground, the beacon lens gone."""
    mat = RUST if ctx.worn else GALV
    hs = TOWER_HS
    # Lower body: 8 bays of 1.5 m to 12 m, then the taper to the head.
    _lattice(ctx, "lower", 0.0, PLATFORM_TOP - 0.15, hs, hs, 8, mat,
             skip=(lambda f, b: f == 1 and b == 2) if ctx.worn else None)
    _lattice(ctx, "upper", PLATFORM_TOP - 0.15, TOWER_H, hs, 0.35, 4, mat, leg_r=0.038, brace_r=0.014)
    if ctx.worn:
        W.rod(ctx, "hanging_brace", (hs, -hs, 3.0), (hs + 0.25, 0.3, 1.9), 0.016, mat, segs=5)
    # Platform frames just under each kit deck (floor top at L * 3 + 0.15, the slab 0.2 deep).
    frames = []
    for lv in range(1, 5):
        z = lv * 3.0 + 0.15 - 0.27
        e = 1.06
        frames += [((-e, -e, z), (e, -e, z)), ((e, -e, z), (e, e, z)), ((e, e, z), (-e, e, z)), ((-e, e, z), (-e, -e, z))]
        frames += [((-e, -e, z), (-hs, -hs, z)), ((e, -e, z), (hs, -hs, z)), ((e, e, z), (hs, hs, z)), ((-e, e, z), (-hs, hs, z))]
    _rods(ctx, "frames", frames, 0.04, GALV, segs=6, patches=0.4)
    # Base plinths.
    for sx in (-1, 1):
        for sy in (-1, 1):
            _bx(ctx, f"plinth{sx}{sy}", (0.45, 0.45, 0.25), (sx * hs, sy * hs, 0.125), "concrete", bevel=0.02, patches=0.6)
    # Head: the whip, the beacon.
    W.rod(ctx, "whip_base", (0, 0, TOWER_H - 0.6), (0, 0, TOWER_H + 0.5), 0.05, GALV, segs=8)
    W.rod(ctx, "whip", (0, 0, TOWER_H + 0.5), (0, 0, TOWER_H + 2.6), 0.018, GALV, segs=6, r2=0.008)
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.rod(ctx, f"head_strut{sx}{sy}", (sx * 0.35, sy * 0.35, TOWER_H), (0, 0, TOWER_H + 0.3), 0.015, GALV, segs=4)
    _cy(ctx, "beacon_base", 0.08, 0.06, (0.36, 0.36, TOWER_H + 0.03), "road_steel_dark", segs=10)
    if not ctx.worn:
        lens = K.lathe("beacon", [(0.09, 0.0), (0.1, 0.09), (0.065, 0.18), (0.0, 0.2)], segs=12)
        K.place(lens, (0.36, 0.36, TOWER_H + 0.06))
        ctx.add(lens, "lens_red", uv="box", uv_scale=4.0, smooth=40, ao=False)
    # Feeder cables (elliptical waveguide) down the north-east leg into a conduit box at the foot.
    for k in range(3):
        off = 0.07 + k * 0.05
        top = PLATFORM_TOP + 1.2 if k < 2 else 6.15 + 1.2
        pts = [(hs - off, hs - 0.06, 0.6), (hs - off, hs - 0.06, top), (hs - off - 0.3, hs - 0.3, top + 0.3)]
        ctx.add(K.tube(f"feeder{k}", pts, 0.022, segs=6, flat=(1.0, 0.6)), "plastic_black", uv="box", uv_scale=3.0, smooth=40)
    _bx(ctx, "conduit_box", (0.5, 0.35, 0.6), (hs - 0.1, hs + 0.15, 0.3), GREY, bevel=0.01, patches=0.6)
    # Guys from three heights on each face to the four anchors.
    anchors = [(0.0, ANCHOR), (ANCHOR, 0.0), (0.0, -ANCHOR), (-ANCHOR, 0.0)]
    guys = []
    for k, (ax, ay) in enumerate(anchors):
        d = Vector((ax, ay, 0.0)).normalized()
        base = Vector((ax, ay, 0.35))
        for j, z in enumerate((6.0, 12.0, 17.5)):
            t = (z - (PLATFORM_TOP - 0.15)) / (TOWER_H - PLATFORM_TOP + 0.15)
            h = hs if z <= PLATFORM_TOP else hs + (0.35 - hs) * t
            top = Vector((d.x * h, d.y * h, z))
            if ctx.worn and k == 3 and j == 2:
                # The slack guy: it hangs from its clip and lies coiled by the anchor.
                drop = [top, top + Vector((-0.4, 0.2, -4.0)), top + Vector((-0.9, 0.5, -9.0)), Vector((ax + 1.2, 0.6, 0.05))]
                ctx.add(K.tube("slack_guy", drop, 0.008, segs=4), "road_steel_dark", uv="box", uv_scale=4.0, ao=False)
                coil = K.tube("guy_coil", [(ax + 1.2 + 0.35 * math.cos(a), 0.6 + 0.35 * math.sin(a), 0.03)
                                           for a in [i * math.tau / 10 for i in range(11)]], 0.01, segs=4)
                ctx.add(coil, "road_steel_dark", uv="box", uv_scale=4.0, ao=False)
                continue
            guys.append((top, base + Vector((-d.x * 0.25, -d.y * 0.25, 0.0)) * (1 + j * 0.1)))
        # The anchor: a concrete deadman, the anchor rod and the turnbuckles.
        _bx(ctx, f"anchor{k}", (0.9, 0.9, 0.3), (ax, ay, 0.15), "concrete", bevel=0.03, patches=0.7, moss=0.4)
        W.rod(ctx, f"anchor_rod{k}", (ax, ay, 0.25), (ax - d.x * 0.3, ay - d.y * 0.3, 0.45), 0.025, STEEL_DARK, segs=6)
    _rods(ctx, "guys", guys, 0.008, "road_steel_dark", segs=4, ao=False)
    ctx.ground_clamp = True


def w4_relay_tower_section(ctx: K.Ctx) -> None:
    """A spare 3 m section of lattice mast, 1 m square, lying on its side on two timber sleepers with splice
    plates at both ends and a bag of bolts wired to one end. Worn: rusted, the bag split and bolts spilled."""
    L, s = 3.0, 0.5
    mat = RUST if ctx.worn else GALV
    for k, x in enumerate((-0.9, 0.9)):
        _bx(ctx, f"sleeper{k}", (0.14, 1.1, 0.12), (x, 0, 0.06), "wood_weathered", bevel=0.01, uv_scale=1.0, moss=0.3)
    zc = 0.12 + s
    legs, braces = [], []
    corners = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
    for sy, sz in corners:
        legs.append(((-L / 2, sy * s, zc + sz * s), (L / 2, sy * s, zc + sz * s)))
    for b in range(3):
        xa, xb = -L / 2 + b, -L / 2 + b + 1
        for f in range(4):
            (ya, za), (yc, zcc) = corners[f], corners[(f + 1) % 4]
            braces.append(((xb, ya * s, zc + za * s), (xb, yc * s, zc + zcc * s)))
            braces.append(((xa, ya * s, zc + za * s), (xb, yc * s, zc + zcc * s)))
    _rods(ctx, "legs", legs, 0.04, mat, segs=8, patches=0.6)
    _rods(ctx, "braces", braces, 0.015, mat, segs=5, patches=0.6)
    for sx in (-1, 1):
        for sy, sz in corners:
            _bx(ctx, f"plate{sx}{sy}{sz}", (0.02, 0.12, 0.12), (sx * L / 2, sy * s, zc + sz * s), STEEL_DARK, bevel=0.0)
    bag = K.blob("bolt_bag", 0.12, subdiv=1, scale=(1.4, 1.0, 0.7), center=(L / 2 - 0.2, -s - 0.12, 0.09), rough=0.2, seed=3)
    ctx.add(bag, "canvas_olive", uv="box", uv_scale=3.0, smooth=50)
    if ctx.worn:
        r = ctx.drnd("bolts")
        for k in range(8):
            _cy(ctx, f"bolt{k}", 0.012, 0.07, (L / 2 - 0.4 + r.uniform(-0.3, 0.3), -s - 0.35 + r.uniform(-0.2, 0.2), 0.012),
                RUST, axis="X", segs=6)


def w4_relay_dish(ctx: K.Ctx) -> None:
    """A 1.2 m microwave dish under a grey fabric radome on a galvanised pipe mount: two clamp brackets, a
    stiff-arm and the elliptical waveguide looping off the back and down the pipe. The origin is at the foot of
    the mount pipe; the dish hangs out toward -Y. Worn: the radome split and flapping, the dish knocked 12 degrees
    off its aim."""
    R, cz = 0.6, 0.8
    W.rod(ctx, "mount_pipe", (0, 0, 0.0), (0, 0, 1.6), 0.045, GALV, segs=10)
    for z in (0.45, 1.15):
        _bx(ctx, f"clamp{z}", (0.14, 0.12, 0.1), (0, -0.02, z), STEEL_DARK, bevel=0.01)
        W.rod(ctx, f"arm{z}", (0, -0.06, z), (0, -0.2, cz + (z - cz) * 0.6), 0.02, GALV, segs=6)
    W.rod(ctx, "stiff_arm", (0, 0, 1.5), (0.4, -0.25, cz + 0.45), 0.014, GALV, segs=5)
    tilt = 12.0 if ctx.worn else 0.0
    parts = []
    # The reflector: a shallow parabola opening toward -Y, the shroud ring and the radome face.
    prof = [(0.0, 0.0)]
    for i in range(1, 7):
        rr = R * i / 6
        prof.append((rr, rr * rr / (4 * 0.45)))
    dish = K.lathe("reflector", prof, segs=24, cap_top=False)
    K.solidify(dish, 0.012, offset=0.0, even=False)
    K.place(dish, (0, 0, 0), (90, 0, 0))
    parts.append((dish, "road_alu"))
    depth = R * R / (4 * 0.45)
    shroud = K.cyl("shroud", R + 0.02, 0.28, segs=24, caps=False, axis="Y", center=(0, -depth - 0.12, 0))
    K.solidify(shroud, 0.01, offset=0.0, even=False)
    parts.append((shroud, "road_paint_white"))
    face = K.cyl("radome", R + 0.03, 0.02, segs=24, axis="Y", center=(0, -depth - 0.27, 0))
    if ctx.worn:
        K.delete_faces(face, lambda c, n: c.x > 0.05 and c.z < 0.15)
    parts.append((face, "canvas_grey"))
    if ctx.worn:
        flap = K.quad_sheet("radome_flap", (0.05, -depth - 0.28, 0.12), (0.5, -depth - 0.3, 0.12), (0.45, -depth - 0.55, -0.4),
                            (0.05, -depth - 0.45, -0.45), 3, 3)
        K.solidify(flap, 0.004, offset=0.0, even=False)
        parts.append((flap, "canvas_grey"))
    hub = K.cyl("hub", 0.09, 0.14, segs=12, axis="Y", center=(0, 0.05, 0))
    parts.append((hub, STEEL_DARK))
    for o, m in parts:
        K.place(o, (0, 0, 0), (0, 0, tilt))
        K.place(o, (0, -0.32, cz))
        ctx.add(o, m, uv="box", uv_scale=2.0, smooth=40, patches=0.4)
    # Waveguide off the back, down the pipe.
    wg = [(0.0, -0.22, cz), (0.1, -0.08, cz - 0.1), (0.07, 0.06, cz - 0.4), (0.06, 0.06, 0.1)]
    ctx.add(K.tube("waveguide", wg, 0.022, segs=6, flat=(1.0, 0.6)), "plastic_black", uv="box", uv_scale=3.0, smooth=40)


def w4_relay_tower_platform_rail(ctx: K.Ctx) -> None:
    """1 m of galvanised railing for a tower platform's open edge: angle posts at both ends, a top and a mid
    rail and a toe board (origin bottom centre, depth centred). Worn: the mid rail bent out."""
    L, H = 1.0, 1.1
    for k, x in enumerate((-L / 2 + 0.03, L / 2 - 0.03)):
        W.section(ctx, f"post{k}", (x, 0, 0.0), (x, 0, H), W.prof_l(0.045, 0.005), GALV, up=(0, 1, 0), patches=0.4)
    W.rod(ctx, "top", (-L / 2, 0, H), (L / 2, 0, H), 0.021, GALV, segs=8)
    if ctx.worn:
        ctx.add(K.tube("mid", [(-L / 2, 0, H * 0.5), (0.0, -0.12, H * 0.47), (L / 2, 0, H * 0.5)], 0.017, segs=8), GALV,
                uv="box", uv_scale=2.0, smooth=40)
    else:
        W.rod(ctx, "mid", (-L / 2, 0, H * 0.5), (L / 2, 0, H * 0.5), 0.017, GALV, segs=8)
    _bx(ctx, "toe", (L, 0.012, 0.12), (0, 0.0, 0.06), GALV, bevel=0.002)


# ============================================================================================
# The shelter
# ============================================================================================

def w4_relay_equipment_rack(ctx: K.Ctx) -> None:
    """A 19-inch relay rack bolted to the floor: radio shelves with their faceplates and dead LEDs, a patch
    panel spilling jumpers, a fan tray and the coax entering through the top. Worn: two units pulled and a
    shelf hanging; destroyed: gutted, the frame racked over and the cards on the floor."""
    r = ctx.rnd("rack")
    dr = ctx.drnd("rack")
    Wd, D, H = 0.58, 0.56, 1.98
    lean = 6.0 if ctx.destroyed else 0.0
    frame = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            frame.append(W.bar_obj(f"post{sx}{sy}", (sx * (Wd / 2 - 0.02), sy * (D / 2 - 0.02), 0.0),
                                   (sx * (Wd / 2 - 0.02), sy * (D / 2 - 0.02), H), 0.04, 0.04, up=(0, 1, 0)))
    f = K.merge_parts(frame, "frame")
    if lean:
        K.place(f, (0, 0, 0), (0, lean, 0))
    ctx.add(f, "furn_plastic_black", uv="box", uv_scale=2.0, patches=0.6)
    _bx(ctx, "top", (Wd, D, 0.04), (math.sin(math.radians(lean)) * H, 0, H - 0.02), "furn_plastic_black", bevel=0.004)
    _bx(ctx, "plinth", (Wd, D, 0.08), (0, 0, 0.04), "furn_plastic_black", bevel=0.004)
    units = [(0.15, 0.18, "radio"), (0.38, 0.18, "radio"), (0.62, 0.09, "patch"), (0.78, 0.18, "radio"), (1.02, 0.27, "mux"),
             (1.36, 0.18, "radio"), (1.6, 0.09, "fan"), (1.75, 0.14, "psu")]
    pulled = {1, 4} if ctx.worn else set()
    for k, (z, h, kind) in enumerate(units):
        if ctx.destroyed:
            break
        if k in pulled:
            if k == 4:
                o = K.box(f"unit{k}", (Wd - 0.1, D - 0.1, h), center=(0, 0, 0), bevel=0.004)
                K.place(o, (0, 0, 0), (25, 0, 8))
                K.place(o, (0.02, -0.25, z - 0.1))
                ctx.add(o, GREY, uv="box", uv_scale=2.0, patches=0.6)
            continue
        _bx(ctx, f"unit{k}", (Wd - 0.08, D - 0.08, h - 0.01), (0, 0.01, z + h / 2), GREY if kind != "fan" else STEEL_DARK,
            bevel=0.004, patches=0.5)
        face = "lab_panel_grey" if kind in ("radio", "mux") else ("road_pcb" if kind == "patch" else "furn_plastic_black")
        _bx(ctx, f"face{k}", (Wd - 0.02, 0.006, h - 0.012), (0, -D / 2 + 0.03, z + h / 2), face, bevel=0.0, ao=False)
        if kind in ("radio", "mux"):
            for j in range(3):
                led = K.cyl(f"led{k}{j}", 0.006, 0.006, segs=6, axis="Y", center=(-0.2 + j * 0.03, -D / 2 + 0.025, z + h - 0.03))
                ctx.add(led, STEEL_DARK if ctx.worn or r.random() < 0.6 else "lab_glow_red", uv="box", uv_scale=4.0, ao=False)
            for j in range(2):
                kn = K.cyl(f"knob{k}{j}", 0.012, 0.015, segs=8, axis="Y", center=(0.12 + j * 0.06, -D / 2 + 0.022, z + h / 2))
                ctx.add(kn, "road_chrome", uv="box", uv_scale=4.0)
        if kind == "patch":
            for j in range(4):
                x0 = -0.2 + j * 0.12
                ctx.add(K.tube(f"jumper{k}{j}", [(x0, -D / 2 + 0.02, z + 0.05), (x0 + 0.03, -D / 2 - 0.12, z - 0.15 - j * 0.05),
                                                  (x0 + 0.1, -D / 2 + 0.01, z - 0.3)], 0.005, segs=5),
                        ["plastic_yellow", "plastic_blue", "plastic_red", "plastic_white"][j], uv="box", uv_scale=4.0, smooth=40, ao=False)
    if ctx.worn and not ctx.destroyed:
        shelf = K.box("hanging_shelf", (Wd - 0.08, D - 0.1, 0.02), center=(0, 0, 0))
        K.place(shelf, (0, 0, 0), (0, 32, 0))
        K.place(shelf, (0.05, 0.0, 1.22))
        ctx.add(shelf, GREY, uv="box", uv_scale=2.0, patches=0.6)
    if ctx.destroyed:
        for k in range(7):
            card = K.box(f"card{k}", (0.22, 0.16, 0.012), center=(0, 0, 0))
            K.place(card, (dr.uniform(-0.3, 0.3), dr.uniform(-0.55, 0.0), 0.006 + k * 0.004), (0, 0, dr.uniform(0, 180)))
            ctx.add(card, "road_pcb", uv="box", uv_scale=4.0, ao=False)
        for k in range(2):
            o = K.box(f"floor_unit{k}", (0.48, 0.45, 0.17), center=(0, 0, 0), bevel=0.004)
            K.place(o, (0, 0, 0), (dr.uniform(-8, 8), 0, dr.uniform(0, 60)))
            K.place(o, (dr.uniform(-0.15, 0.15), -0.55 - k * 0.1, 0.09 + k * 0.17))
            ctx.add(o, GREY, uv="box", uv_scale=2.0, patches=0.8)
    # Coax in through the top.
    for k in range(3):
        ctx.add(K.tube(f"coax{k}", [(-0.15 + k * 0.1, 0.15, H + 0.4), (-0.15 + k * 0.1, 0.15, H - 0.05),
                                    (-0.15 + k * 0.1, 0.2, H - 0.25)], 0.012, segs=6), "plastic_black", uv="box",
                uv_scale=3.0, smooth=40)
    _centre_depth(ctx)


def w4_relay_battery_bank(ctx: K.Ctx) -> None:
    """A two-tier steel rack of big grey standby cells strapped in rows, copper bus bars along the top, a spill
    tray under it and a hydrometer hung on the end. Worn: a cell cracked open and white with corrosion."""
    r = ctx.drnd("cells")
    Wd, D = 1.6, 0.58
    tiers = (0.12, 0.6)
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.section(ctx, f"post{sx}{sy}", (sx * (Wd / 2 - 0.02), sy * (D / 2 - 0.02), 0.0), (sx * (Wd / 2 - 0.02), sy * (D / 2 - 0.02), 1.05),
                      W.prof_l(0.04, 0.004), STEEL_DARK, up=(0, 1, 0))
    _bx(ctx, "tray", (Wd + 0.04, D + 0.04, 0.05), (0, 0, 0.025), "plastic_black", bevel=0.005)
    for t, z in enumerate(tiers):
        _bx(ctx, f"shelf{t}", (Wd - 0.02, D - 0.02, 0.025), (0, 0, z), STEEL_DARK, bevel=0.003)
        for k in range(6):
            x = -Wd / 2 + 0.16 + k * 0.255
            broken = ctx.worn and t == 1 and k == 2
            _bx(ctx, f"cell{t}{k}", (0.2, 0.32, 0.34), (x, 0.0, z + 0.0125 + 0.17), "plastic_grey", bevel=0.01, patches=0.5)
            for j, py in enumerate((-0.09, 0.09)):
                _cy(ctx, f"term{t}{k}{j}", 0.018, 0.04, (x, py, z + 0.37), "lock_zinc", segs=8)
            if broken:
                for j in range(6):
                    b = K.blob(f"crust{j}", 0.05, subdiv=1, scale=(1.2, 1.0, 0.6),
                               center=(x + r.uniform(-0.08, 0.08), r.uniform(-0.12, 0.12), z + 0.37 + r.uniform(0.0, 0.03)), rough=0.5, seed=j)
                    ctx.add(b, "plastic_white", uv="box", uv_scale=4.0, smooth=50)
        bus = [((-Wd / 2 + 0.16 + k * 0.255, 0.09, z + 0.4), (-Wd / 2 + 0.16 + (k + 1) * 0.255, -0.09, z + 0.4)) for k in range(5)]
        for k, (a, b) in enumerate(bus):
            W.bar(ctx, f"bus{t}{k}", a, b, 0.03, 0.006, "road_brass")
    for t, z in enumerate(tiers):
        _bx(ctx, f"strap{t}", (Wd - 0.04, 0.02, 0.03), (0, -D / 2 + 0.03, z + 0.22), "plastic_black", bevel=0.0)
    W.rod(ctx, "hydrometer", (Wd / 2 + 0.03, -0.1, 0.95), (Wd / 2 + 0.03, -0.1, 0.55), 0.015, "glass_clear", segs=6)
    _cy(ctx, "bulb", 0.03, 0.08, (Wd / 2 + 0.03, -0.1, 0.99), "plastic_black", segs=8)


def w4_relay_generator(ctx: K.Ctx) -> None:
    """A standby generator in a grey louvred enclosure on a concrete pad: the hinged lid, the control panel
    with its hour meter and run lamp, the propane flex hose in at the side and the exhaust out of the back.
    Worn: the lid propped up on its stay, a plug lead off, the meter stopped."""
    Wd, D, H = 1.5, 0.8, 1.0
    _bx(ctx, "pad", (Wd + 0.1, D + 0.1, 0.1), (0, 0, 0.05), "concrete", bevel=0.01, patches=0.6)
    _bx(ctx, "body", (Wd, D, H - 0.12), (0, 0, 0.1 + (H - 0.12) / 2), GREY, bevel=0.02, patches=0.6)
    for k in range(6):
        _bx(ctx, f"louvre{k}", (0.55, 0.012, 0.02), (-0.35, -D / 2 - 0.005, 0.3 + k * 0.08), STEEL_DARK, bevel=0.0)
    lid = K.box("lid", (Wd + 0.03, D + 0.03, 0.06), center=(0, D / 2, 0.03), bevel=0.012)
    if ctx.worn:
        K.place(lid, (0, 0, 0), (-55, 0, 0))
        W.rod(ctx, "stay", (0.6, -D / 2 + 0.05, H - 0.12), (0.6, 0.0, H + 0.45), 0.008, STEEL_DARK, segs=4)
        # Exposed engine under the lid.
        _bx(ctx, "engine", (0.7, 0.5, 0.2), (-0.15, 0.0, H - 0.05), "lab_genset_yellow", bevel=0.02)
        W.rod(ctx, "plug_lead", (0.0, -0.1, H + 0.02), (0.15, -0.3, H - 0.1), 0.006, "plastic_red", segs=4)
    K.place(lid, (0, -D / 2, H - 0.12))
    ctx.add(lid, GREY, uv="box", uv_scale=2.0, patches=0.6)
    _bx(ctx, "panel", (0.42, 0.02, 0.3), (0.45, -D / 2 - 0.01, 0.65), "lab_panel_grey", bevel=0.004)
    meter = K.cyl("meter", 0.04, 0.02, segs=12, axis="Y", center=(0.35, -D / 2 - 0.025, 0.7))
    ctx.add(meter, "ceramic_white", uv="box", uv_scale=4.0, ao=False)
    lamp = K.cyl("run_lamp", 0.018, 0.02, segs=8, axis="Y", center=(0.55, -D / 2 - 0.025, 0.72))
    ctx.add(lamp, "road_steel_dark", uv="box", uv_scale=4.0, ao=False)
    for j in range(2):
        _bx(ctx, f"switch{j}", (0.03, 0.03, 0.05), (0.48 + j * 0.1, -D / 2 - 0.025, 0.58), "plastic_black", bevel=0.0)
    hose = [(Wd / 2, 0.15, 0.3), (Wd / 2 + 0.2, 0.2, 0.25), (Wd / 2 + 0.25, 0.3, 0.05)]
    ctx.add(K.tube("propane_hose", hose, 0.02, segs=6), "plastic_black", uv="box", uv_scale=3.0, smooth=40)
    _cy(ctx, "regulator", 0.05, 0.08, (Wd / 2 + 0.06, 0.15, 0.32), "road_paint_red", axis="X", segs=10)
    ex = [(-0.5, D / 2, 0.75), (-0.5, D / 2 + 0.06, 0.75), (-0.5, D / 2 + 0.06, 0.9)]
    ctx.add(K.tube("exhaust", ex, 0.04, segs=8), RUST, uv="box", uv_scale=3.0, smooth=40)


# ============================================================================================
# The compound
# ============================================================================================

def w4_relay_propane_tank(ctx: K.Ctx) -> None:
    """A 500-gallon propane tank on two concrete saddles: the capsule body, the dome lid over the regulator and
    the float gauge, a pipe down into the ground and a warning stencil. Worn: chalked and rust-bloomed, the dome
    lid off on the ground and the gauge needle on red."""
    L, R = 2.75, 0.5
    cz = 0.38 + R
    body_len = L - 2 * R * 0.6
    prof = [(0.0, -L / 2)]
    for i in range(1, 6):
        a = math.pi / 2 * (1 - i / 6)
        prof.append((R * math.cos(a), -body_len / 2 - R * 0.6 * math.sin(a)))
    prof += [(R, -body_len / 2), (R, body_len / 2)]
    for i in range(1, 6):
        a = math.pi / 2 * i / 6
        prof.append((R * math.cos(a), body_len / 2 + R * 0.6 * math.sin(a)))
    prof.append((0.0, L / 2))
    tank = K.lathe("tank", prof, segs=24)
    K.place(tank, (0, 0, 0), (0, 90, 0))
    K.place(tank, (0, 0, cz))
    ctx.add(tank, "steel_painted_white", uv="box", uv_scale=1.0, smooth=40, patches=0.9 if ctx.worn else 0.4)
    for k, x in enumerate((-0.75, 0.75)):
        _bx(ctx, f"saddle{k}", (0.3, 0.8, 0.42), (x, 0, 0.21), "concrete", bevel=0.02, patches=0.7, moss=0.3)
        _bx(ctx, f"cradle{k}", (0.12, 0.7, 0.06), (x, 0, 0.43), STEEL_DARK, bevel=0.005)
    _cy(ctx, "dome_ring", 0.24, 0.12, (0, 0, cz + R + 0.03), "steel_painted_white", segs=18)
    _cy(ctx, "regulator", 0.05, 0.1, (0.08, 0.0, cz + R + 0.12), "road_paint_red", segs=10)
    gauge = K.cyl("gauge", 0.05, 0.02, segs=12, center=(-0.08, 0.05, cz + R + 0.1))
    ctx.add(gauge, "ceramic_white", uv="box", uv_scale=4.0, ao=False)
    needle_end = (-0.11, 0.08, cz + R + 0.112) if ctx.worn else (-0.05, 0.1, cz + R + 0.112)
    W.rod(ctx, "needle", (-0.08, 0.05, cz + R + 0.112), needle_end, 0.003, "plastic_red", segs=4)
    dome = K.lathe("dome", [(0.0, 0.18), (0.18, 0.15), (0.26, 0.05), (0.26, 0.0)], segs=18)
    if ctx.worn:
        K.place(dome, (0, 0, 0), (180, 0, 30))
        K.place(dome, (0.5, -0.85, 0.18))
    else:
        K.place(dome, (0, 0, cz + R + 0.09))
    ctx.add(dome, "steel_painted_white", uv="box", uv_scale=2.0, smooth=40, patches=0.6)
    pipe = [(0.25, 0.0, cz + R + 0.05), (0.4, 0.0, cz + R + 0.05), (0.45, 0.0, cz + 0.1), (0.45, 0.0, 0.0)]
    ctx.add(K.tube("feed_pipe", pipe, 0.02, segs=6), "road_brass", uv="box", uv_scale=3.0, smooth=40)
    _bx(ctx, "stencil", (0.5, 0.004, 0.12), (-0.5, -R - 0.002, cz + 0.12), "road_paint_red", bevel=0.0, ao=False)


def w4_relay_fuel_shed(ctx: K.Ctx) -> None:
    """A low corrugated fuel shed on a timber frame: a shed roof falling to the back, a board door with its
    hasp and open padlock and a NO SMOKING board, shelves of oil and filters inside, a gas can by the door.
    Worn: the door off its top hinge and leaning, the roof rusted."""
    Wd, D = 1.9, 1.4
    hf, hb = 2.05, 1.75
    hw, hd = Wd / 2, D / 2
    for sx in (-1, 1):
        W.bar(ctx, f"post_f{sx}", (sx * (hw - 0.05), -hd + 0.05, 0.0), (sx * (hw - 0.05), -hd + 0.05, hf), 0.09, 0.09, "wood_weathered")
        W.bar(ctx, f"post_b{sx}", (sx * (hw - 0.05), hd - 0.05, 0.0), (sx * (hw - 0.05), hd - 0.05, hb), 0.09, 0.09, "wood_weathered")
    clad = "farm_corrugated_rust" if ctx.worn else "farm_corrugated_galv"
    # Walls: back and both sides corrugated, the front boarded round the door.
    back = K.quad_sheet("back", (-hw, hd, 0.05), (hw, hd, 0.05), (hw, hd, hb), (-hw, hd, hb), 4, 2, thickness=0.01)
    ctx.add(back, clad, uv="box", uv_scale=1.0, patches=0.6)
    for sx in (-1, 1):
        side = K.quad_sheet(f"side{sx}", (sx * hw, -hd, 0.05), (sx * hw, hd, 0.05), (sx * hw, hd, hb), (sx * hw, -hd, hf), 3, 2,
                            thickness=0.01)
        ctx.add(side, clad, uv="box", uv_scale=1.0, patches=0.6)
    door_w = 0.9
    for sx in (-1, 1):
        x0 = sx * (door_w / 2 + (hw - door_w / 2) / 2)
        _bx(ctx, f"front{sx}", (hw - door_w / 2, 0.025, hf - 0.05), (x0, -hd, 0.05 + (hf - 0.05) / 2), "wood_weathered",
            bevel=0.003, uv_scale=1.0, patches=0.6)
    _bx(ctx, "lintel", (door_w, 0.025, 0.2), (0, -hd, hf - 0.1), "wood_weathered", bevel=0.003, uv_scale=1.0)
    door = K.box("door", (door_w - 0.04, 0.04, hf - 0.3), center=((door_w - 0.04) / 2, 0, (hf - 0.3) / 2), bevel=0.004)
    if ctx.worn:
        K.place(door, (0, 0, 0), (0, -9, -62))
    K.place(door, (-door_w / 2 + 0.02, -hd - 0.03, 0.06))
    ctx.add(door, "wood_painted_green", uv="box", uv_scale=1.0, patches=0.8)
    if not ctx.worn:
        _bx(ctx, "no_smoking", (0.5, 0.01, 0.25), (0.05, -hd - 0.06, 1.45), "paint_red_sign", bevel=0.0)
        _bx(ctx, "no_smoking_bar", (0.42, 0.012, 0.05), (0.05, -hd - 0.065, 1.45), "road_paint_white", bevel=0.0, ao=False)
        _bx(ctx, "hasp", (0.12, 0.02, 0.04), (door_w / 2 - 0.08, -hd - 0.06, 1.0), STEEL_DARK, bevel=0.0)
    lock = K.cyl("padlock", 0.025, 0.02, segs=8, axis="Y", center=(door_w / 2 - 0.05, -hd - 0.08, 0.93))
    ctx.add(lock, "lock_steel", uv="box", uv_scale=4.0)
    slope = math.degrees(math.atan2(hf - hb, D))
    roof = K.box("roof", (Wd + 0.2, D + 0.25, 0.02), center=(0, 0, 0), cuts=(3, 2, 0))
    K.place(roof, (0, 0, 0), (-slope, 0, 0))
    K.place(roof, (0, 0, (hf + hb) / 2 + 0.02))
    ctx.add(roof, clad, uv="box", uv_scale=1.0, patches=0.6)
    # Inside: a shelf of oil cans and filters.
    _bx(ctx, "shelf", (Wd - 0.2, 0.35, 0.025), (0, hd - 0.22, 1.0), "wood_weathered", bevel=0.003)
    for k in range(5):
        _cy(ctx, f"oil{k}", 0.06, 0.2, (-0.6 + k * 0.28, hd - 0.22, 1.11), ["road_paint_red", "road_paint_yellow"][k % 2], segs=10)
    _bx(ctx, "gas_can", (0.36, 0.19, 0.3), (0.62, -hd + 0.35, 0.2), "plastic_red", bevel=0.03)


def w4_relay_gate(ctx: K.Ctx) -> None:
    """A chain-link gate leaf on its own galvanised post, swung open and held back with a twist of wire: a
    tube frame with a mid rail and a diagonal, the mesh, the latch with its chain and open padlock hanging.
    Worn: the mesh torn at the foot and the bottom rail bent."""
    L, H = 1.9, 1.75
    hl = L / 2
    W.rod(ctx, "hinge_post", (hl + 0.04, 0, 0.0), (hl + 0.04, 0, H + 0.12), 0.04, GALV, segs=10)
    _cy(ctx, "post_cap", 0.045, 0.04, (hl + 0.04, 0, H + 0.14), GALV, segs=10)
    frame = [((-hl, 0, 0.08), (hl - 0.04, 0, 0.08)), ((-hl, 0, H), (hl - 0.04, 0, H)), ((-hl, 0, 0.08), (-hl, 0, H)),
             ((hl - 0.04, 0, 0.08), (hl - 0.04, 0, H)), ((-hl, 0, H / 2), (hl - 0.04, 0, H / 2)),
             ((-hl, 0, 0.08), (hl - 0.04, 0, H))]
    _rods(ctx, "frame", frame, 0.02, GALV, segs=8, patches=0.4)
    for k, z in enumerate((0.3, H - 0.3)):
        W.rod(ctx, f"hinge{k}", (hl - 0.04, 0, z), (hl + 0.04, 0, z), 0.025, STEEL_DARK, segs=6)
    mesh = K.quad_sheet("mesh", (-hl, 0.0, 0.1), (hl - 0.05, 0.0, 0.1), (hl - 0.05, 0.0, H - 0.02), (-hl, 0.0, H - 0.02), 6, 6)
    if ctx.worn:
        K.delete_faces(mesh, lambda c, n: c.z < 0.45 and c.x < -0.1)
    ctx.add(mesh, "chainlink", uv="box", uv_scale=1.0, ao=False)
    _bx(ctx, "latch", (0.1, 0.06, 0.08), (-hl - 0.02, 0, 1.0), STEEL_DARK, bevel=0.005)
    chain = W.chain_obj("chain", [(-hl - 0.05, -0.04, 1.0), (-hl - 0.07, -0.05, 0.75), (-hl - 0.05, -0.04, 0.6)])
    ctx.add(chain, "trap_chain", uv="box", uv_scale=4.0)
    lock = K.cyl("padlock", 0.025, 0.02, segs=8, axis="Y", center=(-hl - 0.05, -0.05, 0.56))
    ctx.add(lock, "lock_steel", uv="box", uv_scale=4.0)
    W.rod(ctx, "tie_wire", (-hl + 0.05, 0, H - 0.1), (-hl + 0.05, 0.06, H - 0.05), 0.003, GALV, segs=4)


def w4_relay_helipad(ctx: K.Ctx) -> None:
    """A 6 m square concrete helipad 15 cm proud of the ground: a white edge stripe, a white circle and a
    yellow H, tie-down rings at the corners and moss in the joints. Worn: the paint flaking and a crack across
    the H."""
    S, T = 6.0, 0.15
    slab = K.box("slab", (S, S, T), center=(0, 0, T / 2), bevel=0.02, cuts=(5, 5, 0))
    ctx.add(slab, "concrete", uv="box", uv_scale=0.5, patches=0.8, moss=0.5)
    z = T + 0.002
    paint_wear = 1.0 if ctx.worn else 0.3
    for k, (cx, cy, w, d) in enumerate([(0, -S / 2 + 0.25, S - 0.3, 0.2), (0, S / 2 - 0.25, S - 0.3, 0.2),
                                        (-S / 2 + 0.25, 0, 0.2, S - 0.3), (S / 2 - 0.25, 0, 0.2, S - 0.3)]):
        g = K.grid(f"edge{k}", w, d, 6, 1, center=(cx, cy, z))
        ctx.add(g, "road_paint_white", uv="box", uv_scale=1.0, patches=paint_wear, ao=False)
    ring = W.ring_obj("circle", 2.1, 2.3, 0.004, segs=40)
    K.place(ring, (0, 0, z))
    ctx.add(ring, "road_paint_white", uv="box", uv_scale=1.0, patches=paint_wear, ao=False)
    for k, (cx, cy, w, d) in enumerate([(-0.55, 0, 0.3, 1.8), (0.55, 0, 0.3, 1.8), (0, 0, 0.8, 0.3)]):
        g = K.grid(f"h{k}", w, d, 2, 4, center=(cx, cy, z + 0.001))
        ctx.add(g, "road_paint_yellow", uv="box", uv_scale=1.0, patches=paint_wear, ao=False)
    for sx in (-1, 1):
        for sy in (-1, 1):
            rr = W.ring_obj(f"tie{sx}{sy}", 0.05, 0.065, 0.015, segs=10)
            K.place(rr, (sx * (S / 2 - 0.5), sy * (S / 2 - 0.5), T + 0.008))
            ctx.add(rr, STEEL_DARK, uv="box", uv_scale=4.0)
    if ctx.worn:
        crack = K.tube("crack", [(-2.4, 0.3, T - 0.004), (-0.8, 0.1, T - 0.004), (0.4, -0.25, T - 0.004), (2.6, -0.5, T - 0.004)],
                       0.012, segs=4, flat=(1.0, 0.3))
        ctx.add(crack, "road_tar", uv="box", uv_scale=4.0, ao=False)


def w4_relay_field_radio(ctx: K.Ctx) -> None:
    """An olive-drab Cordon field radio on its battery box: the set's knobs and dial window, the handset on its
    curly cord, a short whip antenna folded back and a frequency card under a rubber band. Worn: the handset
    down on its cord."""
    _bx(ctx, "battery_box", (0.42, 0.28, 0.22), (0, 0, 0.11), "ws_paint_olive", bevel=0.01, patches=0.6)
    _bx(ctx, "set", (0.36, 0.26, 0.26), (0, 0, 0.22 + 0.13), "ws_paint_olive", bevel=0.012, patches=0.6)
    _bx(ctx, "front", (0.32, 0.004, 0.2), (0, -0.132, 0.35), "furn_plastic_black", bevel=0.0)
    for j, x in enumerate((-0.1, 0.0, 0.1)):
        kn = K.cyl(f"knob{j}", 0.018, 0.02, segs=10, axis="Y", center=(x, -0.142, 0.32))
        ctx.add(kn, "plastic_black", uv="box", uv_scale=4.0)
    _bx(ctx, "dial", (0.1, 0.004, 0.04), (0.06, -0.136, 0.42), "glass_clear", bevel=0.0, ao=False)
    _bx(ctx, "card", (0.12, 0.003, 0.08), (-0.08, -0.137, 0.42), "item_paper_ledger", bevel=0.0, ao=False)
    W.rod(ctx, "whip_base", (0.14, 0.08, 0.48), (0.14, 0.08, 0.54), 0.012, "plastic_black", segs=6)
    W.rod(ctx, "whip", (0.14, 0.08, 0.54), (-0.15, 0.1, 0.56), 0.004, STEEL_DARK, segs=4)
    if ctx.worn:
        hs = [(-0.17, -0.14, 0.38), (-0.2, -0.2, 0.2), (-0.22, -0.25, 0.04)]
        hand_at = (-0.24, -0.3, 0.03)
        hand_rot = (90, 0, 30)
    else:
        hs = [(-0.17, -0.14, 0.38), (-0.2, -0.12, 0.45), (-0.12, 0.0, 0.5)]
        hand_at = (-0.06, 0.02, 0.515)
        hand_rot = (0, 90, 0)
    ctx.add(K.tube("cord", hs, 0.006, segs=5), "plastic_black", uv="box", uv_scale=4.0, smooth=40, ao=False)
    h = K.box("handset", (0.2, 0.05, 0.04), center=(0, 0, 0), bevel=0.01)
    K.place(h, (0, 0, 0), hand_rot)
    K.place(h, hand_at)
    ctx.add(h, "plastic_black", uv="box", uv_scale=4.0)


def w4_relay_cable_reel(ctx: K.Ctx) -> None:
    """A plywood cable drum on its rim, the axis along X, a few turns of black coax left on it and the loose end
    trailing, chocked with a brick. Worn: the plywood delaminating, the coax gone."""
    R, hw = 0.5, 0.33
    for sx in (-1, 1):
        d = K.cyl(f"flange{sx}", R, 0.03, segs=24, axis="X", center=(sx * hw, 0, R))
        ctx.add(d, "road_plywood", uv="box", uv_scale=1.0, patches=0.8 if ctx.worn else 0.5)
    core = K.cyl("core", 0.18, 2 * hw - 0.03, segs=16, axis="X", center=(0, 0, R))
    ctx.add(core, "road_plywood", uv="box", uv_scale=1.0)
    if not ctx.worn:
        wrap = K.cyl("coax_wrap", 0.26, 2 * hw - 0.06, segs=18, axis="X", center=(0, 0, R))
        ctx.add(wrap, "plastic_black", uv="box", uv_scale=3.0, smooth=40)
        end = [(0.1, -0.26, R), (0.15, -0.5, 0.2), (0.2, -0.75, 0.02), (0.5, -0.9, 0.02)]
        ctx.add(K.tube("coax_end", end, 0.012, segs=6), "plastic_black", uv="box", uv_scale=3.0, smooth=40)
    _bx(ctx, "brick", (0.2, 0.1, 0.07), (0.0, -0.42, 0.035), "brick", bevel=0.005)


def w4_relay_windsock(ctx: K.Ctx) -> None:
    """An orange windsock on a hinged galvanised pole: a concrete collar, the hinge plate, the swivel arm with
    its hoop and the cone of the sock streaming toward +X. Worn: the sock torn to a rag hanging from the hoop."""
    Hp = 4.3
    _cy(ctx, "collar", 0.18, 0.12, (0, 0, 0.06), "concrete", segs=14)
    W.rod(ctx, "pole", (0, 0, 0.0), (0, 0, Hp), 0.045, GALV, segs=10)
    _bx(ctx, "hinge", (0.14, 0.03, 0.2), (0, -0.05, 1.2), STEEL_DARK, bevel=0.004)
    W.rod(ctx, "arm", (0, 0, Hp), (0.25, 0, Hp), 0.015, GALV, segs=6)
    hoop = K.tube("hoop", [(0.25, 0.2 * math.cos(a), Hp + 0.2 * math.sin(a)) for a in [i * math.tau / 14 for i in range(14)]], 0.008,
                  segs=4, closed=True)
    ctx.add(hoop, GALV, uv="box", uv_scale=4.0)
    if ctx.worn:
        sock = K.cyl("sock", 0.19, 0.6, segs=12, r_top=0.08, caps=False, center=(0.3, 0, Hp - 0.3))
    else:
        sock = K.cyl("sock", 0.19, 1.2, segs=12, r_top=0.07, caps=False, axis="X", center=(0.85, 0, Hp - 0.05))
    K.solidify(sock, 0.004, offset=0.0, even=False)
    ctx.add(sock, "plastic_orange", uv="box", uv_scale=2.0, smooth=40, ao=False)


BUILDERS = {
    "w4_relay_tower": w4_relay_tower,
    "w4_relay_tower_section": w4_relay_tower_section,
    "w4_relay_dish": w4_relay_dish,
    "w4_relay_tower_platform_rail": w4_relay_tower_platform_rail,
    "w4_relay_equipment_rack": w4_relay_equipment_rack,
    "w4_relay_battery_bank": w4_relay_battery_bank,
    "w4_relay_generator": w4_relay_generator,
    "w4_relay_propane_tank": w4_relay_propane_tank,
    "w4_relay_fuel_shed": w4_relay_fuel_shed,
    "w4_relay_gate": w4_relay_gate,
    "w4_relay_helipad": w4_relay_helipad,
    "w4_relay_field_radio": w4_relay_field_radio,
    "w4_relay_cable_reel": w4_relay_cable_reel,
    "w4_relay_windsock": w4_relay_windsock,
}


def build(params: dict, outputs: list[str]) -> None:
    K.run(params, outputs, BUILDERS)
