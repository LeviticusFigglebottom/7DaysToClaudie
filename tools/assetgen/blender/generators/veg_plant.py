"""Understory plants: fir saplings, huckleberry bushes, fireweed, yarrow, sword ferns, grass
clumps, shelf (bracket) fungus on a rotting wood chunk, deadfall stick piles and flat litter
(twigs, cones, dead sprays), moss mounds, redwood sorrel carpets.

build(params, outputs): outputs[0] = LOD0, optional outputs[1] = LOD1 (cheaper card set).
Origin = base centre on the ground. Foliage cards map into atlas rects passed in params["atlas"]
(textures/gen/vegetation.py LAYOUTS). Vertex colour: R = AO (darker low/inside), B = per-card
variation, A = wind weight (0 at the ground -> 1 at tips); 1.0 for static wood.

params.kind: sapling | huckleberry | willow | fireweed | yarrow | fern | grass | mushroom | deadfall | moss | carpet
"""
from __future__ import annotations

import math

from mathutils import Vector, noise

from lib import common, export, vcolor
from lib.veg_mesh import UP, MeshBuilder, card, horiz, remap_uvs, ribbon, rot_axis, tube
from lib.veg_tree import Branch, Card, Crown, Stem, Tree, assemble, lerp, smooth


def _aspect(atlas, region):
    u0, v0, u1, v1 = atlas[region]
    return (u1 - u0) / max(1e-6, v1 - v0)


def _dome_normal(center: Vector, bend: float, up_bias: float = 0.6):
    """Normals bent towards 'outward from the plant centre + up' (soft volumetric shading)."""
    def fn(p: Vector, fn_: Vector) -> Vector:
        o = Vector((p.x - center.x, p.y - center.y, 0.0))
        o = (o.normalized() if o.length > 1e-4 else Vector((0, 0, 0))) + Vector((0, 0, up_bias + 0.4))
        o.normalize()
        f = fn_ if fn_.dot(o) >= 0 else -fn_
        return (f * (1.0 - bend) + o * bend).normalized()
    return fn


# ---------------------------------------------------------------------------------------------
# Sword fern
# ---------------------------------------------------------------------------------------------

def build_fern(p, lod):
    rng = common.rng(p["seed"])
    atlas = p["atlas"]
    mb = MeshBuilder()
    n = int(p.get("fronds", 22)) if lod == 0 else int(p.get("fronds", 22) * 0.6)
    size = float(p.get("size", 0.9))
    segs = 6 if lod == 0 else 3
    regions = ("frond_a", "frond_b", "frond_c")
    center = Vector((0, 0, 0.0))
    nfn = _dome_normal(center, 0.55, 0.5)
    rng_l = common.rng(str(p["seed"]) + "f")
    fronds = []
    for i in range(int(p.get("fronds", 22))):
        a = i * 2.39996 + rng_l.uniform(-0.3, 0.3)
        inner = rng_l.random()
        elev = math.radians(lerp(46.0, 84.0, inner) + rng_l.uniform(-6, 6))
        L = size * rng_l.uniform(0.7, 1.05) * lerp(0.85, 1.05, inner)
        fronds.append((rng_l.random(), a, elev, L))
    fronds.sort(key=lambda f: f[0])
    for k, (prio, a, elev, L) in enumerate(fronds):
        if k >= n:
            break
        d0 = Vector((math.cos(a), math.sin(a), 0.0))
        spine = []
        sides = []
        widths = []
        reg = regions[k % 3]
        wmax = L * _aspect(atlas, reg) * 1.0
        for j in range(segs + 1):
            s = j / segs
            # arch: elevation drops along the frond, tip droops
            e = elev - s * (elev * 0.8 + 0.3) * 0.95
            if j == 0:
                pnt = Vector((0, 0, 0.02)) + d0 * 0.04
            else:
                prev = spine[-1]
                dirv = d0 * math.cos(e) + Vector((0, 0, math.sin(e)))
                pnt = prev + dirv * (L / segs)
            spine.append(pnt)
            side = Vector((-d0.y, d0.x, 0.0))
            # fronds roll so their face turns up as they arch out
            sides.append(rot_axis(side, d0, rng.uniform(-0.15, 0.15)))
            widths.append(wmax)

        def col(s, x, _L=L):
            return (lerp(0.45, 1.0, min(1.0, s * 1.4)), 0.0, (k * 0.618) % 1.0, lerp(0.15, 1.0, s))
        ribbon(mb, spine, sides, widths, atlas[reg], p["mat"], fold=0.18 if lod == 0 else 0.0, out=UP,
               col_fn=col, normal_fn=nfn)
    # a few young upright fronds in the centre
    if lod == 0:
        for i in range(3):
            a = rng.uniform(0, 2 * math.pi)
            d = Vector((math.cos(a) * 0.25, math.sin(a) * 0.25, 1.0)).normalized()
            ln = size * rng.uniform(0.35, 0.5)
            card(mb, Vector((0, 0, 0.02)), d, Vector((-math.sin(a), math.cos(a), 0)), ln,
                 ln * _aspect(atlas, "young") * 1.6, atlas["young"], p["mat"], segs=2, droop=0.05, out=d0,
                 col_fn=lambda s, x: (lerp(0.55, 1.0, s), 0.0, 0.5, lerp(0.2, 1.0, s)), normal_fn=nfn)
    return mb


# ---------------------------------------------------------------------------------------------
# Grass clump
# ---------------------------------------------------------------------------------------------

def build_grass(p, lod):
    rng = common.rng(p["seed"])
    atlas = p["atlas"]
    mb = MeshBuilder()
    h = float(p.get("height", 0.5))
    layout = p.get("cards", [["dense", 1.0], ["dense", 0.9], ["tall", 0.8]])
    n = len(layout)
    a0 = rng.uniform(0, math.pi)
    center = Vector((0, 0, 0))

    def nfn(pos, fn_):
        o = Vector((pos.x * 0.6, pos.y * 0.6, 1.0)).normalized()
        f = fn_ if fn_.dot(o) >= 0 else -fn_
        return (f * 0.35 + o * 0.65).normalized()

    # A patch is several tufts spread over a disc (one scatter cell then reads as continuous
    # grass instead of an isolated tuft on bare ground); a single tuft keeps tufts = 1.
    tufts = int(p.get("tufts", 1))
    spread = float(p.get("spread", 0.0))
    for t in range(tufts):
        if t == 0:
            c0, ts = Vector((0.0, 0.0, 0.0)), 1.0
        else:
            ang = t * 2.39996 + rng.uniform(-0.4, 0.4)
            rad = spread * math.sqrt((t - 0.5) / (tufts - 0.5)) * rng.uniform(0.8, 1.1)
            c0, ts = Vector((math.cos(ang) * rad, math.sin(ang) * rad, 0.0)), rng.uniform(0.65, 1.0)
        ta = rng.uniform(0, math.pi)
        # LOD1 (past ~40 m) keeps every other tuft and its two biggest cards: the patch keeps its
        # footprint and silhouette at a quarter of the triangles. The draws above stay in sequence.
        if lod > 0 and t % 2 == 1:
            continue
        for i, (reg, sc) in enumerate(layout):
            if lod > 0 and i >= 2:
                continue
            a = (a0 if t == 0 else ta) + math.pi * i / (2 if lod > 0 else n) + rng.uniform(-0.2, 0.2)
            side = Vector((math.cos(a), math.sin(a), 0.0))
            tilt = Vector((-side.y, side.x, 0.0)) * rng.uniform(-0.25, 0.25)
            ch = h * sc * ts * rng.uniform(0.85, 1.1)
            cw = ch * _aspect(atlas, reg)
            base = c0 + Vector((rng.uniform(-0.05, 0.05), rng.uniform(-0.05, 0.05), -0.02))
            d = (UP + tilt).normalized()
            card(mb, base, d, side, ch, cw, atlas[reg], p["mat"], segs=2 if lod == 0 else 1, droop=0.06,
                 out=Vector((-side.y, side.x, 0.3)),
                 col_fn=lambda s, x: (lerp(0.55, 1.0, s), 0.0, rng.random(), lerp(0.0, 1.0, s)), normal_fn=nfn)
    return mb


# ---------------------------------------------------------------------------------------------
# Fireweed and yarrow (crossed stalk cards)
# ---------------------------------------------------------------------------------------------

def _crossed(mb, base, height, width, rect, mat, rng, lean, n=2, nfn=None):
    a0 = rng.uniform(0, math.pi)
    d = (UP + lean).normalized()
    for i in range(n):
        a = a0 + math.pi * i / n
        side = Vector((math.cos(a), math.sin(a), 0.0))
        card(mb, base, d, side, height, width, rect, mat, segs=2, droop=rng.uniform(0.0, 0.05),
             out=Vector((-side.y, side.x, 0.2)),
             col_fn=lambda s, x: (lerp(0.5, 1.0, s), 0.0, 0.5, s), normal_fn=nfn)


def build_fireweed(p, lod):
    rng = common.rng(p["seed"])
    atlas = p["atlas"]
    mb = MeshBuilder()
    nfn = _dome_normal(Vector((0, 0, 0)), 0.4)
    regs = ("fireweed_a", "fireweed_b", "fireweed_c")
    for i in range(int(p.get("stalks", 6))):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(0.05, 0.42) ** 0.8
        base = Vector((math.cos(a) * r, math.sin(a) * r, -0.02))
        hh = float(p.get("height", 1.0)) * rng.uniform(0.55, 1.12)
        reg = regs[i % 3]
        lean = Vector((math.cos(a), math.sin(a), 0.0)) * rng.uniform(0.02, 0.12)
        _crossed(mb, base, hh, hh * _aspect(atlas, reg) * 1.15, atlas[reg], p["mat"], rng, lean, n=3, nfn=nfn)
    for i in range(4):
        a = i * 1.57 + rng.uniform(-0.3, 0.3)
        d = Vector((math.cos(a) * 0.8, math.sin(a) * 0.8, 0.6)).normalized()
        ln = 0.35 * rng.uniform(0.8, 1.1)
        card(mb, Vector((0, 0, 0.0)), d, Vector((-math.sin(a), math.cos(a), 0)), ln, ln * _aspect(atlas, "fireweed_leaf"),
             atlas["fireweed_leaf"], p["mat"], segs=2, droop=0.1, out=UP,
             col_fn=lambda s, x: (lerp(0.5, 0.9, s), 0.0, 0.3, s * 0.8), normal_fn=nfn)
    return mb


def build_yarrow(p, lod):
    rng = common.rng(p["seed"])
    atlas = p["atlas"]
    mb = MeshBuilder()
    nfn = _dome_normal(Vector((0, 0, 0)), 0.4)
    for i in range(int(p.get("stems", 5))):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(0.0, 0.15)
        base = Vector((math.cos(a) * r, math.sin(a) * r, -0.02))
        hh = float(p.get("height", 0.5)) * rng.uniform(0.75, 1.1)
        reg = ("yarrow_a", "yarrow_b")[i % 2]
        lean = Vector((math.cos(a), math.sin(a), 0.0)) * rng.uniform(0.02, 0.12)
        _crossed(mb, base, hh, hh * _aspect(atlas, reg), atlas[reg], p["mat"], rng, lean, n=2, nfn=nfn)
        # flat flower head seen from above (the side cards show it edge-on)
        top = base + (UP + lean).normalized() * (hh * 0.86)
        hd = hh * 0.36
        card(mb, top - Vector((0, hd * 0.5, 0)), Vector((0, 1, 0)), Vector((1, 0, 0)), hd, hd,
             atlas[("yarrow_top", "yarrow_top_b")[i % 2]], p["mat"], segs=1, droop=0.0, out=UP,
             col_fn=lambda s, x: (1.0, 0.0, 0.7, 1.0), normal_fn=lambda q, fn_: Vector((0, 0, 1)))
    for i in range(5):
        a = i * 1.2566 + rng.uniform(-0.2, 0.2)
        d = Vector((math.cos(a), math.sin(a), 0.25)).normalized()
        ln = float(p.get("height", 0.5)) * 0.45
        card(mb, Vector((0, 0, 0.0)), d, Vector((-math.sin(a), math.cos(a), 0)), ln, ln * _aspect(atlas, "yarrow_leaves"),
             atlas["yarrow_leaves"], p["mat"], segs=2, droop=0.08, out=UP,
             col_fn=lambda s, x: (lerp(0.5, 0.85, s), 0.0, 0.2, s * 0.7), normal_fn=nfn)
    return mb


# ---------------------------------------------------------------------------------------------
# Huckleberry bush
# ---------------------------------------------------------------------------------------------

def build_huckleberry(p, lod):
    rng = common.rng(p["seed"])
    atlas = p["atlas"]
    mat = p["mat"]
    mb = MeshBuilder()
    H = float(p.get("height", 1.0))
    center = Vector((0, 0, H * 0.45))
    # Leaf-card regions and the stem strip in the atlas (willow shrubs reuse this builder).
    regs = tuple(p.get("regs", ("huckle_a", "huckle_b", "huckle_c", "huckle_d")))
    stem_r = float(p.get("stem_scale", 1.0))

    def nfn(pos, fn_):
        o = (pos - center)
        o = Vector((o.x, o.y, o.z * 0.6 + 0.3)).normalized()
        f = fn_ if fn_.dot(o) >= 0 else -fn_
        return (f * 0.45 + o * 0.55).normalized()

    def ao_at(pos):
        o = pos - center
        r = math.sqrt(o.x * o.x + o.y * o.y) / (H * 0.6)
        return max(0.35, min(1.0, 0.4 + 0.45 * r + 0.35 * (pos.z / H)))

    rng_c = common.rng(str(p["seed"]) + "c")
    stems = []
    lean_lo, lean_hi = p.get("lean", (0.15, 0.6))
    card_lo, card_hi = p.get("card_len", (0.38, 0.52))
    for i in range(int(p.get("stems", 6))):
        a = i * 2.39996 + rng.uniform(-0.3, 0.3)
        lean = rng.uniform(lean_lo, lean_hi)
        L = H * rng.uniform(0.75, 1.05)
        pts = [Vector((math.cos(a) * 0.03, math.sin(a) * 0.03, -0.03))]
        d = Vector((math.cos(a) * math.sin(lean), math.sin(a) * math.sin(lean), math.cos(lean)))
        for j in range(1, 5):
            d = (d + Vector((rng.uniform(-0.15, 0.15), rng.uniform(-0.15, 0.15), -0.05 * j))).normalized()
            pts.append(pts[-1] + d * (L / 4))
        stems.append(pts)
        if lod == 0:
            f0 = len(mb.faces)
            tube(mb, pts, [r * stem_r for r in (0.012, 0.01, 0.008, 0.006, 0.004)], 4, p.get("stem_mat", mat), u_repeats=1,
                 tip=False, col_fn=lambda ii, s, aa, pp: (ao_at(pp) * 0.8, 0.0, 0.5, s * 0.6))
            remap_uvs(mb, f0, len(mb.faces), atlas["stem"])
    nclusters = int(p.get("clusters", 26)) if lod == 0 else int(p.get("clusters", 26) * 0.5)
    for k in range(nclusters):
        pts = stems[k % len(stems)]
        s = rng_c.uniform(0.35, 1.0)
        i = min(int(s * (len(pts) - 1)), len(pts) - 2)
        f = s * (len(pts) - 1) - i
        pos = pts[i].lerp(pts[i + 1], f)
        t = (pts[i + 1] - pts[i]).normalized()
        d = rot_axis(t, UP, rng_c.uniform(-1.4, 1.4))
        d.z += rng_c.uniform(-0.3, 0.4)
        d.normalize()
        side = rot_axis(UP.cross(horiz(d)), d, rng_c.gauss(0.0, 0.6))
        ln = H * rng_c.uniform(card_lo, card_hi) * (1.25 if lod else 1.0)
        reg = regs[k % len(regs)]
        aval = ao_at(pos)
        card(mb, pos, d, side, ln, ln * _aspect(atlas, reg), atlas[reg], mat, segs=2 if lod == 0 else 1,
             droop=rng_c.uniform(0.05, 0.2), out=(pos - center).normalized(),
             col_fn=lambda s_, x, av=aval: (av, 0.0, rng_c.random(), lerp(0.4, 1.0, s_)), normal_fn=nfn)
    return mb


def _along(pts: list[Vector], s: float) -> tuple[Vector, Vector]:
    """Point and tangent at fraction s (by segment count) of a polyline."""
    i = min(int(s * (len(pts) - 1)), len(pts) - 2)
    f = s * (len(pts) - 1) - i
    return pts[i].lerp(pts[i + 1], f), (pts[i + 1] - pts[i]).normalized()


def build_willow(p, lod):
    """Pacific willow shrub: a vase of ascending stems that fork in their upper half, and twig cards
    packed toward the stem tips, sweeping up and out from the shrub's axis with drooping ends.
    It reads as one rounded mass of narrow leaves. (Cards spread at random angles along leaning
    stems, as the huckleberry builder does, read as fern fronds at willow size.)"""
    rng = common.rng(p["seed"])
    rng_c = common.rng(str(p["seed"]) + "c")
    atlas = p["atlas"]
    mat = p["mat"]
    stem_mat = p.get("stem_mat", mat)
    regs = tuple(p.get("regs", ("willow_a", "willow_b")))
    mb = MeshBuilder()
    H = float(p.get("height", 2.5))
    center = Vector((0, 0, H * 0.62))
    stem_r = float(p.get("stem_scale", 1.0))

    def nfn(pos, fn_):
        o = pos - center
        o = Vector((o.x, o.y, o.z * 0.7 + 0.25)).normalized()
        f = fn_ if fn_.dot(o) >= 0 else -fn_
        return (f * 0.4 + o * 0.6).normalized()

    def ao_at(pos):
        o = pos - center
        r = math.sqrt(o.x * o.x + o.y * o.y) / (H * 0.45)
        return max(0.3, min(1.0, 0.3 + 0.45 * r + 0.45 * (pos.z / H)))

    lean_lo, lean_hi = p.get("lean", (0.1, 0.35))
    branches = []
    for i in range(int(p.get("stems", 9))):
        a = i * 2.39996 + rng.uniform(-0.4, 0.4)
        lean = rng.uniform(lean_lo, lean_hi)
        L = H * rng.uniform(0.72, 1.0)
        out = Vector((math.cos(a), math.sin(a), 0.0))
        d = Vector((out.x * math.sin(lean), out.y * math.sin(lean), math.cos(lean)))
        pts = [out * 0.05 + Vector((0.0, 0.0, -0.04))]
        for j in range(1, 6):
            # Stays ascending: willow stems bow outward a little, they don't arch over.
            d = (d + Vector((rng.uniform(-0.09, 0.09), rng.uniform(-0.09, 0.09), 0.015)) + out * 0.03).normalized()
            pts.append(pts[-1] + d * (L / 5))
        branches.append((pts, 1.0))
        for _ in range(rng.randint(1, 2)):
            k0 = rng.randint(2, 3)
            side = rot_axis(out, UP, rng.uniform(-0.9, 0.9))
            fd = (d + side * rng.uniform(0.45, 0.8)).normalized()
            fl = L * rng.uniform(0.35, 0.55)
            fork = [pts[k0]]
            for j in range(1, 4):
                fd = (fd + Vector((rng.uniform(-0.1, 0.1), rng.uniform(-0.1, 0.1), 0.06))).normalized()
                fork.append(fork[-1] + fd * (fl / 3))
            branches.append((fork, 0.55))
    # Basal shoots: short leafy whips around the stool fill the lower crown (willows resprout
    # densely from the base; without them the shrub is a vase of bare sticks).
    for i in range(int(p.get("shoots", 8))):
        a = rng.uniform(0.0, math.tau)
        lean = rng.uniform(0.35, 0.75)
        L = H * rng.uniform(0.28, 0.5)
        out = Vector((math.cos(a), math.sin(a), 0.0))
        d = Vector((out.x * math.sin(lean), out.y * math.sin(lean), math.cos(lean)))
        pts = [out * 0.07 + Vector((0.0, 0.0, -0.03))]
        for j in range(1, 4):
            d = (d + Vector((rng.uniform(-0.12, 0.12), rng.uniform(-0.12, 0.12), 0.05))).normalized()
            pts.append(pts[-1] + d * (L / 3))
        branches.append((pts, 0.4))
    if lod == 0:
        for pl, w in branches:
            f0 = len(mb.faces)
            r0 = 0.014 * stem_r * w
            tube(mb, pl, [r0 * (1.0 - 0.75 * k / (len(pl) - 1)) for k in range(len(pl))], 4, stem_mat,
                 u_repeats=1, tip=False, col_fn=lambda ii, s, aa, pp: (ao_at(pp) * 0.8, 0.0, 0.5, s * 0.6))
            remap_uvs(mb, f0, len(mb.faces), atlas["stem"])
    card_lo, card_hi = p.get("card_len", (0.18, 0.28))
    n = int(p.get("clusters", 120))
    if lod:
        n = int(n * 0.45)
    for k in range(n):
        pl, w = branches[k % len(branches)]
        # Leafy from low on the stems, denser toward the tips.
        s = 1.0 - (rng_c.random() ** 1.35) * (0.85 if w == 1.0 else 0.8)
        pos, t = _along(pl, s)
        o = Vector((pos.x, pos.y, 0.0))
        o = o.normalized() if o.length > 1e-3 else horiz(t)
        d = (o * rng_c.uniform(0.3, 0.75) + t * 0.35 + UP * rng_c.uniform(0.55, 0.95)
             + Vector((rng_c.uniform(-0.25, 0.25), rng_c.uniform(-0.25, 0.25), 0.0))).normalized()
        side = rot_axis(horiz(d).cross(UP), d, rng_c.gauss(0.0, 0.7))
        ln = H * rng_c.uniform(card_lo, card_hi) * (1.3 if lod else 1.0)
        reg = regs[k % len(regs)]
        aval = ao_at(pos)
        card(mb, pos - d * ln * 0.1, d, side, ln, ln * _aspect(atlas, reg), atlas[reg], mat, segs=2 if lod == 0 else 1,
             droop=rng_c.uniform(0.12, 0.32), out=(pos - center).normalized(),
             col_fn=lambda s_, x, av=aval: (av, 0.0, rng_c.random(), lerp(0.45, 1.0, s_)), normal_fn=nfn)
    return mb


# ---------------------------------------------------------------------------------------------
# Fir sapling (re-uses the tree machinery at small scale)
# ---------------------------------------------------------------------------------------------

def build_sapling(p, lod):
    """Young fir: thin leader with dense whorls; every branch carries a tilted whole-branch card,
    a crossed one and 2-3 drooping sprays, plus vertical fill cards through the cone so the
    sapling reads as a full little conifer from every side (not stacked plates)."""
    rng = common.rng(p["seed"])
    atlas = p["atlas"]
    H = float(p.get("height", 2.0))
    bark, fol = p["bark"], p["mat"]
    zs = [-0.05, 0.1, 0.35, 0.7]
    z = 1.0
    while z < H - 0.25:
        zs.append(z)
        z += 0.45
    zs.append(H - 0.1)
    pts = [Vector((math.sin(z * 1.3) * 0.015, math.cos(z * 0.9) * 0.015, z)) for z in zs]
    r0 = 0.012 + 0.012 * H
    radii = [max(0.004, r0 * (1.0 - z / H) ** 0.9) for z in zs]
    st = Stem(pts=pts, radii=radii, mat=bark, lobes=[], u_repeats=1, noise_amp=0.0, sides=(6, 4, 3),
              keep_all_below=0.5)
    tree = Tree(name=p["name"], stems=[st], foliage_mat=fol, atlas=atlas, height=H, crown_base=0.2,
                seed=int(p["seed"]), ao_range=(0.42, 1.0), trunk_ao_crown=0.8, normal_bend=(0.6, 0.7, 0.8),
                budgets=(1400, 500, 200), moss_height=0.0)

    def R(z):
        t = max(0.0, min(1.0, (H - z) / max(1e-3, H - 0.1)))
        return H * 0.3 * t ** 0.9 * (0.8 + 0.2 * smooth(0.0, 0.25, 1.0 - t)) + 0.06

    tree.crown = Crown(0.05, H, lambda z: (0.0, 0.0, R(z)), up_bias=0.45)
    z = rng.uniform(0.12, 0.22)
    k = 0
    while z < H - 0.22:
        hz = z / H
        n = rng.choice((4, 4, 5))
        for i in range(n):
            phi = k * 2.4 + 2 * math.pi * i / n + rng.uniform(-0.3, 0.3)
            reach = R(z) * rng.uniform(0.75, 1.08)
            elev = lerp(-0.05, 0.6, hz) + rng.uniform(-0.12, 0.12)
            L = reach / max(0.6, math.cos(elev * 0.7))
            start = Vector((0, 0, z))
            d = Vector((math.cos(phi) * math.cos(elev), math.sin(phi) * math.cos(elev), math.sin(elev)))
            end = start + d * L + Vector((0, 0, -lerp(0.18, 0.06, hz) * L))
            br = Branch(pts=[start, end], radii=[0.005 + 0.005 * L, 0.002], mat=bark, wind0=0.2, wind1=0.6,
                        tip=False, sides=(3 if hz < 0.5 else 0, 0, 0), min_len_lod=(0.3, 99, 99))
            tree.branches.append(br)
            dd = (end - start).normalized()
            base_side = UP.cross(horiz(dd))
            roll = rng.uniform(-0.6, 0.6)
            ln = max(0.25, min(0.9, L * 1.08))
            tree.cards[0].append(Card(base=start, direction=dd, side=rot_axis(base_side, dd, roll), length=ln,
                                      width=ln * 0.92, region="branch", droop=0.12, segs=1, wind0=0.3, wind1=1.0,
                                      prio=2.0, shade=0.85))
            tree.cards[0].append(Card(base=start, direction=dd, side=rot_axis(base_side, dd, roll + 1.3), length=ln * 0.85,
                                      width=ln * 0.7, region="branch", droop=0.1, segs=1, wind0=0.3, wind1=1.0,
                                      prio=1.6, shade=0.8))
            for sp in (0.35, 0.7, 1.0)[: (3 if L > 0.45 else 2)]:
                pnt = br.at(min(sp, 0.96))[0]
                d2 = rot_axis(dd, UP, rng.uniform(-0.9, 0.9) * (1.0 - 0.6 * sp))
                d2.z -= rng.uniform(0.1, 0.45)
                d2.normalize()
                reg = ("spray_b", "spray_c")[rng.randrange(2)]
                ln2 = ln * rng.uniform(0.45, 0.65)
                tree.cards[0].append(Card(base=pnt, direction=d2, side=rot_axis(UP.cross(horiz(d2)), d2, rng.gauss(0, 0.5)),
                                          length=ln2, width=ln2 * _aspect(atlas, reg), region=reg, droop=0.15, segs=2,
                                          wind0=0.4, wind1=1.0, prio=0.5 + sp * 0.5 + rng.random() * 0.3))
            tree.cards[1].append(Card(base=start, direction=dd, side=rot_axis(base_side, dd, roll), length=ln * 1.1,
                                      width=ln * 1.0, region="branch", droop=0.1, segs=1, wind0=0.3, wind1=1.0, prio=1.0))
        z += rng.uniform(0.17, 0.25)
        k += 1
    # vertical fill cards through the cone (crossed), every ~0.5 m of height
    zf = 0.15
    j = 0
    while zf < H - 0.4:
        span = min(0.75, H - zf - 0.2)
        rr = R(zf + span * 0.3)
        for a in (j * 0.7, j * 0.7 + math.pi / 2):
            c = Card(base=Vector((0, 0, zf)), direction=UP, side=Vector((math.cos(a), math.sin(a), 0.0)), length=span,
                     width=rr * 1.7, region="branch", droop=0.0, segs=1, wind0=0.3, wind1=0.9, prio=1.8, shade=0.75)
            tree.cards[0].append(c)
            tree.cards[1].append(Card(**{**c.__dict__, "prio": 1.2}))
        zf += 0.5
        j += 1
    for i in range(3):
        a = i * 2.1
        d = Vector((math.cos(a) * 0.35, math.sin(a) * 0.35, 1.0)).normalized()
        c = Card(base=Vector((0, 0, H - 0.4)), direction=d, side=Vector((-math.sin(a), math.cos(a), 0)), length=0.42,
                 width=0.42 * _aspect(atlas, "spray_b"), region="spray_b", droop=0.0, segs=1, wind0=0.5, wind1=1.0, prio=3.0)
        tree.cards[0].append(c)
        tree.cards[1].append(c)
    return assemble(tree, lod, rng)


# ---------------------------------------------------------------------------------------------
# Shelf fungus on a rotting wood chunk
# ---------------------------------------------------------------------------------------------

def _bracket(mb, mat, attach: Vector, outward: Vector, R: float, thick: float, rng):
    """Hoof-like bracket (red-belted conk): half-disc shelf growing out of `attach` along
    `outward` (horizontal), thick at the wood, rounded margin, flat pore surface below."""
    m = mb.mat(mat)
    o = horiz(outward)
    sd = Vector((-o.y, o.x, 0.0))
    nphi, nr = 9, 4
    phis = [(-1.0 + 2.0 * i / (nphi - 1)) * math.radians(80) for i in range(nphi)]
    top, bot = [], []
    for i, ph in enumerate(phis):
        rowt, rowb = [], []
        dirv = o * math.cos(ph) + sd * math.sin(ph)
        rmax = R * (0.75 + 0.25 * math.cos(ph)) * rng.uniform(0.92, 1.05)
        for j in range(nr + 1):
            q = j / nr
            rr = rmax * q
            ht = thick * (1.0 - q ** 1.6) * 0.7 + thick * 0.18
            hb = thick * 0.25 * (1.0 - q)
            pt = attach + dirv * rr + Vector((0, 0, ht))
            pb = attach + dirv * rr - Vector((0, 0, hb))
            rowt.append(mb.v(pt, (1.0, 0.0, 0.0, 1.0)))
            rowb.append(mb.v(pb, (0.6, 0.0, 0.0, 1.0)))
        top.append(rowt)
        bot.append(rowb)
    for i in range(nphi - 1):
        ua, ub = 2.0 * i / (nphi - 1), 2.0 * (i + 1) / (nphi - 1)
        for j in range(nr):
            va, vb = 0.5 + 0.5 * j / nr, 0.5 + 0.5 * (j + 1) / nr
            mb.f((top[i][j], top[i][j + 1], top[i + 1][j + 1], top[i + 1][j]),
                 ((ua, va), (ua, vb), (ub, vb), (ub, va)), m)
            wa, wb = 0.48 * j / nr, 0.48 * (j + 1) / nr
            mb.f((bot[i][j], bot[i + 1][j], bot[i + 1][j + 1], bot[i][j + 1]),
                 ((ua, wa), (ub, wa), (ub, wb), (ua, wb)), m)
        # rounded margin between top and bottom rims
        mb.f((top[i][nr], bot[i][nr], bot[i + 1][nr], top[i + 1][nr]), ((ua, 0.995), (ua, 0.48), (ub, 0.48), (ub, 0.995)), m)


def build_mushroom(p, lod):
    rng = common.rng(p["seed"])
    mb = MeshBuilder()
    L = float(p.get("length", 0.5))
    r = float(p.get("radius", 0.1))
    noise.seed_set(int(p["seed"]) % 100000)
    pts = [Vector((-L / 2 + L * i / 4, 0.0, r * 0.75)) for i in range(5)]
    radii = [r * (1.0 + 0.08 * math.sin(i * 1.7)) for i in range(5)]

    def rfn(i, s, a):
        return 1.0 + noise.noise(Vector((math.cos(a) * 2.0, math.sin(a) * 2.0, s * 4.0))) * 0.08

    rings, _ = tube(mb, pts, radii, 10, p["wood"], u_repeats=1, radius_fn=rfn, tip=False, cap_end=True, cap_start=True,
                    end_mat=p["end"], up_hint=Vector((0, 0, 1)),
                    end_cap_uv=lambda a, q: (0.5 + 0.497 * q * math.cos(a), 0.5 + 0.497 * q * math.sin(a)))
    nb = int(p.get("brackets", 4))
    for k in range(nb):
        x = -L * 0.35 + L * 0.7 * (k + rng.uniform(0.0, 0.5)) / nb
        a = rng.uniform(-0.6, 1.6) if k % 2 == 0 else rng.uniform(1.6, 3.7)
        ny, nz = math.cos(a), math.sin(a)
        attach = Vector((x, ny * r * 0.95, r * 0.75 + nz * r * 0.95))
        outward = Vector((rng.uniform(-0.2, 0.2), ny if abs(ny) > 0.2 else (0.4 if ny >= 0 else -0.4), 0.0))
        R = rng.uniform(0.06, 0.11) * float(p.get("bracket_scale", 1.0))
        _bracket(mb, p["mat"], attach, outward, R, R * 0.45, rng)
    obj = mb.build(p["name"] + ("" if lod == 0 else "_lod1"))
    vcolor.bake_ao([obj], samples=16, distance=0.25)
    vcolor.fill_channel(obj, 1, 0.0)
    vcolor.set_channel(obj, 2, lambda co, n, li: max(0.0, n.z) * 0.6)
    vcolor.fill_channel(obj, 3, 1.0)
    return obj


# ---------------------------------------------------------------------------------------------
# Herb carpet (redwood sorrel)
# ---------------------------------------------------------------------------------------------

def build_carpet(p, lod):
    """Low herb carpet: a few near-horizontal top-view cards just above the soil (what a player
    looking down sees) plus crossed side cards of the same leaves on their stalks (what reads at
    eye height and at grazing angles)."""
    rng = common.rng(p["seed"])
    atlas = p["atlas"]
    mb = MeshBuilder()
    size = float(p.get("size", 0.9))
    h = float(p.get("height", 0.12))
    m = p["mat"]
    up_n = lambda q, fn_: Vector((0.0, 0.0, 1.0))
    for k in range(int(p.get("tops", 3))):
        c = Vector((rng.uniform(-0.18, 0.18) * size, rng.uniform(-0.18, 0.18) * size, h * rng.uniform(0.6, 1.0)))
        a = rng.uniform(0.0, 2.0 * math.pi)
        d = Vector((math.cos(a), math.sin(a), rng.uniform(-0.1, 0.1))).normalized()
        side = Vector((-math.sin(a), math.cos(a), rng.uniform(-0.1, 0.1)))
        sz = size * rng.uniform(0.7, 1.0)
        card(mb, c - d * (sz * 0.5), d, side, sz, sz, atlas["sorrel_top"], m, segs=1, droop=0.0, out=UP,
             col_fn=lambda q, x: (0.9, 0.0, rng.random(), 0.25), normal_fn=up_n)
    nf = int(p.get("sides", 3))
    a0 = rng.uniform(0.0, math.pi)
    nfn = _dome_normal(Vector((0, 0, 0)), 0.6, 0.6)
    for k in range(nf):
        a = a0 + math.pi * k / nf
        side = Vector((math.cos(a), math.sin(a), 0.0))
        w = size * rng.uniform(0.6, 0.85)
        ht = h * 1.6 * rng.uniform(0.85, 1.1)
        card(mb, Vector((0.0, 0.0, -0.01)), UP, side, ht, w, atlas["sorrel_side"], m, segs=1, droop=0.0,
             out=Vector((-side.y, side.x, 0.2)), col_fn=lambda q, x: (lerp(0.6, 0.95, q), 0.0, rng.random(), q * 0.5),
             normal_fn=nfn)
    return mb


# ---------------------------------------------------------------------------------------------
# Moss mound
# ---------------------------------------------------------------------------------------------

def build_moss(p, lod):
    """Moss mound: a low, lumpy cushion of moss over a buried stone or a rotted stump. The outline
    is irregular and oval, a few humps sit on a soft dome, and the rim runs into a skirt below the
    ground so the mound grows out of the floor (and still meets it on uneven terrain) instead of
    sitting on it like a lid. UVs are planar in metres (the moss texture tiles)."""
    rng = common.rng(p["seed"])
    noise.seed_set(int(p["seed"]) % 100000)
    mb = MeshBuilder()
    m = mb.mat(p["mat"])
    R = float(p.get("radius", 0.7))
    H = float(p.get("height", 0.14))
    nr = 7 if lod == 0 else 3
    ns = 44 if lod == 0 else 16
    ox, oy = rng.uniform(0.0, 40.0), rng.uniform(0.0, 40.0)
    sy = rng.uniform(0.62, 0.85)
    # humps spread around the middle (not stacked on it, which makes a cone)
    humps = []
    nh = int(p.get("humps", 3))
    a0 = rng.uniform(0.0, 2 * math.pi)
    for k in range(nh):
        a = a0 + 2 * math.pi * k / nh + rng.uniform(-0.5, 0.5)
        d = rng.uniform(0.25, 0.55) * R
        c = Vector((math.cos(a) * d, math.sin(a) * d * sy, 0.0))
        humps.append((c, rng.uniform(0.22, 0.42) * R, rng.uniform(0.4, 1.0)))

    def rim(a):
        # Lobed and ragged, not a smooth oval: moss spreads in tongues over the litter, and a clean
        # outline reads as a rug laid on the floor.
        q = Vector((math.cos(a) * 1.2 + ox, math.sin(a) * 1.2 + oy, 0.7))
        return R * (1.0 + 0.22 * noise.noise(q) + 0.13 * noise.noise(q * 3.3) + 0.07 * noise.noise(q * 7.9))

    def height(x, y, s):
        dome = H * max(0.0, 1.0 - s ** 2.6) ** 0.7
        hump = sum(k * H * 0.45 * math.exp(-((x - c.x) ** 2 + (y - c.y) ** 2) / (rr * rr)) for c, rr, k in humps)
        lump = noise.noise(Vector((x * 6.0 + ox, y * 6.0 + oy, 0.3))) * H * 0.22
        return dome + (hump + lump) * (1.0 - s ** 3)

    def col(s, x, y):
        # The thin edge sinks into the floor's shade: occluded by the litter it creeps over.
        v = 0.5 + 0.5 * noise.noise(Vector((x * 2.0 + oy, y * 2.0 + ox, 1.7)))
        return (lerp(1.0, 0.5, smooth(0.45, 1.0, s)), 0.0, v, 1.0)

    rows = []
    for i in range(nr + 1):
        s = i / nr
        row = []
        for j in range(ns):
            a = 2 * math.pi * j / ns
            r = rim(a) * s
            x, y = math.cos(a) * r, math.sin(a) * r * sy
            row.append((mb.v((x, y, height(x, y, s) - 0.02 * s), col(s, x, y)), x, y))
        rows.append(row)
    # Skirt: steeply down into the ground just outside the rim.
    skirt = []
    for j in range(ns):
        a = 2 * math.pi * j / ns
        r = rim(a) * 1.07
        x, y = math.cos(a) * r, math.sin(a) * r * sy
        skirt.append((mb.v((x, y, -0.14), (0.45, 0.0, 0.5, 1.0)), x, y))
    rows.append(skirt)
    # Rows 0 is the centre (all at radius 0): a triangle fan, then quads, wound counter-clockwise
    # seen from above so the faces point up.
    c0 = rows[0][0]
    for j in range(ns):
        j2 = (j + 1) % ns
        b, b2 = rows[1][j], rows[1][j2]
        mb.f((c0[0], b[0], b2[0]), ((c0[1], c0[2]), (b[1], b[2]), (b2[1], b2[2])), m)
    for i in range(1, len(rows) - 1):
        for j in range(ns):
            j2 = (j + 1) % ns
            a0, a1, b0, b1 = rows[i][j], rows[i][j2], rows[i + 1][j], rows[i + 1][j2]
            mb.f((a0[0], b0[0], b1[0], a1[0]), ((a0[1], a0[2]), (b0[1], b0[2]), (b1[1], b1[2]), (a1[1], a1[2])), m)
    return mb


# ---------------------------------------------------------------------------------------------
# Deadfall: pile of dead sticks
# ---------------------------------------------------------------------------------------------

def _cone(mb, mat, base, d, length, r, rng, sides):
    """A closed conifer cone lying on the ground: a short spindle, widest a third of the way
    along, with a wobble in the radius that hints at the scales."""
    n = 5
    pts = [base + d * (length * k / (n - 1)) for k in range(n)]
    prof = (0.45, 0.95, 1.0, 0.75, 0.3)
    ph = rng.uniform(0.0, 6.28)
    tube(mb, pts, [r * k for k in prof], sides, mat, u_repeats=1, tip=True, cap_start=True,
         radius_fn=lambda i, s, a: 1.0 + 0.14 * math.sin(a * 3.0 + i * 2.3 + ph), up_hint=UP)

def build_deadfall(p, lod):
    rng = common.rng(p["seed"])
    mb = MeshBuilder()
    noise.seed_set(int(p["seed"]) % 100000)
    spread = float(p.get("spread", 0.7))
    pile_h = float(p.get("pile_h", 0.35))
    l0, l1 = p.get("stick_len", (0.3, 1.1))
    ra, rb = p.get("stick_r", (0.01, 0.032))
    sides = int(p.get("sides", 5)) if lod == 0 else 3
    caps = bool(p.get("caps", True))
    sticks = []
    for i in range(int(p.get("sticks", 16))):
        L = rng.uniform(l0, l1) * (1.4 if rng.random() < 0.15 else 1.0)
        r0 = rng.uniform(ra, rb) * (0.7 + 0.4 * L)
        yaw = rng.uniform(0, math.pi)
        c = Vector((rng.gauss(0, spread * 0.35), rng.gauss(0, spread * 0.35), 0.0))
        # higher sticks lean on the pile (a flat scatter of litter barely tilts)
        layer = rng.random() ** 1.6
        z0 = r0 + layer * pile_h
        tilt = rng.uniform(-0.35, 0.35) * layer * min(1.0, pile_h / 0.3)
        d = Vector((math.cos(yaw) * math.cos(tilt), math.sin(yaw) * math.cos(tilt), math.sin(tilt)))
        a = c - d * L * 0.5 + Vector((0, 0, z0))
        b = c + d * L * 0.5 + Vector((0, 0, z0))
        if a.z < r0:
            a.z = r0
        if b.z < r0:
            b.z = r0
        perp = Vector((-d.y, d.x, 0.0))
        bend = [rng.uniform(-1, 1) * L * 0.06 for _ in range(3)]
        m1 = a.lerp(b, 0.33) + perp * bend[0] + Vector((0, 0, rng.uniform(-0.02, 0.02)))
        m2 = a.lerp(b, 0.66) + perp * bend[1] + Vector((0, 0, rng.uniform(-0.02, 0.02)))
        sticks.append((a, m1, m2, b, r0))
    for a, m1, m2, b, r0 in sticks:
        tube(mb, [a, m1, m2, b], [r0, r0 * 0.88, r0 * 0.72, r0 * 0.55], sides, p["wood"], u_repeats=1, tip=not caps,
             cap_end=caps, cap_start=caps, end_mat=p.get("end"),
             end_cap_uv=lambda aa, q: (0.5 + 0.497 * q * math.cos(aa), 0.5 + 0.497 * q * math.sin(aa)))
        if rng.random() < 0.7:   # forked twig
            s = rng.uniform(0.3, 0.7)
            q0 = a.lerp(b, s)
            dd = (b - a).normalized()
            t = rot_axis(dd, UP, rng.choice((-1, 1)) * rng.uniform(0.4, 0.9))
            t.z += rng.uniform(0.0, 0.4)
            q1 = q0 + t.normalized() * rng.uniform(0.15, 0.4)
            tube(mb, [q0, q1], [r0 * 0.5, r0 * 0.25], 3, p["wood"], u_repeats=1, tip=True)
    # fallen cones among the litter
    for k in range(int(p.get("cones", 0))):
        a = rng.uniform(0, 2 * math.pi)
        d = Vector((math.cos(a), math.sin(a), rng.uniform(-0.08, 0.08))).normalized()
        L = rng.uniform(0.06, 0.1) * float(p.get("cone_size", 1.0))
        r = L * rng.uniform(0.26, 0.32)
        c = Vector((rng.gauss(0, spread * 0.4), rng.gauss(0, spread * 0.4), r * 0.8))
        _cone(mb, p["cone_mat"], c - d * L * 0.5, d, L, r, rng, 6 if lod == 0 else 4)
    obj = mb.build(p["name"] + ("" if lod == 0 else "_lod1"))
    vcolor.bake_ao([obj], samples=16, distance=0.3)
    vcolor.bake_wear(obj, convex_threshold_deg=40.0, seed=int(p["seed"]))
    vcolor.set_channel(obj, 2, lambda co, n, li: max(0.0, n.z) ** 2 * 0.5)
    vcolor.fill_channel(obj, 3, 1.0)
    objs = [obj]
    # a couple of dead conifer sprays dropped on the pile
    if p.get("dead_sprays", 0) and lod == 0:
        mb2 = MeshBuilder()
        atlas = p["atlas"]
        for k in range(int(p["dead_sprays"])):
            a = rng.uniform(0, 2 * math.pi)
            base = Vector((rng.gauss(0, spread * 0.3), rng.gauss(0, spread * 0.3), rng.uniform(0.05, 0.2) * min(1.0, pile_h / 0.3 + 0.1)))
            d = Vector((math.cos(a), math.sin(a), -0.1)).normalized()
            ln = rng.uniform(0.35, 0.6) * float(p.get("spray_size", 1.0))
            card(mb2, base, d, Vector((-math.sin(a), math.cos(a), 0.05)), ln, ln * _aspect(atlas, "dead") * 0.5,
                 atlas["dead"], p["spray_mat"], segs=1, droop=0.1, out=UP,
                 col_fn=lambda s, x: (0.7, 0.0, 0.5, 0.2), normal_fn=lambda q, fn_: Vector((0, 0, 1)))
        objs.append(mb2.build(p["name"] + "_sprays"))
    return objs


# ---------------------------------------------------------------------------------------------

def build(params: dict, outputs: list[str]) -> None:
    kind = params["kind"]
    name = params["name"]
    for lod, out in enumerate(outputs):
        res = {"fern": build_fern, "grass": build_grass, "fireweed": build_fireweed, "yarrow": build_yarrow,
               "huckleberry": build_huckleberry, "willow": build_willow, "sapling": build_sapling, "mushroom": build_mushroom,
               "deadfall": build_deadfall, "moss": build_moss, "carpet": build_carpet}[kind](params, lod)
        if isinstance(res, MeshBuilder):
            objs = [res.build(name + ("" if lod == 0 else f"_lod{lod}"))]
        elif isinstance(res, list):
            objs = res
        else:
            objs = [res]
        print(f"[veg_plant] {name} lod{lod}: {sum(common.triangle_count(o) for o in objs)} tris")
        export.export_glb(out, objs)
