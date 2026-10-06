"""First-person arms (docs/CHARACTERS.md#first-person-arms, ADR-0029): skeleton with finger and
forearm-twist bones, SDF arms in a Remand jumpsuit with the sleeves rolled to the elbow, working
hands, the bolted wrist tether, hand sockets, and the fp_* action set baked from the hold poses in
game/data/config/viewmodel.json.

Blender: camera at the origin looking -Y, Z up; the player's right arm is at -X (screen right).
The data file is written in Godot camera space (x right, y up, z back): g2b() converts.
"""
from __future__ import annotations

import json
import math
import pathlib

import numpy as np

from . import char_sdf as S
from .char_body import LimbFrame, _n, polyline_dist, smoothstep
from .char_skel import Skeleton, rot_axis

UP = (0.0, 0.0, 1.0)
VIEWMODEL_JSON = pathlib.Path(__file__).resolve().parents[4] / "game" / "data" / "config" / "viewmodel.json"

# FP-only material labels (clear of char_body's ids) -> fp_* materials in game/data/materials/fp.json.
L_SKIN, L_SLEEVE, L_HOUSING, L_SCREEN, L_STRAP, L_METAL, L_NAIL, L_LED = range(40, 48)
LABEL_MATERIALS = {
    L_SKIN: "fp_skin", L_SLEEVE: "fp_sleeve", L_HOUSING: "fp_tether", L_SCREEN: "fp_tether_screen",
    L_STRAP: "fp_tether_strap", L_METAL: "fp_tether_metal", L_NAIL: "fp_nail", L_LED: "fp_tether_led",
}
SIDES = (("L", 1.0), ("R", -1.0))   # Blender x sign of each arm


def g2b(v) -> np.ndarray:
    """Godot camera space (x right, y up, z back) <-> Blender armature space (x left, y back... see
    module doc). The map is its own inverse and a proper rotation, so cross products carry over."""
    v = np.asarray(v, dtype=np.float64)
    return np.array([-v[0], v[2], v[1]])


C_G2B = np.array([[-1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, 1.0, 0.0]])


def load_config() -> dict:
    return json.loads(VIEWMODEL_JSON.read_text())


def _fp_bones():
    bones = [("root", None, "root", "root_tail", UP)]
    for sd in ("L", "R"):
        bones += [
            (f"upper_arm.{sd}", "root", f"shoulder.{sd}", f"elbow.{sd}", UP),
            (f"forearm.{sd}", f"upper_arm.{sd}", f"elbow.{sd}", f"wrist.{sd}", UP),
            # Takes most of the hand's roll about the forearm so pronation spreads along the
            # forearm instead of wringing the wrist (the radius turning round the ulna).
            (f"forearm_twist.{sd}", f"forearm.{sd}", f"twist.{sd}", f"wrist.{sd}", UP),
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
# finger layout in the hand frame: (lateral offset (+ towards thumb), MCP along, segment lengths, radius)
FINGERS = {"ix": (0.0245, 0.089, (0.041, 0.025, 0.020), 0.0096),
           "md": (0.0075, 0.093, (0.046, 0.028, 0.021), 0.0100),
           "rg": (-0.0100, 0.089, (0.043, 0.027, 0.020), 0.0094),
           "pk": (-0.0255, 0.081, (0.034, 0.021, 0.018), 0.0083)}


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
    """Rest pose (Blender space): working arms reaching into the lower view, elbows bent, hands in
    the neutral thumb-up grip most holds use, so the skinned wrists deform least where it matters."""
    j = {"root": np.zeros(3), "root_tail": np.array([0.0, 0.08, 0.0])}
    s = float(p.get("height", 1.78)) / 1.78
    for sd, sx in SIDES:
        gx = -sx                                  # Godot x sign (right arm at +x)
        sh = g2b([gx * 0.200, -0.245, 0.055]) * s
        el = sh + g2b(_n(np.array([gx * 0.30, -0.80, -0.46]))) * 0.295 * s
        wr = el + g2b(_n(np.array([-gx * 0.36, 0.42, -0.83]))) * 0.268 * s
        j[f"shoulder.{sd}"], j[f"elbow.{sd}"], j[f"wrist.{sd}"] = sh, el, wr
        j[f"twist.{sd}"] = el + (wr - el) * 0.45
        sw = _n(wr - sh)
        pr = (el - sh) - sw * float((el - sh) @ sw)
        j[f"pole.{sd}"] = _n(pr)            # rest elbow direction (IK default -> exact rest pose)
        ax = g2b(_n(np.array([-gx * 0.28, 0.22, -0.93])))
        back = g2b(np.array([gx * 0.95, 0.28, 0.05]))
        back = _n(back - ax * float(back @ ax))
        lat = np.cross(ax, back)
        if lat[2] < 0:                       # +lat towards the thumb: up in the neutral grip
            lat = -lat
        j[f"palm_back.{sd}"] = wr + back * 0.05
        j[f"hand_tip.{sd}"] = wr + ax * 0.105 * s
        curl = 0.35
        for key, (lo, along, segs, rad) in FINGERS.items():
            mcp = wr + ax * along * s + lat * lo * s + back * 0.002 * s
            pts = [mcp]
            d = _n(ax + lat * lo * 1.2)
            bend_axis = _n(np.cross(d, back))   # rotating by -angle curls towards the palm
            ang = 0.0
            for si, ln in enumerate(segs):
                ang += curl * (0.7, 1.0, 0.6)[si]
                dd = rot_axis(bend_axis, -ang) @ d
                pts.append(pts[-1] + dd * ln * s)
            j[f"{key}_mcp.{sd}"], j[f"{key}_pip.{sd}"], j[f"{key}_dip.{sd}"], j[f"{key}_tip.{sd}"] = pts
        cmc = wr + ax * 0.022 * s + lat * 0.021 * s - back * 0.011 * s
        tdir = _n(ax * 0.70 + lat * 0.55 - back * 0.45)
        tb = _n(np.cross(tdir, back))
        mcp = cmc + tdir * 0.046 * s
        ip = mcp + _n(rot_axis(tb, -0.25) @ tdir) * 0.034 * s
        tip = ip + _n(rot_axis(tb, -0.5) @ tdir) * 0.029 * s
        j[f"th_cmc.{sd}"], j[f"th_mcp.{sd}"], j[f"th_ip.{sd}"], j[f"th_tip.{sd}"] = cmc, mcp, ip, tip
        j[f"th_up.{sd}"] = mcp + back * 0.03
        j[f"grip.{sd}"] = wr + ax * 0.085 * s - back * 0.033 * s + lat * 0.004 * s
        j[f"lat.{sd}"] = lat
        j[f"axis.{sd}"] = ax
        j[f"back.{sd}"] = back
    return j


class FPModel:
    """SDF model of both arms: skin (human), the rolled jumpsuit sleeves, labels."""

    def __init__(self, sk: FPSkeleton, p: dict):
        self.sk = sk
        self.p = p
        self.s = float(p.get("height", 1.78)) / 1.78
        self.skin = S.Program(L_SKIN)
        self.sleeve = S.Program(L_SLEEVE)
        self.noise = S.Noise(int(p.get("seed", 1)) * 13 + 5)
        j = sk.j
        self.ua = {sd: LimbFrame(j[f"shoulder.{sd}"], j[f"elbow.{sd}"], sx, fwd_hint=(0, 0, 1)) for sd, sx in SIDES}
        self.fa = {sd: LimbFrame(j[f"elbow.{sd}"], j[f"wrist.{sd}"], sx, fwd_hint=(0, 0, 1)) for sd, sx in SIDES}
        # The forearm's own cross-section frame at the wrist: radial (thumb side) and dorsal (back).
        self.dorsal = {}
        self.radial = {}
        for sd, _ in SIDES:
            fa = self.fa[sd]
            b = j[f"back.{sd}"]
            self.dorsal[sd] = _n(b - fa.axis * float(b @ fa.axis))
            self.radial[sd] = _n(np.cross(fa.axis, self.dorsal[sd]))
            if float(self.radial[sd] @ j[f"lat.{sd}"]) < 0:
                self.radial[sd] = -self.radial[sd]
        self.roll_t = float(p.get("sleeve_roll", 0.17))   # rolled cuff this far along the forearm
        # The plane through each elbow between the upper arm and the forearm: the rest elbow is bent
        # past 90 deg, so "past the elbow along the upper arm" would put the hand on the upper arm.
        self.el_n = {sd: _n(self.ua[sd].axis + self.fa[sd].axis) for sd, _ in SIDES}

    def build(self):
        for sd, sx in SIDES:
            self._arm(sd, sx)
            self._hand(sd, sx)
            self._sleeve(sd, sx)

    # --- skin -------------------------------------------------------------------------------
    def _arm(self, sd, sx):
        s = self.s
        j = self.sk.j
        ua, fa = self.ua[sd], self.fa[sd]
        dor, rad = self.dorsal[sd], self.radial[sd]
        Rf = np.stack([rad, dor, fa.axis], 1)        # ellipsoid radii order: radial, dorsal, along
        # upper arm (under the sleeve) and the elbow
        self.skin.cone(ua.at(-0.1), ua.at(1.0), 0.050 * s, 0.040 * s, k=0.02 * s, squash=0.9, up_hint=ua.fwd)
        self.skin.sphere(fa.at(0.0) - dor * 0.010 * s, 0.020 * s, k=0.016 * s)
        # forearm: a working man's - full near the elbow, flat and wide at the wrist
        self.skin.cone(fa.at(0.02), fa.at(1.0), 0.041 * s, 0.0285 * s, k=0.022 * s, squash=0.74, up_hint=dor)
        self.skin.ellipsoid(fa.at(0.30) + dor * 0.004 * s, np.array([0.035, 0.031, 0.105]) * s, R=Rf, k=0.02 * s)
        # brachioradialis ridge on the thumb side, flexor mass on the palm side
        self.skin.ellipsoid(fa.at(0.22) + rad * 0.020 * s + dor * 0.006 * s, np.array([0.018, 0.020, 0.085]) * s,
                            R=Rf, k=0.016 * s)
        self.skin.ellipsoid(fa.at(0.34) - dor * 0.012 * s - rad * 0.006 * s, np.array([0.028, 0.024, 0.095]) * s,
                            R=Rf, k=0.018 * s)
        # wrist bones: the ulnar head and the radial styloid
        self.skin.sphere(j[f"wrist.{sd}"] - fa.axis * 0.012 * s - rad * 0.023 * s + dor * 0.007 * s, 0.0075 * s,
                         k=0.008 * s)
        self.skin.sphere(j[f"wrist.{sd}"] - fa.axis * 0.010 * s + rad * 0.024 * s, 0.0070 * s, k=0.008 * s)
        # palm-side tendons at the wrist and a few dorsal veins (raised, softly blended)
        for off in (-0.008, 0.004):
            a = fa.at(0.62) - dor * 0.019 * s + rad * off * s
            b = j[f"wrist.{sd}"] - dor * 0.016 * s + rad * off * 1.2 * s
            self.skin.capsule(a, b, 0.0035 * s, k=0.006 * s)
        r = np.random.default_rng(int(self.p.get("seed", 1)) + (7 if sd == "L" else 11))
        veins = [((0.12, 0.55), (0.62, 0.30), 0.0022), ((0.30, -0.20), (0.92, 0.05), 0.0019),
                 ((0.55, 0.40), (0.95, 0.15), 0.0016)]
        for (t0, a0), (t1, a1), vr in veins:
            pts = []
            for k in range(7):
                t = t0 + (t1 - t0) * k / 6
                ang = a0 + (a1 - a0) * k / 6 + float(r.uniform(-0.12, 0.12))
                # sit on the dorsal / radial surface of the forearm cone
                rr = (0.041 + (0.0285 - 0.041) * t) * s
                c = math.cos(ang * math.pi)
                sn = math.sin(ang * math.pi)
                pts.append(fa.at(t) + dor * c * rr * 0.80 + rad * sn * rr * 1.02)
            for a, b in zip(pts[:-1], pts[1:]):
                self.skin.capsule(a, b, vr * s, k=0.004 * s)

    def _hand(self, sd, sx):
        s = self.s
        j = self.sk.j
        wr, ax, back, lat = j[f"wrist.{sd}"], j[f"axis.{sd}"], j[f"back.{sd}"], j[f"lat.{sd}"]
        R = np.stack([lat, back, ax], 1)
        # palm block, the back of the hand's gentle arch, heel of the hand
        pc = wr + ax * 0.051 * s + back * 0.001 * s
        self.skin.box(pc, np.array([0.0415, 0.0135, 0.043]) * s, R=R, rounding=0.011 * s, k=0.010 * s)
        self.skin.ellipsoid(wr + ax * 0.052 * s + back * 0.007 * s, np.array([0.038, 0.010, 0.040]) * s, R=R, k=0.008 * s)
        self.skin.ellipsoid(wr + ax * 0.016 * s - back * 0.002 * s, np.array([0.033, 0.017, 0.023]) * s, R=R, k=0.012 * s)
        # thenar (thumb ball) and hypothenar pads on the palm side
        self.skin.ellipsoid(wr + ax * 0.034 * s + lat * 0.023 * s - back * 0.012 * s, np.array([0.018, 0.014, 0.028]) * s,
                            R=R, k=0.010 * s)
        self.skin.ellipsoid(wr + ax * 0.045 * s - lat * 0.027 * s - back * 0.010 * s, np.array([0.011, 0.012, 0.032]) * s,
                            R=R, k=0.010 * s)
        for key, (lo, along, segs, rad) in FINGERS.items():
            pts = [j[f"{key}_mcp.{sd}"], j[f"{key}_pip.{sd}"], j[f"{key}_dip.{sd}"], j[f"{key}_tip.{sd}"]]
            # knuckle (MCP head) on the back, tendon from the wrist to it
            self.skin.sphere(pts[0] + back * 0.0045 * s, rad * 0.98 * s, k=0.005 * s)
            self.skin.capsule(wr + ax * 0.018 * s + lat * lo * 0.55 * s + back * 0.012 * s,
                              pts[0] + back * 0.009 * s, 0.0026 * s, k=0.006 * s)
            for si in range(3):
                r0 = rad * (1.0 - 0.10 * si) * s
                self.skin.cone(pts[si], pts[si + 1], r0, r0 * 0.9, k=0.0025 * s)
                if si < 2:   # joint knuckles on the back of the finger
                    self.skin.sphere(pts[si + 1] + back * r0 * 0.3, r0 * 0.72, k=0.003 * s)
            # nail: a flat plate on the back of the distal phalanx, its own material
            fd = _n(pts[3] - pts[2])
            nail = pts[3] - fd * 0.008 * s + back * rad * 0.62 * s
            self.skin.ellipsoid(nail, np.array([rad * 0.78, 0.0020, 0.0085]) * s,
                                R=np.stack([lat, back, fd], 1), k=0.0012 * s, label=L_NAIL)
        tp = [j[f"th_cmc.{sd}"], j[f"th_mcp.{sd}"], j[f"th_ip.{sd}"], j[f"th_tip.{sd}"]]
        for si, (r0, r1) in enumerate(((0.0150, 0.0125), (0.0122, 0.0110), (0.0108, 0.0096))):
            self.skin.cone(tp[si], tp[si + 1], r0 * s, r1 * s, k=0.005 * s)
        tfd = _n(tp[3] - tp[2])
        tback = _n(np.cross(tfd, lat) if sd == "L" else np.cross(lat, tfd))
        if float(tback @ back) < -0.2:
            tback = -tback
        self.skin.ellipsoid(tp[3] - tfd * 0.008 * s + tback * 0.0062 * s, np.array([0.0080, 0.0021, 0.0092]) * s,
                            R=np.stack([_n(np.cross(tback, tfd)), tback, tfd], 1), k=0.0012 * s, label=L_NAIL)

    # --- sleeve -----------------------------------------------------------------------------
    def _sleeve(self, sd, sx):
        """Jumpsuit sleeve over the upper arm, rolled up to just below the elbow: a thick band of
        three folds, ragged and uneven, so the forearms are bare."""
        s = self.s
        j = self.sk.j
        ua, fa = self.ua[sd], self.fa[sd]
        nz = self.noise
        t_roll = self.roll_t
        band = 0.050 * s                                   # width of the roll along the forearm

        def sl(P, ua=ua, fa=fa):
            d_arm = self._arm_dist(P, sd)
            on_fa = (P - fa.head) @ self.el_n[sd]
            along_fa = np.where(on_fa > 0.0, (P - fa.head) @ fa.axis, -1.0)
            end = t_roll * fa.len
            # the roll's lower edge wanders a little round the arm
            wob = 0.006 * s * nz.noise(P, 30.0)
            beyond = along_fa - (end + wob)                # > 0 past the roll
            u = np.clip(1.0 - (end - along_fa) / band, 0.0, 1.0)   # 0 above the roll .. 1 at its edge
            folds = 0.0011 * s * np.sin(((P - fa.head) @ fa.axis) / (0.030 * s) * 2 * math.pi + nz.noise(P, 12.0) * 2.5) \
                * np.clip(nz.noise(P, 5.0) + 0.5, 0, 1)
            el = (P - j[f"elbow.{sd}"]) @ ua.axis
            folds += 0.0022 * s * np.exp(-((el + 0.01 * s) / (0.05 * s)) ** 2) * (0.5 + 0.5 * nz.noise(P, 14.0))
            # the roll: three stacked folds swelling out of the sleeve, thickest at the edge, lumpy
            ridge = np.abs(np.sin(u * 3.0 * math.pi * 0.98)) ** 0.7
            swell = smoothstep(0.0, 0.35, u)
            roll = 0.0080 * s * swell * (0.55 + 0.45 * ridge) * (0.8 + 0.4 * (nz.noise(P, 18.0) * 0.5 + 0.5))
            dd = d_arm - (0.0085 * s + folds * (1.0 - swell) + roll)
            return np.maximum(dd, beyond)
        pts = [ua.at(-0.15), j[f"elbow.{sd}"], fa.at(t_roll + 0.05)]
        lo = np.minimum.reduce([p_ for p_ in pts]) - 0.09 * s
        hi = np.maximum.reduce([p_ for p_ in pts]) + 0.09 * s
        self.sleeve.union(sl, lo, hi, k=0.0, label=L_SLEEVE)

    def _arm_dist(self, P, sd):
        """Distance to a smooth arm base shape (no hand) used for the sleeve offset."""
        s = self.s
        ua, fa = self.ua[sd], self.fa[sd]
        d1 = S.sd_round_cone(P, ua.at(-0.15), ua.at(1.0), 0.051 * s, 0.041 * s)
        d2 = S.sd_round_cone_ellip(P, fa.at(0.0), fa.at(0.6), 0.044 * s, 0.037 * s, 0.86, self.dorsal[sd])
        return S.smin(d1, d2, 0.03 * s)

    def eval_points(self, P):
        d, lab = self.skin.eval(P)
        # The SDF primitives label their unions 0 unless told otherwise: that is the skin here
        # (0 alone would map to the Hollowed's skin_hollow material).
        lab = np.where(lab == 0, L_SKIN, lab)
        d2, l2 = self.sleeve.eval(P)
        better = d2 < d
        d = np.minimum(d, d2)
        lab = np.where(better, l2, lab)
        # close the arms just behind the camera (the shoulders are never seen)
        for sd, sx in SIDES:
            ua = self.ua[sd]
            side = (P[:, 0] * sx) > 0
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
        for sd, sx in SIDES:
            side = (V[:, 0] * sx) > 0
            if not side.any():
                continue
            P = V[side]
            j = sk.j
            ua, fa = self.ua[sd], self.fa[sd]
            de = (P - j[f"elbow.{sd}"]) @ self.el_n[sd]
            w_fa = smoothstep(-0.030 * s, 0.030 * s, de)
            dw = (P - j[f"wrist.{sd}"]) @ fa.axis
            w_h = smoothstep(-0.020 * s, 0.022 * s, dw)
            # forearm twist ramps in from below the rolled sleeve to the wrist
            t_fa = ((P - fa.head) @ fa.axis) / fa.len
            w_tw = smoothstep(0.25, 0.92, t_fa)
            Wl = np.zeros((len(P), len(FP_NAMES)))
            Wl[:, bi[f"upper_arm.{sd}"]] = 1 - w_fa
            Wl[:, bi[f"forearm.{sd}"]] = w_fa * (1 - w_h) * (1 - w_tw)
            Wl[:, bi[f"forearm_twist.{sd}"]] = w_fa * (1 - w_h) * w_tw
            hand_w = w_fa * w_h
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


# --------------------------------------------------------------------------------------------
# Narrow-band meshing: fingers need a ~1 mm cell, which a dense grid over a whole arm cannot afford
# --------------------------------------------------------------------------------------------

def sparse_surface_nets(sdf, lo, hi, h: float, coarse: int = 4, band: float = 1.6, block: int = 8):
    """Surface nets of sdf (P (N,3) -> d (N,)) over the box lo..hi at cell h, evaluating the SDF
    only near the surface: a coarse lattice (every `coarse`-th point) finds the cells within
    band * coarse cell of the surface, and only their fine points are evaluated (in spatial blocks
    so the SDF program's AABB culling stays tight). Everything else takes the sign of the nearest
    coarse point. Same output conventions as char_mesh.surface_nets (verts in cell order, quads
    wound outward) with a fraction of the evaluations and memory. Returns (verts, quads)."""
    lo = np.asarray(lo, dtype=np.float64)
    ext = np.asarray(hi, dtype=np.float64) - lo
    cs = tuple(int(math.ceil(float(e) / (h * coarse))) + 1 for e in ext)     # coarse points per axis
    shape = tuple((c - 1) * coarse + 1 for c in cs)                          # fine points per axis
    H = h * coarse
    # coarse lattice, in x slabs
    axes = [lo[a] + np.arange(cs[a]) * H for a in range(3)]
    dc = np.empty(cs, np.float32)
    for i in range(cs[0]):
        gy, gz = np.meshgrid(axes[1], axes[2], indexing="ij")
        P = np.stack([np.full(gy.size, axes[0][i]), gy.ravel(), gz.ravel()], -1)
        dc[i] = sdf(P).reshape(cs[1], cs[2])
    # candidate coarse cells: any corner within the band
    a = np.abs(dc)
    m = a[:-1, :-1, :-1]
    for di in (0, 1):
        for dj in (0, 1):
            for dk in (0, 1):
                m = np.minimum(m, a[di:a.shape[0] - 1 + di, dj:a.shape[1] - 1 + dj, dk:a.shape[2] - 1 + dk])
    cand = m < band * H
    del a, m
    # fine field: nearest coarse sign everywhere, exact values in the candidate cells
    near = [np.minimum((np.arange(n) + coarse // 2) // coarse, c - 1) for n, c in zip(shape, cs)]
    d = dc[np.ix_(*near)]
    ncell = cand.shape
    f = np.arange(block * coarse + 1)
    for bi in range(0, ncell[0], block):
        for bj in range(0, ncell[1], block):
            for bk in range(0, ncell[2], block):
                cm = cand[bi:bi + block, bj:bj + block, bk:bk + block]
                if not cm.any():
                    continue
                nb = cm.shape
                pm = np.zeros(tuple(n * coarse + 1 for n in nb), bool)
                maps = []
                for ax_ in range(3):
                    ff = f[:nb[ax_] * coarse + 1]
                    ca = np.minimum(ff // coarse, nb[ax_] - 1)
                    cb = np.where(ff % coarse == 0, np.maximum(ff // coarse - 1, 0), ca)
                    maps.append((ca, cb))
                for x in maps[0]:
                    for y in maps[1]:
                        for z in maps[2]:
                            pm |= cm[np.ix_(x, y, z)]
                I, J, K = np.nonzero(pm)
                I = I + bi * coarse
                J = J + bj * coarse
                K = K + bk * coarse
                P = lo + np.stack([I, J, K], -1) * h
                d[I, J, K] = sdf(P)
    del dc, cand
    return _sparse_nets(d, lo, h)


def _sparse_nets(d: np.ndarray, origin, h: float):
    """Surface nets from a dense field touching only the sign-crossing edges."""
    nx, ny, nz = d.shape
    inside = d < 0.0
    cy, cz = ny - 1, nz - 1

    def key(i, j, k):
        return (i.astype(np.int64) * cy + j) * cz + k

    keys, pts, edges = [], [], []
    for axis in range(3):
        sl0 = [slice(None)] * 3
        sl1 = [slice(None)] * 3
        sl0[axis] = slice(0, -1)
        sl1[axis] = slice(1, None)
        I, J, K = np.nonzero(inside[tuple(sl0)] != inside[tuple(sl1)])
        e = np.zeros(3, np.int64)
        e[axis] = 1
        d0 = d[I, J, K].astype(np.float64)
        d1 = d[I + e[0], J + e[1], K + e[2]].astype(np.float64)
        den = d0 - d1
        den = np.where(np.abs(den) < 1e-12, 1e-12, den)
        t = np.clip(d0 / den, 0.0, 1.0)
        p = np.stack([I + t * e[0], J + t * e[1], K + t * e[2]], -1)
        others = [ax for ax in range(3) if ax != axis]
        for da in (0, 1):
            for db in (0, 1):
                c = [I, J, K]
                c = [c[0].copy(), c[1].copy(), c[2].copy()]
                c[others[0]] = c[others[0]] - da
                c[others[1]] = c[others[1]] - db
                ok = np.ones(len(I), bool)
                for ax, n in zip(range(3), (nx, ny, nz)):
                    ok &= (c[ax] >= 0) & (c[ax] <= n - 2)
                keys.append(key(c[0][ok], c[1][ok], c[2][ok]))
                pts.append(p[ok])
        edges.append((axis, I, J, K))
    allk = np.concatenate(keys)
    allp = np.concatenate(pts, 0)
    uk, inv = np.unique(allk, return_inverse=True)
    cnt = np.bincount(inv, minlength=len(uk)).astype(np.float64)
    S = np.stack([np.bincount(inv, weights=allp[:, a], minlength=len(uk)) for a in range(3)], -1)
    verts = np.asarray(origin, dtype=np.float64) + h * (S / cnt[:, None])

    def vid(i, j, k):
        return np.searchsorted(uk, key(i, j, k))

    quads = []
    for axis, I, J, K in edges:
        c = [I, J, K]
        o0, o1 = [ax for ax in range(3) if ax != axis]
        n = (nx, ny, nz)
        ok = (c[o0] >= 1) & (c[o0] <= n[o0] - 2) & (c[o1] >= 1) & (c[o1] <= n[o1] - 2)
        I, J, K = I[ok], J[ok], K[ok]
        if not len(I):
            continue
        if axis == 0:
            q = np.stack([vid(I, J - 1, K - 1), vid(I, J, K - 1), vid(I, J, K), vid(I, J - 1, K)], -1)
        elif axis == 1:
            q = np.stack([vid(I - 1, J, K - 1), vid(I - 1, J, K), vid(I, J, K), vid(I, J, K - 1)], -1)
        else:
            q = np.stack([vid(I - 1, J - 1, K), vid(I, J - 1, K), vid(I, J, K), vid(I - 1, J, K)], -1)
        flip = ~inside[I, J, K]
        q[flip] = q[flip][:, ::-1]
        quads.append(q)
    quads = np.concatenate(quads, 0) if quads else np.zeros((0, 4), np.int64)
    return verts, quads


# --------------------------------------------------------------------------------------------
# The tether: a rugged Remand Program wrist unit bolted over the back of the left wrist
# --------------------------------------------------------------------------------------------

def build_tether(sk: FPSkeleton, s: float, model: FPModel):
    """Housing, recessed landscape screen (u along the forearm, v across), bezel, bolts, straps
    with a lock block, side buttons, status LED and an antenna stub.
    Returns (parts, centre, R): parts = list of (verts, faces, label, uv_rects_or_None)."""
    import bmesh
    from mathutils import Vector

    j = sk.j
    fa = model.fa["L"]
    ax = fa.axis
    dor = model.dorsal["L"]
    rad = model.radial["L"]
    across = np.cross(ax, dor)                     # completes (across, along, up), right-handed
    R = np.stack([across, ax, dor], 1)
    # the little-finger side, where the screen image's top goes (+1: +across)
    top_sign = -1.0 if float(across @ rad) > 0 else 1.0
    centre_axis = j["wrist.L"] - ax * 0.062 * s
    r_up = 0.0215 * s                              # forearm surface height above the axis (dorsal)
    parts = []

    def emit(bm, label, uv=None, xf=lambda v: v):
        verts = [centre_axis + R @ xf(np.array(v.co)) for v in bm.verts]
        faces = [tuple(v.index for v in f.verts) for f in bm.faces]
        parts.append((verts, faces, label, uv))

    def box(cx, cy, cz, hx, hy, hz, bevel, label, segs=2):
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=Vector((2 * hx, 2 * hy, 2 * hz)), verts=bm.verts)
        if bevel > 0:
            bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=segs, affect="EDGES", profile=0.5)
        bmesh.ops.translate(bm, vec=Vector((cx, cy, cz)), verts=bm.verts)
        emit(bm, label)
        bm.free()

    def cyl(cx, cy, cz, radius, depth, label, axis="z", segs=8):
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=radius, radius2=radius, depth=depth)
        sw = {"z": lambda v: v, "x": lambda v: np.array([v[2], v[1], v[0]]), "y": lambda v: np.array([v[0], v[2], v[1]])}[axis]
        emit(bm, label, xf=lambda v, sw=sw: sw(v) + np.array([cx, cy, cz]))
        bm.free()

    L_, W_, H_ = 0.038 * s, 0.026 * s, 0.0105 * s      # half extents: along, across, height
    base = r_up - 0.002 * s
    # housing: a bevelled block with a lower skirt that hugs the forearm
    box(0.0, 0.0, base + H_, W_, L_, H_, 0.0042 * s, L_HOUSING, segs=3)
    box(0.0, 0.0, base + 0.002 * s, W_ * 1.04, L_ * 1.02, 0.0035 * s, 0.002 * s, L_HOUSING)
    # raised bezel round the screen, and the screen recessed into it
    top = base + 2 * H_
    sw_, sl_ = 0.0215 * s, 0.0335 * s                   # screen half extents (across, along): ~1.56:1
    for (cx, cy, hx, hy) in ((0, sl_ + 0.0018 * s, sw_ + 0.0035 * s, 0.0018 * s), (0, -sl_ - 0.0018 * s, sw_ + 0.0035 * s, 0.0018 * s),
                             (sw_ + 0.0018 * s, 0, 0.0018 * s, sl_), (-sw_ - 0.0018 * s, 0, 0.0018 * s, sl_)):
        box(cx, cy, top + 0.0007 * s, hx, hy, 0.0010 * s, 0.0006 * s, L_HOUSING, segs=1)
    # the screen sits just proud of the housing's top, inside the bezel (whose top is 1.4 mm higher)
    sz = top + 0.0003 * s
    corners = ((-sw_, -sl_), (sw_, -sl_), (sw_, sl_), (-sw_, sl_))   # counter-clockwise seen from above
    sv = [np.array([x, y, sz]) for x, y in corners]
    # u runs along the forearm towards the hand, the image's top towards the little-finger side
    # (up, when the wrist is raised to read it, thumb down): the screen reads landscape and upright
    # (the game renders the tether UI into it). Blender v is flipped against Godot's.
    parts.append(([centre_axis + R @ v for v in sv], [(0, 1, 2, 3)], L_SCREEN,
                  [[(0.5 + 0.5 * y / sl_, 0.5 + 0.5 * top_sign * x / sw_) for x, y in corners]]))
    # corner bolts (hex heads) and the side buttons
    for bx in (-W_ + 0.0045 * s, W_ - 0.0045 * s):
        for by in (-L_ + 0.0045 * s, L_ - 0.0045 * s):
            cyl(bx, by, top + 0.0008 * s, 0.0024 * s, 0.0022 * s, L_METAL, segs=6)
    for k, by in enumerate((-0.014 * s, 0.0 * s, 0.014 * s)):
        box(W_ + 0.0012 * s, by, base + H_, 0.0016 * s, 0.0042 * s, 0.0032 * s, 0.0008 * s, L_STRAP, segs=1)
    # status LED and the antenna stub at the elbow end
    box(-sw_ + 0.002 * s, L_ - 0.0022 * s, top + 0.0002 * s, 0.0016 * s, 0.0012 * s, 0.0008 * s, 0.0004 * s, L_LED, segs=1)
    cyl(W_ - 0.008 * s, -L_ - 0.004 * s, base + H_ * 1.2, 0.0042 * s, 0.012 * s, L_STRAP, axis="y", segs=8)
    # straps: two wide rubberised bands round the forearm with a lock block underneath
    n = 18
    for yy in (-L_ + 0.010 * s, L_ - 0.010 * s):
        verts, faces = [], []
        hw = 0.0085 * s
        for k_ in range(4):
            yk = yy + (-hw if k_ in (0, 2) else hw)
            for i in range(n):
                a = 2 * math.pi * i / n
                if k_ < 2:
                    rx, rz = 0.0335 * s, 0.0250 * s   # outer
                else:
                    rx, rz = 0.0300 * s, 0.0218 * s   # inner (against the skin)
                verts.append(np.array([math.cos(a) * rx, yk, math.sin(a) * rz - 0.001 * s]))
        for i in range(n):
            i2 = (i + 1) % n
            faces.append((i, i2, n + i2, n + i))
            faces.append((2 * n + i2, 2 * n + i, 3 * n + i, 3 * n + i2))
            faces.append((i2, i, 2 * n + i, 2 * n + i2))
            faces.append((n + i, n + i2, 3 * n + i2, 3 * n + i))
        parts.append(([centre_axis + R @ v for v in verts], faces, L_STRAP, None))
        box(0.0, yy, -0.0265 * s, 0.0085 * s, 0.0105 * s, 0.0045 * s, 0.0015 * s, L_METAL, segs=1)
    return parts, centre_axis, R


# --------------------------------------------------------------------------------------------
# Posing: hands placed by where they grip (point, thumb/handle direction, knuckle direction)
# --------------------------------------------------------------------------------------------

def _R(axis, deg):
    return rot_axis(np.asarray(axis, dtype=np.float64), math.radians(deg))


def _frame(x, z):
    z = _n(np.asarray(z, dtype=np.float64))
    x = np.asarray(x, dtype=np.float64)
    x = _n(x - z * float(x @ z))
    return np.stack([x, np.cross(z, x), z], 1)


def euler_g(rot) -> np.ndarray:
    """Rotation about Godot camera axes (pitch about x, yaw about y, roll about z; degrees,
    applied in that order), as a Blender-space matrix."""
    p, y, r = (math.radians(float(a)) for a in rot)
    cx, sx_ = math.cos(p), math.sin(p)
    cy, sy = math.cos(y), math.sin(y)
    cz, sz = math.cos(r), math.sin(r)
    mx = np.array([[1, 0, 0], [0, cx, -sx_], [0, sx_, cx]])
    my = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    mz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return C_G2B @ (mz @ my @ mx) @ C_G2B.T


class FPRig:
    """Evaluates hand placements into bone rotations: two-bone IK to the wrist, the hand turned to
    its grip, part of that turn handed to the forearm twist bone, and finger curls."""

    TWIST_SHARE = 0.7

    def __init__(self, sk: FPSkeleton):
        self.sk = sk
        j = sk.j
        self.S0 = {}
        self.grip_off = {}
        for sd, _ in SIDES:
            self.S0[sd] = _frame(j[f"axis.{sd}"], j[f"lat.{sd}"])
            self.grip_off[sd] = j[f"grip.{sd}"] - j[f"wrist.{sd}"]

    def hand(self, sd: str, grip, d, k):
        """(wrist target, hand world rotation) so the socket sits at `grip` with its handle axis
        (thumb side) along d and the knuckles towards k (all Blender space)."""
        Rh = _frame(k, d) @ self.S0[sd].T
        return np.asarray(grip) - Rh @ self.grip_off[sd], Rh

    def evaluate(self, prm: dict):
        """prm: per side 'S.wrist' (3,), 'S.Rh' (3x3), 'S.pole' (3,), and the scalars 'S.fist'
        (0 open..1 fist), 'S.thumb' (0..1 tuck), 'S.index' (extra index curl, -1 points), 'S.flick'
        (thumb strike, degrees)."""
        sk = self.sk
        Q = {n: np.eye(3) for n in sk.names}
        for sd, sx in SIDES:
            sk.solve_two_bone(Q, f"upper_arm.{sd}", f"forearm.{sd}", prm[f"{sd}.wrist"], prm[f"{sd}.pole"], z_sign=-1.0)
            acc, _ = sk.fk(Q)
            Rh = prm[f"{sd}.Rh"]
            A = acc[f"forearm.{sd}"]
            Qh = A.T @ Rh
            Q[f"hand.{sd}"] = Qh
            # swing-twist split of the hand's turn about the forearm's (rest-space) axis
            axis = sk.rest[f"forearm.{sd}"][:, 1]
            q = _quat(Qh)
            tw = 2.0 * math.atan2(float(q[1:] @ axis), q[0])
            if tw > math.pi:
                tw -= 2 * math.pi
            elif tw < -math.pi:
                tw += 2 * math.pi
            Q[f"forearm_twist.{sd}"] = rot_axis(axis, tw * self.TWIST_SHARE)
            grip = float(prm.get(f"{sd}.fist", 0.3))
            idx = float(prm.get(f"{sd}.index", 0.0))
            thumb = float(prm.get(f"{sd}.thumb", grip))
            for bn, amt in ((f"index_1.{sd}", 55 * (grip + idx)), (f"index_2.{sd}", 70 * (grip + idx)),
                            (f"fingers_1.{sd}", 62 * grip), (f"fingers_2.{sd}", 78 * grip)):
                Q[bn] = _R(sk.rest[bn][:, 0], -amt)
            # A closed thumb wraps the handle over the index and middle fingers (fitted so its tip
            # sits ~4 cm off the handle axis, on the fingers, not sticking out beside them).
            Q[f"thumb_1.{sd}"] = _R(sk.rest[f"thumb_1.{sd}"][:, 0], 30 * thumb) @ \
                _R(sk.rest[f"thumb_1.{sd}"][:, 2], 30 * thumb * sx)
            Q[f"thumb_2.{sd}"] = _R(sk.rest[f"thumb_2.{sd}"][:, 0], -60 * thumb - float(prm.get(f"{sd}.flick", 0.0)))
        return Q, np.zeros(3)


def _quat(m: np.ndarray) -> np.ndarray:
    """(w, x, y, z) of a rotation matrix (column-vector convention)."""
    t = m[0, 0] + m[1, 1] + m[2, 2]
    if t > 0:
        r = math.sqrt(1.0 + t) * 2
        return np.array([0.25 * r, (m[2, 1] - m[1, 2]) / r, (m[0, 2] - m[2, 0]) / r, (m[1, 0] - m[0, 1]) / r])
    if m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        r = math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
        return np.array([(m[2, 1] - m[1, 2]) / r, 0.25 * r, (m[0, 1] + m[1, 0]) / r, (m[0, 2] + m[2, 0]) / r])
    if m[1, 1] > m[2, 2]:
        r = math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
        return np.array([(m[0, 2] - m[2, 0]) / r, (m[0, 1] + m[1, 0]) / r, 0.25 * r, (m[1, 2] + m[2, 1]) / r])
    r = math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
    return np.array([(m[1, 0] - m[0, 1]) / r, (m[0, 2] + m[2, 0]) / r, (m[1, 2] + m[2, 1]) / r, 0.25 * r])


# --------------------------------------------------------------------------------------------
# Actions from the data file
# --------------------------------------------------------------------------------------------

SCALARS = ("fist", "thumb", "index", "flick")
DEFAULT_SCALARS = {"fist": 0.4, "thumb": 0.4, "index": 0.0, "flick": 0.0}


class Hand:
    """One hand's placement: grip point g, frame F (columns: knuckles, palm-ish, handle/thumb dir),
    elbow hint, curls; plus, for a hand on the other's handle, where along it and how turned."""

    __slots__ = ("g", "F", "elbow", "sc", "on", "along", "spin", "flip")

    def __init__(self, g, F, elbow, sc, on=None, along=0.0, spin=0.0, flip=False):
        self.g, self.F, self.elbow, self.sc = g, F, elbow, sc
        self.on, self.along, self.spin, self.flip = on, along, spin, flip


def _scalars(spec: dict, base: dict | None = None) -> dict:
    out = dict(base) if base else dict(DEFAULT_SCALARS)
    for c in SCALARS:
        if c in spec:
            out[c] = float(spec[c])
    return out


def _spec_hand(sd: str, spec: dict) -> Hand:
    """An absolute hand spec (Godot camera space) -> Hand (Blender space)."""
    if "on" in spec:
        return Hand(None, None, g2b(spec.get("elbow", [0.0, 0.0, 0.0])), _scalars(spec), on=spec["on"],
                    along=float(spec.get("along", 0.2)), spin=float(spec.get("spin", 0.0)), flip=bool(spec.get("flip", False)))
    d = g2b(_n(np.asarray(spec["dir"], dtype=np.float64)))
    if "back" in spec:
        # right hand: (knuckles, thumb, back) is right-handed; the left mirrors it
        b = g2b(_n(np.asarray(spec["back"], dtype=np.float64)))
        k = np.cross(d, b) if sd == "R" else np.cross(b, d)
    else:
        k = g2b(_n(np.asarray(spec["knuckles"], dtype=np.float64)))
    return Hand(g2b(spec["grip"]), _frame(k, d), g2b(spec.get("elbow", [0.0, 0.0, 0.0])), _scalars(spec))


def pose_hands(pose: dict) -> dict:
    return {sd: _spec_hand(sd, pose[sd]) for sd, _ in SIDES if sd in pose}


def _relative(h: Hand, ch: dict, sd: str) -> Hand:
    """A hold hand moved by keyed channels: S.move (m) and S.rot (pitch, yaw, roll deg about the
    camera axes, pivoting on the grip), S.elbow, S.along / S.spin and the curls."""
    mv = g2b(ch.get(f"{sd}.move", [0.0, 0.0, 0.0]))
    rot = ch.get(f"{sd}.rot", [0.0, 0.0, 0.0])
    el = h.elbow + g2b(ch.get(f"{sd}.elbow", [0.0, 0.0, 0.0]))
    sc = dict(h.sc)
    for c in SCALARS:
        if f"{sd}.{c}" in ch:
            sc[c] = float(ch[f"{sd}.{c}"])
    if h.on is not None:
        return Hand(None, euler_g(rot), el, sc, on=h.on, along=float(ch.get(f"{sd}.along", h.along)),
                    spin=float(ch.get(f"{sd}.spin", h.spin)), flip=h.flip)
    return Hand(h.g + mv, euler_g(rot) @ h.F, el, sc)


def _key_hands(hold: dict, key: dict) -> dict:
    out = {}
    for sd, _ in SIDES:
        if sd not in hold:
            continue
        if sd in key and isinstance(key[sd], dict):
            out[sd] = _spec_hand(sd, key[sd])
        else:
            out[sd] = _relative(hold[sd], key, sd)
    return out


def _slerp(qa, qb, t):
    if float(qa @ qb) < 0:
        qb = -qb
    d = float(np.clip(qa @ qb, -1.0, 1.0))
    if d > 0.9995:
        q = qa + (qb - qa) * t
        return q / np.linalg.norm(q)
    th = math.acos(d)
    return (math.sin((1 - t) * th) * qa + math.sin(t * th) * qb) / math.sin(th)


def _qmat(q):
    w, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def _lerp_hand(a: Hand, b: Hand, t: float) -> Hand:
    sc = {c: a.sc[c] + (b.sc[c] - a.sc[c]) * t for c in SCALARS}
    el = a.elbow + (b.elbow - a.elbow) * t
    F = _qmat(_slerp(_quat(a.F), _quat(b.F), t)) if a.F is not None and b.F is not None else None
    if a.on is not None:
        return Hand(None, F, el, sc, on=a.on, along=a.along + (b.along - a.along) * t, spin=a.spin + (b.spin - a.spin) * t,
                    flip=a.flip)
    return Hand(a.g + (b.g - a.g) * t, F, el, sc)


class PoseSolver:
    """Hands -> rig parameters. A hand 'on' the other grips its handle `along` metres up it
    (+ towards the head) with its knuckles turned `spin` degrees round it (its F, when keyed, is
    an extra rotation in camera axes)."""

    def __init__(self, rig: FPRig):
        self.rig = rig
        j = rig.sk.j
        self.pole0 = {sd: j[f"pole.{sd}"] for sd, _ in SIDES}

    def solve(self, hands: dict) -> dict:
        prm = {}
        placed = {}
        for sd, _ in sorted(SIDES, key=lambda s: 1 if hands[s[0]].on is not None else 0):
            h = hands[sd]
            if h.on is not None:
                o = placed[h.on]
                d0, k0 = o.F[:, 2], o.F[:, 0]
                g = o.g + d0 * h.along
                d = -d0 if h.flip else d0
                k = _R(d0, h.spin) @ k0
                if h.F is not None:
                    d, k = h.F @ d, h.F @ k
                F = _frame(k, d)
            else:
                g, F = h.g, h.F
            placed[sd] = Hand(g, F, h.elbow, h.sc)
            wrist, Rh = self.rig.hand(sd, g, F[:, 2], F[:, 0])
            prm[f"{sd}.wrist"], prm[f"{sd}.Rh"] = wrist, Rh
            prm[f"{sd}.pole"] = _n(self.pole0[sd] + h.elbow)
            for c in SCALARS:
                prm[f"{sd}.{c}"] = h.sc[c]
        return prm


def merge_pose(base: dict, over: dict) -> dict:
    """A hold pose with some hands replaced (guard, tether reading)."""
    out = {sd: dict(base.get(sd, {})) for sd, _ in SIDES}
    for sd, spec in over.items():
        if sd in ("L", "R"):
            out[sd] = dict(spec)
    return out


def _idle(pose: dict, n: int = 60) -> list[dict]:
    """A held pose with a tiny looping drift (the game's rig adds the big breathing and sway)."""
    hold = pose_hands(pose)
    frames = []
    for i in range(n + 1):
        w = 2 * math.pi * i / n
        ch = {"R.move": [0.0010 * math.sin(w + 0.7), 0.0018 * math.sin(w), 0.0],
              "R.rot": [0.6 * math.sin(w + 0.4), 0.0, 0.0],
              "L.move": [0.0, 0.0016 * math.sin(w + 1.3), 0.0], "L.rot": [0.5 * math.sin(w + 2.0), 0.0, 0.0]}
        frames.append(_key_hands(hold, ch))
    return frames


def _keyed(pose: dict, keys: list, n: int) -> list[dict]:
    """Per-frame hands from [frame, channels-or-hands, ease] keys (positions eased, frames slerped)."""
    from .char_anim import ease
    hold = pose_hands(pose)
    ks = sorted(((int(k[0]), _key_hands(hold, k[1]), k[2] if len(k) > 2 else "inout") for k in keys), key=lambda k: k[0])
    frames = []
    for f in range(n + 1):
        if f <= ks[0][0]:
            frames.append(ks[0][1])
            continue
        if f >= ks[-1][0]:
            frames.append(ks[-1][1])
            continue
        for (f0, h0, _), (f1, h1, e1) in zip(ks[:-1], ks[1:]):
            if f0 <= f <= f1:
                t = ease((f - f0) / max(f1 - f0, 1), e1)
                frames.append({sd: _lerp_hand(h0[sd], h1[sd], t) for sd in h0})
                break
    return frames


def fp_actions(cfg: dict):
    """[(name, frames, loop, per-frame hands)] for every action the data asks for: per hold class
    its idle (fp_<class>), guard (fp_<class>_guard) and tether-reading (fp_<class>_tether) loops;
    every attack (fp_<style>) and use (fp_<use>) keyed on its hold."""
    holds = cfg["holds"]
    tether = cfg.get("tether", {})
    out = []
    for cls, h in holds.items():
        if cls.startswith("_") or "pose" not in h:
            continue
        pose = h["pose"]
        out.append((f"fp_{cls}", 60, True, _idle(pose)))
        if "guard" in h:
            out.append((f"fp_{cls}_guard", 60, True, _idle(merge_pose(pose, h["guard"]))))
        if "pose" in tether and not h.get("no_tether", False):
            over = {"L": tether["pose"]["L"]}
            if "tether_right" in h:
                over["R"] = h["tether_right"]
            out.append((f"fp_{cls}_tether", 60, True, _idle(merge_pose(pose, over))))
    for group in ("attacks", "uses"):
        for name, a in cfg.get(group, {}).items():
            if name.startswith("_") or "keys" not in a:
                continue
            pose = holds[a["hold"]]["pose"]
            if "pose" in a:
                pose = merge_pose(pose, a["pose"])
            n = int(a["frames"])
            out.append((f"fp_{name}", n, bool(a.get("loop", False)), _keyed(pose, a["keys"], n)))
    return out
