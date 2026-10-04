"""Building blocks for the exterior props family (generators/props_ext_*.py).

Workflow of a prop builder ``fn(ctx)``:
  1. Create parts with the primitives below (bmesh based, deterministic). Each part is built
     around the origin, UV-mapped in its own frame, then placed with ``place()`` (so wood grain
     and texture follow the part when it is rotated).
  2. Register each part with ``ctx.add(obj, material, ...)``: assigns ``M_<material>``, UVs,
     smoothing and the per-part vertex colour channels G (wear) and B (moss / variation).
  3. Register collision proxies with ``ctx.col_box`` / ``ctx.col_hull``.
``run()`` builds one GLB per condition (clean / worn / destroyed): fresh scene, same shape seed
(``ctx.rnd(key)`` streams are keyed, not sequential), joins the parts, bakes vertex AO (R),
enforces the conventions (front -Y, origin bottom centre, metres) and exports.

Atlas regions (Blender UV rects u0, v0, u1, v1 — v up) for the non-tiling textures:
  paint_red_sign  : ATLAS_SIGN[...]   stop / blank, clean / worn
  paper_trash     : ATLAS_PAPER[...]  news / note / kraft / flyer
  plywood_marks   : ATLAS_PLY[...]    plain / x / arrow / tally
"""
from __future__ import annotations

import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector, noise

from . import common, export, materials, vcolor

# --------------------------------------------------------------------------------------------
# Atlas rects (image cell (col, row) from the top-left -> Blender UV rect)
# --------------------------------------------------------------------------------------------

def _cell(col: int, row: int, n: int = 2, pad: float = 0.0) -> tuple[float, float, float, float]:
    s = 1.0 / n
    return (col * s + pad, 1.0 - (row + 1) * s + pad, (col + 1) * s - pad, 1.0 - row * s - pad)


ATLAS_SIGN = {"stop": _cell(0, 0), "blank": _cell(1, 0), "stop_worn": _cell(0, 1), "blank_worn": _cell(1, 1)}
ATLAS_PAPER = {"news": _cell(0, 0), "note": _cell(1, 0), "kraft": _cell(0, 1), "flyer": _cell(1, 1)}
ATLAS_PLY = {"plain": _cell(0, 0), "x": _cell(1, 0), "arrow": _cell(0, 1), "tally": _cell(1, 1)}

# Blender-only preview colours (dev_preview / Cycles); Godot swaps in the real materials.
materials.PREVIEW_COLORS.update({
    "car_paint_red": (0.25, 0.04, 0.03), "car_paint_blue": (0.05, 0.09, 0.2), "car_paint_green": (0.06, 0.13, 0.08),
    "car_paint_tan": (0.4, 0.33, 0.22), "car_paint_white": (0.6, 0.6, 0.58), "car_paint_brown": (0.2, 0.1, 0.05),
    "car_rust": (0.3, 0.12, 0.04), "car_burnt": (0.05, 0.045, 0.04), "underbody": (0.07, 0.05, 0.04),
    "tyre_rubber": (0.03, 0.03, 0.03), "chrome_pitted": (0.6, 0.6, 0.6), "window_grime": (0.03, 0.04, 0.05),
    "plastic_black": (0.03, 0.03, 0.03), "car_upholstery": (0.12, 0.1, 0.08), "lens_red": (0.35, 0.02, 0.02),
    "lens_amber": (0.5, 0.25, 0.02), "lens_clear": (0.5, 0.52, 0.5), "cardboard": (0.35, 0.22, 0.11),
    "cardboard_wet": (0.22, 0.14, 0.07), "packing_tape": (0.45, 0.33, 0.18), "plastic_bag_black": (0.02, 0.02, 0.02),
    "plastic_bag_green": (0.04, 0.08, 0.04), "wood_weathered": (0.3, 0.28, 0.25), "wood_fresh": (0.45, 0.33, 0.2),
    "wood_creosote": (0.12, 0.08, 0.05), "wood_charred": (0.03, 0.03, 0.03), "metal_galvanized": (0.45, 0.46, 0.46),
    "concrete_barrier": (0.4, 0.4, 0.38), "paint_red_sign": (0.4, 0.05, 0.04), "plywood_marks": (0.4, 0.32, 0.2),
    "corpse_skin": (0.15, 0.12, 0.08), "corpse_bone": (0.45, 0.4, 0.3), "blood_dried": (0.08, 0.01, 0.01),
    "ash_burnt": (0.04, 0.04, 0.04), "paper_trash": (0.6, 0.58, 0.5),
})


# --------------------------------------------------------------------------------------------
# Small math helpers
# --------------------------------------------------------------------------------------------

def V(*a) -> Vector:
    return Vector(a[0]) if len(a) == 1 else Vector(a)


def smooth01(e0: float, e1: float, x: float) -> float:
    return common.smoothstep(e0, e1, x)


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if x < lo else hi if x > hi else x


def rot_matrix(rot: tuple[float, float, float] | None) -> Matrix:
    """XYZ Euler in degrees -> 4x4."""
    if rot is None:
        return Matrix.Identity(4)
    from mathutils import Euler
    return Euler(tuple(math.radians(a) for a in rot), "XYZ").to_matrix().to_4x4()


def place(obj: bpy.types.Object, loc=(0, 0, 0), rot=None, scale=None) -> bpy.types.Object:
    """Bake a transform into the mesh (parts stay at identity object transforms)."""
    m = Matrix.Translation(Vector(loc)) @ rot_matrix(rot)
    if scale is not None:
        s = scale if isinstance(scale, (tuple, list)) else (scale, scale, scale)
        m = m @ Matrix.Diagonal((*s, 1.0))
    obj.data.transform(m)
    obj.data.update()
    return obj


AXES = {"x": Vector((1, 0, 0)), "-x": Vector((-1, 0, 0)), "y": Vector((0, 1, 0)), "-y": Vector((0, -1, 0)),
        "z": Vector((0, 0, 1)), "-z": Vector((0, 0, -1))}


def orient(obj: bpy.types.Object, long, normal, loc=(0, 0, 0)) -> bpy.types.Object:
    """Rotates a part built along X (thickness along Z) so local X -> `long` and local Z ->
    `normal` (axis names 'x', '-y', ... or vectors), then moves it to `loc`."""
    a = (AXES[long] if isinstance(long, str) else Vector(long)).normalized()
    n = (AXES[normal] if isinstance(normal, str) else Vector(normal)).normalized()
    n = (n - a * n.dot(a)).normalized()
    b = n.cross(a)
    m = Matrix((
        (a.x, b.x, n.x, 0.0),
        (a.y, b.y, n.y, 0.0),
        (a.z, b.z, n.z, 0.0),
        (0.0, 0.0, 0.0, 1.0)))
    obj.data.transform(Matrix.Translation(Vector(loc)) @ m)
    obj.data.update()
    return obj


def canon_bm(bm: bmesh.types.BMesh) -> None:
    """Puts verts, edges and faces into a geometry-defined order. Several bmesh operators
    (extrude_face_region, bisect_plane, convex_hull, subdivide_edges) and the boolean modifier emit
    new elements in pointer-hash / thread order, which differs from run to run. Sorting keeps the
    exported GLBs byte-identical and makes later order-dependent steps (hulls, decimation, loops
    that draw random numbers per element) reproducible."""
    def vkey(v):
        return (tuple(v.co), tuple(sorted(tuple(e.other_vert(v).co) for e in v.link_edges)))

    def reorder(seq, key):
        # BMElemSeq.sort() only takes numeric keys: rank in Python, then sort by index.
        for i, el in enumerate(sorted(seq, key=key)):
            el.index = i
        seq.sort()
        seq.index_update()
    reorder(bm.verts, vkey)
    reorder(bm.edges, lambda e: tuple(sorted((e.verts[0].index, e.verts[1].index))))
    reorder(bm.faces, lambda f: (f.material_index, tuple(sorted(v.index for v in f.verts)),
                                 tuple(v.index for v in f.verts)))


_ATTR_FMT = {"FLOAT": ("value", 1, 0.0), "INT": ("value", 1, 0), "BOOLEAN": ("value", 1, False),
             "INT8": ("value", 1, 0), "FLOAT2": ("vector", 2, 0.0), "INT32_2D": ("value", 2, 0),
             "FLOAT_VECTOR": ("vector", 3, 0.0), "FLOAT_COLOR": ("color", 4, 0.0),
             "BYTE_COLOR": ("color", 4, 0.0), "QUATERNION": ("value", 4, 0.0)}


def canon_loops(me: bpy.types.Mesh) -> None:
    """Starts every face at its lowest-index vertex (winding kept). Booleans and some bmesh
    operators pick a face's first corner arbitrarily; the corner order decides the exported vertex
    order and which diagonal a quad is split along."""
    nl = len(me.loops)
    if not me.polygons:
        return
    starts = [0] * len(me.polygons)
    totals = [0] * len(me.polygons)
    me.polygons.foreach_get("loop_start", starts)
    me.polygons.foreach_get("loop_total", totals)
    cv = [0] * nl
    me.loops.foreach_get("vertex_index", cv)
    perm = None
    for s, t in zip(starts, totals):
        seg = cv[s:s + t]
        k = seg.index(min(seg))
        if k:
            if perm is None:
                perm = list(range(nl))
            perm[s:s + t] = [s + (k + i) % t for i in range(t)]
    if perm is None:
        return
    ce = [0] * nl
    me.loops.foreach_get("edge_index", ce)
    me.loops.foreach_set("vertex_index", [cv[p] for p in perm])
    me.loops.foreach_set("edge_index", [ce[p] for p in perm])
    for a in me.attributes:
        if a.domain != "CORNER" or a.name.startswith(".corner_") or a.data_type not in _ATTR_FMT:
            continue
        prop, w, zero = _ATTR_FMT[a.data_type]
        vals = [zero] * (nl * w)
        a.data.foreach_get(prop, vals)
        a.data.foreach_set(prop, [vals[p * w + c] for p in perm for c in range(w)])
    me.update()


def canon(obj: bpy.types.Object) -> bpy.types.Object:
    """canon_bm() + canon_loops() for an object's mesh (after modifiers / joins)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    return write_bm(bm, obj)


def write_bm(bm: bmesh.types.BMesh, obj: bpy.types.Object) -> bpy.types.Object:
    """Canonical order, then back into the object's mesh; frees the bmesh."""
    canon_bm(bm)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    canon_loops(obj.data)
    return obj


def _obj(name: str, bm: bmesh.types.BMesh) -> bpy.types.Object:
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    canon_bm(bm)
    o = common.mesh_from_bmesh(name, bm)
    canon_loops(o.data)
    return o


def _obj_raw(name: str, bm: bmesh.types.BMesh) -> bpy.types.Object:
    """Like _obj but keeps the face winding as built (for open sheets / deliberate normals)."""
    canon_bm(bm)
    o = common.mesh_from_bmesh(name, bm)
    canon_loops(o.data)
    return o


# --------------------------------------------------------------------------------------------
# Primitives (all return a new Object with identity transform; mesh in metres)
# --------------------------------------------------------------------------------------------

def slice_at(bm: bmesh.types.BMesh, axis: int, value: float) -> None:
    """Edge loop where the axis-aligned plane coord[axis] == value cuts the mesh. The new vertices
    are snapped onto the plane: bisect_plane interpolates along each edge from its first vertex,
    so the result otherwise depends (in the last bit) on edge orientation."""
    co = Vector((0, 0, 0))
    co[axis] = value
    no = Vector((0, 0, 0))
    no[axis] = 1.0
    geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
    res = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no)
    for g in res["geom_cut"]:
        if isinstance(g, bmesh.types.BMVert):
            g.co[axis] = value


def _slice_bm(bm: bmesh.types.BMesh, axis: int, cuts: int) -> None:
    if cuts <= 0:
        return
    vs = [v.co[axis] for v in bm.verts]
    lo, hi = min(vs), max(vs)
    for k in range(1, cuts + 1):
        slice_at(bm, axis, lo + (hi - lo) * k / (cuts + 1))


def box(name: str, size, center=(0, 0, 0), *, bevel: float = 0.0, bevel_segs: int = 1,
        cuts: tuple[int, int, int] = (0, 0, 0)) -> bpy.types.Object:
    """Axis-aligned box (optionally bevelled; `cuts` adds edge loops per axis for wear/deforms)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    if bevel > 0.0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=min(bevel, min(size) * 0.49), segments=bevel_segs,
                        affect="EDGES", profile=0.5)
    for ax in range(3):
        _slice_bm(bm, ax, cuts[ax])
    bmesh.ops.translate(bm, vec=Vector(center), verts=bm.verts)
    return _obj(name, bm)


def cyl(name: str, r: float, h: float, *, segs: int = 12, center=(0, 0, 0), axis: str = "Z",
        r_top: float | None = None, caps: bool = True, cuts: int = 0, bevel: float = 0.0) -> bpy.types.Object:
    """Cylinder/cone centred at `center` along `axis`."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=caps, cap_tris=False, segments=segs, radius1=r,
                          radius2=r if r_top is None else r_top, depth=h)
    if bevel > 0 and caps:
        cap_edges = [e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-6 and abs(abs(e.verts[0].co.z) - h / 2) < 1e-6]
        bmesh.ops.bevel(bm, geom=cap_edges, offset=bevel, segments=1, affect="EDGES", profile=0.5)
    _slice_bm(bm, 2, cuts)
    if axis == "X":
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "Y"))
    elif axis == "Y":
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "X"))
    bmesh.ops.translate(bm, vec=Vector(center), verts=bm.verts)
    return _obj(name, bm)


def lathe(name: str, profile: list[tuple[float, float]], *, segs: int = 16, cap_bottom: bool = True,
          cap_top: bool = True, angle0: float = 0.0, arc: float = 2 * math.pi,
          close_profile: bool = False) -> bpy.types.Object:
    """Surface of revolution around Z from (radius, z) points listed bottom -> top.
    Radius 0 points collapse to a pole (no degenerate quads). close_profile sweeps a closed
    cross-section (torus-like: tyres, hoses, rims) — no caps."""
    if close_profile:
        return _lathe_closed(name, profile, segs)
    bm = bmesh.new()
    full = abs(arc - 2 * math.pi) < 1e-6
    n = segs if full else segs + 1
    rings = []
    for r, z in profile:
        if r < 1e-6:
            rings.append([bm.verts.new((0.0, 0.0, z))])
            continue
        ring = []
        for i in range(n):
            a = angle0 + arc * i / segs
            ring.append(bm.verts.new((r * math.cos(a), r * math.sin(a), z)))
        rings.append(ring)
    for a, b in zip(rings[:-1], rings[1:]):
        for i in range(segs):
            j = (i + 1) % n if full else i + 1
            if len(a) == 1 and len(b) == 1:
                continue
            if len(a) == 1:
                bm.faces.new((a[0], b[i], b[j]))
            elif len(b) == 1:
                bm.faces.new((a[i], a[j], b[0]))
            else:
                bm.faces.new((a[i], a[j], b[j], b[i]))
    if full and cap_bottom and len(rings[0]) > 1:
        bm.faces.new(list(reversed(rings[0])))
    if full and cap_top and len(rings[-1]) > 1:
        bm.faces.new(rings[-1])
    return _obj(name, bm)


def _lathe_closed(name: str, profile: list[tuple[float, float]], segs: int) -> bpy.types.Object:
    bm = bmesh.new()
    rings = []
    for r, z in profile:
        rings.append([bm.verts.new((r * math.cos(math.tau * i / segs), r * math.sin(math.tau * i / segs), z))
                      for i in range(segs)])
    n = len(rings)
    for k in range(n):
        a, b = rings[k], rings[(k + 1) % n]
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new((a[i], a[j], b[j], b[i]))
    return _obj(name, bm)


def _frames(points: list[Vector]) -> list[tuple[Vector, Vector, Vector]]:
    """Parallel-transport frames (tangent, normal, binormal) along a polyline."""
    tans = []
    for i in range(len(points)):
        if i == 0:
            t = points[1] - points[0]
        elif i == len(points) - 1:
            t = points[-1] - points[-2]
        else:
            t = (points[i + 1] - points[i]).normalized() + (points[i] - points[i - 1]).normalized()
        tans.append(t.normalized())
    up = Vector((0, 0, 1)) if abs(tans[0].z) < 0.9 else Vector((1, 0, 0))
    n = tans[0].cross(up).normalized()
    out = []
    for i, t in enumerate(tans):
        if i > 0:
            n = n - t * n.dot(t)
            if n.length < 1e-6:
                n = t.orthogonal()
            n.normalize()
        b = t.cross(n).normalized()
        out.append((t, n, b))
    return out


def tube(name: str, points, radius: float | list[float], *, segs: int = 8, caps: bool = True,
         closed: bool = False, flat: tuple[float, float] | None = None) -> bpy.types.Object:
    """Sweeps a circle (or ellipse `flat`=(rx_scale, ry_scale)) along a polyline. radius may vary
    per point. closed=True joins the last ring back to the first (hoops, rims)."""
    pts = [Vector(p) for p in points]
    radii = list(radius) if isinstance(radius, (list, tuple)) else [radius] * len(pts)
    if closed:
        n = len(pts)
        c = sum(pts, Vector()) / n
        pn = Vector()
        for i in range(n):
            pn += (pts[i] - c).cross(pts[(i + 1) % n] - c)
        pn = pn.normalized() if pn.length > 1e-9 else Vector((0, 0, 1))
        frames = []
        for i in range(n):
            t = (pts[(i + 1) % n] - pts[i - 1]).normalized()
            b = pn - t * pn.dot(t)
            b = b.normalized() if b.length > 1e-9 else t.orthogonal().normalized()
            frames.append((t, b.cross(t).normalized(), b))
    else:
        frames = _frames(pts)
    bm = bmesh.new()
    rings = []
    sx, sy = flat if flat else (1.0, 1.0)
    for p, (t, n, b), r in zip(pts, frames, radii):
        ring = []
        for i in range(segs):
            a = 2 * math.pi * i / segs
            ring.append(bm.verts.new(p + (n * math.cos(a) * sx + b * math.sin(a) * sy) * r))
        rings.append(ring)
    pairs = list(zip(rings[:-1], rings[1:]))
    if closed:
        pairs.append((rings[-1], rings[0]))
    for ra, rb in pairs:
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new((ra[i], ra[j], rb[j], rb[i]))
    if caps and not closed:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    return _obj(name, bm)


def sweep(name: str, points, profile: list[tuple[float, float]], *, caps: bool = True, up=(0, 0, 1),
          scale: list[float] | None = None) -> bpy.types.Object:
    """Sweeps a closed 2D profile (x = lateral, y = up, CCW) along a polyline; the lateral axis is
    path_tangent x up (bumpers, trim strips, rails). scale: optional per-point profile scale."""
    pts = [Vector(p) for p in points]
    u = Vector(up).normalized()
    bm = bmesh.new()
    rings = []
    for i, p in enumerate(pts):
        if i == 0:
            t = pts[1] - pts[0]
        elif i == len(pts) - 1:
            t = pts[-1] - pts[-2]
        else:
            t = (pts[i + 1] - pts[i]).normalized() + (pts[i] - pts[i - 1]).normalized()
        t.normalize()
        lat = t.cross(u)
        lat = lat.normalized() if lat.length > 1e-6 else t.orthogonal().normalized()
        upv = lat.cross(t).normalized()
        s = scale[i] if scale else 1.0
        rings.append([bm.verts.new(p + lat * a * s + upv * b * s) for a, b in profile])
    n = len(profile)
    for ra, rb in zip(rings[:-1], rings[1:]):
        for k in range(n):
            j = (k + 1) % n
            bm.faces.new((ra[k], ra[j], rb[j], rb[k]))
    if caps:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    return _obj(name, bm)


def prism(name: str, poly: list[tuple[float, float]], depth: float, *, plane: str = "XZ",
          offset: float = 0.0, bevel: float = 0.0) -> bpy.types.Object:
    """Extrudes a 2D outline (CCW) by `depth`. plane 'XZ': outline in (x, z), extruded along +Y
    centred on y=offset; 'YZ': outline in (y, z) along X; 'XY': outline in (x, y) along Z from offset."""
    bm = bmesh.new()
    vs = []
    for a, b in poly:
        if plane == "XZ":
            vs.append(bm.verts.new((a, offset - depth / 2, b)))
        elif plane == "YZ":
            vs.append(bm.verts.new((offset - depth / 2, a, b)))
        else:
            vs.append(bm.verts.new((a, b, offset)))
    bm.faces.new(vs)
    d = {"XZ": Vector((0, depth, 0)), "YZ": Vector((depth, 0, 0)), "XY": Vector((0, 0, depth))}[plane]
    # Side walls built explicitly: extrude_face_region creates them (and orients their edges) in
    # hash order, which leaks into later bisects as last-bit coordinate differences.
    top = [bm.verts.new(v.co + d) for v in vs]
    bm.faces.new(list(reversed(top)))
    for i in range(len(vs)):
        j = (i + 1) % len(vs)
        bm.faces.new((vs[j], vs[i], top[i], top[j]))
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=1, affect="EDGES", profile=0.5,
                        clamp_overlap=True)
    return _obj(name, bm)


def loft(name: str, rings: list[list[tuple[float, float, float]]], *, closed_ring: bool = True,
         cap_start: bool = True, cap_end: bool = True, recalc: bool = True) -> bpy.types.Object:
    """Bridges consecutive rings (equal vertex counts) with quads; optional n-gon caps."""
    bm = bmesh.new()
    rv = [[bm.verts.new(Vector(p)) for p in ring] for ring in rings]
    n = len(rv[0])
    for a, b in zip(rv[:-1], rv[1:]):
        for i in range(n if closed_ring else n - 1):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i]))
    if cap_start and closed_ring:
        bm.faces.new(list(reversed(rv[0])))
    if cap_end and closed_ring:
        bm.faces.new(rv[-1])
    return _obj(name, bm) if recalc else _obj_raw(name, bm)


def grid(name: str, w: float, h: float, nx: int, ny: int, *, center=(0, 0, 0)) -> bpy.types.Object:
    """Subdivided XY plane facing +Z (cloth, paper, tarp, mattress ... to be deformed)."""
    bm = bmesh.new()
    vs = [[bm.verts.new((center[0] - w / 2 + w * i / nx, center[1] - h / 2 + h * j / ny, center[2]))
           for i in range(nx + 1)] for j in range(ny + 1)]
    for j in range(ny):
        for i in range(nx):
            bm.faces.new((vs[j][i], vs[j][i + 1], vs[j + 1][i + 1], vs[j + 1][i]))
    return _obj_raw(name, bm)


def quad_sheet(name: str, p0, p1, p2, p3, nu: int = 1, nv: int = 1, *, thickness: float = 0.0) -> bpy.types.Object:
    """Bilinear grid between corners p0 (u0,v0) p1 (u1,v0) p2 (u1,v1) p3 (u0,v1); optional
    solidify. UVs: u along p0->p1, v along p0->p3, in metres (box-like but follows the sheet)."""
    P = [Vector(p) for p in (p0, p1, p2, p3)]
    bm = bmesh.new()
    vs = []
    for j in range(nv + 1):
        t = j / nv
        row = []
        for i in range(nu + 1):
            s = i / nu
            row.append(bm.verts.new(P[0].lerp(P[1], s).lerp(P[3].lerp(P[2], s), t)))
        vs.append(row)
    faces = []
    for j in range(nv):
        for i in range(nu):
            faces.append(bm.faces.new((vs[j][i], vs[j][i + 1], vs[j + 1][i + 1], vs[j + 1][i])))
    uvl = bm.loops.layers.uv.new("UVMap")
    eu = (P[1] - P[0]).normalized()
    ev = (P[3] - P[0]).normalized()
    for f in faces:
        for loop in f.loops:
            d = loop.vert.co - P[0]
            loop[uvl].uv = (d.dot(eu), d.dot(ev))
    o = _obj_raw(name, bm)
    if thickness > 0:
        solidify(o, thickness, offset=-1.0)
    return o


def blob(name: str, radius: float, *, subdiv: int = 2, scale=(1, 1, 1), center=(0, 0, 0),
         rough: float = 0.0, seed: int = 0, noise_scale: float = 2.0) -> bpy.types.Object:
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=radius)
    noise.seed_set(seed % 100000)
    off = Vector((seed * 0.37 % 50, seed * 0.61 % 50, seed * 0.83 % 50))
    for v in bm.verts:
        d = v.co.normalized()
        k = 1.0 + rough * noise.noise(d * noise_scale + off)
        v.co = Vector((d.x * scale[0], d.y * scale[1], d.z * scale[2])) * radius * k
    bmesh.ops.translate(bm, vec=Vector(center), verts=bm.verts)
    return _obj(name, bm)


def chunk(name: str, size: float, r: random.Random, *, n: int = 12, flat: float = 1.0,
          elong: float = 1.0) -> bpy.types.Object:
    """Irregular convex rubble chunk from a random point hull (plaster, concrete, brick bits)."""
    bm = bmesh.new()
    pts = []
    for _ in range(n):
        d = Vector((r.gauss(0, 1), r.gauss(0, 1), r.gauss(0, 1))).normalized()
        k = r.uniform(0.55, 1.0)
        pts.append(bm.verts.new((d.x * size * 0.5 * k * elong, d.y * size * 0.5 * k, d.z * size * 0.5 * k * flat)))
    bmesh.ops.convex_hull(bm, input=pts, use_existing_faces=False)
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    return _obj(name, bm)


def hull_of(name: str, points) -> bpy.types.Object:
    bm = bmesh.new()
    vs = [bm.verts.new(Vector(p)) for p in points]
    bmesh.ops.convex_hull(bm, input=vs, use_existing_faces=False)
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    return _obj(name, bm)


def solidify(obj: bpy.types.Object, thickness: float, *, offset: float = -1.0, mat_offset: int = 0,
             mat_offset_rim: int = 0, even: bool = True) -> bpy.types.Object:
    """Gives a sheet thickness. mat_offset shifts the material slot of the inner (back) shell, e.g.
    a lining on the underside of a fabric layer. even=False for sheets with folded-over (180 deg)
    creases, where even-thickness offsets explode into spikes."""
    m = obj.modifiers.new("solid", "SOLIDIFY")
    m.thickness = thickness
    m.offset = offset
    m.use_even_offset = even
    m.material_offset = mat_offset
    m.material_offset_rim = mat_offset_rim
    common.apply_modifiers(obj)
    return canon(obj)


def subdivide(obj: bpy.types.Object, cuts: int = 1, smooth: float = 0.0) -> bpy.types.Object:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.subdivide_edges(bm, edges=list(bm.edges), cuts=cuts, use_grid_fill=True, smooth=smooth)
    return write_bm(bm, obj)


def triangulate(obj: bpy.types.Object) -> bpy.types.Object:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    return write_bm(bm, obj)


def bisect(obj: bpy.types.Object, co, no) -> bpy.types.Object:
    """Adds an edge loop where the plane cuts the mesh (nothing removed): clean creases/folds."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=Vector(co), plane_no=Vector(no))
    return write_bm(bm, obj)


def cut_plane(obj: bpy.types.Object, co, no, *, keep: str = "below", fill: bool = True) -> bpy.types.Object:
    """Bisects the mesh and deletes one side ('below' keeps the side opposite `no`)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
    res = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=Vector(co), plane_no=Vector(no),
                                 clear_outer=keep == "below", clear_inner=keep == "above")
    if fill:
        edges = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
        if edges:
            bmesh.ops.holes_fill(bm, edges=edges, sides=0)
    return write_bm(bm, obj)


def delete_faces(obj: bpy.types.Object, pred) -> bpy.types.Object:
    """Deletes faces where pred(face_center: Vector, normal: Vector) is True."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    kill = [f for f in bm.faces if pred(f.calc_center_median(), f.normal)]
    if kill:
        bmesh.ops.delete(bm, geom=kill, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    return write_bm(bm, obj)


def duplicate(obj: bpy.types.Object, name: str) -> bpy.types.Object:
    me = obj.data.copy()
    me.name = name
    return common.new_object(name, me)


def remove(obj: bpy.types.Object) -> None:
    """Deletes an object. Refreshes the view layer: a removed object otherwise lingers as a None
    entry in view_layer.objects and breaks common.set_active()/join()."""
    me = obj.data if obj.type == "MESH" else None
    bpy.data.objects.remove(obj, do_unlink=True)
    if me is not None and me.users == 0:
        bpy.data.meshes.remove(me)
    bpy.context.view_layer.update()


def merge_parts(objs: list[bpy.types.Object], name: str) -> bpy.types.Object:
    """Joins raw parts (same material) into one object before ctx.add()."""
    objs = [o for o in objs if o is not None]
    if len(objs) == 1:
        objs[0].name = name
        return objs[0]
    return common.join(objs, name)


# --------------------------------------------------------------------------------------------
# Deformers (operate on mesh data in place)
# --------------------------------------------------------------------------------------------

def noise_disp(obj, amount: float, scale: float = 2.0, seed: int = 0, *, along_normal: bool = True,
               mask=None, octaves: int = 2) -> None:
    noise.seed_set(seed % 100000)
    me = obj.data
    me.update()
    off = Vector((seed * 0.731 % 61, seed * 0.379 % 59, seed * 0.517 % 53))
    for v in me.vertices:
        w = 1.0 if mask is None else mask(v.co)
        if w <= 0:
            continue
        p = v.co * scale + off
        if along_normal:
            n = noise.fractal(p, 0.5, 2.0, octaves, noise_basis="PERLIN_ORIGINAL")
            v.co += v.normal * n * amount * w
        else:
            d = noise.noise_vector(p, noise_basis="PERLIN_ORIGINAL")
            v.co += Vector(d) * amount * w
    me.update()


def crumple(obj, amount: float, scale: float = 6.0, seed: int = 0, mask=None) -> None:
    """Vector-noise displacement (crushed cans, cardboard, bags, sheet metal)."""
    noise_disp(obj, amount, scale, seed, along_normal=False, mask=mask)


def dent(obj, center, radius: float, depth: float, direction=None) -> None:
    """Pushes vertices within `radius` of `center` along `direction` (default: toward the centre's
    inside, i.e. opposite the average normal). Smooth cosine falloff."""
    c = Vector(center)
    me = obj.data
    me.update()
    d = Vector(direction).normalized() if direction is not None else None
    for v in me.vertices:
        dist = (v.co - c).length
        if dist >= radius:
            continue
        f = 0.5 + 0.5 * math.cos(math.pi * dist / radius)
        dirv = d if d is not None else -v.normal
        v.co += dirv * depth * f
    me.update()


def bend(obj, axis: int, amount: float, *, along: int = 2, origin: float = 0.0) -> None:
    """Quadratic bend: offset along `axis` grows with (coord[along]-origin)^2 * amount."""
    for v in obj.data.vertices:
        t = v.co[along] - origin
        v.co[axis] += amount * t * t
    obj.data.update()


def kink(objs, pivot, rot, *, axis: int = 2, blend: float = 0.06) -> None:
    """Bends everything above pivot[axis] about `pivot` by Euler `rot` (deg); geometry below stays
    put and a short blend zone keeps tubes/posts connected (impact-bent posts, folded poles)."""
    p = Vector(pivot)
    m = Matrix.Translation(p) @ rot_matrix(rot) @ Matrix.Translation(-p)
    for o in objs if isinstance(objs, (list, tuple)) else [objs]:
        for v in o.data.vertices:
            d = v.co[axis] - p[axis]
            if d <= 0:
                continue
            t = min(1.0, d / blend) if blend > 0 else 1.0
            v.co = v.co.lerp(m @ v.co, t)
        o.data.update()


def taper(obj, axis_from: int, factor_fn) -> None:
    """Scales the two other axes by factor_fn(coord[axis_from])."""
    others = [i for i in range(3) if i != axis_from]
    for v in obj.data.vertices:
        f = factor_fn(v.co[axis_from])
        for i in others:
            v.co[i] *= f
    obj.data.update()


def map_verts(obj, fn) -> None:
    """v.co = fn(co: Vector) -> Vector for every vertex."""
    for v in obj.data.vertices:
        v.co = fn(v.co.copy())
    obj.data.update()


def settle(obj, ground: float = 0.0, *, squash: float = 0.25) -> None:
    """Soft ground clamp: vertices below `ground` are pushed up and flattened (cloth/bags on floors)."""
    for v in obj.data.vertices:
        if v.co.z < ground:
            v.co.z = ground + (v.co.z - ground) * squash * 0.1
    obj.data.update()


def drop_to_ground(obj, ground: float = 0.0) -> None:
    zmin = min(v.co.z for v in obj.data.vertices)
    obj.data.transform(Matrix.Translation((0, 0, ground - zmin)))
    obj.data.update()


def lift_min(obj, ground: float = 0.0) -> None:
    """Raises the part only if it dips below `ground` (fallen debris resting on the floor)."""
    zmin = min(v.co.z for v in obj.data.vertices)
    if zmin < ground:
        obj.data.transform(Matrix.Translation((0, 0, ground - zmin)))
        obj.data.update()


def jagged_hole(obj, center, radius: float, seed: int, *, axis: int = 1, jag: float = 0.35) -> None:
    """Deletes faces of a (subdivided) sheet inside an irregular radius around `center`, measured
    in the plane perpendicular to `axis` — broken glass, torn cardboard, punched sheet metal."""
    c = Vector(center)
    r = random.Random(seed)
    lobes = [(r.uniform(0, math.tau), r.uniform(0.0, jag), r.randint(2, 6)) for _ in range(4)]
    others = [i for i in range(3) if i != axis]

    def inside(p, _n):
        dx, dy = p[others[0]] - c[others[0]], p[others[1]] - c[others[1]]
        a = math.atan2(dy, dx)
        k = 1.0 + sum(amp * math.sin(f * a + ph) for ph, amp, f in lobes)
        return math.hypot(dx, dy) < radius * k
    delete_faces(obj, inside)


# --------------------------------------------------------------------------------------------
# UV projection (part-local, metre scaled)
# --------------------------------------------------------------------------------------------

def _uvl(me):
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    return me.uv_layers.active


def uv_box(obj, scale: float = 1.0, *, long_axis: int | None = None, offset=(0.0, 0.0)) -> None:
    """Per-face dominant-axis projection. With long_axis, side faces map u along that axis
    (wood grain / brushed direction follows the part), end faces use the other two axes."""
    me = obj.data
    uvl = _uvl(me)
    ou, ov = offset
    for p in me.polygons:
        n = p.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if long_axis is not None and ax != long_axis:
                other = 3 - ax - long_axis
                u, v = co[long_axis], co[other]
            elif long_axis is not None:
                a1, a2 = [i for i in range(3) if i != ax]
                u, v = co[a1], co[a2]
            elif ax == 0:
                u, v = (co.y if n.x > 0 else -co.y), co.z
            elif ax == 1:
                u, v = (-co.x if n.y > 0 else co.x), co.z
            else:
                u, v = co.x, (co.y if n.z > 0 else -co.y)
            uvl.data[li].uv = (u * scale + ou, v * scale + ov)


def uv_cyl(obj, *, axis: int = 2, scale: float = 1.0, u_repeats: float | None = None, offset=(0.0, 0.0),
           caps_planar: bool = True) -> None:
    """Cylindrical projection (u around, v along axis). Faces nearly perpendicular to the axis
    (caps) get planar mapping instead of smeared cylindrical UVs."""
    me = obj.data
    uvl = _uvl(me)
    o = [i for i in range(3) if i != axis]
    for p in me.polygons:
        if caps_planar and abs(p.normal[axis]) > 0.8:
            for li in p.loop_indices:
                co = me.vertices[me.loops[li].vertex_index].co
                uvl.data[li].uv = (co[o[0]] * scale + offset[0], co[o[1]] * scale + offset[1])
            continue
        angs = []
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            angs.append(math.atan2(co[o[1]], co[o[0]]))
        ref = angs[0]
        fixed = [a + (math.tau if a - ref < -math.pi else (-math.tau if a - ref > math.pi else 0.0)) for a in angs]
        for k, li in enumerate(p.loop_indices):
            co = me.vertices[me.loops[li].vertex_index].co
            rad = math.hypot(co[o[0]], co[o[1]])
            t = fixed[k] / math.tau + 0.5
            u = t * u_repeats if u_repeats is not None else t * math.tau * max(rad, 0.01) * scale
            uvl.data[li].uv = (u + offset[0], co[axis] * scale + offset[1])


def uv_planar(obj, axis: int = 2, *, rect=None, scale: float = 1.0, flip_u: bool = False,
              bounds=None, offset=(0.0, 0.0)) -> None:
    """Planar projection along `axis`. rect=(u0, v0, u1, v1) maps the object's bounds (or `bounds`
    ((lo_a, lo_b), (hi_a, hi_b))) into an atlas cell. Projection axes: X->(y,z) Y->(x,z) Z->(x,y)."""
    me = obj.data
    uvl = _uvl(me)
    o = [i for i in range(3) if i != axis]
    if rect is not None:
        if bounds is None:
            xs = [v.co[o[0]] for v in me.vertices]
            ys = [v.co[o[1]] for v in me.vertices]
            bounds = ((min(xs), min(ys)), (max(xs), max(ys)))
        (x0, y0), (x1, y1) = bounds
    for li, loop in enumerate(me.loops):
        co = me.vertices[loop.vertex_index].co
        a, b = co[o[0]], co[o[1]]
        if flip_u:
            a = -a
        if rect is None:
            uvl.data[li].uv = (a * scale + offset[0], b * scale + offset[1])
        else:
            if flip_u:
                a = -a
                u = (x1 - a) / max(1e-6, x1 - x0)
            else:
                u = (a - x0) / max(1e-6, x1 - x0)
            v = (b - y0) / max(1e-6, y1 - y0)
            uvl.data[li].uv = (rect[0] + u * (rect[2] - rect[0]), rect[1] + v * (rect[3] - rect[1]))


def uv_sheet(obj, *, scale: float = 1.0, offset=(0.0, 0.0)) -> None:
    """For deformed grids/cloth: keeps the UVs computed before deformation (call before deforming)."""
    uv_planar(obj, 2, scale=scale, offset=offset)


# --------------------------------------------------------------------------------------------
# Vertex colour channels per part
# --------------------------------------------------------------------------------------------

def _edge_convexity(bm) -> list[float]:
    conv = [0.0] * len(bm.verts)
    lim = math.radians(18.0)
    for e in bm.edges:
        lf = e.link_faces
        if len(lf) != 2:
            for v in e.verts:
                conv[v.index] = max(conv[v.index], 0.55)
            continue
        f1, f2 = lf
        ang = f1.normal.angle(f2.normal, 0.0)
        if ang < lim:
            continue
        if (f2.calc_center_median() - f1.calc_center_median()).dot(f1.normal) < 0.0:
            amt = min(1.0, ang / math.radians(75.0))
            for v in e.verts:
                conv[v.index] = max(conv[v.index], amt)
    return conv


def paint_part(obj, *, level: float, wear: float = 1.0, edge: float = 1.0, patches: float = 0.6,
               low: float = 0.0, low_h: float = 0.5, base: float = 0.0, seed: int = 0, scale: float = 2.2,
               moss: float = 0.0, tint: float = 0.0, ground: float = 0.0, extra=None) -> None:
    """Writes G (wear) and B (moss / variation) for every corner of a part (R = 1, A = 1).
    level: condition wear (clean ~0.2, worn ~0.6, destroyed ~0.85); wear: per-part multiplier.
    extra(co_world, normal) -> additive G term (e.g. blood stains, scorch)."""
    me = obj.data
    layer = vcolor.ensure_layer(obj, fill=(1.0, 0.0, 0.0, 1.0))
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    conv = _edge_convexity(bm)
    bm.free()
    noise.seed_set(seed % 100000)
    off = Vector((seed * 0.917 % 71, seed * 0.613 % 67, seed * 0.271 % 73))
    t0 = 0.9 - 0.55 * level
    g_v = []
    b_v = []
    for v in me.vertices:
        p = v.co
        nz = noise.noise(p * scale + off) * 0.6 + noise.noise(p * scale * 2.7 + off * 1.3) * 0.4
        nz = clamp(0.5 + 0.5 * nz * 1.6)
        g = base
        g += level * 1.3 * edge * conv[v.index] * (0.55 + 0.9 * nz)
        g += patches * smooth01(t0, t0 + 0.22, nz)
        if low > 0.0:
            g += low * level * (1.0 - smooth01(0.0, low_h, p.z - ground)) * (0.5 + nz)
        if extra is not None:
            g += extra(p, v.normal)
        g_v.append(clamp(g * wear))
        b = tint
        if moss > 0.0:
            up = max(0.0, v.normal.z)
            m2 = clamp(0.5 + 0.5 * noise.noise(p * 3.1 + off * 0.7) * 1.8)
            b = max(b, moss * up * smooth01(0.35, 0.7, m2))
        b_v.append(clamp(b))
    cols = [0.0] * (len(layer.data) * 4)
    layer.data.foreach_get("color", cols)
    for li, loop in enumerate(me.loops):
        vi = loop.vertex_index
        cols[li * 4 + 0] = 1.0
        cols[li * 4 + 1] = g_v[vi]
        cols[li * 4 + 2] = b_v[vi]
        cols[li * 4 + 3] = 1.0
    layer.data.foreach_set("color", cols)


# --------------------------------------------------------------------------------------------
# Build context
# --------------------------------------------------------------------------------------------

COND_LEVEL = {"clean": 0.3, "worn": 0.65, "destroyed": 0.85}


class Ctx:
    """Per-variant build state."""

    def __init__(self, params: dict, cond: str):
        self.p = params
        self.cond = cond
        self.seed = int(params.get("seed", 1))
        self.level = float(params.get("levels", {}).get(cond, COND_LEVEL.get(cond, 0.5)))
        self.parts: list[bpy.types.Object] = []
        self.cols: list[bpy.types.Object] = []
        self.no_ao: set[str] = set()
        self.ground_clamp = True  # vertices below z=0 are raised to the floor in finalize()
        self.post: list = []  # callables fn(joined_obj) run after the AO bake (e.g. panel seams)
        self._n = 0

    # Conditions
    @property
    def clean(self) -> bool:
        return self.cond == "clean"

    @property
    def worn(self) -> bool:
        return self.cond in ("worn", "destroyed")

    @property
    def destroyed(self) -> bool:
        return self.cond == "destroyed"

    def param(self, key: str, default=None):
        """Task parameter; a {condition: value} dict picks the value for this condition (falls back
        to 'worn' for destroyed, then 'clean')."""
        v = self.p.get(key, default)
        if isinstance(v, dict):
            for c in (self.cond, "worn" if self.cond == "destroyed" else self.cond, "clean"):
                if c in v:
                    return v[c]
            return default
        return v

    def rnd(self, key: str | int) -> random.Random:
        """Keyed RNG stream: identical across conditions for the same key (stable shapes)."""
        return random.Random(f"{self.seed}:{key}")

    def drnd(self, key: str | int) -> random.Random:
        """Condition-specific RNG stream (damage that differs between variants)."""
        return random.Random(f"{self.seed}:{self.cond}:{key}")

    def uid(self, base: str = "p") -> str:
        self._n += 1
        return f"{base}_{self._n:03d}"

    def add(self, obj, mat: str | None, *, uv: str | None = "box", uv_scale: float = 1.0, long_axis: int | None = None,
            uv_axis: int = 2, rect=None, uv_offset=None, smooth: float | None = None, wear: float = 1.0,
            edge: float = 1.0, patches: float = 0.6, low: float = 0.0, low_h: float = 0.5, base: float = 0.0,
            moss: float = 0.0, tint: float = 0.0, extra=None, noise_scale: float = 2.2, ao: bool = True,
            cyl_repeats: float | None = None, at=None, ori=None) -> bpy.types.Object:
        """Assign material, UVs (computed in the part's own frame), optional placement
        (`ori`=(long, normal, loc) via orient(), then `at`=(loc, rot_deg[, scale])), smoothing and
        wear/moss vertex colours (world space).
        uv: 'box' | 'cyl' | 'planar' | None (keep existing UVs). mat None keeps existing slots."""
        if mat is not None:
            materials.assign_all(obj, mat)
        if uv_offset is None:
            r = self.rnd(f"uvoff:{len(self.parts)}")
            uv_offset = (r.uniform(0, 7), r.uniform(0, 7))
        if uv == "box":
            uv_box(obj, uv_scale, long_axis=long_axis, offset=uv_offset)
        elif uv == "cyl":
            uv_cyl(obj, axis=uv_axis, scale=uv_scale, u_repeats=cyl_repeats, offset=uv_offset)
        elif uv == "planar":
            uv_planar(obj, uv_axis, rect=rect, scale=uv_scale, offset=(0, 0) if rect else uv_offset)
        if ori is not None:
            orient(obj, *ori)
        if at is not None:
            place(obj, at[0], at[1] if len(at) > 1 else None, at[2] if len(at) > 2 else None)
        if smooth is None:
            common.shade_flat(obj)
        else:
            common.shade_smooth(obj, angle_deg=smooth)
        # Patch coverage grows with the condition level twice (lower noise threshold in paint_part
        # and a stronger contribution here) so clean variants keep only light edge chipping.
        paint_part(obj, level=self.level, wear=wear, edge=edge, patches=patches * self.level / 0.65 if patches else 0.0,
                   low=low, low_h=low_h, base=base, seed=self.seed + len(self.parts) * 17, scale=noise_scale,
                   moss=moss, tint=tint, extra=extra)
        if not ao:
            self.no_ao.add(obj.name)
        self.parts.append(obj)
        return obj

    def col_box(self, lo, hi, name: str | None = None, rot=None, center=None) -> bpy.types.Object:
        lo, hi = Vector(lo), Vector(hi)
        o = box(name or self.uid("col"), hi - lo, (lo + hi) / 2)
        if rot is not None:
            c = (lo + hi) / 2 if center is None else Vector(center)
            o.data.transform(Matrix.Translation(c) @ rot_matrix(rot) @ Matrix.Translation(-c))
        self.cols.append(o)
        return o

    def col_hull(self, points_or_objs, name: str | None = None, max_points: int = 64) -> bpy.types.Object:
        pts = []
        for x in points_or_objs:
            if isinstance(x, bpy.types.Object):
                pts += [x.matrix_world @ v.co for v in x.data.vertices]
            else:
                pts.append(Vector(x))
        if len(pts) > max_points * 4:
            step = len(pts) / (max_points * 4)
            pts = [pts[int(i * step)] for i in range(max_points * 4)]
        o = hull_of(name or self.uid("col"), pts)
        if len(o.data.vertices) > max_points:
            from .lod import decimated_copy
            d = decimated_copy(o, max_points / len(o.data.vertices), o.name + "_d")
            remove(o)
            o = canon(d)
        self.cols.append(o)
        return o


# --------------------------------------------------------------------------------------------
# Finalise + export
# --------------------------------------------------------------------------------------------

def finalize(ctx: Ctx, name: str, *, ao_samples: int = 20, ao_dist: float = 0.6, ao_strength: float = 1.0,
             ground_ao: bool = True) -> bpy.types.Object:
    """Joins the registered parts, bakes vertex AO into R (parts added with ao=False keep R = 1)."""
    parts = [o for o in ctx.parts if o is not None and len(o.data.polygons) > 0]
    if ctx.ground_clamp:
        for o in parts:
            for v in o.data.vertices:
                if v.co.z < 0.0:
                    v.co.z = 0.0
            o.data.update()
    for o in parts:
        a = o.data.attributes.get("hm_noao") or o.data.attributes.new("hm_noao", "INT", "FACE")
        a.data.foreach_set("value", [1 if o.name in ctx.no_ao else 0] * len(o.data.polygons))
    obj = common.join(parts, name)
    me = obj.data
    # Drop unused / empty material slots (each slot becomes a draw call in Godot).
    used = sorted({p.material_index for p in me.polygons if p.material_index < len(me.materials)
                   and me.materials[p.material_index] is not None})
    if len(used) != len(me.materials):
        mats = [me.materials[i] for i in used]
        remap = {old: new for new, old in enumerate(used)}
        idx = [remap.get(p.material_index, 0) for p in me.polygons]
        me.materials.clear()
        for m in mats:
            me.materials.append(m)
        me.polygons.foreach_set("material_index", idx)
    canon(obj)
    vcolor.bake_ao([obj], samples=ao_samples, distance=ao_dist, strength=ao_strength, ground=ground_ao)
    a = me.attributes.get("hm_noao")
    flags = [0] * len(me.polygons)
    a.data.foreach_get("value", flags)
    if any(flags):
        layer = me.color_attributes.get(vcolor.ATTR)
        cols = [0.0] * (len(layer.data) * 4)
        layer.data.foreach_get("color", cols)
        for p in me.polygons:
            if flags[p.index]:
                for li in p.loop_indices:
                    cols[li * 4] = 1.0
        layer.data.foreach_set("color", cols)
    me.attributes.remove(me.attributes.get("hm_noao"))
    for fn in ctx.post:
        fn(obj)
    return obj


def darken_faces(obj, pred, value: float = 0.2, channel: int = 0) -> int:
    """Sets a vertex colour channel on every corner of faces where pred(center, normal) is True
    (crisp per-face values: panel gaps, scorch marks). Returns the number of faces touched."""
    me = obj.data
    layer = me.color_attributes.get(vcolor.ATTR)
    cols = [0.0] * (len(layer.data) * 4)
    layer.data.foreach_get("color", cols)
    n = 0
    for p in me.polygons:
        if pred(p.center, p.normal):
            n += 1
            for li in p.loop_indices:
                cols[li * 4 + channel] = min(cols[li * 4 + channel], value) if channel == 0 else value
    layer.data.foreach_set("color", cols)
    return n


def report(name: str, obj, cols) -> None:
    lo, hi = common.bounds(obj)
    print(f"[props_ext] {name}: tris={common.triangle_count(obj)} size=({hi.x - lo.x:.2f}, {hi.y - lo.y:.2f}, "
          f"{hi.z - lo.z:.2f}) zmin={lo.z:.3f} mats={[m.name if m else None for m in obj.data.materials]} cols={len(cols)}")


def run(params: dict, outputs: list[str], builders: dict) -> None:
    """Entry point used by every props_ext generator's build(): one GLB per condition.
    The scene is left holding the last variant (dev_preview renders it)."""
    prop = params["prop"]
    fn = builders[prop]
    conds = params.get("conditions", ["clean"])
    if len(conds) != len(outputs):
        raise ValueError(f"{prop}: {len(conds)} conditions but {len(outputs)} outputs")
    only = params.get("_only")  # dev helper: build a single condition
    for cond, out in zip(conds, outputs):
        if only and cond != only:
            continue
        bpy.ops.wm.read_factory_settings(use_empty=True)
        ctx = Ctx(params, cond)
        fn(ctx)
        name = prop if cond == "clean" else f"{prop}_{cond}"
        obj = finalize(ctx, name, ao_samples=int(params.get("ao_samples", 20)), ao_dist=float(params.get("ao_dist", 0.6)),
                       ao_strength=float(params.get("ao_strength", 1.0)))
        for k, c in enumerate(ctx.cols):
            c.name = f"{name}_col{k}-convcolonly"
            c.data.name = c.name
            c.data.materials.clear()
            for p in c.data.polygons:
                p.use_smooth = False
        report(name, obj, ctx.cols)
        export.export_glb(out, [obj] + ctx.cols)
