"""Birds (ADR-0027): a songbird and a crow, each as two unskinned meshes in one glb, drawn as
MultiMesh instances by the game's flocks (no skeletons):

  fly    wings spread, origin at the shoulders (the flap pivots on y = 0); UV2.x is the span
         fraction (0 on the body, 1 at the wingtip) the fur shader flaps by (wing_flap).
  perch  wings folded along the back, standing on its feet at the origin.

Feathers use the fur shader with vertex colour (R = AO, G = pale breast, B = dark cap, bars,
primaries); UVs run along the body and chordwise across the wing, so the feather texture's rows
lie as feathers do.

params: name, seed, kind (songbird / crow), length (beak to tail, m), span (wingtip to wingtip),
fingers (separated primaries at the tip: the crow's five), budget ({body, wing}), materials
({feathers, beak, eye}).
"""
from __future__ import annotations

import math

import bmesh
import bpy
import numpy as np

from lib import animal_body as AB, char_mesh as M, char_sdf as S, common, export, vcolor

L_FEATHER, L_BEAK = 0, 1


def _body_program(p: dict, perched: bool) -> tuple[S.Program, dict]:
    """Body, head, beak and tail (and, perched, folded wings and legs). Front = -Y."""
    L = float(p["length"])
    crow = p["kind"] == "crow"
    prog = S.Program(L_FEATHER)
    z0 = 0.0 if not perched else L * (0.30 if crow else 0.26)     # body centre height
    tilt = 0.0 if not perched else -math.radians(16.0 if crow else 26.0)   # perched birds sit up, tail down

    def P(x, y, z):
        # rotate about X so a perched bird's head rises and its tail drops
        c, s = math.cos(tilt), math.sin(tilt)
        return np.array([x * L, (y * c - z * s) * L, (y * s + z * c) * L + z0])
    info = {"z0": z0, "P": P}
    bw = 0.12 if crow else 0.15
    prog.ellipsoid(P(0, 0.02, 0), np.array([bw, 0.24, bw * 1.05]) * L, k=0.0)                  # body
    prog.ellipsoid(P(0, -0.12, 0.02), np.array([bw * 0.95, 0.14, bw * 0.95]) * L, k=0.04 * L)   # breast
    hr = 0.085 if crow else 0.10
    hc = P(0, -0.30, 0.10 if not perched else 0.12)
    prog.sphere(hc, hr * L, k=0.06 * L)                                                        # head
    prog.capsule(P(0, -0.20, 0.05), hc, hr * 0.85 * L, k=0.05 * L)                              # neck
    bl = 0.17 if crow else 0.09
    bb = hc + np.array([0, -hr * 0.8 * L, -hr * 0.15 * L])
    tip = bb + np.array([0, -bl * L, -bl * (0.22 if crow else 0.1) * L])
    prog.cone(bb, tip, hr * (0.5 if crow else 0.45) * L, 0.004 * L, k=0.01 * L, label=L_BEAK, squash=1.2 if crow else 1.0)
    if crow:
        # nasal bristles: the feathers that sheathe the base of a crow's bill
        prog.ellipsoid(bb + np.array([0, -0.02 * L, 0.01 * L]), np.array([0.035, 0.05, 0.03]) * L, k=0.01 * L)
    info["head"] = hc
    info["head_r"] = hr * L
    # tail: a flat fan behind
    tl = 0.42 if crow else 0.40
    tc = P(0, 0.22 + tl * 0.5, -0.02)
    prog.ellipsoid(tc, np.array([0.07 if crow else 0.06, tl * 0.5, 0.012]) * L, k=0.02 * L)
    if perched:
        # folded wings: long slabs along the flanks, primaries crossing over the rump
        for sx in (1.0, -1.0):
            prog.ellipsoid(P(sx * bw * 0.85, 0.12, 0.03), np.array([0.035, 0.30, 0.09]) * L, k=0.03 * L)
            prog.ellipsoid(P(sx * bw * 0.35, 0.36, 0.075), np.array([0.03, 0.17, 0.022]) * L, k=0.03 * L)
        # legs and feet on the ground
        for sx in (1.0, -1.0):
            hip = P(sx * 0.05, 0.02, -0.06)
            ank = np.array([sx * 0.05 * L, hip[1] - 0.01 * L, 0.012 * L])
            prog.capsule(hip, ank, 0.010 * L, k=0.01 * L, label=L_BEAK)
            for ang in (-25.0, 0.0, 25.0):
                a = math.radians(ang)
                toe = ank + np.array([math.sin(a) * 0.07 * L, -math.cos(a) * 0.07 * L, -0.008 * L])
                prog.capsule(ank, toe, 0.005 * L, k=0.004 * L, label=L_BEAK)
            prog.capsule(ank, ank + np.array([0, 0.05 * L, -0.008 * L]), 0.005 * L, k=0.004 * L, label=L_BEAK)
    return prog, info


def _wing(p: dict, side: float, rng) -> tuple[list, list, list, list]:
    """A spread wing as a thin closed slab: (verts, faces, uv, span) lists. Chord follows the
    wing's outline, with a cambered top; the crow's tip splits into fingers."""
    L = float(p["length"])
    span = float(p["span"]) * 0.5
    crow = p["kind"] == "crow"
    sh = float(p.get("shoulder", 0.012))
    n_s = 16
    n_c = 6
    fingers = int(p.get("fingers", 0))
    th = 0.004 * L / 0.2
    verts, faces, uvs, spans = [], [], [], []

    def outline(t):
        """leading-edge y and chord at span fraction t (front = -Y)."""
        if crow:
            chord = 0.30 * L * (1.0 - 0.25 * t) if t < 0.62 else 0.30 * L * 0.85 * (1 - (t - 0.62) / 0.38 * 0.25)
            lead = -0.04 * L + 0.06 * L * t * t
        else:
            chord = 0.24 * L * math.sqrt(max(0.0, 1.0 - t ** 2.2)) + 0.03 * L
            lead = -0.03 * L + 0.10 * L * t ** 1.5
        return lead, chord

    def add_slab(ts, cs, finger_off=0.0):
        base = len(verts)
        rows = []
        for t in ts:
            lead, chord = outline(t)
            row = []
            for i, c in enumerate(cs):
                x = side * (sh + t * (span - sh))
                y = lead + c * chord + finger_off
                camber = math.sin(math.pi * c) * 0.03 * chord
                droop = -0.05 * L * t * t          # the tips droop a little in a glide
                z_top = camber + th * (1 - c) * (1 - 0.7 * t) + droop
                z_bot = camber * 0.6 - th * 0.3 * (1 - c) + droop
                row.append((x, y, z_top, z_bot, t, c, chord))
            rows.append(row)
        idx = {}
        for a, row in enumerate(rows):
            for b, (x, y, zt, zb, t, c, chord) in enumerate(row):
                for k, z in ((0, zt), (1, zb)):
                    idx[(a, b, k)] = len(verts)
                    verts.append((x, y, z))
                    uvs.append((abs(x), y))
                    spans.append(t)
        na, nb = len(rows), len(rows[0])
        for a in range(na - 1):
            for b in range(nb - 1):
                q = [idx[(a, b, 0)], idx[(a + 1, b, 0)], idx[(a + 1, b + 1, 0)], idx[(a, b + 1, 0)]]
                faces.append(q if side < 0 else q[::-1])
                q = [idx[(a, b, 1)], idx[(a, b + 1, 1)], idx[(a + 1, b + 1, 1)], idx[(a + 1, b, 1)]]
                faces.append(q if side < 0 else q[::-1])
        # close the edges (leading, trailing, tip; the root hides in the body)
        for a in range(na - 1):
            for b in (0, nb - 1):
                q = [idx[(a, b, 0)], idx[(a, b, 1)], idx[(a + 1, b, 1)], idx[(a + 1, b, 0)]]
                faces.append(q if (b == 0) == (side < 0) else q[::-1])
        for b in range(nb - 1):
            a = na - 1
            q = [idx[(a, b, 0)], idx[(a, b, 1)], idx[(a, b + 1, 1)], idx[(a, b + 1, 0)]]
            faces.append(q if side > 0 else q[::-1])
        del base

    tip_t = 0.62 if fingers else 1.0
    ts = [tip_t * (i / n_s) ** 0.85 for i in range(n_s + 1)]
    cs = [i / n_c for i in range(n_c + 1)]
    add_slab(ts, cs)
    if fingers:
        # separated primaries: narrow feathers fanning from the hand to the tip
        for f in range(fingers):
            c0 = f / fingers
            c1 = c0 + 0.82 / fingers
            fts = [tip_t - 0.04 + (1.0 - tip_t + 0.04) * (i / 6) for i in range(7)]
            fcs = [c0 + (c1 - c0) * (i / 2) for i in range(3)]
            # the outer fingers are the longest; they fan forward a little
            add_slab([min(1.0, t * (1.0 - 0.07 * f)) for t in fts], fcs, finger_off=-0.012 * L * (fingers - 1 - f))
    del rng
    return verts, faces, uvs, spans


def _mesh(name, verts, faces):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.update()
    return common.new_object(name, me)


def _plumage(obj, p: dict, info: dict, wing_span=None):
    """G pale (breast and belly; a crow has none), B dark (cap, eye stripe, primaries, tail tip)."""
    me = obj.data
    V = M.mesh_arrays(obj)
    L = float(p["length"])
    crow = p["kind"] == "crow"
    Nv = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get("normal", Nv)
    Nv = Nv.reshape(-1, 3)
    z0 = info["z0"]
    under = np.clip((-Nv[:, 2] - 0.1) / 0.5, 0, 1)
    breast = np.clip((-V[:, 1] / L + 0.05) / 0.2, 0, 1) * np.clip((z0 + 0.06 * L - V[:, 2]) / (0.08 * L), 0, 1)
    pale = np.zeros(len(V)) if crow else np.clip(np.maximum(under * 0.9, breast), 0, 1)
    if not crow:
        # a streaked breast: song sparrow-like flecks
        nz = S.Noise(int(p.get("seed", 1)))
        pale = pale * (0.75 + 0.25 * (nz.noise(V, 90.0 / L) > -0.1))
    hd = np.sqrt(((V - info["head"]) ** 2).sum(-1))
    cap = np.clip((info["head_r"] * 1.15 - hd) / (info["head_r"] * 0.4), 0, 1) * np.clip((V[:, 2] - info["head"][2]) / (0.03 * L) + 0.3, 0, 1)
    dark = np.maximum(cap * (0.7 if not crow else 1.0), np.full(len(V), 0.35 if crow else 0.0))
    tail = np.clip((V[:, 1] / L - 0.55) / 0.1, 0, 1) * 0.6
    dark = np.maximum(dark, tail)
    if wing_span is not None:
        ws = np.asarray(wing_span)
        dark = np.maximum(dark, np.clip((ws - 0.55) / 0.3, 0, 1) * (0.7 if not crow else 0.6))
        pale = np.where(ws > 0.0, 0.0, pale)
        # pale wing bars on the songbird's coverts
        if not crow:
            bar = (np.abs(V[:, 1] / L - 0.02) < 0.025) * (ws > 0.05) * (ws < 0.5)
            pale = np.maximum(pale, bar * 0.6)
    lv = np.zeros(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", lv)
    vcolor.set_channel(obj, 1, lambda co, n, li: float(pale[lv[li]]))
    vcolor.set_channel(obj, 2, lambda co, n, li: float(dark[lv[li]]))
    vcolor.fill_channel(obj, 3, 1.0)


def _uv_body(obj, L):
    me = obj.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    lv = np.zeros(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", lv)
    V = M.mesh_arrays(obj)
    ang = np.arctan2(V[:, 0], V[:, 2])
    r = 0.12 * L
    uv = np.stack([ang * r, V[:, 1]], -1)[lv]
    # keep each face on one branch of the angle
    ls = np.zeros(len(me.polygons), np.int32)
    lt = np.zeros(len(me.polygons), np.int32)
    me.polygons.foreach_get("loop_start", ls)
    me.polygons.foreach_get("loop_total", lt)
    ref = np.repeat(uv[ls, 0], lt)
    period = 2 * math.pi * r
    uv[:, 0] = np.where(uv[:, 0] - ref > period / 2, uv[:, 0] - period, np.where(uv[:, 0] - ref < -period / 2, uv[:, 0] + period, uv[:, 0]))
    me.uv_layers[0].data.foreach_set("uv", uv.astype(np.float32).ravel())


def _span_uv2(obj, span_per_vertex):
    me = obj.data
    while len(me.uv_layers) < 2:
        me.uv_layers.new(name=f"UV{len(me.uv_layers)}")
    lv = np.zeros(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", lv)
    sp = np.asarray(span_per_vertex)[lv]
    uv2 = np.stack([sp, np.zeros_like(sp)], -1).astype(np.float32)
    me.uv_layers[1].data.foreach_set("uv", uv2.ravel())


def build(params: dict, outputs: list[str]) -> None:
    mats = params.get("materials", {})
    L = float(params["length"])
    budget = params.get("budget", {})
    rng = np.random.default_rng(int(params.get("seed", 1)))
    objs = []
    for perched in (False, True):
        name = "perch" if perched else "fly"
        prog, info = _body_program(params, perched)
        body = AB.mesh_program(prog, name, L * 0.008, int(budget.get("body", 700)), pad=0.02 * L)
        lab = AB.label_faces(prog, body)
        M.assign_labels(body, lab, {L_FEATHER: mats.get("feathers", "feathers_songbird"), L_BEAK: mats.get("beak", "beak")})
        # eyes
        er = info["head_r"] * 0.22
        for sx in (1.0, -1.0):
            c = info["head"] + np.array([sx * info["head_r"] * 0.78, -info["head_r"] * 0.35, info["head_r"] * 0.2])
            bm = bmesh.new()
            bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=6, radius=er)
            bmesh.ops.translate(bm, vec=tuple(c), verts=bm.verts[:])
            me = bpy.data.meshes.new("eye")
            bm.to_mesh(me)
            bm.free()
            eo = common.new_object("eye", me)
            M.assign_labels(eo, np.zeros(len(me.polygons), np.int32), {0: mats.get("eye", "eye_animal")})
            body = common.join([body, eo], name)
        spans = None
        if not perched:
            nb = len(body.data.vertices)
            wv, wf, wuv, ws = [], [], [], []
            for side in (1.0, -1.0):
                v, f, uv, sp = _wing(params, side, rng)
                off = len(wv)
                wv += v
                wf += [[i + off for i in q] for q in f]
                wuv += uv
                ws += sp
            wing = _mesh("wing", wv, wf)
            M.assign_labels(wing, np.zeros(len(wf), np.int32), {0: mats.get("feathers", "feathers_songbird")})
            body = common.join([body, wing], name)
            spans = [0.0] * nb + ws
        _uv_body(body, L)
        if spans is not None:
            # wing UVs: span along U, chord along V (feathers lie chordwise)
            me = body.data
            lv = np.zeros(len(me.loops), np.int32)
            me.loops.foreach_get("vertex_index", lv)
            uv = np.zeros(len(me.loops) * 2, np.float32)
            me.uv_layers[0].data.foreach_get("uv", uv)
            uv = uv.reshape(-1, 2)
            V = M.mesh_arrays(body)
            sp = np.asarray(spans)
            on_wing = sp[lv] > 0.0
            uv[on_wing, 0] = np.abs(V[lv[on_wing], 0]) + 5.0
            uv[on_wing, 1] = V[lv[on_wing], 1]
            me.uv_layers[0].data.foreach_set("uv", uv.ravel())
        _span_uv2(body, spans if spans is not None else [0.0] * len(body.data.vertices))
        common.shade_smooth(body, angle_deg=70.0)
        objs.append((body, info, spans))
    for o, info, spans in objs:
        vcolor.bake_ao([o], samples=12, distance=0.08 * L / 0.2, strength=0.8, ground=info["z0"] > 0)
        _plumage(o, params, info, spans)
    export.export_glb(outputs[0], [o for o, _, _ in objs])
    print(f"[animal_bird] {params.get('name')}: " + ", ".join(f"{o.name} {common.triangle_count(o)}" for o, _, _ in objs))
