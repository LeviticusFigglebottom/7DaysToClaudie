"""glTF export with the project's fixed settings (deterministic, no embedded images)."""
from __future__ import annotations

import pathlib

import bpy


def export_glb(path: str, objects: list[bpy.types.Object] | None = None, *, animations: bool = False,
               skins: bool = False) -> None:
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    if objects is not None:
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        for o in objects:
            o.select_set(True)
        bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        use_selection=objects is not None,
        export_yup=True,
        export_apply=True,
        export_texcoords=True,
        export_normals=True,
        export_tangents=False,
        export_vertex_color="ACTIVE",
        export_all_vertex_colors=False,
        export_materials="EXPORT",
        export_image_format="NONE",
        export_cameras=False,
        export_lights=False,
        export_extras=False,
        export_animations=animations,
        export_skins=skins,
        export_morph=False,
        export_animation_mode="ACTIONS",
        export_force_sampling=True,
        export_def_bones=skins,
        export_leaf_bone=False,
    )
