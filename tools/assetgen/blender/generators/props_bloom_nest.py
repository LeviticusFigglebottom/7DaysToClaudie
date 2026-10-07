"""Bloom nests (ADR-0055): the grown masses of Bloom in the deep woods, landmarks the player burns.

  nest_root_mass      a cage of pale fungal roots arched over a hollow, bracket shelves on them,
                      threads slung between, a felted mat round the foot and, in the hollow, the
                      heart: a fused knot of glowing flesh with sacs hanging over it (the part
                      BloomNests makes burnable; its core box sits there)
  nest_pod            a cluster of standing sacs on stalks out of a felt cushion, veined, the big
                      one splitting at the top (the Hollowed come out of these)
  nest_shelf_cluster  a dead stump swallowed by the Bloom: felt sheath, tiers of brackets, caps
  nest_remains        what it took: a human skeleton bound to the ground in felt, a torn pack and
                      what spilled from it

Conditions: 'clean' is the living nest; 'destroyed' is burned (charred and broken roots, burst and
blackened sacs, ash over the mat). nest_remains has no burned form (the bones stay as they are).

Conventions (docs/ASSET_PIPELINE.md): metres, Z up, front -Y, origin bottom centre. Materials
nest_* (game/data/materials/props_bloom_nest.json) use the bloom_fungus shader, which reads the
vertex colours as R = baked AO, G = gills / underside (greyer, and they glow at night like the
Bloom's threads), B = thinness (light through it). ctx.add's paint writes G from `base` / `extra`
(edge and patch wear off) and B from `tint`, so every part sets its own.
"""
from __future__ import annotations

import math
import random

from mathutils import Vector, noise

from lib import props_ext_kit as K
from lib import props_outskirts_parts as O
from lib import props_wild_parts as W


ROOT = "nest_root"          # root flesh: pale, waxy, fibrous (bloom_cap texture); threads glow at night
FELT = "nest_felt"          # the felted mycelium of the mat and cushions (bloom_mound texture)
FLESH = "nest_flesh"        # sacs and the heart: waxy, translucent, glowing veins
SHELF = "nest_shelf"        # bracket shelves and caps (bloom_cap texture), gills under
CHAR = "nest_char"          # burned root
CHAR_FLESH = "nest_char_flesh"  # burst, blackened sacs
ASH = "nest_ash"


def _bloom(ctx, obj, mat, *, glow: float = 0.0, thin: float = 0.0, under: float = 0.0, smooth: float = 60,
           uv_scale: float = 1.6, uv: str = "box"):
    """Adds a Bloom part: G = glow (+ `under` on faces turned down), B = thinness, no wear."""
    extra = None
    if under > 0.0:
        extra = lambda p, n: under * K.smooth01(0.1, 0.6, -n.z)  # noqa: E731
    return ctx.add(obj, mat, uv=uv, uv_scale=uv_scale, smooth=smooth, edge=0.0, patches=0.0, base=glow, tint=thin,
                   extra=extra)


def _burnt(ctx, obj, mat=CHAR, *, smooth: float = 50, uv_scale: float = 1.4):
    return ctx.add(obj, mat, uv="box", uv_scale=uv_scale, smooth=smooth, patches=0.5, edge=0.6)


def _bez(a: Vector, b: Vector, c: Vector, n: int) -> list[Vector]:
    """Quadratic Bezier a -> c pulled toward b, n points."""
    out = []
    for i in range(n):
        t = i / (n - 1)
        out.append(a * (1 - t) ** 2 + b * 2 * t * (1 - t) + c * t * t)
    return out


def _gnarl(pts: list[Vector], amp: float, seed: int, *, keep_ends: bool = True) -> list[Vector]:
    """Wanders a polyline sideways by smooth noise (roots don't run straight)."""
    off = Vector((seed * 0.37 % 41, seed * 0.71 % 43, seed * 0.13 % 47))
    out = []
    n = len(pts)
    for i, p in enumerate(pts):
        w = 1.0 if not keep_ends else math.sin(math.pi * i / max(1, n - 1)) ** 0.6
        d = Vector(noise.noise_vector(p * 0.9 + off))
        out.append(p + d * amp * w)
    return out


def _radii(n: int, r0: float, r1: float, seed: int, *, knots: float = 0.25) -> list[float]:
    """Tapering radii with knotted swellings along the way."""
    rr = random.Random(seed)
    out = []
    for i in range(n):
        t = i / max(1, n - 1)
        r = r0 + (r1 - r0) * t ** 0.8
        out.append(r * (1.0 + knots * max(0.0, rr.uniform(-0.6, 1.0))))
    return out


def _root(ctx, name, pts, r0, r1, seed, *, burnt=False, glow=0.0, segs=9, disp=0.25):
    o = K.tube(name, pts, _radii(len(pts), r0, r1, seed), segs=segs)
    K.noise_disp(o, r0 * disp, scale=3.5, seed=seed)
    if burnt:
        K.noise_disp(o, r0 * 0.12, scale=12.0, seed=seed + 1)
        return _burnt(ctx, o)
    return _bloom(ctx, o, ROOT, glow=glow, thin=0.1, smooth=70, uv_scale=1.6)


def _bracket(name, r, seed, *, thick=0.06):
    """A bracket fungus: half a lathed shelf protruding along +X from x=0, flat top with a rolled
    rim, the underside slightly domed; wavy margin."""
    prof = [(0.0, -thick * 0.6), (r * 0.55, -thick * 0.5), (r * 0.92, -thick * 0.15), (r, 0.0),
            (r * 0.96, thick * 0.35), (r * 0.6, thick * 0.55), (0.0, thick * 0.6)]
    o = K.lathe(name, prof, segs=12, angle0=-math.pi / 2, arc=math.pi)
    rr = random.Random(seed)
    ph = rr.uniform(0, math.tau)
    K.map_verts(o, lambda co: Vector((co.x * (1.0 + 0.08 * math.sin(math.atan2(co.y, max(co.x, 1e-4)) * 5 + ph)), co.y * 1.15,
                                     co.z + 0.25 * thick * (co.x / r) ** 2)))
    K.noise_disp(o, thick * 0.15, scale=18.0, seed=seed)
    return o


def _shelves(ctx, at: Vector, out_dir: Vector, n: int, size: float, seed: int, *, burnt=False):
    """A stack of brackets on a surface at `at`, protruding along `out_dir` (horizontal)."""
    rr = random.Random(seed)
    d = Vector((out_dir.x, out_dir.y, 0.0))
    d = d.normalized() if d.length > 1e-6 else Vector((1, 0, 0))
    yaw = math.degrees(math.atan2(d.y, d.x))
    z = 0.0
    for k in range(n):
        r = size * rr.uniform(0.55, 1.0) * (1.0 - 0.15 * k)
        o = _bracket(f"shelf{seed}_{k}", r, seed + k * 7)
        side = rr.uniform(-40, 40)
        K.place(o, rot=(rr.uniform(-8, 8), rr.uniform(-12, 4), yaw + side))
        sd = Vector((math.cos(math.radians(yaw + side)), math.sin(math.radians(yaw + side)), 0.0))
        K.place(o, at + Vector((0, 0, z)) + (sd - d) * r * 0.25 - sd * r * 0.12)
        z += size * rr.uniform(0.35, 0.75)
        if burnt:
            _burnt(ctx, o, CHAR, smooth=40)
        else:
            _bloom(ctx, o, SHELF, under=1.0, thin=0.5, smooth=45, uv="planar", uv_scale=1.0 / max(r, 0.05))


def _cap(name, base: Vector, R: float, H: float, seed: int, lean=(0.0, 0.0)):
    """A simple mushroom (stem + convex cap) for scattering."""
    rr = random.Random(seed)
    stem = K.tube(name + "s", [base + Vector((0, 0, -0.02)), base + Vector((lean[0] * H * 0.5, lean[1] * H * 0.5, H * 0.55)),
                              base + Vector((lean[0] * H, lean[1] * H, H))], [R * 0.32, R * 0.24, R * 0.2], segs=6)
    top = base + Vector((lean[0] * H, lean[1] * H, H))
    cap = K.lathe(name + "c", [(0.0, -R * 0.12), (R * 0.4, -R * 0.15), (R, -R * 0.05), (R * 0.95, R * 0.12),
                               (R * 0.6, R * 0.38), (0.0, R * 0.48)], segs=10)
    K.noise_disp(cap, R * 0.06, scale=30.0, seed=seed)
    K.place(cap, top, (rr.uniform(-12, 12), rr.uniform(-12, 12), 0))
    return stem, cap


def _caps(ctx, centre: Vector, r_in: float, r_out: float, n: int, seed: int, z_fn=None, size: float = 1.0):
    rr = random.Random(seed)
    for k in range(n):
        a = rr.uniform(0, math.tau)
        r = rr.uniform(r_in, r_out)
        p = centre + Vector((math.cos(a) * r, math.sin(a) * r, 0.0))
        if z_fn is not None:
            p.z = z_fn(p) - 0.01
        R = rr.uniform(0.025, 0.06) * size
        s, c = _cap(f"cap{seed}_{k}", p, R, R * rr.uniform(2.2, 3.6), seed + k, (rr.uniform(-0.3, 0.3), rr.uniform(-0.3, 0.3)))
        _bloom(ctx, s, SHELF, thin=0.3, smooth=50, uv_scale=6.0)
        _bloom(ctx, c, SHELF, under=1.0, thin=0.6, smooth=45, uv_scale=6.0)


def _felt_mat(name, profile, seed, *, segs=40, tongues=0.18):
    """A felt cushion of revolution with a ragged, tongued outline."""
    o = K.lathe(name, profile, segs=segs, cap_bottom=False)
    off = random.Random(seed).uniform(0, 50)
    rmax = max(r for r, _ in profile)

    def rag(co):
        a = math.atan2(co.y, co.x)
        q = Vector((math.cos(a) * 1.7 + off, math.sin(a) * 1.7, 0.3))
        k = 1.0 + tongues * max(0.0, noise.noise(q)) * 2.0 + 0.06 * noise.noise(q * 3.1)
        r = math.hypot(co.x, co.y)
        w = (r / rmax) ** 2
        return Vector((co.x * (1 + (k - 1) * w), co.y * (1 + (k - 1) * w), co.z))
    K.map_verts(o, rag)
    K.noise_disp(o, 0.03, scale=3.0, seed=seed)
    return o


def _sac(name, R: float, H: float, seed: int, *, split: float = 0.0):
    """A pod: an egg-shaped sac of revolution (base at z=0, top at H), lumpy, its top optionally
    split open (`split` = fraction of the height the tear runs down)."""
    prof = [(0.0, 0.0), (R * 0.35, H * 0.02), (R * 0.8, H * 0.15), (R, H * 0.4), (R * 0.92, H * 0.62),
            (R * 0.62, H * 0.84), (R * 0.28, H * 0.96), (0.0, H)]
    o = K.lathe(name, prof, segs=20)
    # Lobed and lumpy: swellings round it (what is curled up inside pressing out), finer knobs.
    rr0 = random.Random(seed)
    ph, ph2 = rr0.uniform(0, math.tau), rr0.uniform(0, math.tau)
    K.map_verts(o, lambda co: Vector((co.x * (1.0 + 0.08 * math.sin(math.atan2(co.y, co.x) * 3 + ph + co.z / H * 2.5)
                                              + 0.05 * math.sin(co.z / H * 9 + ph2)),
                                      co.y * (1.0 + 0.08 * math.sin(math.atan2(co.y, co.x) * 3 + ph + co.z / H * 2.5)
                                              + 0.05 * math.sin(co.z / H * 9 + ph2)), co.z)))
    K.noise_disp(o, R * 0.1, scale=3.0 / R, seed=seed)
    if split > 0.0:
        z0 = H * (1.0 - split)
        rr = random.Random(seed)
        a0 = rr.uniform(0, math.tau)
        K.delete_faces(o, lambda c, n: c.z > z0 and abs(math.remainder(math.atan2(c.y, c.x) - a0, math.tau)) < 0.45)
    return o


def _veins(ctx, centre: Vector, R: float, H: float, n: int, seed: int, *, z0=0.0, mat=ROOT, glow=1.0):
    """Raised veins running up a sac's surface (meridians wandering a little)."""
    rr = random.Random(seed)
    for k in range(n):
        a = rr.uniform(0, math.tau)
        pts = []
        for i in range(7):
            t = i / 6
            z = H * (0.05 + 0.75 * t)
            prof_r = R * (0.5 + 0.5 * math.sin(math.pi * min(1.0, z / H * 1.15))) * 0.97
            aa = a + 0.3 * math.sin(t * 3 + k)
            pts.append(centre + Vector((math.cos(aa) * prof_r, math.sin(aa) * prof_r, z0 + z)))
        o = K.tube(f"vein{seed}_{k}", pts, [R * 0.06, R * 0.055, R * 0.05, R * 0.045, R * 0.035, R * 0.025, R * 0.01], segs=6)
        _bloom(ctx, o, mat, glow=glow, thin=0.2, smooth=50, uv_scale=4.0)


def _hang(ctx, top: Vector, length: float, seed: int, *, sac: float = 0.0, burnt=False):
    """A thread hanging from `top`, swaying a little, with a small sac at its end."""
    rr = random.Random(seed)
    bot = top + Vector((rr.uniform(-0.05, 0.05), rr.uniform(-0.05, 0.05), -length))
    mid = top.lerp(bot, 0.5) + Vector((rr.uniform(-0.04, 0.04), rr.uniform(-0.04, 0.04), 0))
    o = K.tube(f"hang{seed}", [top + Vector((0, 0, 0.05)), mid, bot], [0.022, 0.014, 0.012], segs=5)
    if burnt:
        _burnt(ctx, o)
    else:
        _bloom(ctx, o, ROOT, glow=0.5, thin=0.4, smooth=50, uv_scale=4.0)
    if sac > 0.0:
        s = _sac(f"hsac{seed}", sac, sac * 2.4, seed)
        K.place(s, rot=(180, 0, rr.uniform(0, 360)))
        K.place(s, bot + Vector((0, 0, 0.03)))
        if burnt:
            K.map_verts(s, lambda co: Vector((co.x, co.y, co.z * 0.7 + bot.z * 0.3)))
            _burnt(ctx, s, CHAR_FLESH)
        else:
            _bloom(ctx, s, FLESH, glow=0.35, thin=1.0, smooth=60, uv_scale=3.0)


# ============================================================================================
# Root mass
# ============================================================================================

def nest_root_mass(ctx: K.Ctx) -> None:
    """The nest itself: ~5 m across, up to 3 m high, hunched forward over its mouth (-Y). Its roots
    rise out of a lumpy collar where they fuse, arch in over the heart (some fall short and curl
    out like fingers) and are stepped with bracket shelves; threads and sacs hang inside."""
    burnt = ctx.destroyed
    rr = ctx.rnd("roots")
    apex = Vector((0.0, 0.55, 2.7))
    heart = Vector((0.0, 0.1, 0.0))

    def ground(p: Vector) -> float:
        r = math.hypot(p.x, p.y - 0.1)
        return 0.32 * math.exp(-((r - 1.95) / 0.55) ** 2) + 0.05 * math.exp(-(r / 0.9) ** 2)

    # The mat: a felt ring the roots grow from, a shallow bowl in the hollow, tongues out over the
    # litter.
    prof = [(0.0, 0.05), (0.7, 0.07), (1.35, 0.18), (1.75, 0.31), (2.1, 0.33), (2.5, 0.18), (2.95, 0.05), (3.3, -0.04)]
    mat = _felt_mat("mat", prof, ctx.seed + 1, tongues=0.28)
    K.place(mat, (0.0, 0.1, 0.0))
    if burnt:
        _burnt(ctx, mat, ASH, smooth=60, uv_scale=0.5)
    else:
        _bloom(ctx, mat, FELT, glow=0.15, thin=0.2, smooth=70, uv_scale=1.6)
    # The collar: lumps where the roots fuse, round the ring except the mouth.
    gap = math.radians(46.0)
    for k in range(13):
        a = -math.pi / 2 + gap * 0.8 + (math.tau - 1.6 * gap) * (k + rr.uniform(-0.3, 0.3)) / 12
        rb = rr.uniform(1.85, 2.2)
        c = Vector((math.cos(a) * rb, 0.1 + math.sin(a) * rb, rr.uniform(0.05, 0.2)))
        b = K.blob(f"collar{k}", rr.uniform(0.32, 0.5), subdiv=2, scale=(1.5, 1.0, 0.75 if not burnt else 0.45), center=(0, 0, 0),
                   rough=0.3, seed=ctx.seed + 900 + k, noise_scale=2.2)
        K.place(b, c, (0, 0, math.degrees(a) + 90))
        if burnt:
            _burnt(ctx, b, CHAR, smooth=55)
        else:
            _bloom(ctx, b, ROOT, glow=0.2, thin=0.15, smooth=65, uv_scale=1.4)
    # Main roots: out of the collar, arching in over the heart toward an apex hunched back over it;
    # some fall short and curl outward, a clawed hand. Each runs past its end in a finger curling down.
    n_main = 12
    tops = []
    claws = {2, 6, 9}
    for i in range(n_main):
        a = -math.pi / 2 + gap + (math.tau - 2 * gap) * (i + rr.uniform(-0.25, 0.25)) / (n_main - 1)
        rb = rr.uniform(1.8, 2.3)
        base = Vector((math.cos(a) * rb, 0.1 + math.sin(a) * rb, -0.15))
        r0 = rr.uniform(0.15, 0.3)
        if i in claws:
            # Rises steeply, then curls outward and down.
            up = Vector((math.cos(a) * (rb - 0.2), 0.1 + math.sin(a) * (rb - 0.2), rr.uniform(1.7, 2.3)))
            tip = Vector((math.cos(a) * (rb + 0.9), 0.1 + math.sin(a) * (rb + 0.9), rr.uniform(1.2, 1.7)))
            pts = _bez(base, up + Vector((0, 0, 0.6)), tip, 10)
            r0 *= 0.85
        else:
            mid = Vector((math.cos(a) * (rb + 0.45), 0.1 + math.sin(a) * (rb + 0.45), rr.uniform(1.4, 2.3)))
            tip_a = a + math.pi + rr.uniform(-0.6, 0.6)
            tip = apex + Vector((math.cos(tip_a) * rr.uniform(0.15, 0.8), math.sin(tip_a) * rr.uniform(0.15, 0.8),
                                 rr.uniform(-0.5, 0.25)))
            pts = _bez(base, mid, tip, 10)
            # The finger past the apex, curling down toward the heart.
            d = (pts[-1] - pts[-2]).normalized()
            f1 = pts[-1] + d * 0.3 + Vector((0, 0, -0.1))
            f2 = f1 + d * 0.15 + Vector((0, 0, -0.3))
            pts += [f1, f2]
        pts = _gnarl(pts, 0.16, ctx.seed + i * 13)
        if burnt and i % 3 != 1:
            # Burned through: the arch broke and fell, a charred stump left standing.
            cut = rr.randint(4, 7)
            pts = pts[:cut]
            _root(ctx, f"root{i}", pts, r0, r0 * 0.55, ctx.seed + i, burnt=True)
            fall = [Vector((p.x * 1.15 + math.cos(a) * 0.5 * k, p.y * 1.15 + math.sin(a) * 0.5 * k, 0.08)) for k, p in enumerate(pts[:4])]
            _root(ctx, f"fallen{i}", fall, r0 * 0.6, r0 * 0.35, ctx.seed + 300 + i, burnt=True, segs=7)
        else:
            _root(ctx, f"root{i}", pts, r0, 0.035, ctx.seed + i, burnt=burnt)
        tops.append(pts)
        # Collision: the root's run in three convex pieces.
        for s0, s1 in ((0, 4), (3, 7), (6, len(pts))):
            seg = pts[s0:s1]
            if len(seg) < 2:
                continue
            hull = []
            for p in seg:
                for dv in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                    hull.append(p + Vector(dv) * r0 * 0.9)
            ctx.col_hull(hull, max_points=24)
        # Brackets on the outside of the roots, stepping up them.
        if not burnt or i % 4 == 0:
            for k, t in enumerate((rr.uniform(0.18, 0.3), rr.uniform(0.42, 0.58))):
                if k == 1 and rr.random() < 0.4:
                    continue
                j = min(int(t * 9), len(pts) - 1)
                p = pts[j]
                out = Vector((p.x, p.y - 0.1, 0.0))
                _shelves(ctx, p + out.normalized() * r0 * 0.75, out, rr.randint(2, 4) if not burnt else 1,
                         rr.uniform(0.3, 0.5) * (1.0 - 0.3 * t), ctx.seed + 100 + i * 5 + k, burnt=burnt)
    # The mouth: a thick root arching over the front gap, the lintel of the hollow.
    ml = Vector((math.cos(-math.pi / 2 - gap) * 2.0, 0.1 + math.sin(-math.pi / 2 - gap) * 2.0, -0.1))
    mr = Vector((math.cos(-math.pi / 2 + gap) * 2.0, 0.1 + math.sin(-math.pi / 2 + gap) * 2.0, -0.1))
    lintel = _gnarl(_bez(ml, Vector((0.0, -2.0, 3.9)), mr, 13), 0.12, ctx.seed + 77)
    if burnt:
        _root(ctx, "lintel_l", lintel[:5], 0.28, 0.16, ctx.seed + 78, burnt=True)
        _root(ctx, "lintel_r", lintel[9:], 0.16, 0.28, ctx.seed + 79, burnt=True)
    else:
        lr = [0.32, 0.27, 0.23, 0.2, 0.18, 0.17, 0.17, 0.17, 0.18, 0.2, 0.23, 0.27, 0.32]
        o = K.tube("lintel", lintel, lr, segs=10)
        K.noise_disp(o, 0.06, scale=3.5, seed=ctx.seed + 78)
        _bloom(ctx, o, ROOT, glow=0.2, thin=0.1, smooth=70)
        for k, j in enumerate((3, 9)):
            out = Vector((lintel[j].x, -1.0, 0.0))
            _shelves(ctx, lintel[j] + Vector((0, -0.2, -0.05)), out, 3, 0.42, ctx.seed + 150 + k)
        # Threads hanging in the mouth like a curtain.
        for k in range(5):
            _hang(ctx, lintel[4 + k] - Vector((0, 0, 0.12)), rr.uniform(0.5, 1.3), ctx.seed + 160 + k,
                  sac=rr.uniform(0.05, 0.09) if k % 2 == 0 else 0.0)
    # Thinner roots twining round the main ones, and buttresses spreading over the ground.
    for i in range(16):
        host = tops[i % n_main]
        ph = rr.uniform(0, math.tau)
        tw = []
        for j, p in enumerate(host[:8]):
            a = ph + j * 0.9
            tw.append(p + Vector((math.cos(a) * 0.24, math.sin(a) * 0.24, math.sin(a + 1.0) * 0.12)))
        if burnt:
            tw = tw[:rr.randint(3, 5)]
        _root(ctx, f"twine{i}", tw, 0.09, 0.03, ctx.seed + 200 + i, burnt=burnt, segs=6, disp=0.4)
    for i in range(12):
        a = math.tau * (i + rr.uniform(0, 0.6)) / 12
        r0 = rr.uniform(1.6, 2.0)
        r1 = rr.uniform(2.9, 3.8)
        pts = [Vector((math.cos(a + 0.15 * t) * (r0 + (r1 - r0) * t), 0.1 + math.sin(a + 0.15 * t) * (r0 + (r1 - r0) * t),
                       0.28 * (1 - t) ** 1.5 - 0.14 * t)) for t in [k / 6 for k in range(7)]]
        o = K.tube(f"buttress{i}", _gnarl(pts, 0.12, ctx.seed + 400 + i), _radii(7, 0.17, 0.03, ctx.seed + i), segs=7,
                   flat=(1.0, 0.55))
        K.noise_disp(o, 0.03, scale=4.0, seed=ctx.seed + 400 + i)
        if burnt:
            _burnt(ctx, o)
        else:
            _bloom(ctx, o, ROOT, glow=0.4, thin=0.1, smooth=60)
    # The heart: a fused knot of flesh in the hollow, veined, its threads glowing.
    hr = ctx.rnd("heart")
    lobes = [(Vector((0, 0, 0.6)), 0.55), (Vector((0.34, 0.14, 0.46)), 0.38), (Vector((-0.36, 0.06, 0.44)), 0.36),
             (Vector((0.08, 0.26, 1.0)), 0.34), (Vector((-0.14, -0.2, 0.88)), 0.27), (Vector((0.26, -0.16, 0.28)), 0.25)]
    for k, (c, r) in enumerate(lobes):
        b = K.blob(f"heart{k}", r, subdiv=3, scale=(1.0, 0.95, 0.85 if not burnt else 0.5), center=heart + c * (1.0 if not burnt else 0.6),
                   rough=0.2, seed=ctx.seed + 500 + k, noise_scale=2.5)
        if burnt:
            _burnt(ctx, b, CHAR_FLESH, smooth=60)
        else:
            _bloom(ctx, b, FLESH, glow=0.25, thin=0.9, smooth=70, uv_scale=2.0)
    if not burnt:
        for k in range(11):
            a = hr.uniform(0, math.tau)
            p0 = heart + Vector((math.cos(a) * 1.0, math.sin(a) * 1.0, 0.05))
            p1 = heart + Vector((math.cos(a) * 0.58, math.sin(a) * 0.58, hr.uniform(0.4, 0.7)))
            p2 = heart + Vector((math.cos(a + 0.6) * 0.28, math.sin(a + 0.6) * 0.28, hr.uniform(0.9, 1.2)))
            o = K.tube(f"hvein{k}", _gnarl([p0, p1, p2], 0.05, ctx.seed + 600 + k), [0.06, 0.04, 0.018], segs=6)
            _bloom(ctx, o, ROOT, glow=1.0, thin=0.3, smooth=50, uv_scale=3.0)
        # Sacs hanging from the roof of the cage over the heart; threads slung between roots.
        for k in range(8):
            pts = tops[(k * 5) % n_main]
            if len(pts) < 10:
                continue
            top = pts[hr.randint(6, 9)]
            _hang(ctx, top - Vector((0, 0, 0.12)), hr.uniform(0.35, 1.1), ctx.seed + 700 + k, sac=hr.uniform(0.08, 0.15))
        for k in range(7):
            a = tops[k * 2 % n_main][hr.randint(4, 7)]
            b = tops[(k * 2 + 3) % n_main][hr.randint(4, 7)]
            mid = a.lerp(b, 0.5) + Vector((0, 0, -0.5))
            o = K.tube(f"sling{k}", _bez(a, mid, b, 7), 0.02, segs=5)
            _bloom(ctx, o, ROOT, glow=0.8, thin=0.6, smooth=50, uv_scale=4.0)
        _caps(ctx, Vector((0, 0.1, 0)), 1.0, 3.0, 30, ctx.seed + 800, z_fn=ground)
    else:
        for k in range(4):
            pts = tops[(k * 3 + 1) % n_main]
            if len(pts) > 8:
                _hang(ctx, pts[8] - Vector((0, 0, 0.1)), hr.uniform(0.3, 0.7), ctx.seed + 700 + k, sac=0.08, burnt=True)
    # No collider on the heart: BloomNests puts the burnable core box there.


# ============================================================================================
# Pods
# ============================================================================================

def nest_pod(ctx: K.Ctx) -> None:
    """A cluster of standing sacs out of a felt cushion: the big one ~1.5 m, tearing open at the
    top; two smaller ones leaning off it. Burned: burst open, petals peeled back and blackened."""
    burnt = ctx.destroyed
    rr = ctx.rnd("pod")
    cushion = _felt_mat("cushion", [(0.0, 0.16), (0.35, 0.17), (0.6, 0.12), (0.85, 0.04), (1.0, -0.03)], ctx.seed + 1,
                        segs=28, tongues=0.25)
    if burnt:
        _burnt(ctx, cushion, ASH, smooth=60, uv_scale=1.0)
    else:
        _bloom(ctx, cushion, FELT, glow=0.2, thin=0.2, smooth=70)
    sacs = [(Vector((0.0, 0.05, 0.1)), 0.42, 1.45, (0, 0)), (Vector((0.48, -0.12, 0.05)), 0.26, 0.85, (14, 18)),
            (Vector((-0.42, -0.2, 0.05)), 0.22, 0.7, (-12, -20))]
    for k, (c, R, H, (lx, ly)) in enumerate(sacs):
        # Its stalk: a short neck of felt the sac sits on.
        stalk = K.tube(f"stalk{k}", [c + Vector((0, 0, -0.1)), c + Vector((0, 0, 0.12))], [R * 0.45, R * 0.35], segs=10)
        if burnt:
            _burnt(ctx, stalk)
            s = _sac(f"sac{k}", R, H * 0.8, ctx.seed + k)
            # Burst: the top torn away in ragged petals, what is left flared out and slumped.
            top = H * 0.8
            ph = rr.uniform(0, math.tau)
            K.delete_faces(s, lambda c, n, top=top, ph=ph: c.z > top * (0.5 + 0.18 * math.sin(math.atan2(c.y, c.x) * 5 + ph)))

            def peel(co, top=top):
                f = max(0.0, (co.z - top * 0.25) / (top * 0.45))
                k2 = 1.0 + 0.55 * f * f
                return Vector((co.x * k2, co.y * k2, co.z - 0.12 * top * f * f))
            K.map_verts(s, peel)
            K.place(s, rot=(ly * 0.5, lx * 0.5, rr.uniform(0, 360)))
            K.place(s, c + Vector((0, 0, 0.08)))
            K.solidify(s, 0.02)
            _burnt(ctx, s, CHAR_FLESH, smooth=55)
        else:
            _bloom(ctx, stalk, ROOT, glow=0.3, thin=0.2, smooth=60)
            s = _sac(f"sac{k}", R, H, ctx.seed + k, split=0.28 if k == 0 else 0.0)
            K.place(s, rot=(ly, lx, rr.uniform(0, 360)))
            K.place(s, c + Vector((0, 0, 0.08)))
            _bloom(ctx, s, FLESH, glow=0.3, thin=1.0, smooth=70, uv_scale=2.0)
            # The inner skin seen through the tear: a darker, glowing lining.
            if k == 0:
                lin = _sac("lining", R * 0.9, H * 0.96, ctx.seed + 9)
                K.place(lin, rot=(ly, lx, 0))
                K.place(lin, c + Vector((0, 0, 0.1)))
                _bloom(ctx, lin, FLESH, glow=1.0, thin=0.6, smooth=60, uv_scale=2.0)
            _veins(ctx, c + Vector((0, 0, 0.08)), R, H, 7 if k == 0 else 4, ctx.seed + 20 + k, glow=0.9)
    if not burnt:
        _caps(ctx, Vector((0, 0, 0)), 0.55, 0.95, 9, ctx.seed + 50, z_fn=lambda p: 0.08)
    ctx.col_box((-0.5, -0.45, 0.0), (0.5, 0.5, 1.45 if not burnt else 1.0))
    ctx.col_box((-0.68, -0.42, 0.0), (0.72, 0.1, 0.8 if not burnt else 0.5))


# ============================================================================================
# Shelf cluster
# ============================================================================================

def nest_shelf_cluster(ctx: K.Ctx) -> None:
    """A snapped dead stump the Bloom has swallowed: a felt sheath up the trunk, brackets in tiers
    round it, caps fruiting at its foot."""
    burnt = ctx.destroyed
    rr = ctx.rnd("stump")
    H, R = 1.25, 0.32
    log = W.log_obj("stump", H, R, ctx.seed, sides=12, rings=6, taper=0.15, bow=0.03, bark="burn_wood_char" if burnt else "wild_log_bark",
                    end="wood_log_end_charred" if burnt else "wood_log_end_rotten", knots=0)
    K.orient(log, (0, 0, 1), (1, 0, 0), (0, 0, H / 2 - 0.05))
    # A jagged snapped top: push the top ring's vertices up and down.
    K.map_verts(log, lambda co: Vector((co.x, co.y, co.z + (0.18 * max(0.0, math.sin(math.atan2(co.y, co.x) * 3 + 1.0))
                                                            if co.z > H - 0.15 else 0.0))))
    ctx.add(log, None, uv=None, smooth=45, patches=0.4, edge=0.5)
    # Felt sheath: a sleeve of mycelium over the lower trunk, ragged at its top.
    sheath = K.lathe("sheath", [(R * 1.55, -0.04), (R * 1.25, 0.12), (R * 1.12, 0.45), (R * 1.07, 0.75), (R * 1.0, 0.95)], segs=20,
                     cap_bottom=False, cap_top=False)
    K.noise_disp(sheath, 0.03, scale=5.0, seed=ctx.seed + 3)
    off = rr.uniform(0, 40)
    K.delete_faces(sheath, lambda c, n: c.z > 0.55 + 0.35 * noise.noise(Vector((math.atan2(c.y, c.x) * 1.4 + off, 0.3, 0.6))))
    K.solidify(sheath, 0.025)
    if burnt:
        _burnt(ctx, sheath, ASH)
    else:
        _bloom(ctx, sheath, FELT, glow=0.3, thin=0.2, smooth=60)
    tiers = 4 if not burnt else 2
    for k in range(tiers * 3):
        a = math.tau * k / 3 + rr.uniform(-0.4, 0.4) + (k // 3) * 0.9
        z = 0.2 + (k // 3) * 0.26 + rr.uniform(-0.05, 0.05)
        d = Vector((math.cos(a), math.sin(a), 0))
        _shelves(ctx, d * R * 0.95 + Vector((0, 0, z)), d, 1 if burnt else rr.randint(1, 2), rr.uniform(0.22, 0.34),
                 ctx.seed + 30 + k, burnt=burnt)
    # Roots of felt running off it into the litter.
    for i in range(6):
        a = math.tau * i / 6 + rr.uniform(-0.3, 0.3)
        pts = [Vector((math.cos(a + 0.2 * t) * (R * 1.15 + 0.6 * t), math.sin(a + 0.2 * t) * (R * 1.15 + 0.6 * t), 0.14 * (1 - t) - 0.05))
               for t in [k / 4 for k in range(5)]]
        o = K.tube(f"run{i}", _gnarl(pts, 0.06, ctx.seed + 60 + i), _radii(5, 0.11, 0.06, ctx.seed + i), segs=6, flat=(1.0, 0.5))
        if burnt:
            _burnt(ctx, o)
        else:
            _bloom(ctx, o, ROOT, glow=0.5, thin=0.1, smooth=60)
    if not burnt:
        _caps(ctx, Vector((0, 0, 0)), R * 1.4, 0.75, 14, ctx.seed + 90, z_fn=lambda p: 0.0)
    ctx.col_hull([Vector((math.cos(a) * R * 1.3, math.sin(a) * R * 1.3, z)) for a in [k * math.tau / 8 for k in range(8)]
                  for z in (0.0, H + 0.1)], max_points=24)


# ============================================================================================
# Remains
# ============================================================================================

def _human_skull(name, s, seed):
    """A human skull facing -Y, the cranium at the origin; s = cranium radius (~0.09)."""
    cran = K.blob(name + "c", s, subdiv=3, scale=(0.82, 1.0, 0.88), rough=0.03, seed=seed)
    face = K.blob(name + "f", s * 0.62, subdiv=2, scale=(0.95, 0.7, 0.9), center=(0, -s * 0.62, -s * 0.38), seed=seed + 1)
    jaw = K.tube(name + "j", [(-s * 0.55, -s * 0.15, -s * 0.62), (-s * 0.42, -s * 0.78, -s * 0.9), (0, -s * 0.98, -s * 0.95),
                              (s * 0.42, -s * 0.78, -s * 0.9), (s * 0.55, -s * 0.15, -s * 0.62)], s * 0.13, segs=6, flat=(0.7, 1.0))
    o = K.merge_parts([cran, face, jaw], name)
    for sx in (-1, 1):
        K.dent(o, (sx * s * 0.34, -s * 0.95, -s * 0.18), s * 0.24, s * 0.16)
    K.dent(o, (0, -s * 1.05, -s * 0.45), s * 0.13, s * 0.08)
    K.noise_disp(o, s * 0.02, scale=20.0, seed=seed)
    return o


def nest_remains(ctx: K.Ctx) -> None:
    """Someone the nest took: a skeleton lying curled on its side, felt grown over and through it,
    a pack torn open beside it, what it held spilled."""
    rr = ctx.rnd("remains")
    # Spine: a curled chain of vertebrae along a curve (head at -X).
    spine = _bez(Vector((-0.38, 0.0, 0.07)), Vector((0.05, 0.2, 0.1)), Vector((0.38, 0.05, 0.08)), 14)
    for k, p in enumerate(spine):
        v = O.vertebra_obj(f"vert{k}", 0.045 - 0.012 * k / 13, ctx.seed + k)
        K.place(v, p, (90, 0, math.degrees(math.atan2((spine[min(k + 1, 13)] - spine[max(k - 1, 0)]).y,
                                                      (spine[min(k + 1, 13)] - spine[max(k - 1, 0)]).x)) + 90))
        ctx.add(v, "out_bone", uv="box", uv_scale=6.0, smooth=50, patches=0.6, edge=0.9)
    # Ribs: arcs off the upper spine, a few broken and fallen.
    for k in range(9):
        p = spine[1 + k]
        for side in (-1, 1):
            if rr.random() < 0.25:
                continue
            r = 0.13 - 0.004 * k
            rib = O.rib_obj(f"rib{k}{side}", r, ctx.seed + k * 3 + side, arc=170.0 if rr.random() > 0.3 else 90.0, side=side)
            K.place(rib, rot=(0, 0, 90 + rr.uniform(-8, 8)))
            K.place(rib, p + Vector((0, 0, 0.02)), (0, 25 * side, 0))
            ctx.add(rib, "out_bone", uv="box", uv_scale=6.0, smooth=50, patches=0.6, edge=0.9)
    sk = _human_skull("skull", 0.088, ctx.seed + 40)
    K.place(sk, rot=(-15, 80, 200))
    K.place(sk, Vector((-0.55, -0.02, 0.08)))
    ctx.add(sk, "out_bone", uv="box", uv_scale=4.0, smooth=55, patches=0.6, edge=0.9)
    # Pelvis and limbs: a drawn-up leg, an arm flung out, a lost femur.
    pel = K.blob("pelvis", 0.12, subdiv=2, scale=(0.7, 1.0, 0.55), center=(0.44, 0.08, 0.07), rough=0.25, seed=ctx.seed + 41)
    K.dent(pel, (0.44, 0.08, 0.14), 0.08, 0.05)
    ctx.add(pel, "out_bone", uv="box", uv_scale=4.0, smooth=50, patches=0.6, edge=0.9)
    for k, (a, b, r) in enumerate((((0.46, 0.15, 0.05), (0.62, -0.22, 0.04), 0.022), ((0.62, -0.22, 0.04), (0.3, -0.38, 0.03), 0.018),
                                    ((-0.25, -0.08, 0.05), (-0.42, -0.4, 0.03), 0.017), ((-0.42, -0.4, 0.03), (-0.2, -0.55, 0.025), 0.013),
                                    ((0.15, 0.48, 0.03), (0.52, 0.42, 0.04), 0.022))):
        O.add_bone(ctx, f"limb{k}", a, b, r, ctx.seed + 50 + k)
    # Felt: cushions grown over the bones, threads binding them down, caps up through the ribs.
    for k in range(6):
        c = spine[rr.randint(0, 13)] + Vector((rr.uniform(-0.15, 0.15), rr.uniform(-0.15, 0.15), -0.02))
        f = K.blob(f"felt{k}", rr.uniform(0.1, 0.2), subdiv=2, scale=(1.0, 1.0, 0.28), center=c, rough=0.3, seed=ctx.seed + 60 + k)
        _bloom(ctx, f, FELT, glow=0.4, thin=0.3, smooth=60)
    for k in range(8):
        a = rr.uniform(0, math.tau)
        p0 = Vector((rr.uniform(-0.5, 0.5), rr.uniform(-0.25, 0.3), 0.07))
        p2 = p0 + Vector((math.cos(a) * 0.45, math.sin(a) * 0.45, -0.1))
        pts = _gnarl(_bez(p0, p0.lerp(p2, 0.5) + Vector((0, 0, -0.03)), p2, 7), 0.05, ctx.seed + 90 + k)
        o = K.tube(f"thread{k}", pts, [0.009, 0.008, 0.007, 0.006, 0.005, 0.004, 0.003], segs=4)
        _bloom(ctx, o, ROOT, glow=1.0, thin=0.5, smooth=40, uv_scale=6.0)
    _caps(ctx, Vector((0, 0.05, 0.0)), 0.05, 0.4, 10, ctx.seed + 70, z_fn=lambda p: 0.05, size=0.45)
    # The torn pack: a slumped canvas body ripped open along the top, a strap gone.
    pk = Vector((0.55, 0.62, 0.0))
    body = K.box("pack", (0.34, 0.46, 0.17), center=(0, 0, 0.085), bevel=0.05, bevel_segs=3, cuts=(6, 8, 2))
    K.noise_disp(body, 0.03, scale=4.0, seed=ctx.seed + 80)
    K.map_verts(body, lambda co: Vector((co.x, co.y, co.z * (0.8 - 0.25 * max(0.0, co.y / 0.23)) * (1.0 - 0.4 * (co.x / 0.17) ** 2))))
    K.delete_faces(body, lambda c, n: n.z > 0.5 and abs(c.x + 0.25 * c.y) < 0.06 and -0.08 < c.y < 0.2)
    K.solidify(body, 0.008)
    K.place(body, pk, (0, 0, 35))
    ctx.add(body, "canvas_olive", uv_scale=1.0, smooth=50, patches=0.8, edge=0.6, low=0.6, low_h=0.1)
    strap = K.tube("strap", [pk + Vector((0.05, -0.15, 0.02)), pk + Vector((-0.12, -0.32, 0.01)), pk + Vector((-0.3, -0.36, 0.006))],
                   0.024, segs=4, flat=(1.0, 0.18))
    ctx.add(strap, "plastic_black", uv_scale=1.0, smooth=40, wear=0.6)
    rag = O.hide_obj("rag", 0.42, 0.3, ctx.seed + 81, nx=8, ny=6, ragged=0.2)
    K.place(rag, rot=(-90, 0, 0))
    K.crumple(rag, 0.03, scale=6.0, seed=ctx.seed + 82)
    K.place(rag, pk + Vector((-0.12, -0.36, 0.02)), (0, 0, 20))
    K.solidify(rag, 0.004)
    ctx.add(rag, "cloth_canvas", uv_scale=2.0, smooth=50, patches=0.8, edge=0.3)
    can = K.cyl("can", 0.037, 0.11, segs=12, center=(0, 0, 0))
    K.place(can, rot=(90, 0, rr.uniform(0, 180)))
    K.place(can, pk + Vector((0.22, -0.3, 0.037)))
    ctx.add(can, "can_green", uv="cyl", uv_axis=1, uv_scale=1.0, smooth=40, patches=0.7)
    # Felt creeping over the pack's foot.
    f = K.blob("packfelt", 0.2, subdiv=2, scale=(1.2, 0.8, 0.22), center=pk + Vector((-0.1, 0.18, 0.0)), rough=0.3, seed=ctx.seed + 83)
    _bloom(ctx, f, FELT, glow=0.4, thin=0.3, smooth=60)
    ctx.col_box((-0.7, -0.55, 0.0), (0.75, 0.9, 0.2))


BUILDERS = {
    "nest_root_mass": nest_root_mass,
    "nest_pod": nest_pod,
    "nest_shelf_cluster": nest_shelf_cluster,
    "nest_remains": nest_remains,
}


def build(params: dict, outputs: list[str]) -> None:
    K.run(params, outputs, BUILDERS)
