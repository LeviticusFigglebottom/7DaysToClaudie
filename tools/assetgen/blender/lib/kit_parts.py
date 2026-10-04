"""Reusable construction parts for the POI kit: boards with splintered ends, splinter slivers,
plaster rubble, nails. All parts are added to a lib.kit_geo.KitMesh."""
from __future__ import annotations

import math
import random

from mathutils import Matrix, Vector

from . import kit_poly as P
from .kit_geo import KitMesh, SIDE_N


def board_frame(p0, p1, wdir) -> tuple[Matrix, float]:
    """Frame for a board from p0 to p1 (local +Z), width along wdir (local X), thickness local Y."""
    p0, p1 = Vector(p0), Vector(p1)
    z = p1 - p0
    length = z.length
    z.normalize()
    x = Vector(wdir)
    x = (x - z * x.dot(z))
    if x.length < 1e-6:
        x = z.orthogonal()
    x.normalize()
    y = z.cross(x)
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = p0
    return m, length


def _jag_end(z_end: float, sign: float, w: float, depth: float, rng: random.Random, teeth: int) -> tuple[list, list]:
    """Splintered end profile from x=+w/2 to x=-w/2. Returns (points (x, z), pinch factors).
    teeth=0 gives a cheap slanted break whose longer corner is pinched into a splinter point."""
    if teeth <= 0:
        d1, d2 = depth * rng.uniform(-0.2, 1.0), depth * rng.uniform(-0.2, 1.0)
        if abs(d1 - d2) < depth * 0.35:
            d1 += depth * 0.4
        p1 = rng.uniform(0.15, 0.4) if d1 > d2 else 1.0
        p2 = rng.uniform(0.15, 0.4) if d2 > d1 else 1.0
        return [(w / 2, z_end + sign * d1), (-w / 2, z_end + sign * d2)], [p1, p2]
    n = teeth * 2 + 1
    pts, pinch = [], []
    for i in range(n):
        t = i / (n - 1)
        x = w / 2 - w * t
        if 0 < i < n - 1:
            x += rng.uniform(-0.25, 0.25) * w / (n - 1)
        tip = i % 2 == 1
        if tip:
            dz = depth * rng.uniform(0.35, 1.0)
            pin = rng.uniform(0.12, 0.45)
        else:
            dz = depth * rng.uniform(-0.3, 0.12)
            pin = rng.uniform(0.7, 1.0)
        pts.append((x, z_end + sign * dz))
        pinch.append(pin)
    return pts, pinch


def board(km: KitMesh, p0, p1, wdir, width: float, thick: float, *, mat: str, rng: random.Random,
          end0: float | None = None, end1: float | None = None, teeth: int | None = None, side="n",
          end_mat: str | None = None, uv_scale: float = 1.0, uv_jitter: bool = True) -> None:
    """Board from p0 to p1 (grain along its length). end0/end1 = None for a saw cut or the jag depth
    (m) of a splintered break at that end. Broken-end faces use `end_mat` (default `mat`)."""
    m, length = board_frame(p0, p1, wdir)
    w, t = width, thick
    loop: list[tuple[float, float]] = []
    pinch: list[float] = []
    # bottom end (z = 0), from x=-w/2 to +w/2
    if end0 is None:
        loop += [(-w / 2, 0.0), (w / 2, 0.0)]
        pinch += [1.0, 1.0]
        bot_ids = set()
    else:
        k = rng.randint(2, 3) if teeth is None else teeth
        pts, pin = _jag_end(0.0, -1.0, w, end0, rng, k)
        pts, pin = list(reversed(pts)), list(reversed(pin))
        bot_ids = set(range(len(pts)))
        loop += pts
        pinch += pin
    # top end (z = length), from x=+w/2 to -w/2
    if end1 is None:
        top_start = len(loop)
        loop += [(w / 2, length), (-w / 2, length)]
        pinch += [1.0, 1.0]
        top_ids = set()
    else:
        k = rng.randint(2, 3) if teeth is None else teeth
        pts, pin = _jag_end(length, 1.0, w, end1, rng, k)
        top_start = len(loop)
        top_ids = set(range(top_start, top_start + len(pts)))
        loop += pts
        pinch += pin
    offs = [rng.uniform(-0.3, 0.3) for _ in loop]

    def depth_fn(li, vi, a, b):
        f = pinch[vi]
        c = offs[vi] * (1 - f) * t / 2
        return (c - t / 2 * f, c + t / 2 * f)

    em = end_mat or mat

    def rim_mat(pa, pb):
        ia = _find(loop, pa)
        ib = _find(loop, pb)
        if (ia in bot_ids and ib in bot_ids) or (ia in top_ids and ib in top_ids):
            return (em, SIDE_N)
        return None

    uo = (rng.uniform(0, 4), rng.uniform(0, 4)) if uv_jitter else (0.0, 0.0)
    km.prism([loop], -t / 2, t / 2, axis="y", mat=mat, side=(side, side, side), frame=m, grain="z",
             depth_fn=depth_fn, rim_mat_fn=rim_mat, uv_scale=uv_scale, uv_off=uo)


def _find(loop, p) -> int:
    for i, q in enumerate(loop):
        if abs(q[0] - p[0]) < 1e-9 and abs(q[1] - p[1]) < 1e-9:
            return i
    return -1


def sliver(km: KitMesh, base, direction, length: float, width: float, rng: random.Random, *, mat: str) -> None:
    """A thin splinter spike (tetrahedron-ish) from `base` along `direction`."""
    b = Vector(base)
    d = Vector(direction).normalized()
    s = d.orthogonal().normalized()
    u = d.cross(s)
    tip = b + d * length + s * rng.uniform(-0.2, 0.2) * length * 0.3
    pts = [b + s * width * 0.5, b - s * width * 0.5 + u * width * 0.3, b + u * width * 0.6 - s * width * 0.1, tip]
    km.hull([tuple(p) for p in pts], mat, grain=None)


def rubble(km: KitMesh, center, size: float, rng: random.Random, *, mat: str, flat_bottom: bool = True,
           top_mat: tuple[str, float] | None = None, n: int = 7) -> None:
    """Irregular chunk (convex hull of jittered points). With top_mat=(mat, side) the up-facing
    faces get that material (e.g. a plaster chunk still carrying its wall finish)."""
    c = Vector(center)
    pts = []
    sx, sy, sz = size * rng.uniform(0.8, 1.3), size * rng.uniform(0.7, 1.2), size * rng.uniform(0.35, 0.7)
    for _ in range(n):
        a = rng.uniform(0, math.tau)
        e = rng.uniform(-1.0, 1.0)
        r = rng.uniform(0.6, 1.0)
        p = Vector((math.cos(a) * math.sqrt(1 - e * e) * sx * r, math.sin(a) * math.sqrt(1 - e * e) * sy * r,
                    e * sz * r))
        pts.append(p)
    rot = Matrix.Rotation(rng.uniform(0, math.tau), 3, "Z")
    pts = [rot @ p for p in pts]
    if flat_bottom:
        zmin = min(p.z for p in pts)
        pts = [Vector((p.x, p.y, max(p.z, zmin + sz * 0.35))) for p in pts]
        zmin = min(p.z for p in pts)
        pts = [p - Vector((0, 0, zmin)) for p in pts]
    pts = [tuple(c + p) for p in pts]

    def mat_fn(n):
        if top_mat is not None and n.z > 0.75:
            return top_mat
        return None

    km.hull(pts, mat, mat_fn=mat_fn, uv_off=(rng.uniform(0, 3), rng.uniform(0, 3)))


def plaster_flake(km: KitMesh, center, size: float, rng: random.Random, *, finish_side: float,
                  thick: float = 0.018, tilt: float = 0.25) -> None:
    """A fallen piece of wall skin lying on the floor: jagged slab, finish on top, broken plaster below."""
    poly = P.star(0.0, 0.0, size, size * rng.uniform(0.55, 0.9), rng.randint(5, 7), rng, rough=0.3, teeth=0.25)
    m = Matrix.Translation(Vector(center) + Vector((0, 0, thick / 2 + 0.002))) @ \
        Matrix.Rotation(rng.uniform(-tilt, tilt), 4, "X") @ Matrix.Rotation(rng.uniform(-tilt, tilt), 4, "Y") @ \
        Matrix.Rotation(rng.uniform(0, math.tau), 4, "Z")
    km.prism([poly], -thick / 2, thick / 2, axis="z", mat="kit_wall_inner", mat_back="kit_wall", side=(SIDE_N, finish_side, SIDE_N),
             mat_rim="kit_wall_inner", frame=m, uv_off=(rng.uniform(0, 3), rng.uniform(0, 3)))


def nail(km: KitMesh, pos, normal, rng: random.Random, *, mat: str = "metal_steel", head: float = 0.009,
         proud: float = 0.003) -> None:
    """Nail head sitting on a surface (pos on the surface, normal pointing out)."""
    n = Vector(normal).normalized()
    m, _ = board_frame(Vector(pos) - n * 0.001, Vector(pos) + n * proud, n.orthogonal())
    rot = Matrix.Rotation(rng.uniform(0, math.pi / 2), 4, "Z")
    km.box((-head / 2, -head / 2, 0.0), (head / 2, head / 2, proud + 0.001), mat, frame=m @ rot)


def glass_pane(km: KitMesh, x0: float, x1: float, z0: float, z1: float, yc: float = 0.0, *, t: float = 0.003,
               uv_rect: tuple | None = None) -> None:
    """Intact pane (two caps, edges hidden in the frame). UV0 spans the lite (or uv_rect) 0..1 so the
    glass texture's edge grime follows the frame."""
    gx0, gx1, gz0, gz1 = uv_rect or (x0, x1, z0, z1)
    uv = lambda p, n: ((p.x - gx0) / (gx1 - gx0), (p.z - gz0) / (gz1 - gz0))  # noqa: E731
    h = t / 2
    km.emit([(x0, yc - h, z0), (x1, yc - h, z0), (x1, yc - h, z1), (x0, yc - h, z1),
             (x0, yc + h, z0), (x1, yc + h, z0), (x1, yc + h, z1), (x0, yc + h, z1)],
            [([0, 1, 2, 3], "glass", "y", False), ([5, 4, 7, 6], "glass", "y", False)], uv_fn=uv)


def glass_shards(km: KitMesh, x0: float, x1: float, z0: float, z1: float, rng: random.Random, *, yc: float = 0.0,
                 uv_rect: tuple | None = None, t: float = 0.003, n_hole: int = 8, tuck: float = 0.004,
                 cracks: tuple[int, int] = (3, 4)) -> None:
    """Broken lite: jagged shards still stuck in the frame around a star-shaped hole, split by radial
    cracks. Shards are rimless double caps (3 mm glass edges are invisible)."""
    cx, cz = (x0 + x1) / 2 + rng.uniform(-0.15, 0.15) * (x1 - x0), (z0 + z1) / 2 + rng.uniform(-0.15, 0.15) * (z1 - z0)
    hole = P.star(cx, cz, (x1 - x0) * rng.uniform(0.25, 0.4), (z1 - z0) * rng.uniform(0.25, 0.4), n_hole, rng,
                  rough=0.35, teeth=0.5)
    outer = [(x0 - tuck, z0 - tuck), (x1 + tuck, z0 - tuck), (x1 + tuck, z1 + tuck), (x0 - tuck, z1 + tuck)]
    angles = sorted(rng.uniform(0, math.tau) for _ in range(rng.randint(*cracks)))
    gx0, gx1, gz0, gz1 = uv_rect or (x0, x1, z0, z1)
    uv = lambda p, n: ((p.x - gx0) / (gx1 - gx0), (p.z - gz0) / (gz1 - gz0))  # noqa: E731
    for pc in P.sector_split(outer, hole, (cx, cz), angles, arc_steps=1, gap=0.02):
        if rng.random() < 0.15:
            continue
        start = len(km.faces)
        km.prism([pc], yc - t / 2, yc + t / 2, axis="y", mat="glass", side=("y", "y", SIDE_N), rim_filter=lambda a, b: False)
        for f in km.faces[start:]:
            f.uvs = [uv(km.co[v], None) for v in f.verts]
