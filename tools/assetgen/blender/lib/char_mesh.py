"""Meshing helpers for characters: surface nets on SDF grids, surface projection, Blender mesh
construction from arrays, decimation with protected regions, label->material assignment.

All functions are deterministic (pure numpy + Blender's deterministic modifiers).
"""
from __future__ import annotations

import numpy as np
import bpy

from . import common, materials


def surface_nets(d: np.ndarray, origin, h: float):
    """Naive surface nets. d: (nx,ny,nz) signed distances (negative inside).
    Returns verts (V,3) world coords and quads (F,4) int indices with outward winding."""
    origin = np.asarray(origin, dtype=np.float64)
    nx, ny, nz = d.shape
    inside = d < 0.0
    cshape = (nx - 1, ny - 1, nz - 1)
    S = np.zeros(cshape + (3,), np.float64)
    C = np.zeros(cshape, np.int32)

    def crossing(d0, d1):
        den = d0 - d1
        den = np.where(np.abs(den) < 1e-12, 1e-12, den)
        return np.clip(d0 / den, 0.0, 1.0)

    # x edges
    cx = inside[:-1] != inside[1:]
    tx = np.where(cx, crossing(d[:-1], d[1:]), 0.0)
    ii, jj, kk = np.meshgrid(np.arange(nx - 1), np.arange(ny), np.arange(nz), indexing="ij")
    Ex = np.stack([ii + tx, jj.astype(np.float64), kk.astype(np.float64)], -1) * cx[..., None]
    Cx = cx.astype(np.int32)
    S += Ex[:, :-1, :-1] + Ex[:, 1:, :-1] + Ex[:, :-1, 1:] + Ex[:, 1:, 1:]
    C += Cx[:, :-1, :-1] + Cx[:, 1:, :-1] + Cx[:, :-1, 1:] + Cx[:, 1:, 1:]
    del Ex, ii, jj, kk
    # y edges
    cy = inside[:, :-1] != inside[:, 1:]
    ty = np.where(cy, crossing(d[:, :-1], d[:, 1:]), 0.0)
    ii, jj, kk = np.meshgrid(np.arange(nx), np.arange(ny - 1), np.arange(nz), indexing="ij")
    Ey = np.stack([ii.astype(np.float64), jj + ty, kk.astype(np.float64)], -1) * cy[..., None]
    Cy = cy.astype(np.int32)
    S += Ey[:-1, :, :-1] + Ey[1:, :, :-1] + Ey[:-1, :, 1:] + Ey[1:, :, 1:]
    C += Cy[:-1, :, :-1] + Cy[1:, :, :-1] + Cy[:-1, :, 1:] + Cy[1:, :, 1:]
    del Ey, ii, jj, kk
    # z edges
    cz = inside[:, :, :-1] != inside[:, :, 1:]
    tz = np.where(cz, crossing(d[:, :, :-1], d[:, :, 1:]), 0.0)
    ii, jj, kk = np.meshgrid(np.arange(nx), np.arange(ny), np.arange(nz - 1), indexing="ij")
    Ez = np.stack([ii.astype(np.float64), jj.astype(np.float64), kk + tz], -1) * cz[..., None]
    Cz = cz.astype(np.int32)
    S += Ez[:-1, :-1, :] + Ez[1:, :-1, :] + Ez[:-1, 1:, :] + Ez[1:, 1:, :]
    C += Cz[:-1, :-1, :] + Cz[1:, :-1, :] + Cz[:-1, 1:, :] + Cz[1:, 1:, :]
    del Ez, ii, jj, kk

    active = C > 0
    vid = np.full(cshape, -1, np.int64)
    nv = int(active.sum())
    vid[active] = np.arange(nv)
    verts = origin + h * (S[active] / C[active][:, None])

    quads = []
    # x-edge faces: cells (i, j-1, k-1), (i, j, k-1), (i, j, k), (i, j-1, k)
    e = cx[:, 1:ny - 1, 1:nz - 1]
    I, J, K = np.nonzero(e)
    J = J + 1
    K = K + 1
    if len(I):
        q = np.stack([vid[I, J - 1, K - 1], vid[I, J, K - 1], vid[I, J, K], vid[I, J - 1, K]], -1)
        flip = ~inside[I, J, K]  # outside at low x -> normal points -x
        q[flip] = q[flip][:, ::-1]
        quads.append(q)
    # y-edge faces: cells (i-1, j, k-1), (i-1, j, k), (i, j, k), (i, j, k-1)
    e = cy[1:nx - 1, :, 1:nz - 1]
    I, J, K = np.nonzero(e)
    I = I + 1
    K = K + 1
    if len(I):
        q = np.stack([vid[I - 1, J, K - 1], vid[I - 1, J, K], vid[I, J, K], vid[I, J, K - 1]], -1)
        flip = ~inside[I, J, K]
        q[flip] = q[flip][:, ::-1]
        quads.append(q)
    # z-edge faces: cells (i-1, j-1, k), (i, j-1, k), (i, j, k), (i-1, j, k)
    e = cz[1:nx - 1, 1:ny - 1, :]
    I, J, K = np.nonzero(e)
    I = I + 1
    J = J + 1
    if len(I):
        q = np.stack([vid[I - 1, J - 1, K], vid[I, J - 1, K], vid[I, J, K], vid[I - 1, J, K]], -1)
        flip = ~inside[I, J, K]
        q[flip] = q[flip][:, ::-1]
        quads.append(q)
    quads = np.concatenate(quads, 0) if quads else np.zeros((0, 4), np.int64)
    ok = np.all(quads >= 0, axis=1)
    return verts, quads[ok]


def project_to_surface(verts: np.ndarray, sdf, h: float, iterations: int = 2) -> np.ndarray:
    """Moves vertices onto the zero level set: p -= d * grad / |grad|^2 (clamped to h)."""
    P = verts.copy()
    eps = h * 0.25
    for _ in range(iterations):
        d0 = sdf(P)
        g = np.zeros_like(P)
        for a in range(3):          # forward differences (half the cost of central ones)
            o = np.zeros(3)
            o[a] = eps
            g[:, a] = (sdf(P + o) - d0) / eps
        gn2 = np.maximum((g * g).sum(-1), 1e-8)
        step = -(d0 / gn2)[:, None] * g
        sl = np.sqrt((step * step).sum(-1))
        scale = np.minimum(1.0, (h * 0.75) / np.maximum(sl, 1e-12))
        P += step * scale[:, None]
    return P


def mesh_from_arrays(name: str, verts: np.ndarray, faces: np.ndarray) -> bpy.types.Object:
    """Builds a Blender mesh object from (V,3) verts and (F,k) faces (all same arity)."""
    me = bpy.data.meshes.new(name)
    nv, nf = len(verts), len(faces)
    k = faces.shape[1] if nf else 3
    me.vertices.add(nv)
    me.vertices.foreach_set("co", np.asarray(verts, np.float32).ravel())
    me.loops.add(nf * k)
    me.loops.foreach_set("vertex_index", np.asarray(faces, np.int32).ravel())
    me.polygons.add(nf)
    me.polygons.foreach_set("loop_start", np.arange(0, nf * k, k, dtype=np.int32))
    me.update(calc_edges=True)
    me.validate(clean_customdata=False)
    return common.new_object(name, me)


def mesh_arrays(obj: bpy.types.Object):
    """Returns verts (V,3) and triangle/poly data: (loop_start, loop_total, loop_verts)."""
    me = obj.data
    V = np.zeros(len(me.vertices) * 3, np.float64)
    me.vertices.foreach_get("co", V)
    return V.reshape(-1, 3)


def face_centers(obj: bpy.types.Object) -> np.ndarray:
    me = obj.data
    C = np.zeros(len(me.polygons) * 3, np.float64)
    me.polygons.foreach_get("center", C)
    return C.reshape(-1, 3)


def face_normals(obj: bpy.types.Object) -> np.ndarray:
    me = obj.data
    N = np.zeros(len(me.polygons) * 3, np.float64)
    me.polygons.foreach_get("normal", N)
    return N.reshape(-1, 3)


def set_vertex_group(obj: bpy.types.Object, name: str, weights: np.ndarray, threshold: float = 1e-4) -> None:
    vg = obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)
    for i in np.nonzero(weights > threshold)[0]:
        vg.add([int(i)], float(weights[i]), "REPLACE")


def decimate(obj: bpy.types.Object, target_tris: int, protect: np.ndarray | None = None,
             protect_factor: float = 1.0) -> None:
    """Collapse-decimates to ~target_tris. `protect` (per-vertex 0..1) keeps detail where high."""
    tris = common.triangle_count(obj)
    if tris <= target_tris:
        return
    mod = obj.modifiers.new("dec", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.use_collapse_triangulate = True
    if protect is not None:
        set_vertex_group(obj, "_protect", protect)
        mod.vertex_group = "_protect"
        mod.vertex_group_factor = protect_factor
        mod.invert_vertex_group = True
    # The ratio is applied to faces; iterate a couple of times to land near the target.
    mod.ratio = max(0.002, min(1.0, target_tris / tris))
    common.apply_modifiers(obj)
    vg = obj.vertex_groups.get("_protect")
    if vg is not None:
        obj.vertex_groups.remove(vg)


def assign_labels(obj: bpy.types.Object, labels: np.ndarray, label_materials: dict[int, str]) -> None:
    """labels: per-polygon int labels -> material slots M_<id>."""
    slot_of = {}
    for lab in sorted(set(int(x) for x in np.unique(labels))):
        mat_id = label_materials.get(lab, "skin_hollow")
        slot_of[lab] = materials.assign(obj, mat_id)
    idx = np.array([slot_of[int(x)] for x in labels], np.int32)
    obj.data.polygons.foreach_set("material_index", idx)
    obj.data.update()


def remove_small_islands(obj, min_fraction: float = 0.02, min_faces: int = 60) -> int:
    """Deletes connected components smaller than min_fraction of the largest one (debris from
    thin SDF features). Returns the number of removed faces."""
    import bmesh
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    seen = set()
    comps = []
    for f in bm.faces:
        if f.index in seen:
            continue
        stack = [f]
        comp = []
        seen.add(f.index)
        while stack:
            g = stack.pop()
            comp.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen:
                        seen.add(h.index)
                        stack.append(h)
        comps.append(comp)
    if not comps:
        bm.free()
        return 0
    big = max(len(c) for c in comps)
    kill = [f for c in comps if len(c) < max(min_faces, big * min_fraction) for f in c]
    n = len(kill)
    if kill:
        bmesh.ops.delete(bm, geom=kill, context="FACES")
    bm.to_mesh(me)
    bm.free()
    me.update()
    return n
