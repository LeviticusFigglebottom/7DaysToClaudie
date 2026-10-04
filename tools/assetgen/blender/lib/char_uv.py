"""UV projection for character segments (metre-scaled, tiling materials).

Cylindrical around the segment's axis (u = angle * radius, v = distance along the axis) with the
seam placed on a hidden side; faces whose normal runs along the axis (caps, shoulder tops, the
crown, soles) use a planar projection instead. Deterministic, numpy only.
"""
from __future__ import annotations

import math

import numpy as np


def loop_data(obj):
    me = obj.data
    nl = len(me.loops)
    lv = np.zeros(nl, np.int32)
    me.loops.foreach_get("vertex_index", lv)
    V = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get("co", V)
    V = V.reshape(-1, 3)
    ls = np.zeros(len(me.polygons), np.int32)
    lt = np.zeros(len(me.polygons), np.int32)
    me.polygons.foreach_get("loop_start", ls)
    me.polygons.foreach_get("loop_total", lt)
    N = np.zeros(len(me.polygons) * 3)
    me.polygons.foreach_get("normal", N)
    N = N.reshape(-1, 3)
    face_of_loop = np.repeat(np.arange(len(ls)), lt)
    return V, lv, ls, lt, N, face_of_loop


def project(obj, axis_origin, axis_dir, seam_dir, *, planar_threshold: float = 0.8,
            planar_mask=None, box_mask=None, radius: float | None = None) -> None:
    """axis_origin/axis_dir: cylinder axis. seam_dir: direction (perpendicular-ish to the axis)
    where the u seam goes. planar_mask(face_centers) -> bool forces planar projection along the
    axis; box_mask(face_centers) -> bool forces box projection (feet/boots)."""
    me = obj.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uvl = me.uv_layers.active
    V, lv, ls, lt, N, fol = loop_data(obj)
    o = np.asarray(axis_origin, dtype=np.float64)
    a = np.asarray(axis_dir, dtype=np.float64)
    a = a / np.linalg.norm(a)
    sd = np.asarray(seam_dir, dtype=np.float64)
    sd = sd - a * (sd @ a)
    sd /= np.linalg.norm(sd)
    front = -sd                       # angle 0 opposite the seam
    side = np.cross(a, front)
    P = V[lv] - o
    along = P @ a
    x = P @ front
    y = P @ side
    ang = np.arctan2(y, x)            # (-pi, pi], seam at +-pi
    # fix the seam per face: keep each face's angles on the same branch
    nf = len(ls)
    ang_f_ref = ang[ls]
    ref = np.repeat(ang_f_ref, lt)
    ang = np.where(ang - ref > math.pi, ang - 2 * math.pi, np.where(ang - ref < -math.pi, ang + 2 * math.pi, ang))
    if radius is None:
        rr = np.sqrt(x * x + y * y)
        radius = float(np.median(rr)) if len(rr) else 0.05
    u = ang * radius
    v = along
    # planar along the axis for faces facing along it
    Nl = N[fol]
    cosn = np.abs(Nl @ a)
    planar = cosn > planar_threshold
    if planar_mask is not None or box_mask is not None:
        C = np.zeros(nf * 3)
        me.polygons.foreach_get("center", C)
        C = C.reshape(-1, 3)
        if planar_mask is not None:
            planar |= planar_mask(C)[fol]
        boxm = box_mask(C)[fol] if box_mask is not None else np.zeros(len(lv), bool)
    else:
        boxm = np.zeros(len(lv), bool)
    pu = x
    pv = y
    u = np.where(planar, pu + 7.31, u)
    v = np.where(planar, pv + 3.17, v)
    if boxm.any():
        Pw = V[lv]
        dom = np.argmax(np.abs(Nl), axis=1)
        bu = np.where(dom == 0, Pw[:, 1], Pw[:, 0])
        bv = np.where(dom == 2, Pw[:, 1], Pw[:, 2])
        u = np.where(boxm, bu + 11.3, u)
        v = np.where(boxm, bv + 5.7, v)
    uv = np.stack([u, v], -1).astype(np.float32)
    uvl.data.foreach_set("uv", uv.ravel())


def planar(obj, origin, normal, up, scale: float = 1.0, offset=(0.0, 0.0), rect=None) -> None:
    """Planar projection onto the plane (origin, normal) with `up` as +v. With rect=(u0,v0,u1,v1)
    the object's projected bounds map into that atlas rectangle."""
    me = obj.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uvl = me.uv_layers.active
    V, lv, *_ = loop_data(obj)
    n = np.asarray(normal, dtype=np.float64)
    n /= np.linalg.norm(n)
    upv = np.asarray(up, dtype=np.float64)
    upv = upv - n * (upv @ n)
    upv /= np.linalg.norm(upv)
    right = np.cross(upv, n)
    P = V[lv] - np.asarray(origin)
    u = P @ right
    v = P @ upv
    if rect is not None:
        u0, v0, u1, v1 = rect
        umin, umax = u.min(), u.max()
        vmin, vmax = v.min(), v.max()
        span = max(umax - umin, vmax - vmin, 1e-6)
        cu, cv = (umin + umax) / 2, (vmin + vmax) / 2
        u = (u - cu) / span + 0.5
        v = (v - cv) / span + 0.5
        u = u0 + u * (u1 - u0)
        v = v0 + v * (v1 - v0)
    else:
        u = u * scale + offset[0]
        v = v * scale + offset[1]
    uvl.data.foreach_set("uv", np.stack([u, v], -1).astype(np.float32).ravel())
