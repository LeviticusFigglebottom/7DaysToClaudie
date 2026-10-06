"""Player-built log pieces and blueprint ghosts, plus the shared building-log toolkit (ADR-0035) that
structure_base / structure_camp / structure_stations import (their catalog tasks list this file as
a source).

log_piece: 4.0 m along X, envelope d = 0.34 m (no vertex beyond r = 0.17 or |x| = 2.0), origin at the
CENTRE (physics object). The snapping contract (game/src/building/log_snapper.gd) is unchanged: a
cove scribed along the underside and saddle notches near both ends, both cylindrical cuts of radius
CUT_R about the line 0.29 m below the axis (crossing logs at x = +-1.83).

The look (The Forest's hand-built logs): thick fissured bark plates displaced into the geometry
from the same periodic plate field the struct_log_bark texture paints (textures/gen/structures.py,
keep BARK_* in sync), a gentle taper and out-of-round lobes, trimmed branch stubs and flush knots,
axe-chopped ends (two chop facets meeting at a ridge, a hewn chamfer round the rim, disc-mapped end
grain with rings and checks) and moss patches on the upper side through vertex colour B (the
struct_log_bark material binds the moss layer). Cuts use struct_log_hewn.

Variants: reinforced (rope lashings + iron straps with bolts, bark pressed flat under them), frac
(Voronoi chunks via lib.fracture of the clean log, inner item_wood_inner). Ghosts: simple merged logs
at the blueprint piece transforms (Godot coordinates converted to Blender: (x, y, z) -> (x, -z, y)),
origin = blueprint origin.
"""
from __future__ import annotations

import math
import random

import bpy
import numpy as np
from mathutils import Matrix, Vector, noise

from lib import common, fracture, item_kit as K, vcolor

LEN, RAD = 4.0, 0.17
NOTCH_X = 1.83          # crossing-log centre lines (cabin walls at +-1.83 m)
STEP = 0.29             # vertical spacing of stacked / crossing logs
CUT_R = 0.176           # cutter radius (log radius + clearance)
ENV = 0.1695            # hard cap on any bark vertex (inside the 0.17 envelope)

# Bark plate field shared with textures/gen/structures.py (struct_log_bark): one tile = once round
# the log (u) x 1 m along it (v).
BARK_SEED = 3517
BARK_CELLS = 34
BARK_STRETCH = 4.2
BARK_DEPTH = 0.016      # furrow depth below the plate crowns (m)

MAT_BARK = "struct_log_bark"
MAT_END = "struct_log_end"
MAT_HEWN = "struct_log_hewn"
MAT_KNOT = "struct_log_knot"


# ------------------------------------------------------------------------------------------------
# Bark field
# ------------------------------------------------------------------------------------------------

def _bark_tiled() -> np.ndarray:
    r = random.Random(BARK_SEED)
    pts = np.array([(r.random(), r.random()) for _ in range(BARK_CELLS)], np.float64)
    tiled = np.concatenate([pts + np.array([dx, dy]) for dx in (-1, 0, 1) for dy in (-1, 0, 1)])
    tiled[:, 1] /= BARK_STRETCH
    return tiled


_TILED = _bark_tiled()


def bark_gap(u: np.ndarray, v: np.ndarray):
    """(F2 - F1 in metres, cross) of the plate field at tile coords: gap 0 on a furrow, ~0.03+ on a
    plate crown; cross 1 where the furrow runs round the log (bridged, shallow)."""
    tau = 2.0 * math.pi
    uw = u + 0.007 * np.sin(tau * (1.0 * v + 3.0 * u) + 1.3) + 0.005 * np.sin(tau * (4.0 * v - 5.0 * u) + 0.4)
    vw = v + 0.030 * np.sin(tau * (3.0 * u + v) + 2.1)
    q = np.stack([uw % 1.0, (vw % 1.0) / BARK_STRETCH], -1)
    d = np.sqrt(((q[:, None, :] - _TILED[None, :, :]) ** 2).sum(-1))
    order = np.argsort(d, axis=1, kind="stable")[:, :2]
    rows = np.arange(len(q))
    d0, d1 = d[rows, order[:, 0]], d[rows, order[:, 1]]
    sep = _TILED[order[:, 1]] - _TILED[order[:, 0]]
    du, dv = np.abs(sep[:, 0]), np.abs(sep[:, 1])          # metric space: the furrow is normal to sep
    cross = np.clip((dv / np.maximum(np.hypot(du, dv), 1e-9) - 0.55) / 0.35, 0.0, 1.0)
    return d1 - d0, cross


def _smooth(e0: float, e1: float, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def bark_relief(u: np.ndarray, v: np.ndarray) -> np.ndarray:
    """0 at a furrow bottom .. 1 on a plate crown (smoothed to what the mesh can resolve)."""
    gap, cross = bark_gap(u, v)
    bridge = 0.75 * _smooth(0.0, 1.0, cross)
    rel = _smooth(0.0, 0.03, gap)
    return rel + (1.0 - rel) * bridge


# ------------------------------------------------------------------------------------------------
# The building log
# ------------------------------------------------------------------------------------------------

def _ring_positions(length: float, step: float, notches: bool, end_in: float) -> list[float]:
    h = length / 2
    xs = {round(-h + end_in, 4), round(h - end_in, 4)}
    if notches:
        for sgn in (1, -1):
            c = sgn * NOTCH_X
            for k in range(-7, 8):
                xs.add(round(c + k * 0.022, 4))
    n = max(2, int(round((length - 2 * end_in) / step)))
    for i in range(n + 1):
        x = -h + end_in + (length - 2 * end_in) * i / n
        if not notches or all(abs(x - sgn * NOTCH_X) > 0.17 for sgn in (1, -1)):
            xs.add(round(x, 4))
    return sorted(xs)


def _knot_list(r: random.Random, length: float, count: int, notches: bool, bands) -> list[tuple]:
    """(x, angle, radius, protrusion) for branch stubs / knots, kept off the notches, the cove
    (underside), the reinforcement bands and the ends."""
    out = []
    tries = 0
    while len(out) < count and tries < 200:
        tries += 1
        x = r.uniform(-length / 2 + 0.35, length / 2 - 0.35)
        a = r.uniform(-0.6, math.pi + 0.6)          # upper side and flanks (z > -0.1)
        if notches and any(abs(x - s * NOTCH_X) < 0.3 for s in (1, -1)):
            continue
        if any(b0 - 0.08 < x < b1 + 0.08 for b0, b1, _ in bands):
            continue
        if any(abs(x - o[0]) < 0.45 for o in out):
            continue
        stub = len(out) % 2 == 0
        out.append((x, a, r.uniform(0.024, 0.034) if stub else r.uniform(0.016, 0.024), stub))
    return out


def log_mesh(name: str, seed: int, *, length: float = LEN, crown: float = 0.168, taper: float = 0.04, sides: int = 28,
             step: float = 0.06, notches: bool = True, cove: bool = True, bands=(), knots: int = 5, end_rings=(0.68, 0.36),
             relief: float = 1.0, v_offset: float = 0.0) -> bpy.types.Object:
    """The building log along X, centred on the origin. bands = [(x0, x1, r)] where the bark is pressed
    flat to radius r (under lashings and straps). relief scales the bark displacement."""
    r = random.Random(seed)
    noise.seed_set(seed % 99991)
    mb = K.MB()
    h = length / 2
    xs = _ring_positions(length, step, notches, 0.10)
    a1, a2, a3 = r.uniform(0, 6.28), r.uniform(0, 6.28), r.uniform(0, 6.28)
    rot = r.uniform(0, 6.28)
    flip = r.random() < 0.5                       # which end is the butt (thicker)
    kl = _knot_list(r, length, knots, notches, bands)

    def centre(x: float) -> Vector:
        t = (x + h) / length
        return Vector((x, 0.0035 * math.sin(t * 2.3 + a1), 0.003 * math.sin(t * 1.7 + a2)))

    def base_r(x: float) -> float:
        t = (x + h) / length
        t = 1.0 - t if flip else t
        return crown * (1.0 - taper * t) * (1.0 + 0.008 * math.sin(t * 7.0 + a3))

    def lobes(th: float, x: float) -> float:
        return 1.0 + 0.012 * math.sin(2 * th + a1) + 0.008 * math.sin(3 * th + a2 + x * 0.4)

    def band_w(x: float):
        best = None
        for b0, b1, br in bands:
            w = min(_smooth(b0 - 0.03, b0, x), 1.0 - _smooth(b1, b1 + 0.03, x))
            if w > 0 and (best is None or w > best[0]):
                best = (float(w), br)
        return best

    def knot_bump(x: float, th: float) -> float:
        acc = 0.0
        for kx, ka, kr, stub in kl:
            dth = math.atan2(math.sin(th - ka), math.cos(th - ka)) * 0.16
            d2 = ((x - kx) ** 2 + dth * dth) / (kr * 2.4) ** 2
            acc += (0.007 if stub else 0.004) * math.exp(-d2)
        return acc

    def radius_at(x: float, ths: list[float], us: np.ndarray) -> list[float]:
        rel = bark_relief(us, np.full_like(us, x + h + v_offset))
        rb = base_r(x)
        bw = band_w(x)
        out = []
        for k, th in enumerate(ths):
            rr = rb * lobes(th, x) - BARK_DEPTH * relief * (1.0 - float(rel[k]))
            rr += knot_bump(x, th) + 0.0015 * noise.noise(Vector((x * 9.0, math.cos(th) * 2.0, math.sin(th) * 2.0)))
            if bw is not None:
                rr = rr + (bw[1] - rr) * bw[0]
            out.append(min(rr, ENV))
        return out

    ths = [rot + 2 * math.pi * k / sides for k in range(sides)]
    us = np.array([k / sides for k in range(sides)], np.float64)
    dirs = [Vector((0.0, math.cos(t), math.sin(t))) for t in ths]
    rings: list[list[int]] = []
    vcoord: list[float] = []
    for x in xs:
        c = centre(x)
        rr = radius_at(x, ths, us)
        rings.append([mb.vert(c + dirs[k] * rr[k]) for k in range(sides)])
        vcoord.append(x + h + v_offset)
    # bark quads (u = 0..1 once round, v = metres along)
    for i in range(len(rings) - 1):
        for k in range(sides):
            k2 = (k + 1) % sides
            mb.face((rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]),
                    ((k / sides, vcoord[i]), ((k + 1) / sides, vcoord[i]), ((k + 1) / sides, vcoord[i + 1]), (k / sides, vcoord[i + 1])),
                    MAT_BARK, True)

    # axe-chopped ends: two chop facets meeting at a ridge (never beyond |x| = length/2), a bark lip,
    # a hewn chamfer round the rim, then the end-grain disc
    for sgn in (1, -1):
        ea = r.uniform(0, math.pi)
        depth_f, tilt_f = r.uniform(0.055, 0.075), r.uniform(0.006, 0.014)
        ridge_off = r.uniform(-0.25, 0.25)

        def chop(y: float, z: float, ea=ea, depth_f=depth_f, tilt_f=tilt_f, ridge_off=ridge_off) -> float:
            yy = y * math.cos(ea) + z * math.sin(ea)
            zz = -y * math.sin(ea) + z * math.cos(ea)
            rr0 = crown
            return (depth_f * abs(zz / rr0 - ridge_off * 0.3) + tilt_f * (1.0 + yy / rr0) * 0.5
                    + 0.008 * abs(math.sin(2.6 * yy / rr0 + ea * 3.0)) + 0.0012 * math.sin(yy * 60.0 + ea))

        last = rings[-1] if sgn > 0 else rings[0]
        xin = xs[-1] if sgn > 0 else xs[0]
        c_end = centre(sgn * h)
        rr_l = radius_at(sgn * (h - 0.02), ths, us)
        lip, bsec, cham = [], [], []
        rend = base_r(sgn * h) * 0.84
        for k in range(sides):
            d = dirs[k]
            p = d * rr_l[k] * 0.99
            ex = sgn * (h - chop(p.y, p.z))
            lip.append(mb.vert(Vector((ex - sgn * 0.012, c_end.y + p.y, c_end.z + p.z))))
            # inner face of the bark (the bark's cut section shows as a dark band round the rim)
            b = d * (base_r(sgn * h) - BARK_DEPTH * 0.9) * lobes(ths[k], sgn * h)
            bsec.append(mb.vert(Vector((sgn * (h - chop(b.y, b.z)) - sgn * 0.009, c_end.y + b.y, c_end.z + b.z))))
            q = d * rend * lobes(ths[k], sgn * h)
            cham.append(mb.vert(Vector((sgn * (h - chop(q.y, q.z)) - sgn * 0.001, c_end.y + q.y, c_end.z + q.z))))
        disc = [cham]
        for qf in end_rings:
            ring = []
            for k in range(sides):
                q = dirs[k] * rend * qf * lobes(ths[k], sgn * h)
                ring.append(mb.vert(Vector((sgn * (h - chop(q.y, q.z)), c_end.y + q.y, c_end.z + q.z))))
            disc.append(ring)
        cv = mb.vert(Vector((sgn * (h - chop(0.0, 0.0)), c_end.y, c_end.z)))
        circ = 2 * math.pi * crown
        vin = xin + h + v_offset
        vl = (sgn * (h - 0.02)) + h + v_offset
        for k in range(sides):
            k2 = (k + 1) % sides
            u0, u1 = k / sides, (k + 1) / sides
            # bark section: the plate field squeezed into the band reads as cork and furrow colours
            bs0, bs1 = (vl, vl + 0.004 * sgn)
            if sgn > 0:
                mb.face((last[k], last[k2], lip[k2], lip[k]), ((u0, vin), (u1, vin), (u1, vl), (u0, vl)), MAT_BARK, True)
                mb.face((lip[k], lip[k2], bsec[k2], bsec[k]), ((u0, bs0), (u1, bs0), (u1, bs1), (u0, bs1)), MAT_BARK, False)
                mb.face((bsec[k], bsec[k2], cham[k2], cham[k]), ((u0 * circ, 0.0), (u1 * circ, 0.0), (u1 * circ, 0.03), (u0 * circ, 0.03)),
                        MAT_HEWN, False)
            else:
                mb.face((lip[k], lip[k2], last[k2], last[k]), ((u0, vl), (u1, vl), (u1, vin), (u0, vin)), MAT_BARK, True)
                mb.face((bsec[k], bsec[k2], lip[k2], lip[k]), ((u0, bs1), (u1, bs1), (u1, bs0), (u0, bs0)), MAT_BARK, False)
                mb.face((cham[k], cham[k2], bsec[k2], bsec[k]), ((u0 * circ, 0.03), (u1 * circ, 0.03), (u1 * circ, 0.0), (u0 * circ, 0.0)),
                        MAT_HEWN, False)

        def duv(k: int, qf: float) -> tuple[float, float]:
            a = ths[k % sides] - rot
            return (0.5 + 0.46 * qf * math.cos(a) * sgn, 0.5 + 0.46 * qf * math.sin(a))
        qs = [1.0] + list(end_rings)
        for j in range(len(disc) - 1):
            ra, rb_ = disc[j], disc[j + 1]
            for k in range(sides):
                k2 = (k + 1) % sides
                vs = (ra[k], ra[k2], rb_[k2], rb_[k])
                uvs = (duv(k, qs[j]), duv(k + 1, qs[j]), duv(k + 1, qs[j + 1]), duv(k, qs[j + 1]))
                if sgn < 0:
                    vs, uvs = vs[::-1], uvs[::-1]
                mb.face(vs, uvs, MAT_END, False)
        inner = disc[-1]
        for k in range(sides):
            k2 = (k + 1) % sides
            vs = (inner[k], inner[k2], cv)
            uvs = (duv(k, qs[-1]), duv(k + 1, qs[-1]), (0.5, 0.5))
            if sgn < 0:
                vs, uvs = vs[::-1], uvs[::-1]
            mb.face(vs, uvs, MAT_END, False)

    n_log = len(mb.co)
    # saddle notches + cove: cylindrical cuts about the line STEP below the axis
    cut = set()
    for i in range(n_log):
        c = mb.co[i]
        z_new = None
        if cove and c.y * c.y + (c.z + STEP) ** 2 < CUT_R ** 2:
            z_new = -STEP + math.sqrt(max(0.0, CUT_R ** 2 - c.y * c.y))
        if notches:
            for s in (1, -1):
                dx = c.x - s * NOTCH_X
                if dx * dx + (c.z + STEP) ** 2 < CUT_R ** 2:
                    zn = -STEP + math.sqrt(max(0.0, CUT_R ** 2 - dx * dx))
                    z_new = zn if z_new is None else max(z_new, zn)
        if z_new is not None and z_new > c.z:
            mb.co[i] = Vector((c.x, c.y, z_new))
            cut.add(i)
    for fi, f in enumerate(mb.faces):
        if mb.fmat[fi] in (MAT_BARK, MAT_HEWN) and sum(1 for v in f if v in cut) >= 3:
            mb.fmat[fi] = MAT_HEWN
            mb.fuv[fi] = [(mb.co[v].x, mb.co[v].y) for v in f]
            mb.fsmooth[fi] = False

    # trimmed branch stubs and flush knots: bark collar growing out of the surface, axe-trimmed face
    for j, (kx, ka, kr, stub) in enumerate(kl):
        th = ka
        d = Vector((0.0, math.cos(th), math.sin(th)))
        c = centre(kx)
        rs = radius_at(kx, [th], np.array([((th - rot) / (2 * math.pi)) % 1.0]))[0]
        tip_r = min(ENV, rs + (0.009 if stub else 0.003))
        tilt = Vector((r.uniform(-0.25, 0.25), 0, 0))
        ax = (d + tilt).normalized()
        base = c + d * (rs - 0.03)
        tip = c + d * tip_r
        pts = [base, base.lerp(tip, 0.6), tip]
        radii = [kr * 1.9, kr * 1.3, kr]
        rings_k = K.tube(mb, pts, radii, sides=8, mat=MAT_BARK, caps=(False, False), up=Vector((1, 0, 0)), rot=r.uniform(0, 6.28))
        # trimmed face: flat cap, slightly bevelled toward the trim direction
        top = rings_k[-1]
        cc = mb.vert(tip + ax * 0.0005)
        uvr = [(0.5 + 0.46 * math.cos(2 * math.pi * k / 8), 0.5 + 0.46 * math.sin(2 * math.pi * k / 8)) for k in range(8)]
        mb.tri_fan(cc, top, (0.5, 0.5), uvr, MAT_KNOT, smooth=False)
        # stubs/knots poke out of the log: keep every vertex within the envelope
        for ring in rings_k:
            for vi in ring:
                p = mb.co[vi] - c
                rad = math.hypot(p.y, p.z)
                if rad > ENV:
                    s_ = ENV / rad
                    mb.co[vi] = Vector((mb.co[vi].x, c.y + p.y * s_, c.z + p.z * s_))
    # the contract is about the true axis (the centre line wobbles a few mm): clamp against it
    for i, co in enumerate(mb.co):
        rad = math.hypot(co.y, co.z)
        if rad > ENV:
            mb.co[i] = Vector((co.x, co.y * ENV / rad, co.z * ENV / rad))
    obj = mb.build(name, sharp_deg=60)
    return obj


def moss_mask(seed: int):
    """Vertex colour B: patchy moss on the upper side of the bark (the shader multiplies by facing up)."""
    noise.seed_set(seed % 9973)
    off = Vector((seed % 17 * 1.7, seed % 7 * 2.3, 0.0))

    def fn(co, n, li):
        p = co + off
        m = noise.noise(p * 1.4) * 0.65 + noise.noise(p * 4.5) * 0.35
        return float(_smooth(0.22, 0.48, m))
    return fn


def finish(outputs: list[str], name: str, parts, seed: int, *, separate=(), foliage=(), colliders=(), pivots: dict | None = None,
           ground: bool = True, wear_deg: float = 35.0, ao_dist: float | None = None, ao_samples: int = 16) -> int:
    """Like item_kit.publish (no settle / drop: parts are modelled in place) but the B channel is the
    moss mask, and `pivots` = {node name: Vector} sets a separate node's origin (a door leaf's hinge,
    a rack fill's bottom centre; '*' = each node's own bottom centre)."""
    obj = K.join(parts, name)
    seps = [o for o in separate if o is not None]
    fol = [o for o in foliage if o is not None]
    solid = [obj] + seps
    meshes = solid + fol
    for i, o in enumerate(meshes):
        K.bake_wear_and_masks(o, wear_deg=wear_deg, seed=seed + i * 17)
    for o in solid:
        vcolor.set_channel(o, 2, moss_mask(seed))
    for o in fol:
        zmin = min((o.matrix_world @ v.co).z for v in o.data.vertices)
        K.foliage_wind(o, base_z=zmin, height=0.6, amount=0.3)
    K.bake_ao(meshes, ground=ground, dist=ao_dist, samples=ao_samples)
    pivots = pivots or {}
    for o in seps:
        piv = pivots.get(o.name, pivots.get("*"))
        if piv is None:
            continue
        if piv == "bottom":
            V = K.world_verts([o])
            lo, hi = V.min(0), V.max(0)
            piv = Vector(((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]))
        piv = Vector(piv)
        o.data.transform(Matrix.Translation(-piv))
        o.location = piv
    bpy.context.view_layer.update()
    cols = [c for c in colliders if c is not None]
    K.export_objects(outputs[0], meshes + cols)
    tris = K.tri_count(meshes)
    print(f"[structure] {name}: {tris} tris -> {outputs[0]}")
    for o in meshes:
        V = K.world_verts([o])
        lo, hi = V.min(0), V.max(0)
        print(f"[structure]   node {o.name}: {K.tri_count([o])} tris, bounds {tuple(round(float(a), 3) for a in lo)} .. "
              f"{tuple(round(float(a), 3) for a in hi)}, origin {tuple(round(a, 3) for a in o.location)}")
    return tris


# ------------------------------------------------------------------------------------------------
# Shared pieces for the other structure generators
# ------------------------------------------------------------------------------------------------

def place(obj: bpy.types.Object, m: Matrix) -> bpy.types.Object:
    obj.data.transform(m)
    obj.data.update()
    return obj


def axis_matrix(p0, p1) -> Matrix:
    """Maps local +X (a log built along X, centred) onto the segment p0 -> p1 (centre at its middle),
    keeping local +Z as close to world up as possible."""
    p0, p1 = Vector(p0), Vector(p1)
    d = (p1 - p0)
    x = d.normalized()
    up = Vector((0, 0, 1)) if abs(x.z) < 0.95 else Vector((0, 1, 0))
    y = up.cross(x).normalized()
    z = x.cross(y).normalized()
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = (p0 + p1) / 2
    return m


def light_log(name: str, seed: int, *, length: float = LEN, crown: float = 0.168, sides: int = 12, step: float = 0.3,
              knots: int = 2) -> bpy.types.Object:
    """A cheap building log (rack fills, stringers): same bark field, no notches or cove (~500 tris)."""
    return log_mesh(name, seed, length=length, crown=crown, sides=sides, step=step, notches=False, cove=False, knots=knots,
                    end_rings=(0.5,), relief=0.8)


def half_log(mb: K.MB, length: float, radius: float, seed: int, *, sides: int = 10, steps: int = 4, depth: float = 0.92,
             bark: str = MAT_BARK, flat_mat: str = MAT_HEWN, end_mat: str = MAT_END, char_from: float | None = None,
             char_mat: str = "struct_log_char", ember_tip: str | None = None) -> None:
    """A split log along local X (centred), flat riven face up at z = 0, round barked underside down
    to -radius*depth. char_from = fraction of the length (from +X) that is burnt: the bark there is
    charred, the far end tapers to a glowing / charred tip (ember_tip = its material)."""
    r = random.Random(seed)
    noise.seed_set(seed % 99991)
    h = length / 2
    circ = 2 * math.pi * 0.16
    xs = [-h + length * i / steps for i in range(steps + 1)]
    ph = r.uniform(0, 6.28)
    rings = []
    for i, x in enumerate(xs):
        t = i / steps
        burn = 0.0 if char_from is None else max(0.0, (t - (1.0 - char_from)) / max(char_from, 1e-6))
        rr = radius * (1.0 + 0.04 * math.sin(t * 5.0 + ph)) * (1.0 - 0.45 * burn ** 1.5)
        ring = []
        for k in range(sides + 1):
            th = math.pi + math.pi * k / sides
            lump = 1.0 + 0.03 * noise.noise(Vector((x * 6.0, k * 0.7, seed % 31)))
            y, z = math.cos(th) * rr * lump, math.sin(th) * rr * depth * lump
            ring.append(mb.vert((x, y, z - burn * 0.01)))
        rings.append((ring, burn, rr))
    # riven face rows: the arc's two edge vertices plus `across` interior points with split relief
    across = 3
    flats = []
    for i, (ring, burn, rr) in enumerate(rings):
        row = [ring[sides]]
        x = xs[i]
        for j in range(across, 0, -1):
            f = j / (across + 1)
            y = -rr + 2 * rr * f
            z = 0.006 * noise.noise(Vector((x * 4.0, y * 9.0, seed % 13 + 0.5))) - 0.004 * math.exp(-((y - rr * 0.1) / 0.012) ** 2)
            row.append(mb.vert((x, y, z - burn * 0.01)))
        row.append(ring[0])
        flats.append(row)
    for i in range(steps):
        (ra, ba, rra), (rb, bb, rrb) = rings[i], rings[i + 1]
        chr_ = char_from is not None and (ba + bb) * 0.5 > 0.12
        for k in range(sides):
            u0, u1 = (k / sides) * math.pi * rra / circ, ((k + 1) / sides) * math.pi * rra / circ
            mb.face((ra[k], ra[k + 1], rb[k + 1], rb[k]), ((u0, xs[i]), (u1, xs[i]), (u1, xs[i + 1]), (u0, xs[i + 1])),
                    char_mat if chr_ else bark, True)
        # flat riven face: strips across the width, torn a few mm up and down along the split
        fa, fb = flats[i], flats[i + 1]
        for j in range(len(fa) - 1):
            vs = (fa[j], fa[j + 1], fb[j + 1], fb[j])
            mb.face(vs, [(mb.co[v].x, mb.co[v].y) for v in vs], char_mat if chr_ else flat_mat, False)
    for end, (ring, burn, rr) in ((0, rings[0]), (1, rings[-1])):
        sgn = -1 if end == 0 else 1
        c = mb.vert(((xs[0] if end == 0 else xs[-1]) + sgn * 0.003, 0.0, -rr * depth * 0.45))
        uvr = [(0.5 + 0.46 * math.cos(math.pi + math.pi * k / sides), 0.5 + 0.46 * math.sin(math.pi + math.pi * k / sides))
               for k in range(sides + 1)]
        m = end_mat if (end == 0 or ember_tip is None) else ember_tip
        for k in range(sides):
            vs = (c, ring[k + 1], ring[k]) if end == 0 else (c, ring[k], ring[k + 1])
            uv = ((0.5, 0.35), uvr[k + 1], uvr[k]) if end == 0 else ((0.5, 0.35), uvr[k], uvr[k + 1])
            mb.face(vs, uv, m, False)
        vs = (c, ring[0], ring[sides]) if end == 0 else (c, ring[sides], ring[0])
        mb.face(vs, ((0.5, 0.35), uvr[0], uvr[sides]) if end == 0 else ((0.5, 0.35), uvr[sides], uvr[0]), m, False)


def pole(mb: K.MB, a, b, r0: float, r1: float, seed: int, *, bark: str | None = None, n: int = 5, bend: float = 0.01,
         sides: int = 8, caps=(True, True), lumpy: float = 0.04) -> list:
    """A barked pole a -> b. Default bark by size: item_bark's 0.6 m plates only read on trunks, so
    poles under 6 cm radius get the fine young bark (item_bark_twig)."""
    if bark is None:
        bark = MAT_BARK if r0 >= 0.034 else "item_bark_twig"
    a, b = Vector(a), Vector(b)
    d = b - a
    side = d.orthogonal().normalized()
    rr = random.Random(seed)
    ph = rr.uniform(0, 6.28)
    pts = [a + d * (i / (n - 1)) + side * bend * math.sin(i / (n - 1) * math.pi + ph) for i in range(n)]
    if bark != MAT_BARK:
        return K.stick(mb, pts, r0, r1, sides=sides, seed=seed, bark=bark, caps=caps, lumpy=lumpy)
    # the building-log bark wraps once round (u 0..1) so its plates tile without a seam
    radii = [(r0 + (r1 - r0) * i / (n - 1)) * (1.0 + rr.uniform(-lumpy, lumpy)) for i in range(n)]
    return K.tube(mb, pts, radii, sides=sides, mat=MAT_BARK, cap_mat=MAT_END, cap_uv="disc", caps=caps, rot=rr.uniform(0, 6.28),
                  u_tile=1.0, v_offset=rr.uniform(0, 1))


def bind(mb: K.MB, center, axis, radius: float, seed: int, *, turns: float = 4, cord: float = 0.005, width: float = 0.05,
         mat: str = "item_rope", per_turn: int = 9, sides: int = 4) -> None:
    """A rope binding round a pole (axis = the pole's direction)."""
    c = Vector(center)
    ax = Vector(axis).normalized() * (width / 2)
    K.lashing(mb, c - ax, c + ax, radius, cord=cord, turns=turns, per_turn=per_turn, sides=sides, mat=mat, seed=seed,
              wobble=cord * 0.25)


def cross_lash(mb: K.MB, center, axis_a, axis_b, radius: float, seed: int, *, cord: float = 0.005, mat: str = "item_rope") -> None:
    """Square lashing where two poles cross: wraps along both poles plus a frapping turn."""
    bind(mb, center, axis_a, radius, seed, turns=3, cord=cord, width=radius * 1.6, mat=mat, per_turn=7)
    bind(mb, center, axis_b, radius * 1.02, seed + 1, turns=3, cord=cord, width=radius * 1.6, mat=mat, per_turn=7)


def stone(name: str, size, seed: int, center, *, mat: str = "item_stone", tris: int = 120, lump: float = 0.18,
          flat: float = 0.35) -> bpy.types.Object:
    o = K.pebble(name, size, seed, mat=mat, subdiv=3, lump=lump, flat_bottom=flat, center=center)
    n = common.triangle_count(o)
    if n > tris:
        mod = o.modifiers.new("dec", "DECIMATE")
        mod.ratio = tris / n
        common.apply_modifiers(o)
        common.shade_smooth(o, angle_deg=60.0)
    return o


# ------------------------------------------------------------------------------------------------
# Builders
# ------------------------------------------------------------------------------------------------

def _report_envelope(obj) -> None:
    V = K.world_verts([obj])
    rad = np.sqrt(V[:, 1] ** 2 + V[:, 2] ** 2)
    print(f"[structure_logs] {obj.name}: |x| <= {np.abs(V[:, 0]).max():.4f}, r <= {rad.max():.4f}")


def log_piece(p, outputs):
    obj = log_mesh("log_piece", int(p["seed"]))
    _report_envelope(obj)
    finish(outputs, "log_piece", [obj], int(p["seed"]), ground=False, ao_dist=0.25)


REINF_LASH = (-1.48, 1.48)
REINF_STRAP = (-0.72, 0.72)
BAND_R = 0.158


def log_piece_reinforced(p, outputs):
    seed = int(p["seed"])
    bands = [(x - 0.07, x + 0.07, BAND_R) for x in REINF_LASH] + [(x - 0.035, x + 0.035, BAND_R) for x in REINF_STRAP]
    obj = log_mesh("log_piece_reinforced", seed, bands=sorted(bands))
    mb = K.MB()
    # rope lashings outboard of the notches, on bark pressed flat under them
    cord = 0.0055
    for k, x in enumerate(REINF_LASH):
        # wound over the bark and across the cove (never into the space the log below sits in)
        pts = K.helix((x - 0.05, 0, 0), (x + 0.05, 0, 0), BAND_R + cord * 0.85, 6, phase=k * 1.3, per_turn=12, up=Vector((0, 0, 1)))
        rc = CUT_R + cord * 1.1
        for i, q in enumerate(pts):
            if q.y * q.y + (q.z + STEP) ** 2 < rc * rc:
                pts[i] = Vector((q.x, q.y, -STEP + math.sqrt(max(0.0, rc * rc - q.y * q.y))))
        K.tube(mb, pts, cord, sides=5, mat="item_rope", u_tile=1.0, v_scale=1.0 / (2 * math.pi * cord) / 3.0, up=Vector((1, 0, 0)))
    # forged iron straps with bolts
    sr = BAND_R + 0.0036
    for k, x in enumerate(REINF_STRAP):
        loop = []
        for i in range(28):
            a = 2 * math.pi * i / 28
            y, z = math.cos(a) * sr, math.sin(a) * sr
            if y * y + (z + STEP) ** 2 < CUT_R ** 2:
                z = -STEP + math.sqrt(max(0.0, CUT_R ** 2 - y * y)) + 0.004
            loop.append(Vector((x, y, z)))
        K.tube(mb, loop, (0.022, 0.0035), profile=K.rect_profile(1, 1, 0.25), mat="item_iron_strap", closed=True, up=Vector((1, 0, 0)))
        for a in (math.radians(25), math.radians(155), math.radians(90)):
            y, z = math.cos(a) * (sr + 0.0035), math.sin(a) * (sr + 0.0035)
            n = Vector((0, math.cos(a), math.sin(a)))
            m = Matrix.Translation((x, y, z)) @ n.to_track_quat("Z", "X").to_matrix().to_4x4()
            mb.push(m)
            K.lathe(mb, [(0.012, 0.0), (0.012, 0.0025), (0.008, 0.0042)], segments=6, mat="item_iron_strap", cap_bottom=False, cap_top=True)
            mb.pop()
    hw = mb.build("hardware", sharp_deg=45)
    _report_envelope(obj)
    finish(outputs, "log_piece_reinforced", [obj, hw], seed, ground=False, ao_dist=0.25)


def log_piece_frac(p, outputs):
    seed = int(p["seed"])
    src = log_mesh("log_src", seed)          # identical to log_piece so the chunks swap in seamlessly
    chunks = fracture.fracture(src, int(p.get("pieces", 9)), int(p.get("frac_seed", seed)), "item_wood_inner", margin=0.003,
                               bias=(1.0, 0.55, 0.55))
    bpy.data.objects.remove(src, do_unlink=True)
    bpy.context.view_layer.update()
    for ch in chunks:
        _canon(ch)
        me = ch.data
        inner = [i for i, m in enumerate(me.materials) if m is not None and m.name == "M_item_wood_inner"]
        uvl = me.uv_layers.active or me.uv_layers.new(name="UVMap")
        for poly in me.polygons:
            if poly.material_index in inner:
                n = poly.normal
                ax = max(range(3), key=lambda i: abs(n[i]))
                for li in poly.loop_indices:
                    co = me.vertices[me.loops[li].vertex_index].co + ch.location
                    u, v = ((co.y, co.z) if ax == 0 else (co.x, co.z) if ax == 1 else (co.x, co.y))
                    uvl.data[li].uv = (u, v)
        K.mark_sharp(ch, 40.0)
        K.bake_wear_and_masks(ch, wear_deg=30.0, seed=seed)
        vcolor.set_channel(ch, 2, moss_mask(seed))
    K.bake_ao(chunks, ground=False, dist=0.2, samples=16)
    K.export_objects(outputs[0], chunks)
    print(f"[item_kit] log_piece_frac: {K.tri_count(chunks)} tris in {len(chunks)} chunks -> {outputs[0]}")


def _canon(obj) -> None:
    """Geometry-defined element order (bisect_plane / holes_fill emit in a run-dependent order)."""
    import bmesh

    bm = bmesh.new()
    bm.from_mesh(obj.data)

    def vkey(v):
        return (tuple(round(c, 6) for c in v.co), tuple(sorted(tuple(round(c, 6) for c in e.other_vert(v).co) for e in v.link_edges)))

    def reorder(seq, key):
        for i, el in enumerate(sorted(seq, key=key)):
            el.index = i
        seq.sort()
        seq.index_update()
    reorder(bm.verts, vkey)
    reorder(bm.edges, lambda e: tuple(sorted((e.verts[0].index, e.verts[1].index))))

    def fkey(f):
        vs = [v.index for v in f.verts]
        k = vs.index(min(vs))
        return (f.material_index, tuple(sorted(vs)), tuple(vs[k:] + vs[:k]))
    reorder(bm.faces, fkey)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def _godot_to_blender(pos, rot_deg) -> Matrix:
    gx, gy, gz = pos
    rx, ry, rz = (math.radians(a) for a in rot_deg)
    # Godot Euler YXZ: R = Ry * Rx * Rz ; axes map Godot X->X, Y->Z, Z->-Y
    R = Matrix.Rotation(ry, 4, "Z") @ Matrix.Rotation(rx, 4, "X") @ Matrix.Rotation(-rz, 4, "Y")
    return Matrix.Translation((gx, -gz, gy)) @ R


def ghost(p, outputs):
    seed = int(p["seed"])
    mb = K.MB()
    for k, piece in enumerate(p["pieces"]):
        m = _godot_to_blender(piece["pos"], piece.get("rot", [0, 0, 0]))
        mb.push(m)
        pts = [Vector((-LEN / 2 + LEN * i / 5, 0, 0)) for i in range(6)]
        K.tube(mb, pts, RAD * 0.98, sides=12, mat="item_ghost", cap_mat="item_ghost", rot=0.13 * k)
        mb.pop()
    obj = mb.build(p["name"], sharp_deg=50)
    K.publish(outputs, name=p["name"], parts=[obj], seed=seed, keep_origin=True, inset=False, ao_dist=0.3, ao_samples=12)


BUILDERS = {"log_piece": log_piece, "log_piece_reinforced": log_piece_reinforced, "log_piece_frac": log_piece_frac, "ghost": ghost}


def build(params: dict, outputs: list[str]) -> None:
    BUILDERS[params["kind"]](params, outputs)
