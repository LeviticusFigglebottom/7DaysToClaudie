"""LOD helpers: decimated copies for explicit LOD meshes (vegetation, large props)."""
from __future__ import annotations

import bpy

from .common import apply_modifiers, new_object


def decimated_copy(obj: bpy.types.Object, ratio: float, name: str) -> bpy.types.Object:
    me = obj.data.copy()
    me.name = name
    c = new_object(name, me)
    c.matrix_world = obj.matrix_world.copy()
    mod = c.modifiers.new("dec", "DECIMATE")
    mod.ratio = max(0.01, min(1.0, ratio))
    mod.use_collapse_triangulate = True
    apply_modifiers(c)
    return c
