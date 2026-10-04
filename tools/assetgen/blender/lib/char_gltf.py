"""glTF export helpers for characters.

Blender 5.2's glTF exporter has no option to write node visibility, but the contract wants the
stump caps hidden by default. The exporter calls `gather_node_hook` on user extensions found on
registered add-on modules; `hidden_nodes()` temporarily registers this module as such an add-on
so `stump_*` nodes get `KHR_node_visibility: {visible: false}` (read by Godot's glTF importer).
Export itself still goes through lib.export.export_glb().
"""
from __future__ import annotations

import contextlib
import sys

import bpy

_HIDDEN_PREFIXES: tuple[str, ...] = ()
MODULE_KEY = __name__


class glTF2ExportUserExtension:  # noqa: N801 - name required by the glTF exporter
    def __init__(self):
        from io_scene_gltf2.io.com.gltf2_io_extensions import Extension
        self.Extension = Extension

    def gather_node_hook(self, gltf2_object, blender_object, export_settings):
        if blender_object is None or not _HIDDEN_PREFIXES:
            return
        if blender_object.name.startswith(_HIDDEN_PREFIXES):
            if gltf2_object.extensions is None:
                gltf2_object.extensions = {}
            gltf2_object.extensions["KHR_node_visibility"] = self.Extension(
                name="KHR_node_visibility", extension={"visible": False}, required=False)


@contextlib.contextmanager
def hidden_nodes(prefixes: tuple[str, ...]):
    """Within the block, nodes whose names start with `prefixes` export as invisible."""
    global _HIDDEN_PREFIXES
    prefs = bpy.context.preferences
    sys.modules.setdefault(MODULE_KEY, sys.modules[__name__])
    addon = prefs.addons.get(MODULE_KEY)
    created = False
    if addon is None:
        addon = prefs.addons.new()
        addon.module = MODULE_KEY
        created = True
    _HIDDEN_PREFIXES = tuple(prefixes)
    try:
        yield
    finally:
        _HIDDEN_PREFIXES = ()
        if created:
            prefs.addons.remove(addon)
