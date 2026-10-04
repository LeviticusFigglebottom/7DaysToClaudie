"""Vegetation mesh building blocks (runs inside Blender).

MeshBuilder accumulates vertices with per-vertex RGBA (written to the "Color" corner attribute,
see lib/vcolor.py for channel meanings), optional per-vertex custom normals, per-corner UVs and
per-face material slots, then turns everything into one Blender object in a single pass. It is
much faster and more controllable than bmesh/operators for the tens of thousands of elements a
tree needs, and keeps the result deterministic (no operators, no context).

Building blocks:
  tube()  generalized cylinder along a polyline (parallel-transport frames), bark UVs that keep
          the texel aspect ~1 as the radius changes, optional per-vertex radial noise, cap/tip.
  card()  foliage card mapped onto an atlas rect (Blender UV convention), bent along its length
          (droop), optionally folded along its midrib, with crown-style bent normals.
"""
from __future__ import annotations

import math

import bpy
from mathutils import Quaternion, Vector

from . import materials

UP = Vector((0.0, 0.0, 1.0))


class MeshBuilder:
    def __init__(self) -> None:
        self.co: list[tuple[float, float, float]] = []
        self.col: list[tuple[float, float, float, float]] = []
        self.nrm: list = []
        self.faces: list[tuple[int, ...]] = []
        self.uvs: list[tuple[tuple[float, float], ...]] = []
        self.fmat: list[int] = []
        self.mats: list[str] = []

    # -- elements -----------------------------------------------------------------------------
    def mat(self, mat_id: str) -> int:
        if mat_id not in self.mats:
            self.mats.append(mat_id)
        return self.mats.index(mat_id)

    def v(self, co, col=(1.0, 1.0, 1.0, 1.0), n=None) -> int:
        self.co.append((float(co[0]), float(co[1]), float(co[2])))
        self.col.append(tuple(float(c) for c in col))
        self.nrm.append(None if n is None else (float(n[0]), float(n[1]), float(n[2])))
        return len(self.co) - 1

    def f(self, idx, uv, mat: int) -> None:
        self.faces.append(tuple(idx))
        self.uvs.append(tuple((float(a), float(b)) for a, b in uv))
        self.fmat.append(mat)

    def tris(self) -> int:
        return sum(len(f) - 2 for f in self.faces)

    def extend(self, other: "MeshBuilder") -> None:
        off = len(self.co)
        remap = [self.mat(m) for m in other.mats]
        self.co += other.co
        self.col += other.col
        self.nrm += other.nrm
        self.faces += [tuple(i + off for i in f) for f in other.faces]
        self.uvs += other.uvs
        self.fmat += [remap[m] for m in other.fmat]

    def set_channel(self, ch: int, fn) -> None:
        """col[ch] = fn(index, co, col) for every vertex."""
        for i, (co, c) in enumerate(zip(self.co, self.col)):
            lst = list(c)
            lst[ch] = max(0.0, min(1.0, fn(i, co, c)))
            self.col[i] = tuple(lst)

    # -- output -------------------------------------------------------------------------------
    def build(self, name: str) -> bpy.types.Object:
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.co, [], self.faces)
        nloops = sum(len(f) for f in self.faces)
        assert len(me.polygons) == len(self.faces) and len(me.loops) == nloops, "degenerate faces dropped"
        uvl = me.uv_layers.new(name="UVMap")
        flat = [c for fuv in self.uvs for uv in fuv for c in uv]
        uvl.data.foreach_set("uv", flat)
        ca = me.color_attributes.new("Color", "BYTE_COLOR", "CORNER")
        cols = [c for f in self.faces for vi in f for c in self.col[vi]]
        ca.data.foreach_set("color", cols)
        me.color_attributes.active_color = ca
        try:
            me.color_attributes.render_color_index = me.color_attributes.find("Color")
        except AttributeError:
            pass
        for m in self.mats:
            me.materials.append(materials.material(m))
        me.polygons.foreach_set("material_index", self.fmat)
        me.polygons.foreach_set("use_smooth", [True] * len(self.faces))
        me.update()
        if any(n is not None for n in self.nrm):
            vn = [0.0] * (len(me.vertices) * 3)
            me.vertices.foreach_get("normal", vn)
            normals = []
            for i, n in enumerate(self.nrm):
                normals.append(n if n is not None else (vn[i * 3], vn[i * 3 + 1], vn[i * 3 + 2]))
            me.normals_split_custom_set_from_vertices(normals)
        obj = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(obj)
        return obj


# ---------------------------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------------------------

def frames(pts: list[Vector], up_hint: Vector | None = None) -> list[tuple[Vector, Vector, Vector]]:
    """Parallel-transport frames (tangent, normal, binormal) along a polyline."""
    n = len(pts)
    tans = []
    for i in range(n):
        a = pts[max(0, i - 1)]
        b = pts[min(n - 1, i + 1)]
        t = (b - a)
        tans.append(t.normalized() if t.length > 1e-9 else Vector((0, 0, 1)))
    hint = up_hint or UP
    nrm = hint - tans[0] * hint.dot(tans[0])
    if nrm.length < 1e-4:
        nrm = tans[0].orthogonal()
    nrm.normalize()
    out = []
    for i in range(n):
        if i > 0:
            q = tans[i - 1].rotation_difference(tans[i])
            nrm = q @ nrm
            nrm = (nrm - tans[i] * nrm.dot(tans[i])).normalized()
        out.append((tans[i], nrm, tans[i].cross(nrm)))
    return out


def tube(mb: MeshBuilder, pts: list[Vector], radii: list[float], sides: int, mat: str, *,
         u_repeats: float = 1.0, v_per_circ: float | None = None, v0: float = 0.0,
         col_fn=None, radius_fn=None, cap_start: bool = False, tip: bool = True, cap_end: bool = False,
         up_hint: Vector | None = None, phase: float = 0.0, end_cap_uv=None, end_mat: str | None = None):
    """Generalized cylinder. col_fn(i_ring, s_along, angle, pos) -> RGBA. radius_fn(i_ring, s, angle)
    -> multiplier for radial noise. UV: u wraps `u_repeats` times around; v advances by arc
    length * u_repeats / circumference (texel aspect ~1) unless v_per_circ overrides it.
    tip=True closes the end with a cone point; cap_end=True closes it with a flat cap instead
    (end_cap_uv: function(angle, rnorm) -> (u, v) for the cap face, e.g. an end-grain disc).
    Returns (rings: list[list[int]], v_end)."""
    m = mb.mat(mat)
    fr = frames(pts, up_hint)
    n = len(pts)
    total = sum((pts[i + 1] - pts[i]).length for i in range(n - 1)) or 1.0
    rings: list[list[int]] = []
    vcoords = []
    v = v0
    acc = 0.0
    for i in range(n):
        if i > 0:
            seg = (pts[i] - pts[i - 1]).length
            acc += seg
            rr = max(0.004, 0.5 * (radii[i] + radii[i - 1]))
            v += seg * (u_repeats / (2 * math.pi * rr) if v_per_circ is None else v_per_circ)
        vcoords.append(v)
        t, nn, bb = fr[i]
        s = acc / total
        ring = []
        for j in range(sides):
            a = 2 * math.pi * j / sides + phase
            rad = radii[i] * (radius_fn(i, s, a) if radius_fn else 1.0)
            off = nn * math.cos(a) + bb * math.sin(a)
            p = pts[i] + off * rad
            col = col_fn(i, s, a, p) if col_fn else (1.0, 1.0, 1.0, 1.0)
            ring.append(mb.v(p, col))
        rings.append(ring)
    for i in range(n - 1):
        for j in range(sides):
            j2 = (j + 1) % sides
            u0 = u_repeats * j / sides
            u1 = u_repeats * (j + 1) / sides
            mb.f((rings[i][j], rings[i][j2], rings[i + 1][j2], rings[i + 1][j]),
                 ((u0, vcoords[i]), (u1, vcoords[i]), (u1, vcoords[i + 1]), (u0, vcoords[i + 1])), m)
    if tip and not cap_end:
        t = fr[-1][0]
        tp = pts[-1] + t * max(radii[-1] * 2.5, 0.01)
        col = col_fn(n - 1, 1.0, 0.0, tp) if col_fn else (1.0, 1.0, 1.0, 1.0)
        ti = mb.v(tp, col)
        vt = vcoords[-1] + radii[-1] * 2.5 * u_repeats / (2 * math.pi * max(radii[-1], 0.004))
        for j in range(sides):
            j2 = (j + 1) % sides
            u0 = u_repeats * j / sides
            u1 = u_repeats * (j + 1) / sides
            mb.f((rings[-1][j], rings[-1][j2], ti), ((u0, vcoords[-1]), (u1, vcoords[-1]), ((u0 + u1) * 0.5, vt)), m)
    if cap_end:
        _cap(mb, rings[-1], pts[-1], fr[-1], sides, phase, end_mat or mat, end_cap_uv, flip=False, col_fn=col_fn,
             i_ring=n - 1)
    if cap_start:
        _cap(mb, rings[0], pts[0], fr[0], sides, phase, end_mat or mat, end_cap_uv, flip=True, col_fn=col_fn, i_ring=0)
    return rings, v


def _cap(mb, ring, center, frame, sides, phase, mat, uv_fn, flip, col_fn, i_ring):
    """Flat cap with its own vertices (hard edge) and a centre vertex (fan of triangles)."""
    m = mb.mat(mat)
    t, nn, bb = frame
    cidx = []
    for j in range(sides):
        cidx.append(mb.v(mb.co[ring[j]], mb.col[ring[j]]))
    col = col_fn(i_ring, 0.0 if flip else 1.0, 0.0, center) if col_fn else (1.0, 1.0, 1.0, 1.0)
    c = mb.v(center, col)

    def uv_of(j):
        a = 2 * math.pi * j / sides + phase
        if uv_fn is not None:
            return uv_fn(a, 1.0)
        return (0.5 + 0.5 * math.cos(a), 0.5 + 0.5 * math.sin(a))

    cuv = uv_fn(0.0, 0.0) if uv_fn is not None else (0.5, 0.5)
    for j in range(sides):
        j2 = (j + 1) % sides
        if flip:
            mb.f((cidx[j2], cidx[j], c), (uv_of(j2), uv_of(j), cuv), m)
        else:
            mb.f((cidx[j], cidx[j2], c), (uv_of(j), uv_of(j2), cuv), m)


def card(mb: MeshBuilder, base: Vector, direction: Vector, side: Vector, length: float, width: float,
         rect, mat: str, *, segs: int = 2, droop: float = 0.0, fold: float = 0.0, out: Vector | None = None,
         col_fn=None, normal_fn=None, mirror: bool = False, width_taper: float = 1.0, twist: float = 0.0) -> None:
    """Foliage card. `direction` runs from base to tip, `side` across the width. The front face
    (geometric normal side x direction) is turned towards `out` when given. droop bends the card
    towards -Z quadratically (fraction of its length). fold lifts the long edges by
    fold*width/2 along the front normal (negative = umbrella/convex). twist rolls the card
    progressively around its length axis (radians at the tip). col_fn(s, x) -> RGBA (s 0..1
    along, x -1..1 across). normal_fn(pos, front_normal) -> custom normal. rect = (u0, v0, u1,
    v1) atlas region; the texture's base is at v0, its tip at v1."""
    m = mb.mat(mat)
    d = direction.normalized()
    sd = (side - d * side.dot(d)).normalized()
    u0, v0, u1, v1 = rect
    if mirror:
        u0, u1 = u1, u0
    gn = sd.cross(d)
    if out is not None and gn.dot(out) < 0.0:
        sd = -sd
        u0, u1 = u1, u0
        gn = -gn
    xs = (-1.0, 0.0, 1.0) if fold != 0.0 else (-1.0, 1.0)
    rows = []
    for k in range(segs + 1):
        s = k / segs
        center = base + d * (length * s) + Vector((0.0, 0.0, -droop * length * s * s))
        w = width * (1.0 - (1.0 - width_taper) * s)
        sk = sd
        nk = gn
        if twist != 0.0:
            q = Quaternion(d, twist * s)
            sk = q @ sd
            nk = q @ gn
        row = []
        for x in xs:
            p = center + sk * (x * w * 0.5) + nk * (abs(x) * fold * w * 0.5)
            col = col_fn(s, x) if col_fn else (1.0, 1.0, 1.0, 1.0)
            n = normal_fn(p, nk) if normal_fn else None
            row.append(mb.v(p, col, n))
        rows.append((row, s))
    for k in range(segs):
        (ra, sa), (rb, sb) = rows[k], rows[k + 1]
        for c in range(len(xs) - 1):
            ua = u0 + (u1 - u0) * (xs[c] * 0.5 + 0.5)
            ub = u0 + (u1 - u0) * (xs[c + 1] * 0.5 + 0.5)
            va = v0 + (v1 - v0) * sa
            vb = v0 + (v1 - v0) * sb
            mb.f((ra[c], ra[c + 1], rb[c + 1], rb[c]), ((ua, va), (ub, va), (ub, vb), (ua, vb)), m)


def ribbon(mb: MeshBuilder, spine: list[Vector], sides: list[Vector], widths: list[float], rect, mat: str, *,
           fold: float = 0.0, out: Vector | None = None, col_fn=None, normal_fn=None) -> None:
    """Card strip along a curved spine (fronds, blades). sides[i] = unit across-vector at each
    spine point; widths[i] = full width. fold lifts the edges along the local front normal (V
    section). The texture rect runs v0 (spine start) -> v1 (spine end). col_fn(s, x) -> RGBA,
    normal_fn(pos, front_normal) -> custom normal. The front face is turned towards `out`."""
    m = mb.mat(mat)
    n = len(spine)
    u0, v0, u1, v1 = rect
    xs = (-1.0, 0.0, 1.0) if fold != 0.0 else (-1.0, 1.0)
    total = sum((spine[i + 1] - spine[i]).length for i in range(n - 1)) or 1.0
    flip = False
    if out is not None:
        d = (spine[-1] - spine[0])
        mid = n // 2
        gn = sides[mid].cross(d)
        flip = gn.dot(out) < 0.0
    rows = []
    acc = 0.0
    for i in range(n):
        if i > 0:
            acc += (spine[i] - spine[i - 1]).length
        s = acc / total
        t = (spine[min(n - 1, i + 1)] - spine[max(0, i - 1)]).normalized()
        sd = sides[i] - t * sides[i].dot(t)
        sd = sd.normalized() if sd.length > 1e-6 else t.orthogonal().normalized()
        if flip:
            sd = -sd
        gn = sd.cross(t).normalized()
        row = []
        for x in xs:
            p = spine[i] + sd * (x * widths[i] * 0.5) + gn * (abs(x) * fold * widths[i] * 0.5)
            col = col_fn(s, x) if col_fn else (1.0, 1.0, 1.0, 1.0)
            nn = normal_fn(p, gn) if normal_fn else None
            row.append(mb.v(p, col, nn))
        rows.append((row, s))
    uu = (u0, u1) if not flip else (u1, u0)
    for i in range(n - 1):
        (ra, sa), (rb, sb) = rows[i], rows[i + 1]
        for c in range(len(xs) - 1):
            ua = uu[0] + (uu[1] - uu[0]) * (xs[c] * 0.5 + 0.5)
            ub = uu[0] + (uu[1] - uu[0]) * (xs[c + 1] * 0.5 + 0.5)
            va = v0 + (v1 - v0) * sa
            vb = v0 + (v1 - v0) * sb
            mb.f((ra[c], ra[c + 1], rb[c + 1], rb[c]), ((ua, va), (ub, va), (ub, vb), (ua, vb)), m)


def remap_uvs(mb: MeshBuilder, f0: int, f1: int, rect) -> None:
    """Linearly squeezes the UVs of faces [f0, f1) into an atlas rect (u by the range used,
    v by the range used), e.g. to map stem tubes onto a stem strip of a foliage atlas."""
    if f1 <= f0:
        return
    us = [uv[0] for fu in mb.uvs[f0:f1] for uv in fu]
    vs = [uv[1] for fu in mb.uvs[f0:f1] for uv in fu]
    ua, ub, va, vb = min(us), max(us), min(vs), max(vs)
    u0, v0, u1, v1 = rect
    du, dv = max(ub - ua, 1e-6), max(vb - va, 1e-6)
    for i in range(f0, f1):
        mb.uvs[i] = tuple((u0 + (u1 - u0) * (u - ua) / du, v0 + (v1 - v0) * (v - va) / dv) for u, v in mb.uvs[i])


def rot_axis(v: Vector, axis: Vector, ang: float) -> Vector:
    return Quaternion(axis.normalized(), ang) @ v


def horiz(v: Vector) -> Vector:
    h = Vector((v.x, v.y, 0.0))
    return h.normalized() if h.length > 1e-6 else Vector((1.0, 0.0, 0.0))
