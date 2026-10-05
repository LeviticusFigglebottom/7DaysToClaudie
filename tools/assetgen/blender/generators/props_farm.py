"""Farm props family — the Okafor farm in Larch Hollow: farmyard (tractor wreck, windmill pump,
grain bin, trough, coop, plough, fences and gate, round bales), barn (square bales, feed sacks and
bin, milk cans, stalls, tool rack, saddle, tool chest, hurricane lantern, wagon wheel) and the
farmhouse (cast-iron cookstove, butter churn, washtub, quilt bed, hope chest, oil lamp) with its
root cellar (preserve shelving and jars, produce crates).

Each builder takes a props_ext_kit.Ctx and registers parts; the kit builds one GLB per condition
(clean / worn / destroyed). Front faces -Y, origin at the bottom centre, metres. Abandoned
Pacific-Northwest farm: sun-silvered wood, rust under galvanising and paint, moss on the
up-facing wood (vertex B), mould on the old hay. No text or logos anywhere.

params: prop (id), conditions, seed, [produce] (crate contents)."""
from __future__ import annotations

import math
import random

from mathutils import Matrix, Vector

from lib import props_ext_kit as K
from lib import props_ext_parts as P

# Blender-only preview colours (dev_preview / Cycles); Godot swaps in the real materials.
K.materials.PREVIEW_COLORS.update({
    "farm_hay": (0.55, 0.43, 0.2), "farm_hay_old": (0.38, 0.35, 0.3), "farm_twine": (0.45, 0.36, 0.22),
    "farm_corrugated_galv": (0.5, 0.51, 0.5), "farm_corrugated_rust": (0.35, 0.2, 0.12), "farm_quilt": (0.45, 0.3, 0.25),
    "farm_leather_saddle": (0.3, 0.17, 0.08), "farm_leather_black": (0.08, 0.07, 0.06), "farm_potato": (0.4, 0.3, 0.18),
    "farm_apple": (0.45, 0.08, 0.05), "farm_onion": (0.55, 0.38, 0.2), "farm_preserve_peach": (0.75, 0.42, 0.1),
    "farm_preserve_beet": (0.35, 0.03, 0.08), "farm_preserve_pickle": (0.3, 0.35, 0.1), "farm_preserve_jam": (0.15, 0.03, 0.08),
    "farm_preserve_spoiled": (0.25, 0.25, 0.15), "farm_jar_glass": (0.7, 0.8, 0.78), "farm_feed_sack": (0.5, 0.4, 0.25),
    "farm_grain": (0.6, 0.48, 0.25), "farm_tractor_red": (0.45, 0.1, 0.05), "farm_tractor_cream": (0.65, 0.6, 0.48),
    "farm_wood_barn_red": (0.4, 0.1, 0.06), "farm_wood_green": (0.15, 0.22, 0.13), "farm_wood_grey": (0.42, 0.4, 0.37),
    "farm_wood_cedar": (0.45, 0.27, 0.15), "farm_iron_black": (0.05, 0.05, 0.05), "farm_iron_white": (0.7, 0.68, 0.62),
    "farm_steel_blade": (0.4, 0.4, 0.38), "farm_wick_flame": (1.0, 0.6, 0.2), "farm_feathers": (0.7, 0.66, 0.6),
    "farm_chicken_wire": (0.5, 0.5, 0.48), "farm_trough_water": (0.08, 0.1, 0.06),
})


# ============================================================================================
# Shared helpers
# ============================================================================================

def _board(name: str, L: float, W: float, T: float, r: random.Random, *, cuts: int = 2, bow: float = 0.0,
           twist: float = 0.0, bevel: float = 0.003):
    """Rough-sawn board along X (width Y, thickness Z) with a little random bow and twist."""
    return P.plank(name, L, W, T, cuts=cuts, bow=bow + r.uniform(-0.002, 0.002), twist=twist + r.uniform(-1.2, 1.2),
                   bevel=bevel)


def _hoop(name: str, radius: float, z: float, *, tube_r: float = 0.006, segs: int = 20, flat=(0.35, 1.0),
          center=(0.0, 0.0)):
    """Flat band (barrel hoop, can bead) round the Z axis at height z."""
    pts = [(center[0] + radius * math.cos(math.tau * i / segs), center[1] + radius * math.sin(math.tau * i / segs), z)
           for i in range(segs)]
    return K.tube(name, pts, tube_r, segs=4, closed=True, flat=flat)


def _ring_x(name: str, radius: float, x: float, *, tube_r: float = 0.004, segs: int = 24, z0: float = 0.0, y0: float = 0.0,
            squash=None):
    """Closed loop in the YZ plane at x (twine round a bale, a hoop on a round bale)."""
    pts = []
    for i in range(segs):
        a = math.tau * i / segs
        p = Vector((x, y0 + radius * math.cos(a), z0 + radius * math.sin(a)))
        if squash is not None:
            p = squash(p)
        pts.append(p)
    return K.tube(name, pts, tube_r, segs=4, closed=True)


def _spoked_wheel(ctx: K.Ctx, name: str, R: float, width: float, n_spokes: int, *, hub_r: float, mat_wood: str,
                  mat_iron: str, felloe: float = 0.06, broken: tuple = (), segs: int = 24) -> list:
    """Wooden wheel in the XZ plane (axis Y) centred at the origin: hub, tapered spokes, felloe and
    a thin iron tyre. Returns the registered parts (for later placement as a group)."""
    parts = []
    hub = K.lathe(f"{name}_hub", [(0.0, -width * 0.7), (hub_r * 0.75, -width * 0.7), (hub_r, -width * 0.45),
                                   (hub_r * 1.05, 0.0), (hub_r, width * 0.45), (hub_r * 0.75, width * 0.7), (0.0, width * 0.7)],
                  segs=12)
    K.place(hub, rot=(90, 0, 0))
    parts.append(ctx.add(hub, mat_wood, uv="cyl", uv_axis=1, smooth=40, patches=0.3))
    for side in (-1, 1):
        band = K.lathe(f"{name}_band", [(hub_r * 0.98, side * width * 0.42 - 0.012), (hub_r * 1.07, side * width * 0.42 - 0.012),
                                         (hub_r * 1.07, side * width * 0.42 + 0.012), (hub_r * 0.98, side * width * 0.42 + 0.012)],
                       segs=12, close_profile=True)
        K.place(band, rot=(90, 0, 0))
        parts.append(ctx.add(band, mat_iron, uv="cyl", uv_axis=1, smooth=40))
    for k in range(n_spokes):
        if k in broken:
            continue
        a = math.tau * (k + 0.5) / n_spokes
        ln = R - felloe - hub_r + 0.02
        sp = K.box(f"{name}_spoke", (ln, 0.045, 0.03), center=(hub_r + ln / 2 - 0.01, 0, 0), bevel=0.006, cuts=(2, 0, 0))
        K.taper(sp, 0, lambda x: 1.0 - 0.3 * max(0.0, (x - hub_r)) / max(1e-3, ln))
        K.place(sp, rot=(0, -math.degrees(a), 0))
        parts.append(ctx.add(sp, mat_wood, long_axis=0, smooth=None, patches=0.35))
    fel = K.lathe(f"{name}_felloe", [(R - felloe, -width * 0.32), (R - 0.008, -width * 0.32), (R - 0.008, width * 0.32),
                                      (R - felloe, width * 0.32)], segs=segs, close_profile=True)
    K.place(fel, rot=(90, 0, 0))
    parts.append(ctx.add(fel, mat_wood, uv="cyl", uv_axis=1, smooth=None, patches=0.35))
    tyre = K.lathe(f"{name}_tyre", [(R - 0.009, -width * 0.36), (R + 0.004, -width * 0.36), (R + 0.004, width * 0.36),
                                     (R - 0.009, width * 0.36)], segs=segs, close_profile=True)
    K.place(tyre, rot=(90, 0, 0))
    parts.append(ctx.add(tyre, mat_iron, uv="cyl", uv_axis=1, smooth=30, wear=1.2))
    return parts


def _recenter_y(ctx: K.Ctx) -> None:
    """Centres a wall-leaning prop's depth on the origin (PoiBuilder's `against` assumes the
    origin is mid-depth), collision proxies included."""
    ys = [v.co.y for o in ctx.parts for v in o.data.vertices]
    if not ys:
        return
    dy = -(min(ys) + max(ys)) / 2
    _move(ctx.parts + ctx.cols, Matrix.Translation((0, dy, 0)))


def _move(parts: list, m: Matrix) -> None:
    for o in parts:
        o.data.transform(m)
        o.data.update()


def _xf(loc=(0, 0, 0), rot=None) -> Matrix:
    return Matrix.Translation(Vector(loc)) @ K.rot_matrix(rot)


def _jar(ctx: K.Ctx, x: float, y: float, z: float, *, rad: float, h: float, content: str | None, broken: bool = False,
         segs: int = 6, lid: str = "furn_tin", tilt=None):
    """Mason jar: glass shell, packed contents and a screw band lid. Broken: the top sheared off,
    a puddle of contents at its foot."""
    prof = [(0.0, 0.0), (rad, 0.01), (rad, h * 0.82), (rad * 0.8, h)]
    glass = K.lathe("jar", prof, segs=segs, cap_bottom=False, cap_top=False)
    parts = []
    if broken:
        K.cut_plane(glass, (0, 0, h * 0.45), (0.3, 0.2, 1.0), keep="below", fill=False)
    if content is not None:
        fill = h * (0.4 if broken else 0.78)
        c = K.cyl("contents", rad * 0.9, fill, segs=segs, center=(0, 0, 0.004 + fill / 2))
        parts.append(ctx.add(c, content, uv="cyl", uv_scale=1.0, smooth=40, wear=0.2, at=((x, y, z), tilt)))
    parts.append(ctx.add(glass, "farm_jar_glass", uv="cyl", uv_scale=1.0, smooth=40, wear=0.1, ao=False, at=((x, y, z), tilt)))
    if not broken:
        cap = K.cyl("lid", rad * 0.84, 0.014, segs=segs, center=(0, 0, h + 0.004))
        parts.append(ctx.add(cap, lid, uv="cyl", smooth=40, wear=1.2, at=((x, y, z), tilt)))
    return parts


# ============================================================================================
# Hay
# ============================================================================================

def farm_hay_bale_square(ctx: K.Ctx) -> None:
    """Small square bale of grass hay (0.92 x 0.46 x 0.36) bound by two loops of sisal twine sunk
    into the bale, flake seams across it, stalks sticking out. Worn: rained on for a season —
    grey, slumped, mould blooming on top. Destroyed: twine burst, the flakes slid apart."""
    L, W, H = 0.92, 0.46, 0.36
    mat = "farm_hay" if ctx.clean else "farm_hay_old"
    twine_x = (-0.24, 0.24)

    def pinch_at(x: float) -> float:
        return sum(math.exp(-((x - tx) / 0.035) ** 2) for tx in twine_x)

    def bale_part(name: str, x0: float, x1: float, seed: int):
        b = K.box(name, (x1 - x0, W, H), center=((x0 + x1) / 2, 0, H / 2), bevel=0.035, bevel_segs=2,
                  cuts=(max(3, int((x1 - x0) / 0.06)), 3, 3))

        def shape(co: Vector) -> Vector:
            ridge = 0.004 * math.sin(co.x / 0.065 * math.pi)
            pinch = min(1.0, pinch_at(co.x))
            belly = 1.0 - ((co.z - H / 2) / (H / 2)) ** 2
            sy = 1.0 + 0.05 * belly - 0.045 * pinch
            sz = 1.0 - 0.04 * pinch
            slump = (0.035 * (1.0 - (co.x / (L / 2)) ** 2) * (co.z / H)) if ctx.worn else 0.0
            return Vector((co.x, co.y * sy + math.copysign(ridge, co.y), H / 2 + (co.z - H / 2) * sz - slump))
        K.map_verts(b, shape)
        K.noise_disp(b, 0.011, scale=9.0, seed=seed, mask=lambda co: 1.0 - min(1.0, pinch_at(co.x)))
        return b

    if ctx.destroyed:
        spans = [(-L / 2, -0.17), (-0.15, 0.13), (0.15, L / 2)]
        for k, (x0, x1) in enumerate(spans):
            dr = ctx.drnd(f"flake{k}")
            b = bale_part(f"flake{k}", x0, x1, ctx.seed + k)
            mx = (x0 + x1) / 2
            K.place(b, (-mx, 0, 0))
            K.place(b, rot=(dr.uniform(-10, 10), dr.uniform(-22, 22) if k != 1 else 0.0, dr.uniform(-18, 18)))
            K.place(b, (mx * 1.35 + (0.08 if k == 2 else 0.0), dr.uniform(-0.07, 0.07), 0))
            K.lift_min(b)
            ctx.add(b, mat, long_axis=0, smooth=35, patches=0.4, moss=0.35)
        pile = K.blob("loose", 0.33, subdiv=2, scale=(1.4, 1.0, 0.32), center=(0.05, 0.3, 0.02), rough=0.4, seed=ctx.seed)
        ctx.add(pile, mat, smooth=40, moss=0.3)
        tw = K.tube("twine_snapped", [(-0.5, -0.3, 0.004), (-0.3, -0.34, 0.004), (-0.1, -0.31, 0.005), (0.15, -0.36, 0.004),
                                       (0.35, -0.3, 0.004)], 0.003, segs=4)
        ctx.add(tw, "farm_twine", wear=0.3)
        ctx.col_box((-0.62, -0.32, 0), (0.62, 0.45, 0.3))
        return
    body = bale_part("bale", -L / 2, L / 2, ctx.seed)
    ctx.add(body, mat, long_axis=0, smooth=35, patches=0.4, moss=0.45 if ctx.worn else 0.1)
    for tx in twine_x:
        a, c = W / 2 + 0.004, H / 2 * 0.96 + 0.004
        pts = []
        n = 28
        for i in range(n):
            t = math.tau * i / n
            ct, st = math.cos(t), math.sin(t)
            p = Vector((tx, a * math.copysign(abs(ct) ** 0.25, ct), H / 2 + c * math.copysign(abs(st) ** 0.25, st)))
            if ctx.worn:
                p.z -= 0.035 * (1.0 - (tx / (L / 2)) ** 2) * (p.z / H)
            pts.append(p)
        ctx.add(K.tube("twine", pts, 0.003, segs=4, closed=True), "farm_twine", wear=0.3)
    r = ctx.rnd("straws")
    for k in range(16):
        ln = r.uniform(0.06, 0.15)
        s = K.box("straw", (ln, 0.004, 0.0016))
        side = r.choice(("top", "end", "side"))
        if side == "top":
            loc = (r.uniform(-0.4, 0.4), r.uniform(-0.2, 0.2), H - 0.01)
            rot = (r.uniform(-10, 10), r.uniform(-25, -5), r.uniform(0, 180))
        elif side == "end":
            sx = r.choice((-1, 1))
            loc = (sx * (L / 2 - 0.01), r.uniform(-0.2, 0.2), r.uniform(0.05, H - 0.05))
            rot = (r.uniform(-30, 30), r.uniform(-30, 30), r.uniform(-25, 25) + (0 if sx > 0 else 180))
        else:
            sy = r.choice((-1, 1))
            loc = (r.uniform(-0.42, 0.42), sy * (W / 2 - 0.01), r.uniform(0.05, H - 0.05))
            rot = (r.uniform(-20, 20), r.uniform(-40, 40), sy * 90 + r.uniform(-30, 30))
        K.place(s, (ln / 2, 0, 0))
        ctx.add(s, mat, long_axis=0, at=(loc, rot), patches=0.2)
    ctx.col_box((-L / 2, -W / 2 - 0.02, 0), (L / 2, W / 2 + 0.02, H))


def farm_hay_bale_round(ctx: K.Ctx) -> None:
    """Round bale (1.5 m across, 1.2 m wide) lying on its curved side: rolled layers showing as
    rings on the domed ends, eight twine wraps, the weight flattening its belly. Worn: a winter
    outside — grey crust, mould on top, slumped. Destroyed: split and slumping open."""
    R, Wd = 0.76, 1.2
    mat = "farm_hay" if ctx.clean else "farm_hay_old"
    prof = []
    n_end = 9
    for k in range(n_end):
        rr = 0.03 + k * (R - 0.1) / (n_end - 1)
        dome = 0.04 * (1.0 - (rr / R) ** 2)
        prof.append((rr, -Wd / 2 - dome + (0.007 if k % 2 else -0.004)))
    prof += [(R - 0.035, -Wd / 2 + 0.01), (R - 0.008, -Wd / 2 + 0.045), (R + 0.004, -Wd / 2 + 0.1), (R + 0.012, -0.3),
             (R + 0.016, 0.0), (R + 0.012, 0.3), (R + 0.004, Wd / 2 - 0.1), (R - 0.008, Wd / 2 - 0.045),
             (R - 0.035, Wd / 2 - 0.01)]
    for k in range(n_end - 1, -1, -1):
        rr = 0.03 + k * (R - 0.1) / (n_end - 1)
        dome = 0.04 * (1.0 - (rr / R) ** 2)
        prof.append((rr, Wd / 2 + dome - (0.007 if k % 2 else -0.004)))
    prof = [(0.0, prof[0][1] - 0.004)] + prof + [(0.0, prof[-1][1] + 0.004)]
    body = K.lathe("roundbale", prof, segs=28)
    K.place(body, (0, 0, R), rot=(0, 90, 0))
    sag = 0.86 if ctx.worn else 0.93
    if ctx.destroyed:
        sag = 0.7

    def squash(co: Vector) -> Vector:
        z = co.z * sag
        flat = 0.2
        if z < flat:
            z = flat - (flat - z) * 0.3
        z -= flat * 0.7  # the flattened belly rests on the ground
        bulge = 1.0 + (0.08 if ctx.destroyed else 0.03) * max(0.0, 1.0 - abs(z - 0.3) / 0.5)
        return Vector((co.x, co.y * bulge, z))
    K.map_verts(body, squash)
    K.noise_disp(body, 0.016, scale=3.5, seed=ctx.seed)
    if ctx.destroyed:
        K.noise_disp(body, 0.05, scale=1.2, seed=ctx.seed + 3)
    ctx.add(body, mat, uv="cyl", uv_axis=0, uv_scale=1.0, smooth=45, patches=0.4, moss=0.55 if ctx.worn else 0.12)
    for k in range(8):
        x = -0.48 + k * 0.96 / 7
        if ctx.destroyed and k in (3, 4):
            continue
        ring = _ring_x("wrap", R + 0.02, x, tube_r=0.0035, segs=28, z0=R, squash=squash)
        ctx.add(ring, "farm_twine", wear=0.3)
    if ctx.destroyed:
        spill = K.blob("spill", 0.45, subdiv=2, scale=(1.5, 1.2, 0.25), center=(0.2, -0.8, 0.0), rough=0.35, seed=ctx.seed + 9)
        ctx.add(spill, mat, smooth=40, moss=0.3)
    top = 2 * R * sag + 0.02
    ctx.col_box((-Wd / 2 - 0.05, -R - 0.05, 0), (Wd / 2 + 0.05, R + 0.05, top))


# ============================================================================================
# Yard: fences and gate
# ============================================================================================

def _post(name: str, h: float, r: random.Random, *, w: float = 0.13):
    """Hewn fence post: squared, tapering a little, its top cut on a slant to shed rain."""
    p = K.box(name, (w, w * 0.92, h), center=(0, 0, h / 2), bevel=0.012, cuts=(0, 0, 4))
    K.taper(p, 2, lambda z: 1.0 - 0.08 * z / h)
    K.cut_plane(p, (0, 0, h - 0.03), (r.uniform(-0.3, 0.3), 0.35, 1.0), keep="below")
    K.noise_disp(p, 0.006, scale=6.0, seed=r.randint(0, 999))
    return p


def farm_fence_rail(ctx: K.Ctx) -> None:
    """Post-and-rail fence, 3 m: two hewn posts and three split cedar rails let into them. Worn:
    silver-grey and mossy, the middle rail dropped from one post. Destroyed: rails broken and
    lying in the grass, one post leaning."""
    mat = "farm_wood_grey"
    r = ctx.rnd("fence")
    posts = []
    for k, x in enumerate((-1.45, 1.45)):
        p = _post(f"post{k}", 1.3, ctx.rnd(f"post{k}"))
        if ctx.destroyed and k == 1:
            K.kink([p], (0, 0, 0.05), (14, -8, 0), blend=0.3)
        K.place(p, (x, 0, 0))
        posts.append(ctx.add(p, mat, long_axis=2, smooth=None, patches=0.5, moss=0.4, low=0.6, low_h=0.3))
    for k, z in enumerate((0.38, 0.72, 1.06)):
        rr = ctx.rnd(f"rail{k}")
        rail = P.log_split(f"rail{k}", 3.02, 0.075, rr, kind="half" if k % 2 else "quarter", segs=7)
        K.map_verts(rail, lambda co: Vector((co.x, co.y, co.z - 0.03 * (1 - (co.x / 1.51) ** 2))))
        K.noise_disp(rail, 0.006, scale=5.0, seed=rr.randint(0, 999))
        rot = (rr.uniform(-25, 25), 0, 0)
        if ctx.destroyed and k != 0:
            dr = ctx.drnd(f"rail{k}")
            P.break_end(rail, dr.uniform(-0.3, 0.4), dr, side=1, depth=0.12)
            K.uv_box(rail, 1.0, long_axis=0)
            ctx.add(rail, mat, uv=None, smooth=None, patches=0.5, moss=0.5,
                    at=((dr.uniform(-0.3, 0.3), -0.35 - 0.25 * k, 0.06), (dr.uniform(-6, 6), 90 + dr.uniform(-5, 5), dr.uniform(-12, 12))))
            continue
        if ctx.worn and k == 1:
            rot = (rot[0], math.degrees(math.atan2(0.62, 2.9)), 0)
            ctx.add(rail, mat, long_axis=0, smooth=None, patches=0.5, moss=0.5, at=((0.02, 0.02, z - 0.33), rot))
            continue
        ctx.add(rail, mat, long_axis=0, smooth=None, patches=0.5, moss=0.45, at=((0, 0.0, z), rot))
    ctx.col_box((-1.52, -0.12, 0), (1.52, 0.12, 1.3))


def farm_fence_wire(ctx: K.Ctx) -> None:
    """Post-and-barbed-wire fence, 3 m: two round cedar posts, four sagging strands with two-point
    barbs every 25 cm. Worn: rusted, the top strand snapped and curling to the ground. Destroyed:
    a post snapped at the base, the wire slack in the grass."""
    wood = "farm_wood_cedar"
    wire = "metal_galvanized" if ctx.clean else "car_rust"
    post_top = []
    for k, x in enumerate((-1.5, 1.5)):
        rr = ctx.rnd(f"p{k}")
        p = K.cyl(f"post{k}", 0.065, 1.32, segs=9, center=(0, 0, 0.66), r_top=0.058, cuts=4)
        K.cut_plane(p, (0, 0, 1.3), (rr.uniform(-0.2, 0.2), rr.uniform(-0.2, 0.2), 1.0), keep="below")
        K.noise_disp(p, 0.007, scale=5.0, seed=rr.randint(0, 999))
        if ctx.destroyed and k == 0:
            K.kink([p], (0, 0, 0.12), (0, 62, 10), blend=0.05)
        K.place(p, (x, 0, 0))
        # Box UVs with the long axis up: the grain runs along the post (cylindrical UVs would
        # wrap it round the post in rings).
        ctx.add(p, wood, uv="box", long_axis=2, smooth=40, patches=0.5, moss=0.45, low=0.7, low_h=0.35)
        post_top.append(x)
    heights = (0.32, 0.56, 0.8, 1.04)
    for s, z in enumerate(heights):
        n = 13
        pts = []
        snapped = ctx.worn and not ctx.destroyed and s == 3
        slack = ctx.destroyed
        for i in range(n):
            t = i / (n - 1)
            x = -1.5 + 3.0 * t
            sag = 0.035 * math.sin(math.pi * t)
            zz = z - sag
            yy = -0.07
            if slack:
                zz = max(0.03, z * (0.15 + 0.85 * t) - 0.25 * math.sin(math.pi * t)) if s > 0 else 0.03 + 0.02 * math.sin(7 * t)
                yy = -0.07 - 0.25 * math.sin(math.pi * t) * (s / 3)
            if snapped and t > 0.55:
                k2 = (t - 0.55) / 0.45
                zz = z - k2 * (z - 0.05)
                yy = -0.07 - 0.35 * math.sin(k2 * 2.5)
                x = -1.5 + 3.0 * (0.55 + 0.25 * k2)
            pts.append((x, yy, zz))
        strand = K.tube(f"strand{s}", pts, 0.0028, segs=3, caps=False)
        ctx.add(strand, wire, uv_scale=2.0, smooth=50, wear=1.0)
        # Barbs: a short cross piece wrapped round the strand every 25 cm.
        for b in range(1, 12):
            t = b / 12
            i = min(n - 2, int(t * (n - 1)))
            f = t * (n - 1) - i
            pa, pb = Vector(pts[i]), Vector(pts[i + 1])
            c = pa.lerp(pb, f)
            d = (pb - pa).normalized()
            side = d.cross(Vector((0, 0, 1))).normalized() if abs(d.z) < 0.9 else Vector((0, 1, 0))
            ang = (b * 47) % 180
            off = side * math.cos(math.radians(ang)) * 0.014 + d.cross(side).normalized() * math.sin(math.radians(ang)) * 0.014
            barb = K.tube("barb", [c - off, c + off], 0.0014, segs=3, caps=False)
            ctx.add(barb, wire, uv_scale=2.0, wear=1.0)
    ctx.col_box((-1.56, -0.1, 0), (1.56, 0.08, 1.3))


def farm_gate(ctx: K.Ctx) -> None:
    """Five-bar timber field gate (3 m) on strap hinges, hung from a round gatepost; diagonal
    brace from the bottom hinge to the top of the latch stile, iron latch. Worn: dropped on its
    hinges, the latch end dragging. Destroyed: off its hinges, propped against the post."""
    wood = "farm_wood_grey"
    iron = "farm_iron_black"
    r = ctx.rnd("gate")
    gp = K.cyl("gatepost", 0.09, 1.55, segs=10, center=(0, 0, 0.775), r_top=0.082, cuts=3)
    K.noise_disp(gp, 0.006, scale=5.0, seed=ctx.seed)
    ctx.add(gp, "farm_wood_cedar", uv="box", long_axis=2, smooth=40, patches=0.5, moss=0.45, at=((-1.62, 0, 0), None))
    leaf = []
    Lg = 2.95
    hang = K.box("hang_stile", (0.1, 0.07, 1.22), center=(0.05, 0, 0.61), bevel=0.008)
    latch = K.box("latch_stile", (0.08, 0.06, 1.18), center=(Lg - 0.04, 0, 0.6), bevel=0.008)
    leaf += [hang, latch]
    for k in range(5):
        z = 0.12 + k * 0.255
        bar = _board(f"bar{k}", Lg - 0.18, 0.085, 0.032, ctx.rnd(f"bar{k}"), cuts=3)
        K.place(bar, rot=(90, 0, 0))
        K.place(bar, (Lg / 2, 0, z))
        leaf.append(bar)
    dx, dz = Lg - 0.2, 1.0
    brace = _board("brace", math.hypot(dx, dz), 0.08, 0.03, r, cuts=3)
    K.place(brace, rot=(90, 0, 0))
    K.place(brace, rot=(0, -math.degrees(math.atan2(dz, dx)), 0))
    K.place(brace, (0.1 + dx / 2, 0.035, 0.14 + dz / 2))
    leaf.append(brace)
    straps = []
    for z in (0.2, 1.0):
        st = K.box("strap", (0.55, 0.008, 0.045), center=(0.28, -0.04, z), bevel=0.002)
        straps.append(st)
        pin = K.cyl("pintle", 0.012, 0.08, segs=6, center=(-0.05, -0.04, z))
        straps.append(pin)
    lt = K.box("latch", (0.16, 0.03, 0.03), center=(Lg - 0.02, -0.04, 1.0), bevel=0.003)
    straps.append(lt)
    wood_leaf = K.merge_parts(leaf, "leaf")
    iron_leaf = K.merge_parts(straps, "ironwork")
    K.uv_box(wood_leaf, 1.0, long_axis=0)
    K.uv_box(iron_leaf, 1.0)
    if ctx.destroyed:
        m = _xf((-1.3, -0.6, 0.0)) @ _xf(rot=(-68, 0, 4))
    elif ctx.worn:
        m = _xf((-1.55, 0, 0.06)) @ _xf(rot=(0, 3.2, 0))
    else:
        m = _xf((-1.55, 0, 0.1))
    for o in (wood_leaf, iron_leaf):
        o.data.transform(m)
        o.data.update()
        K.lift_min(o)
    ctx.add(wood_leaf, wood, uv=None, smooth=None, patches=0.5, moss=0.4)
    ctx.add(iron_leaf, iron, uv=None, smooth=None, wear=1.2)
    ctx.col_box((-1.72, -0.1, 0), (1.5, 0.1, 1.55))


# ============================================================================================
# Yard: machinery
# ============================================================================================

def _lugged_tyre(ctx: K.Ctx, name: str, R: float, r_rim: float, width: float, x: float, y: float, z: float, *,
                 lugs: int, flat: float = 0.0, mat: str = "tyre_rubber"):
    """Tractor drive tyre round X: smooth carcass plus chevron lugs (alternating half-bars that
    meet at the centre line) — the silhouette that says 'tractor' at fifty metres."""
    t = P.tyre(f"{name}_carcass", R - 0.035, r_rim, width, segs=26)
    parts = [t]
    for k in range(lugs):
        a = math.tau * k / lugs
        for side in (-1, 1):
            lug = K.box(f"{name}_lug", (width * 0.5, 0.06, 0.045), center=(side * width * 0.24, 0, R - 0.035 + 0.018))
            K.taper(lug, 2, lambda z: 1.0 - 0.35 * max(0.0, z - (R - 0.035)) / 0.045)
            K.place(lug, rot=(0, 0, side * 22))
            K.place(lug, rot=(math.degrees(a + side * 0.09), 0, 0))
            parts.append(lug)
    tyre = K.merge_parts(parts, name)
    K.place(tyre, (x, y, z))
    if flat > 0:
        P.flatten_tyre(tyre, z, R, amount=flat, bulge=0.035)
    ctx.add(tyre, mat, uv="cyl", uv_axis=0, uv_scale=1.0, smooth=35, wear=0.6, low=0.8, low_h=0.3)
    return tyre


def farm_tractor_wreck(ctx: K.Ctx) -> None:
    """Abandoned 1950s row-crop tractor, nose to -Y: lugged rear drive wheels on dished steel
    rims, narrow front axle, long hood over the engine, grille shell with headlamps, exhaust and
    air-intake stacks, steering wheel, pan seat on its spring, curved fenders, drawbar. Worn:
    paint gone to rust, the left rear tyre flat, the right hood side panel missing (engine
    showing). Destroyed: burnt out, a front wheel off and lying in the grass."""
    paint = "farm_tractor_red" if not ctx.destroyed else "car_burnt"
    cream = "farm_tractor_cream" if not ctx.destroyed else "car_burnt"
    iron = "car_rust" if ctx.worn else "farm_iron_black"
    RR, rr_rim, rw = 0.66, 0.42, 0.33
    rear_y, rear_x = 0.62, 0.78
    FR, fr_rim, fw = 0.31, 0.19, 0.14
    front_y, front_x = -1.32, 0.52
    # Rear wheels: lugged tyres on dished cream rims.
    for side in (-1, 1):
        flat = 0.42 if (ctx.worn and side < 0) else 0.0
        _lugged_tyre(ctx, f"rtyre{side}", RR, rr_rim, rw, side * rear_x, rear_y, RR, lugs=18, flat=flat,
                     mat="tyre_rubber" if not ctx.destroyed else "car_burnt")
        rim = P.steel_rim(f"rrim{side}", rr_rim, rw * 0.92, segs=18, dish=0.06)
        # steel_rim's dished face comes out on +X: turn the left one round so both face outward.
        if side < 0:
            K.place(rim, rot=(0, 0, 180))
        ctx.add(rim, cream, uv="cyl", uv_axis=0, smooth=40, wear=1.1, at=((side * rear_x, rear_y, RR), None))
        hub = K.cyl(f"rhub{side}", 0.11, 0.16, segs=12, axis="X", center=(side * (rear_x - 0.12), rear_y, RR))
        ctx.add(hub, iron, uv="cyl", uv_axis=0, smooth=40, wear=1.2)
        # Axle end and the wheel-centre nuts on the outer face (its centre stands 5.6 cm proud).
        face = rw * 0.92 / 2 - 0.06 * 1.6
        axle_end = K.cyl(f"raxle{side}", 0.065, 0.07, segs=12, axis="X", center=(side * (rear_x + face + 0.035), rear_y, RR))
        ctx.add(axle_end, iron, uv="cyl", uv_axis=0, smooth=40, wear=1.2)
        for k in range(8):
            a = math.tau * k / 8
            nut = K.cyl("nut", 0.013, 0.03, segs=6, axis="X", center=(side * (rear_x + face + 0.012), rear_y + math.cos(a) * 0.09,
                                                                      RR + math.sin(a) * 0.09))
            ctx.add(nut, iron, wear=1.4)
    # Front wheels (the right one off its spindle when destroyed).
    for side in (-1, 1):
        ft = P.tyre(f"ftyre{side}", FR, fr_rim, fw, segs=18)
        for k in range(3):
            ft2 = K.lathe("rib", [(FR - 0.004, -0.004), (FR + 0.008, -0.002), (FR + 0.008, 0.002), (FR - 0.004, 0.004)], segs=18,
                          close_profile=True)
            K.place(ft2, rot=(0, 90, 0))
            K.place(ft2, ((k - 1) * 0.04, 0, 0))
            ft = K.merge_parts([ft, ft2], f"ftyre{side}")
        frim = P.steel_rim(f"frim{side}", fr_rim, fw * 0.9, segs=14, dish=0.03)
        fhub = K.cyl(f"fhub{side}", 0.045, 0.05, segs=10, axis="X", center=(fw * 0.9 / 2 - 0.03 * 1.6 + 0.025, 0, 0))
        frim = K.merge_parts([frim, fhub], f"frim{side}")
        if side < 0:
            K.place(frim, rot=(0, 0, 180))
        if ctx.destroyed and side > 0:
            loc, rot = (1.25, -1.6, fw / 2 + 0.005), (0, 90, 0)
            ft_m = _xf(loc) @ _xf(rot=(0, 90, 12))
            for o, m2 in ((ft, "car_burnt"), (frim, "car_burnt")):
                o.data.transform(ft_m)
                o.data.update()
                K.lift_min(o)
                ctx.add(o, m2, uv="cyl", uv_axis=2, smooth=35)
            continue
        ctx.add(ft, "tyre_rubber" if not ctx.destroyed else "car_burnt", uv="cyl", uv_axis=0, smooth=35, wear=0.6,
                at=((side * front_x, front_y, FR), None))
        ctx.add(frim, cream, uv="cyl", uv_axis=0, smooth=40, wear=1.1, at=((side * front_x, front_y, FR), None))
    # Front axle beam, spindles, steering arms.
    axle = K.box("faxle", (front_x * 2 - 0.12, 0.09, 0.1), center=(0, front_y, FR + 0.08), bevel=0.01)
    ctx.add(axle, paint, long_axis=0, smooth=None, wear=1.1)
    for side in (-1, 1):
        if ctx.destroyed and side > 0:
            continue
        kp = K.cyl("kingpin", 0.03, 0.22, segs=8, center=(side * (front_x - 0.07), front_y, FR + 0.06))
        ctx.add(kp, iron, uv="cyl", smooth=40)
    # Rear axle housing + transmission (between the drive wheels).
    trans = K.box("trans", (0.62, 0.72, 0.6), center=(0, rear_y - 0.12, RR + 0.02), bevel=0.05, bevel_segs=2)
    ctx.add(trans, paint, smooth=None, wear=1.0)
    for side in (-1, 1):
        at = K.cyl(f"axletube{side}", 0.075, rear_x - 0.36, segs=12, axis="X", center=(side * (0.31 + (rear_x - 0.36) / 2), rear_y, RR),
                   r_top=0.06)
        ctx.add(at, paint, uv="cyl", uv_axis=0, smooth=40, wear=1.0)
        bell = K.lathe(f"bell{side}", [(0.0, 0.0), (0.16, 0.0), (0.15, 0.08), (0.09, 0.12), (0.0, 0.12)], segs=14)
        K.place(bell, rot=(0, side * 90, 0))
        ctx.add(bell, paint, uv="cyl", uv_axis=0, smooth=40, wear=1.0, at=((side * 0.3, rear_y, RR), None))
    # Engine block and hood.
    eng = K.box("engine", (0.42, 1.25, 0.5), center=(0, -0.62, FR + 0.42), bevel=0.03)
    ctx.add(eng, iron if ctx.worn else paint, smooth=None, wear=1.2)
    hood_rings = []
    for k, y in enumerate((-1.42, -1.1, -0.6, -0.1, 0.18)):
        wtop = 0.24 if k < 4 else 0.26
        z0, z1 = 1.04, 1.36 + 0.02 * k
        ring = [(-wtop, y, z0)] + [(math.cos(math.pi * (1 - i / 9)) * wtop, y, z1 - 0.07 + math.sin(math.pi * (1 - i / 9)) * 0.07)
                                     for i in range(10)] + [(wtop, y, z0)]
        hood_rings.append(ring)
    hood = K.loft("hood", hood_rings, closed_ring=True, cap_start=True, cap_end=True)
    if ctx.worn:
        # The right side panel is gone: cut the hood above the frame on +X.
        K.delete_faces(hood, lambda c, n: c.x > 0.05 and n.x > 0.5 and c.z < 1.3 and -1.3 < c.y < 0.05)
        K.solidify(hood, 0.006)
        for k in range(4):
            cylp = K.cyl("cyl_head", 0.06, 0.2, segs=10, center=(0.12, -1.05 + k * 0.24, FR + 0.72))
            ctx.add(cylp, iron, uv="cyl", smooth=40, wear=1.3)
    ctx.add(hood, paint, uv="box", uv_scale=1.0, smooth=35, wear=1.0, patches=0.6)
    tank_cap = K.cyl("fuelcap", 0.045, 0.05, segs=10, center=(0, -0.25, 1.43))
    ctx.add(tank_cap, iron, uv="cyl", smooth=40)
    # Grille shell with bars, headlamps on brackets.
    shell = K.box("grille_shell", (0.56, 0.12, 0.84), center=(0, -1.5, FR + 0.6), bevel=0.05, bevel_segs=2)
    ctx.add(shell, paint, smooth=40, wear=1.1)
    for k in range(9):
        bar = K.box("grille_bar", (0.42, 0.03, 0.022), center=(0, -1.565, FR + 0.3 + k * 0.07), bevel=0.003)
        ctx.add(bar, cream, wear=1.3)
    for side in (-1, 1):
        lamp = K.lathe("lamp", [(0.0, 0.0), (0.075, 0.0), (0.08, 0.05), (0.065, 0.1), (0.0, 0.11)], segs=12)
        K.place(lamp, rot=(-90, 0, 0))
        ctx.add(lamp, cream, uv="cyl", uv_axis=1, smooth=40, wear=1.2, at=((side * 0.38, -1.42, FR + 0.98), None))
        lens = K.cyl("lens", 0.068, 0.01, segs=12, axis="Y", center=(side * 0.38, -1.425, FR + 0.98))
        if not ctx.worn:
            ctx.add(lens, "lens_clear", uv="cyl", uv_axis=1, smooth=40, ao=False)
        brk = K.box("lampbracket", (0.16, 0.03, 0.03), center=(side * 0.3, -1.4, FR + 0.93))
        ctx.add(brk, iron)
    # Stacks.
    ex = K.tube("exhaust", [(0.12, -0.85, 1.38), (0.12, -0.85, 1.75), (0.12, -0.83, 1.95)], 0.032, segs=10)
    ctx.add(ex, "car_rust", uv="cyl", smooth=45, wear=1.0)
    cap = K.lathe("raincap", [(0.0, 0.0), (0.05, 0.0), (0.05, 0.012), (0.0, 0.02)], segs=10)
    ctx.add(cap, "car_rust", smooth=40, at=((0.12, -0.83, 1.96), (0, -35 if not ctx.worn else -80, 0)))
    air = K.tube("intake", [(-0.12, -0.95, 1.38), (-0.12, -0.95, 1.62)], 0.026, segs=10)
    ctx.add(air, paint, uv="cyl", smooth=45)
    cup = K.cyl("cleaner", 0.065, 0.12, segs=12, center=(-0.12, -0.95, 1.68))
    ctx.add(cup, iron, uv="cyl", smooth=40, wear=1.2)
    # Steering column and wheel.
    col = K.tube("column", [(0, 0.12, 1.36), (0, 0.32, 1.48), (0, 0.48, 1.56)], 0.028, segs=8)
    ctx.add(col, iron, uv="cyl", smooth=40)
    sw_parts = [K.tube("swrim", [(0.2 * math.cos(math.tau * i / 20), 0.2 * math.sin(math.tau * i / 20), 0.0) for i in range(20)],
                       0.014, segs=6, closed=True)]
    for k in range(3):
        a = math.tau * k / 3 + 0.3
        sw_parts.append(K.tube("spoke", [(0, 0, 0), (0.19 * math.cos(a), 0.19 * math.sin(a), 0)], 0.009, segs=5))
    sw = K.merge_parts(sw_parts, "steering")
    K.place(sw, rot=(-58, 0, 0))
    ctx.add(sw, "plastic_black" if not ctx.destroyed else "car_burnt", uv="cyl", smooth=40, wear=0.8, at=((0, 0.5, 1.57), None))
    # Seat on its spring arm.
    arm = K.tube("seatarm", [(0, 0.35, RR + 0.28), (0, 0.72, RR + 0.36), (0, 0.98, RR + 0.5)], [0.03, 0.026, 0.022], segs=6)
    ctx.add(arm, iron, smooth=40, wear=1.0)
    seat = K.lathe("seat", [(0.0, 0.0), (0.2, 0.0), (0.23, 0.04), (0.235, 0.09), (0.215, 0.1), (0.19, 0.045), (0.0, 0.035)], segs=16)
    K.place(seat, scale=(1.0, 0.88, 1.0))
    K.solidify(seat, 0.006)
    ctx.add(seat, paint if not ctx.worn else "car_rust", uv="cyl", smooth=40, wear=1.2, at=((0, 1.02, RR + 0.5), (-8, 0, 0)))
    # Fenders over the drive wheels.
    for side in (-1, 1):
        pts = []
        for i in range(12):
            a = math.radians(-10 + 125 * i / 11)
            pts.append((side * rear_x, rear_y + math.cos(a) * (RR + 0.09) * -1, RR + math.sin(a) * (RR + 0.09)))
        prof = [(-rw * 0.62, 0.0), (rw * 0.62, 0.0), (rw * 0.62, 0.01), (-rw * 0.62, 0.01)]
        fender = K.sweep(f"fender{side}", pts, prof, up=(1, 0, 0))
        lip = K.tube("lip", [(p[0] + side * rw * 0.62, p[1], p[2]) for p in pts], 0.012, segs=5)
        fl = K.merge_parts([fender, lip], f"fender{side}")
        if ctx.worn and side < 0:
            K.dent(fl, (side * (rear_x + 0.15), rear_y - 0.3, RR + 0.62), 0.25, 0.06)
        ctx.add(fl, paint, uv="box", smooth=35, wear=1.0)
        step = K.box("platform", (0.22, 0.5, 0.025), center=(side * 0.42, rear_y - 0.55, RR - 0.05))
        ctx.add(step, iron, wear=1.0)
    # Drawbar and hitch.
    db = K.box("drawbar", (0.12, 0.6, 0.04), center=(0, rear_y + 0.55, 0.42), bevel=0.006)
    ctx.add(db, iron, wear=1.2)
    pin = K.cyl("hitchpin", 0.018, 0.12, segs=8, center=(0, rear_y + 0.8, 0.46))
    ctx.add(pin, iron)
    ctx.col_box((-1.0, -1.62, 0), (1.0, 1.25, 1.55))


def farm_plough(ctx: K.Ctx) -> None:
    """Two-bottom moldboard plough left where it was unhitched: curved beams from the clevis to
    each bottom (share, twisted moldboard, landside), rolling coulters, a spoked gauge wheel and
    the lift lever on its quadrant. Rust everywhere except the polished curve of the moldboards."""
    rust = "car_rust"
    blade = "farm_steel_blade"
    parts_rust = []
    for k, (bx, by) in enumerate(((-0.24, 0.05), (0.2, 0.62))):
        pts = []
        for i in range(9):
            t = i / 8
            y = -1.05 + (by - -1.05) * t
            z = 0.5 * (1 - t) ** 1.2 + 0.62 * math.sin(math.pi * t) * 0.6 + 0.12
            x = (bx * 0.4) * (1 - t) + bx * t
            pts.append((x, y, z))
        beam = K.sweep(f"beam{k}", pts, [(-0.025, -0.05), (0.025, -0.05), (0.025, 0.05), (-0.025, 0.05)])
        parts_rust.append(beam)
        shank = K.box("shank", (0.05, 0.08, 0.32), center=(bx, by + 0.03, 0.26), bevel=0.006)
        parts_rust.append(shank)
        # Bottom: share point, landside, and a twisted moldboard sheet.
        share = K.prism("share", [(0.0, 0.0), (0.34, 0.0), (0.0, 0.06)], 0.012, plane="XY", offset=0.012)
        K.place(share, rot=(0, 0, -62))
        K.place(share, (bx - 0.02, by - 0.12, 0.0))
        ctx.add(share, blade, smooth=None, wear=1.0)
        land = K.box("landside", (0.02, 0.5, 0.11), center=(bx - 0.03, by + 0.12, 0.06))
        parts_rust.append(land)
        mb = K.quad_sheet("moldboard", (0, 0, 0), (0.36, 0, 0), (0.36, 0, 0.3), (0, 0, 0.3), 6, 4)

        def twist(co: Vector) -> Vector:
            u = co.x / 0.36
            v = co.z / 0.3
            ang = math.radians(25 + 55 * u + 20 * v * u)
            return Vector((co.x * 0.9, -0.12 + math.sin(ang) * 0.18 * u + 0.14 * v * u, co.z + 0.02 * u))
        K.map_verts(mb, twist)
        K.solidify(mb, 0.008)
        ctx.add(mb, blade, uv="box", uv_scale=1.0, smooth=40, wear=1.1, at=((bx, by + 0.06, 0.02), (0, 0, 8)))
        # Rolling coulter ahead of the bottom.
        disc = K.cyl("coulter", 0.2, 0.008, segs=20, axis="X", center=(0, 0, 0))
        cpost = K.box("coulter_post", (0.03, 0.04, 0.3), center=(0, -0.03, 0.15))
        hub = K.cyl("coulter_hub", 0.035, 0.06, segs=8, axis="X", center=(0, 0, 0))
        ctx.add(disc, blade, uv="cyl", uv_axis=0, smooth=40, wear=1.0, at=((bx - 0.04, by - 0.42, 0.2), (0, 0, 0)))
        ctx.add(K.merge_parts([cpost, hub], "coulter_mount"), rust, at=((bx - 0.04, by - 0.42, 0.2), None))
    cross = K.box("crossbar", (0.6, 0.06, 0.06), center=(0, -0.38, 0.58), bevel=0.005)
    parts_rust.append(cross)
    clevis = K.box("clevis", (0.16, 0.12, 0.05), center=(-0.05, -1.08, 0.6), bevel=0.006)
    parts_rust.append(clevis)
    # Gauge wheel on a stub arm.
    wheel_parts = [K.tube("gw_rim", [(0.0, 0.25 * math.cos(math.tau * i / 22), 0.25 * math.sin(math.tau * i / 22)) for i in range(22)],
                          0.012, segs=5, closed=True, flat=(1.0, 2.2))]
    for k in range(8):
        a = math.tau * k / 8
        wheel_parts.append(K.tube("gw_spoke", [(0, 0, 0), (0, 0.24 * math.cos(a), 0.24 * math.sin(a))], 0.008, segs=4))
    wheel_parts.append(K.cyl("gw_hub", 0.04, 0.08, segs=8, axis="X"))
    gw = K.merge_parts(wheel_parts, "gauge_wheel")
    ctx.add(gw, rust, uv="cyl", uv_axis=0, smooth=40, at=((0.48, -0.3, 0.25), None))
    arm = K.tube("gw_arm", [(0.43, -0.3, 0.25), (0.3, -0.36, 0.45), (0.1, -0.38, 0.58)], 0.02, segs=6)
    parts_rust.append(arm)
    lever = K.tube("lever", [(0.12, -0.5, 0.6), (0.18, -0.38, 1.05)], 0.016, segs=6)
    quad = K.tube("quadrant", [(0.12, -0.6 + 0.2 * math.cos(a), 0.62 + 0.2 * math.sin(a)) for a in [math.radians(20 + 9 * i) for i in range(12)]],
                  0.008, segs=4, flat=(1.0, 2.5))
    parts_rust += [lever, quad]
    rr = K.merge_parts(parts_rust, "frame")
    ctx.add(rr, rust, uv="box", smooth=35, wear=1.0, patches=0.6)
    ctx.col_box((-0.45, -1.15, 0), (0.75, 0.8, 0.75))


# ============================================================================================
# Yard: structures and fixtures
# ============================================================================================

def farm_water_trough(ctx: K.Ctx) -> None:
    """Oval galvanised stock tank (2.4 x 0.78 x 0.6): ribbed walls, rolled top rim, a drain plug,
    green water with a skin of leaves and scum. Worn: dented, rust bleeding through, the water
    low and black. Destroyed: shoved off its footing on its side, empty, rusted through."""
    L, Wd, H = 2.4, 0.78, 0.6
    rad = Wd / 2
    straight = L - Wd

    def outline(scale: float = 1.0, n_arc: int = 9):
        pts = []
        for i in range(n_arc):
            a = -math.pi / 2 + math.pi * i / (n_arc - 1)
            pts.append((straight / 2 + math.cos(a) * rad * scale, math.sin(a) * rad * scale))
        for k in range(1, 4):
            pts.append((straight / 2 - straight * k / 4, rad * scale))
        for i in range(n_arc):
            a = math.pi / 2 + math.pi * i / (n_arc - 1)
            pts.append((-straight / 2 + math.cos(a) * rad * scale, math.sin(a) * rad * scale))
        for k in range(1, 4):
            pts.append((-straight / 2 + straight * k / 4, -rad * scale))
        return pts
    # Wall rings bottom -> top: two pressed ribs stiffen the sheet (and give the wear and rust
    # vertex colours some resolution up the side).
    rings = [(0.0, 0.97), (0.08, 1.0)]
    for zc in (0.2, 0.4):
        rings += [(zc - 0.035, 1.0), (zc, 1.014), (zc + 0.035, 1.0)]
    rings.append((H - 0.02, 1.0))
    wall = K.loft("wall", [[(x, y, z) for x, y in outline(s)] for z, s in rings], closed_ring=True, cap_start=True,
                  cap_end=False)
    K.solidify(wall, 0.004, offset=-1.0)
    rim = K.tube("rim", [(x * 1.004, y * 1.012, H - 0.01) for x, y in outline(1.0)], 0.014, segs=6, closed=True)
    plug = K.cyl("drain", 0.03, 0.03, segs=8, axis="X", center=(L / 2 - 0.01, 0, 0.06))
    tank = K.merge_parts([wall, rim, plug], "tank")
    if ctx.worn:
        dr = ctx.drnd("dents")
        for k in range(4):
            K.dent(tank, (dr.uniform(-0.8, 0.8), -rad * dr.choice((-1, 1)), dr.uniform(0.15, 0.45)), 0.18, 0.025)
    water_z = 0.46 if ctx.clean else 0.3
    if ctx.destroyed:
        m = _xf((0, 0.1, rad + 0.02)) @ _xf(rot=(-84, 0, 3))
        tank.data.transform(m)
        tank.data.update()
        K.drop_to_ground(tank)
    # Box UVs (the sides run along X): a cylindrical projection round an oval smears the zinc
    # pattern along the straight sides.
    ctx.add(tank, "metal_galvanized", uv="box", uv_scale=1.5, smooth=40, wear=1.0, patches=0.6, low=0.6, low_h=0.25)
    if not ctx.destroyed:
        surf = K.loft("water", [[(x, y, water_z) for x, y in outline(0.985)]], closed_ring=True, cap_start=False, cap_end=True,
                      recalc=False)
        ctx.add(surf, "farm_trough_water", uv="planar", uv_axis=2, uv_scale=0.5, smooth=None, ao=False)
        r = ctx.rnd("leaves")
        for k in range(10):
            lf = K.box("leaf", (0.05, 0.03, 0.002))
            ctx.add(lf, "farm_hay_old", at=((r.uniform(-1.0, 1.0), r.uniform(-0.3, 0.3), water_z + 0.002), (0, 0, r.uniform(0, 180))))
        ctx.col_box((-L / 2, -rad, 0), (L / 2, rad, H))
    else:
        ctx.col_box((-L / 2, -0.3, 0), (L / 2, 0.5, Wd))


def farm_chicken_coop(ctx: K.Ctx) -> None:
    """Board-and-batten hen house on legs (1.4 x 0.9 floor, shed roof of corrugated tin), pop hole
    with a cleated ramp, nesting boxes bumped out on the west end under a hinged lid, a chicken-wire
    vent, feathers on the ramp. Worn: pop door hanging from one hinge, a roof sheet lifted.
    Destroyed: a leg rotted through, the coop slumped onto one corner, the roof caved."""
    paint = "farm_wood_barn_red"
    raw = "farm_wood_grey"
    tin = "farm_corrugated_galv" if ctx.clean else "farm_corrugated_rust"
    Lx, Dy, floor_z = 1.4, 0.9, 0.5
    h_front, h_back = 0.85, 1.12
    group_paint, group_raw = [], []
    for sx in (-1, 1):
        for sy in (-1, 1):
            leg = K.box("leg", (0.07, 0.07, floor_z), center=(sx * (Lx / 2 - 0.05), sy * (Dy / 2 - 0.05), floor_z / 2), bevel=0.006)
            group_raw.append(leg)
    group_raw.append(K.box("floor", (Lx, Dy, 0.04), center=(0, 0, floor_z + 0.02), bevel=0.004))
    # Front and back walls: vertical boards with battens over the joints.
    for side, y, h in (("front", -Dy / 2, h_front), ("back", Dy / 2, h_back)):
        n = 7
        bw = Lx / n
        for k in range(n):
            x = -Lx / 2 + bw * (k + 0.5)
            if side == "front" and k == 5:
                # Pop hole: the board stops above it.
                b = K.box("board", (bw - 0.004, 0.018, h - 0.33), center=(x, y, floor_z + 0.04 + 0.33 + (h - 0.33) / 2), bevel=0.002)
            else:
                b = K.box("board", (bw - 0.004, 0.018, h), center=(x, y, floor_z + 0.04 + h / 2), bevel=0.002)
            group_paint.append(b)
            if k:
                bat = K.box("batten", (0.035, 0.012, h), center=(-Lx / 2 + bw * k, y + math.copysign(0.014, y), floor_z + 0.04 + h / 2))
                group_paint.append(bat)
    for sx in (-1, 1):
        poly = [(-Dy / 2, floor_z + 0.04), (Dy / 2, floor_z + 0.04), (Dy / 2, floor_z + 0.04 + h_back), (-Dy / 2, floor_z + 0.04 + h_front)]
        sidep = K.prism("side", poly, 0.018, plane="YZ", offset=sx * (Lx / 2 - 0.009))
        group_paint.append(sidep)
    # Chicken-wire vent high on the east end.
    vent = K.quad_sheet("vent", (Lx / 2 + 0.012, -0.25, floor_z + 0.62), (Lx / 2 + 0.012, 0.25, floor_z + 0.62),
                        (Lx / 2 + 0.012, 0.25, floor_z + 0.9), (Lx / 2 + 0.012, -0.25, floor_z + 0.9))
    ctx.add(vent, "farm_chicken_wire", uv="planar", uv_axis=0, uv_scale=3.0, ao=False)
    # Nesting boxes on the west end.
    nb = K.box("nestbox", (0.3, 0.7, 0.32), center=(-Lx / 2 - 0.15, 0, floor_z + 0.2), bevel=0.004)
    group_paint.append(nb)
    lid = K.box("nestlid", (0.36, 0.76, 0.02), center=(0, 0, 0), bevel=0.003)
    lid_rot = (0, -18 if not ctx.worn else -52, 0)
    ctx.add(lid, raw, long_axis=1, smooth=None, patches=0.5, moss=0.4, at=((-Lx / 2 - 0.17, 0, floor_z + 0.38), lid_rot))
    # Roof: one corrugated sheet per half, ridges running down the slope (texture along Y).
    slope = math.degrees(math.atan2(h_back - h_front, Dy))
    for k, x in enumerate((-Lx / 4 - 0.03, Lx / 4 + 0.03)):
        sh = K.box("roofsheet", (Lx / 2 + 0.12, Dy + 0.3, 0.012), center=(0, 0, 0))
        rot = (slope, 0, 0)
        loc = (x, 0, floor_z + 0.04 + (h_front + h_back) / 2 + 0.03)
        if ctx.worn and k == 1:
            rot = (slope - 9, 3, 0)
            loc = (x, 0.05, loc[2] + 0.06)
        if ctx.destroyed:
            rot = (slope + (14 if k else -6), -12 if k else 8, 0)
            loc = (x, 0, loc[2] - 0.25)
        ctx.add(sh, tin, uv="box", long_axis=1, uv_scale=1.0, smooth=None, wear=1.0, at=(loc, rot))
    # Pop door and ramp.
    door = K.box("popdoor", (0.2, 0.016, 0.3), center=(0, 0, 0.15), bevel=0.002)
    pop_x = -Lx / 2 + (Lx / 7) * 5.5
    if ctx.worn:
        ctx.add(door, raw, long_axis=2, at=((pop_x - 0.05, -Dy / 2 - 0.04, floor_z + 0.02), (0, 28, 12)))
    else:
        ctx.add(door, raw, long_axis=2, at=((pop_x, -Dy / 2 - 0.02, floor_z + 0.04), (82, 0, 0)))
    rlen = 0.9
    ramp = _board("ramp", rlen, 0.22, 0.022, ctx.rnd("ramp"), cuts=4)
    cleats = [K.box("cleat", (0.02, 0.2, 0.018), center=(-rlen / 2 + 0.12 + k * 0.14, 0, 0.018)) for k in range(5)]
    rp = K.merge_parts([ramp] + cleats, "ramp")
    ang = math.degrees(math.asin((floor_z + 0.04) / rlen))
    K.place(rp, rot=(0, 0, 90))
    ctx.add(rp, raw, long_axis=1, smooth=None, patches=0.5, moss=0.4,
            at=((pop_x, -Dy / 2 - math.cos(math.radians(ang)) * rlen / 2, (floor_z + 0.04) / 2), (ang, 0, 0)))
    r = ctx.rnd("feathers")
    for k in range(12):
        f = K.box("feather", (0.045, 0.012, 0.002))
        K.place(f, rot=(0, 0, r.uniform(0, 180)))
        ctx.add(f, "farm_feathers", at=((r.uniform(-0.6, 0.9), -Dy / 2 - r.uniform(0.1, 0.9), 0.003), (r.uniform(-15, 15), 0, 0)))
    wood_p = K.merge_parts(group_paint, "coop_paint")
    wood_r = K.merge_parts(group_raw, "coop_raw")
    ctx.add(wood_p, paint, uv="box", long_axis=2, smooth=None, patches=0.6, low=0.4, low_h=0.6)
    ctx.add(wood_r, raw, uv="box", long_axis=2, smooth=None, patches=0.5, moss=0.4)
    if ctx.destroyed:
        # A rotten front leg gave way: the whole house slumps forward onto that corner.
        m = _xf((-Lx / 2, Dy / 2, 0.0)) @ _xf(rot=(7, 6, 0)) @ _xf((Lx / 2, -Dy / 2, 0.0))
        for o in ctx.parts:
            if o.name.startswith("feather"):
                continue
            o.data.transform(m)
            o.data.update()
    ctx.col_box((-Lx / 2 - 0.3, -Dy / 2 - 0.85, 0), (Lx / 2 + 0.05, Dy / 2 + 0.15, floor_z + h_back + 0.15))


def _strut(name: str, a: Vector, b: Vector, w: float, t: float, outward: Vector):
    """Flat bar / angle from a to b (built along X, then oriented with its face toward `outward`)."""
    d = b - a
    o = K.box(name, (d.length, w, t), bevel=0.002)
    n = outward - d.normalized() * outward.dot(d.normalized())
    if n.length < 1e-6:
        n = d.orthogonal()
    K.orient(o, d.normalized(), n.normalized(), (a + b) / 2)
    return o


def farm_windmill_pump(ctx: K.Ctx) -> None:
    """Steel-lattice windmill over the farm well: four angle-iron legs on concrete footings
    tapering to a platform 6.6 m up, girts and rod bracing on every face, the 18-blade wheel
    (2.6 m) and blank tail vane on the gear head, the pump rod down to a cast-iron pitcher pump
    on a plank well cover. Worn: blades gone, the vane folded. Destroyed: the head, wheel and
    vane torn off in a storm and lying beside the tower."""
    galv = "metal_galvanized"
    iron = "farm_iron_black"
    H, base, top = 7.0, 1.05, 0.2
    corners = [(-1, -1), (1, -1), (1, 1), (-1, 1)]

    def leg_at(z: float, c) -> Vector:
        w = base + (top - base) * (z / H)
        return Vector((c[0] * w, c[1] * w, z))
    tower = []
    for c in corners:
        tower.append(_strut("leg", leg_at(0.12, c), leg_at(H, c), 0.07, 0.07, Vector((c[0], c[1], 0))))
        foot = K.cyl("footing", 0.16, 0.34, segs=10, center=(c[0] * base, c[1] * base, 0.05))
        ctx.add(foot, "concrete_barrier", uv="cyl", smooth=40, patches=0.4, moss=0.5)
    levels = [0.55, 1.9, 3.2, 4.4, 5.5, 6.55]
    for k, z in enumerate(levels):
        for i in range(4):
            ca, cb = corners[i], corners[(i + 1) % 4]
            out = Vector(((ca[0] + cb[0]) / 2, (ca[1] + cb[1]) / 2, 0))
            tower.append(_strut("girt", leg_at(z, ca), leg_at(z, cb), 0.05, 0.008, out))
            if k + 1 < len(levels):
                z2 = levels[k + 1]
                for p0, p1 in ((leg_at(z, ca), leg_at(z2, cb)), (leg_at(z, cb), leg_at(z2, ca))):
                    tower.append(K.tube("rod", [p0 + out * 0.02, p1 + out * 0.02], 0.007, segs=4, caps=False))
    plat = []
    for i in range(4):
        ca, cb = corners[i], corners[(i + 1) % 4]
        out = Vector(((ca[0] + cb[0]) / 2, (ca[1] + cb[1]) / 2, 0))
        mid = (leg_at(6.6, ca) + leg_at(6.6, cb)) / 2 + out * 0.32
        sz = (0.95, 0.3, 0.035) if abs(out.x) < 0.5 else (0.3, 0.95, 0.035)
        plat.append(K.box("plank", sz, center=(mid.x, mid.y, 6.62), bevel=0.003))
    tw = K.merge_parts(tower, "tower")
    ctx.add(tw, galv, uv="box", uv_scale=1.0, smooth=None, wear=1.0, patches=0.6)
    pl = K.merge_parts(plat, "platform")
    ctx.add(pl, "farm_wood_grey", long_axis=0, smooth=None, patches=0.5, moss=0.4)
    rod = K.tube("pumprod", [(0, 0, 0.9), (0, 0, H)], 0.01, segs=5)
    ctx.add(rod, galv, uv="cyl", smooth=40)
    # Head, wheel and vane (built at the masthead, moved as one group if torn off).
    head_g, wheel_g, vane_g = [], [], []
    hz = H + 0.32
    head_g.append(K.cyl("turntable", 0.16, 0.12, segs=12, center=(0, 0, H + 0.06)))
    head_g.append(K.box("gearbox", (0.28, 0.55, 0.3), center=(0, -0.05, hz), bevel=0.04, bevel_segs=2))
    head_g.append(K.cyl("shaft", 0.035, 0.36, segs=8, axis="Y", center=(0, -0.45, hz)))
    head_g.append(K.cyl("hub", 0.11, 0.14, segs=12, axis="Y", center=(0, -0.62, hz)))
    n_bl = 18
    missing = {2, 3, 9} if ctx.worn and not ctx.destroyed else set()
    for k in range(n_bl):
        if k in missing:
            continue
        a = math.tau * k / n_bl
        r0, r1, w0, w1 = 0.42, 1.3, 0.12, 0.27
        bl = K.quad_sheet("blade", (r0, 0, -w0 / 2), (r1, 0, -w1 / 2), (r1, 0, w1 / 2), (r0, 0, w0 / 2), 3, 2)
        K.map_verts(bl, lambda co: Vector((co.x, 0.035 * (1.0 - (2.0 * co.z / max(1e-3, w0 + (w1 - w0) * (co.x - r0) / (r1 - r0))) ** 2), co.z)))
        K.solidify(bl, 0.003)
        K.place(bl, rot=(28, 0, 0))
        K.place(bl, rot=(0, math.degrees(a), 0))
        K.place(bl, (0, -0.68, hz))
        wheel_g.append(bl)
    for rr in (0.78, 1.3):
        wheel_g.append(K.tube("wheelrim", [(rr * math.cos(math.tau * i / 30), -0.66, hz + rr * math.sin(math.tau * i / 30)) for i in range(30)],
                              0.011, segs=4, closed=True, flat=(1.0, 2.0)))
    for k in range(6):
        a = math.tau * k / 6 + 0.17
        wheel_g.append(K.tube("arm", [(0.1 * math.cos(a), -0.62, hz + 0.1 * math.sin(a)), (1.3 * math.cos(a), -0.66, hz + 1.3 * math.sin(a))],
                              0.012, segs=4, caps=False))
    vane_g.append(K.tube("boom", [(0, 0.2, hz + 0.05), (0, 1.0, hz + 0.18), (0, 1.75, hz + 0.25)], 0.028, segs=6))
    vane = K.prism("vane", [(1.35, -0.28), (2.35, -0.42), (2.35, 0.55), (1.35, 0.42)], 0.012, plane="YZ", offset=0.0)
    K.place(vane, (0, 0, hz + 0.18))
    if ctx.worn and not ctx.destroyed:
        K.kink([vane], (0, 1.95, 0), (0, 0, 28), axis=1, blend=0.12)
    vane_g.append(vane)
    head = K.merge_parts(head_g, "head")
    wheel = K.merge_parts(wheel_g, "wheel")
    boom = K.merge_parts(vane_g[:1], "boom")
    vane_o = vane_g[1]
    K.uv_box(head, 1.0)
    K.uv_box(wheel, 1.0)
    K.uv_box(boom, 1.0)
    K.uv_box(vane_o, 1.0)
    if ctx.destroyed:
        # Torn off whole: wheel face-down beside the tower, the head and vane on their sides.
        mw = _xf((2.1, -1.6, 0.1)) @ _xf(rot=(78, 0, 25)) @ _xf((0, 0.66, -hz))
        mh = _xf((1.2, 1.4, 0.2)) @ _xf(rot=(0, 85, 40)) @ _xf((0, 0, -hz))
        for o, m in ((wheel, mw), (head, mh), (boom, mh), (vane_o, mh)):
            o.data.transform(m)
            o.data.update()
            K.lift_min(o)
    ctx.add(head, iron, uv=None, smooth=40, wear=1.1)
    ctx.add(wheel, galv, uv=None, smooth=None, wear=1.0, patches=0.6)
    ctx.add(boom, galv, uv=None, smooth=40, wear=1.0)
    ctx.add(vane_o, "paint_red", uv=None, smooth=None, wear=1.2, patches=0.7)
    # Well cover and pitcher pump at the foot of the tower.
    cover = K.box("wellcover", (1.0, 1.0, 0.08), center=(0, 0, 0.04), bevel=0.006)
    ctx.add(cover, "farm_wood_grey", long_axis=0, smooth=None, patches=0.5, moss=0.5)
    pump = K.lathe("pump", [(0.0, 0.08), (0.09, 0.08), (0.1, 0.12), (0.075, 0.18), (0.07, 0.6), (0.085, 0.64), (0.09, 0.72),
                            (0.06, 0.78), (0.0, 0.79)], segs=12)
    ctx.add(pump, iron, uv="cyl", smooth=40, wear=1.2)
    spout = K.tube("spout", [(0, -0.06, 0.58), (0, -0.2, 0.56), (0, -0.28, 0.5)], [0.035, 0.03, 0.026], segs=8)
    ctx.add(spout, iron, uv="cyl", smooth=40, wear=1.2)
    handle = K.tube("pumphandle", [(0, 0.05, 0.76), (0, 0.25, 0.8), (0, 0.55, 0.72)], [0.02, 0.018, 0.016], segs=6)
    ctx.add(handle, iron, uv="cyl", smooth=40, wear=1.2)
    for c in corners:
        ctx.col_box((c[0] * base - 0.12, c[1] * base - 0.12, 0), (c[0] * base + 0.12, c[1] * base + 0.12, 2.5))
    ctx.col_box((-0.5, -0.5, 0), (0.5, 0.5, 0.8))


def farm_grain_bin(ctx: K.Ctx) -> None:
    """Corrugated steel grain bin (3.6 m across): footing ring, ringed wall sheets with seams,
    standing-seam cone roof with a cap vent and an eave hatch, wall ladder, a bolted access door
    and an unloading spout. Worn: dented, rust streaking from every seam, a roof hatch open."""
    R, Hw, fz = 1.8, 3.4, 0.18
    wallmat = "farm_corrugated_galv" if ctx.clean else "farm_corrugated_rust"
    foot = K.cyl("footing", R + 0.14, fz, segs=28, center=(0, 0, fz / 2))
    ctx.add(foot, "concrete_barrier", uv="cyl", smooth=40, patches=0.4, moss=0.5)
    wall = K.cyl("wall", R, Hw, segs=36, center=(0, 0, fz + Hw / 2), caps=False, cuts=5)
    if ctx.worn:
        dr = ctx.drnd("dents")
        for k in range(5):
            a = dr.uniform(0, math.tau)
            K.dent(wall, (R * math.cos(a), R * math.sin(a), dr.uniform(0.6, 2.6)), dr.uniform(0.25, 0.5), 0.05)
    ctx.add(wall, wallmat, uv="cyl", uv_scale=1.0, smooth=40, wear=1.0, patches=0.6, low=0.6, low_h=0.5)
    seams = []
    for k in range(8):
        a = math.tau * k / 8 + 0.2
        seams.append(K.box("seam", (0.04, 0.012, Hw), center=(0, 0, 0)))
        K.place(seams[-1], (0, 0, fz + Hw / 2))
        K.place(seams[-1], rot=(0, 0, math.degrees(a) + 90))
        K.place(seams[-1], (R * math.cos(a) * 1.004, R * math.sin(a) * 1.004, 0))
    seams.append(K.tube("eave", [(R * 1.01 * math.cos(math.tau * i / 36), R * 1.01 * math.sin(math.tau * i / 36), fz + Hw) for i in range(36)],
                        0.02, segs=5, closed=True))
    ctx.add(K.merge_parts(seams, "seams"), "metal_galvanized", smooth=None, wear=1.1)
    roof_h = 1.25
    roof = K.cyl("roof", R + 0.16, roof_h, segs=36, center=(0, 0, fz + Hw + roof_h / 2 - 0.05), r_top=0.3, caps=False, cuts=2)
    ctx.add(roof, "metal_galvanized", uv="cyl", uv_scale=1.0, smooth=40, wear=1.0, patches=0.6, moss=0.15)
    ribs = []
    for k in range(18):
        a = math.tau * k / 18
        p0 = Vector(((R + 0.15) * math.cos(a), (R + 0.15) * math.sin(a), fz + Hw - 0.05))
        p1 = Vector((0.32 * math.cos(a), 0.32 * math.sin(a), fz + Hw + roof_h - 0.06))
        ribs.append(_strut("rib", p0, p1, 0.03, 0.02, Vector((math.cos(a), math.sin(a), 0.7))))
    cap = K.lathe("capvent", [(0.0, 0.0), (0.34, 0.0), (0.36, 0.08), (0.2, 0.2), (0.0, 0.24)], segs=16)
    K.place(cap, (0, 0, fz + Hw + roof_h - 0.08))
    ribs.append(cap)
    ctx.add(K.merge_parts(ribs, "ribs"), "metal_galvanized", smooth=None, wear=1.0)
    hatch = K.box("roofhatch", (0.5, 0.45, 0.04), center=(0, 0, 0), bevel=0.006)
    ang = math.degrees(math.atan2(roof_h, R - 0.3))
    hr = (0, -ang, 0) if not ctx.worn else (0, -ang - 55, 0)
    ctx.add(hatch, "metal_galvanized", at=((R - 0.35, 0.0, fz + Hw + 0.35), hr), wear=1.1)
    # Ladder up the front (-Y) and the access door beside it.
    lad = []
    for sx in (-0.2, 0.2):
        lad.append(K.tube("rail", [(sx, -R - 0.14, fz + 0.3), (sx, -R - 0.14, fz + Hw + 0.15)], 0.02, segs=6))
    for k in range(12):
        z = fz + 0.55 + k * 0.28
        lad.append(K.tube("rung", [(-0.2, -R - 0.14, z), (0.2, -R - 0.14, z)], 0.012, segs=5, caps=False))
    for z in (fz + 0.8, fz + 2.4):
        lad.append(K.box("standoff", (0.04, 0.14, 0.03), center=(-0.2, -R - 0.07, z)))
        lad.append(K.box("standoff", (0.04, 0.14, 0.03), center=(0.2, -R - 0.07, z)))
    ctx.add(K.merge_parts(lad, "ladder"), "metal_galvanized", smooth=None, wear=1.1)
    door = K.box("door", (0.62, 0.05, 0.82), center=(0, 0, 0), bevel=0.01)
    a = math.radians(-60)
    ctx.add(door, "metal_galvanized", at=((R * math.cos(a) * 1.01, R * math.sin(a) * 1.01, fz + 0.55), (0, 0, -60 + 90)), wear=1.1)
    for k in range(2):
        hd = K.box("doorhandle", (0.12, 0.03, 0.03))
        ctx.add(hd, "farm_iron_black", at=((R * math.cos(a) * 1.03, R * math.sin(a) * 1.03, fz + 0.35 + k * 0.4), (0, 0, 30)))
    spout = K.tube("spout", [(R * 0.9, 0.6, fz + 0.25), (R + 0.5, 0.75, fz + 0.15), (R + 0.75, 0.8, 0.35)], 0.09, segs=10)
    ctx.add(spout, "metal_galvanized", uv="cyl", smooth=40, wear=1.0)
    ctx.col_box((-R - 0.15, -R - 0.2, 0), (R + 0.15, R + 0.15, fz + Hw + roof_h))


def farm_wagon_wheel(ctx: K.Ctx) -> None:
    """Twelve-spoke wooden wagon wheel (1.1 m) with an iron tyre and banded hub, leaning back
    against a wall. Worn: silver-grey, a spoke snapped (its stub left in the felloe). Destroyed:
    lying flat in the grass with three spokes gone."""
    R, width = 0.56, 0.09
    wood = "farm_wood_grey" if ctx.worn else "farm_wood_cedar"
    iron = "car_rust" if ctx.worn else "farm_iron_black"
    broken = (3,) if (ctx.worn and not ctx.destroyed) else ((2, 3, 7) if ctx.destroyed else ())
    parts = _spoked_wheel(ctx, "wheel", R, width, 12, hub_r=0.075, mat_wood=wood, mat_iron=iron, broken=broken)
    if ctx.worn and not ctx.destroyed:
        a = math.tau * 3.5 / 12
        stub = K.box("stub", (0.16, 0.045, 0.03), center=(R - 0.13, 0, 0), bevel=0.005)
        P.break_end(stub, R - 0.2, ctx.drnd("stub"), side=-1, depth=0.04)
        K.place(stub, rot=(0, -math.degrees(a), 0))
        parts.append(ctx.add(stub, wood, long_axis=0))
    if ctx.destroyed:
        m = _xf((0, 0, width * 0.36 + 0.004)) @ _xf(rot=(90, 0, 0))
    else:
        lean = 13.0
        m = _xf((0, 0, (R + 0.004) * math.cos(math.radians(lean)) + 0.005)) @ _xf(rot=(-lean, 0, 0))
    _move(parts, m)
    if ctx.worn and not ctx.destroyed:
        sp = K.box("loose_spoke", (0.32, 0.045, 0.03), bevel=0.006)
        ctx.add(sp, wood, long_axis=0, at=((0.25, -0.35, 0.016), (0, 0, 35)))
    if ctx.destroyed:
        ctx.col_box((-R, -R, 0), (R, R, 0.12))
    else:
        ctx.col_box((-R, -0.1, 0), (R, 0.25, 2 * R))
        _recenter_y(ctx)


# ============================================================================================
# Barn
# ============================================================================================

def _sack_shape(name: str, L: float, W: float, T: float, seed: int, *, slump: float = 0.0):
    """Filled feed sack lying flat: pillowed, flattening to the sewn ends, crinkled."""
    s = K.box(name, (L, W, T), bevel=min(T * 0.45, 0.05), bevel_segs=2, cuts=(7, 5, 1))

    def f(co: Vector) -> Vector:
        tx = co.x / (L / 2)
        ty = co.y / (W / 2)
        k = max(0.22, (1.0 - 0.62 * tx ** 4) * (1.0 - 0.3 * ty ** 4))
        z = co.z * k - slump * (1.0 - ty * ty) * (1.0 if co.z > 0 else 0.4)
        return Vector((co.x, co.y * (1.0 + 0.05 * (1.0 - tx * tx)), z))
    K.map_verts(s, f)
    K.crumple(s, 0.009, scale=7.0, seed=seed)
    return s


def farm_feed_sacks(ctx: K.Ctx) -> None:
    """Three 50 lb feed sacks slumped together: two kraft multiwall bags side by side and a burlap
    sack lying across them, sewn ends with their stitch lines. Worn: damp-stained and sagging.
    Destroyed: the burlap sack slit and empty, feed spilled across the floor."""
    L, W, T = 0.68, 0.42, 0.16
    arr = [("farm_feed_sack", (0.0, -0.215, T / 2), 3.0), ("farm_feed_sack", (0.02, 0.215, T / 2), -4.0),
           ("furn_burlap", (0.0, 0.0, T + T / 2 - 0.035), 84.0)]
    for k, (mat, loc, rotz) in enumerate(arr):
        top = k == 2
        empty = top and ctx.destroyed
        s = _sack_shape(f"sack{k}", L, W, T * (0.45 if empty else 1.0), ctx.seed + k, slump=(0.05 if top else 0.02 if ctx.worn else 0.0))
        if top:
            K.bend(s, 2, -0.2, along=1)
        tab = K.box("tab", (0.05, W * 0.9, 0.014), center=(L / 2 + 0.012, 0, 0.0), bevel=0.003)
        stitch = K.tube("stitch", [(L / 2 + 0.02, -W * 0.43 + i * W * 0.86 / 10, 0.009 * (1 if i % 2 else -1)) for i in range(11)],
                        0.0022, segs=3)
        if mat == "farm_feed_sack":
            ctx.add(s, mat, uv="planar", uv_axis=2, rect=(0.0, 0.0, 1.0, 1.0), smooth=35, patches=0.45, at=(loc, (0, 0, rotz)))
        else:
            ctx.add(s, mat, uv="box", uv_scale=1.0, smooth=35, patches=0.45, at=(loc, (0, 0, rotz)))
        ctx.add(tab, mat, uv="box", smooth=None, patches=0.4, at=(loc, (0, 0, rotz)))
        ctx.add(stitch, "farm_twine", wear=0.3, at=(loc, (0, 0, rotz)))
    if ctx.destroyed:
        spill = K.blob("spill", 0.3, subdiv=2, scale=(1.6, 1.0, 0.12), center=(0.1, -0.55, 0.0), rough=0.35, seed=ctx.seed + 7)
        ctx.add(spill, "farm_grain", smooth=40)
        r = ctx.drnd("kernels")
        for k in range(18):
            g = K.blob("kernel", 0.006, subdiv=1, scale=(1.4, 1.0, 0.8))
            ctx.add(g, "farm_grain", smooth=40, at=((r.uniform(-0.5, 0.6), r.uniform(-0.95, -0.4), 0.004), (0, 0, r.uniform(0, 180))))
    ctx.col_box((-0.38, -0.46, 0), (0.42, 0.46, 0.42))


def farm_feed_bin(ctx: K.Ctx) -> None:
    """Barn-red feed bin (1.2 x 0.62 x 0.78) of lapped boards on skids, with a sloping lid on
    strap hinges, a hasp, and oats inside. Worn: paint worn to grey wood, the lid propped open.
    Destroyed: lid thrown off, a front board kicked in."""
    L, D, H = 1.2, 0.62, 0.78
    t = 0.022
    mat = "farm_wood_barn_red"
    iron = "farm_iron_black"
    drop = 0.12
    boards = []
    for side, y, hh in (("front", -D / 2 + t / 2, H - drop), ("back", D / 2 - t / 2, H)):
        n = 4
        bh = (hh - 0.06) / n
        for k in range(n):
            if ctx.destroyed and side == "front" and k == 2:
                continue
            # Nine loops along each board: the paint wear is vertex colour, and on 30 cm quads it
            # smeared into streaks across the front.
            b = _board(f"{side}{k}", L, bh + 0.012, t, ctx.rnd(f"{side}{k}"), cuts=9)
            K.orient(b, "x", "-y" if side == "front" else "y", (0, y + (-0.004 if side == "front" else 0.004) * (k % 2), 0.06 + bh * (k + 0.5)))
            boards.append(b)
    for sx in (-1, 1):
        poly = [(-D / 2, 0.06), (D / 2, 0.06), (D / 2, H), (-D / 2, H - drop)]
        boards.append(K.prism("end", poly, t, plane="YZ", offset=sx * (L / 2 - t / 2)))
        for y in (-D / 2 + 0.05, D / 2 - 0.05):
            boards.append(K.box("cleat", (0.03, 0.06, H - 0.12), center=(sx * (L / 2 + 0.01), y, 0.06 + (H - 0.12) / 2), bevel=0.003))
    for y in (-D / 2 + 0.08, D / 2 - 0.08):
        boards.append(K.box("skid", (L + 0.06, 0.07, 0.06), center=(0, y, 0.03), bevel=0.006))
    body = K.merge_parts(boards, "bin")
    ctx.add(body, mat, uv="box", long_axis=0, smooth=None, patches=0.45, low=0.45, low_h=0.25)
    fill = K.box("oats", (L - 0.06, D - 0.06, 0.02), center=(0, 0, 0.42))
    K.noise_disp(fill, 0.02, scale=4.0, seed=ctx.seed)
    ctx.add(fill, "farm_grain", smooth=40)
    if ctx.destroyed:
        kicked = _board("kicked", L * 0.55, (H - drop - 0.06) / 4, t, ctx.drnd("kick"), cuts=2)
        P.break_end(kicked, 0.1, ctx.drnd("kickb"), side=1, depth=0.06)
        ctx.add(kicked, mat, long_axis=0, at=((0.1, -0.5, 0.012), (0, 0, 12)))
    # Lid: boards on two battens, hinged along the back top edge.
    lid_parts = []
    lw = D + 0.06
    for k in range(3):
        lb = _board(f"lid{k}", L + 0.06, lw / 3 - 0.004, t, ctx.rnd(f"lid{k}"), cuts=2)
        K.place(lb, (0, -lw / 2 + lw / 6 + k * lw / 3, t / 2))
        lid_parts.append(lb)
    for x in (-L / 2 + 0.1, L / 2 - 0.1):
        lid_parts.append(K.box("lidbatten", (0.05, lw - 0.08, 0.02), center=(x, 0, -0.01)))
    lid = K.merge_parts(lid_parts, "lid")
    K.uv_box(lid, 1.0, long_axis=0)
    hinges = []
    for x in (-0.35, 0.35):
        hinges.append(K.box("strap", (0.035, 0.3, 0.006), center=(x, lw / 2 - 0.15, t + 0.003)))
        hinges.append(K.cyl("knuckle", 0.012, 0.06, segs=6, axis="X", center=(x, lw / 2, t * 0.5)))
    hinges.append(K.box("hasp", (0.05, 0.1, 0.006), center=(0, -lw / 2 + 0.03, t + 0.003)))
    hw = K.merge_parts(hinges, "hinges")
    K.uv_box(hw, 1.0)
    slope = math.degrees(math.atan2(drop, D))
    # Lid local frame: hinge line along X at the back edge (y = +lw/2).
    if ctx.destroyed:
        m = _xf((-0.6, 0.75, 0.04)) @ _xf(rot=(176, 0, 18))
    elif ctx.worn:
        m = _xf((0, D / 2, H)) @ _xf(rot=(slope - 60, 0, 0)) @ _xf((0, -lw / 2, 0))
    else:
        m = _xf((0, D / 2, H)) @ _xf(rot=(slope, 0, 0)) @ _xf((0, -lw / 2, 0))
    for o in (lid, hw):
        o.data.transform(m)
        o.data.update()
    if ctx.destroyed:
        K.lift_min(lid)
        K.lift_min(hw)
    ctx.add(lid, mat, uv=None, smooth=None, patches=0.6)
    ctx.add(hw, iron, uv=None, smooth=None, wear=1.2)
    staple = K.box("staple", (0.04, 0.012, 0.05), center=(0, -D / 2 - 0.008, H - drop - 0.04))
    ctx.add(staple, iron, wear=1.2)
    ctx.col_box((-L / 2 - 0.03, -D / 2, 0), (L / 2 + 0.03, D / 2, H))


def farm_milk_can(ctx: K.Ctx) -> None:
    """Ten-gallon galvanised milk can with a mushroom lid, rolled beads and shoulder handles.
    Worn: dented and rusting through the zinc. Destroyed: knocked over, the lid rolled away."""
    prof = [(0.0, 0.0), (0.15, 0.0), (0.162, 0.012), (0.162, 0.03), (0.157, 0.04), (0.157, 0.4), (0.15, 0.43), (0.128, 0.47),
            (0.108, 0.505), (0.098, 0.53), (0.098, 0.555), (0.112, 0.565), (0.112, 0.58)]
    body = K.lathe("can", prof, segs=20, cap_top=False)
    beads = [_hoop("bead", 0.161, 0.03, tube_r=0.006, segs=20), _hoop("bead", 0.159, 0.385, tube_r=0.006, segs=20)]
    handles = []
    for sx in (-1, 1):
        handles.append(K.tube("handle", [(sx * 0.12, -0.045, 0.455), (sx * 0.19, -0.04, 0.49), (sx * 0.205, 0.0, 0.5),
                                         (sx * 0.19, 0.04, 0.49), (sx * 0.12, 0.045, 0.455)], 0.0085, segs=6))
    can = K.merge_parts([body] + beads + handles, "milkcan")
    lid = K.lathe("lid", [(0.0, 0.545), (0.094, 0.545), (0.097, 0.565), (0.122, 0.58), (0.124, 0.595), (0.07, 0.625), (0.0, 0.63)],
                  segs=20)
    K.place(lid, (0, 0, -0.545))
    # UVs upright, before the can is knocked over; 2.5x so the zinc spangle reads at can scale.
    K.uv_cyl(can, axis=2, scale=2.5)
    if ctx.worn:
        dr = ctx.drnd("dents")
        for k in range(3):
            a = dr.uniform(0, math.tau)
            K.dent(can, (0.16 * math.cos(a), 0.16 * math.sin(a), dr.uniform(0.1, 0.35)), dr.uniform(0.05, 0.09), 0.012)
    if ctx.destroyed:
        m = _xf((0.0, 0.0, 0.162)) @ _xf(rot=(0, 92, 18)) @ _xf((0, 0, -0.29))
        can.data.transform(m)
        can.data.update()
        K.lift_min(can)
        ctx.add(can, "metal_galvanized", uv=None, smooth=40, wear=1.0, patches=0.6)
        ctx.add(lid, "metal_galvanized", uv="cyl", uv_scale=2.5, smooth=40, wear=1.0, at=((0.45, -0.25, 0.03), (12, 75, 0)))
        ctx.col_box((-0.32, -0.2, 0), (0.32, 0.2, 0.33))
        return
    ctx.add(can, "metal_galvanized", uv=None, smooth=40, wear=1.0, patches=0.6, low=0.8, low_h=0.15)
    ctx.add(lid, "metal_galvanized", uv="cyl", uv_scale=2.5, smooth=40, wear=1.0, at=((0, 0, 0.548), None))
    ctx.col_box((-0.2, -0.17, 0), (0.2, 0.17, 0.63))


def _fork(name: str, L: float, tines: int, spread: float):
    """Hay fork lying along X, tines toward +X: ash handle, iron ferrule and curved tines."""
    handle = K.cyl(f"{name}_handle", 0.016, L - 0.4, segs=8, axis="X", center=(-(L - 0.4) / 2, 0, 0))
    ferrule = K.cyl(f"{name}_ferrule", 0.021, 0.12, segs=8, axis="X", center=(0.06, 0, 0), r_top=0.014)
    steel = [ferrule]
    for k in range(tines):
        y = (k - (tines - 1) / 2) * spread
        steel.append(K.tube(f"{name}_tine", [(0.1, y * 0.4, 0), (0.18, y * 0.9, 0.0), (0.3, y, 0.012), (0.4, y * 1.02, 0.035)],
                            [0.008, 0.0075, 0.006, 0.003], segs=5))
    steel.append(K.tube(f"{name}_bow", [(0.1, -spread * 0.45 * (tines - 1) / 2, 0), (0.1, spread * 0.45 * (tines - 1) / 2, 0)], 0.008,
                        segs=5))
    return handle, K.merge_parts(steel, f"{name}_steel")


def farm_pitchfork(ctx: K.Ctx) -> None:
    """Three-tine hay fork dropped on the floor (1.45 m). Worn: the handle grey and split."""
    handle, steel = _fork("fork", 1.45, 3, 0.055)
    K.place(handle, (0, 0, 0.017))
    K.place(steel, (0, 0, 0.017))
    ctx.add(handle, "farm_wood_grey" if ctx.worn else "wood_fresh", uv="box", long_axis=0, smooth=40, patches=0.4)
    ctx.add(steel, "farm_steel_blade", uv="cyl", uv_axis=0, smooth=40, wear=1.2)
    ctx.col_box((-1.05, -0.08, 0), (0.42, 0.08, 0.06))


def farm_tool_rack(ctx: K.Ctx) -> None:
    """Barn tool rack against the wall (1.3 m): a peg board on two uprights holding a pitchfork,
    a bow rake, a round-point shovel, a scythe hung on its snath, a coil of rope and a hay hook.
    Worn: the shovel gone from its pegs, lying below. Destroyed: the board torn down at one end,
    tools on the floor."""
    wood = "farm_wood_grey"
    handle_mat = "farm_wood_grey" if ctx.worn else "wood_fresh"
    steel = "farm_steel_blade"
    frame = []
    for x in (-0.6, 0.6):
        frame.append(K.box("upright", (0.07, 0.03, 1.85), center=(x, -0.015, 0.925), bevel=0.004))
    board = K.box("pegboard", (1.32, 0.025, 0.16), center=(0, -0.045, 1.62), bevel=0.004)
    frame.append(board)
    pegs = []
    for x in (-0.48, -0.42, -0.22, -0.16, 0.05, 0.11, 0.3, 0.52):
        pegs.append(K.cyl("peg", 0.012, 0.12, segs=6, axis="Y", center=(x, -0.11, 1.6)))
    fr = K.merge_parts(frame + pegs, "rackframe")
    K.uv_box(fr, 1.0, long_axis=2)
    if ctx.destroyed:
        m = _xf((0.6, 0, 0)) @ _xf(rot=(0, 52, 0)) @ _xf((-0.6, 0, 0))
        board_m = m
    else:
        board_m = Matrix.Identity(4)
    fr.data.transform(board_m)
    fr.data.update()
    K.lift_min(fr)
    ctx.add(fr, wood, uv=None, smooth=None, patches=0.5, moss=0.2)
    # Pitchfork hanging tines-up between two pegs.
    h, st = _fork("rackfork", 1.5, 4, 0.05)
    for o in (h, st):
        K.place(o, rot=(0, -90, 0))
        K.place(o, (-0.45, -0.14, 0.42 + 0.67))
    if ctx.destroyed:
        for o in (h, st):
            o.data.transform(_xf((-0.2, -0.45, 0.02)) @ _xf(rot=(0, 90, 20)) @ _xf((0.45, 0.14, -1.09)))
            o.data.update()
            K.lift_min(o)
    ctx.add(h, handle_mat, uv="box", long_axis=2, smooth=40, patches=0.4)
    ctx.add(st, steel, uv="cyl", uv_axis=2, smooth=40, wear=1.2)
    # Bow rake, head up.
    rake = [K.cyl("rakehandle", 0.015, 1.45, segs=8, center=(-0.19, -0.14, 0.78))]
    rh = [K.box("rakehead", (0.36, 0.025, 0.03), center=(-0.19, -0.14, 1.52), bevel=0.004)]
    for k in range(12):
        rh.append(K.tube("tooth", [(-0.35 + k * 0.029, -0.14, 1.53), (-0.35 + k * 0.029, -0.16, 1.6), (-0.35 + k * 0.029, -0.19, 1.62)],
                         0.004, segs=4))
    for sx in (-1, 1):
        rh.append(K.tube("bow", [(-0.19 + sx * 0.16, -0.14, 1.53), (-0.19 + sx * 0.06, -0.14, 1.46), (-0.19, -0.14, 1.42)], 0.005, segs=4))
    if not ctx.destroyed:
        ctx.add(K.merge_parts(rake, "rakehandle"), handle_mat, uv="box", long_axis=2, smooth=40, patches=0.4)
        ctx.add(K.merge_parts(rh, "rakehead"), steel, smooth=40, wear=1.2)
    # Round-point shovel, blade down (on the floor when worn).
    sh_handle = K.cyl("shovelhandle", 0.016, 1.15, segs=8, center=(0, 0, 0.575))
    grip = K.tube("dgrip", [(-0.07, 0, 1.15), (-0.06, 0, 1.25), (0.0, 0, 1.28), (0.06, 0, 1.25), (0.07, 0, 1.15)], 0.011, segs=5)
    blade = K.quad_sheet("blade", (-0.12, 0, -0.3), (0.12, 0, -0.3), (0.12, 0, 0.0), (-0.12, 0, 0.0), 4, 4)
    K.map_verts(blade, lambda co: Vector((co.x * (1.0 - 0.55 * max(0.0, -co.z - 0.18) / 0.12), 0.05 * (co.x / 0.12) ** 2 - 0.02 * co.z,
                                          co.z)))
    K.solidify(blade, 0.003)
    socket = K.cyl("socket", 0.022, 0.12, segs=8, center=(0, 0, 0.03), r_top=0.017)
    shovel_wood = K.merge_parts([sh_handle, grip], "shovel_wood")
    shovel_steel = K.merge_parts([blade, socket], "shovel_steel")
    K.uv_box(shovel_wood, 1.0, long_axis=2)
    K.uv_box(shovel_steel, 1.0)
    if ctx.worn:
        sm = _xf((0.35, -0.55, 0.03)) @ _xf(rot=(0, 90, -25)) @ _xf((0, 0, -0.5))
    else:
        sm = _xf((0.08, -0.13, 0.32))
    for o in (shovel_wood, shovel_steel):
        o.data.transform(sm)
        o.data.update()
        if ctx.worn:
            K.lift_min(o)
    ctx.add(shovel_wood, handle_mat, uv=None, smooth=40, patches=0.4)
    ctx.add(shovel_steel, steel, uv=None, smooth=40, wear=1.3)
    # Scythe hung on two pegs: curved snath with two nibs, long blade.
    if not ctx.destroyed:
        snath_pts = [(0.62, -0.13, 1.68), (0.42, -0.13, 1.69), (0.2, -0.13, 1.66), (0.0, -0.13, 1.6), (-0.2, -0.13, 1.5)]
        snath = K.tube("snath", snath_pts, 0.016, segs=6)
        nibs = [K.tube("nib", [(0.25, -0.13, 1.67), (0.25, -0.22, 1.71)], 0.011, segs=5),
                K.tube("nib", [(-0.05, -0.13, 1.58), (-0.05, -0.22, 1.63)], 0.011, segs=5)]
        ctx.add(K.merge_parts([snath] + nibs, "snath"), handle_mat, uv="box", smooth=40, patches=0.4)
        bl_pts = [(0.62 - 0.1 * k, -0.15, 1.66 - 0.02 * k * k * 0.5) for k in range(9)]
        sc = K.sweep("scytheblade", bl_pts, [(-0.002, -0.06), (0.002, -0.06), (0.001, 0.0), (-0.001, 0.0)], up=(0, 1, 0),
                     scale=[1.0 - 0.1 * k for k in range(9)])
        ctx.add(sc, steel, uv="box", smooth=40, wear=1.4)
    # Rope coil on the end peg, a hay hook beside it.
    coil = []
    for k in range(5):
        rr = 0.14 + 0.012 * k
        coil.append(K.tube("rope", [(0.52 + rr * 0.35 * math.sin(math.tau * i / 16), -0.16 - 0.01 * k, 1.6 - rr + rr * math.cos(math.tau * i / 16))
                                    for i in range(16)], 0.009, segs=5, closed=True))
    ctx.add(K.merge_parts(coil, "rope"), "farm_twine", uv="box", uv_scale=2.0, smooth=40, wear=0.3)
    hook = K.tube("hayhook", [(-0.55, -0.15, 1.55), (-0.55, -0.15, 1.38), (-0.53, -0.2, 1.3), (-0.5, -0.24, 1.33)], 0.007, segs=5)
    ctx.add(hook, "car_rust", smooth=40)
    ctx.col_box((-0.66, -0.3, 0), (0.66, 0.0, 1.85))
    if not ctx.destroyed:
        _recenter_y(ctx)


def farm_saddle_stand(ctx: K.Ctx) -> None:
    """Western saddle over a blanket on a plank saddle stand: skirt and seat, swell and horn,
    high cantle, fenders with wooden stirrups, latigo and cinch hanging, brass conchos. Worn: the
    leather dry and cracked, a stirrup turned. Destroyed: the saddle pulled off onto the floor."""
    wood = "farm_wood_grey"
    leather = "farm_leather_saddle"
    straps = "farm_leather_black"
    rail_z = 0.92
    # Stand: rail, splayed end legs, stretchers.
    stand = [K.box("rail", (0.66, 0.1, 0.09), center=(0, 0, rail_z - 0.045), bevel=0.03, bevel_segs=2)]
    for x in (-0.3, 0.3):
        for sy in (-1, 1):
            stand.append(_strut("leg", Vector((x, sy * 0.3, 0.0)), Vector((x, sy * 0.03, rail_z - 0.08)), 0.08, 0.025, Vector((0, sy, 0))))
        stand.append(K.box("tie", (0.025, 0.5, 0.06), center=(x, 0, 0.3)))
    stand.append(K.box("stretcher", (0.6, 0.025, 0.06), center=(0, 0, 0.3)))
    st = K.merge_parts(stand, "stand")
    ctx.add(st, wood, uv="box", long_axis=0, smooth=None, patches=0.5)
    z0 = rail_z + 0.012
    Rd = 0.16

    def drape(co: Vector, extra: float = 0.0) -> Vector:
        s = co.y
        tmax = 1.2
        sm = Rd * tmax
        x = co.x * (1.0 - 0.18 * max(0.0, abs(s) - 0.15))
        if abs(s) <= sm:
            th = s / Rd
            return Vector((x, (Rd + extra) * math.sin(th), z0 - Rd + (Rd + extra) * math.cos(th)))
        sg = 1.0 if s > 0 else -1.0
        e = Vector((x, sg * (Rd + extra) * math.sin(tmax), z0 - Rd + (Rd + extra) * math.cos(tmax)))
        tan = Vector((0, sg * math.cos(tmax), -math.sin(tmax)))
        down = Vector((0, sg * 0.25, -1.0)).normalized()
        k = abs(s) - sm
        return e + tan * min(k, 0.05) + down * max(0.0, k - 0.05)
    saddle_parts = []
    blanket = K.grid("blanket", 0.78, 1.0, 12, 14)
    K.uv_sheet(blanket, scale=1.0)
    K.map_verts(blanket, lambda co: drape(co, 0.0))
    K.noise_disp(blanket, 0.006, scale=6.0, seed=ctx.seed, along_normal=False)
    K.solidify(blanket, 0.012)
    skirt = K.grid("skirt", 0.6, 0.86, 10, 12)
    K.uv_sheet(skirt, scale=1.0)
    K.map_verts(skirt, lambda co: drape(co, 0.014))
    K.solidify(skirt, 0.014)
    seat = K.blob("seat", 0.5, subdiv=2, scale=(0.5, 0.33, 0.075), center=(0.0, 0, 0))
    K.map_verts(seat, lambda co: Vector((co.x, co.y, co.z + 0.06 * K.smooth01(-0.1, 0.25, co.x) - 0.02 * K.smooth01(0.0, -0.2, co.x))))
    # Wrap the seat over the skirt's curve (a flat seat stood off the draped skirt like a plank).
    seat_r = Rd + 0.045

    def wrap(co: Vector) -> Vector:
        r = seat_r + co.z
        th = co.y / seat_r
        return Vector((co.x, r * math.sin(th), z0 - Rd + r * math.cos(th)))
    K.map_verts(seat, wrap)
    K.place(seat, (0.02, 0, 0))
    cantle_pts = [(0.24, 0.17 * math.cos(math.pi * i / 10) * -1, z0 + 0.05 + 0.13 * math.sin(math.pi * i / 10)) for i in range(11)]
    cantle = K.sweep("cantle", cantle_pts, [(-0.015, 0.0), (0.015, 0.0), (0.015, 0.05), (-0.015, 0.05)], up=(1, 0, 0))
    swell = K.blob("swell", 0.5, subdiv=2, scale=(0.14, 0.3, 0.16), center=(-0.23, 0, z0 + 0.06))
    horn = K.tube("horn", [(-0.25, 0, z0 + 0.12), (-0.27, 0, z0 + 0.22), (-0.275, 0, z0 + 0.26)], [0.03, 0.022, 0.022], segs=8)
    cap = K.cyl("horncap", 0.05, 0.022, segs=12, center=(-0.275, 0, z0 + 0.27))
    saddle_parts += [skirt, seat, cantle, swell, horn, cap]
    fenders, stirrups, strapl, brass = [], [], [], []
    for sy in (-1, 1):
        f = K.quad_sheet("fender", (-0.08, 0, 0), (0.14, 0, 0), (0.12, 0, -0.42), (-0.06, 0, -0.42), 2, 4)
        K.map_verts(f, lambda co: Vector((co.x, 0.02 * math.sin(co.z * 6.0), co.z)))
        K.solidify(f, 0.008)
        top = drape(Vector((0.03, sy * 0.25, 0)), 0.03)
        K.place(f, (top.x, top.y + sy * 0.01, top.z - 0.02))
        fenders.append(f)
        turn = 70 if (ctx.worn and sy > 0) else 0
        sp = [(0.13 * math.cos(math.pi * i / 8) * 0.5, 0.0, -0.13 * math.sin(math.pi * i / 8)) for i in range(9)]
        stirrup = K.tube("stirrup", sp, 0.016, segs=5, flat=(1.0, 2.2))
        tread = K.box("tread", (0.07, 0.11, 0.015), center=(0, 0, -0.13))
        sp_o = K.merge_parts([stirrup, tread], "stirrup")
        K.place(sp_o, rot=(0, 0, turn))
        K.place(sp_o, (top.x + 0.03, top.y + sy * 0.04, top.z - 0.47))
        stirrups.append(sp_o)
        strapl.append(K.box("latigo", (0.04, 0.008, 0.36), center=(-0.13, top.y + sy * 0.02, top.z - 0.22)))
        for k in range(2):
            brass.append(K.cyl("concho", 0.02, 0.008, segs=10, axis="Y", center=(0.18 - k * 0.38, sy * (Rd * math.sin(1.2) + 0.045), z0 - 0.12)))
    cinch = K.box("cinch", (0.12, 0.01, 0.42), center=(0.0, -(Rd + 0.07), z0 - 0.55))
    strapl.append(cinch)
    ring = K.tube("cinchring", [(0.0 + 0.04 * math.cos(math.tau * i / 10), -(Rd + 0.07), z0 - 0.78 + 0.04 * math.sin(math.tau * i / 10))
                                for i in range(10)], 0.006, segs=4, closed=True)
    sad = K.merge_parts(saddle_parts + fenders, "saddle")
    K.uv_box(sad, 1.0)
    stp = K.merge_parts(stirrups, "stirrups")
    K.uv_box(stp, 1.0)
    stl = K.merge_parts(strapl, "straps")
    K.uv_box(stl, 1.0)
    br = K.merge_parts(brass, "conchos")
    K.uv_box(br, 4.0)
    if ctx.destroyed:
        m = _xf((0.05, -0.75, 0.0)) @ _xf(rot=(0, 0, 25)) @ _xf((0, 0, -(z0 - 0.62)))
        for o in (sad, stp, stl, blanket, ring, br):
            o.data.transform(m)
            o.data.update()
            K.lift_min(o)
    ctx.add(blanket, "canvas_navy", uv=None, smooth=40, patches=0.4)
    ctx.add(sad, leather, uv=None, smooth=40, wear=1.0, patches=0.6)
    ctx.add(stp, "farm_wood_cedar", uv=None, smooth=None, wear=1.0)
    ctx.add(stl, straps, uv=None, smooth=None, wear=0.8)
    ctx.add(ring, "furn_brass" if not ctx.worn else "car_rust", uv="box", smooth=40)
    ctx.add(br, "furn_brass", uv=None, smooth=40, wear=0.6)
    ctx.col_box((-0.36, -0.36, 0), (0.36, 0.36, rail_z + 0.3))


def farm_stall_partition(ctx: K.Ctx) -> None:
    """Horse-stall wall section (2 m): oak posts, tongue-and-groove kick boards to 1.35 m with the
    top board chewed by a cribbing horse, iron bars above to 2.2 m under a capping rail. Worn: a
    kicked-out board, bars rusted. Destroyed: the boards smashed out, two bars bent."""
    wood = "wood_stained" if ctx.clean else "farm_wood_grey"
    iron = "farm_iron_black" if ctx.clean else "car_rust"
    Lp = 2.0
    posts = [K.box("post", (0.12, 0.12, 2.32), center=(sx * (Lp / 2), 0, 1.16), bevel=0.01, cuts=(0, 0, 3)) for sx in (-1, 1)]
    for p in posts:
        K.noise_disp(p, 0.004, scale=5.0, seed=ctx.seed)
    ctx.add(K.merge_parts(posts, "posts"), wood, uv="box", long_axis=2, smooth=None, patches=0.5)
    boards = []
    n = 6
    bh = 1.3 / n
    for k in range(n):
        if ctx.worn and not ctx.destroyed and k == 1:
            continue
        if ctx.destroyed and k in (1, 2, 4):
            dr = ctx.drnd(f"b{k}")
            piece = _board(f"broken{k}", dr.uniform(0.5, 1.1), bh, 0.04, dr, cuts=2)
            P.break_end(piece, 0.15, dr, side=1, depth=0.08)
            ctx.add(piece, wood, long_axis=0, at=((dr.uniform(-0.6, 0.6), -dr.uniform(0.2, 0.7), 0.02 + 0.045 * (k % 2)), (90 if dr.random() < 0.3 else 0, 0, dr.uniform(-40, 40))))
            continue
        b = _board(f"board{k}", Lp - 0.12, bh - 0.006, 0.04, ctx.rnd(f"board{k}"), cuts=4)
        K.orient(b, "x", "-y", (0, 0, 0.05 + bh * (k + 0.5)))
        if k == n - 1:
            K.noise_disp(b, 0.012, scale=10.0, seed=ctx.seed + 31, mask=lambda co: 1.0 if co.z > 0.05 + bh * (n - 0.5) else 0.0)
        boards.append(b)
    if ctx.worn and not ctx.destroyed:
        kb = _board("kicked", Lp - 0.12, bh - 0.006, 0.04, ctx.drnd("kick"), cuts=4)
        ctx.add(kb, wood, long_axis=0, at=((0.1, -0.35, 0.03), (8, 0, 6)))
    cap = K.box("cap", (Lp - 0.1, 0.09, 0.05), center=(0, 0, 1.38), bevel=0.008)
    top = K.box("toprail", (Lp - 0.1, 0.07, 0.06), center=(0, 0, 2.22), bevel=0.008)
    boards += [cap, top]
    ctx.add(K.merge_parts(boards, "boards"), wood, uv="box", long_axis=0, smooth=None, patches=0.55)
    bars = []
    for k in range(17):
        x = -Lp / 2 + 0.12 + k * (Lp - 0.24) / 16
        if ctx.destroyed and k in (5, 6):
            bars.append(K.tube("bar", [(x, 0, 1.4), (x, -0.06, 1.75), (x + 0.04, -0.12, 1.95)], 0.011, segs=6))
            continue
        bars.append(K.cyl("bar", 0.011, 0.8, segs=6, center=(x, 0, 1.8)))
    ctx.add(K.merge_parts(bars, "bars"), iron, uv="cyl", smooth=40, wear=1.0)
    ctx.col_box((-Lp / 2 - 0.06, -0.06, 0), (Lp / 2 + 0.06, 0.06, 2.3))


def farm_tool_chest(ctx: K.Ctx) -> None:
    """Carpenter's tool chest (0.8 x 0.45 x 0.42): dovetailed pine box on a plinth, lid with a
    lip, iron corner plates, rope handles, hasp and padlock. Worn: lid ajar on the saw till.
    Destroyed: lid wrenched off, one end split open."""
    L, D, H = 0.8, 0.45, 0.42
    wood = "wood_stained" if ctx.clean else "farm_wood_grey"
    iron = "farm_iron_black"
    body = K.box("chest", (L, D, H - 0.06), center=(0, 0, 0.035 + (H - 0.06) / 2), bevel=0.006, cuts=(2, 0, 2))
    plinth = K.box("plinth", (L + 0.03, D + 0.03, 0.05), center=(0, 0, 0.025), bevel=0.006)
    tails = []
    for sx in (-1, 1):
        for k in range(4):
            tails.append(K.box("dovetail", (0.012, 0.03, 0.05), center=(sx * (L / 2 + 0.002), -D / 2 + 0.02, 0.07 + k * 0.085)))
    wb = K.merge_parts([body, plinth] + tails, "chest")
    if ctx.destroyed:
        K.delete_faces(wb, lambda c, n: c.x > L / 2 - 0.01 and n.x > 0.5 and c.z > 0.1)
    ctx.add(wb, wood, uv="box", long_axis=0, smooth=None, patches=0.5)
    lid = K.box("lid", (L + 0.03, D + 0.03, 0.05), center=(0, D / 2, 0.025), bevel=0.008)
    if ctx.destroyed:
        ctx.add(lid, wood, long_axis=0, at=((0.25, -0.55, 0.0), (180, 0, 22)))
    elif ctx.worn:
        ctx.add(lid, wood, long_axis=0, at=((0, -D / 2 + 0.012, H - 0.025), (32, 0, 0)))
    else:
        ctx.add(lid, wood, long_axis=0, at=((0, -D / 2 + 0.012, H - 0.025), None))
    hw = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            hw.append(K.box("corner", (0.06, 0.06, 0.004), center=(sx * (L / 2 - 0.03), sy * (D / 2 - 0.03), H - 0.03)))
            hw.append(K.box("cornerv", (0.004, 0.06, 0.06), center=(sx * (L / 2 + 0.002), sy * (D / 2 - 0.03), 0.08)))
    hw.append(K.box("hasp", (0.05, 0.006, 0.08), center=(0, -D / 2 - 0.004, H - 0.08)))
    ctx.add(K.merge_parts(hw, "corners"), iron, wear=1.2)
    if not ctx.worn:
        lock = K.box("padlock", (0.045, 0.02, 0.05), center=(0, -D / 2 - 0.02, H - 0.13), bevel=0.006)
        shackle = K.tube("shackle", [(-0.015, -D / 2 - 0.02, H - 0.105), (-0.015, -D / 2 - 0.02, H - 0.08), (0.015, -D / 2 - 0.02, H - 0.08),
                                     (0.015, -D / 2 - 0.02, H - 0.105)], 0.004, segs=4)
        ctx.add(K.merge_parts([lock, shackle], "padlock"), "furn_brass", wear=0.8)
    for sx in (-1, 1):
        rope = K.tube("ropehandle", [(sx * (L / 2 + 0.004), -0.09, 0.3), (sx * (L / 2 + 0.05), -0.07, 0.25), (sx * (L / 2 + 0.06), 0.0, 0.23),
                                     (sx * (L / 2 + 0.05), 0.07, 0.25), (sx * (L / 2 + 0.004), 0.09, 0.3)], 0.01, segs=5)
        ctx.add(rope, "farm_twine", uv="box", uv_scale=2.0, smooth=40, wear=0.4)
    ctx.col_box((-L / 2 - 0.06, -D / 2 - 0.03, 0), (L / 2 + 0.06, D / 2 + 0.03, H))


def farm_lantern(ctx: K.Ctx) -> None:
    """Tin hurricane lantern: fuel fount, wire globe guard, glass globe with a flame, the twin
    air tubes up to the vented cap, bail handle. Worn: paint gone, globe smoked. Destroyed:
    lying on its side, globe shattered."""
    tin = "paint_red" if ctx.clean else "metal_galvanized"
    parts = []
    font = K.lathe("fount", [(0.0, 0.0), (0.078, 0.0), (0.088, 0.015), (0.088, 0.05), (0.07, 0.068), (0.03, 0.075), (0.0, 0.075)], segs=16)
    capp = K.lathe("cap", [(0.0, 0.27), (0.06, 0.27), (0.07, 0.29), (0.05, 0.31), (0.03, 0.33), (0.0, 0.335)], segs=14)
    tubes = []
    for sx in (-1, 1):
        tubes.append(K.tube("airtube", [(sx * 0.085, 0, 0.05), (sx * 0.09, 0, 0.18), (sx * 0.075, 0, 0.27), (sx * 0.04, 0, 0.3)], 0.011, segs=6))
    guard = [K.tube("guard", [(0.07 * math.cos(a), 0.07 * math.sin(a), 0.085), (0.078 * math.cos(a), 0.078 * math.sin(a), 0.17),
                              (0.06 * math.cos(a), 0.06 * math.sin(a), 0.26)], 0.003, segs=4) for a in (math.pi / 2, -math.pi / 2, 0.3, math.pi - 0.3)]
    bail = K.tube("bail", [(0.09, 0, 0.2), (0.09, 0, 0.33), (0.0, 0, 0.4), (-0.09, 0, 0.33), (-0.09, 0, 0.2)], 0.0025, segs=4)
    metal = K.merge_parts([font, capp] + tubes + guard + [bail], "lantern")
    K.uv_box(metal, 1.0)
    globe = K.lathe("globe", [(0.035, 0.078), (0.06, 0.12), (0.066, 0.17), (0.058, 0.23), (0.035, 0.27)], segs=14, cap_bottom=False, cap_top=False)
    K.uv_box(globe, 1.0)
    flame = K.blob("flame", 0.012, subdiv=1, scale=(1.0, 1.0, 2.2), center=(0, 0, 0.13))
    K.uv_box(flame, 1.0)
    burner = K.cyl("burner", 0.025, 0.02, segs=10, center=(0, 0, 0.085))
    K.uv_box(burner, 1.0)
    objs = [(metal, tin), (burner, "furn_brass")]
    if not ctx.destroyed:
        objs += [(globe, "glass_clear" if ctx.clean else "glass_brown"), (flame, "farm_wick_flame")]
    else:
        K.cut_plane(globe, (0, 0, 0.13), (0.3, 0.2, 1.0), keep="below", fill=False)
        objs.append((globe, "glass_clear"))
        m = _xf((0, 0, 0.09)) @ _xf(rot=(0, 90, 25)) @ _xf((0, 0, -0.09))
        for o, _ in objs:
            o.data.transform(m)
            o.data.update()
    for o, mat in objs:
        if ctx.destroyed:
            K.lift_min(o)
        ctx.add(o, mat, uv=None, smooth=40, wear=1.0, ao=mat not in ("farm_wick_flame",))
    ctx.col_box((-0.1, -0.09, 0), (0.1, 0.09, 0.34))


# ============================================================================================
# Farmhouse
# ============================================================================================

def farm_stove_castiron(ctx: K.Ctx) -> None:
    """Cast-iron wood cookstove: six lids on the cooktop, firebox and ash doors on the left, a
    cream-enamelled oven door with a nickel bar and thermometer, side water reservoir, warming
    closet over a splashback, stovepipe up the back, nickel towel rail; a kettle and a skillet
    left on the lids. Worn: rust blooming, oven door hanging open. Destroyed: oven door on the
    floor, lids knocked off, the pipe down across the top."""
    iron = "furn_cast_iron"
    nickel = "chrome_pitted"
    enamel = "farm_iron_white"
    W, D = 1.04, 0.66
    leg_h, top_z = 0.17, 0.78
    body = K.box("body", (W, D, top_z - leg_h - 0.04), center=(0, 0, (leg_h + top_z - 0.04) / 2), bevel=0.012)
    top = K.box("cooktop", (W + 0.05, D + 0.04, 0.04), center=(0, 0.0, top_z - 0.02), bevel=0.008)
    skirt = K.box("skirt", (W + 0.02, D + 0.02, 0.05), center=(0, 0, leg_h + 0.025), bevel=0.01)
    iron_parts = [body, top, skirt]
    lids_off = {(0, 0), (2, 1)} if ctx.destroyed else set()
    for ix, x in enumerate((-0.32, 0.0, 0.32)):
        for iy, y in enumerate((-0.13, 0.15)):
            if (ix, iy) in lids_off:
                ring = K.lathe("lidring", [(0.08, top_z), (0.1, top_z), (0.1, top_z + 0.006), (0.08, top_z + 0.006)], segs=16, close_profile=True)
                K.place(ring, (x, y, 0))
                iron_parts.append(ring)
                continue
            lid = K.cyl("lid", 0.095, 0.012, segs=16, center=(x, y, top_z + 0.004))
            slot = K.box("lifter", (0.05, 0.014, 0.006), center=(x + 0.045, y, top_z + 0.012))
            iron_parts += [lid, slot]
    for sx in (-1, 1):
        for sy in (-1, 1):
            leg = K.lathe("leg", [(0.0, 0.0), (0.04, 0.0), (0.032, 0.035), (0.022, 0.09), (0.03, leg_h - 0.02), (0.04, leg_h), (0.0, leg_h)], segs=8)
            K.place(leg, (sx * (W / 2 - 0.07), sy * (D / 2 - 0.07), 0))
            iron_parts.append(leg)
    fire = K.box("firedoor", (0.26, 0.026, 0.24), center=(-0.3, -D / 2 - 0.012, 0.52), bevel=0.006)
    ash = K.box("ashdoor", (0.24, 0.022, 0.1), center=(-0.3, -D / 2 - 0.01, 0.28), bevel=0.004)
    iron_parts += [fire, ash]
    # Reservoir on the right end.
    res = K.box("reservoir", (0.22, D - 0.04, 0.5), center=(W / 2 + 0.11, 0, top_z - 0.27), bevel=0.012)
    iron_parts.append(res)
    # Splashback, warming closet and the shelf brackets.
    splash = K.box("splash", (W, 0.04, 0.34), center=(0, D / 2 - 0.02, top_z + 0.17))
    closet = K.box("closet", (W - 0.06, 0.26, 0.26), center=(0, D / 2 - 0.16, top_z + 0.36 + 0.13), bevel=0.01)
    iron_parts += [splash, closet]
    for sx in (-1, 1):
        iron_parts.append(K.tube("bracket", [(sx * (W / 2 - 0.05), D / 2 - 0.04, top_z + 0.12), (sx * (W / 2 - 0.05), D / 2 - 0.2, top_z + 0.3),
                                             (sx * (W / 2 - 0.05), D / 2 - 0.26, top_z + 0.36)], 0.012, segs=5))
    ir = K.merge_parts(iron_parts, "stove_iron")
    K.uv_box(ir, 1.0)
    # Indoors and blacked every week for forty years: rust blooms in patches, it doesn't take over.
    ctx.add(ir, iron, uv=None, smooth=None, wear=0.8, patches=0.22)
    # Enamel panels: oven door, reservoir lid, closet doors.
    enam = []
    enam.append(K.box("reslid", (0.21, D - 0.08, 0.016), center=(W / 2 + 0.11, 0, top_z - 0.012), bevel=0.004))
    for sx in (-1, 1):
        enam.append(K.box("closetdoor", ((W - 0.12) / 2, 0.012, 0.2), center=(sx * (W - 0.12) / 4, D / 2 - 0.295, top_z + 0.49), bevel=0.004))
    oven = K.box("ovendoor", (0.46, 0.03, 0.38), center=(0.0, 0.0, 0.19), bevel=0.01)
    oven_panel = K.box("ovenpanel", (0.38, 0.008, 0.28), center=(0.0, -0.018, 0.2), bevel=0.003)
    thermo = K.cyl("thermo", 0.035, 0.01, segs=12, axis="Y", center=(0.0, -0.024, 0.3))
    handle = K.tube("ovenbar", [(-0.18, -0.06, 0.37), (0.18, -0.06, 0.37)], 0.011, segs=6)
    hb = [K.box("barpost", (0.015, 0.05, 0.015), center=(sx * 0.18, -0.035, 0.37)) for sx in (-1, 1)]
    oven_iron = K.merge_parts([oven], "ovendoor")
    oven_enam = K.merge_parts([oven_panel], "ovenpanel")
    oven_nick = K.merge_parts([thermo, handle] + hb, "ovennickel")
    for o in (oven_iron, oven_enam, oven_nick):
        K.uv_box(o, 1.0)
    # Oven door frame: hinge along its bottom edge (local z = 0) at the front of the body.
    if ctx.destroyed:
        dm = _xf((0.15, -D / 2 - 0.65, 0.016)) @ _xf(rot=(-90, 0, 12))
    elif ctx.worn:
        dm = _xf((0.2, -D / 2 - 0.016, 0.28)) @ _xf(rot=(62, 0, 0))
    else:
        dm = _xf((0.2, -D / 2 - 0.016, 0.28))
    for o in (oven_iron, oven_enam, oven_nick):
        o.data.transform(dm)
        o.data.update()
        if ctx.destroyed:
            K.lift_min(o)
    ctx.add(oven_iron, iron, uv=None, smooth=None, wear=0.8, patches=0.22)
    ctx.add(oven_enam, enamel, uv=None, smooth=None, wear=0.9, patches=0.3)
    en = K.merge_parts(enam, "enamel")
    K.uv_box(en, 1.0)
    ctx.add(en, enamel, uv=None, smooth=None, wear=0.9, patches=0.3)
    nick = [K.tube("rail", [(-0.46, -D / 2 - 0.09, 0.7), (0.46, -D / 2 - 0.09, 0.7)], 0.011, segs=8)]
    for x in (-0.46, 0.46):
        nick.append(K.box("railbracket", (0.02, 0.08, 0.02), center=(x, -D / 2 - 0.05, 0.7)))
    for sx in (-1, 1):
        nick.append(K.cyl("knob", 0.015, 0.025, segs=8, axis="Y", center=(sx * 0.06, D / 2 - 0.31, top_z + 0.49)))
    nick.append(K.cyl("vent", 0.045, 0.012, segs=12, axis="Y", center=(-0.3, -D / 2 - 0.028, 0.55)))
    nick.append(K.box("faucet", (0.03, 0.05, 0.03), center=(W / 2 + 0.11, -D / 2 + 0.0, top_z - 0.42)))
    nk = K.merge_parts(nick, "nickel")
    K.uv_box(nk, 2.0)
    ctx.add(nk, nickel, uv=None, smooth=40, wear=1.0)
    ctx.add(oven_nick, nickel, uv=None, smooth=40, wear=1.0)
    # Stovepipe behind the warming closet (or down across the cooktop).
    pipe = [K.cyl("pipe", 0.075, 1.05, segs=14, center=(0, 0, 0.525), cuts=2),
            K.cyl("collar", 0.085, 0.05, segs=14, center=(0, 0, 0.0)),
            K.tube("damper", [(-0.12, 0, 0.45), (0.12, 0, 0.45)], 0.008, segs=5)]
    pp = K.merge_parts(pipe, "pipe")
    K.uv_box(pp, 1.0)
    if ctx.destroyed:
        pm = _xf((-0.05, 0.05, top_z + 0.1)) @ _xf(rot=(0, 78, 15))
    else:
        pm = _xf((0.33, D / 2 + 0.06, top_z))
    pp.data.transform(pm)
    pp.data.update()
    ctx.add(pp, "car_rust" if ctx.worn else iron, uv=None, smooth=40, wear=1.0)
    # Kettle and skillet.
    kettle = K.lathe("kettle", [(0.0, 0.0), (0.095, 0.0), (0.11, 0.035), (0.105, 0.11), (0.07, 0.16), (0.045, 0.17), (0.045, 0.18), (0.0, 0.185)], segs=14)
    spout = K.tube("spout", [(0.09, 0, 0.05), (0.15, 0, 0.11), (0.18, 0, 0.15)], [0.022, 0.016, 0.011], segs=6)
    bail = K.tube("kbail", [(-0.06, 0, 0.16), (-0.04, 0, 0.25), (0.04, 0, 0.25), (0.06, 0, 0.16)], 0.005, segs=4)
    kt = K.merge_parts([kettle, spout, bail], "kettle")
    pan = K.lathe("skillet", [(0.0, 0.0), (0.11, 0.0), (0.125, 0.012), (0.13, 0.045), (0.12, 0.045), (0.112, 0.014), (0.0, 0.012)], segs=16)
    ph = K.box("panhandle", (0.16, 0.035, 0.016), center=(0.2, 0, 0.035))
    sk = K.merge_parts([pan, ph], "skillet")
    if ctx.destroyed:
        ctx.add(kt, "car_rust", uv="cyl", smooth=40, wear=1.0, at=((-0.55, -0.8, 0.11), (85, 0, 30)))
        ctx.add(sk, iron, uv="cyl", smooth=40, wear=1.0, at=((0.5, -0.6, 0.0), (0, 0, 140)))
    else:
        ctx.add(kt, "farm_iron_white" if ctx.clean else "car_rust", uv="cyl", smooth=40, wear=1.0, at=((-0.32, -0.13, top_z + 0.01), (0, 0, 25)))
        ctx.add(sk, iron, uv="cyl", smooth=40, wear=1.0, at=((0.32, 0.15, top_z + 0.01), (0, 0, -30)))
    ctx.col_box((-W / 2 - 0.03, -D / 2 - 0.1, 0), (W / 2 + 0.23, D / 2 + 0.14, top_z + 0.62))


def farm_butter_churn(ctx: K.Ctx) -> None:
    """Stave-built dash churn (0.62 m) with three iron hoops, a lid and the dasher standing up
    through it. Worn: staves grey and shrunk, a hoop slipped. Destroyed: knocked over, lid off,
    the dasher on the floor."""
    wood = "wood_stained" if ctx.clean else "farm_wood_grey"
    iron = "farm_iron_black" if ctx.clean else "car_rust"
    Hc = 0.62

    def rad(z: float) -> float:
        return 0.155 - 0.04 * (z / Hc)
    prof = [(0.0, 0.0), (rad(0.0) - 0.008, 0.0), (rad(0.0), 0.012)] + [(rad(z), z) for z in (0.15, 0.3, 0.45)] + [(rad(Hc), Hc),
                                                                                                         (rad(Hc) - 0.016, Hc), (rad(Hc) - 0.016, Hc - 0.04), (0.0, Hc - 0.04)]
    body = K.lathe("churn", prof, segs=14)
    K.noise_disp(body, 0.002, scale=8.0, seed=ctx.seed)
    hoops = []
    for k, z in enumerate((0.07, 0.32, 0.56)):
        zz = z - (0.05 if (ctx.worn and k == 1) else 0.0)
        hoops.append(_hoop("hoop", rad(zz) + 0.004, zz, tube_r=0.012, segs=14, flat=(0.3, 1.0)))
    lid = K.cyl("lid", rad(Hc) - 0.012, 0.022, segs=14, center=(0, 0, Hc - 0.03))
    knob = K.cyl("lidknob", 0.03, 0.03, segs=8, center=(0.05, 0, Hc - 0.005))
    dasher = [K.cyl("dasher", 0.016, 0.62, segs=8, center=(0, 0, 0.31)), K.cyl("dashtop", 0.022, 0.04, segs=8, center=(0, 0, 0.62))]
    cross = [K.box("dash", (0.16, 0.03, 0.014), center=(0, 0, 0.0)), K.box("dash", (0.03, 0.16, 0.014), center=(0, 0, 0.0))]
    ch = K.merge_parts([body], "churnbody")
    K.uv_box(ch, 1.0, long_axis=2)
    hoopo = K.merge_parts(hoops, "hoops")
    K.uv_box(hoopo, 1.0)
    hp = K.merge_parts([lid, knob], "lid")
    K.uv_box(hp, 1.0)
    ds = K.merge_parts(dasher + cross, "dasher")
    K.uv_box(ds, 1.0, long_axis=2)
    if ctx.destroyed:
        m = _xf((0, 0, rad(0.3))) @ _xf(rot=(0, 90, 30)) @ _xf((0, 0, -0.3))
        for o in (ch, hoopo):
            o.data.transform(m)
            o.data.update()
        K.lift_min(ch)
        ctx.add(ch, wood, uv=None, smooth=None, patches=0.5)
        ctx.add(hoopo, iron, uv=None, smooth=40, wear=1.1)
        ctx.add(hp, wood, uv=None, smooth=None, at=((0.45, -0.25, 0.0), (180, 0, 0)))
        ctx.add(ds, wood, uv=None, smooth=40, at=((-0.2, -0.45, 0.016), (0, 90, 70)))
        ctx.col_box((-0.4, -0.2, 0), (0.4, 0.2, 0.32))
        return
    ctx.add(ch, wood, uv=None, smooth=None, patches=0.5, low=0.6, low_h=0.2)
    ctx.add(hp, wood, uv=None, smooth=None, patches=0.4)
    ctx.add(ds, wood, uv=None, smooth=40, at=((0, 0, 0.12), (4, 0, 0)))
    ctx.add(hoopo, iron, uv=None, smooth=40, wear=1.1)
    ctx.col_box((-0.16, -0.16, 0), (0.16, 0.16, 0.8))


def farm_washtub(ctx: K.Ctx) -> None:
    """Galvanised washtub with drop handles and a wooden washboard leaning in it, a cake of lye
    soap on the rim. Worn: dull, rust round the seams, grey water in the bottom. Destroyed:
    tipped on its side, the washboard split."""
    tub = P.bucket("tub", top_r=0.31, bot_r=0.27, h=0.27, segs=22, wall=0.004)
    beads = [_hoop("bead", 0.3, 0.08, tube_r=0.005, segs=22), _hoop("bead", 0.31, 0.2, tube_r=0.005, segs=22)]
    handles = []
    for sx in (-1, 1):
        handles.append(K.tube("tubhandle", [(sx * 0.315, -0.06, 0.24), (sx * 0.36, -0.05, 0.215), (sx * 0.37, 0.0, 0.21), (sx * 0.36, 0.05, 0.215),
                                            (sx * 0.315, 0.06, 0.24)], 0.007, segs=5))
    tb = K.merge_parts([tub] + beads + handles, "washtub")
    K.uv_box(tb, 2.5)
    board = []
    for sx in (-1, 1):
        board.append(K.box("leg", (0.04, 0.022, 0.62), center=(sx * 0.15, 0, 0.31), bevel=0.004))
    board.append(K.box("topboard", (0.34, 0.025, 0.1), center=(0, 0, 0.57), bevel=0.004))
    board.append(K.box("crossbar", (0.3, 0.02, 0.04), center=(0, 0, 0.06), bevel=0.003))
    wb = K.merge_parts(board, "washboard_frame")
    K.uv_box(wb, 1.0, long_axis=2)
    rib = K.box("rubbing", (0.26, 0.01, 0.36), center=(0, 0, 0.3), cuts=(0, 0, 24))
    K.map_verts(rib, lambda co: Vector((co.x, co.y + 0.004 * math.sin(co.z * 90.0) * (1.0 if co.y < 0 else 0.0), co.z)))
    K.uv_box(rib, 1.0)
    if ctx.destroyed:
        m = _xf((0, 0, 0.31)) @ _xf(rot=(-95, 0, 10)) @ _xf((0, 0, -0.14))
        tb.data.transform(m)
        tb.data.update()
        K.lift_min(tb)
        for o in (wb, rib):
            o.data.transform(_xf((0.35, -0.55, 0.012)) @ _xf(rot=(-90, 0, 30)))
            o.data.update()
            K.lift_min(o)
    else:
        for o in (wb, rib):
            o.data.transform(_xf((0.0, 0.12, 0.02)) @ _xf(rot=(-14, 0, 0)))
            o.data.update()
    ctx.add(tb, "metal_galvanized", uv=None, smooth=40, wear=1.0, patches=0.6, low=0.6, low_h=0.1)
    ctx.add(wb, "farm_wood_grey" if ctx.worn else "wood_fresh", uv=None, smooth=None, patches=0.5)
    ctx.add(rib, "metal_galvanized" if ctx.clean else "car_rust", uv=None, smooth=None, wear=0.8)
    if not ctx.destroyed:
        water = K.cyl("water", 0.268, 0.004, segs=22, center=(0, 0, 0.05 if ctx.worn else 0.12))
        ctx.add(water, "farm_trough_water", uv="planar", smooth=None, ao=False)
        soap = K.box("soap", (0.08, 0.05, 0.03), center=(0, 0, 0.015), bevel=0.008)
        ctx.add(soap, "candle_wax", smooth=40, at=((0.22, -0.2, 0.268), (0, 0, 35)))
    ctx.col_box((-0.38, -0.32, 0), (0.38, 0.32, 0.62))


def farm_quilt_bed(ctx: K.Ctx) -> None:
    """White-painted iron double bed with brass finials: arched head and foot rails over
    spindles, ticking mattress, two pillows and a hand-pieced patchwork quilt hanging over the
    sides. Worn: quilt thrown back and stained, a pillow on the floor. Destroyed: a side rail
    broken so the mattress slumps to the floor at one corner, the quilt dragged half off."""
    W, Lb = 1.42, 2.0
    frame = "farm_iron_white"
    brass = "furn_brass"
    mz = 0.36
    fr = []

    def end(y: float, h_post: float, h_mid: float):
        for sx in (-1, 1):
            fr.append(K.cyl("post", 0.022, h_post, segs=10, center=(sx * W / 2, y, h_post / 2)))
        arch = [(x, y, h_post - 0.08 + (h_mid - h_post + 0.08) * (1.0 - (x / (W / 2)) ** 2)) for x in [-W / 2 + W * i / 14 for i in range(15)]]
        fr.append(K.tube("archrail", arch, 0.016, segs=6))
        fr.append(K.tube("lowrail", [(-W / 2, y, 0.55), (W / 2, y, 0.55)], 0.014, segs=6))
        for k in range(9):
            x = -W / 2 + W * (k + 1) / 10
            top = h_post - 0.08 + (h_mid - h_post + 0.08) * (1.0 - (x / (W / 2)) ** 2)
            fr.append(K.tube("spindle", [(x, y, 0.55), (x, y, top)], 0.008, segs=5, caps=False))
    end(Lb / 2, 1.18, 1.3)
    end(-Lb / 2, 0.9, 0.98)
    knobs = []
    for sy, hp in ((1, 1.18), (-1, 0.9)):
        for sx in (-1, 1):
            knobs.append(K.lathe("finial", [(0.0, 0.0), (0.028, 0.0), (0.03, 0.012), (0.018, 0.022), (0.03, 0.045), (0.022, 0.068), (0.0, 0.072)],
                                 segs=10))
            K.place(knobs[-1], (sx * W / 2, sy * Lb / 2, hp))
    broken = ctx.destroyed
    for sx in (-1, 1):
        if broken and sx > 0:
            fr.append(K.tube("siderail", [(sx * W / 2, Lb / 2, mz - 0.03), (sx * W / 2, -0.1, mz - 0.06), (sx * (W / 2 - 0.02), -Lb / 2 + 0.1, 0.03)],
                             0.02, segs=4, flat=(1.0, 1.6)))
            continue
        fr.append(K.box("siderail", (0.04, Lb, 0.06), center=(sx * W / 2, 0, mz - 0.03), bevel=0.004))
    for k in range(5):
        fr.append(K.box("slat", (W - 0.06, 0.06, 0.012), center=(0, -Lb / 2 + 0.25 + k * 0.38, mz - 0.03)))
    fo = K.merge_parts(fr, "bedframe")
    K.uv_box(fo, 1.0)
    ctx.add(fo, frame, uv=None, smooth=40, wear=1.0, patches=0.6)
    kn = K.merge_parts(knobs, "finials")
    K.uv_box(kn, 2.0)
    ctx.add(kn, brass, uv=None, smooth=40, wear=0.7)
    tilt = (lambda co: Vector((co.x, co.y, co.z - max(0.0, (co.x + W / 2) / W) * max(0.0, (-co.y + Lb / 2) / Lb) * 0.3))) if broken else None
    mat = K.box("mattress", (W - 0.06, Lb - 0.06, 0.2), center=(0, 0, mz + 0.1), bevel=0.05, bevel_segs=2, cuts=(4, 6, 1))
    K.noise_disp(mat, 0.008, scale=3.0, seed=ctx.seed)
    if tilt:
        K.map_verts(mat, tilt)
    ctx.add(mat, "mattress_ticking", uv="box", smooth=40, patches=0.5)
    top_z = mz + 0.205
    for k, x in enumerate((-0.33, 0.33)):
        if ctx.worn and not ctx.destroyed and k == 1:
            pl = K.blob("pillow", 0.5, subdiv=2, scale=(0.32, 0.22, 0.06), center=(0.9, -0.2, 0.06), rough=0.15, seed=ctx.seed + k)
            ctx.add(pl, "furn_linen", smooth=40, patches=0.5)
            continue
        pl = K.blob("pillow", 0.5, subdiv=2, scale=(0.32, 0.22, 0.075), center=(x, Lb / 2 - 0.28, top_z + 0.06), rough=0.12, seed=ctx.seed + k)
        if tilt:
            K.map_verts(pl, tilt)
        ctx.add(pl, "furn_linen", smooth=40, patches=0.5)
    # Quilt: a sheet draped over the mattress top, hanging down the sides and the foot.
    qw, ql = 2.06, 1.9 if not ctx.worn else 1.4
    q = K.grid("quilt", qw, ql, 22, 22)
    K.uv_sheet(q, scale=1.0)
    hx, foot = (W - 0.06) / 2 + 0.03, -Lb / 2 + 0.03
    y_shift = -0.5 if not ctx.worn else -0.6

    def drape(co: Vector) -> Vector:
        x, y = co.x, co.y + y_shift
        z = top_z + 0.012
        ox = abs(x) - hx
        if ox > 0:
            z -= ox
            x = math.copysign(hx + 0.015 + 0.02 * ox, x)
        oy = foot - y
        if oy > 0:
            z -= oy
            y = foot - 0.015 - 0.02 * oy
        z = max(z, 0.08)
        return Vector((x, y, z))
    K.map_verts(q, drape)
    K.noise_disp(q, 0.012 if not ctx.worn else 0.03, scale=4.0, seed=ctx.seed + 5, along_normal=False)
    if ctx.worn:
        # The turned-back top: a fat roll across the bed.
        roll = K.cyl("roll", 0.07, W + 0.1, segs=10, axis="X", center=(0, ql / 2 + y_shift + 0.04, top_z + 0.06))
        K.noise_disp(roll, 0.02, scale=4.0, seed=ctx.seed + 6, along_normal=False)
        if tilt:
            K.map_verts(roll, tilt)
        ctx.add(roll, "farm_quilt", uv="cyl", uv_axis=0, smooth=40, patches=0.6)
    if tilt:
        K.map_verts(q, tilt)
    K.solidify(q, 0.012)
    ctx.add(q, "farm_quilt", uv=None, smooth=40, patches=0.6 if ctx.worn else 0.3)
    ctx.col_box((-W / 2 - 0.04, -Lb / 2 - 0.04, 0), (W / 2 + 0.04, Lb / 2 + 0.04, 1.27))


def farm_hope_chest(ctx: K.Ctx) -> None:
    """Cedar hope chest (1.05 m) on bracket feet: two raised front panels, a moulded lid,
    brass escutcheon and side handles. Worn: lid ajar, the corner of a quilt caught in it.
    Destroyed: lid torn off the hinges, a front panel split."""
    L, D, H = 1.05, 0.48, 0.52
    wood = "farm_wood_cedar" if ctx.clean else "wood_stained"
    case = [K.box("case", (L, D, H - 0.14), center=(0, 0, 0.08 + (H - 0.14) / 2), bevel=0.008)]
    case.append(K.box("plinth", (L + 0.03, D + 0.03, 0.05), center=(0, 0, 0.085), bevel=0.01))
    for sx in (-1, 1):
        for sy in (-1, 1):
            foot = K.prism("bracketfoot", [(0.0, 0.0), (0.09, 0.0), (0.09, 0.07), (0.0, 0.07), (0.0, 0.0)][:4], 0.03, plane="XZ")
            K.place(foot, (sx * (L / 2 - 0.045) - 0.045, sy * (D / 2 - 0.01), 0.0))
            case.append(foot)
    for k, x in enumerate((-0.25, 0.25)):
        if ctx.destroyed and k == 1:
            continue
        case.append(K.box("panel", (0.4, 0.016, 0.22), center=(x, -D / 2 - 0.006, 0.08 + (H - 0.14) / 2), bevel=0.012, bevel_segs=2))
    cs = K.merge_parts(case, "chest")
    K.uv_box(cs, 1.0, long_axis=0)
    ctx.add(cs, wood, uv=None, smooth=None, patches=0.4)
    lid = K.box("lid", (L + 0.04, D + 0.04, 0.05), center=(0, D / 2, 0.025), bevel=0.012, bevel_segs=2)
    mould = K.box("mould", (L + 0.06, D + 0.06, 0.016), center=(0, D / 2, 0.008), bevel=0.006)
    lo = K.merge_parts([lid, mould], "lid")
    K.uv_box(lo, 1.0, long_axis=0)
    if ctx.destroyed:
        lm = _xf((-0.3, -0.75, 0.0)) @ _xf(rot=(0, 0, 18)) @ _xf((0, -D / 2, 0))
    elif ctx.worn:
        lm = _xf((0, D / 2, H - 0.06)) @ _xf(rot=(-24, 0, 0)) @ _xf((0, -D, 0))
    else:
        lm = _xf((0, -D / 2 - 0.02, H - 0.06))
    lo.data.transform(lm)
    lo.data.update()
    if ctx.destroyed:
        K.lift_min(lo)
    ctx.add(lo, wood, uv=None, smooth=None, patches=0.4)
    br = [K.box("escutcheon", (0.05, 0.006, 0.06), center=(0, -D / 2 - 0.014, H - 0.12), bevel=0.003)]
    for sx in (-1, 1):
        br.append(K.tube("handle", [(sx * (L / 2 + 0.004), -0.06, 0.32), (sx * (L / 2 + 0.03), -0.05, 0.3), (sx * (L / 2 + 0.03), 0.05, 0.3),
                                    (sx * (L / 2 + 0.004), 0.06, 0.32)], 0.006, segs=4))
    bo = K.merge_parts(br, "brass")
    K.uv_box(bo, 2.0)
    ctx.add(bo, "furn_brass", uv=None, smooth=40, wear=0.6)
    if ctx.worn and not ctx.destroyed:
        corner = K.quad_sheet("quiltcorner", (-0.2, -D / 2 - 0.01, H - 0.06), (0.15, -D / 2 - 0.01, H - 0.06), (0.1, -D / 2 - 0.03, H - 0.3),
                              (-0.16, -D / 2 - 0.04, H - 0.22), 4, 3)
        K.noise_disp(corner, 0.01, scale=8.0, seed=ctx.seed, along_normal=False)
        K.solidify(corner, 0.01)
        ctx.add(corner, "farm_quilt", uv="planar", uv_axis=1, uv_scale=1.0, smooth=40)
    ctx.col_box((-L / 2 - 0.03, -D / 2 - 0.03, 0), (L / 2 + 0.03, D / 2 + 0.03, H))


def farm_oil_lamp(ctx: K.Ctx) -> None:
    """Kerosene table lamp: pressed-glass foot and font, brass collar and burner with its wick
    knob, tall waisted glass chimney with the flame inside. Worn: chimney sooted. Destroyed:
    knocked over, chimney broken off."""
    foot = K.lathe("foot", [(0.0, 0.0), (0.07, 0.0), (0.072, 0.012), (0.04, 0.03), (0.02, 0.07), (0.03, 0.09), (0.0, 0.09)], segs=14)
    font = K.lathe("font", [(0.0, 0.09), (0.03, 0.09), (0.075, 0.13), (0.078, 0.16), (0.055, 0.19), (0.025, 0.2), (0.0, 0.2)], segs=14)
    oil = K.lathe("oil", [(0.0, 0.095), (0.066, 0.13), (0.069, 0.15), (0.0, 0.15)], segs=12)
    collar = K.lathe("collar", [(0.0, 0.198), (0.03, 0.198), (0.03, 0.215), (0.04, 0.225), (0.04, 0.245), (0.03, 0.255), (0.0, 0.255)], segs=12)
    knob = K.cyl("wickknob", 0.008, 0.03, segs=8, axis="X", center=(0.05, 0, 0.235))
    chimney = K.lathe("chimney", [(0.032, 0.25), (0.038, 0.27), (0.045, 0.31), (0.03, 0.36), (0.026, 0.42), (0.028, 0.45)], segs=14,
                      cap_bottom=False, cap_top=False)
    flame = K.blob("flame", 0.01, subdiv=1, scale=(1.2, 0.5, 2.6), center=(0, 0, 0.285))
    glass = K.merge_parts([foot, font], "glass")
    brass = K.merge_parts([collar, knob], "brass")
    objs = [(glass, "glass_green"), (oil, "candle_wax"), (brass, "furn_brass")]
    if ctx.destroyed:
        K.cut_plane(chimney, (0, 0, 0.33), (0.4, 0.2, 1.0), keep="below", fill=False)
    objs.append((chimney, "glass_clear" if ctx.clean else "glass_brown"))
    if not ctx.destroyed:
        objs.append((flame, "farm_wick_flame"))
    for o, _ in objs:
        K.uv_box(o, 2.0)
    if ctx.destroyed:
        m = _xf((0, 0, 0.078)) @ _xf(rot=(0, 90, 40)) @ _xf((0, 0, -0.14))
        for o, _ in objs:
            o.data.transform(m)
            o.data.update()
            K.lift_min(o)
    for o, mat in objs:
        ctx.add(o, mat, uv=None, smooth=40, wear=0.8, ao=mat != "farm_wick_flame")
    ctx.col_box((-0.08, -0.08, 0), (0.08, 0.08, 0.45))


# ============================================================================================
# Root cellar
# ============================================================================================

_PRESERVES = ("farm_preserve_peach", "farm_preserve_beet", "farm_preserve_pickle", "farm_preserve_jam", "farm_preserve_peach",
              "farm_preserve_pickle")


def farm_cellar_shelf(ctx: K.Ctx) -> None:
    """Rough-sawn root-cellar shelving (1.2 x 0.4 x 1.9) lined with Ife's preserves — peaches,
    beets, pickles, jam — two stoneware crocks on the bottom. Worn: dusty, jars gone dark or
    broken, gaps where someone took the good ones. Destroyed: a shelf collapsed onto the one
    below, jars smashed on the floor."""
    W, D, Hs = 1.2, 0.4, 1.9
    wood = "farm_wood_grey"
    fr = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            fr.append(K.box("upright", (0.045, 0.09, Hs), center=(sx * (W / 2 - 0.03), sy * (D / 2 - 0.05), Hs / 2), bevel=0.004))
    shelves = (0.06, 0.48, 0.9, 1.32, 1.74)
    for k, z in enumerate(shelves):
        if ctx.destroyed and k == 3:
            sb = _board("shelf_fallen", W - 0.02, D - 0.02, 0.025, ctx.rnd(f"s{k}"), cuts=3)
            K.place(sb, rot=(0, 14, 0))
            K.place(sb, (0, 0, z - 0.18))
            fr.append(sb)
            continue
        sb = _board(f"shelf{k}", W - 0.02, D - 0.02, 0.025, ctx.rnd(f"s{k}"), cuts=3)
        K.place(sb, (0, 0, z))
        fr.append(sb)
    brace = _board("brace", math.hypot(W - 0.1, Hs - 0.3), 0.08, 0.02, ctx.rnd("brace"), cuts=3)
    K.place(brace, rot=(90, 0, 0))
    K.place(brace, rot=(0, -math.degrees(math.atan2(Hs - 0.3, W - 0.1)), 0))
    K.place(brace, (0, D / 2 - 0.01, Hs / 2))
    fr.append(brace)
    f = K.merge_parts(fr, "shelving")
    K.uv_box(f, 1.0, long_axis=0)
    ctx.add(f, wood, uv=None, smooth=None, patches=0.5, moss=0.15)
    r = ctx.rnd("jars")
    dr = ctx.drnd("jars")
    for k, z in enumerate(shelves[1:], start=1):
        if ctx.destroyed and k == 3:
            continue
        x = -W / 2 + 0.09
        while x < W / 2 - 0.08:
            quart = r.random() < 0.55
            rad, h = (0.046, 0.17) if quart else (0.04, 0.13)
            gap = r.random() < (0.32 if ctx.worn else 0.12)
            if not gap:
                content = _PRESERVES[r.randrange(len(_PRESERVES))]
                if ctx.worn and dr.random() < 0.3:
                    content = "farm_preserve_spoiled"
                broken = ctx.worn and dr.random() < 0.12
                y = r.uniform(-0.08, 0.06) + (0.0 if r.random() < 0.6 else -0.1)
                _jar(ctx, x, y, z + 0.0125, rad=rad, h=h, content=content, broken=broken)
            x += rad * 2 + r.uniform(0.012, 0.03)
    for k, x in enumerate((-0.3, 0.25)):
        crock = K.lathe("crock", [(0.0, 0.0), (0.12, 0.0), (0.135, 0.03), (0.14, 0.2), (0.13, 0.27), (0.12, 0.28), (0.11, 0.27), (0.0, 0.26)], segs=14)
        ctx.add(crock, "ceramic_white" if ctx.clean else "enamel_appliance", uv="cyl", smooth=40, wear=0.7, at=((x, 0.0, shelves[0] + 0.0125), None))
        lid = K.cyl("crocklid", 0.11, 0.02, segs=14, center=(x, 0.0, shelves[0] + 0.3))
        ctx.add(lid, "furn_wood_raw", uv="cyl", smooth=40)
    if ctx.destroyed or ctx.worn:
        sh = []
        for k in range(10 if ctx.destroyed else 4):
            sh.append(K.box("shard", (dr.uniform(0.02, 0.05), dr.uniform(0.015, 0.04), 0.003)))
            K.place(sh[-1], (dr.uniform(-0.5, 0.5), dr.uniform(-0.45, -0.22), 0.002), rot=(0, 0, dr.uniform(0, 180)))
        so = K.merge_parts(sh, "shards")
        K.uv_box(so, 2.0)
        ctx.add(so, "farm_jar_glass", uv=None, ao=False)
        puddle = K.cyl("puddle", 0.18 if ctx.destroyed else 0.1, 0.004, segs=12, center=(0.1, -0.33, 0.002))
        K.place(puddle, scale=(1.4, 0.8, 1.0))
        ctx.add(puddle, "farm_preserve_beet", uv="planar", smooth=40)
    ctx.col_box((-W / 2, -D / 2, 0), (W / 2, D / 2, Hs))


def farm_preserve_jars(ctx: K.Ctx) -> None:
    """A handful of quart and pint jars on the floor by the shelves, one tipped over, a stoneware
    jug beside them. Worn: dusty, two gone bad. Destroyed: most of them smashed."""
    r = ctx.rnd("jars")
    dr = ctx.drnd("jars")
    spots = [(-0.12, 0.02), (-0.02, -0.03), (0.08, 0.03), (0.0, 0.08), (0.1, -0.06), (-0.12, -0.08)]
    for k, (x, y) in enumerate(spots):
        quart = k % 2 == 0
        rad, h = (0.046, 0.17) if quart else (0.04, 0.13)
        content = _PRESERVES[r.randrange(len(_PRESERVES))]
        if ctx.worn and dr.random() < 0.35:
            content = "farm_preserve_spoiled"
        broken = ctx.destroyed and k != 2
        tilt = None
        z = 0.0
        if k == 4 and not ctx.destroyed:
            tilt = (0, 88, 30)
            z = rad
        # Ten sides: these sit on the floor in plain view (the shelf's jars keep six).
        _jar(ctx, x, y, z, rad=rad, h=h, content=content, broken=broken, tilt=tilt, segs=10)
    jug = K.lathe("jug", [(0.0, 0.0), (0.075, 0.0), (0.085, 0.03), (0.085, 0.14), (0.06, 0.2), (0.022, 0.23), (0.022, 0.26), (0.0, 0.26)], segs=12)
    hd = K.tube("jughandle", [(0.02, 0, 0.24), (0.06, 0, 0.25), (0.09, 0, 0.19), (0.08, 0, 0.15)], 0.009, segs=5)
    jg = K.merge_parts([jug, hd], "jug")
    ctx.add(jg, "enamel_appliance", uv="cyl", smooth=40, wear=0.8, at=((0.22, 0.05, 0.0), (0, 0, 120)))
    if ctx.destroyed:
        sh = []
        for k in range(12):
            sh.append(K.box("shard", (dr.uniform(0.02, 0.05), dr.uniform(0.015, 0.04), 0.003)))
            K.place(sh[-1], (dr.uniform(-0.25, 0.25), dr.uniform(-0.2, 0.15), 0.002), rot=(0, 0, dr.uniform(0, 180)))
        so = K.merge_parts(sh, "shards")
        K.uv_box(so, 2.0)
        ctx.add(so, "farm_jar_glass", uv=None, ao=False)
    ctx.col_box((-0.18, -0.12, 0), (0.3, 0.13, 0.26))


def farm_crate_produce(ctx: K.Ctx) -> None:
    """Slatted produce crate (0.55 x 0.38 x 0.3) heaped with root-cellar stores (`produce`:
    potato / apple / onion). Worn: the crop shrivelled and sprouting, a slat split. Destroyed:
    crate burst, spilled across the floor."""
    produce = str(ctx.param("produce", "potato"))
    mat = {"potato": "farm_potato", "apple": "farm_apple", "onion": "farm_onion"}.get(produce, "farm_potato")
    L, Wc, Hc = 0.55, 0.38, 0.3
    t = 0.012
    wood = "wood_fresh" if ctx.clean else "farm_wood_grey"
    parts = []
    for sx in (-1, 1):
        parts.append(K.box("endboard", (0.02, Wc, Hc), center=(sx * (L / 2 - 0.01), 0, Hc / 2), bevel=0.003))
        parts.append(K.box("handhold", (0.022, 0.1, 0.03), center=(sx * (L / 2 - 0.01), 0, Hc - 0.05)))
    for side in (-1, 1):
        for k, z in enumerate((0.04, 0.15, 0.26)):
            if ctx.destroyed and side < 0 and k > 0:
                continue
            sl = _board("slat", L - 0.02, 0.07, t, ctx.rnd(f"slat{side}{k}"), cuts=2)
            K.orient(sl, "x", "y" if side > 0 else "-y", (0, side * (Wc / 2 - t / 2), z))
            parts.append(sl)
    for y in (-0.12, 0.0, 0.12):
        parts.append(K.box("bottom", (L - 0.04, 0.09, t), center=(0, y, t / 2)))
    crate = K.merge_parts(parts, "crate")
    K.uv_box(crate, 1.0, long_axis=0)
    ctx.add(crate, wood, uv=None, smooth=None, patches=0.5)
    r = ctx.rnd("crop")
    n = 26 if produce != "apple" else 18
    for k in range(n):
        rr = {"potato": 0.042, "apple": 0.038, "onion": 0.036}.get(produce, 0.04) * r.uniform(0.8, 1.15)
        if ctx.worn:
            rr *= 0.88
        sc = {"potato": (1.35, 1.0, 0.85), "apple": (1.0, 1.0, 0.92), "onion": (1.0, 1.0, 0.9)}.get(produce, (1.2, 1.0, 0.9))
        # Apples are round and shiny: a bare icosahedron reads as a die, so they get one more level.
        b = K.blob("crop", rr, subdiv=2 if produce == "apple" else 1, scale=sc, rough=0.12 if produce == "potato" else 0.04,
                   seed=ctx.seed + k)
        layer = k // 9
        if ctx.destroyed:
            loc = (r.uniform(-0.4, 0.5), r.uniform(-0.55, 0.0) if k % 3 else r.uniform(-0.12, 0.12), rr * sc[2] * 0.9)
        else:
            loc = (r.uniform(-L / 2 + 0.07, L / 2 - 0.07), r.uniform(-Wc / 2 + 0.06, Wc / 2 - 0.06), 0.06 + layer * 0.07 + r.uniform(0.0, 0.03))
        # 60 deg: an icosahedron's faces meet at ~42 deg, so a 40 deg split left every crop faceted.
        ctx.add(b, mat, uv="box", smooth=60, patches=0.3, at=(loc, (r.uniform(0, 180), r.uniform(0, 180), r.uniform(0, 180))))
        if produce == "onion" and k % 3 == 0:
            tip = K.tube("onion_neck", [(0, 0, rr * 0.8), (0, 0.004, rr * 1.4)], 0.006, segs=4)
            ctx.add(tip, "farm_hay_old", at=(loc, None))
        if ctx.worn and produce == "potato" and k % 5 == 0:
            sprout = K.tube("sprout", [(0, 0, rr * 0.7), (0.01, 0.01, rr * 1.4), (0.025, 0.0, rr * 1.8)], 0.0035, segs=4)
            ctx.add(sprout, "candle_wax", at=(loc, None))
    if ctx.destroyed:
        ctx.col_box((-0.45, -0.6, 0), (0.55, 0.2, 0.3))
    else:
        ctx.col_box((-L / 2, -Wc / 2, 0), (L / 2, Wc / 2, Hc))


def farm_shell_box(ctx: K.Ctx) -> None:
    """Papa's box of 12-gauge shells left on its side, flap torn open, red paper hulls with brass
    heads, a few rolled out. Worn: the card damp and slumped, shells tarnished."""
    card = "cardboard" if ctx.clean else "cardboard_wet"
    bx = K.box("shellbox", (0.13, 0.075, 0.065), center=(0, 0, 0.0325), bevel=0.003, cuts=(2, 1, 1))
    if ctx.worn:
        K.crumple(bx, 0.004, scale=20.0, seed=ctx.seed)
    flap = K.box("flap", (0.13, 0.075, 0.002), center=(0, 0.0375, 0.001))
    K.place(flap, rot=(-125, 0, 0))
    K.place(flap, (0, 0.0, 0.065))
    box = K.merge_parts([bx, flap], "box")
    K.uv_box(box, 4.0)
    m = _xf((0, 0, 0.0375)) @ _xf(rot=(-90, 0, 12)) @ _xf((0, 0, -0.0325))
    box.data.transform(m)
    box.data.update()
    K.lift_min(box)
    ctx.add(box, card, uv=None, smooth=None, patches=0.4)
    r = ctx.rnd("shells")
    hulls, heads = [], []
    spots = [(-0.04, 0.03, 0.0), (-0.015, 0.03, 0.0), (0.01, 0.03, 0.0), (0.035, 0.03, 0.0),
             (0.1, -0.04, 1.0), (0.13, 0.01, 1.0), (0.06, -0.07, 1.0)]
    for k, (x, y, lying) in enumerate(spots):
        hull = K.cyl("hull", 0.0105, 0.058, segs=8, center=(0, 0, 0.012 + 0.029))
        head = K.cyl("head", 0.0115, 0.012, segs=8, center=(0, 0, 0.006))
        if lying:
            mm = _xf((x, y, 0.0115)) @ _xf(rot=(0, 90, r.uniform(0, 180)))
        else:
            mm = _xf((x, y + 0.01, 0.0115)) @ _xf(rot=(0, 90, 0)) @ _xf((0, 0, 0.0))
        for o in (hull, head):
            o.data.transform(mm)
            o.data.update()
        hulls.append(hull)
        heads.append(head)
    hl = K.merge_parts(hulls, "hulls")
    hd = K.merge_parts(heads, "heads")
    K.uv_box(hl, 6.0)
    K.uv_box(hd, 6.0)
    ctx.add(hl, "plastic_red", uv=None, smooth=60, wear=0.6)
    ctx.add(hd, "furn_brass", uv=None, smooth=60, wear=0.8)
    ctx.col_box((-0.08, -0.08, 0), (0.17, 0.06, 0.08))


# --- Item models (pickups / dropped items: origin bottom centre) ---------------------------------

def farm_item_preserves(ctx: K.Ctx) -> None:
    """A quart jar of Ife's peaches, ring band and lid, a paper label tied on with twine."""
    _jar(ctx, 0.0, 0.0, 0.0, rad=0.046, h=0.17, content="farm_preserve_peach", segs=12)
    tag = K.box("label", (0.035, 0.002, 0.045), center=(0.0, -0.048, 0.09))
    ctx.add(tag, "paper_trash", uv="planar", uv_axis=1, rect=K.ATLAS_PAPER["note"])
    tw = _hoop("tie", 0.042, 0.158, tube_r=0.0016, segs=12, flat=(1.0, 1.0))
    ctx.add(tw, "farm_twine", wear=0.3)
    ctx.col_box((-0.047, -0.047, 0), (0.047, 0.047, 0.18))


def farm_item_potatoes(ctx: K.Ctx) -> None:
    """Three cellar potatoes, dry soil on them, one sprouting."""
    for k, (x, y, z, rz) in enumerate(((0.0, 0.0, 0.03, 0), (0.06, 0.02, 0.028, 40), (0.03, -0.045, 0.026, 110))):
        b = K.blob("potato", 0.04, subdiv=2, scale=(1.35, 1.0, 0.8), rough=0.12, seed=ctx.seed + k)
        ctx.add(b, "farm_potato", smooth=70, at=((x, y, z), (0, 0, rz)))
    sp = K.tube("sprout", [(0.03, -0.045, 0.05), (0.04, -0.04, 0.065), (0.05, -0.05, 0.075)], 0.003, segs=4)
    ctx.add(sp, "candle_wax")
    ctx.col_box((-0.06, -0.08, 0), (0.12, 0.05, 0.065))


# ============================================================================================

BUILDERS = {
    "farm_hay_bale_square": farm_hay_bale_square,
    "farm_hay_bale_round": farm_hay_bale_round,
    "farm_fence_rail": farm_fence_rail,
    "farm_fence_wire": farm_fence_wire,
    "farm_gate": farm_gate,
    "farm_tractor_wreck": farm_tractor_wreck,
    "farm_plough": farm_plough,
    "farm_water_trough": farm_water_trough,
    "farm_chicken_coop": farm_chicken_coop,
    "farm_windmill_pump": farm_windmill_pump,
    "farm_grain_bin": farm_grain_bin,
    "farm_wagon_wheel": farm_wagon_wheel,
    "farm_feed_sacks": farm_feed_sacks,
    "farm_feed_bin": farm_feed_bin,
    "farm_milk_can": farm_milk_can,
    "farm_pitchfork": farm_pitchfork,
    "farm_tool_rack": farm_tool_rack,
    "farm_saddle_stand": farm_saddle_stand,
    "farm_stall_partition": farm_stall_partition,
    "farm_tool_chest": farm_tool_chest,
    "farm_lantern": farm_lantern,
    "farm_stove_castiron": farm_stove_castiron,
    "farm_butter_churn": farm_butter_churn,
    "farm_washtub": farm_washtub,
    "farm_quilt_bed": farm_quilt_bed,
    "farm_hope_chest": farm_hope_chest,
    "farm_oil_lamp": farm_oil_lamp,
    "farm_cellar_shelf": farm_cellar_shelf,
    "farm_preserve_jars": farm_preserve_jars,
    "farm_crate_potatoes": farm_crate_produce,
    "farm_crate_apples": farm_crate_produce,
    "farm_shell_box": farm_shell_box,
    "farm_jar_preserves": farm_item_preserves,
    "farm_cellar_potatoes": farm_item_potatoes,
}


def build(params: dict, outputs: list[str]) -> None:
    K.run(params, outputs, BUILDERS)
