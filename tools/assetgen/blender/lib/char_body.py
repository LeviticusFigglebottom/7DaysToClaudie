"""Hollowed body model: anatomy SDF (skin), clothing, boots, hair, Bloom growths, wounds,
dismemberment segment regions and the continuous skinning-weight function.

Everything is driven by the skeleton (char_skel.build_joints) so proportions/posture params
propagate to the whole body. Units: metres, Blender Z-up, front = -Y, left = +X.
"""
from __future__ import annotations

import math

import numpy as np

from . import char_sdf as S
from .char_skel import BONE_NAMES, Skeleton, _n, rot_axis

# Material labels (index -> material id). Labels are SDF payloads; materials are assigned per face.
L_SKIN, L_FLANNEL, L_TSHIRT, L_JACKET, L_HOSPITAL, L_DENIM, L_BOOT, L_HAIR, L_BLOOM, L_GORE, L_TEETH, L_EYES = range(12)
L_SKIN_HUMAN, L_JUMPSUIT, L_TETHER, L_TETHER_SCREEN = 12, 13, 14, 15
LABEL_MATERIALS = {
    L_SKIN: "skin_hollow", L_FLANNEL: "cloth_flannel", L_TSHIRT: "cloth_tshirt", L_JACKET: "cloth_jacket",
    L_HOSPITAL: "cloth_hospital", L_DENIM: "cloth_denim", L_BOOT: "leather_boot", L_HAIR: "hair",
    L_BLOOM: "bloom_growth", L_GORE: "gore", L_TEETH: "teeth", L_EYES: "eyes_hollow",
    L_SKIN_HUMAN: "skin_human", L_JUMPSUIT: "cloth_jumpsuit", L_TETHER: "tether", L_TETHER_SCREEN: "tether_screen",
}
CLOTH_LABELS = {"flannel": L_FLANNEL, "tshirt": L_TSHIRT, "jacket": L_JACKET, "hospital": L_HOSPITAL,
                "denim": L_DENIM, "canvas": L_JACKET}

SEGMENTS = ["body_head", "body_torso", "body_upper_arm.L", "body_forearm.L", "body_upper_arm.R",
            "body_forearm.R", "body_thigh.L", "body_shin.L", "body_thigh.R", "body_shin.R"]
# Stump caps: name -> (parent segment that keeps the cap, cut id, rigid bone)
STUMPS = {
    "stump_neck": ("body_torso", "neck", "neck"),
    "stump_shoulder.L": ("body_torso", "shoulder.L", "shoulder.L"),
    "stump_shoulder.R": ("body_torso", "shoulder.R", "shoulder.R"),
    "stump_elbow.L": ("body_upper_arm.L", "elbow.L", "upper_arm.L"),
    "stump_elbow.R": ("body_upper_arm.R", "elbow.R", "upper_arm.R"),
    "stump_hip.L": ("body_torso", "hip.L", "hips"),
    "stump_hip.R": ("body_torso", "hip.R", "hips"),
    "stump_knee.L": ("body_thigh.L", "knee.L", "thigh.L"),
    "stump_knee.R": ("body_thigh.R", "knee.R", "thigh.R"),
}

OVERLAP = 0.009      # how far each segment extends past its cut (closed there with a gore cap)
INSET = 0.0035       # how far the overlapping skirt is tucked under the neighbour's surface
INSET_RAMP = 0.004


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def seg_dist(P, a, b):
    """Distance from points to segment ab and the clamped parameter t."""
    ab = b - a
    t = np.clip(((P - a) @ ab) / max(float(ab @ ab), 1e-12), 0.0, 1.0)
    q = a + t[:, None] * ab
    return np.sqrt(((P - q) ** 2).sum(-1)), t


def polyline_dist(P, pts, P2=None):
    """Distance from points to a polyline (vectorized with one matmul for all segments)."""
    pts = [np.asarray(p, dtype=np.float64) for p in pts]
    if P2 is None:
        P2 = (P * P).sum(-1)
    A = np.stack(pts[:-1], 1)                  # (3, k) segment starts
    D = np.stack([b - a for a, b in zip(pts[:-1], pts[1:])], 1)   # (3, k) directions
    PA = P @ A                                 # (N, k)
    PD = P @ D
    aa = (A * A).sum(0)
    ad = (A * D).sum(0)
    dd = np.maximum((D * D).sum(0), 1e-12)
    u = PD - ad                                # (P - a).d
    t = np.clip(u / dd, 0.0, 1.0)
    dist2 = P2[:, None] - 2 * PA + aa - 2 * t * u + t * t * dd
    return np.sqrt(np.maximum(dist2.min(1), 0.0))


class LimbFrame:
    """Semantic frame of a limb bone: axis (head->tail), fwd (anterior), out (away from body)."""

    def __init__(self, head, tail, side: float, fwd_hint=(0.0, -1.0, 0.0)):
        self.head = np.asarray(head, dtype=np.float64)
        self.tail = np.asarray(tail, dtype=np.float64)
        self.axis = _n(self.tail - self.head)
        f = np.asarray(fwd_hint, dtype=np.float64)
        self.fwd = _n(f - self.axis * float(f @ self.axis))
        o = np.cross(self.axis, self.fwd)
        if o[0] * side < 0:
            o = -o
        self.out = _n(o)
        self.len = float(np.linalg.norm(self.tail - self.head))

    def at(self, t: float, out: float = 0.0, fwd: float = 0.0) -> np.ndarray:
        """Point at fraction t along the bone, offset by out/fwd metres."""
        return self.head + self.axis * (t * self.len) + self.out * out + self.fwd * fwd

    def R(self) -> np.ndarray:
        """Columns (out, fwd, axis) -> local frame for ellipsoids (radii order out, fwd, axis)."""
        return np.stack([self.out, self.fwd, self.axis], axis=1)


class BodyModel:
    def __init__(self, skel: Skeleton, params: dict):
        self.skel = skel
        self.p = params
        self.H = float(params.get("height", 1.75))
        self.s = self.H / 1.75
        self.build = float(params.get("build", 0.3))
        self.gaunt = float(np.clip(params.get("gaunt", 1.0 - 1.6 * self.build), 0.0, 1.0))
        self.fem = 1.0 if params.get("sex", "m") == "f" else 0.0
        self.t = 0.78 + 0.5 * self.build   # soft tissue factor
        self.noise = S.Noise(int(params.get("seed", 1)) * 7 + 3)
        self.skin = S.Program(L_SKIN)
        self.base = S.Program(L_SKIN)      # smoothed body used as the cloth base
        self.boots = S.Program(L_BOOT)
        self.hair = S.Program(L_HAIR)
        self.growth = S.Program(L_BLOOM)
        self.garments: list = []           # callables (P, d_base) -> (d, label)
        self.wounds: list = []             # (center, radius, amount) for vertex colour G
        self.bloom_sites: list = []        # (center, radius, amount) for vertex colour B
        self.bloom_extras: list = []       # filament / shelf sites (char_extras.bloom)
        j = skel.j
        self.arm = {}
        self.leg = {}
        for side, sx in (("L", 1.0), ("R", -1.0)):
            self.arm[side] = {
                "ua": LimbFrame(j[f"shoulder.{side}"], j[f"elbow.{side}"], sx),
                "fa": LimbFrame(j[f"elbow.{side}"], j[f"wrist.{side}"], sx),
                "hand": LimbFrame(j[f"wrist.{side}"], j[f"hand_tip.{side}"], sx),
            }
            self.leg[side] = {
                "th": LimbFrame(j[f"hip.{side}"], j[f"knee.{side}"], sx),
                "sh": LimbFrame(j[f"knee.{side}"], j[f"ankle.{side}"], sx),
            }
        # Head centre and frame (left, up, front) from the head bone.
        R = skel.rest["head"]
        self.hR = R
        self.hc = skel.head["head"] + R @ np.array([0.0, 0.072, 0.024]) * self.s
        Rn = skel.rest["neck"]
        self.nR = Rn

    # ------------------------------------------------------------------------------------------
    # helpers
    def T(self, bone, x, y, z):
        """Torso/head bone-local offset: x = left, y = along the bone (up), z = front."""
        return self.skel.head[bone] + self.skel.rest[bone] @ (np.array([x, y, z]) * self.s)

    def HP(self, x, y, z):
        """Head-local point (x left, y up, z front) relative to the head centre (metres*s)."""
        return self.hc + self.hR @ (np.array([x, y, z]) * self.s)

    # ------------------------------------------------------------------------------------------
    # Anatomy
    def build_anatomy(self):
        self._torso(self.skin, detail=True)
        self._torso(self.base, detail=False)
        self._neck(self.skin, detail=True)
        self._neck(self.base, detail=False)
        self._head(self.skin)
        for side, sx in (("L", 1.0), ("R", -1.0)):
            self._arm(self.skin, side, sx, detail=True)
            self._arm(self.base, side, sx, detail=False)
            self._hand(self.skin, side, sx)
            self._leg(self.skin, side, sx, detail=True)
            self._leg(self.base, side, sx, detail=False)
            if not self.p.get("boots", {}).get(side, False):
                self._foot(self.skin, side, sx)

    def _torso(self, prog: S.Program, detail: bool):
        s, t, g, fem, b = self.s, self.t, self.gaunt, self.fem, self.build
        wmul = 0.95 + 0.20 * b
        dmul = 0.90 + 0.30 * b
        belly = float(self.p.get("belly", max(0.0, b - 0.5) * 1.6))
        Rc = self.skel.rest["chest"] @ np.array([[1, 0, 0], [0, 0, 1], [0, 1, 0]])  # radii (left, front, up)
        Rh = self.skel.rest["hips"] @ np.array([[1, 0, 0], [0, 0, 1], [0, 1, 0]])
        Rs = self.skel.rest["spine"] @ np.array([[1, 0, 0], [0, 0, 1], [0, 1, 0]])
        # (bone, along, front offset of the section centre from the bone, half width, half depth)
        # reference: 1.75 m gaunt male. The spine bones run ~4 cm behind the trunk centre.
        sec = [
            ("hips", -0.100, 0.008, 0.132 + 0.014 * fem, 0.086),
            ("hips", -0.052, 0.006, 0.148 + 0.018 * fem, 0.098),
            ("hips", 0.000, 0.014, 0.143 + 0.014 * fem, 0.094),
            ("spine", 0.040, 0.034 - 0.006 * g, 0.121 - 0.010 * fem, 0.080 - 0.010 * g),
            ("spine", 0.120, 0.037, 0.129 - 0.010 * fem, 0.088 - 0.004 * g),
            ("chest", 0.050, 0.040, 0.141 - 0.010 * fem, 0.097),
            ("chest", 0.110, 0.040, 0.149 - 0.014 * fem, 0.100),
            ("chest", 0.160, 0.035, 0.150 - 0.016 * fem, 0.093),
            ("chest", 0.198, 0.024, 0.128 - 0.014 * fem, 0.080),
            ("chest", 0.228, 0.012, 0.072, 0.058),
        ]
        if not detail:  # cloth drapes over the belly concavity and the small of the back
            sec = [(bn, al, fo + (0.008 if i == 3 else 0.0), w * 1.015, d * (1.06 if i in (3, 4) else 1.0))
                   for i, (bn, al, fo, w, d) in enumerate(sec)]
        pts = []
        for bn, al, fo, w, d in sec:
            wm = wmul * (1.0 + 0.10 * belly if bn == "spine" else 1.0)
            dm = dmul * (1.0 + 0.22 * belly if bn == "spine" else 1.0)
            pts.append((self.T(bn, 0.0, al, fo + (0.012 * belly if bn == "spine" else 0.0)), w * wm * s, d * dm * s))
        k = 0.03 * s if detail else 0.05 * s
        for (c0, w0, d0), (c1, w1, d1) in zip(pts[:-1], pts[1:]):
            sq = 0.5 * (d0 / w0 + d1 / w1)
            prog.cone(c0, c1, w0, w1, k=k, label=L_SKIN, squash=sq, up_hint=self.skel.rest["spine"][:, 2])
        for side, sx in (("L", 1.0), ("R", -1.0)):
            # trapezius: from high on the side of the neck down to the acromion (sloped shoulders)
            a = self.T("neck", sx * 0.026, -0.006, -0.020)
            bpt = self.skel.j[f"shoulder.{side}"] + self.skel.rest["chest"] @ np.array([-sx * 0.012, 0.028, -0.006]) * s
            prog.cone(a, bpt, 0.034 * s * (0.8 + 0.25 * t), 0.022 * s * t, k=0.026 * s, label=L_SKIN, squash=0.7,
                      up_hint=self.skel.rest["chest"][:, 2])
            # pectoral plate
            pc = self.T("chest", sx * 0.066, 0.140, 0.112 + 0.006 * b)
            prog.ellipsoid(pc, np.array([0.068, 0.018 + 0.016 * b + 0.006 * fem, 0.056]) * s * (0.9 + 0.15 * t),
                           R=Rc, k=0.03 * s, label=L_SKIN)
            # scapula
            sc = self.T("chest", sx * 0.074, 0.148, -0.048)
            prog.ellipsoid(sc, np.array([0.060, 0.016 + 0.006 * t, 0.070]) * s, R=Rc, k=0.025 * s, label=L_SKIN)
            # latissimus flare under the armpit (V-taper)
            lt = self.T("chest", sx * 0.118, 0.090, -0.010)
            prog.ellipsoid(lt, np.array([0.030 + 0.012 * t, 0.050, 0.075]) * s, R=Rc, k=0.03 * s, label=L_SKIN)
            # buttock
            bu = self.T("hips", sx * 0.060, -0.062, -0.052)
            prog.ellipsoid(bu, np.array([0.070 + 0.010 * fem, 0.056 + 0.012 * b + 0.010 * fem, 0.080]) * s * (0.85 + 0.2 * t),
                           R=Rh, k=0.03 * s, label=L_SKIN)
            if fem > 0:
                br = self.T("chest", sx * 0.056, 0.100, 0.122)
                prog.ellipsoid(br, np.array([0.048, 0.034, 0.044]) * s * (0.85 + 0.3 * b), R=Rc,
                               k=(0.025 if detail else 0.04) * s, label=L_SKIN)
        if belly > 0.01:
            bc = self.T("spine", 0.0, 0.03, 0.075)
            prog.ellipsoid(bc, np.array([0.11, 0.07 * belly, 0.10]) * s, R=Rs, k=0.05 * s, label=L_SKIN)
        if not detail:
            return
        # --- bony landmarks / detail (gauntness) ---------------------------------------------
        for side, sx in (("L", 1.0), ("R", -1.0)):
            # clavicle (sternum -> acromion, just under the skin)
            a = self.T("chest", sx * 0.016, 0.224, 0.062)
            bpt = self.skel.j[f"shoulder.{side}"] + self.skel.rest["chest"] @ np.array([-sx * 0.010, 0.020, 0.030]) * s
            prog.capsule(a, bpt, (0.0065 + 0.004 * g) * s, k=0.010 * s, label=L_SKIN)
            # iliac crest (front hip bone)
            ic = self.T("hips", sx * 0.110, 0.012, 0.062)
            prog.sphere(ic, 0.020 * s, k=0.02 * s, label=L_SKIN)
            # spinal erectors (just proud of the back)
            a = self.T("hips", sx * 0.026, -0.010, -0.050)
            bpt = self.T("chest", sx * 0.026, 0.080, -0.040)
            prog.cone(a, bpt, 0.020 * s * t, 0.016 * s * t, k=0.02 * s, label=L_SKIN)
        # sternal notch, spine groove
        prog.sphere(self.T("chest", 0.0, 0.226, 0.068), 0.012 * s, k=0.01 * s, label=None, mode="sub")
        a = self.T("hips", 0.0, -0.010, -0.075)
        bpt = self.T("chest", 0.0, 0.080, -0.062)
        prog.capsule(a, bpt, 0.005 * s, k=0.010 * s, label=None, mode="sub")
        # ribs on the flanks and below the pecs (displacement ridges) for gaunt bodies
        if g > 0.05:
            R = self.skel.rest["chest"]
            org = self.skel.head["chest"] + R @ np.array([0.0, 0.0, 0.040]) * s
            amp = 0.0040 * g * s

            def ribs(P, R=R, org=org, amp=amp):
                q = (P - org) @ R           # (left, up, front)
                x, y, z = q[:, 0], q[:, 1], q[:, 2]
                ang = np.arctan2(np.abs(x), z)  # 0 at the sternum, pi/2 at the side
                slant = y + 0.050 * s * np.cos(ang)
                phase = slant / (0.025 * s)
                ridge = np.maximum(np.cos(phase * 2 * math.pi), 0.0) ** 3
                win = smoothstep(-0.03 * s, 0.01 * s, y) * (1 - smoothstep(0.10 * s, 0.15 * s, y))
                win *= smoothstep(0.30, 0.75, ang) * (1 - smoothstep(1.9, 2.4, ang))
                return -amp * ridge * win
            prog.displace(ribs, org - 0.22 * s, org + 0.22 * s)
            # vertebrae bumps along the back
            for i in range(10):
                tt = i / 9.0
                if tt < 0.35:
                    c = self.T("spine", 0.0, 0.02 + tt / 0.35 * 0.12, -0.052)
                else:
                    c = self.T("chest", 0.0, -0.01 + (tt - 0.35) / 0.65 * 0.24, -0.050 + 0.012 * (tt - 0.35))
                prog.sphere(c, 0.0075 * s * (0.6 + 0.6 * g), k=0.008 * s, label=L_SKIN)

    def _neck(self, prog: S.Program, detail: bool):
        s, g, t = self.s, self.gaunt, self.t
        a = self.T("neck", 0.0, -0.005, 0.030)
        bpt = self.T("neck", 0.0, self.skel.length("neck") / s + 0.020, 0.022)
        prog.cone(a, bpt, 0.054 * s * (0.88 + 0.16 * t), 0.046 * s * (0.9 + 0.12 * t), k=0.025 * s, label=L_SKIN,
                  squash=0.88, up_hint=self.skel.rest["neck"][:, 2])
        if not detail:
            return
        for side, sx in (("L", 1.0), ("R", -1.0)):
            mast = self.HP(sx * 0.050, -0.030, -0.030)
            notch = self.T("chest", sx * 0.014, 0.225, 0.060)
            prog.capsule(mast, notch, (0.009 + 0.004 * g) * s, k=0.012 * s, label=L_SKIN)
        if self.fem < 0.5:
            prog.ellipsoid(self.T("neck", 0.0, 0.045, 0.062), np.array([0.010, 0.012, 0.016]) * s, k=0.01 * s, label=L_SKIN)

    def _head(self, prog: S.Program):
        s, g, HP = self.s, self.gaunt, self.HP
        R = self.hR
        Rl = R @ np.array([[1, 0, 0], [0, 0, 1], [0, 1, 0]])  # radii order (left, front, up)
        hs = float(self.p.get("head_scale", 1.0))
        # cranium + occiput + forehead
        prog.ellipsoid(HP(0, 0.035, -0.012), np.array([0.074, 0.096, 0.088]) * s * hs, R=Rl, k=0.0, label=L_SKIN)
        prog.ellipsoid(HP(0, 0.008, -0.058), np.array([0.062, 0.050, 0.062]) * s * hs, R=Rl, k=0.02 * s, label=L_SKIN)
        prog.ellipsoid(HP(0, 0.045, 0.040), np.array([0.064, 0.052, 0.052]) * s * hs, R=Rl, k=0.02 * s, label=L_SKIN)
        # face mass (maxilla) and cheekbones
        prog.ellipsoid(HP(0, -0.030, 0.050), np.array([0.056, 0.052, 0.050]) * s, R=Rl, k=0.025 * s, label=L_SKIN)
        for sx in (1.0, -1.0):
            prog.ellipsoid(HP(sx * 0.047, -0.006, 0.058), np.array([0.022, 0.024, 0.013]) * s, R=Rl, k=0.012 * s, label=L_SKIN)
            prog.capsule(HP(sx * 0.054, -0.006, 0.045), HP(sx * 0.068, -0.004, 0.004), 0.0085 * s, k=0.01 * s, label=L_SKIN)
            # brow ridge
            prog.capsule(HP(sx * 0.012, 0.026, 0.090), HP(sx * 0.046, 0.024, 0.078), (0.010 + 0.002 * g) * s, k=0.012 * s, label=L_SKIN)
        # nose
        prog.capsule(HP(0, 0.010, 0.093), HP(0, -0.024, 0.110), 0.0072 * s, k=0.008 * s, label=L_SKIN)
        prog.sphere(HP(0, -0.030, 0.106), 0.0105 * s, k=0.007 * s, label=L_SKIN)
        for sx in (1.0, -1.0):
            prog.sphere(HP(sx * 0.0125, -0.036, 0.096), 0.0074 * s, k=0.006 * s, label=L_SKIN)
        # upper lip / philtrum
        prog.ellipsoid(HP(0, -0.050, 0.083), np.array([0.026, 0.017, 0.016]) * s, R=Rl, k=0.012 * s, label=L_SKIN)
        prog.capsule(HP(-0.019, -0.0585, 0.0905), HP(0.019, -0.0585, 0.0905), 0.0052 * s, k=0.005 * s, label=L_SKIN)
        # mandible in jaw space
        jR = self.skel.rest["jaw"]
        j0 = self.skel.head["jaw"]
        jt = self.skel.tail["jaw"]
        jl = float(np.linalg.norm(jt - j0))
        left = R[:, 0]
        jy = _n(jt - j0)                      # forward-down along the jaw
        jz = _n(np.cross(left, jy))           # roughly up/forward (perpendicular)
        if jz @ R[:, 1] < 0:
            jz = -jz
        def JP(x, along, up):
            return j0 + left * (x * s) + jy * along + jz * (up * s)
        chin = JP(0, jl * 0.98, 0.006)
        prog.ellipsoid(chin, np.array([0.022, 0.017, 0.016]) * s, R=np.stack([left, jz, jy], 1), k=0.012 * s, label=L_SKIN)
        for sx in (1.0, -1.0):
            ang = JP(sx * 0.050, jl * 0.30, -0.026)
            front = JP(sx * 0.020, jl * 0.92, 0.000)
            prog.capsule(front, ang, 0.0105 * s, k=0.015 * s, label=L_SKIN)
            tmj = HP(sx * 0.055, -0.005, -0.004)
            prog.capsule(ang, tmj, 0.011 * s, k=0.015 * s, label=L_SKIN)
        # lower face mass + lower lip
        prog.ellipsoid(JP(0, jl * 0.62, 0.016), np.array([0.040, 0.030, 0.036]) * s, R=np.stack([left, jz, jy], 1),
                       k=0.02 * s, label=L_SKIN)
        prog.capsule(JP(-0.017, jl * 0.80, 0.030), JP(0.017, jl * 0.80, 0.030), 0.0058 * s, k=0.005 * s, label=L_SKIN)
        # ears
        for sx in (1.0, -1.0):
            if self.p.get("missing_ear") == ("L" if sx > 0 else "R"):
                continue
            ec = HP(sx * 0.073, 0.004, -0.008)
            eR = R @ rot_axis((0, 1, 0), 0.0) @ np.array([[1, 0, 0], [0, 0, 1], [0, 1, 0]])
            eR = rot_axis(R[:, 0], math.radians(-15)) @ eR
            prog.ellipsoid(ec + R[:, 0] * sx * 0.004 * s, np.array([0.0065, 0.019, 0.030]) * s, R=eR, k=0.004 * s, label=L_SKIN)
            prog.sphere(ec + R[:, 0] * sx * 0.012 * s + R[:, 2] * 0.003 * s, 0.0085 * s, k=0.003 * s, label=None, mode="sub")
        # --- carving: eye sockets, temples, hollow cheeks, mouth -----------------------------
        for sx in (1.0, -1.0):
            prog.sphere(HP(sx * 0.032, 0.012, 0.084), 0.0175 * s, k=0.006 * s, label=None, mode="sub")
            if g > 0.05:
                prog.ellipsoid(HP(sx * 0.071, 0.035, 0.032), np.array([0.010, 0.02, 0.022]) * s * (0.5 + 0.6 * g), R=Rl,
                               k=0.012 * s, label=None, mode="sub")
                prog.ellipsoid(HP(sx * 0.052, -0.045, 0.052), np.array([0.016, 0.018, 0.022]) * s * (0.6 + 0.5 * g), R=Rl,
                               k=0.014 * s, label=None, mode="sub")
        # eyelid shells around the eyeballs, with the palpebral slit cut out
        open_ = float(self.p.get("eye_open", 0.6))
        for sx in (1.0, -1.0):
            ecen = HP(sx * 0.032, 0.012, 0.073)
            prog.sphere(ecen, 0.0150 * s, k=0.004 * s, label=L_SKIN)
            slit = HP(sx * 0.032, 0.0115, 0.086)
            sR = rot_axis(R[:, 2], sx * math.radians(6)) @ Rl
            prog.ellipsoid(slit, np.array([0.0135, 0.016, 0.0028 + 0.0055 * open_]) * s, R=sR, k=0.0015 * s, label=None, mode="sub")
            prog.sphere(ecen, 0.0118 * s, k=0.0, label=None, mode="sub")
        # mouth: slit between the lips + dark oral cavity
        mo = float(self.p.get("mouth_open", 0.3))
        up_lip = HP(0, -0.0585, 0.090)
        lo_lip = JP(0, jl * 0.80, 0.030)
        mc = 0.5 * (up_lip + lo_lip)
        gap = abs(float((up_lip - lo_lip) @ R[:, 1])) / s       # lip separation (reference metres)
        half = max(0.0035 + 0.006 * mo, 0.5 * gap - 0.002)
        prog.ellipsoid(mc, np.array([0.019 + 0.25 * half, 0.022, half]) * s, R=Rl, k=0.003 * s, label=L_GORE, mode="sub")
        cav = mc + R[:, 2] * (-0.028 * s)
        prog.ellipsoid(cav, np.array([0.022, 0.030, max(0.013 + 0.012 * mo, half + 0.008)]) * s, R=Rl, k=0.006 * s,
                       label=L_GORE, mode="sub")

    def _arm(self, prog: S.Program, side: str, sx: float, detail: bool):
        s, t, g = self.s, self.t, self.gaunt
        ua, fa = self.arm[side]["ua"], self.arm[side]["fa"]
        k = 0.02 * s if detail else 0.03 * s
        # deltoid cap over the shoulder joint
        dc = ua.at(0.10, out=0.008 * s, fwd=0.002 * s)
        prog.ellipsoid(dc, np.array([0.038, 0.043, 0.072]) * s * (0.85 + 0.2 * t), R=ua.R(), k=0.025 * s, label=L_SKIN)
        prog.cone(ua.at(0.0), ua.at(1.0), 0.040 * s * (0.85 + 0.18 * t), 0.032 * s * (0.9 + 0.1 * t), k=k, label=L_SKIN,
                  squash=0.9, up_hint=ua.fwd)
        if detail:
            prog.ellipsoid(ua.at(0.48, fwd=0.012 * s), np.array([0.026, 0.026, 0.085]) * s * (0.75 + 0.3 * t), R=ua.R(),
                           k=0.018 * s, label=L_SKIN)
            prog.ellipsoid(ua.at(0.40, fwd=-0.014 * s), np.array([0.029, 0.026, 0.095]) * s * (0.75 + 0.3 * t), R=ua.R(),
                           k=0.018 * s, label=L_SKIN)
            # elbow bones
            prog.sphere(fa.at(0.0, fwd=-0.020 * s), 0.0145 * s, k=0.012 * s, label=L_SKIN)
            prog.sphere(fa.at(0.0, out=-0.022 * s, fwd=-0.004 * s), 0.0105 * s, k=0.01 * s, label=L_SKIN)
            prog.sphere(fa.at(0.0, out=0.020 * s, fwd=-0.004 * s), 0.010 * s, k=0.01 * s, label=L_SKIN)
            # armpit folds (anterior/posterior) linking chest wall and arm
            pf = self.T("chest", sx * 0.105, 0.140, 0.060)
            prog.cone(pf, ua.at(0.25, fwd=0.012 * s), 0.020 * s, 0.018 * s, k=0.02 * s, label=L_SKIN)
            bf = self.T("chest", sx * 0.105, 0.120, -0.055)
            prog.cone(bf, ua.at(0.25, fwd=-0.016 * s), 0.024 * s, 0.018 * s, k=0.02 * s, label=L_SKIN)
        # forearm
        prog.cone(fa.at(0.0), fa.at(1.0), 0.035 * s * (0.85 + 0.15 * t), 0.0225 * s, k=k, label=L_SKIN,
                  squash=0.78, up_hint=fa.fwd)
        if detail:
            prog.ellipsoid(fa.at(0.28, out=0.010 * s, fwd=0.010 * s), np.array([0.024, 0.022, 0.075]) * s * (0.8 + 0.25 * t),
                           R=fa.R(), k=0.016 * s, label=L_SKIN)
            prog.ellipsoid(fa.at(0.30, out=-0.012 * s, fwd=0.002 * s), np.array([0.022, 0.022, 0.08]) * s * (0.8 + 0.25 * t),
                           R=fa.R(), k=0.016 * s, label=L_SKIN)
            prog.sphere(fa.at(0.97, out=-0.015 * s, fwd=-0.006 * s), 0.0075 * s, k=0.006 * s, label=L_SKIN)

    def _hand(self, prog: S.Program, side: str, sx: float):
        s = self.s
        hf = self.arm[side]["hand"]
        wrist = self.skel.j[f"wrist.{side}"]
        back = _n(self.skel.j[f"palm_back.{side}"] - wrist)
        ax = hf.axis
        back = _n(back - ax * float(back @ ax))
        lat = np.cross(ax, back)          # across the palm
        # make `lat` point from pinky to index side: index is towards the body front
        if lat @ np.array([0.0, -1.0, 0.0]) < 0:
            lat = -lat
        claw = float(self.p.get("claw", 0.5))
        L = hf.len / (0.100 * self.H)     # hand length scale (relative to the reference hand)
        sc = s * L
        R = np.stack([lat, back, ax], 1)
        # palm (rounded box) + heel of the hand
        pc = wrist + ax * 0.048 * sc + back * 0.002 * sc
        prog.box(pc, np.array([0.039, 0.0115, 0.040]) * sc, R=R, rounding=0.0095 * sc, k=0.010 * s, label=L_SKIN)
        prog.ellipsoid(wrist + ax * 0.018 * sc - back * 0.002 * sc, np.array([0.030, 0.014, 0.022]) * sc, R=R, k=0.012 * s, label=L_SKIN)
        # thenar (thumb muscle)
        prog.ellipsoid(wrist + ax * 0.030 * sc + lat * 0.022 * sc - back * 0.010 * sc, np.array([0.016, 0.012, 0.026]) * sc,
                       R=R, k=0.01 * s, label=L_SKIN)
        # fingers: (lateral offset, length, base radius)
        fingers = [(0.027, 0.074, 0.0098), (0.009, 0.082, 0.0101), (-0.009, 0.077, 0.0097), (-0.026, 0.062, 0.0086)]
        r = np.random.default_rng(int(self.p.get("seed", 1)) + (11 if side == "L" else 23))
        for fi, (lo, ln, rad) in enumerate(fingers):
            base = wrist + ax * (0.086 - 0.006 * abs(fi - 1.2)) * sc + lat * lo * sc + back * 0.001 * sc
            d = _n(ax + lat * (lo * 1.6))
            segs = (0.46, 0.30, 0.24)
            curls = (0.30 + 0.35 * claw, 0.45 + 0.45 * claw, 0.30 + 0.35 * claw)
            jitter = r.uniform(-0.12, 0.12)
            p0 = base
            rr = rad * sc
            # knuckle bump on the back
            prog.sphere(base + back * 0.004 * sc, rr * 1.05, k=0.004 * s, label=L_SKIN)
            curl_axis = _n(np.cross(d, back))  # rotating d about this bends towards the palm
            ang = 0.0
            for si, (sl, cu) in enumerate(zip(segs, curls)):
                ang += cu + (jitter if si == 0 else 0.0)
                dd = rot_axis(curl_axis, -ang) @ d
                if dd @ back > (d @ back) + 1e-6:  # bend direction sanity: must curl to the palm
                    dd = rot_axis(curl_axis, ang) @ d
                p1 = p0 + dd * ln * sl * sc
                r1 = rr * (0.92 - 0.12 * si)
                prog.cone(p0, p1, rr * (1.0 - 0.1 * si), r1, k=0.0025 * s, label=L_SKIN)
                p0 = p1
        # thumb: from the base of the palm, across towards the index side and palm
        tb = wrist + ax * 0.022 * sc + lat * 0.026 * sc - back * 0.008 * sc
        tdir = _n(ax * 0.75 + lat * 0.55 - back * 0.45)
        p0 = tb
        for si, (ln, rad) in enumerate(((0.042, 0.0115), (0.032, 0.0098), (0.028, 0.0088))):
            dd = rot_axis(_n(np.cross(tdir, back)), -(0.15 + 0.25 * claw) * si) @ tdir
            p1 = p0 + dd * ln * sc
            prog.cone(p0, p1, rad * sc, rad * sc * 0.92, k=0.004 * s, label=L_SKIN)
            p0 = p1

    def _leg(self, prog: S.Program, side: str, sx: float, detail: bool):
        s, t, g = self.s, self.t, self.gaunt
        th, sh = self.leg[side]["th"], self.leg[side]["sh"]
        k = 0.025 * s if detail else 0.04 * s
        prog.cone(th.at(-0.02), th.at(1.0), 0.074 * s * (0.85 + 0.2 * t), 0.047 * s, k=k, label=L_SKIN,
                  squash=0.95, up_hint=th.fwd)
        prog.ellipsoid(th.at(0.42, fwd=0.016 * s), np.array([0.052, 0.046, 0.17]) * s * (0.8 + 0.25 * t), R=th.R(),
                       k=0.03 * s, label=L_SKIN)
        prog.ellipsoid(th.at(0.45, fwd=-0.020 * s), np.array([0.050, 0.040, 0.16]) * s * (0.8 + 0.25 * t), R=th.R(),
                       k=0.03 * s, label=L_SKIN)
        prog.ellipsoid(th.at(0.22, out=-0.030 * s), np.array([0.040, 0.046, 0.13]) * s * (0.8 + 0.25 * t), R=th.R(),
                       k=0.03 * s, label=L_SKIN)
        if detail:
            prog.ellipsoid(th.at(0.86, out=-0.024 * s, fwd=0.010 * s), np.array([0.026, 0.026, 0.048]) * s * (0.8 + 0.25 * t),
                           R=th.R(), k=0.015 * s, label=L_SKIN)
            prog.ellipsoid(sh.at(0.0, fwd=0.040 * s), np.array([0.021, 0.011, 0.026]) * s, R=sh.R(), k=0.012 * s, label=L_SKIN)
            for o in (-0.030, 0.030):
                prog.sphere(sh.at(-0.02, out=o * s, fwd=0.002 * s), 0.028 * s, k=0.018 * s, label=L_SKIN)
        prog.cone(sh.at(0.0), sh.at(1.0), 0.041 * s * (0.9 + 0.1 * t), 0.025 * s, k=k, label=L_SKIN, squash=0.92, up_hint=sh.fwd)
        prog.ellipsoid(sh.at(0.27, fwd=-0.028 * s, out=0.004 * s), np.array([0.042, 0.036, 0.11]) * s * (0.75 + 0.3 * t),
                       R=sh.R(), k=0.025 * s, label=L_SKIN)
        if detail:
            prog.capsule(sh.at(0.08, fwd=0.028 * s), sh.at(0.85, fwd=0.018 * s), 0.010 * s, k=0.012 * s, label=L_SKIN)
            prog.capsule(sh.at(0.65, fwd=-0.024 * s), sh.at(1.02, fwd=-0.028 * s), 0.010 * s, k=0.012 * s, label=L_SKIN)
            for o in (-0.025, 0.026):
                prog.sphere(sh.at(1.0, out=o * s, fwd=-0.002 * s), 0.0100 * s, k=0.008 * s, label=L_SKIN)

    def foot_frame(self, side: str, sx: float):
        j = self.skel.j
        fwd = _n((j[f"toe_tip.{side}"] - j[f"heel.{side}"]) * np.array([1, 1, 0]))
        up = np.array([0.0, 0.0, 1.0])
        out = np.cross(up, fwd)
        if out[0] * sx < 0:
            out = -out
        return fwd, up, out

    def _foot(self, prog: S.Program, side: str, sx: float):
        s = self.s
        j = self.skel.j
        ank, ball = j[f"ankle.{side}"], j[f"ball.{side}"]
        fwd, up, out = self.foot_frame(side, sx)
        R = np.stack([out, up, fwd], 1)
        g0 = np.array([ank[0], ank[1], 0.0])          # ankle projected to the ground
        bg = np.array([ball[0], ball[1], 0.0])
        def F(f, u, o=0.0, base=g0):
            return base + fwd * (f * s) + up * (u * s) + out * (o * s)
        # heel pad, sole body, instep, forefoot
        prog.ellipsoid(F(-0.028, 0.032), np.array([0.026, 0.032, 0.029]) * s, R=R, k=0.01 * s, label=L_SKIN)
        prog.cone(F(-0.020, 0.030), F(0.000, 0.020, -0.004, bg), 0.030 * s, 0.024 * s, k=0.02 * s, label=L_SKIN,
                  squash=0.70, up_hint=up)
        prog.cone(F(0.006, 0.068), F(-0.030, 0.030, -0.004, bg), 0.026 * s, 0.020 * s, k=0.022 * s, label=L_SKIN)
        prog.ellipsoid(F(0.002, 0.016, -0.004, bg), np.array([0.040, 0.016, 0.020]) * s, R=R, k=0.016 * s, label=L_SKIN)
        # toes: (out offset, length, radius); big toe on the inside (-out)
        toes = [(-0.024, 0.036, 0.0115), (-0.005, 0.033, 0.0080), (0.008, 0.030, 0.0074), (0.019, 0.026, 0.0068),
                (0.029, 0.021, 0.0062)]
        for i, (o, ln, rad) in enumerate(toes):
            b0 = F(0.004 - 0.004 * i, 0.011, o, bg)
            prog.cone(b0, b0 + fwd * ln * s - up * 0.003 * s + out * (o * 0.15 * s), rad * s, rad * s * 0.85,
                      k=0.003 * s, label=L_SKIN)
        # arch carve on the inner sole
        prog.ellipsoid(F(0.0, 0.0, -0.022, 0.5 * (g0 + bg)), np.array([0.014, 0.010, 0.040]) * s, R=R,
                       k=0.008 * s, label=None, mode="sub")

    # ------------------------------------------------------------------------------------------
    # Segment regions (signed: < 0 inside the segment's own region)
    def build_regions(self):
        j = self.skel.j
        s = self.s
        self.cuts = {}
        # neck: plane at mid-neck, normal along the neck, limited to a tube around neck/head axis
        n0, h0 = self.skel.head["neck"], self.skel.head["head"]
        nax = _n(h0 - n0)
        self.cuts["neck"] = (n0 + (h0 - n0) * float(self.p.get("neck_cut", 0.56)), nax)
        for side, sx in (("L", 1.0), ("R", -1.0)):
            ua = self.arm[side]["ua"]
            lateral = np.array([sx, 0.0, 0.0])
            lateral = _n(lateral - self.skel.rest["chest"][:, 1] * float(lateral @ self.skel.rest["chest"][:, 1]))
            n = _n(lateral * math.cos(math.radians(18)) + ua.axis * math.sin(math.radians(18)) * 0.0
                   - self.skel.rest["chest"][:, 1] * math.sin(math.radians(18)))
            c = j[f"shoulder.{side}"] - lateral * 0.026 * s
            self.cuts[f"shoulder.{side}"] = (c, n)
            self.cuts[f"elbow.{side}"] = (j[f"elbow.{side}"] - ua.axis * 0.020 * s, ua.axis)
            th = self.leg[side]["th"]
            al = math.radians(55.0)
            n = _n(np.array([sx * math.sin(al), 0.0, -math.cos(al)]))
            self.cuts[f"hip.{side}"] = (j[f"hip.{side}"].copy(), n)
            self.cuts[f"knee.{side}"] = (j[f"knee.{side}"] - th.axis * 0.026 * s, th.axis)
        self.arm_poly = {side: [j[f"shoulder.{side}"], j[f"elbow.{side}"], j[f"wrist.{side}"], j[f"hand_tip.{side}"]]
                         for side in ("L", "R")}
        self.leg_poly = {side: [j[f"hip.{side}"], j[f"knee.{side}"], j[f"ankle.{side}"], j[f"toe_tip.{side}"]]
                         for side in ("L", "R")}

    def _plane(self, P, cut):
        c, n = self.cuts[cut]
        return (P - c) @ n

    def region_raw(self, P):
        """Signed 'inside' measures (positive inside) for the limb/head test volumes."""
        s = self.s
        out = {}
        P2 = (P * P).sum(-1)
        # head: beyond the mid-neck plane; close to the plane also within a tube around the neck
        neck_axis_pts = [self.skel.head["neck"], self.skel.head["head"], self.skel.tail["head"] + _n(self.skel.tail["head"] - self.skel.head["head"]) * 0.1]
        d_ax = polyline_dist(P, neck_axis_pts, P2)
        hp = self._plane(P, "neck")
        out["head"] = np.minimum(hp, np.maximum(0.072 * s - d_ax, hp - 0.045 * s))
        for side, sx in (("L", 1.0), ("R", -1.0)):
            ap = self.arm_poly[side]
            tube = np.maximum(0.095 * s - polyline_dist(P, ap[:3], P2), 0.135 * s - polyline_dist(P, ap[2:], P2))
            arm = np.minimum(self._plane(P, f"shoulder.{side}"), tube)
            out[f"arm.{side}"] = arm
            out[f"forearm.{side}"] = np.minimum(arm, self._plane(P, f"elbow.{side}"))
            ltube = 0.15 * s - polyline_dist(P, self.leg_poly[side], P2)
            mid = P[:, 0] * sx
            leg = np.minimum(np.minimum(self._plane(P, f"hip.{side}"), ltube), mid)
            out[f"leg.{side}"] = leg
            out[f"shin.{side}"] = np.minimum(leg, self._plane(P, f"knee.{side}"))
        return out

    def region(self, P, seg: str, raw=None):
        """Signed distance-like value: < 0 inside segment `seg`'s own region."""
        r = self.region_raw(P) if raw is None else raw
        excl_arms = np.maximum(r["arm.L"], r["arm.R"])
        if seg == "body_head":
            return -r["head"]
        for side in ("L", "R"):
            if seg == f"body_upper_arm.{side}":
                return -np.minimum(r[f"arm.{side}"], -r[f"forearm.{side}"])
            if seg == f"body_forearm.{side}":
                return -r[f"forearm.{side}"]
            if seg == f"body_thigh.{side}":
                return -np.minimum(np.minimum(r[f"leg.{side}"], -r[f"shin.{side}"]), -excl_arms)
            if seg == f"body_shin.{side}":
                return -np.minimum(r[f"shin.{side}"], -excl_arms)
        if seg == "body_torso":
            m = np.maximum.reduce([r["head"], r["arm.L"], r["arm.R"],
                                   np.minimum(r["leg.L"], -excl_arms), np.minimum(r["leg.R"], -excl_arms)])
            return m
        raise KeyError(seg)

    # ------------------------------------------------------------------------------------------
    # Evaluation
    def eval_points(self, P, seg: str | None = None, chunk: int = 200000):
        if len(P) > chunk:
            ds, ls = [], []
            for i in range(0, len(P), chunk):
                d, lab = self.eval_points(P[i:i + chunk], seg, chunk)
                ds.append(d)
                ls.append(lab)
            return np.concatenate(ds), np.concatenate(ls)
        d, lab = self.skin.eval(P)
        d, lab = self._add_layers(P, d, lab)
        return self._segmentize(P, d, lab, seg)

    def eval_grid(self, origin, h, shape, seg: str | None = None, narrow: bool = True):
        """Distance grid. With narrow=True the field is first evaluated on a 2x coarser grid and
        only voxels near the surface are evaluated exactly (the rest are interpolated: their sign
        is all surface nets needs). Labels are returned only for narrow=False."""
        if narrow and min(shape) > 8:
            return self._eval_grid_narrow(origin, h, shape, seg), None
        d, lab = self.skin.eval_grid(origin, h, shape)
        axes = [np.asarray(origin)[a] + np.arange(shape[a]) * h for a in range(3)]
        gx, gy, gz = np.meshgrid(*axes, indexing="ij")
        P = np.stack([gx.ravel(), gy.ravel(), gz.ravel()], -1)
        del gx, gy, gz
        d = d.ravel()
        lab = lab.ravel()
        d, lab = self._add_layers(P, d, lab, grid=(origin, h, shape))
        d, lab = self._segmentize(P, d, lab, seg)
        return d.reshape(shape), lab.reshape(shape)

    def _eval_grid_narrow(self, origin, h, shape, seg):
        origin = np.asarray(origin, dtype=np.float64)
        cs = tuple((n - 1 + 1) // 2 + 1 for n in shape)
        dc, _ = self.eval_grid(origin, 2 * h, cs, seg, narrow=False)
        # trilinear upsample by 2 (separable averaging)
        up = dc
        for ax in range(3):
            n = up.shape[ax]
            new_shape = list(up.shape)
            new_shape[ax] = 2 * n - 1
            out = np.empty(new_shape)
            sl_even = [slice(None)] * 3
            sl_even[ax] = slice(0, None, 2)
            out[tuple(sl_even)] = up
            sl_odd = [slice(None)] * 3
            sl_odd[ax] = slice(1, None, 2)
            a = [slice(None)] * 3
            a[ax] = slice(0, -1)
            b = [slice(None)] * 3
            b[ax] = slice(1, None)
            out[tuple(sl_odd)] = 0.5 * (up[tuple(a)] + up[tuple(b)])
            up = out
        up = up[:shape[0], :shape[1], :shape[2]]
        band = 3.2 * (2 * h)
        near = np.nonzero(np.abs(up) < band)
        if len(near[0]):
            P = origin + np.stack(near, -1) * h
            dn, _ = self.eval_points(P, seg)
            up[near] = dn
        return up

    def _add_layers(self, P, d, lab, grid=None):
        # Bloom growth masses blend into whatever surface is there
        if self.growth.ops:
            if grid is not None:
                dg, lg = self.growth.eval_grid(*grid)
                dg, lg = dg.ravel(), lg.ravel()
            else:
                dg, lg = self.growth.eval(P)
            near = dg < 0.03
            if near.any():
                k = 0.006 * self.s
                dn = S.smin(d[near], dg[near], k)
                lab[near] = np.where(dg[near] < d[near] + 0.0005, lg[near], lab[near])
                d[near] = dn
        # clothing over skin
        if self.garments:
            sel = np.nonzero(np.abs(d) < 0.03)[0]
            if len(sel):
                Ps = P[sel]
                db, _ = self.base.eval(Ps)
                ds, ls = d[sel], lab[sel]
                # the cloth always encloses the detailed skin (bony bumps show through softly)
                db = np.minimum(db, S.smin(db, ds + 0.0025 * self.s, 0.006 * self.s))
                # garments never reach above the neck cut (head segment stays skin + hair)
                n_c, n_ax = self.cuts["neck"]
                hp = (Ps - n_c) @ n_ax
                d_ax = polyline_dist(Ps, [self.skel.head["neck"], self.skel.tail["head"]])
                clip = np.minimum(hp + 0.012 * self.s, 0.12 * self.s - d_ax)
                for g in self.garments:
                    dg, lg = g(Ps, db)
                    dg = np.maximum(dg, clip)
                    better = dg < ds
                    ls = np.where(better, lg, ls)
                    ds = np.minimum(ds, dg)
                d[sel], lab[sel] = ds, ls
        if self.boots.ops:
            if grid is not None:
                db_, lb_ = self.boots.eval_grid(*grid)
                db_, lb_ = db_.ravel(), lb_.ravel()
            else:
                db_, lb_ = self.boots.eval(P)
            better = db_ < d
            lab = np.where(better, lb_, lab)
            d = np.minimum(d, db_)
        return d, lab

    def _segmentize(self, P, d, lab, seg):
        if seg is None:
            return d, lab
        # Only points inside / near the body matter: far outside, d stays positive anyway.
        idx = np.nonzero(d < 0.03)[0]
        if len(idx):
            Pi = P[idx]
            r = self.region(Pi, seg)
            di = d[idx] + getattr(self, "inset", INSET) * smoothstep(0.0, INSET_RAMP, r)
            cap = r - getattr(self, "overlap", OVERLAP)
            li = np.where(cap > di, np.int16(L_GORE), lab[idx])
            d = d.copy()
            lab = lab.copy()
            d[idx] = np.maximum(di, cap)
            lab[idx] = li
        if seg == "body_head" and self.hair.ops:
            dh, lh = self.hair.eval(P)
            lab = np.where(dh < d, lh, lab)
            d = np.minimum(d, dh)
        return d, lab

    # ------------------------------------------------------------------------------------------
    # Skinning weights: continuous function of position per region (cuts are 100 % parent)
    def weights(self, P, seg: str) -> np.ndarray:
        nb = len(BONE_NAMES)
        W = np.zeros((len(P), nb))
        bi = {n: i for i, n in enumerate(BONE_NAMES)}
        s = self.s
        sk = self.skel

        def chain_param(P, a, b):
            ab = b - a
            return ((P - a) @ ab) / float(ab @ ab)

        if seg in ("body_torso",):
            self._torso_weights(P, W, bi)
        elif seg == "body_head":
            n_c, n_ax = self.cuts["neck"]
            hp = (P - n_c) @ n_ax
            sb = float((sk.head["head"] - n_c) @ n_ax)
            wh = smoothstep(0.0, sb + 0.012 * s, hp)
            W[:, bi["neck"]] = 1 - wh
            W[:, bi["head"]] = wh
            # jaw: points below the mouth line and in front of the ear
            jaw = self._jaw_mask(P)
            W[:, bi["jaw"]] = W[:, bi["head"]] * jaw
            W[:, bi["head"]] *= (1 - jaw)
        else:
            side = seg[-1]
            if "arm" in seg:
                c, n = self.cuts[f"shoulder.{side}"]
                ds = (P - c) @ n
                w_ua = smoothstep(0.0, 0.085 * s, ds)
                ec, en = self.cuts[f"elbow.{side}"]
                de = (P - ec) @ en
                w_fa = smoothstep(0.0, 0.065 * s, de)
                wr = sk.j[f"wrist.{side}"]
                fa_ax = self.arm[side]["fa"].axis
                dw = (P - wr) @ fa_ax
                w_h = smoothstep(-0.022 * s, 0.028 * s, dw)
                W[:, bi[f"shoulder.{side}"]] = 1 - w_ua
                rest = w_ua
                W[:, bi[f"upper_arm.{side}"]] = rest * (1 - w_fa)
                rest2 = rest * w_fa
                W[:, bi[f"forearm.{side}"]] = rest2 * (1 - w_h)
                W[:, bi[f"hand.{side}"]] = rest2 * w_h
            else:
                c, n = self.cuts[f"hip.{side}"]
                dh = (P - c) @ n
                th = self.leg[side]["th"]
                w_th = smoothstep(0.0, 0.11 * s, dh)
                kc, kn = self.cuts[f"knee.{side}"]
                dk = (P - kc) @ kn
                w_sh = smoothstep(0.0, 0.07 * s, dk)
                an = sk.j[f"ankle.{side}"]
                sh_ax = self.leg[side]["sh"].axis
                da = (P - an) @ sh_ax
                # foot: below/in front of the ankle; blend over the ankle joint
                fwd = _n((sk.j[f"toe_tip.{side}"] - sk.j[f"heel.{side}"]) * np.array([1, 1, 0]))
                df = (P - an) @ fwd
                w_ft = smoothstep(-0.03 * s, 0.025 * s, da) * (0.35 + 0.65 * smoothstep(-0.06 * s, 0.02 * s, df))
                w_ft = np.maximum(w_ft, smoothstep(-0.01 * s, 0.03 * s, df) * smoothstep(-0.06 * s, 0.0, da))
                ball = sk.j[f"ball.{side}"]
                db = (P - ball) @ fwd
                w_toe = smoothstep(-0.012 * s, 0.018 * s, db)
                W[:, bi["hips"]] = 1 - w_th
                W[:, bi[f"thigh.{side}"]] = w_th * (1 - w_sh)
                rest = w_th * w_sh
                W[:, bi[f"shin.{side}"]] = rest * (1 - w_ft)
                W[:, bi[f"foot.{side}"]] = rest * w_ft * (1 - w_toe)
                W[:, bi[f"toe.{side}"]] = rest * w_ft * w_toe
                del th
        return W

    def _jaw_mask(self, P):
        s = self.s
        R = self.hR
        q = (P - self.hc) @ R / s        # (left, up, front) head-local in reference metres
        x, y, z = q[:, 0], q[:, 1], q[:, 2]
        # below the mouth line (which tilts down towards the back), in front of the ear/TMJ
        mouth_y = -0.060 + 0.25 * (0.085 - z) * 0.35
        below = 1 - smoothstep(mouth_y - 0.006, mouth_y + 0.004, y)
        front = smoothstep(-0.020, 0.012, z)
        lateral = 1 - smoothstep(0.050, 0.075, np.abs(x))
        under = 1 - smoothstep(-0.130, -0.105, y)  # neck below the jaw stays with the neck/head
        neckside = smoothstep(-0.115, -0.085, y) + smoothstep(0.02, 0.05, z)
        return np.clip(below * front * lateral * under * np.clip(neckside, 0, 1), 0, 1)

    def _torso_weights(self, P, W, bi):
        sk, s = self.skel, self.s
        # spine chain by projection onto the spine polyline (hips, spine, chest, neck)
        pel, sp0, ch0, nk0 = sk.head["hips"], sk.head["spine"], sk.head["chest"], sk.head["neck"]
        up_h = _n(sp0 - pel)
        up_s = _n(ch0 - sp0)
        up_c = _n(nk0 - ch0)
        a = (P - sp0) @ up_s                     # height relative to spine0 along spine dir
        b = (P - ch0) @ up_c                     # relative to chest0
        w_spine = smoothstep(-0.05 * s, 0.05 * s, a)
        w_chest = smoothstep(-0.05 * s, 0.06 * s, b)
        n_c, n_ax = self.cuts["neck"]
        hn = (P - n_c) @ n_ax
        nb_ = float((nk0 - n_c) @ n_ax)          # neck base (negative)
        w_neck = smoothstep(nb_ + 0.005 * s, -0.004 * s, hn)
        wh = 1 - w_spine
        wsp = w_spine * (1 - w_chest)
        wc = w_spine * w_chest
        W[:, bi["hips"]] = wh
        W[:, bi["spine"]] = wsp
        W[:, bi["chest"]] = wc * (1 - w_neck)
        W[:, bi["neck"]] = wc * w_neck
        # shoulders (clavicle bones): lateral upper torso, 100 % at the shoulder cut
        for side, sx in (("L", 1.0), ("R", -1.0)):
            c, n = self.cuts[f"shoulder.{side}"]
            ds = (P - c) @ n                     # 0 at the cut, negative inwards
            dj = np.sqrt(((P - sk.j[f"shoulder.{side}"]) ** 2).sum(-1))
            hgt = (P - ch0) @ up_c
            w_sh = smoothstep(-0.10 * s, 0.0, ds) * (1 - smoothstep(0.09 * s, 0.16 * s, dj))
            w_sh *= smoothstep(0.06 * s, 0.13 * s, hgt)
            w_sh = np.maximum(w_sh, (ds > -0.002 * s) * smoothstep(0.0, 0.05 * s, hgt) * (dj < 0.14 * s))
            w_sh = np.clip(w_sh, 0, 1)
            take = w_sh
            for nm in ("chest", "spine", "neck"):
                W[:, bi[nm]] *= (1 - take)
            W[:, bi[f"shoulder.{side}"]] += take
        # thighs never influence the torso (hip cuts stay rigid on the hips bone)


def normalize_weights(W: np.ndarray, max_influences: int = 4, eps: float = 1e-3) -> np.ndarray:
    W = np.clip(W, 0.0, None)
    if W.shape[1] > max_influences:
        idx = np.argsort(-W, axis=1)[:, max_influences:]
        np.put_along_axis(W, idx, 0.0, axis=1)
    W[W < eps] = 0.0
    tot = W.sum(1, keepdims=True)
    tot[tot < 1e-9] = 1.0
    return W / tot
