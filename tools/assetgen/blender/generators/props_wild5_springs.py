"""Wilderness set pieces, round 5: props of Ember Creek Hot Springs (w5_hot_springs_bathhouse), an old timber
hot-springs bathhouse resort up a remote valley that the Cordon made a holding site.

The bathhouse: the plunge pool (a white-tiled basin raised knee-high in a cedar-capped surround, steps down at one
end, a brass rail), two-tier cedar steam room benches, slatted changing benches under a peg board of robes, a
painted towel cubby, the cabin key board behind the desk, the owner's oval cedar soaking tub. The Bloom: a bank of
felt and shelf caps up a steam-soaked wall and a low mat of it over wet tiles (both glow: the defs' lights). The
cellar: the riveted firetube boiler on its brick setting, the cedar stave cistern the spring is piped into and the
lagged mains along the wall. Outside: the boardwalk on its sleepers, the open-air rock pool and the steam that hangs
over hot water (veils on the springs' steam material).

Conventions (docs/ASSET_PIPELINE.md): metres, Z up, front -Y, origin bottom centre; floor props have their depth
centred on the origin (PoiBuilder's collision box is the def's size centred there). Wall props (the Bloom bank, the
key board, the mains) hang with their origin on the wall plane, bottom centre, reaching out toward -Y. New
materials: w5_springs_water, w5_springs_water_scum and w5_springs_steam (game/data/materials/props_wild5_springs.json);
the rest are shared. 'clean' is the springs the week the Cordon closed the valley, 'worn' a season later.
"""
from __future__ import annotations

import math

from mathutils import Vector

from lib import materials as MAT
from lib import props_ext_kit as K
from lib import props_ext_parts as P
from lib import props_wild_parts as W

CEDAR = "wild_cedar"
CEDAR_OLD = "wild_lumber_weathered"
TILE = "ceramic_white"
WATER = "w5_springs_water"
SCUM = "w5_springs_water_scum"
STEAM = "w5_springs_steam"
BRASS = "road_brass"
IRON = "wild_cast_iron"
RUST = "wild_cast_iron_rust"
STEEL = "road_steel"
DARK = "road_steel_dark"
BRICK = "brick"
ROCK = "rock_moss"
STONE = "stone_river"
TOWEL = "road_towel_white"
TOWEL_B = "furn_towel"
PAINT = "wood_painted_white"
LAG = "canvas_grey"
FELT = "bloom_felt"
CAPS = "bloom_caps"
COPPER = "furn_brass"

MAT.PREVIEW_COLORS.update({WATER: (0.3, 0.52, 0.48), SCUM: (0.37, 0.39, 0.31), STEAM: (0.9, 0.92, 0.92)})


def _bx(ctx, name, size, center, mat, *, bevel=0.006, uv_scale=2.0, **kw):
    return ctx.add(K.box(name, size, center=center, bevel=bevel), mat, uv="box", uv_scale=uv_scale, **kw)


def _cy(ctx, name, r, h, center, mat, *, axis="Z", segs=12, r_top=None, uv_scale=2.0, **kw):
    o = K.cyl(name, r, h, segs=segs, center=center, axis=axis, r_top=r_top)
    return ctx.add(o, mat, uv="box", uv_scale=uv_scale, smooth=40, **kw)


def _caps(ctx, name, cx, cy, z, n, r, *, spread=0.12, size=1.0):
    """A troop of small Bloom caps (stem and domed cap) round (cx, cy) at height z."""
    for k in range(n):
        a = r.uniform(0, math.tau)
        d = r.uniform(0.0, spread)
        x, y = cx + math.cos(a) * d, cy + math.sin(a) * d
        h = r.uniform(0.025, 0.07) * size
        cr = r.uniform(0.012, 0.03) * size
        lean = (r.uniform(-14, 14), r.uniform(-14, 14), 0)
        stem = K.cyl(f"{name}_stem{k}", cr * 0.28, h, segs=6, center=(0, 0, h / 2))
        cap = K.lathe(f"{name}_cap{k}", [(0.0, h + cr * 0.55), (cr * 0.55, h + cr * 0.45), (cr, h + cr * 0.05), (cr * 0.9, h - cr * 0.1),
                                          (0.0, h - 0.002)], segs=8)
        for o in (stem, cap):
            K.place(o, (0, 0, 0), lean)
            K.place(o, (x, y, z))
        ctx.add(stem, FELT, uv="box", uv_scale=4.0, smooth=40, ao=False)
        ctx.add(cap, CAPS, uv="box", uv_scale=4.0, smooth=40, ao=False)


def _felt(ctx, name, cx, cy, z, n, r, *, spread=0.3, spread_y=None, spread_z=0.0, size=0.07, flat=0.35, scale=(1.4, 1.2)):
    """Cushions of white Bloom felt round (cx, cy, z)."""
    sy = spread if spread_y is None else spread_y
    for k in range(n):
        x = cx + r.uniform(-spread, spread)
        y = cy + r.uniform(-sy, sy)
        zz = z + r.uniform(-spread_z, spread_z)
        b = K.blob(f"{name}{k}", size * r.uniform(0.6, 1.3), subdiv=1, scale=(scale[0], scale[1], flat), center=(x, y, zz), rough=0.35, seed=k + 3)
        ctx.add(b, FELT, uv="box", uv_scale=3.0, smooth=50, ao=False)


def _shelf_cap(ctx, name, x, z, rad, r):
    """A bracket fungus standing out of a wall (the wall at y = 0, the cap reaching toward -Y)."""
    cap = K.lathe(name, [(0.0, 0.0), (rad, -0.004), (rad * 0.92, 0.025), (rad * 0.5, 0.04), (0.0, 0.045)], segs=10)
    K.place(cap, scale=(1.0, 0.75, 1.0))
    K.place(cap, (x, -rad * 0.6, z), (r.uniform(-6, 6), 0, r.uniform(-15, 15)))
    ctx.add(cap, CAPS, uv="box", uv_scale=4.0, smooth=40, ao=False)


# ============================================================================================
# Water
# ============================================================================================

def w5_springs_plunge_pool(ctx: K.Ctx) -> None:
    """The plunge pool: a basin of small white tiles raised knee-high in a cedar-capped surround (4.2 x 6.2 m), steps
    down inside the near (-Y) end with a brass hand rail, an overflow grate and the inlet pipe at the far end, the water
    standing 0.15 under the coping. Worn: tepid and grey with scum, towels floating, tiles crazed and gone in patches."""
    Wd, L, H = 4.2, 6.2, 0.6
    t = 0.24
    r = ctx.rnd("pool")
    dr = ctx.drnd("pool")
    # Tiled walls (outside and inside faces both tile), the cedar coping on top.
    for sx in (-1, 1):
        _bx(ctx, f"wall_x{sx}", (t, L, H - 0.06), (sx * (Wd / 2 - t / 2), 0, (H - 0.06) / 2), TILE, uv_scale=4.0, patches=0.3)
        _bx(ctx, f"cap_x{sx}", (t + 0.06, L + 0.06, 0.06), (sx * (Wd / 2 - t / 2), 0, H - 0.03), CEDAR, bevel=0.01, uv_scale=1.5)
    for sy in (-1, 1):
        _bx(ctx, f"wall_y{sy}", (Wd - 2 * t, t, H - 0.06), (0, sy * (L / 2 - t / 2), (H - 0.06) / 2), TILE, uv_scale=4.0, patches=0.3)
        _bx(ctx, f"cap_y{sy}", (Wd - 2 * t, t + 0.06, 0.06), (0, sy * (L / 2 - t / 2), H - 0.03), CEDAR, bevel=0.01, uv_scale=1.5)
    # Basin floor and a tiled band (darker grout line) under the water line.
    _bx(ctx, "basin", (Wd - 2 * t, L - 2 * t, 0.02), (0, 0, 0.01), TILE, uv_scale=5.0, patches=0.5, low=0.4)
    for sx in (-1, 1):
        _bx(ctx, f"band_x{sx}", (0.01, L - 2 * t, 0.06), (sx * (Wd / 2 - t - 0.005), 0, 0.42), "road_paint_blue", bevel=0.0, ao=False)
    # Steps down inside the near end.
    for k in range(3):
        d = 0.32
        y0 = -L / 2 + t + k * d
        _bx(ctx, f"step{k}", (1.2, d, 0.42 - k * 0.14), (-0.8, y0 + d / 2, (0.42 - k * 0.14) / 2), TILE, uv_scale=4.0, patches=0.4)
    # Brass hand rail from the coping down into the water.
    rail = [(-1.5, -L / 2 + 0.12, H + 0.32), (-1.5, -L / 2 + 0.35, H + 0.36), (-1.5, -L / 2 + 0.7, 0.55), (-1.5, -L / 2 + 0.9, 0.08)]
    ctx.add(K.tube("rail", rail, 0.022, segs=8), BRASS if ctx.clean else "road_rust", uv_scale=3.0, smooth=50)
    W.rod(ctx, "rail_post", (-1.5, -L / 2 + 0.12, H), (-1.5, -L / 2 + 0.12, H + 0.32), 0.022, BRASS if ctx.clean else "road_rust", segs=8)
    # Overflow grate and the inlet pipe at the far end.
    _bx(ctx, "grate", (0.5, 0.01, 0.08), (0.9, L / 2 - t - 0.006, 0.47), DARK, bevel=0.0, ao=False)
    W.rod(ctx, "inlet", (-0.6, L / 2 - t + 0.02, 0.5), (-0.6, L / 2 - t - 0.25, 0.5), 0.05, BRASS if ctx.clean else RUST, segs=10)
    W.rod(ctx, "inlet_down", (-0.6, L / 2 - t - 0.25, 0.5), (-0.6, L / 2 - t - 0.25, 0.4), 0.05, BRASS if ctx.clean else RUST, segs=10)
    # The water.
    wz = 0.45 if ctx.clean else 0.4
    _bx(ctx, "water", (Wd - 2 * t - 0.01, L - 2 * t - 0.01, 0.01), (0, 0, wz), WATER if ctx.clean else SCUM, bevel=0.0, ao=False)
    if ctx.worn:
        # Floating towels and a scum line.
        for k in range(3):
            tw = K.box(f"float_towel{k}", (dr.uniform(0.5, 0.8), dr.uniform(0.35, 0.5), 0.02), cuts=(4, 3, 0))
            K.noise_disp(tw, 0.025, scale=4.0, seed=k + 11)
            K.place(tw, (dr.uniform(-1.0, 1.2), dr.uniform(-1.6, 2.4), wz + 0.012), (0, 0, dr.uniform(0, 180)))
            ctx.add(tw, TOWEL_B, uv_scale=2.0, smooth=40, patches=0.7, ao=False)
        for sx in (-1, 1):
            _bx(ctx, f"scum_line{sx}", (0.012, L - 2 * t, 0.05), (sx * (Wd / 2 - t - 0.006), 0, wz + 0.03), "road_oil_dark", bevel=0.0, ao=False)
        # Tiles gone in patches on the outside faces (dark grout showing).
        for k in range(5):
            sx = dr.choice((-1, 1))
            _bx(ctx, f"chip{k}", (0.012, dr.uniform(0.15, 0.4), dr.uniform(0.1, 0.25)), (sx * (Wd / 2 + 0.004), dr.uniform(-2.6, 2.6), dr.uniform(0.12, 0.4)),
                "road_concrete", bevel=0.0)
    else:
        # A folded towel left on the coping.
        _bx(ctx, "towel", (0.35, 0.25, 0.06), (Wd / 2 - 0.12, -1.8, H + 0.03), TOWEL, bevel=0.02, uv_scale=2.0)
    _ = r


def w5_springs_rock_pool(ctx: K.Ctx) -> None:
    """The open-air rock pool: an oval of mossy boulders on a mortared stone wall round the spring (6.0 x 4.6 m), the
    water a hand under the rocks' tops, a timber step at the near (-Y) side and a duckboard on the far rocks. Worn:
    silted and green, leaves on the water, the step rotted."""
    r = ctx.rnd("rocks")
    dr = ctx.drnd("rocks")
    ax, ay = 2.55, 1.85
    # Mortared wall under the boulders: a squat ring.
    ring = K.lathe("wall", [(0.0, 0.0), (1.0, 0.0), (1.0, 0.35), (0.86, 0.38), (0.86, 0.02), (0.0, 0.02)], segs=28)
    K.place(ring, scale=(ax + 0.1, ay + 0.1, 1.0))
    ctx.add(ring, STONE, uv="box", uv_scale=1.2, smooth=40, patches=0.5, moss=0.4)
    n = 22
    for k in range(n):
        a = math.tau * k / n + r.uniform(-0.06, 0.06)
        rad = r.uniform(0.36, 0.5)
        x = math.cos(a) * (ax + 0.05)
        y = math.sin(a) * (ay + 0.05)
        # Keep the near step's gap (front, -Y) low.
        if abs(a - math.radians(270)) < 0.2:
            rad *= 0.7
        b = K.blob(f"boulder{k}", rad, subdiv=2, scale=(1.15, 0.95, 0.8), rough=0.3, seed=ctx.seed + k)
        K.place(b, (x, y, rad * 0.55), (0, 0, math.degrees(a)))
        K.map_verts(b, lambda co: Vector((max(-3.0, min(3.0, co.x)), max(-2.3, min(2.3, co.y)), min(0.7, co.z))))
        ctx.add(b, ROCK if k % 3 else STONE, uv="box", uv_scale=1.0, smooth=40, moss=0.5, patches=0.4)
    # Water.
    water = K.cyl("water", 1.0, 0.01, segs=28, center=(0, 0, 0.5))
    K.place(water, scale=(ax - 0.12, ay - 0.12, 1.0))
    ctx.add(water, WATER if ctx.clean else SCUM, uv="box", uv_scale=1.0, smooth=40, ao=False)
    # The timber step at the near side and a duckboard on the far rocks.
    _bx(ctx, "step", (0.9, 0.35, 0.08), (0.0, -ay - 0.05, 0.3), CEDAR if ctx.clean else CEDAR_OLD, bevel=0.01, uv_scale=1.5,
        patches=0.6, moss=0.3)
    for sx in (-1, 1):
        _bx(ctx, f"step_leg{sx}", (0.08, 0.08, 0.26), (sx * 0.38, -ay - 0.05, 0.13), CEDAR_OLD, bevel=0.005)
    for k in range(6):
        _bx(ctx, f"duck{k}", (0.12, 0.8, 0.035), (-0.5 + k * 0.18, ay + 0.05, 0.66), CEDAR_OLD, bevel=0.005, uv_scale=1.5, moss=0.3)
    if ctx.worn:
        for k in range(14):
            lf = K.box(f"leaf{k}", (0.06, 0.04, 0.003))
            K.place(lf, (dr.uniform(-1.8, 1.8), dr.uniform(-1.2, 1.2), 0.507), (0, 0, dr.uniform(0, 180)))
            ctx.add(lf, "out_earth", uv_scale=4.0, ao=False)
    else:
        _bx(ctx, "towel", (0.4, 0.3, 0.05), (1.8, ay - 0.3, 0.68), TOWEL, bevel=0.02, uv_scale=2.0)


def w5_springs_steam(ctx: K.Ctx) -> None:
    """Steam over hot water: soft flattened veils rising and drifting in a loose column (3.0 x 3.0 x 2.4 m), thinning
    with height. Worn: thinner, fewer veils (the water cooling)."""
    r = ctx.rnd("steam")
    n = 9 if ctx.clean else 5
    for k in range(n):
        z = 0.15 + k * (2.0 / n) + r.uniform(-0.05, 0.05)
        rad = 0.55 + 0.35 * (k / n) + r.uniform(-0.08, 0.08)
        drift = 0.25 * (k / n)
        b = K.blob(f"veil{k}", rad, subdiv=2, scale=(r.uniform(1.1, 1.6), r.uniform(0.8, 1.2), r.uniform(0.45, 0.7)), rough=0.5,
                   seed=ctx.seed + k * 7, noise_scale=1.5)
        K.place(b, (drift + r.uniform(-0.35, 0.35), r.uniform(-0.35, 0.35), z), (r.uniform(-12, 12), r.uniform(-12, 12), r.uniform(0, 180)))
        K.map_verts(b, lambda co: Vector((max(-1.5, min(1.5, co.x)), max(-1.5, min(1.5, co.y)), max(0.0, min(2.4, co.z)))))
        ctx.add(b, STEAM, uv="box", uv_scale=1.0, smooth=60, ao=False, wear=0.0, edge=0.0, patches=0.0)


# ============================================================================================
# The bathhouse
# ============================================================================================

def w5_springs_steam_bench(ctx: K.Ctx) -> None:
    """Two tiers of slatted cedar benches (2.4 m long) built against the steam room wall: the lower tier at seat height
    in front, the upper one 0.9 up behind it, closed risers of tongue-and-groove, a heel board. Worn: grey and
    sweat-blackened, white Bloom felt furring the slats and a troop of caps in the corner."""
    Wd = 2.4
    wood = CEDAR if ctx.clean else CEDAR_OLD
    # Lower tier: y -0.6 .. -0.05 at 0.45; upper tier: y 0.05 .. 0.6 at 0.9.
    for tier, (y0, y1, z) in enumerate(((-0.6, -0.05, 0.45), (0.05, 0.6, 0.9))):
        n = 5
        for k in range(n):
            w = (y1 - y0) / n - 0.015
            y = y0 + (k + 0.5) * (y1 - y0) / n
            _bx(ctx, f"slat{tier}_{k}", (Wd, w, 0.035), (0, y, z - 0.0175), wood, bevel=0.004, uv_scale=1.5, patches=0.5)
        for sx in (-1, 0, 1):
            _bx(ctx, f"bearer{tier}{sx}", (0.05, y1 - y0, 0.07), (sx * (Wd / 2 - 0.06), (y0 + y1) / 2, z - 0.07), wood, bevel=0.004)
    # Risers.
    for k in range(10):
        _bx(ctx, f"riser_lo{k}", (Wd / 10 - 0.008, 0.02, 0.38), (-Wd / 2 + (k + 0.5) * Wd / 10, -0.56, 0.21), wood, bevel=0.003, uv_scale=1.5)
        _bx(ctx, f"riser_hi{k}", (Wd / 10 - 0.008, 0.02, 0.4), (-Wd / 2 + (k + 0.5) * Wd / 10, 0.0, 0.66), wood, bevel=0.003, uv_scale=1.5)
    # End frames.
    for sx in (-1, 1):
        _bx(ctx, f"end_lo{sx}", (0.04, 0.6, 0.45), (sx * (Wd / 2 - 0.02), -0.3, 0.225), wood, bevel=0.004)
        _bx(ctx, f"end_hi{sx}", (0.04, 0.6, 0.9), (sx * (Wd / 2 - 0.02), 0.3, 0.45), wood, bevel=0.004)
    if ctx.worn:
        r = ctx.rnd("bloom")
        _felt(ctx, "felt_lo", 0.3, -0.35, 0.46, 9, r, spread=0.9, spread_y=0.2, size=0.08, flat=0.25)
        _felt(ctx, "felt_hi", -0.4, 0.3, 0.91, 7, r, spread=0.8, spread_y=0.2, size=0.08, flat=0.25)
        _felt(ctx, "felt_riser", 0.6, -0.59, 0.25, 6, r, spread=0.4, spread_y=0.01, spread_z=0.15, size=0.06, flat=0.9, scale=(1.2, 0.4))
        _caps(ctx, "troop_a", 1.0, 0.4, 0.92, 7, r, spread=0.1, size=1.3)
        _caps(ctx, "troop_b", -1.0, -0.3, 0.47, 5, r, spread=0.08, size=1.2)


def _felt_sheet(ctx, name, w, h, nx, ny, edge, lift, r, *, seed=0, center=(0, 0, 0)):
    """A felt sheet over a w x h patch of the XY plane (facing +Z): faces outside `edge(x, y)` (True inside) are cut
    away for a ragged outline, the rest raised by `lift(x, y)` plus noise, so the felt reads as one grown mat."""
    sh = K.grid(name, w, h, nx, ny, center=center)
    K.delete_faces(sh, lambda c, n: not edge(c.x, c.y))
    # Jitter the lattice (inside the sheet's bounds) so the cut outline doesn't read as stair steps.
    jx, jy = 0.4 * w / nx, 0.4 * h / ny
    for v in sh.data.vertices:
        v.co.x = max(center[0] - w / 2, min(center[0] + w / 2, v.co.x + r.uniform(-jx, jx)))
        v.co.y = max(center[1] - h / 2, min(center[1] + h / 2, v.co.y + r.uniform(-jy, jy)))
        v.co.z = lift(v.co.x, v.co.y)
    sh.data.update()
    K.noise_disp(sh, 0.025, scale=6.0, seed=seed)
    return sh


def w5_springs_bloom_wall(ctx: K.Ctx) -> None:
    """The Bloom up a steam-soaked wall (wall-mounted, 1.8 x 2.0 m): one thick white felt of mycelium grown up from the
    floor and thinning to head height in ragged fingers, cushions bulging out of it low down, shelves of pale bracket
    caps through it and troops of small caps at the foot. Worn: higher and thicker, the caps crowding to the top."""
    r = ctx.rnd("bank")
    top = 1.55 if ctx.clean else 1.85
    fingers = [(r.uniform(-0.8, 0.8), r.uniform(0.15, 0.35)) for _ in range(6)]

    def edge(x, y):
        # y is the height up the wall before the sheet is stood up.
        lim = top * (1.0 - 0.5 * (abs(x) / 0.9) ** 1.5)
        for fx, fh in fingers:
            if abs(x - fx) < 0.07:
                lim += fh
        return y < lim

    def lift(x, y):
        return 0.03 + 0.09 * max(0.0, 1.0 - y / top) * (1.0 - 0.6 * (abs(x) / 0.9) ** 2)

    sh = _felt_sheet(ctx, "felt", 1.8, 2.0, 18, 20, edge, lift, r, seed=ctx.seed, center=(0, 1.0, 0))
    # Stand it up: grid y (height) -> Blender z, its +Z face -> -Y (out of the wall).
    K.map_verts(sh, lambda co: Vector((co.x, -max(0.005, co.z), max(0.0, co.y))))
    ctx.add(sh, FELT, uv="box", uv_scale=2.0, smooth=60, ao=False)
    # Cushions bulging out of the felt low down.
    for k in range(10 if ctx.clean else 16):
        x = r.uniform(-0.75, 0.75)
        z = r.random() ** 1.5 * top * 0.6
        rad = r.uniform(0.08, 0.15)
        b = K.blob(f"cushion{k}", rad, subdiv=2, scale=(1.3, 0.5, 1.0), rough=0.3, seed=k + 5)
        K.place(b, (x, -0.06, z + rad * 0.4))
        ctx.add(b, FELT, uv="box", uv_scale=3.0, smooth=60, ao=False)
    # Bracket caps through the felt.
    for k in range(9 if ctx.clean else 14):
        h = r.uniform(0.3, top - 0.1)
        _shelf_cap(ctx, f"shelf{k}", r.uniform(-0.6, 0.6), h, r.uniform(0.06, 0.14), r)
    # Small caps at the foot.
    for k in range(4):
        _caps(ctx, f"foot{k}", r.uniform(-0.7, 0.7), -0.14, 0.0, 5, r, spread=0.08, size=1.4)


def w5_springs_bloom_mat(ctx: K.Ctx) -> None:
    """A low cushion of Bloom felt (1.6 x 1.4 m) grown over wet tiles: one ragged mat domed in the middle with
    cushions on it, a troop of pale caps standing in it. Worn: thicker, more caps."""
    r = ctx.rnd("mat")
    lobes = [(r.uniform(-0.5, 0.5), r.uniform(-0.4, 0.4), r.uniform(0.25, 0.4)) for _ in range(5)]

    def edge(x, y):
        if (x / 0.78) ** 2 + (y / 0.68) ** 2 < 0.55:
            return True
        return any((x - lx) ** 2 + (y - ly) ** 2 < lr * lr for lx, ly, lr in lobes)

    hmax = 0.1 if ctx.clean else 0.16

    def lift(x, y):
        return 0.01 + hmax * max(0.0, 1.0 - (x / 0.8) ** 2 - (y / 0.7) ** 2)

    sh = _felt_sheet(ctx, "felt", 1.6, 1.4, 16, 14, edge, lift, r, seed=ctx.seed)
    ctx.add(sh, FELT, uv="box", uv_scale=2.0, smooth=60, ao=False)
    for k in range(6 if ctx.clean else 10):
        x, y = r.uniform(-0.45, 0.45), r.uniform(-0.35, 0.35)
        rad = r.uniform(0.07, 0.12)
        b = K.blob(f"cushion{k}", rad, subdiv=2, scale=(1.3, 1.1, 0.45), rough=0.3, seed=k + 9)
        K.place(b, (x, y, lift(x, y) + rad * 0.15))
        ctx.add(b, FELT, uv="box", uv_scale=3.0, smooth=60, ao=False)
    for k in range(5 if ctx.clean else 9):
        x, y = r.uniform(-0.5, 0.5), r.uniform(-0.4, 0.4)
        _caps(ctx, f"troop{k}", x, y, lift(x, y), 6, r, spread=0.1, size=1.8)


def w5_springs_towel_shelf(ctx: K.Ctx) -> None:
    """A tall painted cubby shelf (1.4 x 0.45 x 1.9 m): four columns of five squares, a folded stack of towels or a robe
    in each, a wire basket of soap on top. Worn: half the towels pulled out and dropped, mildew on the rest."""
    Wd, D, H = 1.4, 0.45, 1.9
    r = ctx.rnd("towels")
    dr = ctx.drnd("towels")
    paint = PAINT
    _bx(ctx, "back", (Wd, 0.02, H), (0, D / 2 - 0.01, H / 2), paint, bevel=0.003)
    for sx in (-1, 1):
        _bx(ctx, f"side{sx}", (0.025, D, H), (sx * (Wd / 2 - 0.0125), 0, H / 2), paint, bevel=0.004)
    for k in range(6):
        z = 0.05 + k * (H - 0.08) / 5
        _bx(ctx, f"shelf{k}", (Wd, D, 0.022), (0, 0, z), paint, bevel=0.003)
    for k in range(1, 4):
        _bx(ctx, f"div{k}", (0.018, D - 0.02, H - 0.1), (-Wd / 2 + k * Wd / 4, -0.01, H / 2 + 0.01), paint, bevel=0.003)
    _bx(ctx, "kick", (Wd, 0.02, 0.05), (0, -D / 2 + 0.01, 0.025), paint, bevel=0.003)
    cw = Wd / 4
    keep = 1.0 if ctx.clean else 0.5
    for row in range(5):
        z0 = 0.05 + row * (H - 0.08) / 5 + 0.011
        for col in range(4):
            x = -Wd / 2 + (col + 0.5) * cw
            if dr.random() > keep:
                continue
            n = r.randint(2, 4)
            for j in range(n):
                th = 0.06
                tw = K.box(f"towel{row}{col}{j}", (cw - 0.08, D - 0.12, th - 0.005), bevel=0.02)
                K.place(tw, (x + r.uniform(-0.01, 0.01), -0.02, z0 + th * (j + 0.5)), (0, 0, r.uniform(-3, 3)))
                ctx.add(tw, TOWEL if (row + col) % 3 else TOWEL_B, uv_scale=2.0, smooth=40, patches=0.3 if ctx.clean else 0.8)
    # Wire basket of soap on top.
    _bx(ctx, "basket", (0.4, 0.28, 0.12), (0.35, 0.0, H + 0.06), "metal_galvanized", bevel=0.01, uv_scale=3.0)
    for k in range(4):
        _bx(ctx, f"soap{k}", (0.08, 0.05, 0.03), (0.22 + k * 0.09, r.uniform(-0.06, 0.06), H + 0.13), "road_paint_cream", bevel=0.01)
    if ctx.worn:
        for k in range(3):
            tw = K.box(f"dropped{k}", (0.5, 0.35, 0.03), cuts=(4, 3, 0))
            K.noise_disp(tw, 0.03, scale=4.0, seed=k + 21)
            K.place(tw, (dr.uniform(-0.5, 0.5), -D / 2 + 0.05, 0.02), (0, 0, dr.uniform(-30, 30)))
            ctx.add(tw, TOWEL_B, uv_scale=2.0, smooth=40, patches=0.8)
        ctx.add(K.box("mildew", (Wd - 0.1, 0.005, 0.5), center=(0, -D / 2 - 0.001, 0.3)), "furn_mold", uv_scale=1.5, ao=False)


def w5_springs_changing_bench(ctx: K.Ctx) -> None:
    """A changing room bench (1.8 m): a seat of three cedar slats on painted legs at 0.45, a tall back board with a rail
    of turned pegs at 1.55, robes and a towel hanging off the pegs. Worn: the robes on the floor, the slats split."""
    Wd = 1.8
    r = ctx.rnd("bench")
    for k in range(3):
        _bx(ctx, f"slat{k}", (Wd, 0.11, 0.03), (0, -0.2 + k * 0.13, 0.435), CEDAR if ctx.clean else CEDAR_OLD, bevel=0.004, uv_scale=1.5)
    for sx in (-1, 1):
        for sy in (-1, 1):
            _bx(ctx, f"leg{sx}{sy}", (0.045, 0.045, 0.42), (sx * (Wd / 2 - 0.08), -0.08 + sy * 0.12, 0.21), PAINT, bevel=0.005)
        _bx(ctx, f"stretcher{sx}", (0.04, 0.3, 0.04), (sx * (Wd / 2 - 0.08), -0.08, 0.12), PAINT, bevel=0.004)
    # Back board and peg rail.
    _bx(ctx, "backboard", (Wd, 0.025, 1.3), (0, 0.235, 0.45 + 0.65), PAINT, bevel=0.004, patches=0.5)
    _bx(ctx, "peg_rail", (Wd, 0.03, 0.09), (0, 0.21, 1.55), CEDAR, bevel=0.006)
    pegs = [-0.7, -0.35, 0.0, 0.35, 0.7]
    for k, x in enumerate(pegs):
        W.rod(ctx, f"peg{k}", (x, 0.2, 1.55), (x, 0.08, 1.58), 0.014, CEDAR, segs=8)
    hang = [0, 2, 4] if ctx.clean else [2]
    for k in hang:
        x = pegs[k]
        robe = K.box(f"robe{k}", (0.36, 0.08, 0.95), cuts=(3, 1, 6))
        K.noise_disp(robe, 0.02, scale=4.0, seed=k + 3)
        K.taper(robe, 2, lambda t: 0.75 + 0.35 * (1 - t))
        K.place(robe, (x, 0.16, 1.58 - 0.475))
        ctx.add(robe, TOWEL if k != 2 else "canvas_grey", uv_scale=2.0, smooth=40, patches=0.4)
    if ctx.worn:
        dr = ctx.drnd("bench")
        for k in range(2):
            pile = K.box(f"floor_robe{k}", (0.6, 0.4, 0.06), cuts=(4, 3, 1))
            K.noise_disp(pile, 0.04, scale=3.0, seed=k + 9)
            K.place(pile, (dr.uniform(-0.6, 0.6), -0.05, 0.03), (0, 0, dr.uniform(-40, 40)))
            ctx.add(pile, TOWEL, uv_scale=2.0, smooth=40, patches=0.8)
    _ = r


def w5_springs_key_board(ctx: K.Ctx) -> None:
    """The cabin key board (wall-mounted, 0.8 x 0.6 m): a varnished board with a moulded edge, two rows of brass cup
    hooks under painted numbers and a key on a wooden fob on a few of them. Worn: one key left."""
    _bx(ctx, "board", (0.8, 0.025, 0.6), (0, -0.0125, 0.3), "wood_furniture_oak", bevel=0.008, uv_scale=2.0)
    _bx(ctx, "edge", (0.76, 0.01, 0.56), (0, -0.028, 0.3), "wood_furniture_dark", bevel=0.004, uv_scale=2.0)
    keys = (0, 3, 5) if ctx.clean else (5,)
    for k in range(8):
        row, col = divmod(k, 4)
        x = -0.27 + col * 0.18
        z = 0.42 - row * 0.24
        _bx(ctx, f"num{k}", (0.05, 0.003, 0.05), (x, -0.035, z + 0.06), "road_paint_white", bevel=0.0, ao=False)
        W.rod(ctx, f"hook{k}", (x, -0.03, z), (x, -0.07, z + 0.01), 0.004, BRASS, segs=5)
        if k in keys:
            _bx(ctx, f"fob{k}", (0.035, 0.012, 0.09), (x, -0.07, z - 0.08), "wood_furniture_dark", bevel=0.005)
            W.rod(ctx, f"key{k}", (x, -0.07, z - 0.01), (x, -0.07, z - 0.035), 0.006, BRASS, segs=5)


def w5_springs_cedar_tub(ctx: K.Ctx) -> None:
    """The owner's oval soaking tub (1.6 x 1.0 x 0.85 m): cedar staves round an oval, three copper hoops, a step at the
    near side and a brass tap piped from the spring at one end, the water steaming under the rim. Worn: dry, a stave
    sprung loose and the hoops green."""
    ax, ay, H = 0.78, 0.46, 0.8
    n = 28
    dr = ctx.drnd("tub")
    sprung = dr.randrange(n) if ctx.worn else -1
    for k in range(n):
        a = math.tau * (k + 0.5) / n
        x, y = math.cos(a) * ax, math.sin(a) * ay
        w = math.tau * math.hypot(ax, ay) / math.sqrt(2) / n * 1.02
        st = K.box(f"stave{k}", (w, 0.035, H), bevel=0.003, center=(0, 0, H / 2))
        K.place(st, rot=(0, 0, math.degrees(math.atan2(math.sin(a) * ax, math.cos(a) * ay)) + 90))
        if k == sprung:
            K.place(st, rot=(8.0, 0, 0))
        K.place(st, (x, y, 0))
        ctx.add(st, CEDAR if ctx.clean else CEDAR_OLD, uv_scale=1.5, patches=0.4)
    for j, z in enumerate((0.12, 0.42, 0.7)):
        hoop = W.ring_obj(f"hoop{j}", 1.0, 1.02, 0.04, segs=28)
        K.place(hoop, scale=(ax + 0.02, ay + 0.02, 1.0))
        K.place(hoop, (0, 0, z))
        ctx.add(hoop, COPPER if ctx.clean else "civic_bronze", uv_scale=3.0, smooth=40)
    fl = K.cyl("floor", 1.0, 0.04, segs=24, center=(0, 0, 0.06))
    K.place(fl, scale=(ax - 0.03, ay - 0.03, 1.0))
    ctx.add(fl, CEDAR_OLD, uv_scale=1.5)
    if ctx.clean:
        water = K.cyl("water", 1.0, 0.01, segs=24, center=(0, 0, H - 0.12))
        K.place(water, scale=(ax - 0.03, ay - 0.03, 1.0))
        ctx.add(water, WATER, uv_scale=1.0, smooth=40, ao=False)
    # Step at the near side, tap at one end.
    _bx(ctx, "step", (0.6, 0.25, 0.3), (0.0, -ay - 0.02, 0.15), CEDAR_OLD, bevel=0.01)
    W.rod(ctx, "tap_pipe", (ax - 0.02, 0.0, H + 0.05), (ax - 0.15, 0.0, H + 0.05), 0.02, BRASS if ctx.clean else "civic_bronze", segs=8)
    W.rod(ctx, "tap_riser", (ax - 0.02, 0.0, 0.0), (ax - 0.02, 0.0, H + 0.05), 0.02, BRASS if ctx.clean else "civic_bronze", segs=8)


# ============================================================================================
# The cellar
# ============================================================================================

def w5_springs_boiler(ctx: K.Ctx) -> None:
    """A riveted horizontal firetube boiler (1.6 x 3.4 x 2.5 m) on a brick setting: the round shell over the firebox,
    the front (-Y) with its two cast-iron fire doors and ash pit door in the brick, the smokebox door on the shell's end,
    rivet rows, the steam dome with its safety valve and the steam main going up, a pressure gauge and water glass on
    the front and the flue rising from the back. Worn: rust bleeding from the rivets, the fire doors hanging open on
    cold ash."""
    shell_mat = IRON if ctx.clean else RUST
    L = 3.0
    y0 = -1.65
    # Brick setting.
    _bx(ctx, "setting", (1.6, L, 0.9), (0, y0 + L / 2 + 0.05, 0.45), BRICK, bevel=0.01, uv_scale=1.0, patches=0.6)
    _bx(ctx, "front", (1.5, 0.12, 1.25), (0, y0 + 0.06, 0.62), BRICK, bevel=0.01, uv_scale=1.0)
    # Shell.
    sh = K.cyl("shell", 0.62, L, segs=24, center=(0, y0 + L / 2 + 0.05, 1.42), axis="Y")
    ctx.add(sh, shell_mat, uv="cyl", uv_axis=1, uv_scale=1.5, smooth=40, patches=0.6)
    for k in range(5):
        y = y0 + 0.2 + k * (L - 0.3) / 4
        band = W.ring_obj(f"seam{k}", 0.62, 0.635, 0.05, segs=24)
        K.place(band, rot=(90, 0, 0))
        K.place(band, (0, y, 1.42))
        ctx.add(band, shell_mat, uv_scale=2.0, smooth=40)
        for j in range(16):
            a = math.tau * j / 16
            if math.sin(a) < -0.3:
                continue
            rv = K.cyl(f"rivet{k}_{j}", 0.012, 0.02, segs=6, axis="Y")
            K.place(rv, rot=(0, math.degrees(a), 0))
            K.place(rv, (math.cos(a) * 0.64, y, 1.42 + math.sin(a) * 0.64))
            ctx.add(rv, shell_mat, uv_scale=3.0)
    # Smokebox door on the front end and the fire doors below it in the brick.
    sd = K.cyl("smokebox_door", 0.5, 0.06, segs=24, center=(0, y0 + 0.02, 1.42), axis="Y")
    ctx.add(sd, DARK if ctx.clean else RUST, uv_scale=1.5, smooth=40, patches=0.5)
    W.rod(ctx, "dog", (-0.3, y0 - 0.03, 1.42), (0.3, y0 - 0.03, 1.42), 0.02, IRON, segs=6)
    for sx in (-1, 1):
        door = K.box(f"fire_door{sx}", (0.42, 0.04, 0.34), bevel=0.01)
        if ctx.worn:
            K.place(door, (sx * 0.21, 0, 0))
            K.place(door, rot=(0, 0, -sx * 30))
            K.place(door, (sx * 0.42, y0 - 0.02, 0.62))
        else:
            K.place(door, (sx * 0.22, y0 - 0.02, 0.62))
        ctx.add(door, IRON if ctx.clean else RUST, uv_scale=2.0, patches=0.5)
    _bx(ctx, "firebox_mouth", (0.84, 0.02, 0.32), (0, y0 - 0.003, 0.62), "road_burnt", bevel=0.0, ao=False)
    _bx(ctx, "ash_door", (0.6, 0.04, 0.22), (0, y0 - 0.02, 0.2), IRON if ctx.clean else RUST, bevel=0.008)
    # Gauge and water glass.
    _cy(ctx, "gauge", 0.09, 0.05, (0.45, y0 - 0.03, 2.0), BRASS, axis="Y", segs=16)
    _bx(ctx, "gauge_face", (0.13, 0.005, 0.13), (0.45, y0 - 0.058, 2.0), "road_paint_white", bevel=0.0, ao=False)
    W.rod(ctx, "gauge_pipe", (0.45, y0 + 0.05, 1.9), (0.45, y0 + 0.05, 1.95), 0.012, BRASS, segs=6)
    W.rod(ctx, "glass", (-0.45, y0 - 0.02, 1.2), (-0.45, y0 - 0.02, 1.65), 0.018, "glass_clear", segs=8)
    # Steam dome, safety valve, main.
    _cy(ctx, "dome", 0.24, 0.3, (0, y0 + 1.0, 2.1), shell_mat, segs=16)
    _cy(ctx, "dome_cap", 0.27, 0.04, (0, y0 + 1.0, 2.27), shell_mat, segs=16)
    W.rod(ctx, "safety", (0, y0 + 1.9, 2.0), (0, y0 + 1.9, 2.3), 0.04, BRASS if ctx.clean else "civic_bronze", segs=8)
    W.rod(ctx, "lever", (0, y0 + 1.9, 2.3), (0, y0 + 2.4, 2.25), 0.012, IRON, segs=6)
    W.rod(ctx, "main", (0, y0 + 1.0, 2.29), (0, y0 + 1.0, 2.5), 0.06, IRON, segs=10)
    # Flue from the back.
    W.rod(ctx, "flue_box", (0, L / 2 + 0.05 - 0.2, 1.0), (0, L / 2 + 0.05 - 0.2, 1.6), 0.3, DARK if ctx.clean else RUST, segs=12)
    W.rod(ctx, "flue", (0, L / 2 + 0.05 - 0.2, 1.6), (0, L / 2 + 0.05 - 0.2, 2.5), 0.2, DARK if ctx.clean else RUST, segs=12)
    if ctx.worn:
        dr = ctx.drnd("ash")
        for k in range(6):
            a = K.blob(f"ash{k}", dr.uniform(0.06, 0.12), subdiv=1, scale=(1.5, 1.2, 0.3), center=(dr.uniform(-0.4, 0.4), y0 - dr.uniform(0.05, 0.12), 0.02),
                       rough=0.3, seed=k)
            ctx.add(a, "ash_burnt", uv_scale=2.0)


def w5_springs_cistern(ctx: K.Ctx) -> None:
    """The spring cistern (2.2 x 2.2 x 2.3 m): a tall cedar stave tank on a stone plinth, four iron hoops, a cover of
    boards with a hatch and a float gauge's rod and board standing over it, the feed pipe coming up out of the rock
    and the lagged hot main leaving near the top; white mineral crust down the staves. Worn: the crust thicker, the
    hoops rusted, a stave weeping."""
    R, H = 1.0, 2.0
    _cy(ctx, "plinth", 1.08, 0.12, (0, 0, 0.06), STONE, segs=20, uv_scale=1.0)
    n = 30
    for k in range(n):
        a = math.tau * (k + 0.5) / n
        st = K.box(f"stave{k}", (math.tau * R / n * 1.02, 0.05, H), bevel=0.003, center=(0, 0, H / 2))
        K.place(st, rot=(0, 0, math.degrees(a) + 90))
        K.place(st, (math.cos(a) * R, math.sin(a) * R, 0.12))
        ctx.add(st, CEDAR if ctx.clean else CEDAR_OLD, uv_scale=1.5, patches=0.5)
    for j, z in enumerate((0.35, 0.85, 1.4, 1.95)):
        hoop = W.ring_obj(f"hoop{j}", R + 0.025, R + 0.04, 0.05, segs=30)
        K.place(hoop, (0, 0, z))
        ctx.add(hoop, IRON if ctx.clean else RUST, uv_scale=3.0, smooth=40)
    for k in range(9):
        y = -R + 0.13 + k * 0.22
        chord = 2.0 * math.sqrt(max(0.0, (R + 0.03) ** 2 - (abs(y) + 0.1) ** 2))
        _bx(ctx, f"cover{k}", (chord, 0.2, 0.04), (0, y, H + 0.14), CEDAR_OLD, bevel=0.004)
    _bx(ctx, "hatch", (0.5, 0.5, 0.03), (0.4, 0.2, H + 0.175), CEDAR, bevel=0.004)
    W.rod(ctx, "float_rod", (-0.4, -0.3, H + 0.16), (-0.4, -0.3, H + 0.3), 0.012, STEEL, segs=6)
    _bx(ctx, "float_board", (0.25, 0.02, 0.06), (-0.4, -0.3, H + 0.28), "road_paint_white", bevel=0.0)
    # Feed pipe and the lagged main.
    W.rod(ctx, "feed", (0.9, -0.55, 0.0), (0.9, -0.55, 0.3), 0.06, IRON if ctx.clean else RUST, segs=10)
    W.rod(ctx, "main", (-0.85, -0.55, 1.75), (-1.1, -0.55, 1.75), 0.08, "canvas_grey", segs=10)
    # Mineral crust down the staves.
    r = ctx.rnd("crust")
    for k in range(14 if ctx.clean else 26):
        a = r.uniform(0, math.tau)
        z = r.uniform(0.2, 1.9)
        b = K.blob(f"crust{k}", r.uniform(0.04, 0.08), subdiv=1, scale=(0.6, 0.6, 2.4), center=(math.cos(a) * (R + 0.03), math.sin(a) * (R + 0.03), z),
                   rough=0.4, seed=k)
        ctx.add(b, "plaster_rubble", uv_scale=3.0, smooth=40)


def w5_springs_pipe_run(ctx: K.Ctx) -> None:
    """The spring mains along a wall (wall-mounted, 3.0 x 1.4 m): two hot mains in canvas lagging and a bare cold feed
    on iron brackets, a gate valve with its handwheel on each, a thermometer and a pressure gauge on the upper main.
    Worn: the lagging hanging off in rags, crust round the joints."""
    Lx = 3.0
    rows = [(1.15, 0.075, LAG), (0.85, 0.075, LAG), (0.45, 0.04, IRON if ctx.clean else RUST)]
    for k, (z, rr, mat) in enumerate(rows):
        W.rod(ctx, f"pipe{k}", (-Lx / 2, -0.15, z), (Lx / 2, -0.15, z), rr, mat, segs=12, uv_scale=1.0)
        # Gate valve with a handwheel.
        vx = -0.8 + k * 0.7
        _cy(ctx, f"valve{k}", rr + 0.03, 0.18, (vx, -0.15, z), IRON if ctx.clean else RUST, axis="X", segs=12)
        W.rod(ctx, f"stem{k}", (vx, -0.15, z + rr), (vx, -0.15, z + rr + 0.12), 0.01, STEEL, segs=6)
        wheel = W.ring_obj(f"wheel{k}", 0.06, 0.075, 0.015, segs=16)
        K.place(wheel, (vx, -0.15, z + rr + 0.12))
        ctx.add(wheel, "road_paint_red", uv_scale=3.0, smooth=40)
    for sx in (-1.2, 0.0, 1.2):
        W.bar(ctx, f"bracket{sx}", (sx, 0.0, 0.3), (sx, 0.0, 1.3), 0.05, 0.01, IRON if ctx.clean else RUST, up=(0, 1, 0))
        for z, rr, _m in rows:
            W.bar(ctx, f"arm{sx}_{z}", (sx, 0.0, z - rr - 0.01), (sx, -0.25, z - rr - 0.01), 0.04, 0.008, IRON if ctx.clean else RUST)
    _cy(ctx, "gauge", 0.06, 0.04, (0.9, -0.24, 1.32), BRASS, axis="Y", segs=14)
    _bx(ctx, "gauge_face", (0.09, 0.004, 0.09), (0.9, -0.262, 1.32), "road_paint_white", bevel=0.0, ao=False)
    W.rod(ctx, "gauge_stem", (0.9, -0.15, 1.22), (0.9, -0.15, 1.3), 0.008, BRASS, segs=6)
    W.rod(ctx, "thermo", (1.2, -0.15, 1.22), (1.2, -0.15, 1.38), 0.01, "glass_clear", segs=6)
    if ctx.worn:
        dr = ctx.drnd("rags")
        for k in range(5):
            x = dr.uniform(-1.3, 1.3)
            z = dr.choice((1.15, 0.85))
            rag = K.box(f"rag{k}", (0.2, 0.02, 0.35), cuts=(2, 0, 4))
            K.noise_disp(rag, 0.02, scale=5.0, seed=k + 31)
            K.place(rag, (x, -0.24, z - 0.2), (dr.uniform(-10, 10), 0, dr.uniform(-15, 15)))
            ctx.add(rag, LAG, uv_scale=2.0, smooth=40, patches=0.8)


# ============================================================================================
# Outside
# ============================================================================================

def w5_springs_boardwalk(ctx: K.Ctx) -> None:
    """A 2 x 4 m section of cedar boardwalk: boards across on two sleepers bedded in the ground, the top 0.11 up.
    Worn: boards split, sagging and a few missing."""
    r = ctx.rnd("boards")
    dr = ctx.drnd("boards")
    for sx in (-1, 1):
        _bx(ctx, f"sleeper{sx}", (0.14, 4.0, 0.07), (sx * 0.75, 0, 0.035), CEDAR_OLD, bevel=0.01, uv_scale=1.0, moss=0.4, low=0.5)
    n = 26
    pitch = 4.0 / n
    for k in range(n):
        if ctx.worn and dr.random() < 0.12:
            continue
        y = -2.0 + (k + 0.5) * pitch
        pl = P.plank(f"board{k}", 2.0 * r.uniform(0.97, 1.0), pitch - 0.012, 0.035, cuts=2,
                     bow=0.0 if ctx.clean else dr.uniform(0.0, 0.02))
        K.place(pl, (r.uniform(-0.02, 0.02), y, 0.0875), (0, 0, r.uniform(-1.0, 1.0)))
        ctx.add(pl, CEDAR_OLD if (ctx.worn or k % 4) else CEDAR, uv_scale=1.0, patches=0.5, moss=0.25)


BUILDERS = {
    "w5_springs_plunge_pool": w5_springs_plunge_pool,
    "w5_springs_rock_pool": w5_springs_rock_pool,
    "w5_springs_steam": w5_springs_steam,
    "w5_springs_steam_bench": w5_springs_steam_bench,
    "w5_springs_bloom_wall": w5_springs_bloom_wall,
    "w5_springs_bloom_mat": w5_springs_bloom_mat,
    "w5_springs_boiler": w5_springs_boiler,
    "w5_springs_cistern": w5_springs_cistern,
    "w5_springs_boardwalk": w5_springs_boardwalk,
    "w5_springs_towel_shelf": w5_springs_towel_shelf,
    "w5_springs_changing_bench": w5_springs_changing_bench,
    "w5_springs_key_board": w5_springs_key_board,
    "w5_springs_cedar_tub": w5_springs_cedar_tub,
    "w5_springs_pipe_run": w5_springs_pipe_run,
}


def build(params: dict, outputs: list[str]) -> None:
    K.run(params, outputs, BUILDERS)
