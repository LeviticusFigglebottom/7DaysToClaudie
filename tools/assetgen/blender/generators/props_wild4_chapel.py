"""Forest set pieces, round 4 (ADR-0053): props of Shiloh Chapel (w4_overgrown_chapel), a pioneer timber chapel in
a forest clearing half taken back by the woods.

The chapel: settlers' plank pews, a panelled box pulpit, a plank table altar under a linen frontal. The churchyard:
the bronze bell where it came down with its bell-cote, round-topped slate headstones, cedar grave crosses and thin
marble tablets (lettered faces from the shared civic_engrave atlas), a family plot's wrought-iron railing and its
gate, the roofed lych gate, the dry-stone wall, an open grave with its spoil heap, graves the Bloom has broken
open, ivy and long grass. The Teague vault: the granite front, rubble side walls and turf cap that wrap the vault
porch's kit room (a shell), the burial niches, pine coffins, the church silver chest and the reliquary.

Conventions (docs/ASSET_PIPELINE.md): metres, Z up, front -Y, origin bottom centre; floor props have their depth
centred on the origin (PoiBuilder's collision box is the def's size centred there). The ivy hangs with its origin on
the wall plane, bottom centre, reaching out toward -Y. The vault shell's origin is the kit room's plan centre on the
ground (lib.props_outskirts_parts.Room); the catalog passes the room's size, floor height and openings exactly as
w4_overgrown_chapel.json has them. Only shared materials are used. 'clean' is the chapel as the pastor kept it,
'worn' a winter after he went down into the vault, 'destroyed' broken.
"""
from __future__ import annotations

import math

from mathutils import Vector

from lib import props_ext_kit as K
from lib import props_outskirts_parts as O
from lib import props_wild_parts as W

PINE = "wild_lumber_dark"
PINE_OLD = "wild_lumber_weathered"
CEDAR = "wild_cedar"
STONE = "mine_limestone"
FIELD = "stone_river"
GRANITE = "civic_granite"
IRON = "civic_iron"
SOIL = "civic_soil"
TURF = "moss_mound"
MOSS = "sphagnum_green"
LINEN = "furn_linen"
BRONZE = "civic_bronze"
GILT = "civic_brass"
SILVER = "road_chrome"
ENGRAVE = "civic_engrave_granite"
ENGRAVE_MARBLE = "civic_engrave_marble"
LEAVES = "foliage_birch"
GRASS = "grass"


def _bx(ctx, name, size, center, mat, *, bevel=0.006, uv_scale=2.0, **kw):
    return ctx.add(K.box(name, size, center=center, bevel=bevel), mat, uv="box", uv_scale=uv_scale, **kw)


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


def _tilt(ctx, rot, pivot=(0, 0, 0)) -> None:
    """Rotates every registered part about a pivot (Euler degrees): leaning stones, a sagging gate."""
    p = Vector(pivot)
    for o in ctx.parts:
        K.place(o, -p)
        K.place(o, (0, 0, 0), rot)
        K.place(o, p)


def _engrave_rect(cell: int, y0: float = 20.0, y1: float = 500.0) -> tuple[float, float, float, float]:
    """UV rect of carved headstone face `cell` of the shared civic_engrave atlas (1024 px, 4 x 2 portrait
    cells of 256 x 512; textures/gen/civic.py). Cells 0, 4, 6 and 7 carry no town's name."""
    cx, cy = cell % 4, cell // 4
    x0, x1 = cx * 256 + 2, cx * 256 + 254
    ya, yb = cy * 512 + y0 + 2, cy * 512 + y1 - 2
    return (x0 / 1024.0, 1.0 - yb / 1024.0, x1 / 1024.0, 1.0 - ya / 1024.0)


def _arch_outline(w: float, h: float, segs: int = 10) -> list[tuple[float, float]]:
    """A round-topped slab outline (x, z), counter-clockwise from the bottom left."""
    r = w / 2
    pts = [(-r, 0.0), (r, 0.0)]
    for i in range(segs + 1):
        a = math.pi * i / segs
        pts.append((r * math.cos(a), h - r + r * math.sin(a)))
    pts.append((-r, 0.0))
    # Drop the duplicated corner points the arc starts and ends on.
    out = []
    for p in pts:
        if not out or (abs(out[-1][0] - p[0]) > 1e-5 or abs(out[-1][1] - p[1]) > 1e-5):
            out.append(p)
    if abs(out[0][0] - out[-1][0]) < 1e-5 and abs(out[0][1] - out[-1][1]) < 1e-5:
        out.pop()
    return out


def _caps(ctx, name, cx, cy, z, n, r, *, spread=0.12, size=1.0, mat="bloom_caps"):
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
        ctx.add(stem, "bloom_felt", uv="box", uv_scale=4.0, smooth=40, ao=False)
        ctx.add(cap, mat, uv="box", uv_scale=4.0, smooth=40, ao=False)


def _felt(ctx, name, cx, cy, z, n, r, *, spread=0.3, size=0.07, flat=0.35):
    """Cushions of white Bloom felt."""
    for k in range(n):
        x = cx + r.uniform(-spread, spread)
        y = cy + r.uniform(-spread, spread)
        b = K.blob(f"{name}{k}", size * r.uniform(0.6, 1.3), subdiv=1, scale=(1.4, 1.2, flat), center=(x, y, z), rough=0.35, seed=k + 3)
        ctx.add(b, "bloom_felt", uv="box", uv_scale=3.0, smooth=50, ao=False)


# ============================================================================================
# The chapel
# ============================================================================================

def w4_chapel_pew(ctx: K.Ctx) -> None:
    """A settler's pew: a seat of two wide pine planks pegged into sawn end boards (a scrolled arm at the
    front, the back raked), a two-plank backrest, a hymn shelf on the back. Worn: grey with damp, moss in the
    joints, the top backrest plank split. Destroyed: the seat broken through in the middle and sagging, an end
    board knocked off."""
    L, D = 1.9, 0.62
    hd = D / 2
    wood = PINE if ctx.clean else PINE_OLD
    moss = 0.0 if ctx.clean else 0.5
    r = ctx.rnd("pew")
    # End boards: an outline in (y, z) extruded along x.
    end = [(-hd, 0.0), (-hd + 0.08, 0.0), (-hd + 0.08, 0.32), (-hd + 0.02, 0.36), (-hd + 0.02, 0.62), (-hd + 0.12, 0.66),
           (-0.06, 0.6), (0.12, 0.62), (hd - 0.02, 0.95), (hd, 0.95), (hd, 0.0), (hd - 0.1, 0.0), (hd - 0.1, 0.06), (-hd + 0.18, 0.06),
           (-hd + 0.18, 0.0)]
    for k, sx in enumerate((-1, 1)):
        if ctx.destroyed and sx == 1:
            continue
        e = K.prism(f"end{k}", end, 0.05, plane="YZ")
        K.place(e, (sx * (L / 2 - 0.025), 0, 0))
        ctx.add(e, wood, uv="box", uv_scale=1.5, moss=moss, patches=0.6)
    seat_z = 0.44
    if ctx.destroyed:
        for k, sx in enumerate((-1, 1)):
            half = K.box(f"seat{k}", (L / 2 - 0.06, 0.4, 0.035), center=(0, 0, 0), bevel=0.004)
            K.place(half, (0, 0, 0), (0, sx * 11, 0))
            K.place(half, (sx * L / 4, -0.11, seat_z - 0.09))
            ctx.add(half, wood, uv="box", uv_scale=1.5, long_axis=0, moss=moss)
    else:
        for k, y in enumerate((-0.2, -0.0)):
            _bx(ctx, f"seat{k}", (L - 0.02, 0.2, 0.035), (0, y, seat_z - 0.0175), wood, bevel=0.004, uv_scale=1.5, long_axis=0, moss=moss)
        _bx(ctx, "rail", (L - 0.1, 0.03, 0.08), (0, -0.27, seat_z - 0.08), wood, bevel=0.003, uv_scale=1.5, long_axis=0)
    # Backrest planks, raked back.
    for k, z in enumerate((0.62, 0.84)):
        y = 0.12 + (z - 0.6) * 0.45
        if ctx.worn and k == 1:
            for j, sx in enumerate((-1, 1)):
                piece = K.box(f"back{k}{j}", (L / 2 - 0.05, 0.022, 0.13), bevel=0.003)
                K.place(piece, (0, 0, 0), (-12, sx * (4 if ctx.destroyed else 2), 0))
                K.place(piece, (sx * (L / 4 + 0.01), y + 0.01, z - (0.04 if ctx.destroyed else 0.01) * (1 + j)))
                ctx.add(piece, wood, uv="box", uv_scale=1.5, long_axis=0, moss=moss)
        else:
            plank = K.box(f"back{k}", (L - 0.04, 0.022, 0.13), bevel=0.003)
            K.place(plank, (0, 0, 0), (-12, 0, 0))
            K.place(plank, (0, y, z))
            ctx.add(plank, wood, uv="box", uv_scale=1.5, long_axis=0, moss=moss)
    # Hymn shelf on the back (for the pew behind).
    _bx(ctx, "shelf", (L - 0.2, 0.08, 0.02), (0, hd - 0.06, 0.66), wood, bevel=0.002)
    _bx(ctx, "shelf_lip", (L - 0.2, 0.012, 0.04), (0, hd - 0.02, 0.69), wood, bevel=0.002)
    for k in range(2 if ctx.clean else 1):
        b = K.box(f"hymnal{k}", (0.12, 0.03, 0.18), bevel=0.004)
        K.place(b, (0, 0, 0), (-8, 0, 0))
        K.place(b, (-0.5 + k * 0.15 + r.uniform(-0.03, 0.03), hd - 0.06, 0.77))
        ctx.add(b, "item_bookcloth", uv="box", uv_scale=3.0)
    _centre_depth(ctx)


def w4_chapel_pulpit(ctx: K.Ctx) -> None:
    """A panelled pine box pulpit on a plinth: raised panels on its front and sides, a moulded rail, a sloped
    book board with the big Bible open on it, two steps up its right side. Worn: the panels warped and streaked,
    the Bible swollen and mouldy."""
    wood = PINE if ctx.clean else PINE_OLD
    _bx(ctx, "plinth", (1.0, 0.9, 0.2), (0, 0, 0.1), wood, bevel=0.01, uv_scale=1.2)
    bw, bd, x0 = 0.72, 0.62, -0.12
    z0, z1 = 0.2, 1.18
    # The box: four panelled walls.
    for k, (sx, sy, w, d) in enumerate([(0, -1, bw, 0.04), (0, 1, bw, 0.04), (-1, 0, 0.04, bd), (1, 0, 0.04, bd)]):
        cx = x0 + sx * (bw / 2 - 0.02)
        cy = sy * (bd / 2 - 0.02)
        if k == 3:
            # The open side: a door frame only, where the steps arrive.
            for j, yy in enumerate((-bd / 2 + 0.04, bd / 2 - 0.04)):
                _bx(ctx, f"jamb{j}", (0.04, 0.06, z1 - z0), (cx, yy, (z0 + z1) / 2), wood, bevel=0.004)
            continue
        _bx(ctx, f"wall{k}", (w, d, z1 - z0), (cx, cy, (z0 + z1) / 2), wood, bevel=0.005, uv_scale=1.2)
        if sy == -1:
            for j in range(2):
                px = x0 - bw / 4 + j * bw / 2
                _bx(ctx, f"panel{j}", (bw / 2 - 0.1, 0.02, 0.62), (px, -bd / 2 - 0.008, 0.68), wood, bevel=0.012, uv_scale=1.2)
        if sx == -1:
            _bx(ctx, "panel_side", (0.02, bd - 0.14, 0.62), (x0 - bw / 2 - 0.008, 0, 0.68), wood, bevel=0.012, uv_scale=1.2)
    _bx(ctx, "rail", (bw + 0.06, bd + 0.06, 0.05), (x0, 0, z1 + 0.025), wood, bevel=0.01)
    # The book board: sloped to the front, a lip to hold the Bible.
    board = K.box("board", (0.52, 0.34, 0.025), bevel=0.003)
    K.place(board, (0, 0, 0), (-22, 0, 0))
    K.place(board, (x0, -0.16, z1 + 0.13))
    ctx.add(board, wood, uv="box", uv_scale=1.5)
    _bx(ctx, "board_lip", (0.52, 0.02, 0.04), (x0, -0.32, z1 + 0.08), wood, bevel=0.003)
    _bx(ctx, "board_post", (0.06, 0.06, 0.14), (x0, -0.08, z1 + 0.06), wood)
    # The Bible lying open on the board.
    for j, sx in enumerate((-1, 1)):
        leaf = K.box(f"bible{j}", (0.2, 0.26, 0.035 if ctx.clean else 0.05), bevel=0.006)
        K.place(leaf, (0, 0, 0), (-22, sx * 4, 0))
        K.place(leaf, (x0 + sx * 0.1, -0.15, z1 + 0.165))
        ctx.add(leaf, "paper_pages" if ctx.clean else "item_paper_ledger", uv="box", uv_scale=3.0, ao=False)
        cov = K.box(f"cover{j}", (0.205, 0.265, 0.008), bevel=0.002)
        K.place(cov, (0, 0, 0), (-22, sx * 4, 0))
        K.place(cov, (x0 + sx * 0.1, -0.145, z1 + 0.14))
        ctx.add(cov, "item_bookcloth", uv="box", uv_scale=3.0)
    # Two steps up the right side, inside the plinth's footprint.
    for k in range(2):
        _bx(ctx, f"step{k}", (0.24, 0.5 - k * 0.12, 0.02), (0.37, 0.12 + k * 0.06, 0.4 + k * 0.22), wood, bevel=0.003)
        _bx(ctx, f"riser{k}", (0.22, 0.02, 0.22), (0.37, -0.12 + k * 0.12, 0.3 + k * 0.22), wood, bevel=0.002)
    _bx(ctx, "stringer", (0.03, 0.45, 0.6), (0.48, 0.15, 0.45), wood, bevel=0.004)
    _centre_depth(ctx)


def w4_chapel_altar(ctx: K.Ctx) -> None:
    """A table altar of adzed planks under a white linen frontal, two short brass candlesticks and a turned
    wooden cross. Worn: the linen grey and torn up one side, wax run down the boards, a candlestick down."""
    Wd, D, H = 1.6, 0.7, 0.86
    wood = PINE if ctx.clean else PINE_OLD
    for k, y in enumerate((-0.23, 0.0, 0.23)):
        _bx(ctx, f"top{k}", (Wd, 0.225, 0.06), (0, y, H - 0.03), wood, bevel=0.006, uv_scale=1.4, long_axis=0)
    for sx in (-1, 1):
        for sy in (-1, 1):
            _bx(ctx, f"leg{sx}{sy}", (0.1, 0.1, H - 0.06), (sx * (Wd / 2 - 0.1), sy * (D / 2 - 0.1), (H - 0.06) / 2), wood, bevel=0.008)
    _bx(ctx, "back", (Wd - 0.2, 0.03, H - 0.2), (0, D / 2 - 0.1, (H - 0.06) / 2 + 0.05), wood, bevel=0.003)
    # The linen frontal hanging over the front edge.
    nx, nz = 12, 6
    sheet = K.quad_sheet("frontal", (-Wd / 2 - 0.01, -D / 2 - 0.012, 0.3), (Wd / 2 + 0.01, -D / 2 - 0.012, 0.3),
                         (Wd / 2 + 0.01, -D / 2 - 0.012, H + 0.005), (-Wd / 2 - 0.01, -D / 2 - 0.012, H + 0.005), nx, nz)
    r = ctx.drnd("linen")
    for v in sheet.data.vertices:
        t = (H - v.co.z) / (H - 0.3)
        v.co.y -= 0.012 * math.sin(v.co.x * 9.0 + 1.3) * t
        if ctx.worn and v.co.x > 0.25:
            v.co.z += 0.32 * t * min(1.0, (v.co.x - 0.25) / 0.4)
    ctx.add(sheet, LINEN, uv="planar", uv_axis=1, uv_scale=1.5, smooth=40, ao=False)
    _bx(ctx, "cloth_top", (Wd + 0.02, D - 0.1, 0.006), (0, -0.04, H + 0.003), LINEN, bevel=0.0, ao=False)
    # Candlesticks and the cross.
    prof = [(0.0, 0.0), (0.045, 0.0), (0.04, 0.015), (0.012, 0.03), (0.01, 0.09), (0.03, 0.1), (0.025, 0.11), (0.0, 0.11)]
    for k, sx in enumerate((-1, 1)):
        cs = K.lathe(f"stick{k}", prof, segs=10)
        if ctx.worn and k == 1:
            K.place(cs, (0, 0, 0), (90, 0, 30))
            K.place(cs, (sx * 0.45, -0.1, H + 0.05))
        else:
            K.place(cs, (sx * 0.55, 0.12, H + 0.006))
            cnd = K.cyl(f"candle{k}", 0.012, 0.09 if ctx.clean else 0.04, segs=8,
                        center=(sx * 0.55, 0.12, H + 0.116 + (0.045 if ctx.clean else 0.02)))
            ctx.add(cnd, "candle_wax", uv="box", uv_scale=4.0, smooth=40, ao=False)
        ctx.add(cs, GILT, uv="box", uv_scale=4.0, smooth=40)
    _bx(ctx, "cross_base", (0.14, 0.1, 0.04), (0, 0.15, H + 0.02), wood, bevel=0.005)
    _bx(ctx, "cross_up", (0.03, 0.03, 0.24), (0, 0.15, H + 0.16), wood, bevel=0.004)
    _bx(ctx, "cross_bar", (0.13, 0.03, 0.03), (0, 0.15, H + 0.2), wood, bevel=0.004)
    if ctx.worn:
        rr = ctx.rnd("wax")
        for k in range(5):
            d = K.blob(f"wax{k}", 0.02, subdiv=1, scale=(1.4, 1.0, 0.25), center=(rr.uniform(-0.7, 0.7), rr.uniform(-0.25, 0.25), H + 0.008),
                       rough=0.3, seed=k)
            ctx.add(d, "candle_wax", uv="box", uv_scale=4.0, ao=False)
    _centre_depth(ctx)


def w4_chapel_bell_fallen(ctx: K.Ctx) -> None:
    """The chapel's bronze bell on its side in the grass where it came down with its bell-cote: the yoke still
    bolted to its crown, the cote's rotten posts snapped and scattered, its shingled hood broken in two. Worn:
    green with verdigris and moss, the grass grown up through the wreck."""
    r = ctx.rnd("bell")
    prof = [(0.0, 0.62), (0.12, 0.61), (0.17, 0.58), (0.2, 0.5), (0.22, 0.36), (0.26, 0.2), (0.33, 0.08), (0.38, 0.02),
            (0.385, 0.0), (0.35, 0.0), (0.3, 0.06), (0.24, 0.18), (0.2, 0.34), (0.18, 0.5), (0.14, 0.56), (0.0, 0.57)]
    bell = K.lathe("bell", prof, segs=24, cap_bottom=False, cap_top=False)
    lip = K.lathe("bell_lip", [(0.35, 0.0), (0.39, 0.0), (0.39, 0.03), (0.36, 0.03)], segs=24, close_profile=True)
    yoke = K.box("yoke", (0.6, 0.16, 0.16), center=(0, 0, 0.7), bevel=0.01)
    straps = [K.box(f"strap{k}", (0.03, 0.08, 0.16), center=(sx * 0.08, 0, 0.6)) for k, sx in enumerate((-1, 1))]
    clapper = K.cyl("clapper", 0.02, 0.4, segs=6, center=(0.12, 0.0, 0.25))
    ball = K.blob("ball", 0.05, subdiv=1, center=(0.18, 0.0, 0.06))
    parts = [(bell, BRONZE), (lip, BRONZE), (yoke, PINE_OLD), (clapper, "wild_cast_iron_rust"), (ball, "wild_cast_iron_rust")]
    parts += [(s, "wild_cast_iron_rust") for s in straps]
    for o, m in parts:
        K.place(o, (0, 0, 0), (0, 98, 0))
        K.place(o, (0.15, -0.1, 0.38))
        ctx.add(o, m, uv="box", uv_scale=2.0, smooth=40 if m == BRONZE else None, moss=0.0 if ctx.clean else 0.5, patches=0.6)
    # The bell-cote's wreck: two snapped posts, a cross tie and the hood in two pieces.
    for k, (a, b, w) in enumerate([((-0.95, -0.6, 0.07), (-0.2, 0.75, 0.12), 0.14), ((0.55, 0.65, 0.07), (1.05, -0.55, 0.1), 0.14),
                                    ((-0.8, 0.1, 0.25), (0.2, 0.78, 0.06), 0.1)]):
        W.bar(ctx, f"post{k}", a, b, w, w, PINE_OLD, bevel=0.01, moss=0.5)
    for k, (cx, cy, yaw, tilt) in enumerate([(-0.55, 0.45, 15, 28), (0.75, -0.2, -40, -20)]):
        hood = K.box(f"hood{k}", (0.9, 0.7, 0.03))
        K.place(hood, (0, 0, 0), (tilt, 0, yaw))
        K.place(hood, (cx, cy, 0.3 + abs(tilt) / 120))
        ctx.add(hood, "civic_shingle", uv="box", uv_scale=1.0, moss=0.6)
        rafter = K.box(f"rafter{k}", (0.9, 0.06, 0.06))
        K.place(rafter, (0, 0, 0), (tilt, 0, yaw))
        K.place(rafter, (cx, cy, 0.27 + abs(tilt) / 120))
        ctx.add(rafter, PINE_OLD, uv="box", uv_scale=1.5)
    if ctx.worn:
        for k in range(6):
            t = K.blob(f"moss{k}", 0.08, subdiv=1, scale=(1.5, 1.2, 0.4), center=(r.uniform(-0.9, 0.9), r.uniform(-0.7, 0.7), 0.02),
                       rough=0.4, seed=k)
            ctx.add(t, MOSS, uv="box", uv_scale=2.0, smooth=50)
    _centre_depth(ctx)


# ============================================================================================
# The churchyard
# ============================================================================================

def _snap(ctx, keep_below: float, *, fall=(0, -0.55)) -> None:
    """Destroyed headstones: everything above `keep_below` breaks off and lies face up in front."""
    top = []
    for o in list(ctx.parts):
        zs = [v.co.z for v in o.data.vertices]
        if min(zs) >= keep_below - 0.02:
            top.append(o)
        elif max(zs) > keep_below:
            # The part breaks in two: the stub stays, its copy above the break falls (the mesh copy keeps the
            # part's material, UVs and painted channels).
            dup = K.duplicate(o, o.name + "_broken")
            K.cut_plane(o, (0, 0, keep_below), (0, 0, 1), keep="below")
            K.cut_plane(dup, (0, 0, keep_below), (0, 0, 1), keep="above")
            ctx.parts.append(dup)
            top.append(dup)
    for o in top:
        K.place(o, (0, 0, -keep_below))
        K.place(o, (0, 0, 0), (-88, 0, 7))
        K.place(o, (fall[0], fall[1], 0.06))


def w4_chapel_headstone(ctx: K.Ctx) -> None:
    """A round-topped slate headstone on a fieldstone footing, a lettered face (civic_engrave cell `cell`).
    Worn: leaning with the frost heave, moss up its face. Destroyed: snapped off at the footing and lying face up
    in the grass in front of it."""
    cell = int(ctx.param("cell", 0))
    w, h, t = 0.5, 0.75, 0.065
    foot = K.box("footing", (0.6, 0.24, 0.1), center=(0, 0, 0.05), bevel=0.02)
    K.noise_disp(foot, 0.012, 6.0, seed=ctx.seed)
    ctx.add(foot, FIELD, uv="box", uv_scale=2.0, moss=0.6)
    slab = K.prism("slab", _arch_outline(w, h), t, plane="XZ", bevel=0.006)
    K.place(slab, (0, 0, 0.08))
    face_z0 = 0.08
    ctx.add(slab, ENGRAVE, uv="planar", uv_axis=1, rect=_engrave_rect(cell),
            moss=0.0 if ctx.clean else 0.55, patches=0.5)
    del face_z0
    if ctx.destroyed:
        _snap(ctx, 0.2)
    elif ctx.worn:
        rr = ctx.rnd("lean")
        _tilt(ctx, (rr.uniform(-10, -5), rr.uniform(-5, 5), rr.uniform(-4, 4)))
    _centre_depth(ctx)


def w4_chapel_headstone_cross(ctx: K.Ctx) -> None:
    """A grave cross of two adzed cedar boards pegged together, a name burned into the crossbar, set in a cairn
    of fieldstones. Worn: silver-grey, cracked and leaning. Destroyed: snapped and lying across the grave."""
    wood = CEDAR if ctx.clean else PINE_OLD
    r = ctx.rnd("cairn")
    for k in range(6):
        a = k / 6 * math.tau + r.uniform(-0.3, 0.3)
        s = K.chunk(f"cairn{k}", r.uniform(0.09, 0.14), r, n=10, flat=0.6)
        K.place(s, (math.cos(a) * 0.12, math.sin(a) * 0.06, 0.035))
        ctx.add(s, FIELD, uv="box", uv_scale=3.0, moss=0.5)
    up = K.box("upright", (0.085, 0.045, 1.05), center=(0, 0, 0.525), bevel=0.006, cuts=(0, 0, 4))
    bar = K.box("crossbar", (0.56, 0.044, 0.085), center=(0, -0.045, 0.77), bevel=0.006, cuts=(4, 0, 0))
    for o in (up, bar):
        K.noise_disp(o, 0.004, 9.0, seed=ctx.seed)
        ctx.add(o, wood, uv="box", uv_scale=2.0, moss=0.0 if ctx.clean else 0.4)
    burn = K.box("burn", (0.36, 0.004, 0.03), center=(0, -0.068, 0.77))
    ctx.add(burn, "wood_charred", uv="box", uv_scale=4.0, ao=False)
    for x in (-0.02, 0.02):
        _cy(ctx, f"peg{x}", 0.007, 0.01, (x, -0.069, 0.77), "wood_creosote", axis="Y", segs=6)
    if ctx.destroyed:
        _snap(ctx, 0.3, fall=(0.1, -0.5))
    elif ctx.worn:
        rr = ctx.rnd("lean")
        _tilt(ctx, (rr.uniform(-12, -6), rr.uniform(-7, 7), rr.uniform(-6, 6)))
    _centre_depth(ctx)


def w4_chapel_headstone_tablet(ctx: K.Ctx) -> None:
    """A thin marble tablet with a scalloped top set straight into the turf, its lettering worn soft (civic_engrave
    cell `cell`). Worn: tipped back and furred with moss. Destroyed: cracked across and the top lying in front."""
    cell = int(ctx.param("cell", 6))
    w, h, t = 0.46, 0.76, 0.055
    pts = [(-w / 2, 0.0), (w / 2, 0.0), (w / 2, h - 0.1)]
    for i in range(1, 9):
        a = math.pi * i / 9
        x = w / 2 * math.cos(a)
        z = h - 0.1 + 0.1 * math.sin(a) + (0.02 if i in (3, 6) else 0.0)
        pts.append((x, z))
    pts.append((-w / 2, h - 0.1))
    slab = K.prism("tablet", pts, t, plane="XZ", bevel=0.005)
    ctx.add(slab, ENGRAVE_MARBLE, uv="planar", uv_axis=1, rect=_engrave_rect(cell, 40, 480),
            moss=0.0 if ctx.clean else 0.6, patches=0.5)
    sod = K.blob("sod", 0.2, subdiv=1, scale=(1.5, 0.6, 0.18), center=(0, 0, 0.0), rough=0.4, seed=ctx.seed)
    ctx.add(sod, TURF, uv="box", uv_scale=2.0, smooth=50)
    if ctx.destroyed:
        _snap(ctx, 0.35, fall=(0.0, -0.45))
    elif ctx.worn:
        rr = ctx.rnd("lean")
        _tilt(ctx, (rr.uniform(8, 14), rr.uniform(-4, 4), rr.uniform(-5, 5)))
    _centre_depth(ctx)


def _kerb(ctx, name, L, worn):
    k = K.box(name, (L, 0.14, 0.12), center=(0, 0, 0.06), bevel=0.012, cuts=(4, 0, 0))
    ctx.add(k, GRANITE, uv="box", uv_scale=1.5, moss=0.5 if worn else 0.2, patches=0.5)


def _finial(ctx, name, x, z, y=0.0):
    sp = K.lathe(name, [(0.0, 0.0), (0.012, 0.0), (0.02, 0.03), (0.0, 0.08)], segs=6)
    K.place(sp, (x, y, z))
    ctx.add(sp, IRON, uv="box", uv_scale=4.0, smooth=40)


def w4_chapel_iron_railing(ctx: K.Ctx) -> None:
    """Two metres of a family plot's wrought-iron railing: square pickets with cast spear finials between two flat
    rails, end posts with ball caps, on a dressed granite kerb. Worn: rust bleeding down the kerb, a picket bent
    outward."""
    L = 2.0
    _kerb(ctx, "kerb", L, ctx.worn)
    for k, z in enumerate((0.26, 0.92)):
        W.bar(ctx, f"rail{k}", (-L / 2 + 0.03, 0, z), (L / 2 - 0.03, 0, z), 0.018, 0.04, IRON)
    for k, sx in enumerate((-1, 1)):
        x = sx * (L / 2 - 0.03)
        _bx(ctx, f"post{k}", (0.05, 0.05, 0.95), (x, 0, 0.12 + 0.475), IRON, bevel=0.004)
        ball = K.blob(f"ball{k}", 0.035, subdiv=1, center=(x, 0, 1.1))
        ctx.add(ball, IRON, uv="box", uv_scale=4.0, smooth=40)
    n = 15
    bent = ctx.rnd("bent").randrange(2, n - 2) if ctx.worn else -1
    for k in range(n):
        x = -L / 2 + 0.12 + k * (L - 0.24) / (n - 1)
        top = 1.02
        if k == bent:
            pk = K.box(f"picket{k}", (0.018, 0.018, top - 0.12), center=(0, 0, (top - 0.12) / 2), cuts=(0, 0, 6))
            K.bend(pk, 1, -0.12, along=2, origin=0.3)
            K.place(pk, (x, 0, 0.12))
            ctx.add(pk, IRON, uv="box", uv_scale=4.0)
            continue
        _bx(ctx, f"picket{k}", (0.018, 0.018, top - 0.12), (x, 0, 0.12 + (top - 0.12) / 2), IRON, bevel=0.0, uv_scale=4.0)
        _finial(ctx, f"spear{k}", x, top)
    _centre_depth(ctx)


def w4_chapel_iron_railing_gate(ctx: K.Ctx) -> None:
    """The plot's gate: two heavy posts with ball finials and a scrolled arch between them, the little gate swung
    open on its pins and rusted fast in the grass, the gap between the posts clear."""
    L = 2.0
    for k, sx in enumerate((-1, 1)):
        kb = K.box(f"kerb{k}", (0.5, 0.14, 0.12), center=(sx * 0.75, 0, 0.06), bevel=0.012)
        ctx.add(kb, GRANITE, uv="box", uv_scale=1.5, moss=0.4)
        x = sx * (L / 2 - 0.05)
        _bx(ctx, f"post{k}", (0.07, 0.07, 1.2), (x, 0, 0.6), IRON, bevel=0.006)
        ball = K.blob(f"ball{k}", 0.05, subdiv=2, center=(x, 0, 1.27))
        ctx.add(ball, IRON, uv="box", uv_scale=4.0, smooth=40)
        # A short run of pickets between each post and the gap.
        for j in range(3):
            px = sx * (0.6 + j * 0.12)
            _bx(ctx, f"stub{k}{j}", (0.018, 0.018, 0.86), (px, 0, 0.12 + 0.43), IRON, bevel=0.0, uv_scale=4.0)
            _finial(ctx, f"stub_spear{k}{j}", px, 0.98)
        W.bar(ctx, f"stub_rail{k}", (sx * 0.55, 0, 0.92), (x, 0, 0.92), 0.018, 0.04, IRON)
    # The scrolled arch over the gap.
    arc = [(0.9 * math.cos(math.pi * i / 16), 0.0, 1.18 + 0.24 * math.sin(math.pi * i / 16)) for i in range(17)]
    ctx.add(K.tube("arch", arc, 0.012, segs=6), IRON, uv="box", uv_scale=4.0, smooth=40)
    for k, sx in enumerate((-1, 1)):
        scroll = [(sx * (0.3 + 0.08 * math.cos(a)), 0.0, 1.27 + 0.08 * math.sin(a)) for a in [i * 0.45 for i in range(14)]]
        ctx.add(K.tube(f"scroll{k}", scroll, 0.008, segs=5), IRON, uv="box", uv_scale=4.0, smooth=40)
    # The gate leaf, hinged on the left post and swung open inward (toward +Y, the plot), sunk at its free end.
    leaf_w = 0.82
    hinge = Vector((-(L / 2 - 0.1), 0.0, 0.0))
    swing = 105.0
    leaf_parts = []
    for z in (0.22, 0.88):
        leaf_parts.append(W.bar_obj(f"leaf_rail{z}", (0, 0, z), (leaf_w, 0, z), 0.018, 0.035))
    for j in range(6):
        x = 0.06 + j * (leaf_w - 0.12) / 5
        leaf_parts.append(K.box(f"leaf_picket{j}", (0.016, 0.016, 0.82), center=(x, 0, 0.55)))
    leaf_parts.append(K.box("leaf_stile", (0.03, 0.03, 0.9), center=(leaf_w, 0, 0.53)))
    for o in leaf_parts:
        K.place(o, (0, 0, 0), (0, -4 if ctx.clean else -7, 0))
        K.place(o, (0, 0, 0), (0, 0, swing))
        K.place(o, hinge + Vector((0, 0, 0.08)))
        ctx.add(o, IRON, uv="box", uv_scale=4.0)


def w4_chapel_stone_wall(ctx: K.Ctx) -> None:
    """Two metres of dry-stone churchyard wall: fieldstones laid in rough courses without mortar under a row of
    flat capstones, moss in the joints. Worn: the right-hand end tumbled, its stones in the grass."""
    L, D, H = 2.0, 0.5, 0.75
    r = ctx.rnd("wall")
    dr = ctx.drnd("tumble")
    courses = 4
    for c in range(courses):
        z = 0.06 + c * 0.15
        x = -L / 2 + r.uniform(0.0, 0.12)
        width = D - c * 0.05
        while x < L / 2 - 0.05:
            s = r.uniform(0.22, 0.36)
            if ctx.worn and x > L / 2 - 0.55 and c >= 2:
                if dr.random() < 0.7:
                    st = K.chunk(f"fallen{c}_{x:.2f}", s, dr, n=10, flat=0.6)
                    K.place(st, (min(L / 2, x + dr.uniform(0.1, 0.5)), dr.uniform(-0.6, -0.3), 0.06))
                    ctx.add(st, FIELD, uv="box", uv_scale=2.5, moss=0.5)
                x += s
                continue
            for sy in (-1, 1):
                st = K.chunk(f"st{c}_{x:.2f}_{sy}", s, r, n=12, flat=0.55, elong=1.3)
                K.place(st, (x + s / 2, sy * (width / 2 - s * 0.32), z + 0.05))
                ctx.add(st, FIELD, uv="box", uv_scale=2.5, moss=0.45, patches=0.5)
            x += s * r.uniform(0.85, 1.0)
    # Capstones on edge along the top.
    x = -L / 2 + 0.05
    k = 0
    while x < L / 2 - 0.1:
        if ctx.worn and x > L / 2 - 0.6:
            break
        w = r.uniform(0.16, 0.24)
        cap = K.chunk(f"cap{k}", 0.3, r, n=10, flat=0.45)
        K.place(cap, (0, 0, 0), (90, 0, 0))
        K.place(cap, (x + w / 2, 0, H - 0.1))
        ctx.add(cap, FIELD, uv="box", uv_scale=2.5, moss=0.65)
        x += w
        k += 1
    _centre_depth(ctx)


def w4_chapel_lych_gate(ctx: K.Ctx) -> None:
    """The roofed gate into the churchyard: four adzed cedar posts on stone pads, wall plates and tie beams, a
    steep cedar-shingled hood with bargeboards, and a coffin bench along each side inside the posts. The path runs
    through it front to back. Worn: the hood sagging in the middle and furred with moss, a bench board gone."""
    hx, hy = 1.3, 0.8
    post_h = 2.2
    wood = CEDAR if ctx.clean else PINE_OLD
    moss = 0.0 if ctx.clean else 0.5
    for sx in (-1, 1):
        for sy in (-1, 1):
            pad = K.box(f"pad{sx}{sy}", (0.3, 0.3, 0.14), center=(sx * hx, sy * hy, 0.07), bevel=0.03)
            K.noise_disp(pad, 0.01, 5.0, seed=sx * 3 + sy)
            ctx.add(pad, FIELD, uv="box", uv_scale=2.0, moss=0.5)
            _bx(ctx, f"post{sx}{sy}", (0.16, 0.16, post_h - 0.14), (sx * hx, sy * hy, 0.14 + (post_h - 0.14) / 2), wood, bevel=0.012,
                uv_scale=1.5, moss=moss)
            # Braces from post to plate.
            W.bar(ctx, f"brace{sx}{sy}", (sx * hx, sy * (hy - 0.08), post_h - 0.55), (sx * hx, sy * (hy - 0.5), post_h - 0.08),
                  0.08, 0.08, wood)
    for sx in (-1, 1):
        W.bar(ctx, f"plate{sx}", (sx * hx, -hy - 0.25, post_h + 0.06), (sx * hx, hy + 0.25, post_h + 0.06), 0.16, 0.14, wood)
    for sy in (-1, 1):
        W.bar(ctx, f"tie{sy}", (-hx - 0.2, sy * hy, post_h + 0.2), (hx + 0.2, sy * hy, post_h + 0.2), 0.14, 0.14, wood)
    # The hood: ridge along Y (the path), two steep slopes down to eaves past the posts on X.
    ridge_z = 3.2
    eave_x, eave_z = hx + 0.45, post_h + 0.1
    ylen = 2 * hy + 0.9
    sag = 0.12 if ctx.worn else 0.0
    for k, sx in enumerate((-1, 1)):
        sheet = K.quad_sheet(f"roof{k}", (0.0, -ylen / 2, ridge_z), (0.0, ylen / 2, ridge_z), (sx * eave_x, ylen / 2, eave_z),
                             (sx * eave_x, -ylen / 2, eave_z), 6, 4)
        if sag > 0:
            for v in sheet.data.vertices:
                v.co.z -= sag * (1.0 - (2.0 * v.co.y / ylen) ** 2) * (1.0 - abs(v.co.x) / eave_x * 0.5)
        K.solidify(sheet, 0.06, offset=1.0 if sx < 0 else -1.0)
        ctx.add(sheet, "civic_shingle", uv="box", uv_scale=1.0, moss=0.7 if ctx.worn else 0.25)
        for j, sy in enumerate((-1, 1)):
            W.bar(ctx, f"barge{k}{j}", (0.0, sy * (ylen / 2 + 0.02), ridge_z + 0.05), (sx * (eave_x + 0.05), sy * (ylen / 2 + 0.02), eave_z - 0.03),
                  0.22, 0.04, wood, up=(0, 1, 0))
        for j in range(3):
            y = -hy + j * hy
            W.bar(ctx, f"rafter{k}{j}", (0.0, y, ridge_z - 0.06), (sx * (hx + 0.1), y, post_h + 0.24), 0.07, 0.1, wood)
    W.bar(ctx, "ridge", (0, -ylen / 2 - 0.02, ridge_z - 0.02), (0, ylen / 2 + 0.02, ridge_z - 0.02), 0.08, 0.12, wood)
    _bx(ctx, "ridge_cap", (0.14, ylen + 0.06, 0.04), (0, 0, ridge_z + 0.06 - sag), "civic_shingle", bevel=0.0, uv_scale=1.0)
    # Coffin benches inside the posts.
    for k, sx in enumerate((-1, 1)):
        x = sx * (hx - 0.12)
        for j, sy in enumerate((-1, 1)):
            _bx(ctx, f"bench_leg{k}{j}", (0.08, 0.08, 0.42), (x, sy * (hy - 0.25), 0.21), wood)
        n_boards = 1 if (ctx.worn and sx > 0) else 2
        for b in range(n_boards):
            _bx(ctx, f"bench{k}{b}", (0.13, 2 * hy - 0.3, 0.04), (x - sx * 0.07 + sx * b * 0.14, 0, 0.44), wood, bevel=0.004,
                uv_scale=1.5, moss=moss)


def w4_chapel_grave_dug(ctx: K.Ctx) -> None:
    """A freshly dug grave: the dark pit (its walls fall away below the turf) shored with two planks across it, a
    long heap of spoil on its right with the shovel stood in it and the cut turf stacked at its foot. Worn: the spoil
    rained down and threads of white Bloom felt in it."""
    r = ctx.rnd("spoil")
    px, pw, pl = -0.32, 0.8, 2.0
    # The pit: a soil rim that falls to a near-black floor, read as depth from above.
    rim = []
    for k, (a, b) in enumerate([((-pw / 2, -pl / 2), (pw / 2, -pl / 2)), ((pw / 2, -pl / 2), (pw / 2, pl / 2)),
                                 ((pw / 2, pl / 2), (-pw / 2, pl / 2)), ((-pw / 2, pl / 2), (-pw / 2, -pl / 2))]):
        a3 = Vector((a[0] + px, a[1], 0.0))
        b3 = Vector((b[0] + px, b[1], 0.0))
        out = Vector((b3.y - a3.y, -(b3.x - a3.x), 0)).normalized() * 0.18
        s = K.quad_sheet(f"rim{k}", a3 + Vector((0, 0, 0.005)), b3 + Vector((0, 0, 0.005)), b3 + out + Vector((0, 0, 0.09)),
                         a3 + out + Vector((0, 0, 0.09)), 4, 1)
        rim.append(s)
        ctx.add(s, SOIL, uv="box", uv_scale=2.0, ao=True)
    floor = K.box("pit", (pw - 0.02, pl - 0.02, 0.01), center=(px, 0, 0.004))
    ctx.add(floor, "paint_black", uv="box", uv_scale=1.0, ao=False)
    for k, y in enumerate((-0.55, 0.45)):
        W.bar(ctx, f"plank{k}", (px - pw / 2 - 0.2, y, 0.11), (px + pw / 2 + 0.15, y + 0.04, 0.11), 0.22, 0.04, "wood_weathered")
    # The spoil heap along the right side.
    hh = 0.5 if ctx.clean else 0.38
    for k in range(7):
        y = -pl / 2 + 0.15 + k * (pl - 0.3) / 6
        b = K.blob(f"spoil{k}", 0.34, subdiv=2, scale=(0.9, 1.1, hh / 0.34), center=(0.42 + r.uniform(-0.04, 0.04), y, 0.0), rough=0.35,
                   seed=k + 11)
        ctx.add(b, SOIL, uv="box", uv_scale=2.0, smooth=50)
    for k in range(8):
        c = K.chunk(f"clod{k}", r.uniform(0.06, 0.12), r, n=9)
        K.place(c, (r.uniform(0.1, 0.72), r.uniform(-1.1, 1.1), r.uniform(0.02, hh * 0.6)))
        ctx.add(c, SOIL, uv="box", uv_scale=3.0)
    # The shovel stood in the heap.
    W.rod(ctx, "shaft", (0.45, 0.35, 0.3), (0.38, 0.42, 1.25), 0.016, "wood_fresh", segs=8)
    blade = K.box("blade", (0.22, 0.02, 0.28), bevel=0.004)
    K.place(blade, (0, 0, 0), (0, 4, 0))
    K.place(blade, (0.46, 0.34, 0.22))
    ctx.add(blade, "metal_galvanized", uv="box", uv_scale=3.0)
    W.bar(ctx, "grip", (0.31, 0.43, 1.27), (0.45, 0.41, 1.25), 0.03, 0.03, "wood_fresh")
    # The cut turf stacked at the foot.
    for k in range(3):
        t = K.box(f"turf{k}", (0.32, 0.3, 0.07), bevel=0.01)
        K.place(t, (0, 0, 0), (0, 0, r.uniform(-12, 12)))
        K.place(t, (px + r.uniform(-0.05, 0.05), pl / 2 + 0.3, 0.035 + k * 0.07))
        ctx.add(t, TURF if k == 2 else SOIL, uv="box", uv_scale=2.0)
    if ctx.worn:
        _felt(ctx, "felt", 0.42, 0.0, 0.25, 6, ctx.rnd("felt"), spread=0.25, size=0.05, flat=0.3)
    _centre_depth(ctx)


def w4_chapel_bloom_grave(ctx: K.Ctx) -> None:
    """A sunken grave mound broken open by the Bloom: the turf split along the coffin's length, a cushion of white
    felt welling up through it and a troop of pale caps (they glow at night: the def's light). Worn: the felt over
    the whole mound and twice the caps."""
    r = ctx.rnd("bloom")
    mound = K.blob("mound", 0.5, subdiv=3, scale=(0.85, 2.0, 0.25), center=(0, 0, -0.04), rough=0.18, seed=ctx.seed)
    ctx.add(mound, TURF, uv="box", uv_scale=1.5, smooth=50)
    split = K.blob("split", 0.4, subdiv=2, scale=(0.5, 2.0, 0.2), center=(0.05, 0.05, 0.0), rough=0.3, seed=ctx.seed + 1)
    ctx.add(split, SOIL, uv="box", uv_scale=2.0, smooth=50)
    n_felt = 7 if ctx.clean else 12
    _felt(ctx, "felt", 0.05, 0.0, 0.08, n_felt, r, spread=0.3 if ctx.clean else 0.4, size=0.1, flat=0.35)
    for k in range(4 if ctx.clean else 7):
        _caps(ctx, f"troop{k}", r.uniform(-0.25, 0.3), r.uniform(-0.8, 0.8), 0.1, 6, r, spread=0.1, size=1.6)
    _centre_depth(ctx)


def w4_chapel_ivy(ctx: K.Ctx) -> None:
    """Ivy up a wall: woody stems spreading from the ground in a fan and a dense mat of leaf sprays and dark moss
    cushions over them, thickest low down (wall-mounted: origin on the wall plane, everything in front of it).
    Worn: half of it browned off to bare stems."""
    r = ctx.rnd("ivy")
    H, Wd = 2.7, 1.3
    stems = []
    for k in range(7):
        a = (k - 3) / 3.0
        pts = [(a * 0.08, -0.03, 0.0)]
        for j in range(1, 6):
            t = j / 5
            pts.append((a * Wd / 2 * t + r.uniform(-0.06, 0.06), -0.03 - r.uniform(0.0, 0.02), t * H * r.uniform(0.75, 1.0)))
        stems.append(pts)
        W.pole(ctx, f"stem{k}", pts, 0.012, "bark_dead_static", r_end=0.005, seed=k, segs=5)
    keep = 1.0 if ctx.clean else 0.5
    n = 46
    for k in range(n):
        if r.random() > keep:
            continue
        z = H * (r.random() ** 0.8)
        spread = Wd / 2 * (0.35 + 0.65 * z / H)
        x = r.uniform(-spread, spread)
        s = r.uniform(0.28, 0.42)
        yaw = r.uniform(-25, 25)
        tilt = r.uniform(-25, 15)
        card = K.quad_sheet(f"leaf{k}", (-s / 2, 0, -s / 2), (s / 2, 0, -s / 2), (s / 2, 0, s / 2), (-s / 2, 0, s / 2), 1, 1)
        me = card.data
        uvl = me.uv_layers.active
        for li, loop in enumerate(me.loops):
            co = me.vertices[loop.vertex_index].co
            uvl.data[li].uv = (co.x / s + 0.5, co.z / s + 0.5)
        K.place(card, (0, 0, 0), (tilt, 0, yaw))
        K.place(card, (x, -0.06 - r.uniform(0.0, 0.14), max(s / 2, z)))
        ctx.add(card, LEAVES, uv=None, ao=False)
    for k in range(10 if ctx.clean else 5):
        z = r.uniform(0.0, H * 0.6)
        b = K.blob(f"mat{k}", r.uniform(0.1, 0.18), subdiv=1, scale=(1.4, 0.45, 1.0), center=(r.uniform(-0.45, 0.45), -0.06, z), rough=0.4,
                   seed=k)
        ctx.add(b, MOSS, uv="box", uv_scale=2.0, smooth=50)
    # Keep everything in front of the wall plane.
    for o in ctx.parts:
        for v in o.data.vertices:
            if v.co.y > -0.004:
                v.co.y = -0.004
        o.data.update()


def w4_chapel_long_grass(ctx: K.Ctx) -> None:
    """A clump of long churchyard grass gone to seed: crossed blade cards round a dense centre. Worn: thinner,
    flattened to one side."""
    r = ctx.rnd("grass")
    n = 9 if ctx.clean else 6
    for k in range(n):
        a = k / n * math.pi + r.uniform(-0.2, 0.2)
        w = r.uniform(0.6, 0.9)
        h = r.uniform(0.6, 0.85) if ctx.clean else r.uniform(0.45, 0.65)
        cx, cy = r.uniform(-0.25, 0.25), r.uniform(-0.25, 0.25)
        dx, dy = math.cos(a) * w / 2, math.sin(a) * w / 2
        lean = 0.0 if ctx.clean else 0.18
        card = K.quad_sheet(f"blades{k}", (cx - dx, cy - dy, 0.0), (cx + dx, cy + dy, 0.0), (cx + dx + lean, cy + dy, h),
                            (cx - dx + lean, cy - dy, h), 2, 2)
        me = card.data
        uvl = me.uv_layers.active
        for li, loop in enumerate(me.loops):
            co = me.vertices[loop.vertex_index].co
            t = ((co.x - (cx - dx)) * dx + (co.y - (cy - dy)) * dy) / max(1e-6, dx * dx + dy * dy) / 2.0
            uvl.data[li].uv = (t, co.z / h)
        ctx.add(card, GRASS, uv=None, ao=False)


# ============================================================================================
# The Teague vault
# ============================================================================================

def w4_chapel_mausoleum_front(ctx: K.Ctx) -> None:
    """The Teague vault dug into the bank behind the chapel (params w, d, floor, openings: the vault porch's kit
    room): a dressed granite front round the iron door with pilasters, a carved lintel and a pediment; rubble
    stone faces hugging the kit room's other walls; rubble wing walls angled back into the bank; and a cap of
    turf, moss, ferns and two young firs over its roof. Worn: moss and soot streaks down the granite, the turf
    slumped over the cornice."""
    fh = float(ctx.param("floor", 0.6))
    room = O.Room(int(ctx.param("w", 2)), int(ctx.param("d", 6)), fh)
    ops = [tuple(o) for o in ctx.param("openings", [("S", 1, "door")])]
    hw, hd = room.w / 2, room.d / 2
    top = fh + 3.0
    r = ctx.rnd("vault")
    # Rubble faces on N, E, W just outside the kit walls (no openings there).
    for side in ("N", "E", "W"):
        start, along, out = room.side_line(side, 0.12)
        L = room.length(side) + 0.24
        st = start - along * 0.12
        p0, p1 = st, st + along * L
        sheet = K.quad_sheet(f"rubble_{side}", (p0.x, p0.y, 0.0), (p1.x, p1.y, 0.0), (p1.x, p1.y, top + 0.15), (p0.x, p0.y, top + 0.15),
                             max(2, int(L * 2)), 6)
        K.solidify(sheet, 0.18, offset=-1.0 if side in ("N", "E") else 1.0)
        K.noise_disp(sheet, 0.03, 3.0, seed=ctx.seed + len(side))
        ctx.add(sheet, FIELD, uv="box", uv_scale=1.2, moss=0.55, patches=0.6)
    # The granite front on S, centred on the door.
    holes = O.holes_on("S", ops, floor=fh)
    if holes:
        a, b, hz0, hz1 = holes[0]
        door_c = -hw + (a + b) / 2
        door_w = b - a
        door_top = hz1
    else:
        door_c, door_w, door_top = 0.0, 1.0, fh + 2.2
    fy0 = -hd - 0.13
    ft = 0.16
    fw = 3.6
    fx0, fx1 = door_c - fw / 2, door_c + fw / 2
    fz1 = top + 0.3
    # Ashlar courses: wall pieces left and right of the door, and over it.
    for k, (xa, xb, za, zb) in enumerate([(fx0, door_c - door_w / 2, 0.0, fz1), (door_c + door_w / 2, fx1, 0.0, fz1),
                                          (door_c - door_w / 2, door_c + door_w / 2, door_top, fz1)]):
        blk = K.box(f"ashlar{k}", (xb - xa, ft, zb - za), center=((xa + xb) / 2, fy0 - ft / 2, (za + zb) / 2), cuts=(3, 0, 5))
        ctx.add(blk, GRANITE, uv="box", uv_scale=1.0, moss=0.3 if ctx.clean else 0.6, patches=0.6)
    # Door surround: an architrave and a lintel block with a carved panel.
    for k, sx in enumerate((-1, 1)):
        _bx(ctx, f"jamb{k}", (0.14, 0.08, door_top - fh), (door_c + sx * (door_w / 2 + 0.07), fy0 - ft - 0.04, (door_top + fh) / 2), GRANITE,
            bevel=0.01, uv_scale=1.5)
    _bx(ctx, "lintel", (door_w + 0.5, 0.12, 0.34), (door_c, fy0 - ft - 0.06, door_top + 0.17), GRANITE, bevel=0.015, uv_scale=1.5)
    panel = K.box("lintel_panel", (door_w + 0.1, 0.01, 0.2), center=(door_c, fy0 - ft - 0.125, door_top + 0.17))
    ctx.add(panel, ENGRAVE, uv="planar", uv_axis=1, rect=_engrave_rect(7, 200, 330), ao=False)
    # The threshold slab the kit's steps arrive at, and a plinth course.
    _bx(ctx, "plinth", (fw + 0.1, 0.1, 0.3), (door_c, fy0 - ft - 0.05, 0.15), GRANITE, bevel=0.015, uv_scale=1.5)
    # Pilasters at the outer edges.
    for k, x in enumerate((fx0 + 0.15, fx1 - 0.15)):
        _bx(ctx, f"pilaster{k}", (0.3, 0.12, fz1 - 0.3), (x, fy0 - ft - 0.06, 0.3 + (fz1 - 0.3) / 2), GRANITE, bevel=0.012, uv_scale=1.5)
    # Cornice and pediment.
    _bx(ctx, "cornice", (fw + 0.3, 0.3, 0.16), (door_c, fy0 - ft / 2 - 0.05, fz1 + 0.08), GRANITE, bevel=0.02, uv_scale=1.5)
    ped = K.prism("pediment", [(fx0 - 0.1, 0.0), (fx1 + 0.1, 0.0), (door_c, 0.7)], 0.24, plane="XZ", bevel=0.01)
    K.place(ped, (0, fy0 - ft / 2, fz1 + 0.16))
    ctx.add(ped, GRANITE, uv="box", uv_scale=1.5, moss=0.4 if ctx.clean else 0.7)
    # Wing walls angled back into the bank from the facade's ends, their tops falling with the slope.
    for k, (xa, xb) in enumerate([(fx0, fx0 - 0.9), (fx1, fx1 + 0.9)]):
        pts = [(0.0, 0.0), (1.0, 0.0), (1.0, 0.7), (0.0, fz1 - 0.2)]
        wing = K.prism(f"wing{k}", pts, 0.4, plane="XZ")
        d = Vector((xb - xa, 2.4, 0.0))
        K.place(wing, (0, 0, 0), (0, 0, 0))
        # Stretch the unit outline along the wing's run, then turn it to run from (xa, fy0) back into the bank.
        K.place(wing, (0, 0, 0), None, (d.length, 1.0, 1.0))
        ang = math.degrees(math.atan2(d.y, d.x))
        K.place(wing, (0, 0, 0), (0, 0, ang))
        K.place(wing, (xa, fy0 - 0.1, 0.0))
        K.noise_disp(wing, 0.025, 3.0, seed=ctx.seed + k)
        ctx.add(wing, FIELD, uv="box", uv_scale=1.2, moss=0.6)
    # The turf cap over the roof, spilling over the rubble faces and the cornice.
    cap = K.blob("turf_cap", 1.0, subdiv=3, scale=(hw + 0.9, hd + 0.9, 0.95), center=(door_c * 0.3, 0.3, top + 0.05), rough=0.25,
                 seed=ctx.seed)
    for v in cap.data.vertices:
        if v.co.z < top - 0.05:
            v.co.z = top - 0.05 + (v.co.z - top + 0.05) * 0.15
    ctx.add(cap, TURF, uv="box", uv_scale=0.8, smooth=50)
    for k in range(9):
        b = K.blob(f"moss{k}", r.uniform(0.2, 0.35), subdiv=1, scale=(1.5, 1.2, 0.4),
                   center=(r.uniform(-hw - 0.5, hw + 0.5), r.uniform(-hd, hd + 0.5), top + 0.5 + r.uniform(0, 0.25)), rough=0.4, seed=k)
        ctx.add(b, MOSS, uv="box", uv_scale=1.5, smooth=50)
    # Ferns (crossed leaf cards) and two young firs on the cap.
    for k in range(8):
        cx, cy = r.uniform(-hw - 0.4, hw + 0.4), r.uniform(-hd + 0.3, hd + 0.4)
        cz = top + 0.55 + r.uniform(0.0, 0.3)
        for j in range(2):
            a = j * math.pi / 2 + r.uniform(0, 0.5)
            s = 0.6
            dx, dy = math.cos(a) * s / 2, math.sin(a) * s / 2
            card = K.quad_sheet(f"fern{k}{j}", (cx - dx, cy - dy, cz - 0.05), (cx + dx, cy + dy, cz - 0.05), (cx + dx, cy + dy, cz + 0.5),
                                (cx - dx, cy - dy, cz + 0.5), 1, 1)
            me = card.data
            uvl = me.uv_layers.active
            for li, loop in enumerate(me.loops):
                c = me.vertices[loop.vertex_index].co
                uvl.data[li].uv = (((c.x - cx) * dx + (c.y - cy) * dy) / (s * s / 4) * 0.5 + 0.5, (c.z - cz + 0.05) / 0.55)
            ctx.add(card, "fern", uv=None, ao=False)
    for k, (fx, fyy) in enumerate([(-hw - 0.2, hd - 0.4), (hw + 0.3, 0.6)]):
        h = 1.6 + k * 0.5
        trunk = K.cyl(f"fir_trunk{k}", 0.05, h, segs=7, center=(fx, fyy, top + 0.5 + h / 2), r_top=0.015)
        ctx.add(trunk, "bark_grey_fir_static", uv="box", uv_scale=1.0, smooth=40)
        for j in range(4):
            zz = top + 0.8 + j * h / 5
            rr_ = 0.55 * (1 - j / 4) + 0.12
            cone = K.cyl(f"fir_tier{k}{j}", rr_, 0.45, segs=8, center=(fx, fyy, zz + 0.2), r_top=0.02)
            K.noise_disp(cone, 0.04, 4.0, seed=k * 10 + j)
            ctx.add(cone, "moss_mound" if ctx.worn else "sphagnum_green", uv="box", uv_scale=2.0, smooth=40)
    if ctx.worn:
        for k in range(6):
            st = K.quad_sheet(f"streak{k}", (0, 0, 0), (0.12, 0, 0), (0.12, 0, 1.6), (0, 0, 1.6), 1, 3)
            x = r.uniform(fx0 + 0.3, fx1 - 0.3)
            if abs(x - door_c) < door_w / 2 + 0.2:
                continue
            K.place(st, (x, fy0 - ft - 0.004, fz1 - 1.7))
            ctx.add(st, "rock_moss", uv="box", uv_scale=2.0, ao=False)


def w4_chapel_coffin(ctx: K.Ctx) -> None:
    """A six-sided pine coffin on two stone blocks, its lid nailed down with square nails, the long axis front to
    back. Worn: the lid levered off and lying askew across it, a shroud inside, white Bloom felt along the seams."""
    wood = PINE if ctx.clean else PINE_OLD
    outline = [(-0.18, -0.98), (0.18, -0.98), (0.31, 0.45), (0.22, 0.98), (-0.22, 0.98), (-0.31, 0.45)]
    for k, y in enumerate((-0.62, 0.62)):
        blk = K.box(f"block{k}", (0.5, 0.24, 0.12), center=(0, y, 0.06), bevel=0.02)
        K.noise_disp(blk, 0.008, 6.0, seed=k)
        ctx.add(blk, STONE, uv="box", uv_scale=2.0)
    z0, z1 = 0.12, 0.52
    body = K.prism("body", outline, z1 - z0, plane="XY", offset=z0)
    K.delete_faces(body, lambda c, n: n.z > 0.9)
    K.solidify(body, 0.025, offset=-1.0)
    ctx.add(body, wood, uv="box", uv_scale=1.5, long_axis=1, moss=0.0 if ctx.clean else 0.3)
    lid = K.prism("lid", outline, 0.035, plane="XY", offset=0.0, bevel=0.004)
    if ctx.clean:
        K.place(lid, (0, 0, z1))
        for k, (x, y) in enumerate([(-0.15, -0.9), (0.15, -0.9), (-0.27, 0.45), (0.27, 0.45), (-0.2, 0.9), (0.2, 0.9)]):
            _cy(ctx, f"nail{k}", 0.007, 0.006, (x, y, z1 + 0.037), "wild_cast_iron", segs=4)
    else:
        K.place(lid, (0, 0, 0), (0, -9, 24))
        K.place(lid, (0.18, 0.05, z1 + 0.03))
        shroud = K.blob("shroud", 0.25, subdiv=2, scale=(0.85, 3.2, 0.5), center=(0, 0.05, z0 + 0.1), rough=0.2, seed=ctx.seed)
        ctx.add(shroud, LINEN, uv="box", uv_scale=2.0, smooth=50)
        _felt(ctx, "seam", 0.0, 0.0, z1 - 0.02, 7, ctx.rnd("felt"), spread=0.25, size=0.04, flat=0.3)
    ctx.add(lid, wood, uv="box", uv_scale=1.5, long_axis=1)
    _centre_depth(ctx)


def w4_chapel_crypt_niche(ctx: K.Ctx) -> None:
    """A wall of dressed limestone in the vault with two round-arched burial niches one above the other (the
    lower floor 0.32 m up, the upper 1.22 m: the def's bed anchors), a linen shroud laid flat in each, a lettered
    granite ledge under each and a plinth. Worn: the shrouds stained and Bloom felt in the joints."""
    Wd, H, D = 2.2, 2.2, 0.85
    hd = D / 2
    back_t = 0.12
    open_w = 1.86
    pier = (Wd - open_w) / 2
    # Back slab and piers.
    _bx(ctx, "back", (Wd, back_t, H), (0, hd - back_t / 2, H / 2), STONE, bevel=0.01, uv_scale=1.0)
    for k, sx in enumerate((-1, 1)):
        _bx(ctx, f"pier{k}", (pier, D - back_t, H), (sx * (Wd / 2 - pier / 2), -back_t / 2, H / 2), STONE, bevel=0.012, uv_scale=1.0)
    # Floors: plinth, the divider (upper niche floor) and the head slab.
    for k, (za, zb) in enumerate([(0.0, 0.32), (1.1, 1.22), (2.02, H)]):
        _bx(ctx, f"slab{k}", (open_w, D - back_t, zb - za), (0, -back_t / 2, (za + zb) / 2), STONE, bevel=0.008, uv_scale=1.0)
    # Arched heads of each niche: a spandrel prism over each opening's top.
    for k, (z_floor, z_top) in enumerate([(0.32, 1.1), (1.22, 2.02)]):
        rise = 0.28
        spring = z_top - rise
        pts = [(-open_w / 2, spring), (-open_w / 2, z_top), (open_w / 2, z_top), (open_w / 2, spring)]
        for i in range(1, 12):
            a = math.pi * i / 12
            pts.append((open_w / 2 * math.cos(a), spring + rise * math.sin(a)))
        spandrel = K.prism(f"spandrel{k}", pts, 0.12, plane="XZ")
        K.place(spandrel, (0, -hd + 0.06, 0))
        ctx.add(spandrel, STONE, uv="box", uv_scale=1.0, moss=0.0 if ctx.clean else 0.3)
        ledge = K.box(f"ledge{k}", (open_w - 0.1, 0.012, 0.09), center=(0, -hd - 0.004, z_floor - 0.06))
        ctx.add(ledge, ENGRAVE, uv="planar", uv_axis=1, rect=_engrave_rect(4 if k else 0, 190, 300), ao=False)
        # A shroud laid flat along the niche floor.
        sh = K.box(f"shroud{k}", (1.7, D - back_t - 0.2, 0.02), center=(0, -0.05, z_floor + 0.012), bevel=0.008, cuts=(6, 2, 0))
        K.noise_disp(sh, 0.008, 5.0, seed=ctx.seed + k)
        ctx.add(sh, LINEN, uv="box", uv_scale=2.0, smooth=50, ao=True)
    if ctx.worn:
        rr = ctx.rnd("felt")
        for k in range(10):
            x = rr.choice((-1, 1)) * rr.uniform(0.85, 0.95)
            b = K.blob(f"felt{k}", 0.035, subdiv=1, scale=(0.6, 0.6, 1.6), center=(x, -hd + 0.02, rr.uniform(0.1, 2.0)), rough=0.3, seed=k)
            ctx.add(b, "bloom_felt", uv="box", uv_scale=3.0, ao=False)
    _centre_depth(ctx)


def w4_chapel_silver_chest(ctx: K.Ctx) -> None:
    """An iron-bound oak chest with a hasp and a padlock, the church silver inside: a chalice, a paten, two
    candlesticks and the alms dish on a purple cloth. Worn: the lid thrown up, the cloth pulled back."""
    Wd, D, H = 1.0, 0.56, 0.48
    hd = D / 2
    oak = "civic_oak_dark"
    body = K.box("body", (Wd, D, H), center=(0, 0, H / 2), bevel=0.01)
    if ctx.worn:
        K.delete_faces(body, lambda c, n: n.z > 0.9)
        K.solidify(body, 0.03, offset=-1.0)
    ctx.add(body, oak, uv="box", uv_scale=1.5, patches=0.6)
    for k, x in enumerate((-0.38, 0.0, 0.38)):
        band = K.box(f"band{k}", (0.05, D + 0.012, H + 0.006), center=(x, 0, H / 2), bevel=0.002)
        if ctx.worn:
            K.delete_faces(band, lambda c, n: n.z > 0.9)
        ctx.add(band, "wild_cast_iron", uv="box", uv_scale=3.0)
    for k, sx in enumerate((-1, 1)):
        h = K.tube(f"handle{k}", [(sx * (Wd / 2 + 0.01), -0.06, H * 0.62), (sx * (Wd / 2 + 0.06), -0.06, H * 0.55),
                                  (sx * (Wd / 2 + 0.06), 0.06, H * 0.55), (sx * (Wd / 2 + 0.01), 0.06, H * 0.62)], 0.008, segs=5)
        ctx.add(h, "wild_cast_iron", uv="box", uv_scale=4.0, smooth=40)
    lid_t = 0.06
    lid = K.box("lid", (Wd + 0.02, D + 0.02, lid_t), center=(0, -(D + 0.02) / 2, lid_t / 2), bevel=0.012)
    hinge_y = hd - 0.02
    if ctx.worn:
        K.place(lid, (0, 0, 0), (-92, 0, 0))
        K.place(lid, (0, hinge_y - lid_t, H))
    else:
        K.place(lid, (0, hinge_y + 0.01, H))
        hasp = K.box("hasp", (0.06, 0.012, 0.12), center=(0, -hd - 0.008, H - 0.03))
        ctx.add(hasp, "wild_cast_iron", uv="box", uv_scale=4.0)
        lock = K.box("padlock", (0.06, 0.025, 0.07), center=(0, -hd - 0.025, H - 0.11), bevel=0.008)
        ctx.add(lock, "civic_brass", uv="box", uv_scale=4.0)
    ctx.add(lid, oak, uv="box", uv_scale=1.5, patches=0.6)
    if ctx.worn:
        cloth = K.box("cloth", (Wd - 0.12, D - 0.12, 0.03), center=(0, 0, H - 0.12), bevel=0.01, cuts=(4, 3, 0))
        K.noise_disp(cloth, 0.012, 5.0, seed=ctx.seed)
        ctx.add(cloth, "civic_felt_red", uv="box", uv_scale=2.0, smooth=50)
        cup = K.lathe("chalice", [(0.0, 0.0), (0.05, 0.0), (0.045, 0.01), (0.012, 0.03), (0.01, 0.1), (0.04, 0.12), (0.055, 0.2),
                                  (0.05, 0.2), (0.035, 0.13), (0.0, 0.125)], segs=14)
        K.place(cup, (-0.22, -0.02, H - 0.105))
        ctx.add(cup, SILVER, uv="box", uv_scale=4.0, smooth=40)
        paten = K.cyl("paten", 0.09, 0.01, segs=16, center=(0.12, 0.05, H - 0.1))
        ctx.add(paten, SILVER, uv="box", uv_scale=4.0, smooth=40)
        for k, x in enumerate((0.3, 0.38)):
            cs = K.lathe(f"stick{k}", [(0.0, 0.0), (0.035, 0.0), (0.01, 0.03), (0.008, 0.2), (0.025, 0.21), (0.0, 0.22)], segs=10)
            K.place(cs, (0, 0, 0), (90, 0, 10 + k * 15))
            K.place(cs, (x - 0.1, -0.12 + k * 0.1, H - 0.08))
            ctx.add(cs, SILVER, uv="box", uv_scale=4.0, smooth=40)
    _centre_depth(ctx)


def w4_chapel_reliquary(ctx: K.Ctx) -> None:
    """A little gilt-bronze house-shaped casket on a limestone pedestal: a moulded base and cap on the pedestal,
    the casket's walls on four feet, a pitched lid with a cresting and a cross on its ridge, a crystal window in its
    front. Worn: the gilt rubbed through to bronze, the window clouded, felt at the pedestal's foot."""
    _bx(ctx, "base", (0.5, 0.42, 0.1), (0, 0, 0.05), STONE, bevel=0.015, uv_scale=1.5)
    _bx(ctx, "shaft", (0.38, 0.3, 0.72), (0, 0, 0.46), STONE, bevel=0.01, uv_scale=1.5)
    _bx(ctx, "cap", (0.5, 0.42, 0.08), (0, 0, 0.86), STONE, bevel=0.015, uv_scale=1.5)
    metal = GILT if ctx.clean else BRONZE
    z = 0.9
    for sx in (-1, 1):
        for sy in (-1, 1):
            f = K.blob(f"foot{sx}{sy}", 0.02, subdiv=1, center=(sx * 0.17, sy * 0.08, z + 0.015))
            ctx.add(f, metal, uv="box", uv_scale=4.0, smooth=40)
    _bx(ctx, "casket", (0.4, 0.2, 0.17), (0, 0, z + 0.03 + 0.085), metal, bevel=0.006, uv_scale=3.0)
    roof = K.prism("roof", [(-0.11, 0.0), (0.11, 0.0), (0.0, 0.1)], 0.42, plane="YZ", bevel=0.003)
    K.place(roof, (0, 0, z + 0.2))
    ctx.add(roof, metal, uv="box", uv_scale=3.0)
    win = K.box("window", (0.16, 0.006, 0.09), center=(0, -0.103, z + 0.115))
    ctx.add(win, "glass_clear" if ctx.clean else "glass_brown", uv="box", uv_scale=3.0, ao=False)
    _bx(ctx, "cross_up", (0.012, 0.012, 0.1), (0, 0, z + 0.35), metal, bevel=0.0)
    _bx(ctx, "cross_bar", (0.06, 0.012, 0.012), (0, 0, z + 0.37), metal, bevel=0.0)
    for k in range(5):
        x = -0.16 + k * 0.08
        g = K.blob(f"crest{k}", 0.012, subdiv=1, center=(x, 0, z + 0.305))
        ctx.add(g, metal, uv="box", uv_scale=4.0, smooth=40)
    if ctx.worn:
        _felt(ctx, "felt", 0.0, 0.0, 0.02, 5, ctx.rnd("felt"), spread=0.18, size=0.05, flat=0.3)
    _centre_depth(ctx)


BUILDERS = {
    "w4_chapel_pew": w4_chapel_pew,
    "w4_chapel_pulpit": w4_chapel_pulpit,
    "w4_chapel_altar": w4_chapel_altar,
    "w4_chapel_bell_fallen": w4_chapel_bell_fallen,
    "w4_chapel_headstone": w4_chapel_headstone,
    "w4_chapel_headstone_cross": w4_chapel_headstone_cross,
    "w4_chapel_headstone_tablet": w4_chapel_headstone_tablet,
    "w4_chapel_iron_railing": w4_chapel_iron_railing,
    "w4_chapel_iron_railing_gate": w4_chapel_iron_railing_gate,
    "w4_chapel_mausoleum_front": w4_chapel_mausoleum_front,
    "w4_chapel_coffin": w4_chapel_coffin,
    "w4_chapel_crypt_niche": w4_chapel_crypt_niche,
    "w4_chapel_lych_gate": w4_chapel_lych_gate,
    "w4_chapel_grave_dug": w4_chapel_grave_dug,
    "w4_chapel_bloom_grave": w4_chapel_bloom_grave,
    "w4_chapel_ivy": w4_chapel_ivy,
    "w4_chapel_long_grass": w4_chapel_long_grass,
    "w4_chapel_silver_chest": w4_chapel_silver_chest,
    "w4_chapel_reliquary": w4_chapel_reliquary,
    "w4_chapel_stone_wall": w4_chapel_stone_wall,
}


def build(params: dict, outputs: list[str]) -> None:
    K.run(params, outputs, BUILDERS)
