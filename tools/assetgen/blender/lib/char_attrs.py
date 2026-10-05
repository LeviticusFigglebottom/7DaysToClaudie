"""Per-vertex shader data for character meshes (ADR-0028), written as extra UV layers that the
glTF exporter writes as TEXCOORD_1..5 and Godot imports as UV2 and CUSTOM0 / CUSTOM1:

  UV2      rest-pose position x, y      (Godot object space = Blender (x, z, -y), metres)
  CUSTOM0  rest-pose z, gate, wet, bruise
  CUSTOM1  trim, seam, paint, edge      (signed distances in metres; FAR = nothing near)

The skin and cloth shaders (game/assets/shaders/character.gdshaderinc) pattern veins, mottling,
seams and paint from the rest pose, so the patterns stay put on a moving body. Distances (not
masks) carry the marks: a distance interpolates linearly across a triangle, so a 3 mm seam stays a
crisp line on triangles a few centimetres across, where a 0/1 mask would smear into a band.

Gate codes (the shader hides gated-out geometry per instance): 0 always, 1 from the Seeded tier up,
2 Bloomed only, 4 an intact pustule (gone once burst), 5 a burst crater (only once burst).
"""
from __future__ import annotations

import numpy as np

LAYERS = ("rest_xy", "rest_z_gate", "wet_bruise", "trim_seam", "paint_edge")
FAR = 1.0
GATE_ALWAYS, GATE_SEEDED, GATE_BLOOMED, GATE_PUSTULE, GATE_BURST = 0.0, 1.0, 2.0, 4.0, 5.0


class Fields:
    """Per-vertex channels for one mesh (defaults: nothing marked)."""

    def __init__(self, n: int):
        self.gate = np.zeros(n)
        self.wet = np.zeros(n)
        self.bruise = np.zeros(n)
        self.trim = np.full(n, FAR)
        self.seam = np.full(n, FAR)
        self.paint = np.full(n, FAR)
        self.edge = np.full(n, FAR)


def rest_godot(V: np.ndarray) -> np.ndarray:
    """Blender (x, y, z) -> Godot object space (x, z, -y)."""
    return np.stack([V[:, 0], V[:, 2], -V[:, 1]], -1)


def write(obj, V: np.ndarray, f: Fields) -> None:
    """Adds the five layers after the material UV map (which must exist and stay first)."""
    me = obj.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    first = me.uv_layers[0].name
    for nm in LAYERS:
        if me.uv_layers.get(nm) is None:
            me.uv_layers.new(name=nm)
    me.uv_layers.active = me.uv_layers[first]
    try:
        me.uv_layers[first].active_render = True
    except AttributeError:
        pass
    lv = np.zeros(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", lv)
    R = rest_godot(V)
    pairs = {
        "rest_xy": (R[:, 0], R[:, 1]),
        "rest_z_gate": (R[:, 2], f.gate),
        "wet_bruise": (f.wet, f.bruise),
        "trim_seam": (f.trim, f.seam),
        "paint_edge": (f.paint, f.edge),
    }
    for nm, (a, b) in pairs.items():
        uv = np.empty((len(lv), 2), np.float32)
        uv[:, 0] = np.asarray(a, np.float64)[lv]
        # glTF flips V (v' = 1 - v): pre-flip so Godot reads the value itself.
        uv[:, 1] = 1.0 - np.asarray(b, np.float64)[lv]
        me.uv_layers[nm].data.foreach_set("uv", uv.ravel())


def signed_min(*fields: np.ndarray) -> np.ndarray:
    """Per point, the signed distance with the smallest magnitude (the nearest mark wins)."""
    st = np.stack(fields, 0)
    idx = np.argmin(np.abs(st), 0)
    return np.take_along_axis(st, idx[None], 0)[0]
