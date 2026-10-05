"""Granite rocks: weathered boulders, loose pebble clusters and slabby cliff-band masses.

Shape model: a rock block is a *smoothed convex polytope* — the soft maximum of a few plane
distances, d(p) = k * log(sum exp((n_i . p - h_i) / k)) — so faces stay flat-ish and blocky while
edges/corners round off with radius ~k, like exfoliated, weathered granite. The surface is found
by radial bisection from an icosphere (vectorized with numpy), then weathering noise, a joint
groove or two, partial embedding (the base continues below z = 0) and decimation to budget.
Cliffs stack several slabs (sheeting joints) into one mass.

params: kind ("boulder" | "pebbles" | "cliff"), seed, size [x, y, z] (m), tris (budget),
        round (edge radius as fraction of the smallest size), cuts (extra fracture planes),
        embed (fraction of the height below ground), moss (0..1 up-facing moss mask in B),
        joints, talus (cliff: vertical joints, fallen blocks at the foot), count (pebbles).
"""
from __future__ import annotations

import math

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector, noise

from lib import common, export, materials, uv, vcolor
from lib.lod import decimated_copy


def _planes(r, sx, sy, sz, cuts, *, tilt=0.12, slab=False, yaw=math.pi):
    """Box planes (randomly perturbed) + random corner/edge fracture planes. yaw = max random
    rotation about Z (cliffs keep their long side along X and the face towards -Y)."""
    planes = []
    rot = Matrix.Rotation(r.uniform(-tilt, tilt), 3, "X") @ Matrix.Rotation(r.uniform(-tilt, tilt), 3, "Y") @ \
        Matrix.Rotation(r.uniform(0, yaw) if yaw >= math.pi else r.uniform(-yaw, yaw), 3, "Z")
    for axis, ext in ((Vector((1, 0, 0)), sx), (Vector((0, 1, 0)), sy), (Vector((0, 0, 1)), sz)):
        for sgn in (1, -1):
            n = rot @ (axis * sgn)
            n = (n + Vector((r.uniform(-0.15, 0.15), r.uniform(-0.15, 0.15), r.uniform(-0.15, 0.15)))).normalized()
            planes.append((n, ext * r.uniform(0.9, 1.08)))
    for _ in range(cuts):
        n = Vector((r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-0.6, 1.0) if not slab else r.uniform(-0.3, 0.6)))
        n.normalize()
        ext = math.sqrt((n.x * sx) ** 2 + (n.y * sy) ** 2 + (n.z * sz) ** 2)
        planes.append((n, ext * r.uniform(0.62, 0.85)))
    return planes


def _project(dirs: np.ndarray, planes, k: float, tmax: float) -> np.ndarray:
    """Distance along each unit direction to the soft-max polytope surface (bisection)."""
    N = np.array([list(n) for n, _ in planes], np.float64)          # (P,3)
    Hh = np.array([h for _, h in planes], np.float64)               # (P,)
    nd = dirs @ N.T                                                   # (V,P)
    lo = np.zeros(len(dirs))
    hi = np.full(len(dirs), tmax)
    for _ in range(28):
        mid = (lo + hi) * 0.5
        x = (nd * mid[:, None] - Hh[None, :]) / k
        m = x.max(1)
        d = k * (m + np.log(np.exp(x - m[:, None]).sum(1)))
        inside = d < 0.0
        lo = np.where(inside, mid, lo)
        hi = np.where(inside, hi, mid)
    return (lo + hi) * 0.5


def rock_block(name: str, p: dict, r, *, size, center=(0.0, 0.0, 0.0), subdiv=5, cuts=None, slab=False,
               round_frac=None, noise_amp=0.035, grooves=1, extra_grooves=(), yaw=math.pi, tilt=0.12, lumps=0.0):
    """extra_grooves: [(normal, offset, half_width, depth)] joint planes in block-local space.
    lumps: amplitude (fraction of the smallest size) of a low-frequency swell that bends the flat
    faces, so a boulder reads as weathered stone rather than a rounded box."""
    sx, sy, sz = (s * 0.5 for s in size)
    cuts = int(p.get("cuts", 5)) if cuts is None else cuts
    planes = _planes(r, sx, sy, sz, cuts, slab=slab, yaw=yaw, tilt=tilt)
    k = float(p.get("round", 0.12) if round_frac is None else round_frac) * min(sx, sy, sz) * 2.0 * 0.5
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    verts = list(bm.verts)
    dirs = np.array([list(v.co.normalized()) for v in verts], np.float64)
    t = _project(dirs, planes, k, tmax=2.5 * max(sx, sy, sz))
    seed = int(p["seed"]) % 100000
    noise.seed_set(seed)
    off = Vector((r.uniform(0, 100), r.uniform(0, 100), r.uniform(0, 100)))
    scale = 1.0 / max(sx, sy, sz)
    gplanes = []
    for _ in range(grooves):
        gn = Vector((r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-0.3, 0.3))).normalized()
        gw = r.uniform(0.02, 0.05) * min(sx, sy, sz) * 2
        gplanes.append((gn, r.uniform(-0.3, 0.3) * min(sx, sy), gw, gw * 0.9))
    gplanes += list(extra_grooves)
    for v, dvec, tt in zip(verts, dirs, t):
        pos = Vector(dvec) * tt
        q = pos * scale * 1.6 + off
        n1 = noise.fractal(q, 0.55, 2.2, 5, noise_basis="PERLIN_ORIGINAL")
        n2 = noise.noise(q * 4.0, noise_basis="VORONOI_F2F1")
        disp = (n1 * 1.0 + n2 * 0.25) * noise_amp * min(sx, sy, sz) * 2.0
        if lumps > 0.0:
            disp += noise.noise(q * 0.45 + Vector((3.7, 1.3, 0.0))) * lumps * min(sx, sy, sz) * 2.0
        for gn, gh, gw, gd in gplanes:
            dist = abs(pos.dot(gn) - gh)
            if dist < gw * 2:
                disp -= (1.0 - dist / (gw * 2)) ** 2 * gd
        v.co = pos + Vector(dvec) * disp + Vector(center)
    obj = common.mesh_from_bmesh(name, bm)
    return obj


def _embed_and_cut(obj, embed: float, floor_extra: float = 0.0) -> None:
    """Sinks the rock so `embed` of its height is below z = 0 and flattens what is deeper."""
    me = obj.data
    zs = [v.co.z for v in me.vertices]
    zmin, zmax = min(zs), max(zs)
    h = zmax - zmin
    shift = -(zmin + h * embed)
    cut = -(h * embed) + h * 0.06 + floor_extra
    for v in me.vertices:
        v.co.z += shift
        if v.co.z < cut - h * 0.5:
            v.co.z = cut - h * 0.5
    me.update()


def _finish(obj, p, tris, *, ao_dist):
    obj.data.materials.clear()
    materials.assign_all(obj, p.get("material", "rock_granite"))
    common.shade_smooth(obj, angle_deg=60.0)
    if common.triangle_count(obj) > tris:
        low = decimated_copy(obj, tris / common.triangle_count(obj), obj.name + "_d")
        name = obj.name
        bpy.data.objects.remove(obj, do_unlink=True)
        obj = low
        obj.name = name
        obj.data.name = name
        common.shade_smooth(obj, angle_deg=60.0)
    uv.box_project(obj, scale=0.5)
    vcolor.bake_ao([obj], samples=24, distance=ao_dist)
    vcolor.bake_wear(obj, convex_threshold_deg=28.0, seed=int(p["seed"]))
    moss = float(p.get("moss", 0.6))
    noise.seed_set(int(p["seed"]) % 1000 + 7)

    def mfn(co, n, li):
        up = max(0.0, n.z)
        nz = noise.noise(co * 0.9) * 0.5 + 0.5
        return moss * min(1.0, (up ** 1.1) * (0.75 + 0.7 * nz))
    vcolor.set_channel(obj, 2, mfn)
    vcolor.fill_channel(obj, 3, 1.0)
    return obj


def _hull(obj, name, max_points=48):
    """Convex collision proxy from the mesh's support points in `max_points` Fibonacci-sampled
    directions (<= max_points vertices; physics engines want small hulls)."""
    co = np.array([list(v.co) for v in obj.data.vertices], np.float64)
    n = int(max_points)
    i = np.arange(n) + 0.5
    phi = np.arccos(1.0 - 2.0 * i / n)
    th = math.pi * (1.0 + 5 ** 0.5) * i
    dirs = np.stack([np.cos(th) * np.sin(phi), np.sin(th) * np.sin(phi), np.cos(phi)], -1)
    idx = sorted(set(int(k) for k in np.argmax(co @ dirs.T, axis=0)))
    bm = bmesh.new()
    for k in idx:
        bm.verts.new(Vector(co[k]))
    res = bmesh.ops.convex_hull(bm, input=list(bm.verts))
    keep = set(e for e in res["geom"] if isinstance(e, bmesh.types.BMVert))
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v not in keep], context="VERTS")
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    col = common.new_object(name, me)
    return col


def build_boulder(p, name):
    """Weathered granite boulder: a tilted block chipped by extra fracture planes, its faces bent by
    a low swell. outputs[1] (optional) gets a decimated LOD1 for distant scatter."""
    r = common.rng(p["seed"])
    size = p.get("size", [1.8, 1.4, 1.2])
    obj = rock_block(name, p, r, size=size, subdiv=6, grooves=int(p.get("grooves", 1)), tilt=0.3,
                     noise_amp=0.03, lumps=float(p.get("lumps", 0.07)))
    _embed_and_cut(obj, float(p.get("embed", 0.18)))
    obj = _finish(obj, p, int(p.get("tris", 1500)), ao_dist=max(size) * 0.5)
    return [obj, _hull(obj, name + "-convcolonly", 48)]


def build_pebbles(p, name):
    r = common.rng(p["seed"])
    parts = []
    for i in range(int(p.get("count", 6))):
        s = r.uniform(0.13, 0.32)
        size = [s * r.uniform(1.1, 1.6), s * r.uniform(0.9, 1.2), s * r.uniform(0.5, 0.8)]
        c = (r.uniform(-0.4, 0.4), r.uniform(-0.4, 0.4), 0.0)
        q = dict(p, seed=int(p["seed"]) * 31 + i)
        o = rock_block(f"peb{i}", q, r, size=size, center=c, subdiv=2, cuts=3, round_frac=0.3, noise_amp=0.03,
                       grooves=0)
        me = o.data
        zs = [v.co.z for v in me.vertices]
        zmin, zmax = min(zs), max(zs)
        for v in me.vertices:
            v.co.z -= zmin + (zmax - zmin) * r.uniform(0.15, 0.3)
        parts.append(o)
    obj = common.join(parts, name)
    obj = _finish(obj, p, int(p.get("tris", 420)), ao_dist=0.15)
    return [obj]


def build_cliff(p, name):
    """Cliff-band mass: one wide angular granite body cut by horizontal sheeting joints and a few
    vertical joints, a stepped-back cap slab and fallen blocks at the foot. The steep face is the
    front (-Y). Origin bottom centre of the footprint."""
    r = common.rng(p["seed"])
    W, D, H = p.get("size", [9.0, 4.0, 7.0])
    sheets = []
    n_sh = max(2, int(H / 1.7))
    for i in range(n_sh):
        zl = -H / 2 + H * (i + 1) / (n_sh + 1) + r.uniform(-0.25, 0.25)
        nrm = Vector((r.uniform(-0.08, 0.08), r.uniform(-0.12, 0.02), 1.0)).normalized()
        sheets.append((nrm, zl, r.uniform(0.05, 0.1), r.uniform(0.08, 0.2)))
    for i in range(int(p.get("joints", 2))):
        a = r.uniform(-0.5, 0.5)
        nrm = Vector((math.cos(a), math.sin(a), 0.0))
        sheets.append((nrm, r.uniform(-0.3, 0.3) * W, r.uniform(0.08, 0.16), r.uniform(0.2, 0.45)))
    q = dict(p, seed=int(p["seed"]) * 17 + 1)
    main = rock_block("main", q, r, size=[W, D, H], center=(0.0, 0.0, H * 0.5), subdiv=5, cuts=int(p.get("cuts", 8)),
                      slab=True, round_frac=0.035, noise_amp=0.018, grooves=0, extra_grooves=sheets, yaw=0.12)
    parts = [main]
    # cap slab stepping back from the face
    q = dict(p, seed=int(p["seed"]) * 17 + 2)
    cw, cd, ch = W * r.uniform(0.45, 0.7), D * r.uniform(0.5, 0.75), H * r.uniform(0.22, 0.32)
    parts.append(rock_block("cap", q, r, size=[cw, cd, ch], center=(r.uniform(-0.2, 0.2) * W, D * 0.15, H * 0.86),
                            subdiv=4, cuts=5, slab=True, round_frac=0.05, noise_amp=0.02, grooves=0, yaw=0.3))
    # fallen blocks at the foot of the face
    for k in range(int(p.get("talus", 2))):
        q = dict(p, seed=int(p["seed"]) * 17 + 10 + k)
        s = r.uniform(0.12, 0.22) * H
        parts.append(rock_block(f"talus{k}", q, r, size=[s * r.uniform(1.0, 1.6), s * r.uniform(0.8, 1.2), s],
                                center=(r.uniform(-0.4, 0.4) * W, -D * r.uniform(0.45, 0.6), s * 0.35),
                                subdiv=3, cuts=5, round_frac=0.1, noise_amp=0.03, grooves=0))
    obj = common.join(parts, name)
    _embed_and_cut(obj, float(p.get("embed", 0.06)))
    me = obj.data
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    me.transform(Matrix.Translation((-(min(xs) + max(xs)) / 2, -(min(ys) + max(ys)) / 2, 0.0)))
    obj = _finish(obj, p, int(p.get("tris", 2400)), ao_dist=2.0)
    return [obj, _hull(obj, name + "-convcolonly", 96)]


def build(params: dict, outputs: list[str]) -> None:
    name = params.get("name", "rock")
    kind = params.get("kind", "boulder")
    objs = {"boulder": build_boulder, "pebbles": build_pebbles, "cliff": build_cliff}[kind](params, name)
    print(f"[rock] {name}: {common.triangle_count(objs[0])} tris")
    bpy.context.view_layer.update()   # drop stale entries of removed objects before export
    export.export_glb(outputs[0], objs)
    if len(outputs) > 1:
        # LOD1: the same rock decimated (vertex colours and UVs survive the collapse)
        low = decimated_copy(objs[0], float(params.get("lod1_ratio", 0.3)), name + "_lod1")
        print(f"[rock] {name}_lod1: {common.triangle_count(low)} tris")
        bpy.context.view_layer.update()
        export.export_glb(outputs[1], [low])
