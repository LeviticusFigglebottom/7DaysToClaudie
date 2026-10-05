"""The Remand Program's heavy-lift supply drone (ADR-0023): the coaxial X8 that carries a supply lift
in under the Cordon's colours, and its rotor.

program_drone        Body only, origin at the centre of the airframe, front -Y (Godot +Z), ~2.9 m
                     across the motor axes. A white fibreglass hull with an orange nose and battery
                     bays, black stencils (REMAND SALVAGE PROGRAM, unit RP-HL 09, the Cordon
                     Authority roundel, a big belly number for spotters on the ground), four folding
                     carbon arms with coaxial motor pairs, nav lights (red port, green starboard,
                     white tail and a top strobe), skids, a gimbal camera, GPS and radio masts and a
                     cargo hook with an orange four-leg sling down to the canister's lifting lugs.
program_drone_rotor  One 2-blade carbon rotor (0.96 m) with a faint blur disc, origin at its hub; the
                     game places eight on the motor axes (ROTORS below) and spins them.

Livery decals map cells of the program_livery atlas (textures/gen/program.py LIVERY; keep in sync).
Materials: game/data/materials/program.json."""
from __future__ import annotations

import math

from mathutils import Vector

from lib import props_ext_kit as K

# Rotor hubs (Blender): arms at 45 + 90k degrees, motor axes at radius ARM_R, upper and lower rotor
# planes at +/- ROTOR_Z. Mirrored in game/src/world/program_drone.gd ROTORS.
ARM_R = 1.15
ROTOR_Z = 0.135
ROTOR_R = 0.48
# Livery atlas: cells in 128 px units of the 1024 px program_livery texture.
ATLAS_PX = 1024
UNIT = 128
ATLAS = {
    "side": (0, 0, 8, 1), "side_b": (0, 1, 8, 1), "top": (0, 2, 4, 4), "chevron": (4, 2, 4, 1),
    "caution": (4, 3, 4, 1), "roundel": (4, 4, 2, 2), "plate": (6, 4, 2, 1), "warning": (6, 5, 2, 1),
    "nose": (4, 6, 4, 2), "panel": (0, 6, 4, 2),
}


def _rect(name: str, inset: float = 2.0) -> tuple[float, float, float, float]:
    """Blender UV rect (u0, v0, u1, v1; v up) of an atlas cell."""
    x, y, w, h = [v * UNIT for v in ATLAS[name]]
    x0, y0, x1, y1 = x + inset, y + inset, x + w - inset, y + h - inset
    return (x0 / ATLAS_PX, 1.0 - y1 / ATLAS_PX, x1 / ATLAS_PX, 1.0 - y0 / ATLAS_PX)


def _decal(ctx, name: str, w: float, h: float, cell: str, loc, rot, *, nu: int = 2, nv: int = 2):
    """A livery panel w x h facing -Y with the atlas cell mapped edge to edge, turned by `rot`
    (degrees) and moved to `loc`."""
    o = K.quad_sheet(name, (-w / 2, 0, -h / 2), (w / 2, 0, -h / 2), (w / 2, 0, h / 2), (-w / 2, 0, h / 2), nu, nv)
    K.uv_planar(o, 1, rect=_rect(cell))
    K.place(o, (0, 0, 0), rot)
    K.place(o, loc)
    return ctx.add(o, "program_livery", uv=None, wear=0.5, patches=0.3, edge=0.3)


def _hull_shape(co: Vector) -> Vector:
    """Tapers the nose (y < -0.42) narrower and lower, and the tail a little."""
    t = max(0.0, min(1.0, (-0.42 - co.y) / 0.34))
    s = 1.0 - 0.38 * t * t
    co.x *= s
    co.z = co.z * (1.0 - 0.3 * t * t) - 0.03 * t
    tt = max(0.0, min(1.0, (co.y - 0.5) / 0.25))
    co.x *= 1.0 - 0.12 * tt
    co.z *= 1.0 - 0.15 * tt
    return co


def program_drone(ctx: K.Ctx) -> None:
    ctx.ground_clamp = False
    # --- Hull, belly, nose ------------------------------------------------------------------------
    hull = K.box("hull", (0.66, 1.46, 0.3), center=(0, 0.02, 0.0), bevel=0.09, bevel_segs=3, cuts=(2, 8, 1))
    K.map_verts(hull, _hull_shape)
    ctx.add(hull, "program_white", uv_scale=1.5, smooth=35, patches=0.4, edge=0.8)
    belly = K.box("belly", (0.56, 1.24, 0.06), center=(0, 0.06, -0.17), bevel=0.02, cuts=(1, 4, 0))
    ctx.add(belly, "program_grey", uv_scale=1.5, patches=0.5)
    nose = K.blob("nose", 0.2, subdiv=2, scale=(1.25, 1.1, 0.75), center=(0, -0.63, -0.02))
    K.cut_plane(nose, (0, -0.6, 0), (0, 1, 0), keep="below")
    ctx.add(nose, "program_orange", uv_scale=1.5, smooth=50, patches=0.4)
    # Gimbal camera under the nose.
    yoke = K.box("yoke", (0.16, 0.06, 0.1), center=(0, -0.62, -0.2), bevel=0.01)
    ctx.add(yoke, "program_grey", uv_scale=2.0, patches=0.4)
    cam = K.blob("camball", 0.075, subdiv=2, center=(0, -0.64, -0.29))
    ctx.add(cam, "program_grey", uv_scale=2.0, smooth=50, patches=0.3)
    lens = K.cyl("lens", 0.034, 0.03, segs=14, axis="Y", center=(0, -0.71, -0.29))
    ctx.add(lens, "plastic_black", uv_scale=2.0, smooth=40, wear=0.2)
    # --- Livery --------------------------------------------------------------------------------------
    # Flank bands, the aerial number on top, the big belly number for spotters on the ground, the
    # Cordon roundel behind the batteries, a data plate on the tail and a warning on the belly.
    for sx in (-1, 1):
        _decal(ctx, "side", 0.85, 0.11, "side", (sx * 0.334, 0.07, 0.0), (0, 0, 90 * sx), nu=8, nv=1)
    _decal(ctx, "top", 0.36, 0.36, "top", (0, -0.27, 0.152), (-90, 0, 180), nu=2, nv=2)
    _decal(ctx, "roundel", 0.2, 0.2, "roundel", (0, 0.5, 0.152), (-90, 0, 180), nu=1, nv=1)
    _decal(ctx, "belly09", 0.42, 0.42, "top", (0, -0.3, -0.201), (90, 0, 0), nu=2, nv=2)
    _decal(ctx, "warning", 0.3, 0.15, "warning", (0, 0.45, -0.201), (90, 0, 0), nu=1, nv=1)
    _decal(ctx, "plate", 0.18, 0.09, "plate", (0, 0.734, 0.0), (0, 0, 180), nu=1, nv=1)
    # --- Battery bays, spine, masts, antennas ---------------------------------------------------------
    # Two hot-swap packs sunk into bays either side of a raised spine: grey bay rims, orange packs
    # with black pull handles and a vent strip, a latch at each end.
    spine = K.box("spine", (0.1, 0.7, 0.08), center=(0, 0.2, 0.17), bevel=0.025, bevel_segs=2, cuts=(0, 4, 0))
    ctx.add(spine, "program_white", uv_scale=1.5, smooth=35, patches=0.4, edge=1.0)
    for sx in (-1, 1):
        rim = K.box("bayrim", (0.24, 0.5, 0.03), center=(sx * 0.165, 0.17, 0.145), bevel=0.008)
        ctx.add(rim, "program_grey", uv_scale=2.0, patches=0.5, edge=1.2)
        bat = K.box("battery", (0.21, 0.46, 0.07), center=(sx * 0.165, 0.17, 0.175), bevel=0.012, cuts=(1, 3, 0))
        ctx.add(bat, "program_orange", uv_scale=1.5, patches=0.5, edge=1.0)
        handle = K.tube("pull", [(sx * 0.11, 0.08, 0.21), (sx * 0.11, 0.08, 0.235), (sx * 0.22, 0.08, 0.235), (sx * 0.22, 0.08, 0.21)],
                        0.008, segs=6)
        ctx.add(handle, "plastic_black", uv_scale=2.0, smooth=40, wear=0.5)
        for y in (-0.06, 0.4):
            latch = K.box("latch", (0.06, 0.025, 0.03), center=(sx * 0.165, y, 0.19), bevel=0.004)
            ctx.add(latch, "chrome_pitted", uv_scale=2.0, wear=0.8)
        for k in range(4):
            vent = K.box("batvent", (0.14, 0.008, 0.004), center=(sx * 0.165, 0.26 + k * 0.022, 0.211))
            ctx.add(vent, "plastic_black", uv_scale=2.0, wear=0.2)
    mast = K.cyl("gpsmast", 0.012, 0.18, segs=8, center=(0, 0.48, 0.3))
    ctx.add(mast, "program_grey", uv_scale=2.0)
    puck = K.cyl("gpspuck", 0.06, 0.025, segs=16, center=(0, 0.48, 0.4), bevel=0.006)
    ctx.add(puck, "program_white", uv_scale=2.0, smooth=40)
    # Radio whips on the spine, raked back.
    for sx in (-1, 1):
        whip = K.tube("whip", [(sx * 0.03, 0.05, 0.2), (sx * 0.05, 0.12, 0.42)], [0.006, 0.003], segs=5)
        ctx.add(whip, "plastic_black", uv_scale=2.0, smooth=40)
    # Forward sensor head: a dark window in the nose and a landing light under it.
    window = K.box("sensorwin", (0.2, 0.02, 0.07), center=(0, -0.82, 0.0), bevel=0.012)
    ctx.add(window, "plastic_black", uv_scale=2.0, wear=0.2, patches=0.0)
    lamp = K.cyl("landlight", 0.03, 0.012, segs=12, center=(0, -0.7, -0.115), bevel=0.003)
    ctx.add(lamp, "program_nav_white", uv_scale=1.0, wear=0.0, ao=False)
    # Access hatches and vents down the flanks (the livery atlas' panel cell).
    for sx in (-1, 1):
        _decal(ctx, "hatch", 0.3, 0.1, "panel", (sx * 0.335, -0.27, -0.005), (0, 0, 90 * sx), nu=2, nv=1)
    for sx in (-1, 1):
        ant = K.tube("antenna", [(sx * 0.27, 0.6, -0.08), (sx * 0.34, 0.66, -0.3)], 0.006, segs=6)
        ctx.add(ant, "plastic_black", uv_scale=2.0, smooth=40)
        tip = K.blob("anttip", 0.012, subdiv=1, center=(sx * 0.34, 0.66, -0.3))
        ctx.add(tip, "plastic_black", uv_scale=2.0)
    # --- Arms, motors, lights ------------------------------------------------------------------------
    for k in range(4):
        a = math.radians(45 + 90 * k)
        d = Vector((math.cos(a), math.sin(a), 0.0))
        deg = math.degrees(a)
        tip = d * ARM_R
        front = d.y < 0.0
        # Built along X and turned into place after its UVs are laid (cylindrical about the tube).
        arm = K.tube("arm", [(0.3, 0, 0), (0.6, 0, 0), (ARM_R, 0, 0)], 0.042, segs=10)
        ctx.add(arm, "program_carbon", uv="cyl", uv_axis=0, uv_scale=4.0, smooth=40, patches=0.2, at=((0, 0, 0), (0, 0, deg)))
        hinge = K.box("hinge", (0.13, 0.11, 0.1), center=(0, 0, 0), bevel=0.015)
        K.place(hinge, d * 0.44, (0, 0, math.degrees(a)))
        ctx.add(hinge, "program_grey", uv_scale=2.0, patches=0.5, edge=1.2)
        lock = K.cyl("lock", 0.022, 0.13, segs=10, center=(0, 0, 0))
        K.place(lock, d * 0.44 + Vector((0, 0, 0.0)), (0, 0, 0))
        ctx.add(lock, "chrome_pitted", uv_scale=2.0, smooth=40)
        # Sleeve near the tip: hazard chevrons on the front arms (orientation), white behind.
        sleeve = K.cyl("sleeve", 0.047, 0.2, segs=12, axis="X")
        if front:
            K.uv_cyl(sleeve, axis=0, scale=1.0)
            # map the cylinder's UVs (u around, v along) into the chevron cell
            u0, v0, u1, v1 = _rect("chevron")
            me = sleeve.data
            uvl = me.uv_layers.active.data
            us = [l.uv[0] for l in uvl]
            vs = [l.uv[1] for l in uvl]
            umin, umax, vmin, vmax = min(us), max(us), min(vs), max(vs)
            for l in uvl:
                l.uv = (u0 + (l.uv[0] - umin) / max(umax - umin, 1e-6) * (u1 - u0),
                        v0 + (l.uv[1] - vmin) / max(vmax - vmin, 1e-6) * (v1 - v0))
            ctx.add(sleeve, "program_livery", uv=None, smooth=40, wear=0.5, patches=0.3, at=(tuple(d * 0.92), (0, 0, deg)))
        else:
            ctx.add(sleeve, "program_white", uv="cyl", uv_axis=0, uv_scale=1.5, smooth=40, patches=0.4, at=(tuple(d * 0.92), (0, 0, deg)))
        # Speed controller under the arm, its heat sink finned.
        esc = K.box("esc", (0.16, 0.07, 0.035), center=(0, 0, 0), bevel=0.006)
        ctx.add(esc, "program_grey", uv_scale=2.0, patches=0.4, at=(tuple(d * 0.8 + Vector((0, 0, -0.06))), (0, 0, deg)))
        for f in range(4):
            fin = K.box("escfin", (0.14, 0.004, 0.018), center=(0, 0, 0))
            ctx.add(fin, "chrome_pitted", uv_scale=3.0, wear=0.3,
                    at=(tuple(d * 0.8 + Vector((0, 0, -0.085)) + Vector((-d.y, d.x, 0)) * (-0.024 + f * 0.016)), (0, 0, deg)))
        # Motor mount: a clamp on the arm end and a vertical post through it.
        clamp = K.box("clamp", (0.14, 0.1, 0.1), center=(0, 0, 0), bevel=0.012)
        K.place(clamp, tip, (0, 0, math.degrees(a)))
        ctx.add(clamp, "program_grey", uv_scale=2.0, patches=0.4, edge=1.2)
        post = K.cyl("post", 0.026, 0.2, segs=10, center=tuple(tip))
        ctx.add(post, "program_anodized", uv_scale=2.0, smooth=40)
        for sz in (1, -1):
            # Outrunner bell with cooling slots (alternate faces darker) and a prop adaptor.
            bell = K.lathe("bell", [(0.0, 0.0), (0.072, 0.0), (0.076, 0.012), (0.076, 0.056), (0.064, 0.066), (0.02, 0.07),
                                    (0.0, 0.07)], segs=18)
            if sz < 0:
                K.place(bell, (0, 0, 0), (180, 0, 0))
            K.place(bell, tip + Vector((0, 0, sz * 0.05)))
            ctx.add(bell, "program_anodized", uv="cyl", uv_scale=2.0, smooth=35, patches=0.3)
            band = K.cyl("coil", 0.078, 0.022, segs=18, center=tuple(tip + Vector((0, 0, sz * 0.082))))
            ctx.add(band, "chrome_pitted", uv="cyl", uv_scale=3.0, smooth=35)
            adaptor = K.cyl("adaptor", 0.018, 0.03, segs=10, center=tuple(tip + Vector((0, 0, sz * (ROTOR_Z - 0.012)))))
            ctx.add(adaptor, "chrome_pitted", uv_scale=3.0, smooth=40)
        # Nav light on the arm's end cap between the rotor pair: red port (+X), green starboard,
        # white on the tail arms' undersides too.
        cap = K.blob("navlight", 0.024, subdiv=2, scale=(1.0, 1.0, 0.8), center=tuple(d * (ARM_R + 0.085)))
        ctx.add(cap, "program_nav_red" if d.x > 0 else "program_nav_green", uv_scale=1.0, smooth=50, wear=0.0, ao=False)
        housing = K.cyl("navhousing", 0.03, 0.03, segs=10, axis="X")
        ctx.add(housing, "program_grey", uv_scale=2.0, smooth=40, at=(tuple(d * (ARM_R + 0.06)), (0, 0, deg)))
    strobe = K.blob("strobe", 0.03, subdiv=2, scale=(1, 1, 0.7), center=(0, 0.3, 0.17))
    ctx.add(strobe, "program_nav_white", uv_scale=1.0, smooth=50, wear=0.0, ao=False)
    tail = K.blob("taillight", 0.022, subdiv=2, center=(0, 0.775, -0.05))
    ctx.add(tail, "program_nav_white", uv_scale=1.0, smooth=50, wear=0.0, ao=False)
    # --- Landing gear ----------------------------------------------------------------------------------
    for sx in (-1, 1):
        skid = K.tube("skid", [(sx * 0.36, -0.62, -0.5), (sx * 0.36, -0.55, -0.6), (sx * 0.36, 0.55, -0.6), (sx * 0.36, 0.64, -0.52)],
                      0.022, segs=8)
        ctx.add(skid, "program_carbon", uv="cyl", uv_axis=1, uv_scale=4.0, smooth=40, patches=0.4, edge=1.2)
        for y in (-0.35, 0.4):
            strut = K.tube("strut", [(sx * 0.36, y, -0.6), (sx * 0.31, y, -0.4), (sx * 0.24, y, -0.19)], 0.018, segs=8)
            ctx.add(strut, "program_carbon", uv="cyl", uv_axis=2, uv_scale=4.0, smooth=40, patches=0.3)
            foot = K.box("skidpad", (0.06, 0.12, 0.012), center=(sx * 0.36, y, -0.625))
            ctx.add(foot, "rubber_black", uv_scale=2.0, wear=0.6)
    # --- Cargo hook and sling --------------------------------------------------------------------------
    winch = K.box("winch", (0.2, 0.24, 0.1), center=(0, 0.02, -0.25), bevel=0.015)
    ctx.add(winch, "program_grey", uv_scale=2.0, patches=0.5, edge=1.2)
    hook = K.tube("hook", [(0, 0.0, -0.3), (0, 0.0, -0.36), (0, 0.035, -0.4), (0, 0.07, -0.37)], 0.012, segs=6)
    ctx.add(hook, "chrome_pitted", uv_scale=2.0, smooth=40, wear=0.6)
    ring = K.tube("ring", [(0.03 * math.cos(t), 0.03 * math.sin(t), -0.4) for t in [i * math.tau / 10 for i in range(10)]],
                  0.008, segs=5, closed=True)
    ctx.add(ring, "chrome_pitted", uv_scale=2.0, smooth=40)
    for k in range(4):
        a = math.radians(45 + 90 * k)
        lug = Vector((0.27 * math.cos(a), 0.27 * math.sin(a), -0.86))
        top = Vector((0.02 * math.cos(a), 0.02 * math.sin(a), -0.41))
        leg = K.tube("sling", [top, top.lerp(lug, 0.5) + Vector((0, 0, -0.01)), lug], 0.011, segs=4, flat=(1.0, 0.25))
        ctx.add(leg, "program_webbing", uv="cyl", uv_axis=2, uv_scale=4.0, smooth=40, wear=0.6)
        shackle = K.blob("shackle", 0.016, subdiv=1, center=tuple(lug))
        ctx.add(shackle, "chrome_pitted", uv_scale=2.0)


def program_drone_rotor(ctx: K.Ctx) -> None:
    """2-blade carbon rotor, hub at the origin, blades in the XY plane: tapered and twisted from 18
    degrees at the root to 6 at the tip, with a faint blur disc for when it spins."""
    ctx.ground_clamp = False
    hub = K.cyl("hub", 0.036, 0.034, segs=14, bevel=0.006)
    ctx.add(hub, "program_anodized", uv_scale=2.0, smooth=40)
    cap = K.blob("spinner", 0.03, subdiv=2, scale=(1, 1, 0.6), center=(0, 0, 0.017))
    ctx.add(cap, "program_orange", uv_scale=2.0, smooth=50)
    for side in (1, -1):
        blade = K.box("blade", (ROTOR_R - 0.035, 1.0, 1.0), center=((ROTOR_R + 0.035) / 2, 0, 0), cuts=(10, 2, 0))

        def shape(co: Vector, side=side) -> Vector:
            t = max(0.0, min(1.0, (co.x - 0.035) / (ROTOR_R - 0.035)))
            chord = 0.074 * (1.0 - 0.55 * t) + 0.01 * math.sin(math.pi * min(1.0, t * 3.0))
            thick = 0.012 * (1.0 - 0.6 * t)
            twist = math.radians(18.0 - 12.0 * t)
            y = co.y * chord
            z = co.z * thick
            # Airfoil: a cambered section, the leading edge rounder.
            z += 0.004 * (1.0 - (2.0 * co.y) ** 2) * (1.0 - t * 0.5)
            yy = y * math.cos(twist) - z * math.sin(twist)
            zz = y * math.sin(twist) + z * math.cos(twist)
            return Vector((co.x, yy, zz))
        K.map_verts(blade, shape)
        if side < 0:
            K.place(blade, (0, 0, 0), (0, 0, 180))
        ctx.add(blade, "program_carbon", uv_scale=4.0, smooth=30, patches=0.3, edge=1.4)
        tipband = K.box("tipband", (0.04, 1.0, 1.0), center=(ROTOR_R - 0.025, 0, 0))
        K.map_verts(tipband, lambda co: Vector((co.x, co.y * 0.034, co.z * 0.007 + 0.002)))
        if side < 0:
            K.place(tipband, (0, 0, 0), (0, 0, 180))
        ctx.add(tipband, "program_orange", uv_scale=2.0, patches=0.5)
    blur = K.cyl("blur", ROTOR_R - 0.01, 0.002, segs=40)
    ctx.add(blur, "program_rotor_blur", uv="planar", uv_axis=2, uv_scale=1.0, wear=0.0, ao=False)


BUILDERS = {
    "program_drone": program_drone,
    "program_drone_rotor": program_drone_rotor,
}


def build(params: dict, outputs: list[str]) -> None:
    K.run(params, outputs, BUILDERS)
