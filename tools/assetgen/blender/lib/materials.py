"""Material slots. Generators only *name* materials (M_<id>); Godot supplies the real material.
The viewport/preview colour here is a rough stand-in so preview renders read correctly."""
from __future__ import annotations

import bpy

# Fallback preview colours (linear RGB) for common material ids; unknown ids get mid grey.
PREVIEW_COLORS: dict[str, tuple[float, float, float]] = {
    "bark_grey_fir": (0.16, 0.12, 0.10), "bark_larch": (0.22, 0.12, 0.08), "bark_birch": (0.75, 0.73, 0.68),
    "bark_dead": (0.25, 0.23, 0.21), "wood_log_end": (0.55, 0.40, 0.25), "foliage_fir": (0.05, 0.12, 0.06),
    "foliage_larch": (0.55, 0.38, 0.06), "foliage_birch": (0.30, 0.38, 0.08), "fern": (0.08, 0.20, 0.05),
    "grass": (0.18, 0.25, 0.08), "rock_granite": (0.35, 0.34, 0.32), "rock_moss": (0.20, 0.26, 0.12),
    "wood_raw": (0.45, 0.32, 0.20), "wood_painted": (0.70, 0.68, 0.62), "wood_dark": (0.20, 0.13, 0.08),
    "metal_painted": (0.30, 0.35, 0.40), "metal_rusty": (0.35, 0.18, 0.08), "metal_steel": (0.55, 0.56, 0.58),
    "plastic": (0.60, 0.60, 0.58), "fabric": (0.35, 0.30, 0.28), "glass": (0.60, 0.70, 0.72),
    "paper": (0.85, 0.82, 0.74), "ceramic": (0.85, 0.85, 0.82), "concrete": (0.50, 0.50, 0.48),
    "brick": (0.45, 0.20, 0.14), "skin_hollow": (0.55, 0.52, 0.47), "cloth_denim": (0.12, 0.16, 0.26),
    "cloth_flannel": (0.40, 0.10, 0.08), "blood": (0.25, 0.02, 0.02), "stone_river": (0.40, 0.40, 0.38),
    "rope": (0.55, 0.45, 0.30), "leather": (0.30, 0.18, 0.10),
}


def material(mat_id: str) -> bpy.types.Material:
    name = f"M_{mat_id}"
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
        col = PREVIEW_COLORS.get(mat_id, (0.5, 0.5, 0.5))
        mat.diffuse_color = (*col, 1.0)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf is not None:
            bsdf.inputs["Base Color"].default_value = (*col, 1.0)
            bsdf.inputs["Roughness"].default_value = 0.8
            if mat_id.startswith("metal_steel"):
                bsdf.inputs["Metallic"].default_value = 1.0
                bsdf.inputs["Roughness"].default_value = 0.45
            # Preview: show vertex AO (R channel) multiplied into base colour.
            nt = mat.node_tree
            attr = nt.nodes.new("ShaderNodeVertexColor")
            attr.layer_name = "Color"
            sep = nt.nodes.new("ShaderNodeSeparateColor")
            mul = nt.nodes.new("ShaderNodeMix")
            mul.data_type = "RGBA"
            mul.blend_type = "MULTIPLY"
            mul.inputs[0].default_value = 1.0
            mul.inputs[6].default_value = (*col, 1.0)
            nt.links.new(attr.outputs["Color"], sep.inputs[0])
            comb = nt.nodes.new("ShaderNodeCombineColor")
            nt.links.new(sep.outputs[0], comb.inputs[0])
            nt.links.new(sep.outputs[0], comb.inputs[1])
            nt.links.new(sep.outputs[0], comb.inputs[2])
            nt.links.new(comb.outputs[0], mul.inputs[7])
            nt.links.new(mul.outputs[2], bsdf.inputs["Base Color"])
        if mat_id.startswith("foliage") or mat_id in ("fern", "grass"):
            mat.blend_method = "CLIP" if hasattr(mat, "blend_method") else None
    return mat


def assign(obj: bpy.types.Object, mat_id: str) -> int:
    """Adds the material to the object (if missing) and returns its slot index."""
    mat = material(mat_id)
    for i, slot in enumerate(obj.data.materials):
        if slot == mat:
            return i
    obj.data.materials.append(mat)
    return len(obj.data.materials) - 1


def assign_all(obj: bpy.types.Object, mat_id: str) -> None:
    idx = assign(obj, mat_id)
    for p in obj.data.polygons:
        p.material_index = idx
