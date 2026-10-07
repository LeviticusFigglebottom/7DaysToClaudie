"""Forest set pieces, round 4 (ADR-0053): props of the trestle tunnel (w4_trestle_tunnel), an abandoned logging
line's timber trestle over a dry ravine into a tunnel the Cordon blew with the work train inside.

The trestle: its bents (creosoted posts, cap, sway braces), the deck dressing laid on the POI's kit deck (stringers
under it, tie ends, guard timbers, rails), timber cribs for the abutment. The tunnel: the hillside over it (its
collision is only the plinth the kit rooms stand on), the concrete portal face, track on ballast, the collapse with
the buried engine's cab, a derailed log flatcar and a boxcar whose plank floor is its collision box (vault in at
the door; lumber bundles inside keep its walls honest). The section house: a pump handcar, the foreman's key board,
a spike keg and a pile of old ties.

Conventions (docs/ASSET_PIPELINE.md): metres, Z up, front -Y, origin bottom centre; PoiBuilder's collision box is
the def's size centred over the origin (game/data/props/wild4_trestle.json). Wall props: origin on the wall plane.
'clean' is the line as it was kept, 'worn' a few seasons abandoned, 'destroyed' broken.
"""
from __future__ import annotations

import math
import random

from mathutils import Vector

from lib import props_ext_kit as K
from lib import props_outskirts_parts as O
from lib import props_wild_parts as W

TIMBER = "wood_creosote"
TIMBER_ROT = "mine_timber_rot"
RAIL = "mine_rail"
RUST = "mine_steel_rust"
IRON = "wild_cast_iron_rust"
BALLAST = "mine_ballast"
ROCK = "rock_granite"
RUBBLE = "mine_rubble"
CONCRETE = "mine_concrete"
OXIDE = "wild_paint_red_oxide"
PLANK = "wood_weathered"

GAUGE = 1.07  # rail centres, m (a light logging line)


def _rail(ctx, name, y0, y1, x, z0, *, mat=RAIL, kink=0.0):
    """One light rail along Y from y0 to y1 at x, its foot on z0 (0.09 m tall)."""
    prof = W.prof_i(0.09, 0.075, 0.014, 0.012)
    a = Vector((x, y0, z0 + 0.045))
    b = Vector((x + kink, y1, z0 + 0.045))
    return W.section(ctx, name, a, b, prof, mat, up=(0, 0, 1), smooth=None, patches=0.4)


def _bolt(ctx, name, at, axis="Y"):
    o = K.cyl(name, 0.025, 0.05, segs=6, center=at, axis=axis)
    return ctx.add(o, IRON, uv="box", uv_scale=8.0)


# ============================================================================================
# The trestle
# ============================================================================================

def w4_trestle_bent(ctx: K.Ctx) -> None:
    """A bent across the track (its plane along X): two plumb posts and two battered outer posts on a mudsill
    over concrete footings, a cap at 2.4-2.55 m, a girt half way up and X sway braces bolted on both faces."""
    r = ctx.rnd("bent")
    top = 2.55
    for k, x in enumerate((-2.3, -0.75, 0.75, 2.3)):
        f = K.box(f"footing{k}", (0.6, 0.6, 0.25), center=(x * 0.95, 0, 0.1), bevel=0.02)
        ctx.add(f, CONCRETE, uv="box", uv_scale=1.5, patches=0.5, moss=0.3)
    W.bar(ctx, "mudsill", (-2.3, 0, 0.32), (2.3, 0, 0.32), 0.3, 0.25, TIMBER, bevel=0.01, cuts=4, moss=0.3)
    posts = [((-2.05, 0.45), (-1.2, top - 0.15)), ((-0.5, 0.45), (-0.5, top - 0.15)),
             ((0.5, 0.45), (0.5, top - 0.15)), ((2.05, 0.45), (1.2, top - 0.15))]
    for k, ((x0, z0), (x1, z1)) in enumerate(posts):
        W.bar(ctx, f"post{k}", (x0, 0, z0), (x1, 0, z1), 0.28, 0.28, TIMBER, bevel=0.012, cuts=3, moss=0.2)
    W.bar(ctx, "cap", (-1.6, 0, top - 0.075), (1.6, 0, top - 0.075), 0.32, 0.15, TIMBER, bevel=0.01, cuts=3)
    for side in (-1, 1):
        y = side * 0.19
        W.bar(ctx, f"girt{side}", (-1.75, y, 1.35), (1.75, y, 1.35), 0.22, 0.08, TIMBER, up=(0, 1, 0), bevel=0.008)
        hang = ctx.worn and side > 0
        a, b = (-1.95, y, 0.6), (1.35, y, top - 0.3)
        if hang:
            # Its top bolt has rusted through: the brace hangs off the bottom one.
            b = (-0.6, y - 0.05, -0.2)
        W.bar(ctx, f"brace_a{side}", a, b, 0.2, 0.07, TIMBER, up=(0, 1, 0), bevel=0.008)
        W.bar(ctx, f"brace_b{side}", (1.95, y, 0.6), (-1.35, y, top - 0.3), 0.2, 0.07, TIMBER, up=(0, 1, 0), bevel=0.008)
        for x in (-1.2, -0.5, 0.5, 1.2):
            _bolt(ctx, f"bolt{side}{x}", (x, y + side * 0.04, 1.35))
    if ctx.worn:
        # A split in the north post and drift litter at the foot.
        for k in range(5):
            c = K.chunk(f"litter{k}", r.uniform(0.12, 0.25), r, n=8, flat=0.5)
            K.place(c, (r.uniform(-2.2, 2.2), r.uniform(-0.4, 0.4), 0.04))
            ctx.add(c, "out_bark_slab" if k % 2 else ROCK, uv="box", uv_scale=2.0, patches=0.5, moss=0.4)


def w4_trestle_deck_section(ctx: K.Ctx) -> None:
    """3.2 m of deck dressing (track along Y) laid on a 3 m kit deck whose top is the origin: four stringers
    under the deck (0.2-0.6 m down), the tie ends past both edges, a guard timber on each side, two rails on
    tie plates."""
    ctx.ground_clamp = False
    r = ctx.rnd("deck")
    L = 3.2
    for k, x in enumerate((-1.15, -0.4, 0.4, 1.15)):
        W.bar(ctx, f"stringer{k}", (x, -L / 2, -0.4), (x, L / 2, -0.4), 0.22, 0.4, TIMBER, bevel=0.01, cuts=3)
    n = 8
    for i in range(n):
        y = -L / 2 + (i + 0.5) * L / n
        for side in (-1, 1):
            if ctx.worn and side > 0 and i in (2, 5):
                continue
            W.bar(ctx, f"tie{i}{side}", (side * 1.5, y, -0.1), (side * 1.9, y, -0.1), 0.2, 0.2, TIMBER, bevel=0.01)
    for side in (-1, 1):
        if ctx.worn and side < 0:
            # This side's guard timber went over the edge; two short lengths lie on the ties.
            W.bar(ctx, "guard_stub", (side * 1.75, -L / 2, 0.075), (side * 1.75, -0.4, 0.075), 0.2, 0.15, TIMBER_ROT, bevel=0.01)
            continue
        W.bar(ctx, f"guard{side}", (side * 1.75, -L / 2, 0.075), (side * 1.75, L / 2, 0.075), 0.2, 0.15, TIMBER, bevel=0.01, cuts=3)
    for side in (-1, 1):
        x = side * GAUGE / 2
        _rail(ctx, f"rail{side}", -L / 2, L / 2, x, 0.012, mat=RUST if ctx.worn else RAIL)
        for i in range(n):
            y = -L / 2 + (i + 0.5) * L / n
            p = K.box(f"plate{side}{i}", (0.2, 0.16, 0.012), center=(x, y, 0.006))
            ctx.add(p, RUST, uv="box", uv_scale=6.0)
    _ = r


def w4_trestle_rail_section(ctx: K.Ctx) -> None:
    """3 m of track along Y: a ballast bed, seven rough ties and two light rails (worn: ties gone, a rail kinked)."""
    r = ctx.rnd("track")
    L = 3.0
    bed = K.prism("ballast", [(-1.25, 0.0), (1.25, 0.0), (0.95, 0.12), (-0.95, 0.12)], L, plane="XZ")
    K.place(bed, (0, 0, 0), (0, 0, 0))
    bed2 = K.box("ballast_top", (1.9, L, 0.02), center=(0, 0, 0.11), cuts=(3, 6, 0))
    K.noise_disp(bed2, 0.02, scale=4.0, seed=ctx.seed)
    ctx.add(bed, BALLAST, uv="box", uv_scale=1.5, patches=0.5, moss=0.3)
    ctx.add(bed2, BALLAST, uv="box", uv_scale=1.5, patches=0.5, moss=0.3)
    for i in range(7):
        if ctx.worn and i in (2, 5):
            continue
        y = -L / 2 + (i + 0.5) * L / 7 + r.uniform(-0.04, 0.04)
        t = K.box(f"tie{i}", (1.9, 0.18, 0.12), center=(r.uniform(-0.03, 0.03), y, 0.16), bevel=0.01, cuts=(3, 0, 0))
        K.place(t, (0, 0, 0), (0, 0, r.uniform(-2.5, 2.5)))
        ctx.add(t, TIMBER_ROT if ctx.worn else TIMBER, long_axis=0, patches=0.5, moss=0.25)
    for side in (-1, 1):
        kink = 0.06 if (ctx.worn and side > 0) else 0.0
        _rail(ctx, f"rail{side}", -L / 2, L / 2, side * GAUGE / 2, 0.22, mat=RUST if ctx.worn else RAIL, kink=kink)


def w4_trestle_crib(ctx: K.Ctx) -> None:
    """A rock-filled crib of squared timbers laid log-cabin fashion, 2 x 4 m, 2.95 m tall."""
    r = ctx.rnd("crib")
    h, t = 2.95, 0.245
    n = int(h / t)
    for k in range(n):
        z = k * t + t / 2
        rot = TIMBER_ROT if (ctx.worn and k % 3 == 0) else TIMBER
        if k % 2 == 0:
            for x in (-0.85, 0.85):
                W.bar(ctx, f"long{k}{x}", (x, -2.0, z), (x, 2.0, z), t, t, rot, bevel=0.01, moss=0.2)
        else:
            for y in (-1.85, 0.0, 1.85):
                W.bar(ctx, f"cross{k}{y}", (-1.0, y, z), (1.0, y, z), t, t, rot, bevel=0.01, moss=0.2)
    fill = K.box("fill", (1.5, 3.6, h - 0.05), center=(0, 0, (h - 0.05) / 2))
    ctx.add(fill, RUBBLE, uv="box", uv_scale=1.0)
    for k in range(10):
        s = K.chunk(f"rock{k}", r.uniform(0.25, 0.4), r, n=10, flat=0.6)
        K.place(s, (r.uniform(-0.6, 0.6), r.uniform(-1.6, 1.6), h - 0.08))
        ctx.add(s, ROCK, uv="box", uv_scale=2.0, patches=0.4, moss=0.4)
    if ctx.worn:
        for k in range(4):
            s = K.chunk(f"spill{k}", r.uniform(0.2, 0.35), r, n=9, flat=0.6)
            K.place(s, (r.choice((-1, 1)) * r.uniform(1.0, 1.3), r.uniform(-1.8, 1.8), 0.08))
            ctx.add(s, ROCK, uv="box", uv_scale=2.0, patches=0.4, moss=0.4)


# ============================================================================================
# The tunnel
# ============================================================================================

def w4_trestle_hill(ctx: K.Ctx) -> None:
    """The hill over the tunnel: a 10.6 x 17.6 m block of rock (a cut face round its plinth, the kit rooms of the
    tunnel inside it from 3.15 m up), rounding into a mossy brow, boulders on top. Its front face (-Y) stays flat
    on the tunnel's portal wall line; the portal prop stands in front of it."""
    r = ctx.rnd("hill")
    X, Yf, Yb, H = 5.35, -8.75, 8.85, 12.0
    o = K.box("hill", (2 * X, Yb - Yf, H), center=(0, (Yf + Yb) / 2, H / 2), cuts=(10, 16, 10))

    def shape(v):
        z = v.co.z
        if z <= 3.3:
            return
        k = (z - 3.3) / (H - 3.3)
        # Rounded brow: the sides draw in above the tunnel's crown, the back slopes away.
        inset = 1.6 * k * k
        v.co.x = max(-X + inset, min(X - inset, v.co.x))
        if v.co.y > Yf + 0.2:
            v.co.y = min(Yb - 2.2 * k * k, v.co.y)
        v.co.z = 3.3 + (z - 3.3) * (0.82 + 0.18 * math.cos(v.co.x / X * 1.4))
    for v in o.data.vertices:
        shape(v)
    o.data.update()
    K.noise_disp(o, 0.35, scale=0.6, seed=ctx.seed, mask=lambda c: 0.0 if c.y < Yf + 0.25 else 1.0)
    ctx.add(o, ROCK, uv="box", uv_scale=0.35, smooth=40, patches=0.5, moss=0.55)
    for k in range(9):
        b = K.chunk(f"boulder{k}", r.uniform(0.7, 1.5), r, n=14, flat=0.7)
        K.subdivide(b, 1, smooth=0.5)
        K.place(b, (r.uniform(-3.5, 3.5), r.uniform(-6.0, 7.0), r.uniform(9.3, 10.0)))
        ctx.add(b, "rock_moss", uv="box", uv_scale=1.0, smooth=50, patches=0.4, moss=0.6)
    for k in range(6):
        W.pole(ctx, f"root{k}", [(r.uniform(-4, 4), Yf - 0.02, r.uniform(10.2, 11.0)),
                                (r.uniform(-4, 4), Yf - 0.15, r.uniform(9.9, 10.3))], 0.05, "bark_dead",
               r_end=0.02, seed=ctx.seed + k, wobble=0.1)


def w4_trestle_tunnel_portal(ctx: K.Ctx) -> None:
    """A concrete tunnel portal built forward (-Y) from its back plane at the origin: a solid face under the bore
    (0-3.15 m, the collision box), piers either side of the bore (x -3.5..3.5, 3.15-8.95 m), an arched ring and a
    headwall to 10 m with a cast date panel, a Cordon stencil."""
    r = ctx.rnd("portal")
    T = 0.6
    yc = -T / 2

    def slab(name, x0, x1, z0, z1, t=T, y=yc):
        o = K.box(name, (x1 - x0, t, z1 - z0), center=((x0 + x1) / 2, y, (z0 + z1) / 2), bevel=0.02, cuts=(3, 0, 3))
        return ctx.add(o, CONCRETE, uv="box", uv_scale=0.8, patches=0.6, moss=0.3)

    slab("base", -4.8, 4.8, 0.0, 3.15)
    slab("pier_w", -4.8, -3.5, 3.15, 10.0)
    slab("pier_e", 3.5, 4.8, 3.15, 10.0)
    slab("head", -3.5, 3.5, 8.95, 10.0)
    # Spandrels: the arch springs at 7.0 m and peaks at the 8.95 m crown.
    for side in (-1, 1):
        pts = [(side * 3.5, 8.95), (side * 3.5, 7.0)]
        for i in range(1, 12):
            a = math.pi / 2 * i / 12
            pts.append((side * 3.5 * math.cos(a), 7.0 + 1.95 * math.sin(a)))
        pts.append((0.0, 8.95))
        if side > 0:
            pts.reverse()
        sp = K.prism(f"spandrel{side}", pts, T, plane="XZ", offset=yc)
        ctx.add(sp, CONCRETE, uv="box", uv_scale=0.8, patches=0.6, moss=0.3)
    # The arch ring, proud of the face.
    for i in range(14):
        a0, a1 = math.pi * i / 14, math.pi * (i + 1) / 14
        p0 = Vector((3.62 * math.cos(a0), -T - 0.06, 7.0 + 2.05 * math.sin(a0)))
        p1 = Vector((3.62 * math.cos(a1), -T - 0.06, 7.0 + 2.05 * math.sin(a1)))
        W.bar(ctx, f"ring{i}", p0, p1, 0.12, 0.3, CONCRETE, up=(0, -1, 0), patches=0.6)
    for side in (-1, 1):
        W.bar(ctx, f"ringleg{side}", (side * 3.62, -T - 0.06, 3.15), (side * 3.62, -T - 0.06, 7.0), 0.12, 0.3, CONCRETE,
              up=(0, -1, 0), patches=0.6)
    # Coping and the date panel.
    cop = K.box("coping", (9.9, T + 0.2, 0.25), center=(0, yc - 0.05, 10.12), bevel=0.02)
    ctx.add(cop, CONCRETE, uv="box", uv_scale=0.8, patches=0.6, moss=0.5)
    panel = K.box("date", (1.6, 0.06, 0.5), center=(0, -T - 0.03, 9.48), bevel=0.01)
    ctx.add(panel, "bridge_concrete", uv="box", uv_scale=1.0, patches=0.4)
    # The Cordon's stencil: a band of hazard paint across the base and a sprayed X.
    band = K.box("hazard", (3.0, 0.02, 0.4), center=(-1.2, -T - 0.011, 2.3))
    ctx.add(band, "paint_orange_wood" if not ctx.worn else "ws_paint_yellow", uv="box", uv_scale=2.0, patches=0.6)
    for s in (-1, 1):
        W.bar(ctx, f"x{s}", (1.4 - 0.5, -T - 0.012, 1.6 + s * 0.5), (1.4 + 0.5, -T - 0.012, 1.6 - s * 0.5), 0.12, 0.01,
              "paint_red_sign", up=(0, -1, 0), patches=0.6)
    if ctx.worn:
        for k in range(8):
            c = K.chunk(f"spall{k}", r.uniform(0.15, 0.35), r, n=9, flat=0.5)
            K.place(c, (r.uniform(-4.5, 4.5), -T - r.uniform(0.2, 0.9), 0.05))
            ctx.add(c, CONCRETE, uv="box", uv_scale=2.0, patches=0.5)


def w4_trestle_rubble_wall(ctx: K.Ctx) -> None:
    """The collapse filling a 7 m bore to its crown: a slope of rock (its foot at -Y, packed against the back at
    +Y), split timber sets and lagging, a twisted rail and the cab roof and stack of the buried engine."""
    r = ctx.rnd("rubble")
    core = K.prism("core", [(-1.3, 0.0), (1.3, 0.0), (1.3, 5.8), (0.2, 5.8), (-1.0, 1.2)], 7.0, plane="YZ")
    ctx.add(core, RUBBLE, uv="box", uv_scale=0.8, patches=0.5)
    for k in range(90):
        y = r.uniform(-1.3, 1.2)
        zmax = 1.2 + (y + 1.0) / 1.2 * 4.6 if y > -1.0 else 1.2 * (y + 1.3) / 0.3
        z = r.uniform(0.0, max(0.2, min(5.6, zmax)))
        s = K.chunk(f"rock{k}", r.uniform(0.3, 0.8), r, n=10, flat=r.uniform(0.5, 1.0))
        K.place(s, (r.uniform(-3.4, 3.4), y - 0.1, z), (r.uniform(0, 360), r.uniform(0, 360), r.uniform(0, 360)))
        ctx.add(s, ROCK if k % 3 else RUBBLE, uv="box", uv_scale=1.5, patches=0.5, moss=0.1)
    for k in range(6):
        a = Vector((r.uniform(-3.2, 3.2), r.uniform(-1.0, 0.6), r.uniform(0.3, 4.5)))
        b = a + Vector((r.uniform(-1.5, 1.5), r.uniform(-0.6, 0.6), r.uniform(-1.2, 1.2)))
        W.bar(ctx, f"timber{k}", a, b, 0.22, 0.22, TIMBER_ROT, bevel=0.01)
    W.pole(ctx, "rail_twist", [(-1.2, -1.3, 0.1), (-0.6, -1.0, 0.7), (0.3, -0.9, 1.1), (0.9, -0.6, 1.9)], 0.04, RUST,
           r_end=0.04, segs=5)
    # The engine's cab roof and stack, half buried at the foot of the slide.
    cab = K.box("cab_roof", (2.4, 1.6, 0.12), center=(1.2, -0.5, 2.2), bevel=0.05, cuts=(4, 2, 0))
    K.place(cab, (0, 0, 0), (12, -8, 6))
    K.bend(cab, 0, 0.15)
    ctx.add(cab, "paint_black", uv="box", uv_scale=1.0, patches=0.7)
    st = K.cyl("stack", 0.22, 1.1, segs=12, center=(-1.8, -0.7, 1.4), r_top=0.3)
    K.place(st, (0, 0, 0), (0, 14, 0))
    ctx.add(st, "paint_black", uv="cyl", smooth=40, patches=0.7)


def w4_trestle_boxcar(ctx: K.Ctx) -> None:
    """A wooden boxcar 7.2 m long (along Y) on two trucks, its floor at 1.15 m (the collision box), oxide-red
    board sides and ends, the side door on +X rolled open, a roof with a running board, grab irons and a brake
    wheel. The inside of the walls is bare boards."""
    r = ctx.rnd("boxcar")
    L, Wd, F, Ht = 7.2, 2.8, 1.15, 3.65
    for ty in (-2.6, 2.6):
        fr = K.box(f"truck{ty}", (1.9, 1.6, 0.3), center=(0, ty, 0.55), bevel=0.02)
        ctx.add(fr, IRON, uv="box", uv_scale=2.0, patches=0.5)
        for wy in (ty - 0.6, ty + 0.6):
            for sx in (-1, 1):
                wh = K.cyl(f"wheel{ty}{wy}{sx}", 0.36, 0.1, segs=16, center=(sx * GAUGE / 2, wy, 0.36), axis="X")
                ctx.add(wh, IRON, uv="cyl", uv_axis=0, smooth=40)
            ax = K.cyl(f"axle{ty}{wy}", 0.06, GAUGE + 0.2, segs=8, center=(0, wy, 0.36), axis="X")
            ctx.add(ax, IRON, uv="cyl", uv_axis=0)
    frame = K.box("underframe", (Wd - 0.1, L, 0.3), center=(0, 0, 0.85), cuts=(2, 6, 0))
    ctx.add(frame, IRON, uv="box", uv_scale=1.5, patches=0.5)
    floor = K.box("floor", (Wd, L, 0.15), center=(0, 0, F - 0.075), cuts=(12, 0, 0))
    ctx.add(floor, PLANK, uv="box", uv_scale=1.0, long_axis=1, patches=0.5)
    paint = OXIDE
    wall_t = 0.07
    door_y = (-0.85, 0.85)
    # Sides: the -X side whole, the +X side cut for the door.
    side_spans = {-1: [(-L / 2, L / 2)], 1: [(-L / 2, door_y[0]), (door_y[1], L / 2)]}
    for sx, spans in side_spans.items():
        x = sx * (Wd / 2 - wall_t / 2)
        for k, (y0, y1) in enumerate(spans):
            o = K.box(f"side{sx}{k}", (wall_t, y1 - y0, Ht - F), center=(x, (y0 + y1) / 2, (F + Ht) / 2),
                      cuts=(0, max(2, int((y1 - y0) / 0.14)), 0))
            if ctx.worn:
                K.noise_disp(o, 0.012, scale=3.0, seed=ctx.seed + k + sx)
            ctx.add(o, paint, uv="box", uv_scale=1.0, long_axis=2, patches=0.6)
    if True:
        hdr = K.box("door_header", (wall_t, door_y[1] - door_y[0], Ht - 3.2), center=(Wd / 2 - wall_t / 2, 0, (3.2 + Ht) / 2))
        ctx.add(hdr, paint, uv="box", uv_scale=1.0, patches=0.6)
    for sy in (-1, 1):
        o = K.box(f"end{sy}", (Wd, wall_t, Ht - F), center=(0, sy * (L / 2 - wall_t / 2), (F + Ht) / 2), cuts=(16, 0, 0))
        ctx.add(o, paint, uv="box", uv_scale=1.0, long_axis=2, patches=0.6)
    roof = K.box("roof", (Wd + 0.12, L + 0.1, 0.08), center=(0, 0, Ht + 0.04), cuts=(4, 8, 0))
    for v in roof.data.vertices:
        v.co.z += 0.1 * (1.0 - (v.co.x / (Wd / 2 + 0.06)) ** 2)
    roof.data.update()
    ctx.add(roof, "farm_corrugated_rust" if ctx.worn else IRON, uv="box", uv_scale=1.0, patches=0.6)
    W.bar(ctx, "running_board", (0, -L / 2, Ht + 0.2), (0, L / 2, Ht + 0.2), 0.5, 0.04, PLANK, bevel=0.005)
    # The door, rolled back along its track toward +Y.
    door = K.box("door", (0.06, 1.75, 2.1), center=(Wd / 2 + 0.06, 1.85, F + 1.07), cuts=(0, 10, 0))
    ctx.add(door, paint, uv="box", uv_scale=1.0, long_axis=2, patches=0.6)
    W.bar(ctx, "door_track", (Wd / 2 + 0.05, -1.0, 3.28), (Wd / 2 + 0.05, 3.0, 3.28), 0.05, 0.06, IRON)
    W.bar(ctx, "door_sill", (Wd / 2 + 0.03, door_y[0], F - 0.04), (Wd / 2 + 0.03, door_y[1], F - 0.04), 0.06, 0.08, IRON)
    for sy in (-1, 1):
        for k in range(3):
            W.rod(ctx, f"grab{sy}{k}", (Wd / 2 - 0.3, sy * (L / 2 + 0.05), 1.4 + k * 0.35),
                  (Wd / 2 - 0.75, sy * (L / 2 + 0.05), 1.4 + k * 0.35), 0.015, IRON, segs=6)
    wheel = W.ring_obj("brake_wheel", 0.24, 0.27, 0.03, segs=20)
    K.place(wheel, (0, 0, 0), (90, 0, 0))
    K.place(wheel, (-0.6, -L / 2 - 0.15, 3.1))
    ctx.add(wheel, IRON, uv="box", uv_scale=4.0, smooth=40)
    W.rod(ctx, "brake_staff", (-0.6, -L / 2 - 0.15, 1.0), (-0.6, -L / 2 - 0.15, 3.1), 0.02, IRON, segs=6)
    if ctx.worn:
        for k in range(3):
            c = K.chunk(f"board{k}", 0.3, r, n=6, flat=0.2, elong=4.0)
            K.place(c, (r.uniform(-1.0, 1.0), r.uniform(-L / 2, L / 2), F + 0.03))
            ctx.add(c, PLANK, uv="box", uv_scale=2.0, patches=0.5)


def w4_trestle_lumber_stack(ctx: K.Ctx) -> None:
    """A bundle of rough-sawn boards 2.4 m long (along Y) on two bearers, in four lifts with stickers between,
    banded with strap iron, the end grain stencilled."""
    r = ctx.rnd("lumber")
    for y in (-0.8, 0.8):
        W.bar(ctx, f"bearer{y}", (-1.1, y, 0.05), (1.1, y, 0.05), 0.1, 0.1, PLANK)
    z = 0.1
    for k in range(4):
        h = 0.34
        slide = r.uniform(0.15, 0.35) if (ctx.worn and k == 3) else 0.0
        o = K.box(f"lift{k}", (2.2, 2.35, h), center=(slide * 0.3, slide, z + h / 2), cuts=(14, 0, 4))
        ctx.add(o, "wood_fresh", uv="box", uv_scale=1.0, long_axis=1, patches=0.4)
        z += h
        if k < 3:
            for y in (-0.9, 0.0, 0.9):
                W.bar(ctx, f"sticker{k}{y}", (-1.1, y, z + 0.02), (1.1, y, z + 0.02), 0.04, 0.04, PLANK)
            z += 0.04
    for y in (-0.7, 0.7):
        if ctx.worn and y > 0:
            continue
        band = K.box(f"band{y}", (2.24, 0.04, z - 0.1 + 0.02), center=(0, y, (z + 0.1) / 2))
        K.delete_faces(band, lambda c, n: abs(n.y) > 0.9)
        ctx.add(band, RUST, uv="box", uv_scale=4.0)
        top = K.box(f"bandtop{y}", (2.24, 0.04, 0.01), center=(0, y, z + 0.005))
        ctx.add(top, RUST, uv="box", uv_scale=4.0)


def w4_trestle_flatcar_derailed(ctx: K.Ctx) -> None:
    """A logging flatcar 5.4 m long (along Y) off the rails: its front truck dropped (the car tipped down at -Y
    and listing), three logs chained on the bunks and a fourth rolled off the -X side."""
    r = ctx.rnd("flat")
    L = 5.4
    parts_start = len(ctx.parts)
    for ty in (-1.9, 1.9):
        fr = K.box(f"truck{ty}", (1.8, 1.4, 0.28), center=(0, ty, 0.5), bevel=0.02)
        ctx.add(fr, IRON, uv="box", uv_scale=2.0, patches=0.5)
        for wy in (ty - 0.5, ty + 0.5):
            for sx in (-1, 1):
                wh = K.cyl(f"wheel{ty}{wy}{sx}", 0.33, 0.1, segs=16, center=(sx * GAUGE / 2, wy, 0.33), axis="X")
                ctx.add(wh, IRON, uv="cyl", uv_axis=0, smooth=40)
    for x in (-0.9, 0.0, 0.9):
        W.bar(ctx, f"sill{x}", (x, -L / 2, 0.82), (x, L / 2, 0.82), 0.2, 0.3, TIMBER, bevel=0.01, cuts=4)
    deck = K.box("deck", (2.5, L, 0.08), center=(0, 0, 1.01), cuts=(14, 0, 0))
    if ctx.worn:
        K.noise_disp(deck, 0.02, scale=2.0, seed=ctx.seed)
    ctx.add(deck, PLANK, uv="box", uv_scale=1.0, long_axis=1, patches=0.6)
    for k, y in enumerate((-1.8, 0.0, 1.8)):
        W.bar(ctx, f"bunk{k}", (-1.25, y, 1.15), (1.25, y, 1.15), 0.25, 0.2, TIMBER, bevel=0.01)
        for sx in (-1, 1):
            W.bar(ctx, f"stake{k}{sx}", (sx * 1.15, y, 1.1), (sx * 1.15, y, 1.85), 0.1, 0.1, TIMBER)
    logs = [(-0.55, 1.6), (0.55, 1.6), (0.0, 2.15)]
    for k, (x, z) in enumerate(logs):
        O.add_log_between(ctx, f"log{k}", (x, -L / 2 + 0.1, z), (x + r.uniform(-0.05, 0.05), L / 2 - 0.1, z), 0.34,
                          ctx.seed + k, mat_bark="wild_log_bark", sides=12, rings=5)
    for k, y in enumerate((-1.0, 1.0)):
        if ctx.worn and k == 1:
            continue
        ch = W.chain_obj(f"chain{k}", [(-1.15, y, 1.2), (-0.9, y, 2.0), (0.0, y, 2.52), (0.9, y, 2.0), (1.15, y, 1.2)])
        ctx.add(ch, "trap_chain", uv="box", uv_scale=8.0, smooth=40, patches=0.4)
    # Tip the car: the front (-Y) truck dropped into the ballast, a list to +X.
    for o in ctx.parts[parts_start:]:
        K.place(o, (0, 0, 0), (-3.5, 4.0, 0))
        K.place(o, (0, 0, -0.12))
    O.add_log_between(ctx, "log_off", (-1.6, -L / 2 + 0.9, 0.9), (-1.75, L / 2 - 0.6, 0.35), 0.32, ctx.seed + 9,
                      mat_bark="wild_log_bark", sides=12, rings=5)


def w4_trestle_handcar(ctx: K.Ctx) -> None:
    """A pump handcar 2.4 m long (along Y) standing on rails 0.27 m up: a plank platform on four cast wheels, the
    A-frame and walking beam with a handle bar each end, a brake lever and a tool box (destroyed: off one axle)."""
    r = ctx.rnd("handcar")
    base = 0.27
    for wy in (-0.7, 0.7):
        for sx in (-1, 1):
            wh = K.cyl(f"wheel{wy}{sx}", 0.25, 0.08, segs=14, center=(sx * GAUGE / 2, wy, base + 0.25), axis="X")
            ctx.add(wh, IRON, uv="cyl", uv_axis=0, smooth=40)
        ax = K.cyl(f"axle{wy}", 0.04, GAUGE + 0.15, segs=8, center=(0, wy, base + 0.25), axis="X")
        ctx.add(ax, IRON, uv="cyl", uv_axis=0)
    pz = base + 0.5
    for x in (-0.6, 0.6):
        W.bar(ctx, f"frame{x}", (x, -1.2, pz), (x, 1.2, pz), 0.12, 0.15, TIMBER, bevel=0.01)
    plat = K.box("platform", (1.7, 2.4, 0.05), center=(0, 0, pz + 0.1), cuts=(10, 0, 0))
    ctx.add(plat, PLANK, uv="box", uv_scale=1.0, long_axis=1, patches=0.6)
    for sy in (-1, 1):
        W.bar(ctx, f"aframe{sy}", (0, sy * 0.45, pz + 0.12), (0, 0, pz + 0.95), 0.08, 0.08, TIMBER)
    beam_tilt = 0.12 if not ctx.destroyed else 0.3
    a = Vector((0, -1.0, pz + 0.95 - beam_tilt))
    b = Vector((0, 1.0, pz + 0.95 + beam_tilt))
    W.bar(ctx, "beam", a, b, 0.07, 0.1, "paint_red" if ctx.clean else IRON, patches=0.6)
    for k, p in enumerate((a, b)):
        if ctx.worn and k == 1:
            continue
        W.rod(ctx, f"handle{k}", (p.x - 0.55, p.y, p.z), (p.x + 0.55, p.y, p.z), 0.022, PLANK, segs=8)
    W.rod(ctx, "brake", (0.75, 0.9, pz + 0.12), (0.75, 1.05, pz + 0.85), 0.018, IRON, segs=6)
    box = K.box("toolbox", (0.7, 0.35, 0.3), center=(-0.35, -0.95, pz + 0.27), bevel=0.01)
    ctx.add(box, "paint_red" if ctx.clean else PLANK, uv="box", uv_scale=1.5, patches=0.6)
    if ctx.destroyed:
        for o in ctx.parts:
            K.place(o, (0, 0, 0), (0, 7, 0))
            K.place(o, (0, 0, -0.08))
    _ = r


def w4_trestle_key_board(ctx: K.Ctx) -> None:
    """The foreman's key board (origin on the wall plane, bottom centre, front -Y): a painted board, two rows of
    cup hooks with brass-tagged keys, two hooks empty, a stencilled list down the right edge."""
    r = ctx.rnd("keys")
    b = K.box("board", (0.6, 0.025, 0.5), center=(0, -0.0125, 0.25), bevel=0.004)
    ctx.add(b, "wood_painted_green", uv="box", uv_scale=1.5, patches=0.5)
    edge = K.box("list", (0.12, 0.004, 0.42), center=(0.22, -0.027, 0.25))
    ctx.add(edge, "paper_pages", uv="box", uv_scale=3.0, patches=0.5)
    for row, z in enumerate((0.36, 0.16)):
        for k in range(5):
            x = -0.24 + k * 0.095
            W.rod(ctx, f"hook{row}{k}", (x, -0.025, z), (x, -0.05, z), 0.004, "metal_galvanized", segs=5)
            if (row, k) in ((0, 2), (1, 4)) or (ctx.worn and r.random() < 0.3):
                continue
            key = K.box(f"key{row}{k}", (0.018, 0.004, 0.06), center=(x, -0.05, z - 0.04))
            ctx.add(key, "item_brass", uv="box", uv_scale=10.0)
            tag = K.cyl(f"tag{row}{k}", 0.017, 0.003, segs=10, center=(x, -0.052, z - 0.09), axis="Y")
            ctx.add(tag, "item_brass", uv="box", uv_scale=10.0)


def w4_trestle_spike_keg(ctx: K.Ctx) -> None:
    """A wooden nail keg of railway spikes, a claw bar leaning in it."""
    r = ctx.rnd("keg")
    keg = K.cyl("keg", 0.22, 0.6, segs=16, center=(0, 0, 0.3), cuts=4)
    for v in keg.data.vertices:
        k = 1.0 + 0.08 * (1.0 - ((v.co.z - 0.3) / 0.3) ** 2)
        v.co.x *= k
        v.co.y *= k
    keg.data.update()
    ctx.add(keg, PLANK, uv="cyl", smooth=40, patches=0.5)
    for z in (0.08, 0.52):
        hoop = W.ring_obj(f"hoop{z}", 0.225, 0.235, 0.03, segs=20)
        K.place(hoop, (0, 0, z))
        ctx.add(hoop, RUST, uv="box", uv_scale=6.0, smooth=40)
    for k in range(14):
        a = Vector((r.uniform(-0.15, 0.15), r.uniform(-0.15, 0.15), 0.58))
        b = a + Vector((r.uniform(-0.12, 0.12), r.uniform(-0.12, 0.12), r.uniform(-0.03, 0.05)))
        W.bar(ctx, f"spike{k}", a, b, 0.016, 0.016, RUST)
    W.rod(ctx, "claw_bar", (0.08, -0.05, 0.1), (0.3, -0.2, 0.75), 0.016, RUST, segs=6)


def w4_trestle_tie_pile(ctx: K.Ctx) -> None:
    """Old ties crib-stacked: two layers of five along X, a cross layer, a last pair on top; weeds through them."""
    r = ctx.rnd("ties")
    z = 0.075
    for layer in range(4):
        if layer % 2 == 0:
            for k in range(5):
                y = -0.52 + k * 0.26
                W.bar(ctx, f"tie{layer}{k}", (-1.2, y, z), (1.2 + r.uniform(-0.1, 0.1), y, z), 0.2, 0.15,
                      TIMBER_ROT if ctx.worn else TIMBER, bevel=0.01)
        else:
            for x in (-0.9, 0.9):
                W.bar(ctx, f"cross{layer}{x}", (x, -0.62, z), (x, 0.62, z), 0.2, 0.15, TIMBER, bevel=0.01)
        z += 0.17
    for k in range(6):
        g = K.blob(f"weed{k}", 0.18, subdiv=1, scale=(1.0, 1.0, 1.4), center=(r.uniform(-1.3, 1.3), r.uniform(-0.65, 0.65), 0.15),
                   rough=0.4, seed=ctx.seed + k)
        ctx.add(g, "rock_moss", uv="box", uv_scale=2.0, smooth=50, moss=0.9)


BUILDERS = {
    "w4_trestle_bent": w4_trestle_bent,
    "w4_trestle_deck_section": w4_trestle_deck_section,
    "w4_trestle_rail_section": w4_trestle_rail_section,
    "w4_trestle_crib": w4_trestle_crib,
    "w4_trestle_hill": w4_trestle_hill,
    "w4_trestle_tunnel_portal": w4_trestle_tunnel_portal,
    "w4_trestle_rubble_wall": w4_trestle_rubble_wall,
    "w4_trestle_boxcar": w4_trestle_boxcar,
    "w4_trestle_lumber_stack": w4_trestle_lumber_stack,
    "w4_trestle_flatcar_derailed": w4_trestle_flatcar_derailed,
    "w4_trestle_handcar": w4_trestle_handcar,
    "w4_trestle_key_board": w4_trestle_key_board,
    "w4_trestle_spike_keg": w4_trestle_spike_keg,
    "w4_trestle_tie_pile": w4_trestle_tie_pile,
}


def build(params: dict, outputs: list[str]) -> None:
    K.run(params, outputs, BUILDERS)
