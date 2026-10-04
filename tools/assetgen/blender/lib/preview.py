"""Preview renders for visual QA (Cycles CPU, works headless without a GPU).

    preview.render_preview(objects, "/path/out.png")
Renders a 3/4 view on a neutral ground with sun + sky fill. Generators call this only when
params["preview"] is set (the orchestrator never does), e.g. from the dev helper:
    blender -b --factory-startup --python tools/assetgen/blender/dev_preview.py -- <module> '<params json>' out.png
"""
from __future__ import annotations

import math

import bpy
from mathutils import Vector


def render_preview(objects: list[bpy.types.Object], out_path: str, *, size: tuple[int, int] = (640, 480),
                   samples: int = 24, angle_deg: float = 35.0, elevation_deg: float = 20.0, ground: bool = True) -> None:
    scene = bpy.context.scene
    meshes = [o for o in objects if o.type == "MESH"]
    vs = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
    lo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
    hi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
    center = (lo + hi) / 2
    radius = max((hi - lo).length / 2, 0.1)
    cam_data = bpy.data.cameras.new("PreviewCam")
    cam_data.lens = 50
    cam = bpy.data.objects.new("PreviewCam", cam_data)
    scene.collection.objects.link(cam)
    a, e = math.radians(angle_deg), math.radians(elevation_deg)
    dist = radius / math.tan(math.radians(18)) * 1.15
    cam.location = center + Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * dist
    cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    sun = bpy.data.objects.new("PreviewSun", bpy.data.lights.new("PreviewSun", "SUN"))
    sun.data.energy = 3.5
    sun.data.angle = math.radians(6)
    sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(-35))
    scene.collection.objects.link(sun)
    world = bpy.data.worlds.new("PreviewWorld")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (0.55, 0.6, 0.68, 1.0)
    bg.inputs[1].default_value = 0.6
    scene.world = world
    if ground:
        bpy.ops.mesh.primitive_plane_add(size=radius * 12, location=(center.x, center.y, lo.z - 0.001))
        g = bpy.context.active_object
        gm = bpy.data.materials.new("PreviewGround")
        gm.diffuse_color = (0.25, 0.25, 0.24, 1)
        gm.use_nodes = True
        gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.22, 0.22, 0.2, 1)
        g.data.materials.append(gm)
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = size
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "AgX" if "AgX" in [i.identifier for i in scene.view_settings.bl_rna.properties["view_transform"].enum_items] else "Filmic"
    scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
