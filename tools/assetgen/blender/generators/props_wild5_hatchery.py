"""Wilderness set pieces, round 5: props of the Silver Run fish hatchery (w5_fish_hatchery), a state trout hatchery on a
forest creek the Cordon used as a water-testing post.

The shed: 5 m concrete raceway sections (still water and dead trout, or white Bloom felt wall to wall), the headbox
along their heads, the posts and top plates of the open-sided shed, a feed cart and a tote of dead fish. The hatch house:
vertical-flow incubator stacks, an aluminium hatching trough, the water chiller, pallets of feed and the Cordon's sample
board and sample coolers. The creek: the intake weir with its piers and the abutment the catwalk ladder leans on, the
raised weir pool behind it, the creek bed below, the intake pipe, the headgate stand and the Cordon's automatic sampler
on the catwalk, and the catwalk's pipe railing. The yard: the carved trout sign, the fish stocking truck and the feed
silo.

Conventions (docs/ASSET_PIPELINE.md): metres, Z up, front -Y, origin bottom centre; floor props have their depth centred
on the origin (PoiBuilder's collision box is the def's size centred there). The sample board hangs with its origin on the
wall plane (bottom centre, reaching out toward -Y). The weir's front (-Y) is downstream; its origin is the centre of the
wall's footprint (the creek runs over local x -4 .. +2, the abutment is +2 .. +4). The sampler's hose drops below its
origin into the pool (it stands on the catwalk 3 m up). 'clean' is the hatchery the week the Cordon came, 'worn' after
the Bloom, 'destroyed' (the incubators) pulled apart.
"""
from __future__ import annotations

import math

from mathutils import Vector

from lib import props_ext_kit as K
from lib import props_ext_parts as P
from lib import props_wild_parts as W

CONC = "concrete"
CONC_OLD = "mine_concrete"
WATER = "farm_trough_water"
CREEK = "road_water_film"
GALV = "metal_galvanized"
ALU = "road_alu"
STEEL = "road_steel"
DARK = "road_steel_dark"
RUST = "road_rust"
TROUT = "w5_hatchery_trout"
FELT = "bloom_felt"
CAPS = "bloom_caps"
GREEN = "road_paint_green"
TYRE = "tyre_rubber"
GLASS = "window_grime"
STONE = "stone_river"
GRAVEL = "out_gravel"
MOSS = "moss_ground"


def _bx(ctx, name, size, center, mat, *, bevel=0.006, uv_scale=2.0, cuts=(0, 0, 0), **kw):
    return ctx.add(K.box(name, size, center=center, bevel=bevel, cuts=cuts), mat, uv="box", uv_scale=uv_scale, **kw)


def _cy(ctx, name, r, h, center, mat, *, axis="Z", segs=12, r_top=None, uv_scale=2.0, **kw):
    o = K.cyl(name, r, h, segs=segs, center=center, axis=axis, r_top=r_top)
    return ctx.add(o, mat, uv="box", uv_scale=uv_scale, smooth=40, **kw)


def _sheet(ctx, name, x0, x1, y0, y1, z, mat, *, nx=1, ny=1, uv_scale=1.0, **kw):
    """A flat horizontal sheet (water surface) at height z."""
    o = K.grid(name, x1 - x0, y1 - y0, nx, ny, center=((x0 + x1) / 2, (y0 + y1) / 2, z))
    return ctx.add(o, mat, uv="planar", uv_axis=2, uv_scale=uv_scale, smooth=None, ao=False, **kw)


def _trout(ctx, name, length, at, rotz, *, belly_up=True, furred=False, r=None):
    """A dead trout: an elongated body, a forked tail and a dorsal fin, lying on its side or belly up."""
    L = length
    body = K.blob(f"{name}_body", 0.5, subdiv=2, scale=(L, L * 0.19, L * 0.24), rough=0.05, seed=sum(ord(ch) for ch in name) % 997)
    K.taper(body, 0, lambda x: 1.0 - 0.55 * max(0.0, x / (L * 0.5)) ** 2)
    tail = K.prism(f"{name}_tail", [(0.0, 0.0), (L * 0.2, L * 0.1), (L * 0.16, 0.0), (L * 0.2, -L * 0.1)], L * 0.012, plane="XZ")
    K.place(tail, (L * 0.42, 0, 0))
    fin = K.prism(f"{name}_fin", [(-L * 0.08, 0.0), (L * 0.06, 0.0), (-L * 0.02, L * 0.08)], L * 0.01, plane="XZ")
    K.place(fin, (0, 0, L * 0.1))
    parts = [body, tail, fin]
    rot = (90 if not belly_up else 180, 0, rotz)
    for o in parts:
        K.place(o, (0, 0, 0), rot)
        K.place(o, at)
    ctx.add(K.merge_parts(parts, name), TROUT, uv="box", uv_scale=4.0, smooth=50, ao=False,
            patches=0.6 if furred else 0.2)
    if furred and r is not None:
        _felt(ctx, f"{name}_fur", at[0], at[1], at[2] + L * 0.08, 2, r, spread=L * 0.25, size=L * 0.12, flat=0.4)


def _felt(ctx, name, cx, cy, z, n, r, *, spread=0.3, size=0.07, flat=0.35):
    """Cushions of white Bloom felt."""
    for k in range(n):
        x = cx + r.uniform(-spread, spread)
        y = cy + r.uniform(-spread, spread)
        b = K.blob(f"{name}{k}", size * r.uniform(0.6, 1.3), subdiv=1, scale=(1.4, 1.2, flat), center=(x, y, z), rough=0.35,
                   seed=k + 3)
        ctx.add(b, FELT, uv="box", uv_scale=3.0, smooth=50, ao=False)


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
        cap = K.lathe(f"{name}_cap{k}", [(0.0, h + cr * 0.55), (cr * 0.55, h + cr * 0.45), (cr, h + cr * 0.05),
                                         (cr * 0.9, h - cr * 0.1), (0.0, h - 0.002)], segs=8)
        for o in (stem, cap):
            K.place(o, (0, 0, 0), lean)
            K.place(o, (x, y, z))
        ctx.add(stem, FELT, uv="box", uv_scale=4.0, smooth=40, ao=False)
        ctx.add(cap, CAPS, uv="box", uv_scale=4.0, smooth=40, ao=False)


def _felt_mat(ctx, name, x0, x1, y0, y1, z, r, *, n=10):
    """A mat of Bloom felt over a water surface: a lumpy sheet plus cushions and cap troops along its edges."""
    nx, ny = max(2, int((x1 - x0) / 0.25)), max(2, int((y1 - y0) / 0.25))
    o = K.grid(name, x1 - x0, y1 - y0, nx, ny, center=((x0 + x1) / 2, (y0 + y1) / 2, z))
    K.map_verts(o, lambda v: Vector((v.x, v.y, v.z + 0.025 * math.sin(v.x * 7.1 + v.y * 3.3) + 0.02 * math.sin(v.y * 9.7))))
    ctx.add(o, FELT, uv="planar", uv_axis=2, uv_scale=1.0, smooth=40, ao=False)
    for k in range(n):
        cx, cy = r.uniform(x0 + 0.1, x1 - 0.1), r.uniform(y0 + 0.1, y1 - 0.1)
        _felt(ctx, f"{name}_c{k}", cx, cy, z + 0.03, 2, r, spread=0.15, size=0.1, flat=0.45)
    for k in range(4):
        side = x0 + 0.08 if k % 2 == 0 else x1 - 0.08
        _caps(ctx, f"{name}_caps{k}", side, r.uniform(y0 + 0.3, y1 - 0.3), z + 0.02, 5, r, spread=0.15, size=1.2)


# ============================================================================================
# The raceway shed
# ============================================================================================

def w5_hatchery_raceway(ctx: K.Ctx) -> None:
    """A 5 m raceway section: 0.15 m walls with a chamfered cap round a 1.5 m channel, keyway slots for dam boards at
    both ends and a screen frame at the tail. Clean: still green water to within 0.12 m of the cap, trout belly up along
    the screen. Worn: white Bloom felt from wall to wall, caps along the walls."""
    Wd, L, H, t = 1.8, 5.0, 0.9, 0.15
    r = ctx.rnd("raceway")
    for sx in (-1, 1):
        x = sx * (Wd / 2 - t / 2)
        _bx(ctx, f"wall{sx}", (t, L, H - 0.03), (x, 0, (H - 0.03) / 2), CONC, bevel=0.012, uv_scale=1.0, patches=0.7,
            low=0.5, low_h=0.6, moss=0.15 if ctx.worn else 0.0)
        _bx(ctx, f"cap{sx}", (t + 0.02, L, 0.03), (x, 0, H - 0.015), CONC, bevel=0.01, uv_scale=1.0, patches=0.5)
        for sy in (-1, 1):
            # Keyway slots: a steel channel set in the wall at each end.
            _bx(ctx, f"key{sx}{sy}", (0.04, 0.06, H - 0.1), (sx * (Wd / 2 - t - 0.01), sy * (L / 2 - 0.12), H / 2), GALV,
                bevel=0.003, patches=0.4)
    _bx(ctx, "floor", (Wd - 2 * t, L, 0.08), (0, 0, 0.04), CONC, bevel=0.0, uv_scale=1.0)
    # Dam boards at the head, the screen at the tail (-Y is downstream).
    for k in range(3):
        _bx(ctx, f"board{k}", (Wd - 2 * t, 0.04, 0.18), (0, L / 2 - 0.12, 0.14 + k * 0.2), "wood_weathered", bevel=0.004,
            uv_scale=1.0, moss=0.2)
    fr = []
    for x in (-(Wd / 2 - t), Wd / 2 - t):
        fr.append(((x, -L / 2 + 0.12, 0.1), (x, -L / 2 + 0.12, H - 0.05)))
    fr.append(((-(Wd / 2 - t), -L / 2 + 0.12, H - 0.08), (Wd / 2 - t, -L / 2 + 0.12, H - 0.08)))
    for a, b in fr:
        W.rod(ctx, ctx.uid("frame"), a, b, 0.015, GALV, segs=6)
    for k in range(9):
        x = -(Wd / 2 - t) + (k + 1) * (Wd - 2 * t) / 10
        W.rod(ctx, f"screen{k}", (x, -L / 2 + 0.12, 0.1), (x, -L / 2 + 0.12, H - 0.1), 0.004, STEEL, segs=4, ao=False)
    wz = H - 0.12
    _sheet(ctx, "water", -(Wd / 2 - t), Wd / 2 - t, -L / 2, L / 2, wz, WATER, uv_scale=0.5)
    if ctx.worn:
        _felt_mat(ctx, "felt", -(Wd / 2 - t) + 0.01, Wd / 2 - t - 0.01, -L / 2 + 0.2, L / 2 - 0.25, wz + 0.01, r, n=12)
        for k in range(3):
            _trout(ctx, f"trout_w{k}", 0.3, (r.uniform(-0.4, 0.4), -L / 2 + 0.25 + k * 0.12, wz + 0.03), r.uniform(-30, 30),
                   furred=True, r=r)
    else:
        for k in range(9):
            near_screen = k < 6
            y = -L / 2 + 0.25 + r.uniform(0, 0.4) if near_screen else r.uniform(-1.5, 2.0)
            _trout(ctx, f"trout{k}", r.uniform(0.22, 0.34), (r.uniform(-0.55, 0.55), y, wz + 0.02), r.uniform(0, 360),
                   belly_up=k % 3 != 0)


def w5_hatchery_headbox(ctx: K.Ctx) -> None:
    """The headbox: a 9 m concrete channel 0.7 m deep along the shed's head wall, a galvanised cover in sections, three
    gate valves with handwheels at x = -3, 0, +3 and splash boards down the front into the raceways. Worn: one cover
    section off, felt in the channel."""
    L, D, H = 9.0, 0.7, 1.1
    r = ctx.rnd("headbox")
    _bx(ctx, "back", (L, 0.15, H), (0, D / 2 - 0.075, H / 2), CONC, bevel=0.01, uv_scale=1.0, patches=0.6)
    _bx(ctx, "front", (L, 0.15, H - 0.15), (0, -D / 2 + 0.075, (H - 0.15) / 2), CONC, bevel=0.01, uv_scale=1.0, patches=0.6,
        low=0.5, low_h=0.4)
    for sx in (-1, 1):
        _bx(ctx, f"end{sx}", (0.15, D, H), (sx * (L / 2 - 0.075), 0, H / 2), CONC, bevel=0.01, uv_scale=1.0)
    _sheet(ctx, "water", -L / 2 + 0.15, L / 2 - 0.15, -D / 2 + 0.15, D / 2 - 0.15, H - 0.3, WATER, uv_scale=0.5)
    for k in range(6):
        x0 = -L / 2 + 0.15 + k * (L - 0.3) / 6
        x1 = x0 + (L - 0.3) / 6 - 0.02
        if ctx.worn and k == 2:
            _felt_mat(ctx, f"felt{k}", x0, x1, -D / 2 + 0.16, D / 2 - 0.16, H - 0.29, r, n=4)
            cov = K.box(f"cover{k}", (x1 - x0, D - 0.1, 0.02), center=(0, 0, 0))
            K.place(cov, (0, 0, 0), (0, 70, 0))
            K.place(cov, ((x0 + x1) / 2, -D / 2 - 0.5, 0.36))
            ctx.add(cov, GALV, uv="box", uv_scale=2.0, patches=0.6)
            continue
        _bx(ctx, f"cover{k}", (x1 - x0, D - 0.1, 0.02), ((x0 + x1) / 2, 0, H + 0.01), GALV, bevel=0.002, patches=0.5)
    for k, x in enumerate((-3.0, 0.0, 3.0)):
        # The gate valve's spout down the front, and its handwheel on a stem above the cover.
        _bx(ctx, f"spout{k}", (0.5, 0.18, 0.06), (x, -D / 2 - 0.09, H - 0.35), CONC, bevel=0.01)
        _bx(ctx, f"splash{k}", (0.5, 0.03, 0.55), (x, -D / 2 - 0.05, H - 0.65), "wood_weathered", bevel=0.004, moss=0.3)
        W.rod(ctx, f"stem{k}", (x, -0.1, H - 0.2), (x, -0.1, H + 0.35), 0.02, STEEL, segs=6)
        ring = W.ring_obj(f"wheel{k}", 0.13, 0.15, 0.025, segs=16)
        K.place(ring, (x, -0.1, H + 0.35))
        ctx.add(ring, "road_paint_red", uv_scale=4.0, smooth=40)
        for j in range(3):
            a = j * math.tau / 3
            W.rod(ctx, f"spoke{k}{j}", (x, -0.1, H + 0.35), (x + math.cos(a) * 0.14, -0.1 + math.sin(a) * 0.14, H + 0.35), 0.008,
                  "road_paint_red", segs=4)
    scoop = K.lathe("scoop", [(0.0, 0.0), (0.08, 0.01), (0.09, 0.12)], segs=10, cap_top=False)
    K.place(scoop, (1.4, 0.1, H + 0.02), (90, 0, 20))
    ctx.add(scoop, ALU, uv="box", uv_scale=3.0, smooth=40)
    W.rod(ctx, "scoop_handle", (1.4, 0.1, H + 0.06), (1.75, 0.0, H + 0.06), 0.012, ALU, segs=6)


def w5_hatchery_shed_post(ctx: K.Ctx) -> None:
    """A creosoted 0.18 m post from the pony wall's foot to the eave, a 0.2 m top plate a metre each way along the wall
    and two knee braces. Worn: one brace split off and hanging."""
    H = 2.65
    _bx(ctx, "post", (0.18, 0.18, H), (0, 0, H / 2), "wood_creosote", bevel=0.01, uv_scale=1.0, patches=0.5, low=0.4,
        low_h=0.8)
    _bx(ctx, "plate", (2.0, 0.18, 0.2), (0, 0, H + 0.1), "wood_creosote", bevel=0.01, uv_scale=1.0, patches=0.4)
    for sx in (-1, 1):
        if ctx.worn and sx > 0:
            W.bar(ctx, "brace_hang", (0.1, 0, H - 0.05), (0.18, 0.08, H - 0.75), 0.1, 0.08, "wood_creosote", bevel=0.005)
            continue
        W.bar(ctx, f"brace{sx}", (sx * 0.08, 0, H - 0.55), (sx * 0.62, 0, H - 0.01), 0.1, 0.08, "wood_creosote", up=(0, 1, 0),
              bevel=0.005)
    W.bolts(ctx, "bolts", [((sx * 0.35, -0.091, H + 0.1), (0, -1, 0)) for sx in (-1, 1)] + [((0, -0.091, H - 0.3), (0, -1, 0))],
            DARK, r=0.015)


def w5_hatchery_intake_pipe(ctx: K.Ctx) -> None:
    """A 2.8 m run of 0.6 m riveted steel pipe along X on two concrete saddles: a bellmouth with a bar screen at the
    dam end (-X), a gate valve with a handwheel on a stand, a flange at the headbox end (+X). Worn: rust, the screen
    choked with leaves and white growth."""
    L, R, zc = 2.8, 0.3, 0.45
    mat = RUST if ctx.worn else "road_paint_green"
    W.rod(ctx, "pipe", (-L / 2 + 0.35, 0, zc), (L / 2 - 0.05, 0, zc), R, mat, segs=16, uv_scale=1.0)
    bell = K.lathe("bell", [(R, 0.0), (R * 1.15, 0.12), (R * 1.35, 0.3)], segs=16, cap_bottom=False, cap_top=False)
    K.place(bell, (0, 0, 0), (0, -90, 0))
    K.place(bell, (-L / 2 + 0.35, 0, zc))
    ctx.add(bell, mat, uv="box", uv_scale=1.0, smooth=40)
    for k in range(7):
        y = -R * 1.2 + k * R * 2.4 / 6
        W.rod(ctx, f"bar{k}", (-L / 2 + 0.06, y, zc - R * 1.2), (-L / 2 + 0.06, y, zc + R * 1.2), 0.012, DARK, segs=4)
    for x in (L / 2 - 0.08, -0.1):
        ring = W.ring_obj(f"flange{x}", R, R + 0.05, 0.05, segs=16)
        K.place(ring, (0, 0, 0), (0, 90, 0))
        K.place(ring, (x, 0, zc))
        ctx.add(ring, mat, uv_scale=2.0, smooth=40)
    W.bolts(ctx, "rivets", [((x, math.cos(a) * (R + 0.003), zc + math.sin(a) * (R + 0.003)), (0, math.cos(a), math.sin(a)))
                            for x in (-0.6, 0.5) for a in [j * math.tau / 12 for j in range(12)]], mat, r=0.01)
    for k, x in enumerate((-0.75, 0.85)):
        sad = K.prism(f"saddle{k}", [(-0.35, 0.0), (0.35, 0.0), (0.35, zc - R * 0.6), (0.2, zc - R * 0.2), (-0.2, zc - R * 0.2),
                                     (-0.35, zc - R * 0.6)], 0.3, plane="YZ")
        K.place(sad, (x, 0, 0))
        ctx.add(sad, CONC, uv="box", uv_scale=1.0, patches=0.6, moss=0.3)
    # The gate valve: a body on the pipe, a stem and a handwheel.
    _cy(ctx, "valve", 0.2, 0.3, (0.2, 0, zc + R + 0.05), DARK, segs=10)
    W.rod(ctx, "valve_stem", (0.2, 0, zc + R + 0.2), (0.2, 0, zc + R + 0.4), 0.02, STEEL, segs=6)
    wheel = W.ring_obj("valve_wheel", 0.16, 0.18, 0.025, segs=16)
    K.place(wheel, (0.2, 0, zc + R + 0.4))
    ctx.add(wheel, "road_paint_red" if ctx.clean else RUST, uv_scale=3.0, smooth=40)
    if ctx.worn:
        r = ctx.drnd("leaves")
        for k in range(6):
            lf = K.blob(f"leaf{k}", 0.08, subdiv=1, scale=(1.6, 1.0, 0.3), center=(-L / 2 + 0.02, r.uniform(-0.3, 0.3), zc + r.uniform(-0.3, 0.2)),
                        rough=0.4, seed=k)
            ctx.add(lf, "fen_leaves", uv="box", uv_scale=3.0, smooth=40, ao=False)
        _felt(ctx, "screen_felt", -L / 2 + 0.03, 0, zc - 0.2, 4, r, spread=0.25, size=0.08)


def w5_hatchery_fish_tote(ctx: K.Ctx) -> None:
    """A grey 1 m fish tote on a pallet, a dip net across it, full of dead trout in melted ice. Worn: the fish furred
    white, spores on the rim and the pallet."""
    r = ctx.rnd("tote")
    for k in range(3):
        _bx(ctx, f"stringer{k}", (1.1, 0.08, 0.1), (0, -0.4 + k * 0.4, 0.05), "wood_weathered", bevel=0.005, uv_scale=1.0)
    for k in range(7):
        _bx(ctx, f"deck{k}", (0.12, 0.9, 0.022), (-0.5 + k * 1.0 / 6, 0, 0.111), "wood_weathered", bevel=0.003, uv_scale=1.0)
    t = 0.04
    base = 0.122
    h = 0.6
    _bx(ctx, "tote_floor", (1.0, 0.8, t), (0, 0, base + t / 2), "plastic_grey", bevel=0.01)
    for sx in (-1, 1):
        _bx(ctx, f"tote_x{sx}", (t, 0.8, h), (sx * (0.5 - t / 2), 0, base + h / 2), "plastic_grey", bevel=0.01, patches=0.4)
        _bx(ctx, f"tote_y{sx}", (1.0, t, h), (0, sx * (0.4 - t / 2), base + h / 2), "plastic_grey", bevel=0.01, patches=0.4)
    _sheet(ctx, "melt", -0.46, 0.46, -0.36, 0.36, base + h - 0.15, "road_water_grey")
    for k in range(10):
        _trout(ctx, f"fish{k}", r.uniform(0.24, 0.34), (r.uniform(-0.3, 0.3), r.uniform(-0.22, 0.22), base + h - 0.13 + (k % 3) * 0.03),
               r.uniform(0, 360), belly_up=k % 2 == 0, furred=ctx.worn and k % 2 == 0, r=r)
    # The dip net: a long handle across the tote and its hoop.
    W.rod(ctx, "net_handle", (-0.75, -0.3, base + h + 0.03), (0.4, 0.25, base + h + 0.02), 0.014, ALU, segs=6)
    hoop = W.ring_obj("net_hoop", 0.2, 0.215, 0.012, segs=16)
    K.place(hoop, (0.55, 0.32, base + h + 0.02))
    ctx.add(hoop, ALU, uv_scale=3.0, smooth=40)
    net = K.lathe("net", [(0.2, 0.0), (0.14, -0.12), (0.0, -0.16)], segs=12, cap_top=False, cap_bottom=False)
    K.place(net, (0.55, 0.32, base + h + 0.02))
    ctx.add(net, "out_net", uv="box", uv_scale=3.0, smooth=40, ao=False)
    if ctx.worn:
        _caps(ctx, "rim_caps", 0.48, -0.3, base + h, 6, r, spread=0.1)
        _felt(ctx, "pallet_felt", -0.45, 0.35, 0.13, 3, r, spread=0.1, size=0.06)


def w5_hatchery_feed_cart(ctx: K.Ctx) -> None:
    """A galvanised two-wheeled feed cart: a hopper of pellets with a hinged lid, handles at the back (+Y), a caster at
    the front, a scoop on a chain. Worn: the lid off, the feed caked green."""
    r = ctx.rnd("cart")
    zb = 0.35
    hop = K.prism("hopper", [(-0.55, 0.0), (0.55, 0.0), (0.6, 0.65), (-0.6, 0.65)], 0.7, plane="YZ")
    K.place(hop, (0, 0, zb))
    ctx.add(hop, GALV, uv="box", uv_scale=2.0, patches=0.5)
    feed = K.grid("feed", 0.68, 1.15, 6, 8, center=(0, 0, zb + 0.6))
    K.map_verts(feed, lambda v: Vector((v.x, v.y, v.z + 0.03 * math.sin(v.y * 9.0) * math.cos(v.x * 7.0))))
    ctx.add(feed, "farm_grain" if ctx.clean else "moss_ground", uv="planar", uv_axis=2, uv_scale=2.0, smooth=40, ao=False)
    if ctx.clean:
        lid = K.box("lid", (0.72, 0.6, 0.02), center=(0, 0, 0))
        K.place(lid, (0, 0, 0), (-80, 0, 0))
        K.place(lid, (0, 0.62, zb + 0.95))
        ctx.add(lid, GALV, uv="box", uv_scale=2.0, patches=0.5)
    for sx in (-1, 1):
        t = P.tyre(f"wheel{sx}", 0.2, 0.12, 0.07, segs=14)
        K.place(t, (sx * 0.42, 0.25, 0.2))
        ctx.add(t, TYRE, uv_scale=2.0, smooth=40)
        W.rod(ctx, f"handle{sx}", (sx * 0.3, 0.55, zb + 0.5), (sx * 0.3, 0.68, zb + 0.75), 0.016, STEEL, segs=6)
    W.rod(ctx, "axle", (-0.42, 0.25, 0.2), (0.42, 0.25, 0.2), 0.018, DARK, segs=6)
    W.rod(ctx, "grip", (-0.3, 0.68, zb + 0.75), (0.3, 0.68, zb + 0.75), 0.018, "road_rubber", segs=8)
    W.rod(ctx, "caster_leg", (0, -0.45, zb), (0, -0.45, 0.1), 0.02, STEEL, segs=6)
    cw = P.tyre("caster", 0.08, 0.05, 0.04, segs=10)
    K.place(cw, (0, -0.45, 0.08))
    ctx.add(cw, TYRE, uv_scale=3.0, smooth=40)
    scoop = K.lathe("scoop", [(0.0, 0.0), (0.07, 0.01), (0.08, 0.1)], segs=10, cap_top=False)
    K.place(scoop, (0, 0, 0), (100, 0, 0))
    K.place(scoop, (0.38, -0.2, zb + 0.4))
    ctx.add(scoop, ALU, uv="box", uv_scale=3.0, smooth=40)
    ch = W.chain_obj("scoop_chain", [(0.36, -0.15, zb + 0.62), (0.4, -0.2, zb + 0.5)], link=0.03, wire=0.003)
    ctx.add(ch, STEEL, uv_scale=4.0, ao=False)
    if ctx.worn:
        _felt(ctx, "feed_mould", 0, 0, zb + 0.62, 4, r, spread=0.25, size=0.07)


# ============================================================================================
# The hatch house
# ============================================================================================

def w5_hatchery_incubator_stack(ctx: K.Ctx) -> None:
    """A vertical-flow incubator: eight green fibreglass trays in a stainless frame (front -Y), the supply pipe and
    valve on top, a drain spout and pan at the foot. Worn: furred trays, the water off. Destroyed: the frame racked
    over and half the trays out on the floor."""
    r = ctx.rnd("inc")
    Wd, D, H = 0.66, 0.6, 1.85
    lean = 0.0
    frame = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            frame.append(((sx * Wd / 2, sy * D / 2, 0.0), (sx * Wd / 2 + lean, sy * D / 2, H - 0.1)))
    for z in (0.12, H - 0.12):
        for sy in (-1, 1):
            frame.append(((-Wd / 2, sy * D / 2, z), (Wd / 2, sy * D / 2, z)))
    for a, b in frame:
        W.bar(ctx, ctx.uid("frame"), a, b, 0.03, 0.03, "furn_steel_stainless", bevel=0.003)
    _bx(ctx, "pan", (Wd + 0.04, D + 0.04, 0.08), (0, 0, 0.04), "furn_steel_stainless", bevel=0.004)
    n = 8
    out_trays = {2, 5, 6} if ctx.destroyed else set()
    for k in range(n):
        z = 0.18 + k * 0.19
        if k in out_trays:
            fz = 0.02 + len([j for j in out_trays if j < k]) * 0.07
            tray = K.box(f"tray{k}", (Wd - 0.06, D - 0.04, 0.07), center=(0, 0, 0.035), bevel=0.008)
            K.place(tray, (0, 0, 0), (r.uniform(-8, 8), r.uniform(-8, 8), r.uniform(-40, 40)))
            K.place(tray, (r.uniform(-0.25, 0.25), -D / 2 - 0.45 - r.uniform(0, 0.25), fz))
            ctx.add(tray, "road_plastic_green", uv="box", uv_scale=2.0, patches=0.6)
            continue
        _bx(ctx, f"tray{k}", (Wd - 0.06, D - 0.04, 0.08), (0, 0.0, z), "road_plastic_green", bevel=0.008, patches=0.4)
        _bx(ctx, f"lip{k}", (Wd - 0.1, 0.02, 0.03), (0, -D / 2 + 0.01, z), "road_plastic_green", bevel=0.004)
        if ctx.worn and k % 2 == 0:
            _felt(ctx, f"tray_felt{k}", 0, -D / 2 + 0.03, z + 0.03, 2, r, spread=0.18, size=0.04, flat=0.5)
    W.rod(ctx, "supply", (-Wd / 2 - 0.05, D / 2 - 0.08, H - 0.05), (Wd / 2 + 0.05, D / 2 - 0.08, H - 0.05), 0.025, "plastic_white", segs=8)
    W.rod(ctx, "drop", (0.15, D / 2 - 0.08, H - 0.05), (0.15, 0.1, H - 0.2), 0.02, "plastic_white", segs=8)
    _cy(ctx, "valve", 0.03, 0.08, (0.15, D / 2 - 0.08, H + 0.0), "road_paint_blue", segs=8)
    W.rod(ctx, "spout", (0.0, -D / 2, 0.12), (0.0, -D / 2 - 0.12, 0.08), 0.025, "plastic_white", segs=8)


def w5_hatchery_hatch_trough(ctx: K.Ctx) -> None:
    """A 3 m aluminium hatching trough (long along Y) on a steel stand: four perforated baskets, a supply pipe and valve
    at the head (+Y), a standpipe drain at the foot. Worn: the baskets empty and filmed white, a sample jar in one."""
    r = ctx.rnd("trough")
    L, Wd, zt, h = 3.0, 0.7, 0.62, 0.3
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.bar(ctx, f"leg{sx}{sy}", (sx * 0.3, sy * 1.35, 0.0), (sx * 0.3, sy * 1.35, zt), 0.04, 0.04, STEEL, bevel=0.003)
        W.bar(ctx, f"rail{sx}", (sx * 0.3, -1.35, 0.2), (sx * 0.3, 1.35, 0.2), 0.04, 0.03, STEEL, bevel=0.003)
    _bx(ctx, "bottom", (Wd, L, 0.02), (0, 0, zt + 0.01), ALU, bevel=0.002)
    for sx in (-1, 1):
        _bx(ctx, f"side{sx}", (0.02, L, h), (sx * (Wd / 2 - 0.01), 0, zt + h / 2), ALU, bevel=0.003, patches=0.4)
    for sy in (-1, 1):
        _bx(ctx, f"end{sy}", (Wd, 0.02, h), (0, sy * (L / 2 - 0.01), zt + h / 2), ALU, bevel=0.003)
    _sheet(ctx, "water", -Wd / 2 + 0.02, Wd / 2 - 0.02, -L / 2 + 0.02, L / 2 - 0.02, zt + h - 0.06, WATER, uv_scale=0.6)
    for k in range(4):
        y = -L / 2 + 0.38 + k * 0.74
        _bx(ctx, f"basket{k}", (Wd - 0.08, 0.64, 0.02), (0, y, zt + h - 0.12), "furn_steel_stainless", bevel=0.002)
        for sx in (-1, 1):
            _bx(ctx, f"basket_rim{k}{sx}", (Wd - 0.08, 0.015, 0.14), (0, y + sx * 0.32, zt + h - 0.06), "furn_steel_stainless", bevel=0.0)
        if ctx.worn:
            _felt(ctx, f"film{k}", 0, y, zt + h - 0.1, 2, r, spread=0.2, size=0.05, flat=0.3)
    W.rod(ctx, "supply", (0, L / 2 + 0.05, zt + h + 0.25), (0, L / 2 - 0.2, zt + h + 0.1), 0.02, "plastic_white", segs=8)
    W.rod(ctx, "riser", (0, L / 2 + 0.05, 0.0), (0, L / 2 + 0.05, zt + h + 0.25), 0.02, "plastic_white", segs=8)
    W.rod(ctx, "standpipe", (0.2, -L / 2 + 0.1, zt), (0.2, -L / 2 + 0.1, zt + h - 0.05), 0.025, "plastic_white", segs=8)
    if ctx.worn:
        jar = K.lathe("jar", [(0.0, 0.0), (0.04, 0.0), (0.04, 0.1), (0.03, 0.12), (0.0, 0.12)], segs=10)
        K.place(jar, (-0.15, 0.4, zt + h - 0.11))
        ctx.add(jar, "glass_clear", uv="box", uv_scale=3.0, smooth=40, ao=False)


def w5_hatchery_results_board(ctx: K.Ctx) -> None:
    """The Cordon's sampling grid on a whiteboard (origin on the wall plane, bottom centre): an aluminium frame, ruled
    lines, red crosses in nearly every square, a pen tray. Worn: the bottom rows smeared away."""
    Wd, H, T = 1.2, 0.9, 0.02
    _bx(ctx, "board", (Wd, T, H), (0, -T / 2, H / 2), "plastic_white", bevel=0.002, patches=0.2)
    for z in (0.0, H):
        _bx(ctx, f"frame_h{z}", (Wd + 0.02, 0.03, 0.025), (0, -0.015, z), ALU, bevel=0.003)
    for x in (-Wd / 2, Wd / 2):
        _bx(ctx, f"frame_v{x}", (0.025, 0.03, H), (x, -0.015, H / 2), ALU, bevel=0.003)
    rows, cols = 6, 8
    for i in range(rows + 1):
        z = 0.08 + i * (H - 0.16) / rows
        _bx(ctx, f"rule_h{i}", (Wd - 0.12, 0.002, 0.005), (0, -T - 0.001, z), "road_paint_black", bevel=0.0, ao=False)
    for j in range(cols + 1):
        x = -Wd / 2 + 0.06 + j * (Wd - 0.12) / cols
        _bx(ctx, f"rule_v{j}", (0.005, 0.002, H - 0.16), (x, -T - 0.001, H / 2), "road_paint_black", bevel=0.0, ao=False)
    r = ctx.rnd("crosses")
    for i in range(rows):
        if ctx.worn and i < 2:
            continue
        for j in range(cols):
            if r.random() < 0.18:
                continue
            cx = -Wd / 2 + 0.06 + (j + 0.5) * (Wd - 0.12) / cols
            cz = 0.08 + (i + 0.5) * (H - 0.16) / rows
            for s in (-1, 1):
                b = K.box(f"x{i}{j}{s}", (0.07, 0.002, 0.007))
                K.place(b, (0, 0, 0), (0, s * 45, 0))
                K.place(b, (cx, -T - 0.002, cz))
                ctx.add(b, "road_paint_red", uv="box", uv_scale=4.0, ao=False)
    _bx(ctx, "tray", (0.5, 0.06, 0.015), (0.2, -T - 0.03, 0.01), ALU, bevel=0.002)
    W.rod(ctx, "marker", (0.05, -T - 0.035, 0.03), (0.17, -T - 0.035, 0.03), 0.008, "plastic_red", segs=6)


def w5_hatchery_chiller(ctx: K.Ctx) -> None:
    """A packaged water chiller (back +Y on the wall): a louvred grey cabinet, two condenser fans on top, insulated
    supply and return lines up the wall to the ceiling, a dial thermometer and a red isolator. Worn: a fan guard off,
    the lines sweating rust."""
    Wd, D, H = 1.6, 0.9, 1.45
    _bx(ctx, "cabinet", (Wd, D - 0.1, H), (0, -0.05, H / 2), "road_paint_grey", bevel=0.01, patches=0.5, low=0.3)
    for k in range(10):
        _bx(ctx, f"louvre{k}", (Wd - 0.3, 0.02, 0.03), (-0.1, -D / 2 - 0.0, 0.25 + k * 0.1), DARK, bevel=0.002)
    for k, x in enumerate((-0.4, 0.4)):
        _cy(ctx, f"fan_ring{k}", 0.3, 0.12, (x, -0.05, H + 0.06), "road_paint_grey", segs=16)
        if not (ctx.worn and k == 1):
            guard = W.ring_obj(f"guard{k}", 0.24, 0.28, 0.01, segs=16)
            K.place(guard, (x, -0.05, H + 0.125))
            ctx.add(guard, DARK, uv_scale=3.0, smooth=40)
            for j in range(4):
                a = j * math.pi / 4
                W.rod(ctx, f"guard_bar{k}{j}", (x - math.cos(a) * 0.27, -0.05 - math.sin(a) * 0.27, H + 0.125),
                      (x + math.cos(a) * 0.27, -0.05 + math.sin(a) * 0.27, H + 0.125), 0.005, DARK, segs=4)
        for j in range(3):
            bl = K.box(f"blade{k}{j}", (0.22, 0.06, 0.008))
            K.place(bl, (0, 0, 0), (12, 0, j * 120))
            K.place(bl, (x + math.cos(j * math.tau / 3) * 0.11, -0.05 + math.sin(j * math.tau / 3) * 0.11, H + 0.1))
            ctx.add(bl, DARK, uv="box", uv_scale=3.0)
    pipe_mat = RUST if ctx.worn else "plastic_black"
    for k, x in enumerate((0.55, 0.7)):
        W.rod(ctx, f"line{k}", (x, D / 2 - 0.1, 0.6), (x, D / 2 - 0.1, H + 0.3), 0.05, pipe_mat, segs=10)
        W.rod(ctx, f"line_up{k}", (x, D / 2 - 0.1, H + 0.3), (x, D / 2 - 0.05, 2.6), 0.05, pipe_mat, segs=10)
    _cy(ctx, "dial", 0.06, 0.03, (-0.65, -D / 2 - 0.0, H - 0.25), "plastic_white", axis="Y", segs=14)
    _bx(ctx, "isolator", (0.18, 0.12, 0.24), (0.6, -D / 2 + 0.0, H - 0.35), "road_paint_red", bevel=0.01)
    _bx(ctx, "plinth", (Wd + 0.06, D - 0.04, 0.08), (0, -0.04, 0.04), CONC, bevel=0.01)


def w5_hatchery_sample_cooler(ctx: K.Ctx) -> None:
    """Three white sample coolers stacked, strapped and taped with chain-of-custody labels. Worn: the top one open and
    empty, its ice packs on the floor."""
    for k in range(3):
        z = k * 0.3
        _bx(ctx, f"cooler{k}", (0.62, 0.42, 0.26), (0, 0, z + 0.13), "plastic_white", bevel=0.02, patches=0.3)
        _bx(ctx, f"lid{k}", (0.64, 0.44, 0.04), (0, 0, z + 0.28), "plastic_white", bevel=0.015)
        _bx(ctx, f"label{k}", (0.18, 0.002, 0.1), (0.1, -0.212, z + 0.14), "road_paper_yellow", bevel=0.0, ao=False)
        for sx in (-1, 1):
            _bx(ctx, f"handle{k}{sx}", (0.03, 0.14, 0.03), (sx * 0.325, 0, z + 0.22), "plastic_black", bevel=0.005)
        _bx(ctx, f"tape{k}", (0.65, 0.445, 0.02), (-0.2, 0, z + 0.2), "road_paint_orange", bevel=0.0, ao=False)
    if ctx.worn:
        # The top cooler's lid swung open; ice packs on the floor.
        for o in [p for p in ctx.parts if p.name.startswith("lid2")]:
            K.place(o, (0, -0.22, -0.88))
            K.place(o, (0, 0, 0), (-100, 0, 0))
            K.place(o, (0, 0.22, 0.88))
        r = ctx.drnd("ice")
        for k in range(3):
            _bx(ctx, f"icepack{k}", (0.15, 0.1, 0.03), (r.uniform(-0.3, 0.3), -0.35 + r.uniform(-0.05, 0.05), 0.015),
                "plastic_blue", bevel=0.01)


def w5_hatchery_feed_pallet(ctx: K.Ctx) -> None:
    """A pallet of 20 kg feed sacks six courses high, stretch-wrapped. Worn: the wrap slit, the top sacks torn and the
    pellets spilled."""
    r = ctx.rnd("pallet")
    for k in range(3):
        _bx(ctx, f"stringer{k}", (1.2, 0.08, 0.1), (0, -0.42 + k * 0.42, 0.05), "wood_weathered", bevel=0.005, uv_scale=1.0)
    for k in range(7):
        _bx(ctx, f"deck{k}", (0.13, 1.0, 0.022), (-0.54 + k * 1.08 / 6, 0, 0.111), "wood_weathered", bevel=0.003, uv_scale=1.0)
    z = 0.122
    courses = 5 if ctx.worn else 6
    for c in range(courses):
        for j in range(3):
            along_x = (c % 2 == 0)
            if along_x:
                size, cen = (1.15, 0.31, 0.16), (r.uniform(-0.02, 0.02), -0.33 + j * 0.33, z + 0.08)
            else:
                size, cen = (0.37, 0.95, 0.16), (-0.38 + j * 0.38, r.uniform(-0.02, 0.02), z + 0.08)
            b = K.box(f"sack{c}{j}", size, center=(0, 0, 0), bevel=0.05, bevel_segs=2)
            K.place(b, cen, (0, 0, r.uniform(-2, 2)))
            ctx.add(b, "farm_feed_sack", uv="box", uv_scale=1.0, smooth=35, patches=0.3)
        z += 0.165
    if ctx.worn:
        for k in range(2):
            torn = K.box(f"torn{k}", (0.5, 0.3, 0.1), center=(0, 0, 0), bevel=0.04)
            K.place(torn, (-0.2 + k * 0.4, 0.1 - k * 0.2, z + 0.05), (r.uniform(-10, 10), r.uniform(-10, 10), r.uniform(0, 60)))
            ctx.add(torn, "farm_feed_sack", uv="box", uv_scale=1.0, smooth=35, patches=0.6)
        spill = K.blob("spill", 0.3, subdiv=2, scale=(1.4, 1.0, 0.12), center=(0.35, -0.65, 0.0), rough=0.3, seed=4)
        ctx.add(spill, "farm_grain", uv="box", uv_scale=3.0, smooth=40, ao=False)
    else:
        wrap = K.box("wrap", (1.19, 0.99, z - 0.13), center=(0, 0, (z + 0.13) / 2))
        ctx.add(wrap, "road_bag_clear", uv="box", uv_scale=1.0, smooth=None, ao=False)


# ============================================================================================
# The creek: the weir, the pool, the creek bed, the intake, the catwalk's fittings
# ============================================================================================

CREST = 1.0
DECK = 2.95


def w5_hatchery_dam(ctx: K.Ctx) -> None:
    """The intake weir (front -Y downstream): a 1 m concrete weir wall across the creek (x -4 .. +2) with water sheeting
    over its crest onto a stone apron, a west wing pier, a middle pier and the east abutment block (x +2 .. +4, the full
    2.95 m) carrying the POI's kit catwalk on a concrete beam, the intake gate's slot in the abutment and two steel legs
    under the catwalk's landing over the bank (x +2 .. +4, y -0.5 .. -1.5). Worn: moss and white film on the lip."""
    r = ctx.rnd("dam")
    moss = 0.5 if ctx.worn else 0.25
    _bx(ctx, "weir", (6.0, 1.0, CREST), (-1.0, 0, CREST / 2), CONC_OLD, bevel=0.02, uv_scale=1.0, patches=0.7, moss=moss,
        cuts=(6, 0, 0))
    _bx(ctx, "crest", (6.0, 0.4, 0.06), (-1.0, -0.2, CREST + 0.03), CONC_OLD, bevel=0.015, uv_scale=1.0, moss=moss)
    for x, w in ((-3.85, 0.3), (-1.0, 0.4)):
        _bx(ctx, f"pier{x}", (w, 1.0, DECK), (x, 0, DECK / 2), CONC_OLD, bevel=0.02, uv_scale=1.0, patches=0.6, moss=moss * 0.6)
        nose = K.prism(f"nose{x}", [(-w / 2, 0.0), (w / 2, 0.0), (0.0, 0.3)], DECK - 0.4, plane="XY")
        K.place(nose, (x, 0.5, 0.0))
        ctx.add(nose, CONC_OLD, uv="box", uv_scale=1.0, moss=moss)
    _bx(ctx, "abutment", (2.0, 1.0, DECK), (3.0, 0, DECK / 2), CONC_OLD, bevel=0.02, uv_scale=1.0, patches=0.6, moss=moss * 0.5,
        cuts=(2, 0, 3))
    _bx(ctx, "beam", (6.0, 0.6, 0.3), (-1.0, 0, DECK - 0.15), CONC_OLD, bevel=0.015, uv_scale=1.0, patches=0.5)
    # The intake gate in the abutment's upstream face: a steel frame and the gate leaf, the stem up to the deck.
    _bx(ctx, "gate_frame", (0.9, 0.1, 1.3), (2.6, 0.52, 0.65), DARK, bevel=0.01, patches=0.6)
    _bx(ctx, "gate_leaf", (0.7, 0.06, 0.9), (2.6, 0.56, 0.55), RUST if ctx.worn else "road_paint_grey", bevel=0.005)
    W.rod(ctx, "gate_stem", (2.6, 0.56, 1.0), (2.6, 0.56, DECK), 0.025, STEEL, segs=6)
    # Water: a sheet over the crest and down the downstream face, the splash at the foot.
    falls = []
    for k in range(5):
        x0 = -4.0 + 0.1 + k * 5.8 / 5
        x1 = x0 + 5.8 / 5 - 0.05
        if x0 < -1.25 < x1 or x0 < -0.75 < x1:
            continue
        pts = [(-0.0, CREST + 0.06), (-0.5, CREST + 0.05), (-0.62, CREST - 0.1), (-0.66, 0.4), (-0.7, 0.05)]
        rings = [[(x0, y, z), (x1, y, z)] for y, z in pts]
        o = K.loft(f"fall{k}", rings, closed_ring=False, cap_start=False, cap_end=False)
        ctx.add(o, CREEK, uv="box", uv_scale=1.0, smooth=40, ao=False)
        falls.append(o)
    for k in range(10):
        foam = K.blob(f"foam{k}", 0.12, subdiv=1, scale=(2.0, 1.0, 0.25), center=(r.uniform(-3.8, 1.8), -0.8 + r.uniform(-0.1, 0.1), 0.04),
                      rough=0.4, seed=k)
        ctx.add(foam, "plastic_white", uv="box", uv_scale=2.0, smooth=40, ao=False)
    # The apron of placed stone below the weir.
    for k in range(26):
        st = K.chunk(f"apron{k}", r.uniform(0.18, 0.32), r, flat=0.45)
        K.place(st, (r.uniform(-3.9, 1.9), -0.6 - r.uniform(0.0, 0.9), 0.02))
        ctx.add(st, STONE, uv="box", uv_scale=2.0, smooth=30, moss=0.4)
    # The landing's legs and the stringer under the catwalk's bank end.
    for x in (2.1, 3.92):
        W.bar(ctx, f"leg{x}", (x, -1.42, 0.0), (x, -1.42, DECK - 0.02), 0.1, 0.1, GALV, bevel=0.004, patches=0.5)
        _bx(ctx, f"footing{x}", (0.35, 0.35, 0.15), (x, -1.42, 0.075), CONC, bevel=0.02)
    W.bar(ctx, "stringer", (2.0, -1.42, DECK - 0.08), (4.0, -1.42, DECK - 0.08), 0.1, 0.15, GALV, bevel=0.004)
    for x in (2.1, 3.92):
        W.bar(ctx, f"joist{x}", (x, -0.5, DECK - 0.08), (x, -1.47, DECK - 0.08), 0.08, 0.15, GALV, bevel=0.004)
    if ctx.worn:
        _felt(ctx, "lip_felt", -2.0, -0.15, CREST + 0.06, 6, r, spread=1.2, size=0.08, flat=0.3)
    ctx.ground_clamp = True


def w5_hatchery_weir_pool(ctx: K.Ctx) -> None:
    """The pool behind the weir: water held at 0.9 m between dry-laid stone banks (the creek over x -1.5 .. +1.5, banks
    out to +-3), fed over a boulder riffle at the back (+Y). Collision none. Worn: white scum in the corners."""
    r = ctx.rnd("pool")
    L, Wd, zw = 7.0, 6.0, 0.9
    _sheet(ctx, "water", -2.5, 2.5, -L / 2, L / 2, zw, WATER, nx=4, ny=4, uv_scale=0.4)
    _bx(ctx, "bed", (5.0, L, zw - 0.15), (0, 0, (zw - 0.15) / 2), "out_earth", bevel=0.0, uv_scale=1.0)
    for sx in (-1, 1):
        for k in range(9):
            y = -L / 2 + 0.4 + k * (L - 0.8) / 8
            for j in range(2):
                st = K.chunk(f"bank{sx}{k}{j}", r.uniform(0.3, 0.45), r, flat=0.7)
                K.place(st, (sx * (2.55 + j * 0.3 + r.uniform(-0.05, 0.05)), y + r.uniform(-0.2, 0.2), 0.25 + j * 0.45))
                ctx.add(st, STONE, uv="box", uv_scale=2.0, smooth=30, moss=0.5)
        _bx(ctx, f"bank_fill{sx}", (0.9, L, zw + 0.05), (sx * 2.85, 0, (zw + 0.05) / 2), "out_earth", bevel=0.05, uv_scale=1.0,
            moss=0.7)
    for k in range(12):
        st = K.chunk(f"riffle{k}", r.uniform(0.3, 0.5), r, flat=0.6)
        K.place(st, (r.uniform(-2.3, 2.3), L / 2 - 0.3 + r.uniform(-0.2, 0.2), zw - 0.1 + r.uniform(0.0, 0.4)))
        ctx.add(st, STONE, uv="box", uv_scale=2.0, smooth=30, moss=0.6)
    for k in range(4):
        lp = K.blob(f"lily{k}", 0.2, subdiv=1, scale=(1.4, 1.0, 0.05), center=(r.uniform(-2.0, 2.0), r.uniform(-2.5, 2.5), zw + 0.01),
                    rough=0.2, seed=k)
        ctx.add(lp, "fen_plants", uv="box", uv_scale=2.0, smooth=40, ao=False)
    if ctx.worn:
        for k in range(4):
            cx, cy = (-2.2 if k % 2 else 2.2), (-3.0 if k < 2 else 3.0)
            _felt(ctx, f"scum{k}", cx, cy, zw + 0.01, 3, r, spread=0.3, size=0.12, flat=0.15)


def w5_hatchery_creek(ctx: K.Ctx) -> None:
    """8 m of shallow creek (along Y): a water ribbon 3 m wide over a cobble bed, gravel bars and mossy stones along both
    banks out to +-3 m, a snag. Collision none: walked through. Worn: white spore scum in the eddies."""
    r = ctx.rnd("creek")
    L = 8.0
    wob = lambda y: 0.25 * math.sin(y * 0.8 + ctx.seed % 7)  # noqa: E731
    o = K.grid("water", 3.0, L, 6, 16, center=(0, 0, 0.06))
    K.map_verts(o, lambda v: Vector((v.x + wob(v.y), v.y, v.z)))
    ctx.add(o, CREEK, uv="planar", uv_axis=2, uv_scale=0.5, smooth=None, ao=False)
    bed = K.grid("bed", 3.4, L, 6, 16, center=(0, 0, 0.02))
    K.map_verts(bed, lambda v: Vector((v.x + wob(v.y), v.y, v.z)))
    ctx.add(bed, GRAVEL, uv="planar", uv_axis=2, uv_scale=1.0, smooth=None)
    for sx in (-1, 1):
        bank = K.grid(f"bank{sx}", 1.4, L, 3, 16, center=(sx * 2.25, 0, 0.03))
        K.map_verts(bank, lambda v, s=sx: Vector((v.x + wob(v.y), v.y, v.z + 0.06 * (abs(v.x) - 1.55) * s * s)))
        ctx.add(bank, GRAVEL if sx < 0 else MOSS, uv="planar", uv_axis=2, uv_scale=1.0, smooth=None, moss=0.4)
        for k in range(14):
            y = -L / 2 + 0.3 + k * (L - 0.6) / 13 + r.uniform(-0.2, 0.2)
            st = K.chunk(f"stone{sx}{k}", r.uniform(0.12, 0.3), r, flat=0.55)
            K.place(st, (sx * (1.55 + r.uniform(-0.1, 0.6)) + wob(y), y, 0.03))
            ctx.add(st, STONE, uv="box", uv_scale=2.0, smooth=30, moss=0.5)
    for k in range(8):
        y = r.uniform(-L / 2 + 0.5, L / 2 - 0.5)
        st = K.chunk(f"cobble{k}", r.uniform(0.1, 0.18), r, flat=0.5)
        K.place(st, (r.uniform(-1.0, 1.0) + wob(y), y, 0.03))
        ctx.add(st, STONE, uv="box", uv_scale=2.0, smooth=30, moss=0.3)
    W.add_log(ctx, "snag", 2.2, 0.09, ctx.seed, at=(1.2, r.uniform(-2.5, 2.5), 0.08), rot=(0, 0, 35 + r.uniform(-15, 15)), moss=0.6)
    if ctx.worn:
        for k in range(5):
            y = r.uniform(-L / 2 + 0.5, L / 2 - 0.5)
            _felt(ctx, f"scum{k}", (1.3 if k % 2 else -1.3) + wob(y), y, 0.07, 3, r, spread=0.25, size=0.1, flat=0.12)


def w5_hatchery_headgate(ctx: K.Ctx) -> None:
    """The headgate's lifting stand: a cast-iron pedestal on a base plate, a geared head with a handwheel and the
    threaded stem through the deck. Worn: the wheel chained and padlocked."""
    _bx(ctx, "plate", (0.5, 0.5, 0.03), (0, 0, 0.015), "wild_cast_iron", bevel=0.005)
    ped = K.lathe("pedestal", [(0.16, 0.03), (0.11, 0.12), (0.08, 0.7), (0.12, 0.8), (0.12, 0.92), (0.0, 0.92)], segs=12)
    ctx.add(ped, "wild_cast_iron_rust" if ctx.worn else "wild_cast_iron", uv="box", uv_scale=2.0, smooth=40, patches=0.6)
    W.rod(ctx, "stem", (0, 0, 0.92), (0, 0, 1.28), 0.025, STEEL, segs=8)
    wheel = W.ring_obj("wheel", 0.24, 0.27, 0.03, segs=20)
    K.place(wheel, (0, 0, 0), (90, 0, 0))
    K.place(wheel, (0, -0.2, 0.86))
    ctx.add(wheel, "road_paint_red" if ctx.clean else RUST, uv_scale=3.0, smooth=40)
    W.rod(ctx, "shaft", (0, -0.2, 0.86), (0, -0.05, 0.86), 0.025, STEEL, segs=6)
    for j in range(4):
        a = j * math.pi / 2 + 0.3
        W.rod(ctx, f"spoke{j}", (0, -0.2, 0.86), (math.cos(a) * 0.25, -0.2, 0.86 + math.sin(a) * 0.25), 0.012, "road_paint_red" if ctx.clean else RUST, segs=4)
    if ctx.worn:
        ch = W.chain_obj("chain", [(0.25, -0.2, 0.86), (0.1, -0.1, 0.7), (0.0, 0.0, 0.6), (0.08, 0.1, 0.75)], link=0.045, wire=0.005)
        ctx.add(ch, STEEL, uv_scale=4.0, ao=False)
        _bx(ctx, "padlock", (0.05, 0.025, 0.06), (0.1, 0.1, 0.72), "lock_steel", bevel=0.005)


def w5_hatchery_sampler(ctx: K.Ctx) -> None:
    """The Cordon's automatic sampler on the catwalk: a grey hard case on folding legs, the bottle carousel under its
    lid, a battery box, a solar panel on a pole and the intake hose over the rail (+X) and down 3 m into the pool
    (below the origin). Worn: the panel cracked, the hose cut at the rail."""
    ctx.ground_clamp = False
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.rod(ctx, f"leg{sx}{sy}", (sx * 0.22, sy * 0.15, 0.0), (sx * 0.2, sy * 0.13, 0.4), 0.012, ALU, segs=6)
    _bx(ctx, "case", (0.5, 0.36, 0.38), (0, 0, 0.59), "plastic_grey", bevel=0.02, patches=0.4)
    _bx(ctx, "lid", (0.52, 0.38, 0.05), (0, 0, 0.805), "plastic_grey", bevel=0.015)
    for k in range(2):
        _bx(ctx, f"latch{k}", (0.05, 0.02, 0.06), (-0.12 + k * 0.24, -0.19, 0.76), "plastic_black", bevel=0.004)
    _bx(ctx, "stencil", (0.3, 0.002, 0.06), (0, -0.181, 0.6), "road_paint_orange", bevel=0.0, ao=False)
    _bx(ctx, "battery", (0.2, 0.16, 0.18), (-0.18, 0.05, 0.09), "plastic_black", bevel=0.01)
    W.rod(ctx, "panel_pole", (-0.22, 0.17, 0.0), (-0.22, 0.17, 0.85), 0.012, ALU, segs=6)
    pan = K.box("panel", (0.32, 0.22, 0.02))
    K.place(pan, (0, 0, 0), (-35, 0, 0))
    K.place(pan, (-0.22, 0.17, 0.88))
    ctx.add(pan, "furn_crt_screen", uv="box", uv_scale=2.0)
    hose_mat = "plastic_black"
    W.rod(ctx, "hose_out", (0.25, 0.0, 0.5), (0.4, 0.0, 0.6), 0.015, hose_mat, segs=6)
    pts = [(0.4, 0.0, 0.6), (0.5, 0.0, 1.1), (0.56, 0.0, 1.14), (0.6, 0.0, 1.0)]
    if not ctx.worn:
        pts += [(0.62, 0.0, -0.5), (0.6, 0.05, -1.5)]
    ctx.add(K.tube("hose", pts, 0.015, segs=6), hose_mat, uv="box", uv_scale=3.0, smooth=40, ao=False)
    if not ctx.worn:
        # The hose runs on down the dam's piers to the pool (the catwalk stands 3 m over the ground).
        ctx.add(K.tube("hose_low", [(0.6, 0.05, -1.5), (0.58, 0.1, -2.6), (0.7, 0.2, -2.85)], 0.015, segs=6), hose_mat, uv="box",
                uv_scale=3.0, smooth=40, ao=False)


def w5_hatchery_catwalk_rail(ctx: K.Ctx) -> None:
    """1 m of galvanised pipe railing (depth centred on the origin): posts at both ends, a top rail at 1.05 m, a knee
    rail and a toe board. Worn: the knee rail sagging, the toe board split."""
    mat = GALV
    for x in (-0.47, 0.47):
        W.rod(ctx, f"post{x}", (x, 0, 0.0), (x, 0, 1.05), 0.022, mat, segs=8, patches=0.5)
        _bx(ctx, f"base{x}", (0.1, 0.06, 0.01), (x, 0, 0.005), mat, bevel=0.0)
    W.rod(ctx, "top", (-0.5, 0, 1.05), (0.5, 0, 1.05), 0.022, mat, segs=8, patches=0.5)
    if ctx.worn:
        ctx.add(K.tube("knee", [(-0.47, 0, 0.55), (0.0, -0.03, 0.45), (0.47, 0, 0.55)], 0.018, segs=6), mat, uv="box", uv_scale=2.0, smooth=40)
        _bx(ctx, "toe_a", (0.5, 0.025, 0.1), (-0.24, 0, 0.06), "wood_weathered", bevel=0.003)
        tb = K.box("toe_b", (0.42, 0.025, 0.1))
        K.place(tb, (0, 0, 0), (0, 12, 0))
        K.place(tb, (0.26, 0, 0.07))
        ctx.add(tb, "wood_weathered", uv="box", uv_scale=2.0)
    else:
        W.rod(ctx, "knee", (-0.5, 0, 0.55), (0.5, 0, 0.55), 0.018, mat, segs=6)
        _bx(ctx, "toe", (1.0, 0.025, 0.1), (0, 0, 0.06), "wood_weathered", bevel=0.003)


# ============================================================================================
# The yard
# ============================================================================================

def w5_hatchery_sign(ctx: K.Ctx) -> None:
    """A routed cedar sign between two peeled log posts under a shingled cap: a carved rainbow trout leaping over three
    painted ripples, a routed border. Worn: the paint grey, a corner split, orange quarantine tape round one post."""
    for sx in (-1, 1):
        W.pole(ctx, f"post{sx}", [(sx * 1.25, 0, 0.0), (sx * 1.25, 0, 2.05)], 0.11, "out_log_peeled", r_end=0.1, seed=sx + 3)
    board_w, board_h, zb = 2.2, 0.9, 0.95
    _bx(ctx, "board", (board_w, 0.07, board_h), (0, 0, zb + board_h / 2), "wild_cedar", bevel=0.01, uv_scale=1.0, patches=0.5)
    for sy in (-1, 1):
        _bx(ctx, f"rail{sy}", (2.5, 0.09, 0.1), (0, 0, zb + (board_h + 0.05 if sy > 0 else -0.05)), "out_log_peeled", bevel=0.01, uv_scale=1.0)
    # The routed border.
    for z in (zb + 0.06, zb + board_h - 0.06):
        _bx(ctx, f"border_h{z}", (board_w - 0.1, 0.005, 0.02), (0, -0.036, z), "road_paint_white" if ctx.clean else "wood_weathered",
            bevel=0.0, ao=False)
    # The trout: a leaping silhouette in relief, olive back, a pink band.
    body = [(-0.55, 0.0), (-0.4, 0.1), (-0.1, 0.17), (0.25, 0.15), (0.45, 0.06), (0.52, 0.0), (0.45, -0.05), (0.2, -0.12), (-0.15, -0.13),
            (-0.4, -0.06)]
    fish = K.prism("fish", body, 0.03, plane="XZ")
    K.place(fish, (0, 0, 0), (0, 18, 0))
    K.place(fish, (0.05, -0.05, zb + 0.5))
    ctx.add(fish, "road_paint_green" if ctx.clean else "wood_weathered", uv="box", uv_scale=2.0)
    tail = K.prism("tail", [(0.0, 0.0), (0.22, 0.14), (0.16, 0.0), (0.22, -0.14)], 0.03, plane="XZ")
    K.place(tail, (0, 0, 0), (0, 18, 0))
    K.place(tail, (0.52, -0.05, zb + 0.33))
    ctx.add(tail, "road_paint_green" if ctx.clean else "wood_weathered", uv="box", uv_scale=2.0)
    band = K.prism("band", [(-0.4, -0.02), (0.4, -0.01), (0.4, 0.03), (-0.4, 0.03)], 0.032, plane="XZ")
    K.place(band, (0, 0, 0), (0, 18, 0))
    K.place(band, (0.05, -0.052, zb + 0.5))
    ctx.add(band, "road_paint_red" if ctx.clean else "wood_weathered", uv="box", uv_scale=2.0)
    for k in range(3):
        rp = K.tube(f"ripple{k}", [(-0.8 + k * 0.1 + i * 0.12, -0.04, zb + 0.18 + 0.03 * math.sin(i * 1.7) + k * 0.06) for i in range(8)],
                    0.012, segs=5)
        ctx.add(rp, "road_paint_blue" if ctx.clean else "wood_weathered", uv="box", uv_scale=3.0, ao=False)
    cap = K.prism("cap", [(-1.45, 0.0), (1.45, 0.0), (1.45, 0.04), (0.0, 0.22), (-1.45, 0.04)], 0.4, plane="XZ")
    K.place(cap, (0, 0, 2.05))
    ctx.add(cap, "wild_cedar", uv="box", uv_scale=1.0, moss=0.4 if ctx.worn else 0.1)
    if ctx.worn:
        r = ctx.drnd("tape")
        pts = [(-1.25 + 0.13 * math.cos(a), 0.13 * math.sin(a), 1.2 + a * 0.03) for a in [i * 0.6 for i in range(14)]]
        ctx.add(K.tube("tape", pts, 0.02, segs=4, flat=(1.0, 0.15)), "road_paint_orange", uv="box", uv_scale=3.0, ao=False)
        ctx.add(K.tube("tape_tail", [(-1.25, -0.13, 1.6), (-1.4, -0.2, 1.3), (-1.5, -0.25, 1.0 + r.uniform(0, 0.2))], 0.02, segs=4,
                       flat=(1.0, 0.15)), "road_paint_orange", uv="box", uv_scale=3.0, ao=False)


def w5_hatchery_stocking_truck(ctx: K.Ctx) -> None:
    """A state fish stocking truck (front -Y): a green cab-over, a flatbed with two insulated aluminium fish tanks,
    their aerator boxes and hatches, an oxygen bottle rack, the release chutes folded at the back. Worn: tyres flat,
    a window out, the tank hatches open and white inside."""
    r = ctx.rnd("truck")
    L = 7.6
    yf, yb = -L / 2, L / 2
    # Chassis and wheels.
    for sx in (-1, 1):
        W.bar(ctx, f"rail{sx}", (sx * 0.45, yf + 0.4, 0.62), (sx * 0.45, yb - 0.2, 0.62), 0.12, 0.22, DARK, bevel=0.005)
    axles = [yf + 1.0, yb - 1.9, yb - 0.9]
    for k, y in enumerate(axles):
        for sx in (-1, 1):
            t = P.tyre(f"tyre{k}{sx}", 0.5, 0.3, 0.3, segs=18)
            K.place(t, (sx * 1.0, y, 0.5))
            if ctx.worn and k > 0:
                P.flatten_tyre(t, 0.5, 0.5)
            ctx.add(t, TYRE, uv_scale=1.5, smooth=40, patches=0.3)
            rim = P.steel_rim(f"rim{k}{sx}", 0.3, 0.26, segs=14)
            if sx > 0:
                K.place(rim, (0, 0, 0), (0, 0, 180))
            K.place(rim, (sx * 1.02, y, 0.5))
            ctx.add(rim, "road_paint_white", uv_scale=1.5, smooth=40, patches=0.4)
        W.rod(ctx, f"axle{k}", (-0.9, y, 0.5), (0.9, y, 0.5), 0.06, DARK, segs=8)
    # Cab-over: a tall box with a sloped windshield.
    cab_y0, cab_y1 = yf, yf + 2.0
    cab = K.prism("cab", [(cab_y0 + 0.15, 0.75), (cab_y1, 0.75), (cab_y1, 2.85), (cab_y0 + 0.35, 2.85), (cab_y0, 2.2), (cab_y0, 0.95)],
                  2.3, plane="YZ")
    ctx.add(cab, "car_paint_green", uv="box", uv_scale=1.0, patches=0.5, low=0.4)
    ws = K.box("windshield", (2.0, 0.02, 0.85))
    K.place(ws, (0, 0, 0), (-17, 0, 0))
    K.place(ws, (0, cab_y0 + 0.17, 2.5))
    if not ctx.worn:
        ctx.add(ws, GLASS, uv="box", uv_scale=1.0, ao=False)
    for sx in (-1, 1):
        _bx(ctx, f"door_win{sx}", (0.02, 0.9, 0.6), (sx * 1.16, cab_y0 + 1.0, 2.25), GLASS if not (ctx.worn and sx > 0) else DARK,
            bevel=0.0, ao=False)
        _bx(ctx, f"seal{sx}", (0.03, 0.4, 0.35), (sx * 1.16, cab_y0 + 1.2, 1.4), "road_paint_white", bevel=0.0, ao=False)
        W.rod(ctx, f"mirror_arm{sx}", (sx * 1.15, cab_y0 + 0.4, 2.2), (sx * 1.4, cab_y0 + 0.3, 2.3), 0.015, CHROME_OR(ctx), segs=6)
        _bx(ctx, f"mirror{sx}", (0.05, 0.12, 0.3), (sx * 1.42, cab_y0 + 0.3, 2.3), "road_steel_dark", bevel=0.01)
        _bx(ctx, f"fender{sx}", (0.35, 1.1, 0.06), (sx * 1.0, axles[0], 1.05), "car_paint_green", bevel=0.01)
        _bx(ctx, f"lamp{sx}", (0.22, 0.04, 0.14), (sx * 0.85, cab_y0 - 0.0, 1.15), "lens_clear", bevel=0.01, ao=False)
    _bx(ctx, "grille", (1.2, 0.04, 0.35), (0, cab_y0 - 0.0, 1.2), DARK, bevel=0.005)
    _bx(ctx, "bumper", (2.3, 0.15, 0.2), (0, cab_y0 - 0.05, 0.8), "road_steel", bevel=0.01)
    # The bed and the two tanks.
    _bx(ctx, "bed", (2.4, yb - cab_y1 - 0.1, 0.12), (0, (cab_y1 + 0.1 + yb) / 2, 0.8), "road_steel_dark", bevel=0.01)
    tank_y = [cab_y1 + 0.35 + 1.15, cab_y1 + 0.35 + 3.55]
    for k, y in enumerate(tank_y):
        _bx(ctx, f"tank{k}", (2.2, 2.2, 1.5), (0, y, 0.86 + 0.75), ALU, bevel=0.06, patches=0.5, cuts=(2, 2, 1))
        for z in (1.05, 1.85):
            _bx(ctx, f"band{k}{z}", (2.24, 0.06, 0.06), (0, y - 1.1, z), STEEL, bevel=0.005)
        for j, x in enumerate((-0.5, 0.5)):
            hatch_open = ctx.worn and j == 0
            hb = K.box(f"hatch{k}{j}", (0.7, 0.7, 0.05), center=(0, 0, 0), bevel=0.01)
            if hatch_open:
                K.place(hb, (0, -0.35, 0))
                K.place(hb, (0, 0, 0), (-110, 0, 0))
                K.place(hb, (x, y - 0.0, 2.38))
            else:
                K.place(hb, (x, y, 2.39))
            ctx.add(hb, ALU, uv="box", uv_scale=2.0, patches=0.5)
            if hatch_open:
                _felt(ctx, f"tank_felt{k}", x, y, 2.33, 3, r, spread=0.2, size=0.08, flat=0.3)
        _bx(ctx, f"aerator{k}", (0.5, 0.35, 0.3), (0.75, y + 0.7, 2.5), "road_paint_grey", bevel=0.01)
        W.rod(ctx, f"chute{k}", (0.0, y + 1.1, 1.2), (0.0, y + 1.45, 0.95), 0.12, ALU, segs=10)
    for k in range(3):
        _cy(ctx, f"o2_{k}", 0.11, 1.3, (-0.95 + k * 0.25, cab_y1 + 0.18, 1.55), "road_paint_green" if k % 2 else "road_paint_white", segs=10)
    W.rod(ctx, "o2_strap", (-1.1, cab_y1 + 0.18, 1.8), (-0.4, cab_y1 + 0.18, 1.8), 0.015, DARK, segs=4)
    _bx(ctx, "state_panel", (0.002, 1.4, 0.45), (1.16, cab_y0 + 1.0, 1.35), "road_paint_white", bevel=0.0, ao=False)


def CHROME_OR(ctx) -> str:
    return "road_steel" if ctx.worn else "chrome_pitted"


def w5_hatchery_feed_silo(ctx: K.Ctx) -> None:
    """A galvanised bulk feed bin: a ribbed 2.0 m tank on four legs, a 60 degree hopper with the auger boot underneath,
    a peaked lid, a ladder up the side (+X) and the feed tube off toward the raceways (-X). Worn: streaked, the lid
    hanging open."""
    R, zc0, zc1 = 1.0, 2.2, 4.6
    mat = GALV
    tank = K.lathe("tank", [(0.12, zc0 - 1.25), (R, zc0), (R, zc1), (0.15, zc1 + 0.55), (0.0, zc1 + 0.6)], segs=24)
    ctx.add(tank, mat, uv="cyl", uv_scale=1.0, smooth=35, patches=0.6, low=0.3 if ctx.worn else 0.0)
    for k in range(5):
        z = zc0 + 0.1 + k * (zc1 - zc0 - 0.2) / 4
        ring = W.ring_obj(f"rib{k}", R, R + 0.025, 0.04, segs=24)
        K.place(ring, (0, 0, z))
        ctx.add(ring, mat, uv_scale=2.0, smooth=40)
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.bar(ctx, f"leg{sx}{sy}", (sx * 0.85, sy * 0.85, 0.0), (sx * 0.72, sy * 0.72, zc0 + 0.2), 0.09, 0.09, mat, bevel=0.004)
            _bx(ctx, f"foot{sx}{sy}", (0.25, 0.25, 0.08), (sx * 0.85, sy * 0.85, 0.04), CONC, bevel=0.01)
    _cy(ctx, "boot", 0.12, 0.3, (0, 0, zc0 - 1.4), DARK, segs=10)
    W.rod(ctx, "auger", (0, 0, zc0 - 1.4), (-1.6, 0, zc0 - 0.9), 0.07, mat, segs=10)
    _bx(ctx, "motor", (0.3, 0.25, 0.25), (0.25, 0.0, zc0 - 1.4), "road_paint_grey", bevel=0.01)
    # The ladder up the +X side and a cage at the top.
    for sy in (-1, 1):
        W.rod(ctx, f"lad_rail{sy}", (R + 0.12, sy * 0.2, 0.6), (R + 0.12, sy * 0.2, zc1 + 0.4), 0.018, mat, segs=6)
    for k in range(int((zc1 - 0.6) / 0.3)):
        z = 0.75 + k * 0.3
        W.rod(ctx, f"rung{k}", (R + 0.12, -0.2, z), (R + 0.12, 0.2, z), 0.012, mat, segs=4)
    lid = K.lathe("lid", [(0.3, 0.0), (0.3, 0.04), (0.0, 0.12)], segs=12)
    if ctx.worn:
        K.place(lid, (0.3, 0, 0))
        K.place(lid, (0, 0, 0), (0, -100, 0))
        K.place(lid, (-0.3, 0, zc1 + 0.62))
    else:
        K.place(lid, (0, 0, zc1 + 0.6))
    ctx.add(lid, mat, uv="box", uv_scale=2.0, smooth=40)
    ctx.ground_clamp = True


BUILDERS = {
    "w5_hatchery_raceway": w5_hatchery_raceway,
    "w5_hatchery_headbox": w5_hatchery_headbox,
    "w5_hatchery_shed_post": w5_hatchery_shed_post,
    "w5_hatchery_intake_pipe": w5_hatchery_intake_pipe,
    "w5_hatchery_fish_tote": w5_hatchery_fish_tote,
    "w5_hatchery_feed_cart": w5_hatchery_feed_cart,
    "w5_hatchery_incubator_stack": w5_hatchery_incubator_stack,
    "w5_hatchery_hatch_trough": w5_hatchery_hatch_trough,
    "w5_hatchery_results_board": w5_hatchery_results_board,
    "w5_hatchery_chiller": w5_hatchery_chiller,
    "w5_hatchery_sample_cooler": w5_hatchery_sample_cooler,
    "w5_hatchery_feed_pallet": w5_hatchery_feed_pallet,
    "w5_hatchery_dam": w5_hatchery_dam,
    "w5_hatchery_weir_pool": w5_hatchery_weir_pool,
    "w5_hatchery_creek": w5_hatchery_creek,
    "w5_hatchery_headgate": w5_hatchery_headgate,
    "w5_hatchery_sampler": w5_hatchery_sampler,
    "w5_hatchery_catwalk_rail": w5_hatchery_catwalk_rail,
    "w5_hatchery_sign": w5_hatchery_sign,
    "w5_hatchery_stocking_truck": w5_hatchery_stocking_truck,
    "w5_hatchery_feed_silo": w5_hatchery_feed_silo,
}


def build(params: dict, outputs: list[str]) -> None:
    K.run(params, outputs, BUILDERS)
