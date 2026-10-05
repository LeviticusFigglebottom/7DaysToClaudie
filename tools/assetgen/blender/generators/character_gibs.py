"""Gibs for dismemberment (models/characters/gibs.glb): unskinned pieces cut from a bare Hollowed
body with ragged gore at the cuts, plus loose flesh chunks. Origin of each piece = centre of its
(body-side) cut. Materials M_skin_hollow + M_gore only.

  gib_head, gib_arm_upper, gib_arm_lower, gib_leg_upper, gib_leg_lower, gib_chunk_a..d
"""
from __future__ import annotations

import math

import bpy
import numpy as np
from mathutils import Matrix

from lib import char_body as B, char_dress, char_mesh as M, char_pipeline as CP, char_sdf as S, char_uv as U
from lib import char_attrs as A, common, export, vcolor
from lib.char_skel import Skeleton, build_joints

PIECES = {
    # name: (segment, cut at the origin, tris)
    "gib_head": ("body_head", "neck", 1300),
    "gib_arm_upper": ("body_upper_arm.L", "shoulder.L", 320),
    "gib_arm_lower": ("body_forearm.L", "elbow.L", 760),
    "gib_leg_upper": ("body_thigh.L", "hip.L", 420),
    "gib_leg_lower": ("body_shin.L", "knee.L", 560),
}


def _gore_cut_relief(model, obj, seg, rng):
    """Push cap (gore) vertices around with noise so the cut reads as torn flesh, not a slice."""
    me = obj.data
    V = M.mesh_arrays(obj)
    _, lab = model.eval_points(V, seg)
    nz = model.noise
    disp = nz.fbm(V, 60.0, 3) * 0.006 + nz.noise(V * 1.0 + 3.1, 25.0) * 0.004
    N = np.zeros(len(V) * 3)
    me.vertices.foreach_get("normal", N)
    N = N.reshape(-1, 3)
    is_gore = lab == B.L_GORE
    V[is_gore] += N[is_gore] * disp[is_gore, None]
    me.vertices.foreach_set("co", V.ravel().astype(np.float32))
    me.update()


def _chunk(name, seed, size, s):
    r = np.random.default_rng(seed)
    prog = S.Program(B.L_GORE)
    c0 = np.zeros(3)
    for i in range(5):
        c = c0 + r.normal(0, 0.35, 3) * size
        prog.ellipsoid(c, np.abs(r.normal(1.0, 0.25, 3)) * size * 0.55, k=size * 0.25, label=B.L_GORE)
    nz = S.Noise(seed)
    # a patch of skin on one side (the outside of the torn chunk)
    skin_dir = S.normalize(r.normal(0, 1, 3))

    def skinside(P):
        return -(P @ skin_dir - size * 0.15)
    prog.paint(skinside, c0 - size * 3, c0 + size * 3, B.L_SKIN)
    prog.displace(lambda P: nz.fbm(P, 1.0 / (size * 0.35), 3) * size * 0.12, c0 - size * 3, c0 + size * 3)
    h = size / 12.0
    lo, hi = prog.bounds()
    lo, hi = lo - 3 * h, hi + 3 * h
    shape = tuple(int(x) for x in np.ceil((hi - lo) / h) + 1)
    d, _ = prog.eval_grid(lo, h, shape)
    V, Q = M.surface_nets(d, lo, h)
    V = M.project_to_surface(V, lambda P: prog.eval(P)[0], h)
    obj = M.mesh_from_arrays(name, V, Q)
    M.remove_small_islands(obj)
    M.decimate(obj, 150)
    C = M.face_centers(obj)
    _, lab = prog.eval(C - M.face_normals(obj) * 0.0005)
    M.assign_labels(obj, lab, B.LABEL_MATERIALS)
    return obj


def build(params: dict, outputs: list[str]) -> None:
    p = {k: v for k, v in params.items() if k not in ("outfit", "boots", "hair", "wounds", "bloom")}
    p["blood"] = 1.0
    rng = np.random.default_rng(int(p.get("seed", 1)) + 99)
    joints = build_joints(p)
    skel = Skeleton(joints, p)
    model = B.BodyModel(skel, p)
    model.build_anatomy()
    model.build_regions()
    char_dress.dress(model, {**p, "hair": {"style": "none"}}, rng)
    model.overlap = 0.0015
    model.inset = 0.0
    coarse = CP.coarse_field(model)
    objs = []
    from lib.char_build import SEG_CFG
    for name, (seg, cut, tris) in PIECES.items():
        bb = CP.segment_bounds(model, coarse, seg)
        obj = CP.mesh_segment(model, seg, SEG_CFG[seg]["h"], bb[0], bb[1], name=name)
        M.decimate(obj, tris)
        _gore_cut_relief(model, obj, seg, rng)
        lab = CP.label_faces(model, obj, seg)
        M.assign_labels(obj, lab, B.LABEL_MATERIALS)
        # UVs before moving the origin
        sk = model.skel
        if seg == "body_head":
            U.project(obj, model.hc, model.hR[:, 1], -model.hR[:, 2], planar_threshold=0.75)
        else:
            side = seg[-1]
            f = {"body_upper_arm": model.arm[side]["ua"], "body_forearm": model.arm[side]["fa"],
                 "body_thigh": model.leg[side]["th"], "body_shin": model.leg[side]["sh"]}[seg[:-2]]
            U.project(obj, f.head, f.axis, -f.out, planar_threshold=0.85)
        c, n = model.cuts[cut]
        # origin at the centre of the cut (section centroid on the cut plane)
        V = M.mesh_arrays(obj)
        # shader data from the body's rest pose, before the origin moves: a severed arm's veins and
        # mottling are the ones it had on the body (ADR-0028)
        f = A.Fields(len(V))
        f.wet, f.bruise = model.skin_masks(V)
        A.write(obj, V, f)
        near = np.abs((V - c) @ n) < 0.004 * model.s
        centre = V[near].mean(0) if near.sum() > 3 else c
        obj.data.transform(Matrix.Translation(tuple(-centre)))
        obj.location = (0.0, 0.0, 0.0)
        common.shade_smooth(obj, angle_deg=70.0)
        objs.append(obj)
    for i, letter in enumerate("abcd"):
        objs.append(_chunk(f"gib_chunk_{letter}", int(p.get("seed", 1)) * 3 + i, 0.035 + 0.012 * i, model.s))
    for o in objs:
        if o.name.startswith("gib_chunk"):
            U.project(o, (0, 0, 0), (0, 0, 1), (0, 1, 0), planar_threshold=0.7)
            common.shade_smooth(o, angle_deg=70.0)
            A.write(o, M.mesh_arrays(o), A.Fields(len(o.data.vertices)))
    vcolor.bake_ao(objs, samples=12, distance=0.08, strength=0.8, ground=False)
    for o in objs:
        vcolor.fill_channel(o, 1, 0.85)       # blood/dirt mask high: fresh gore
        vcolor.fill_channel(o, 2, 0.0)
        vcolor.fill_channel(o, 3, 1.0)
    # lay the pieces out side by side (separate objects; the game spawns them individually)
    x = 0.0
    for o in objs:
        lo, hi = common.bounds(o)
        o.location = (x - lo.x, 0.0, 0.0)
        x += (hi.x - lo.x) + 0.1
    for o in objs:
        o.location = (0.0, 0.0, 0.0)
    export.export_glb(outputs[0], objs)
    print("[character_gibs]", {o.name: common.triangle_count(o) for o in objs})
