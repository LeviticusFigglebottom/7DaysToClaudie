"""Geometry toolkit for the interior-props family (bmesh, deterministic).

Every builder returns a new mesh Object whose vertices are already in final (world) coordinates
(identity object transform). Z up, metres, front = -Y (see docs/ASSET_PIPELINE.md).

  box            bevelled box
  rbox           rounded / soft box on a grid (cushions, mattresses, pillows, dentable sheet metal)
  cyl            cylinder / cone frustum along X|Y|Z, optional bevelled rims
  lathe          surface of revolution from a (radius, height) profile, along X|Y|Z
  tube           circular tube swept along a polyline (chrome frames, rails, wires); fillet() rounds paths
  prism          2D polygon extruded along an axis (shaped rails, splats, broken panels)
  hollow_box     box with a cavity open on one face (carcasses, drawers, trays)
  panel          door / drawer front with frame-and-panel detail via insets
  xform          rotate / translate an object's mesh in place
  splinter_cut   cut an object by a plane and splinter the cut (broken legs, rails, posts)
  jagged_split   split a rectangle into two polygons along a zig-zag break line
  shatter_cells  radial crack cells of a pane, clipped to its rectangle
"""
from __future__ import annotations

import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

from . import common

AXES = {"X": 0, "Y": 1, "Z": 2}


def _obj(name: str, bm: bmesh.types.BMesh) -> bpy.types.Object:
    return common.mesh_from_bmesh(name, bm)


def _axis_matrix(axis: str) -> Matrix:
    """Rotation taking +Z to the given axis."""
    if axis == "X":
        return Matrix.Rotation(math.pi / 2, 4, "Y")
    if axis == "Y":
        return Matrix.Rotation(-math.pi / 2, 4, "X")
    if axis == "-Y":
        return Matrix.Rotation(math.pi / 2, 4, "X")
    if axis == "-X":
        return Matrix.Rotation(-math.pi / 2, 4, "Y")
    if axis == "-Z":
        return Matrix.Rotation(math.pi, 4, "X")
    return Matrix.Identity(4)


# ------------------------------------------------------------------------------------------------
# basic solids
# ------------------------------------------------------------------------------------------------


def box(name: str, size, center=(0, 0, 0), bevel: float = 0.0, segs: int = 1) -> bpy.types.Object:
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    if bevel > 0.0:
        b = min(bevel, 0.45 * min(size))
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=b, offset_type="OFFSET", segments=segs, profile=0.5,
                        affect="EDGES", clamp_overlap=True)
    bmesh.ops.translate(bm, vec=Vector(center), verts=bm.verts)
    return _obj(name, bm)


def _axis_coords(h: float, r: float, n_inner: int, rs: int) -> list[float]:
    if r <= 1e-6 or rs <= 0:
        return [-h + 2 * h * t / max(1, n_inner) for t in range(max(1, n_inner) + 1)]
    inner = h - r
    pts = [-h + r * t / rs for t in range(rs)]
    pts += [-inner + 2 * inner * t / max(1, n_inner) for t in range(max(1, n_inner) + 1)]
    pts += [inner + r * t / rs for t in range(1, rs + 1)]
    return pts


def rbox(name: str, size, center=(0, 0, 0), radius: float = 0.03, inner=(2, 2, 1), rs: int = 1,
         bulge=(0.0, 0.0, 0.0), sag: float = 0.0, sag_at=(0.0, 0.0), sag_r: float = 0.25,
         wrinkle: float = 0.0, wrinkle_scale: float = 9.0, seed: int = 0, taper_top: float = 0.0,
         squash=None) -> bpy.types.Object:
    """Rounded box on a structured grid (soft cushions etc.).
    radius: edge rounding (clamped to the half sizes); inner: grid segments of the flat region per axis;
    rs: segments per rounding zone half; bulge: per-axis outward doming of the face pairs (m);
    sag: dip of the top face around sag_at (local x, y) with radius sag_r; wrinkle: noise amplitude (m);
    taper_top: shrink factor of the top in x/y (0..1, for pillows / wedge backs);
    squash: optional fn(Vector local) -> Vector applied last (custom shaping)."""
    from mathutils import noise
    hx, hy, hz = (s * 0.5 for s in size)
    r = min(radius, 0.98 * min(hx, hy, hz))
    X = _axis_coords(hx, r, inner[0], rs)
    Y = _axis_coords(hy, r, inner[1], rs)
    Z = _axis_coords(hz, r, inner[2], rs)
    nx, ny, nz = len(X) - 1, len(Y) - 1, len(Z) - 1
    bm = bmesh.new()
    verts: dict[tuple[int, int, int], bmesh.types.BMVert] = {}

    def vert(i, j, k):
        key = (i, j, k)
        v = verts.get(key)
        if v is None:
            v = bm.verts.new((X[i], Y[j], Z[k]))
            verts[key] = v
        return v

    def quad(a, b, c, d):
        bm.faces.new((vert(*a), vert(*b), vert(*c), vert(*d)))

    for j in range(ny):
        for k in range(nz):
            quad((0, j, k), (0, j, k + 1), (0, j + 1, k + 1), (0, j + 1, k))
            quad((nx, j, k), (nx, j + 1, k), (nx, j + 1, k + 1), (nx, j, k + 1))
    for i in range(nx):
        for k in range(nz):
            quad((i, 0, k), (i + 1, 0, k), (i + 1, 0, k + 1), (i, 0, k + 1))
            quad((i, ny, k), (i, ny, k + 1), (i + 1, ny, k + 1), (i + 1, ny, k))
    for i in range(nx):
        for j in range(ny):
            quad((i, j, 0), (i, j + 1, 0), (i + 1, j + 1, 0), (i + 1, j, 0))
            quad((i, j, nz), (i + 1, j, nz), (i + 1, j + 1, nz), (i, j + 1, nz))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    inner_h = Vector((hx - r, hy - r, hz - r))
    hs = Vector((hx, hy, hz))
    noise.seed_set(int(seed) % 100000 + 1)
    for v in bm.verts:
        q = v.co.copy()
        c = Vector((max(-inner_h.x, min(inner_h.x, q.x)), max(-inner_h.y, min(inner_h.y, q.y)),
                    max(-inner_h.z, min(inner_h.z, q.z))))
        d = q - c
        n = d.normalized() if d.length > 1e-9 else Vector((0, 0, 1))
        p = c + n * r if d.length > 1e-9 else q
        u = [max(-1.0, min(1.0, p[a] / hs[a])) for a in range(3)]
        disp = Vector((0, 0, 0))
        for a in range(3):
            if bulge[a] != 0.0:
                o = [b for b in range(3) if b != a]
                f = (1 - u[o[0]] ** 2) * (1 - u[o[1]] ** 2)
                disp[a] += bulge[a] * f * (1.0 if p[a] >= 0 else -1.0) * min(1.0, abs(u[a]) * 1.5)
        if taper_top:
            t = (u[2] + 1) * 0.5
            p.x *= 1 - taper_top * t
            p.y *= 1 - taper_top * t
        if sag and p.z > 0:
            dd = (p.x - sag_at[0]) ** 2 + (p.y - sag_at[1]) ** 2
            disp.z -= sag * math.exp(-dd / (sag_r * sag_r)) * max(0.0, u[2])
        p += disp
        if wrinkle:
            w = noise.noise(p * wrinkle_scale + Vector((seed * 0.37, 1.3, 2.1)))
            p += n * w * wrinkle
        if squash is not None:
            p = squash(p)
        v.co = p
    bmesh.ops.translate(bm, vec=Vector(center), verts=bm.verts)
    return _obj(name, bm)


def cyl(name: str, r: float, h: float, center=(0, 0, 0), axis: str = "Z", segs: int = 12, r_top: float | None = None,
        bevel: float = 0.0, bevel_segs: int = 1, cap: bool = True) -> bpy.types.Object:
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=segs, radius1=r,
                          radius2=r if r_top is None else r_top, depth=h)
    if bevel > 0.0 and cap:
        rim = [e for e in bm.edges if len(e.link_faces) == 2 and
               abs(e.link_faces[0].normal.dot(e.link_faces[1].normal)) < 0.5]
        if rim:
            bmesh.ops.bevel(bm, geom=rim, offset=min(bevel, 0.45 * min(r, h)), offset_type="OFFSET",
                            segments=bevel_segs, profile=0.5, affect="EDGES", clamp_overlap=True)
    bm.transform(_axis_matrix(axis))
    bmesh.ops.translate(bm, vec=Vector(center), verts=bm.verts)
    return _obj(name, bm)


def lathe(name: str, profile, segs: int = 16, center=(0, 0, 0), axis: str = "Z", cap_bottom: bool = True,
          cap_top: bool = True, phase: float = 0.0) -> bpy.types.Object:
    """profile: [(radius, height), ...] bottom to top (heights along `axis` from `center`)."""
    bm = bmesh.new()
    rings = []
    for rad, z in profile:
        if rad < 1e-5:
            rings.append([bm.verts.new((0.0, 0.0, z))])
            continue
        ring = []
        for i in range(segs):
            a = 2 * math.pi * i / segs + phase
            ring.append(bm.verts.new((rad * math.cos(a), rad * math.sin(a), z)))
        rings.append(ring)
    for a, b in zip(rings[:-1], rings[1:]):
        if len(a) == 1 and len(b) == 1:
            continue
        if len(a) == 1:
            for i in range(segs):
                bm.faces.new((a[0], b[i], b[(i + 1) % segs]))
        elif len(b) == 1:
            for i in range(segs):
                bm.faces.new((a[i], a[(i + 1) % segs], b[0]))
        else:
            for i in range(segs):
                j = (i + 1) % segs
                bm.faces.new((a[i], a[j], b[j], b[i]))
    if cap_bottom and len(rings[0]) > 1:
        bm.faces.new(list(reversed(rings[0])))
    if cap_top and len(rings[-1]) > 1:
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.transform(_axis_matrix(axis))
    bmesh.ops.translate(bm, vec=Vector(center), verts=bm.verts)
    return _obj(name, bm)


def fillet(pts, radius: float, steps: int = 3) -> list[Vector]:
    """Rounds the interior corners of a polyline with quadratic Bezier arcs."""
    P = [Vector(p) for p in pts]
    if len(P) < 3 or radius <= 0:
        return P
    out = [P[0]]
    for i in range(1, len(P) - 1):
        a, b, c = P[i - 1], P[i], P[i + 1]
        d1, d2 = (a - b), (c - b)
        l1, l2 = d1.length, d2.length
        if l1 < 1e-6 or l2 < 1e-6:
            continue
        k = min(radius, 0.45 * l1, 0.45 * l2)
        s, e = b + d1.normalized() * k, b + d2.normalized() * k
        for t in range(steps + 1):
            u = t / steps
            out.append(s * (1 - u) ** 2 + b * 2 * u * (1 - u) + e * u * u)
    out.append(P[-1])
    return out


def tube(name: str, pts, radius: float, segs: int = 8, cap: bool = True, closed: bool = False,
         radii: list[float] | None = None) -> bpy.types.Object:
    """Circular tube along a polyline using parallel-transport frames (no twisting)."""
    P = [Vector(p) for p in pts]
    n = len(P)
    tangents = []
    for i in range(n):
        if closed:
            t = P[(i + 1) % n] - P[i - 1]
        else:
            t = (P[min(i + 1, n - 1)] - P[max(i - 1, 0)])
        tangents.append(t.normalized() if t.length > 1e-9 else Vector((0, 0, 1)))
    ref = Vector((0, 0, 1)) if abs(tangents[0].z) < 0.9 else Vector((1, 0, 0))
    normal = tangents[0].cross(ref).normalized()
    frames = []
    prev_t = tangents[0]
    for i in range(n):
        t = tangents[i]
        axis = prev_t.cross(t)
        if axis.length > 1e-9:
            ang = math.acos(max(-1.0, min(1.0, prev_t.dot(t))))
            normal = Matrix.Rotation(ang, 3, axis.normalized()) @ normal
        prev_t = t
        frames.append((normal.copy(), t.cross(normal).normalized()))
    bm = bmesh.new()
    rings = []
    for i in range(n):
        nn, bb = frames[i]
        rad = radii[i] if radii else radius
        ring = [bm.verts.new(P[i] + (nn * math.cos(2 * math.pi * k / segs) + bb * math.sin(2 * math.pi * k / segs)) * rad)
                for k in range(segs)]
        rings.append(ring)
    pairs = list(zip(rings[:-1], rings[1:]))
    if closed:
        pairs.append((rings[-1], rings[0]))
    for a, b in pairs:
        for k in range(segs):
            j = (k + 1) % segs
            bm.faces.new((a[k], a[j], b[j], b[k]))
    if cap and not closed:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _obj(name, bm)


def prism(name: str, poly, depth: float, plane: str = "XZ", offset: float = 0.0, bevel: float = 0.0) -> bpy.types.Object:
    """Extrudes a simple 2D polygon (CCW) in `plane` by `depth` along the plane normal starting at `offset`.
    XZ: (u,v)->(x,z), extruded along +Y; XY: (x,y) along +Z; YZ: (y,z) along +X.
    Side face i corresponds to polygon edge i (poly[i] -> poly[i+1]); returns object with the custom
    integer attribute 'edge_id' on faces (-1 for the caps) so callers can retexture break faces."""
    bm = bmesh.new()

    def to3(u, v, w):
        if plane == "XZ":
            return (u, w, v)
        if plane == "XY":
            return (u, v, w)
        return (w, u, v)

    a = [bm.verts.new(to3(u, v, offset)) for u, v in poly]
    b = [bm.verts.new(to3(u, v, offset + depth)) for u, v in poly]
    lay = bm.faces.layers.int.new("edge_id")
    f0 = bm.faces.new(a)
    f1 = bm.faces.new(list(reversed(b)))
    f0[lay] = -1
    f1[lay] = -1
    m = len(poly)
    for i in range(m):
        j = (i + 1) % m
        f = bm.faces.new((a[i], b[i], b[j], a[j]))
        f[lay] = i
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if bevel > 0:
        cap_edges = [e for e in bm.edges if len(e.link_faces) == 2 and
                     (e.link_faces[0][lay] == -1) != (e.link_faces[1][lay] == -1)]
        bmesh.ops.bevel(bm, geom=cap_edges, offset=bevel, offset_type="OFFSET", segments=1, profile=0.5,
                        affect="EDGES", clamp_overlap=True)
    return _obj(name, bm)


def hollow_box(name: str, size, center=(0, 0, 0), wall: float = 0.018, open_face: str = "-Y",
               bevel: float = 0.0, back: float | None = None) -> bpy.types.Object:
    """Box with a cavity open on `open_face` ("-Y", "+Z", ...). `back` = thickness of the face
    opposite the opening (default = wall)."""
    sx, sy, sz = size
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=min(bevel, wall * 0.45), offset_type="OFFSET", segments=1,
                        profile=0.5, affect="EDGES", clamp_overlap=True)
    ax = AXES[open_face[1]]
    sign = 1.0 if open_face[0] == "+" else -1.0
    want = Vector((0, 0, 0))
    want[ax] = sign
    face = max(bm.faces, key=lambda f: (f.normal.dot(want) > 0.99) * f.calc_area())
    bmesh.ops.inset_individual(bm, faces=[face], thickness=wall, depth=0.0, use_even_offset=True)
    ext = bmesh.ops.extrude_face_region(bm, geom=[face])
    nv = [g for g in ext["geom"] if isinstance(g, bmesh.types.BMVert)]
    depth = size[ax] - (back if back is not None else wall)
    bmesh.ops.translate(bm, vec=-want * depth, verts=nv)
    if face.is_valid:
        bmesh.ops.delete(bm, geom=[face], context="FACES")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.translate(bm, vec=Vector(center), verts=bm.verts)
    return _obj(name, bm)


def panel(name: str, w: float, h: float, t: float, center=(0, 0, 0), style: str = "shaker", frame: float = 0.06,
          recess: float = 0.006, bevel: float = 0.003, facing: str = "-Y") -> bpy.types.Object:
    """Door/drawer front lying in the XZ plane (thickness along Y), detailed on the -Y face.
    style: 'slab' (plain bevelled), 'shaker' (flat recessed centre), 'raised' (raised field with
    bevelled margin), 'groove' (single routed groove line)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector((w, t, h)), verts=bm.verts)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=min(bevel, t * 0.4), offset_type="OFFSET", segments=1,
                        profile=0.5, affect="EDGES", clamp_overlap=True)
    front = max(bm.faces, key=lambda f: (f.normal.y < -0.99) * f.calc_area())
    fr = min(frame, w * 0.3, h * 0.3)
    if style == "shaker":
        bmesh.ops.inset_individual(bm, faces=[front], thickness=fr, depth=-recess, use_even_offset=True)
    elif style == "raised":
        bmesh.ops.inset_individual(bm, faces=[front], thickness=fr, depth=-recess * 1.5, use_even_offset=True)
        bmesh.ops.inset_individual(bm, faces=[front], thickness=min(0.022, fr * 0.5), depth=recess * 1.3,
                                   use_even_offset=True)
    elif style == "groove":
        bmesh.ops.inset_individual(bm, faces=[front], thickness=fr, depth=0.0, use_even_offset=True)
        bmesh.ops.inset_individual(bm, faces=[front], thickness=0.004, depth=-recess * 0.6, use_even_offset=True)
        bmesh.ops.inset_individual(bm, faces=[front], thickness=0.004, depth=recess * 0.6, use_even_offset=True)
    if facing == "+Y":
        bm.transform(Matrix.Rotation(math.pi, 4, "Z"))
    bmesh.ops.translate(bm, vec=Vector(center), verts=bm.verts)
    return _obj(name, bm)


# ------------------------------------------------------------------------------------------------
# transforms
# ------------------------------------------------------------------------------------------------


def rot_matrix(rot_deg=(0, 0, 0)) -> Matrix:
    rx, ry, rz = (math.radians(a) for a in rot_deg)
    return (Matrix.Rotation(rz, 4, "Z") @ Matrix.Rotation(ry, 4, "Y") @ Matrix.Rotation(rx, 4, "X"))


def xform(obj: bpy.types.Object, rot=(0, 0, 0), pivot=(0, 0, 0), loc=(0, 0, 0), scale=None, matrix: Matrix | None = None) -> None:
    """Rotates (XYZ euler degrees) about `pivot`, then translates by `loc` (mesh data, in place)."""
    pv = Vector(pivot)
    m = matrix if matrix is not None else rot_matrix(rot)
    if scale is not None:
        m = m @ Matrix.Diagonal(Vector((*scale, 1.0)))
    full = Matrix.Translation(Vector(loc)) @ Matrix.Translation(pv) @ m @ Matrix.Translation(-pv)
    obj.data.transform(full)
    obj.data.update()


def bounds(objs) -> tuple[Vector, Vector]:
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for o in objs:
        for v in o.data.vertices:
            for a in range(3):
                lo[a] = min(lo[a], v.co[a])
                hi[a] = max(hi[a], v.co[a])
    return lo, hi


# ------------------------------------------------------------------------------------------------
# breakage
# ------------------------------------------------------------------------------------------------


def splinter_cut(obj: bpy.types.Object, plane_co, plane_no, jag: float = 0.02, seed: int = 0,
                 inner_slot: int | None = None) -> bool:
    """Keeps the part of `obj` behind the plane (opposite plane_no), fills the cut and splinters it:
    the cap is poked and its rim / centre are jittered along the normal. inner_slot = material slot
    index for the cap faces. Returns False if nothing remains."""
    r = random.Random(seed)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    co, no = Vector(plane_co), Vector(plane_no).normalized()
    geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
    res = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no, clear_outer=True)
    cut_edges = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge) and e.is_valid]
    if not bm.faces:
        bm.free()
        return False
    cut_verts = {v for e in cut_edges for v in e.verts}
    if cut_edges:
        filled = bmesh.ops.holes_fill(bm, edges=cut_edges, sides=0)
        caps = filled.get("faces", [])
        if inner_slot is not None:
            for f in caps:
                f.material_index = inner_slot
        if caps:
            poked = bmesh.ops.poke(bm, faces=caps)
            for v in poked["verts"]:
                v.co += no * r.uniform(-0.3, 1.0) * jag * 1.6
            if inner_slot is not None:
                for f in poked["faces"]:
                    f.material_index = inner_slot
    for v in sorted(cut_verts, key=lambda v: (round(v.co.x, 5), round(v.co.y, 5), round(v.co.z, 5))):
        if v.is_valid:
            v.co += no * r.uniform(-0.6, 0.9) * jag
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return True


def jagged_split(w: float, h: float, a, b, teeth: int = 7, amp: float = 0.02, seed: int = 0):
    """Splits the rectangle [-w/2,w/2]x[-h/2,h/2] along a zig-zag line from boundary point a to b.
    Returns (poly_left, poly_right, break_edges_left, break_edges_right): CCW polygons and the indices
    of their edges lying on the break (for inner-material assignment)."""
    r = random.Random(seed)
    A, B = Vector((a[0], a[1])), Vector((b[0], b[1]))
    d = B - A
    nrm = Vector((-d.y, d.x)).normalized()
    zz = [A]
    for i in range(1, teeth):
        t = i / teeth + r.uniform(-0.3, 0.3) / teeth
        zz.append(A + d * t + nrm * r.uniform(-amp, amp))
    zz.append(B)
    corners = [Vector((-w / 2, -h / 2)), Vector((w / 2, -h / 2)), Vector((w / 2, h / 2)), Vector((-w / 2, h / 2))]

    def perim_param(p):
        # position along the CCW perimeter starting at corner 0
        x, y = p
        if abs(y + h / 2) < 1e-6:
            return x + w / 2
        if abs(x - w / 2) < 1e-6:
            return w + y + h / 2
        if abs(y - h / 2) < 1e-6:
            return w + h + (w / 2 - x)
        return 2 * w + h + (h / 2 - y)

    ta, tb = perim_param(A), perim_param(B)
    cps = [(perim_param(c), c) for c in corners]
    per = 2 * (w + h)

    def walk(t0, t1):
        # corners strictly between t0 and t1 going CCW
        out = []
        for tc, c in sorted(cps, key=lambda x: (x[0] - t0) % per):
            if 1e-9 < (tc - t0) % per < (t1 - t0) % per - 1e-9:
                out.append(c)
        return out

    # polygon 1: A -> (perimeter CCW to B) -> back along zigzag B..A
    p1 = [A] + walk(ta, tb) + [B] + list(reversed(zz[1:-1]))
    br1 = list(range(len(p1) - len(zz) + 1, len(p1))) + [len(p1) - 1]
    p2 = [B] + walk(tb, ta) + [A] + zz[1:-1]
    br2 = list(range(len(p2) - len(zz) + 1, len(p2))) + [len(p2) - 1]

    def ccw(poly):
        area = sum(poly[i].x * poly[(i + 1) % len(poly)].y - poly[(i + 1) % len(poly)].x * poly[i].y for i in range(len(poly)))
        return area > 0

    def fix(poly, br):
        if ccw(poly):
            return [(p.x, p.y) for p in poly], sorted(set(br))
        n = len(poly)
        rp = list(reversed(poly))
        # edge i (p[i]->p[i+1]) becomes edge n-2-i in the reversed polygon
        nbr = sorted({(n - 2 - i) % n for i in br})
        return [(p.x, p.y) for p in rp], nbr

    q1, b1 = fix(p1, [i % len(p1) for i in br1])
    q2, b2 = fix(p2, [i % len(p2) for i in br2])
    return q1, q2, b1, b2


def _clip_poly(poly, x0, y0, x1, y1):
    def clip(pts, inside, inter):
        out = []
        for i in range(len(pts)):
            cur, prev = pts[i], pts[i - 1]
            if inside(cur):
                if not inside(prev):
                    out.append(inter(prev, cur))
                out.append(cur)
            elif inside(prev):
                out.append(inter(prev, cur))
        return out

    def ix(xc):
        return lambda p, q: (xc, p[1] + (q[1] - p[1]) * (xc - p[0]) / (q[0] - p[0]))

    def iy(yc):
        return lambda p, q: (p[0] + (q[0] - p[0]) * (yc - p[1]) / (q[1] - p[1]), yc)

    pts = list(poly)
    for inside, inter in ((lambda p: p[0] >= x0, ix(x0)), (lambda p: p[0] <= x1, ix(x1)),
                          (lambda p: p[1] >= y0, iy(y0)), (lambda p: p[1] <= y1, iy(y1))):
        if not pts:
            break
        pts = clip(pts, inside, inter)
    return pts


def shatter_cells(w: float, h: float, impact=(0.0, 0.0), spokes: int = 9, rings: int = 3, seed: int = 0):
    """Radial/concentric crack cells of a w x h pane centred at 0 (2D). Returns list of
    (polygon, ring_index) clipped to the pane."""
    r = random.Random(seed)
    ix, iy = impact
    angs = sorted((2 * math.pi * (k + r.uniform(-0.3, 0.3)) / spokes) for k in range(spokes))
    reach = math.hypot(w, h) * 1.2
    radii = [reach * (0.08 + 0.92 * ((k + 1) / rings) ** 1.6) for k in range(rings)]
    cells = []
    for ri in range(rings):
        r0 = 0.0 if ri == 0 else radii[ri - 1]
        r1 = radii[ri]
        for k in range(spokes):
            a0, a1 = angs[k], angs[(k + 1) % spokes] + (2 * math.pi if k == spokes - 1 else 0.0)
            j0 = r.uniform(0.85, 1.15)
            j1 = r.uniform(0.85, 1.15)
            pts = []
            if r0 <= 1e-6:
                pts.append((ix, iy))
            else:
                pts.append((ix + math.cos(a0) * r0 * j0, iy + math.sin(a0) * r0 * j0))
            pts.append((ix + math.cos(a0) * r1 * j1, iy + math.sin(a0) * r1 * j1))
            am = (a0 + a1) * 0.5
            pts.append((ix + math.cos(am) * r1 * r.uniform(0.9, 1.1), iy + math.sin(am) * r1 * r.uniform(0.9, 1.1)))
            pts.append((ix + math.cos(a1) * r1 * j0, iy + math.sin(a1) * r1 * j0))
            if r0 > 1e-6:
                pts.append((ix + math.cos(a1) * r0 * j1, iy + math.sin(a1) * r0 * j1))
            poly = _clip_poly(pts, -w / 2, -h / 2, w / 2, h / 2)
            if len(poly) >= 3:
                area = 0.5 * abs(sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                                     for i in range(len(poly))))
                if area > 1e-5:
                    if sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                           for i in range(len(poly))) < 0:
                        poly = list(reversed(poly))
                    cells.append((poly, ri))
    return cells


def rrect_ring(w: float, d: float, r: float, z: float, n: int = 3, cx: float = 0.0, cy: float = 0.0):
    """Points of a rounded rectangle outline (CCW from above) at height z; constant count 4*(n+1)."""
    r = max(0.002, min(r, w / 2 - 1e-4, d / 2 - 1e-4))
    pts = []
    for qx, qy, a0 in ((w / 2 - r, -d / 2 + r, -90), (w / 2 - r, d / 2 - r, 0), (-w / 2 + r, d / 2 - r, 90),
                       (-w / 2 + r, -d / 2 + r, 180)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + qx + r * math.cos(a), cy + qy + r * math.sin(a), z))
    return pts


def loft(name: str, rings, cap_bottom: bool = True, cap_top: bool = False, inward: bool = False) -> bpy.types.Object:
    """Skins consecutive rings (equal point counts, CCW from above). inward=True makes the faces visible from
    inside (basins, tubs). Ring with a single point = apex."""
    bm = bmesh.new()
    vr = [[bm.verts.new(p) for p in ring] for ring in rings]
    for a, b in zip(vr[:-1], vr[1:]):
        if len(a) == 1:
            for i in range(len(b)):
                bm.faces.new((a[0], b[i], b[(i + 1) % len(b)]))
        elif len(b) == 1:
            for i in range(len(a)):
                bm.faces.new((a[i], a[(i + 1) % len(a)], b[0]))
        else:
            n = len(a)
            for i in range(n):
                j = (i + 1) % n
                bm.faces.new((a[i], a[j], b[j], b[i]))
    if cap_bottom and len(vr[0]) > 2:
        bm.faces.new(list(reversed(vr[0])))
    if cap_top and len(vr[-1]) > 2:
        bm.faces.new(vr[-1])
    # orientation from construction: CCW rings stacked upward give outward-facing sides
    if inward:
        for f in bm.faces:
            f.normal_flip()
    return _obj(name, bm)
