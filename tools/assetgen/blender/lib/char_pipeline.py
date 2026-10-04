"""Segment meshing pipeline: SDF -> surface nets -> projection -> part-wise decimation -> labels.

Used by every character generator (bodies, gibs, first-person arms).
"""
from __future__ import annotations

import numpy as np
import bpy

from . import char_mesh as M
from . import common


def coarse_field(model, h: float = 0.012, pad: float = 0.06):
    """Full-body distance field on a coarse grid (no segmentation) for bounds queries."""
    lo, hi = model.skin.bounds()
    for prog in (model.boots, model.hair, model.growth):
        if prog.ops:
            l2, h2 = prog.bounds()
            lo, hi = np.minimum(lo, l2), np.maximum(hi, h2)
    lo = lo - pad
    hi = hi + pad
    shape = tuple(int(x) for x in np.ceil((hi - lo) / h) + 1)
    d, _ = model.eval_grid(lo, h, shape, None, narrow=False)
    axes = [lo[a] + np.arange(shape[a]) * h for a in range(3)]
    gx, gy, gz = np.meshgrid(*axes, indexing="ij")
    P = np.stack([gx.ravel(), gy.ravel(), gz.ravel()], -1)
    return {"d": d.ravel(), "P": P, "h": h}


def segment_bounds(model, coarse, seg: str, margin: float = 0.02):
    P, d = coarse["P"], coarse["d"]
    sel = np.nonzero(d < coarse["h"] * 1.5 + margin)[0]
    Ps = P[sel]
    r = model.region(Ps, seg)
    ds = np.maximum(d[sel], r - 0.009)
    keep = ds < coarse["h"] * 1.2
    if seg == "body_head" and model.hair.ops:
        dh, _ = model.hair.eval(Ps)
        keep |= dh < coarse["h"] * 1.2
    Pk = Ps[keep]
    if len(Pk) == 0:
        return None
    return Pk.min(0) - margin, Pk.max(0) + margin


def mesh_segment(model, seg: str, h: float, lo, hi, name: str | None = None):
    """Returns a Blender object of the full-resolution surface for segment `seg`."""
    lo = np.asarray(lo, dtype=np.float64)
    hi = np.asarray(hi, dtype=np.float64)
    shape = tuple(int(x) for x in np.ceil((hi - lo) / h) + 1)
    d, _ = model.eval_grid(lo, h, shape, seg)
    V, Q = M.surface_nets(d, lo, h)
    del d
    V = M.project_to_surface(V, lambda P: model.eval_points(P, seg)[0], h, iterations=2)
    obj = M.mesh_from_arrays(name or seg, V, Q)
    M.remove_small_islands(obj)
    return obj


def decimate_parts(obj, parts: list[tuple], total_target: int) -> None:
    """parts: list of (mask_fn(P)->bool array, target_tris). Remaining faces form the last part
    with the leftover budget. Each pass locks every vertex outside its part."""
    for mask_fn, target in parts:
        V = M.mesh_arrays(obj)
        inpart = mask_fn(V)
        faces = _face_vertex_arrays(obj)
        fin = np.array([inpart[f].mean() > 0.5 for f in faces]) if faces else np.zeros(0, bool)
        cur_part = int(sum(len(f) - 2 for f, m in zip(faces, fin) if m))
        total = common.triangle_count(obj)
        if cur_part <= target:
            continue
        goal = total - (cur_part - target)
        lock = (~inpart).astype(np.float64)
        M.decimate(obj, goal, protect=lock)
    # rest
    V = M.mesh_arrays(obj)
    total = common.triangle_count(obj)
    if total > total_target:
        allmask = np.zeros(len(V), bool)
        for mask_fn, _ in parts:
            allmask |= mask_fn(V)
        rest_lock = allmask.astype(np.float64)
        M.decimate(obj, total_target, protect=rest_lock if allmask.any() else None)


def _face_vertex_arrays(obj):
    me = obj.data
    ls = np.zeros(len(me.polygons), np.int32)
    lt = np.zeros(len(me.polygons), np.int32)
    me.polygons.foreach_get("loop_start", ls)
    me.polygons.foreach_get("loop_total", lt)
    lv = np.zeros(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", lv)
    return [lv[a:a + b] for a, b in zip(ls, lt)]


def label_faces(model, obj, seg: str) -> np.ndarray:
    C = M.face_centers(obj)
    N = M.face_normals(obj)
    # sample just inside the surface so the label is the one owning the surface
    _, lab = model.eval_points(C - N * 0.0008, seg)
    return lab
