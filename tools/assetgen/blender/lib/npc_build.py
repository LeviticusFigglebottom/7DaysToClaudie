"""Living human bodies (trader-post NPCs): the Hollowed body pipeline with the infection left out.

Same skeleton, segments, stump caps, vertex data and shaders as the Hollowed (docs/CHARACTERS.md),
built from the same char_* libs, so a living body animates, LODs and imports exactly like one.
What differs from char_build.build_body:

* no Bloom: no tier growths (the gated caps and mats every Hollowed carries), no wounds or Bloom
  sites (vertex B stays 0), no blood (params blood 0), no bruising (params bruise 0); the skin's
  infection is switched off in the material (npc_skin: bloom_skin / pallor / mottle 0), not forked;
* clear eyes and a closed mouth come from params (remap eyes_hollow -> npc_eye, mouth_open 0);
* no fingernails (work gloves) and a few garments the Hollowed never wear, all SDF over the same
  cloth base: a quilted padded vest with pouches, an armband, work gloves and a short beard.

The dressing params (all optional) beyond char_dress.dress:
  vest     {"hem", "neck_front", "armhole", "thickness", "quilt" (channel spacing m),
            "pouches": [{"x", "h", "w", "hgt", "depth"}]}   (h = height above the pelvis, m)
  armband  {"side", "t" (fraction down the upper arm), "width"}
  gloves   {"cuff": distance up the forearm from the wrist (m)}
  beard    {"thickness", "line" (cheek line, head-local y), "moustache": bool}
"""
from __future__ import annotations

import bpy
import numpy as np

from . import char_body as B
from . import char_build as CB
from . import char_dress as D
from . import char_extras as X
from . import char_mesh as M
from . import char_pipeline as CP
from . import char_skel as K
from . import char_uv as U
from . import char_wardrobe as W
from . import common
from .char_attrs import FAR, signed_min
from .char_body import _n, smoothstep


# --------------------------------------------------------------------------------------------
# Garments
# --------------------------------------------------------------------------------------------

class PaddedVest(W.Top):
    """A sleeveless quilted vest: the Top vest cut (armholes, zip placket) puffed out between
    horizontal quilting channels, with the channel seams as stitch lines for the cloth shader."""

    def __init__(self, model, spec: dict, mz):
        super().__init__(model, {"type": "hivis", "sleeve": 0.0, "tears": [], **spec}, mz)
        self.quilt = float(spec.get("quilt", 0.075)) * model.s
        self.puff = float(spec.get("puff", 0.0035)) * model.s

    def _quilt(self, h):
        ph = h / self.quilt
        return np.abs(ph - np.round(ph)) * self.quilt          # distance to the nearest channel seam

    def sdf(self, P_all, d_base):
        d, lab = super().sdf(P_all, d_base)
        near = d < 0.02
        if near.any():
            P = P_all[near]
            q = self._quilt(self.mz.h(P))
            # a rounded channel: full height mid-channel, pinched to nothing at the seam
            bulge = np.sqrt(np.clip(q / (0.5 * self.quilt), 0.0, 1.0)) * self.puff
            d = d.copy()
            d[near] -= bulge
        return d, lab

    def fields(self, P):
        trim, seam, edge = super().fields(P)
        seam = signed_min(seam, self._quilt(self.mz.h(P)))
        return trim, seam, edge


class Armband(W.Garment):
    """A cloth band round one upper arm over the sleeve (the Program's yellow armband)."""

    def __init__(self, model, spec: dict, mz):
        s = model.s
        self.m, self.mz, self.spec = model, mz, spec
        self.kind = "armband"
        self.label = B.L_CAP
        side = spec.get("side", "L")
        self.f = model.arm[side]["ua"]
        self.c = float(spec.get("t", 0.42)) * self.f.len
        self.w = float(spec.get("width", 0.075)) * s * 0.5
        self.thick = float(spec.get("thickness", 0.0085)) * s

    def _band(self, P):
        f = self.f
        t = (P - f.head) @ f.axis
        r = np.sqrt(np.maximum(((P - f.head) ** 2).sum(-1) - t * t, 0.0))
        band = np.abs(t - self.c) - self.w
        return np.where(r < 0.11 * self.m.s, band, 1.0)

    def sdf(self, P, d_base):
        d = np.maximum(d_base - self.thick, self._band(P))
        return d, np.full(len(P), self.label, np.int16)

    def fields(self, P):
        n = len(P)
        return np.full(n, FAR), np.full(n, FAR), np.maximum(-self._band(P), 0.0001)


# --------------------------------------------------------------------------------------------
# Dressing beyond char_dress
# --------------------------------------------------------------------------------------------

def add_pouch(model, spec: dict, label: int) -> None:
    """A rounded box pouch with a flap, sitting on whatever the torso wears (surface hit from the
    trunk axis), on the boots program (hard union, owned by the torso segment)."""
    s = model.s
    mz = model.measures
    h = float(spec.get("h", 0.10)) * s
    x = float(spec.get("x", 0.08)) * s
    w = float(spec.get("w", 0.075)) * s * 0.5
    hgt = float(spec.get("hgt", 0.10)) * s * 0.5
    depth = float(spec.get("depth", 0.032)) * s * 0.5
    tf = W.TrunkFrame(model)
    probe = mz.pel + mz.up * h
    q0, _, idx, _ = W.closest_on_polyline(probe[None], tf.pts)
    R = tf.R[int(idx[0])]
    left, up, front = R[:, 0], R[:, 1], R[:, 2]
    origin = q0[0] + left * x
    p, nrm = D.surface_hit(model, origin, front, max_dist=0.4 * s)
    # sit flat against the panel: face along the surface normal, upright along the trunk
    zf = _n(nrm)
    yu = _n(up - zf * float(up @ zf))
    xl = np.cross(yu, zf)
    Rb = np.stack([xl, yu, zf], 1)
    c = p + zf * (depth - 0.004 * s)
    model.boots.box(c, np.array([w, hgt, depth]), R=Rb, rounding=0.006 * s, k=0.0, label=label)
    # the flap: a thin lid over the top third, a little wider and proud
    fc = c + yu * (hgt * 0.62) + zf * (depth + 0.0012 * s)
    model.boots.box(fc, np.array([w + 0.003 * s, hgt * 0.40, 0.0035 * s]), R=Rb, rounding=0.0028 * s, k=0.0, label=label)


def add_gloves(model, spec: dict) -> None:
    """Work gloves: the hand's own surface relabelled (glove material) and thickened a little,
    with a turned cuff a short way up the forearm."""
    s = model.s
    cuff = float(spec.get("cuff", 0.035)) * s
    for side in ("L", "R"):
        wr = model.skel.j[f"wrist.{side}"]
        ax = model.arm[side]["fa"].axis
        tip = model.skel.j[f"hand_tip.{side}"]

        def along(P, wr=wr, ax=ax):
            return (P - wr) @ ax

        def near(P, wr=wr, tip=tip):
            return B.polyline_dist(P, [wr - ax * 0.06 * s, wr, tip]) < 0.13 * s

        def region(P, along=along, near=near):
            return np.where(near(P), -cuff - along(P), 1.0)

        def inflate(P, along=along, near=near):
            a = along(P)
            on = near(P) * smoothstep(-cuff - 0.004 * s, -cuff + 0.004 * s, a)
            # the cuff stands a little proud of the back of the glove
            band = smoothstep(-cuff - 0.004 * s, -cuff + 0.002 * s, a) * (1 - smoothstep(-cuff + 0.016 * s, -cuff + 0.022 * s, a))
            return -(0.0012 * s * on + 0.0022 * s * band)
        lo = np.minimum(wr - ax * 0.10 * s, tip) - 0.12 * s
        hi = np.maximum(wr - ax * 0.10 * s, tip) + 0.12 * s
        model.skin.paint(region, lo, hi, B.L_HIDE)
        model.skin.displace(inflate, lo, hi)


def add_beard(model, spec: dict) -> None:
    """A short full beard (jaw, chin, cheeks below the cheekbones, sideburns) and a moustache, a
    few millimetres proud of the skin, clumped, on the hair program (head segment only); the
    lips stay clear, and it thins out under the jaw towards the neck cut."""
    s = model.s
    R, hc = model.hR, model.hc
    thick = float(spec.get("thickness", 0.0045)) * s
    line = float(spec.get("line", -0.030))
    moustache = bool(spec.get("moustache", True))
    nz = model.noise
    up_a, up_b = model.HP(-0.021, -0.0585, 0.0905), model.HP(0.021, -0.0585, 0.0905)
    lo_a, lo_b = model.jaw_point(-0.018, 0.80, 0.030), model.jaw_point(0.018, 0.80, 0.030)

    def beard(P):
        q = (P - hc) @ R / s                     # head-local (left, up, front), reference metres
        x, y, z = q[:, 0], q[:, 1], q[:, 2]
        ax_ = np.abs(x)
        # the cheek line: low on the cheek, rising to the sideburns just in front of the ear
        side = smoothstep(0.052, 0.068, ax_) * (1 - smoothstep(-0.005, 0.020, z))
        top = line - 0.008 * (1 - smoothstep(0.030, 0.055, ax_)) + 0.030 * side
        reg = y - (top + nz.noise(P, 60.0) * 0.002)
        reg = np.maximum(reg, -0.035 - z)                                    # nothing behind the ear
        reg = np.maximum(reg, -0.106 - y)                                    # ends under the jaw
        if moustache:
            mo = np.maximum(np.maximum(np.abs(y + 0.0495) - 0.0070, ax_ - 0.027), 0.072 - z)
            reg = np.minimum(reg, mo)
        d_lip = np.minimum(B.seg_dist(P, up_a, up_b)[0], B.seg_dist(P, lo_a, lo_b)[0]) / s
        reg = np.maximum(reg, 0.0065 - d_lip)                               # lips clear
        # The edges taper into the skin (no step): full thickness 8 mm inside the line. Outside
        # the line the shell is cut off (the head's segment skirt at the neck cut lies outside
        # the skin, and an unbounded shell took it over: a beard down the throat).
        inside = smoothstep(0.0, 0.008, -reg)
        clump = 0.7 + 0.6 * np.clip(nz.fbm(P * np.array([1.0, 1.0, 1.4]), 45.0, 2) + 0.5, 0, 1)
        ds, _ = model.skin.eval(P)
        return np.maximum(ds - thick * inside * clump + 0.0004 * s, reg * s)

    c = model.HP(0, -0.06, 0.03)
    model.hair.union(beard, c - 0.13 * s, c + 0.13 * s, k=0.0, label=B.L_HAIR)


def close_mouth(model) -> None:
    """The face builder always carves the Hollowed's slack mouth open (a slit at least 7 mm
    high). A living face at rest has its lips together: fill the slit with lip (skin) and cut
    only a fine parting line between them."""
    s = model.s
    R = model.hR
    Rl = R @ np.array([[1, 0, 0], [0, 0, 1], [0, 1, 0]])
    up_lip = model.HP(0, -0.0585, 0.090)
    lo_lip = model.jaw_point(0.0, 0.80, 0.030)
    mc = 0.5 * (up_lip + lo_lip)
    model.skin.ellipsoid(mc - R[:, 2] * 0.006 * s, np.array([0.022, 0.008, 0.0085]) * s, R=Rl, k=0.004 * s, label=B.L_SKIN)
    model.skin.ellipsoid(mc, np.array([0.020, 0.006, 0.0009]) * s, R=Rl, k=0.0006 * s, label=B.L_GORE, mode="sub")


def dress_npc(model, params: dict, rng) -> None:
    mz = model.measures
    if params.get("closed_mouth", True):
        close_mouth(model)
    if params.get("vest"):
        spec = dict(params["vest"])
        pouches = spec.pop("pouches", [])
        model.garments.append(PaddedVest(model, spec, mz))
        for pch in pouches:
            add_pouch(model, pch, B.L_HUNTER)
    if params.get("armband"):
        model.garments.append(Armband(model, params["armband"], mz))
    if params.get("gloves"):
        add_gloves(model, params["gloves"])
    if params.get("beard"):
        add_beard(model, params["beard"])


# --------------------------------------------------------------------------------------------
# Assembly (char_build.build_body without the infection)
# --------------------------------------------------------------------------------------------

def build_npc_body(params: dict):
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
    D.dress(model, params, rng)
    dress_npc(model, params, rng)
    coarse = CP.coarse_field(model)

    extras: dict[str, X.Part] = {}
    head_x = X.eyes(model)
    head_x.merge(X.teeth(model, rng))
    extras["body_head"] = head_x
    for seg, part in X.accessories(model, rng).items():
        extras.setdefault(seg, X.Part()).merge(part)
    for seg, part in X.buttons(model, rng).items():
        extras.setdefault(seg, X.Part()).merge(part)
    for seg, part in model.extra_parts.items():
        extras.setdefault(seg, X.Part()).merge(part)

    def part_tris(part):
        return sum(len(f) - 2 for f in part.F)
    extra_tris = sum(part_tris(pt) for pt in extras.values()) + CB.CAP_TRIS * len(B.STUMPS)
    targets = {seg: CB._parts_for(model, seg)[1] for seg in B.SEGMENTS}
    room = CB.BODY_BUDGET - extra_tris
    head_t = targets.get("body_head", 0)
    rest_t = float(sum(v for k, v in targets.items() if k != "body_head"))
    scale = min(1.0, (room - head_t) / rest_t) if rest_t > 0 else 1.0
    order = list(B.SEGMENTS)
    planned = {seg: int(targets[seg] * (1.0 if seg == "body_head" else scale)) for seg in order}
    objs, stats = [], {}
    mats = B.label_materials(params)
    face_labels: dict[str, np.ndarray] = {}
    over = 0
    for i, seg in enumerate(order):
        cfg = CB.SEG_CFG[seg]
        bb = CP.segment_bounds(model, coarse, seg)
        obj = CP.mesh_segment(model, seg, cfg["h"], bb[0], bb[1], name=seg)
        parts, _ = CB._parts_for(model, seg)
        tris = planned[seg]
        if seg != "body_head" and over > 0:
            later = sum(planned[s] for s in order[i:] if s != "body_head")
            cut = min(tris // 2, int(round(over * tris / max(1, later))))
            tris -= cut
            over -= cut
        CP.decimate_parts(obj, parts, tris)
        over = max(0, over + common.triangle_count(obj) - tris)
        labels = list(CP.label_faces(model, obj, seg))
        part = extras.get(seg)
        x_v0 = x_f0 = None
        if part is not None and part.V:
            x_v0, x_f0 = CB._append_part(obj, part)
            labels += part.L
        labels = np.array(labels[:len(obj.data.polygons)], dtype=np.int32)
        M.assign_labels(obj, labels, mats)
        face_labels[seg] = labels
        CB._uv_segment(model, obj, seg)
        if part is not None and x_f0 is not None:
            CB._set_part_uvs(obj, part, x_f0)
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
        M.assign_labels(o, np.array(lab), mats)
        c, n = model.cuts[cut]
        U.planar(o, c, n, (0.0, 0.0, 1.0) if abs(n[2]) < 0.9 else (0.0, 1.0, 0.0), scale=1.0)
        common.shade_smooth(o, angle_deg=60.0)
        o["_rigid"] = bone
        caps.append(o)
    CB._vertex_colors(model, objs, caps, rng)
    CB.shader_attrs(model, objs, extras, face_labels)
    CB._skin(arm, model, objs, caps)
    return arm, objs, caps, skel, model, stats


def height_of(objs) -> float:
    """Top of the rest-pose body (m)."""
    top = 0.0
    for o in objs:
        V = M.mesh_arrays(o)
        if len(V):
            top = max(top, float(V[:, 2].max()))
    return top

