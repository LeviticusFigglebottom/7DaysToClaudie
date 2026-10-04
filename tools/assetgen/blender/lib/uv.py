"""Context-free UV projection helpers (no edit-mode operators, deterministic)."""
from __future__ import annotations

import math

import bpy
from mathutils import Vector


def _uv_layer(me: bpy.types.Mesh, name: str = "UVMap"):
    if not me.uv_layers:
        me.uv_layers.new(name=name)
    return me.uv_layers.active


def box_project(obj: bpy.types.Object, scale: float = 1.0, offset: tuple[float, float] = (0.0, 0.0), world: bool = False) -> None:
    """Tri-planar box mapping: each face projected on its dominant axis. 1 UV unit = 1/scale metres.
    With world=True uses world coordinates (seamless across separate pieces)."""
    me = obj.data
    uvl = _uv_layer(me)
    mw = obj.matrix_world if world else None
    for p in me.polygons:
        n = p.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if mw is not None:
                co = mw @ co
            if ax == 0:
                u, v = (co.y if n.x > 0 else -co.y), co.z
            elif ax == 1:
                u, v = (-co.x if n.y > 0 else co.x), co.z
            else:
                u, v = co.x, (co.y if n.z > 0 else -co.y)
            uvl.data[li].uv = (u * scale + offset[0], v * scale + offset[1])


def cylinder_project(obj: bpy.types.Object, radius_scale: float = 1.0, height_scale: float = 1.0,
                     axis: str = "Z", u_repeats: float | None = None) -> None:
    """Cylindrical mapping around an axis (bark, logs, pipes). u wraps around, v runs along axis.
    u_repeats: if set, u spans [0, u_repeats) around the circumference; else uses arc length * radius_scale."""
    me = obj.data
    uvl = _uv_layer(me)
    ai = "XYZ".index(axis)
    oi = [i for i in range(3) if i != ai]
    for p in me.polygons:
        angs = []
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            angs.append(math.atan2(co[oi[1]], co[oi[0]]))
        # Fix the seam: keep a face's angles on the same side.
        ref = angs[0]
        fixed = [a + (2 * math.pi if a - ref < -math.pi else (-2 * math.pi if a - ref > math.pi else 0.0)) for a in angs]
        for k, li in enumerate(p.loop_indices):
            co = me.vertices[me.loops[li].vertex_index].co
            r = math.hypot(co[oi[0]], co[oi[1]])
            t = fixed[k] / (2 * math.pi) + 0.5
            u = t * u_repeats if u_repeats is not None else t * 2 * math.pi * max(r, 0.01) * radius_scale
            uvl.data[li].uv = (u, co[ai] * height_scale)


def planar_project(obj: bpy.types.Object, axis: str = "Z", scale: float = 1.0, rect: tuple[float, float, float, float] | None = None) -> None:
    """Planar mapping along an axis. rect=(u0, v0, u1, v1) maps the object's bounds into an atlas region."""
    me = obj.data
    uvl = _uv_layer(me)
    ai = "XYZ".index(axis)
    oi = [i for i in range(3) if i != ai]
    if rect is not None:
        xs = [v.co[oi[0]] for v in me.vertices]
        ys = [v.co[oi[1]] for v in me.vertices]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    for li, loop in enumerate(me.loops):
        co = me.vertices[loop.vertex_index].co
        if rect is None:
            uvl.data[li].uv = (co[oi[0]] * scale, co[oi[1]] * scale)
        else:
            u = (co[oi[0]] - x0) / max(1e-6, x1 - x0)
            v = (co[oi[1]] - y0) / max(1e-6, y1 - y0)
            uvl.data[li].uv = (rect[0] + u * (rect[2] - rect[0]), rect[1] + v * (rect[3] - rect[1]))
