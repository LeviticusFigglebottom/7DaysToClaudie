"""Wilderness set pieces, round 4 (ADR-0053): the Kettle Creek backcountry ranger station
(game/data/pois/buildings/w4_backcountry_ranger_station.json).

A district station at the end of a forest road that the Cordon made a checkpoint: a stacked steel lattice
fire-weather tower (one 3 m section per kit level, the POI's kit platforms are its landings) on concrete
piers, the steel-clad cab that wraps the kit room on top, the Stevenson screen, the rain gauge and the
anemometer mast at its foot, the district's brush truck, the checkpoint's barrier arm, the elevated fuel
tank, the compound's chain-link gate standing open, the gun safe and the fire danger sign.

Conventions (docs/ASSET_PIPELINE.md): metres, Z up, front -Y, origin bottom centre (floor props are centred
on the origin: PoiBuilder's collision box is the def's size centred there). The tower pieces and the cab
centre on the tower's axis (a grid vertex of the plan: the middle of its 2 x 2 landings). The cab shell
wraps a 2 x 2 kit room whose floor is at the origin (the catalog's SHELLS lists its openings). Lettering
reuses the round-3 w3_signs atlas (its CHECKPOINT cell). 'clean' is the station as it was kept, 'worn' a
season abandoned, 'destroyed' broken or burnt.
"""
from __future__ import annotations

import math

from mathutils import Vector

from lib import props_ext_kit as K
from lib import props_ext_parts as P
from lib import props_outskirts_parts as O
from lib import props_wild_parts as W
from lib import materials as MAT

GALV = "metal_galvanized"
STEEL = "road_steel"
DARK = "road_steel_dark"
CONC = "road_concrete"
GREEN = "car_paint_green"
WHITE = "car_paint_white"

# The round-3 lettering atlas (textures/gen/wild3.py): 8 x 8 units of 256 px.
SIGNS = "w3_signs"
UNIT = 256
ATLAS_PX = 2048.0
ATLAS = {"checkpoint": (6, 5, 2, 1)}

MAT.PREVIEW_COLORS.update({"w3_signs": (0.5, 0.4, 0.3)})


def _rect(name: str, inset: float = 2.0) -> tuple[float, float, float, float]:
    """Blender UV rect (u0, v0, u1, v1; v up) of an atlas cell."""
    x, y, w, h = [v * UNIT for v in ATLAS[name]]
    x0, y0, x1, y1 = x + inset, y + inset, x + w - inset, y + h - inset
    return (x0 / ATLAS_PX, 1.0 - y1 / ATLAS_PX, x1 / ATLAS_PX, 1.0 - y0 / ATLAS_PX)


def _face(ctx, name, w, h, rect, loc, rot_z=0.0):
    """Flat lettered face (w x h) facing -Y with an atlas rect mapped edge to edge; rot_z 180 faces +Y."""
    o = K.quad_sheet(name, (-w / 2, 0, -h / 2), (w / 2, 0, -h / 2), (w / 2, 0, h / 2), (-w / 2, 0, h / 2), 2, 2)
    K.uv_planar(o, 1, rect=rect)
    K.place(o, (0, 0, 0), (0, 0, rot_z))
    K.place(o, loc)
    return ctx.add(o, SIGNS, uv=None, wear=0.6, patches=0.35, edge=0.6)


def _box(ctx, name, size, center, mat, *, bevel=0.0, uv_scale=1.0, **kw):
    return ctx.add(K.box(name, size, center=center, bevel=bevel), mat, uv="box", uv_scale=uv_scale, **kw)


# ============================================================================================
# The fire-weather tower
# ============================================================================================

# Half the lattice's face (legs stand just outside the 2 x 2 landings' edges) and one section's height.
HS = 1.15
SEC = 3.0


def w4_ranger_tower_leg_section(ctx: K.Ctx) -> None:
    """One 3 m storey of the fire-weather tower: four galvanised angle legs at the corners of a 2.3 m
    square, bolted splice plates at the foot, girts at mid-height and the top, X-bracing on every face, and
    the landing's frame (channels round the kit platform's slab, 0.2 m under the next floor). Stacked one
    per kit level. Worn: rust and a brace hanging off its bottom bolt. Collision none: the kit landings and
    the rails carry the climber."""
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.bar(ctx, f"leg{sx}{sy}", (sx * HS, sy * HS, 0.0), (sx * HS, sy * HS, SEC), 0.085, 0.085, GALV,
                  up=(sx, 0, 0), bevel=0.004, patches=0.6)
            # splice plate with its bolts at the foot of the section
            _box(ctx, f"splice{sx}{sy}", (0.16, 0.16, 0.22), (sx * HS, sy * HS, 0.11), GALV, bevel=0.004, uv_scale=3.0)
            W.bolts(ctx, f"bolts{sx}{sy}", [((sx * (HS + 0.081), sy * HS + dz * 0.0, 0.05 + dz), (sx, 0, 0)) for dz in (0.0, 0.12)],
                    STEEL, r=0.012)
    corners = [(-HS, -HS), (HS, -HS), (HS, HS), (-HS, HS)]
    hang = ctx.drnd("hang").randrange(4) if ctx.worn else -1
    for f in range(4):
        a, b = corners[f], corners[(f + 1) % 4]
        for z in (1.5, SEC - 0.06):
            W.bar(ctx, f"girt{f}{z:.1f}", (a[0], a[1], z), (b[0], b[1], z), 0.06, 0.008, GALV, up=(0, 0, 1))
        for k, (z0, z1) in enumerate(((0.08, 1.5), (1.5, SEC - 0.06))):
            W.bar(ctx, f"xa{f}{k}", (a[0], a[1], z0), (b[0], b[1], z1), 0.05, 0.007, GALV)
            if hang == f and k == 0:
                # a brace sprung off its top bolt, hanging from the foot of the leg
                W.bar(ctx, f"xb{f}{k}", (b[0], b[1], z0), (b[0] * 0.55 + a[0] * 0.45, b[1] * 0.55 + a[1] * 0.45 - 0.25, z0 - 0.0 + 0.9),
                      0.05, 0.007, GALV)
                continue
            W.bar(ctx, f"xb{f}{k}", (b[0], b[1], z0), (a[0], a[1], z1), 0.05, 0.007, GALV)
    # The landing frame under the next level's kit slab (its bottom is 0.2 under the floor top).
    zf = SEC - 0.2 - 0.07
    for s in (-1, 1):
        W.bar(ctx, f"chan_x{s}", (-HS, s * 0.98, zf), (HS, s * 0.98, zf), 0.06, 0.12, DARK, up=(0, 0, 1))
        W.bar(ctx, f"chan_y{s}", (s * 0.98, -HS, zf - 0.005), (s * 0.98, HS, zf - 0.005), 0.06, 0.12, DARK, up=(0, 0, 1))
    W.bar(ctx, "joist", (0.0, -HS, zf), (0.0, HS, zf), 0.05, 0.1, DARK, up=(0, 0, 1))


def w4_ranger_tower_footing(ctx: K.Ctx) -> None:
    """The tower's four concrete piers, a hand's breadth out of the ground, the anchor bolts and the base
    plates the first section stands on."""
    r = ctx.rnd("piers")
    for sx in (-1, 1):
        for sy in (-1, 1):
            p = K.box(f"pier{sx}{sy}", (0.46, 0.46, 0.5), center=(sx * HS, sy * HS, 0.0), bevel=0.02, cuts=(1, 1, 1))
            K.noise_disp(p, 0.006, scale=5.0, seed=r.randint(0, 999))
            ctx.add(p, CONC, uv="box", uv_scale=1.5, patches=0.6, moss=0.3)
            _box(ctx, f"plate{sx}{sy}", (0.26, 0.26, 0.02), (sx * HS, sy * HS, 0.26), GALV, uv_scale=3.0)
            W.bolts(ctx, f"anchor{sx}{sy}", [((sx * HS + dx, sy * HS + dy, 0.27), (0, 0, 1)) for dx in (-0.09, 0.09) for dy in (-0.09, 0.09)],
                    STEEL, r=0.014, h=0.03)
    ctx.ground_clamp = True


# The cab: a 2 x 2 kit room (floor at the origin) with a window2 on each side (catalog SHELLS).
def _cab_walls(ctx, room, ops, *, z0, z1, mat, off=0.12):
    """Ribbed steel panels standing `off` outside the kit room's edge lines from z0 to z1, cut round the
    openings with a steel trim frame."""
    for side in ("N", "S", "E", "W"):
        start, along, out = room.side_line(side, off)
        L = room.length(side) + 2 * off
        st = start - along * off
        holes = [(a + off, b + off, hz0, hz1) for (a, b, hz0, hz1) in O.holes_on(side, ops, floor=room.floor)]
        cuts = sorted({z0, z1} | {max(z0, min(z1, h[2])) for h in holes} | {max(z0, min(z1, h[3])) for h in holes})
        for i in range(len(cuts) - 1):
            za, zb = cuts[i], cuts[i + 1]
            if zb - za < 0.01:
                continue
            for s0, s1 in O.clip_spans(0.0, L, za + 0.001, zb - 0.001, holes, min_len=0.01):
                p0 = st + along * s0
                p1 = st + along * s1
                pan = K.quad_sheet(f"{side}p{i}_{s0:.2f}", (p0.x, p0.y, za), (p1.x, p1.y, za), (p1.x, p1.y, zb), (p0.x, p0.y, zb),
                                   max(1, int((s1 - s0) / 0.5)), 1)
                K.solidify(pan, 0.03, offset=1.0 if side in ("N", "E") else -1.0)
                ctx.add(pan, mat, uv="box", uv_scale=1.0, patches=0.5)
        for (a, b, hz0, hz1) in holes:
            for t in (a, b):
                p = st + along * t
                W.bar(ctx, f"{side}trim{t:.2f}", (p.x, p.y, max(z0, hz0)), (p.x, p.y, min(z1, hz1)), 0.05, 0.06, STEEL,
                      up=tuple(out))
            for zz in (hz0, hz1):
                if z0 < zz < z1:
                    pa, pb = st + along * a, st + along * b
                    W.bar(ctx, f"{side}trimh{a:.2f}{zz:.1f}", (pa.x, pa.y, zz), (pb.x, pb.y, zz), 0.05, 0.06, STEEL,
                          up=tuple(out))
        # vertical ribs between the openings
        t = 0.25
        while t < L - 0.1:
            if not any(a - 0.04 < t < b + 0.04 for (a, b, _hz0, _hz1) in holes):
                p = st + along * t + out * 0.035
                W.bar(ctx, f"{side}rib{t:.2f}", (p.x, p.y, z0), (p.x, p.y, z1), 0.035, 0.02, mat, up=tuple(out))
            t += 0.25


def w4_ranger_tower_cab(ctx: K.Ctx) -> None:
    """The enclosed cab on top of the tower, round the POI's 2 x 2 kit room: green ribbed steel cladding
    cut for a window on every side, storm shutters propped open over each window on steel stays, the cab's
    floor frame and its skirt over the kit slab's edge, a whip antenna on a wall bracket and the lightning
    rod's down conductor to the top of the lattice (the kit roof is the cab's hip). Worn: a shutter hanging
    from one hinge, the whip bent. No collision: the kit walls hold."""
    ctx.ground_clamp = False  # the skirt and the floor frame hang below the cab's floor
    room = O.Room(int(ctx.param("w", 2)), int(ctx.param("d", 2)), float(ctx.param("floor", 0.0)))
    ops = [tuple(o) for o in ctx.param("openings", [])]
    z0, z1 = -0.28, 2.82
    _cab_walls(ctx, room, ops, z0=z0, z1=z1, mat=GREEN)
    hw, hd = room.w / 2 + 0.15, room.d / 2 + 0.15
    # floor frame under the kit slab
    for s in (-1, 1):
        W.bar(ctx, f"frame_x{s}", (-hw, s * (hd - 0.05), z0 + 0.04), (hw, s * (hd - 0.05), z0 + 0.04), 0.08, 0.14, DARK)
        W.bar(ctx, f"frame_y{s}", (s * (hw - 0.05), -hd, z0 + 0.04), (s * (hw - 0.05), hd, z0 + 0.04), 0.08, 0.14, DARK)
    # storm shutters: hinged at the top of each window, propped out on two stays
    loose = ctx.drnd("shutter").randrange(4) if ctx.worn else -1
    for k, (side, idx, kind) in enumerate(ops):
        holes = O.holes_on(side, [(side, idx, kind)], floor=room.floor)
        if not holes:
            continue
        a, b, hz0, hz1 = holes[0]
        start, along, out = room.side_line(side, 0.17)
        ca = start + along * a
        cb = start + along * b
        width = (cb - ca).length
        drop = hz1 - hz0
        ang = math.radians(55.0 if k != loose else 5.0)
        hinge_z = hz1 + 0.02
        mid = (ca + cb) / 2
        tip = mid + out * (math.sin(ang) * drop) + Vector((0, 0, hinge_z - math.cos(ang) * drop))
        hinge = mid + Vector((0, 0, hinge_z))
        sh = K.box(f"shutter{k}", (width, 0.03, drop), bevel=0.006)
        centre = (hinge + tip) / 2
        normal = (tip - hinge).cross(along).normalized()
        K.orient(sh, along, normal, centre)
        ctx.add(sh, GREEN, uv="box", uv_scale=1.0, patches=0.6)
        if k != loose:
            for t in (0.15, width - 0.15):
                base = ca + along * t + Vector((0, 0, hz0 + 0.2))
                end = ca + along * t + out * (math.sin(ang) * drop * 0.85) + Vector((0, 0, hinge_z - math.cos(ang) * drop * 0.85))
                W.rod(ctx, f"stay{k}{t:.1f}", base, end, 0.012, STEEL, segs=5)
    # whip antenna on a bracket off the east wall, the lightning rod's conductor down the north-west corner
    bx, by = hw + 0.05, 0.4
    W.bar(ctx, "bracket", (hw, by, 2.3), (bx + 0.12, by, 2.3), 0.05, 0.05, DARK)
    whip_top = (bx + 0.12 + (0.35 if ctx.worn else 0.0), by, 5.2 if not ctx.worn else 4.6)
    W.rod(ctx, "whip_base", (bx + 0.12, by, 2.0), (bx + 0.12, by, 2.9), 0.03, DARK, segs=8)
    W.rod(ctx, "whip", (bx + 0.12, by, 2.9), whip_top, 0.008, "road_steel", segs=5)
    W.rod(ctx, "conductor", (-hw - 0.02, hd + 0.02, 2.85), (-hw - 0.02, hd + 0.02, z0 - 0.3), 0.01, "road_brass", segs=5)
    # number plate of the tower on the south side
    _box(ctx, "plate", (0.42, 0.02, 0.16), (0.55, -hd - 0.05, 2.45), WHITE, uv_scale=3.0)


def w4_ranger_weather_screen(ctx: K.Ctx) -> None:
    """A Stevenson screen: a white louvred box on four legs with a double roof, its door to the north (here
    -Y, the front), the thermometers' rack showing through the door when it hangs open (worn), a hygrograph
    drum on the shelf. Destroyed: knocked off its stand on the grass."""
    r = ctx.rnd("screen")
    Wd, D, H = 0.78, 0.56, 0.62
    z0 = 1.15
    tilt = (0, 0, 0)
    parts = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            leg = W.bar_obj(f"leg{sx}{sy}", (sx * (Wd / 2 - 0.05), sy * (D / 2 - 0.05), -0.05), (sx * (Wd / 2 - 0.05), sy * (D / 2 - 0.05), z0),
                            0.06, 0.06, up=(1, 0, 0))
            ctx.add(leg, "wood_painted_white", long_axis=0, patches=0.6)
    for sy in (-1, 1):
        W.bar(ctx, f"rail{sy}", (-Wd / 2 + 0.02, sy * (D / 2 - 0.05), z0 - 0.3), (Wd / 2 - 0.02, sy * (D / 2 - 0.05), z0 - 0.3), 0.04, 0.04,
              "wood_painted_white")
    base = K.box("floor", (Wd, D, 0.03), center=(0, 0, z0 + 0.015))
    parts.append(ctx.add(base, "wood_painted_white", patches=0.5))
    # louvred sides: slanted slats on the back and the two ends, a louvred door on the front
    for side in ("back", "w", "e", "door"):
        n = 9
        for k in range(n):
            z = z0 + 0.06 + k * (H - 0.08) / n
            if side in ("back", "door"):
                y = D / 2 - 0.02 if side == "back" else -D / 2 + 0.02
                o = K.box(f"{side}{k}", (Wd - 0.06, 0.012, 0.06), center=(0, 0, 0))
                K.place(o, (0, y, z), (55 if side == "back" else -55, 0, 0))
            else:
                x = -Wd / 2 + 0.02 if side == "w" else Wd / 2 - 0.02
                o = K.box(f"{side}{k}", (0.012, D - 0.06, 0.06), center=(0, 0, 0))
                K.place(o, (x, 0, z), (0, 55 if side == "w" else -55, 0))
            ctx.add(o, "wood_painted_white", patches=0.5)
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.bar(ctx, f"post{sx}{sy}", (sx * (Wd / 2 - 0.02), sy * (D / 2 - 0.02), z0), (sx * (Wd / 2 - 0.02), sy * (D / 2 - 0.02), z0 + H),
                  0.035, 0.035, "wood_painted_white", up=(1, 0, 0))
    roof1 = K.box("roof1", (Wd + 0.06, D + 0.06, 0.025), center=(0, 0, z0 + H + 0.02))
    ctx.add(roof1, "wood_painted_white", patches=0.5)
    roof2 = K.box("roof2", (Wd + 0.16, D + 0.2, 0.025), center=(0, 0, 0))
    K.place(roof2, (0, 0, z0 + H + 0.11), (6, 0, 0))
    ctx.add(roof2, "wood_painted_white", patches=0.6)
    for sx in (-1, 1):
        _box(ctx, f"spacer{sx}", (0.04, D, 0.06), (sx * (Wd / 2 - 0.05), 0, z0 + H + 0.06), "wood_painted_white")
    # inside: the thermometer rack and the hygrograph drum (seen through the louvres and the open door)
    W.bar(ctx, "therm_rack", (-0.25, 0.0, z0 + 0.35), (0.25, 0.0, z0 + 0.35), 0.03, 0.02, "wood_stained")
    for k, x in enumerate((-0.18, 0.0, 0.18)):
        W.rod(ctx, f"therm{k}", (x, -0.02, z0 + 0.2), (x, -0.02, z0 + 0.5), 0.008, "glass_clear", segs=6)
    drum = K.cyl("drum", 0.06, 0.1, segs=12, center=(0.15, 0.08, z0 + 0.1))
    ctx.add(drum, "road_steel", uv="cyl", uv_axis=2, smooth=40)
    _ = r, tilt, parts
    if ctx.destroyed:
        # the whole screen pushed over onto its back beside the stand
        for o in list(ctx.parts):
            K.place(o, (0, 0, 0), (-80, 0, 12))
            K.place(o, (0.1, 0.9, 0.42))


def w4_ranger_rain_gauge(ctx: K.Ctx) -> None:
    """The standard 8-inch rain gauge: a copper-and-steel can with its funnel and measuring tube inside,
    in a ring stand screwed to a cedar post, the measuring stick clipped to the post."""
    W.rod(ctx, "post", (0, 0.04, 0.0), (0, 0.04, 0.62), 0.05, "wood_weathered", segs=8)
    can = K.cyl("can", 0.105, 0.58, segs=18, center=(0, -0.08, 0.92))
    ctx.add(can, GALV, uv="cyl", uv_axis=2, smooth=40, patches=0.5)
    rim = W.ring_obj("rim", 0.1, 0.112, 0.03, segs=18)
    K.place(rim, (0, -0.08, 1.21))
    ctx.add(rim, "road_brass", uv="box", uv_scale=4.0)
    fun = K.lathe("funnel", [(0.1, 0.0), (0.03, -0.09), (0.015, -0.12)], segs=16, cap_bottom=False, cap_top=False)
    K.place(fun, (0, -0.08, 1.2))
    ctx.add(fun, "road_brass", uv="box", uv_scale=4.0, smooth=40)
    for z in (0.7, 1.05):
        ring = W.ring_obj(f"stand{z}", 0.108, 0.125, 0.025, segs=18)
        K.place(ring, (0, -0.08, z))
        ctx.add(ring, DARK, uv="box", uv_scale=4.0)
    W.bar(ctx, "arm", (0, 0.0, 0.6), (0, -0.08, 0.7), 0.04, 0.01, DARK)
    stick = K.box("stick", (0.012, 0.004, 0.6), center=(0.07, 0.0, 0.35))
    ctx.add(stick, "wood_stained", uv="box", uv_scale=3.0)
    if ctx.worn:
        dent = K.cyl("leaf_litter", 0.09, 0.01, segs=10, center=(0, -0.08, 1.12))
        ctx.add(dent, "out_earth", uv="box", uv_scale=2.0)


def w4_ranger_anemometer_mast(ctx: K.Ctx) -> None:
    """A 10 m galvanised pipe mast on a hinged base plate, guyed three ways at two heights to screw
    anchors, the cup anemometer and the wind vane on a cross arm at the top, the cable down the mast to the
    junction box at chest height. Worn: a cup gone, the vane bent, one guy slack."""
    H = 10.0
    W.rod(ctx, "mast_lo", (0, 0, 0.05), (0, 0, 5.0), 0.038, GALV, segs=10)
    W.rod(ctx, "mast_hi", (0, 0, 4.95), (0, 0, H), 0.03, GALV, segs=10)
    _box(ctx, "base", (0.4, 0.4, 0.04), (0, 0, 0.02), STEEL, uv_scale=2.0)
    _box(ctx, "hinge", (0.12, 0.1, 0.16), (0, 0, 0.12), STEEL, uv_scale=3.0)
    _box(ctx, "jbox", (0.22, 0.12, 0.28), (0, -0.1, 1.5), "road_paint_grey", bevel=0.01, uv_scale=3.0)
    W.rod(ctx, "cable", (0.02, -0.04, 1.65), (0.02, -0.04, H - 0.3), 0.008, "tyre_rubber", segs=5)
    slack = ctx.drnd("slack").randrange(3) if ctx.worn else -1
    R = 2.0
    for k in range(3):
        a = math.radians(90 + k * 120)
        ax, ay = math.cos(a) * R, math.sin(a) * R
        _box(ctx, f"anchor{k}", (0.12, 0.12, 0.08), (ax, ay, 0.04), STEEL, uv_scale=3.0)
        for z in (4.6, 8.6):
            if k == slack and z > 5:
                pts = [(ax, ay, 0.08), (ax * 0.6, ay * 0.6, 0.15), (ax * 0.25, ay * 0.25, z * 0.35), (0, 0, z)]
                ctx.add(K.tube(f"guy{k}{z}", pts, 0.004, segs=4), STEEL, uv="box", uv_scale=6.0)
                continue
            W.rod(ctx, f"guy{k}{z}", (ax, ay, 0.08), (0, 0, z), 0.004, STEEL, segs=4)
        W.rod(ctx, f"collar{k}", (0, 0, 4.6), (0, 0, 4.66), 0.05, STEEL, segs=8)
    # cross arm, anemometer cups and the vane
    W.bar(ctx, "crossarm", (-0.6, 0, H - 0.05), (0.6, 0, H - 0.05), 0.04, 0.04, GALV)
    W.rod(ctx, "anemo_shaft", (-0.6, 0, H - 0.05), (-0.6, 0, H + 0.35), 0.015, STEEL, segs=6)
    lost = ctx.drnd("cup").randrange(3) if ctx.worn else -1
    for k in range(3):
        a = math.radians(k * 120 + 15)
        arm_end = Vector((-0.6 + math.cos(a) * 0.16, math.sin(a) * 0.16, H + 0.32))
        W.rod(ctx, f"cup_arm{k}", (-0.6, 0, H + 0.32), arm_end, 0.005, STEEL, segs=4)
        if k == lost:
            continue
        cup = K.lathe(f"cup{k}", [(0.0, -0.04), (0.03, -0.03), (0.045, 0.0)], segs=12, cap_bottom=False, cap_top=False)
        K.place(cup, (0, 0, 0), (0, 90, math.degrees(a) + 90))
        K.place(cup, arm_end)
        ctx.add(cup, "plastic_black", uv="box", uv_scale=4.0, smooth=40)
    W.rod(ctx, "vane_shaft", (0.6, 0, H - 0.05), (0.6, 0, H + 0.3), 0.015, STEEL, segs=6)
    bend = 25 if ctx.worn else 0
    vane = K.box("vane", (0.5, 0.008, 0.16), center=(0.22, 0, 0))
    K.place(vane, (0.6, 0, H + 0.3), (bend, 0, 30))
    ctx.add(vane, "road_alu", uv="box", uv_scale=2.0)
    W.rod(ctx, "vane_nose", (0.6, 0, H + 0.3), (0.6 - 0.2 * math.cos(math.radians(30)), -0.2 * math.sin(math.radians(30)), H + 0.3),
          0.012, DARK, segs=6)
    W.rod(ctx, "finial", (0, 0, H), (0, 0, H + 0.45), 0.008, "road_brass", segs=5)


# ============================================================================================
# The station
# ============================================================================================

def _wheel(ctx, name, x, y, r_out=0.42, width=0.28, flat=False):
    ty = P.tyre(f"{name}_tyre", r_out, 0.25, width, segs=18)
    K.place(ty, (x, y, r_out))
    if flat:
        P.flatten_tyre(ty, r_out, r_out, amount=0.3)
    ctx.add(ty, "tyre_rubber", uv="box", uv_scale=2.0, smooth=40)
    rim = K.cyl(f"{name}_rim", 0.25, width * 0.8, segs=14, center=(x, y, r_out), axis="X")
    ctx.add(rim, WHITE if not ctx.destroyed else "road_burnt", uv="box", uv_scale=3.0)
    hub = K.cyl(f"{name}_hub", 0.09, width * 0.85, segs=8, center=(x, y, r_out), axis="X")
    ctx.add(hub, DARK, uv="box", uv_scale=4.0)


def w4_ranger_brush_truck(ctx: K.Ctx) -> None:
    """The district's brush truck, a Type 6 engine: a crew-cab one-ton chassis painted forest green with a
    white roof and stripe, the brush guard and winch bumper on the front, the light bar, and on the flatbed
    the 300-gallon tank, the pump, the hose reel and the side lockers, a ladder and shovels in the rack.
    Front -Y. Worn: dust, a flat front tyre, a locker door hanging; destroyed: burnt out on its rims."""
    burnt = ctx.destroyed
    paint = "road_burnt" if burnt else GREEN
    white = "road_burnt" if burnt else WHITE
    glass = "road_glass"
    L, Wd = 6.2, 2.1
    y_front, y_rear = -L / 2 + 0.25, L / 2
    # chassis rails and the axles
    for sx in (-1, 1):
        W.bar(ctx, f"rail{sx}", (sx * 0.45, y_front, 0.62), (sx * 0.45, y_rear - 0.1, 0.62), 0.1, 0.2, DARK)
    flat = ctx.worn and not burnt
    for sx in (-1, 1):
        _wheel(ctx, f"wf{sx}", sx * 0.92, -1.75, flat=(flat and sx == 1))
        _wheel(ctx, f"wr{sx}", sx * 0.92, 1.45)
    # the cab: hood, crew cab, windscreen, doors, mirrors
    hood = K.box("hood", (1.95, 1.25, 0.6), center=(0, -2.45, 1.15), bevel=0.06, cuts=(2, 2, 1))
    ctx.add(hood, paint, uv="box", uv_scale=1.0, patches=0.5)
    grille = K.box("grille", (1.0, 0.04, 0.42), center=(0, -3.08, 1.12))
    ctx.add(grille, DARK if not burnt else "road_burnt", uv="box", uv_scale=3.0)
    for sx in (-1, 1):
        lamp = K.cyl(f"head{sx}", 0.09, 0.04, segs=12, center=(sx * 0.68, -3.09, 1.2), axis="Y")
        ctx.add(lamp, "lens_clear" if not burnt else "road_burnt", uv="box", ao=not burnt)
    cab = K.box("cab", (2.0, 2.0, 1.25), center=(0, -0.85, 1.6), bevel=0.05, cuts=(2, 2, 1))
    ctx.add(cab, paint, uv="box", uv_scale=1.0, patches=0.5)
    roof = K.box("roof", (1.94, 1.9, 0.08), center=(0, -0.8, 2.25), bevel=0.03)
    ctx.add(roof, white, uv="box", uv_scale=1.0, patches=0.5)
    if not burnt:
        ws = K.box("windscreen", (1.8, 0.03, 0.55), center=(0, 0, 0))
        K.place(ws, (0, -1.82, 1.95), (-18, 0, 0))
        ctx.add(ws, glass, uv="box", ao=False)
        for sx in (-1, 1):
            for k, y in enumerate((-1.25, -0.4)):
                win = K.box(f"win{sx}{k}", (0.03, 0.72, 0.45), center=(sx * 1.005, y, 1.98))
                ctx.add(win, glass, uv="box", ao=False)
    for sx in (-1, 1):
        stripe = K.box(f"stripe{sx}", (0.02, 4.4, 0.1), center=(sx * 1.01, -0.6, 1.32))
        ctx.add(stripe, white, uv="box", uv_scale=2.0, patches=0.5)
        W.bar(ctx, f"mirror_arm{sx}", (sx * 1.0, -1.6, 1.95), (sx * 1.25, -1.6, 1.95), 0.03, 0.03, DARK)
        _box(ctx, f"mirror{sx}", (0.05, 0.08, 0.3), (sx * 1.27, -1.6, 1.95), DARK, uv_scale=3.0)
        _box(ctx, f"step{sx}", (0.18, 1.6, 0.05), (sx * 1.08, -0.85, 0.55), DARK, uv_scale=2.0)
    # light bar
    lb = K.box("lightbar", (1.3, 0.25, 0.1), center=(0, -1.3, 2.34), bevel=0.02)
    ctx.add(lb, "lens_red" if not burnt else "road_burnt", uv="box", ao=False)
    # brush guard + winch bumper (the part the player climbs over)
    bump = K.box("bumper", (2.1, 0.32, 0.3), center=(0, -3.2, 0.72), bevel=0.02)
    ctx.add(bump, DARK, uv="box", uv_scale=2.0, patches=0.6)
    winch = K.cyl("winch", 0.12, 0.6, segs=12, center=(0, -3.3, 0.72), axis="X")
    ctx.add(winch, DARK, uv="box", uv_scale=3.0)
    for sx in (-1, 0, 1):
        x = sx * 0.85
        W.rod(ctx, f"guard{sx}", (x, -3.28, 0.85), (x * 0.95, -3.22, 1.5), 0.03, DARK, segs=6)
    W.rod(ctx, "guard_top", (-0.85, -3.22, 1.5), (0.85, -3.22, 1.5), 0.03, DARK, segs=6)
    # the bed: tank, pump, reel, lockers
    bed = K.box("bed", (2.05, 3.05, 0.12), center=(0, 1.45, 0.98))
    ctx.add(bed, DARK, uv="box", uv_scale=1.5, patches=0.6)
    for sx in (-1, 1):
        lk = K.box(f"locker{sx}", (0.45, 2.9, 0.95), center=(sx * 0.8, 1.45, 1.52), bevel=0.02, cuts=(0, 3, 1))
        ctx.add(lk, paint, uv="box", uv_scale=1.0, patches=0.5)
        for k in range(3):
            door = K.box(f"ldoor{sx}{k}", (0.02, 0.88, 0.82), center=(sx * 1.035, 0.55 + k * 0.95, 1.52))
            if ctx.worn and k == 1 and sx == 1 and not burnt:
                K.remove(door)
                door = K.box(f"ldoor{sx}{k}", (0.02, 0.88, 0.82), center=(0, 0.44, 0))
                K.place(door, (sx * 1.04, 0.11 + k * 0.95, 1.52), (0, 0, -sx * 70))
            ctx.add(door, white if k != 1 else paint, uv="box", uv_scale=1.5, patches=0.5)
    tank = K.box("tank", (1.1, 1.8, 0.9), center=(0, 1.75, 1.5), bevel=0.06)
    ctx.add(tank, "road_paint_white" if not burnt else "road_burnt", uv="box", uv_scale=1.0, patches=0.6)
    pump = K.box("pump", (0.6, 0.45, 0.45), center=(0, 0.5, 1.3), bevel=0.03)
    ctx.add(pump, "road_paint_red" if not burnt else "road_burnt", uv="box", uv_scale=2.0, patches=0.5)
    reel = K.cyl("reel", 0.32, 0.55, segs=16, center=(0, 2.85, 1.42), axis="X")
    ctx.add(reel, "road_paint_red" if not burnt else "road_burnt", uv="box", uv_scale=2.0)
    hose = K.cyl("hose", 0.27, 0.5, segs=16, center=(0, 2.85, 1.42), axis="X")
    ctx.add(hose, "canvas_khaki" if not burnt else "road_burnt", uv="cyl", uv_axis=0, smooth=40)
    # ladder and tool rack over the lockers
    for sx in (-1, 1):
        W.rod(ctx, f"rack{sx}", (sx * 0.8, 0.1, 2.05), (sx * 0.8, 2.8, 2.05), 0.02, DARK, segs=6)
    for k in range(5):
        W.rod(ctx, f"rung{k}", (-0.8, 0.3 + k * 0.6, 2.06), (0.8, 0.3 + k * 0.6, 2.06), 0.015, GALV, segs=5)
    if not burnt:
        for k, x in enumerate((-0.4, 0.15)):
            W.rod(ctx, f"shovel{k}", (x, 0.2, 2.12), (x + 0.05, 1.6, 2.12), 0.015, "wood_weathered", segs=5)
            _box(ctx, f"blade{k}", (0.22, 0.28, 0.02), (x + 0.06, 1.75, 2.12), DARK, uv_scale=3.0)
    # rear bumper and tail lights
    _box(ctx, "rear_bumper", (2.0, 0.15, 0.2), (0, y_rear - 0.05, 0.62), DARK, uv_scale=2.0)
    for sx in (-1, 1):
        _box(ctx, f"tail{sx}", (0.12, 0.03, 0.2), (sx * 0.9, y_rear - 0.02, 1.0), "lens_red" if not burnt else "road_burnt", ao=False)


def w4_ranger_checkpoint_barrier(ctx: K.Ctx) -> None:
    """The checkpoint's barrier arm across the forest road: a steel pivot post with its concrete-filled
    counterweight box on the east end, the red-and-white striped arm down on a fork post at the other end,
    the Cordon's STOP / CHECKPOINT board hung in the middle, both posts on concrete pads. Worn: the arm
    bowed and taped where it was splinted; destroyed: the arm snapped and down on the road."""
    span = 4.5
    px = span / 2 - 0.1  # pivot post (+x)
    fx = -span / 2 + 0.15  # fork post (-x)
    zarm = 1.0
    for x, sz in ((px, 0.5), (fx, 0.35)):
        _box(ctx, f"pad{x:.1f}", (sz, sz, 0.12), (x, 0, 0.06), CONC, uv_scale=1.5, patches=0.6)
    _box(ctx, "pivot_post", (0.16, 0.16, 1.0), (px, 0, 0.6), "road_paint_yellow", bevel=0.01, uv_scale=2.0, patches=0.6)
    _box(ctx, "hinge", (0.2, 0.24, 0.2), (px, 0, zarm + 0.05), DARK, bevel=0.01, uv_scale=3.0)
    W.rod(ctx, "fork_post", (fx, 0, 0.1), (fx, 0, zarm - 0.08), 0.04, "road_paint_yellow", segs=8)
    for s in (-1, 1):
        W.bar(ctx, f"fork{s}", (fx, s * 0.03, zarm - 0.1), (fx, s * 0.09, zarm + 0.08), 0.02, 0.02, DARK)
    _box(ctx, "counterweight", (0.45, 0.3, 0.35), (px + 0.3, 0, zarm + 0.05), CONC, bevel=0.02, uv_scale=1.5, patches=0.6)
    snapped = ctx.destroyed
    n = 8
    x0, x1 = px - 0.05, fx - 0.25
    for k in range(n):
        a = x0 + (x1 - x0) * k / n
        b = x0 + (x1 - x0) * (k + 1) / n
        if snapped and k >= 5:
            # the broken end lying on the road
            dz = 0.08
            seg = K.box(f"arm{k}", (abs(b - a), 0.08, 0.1), center=((a + b) / 2, 0.35, dz))
            K.place(seg, (0, 0, 0))
        else:
            bow = -0.06 * math.sin(math.pi * k / n) if ctx.worn else 0.0
            seg = K.box(f"arm{k}", (abs(b - a) + 0.002, 0.08, 0.1), center=((a + b) / 2, 0, zarm + bow))
        ctx.add(seg, "road_paint_red" if k % 2 == 0 else "road_paint_white", uv="box", uv_scale=2.0, patches=0.6)
    if ctx.worn and not snapped:
        tape = K.cyl("splint", 0.07, 0.25, segs=8, center=(px - 2.3, 0, zarm - 0.06), axis="X")
        ctx.add(tape, "road_alu", uv="box", uv_scale=4.0)
    # the Cordon's board under the arm, both faces
    _box(ctx, "board", (0.62, 0.02, 0.31), (0.2, 0, zarm - 0.27), "road_plywood", uv_scale=2.0)
    for side, rz in ((-1, 0.0), (1, 180.0)):
        _face(ctx, f"stop{side}", 0.6, 0.29, _rect("checkpoint"), (0.2, side * 0.0115, zarm - 0.27), rz)
    for s in (-1, 1):
        W.rod(ctx, f"hanger{s}", (0.2 + s * 0.25, 0, zarm - 0.12), (0.2 + s * 0.25, 0, zarm - 0.05), 0.004, STEEL, segs=4)


def w4_ranger_fuel_pump(ctx: K.Ctx) -> None:
    """The station's elevated fuel tank: a red 300-gallon steel tank lying on a welded angle stand over a
    drip tray, the gravity hose and nozzle hung on its hook, the shut-off valve, the hand rotary pump
    bolted to the leg for when the valve sticks, a fire extinguisher on the far leg. Worn: rust and
    drips; destroyed: a leg buckled, the tank tipped and holed, the hose cut."""
    Lt, R = 1.8, 0.45
    zt = 1.25 + R
    tip = 9.0 if ctx.destroyed else 0.0
    legs = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            z_top = 1.25 if not (ctx.destroyed and sx == 1 and sy == -1) else 0.9
            legs.append(W.bar(ctx, f"leg{sx}{sy}", (sx * 0.7, sy * 0.45, 0.0), (sx * 0.6, sy * 0.32, z_top), 0.06, 0.06, DARK, up=(1, 0, 0)))
    for sx in (-1, 1):
        W.bar(ctx, f"saddle{sx}", (sx * 0.6, -0.4, 1.22), (sx * 0.6, 0.4, 1.22), 0.08, 0.08, DARK)
        W.bar(ctx, f"brace{sx}", (sx * 0.68, -0.43, 0.3), (sx * 0.68, 0.43, 0.3), 0.04, 0.04, DARK)
    tank = K.cyl("tank", R, Lt, segs=20, center=(0, 0, 0), axis="X", bevel=0.03)
    K.place(tank, (0, 0, zt), (tip, 0, 0))
    ctx.add(tank, "road_paint_red", uv="cyl", uv_axis=0, smooth=40, patches=0.7)
    for sx in (-1, 1):
        band = K.cyl(f"band{sx}", R + 0.01, 0.05, segs=20, center=(sx * 0.6, 0, zt), axis="X")
        ctx.add(band, DARK, uv="box", uv_scale=3.0)
    _box(ctx, "fill_cap", (0.14, 0.14, 0.08), (-0.4, 0, zt + R + 0.02), DARK, uv_scale=3.0)
    W.rod(ctx, "vent", (0.5, 0, zt + R), (0.5, 0, zt + R + 0.35), 0.02, GALV, segs=6)
    _box(ctx, "vent_cap", (0.08, 0.08, 0.04), (0.5, 0, zt + R + 0.37), GALV, uv_scale=3.0)
    _box(ctx, "valve", (0.1, 0.1, 0.12), (0.75, -0.25, zt - R - 0.05), "road_brass", uv_scale=3.0)
    if not ctx.destroyed:
        pts = [(0.75, -0.25, zt - R - 0.1), (0.85, -0.5, 1.0), (0.82, -0.55, 0.5), (0.75, -0.52, 0.9)]
        ctx.add(K.tube("hose", pts, 0.022, segs=6), "tyre_rubber", uv="box", uv_scale=3.0, smooth=40)
        _box(ctx, "nozzle", (0.06, 0.25, 0.08), (0.75, -0.55, 0.95), "road_alu", uv_scale=3.0)
    else:
        pts = [(0.75, -0.25, zt - R - 0.1), (0.9, -0.6, 0.4), (1.0, -0.8, 0.03)]
        ctx.add(K.tube("hose", pts, 0.022, segs=6), "tyre_rubber", uv="box", uv_scale=3.0, smooth=40)
    _box(ctx, "hook", (0.04, 0.12, 0.04), (0.68, -0.5, 1.0), DARK, uv_scale=4.0)
    # hand pump on the -x leg
    _box(ctx, "pump_body", (0.16, 0.16, 0.3), (-0.82, -0.3, 0.95), "road_paint_yellow", uv_scale=3.0)
    W.rod(ctx, "pump_crank", (-0.82, -0.39, 1.0), (-0.82, -0.55, 1.1), 0.012, DARK, segs=5)
    # drip tray
    tray = K.box("tray", (1.5, 0.95, 0.12), center=(0, 0, 0.06))
    ctx.add(tray, "road_steel", uv="box", uv_scale=1.5, patches=0.7)
    if ctx.worn:
        slick = K.box("slick", (1.3, 0.8, 0.005), center=(0, 0, 0.1))
        ctx.add(slick, "road_oil_dark", uv="box", uv_scale=1.0, ao=False)
    ext = K.cyl("extinguisher", 0.07, 0.42, segs=12, center=(-0.62, 0.42, 0.55))
    ctx.add(ext, "road_paint_red", uv="cyl", uv_axis=2, smooth=40, patches=0.5)


def w4_ranger_compound_gate(ctx: K.Ctx) -> None:
    """The compound's double chain-link gate, both leaves swung back inside the fence (+Y) and left
    open, on 3-inch posts in concrete; the chain hangs off the east post with its padlock open, a drop rod
    under each leaf. Collision none: the way in is the open gap; the leaves stand along the drive."""
    gap = 4.2
    for sx in (-1, 1):
        x = sx * (gap / 2 + 0.05)
        W.rod(ctx, f"post{sx}", (x, 0, -0.02), (x, 0, 2.15), 0.045, GALV, segs=10)
        cap = K.cyl(f"cap{sx}", 0.055, 0.05, segs=10, center=(x, 0, 2.17))
        ctx.add(cap, GALV, uv="box", uv_scale=3.0)
        ctx.add(K.cyl(f"foot{sx}", 0.16, 0.1, segs=8, center=(x, 0, 0.05)), CONC, uv="box", uv_scale=2.0)
        swing = 82.0 + (ctx.drnd(f"sw{sx}").uniform(-6, 6) if ctx.worn else 0.0)
        a = math.radians(swing)
        L = gap / 2 - 0.08
        d = Vector((-sx * math.cos(a), math.sin(a), 0.0))
        h0 = Vector((x - sx * 0.06, 0.0, 0.0)) + Vector((0, 0.02, 0))
        frame = []
        for z in (0.1, 1.95):
            frame.append(W.rod_obj(f"f{sx}{z}", h0 + Vector((0, 0, z)), h0 + d * L + Vector((0, 0, z)), 0.02))
        frame.append(W.rod_obj(f"f{sx}v0", h0 + Vector((0, 0, 0.1)), h0 + Vector((0, 0, 1.95)), 0.022))
        frame.append(W.rod_obj(f"f{sx}v1", h0 + d * L + Vector((0, 0, 0.1)), h0 + d * L + Vector((0, 0, 1.95)), 0.02))
        frame.append(W.rod_obj(f"f{sx}br", h0 + Vector((0, 0, 0.1)), h0 + d * L + Vector((0, 0, 1.95)), 0.014))
        ctx.add(K.merge_parts(frame, f"leaf{sx}"), GALV, uv="box", uv_scale=2.0, patches=0.5)
        p0 = h0 + Vector((0, 0, 0.12))
        p1 = h0 + d * L + Vector((0, 0, 0.12))
        m = K.quad_sheet(f"mesh{sx}", tuple(p0), tuple(p1), tuple(p1 + Vector((0, 0, 1.81))), tuple(p0 + Vector((0, 0, 1.81))), 4, 4)
        ctx.add(m, "chainlink", uv=None, patches=0.3)
        tipv = h0 + d * L
        W.rod(ctx, f"drop{sx}", tipv + Vector((0.02 * sx, 0, 0.0)), tipv + Vector((0.02 * sx, 0, 0.7)), 0.01, GALV, segs=5)
    ch = W.chain_obj("chain", [(gap / 2 + 0.1, -0.03, 1.2), (gap / 2 + 0.12, -0.06, 0.8), (gap / 2 + 0.08, -0.04, 0.55)], link=0.05, wire=0.007)
    ctx.add(ch, "trap_chain", uv="box", uv_scale=8.0, smooth=40)
    ctx.add(K.box("lock", (0.06, 0.03, 0.07), center=(gap / 2 + 0.08, -0.05, 0.5), bevel=0.006), "lock_steel", uv="box")


def w4_ranger_gun_safe(ctx: K.Ctx) -> None:
    """The district's gun safe: a dark green steel cabinet with a combination dial, a three-spoke handle
    and a keyed lock under it (the district key), the hinges outside on the left. Worn: scratched and
    dented where somebody tried a pry bar; destroyed: the door pried open and bent back."""
    Wd, D, H = 0.74, 0.58, 1.52
    body = K.box("body", (Wd, D - 0.05, H), center=(0, 0.025, H / 2), bevel=0.015, cuts=(1, 1, 2))
    ctx.add(body, "steel_safe_black", uv="box", uv_scale=1.0, patches=0.5)
    door_parts = []
    dr = K.box("door", (Wd - 0.04, 0.06, H - 0.06), center=(0, -D / 2 + 0.03, H / 2), bevel=0.012)
    door_parts.append(ctx.add(dr, "steel_locker_green", uv="box", uv_scale=1.0, patches=0.5))
    dial = K.cyl("dial", 0.055, 0.03, segs=16, center=(0.05, -D / 2 - 0.015, H * 0.62), axis="Y")
    door_parts.append(ctx.add(dial, "road_chrome", uv="box", uv_scale=4.0))
    hub = K.cyl("hub", 0.03, 0.04, segs=10, center=(0.05, -D / 2 - 0.02, H * 0.48), axis="Y")
    door_parts.append(ctx.add(hub, "road_chrome", uv="box", uv_scale=4.0))
    for k in range(3):
        a = math.radians(90 + k * 120)
        door_parts.append(W.rod(ctx, f"spoke{k}", (0.05, -D / 2 - 0.035, H * 0.48),
                                (0.05 + math.cos(a) * 0.13, -D / 2 - 0.035, H * 0.48 + math.sin(a) * 0.13), 0.01, "road_chrome", segs=6))
    key = K.cyl("keylock", 0.018, 0.02, segs=10, center=(0.05, -D / 2 - 0.01, H * 0.38), axis="Y")
    door_parts.append(ctx.add(key, "road_brass", uv="box", uv_scale=4.0))
    for z in (0.25, H - 0.25):
        hg = K.cyl(f"hinge{z:.1f}", 0.02, 0.12, segs=8, center=(-Wd / 2 + 0.01, -D / 2 + 0.01, z))
        ctx.add(hg, DARK, uv="box", uv_scale=4.0)
    plinth = K.box("plinth", (Wd - 0.02, D - 0.07, 0.04), center=(0, 0.03, 0.02))
    ctx.add(plinth, DARK, uv="box")
    if ctx.worn:
        for k in range(3):
            s = K.box(f"scratch{k}", (0.15, 0.004, 0.01), center=(Wd / 2 - 0.1, -D / 2 - 0.002, H * (0.4 + k * 0.05)))
            ctx.add(s, "road_steel", uv="box", ao=False)
    if ctx.destroyed:
        # swing the door open on its left hinge (pivot at the left front edge)
        pivot = Vector((-Wd / 2 + 0.01, -D / 2 + 0.01, 0))
        for o in door_parts:
            for v in o.data.vertices:
                rel = v.co - pivot
                a = math.radians(-115)
                v.co = pivot + Vector((rel.x * math.cos(a) - rel.y * math.sin(a), rel.x * math.sin(a) + rel.y * math.cos(a), rel.z))
            o.data.update()
        inside = K.box("shelf", (Wd - 0.12, D - 0.14, 0.02), center=(0, 0.03, H * 0.7))
        ctx.add(inside, "wood_stained", uv="box")


def w4_ranger_fire_danger_sign(ctx: K.Ctx) -> None:
    """The fire danger rating sign by the gate: a routed cedar board on two posts under a little shingled
    roof, the half-dial painted in its five bands (low, moderate, high, very high, extreme) and the arrow
    left on EXTREME the day the Cordon came. Worn: the paint weathered, the arrow drooping."""
    top = 2.25
    for sx in (-1, 1):
        W.bar(ctx, f"post{sx}", (sx * 0.95, 0, -0.05), (sx * 0.95, 0, top + 0.1), 0.11, 0.11, "wood_weathered", up=(1, 0, 0))
    board = K.box("board", (1.8, 0.05, 1.05), center=(0, 0, top - 0.55), bevel=0.01, cuts=(2, 0, 1))
    ctx.add(board, "wood_stained", uv="box", uv_scale=1.0, patches=0.5)
    face = K.box("face", (1.62, 0.01, 0.9), center=(0, -0.03, top - 0.55))
    ctx.add(face, "wood_painted_white", uv="box", uv_scale=1.0, patches=0.5)
    cx, cz = 0.0, top - 0.95
    R0, R1 = 0.25, 0.72
    bands = ["car_paint_green", "road_paint_blue", "road_paint_yellow", "road_paint_orange", "road_paint_red"]
    for k, mat in enumerate(bands):
        a0 = math.pi - k * math.pi / 5
        a1 = math.pi - (k + 1) * math.pi / 5
        steps = 4
        for j in range(steps):
            b0 = a0 + (a1 - a0) * j / steps
            b1 = a0 + (a1 - a0) * (j + 1) / steps
            q = K.quad_sheet(f"band{k}{j}", (cx + math.cos(b0) * R0, -0.036, cz + math.sin(b0) * R0),
                             (cx + math.cos(b0) * R1, -0.036, cz + math.sin(b0) * R1),
                             (cx + math.cos(b1) * R1, -0.036, cz + math.sin(b1) * R1),
                             (cx + math.cos(b1) * R0, -0.036, cz + math.sin(b1) * R0))
            ctx.add(q, mat, uv="box", uv_scale=2.0, patches=0.5)
    ang = math.radians(18 if not ctx.worn else 8)
    tip = (cx + math.cos(ang) * 0.66, -0.05, cz + math.sin(ang) * 0.66)
    W.bar(ctx, "arrow", (cx, -0.05, cz), tip, 0.06, 0.012, "road_paint_black", up=(0, -1, 0))
    hub = K.cyl("pivot", 0.04, 0.02, segs=10, center=(cx, -0.055, cz), axis="Y")
    ctx.add(hub, "road_brass", uv="box", uv_scale=4.0)
    for s in (-1, 1):
        rf = K.box(f"roof{s}", (2.2, 0.3, 0.03), center=(0, 0, 0))
        K.place(rf, (0, s * 0.12, top + 0.16), (s * 25, 0, 0))
        ctx.add(rf, "farm_wood_cedar", uv="box", uv_scale=1.0, patches=0.6, moss=0.3)


BUILDERS = {
    "w4_ranger_tower_leg_section": w4_ranger_tower_leg_section,
    "w4_ranger_tower_footing": w4_ranger_tower_footing,
    "w4_ranger_tower_cab": w4_ranger_tower_cab,
    "w4_ranger_weather_screen": w4_ranger_weather_screen,
    "w4_ranger_rain_gauge": w4_ranger_rain_gauge,
    "w4_ranger_anemometer_mast": w4_ranger_anemometer_mast,
    "w4_ranger_brush_truck": w4_ranger_brush_truck,
    "w4_ranger_checkpoint_barrier": w4_ranger_checkpoint_barrier,
    "w4_ranger_fuel_pump": w4_ranger_fuel_pump,
    "w4_ranger_compound_gate": w4_ranger_compound_gate,
    "w4_ranger_gun_safe": w4_ranger_gun_safe,
    "w4_ranger_fire_danger_sign": w4_ranger_fire_danger_sign,
}


def build(params: dict, outputs: list[str]) -> None:
    K.run(params, outputs, BUILDERS)
