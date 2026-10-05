"""Assembles a complete Hollowed body: armature, segmented skinned meshes, extras, stump caps,
vertex colours. Animations are added by char_anim; export by the generator.
"""
from __future__ import annotations

import math

import bmesh
import bpy
import numpy as np

from . import char_body as B
from . import char_extras as X
from . import char_mesh as M
from . import char_pipeline as CP
from . import char_skel as K
from . import char_uv as U
from . import common, vcolor

# Per segment: grid spacing (m), triangle budget, decimation parts.
SEG_CFG = {
    "body_head": {"h": 0.0024, "tris": 4200},
    "body_torso": {"h": 0.0048, "tris": 3600},
    "body_upper_arm.L": {"h": 0.0040, "tris": 460},
    "body_upper_arm.R": {"h": 0.0040, "tris": 460},
    "body_forearm.L": {"h": 0.0024, "tris": 1250},
    "body_forearm.R": {"h": 0.0024, "tris": 1250},
    "body_thigh.L": {"h": 0.0048, "tris": 560},
    "body_thigh.R": {"h": 0.0048, "tris": 560},
    "body_shin.L": {"h": 0.0034, "tris": 760},
    "body_shin.R": {"h": 0.0034, "tris": 760},
}
# Hard cap per body (contract: <= 16k), incl. extras and stump caps. The face is what players see
# from arm's length: it gets the biggest share (at 1.7k it decimated into jagged eye sockets).
# Godot's import LODs bring distant bodies back down.
BODY_BUDGET = 15800
CAP_TRIS = 56


def _parts_for(model, seg: str):
    """Decimation budget per segment. Uniform QEM decimation already spends triangles on the
    face, fingers and toes (high curvature), so no locked parts are used."""
    tris = model.p.get("seg_tris", {}).get(seg, SEG_CFG[seg]["tris"])
    return [], tris


def _parts_for_locked(model, seg: str):
    s = model.s
    sk = model.skel
    tris = model.p.get("seg_tris", {}).get(seg, SEG_CFG[seg]["tris"])
    if seg == "body_head":
        R, hc = model.hR, model.hc

        def face(V):
            q = (V - hc) @ R / s
            return (q[:, 2] > 0.035) & (q[:, 1] > -0.115) & (q[:, 1] < 0.045) & (np.abs(q[:, 0]) < 0.06)

        def ears(V):
            q = (V - hc) @ R / s
            return (np.abs(q[:, 0]) > 0.064) & (q[:, 1] > -0.04) & (q[:, 1] < 0.05) & (np.abs(q[:, 2]) < 0.04)
        return [(face, int(tris * 0.40)), (ears, int(tris * 0.08))], tris
    if seg.startswith("body_forearm"):
        side = seg[-1]
        wr = sk.j[f"wrist.{side}"]
        ax = model.arm[side]["fa"].axis

        def hand(V):
            return (V - wr) @ ax > -0.012 * s
        return [(hand, int(tris * 0.58))], tris
    if seg.startswith("body_shin"):
        side = seg[-1]
        an = sk.j[f"ankle.{side}"]

        def foot(V):
            return V[:, 2] < an[2] + 0.025 * s
        return [(foot, int(tris * 0.42))], tris
    return [], tris


def _uv_segment(model, obj, seg: str):
    sk, s = model.skel, model.s
    if seg == "body_head":
        U.project(obj, model.hc, model.hR[:, 1], -model.hR[:, 2], planar_threshold=0.75)
    elif seg == "body_torso":
        pel, nk = sk.head["hips"], sk.head["neck"]
        U.project(obj, pel, nk - pel, (0.0, 1.0, 0.0), planar_threshold=0.80)
    else:
        side = seg[-1]
        if "upper_arm" in seg:
            f = model.arm[side]["ua"]
        elif "forearm" in seg:
            f = model.arm[side]["fa"]
        elif "thigh" in seg:
            f = model.leg[side]["th"]
        else:
            f = model.leg[side]["sh"]
        box = None
        if "shin" in seg:
            an = sk.j[f"ankle.{side}"]

            def box(C, z=an[2]):
                return C[:, 2] < z + 0.01 * s
        elif "forearm" in seg:
            # the hand: fingers sit off the forearm axis, where the cylinder mapping smeared the
            # skin into streaks along them; box projection keeps texels square
            wr = sk.j[f"wrist.{side}"]

            def box(C, wr=wr, ax=f.axis):
                return (C - wr) @ ax > -0.005 * s
        U.project(obj, f.head, f.axis, -f.out, planar_threshold=0.85, box_mask=box)


def _append_part(obj, part: X.Part):
    """Appends a Part's geometry to obj (after decimation). Returns (first vertex, first face)."""
    me = obj.data
    v0 = len(me.vertices)
    f0 = len(me.polygons)
    bm = bmesh.new()
    bm.from_mesh(me)
    nv = [bm.verts.new(v) for v in part.V]
    bm.verts.ensure_lookup_table()
    for f in part.F:
        try:
            bm.faces.new([nv[i] for i in f])
        except ValueError:
            pass
    bm.to_mesh(me)
    bm.free()
    me.update()
    return v0, f0


def build_body(params: dict):
    scene = bpy.context.scene
    scene.render.fps = 30
    scene.render.fps_base = 1.0
    seed = int(params.get("seed", 1))
    rng = np.random.default_rng(seed)
    joints = K.build_joints(params)
    skel = K.Skeleton(joints, params)
    arm = K.create_armature(skel)
    model = B.BodyModel(skel, params)
    model.build_anatomy()
    model.build_regions()
    from . import char_dress
    char_dress.dress(model, params, rng)
    coarse = CP.coarse_field(model)

    extras: dict[str, X.Part] = {}
    head_x = X.eyes(model)
    head_x.merge(X.teeth(model, rng))
    extras["body_head"] = head_x
    for seg, part in X.bloom(model, rng).items():
        if seg in extras:
            extras[seg].merge(part)
        else:
            extras[seg] = part

    # budget: segment targets scaled so segments + extras + caps stay under BODY_BUDGET
    def part_tris(part):
        return sum(len(f) - 2 for f in part.F)
    extra_tris = sum(part_tris(pt) for pt in extras.values()) + CAP_TRIS * len(B.STUMPS)
    targets = {seg: _parts_for(model, seg)[1] for seg in B.SEGMENTS}
    room = BODY_BUDGET - extra_tris
    scale = min(1.0, room / float(sum(targets.values())))
    objs = []
    stats = {}
    for seg in B.SEGMENTS:
        cfg = SEG_CFG[seg]
        bb = CP.segment_bounds(model, coarse, seg)
        obj = CP.mesh_segment(model, seg, cfg["h"], bb[0], bb[1], name=seg)
        parts, _ = _parts_for(model, seg)
        tris = int(targets[seg] * scale)
        CP.decimate_parts(obj, parts, tris)
        labels = list(CP.label_faces(model, obj, seg))
        part = extras.get(seg)
        x_v0 = x_f0 = None
        if part is not None and part.V:
            x_v0, x_f0 = _append_part(obj, part)
            labels += part.L
        labels = np.array(labels[:len(obj.data.polygons)], dtype=np.int32)
        M.assign_labels(obj, labels, B.LABEL_MATERIALS)
        _uv_segment(model, obj, seg)
        if part is not None and x_f0 is not None:
            _set_part_uvs(obj, part, x_f0)
        common.shade_smooth(obj, angle_deg=75.0)
        obj["_x_v0"] = -1 if x_v0 is None else x_v0
        objs.append(obj)
        stats[seg] = common.triangle_count(obj)
        obj["_part"] = 0
        obj["_seg"] = seg
        if part is not None:
            obj["_xbones"] = ",".join(part.bone)
    caps = []
    for name, (parent_seg, cut, bone) in B.STUMPS.items():
        v, f, lab = X.stump_cap(model, cut, rng)
        me = bpy.data.meshes.new(name)
        me.from_pydata([tuple(x) for x in v], [], [tuple(ff) for ff in f])
        me.update()
        o = common.new_object(name, me)
        M.assign_labels(o, np.array(lab), B.LABEL_MATERIALS)
        c, n = model.cuts[cut]
        U.planar(o, c, n, (0.0, 0.0, 1.0) if abs(n[2]) < 0.9 else (0.0, 1.0, 0.0), scale=1.0)
        common.shade_smooth(o, angle_deg=60.0)
        o["_rigid"] = bone
        caps.append(o)
    _vertex_colors(model, objs, caps, rng)
    _skin(arm, model, objs, caps)
    return arm, objs, caps, skel, model, stats


def _set_part_uvs(obj, part: X.Part, f0: int):
    me = obj.data
    uvl = me.uv_layers.active
    for i, uvs in enumerate(part.UV):
        if uvs is None:
            continue
        poly = me.polygons[f0 + i]
        for k, li in enumerate(poly.loop_indices):
            uvl.data[li].uv = uvs[k]


def _vertex_colors(model, objs, caps, rng):
    """R = AO, G = dirt/blood mask, B = Bloom mask, A = 1."""
    vcolor.bake_ao(objs + caps, samples=14, distance=0.22, strength=0.9, ground=False)
    nz = model.noise
    s = model.s
    wounds = model.wounds
    sites = model.bloom_sites
    blood = float(model.p.get("blood", 0.5))
    grime = float(model.p.get("grime", 0.4))
    for o in objs + caps:
        V = M.mesh_arrays(o)
        g = grime * (0.35 + 0.65 * np.clip(nz.fbm(V, 6.0, 3) * 0.5 + 0.5, 0, 1))
        g += np.clip(0.30 - V[:, 2] / s, 0, 0.3) * 1.6 * grime          # mud on the lower legs
        for c, r, amt in wounds:
            d = np.sqrt(((V - c) ** 2).sum(-1))
            spread = 1 - np.clip((d - r) / (r * 2.5 + 0.03), 0, 1)
            drip = np.clip(1 - np.abs((V[:, 0] - c[0])) / (r * 1.5 + 0.02), 0, 1) * (V[:, 2] < c[2]) * \
                np.clip(1 - (c[2] - V[:, 2]) / 0.35, 0, 1) * 0.6
            g = np.maximum(g, (spread + drip * (nz.noise(V, 30.0) > 0)) * amt * blood)
        # mouth/chin blood
        mouth = model.HP(0, -0.07, 0.085)
        d = np.sqrt(((V - mouth) ** 2).sum(-1))
        g = np.maximum(g, (1 - np.clip(d / (0.06 * s), 0, 1)) * blood * 0.9)
        # hands
        for side in ("L", "R"):
            wr = model.skel.j[f"wrist.{side}"]
            ax = model.arm[side]["fa"].axis
            hp = (V - wr) @ ax
            g = np.maximum(g, np.clip(hp / (0.08 * s), 0, 1) * blood * 0.7 * (0.6 + 0.4 * (nz.noise(V, 20.0) > -0.2)))
        bl = np.zeros(len(V))
        for c, r, amt in sites:
            d = np.sqrt(((V - c) ** 2).sum(-1))
            veins = np.clip(1 - np.abs(nz.noise(V, 25.0)) * 6.0, 0, 1)
            near = 1 - np.clip((d - r) / (r * 3.0 + 0.04), 0, 1)
            bl = np.maximum(bl, np.clip(near * (0.55 + 0.45 * veins) + (1 - np.clip(d / r, 0, 1)), 0, 1) * amt)
        if o.name.startswith("stump_"):
            g[:] = 1.0
        vcolor.set_channel(o, 1, lambda co, n, li, g=g, lv=_loop_verts(o): float(g[lv[li]]))
        vcolor.set_channel(o, 2, lambda co, n, li, bl=bl, lv=_loop_verts(o): float(bl[lv[li]]))
        vcolor.fill_channel(o, 3, 1.0)


def _loop_verts(o):
    lv = np.zeros(len(o.data.loops), np.int32)
    o.data.loops.foreach_get("vertex_index", lv)
    return lv


def _skin(arm, model, objs, caps):
    names = K.BONE_NAMES
    for o in objs:
        seg = o["_seg"]
        V = M.mesh_arrays(o)
        W = model.weights(V, seg)
        x0 = int(o.get("_x_v0", -1))
        xb = o.get("_xbones", "")
        if x0 >= 0 and xb:
            bones = xb.split(",")
            for i, bn in enumerate(bones):
                vi = x0 + i
                if vi >= len(W):
                    break
                if bn:
                    W[vi] = 0.0
                    W[vi, names.index(bn)] = 1.0
        W = B.normalize_weights(W)
        _apply_weights(o, W, names)
        _bind(o, arm)
    for o in caps:
        W = np.zeros((len(o.data.vertices), len(names)))
        W[:, names.index(o["_rigid"])] = 1.0
        _apply_weights(o, W, names)
        _bind(o, arm)


def _apply_weights(o, W, names):
    for bi, bn in enumerate(names):
        col = W[:, bi]
        nzi = np.nonzero(col > 0)[0]
        if len(nzi) == 0:
            continue
        vg = o.vertex_groups.new(name=bn)
        # group identical weights to minimise API calls
        vals = np.round(col[nzi], 4)
        order = np.argsort(vals, kind="stable")
        sv = vals[order]
        si = nzi[order]
        start = 0
        while start < len(sv):
            end = start
            while end < len(sv) and sv[end] == sv[start]:
                end += 1
            vg.add([int(x) for x in si[start:end]], float(sv[start]), "REPLACE")
            start = end


def _bind(o, arm):
    o.parent = arm
    o.matrix_parent_inverse.identity()
    mod = o.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    mod.use_vertex_groups = True
