"""Forest set pieces, round 4 (ADR-0053): props of the Dunmore Timber truck depot (w4_logging_truck_depot), a logging
company's truck shop deep in the timber.

The yard: a loaded log truck (a conventional-cab tractor hauling a pole trailer of long fir under binder chains),
the weighbridge it sits on, a squat diesel pump on its concrete island, the horizontal storage tank on its saddles,
the log deck's tall stack and a low cull pile, and a yellow log loader with its forks down. The shop: the bare tractor
up on a four-post drive-on lift, oak planks over the inspection pit, a welding cart, parts shelving, the dispatcher's
radio console, the truck board on her wall and a stack of log-truck tyres.

Conventions (docs/ASSET_PIPELINE.md): metres, Z up, front -Y, origin bottom centre; floor props have their depth
centred on the origin (PoiBuilder's collision box is the def's size centred there). The truck board hangs with its
origin on the wall plane, bottom centre, reaching out toward -Y. Vehicles face -Y (the cab at the front). Only shared
materials are used. 'clean' is the depot the week the Cordon shut the roads, 'worn' a season or two later, 'destroyed'
looted and knocked about.
"""
from __future__ import annotations

import math

from mathutils import Vector

from lib import props_ext_kit as K
from lib import props_ext_parts as P
from lib import props_wild_parts as W

TRUCK_PAINT = "car_paint_green"
CHASSIS = "road_steel_dark"
STEEL = "road_steel"
GALV = "metal_galvanized"
CHROME = "chrome_pitted"
GLASS = "window_grime"
TYRE = "tyre_rubber"
LIFT = "road_paint_lift"
CONCRETE = "road_concrete"
YELLOW = "road_paint_yellow"
LOADER = "wild_paint_skidder_yellow"
SHELF = "metal_shelf_grey"


def _bx(ctx, name, size, center, mat, *, bevel=0.006, uv_scale=2.0, cuts=(0, 0, 0), **kw):
    return ctx.add(K.box(name, size, center=center, bevel=bevel, cuts=cuts), mat, uv="box", uv_scale=uv_scale, **kw)


def _cy(ctx, name, r, h, center, mat, *, axis="Z", segs=12, r_top=None, uv_scale=2.0, **kw):
    o = K.cyl(name, r, h, segs=segs, center=center, axis=axis, r_top=r_top)
    return ctx.add(o, mat, uv="box", uv_scale=uv_scale, smooth=40, **kw)


def _centre_depth(ctx) -> None:
    """Moves every part so the model's depth (Blender Y) is centred on the origin, as PoiBuilder centres the
    def's collision box there."""
    lo, hi = 1e9, -1e9
    for o in ctx.parts:
        for v in o.data.vertices:
            lo = min(lo, v.co.y)
            hi = max(hi, v.co.y)
    for o in ctx.parts:
        K.place(o, (0, -(lo + hi) * 0.5, 0))


def _wheel(ctx, name, x, y, z, r_out, width, *, flat=0.0, rim_mat=STEEL, dual=False):
    """A truck wheel round the X axis at (x, y, z): the tyre, a steel disc rim and its hub; `dual` adds the inner
    tyre of a dual pair."""
    xs = [x] if not dual else [x, x - math.copysign(width + 0.03, x)]
    for k, xx in enumerate(xs):
        t = P.tyre(f"{name}t{k}", r_out, r_out * 0.58, width, segs=20)
        K.place(t, (xx, y, z))
        if flat > 0.0:
            P.flatten_tyre(t, z, r_out, amount=flat, ground=0.0)
        ctx.add(t, TYRE, uv_scale=1.5, smooth=40, patches=0.3, low=0.6, low_h=0.5)
    rim = P.steel_rim(f"{name}rim", r_out * 0.6, width * 0.9, segs=16)
    K.place(rim, rot=(0, 0, 0 if x > 0 else 180))
    K.place(rim, (x, y, z))
    ctx.add(rim, rim_mat, uv_scale=1.5, smooth=40, patches=0.5, edge=0.7)
    hub = K.cyl(f"{name}hub", r_out * 0.17, 0.08, segs=10, axis="X", center=(x + math.copysign(width * 0.45, x), y, z))
    ctx.add(hub, CHROME, uv_scale=3.0, smooth=40)


def _log(ctx, name, L, R, seed, at, rot, *, moss=0.15, bark="wild_log_bark"):
    lg = W.log_obj(name, L, R, seed, sides=12, rings=8, taper=0.1, bow=0.03, bark=bark)
    K.place(lg, at, rot)
    return ctx.add(lg, None, uv=None, smooth=50, patches=0.3, edge=0.6, moss=moss)


# ============================================================================================
# Trucks
# ============================================================================================

def _tractor(ctx, y0: float, *, hood_up: bool = False, wheel_off: bool = False) -> None:
    """A conventional-cab log truck tractor whose front bumper is at y = y0, running back 6.8 m toward +Y: long hood,
    day cab, twin stacks, fuel tanks, the headache rack, the tandem drive axles and a log bunk with stakes over them."""
    worn = ctx.worn
    flat = 0.3 if worn else 0.0
    r = ctx.rnd(f"tractor{y0}")
    # Frame rails, bumper.
    for sx in (-1, 1):
        W.section(ctx, f"rail{sx}", (sx * 0.45, y0 + 0.3, 0.95), (sx * 0.45, y0 + 6.8, 0.95), W.prof_c(0.3, 0.09, 0.01), CHASSIS)
    _bx(ctx, "bumper", (2.4, 0.22, 0.32), (0, y0 + 0.12, 0.82), CHROME, bevel=0.03, patches=0.5)
    # Axles and wheels.
    ys = y0 + 1.2
    W.rod(ctx, "steer_axle", (-0.9, ys, 0.55), (0.9, ys, 0.55), 0.07, CHASSIS, segs=10)
    for sx in (-1, 1):
        if wheel_off and sx > 0:
            # The wheel leant against the bumper and the hub on a jack stand.
            t = P.tyre("off_tyre", 0.53, 0.31, 0.3, segs=20)
            K.place(t, rot=(0, 0, 90))
            K.place(t, rot=(-12, 0, 0))
            K.place(t, (1.65, y0 - 0.25, 0.55))
            ctx.add(t, TYRE, uv_scale=1.5, smooth=40, patches=0.3)
            W.rod(ctx, "jack_post", (1.0, ys, 0.0), (1.0, ys, 0.45), 0.04, "road_paint_red", segs=8)
            _bx(ctx, "jack_base", (0.3, 0.3, 0.04), (1.0, ys, 0.02), "road_paint_red", bevel=0.005)
            continue
        _wheel(ctx, f"steer{sx}", sx * 1.03, ys, 0.53, 0.53, 0.3, flat=flat)
    for k, yd in enumerate((y0 + 4.85, y0 + 6.1)):
        W.rod(ctx, f"drive_axle{k}", (-0.95, yd, 0.53), (0.95, yd, 0.53), 0.09, CHASSIS, segs=10)
        diff = K.blob(f"diff{k}", 0.3, subdiv=2, scale=(0.9, 0.8, 0.8), center=(0, yd, 0.53))
        ctx.add(diff, CHASSIS, uv_scale=1.5, smooth=40, patches=0.5)
        for sx in (-1, 1):
            _wheel(ctx, f"drive{k}{sx}", sx * 1.03, yd, 0.53, 0.53, 0.27, flat=flat, dual=True)
    # Hood (tilts forward about the bumper when up), grille, fenders.
    hood = []
    hb = K.box("hood", (1.5, 2.6, 1.0), center=(0, y0 + 1.55, 1.65), bevel=0.08, bevel_segs=2, cuts=(2, 3, 1))
    hood.append(ctx.add(hb, TRUCK_PAINT, uv_scale=1.0, smooth=35, patches=0.4, edge=0.7))
    grille = K.box("grille", (1.1, 0.06, 0.85), center=(0, y0 + 0.24, 1.6), bevel=0.01)
    hood.append(ctx.add(grille, CHROME, uv_scale=2.0, patches=0.5))
    for k in range(8):
        hood.append(W.bar(ctx, f"grille_bar{k}", (-0.5, y0 + 0.2, 1.24 + k * 0.1), (0.5, y0 + 0.2, 1.24 + k * 0.1), 0.03, 0.02, CHASSIS))
    for sx in (-1, 1):
        pts = [(sx * 1.0, ys + 0.75 * math.cos(a), 0.55 + 0.75 * math.sin(a)) for a in [math.radians(d) for d in (5, 40, 75, 110, 145, 175)]]
        fd = K.sweep(f"fender{sx}", pts, [(-0.2, -0.005), (0.2, -0.005), (0.2, 0.005), (-0.2, 0.005)], up=(1, 0, 0))
        hood.append(ctx.add(fd, TRUCK_PAINT, uv_scale=1.0, smooth=40, patches=0.4, edge=0.7))
        lamp = K.cyl(f"headlamp{sx}", 0.11, 0.06, segs=14, axis="Y", center=(sx * 0.68, y0 + 0.3, 1.35))
        hood.append(ctx.add(lamp, "lens_clear", uv_scale=2.0, smooth=40, ao=False))
    if hood_up:
        for o in hood:
            K.place(o, (0, -(y0 + 0.2), -1.0))
            K.place(o, rot=(62, 0, 0))
            K.place(o, (0, y0 + 0.2, 1.0))
        eng = K.box("engine", (0.9, 1.6, 0.75), center=(0, y0 + 1.7, 1.45), bevel=0.05)
        ctx.add(eng, "wild_cast_iron_rust" if worn else "road_engine", uv_scale=1.0, patches=0.6)
        rad = K.box("radiator", (1.1, 0.12, 0.9), center=(0, y0 + 0.65, 1.45), bevel=0.01)
        ctx.add(rad, CHASSIS, uv_scale=2.0, patches=0.5)
    # Cab.
    cy0, cy1 = y0 + 2.85, y0 + 4.55
    cab = K.box("cab", (2.2, cy1 - cy0, 1.55), center=(0, (cy0 + cy1) / 2, 2.12), bevel=0.06, bevel_segs=2, cuts=(2, 2, 1))
    ctx.add(cab, TRUCK_PAINT, uv_scale=1.0, smooth=35, patches=0.4, edge=0.7)
    _bx(ctx, "cab_floor", (2.25, cy1 - cy0, 0.2), (0, (cy0 + cy1) / 2, 1.3), CHASSIS, bevel=0.02)
    glass_gone = worn and r.random() < 0.9
    ws = K.box("windshield", (1.9, 0.02, 0.62), center=(0, cy0 - 0.01, 2.5))
    K.place(ws, (0, 0, 0))
    ctx.add(ws, GLASS if not glass_gone else "road_steel_dark", uv_scale=1.0, wear=0.3, ao=False)
    for sx in (-1, 1):
        sw = K.box(f"sidewin{sx}", (0.02, 0.9, 0.55), center=(sx * 1.11, cy0 + 0.6, 2.45))
        ctx.add(sw, GLASS if (sx < 0 or not worn) else "road_steel_dark", uv_scale=1.0, wear=0.3, ao=False)
        W.rod(ctx, f"mirror_arm{sx}", (sx * 1.1, cy0 + 0.15, 2.4), (sx * 1.38, cy0 + 0.1, 2.4), 0.015, CHROME, segs=6)
        _bx(ctx, f"mirror{sx}", (0.06, 0.18, 0.4), (sx * 1.4, cy0 + 0.1, 2.35), CHROME, bevel=0.01)
        W.rod(ctx, f"step{sx}", (sx * 1.0, cy0 + 0.3, 0.95), (sx * 1.0, cy0 + 1.0, 0.95), 0.03, CHROME, segs=6)
        # Fuel tank under the door and a stack behind the cab.
        tank = K.cyl(f"tank{sx}", 0.3, 1.2, segs=16, axis="Y", center=(sx * 0.95, cy0 + 1.0, 0.72))
        ctx.add(tank, "road_alu", uv="cyl", uv_axis=1, uv_scale=2.0, smooth=40, patches=0.4)
        W.rod(ctx, f"stack{sx}", (sx * 1.15, cy1 + 0.15, 1.3), (sx * 1.15, cy1 + 0.15, 3.7), 0.075, CHROME if not worn else "car_rust", segs=12)
        W.rod(ctx, f"stack_guard{sx}", (sx * 1.15, cy1 + 0.07, 1.8), (sx * 1.15, cy1 + 0.07, 2.8), 0.085, CHROME, segs=12, caps=False)
    # Headache rack behind the cab.
    hy = cy1 + 0.35
    for sx in (-1, 1):
        W.bar(ctx, f"rack_post{sx}", (sx * 1.15, hy, 1.1), (sx * 1.15, hy, 3.35), 0.1, 0.1, CHASSIS)
    for k in range(5):
        W.bar(ctx, f"rack_bar{k}", (-1.15, hy, 1.4 + k * 0.48), (1.15, hy, 1.4 + k * 0.48), 0.08, 0.06, CHASSIS)
    # Log bunk over the drive axles.
    by = y0 + 5.5
    W.section(ctx, "bunk", (-1.25, by, 1.3), (1.25, by, 1.3), W.prof_i(0.25, 0.2, 0.02, 0.015), CHASSIS)
    for sx in (-1, 1):
        W.bar(ctx, f"stake{sx}", (sx * 1.2, by, 1.2), (sx * 1.22, by, 3.0), 0.12, 0.12, CHASSIS)
        flap = K.box(f"flap{sx}", (0.55, 0.02, 0.5), center=(sx * 1.0, y0 + 6.75, 0.5))
        ctx.add(flap, "road_rubber", uv_scale=1.0, patches=0.3)


def w4_depot_log_tractor(ctx: K.Ctx) -> None:
    """The tractor unit of a log truck on its own (it stands on the lift in the shop). Worn: the hood tilted forward
    over the engine, the right steer wheel off and leant on the bumper, the hub on a jack stand."""
    _tractor(ctx, -3.4, hood_up=ctx.worn, wheel_off=ctx.worn)


def w4_depot_log_truck(ctx: K.Ctx) -> None:
    """A loaded log truck: the tractor and a pole trailer under three courses of long fir and larch, binder chains
    cinched over the load. Worn: tyres soft, the windshield out, moss on the top course."""
    y0 = -8.0
    _tractor(ctx, y0)
    worn = ctx.worn
    flat = 0.3 if worn else 0.0
    r = ctx.rnd("load")
    # Reach pole from the tractor's bunk back to the trailer, the trailer's short frame, bunk and axles.
    W.rod(ctx, "reach", (0, y0 + 5.2, 0.98), (0, 6.6, 0.98), 0.1, CHASSIS, segs=10)
    for sx in (-1, 1):
        W.section(ctx, f"trailer_rail{sx}", (sx * 0.42, 4.2, 1.0), (sx * 0.42, 7.85, 1.0), W.prof_c(0.26, 0.08, 0.01), CHASSIS)
    for k, ya in enumerate((5.4, 6.7)):
        W.rod(ctx, f"trailer_axle{k}", (-0.95, ya, 0.53), (0.95, ya, 0.53), 0.08, CHASSIS, segs=10)
        for sx in (-1, 1):
            _wheel(ctx, f"trailer{k}{sx}", sx * 1.03, ya, 0.53, 0.53, 0.27, flat=flat, dual=True)
    by = 6.05
    W.section(ctx, "trailer_bunk", (-1.25, by, 1.3), (1.25, by, 1.3), W.prof_i(0.25, 0.2, 0.02, 0.015), CHASSIS)
    for sx in (-1, 1):
        W.bar(ctx, f"trailer_stake{sx}", (sx * 1.2, by, 1.2), (sx * 1.22, by, 3.0), 0.12, 0.12, CHASSIS)
        pts = [(sx * 1.05, 6.4 + 0.75 * math.cos(a), 0.55 + 0.75 * math.sin(a)) for a in [math.radians(d) for d in (20, 60, 100, 140, 175)]]
        fd = K.sweep(f"trailer_fender{sx}", pts, [(-0.18, -0.004), (0.18, -0.004), (0.18, 0.004), (-0.18, 0.004)], up=(1, 0, 0))
        ctx.add(fd, CHASSIS, uv_scale=1.0, smooth=40, patches=0.5)
        lamp = K.box(f"tail{sx}", (0.18, 0.05, 0.1), center=(sx * 0.85, 7.88, 1.05))
        ctx.add(lamp, "lens_red", uv_scale=2.0, ao=False)
    # The load: three courses of long logs bunk to bunk.
    L, yc = 10.2, 2.75
    courses = [(4, 0.28), (3, 0.27), (2, 0.26)]
    z = 1.43
    crest = z
    for ci, (n, R) in enumerate(courses):
        xs = [(-(n - 1) / 2 + i) * 2 * R for i in range(n)]
        zc = z + R
        for i, x in enumerate(xs):
            Rl = R * r.uniform(0.9, 1.06)
            bark = "wild_log_bark_larch" if r.random() < 0.3 else "wild_log_bark"
            moss = 0.6 if (worn and ci == len(courses) - 1) else 0.12
            _log(ctx, f"load{ci}{i}", L * r.uniform(0.97, 1.0), Rl, r.randint(0, 99999),
                 (x, yc + r.uniform(-0.15, 0.15), zc - (R - Rl)), (r.uniform(-1, 1), 0, 90 + r.uniform(-0.6, 0.6)), moss=moss, bark=bark)
        crest = zc + R
        z = zc + R * 0.75
    top = crest
    # Binder chains over the load, hooked to the bunks' ends.
    for k, yb in enumerate((-1.2, 2.6, 6.6)):
        pts = [(-1.25, yb, 1.35), (-1.0, yb, top - 0.25), (-0.4, yb, top + 0.05), (0.4, yb, top + 0.05), (1.0, yb, top - 0.25),
               (1.25, yb, 1.35)]
        ch = W.chain_obj(f"binder{k}", pts, link=0.07, wire=0.007)
        ctx.add(ch, "trap_chain", uv_scale=4.0, smooth=40, patches=0.5)
        _bx(ctx, f"binder_lever{k}", (0.05, 0.05, 0.45), (1.27, yb, 1.75), "road_paint_yellow", bevel=0.005)


def w4_depot_truck_lift(ctx: K.Ctx) -> None:
    """A four-post drive-on truck lift with its runways raised to 1.55 m: square posts with ladder-slot locks, the
    crossbeams riding on them, two diamond-plate runways, a ramp hanging off the back of each and the power unit on
    the front left post. Worn: the paint chalky and rust in the runway plates."""
    hx, hy, H = 1.78, 4.15, 2.6
    rz = 1.55
    for sx in (-1, 1):
        for sy in (-1, 1):
            _bx(ctx, f"post{sx}{sy}", (0.24, 0.24, H), (sx * hx, sy * hy, H / 2), LIFT, bevel=0.01, patches=0.5)
            _bx(ctx, f"foot{sx}{sy}", (0.4, 0.4, 0.03), (sx * hx, sy * hy, 0.015), LIFT, bevel=0.004)
            _bx(ctx, f"cap{sx}{sy}", (0.3, 0.3, 0.05), (sx * hx, sy * hy, H - 0.02), CHASSIS, bevel=0.005)
            _bx(ctx, f"slots{sx}{sy}", (0.04, 0.01, H - 0.4), (sx * hx - sx * 0.08, sy * hy - sy * 0.125, H / 2), CHASSIS, bevel=0.0)
    for sy in (-1, 1):
        W.section(ctx, f"crossbeam{sy}", (-hx, sy * hy, rz - 0.15), (hx, sy * hy, rz - 0.15), W.prof_c(0.3, 0.2, 0.012), LIFT)
    for sx in (-1, 1):
        x = sx * 1.0
        _bx(ctx, f"runway{sx}", (0.56, 2 * hy - 0.2, 0.06), (x, 0, rz - 0.03), "road_tread", bevel=0.005, uv_scale=1.0, patches=0.6)
        for side in (-1, 1):
            _bx(ctx, f"runway_lip{sx}{side}", (0.03, 2 * hy - 0.2, 0.1), (x + side * 0.29, 0, rz), LIFT, bevel=0.003)
        ramp = K.box(f"ramp{sx}", (0.56, 1.3, 0.05))
        K.place(ramp, rot=(-48, 0, 0))
        K.place(ramp, (x, hy + 0.15, rz - 0.5))
        ctx.add(ramp, "road_tread", uv_scale=1.0, patches=0.6)
        W.rod(ctx, f"cable{sx}", (sx * hx, -hy, H - 0.1), (sx * hx, hy, H - 0.1), 0.012, GALV, segs=6)
    _bx(ctx, "power_unit", (0.3, 0.35, 0.45), (-hx - 0.27, -hy, 1.2), "road_paint_grey", bevel=0.01)
    W.rod(ctx, "hyd_line", (-hx - 0.27, -hy, 0.95), (-hx - 0.12, -hy + 0.1, 0.4), 0.012, "road_rubber", segs=6)
    _bx(ctx, "control", (0.12, 0.1, 0.2), (-hx - 0.27, -hy - 0.2, 1.3), YELLOW, bevel=0.005)


def w4_depot_weighbridge(ctx: K.Ctx) -> None:
    """A pit-mounted truck scale flush with the yard: twelve metres of checker-plate deck in a concrete surround,
    steel ramps off both ends, a yellow stop line and the load cell junction box on the curb. Worn: rust through
    the deck at one corner, gravel in the joints."""
    Wd, L, h = 3.2, 12.0, 0.3
    deck = K.box("deck", (Wd, L, 0.04), center=(0, 0, h - 0.02), cuts=(2, 8, 0))
    ctx.add(deck, "road_tread", uv_scale=1.0, patches=0.7, low=0.4)
    for k in range(5):
        y = -L / 2 + (k + 0.5) * L / 5
        _bx(ctx, f"seam{k}", (Wd, 0.02, 0.01), (0, y + L / 10, h + 0.003), CHASSIS, bevel=0.0, ao=False)
    _bx(ctx, "body", (Wd - 0.05, L - 0.05, h - 0.04), (0, 0, (h - 0.04) / 2), CONCRETE, bevel=0.0, uv_scale=1.0)
    for sx in (-1, 1):
        _bx(ctx, f"curb{sx}", (0.12, L + 2.0, h + 0.04), (sx * (Wd / 2 + 0.06), 0, (h + 0.04) / 2), CONCRETE, bevel=0.015,
            uv_scale=1.0, patches=0.6)
    for sy in (-1, 1):
        ramp = K.prism(f"ramp{sy}", [(0.0, 0.0), (1.0, 0.0), (0.0, h)], Wd, plane="YZ")
        K.place(ramp, rot=(0, 0, 0 if sy > 0 else 180))
        K.place(ramp, (0, sy * L / 2, 0))
        ctx.add(ramp, "road_tread", uv_scale=1.0, patches=0.7, low=0.4)
    _bx(ctx, "stop_line", (Wd - 0.2, 0.15, 0.006), (0, -L / 2 + 0.6, h + 0.003), YELLOW, bevel=0.0, ao=False)
    _bx(ctx, "jbox_lid", (0.3, 0.3, 0.012), (Wd / 2 - 0.3, 2.0, h + 0.006), "road_paint_grey", bevel=0.002)
    if ctx.worn:
        hole = K.box("rust_patch", (0.6, 0.8, 0.005), center=(Wd / 2 - 0.4, L / 2 - 0.6, h + 0.002))
        ctx.add(hole, "car_rust", uv_scale=1.0, ao=False)


def w4_depot_fuel_pump(ctx: K.Ctx) -> None:
    """A squat red commercial diesel pump: the cabinet on its base plate, a mechanical register behind glass on the
    front, the price sign on top, the hose looped on its hook and a high-flow nozzle in the boot. Worn: the hose cut
    off short, the glass starred. Destroyed: the cabinet door hanging and the head knocked crooked."""
    r = ctx.rnd("pump")
    Wd, D = 0.8, 0.5
    _bx(ctx, "base", (0.9, 0.6, 0.06), (0, 0, 0.03), CONCRETE, bevel=0.005)
    _bx(ctx, "cabinet", (Wd, D, 1.0), (0, 0, 0.56), "road_paint_red", bevel=0.02, patches=0.6)
    head = [_bx(ctx, "head", (Wd, D - 0.06, 0.5), (0, 0, 1.31), "road_paint_red", bevel=0.02, patches=0.6)]
    head.append(_bx(ctx, "register", (0.6, 0.02, 0.3), (0, -D / 2 + 0.02, 1.33), "road_paint_white", bevel=0.0, ao=False))
    for k in range(3):
        head.append(_bx(ctx, f"wheel{k}", (0.42, 0.015, 0.05), (0.0, -D / 2 + 0.005, 1.24 + k * 0.08), "road_paint_black", bevel=0.0, ao=False))
    glass = K.box("glass", (0.64, 0.01, 0.34), center=(0, -D / 2 - 0.0, 1.33))
    head.append(ctx.add(glass, "road_glass" if not ctx.worn else "window_grime", uv_scale=1.0, wear=0.2, ao=False))
    head.append(_bx(ctx, "sign", (0.7, 0.06, 0.24), (0, 0, 1.7), "road_paint_white", bevel=0.01))
    head.append(_bx(ctx, "sign_band", (0.72, 0.065, 0.05), (0, 0, 1.62), "road_paint_red", bevel=0.0))
    if ctx.destroyed:
        for o in head:
            K.place(o, (0, 0, -1.06))
            K.place(o, rot=(0, 9, 4))
            K.place(o, (0.02, 0, 1.06))
        door = K.box("door", (0.6, 0.02, 0.8), center=(0.3, 0, 0.4))
        K.place(door, rot=(0, 0, -70))
        K.place(door, (-0.3, -D / 2 - 0.01, 0.18))
        ctx.add(door, "road_paint_red", uv_scale=2.0, patches=0.6)
    # Hook, hose and nozzle on the side.
    _bx(ctx, "boot", (0.06, 0.12, 0.2), (Wd / 2 + 0.04, -0.05, 1.0), CHASSIS, bevel=0.005)
    if not ctx.worn:
        hose = [(Wd / 2 - 0.05, 0.15, 1.5), (Wd / 2 + 0.08, 0.15, 1.45), (Wd / 2 + 0.12, 0.1, 0.9), (Wd / 2 + 0.1, 0.0, 0.45),
                (Wd / 2 + 0.08, -0.08, 0.6), (Wd / 2 + 0.06, -0.05, 0.98)]
        ctx.add(K.tube("hose", hose, 0.022, segs=8), "road_rubber", uv_scale=3.0, smooth=50, patches=0.3)
        nz = K.box("nozzle", (0.05, 0.08, 0.26), center=(Wd / 2 + 0.05, -0.05, 1.08), bevel=0.01)
        ctx.add(nz, "road_paint_green", uv_scale=3.0, patches=0.4)
        W.rod(ctx, "spout", (Wd / 2 + 0.05, -0.05, 0.95), (Wd / 2 + 0.05, -0.12, 0.85), 0.012, CHROME, segs=6)
    else:
        hose = [(Wd / 2 - 0.05, 0.15, 1.5), (Wd / 2 + 0.08, 0.15, 1.45), (Wd / 2 + 0.1, 0.12 + r.uniform(-0.02, 0.02), 1.15)]
        ctx.add(K.tube("hose_cut", hose, 0.022, segs=8), "road_rubber", uv_scale=3.0, smooth=50, patches=0.3)


def w4_depot_fuel_island(ctx: K.Ctx) -> None:
    """A raised concrete pump island: rounded ends with steel nose caps and a yellow bollard at each end."""
    Wd, L, h = 1.2, 4.6, 0.18
    _bx(ctx, "slab", (Wd, L - Wd, h), (0, 0, h / 2), CONCRETE, bevel=0.02, uv_scale=1.0, patches=0.5)
    for sy in (-1, 1):
        nose = K.cyl(f"nose{sy}", Wd / 2, h, segs=16, center=(0, sy * (L - Wd) / 2, h / 2))
        ctx.add(nose, CONCRETE, uv_scale=1.0, smooth=40, patches=0.5)
        rim = K.cyl(f"nose_cap{sy}", Wd / 2 + 0.01, 0.05, segs=16, center=(0, sy * (L - Wd) / 2, h - 0.02))
        ctx.add(rim, GALV, uv_scale=2.0, smooth=40, patches=0.5)
        _cy(ctx, f"bollard{sy}", 0.08, 1.0, (0, sy * (L / 2 - 0.25), h + 0.5), YELLOW, segs=12, patches=0.6)
        _cy(ctx, f"bollard_cap{sy}", 0.085, 0.04, (0, sy * (L / 2 - 0.25), h + 1.0), YELLOW, segs=12)


def w4_depot_fuel_tank(ctx: K.Ctx) -> None:
    """A horizontal steel diesel tank on three concrete saddles: rolled shell with banded seams and dished heads,
    the fill neck, gauge and vent pipe on top, a ladder up its front head, the outlet valve and a pipe running down
    to the pumps. Worn: rust weeping from the seams and the saddles mossy."""
    R, L, zc = 1.2, 6.4, 1.75
    shell = K.cyl("shell", R, L, segs=28, axis="Y", center=(0, 0, zc), cuts=6)
    ctx.add(shell, "lab_tank_green", uv="cyl", uv_axis=1, uv_scale=1.0, smooth=40, patches=0.6)
    for sy in (-1, 1):
        prof = [(0.0, 0.25), (R * 0.5, 0.2), (R * 0.85, 0.1), (R, 0.0)]
        head = K.lathe(f"head{sy}", [(rr, zz) for rr, zz in reversed(prof)], segs=28, cap_bottom=False)
        K.place(head, rot=(-90 * sy, 0, 0))
        K.place(head, (0, sy * L / 2, zc))
        ctx.add(head, "lab_tank_green", uv_scale=1.0, smooth=40, patches=0.6)
    for k in range(4):
        y = -L / 2 + (k + 0.5) * L / 4
        band = K.cyl(f"band{k}", R + 0.012, 0.06, segs=28, axis="Y", center=(0, y, zc))
        ctx.add(band, "lab_tank_green", uv_scale=2.0, smooth=40, patches=0.7)
    for k, y in enumerate((-2.3, 0.0, 2.3)):
        sad = K.prism(f"saddle{k}", [(-1.05, 0.0), (1.05, 0.0), (1.05, 0.75), (0.75, 0.75), (0.45, 0.68), (0.0, 0.62),
                                     (-0.45, 0.68), (-0.75, 0.75), (-1.05, 0.75)], 0.4, plane="XZ", offset=y)
        ctx.add(sad, CONCRETE, uv_scale=1.0, patches=0.5, moss=0.5 if ctx.worn else 0.0)
    top = zc + R
    _cy(ctx, "fill_neck", 0.1, 0.25, (0.3, 1.5, top + 0.08), STEEL, segs=12)
    _cy(ctx, "fill_cap", 0.12, 0.05, (0.3, 1.5, top + 0.22), "road_paint_yellow", segs=12)
    W.rod(ctx, "vent", (-0.3, 0.6, top - 0.05), (-0.3, 0.6, top + 0.35), 0.04, GALV, segs=8)
    vc = K.cyl("vent_cap", 0.09, 0.08, segs=10, r_top=0.03, center=(-0.3, 0.6, top + 0.38))
    ctx.add(vc, GALV, uv_scale=2.0, smooth=40)
    _cy(ctx, "gauge", 0.08, 0.06, (0.0, -0.8, top + 0.02), "road_chrome", segs=12)
    # Ladder up the front head, and a walk plate on top.
    ly = -L / 2 - 0.45
    for sx in (-1, 1):
        W.rod(ctx, f"ladder_rail{sx}", (sx * 0.22, ly, 0.0), (sx * 0.22, ly + 0.15, top + 0.9), 0.025, GALV, segs=6)
    for k in range(9):
        z = 0.3 + k * 0.33
        W.rod(ctx, f"rung{k}", (-0.22, ly + 0.15 * z / (top + 0.9), z), (0.22, ly + 0.15 * z / (top + 0.9), z), 0.016, GALV, segs=6)
    _bx(ctx, "walk", (0.6, 1.4, 0.03), (0, -L / 2 + 0.6, top + 0.04), "road_tread", bevel=0.0, uv_scale=1.0)
    # Outlet valve and pipe running off toward the pumps (-X).
    W.rod(ctx, "outlet", (-0.4, -L / 2 + 0.4, zc - R + 0.05), (-0.4, -L / 2 + 0.4, 0.35), 0.045, GALV, segs=8)
    _cy(ctx, "valve", 0.09, 0.12, (-0.4, -L / 2 + 0.4, 0.45), "road_paint_red", segs=10)
    W.rod(ctx, "pipe", (-0.4, -L / 2 + 0.4, 0.25), (-1.38, -L / 2 + 0.4, 0.25), 0.04, GALV, segs=8)


# ============================================================================================
# Log deck and loader
# ============================================================================================

def w4_depot_log_stack(ctx: K.Ctx) -> None:
    """The log deck's tall stack: four courses of long logs on two skid logs between steel stakes, the ends sawn
    and spray-marked. Worn: moss on the top course and the ends checked grey."""
    r = ctx.rnd("stack")
    for sx in (-1, 1):
        sk = W.log_obj(f"skid{sx}", 3.9, 0.15, r.randint(0, 999), sides=10, rings=4, taper=0.05)
        K.place(sk, (sx * 2.4, 0, 0.15), (0, 0, 90))
        ctx.add(sk, None, uv=None, smooth=50, patches=0.4, moss=0.5)
    courses = [(6, 0.31), (5, 0.3), (4, 0.29), (3, 0.28)]
    z = 0.3
    for ci, (n, R) in enumerate(courses):
        ys = [(-(n - 1) / 2 + i) * 2 * R * 1.02 for i in range(n)]
        zc = z + R
        for i, y in enumerate(ys):
            Rl = R * r.uniform(0.9, 1.05)
            bark = "wild_log_bark_larch" if r.random() < 0.35 else "wild_log_bark"
            moss = 0.65 if (ctx.worn and ci == len(courses) - 1) else 0.15
            Ll = r.uniform(6.2, 6.7)
            xo = r.uniform(-0.15, 0.15)
            _log(ctx, f"log{ci}{i}", Ll, Rl, r.randint(0, 99999), (xo, y, zc - (R - Rl)),
                 (r.uniform(-1.5, 1.5), 0, r.uniform(-1.0, 1.0) + (180 if r.random() < 0.5 else 0)), moss=moss, bark=bark)
            if r.random() < 0.6:
                dot = K.cyl(f"mark{ci}{i}", Rl * 0.35, 0.01, segs=10, axis="X", center=(xo + Ll * 0.5 + 0.01, y, zc - (R - Rl)))
                ctx.add(dot, "road_paint_orange", uv_scale=4.0, ao=False)
        z = zc + R * 0.72
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.bar(ctx, f"stake{sx}{sy}", (sx * 2.4, sy * 1.94, 0.0), (sx * 2.4, sy * 1.96, 2.45), 0.08, 0.08, CHASSIS)


def w4_depot_log_pile_low(ctx: K.Ctx) -> None:
    """A low pile of cull logs, two courses on the ground, chocked at the ends: low enough to scramble over."""
    r = ctx.rnd("pile")
    z = 0.0
    for ci, (n, R) in enumerate([(4, 0.26), (3, 0.23)]):
        ys = [(-(n - 1) / 2 + i) * 2 * R * 1.04 for i in range(n)]
        zc = z + R
        for i, y in enumerate(ys):
            Rl = R * r.uniform(0.88, 1.04)
            _log(ctx, f"cull{ci}{i}", r.uniform(5.0, 5.8), Rl, r.randint(0, 99999), (r.uniform(-0.3, 0.3), y, zc - (R - Rl)),
                 (r.uniform(-2, 2), 0, r.uniform(-3, 3)), moss=0.5 if ctx.worn else 0.25)
        z = zc + R * 0.7
    for sy in (-1, 1):
        ch = K.prism(f"chock{sy}", [(0.0, 0.0), (0.3, 0.0), (0.0, 0.25)], 0.25, plane="YZ")
        K.place(ch, rot=(0, 0, 0 if sy > 0 else 180))
        K.place(ch, (0.0, sy * 1.05, 0))
        ctx.add(ch, "wood_weathered", uv_scale=1.0, patches=0.5)


def _lugged_tyre(ctx, name, x, y, z, r_out, r_rim, width, flat):
    """Big loader tyre with chevron lugs and a steel rim, axle along X, flattened at the bottom."""
    t = P.tyre(name, r_out - 0.05, r_rim, width, segs=20)
    K.place(t, (x, y, z))
    P.flatten_tyre(t, z, r_out - 0.05, amount=flat, ground=0.0)
    ctx.add(t, TYRE, uv_scale=1.5, smooth=40, patches=0.3, low=0.6, low_h=0.5)
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
    ctx.add(lg, TYRE, uv_scale=1.5, smooth=None, patches=0.3, low=0.6, low_h=0.5)
    rim = P.steel_rim(name + "rim", r_rim + 0.02, width * 0.85, segs=16)
    K.place(rim, rot=(0, 0, 0 if x > 0 else 180))
    K.place(rim, (x, y, z))
    ctx.add(rim, LOADER, uv_scale=1.5, smooth=40, patches=0.4, edge=0.7)


def w4_depot_loader(ctx: K.Ctx) -> None:
    """A yellow articulated wheel loader on log forks: four lugged tyres, the front and rear frames on their pivot,
    lift arms up from the front axle to a fork carriage with two tines on the ground and a curved top clamp, the
    ROPS cab, the engine hood and the counterweight. Worn: tyres flat, the cab glass gone, rust in the forks."""
    worn = ctx.worn
    YF, YR, ZA = -1.55, 1.55, 0.8
    RO, RR, TW, TX = 0.86, 0.45, 0.62, 1.12
    for y in (YF, YR):
        for sx in (-1, 1):
            _lugged_tyre(ctx, f"t{y}{sx}", sx * TX, y, ZA, RO, RR, TW, 0.3 if worn else 0.18)
        W.rod(ctx, f"axle{y}", (-TX + 0.25, y, ZA), (TX - 0.25, y, ZA), 0.12, "wild_cast_iron_rust", segs=12)
        diff = K.blob(f"diff{y}", 0.5, subdiv=2, scale=(0.5, 0.42, 0.42), center=(0, y, ZA))
        ctx.add(diff, "wild_cast_iron_rust", uv_scale=1.5, smooth=40, patches=0.6)
        for sx in (-1, 1):
            pts = [(sx * TX, y + 1.0 * math.cos(a), ZA + 1.0 * math.sin(a)) for a in [math.radians(d) for d in (25, 60, 95, 130, 160)]]
            fd = K.sweep(f"fender{y}{sx}", pts, [(-0.35, -0.005), (0.35, -0.005), (0.35, 0.005), (-0.35, 0.005)], up=(1, 0, 0))
            ctx.add(fd, LOADER, uv_scale=1.0, smooth=40, patches=0.44, edge=0.7)
    _bx(ctx, "front_frame", (1.0, 2.2, 0.55), (0, -1.6, 1.15), LOADER, bevel=0.03, uv_scale=1.0, patches=0.4, edge=0.7)
    _bx(ctx, "rear_frame", (1.15, 2.6, 0.6), (0, 1.5, 1.2), LOADER, bevel=0.03, uv_scale=1.0, patches=0.4, edge=0.7)
    _cy(ctx, "pivot", 0.22, 0.6, (0, -0.25, 1.2), "wild_cast_iron_rust", segs=14)
    # Engine hood and counterweight behind the cab.
    hood = K.box("hood", (1.4, 1.8, 0.95), center=(0, 2.0, 1.95), bevel=0.06, bevel_segs=2, cuts=(2, 3, 1))
    ctx.add(hood, LOADER, uv_scale=1.0, smooth=35, patches=0.4, edge=0.7)
    for sx in (-1, 1):
        for k in range(6):
            _bx(ctx, f"louvre{sx}{k}", (0.02, 0.05, 0.45), (sx * 0.71, 1.5 + k * 0.12, 1.95), LOADER, bevel=0.0, patches=0.3)
    _bx(ctx, "counterweight", (1.9, 0.5, 0.9), (0, 3.35, 1.3), LOADER, bevel=0.08, uv_scale=1.0, patches=0.5, edge=0.8)
    W.rod(ctx, "exhaust", (0.45, 2.3, 2.4), (0.45, 2.3, 3.3), 0.06, "car_rust", segs=10)
    _cy(ctx, "air_cleaner", 0.13, 0.4, (-0.45, 1.6, 2.6), LOADER, segs=14)
    # Cab: ROPS posts, roof, glass.
    dz, cy0, cy1 = 1.5, -0.35, 1.0
    _bx(ctx, "cab_floor", (1.6, cy1 - cy0, 0.06), (0, (cy0 + cy1) / 2, dz), LOADER, bevel=0.01)
    for sx in (-1, 1):
        for y in (cy0, cy1):
            W.bar(ctx, f"rops{sx}{y}", (sx * 0.78, y, dz), (sx * 0.74, y, 3.3), 0.1, 0.1, LOADER, patches=0.39)
    roof = K.box("roof", (1.75, cy1 - cy0 + 0.3, 0.08), center=(0, (cy0 + cy1) / 2, 3.33), bevel=0.02, cuts=(2, 2, 0))
    ctx.add(roof, LOADER, uv_scale=1.0, patches=0.44, edge=0.7, moss=0.4 if worn else 0.1)
    if not worn:
        for k, (size, c) in enumerate((((1.45, 0.01, 1.4), (0, cy0 - 0.02, dz + 0.95)), ((0.01, 1.2, 1.3), (-0.76, (cy0 + cy1) / 2, dz + 1.0)),
                                       ((0.01, 1.2, 1.3), (0.76, (cy0 + cy1) / 2, dz + 1.0)))):
            g = K.box(f"glass{k}", size, center=c)
            ctx.add(g, GLASS, uv_scale=1.0, wear=0.3, ao=False)
    _bx(ctx, "seat", (0.5, 0.48, 0.12), (0, 0.45, dz + 0.42), "car_upholstery", bevel=0.04)
    _bx(ctx, "seat_back", (0.5, 0.1, 0.45), (0, 0.7, dz + 0.7), "car_upholstery", bevel=0.04)
    W.rod(ctx, "column", (0, -0.2, dz), (0, 0.0, dz + 0.8), 0.04, CHASSIS, segs=8)
    wheel = W.ring_obj("wheel", 0.17, 0.2, 0.03, segs=18)
    K.place(wheel, rot=(-30, 0, 0))
    K.place(wheel, (0, 0.02, dz + 0.83))
    ctx.add(wheel, "plastic_black", uv_scale=2.0, smooth=40)
    # Lift arms from the front frame to the fork carriage, the tilt ram, the tines and the top clamp.
    fy = -3.55
    for sx in (-1, 1):
        W.bar(ctx, f"arm{sx}", (sx * 0.62, -0.7, 1.7), (sx * 0.62, fy + 0.25, 0.45), 0.16, 0.22, LOADER, patches=0.45)
        W.rod(ctx, f"lift_ram{sx}", (sx * 0.45, -0.9, 1.05), (sx * 0.45, -2.3, 1.2), 0.06, LOADER, segs=10)
        W.rod(ctx, f"lift_rod{sx}", (sx * 0.45, -1.9, 1.15), (sx * 0.45, -2.3, 1.2), 0.035, CHROME, segs=8)
    _bx(ctx, "carriage", (1.9, 0.15, 0.9), (0, fy + 0.15, 0.55), LOADER, bevel=0.02, patches=0.5)
    tine_mat = "wild_saw_steel_rust" if worn else CHASSIS
    for sx in (-1, 1):
        tine = K.box(f"tine{sx}", (0.14, 0.55, 0.1), center=(sx * 0.7, fy - 0.2, 0.05), bevel=0.01)
        ctx.add(tine, tine_mat, uv_scale=1.0, patches=0.6)
        clamp = K.tube(f"clamp{sx}", [(sx * 0.55, fy + 0.15, 0.95), (sx * 0.55, fy - 0.1, 1.25), (sx * 0.55, fy - 0.45, 1.15),
                                      (sx * 0.55, fy - 0.5, 0.75)], 0.07, segs=8)
        ctx.add(clamp, LOADER, uv_scale=1.0, smooth=40, patches=0.5)
    W.rod(ctx, "tilt_ram", (0, -0.8, 2.0), (0, fy + 0.3, 1.0), 0.07, LOADER, segs=10)


# ============================================================================================
# The shop
# ============================================================================================

def w4_depot_welding_cart(ctx: K.Ctx) -> None:
    """A two-wheeled welding cart: a steel deck and handle frame, an oxygen bottle and an acetylene bottle chained
    in at the back with regulators and gauges, the twin hose coiled on the handle with the torch, and a stick
    welder on the front of the deck with its leads hung over it. Worn: the oxygen cap off and the hoses down."""
    D = 0.86
    _bx(ctx, "deck", (0.56, D, 0.04), (0, 0, 0.17), "road_paint_red", bevel=0.005, patches=0.6)
    for sx in (-1, 1):
        W.rod(ctx, f"upright{sx}", (sx * 0.26, D / 2 - 0.08, 0.17), (sx * 0.26, D / 2 - 0.02, 1.42), 0.016, "road_paint_red", segs=8)
        _wheel_small = K.cyl(f"wheel{sx}", 0.15, 0.06, segs=14, axis="X", center=(sx * 0.31, D / 2 - 0.12, 0.15))
        ctx.add(_wheel_small, "road_rubber", uv_scale=2.0, smooth=40)
        W.rod(ctx, f"leg{sx}", (sx * 0.24, -D / 2 + 0.06, 0.17), (sx * 0.24, -D / 2 + 0.06, 0.0), 0.014, "road_paint_red", segs=6)
    W.rod(ctx, "axle", (-0.31, D / 2 - 0.12, 0.15), (0.31, D / 2 - 0.12, 0.15), 0.012, STEEL, segs=6)
    W.rod(ctx, "handle", (-0.26, D / 2 - 0.02, 1.42), (0.26, D / 2 - 0.02, 1.42), 0.016, "road_paint_red", segs=8)
    W.rod(ctx, "bottle_band", (-0.26, D / 2 - 0.05, 0.9), (0.26, D / 2 - 0.05, 0.9), 0.01, STEEL, segs=6)
    # Bottles.
    for k, (x, rad, h, mat) in enumerate(((-0.12, 0.1, 1.15, "road_paint_green"), (0.13, 0.13, 0.95, "road_paint_black"))):
        prof = [(0.0, 0.0), (rad, 0.0), (rad, h - rad * 0.8), (rad * 0.6, h - rad * 0.2), (0.03, h), (0.0, h)]
        b = K.lathe(f"bottle{k}", prof, segs=16)
        K.place(b, (x, D / 2 - 0.2, 0.19))
        ctx.add(b, mat, uv="cyl", uv_axis=2, uv_scale=1.5, smooth=40, patches=0.5)
        top = 0.19 + h
        _bx(ctx, f"regulator{k}", (0.06, 0.06, 0.08), (x, D / 2 - 0.2, top + 0.05), "road_brass", bevel=0.005)
        for j in (-1, 1):
            g = K.cyl(f"gauge{k}{j}", 0.03, 0.02, segs=12, axis="Y", center=(x + j * 0.05, D / 2 - 0.24, top + 0.08))
            ctx.add(g, CHROME, uv_scale=4.0, smooth=40)
    # Welder on the front of the deck, its leads.
    _bx(ctx, "welder", (0.42, 0.34, 0.32), (0, -D / 2 + 0.22, 0.35), "road_paint_blue", bevel=0.015, patches=0.5)
    _bx(ctx, "welder_face", (0.3, 0.01, 0.18), (0, -D / 2 + 0.045, 0.37), "road_paint_black", bevel=0.0, ao=False)
    _cy(ctx, "knob", 0.03, 0.03, (0.1, -D / 2 + 0.035, 0.42), "plastic_black", axis="Y", segs=10)
    lead = [(-0.15, -D / 2 + 0.05, 0.3), (-0.22, -D / 2 + 0.0, 0.35), (-0.25, -D / 2 + 0.1, 0.56), (-0.1, -D / 2 + 0.2, 0.53),
            (0.05, -D / 2 + 0.3, 0.52)]
    ctx.add(K.tube("lead", lead, 0.012, segs=6), "road_rubber", uv_scale=3.0, smooth=50)
    # Twin hose coil on the handle (or trailing down).
    if not ctx.worn:
        for j in range(3):
            ring = W.ring_obj(f"coil{j}", 0.15, 0.165, 0.02, segs=16)
            K.place(ring, rot=(90, 0, 0))
            K.place(ring, (0.0, D / 2 + 0.02, 1.28 - j * 0.015))
            ctx.add(ring, "road_paint_red" if j % 2 else "road_paint_green", uv_scale=3.0, smooth=40)
    else:
        hose = [(0.0, D / 2 - 0.2, 1.35), (0.15, D / 2 - 0.05, 1.2), (0.25, D / 2 - 0.04, 0.6), (0.2, D / 2 - 0.06, 0.02)]
        ctx.add(K.tube("hose_down", hose, 0.012, segs=6), "road_paint_red", uv_scale=3.0, smooth=50)


def _filter(ctx, name, x, y, z, rad, h, mat):
    return _cy(ctx, name, rad, h, (x, y, z + h / 2), mat, segs=10, uv_scale=3.0, patches=0.4)


def w4_depot_parts_shelf(ctx: K.Ctx) -> None:
    """Heavy steel shelving full of truck parts: angle uprights, five shelves of boxed filters, spin-on oil filters,
    fan belts on hooks under the top shelf, brake shoes and a bin of bolts. Worn: half picked over. Destroyed: the
    shelves stripped, a few boxes on the floor, one shelf dropped at a corner."""
    r = ctx.rnd("parts")
    dr = ctx.drnd("parts")
    Wd, D, H = 1.8, 0.56, 2.15
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.section(ctx, f"upright{sx}{sy}", (sx * (Wd / 2 - 0.02), sy * (D / 2 - 0.02), 0.0), (sx * (Wd / 2 - 0.02), sy * (D / 2 - 0.02), H),
                      W.prof_l(0.04, 0.004), SHELF, up=(sx, sy, 0))
    levels = [0.08, 0.5, 0.92, 1.34, 1.76, 2.12]
    keep = 1.0 if ctx.clean else (0.5 if not ctx.destroyed else 0.1)
    for li, z in enumerate(levels):
        sh = K.box(f"shelf{li}", (Wd, D, 0.025), center=(0, 0, z))
        if ctx.destroyed and li == 3:
            K.place(sh, (-Wd / 2, 0, -z))
            K.place(sh, rot=(0, -9, 0))
            K.place(sh, (Wd / 2, 0, z))
        ctx.add(sh, SHELF, uv_scale=2.0, patches=0.6)
        if li == len(levels) - 1:
            continue
        x = -Wd / 2 + 0.08
        while x < Wd / 2 - 0.15:
            kind = r.random()
            if kind < 0.45:
                w = r.uniform(0.18, 0.32)
                h = r.uniform(0.18, 0.3)
                if dr.random() < keep:
                    bx = K.box(f"box{li}_{x:.2f}", (w, r.uniform(0.25, 0.4), h), center=(x + w / 2, r.uniform(-0.05, 0.05), z + 0.012 + h / 2), bevel=0.004)
                    ctx.add(bx, "road_cardboard", uv_scale=2.0, patches=0.5)
                x += w + 0.03
            elif kind < 0.8:
                n = r.randint(2, 4)
                mat = r.choice(("road_paint_blue", "road_paint_orange", "road_paint_white", "road_paint_black"))
                for j in range(n):
                    if dr.random() < keep:
                        _filter(ctx, f"filter{li}_{x:.2f}_{j}", x + 0.06 + j * 0.12, r.uniform(-0.1, 0.1), z + 0.012, 0.055, r.uniform(0.14, 0.24), mat)
                x += n * 0.12 + 0.04
            else:
                if dr.random() < keep:
                    for j in range(2):
                        shoe = W.ring_obj(f"shoe{li}_{x:.2f}_{j}", 0.18, 0.21, 0.12, segs=10)
                        K.place(shoe, rot=(90, 0, 0))
                        K.cut_plane(shoe, Vector((0, 0, 0)), Vector((0, 0, -1)), keep="below", fill=False)
                        K.place(shoe, (x + 0.2, -0.12 + j * 0.18, z + 0.03))
                        ctx.add(shoe, "road_steel", uv_scale=2.0, smooth=40, patches=0.6)
                x += 0.45
    # Fan belts on hooks under the top shelf.
    if not ctx.destroyed:
        for k in range(5 if ctx.clean else 2):
            x = -0.7 + k * 0.32
            W.rod(ctx, f"hook{k}", (x, -D / 2 + 0.04, 2.08), (x, -D / 2 - 0.04, 2.02), 0.006, STEEL, segs=4)
            belt = K.tube(f"belt{k}", [(x - 0.06, -D / 2 - 0.04, 2.02), (x - 0.08, -D / 2 - 0.05, 1.85), (x, -D / 2 - 0.05, 1.82),
                                       (x + 0.08, -D / 2 - 0.05, 1.85), (x + 0.06, -D / 2 - 0.04, 2.02)], 0.008, segs=5)
            ctx.add(belt, "plastic_black", uv_scale=3.0, smooth=40)
    if ctx.worn:
        for k in range(3 if ctx.destroyed else 1):
            w = dr.uniform(0.2, 0.32)
            bx = K.box(f"floorbox{k}", (w, 0.3, 0.2), center=(dr.uniform(-0.6, 0.6), -D / 2 - 0.05, 0.1), bevel=0.004)
            K.place(bx, rot=(0, 0, dr.uniform(-30, 30)))
            ctx.add(bx, "road_cardboard", uv_scale=2.0, patches=0.6)


def w4_depot_dispatch_radio(ctx: K.Ctx) -> None:
    """The dispatcher's console: a grey steel desk with a drawer pedestal, a riser shelf at the back with the base
    station radio, its power supply and a gang charger of handheld radios, a desk microphone, a goose-neck lamp, the
    channel list taped to the riser, a clipboard of load sheets and a coffee mug. Worn: papers everywhere, the mug
    knocked over, one handheld gone from the charger."""
    Wd, D, top = 1.6, 0.76, 0.76
    _bx(ctx, "top", (Wd, D, 0.035), (0, 0, top - 0.017), "steel_cabinet_beige", bevel=0.006, patches=0.5)
    _bx(ctx, "pedestal", (0.42, D - 0.06, top - 0.04), (Wd / 2 - 0.23, 0.0, (top - 0.04) / 2), "steel_cabinet_beige", bevel=0.006, patches=0.5)
    for k in range(3):
        _bx(ctx, f"drawer{k}", (0.38, 0.015, 0.2), (Wd / 2 - 0.23, -D / 2 + 0.02, 0.13 + k * 0.22), "steel_cabinet_beige", bevel=0.004)
        _bx(ctx, f"pull{k}", (0.1, 0.02, 0.015), (Wd / 2 - 0.23, -D / 2 + 0.005, 0.18 + k * 0.22), CHROME, bevel=0.0)
    _bx(ctx, "leg_panel", (0.03, D - 0.06, top - 0.04), (-Wd / 2 + 0.03, 0.0, (top - 0.04) / 2), "steel_cabinet_beige", bevel=0.004)
    _bx(ctx, "modesty", (Wd - 0.5, 0.02, 0.4), (-0.2, D / 2 - 0.05, 0.5), "steel_cabinet_beige", bevel=0.0)
    # Riser shelf at the back with the radio gear.
    _bx(ctx, "riser", (Wd - 0.1, 0.3, 0.02), (0, D / 2 - 0.17, top + 0.3), "steel_cabinet_beige", bevel=0.004)
    for sx in (-1, 1):
        _bx(ctx, f"riser_leg{sx}", (0.02, 0.3, 0.3), (sx * (Wd / 2 - 0.07), D / 2 - 0.17, top + 0.15), "steel_cabinet_beige", bevel=0.0)
    _bx(ctx, "base_station", (0.42, 0.26, 0.13), (-0.3, D / 2 - 0.17, top + 0.38), "plastic_black", bevel=0.01)
    _bx(ctx, "display", (0.14, 0.005, 0.04), (-0.38, D / 2 - 0.30, top + 0.4), "lab_glow_green" if not ctx.worn else "road_steel_dark", bevel=0.0, ao=False)
    for k in range(3):
        _cy(ctx, f"rknob{k}", 0.015, 0.02, (-0.2 + k * 0.05, D / 2 - 0.31, top + 0.37), CHROME, axis="Y", segs=8)
    _bx(ctx, "psu", (0.3, 0.24, 0.12), (-0.3, D / 2 - 0.17, top + 0.1), "road_paint_grey", bevel=0.008)
    _bx(ctx, "charger", (0.4, 0.14, 0.06), (0.3, D / 2 - 0.15, top + 0.34), "plastic_black", bevel=0.006)
    for k in range(4 if ctx.clean else 3):
        _bx(ctx, f"handheld{k}", (0.06, 0.04, 0.16), (0.16 + k * 0.09, D / 2 - 0.15, top + 0.44), "plastic_black", bevel=0.006)
        W.rod(ctx, f"aerial{k}", (0.16 + k * 0.09, D / 2 - 0.15, top + 0.52), (0.16 + k * 0.09, D / 2 - 0.15, top + 0.62), 0.006, "plastic_black", segs=5)
    _bx(ctx, "channel_list", (0.3, 0.003, 0.18), (0.25, D / 2 - 0.32, top + 0.2), "item_paper_ledger", bevel=0.0, ao=False)
    # Desk microphone, lamp, clipboard, mug.
    _cy(ctx, "mic_base", 0.07, 0.03, (-0.15, -0.05, top + 0.015), "plastic_black", segs=14)
    W.rod(ctx, "mic_stem", (-0.15, -0.05, top + 0.03), (-0.15, -0.02, top + 0.22), 0.008, CHROME, segs=6)
    _cy(ctx, "mic_head", 0.03, 0.09, (-0.15, -0.03, top + 0.24), CHROME, axis="Y", segs=10)
    W.rod(ctx, "mic_cord", (-0.15, -0.05, top + 0.02), (-0.3, D / 2 - 0.3, top + 0.02), 0.005, "plastic_black", segs=4)
    _cy(ctx, "lamp_base", 0.08, 0.03, (0.62, 0.15, top + 0.015), "road_paint_green", segs=14)
    lamp = K.tube("lamp_neck", [(0.62, 0.15, top + 0.03), (0.6, 0.1, top + 0.25), (0.56, 0.0, top + 0.32)], 0.01, segs=6)
    ctx.add(lamp, CHROME, uv_scale=3.0, smooth=50)
    shade = K.cyl("lamp_shade", 0.08, 0.1, segs=14, r_top=0.035, center=(0.55, 0.05, top + 0.3))
    ctx.add(shade, "road_paint_green", uv_scale=2.0, smooth=40)
    clip = K.box("clipboard", (0.23, 0.32, 0.01), center=(0.15, -0.12, top + 0.005))
    K.place(clip, rot=(0, 0, 8))
    ctx.add(clip, "road_plywood", uv_scale=2.0, patches=0.4)
    sheet = K.box("load_sheets", (0.21, 0.28, 0.004), center=(0.15, -0.13, top + 0.012))
    K.place(sheet, rot=(0, 0, 8))
    ctx.add(sheet, "item_paper_ledger", uv_scale=1.0, ao=False)
    mug = K.lathe("mug", [(0.0, 0.0), (0.04, 0.0), (0.042, 0.1), (0.036, 0.1), (0.034, 0.01), (0.0, 0.01)], segs=12)
    if ctx.worn:
        K.place(mug, rot=(90, 0, 30))
        K.place(mug, (0.42, -0.2, top + 0.04))
    else:
        K.place(mug, (0.42, -0.2, top))
    ctx.add(mug, "ceramic_white", uv_scale=3.0, smooth=40)
    if ctx.worn:
        dr = ctx.drnd("papers")
        for k in range(5):
            p = K.box(f"paper{k}", (0.21, 0.28, 0.002), center=(dr.uniform(-0.6, 0.3), dr.uniform(-0.3, 0.2), top + 0.006 + k * 0.002))
            K.place(p, rot=(0, 0, dr.uniform(-40, 40)))
            ctx.add(p, "item_paper_ledger" if k % 2 else "road_paper_white", uv_scale=1.0, ao=False)
    _centre_depth(ctx)


def w4_depot_pit_planks(ctx: K.Ctx) -> None:
    """Thick oak planks laid across the inspection pit side by side, oily and boot-marked. Worn: the near end's planks
    dragged back and stacked askew on the others, leaving the pit open there."""
    r = ctx.rnd("planks")
    L, n = 2.0, 26
    pw = 7.0 / n
    for k in range(n):
        y = -3.5 + (k + 0.5) * pw
        z = 0.03
        rot = (0, 0, r.uniform(-1.5, 1.5))
        if ctx.worn and k < 3:
            # Dragged back onto the planks behind them.
            y = -3.5 + (k + 4.5) * pw + r.uniform(-0.05, 0.05)
            z = 0.09 + k * 0.0
            rot = (r.uniform(-2, 2), 0, r.uniform(-12, 12))
        pl = P.plank(f"plank{k}", L * r.uniform(0.97, 1.03), pw * 0.94, 0.055)
        K.place(pl, rot=rot)
        K.place(pl, (r.uniform(-0.04, 0.04), y, z))
        ctx.add(pl, "wild_lumber_weathered", uv_scale=1.0, patches=0.5, low=0.3)


def w4_depot_dispatch_board(ctx: K.Ctx) -> None:
    """The dispatch board on the office wall: an aluminium-framed whiteboard ruled into six truck rows, a coloured
    magnet on each, the last loads in marker and trucks 4 and 6 ringed twice in red, a marker tray under it."""
    Wd, H, T = 1.6, 1.0, 0.03
    _bx(ctx, "frame", (Wd, T, H), (0, -T / 2, H / 2), "road_alu", bevel=0.008, patches=0.3)
    _bx(ctx, "face", (Wd - 0.06, 0.004, H - 0.06), (0, -T - 0.002, H / 2), "road_paint_white", bevel=0.0, patches=0.4, ao=False)
    for k in range(7):
        z = 0.08 + k * (H - 0.16) / 6
        _bx(ctx, f"rule{k}", (Wd - 0.12, 0.002, 0.008), (0, -T - 0.005, z), "road_paint_black", bevel=0.0, ao=False)
    _bx(ctx, "col_rule", (0.008, 0.002, H - 0.16), (-0.45, -T - 0.005, H / 2), "road_paint_black", bevel=0.0, ao=False)
    r = ctx.rnd("board")
    mats = ("plastic_red", "plastic_blue", "plastic_yellow", "plastic_white", "road_paint_green", "plastic_orange")
    for k in range(6):
        z = 0.08 + (k + 0.5) * (H - 0.16) / 6
        _cy(ctx, f"magnet{k}", 0.025, 0.012, (-0.6 + r.uniform(0, 0.08), -T - 0.01, z), mats[k], axis="Y", segs=10)
        for j in range(r.randint(2, 5)):
            _bx(ctx, f"scrawl{k}{j}", (r.uniform(0.05, 0.14), 0.002, 0.012), (-0.35 + j * 0.16, -T - 0.005, z + r.uniform(-0.02, 0.02)),
                "road_paint_black" if j % 3 else "road_paint_blue", bevel=0.0, ao=False)
        if k in (3, 5):
            for j in range(2):
                ring = W.ring_obj(f"ring{k}{j}", 0.07 + j * 0.012, 0.078 + j * 0.012, 0.003, segs=16)
                K.place(ring, rot=(90, 0, 0), scale=(1.6, 1.0, 1.0))
                K.place(ring, (-0.6, -T - 0.006, z))
                ctx.add(ring, "road_paint_red", uv_scale=4.0, ao=False)
    _bx(ctx, "tray", (0.6, 0.06, 0.02), (0.3, -T - 0.03, 0.0 + 0.01), "road_alu", bevel=0.003)
    for k in range(3 if ctx.clean else 1):
        W.rod(ctx, f"marker{k}", (0.1 + k * 0.12, -T - 0.035, 0.03), (0.22 + k * 0.12, -T - 0.035, 0.03), 0.008, mats[k], segs=6)


def w4_depot_tire_stack(ctx: K.Ctx) -> None:
    """Three heavy log-truck tyres stacked flat, the top one still on its steel rim. Worn: the stack slumped, mud on
    the treads."""
    r = ctx.rnd("tyres")
    ro, w = 0.53, 0.28
    for k in range(3):
        t = P.tyre(f"tyre{k}", ro, ro * 0.58, w, segs=20)
        K.place(t, rot=(0, 90, 0))
        off = (r.uniform(-0.03, 0.03), r.uniform(-0.03, 0.03)) if not ctx.worn else (r.uniform(-0.08, 0.08), r.uniform(-0.08, 0.08))
        K.place(t, (off[0], off[1], w / 2 + k * w))
        ctx.add(t, TYRE, uv_scale=1.5, smooth=40, patches=0.3, low=0.6 if ctx.worn else 0.2, low_h=0.4)
        if k == 2:
            rim = P.steel_rim("rim", ro * 0.6, w * 0.9, segs=16)
            K.place(rim, rot=(0, 90, 0))
            K.place(rim, (off[0], off[1], w / 2 + k * w))
            ctx.add(rim, "road_paint_grey", uv_scale=1.5, smooth=40, patches=0.5)


BUILDERS = {
    "w4_depot_log_truck": w4_depot_log_truck,
    "w4_depot_log_tractor": w4_depot_log_tractor,
    "w4_depot_truck_lift": w4_depot_truck_lift,
    "w4_depot_weighbridge": w4_depot_weighbridge,
    "w4_depot_fuel_pump": w4_depot_fuel_pump,
    "w4_depot_fuel_tank": w4_depot_fuel_tank,
    "w4_depot_fuel_island": w4_depot_fuel_island,
    "w4_depot_log_stack": w4_depot_log_stack,
    "w4_depot_log_pile_low": w4_depot_log_pile_low,
    "w4_depot_loader": w4_depot_loader,
    "w4_depot_welding_cart": w4_depot_welding_cart,
    "w4_depot_parts_shelf": w4_depot_parts_shelf,
    "w4_depot_dispatch_radio": w4_depot_dispatch_radio,
    "w4_depot_pit_planks": w4_depot_pit_planks,
    "w4_depot_dispatch_board": w4_depot_dispatch_board,
    "w4_depot_tire_stack": w4_depot_tire_stack,
}


def build(params: dict, outputs: list[str]) -> None:
    K.run(params, outputs, BUILDERS)
