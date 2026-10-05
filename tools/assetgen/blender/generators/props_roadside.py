"""Route 9 roadside props: Cordon Gas & Garage (forecourt, kiosk, garage), the Timberline Motel and the
Tamsin Valley Clinic. Built with the exterior props kit (lib/props_ext_kit.py: parts -> ctx.add ->
one GLB per condition, vertex AO/wear/variation, collision proxies).

Front faces -Y (Godot +Z), origin bottom centre; wall-mounted props have their origin on the wall
plane (the prop stands off it towards -Y); ceiling props (canopy light) hang down from z = 0.
Lettered faces map rectangles of the generated atlases (textures/gen/roadside.py: road_signs,
road_signs_motel, road_spray) -- ATLAS_GAS / ATLAS_MOTEL below must match that module's GAS / MOTEL.

clean     : abandoned one winter -- grime, sun-fade, light rust, things left where they were.
worn      : heavy rust, dents, broken glass and lenses, panels hanging, stock spilled.
destroyed : smashed, burnt or knocked over (only props that break: pumps, machines, furniture).
"""
from __future__ import annotations

import math

from mathutils import Matrix, Vector

from lib import props_ext_kit as K
from lib import props_ext_parts as P

# --------------------------------------------------------------------------------------------
# Atlases (units of 256 px; textures/gen/roadside.py GAS / MOTEL)
# --------------------------------------------------------------------------------------------

UNIT = 256
ATLAS_PX = 2048
ATLAS_GAS = {
    "gas_brand": (0, 0, 6, 2), "vending": (6, 0, 2, 4), "gas_prices": (0, 2, 4, 2), "pump_face": (4, 2, 2, 2),
    "canopy_band": (0, 4, 8, 1), "pump_vintage": (0, 5, 2, 3), "ice_front": (2, 5, 3, 1), "air_pump": (2, 6, 1, 2),
    "xray_label": (3, 6, 1, 1), "exit_sign": (4, 6, 1, 1), "oil_label": (3, 7, 2, 1), "newspaper": (5, 5, 2, 3),
    "box_labels": (7, 5, 1, 3),
}
ATLAS_MOTEL = {
    "motel_main": (0, 0, 5, 3), "vacancy": (5, 0, 3, 1), "no_box": (5, 1, 1, 1), "weekly": (6, 1, 2, 1),
    "amenities": (5, 2, 3, 1), "office": (0, 3, 2, 1), "laundry": (2, 3, 2, 1), "ice_label": (4, 3, 2, 1),
    "room_numbers": (6, 3, 2, 1), "clinic_sign": (0, 4, 6, 1), "clinic_hours": (6, 4, 2, 2),
    "quarantine": (0, 5, 2, 3), "xray_films": (2, 5, 2, 2), "eye_chart": (4, 5, 1, 2), "rates": (5, 5, 1, 2),
    "dnd": (7, 6, 1, 2), "staff_only": (2, 7, 2, 1), "lobby_strip": (4, 7, 3, 1),
}
GAS = "road_signs"
MOTEL = "road_signs_motel"
SPRAY = "road_spray"


def _rect(table: dict, name: str, sub=None, inset: float = 2.0) -> tuple[float, float, float, float]:
    """Blender UV rect (u0, v0, u1, v1; v up) of an atlas cell, or of a sub-rectangle given as
    fractions (fx0, fy0, fx1, fy1) of the cell with y measured from the top of the image."""
    x, y, w, h = [v * UNIT for v in table[name]]
    if sub:
        fx0, fy0, fx1, fy1 = sub
        x, y, w, h = x + fx0 * w, y + fy0 * h, (fx1 - fx0) * w, (fy1 - fy0) * h
    x0, y0, x1, y1 = x + inset, y + inset, x + w - inset, y + h - inset
    return (x0 / ATLAS_PX, 1.0 - y1 / ATLAS_PX, x1 / ATLAS_PX, 1.0 - y0 / ATLAS_PX)


def _spray_rect(i: int) -> tuple[float, float, float, float]:
    """road_spray: 2 x 4 sheets of 512 x 256 px in a 1024 px image, row-major from the top-left."""
    col, row = i % 2, i // 2
    x0, y0 = col * 512 + 3, row * 256 + 3
    x1, y1 = x0 + 506, y0 + 250
    return (x0 / 1024, 1.0 - y1 / 1024, x1 / 1024, 1.0 - y0 / 1024)


def _room_number_rect(n: int) -> tuple[float, float, float, float]:
    """Brass room-number plate 1..8 (4 x 2 plates of 128 px in the room_numbers cell)."""
    i = n - 1
    return _rect(ATLAS_MOTEL, "room_numbers", ((i % 4) / 4, (i // 4) / 2, (i % 4 + 1) / 4, (i // 4 + 1) / 2), inset=6.0)


# --------------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------------

def _face(ctx, name, w, h, rect, mat, loc, rot_z=0.0, *, nu=2, nv=2, wear=0.6, patches=0.35, edge=0.6, ao=True,
          rot=None):
    """Flat lettered face (w x h) facing -Y, its atlas rect mapped edge to edge; rot_z 180 faces +Y."""
    o = K.quad_sheet(name, (-w / 2, 0, -h / 2), (w / 2, 0, -h / 2), (w / 2, 0, h / 2), (-w / 2, 0, h / 2), nu, nv)
    K.uv_planar(o, 1, rect=rect)
    K.place(o, (0, 0, 0), rot if rot is not None else (0, 0, rot_z))
    K.place(o, loc)
    return ctx.add(o, mat, uv=None, wear=wear, patches=patches, edge=edge, ao=ao)


def _bezier(p0, p1, p2, p3, n: int) -> list[Vector]:
    p0, p1, p2, p3 = (Vector(p) for p in (p0, p1, p2, p3))
    out = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        out.append(p0 * a + p1 * b + p2 * c + p3 * d)
    return out


def _bolts(ctx, pts, normal: str = "-y", r: float = 0.009, h: float = 0.006, mat: str = "road_chrome", segs: int = 6):
    """Hex bolt heads standing off a surface along `normal` ('x', '-x', 'y', '-y', 'z', '-z')."""
    axis = normal[-1].upper()
    sign = -1.0 if normal.startswith("-") else 1.0
    off = {"X": Vector((sign * h / 2, 0, 0)), "Y": Vector((0, sign * h / 2, 0)), "Z": Vector((0, 0, sign * h / 2))}[axis]
    parts = [K.cyl(ctx.uid("bolt"), r, h, segs=segs, axis=axis, center=Vector(p) + off) for p in pts]
    if not parts:
        return None
    o = K.merge_parts(parts, ctx.uid("bolts"))
    return ctx.add(o, mat, uv_scale=2.0, wear=0.9, patches=0.3)


def _caster(ctx, x: float, y: float, top: float, r: float = 0.04, *, wheel_mat: str = "road_plastic_black",
            mat: str = "road_steel", brake: bool = False):
    """Swivel caster under a plate at height `top`: plate, swivel, fork, wheel (axle along X)."""
    plate = K.box(ctx.uid("cplate"), (0.07, 0.07, 0.008), center=(x, y, top - 0.004))
    sw = K.cyl(ctx.uid("cswivel"), 0.022, 0.014, segs=10, center=(x, y, top - 0.015))
    fz = (top - 0.022 + r) / 2
    fh = top - 0.022 - r + 0.012
    forks = [K.box(ctx.uid("cfork"), (0.005, 0.04, fh), center=(x + s * 0.019, y + 0.012, fz + 0.006)) for s in (-1, 1)]
    wheel = K.cyl(ctx.uid("cwheel"), r, 0.026, segs=12, axis="X", center=(x, y + 0.016, r))
    hub = K.cyl(ctx.uid("chub"), r * 0.45, 0.03, segs=8, axis="X", center=(x, y + 0.016, r))
    for o in [plate, sw] + forks:
        ctx.add(o, mat, uv_scale=2.0, wear=0.8, patches=0.4)
    ctx.add(wheel, wheel_mat, uv="cyl", uv_axis=0, uv_scale=2.0, smooth=40, wear=0.5, patches=0.2)
    ctx.add(hub, "road_chrome", uv_scale=2.0, wear=0.6)
    if brake:
        lev = K.box(ctx.uid("cbrake"), (0.02, 0.05, 0.008), center=(x, y - 0.03, r * 2 + 0.006), bevel=0.002)
        K.place(lev, rot=(20, 0, 0))
        ctx.add(lev, "road_plastic_red", uv_scale=2.0, wear=0.6)


def _padlock(ctx, loc, rot_z: float = 0.0, s: float = 1.0, open_: bool = False):
    """Brass-bodied padlock hanging from a hasp (body + shackle)."""
    body = K.box(ctx.uid("plbody"), (0.04 * s, 0.018 * s, 0.035 * s), center=(0, 0, -0.03 * s), bevel=0.004 * s)
    pts = [(-0.012 * s, 0, -0.014 * s), (-0.012 * s, 0, 0.004 * s), (-0.008 * s, 0, 0.012 * s), (0.0, 0, 0.015 * s),
           (0.008 * s, 0, 0.012 * s), (0.012 * s, 0, 0.004 * s), (0.012 * s, 0, -0.014 * s + (0.012 * s if open_ else 0))]
    sh = K.tube(ctx.uid("plshackle"), pts, 0.0032 * s, segs=6)
    for o in (body, sh):
        K.place(o, rot=(0, 0, rot_z))
        K.place(o, loc)
    ctx.add(body, "road_brass", uv_scale=3.0, smooth=35, wear=0.7)
    ctx.add(sh, "road_chrome", uv_scale=3.0, smooth=40, wear=0.6)


def _louvres(ctx, x0, x1, z0, z1, y, n: int, mat: str, *, depth: float = 0.012, slope: float = 35.0, face: str = "-y"):
    """Row of slanted louvre blades in a vent opening on a face at plane y (pointing -Y or +Y)."""
    sign = -1.0 if face == "-y" else 1.0
    dz = (z1 - z0) / n
    for k in range(n):
        b = K.box(ctx.uid("louvre"), (x1 - x0, depth, dz * 0.9), center=(0, 0, 0))
        K.place(b, rot=(slope * sign, 0, 0))
        K.place(b, ((x0 + x1) / 2, y + sign * depth * 0.2, z0 + dz * (k + 0.5)))
        ctx.add(b, mat, uv_scale=2.0, wear=0.7, patches=0.5)
    back = K.box(ctx.uid("louvreback"), (x1 - x0, 0.004, z1 - z0), center=((x0 + x1) / 2, y - sign * 0.012, (z0 + z1) / 2))
    ctx.add(back, "road_plastic_black", uv_scale=2.0, wear=0.2, patches=0.0, ao=True)


def _tire(name: str, ro: float = 0.32, rb: float = 0.19, w: float = 0.2, segs: int = 14, grooves: bool = True) -> object:
    """Closed tyre carcass (tread, rounded shoulders, bulging sidewalls, bead, inner liner) around Z,
    centred at the origin -- see-through bead openings are what made loose tyres look hollow.
    `grooves` cuts two circumferential tread grooves into the profile; racks and stacks drop them
    and spend the triangles on more segments instead (a 12-gon tyre reads as a plate)."""
    side = ro - rb
    hw = w / 2
    if grooves:
        tread = [(ro, -hw * 0.66), (ro, -hw * 0.3), (ro - 0.009, -hw * 0.22), (ro, -hw * 0.12), (ro, hw * 0.12),
                 (ro - 0.009, hw * 0.22), (ro, hw * 0.3), (ro, hw * 0.66)]
    else:
        tread = [(ro - 0.004, -hw * 0.7), (ro, -hw * 0.45), (ro, hw * 0.45), (ro - 0.004, hw * 0.7)]
    prof = ([(rb, -hw * 0.5), (rb + 0.012, -hw * 0.94), (rb + side * 0.55, -hw), (ro - 0.03, -hw * 0.92)] + tread
            + [(ro - 0.03, hw * 0.92), (rb + side * 0.55, hw), (rb + 0.012, hw * 0.94), (rb, hw * 0.5), (rb + 0.03, 0.0)])
    return K.lathe(name, prof, segs=segs, close_profile=True)


def _hose(ctx, name, pts, r: float = 0.016, mat: str = "road_rubber", segs: int = 8):
    o = K.tube(name, pts, r, segs=segs)
    return ctx.add(o, mat, uv="cyl", uv_axis=2, uv_scale=2.0, smooth=50, wear=0.4, patches=0.2, edge=0.2)


def _nozzle_parts(ctx, grip: str) -> list:
    """Fuel nozzle in its own frame: hose inlet at the origin, body along +X, spout pointing down
    and forward at the +X end (tip ~ (0.36, 0, -0.1)). Returns [(obj, material)]."""
    swivel = K.cyl(ctx.uid("nzswivel"), 0.017, 0.05, segs=10, axis="X", center=(0.025, 0, 0))
    body = K.box(ctx.uid("nzbody"), (0.16, 0.048, 0.07), center=(0.13, 0, 0.0), bevel=0.012, bevel_segs=2)
    cover = K.box(ctx.uid("nzgrip"), (0.11, 0.056, 0.04), center=(0.12, 0, 0.03), bevel=0.012, bevel_segs=2)
    lever = K.box(ctx.uid("nzlever"), (0.13, 0.014, 0.012), center=(0.12, 0, -0.05), bevel=0.003)
    K.place(lever, rot=(0, 6, 0))
    guard = K.tube(ctx.uid("nzguard"), [(0.055, 0, -0.03), (0.06, 0, -0.075), (0.085, 0, -0.085), (0.18, 0, -0.085),
                                        (0.2, 0, -0.07), (0.205, 0, -0.03)], 0.006, segs=6)
    spout = K.tube(ctx.uid("nzspout"), [(0.2, 0, 0.0), (0.25, 0, -0.006), (0.3, 0, -0.035), (0.34, 0, -0.07),
                                        (0.365, 0, -0.105)], 0.0105, segs=8)
    boot = K.cyl(ctx.uid("nzboot"), 0.02, 0.045, segs=10, axis="X", center=(0.235, 0, -0.004))
    return [(swivel, "road_chrome"), (body, "road_alu"), (cover, grip), (lever, "road_alu"), (guard, "road_alu"),
            (spout, "road_chrome"), (boot, "road_rubber")]


def _add_nozzle(ctx, grip: str, loc, rot) -> None:
    for o, m in _nozzle_parts(ctx, grip):
        K.place(o, rot=rot)
        K.place(o, loc)
        ctx.add(o, m, uv_scale=3.0, smooth=35, wear=0.7, patches=0.3)


def _boot_nozzle(ctx, grip: str, boot_top: Vector, lean: float) -> tuple[Vector, Vector]:
    """Hangs a nozzle in a dispenser boot: spout down into the boot opening at `boot_top`, handle
    tilted 30 deg out from the face (lean -1 = towards -Y, +1 = +Y, 0 = towards -X for side hooks).
    Returns (hose inlet position, direction the hose leaves the inlet)."""
    rz = 90.0 if lean < 0 else (-90.0 if lean > 0 else 0.0)
    rot = (0.0, 60.0, rz)
    m = K.rot_matrix(rot)
    tip = m @ Vector((0.365, 0.0, -0.105))
    loc = Vector(boot_top) - tip
    _add_nozzle(ctx, grip, loc, rot)
    din = (m @ Vector((-1.0, 0.0, 0.0))).normalized()
    return loc, din


# ============================================================================================
# Fuel dispensers
# ============================================================================================

def fuel_pump(ctx: K.Ctx) -> None:
    """90s two-sided gasoline dispenser: louvred hydraulic cabinet with a keyed door, electronics
    head with lettered faces (totals / gallons LCDs, grade buttons), brand valance, a hose on each
    side looping from the top outlets down to a nozzle in its boot. Worn: a nozzle pulled out and
    dropped, cracked faces, dents, rust. Destroyed: rammed by a car and burnt -- pushed over,
    cabinet caved in, head face gone, hoses torn."""
    W, D = 1.1, 0.5
    burnt = ctx.destroyed
    paint = "road_burnt" if burnt else "road_paint_white"
    plinth = K.box("plinth", (W + 0.06, D + 0.06, 0.06), center=(0, 0, 0.03), bevel=0.012)
    ctx.add(plinth, "road_steel_dark", uv_scale=1.5, low=1.0, low_h=0.3, patches=0.6)
    cab = K.box("cab", (W, D, 0.88), center=(0, 0, 0.06 + 0.44), bevel=0.014, cuts=(3, 1, 3))
    head = K.box("head", (W - 0.02, D - 0.08, 0.7), center=(0, 0, 0.95 + 0.35), bevel=0.02, cuts=(3, 1, 2))
    valance = K.box("valance", (W + 0.08, D + 0.04, 0.17), center=(0, 0, 1.66 + 0.085), bevel=0.016)
    stripe = K.box("stripe", (W + 0.085, D + 0.045, 0.035), center=(0, 0, 1.70))
    parts_body = [cab, head, valance, stripe]
    side_parts = []
    if ctx.worn:
        dr = ctx.drnd("dents")
        for _ in range(3):
            K.dent(cab, (dr.uniform(-0.5, 0.5), -D / 2, dr.uniform(0.2, 0.8)), dr.uniform(0.12, 0.22), dr.uniform(0.012, 0.03))
    if burnt:
        K.dent(cab, (0.1, -D / 2, 0.45), 0.42, 0.14)
        K.dent(head, (0.25, -D / 2, 1.1), 0.3, 0.06)
    ctx.add(cab, paint, uv_scale=1.0, patches=0.6, low=0.9, low_h=0.45)
    ctx.add(head, paint, uv_scale=1.0, patches=0.5)
    ctx.add(valance, "road_burnt" if burnt else "road_paint_green", uv_scale=1.0, patches=0.5)
    ctx.add(stripe, "road_burnt" if burnt else "road_paint_cream", uv_scale=1.0, patches=0.4)
    for s in (-1, 1):
        # Cabinet doors (front/back) with louvres, keyed latch and seams.
        y = s * (D / 2 + 0.004)
        door = K.box(ctx.uid("door"), (W - 0.14, 0.008, 0.72), center=(0, y, 0.53), bevel=0.003)
        ctx.add(door, paint, uv_scale=1.0, patches=0.6, low=0.8, low_h=0.4)
        _louvres(ctx, -0.36, 0.36, 0.22, 0.46, y + s * 0.004, 6, paint, face="-y" if s < 0 else "+y")
        key = K.cyl(ctx.uid("key"), 0.012, 0.012, segs=10, axis="Y", center=(0.38, y + s * 0.008, 0.7))
        ctx.add(key, "road_chrome", uv_scale=3.0, wear=0.7)
        _bolts(ctx, [(x, y + s * 0.004, z) for x in (-0.44, 0.44) for z in (0.2, 0.86)], normal="-y" if s < 0 else "y",
               r=0.007)
        # Lettered head faces in chrome bezels.
        hy = s * ((D - 0.08) / 2 + 0.003)
        if not (burnt and s < 0):
            f = _face(ctx, ctx.uid("face"), W - 0.14, 0.6, _rect(ATLAS_GAS, "pump_face"), "road_burnt" if burnt else GAS,
                      (0, hy, 1.31), 0.0 if s < 0 else 180.0, nu=6, nv=6, wear=0.5)
            if ctx.worn and s < 0:
                K.jagged_hole(f, (0.18, hy, 1.42), 0.11, ctx.drnd("crack").randint(0, 999), axis=1)
        else:
            guts = K.box(ctx.uid("guts"), (W - 0.2, 0.05, 0.55), center=(0, hy * 0.6, 1.3))
            ctx.add(guts, "road_pcb", uv_scale=2.0, patches=0.0)
            for k in range(6):
                wire = K.tube(ctx.uid("wire"), [(-0.3 + k * 0.12, hy, 1.5), (-0.32 + k * 0.13, hy - 0.08, 1.2 - k * 0.02),
                                               (-0.35 + k * 0.14, hy - 0.12, 0.98)], 0.004, segs=4)
                ctx.add(wire, ["road_plastic_red", "road_plastic_black", "road_plastic_yellow"][k % 3], uv_scale=2.0)
        for z in (1.0, 1.62):
            bz = K.box(ctx.uid("bezel"), (W - 0.1, 0.012, 0.025), center=(0, hy + s * 0.004, z), bevel=0.003)
            ctx.add(bz, "road_chrome", uv_scale=2.0, wear=0.6)
        # Grade buttons on a sloped sill under the face.
        sill = K.box(ctx.uid("sill"), (W - 0.16, 0.07, 0.035), center=(0, hy + s * 0.03, 0.985), bevel=0.006)
        K.place(sill, (0, -hy - s * 0.03, -0.985))
        K.place(sill, rot=(s * -25, 0, 0))
        K.place(sill, (0, hy + s * 0.03, 0.985))
        ctx.add(sill, "road_plastic_black", uv_scale=2.0, wear=0.4)
        for k, col in enumerate(("road_plastic_yellow", "road_plastic_red", "road_plastic_green")):
            if burnt:
                break
            b = K.box(ctx.uid("btn"), (0.11, 0.03, 0.03), center=(-0.24 + k * 0.24, hy + s * 0.05, 1.0), bevel=0.006)
            ctx.add(b, col, uv_scale=2.0, wear=0.5)
        # Nozzle boot on the face near the right-hand edge (as seen from that side).
        side = -s  # +X on the front face, -X on the back face
        bx = side * 0.43
        by = s * ((D - 0.08) / 2 + 0.045)
        boot = K.box(ctx.uid("boot"), (0.1, 0.09, 0.15), center=(bx, by, 1.07), bevel=0.012)
        ctx.add(boot, "road_steel_dark", uv_scale=2.0, wear=0.6)
        outlet = Vector((side * 0.47, s * 0.12, 1.66))
        stub = K.cyl(ctx.uid("outlet"), 0.03, 0.07, segs=10, center=outlet + Vector((0, 0, -0.025)))
        ctx.add(stub, "road_chrome", uv_scale=2.0, wear=0.6)
        if burnt:
            torn = _bezier(outlet, outlet + Vector((side * 0.1, s * 0.08, -0.3)), outlet + Vector((side * 0.2, s * 0.25, -0.6)),
                           outlet + Vector((side * 0.22, s * 0.32, -0.78)), 8)
            _hose(ctx, ctx.uid("hose"), torn, mat="road_burnt")
            continue
        dropped = ctx.worn and s < 0
        if dropped:
            inlet = Vector((side * 0.95, s * 0.95, 0.06))
            _add_nozzle(ctx, "road_plastic_black", inlet, (-90, 0, -150))
            pts = _bezier(outlet, outlet + Vector((side * 0.2, s * 0.15, -0.1)), inlet + Vector((-side * 0.6, -s * 0.2, 0.05)),
                          inlet, 18)
        else:
            inlet, din = _boot_nozzle(ctx, "road_plastic_black", Vector((bx, by, 1.15)), lean=s)
            low = Vector((side * 0.08, s * (D / 2 + 0.42), 0.32))
            seg_a = _bezier(outlet, outlet + Vector((side * 0.12, s * 0.25, -0.15)), low + Vector((side * 0.3, 0, 0.45)), low, 12)
            seg_b = _bezier(low, low + Vector((-side * 0.18, 0, -0.22)), inlet + din * 0.45, inlet, 12)
            pts = seg_a + seg_b[1:]
        _hose(ctx, ctx.uid("hose"), pts)
    # Chrome corner trims on the head.
    for sx in (-1, 1):
        for sy in (-1, 1):
            t = K.box(ctx.uid("trim"), (0.022, 0.022, 0.7), center=(sx * (W / 2 - 0.012), sy * ((D - 0.08) / 2 - 0.012), 1.3))
            ctx.add(t, "road_chrome", uv_scale=2.0, wear=0.6)
    if burnt:
        # Rammed: pushed back and over, slumped towards +Y.
        K.kink(ctx.parts, (0, 0, 0.12), (-13, 4, 6), blend=0.2)
        soot = K.box("soot", (W + 0.4, D + 0.6, 0.004), center=(0, 0.05, 0.002))
        ctx.add(soot, "road_burnt", uv_scale=1.0, patches=0.0, edge=0.0)
    ctx.col_box((-W / 2 - 0.06, -D / 2 - 0.03, 0), (W / 2 + 0.06, D / 2 + 0.03, 1.84))


def fuel_pump_vintage(ctx: K.Ctx) -> None:
    """Older single-hose pump (1960s cabinet kept for regular): rounded red cabinet with a crown,
    rolling-number dial face in a chrome bezel, hand lever, side nozzle hook and a hose looping
    to the ground. Worn: face glass cracked, rust blooming through the red, lever snapped.
    Destroyed: knocked off its base and lying on its back."""
    W, D, H = 0.62, 0.42, 1.38
    base = K.box("base", (W + 0.06, D + 0.06, 0.07), center=(0, 0, 0.035), bevel=0.01)
    ctx.add(base, "road_steel_dark", uv_scale=1.5, low=1.0, low_h=0.3)
    body = K.box("body", (W, D, H), center=(0, 0, 0.07 + H / 2), bevel=0.07, bevel_segs=3, cuts=(2, 1, 3))
    crown = K.cyl("crown", W / 2, D, segs=20, axis="Y", center=(0, 0, 0.07 + H - 0.02))
    K.cut_plane(crown, (0, 0, 0.07 + H - 0.02), (0, 0, 1), keep="above")
    if ctx.worn:
        dr = ctx.drnd("d")
        K.dent(body, (dr.uniform(-0.2, 0.2), -D / 2, dr.uniform(0.3, 0.9)), 0.15, 0.025)
    ctx.add(body, "road_paint_red", uv_scale=1.0, patches=0.7, low=0.9, low_h=0.5, smooth=35)
    ctx.add(crown, "road_paint_red", uv_scale=1.0, patches=0.7, smooth=40)
    cap = K.box("capband", (W + 0.012, D + 0.012, 0.03), center=(0, 0, 0.07 + H - 0.05))
    ctx.add(cap, "road_chrome", uv_scale=2.0, wear=0.7)
    # Dial face (2:3) in a bezel, plus the lower access door.
    f = _face(ctx, "dial", 0.46, 0.69, _rect(ATLAS_GAS, "pump_vintage"), GAS, (0, -D / 2 - 0.004, 1.03), nu=5, nv=6)
    if ctx.worn:
        K.jagged_hole(f, (0.1, -D / 2 - 0.004, 1.15), 0.07, ctx.drnd("c").randint(0, 999), axis=1)
    for (x, z, w, h) in ((0, 1.385, 0.5, 0.025), (0, 0.675, 0.5, 0.025), (-0.24, 1.03, 0.025, 0.73), (0.24, 1.03, 0.025, 0.73)):
        bz = K.box(ctx.uid("bezel"), (w, 0.016, h), center=(x, -D / 2 - 0.006, z), bevel=0.004)
        ctx.add(bz, "road_chrome", uv_scale=2.0, wear=0.6)
    door = K.box("door", (W - 0.14, 0.008, 0.44), center=(0, -D / 2 - 0.003, 0.36), bevel=0.003)
    ctx.add(door, "road_paint_red", uv_scale=1.0, patches=0.8, low=0.9)
    _louvres(ctx, -0.18, 0.18, 0.16, 0.3, -D / 2 - 0.007, 4, "road_paint_red")
    _bolts(ctx, [(x, -D / 2 - 0.007, z) for x in (-0.22, 0.22) for z in (0.18, 0.54)], r=0.006)
    # Hand lever (reset) on the right side, nozzle hook on the left.
    piv = Vector((W / 2 + 0.01, 0.0, 1.0))
    lev_end = piv + (Vector((0.03, -0.02, -0.22)) if ctx.worn else Vector((0.04, -0.06, 0.2)))
    lever = K.tube("lever", [piv, piv + (lev_end - piv) * 0.5, lev_end], 0.012, segs=6)
    knob = K.cyl("knob", 0.022, 0.05, segs=10, center=lev_end)
    ctx.add(lever, "road_chrome", uv_scale=2.0, wear=0.6)
    ctx.add(knob, "road_plastic_black", uv_scale=2.0, wear=0.4)
    hook = K.box("hook", (0.06, 0.08, 0.1), center=(-W / 2 - 0.03, -0.08, 0.98), bevel=0.01)
    ctx.add(hook, "road_chrome", uv_scale=2.0, wear=0.7)
    out = Vector((-W / 2 - 0.01, 0.08, 1.25))
    outlet = K.cyl("outlet", 0.025, 0.05, segs=10, axis="X", center=out)
    ctx.add(outlet, "road_chrome", uv_scale=2.0)
    inlet, din = _boot_nozzle(ctx, "road_plastic_black", Vector((-W / 2 - 0.03, -0.08, 1.04)), lean=0)
    low = Vector((-W / 2 - 0.42, -0.3, 0.3))
    pts = _bezier(out, out + Vector((-0.2, -0.05, -0.2)), low + Vector((0.05, 0.12, 0.42)), low, 12)
    pts += _bezier(low, low + Vector((-0.08, -0.12, -0.16)), inlet + din * 0.4, inlet, 12)[1:]
    _hose(ctx, "hose", pts)
    if ctx.destroyed:
        # Knocked off its base: everything above the base lies on its back.
        movers = [o for o in ctx.parts if o.name not in ("base",)]
        for o in movers:
            o.data.transform(Matrix.Translation((0, 0.3, 0.0)) @ K.rot_matrix((-88, 0, 12)) @ Matrix.Translation((0, 0, -0.07)))
            o.data.update()
            K.lift_min(o)
        ctx.col_box((-0.5, -0.2, 0), (0.5, 1.8, 0.55))
    else:
        ctx.col_box((-W / 2 - 0.05, -D / 2 - 0.03, 0), (W / 2 + 0.05, D / 2 + 0.03, 0.07 + H + 0.3))


def pump_island(ctx: K.Ctx) -> None:
    """Concrete pump island (stadium plan, 0.18 m) with a steel nosing, yellow crash bollards at the
    ends, a waste bin and a squeegee bucket. Worn: chipped concrete, a bollard knocked crooked."""
    L, Wd, Ht = 4.2, 1.3, 0.18
    rr = Wd / 2
    outline = []
    for k in range(9):
        a = -math.pi / 2 + math.pi * k / 8
        outline.append((L / 2 - rr + rr * math.cos(a), rr * math.sin(a)))
    for k in range(9):
        a = math.pi / 2 + math.pi * k / 8
        outline.append((-L / 2 + rr + rr * math.cos(a), rr * math.sin(a)))
    slab = K.prism("slab", outline, Ht, plane="XY", offset=0.0, bevel=0.012)
    ctx.add(slab, "road_concrete", uv_scale=1.0, patches=0.6, edge=1.2, low=0.6, low_h=0.1)
    nosing = K.tube("nosing", [(x, y, Ht - 0.008) for x, y in outline], 0.012, segs=6, closed=True)
    ctx.add(nosing, "road_steel", uv_scale=2.0, wear=1.0, patches=0.6)
    br = ctx.rnd("b")
    for i, (x, y) in enumerate(((-L / 2 + 0.28, -0.3), (-L / 2 + 0.28, 0.3), (L / 2 - 0.28, -0.3), (L / 2 - 0.28, 0.3))):
        prof = [(0.0, 0.0), (0.055, 0.0), (0.055, 0.84), (0.05, 0.875), (0.032, 0.895), (0.0, 0.9)]
        b = K.lathe(ctx.uid("bollard"), prof, segs=12)
        band = K.cyl(ctx.uid("band"), 0.057, 0.06, segs=12, center=(0, 0, 0.72))
        for o in (b, band):
            if ctx.worn and i == 2:
                K.place(o, rot=(0, -9, 0))
            K.place(o, (x, y, Ht))
        ctx.add(b, "road_paint_yellow", uv="cyl", uv_scale=1.0, smooth=40, patches=0.7, low=0.8, low_h=0.3)
        ctx.add(band, "road_plastic_red", uv="cyl", uv_scale=1.0, smooth=40, patches=0.4)
    # Waste bin with a swing lid on a pedestal, squeegee bucket on a post.
    bin_ = K.lathe("bin", [(0.0, 0.0), (0.17, 0.0), (0.18, 0.04), (0.18, 0.62), (0.16, 0.66), (0.0, 0.66)], segs=14)
    lid = K.lathe("lid", [(0.0, 0.0), (0.19, 0.0), (0.19, 0.03), (0.12, 0.1), (0.0, 0.12)], segs=14)
    hole = K.box("hole", (0.16, 0.02, 0.06), center=(0, -0.16, 0.05), bevel=0.01)
    K.place(lid, (0, 0, 0.66))
    K.place(hole, (0, 0, 0.66))
    for o in (bin_, lid, hole):
        K.place(o, (-1.0, 0.0, Ht))
    ctx.add(bin_, "road_paint_green", uv="cyl", uv_scale=1.0, smooth=40, patches=0.7, low=0.6)
    ctx.add(lid, "road_paint_green", uv="cyl", uv_scale=1.0, smooth=40, patches=0.6)
    ctx.add(hole, "road_plastic_black", uv_scale=2.0, patches=0.0)
    post = K.box("post", (0.05, 0.05, 0.75), center=(1.0, 0.0, Ht + 0.375))
    ctx.add(post, "road_steel", uv_scale=1.5, patches=0.6)
    bk = P.bucket("bucket", top_r=0.13, bot_r=0.11, h=0.28, segs=12)
    K.place(bk, (1.0, -0.12, Ht + 0.42))
    ctx.add(bk, "road_plastic_blue", uv="cyl", uv_scale=1.0, smooth=40, patches=0.3)
    sq_h = K.cyl("sq_handle", 0.012, 0.45, segs=6, center=(0, 0, 0.225))
    sq_b = K.box("sq_blade", (0.2, 0.03, 0.05), center=(0, 0, 0.0), bevel=0.008)
    for o in (sq_h, sq_b):
        K.place(o, rot=(12, 0, 0))
        K.place(o, (1.0, -0.14, Ht + 0.5))
    ctx.add(sq_h, "road_plastic_black", uv_scale=2.0, smooth=40)
    ctx.add(sq_b, "road_rubber", uv_scale=2.0)
    if ctx.worn:
        for k in range(5):
            ch = K.chunk(ctx.uid("chip"), br.uniform(0.04, 0.09), br)
            K.place(ch, (br.uniform(-1.8, 1.8), br.choice((-0.72, 0.72)), 0.02))
            ctx.add(ch, "road_concrete", uv_scale=2.0, patches=0.6)
    ctx.col_box((-L / 2, -Wd / 2, 0), (L / 2, Wd / 2, Ht + 0.75))


# ============================================================================================
# Canopy
# ============================================================================================

CANOPY_L, CANOPY_W, CANOPY_H = 12.0, 7.0, 0.9
CANOPY_COLUMNS = [(sx * 2.6, sy * 1.4) for sx in (-1, 1) for sy in (-1, 1)]  # on two islands across the lanes


def fuel_canopy(ctx: K.Ctx) -> None:
    """Forecourt canopy roof (12 x 7 m) hung at the top of four columns (column centres at
    CANOPY_COLUMNS): green fascia with cream pinstripes and the CORDON GAS & GARAGE band front
    and back, white soffit panels with seams, eight recessed lights, drain scuppers. Origin =
    bottom centre of the fascia (place with y = the clear height). No collision (walk under it).
    Worn: soffit panels fallen out (purlins showing), lenses smashed, a fascia panel hanging."""
    L, Wd, H = CANOPY_L, CANOPY_W, CANOPY_H
    ctx.ground_clamp = False
    r = ctx.drnd("panels")
    t = 0.08
    for (sx, sy, lx, ly) in ((0, -1, L, t), (0, 1, L, t), (-1, 0, t, Wd), (1, 0, t, Wd)):
        fas = K.box(ctx.uid("fascia"), (lx, ly, H), center=(sx * (L / 2 - t / 2), sy * (Wd / 2 - t / 2), H / 2), cuts=(4, 2, 1))
        if ctx.worn and sx == 1:
            K.dent(fas, (L / 2, 1.2, 0.2), 0.8, 0.1)
        ctx.add(fas, "road_paint_green", uv_scale=1.0, patches=0.5, edge=0.8)
    # Cream pinstripes (match the lettered band cell: 14..24 px from its top and bottom edges).
    for z in (H * (1 - 19 / 256), H * (19 / 256)):
        for (sx, sy, lx, ly) in ((0, -1, L + 0.02, 0.012), (0, 1, L + 0.02, 0.012), (-1, 0, 0.012, Wd + 0.02),
                                 (1, 0, 0.012, Wd + 0.02)):
            pin = K.box(ctx.uid("pin"), (lx, ly, H * 10 / 256), center=(sx * (L / 2 + 0.002), sy * (Wd / 2 + 0.002), z))
            ctx.add(pin, "road_paint_cream", uv_scale=1.0, patches=0.4, edge=0.5)
    band = _rect(ATLAS_GAS, "canopy_band", inset=3.0)
    for s in (-1, 1):
        bf = _face(ctx, ctx.uid("band"), 7.2, H, band, GAS, (0, s * (Wd / 2 + 0.006), H / 2), 0.0 if s < 0 else 180.0,
                   nu=10, nv=2, wear=0.6)
        if ctx.worn and s > 0:
            K.jagged_hole(bf, (-2.6, Wd / 2, 0.35), 0.4, r.randint(0, 999), axis=1)
    # Roof deck (dark membrane, seen from the hills and the motel walkway) and a metal flashing
    # strip round its edge only: a full steel cap read as a quilt of rust from above.
    deck = K.box("deck", (L - 0.02, Wd - 0.02, 0.06), center=(0, 0, H - 0.03), cuts=(6, 3, 0))
    ctx.add(deck, "road_tar", uv_scale=0.25, patches=0.25)
    fw = 0.14
    for (sx, sy, lx, ly) in ((0, -1, L + 0.04, fw), (0, 1, L + 0.04, fw), (-1, 0, fw, Wd + 0.04 - 2 * fw), (1, 0, fw, Wd + 0.04 - 2 * fw)):
        cap = K.box(ctx.uid("flashing"), (lx, ly, 0.035), center=(sx * (L / 2 + 0.02 - fw / 2), sy * (Wd / 2 + 0.02 - fw / 2), H + 0.0175))
        K.delete_faces(cap, lambda c, n: n.z < -0.5)
        ctx.add(cap, "road_steel", uv_scale=1.0, patches=0.6, edge=1.0)
    # Purlins (visible where soffit panels are missing).
    for y in (-2.4, -0.8, 0.8, 2.4):
        pr = K.box(ctx.uid("purlin"), (L - 0.2, 0.08, 0.2), center=(0, y, H - 0.16))
        ctx.add(pr, "road_steel_dark", uv_scale=1.0, patches=0.6)
    for x in sorted({c[0] for c in CANOPY_COLUMNS}):
        beam = K.box(ctx.uid("girder"), (0.25, Wd - 0.2, 0.3), center=(x, 0, H - 0.21))
        ctx.add(beam, "road_steel_dark", uv_scale=1.0, patches=0.6)
    for (x, y) in CANOPY_COLUMNS:
        collar = K.box(ctx.uid("collar"), (0.42, 0.42, 0.08), center=(x, y, 0.13))
        ctx.add(collar, "road_paint_white", uv_scale=1.0, patches=0.4)
    # Soffit: 0.6 m panels across the depth with dark seams, light housings in two rows.
    lights = [(x, y) for x in (-4.6, -1.3, 1.3, 4.6) for y in (-1.9, 1.9)]
    n = int((Wd - 0.2) / 0.6)
    missing = set()
    if ctx.worn:
        missing = {r.randint(0, n - 1) for _ in range(3)}
    for k in range(n):
        y0 = -Wd / 2 + 0.1 + k * 0.6
        if k in missing:
            continue
        pn = K.box(ctx.uid("soffit"), (L - 0.18, 0.592, 0.02), center=(0, y0 + 0.3, 0.1), cuts=(6, 0, 0))
        if ctx.worn and r.random() < 0.3:
            K.place(pn, (0, 0, -r.uniform(0.0, 0.06)))
        ctx.add(pn, "road_paint_white", uv_scale=1.0, patches=0.5, low=0.0)
    if ctx.worn:
        # One panel hanging down from a single screw at one end.
        hang = K.box("hang", (2.4, 0.592, 0.02), center=(0, 0, 0))
        K.place(hang, (1.2, 0, 0))
        K.place(hang, rot=(0, 52, 8))
        K.place(hang, (-5.4, -Wd / 2 + 0.1 + (min(missing) if missing else 2) * 0.6 + 0.3, 0.1))
        ctx.add(hang, "road_paint_white", uv_scale=1.0, patches=0.7)
    for i, (x, y) in enumerate(lights):
        hs = K.box(ctx.uid("lhouse"), (0.56, 0.56, 0.05), center=(x, y, 0.07))
        ctx.add(hs, "road_paint_white", uv_scale=1.5, patches=0.4)
        lens = K.box(ctx.uid("lens"), (0.46, 0.46, 0.02), center=(x, y, 0.045), cuts=(3, 3, 0))
        broken = ctx.worn and i in (1, 4, 6)
        if broken:
            K.jagged_hole(lens, (x + 0.05, y, 0.045), 0.2, r.randint(0, 999), axis=2)
        ctx.add(lens, "road_lens_frost", uv_scale=1.0, patches=0.0, edge=0.2, ao=False)
    # Scuppers and downspout stubs at the column corners.
    for (x, y) in CANOPY_COLUMNS:
        sc = K.box(ctx.uid("scupper"), (0.12, 0.12, 0.1), center=(x + 0.18, y + 0.0, 0.06))
        ctx.add(sc, "road_steel", uv_scale=2.0, patches=0.6)
    ctx.col_box((-L / 2, -Wd / 2, 0), (L / 2, Wd / 2, H))


def canopy_column(ctx: K.Ctx) -> None:
    """Canopy column: 0.3 m steel tube on a concrete-filled, yellow-capped crash pedestal, a rain
    downspout down its back face, a fire-extinguisher bracket on the front. Worn: extinguisher
    gone (bracket only), pedestal chipped, rust running from the base plate."""
    Hc = 4.72
    ped = K.box("ped", (0.56, 0.56, 0.95), center=(0, 0, 0.475), bevel=0.03, cuts=(1, 1, 2))
    ctx.add(ped, "road_concrete", uv_scale=1.0, patches=0.6, edge=1.2, low=0.6)
    capp = K.box("pedcap", (0.565, 0.565, 0.18), center=(0, 0, 0.86), bevel=0.02)
    ctx.add(capp, "road_paint_yellow", uv_scale=1.0, patches=0.7, edge=1.2)
    col = K.box("col", (0.3, 0.3, Hc - 0.95), center=(0, 0, 0.95 + (Hc - 0.95) / 2), bevel=0.012, cuts=(0, 0, 4))
    ctx.add(col, "road_paint_white", uv_scale=1.0, patches=0.5, low=0.0)
    plate = K.box("plate", (0.4, 0.4, 0.02), center=(0, 0, 0.96))
    ctx.add(plate, "road_steel", uv_scale=2.0, wear=1.0, patches=0.6)
    _bolts(ctx, [(sx * 0.16, sy * 0.16, 0.97) for sx in (-1, 1) for sy in (-1, 1)], normal="z", r=0.014, h=0.025)
    ds = K.box("downspout", (0.075, 0.055, Hc - 1.0), center=(0, 0.18, 1.0 + (Hc - 1.0) / 2))
    ctx.add(ds, "road_steel", uv_scale=1.0, patches=0.6)
    elbow = K.tube("elbow", [(0, 0.18, 1.02), (0, 0.24, 0.98), (0, 0.33, 0.97)], 0.032, segs=8)
    ctx.add(elbow, "road_steel", uv_scale=2.0, patches=0.7)
    for z in (1.6, 2.6, 3.6):
        strap = K.box(ctx.uid("strap"), (0.09, 0.07, 0.02), center=(0, 0.18, z))
        ctx.add(strap, "road_steel_dark", uv_scale=2.0, wear=0.8)
    br = K.box("bracket", (0.12, 0.05, 0.06), center=(0, -0.175, 1.5))
    ctx.add(br, "road_steel_dark", uv_scale=2.0, wear=0.8)
    if not ctx.worn:
        ext = K.lathe("ext", [(0.0, 0.0), (0.075, 0.0), (0.08, 0.02), (0.08, 0.42), (0.06, 0.47), (0.02, 0.5), (0.0, 0.5)], segs=12)
        K.place(ext, (0, -0.25, 1.15))
        ctx.add(ext, "road_paint_red", uv="cyl", uv_scale=1.0, smooth=40, patches=0.4)
        valve = K.box("valve", (0.05, 0.07, 0.06), center=(0, -0.25, 1.68), bevel=0.008)
        ctx.add(valve, "road_chrome", uv_scale=2.0)
        hose = K.tube("exthose", [(0.02, -0.28, 1.66), (0.07, -0.31, 1.55), (0.08, -0.32, 1.3)], 0.009, segs=6)
        ctx.add(hose, "road_rubber", uv_scale=2.0, smooth=40)
    else:
        rust = K.box("rustrun", (0.3, 0.002, 0.5), center=(0, -0.152, 1.2))
        ctx.add(rust, "road_rust", uv_scale=1.0, patches=0.0, edge=0.0)
    ctx.col_box((-0.28, -0.28, 0), (0.28, 0.28, Hc))


def canopy_light(ctx: K.Ctx) -> None:
    """Under-canopy metal-halide fixture (ceiling plane at z = 0, hangs down): square housing,
    prismatic drop lens, conduit stub. Worn: lens cracked, fixture hanging askew from its
    conduit. Destroyed: torn out, dangling by its wires, lens gone."""
    ctx.ground_clamp = False
    parts = []
    hs = K.box("housing", (0.5, 0.5, 0.1), center=(0, 0, -0.05), bevel=0.01)
    rim = K.box("rim", (0.54, 0.54, 0.02), center=(0, 0, -0.1), bevel=0.004)
    lens = K.lathe("lens", [(0.0, -0.17), (0.12, -0.16), (0.2, -0.13), (0.25, -0.11), (0.25, -0.1)], segs=4,
                   angle0=math.pi / 4, cap_top=False)
    K.map_verts(lens, lambda co: Vector((co.x / math.cos(math.pi / 4) * 0.98, co.y / math.cos(math.pi / 4) * 0.98, co.z)))
    for k in range(4):
        fin = K.box(ctx.uid("fin"), (0.04, 0.3, 0.004), center=(0, 0, -0.005))
        K.place(fin, rot=(0, 0, 45 + k * 90))
        K.place(fin, (0, 0, -0.0))
    conduit = K.tube("conduit", [(0.22, 0.0, -0.05), (0.32, 0.0, -0.05), (0.38, 0.0, -0.02), (0.4, 0.0, 0.02)], 0.012, segs=6)
    box_ = K.box("jbox", (0.12, 0.12, 0.05), center=(0.4, 0.0, -0.02))
    parts = [hs, rim, lens]
    if ctx.destroyed:
        for o in parts:
            o.data.transform(Matrix.Translation((0.05, 0.1, -0.55)) @ K.rot_matrix((70, 15, 30)))
            o.data.update()
        for k in range(3):
            w = K.tube(ctx.uid("wire"), [(0.4 + k * 0.01, 0, -0.04), (0.35, 0.05, -0.3), (0.2, 0.1, -0.55)], 0.004, segs=4)
            ctx.add(w, ["road_plastic_black", "road_plastic_white", "road_plastic_green"][k], uv_scale=2.0)
    elif ctx.worn:
        for o in parts:
            o.data.transform(Matrix.Translation((0.4, 0, -0.02)) @ K.rot_matrix((0, -24, 6)) @ Matrix.Translation((-0.4, 0, 0.02)))
            o.data.update()
    ctx.add(hs, "road_paint_white", uv_scale=1.5, patches=0.5)
    ctx.add(rim, "road_steel", uv_scale=2.0, patches=0.5)
    if not ctx.destroyed:
        if ctx.worn:
            K.subdivide(lens, 1)
            K.jagged_hole(lens, (0.08, 0.05, -0.15), 0.12, ctx.drnd("l").randint(0, 999), axis=2)
        ctx.add(lens, "road_lamp_glow", uv_scale=1.0, patches=0.0, edge=0.0, ao=False)
    ctx.add(conduit, "road_steel", uv_scale=2.0, patches=0.5)
    ctx.add(box_, "road_steel", uv_scale=2.0, patches=0.5)
    ctx.col_box((-0.27, -0.27, -0.18), (0.27, 0.27, 0.0))


# ============================================================================================
# Forecourt machines
# ============================================================================================

def air_pump(ctx: K.Ctx) -> None:
    """Coin-op air & water machine on a post: lettered red cabinet with a rain hood and coin
    mechanism, coiled air hose on a hook with a chuck, water hose with a trigger nozzle.
    Worn: air hose cut and lying slack, rust, coin box pried. Destroyed: post bent, cabinet on the
    ground."""
    plate = K.box("plate", (0.32, 0.32, 0.015), center=(0, 0, 0.0075))
    post = K.box("post", (0.1, 0.1, 0.86), center=(0, 0.02, 0.44), cuts=(0, 0, 3))
    cab = K.box("cab", (0.36, 0.3, 0.66), center=(0, 0, 0.86 + 0.33), bevel=0.01)
    hood = K.prism("hood", [(-0.21, 0.0), (0.21, 0.0), (0.21, 0.035), (-0.21, 0.09)], 0.4, plane="YZ")
    K.place(hood, rot=(0, 0, 90))
    K.place(hood, (0, 0.0, 1.52))
    upper = [cab, hood]
    face_y = -0.15 - 0.003
    f = _face(ctx, "face", 0.3, 0.6, _rect(ATLAS_GAS, "air_pump"), GAS, (0, face_y, 1.19), nu=3, nv=5)
    upper.append(f)
    coin = K.box("coin", (0.08, 0.03, 0.05), center=(0, face_y - 0.012, 0.98), bevel=0.006)
    upper.append(coin)
    hook_r = K.tube("hookr", [(0.18, -0.02, 1.25), (0.25, -0.02, 1.25), (0.26, -0.02, 1.3)], 0.008, segs=6)
    hook_l = K.tube("hookl", [(-0.18, -0.02, 1.2), (-0.25, -0.02, 1.2), (-0.26, -0.02, 1.25)], 0.008, segs=6)
    upper += [hook_r, hook_l]
    # Air hose: helix coil hanging on the right hook, tail to a chuck.
    hose_pts = [Vector((0.18, 0.06, 0.95))]
    if not ctx.worn:
        for k in range(30):
            a = k / 29 * math.tau * 2.6
            hose_pts.append(Vector((0.27 + 0.02 * k / 29, -0.02 + 0.12 * math.sin(a), 1.12 + 0.13 * math.cos(a) - k * 0.004)))
        hose_pts.append(Vector((0.3, -0.12, 0.85)))
        chuck_at = Vector((0.3, -0.14, 0.78))
    else:
        hose_pts += [Vector((0.25, 0.0, 0.6)), Vector((0.32, -0.2, 0.15)), Vector((0.45, -0.45, 0.02)), Vector((0.62, -0.5, 0.02))]
        chuck_at = Vector((0.66, -0.52, 0.02))
    air = K.tube("airhose", hose_pts, 0.011, segs=6)
    chuck = K.cyl("chuck", 0.016, 0.09, segs=8, center=chuck_at)
    upper += [air, chuck]
    water_pts = [Vector((-0.18, 0.06, 0.95)), Vector((-0.26, 0.02, 1.15)), Vector((-0.27, -0.04, 1.22)),
                 Vector((-0.26, -0.1, 1.1)), Vector((-0.24, -0.12, 0.9))]
    water = K.tube("waterhose", water_pts, 0.012, segs=6)
    wn = K.box("wnozzle", (0.03, 0.05, 0.12), center=(-0.24, -0.14, 0.82), bevel=0.008)
    upper += [water, wn]
    if ctx.destroyed:
        K.kink([post] + upper, (0, 0.02, 0.32), (-70, 10, 0), blend=0.12)
        for o in upper:
            K.lift_min(o)
    ctx.add(plate, "road_steel", uv_scale=2.0, patches=0.6)
    _bolts(ctx, [(sx * 0.12, sy * 0.12, 0.015) for sx in (-1, 1) for sy in (-1, 1)], normal="z", r=0.012, h=0.015)
    ctx.add(post, "road_paint_red", uv_scale=1.0, patches=0.7, low=1.0, low_h=0.4)
    ctx.add(cab, "road_paint_red", uv_scale=1.0, patches=0.6)
    ctx.add(hood, "road_paint_red", uv_scale=1.0, patches=0.6, edge=1.2)
    ctx.add(coin, "road_chrome", uv_scale=2.0, wear=0.7)
    for o in (hook_r, hook_l, chuck):
        ctx.add(o, "road_chrome", uv_scale=2.0, wear=0.6)
    ctx.add(air, "road_rubber", uv="cyl", uv_axis=2, uv_scale=2.0, smooth=50, patches=0.2)
    ctx.add(water, "road_plastic_green", uv="cyl", uv_axis=2, uv_scale=2.0, smooth=50, patches=0.2)
    ctx.add(wn, "road_plastic_black", uv_scale=2.0, wear=0.4)
    ctx.col_box((-0.22, -0.2, 0), (0.22, 0.2, 1.6))


def ice_freezer(ctx: K.Ctx) -> None:
    """Outdoor ice merchandiser (chest): lettered ICE front, two hinged lids with gaskets, pulls and
    hasps, rear condenser grille, corner bumpers, drain spigot. Worn: a lid propped open on its
    prop rod over a puddle of melt water, the hasp's padlock hanging open. Destroyed: a lid torn off
    and lying in front, dents, rust through the panels."""
    W, D, H = 1.5, 0.75, 0.95
    kick = K.box("kick", (W - 0.06, D - 0.06, 0.1), center=(0, 0, 0.05))
    ctx.add(kick, "road_steel_dark", uv_scale=1.5, low=1.0)
    body = K.box("body", (W, D, H - 0.1), center=(0, 0, 0.1 + (H - 0.1) / 2), bevel=0.03, bevel_segs=2, cuts=(3, 1, 2))
    if ctx.worn:
        dr = ctx.drnd("d")
        for _ in range(3 if ctx.destroyed else 2):
            K.dent(body, (dr.uniform(-0.6, 0.6), -D / 2, dr.uniform(0.25, 0.7)), dr.uniform(0.12, 0.2), 0.02)
    ctx.add(body, "road_paint_white", uv_scale=1.0, patches=0.6, low=0.9, low_h=0.35, smooth=30)
    _face(ctx, "front", 1.38, 0.46, _rect(ATLAS_GAS, "ice_front"), GAS, (0, -D / 2 - 0.004, 0.6), nu=6, nv=2)
    for z in (0.33, 0.87):
        tr = K.box(ctx.uid("trim"), (W + 0.006, D + 0.006, 0.03), center=(0, 0, z))
        ctx.add(tr, "road_paint_blue", uv_scale=1.0, patches=0.5)
    for sx in (-1, 1):
        for sy in (-1, 1):
            bump = K.box(ctx.uid("bumper"), (0.06, 0.06, 0.82), center=(sx * (W / 2 - 0.01), sy * (D / 2 - 0.01), 0.52),
                         bevel=0.015)
            ctx.add(bump, "road_plastic_black", uv_scale=2.0, wear=0.5)
    _louvres(ctx, -0.5, 0.5, 0.14, 0.3, D / 2 + 0.003, 5, "road_steel_dark", face="+y")
    spig = K.cyl("spigot", 0.012, 0.06, segs=8, axis="X", center=(W / 2 + 0.03, -0.2, 0.16))
    ctx.add(spig, "road_chrome", uv_scale=2.0)
    hinge_y, hinge_z = D / 2 - 0.02, H + 0.005
    for i, x in enumerate((-W / 4, W / 4)):
        lid = K.box(ctx.uid("lid"), (W / 2 - 0.03, D - 0.02, 0.05), center=(x, 0, H + 0.025), bevel=0.012)
        gasket = K.box(ctx.uid("gasket"), (W / 2 - 0.05, D - 0.05, 0.012), center=(x, 0, H - 0.002))
        pull = K.box(ctx.uid("pull"), (0.22, 0.03, 0.025), center=(x, -D / 2 + 0.005, H + 0.03), bevel=0.006)
        hasp = K.box(ctx.uid("hasp"), (0.03, 0.01, 0.07), center=(x + 0.16, -D / 2 - 0.006, H - 0.01))
        grp = [lid, gasket, pull, hasp]
        ang = 0.0
        if ctx.worn and i == 1 and not ctx.destroyed:
            ang = -72.0
        if ang:
            for o in grp:
                o.data.transform(Matrix.Translation((0, hinge_y, hinge_z)) @ K.rot_matrix((ang, 0, 0)) @ Matrix.Translation((0, -hinge_y, -hinge_z)))
                o.data.update()
            rod = K.tube("proprod", [(x + 0.3, -0.25, H), (x + 0.3, -0.1, H + 0.55)], 0.007, segs=6)
            ctx.add(rod, "road_chrome", uv_scale=2.0)
        if ctx.destroyed and i == 0:
            for o in grp:
                o.data.transform(Matrix.Translation((-0.2, -1.05, 0.0)) @ K.rot_matrix((0, 8, 25)) @ Matrix.Translation((-x, 0, -H)))
                o.data.update()
                K.lift_min(o)
        ctx.add(lid, "road_paint_white", uv_scale=1.0, patches=0.6, smooth=30)
        ctx.add(gasket, "road_rubber", uv_scale=2.0)
        ctx.add(pull, "road_chrome", uv_scale=2.0, wear=0.6)
        ctx.add(hasp, "road_steel", uv_scale=2.0, wear=0.8)
        if not (ctx.destroyed and i == 0):
            _padlock(ctx, Vector((x + 0.16, -D / 2 - 0.02, H - 0.04)), open_=ctx.worn and i == 1)
    if ctx.worn:
        inner = K.box("liner", (W / 2 - 0.08, D - 0.1, 0.02), center=(W / 4, 0, H - 0.25))
        ctx.add(inner, "road_paint_grey", uv_scale=1.0, patches=0.3)
        bag = P.add_bag(ctx, "icebag", ctx.rnd("bag"), "road_bag_clear", size=(0.32, 0.22, 0.3), segs=10, flat=0.5,
                        loc=(W / 4 - 0.1, 0.0, H - 0.24), rotz=30)
        puddle = K.cyl("melt", 0.45, 0.003, segs=16, center=(0.2, -0.55, 0.0015))
        K.map_verts(puddle, lambda co: Vector((co.x * 1.4, co.y * 0.8, co.z)))
        ctx.add(puddle, "road_water_film", uv_scale=1.0, patches=0.0, edge=0.0, ao=False)
    ctx.col_box((-W / 2, -D / 2, 0), (W / 2, D / 2, H + 0.06))


def vending_machine(ctx: K.Ctx) -> None:
    """90s soda machine: red cabinet, printed front (TAMSIN SPRINGS), clear selection buttons over
    the flavour column, coin slot + return cup, T-handle lock, hinges, delivery bin with its flap,
    leveling feet and rear vents. Worn: dented side, coin door pried, cans dropped at its feet. Destroyed: door wrenched open on its hinges, can
    columns showing, cans spilled across the floor."""
    W, D, H = 0.95, 0.82, 1.83
    for sx in (-1, 1):
        for sy in (-1, 1):
            foot = K.cyl(ctx.uid("foot"), 0.025, 0.04, segs=8, center=(sx * 0.4, sy * 0.33, 0.02))
            ctx.add(foot, "road_steel_dark", uv_scale=2.0)
    cab = K.box("cab", (W, D - 0.06, H - 0.04), center=(0, 0.03, 0.04 + (H - 0.04) / 2), bevel=0.012, cuts=(1, 2, 3))
    if ctx.worn:
        K.dent(cab, (W / 2, 0.1, 0.9), 0.25, 0.03)
    ctx.add(cab, "road_paint_red", uv_scale=1.0, patches=0.6, low=0.9, low_h=0.4)
    _louvres(ctx, -0.3, 0.3, 1.55, 1.75, D / 2 + 0.003, 5, "road_paint_red", face="+y")
    hinge_x, door_y = -W / 2 + 0.02, -D / 2 + 0.03
    door_parts = []
    frame = K.box("doorframe", (W, 0.06, H - 0.06), center=(0, door_y, 0.06 + (H - 0.06) / 2), bevel=0.01)
    door_parts.append((frame, "road_paint_black", {"patches": 0.6, "low": 0.8}))
    fy = door_y - 0.032
    face = K.quad_sheet("front", (-0.4375, 0, -0.875), (0.4375, 0, -0.875), (0.4375, 0, 0.875), (-0.4375, 0, 0.875), 4, 8)
    K.uv_planar(face, 1, rect=_rect(ATLAS_GAS, "vending"))
    K.place(face, (0, fy, 0.08 + 0.875))
    door_parts.append((face, GAS, {"patches": 0.35, "wear": 0.5}))
    # No separate polycarbonate sheet over the print: a glass layer this size mirrors the sky and
    # washed the whole front out to grey in-engine. The print's own wear carries the age.
    # Selection buttons over the printed flavour column: cell x 382..490 of 512, rows 70+120 i (56 px).
    for i in range(6):
        cx = -0.4375 + 0.875 * (436 / 512)
        cz = 0.08 + 1.75 * (1 - (98 + i * 120) / 1024)
        b = K.box(ctx.uid("btn"), (0.17, 0.02, 0.085), center=(cx, fy - 0.012, cz), bevel=0.006)
        door_parts.append((b, "road_glass", {"patches": 0.0, "ao": False}))
    cz_coin = 0.08 + 1.75 * (1 - 870 / 1024)
    slot = K.box("slot", (0.07, 0.03, 0.09), center=(0.31, fy - 0.015, cz_coin + 0.08), bevel=0.006)
    ret = K.box("return", (0.09, 0.05, 0.07), center=(0.31, fy - 0.025, cz_coin - 0.06), bevel=0.008)
    lock = K.cyl("lock", 0.022, 0.03, segs=10, axis="Y", center=(0.31, fy - 0.015, 0.75))
    tbar = K.box("tbar", (0.09, 0.02, 0.018), center=(0.31, fy - 0.035, 0.75), bevel=0.004)
    for o in (slot, ret, lock, tbar):
        door_parts.append((o, "road_chrome", {"wear": 0.7}))
    binb = K.box("bin", (0.5, 0.05, 0.18), center=(-0.13, fy - 0.012, 0.2), bevel=0.01)
    flap = K.box("flap", (0.44, 0.02, 0.12), center=(-0.13, fy - 0.036, 0.21), bevel=0.004)
    K.place(flap, (0.13, -fy + 0.036, -0.21))
    K.place(flap, rot=(-14, 0, 0))
    K.place(flap, (-0.13, fy - 0.036, 0.21))
    door_parts += [(binb, "road_plastic_black", {"wear": 0.4}), (flap, "road_plastic_black", {"wear": 0.4})]
    if ctx.worn and not ctx.destroyed:
        # Coin door pried: bent plate sticking out.
        pry = K.box("pry", (0.12, 0.012, 0.18), center=(0.31, fy - 0.05, cz_coin))
        K.place(pry, (-0.31, -(fy - 0.05), -cz_coin))
        K.place(pry, rot=(0, 0, 28))
        K.place(pry, (0.31, fy - 0.05, cz_coin))
        door_parts.append((pry, "road_steel", {"wear": 1.0}))
    if ctx.destroyed:
        for o, _, _ in door_parts:
            o.data.transform(Matrix.Translation((hinge_x, door_y, 0)) @ K.rot_matrix((0, 0, -68)) @ Matrix.Translation((-hinge_x, -door_y, 0)))
            o.data.update()
        inner = K.box("inner", (W - 0.08, 0.05, H - 0.15), center=(0, -D / 2 + 0.12, 0.95))
        ctx.add(inner, "road_paint_grey", uv_scale=1.0, patches=0.5)
        cr = ctx.rnd("columns")
        for k in range(6):
            col = K.box(ctx.uid("column"), (0.12, 0.5, 1.4), center=(-0.36 + k * 0.145, 0.0, 0.85))
            ctx.add(col, "road_steel", uv_scale=1.5, patches=0.5)
    for o, m, kw in door_parts:
        ctx.add(o, m, uv=None if m == GAS else "box", uv_scale=1.0, **kw)
    for z in (0.3, 1.0, 1.65):
        hg = K.cyl(ctx.uid("hinge"), 0.014, 0.08, segs=8, center=(hinge_x - 0.01, door_y - 0.02, z))
        ctx.add(hg, "road_steel", uv_scale=2.0, wear=0.7)
    if ctx.worn:
        cr = ctx.drnd("cans")
        n = 14 if ctx.destroyed else 5
        for i in range(n):
            c = P.can(ctx.uid("can"), cr, crushed=cr.uniform(0.0, 0.6), segs=8)
            K.place(c, rot=(90, 0, cr.uniform(0, 360)))
            K.lift_min(c)
            K.place(c, (cr.uniform(-0.7, 0.6), cr.uniform(-1.3, -0.5), 0))
            ctx.add(c, cr.choice(["can_red", "can_blue", "can_green", "can_alu"]), uv="cyl", uv_axis=2, uv_scale=1.0,
                    smooth=45, patches=0.3)
    ctx.col_box((-W / 2, -D / 2, 0), (W / 2, D / 2, H))


def newspaper_box(ctx: K.Ctx) -> None:
    """Coin-op newspaper box on a pedestal: lettered blue front with the Courier's last edition
    behind the window (ROUTE 9 CLOSED AT CORDON), coin mechanism hood, pull handle, bottom hinges.
    Worn: window cracked, dents, rust. Destroyed: knocked over onto its back."""
    W, D, H = 0.48, 0.4, 0.7
    z0 = 0.4
    base = K.box("base", (0.4, 0.36, 0.02), center=(0, 0, 0.01))
    stem = K.box("stem", (0.08, 0.08, z0 - 0.02), center=(0, 0.04, 0.02 + (z0 - 0.02) / 2))
    body = K.box("body", (W, D, H), center=(0, 0, z0 + H / 2), bevel=0.012, cuts=(1, 1, 2))
    hood = K.box("hood", (0.2, 0.14, 0.11), center=(0.0, -0.08, z0 + H + 0.05), bevel=0.012)
    roof = K.box("roof", (W + 0.03, D + 0.03, 0.02), center=(0, 0, z0 + H + 0.005), bevel=0.006)
    grp = [base, stem, body, hood, roof]
    f = _face(ctx, "front", 0.46, 0.69, _rect(ATLAS_GAS, "newspaper"), GAS, (0, -D / 2 - 0.004, z0 + 0.35), nu=4, nv=6)
    win = K.box("window", (0.4, 0.006, 0.36), center=(0, -D / 2 - 0.009, z0 + 0.35 + 0.69 * (0.5 - 390 / 768)), cuts=(4, 0, 4))
    if ctx.worn:
        K.jagged_hole(win, (0.06, -D / 2 - 0.009, z0 + 0.38), 0.11, ctx.drnd("w").randint(0, 999), axis=1)
    handle = K.box("handle", (0.16, 0.03, 0.022), center=(0, -D / 2 - 0.02, z0 + 0.12), bevel=0.006)
    coin = K.box("coinplate", (0.08, 0.012, 0.05), center=(0, -0.155, z0 + H + 0.06), bevel=0.004)
    hinges = [K.cyl(ctx.uid("hinge"), 0.01, 0.06, segs=8, axis="X", center=(sx * 0.15, -D / 2 - 0.008, z0 + 0.02)) for sx in (-1, 1)]
    grp += [f, win, handle, coin] + hinges
    if ctx.worn:
        K.dent(body, (W / 2, 0.0, z0 + 0.4), 0.15, 0.02)
    if ctx.destroyed:
        for o in grp:
            o.data.transform(Matrix.Translation((0, 0.2, 0.0)) @ K.rot_matrix((-90, 0, 18)))
            o.data.update()
            K.lift_min(o)
    ctx.add(base, "road_steel_dark", uv_scale=2.0, patches=0.6)
    ctx.add(stem, "road_steel_dark", uv_scale=2.0, patches=0.6, low=0.8)
    ctx.add(body, "road_paint_blue", uv_scale=1.0, patches=0.6, low=0.6)
    ctx.add(hood, "road_chrome", uv_scale=2.0, wear=0.6)
    ctx.add(roof, "road_paint_blue", uv_scale=1.0, patches=0.6, edge=1.2)
    ctx.add(win, "road_glass", uv_scale=1.0, patches=0.0, ao=False)
    ctx.add(handle, "road_chrome", uv_scale=2.0, wear=0.6)
    ctx.add(coin, "road_chrome", uv_scale=2.0, wear=0.6)
    for h_ in hinges:
        ctx.add(h_, "road_steel", uv_scale=2.0)
    ctx.col_box((-W / 2, -D / 2, 0), (W / 2, D / 2, z0 + H + 0.12))


# ============================================================================================
# Garage
# ============================================================================================

def tire_rack(ctx: K.Ctx) -> None:
    """Two-tier tube tyre rack loaded with used tyres standing on their treads. Worn: half empty,
    a tyre fallen out and lying on the floor, rack bowed."""
    L, Dp, H = 1.8, 0.5, 1.6
    tube = 0.016
    for sx in (-1, 1):
        for sy in (-1, 1):
            up = K.box(ctx.uid("up"), (0.035, 0.035, H), center=(sx * (L / 2 - 0.02), sy * (Dp / 2 - 0.02), H / 2))
            ctx.add(up, "road_paint_grey", uv_scale=2.0, patches=0.6, low=0.8)
            ft = K.box(ctx.uid("foot"), (0.07, 0.07, 0.008), center=(sx * (L / 2 - 0.02), sy * (Dp / 2 - 0.02), 0.004))
            ctx.add(ft, "road_steel", uv_scale=2.0)
    tiers = (0.12, 0.92)
    for z in tiers:
        for sy in (-1, 1):
            rail = K.cyl(ctx.uid("rail"), tube, L, segs=8, axis="X", center=(0, sy * 0.13, z))
            ctx.add(rail, "road_paint_grey", uv_scale=2.0, patches=0.6)
        for sx in (-1, 1):
            cross = K.cyl(ctx.uid("cross"), tube, Dp, segs=8, axis="Y", center=(sx * (L / 2 - 0.02), 0, z))
            ctx.add(cross, "road_paint_grey", uv_scale=2.0, patches=0.6)
    top = K.cyl("toprail", tube, L, segs=8, axis="X", center=(0, 0, H - 0.02))
    ctx.add(top, "road_paint_grey", uv_scale=2.0, patches=0.6)
    r = ctx.rnd("tyres")
    dr = ctx.drnd("gone")
    ro = 0.31
    for ti, z in enumerate(tiers):
        n = 4
        for k in range(n):
            if ctx.worn and dr.random() < 0.35:
                continue
            t = _tire(ctx.uid("tyre"), ro=ro * r.uniform(0.94, 1.03), rb=0.19, w=r.uniform(0.17, 0.22), segs=18, grooves=False)
            K.place(t, rot=(0, 90, 0))
            K.place(t, rot=(r.uniform(-4, 4), 0, r.uniform(-6, 6)))
            K.place(t, (-L / 2 + 0.24 + k * 0.43, r.uniform(-0.02, 0.02), z + ro * 0.86))
            ctx.add(t, "road_tire", uv="cyl", uv_axis=0, uv_scale=1.0, smooth=50, patches=0.2, edge=0.3)
    if ctx.worn:
        t = _tire("fallen", ro=0.31, rb=0.19, w=0.2, segs=18, grooves=False)
        K.place(t, (0.4, -0.75, 0.1))
        ctx.add(t, "road_tire", uv="cyl", uv_axis=2, uv_scale=1.0, smooth=50, patches=0.2)
    ctx.col_box((-L / 2, -Dp / 2, 0), (L / 2, Dp / 2, H))


def tire_stack(ctx: K.Ctx) -> None:
    """Four used tyres stacked flat (one on a steel rim), the top one slid askew; rain water and
    leaf litter in the top one. Worn: stack toppled into a slumped pile."""
    r = ctx.rnd("stack")
    z = 0.0
    for k in range(4):
        w = r.uniform(0.18, 0.22)
        t = _tire(ctx.uid("tyre"), ro=r.uniform(0.3, 0.33), rb=0.19, w=w, segs=22, grooves=False)
        dx, dy = r.uniform(-0.04, 0.04), r.uniform(-0.04, 0.04)
        if k == 3:
            dx, dy = 0.08, -0.05
        if ctx.worn and k >= 2:
            K.place(t, rot=(70 + k * 6, 0, r.uniform(0, 180)))
            K.place(t, (0.35 + (k - 2) * 0.25, -0.2, 0.0))
            K.lift_min(t)
            ctx.add(t, "road_tire", uv="cyl", uv_axis=2, uv_scale=1.0, smooth=50, patches=0.2)
            continue
        K.place(t, (dx, dy, z + w / 2))
        K.place(t, rot=(r.uniform(-3, 3), r.uniform(-3, 3), r.uniform(0, 360)))
        ctx.add(t, "road_tire", uv="cyl", uv_axis=2, uv_scale=1.0, smooth=50, patches=0.2)
        if k == 1:
            rim = P.steel_rim("rim", 0.19, 0.16, segs=14)
            K.place(rim, rot=(0, 90, 0))
            K.place(rim, (dx, dy, z + w / 2))
            ctx.add(rim, "road_steel", uv_scale=2.0, smooth=40, wear=1.0, patches=0.7)
        z += w * 0.98
    if not ctx.worn:
        pool = K.cyl("pool", 0.18, 0.004, segs=14, center=(0.08, -0.05, z - 0.03))
        ctx.add(pool, "road_water_film", uv_scale=1.0, patches=0.0, edge=0.0, ao=False)
    ctx.col_box((-0.34, -0.34, 0), (0.34, 0.34, max(z, 0.4)))


LIFT_CARRIAGE_Z = 1.85
LIFT_SPAN = 3.44  # post centre to post centre: two posts mirrored (rot 180) meet in the middle


def _lift_post(ctx: K.Ctx, power: bool) -> None:
    """Two-post car lift column (the left post; the right is the same model turned 180 deg, its
    half of the overhead beam meeting this one LIFT_SPAN away): open steel channel, carriage with
    two swing arms and screw pads raised to LIFT_CARRIAGE_Z, hydraulic cylinder, equaliser
    cables over sheaves, half overhead beam with the shut-off bar, base plate with anchors;
    `power`: motor, pump and reservoir with the push-button station. Worn: rust, chipped paint,
    a pad missing, hydraulic oil weeping down the post."""
    H = 3.65
    paint = "road_paint_lift"
    base = K.box("base", (0.55, 0.5, 0.02), center=(0, 0, 0.01))
    ctx.add(base, "road_steel_dark", uv_scale=2.0, patches=0.6)
    _bolts(ctx, [(sx * 0.21, sy * 0.19, 0.02) for sx in (-1, 1) for sy in (-1, 1)], normal="z", r=0.016, h=0.03)
    web = K.box("web", (0.012, 0.32, H), center=(-0.144, 0, H / 2), cuts=(0, 0, 4))
    fl = [K.box(ctx.uid("flange"), (0.3, 0.012, H), center=(0, sy * 0.154, H / 2), cuts=(0, 0, 4)) for sy in (-1, 1)]
    lips = [K.box(ctx.uid("lip"), (0.012, 0.05, H), center=(0.144, sy * 0.13, H / 2)) for sy in (-1, 1)]
    for o in [web] + fl + lips:
        ctx.add(o, paint, uv_scale=1.0, patches=0.6, low=0.9, low_h=0.5)
    # Safety lock ladder inside the channel.
    ladder = K.box("ladder", (0.02, 0.06, H - 0.4), center=(-0.12, 0, H / 2))
    ctx.add(ladder, "road_steel", uv_scale=2.0, patches=0.6)
    cyl_body = K.cyl("cylbody", 0.045, 1.6, segs=12, center=(-0.07, 0, 0.82))
    rod = K.cyl("rod", 0.024, LIFT_CARRIAGE_Z - 1.62, segs=10, center=(-0.07, 0, 1.62 + (LIFT_CARRIAGE_Z - 1.62) / 2))
    ctx.add(cyl_body, "road_steel_dark", uv="cyl", uv_scale=2.0, smooth=40, patches=0.5)
    ctx.add(rod, "road_chrome", uv="cyl", uv_scale=2.0, smooth=40, wear=0.6)
    cz = LIFT_CARRIAGE_Z
    car = K.box("carriage", (0.22, 0.24, 0.72), center=(0.02, 0, cz + 0.24), bevel=0.01)
    carp = K.box("carplate", (0.08, 0.36, 0.3), center=(0.17, 0, cz + 0.05), bevel=0.008)
    ctx.add(car, paint, uv_scale=1.0, patches=0.6)
    ctx.add(carp, paint, uv_scale=1.0, patches=0.6)
    rel = K.box("release", (0.02, 0.12, 0.02), center=(0.15, -0.2, cz + 0.45))
    knob = K.box("relknob", (0.03, 0.04, 0.03), center=(0.15, -0.27, cz + 0.45), bevel=0.006)
    ctx.add(rel, "road_steel", uv_scale=2.0)
    ctx.add(knob, "road_plastic_yellow", uv_scale=2.0)
    # Swing arms (front long, back short) with screw pads.
    dr = ctx.drnd("pads")
    for k, (ang, L) in enumerate(((-38.0, 1.12), (30.0, 0.86))):
        piv = Vector((0.2, -0.12 if ang < 0 else 0.12, cz - 0.02))
        d = Vector((math.cos(math.radians(ang)), math.sin(math.radians(ang)), 0.0))
        outer = K.box(ctx.uid("arm"), (L * 0.62, 0.1, 0.07), center=(L * 0.31, 0, 0), bevel=0.006)
        inner = K.box(ctx.uid("arminner"), (L * 0.42, 0.08, 0.055), center=(L * 0.62 + L * 0.19, 0, 0.0), bevel=0.005)
        pin = K.cyl(ctx.uid("armpin"), 0.03, 0.12, segs=10, center=(0, 0, 0.02))
        tread = K.box(ctx.uid("armtread"), (L * 0.5, 0.095, 0.004), center=(L * 0.3, 0, 0.037))
        pad_post = K.cyl(ctx.uid("padpost"), 0.022, 0.08, segs=10, center=(L - 0.04, 0, 0.07))
        pad = K.lathe(ctx.uid("pad"), [(0.0, 0.0), (0.06, 0.0), (0.065, 0.015), (0.06, 0.03), (0.0, 0.03)], segs=12)
        K.place(pad, (L - 0.04, 0, 0.11))
        grp = [outer, inner, pin, tread, pad_post, pad]
        for o in grp:
            K.place(o, rot=(0, 0, ang))
            K.place(o, piv)
        ctx.add(outer, paint, uv_scale=1.0, patches=0.6)
        ctx.add(inner, "road_steel", uv_scale=1.5, patches=0.5)
        ctx.add(pin, "road_chrome", uv_scale=2.0)
        ctx.add(tread, "road_tread", uv_scale=4.0, patches=0.3)
        ctx.add(pad_post, "road_chrome", uv_scale=2.0, wear=0.6)
        if not (ctx.worn and k == 1 and dr.random() < 0.7):
            ctx.add(pad, "road_rubber", uv_scale=2.0, smooth=40)
    # Overhead half beam, sheaves, cables, shut-off bar.
    beam = K.box("beam", (LIFT_SPAN / 2 + 0.05, 0.12, 0.16), center=((LIFT_SPAN / 2 + 0.05) / 2 - 0.05, 0, H + 0.08))
    ctx.add(beam, paint, uv_scale=1.0, patches=0.6)
    cap = K.box("cap", (0.34, 0.36, 0.06), center=(0, 0, H + 0.03))
    ctx.add(cap, paint, uv_scale=1.0, patches=0.6)
    sheave = K.cyl("sheave", 0.07, 0.03, segs=14, axis="Y", center=(0.05, 0, H - 0.05))
    ctx.add(sheave, "road_steel", uv_scale=2.0, smooth=40)
    for k, sy in enumerate((-0.03, 0.03)):
        cab_ = K.tube(ctx.uid("cable"), [(0.06, sy, cz + 0.6), (0.1, sy, H - 0.08), (0.2, sy, H + 0.04),
                                         (LIFT_SPAN / 2, sy, H + 0.04)], 0.005, segs=4)
        ctx.add(cab_, "road_steel", uv_scale=2.0, wear=0.6)
    bar = K.cyl("shutbar", 0.016, LIFT_SPAN / 2 - 0.3, segs=8, axis="X", center=(0.3 + (LIFT_SPAN / 2 - 0.3) / 2, 0, H - 0.1))
    ctx.add(bar, "road_steel", uv_scale=2.0, patches=0.4)
    foam = K.cyl("barfoam", 0.04, 0.5, segs=10, axis="X", center=(LIFT_SPAN / 2 - 0.3, 0, H - 0.1))
    ctx.add(foam, "road_plastic_yellow", uv_scale=2.0, smooth=40, wear=0.5)
    if power:
        mx, my = -0.05, -0.24
        motor = K.cyl("motor", 0.085, 0.3, segs=14, center=(mx, my, 1.35))
        fins = K.cyl("motorfins", 0.09, 0.2, segs=14, center=(mx, my, 1.32))
        pump = K.box("pumpblock", (0.14, 0.12, 0.14), center=(mx, my, 1.13), bevel=0.01)
        tank = K.box("tank", (0.16, 0.13, 0.3), center=(mx, my, 0.9), bevel=0.02)
        bracket = K.box("pbracket", (0.18, 0.08, 0.04), center=(mx, -0.18, 1.2))
        btns = K.box("btnbox", (0.08, 0.06, 0.12), center=(0.08, -0.2, 1.35), bevel=0.008)
        b_up = K.cyl("btnup", 0.014, 0.02, segs=10, axis="Y", center=(0.08, -0.235, 1.38))
        hyd = K.tube("hydhose", [(mx, my + 0.06, 1.13), (mx + 0.04, -0.14, 0.95), (-0.07, -0.05, 0.4), (-0.07, 0.0, 0.08)],
                     0.012, segs=6)
        ctx.add(motor, "road_paint_grey", uv="cyl", uv_scale=1.0, smooth=40, patches=0.5)
        ctx.add(fins, "road_steel_dark", uv="cyl", uv_scale=2.0, smooth=40, patches=0.5)
        ctx.add(pump, "road_alu", uv_scale=2.0, patches=0.5)
        ctx.add(tank, "road_plastic_white", uv_scale=1.0, patches=0.4)
        ctx.add(bracket, "road_steel_dark", uv_scale=2.0)
        ctx.add(btns, "road_plastic_black", uv_scale=2.0)
        ctx.add(b_up, "road_plastic_green", uv_scale=2.0)
        ctx.add(hyd, "road_rubber", uv_scale=2.0, smooth=40)
        if ctx.worn:
            weep = K.box("weep", (0.12, 0.002, 0.9), center=(-0.07, -0.161, 0.5))
            ctx.add(weep, "road_oil_dark", uv_scale=1.0, patches=0.0, edge=0.0)
    ctx.col_box((-0.27, -0.25, 0), (0.27, 0.25, H + 0.16))


def lift_post(ctx: K.Ctx) -> None:
    _lift_post(ctx, True)


def lift_post_b(ctx: K.Ctx) -> None:
    _lift_post(ctx, False)


def tool_chest(ctx: K.Ctx) -> None:
    """Rolling tool chest: roller cabinet (six drawers on ball slides, full-width pulls, side handle,
    rubber top mat, casters) under a top chest with five drawers and a lid. Worn: lid propped open
    over the till tray, drawers left ajar. Destroyed: drawers ripped out and dumped, lid torn off,
    dents."""
    W, D = 0.68, 0.46
    r = ctx.drnd("drawers")
    paint = "road_paint_red"
    for (x, y, br) in ((-0.28, -0.17, True), (0.28, -0.17, True), (-0.28, 0.17, False), (0.28, 0.17, False)):
        _caster(ctx, x, y, 0.13, r=0.05, brake=br)
    cab = K.box("cab", (W, D, 0.86), center=(0, 0, 0.13 + 0.43), bevel=0.01)
    ctx.add(cab, paint, uv_scale=1.0, patches=0.5, low=0.8, low_h=0.4)
    heights = (0.09, 0.09, 0.12, 0.12, 0.16, 0.2)
    z = 0.13 + 0.86 - 0.02
    for k, dh in enumerate(heights):
        z -= dh
        pull_out = 0.0
        if ctx.destroyed:
            pull_out = r.uniform(0.05, 0.3)
        elif ctx.worn and r.random() < 0.3:
            pull_out = r.uniform(0.03, 0.12)
        fr = K.box(ctx.uid("drawer"), (W - 0.04, 0.012, dh - 0.008), center=(0, -D / 2 - 0.006 - pull_out, z + dh / 2), bevel=0.003)
        pull = K.box(ctx.uid("pull"), (W - 0.1, 0.022, 0.016), center=(0, -D / 2 - 0.022 - pull_out, z + dh - 0.022), bevel=0.004)
        ctx.add(fr, paint, uv_scale=1.0, patches=0.5)
        ctx.add(pull, "road_alu", uv_scale=2.0, wear=0.5)
        if pull_out > 0.02:
            box_ = K.box(ctx.uid("dbox"), (W - 0.06, pull_out, dh - 0.02), center=(0, -D / 2 - pull_out / 2, z + dh / 2))
            ctx.add(box_, "road_steel_dark", uv_scale=1.0, patches=0.4)
            _scatter_tools(ctx, r, (0, -D / 2 - pull_out / 2, z + dh - 0.01), (W - 0.12, max(0.02, pull_out - 0.04)))
    mat = K.box("topmat", (W - 0.02, D - 0.02, 0.006), center=(0, 0, 0.13 + 0.86 + 0.003))
    ctx.add(mat, "road_rubber", uv_scale=2.0, patches=0.2)
    handle = K.tube("handle", [(W / 2 + 0.0, -0.17, 0.9), (W / 2 + 0.06, -0.17, 0.9), (W / 2 + 0.06, 0.17, 0.9),
                               (W / 2 + 0.0, 0.17, 0.9)], 0.012, segs=8)
    ctx.add(handle, "road_chrome", uv_scale=2.0, wear=0.6)
    # Top chest.
    tz = 0.13 + 0.86 + 0.006
    top = K.box("topchest", (W - 0.02, D - 0.06, 0.36), center=(0, 0.02, tz + 0.18), bevel=0.01)
    ctx.add(top, paint, uv_scale=1.0, patches=0.5)
    z = tz + 0.33
    for k, dh in enumerate((0.06, 0.06, 0.06, 0.08, 0.08)):
        z -= dh
        po = r.uniform(0.04, 0.2) if ctx.destroyed and k % 2 == 0 else 0.0
        fr = K.box(ctx.uid("tdrawer"), (W - 0.06, 0.012, dh - 0.008), center=(0, -D / 2 + 0.024 - po, z + dh / 2), bevel=0.003)
        pull = K.box(ctx.uid("tpull"), (W - 0.12, 0.02, 0.012), center=(0, -D / 2 + 0.01 - po, z + dh - 0.018), bevel=0.003)
        ctx.add(fr, paint, uv_scale=1.0, patches=0.5)
        ctx.add(pull, "road_alu", uv_scale=2.0, wear=0.5)
    lid = K.box("lid", (W - 0.01, D - 0.05, 0.03), center=(0, 0.02, tz + 0.375), bevel=0.008)
    hinge_y, hinge_z = D / 2 - 0.02, tz + 0.36
    if ctx.destroyed:
        lid.data.transform(Matrix.Translation((0.55, -0.55, 0.0)) @ K.rot_matrix((0, 0, 35)) @ Matrix.Translation((0, 0, -(tz + 0.36))))
        lid.data.update()
        K.lift_min(lid)
    elif ctx.worn:
        lid.data.transform(Matrix.Translation((0, hinge_y, hinge_z)) @ K.rot_matrix((-100, 0, 0)) @ Matrix.Translation((0, -hinge_y, -hinge_z)))
        lid.data.update()
        tray = K.box("tray", (W - 0.06, D - 0.12, 0.012), center=(0, 0.02, tz + 0.345))
        ctx.add(tray, "road_rubber", uv_scale=2.0)
        _scatter_tools(ctx, ctx.rnd("tray"), (0, 0.02, tz + 0.352), (W - 0.12, D - 0.16))
    ctx.add(lid, paint, uv_scale=1.0, patches=0.5)
    lock = K.cyl("lock", 0.01, 0.012, segs=8, axis="Y", center=(0.27, -D / 2 + 0.015, tz + 0.3))
    ctx.add(lock, "road_chrome", uv_scale=2.0)
    if not ctx.worn:
        _scatter_tools(ctx, ctx.rnd("top"), (0.0, -0.05, 0.13 + 0.86 + 0.006), (0.0, 0.0), n=0)
    ctx.col_box((-W / 2, -D / 2 - 0.02, 0), (W / 2, D / 2, tz + 0.39))


def _scatter_tools(ctx, r, center, extent, n: int = 4) -> None:
    """Wrenches, a ratchet and sockets lying in a tray/drawer."""
    cx, cy, cz = center
    for i in range(n):
        x = cx + r.uniform(-extent[0] / 2, extent[0] / 2)
        y = cy + r.uniform(-extent[1] / 2, extent[1] / 2)
        kind = i % 3
        if kind == 0:
            L = r.uniform(0.14, 0.24)
            sh = K.box(ctx.uid("wrench"), (L, 0.016, 0.006), center=(0, 0, 0.003), bevel=0.002)
            e1 = K.cyl(ctx.uid("wr_end"), 0.016, 0.007, segs=8, center=(L / 2, 0, 0.0035))
            e2 = K.cyl(ctx.uid("wr_end"), 0.014, 0.007, segs=8, center=(-L / 2, 0, 0.0035))
            grp = [sh, e1, e2]
        elif kind == 1:
            sh = K.cyl(ctx.uid("ratchet"), 0.009, 0.18, segs=8, axis="X", center=(0, 0, 0.009))
            hd = K.cyl(ctx.uid("rhead"), 0.02, 0.016, segs=10, center=(0.1, 0, 0.009))
            grp = [sh, hd]
        else:
            grp = [K.cyl(ctx.uid("socket"), 0.012 + k * 0.002, 0.03, segs=8, center=(k * 0.035, 0, 0.015)) for k in range(3)]
        rz = r.uniform(0, 180)
        for o in grp:
            K.place(o, rot=(0, 0, rz))
            K.place(o, (x, y, cz))
            ctx.add(o, "road_chrome", uv_scale=3.0, smooth=35, wear=0.6)


def engine_hoist(ctx: K.Ctx) -> None:
    """Folding shop crane: splayed legs on casters, upright with gussets, telescoping boom raised by
    a bottle-jack ram with its pump handle, chain and hook -- holding the V8 pulled from a Guard
    truck. Worn: the engine let down onto a tyre, chain slack, paint flaking."""
    paint = "road_paint_orange"
    legs = []
    for sx in (-1, 1):
        leg = K.box(ctx.uid("leg"), (0.07, 1.45, 0.07), center=(0, -0.72, 0.1))
        K.place(leg, rot=(0, 0, sx * -7.5))
        K.place(leg, (sx * 0.14, 0.42, 0.0))
        legs.append(leg)
    rear = K.box("rear", (0.48, 0.08, 0.08), center=(0, 0.42, 0.1))
    for o in legs + [rear]:
        ctx.add(o, paint, uv_scale=1.0, patches=0.7, low=0.9, low_h=0.3)
    for (x, y) in ((-0.33, -0.98), (0.33, -0.98), (-0.2, 0.42), (0.2, 0.42)):
        _caster(ctx, x, y, 0.065, r=0.035, wheel_mat="road_steel_dark")
    up = K.box("upright", (0.09, 0.09, 1.3), center=(0, 0.42, 0.14 + 0.65))
    gus = [K.prism(ctx.uid("gusset"), [(0.0, 0.0), (0.3, 0.0), (0.0, 0.3)], 0.01, plane="YZ") for _ in range(2)]
    for k, g in enumerate(gus):
        K.place(g, rot=(0, 0, 180 if k else 0))
        K.place(g, (0.05 if k == 0 else -0.05, 0.42, 0.14))
    ctx.add(up, paint, uv_scale=1.0, patches=0.6)
    for g in gus:
        ctx.add(g, paint, uv_scale=1.0, patches=0.6)
    top = Vector((0, 0.42, 1.44))
    ang = 22.0 if not ctx.worn else 12.0
    d = Vector((0, -math.cos(math.radians(ang)), math.sin(math.radians(ang))))
    boom = K.box("boom", (0.08, 1.15, 0.08), center=(0, -0.575, 0))
    ext = K.box("boomext", (0.065, 0.55, 0.065), center=(0, -1.25, 0))
    for o in (boom, ext):
        # Raise the boom along d (a +X rotation would tip it down onto the engine).
        K.place(o, rot=(-ang, 0, 0))
        K.place(o, top)
    ctx.add(boom, paint, uv_scale=1.0, patches=0.6)
    ctx.add(ext, "road_paint_grey", uv_scale=1.0, patches=0.5)
    for k in range(4):
        hole = K.cyl(ctx.uid("pinhole"), 0.012, 0.08, segs=8, axis="X", center=top + d * (0.95 + k * 0.08))
        ctx.add(hole, "road_steel_dark", uv_scale=2.0)
    tip = top + d * 1.5
    # Ram from the upright (z 0.6) to the boom (~0.55 out).
    ra = Vector((0, 0.36, 0.62))
    rb = top + d * 0.55 + Vector((0, 0, -0.05))
    axis = (rb - ra).normalized()
    jack = K.cyl("jack", 0.045, 0.34, segs=12, center=(0, 0, 0.17))
    rodj = K.cyl("ramrod", 0.022, (rb - ra).length - 0.3, segs=10, center=(0, 0, 0.3 + ((rb - ra).length - 0.3) / 2))
    rot = Vector((0, 0, 1)).rotation_difference(axis).to_euler()
    for o in (jack, rodj):
        o.data.transform(Matrix.Translation(ra) @ rot.to_matrix().to_4x4())
        o.data.update()
    ctx.add(jack, "road_paint_red", uv="cyl", uv_scale=2.0, smooth=40, patches=0.5)
    ctx.add(rodj, "road_chrome", uv="cyl", uv_scale=2.0, smooth=40, wear=0.6)
    hand = K.tube("pumphandle", [ra + Vector((0.05, -0.02, 0.1)), ra + Vector((0.2, -0.15, 0.28)), ra + Vector((0.32, -0.25, 0.42))],
                  0.012, segs=6)
    ctx.add(hand, "road_chrome", uv_scale=2.0, wear=0.6)
    # Chain + hook.
    links = 8 if not ctx.worn else 11
    p = tip + Vector((0, 0, -0.06))
    for k in range(links):
        ring = K.lathe(ctx.uid("link"), [(0.022 + 0.006 * math.cos(a), 0.006 * math.sin(a)) for a in [i * math.tau / 6 for i in range(6)]],
                       segs=8, close_profile=True)
        K.map_verts(ring, lambda co: Vector((co.x, co.y * 1.6, co.z)))
        K.place(ring, rot=(90, 0, 90 if k % 2 else 0))
        sag = 0.0 if not ctx.worn else 0.02 * math.sin(k / links * math.pi)
        K.place(ring, p + Vector((0, sag, -k * 0.055)))
        ctx.add(ring, "road_steel", uv_scale=3.0, smooth=40, wear=0.8)
    hz = p.z - links * 0.055 - 0.03
    hook = K.tube("hook", [(0, 0, hz + 0.03), (0, 0, hz - 0.03), (0, -0.03, hz - 0.08), (0, -0.07, hz - 0.07),
                           (0, -0.08, hz - 0.03)], 0.011, segs=6)
    K.place(hook, (p.x, p.y, 0))
    ctx.add(hook, "road_steel_dark", uv_scale=2.0, wear=0.7)
    # Engine block (V8): block, heads, valve covers, oil pan, bell housing, exhaust manifolds.
    ez = hz - 0.42 if not ctx.worn else 0.32
    ey = p.y
    eng = []
    blk = K.box("block", (0.42, 0.62, 0.36), center=(0, 0, 0), bevel=0.02)
    pan = K.box("pan", (0.36, 0.5, 0.14), center=(0, 0.02, -0.25), bevel=0.02)
    bell = K.lathe("bell", [(0.0, 0.0), (0.22, 0.0), (0.25, 0.1), (0.0, 0.1)], segs=14)
    K.place(bell, rot=(90, 0, 0))
    K.place(bell, (0, 0.31, -0.04))
    eng += [(blk, "road_engine"), (pan, "road_engine"), (bell, "road_alu")]
    for sx in (-1, 1):
        head = K.box(ctx.uid("head"), (0.16, 0.58, 0.12), center=(0, 0, 0), bevel=0.012)
        cover = K.box(ctx.uid("vcover"), (0.13, 0.54, 0.06), center=(0, 0, 0.08), bevel=0.02)
        mani = K.box(ctx.uid("manifold"), (0.05, 0.5, 0.07), center=(sx * 0.1, 0, -0.05), bevel=0.01)
        for o in (head, cover, mani):
            K.place(o, rot=(0, sx * 42, 0))
            K.place(o, (sx * 0.2, 0, 0.2))
        eng += [(head, "road_engine"), (cover, "road_paint_orange"), (mani, "road_rust")]
    intake = K.box("intake", (0.18, 0.5, 0.08), center=(0, 0, 0.24), bevel=0.01)
    pulley = K.cyl("pulley", 0.08, 0.04, segs=12, axis="Y", center=(0, -0.34, -0.05))
    eng += [(intake, "road_alu"), (pulley, "road_steel_dark")]
    for o, m in eng:
        K.place(o, rot=(0, 0, 90))
        K.place(o, (0, ey, ez))
        if ctx.worn:
            K.lift_min(o)
        ctx.add(o, m, uv_scale=1.5, smooth=30, patches=0.6, low=0.4)
    if not ctx.worn:
        sling = K.tube("sling", [(-0.2, ey, ez + 0.28), (0.0, ey, hz - 0.04), (0.2, ey, ez + 0.28)], 0.01, segs=6)
        ctx.add(sling, "road_steel", uv_scale=2.0, wear=0.6)
    else:
        t = _tire("tyre_under", ro=0.31, rb=0.19, w=0.2, segs=14)
        K.place(t, (0, ey, 0.1))
        ctx.add(t, "road_tire", uv="cyl", uv_axis=2, uv_scale=1.0, smooth=50, patches=0.2)
    for o in ctx.parts:  # centre the leg footprint on the origin (PropDef collision box)
        o.data.transform(Matrix.Translation((0, 0.28, 0)))
        o.data.update()
    ctx.col_box((-0.42, -0.78, 0), (0.42, 0.78, 2.0))


def oil_drum(ctx: K.Ctx) -> None:
    """55-gallon motor-oil drum with rolling hoops and chimes, bungs, a rotary hand pump with crank
    and spout over a drip can, and an old oil stain on the floor. Worn: dented, rust bloom, a big
    stain. Destroyed: crushed in on one side and leaking a puddle."""
    R, H = 0.29, 0.88
    prof = [(0.0, 0.0), (R - 0.01, 0.0), (R, 0.012), (R, 0.03), (R - 0.004, 0.04), (R - 0.004, H * 0.32), (R + 0.006, H * 0.33),
            (R + 0.006, H * 0.35), (R - 0.004, H * 0.36), (R - 0.004, H * 0.64), (R + 0.006, H * 0.65), (R + 0.006, H * 0.67),
            (R - 0.004, H * 0.68), (R - 0.004, H - 0.04), (R, H - 0.03), (R, H - 0.012), (R - 0.01, H), (R - 0.02, H - 0.01),
            (0.0, H - 0.01)]
    drum = K.lathe("drum", prof, segs=20)
    if ctx.worn:
        dr = ctx.drnd("d")
        for _ in range(2 if not ctx.destroyed else 4):
            a = dr.uniform(0, math.tau)
            K.dent(drum, (math.cos(a) * R, math.sin(a) * R, dr.uniform(0.2, 0.7)), dr.uniform(0.1, 0.18), dr.uniform(0.02, 0.05))
    if ctx.destroyed:
        K.dent(drum, (0.0, -R, 0.45), 0.35, 0.16)
    ctx.add(drum, "road_paint_drum", uv="cyl", uv_scale=1.0, smooth=35, patches=0.7, low=0.8, low_h=0.35)
    b1 = K.cyl("bung1", 0.035, 0.016, segs=6, center=(0.15, 0.0, H - 0.002))
    b2 = K.cyl("bung2", 0.02, 0.014, segs=6, center=(-0.17, 0.05, H - 0.002))
    ctx.add(b1, "road_steel", uv_scale=2.0, wear=0.8)
    ctx.add(b2, "road_steel", uv_scale=2.0, wear=0.8)
    pb = K.cyl("pumpbody", 0.055, 0.12, segs=12, center=(0.15, 0.0, H + 0.16))
    pt = K.cyl("pumptube", 0.02, 0.12, segs=8, center=(0.15, 0.0, H + 0.06))
    crank = K.tube("crank", [(0.15, 0.06, H + 0.16), (0.15, 0.08, H + 0.16), (0.15, 0.08, H + 0.31)], 0.008, segs=6)
    cknob = K.cyl("cknob", 0.014, 0.06, segs=8, axis="Y", center=(0.15, 0.11, H + 0.31))
    spout = K.tube("spout", [(0.15, -0.05, H + 0.18), (0.15, -0.16, H + 0.2), (0.15, -0.24, H + 0.14), (0.15, -0.26, H + 0.06)],
                   0.012, segs=8)
    ctx.add(pb, "road_paint_red", uv="cyl", uv_scale=2.0, smooth=40, patches=0.6)
    ctx.add(pt, "road_steel", uv_scale=2.0)
    ctx.add(crank, "road_steel", uv_scale=2.0, wear=0.6)
    ctx.add(cknob, "road_plastic_black", uv_scale=2.0)
    ctx.add(spout, "road_steel", uv_scale=2.0, wear=0.6)
    can = K.lathe("dripcan", [(0.0, 0.0), (0.07, 0.0), (0.07, 0.12), (0.065, 0.13), (0.0, 0.13)], segs=10)
    K.place(can, (0.18, -0.42, 0.0))
    ctx.add(can, "road_steel", uv="cyl", uv_scale=2.0, smooth=40, patches=0.8)
    rs = 0.45 if ctx.clean else (0.7 if not ctx.destroyed else 0.95)
    stain = K.cyl("stain", rs, 0.003, segs=18, center=(0.08, -0.25, 0.0015))
    K.map_verts(stain, lambda co: Vector((co.x * 1.2, co.y * 0.9, co.z)))
    ctx.add(stain, "road_oil_dark", uv_scale=1.0, patches=0.0, edge=0.0, ao=False)
    ctx.col_box((-R - 0.01, -R - 0.01, 0), (R + 0.01, R + 0.01, H + 0.3))


def oil_shelf(ctx: K.Ctx) -> None:
    """Steel shelving of motor oil: lettered quart bottles in four grades, gallon jugs, filter boxes,
    spray cans, rags. Worn: half sold out, bottles knocked over and on the floor. Destroyed: a shelf
    collapsed at one end, stock avalanched onto the floor."""
    L, Dp, H = 1.2, 0.42, 1.8
    for sx in (-1, 1):
        for sy in (-1, 1):
            p = K.box(ctx.uid("post"), (0.035, 0.035, H), center=(sx * (L / 2 - 0.018), sy * (Dp / 2 - 0.018), H / 2))
            ctx.add(p, "road_paint_grey", uv_scale=2.0, patches=0.6, low=0.8)
    shelves = (0.12, 0.55, 0.98, 1.41, 1.78)
    r = ctx.rnd("stock")
    dr = ctx.drnd("gone")
    labels = [_rect(ATLAS_GAS, "oil_label", (k / 4, 0.0, (k + 1) / 4, 1.0)) for k in range(4)]
    for si, z in enumerate(shelves):
        sh = K.box(ctx.uid("shelf"), (L - 0.02, Dp - 0.02, 0.02), center=(0, 0, z))
        lip = K.box(ctx.uid("lip"), (L - 0.02, 0.01, 0.04), center=(0, -Dp / 2 + 0.005, z + 0.01))
        grp = [sh, lip]
        if ctx.destroyed and si == 2:
            for o in grp:
                o.data.transform(Matrix.Translation((L / 2, 0, z)) @ K.rot_matrix((0, 18, 0)) @ Matrix.Translation((-L / 2, 0, -z)))
                o.data.update()
        for o in grp:
            ctx.add(o, "road_paint_grey", uv_scale=1.0, patches=0.6)
        if si == 4:
            break
        top = z + 0.01
        if si in (0, 1):
            # Quart bottles in rows of 10 x 2.
            for row in range(2):
                for k in range(10):
                    if ctx.worn and dr.random() < 0.45:
                        continue
                    g = (k // 3 + si) % 4
                    b = K.box(ctx.uid("quart"), (0.095, 0.06, 0.2), center=(0, 0, 0.1), bevel=0.01)
                    K.uv_planar(b, 1, rect=labels[g])
                    capq = K.cyl(ctx.uid("qcap"), 0.02, 0.035, segs=6, center=(0.02, 0, 0.215))
                    loc = (-L / 2 + 0.08 + k * 0.105, -0.1 + row * 0.18, top)
                    for o in (b, capq):
                        K.place(o, rot=(0, 0, r.uniform(-4, 4)))
                        K.place(o, loc)
                    ctx.add(b, GAS, uv=None, smooth=30, patches=0.2, wear=0.4)
                    ctx.add(capq, ["road_plastic_yellow", "road_plastic_red", "road_plastic_black"][g % 3], uv_scale=2.0, smooth=40)
        elif si == 2:
            for k in range(5):
                if ctx.worn and dr.random() < 0.4:
                    continue
                jug = K.box(ctx.uid("jug"), (0.16, 0.12, 0.27), center=(0, 0, 0.135), bevel=0.02, bevel_segs=2)
                hnd = K.tube(ctx.uid("jughandle"), [(0.04, 0.0, 0.2), (0.06, 0.0, 0.3), (0.0, 0.0, 0.31), (-0.04, 0.0, 0.27)],
                             0.012, segs=6)
                for o in (jug, hnd):
                    K.place(o, (-L / 2 + 0.13 + k * 0.23, 0.0, top))
                ctx.add(jug, "road_plastic_jug", uv_scale=1.5, smooth=35, patches=0.3)
                ctx.add(hnd, "road_plastic_jug", uv_scale=2.0, smooth=35)
        else:
            for k in range(6):
                if ctx.worn and dr.random() < 0.4:
                    continue
                fb = K.box(ctx.uid("filterbox"), (0.11, 0.11, 0.14), center=(-L / 2 + 0.1 + k * 0.17, r.uniform(-0.08, 0.05), top + 0.07))
                ctx.add(fb, "road_cardboard", uv_scale=2.0, patches=0.3)
            for k in range(4):
                sc = K.lathe(ctx.uid("spray"), [(0.0, 0.0), (0.033, 0.0), (0.033, 0.17), (0.02, 0.2), (0.0, 0.205)], segs=8)
                K.place(sc, (0.3 + k * 0.07, 0.12, top))
                ctx.add(sc, ["can_red", "can_blue", "can_green", "can_alu"][k], uv="cyl", uv_scale=1.0, smooth=40)
    if ctx.worn:
        n = 6 if not ctx.destroyed else 14
        for i in range(n):
            g = i % 4
            b = K.box(ctx.uid("fallen"), (0.095, 0.06, 0.2), center=(0, 0, 0.1), bevel=0.012)
            K.uv_planar(b, 1, rect=labels[g])
            K.place(b, rot=(90, 0, dr.uniform(0, 360)))
            K.lift_min(b)
            K.place(b, (dr.uniform(-0.6, 0.6), dr.uniform(-0.75, -0.25), 0.0))
            ctx.add(b, GAS, uv=None, smooth=30, patches=0.2)
        puddle = K.cyl("oilpuddle", 0.35, 0.003, segs=16, center=(0.1, -0.5, 0.0015))
        ctx.add(puddle, "road_oil_dark", uv_scale=1.0, patches=0.0, edge=0.0, ao=False)
    ctx.col_box((-L / 2, -Dp / 2, 0), (L / 2, Dp / 2, H))


def rollup_door(ctx: K.Ctx) -> None:
    """Garage bay roll-up door, down and locked: 3 m corrugated steel curtain in side guides,
    bottom bar with a rubber seal, lift handle, a padlocked hasp at the floor, header plate outside
    and the drum hood inside (+Y). Origin on the wall line at the bottom centre of the opening.
    Worn: dents, rust. Destroyed: rammed from outside -- bowed in, a slat torn open (still shut)."""
    Wd, Hd = 3.0, 2.45
    n = 33
    outline = []
    for k in range(n + 1):
        z = Hd * k / n
        outline.append((-0.008 if k % 2 == 0 else -0.018, z))
    back = [(0.004 if k % 2 == 0 else -0.006, Hd * k / n) for k in range(n + 1)]
    poly = [(y, z) for (y, z) in outline] + [(y, z) for (y, z) in reversed(back)]
    cur = K.prism("curtain", poly, Wd, plane="YZ")
    K.subdivide(cur, 1)
    if ctx.worn:
        dr = ctx.drnd("d")
        for _ in range(3):
            K.dent(cur, (dr.uniform(-1.2, 1.2), -0.02, dr.uniform(0.3, 1.8)), dr.uniform(0.2, 0.35), 0.03, direction=(0, 1, 0))
    if ctx.destroyed:
        K.dent(cur, (0.4, -0.02, 0.6), 0.9, 0.22, direction=(0, 1, 0))
        K.jagged_hole(cur, (0.7, 0.0, 0.42), 0.22, ctx.drnd("h").randint(0, 999), axis=1)
    ctx.add(cur, "road_paint_white", uv_scale=1.0, patches=0.6, low=0.9, low_h=0.6, long_axis=0)
    bar = K.box("bottombar", (Wd - 0.02, 0.06, 0.05), center=(0, -0.006, 0.025))
    seal = K.box("seal", (Wd - 0.02, 0.03, 0.012), center=(0, -0.006, 0.006))
    ctx.add(bar, "road_alu", uv_scale=2.0, wear=0.8, patches=0.5)
    ctx.add(seal, "road_rubber", uv_scale=2.0)
    for s in (-1, 1):
        hdl = K.box(ctx.uid("handle"), (0.14, 0.03, 0.03), center=(0, s * 0.045, 0.32), bevel=0.006)
        ctx.add(hdl, "road_steel", uv_scale=2.0, wear=0.8)
    hasp = K.box("hasp", (0.04, 0.012, 0.09), center=(1.15, -0.04, 0.07))
    eye = K.box("eye", (0.05, 0.03, 0.03), center=(1.15, -0.05, 0.015))
    ctx.add(hasp, "road_steel", uv_scale=2.0, wear=0.9)
    ctx.add(eye, "road_steel_dark", uv_scale=2.0)
    _padlock(ctx, Vector((1.15, -0.07, 0.06)), s=1.3)
    for s in (-1, 1):
        g = K.box(ctx.uid("guide"), (0.08, 0.12, 2.8), center=(s * (Wd / 2 + 0.03), 0.0, 1.4))
        ctx.add(g, "road_steel", uv_scale=1.0, patches=0.6, low=0.8)
    header = K.box("header", (Wd + 0.2, 0.02, 0.35), center=(0, -0.07, Hd + 0.175))
    ctx.add(header, "road_paint_white", uv_scale=1.0, patches=0.6)
    hood = K.box("hood", (Wd + 0.2, 0.42, 0.42), center=(0, 0.24, Hd + 0.2), bevel=0.02)
    ctx.add(hood, "road_steel", uv_scale=1.0, patches=0.5)
    ctx.col_box((-Wd / 2 - 0.08, -0.08, 0), (Wd / 2 + 0.08, 0.08, 2.8))


def rollup_door_open(ctx: K.Ctx) -> None:
    """The same bay door rolled up: curtain coiled on its drum in the hood, guides, header, the
    bottom bar tucked under the hood and the pull rope hanging. No collision (drive through)."""
    Wd, Hd = 3.0, 2.45
    drum = K.cyl("coil", 0.2, Wd - 0.04, segs=16, axis="X", center=(0, 0.22, Hd + 0.17))
    ctx.add(drum, "road_paint_white", uv="cyl", uv_axis=0, uv_scale=1.0, smooth=40, patches=0.6)
    for k in range(5):
        ring = K.cyl(ctx.uid("ring"), 0.205, 0.01, segs=16, axis="X", center=(-1.2 + k * 0.6, 0.22, Hd + 0.17))
        ctx.add(ring, "road_steel_dark", uv_scale=2.0)
    bar = K.box("bottombar", (Wd - 0.02, 0.06, 0.05), center=(0, 0.0, Hd - 0.02))
    ctx.add(bar, "road_alu", uv_scale=2.0, wear=0.8)
    rope = K.tube("rope", [(0.0, -0.01, Hd - 0.04), (0.02, -0.02, 2.0), (0.0, -0.02, 1.6)], 0.008, segs=6)
    ctx.add(rope, "road_rope", uv_scale=3.0, smooth=40)
    for s in (-1, 1):
        g = K.box(ctx.uid("guide"), (0.08, 0.12, 2.8), center=(s * (Wd / 2 + 0.03), 0.0, 1.4))
        ctx.add(g, "road_steel", uv_scale=1.0, patches=0.6, low=0.8)
    header = K.box("header", (Wd + 0.2, 0.02, 0.35), center=(0, -0.07, Hd + 0.175))
    ctx.add(header, "road_paint_white", uv_scale=1.0, patches=0.6)
    hood = K.box("hood", (Wd + 0.2, 0.46, 0.46), center=(0, 0.24, Hd + 0.2), bevel=0.02)
    K.delete_faces(hood, lambda c, n: n.z < -0.9)
    ctx.add(hood, "road_steel", uv_scale=1.0, patches=0.5)
    ctx.col_box((-Wd / 2 - 0.08, -0.08, 2.4), (Wd / 2 + 0.08, 0.5, 2.8))


def workbench(ctx: K.Ctx) -> None:
    """Heavy garage workbench: angle-iron frame, oil-soaked laminated top, plywood under-shelf with
    a car battery and coffee cans of bolts, pegboard backboard with wrenches, hammer, screwdrivers
    and a hacksaw, bench vise on the right, bench grinder at the back left, a trouble light and
    rags. Worn: tools missing from the board (outlines only), rust, a spill."""
    L, Dp = 1.8, 0.7
    r = ctx.rnd("bench")
    for sx in (-1, 1):
        for sy in (-1, 1):
            leg = K.box(ctx.uid("leg"), (0.05, 0.05, 0.86), center=(sx * (L / 2 - 0.05), sy * (Dp / 2 - 0.05), 0.43))
            ctx.add(leg, "road_paint_grey", uv_scale=2.0, patches=0.6, low=0.9, low_h=0.3)
    for z in (0.18, 0.84):
        for sy in (-1, 1):
            rail = K.box(ctx.uid("rail"), (L - 0.1, 0.04, 0.04), center=(0, sy * (Dp / 2 - 0.05), z))
            ctx.add(rail, "road_paint_grey", uv_scale=2.0, patches=0.6)
    shelf = K.box("shelf", (L - 0.12, Dp - 0.1, 0.02), center=(0, 0, 0.2))
    ctx.add(shelf, "road_plywood", uv_scale=1.0, patches=0.5)
    top = K.box("top", (L, Dp, 0.05), center=(0, 0, 0.885), bevel=0.006)
    ctx.add(top, "road_wood_bench", uv_scale=1.0, patches=0.7, long_axis=0)
    board = K.box("board", (L - 0.04, 0.02, 0.62), center=(0, Dp / 2 - 0.02, 0.91 + 0.31))
    ctx.add(board, "road_pegboard", uv_scale=1.0, patches=0.3)
    by = Dp / 2 - 0.035
    tools = [(-0.7, 1.35, "wrench", 0.22), (-0.6, 1.35, "wrench", 0.19), (-0.5, 1.35, "wrench", 0.16),
             (-0.2, 1.3, "hammer", 0.0), (0.05, 1.3, "driver", 0.0), (0.12, 1.3, "driver", 0.0), (0.19, 1.3, "driver", 0.0),
             (0.5, 1.28, "saw", 0.0)]
    dr = ctx.drnd("gone")
    for (x, z, kind, L2) in tools:
        missing = ctx.worn and dr.random() < 0.45
        if missing:
            ghost = K.box(ctx.uid("ghost"), (0.04 if kind != "saw" else 0.4, 0.002, 0.22), center=(x, by + 0.008, z))
            ctx.add(ghost, "road_oil_dark", uv_scale=1.0, patches=0.0, edge=0.0)
            continue
        pegs = K.cyl(ctx.uid("peg"), 0.004, 0.05, segs=4, axis="Y", center=(x, by - 0.01, z + 0.12))
        ctx.add(pegs, "road_steel", uv_scale=2.0)
        if kind == "wrench":
            o = K.box(ctx.uid("wrench"), (0.018, 0.006, L2), center=(x, by - 0.01, z), bevel=0.002)
            e = K.cyl(ctx.uid("wrend"), 0.018, 0.007, segs=8, axis="Y", center=(x, by - 0.01, z + L2 / 2))
            ctx.add(o, "road_chrome", uv_scale=3.0, wear=0.6)
            ctx.add(e, "road_chrome", uv_scale=3.0, wear=0.6)
        elif kind == "hammer":
            h = K.cyl(ctx.uid("hhandle"), 0.013, 0.3, segs=8, center=(x, by - 0.02, z - 0.05))
            hd = K.box(ctx.uid("hhead"), (0.11, 0.028, 0.028), center=(x, by - 0.02, z + 0.11), bevel=0.004)
            ctx.add(h, "road_wood_bench", uv_scale=3.0, smooth=40)
            ctx.add(hd, "road_steel_dark", uv_scale=3.0, wear=0.8)
        elif kind == "driver":
            h = K.cyl(ctx.uid("dhandle"), 0.014, 0.1, segs=8, center=(x, by - 0.02, z + 0.05))
            sh = K.cyl(ctx.uid("dshaft"), 0.004, 0.14, segs=6, center=(x, by - 0.02, z - 0.07))
            ctx.add(h, r.choice(["road_plastic_red", "road_plastic_yellow", "road_plastic_blue"]), uv_scale=3.0, smooth=40)
            ctx.add(sh, "road_chrome", uv_scale=3.0)
        else:
            fr = K.tube(ctx.uid("sawframe"), [(x - 0.2, by - 0.015, z), (x - 0.2, by - 0.015, z + 0.1), (x + 0.2, by - 0.015, z + 0.1),
                                              (x + 0.2, by - 0.015, z)], 0.006, segs=6)
            bl = K.box(ctx.uid("sawblade"), (0.4, 0.002, 0.012), center=(x, by - 0.015, z))
            ctx.add(fr, "road_paint_blue", uv_scale=3.0)
            ctx.add(bl, "road_steel", uv_scale=3.0)
    # Bench vise.
    vx, vy = L / 2 - 0.2, -Dp / 2 + 0.1
    vb = K.box("visebody", (0.12, 0.22, 0.09), center=(vx, vy + 0.03, 0.955), bevel=0.01)
    jaw1 = K.box("jaw1", (0.15, 0.03, 0.08), center=(vx, vy - 0.08, 0.99), bevel=0.006)
    jaw2 = K.box("jaw2", (0.15, 0.03, 0.08), center=(vx, vy - 0.03, 0.99), bevel=0.006)
    screw = K.cyl("visescrew", 0.012, 0.22, segs=8, axis="Y", center=(vx, vy - 0.12, 0.95))
    tbar = K.cyl("visebar", 0.008, 0.22, segs=6, axis="X", center=(vx, vy - 0.22, 0.95))
    for o in (vb, jaw1, jaw2):
        ctx.add(o, "road_paint_blue", uv_scale=2.0, patches=0.7)
    ctx.add(screw, "road_steel", uv_scale=2.0)
    ctx.add(tbar, "road_chrome", uv_scale=2.0)
    # Bench grinder.
    gx, gy = -L / 2 + 0.3, Dp / 2 - 0.2
    mot = K.cyl("gmotor", 0.07, 0.18, segs=12, axis="X", center=(gx, gy, 0.99))
    gb = K.box("gbase", (0.16, 0.12, 0.04), center=(gx, gy, 0.93))
    ctx.add(mot, "road_paint_grey", uv="cyl", uv_axis=0, uv_scale=2.0, smooth=40)
    ctx.add(gb, "road_paint_grey", uv_scale=2.0)
    for s in (-1, 1):
        wh = K.cyl(ctx.uid("gwheel"), 0.075, 0.025, segs=14, axis="X", center=(gx + s * 0.13, gy, 0.99))
        gd = K.cyl(ctx.uid("gguard"), 0.085, 0.04, segs=14, axis="X", center=(gx + s * 0.13, gy, 0.99))
        K.cut_plane(gd, (0, gy - 0.02, 0), (0, -1, 0), keep="below")
        ctx.add(wh, "road_concrete", uv_scale=2.0)
        ctx.add(gd, "road_paint_grey", uv_scale=2.0)
    # Clutter on the top and the shelf.
    can = K.lathe("boltcan", [(0.0, 0.0), (0.06, 0.0), (0.06, 0.13), (0.0, 0.13)], segs=10, cap_top=False)
    K.place(can, (0.1, -0.1, 0.91))
    ctx.add(can, "can_alu", uv="cyl", uv_scale=2.0, smooth=40, patches=0.6)
    oc = K.lathe("oilcan", [(0.0, 0.0), (0.05, 0.0), (0.05, 0.05), (0.02, 0.09), (0.006, 0.2), (0.0, 0.2)], segs=10)
    K.place(oc, (-0.3, -0.15, 0.91))
    ctx.add(oc, "road_paint_red", uv="cyl", uv_scale=2.0, smooth=40)
    rag = K.blob("rag", 0.09, subdiv=2, scale=(1.4, 1.0, 0.25), rough=0.3, seed=r.randint(0, 999))
    K.place(rag, (-0.05, 0.1, 0.92))
    ctx.add(rag, "road_rag", uv_scale=2.0, smooth=60, patches=0.0)
    bat = K.box("battery", (0.3, 0.17, 0.2), center=(0.4, 0.0, 0.31), bevel=0.01)
    ctx.add(bat, "road_plastic_black", uv_scale=2.0, patches=0.3)
    for s in (-1, 1):
        post = K.cyl(ctx.uid("bpost"), 0.012, 0.025, segs=8, center=(0.4 + s * 0.1, -0.05, 0.42))
        ctx.add(post, "road_lead", uv_scale=2.0)
    lamp = K.lathe("troublelight", [(0.0, 0.0), (0.035, 0.0), (0.045, 0.1), (0.04, 0.18), (0.0, 0.2)], segs=8)
    K.place(lamp, rot=(0, 80, 20))
    K.place(lamp, (-0.55, -0.15, 0.95))
    ctx.add(lamp, "road_lamp_cage", uv_scale=2.0, smooth=40)
    cord = K.tube("lampcord", [(-0.65, -0.13, 0.94), (-0.8, -0.2, 0.92), (-0.88, -0.32, 0.6), (-0.9, -0.38, 0.05)], 0.006, segs=5)
    ctx.add(cord, "road_plastic_yellow", uv_scale=2.0, smooth=40)
    if ctx.worn:
        sp = K.cyl("spill", 0.3, 0.003, segs=14, center=(-0.2, -0.6, 0.0015))
        ctx.add(sp, "road_oil_dark", uv_scale=1.0, patches=0.0, edge=0.0, ao=False)
    ctx.col_box((-L / 2, -Dp / 2, 0), (L / 2, Dp / 2, 0.91))


def creeper(ctx: K.Ctx) -> None:
    """Mechanic's creeper: padded vinyl deck with a headrest on a tube frame and six casters.
    Worn: vinyl split, a caster gone (tilted)."""
    Lc, Wc = 1.0, 0.44
    for sx in (-1, 1):
        rail = K.tube(ctx.uid("rail"), [(sx * Wc / 2, -Lc / 2, 0.1), (sx * Wc / 2, Lc / 2, 0.1)], 0.011, segs=8)
        ctx.add(rail, "road_paint_red", uv_scale=2.0, patches=0.6)
    for y in (-Lc / 2 + 0.06, 0.0, Lc / 2 - 0.06):
        for sx in (-1, 1):
            if ctx.worn and y == 0.0 and sx == 1:
                continue
            _caster(ctx, sx * (Wc / 2 - 0.04), y, 0.095, r=0.03)
    deck = K.box("deck", (Wc - 0.04, Lc - 0.04, 0.025), center=(0, 0, 0.115))
    ctx.add(deck, "road_plywood", uv_scale=1.0, patches=0.5)
    pad = K.box("pad", (Wc - 0.06, Lc - 0.24, 0.035), center=(0, -0.07, 0.145), bevel=0.012, bevel_segs=2)
    head = K.box("headrest", (Wc - 0.12, 0.18, 0.06), center=(0, Lc / 2 - 0.12, 0.16), bevel=0.02, bevel_segs=2)
    ctx.add(pad, "road_vinyl_black", uv_scale=2.0, smooth=40, patches=0.3)
    ctx.add(head, "road_vinyl_black", uv_scale=2.0, smooth=40, patches=0.3)
    if ctx.worn:
        for o in ctx.parts:
            o.data.transform(K.rot_matrix((0, 2.5, 0)))
            o.data.update()
    ctx.col_box((-Wc / 2, -Lc / 2, 0), (Wc / 2, Lc / 2, 0.19))


def cooler(ctx: K.Ctx) -> None:
    """Three-door reach-in cooler for the kiosk's back wall: black frame and mullions, glass doors
    with handle bars, wire shelves of soda cans and bottles behind the glass, a header with a dead
    strip light, kick grille. Worn: a door's glass smashed, shelves half emptied, bottles on the
    floor. Destroyed: two doors smashed, a door hanging, the stock spilled."""
    W, Dp, H = 2.3, 0.8, 2.1
    cab = K.box("cab", (W, Dp - 0.04, H), center=(0, 0.02, H / 2), bevel=0.01)
    K.delete_faces(cab, lambda c, n: n.y < -0.9)
    ctx.add(cab, "road_paint_black", uv_scale=1.0, patches=0.5)
    liner = K.box("liner", (W - 0.06, 0.02, H - 0.4), center=(0, Dp / 2 - 0.06, 1.05))
    ctx.add(liner, "road_paint_white", uv_scale=1.0, patches=0.4)
    header = K.box("header", (W, 0.06, 0.28), center=(0, -Dp / 2 + 0.03, H - 0.14))
    ctx.add(header, "road_paint_black", uv_scale=1.0, patches=0.4)
    strip = K.box("strip", (W - 0.2, 0.01, 0.05), center=(0, -Dp / 2 - 0.003, H - 0.14))
    ctx.add(strip, "road_lens_frost", uv_scale=1.0, patches=0.0, ao=False)
    kick = K.box("kick", (W, 0.04, 0.16), center=(0, -Dp / 2 + 0.06, 0.08))
    ctx.add(kick, "road_steel_dark", uv_scale=1.0, patches=0.5)
    _louvres(ctx, -0.9, 0.9, 0.02, 0.14, -Dp / 2 + 0.035, 4, "road_steel_dark")
    r = ctx.rnd("stock")
    dr = ctx.drnd("gone")
    dw = W / 3
    shelves = (0.3, 0.68, 1.06, 1.44)
    for d in range(3):
        x0 = -W / 2 + dw * d
        cx = x0 + dw / 2
        for z in shelves:
            sh = K.box(ctx.uid("shelf"), (dw - 0.06, Dp - 0.2, 0.012), center=(cx, 0.05, z))
            ctx.add(sh, "road_steel", uv_scale=2.0, patches=0.4)
            for k in range(5):
                if ctx.worn and dr.random() < (0.5 if not ctx.destroyed else 0.7):
                    continue
                x = x0 + 0.1 + k * (dw - 0.2) / 4
                if (d + int(z * 10)) % 2:
                    o = K.lathe(ctx.uid("bottle"), [(0.0, 0.0), (0.035, 0.0), (0.035, 0.17), (0.014, 0.23), (0.014, 0.27), (0.0, 0.27)],
                                segs=7)
                    K.place(o, (x, -0.15, z + 0.006))
                    ctx.add(o, r.choice(["glass_brown", "glass_green", "road_plastic_jug"]), uv="cyl", uv_scale=1.0, smooth=40,
                            patches=0.0)
                else:
                    for j in range(2):
                        c = K.cyl(ctx.uid("can"), 0.033, 0.122, segs=7, center=(x, -0.15 + j * 0.08, z + 0.067))
                        ctx.add(c, r.choice(["can_red", "can_blue", "can_green", "can_alu"]), uv="cyl", uv_scale=1.0, smooth=40,
                                patches=0.0)
        # Door: frame, glass, handle.
        smashed = (ctx.worn and d == 1) or (ctx.destroyed and d == 2)
        hang = ctx.destroyed and d == 0
        fr = []
        for (fx, fz, fw, fh) in ((cx, 0.2, dw - 0.02, 0.05), (cx, H - 0.31, dw - 0.02, 0.05), (x0 + 0.03, 1.07, 0.05, 1.75),
                                 (x0 + dw - 0.03, 1.07, 0.05, 1.75)):
            fr.append(K.box(ctx.uid("dframe"), (fw, 0.05, fh), center=(fx, -Dp / 2 - 0.02, fz)))
        glass = K.box(ctx.uid("dglass"), (dw - 0.1, 0.008, 1.7), center=(cx, -Dp / 2 - 0.02, 1.07), cuts=(3, 0, 6))
        if smashed:
            K.jagged_hole(glass, (cx + 0.05, -Dp / 2 - 0.02, 1.1), 0.36, dr.randint(0, 999), axis=1)
        handle = K.box(ctx.uid("dhandle"), (0.025, 0.04, 0.6), center=(x0 + dw - 0.09, -Dp / 2 - 0.07, 1.1), bevel=0.006)
        grp = fr + [glass, handle]
        if hang:
            hx = x0 + 0.03
            for o in grp:
                o.data.transform(Matrix.Translation((hx, -Dp / 2, 0)) @ K.rot_matrix((0, 6, -75)) @ Matrix.Translation((-hx, Dp / 2, 0)))
                o.data.update()
        for o in fr:
            ctx.add(o, "road_paint_black", uv_scale=1.0, patches=0.4)
        ctx.add(glass, "road_glass", uv_scale=1.0, patches=0.0, ao=False)
        ctx.add(handle, "road_chrome", uv_scale=2.0, wear=0.5)
    if ctx.worn:
        n = 5 if not ctx.destroyed else 12
        for i in range(n):
            b = P.bottle(ctx.uid("floorbottle"), dr, broken=dr.random() < 0.5)
            K.place(b, rot=(90, 0, dr.uniform(0, 360)))
            K.lift_min(b)
            K.place(b, (dr.uniform(-1.0, 1.0), dr.uniform(-1.2, -0.55), 0))
            ctx.add(b, dr.choice(["glass_brown", "glass_green"]), uv="cyl", uv_scale=1.0, smooth=50, patches=0.0)
        P.add_litter(ctx, dr, 6 if not ctx.destroyed else 10, extent=(0.9, 0.3), center=(0, -0.85), kinds=("can", "can", "paper"))
    ctx.col_box((-W / 2, -Dp / 2 - 0.05, 0), (W / 2, Dp / 2, H))


# ============================================================================================
# Pylon signs
# ============================================================================================

def sign_gas(ctx: K.Ctx) -> None:
    """Roadside price pylon: two square posts on footings, the double-faced CORDON brand cabinet on
    top and the price board under it (aluminium frames, end caps, conduit, service rungs). Worn:
    a brand face smashed open on the road side -- fluorescent tubes showing -- and the price board
    hanging crooked. Destroyed: the brand cabinet face gone on both sides, price board dropped to one
    corner, a post buckled."""
    span = 2.0
    r = ctx.drnd("sign")
    posts = []
    for sx in (-1, 1):
        ft = K.box(ctx.uid("footing"), (0.55, 0.55, 0.25), center=(sx * span / 2, 0, 0.125), bevel=0.02)
        ctx.add(ft, "road_concrete", uv_scale=1.0, patches=0.6, edge=1.2)
        p = K.box(ctx.uid("post"), (0.22, 0.22, 6.35), center=(sx * span / 2, 0, 0.25 + 3.175), bevel=0.01, cuts=(0, 0, 6))
        posts.append(p)
    for z in (1.0, 1.4, 1.8, 2.2, 2.6, 3.0, 3.4):
        rung = K.cyl(ctx.uid("rung"), 0.012, 0.26, segs=6, axis="Y", center=(span / 2 + 0.13, 0, z))
        ctx.add(rung, "road_steel", uv_scale=2.0, wear=0.8)
    conduit = K.cyl("conduit", 0.022, 3.9, segs=8, center=(-span / 2, 0.14, 0.25 + 1.95))
    ctx.add(conduit, "road_steel", uv_scale=2.0, patches=0.5)
    # Brand cabinet.
    bz = 5.75
    cab = K.box("brandcab", (2.5, 0.34, 0.86), center=(0, 0, bz), bevel=0.012)
    capb = K.box("brandcap", (2.58, 0.4, 0.06), center=(0, 0, bz + 0.46), bevel=0.01)
    ctx.add(cab, "road_paint_green", uv_scale=1.0, patches=0.5)
    ctx.add(capb, "road_paint_green", uv_scale=1.0, patches=0.6, edge=1.2)
    brand = _rect(ATLAS_GAS, "gas_brand")
    for s in (-1, 1):
        y = s * 0.172
        broken = (ctx.worn and s < 0) or ctx.destroyed
        if ctx.destroyed:
            tubes = []
            for k in range(4):
                tb = K.cyl(ctx.uid("tube"), 0.016, 2.2, segs=8, axis="X", center=(0, s * 0.08, bz - 0.3 + k * 0.2))
                ctx.add(tb, "road_lens_frost", uv_scale=1.0, patches=0.0, ao=False)
            continue
        f = _face(ctx, ctx.uid("brandface"), 2.4, 0.8, brand, GAS, (0, y, bz), 0.0 if s < 0 else 180.0, nu=12, nv=4)
        if broken:
            K.jagged_hole(f, (0.55, y, bz - 0.05), 0.38, r.randint(0, 999), axis=1)
            for k in range(4):
                tb = K.cyl(ctx.uid("tube"), 0.016, 2.2, segs=8, axis="X", center=(0, s * 0.1, bz - 0.3 + k * 0.2))
                ctx.add(tb, "road_lens_frost", uv_scale=1.0, patches=0.0, ao=False)
        for (x, z, w, h) in ((0, bz + 0.41, 2.46, 0.03), (0, bz - 0.41, 2.46, 0.03), (-1.22, bz, 0.03, 0.85), (1.22, bz, 0.03, 0.85)):
            fr = K.box(ctx.uid("frame"), (w, 0.02, h), center=(x, y + s * 0.008, z))
            ctx.add(fr, "road_alu", uv_scale=2.0, wear=0.6)
    # Price board cabinet.
    pz = 4.7
    pcab = K.box("pricecab", (2.5, 0.28, 1.26), center=(0, 0, 0), bevel=0.012)
    pparts = [pcab]
    prices = _rect(ATLAS_GAS, "gas_prices")
    pfaces = []
    for s in (-1, 1):
        o = K.quad_sheet(ctx.uid("priceface"), (-1.2, 0, -0.6), (1.2, 0, -0.6), (1.2, 0, 0.6), (-1.2, 0, 0.6), 8, 4)
        K.uv_planar(o, 1, rect=prices)
        K.place(o, (0, 0, 0), (0, 0, 0.0 if s < 0 else 180.0))
        K.place(o, (0, s * 0.143, 0))
        pfaces.append(o)
    hangers = [K.cyl(ctx.uid("hanger"), 0.012, 0.42, segs=6, center=(sx * 0.9, 0, 0.84)) for sx in (-1, 1)]
    tilt = None
    if ctx.worn:
        tilt = (0, 7, 0) if not ctx.destroyed else (0, 24, 0)
    for o in pparts + pfaces + hangers:
        if tilt:
            o.data.transform(Matrix.Translation((-0.9, 0, 0.63)) @ K.rot_matrix(tilt) @ Matrix.Translation((0.9, 0, -0.63)))
            o.data.update()
        K.place(o, (0, 0, pz))
    ctx.add(pcab, "road_paint_green", uv_scale=1.0, patches=0.5)
    for o in pfaces:
        ctx.add(o, GAS, uv=None, wear=0.6, patches=0.35)
    for o in hangers:
        ctx.add(o, "road_steel", uv_scale=2.0, wear=0.8)
    if ctx.destroyed:
        K.kink([posts[1]], (span / 2, 0, 2.2), (0, -5, 0), blend=0.3)
    for p in posts:
        ctx.add(p, "road_paint_green", uv_scale=1.0, patches=0.6, low=1.0, low_h=0.8)
    ctx.col_box((-span / 2 - 0.3, -0.3, 0), (span / 2 + 0.3, 0.3, 6.25))


def sign_motel(ctx: K.Ctx) -> None:
    """Timberline Motel pylon: twin poles, the big double-faced sign cabinet (larch, TIMBERLINE
    MOTEL, est. 1961) crowned by a bulb-studded arrow bending down towards the office, then
    VACANCY with its NO box, the amenities board and WEEKLY RATES hung on hooks. Worn: half the
    bulbs gone, NO box hanging askew, amenities board fallen at the foot. Destroyed: main face
    smashed through, arrow folded down."""
    r = ctx.drnd("sign")
    poles = []
    for sx in (-1, 1):
        ft = K.cyl(ctx.uid("footing"), 0.3, 0.3, segs=14, center=(sx * 0.9, 0, 0.15))
        ctx.add(ft, "road_concrete", uv_scale=1.0, patches=0.6)
        p = K.cyl(ctx.uid("pole"), 0.11, 7.1, segs=12, center=(sx * 0.9, 0, 0.3 + 3.55), cuts=6)
        poles.append(p)
    for p in poles:
        ctx.add(p, "road_paint_brown", uv="cyl", uv_scale=1.0, smooth=40, patches=0.6, low=1.0, low_h=1.0)
    mz = 6.35
    cab = K.box("maincab", (3.0, 0.42, 1.8), center=(0, 0, mz), bevel=0.04, bevel_segs=2)
    ctx.add(cab, "road_paint_brown", uv_scale=1.0, patches=0.5)
    main = _rect(ATLAS_MOTEL, "motel_main")
    for s in (-1, 1):
        f = _face(ctx, ctx.uid("mainface"), 2.9, 1.74, main, MOTEL, (0, s * 0.213, mz), 0.0 if s < 0 else 180.0, nu=10, nv=6)
        if ctx.destroyed and s < 0:
            K.jagged_hole(f, (-0.5, s * 0.213, mz - 0.1), 0.55, r.randint(0, 999), axis=1)
    # Arrow over the top with bulbs.
    path = [Vector((-1.6, 0, mz + 0.95)), Vector((-0.6, 0, mz + 1.35)), Vector((0.6, 0, mz + 1.35)), Vector((1.6, 0, mz + 0.95)),
            Vector((1.85, 0, mz + 0.2)), Vector((1.75, 0, mz - 0.7))]
    if ctx.destroyed:
        path = [Vector((-1.6, 0, mz + 0.95)), Vector((-0.6, 0, mz + 1.35)), Vector((0.5, 0, mz + 1.3)), Vector((1.1, -0.3, mz + 0.8)),
                Vector((1.2, -0.5, mz + 0.1)), Vector((1.0, -0.6, mz - 0.4))]
    pts = []
    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        for k in range(6):
            pts.append(a.lerp(b, k / 6))
    pts.append(path[-1])
    arrow = K.tube("arrow", pts, 0.07, segs=8)
    ctx.add(arrow, "road_paint_orange", uv="cyl", uv_scale=1.0, smooth=40, patches=0.6)
    tip = path[-1]
    head = K.prism("arrowhead", [(-0.28, 0.0), (0.28, 0.0), (0.0, -0.42)], 0.1, plane="XZ")
    K.place(head, tip)
    ctx.add(head, "road_paint_orange", uv_scale=1.0, patches=0.6)
    for i, pnt in enumerate(pts[1:-1:2]):
        if ctx.worn and r.random() < 0.5:
            sock = K.cyl(ctx.uid("socket"), 0.02, 0.04, segs=6, axis="Y", center=pnt + Vector((0, -0.08, 0)))
            ctx.add(sock, "road_steel_dark", uv_scale=2.0)
            continue
        bulb = K.blob(ctx.uid("bulb"), 0.045, subdiv=1, center=pnt + Vector((0, -0.1, 0)))
        ctx.add(bulb, "road_bulb", uv_scale=2.0, smooth=60, patches=0.0, ao=False)
    # Lower boards on hooks from a crossbar.
    bar_z = 5.25
    bar = K.cyl("crossbar", 0.03, 2.2, segs=8, axis="X", center=(0, 0, bar_z))
    ctx.add(bar, "road_paint_brown", uv="cyl", uv_axis=0, uv_scale=1.0, smooth=40, patches=0.6)
    boards = [("vacancy", 1.8, 0.6, 0.25, 4.6, 0.0), ("no_box", 0.6, 0.6, -1.0, 4.6, 0.0),
              ("amenities", 1.8, 0.6, 0.25, 3.75, 0.0), ("weekly", 1.2, 0.6, -0.55, 2.95, 0.0)]
    for name, w, h, x, z, _ in boards:
        if ctx.worn and name == "amenities":
            # Fallen to the foot of the pole, leaning on it.
            bd = K.box(ctx.uid("board"), (w, 0.05, h), center=(0, 0, 0))
            fc = K.quad_sheet(ctx.uid("bface"), (-w / 2, 0, -h / 2), (w / 2, 0, -h / 2), (w / 2, 0, h / 2), (-w / 2, 0, h / 2), 4, 2)
            K.uv_planar(fc, 1, rect=_rect(ATLAS_MOTEL, name))
            K.place(fc, (0, -0.027, 0))
            for o in (bd, fc):
                K.place(o, rot=(-68, 0, 14))
                K.place(o, (0.4, -0.55, 0.28))
            ctx.add(bd, "road_paint_brown", uv_scale=1.0, patches=0.6)
            ctx.add(fc, MOTEL, uv=None, wear=0.7, patches=0.5)
            continue
        tilt = (0, 0, 0)
        if ctx.worn and name == "no_box":
            tilt = (0, 18, 0)
        bd = K.box(ctx.uid("board"), (w + 0.06, 0.05, h + 0.06), center=(0, 0, 0), bevel=0.01)
        grp = [bd]
        for s in (-1, 1):
            fc = K.quad_sheet(ctx.uid("bface"), (-w / 2, 0, -h / 2), (w / 2, 0, -h / 2), (w / 2, 0, h / 2), (-w / 2, 0, h / 2), 4, 2)
            K.uv_planar(fc, 1, rect=_rect(ATLAS_MOTEL, name))
            K.place(fc, (0, 0, 0), (0, 0, 0.0 if s < 0 else 180.0))
            K.place(fc, (0, s * 0.027, 0))
            grp.append(fc)
        for o in grp:
            if tilt != (0, 0, 0):
                o.data.transform(Matrix.Translation((w / 2, 0, h / 2)) @ K.rot_matrix(tilt) @ Matrix.Translation((-w / 2, 0, -h / 2)))
                o.data.update()
            K.place(o, (x, 0, z))
        ctx.add(grp[0], "road_paint_brown", uv_scale=1.0, patches=0.6)
        for o in grp[1:]:
            ctx.add(o, MOTEL, uv=None, wear=0.6, patches=0.35)
        top_z = z + h / 2 + 0.03
        hook_to = bar_z if name in ("vacancy", "no_box") else top_z + 0.6
        for hx in (x - w / 2 + 0.1, x + w / 2 - 0.1):
            hk = K.cyl(ctx.uid("hook"), 0.008, hook_to - top_z, segs=5, center=(hx, 0, top_z + (hook_to - top_z) / 2))
            ctx.add(hk, "road_steel", uv_scale=2.0, wear=0.8)
        if name in ("amenities", "weekly"):
            sub = K.cyl(ctx.uid("subbar"), 0.022, w + 0.2, segs=8, axis="X", center=(x, 0, hook_to))
            ctx.add(sub, "road_paint_brown", uv_scale=1.0, smooth=40, patches=0.6)
    ctx.col_box((-1.2, -0.35, 0), (1.2, 0.35, 7.3))


# ============================================================================================
# Motel
# ============================================================================================

def motel_bed(ctx: K.Ctx) -> None:
    """Motel queen bed: steel frame on glides, box spring and mattress under a quilted 90s spread
    draped to the floor with folds, pillow tuck, two pillows, and the laminate headboard bolted to
    the wall behind (+Y). Worn: spread dragged half off and rumpled, a pillow on the floor, stains.
    Destroyed: mattress slashed open (foam), frame collapsed at the foot corner."""
    W, L = 1.52, 2.0
    zt = 0.62
    for sx in (-1, 1):
        for sy in (-1, 1):
            g = K.cyl(ctx.uid("glide"), 0.025, 0.12, segs=8, center=(sx * 0.7, sy * 0.92, 0.06))
            ctx.add(g, "road_steel_dark", uv_scale=2.0)
    frame = K.box("frame", (W - 0.04, L - 0.04, 0.06), center=(0, 0, 0.15))
    ctx.add(frame, "road_steel_dark", uv_scale=1.0, patches=0.6)
    box_ = K.box("boxspring", (W, L, 0.2), center=(0, 0, 0.29), bevel=0.02)
    mat = K.box("mattress", (W, L, 0.22), center=(0, 0, 0.5), bevel=0.04, bevel_segs=2)
    ctx.add(box_, "road_linen", uv_scale=1.0, smooth=30, patches=0.3)
    ctx.add(mat, "road_linen", uv_scale=1.0, smooth=30, patches=0.3)
    # Spread: a grid shaped over the mattress and dropped down the sides and the foot.
    r = ctx.rnd("spread")
    nx, ny = 26, 30
    sw, sl = W + 2 * 0.55, L + 0.5
    spread = K.grid("spread", sw, sl, nx, ny)
    K.uv_planar(spread, 2, scale=1.0)
    hw, foot = W / 2 + 0.02, -L / 2 - 0.02
    head = L / 2 - 0.02
    rumple = 1.0 if ctx.clean else 2.2
    ph = r.uniform(0, 6.28)

    def drape(co: Vector) -> Vector:
        x, y = co.x, co.y - 0.25
        dx = max(0.0, abs(x) - hw)
        dy = max(0.0, foot - y)
        d = math.hypot(dx, dy)
        z = zt + 0.025
        if y > head - 0.55:
            z += 0.09 * math.sin(min(1.0, (y - (head - 0.55)) / 0.4) * math.pi * 0.5)  # pillow tuck
        y = min(y, head)
        if d > 0.0:
            # Over the rounded edge, then straight down; hems wave in soft folds.
            fold = 0.035 * rumple * math.sin(x * 9.0 + ph) + 0.03 * rumple * math.sin(y * 7.0 + ph * 1.7)
            ex = math.copysign(hw, x) if dx > 0 else x
            ey = foot if dy > 0 else y
            down = min(d, zt - 0.06)
            out = 0.04 + max(0.0, d - down) * 0.6
            nx_, ny_ = (dx / d, dy / d) if d > 1e-6 else (0.0, 0.0)
            x = ex + math.copysign(nx_ * out, x) + (fold if dx > 0 else 0.0) * 0.4
            y = ey - ny_ * out + (fold if dy > 0 else 0.0) * 0.4
            z = zt + 0.025 - down
        z += 0.012 * rumple * math.sin(co.x * 11.0 + ph) * math.sin(co.y * 8.0 + ph)
        return Vector((x, y, z))
    K.map_verts(spread, drape)
    if ctx.destroyed:
        K.jagged_hole(spread, (0.15, -0.1, zt + 0.02), 0.32, ctx.drnd("slash").randint(0, 999), axis=2, jag=0.6)
        foam = K.blob("foam", 0.3, subdiv=2, scale=(1.0, 0.6, 0.2), rough=0.4, seed=5, center=(0.15, -0.1, zt - 0.02))
        ctx.add(foam, "road_foam", uv_scale=2.0, smooth=50, patches=0.2)
    if ctx.worn:
        K.crumple(spread, 0.02, scale=4.0, seed=ctx.drnd("c").randint(0, 999))
    K.solidify(spread, 0.012, offset=-1.0, even=False)
    ctx.add(spread, "road_bedspread", uv=None, smooth=50, patches=0.2, edge=0.3)
    pil = []
    for k, sx in enumerate((-0.38, 0.38)):
        if ctx.worn and k == 1:
            pw = K.box("pillow_floor", (0.66, 0.42, 0.13), center=(0, 0, 0.065), bevel=0.06, bevel_segs=3)
            K.crumple(pw, 0.02, scale=6.0, seed=3)
            K.place(pw, rot=(0, 0, 35))
            K.place(pw, (W / 2 + 0.45, 0.4, 0.0))
            K.lift_min(pw)
            ctx.add(pw, "road_linen", uv_scale=1.0, smooth=50, patches=0.3)
            continue
        pw = K.box(ctx.uid("pillow"), (0.66, 0.42, 0.13), center=(0, 0, 0.065), bevel=0.06, bevel_segs=3)
        K.crumple(pw, 0.012, scale=6.0, seed=k + 1)
        K.place(pw, rot=(-12, 0, r.uniform(-4, 4)))
        K.place(pw, (sx, L / 2 - 0.3, zt + 0.12))
        ctx.add(pw, "road_linen", uv_scale=1.0, smooth=50, patches=0.3)
        pil.append(pw)
    hb = K.box("headboard", (1.65, 0.035, 0.72), center=(0, L / 2 + 0.045, 0.94), bevel=0.012)
    ctx.add(hb, "road_laminate", uv_scale=1.0, patches=0.5, long_axis=0)
    rail = K.box("hbrail", (1.65, 0.05, 0.05), center=(0, L / 2 + 0.03, 1.32), bevel=0.01)
    ctx.add(rail, "road_laminate_dark", uv_scale=1.0, patches=0.5, long_axis=0)
    _bolts(ctx, [(sx * 0.7, L / 2 + 0.027, z) for sx in (-1, 1) for z in (0.7, 1.2)], normal="-y", r=0.008, h=0.004)
    if ctx.destroyed:
        movers = [o for o in ctx.parts if not o.name.startswith(("headboard", "hbrail", "bolts"))]
        for o in movers:
            o.data.transform(Matrix.Translation((W / 2, -L / 2, 0)) @ K.rot_matrix((4, -5, 0)) @ Matrix.Translation((-W / 2, L / 2, 0)))
            o.data.update()
    ctx.col_box((-W / 2 - 0.08, -L / 2 - 0.08, 0), (W / 2 + 0.08, L / 2 + 0.07, zt + 0.15))


def _lamp(ctx, loc, *, base_mat="road_ceramic", tilt=None, broken=False):
    """Ginger-jar table lamp: weighted base, brass neck, harp, socket, pleated shade."""
    parts = []
    base = K.lathe(ctx.uid("lampbase"), [(0.0, 0.0), (0.07, 0.0), (0.08, 0.02), (0.11, 0.12), (0.1, 0.24), (0.05, 0.3),
                                         (0.03, 0.31), (0.0, 0.31)], segs=12)
    neck = K.cyl(ctx.uid("lampneck"), 0.012, 0.12, segs=8, center=(0, 0, 0.37))
    harp = K.tube(ctx.uid("harp"), [(-0.06, 0, 0.4), (-0.07, 0, 0.55), (0.0, 0, 0.6), (0.07, 0, 0.55), (0.06, 0, 0.4)], 0.004, segs=4)
    shade = K.lathe(ctx.uid("shade"), [(0.19, 0.38), (0.12, 0.64)], segs=16, cap_bottom=False, cap_top=False)
    parts = [(base, base_mat), (neck, "road_brass"), (harp, "road_brass"), (shade, "road_shade")]
    for o, m in parts:
        if broken and o is shade:
            K.subdivide(o, 1)
            K.jagged_hole(o, (0.15, -0.05, 0.5), 0.09, 7, axis=1)
        if tilt:
            K.place(o, rot=tilt)
        K.place(o, loc)
        ctx.add(o, m, uv="cyl" if o in (base, shade) else "box", uv_scale=2.0, smooth=40, patches=0.3)


def motel_nightstand(ctx: K.Ctx) -> None:
    """Laminate nightstand bolted beside the bed: drawer with a brass pull, open shelf with a phone
    book, ginger-jar lamp, beige push-button phone with a coiled cord, glass ashtray. Worn: phone
    knocked off the hook (handset dangling), shade torn. Destroyed: drawer ripped out, lamp on the
    floor."""
    W, Dp, H = 0.55, 0.42, 0.58
    car = K.box("carcass", (W, Dp, H - 0.06), center=(0, 0, 0.06 + (H - 0.06) / 2), bevel=0.006)
    K.delete_faces(car, lambda c, n: n.y < -0.9 and c.z < 0.38)
    ctx.add(car, "road_laminate", uv_scale=1.0, patches=0.5, long_axis=0)
    kick = K.box("kick", (W - 0.06, Dp - 0.06, 0.06), center=(0, 0.02, 0.03))
    ctx.add(kick, "road_laminate_dark", uv_scale=1.0)
    inner = K.box("inner", (W - 0.04, Dp - 0.04, 0.3), center=(0, 0.01, 0.23))
    K.delete_faces(inner, lambda c, n: n.y > 0.9)
    ctx.add(inner, "road_laminate_dark", uv_scale=1.0, patches=0.3)
    shelf = K.box("shelf", (W - 0.04, Dp - 0.04, 0.015), center=(0, 0.01, 0.2))
    ctx.add(shelf, "road_laminate", uv_scale=1.0)
    out = 0.0 if not ctx.destroyed else 0.25
    dr = K.box("drawer", (W - 0.03, 0.02, 0.16), center=(0, -Dp / 2 - 0.01 - out, 0.47), bevel=0.004)
    pull = K.box("pull", (0.12, 0.02, 0.016), center=(0, -Dp / 2 - 0.03 - out, 0.48), bevel=0.004)
    ctx.add(dr, "road_laminate", uv_scale=1.0, patches=0.5, long_axis=0)
    ctx.add(pull, "road_brass", uv_scale=2.0, wear=0.6)
    if out:
        db = K.box("drawerbox", (W - 0.06, out, 0.12), center=(0, -Dp / 2 - out / 2, 0.47))
        ctx.add(db, "road_laminate_dark", uv_scale=1.0)
    cov, pg = P.book("phonebook", ctx.rnd("book"), w=0.21, h=0.28, t=0.05)
    for o, m in ((cov, "road_paper_yellow"), (pg, "road_paper_white")):
        K.place(o, rot=(0, 0, 90))
        K.place(o, (-0.05, 0.0, 0.208))
        ctx.add(o, m, uv_scale=2.0, patches=0.3)
    if ctx.destroyed:
        _lamp(ctx, Vector((0.55, -0.35, 0.12)), tilt=(85, 0, 30), broken=True)
    else:
        _lamp(ctx, Vector((-0.12, 0.05, H)), broken=ctx.worn)
    ph = K.box("phone", (0.2, 0.22, 0.06), center=(0.15, -0.03, H + 0.03), bevel=0.015)
    pad = K.box("keypad", (0.12, 0.1, 0.012), center=(0.15, -0.08, H + 0.06))
    K.place(pad, (-0.15, 0.08, -(H + 0.06)))
    K.place(pad, rot=(14, 0, 0))
    K.place(pad, (0.15, -0.08, H + 0.065))
    ctx.add(ph, "road_plastic_beige", uv_scale=2.0, smooth=30, patches=0.3)
    ctx.add(pad, "road_plastic_black", uv_scale=2.0)
    if ctx.worn:
        hs_pts = [(0.3, -0.25, 0.32), (0.31, -0.27, 0.22), (0.3, -0.27, 0.12)]
        cord = K.tube("cord", [(0.23, -0.05, H + 0.03), (0.28, -0.12, H - 0.05), (0.3, -0.22, 0.4), (0.3, -0.25, 0.33)], 0.005, segs=5)
    else:
        hs_pts = [(0.07, 0.03, H + 0.085), (0.15, 0.04, H + 0.1), (0.23, 0.03, H + 0.085)]
        cord = K.tube("cord", [(0.06, -0.02, H + 0.05), (0.0, -0.1, H + 0.02), (-0.02, -0.15, H + 0.005)], 0.005, segs=5)
    hs = K.tube("handset", hs_pts, [0.022, 0.014, 0.022], segs=8)
    ctx.add(hs, "road_plastic_beige", uv_scale=2.0, smooth=40, patches=0.2)
    ctx.add(cord, "road_plastic_beige", uv_scale=2.0, smooth=40)
    tray = K.lathe("ashtray", [(0.0, 0.0), (0.055, 0.0), (0.06, 0.025), (0.045, 0.025), (0.04, 0.012), (0.0, 0.012)], segs=10)
    K.place(tray, (0.17, 0.13, H))
    ctx.add(tray, "road_glass", uv_scale=2.0, smooth=40, patches=0.0, ao=False)
    ctx.col_box((-W / 2, -Dp / 2, 0), (W / 2, Dp / 2, H + 0.1))


def tv_dresser(ctx: K.Ctx) -> None:
    """Long low motel dresser (six drawers, brass bar pulls) with a CRT colour TV chained to a swivel
    base, an ice bucket with wrapped glasses on a tray, and the wall mirror above it. Worn: TV
    screen cracked, a drawer open, mirror silvering spotted. Destroyed: TV pulled off and face down
    on the floor, mirror smashed."""
    W, Dp, H = 1.5, 0.5, 0.76
    car = K.box("carcass", (W, Dp, H - 0.06), center=(0, 0, 0.06 + (H - 0.06) / 2), bevel=0.006)
    ctx.add(car, "road_laminate", uv_scale=1.0, patches=0.5, long_axis=0)
    kick = K.box("kick", (W - 0.06, Dp - 0.06, 0.06), center=(0, 0.02, 0.03))
    ctx.add(kick, "road_laminate_dark", uv_scale=1.0)
    top = K.box("top", (W + 0.02, Dp + 0.02, 0.025), center=(0, 0, H + 0.0125), bevel=0.006)
    ctx.add(top, "road_laminate_dark", uv_scale=1.0, patches=0.5, long_axis=0)
    dr_r = ctx.drnd("dr")
    for col in (-1, 1):
        for row in range(3):
            z = 0.12 + row * 0.2
            out = 0.18 if (ctx.worn and col == 1 and row == 2) else 0.0
            fr = K.box(ctx.uid("drawer"), (W / 2 - 0.04, 0.02, 0.18), center=(col * W / 4, -Dp / 2 - 0.01 - out, z + 0.09), bevel=0.004)
            pull = K.box(ctx.uid("pull"), (0.22, 0.02, 0.014), center=(col * W / 4, -Dp / 2 - 0.03 - out, z + 0.12), bevel=0.004)
            ctx.add(fr, "road_laminate", uv_scale=1.0, patches=0.5, long_axis=0)
            ctx.add(pull, "road_brass", uv_scale=2.0, wear=0.6)
            if out:
                db = K.box(ctx.uid("dbox"), (W / 2 - 0.06, out, 0.14), center=(col * W / 4, -Dp / 2 - out / 2, z + 0.09))
                ctx.add(db, "road_laminate_dark", uv_scale=1.0)
                P.add_litter(ctx, dr_r, 2, extent=(0.15, 0.04), center=(col * W / 4, -Dp / 2 - out / 2), kinds=("paper",))
    # TV on its swivel base, cable to the dresser.
    tv_parts = []
    sb = K.cyl("swivel", 0.16, 0.03, segs=14, center=(0.3, 0.02, 0.015))
    case = K.box("tvcase", (0.56, 0.46, 0.44), center=(0, 0.05, 0.25), bevel=0.03, bevel_segs=2)
    back = K.box("tvback", (0.4, 0.2, 0.32), center=(0, 0.35, 0.24), bevel=0.04)
    scr = K.grid("screen", 0.44, 0.33, 6, 5)
    K.uv_planar(scr, 2, rect=(0.05, 0.05, 0.95, 0.95))
    K.map_verts(scr, lambda co: Vector((co.x, co.y, 0.02 * (1 - (co.x / 0.22) ** 2) * (1 - (co.y / 0.165) ** 2))))
    K.place(scr, rot=(90, 0, 0))
    K.place(scr, (-0.04, -0.18, 0.26))
    knobs = [K.cyl(ctx.uid("knob"), 0.014, 0.02, segs=8, axis="Y", center=(0.22, -0.185, 0.36 - k * 0.06)) for k in range(3)]
    grill = K.box("grill", (0.06, 0.006, 0.12), center=(0.22, -0.18, 0.15))
    tv_parts = [(sb, "road_plastic_black"), (case, "road_plastic_black"), (back, "road_plastic_black"), (scr, "road_crt"),
                (grill, "road_steel_dark")] + [(k, "road_chrome") for k in knobs]
    if ctx.worn:
        K.subdivide(scr, 1)
        K.jagged_hole(scr, (0.05, -0.18, 0.3), 0.08, ctx.drnd("scr").randint(0, 999), axis=1)
    for o, m in tv_parts:
        if o is not sb:
            K.place(o, (0.3, 0.0, 0.03))
        if ctx.destroyed:
            o.data.transform(Matrix.Translation((0.25, -0.75, 0.0)) @ K.rot_matrix((-90, 0, 20)) @ Matrix.Translation((-0.3, 0.0, 0.0)))
            o.data.update()
        else:
            K.place(o, (0, 0, H + 0.025))
        ctx.add(o, m, uv=None if m == "road_crt" else "box", uv_scale=2.0, smooth=30, patches=0.3)
    if not ctx.destroyed:
        cable = K.tube("seccable", [(0.55, 0.1, H + 0.12), (0.62, 0.15, H + 0.04), (0.66, 0.2, H + 0.03)], 0.005, segs=5)
        ctx.add(cable, "road_steel", uv_scale=2.0)
    # Ice bucket + glasses.
    tray = K.box("tray", (0.32, 0.22, 0.012), center=(-0.45, 0.0, H + 0.031))
    ctx.add(tray, "road_plastic_brown", uv_scale=2.0)
    bucket = K.lathe("icebucket", [(0.0, 0.0), (0.08, 0.0), (0.1, 0.17), (0.105, 0.18), (0.0, 0.18)], segs=12)
    K.place(bucket, (-0.5, 0.0, H + 0.037))
    ctx.add(bucket, "road_plastic_brown", uv="cyl", uv_scale=2.0, smooth=40, patches=0.3)
    for k in range(2):
        g = K.lathe(ctx.uid("glass"), [(0.0, 0.0), (0.03, 0.0), (0.036, 0.11), (0.0, 0.11)], segs=8)
        K.place(g, (-0.36, -0.05 + k * 0.09, H + 0.037))
        ctx.add(g, "road_wrap", uv="cyl", uv_scale=2.0, smooth=40, patches=0.0)
    # Mirror on the wall above.
    mz = 1.32
    mf = K.box("mirrorframe", (1.1, 0.03, 0.8), center=(0, Dp / 2 + 0.01, mz), bevel=0.008)
    ctx.add(mf, "road_laminate_dark", uv_scale=1.0, patches=0.5)
    mg = K.box("mirror", (1.0, 0.008, 0.7), center=(0, Dp / 2 - 0.007, mz), cuts=(4, 0, 3))
    if ctx.destroyed:
        K.jagged_hole(mg, (0.2, Dp / 2, mz + 0.05), 0.32, ctx.drnd("m").randint(0, 999), axis=1, jag=0.6)
    ctx.add(mg, "road_mirror", uv_scale=1.0, patches=0.0, ao=False)
    ctx.col_box((-W / 2, -Dp / 2, 0), (W / 2, Dp / 2, H + 0.5))


def housekeeping_cart(ctx: K.Ctx) -> None:
    """Housekeeping cart: three grey plastic shelves on corner posts and casters, folded towel and
    sheet stacks, toilet-roll stacks, spray bottles and a caddy, a yellow trash bag hung on one end
    and a canvas linen bag on the other, push handle. Worn: towels scattered, bags torn. Destroyed:
    tipped stock all over the floor, a shelf cracked."""
    L, Wd = 1.1, 0.5
    r = ctx.rnd("cart")
    dr = ctx.drnd("mess")
    for sx in (-1, 1):
        for sy in (-1, 1):
            _caster(ctx, sx * (L / 2 - 0.06), sy * (Wd / 2 - 0.06), 0.1, r=0.04, brake=sx < 0 and sy < 0)
            post = K.box(ctx.uid("post"), (0.035, 0.035, 0.85), center=(sx * (L / 2 - 0.02), sy * (Wd / 2 - 0.02), 0.1 + 0.425))
            ctx.add(post, "road_plastic_grey", uv_scale=2.0, patches=0.4)
    for z in (0.12, 0.5, 0.92):
        sh = K.box(ctx.uid("shelf"), (L, Wd, 0.03), center=(0, 0, z), bevel=0.008)
        lip = K.box(ctx.uid("lip"), (L, Wd, 0.05), center=(0, 0, z + 0.03))
        K.delete_faces(lip, lambda c, n: abs(n.z) > 0.9)
        ctx.add(sh, "road_plastic_grey", uv_scale=1.0, patches=0.4)
        ctx.add(lip, "road_plastic_grey", uv_scale=1.0, patches=0.4)
    stacks = [(-0.3, 0.135, "road_towel_white", 6), (0.05, 0.135, "road_linen", 5), (-0.3, 0.515, "road_towel_white", 5),
              (0.05, 0.515, "road_linen", 4)]
    for (x, z, m, n) in stacks:
        for k in range(n):
            if ctx.worn and k >= n - 2 and dr.random() < 0.6:
                continue
            t = K.box(ctx.uid("fold"), (0.3, 0.22, 0.045), center=(0, 0, 0.0225), bevel=0.015, bevel_segs=2)
            K.crumple(t, 0.004, scale=8.0, seed=r.randint(0, 999))
            K.place(t, rot=(0, 0, r.uniform(-5, 5)))
            K.place(t, (x + r.uniform(-0.01, 0.01), -0.08, z + 0.015 + k * 0.045))
            ctx.add(t, m, uv_scale=2.0, smooth=40, patches=0.2)
    for k in range(4):
        roll = K.lathe(ctx.uid("roll"), [(0.0, 0.0), (0.055, 0.0), (0.055, 0.11), (0.0, 0.11)], segs=10)
        K.place(roll, (0.35 + (k % 2) * 0.12, -0.08 + (k // 2) * 0.13, 0.95))
        ctx.add(roll, "road_paper_white", uv="cyl", uv_scale=2.0, smooth=40, patches=0.2)
    caddy = K.box("caddy", (0.36, 0.2, 0.1), center=(-0.15, 0.08, 0.99))
    K.delete_faces(caddy, lambda c, n: n.z > 0.9)
    ctx.add(caddy, "road_plastic_blue", uv_scale=2.0, patches=0.3)
    for k in range(3):
        b = K.lathe(ctx.uid("spray"), [(0.0, 0.0), (0.035, 0.0), (0.035, 0.16), (0.015, 0.2), (0.0, 0.2)], segs=8)
        trig = K.box(ctx.uid("trigger"), (0.03, 0.06, 0.05), center=(0, -0.02, 0.22), bevel=0.006)
        for o in (b, trig):
            K.place(o, (-0.26 + k * 0.1, 0.08, 0.95))
        ctx.add(b, ["road_plastic_blue", "road_plastic_green", "road_plastic_white"][k], uv="cyl", uv_scale=2.0, smooth=40)
        ctx.add(trig, "road_plastic_white", uv_scale=2.0)
    for sx, m in ((-1, "road_trash_yellow"), (1, "road_canvas")):
        hoop = K.tube(ctx.uid("hoop"), [(sx * L / 2, -0.2, 0.9), (sx * (L / 2 + 0.3), -0.2, 0.9), (sx * (L / 2 + 0.3), 0.2, 0.9),
                                        (sx * L / 2, 0.2, 0.9)], 0.01, segs=6)
        ctx.add(hoop, "road_chrome", uv_scale=2.0)
        bag = P.trash_bag_mesh(ctx.uid("bag"), r, size=(0.32, 0.4, 0.7), tied=False, slump=0.0, segs=12, open_top=True)
        K.map_verts(bag, lambda co: Vector((co.x, co.y, 0.9 - co.z * 1.0 if co.z < 0.9 else co.z)))
        K.place(bag, (sx * (L / 2 + 0.15), 0.0, 0.0))
        if ctx.worn:
            K.jagged_hole(bag, (sx * (L / 2 + 0.15), -0.2, 0.45), 0.08, dr.randint(0, 999), axis=1)
        ctx.add(bag, m, uv_scale=1.5, smooth=60, patches=0.2)
    handle = K.tube("handle", [(L / 2 - 0.02, -0.2, 0.95), (L / 2 - 0.02, -0.2, 1.08), (L / 2 - 0.02, 0.2, 1.08), (L / 2 - 0.02, 0.2, 0.95)],
                    0.012, segs=8)
    ctx.add(handle, "road_plastic_grey", uv_scale=2.0, smooth=40)
    if ctx.worn:
        for k in range(3 if not ctx.destroyed else 7):
            t = K.box(ctx.uid("floortowel"), (0.5, 0.35, 0.02), center=(0, 0, 0.01))
            K.subdivide(t, 2)
            K.crumple(t, 0.03, scale=5.0, seed=dr.randint(0, 999))
            K.place(t, rot=(0, 0, dr.uniform(0, 360)))
            K.place(t, (dr.uniform(-0.8, 0.8), dr.uniform(-0.9, -0.4), 0.0))
            K.lift_min(t)
            ctx.add(t, dr.choice(["road_towel_white", "road_linen"]), uv_scale=2.0, smooth=50, patches=0.2)
    ctx.col_box((-L / 2 - 0.3, -Wd / 2, 0), (L / 2 + 0.3, Wd / 2, 1.1))


def _laundry_cabinet(ctx, coin_y: float) -> None:
    W, Dp, H = 0.69, 0.7, 0.92
    for sx in (-1, 1):
        for sy in (-1, 1):
            f = K.cyl(ctx.uid("foot"), 0.02, 0.03, segs=8, center=(sx * 0.3, sy * 0.3, 0.015))
            ctx.add(f, "road_rubber", uv_scale=2.0)
    cab = K.box("cab", (W, Dp, H - 0.03), center=(0, 0, 0.03 + (H - 0.03) / 2), bevel=0.012, cuts=(1, 1, 2))
    if ctx.worn:
        dr = ctx.drnd("d")
        K.dent(cab, (dr.uniform(-0.2, 0.2), -Dp / 2, dr.uniform(0.2, 0.6)), 0.14, 0.02)
    if ctx.destroyed:
        K.dent(cab, (0.1, -Dp / 2, 0.45), 0.3, 0.07)
    ctx.add(cab, "road_enamel", uv_scale=1.0, patches=0.5, low=0.8, low_h=0.3)
    con = K.box("console", (W, 0.14, 0.2), center=(0, Dp / 2 - 0.07, H + 0.1), bevel=0.01)
    ctx.add(con, "road_enamel", uv_scale=1.0, patches=0.5)
    trim = K.box("contrim", (W + 0.004, 0.02, 0.04), center=(0, Dp / 2 - 0.14, H + 0.17))
    ctx.add(trim, "road_chrome", uv_scale=2.0, wear=0.6)
    slide = K.box("coinslide", (0.2, 0.06, 0.06), center=(0.12, Dp / 2 - 0.16, H + 0.08), bevel=0.006)
    knob = K.box("slideknob", (0.04, 0.05, 0.04), center=(0.12, Dp / 2 - 0.2, H + 0.08), bevel=0.006)
    cbox = K.box("coinbox", (0.1, 0.012, 0.08), center=(-0.15, Dp / 2 - 0.145, H + 0.09), bevel=0.004)
    lock = K.cyl("cblock", 0.01, 0.012, segs=8, axis="Y", center=(-0.15, Dp / 2 - 0.152, H + 0.09))
    for o in (slide, knob, lock):
        ctx.add(o, "road_chrome", uv_scale=2.0, wear=0.7)
    ctx.add(cbox, "road_steel", uv_scale=2.0, wear=0.7)
    if ctx.destroyed:
        pried = K.box("pried", (0.1, 0.012, 0.08), center=(0, 0, 0))
        K.place(pried, rot=(70, 0, 15))
        K.place(pried, (-0.15, Dp / 2 - 0.2, H + 0.05))
        ctx.add(pried, "road_steel", uv_scale=2.0, wear=1.0)


def washer(ctx: K.Ctx) -> None:
    """Coin-op top-loading washer: enamel cabinet with seams, hinged lid with a recessed grip, back
    console with chrome coin slide and locked coin box. Worn: lid up (drum and a forgotten load
    visible), rust at the feet, detergent drips. Destroyed: lid torn off, front caved in, coin box
    pried out."""
    W, Dp, H = 0.69, 0.7, 0.92
    _laundry_cabinet(ctx, 0.0)
    hinge_y, hinge_z = 0.12, H
    lid = K.box("lid", (0.62, 0.46, 0.03), center=(0, -0.11, H + 0.015), bevel=0.01)
    grip = K.box("grip", (0.18, 0.03, 0.012), center=(0, -0.33, H + 0.03))
    grp = [lid, grip]
    if ctx.destroyed:
        for o in grp:
            o.data.transform(Matrix.Translation((0.65, -0.55, 0.0)) @ K.rot_matrix((0, 0, 30)) @ Matrix.Translation((0, 0.11, -H)))
            o.data.update()
            K.lift_min(o)
    elif ctx.worn:
        for o in grp:
            o.data.transform(Matrix.Translation((0, hinge_y, hinge_z)) @ K.rot_matrix((-95, 0, 0)) @ Matrix.Translation((0, -hinge_y, -hinge_z)))
            o.data.update()
    ctx.add(lid, "road_enamel", uv_scale=1.0, patches=0.5)
    ctx.add(grip, "road_steel_dark", uv_scale=2.0)
    opening = K.cyl("opening", 0.24, 0.01, segs=18, center=(0, -0.11, H + 0.002))
    ctx.add(opening, "road_steel_dark", uv_scale=2.0, patches=0.2)
    if ctx.worn:
        drum = K.lathe("drum", [(0.23, 0.0), (0.23, -0.45), (0.0, -0.45)], segs=18, cap_bottom=False, cap_top=False)
        K.place(drum, (0, -0.11, H))
        ctx.add(drum, "road_stainless", uv="cyl", uv_scale=2.0, smooth=40, patches=0.3)
        load = K.blob("load", 0.18, subdiv=2, scale=(1.0, 1.0, 0.5), rough=0.4, seed=11, center=(0, -0.11, H - 0.35))
        ctx.add(load, "road_rag", uv_scale=2.0, smooth=50, patches=0.0)
    ctx.col_box((-W / 2, -Dp / 2, 0), (W / 2, Dp / 2, H + 0.2))


def dryer(ctx: K.Ctx) -> None:
    """Coin-op front-load dryer: enamel cabinet, round porthole door with a chrome ring and smoked
    glass, lint-screen slot, back console with coin slide. Worn: door hanging open showing the
    drum and a tangle of clothes. Destroyed: door torn off, glass broken, front caved in."""
    W, Dp, H = 0.69, 0.7, 0.92
    _laundry_cabinet(ctx, 0.0)
    lint = K.box("lint", (0.3, 0.02, 0.025), center=(0, -Dp / 2 - 0.005, H - 0.06))
    ctx.add(lint, "road_steel_dark", uv_scale=2.0)
    ring = K.lathe("doorring", [(0.21, -0.01), (0.23, 0.0), (0.23, 0.03), (0.2, 0.04), (0.18, 0.035)], segs=20, cap_bottom=False,
                   cap_top=False)
    glass = K.lathe("doorglass", [(0.0, 0.03), (0.18, 0.035), (0.185, 0.03)], segs=20, cap_bottom=False, cap_top=False)
    handle = K.box("dhandle", (0.04, 0.03, 0.12), center=(0.21, 0.0, 0.045), bevel=0.008)
    door = [(ring, "road_chrome"), (glass, "road_glass"), (handle, "road_plastic_black")]
    cz = 0.5
    for o, _ in door:
        K.place(o, rot=(90, 0, 0))
        K.place(o, (0, -Dp / 2 - 0.0, cz))
    if ctx.worn and not ctx.destroyed:
        hx = -0.23
        for o, _ in door:
            o.data.transform(Matrix.Translation((hx, -Dp / 2, cz)) @ K.rot_matrix((0, 0, -105)) @ Matrix.Translation((-hx, Dp / 2, -cz)))
            o.data.update()
    if ctx.destroyed:
        for o, _ in door:
            o.data.transform(Matrix.Translation((-0.45, -0.75, 0.0)) @ K.rot_matrix((-90, 0, 40)) @ Matrix.Translation((0, Dp / 2, -cz)))
            o.data.update()
            K.lift_min(o)
    if ctx.worn:
        hole = K.cyl("drumhole", 0.2, 0.02, segs=20, axis="Y", center=(0, -Dp / 2 + 0.005, cz))
        ctx.add(hole, "road_steel_dark", uv_scale=2.0, patches=0.2)
        clothes = K.blob("clothes", 0.16, subdiv=2, scale=(1.0, 0.8, 0.7), rough=0.45, seed=21, center=(0.02, -Dp / 2 - 0.05, 0.37))
        ctx.add(clothes, "road_rag", uv_scale=2.0, smooth=50, patches=0.0)
    for o, m in door:
        if ctx.destroyed and o is glass:
            continue
        ctx.add(o, m, uv_scale=2.0, smooth=40, patches=0.2, ao=m != "road_glass")
    ctx.col_box((-W / 2, -Dp / 2, 0), (W / 2, Dp / 2, H + 0.2))


def ice_machine(ctx: K.Ctx) -> None:
    """Motel ice machine: stainless bin on legs with a slanted flip-up door, cuber head on top with a
    louvred front and the ICE plaque, water line and drain hose behind, scale streaks. Worn: bin
    door hanging open, louvres dented, a puddle under it."""
    W, Dp = 0.76, 0.78
    for sx in (-1, 1):
        for sy in (-1, 1):
            leg = K.cyl(ctx.uid("leg"), 0.022, 0.15, segs=8, center=(sx * 0.33, sy * 0.33, 0.075))
            ctx.add(leg, "road_stainless", uv_scale=2.0)
    bin_ = K.box("bin", (W, Dp, 0.8), center=(0, 0, 0.15 + 0.4), bevel=0.012)
    ctx.add(bin_, "road_stainless", uv_scale=1.0, patches=0.5, low=0.6, low_h=0.4)
    hinge_y, hinge_z = -Dp / 2 + 0.02, 0.92
    door = K.box("bindoor", (0.6, 0.02, 0.26), center=(0, -Dp / 2 - 0.01, 0.79), bevel=0.006)
    dh = K.box("binhandle", (0.3, 0.03, 0.02), center=(0, -Dp / 2 - 0.03, 0.68), bevel=0.005)
    for o in (door, dh):
        K.place(o, (0, -hinge_y, -hinge_z))
        K.place(o, rot=(-14 if not ctx.worn else -105, 0, 0))
        K.place(o, (0, hinge_y, hinge_z))
    ctx.add(door, "road_stainless", uv_scale=1.0, patches=0.5)
    ctx.add(dh, "road_chrome", uv_scale=2.0)
    head = K.box("head", (W, Dp - 0.12, 0.58), center=(0, 0.04, 0.95 + 0.29), bevel=0.012)
    ctx.add(head, "road_stainless", uv_scale=1.0, patches=0.5)
    _louvres(ctx, -0.32, 0.32, 1.0, 1.32, -Dp / 2 + 0.1 - 0.005, 8, "road_stainless")
    _face(ctx, "plaque", 0.36, 0.18, _rect(ATLAS_MOTEL, "ice_label"), MOTEL, (0, -Dp / 2 + 0.1 - 0.006, 1.42), nu=2, nv=1)
    wl = K.tube("waterline", [(0.25, Dp / 2 - 0.05, 1.3), (0.3, Dp / 2 + 0.05, 1.2), (0.3, Dp / 2 + 0.06, 0.0)], 0.008, segs=5)
    dh2 = K.tube("drain", [(-0.2, Dp / 2, 0.2), (-0.22, Dp / 2 + 0.08, 0.1), (-0.3, Dp / 2 + 0.1, 0.02)], 0.015, segs=6)
    ctx.add(wl, "road_plastic_white", uv_scale=2.0, smooth=40)
    ctx.add(dh2, "road_plastic_white", uv_scale=2.0, smooth=40)
    if ctx.worn:
        p = K.cyl("puddle", 0.4, 0.003, segs=16, center=(0.1, -0.45, 0.0015))
        ctx.add(p, "road_water_film", uv_scale=1.0, patches=0.0, edge=0.0, ao=False)
    ctx.col_box((-W / 2, -Dp / 2, 0), (W / 2, Dp / 2, 1.53))


def walkway_post(ctx: K.Ctx) -> None:
    """Upper-walkway support post: square steel tube on an anchored base plate with a cap plate and
    a 60s scroll bracket under the slab edge. Worn: base rusted through the paint, scroll bent."""
    Hp = 2.95
    plate = K.box("base", (0.2, 0.2, 0.012), center=(0, 0, 0.006))
    ctx.add(plate, "road_steel", uv_scale=2.0, wear=1.0, patches=0.7)
    _bolts(ctx, [(sx * 0.075, sy * 0.075, 0.012) for sx in (-1, 1) for sy in (-1, 1)], normal="z", r=0.011, h=0.018)
    post = K.box("post", (0.1, 0.1, Hp - 0.02), center=(0, 0, 0.012 + (Hp - 0.02) / 2), bevel=0.006, cuts=(0, 0, 3))
    ctx.add(post, "road_paint_white", uv_scale=1.0, patches=0.6, low=1.0, low_h=0.6)
    cap = K.box("cap", (0.2, 0.2, 0.012), center=(0, 0, Hp - 0.006))
    ctx.add(cap, "road_steel", uv_scale=2.0, patches=0.6)
    bend = 0.0 if not ctx.worn else 0.04
    for s in (-1, 1):
        pts = []
        for k in range(14):
            t = k / 13
            a = t * math.pi * 1.6
            rr = 0.16 * (1 - t * 0.6)
            pts.append(Vector((s * (0.05 + 0.25 * t), 0.0, Hp - 0.04 - rr * math.sin(a) * 0.6 - 0.25 * t * t + bend * t)))
        scroll = K.sweep(ctx.uid("scroll"), pts, [(-0.006, -0.015), (0.006, -0.015), (0.006, 0.015), (-0.006, 0.015)])
        ctx.add(scroll, "road_paint_white", uv_scale=2.0, patches=0.6)
    ctx.col_box((-0.1, -0.1, 0), (0.1, 0.1, Hp))


def suitcase(ctx: K.Ctx) -> None:
    """90s hard-shell suitcase lying flat: moulded shell with ribs, aluminium valance seam, two
    latches, carry handle, feet. Worn: scuffed, a latch sprung, a luggage strap round it."""
    L, Wd, Hs = 0.66, 0.44, 0.21
    r = ctx.rnd("case")
    sh = K.box("shell", (L, Wd, Hs), center=(0, 0, Hs / 2 + 0.01), bevel=0.04, bevel_segs=3, cuts=(3, 2, 0))
    for k in range(3):
        K.dent(sh, ((k - 1) * 0.18, 0.0, Hs + 0.01), 0.06, -0.006)
    ctx.add(sh, r.choice(["road_plastic_navy", "road_plastic_maroon"]), uv_scale=1.5, smooth=30, patches=0.4)
    seam = K.box("seam", (L + 0.006, Wd + 0.006, 0.018), center=(0, 0, Hs * 0.55 + 0.01), bevel=0.03)
    K.delete_faces(seam, lambda c, n: abs(n.z) > 0.9)
    ctx.add(seam, "road_alu", uv_scale=2.0, wear=0.6)
    for sx in (-1, 1):
        latch = K.box(ctx.uid("latch"), (0.05, 0.012, 0.035), center=(sx * 0.18, -Wd / 2 - 0.006, Hs * 0.55 + 0.01), bevel=0.004)
        if ctx.worn and sx > 0:
            K.place(latch, (0, -0.006, 0.012))
        ctx.add(latch, "road_chrome", uv_scale=3.0, wear=0.6)
    handle = K.tube("handle", [(-0.09, -Wd / 2 - 0.005, Hs * 0.55), (-0.08, -Wd / 2 - 0.035, Hs * 0.55 + 0.01),
                               (0.08, -Wd / 2 - 0.035, Hs * 0.55 + 0.01), (0.09, -Wd / 2 - 0.005, Hs * 0.55)], 0.012, segs=8)
    ctx.add(handle, "road_plastic_black", uv_scale=2.0, smooth=40)
    for sx in (-1, 1):
        for sy in (-1, 1):
            ft = K.cyl(ctx.uid("foot"), 0.012, 0.012, segs=6, center=(sx * 0.27, sy * 0.17, 0.006))
            ctx.add(ft, "road_plastic_black", uv_scale=2.0)
    if ctx.worn:
        strap = K.box("strap", (0.04, Wd + 0.02, Hs + 0.024), center=(0.08, 0, Hs / 2 + 0.01))
        K.delete_faces(strap, lambda c, n: abs(n.x) > 0.9)
        ctx.add(strap, "road_plastic_red", uv_scale=2.0)
    ctx.col_box((-L / 2, -Wd / 2, 0), (L / 2, Wd / 2, Hs + 0.02))


# ============================================================================================
# Clinic
# ============================================================================================

def exam_table(ctx: K.Ctx) -> None:
    """Padded examination table (long axis along X, drawers facing -Y): beige steel cabinet base
    with drawers and a pull-out step, teal vinyl top with the backrest raised at the head (+X),
    paper roll on its bracket and a sheet run down the table, folded stirrups. Worn: paper torn and
    trailing, vinyl split. Destroyed: backrest torn off and on the floor, drawers dumped."""
    L, Wd = 1.85, 0.68
    r = ctx.drnd("t")
    base = K.box("base", (L - 0.25, Wd - 0.08, 0.6), center=(-0.05, 0, 0.1 + 0.3), bevel=0.01)
    plinth = K.box("plinth", (L - 0.3, Wd - 0.14, 0.1), center=(-0.05, 0, 0.05))
    ctx.add(base, "road_paint_beige", uv_scale=1.0, patches=0.5, low=0.8, low_h=0.3)
    ctx.add(plinth, "road_steel_dark", uv_scale=1.0)
    for k, x in enumerate((-0.55, -0.15, 0.25)):
        for z in (0.5, 0.25):
            out = 0.2 if (ctx.destroyed and (k + int(z * 10)) % 2 == 0) else 0.0
            d = K.box(ctx.uid("drawer"), (0.36, 0.015, 0.2), center=(x, -Wd / 2 + 0.03 - out, z + 0.1), bevel=0.003)
            pl = K.box(ctx.uid("pull"), (0.12, 0.02, 0.014), center=(x, -Wd / 2 + 0.015 - out, z + 0.16), bevel=0.003)
            ctx.add(d, "road_paint_beige", uv_scale=1.0, patches=0.5)
            ctx.add(pl, "road_chrome", uv_scale=2.0)
    step = K.box("step", (0.4, 0.3, 0.04), center=(-L / 2 + 0.3, -Wd / 2 - 0.1, 0.25), bevel=0.008)
    tread = K.box("steptread", (0.38, 0.26, 0.006), center=(-L / 2 + 0.3, -Wd / 2 - 0.1, 0.273))
    ctx.add(step, "road_paint_beige", uv_scale=1.0, patches=0.5)
    ctx.add(tread, "road_tread", uv_scale=4.0)
    zt = 0.7
    flat = K.box("pad", (1.35, Wd, 0.08), center=(-L / 2 + 0.675, 0, zt + 0.04), bevel=0.025, bevel_segs=2, cuts=(3, 1, 0))
    if ctx.worn:
        K.dent(flat, (-0.3, 0.1, zt + 0.08), 0.12, 0.01)
    ctx.add(flat, "road_vinyl_teal", uv_scale=1.5, smooth=35, patches=0.4)
    hx, hz = -L / 2 + 1.36, zt + 0.06
    back = K.box("backrest", (0.5, Wd, 0.08), center=(0.25, 0, 0.0), bevel=0.025, bevel_segs=2)
    bracket = K.box("hingebar", (0.05, Wd - 0.1, 0.03), center=(0, 0, -0.04))
    if ctx.destroyed:
        for o in (back,):
            o.data.transform(Matrix.Translation((0.55, -0.85, 0.04)) @ K.rot_matrix((0, 0, 25)))
            o.data.update()
    else:
        for o in (back, bracket):
            K.place(o, rot=(0, -32, 0))
            K.place(o, (hx, 0, hz))
    ctx.add(back, "road_vinyl_teal", uv_scale=1.5, smooth=35, patches=0.4)
    if not ctx.destroyed:
        ctx.add(bracket, "road_chrome", uv_scale=2.0)
    roll_x = L / 2 + 0.03
    roll = K.cyl("roll", 0.06, Wd - 0.12, segs=12, axis="Y", center=(roll_x, 0, zt + 0.12))
    core = K.cyl("rollbar", 0.012, Wd - 0.02, segs=8, axis="Y", center=(roll_x, 0, zt + 0.12))
    ctx.add(roll, "road_paper_white", uv="cyl", uv_axis=1, uv_scale=2.0, smooth=40, patches=0.2)
    ctx.add(core, "road_chrome", uv_scale=2.0)
    for s in (-1, 1):
        arm = K.box(ctx.uid("rollarm"), (0.1, 0.02, 0.08), center=(roll_x - 0.04, s * (Wd / 2 - 0.02), zt + 0.08))
        ctx.add(arm, "road_chrome", uv_scale=2.0)
    # Paper sheet over the pad (and torn trailing when worn).
    n_end = -L / 2 + (0.25 if ctx.worn else 0.05)
    sheet = K.quad_sheet("paper", (n_end, -Wd / 2 + 0.08, zt + 0.083), (hx, -Wd / 2 + 0.08, zt + 0.083), (hx, Wd / 2 - 0.08, zt + 0.083),
                         (n_end, Wd / 2 - 0.08, zt + 0.083), 8, 3)
    K.crumple(sheet, 0.003, scale=8.0, seed=4)
    ctx.add(sheet, "road_paper_white", uv_scale=1.0, smooth=40, patches=0.1, edge=0.0)
    if not ctx.destroyed:
        top_pts = [Vector((hx, 0, hz + 0.03))]
        d = Vector((math.cos(math.radians(32)), 0, math.sin(math.radians(32))))
        sheet2 = K.quad_sheet("paper2", (hx, -Wd / 2 + 0.08, hz + 0.045), (hx + d.x * 0.5, -Wd / 2 + 0.08, hz + 0.045 + d.z * 0.5),
                              (hx + d.x * 0.5, Wd / 2 - 0.08, hz + 0.045 + d.z * 0.5), (hx, Wd / 2 - 0.08, hz + 0.045), 4, 3)
        ctx.add(sheet2, "road_paper_white", uv_scale=1.0, smooth=40, patches=0.1, edge=0.0)
    if ctx.worn:
        tail = K.quad_sheet("papertail", (n_end, -0.2, zt + 0.083), (n_end, 0.2, zt + 0.083), (n_end - 0.15, 0.25, 0.2),
                            (n_end - 0.1, -0.15, 0.02), 3, 4)
        K.crumple(tail, 0.02, scale=6.0, seed=8)
        ctx.add(tail, "road_paper_white", uv_scale=1.0, smooth=40, patches=0.1, edge=0.0)
    for s in (-1, 1):
        st = K.tube(ctx.uid("stirrup"), [(-L / 2 + 0.05, s * 0.2, zt - 0.02), (-L / 2 + 0.02, s * 0.2, zt - 0.06),
                                         (-L / 2 + 0.02, s * 0.22, zt - 0.2)], 0.01, segs=6)
        ctx.add(st, "road_chrome", uv_scale=2.0)
    ctx.col_box((-L / 2, -Wd / 2, 0), (L / 2 + 0.1, Wd / 2, 1.05))


def medical_cabinet(ctx: K.Ctx) -> None:
    """Enamelled steel supply cabinet: glass-doored upper case with glass shelves of labelled supply
    boxes and amber bottles, solid lower doors with chrome handles and a lock, on short legs.
    Worn: a pane smashed, shelves half emptied, a door ajar. Destroyed: both panes smashed, a door
    torn off on the floor, boxes spilled."""
    W, Dp = 0.9, 0.42
    r = ctx.rnd("stock")
    dr = ctx.drnd("gone")
    for sx in (-1, 1):
        for sy in (-1, 1):
            leg = K.cyl(ctx.uid("leg"), 0.015, 0.1, segs=8, center=(sx * 0.4, sy * 0.17, 0.05))
            ctx.add(leg, "road_chrome", uv_scale=2.0)
    lower = K.box("lower", (W, Dp, 0.85), center=(0, 0, 0.1 + 0.425), bevel=0.01)
    upper = K.box("upper", (W, Dp - 0.04, 0.88), center=(0, 0.02, 0.95 + 0.44), bevel=0.01)
    K.delete_faces(upper, lambda c, n: n.y < -0.9)
    ctx.add(lower, "road_paint_white", uv_scale=1.0, patches=0.5, low=0.7, low_h=0.3)
    ctx.add(upper, "road_paint_white", uv_scale=1.0, patches=0.5)
    inner_back = K.box("innerback", (W - 0.04, 0.01, 0.84), center=(0, Dp / 2 - 0.04, 1.39))
    ctx.add(inner_back, "road_paint_grey", uv_scale=1.0, patches=0.2)
    labels = [_rect(ATLAS_GAS, "box_labels", (0.0, k / 6, 1.0, (k + 1) / 6)) for k in range(6)]
    for si, z in enumerate((1.0, 1.28, 1.56)):
        sh = K.box(ctx.uid("shelf"), (W - 0.05, Dp - 0.1, 0.008), center=(0, 0.02, z))
        ctx.add(sh, "road_glass", uv_scale=1.0, patches=0.0, ao=False)
        x = -W / 2 + 0.08
        k = 0
        while x < W / 2 - 0.08:
            gone = ctx.worn and dr.random() < (0.45 if not ctx.destroyed else 0.8)
            if (k + si) % 3 == 2:
                if not gone:
                    b = K.lathe(ctx.uid("bottle"), [(0.0, 0.0), (0.03, 0.0), (0.03, 0.1), (0.014, 0.12), (0.014, 0.14), (0.0, 0.14)], segs=8)
                    K.place(b, (x, -0.02, z + 0.004))
                    ctx.add(b, "glass_brown", uv="cyl", uv_scale=1.0, smooth=40, patches=0.0)
                x += 0.08
            else:
                bw = r.uniform(0.12, 0.16)
                if not gone:
                    bx = K.box(ctx.uid("box"), (bw, 0.2, 0.17), center=(0, 0, 0.085))
                    K.uv_planar(bx, 1, rect=labels[(k + si * 2) % 6])
                    K.place(bx, (x + bw / 2 - 0.04, 0.0, z + 0.004))
                    ctx.add(bx, GAS, uv=None, patches=0.2, wear=0.3)
                x += bw + 0.015
            k += 1
    hinge_y = -Dp / 2 + 0.005
    for i, sx in enumerate((-1, 1)):
        hx = sx * (W / 2 - 0.01)
        frame = K.box(ctx.uid("gframe"), (W / 2 - 0.01, 0.02, 0.86), center=(sx * W / 4, hinge_y, 1.39), bevel=0.004)
        K.delete_faces(frame, lambda c, n: abs(n.y) > 0.9)
        pane = K.box(ctx.uid("pane"), (W / 2 - 0.06, 0.006, 0.8), center=(sx * W / 4, hinge_y, 1.39), cuts=(3, 0, 5))
        smashed = (ctx.worn and i == 0) or ctx.destroyed
        if smashed:
            K.jagged_hole(pane, (sx * W / 4 + 0.02, hinge_y, 1.42), 0.22, dr.randint(0, 999), axis=1)
        hd = K.box(ctx.uid("ghandle"), (0.02, 0.03, 0.12), center=(sx * 0.04, hinge_y - 0.02, 1.3), bevel=0.004)
        grp = [frame, pane, hd]
        ajar = ctx.worn and not ctx.destroyed and i == 1
        if ajar:
            for o in grp:
                o.data.transform(Matrix.Translation((hx, hinge_y, 0)) @ K.rot_matrix((0, 0, 40)) @ Matrix.Translation((-hx, -hinge_y, 0)))
                o.data.update()
        ctx.add(frame, "road_paint_white", uv_scale=1.0, patches=0.5)
        ctx.add(pane, "road_glass", uv_scale=1.0, patches=0.0, ao=False)
        ctx.add(hd, "road_chrome", uv_scale=2.0)
        ld = K.box(ctx.uid("ldoor"), (W / 2 - 0.02, 0.015, 0.78), center=(sx * W / 4, -Dp / 2 - 0.006, 0.52), bevel=0.004)
        lh = K.box(ctx.uid("lhandle"), (0.02, 0.03, 0.12), center=(sx * 0.05, -Dp / 2 - 0.025, 0.7), bevel=0.004)
        if ctx.destroyed and i == 0:
            for o in (ld, lh):
                o.data.transform(Matrix.Translation((-0.3, -0.75, 0.0)) @ K.rot_matrix((-90, 0, 15)) @ Matrix.Translation((W / 4, Dp / 2, -0.12)))
                o.data.update()
                K.lift_min(o)
        ctx.add(ld, "road_paint_white", uv_scale=1.0, patches=0.5)
        ctx.add(lh, "road_chrome", uv_scale=2.0)
    lock = K.cyl("lock", 0.012, 0.015, segs=8, axis="Y", center=(0.0, -Dp / 2 - 0.012, 0.86))
    ctx.add(lock, "road_chrome", uv_scale=2.0)
    if ctx.worn:
        for k in range(3 if not ctx.destroyed else 8):
            bw = dr.uniform(0.12, 0.16)
            bx = K.box(ctx.uid("floorbox"), (bw, 0.2, 0.17), center=(0, 0, 0.085))
            K.uv_planar(bx, 1, rect=labels[k % 6])
            K.place(bx, rot=(dr.choice((0, 90)), 0, dr.uniform(0, 360)))
            K.lift_min(bx)
            K.place(bx, (dr.uniform(-0.5, 0.5), dr.uniform(-0.9, -0.4), 0.0))
            ctx.add(bx, GAS, uv=None, patches=0.2)
        P.add_litter(ctx, dr, 4, extent=(0.5, 0.25), center=(0, -0.6), kinds=("paper", "wad"))
    ctx.col_box((-W / 2, -Dp / 2, 0), (W / 2, Dp / 2, 1.85))


def iv_stand(ctx: K.Ctx) -> None:
    """Rolling IV pole: five-spoke caster base, chrome pole with a height collar, four-hook head, a
    half-empty saline bag with drip chamber and tubing coiled down. Worn: bag empty and crumpled,
    tubing cut. Destroyed: knocked over on the floor."""
    parts = []
    hub = K.cyl("hub", 0.04, 0.05, segs=10, center=(0, 0, 0.1))
    parts.append((hub, "road_chrome"))
    for k in range(5):
        a = k * math.tau / 5
        sp = K.box(ctx.uid("spoke"), (0.26, 0.03, 0.025), center=(0.13, 0, 0.0))
        K.place(sp, rot=(0, 0, math.degrees(a)))
        K.place(sp, (0, 0, 0.09))
        parts.append((sp, "road_chrome"))
    pole = K.cyl("pole", 0.013, 1.82, segs=10, center=(0, 0, 0.12 + 0.91))
    inner = K.cyl("inner", 0.01, 0.3, segs=8, center=(0, 0, 1.95 - 0.15))
    collar = K.cyl("collar", 0.022, 0.05, segs=10, center=(0, 0, 1.55))
    knob = K.cyl("collarknob", 0.012, 0.04, segs=8, axis="X", center=(0.035, 0, 1.55))
    parts += [(pole, "road_chrome"), (inner, "road_chrome"), (collar, "road_plastic_grey"), (knob, "road_plastic_grey")]
    for k in range(4):
        a = k * math.pi / 2 + math.pi / 4
        d = Vector((math.cos(a), math.sin(a), 0))
        hk = K.tube(ctx.uid("hook"), [Vector((0, 0, 1.94)), d * 0.08 + Vector((0, 0, 1.95)), d * 0.13 + Vector((0, 0, 1.97)),
                                      d * 0.14 + Vector((0, 0, 2.0))], 0.005, segs=5)
        parts.append((hk, "road_chrome"))
    hang = Vector((0.1, 0.0, 1.96))
    bag = K.box("bag", (0.13, 0.03, 0.22), center=(0, 0, -0.13), bevel=0.012, cuts=(1, 0, 2))
    if ctx.worn:
        K.map_verts(bag, lambda co: Vector((co.x, co.y * 0.3, co.z)))
        K.crumple(bag, 0.01, scale=10.0, seed=3)
    else:
        K.crumple(bag, 0.004, scale=10.0, seed=3)
    K.place(bag, hang)
    drip = K.cyl("drip", 0.01, 0.06, segs=8, center=hang + Vector((0, 0, -0.29)))
    tube_pts = [hang + Vector((0, 0, -0.32)), hang + Vector((0.02, -0.03, -0.6)), Vector((0.12, -0.08, 1.0)), Vector((0.06, -0.06, 0.8)),
                Vector((0.0, -0.05, 0.85)), Vector((0.03, -0.02, 1.1))]
    if ctx.worn:
        tube_pts = tube_pts[:3]
    tubing = K.tube("tubing", tube_pts, 0.003, segs=4)
    parts += [(bag, "road_iv_bag"), (drip, "road_iv_bag"), (tubing, "road_iv_bag")]
    for k in range(5):
        a = k * math.tau / 5
        _caster(ctx, math.cos(a) * 0.25, math.sin(a) * 0.25, 0.085, r=0.03, wheel_mat="road_plastic_black", mat="road_chrome")
    if ctx.destroyed:
        for o, _ in parts:
            o.data.transform(Matrix.Translation((0, 0, 0.09)) @ K.rot_matrix((86, 0, 30)))
            o.data.update()
            K.lift_min(o)
    for o, m in parts:
        ctx.add(o, m, uv_scale=2.0, smooth=40, patches=0.3, ao=m != "road_iv_bag")
    ctx.col_box((-0.27, -0.27, 0), (0.27, 0.27, 2.0))


def wheelchair(ctx: K.Ctx) -> None:
    """Chrome-frame folding wheelchair: big spoked rear wheels with push rims, front casters, black
    vinyl sling seat and back, padded armrests, swing-away footrests, push handles. Worn: a footrest
    gone, seat sling split. Destroyed: tipped onto its side."""
    parts = []
    sw = 0.23
    for s in (-1, 1):
        x = s * sw
        fr = K.tube(ctx.uid("side"), [(x, 0.32, 0.98), (x, 0.3, 0.9), (x, 0.26, 0.48), (x, -0.22, 0.48), (x, -0.26, 0.36),
                                      (x, -0.3, 0.16)], 0.012, segs=8)
        low = K.tube(ctx.uid("lowrail"), [(x, 0.26, 0.3), (x, -0.28, 0.3)], 0.011, segs=8)
        arm = K.tube(ctx.uid("armtube"), [(x, 0.24, 0.48), (x, 0.22, 0.72), (x, -0.1, 0.72), (x, -0.14, 0.48)], 0.01, segs=6)
        pad = K.box(ctx.uid("armpad"), (0.05, 0.3, 0.035), center=(x, 0.06, 0.74), bevel=0.012)
        grip = K.cyl(ctx.uid("grip"), 0.017, 0.11, segs=8, axis="Y", center=(x, 0.37, 0.98))
        parts += [(fr, "road_chrome"), (low, "road_chrome"), (arm, "road_chrome"), (pad, "road_vinyl_black"), (grip, "road_rubber")]
        # Rear wheel with push rim and spokes.
        wc = Vector((s * (sw + 0.06), 0.18, 0.3))
        tyre = K.lathe(ctx.uid("tyre"), [(0.29 + 0.012 * math.cos(a), 0.012 * math.sin(a)) for a in [i * math.tau / 6 for i in range(6)]],
                       segs=20, close_profile=True)
        rim = K.lathe(ctx.uid("rim"), [(0.27 + 0.01 * math.cos(a), 0.008 * math.sin(a)) for a in [i * math.tau / 6 for i in range(6)]],
                      segs=20, close_profile=True)
        prim = K.lathe(ctx.uid("pushrim"), [(0.255 + 0.007 * math.cos(a), 0.007 * math.sin(a)) for a in [i * math.tau / 6 for i in range(6)]],
                       segs=20, close_profile=True)
        hubw = K.cyl(ctx.uid("whub"), 0.03, 0.06, segs=10, center=(0, 0, 0))
        wparts = [(tyre, "road_rubber", 0.0), (rim, "road_chrome", 0.0), (prim, "road_chrome", s * 0.035), (hubw, "road_chrome", 0.0)]
        for k in range(12):
            a = k * math.tau / 12
            sp = K.box(ctx.uid("spoke"), (0.003, 0.003, 0.25), center=(0, 0, 0.14))
            K.place(sp, rot=(0, 0, 0))
            K.place(sp, rot=(math.degrees(a), 0, 0))
            wparts.append((sp, "road_steel", 0.0))
        for o, m, off in wparts:
            if o is not sp or True:
                if o.name.startswith(("tyre", "rim", "pushrim", "whub")):
                    K.place(o, rot=(0, 90, 0))
            K.place(o, wc + Vector((off, 0, 0)))
            parts.append((o, m))
        # Front caster fork + wheel.
        cw = K.cyl(ctx.uid("cwheel"), 0.08, 0.025, segs=12, axis="X", center=(x, -0.33, 0.08))
        fork = K.box(ctx.uid("cfork"), (0.03, 0.03, 0.1), center=(x, -0.3, 0.17))
        parts += [(cw, "road_rubber"), (fork, "road_chrome")]
        if not (ctx.worn and s > 0):
            fr2 = K.tube(ctx.uid("footrest"), [(x, -0.3, 0.42), (x, -0.4, 0.22), (x, -0.42, 0.14)], 0.01, segs=6)
            plate = K.box(ctx.uid("footplate"), (0.14, 0.12, 0.012), center=(x - s * 0.06, -0.44, 0.13), bevel=0.004)
            parts += [(fr2, "road_chrome"), (plate, "road_plastic_black")]
    cross = [K.tube(ctx.uid("cross"), [(-sw, 0.1, 0.48), (sw, -0.1, 0.3)], 0.01, segs=6),
             K.tube(ctx.uid("cross"), [(sw, 0.1, 0.48), (-sw, -0.1, 0.3)], 0.01, segs=6)]
    parts += [(c, "road_chrome") for c in cross]
    seat = K.grid("seat", sw * 2, 0.44, 6, 6)
    K.uv_planar(seat, 2, scale=1.0)
    K.map_verts(seat, lambda co: Vector((co.x, co.y, -0.03 * (1 - (co.x / sw) ** 2))))
    K.place(seat, (0, 0.03, 0.49))
    back = K.grid("back", sw * 2, 0.4, 6, 5)
    K.uv_planar(back, 2, scale=1.0)
    K.map_verts(back, lambda co: Vector((co.x, co.y, 0.03 * (1 - (co.x / sw) ** 2))))
    K.place(back, rot=(-80, 0, 0))
    K.place(back, (0, 0.28, 0.7))
    if ctx.worn:
        K.jagged_hole(seat, (0.05, 0.03, 0.47), 0.07, 5, axis=2)
    for o in (seat, back):
        K.solidify(o, 0.006, offset=0.0, even=False)
        parts.append((o, "road_vinyl_black"))
    if ctx.destroyed:
        for o, _ in parts:
            o.data.transform(Matrix.Translation((0.2, 0.0, 0.0)) @ K.rot_matrix((0, 88, 15)))
            o.data.update()
        zmin = min(min((v.co.z for v in o.data.vertices), default=0.0) for o, _ in parts)
        for o, _ in parts:
            o.data.transform(Matrix.Translation((0, 0, -zmin)))
            o.data.update()
    for o, m in parts:
        ctx.add(o, m, uv_scale=2.0, smooth=40, patches=0.3)
    ctx.col_box((-0.33, -0.5, 0), (0.33, 0.5, 1.0))


def xray_unit(ctx: K.Ctx) -> None:
    """Radiographic room: fixed patient table (long axis X) on a pedestal with a Bucky tray and
    handgrips; floor rail behind it carrying the tube stand -- column, counterweight housing,
    horizontal arm, tube housing and collimator with knobs and the light window; HV cables looping
    back over the column; a lead apron on the column hook. Worn: apron on the floor, cables chewed,
    dust."""
    ped = K.box("pedestal", (0.6, 0.45, 0.68), center=(0, 0, 0.34), bevel=0.02)
    top = K.box("tabletop", (2.0, 0.65, 0.06), center=(0, 0, 0.71), bevel=0.012)
    pad = K.box("tablepad", (1.8, 0.55, 0.03), center=(0, 0, 0.755), bevel=0.012)
    bucky = K.box("bucky", (0.5, 0.5, 0.08), center=(0.1, 0.0, 0.64), bevel=0.006)
    ctx.add(ped, "road_paint_beige", uv_scale=1.0, patches=0.4, low=0.6)
    ctx.add(top, "road_paint_beige", uv_scale=1.0, patches=0.4)
    ctx.add(pad, "road_vinyl_black", uv_scale=1.5, smooth=35, patches=0.3)
    ctx.add(bucky, "road_steel_dark", uv_scale=1.5)
    for s in (-1, 1):
        g = K.tube(ctx.uid("grip"), [(s * 0.6, -0.33, 0.7), (s * 0.6, -0.38, 0.76), (s * 0.4, -0.38, 0.76), (s * 0.4, -0.33, 0.7)], 0.01, segs=6)
        ctx.add(g, "road_chrome", uv_scale=2.0)
    rail = K.box("rail", (2.3, 0.18, 0.05), center=(0, 0.55, 0.025))
    ctx.add(rail, "road_steel_dark", uv_scale=1.0, patches=0.5)
    cx = -0.25
    carr = K.box("carriage", (0.36, 0.3, 0.16), center=(cx, 0.55, 0.13), bevel=0.01)
    col = K.box("column", (0.18, 0.22, 2.0), center=(cx, 0.55, 0.21 + 1.0), bevel=0.01)
    cw = K.box("counterweight", (0.14, 0.12, 0.6), center=(cx, 0.69, 1.3), bevel=0.01)
    ctx.add(carr, "road_paint_beige", uv_scale=1.0, patches=0.4)
    ctx.add(col, "road_paint_beige", uv_scale=1.0, patches=0.4)
    ctx.add(cw, "road_paint_grey", uv_scale=1.0, patches=0.4)
    arm = K.box("arm", (0.14, 0.62, 0.14), center=(cx, 0.17, 1.62), bevel=0.01)
    ctx.add(arm, "road_paint_beige", uv_scale=1.0, patches=0.4)
    tube = K.cyl("tubehousing", 0.11, 0.46, segs=16, axis="X", center=(cx, -0.04, 1.5))
    caps = [K.cyl(ctx.uid("tubecap"), 0.115, 0.04, segs=16, axis="X", center=(cx + s * 0.25, -0.04, 1.5)) for s in (-1, 1)]
    coll = K.box("collimator", (0.2, 0.2, 0.18), center=(cx, -0.04, 1.3), bevel=0.012)
    window = K.box("lightwin", (0.12, 0.12, 0.006), center=(cx, -0.04, 1.207))
    knobs = [K.cyl(ctx.uid("knob"), 0.015, 0.02, segs=8, axis="Y", center=(cx + k * 0.06 - 0.03, -0.145, 1.33)) for k in range(2)]
    handle = K.tube("collhandle", [(cx - 0.12, -0.12, 1.25), (cx - 0.12, -0.18, 1.25), (cx + 0.12, -0.18, 1.25), (cx + 0.12, -0.12, 1.25)],
                    0.01, segs=6)
    ctx.add(tube, "road_paint_beige", uv="cyl", uv_axis=0, uv_scale=1.0, smooth=40, patches=0.4)
    for c in caps:
        ctx.add(c, "road_steel_dark", uv_scale=1.5, smooth=40)
    ctx.add(coll, "road_paint_grey", uv_scale=1.5, patches=0.4)
    ctx.add(window, "road_glass", uv_scale=1.0, patches=0.0, ao=False)
    for k in knobs:
        ctx.add(k, "road_plastic_black", uv_scale=2.0)
    ctx.add(handle, "road_chrome", uv_scale=2.0)
    _face(ctx, "xlabel", 0.1, 0.1, _rect(ATLAS_GAS, "xray_label"), GAS, (cx, -0.142, 1.42), nu=1, nv=1, ao=False)
    dr = ctx.drnd("cable")
    for k, s in enumerate((-1, 1)):
        pts = [Vector((cx + s * 0.27, -0.04, 1.5)), Vector((cx + s * 0.32, 0.1, 1.75)), Vector((cx + s * 0.12, 0.5, 2.1)),
               Vector((cx + s * 0.1, 0.72, 2.0)), Vector((cx + s * 0.15, 0.78, 1.0)), Vector((cx + s * 0.25, 0.8, 0.04))]
        if ctx.worn and k == 1:
            pts = pts[:4] + [Vector((cx + 0.2, 0.85, 1.6))]
        cab = K.tube(ctx.uid("hvcable"), pts, 0.02, segs=8)
        ctx.add(cab, "road_rubber", uv_scale=2.0, smooth=40)
    if not ctx.worn:
        ap = K.quad_sheet("apron", (cx - 0.25, 0.43, 1.75), (cx + 0.25, 0.43, 1.75), (cx + 0.27, 0.42, 0.95), (cx - 0.27, 0.42, 0.95), 4, 6)
        K.crumple(ap, 0.015, scale=4.0, seed=2)
        hook = K.cyl("aphook", 0.012, 0.1, segs=6, axis="Y", center=(cx, 0.48, 1.78))
        ctx.add(hook, "road_chrome", uv_scale=2.0)
    else:
        ap = K.quad_sheet("apron", (0.6, -0.8, 0.02), (1.1, -0.75, 0.02), (1.05, -0.2, 0.03), (0.55, -0.25, 0.02), 4, 6)
        K.crumple(ap, 0.03, scale=4.0, seed=2)
        K.lift_min(ap)
    K.solidify(ap, 0.01, offset=0.0, even=False)
    ctx.add(ap, "road_vinyl_blue", uv_scale=1.5, smooth=50, patches=0.2)
    for o in ctx.parts:  # centre the table + rail footprint on the origin (PropDef collision box)
        o.data.transform(Matrix.Translation((0, -0.2, 0)))
        o.data.update()
    ctx.col_box((-1.0, -0.55, 0), (1.0, 0.55, 2.22))


def waiting_chairs(ctx: K.Ctx) -> None:
    """Three linked waiting-room chairs on a steel beam and T-legs: orange vinyl seat and back
    cushions on moulded shells, chrome loop arms. Worn: a cushion split to the foam, gum and
    cigarette burns. Destroyed: the end chair wrenched off the beam and lying tipped."""
    pitch = 0.58
    beam = K.box("beam", (1.74, 0.06, 0.05), center=(0, 0.02, 0.3))
    ctx.add(beam, "road_steel_dark", uv_scale=1.0, patches=0.5)
    for s in (-1, 1):
        lg = K.box(ctx.uid("leg"), (0.05, 0.05, 0.28), center=(s * 0.62, 0.02, 0.14))
        ft = K.box(ctx.uid("foot"), (0.05, 0.56, 0.03), center=(s * 0.62, 0.02, 0.015), bevel=0.008)
        ctx.add(lg, "road_steel_dark", uv_scale=1.5)
        ctx.add(ft, "road_steel_dark", uv_scale=1.5)
    dr = ctx.drnd("c")
    for k in range(3):
        x = (k - 1) * pitch
        grp = []
        shell = K.box(ctx.uid("shell"), (0.5, 0.46, 0.03), center=(x, -0.02, 0.4), bevel=0.01)
        cush = K.box(ctx.uid("cushion"), (0.48, 0.44, 0.06), center=(x, -0.02, 0.445), bevel=0.025, bevel_segs=2)
        bshell = K.box(ctx.uid("bshell"), (0.5, 0.03, 0.42), center=(x, 0.2, 0.68), bevel=0.01)
        bcush = K.box(ctx.uid("bcushion"), (0.46, 0.05, 0.36), center=(x, 0.17, 0.69), bevel=0.02, bevel_segs=2)
        for o in (bshell, bcush):
            K.place(o, (-x, -0.2, -0.45))
            K.place(o, rot=(-8, 0, 0))
            K.place(o, (x, 0.2, 0.45))
        stem = K.box(ctx.uid("stem"), (0.04, 0.04, 0.1), center=(x, 0.02, 0.35))
        grp = [(shell, "road_plastic_brown"), (bshell, "road_plastic_brown"), (stem, "road_steel_dark")]
        split = ctx.worn and k == 1
        if split:
            K.subdivide(cush, 1)
            K.jagged_hole(cush, (x + 0.05, -0.02, 0.475), 0.09, dr.randint(0, 999), axis=2)
            foam = K.box(ctx.uid("foam"), (0.4, 0.36, 0.04), center=(x, -0.02, 0.44))
            grp.append((foam, "road_foam"))
        grp += [(cush, "road_vinyl_orange"), (bcush, "road_vinyl_orange")]
        if ctx.destroyed and k == 2:
            for o, _ in grp:
                o.data.transform(Matrix.Translation((x + 0.35, -0.45, 0.0)) @ K.rot_matrix((0, -75, 20)) @ Matrix.Translation((-x, 0.0, -0.3)))
                o.data.update()
            zmin = min(min(v.co.z for v in o.data.vertices) for o, _ in grp)
            for o, _ in grp:
                o.data.transform(Matrix.Translation((0, 0, -zmin)))
                o.data.update()
        for o, m in grp:
            ctx.add(o, m, uv_scale=1.5, smooth=35, patches=0.4)
    for k in range(4):
        x = -0.87 + k * pitch
        if ctx.destroyed and k == 3:
            continue
        arm = K.tube(ctx.uid("arm"), [(x, 0.08, 0.33), (x, 0.06, 0.62), (x, -0.16, 0.62), (x, -0.18, 0.42)], 0.012, segs=6)
        pad = K.box(ctx.uid("armpad"), (0.05, 0.22, 0.025), center=(x, -0.05, 0.635), bevel=0.008)
        ctx.add(arm, "road_chrome", uv_scale=2.0, smooth=40)
        ctx.add(pad, "road_plastic_black", uv_scale=2.0)
    ctx.col_box((-0.88, -0.27, 0), (0.88, 0.3, 0.9))


def staff_locker(ctx: K.Ctx) -> None:
    """Bank of three steel staff lockers: louvred doors with lift latches and brass number plates,
    a padlock on the middle one, base kick. Worn: the third door hanging open on a coat and a bag.
    Destroyed: doors pried and dented, one torn off on the floor."""
    W, Dp, H = 0.9, 0.45, 1.83
    car = K.box("carcass", (W, Dp, H - 0.1), center=(0, 0, 0.1 + (H - 0.1) / 2), bevel=0.006)
    K.delete_faces(car, lambda c, n: n.y < -0.9)
    ctx.add(car, "road_paint_lockers", uv_scale=1.0, patches=0.5, low=0.7)
    kick = K.box("kick", (W - 0.02, Dp - 0.04, 0.1), center=(0, 0.02, 0.05))
    ctx.add(kick, "road_steel_dark", uv_scale=1.0)
    inner = K.box("inner", (W - 0.02, 0.01, H - 0.12), center=(0, Dp / 2 - 0.01, 0.1 + (H - 0.12) / 2))
    ctx.add(inner, "road_paint_grey", uv_scale=1.0)
    dr = ctx.drnd("lk")
    dw = W / 3
    for k in range(3):
        cx = -W / 2 + dw * (k + 0.5)
        hx = cx - dw / 2 + 0.01
        door = K.box(ctx.uid("door"), (dw - 0.012, 0.018, H - 0.14), center=(cx, -Dp / 2 - 0.009, 0.12 + (H - 0.14) / 2), bevel=0.004,
                     cuts=(1, 0, 3))
        if ctx.destroyed:
            K.dent(door, (cx, -Dp / 2, dr.uniform(0.6, 1.4)), 0.15, 0.025)
        grp = [(door, "road_paint_lockers")]
        for zz in (1.5, 0.35):
            for j in range(5):
                sl = K.box(ctx.uid("slot"), (0.18, 0.012, 0.012), center=(cx, -Dp / 2 - 0.016, zz + j * 0.035))
                grp.append((sl, "road_steel_dark"))
        latch = K.box(ctx.uid("latch"), (0.03, 0.03, 0.12), center=(cx + dw / 2 - 0.05, -Dp / 2 - 0.03, 1.0), bevel=0.006)
        grp.append((latch, "road_chrome"))
        num = K.quad_sheet(ctx.uid("num"), (-0.03, 0, -0.03), (0.03, 0, -0.03), (0.03, 0, 0.03), (-0.03, 0, 0.03), 1, 1)
        K.uv_planar(num, 1, rect=_room_number_rect(k + 1))
        K.place(num, (cx, -Dp / 2 - 0.0195, 1.68))
        grp.append((num, MOTEL))
        open_ = ctx.worn and not ctx.destroyed and k == 2
        torn = ctx.destroyed and k == 0
        if open_:
            for o, _ in grp:
                o.data.transform(Matrix.Translation((hx, -Dp / 2, 0)) @ K.rot_matrix((0, 0, -110)) @ Matrix.Translation((-hx, Dp / 2, 0)))
                o.data.update()
            coat = K.box("coat", (0.22, 0.18, 0.8), center=(cx, 0.0, 1.15), bevel=0.06, bevel_segs=2)
            K.crumple(coat, 0.02, scale=5.0, seed=6)
            ctx.add(coat, "road_canvas", uv_scale=2.0, smooth=50, patches=0.2)
            bag = K.box("bag", (0.24, 0.16, 0.2), center=(cx, 0.0, 0.25), bevel=0.04)
            ctx.add(bag, "road_vinyl_black", uv_scale=2.0, smooth=40)
        if torn:
            for o, _ in grp:
                o.data.transform(Matrix.Translation((-0.1, -0.85, 0.0)) @ K.rot_matrix((-90, 0, 10)) @ Matrix.Translation((-cx, Dp / 2, -0.12)))
                o.data.update()
            zmin = min(min(v.co.z for v in o.data.vertices) for o, _ in grp)
            for o, _ in grp:
                o.data.transform(Matrix.Translation((0, 0, -zmin)))
                o.data.update()
        for o, m in grp:
            ctx.add(o, m, uv=None if m == MOTEL else "box", uv_scale=1.0, patches=0.5, ao=m != MOTEL)
        if k == 1 and not ctx.destroyed:
            _padlock(ctx, Vector((cx + dw / 2 - 0.05, -Dp / 2 - 0.05, 0.93)))
    ctx.col_box((-W / 2, -Dp / 2 - 0.02, 0), (W / 2, Dp / 2, H))


def sharps_bin(ctx: K.Ctx) -> None:
    """Clinic floor waste bin: red step-on can with a hinged lid and biohazard-red liner tucked
    over the rim. Worn: lid stuck open, liner torn."""
    prof = [(0.0, 0.0), (0.15, 0.0), (0.16, 0.02), (0.165, 0.5), (0.155, 0.52), (0.0, 0.52)]
    can = K.lathe("can", prof, segs=14)
    ctx.add(can, "road_plastic_red", uv="cyl", uv_scale=2.0, smooth=40, patches=0.4)
    lid = K.cyl("lid", 0.17, 0.03, segs=14, center=(0, 0, 0.0))
    if ctx.worn:
        K.place(lid, (0, -0.16, 0))
        K.place(lid, rot=(-100, 0, 0))
        K.place(lid, (0, 0.16, 0.54))
        liner = K.lathe("liner", [(0.16, 0.0), (0.17, 0.03), (0.15, -0.08)], segs=14, cap_bottom=False, cap_top=False)
        K.place(liner, (0, 0, 0.52))
        ctx.add(liner, "road_trash_yellow", uv_scale=2.0, smooth=50)
    else:
        K.place(lid, (0, 0, 0.535))
    ctx.add(lid, "road_plastic_red", uv_scale=2.0, smooth=40, patches=0.4)
    pedal = K.box("pedal", (0.12, 0.08, 0.02), center=(0, -0.18, 0.03), bevel=0.005)
    ctx.add(pedal, "road_steel_dark", uv_scale=2.0)
    ctx.col_box((-0.17, -0.2, 0), (0.17, 0.17, 0.56))


def mop_bucket(ctx: K.Ctx) -> None:
    """Yellow janitor's mop bucket on casters with a side-press wringer and a string mop standing in
    it. Worn: grey water scum line, mop on the floor beside it."""
    body = K.box("body", (0.55, 0.38, 0.32), center=(0, 0, 0.08 + 0.16), bevel=0.04, bevel_segs=2)
    K.delete_faces(body, lambda c, n: n.z > 0.9)
    K.solidify(body, 0.008, offset=-1.0)
    ctx.add(body, "road_plastic_yellow", uv_scale=1.5, smooth=30, patches=0.4)
    water = K.box("water", (0.5, 0.33, 0.004), center=(0, 0, 0.3))
    ctx.add(water, "road_water_grey", uv_scale=1.0, patches=0.0, ao=False)
    for sx in (-1, 1):
        for sy in (-1, 1):
            w = K.cyl(ctx.uid("wheel"), 0.035, 0.025, segs=10, axis="X", center=(sx * 0.22, sy * 0.14, 0.035))
            ctx.add(w, "road_plastic_black", uv_scale=2.0)
    wr = K.box("wringer", (0.22, 0.3, 0.2), center=(0.15, 0.0, 0.48), bevel=0.02)
    lever = K.tube("lever", [(0.25, 0.12, 0.55), (0.3, 0.14, 0.8), (0.28, 0.12, 1.0)], 0.012, segs=6)
    ctx.add(wr, "road_plastic_grey", uv_scale=1.5, patches=0.4)
    ctx.add(lever, "road_steel", uv_scale=2.0)
    if not ctx.worn:
        handle = K.cyl("mophandle", 0.012, 1.35, segs=8, center=(-0.1, 0.0, 0.28 + 0.675))
        K.place(handle, (0.1, 0, -0.28))
        K.place(handle, rot=(0, 8, 0))
        K.place(handle, (-0.1, 0, 0.28))
        head = K.blob("mophead", 0.12, subdiv=2, scale=(1.0, 1.0, 0.8), rough=0.5, seed=4, center=(-0.12, 0.0, 0.3))
    else:
        handle = K.cyl("mophandle", 0.012, 1.35, segs=8, axis="X", center=(-0.35, -0.45, 0.02))
        head = K.blob("mophead", 0.12, subdiv=2, scale=(1.0, 1.2, 0.4), rough=0.5, seed=4, center=(-1.1, -0.45, 0.04))
    ctx.add(handle, "road_paint_blue", uv_scale=2.0, smooth=40)
    ctx.add(head, "road_rag", uv_scale=2.0, smooth=50, patches=0.0)
    ctx.col_box((-0.3, -0.2, 0), (0.3, 0.2, 0.58))


# ============================================================================================
# Wall-mounted lettered pieces (origin on the wall plane, bottom centre; faces -Y)
# ============================================================================================

def _plaque(ctx, rect, mat, w, h, *, t=0.018, frame=None, screws=True, bevel=0.004):
    board = K.box("board", (w, t, h), center=(0, -t / 2, h / 2), bevel=bevel)
    ctx.add(board, frame or "road_paint_black", uv_scale=1.0, patches=0.4, ao=False)
    _face(ctx, "face", w - 0.01, h - 0.01, rect, mat, (0, -t - 0.001, h / 2), nu=2, nv=2, ao=False)
    if screws:
        _bolts(ctx, [(sx * (w / 2 - 0.025), -t - 0.001, sz) for sx in (-1, 1) for sz in (0.025, h - 0.025)], normal="-y", r=0.006,
               h=0.003)
    if ctx.worn:
        for o in ctx.parts:
            o.data.transform(Matrix.Translation((-w / 2 + 0.025, 0, h - 0.025)) @ K.rot_matrix((0, -6, 0))
                             @ Matrix.Translation((w / 2 - 0.025, 0, -(h - 0.025))))
            o.data.update()
    ctx.col_box((-w / 2, -t, 0), (w / 2, 0, h))


def _make_plaque(table, cell, w, h, mat_atlas, frame=None):
    def fn(ctx: K.Ctx) -> None:
        _plaque(ctx, _rect(table, cell), mat_atlas, w, h, frame=frame)
    fn.__doc__ = f"Wall plaque ({cell}): {w} x {h} m board with its lettered face, screws; worn hangs crooked."
    return fn


def _make_room_number(n: int):
    def fn(ctx: K.Ctx) -> None:
        plate = K.box("plate", (0.13, 0.008, 0.13), center=(0, -0.004, 0.065), bevel=0.003)
        ctx.add(plate, "road_brass", uv_scale=2.0, patches=0.3, ao=False)
        _face(ctx, "num", 0.125, 0.125, _room_number_rect(n), MOTEL, (0, -0.0085, 0.065), nu=1, nv=1, ao=False)
        ctx.col_box((-0.065, -0.01, 0), (0.065, 0.0, 0.13))
    fn.__doc__ = f"Brass door number plate {n}."
    return fn


def _make_plywood(i: int):
    def fn(ctx: K.Ctx) -> None:
        """Spray-painted plywood sheet nailed flat to a wall or door (2.44 x 1.22 m). Worn: a corner
        split off, delaminating edges."""
        W, H, T = 2.44, 1.22, 0.018
        sheet = K.quad_sheet("sheet", (-W / 2, 0, 0), (W / 2, 0, 0), (W / 2, 0, H), (-W / 2, 0, H), 8, 4)
        K.uv_planar(sheet, 1, rect=_spray_rect(i))
        if ctx.worn:
            K.jagged_hole(sheet, (W / 2 - 0.05, 0, 0.05), 0.35, ctx.drnd("corner").randint(0, 999), axis=1, jag=0.5)
        K.place(sheet, (0, -T, 0))
        ctx.add(sheet, SPRAY, uv=None, patches=0.3, wear=0.6, ao=False)
        edge = K.box("edge", (W, T, H), center=(0, -T / 2, H / 2))
        K.delete_faces(edge, lambda c, n: abs(n.y) > 0.9)
        ctx.add(edge, "road_plywood", uv_scale=2.0, patches=0.5)
        back = K.quad_sheet("back", (W / 2, 0, 0), (-W / 2, 0, 0), (-W / 2, 0, H), (W / 2, 0, H), 1, 1)
        ctx.add(back, "road_plywood", uv_scale=1.0, patches=0.5, ao=False)
        nails = [(x, -T - 0.001, z) for x in (-1.15, -0.4, 0.4, 1.15) for z in (0.06, H - 0.06)]
        _bolts(ctx, nails, normal="-y", r=0.006, h=0.003, mat="road_steel_dark", segs=5)
        ctx.col_box((-W / 2, -T, 0), (W / 2, 0, H))
    return fn


def xray_viewer(ctx: K.Ctx) -> None:
    """Wall-mounted x-ray lightbox (two panels) still holding Patient 1's chest films a week apart
    -- the second one white with the Bloom. Worn: one film fallen out, diffuser cracked."""
    W, H, Dp = 0.98, 0.56, 0.08
    case = K.box("case", (W, Dp, H), center=(0, -Dp / 2, H / 2), bevel=0.008)
    ctx.add(case, "road_paint_beige", uv_scale=1.0, patches=0.4, ao=False)
    diff = K.quad_sheet("diffuser", (-W / 2 + 0.03, 0, 0.03), (W / 2 - 0.03, 0, 0.03), (W / 2 - 0.03, 0, H - 0.03), (-W / 2 + 0.03, 0, H - 0.03),
                        2, 2)
    K.place(diff, (0, -Dp - 0.001, 0))
    ctx.add(diff, "road_lens_frost", uv_scale=1.0, patches=0.0, ao=False)
    films = _rect(ATLAS_MOTEL, "xray_films")
    for k in range(2):
        if ctx.worn and k == 0:
            continue  # this film slid out of the clip (the scatter of a POI can put it on the floor)
        sub = _rect(ATLAS_MOTEL, "xray_films", (k * 0.5, 0.0, (k + 1) * 0.5, 1.0))
        _face(ctx, ctx.uid("film"), W / 2 - 0.05, H - 0.07, sub, MOTEL, ((k - 0.5) * (W / 2), -Dp - 0.003, H / 2), nu=1, nv=1, ao=False)
    clip = K.box("clip", (W - 0.06, 0.012, 0.025), center=(0, -Dp - 0.006, H - 0.03))
    ctx.add(clip, "road_chrome", uv_scale=2.0, ao=False)
    sw = K.box("switch", (0.03, 0.02, 0.04), center=(W / 2 - 0.05, -Dp - 0.01, 0.06), bevel=0.004)
    ctx.add(sw, "road_plastic_black", uv_scale=2.0, ao=False)
    ctx.col_box((-W / 2, -Dp, 0), (W / 2, 0, H))


def eye_chart(ctx: K.Ctx) -> None:
    """Snellen eye chart on a board with a chrome hanging wire. Worn: corner curled, stained."""
    W, H = 0.3, 0.6
    board = K.box("board", (W, 0.006, H), center=(0, -0.003, H / 2))
    ctx.add(board, "road_cardboard", uv_scale=2.0, patches=0.3, ao=False)
    sheet = K.quad_sheet("chart", (-W / 2 + 0.005, 0, 0.005), (W / 2 - 0.005, 0, 0.005), (W / 2 - 0.005, 0, H - 0.005), (-W / 2 + 0.005, 0, H - 0.005),
                         3, 4)
    K.uv_planar(sheet, 1, rect=_rect(ATLAS_MOTEL, "eye_chart"))
    if ctx.worn:
        K.map_verts(sheet, lambda co: Vector((co.x, co.y - max(0.0, co.x - 0.08) * max(0.0, 0.15 - co.z) * 3.0, co.z)))
    K.place(sheet, (0, -0.0065, 0))
    ctx.add(sheet, MOTEL, uv=None, patches=0.2, ao=False)
    wire = K.tube("wire", [(-0.12, -0.004, H - 0.02), (0.0, -0.002, H + 0.12), (0.12, -0.004, H - 0.02)], 0.002, segs=4)
    ctx.add(wire, "road_chrome", uv_scale=2.0, ao=False)
    ctx.col_box((-W / 2, -0.01, 0), (W / 2, 0, H))


def quarantine_notice(ctx: K.Ctx) -> None:
    """Printed Cordon Medical quarantine notice stapled and taped flat to a door or wall. Worn:
    rain-wrinkled, a corner torn away."""
    W, H = 0.34, 0.51
    sheet = K.quad_sheet("notice", (-W / 2, 0, 0), (W / 2, 0, 0), (W / 2, 0, H), (-W / 2, 0, H), 4, 6)
    K.uv_planar(sheet, 1, rect=_rect(ATLAS_MOTEL, "quarantine"))
    K.crumple(sheet, 0.003 if ctx.clean else 0.008, scale=9.0, seed=12)
    K.map_verts(sheet, lambda co: Vector((co.x, -abs(co.y) - 0.002, co.z)))
    if ctx.worn:
        K.jagged_hole(sheet, (W / 2, 0, 0.0), 0.1, 31, axis=1, jag=0.5)
    ctx.add(sheet, MOTEL, uv=None, smooth=40, patches=0.1, ao=False)
    ctx.col_box((-W / 2, -0.01, 0), (W / 2, 0, H))


def sign_clinic(ctx: K.Ctx) -> None:
    """TAMSIN VALLEY CLINIC fascia sign (3.0 x 0.5 m face) on standoff brackets over the entrance.
    Worn: one end dropped on a sheared bracket."""
    W, H = 3.0, 0.5
    panel = K.box("panel", (W + 0.04, 0.05, H + 0.04), center=(0, -0.12, (H + 0.04) / 2), bevel=0.01)
    grp = [(panel, "road_paint_blue")]
    face = K.quad_sheet("face", (-W / 2, 0, -H / 2), (W / 2, 0, -H / 2), (W / 2, 0, H / 2), (-W / 2, 0, H / 2), 8, 2)
    K.uv_planar(face, 1, rect=_rect(ATLAS_MOTEL, "clinic_sign"))
    K.place(face, (0, -0.147, (H + 0.04) / 2))
    grp.append((face, MOTEL))
    for sx in (-1.2, 1.2):
        br = K.box(ctx.uid("standoff"), (0.05, 0.1, 0.05), center=(sx, -0.05, (H + 0.04) / 2))
        grp.append((br, "road_steel"))
    if ctx.worn:
        for o, _ in grp:
            o.data.transform(Matrix.Translation((-1.2, -0.05, H / 2)) @ K.rot_matrix((0, 9, 0)) @ Matrix.Translation((1.2, 0.05, -H / 2)))
            o.data.update()
    for o, m in grp:
        ctx.add(o, m, uv=None if m == MOTEL else "box", uv_scale=1.0, patches=0.4, ao=False)
    ctx.col_box((-W / 2, -0.15, 0), (W / 2, 0, H + 0.04))


# ============================================================================================
# Registry
# ============================================================================================

BUILDERS = {
    "road_fuel_pump": fuel_pump,
    "road_fuel_pump_vintage": fuel_pump_vintage,
    "road_pump_island": pump_island,
    "road_fuel_canopy": fuel_canopy,
    "road_canopy_column": canopy_column,
    "road_canopy_light": canopy_light,
    "road_air_pump": air_pump,
    "road_ice_freezer": ice_freezer,
    "road_vending_machine": vending_machine,
    "road_newspaper_box": newspaper_box,
    "road_tire_rack": tire_rack,
    "road_tire_stack": tire_stack,
    "road_lift_post": lift_post,
    "road_lift_post_b": lift_post_b,
    "road_tool_chest": tool_chest,
    "road_engine_hoist": engine_hoist,
    "road_oil_drum": oil_drum,
    "road_oil_shelf": oil_shelf,
    "road_rollup_door": rollup_door,
    "road_rollup_door_open": rollup_door_open,
    "road_workbench": workbench,
    "road_creeper": creeper,
    "road_cooler": cooler,
    "road_sign_gas": sign_gas,
    "road_sign_motel": sign_motel,
    "road_motel_bed": motel_bed,
    "road_motel_nightstand": motel_nightstand,
    "road_tv_dresser": tv_dresser,
    "road_housekeeping_cart": housekeeping_cart,
    "road_washer": washer,
    "road_dryer": dryer,
    "road_ice_machine": ice_machine,
    "road_walkway_post": walkway_post,
    "road_suitcase": suitcase,
    "road_exam_table": exam_table,
    "road_medical_cabinet": medical_cabinet,
    "road_iv_stand": iv_stand,
    "road_wheelchair": wheelchair,
    "road_xray_unit": xray_unit,
    "road_waiting_chairs": waiting_chairs,
    "road_staff_locker": staff_locker,
    "road_sharps_bin": sharps_bin,
    "road_mop_bucket": mop_bucket,
    "road_xray_viewer": xray_viewer,
    "road_eye_chart": eye_chart,
    "road_quarantine_notice": quarantine_notice,
    "road_sign_clinic": sign_clinic,
    "road_plaque_office": _make_plaque(ATLAS_MOTEL, "office", 0.9, 0.45, MOTEL),
    "road_plaque_laundry": _make_plaque(ATLAS_MOTEL, "laundry", 0.8, 0.4, MOTEL),
    "road_plaque_rates": _make_plaque(ATLAS_MOTEL, "rates", 0.3, 0.6, MOTEL, frame="road_laminate_dark"),
    "road_plaque_staff": _make_plaque(ATLAS_MOTEL, "staff_only", 0.5, 0.25, MOTEL),
    "road_plaque_ring_bell": _make_plaque(ATLAS_MOTEL, "lobby_strip", 0.6, 0.2, MOTEL),
    "road_plaque_exit": _make_plaque(ATLAS_GAS, "exit_sign", 0.3, 0.3, GAS, frame="road_plastic_white"),
    "road_plaque_clinic_hours": _make_plaque(ATLAS_MOTEL, "clinic_hours", 0.4, 0.4, MOTEL, frame="road_paint_blue"),
}
BUILDERS.update({f"road_room_number_{n}": _make_room_number(n) for n in range(1, 9)})
PLYWOOD = ["sick_inside", "no_gas", "quarantine", "use_bathrooms", "stay_off_walkway", "help_room6", "dead_inside", "gone_to_cordon"]
BUILDERS.update({f"road_plywood_{name}": _make_plywood(i) for i, name in enumerate(PLYWOOD)})


def build(params: dict, outputs: list[str]) -> None:
    K.run(params, outputs, BUILDERS)
