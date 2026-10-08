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


# Finger joint prefixes and their bone names.
FINGER_BONES = (("ix", "index"), ("md", "middle"), ("rg", "ring"), ("pk", "pinky"))
# The finger names a hand spec's `curls` takes.
FINGER_NAMES = tuple(n for _, n in FINGER_BONES)


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
            (f"thumb_2.{sd}", f"thumb_1.{sd}", f"th_mcp.{sd}", f"th_ip.{sd}", f"th_up.{sd}"),
            (f"thumb_3.{sd}", f"thumb_2.{sd}", f"th_ip.{sd}", f"th_tip.{sd}", f"th_up.{sd}"),
        ]
        # Every finger bends at its own three knuckles (ADR-0045): the middle, ring and little
        # fingers once shared the middle finger's two bones, so they hinged 1-3 cm off their own
        # knuckles, could not close separately and a fist left a hollow under them.
        for k, name in FINGER_BONES:
            bones += [
                (f"{name}_1.{sd}", f"hand.{sd}", f"{k}_mcp.{sd}", f"{k}_pip.{sd}", f"palm_back.{sd}"),
                (f"{name}_2.{sd}", f"{name}_1.{sd}", f"{k}_pip.{sd}", f"{k}_dip.{sd}", f"palm_back.{sd}"),
                (f"{name}_3.{sd}", f"{name}_2.{sd}", f"{k}_dip.{sd}", f"{k}_tip.{sd}", f"palm_back.{sd}"),
            ]
    # Joint helpers (TD-174): a bone at each finger and thumb joint and at the wrist that turns
    # half as far as the bone past it (FPRig.evaluate). The skin over a joint follows it, so a
    # knuckle bent 90 deg wraps round in two 45 deg steps instead of linear blend skinning
    # averaging two positions 90 deg apart into a dent (and the back of a bent wrist into a fold).
    for sd in ("L", "R"):
        bones.append((f"wrist_k.{sd}", f"forearm.{sd}", f"wrist.{sd}", f"hand_tip.{sd}", UP))
        bones += [
            (f"thumb_k1.{sd}", f"hand.{sd}", f"th_cmc.{sd}", f"th_mcp.{sd}", f"th_up.{sd}"),
            (f"thumb_k2.{sd}", f"thumb_1.{sd}", f"th_mcp.{sd}", f"th_ip.{sd}", f"th_up.{sd}"),
            (f"thumb_k3.{sd}", f"thumb_2.{sd}", f"th_ip.{sd}", f"th_tip.{sd}", f"th_up.{sd}"),
        ]
        for k, name in FINGER_BONES:
            bones += [
                (f"{name}_k1.{sd}", f"hand.{sd}", f"{k}_mcp.{sd}", f"{k}_pip.{sd}", f"palm_back.{sd}"),
                (f"{name}_k2.{sd}", f"{name}_1.{sd}", f"{k}_pip.{sd}", f"{k}_dip.{sd}", f"palm_back.{sd}"),
                (f"{name}_k3.{sd}", f"{name}_2.{sd}", f"{k}_dip.{sd}", f"{k}_tip.{sd}", f"palm_back.{sd}"),
            ]
    return bones


def _helper_of(name: str) -> str | None:
    """The bone a joint helper halves (its sibling, so half that bone's local turn is its own), or
    None for an ordinary bone."""
    base, sd = name.rsplit(".", 1)
    if base == "wrist_k":
        return f"hand.{sd}"
    if "_k" in base:
        digit, kn = base.rsplit("_k", 1)
        return f"{digit}_{kn}.{sd}"
    return None


FP_BONES = _fp_bones()
FP_NAMES = [b[0] for b in FP_BONES]
# finger layout in the hand frame: (lateral offset (+ towards thumb), MCP along, segment lengths, radius)
FINGERS = {"ix": (0.0245, 0.089, (0.041, 0.025, 0.020), 0.0096),
           "md": (0.0075, 0.093, (0.046, 0.028, 0.021), 0.0100),
           "rg": (-0.0108, 0.089, (0.043, 0.027, 0.020), 0.0094),
           "pk": (-0.0280, 0.081, (0.034, 0.021, 0.018), 0.0083)}

# Mesh-only hand shape (the joints above stay the skeleton's): radii (m) at the MCP, PIP, DIP and
# tip of each finger (middle longest and thickest, little finger slimmest) and the nail half-length.
FINGER_SHAPE = {"ix": ((0.0090, 0.0079, 0.0073, 0.0064), 0.0055),
                "md": ((0.0092, 0.0081, 0.0075, 0.0066), 0.0058),
                "rg": ((0.0087, 0.0079, 0.0072, 0.0063), 0.0054),
                "pk": ((0.0077, 0.0069, 0.0063, 0.0056), 0.0046)}
THUMB_RADII = (0.0125, 0.0113, 0.0105, 0.0091)    # CMC, MCP, IP, tip
TIP_PULL = 0.0025                                  # the distal cone stops this short of the tip joint
# Palm outline in the hand frame (u towards the thumb, w along the hand; m, counter-clockwise):
# heel, index metacarpal, over the four knuckles, down the little-finger edge. Rounded by
# PALM_ROUND, so the outline is the skin's.
PALM_OUTLINE = ((0.0265, 0.004), (0.0320, 0.062), (0.0325, 0.086), (0.0075, 0.096), (-0.0105, 0.092),
                (-0.0355, 0.077), (-0.0365, 0.045), (-0.0280, 0.006))
PALM_ROUND = 0.0065


def _palm_top(u, w):
    """Height of the back of the hand over the hand axis (m): arched across the metacarpals
    (highest over the middle finger's), rising a little towards the wrist."""
    return 0.0125 - 4.5 * (u - 0.002) ** 2 + 0.0025 * (1.0 - smoothstep(0.0, 0.040, w))


def _inset_poly(V, r: float) -> np.ndarray:
    """A convex counter-clockwise polygon with every edge moved inwards by r."""
    V = np.asarray(V, dtype=np.float64)
    n = len(V)
    lines = []
    for i in range(n):
        e = _n(V[(i + 1) % n] - V[i])
        lines.append((V[i] + np.array([-e[1], e[0]]) * r, e))
    out = []
    for i in range(n):
        (p0, e0), (p1, e1) = lines[i - 1], lines[i]
        t = np.linalg.solve(np.array([[e0[0], -e1[0]], [e0[1], -e1[1]]]), p1 - p0)[0]
        out.append(p0 + e0 * t)
    return np.array(out)


def _sd_poly2(p: np.ndarray, V: np.ndarray) -> np.ndarray:
    """Exact signed distance to a 2D polygon (iq), p (N,2)."""
    d = ((p - V[0]) ** 2).sum(-1)
    sgn = np.ones(len(p))
    n = len(V)
    for i in range(n):
        vi, vj = V[i], V[i - 1]
        e = vj - vi
        w = p - vi
        b = w - e[None, :] * np.clip((w @ e) / float(e @ e), 0.0, 1.0)[:, None]
        d = np.minimum(d, (b * b).sum(-1))
        c1 = p[:, 1] >= vi[1]
        c2 = p[:, 1] < vj[1]
        c3 = e[0] * w[:, 1] > e[1] * w[:, 0]
        flip = (c1 & c2 & c3) | (~c1 & ~c2 & ~c3)
        sgn = np.where(flip, -sgn, sgn)
    return sgn * np.sqrt(d)


def _finger_frames(pts, ref):
    """Per segment (side, nail side, direction): the nail side is `ref` (the back of the hand for
    the fingers) made perpendicular to the segment."""
    out = []
    for a, b in zip(pts[:-1], pts[1:]):
        d = _n(np.asarray(b) - np.asarray(a))
        bk = _n(ref - d * float(ref @ d))
        out.append((np.cross(bk, d), bk, d))
    return out


def _thumb_frames(tp, lat, back):
    # the thumb is turned about its own axis against the fingers: its nail faces out and back
    return _finger_frames(tp, _n(lat * 0.8 + back * 0.6))


def _finger_sdf(pts, radii, fr, s, squash: float = 0.88, knobs=(1, 2), pads=(0, 1, 2)):
    """One digit: three tapering phalanges (a little deeper than wide... flattened palm to back by
    `squash`), joints slightly wider than the shafts either side and proud on the back, and a fleshy
    pad under each phalanx (the creases fall between them; the last one is the fingertip pulp)."""
    pts = [np.asarray(p, dtype=np.float64) for p in pts]
    segs = [(pts[0], pts[1]), (pts[1], pts[2]), (pts[2], pts[3] - fr[2][2] * TIP_PULL * s)]
    knob = []
    for ji in knobs:
        bk = _n(fr[ji - 1][1] + fr[ji][1])
        dd = _n(fr[ji - 1][2] + fr[ji][2])
        r = radii[ji]
        knob.append((pts[ji] + bk * r * 0.06, (r * 1.0, r * 0.93, r * 0.90), np.stack([_n(np.cross(bk, dd)), bk, dd], 1)))
    pad = []
    for si in pads:
        a, b = segs[si]
        sl, bk, dd = fr[si]
        ln = float(np.linalg.norm(b - a))
        r = 0.5 * (radii[si] + radii[si + 1])
        c = (a + b) * 0.5 + dd * ln * (0.06 if si < 2 else 0.18) - bk * r * 0.30
        pad.append((c, (r * 0.86, r * 0.70, ln * 0.40 + (r * 0.35 if si == 2 else 0.0)), np.stack([sl, bk, dd], 1)))

    def fn(P):
        d = None
        for si, (a, b) in enumerate(segs):
            ds = S.sd_round_cone_ellip(P, a, b, radii[si], radii[si + 1], squash, fr[si][1])
            d = ds if d is None else S.smin(d, ds, 0.0015 * s)
        for c, rr, Rk in knob:
            d = S.smin(d, S.sd_ellipsoid(P, c, rr, Rk), 0.0020 * s)
        for c, rr, Rk in pad:
            d = S.smin(d, S.sd_ellipsoid(P, c, rr, Rk), 0.0015 * s)
        return d
    return fn


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
        self.palm_fn = {}                  # side -> the metacarpal block's SDF (skinning uses it)

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
        self.skin.cone(fa.at(0.02), fa.at(1.0), 0.041 * s, 0.0276 * s, k=0.022 * s, squash=0.74, up_hint=dor)
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
                rr = (0.041 + (0.0276 - 0.041) * t) * s
                c = math.cos(ang * math.pi)
                sn = math.sin(ang * math.pi)
                pts.append(fa.at(t) + dor * c * rr * 0.80 + rad * sn * rr * 1.02)
            for a, b in zip(pts[:-1], pts[1:]):
                self.skin.capsule(a, b, vr * s, k=0.004 * s)

    def _hand(self, sd, sx):
        """The working hand, built in the hand frame (u towards the thumb, v the back, w along):
        a domed metacarpal block (wider than deep, its back arched across the knuckles) with the
        thenar, hypothenar and distal palm pads under it, raised MCP knuckles and extensor tendons
        on the back, four separate fingers (each its own field, so the gaps between them survive
        the union) with knobbly PIP/DIP joints, phalanx pads and rounded tips with inset nails, and
        a thumb on a thenar mass joined to the index by its web."""
        s = self.s
        j = self.sk.j
        wr, ax, back, lat = j[f"wrist.{sd}"], j[f"axis.{sd}"], j[f"back.{sd}"], j[f"lat.{sd}"]
        R = np.stack([lat, back, ax], 1)
        sk_ = self.skin

        def world(u, v, w):
            return wr + (lat * u + back * v + ax * w) * s

        def local(p):
            return ((np.asarray(p) - wr) @ R) / s

        def box_of(pts, m):
            pts = np.asarray(pts)
            return pts.min(0) - m * s, pts.max(0) + m * s

        poly = _inset_poly(PALM_OUTLINE, PALM_ROUND)

        def palm(P):
            q = ((P - wr) @ R) / s
            u, v, w = q[:, 0], q[:, 1], q[:, 2]
            d2 = _sd_poly2(np.stack([u, w], -1), poly)
            top = _palm_top(u, w) - PALM_ROUND
            bot = -(0.0100 + 0.0035 * smoothstep(0.050, 0.085, w)) + PALM_ROUND
            dv = np.maximum(v - top, bot - v)
            out = np.sqrt(np.maximum(d2, 0.0) ** 2 + np.maximum(dv, 0.0) ** 2)
            return (out + np.minimum(np.maximum(d2, dv), 0.0) - PALM_ROUND) * s

        corners = [world(u, v, w) for u, w in PALM_OUTLINE for v in (-0.02, 0.02)]
        sk_.union(palm, *box_of(corners, 0.004), k=0.011 * s)
        self.palm_fn[sd] = palm
        # heel of the hand over the carpals, blending into the wrist
        sk_.ellipsoid(world(-0.001, 0.0005, 0.014), np.array([0.0275, 0.0160, 0.020]) * s, R=R, k=0.010 * s)
        # pads on the palm side: hypothenar (little-finger edge), the distal pad under the knuckles
        sk_.ellipsoid(world(-0.0250, -0.0072, 0.043), np.array([0.0115, 0.0100, 0.032]) * s, R=R, k=0.008 * s)
        a_ = j[f"ix_mcp.{sd}"] - back * 0.0100 * s - ax * 0.011 * s
        b_ = j[f"pk_mcp.{sd}"] - back * 0.0090 * s - ax * 0.010 * s
        sk_.capsule(a_, b_, 0.0070 * s, k=0.010 * s)
        # extensor tendons fanning from the wrist to each knuckle, under the skin of the back
        for key in ("ix", "md", "rg", "pk"):
            mu, _, mw = local(j[f"{key}_mcp.{sd}"])
            a_ = world(mu * 0.5, _palm_top(np.array([mu * 0.5]), np.array([0.030]))[0] - 0.0016, 0.030)
            b_ = world(mu, _palm_top(np.array([mu]), np.array([mw]))[0] - 0.0012, mw - 0.008)
            sk_.capsule(a_, b_, 0.0019 * s, k=0.005 * s)
        # thenar eminence on the thumb's metacarpal, and the adductor mass towards the palm
        cmc, tmcp = j[f"th_cmc.{sd}"], j[f"th_mcp.{sd}"]
        t1 = _n(tmcp - cmc)
        tl = _n(lat - t1 * float(lat @ t1))
        Rt = np.stack([tl, np.cross(t1, tl) * (1 if float(np.cross(t1, tl) @ back) > 0 else -1), t1], 1)
        sk_.ellipsoid(cmc + (tmcp - cmc) * 0.42 - back * 0.0085 * s - lat * 0.0065 * s,
                      np.array([0.0150, 0.0120, 0.0270]) * s, R=Rt, k=0.009 * s)
        sk_.ellipsoid(world(0.0115, -0.0085, 0.052), np.array([0.0125, 0.0075, 0.019]) * s, R=R, k=0.009 * s)
        # knuckles (metacarpal heads), riding the arch of the back
        for key, (lo, along, segs, rad) in FINGERS.items():
            r0 = FINGER_SHAPE[key][0][0]
            mu, _, mw = local(j[f"{key}_mcp.{sd}"])
            top = float(_palm_top(np.array([mu]), np.array([mw]))[0])
            c = world(mu, top - r0 * 0.70, mw + 0.001)
            sk_.ellipsoid(c, np.array([r0 * 0.98, r0 * 0.95, r0 * 1.05]) * s, R=R, k=0.0045 * s)
        # the fingers' roots on the palm side: soft pads that meet as the webs between them (the
        # palm reaches a third of the way up the first phalanges there; the clefts on the back stay
        # open)
        for key in ("ix", "md", "rg", "pk"):
            m_, p_ = j[f"{key}_mcp.{sd}"], j[f"{key}_pip.{sd}"]
            r0 = FINGER_SHAPE[key][0][0]
            fl, fb, fd = _finger_frames([m_, p_], back)[0]
            ln = float(np.linalg.norm(p_ - m_))
            sk_.ellipsoid(m_ + (p_ - m_) * 0.18 - fb * r0 * 0.45 * s, np.array([r0 * 0.95, r0 * 0.70, ln * 0.26 / s]) * s,
                          R=np.stack([fl, fb, fd], 1), k=0.006 * s)
        # fingers: separate fields, each smooth-unioned on its own so the clefts stay open
        for key in ("ix", "md", "rg", "pk"):
            pts = [j[f"{key}_{n}.{sd}"] for n in ("mcp", "pip", "dip", "tip")]
            radii, nail_hl = FINGER_SHAPE[key]
            fr = _finger_frames(pts, back)
            fn = _finger_sdf(pts, [r * s for r in radii], fr, s)
            sk_.union(fn, *box_of(pts, 0.014), k=0.0035 * s)
            # the nail: a thin curved plate set into the back of the tip, ending at the free edge
            fd, fl, fb = fr[2][2], fr[2][0], fr[2][1]
            end = pts[3] - fd * TIP_PULL * s + fd * radii[3] * s
            rn = radii[3] + (radii[2] - radii[3]) * 0.25
            nc = end - fd * (nail_hl + 0.0017) * s + fb * (rn * 0.87 - 0.0008) * s
            sk_.ellipsoid(nc, np.array([rn * 0.76, 0.0014, nail_hl]) * s, R=np.stack([fl, fb, fd], 1),
                          k=0.0008 * s, label=L_NAIL)
        # the thumb, and the web between it and the index
        tp = [j[f"th_cmc.{sd}"], j[f"th_mcp.{sd}"], j[f"th_ip.{sd}"], j[f"th_tip.{sd}"]]
        tfr = _thumb_frames(tp, lat, back)
        fn = _finger_sdf(tp, [r * s for r in THUMB_RADII], tfr, s, squash=0.84, knobs=(1, 2), pads=(1, 2))
        sk_.union(fn, *box_of(tp, 0.016), k=0.0075 * s)
        web_a = world(0.0250, 0.0015, 0.064)
        web_b = tp[1] + (tp[2] - tp[1]) * 0.35 - tfr[1][1] * 0.002 * s
        sk_.capsule(web_a, web_b, 0.0065 * s, k=0.009 * s)
        # first dorsal interosseous: the muscle filling the web between the two metacarpals
        sk_.ellipsoid((world(0.022, -0.001, 0.046) + (cmc + tmcp) * 0.5) * 0.5, np.array([0.0105, 0.0085, 0.019]) * s,
                      R=R, k=0.009 * s)
        fd, fl, fb = tfr[2][2], tfr[2][0], tfr[2][1]
        end = tp[3] - fd * TIP_PULL * s + fd * THUMB_RADII[3] * s
        rn = THUMB_RADII[3] + (THUMB_RADII[2] - THUMB_RADII[3]) * 0.25
        nc = end - fd * (0.0064 + 0.0017) * s + fb * (rn * 0.84 - 0.0008) * s
        sk_.ellipsoid(nc, np.array([rn * 0.76, 0.0015, 0.0064]) * s, R=np.stack([fl, fb, fd], 1),
                      k=0.0008 * s, label=L_NAIL)

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
                f"thumb_2.{sd}": [(j[f"th_mcp.{sd}"], j[f"th_ip.{sd}"])],
                f"thumb_3.{sd}": [(j[f"th_ip.{sd}"], j[f"th_tip.{sd}"])],
            }
            for k, name in FINGER_BONES:
                caps[f"{name}_1.{sd}"] = [(j[f"{k}_mcp.{sd}"], j[f"{k}_pip.{sd}"])]
                caps[f"{name}_2.{sd}"] = [(j[f"{k}_pip.{sd}"], j[f"{k}_dip.{sd}"])]
                caps[f"{name}_3.{sd}"] = [(j[f"{k}_dip.{sd}"], j[f"{k}_tip.{sd}"])]
            dist = {}
            for bn, segs in caps.items():
                dist[bn] = np.min(np.stack([polyline_dist(P, [a, b]) for a, b in segs], 0), 0)
            wr, axh = j[f"wrist.{sd}"], j[f"axis.{sd}"]
            # The hand bone owns the whole metacarpal block, measured like a bone ~8 mm under its
            # skin (a line down the hand's axis would lose the back of the hand's thumb side to the
            # thumb's metacarpal, which then folds through it when the thumb closes).
            palm_d = polyline_dist(P, [wr, wr + axh * 0.085 * s]) * 0.9
            if sd in self.palm_fn:
                palm_d = np.minimum(palm_d, np.maximum(self.palm_fn[sd](P), -0.008 * s) + 0.008 * s)
            names = list(caps) + [f"hand.{sd}"]
            D = np.stack([dist[n] for n in caps] + [palm_d], 1)
            sig = 0.0045 * s
            Ew = np.exp(-(D - D.min(1, keepdims=True)) / sig)
            Ew /= Ew.sum(1, keepdims=True)
            for k, n in enumerate(names):
                Wl[:, bi[n]] += hand_w * Ew[:, k]
            self._joint_bands(P, Wl, bi, sd)
            # The wrist helper takes the middle of the forearm-to-hand blend from both sides.
            hs = 0.85 * 4.0 * w_h * (1.0 - w_h) * w_fa
            Wl *= (1.0 - hs)[:, None]
            Wl[:, bi[f"wrist_k.{sd}"]] += hs
            W[side] = Wl
        return W

    # How far either side of a finger joint (in joint radii, along the bisector of its two bones)
    # the skin blends from one bone through the joint's helper to the next, and the helper's share
    # at the joint itself.
    JOINT_BAND = 1.3
    JOINT_HELPER = 0.9

    def _joint_bands(self, P, Wl, bi, sd: str) -> None:
        """Re-blends the skin across every finger and thumb joint (TD-174): from the nearest-bone
        weights, which switch bones within a few mm of the joint (so a curled knuckle dented and
        the clefts between the knuckles opened into slits), to a smooth ramp a joint's radius
        either side of it with the joint's helper bone in the middle. Skin behind a knuckle goes
        back to the hand (the palm's pads and the back of the hand stay put as a finger curls).
        Distal joints first, so each pass only moves weight its own two bones hold."""
        j = self.sk.j
        s = self.s
        ax = j[f"axis.{sd}"]
        h0 = Wl[:, bi[f"hand.{sd}"]].copy()
        # Which of the hand's weight each knuckle may take: near its own finger's axis only, and
        # shared where two fingers' roots meet (a cleft), so the hand's weight is handed out once.
        gates = {}
        for k, _name in FINGER_BONES:
            m, p = j[f"{k}_mcp.{sd}"], j[f"{k}_pip.{sd}"]
            d = _n(p - m)
            r = FINGER_SHAPE[k][0][0] * s
            rel = P - m
            lat = np.linalg.norm(rel - np.outer(rel @ d, d), axis=1)
            gates[k] = 1.0 - smoothstep(1.3 * r, 2.2 * r, lat)
        tot = np.maximum(1.0, sum(gates.values()))
        joints = []
        for k, name in FINGER_BONES:
            radii = FINGER_SHAPE[k][0]
            pts = [j[f"{k}_{n}.{sd}"] for n in ("mcp", "pip", "dip", "tip")]
            dirs = [_n(b - a) for a, b in zip(pts[:-1], pts[1:])]
            joints.append((pts[2], dirs[1], dirs[2], radii[2], f"{name}_2", f"{name}_3", f"{name}_k3", None))
            joints.append((pts[1], dirs[0], dirs[1], radii[1], f"{name}_1", f"{name}_2", f"{name}_k2", None))
            joints.append((pts[0], ax, dirs[0], radii[0], "hand", f"{name}_1", f"{name}_k1", gates[k] / tot))
        tp = [j[f"th_{n}.{sd}"] for n in ("cmc", "mcp", "ip", "tip")]
        td = [_n(b - a) for a, b in zip(tp[:-1], tp[1:])]
        joints.append((tp[2], td[1], td[2], THUMB_RADII[2], "thumb_2", "thumb_3", "thumb_k3", None))
        joints.append((tp[1], td[0], td[1], THUMB_RADII[1], "thumb_1", "thumb_2", "thumb_k2", None))
        # the thumb's root is deep in the thenar mass: only the thumb's own weight re-blends there
        joints.append((tp[0], ax, td[0], THUMB_RADII[0] * 1.4, "hand", "thumb_1", "thumb_k1", 0.0))
        for J, dp, dd, r, pb, db, hb, share in joints:
            ip, idd, ih = bi[f"{pb}.{sd}"], bi[f"{db}.{sd}"], bi[f"{hb}.{sd}"]
            b = _n(dp + dd)
            u = np.clip(((P - J) @ b) / (r * s * self.JOINT_BAND), -1.0, 1.0)
            wp = Wl[:, ip].copy()
            take = wp if share is None else h0 * share
            sl = take + Wl[:, idd]
            sm = smoothstep(-1.0, 1.0, u)
            hw = sl * self.JOINT_HELPER * (1.0 - u * u) ** 2
            Wl[:, idd] = (sl - hw) * sm
            Wl[:, ip] = wp - take + (sl - hw) * (1.0 - sm)
            Wl[:, ih] += hw


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

    def wrist_axes(self, sd: str):
        """Rest-space axes the wrist bends about: flexion (the palm towards the forearm), ulnar
        deviation (towards the little finger), and the forearm's own axis it rolls about."""
        j = self.sk.j
        a, b, lat = _n(j[f"axis.{sd}"]), _n(j[f"back.{sd}"]), _n(j[f"lat.{sd}"])
        ax = _n(self.sk.rest[f"forearm.{sd}"][:, 1])
        # Both bend axes square to the forearm's: the swing then has no roll in it, and
        # wrist_rotation inverts wrist_angles exactly (the hand's own axis is a few degrees off the
        # forearm's at rest, and a bend about axes square to it leaked into the measured roll).
        fx = _n(np.cross(a, -b))
        fx = _n(fx - ax * float(fx @ ax))
        ul = _n(np.cross(a, -lat))
        ul = _n(ul - ax * float(ul @ ax) - fx * float(ul @ fx))
        return fx, ul, ax

    def wrist_angles(self, sd: str, Qh: np.ndarray):
        """(flexion, ulnar deviation, roll) in degrees of a hand rotation relative to its forearm:
        the swing split from the roll about the forearm's axis, as a rotation vector on the flexion
        and deviation axes."""
        fx, ul, ax = self.wrist_axes(sd)
        q = _quat(Qh)
        tw = 2.0 * math.atan2(float(q[1:] @ ax), q[0])
        tw = (tw + math.pi) % (2 * math.pi) - math.pi
        sw = Qh @ rot_axis(ax, -tw)
        w = _rotvec(sw)
        return math.degrees(float(w @ fx)), math.degrees(float(w @ ul)), math.degrees(tw)

    def wrist_rotation(self, sd: str, flex: float, ulnar: float, roll: float) -> np.ndarray:
        """The hand-relative-to-forearm rotation for wrist angles (degrees): wrist_angles' inverse."""
        fx, ul, ax = self.wrist_axes(sd)
        w = fx * math.radians(flex) + ul * math.radians(ulnar)
        ang = float(np.linalg.norm(w))
        sw = rot_axis(w / ang, ang) if ang > 1e-9 else np.eye(3)
        return sw @ rot_axis(ax, math.radians(roll))

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
            grip = min(float(prm.get(f"{sd}.fist", 0.3)), FIST_MAX)
            idx = float(prm.get(f"{sd}.index", 0.0))
            thumb = float(prm.get(f"{sd}.thumb", grip))
            # Per-finger curls (a hand spec's or a key's `curls`) replace the fist (for the
            # index, fist + index) for the fingers they name.
            own = prm.get(f"{sd}.curls") or {}
            lat = sk.j[f"lat.{sd}"]
            for k, name in FINGER_BONES:
                c = max(-0.15, grip + idx) if k == "ix" else grip
                if name in own:
                    c = max(-0.15, min(float(own[name]), FIST_MAX))
                for i, deg in enumerate(FINGER_CURL):
                    bn = f"{name}_{i + 1}.{sd}"
                    Q[bn] = _R(sk.rest[bn][:, 0], -deg * c * FINGER_SCALE[k])
                # Closing fingers converge on the middle finger (splayed at rest, they would
                # close into gaps): swing each knuckle sideways, about its back-of-hand axis.
                bn = f"{name}_1.{sd}"
                r = sk.rest[bn]
                toward_thumb = 1.0 if float(np.cross(r[:, 2], r[:, 1]) @ lat) > 0 else -1.0
                Q[bn] = _R(r[:, 2], FINGER_CONVERGE[k] * max(0.0, c) * toward_thumb) @ Q[bn]
            # The thumb opposes as it closes: its metacarpal swings across the palm and turns
            # about its own length so the pad, not the side, meets the index finger; then its
            # two joints wrap the handle.
            t1 = sk.rest[f"thumb_1.{sd}"]
            Q[f"thumb_1.{sd}"] = _R(t1[:, 0], THUMB_CURL[0] * thumb) @ _R(t1[:, 2], THUMB_CURL[1] * thumb * sx) @ \
                _R(t1[:, 1], THUMB_CURL[2] * thumb * sx)
            Q[f"thumb_2.{sd}"] = _R(sk.rest[f"thumb_2.{sd}"][:, 0], -THUMB_CURL[3] * thumb)
            Q[f"thumb_3.{sd}"] = _R(sk.rest[f"thumb_3.{sd}"][:, 0], -THUMB_CURL[4] * thumb - float(prm.get(f"{sd}.flick", 0.0)))
            # Joint helpers: half the turn of the bone each one halves. The wrist's takes half the
            # hand's bend and a roll between the twist bone's share and the hand's.
            sw = Qh @ rot_axis(axis, -tw)
            for bn in HELPERS[sd]:
                if bn == f"wrist_k.{sd}":
                    Q[bn] = _half(sw) @ rot_axis(axis, tw * (1.0 + self.TWIST_SHARE) * 0.5)
                else:
                    Q[bn] = _half(Q[_helper_of(bn)])
        return Q, np.zeros(3)


HELPERS = {sd: [b[0] for b in FP_BONES if b[0].endswith("." + sd) and _helper_of(b[0])] for sd in ("L", "R")}


def _half(m: np.ndarray, t: float = 0.5) -> np.ndarray:
    """The rotation turned `t` of the way from none to m (about the same axis)."""
    return _qmat(_slerp(np.array([1.0, 0.0, 0.0, 0.0]), _quat(m), t))


def _rotvec(m: np.ndarray) -> np.ndarray:
    """Rotation vector (axis * angle, radians) of a rotation matrix."""
    q = _quat(m)
    if q[0] < 0:
        q = -q
    s_ = float(np.linalg.norm(q[1:]))
    if s_ < 1e-12:
        return np.zeros(3)
    return q[1:] / s_ * 2.0 * math.atan2(s_, float(q[0]))


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

# A bare fist closes further than a grip round a handle: fist runs up to this.
FIST_MAX = 1.3
# Finger curl at fist 1 (degrees at the MCP, PIP and DIP joints: a fist round a ~3.5 cm handle,
# the end joint following the middle one), scaled per finger: the ring and little fingers close
# a little further, as they do round a handle.
FINGER_CURL = (68.0, 92.0, 58.0)
FINGER_SCALE = {"ix": 1.0, "md": 1.0, "rg": 1.05, "pk": 1.12}
# How far each finger swings toward the thumb side (degrees, + towards it) at curl 1.
FINGER_CONVERGE = {"ix": -5.0, "md": 0.0, "rg": 4.0, "pk": 9.0}
# Thumb at curl 1: metacarpal flexion across the palm, swing toward the fingers, opposition about
# its own axis; then MCP and IP flexion (degrees).
THUMB_CURL = (30.0, 30.0, 25.0, 38.0, 48.0)

# A working wrist's range (degrees): flexion and extension, radial and ulnar deviation (an
# ellipse between them), and the forearm's roll either way of the thumb-up rest. viewmodel.json
# `wrist` overrides them.
WRIST_LIMITS = {"flex": 65.0, "extend": 55.0, "radial": 18.0, "ulnar": 32.0, "roll": 95.0}
# Where a wrist rests when nothing makes it work (ADR-0060): the same ellipse, much smaller and
# leaning toward extension, the forearm rolled no further than a hand resting on a table. Inside
# the full range a hand is possible; inside this one it looks relaxed. With only the full range,
# every idle settled at 50-60° of flexion and 15-20° of ulnar deviation (inside it, so free):
# the wrists bent hard down and in that player report 4 saw. viewmodel.json `wrist.comfort`
# overrides it.
WRIST_COMFORT = {"flex": 18.0, "extend": 30.0, "radial": 10.0, "ulnar": 20.0, "roll": 70.0}
# Degrees of over-range one degree of bend away from the middle of the comfort range costs: a
# tie-break between configurations that are all in range (the elbow and roll that keep the wrist
# straightest win), never a reason to break range.
COMFORT_COST = 0.25

SCALARS = ("fist", "thumb", "index", "flick")
DEFAULT_SCALARS = {"fist": 0.4, "thumb": 0.4, "index": 0.0, "flick": 0.0}


class Hand:
    """One hand's placement: grip point g, frame F (columns: knuckles, palm-ish, handle/thumb dir),
    elbow hint, curls; plus, for a hand on the other's handle, where along it and how turned."""

    __slots__ = ("g", "F", "elbow", "sc", "on", "along", "spin", "flip", "item")

    def __init__(self, g, F, elbow, sc, on=None, along=0.0, spin=0.0, flip=False, item=None):
        self.g, self.F, self.elbow, self.sc = g, F, elbow, sc
        self.on, self.along, self.spin, self.flip = on, along, spin, flip
        # The held item's turn and offset in this hand's socket (the hold's `item`), for a hand
        # gripping its handle `on` this one: it follows the item's axis, not the socket's.
        self.item = item


def _curls(v, where: str) -> dict:
    """A `curls` object ({finger: curl}, fingers index / middle / ring / pinky) checked."""
    if not isinstance(v, dict):
        raise ValueError(f"{where}: curls must be an object of finger -> curl")
    bad = [k for k in v if k not in FINGER_NAMES]
    if bad:
        raise ValueError(f"{where}: unknown finger(s) {bad} in curls (fingers: {', '.join(FINGER_NAMES)}; "
                         "the thumb has its own 'thumb' curl)")
    return {k: float(x) for k, x in v.items()}


def _scalars(spec: dict, base: dict | None = None) -> dict:
    out = dict(base) if base else dict(DEFAULT_SCALARS)
    for c in SCALARS:
        if c in spec:
            out[c] = float(spec[c])
    out["curls"] = dict(out.get("curls") or {})
    if "curls" in spec:
        out["curls"].update(_curls(spec["curls"], "hand spec"))
    return out


def finger_curl(sc: dict, finger: str) -> float:
    """What curl a finger closes to for these scalars: its own `curls` entry, else the fist (and
    the index's extra curl), as FPRig.evaluate reads them."""
    own = sc.get("curls") or {}
    if finger in own:
        return float(own[finger])
    return float(sc["fist"]) + (float(sc["index"]) if finger == "index" else 0.0)


def _spec_hand(sd: str, spec: dict) -> Hand:
    """An absolute hand spec (Godot camera space) -> Hand (Blender space)."""
    if "on" in spec:
        return Hand(None, None, g2b(spec.get("elbow", [0.0, 0.0, 0.0])), _scalars(spec), on=spec["on"],
                    along=float(spec.get("along", 0.2)), spin=float(spec.get("spin", 0.0)), flip=bool(spec.get("flip", False)))
    if "wrist" in spec:
        return Hand(g2b(spec["grip"]), _wrist_frame(sd, spec), g2b(spec.get("elbow", [0.0, 0.0, 0.0])), _scalars(spec),
                    item=spec.get("_item"))
    d = g2b(_n(np.asarray(spec["dir"], dtype=np.float64)))
    if "back" in spec:
        # right hand: (knuckles, thumb, back) is right-handed; the left mirrors it
        b = g2b(_n(np.asarray(spec["back"], dtype=np.float64)))
        k = np.cross(d, b) if sd == "R" else np.cross(b, d)
    else:
        k = g2b(_n(np.asarray(spec["knuckles"], dtype=np.float64)))
    return Hand(g2b(spec["grip"]), _frame(k, d), g2b(spec.get("elbow", [0.0, 0.0, 0.0])), _scalars(spec),
                item=spec.get("_item"))


_REST_RIG = []


def _wrist_frame(sd: str, spec: dict) -> np.ndarray:
    """The hand frame of a spec written against its own forearm (ADR-0060): `wrist` = [flexion,
    ulnar deviation, roll] in degrees (wrist_angles' terms; roll + pronates the right hand, - the
    left), the arm reaching the grip with its elbow at the hint. A hand at rest has no tool to
    point; what makes it look relaxed is the wrist, so the wrist is what it says."""
    if not _REST_RIG:
        sk = FPSkeleton(fp_joints({}), {}, bones=FP_BONES)
        _REST_RIG.append(PoseSolver(FPRig(sk)))
    sol = _REST_RIG[0]
    rig = sol.rig
    f, u, r = (float(x) for x in spec["wrist"])
    g = g2b(spec["grip"])
    pole = _n(sol.pole0[sd] + g2b(spec.get("elbow", [0.0, 0.0, 0.0])))
    Rh = sol._arm(sd, g - rig.grip_off[sd], pole, np.eye(3))[0] @ rig.wrist_rotation(sd, f, u, r)
    for _ in range(6):
        A, _q = sol._arm(sd, g - Rh @ rig.grip_off[sd], pole, Rh)
        Rh = A @ rig.wrist_rotation(sd, f, u, r)
    return Rh @ rig.S0[sd]


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
    # S.curls overrides those fingers for this key; the others keep the hold's own curls.
    sc["curls"] = dict(h.sc.get("curls") or {})
    if f"{sd}.curls" in ch:
        sc["curls"].update(_curls(ch[f"{sd}.curls"], f"key channel {sd}.curls"))
    if h.on is not None:
        return Hand(None, euler_g(rot), el, sc, on=h.on, along=float(ch.get(f"{sd}.along", h.along)),
                    spin=float(ch.get(f"{sd}.spin", h.spin)), flip=h.flip)
    return Hand(h.g + mv, euler_g(rot) @ h.F, el, sc, item=h.item)


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
    # A finger with its own curl at either key eases between what it closes to at each (a key
    # without one closes it with the fist), so it neither snaps nor waits for the fist.
    fingers = set(a.sc.get("curls") or {}) | set(b.sc.get("curls") or {})
    sc["curls"] = {f: finger_curl(a.sc, f) + (finger_curl(b.sc, f) - finger_curl(a.sc, f)) * t for f in fingers}
    el =a.elbow + (b.elbow - a.elbow) * t
    F = _qmat(_slerp(_quat(a.F), _quat(b.F), t)) if a.F is not None and b.F is not None else None
    if a.on is not None:
        return Hand(None, F, el, sc, on=a.on, along=a.along + (b.along - a.along) * t, spin=a.spin + (b.spin - a.spin) * t,
                    flip=a.flip)
    return Hand(a.g + (b.g - a.g) * t, F, el, sc, item=a.item)


class PoseSolver:
    """Hands -> rig parameters. A hand 'on' the other grips its handle `along` metres up it
    (+ towards the head) with its knuckles turned `spin` degrees round it (its F, when keyed, is
    an extra rotation in camera axes).

    A pose names where the grip is and how the hand is turned, not where the forearm goes, and a
    wrist only bends so far: an arm laid out by its elbow hint alone left the wrists of most holds
    bent ~90° (up to 140° mid-swing), which is what made them read wrong. So the elbow is swung
    round the shoulder-wrist line to where the forearm best lines up with the hand (staying near
    the authored hint), and whatever bend is left past the wrist's range (`wrist` in
    viewmodel.json: flexion, extension, radial and ulnar deviation, forearm roll) is taken out
    of the hand's turn, keeping the grip where the pose put it."""

    # The search, in degrees: the elbow swung either side of its hint round the shoulder-wrist
    # line, and the hand spun about its handle. What a pose must keep is where the tool points; how
    # the fist is rolled round the handle is free within reason, and turning it is often all a
    # wrist needs (a spear held forward from the hip). The first frame of an action searches wide;
    # later frames search near the last answer, so the arm doesn't jump between solutions, unless
    # that answer leaves the wrist past its range.
    SWINGS = tuple(range(-100, 101, 10))
    SPINS = tuple(range(-90, 91, 10))
    NEAR = (-12.0, -6.0, -3.0, 0.0, 3.0, 6.0, 12.0)
    # Cost of a degree off the hints relative to a degree of over-bend (so between equally good
    # answers the hinted elbow and the authored roll win).
    # A grip moves at most this far (m) to spare a wrist: past it the pose is wrong, not a little
    # off, and the hand turns instead (and the build log says how far).
    MOVE_MAX = 0.06
    # ...and a hand at rest this far (m) to keep its wrist relaxed: an idle's grip is where the
    # hand happens to be, so it gives way before the wrist does.
    MOVE_RELAXED = 0.10
    SWING_COST = 0.15
    # What a jump to another arm configuration between two frames must save (degrees of over-bend):
    # a jump is seen as the hand spinning in one frame.
    JUMP_COST = 40.0
    # An authored hand turning this fast (degrees a frame) hides a jump completely.
    FAST = 25.0
    SPIN_COST = 0.12

    def __init__(self, rig: FPRig, limits: dict | None = None):
        self.rig = rig
        j = rig.sk.j
        self.pole0 = {sd: j[f"pole.{sd}"] for sd, _ in SIDES}
        lim = dict(WRIST_LIMITS)
        lim.update({k: float(v) for k, v in (limits or {}).items() if not k.startswith("_") and k in WRIST_LIMITS})
        comfort = dict(WRIST_COMFORT)
        comfort.update({k: float(v) for k, v in ((limits or {}).get("comfort") or {}).items() if k in WRIST_COMFORT})
        self.full, self.comfort = lim, comfort
        self._fk0 = rig.sk.fk({})
        self.lim = lim
        self.reset()

    def relax(self, w: float) -> None:
        """Limits for a hand `w` (0..1) of the way from the full range to the comfort range: 1 for
        a hold at rest, fading to 0 as a strike carries the hand away from it (ADR-0060)."""
        w = max(0.0, min(1.0, float(w)))
        self.w = w
        self.lim = {k: self.full[k] + (self.comfort[k] - self.full[k]) * w for k in self.full}

    def _ease(self, flex: float, ulnar: float) -> float:
        """Degrees a wrist is bent off the middle of its comfort range (the tie-break cost)."""
        C = self.comfort
        return math.hypot(flex - 0.5 * (C["flex"] - C["extend"]), ulnar - 0.5 * (C["ulnar"] - C["radial"]))

    def reset(self) -> None:
        """Start a new action: search wide again and forget how far hands were turned."""
        self.relax(0.0)
        self.prev = {}                  # side -> (swing, spin) of the last frame
        self.prev_F = {}                # side -> the hand frame the last frame asked for
        self.clamped = {}               # side -> worst degrees a hand was turned back by
        self.moved = {}                 # side -> furthest (m) a grip was moved to spare the wrist

    def _over(self, flex: float, ulnar: float, roll: float) -> float:
        """How far (degrees, elliptical) a wrist pose is outside the limits; 0 inside."""
        L = self.lim
        f = flex / (L["flex"] if flex > 0 else L["extend"])
        u = ulnar / (L["ulnar"] if ulnar > 0 else L["radial"])
        e = math.hypot(f, u)
        over = max(0.0, e - 1.0) * math.hypot(flex, ulnar) / max(e, 1e-9)
        return over + max(0.0, abs(roll) - L["roll"])

    def _clamp(self, flex: float, ulnar: float, roll: float):
        L = self.lim
        f = flex / (L["flex"] if flex > 0 else L["extend"])
        u = ulnar / (L["ulnar"] if ulnar > 0 else L["radial"])
        e = math.hypot(f, u)
        if e > 1.0:
            flex, ulnar = flex / e, ulnar / e
        return flex, ulnar, max(-L["roll"], min(L["roll"], roll))

    def _arm(self, sd: str, wrist, pole, Rh):
        """IK the arm to `wrist` bending toward `pole`: (forearm world rotation, hand rotation
        relative to it)."""
        sk = self.rig.sk
        Q = {}
        # The shoulders never move: the rest pose's fk serves every candidate, and the forearm's
        # turn is its parent's (at rest) times the two bones' (a full fk per candidate was most of
        # the bake's time).
        up = f"upper_arm.{sd}"
        sk.solve_two_bone(Q, up, f"forearm.{sd}", wrist, pole, z_sign=-1.0, base=self._fk0)
        A = self._fk0[0][sk.parent[up]] @ Q[up] @ Q[f"forearm.{sd}"]
        return A, A.T @ Rh

    def _straight_wrist(self, sd: str, wrist, Rh):
        """Where the wrist would be, nearest `wrist`, for this hand turn with the wrist straight:
        the forearm along the hand's rest relation, the elbow anywhere the upper arm reaches."""
        sk = self.rig.sk
        f = Rh @ sk.rest[f"forearm.{sd}"][:, 1]
        sh = sk.j[f"shoulder.{sd}"]
        l1, l2 = sk.length(f"upper_arm.{sd}"), sk.length(f"forearm.{sd}")
        c = sh + f * l2
        return c + _n(np.asarray(wrist) - c) * l1, c

    def _fit(self, sd: str, g, F, elbow, movable: bool = True, item=None, fixed_roll: bool = False):
        """(wrist, Rh, pole) for a grip at g with its handle along F's z: the elbow and the roll
        round the handle that bend the wrist least; then, if the wrist is still past its range,
        the hand moved (tool direction kept) just far enough toward where a straight wrist would
        put it; and what is left turned back about the grip."""
        rig = self.rig
        hint = _n(self.pole0[sd] + elbow)
        g = np.asarray(g, dtype=np.float64)
        d, k = F[:, 2], F[:, 0]
        sh = rig.sk.j[f"shoulder.{sd}"]
        # The fist rolls about what it holds: the item's own axis, which an oblique grip turns off
        # the socket's (rolled about the socket's, a spear held across the palm would swing away).
        spin_ax = item_axis(Hand(g, F, None, None, item=item))[0]

        def place(gg, sw, sp):
            Rs = _R(spin_ax, sp)
            Rh = rig.hand(sd, gg, Rs @ d, Rs @ k)[1]
            wrist = gg - Rh @ rig.grip_off[sd]
            pole = rot_axis(_n(wrist - sh), math.radians(sw)) @ hint
            return wrist, Rh, pole

        def angles(gg, sw, sp):
            wrist, Rh, pole = place(gg, sw, sp)
            return rig.wrist_angles(sd, self._arm(sd, wrist, pole, Rh)[1])

        def over(gg, sw, sp):
            return self._over(*angles(gg, sw, sp))

        def cost(gg, sw, sp):
            a = angles(gg, sw, sp)
            return self._over(*a) + COMFORT_COST * self._ease(a[0], a[1]) + self.SWING_COST * abs(sw) + \
                self.SPIN_COST * abs(sp)

        # A pinned roll (`fixed_roll`: a gun's barrel, an inspect's turn-over) searches the elbow only.
        spins = (0.0,) if fixed_roll else self.SPINS
        near_spin = (0.0,) if fixed_roll else self.NEAR

        def search(gg, around):
            if around is None:
                best = min(((a, b) for a in self.SWINGS for b in spins), key=lambda c: cost(gg, *c))
            else:
                best = around
            near = ((best[0] + a, best[1] + b) for a in self.NEAR for b in near_spin)
            # Within the wide search's bounds: walked frame to frame, the fist once spun 160° round
            # its handle and the elbow swung behind the back.
            return min((c for c in near if abs(c[0]) <= self.SWINGS[-1] and abs(c[1]) <= self.SPINS[-1]),
                       key=lambda c: cost(gg, *c))

        sw, sp = search(g, self.prev.get(sd))
        if sd in self.prev and over(g, sw, sp) > 0.5:
            # A fast swing can outrun the local search: look wide again and take a better answer
            # (the arm may change its elbow between two frames of a strike, never in an idle).
            wide = search(g, None)
            # Mid-strike the hand already turns fast and a new elbow is lost in it; in a slow
            # move it reads as the hand spinning in one frame.
            pf = self.prev_F.get(sd)
            pace = math.degrees(float(np.linalg.norm(_rotvec(F @ pf.T)))) if pf is not None else 0.0
            if cost(g, *wide) + self.JUMP_COST * max(0.0, 1.0 - pace / self.FAST) < cost(g, sw, sp):
                sw, sp = wide
        moved = 0.0
        if movable and over(g, sw, sp) > 0.5:
            # Bisect how far toward the straight-wrist grip the hand must go.
            wrist, Rh, _ = place(g, sw, sp)
            ws, _c = self._straight_wrist(sd, wrist, Rh)
            shift = ws - wrist
            n = float(np.linalg.norm(shift))
            reach = self.MOVE_MAX + (self.MOVE_RELAXED - self.MOVE_MAX) * self.w
            if n > reach:
                shift *= reach / n
            lo, hi = 0.0, 1.0
            fit = search(g + shift, (sw, sp))
            for _ in range(7):
                mid = 0.5 * (lo + hi)
                cand = search(g + shift * mid, (sw, sp))
                if over(g + shift * mid, *cand) <= 0.5:
                    hi, fit = mid, cand
                else:
                    lo = mid
            g = g + shift * hi
            sw, sp = fit
            moved = float(np.linalg.norm(shift)) * hi
        self.prev[sd] = (sw, sp)
        self.prev_F[sd] = F
        wrist, Rh, pole = place(g, sw, sp)
        # Turn the hand back inside the range, about the wrist: in one step, the forearm stays
        # where the arm put it and the grip shifts a little. (Turned about the grip instead, each
        # correction moved the forearm and so the angles again, and a hand 1° past its range could
        # wander 40° off.)
        R0 = Rh
        A, Qh = self._arm(sd, wrist, pole, Rh)
        ang = rig.wrist_angles(sd, Qh)
        c = self._clamp(*ang)
        if max(abs(x - y) for x, y in zip(ang, c)) > 0.05:
            Rh = A @ rig.wrist_rotation(sd, *c)
            g = wrist + Rh @ rig.grip_off[sd]
        turned = math.degrees(float(np.linalg.norm(_rotvec(Rh @ R0.T))))
        self.clamped[sd] = max(self.clamped.get(sd, 0.0), turned)
        self.moved[sd] = max(self.moved.get(sd, 0.0), moved)
        return g, wrist, Rh, pole

    def solve(self, hands: dict) -> dict:
        prm = {}
        placed = {}
        self.relax(hands.get("_relax", 0.0))
        for sd, _ in sorted(SIDES, key=lambda s: 1 if hands[s[0]].on is not None else 0):
            h = hands[sd]
            if h.on is not None:
                o = placed[h.on]
                d0, k0, g0 = item_axis(o)
                g = g0 + d0 * h.along
                d = -d0 if h.flip else d0
                k = _R(d0, h.spin) @ k0
                if h.F is not None:
                    d, k = h.F @ d, h.F @ k
                F = _frame(k, d)
            else:
                g, F = h.g, h.F
            # A hand on the other's handle stays on it: it can turn, not move.
            g, wrist, Rh, pole = self._fit(sd, g, F, h.elbow, movable=h.on is None, item=h.item,
                                           fixed_roll=sd in hands.get("_fixed_roll", ()))
            # What the hand really ended up gripping (the other hand follows this handle).
            placed[sd] = Hand(g, Rh @ self.rig.S0[sd], h.elbow, h.sc, item=h.item)
            prm[f"{sd}.wrist"], prm[f"{sd}.Rh"] = wrist, Rh
            prm[f"{sd}.pole"] = pole
            for c in SCALARS:
                prm[f"{sd}.{c}"] = h.sc[c]
            prm[f"{sd}.curls"] = dict(h.sc.get("curls") or {})
        return prm


def item_axis(h: Hand):
    """(axis, knuckle-side reference, origin) for a hand gripping the handle of the item `h` holds,
    Blender space: the handle's direction is the socket's handle axis turned by the hold's `item`
    rot (deg, Godot's YXZ Euler in socket space, as ViewModelHolds.item_transform places it). An
    oblique grip (a spear's shaft across the palm) turns it off the socket's axis, and the second
    hand follows the shaft. A turn about the handle itself (the club's) moves nothing; `along` is
    measured from this hand's grip, and the item's `pos` (sliding the model in the fist) is
    cosmetic."""
    k, d = h.F[:, 0], h.F[:, 2]
    rot = list(h.item.get("rot", [0, 0, 0])) if h.item else [0, 0, 0]
    if not any(float(a) for a in rot):
        return d, k, h.g
    # Socket axes in Blender space: +X the knuckles, +Y the handle, +Z = X x Y.
    M = np.stack([k, d, np.cross(k, d)], 1)
    rx, ry, rz = (math.radians(float(a)) for a in rot)
    Rx = np.array([[1, 0, 0], [0, math.cos(rx), -math.sin(rx)], [0, math.sin(rx), math.cos(rx)]])
    Ry = np.array([[math.cos(ry), 0, math.sin(ry)], [0, 1, 0], [-math.sin(ry), 0, math.cos(ry)]])
    Rz = np.array([[math.cos(rz), -math.sin(rz), 0], [math.sin(rz), math.cos(rz), 0], [0, 0, 1]])
    ax = _n((M @ (Ry @ Rx @ Rz))[:, 1])
    if float(ax @ d) > 0.9999:
        return d, k, h.g
    ref = k - ax * float(k @ ax)
    if float(np.linalg.norm(ref)) < 1e-6:
        ref = np.cross(ax, d)
    return ax, _n(ref), h.g


def with_item(pose: dict, hold: dict) -> dict:
    """The pose with the hold's `item` placement on the hand that holds it (for item_axis)."""
    it = hold.get("item")
    sd = str(hold.get("hand", "R"))
    if not it or sd not in pose or "on" in pose[sd]:
        return pose
    out = dict(pose)
    out[sd] = dict(pose[sd])
    out[sd]["_item"] = it
    return out


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
        fr = _key_hands(hold, ch)
        fr["_relax"] = 1.0
        frames.append(fr)
    return frames


# A keyed hand this far from its hold (degrees of turn; a centimetre of grip counts as RELAX_CM
# degrees) has left rest and may use the wrist's full range; nearer, its limits ease back toward
# the comfort range, so a strike starts and ends on the arm its idle bakes.
RELAX_SPAN = 30.0
RELAX_CM = 3.0
USE_RELAX = 0.5


def _relax_of(frame: dict, hold: dict, floor: float = 0.0) -> float:
    d = 0.0
    for sd, h0 in hold.items():
        h = frame.get(sd)
        if h is None or h.F is None or h0.F is None or h.g is None or h0.g is None:
            continue
        turn = math.degrees(float(np.linalg.norm(_rotvec(h.F @ h0.F.T))))
        d = max(d, turn + RELAX_CM * 100.0 * float(np.linalg.norm(h.g - h0.g)))
    return max(floor, 1.0 - d / RELAX_SPAN)


def _keyed(pose: dict, keys: list, n: int, relax: float = 0.0) -> list[dict]:
    """Per-frame hands from [frame, channels-or-hands, ease] keys (positions eased, frames slerped),
    each with how relaxed its wrists are kept (`_relax`, at least `relax`)."""
    frames = _keyed_hands(pose, keys, n)
    hold = pose_hands(pose)
    for fr in frames:
        fr["_relax"] = _relax_of(fr, hold, relax)
    return frames


def _keyed_hands(pose: dict, keys: list, n: int) -> list[dict]:
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


def _pinned(frames: list[dict], sides: tuple) -> list[dict]:
    """Frames whose hands on `sides` keep their authored roll about what they hold (`fixed_roll`
    on a hold or an action): PoseSolver won't spin those fists to spare the wrist."""
    if sides:
        for fr in frames:
            fr["_fixed_roll"] = sides
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
        fixed = tuple(h.get("fixed_roll", ()))
        out.append((f"fp_{cls}", 60, True, _pinned(_idle(with_item(pose, h)), fixed)))
        if "guard" in h:
            out.append((f"fp_{cls}_guard", 60, True, _pinned(_idle(with_item(merge_pose(pose, h["guard"]), h)), fixed)))
        if "pose" in tether and not h.get("no_tether", False):
            over = {"L": tether["pose"]["L"]}
            if "tether_right" in h:
                over["R"] = h["tether_right"]
            out.append((f"fp_{cls}_tether", 60, True, _pinned(_idle(with_item(merge_pose(pose, over), h)), fixed)))
    for group in ("attacks", "uses"):
        for name, a in cfg.get(group, {}).items():
            if name.startswith("_") or "keys" not in a:
                continue
            pose = holds[a["hold"]]["pose"]
            if "pose" in a:
                pose = merge_pose(pose, a["pose"])
            n = int(a["frames"])
            fixed = tuple(a.get("fixed_roll", holds[a["hold"]].get("fixed_roll", ())))
            # A use (eating, lighting, reloading) is slow and watched: its wrists stay at least
            # half relaxed throughout; a strike may use the whole range once under way.
            relax = float(a.get("relax", USE_RELAX if group == "uses" else 0.0))
            out.append((f"fp_{name}", n, bool(a.get("loop", False)),
                        _pinned(_keyed(with_item(pose, holds[a["hold"]]), a["keys"], n, relax), fixed)))
    return out
