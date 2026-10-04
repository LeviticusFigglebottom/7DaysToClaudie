"""bmesh primitive builders (deterministic, return BMesh or Object)."""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from .common import mesh_from_bmesh


def box(name: str, size: tuple[float, float, float], center: tuple[float, float, float] = (0, 0, 0),
        bevel: float = 0.0, bevel_segments: int = 1) -> bpy.types.Object:
    """Axis-aligned box; `center` is the box centre. Optional bevel for softer silhouettes."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    bmesh.ops.translate(bm, vec=Vector(center), verts=bm.verts)
    if bevel > 0.0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=bevel_segments, affect="EDGES", profile=0.5)
    return mesh_from_bmesh(name, bm)


def cylinder(name: str, radius: float, depth: float, segments: int = 12, center: tuple[float, float, float] = (0, 0, 0),
             axis: str = "Z", radius_top: float | None = None, cap: bool = True) -> bpy.types.Object:
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=segments, radius1=radius,
                          radius2=radius if radius_top is None else radius_top, depth=depth)
    if axis == "X":
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "Y"))
    elif axis == "Y":
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "X"))
    bmesh.ops.translate(bm, vec=Vector(center), verts=bm.verts)
    return mesh_from_bmesh(name, bm)


def sphere(name: str, radius: float, subdiv: int = 2, center: tuple[float, float, float] = (0, 0, 0)) -> bpy.types.Object:
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=radius)
    bmesh.ops.translate(bm, vec=Vector(center), verts=bm.verts)
    return mesh_from_bmesh(name, bm)


def quad(name: str, width: float, height: float, center=(0, 0, 0), facing: str = "-Y") -> bpy.types.Object:
    """Single quad (e.g. foliage card / decal). facing = normal direction."""
    w, h = width / 2, height / 2
    bm = bmesh.new()
    if facing in ("-Y", "+Y"):
        pts = [(-w, 0, -h), (w, 0, -h), (w, 0, h), (-w, 0, h)]
    elif facing in ("-X", "+X"):
        pts = [(0, -w, -h), (0, w, -h), (0, w, h), (0, -w, h)]
    else:
        pts = [(-w, -h, 0), (w, -h, 0), (w, h, 0), (-w, h, 0)]
    vs = [bm.verts.new(Vector(p) + Vector(center)) for p in pts]
    f = bm.faces.new(vs)
    f.normal_update()
    want = {"-Y": Vector((0, -1, 0)), "+Y": Vector((0, 1, 0)), "-X": Vector((-1, 0, 0)), "+X": Vector((1, 0, 0)),
            "+Z": Vector((0, 0, 1)), "-Z": Vector((0, 0, -1))}[facing]
    if f.normal.dot(want) < 0:
        f.normal_flip()
    return mesh_from_bmesh(name, bm)


def lathe(name: str, profile: list[tuple[float, float]], segments: int = 16, cap_bottom: bool = True,
          cap_top: bool = True) -> bpy.types.Object:
    """Surface of revolution around Z from (radius, z) profile points (bottom to top)."""
    bm = bmesh.new()
    rings = []
    for r, z in profile:
        ring = []
        for i in range(segments):
            a = 2 * math.pi * i / segments
            ring.append(bm.verts.new((r * math.cos(a), r * math.sin(a), z)))
        rings.append(ring)
    for a, b in zip(rings[:-1], rings[1:]):
        for i in range(segments):
            j = (i + 1) % segments
            bm.faces.new((a[i], a[j], b[j], b[i]))
    if cap_bottom and profile[0][0] > 1e-5:
        bm.faces.new(list(reversed(rings[0])))
    if cap_top and profile[-1][0] > 1e-5:
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_from_bmesh(name, bm)


def displace(obj: bpy.types.Object, amount: float, scale: float = 1.0, seed: int = 0, octaves: int = 3) -> None:
    """Noise displacement along vertex normals (deterministic: mathutils.noise with seed)."""
    from mathutils import noise
    noise.seed_set(seed)
    me = obj.data
    me.update()
    for v in me.vertices:
        n = noise.fractal(v.co * scale, 0.5, 2.0, octaves, noise_basis="PERLIN_ORIGINAL")
        v.co += v.normal * n * amount
    me.update()


def subdivide(obj: bpy.types.Object, cuts: int = 1, smooth: float = 0.0) -> None:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.subdivide_edges(bm, edges=list(bm.edges), cuts=cuts, use_grid_fill=True, smooth=smooth)
    bm.to_mesh(obj.data)
    bm.free()
