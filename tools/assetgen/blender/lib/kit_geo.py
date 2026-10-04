"""POI kit mesh builder (docs/POI_KIT.md).

KitMesh accumulates polygons, each with a material id, a side tag and explicit UV0 coordinates, then
builds ONE Blender object with two UV maps:
  * "UVMap"  (TEXCOORD_0 -> Godot UV):  metre-scale box projection; with `grain` the texture U axis
    follows a part's long axis (wood grain runs along U in every kit wood texture).
  * "UVSide" (TEXCOORD_1 -> Godot UV2): u = 0 side A (-Y) / floor top, u = 1 side B (+Y) / ceiling,
    u = 0.5 every other face. v is written as 1.0 in Blender, which glTF flips to 0.0 (Godot reads 0).

Primitives build welded shells (shared vertices) so parts stay manifold for fracture and edge-wear
bakes, while separate parts stay separate. Everything is deterministic (no hashing of unordered
containers, explicit seeds).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import bmesh
import bpy
from mathutils import Matrix, Vector, geometry, noise
from mathutils.bvhtree import BVHTree

from . import common, export, materials, vcolor
from . import kit_poly as P

UV_SIDE = "UVSide"
SIDE_A = 0.0
SIDE_B = 1.0
SIDE_N = 0.5
SIDE_V = 1.0
# Faces of these materials carry the per-instance finishes: neutral vertex colour (1, 0, 0, 1) so every
# wall/floor piece blends seamlessly with its neighbours (AO there comes from the renderer).
FINISH_MATS = ("kit_wall", "kit_floor")
_AX = {"x": 0, "y": 1, "z": 2}


def newell(pts: list[Vector]) -> Vector:
    n = Vector((0.0, 0.0, 0.0))
    k = len(pts)
    for i in range(k):
        a, b = pts[i], pts[(i + 1) % k]
        n.x += (a.y - b.y) * (a.z + b.z)
        n.y += (a.z - b.z) * (a.x + b.x)
        n.z += (a.x - b.x) * (a.y + b.y)
    return n.normalized() if n.length > 1e-12 else Vector((0.0, 0.0, 1.0))


def box_uv(co: Vector, n: Vector, grain: str | None = None, scale: float = 1.0) -> tuple[float, float]:
    """Metre box projection (same layout as lib.uv.box_project); with `grain` the U axis follows
    that axis whenever it lies in the face plane (so wood grain runs along boards, studs, rails)."""
    ax = max(range(3), key=lambda i: abs(n[i]))
    if grain is not None:
        g = _AX[grain]
        if g != ax:
            other = 3 - ax - g
            return co[g] * scale, co[other] * scale
    if ax == 0:
        u, v = (co.y if n.x > 0 else -co.y), co.z
    elif ax == 1:
        u, v = (-co.x if n.y > 0 else co.x), co.z
    else:
        u, v = co.x, (co.y if n.z > 0 else -co.y)
    return u * scale, v * scale


def auto_side(n: Vector, mode) -> float:
    if not isinstance(mode, str):
        return float(mode)
    if mode == "y":
        return SIDE_A if n.y < -0.5 else (SIDE_B if n.y > 0.5 else SIDE_N)
    if mode == "z":
        return SIDE_A if n.z > 0.5 else (SIDE_B if n.z < -0.5 else SIDE_N)
    return SIDE_N


@dataclass
class Face:
    verts: list[int]
    mat: str
    side: float
    uvs: list[tuple[float, float]]
    part: int
    smooth: bool = False


def _map2d(axis: str, a: float, b: float, d: float) -> tuple[float, float, float]:
    if axis == "y":
        return (a, d, b)
    if axis == "x":
        return (d, a, b)
    return (a, b, d)


def _axis_vec(axis: str) -> Vector:
    v = Vector((0.0, 0.0, 0.0))
    v[_AX[axis]] = 1.0
    return v


class KitMesh:
    """Polygon soup with per-face material / side / UV that becomes one Blender mesh object."""

    def __init__(self, name: str):
        self.name = name
        self.co: list[Vector] = []
        self.faces: list[Face] = []
        self.part_values: list[float] = [0.5]
        self.cur_part = 0

    # -- bookkeeping ----------------------------------------------------------------------------
    def part(self, variation: float = 0.5) -> int:
        """Starts a new part; `variation` goes to vertex colour B (per-part tint variation)."""
        self.part_values.append(max(0.0, min(1.0, float(variation))))
        self.cur_part = len(self.part_values) - 1
        return self.cur_part

    def emit(self, pts, polys, frame: Matrix | None = None, *, grain: str | None = None, uv_scale: float = 1.0,
             uv_off: tuple[float, float] = (0.0, 0.0), uv_fn=None) -> int:
        """Adds local points (transformed by `frame`) and polygons [(indices, mat, side, smooth), ...].
        UV0 is computed from LOCAL coordinates (so it rotates with the part). Returns the base index."""
        M = frame if frame is not None else Matrix.Identity(4)
        R = M.to_3x3()
        base = len(self.co)
        loc = [Vector(p) for p in pts]
        for p in loc:
            self.co.append(M @ p)
        for idx, mat, side, smooth in polys:
            lp = [loc[i] for i in idx]
            n = newell(lp)
            if uv_fn is not None:
                uvs = [uv_fn(p, n) for p in lp]
            else:
                uvs = []
                for p in lp:
                    u, v = box_uv(p, n, grain, uv_scale)
                    uvs.append((u + uv_off[0], v + uv_off[1]))
            wn = (R @ n).normalized()
            self.faces.append(Face([base + i for i in idx], mat, auto_side(wn, side), uvs, self.cur_part, smooth))
        return base

    # -- primitives -----------------------------------------------------------------------------
    def box(self, lo, hi, mat: str, *, side="n", frame: Matrix | None = None, grain: str | None = None,
            skip: tuple[str, ...] = (), mats: dict | None = None, sides: dict | None = None, uv_scale: float = 1.0,
            uv_off=(0.0, 0.0)) -> None:
        """Axis-aligned box lo..hi in local space. Face keys: -x +x -y +y -z +z."""
        x0, y0, z0 = lo
        x1, y1, z1 = hi
        pts = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
               (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        faces = {"-z": (0, 3, 2, 1), "+z": (4, 5, 6, 7), "-y": (0, 1, 5, 4), "+y": (2, 3, 7, 6),
                 "-x": (3, 0, 4, 7), "+x": (1, 2, 6, 5)}
        polys = []
        for key in ("-x", "+x", "-y", "+y", "-z", "+z"):
            if key in skip:
                continue
            m = (mats or {}).get(key, mat)
            s = (sides or {}).get(key, side)
            polys.append((list(faces[key]), m, s, False))
        self.emit(pts, polys, frame, grain=grain, uv_scale=uv_scale, uv_off=uv_off)

    def prism(self, loops: list[list[tuple[float, float]]], d0: float, d1: float, *, axis: str = "y", mat: str,
              mat_back: str | None = None, mat_rim: str | None = None, side=("y", "y", SIDE_N),
              frame: Matrix | None = None, grain: str | None = None, uv_scale: float = 1.0, uv_off=(0.0, 0.0),
              depth_fn=None, caps: tuple[bool, bool] = (True, True), rim_filter=None, rim_mat_fn=None,
              back_loops: list | None = None, front_loops: list | None = None) -> None:
        """Extrudes a 2D region (loops[0] = outline, loops[1:] = holes; any winding) between depths
        d0 < d1 along `axis`. 2D coords map to (x, z) for axis y, (y, z) for x, (x, y) for z.
        Front cap (d0) faces -axis, back cap (d1) faces +axis, rim quads face out of the region.
        depth_fn(loop_i, vert_i, a, b) -> (d0', d1') overrides depths per vertex (splinter tips).
        rim_filter(a, b) -> False drops a rim quad (e.g. faces hidden by an end cap).
        rim_mat_fn(a, b) -> (mat, side) | None overrides a rim quad's material/side.
        back_loops: tessellate the back cap from these loops instead (e.g. without crack slits, so
        cracks become blind grooves closed by the back cap)."""
        mat_back = mat_back or mat
        mat_rim = mat_rim or mat
        if back_loops is not None and caps[1]:
            self.prism(back_loops, d0, d1, axis=axis, mat=mat_back, mat_back=mat_back, side=side, frame=frame,
                       grain=grain, uv_scale=uv_scale, uv_off=uv_off, caps=(False, True), rim_filter=lambda a, b: False)
            caps = (caps[0], False)
        if front_loops is not None and caps[0]:
            self.prism(front_loops, d0, d1, axis=axis, mat=mat, mat_back=mat, side=side, frame=frame,
                       grain=grain, uv_scale=uv_scale, uv_off=uv_off, caps=(True, False), rim_filter=lambda a, b: False)
            caps = (False, caps[1])
        outer = P.ccw(loops[0])
        holes = [P.cw(h) for h in loops[1:]]
        all_loops = [outer] + holes
        pts: list[tuple[float, float, float]] = []
        front_ids: list[list[int]] = []
        back_ids: list[list[int]] = []
        for li, lp in enumerate(all_loops):
            f_ids, b_ids = [], []
            for vi, (a, b) in enumerate(lp):
                e0, e1 = (d0, d1) if depth_fn is None else depth_fn(li, vi, a, b)
                f_ids.append(len(pts))
                pts.append(_map2d(axis, a, b, e0))
                b_ids.append(len(pts))
                pts.append(_map2d(axis, a, b, e1))
            front_ids.append(f_ids)
            back_ids.append(b_ids)
        ax = _axis_vec(axis)
        polys = []
        # Caps: tessellate with every loop counter-clockwise (required by tessellate_polygon for holes).
        tess_loops = [[(a, b, 0.0) for a, b in outer]] + [[(a, b, 0.0) for a, b in reversed(h)] for h in holes]
        flat_index: list[tuple[int, int]] = []
        for li, lp in enumerate(all_loops):
            n = len(lp)
            order = range(n) if li == 0 else [n - 1 - k for k in range(n)]
            for vi in order:
                flat_index.append((li, vi))
        tris = geometry.tessellate_polygon(tess_loops)
        expect = abs(P.area(outer)) - sum(abs(P.area(h)) for h in holes)
        got = 0.0
        for t in tris:
            (a0, b0), (a1, b1), (a2, b2) = [all_loops[flat_index[i][0]][flat_index[i][1]] for i in t]
            got += abs((a1 - a0) * (b2 - b0) - (a2 - a0) * (b1 - b0)) / 2
        if abs(got - expect) > max(1e-6, 0.002 * expect):
            raise ValueError(f"prism tessellation failed (area {got:.5f} != {expect:.5f}) in {self.name}")
        for t in tris:
            ids = [flat_index[i] for i in t]
            f = [front_ids[li][vi] for li, vi in ids]
            b = [back_ids[li][vi] for li, vi in ids]
            fp = [Vector(pts[i]) for i in f]
            if newell(fp).dot(ax) > 0:
                f = list(reversed(f))
            bp = [Vector(pts[i]) for i in b]
            if newell(bp).dot(ax) < 0:
                b = list(reversed(b))
            if caps[0]:
                polys.append((f, mat, side[0], False))
            if caps[1]:
                polys.append((b, mat_back, side[1], False))
        # Rims.
        for li, lp in enumerate(all_loops):
            n = len(lp)
            for vi in range(n):
                vj = (vi + 1) % n
                pa, pb = lp[vi], lp[vj]
                if rim_filter is not None and not rim_filter(pa, pb):
                    continue
                q = [front_ids[li][vi], front_ids[li][vj], back_ids[li][vj], back_ids[li][vi]]
                da, db = pb[0] - pa[0], pb[1] - pa[1]
                out = Vector(_map2d(axis, db, -da, 0.0))  # right normal = out of the region
                qp = [Vector(pts[i]) for i in q]
                if newell(qp).dot(out) < 0:
                    q = list(reversed(q))
                m, s = mat_rim, side[2]
                if rim_mat_fn is not None:
                    o = rim_mat_fn(pa, pb)
                    if o is not None:
                        m, s = o
                polys.append((q, m, s, False))
        self.emit(pts, polys, frame, grain=grain, uv_scale=uv_scale, uv_off=uv_off)

    def lathe(self, profile: list[tuple[float, float]], *, mat: str, segments: int = 12, side="n",
              frame: Matrix | None = None, cap_bottom: bool = True, cap_top: bool = True, smooth: bool = True,
              square: bool = False, axis_u: bool = False) -> None:
        """Surface of revolution around local Z from (radius, z) points (bottom to top).
        square=True makes a 4-sided 'turned' section (square post blocks). axis_u=True puts U along the
        axis (wood grain along turned parts)."""
        segs = 4 if square else segments
        pts = []
        rings = []
        for r, z in profile:
            ring = []
            for i in range(segs):
                a = math.tau * i / segs + (math.pi / 4 if square else 0.0)
                rr = r * (math.sqrt(2) if square else 1.0)
                ring.append(len(pts))
                pts.append((rr * math.cos(a), rr * math.sin(a), z))
            rings.append(ring)
        polys = []
        uvs_per_poly = []
        circ = math.tau * max(r for r, _ in profile)
        for k in range(len(rings) - 1):
            ra, rb = rings[k], rings[k + 1]
            for i in range(segs):
                j = (i + 1) % segs
                polys.append(([ra[i], ra[j], rb[j], rb[i]], mat, side, smooth and not square))
                za, zb = profile[k][1], profile[k + 1][1]
                u0, u1 = circ * i / segs, circ * (i + 1) / segs
                if axis_u:
                    uvs_per_poly.append([(za, u0), (za, u1), (zb, u1), (zb, u0)])
                else:
                    uvs_per_poly.append([(u0, za), (u1, za), (u1, zb), (u0, zb)])
        if cap_bottom and profile[0][0] > 1e-5:
            polys.append((list(reversed(rings[0])), mat, side, False))
            uvs_per_poly.append(None)
        if cap_top and profile[-1][0] > 1e-5:
            polys.append((list(rings[-1]), mat, side, False))
            uvs_per_poly.append(None)
        base = len(self.faces)
        self.emit(pts, polys, frame)
        for k, uvs in enumerate(uvs_per_poly):
            if uvs is not None:
                self.faces[base + k].uvs = uvs

    def hull(self, points, mat: str, *, side="n", frame: Matrix | None = None, grain: str | None = None,
             uv_scale: float = 1.0, uv_off=(0.0, 0.0), mat_fn=None) -> None:
        """Convex hull of local points. mat_fn(normal) -> (mat, side) | None per face."""
        bm = bmesh.new()
        for p in points:
            bm.verts.new(p)
        bmesh.ops.convex_hull(bm, input=list(bm.verts))
        drop = [v for v in bm.verts if not v.link_faces]
        if drop:
            bmesh.ops.delete(bm, geom=drop, context="VERTS")
        loose = [f for f in bm.faces if len(f.verts) < 3]
        if loose:
            bmesh.ops.delete(bm, geom=loose, context="FACES")
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.verts.index_update()
        pts = [tuple(v.co) for v in bm.verts]
        polys = []
        for f in bm.faces:
            m, s = mat, side
            if mat_fn is not None:
                o = mat_fn(f.normal)
                if o is not None:
                    m, s = o
            polys.append(([v.index for v in f.verts], m, s, False))
        bm.free()
        self.emit(pts, polys, frame, grain=grain, uv_scale=uv_scale, uv_off=uv_off)

    def quad(self, corners, mat: str, *, side="n", grain: str | None = None, uvs=None, frame=None,
             uv_scale: float = 1.0) -> None:
        base = len(self.faces)
        self.emit(corners, [(list(range(len(corners))), mat, side, False)], frame, grain=grain, uv_scale=uv_scale)
        if uvs is not None:
            self.faces[base].uvs = list(uvs)

    # -- output ---------------------------------------------------------------------------------
    def build(self, name: str | None = None) -> bpy.types.Object:
        name = name or self.name
        me = bpy.data.meshes.new(name)
        me.from_pydata([tuple(c) for c in self.co], [], [f.verts for f in self.faces])
        obj = common.new_object(name, me)
        slots: dict[str, int] = {}
        for f in self.faces:
            if f.mat not in slots:
                slots[f.mat] = materials.assign(obj, f.mat)
        idx = [slots[f.mat] for f in self.faces]
        me.polygons.foreach_set("material_index", idx)
        me.polygons.foreach_set("use_smooth", [f.smooth for f in self.faces])
        uv0 = me.uv_layers.new(name="UVMap")
        uvs = me.uv_layers.new(name=UV_SIDE)
        flat0, flat1 = [], []
        for f in self.faces:
            for u, v in f.uvs:
                flat0 += (u, v)
                flat1 += (f.side, SIDE_V)
        uv0.data.foreach_set("uv", flat0)
        uvs.data.foreach_set("uv", flat1)
        me.uv_layers.active = uv0
        uv0.active_render = True
        me.update()
        obj["kit_part"] = [f.part for f in self.faces]
        obj["kit_part_values"] = list(self.part_values)
        return obj


# -------------------------------------------------------------------------------------------------
# Vertex colours
# -------------------------------------------------------------------------------------------------

def _hemisphere(n: int) -> list[Vector]:
    """Deterministic cosine-weighted hemisphere (Fibonacci spiral) around +Z."""
    out = []
    ga = math.pi * (3 - math.sqrt(5))
    for i in range(n):
        u = (i + 0.5) / n
        r = math.sqrt(u)
        a = i * ga
        out.append(Vector((r * math.cos(a), r * math.sin(a), math.sqrt(max(0.0, 1 - u)))))
    return out


def _bvh(objects: list[bpy.types.Object], planes: list[tuple[float, float]]) -> BVHTree:
    """BVH of world-space geometry of `objects` + horizontal planes (z, facing) large quads."""
    verts: list[Vector] = []
    polys: list[list[int]] = []
    deps = bpy.context.evaluated_depsgraph_get()
    for o in objects:
        if o.type != "MESH":
            continue
        ev = o.evaluated_get(deps)
        me = ev.to_mesh()
        mw = o.matrix_world
        base = len(verts)
        verts += [mw @ v.co for v in me.vertices]
        polys += [[base + i for i in p.vertices] for p in me.polygons]
        ev.to_mesh_clear()
    for z, _ in planes:
        b = len(verts)
        verts += [Vector(c) for c in ((-60, -60, z), (60, -60, z), (60, 60, z), (-60, 60, z))]
        polys.append([b, b + 1, b + 2, b + 3])
    return BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0)


def bake_colors(obj: bpy.types.Object, *, occluders: list[bpy.types.Object] | None = None,
                ground_z: float | None = 0.0, ceiling_z: float | None = None, samples: int = 20,
                distance: float = 0.5, strength: float = 0.85, wear: bool = True, wear_deg: float = 30.0,
                seed: int = 1, finish_neutral: bool = True, part_values: list[float] | None = None,
                wear_scale: float = 0.3) -> None:
    """Vertex colour 'Color': R = per-corner ray-cast AO (face normals, so large flat faces do not
    smear), G = convex-edge wear (lib.vcolor.bake_wear) scaled by `wear_scale`, B = per-part variation,
    A = 1. Kit parts are small low-poly boxes whose every vertex sits on a convex edge, so an unscaled
    mask would wear whole faces; scaled, std_surface shows wear only when instance_wear is raised.
    Finish faces (M_kit_wall / M_kit_floor) get neutral (1, 0, 0, 1)."""
    me = obj.data
    layer = vcolor.ensure_layer(obj)
    planes = []
    if ground_z is not None:
        planes.append((ground_z - 0.0015, 1))
    if ceiling_z is not None:
        planes.append((ceiling_z + 0.0015, -1))
    tree = _bvh([obj] + list(occluders or []), planes)
    dirs = _hemisphere(samples)
    mw = obj.matrix_world
    nm = mw.to_3x3().inverted().transposed()
    finish = {i for i, m in enumerate(me.materials) if m is not None and m.name[2:] in FINISH_MATS}
    n_loops = len(me.loops)
    cols = [1.0] * (n_loops * 4)
    cache: dict[tuple, float] = {}
    for poly in me.polygons:
        if finish_neutral and poly.material_index in finish:
            for li in poly.loop_indices:
                cols[li * 4 + 0] = 1.0
            continue
        n = (nm @ poly.normal).normalized()
        c = mw @ poly.center
        t = n.orthogonal().normalized()
        b = n.cross(t)
        for li in poly.loop_indices:
            vi = me.loops[li].vertex_index
            key = (vi, round(n.x, 3), round(n.y, 3), round(n.z, 3))
            if key in cache:
                cols[li * 4] = cache[key]
                continue
            p = mw @ me.vertices[vi].co
            p = p + (c - p) * 0.04 + n * 0.0015
            hit = 0.0
            for d in dirs:
                w = (t * d.x + b * d.y + n * d.z)
                loc, _, _, dist = tree.ray_cast(p, w, distance)
                if loc is not None:
                    hit += 1.0 - (dist / distance) * 0.5
            ao = max(0.0, min(1.0, 1.0 - strength * hit / len(dirs)))
            cache[key] = ao
            cols[li * 4] = ao
    # Wear (G) via the shared baker, then restore R and fill B/A.
    if wear:
        layer.data.foreach_set("color", cols)
        vcolor.bake_wear(obj, convex_threshold_deg=wear_deg, noise_scale=6.0, seed=seed)
        g = [0.0] * (n_loops * 4)
        layer.data.foreach_get("color", g)
        for li in range(n_loops):
            cols[li * 4 + 1] = g[li * 4 + 1] * wear_scale
    else:
        for li in range(n_loops):
            cols[li * 4 + 1] = 0.0
    parts = list(obj.get("kit_part", [])) or [0] * len(me.polygons)
    pv = part_values if part_values is not None else list(obj.get("kit_part_values", [0.5]))
    for poly in me.polygons:
        neutral = finish_neutral and poly.material_index in finish
        bval = 0.0 if neutral else pv[parts[poly.index]] if parts[poly.index] < len(pv) else 0.5
        for li in poly.loop_indices:
            if neutral:
                cols[li * 4 + 1] = 0.0
            cols[li * 4 + 2] = bval
            cols[li * 4 + 3] = 1.0
    layer.data.foreach_set("color", cols)
    if "kit_part" in obj:
        del obj["kit_part"]
    if "kit_part_values" in obj:
        del obj["kit_part_values"]


# -------------------------------------------------------------------------------------------------
# Collision proxies, export, fracture fix-up
# -------------------------------------------------------------------------------------------------

def collision_box(name: str, lo, hi, frame: Matrix | None = None) -> bpy.types.Object:
    km = KitMesh(name)
    km.box(lo, hi, "collision", frame=frame)
    o = _bare(km, name + "-convcolonly")
    return o


def collision_hull(name: str, points) -> bpy.types.Object:
    km = KitMesh(name)
    km.hull(points, "collision")
    return _bare(km, name + "-convcolonly")


def collision_mesh(name: str, km_builder) -> bpy.types.Object:
    """Trimesh (static only) collision from a KitMesh filled by km_builder(km)."""
    km = KitMesh(name)
    km_builder(km)
    return _bare(km, name + "-colonly")


def _bare(km: KitMesh, name: str) -> bpy.types.Object:
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(c) for c in km.co], [], [f.verts for f in km.faces])
    me.update()
    return common.new_object(name, me)


def export_glb(path: str, objects: list[bpy.types.Object]) -> None:
    export.export_glb(path, objects)


def fix_chunks(chunks: list[bpy.types.Object], inner_mat: str, *, seed: int = 1, uv_scale: float = 1.0,
               grain: str | None = None) -> None:
    """After lib.fracture.fracture(): outward normals, UV0 + UVSide (0.5) on the inner faces (they are
    created with empty loop data), flat shading and fresh vertex colours."""
    import random
    r = random.Random(seed)
    for ch in chunks:
        me = ch.data
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
        inner = None
        for i, m in enumerate(me.materials):
            if m is not None and m.name == "M_" + inner_mat:
                inner = i
        uv0 = me.uv_layers.get("UVMap")
        uvs = me.uv_layers.get(UV_SIDE)
        off = ch.location.copy()
        for poly in me.polygons:
            poly.use_smooth = False
            if poly.material_index != inner:
                continue
            n = poly.normal
            for li in poly.loop_indices:
                co = me.vertices[me.loops[li].vertex_index].co + off
                if uv0 is not None:
                    uv0.data[li].uv = box_uv(co, n, grain, uv_scale)
                if uvs is not None:
                    uvs.data[li].uv = (SIDE_N, SIDE_V)
        me.update()
        bake_colors(ch, ground_z=None, samples=12, distance=0.3, strength=0.6, wear=True, seed=seed,
                    part_values=[r.uniform(0.3, 0.7)])


def frame(loc=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0), order: str = "XYZ") -> Matrix:
    """Translation @ rotation (Euler radians)."""
    from mathutils import Euler
    return Matrix.Translation(Vector(loc)) @ Euler(rot, order).to_matrix().to_4x4()


def axis_frame(origin, x_axis, y_axis) -> Matrix:
    """Frame whose local X/Y axes map to the given directions (Z = X cross Y)."""
    x = Vector(x_axis).normalized()
    y = Vector(y_axis)
    y = (y - x * y.dot(x)).normalized()
    z = x.cross(y)
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = Vector(origin)
    return m


def noise_seed(seed: int) -> None:
    noise.seed_set(int(seed) % 1000003)
