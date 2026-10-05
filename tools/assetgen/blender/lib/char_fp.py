"""First-person arms (docs/CHARACTERS.md#first-person-arms): skeleton with finger bones, SDF arms
in Remand Program jumpsuit sleeves, the wrist tether, hand sockets and the fp_* action set.

Camera at the origin looking -Y (Blender), Z up; the player's right arm is at -X (screen right).
"""
from __future__ import annotations

import math

import numpy as np

from . import char_sdf as S
from .char_body import (L_JUMPSUIT, L_SKIN_HUMAN, L_TETHER, L_TETHER_SCREEN, LimbFrame, _n, polyline_dist,
                        smoothstep)
from .char_skel import Skeleton, rot_axis

FRONT = (0.0, -1.0, 0.0)
UP = (0.0, 0.0, 1.0)


def _fp_bones():
    bones = [("root", None, "root", "root_tail", UP)]
    for sd in ("L", "R"):
        bones += [
            (f"upper_arm.{sd}", "root", f"shoulder.{sd}", f"elbow.{sd}", UP),
            (f"forearm.{sd}", f"upper_arm.{sd}", f"elbow.{sd}", f"wrist.{sd}", UP),
            (f"hand.{sd}", f"forearm.{sd}", f"wrist.{sd}", f"hand_tip.{sd}", UP),
            (f"thumb_1.{sd}", f"hand.{sd}", f"th_cmc.{sd}", f"th_mcp.{sd}", f"th_up.{sd}"),
            (f"thumb_2.{sd}", f"thumb_1.{sd}", f"th_mcp.{sd}", f"th_tip.{sd}", f"th_up.{sd}"),
            (f"index_1.{sd}", f"hand.{sd}", f"ix_mcp.{sd}", f"ix_pip.{sd}", f"palm_back.{sd}"),
            (f"index_2.{sd}", f"index_1.{sd}", f"ix_pip.{sd}", f"ix_tip.{sd}", f"palm_back.{sd}"),
            (f"fingers_1.{sd}", f"hand.{sd}", f"md_mcp.{sd}", f"md_pip.{sd}", f"palm_back.{sd}"),
            (f"fingers_2.{sd}", f"fingers_1.{sd}", f"md_pip.{sd}", f"md_tip.{sd}", f"palm_back.{sd}"),
        ]
    return bones


FP_BONES = _fp_bones()
FP_NAMES = [b[0] for b in FP_BONES]
# finger layout in the hand frame: (lateral offset (+ towards thumb), MCP along, segment lengths)
FINGERS = {"ix": (0.024, 0.088, (0.040, 0.024, 0.020), 0.0088),
           "md": (0.007, 0.092, (0.045, 0.027, 0.021), 0.0092),
           "rg": (-0.010, 0.088, (0.042, 0.026, 0.020), 0.0086),
           "pk": (-0.025, 0.080, (0.033, 0.020, 0.018), 0.0076)}


class FPSkeleton(Skeleton):
    """Skeleton subclass whose z-hints may name joints (finger bend planes)."""

    def _zhint(self, name, zh):
        if isinstance(zh, str):
            sd = name[-1]
            head_joint = [b for b in FP_BONES if b[0] == name][0][2]
            if zh.startswith("palm_back"):
                return self.j[zh] - self.j[f"wrist.{sd}"]
            return self.j[zh] - self.j[head_joint]
        return zh


def fp_joints(p: dict):
    """Rest pose: relaxed 'ready' arms reaching into the lower part of the view."""
    j = {"root": np.zeros(3), "root_tail": np.array([0.0, -0.08, 0.0])}
    s = float(p.get("height", 1.78)) / 1.78
    for sd, sx in (("L", 1.0), ("R", -1.0)):
        sh = np.array([sx * 0.205, 0.070, -0.255]) * s
        el = sh + np.array([sx * 0.055, -0.205, -0.110]) * s
        wr = el + np.array([-sx * 0.090, -0.215, 0.105]) * s
        j[f"shoulder.{sd}"], j[f"elbow.{sd}"], j[f"wrist.{sd}"] = sh, el, wr
        sw = _n(wr - sh)
        pr = (el - sh) - sw * float((el - sh) @ sw)
        j[f"pole.{sd}"] = _n(pr)            # rest elbow direction (IK default -> exact rest pose)
        ax = _n(np.array([-sx * 0.22, -1.0, -0.06]))
        # backs of the hands face up/out towards the camera; palms down and slightly inwards
        back = _n(np.array([sx * 0.50, 0.20, 0.84]))
        back = _n(back - ax * float(back @ ax))
        lat = np.cross(ax, back)
        if lat[0] * sx > 0:      # +lat towards the thumb (the body midline side)
            lat = -lat
        j[f"palm_back.{sd}"] = wr + back * 0.05
        j[f"hand_tip.{sd}"] = wr + ax * 0.105 * s
        curl = 0.35
        for key, (lo, along, segs, rad) in FINGERS.items():
            mcp = wr + ax * along * s + lat * lo * s + back * 0.002 * s
            pts = [mcp]
            d = _n(ax + lat * lo * 1.2)
            bend_axis = _n(np.cross(d, back))
            ang = 0.0
            for si, ln in enumerate(segs):
                ang += curl * (0.7, 1.0, 0.6)[si]
                dd = rot_axis(bend_axis, -ang) @ d
                pts.append(pts[-1] + dd * ln * s)
            j[f"{key}_mcp.{sd}"], j[f"{key}_pip.{sd}"], j[f"{key}_dip.{sd}"], j[f"{key}_tip.{sd}"] = pts
        cmc = wr + ax * 0.020 * s + lat * 0.020 * s - back * 0.010 * s
        tdir = _n(ax * 0.70 + lat * 0.55 - back * 0.45)
        mcp = cmc + tdir * 0.045 * s
        t2 = _n(rot_axis(_n(np.cross(tdir, back)), -0.25) @ tdir)
        ip = mcp + t2 * 0.033 * s
        tip = ip + _n(rot_axis(_n(np.cross(tdir, back)), -0.5) @ tdir) * 0.028 * s
        j[f"th_cmc.{sd}"], j[f"th_mcp.{sd}"], j[f"th_ip.{sd}"], j[f"th_tip.{sd}"] = cmc, mcp, ip, tip
        j[f"th_up.{sd}"] = mcp + back * 0.03 - ax * 0.0
        j[f"grip.{sd}"] = wr + ax * 0.085 * s - back * 0.032 * s + lat * 0.004 * s
        j[f"lat.{sd}"] = lat
        j[f"axis.{sd}"] = ax
        j[f"back.{sd}"] = back
    return j


class FPModel:
    """SDF model of both arms: skin (human), jumpsuit sleeves, labels."""

    def __init__(self, sk: FPSkeleton, p: dict):
        self.sk = sk
        self.p = p
        self.s = float(p.get("height", 1.78)) / 1.78
        self.skin = S.Program(L_SKIN_HUMAN)
        self.sleeve = S.Program(L_JUMPSUIT)
        self.noise = S.Noise(int(p.get("seed", 1)) * 13 + 5)
        j = sk.j
        self.ua = {sd: LimbFrame(j[f"shoulder.{sd}"], j[f"elbow.{sd}"], sx, fwd_hint=(0, 0, 1)) for sd, sx in (("L", 1), ("R", -1))}
        self.fa = {sd: LimbFrame(j[f"elbow.{sd}"], j[f"wrist.{sd}"], sx, fwd_hint=(0, 0, 1)) for sd, sx in (("L", 1), ("R", -1))}

    def build(self):
        s = self.s
        j = self.sk.j
        for sd, sx in (("L", 1.0), ("R", -1.0)):
            ua, fa = self.ua[sd], self.fa[sd]
            # arm: upper arm, elbow, forearm (muscular working arms)
            self.skin.cone(ua.at(-0.1), ua.at(1.0), 0.046 * s, 0.036 * s, k=0.02 * s, label=L_SKIN_HUMAN, squash=0.92,
                           up_hint=ua.fwd)
            self.skin.sphere(fa.at(0.0, fwd=-0.018 * s), 0.016 * s, k=0.014 * s, label=L_SKIN_HUMAN)
            self.skin.cone(fa.at(0.0), fa.at(1.0), 0.039 * s, 0.025 * s, k=0.02 * s, label=L_SKIN_HUMAN, squash=0.78,
                           up_hint=_n(j[f"back.{sd}"]))
            self.skin.ellipsoid(fa.at(0.30, out=0.008 * s), np.array([0.027, 0.026, 0.085]) * s, R=fa.R(), k=0.016 * s,
                                label=L_SKIN_HUMAN)
            self.skin.sphere(fa.at(0.97, out=-0.013 * s, fwd=0.006 * s), 0.0075 * s, k=0.006 * s, label=L_SKIN_HUMAN)
            self._hand(sd, sx)
            # jumpsuit sleeve: offset of the arm cone down to a cuff above the wrist
            self._sleeve(sd, sx)

    def _hand(self, sd, sx):
        s = self.s
        j = self.sk.j
        wr, ax, back, lat = j[f"wrist.{sd}"], j[f"axis.{sd}"], j[f"back.{sd}"], j[f"lat.{sd}"]
        R = np.stack([lat, back, ax], 1)
        pc = wr + ax * 0.050 * s + back * 0.002 * s
        self.skin.box(pc, np.array([0.040, 0.0125, 0.042]) * s, R=R, rounding=0.010 * s, k=0.010 * s, label=L_SKIN_HUMAN)
        self.skin.ellipsoid(wr + ax * 0.016 * s - back * 0.002 * s, np.array([0.031, 0.016, 0.022]) * s, R=R, k=0.012 * s,
                            label=L_SKIN_HUMAN)
        self.skin.ellipsoid(wr + ax * 0.032 * s + lat * 0.022 * s - back * 0.011 * s, np.array([0.017, 0.013, 0.027]) * s,
                            R=R, k=0.010 * s, label=L_SKIN_HUMAN)
        for key, (lo, along, segs, rad) in FINGERS.items():
            pts = [j[f"{key}_mcp.{sd}"], j[f"{key}_pip.{sd}"], j[f"{key}_dip.{sd}"], j[f"{key}_tip.{sd}"]]
            self.skin.sphere(pts[0] + back * 0.004 * s, rad * 1.05 * s, k=0.004 * s, label=L_SKIN_HUMAN)
            for si in range(3):
                r0 = rad * (1.0 - 0.09 * si) * s
                self.skin.cone(pts[si], pts[si + 1], r0, r0 * 0.9, k=0.0025 * s, label=L_SKIN_HUMAN)
            # nail: flat plate on the back of the distal phalanx
            nail = pts[3] - _n(pts[3] - pts[2]) * 0.008 * s + back * rad * 0.55 * s
            self.skin.ellipsoid(nail, np.array([rad * 0.75, 0.0018, 0.008]) * s,
                                R=np.stack([lat, back, _n(pts[3] - pts[2])], 1), k=0.001 * s, label=L_SKIN_HUMAN)
        tp = [j[f"th_cmc.{sd}"], j[f"th_mcp.{sd}"], j[f"th_ip.{sd}"], j[f"th_tip.{sd}"]]
        for si, (r0, r1) in enumerate(((0.0135, 0.0115), (0.0112, 0.0102), (0.0100, 0.0090))):
            self.skin.cone(tp[si], tp[si + 1], r0 * s, r1 * s, k=0.005 * s, label=L_SKIN_HUMAN)

    def _sleeve(self, sd, sx):
        s = self.s
        j = self.sk.j
        ua, fa = self.ua[sd], self.fa[sd]
        nz = self.noise
        cuff = 0.86          # sleeve ends this far along the forearm (above the wrist bone / tether)
        pts = [ua.at(-0.15), j[f"elbow.{sd}"], fa.at(cuff)]

        def sl(P, ua=ua, fa=fa, pts=pts):
            d_arm, _ = self._arm_dist(P, sd)
            t_fa = ((P - fa.head) @ fa.axis) / fa.len
            region = (t_fa - cuff) * fa.len                      # > 0 beyond the cuff
            el = (P - j[f"elbow.{sd}"]) @ ua.axis
            folds = 0.0011 * s * np.sin(((P - fa.head) @ fa.axis) / (0.030 * s) * 2 * math.pi + nz.noise(P, 12.0) * 2.5) \
                * np.clip(nz.noise(P, 5.0) + 0.5, 0, 1)
            folds += 0.0018 * s * np.exp(-((el + 0.01 * s) / (0.05 * s)) ** 2) * (0.5 + 0.5 * nz.noise(P, 14.0))
            cuff_band = (1 - smoothstep(0.0, 0.025 * s, -region)) * 0.0035 * s
            dd = d_arm - (0.0075 * s + cuff_band + folds)
            return np.maximum(dd, region)
        lo = np.minimum.reduce([p_ for p_ in pts]) - 0.08 * s
        hi = np.maximum.reduce([p_ for p_ in pts]) + 0.08 * s
        self.sleeve.union(sl, lo, hi, k=0.0, label=L_JUMPSUIT)

    def _arm_dist(self, P, sd):
        """Distance to a smooth arm base shape (no hand) used for the sleeve offset."""
        s = self.s
        ua, fa = self.ua[sd], self.fa[sd]
        d1 = S.sd_round_cone(P, ua.at(-0.15), ua.at(1.0), 0.047 * s, 0.037 * s)
        d2 = S.sd_round_cone(P, fa.at(0.0), fa.at(1.0), 0.040 * s, 0.027 * s)
        return S.smin(d1, d2, 0.03 * s), None

    def eval_points(self, P):
        d, lab = self.skin.eval(P)
        d2, l2 = self.sleeve.eval(P)
        better = d2 < d
        d = np.minimum(d, d2)
        lab = np.where(better, l2, lab)
        # close the arms just behind the camera (the shoulders are never seen)
        for sd in ("L", "R"):
            ua = self.ua[sd]
            side = (P[:, 0] * (1 if sd == "L" else -1)) > 0
            cut = -((P - ua.at(0.30)) @ ua.axis)
            d = np.where(side, np.maximum(d, cut), d)
        return d, lab

    def eval_grid(self, origin, h, shape, seg=None, narrow=False):
        axes = [np.asarray(origin)[a] + np.arange(shape[a]) * h for a in range(3)]
        gx, gy, gz = np.meshgrid(*axes, indexing="ij")
        P = np.stack([gx.ravel(), gy.ravel(), gz.ravel()], -1)
        d = np.empty(len(P))
        for i in range(0, len(P), 250000):
            d[i:i + 250000] = self.eval_points(P[i:i + 250000])[0]
        return d.reshape(shape), None

    # ------------------------------------------------------------------------------------------
    def weights(self, V):
        """Per-vertex weights over FP_NAMES."""
        sk = self.sk
        bi = {n: i for i, n in enumerate(FP_NAMES)}
        W = np.zeros((len(V), len(FP_NAMES)))
        s = self.s
        for sd, sx in (("L", 1.0), ("R", -1.0)):
            side = (V[:, 0] * sx) > 0
            if not side.any():
                continue
            P = V[side]
            j = sk.j
            ua, fa = self.ua[sd], self.fa[sd]
            de = (P - j[f"elbow.{sd}"]) @ ua.axis
            w_fa = smoothstep(-0.030 * s, 0.035 * s, de)
            dw = (P - j[f"wrist.{sd}"]) @ fa.axis
            w_h = smoothstep(-0.020 * s, 0.022 * s, dw)
            Wl = np.zeros((len(P), len(FP_NAMES)))
            Wl[:, bi[f"upper_arm.{sd}"]] = 1 - w_fa
            Wl[:, bi[f"forearm.{sd}"]] = w_fa * (1 - w_h)
            hand_w = w_fa * w_h
            # fingers: soft assignment by distance to each phalanx capsule vs the palm
            caps = {
                f"thumb_1.{sd}": [(j[f"th_cmc.{sd}"], j[f"th_mcp.{sd}"])],
                f"thumb_2.{sd}": [(j[f"th_mcp.{sd}"], j[f"th_ip.{sd}"]), (j[f"th_ip.{sd}"], j[f"th_tip.{sd}"])],
                f"index_1.{sd}": [(j[f"ix_mcp.{sd}"], j[f"ix_pip.{sd}"])],
                f"index_2.{sd}": [(j[f"ix_pip.{sd}"], j[f"ix_dip.{sd}"]), (j[f"ix_dip.{sd}"], j[f"ix_tip.{sd}"])],
                f"fingers_1.{sd}": [(j[f"{k}_mcp.{sd}"], j[f"{k}_pip.{sd}"]) for k in ("md", "rg", "pk")],
                f"fingers_2.{sd}": [(j[f"{k}_pip.{sd}"], j[f"{k}_dip.{sd}"]) for k in ("md", "rg", "pk")] +
                                   [(j[f"{k}_dip.{sd}"], j[f"{k}_tip.{sd}"]) for k in ("md", "rg", "pk")],
            }
            dist = {}
            for bn, segs in caps.items():
                dist[bn] = np.min(np.stack([polyline_dist(P, [a, b]) for a, b in segs], 0), 0)
            # the palm: distance to the hand axis segment (wrist -> knuckle line)
            wr, axh = j[f"wrist.{sd}"], j[f"axis.{sd}"]
            palm_d = polyline_dist(P, [wr, wr + axh * 0.085 * s])
            names = list(caps) + [f"hand.{sd}"]
            D = np.stack([dist[n] for n in caps] + [palm_d * 0.9], 1)
            sig = 0.004 * s
            Ew = np.exp(-(D - D.min(1, keepdims=True)) / sig)
            Ew /= Ew.sum(1, keepdims=True)
            for k, n in enumerate(names):
                Wl[:, bi[n]] += hand_w * Ew[:, k]
            W[side] = Wl
        return W


def build_tether(sk: FPSkeleton, s: float):
    """Chunky wrist unit on the back of the left forearm: housing, recessed screen, strap, bolts.
    Returns list of (verts, faces, label, uv_rect_or_None)."""
    import bmesh
    from mathutils import Matrix, Vector

    j = sk.j
    fa_head, fa_tail = j["elbow.L"], j["wrist.L"]
    ax = _n(fa_tail - fa_head)
    back = _n(j["back.L"] - ax * float(j["back.L"] @ ax))
    lat = np.cross(back, ax)
    centre_axis = fa_head + ax * (np.linalg.norm(fa_tail - fa_head) - 0.052 * s)
    R = np.stack([lat, ax, back], 1)          # local x = across, y = along the forearm, z = up (dorsal)
    parts = []

    def box(cx, cy, cz, hx, hy, hz, bevel, label):
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=Vector((2 * hx, 2 * hy, 2 * hz)), verts=bm.verts)
        if bevel > 0:
            bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=1, affect="EDGES", profile=0.5)
        verts = [centre_axis + R @ (np.array(v.co) + np.array([cx, cy, cz])) for v in bm.verts]
        faces = [tuple(v.index for v in f.verts) for f in bm.faces]
        bm.free()
        parts.append((verts, faces, label, None))

    r_arm = 0.030 * s            # forearm half-thickness near the wrist (dorsal side)
    # strap: flattened band around the forearm
    n = 14
    verts, faces = [], []
    for yy in (-0.018 * s, 0.018 * s):
        for i in range(n):
            a = 2 * math.pi * i / n
            rx = 0.036 * s
            rz = 0.028 * s
            verts.append(centre_axis + R @ np.array([math.cos(a) * rx, yy, math.sin(a) * rz - 0.002 * s]))
    for yy in (-0.018 * s, 0.018 * s):
        for i in range(n):
            a = 2 * math.pi * i / n
            verts.append(centre_axis + R @ np.array([math.cos(a) * 0.031 * s, yy * 0.98, math.sin(a) * 0.023 * s - 0.002 * s]))
    for i in range(n):
        i2 = (i + 1) % n
        faces.append((i, i2, n + i2, n + i))                    # outer
        faces.append((2 * n + i2, 2 * n + i, 3 * n + i, 3 * n + i2))   # inner
        faces.append((i2, i, 2 * n + i, 2 * n + i2))           # edge -y
        faces.append((n + i, n + i2, 3 * n + i2, 3 * n + i))   # edge +y
    parts.append((verts, faces, L_TETHER, None))
    # housing on the dorsal side
    box(0.0, 0.0, r_arm + 0.010 * s, 0.024 * s, 0.032 * s, 0.011 * s, 0.004 * s, L_TETHER)
    # bezel ridge + screen (slightly recessed into the top)
    box(0.0, 0.003 * s, r_arm + 0.0215 * s, 0.019 * s, 0.024 * s, 0.0012 * s, 0.0008 * s, L_TETHER)
    sv = [centre_axis + R @ np.array([x, y, r_arm + 0.0229 * s]) for x, y in
          ((-0.016 * s, -0.019 * s), (0.016 * s, -0.019 * s), (0.016 * s, 0.025 * s), (-0.016 * s, 0.025 * s))]
    parts.append((sv, [(0, 1, 2, 3)], L_TETHER_SCREEN, [[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]]))
    # side bolts
    for bx in (-0.026 * s, 0.026 * s):
        for by in (-0.022 * s, 0.022 * s):
            bm = bmesh.new()
            bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.0035 * s, radius2=0.0035 * s, depth=0.006 * s)
            verts = [centre_axis + R @ (np.array([v.co.z, v.co.y, v.co.x]) + np.array([bx, by, r_arm + 0.008 * s]))
                     for v in bm.verts]
            faces = [tuple(v.index for v in f.verts) for f in bm.faces]
            bm.free()
            parts.append((verts, faces, L_TETHER, None))
    # status LED / button block
    box(0.0, -0.034 * s, r_arm + 0.006 * s, 0.008 * s, 0.004 * s, 0.005 * s, 0.0015 * s, L_TETHER)
    return parts, centre_axis, R


# --------------------------------------------------------------------------------------------
# Animation
# --------------------------------------------------------------------------------------------

def _R(axis, deg):
    return rot_axis(axis, math.radians(deg))


class FPRig:
    def __init__(self, sk: FPSkeleton):
        self.sk = sk
        self.s = 1.0

    def evaluate(self, prm: dict):
        """prm: hand targets (hand.S.x/y/z offsets from rest wrist), hand orientation (hand.S.pitch,
        yaw, roll in degrees, armature axes; tilt = world-lateral forward/back, applied last), elbow pole drop, grip.S (0 open..1 fist),
        thumb.S (0..1 tuck), index.S (extra index curl, -1 points), arm sway offsets."""
        sk = self.sk
        Q = {n: np.eye(3) for n in sk.names}
        for sd, sx in (("L", 1.0), ("R", -1.0)):
            wr = sk.j[f"wrist.{sd}"]
            tgt = wr + np.array([prm.get(f"hand.{sd}.x", 0.0), prm.get(f"hand.{sd}.y", 0.0), prm.get(f"hand.{sd}.z", 0.0)])
            pole = _n(sk.j[f"pole.{sd}"] + np.array([0.0, prm.get(f"elbow.{sd}.back", 0.0),
                                                      prm.get(f"elbow.{sd}.up", 0.0)]))
            sk.solve_two_bone(Q, f"upper_arm.{sd}", f"forearm.{sd}", tgt, pole, z_sign=-1.0)
            acc, _ = sk.fk(Q)
            # tilt: forward/back about the lateral axis applied last, so a thumb-up (rolled) grip
            # chops in the view plane (pitch turns the hand in its pre-roll frame).
            Rh = _R((1, 0, 0), prm.get(f"hand.{sd}.tilt", 0.0)) @ \
                _R((0, 0, 1), prm.get(f"hand.{sd}.yaw", 0.0) * sx) @ _R((0, 1, 0), prm.get(f"hand.{sd}.roll", 0.0) * sx) @ \
                _R((1, 0, 0), prm.get(f"hand.{sd}.pitch", 0.0))
            O = Rh @ sk.rest[f"hand.{sd}"]
            Q[f"hand.{sd}"] = acc[f"forearm.{sd}"].T @ O @ sk.rest[f"hand.{sd}"].T
            grip = float(prm.get(f"grip.{sd}", 0.3))
            idx = float(prm.get(f"index.{sd}", 0.0))
            thumb = float(prm.get(f"thumb.{sd}", grip))
            # finger curls about each bone's own x axis (bend towards the palm = -x rotation)
            for bn, amt in ((f"index_1.{sd}", 55 * (grip + idx)), (f"index_2.{sd}", 70 * (grip + idx)),
                            (f"fingers_1.{sd}", 62 * grip), (f"fingers_2.{sd}", 78 * grip)):
                Q[bn] = _R(sk.rest[bn][:, 0], -amt)
            Q[f"thumb_1.{sd}"] = _R(sk.rest[f"thumb_1.{sd}"][:, 0], -20 * thumb) @ \
                _R(sk.rest[f"thumb_1.{sd}"][:, 2], 18 * thumb * sx)
            Q[f"thumb_2.{sd}"] = _R(sk.rest[f"thumb_2.{sd}"][:, 0], -45 * thumb - float(prm.get(f"flick.{sd}", 0.0)))
        return Q, np.zeros(3)


def fp_actions(p: dict):
    """(name, frames, loop, generator(frame)->params)"""
    from .char_anim import Keys, ease, smooth_pulse
    base = {"grip.L": 0.30, "grip.R": 0.45, "thumb.L": 0.25, "thumb.R": 0.40}
    # Tool-ready stance (idle, walk, overhead swing): the right hand rolls thumb-up so a held tool's
    # handle (+Y of socket_hand.R runs towards the thumb) stands up and leans in instead of lying
    # flat across the view, and the empty off-hand drops towards the frame edge.
    ready = {**base, "hand.R.roll": 55.0, "hand.R.pitch": 8.0, "hand.R.x": -0.02, "hand.R.z": -0.035,
             "hand.L.x": 0.02, "hand.L.z": -0.04}

    def loop_sway(f, n, amp=1.0, bob=0.0):
        w = 2 * math.pi * f / n
        out = {}
        for sd, sx, ph in (("L", 1.0, 0.0), ("R", -1.0, 0.4)):
            out[f"hand.{sd}.x"] = 0.004 * amp * math.sin(w + ph)
            out[f"hand.{sd}.z"] = 0.005 * amp * math.sin(2 * w + ph) - bob * (0.5 + 0.5 * math.cos(2 * w + ph))
            out[f"hand.{sd}.y"] = 0.003 * amp * math.sin(w + 1.0 + ph)
            out[f"hand.{sd}.pitch"] = 1.5 * amp * math.sin(w + 0.5 + ph)
        return out

    def swayed(f, n, amp, stance):
        d = dict(stance)
        for k, v in loop_sway(f, n, amp).items():
            d[k] = d.get(k, 0.0) + v
        return d

    def idle(f, n=60, stance=ready):
        return swayed(f, n, 1.0, stance)

    def walk(f, n=30, stance=ready):
        w = 2 * math.pi * f / n
        d = swayed(f, n, 0.5, stance)
        for sd, sx, ph in (("L", 1.0, 0.0), ("R", -1.0, math.pi)):
            d[f"hand.{sd}.z"] = d.get(f"hand.{sd}.z", 0.0) - 0.014 * (0.5 + 0.5 * math.cos(2 * w)) + 0.004 * math.sin(w + ph)
            d[f"hand.{sd}.x"] = d.get(f"hand.{sd}.x", 0.0) + 0.010 * math.sin(w + ph)
            d[f"hand.{sd}.y"] = d.get(f"hand.{sd}.y", 0.0) + 0.012 * math.sin(w + ph)
        return d

    # Diagonal chop for the thumb-up grip: the head goes back over the right shoulder (still in
    # view), the grip rolls in as it comes down so the axe crosses the screen side-on at impact
    # (head at centre-left) and follows through low.
    swing_k = Keys(ready, [
        (0, {"grip.R": 0.9}),
        (7, {"grip.R": 1.0, "hand.R.x": -0.10, "hand.R.y": 0.0, "hand.R.z": 0.17, "hand.R.tilt": -40.0,
             "hand.R.roll": 70.0, "elbow.R.up": 0.7, "hand.L.y": 0.03, "hand.L.z": -0.05}, "out"),
        (10, {"grip.R": 1.0, "hand.R.x": -0.04, "hand.R.y": -0.03, "hand.R.z": 0.12, "hand.R.tilt": 0.0,
              "hand.R.roll": 50.0, "elbow.R.up": 0.5}, "in"),
        (13, {"grip.R": 1.0, "hand.R.x": 0.05, "hand.R.y": -0.07, "hand.R.z": 0.0, "hand.R.tilt": 35.0,
              "hand.R.roll": 15.0, "hand.L.z": -0.04}, "lin"),
        (16, {"grip.R": 1.0, "hand.R.x": 0.08, "hand.R.y": -0.05, "hand.R.z": -0.07, "hand.R.tilt": 45.0,
              "hand.R.roll": 5.0}, "out"),
        (24, {"grip.R": 0.9}, "inout")])
    side_k = Keys(base, [
        (0, {"grip.R": 0.9}),
        (7, {"grip.R": 1.0, "hand.R.x": -0.20, "hand.R.y": 0.12, "hand.R.z": 0.10, "hand.R.yaw": -55.0, "hand.R.roll": 40.0,
             "elbow.R.up": 0.5}, "out"),
        (11, {"grip.R": 1.0, "hand.R.x": 0.12, "hand.R.y": -0.14, "hand.R.z": 0.06, "hand.R.yaw": 20.0, "hand.R.roll": 60.0,
              "elbow.R.up": 0.3}, "in"),
        (14, {"grip.R": 1.0, "hand.R.x": 0.26, "hand.R.y": -0.06, "hand.R.z": 0.02, "hand.R.yaw": 55.0, "hand.R.roll": 60.0},
         "out"),
        (22, {"grip.R": 0.9}, "inout")])
    stab_k = Keys(base, [
        (0, {"grip.R": 0.9}),
        (4, {"grip.R": 1.0, "hand.R.y": 0.10, "hand.R.z": 0.02, "hand.R.pitch": -10.0}, "out"),
        (7, {"grip.R": 1.0, "hand.R.x": 0.06, "hand.R.y": -0.24, "hand.R.z": 0.08, "hand.R.pitch": 8.0}, "snap"),
        (10, {"grip.R": 1.0, "hand.R.x": 0.06, "hand.R.y": -0.22, "hand.R.z": 0.07, "hand.R.pitch": 8.0}),
        (16, {"grip.R": 0.9}, "inout")])
    throw_k = Keys(base, [
        (0, {"grip.R": 0.9}),
        (9, {"grip.R": 0.95, "hand.R.x": -0.10, "hand.R.y": 0.26, "hand.R.z": 0.36, "hand.R.pitch": -80.0, "elbow.R.up": 0.9,
             "hand.L.y": -0.08, "hand.L.z": 0.10, "hand.L.x": -0.02}, "out"),
        (13, {"grip.R": 0.9, "hand.R.x": 0.02, "hand.R.y": -0.18, "hand.R.z": 0.24, "hand.R.pitch": 10.0}, "in"),
        (15, {"grip.R": 0.0, "thumb.R": 0.0, "hand.R.x": 0.06, "hand.R.y": -0.24, "hand.R.z": 0.06, "hand.R.pitch": 40.0},
         "lin"),
        (24, {}, "inout")])
    wrist_hold = {"hand.L.x": -0.16, "hand.L.y": -0.06, "hand.L.z": 0.20, "hand.L.roll": -85.0, "hand.L.pitch": 10.0,
                  "hand.L.yaw": -15.0, "elbow.L.up": 0.7, "grip.L": 0.45, "hand.R.z": -0.04, "hand.R.y": 0.03}
    raise_k = Keys(base, [(0, {}), (15, wrist_hold, "inout")])
    lower_k = Keys(base, [(0, wrist_hold), (12, {}, "inout")])
    use_k = Keys(base, [
        (0, {}),
        (12, {"grip.R": 0.75, "hand.R.x": 0.12, "hand.R.y": 0.25, "hand.R.z": 0.22, "hand.R.pitch": -60.0, "hand.R.yaw": 20.0,
              "elbow.R.up": 0.4}, "inout"),
        (28, {"grip.R": 0.75, "hand.R.x": 0.13, "hand.R.y": 0.27, "hand.R.z": 0.25, "hand.R.pitch": -75.0, "hand.R.yaw": 20.0,
              "elbow.R.up": 0.4}),
        (40, {}, "inout")])
    carry_pose = {"grip.R": 0.85, "hand.R.x": 0.02, "hand.R.y": 0.30, "hand.R.z": 0.30, "hand.R.pitch": -40.0,
                  "hand.R.roll": 30.0, "elbow.R.up": 0.2, "elbow.R.back": -0.4, "grip.L": 0.6, "hand.L.x": -0.08,
                  "hand.L.y": 0.05, "hand.L.z": 0.12, "hand.L.roll": -20.0}
    place_k = Keys(base, [
        (0, {"grip.R": 0.8}),
        (9, {"grip.R": 0.8, "hand.R.x": 0.06, "hand.R.y": -0.22, "hand.R.z": -0.16, "hand.R.pitch": 35.0}, "inout"),
        (12, {"grip.R": 0.1, "thumb.R": 0.1, "hand.R.x": 0.06, "hand.R.y": -0.23, "hand.R.z": -0.17, "hand.R.pitch": 30.0}, "out"),
        (20, {}, "inout")])
    light_k = Keys(base, [
        (0, {}),
        (8, {"grip.L": 0.7, "thumb.L": 0.2, "hand.L.x": -0.10, "hand.L.y": -0.02, "hand.L.z": 0.12, "hand.L.pitch": -10.0,
             "hand.L.roll": -30.0, "elbow.L.up": 0.4}, "out"),
        (16, {"grip.L": 0.7, "thumb.L": 0.2, "hand.L.x": -0.10, "hand.L.y": -0.02, "hand.L.z": 0.12, "hand.L.pitch": -10.0,
              "hand.L.roll": -30.0, "elbow.L.up": 0.4}),
        (24, {}, "inout")])
    block_k = Keys(base, [
        (0, {}),
        (6, {"grip.R": 1.0, "hand.R.x": 0.10, "hand.R.y": -0.04, "hand.R.z": 0.26, "hand.R.roll": 75.0, "hand.R.yaw": 20.0,
             "elbow.R.up": 0.5, "hand.L.x": -0.05, "hand.L.y": -0.02, "hand.L.z": 0.22, "hand.L.roll": -60.0,
             "elbow.L.up": 0.5, "grip.L": 0.7}, "snap"),
        (12, {"grip.R": 1.0, "hand.R.x": 0.10, "hand.R.y": -0.04, "hand.R.z": 0.25, "hand.R.roll": 75.0, "hand.R.yaw": 20.0,
              "elbow.R.up": 0.5, "hand.L.x": -0.05, "hand.L.y": -0.02, "hand.L.z": 0.21, "hand.L.roll": -60.0,
              "elbow.L.up": 0.5, "grip.L": 0.7}, "out")])

    def light(f):
        d = light_k.at(f)
        d["flick.L"] = 60.0 * smooth_pulse(f, 10, 2, 1, 3)       # thumb strikes the wheel
        return d

    def carry(f, n=30):
        d = dict(carry_pose)
        for k, v in loop_sway(f, n, 0.6, bob=0.01).items():
            d[k] = d.get(k, 0.0) + v
        return {**base, **d}

    return [
        ("fp_idle", 60, True, lambda f: idle(f)),
        ("fp_walk_bob", 30, True, lambda f: walk(f)),
        ("fp_swing", 24, False, swing_k.at),
        ("fp_swing_side", 22, False, side_k.at),
        ("fp_stab", 16, False, stab_k.at),
        ("fp_throw", 24, False, throw_k.at),
        ("fp_raise_wrist", 15, False, raise_k.at),
        ("fp_lower_wrist", 12, False, lower_k.at),
        ("fp_use", 40, False, use_k.at),
        ("fp_carry_log", 30, True, lambda f: carry(f)),
        ("fp_place", 20, False, place_k.at),
        ("fp_light", 24, False, light),
        ("fp_block", 12, False, block_k.at),
    ]
