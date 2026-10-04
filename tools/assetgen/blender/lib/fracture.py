"""Deterministic Voronoi cell fracture (own implementation of the cell-fracture idea).

For each seed point we start from the source mesh and bisect it with the perpendicular bisector
plane against every other seed, keeping the side nearer to our seed and filling the cut. The
cut faces get material M_<inner_material> so broken insides look like raw wood/brick/concrete.
"""
from __future__ import annotations

import random

import bmesh
import bpy
from mathutils import Vector

from .common import new_object
from .materials import assign


def fracture(obj: bpy.types.Object, pieces: int, seed: int, inner_material: str, margin: float = 0.002,
             bias: tuple[float, float, float] = (1.0, 1.0, 1.0)) -> list[bpy.types.Object]:
    """Returns chunk objects (origin at each chunk's centre). The source object is left untouched."""
    me = obj.data
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    zs = [v.co.z for v in me.vertices]
    lo = Vector((min(xs), min(ys), min(zs)))
    hi = Vector((max(xs), max(ys), max(zs)))
    r = random.Random(seed)
    seeds = []
    for _ in range(pieces):
        seeds.append(Vector((
            lo.x + (hi.x - lo.x) * (0.5 + (r.random() - 0.5) * bias[0]),
            lo.y + (hi.y - lo.y) * (0.5 + (r.random() - 0.5) * bias[1]),
            lo.z + (hi.z - lo.z) * (0.5 + (r.random() - 0.5) * bias[2]),
        )))
    chunks = []
    for i, s in enumerate(seeds):
        bm = bmesh.new()
        bm.from_mesh(me)
        for j, t in enumerate(seeds):
            if i == j:
                continue
            normal = (t - s).normalized()
            mid = (s + t) * 0.5 - normal * margin
            geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
            res = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=mid, plane_no=normal, clear_outer=True)
            cut_edges = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
            if cut_edges:
                filled = bmesh.ops.holes_fill(bm, edges=cut_edges, sides=0)
                for f in filled.get("faces", []):
                    f.material_index = 255  # marked, remapped below
        if len(bm.faces) == 0:
            bm.free()
            continue
        cme = bpy.data.meshes.new(f"{obj.name}_chunk_{i:02d}")
        bm.to_mesh(cme)
        bm.free()
        for m in me.materials:
            cme.materials.append(m)
        chunk = new_object(f"chunk_{i:02d}", cme)
        inner = assign(chunk, inner_material)
        for p in cme.polygons:
            if p.material_index >= len(cme.materials) or p.material_index == 255:
                p.material_index = inner
        # Origin at chunk centre so physics debris rotates naturally.
        c = sum((v.co for v in cme.vertices), Vector()) / max(1, len(cme.vertices))
        cme.transform(__import__("mathutils").Matrix.Translation(-c))
        chunk.location = c
        chunks.append(chunk)
    return chunks
