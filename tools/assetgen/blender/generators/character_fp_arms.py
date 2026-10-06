"""First-person arms (ADR-0029): Remand jumpsuit sleeves rolled to the elbow, bare working
forearms, the convict's hands, the bolted tether over the back of the left wrist, hand sockets and
the fp_* actions baked from the hold poses in game/data/config/viewmodel.json.

Camera at the origin looking -Y (Blender); arms enter from the lower edge of the view.
Sockets (empties parented to the hand bones; in Godot local +Y runs along the gripped handle
towards the thumb/tool head, +X towards the knuckles):
  socket_hand.R - tool grip point (tools parent here), socket_hand.L - off-hand.
params: seed, height, h (meshing cell, m), arm_tris (per arm), sleeve_roll (fraction of the forearm).
"""
from __future__ import annotations

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

from lib import char_anim, char_fp as F, char_mesh as M, char_uv as U, common, export, vcolor
from lib.char_body import normalize_weights, smoothstep
from lib.char_skel import create_armature


def _mesh_arm(model, sd: str, sk, h: float, tris: int):
    j = sk.j
    pts = np.stack([j[f"shoulder.{sd}"], j[f"elbow.{sd}"], j[f"wrist.{sd}"], j[f"hand_tip.{sd}"],
                    j[f"th_tip.{sd}"], j[f"ix_tip.{sd}"], j[f"pk_tip.{sd}"]])
    lo = pts.min(0) - 0.08
    hi = pts.max(0) + 0.08
    # The fingers need a ~1 mm cell for the clefts between them to survive: mesh a narrow band
    # round the surface instead of a dense grid over the whole arm.
    V, Q = F.sparse_surface_nets(lambda P: model.eval_points(P)[0], lo, hi, h)
    V = M.project_to_surface(V, lambda P: model.eval_points(P)[0], h, iterations=2)
    obj = M.mesh_from_arrays(f"arm_{sd}", V, Q)
    M.remove_small_islands(obj)
    # Spend the triangles on the hands and wrists, which are seen at 30-50 cm all game. The
    # collapse ratio is per face, so a protected mesh lands above target: go round again.
    el, wr = j[f"elbow.{sd}"], j[f"wrist.{sd}"]
    for _ in range(4):
        if common.triangle_count(obj) <= tris * 1.05:
            break
        Vd = M.mesh_arrays(obj)
        t = ((Vd - el) @ F._n(wr - el)) / np.linalg.norm(wr - el)
        M.decimate(obj, tris, protect=np.clip(0.6 * (t - 0.55) / 0.35, 0.0, 0.6) + 0.2 * np.clip((t - 0.95) / 0.1, 0.0, 1.0),
                   protect_factor=1.0)
    C = M.face_centers(obj)
    t = ((C - el) @ F._n(wr - el)) / np.linalg.norm(wr - el)
    print(f"[character_fp_arms] arm.{sd}: {common.triangle_count(obj)} tris, {int((t > 1.0).sum())} faces past the wrist")
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


def _dirt_mask(model, sk, o) -> None:
    """Vertex G: where dirt, soot and dried blood gather - skin creases (low AO), the knuckles and
    the creased skin over the finger joints, fingertips and nail folds, the wrist under the tether,
    the sleeve's roll and elbow - broken up by noise. The fp_* materials reveal their grime layer by
    it. Vertex B: the flush of blood under thin skin - knuckles, finger joints and the fingertips
    redden (fp_skin's `flush`)."""
    V = M.mesh_arrays(o)
    lv = np.zeros(len(o.data.loops), np.int32)
    o.data.loops.foreach_get("vertex_index", lv)
    layer = o.data.color_attributes[vcolor.ATTR]
    cols = np.zeros(len(layer.data) * 4, np.float32)
    layer.data.foreach_get("color", cols)
    cols = cols.reshape(-1, 4)
    ao = np.zeros(len(V))
    ao[lv] = cols[:, 0]
    j = sk.j
    s = model.s

    def near(p, r0, r1):
        return 1.0 - smoothstep(r0 * s, r1 * s, np.linalg.norm(V - p, axis=1))

    tip = np.zeros(len(V))
    joint = np.zeros(len(V))
    knuckle = np.zeros(len(V))
    for sd, _ in F.SIDES:
        back = j[f"back.{sd}"]
        for k in ("ix", "md", "rg", "pk", "th"):
            tip = np.maximum(tip, near(j[f"{k}_tip.{sd}"], 0.004, 0.016))
        for k in ("ix", "md", "rg", "pk"):
            knuckle = np.maximum(knuckle, near(j[f"{k}_mcp.{sd}"] + back * 0.010 * s, 0.003, 0.013))
            # the creased skin over the middle and end joints, on the back of the finger
            for jn, w in (("pip", 1.0), ("dip", 0.7)):
                joint = np.maximum(joint, w * near(j[f"{k}_{jn}.{sd}"] + back * 0.007 * s, 0.002, 0.008))
        for jn in ("mcp", "ip"):
            joint = np.maximum(joint, 0.8 * near(j[f"th_{jn}.{sd}"], 0.004, 0.013))
    nz = model.noise
    n1 = nz.fbm(V, 22.0, 3) * 0.5 + 0.5
    n2 = nz.fbm(V + 3.1, 7.0, 2) * 0.5 + 0.5
    n3 = nz.fbm(V + 7.7, 60.0, 2) * 0.5 + 0.5
    g = (1.0 - ao) * 1.6 * (0.5 + n1) + tip * (0.6 + 0.6 * n1) + 0.6 * knuckle * (0.6 + 0.6 * n1) \
        + 0.55 * joint * (0.5 + 0.8 * n3) + 0.35 * smoothstep(0.55, 0.85, n2)
    cols[:, 1] = np.clip(g, 0.0, 1.0)[lv]
    flush = np.clip(0.85 * knuckle + 0.6 * joint + 0.45 * tip, 0.0, 1.0) * (0.75 + 0.5 * n1)
    cols[:, 2] = np.clip(flush, 0.0, 1.0)[lv]
    layer.data.foreach_set("color", cols.ravel())


def build(params: dict, outputs: list[str]) -> None:
    scene = bpy.context.scene
    scene.render.fps = 30
    cfg = F.load_config()
    j = F.fp_joints(params)
    sk = F.FPSkeleton(j, params, bones=F.FP_BONES)
    arm = create_armature(sk)
    model = F.FPModel(sk, params)
    model.build()
    s = model.s
    arms = []
    for sd, _ in F.SIDES:
        o = _mesh_arm(model, sd, sk, float(params.get("h", 0.0011)), int(params.get("arm_tris", 14000)))
        lab = _labels(model, o)
        M.assign_labels(o, lab, F.LABEL_MATERIALS)
        fa = model.fa[sd]
        wr = j[f"wrist.{sd}"]
        U.project(o, fa.head, fa.axis, -model.dorsal[sd], planar_threshold=0.9,
                  box_mask=lambda C, wr=wr, ax=fa.axis: (C - wr) @ ax > 0.0)
        arms.append(o)
    body = common.join(arms, "fp_arms")
    common.shade_smooth(body, angle_deg=70.0)
    # tether (rigid on the left forearm's twist bone: it turns with the wrist like a watch)
    parts, centre, Rt = F.build_tether(sk, s, model)
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
    # Every part but the screen is a closed shell: face them outward (the hand-built straps are
    # wound either way); the screen quad is wound towards the viewer by construction.
    screen = [f for f, lab in zip(bm.faces, labels) if lab == F.L_SCREEN]
    bmesh.ops.recalc_face_normals(bm, faces=[f for f in bm.faces if f not in screen])
    tether = common.mesh_from_bmesh("tether", bm)
    M.assign_labels(tether, np.array(labels), F.LABEL_MATERIALS)
    U.project(tether, centre, Rt[:, 1], -Rt[:, 2], planar_threshold=0.7)
    uvl = tether.data.uv_layers.active
    for fi, uv in enumerate(uvs):
        if uv is None:
            continue
        for k, li in enumerate(tether.data.polygons[fi].loop_indices):
            uvl.data[li].uv = uv[k]
    common.shade_smooth(tether, angle_deg=35.0)
    # vertex colours: R = AO, G = dirt mask, B = flush (arms; 0 on the tether), A = 1
    vcolor.bake_ao([body, tether], samples=24, distance=0.10, strength=0.9, ground=False)
    _dirt_mask(model, sk, body)
    nz = model.noise
    Vt = M.mesh_arrays(tether)
    gt = 0.3 * np.clip(0.4 + 0.6 * (nz.fbm(Vt, 40.0, 3) * 0.5 + 0.5), 0, 1)
    lvt = np.zeros(len(tether.data.loops), np.int32)
    tether.data.loops.foreach_get("vertex_index", lvt)
    vcolor.set_channel(tether, 1, lambda co, n, li, g=gt, lv=lvt: float(g[lv[li]]))
    vcolor.fill_channel(tether, 2, 0.0)
    for o in (body, tether):
        vcolor.fill_channel(o, 3, 1.0)
    # skinning
    names = sk.names
    V = M.mesh_arrays(body)
    W = normalize_weights(model.weights(V))
    _apply_weights(body, W, names)
    _bind(body, arm)
    Wt = np.zeros((len(tether.data.vertices), len(names)))
    Wt[:, names.index("forearm_twist.L")] = 1.0
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
    # actions, from the hold poses in the data file
    rig = F.FPRig(sk)
    solver = F.PoseSolver(rig, cfg.get("wrist"))
    turned = []
    for name, n, loop, frames in F.fp_actions(cfg):
        solver.clamped = {}
        baked = [rig.evaluate(solver.solve(hands)) for hands in frames]
        char_anim.write_action(arm, sk, name, baked)
        # how far the wrist limits turned each hand from what the pose asked for
        turned.append(f"{name} " + "/".join(f"{sd}{solver.clamped.get(sd, 0.0):.0f}" for sd in ("R", "L")))
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    scene.frame_set(0)
    export.export_glb(outputs[0], [arm, body, tether] + sockets, animations=True, skins=True)
    print("[character_fp_arms] hands turned back into the wrist's range (deg): " + ", ".join(turned))
    print(f"[character_fp_arms] tris arms {common.triangle_count(body)} tether {common.triangle_count(tether)} "
          f"actions {len(bpy.data.actions)}")
