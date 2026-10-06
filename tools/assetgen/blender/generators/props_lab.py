"""The Corvane Field Lab (agent Y): props for the game's first tier-5 dungeon, Corvane Mining Co.'s geology field
station that the Cordon took for its forward Bloom lab.

Structures: the prefab lab module and decontamination unit shells (they wrap the POI's kit rooms), the covered
boardwalk's roof, the earth bank the containment block is dug into, the station fence (Y-arms, barbed wire, a
concertina coil), the bay the earlier salvager cut, the chained gate, the station sign and the fence plates, the
diesel tank, the station generator and the core drill rig parked in the yard.
The core shed: steel racking of waxed core boxes, boxes on a pallet with a run of core showing, the diamond core saw
and the geologists' logging bench.
The labs: the epoxy-topped bench with its reagent shelf, the fume hood, the biosafety cabinet, the minus-80
freezer, the centrifuge, the microscope, sample shelving, the nitrogen dewar, the specimen store and the vault's
steel collar, the card reader, the decon shower, the PPE rack, the biohazard bin, the radio desk, the data rack,
the panel light and the red emergency beacon, and the wall signs.

Conventions (docs/ASSET_PIPELINE.md): metres, Z up, front -Y, origin bottom centre (floor props are centred on the
origin: PoiBuilder's collision box is the def's size centred there). Props placed `against` a wall are centred on
their depth (_centre_depth). Wall props: origin on the wall plane, bottom centre, front -Y. Ceiling props: origin
on the ceiling plane, hanging below it. Shells: origin at the kit rooms' plan centre on the ground
(lib.props_outskirts_parts.Room), walls just outside the edge lines, cut where the plan's doors and windows are
(the catalog passes them). Lettered faces map cells of the lab_signs atlas (textures/gen/lab.py: ATLAS below
mirrors its CELLS). 'clean' is the station as the Cordon kept it, 'worn' a season abandoned, 'destroyed' broken.
"""
from __future__ import annotations

import math
import random

from mathutils import Vector

from lib import props_ext_kit as K
from lib import props_ext_parts as P
from lib import props_outskirts_parts as O
from lib import props_wild_parts as W
from lib import materials as MAT

SIGNS = "lab_signs"
UNIT = 256
ATLAS_PX = 2048.0
ATLAS = {
    "station": (0, 0, 6, 2),
    "biohazard": (6, 0, 2, 1.5), "fence_plate": (6, 1.5, 2, 1.5),
    "airlock": (0, 2, 3, 1), "decon": (3, 2, 3, 1),
    "vault": (0, 3, 3, 1), "emergency": (3, 3, 2.5, 1), "containment": (5.5, 3, 2.5, 1.75),
    "core_shed": (0, 4, 4, 1), "freezer": (4, 4, 1.5, 1),
    "mod_prep": (0, 5, 2.8, 1), "mod_micro": (2.8, 5, 2.8, 1), "module_stencil": (5.6, 5, 2.4, 1),
    "mod_cold": (0, 6, 2.8, 1), "mod_admin": (2.8, 6, 2.8, 1), "decon_stencil": (5.6, 6, 2.4, 1),
    "box_ends": (0, 7, 4, 1), "diesel": (4, 7, 2, 1), "genpanel": (6, 7, 2, 1),
}

PANEL = "lab_panel_white"
GREY = "lab_panel_grey"
SKID = "lab_skid_steel"
CAB = "lab_cabinet_grey"
EPOXY = "lab_epoxy"
ENAMEL = "lab_enamel"
STAINLESS = "road_stainless"
STEEL = "road_steel"
DARK = "road_steel_dark"
GLASS = "road_glass"
RUBBER = "tyre_rubber"
GALV = "metal_galvanized"
CONCRETE = "road_concrete"

MAT.PREVIEW_COLORS.update({
    "lab_signs": (0.5, 0.45, 0.35), "lab_panel_white": (0.62, 0.62, 0.58), "lab_panel_grey": (0.3, 0.33, 0.31),
    "lab_skid_steel": (0.1, 0.11, 0.1), "lab_cabinet_grey": (0.45, 0.47, 0.46), "lab_epoxy": (0.03, 0.03, 0.03),
    "lab_enamel": (0.7, 0.7, 0.67), "lab_frost": (0.85, 0.88, 0.9), "lab_tyvek": (0.75, 0.76, 0.74),
    "lab_tyvek_yellow": (0.6, 0.48, 0.1), "lab_waxed_box": (0.42, 0.33, 0.2), "lab_cordon_orange": (0.55, 0.2, 0.06),
    "lab_tank_green": (0.12, 0.17, 0.11), "lab_genset_yellow": (0.5, 0.38, 0.08), "lab_rig_red": (0.3, 0.06, 0.04),
    "lab_earth": (0.25, 0.2, 0.14), "lab_glow_lamp": (0.9, 0.9, 0.85), "lab_glow_red": (0.6, 0.05, 0.03),
    "lab_glow_green": (0.1, 0.6, 0.1), "lab_glow_display": (0.6, 0.15, 0.08),
})


# ============================================================================================
# Helpers
# ============================================================================================

def _rect(name: str, sub=None, inset: float = 2.0) -> tuple[float, float, float, float]:
    """Blender UV rect (u0, v0, u1, v1; v up) of an atlas cell, or of a sub-rectangle given as fractions
    (fx0, fy0, fx1, fy1) of the cell with y measured from the top of the image."""
    x, y, w, h = [v * UNIT for v in ATLAS[name]]
    if sub:
        fx0, fy0, fx1, fy1 = sub
        x, y, w, h = x + fx0 * w, y + fy0 * h, (fx1 - fx0) * w, (fy1 - fy0) * h
    x0, y0, x1, y1 = x + inset, y + inset, x + w - inset, y + h - inset
    return (x0 / ATLAS_PX, 1.0 - y1 / ATLAS_PX, x1 / ATLAS_PX, 1.0 - y0 / ATLAS_PX)


def _face(ctx, name, w, h, rect, loc, rot_z=0.0, *, wear=0.6, patches=0.35, edge=0.6, mat=SIGNS, rot=None):
    """Flat lettered face (w x h) facing -Y with an atlas rect mapped edge to edge; rot_z 180 faces +Y, 90 faces +X."""
    o = K.quad_sheet(name, (-w / 2, 0, -h / 2), (w / 2, 0, -h / 2), (w / 2, 0, h / 2), (-w / 2, 0, h / 2), 2, 2)
    K.uv_planar(o, 1, rect=rect)
    if rot is not None:
        K.place(o, (0, 0, 0), rot)
    K.place(o, (0, 0, 0), (0, 0, rot_z))
    K.place(o, loc)
    return ctx.add(o, mat, uv=None, wear=wear, patches=patches, edge=edge)


def _bx(ctx, name, size, center, mat, *, bevel=0.01, cuts=(0, 0, 0), rot=None, **kw):
    o = K.box(name, size, center=(0, 0, 0), bevel=bevel, cuts=cuts)
    if rot is not None:
        K.place(o, (0, 0, 0), rot)
    K.place(o, center)
    kw.setdefault("uv_scale", 1.0)
    return ctx.add(o, mat, **kw)


def _cy(ctx, name, r, h, center, mat, *, axis="Z", segs=14, r_top=None, smooth=40, **kw):
    o = K.cyl(name, r, h, segs=segs, center=center, axis=axis, r_top=r_top)
    uv_axis = {"X": 0, "Y": 1, "Z": 2}[axis]
    kw.setdefault("uv_scale", 1.0)
    return ctx.add(o, mat, uv="cyl", uv_axis=uv_axis, smooth=smooth, **kw)


def _centre_depth(ctx) -> float:
    """Moves every part so the model's depth (Blender Y) is centred on the origin: a prop placed `against` a
    wall is centred half its depth off the wall, so its back meets the wall face."""
    lo, hi = 1e9, -1e9
    for o in ctx.parts:
        for v in o.data.vertices:
            lo = min(lo, v.co.y)
            hi = max(hi, v.co.y)
    shift = -(lo + hi) * 0.5
    for o in ctx.parts:
        K.place(o, (0, shift, 0))
    return hi - lo


def _bottle(ctx, name, x, y, z, r, h, mat, *, neck=0.35, cap="plastic_black", fallen=False):
    prof = [(0.0, 0.0), (r * 0.92, 0.0), (r, 0.01), (r, h * 0.7), (r * neck, h * 0.86), (r * neck, h)]
    o = K.lathe(name, prof, segs=10, cap_top=True)
    if fallen:
        K.place(o, (0, 0, 0), (90, 0, random.Random(name).uniform(0, 360)))
        K.place(o, (x, y, z + r))
    else:
        K.place(o, (x, y, z))
    ctx.add(o, mat, uv="cyl", uv_axis=2, smooth=40, uv_scale=2.0)
    c = K.cyl(name + "_cap", r * neck * 1.15, h * 0.06, segs=8, center=(0, 0, h + h * 0.03))
    if fallen:
        K.place(c, (0, 0, 0), (90, 0, random.Random(name).uniform(0, 360)))
        K.place(c, (x, y, z + r))
    else:
        K.place(c, (x, y, z))
    ctx.add(c, cap, uv="box", uv_scale=6.0)


def _screws(ctx, name, pts, *, mat=GALV, r=0.007):
    for k, p in enumerate(pts):
        ctx.add(K.cyl(f"{name}{k}", r, 0.006, segs=6, center=p, axis="Y"), mat, uv="box", uv_scale=10.0)


# ============================================================================================
# Shells: the prefab modules and the decon unit
# ============================================================================================

def _shell_walls(ctx, room, ops, *, z0, z1, mat, off=0.12, rib=0.6, skip=()):
    """Ribbed flat panel walls `off` outside a kit room's edge lines from z0 to z1, cut round the openings (side,
    index, kind) with a steel trim; vertical ribs every `rib` metres and a horizontal seam at mid height."""
    for side in ("N", "S", "E", "W"):
        if side in skip:
            continue
        start, along, out = room.side_line(side, off)
        L = room.length(side) + 2 * off
        st = start - along * off
        holes = O.holes_on(side, ops, floor=room.floor)
        holes = [(a + off, b + off, hz0, hz1) for (a, b, hz0, hz1) in holes]
        cuts = sorted({z0, z1} | {max(z0, min(z1, h[2])) for h in holes} | {max(z0, min(z1, h[3])) for h in holes})
        for i in range(len(cuts) - 1):
            za, zb = cuts[i], cuts[i + 1]
            if zb - za < 0.01:
                continue
            for s0, s1 in O.clip_spans(0.0, L, za + 0.001, zb - 0.001, holes, min_len=0.01):
                p0 = st + along * s0
                p1 = st + along * s1
                pan = K.quad_sheet(f"{side}p{i}_{s0:.2f}", (p0.x, p0.y, za), (p1.x, p1.y, za), (p1.x, p1.y, zb), (p0.x, p0.y, zb),
                                   max(1, int((s1 - s0) / 1.0)), max(1, int((zb - za) / 1.0)))
                K.solidify(pan, 0.03, offset=1.0 if side in ("N", "E") else -1.0)
                ctx.add(pan, mat, uv="box", uv_scale=1.0, patches=0.55, low=0.6, low_h=0.8)
        for (a, b, hz0, hz1) in holes:
            for t in (a, b):
                p = st + along * t + out * 0.02
                W.bar(ctx, f"{side}trim{t:.2f}", (p.x, p.y, max(z0, hz0)), (p.x, p.y, min(z1, hz1)), 0.06, 0.05, DARK, up=tuple(out))
            for zz in (hz0, hz1):
                if z0 < zz < z1:
                    pa, pb = st + along * a + out * 0.02, st + along * b + out * 0.02
                    W.bar(ctx, f"{side}trimh{a:.2f}{zz:.1f}", (pa.x, pa.y, zz), (pb.x, pb.y, zz), 0.06, 0.05, DARK, up=tuple(out))
        t = rib
        while t < L - 0.05:
            if not any(a - 0.06 < t < b + 0.06 for (a, b, hz0, hz1) in holes):
                p = st + along * t + out * 0.035
                W.bar(ctx, f"{side}rib{t:.2f}", (p.x, p.y, z0), (p.x, p.y, z1), 0.05, 0.022, mat, up=tuple(out))
            t += rib
        # Mid-height seam strip, broken by the openings.
        zs = z0 + (z1 - z0) * 0.42
        for s0, s1 in O.clip_spans(0.0, L, zs - 0.02, zs + 0.02, holes, min_len=0.05):
            pa, pb = st + along * s0 + out * 0.03, st + along * s1 + out * 0.03
            W.bar(ctx, f"{side}seam{s0:.2f}", (pa.x, pa.y, zs), (pb.x, pb.y, zs), 0.035, 0.012, DARK, up=tuple(out))


def _piers_and_skid(ctx, hw, hd, z_top, *, n_long):
    """Concrete piers under a module's corners and along its length, a steel skid on them and skirting."""
    for k in range(n_long):
        x = -hw + 0.35 + (2 * hw - 0.7) * k / (n_long - 1)
        for sy in (-1, 1):
            _bx(ctx, f"pier{k}{sy}", (0.32, 0.32, z_top - 0.12), (x, sy * (hd - 0.4), (z_top - 0.12) / 2), CONCRETE, bevel=0.02,
                patches=0.6, low=0.8)
            _bx(ctx, f"shim{k}{sy}", (0.22, 0.22, 0.03), (x, sy * (hd - 0.4), z_top - 0.105), "wood_weathered", bevel=0.003)
    for sy in (-1, 1):
        W.section(ctx, f"skid{sy}", (-hw, sy * (hd - 0.4), z_top - 0.06), (hw, sy * (hd - 0.4), z_top - 0.06), W.prof_i(0.12, 0.1, 0.01, 0.008),
                  SKID)


def lab_module_shell(ctx: K.Ctx) -> None:
    """A prefab lab module round a kit room (params w, d, floor, openings): ribbed white panels on a steel skid
    and concrete piers, plywood skirting with a vent, a low gable roof with a drip edge, a rooftop air unit and its
    duct, a vent stack, conduit along the wall to a lamp over the door, the CORVANE FS-2 stencil on both long sides
    (worn: rust runs, a skirting board gone, the stack bent). No collision: the kit walls hold."""
    fh = float(ctx.param("floor", 0.35))
    room = O.Room(int(ctx.param("w", 9)), int(ctx.param("d", 4)), fh)
    ops = [tuple(o) for o in ctx.param("openings", [])]
    z0, z1 = fh - 0.12, fh + 3.0
    _shell_walls(ctx, room, ops, z0=z0, z1=z1, mat=PANEL)
    hw, hd = room.w / 2 + 0.15, room.d / 2 + 0.15
    _piers_and_skid(ctx, hw - 0.1, hd, z0, n_long=4)
    r = ctx.rnd("mod")
    # Skirting boards between the piers (one missing when worn).
    for sy in (-1, 1):
        for k in range(3):
            x0 = -hw + 0.1 + k * (2 * hw - 0.2) / 3
            if ctx.worn and sy < 0 and k == 1:
                continue
            sk = K.box(f"skirt{sy}{k}", ((2 * hw - 0.2) / 3 - 0.02, 0.02, z0 - 0.02), bevel=0.003)
            K.place(sk, (x0 + (2 * hw - 0.2) / 6, sy * (hd - 0.05), (z0 - 0.02) / 2 + 0.01))
            ctx.add(sk, "road_plywood", uv="box", uv_scale=1.0, patches=0.6, low=0.9, low_h=0.3)
    # Roof: two shallow slopes over a drip edge.
    ridge = z1 + 0.32
    for sy in (-1, 1):
        sheet = K.quad_sheet(f"roof{sy}", (-hw - 0.12, 0, ridge), (hw + 0.12, 0, ridge), (hw + 0.12, sy * (hd + 0.14), z1 + 0.04),
                             (-hw - 0.12, sy * (hd + 0.14), z1 + 0.04), 8, 2)
        K.solidify(sheet, 0.05, offset=-1.0 if sy > 0 else 1.0)
        ctx.add(sheet, GREY, uv="box", uv_scale=1.0, patches=0.6)
        W.bar(ctx, f"drip{sy}", (-hw - 0.12, sy * (hd + 0.15), z1 + 0.02), (hw + 0.12, sy * (hd + 0.15), z1 + 0.02), 0.06, 0.08, DARK)
    for sx in (-1, 1):
        tri = K.prism(f"gable{sx}", [(-hd - 0.02, z1 - 0.01), (hd + 0.02, z1 - 0.01), (0, ridge - 0.02)], 0.03, plane="YZ",
                      offset=sx * (hw + 0.02))
        ctx.add(tri, PANEL, uv="box", uv_scale=1.0, patches=0.5)
    # Rooftop air unit at the far end, its duct down through the roof.
    ux = -hw + 1.3
    _bx(ctx, "ac_body", (1.2, 0.95, 0.6), (ux, 0, ridge + 0.26), CAB, bevel=0.03, cuts=(2, 1, 1), patches=0.6)
    fan = W.ring_obj("ac_fan", 0.24, 0.3, 0.03, segs=20)
    K.place(fan, (ux + 0.15, 0, ridge + 0.565))
    ctx.add(fan, DARK, uv="box", uv_scale=3.0)
    grille = K.cyl("ac_grille", 0.25, 0.01, segs=18, center=(ux + 0.15, 0, ridge + 0.56))
    ctx.add(grille, "chainlink", uv="box", uv_scale=4.0)
    for k in range(6):
        _bx(ctx, f"ac_louvre{k}", (0.02, 0.8, 0.04), (ux - 0.61, 0, ridge + 0.06 + k * 0.08), DARK, bevel=0.0, rot=(0, 0, 0))
    # Vent stack with its rain cap (bent when worn).
    lean = (0, 8, 0) if ctx.worn else (0, 0, 0)
    stack = K.cyl("stack", 0.06, 1.0, segs=12, center=(0, 0, 0.5))
    K.place(stack, (0, 0, 0), lean)
    K.place(stack, (hw - 1.4, -0.4, ridge - 0.1))
    ctx.add(stack, GALV, uv="cyl", uv_axis=2, smooth=40)
    cap = K.cyl("stack_cap", 0.13, 0.08, segs=12, center=(0, 0, 1.05), r_top=0.02)
    K.place(cap, (0, 0, 0), lean)
    K.place(cap, (hw - 1.4, -0.4, ridge - 0.1))
    ctx.add(cap, GALV, uv="cyl", uv_axis=2, smooth=40)
    # Conduit and the lamp over each door; the stencil on the long sides.
    for (side, idx, kind) in ops:
        if kind != "door":
            continue
        start, along, out = room.side_line(side, 0.17)
        c = start + along * (idx + 0.5)
        lamp = K.box("door_lamp", (0.22, 0.14, 0.12), bevel=0.02)
        K.orient(lamp, along, (0, 0, 1), c + out * 0.05 + Vector((0, 0, fh + 2.45)))
        ctx.add(lamp, DARK, uv="box", uv_scale=3.0)
        lens = K.box("door_lens", (0.18, 0.02, 0.06))
        K.orient(lens, along, (0, 0, 1), c + out * 0.12 + Vector((0, 0, fh + 2.4)))
        ctx.add(lens, "lab_glow_lamp", uv="box", uv_scale=3.0, ao=False)
        top = c + Vector((0, 0, fh + 2.55))
        W.rod(ctx, "conduit_v", top + out * 0.03, top + out * 0.03 + Vector((0, 0, z1 - fh - 2.6)), 0.012, GALV, segs=6)
        # A small canopy over the door.
        can = K.box("canopy", (1.3, 0.6, 0.04), bevel=0.01)
        K.orient(can, along, (0, 0, 1), c + out * 0.3 + Vector((0, 0, fh + 2.62)))
        ctx.add(can, GREY, uv="box", uv_scale=1.0, patches=0.6)
        for sgn in (-1, 1):
            p = c + along * (sgn * 0.6) + out * 0.02 + Vector((0, 0, fh + 2.6))
            W.rod(ctx, f"canopy_brace{sgn}", p, p + out * 0.55 + Vector((0, 0, 0.0)), 0.012, DARK, segs=5)
    for sy in (-1, 1):
        _face(ctx, f"stencil{sy}", 1.9, 0.8, _rect("module_stencil"), (0.0, sy * (hd + 0.036), z1 - 0.62), 0.0 if sy < 0 else 180.0,
              wear=0.7)
    # Rust runs under the windows and a gas bottle chained by the skirting.
    for k in range(2):
        x = -hw + 0.6 + k * 0.5
        _cy(ctx, f"bottle{k}", 0.11, 1.15, (x, -hd - 0.25, 0.575), "town4_cylinder_grey", segs=12)
        _cy(ctx, f"bottle_cap{k}", 0.05, 0.12, (x, -hd - 0.25, 1.21), DARK, segs=8)
    W.rod(ctx, "bottle_chain", (-hw + 0.4, -hd - 0.12, 0.85), (-hw + 1.3, -hd - 0.12, 0.85), 0.006, "trap_chain", segs=4)
    _ = r


def lab_decon_shell(ctx: K.Ctx) -> None:
    """The Cordon's decontamination unit round its kit rooms (params w, d, floor, openings, skip): ribbed panels
    in Cordon grey, a black-and-yellow band, the DECON stencil, a header tank and pump on the roof with the feed
    down the wall, its back (north) against the containment block."""
    fh = float(ctx.param("floor", 0.35))
    room = O.Room(int(ctx.param("w", 6)), int(ctx.param("d", 4)), fh)
    ops = [tuple(o) for o in ctx.param("openings", [])]
    skip = tuple(ctx.param("skip", ["N"]))
    z0, z1 = fh - 0.12, fh + 3.0
    _shell_walls(ctx, room, ops, z0=z0, z1=z1, mat=GREY, rib=0.5, skip=skip)
    hw, hd = room.w / 2 + 0.15, room.d / 2 + 0.15
    _piers_and_skid(ctx, hw - 0.1, hd - 0.05, z0, n_long=3)
    roof = K.box("roof", (2 * hw + 0.25, 2 * hd + 0.1, 0.08), bevel=0.01, cuts=(4, 2, 0))
    K.place(roof, (0, -0.05, z1 + 0.04))
    ctx.add(roof, GREY, uv="box", uv_scale=1.0, patches=0.6)
    W.bar(ctx, "drip", (-hw - 0.12, -hd - 0.06, z1 + 0.02), (hw + 0.12, -hd - 0.06, z1 + 0.02), 0.06, 0.1, DARK)
    # Header tank and pump.
    _cy(ctx, "tank", 0.55, 1.1, (-hw + 1.0, 0.1, z1 + 0.63), "road_plastic_white", segs=18, patches=0.6)
    _cy(ctx, "tank_lid", 0.2, 0.06, (-hw + 1.0, 0.1, z1 + 1.21), "road_plastic_black", segs=12)
    _bx(ctx, "pump", (0.5, 0.35, 0.35), (-hw + 2.1, 0.0, z1 + 0.255), "town4_pump_blue", bevel=0.02)
    feed = K.tube("feed", [(-hw + 1.55, 0.1, z1 + 0.3), (-hw + 1.85, 0.0, z1 + 0.2), (-hw + 2.1, -hd - 0.08, z1 + 0.15),
                           (-hw + 2.1, -hd - 0.1, fh + 2.4)], 0.025, segs=6)
    ctx.add(feed, "road_plastic_white", uv="box", uv_scale=3.0, smooth=40)
    # The hazard band and the stencils.
    for side, rz, loc in (("S", 0.0, (0.0, -hd - 0.036, z0 + 0.22)),):
        band = _face(ctx, f"band{side}", 2 * hw - 0.1, 0.16, _rect("decon_stencil", (0.0, 0.77, 1.0, 0.92)), loc, rz, wear=0.8)
        _ = band
    _face(ctx, "stencil_s", 1.9, 0.8, _rect("decon_stencil"), (hw - 1.15, -hd - 0.037, z1 - 0.85), 0.0, wear=0.7)
    _face(ctx, "stencil_e", 1.5, 0.63, _rect("decon_stencil"), (hw + 0.037, 0.2, z1 - 0.8), 90.0, wear=0.7)
    # Spent suits in a bin by the door.
    _cy(ctx, "suit_bin", 0.28, 0.7, (-hw + 0.45, -hd - 0.5, 0.35), "road_plastic_red", segs=14, r_top=0.3)
    sb = K.blob("suit_bag", 0.3, subdiv=2, scale=(1.0, 1.0, 0.55), center=(-hw + 0.45, -hd - 0.5, 0.74), rough=0.2, seed=ctx.seed)
    ctx.add(sb, "lab_tyvek_yellow", uv="box", uv_scale=2.0, smooth=50)


# ============================================================================================
# The boardwalk roof, the berm, the wire
# ============================================================================================

def _corrugated(name, L, Wd, *, pitch=0.076, amp=0.018):
    """A corrugated sheet L (x) by Wd (y), corrugations along x, lying flat at z=0."""
    n = max(4, int(Wd / pitch * 4))
    g = K.grid(name, L, Wd, 6, n)
    for v in g.data.vertices:
        v.co.z += amp * math.sin(v.co.y / pitch * math.tau)
    g.data.update()
    return g


def lab_boardwalk_roof(ctx: K.Ctx) -> None:
    """Four metres of the covered boardwalk's roof (2 m deck under it): square steel posts, beams and purlins,
    corrugated sheets on a slight fall, a gutter and downpipe, the conduit and a caged lamp (worn: a sheet lifted
    and bent, the gutter hanging)."""
    hx, hy = 1.12, 2.0
    z_low, z_high = 2.62, 2.82
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.bar(ctx, f"post{sx}{sy}", (sx * hx, sy * (hy - 0.05), 0.0), (sx * hx, sy * (hy - 0.05), z_low if sx > 0 else z_high),
                  0.08, 0.08, GALV, bevel=0.004)
            _bx(ctx, f"base{sx}{sy}", (0.18, 0.18, 0.012), (sx * hx, sy * (hy - 0.05), 0.006), GALV, bevel=0.002)
    for sx in (-1, 1):
        z = z_low if sx > 0 else z_high
        W.bar(ctx, f"beam{sx}", (sx * hx, -hy, z), (sx * hx, hy, z), 0.06, 0.12, GALV, bevel=0.004)
    for k in range(5):
        y = -hy + 0.1 + k * (2 * hy - 0.2) / 4
        W.bar(ctx, f"purlin{k}", (-hx - 0.1, y, z_high + 0.08), (hx + 0.1, y, z_low + 0.08), 0.05, 0.08, GALV)
    fall = math.degrees(math.atan2(z_high - z_low, 2 * hx))
    for k in range(2):
        sh = _corrugated(f"sheet{k}", 2 * hx + 0.4, 2 * hy / 2 + 0.05)
        if ctx.worn and k == 1:
            for v in sh.data.vertices:
                f = max(0.0, (v.co.x + hx) / (2 * hx + 0.4))
                v.co.z += 0.25 * f * f
            sh.data.update()
        K.solidify(sh, 0.004, offset=0.0, even=False)
        K.place(sh, (0, 0, 0), (0, fall, 0))
        K.place(sh, (0, -hy / 2 + k * hy, (z_low + z_high) / 2 + 0.14))
        ctx.add(sh, "farm_corrugated_galv", uv="box", uv_scale=1.0, smooth=None, patches=0.6)
    # Gutter on the low side and its downpipe.
    gut = K.cyl("gutter", 0.06, 2 * hy + 0.1, segs=10, center=(0, 0, 0), axis="Y")
    K.delete_faces(gut, lambda c, n: c.z > 0.01)
    K.solidify(gut, 0.004, offset=0.0, even=False)
    K.place(gut, (0, 0, 0), (0, 0, 0) if not ctx.worn else (6, 0, 0))
    K.place(gut, (hx + 0.27, 0, z_low + 0.08))
    ctx.add(gut, GALV, uv="cyl", uv_axis=1, smooth=40)
    W.rod(ctx, "downpipe", (hx + 0.27, hy - 0.1, z_low + 0.06), (hx + 0.27, hy - 0.1, 0.1), 0.035, GALV, segs=8)
    # Conduit along a beam and the caged lamp under the middle purlin.
    W.rod(ctx, "conduit", (-hx + 0.05, -hy, z_high - 0.08), (-hx + 0.05, hy, z_high - 0.08), 0.012, GALV, segs=6)
    W.rod(ctx, "drop", (-hx + 0.05, 0.0, z_high - 0.08), (0.0, 0.0, z_high + 0.02), 0.01, GALV, segs=6)
    _cy(ctx, "lamp_base", 0.09, 0.06, (0.0, 0.0, z_high - 0.0), DARK, segs=12)
    glob = K.blob("lamp_glass", 0.075, subdiv=2, scale=(1, 1, 1.2), center=(0.0, 0.0, z_high - 0.1))
    ctx.add(glob, "lab_glow_lamp", uv="box", uv_scale=3.0, smooth=50, ao=False)
    for k in range(4):
        a = k * math.pi / 2
        W.rod(ctx, f"cage{k}", (math.cos(a) * 0.09, math.sin(a) * 0.09, z_high - 0.02), (math.cos(a) * 0.09, math.sin(a) * 0.09, z_high - 0.2),
              0.004, DARK, segs=4)
    ring = W.ring_obj("cage_ring", 0.085, 0.095, 0.008, segs=16)
    K.place(ring, (0, 0, z_high - 0.2))
    ctx.add(ring, DARK, uv="box", uv_scale=4.0)


def lab_berm(ctx: K.Ctx) -> None:
    """The hillside the containment block is dug into: an earth bank 6 m long, high (3.2 m) against the wall at the
    back (+Y) and falling away to the front, rounded at its ends where it meets the next one; rocks and roots
    showing, the crown grassed (moss channel)."""
    r = ctx.rnd("berm")
    L, Dp, H = 6.2, 4.6, 3.2
    rings = []
    nx, ny = 14, 12
    for i in range(nx + 1):
        x = -L / 2 + L * i / nx
        end = 1.0 - 0.18 * (abs(x) / (L / 2)) ** 6
        ring = [(x, -Dp / 2, 0.0)]
        for j in range(ny + 1):
            t = j / ny                      # 0 at the front foot, 1 at the wall
            y = -Dp / 2 + Dp * t
            z = H * end * (1.0 - (1.0 - min(1.0, t * 1.35)) ** 2.2)
            ring.append((x, y, z))
        ring.append((x, Dp / 2, 0.0))
        rings.append(ring)
    bank = K.loft("bank", rings, closed_ring=True, cap_start=True, cap_end=True)
    K.noise_disp(bank, 0.12, scale=0.9, seed=ctx.seed)
    ctx.add(bank, "lab_earth", uv="box", uv_scale=0.5, smooth=50, moss=0.85, patches=0.4)
    for k in range(9):
        x = r.uniform(-L / 2 + 0.5, L / 2 - 0.5)
        t = r.uniform(0.1, 0.6)
        z = H * (1.0 - (1.0 - min(1.0, t * 1.35)) ** 2.2) - 0.1
        O.add_stone(ctx, f"rock{k}", (x, -Dp / 2 + Dp * t, z), r.uniform(0.35, 0.8), ctx.seed + k, flat=0.55)
    for k in range(4):
        x = r.uniform(-L / 2 + 0.4, L / 2 - 0.4)
        y = r.uniform(-Dp * 0.3, Dp * 0.1)
        pts = [(x, y, 0.4), (x + r.uniform(-0.3, 0.3), y + 0.3, 0.9), (x + r.uniform(-0.4, 0.4), y + 0.5, 1.5)]
        W.pole(ctx, f"root{k}", pts, 0.04, "w3_log_bark", r_end=0.015, seed=ctx.seed + k, wobble=0.05)


def _fence_bay(ctx, L, *, H=2.2, gap=None):
    """One bay of the station fence: posts on concrete feet with Y-arms, chain-link to a top rail, a bottom tension
    wire, three strands of barbed wire each side of the Y and a concertina coil in it. gap=(x0, x1) leaves the mesh
    out between x0 and x1 (cut). Outward is +Y (the back)."""
    r = ctx.rnd("fence")
    for sx in (-1, 1):
        x = sx * L / 2
        W.rod(ctx, f"post{sx}", (x, 0, -0.02), (x, 0, H + 0.08), 0.03, GALV, segs=8)
        ctx.add(K.cyl(f"foot{sx}", 0.13, 0.12, segs=10, center=(x, 0, 0.06), r_top=0.11), CONCRETE, uv="box", uv_scale=2.0)
        _cy(ctx, f"postcap{sx}", 0.036, 0.04, (x, 0, H + 0.1), GALV, segs=8)
        for sy in (-1, 1):
            W.rod(ctx, f"arm{sx}{sy}", (x, 0, H + 0.06), (x, sy * 0.3, H + 0.46), 0.014, GALV, segs=6)
    W.rod(ctx, "top_rail", (-L / 2, 0, H), (L / 2, 0, H), 0.02, GALV, segs=6)
    W.rod(ctx, "tension", (-L / 2, 0, 0.08), (L / 2, 0, 0.08), 0.004, GALV, segs=4)
    for sy in (-1, 1):
        for k in range(3):
            t = (k + 1) / 3
            y, z = sy * 0.3 * t, H + 0.06 + 0.4 * t
            pts = [(-L / 2, y, z), (0, y, z - 0.015 - r.uniform(0, 0.01)), (L / 2, y, z)]
            ctx.add(K.tube(f"barb{sy}{k}", pts, 0.0028, segs=3), GALV, uv="box", uv_scale=6.0, smooth=40)
            barbs = [K.box(f"barbs{sy}{k}{b}", (0.006, 0.03, 0.006), center=(-L / 2 + 0.1 + b * 0.2, y, z - 0.008)) for b in range(int(L / 0.2))]
            ctx.add(K.merge_parts(barbs, f"barbs{sy}{k}"), GALV, uv="box", uv_scale=8.0)
    pts = []
    n = int(L / 0.018)
    for i in range(n + 1):
        t = i / n
        a = t * L / 0.22 * math.tau
        pts.append((-L / 2 + L * t, math.cos(a) * 0.2, H + 0.42 + math.sin(a) * 0.2))
    ctx.add(K.tube("razor", pts, 0.005, segs=3), GALV, uv="box", uv_scale=6.0, smooth=40, patches=0.6)
    xs = [(-L / 2, L / 2)] if gap is None else [(-L / 2, gap[0]), (gap[1], L / 2)]
    for k, (a, b) in enumerate(xs):
        if b - a < 0.05:
            continue
        mesh = K.quad_sheet(f"mesh{k}", (a, 0, 0.06), (b, 0, 0.06), (b, 0, H - 0.02), (a, 0, H - 0.02), 6, 4)
        if ctx.worn:
            for v in mesh.data.vertices:
                v.co.y -= 0.08 * math.sin(math.pi * (v.co.x + L / 2) / L) * (1.0 - v.co.z / H)
            mesh.data.update()
        ctx.add(mesh, "chainlink", uv=None, patches=0.3)
    return r


def lab_fence(ctx: K.Ctx) -> None:
    """Three metres of the station fence (+Z inside, the Y-arms and the coil over both faces; destroyed: the mesh
    torn from its posts and the coil sagging to the ground)."""
    if ctx.destroyed:
        _fence_bay(ctx, 3.0, gap=(-0.7, 0.9))
        flap = K.quad_sheet("torn", (-0.7, 0, 0.06), (0.1, 0.5, 0.08), (0.2, 0.6, 1.5), (-0.7, 0, 2.15), 3, 4)
        K.crumple(flap, 0.05, seed=ctx.seed)
        ctx.add(flap, "chainlink", uv=None, patches=0.3)
    else:
        _fence_bay(ctx, 3.0)
    # A hazard tag and zip ties here and there.
    _bx(ctx, "tag", (0.1, 0.004, 0.06), (0.9, -0.02, 1.62), "lab_cordon_orange", bevel=0.0)


def lab_fence_cut(ctx: K.Ctx) -> None:
    """A bay cut through with bolt cutters (the earlier salvager's way in): the mesh slit from the ground to the top
    rail and both halves peeled back inward, the coil snipped and hanging, the barbed strands cut, the bolt cutters
    dropped in the grass. No collision."""
    r = _fence_bay(ctx, 3.0, gap=(-1.5, 1.5))
    for sx in (-1, 1):
        x0 = sx * 1.48
        flap = K.quad_sheet(f"flap{sx}", (x0, 0, 0.06), (x0 - sx * 0.85, -0.55, 0.1), (x0 - sx * 0.95, -0.62, 1.9), (x0, 0, 2.14), 4, 6)
        K.crumple(flap, 0.04, seed=ctx.seed + sx)
        ctx.add(flap, "chainlink", uv=None, patches=0.3)
    # The snipped coil hanging in two loops.
    for sx in (-1, 1):
        pts = [(sx * 0.4, 0.15, 2.6), (sx * 0.5, 0.05, 2.0), (sx * 0.35, -0.1, 1.3), (sx * 0.6, -0.15, 0.8)]
        ctx.add(K.tube(f"coil_hang{sx}", pts, 0.006, segs=3), GALV, uv="box", uv_scale=6.0, smooth=40)
    # Bolt cutters in the grass.
    for s in (-1, 1):
        W.rod(ctx, f"cutter_handle{s}", (0.2, -0.6, 0.03), (0.75, -0.6 + s * 0.08, 0.03), 0.013, "plastic_red", segs=6)
    W.bar(ctx, "cutter_jaw", (0.05, -0.6, 0.035), (0.22, -0.6, 0.035), 0.05, 0.025, DARK, bevel=0.004)
    _ = r


def lab_gate(ctx: K.Ctx) -> None:
    """The station's double gate: two leaves of pipe frame and chain-link between heavy posts, barbed wire over
    them, chained and padlocked in the middle, the Corvane plate on the left leaf and the biohazard plate on the
    right (worn: a leaf sagging on its hinge)."""
    L = 5.4
    H = 2.25
    for sx in (-1, 1):
        x = sx * (L / 2 - 0.08)
        W.rod(ctx, f"post{sx}", (x, 0, -0.02), (x, 0, H + 0.5), 0.065, GALV, segs=10)
        _cy(ctx, f"postcap{sx}", 0.075, 0.06, (x, 0, H + 0.53), GALV, segs=10)
        ctx.add(K.cyl(f"foot{sx}", 0.2, 0.14, segs=10, center=(x, 0, 0.07), r_top=0.17), CONCRETE, uv="box", uv_scale=2.0)
    leaf_w = L / 2 - 0.2
    for sx in (-1, 1):
        sag = 0.06 if (ctx.worn and sx > 0) else 0.0
        x_h = sx * (L / 2 - 0.15)
        x_c = sx * 0.04
        frame = [(x_h, 0.08), (x_c, 0.08 - sag), (x_c, H - sag), (x_h, H)]
        for k in range(4):
            a, b = frame[k], frame[(k + 1) % 4]
            W.rod(ctx, f"leaf{sx}{k}", (a[0], 0, a[1]), (b[0], 0, b[1]), 0.022, GALV, segs=8)
        W.rod(ctx, f"brace{sx}", (x_h, 0, 0.12), (x_c, 0, H - 0.05 - sag), 0.016, GALV, segs=6)
        mesh = K.quad_sheet(f"mesh{sx}", (min(x_h, x_c), 0.01, 0.1), (max(x_h, x_c), 0.01, 0.1), (max(x_h, x_c), 0.01, H - 0.02),
                            (min(x_h, x_c), 0.01, H - 0.02), 6, 4)
        ctx.add(mesh, "chainlink", uv=None, patches=0.3)
        for k in range(3):
            z = H + 0.12 + k * 0.12
            ctx.add(K.tube(f"barb{sx}{k}", [(x_h, 0, z), (x_c, 0, z - sag)], 0.003, segs=3), GALV, uv="box", uv_scale=6.0)
        for k in range(2):
            W.rod(ctx, f"hinge{sx}{k}", (x_h + sx * 0.02, 0, 0.3 + k * 1.6), (x_h + sx * 0.1, 0, 0.3 + k * 1.6), 0.03, DARK, segs=8)
        _ = leaf_w
    # Plates.
    _bx(ctx, "plate_l_back", (1.2, 0.012, 0.44), (-1.3, -0.03, 1.45), GREY, bevel=0.003)
    _face(ctx, "plate_l", 1.16, 0.4, _rect("station", (0.0, 0.0, 0.75, 0.42)), (-1.3, -0.037, 1.45), 0.0)
    _bx(ctx, "plate_r_back", (0.62, 0.012, 0.46), (1.25, -0.03, 1.45), GREY, bevel=0.003)
    _face(ctx, "plate_r", 0.6, 0.44, _rect("fence_plate"), (1.25, -0.037, 1.45), 0.0)
    # The chain round both stiles and its padlock.
    pts = [(-0.12, -0.05, 1.12), (0.0, -0.08, 1.05), (0.12, -0.05, 1.12), (0.12, 0.06, 1.2), (-0.12, 0.06, 1.2), (-0.12, -0.05, 1.12)]
    ch = W.chain_obj("chain", pts, link=0.045, wire=0.006)
    ctx.add(ch, "trap_chain", uv="box", uv_scale=8.0, smooth=40)
    _bx(ctx, "padlock", (0.06, 0.03, 0.07), (0.0, -0.09, 0.98), "lock_steel", bevel=0.008)
    W.rod(ctx, "shackle", (-0.02, -0.09, 1.015), (0.02, -0.09, 1.015), 0.006, "lock_steel", segs=6)


def lab_sign_station(ctx: K.Ctx) -> None:
    """The station sign at the gate: a painted steel board in a channel frame between two square posts, the
    Corvane face on the road side and stencilled bracing behind (worn: leaning, a bullet hole or two)."""
    w, h = 2.6, 0.9
    tilt = ctx.drnd("tilt").uniform(2.0, 5.0) if ctx.worn else 0.0
    for sx in (-1, 1):
        W.bar(ctx, f"post{sx}", (sx * (w / 2 + 0.05), 0.04, -0.05), (sx * (w / 2 + 0.05), 0.04, 2.3), 0.08, 0.08, GALV, bevel=0.004)
        ctx.add(K.cyl(f"foot{sx}", 0.16, 0.1, segs=10, center=(sx * (w / 2 + 0.05), 0.04, 0.05)), CONCRETE, uv="box", uv_scale=2.0)
    board = K.box("board", (w, 0.03, h), bevel=0.006, cuts=(4, 0, 2))
    K.place(board, (0, 0, 0), (0, tilt, 0))
    K.place(board, (0, 0.0, 1.75))
    ctx.add(board, "lab_skid_steel", uv="box", uv_scale=1.0, patches=0.5)
    _face(ctx, "face", w - 0.04, h - 0.04, _rect("station"), (0, -0.0165, 0), 0.0, rot=(0, tilt, 0))
    for o in ctx.parts[-1:]:
        K.place(o, (0, 0, 1.75))
    for sx in (-1, 1):
        W.bar(ctx, f"brace{sx}", (sx * (w / 2 - 0.1), 0.03, 1.33), (sx * (w / 2 - 0.1), 0.03, 2.17), 0.04, 0.03, GALV)
    W.bar(ctx, "rail_lo", (-w / 2, 0.035, 1.42), (w / 2, 0.035, 1.42), 0.04, 0.03, GALV)
    W.bar(ctx, "rail_hi", (-w / 2, 0.035, 2.1), (w / 2, 0.035, 2.1), 0.04, 0.03, GALV)


def lab_sign_fence(ctx: K.Ctx) -> None:
    """A biohazard plate wired to the fence at chest height (origin on the ground under it, on the fence's plane;
    worn: a corner torn loose and curled)."""
    w, h, z = 0.6, 0.44, 1.52
    plate = K.box("plate", (w, 0.006, h), bevel=0.002, cuts=(3, 0, 3))
    if ctx.worn:
        for v in plate.data.vertices:
            if v.co.x > w * 0.2 and v.co.z < -h * 0.1:
                f = (v.co.x - w * 0.2) / (w * 0.3) * (-v.co.z - h * 0.1) / (h * 0.4)
                v.co.y -= 0.05 * max(0.0, f)
        plate.data.update()
    K.place(plate, (0, -0.012, z))
    ctx.add(plate, "lab_panel_white", uv="box", uv_scale=2.0, patches=0.5)
    _face(ctx, "face", w - 0.02, h - 0.02, _rect("fence_plate"), (0, -0.0155, z), 0.0)
    for sx in (-1, 1):
        for sz in (-1, 1):
            if ctx.worn and sx > 0 and sz < 0:
                continue
            ring = W.ring_obj(f"tie{sx}{sz}", 0.012, 0.016, 0.004, segs=8)
            K.place(ring, (0, 0, 0), (0, 90, 0))
            K.place(ring, (sx * (w / 2 - 0.03), -0.005, z + sz * (h / 2 - 0.03)))
            ctx.add(ring, "road_plastic_black", uv="box", uv_scale=6.0)


def _wall_sign(ctx: K.Ctx) -> None:
    """A sign screwed to a wall (params cell, w, h; origin on the wall plane, bottom centre, front -Y): a steel or
    plastic plate with rounded corners, its lettered face and four screws (worn: tilted, a corner bent)."""
    cell = str(ctx.param("cell", "biohazard"))
    w, h = float(ctx.param("w", 0.6)), float(ctx.param("h", 0.45))
    t = 0.012
    tilt = ctx.drnd("tilt").uniform(-3.0, 3.0) if ctx.worn else 0.0
    plate = K.box("plate", (w, t, h), bevel=0.004, cuts=(2, 0, 2))
    if ctx.worn:
        for v in plate.data.vertices:
            if v.co.x > w * 0.3 and v.co.z > h * 0.3:
                v.co.y -= 0.02
        plate.data.update()
    K.place(plate, (0, -t / 2, h / 2), (0, tilt, 0))
    ctx.add(plate, "lab_panel_white", uv="box", uv_scale=2.0, patches=0.4)
    _face(ctx, "face", w - 0.012, h - 0.012, _rect(cell), (0, -t - 0.0012, h / 2), 0.0, rot=(0, tilt, 0))
    pts = []
    for sx in (-1, 1):
        for sz in (-1, 1):
            pts.append((sx * (w / 2 - 0.025), -t - 0.003, h / 2 + sz * (h / 2 - 0.025)))
    _screws(ctx, "screw", pts)


# ============================================================================================
# Yard machines: diesel tank, generator, drill rig
# ============================================================================================

def lab_fuel_tank(ctx: K.Ctx) -> None:
    """A double-walled diesel tank on steel saddles in a bund: welded end caps, a level gauge, the fill box and
    vent with its gooseneck, a ladder, a hose reel on the bund's edge and the DIESEL placard on both sides."""
    L, R = 2.5, 0.72
    bund = K.box("bund_floor", (3.2, 1.65, 0.05), center=(0, 0, 0.025))
    ctx.add(bund, DARK, uv="box", uv_scale=1.0, patches=0.6)
    for sx in (-1, 1):
        _bx(ctx, f"bund_end{sx}", (0.04, 1.65, 0.38), (sx * 1.58, 0, 0.19), "lab_tank_green", bevel=0.004)
    for sy in (-1, 1):
        _bx(ctx, f"bund_side{sy}", (3.2, 0.04, 0.38), (0, sy * 0.805, 0.19), "lab_tank_green", bevel=0.004)
    zc = 0.32 + R
    shell = K.cyl("shell", R, L, segs=28, center=(0, 0, zc), axis="X")
    ctx.add(shell, "lab_tank_green", uv="cyl", uv_axis=0, smooth=40, patches=0.6, low=0.6)
    for sx in (-1, 1):
        cap = K.lathe(f"cap{sx}", [(R, 0.0), (R * 0.97, 0.06), (R * 0.75, 0.13), (0.0, 0.16)], segs=28)
        K.place(cap, (0, 0, 0), (0, 90 * sx, 0))
        K.place(cap, (sx * L / 2, 0, zc))
        ctx.add(cap, "lab_tank_green", uv="box", uv_scale=1.0, smooth=40, patches=0.6)
        weld = W.ring_obj(f"weld{sx}", R, R + 0.012, 0.02, segs=28)
        K.place(weld, (0, 0, 0), (0, 90, 0))
        K.place(weld, (sx * L / 2, 0, zc))
        ctx.add(weld, DARK, uv="box", uv_scale=3.0)
    for k, x in enumerate((-0.8, 0.8)):
        sad = K.prism(f"saddle{k}", [(-0.6, 0.05), (0.6, 0.05), (0.55, 0.42), (0.0, 0.33), (-0.55, 0.42)], 0.12, plane="YZ", offset=x)
        ctx.add(sad, DARK, uv="box", uv_scale=2.0, patches=0.6)
    # Top fittings.
    top = zc + R
    _bx(ctx, "fillbox", (0.3, 0.3, 0.16), (0.6, 0.0, top + 0.05), "lab_tank_green", bevel=0.01)
    _cy(ctx, "gauge", 0.07, 0.08, (-0.3, 0.0, top + 0.03), DARK, segs=12)
    dial = K.cyl("gauge_face", 0.055, 0.005, segs=14, center=(-0.3, 0.0, top + 0.072))
    ctx.add(dial, "lab_enamel", uv="box", uv_scale=4.0)
    vent = K.tube("vent", [(-0.9, 0.2, top - 0.02), (-0.9, 0.2, top + 0.55), (-0.82, 0.2, top + 0.68), (-0.72, 0.2, top + 0.6)], 0.025, segs=8)
    ctx.add(vent, GALV, uv="box", uv_scale=3.0, smooth=40)
    # Ladder up the end.
    for sy in (-1, 1):
        W.rod(ctx, f"ladder{sy}", (1.42, sy * 0.18, 0.05), (1.38, sy * 0.18, top + 0.1), 0.014, GALV, segs=6)
    for k in range(5):
        z = 0.3 + k * (top - 0.3) / 5
        W.rod(ctx, f"rung{k}", (1.41, -0.18, z), (1.41, 0.18, z), 0.01, GALV, segs=5)
    # Hose reel on the bund edge with its nozzle.
    _cy(ctx, "reel", 0.22, 0.2, (-1.3, -0.95, 0.6), DARK, axis="Y", segs=16)
    hose = K.lathe("hose_coil", [(0.15, -0.08), (0.2, -0.08), (0.2, 0.08), (0.15, 0.08)], segs=16, close_profile=True)
    K.place(hose, (0, 0, 0), (90, 0, 0))
    K.place(hose, (-1.3, -0.95, 0.6))
    ctx.add(hose, RUBBER, uv="box", uv_scale=3.0, smooth=40)
    W.bar(ctx, "reel_post", (-1.3, -0.85, 0.05), (-1.3, -0.85, 0.5), 0.05, 0.05, DARK)
    for sy in (-1, 1):
        _face(ctx, f"placard{sy}", 0.6, 0.3, _rect("diesel"), (0.0, sy * (R + 0.004), zc), 0.0 if sy < 0 else 180.0, wear=0.8)


def lab_generator(ctx: K.Ctx) -> None:
    """The station generator: a diesel set on a steel skid in a sound-proofed enclosure (doors with hinges and
    handles, louvred ends), the exhaust stack with its rain flap, lifting eyes, the control panel with its hour
    meter and lamp, cables run out under the skid to a junction box (lit: the panel lamp)."""
    L, Dp, H = 3.0, 1.2, 1.75
    for sy in (-1, 1):
        W.section(ctx, f"skid{sy}", (-L / 2 - 0.05, sy * 0.45, 0.07), (L / 2 + 0.05, sy * 0.45, 0.07), W.prof_c(0.14, 0.06, 0.008), SKID)
    body = K.box("body", (L, Dp, H), bevel=0.03, cuts=(4, 2, 2))
    K.place(body, (0, 0, 0.14 + H / 2))
    ctx.add(body, "lab_genset_yellow", uv="box", uv_scale=1.0, patches=0.6, low=0.6)
    # Door seams and handles on both long sides.
    for sy in (-1, 1):
        for k in range(3):
            x = -L / 2 + (k + 0.5) * L / 3
            seam = K.box(f"seam{sy}{k}", (0.01, 0.006, H - 0.2), center=(x + L / 6 - 0.005, sy * (Dp / 2 + 0.002), 0.14 + H / 2))
            ctx.add(seam, DARK, uv="box", uv_scale=4.0)
            hd_ = K.box(f"handle{sy}{k}", (0.03, 0.03, 0.16), bevel=0.006, center=(x + L / 6 - 0.08, sy * (Dp / 2 + 0.02), 0.14 + H * 0.55))
            ctx.add(hd_, DARK, uv="box", uv_scale=4.0)
    # Louvred ends.
    for sx in (-1, 1):
        for k in range(9):
            z = 0.35 + k * 0.15
            lv = K.box(f"louvre{sx}{k}", (0.05, Dp - 0.2, 0.025), center=(0, 0, 0))
            K.place(lv, (0, 0, 0), (0, 30 * sx, 0))
            K.place(lv, (sx * (L / 2 + 0.01), 0, z))
            ctx.add(lv, DARK, uv="box", uv_scale=4.0)
    # Exhaust and lifting eyes.
    top = 0.14 + H
    _cy(ctx, "silencer", 0.14, 0.7, (L / 2 - 0.6, 0.0, top + 0.08), DARK, axis="X", segs=14)
    W.rod(ctx, "stack", (L / 2 - 0.25, 0.0, top + 0.08), (L / 2 - 0.25, 0.0, top + 0.62), 0.06, DARK, segs=12)
    flap = K.cyl("flap", 0.065, 0.01, segs=12, center=(0, 0, 0))
    K.place(flap, (0, 0, 0), (0, 25, 0))
    K.place(flap, (L / 2 - 0.23, 0.0, top + 0.65))
    ctx.add(flap, DARK, uv="box", uv_scale=4.0)
    for sx in (-1, 1):
        eye = W.ring_obj(f"eye{sx}", 0.03, 0.045, 0.02, segs=12)
        K.place(eye, (0, 0, 0), (90, 0, 0))
        K.place(eye, (sx * (L / 2 - 0.2), 0, top + 0.04))
        ctx.add(eye, DARK, uv="box", uv_scale=4.0)
    # The control panel at the front left, its lamp lit on the generator.
    _bx(ctx, "panel_box", (0.55, 0.12, 0.45), (-L / 2 + 0.5, -Dp / 2 - 0.06, top - 0.45), DARK, bevel=0.01)
    _face(ctx, "panel_face", 0.5, 0.25, _rect("genpanel"), (-L / 2 + 0.5, -Dp / 2 - 0.121, top - 0.42), 0.0, wear=0.5)
    lamp = K.box("panel_lamp", (0.08, 0.05, 0.06), bevel=0.01, center=(-L / 2 + 0.5, -Dp / 2 - 0.14, top - 0.13))
    ctx.add(lamp, "lab_glow_lamp", uv="box", uv_scale=4.0, ao=False)
    # Cables to a junction box on a post.
    for k in range(3):
        c = K.tube(f"cable{k}", [(-L / 2 + 0.3, -0.2 + k * 0.08, 0.1), (-L / 2 - 0.3, -0.2 + k * 0.08, 0.03), (-L / 2 - 0.8, 0.1 + k * 0.06, 0.03),
                                 (-L / 2 - 0.9, 0.1 + k * 0.06, 0.7)], 0.018, segs=6)
        ctx.add(c, RUBBER, uv="box", uv_scale=3.0, smooth=40)
    W.bar(ctx, "jb_post", (-L / 2 - 1.0, 0.2, 0.0), (-L / 2 - 1.0, 0.2, 1.1), 0.06, 0.06, GALV)
    _bx(ctx, "jbox", (0.3, 0.14, 0.38), (-L / 2 - 0.9, 0.2, 0.85), "lab_cabinet_grey", bevel=0.01)


def lab_drill_rig(ctx: K.Ctx) -> None:
    """A skid-mounted diamond core drill parked in the yard: the I-beam skid, the power pack with its radiator
    grille and exhaust, the mast laid back on its stand with the drill head and chuck, the rod rack full of rods, a
    water tank and pump, and a stack of empty core trays (worn: rusted, a tray fallen)."""
    r = ctx.rnd("rig")
    L, Wd = 6.0, 2.4
    for sx in (-1, 1):
        W.section(ctx, f"skid{sx}", (sx * (Wd / 2 - 0.15), -L / 2, 0.1), (sx * (Wd / 2 - 0.15), L / 2, 0.1), W.prof_i(0.2, 0.12, 0.012, 0.01), SKID,
                  up=(0, 0, 1))
    for k in range(4):
        y = -L / 2 + 0.3 + k * (L - 0.6) / 3
        W.section(ctx, f"cross{k}", (-Wd / 2 + 0.15, y, 0.12), (Wd / 2 - 0.15, y, 0.12), W.prof_c(0.12, 0.06, 0.008), SKID)
    deck = K.box("deck", (Wd - 0.2, L - 0.2, 0.012), center=(0, 0, 0.215))
    ctx.add(deck, "road_tread", uv="box", uv_scale=1.0, patches=0.6)
    # Power pack at the back.
    _bx(ctx, "pack", (1.8, 1.4, 1.3), (0, L / 2 - 0.85, 0.22 + 0.65), "lab_rig_red", bevel=0.04, cuts=(2, 2, 2), patches=0.7)
    _bx(ctx, "radiator", (1.4, 0.03, 0.9), (0, L / 2 - 0.14, 0.95), DARK, bevel=0.005)
    for k in range(12):
        _bx(ctx, f"fin{k}", (0.01, 0.035, 0.85), (-0.66 + k * 0.12, L / 2 - 0.12, 0.95), "road_steel", bevel=0.0)
    W.rod(ctx, "pack_exhaust", (0.6, L / 2 - 0.9, 1.5), (0.6, L / 2 - 0.9, 2.2), 0.05, DARK, segs=10)
    # Mast: a lattice box beam laid back from the stand at the front to the pack.
    a = Vector((0, -L / 2 + 0.4, 2.9))
    b = Vector((0, L / 2 - 1.2, 1.65))
    d = (b - a).normalized()
    side = Vector((1, 0, 0))
    up = d.cross(side).normalized()
    hw_, hh_ = 0.22, 0.22
    corners = [side * sx * hw_ + up * sz * hh_ for (sx, sz) in ((-1, -1), (-1, 1), (1, 1), (1, -1))]
    for k, c in enumerate(corners):
        W.rod(ctx, f"chord{k}", a + c, b + c, 0.03, "lab_rig_red", segs=8)
    n = 10
    for i in range(n + 1):
        p = a + (b - a) * (i / n)
        for k in range(4):
            c0, c1 = corners[k], corners[(k + 1) % 4]
            W.rod(ctx, f"lace{i}{k}", p + c0, p + c1, 0.012, "lab_rig_red", segs=5)
        if i < n:
            q = a + (b - a) * ((i + 1) / n)
            W.rod(ctx, f"diag{i}", p + corners[i % 2], q + corners[2 + i % 2], 0.01, "lab_rig_red", segs=5)
    # Mast stand (an A-frame) at the front and the drill head on the mast.
    for sx in (-1, 1):
        W.rod(ctx, f"stand{sx}", (sx * 0.8, -L / 2 + 0.4, 0.22), (sx * 0.12, -L / 2 + 0.45, 2.66), 0.04, "lab_rig_red", segs=8)
    W.rod(ctx, "stand_bar", (-0.4, -L / 2 + 0.42, 1.5), (0.4, -L / 2 + 0.42, 1.5), 0.03, "lab_rig_red", segs=6)
    hp = a + (b - a) * 0.55 + up * 0.38
    head = K.box("head", (0.6, 0.7, 0.5), bevel=0.03)
    K.orient(head, d, up, hp)
    ctx.add(head, "lab_rig_red", uv="box", uv_scale=1.0, patches=0.7)
    chuck = K.cyl("chuck", 0.12, 0.3, segs=14, center=(0, 0, 0), axis="Y")
    K.orient(chuck, side, up, hp - d * 0.5)
    ctx.add(chuck, DARK, uv="cyl", uv_axis=1, smooth=40)
    # Rod rack along one side with its rods.
    for k, y in enumerate((-1.5, 0.0, 1.0)):
        W.bar(ctx, f"rack_post{k}", (Wd / 2 - 0.1, y, 0.22), (Wd / 2 - 0.1, y, 1.0), 0.06, 0.06, DARK)
        W.bar(ctx, f"rack_arm{k}", (Wd / 2 - 0.1, y, 0.95), (Wd / 2 + 0.25, y, 0.95), 0.05, 0.05, DARK)
    for k in range(9):
        z = 0.55 + (k // 3) * 0.12
        x = Wd / 2 + 0.02 + (k % 3) * 0.08
        W.rod(ctx, f"rod{k}", (x, -2.1, z), (x, 1.5, z), 0.028, DARK if k % 2 else STEEL, segs=8)
    # Water tank and pump.
    _bx(ctx, "water_tank", (0.9, 1.1, 0.8), (-Wd / 2 + 0.6, -0.6, 0.22 + 0.4), "road_plastic_white", bevel=0.05, patches=0.6)
    _bx(ctx, "pump", (0.45, 0.4, 0.35), (-Wd / 2 + 0.6, 0.35, 0.22 + 0.175), "town4_pump_blue", bevel=0.02)
    hose = K.tube("water_hose", [(-Wd / 2 + 0.6, 0.55, 0.4), (-0.3, 0.8, 0.3), (0.0, 0.2, 1.4), (0.0, -0.1, 2.0)], 0.03, segs=6)
    ctx.add(hose, RUBBER, uv="box", uv_scale=3.0, smooth=40)
    # Empty core trays stacked at the front corner.
    for k in range(4):
        tr = K.box(f"tray{k}", (1.05, 0.34, 0.09), bevel=0.004)
        K.place(tr, (0, 0, 0), (0, 0, 90 + r.uniform(-4, 4)))
        K.place(tr, (-Wd / 2 + 0.45, -L / 2 + 1.0, 0.27 + k * 0.095))
        ctx.add(tr, "lab_waxed_box", uv="box", uv_scale=1.5, patches=0.6)
    if ctx.worn:
        tr = K.box("tray_fallen", (1.05, 0.34, 0.09), bevel=0.004)
        K.place(tr, (0, 0, 0), (0, 12, 70))
        K.place(tr, (-Wd / 2 - 0.4, -L / 2 + 1.4, 0.06))
        ctx.add(tr, "lab_waxed_box", uv="box", uv_scale=1.5, patches=0.7)


# ============================================================================================
# The core shed
# ============================================================================================

def _core_box(ctx, name, x, y, z, *, rot=0.0, lid=True, cores=False, label=0, spill=False):
    """A waxed core box 1.05 x 0.33 x 0.1 (long along X), its end label facing -Y when rot=90 (end on)."""
    L, Wd, H = 1.05, 0.33, 0.1
    parts = []
    bx = K.box(f"{name}_b", (L, Wd, H), bevel=0.004)
    parts.append(bx)
    if cores:
        K.delete_faces(bx, lambda c, n: n.z > 0.9)
        for k in range(3):
            yy = -Wd / 2 + Wd * (k + 0.5) / 3
            xx = -L / 2 + 0.03
            rr = random.Random(f"{name}{k}")
            while xx < L / 2 - 0.05:
                seg = rr.uniform(0.12, 0.3)
                seg = min(seg, L / 2 - 0.03 - xx)
                c = K.cyl(f"{name}_core{k}_{xx:.2f}", 0.024, seg, segs=8, center=(xx + seg / 2, yy, -H / 2 + 0.034), axis="X")
                K.place(c, (0, 0, 0))
                ctx.add(c, "town4_core_rock" if rr.random() < 0.7 else "town4_core_dark", uv="cyl", uv_axis=0, smooth=40,
                        at=((x, y, z + H / 2), (0, 0, rot)))
                xx += seg + 0.01
    elif lid:
        top = K.box(f"{name}_lid", (L + 0.01, Wd + 0.01, 0.012), center=(0, 0, H / 2 + 0.006))
        ctx.add(top, "lab_waxed_box", uv="box", uv_scale=1.5, patches=0.5, at=((x, y, z + H / 2), (0, 0, rot)))
    ctx.add(bx, "lab_waxed_box", uv="box", uv_scale=1.5, patches=0.5, at=((x, y, z + H / 2), (0, 0, rot)))
    # End label (on the -X end in the box's frame).
    col, row = label % 4, (label // 4) % 2
    f = K.quad_sheet(f"{name}_end", (0, -Wd / 2 + 0.01, -H / 2 + 0.008), (0, Wd / 2 - 0.01, -H / 2 + 0.008),
                     (0, Wd / 2 - 0.01, H / 2 - 0.008), (0, -Wd / 2 + 0.01, H / 2 - 0.008), 1, 1)
    K.uv_planar(f, 0, rect=_rect("box_ends", (col / 4, row / 2, (col + 1) / 4, (row + 1) / 2)), flip_u=True)
    K.place(f, (-L / 2 - 0.0015, 0, 0))
    ctx.add(f, SIGNS, uv=None, wear=0.7, at=((x, y, z + H / 2), (0, 0, rot)))
    _ = spill


def lab_core_rack(ctx: K.Ctx) -> None:
    """Pallet racking 2.5 m long: blue uprights with orange beams at three levels and the floor, waxed core boxes
    stacked end-on with their stencilled ends out, a few pulled half out, lids off (destroyed: the top beam pair
    down at one end and the boxes slid off it onto the floor, cores spilled)."""
    r = ctx.rnd("rack")
    L, Dp = 2.45, 1.1
    levels = (0.0, 0.62, 1.24, 1.86)
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.bar(ctx, f"upright{sx}{sy}", (sx * L / 2, sy * Dp / 2, 0.0), (sx * L / 2, sy * Dp / 2, 2.3), 0.07, 0.06, "road_paint_blue",
                  up=(0, 1, 0), bevel=0.004)
        for k in range(5):
            z0 = 0.1 + k * 0.45
            W.rod(ctx, f"lacing{sx}{k}", (sx * L / 2, -Dp / 2, z0), (sx * L / 2, Dp / 2, z0 + 0.42), 0.012, "road_paint_blue", segs=5)
        _bx(ctx, f"foot{sx}", (0.14, Dp + 0.08, 0.012), (sx * L / 2, 0, 0.006), "road_paint_blue", bevel=0.002)
    for li, z in enumerate(levels[1:]):
        drop = ctx.destroyed and li == 2
        for sy in (-1, 1):
            a = (-L / 2, sy * Dp / 2, z)
            b = (L / 2, sy * Dp / 2, z - (0.7 if drop else 0.0))
            W.bar(ctx, f"beam{li}{sy}", a, b, 0.05, 0.1, "lab_cordon_orange", up=(0, 1, 0), bevel=0.004)
        for k in range(4):
            x = -L / 2 + 0.2 + k * (L - 0.4) / 3
            W.bar(ctx, f"deck{li}{k}", (x, -Dp / 2, z + 0.05), (x, Dp / 2, z + 0.05), 0.04, 0.02, GALV)
    # Boxes end-on (their long axis along Y, label out the front), stacked 3 high on each level.
    n_cols = 6
    lab_i = 0
    for li, z in enumerate(levels):
        if li == 3:
            continue
        base = z + (0.07 if li > 0 else 0.03)
        for c in range(n_cols):
            x = -L / 2 + 0.24 + c * (L - 0.48) / (n_cols - 1)
            stack = 3 if (li, c) not in ((0, 5), (2, 1)) else 2
            if ctx.destroyed and li == 2:
                continue
            for s in range(stack):
                pulled = 0.25 if (ctx.worn and r.random() < 0.08) else 0.0
                _core_box(ctx, f"box{li}{c}{s}", x + r.uniform(-0.01, 0.01), -Dp / 2 + 0.55 - pulled, base + s * 0.105,
                          rot=90.0, lid=not pulled, cores=bool(pulled), label=lab_i)
                lab_i += 1
    if ctx.destroyed:
        for k in range(6):
            _core_box(ctx, f"spill{k}", r.uniform(-1.0, 1.0), -Dp / 2 - r.uniform(0.2, 0.7), 0.0, rot=r.uniform(0, 180), lid=False,
                      cores=k % 2 == 0, label=k)
        for k in range(10):
            c = K.cyl(f"loose{k}", 0.024, r.uniform(0.08, 0.25), segs=8, center=(0, 0, 0), axis="X")
            K.place(c, (0, 0, 0), (0, 0, r.uniform(0, 180)))
            K.place(c, (r.uniform(-1.1, 1.1), -Dp / 2 - r.uniform(0.3, 1.0), 0.024))
            ctx.add(c, "town4_core_rock", uv="cyl", uv_axis=0, smooth=40)
    _centre_depth(ctx)


def lab_core_boxes(ctx: K.Ctx) -> None:
    """Core boxes on a pallet: three layers cross-stacked, the top one open on its three rows of grey drill core
    with wooden depth blocks between the runs, its lid leaning against the stack."""
    r = ctx.rnd("boxes")
    for k in range(5):
        pl = P.plank(f"slat{k}", 1.2, 0.14, 0.022)
        K.place(pl, (0, -0.45 + k * 0.225, 0.13))
        ctx.add(pl, "wood_weathered", long_axis=0, patches=0.6)
    for k in range(3):
        _bx(ctx, f"stringer{k}", (0.1, 1.0, 0.1), (-0.5 + k * 0.5, 0, 0.065), "wood_weathered", bevel=0.005, long_axis=1)
    lab_i = 0
    for layer in range(2):
        for k in range(3):
            if layer % 2 == 0:
                _core_box(ctx, f"b{layer}{k}", 0.0, -0.35 + k * 0.35, 0.142 + layer * 0.105, rot=0.0, label=lab_i)
            else:
                _core_box(ctx, f"b{layer}{k}", -0.35 + k * 0.35, 0.0, 0.142 + layer * 0.105, rot=90.0, label=lab_i)
            lab_i += 1
    _core_box(ctx, "open", 0.0, 0.0, 0.142 + 2 * 0.105, rot=r.uniform(-4, 4), lid=False, cores=True, label=6)
    for k in range(2):
        blk = K.box(f"block{k}", (0.012, 0.3, 0.05), center=(-0.12 + k * 0.33, 0.0, 0.142 + 2 * 0.105 + 0.05))
        ctx.add(blk, "road_wood_bench", uv="box", uv_scale=3.0)
    lid = K.box("lid", (1.05, 0.33, 0.012), bevel=0.002)
    K.place(lid, (0, 0, 0), (70, 0, 0))
    K.place(lid, (0.0, -0.62, 0.18))
    ctx.add(lid, "lab_waxed_box", uv="box", uv_scale=1.5, patches=0.6)


def lab_core_saw(ctx: K.Ctx) -> None:
    """A diamond core saw on a steel stand: the water tray, the blade under its hinged guard, a sliding cradle with
    a core half cut, the motor and belt cover, the pump hose to a bucket and a spattered plywood splash board."""
    _bx(ctx, "tray", (1.5, 0.7, 0.16), (0, 0, 0.86), STAINLESS, bevel=0.01, patches=0.6)
    tray_in = K.box("tray_water", (1.42, 0.62, 0.01), center=(0, 0, 0.9))
    ctx.add(tray_in, "road_water_grey", uv="box", uv_scale=1.0, ao=False)
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.bar(ctx, f"leg{sx}{sy}", (sx * 0.65, sy * 0.28, 0.0), (sx * 0.65, sy * 0.28, 0.78), 0.05, 0.05, CAB, bevel=0.003)
    W.bar(ctx, "shelf", (-0.65, 0, 0.25), (0.65, 0, 0.25), 0.56, 0.02, CAB)
    # Blade and guard.
    blade = K.cyl("blade", 0.2, 0.004, segs=24, center=(0, 0, 0), axis="Y")
    K.place(blade, (0.1, 0.0, 1.0))
    ctx.add(blade, STEEL, uv="cyl", uv_axis=1, smooth=40)
    guard = K.cyl("guard", 0.24, 0.1, segs=16, center=(0, 0, 0), axis="Y")
    K.delete_faces(guard, lambda c, n: c.z < 0.02)
    K.solidify(guard, 0.006, offset=0.0, even=False)
    K.place(guard, (0.1, 0.0, 1.02))
    ctx.add(guard, "lab_cordon_orange", uv="box", uv_scale=2.0, smooth=40, patches=0.7)
    _cy(ctx, "motor", 0.11, 0.32, (0.1, 0.32, 1.02), CAB, axis="Y", segs=14)
    _bx(ctx, "belt_cover", (0.28, 0.06, 0.3), (0.1, 0.2, 1.06), "lab_cordon_orange", bevel=0.02)
    # Cradle and the half-cut core.
    _bx(ctx, "cradle", (0.6, 0.12, 0.05), (-0.25, 0.0, 0.94), DARK, bevel=0.004)
    for k, (x0, x1) in enumerate(((-0.55, -0.12), (-0.11, 0.0))):
        c = K.cyl(f"core{k}", 0.024, x1 - x0, segs=10, center=((x0 + x1) / 2, 0.0, 0.99), axis="X")
        if k == 0:
            K.delete_faces(c, lambda cc, n: cc.y > 0.002 and abs(n.x) < 0.9)
        ctx.add(c, "town4_core_rock", uv="cyl", uv_axis=0, smooth=40)
    # Splash board, hose and bucket.
    _bx(ctx, "splash", (1.5, 0.018, 0.6), (0, 0.37, 1.24), "road_plywood", bevel=0.003, patches=0.7)
    hose = K.tube("hose", [(-0.6, 0.3, 0.86), (-0.75, 0.3, 0.6), (-0.8, 0.0, 0.3), (-0.95, -0.2, 0.32)], 0.012, segs=6)
    ctx.add(hose, "road_plastic_black", uv="box", uv_scale=3.0, smooth=40)
    bk = P.bucket("bucket", top_r=0.15, bot_r=0.12, h=0.3)
    K.place(bk, (-0.9, -0.15, 0.0))
    ctx.add(bk, "road_plastic_grey", uv="cyl", uv_axis=2, smooth=40)
    _centre_depth(ctx)


def lab_logging_bench(ctx: K.Ctx) -> None:
    """The geologists' logging bench: a heavy plank top on 4x4 legs with a stretcher, an angled tray of core under a
    clamp lamp, a hand lens, a black-and-white scale bar, a clipboard of logging sheets, a mug of pencils and a
    spray bottle."""
    L, Dp, H = 2.4, 0.85, 0.86
    for k in range(4):
        pl = P.plank(f"top{k}", L, Dp / 4 - 0.01, 0.05, bevel=0.004)
        K.place(pl, (0, -Dp / 2 + (k + 0.5) * Dp / 4, H - 0.025))
        ctx.add(pl, "road_wood_bench", long_axis=0, patches=0.6)
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.bar(ctx, f"leg{sx}{sy}", (sx * (L / 2 - 0.12), sy * (Dp / 2 - 0.08), 0.0), (sx * (L / 2 - 0.12), sy * (Dp / 2 - 0.08), H - 0.05),
                  0.09, 0.09, "road_wood_bench", bevel=0.004)
    W.bar(ctx, "stretcher", (-L / 2 + 0.12, 0, 0.18), (L / 2 - 0.12, 0, 0.18), 0.08, 0.04, "road_wood_bench")
    # Angled core tray resting on a batten.
    tray_rot = (-18, 0, 0)
    tr = K.box("tray", (1.3, 0.36, 0.05), bevel=0.003)
    K.place(tr, (0, 0, 0), tray_rot)
    K.place(tr, (-0.25, 0.05, H + 0.1))
    ctx.add(tr, "lab_waxed_box", uv="box", uv_scale=1.5)
    for k in range(3):
        c = K.cyl(f"core{k}", 0.023, 1.15, segs=10, center=(0, -0.1 + k * 0.1, 0.045), axis="X")
        K.place(c, (0, 0, 0), tray_rot)
        K.place(c, (-0.25, 0.05, H + 0.1))
        ctx.add(c, "town4_core_rock" if k != 1 else "town4_core_dark", uv="cyl", uv_axis=0, smooth=40)
    W.bar(ctx, "batten", (-0.9, 0.2, H + 0.02), (0.4, 0.2, H + 0.02), 0.05, 0.04, "road_wood_bench")
    # Clamp lamp on the back edge.
    W.rod(ctx, "lamp_arm0", (0.7, Dp / 2 - 0.05, H), (0.7, Dp / 2 - 0.05, H + 0.45), 0.01, DARK, segs=6)
    W.rod(ctx, "lamp_arm1", (0.7, Dp / 2 - 0.05, H + 0.45), (0.45, 0.1, H + 0.55), 0.01, DARK, segs=6)
    shade = K.cyl("lamp_shade", 0.09, 0.14, segs=12, center=(0, 0, 0), r_top=0.04)
    K.place(shade, (0, 0, 0), (180, 0, 0))
    K.place(shade, (0.45, 0.1, H + 0.5))
    ctx.add(shade, "lab_cordon_orange", uv="cyl", uv_axis=2, smooth=40)
    # Lens, scale bar, clipboard, mug.
    _cy(ctx, "lens", 0.025, 0.012, (0.62, -0.25, H + 0.006), "item_glass_clear", segs=12)
    for k in range(6):
        _bx(ctx, f"scale{k}", (0.05, 0.025, 0.006), (0.35 + k * 0.05, -0.3, H + 0.003), "road_paint_black" if k % 2 else "lab_enamel",
            bevel=0.0)
    _bx(ctx, "clipboard", (0.23, 0.32, 0.01), (0.85, -0.12, H + 0.005), "road_wood_bench", bevel=0.002, rot=(0, 0, 8))
    _bx(ctx, "sheets", (0.21, 0.28, 0.004), (0.85, -0.13, H + 0.012), "road_paper_white", bevel=0.0, rot=(0, 0, 8))
    _bx(ctx, "clip", (0.06, 0.02, 0.012), (0.83, 0.02, H + 0.015), STEEL, bevel=0.002, rot=(0, 0, 8))
    mug = K.lathe("mug", [(0.0, 0.0), (0.04, 0.0), (0.042, 0.1), (0.036, 0.1), (0.034, 0.012), (0.0, 0.012)], segs=12)
    K.place(mug, (1.05, 0.25, H))
    ctx.add(mug, "lab_enamel", uv="cyl", uv_axis=2, smooth=40)
    for k in range(4):
        a = k * 1.6
        W.rod(ctx, f"pencil{k}", (1.05 + math.cos(a) * 0.012, 0.25 + math.sin(a) * 0.012, H + 0.02),
              (1.05 + math.cos(a) * 0.04, 0.25 + math.sin(a) * 0.04, H + 0.17), 0.004, "road_paint_yellow", segs=5)
    _bottle(ctx, "spray", -1.05, 0.25, H, 0.035, 0.2, "road_plastic_white", neck=0.4, cap="lab_cordon_orange")
    _centre_depth(ctx)


# ============================================================================================
# Labs
# ============================================================================================

def _base_cabinets(ctx, L, Dp, H, *, mat=CAB, doors=2, drawers=True):
    """Steel base cabinets L x Dp x H on a black plinth: door and drawer fronts with pull handles, front -Y."""
    _bx(ctx, "plinth", (L - 0.04, Dp - 0.08, 0.08), (0, 0.03, 0.04), "road_plastic_black", bevel=0.003)
    _bx(ctx, "carcass", (L, Dp, H - 0.08), (0, 0, 0.08 + (H - 0.08) / 2), mat, bevel=0.006, cuts=(2, 0, 1))
    n = doors + (1 if drawers else 0)
    w = L / n
    for k in range(n):
        x = -L / 2 + (k + 0.5) * w
        if drawers and k == n - 1:
            for d in range(3):
                z = 0.08 + (d + 0.5) * (H - 0.1) / 3
                _bx(ctx, f"drawer{k}{d}", (w - 0.03, 0.02, (H - 0.1) / 3 - 0.025), (x, -Dp / 2 - 0.008, z), mat, bevel=0.004)
                _bx(ctx, f"pull{k}{d}", (0.12, 0.02, 0.015), (x, -Dp / 2 - 0.025, z + 0.03), STAINLESS, bevel=0.003)
        else:
            _bx(ctx, f"door{k}", (w - 0.03, 0.02, H - 0.13), (x, -Dp / 2 - 0.008, 0.08 + (H - 0.1) / 2), mat, bevel=0.004)
            _bx(ctx, f"dpull{k}", (0.015, 0.02, 0.12), (x + (w / 2 - 0.08) * (1 if k % 2 else -1), -Dp / 2 - 0.025, H - 0.18), STAINLESS,
                bevel=0.003)


def lab_bench(ctx: K.Ctx) -> None:
    """A lab bench: steel base cabinets, a black epoxy top with a raised back, a reagent shelf on two uprights with
    brown and clear bottles, a gas tap and a socket strip, a box of gloves and a beaker on the top (worn: grime and
    bottles knocked over; destroyed: the shelf down at one end, the bottles smashed across the top)."""
    r = ctx.rnd("bench")
    L, Dp, H = 1.8, 0.72, 0.9
    _base_cabinets(ctx, L, Dp, H - 0.03)
    _bx(ctx, "top", (L + 0.02, Dp + 0.03, 0.03), (0, -0.01, H - 0.015), EPOXY, bevel=0.006)
    _bx(ctx, "upstand", (L + 0.02, 0.02, 0.1), (0, Dp / 2 + 0.005, H + 0.05), EPOXY, bevel=0.004)
    # Shelf uprights and shelves.
    for sx in (-1, 1):
        W.bar(ctx, f"upright{sx}", (sx * (L / 2 - 0.08), Dp / 2 - 0.08, H), (sx * (L / 2 - 0.08), Dp / 2 - 0.08, 1.92), 0.04, 0.04, CAB, bevel=0.003)
    for k, z in enumerate((1.32, 1.72)):
        drop = ctx.destroyed and k == 1
        sh = K.box(f"shelf{k}", (L - 0.1, 0.24, 0.02), bevel=0.003)
        if drop:
            K.place(sh, (0, 0, 0), (0, 22, 0))
            K.place(sh, (0.1, Dp / 2 - 0.16, z - 0.3))
        else:
            K.place(sh, (0, Dp / 2 - 0.16, z))
        ctx.add(sh, CAB, uv="box", uv_scale=1.0, patches=0.6)
        if drop:
            continue
        x = -L / 2 + 0.15
        while x < L / 2 - 0.15:
            kind = r.random()
            fallen = ctx.worn and r.random() < 0.12
            if kind < 0.45:
                _bottle(ctx, f"b{k}_{x:.2f}", x, Dp / 2 - 0.16, z + 0.01, 0.04, 0.2, "glass_brown", fallen=fallen)
            elif kind < 0.8:
                _bottle(ctx, f"b{k}_{x:.2f}", x, Dp / 2 - 0.16, z + 0.01, 0.035, 0.17, "glass_clear", neck=0.45, cap="plastic_blue",
                        fallen=fallen)
            else:
                _bx(ctx, f"box{k}_{x:.2f}", (0.14, 0.12, 0.16), (x + 0.03, Dp / 2 - 0.16, z + 0.09), "road_cardboard", bevel=0.004)
            x += r.uniform(0.11, 0.17)
    # The work top: gas tap, socket strip, a glove box, a beaker or the broken glass.
    W.rod(ctx, "gas_tap", (0.6, Dp / 2 - 0.05, H), (0.6, Dp / 2 - 0.05, H + 0.12), 0.012, "road_brass", segs=8)
    W.rod(ctx, "gas_nozzle", (0.6, Dp / 2 - 0.05, H + 0.11), (0.6, Dp / 2 - 0.15, H + 0.11), 0.008, "road_brass", segs=6)
    _bx(ctx, "sockets", (0.5, 0.05, 0.06), (-0.4, Dp / 2 - 0.03, H + 0.03), "road_plastic_white", bevel=0.005)
    _bx(ctx, "gloves", (0.24, 0.12, 0.09), (-0.6, 0.05, H + 0.045), "road_plastic_blue", bevel=0.006)
    if ctx.destroyed:
        for k in range(8):
            ch = K.chunk(f"glass{k}", r.uniform(0.02, 0.05), r, n=7, flat=0.3)
            K.place(ch, (r.uniform(-0.7, 0.7), r.uniform(-0.25, 0.2), H + 0.01))
            ctx.add(ch, "glass_brown" if k % 2 else "glass_clear", uv="box", uv_scale=4.0)
    else:
        bk = K.lathe("beaker", [(0.0, 0.0), (0.045, 0.0), (0.045, 0.12), (0.05, 0.13)], segs=12, cap_top=False)
        K.place(bk, (0.2, -0.1, H))
        ctx.add(bk, "glass_clear", uv="cyl", uv_axis=2, smooth=40)
    _centre_depth(ctx)


def lab_fume_hood(ctx: K.Ctx) -> None:
    """A fume hood on its cabinet base: the hood box with its sash glass half raised in a steel frame, the
    aerofoil sill, the slotted baffle inside, a flow gauge on the post, the light box on top and the round duct
    rising to the ceiling."""
    L, Dp = 1.5, 0.85
    _base_cabinets(ctx, L, Dp - 0.05, 0.85, doors=2, drawers=False)
    _bx(ctx, "worktop", (L + 0.02, Dp, 0.04), (0, 0.0, 0.87), EPOXY, bevel=0.006)
    z0, z1 = 0.89, 2.3
    # Hood shell: back, sides, top, the fascia over the sash.
    _bx(ctx, "back", (L, 0.04, z1 - z0), (0, Dp / 2 - 0.02, (z0 + z1) / 2), ENAMEL, bevel=0.005)
    for sx in (-1, 1):
        _bx(ctx, f"side{sx}", (0.08, Dp, z1 - z0), (sx * (L / 2 - 0.04), 0, (z0 + z1) / 2), ENAMEL, bevel=0.01)
    _bx(ctx, "roof", (L, Dp, 0.08), (0, 0, z1 - 0.04), ENAMEL, bevel=0.01)
    _bx(ctx, "fascia", (L - 0.16, 0.06, 0.32), (0, -Dp / 2 + 0.03, z1 - 0.24), ENAMEL, bevel=0.008)
    _bx(ctx, "baffle", (L - 0.18, 0.02, z1 - z0 - 0.4), (0, Dp / 2 - 0.1, (z0 + z1) / 2 - 0.1), STAINLESS, bevel=0.002)
    for k in range(3):
        _bx(ctx, f"slot{k}", (L - 0.3, 0.005, 0.02), (0, Dp / 2 - 0.112, z0 + 0.12 + k * 0.42), "road_plastic_black", bevel=0.0)
    # Sash: frame and glass, half raised.
    zs = z0 + 0.45
    _bx(ctx, "sash_glass", (L - 0.2, 0.008, 0.62), (0, -Dp / 2 + 0.07, zs + 0.31), GLASS, bevel=0.0, ao=False)
    for zz in (zs, zs + 0.62):
        _bx(ctx, f"sash_rail{zz:.2f}", (L - 0.18, 0.03, 0.04), (0, -Dp / 2 + 0.07, zz), STAINLESS, bevel=0.004)
    _bx(ctx, "sash_handle", (L - 0.5, 0.04, 0.02), (0, -Dp / 2 + 0.04, zs + 0.03), STAINLESS, bevel=0.004)
    _bx(ctx, "aerofoil", (L - 0.16, 0.08, 0.02), (0, -Dp / 2 + 0.05, z0 + 0.02), STAINLESS, bevel=0.006)
    # Gauge, light box, duct.
    _cy(ctx, "gauge", 0.04, 0.02, (L / 2 - 0.04, -Dp / 2 + 0.05, z0 + 0.95), DARK, axis="Y", segs=12)
    _cy(ctx, "gauge_face", 0.032, 0.004, (L / 2 - 0.04, -Dp / 2 + 0.038, z0 + 0.95), "lab_enamel", axis="Y", segs=12)
    _bx(ctx, "lightbox", (L - 0.3, 0.3, 0.06), (0, -0.05, z1 + 0.03), ENAMEL, bevel=0.005)
    _cy(ctx, "duct", 0.15, 2.75 - z1 - 0.06, (0, 0.12, (2.75 + z1 + 0.06) / 2), GALV, segs=16)
    for k in range(2):
        ring = W.ring_obj(f"duct_band{k}", 0.15, 0.162, 0.03, segs=16)
        K.place(ring, (0, 0.12, z1 + 0.15 + k * 0.2))
        ctx.add(ring, GALV, uv="box", uv_scale=3.0)
    _centre_depth(ctx)


def lab_biosafety_cabinet(ctx: K.Ctx) -> None:
    """A class II biosafety cabinet on its stand: the cabinet with an angled sash over the opening, the front intake
    grille, a stainless work surface inside, the UV tube, the blower housing and exhaust collar on top and the
    airflow alarm panel over the sash (lit only on the generator)."""
    L, Dp = 1.4, 0.8
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.bar(ctx, f"leg{sx}{sy}", (sx * (L / 2 - 0.08), sy * (Dp / 2 - 0.08), 0.0), (sx * (L / 2 - 0.08), sy * (Dp / 2 - 0.08), 0.72), 0.05, 0.05,
                  CAB, bevel=0.003)
            _cy(ctx, f"foot{sx}{sy}", 0.03, 0.03, (sx * (L / 2 - 0.08), sy * (Dp / 2 - 0.08), 0.015), "road_plastic_black", segs=8)
        W.bar(ctx, f"rail{sx}", (sx * (L / 2 - 0.08), -Dp / 2 + 0.08, 0.2), (sx * (L / 2 - 0.08), Dp / 2 - 0.08, 0.2), 0.04, 0.04, CAB)
    z0, z1 = 0.72, 1.98
    _bx(ctx, "base", (L, Dp, 0.12), (0, 0, z0 + 0.06), ENAMEL, bevel=0.01)
    _bx(ctx, "grille", (L - 0.14, 0.12, 0.012), (0, -Dp / 2 + 0.09, z0 + 0.125), "road_plastic_black", bevel=0.0)
    _bx(ctx, "worksurface", (L - 0.16, Dp - 0.25, 0.01), (0, 0.04, z0 + 0.125), STAINLESS, bevel=0.0)
    _bx(ctx, "back", (L, 0.05, z1 - z0), (0, Dp / 2 - 0.025, (z0 + z1) / 2), ENAMEL, bevel=0.008)
    for sx in (-1, 1):
        side = K.prism(f"side{sx}", [(-Dp / 2, z0), (Dp / 2, z0), (Dp / 2, z1), (-Dp / 2 + 0.12, z1), (-Dp / 2, z0 + 0.6)], 0.06, plane="YZ",
                       offset=sx * (L / 2 - 0.03))
        ctx.add(side, ENAMEL, uv="box", uv_scale=1.0, patches=0.5)
    _bx(ctx, "top", (L, Dp - 0.1, 0.08), (0, 0.05, z1 - 0.04), ENAMEL, bevel=0.01)
    # The angled sash from the opening's top to the front edge.
    a = Vector((0, -Dp / 2 + 0.02, z0 + 0.38))
    b = Vector((0, -Dp / 2 + 0.12, z1 - 0.26))
    sash = K.quad_sheet("sash", (-L / 2 + 0.07, a.y, a.z), (L / 2 - 0.07, a.y, a.z), (L / 2 - 0.07, b.y, b.z), (-L / 2 + 0.07, b.y, b.z), 1, 1)
    K.solidify(sash, 0.008, offset=0.0, even=False)
    ctx.add(sash, GLASS, uv="box", uv_scale=1.0, ao=False)
    W.bar(ctx, "sash_bottom", (-L / 2 + 0.07, a.y - 0.01, a.z), (L / 2 - 0.07, a.y - 0.01, a.z), 0.04, 0.03, STAINLESS)
    _bx(ctx, "panel", (L - 0.14, 0.04, 0.22), (0, -Dp / 2 + 0.14, z1 - 0.14), ENAMEL, bevel=0.006)
    _bx(ctx, "display", (0.18, 0.006, 0.06), (0.35, -Dp / 2 + 0.118, z1 - 0.13), "lab_glow_display", bevel=0.0, ao=False)
    _bx(ctx, "uv_tube", (L - 0.3, 0.03, 0.03), (0, Dp / 2 - 0.12, z1 - 0.3), "lab_frost", bevel=0.01)
    _bx(ctx, "blower", (L - 0.2, Dp - 0.25, 0.14), (0, 0.08, z1 + 0.07), CAB, bevel=0.01)
    _cy(ctx, "collar", 0.12, 0.08, (0.3, 0.08, z1 + 0.18), GALV, segs=14)
    _centre_depth(ctx)


def lab_freezer_80(ctx: K.Ctx) -> None:
    """An upright minus-80 freezer: a deep white cabinet with rounded edges, the door with its gasket and the latch
    handle, frost round the seal and on the handle, the keypad and temperature display, the label panel, the
    compressor grille and castors (worn: frost gone, grime, a dent)."""
    L, Dp, H = 0.82, 0.88, 1.96
    _bx(ctx, "cabinet", (L, Dp - 0.08, H - 0.1), (0, 0.04, 0.1 + (H - 0.1) / 2), ENAMEL, bevel=0.03, cuts=(1, 1, 3), patches=0.5)
    door = K.box("door", (L - 0.02, 0.08, H - 0.3), bevel=0.02, cuts=(1, 0, 3))
    if ctx.worn:
        K.dent(door, Vector((0.15, -0.04, 0.2)), 0.12, 0.01)
    K.place(door, (0, -Dp / 2 + 0.04, 0.12 + (H - 0.3) / 2))
    ctx.add(door, ENAMEL, uv="box", uv_scale=1.0, patches=0.5)
    _bx(ctx, "gasket", (L - 0.01, 0.01, H - 0.29), (0, -Dp / 2 + 0.085, 0.12 + (H - 0.3) / 2), "road_plastic_black", bevel=0.0)
    _bx(ctx, "handle", (0.06, 0.06, 0.42), (L / 2 - 0.1, -Dp / 2 - 0.02, 1.05), STAINLESS, bevel=0.012)
    _bx(ctx, "latch", (0.1, 0.04, 0.06), (L / 2 - 0.1, -Dp / 2 - 0.01, 1.3), STAINLESS, bevel=0.008)
    if not ctx.worn:
        for k, (w_, h_, x_, z_) in enumerate(((L - 0.02, 0.025, 0.0, H - 0.18), (L - 0.02, 0.025, 0.0, 0.125), (0.025, H - 0.3, -L / 2 + 0.012, 0.12 + (H - 0.3) / 2))):
            fr = K.box(f"frost{k}", (w_, 0.03, h_), bevel=0.006)
            K.noise_disp(fr, 0.004, scale=30.0, seed=ctx.seed + k)
            K.place(fr, (x_, -Dp / 2 + 0.07, z_))
            ctx.add(fr, "lab_frost", uv="box", uv_scale=4.0, smooth=40)
        fh = K.box("frost_handle", (0.065, 0.065, 0.15), bevel=0.015)
        K.noise_disp(fh, 0.003, scale=30.0, seed=ctx.seed + 9)
        K.place(fh, (L / 2 - 0.1, -Dp / 2 - 0.02, 0.95))
        ctx.add(fh, "lab_frost", uv="box", uv_scale=4.0, smooth=40)
    # Control strip over the door: display, keypad, the label panel.
    _bx(ctx, "control", (L - 0.04, 0.1, 0.16), (0, -Dp / 2 + 0.05, H - 0.08), DARK, bevel=0.01)
    _face(ctx, "label", 0.36, 0.24, _rect("freezer"), (-0.15, -Dp / 2 - 0.002, 1.55), 0.0, wear=0.4)
    _bx(ctx, "display", (0.16, 0.006, 0.05), (0.2, -Dp / 2 - 0.0015, H - 0.08), "lab_glow_display", bevel=0.0, ao=False)
    for k in range(6):
        _bx(ctx, f"key{k}", (0.018, 0.006, 0.014), (-0.25 + (k % 3) * 0.03, -Dp / 2 - 0.002, H - 0.06 - (k // 3) * 0.025), "road_plastic_grey",
            bevel=0.0)
    # Compressor grille and castors.
    for k in range(5):
        _bx(ctx, f"grille{k}", (L - 0.12, 0.01, 0.012), (0, -Dp / 2 + 0.03, 0.03 + k * 0.016), "road_plastic_black", bevel=0.0)
    for sx in (-1, 1):
        for sy in (-1, 1):
            _cy(ctx, f"castor{sx}{sy}", 0.03, 0.03, (sx * (L / 2 - 0.08), sy * (Dp / 2 - 0.1), 0.03), "road_plastic_black", axis="X", segs=10)
    _centre_depth(ctx)


def lab_centrifuge(ctx: K.Ctx) -> None:
    """A floor-standing refrigerated centrifuge: a white body with a rounded top, the domed lid on its hinge, the
    sloped control panel with its display and lock lamp, side vents and castors."""
    L, Dp, H = 0.76, 0.8, 0.86
    _bx(ctx, "body", (L, Dp, H - 0.08), (0, 0, 0.06 + (H - 0.08) / 2), ENAMEL, bevel=0.05, cuts=(1, 1, 1), patches=0.5)
    lid = K.cyl("lid", 0.3, 0.6, segs=18, center=(0, 0, 0), axis="X")
    K.delete_faces(lid, lambda c, n: c.z < -0.001)
    K.place(lid, (0, 0, 0), (0, 0, 0), (1.0, 1.0, 0.35))
    K.place(lid, (0, 0.08, H - 0.02))
    ctx.add(lid, ENAMEL, uv="box", uv_scale=1.0, smooth=40, patches=0.5)
    _cy(ctx, "hinge", 0.025, 0.5, (0, 0.38, H - 0.01), DARK, axis="X", segs=10)
    panel = K.box("panel", (L - 0.08, 0.2, 0.03), bevel=0.006)
    K.place(panel, (0, 0, 0), (-35, 0, 0))
    K.place(panel, (0, -Dp / 2 + 0.07, H - 0.06))
    ctx.add(panel, "lab_cabinet_grey", uv="box", uv_scale=1.0)
    disp = K.box("display", (0.2, 0.08, 0.006))
    K.place(disp, (0, 0, 0), (-35, 0, 0))
    K.place(disp, (-0.12, -Dp / 2 + 0.065, H - 0.04))
    ctx.add(disp, "lab_glow_display", uv="box", uv_scale=4.0, ao=False)
    lamp = K.cyl("lock_lamp", 0.015, 0.012, segs=8, center=(0, 0, 0))
    K.place(lamp, (0, 0, 0), (-35, 0, 0))
    K.place(lamp, (0.2, -Dp / 2 + 0.065, H - 0.035))
    ctx.add(lamp, "lab_glow_red", uv="box", uv_scale=4.0, ao=False)
    for sx in (-1, 1):
        for k in range(6):
            _bx(ctx, f"vent{sx}{k}", (0.006, 0.4, 0.012), (sx * (L / 2 + 0.002), 0.05, 0.25 + k * 0.03), "road_plastic_black", bevel=0.0)
    for sx in (-1, 1):
        for sy in (-1, 1):
            _cy(ctx, f"castor{sx}{sy}", 0.03, 0.03, (sx * (L / 2 - 0.08), sy * (Dp / 2 - 0.08), 0.03), "road_plastic_black", axis="X", segs=10)


def lab_microscope(ctx: K.Ctx) -> None:
    """A binocular microscope (tabletop): the cast base with its lamp, the curved arm, the stage with a slide in its
    clips, the nosepiece and three objectives, the binocular head and eyepieces, focus knobs, and a slide box
    beside it."""
    _bx(ctx, "base", (0.2, 0.26, 0.05), (0, 0.02, 0.025), ENAMEL, bevel=0.015)
    _cy(ctx, "lamp", 0.03, 0.02, (0, -0.04, 0.06), "lab_glow_lamp", segs=12, ao=False)
    arm = K.tube("arm", [(0, 0.12, 0.05), (0, 0.13, 0.15), (0, 0.11, 0.26), (0, 0.06, 0.33)], 0.03, segs=10, flat=(1.2, 0.8))
    ctx.add(arm, ENAMEL, uv="box", uv_scale=4.0, smooth=40)
    _bx(ctx, "stage", (0.15, 0.13, 0.012), (0, -0.02, 0.16), DARK, bevel=0.003)
    _bx(ctx, "slide", (0.075, 0.026, 0.002), (0, -0.03, 0.167), "item_glass_clear", bevel=0.0)
    for sx in (-1, 1):
        W.rod(ctx, f"clip{sx}", (sx * 0.05, -0.06, 0.168), (sx * 0.02, -0.03, 0.169), 0.003, STEEL, segs=4)
    _cy(ctx, "nosepiece", 0.035, 0.03, (0, -0.02, 0.27), DARK, segs=12)
    for k in range(3):
        a = k * 2.1
        x, y = math.cos(a) * 0.022, -0.02 + math.sin(a) * 0.022
        W.rod(ctx, f"objective{k}", (x, y, 0.255), (x * 1.3, y, 0.205), 0.009 - k * 0.001, STEEL, segs=8)
    _bx(ctx, "head", (0.08, 0.1, 0.06), (0, 0.02, 0.32), ENAMEL, bevel=0.012)
    for sx in (-1, 1):
        W.rod(ctx, f"eyepiece{sx}", (sx * 0.025, -0.01, 0.34), (sx * 0.032, -0.07, 0.4), 0.012, DARK, segs=10)
    for sx in (-1, 1):
        _cy(ctx, f"knob{sx}", 0.025, 0.02, (sx * 0.05, 0.11, 0.13), DARK, axis="X", segs=12)
    _bx(ctx, "slide_box", (0.12, 0.08, 0.035), (0.16, -0.1, 0.0175), "road_plastic_grey", bevel=0.004)


def lab_sample_rack(ctx: K.Ctx) -> None:
    """Wire shelving of sample bottles, tube racks, labelled boxes and a clipboard on a hook."""
    r = ctx.rnd("rack")
    L, Dp, H = 1.18, 0.46, 1.86
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.rod(ctx, f"post{sx}{sy}", (sx * (L / 2 - 0.02), sy * (Dp / 2 - 0.02), 0.0), (sx * (L / 2 - 0.02), sy * (Dp / 2 - 0.02), H), 0.012,
                  "road_chrome", segs=8)
    for k, z in enumerate((0.15, 0.6, 1.05, 1.5, 1.84)):
        sh = K.box(f"shelf{k}", (L - 0.02, Dp - 0.02, 0.012), center=(0, 0, z))
        ctx.add(sh, "road_chrome", uv="box", uv_scale=2.0, patches=0.5)
        for sy in (-1, 1):
            W.rod(ctx, f"lip{k}{sy}", (-L / 2, sy * (Dp / 2 - 0.02), z + 0.02), (L / 2, sy * (Dp / 2 - 0.02), z + 0.02), 0.005, "road_chrome", segs=4)
        if k == 4:
            continue
        x = -L / 2 + 0.1
        while x < L / 2 - 0.12:
            t = r.random()
            if t < 0.35:
                _bottle(ctx, f"bt{k}_{x:.2f}", x, -0.05, z + 0.006, 0.045, 0.2, "glass_brown" if r.random() < 0.5 else "road_plastic_white",
                        neck=0.5, cap="road_plastic_black")
                x += 0.12
            elif t < 0.65:
                _bx(ctx, f"tubes{k}_{x:.2f}", (0.2, 0.1, 0.04), (x + 0.07, -0.05, z + 0.026), "road_plastic_blue", bevel=0.004)
                for i in range(5):
                    _cy(ctx, f"tube{k}_{x:.2f}{i}", 0.007, 0.1, (x - 0.01 + i * 0.035, -0.05, z + 0.08), "road_bag_clear", segs=6)
                x += 0.24
            else:
                _bx(ctx, f"box{k}_{x:.2f}", (0.22, 0.3, 0.16), (x + 0.08, 0.0, z + 0.086), "road_cardboard", bevel=0.005)
                x += 0.26
    _bx(ctx, "clipboard", (0.23, 0.01, 0.32), (L / 2 - 0.2, -Dp / 2 - 0.01, 1.3), "road_wood_bench", bevel=0.002)
    _bx(ctx, "sheet", (0.21, 0.004, 0.28), (L / 2 - 0.2, -Dp / 2 - 0.017, 1.29), "road_paper_white", bevel=0.0)
    _centre_depth(ctx)


def lab_dewar(ctx: K.Ctx) -> None:
    """A liquid-nitrogen dewar on a four-wheel dolly: the stainless vessel with its neck, the vent cap and gauge,
    frost on the neck, handles and a cryo-glove hung over one."""
    prof = [(0.0, 0.12), (0.2, 0.12), (0.25, 0.2), (0.25, 0.85), (0.2, 0.96), (0.07, 1.02), (0.07, 1.1), (0.0, 1.1)]
    v = K.lathe("vessel", prof, segs=24)
    ctx.add(v, STAINLESS, uv="cyl", uv_axis=2, smooth=40, patches=0.5)
    _cy(ctx, "cap", 0.075, 0.06, (0, 0, 1.13), "road_plastic_black", segs=14)
    _cy(ctx, "gauge", 0.035, 0.02, (0.09, 0, 1.06), DARK, axis="X", segs=10)
    if not ctx.worn:
        fr = K.lathe("frost", [(0.072, 1.0), (0.09, 1.02), (0.08, 1.09), (0.072, 1.1)], segs=16, cap_bottom=False, cap_top=False)
        K.noise_disp(fr, 0.006, scale=40.0, seed=ctx.seed)
        ctx.add(fr, "lab_frost", uv="cyl", uv_axis=2, smooth=40)
    for sx in (-1, 1):
        h = K.tube(f"handle{sx}", [(sx * 0.2, 0, 0.95), (sx * 0.3, 0, 1.0), (sx * 0.3, 0, 1.08), (sx * 0.15, 0, 1.06)], 0.01, segs=6)
        ctx.add(h, STAINLESS, uv="box", uv_scale=3.0, smooth=40)
    _cy(ctx, "dolly", 0.29, 0.03, (0, 0, 0.09), DARK, segs=16)
    for k in range(4):
        a = k * math.pi / 2 + math.pi / 4
        _cy(ctx, f"wheel{k}", 0.035, 0.03, (math.cos(a) * 0.24, math.sin(a) * 0.24, 0.035), "road_plastic_black", axis="X", segs=10)
    glove = K.blob("glove", 0.09, subdiv=2, scale=(0.6, 0.35, 1.3), center=(0.31, 0.0, 0.9), rough=0.15, seed=ctx.seed)
    ctx.add(glove, "town4_pump_blue", uv="box", uv_scale=3.0, smooth=50)


def lab_sample_vault(ctx: K.Ctx) -> None:
    """A stainless cryo cabinet behind a padlocked steel grille: four shelves of sealed sample canisters with orange
    numbered bands, frost on the shelves (worn: the grille bent, gaps where canisters were taken)."""
    r = ctx.rnd("vault")
    L, Dp, H = 1.18, 0.7, 2.02
    _bx(ctx, "back", (L, 0.03, H), (0, Dp / 2 - 0.015, H / 2), STAINLESS, bevel=0.004)
    for sx in (-1, 1):
        _bx(ctx, f"side{sx}", (0.03, Dp, H), (sx * (L / 2 - 0.015), 0, H / 2), STAINLESS, bevel=0.004)
    _bx(ctx, "top", (L, Dp, 0.04), (0, 0, H - 0.02), STAINLESS, bevel=0.004)
    _bx(ctx, "plinth", (L, Dp, 0.08), (0, 0, 0.04), DARK, bevel=0.004)
    for k, z in enumerate((0.1, 0.55, 1.0, 1.45)):
        _bx(ctx, f"shelf{k}", (L - 0.06, Dp - 0.08, 0.02), (0, 0.02, z), STAINLESS, bevel=0.002)
        if not ctx.worn or k % 2 == 0:
            fr = K.box(f"frost{k}", (L - 0.08, Dp - 0.1, 0.01), center=(0, 0.02, z + 0.012))
            K.noise_disp(fr, 0.003, scale=25.0, seed=ctx.seed + k)
            ctx.add(fr, "lab_frost", uv="box", uv_scale=4.0, smooth=40)
        for i in range(8):
            for j in range(2):
                if ctx.worn and r.random() < 0.3:
                    continue
                x = -L / 2 + 0.1 + i * (L - 0.2) / 7
                y = -0.12 + j * 0.2
                _cy(ctx, f"can{k}{i}{j}", 0.045, 0.2, (x, y, z + 0.11), STAINLESS, segs=10)
                _cy(ctx, f"band{k}{i}{j}", 0.047, 0.03, (x, y, z + 0.16), "lab_cordon_orange", segs=10)
                _cy(ctx, f"lid{k}{i}{j}", 0.04, 0.02, (x, y, z + 0.22), DARK, segs=8)
    # The grille door.
    gy = -Dp / 2 - 0.02
    bend = 0.08 if ctx.worn else 0.0
    for zz in (0.1, H - 0.1):
        W.bar(ctx, f"grille_rail{zz:.1f}", (-L / 2 + 0.04, gy, zz), (L / 2 - 0.04, gy, zz), 0.04, 0.04, DARK)
    for sx in (-1, 1):
        W.bar(ctx, f"grille_stile{sx}", (sx * (L / 2 - 0.04), gy, 0.1), (sx * (L / 2 - 0.04), gy, H - 0.1), 0.04, 0.04, DARK)
    for i in range(9):
        x = -L / 2 + 0.12 + i * (L - 0.24) / 8
        pts = [(x, gy, 0.1), (x, gy - bend * math.sin(math.pi * i / 8), H / 2), (x, gy, H - 0.1)]
        ctx.add(K.tube(f"bar{i}", pts, 0.008, segs=6), DARK, uv="box", uv_scale=4.0, smooth=40)
    _bx(ctx, "hasp", (0.08, 0.02, 0.12), (L / 2 - 0.04, gy - 0.03, 1.05), DARK, bevel=0.004)
    _bx(ctx, "padlock", (0.06, 0.03, 0.07), (L / 2 - 0.04, gy - 0.05, 0.98), "lock_steel", bevel=0.008)
    _centre_depth(ctx)


def lab_vault_frame(ctx: K.Ctx) -> None:
    """The specimen vault's steel collar standing proud of the wall round its door (a 0.96 x 2.15 m opening; the
    kit door_vault hangs in it): a heavy frame with hazard stripes, bolt housings down both jambs, a keypad and
    card slot on its own box, a red status lamp over it and conduit up the wall."""
    W_, H_, T = 2.2, 2.6, 0.32
    ow, oh = 0.98, 2.16
    parts = [((-W_ / 2, -ow / 2), (0, H_)), ((ow / 2, W_ / 2), (0, H_)), ((-ow / 2, ow / 2), (oh, H_))]
    for k, ((x0, x1), (z0, z1)) in enumerate(parts):
        _bx(ctx, f"slab{k}", (x1 - x0, T, z1 - z0), ((x0 + x1) / 2, -T / 2, (z0 + z1) / 2), "lab_skid_steel", bevel=0.02, patches=0.6)
    # Inner collar ring round the opening.
    for k, (a, b) in enumerate((((-ow / 2, -T - 0.04, 0), (-ow / 2, -T - 0.04, oh)), ((ow / 2, -T - 0.04, 0), (ow / 2, -T - 0.04, oh)),
                                 ((-ow / 2, -T - 0.04, oh), (ow / 2, -T - 0.04, oh)))):
        W.bar(ctx, f"collar{k}", a, b, 0.1, 0.1, DARK, up=(0, 1, 0), bevel=0.01)
    # Hazard stripes on the lintel and bolt housings down the jambs.
    _face(ctx, "stripes", ow + 0.6, 0.2, _rect("airlock", (0.0, 0.0, 0.6, 0.23)), (0, -T - 0.002, oh + 0.2), 0.0, wear=0.8)
    for sx in (-1, 1):
        for k in range(4):
            z = 0.3 + k * 0.5
            _cy(ctx, f"bolt{sx}{k}", 0.05, 0.12, (sx * (ow / 2 + 0.17), -T - 0.06, z), STAINLESS, axis="Y", segs=12)
    _bx(ctx, "keypad_box", (0.22, 0.08, 0.32), (ow / 2 + 0.42, -T - 0.04, 1.35), DARK, bevel=0.01)
    for k in range(9):
        _bx(ctx, f"key{k}", (0.035, 0.01, 0.03), (ow / 2 + 0.38 + (k % 3) * 0.045, -T - 0.085, 1.42 - (k // 3) * 0.045), "road_plastic_grey",
            bevel=0.0)
    _bx(ctx, "slot", (0.1, 0.012, 0.012), (ow / 2 + 0.42, -T - 0.085, 1.24), "road_plastic_black", bevel=0.0)
    lamp = K.cyl("lamp", 0.04, 0.05, segs=12, center=(0, 0, 0), axis="Y")
    K.place(lamp, (0, -T - 0.025, oh + 0.42))
    ctx.add(lamp, "lab_glow_red", uv="box", uv_scale=4.0, ao=False)
    W.rod(ctx, "conduit", (ow / 2 + 0.42, -T - 0.0, 1.5), (ow / 2 + 0.42, -T - 0.0, H_ - 0.05), 0.012, GALV, segs=6)
    _centre_depth(ctx)


def lab_card_reader(ctx: K.Ctx) -> None:
    """A keycard reader beside the airlock door (wall-mounted: origin on the wall plane, bottom centre, front -Y): a
    grey box with a card slot, a twelve-key pad, a red lamp lit on the battery and conduit up the wall."""
    _bx(ctx, "box", (0.1, 0.045, 0.17), (0, -0.0225, 0.085), CAB, bevel=0.006)
    _bx(ctx, "slot", (0.07, 0.008, 0.008), (0, -0.047, 0.15), "road_plastic_black", bevel=0.0)
    for k in range(12):
        _bx(ctx, f"key{k}", (0.016, 0.006, 0.013), (-0.022 + (k % 3) * 0.022, -0.047, 0.11 - (k // 3) * 0.02), "road_plastic_grey", bevel=0.0)
    _cy(ctx, "led", 0.007, 0.006, (0.035, -0.047, 0.155), "lab_glow_red", axis="Y", segs=8, ao=False)
    W.rod(ctx, "conduit", (0, -0.012, 0.17), (0, -0.012, 0.2), 0.01, GALV, segs=6)


def lab_decon_shower(ctx: K.Ctx) -> None:
    """A decontamination shower: a stainless tray and drain grate, four posts and a top ring of pipe with nozzles,
    nozzle bars down two posts, a pull handle on a rod, an eyewash on a pedestal and a torn white curtain on one
    side (worn: grime, the curtain half down)."""
    S, H = 1.5, 2.3
    hs = S / 2
    tray = K.box("tray", (S + 0.1, S + 0.1, 0.06), bevel=0.01, cuts=(2, 2, 0))
    K.place(tray, (0, 0, 0.03))
    ctx.add(tray, STAINLESS, uv="box", uv_scale=1.0, patches=0.5)
    _bx(ctx, "grate", (0.3, 0.3, 0.008), (0, 0, 0.062), DARK, bevel=0.0)
    for k in range(5):
        _bx(ctx, f"grate_bar{k}", (0.008, 0.28, 0.006), (-0.12 + k * 0.06, 0, 0.068), STEEL, bevel=0.0)
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.rod(ctx, f"post{sx}{sy}", (sx * hs, sy * hs, 0.06), (sx * hs, sy * hs, H), 0.025, STAINLESS, segs=8)
    for k in range(4):
        a = [(-hs, -hs), (hs, -hs), (hs, hs), (-hs, hs)][k]
        b = [(-hs, -hs), (hs, -hs), (hs, hs), (-hs, hs)][(k + 1) % 4]
        W.rod(ctx, f"top{k}", (a[0], a[1], H), (b[0], b[1], H), 0.022, STAINLESS, segs=8)
    ring = K.lathe("nozzle_ring", [(0.4, -0.012), (0.424, -0.012), (0.424, 0.012), (0.4, 0.012)], segs=20, close_profile=True)
    K.place(ring, (0, 0, H - 0.18))
    ctx.add(ring, STAINLESS, uv="box", uv_scale=3.0, smooth=40)
    # The feed: a pipe from the frame's side to the centre and a drop to the ring's hub, four arms out to it.
    W.rod(ctx, "feed", (-hs, 0, H), (0, 0, H), 0.02, STAINLESS, segs=8)
    W.rod(ctx, "drop", (0, 0, H), (0, 0, H - 0.18), 0.02, STAINLESS, segs=8)
    for k in range(4):
        a = k * math.pi / 2
        W.rod(ctx, f"spoke{k}", (0, 0, H - 0.18), (math.cos(a) * 0.4, math.sin(a) * 0.4, H - 0.18), 0.01, STAINLESS, segs=6)
    for k in range(8):
        a = k * math.tau / 8
        _cy(ctx, f"nozzle{k}", 0.018, 0.04, (math.cos(a) * 0.41, math.sin(a) * 0.41, H - 0.21), DARK, segs=8)
    for sy in (-1, 1):
        for k in range(4):
            _cy(ctx, f"side_nozzle{sy}{k}", 0.014, 0.05, (-hs + 0.04, sy * hs, 0.5 + k * 0.38), DARK, axis="X", segs=8)
    W.rod(ctx, "pull_rod", (0.2, -0.2, H), (0.2, -0.2, 1.75), 0.006, STAINLESS, segs=5)
    tri = K.tube("pull", [(0.12, -0.2, 1.75), (0.28, -0.2, 1.75), (0.2, -0.2, 1.65), (0.12, -0.2, 1.75)], 0.008, segs=5)
    ctx.add(tri, "plastic_green", uv="box", uv_scale=4.0, smooth=40)
    # Eyewash pedestal outside the tray.
    W.rod(ctx, "eyewash_post", (hs + 0.25, -hs + 0.2, 0.0), (hs + 0.25, -hs + 0.2, 1.0), 0.03, "plastic_green", segs=8)
    bowl = K.lathe("eyewash_bowl", [(0.0, 0.0), (0.12, 0.04), (0.14, 0.08), (0.13, 0.085), (0.0, 0.03)], segs=14)
    K.place(bowl, (hs + 0.25, -hs + 0.2, 1.0))
    ctx.add(bowl, "plastic_yellow", uv="cyl", uv_axis=2, smooth=40)
    # Curtain on the +X side, torn.
    cur = K.quad_sheet("curtain", (hs + 0.03, -hs, 0.3), (hs + 0.03, hs, 0.3), (hs + 0.03, hs, H - 0.04), (hs + 0.03, -hs, H - 0.04), 10, 8)
    for v in cur.data.vertices:
        v.co.x += 0.04 * math.sin(v.co.y * 10.0) * (0.6 + 0.4 * (H - v.co.z) / H)
    cur.data.update()
    K.delete_faces(cur, lambda c, n: (c.y > 0.25 and c.z < 1.3) or (ctx.worn and c.y < -0.2 and c.z < 1.6))
    K.solidify(cur, 0.003, offset=0.0, even=False)
    ctx.add(cur, "lab_tyvek", uv="box", uv_scale=1.0, smooth=40, patches=0.6)


def _suit(ctx, name, x, y, z_top, mat, r):
    """A Tyvek coverall hung limp from a hanger (front -Y): the hood folded over the hanger, a flattened body, the
    arms hanging close and the legs ending well clear of the shelf."""
    W.rod(ctx, f"{name}_hanger", (x - 0.2, y, z_top - 0.04), (x + 0.2, y, z_top - 0.04), 0.006, STEEL, segs=5)
    body = K.blob(f"{name}_body", 0.2, subdiv=2, scale=(1.0, 0.28, 1.55), center=(x, y, z_top - 0.4), rough=0.1, seed=r.randint(0, 999))
    ctx.add(body, mat, uv="box", uv_scale=2.0, smooth=50, patches=0.6)
    hood = K.blob(f"{name}_hood", 0.1, subdiv=2, scale=(1.1, 0.45, 0.8), center=(x, y + 0.03, z_top - 0.06), rough=0.15, seed=r.randint(0, 999))
    ctx.add(hood, mat, uv="box", uv_scale=2.0, smooth=50, patches=0.6)
    for sx in (-1, 1):
        arm = K.tube(f"{name}_arm{sx}", [(x + sx * 0.16, y, z_top - 0.12), (x + sx * 0.19, y - 0.01, z_top - 0.38), (x + sx * 0.17, y - 0.02, z_top - 0.62)],
                     [0.05, 0.045, 0.04], segs=8, flat=(1.0, 0.6))
        ctx.add(arm, mat, uv="box", uv_scale=2.0, smooth=50, patches=0.6)
        leg = K.tube(f"{name}_leg{sx}", [(x + sx * 0.08, y, z_top - 0.7), (x + sx * 0.085, y - 0.01, z_top - 0.9), (x + sx * 0.075, y, z_top - 1.06)],
                     [0.06, 0.055, 0.05], segs=8, flat=(1.0, 0.6))
        ctx.add(leg, mat, uv="box", uv_scale=2.0, smooth=50, patches=0.6)
    _bx(ctx, f"{name}_zip", (0.012, 0.004, 0.45), (x, y - 0.058, z_top - 0.42), "road_plastic_white", bevel=0.0)


def lab_ppe_rack(ctx: K.Ctx) -> None:
    """A rack of PPE: Tyvek coveralls (white and yellow) on hangers, half-mask respirators on hooks along the top
    rail, rubber boots on the bottom shelf with taped gloves, a box of filters on top (worn: a suit pulled down and
    trampled)."""
    r = ctx.rnd("ppe")
    L, H = 1.55, 1.95
    for sx in (-1, 1):
        W.rod(ctx, f"upright{sx}", (sx * L / 2, 0, 0.05), (sx * L / 2, 0, H), 0.018, CAB, segs=8)
        W.rod(ctx, f"foot{sx}", (sx * L / 2, -0.28, 0.03), (sx * L / 2, 0.28, 0.03), 0.02, CAB, segs=8)
    W.rod(ctx, "rail", (-L / 2, 0, H - 0.05), (L / 2, 0, H - 0.05), 0.016, STEEL, segs=8)
    _bx(ctx, "shelf", (L, 0.5, 0.02), (0, 0, 0.25), CAB, bevel=0.003)
    _bx(ctx, "top_shelf", (L, 0.45, 0.02), (0, 0, H), CAB, bevel=0.003)
    n = 4
    for k in range(n):
        if ctx.worn and k == 2:
            continue
        x = -L / 2 + 0.25 + k * (L - 0.5) / (n - 1)
        _suit(ctx, f"suit{k}", x, 0.06, H - 0.1, "lab_tyvek" if k % 2 == 0 else "lab_tyvek_yellow", r)
    # Respirators on hooks.
    for k in range(3):
        x = -L / 2 + 0.2 + k * 0.5
        mask = K.blob(f"mask{k}", 0.06, subdiv=2, scale=(1.0, 0.7, 0.9), center=(x, -0.12, H - 0.25), seed=k)
        ctx.add(mask, "road_plastic_black", uv="box", uv_scale=4.0, smooth=50)
        for sx in (-1, 1):
            _cy(ctx, f"filter{k}{sx}", 0.032, 0.03, (x + sx * 0.06, -0.15, H - 0.27), "lab_cordon_orange" if k != 1 else "town4_pump_blue",
                axis="Y", segs=10)
    # Boots and gloves below.
    for k in range(3):
        for s in (-1, 1):
            x = -L / 2 + 0.3 + k * 0.48 + s * 0.07
            boot = K.box(f"boot{k}{s}", (0.11, 0.28, 0.3), bevel=0.04, cuts=(1, 2, 2))
            K.place(boot, (0, 0, 0), (0, 0, 8 * s))
            K.place(boot, (x, -0.1, 0.26 + 0.15))
            ctx.add(boot, "road_rubber" if k != 1 else "plastic_yellow", uv="box", uv_scale=2.0, smooth=40)
    _bx(ctx, "filters_box", (0.4, 0.3, 0.2), (0.4, 0.0, H + 0.11), "road_cardboard", bevel=0.006)
    if ctx.worn:
        # A suit pulled down and trodden flat in front of the rack: a crumpled sheet with its sleeves out.
        pile = K.grid("dropped_suit", 0.95, 0.55, 10, 7, center=(0.15, -0.55, 0.0))
        rr = ctx.drnd("pile")
        for v in pile.data.vertices:
            v.co.z = 0.012 + 0.05 * max(0.0, 1.0 - ((v.co.x - 0.15) / 0.5) ** 2 - ((v.co.y + 0.55) / 0.3) ** 2) + rr.uniform(0.0, 0.025)
        pile.data.update()
        K.crumple(pile, 0.02, scale=8.0, seed=ctx.seed)
        K.solidify(pile, 0.004, offset=0.0, even=False)
        ctx.add(pile, "lab_tyvek", uv="box", uv_scale=2.0, smooth=50, patches=0.7)
        for sx in (-1, 1):
            sl = K.tube(f"sleeve{sx}", [(0.15 + sx * 0.4, -0.5, 0.03), (0.15 + sx * 0.62, -0.62 + sx * 0.05, 0.025),
                                        (0.15 + sx * 0.78, -0.55, 0.02)], 0.04, segs=7, flat=(1.0, 0.4))
            ctx.add(sl, "lab_tyvek", uv="box", uv_scale=2.0, smooth=50, patches=0.7)
    _centre_depth(ctx)


def lab_biohazard_bin(ctx: K.Ctx) -> None:
    """A red pedal bin with the biohazard trefoil, a yellow bag pulled over its rim and the lid propped (worn:
    tipped lid, a stained bag hanging out)."""
    prof = [(0.0, 0.05), (0.19, 0.05), (0.2, 0.06), (0.22, 0.62), (0.215, 0.64), (0.0, 0.64)]
    body = K.lathe("body", prof, segs=4, angle0=math.pi / 4)
    K.place(body, (0, 0, 0), None, (1.0, 1.0, 1.0))
    ctx.add(body, "road_plastic_red", uv="box", uv_scale=2.0, patches=0.5)
    _bx(ctx, "base", (0.3, 0.3, 0.05), (0, 0, 0.025), "road_plastic_black", bevel=0.01)
    _bx(ctx, "pedal", (0.12, 0.08, 0.02), (0, -0.2, 0.03), "road_plastic_black", bevel=0.004)
    bag = K.lathe("bag", [(0.21, 0.6), (0.235, 0.64), (0.22, 0.66)], segs=4, angle0=math.pi / 4, cap_bottom=False, cap_top=False)
    ctx.add(bag, "plastic_yellow", uv="box", uv_scale=2.0, smooth=40)
    lid = K.box("lid", (0.34, 0.34, 0.025), bevel=0.008)
    K.place(lid, (0, 0, 0), (-28 if not ctx.worn else -75, 0, 0))
    K.place(lid, (0, 0.17 + (0.02 if ctx.worn else 0.0), 0.66))
    ctx.add(lid, "road_plastic_red", uv="box", uv_scale=2.0)
    _face(ctx, "label", 0.2, 0.15, _rect("biohazard"), (0, -0.157, 0.42), 0.0, wear=0.5)


def lab_radio_desk(ctx: K.Ctx) -> None:
    """The station's radio desk: a steel desk with a drawer pedestal, the HF transceiver and its power supply, a desk
    microphone, a handset on its hook, the frequency card, a map of the claims under the glass top, the logbook
    open and a mug; the antenna lead out the back."""
    L, Dp, H = 1.6, 0.78, 0.76
    _bx(ctx, "top", (L, Dp, 0.035), (0, 0, H - 0.0175), CAB, bevel=0.006)
    _bx(ctx, "map", (0.9, 0.55, 0.002), (-0.25, 0.02, H + 0.002), "road_paper_yellow", bevel=0.0)
    _bx(ctx, "glass", (1.0, 0.62, 0.006), (-0.25, 0.02, H + 0.006), GLASS, bevel=0.0, ao=False)
    _bx(ctx, "pedestal", (0.42, Dp - 0.04, H - 0.04), (L / 2 - 0.23, 0, (H - 0.04) / 2), CAB, bevel=0.006)
    for d in range(3):
        _bx(ctx, f"drawer{d}", (0.38, 0.02, 0.2), (L / 2 - 0.23, -Dp / 2 + 0.01, 0.13 + d * 0.23), CAB, bevel=0.004)
        _bx(ctx, f"pull{d}", (0.1, 0.02, 0.015), (L / 2 - 0.23, -Dp / 2 - 0.005, 0.18 + d * 0.23), STAINLESS, bevel=0.003)
    for sy in (-1, 1):
        W.bar(ctx, f"leg{sy}", (-L / 2 + 0.04, sy * (Dp / 2 - 0.04), 0.0), (-L / 2 + 0.04, sy * (Dp / 2 - 0.04), H - 0.03), 0.04, 0.04, CAB)
    _bx(ctx, "modesty", (L - 0.5, 0.02, 0.4), (-0.2, Dp / 2 - 0.03, H - 0.25), CAB, bevel=0.003)
    # The radio and its power supply.
    _bx(ctx, "radio", (0.42, 0.32, 0.14), (-0.15, 0.18, H + 0.08), "road_steel_dark", bevel=0.01)
    _bx(ctx, "radio_face", (0.4, 0.006, 0.12), (-0.15, 0.018, H + 0.08), "road_plastic_black", bevel=0.0)
    _bx(ctx, "radio_display", (0.12, 0.004, 0.035), (-0.25, 0.0145, H + 0.11), "lab_glow_display", bevel=0.0, ao=False)
    for k in range(3):
        _cy(ctx, f"knob{k}", 0.018, 0.02, (-0.05 + k * 0.06, 0.008, H + 0.06), STEEL, axis="Y", segs=10)
    _bx(ctx, "psu", (0.22, 0.28, 0.12), (0.25, 0.2, H + 0.07), CAB, bevel=0.008)
    W.rod(ctx, "mic_stem", (-0.55, 0.0, H), (-0.55, 0.0, H + 0.22), 0.008, DARK, segs=6)
    _cy(ctx, "mic_base", 0.07, 0.025, (-0.55, 0.0, H + 0.0125), DARK, segs=12)
    mic = K.cyl("mic_head", 0.03, 0.09, segs=10, center=(0, 0, 0), axis="Y")
    K.place(mic, (-0.55, -0.03, H + 0.24))
    ctx.add(mic, "road_chrome", uv="cyl", uv_axis=1, smooth=40)
    _bx(ctx, "handset", (0.06, 0.2, 0.04), (0.5, -0.05, H + 0.02), "road_plastic_black", bevel=0.015, rot=(0, 0, 20))
    _bx(ctx, "logbook", (0.3, 0.22, 0.02), (-0.2, -0.2, H + 0.02), "road_paint_green", bevel=0.004, rot=(0, 0, -6))
    _bx(ctx, "logbook_pages", (0.28, 0.2, 0.004), (-0.2, -0.2, H + 0.032), "road_paper_white", bevel=0.0, rot=(0, 0, -6))
    cable = K.tube("lead", [(-0.15, 0.34, H + 0.05), (-0.1, Dp / 2 + 0.05, H - 0.1), (0.2, Dp / 2 + 0.03, 1.4), (0.3, Dp / 2 + 0.03, 2.2)], 0.008, segs=5)
    ctx.add(cable, "road_plastic_black", uv="box", uv_scale=3.0, smooth=40)
    _centre_depth(ctx)


def lab_server_rack(ctx: K.Ctx) -> None:
    """A 19-inch rack cabinet: perforated glass door in a dark frame, servers and tape drives with their status
    lights (lit on the battery), a patch panel and a bundle of cable out of its roof (worn: the door open on a
    gap, cables pulled)."""
    r = ctx.rnd("srv")
    L, Dp, H = 0.62, 0.88, 1.98
    _bx(ctx, "frame_back", (L, 0.03, H), (0, Dp / 2 - 0.015, H / 2), DARK, bevel=0.004)
    for sx in (-1, 1):
        _bx(ctx, f"side{sx}", (0.025, Dp, H), (sx * (L / 2 - 0.0125), 0, H / 2), DARK, bevel=0.004)
    _bx(ctx, "roof", (L, Dp, 0.04), (0, 0, H - 0.02), DARK, bevel=0.004)
    _bx(ctx, "plinth", (L, Dp, 0.06), (0, 0, 0.03), "road_plastic_black", bevel=0.004)
    z = 0.12
    k = 0
    while z < H - 0.25:
        u = r.choice((0.045, 0.09, 0.09, 0.135))
        _bx(ctx, f"unit{k}", (L - 0.08, Dp - 0.12, u - 0.006), (0, 0.02, z + u / 2), "road_plastic_black" if k % 3 else CAB, bevel=0.003)
        for j in range(r.randint(1, 4)):
            led = K.box(f"led{k}{j}", (0.008, 0.004, 0.006), center=(-L / 2 + 0.08 + j * 0.02, -Dp / 2 + 0.04, z + u * 0.5))
            ctx.add(led, "lab_glow_green" if r.random() < 0.8 else "lab_glow_red", uv="box", uv_scale=8.0, ao=False)
        z += u
        k += 1
    # Door: a frame and smoked glass, hinged on its left (worn: swung open).
    swing = 25 if ctx.worn else 0
    dw = L - 0.02
    door_parts = [K.box("door_rail_lo", (dw, 0.025, 0.04), center=(dw / 2, 0, 0.08)),
                  K.box("door_rail_hi", (dw, 0.025, 0.04), center=(dw / 2, 0, H - 0.06)),
                  K.box("door_stile_l", (0.03, 0.025, H - 0.1), center=(0.015, 0, H / 2)),
                  K.box("door_stile_r", (0.03, 0.025, H - 0.1), center=(dw - 0.015, 0, H / 2))]
    gl = K.box("door_glass", (dw - 0.05, 0.006, H - 0.18), center=(dw / 2, 0, H / 2))
    for p in door_parts + [gl]:
        K.place(p, (0, 0, 0), (0, 0, swing))
        K.place(p, (-L / 2 + 0.01, -Dp / 2 - 0.0125, 0))
        ctx.add(p, GLASS if p is gl else DARK, uv="box", uv_scale=2.0, ao=p is not gl)
    for k2 in range(3):
        c = K.tube(f"cable{k2}", [(-0.1 + k2 * 0.08, 0.2, H), (-0.1 + k2 * 0.08, 0.25, H + 0.12), (-0.05 + k2 * 0.06, 0.4, H + 0.2)], 0.02, segs=6)
        ctx.add(c, "road_plastic_blue" if k2 == 1 else "road_plastic_grey", uv="box", uv_scale=3.0, smooth=40)
    _centre_depth(ctx)


def lab_ceiling_light(ctx: K.Ctx) -> None:
    """A recessed fluorescent panel on the generator circuit (ceiling-mounted: origin on the ceiling, hanging below
    it): a white steel housing, a prismatic diffuser that glows when lit (worn: a corner of the diffuser broken
    out)."""
    ctx.ground_clamp = False
    L, Dp = 1.22, 0.6
    _bx(ctx, "housing", (L, Dp, 0.08), (0, 0, -0.04), "lab_enamel", bevel=0.008)
    dif = K.box("diffuser", (L - 0.06, Dp - 0.06, 0.012), cuts=(4, 2, 0))
    if ctx.worn:
        K.delete_faces(dif, lambda c, n: c.x > L / 2 - 0.35 and c.y > 0.05)
    K.place(dif, (0, 0, -0.086))
    ctx.add(dif, "lab_glow_lamp", uv="box", uv_scale=2.0, ao=False)
    for sx in (-1, 1):
        _bx(ctx, f"rim{sx}", (0.03, Dp, 0.012), (sx * (L / 2 - 0.015), 0, -0.086), CAB, bevel=0.0)


def lab_emergency_light(ctx: K.Ctx) -> None:
    """A red emergency beacon on its battery pack over a door (wall-mounted: origin on the wall plane, bottom
    centre, front -Y)."""
    _bx(ctx, "plate", (0.22, 0.015, 0.16), (0, -0.0075, 0.08), CAB, bevel=0.004)
    _bx(ctx, "battery", (0.18, 0.08, 0.1), (0, -0.055, 0.06), "road_plastic_white", bevel=0.008)
    dome = K.lathe("dome", [(0.0, 0.0), (0.05, 0.0), (0.05, 0.05), (0.035, 0.09), (0.0, 0.1)], segs=14)
    K.place(dome, (0, -0.06, 0.11))
    ctx.add(dome, "lab_glow_red", uv="cyl", uv_axis=2, smooth=40, ao=False)
    W.rod(ctx, "conduit", (0.08, -0.01, 0.16), (0.08, -0.01, 0.3), 0.009, GALV, segs=6)


# ============================================================================================

BUILDERS = {
    "lab_module_shell": lab_module_shell,
    "lab_decon_shell": lab_decon_shell,
    "lab_boardwalk_roof": lab_boardwalk_roof,
    "lab_berm": lab_berm,
    "lab_fence": lab_fence,
    "lab_fence_cut": lab_fence_cut,
    "lab_gate": lab_gate,
    "lab_sign_station": lab_sign_station,
    "lab_sign_fence": lab_sign_fence,
    "lab_fuel_tank": lab_fuel_tank,
    "lab_generator": lab_generator,
    "lab_drill_rig": lab_drill_rig,
    "lab_core_rack": lab_core_rack,
    "lab_core_boxes": lab_core_boxes,
    "lab_core_saw": lab_core_saw,
    "lab_logging_bench": lab_logging_bench,
    "lab_bench": lab_bench,
    "lab_fume_hood": lab_fume_hood,
    "lab_biosafety_cabinet": lab_biosafety_cabinet,
    "lab_freezer_80": lab_freezer_80,
    "lab_centrifuge": lab_centrifuge,
    "lab_microscope": lab_microscope,
    "lab_sample_rack": lab_sample_rack,
    "lab_dewar": lab_dewar,
    "lab_sample_vault": lab_sample_vault,
    "lab_vault_frame": lab_vault_frame,
    "lab_card_reader": lab_card_reader,
    "lab_decon_shower": lab_decon_shower,
    "lab_ppe_rack": lab_ppe_rack,
    "lab_biohazard_bin": lab_biohazard_bin,
    "lab_radio_desk": lab_radio_desk,
    "lab_server_rack": lab_server_rack,
    "lab_ceiling_light": lab_ceiling_light,
    "lab_emergency_light": lab_emergency_light,
    "lab_sign_biohazard": _wall_sign, "lab_sign_airlock": _wall_sign, "lab_sign_decon": _wall_sign,
    "lab_sign_vault": _wall_sign, "lab_sign_emergency": _wall_sign, "lab_sign_containment": _wall_sign,
    "lab_sign_core_shed": _wall_sign, "lab_sign_module_prep": _wall_sign, "lab_sign_module_micro": _wall_sign,
    "lab_sign_module_cold": _wall_sign, "lab_sign_module_admin": _wall_sign,
}


def build(params: dict, outputs: list[str]) -> None:
    K.run(params, outputs, BUILDERS)
