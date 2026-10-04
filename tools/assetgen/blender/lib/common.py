"""Shared helpers for Blender generators (run inside Blender's Python).

CONVENTIONS (docs/ASSET_PIPELINE.md#conventions) — every generator must follow them:
  * Units are metres, real-world scale. Blender is Z-up.
  * The FRONT of an asset faces Blender -Y (becomes Godot +Z = Vector3.MODEL_FRONT).
  * Origin = bottom centre of the footprint (ground contact). Wall-mounted props: origin on the
    wall plane, bottom centre, front facing away from the wall (-Y).
  * Materials are named "M_<material_id>"; Godot swaps them for res://assets/materials/<material_id>.tres
    on import (src/tools/import/generated_scene_post_import.gd). Do not embed images.
  * Vertex colour attribute "Color" (exported as COLOR_0):
        R = ambient occlusion (1 = open, 0 = occluded)
        G = wear / edge mask (1 = worn edge)       — drives clean/worn/destroyed looks
        B = per-part variation / tint mask (0..1)
        A = wind weight for foliage (0 = rigid base, 1 = free tip); 1.0 for non-foliage
  * Collision proxies: separate low-poly objects named "<name>-convcolonly" (convex) or
    "<name>-colonly" (trimesh). Keep proxies simple (boxes / hulls).
  * Everything random goes through seeded RNG (rng(seed)) — no time, no unseeded random.
"""
from __future__ import annotations

import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector


def rng(seed: int | str) -> random.Random:
    return random.Random(str(seed))


def clear_scene() -> None:
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.curves, bpy.data.armatures, bpy.data.actions):
        for block in list(coll):
            if block.users == 0:
                coll.remove(block)


def new_object(name: str, mesh: bpy.types.Mesh | None = None, collection: bpy.types.Collection | None = None) -> bpy.types.Object:
    if mesh is None:
        mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    (collection or bpy.context.scene.collection).objects.link(obj)
    return obj


def mesh_from_bmesh(name: str, bm: bmesh.types.BMesh) -> bpy.types.Object:
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.update()
    return new_object(name, me)


def set_active(obj: bpy.types.Object) -> None:
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)


def apply_transforms(obj: bpy.types.Object) -> None:
    """Bake location/rotation/scale into mesh data (keeps world position at origin)."""
    if obj.type != "MESH":
        return
    obj.data.transform(obj.matrix_basis)
    obj.matrix_basis = Matrix.Identity(4)


def apply_modifiers(obj: bpy.types.Object) -> None:
    if obj.type != "MESH" or not obj.modifiers:
        return
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=deps)
    old = obj.data
    obj.modifiers.clear()
    obj.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)


def join(objects: list[bpy.types.Object], name: str) -> bpy.types.Object:
    """Joins mesh objects into one (materials and attributes merged)."""
    objects = [o for o in objects if o is not None]
    for o in objects:
        apply_modifiers(o)
    set_active(objects[0])
    for o in objects[1:]:
        o.select_set(True)
    with bpy.context.temp_override(active_object=objects[0], selected_editable_objects=objects, object=objects[0]):
        bpy.ops.object.join()
    objects[0].name = name
    objects[0].data.name = name
    return objects[0]


def origin_to_bottom_center(obj: bpy.types.Object) -> None:
    """Moves mesh so its bounding box bottom-centre sits at the object origin (0,0,0)."""
    me = obj.data
    if not me.vertices:
        return
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    zs = [v.co.z for v in me.vertices]
    offset = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, min(zs)))
    me.transform(Matrix.Translation(-offset))
    obj.location = (0, 0, 0)


def shade_smooth(obj: bpy.types.Object, angle_deg: float | None = 40.0) -> None:
    """Smooth shading; with angle_deg, faces sharper than that stay flat (auto smooth by angle)."""
    me = obj.data
    for p in me.polygons:
        p.use_smooth = True
    if angle_deg is not None:
        # Mark sharp edges by angle so the exporter splits normals there.
        bm = bmesh.new()
        bm.from_mesh(me)
        lim = math.radians(angle_deg)
        for e in bm.edges:
            if len(e.link_faces) == 2:
                a = e.link_faces[0].normal.angle(e.link_faces[1].normal, 0.0)
                e.smooth = a < lim
            else:
                e.smooth = True
        bm.to_mesh(me)
        bm.free()
    me.update()


def shade_flat(obj: bpy.types.Object) -> None:
    for p in obj.data.polygons:
        p.use_smooth = False


def triangle_count(obj: bpy.types.Object) -> int:
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def total_triangles(objects: list[bpy.types.Object]) -> int:
    return sum(triangle_count(o) for o in objects if o.type == "MESH")


def bounds(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    vs = [obj.matrix_world @ v.co for v in obj.data.vertices]
    lo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
    hi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
    return lo, hi


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def smoothstep(e0: float, e1: float, x: float) -> float:
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0) if e1 != e0 else 0.0))
    return t * t * (3 - 2 * t)
