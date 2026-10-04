"""Vertex colour baking: AO (R), wear/edge mask (G), variation (B), wind weight (A).
See common.py for channel meanings. All functions are deterministic."""
from __future__ import annotations

import math
import random

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ATTR = "Color"


def ensure_layer(obj: bpy.types.Object, fill=(1.0, 0.0, 0.0, 1.0)) -> bpy.types.Attribute:
    me = obj.data
    layer = me.color_attributes.get(ATTR)
    if layer is None:
        layer = me.color_attributes.new(ATTR, "BYTE_COLOR", "CORNER")
        n = len(layer.data)
        layer.data.foreach_set("color", list(fill) * n)
    me.color_attributes.active_color = layer
    try:
        me.color_attributes.render_color_index = me.color_attributes.find(ATTR)
    except AttributeError:
        pass
    return layer


def _hemisphere_dirs(n: int, seed: int = 7) -> list[Vector]:
    r = random.Random(seed)
    dirs = []
    for i in range(n):
        # Cosine-weighted hemisphere samples around +Z (rotated per vertex later).
        u, v = (i + r.random()) / n, r.random()
        phi = 2 * math.pi * v
        rr = math.sqrt(u)
        dirs.append(Vector((rr * math.cos(phi), rr * math.sin(phi), math.sqrt(max(0.0, 1 - u)))))
    return dirs


def bake_ao(objects: list[bpy.types.Object], *, samples: int = 24, distance: float = 1.2, strength: float = 1.0,
            ground: bool = True, extra_occluders: list[bpy.types.Object] | None = None) -> None:
    """Ray-cast ambient occlusion into channel R for every object (occluded by all of them + ground)."""
    deps = bpy.context.evaluated_depsgraph_get()
    occ = list(objects) + list(extra_occluders or [])
    bm_all = bmesh.new()
    for o in occ:
        if o.type != "MESH":
            continue
        tmp = bmesh.new()
        tmp.from_object(o, deps)
        tmp.transform(o.matrix_world)
        me = bpy.data.meshes.new("_tmp_occ")
        tmp.to_mesh(me)
        tmp.free()
        bm_all.from_mesh(me)
        bpy.data.meshes.remove(me)
    if ground:
        # Large ground quad at z=0 so bases darken where they meet the floor.
        vs = [bm_all.verts.new(c) for c in ((-50, -50, -0.001), (50, -50, -0.001), (50, 50, -0.001), (-50, 50, -0.001))]
        bm_all.faces.new(vs)
    tree = BVHTree.FromBMesh(bm_all)
    bm_all.free()
    dirs = _hemisphere_dirs(samples)
    for o in objects:
        if o.type != "MESH":
            continue
        me = o.data
        layer = ensure_layer(o)
        mw = o.matrix_world
        nmat = mw.to_3x3().inverted().transposed()
        vert_ao: list[float] = []
        for v in me.vertices:
            p = mw @ v.co
            n = (nmat @ v.normal).normalized()
            if n.length < 0.5:
                vert_ao.append(1.0)
                continue
            # Build tangent frame.
            t = n.orthogonal().normalized()
            b = n.cross(t)
            hit = 0.0
            origin = p + n * 0.004
            for d in dirs:
                w = (t * d.x + b * d.y + n * d.z).normalized()
                loc, _, _, dist = tree.ray_cast(origin, w, distance)
                if loc is not None:
                    hit += 1.0 - (dist / distance) * 0.5
            ao = 1.0 - strength * hit / len(dirs)
            vert_ao.append(max(0.0, min(1.0, ao)))
        cols = [0.0] * (len(layer.data) * 4)
        layer.data.foreach_get("color", cols)
        for li, loop in enumerate(me.loops):
            cols[li * 4] = vert_ao[loop.vertex_index]
        layer.data.foreach_set("color", cols)


def bake_wear(obj: bpy.types.Object, *, convex_threshold_deg: float = 25.0, noise_scale: float = 3.0, seed: int = 1) -> None:
    """Channel G: 1 on convex edges (where paint chips and wood wears), softened with noise."""
    from mathutils import noise
    me = obj.data
    layer = ensure_layer(obj)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    wear = [0.0] * len(bm.verts)
    lim = math.radians(convex_threshold_deg)
    for e in bm.edges:
        if len(e.link_faces) != 2:
            continue
        f1, f2 = e.link_faces
        ang = f1.normal.angle(f2.normal, 0.0)
        if ang < lim:
            continue
        # Convex if the second face centre lies behind the first face plane.
        c2 = f2.calc_center_median()
        convex = (c2 - f1.calc_center_median()).dot(f1.normal) < 0.0
        if convex:
            amt = min(1.0, ang / math.radians(90))
            for v in e.verts:
                wear[v.index] = max(wear[v.index], amt)
    noise.seed_set(seed)
    for v in bm.verts:
        nval = noise.noise(v.co * noise_scale) * 0.5 + 0.5
        wear[v.index] = max(0.0, min(1.0, wear[v.index] * (0.4 + nval)))
    bm.free()
    cols = [0.0] * (len(layer.data) * 4)
    layer.data.foreach_get("color", cols)
    for li, loop in enumerate(me.loops):
        cols[li * 4 + 1] = wear[loop.vertex_index]
    layer.data.foreach_set("color", cols)


def set_channel(obj: bpy.types.Object, channel: int, fn) -> None:
    """Sets one channel per corner with fn(vertex_co_world: Vector, vertex_normal: Vector, loop_index) -> float."""
    me = obj.data
    layer = ensure_layer(obj)
    cols = [0.0] * (len(layer.data) * 4)
    layer.data.foreach_get("color", cols)
    mw = obj.matrix_world
    for li, loop in enumerate(me.loops):
        v = me.vertices[loop.vertex_index]
        cols[li * 4 + channel] = max(0.0, min(1.0, fn(mw @ v.co, v.normal, li)))
    layer.data.foreach_set("color", cols)


def fill_channel(obj: bpy.types.Object, channel: int, value: float) -> None:
    set_channel(obj, channel, lambda *_: value)
