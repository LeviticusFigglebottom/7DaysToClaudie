"""First-person arms: jumpsuit sleeves, the convict's hands (thumb/index/fingers bones), the
bolted-on wrist tether on the left forearm, hand sockets and the fp_* actions.

Camera at the origin looking -Y (Blender); arms enter from the lower edge of the view.
Sockets (empties parented to the hand bones; in Godot local +Y runs along the gripped handle
towards the thumb/tool head, +X towards the fingertips):
  socket_hand.R - tool grip point (tools parent here), socket_hand.L - off-hand.
"""
from __future__ import annotations

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

from lib import char_anim, char_fp as F, char_gltf, char_mesh as M, char_uv as U, common, export, vcolor
from lib.char_body import LABEL_MATERIALS, normalize_weights
from lib.char_skel import create_armature


def _mesh_arm(model, sd: str, sk, h: float, tris: int):
    j = sk.j
    pts = np.stack([j[f"shoulder.{sd}"], j[f"elbow.{sd}"], j[f"wrist.{sd}"], j[f"hand_tip.{sd}"],
                    j[f"th_tip.{sd}"], j[f"ix_tip.{sd}"], j[f"pk_tip.{sd}"]])
    lo = pts.min(0) - 0.08
    hi = pts.max(0) + 0.08
    shape = tuple(int(x) for x in np.ceil((hi - lo) / h) + 1)
    d, _ = model.eval_grid(lo, h, shape)
    V, Q = M.surface_nets(d, lo, h)
    del d
    V = M.project_to_surface(V, lambda P: model.eval_points(P)[0], h, iterations=2)
    obj = M.mesh_from_arrays(f"arm_{sd}", V, Q)
    M.remove_small_islands(obj)
    M.decimate(obj, tris)
    return obj


def _labels(model, obj):
    C = M.face_centers(obj)
    N = M.face_normals(obj)
    _, lab = model.eval_points(C - N * 0.0006)
    return lab


def _apply_weights(o, W, names):
    for bi, bn in enumerate(names):
        col = W[:, bi]
        nzi = np.nonzero(col > 0)[0]
        vg = o.vertex_groups.new(name=bn)
        if len(nzi) == 0:
            continue
        vals = np.round(col[nzi], 4)
        order = np.argsort(vals, kind="stable")
        sv, si = vals[order], nzi[order]
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


def build(params: dict, outputs: list[str]) -> None:
    scene = bpy.context.scene
    scene.render.fps = 30
    j = F.fp_joints(params)
    sk = F.FPSkeleton(j, params, bones=F.FP_BONES)
    arm = create_armature(sk)
    model = F.FPModel(sk, params)
    model.build()
    s = model.s
    arms = []
    for sd in ("L", "R"):
        o = _mesh_arm(model, sd, sk, float(params.get("h", 0.0021)), int(params.get("arm_tris", 3900)))
        lab = _labels(model, o)
        M.assign_labels(o, lab, LABEL_MATERIALS)
        fa = model.fa[sd]
        wr = j[f"wrist.{sd}"]
        U.project(o, fa.head, fa.axis, -j[f"back.{sd}"], planar_threshold=0.9,
                  box_mask=lambda C, wr=wr, ax=fa.axis: (C - wr) @ ax > 0.0)
        arms.append(o)
    body = common.join(arms, "fp_arms")
    common.shade_smooth(body, angle_deg=70.0)
    # tether (rigid on the left forearm)
    parts, centre, Rt = F.build_tether(sk, s)
    bm = bmesh.new()
    labels, uvs = [], []
    for verts, faces, lab, uv in parts:
        vs = [bm.verts.new(Vector(v)) for v in verts]
        for fi, f in enumerate(faces):
            try:
                bm.faces.new([vs[k] for k in f])
            except ValueError:
                continue
            labels.append(lab)
            uvs.append(uv[fi] if uv is not None else None)
    tether = common.mesh_from_bmesh("tether", bm)
    M.assign_labels(tether, np.array(labels), LABEL_MATERIALS)
    U.project(tether, centre, Rt[:, 1], -Rt[:, 2], planar_threshold=0.7)
    uvl = tether.data.uv_layers.active
    for fi, uv in enumerate(uvs):
        if uv is None:
            continue
        for k, li in enumerate(tether.data.polygons[fi].loop_indices):
            uvl.data[li].uv = uv[k]
    common.shade_smooth(tether, angle_deg=40.0)
    # vertex colours
    vcolor.bake_ao([body, tether], samples=16, distance=0.12, strength=0.85, ground=False)
    nz = model.noise
    for o, grime in ((body, 0.35), (tether, 0.3)):
        V = M.mesh_arrays(o)
        g = grime * np.clip(0.4 + 0.6 * (nz.fbm(V, 14.0, 3) * 0.5 + 0.5), 0, 1)
        lv = np.zeros(len(o.data.loops), np.int32)
        o.data.loops.foreach_get("vertex_index", lv)
        vcolor.set_channel(o, 1, lambda co, n, li, g=g, lv=lv: float(g[lv[li]]))
        vcolor.fill_channel(o, 2, 0.0)
        vcolor.fill_channel(o, 3, 1.0)
    # skinning
    names = sk.names
    V = M.mesh_arrays(body)
    W = normalize_weights(model.weights(V))
    _apply_weights(body, W, names)
    _bind(body, arm)
    Wt = np.zeros((len(tether.data.vertices), len(names)))
    Wt[:, names.index("forearm.L")] = 1.0
    _apply_weights(tether, Wt, names)
    _bind(tether, arm)
    # sockets
    sockets = []
    bpy.context.view_layer.update()
    for sd in ("R", "L"):
        e = bpy.data.objects.new(f"socket_hand.{sd}", None)
        e.empty_display_type = "ARROWS"
        e.empty_display_size = 0.05
        scene.collection.objects.link(e)
        e.parent = arm
        e.parent_type = "BONE"
        e.parent_bone = f"hand.{sd}"
        bpy.context.view_layer.update()
        ax, lat = j[f"axis.{sd}"], j[f"lat.{sd}"]
        x = ax
        z = lat                            # along the gripped handle, towards the thumb / tool head
        y = np.cross(z, x)
        Mw = Matrix.Identity(4)
        for r in range(3):
            Mw[r][0], Mw[r][1], Mw[r][2], Mw[r][3] = x[r], y[r], z[r], j[f"grip.{sd}"][r]
        e.matrix_world = Mw
        sockets.append(e)
    # actions
    rig = F.FPRig(sk)
    for name, n, loop, gen in F.fp_actions(params):
        baked = [rig.evaluate(gen(f)) for f in range(n + 1)]
        char_anim.write_action(arm, sk, name, baked)
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    scene.frame_set(0)
    export.export_glb(outputs[0], [arm, body, tether] + sockets, animations=True, skins=True)
    print(f"[character_fp_arms] tris arms {common.triangle_count(body)} tether {common.triangle_count(tether)}")
