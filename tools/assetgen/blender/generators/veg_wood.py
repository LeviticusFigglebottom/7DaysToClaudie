"""Chopping props and deadwood: tree stumps, cut logs (physics objects) and fallen rotting logs.

params.kind:
  stump   - flared stump with root lobes, surface roots and an axe/saw-cut top (end grain) with a
            splintered hinge. Origin bottom centre. Convex collision proxy (<name>-convcolonly).
            keys: radius (top radius), height, bark, end (end-grain material), seed, roots
  log     - straight trunk section along X, both ends cut (end grain). Origin at the GEOMETRIC
            CENTRE (physics object, no collision proxy: the game builds a cylinder shape).
            keys: length, radius, bark, end, seed, knots
  fallen  - long mossy rotting log half sunk into the ground with jagged broken ends and branch
            stubs. Origin bottom centre (ground contact). Convex collision proxy.
            keys: length, radius, sink (fraction of diameter below ground), bark, end, seed
UVs: bark in tiles around the circumference (u) with v by arc length (texel aspect ~1); cut faces
map the end-grain disc texture by angle so its bark ring always sits on the rim.
"""
from __future__ import annotations

import math

import bpy
from mathutils import Vector, noise

from lib import common, export, vcolor
from lib.veg_mesh import MeshBuilder, tube
from lib.veg_tree import lobe_factor, smooth

END_R = 0.497   # end-grain texture: radius (in UV) of the bark rim circle


def end_uv(a: float, q: float) -> tuple[float, float]:
    return 0.5 + END_R * q * math.cos(a), 0.5 + END_R * q * math.sin(a)


def _hull_proxy(name: str, pts: list[Vector]) -> bpy.types.Object:
    """Convex hull object from points (bmesh.ops.convex_hull), no material."""
    import bmesh
    bm = bmesh.new()
    for p in pts:
        bm.verts.new(p)
    bmesh.ops.convex_hull(bm, input=list(bm.verts))
    # drop interior/unused verts the hull op leaves behind
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _finish(mb: MeshBuilder, name: str, *, ao_dist: float, moss_fn=None, wear: bool = True, ground: bool = True,
            seed: int = 0) -> bpy.types.Object:
    obj = mb.build(name)
    vcolor.bake_ao([obj], samples=20, distance=ao_dist, ground=ground)
    if wear:
        vcolor.bake_wear(obj, convex_threshold_deg=35.0, seed=seed)
    else:
        vcolor.fill_channel(obj, 1, 0.0)
    if moss_fn is not None:
        vcolor.set_channel(obj, 2, moss_fn)
    else:
        vcolor.fill_channel(obj, 2, 0.0)
    vcolor.fill_channel(obj, 3, 1.0)
    return obj


# ---------------------------------------------------------------------------------------------
# Stump
# ---------------------------------------------------------------------------------------------

def build_stump(p: dict, name: str):
    rng = common.rng(p["seed"])
    r_top = float(p["radius"])
    h = float(p["height"])
    bark, endm = p["bark"], p["end"]
    sides = int(p.get("sides", 18))
    noise.seed_set(int(p["seed"]) % 100000)
    n_l = rng.randint(4, 6)
    a0 = rng.uniform(0, 2 * math.pi)
    lobes = [(a0 + 2 * math.pi * i / n_l + rng.uniform(-0.35, 0.35), rng.uniform(0.2, 0.45)) for i in range(n_l)]
    tilt = math.radians(rng.uniform(2.0, 6.0))
    tilt_dir = rng.uniform(0, 2 * math.pi)
    zs = [-0.22, -0.08, 0.0, 0.06, 0.14, 0.25, 0.38, h * 0.8, h]

    def radius(z):
        return r_top * (1.0 + 0.03 * (h - z)) + r_top * 0.55 * math.exp(-(max(z, -0.22) + 0.08) / 0.22)

    def rfn(i, s, a):
        z = zs[i]
        lf = lobe_factor(lobes, a) * math.exp(-max(0.0, z) / 0.3) * (1.0 + max(0.0, -z) * 3.0)
        nz = noise.noise(Vector((math.cos(a) * 2.0, math.sin(a) * 2.0, z * 3.0)))
        return 1.0 + lf + nz * 0.03

    def cut_z(x, y):
        return h + math.tan(tilt) * (x * math.cos(tilt_dir) + y * math.sin(tilt_dir))

    pts = [Vector((0.0, 0.0, z)) for z in zs]
    radii = [radius(z) for z in zs]
    mb = MeshBuilder()
    rings, v_end = tube(mb, pts, radii, sides, bark, u_repeats=max(1, round(2 * math.pi * r_top / 0.7)), radius_fn=rfn,
                        tip=False)
    # tilt the top ring onto the cut plane and build the cut face (own vertices, end-grain UVs)
    top = rings[-1]
    for vi in top:
        x, y, _ = mb.co[vi]
        mb.co[vi] = (x, y, cut_z(x, y))
    em = mb.mat(endm)
    rim = []
    for j, vi in enumerate(top):
        rim.append(mb.v(mb.co[vi]))
    # inner ring + centre give the face a little relief (centre slightly sunk, saw-rough)
    inner = []
    for j, vi in enumerate(top):
        x, y, z = mb.co[vi]
        q = 0.55
        inner.append(mb.v((x * q, y * q, cut_z(x * q, y * q) - 0.004)))
    c = mb.v((0.0, 0.0, cut_z(0.0, 0.0) - 0.008))
    for j in range(sides):
        j2 = (j + 1) % sides
        a1, a2 = 2 * math.pi * j / sides, 2 * math.pi * (j + 1) / sides
        mb.f((rim[j], rim[j2], inner[j2], inner[j]), (end_uv(a1, 1.0), end_uv(a2, 1.0), end_uv(a2, 0.55), end_uv(a1, 0.55)), em)
        mb.f((inner[j], inner[j2], c), (end_uv(a1, 0.55), end_uv(a2, 0.55), (0.5, 0.5)), em)
    # hinge splinters: thin wedges standing up along a chord on one side of the cut
    hd = rng.uniform(0, 2 * math.pi)
    hv = Vector((math.cos(hd), math.sin(hd), 0.0))
    hs = Vector((-hv.y, hv.x, 0.0))
    for k in range(rng.randint(3, 6)):
        off = rng.uniform(-0.7, 0.7) * r_top
        base = hv * (r_top * rng.uniform(0.0, 0.2)) + hs * off
        base.z = cut_z(base.x, base.y) - 0.005
        hmax = (rng.uniform(0.04, 0.14) * (1.0 - abs(off) / r_top) + 0.02) * float(p.get("splinter", 1.0))
        w = rng.uniform(0.03, 0.08) * r_top / 0.36
        d = rng.uniform(0.006, 0.012)
        # a thin plate: bottom edge on the cut, jagged top edge with 3 points
        tops = [base + hs * (w * x) + Vector((rng.uniform(-0.006, 0.006), rng.uniform(-0.006, 0.006),
                                               hmax * rng.uniform(0.3, 1.0))) for x in (-0.9, 0.0, 0.9)]
        bot = [base + hs * (w * x) for x in (-1.0, 0.0, 1.0)]
        for sgn in (1, -1):
            off_v = hv * (d * 0.5 * sgn)
            ib = [mb.v(q + off_v) for q in bot]
            it = [mb.v(q + off_v * 0.4) for q in tops]
            for c in range(2):
                quad = (ib[c], ib[c + 1], it[c + 1], it[c]) if sgn > 0 else (ib[c + 1], ib[c], it[c], it[c + 1])
                mb.f(quad, ((0.5, 0.8), (0.53, 0.8), (0.53, 0.86), (0.5, 0.86)), em)
    # surface roots running out from the lobes
    if p.get("roots", True):
        for a, kk in sorted(lobes, key=lambda t: -t[1])[:rng.randint(3, 5)]:
            d = Vector((math.cos(a), math.sin(a), 0.0))
            L = r_top * rng.uniform(1.6, 2.8)
            side = Vector((-d.y, d.x, 0.0)) * rng.uniform(-0.15, 0.15)
            rp = [d * (r_top * 0.5) + Vector((0, 0, 0.34)), d * (r_top * 1.05) + Vector((0, 0, 0.12)),
                  (d + side) * (r_top * 1.35 + L * 0.35) + Vector((0, 0, 0.0)),
                  (d + side * 2.0) * (r_top * 1.35 + L * 0.75) + Vector((0, 0, -0.14))]
            rr = [r_top * f * (0.8 + 0.6 * kk) for f in (0.42, 0.3, 0.17, 0.08)]
            tube(mb, rp, rr, 7, bark, u_repeats=1, tip=False)
    obj = _finish(mb, name, ao_dist=r_top * 1.5, seed=int(p["seed"]))
    hull_pts = [Vector(mb.co[i]) for ring in rings for i in ring] + [Vector(mb.co[i]) for i in rim]
    col = _hull_proxy(name + "-convcolonly", [q for q in hull_pts if q.z > -0.05])
    return [obj, col]


# ---------------------------------------------------------------------------------------------
# Cut log (physics object, centred origin)
# ---------------------------------------------------------------------------------------------

def build_log(p: dict, name: str):
    rng = common.rng(p["seed"])
    L = float(p.get("length", 4.0))
    r = float(p.get("radius", 0.17))
    bark, endm = p["bark"], p["end"]
    sides = int(p.get("sides", 14))
    noise.seed_set(int(p["seed"]) % 100000)
    n = 9
    bow = rng.uniform(0.01, 0.035)
    bow_dir = rng.uniform(0, 2 * math.pi)
    pts, radii = [], []
    for i in range(n):
        s = i / (n - 1)
        x = -L / 2 + L * s
        b = math.sin(math.pi * s) * bow
        pts.append(Vector((x, math.cos(bow_dir) * b, math.sin(bow_dir) * b)))
        radii.append(r * (1.04 - 0.08 * s))
    off = Vector((rng.uniform(0, 30), rng.uniform(0, 30), 0))

    def rfn(i, s, a):
        return 1.0 + noise.noise(Vector((math.cos(a) * 1.5 + off.x, math.sin(a) * 1.5 + off.y, s * 6.0))) * 0.035

    mb = MeshBuilder()
    rings, v_end = tube(mb, pts, radii, sides, bark, u_repeats=max(1, round(2 * math.pi * r / 0.55)), radius_fn=rfn,
                        tip=False, cap_end=True, cap_start=True, end_mat=endm, end_cap_uv=end_uv,
                        up_hint=Vector((0, 0, 1)))
    # a few knots / trimmed branch stubs
    for k in range(int(p.get("knots", rng.randint(2, 4)))):
        s = rng.uniform(0.12, 0.88)
        i = int(s * (n - 1))
        a = rng.uniform(0, 2 * math.pi)
        d = Vector((0.0, math.cos(a), math.sin(a)))
        base = pts[i] + d * (radii[i] * 0.8)
        kr = rng.uniform(0.02, 0.04)
        kl = rng.uniform(0.0, 0.015)
        tube(mb, [base, base + d * (radii[i] * 0.2 + kl)], [kr * 1.3, kr], 6, bark, u_repeats=1, tip=False,
             cap_end=True, end_mat=endm, end_cap_uv=lambda aa, q: (0.5 + 0.12 * q * math.cos(aa), 0.5 + 0.12 * q * math.sin(aa)))
    obj = _finish(mb, name, ao_dist=0.3, ground=False, seed=int(p["seed"]))
    # origin at the geometric (bounding box) centre
    lo, hi = common.bounds(obj)
    cen = (lo + hi) * 0.5
    from mathutils import Matrix
    obj.data.transform(Matrix.Translation(-cen))
    return [obj]


# ---------------------------------------------------------------------------------------------
# Fallen rotting log
# ---------------------------------------------------------------------------------------------

def _jagged_end(mb, ring, center, axis_dir, rng, mat, endm, depth, flip=False):
    """Broken, rotten end: splinters stick out along the axis, the core is hollowed/torn.
    flip=True for the start of a tube (ring winding faces the other way)."""
    n = len(ring)
    m = mb.mat(mat)
    em = mb.mat(endm)

    def face(idx, uv, mat_i):
        if flip:
            mb.f(tuple(reversed(idx)), tuple(reversed(uv)), mat_i)
        else:
            mb.f(idx, uv, mat_i)
    rr = [Vector(mb.co[i]) - center for i in ring]
    row = []
    hs = []
    for j in range(n):
        h = rng.uniform(0.02, 0.18) * depth * (3.0 if rng.random() < 0.18 else 1.0)
        hs.append(h)
        q = center + rr[j] * rng.uniform(0.82, 0.95) + axis_dir * h
        row.append(mb.v(q, (0.7, 0.0, 0.0, 1.0)))
    for j in range(n):
        j2 = (j + 1) % n
        u0, u1 = j / n * 2.0, (j + 1) / n * 2.0
        face((ring[j], ring[j2], row[j2], row[j]), ((u0, 0.0), (u1, 0.0), (u1, 0.25), (u0, 0.25)), m)
    # torn core: inner ring sunk back into the log (rotted heart), end-grain material
    inner = []
    for j in range(n):
        q = center + rr[j] * rng.uniform(0.35, 0.55) - axis_dir * rng.uniform(0.02, 0.15) * depth
        inner.append(mb.v(q, (0.45, 0.0, 0.0, 1.0)))
    c = mb.v(center - axis_dir * 0.2 * depth, (0.35, 0.0, 0.0, 1.0))
    for j in range(n):
        j2 = (j + 1) % n
        a1, a2 = 2 * math.pi * j / n, 2 * math.pi * (j + 1) / n
        face((row[j], row[j2], inner[j2], inner[j]), (end_uv(a1, 0.92), end_uv(a2, 0.92), end_uv(a2, 0.45), end_uv(a1, 0.45)), em)
        face((inner[j], inner[j2], c), (end_uv(a1, 0.45), end_uv(a2, 0.45), (0.5, 0.5)), em)


def build_fallen(p: dict, name: str):
    rng = common.rng(p["seed"])
    L = float(p["length"])
    r = float(p["radius"])
    sink = float(p.get("sink", 0.3))
    bark, endm = p["bark"], p["end"]
    sides = int(p.get("sides", 20))
    noise.seed_set(int(p["seed"]) % 100000)
    n = 16
    zc = r - sink * 2.0 * r
    sag = rng.uniform(0.05, 0.12)
    yaw_bend = rng.uniform(0.25, 0.5) * rng.choice((-1, 1))
    wave = rng.uniform(0, 6.28)
    pts, radii = [], []
    for i in range(n):
        s = i / (n - 1)
        x = -L / 2 + L * s
        y = yaw_bend * math.sin(math.pi * s) * 0.8 + 0.06 * math.sin(s * 9.0 + wave)
        z = zc - sag * math.sin(math.pi * s) + 0.03 * math.sin(s * 7.0 + wave * 1.3)
        pts.append(Vector((x, y, z)))
        radii.append(r * (1.18 - 0.36 * s))
    off = Vector((rng.uniform(0, 30), rng.uniform(0, 30), 0))

    def rfn(i, s, a):
        # lumpy, slumped cross-section: flatter on the bottom, rot pits
        nz = noise.noise(Vector((math.cos(a) * 1.2 + off.x, math.sin(a) * 1.2 + off.y, s * 6.0)))
        nz2 = noise.noise(Vector((math.cos(a) * 3.5 + off.y, math.sin(a) * 3.5, s * 16.0)))
        swell = 1.0 + 0.08 * math.sin(s * 7.0 + off.x)
        flat = 1.0 - 0.15 * max(0.0, -math.sin(a)) ** 2
        return flat * swell * (1.0 + nz * 0.11 + nz2 * 0.04)

    mb = MeshBuilder()
    rings, v_end = tube(mb, pts, radii, sides, bark, u_repeats=max(1, round(2 * math.pi * r / 0.8)), radius_fn=rfn,
                        tip=False, up_hint=Vector((0, 0, 1)))
    _jagged_end(mb, rings[-1], pts[-1], Vector((1, 0, 0)), rng, bark, endm, r)
    _jagged_end(mb, rings[0], pts[0], Vector((-1, 0, 0)), rng, bark, endm, r, flip=True)
    # broken branch stubs (some pointing up, some sideways)
    for k in range(rng.randint(2, 4)):
        s = rng.uniform(0.15, 0.85)
        i = int(s * (n - 1))
        a = rng.uniform(-0.3, math.pi + 0.3)
        d = Vector((rng.uniform(-0.3, 0.3), math.cos(a), math.sin(a))).normalized()
        base = pts[i] + d * radii[i] * 0.7
        sl = rng.uniform(0.2, 0.7)
        sr = rng.uniform(0.06, 0.11)
        bp = [base, base + d * (radii[i] * 0.3 + sl * 0.5), base + d * (radii[i] * 0.3 + sl)]
        tube(mb, bp, [sr, sr * 0.82, sr * 0.68], 6, bark, u_repeats=1, tip=False, cap_end=True, end_mat=endm,
             end_cap_uv=lambda aa, q: (0.5 + 0.2 * q * math.cos(aa), 0.5 + 0.2 * q * math.sin(aa)))

    def moss(co, nrm, li):
        up = max(0.0, nrm.z)
        nz = noise.noise(Vector((co.x * 0.9, co.y * 0.9, co.z * 0.9 + 9.0))) * 0.5 + 0.5
        nz2 = noise.noise(Vector((co.x * 3.0, co.y * 3.0, co.z * 3.0 + 2.0))) * 0.5 + 0.5
        return min(1.0, up ** 1.1 * smooth(0.18, 0.6, nz) * (0.75 + 0.6 * nz2) + 0.12 * (1.0 - smooth(0.0, 0.25, co.z)))

    obj = _finish(mb, name, ao_dist=r * 1.6, moss_fn=moss, seed=int(p["seed"]))
    hull = []
    for i in (0, n // 2, n - 1):
        for j in range(8):
            a = 2 * math.pi * j / 8
            hull.append(pts[i] + Vector((0.0, math.cos(a), math.sin(a))) * radii[i] * 0.97)
    col = _hull_proxy(name + "-convcolonly", [q for q in hull if q.z > -0.15])
    return [obj, col]


def build(params: dict, outputs: list[str]) -> None:
    name = params["name"]
    kind = params["kind"]
    objs = {"stump": build_stump, "log": build_log, "fallen": build_fallen}[kind](params, name)
    print(f"[veg_wood] {name}: {common.triangle_count(objs[0])} tris")
    export.export_glb(outputs[0], objs)
