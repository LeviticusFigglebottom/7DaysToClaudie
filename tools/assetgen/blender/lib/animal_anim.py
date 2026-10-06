"""Quadruped actions (ADR-0027): procedural gaits with IK legs, grazing, alert, bedding and death,
baked per frame (30 fps, in place) on the quadruped skeleton (animal_skel) and written with the
character toolkit's action writer (char_anim.write_action).

Pose parameters (degrees, metres; missing = rest):
  body.x/y/z            pelvis offset (armature space, after the root's roll)
  root.roll             the whole animal rolled about its long axis (lying dead on its side)
  hips.flex / hips.side / hips.twist, spine.*, chest.*, neck.*, neck2.*, head.*   (flex > 0 lowers
                        the front of the bone: the nose goes down)
  jaw.open, tail.lift (> 0 raises it: the deer's flag), tail.side, ear.S.fwd, ear.S.out
  scap.K                shoulder blade swing (front legs, K in FL / FR)
  Legs K in FL, FR, HL, HR are IK by default: foot.K.x/y/z moves the toe tip from its rest spot,
  foot.K.can turns the cannon (metacarpus / metatarsus) from its rest direction and foot.K.hoof
  the hoof or toes (both about the lateral axis; > 0 swings the lower end back). With
  fk.K = 1 the leg is posed by angles instead: leg.K.0 .. leg.K.4 (scapula / thigh down).
"""
from __future__ import annotations

import math

import numpy as np

from . import char_anim as CA
from .char_skel import _n, mat_to_quat, rot_axis

FPS = 30
X = np.array([1.0, 0.0, 0.0])
Y = np.array([0.0, 1.0, 0.0])
Z = np.array([0.0, 0.0, 1.0])
LEGS = {
    "FL": ("L", ("scapula.L", "upper_arm.L", "forearm.L", "cannon_f.L", "hoof_f.L"), "carpus.L", "fetlock_f.L", "toe_f.L"),
    "FR": ("R", ("scapula.R", "upper_arm.R", "forearm.R", "cannon_f.R", "hoof_f.R"), "carpus.R", "fetlock_f.R", "toe_f.R"),
    "HL": ("L", ("thigh.L", "shin.L", "cannon_h.L", "hoof_h.L"), "hock.L", "fetlock_h.L", "toe_h.L"),
    "HR": ("R", ("thigh.R", "shin.R", "cannon_h.R", "hoof_h.R"), "hock.R", "fetlock_h.R", "toe_h.R"),
}


def R(axis, deg):
    return rot_axis(axis, math.radians(deg))


ease = CA.ease


class QuadRig:
    def __init__(self, skel, params: dict):
        self.sk = skel
        self.p = params
        self.s = float(params.get("scale", 1.0))
        self.species = params.get("species", "deer")

    def evaluate(self, prm: dict):
        sk = self.sk
        g = lambda k, d=0.0: float(prm.get(k, d))  # noqa: E731
        Q = {"root": R(Y, g("root.roll"))}
        for b in ("hips", "spine", "chest", "neck", "neck2", "head"):
            Q[b] = R(Z, g(f"{b}.twist")) @ R(Y, g(f"{b}.side")) @ R(X, g(f"{b}.flex"))
        if self.species == "hound":
            # the hound's jaw drops for jaw.open > 0 (the Hollowed's convention); tail2 curls on
            Q["jaw"] = R(X, g("jaw.open"))
            Q["tail2"] = R(Z, g("tail2.side")) @ R(X, -g("tail2.lift"))
        else:
            Q["jaw"] = R(X, -g("jaw.open"))
        Q["tail"] = R(Z, g("tail.side")) @ R(X, -g("tail.lift"))
        for sd, sx in (("L", 1.0), ("R", -1.0)):
            Q[f"ear.{sd}"] = R(Z, sx * g(f"ear.{sd}.out")) @ R(X, -g(f"ear.{sd}.fwd"))
        off = np.array([g("body.x"), g("body.y"), g("body.z")])
        for key, (sd, bones, mid, fet, toe) in LEGS.items():
            front = key[0] == "F"
            if front:
                Q[bones[0]] = R(X, g(f"scap.{key}"))
            if f"blend.{key}" in prm:
                # hound: the leg mixes its IK and FK poses (blend 0 = IK, 1 = FK), so a leg
                # folding under the body or reaching off the ground never pops between the two
                self._blend_leg(Q, key, prm, off, g(f"blend.{key}"))
                continue
            if g(f"fk.{key}") > 0.5:
                for i, bn in enumerate(bones):
                    if front and i == 0:
                        Q[bn] = R(X, g(f"scap.{key}") + g(f"leg.{key}.0"))
                        continue
                    k = i if front else i + 1
                    sx = 1.0 if sd == "L" else -1.0
                    Q[bn] = R(Y, -sx * g(f"leg.{key}.{k}a")) @ R(X, g(f"leg.{key}.{k}")) @ R(sk.axis(bn), g(f"leg.{key}.{k}t"))
                continue
            self._ik_leg(Q, key, prm, off)
        return Q, off

    def _fk_leg(self, Q, key, prm):
        sk = self.sk
        g = lambda k, d=0.0: float(prm.get(k, d))  # noqa: E731
        sd, bones = LEGS[key][0], LEGS[key][1]
        front = key[0] == "F"
        sx = 1.0 if sd == "L" else -1.0
        for i, bn in enumerate(bones):
            if front and i == 0:
                Q[bn] = R(X, g(f"scap.{key}") + g(f"leg.{key}.0"))
                continue
            k = i if front else i + 1
            Q[bn] = R(Y, -sx * g(f"leg.{key}.{k}a")) @ R(X, g(f"leg.{key}.{k}")) @ R(sk.axis(bn), g(f"leg.{key}.{k}t"))

    def _blend_leg(self, Q, key, prm, off, w):
        bones = LEGS[key][1]
        w = min(1.0, max(0.0, w))
        Qi, Qf = dict(Q), dict(Q)
        if w < 1.0:
            self._ik_leg(Qi, key, prm, off)
        if w > 0.0:
            self._fk_leg(Qf, key, prm)
        for bn in bones:
            if bn in Qi or bn in Qf:
                Q[bn] = _slerp_m(Qi.get(bn, np.eye(3)), Qf.get(bn, np.eye(3)), w)

    def _ik_leg(self, Q, key, prm, off):
        sk = self.sk
        sd, bones, mid, fet, toe = LEGS[key]
        front = key[0] == "F"
        upper, lower, cannon, hoof = (bones[1], bones[2], bones[3], bones[4]) if front else bones
        j = sk.j
        toe_t = j[toe] + np.array([prm.get(f"foot.{key}.x", 0.0), prm.get(f"foot.{key}.y", 0.0), prm.get(f"foot.{key}.z", 0.0)])
        h_rot = R(X, float(prm.get(f"foot.{key}.hoof", 0.0)))
        c_rot = R(X, float(prm.get(f"foot.{key}.can", 0.0)))
        fet_t = toe_t - h_rot @ (j[toe] - j[fet])
        mid_t = fet_t - c_rot @ (j[fet] - j[mid])
        # elbows point back, stifles forward; both a little out
        sx = 1.0 if sd == "L" else -1.0
        pole = np.array([sx * 0.15, 1.0 if front else -1.0, 0.0])
        sk.solve_two_bone(Q, upper, lower, mid_t, _n(pole), off, z_sign=1.0)
        acc, pos = sk.fk(Q, off)
        sk.aim(Q, cannon, fet_t - pos[cannon], c_rot @ sk.rest[cannon][:, 2], off)
        sk.aim(Q, hoof, toe_t - fet_t, h_rot @ sk.rest[hoof][:, 2], off)


def _quat_to_m(q):
    w, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def _slerp_m(A, B, t):
    """Rotation matrices: A at t = 0, B at t = 1."""
    if t <= 0.0:
        return A
    if t >= 1.0:
        return B
    qa, qb = mat_to_quat(A), mat_to_quat(B)
    d = float(np.dot(qa, qb))
    if d < 0:
        qb, d = -qb, -d
    if d > 0.9995:
        q = qa + (qb - qa) * t
    else:
        th = math.acos(d)
        q = (math.sin((1 - t) * th) * qa + math.sin(t * th) * qb) / math.sin(th)
    return _quat_to_m(q / np.linalg.norm(q))


# --------------------------------------------------------------------------------------------
# Gaits
# --------------------------------------------------------------------------------------------

# phase offsets per leg, duty factor, stride (m at scale 1), lift (m), cannon fold in swing
# (front back, hind forward), and the body's motion per cycle.
GAITS = {
    "deer": {
        "walk": {"phase": {"HL": 0.0, "FL": 0.25, "HR": 0.5, "FR": 0.75}, "duty": 0.66, "stride": 0.55, "lift": 0.10,
                 "fold_f": 85.0, "fold_h": -22.0, "bob": 0.012, "bob_n": 2, "pitch": 1.0, "nod": 5.0, "neck": 18.0},
        "trot": {"phase": {"FL": 0.0, "HR": 0.0, "FR": 0.5, "HL": 0.5}, "duty": 0.48, "stride": 0.80, "lift": 0.16,
                 "fold_f": 105.0, "fold_h": -28.0, "bob": 0.028, "bob_n": 2, "pitch": 1.5, "nod": 3.0, "neck": 10.0},
        "gallop": {"phase": {"HL": 0.0, "HR": 0.08, "FL": 0.48, "FR": 0.58}, "duty": 0.34, "stride": 1.05, "lift": 0.24,
                   "fold_f": 120.0, "fold_h": -30.0, "bob": 0.10, "bob_n": 1, "pitch": 9.0, "nod": 6.0, "neck": 4.0,
                   "spine": 9.0, "flight": True},
    },
    "hare": {
        "hop": {"phase": {"FL": 0.0, "FR": 0.12, "HL": 0.52, "HR": 0.56}, "duty": 0.42, "stride": 0.11, "lift": 0.035,
                "fold_f": 70.0, "fold_h": 20.0, "bob": 0.028, "bob_n": 1, "pitch": 6.0, "nod": 4.0, "neck": 0.0,
                "spine": 5.0, "hare": True},
        "bound": {"phase": {"FL": 0.0, "FR": 0.09, "HL": 0.50, "HR": 0.54}, "duty": 0.30, "stride": 0.24, "lift": 0.07,
                  "fold_f": 95.0, "fold_h": 25.0, "bob": 0.06, "bob_n": 1, "pitch": 9.0, "nod": 5.0, "neck": 0.0,
                  "spine": 8.0, "hare": True, "flight": True},
    },
}


def gait_frames(rig: QuadRig, kind: str, n: int, base: dict | None = None) -> list[dict]:
    g = GAITS[rig.species][kind]
    s = rig.s
    stride = g["stride"] * s
    lift = g["lift"] * s
    out = []
    for f in range(n):
        t = f / n
        prm = dict(base or {})
        for key, ph in g["phase"].items():
            front = key[0] == "F"
            u = (t - ph) % 1.0
            duty = g["duty"]
            if u < duty:
                a = u / duty
                y = -stride / 2 + a * stride
                z = 0.0
                fold = 0.0
                # push-off: the heel and fetlock rise as the leg trails
                push = ease(max(0.0, (a - 0.65) / 0.35), "in")
            else:
                a = (u - duty) / (1.0 - duty)
                y = stride / 2 - stride * ease(a)
                z = lift * math.sin(math.pi * a) ** 0.9
                fold = math.sin(math.pi * min(1.0, a * 1.15)) ** 0.8
                push = (1.0 - a) ** 2
            if g.get("hare") and not front:
                # the long hind foot: flat in stance, heel up as it drives, rolling forward in the air
                can = 55.0 * push + g["fold_h"] * fold
                hoof = -20.0 * push + 25.0 * fold
            elif front:
                can = g["fold_f"] * fold + 10.0 * push
                hoof = g["fold_f"] * 0.55 * fold + 25.0 * push
            else:
                can = g["fold_h"] * fold - 8.0 * push
                hoof = -g["fold_h"] * 1.2 * fold + 20.0 * push
            prm[f"foot.{key}.y"] = y
            prm[f"foot.{key}.z"] = z
            prm[f"foot.{key}.can"] = can
            prm[f"foot.{key}.hoof"] = hoof
        w = 2 * math.pi * t
        bn = g["bob_n"]
        if g.get("flight"):
            # up in the air between the hind push and the front landing, lowest as the fronts strike
            prm["body.z"] = prm.get("body.z", 0.0) + g["bob"] * s * (0.5 + 0.5 * math.cos(w - 2 * math.pi * 0.28))
            prm["hips.flex"] = prm.get("hips.flex", 0.0) + g["pitch"] * math.sin(w + 0.6)
            prm["spine.flex"] = prm.get("spine.flex", 0.0) - g.get("spine", 0.0) * math.cos(w - 0.4)
            prm["chest.flex"] = prm.get("chest.flex", 0.0) - g.get("spine", 0.0) * 0.6 * math.cos(w - 0.4)
        else:
            prm["body.z"] = prm.get("body.z", 0.0) - g["bob"] * s * (0.5 + 0.5 * math.cos(bn * w))
            prm["hips.flex"] = prm.get("hips.flex", 0.0) + g["pitch"] * math.sin(bn * w)
            prm["hips.side"] = prm.get("hips.side", 0.0) + 1.5 * math.sin(w)
            if g.get("spine"):
                prm["spine.flex"] = prm.get("spine.flex", 0.0) - g["spine"] * math.cos(w - 0.4)
        prm["neck.flex"] = prm.get("neck.flex", 0.0) + g["neck"] + g["nod"] * math.sin(2 * w + 0.8)
        prm["head.flex"] = prm.get("head.flex", 0.0) - g["nod"] * 0.6 * math.sin(2 * w + 0.8)
        prm["tail.lift"] = prm.get("tail.lift", 0.0) + 4.0 * math.sin(2 * w)
        out.append(prm)
    return out


# --------------------------------------------------------------------------------------------
# Poses and actions
# --------------------------------------------------------------------------------------------

def _breath(prm: dict, f: int, n: int, amp: float = 1.0) -> dict:
    w = 2 * math.pi * f / n
    prm["chest.flex"] = prm.get("chest.flex", 0.0) + 0.8 * amp * math.sin(w)
    prm["body.z"] = prm.get("body.z", 0.0) + 0.002 * amp * math.sin(w)
    return prm


def _ear_flicks(prm, f, n, seed, base_fwd=0.0, base_out=0.0, amp=1.0):
    """Ears that never quite settle: seamless drift plus one quick flick each per loop."""
    for sd, o in (("L", 0), ("R", 7)):
        start = (n * (0.3 + 0.37 * (sd == "R")) + seed * 3) % n
        flick = CA.smooth_pulse(f, start, 3, 2, 6)
        prm[f"ear.{sd}.fwd"] = base_fwd + amp * (8.0 * CA.loop_noise(seed + o, f, n) - 18.0 * flick)
        prm[f"ear.{sd}.out"] = base_out + amp * (6.0 * CA.loop_noise(seed + o + 31, f, n) + 10.0 * flick)
    return prm


def act_idle(rig, n=90):
    out = []
    for f in range(n):
        w = 2 * math.pi * f / n
        prm = {"neck.flex": -4.0 + 2.0 * math.sin(w), "head.flex": 4.0, "head.side": 6.0 * math.sin(w + 1.0),
               "neck.side": 3.0 * math.sin(w + 1.0)}
        prm["tail.lift"] = 6.0 * CA.smooth_pulse(f, n * 0.55, 3, 2, 5) - 6.0 * CA.smooth_pulse(f, n * 0.7, 3, 1, 5)
        prm["tail.side"] = 10.0 * CA.smooth_pulse(f, n * 0.62, 3, 1, 5)
        out.append(_ear_flicks(_breath(prm, f, n), f, n, 3))
    return out


def graze_pose(rig) -> dict:
    if rig.species == "deer":
        return {"hips.flex": 7.0, "body.z": -0.035 * rig.s, "body.y": 0.02 * rig.s, "spine.flex": 3.0, "chest.flex": 6.0,
                "neck.flex": 66.0, "neck2.flex": 30.0, "head.flex": 4.0,
                "foot.FL.y": -0.07 * rig.s, "foot.FR.y": -0.02 * rig.s, "foot.FL.x": 0.015 * rig.s, "foot.FR.x": -0.015 * rig.s,
                "scap.FL": -6.0, "scap.FR": -4.0}
    return {"hips.flex": 10.0, "body.z": -0.012 * rig.s, "neck.flex": 28.0, "neck2.flex": 14.0, "head.flex": 22.0}


def act_graze(rig, n=120):
    base = graze_pose(rig)
    out = []
    for f in range(n):
        prm = dict(base)
        w = 2 * math.pi * f / n
        chew = 0.5 + 0.5 * math.sin(w * 8)
        prm["jaw.open"] = 5.0 * chew
        prm["head.side"] = 8.0 * math.sin(w)
        prm["neck.side"] = 5.0 * math.sin(w)
        prm["head.twist"] = 6.0 * math.sin(w * 2 + 0.3)
        # a pluck: the muzzle tugs up and back twice a loop
        for at in (0.2, 0.68):
            p = CA.smooth_pulse(f, n * at, 4, 2, 8)
            prm["neck2.flex"] = prm.get("neck2.flex", 0.0) - 6.0 * p
            prm["head.flex"] = prm.get("head.flex", 0.0) - 10.0 * p
        prm["tail.lift"] = 3.0 * math.sin(w * 2)
        out.append(_ear_flicks(_breath(prm, f, n, 0.7), f, n, 9, base_out=10.0))
    return out


def alert_pose(rig) -> dict:
    if rig.species == "deer":
        return {"neck.flex": -16.0, "neck2.flex": -8.0, "head.flex": 10.0, "hips.flex": -1.5, "tail.lift": 18.0,
                "ear.L.fwd": 22.0, "ear.R.fwd": 22.0, "ear.L.out": -8.0, "ear.R.out": -8.0}
    # the hare sits up on its haunches, ears straight up
    return {"hips.flex": -32.0, "body.z": 0.03 * rig.s, "body.y": 0.025 * rig.s, "spine.flex": -10.0, "chest.flex": -6.0,
            "neck.flex": -12.0, "head.flex": 26.0, "ear.L.fwd": 30.0, "ear.R.fwd": 30.0, "ear.L.out": -16.0, "ear.R.out": -16.0,
            "foot.FL.z": 0.035 * rig.s, "foot.FR.z": 0.035 * rig.s, "foot.FL.y": 0.03 * rig.s, "foot.FR.y": 0.03 * rig.s,
            "foot.FL.can": 40.0, "foot.FR.can": 40.0, "foot.FL.hoof": 70.0, "foot.FR.hoof": 70.0}


def act_alert(rig, n=60):
    """Head up, ears forward, frozen; a deer stamps a fore hoof once, a hare's nose twitches."""
    base = alert_pose(rig)
    out = []
    for f in range(n):
        prm = dict(base)
        w = 2 * math.pi * f / n
        prm["head.side"] = 10.0 * math.sin(w)
        prm["neck.side"] = 4.0 * math.sin(w)
        if rig.species == "deer":
            st = CA.smooth_pulse(f, n * 0.35, 5, 2, 6)
            prm["foot.FR.z"] = 0.09 * rig.s * st
            prm["foot.FR.y"] = -0.03 * rig.s * st
            prm["foot.FR.can"] = 60.0 * st
            prm["foot.FR.hoof"] = 30.0 * st
        else:
            prm["jaw.open"] = 2.0 * (0.5 + 0.5 * math.sin(w * 10))
        out.append(_ear_flicks(_breath(prm, f, n, 1.4), f, n, 5, base_fwd=base.get("ear.L.fwd", 0.0),
                               base_out=base.get("ear.L.out", 0.0), amp=0.5))
    return out


def bed_pose(rig) -> dict:
    """Lying on the brisket, legs folded under (a deer) or tucked flat in its form (a hare)."""
    s = rig.s
    if rig.species == "deer":
        prm = {"body.z": -0.61 * s, "body.y": 0.03 * s, "hips.flex": -4.0, "hips.side": 0.0, "spine.flex": 2.0,
               "neck.flex": -8.0, "neck2.flex": -6.0, "head.flex": 14.0, "head.side": 12.0, "tail.lift": -4.0,
               "ear.L.out": 14.0, "ear.R.out": 14.0}
        # forelegs folded at the carpus: forearm forward along the ground, cannon back under it
        for k in ("FL", "FR"):
            prm[f"fk.{k}"] = 1.0
            prm[f"leg.{k}.0"] = 0.0
            prm[f"leg.{k}.1"] = 8.0
            prm[f"leg.{k}.1a"] = 6.0
            prm[f"leg.{k}.2"] = -88.0
            prm[f"leg.{k}.3"] = 165.0
            prm[f"leg.{k}.4"] = 15.0
        # hind legs: stifle forward along the belly, hock behind, cannon forward on the ground
        for k in ("HL", "HR"):
            prm[f"fk.{k}"] = 1.0
            prm[f"leg.{k}.1"] = -24.0
            prm[f"leg.{k}.1a"] = 34.0
            prm[f"leg.{k}.2"] = 132.0
            prm[f"leg.{k}.3"] = -122.0
            prm[f"leg.{k}.4"] = 0.0
        return prm
    return {"body.z": -0.045 * s, "body.y": 0.012 * s, "hips.flex": 4.0, "neck.flex": 14.0, "head.flex": -6.0,
            "ear.L.fwd": -55.0, "ear.R.fwd": -55.0, "ear.L.out": 6.0, "ear.R.out": 6.0,
            "foot.FL.y": -0.02 * s, "foot.FR.y": -0.02 * s, "foot.FL.can": 50.0, "foot.FR.can": 50.0,
            "foot.FL.hoof": 30.0, "foot.FR.hoof": 30.0}


def act_bed(rig, n=90):
    base = bed_pose(rig)
    out = []
    for f in range(n):
        prm = dict(base)
        w = 2 * math.pi * f / n
        prm["head.side"] = base.get("head.side", 0.0) + 4.0 * math.sin(w)
        out.append(_ear_flicks(_breath(prm, f, n, 1.2), f, n, 13, base_fwd=base.get("ear.L.fwd", 0.0),
                               base_out=base.get("ear.L.out", 0.0), amp=0.6))
    return out


def _blend(a: dict, b: dict, t: float) -> dict:
    """Pose blend; IK/FK switches happen at the midpoint (legs swap mode when folded enough)."""
    out = {}
    for k in set(a) | set(b):
        if k.startswith("fk."):
            out[k] = b.get(k, 0.0) if t > 0.5 else a.get(k, 0.0)
            continue
        out[k] = a.get(k, 0.0) * (1 - t) + b.get(k, 0.0) * t
    return out


def _ik_folded(rig, prm: dict) -> dict:
    """The IK equivalent of an FK-folded pose's lowered body: legs follow under the body."""
    return prm


def act_transition(rig, a: dict, b: dict, n: int, kind="inout"):
    return [_blend(a, b, ease(f / max(1, n - 1), kind)) for f in range(n)]


def act_bed_down(rig, n=45):
    """Fore knees first, then the hind end folds down."""
    stand = {}
    bed = bed_pose(rig)
    out = []
    for f in range(n):
        t = f / (n - 1)
        front = ease(min(1.0, t * 1.6))
        hind = ease(max(0.0, (t - 0.3) / 0.7))
        prm = _blend(stand, bed, (front + hind) * 0.5)
        prm["hips.flex"] = bed.get("hips.flex", 0.0) * hind + 14.0 * (front - hind) if rig.species == "deer" else prm["hips.flex"]
        out.append(prm)
    return out


def act_get_up(rig, n=36):
    """Hind end first (a deer rises rear-up), then the forelegs."""
    stand = {}
    bed = bed_pose(rig)
    out = []
    for f in range(n):
        t = f / (n - 1)
        hind = ease(min(1.0, t * 1.6))
        front = ease(max(0.0, (t - 0.35) / 0.65))
        prm = _blend(bed, stand, (front + hind) * 0.5)
        if rig.species == "deer":
            prm["hips.flex"] = -14.0 * (hind - front)
        out.append(prm)
    return out


def dead_pose(rig) -> dict:
    s = rig.s
    deer = rig.species == "deer"
    ctr = 0.83 if deer else 0.20
    rest_z = 0.17 if deer else 0.045
    prm = {"root.roll": 88.0, "neck.flex": 20.0 if deer else 10.0, "neck2.flex": -10.0, "head.flex": -20.0,
           "neck.side": -18.0, "head.side": -10.0, "jaw.open": 8.0, "tail.lift": -5.0,
           "ear.L.fwd": -30.0, "ear.R.fwd": -30.0}
    th = math.radians(88.0)
    # the trunk's centre (0, ctr) rolled about the root, then dropped to lie on the ground
    prm["body.x"] = -ctr * s * math.sin(th)
    prm["body.z"] = rest_z * s - ctr * s * math.cos(th)
    for k, a in (("FL", (0, 10, -15, 20, 10)), ("FR", (0, 25, -35, 40, 15)), ("HL", (0, -20, 20, -10, 10)), ("HR", (0, -35, 35, -25, 15))):
        prm[f"fk.{k}"] = 1.0
        for i, v in enumerate(a):
            prm[f"leg.{k}.{i}"] = float(v)
    return prm


def act_death(rig, n=40):
    """Legs buckle, the body drops and rolls onto its side; a few last kicks."""
    stand = {}
    dead = dead_pose(rig)
    out = []
    for f in range(n):
        t = f / (n - 1)
        prm = _blend(stand, dead, ease(min(1.0, t * 1.25), "in"))
        kick = CA.smooth_pulse(f, n * 0.82, 2, 1, 5)
        prm["leg.HL.2"] = prm.get("leg.HL.2", 0.0) + 25.0 * kick
        prm["leg.FR.2"] = prm.get("leg.FR.2", 0.0) - 18.0 * kick
        out.append(prm)
    return out


def act_hit(rig, n=12):
    out = []
    for f in range(n):
        p = CA.smooth_pulse(f, 0, 2, 1, n - 3)
        out.append({"body.z": -0.03 * rig.s * p, "hips.side": 6.0 * p, "neck.flex": -12.0 * p, "head.flex": -6.0 * p,
                    "tail.lift": 20.0 * p, "ear.L.fwd": -20.0 * p, "ear.R.fwd": -20.0 * p})
    return out


# --------------------------------------------------------------------------------------------
# The Hollowed hound (DESIGN §6): the Hollowed's action names (EnemyVisual plays them), a dog's
# gaits, and a starved, Bloom-ridden animal's way of holding itself: head carried low, shoulders
# up, tail clamped. Legs blend between IK and FK per leg (`blend.K`) so nothing pops when a leg
# folds or reaches; lying and falling poses are put on the ground by the hide itself (probes:
# a sample of skinned body vertices, posed by linear blend skinning).
# --------------------------------------------------------------------------------------------

GAITS["hound"] = {
    # lateral-sequence walk, the head swinging low
    "walk": {"phase": {"HL": 0.0, "FL": 0.25, "HR": 0.5, "FR": 0.75}, "duty": 0.62, "stride": 0.36, "lift": 0.075,
             "fold_f": 75.0, "fold_h": -28.0, "bob": 0.008, "bob_n": 2, "pitch": 1.2, "nod": 3.5, "neck": 0.0},
    # a slow, deliberate walk with the nose down on a scent
    "track": {"phase": {"HL": 0.0, "FL": 0.25, "HR": 0.5, "FR": 0.75}, "duty": 0.70, "stride": 0.24, "lift": 0.055,
              "fold_f": 60.0, "fold_h": -22.0, "bob": 0.005, "bob_n": 2, "pitch": 0.8, "nod": 1.5, "neck": 0.0},
    # rotary gallop: hind left, hind right, fore right, fore left; flexing hard through the back,
    # all four feet off the ground as the spine gathers
    "gallop": {"phase": {"HL": 0.0, "HR": 0.10, "FR": 0.46, "FL": 0.56}, "duty": 0.30, "stride": 0.62, "lift": 0.15,
               "fold_f": 115.0, "fold_h": -40.0, "bob": 0.07, "bob_n": 1, "pitch": 7.0, "nod": 4.0, "neck": 0.0,
               "spine": 14.0, "flight": True},
}


class Probes:
    """Skinned hide points (rest positions + weights) for grounding poses."""

    def __init__(self, skel, V: np.ndarray, W: np.ndarray, n: int = 900):
        step = max(1, len(V) // n)
        idx = np.arange(0, len(V), step)
        low = np.nonzero(V[:, 2] < 0.03 * float(skel.params.get("scale", 1.0)))[0]
        idx = np.unique(np.concatenate([idx, low]))
        self.V = V[idx]
        self.W = W[idx]
        self.bones = [i for i in range(W.shape[1]) if self.W[:, i].max() > 0.0]

    def posed(self, rig, prm: dict) -> np.ndarray:
        sk = rig.sk
        Q, off = rig.evaluate(prm)
        acc, pos = sk.fk(Q, off)
        out = np.zeros_like(self.V)
        for bi in self.bones:
            bn = sk.names[bi]
            w = self.W[:, bi:bi + 1]
            out += w * (pos[bn] + (self.V - sk.head[bn]) @ acc[bn].T)
        return out


def _ground(rig, prm: dict, center: float = 0.0, clearance: float = 0.0) -> dict:
    """Moves the body so the lowest point of the hide rests on the ground (and, by `center`, for
    a body lying on its side, its middle over the origin)."""
    pr = getattr(rig, "probes", None)
    if pr is None:
        return prm
    for _ in range(2):
        P = pr.posed(rig, prm)
        prm["body.z"] = prm.get("body.z", 0.0) - float(P[:, 2].min()) + clearance * rig.s
    if center > 0.0:
        P = pr.posed(rig, prm)
        prm["body.x"] = prm.get("body.x", 0.0) - center * 0.5 * float(P[:, 0].min() + P[:, 0].max())
    return prm


def hound_stance(rig) -> dict:
    """Head slung low, shoulders up, the tail clamped down between the legs, lips back."""
    s = rig.s
    return {"body.z": -0.014 * s, "hips.flex": -1.5, "neck.flex": 16.0, "neck2.flex": 4.0, "head.flex": -10.0,
            "tail.lift": -24.0, "tail2.lift": -10.0, "ear.L.fwd": -12.0, "ear.R.fwd": -12.0, "jaw.open": 3.0,
            "scap.FL": -3.0, "scap.FR": -3.0}


def _keys(base: dict, keys: list, n: int) -> list[dict]:
    k = CA.Keys(base, keys)
    return [k.at(f) for f in range(n)]


def _add(prm: dict, **kw) -> dict:
    for k, v in kw.items():
        k = k.replace("__", ".")
        prm[k] = prm.get(k, 0.0) + v
    return prm


def hound_idle(rig, n=90):
    """Standing, head low, panting hard through bared teeth; a twitch of the head once a loop."""
    base = hound_stance(rig)
    out = []
    for f in range(n):
        w = 2 * math.pi * f / n
        prm = dict(base)
        pant = 0.5 + 0.5 * math.sin(w * 9)
        prm["jaw.open"] = 9.0 + 9.0 * pant
        prm["chest.flex"] = 1.6 * math.sin(w * 9 - 0.6)
        prm["body.z"] += 0.0025 * rig.s * math.sin(w * 9 - 0.6)
        prm["head.flex"] += 1.5 * math.sin(w * 9)
        prm["neck.flex"] += 2.0 * math.sin(w)
        prm["neck.twist"] = 6.0 * math.sin(w) + 2.0 * math.sin(2 * w + 0.4)
        prm["head.twist"] = -4.0 * math.sin(w + 0.5)
        tw = CA.smooth_pulse(f, n * 0.58, 2, 3, 7)
        prm["head.side"] = 16.0 * tw
        prm["neck.twist"] -= 9.0 * tw
        prm["tail.side"] = 5.0 * math.sin(w)
        prm["hips.side"] = 1.0 * math.sin(w)
        out.append(_ear_flicks(prm, f, n, 17, base_fwd=base["ear.L.fwd"], amp=0.6))
    return out


def hound_walk(rig, n=20):
    base = hound_stance(rig)
    base["jaw.open"] = 8.0
    fr = gait_frames(rig, "walk", n, base)
    for f, prm in enumerate(fr):
        w = 2 * math.pi * f / n
        prm["neck.twist"] = 3.0 * math.sin(w)
        prm["tail.side"] = 6.0 * math.sin(w + 1.0)
    return fr


def hound_track(rig, n=30):
    """Nose to the ground, quartering for the scent: the head sweeps side to side, sniffing."""
    base = hound_stance(rig)
    base.update({"neck.flex": 44.0, "neck2.flex": 22.0, "head.flex": 18.0, "body.z": -0.03 * rig.s, "hips.flex": 3.0,
                 "chest.flex": 4.0, "jaw.open": 2.0, "tail.lift": -8.0, "scap.FL": -6.0, "scap.FR": -6.0})
    fr = gait_frames(rig, "track", n, base)
    for f, prm in enumerate(fr):
        w = 2 * math.pi * f / n
        prm["neck.twist"] = 14.0 * math.sin(w)
        prm["head.twist"] = 9.0 * math.sin(w + 0.4)
        prm["jaw.open"] = 2.0 + 2.5 * max(0.0, math.sin(w * 6)) ** 4
        prm["head.flex"] += 2.0 * math.sin(w * 6)
    return fr


def hound_run(rig, n=12):
    base = hound_stance(rig)
    base.update({"neck.flex": 8.0, "head.flex": -6.0, "jaw.open": 20.0, "tail.lift": 4.0, "tail2.lift": 8.0,
                 "ear.L.fwd": -45.0, "ear.R.fwd": -45.0, "body.z": -0.02 * rig.s})
    return gait_frames(rig, "gallop", n, base)


def hound_attack_a(rig, n=21):
    """Bite-lunge: gather, spring the front end forward, snap, shake, back off."""
    s = rig.s
    base = hound_stance(rig)
    crouch = {"body.z": -0.06 * s, "body.y": 0.04 * s, "hips.flex": 4.0, "neck.flex": 26.0, "head.flex": -16.0, "jaw.open": 8.0,
              "ear.L.fwd": -35.0, "ear.R.fwd": -35.0, "tail.lift": -30.0}
    lunge = {"body.z": 0.01 * s, "body.y": -0.13 * s, "hips.flex": -3.0, "spine.flex": -4.0, "chest.flex": -3.0, "neck.flex": -2.0,
             "neck2.flex": -4.0, "head.flex": 4.0, "jaw.open": 46.0, "foot.FL.y": -0.15 * s, "foot.FR.y": -0.09 * s,
             "ear.L.fwd": -40.0, "ear.R.fwd": -40.0}
    bite = dict(lunge, **{"jaw.open": 0.0, "head.flex": 10.0, "neck.flex": 2.0, "body.y": -0.11 * s})
    hold = dict(bite, **{"body.y": -0.08 * s, "neck.flex": 8.0, "body.z": 0.0})
    fr = _keys(base, [(0, {}), (5, crouch, "inout"), (10, lunge, "snap"), (12, bite, "snap"), (16, hold), (n - 1, {}, "inout")], n)
    for f, prm in enumerate(fr):
        sh = CA.smooth_pulse(f, 12, 1, 3, 2)
        prm["head.side"] = prm.get("head.side", 0.0) + 18.0 * sh * math.sin((f - 12) * 2.4)
        prm["neck.twist"] = prm.get("neck.twist", 0.0) + 10.0 * sh * math.sin((f - 12) * 2.4 + 0.5)
        # a paw lifts as it steps into the lunge
        prm["foot.FL.z"] = 0.05 * s * math.sin(math.pi * min(1.0, max(0.0, (f - 5) / 6.0)))
        prm["foot.FL.can"] = 50.0 * math.sin(math.pi * min(1.0, max(0.0, (f - 5) / 6.0)))
    return fr


def _reach_front(prm, w: float, upper: float, fore: float, past: float, paw: float, spread: float = 0.0):
    """Both forelegs off the ground (FK): reaching, raking, paws turned down, claws out."""
    for k, sx in (("FL", 1.0), ("FR", -1.0)):
        prm[f"blend.{k}"] = w
        prm[f"leg.{k}.1"] = upper
        prm[f"leg.{k}.1a"] = spread
        prm[f"leg.{k}.2"] = fore
        prm[f"leg.{k}.3"] = past
        prm[f"leg.{k}.4"] = paw
    return prm


def hound_attack_b(rig, n=27):
    """A leaping maul: gather low, launch up onto the hind legs with the forelegs reaching, the
    jaws closing at a standing man's chest, raking down, and dropping back onto all fours."""
    s = rig.s
    base = hound_stance(rig)
    crouch = {"body.z": -0.085 * s, "body.y": 0.05 * s, "hips.flex": 5.0, "neck.flex": 30.0, "head.flex": -24.0, "jaw.open": 10.0,
              "ear.L.fwd": -40.0, "ear.R.fwd": -40.0, "tail.lift": -10.0, "foot.HL.can": -8.0, "foot.HR.can": -8.0}
    apex = {"hips.flex": -40.0, "body.z": 0.15 * s, "body.y": -0.12 * s, "spine.flex": -6.0, "chest.flex": -4.0,
            "neck.flex": -10.0, "neck2.flex": -4.0, "head.flex": 22.0, "jaw.open": 48.0, "tail.lift": 25.0, "tail2.lift": 10.0,
            "foot.HL.can": 34.0, "foot.HR.can": 34.0, "foot.HL.hoof": -45.0, "foot.HR.hoof": -45.0,
            "foot.HL.y": -0.03 * s, "foot.HR.y": -0.02 * s, "ear.L.fwd": -50.0, "ear.R.fwd": -50.0}
    hit = dict(apex, **{"jaw.open": 0.0, "head.flex": 34.0, "neck.flex": -8.0, "body.y": -0.15 * s, "hips.flex": -38.0})
    tear = dict(hit, **{"hips.flex": -32.0, "body.z": 0.11 * s, "head.flex": 40.0, "neck.flex": 0.0})
    land = {"body.z": -0.05 * s, "body.y": -0.06 * s, "hips.flex": 2.0, "neck.flex": 22.0, "head.flex": -12.0, "jaw.open": 14.0,
            "foot.FL.y": -0.10 * s, "foot.FR.y": -0.06 * s}
    fr = _keys(base, [(0, {}), (6, crouch), (12, apex, "snap"), (15, hit, "snap"), (18, tear), (23, land, "in"),
                      (n - 1, {}, "inout")], n)
    for f, prm in enumerate(fr):
        # forelegs: off the ground from the launch to the landing
        w = CA.smooth_pulse(f, 7, 4, 9, 4)
        reach = min(1.0, max(0.0, (f - 7) / 5.0))
        rake = min(1.0, max(0.0, (f - 13) / 5.0))
        up = -52.0 * reach + 40.0 * rake
        _reach_front(prm, w, up, -35.0 * reach - 40.0 * rake, 25.0 * reach, 35.0 * reach, 6.0 * reach)
        sh = CA.smooth_pulse(f, 15, 1, 3, 2)
        prm["head.side"] = prm.get("head.side", 0.0) + 16.0 * sh * math.sin((f - 15) * 2.6)
    return fr


def hound_attack_structure(rig, n=30):
    """Clawing and digging at a door: reared half up against it, forepaws raking down it in turn,
    biting at the gap; the hind legs braced, the tail lashing."""
    s = rig.s
    out = []
    for f in range(n):
        w = 2 * math.pi * f / n
        prm = hound_stance(rig)
        prm.update({"hips.flex": -26.0 + 2.0 * math.sin(2 * w), "body.z": 0.03 * s, "body.y": -0.035 * s + 0.008 * s * math.sin(2 * w),
                    "spine.flex": -5.0, "chest.flex": -4.0, "neck.flex": -2.0 + 7.0 * math.sin(2 * w + 1.0), "head.flex": 26.0,
                    "jaw.open": 22.0 + 16.0 * math.sin(2 * w + 2.2), "head.side": 8.0 * math.sin(w), "neck.twist": 6.0 * math.sin(w + 0.5),
                    "tail.lift": 6.0, "tail.side": 18.0 * math.sin(w * 2), "tail2.side": 12.0 * math.sin(w * 2 - 0.7),
                    "ear.L.fwd": -30.0, "ear.R.fwd": -30.0,
                    "foot.HL.can": 12.0, "foot.HR.can": 12.0, "foot.HL.hoof": -14.0, "foot.HR.hoof": -14.0,
                    "foot.HL.y": 0.03 * s, "foot.HR.y": 0.03 * s})
        # each forepaw: up high on the door, raking down it, snatched back up; two strokes a
        # paw a loop, the paws half a stroke apart
        for k, ph in (("FL", 0.0), ("FR", 0.5)):
            u = (2 * f / n + ph) % 1.0
            rake = ease(u / 0.6) if u < 0.6 else 1.0 - ease((u - 0.6) / 0.4)
            prm[f"blend.{k}"] = 1.0
            prm[f"leg.{k}.1"] = -70.0 + 40.0 * rake
            prm[f"leg.{k}.1a"] = 4.0
            prm[f"leg.{k}.2"] = -30.0 - 35.0 * rake
            prm[f"leg.{k}.3"] = 15.0 + 30.0 * rake
            prm[f"leg.{k}.4"] = 40.0 + 25.0 * rake
        out.append(prm)
    return out


def hound_scream(rig, n=66):
    """The howl: a breath drawn in with the head down, then the head thrown back, muzzle to the
    sky, jaws wide; it holds, rising and wavering, then sinks."""
    base = hound_stance(rig)
    inhale = {"neck.flex": 30.0, "head.flex": -6.0, "chest.flex": 4.0, "body.z": -0.03 * rig.s, "jaw.open": 4.0}
    throw = {"neck.flex": -18.0, "neck2.flex": -4.0, "head.flex": -36.0, "jaw.open": 30.0, "chest.flex": -6.0, "hips.flex": -9.0,
             "body.z": 0.0, "ear.L.fwd": -50.0, "ear.R.fwd": -50.0, "tail.lift": -16.0, "scap.FL": 4.0, "scap.FR": 4.0}
    peak = dict(throw, **{"head.flex": -42.0, "neck2.flex": -8.0, "jaw.open": 34.0})
    fr = _keys(base, [(0, {}), (10, inhale), (20, throw, "snap"), (50, peak), (58, {"neck.flex": 12.0, "jaw.open": 8.0}),
                      (n - 1, {}, "inout")], n)
    for f, prm in enumerate(fr):
        held = CA.smooth_pulse(f, 18, 4, 30, 8)
        prm["jaw.open"] += held * (4.0 * math.sin(f * 1.7) + 2.0 * math.sin(f * 0.6))
        prm["head.flex"] += held * 2.0 * math.sin(f * 2.3)
        prm["neck.twist"] = prm.get("neck.twist", 0.0) + held * 3.0 * math.sin(f * 0.45)
        prm["chest.flex"] = prm.get("chest.flex", 0.0) - held * 1.5 * math.sin(f * 0.9)
    return fr


def hound_hit(rig, n=12, front=True):
    s = rig.s
    out = []
    for f in range(n):
        p = CA.smooth_pulse(f, 0, 2, 1, n - 4)
        prm = hound_stance(rig)
        if front:
            _add(prm, body__y=0.05 * s * p, body__z=-0.012 * s * p, hips__flex=-5.0 * p, neck__flex=-18.0 * p, head__flex=-16.0 * p,
                 head__side=12.0 * p, jaw__open=26.0 * p, tail__lift=-12.0 * p)
            prm["foot.FL.y"] = 0.03 * s * p
        else:
            _add(prm, body__y=-0.05 * s * p, body__z=-0.03 * s * p, hips__flex=-7.0 * p, neck__twist=26.0 * p, head__twist=16.0 * p,
                 neck__flex=-8.0 * p, jaw__open=22.0 * p, tail__lift=-20.0 * p)
            prm["foot.HL.y"] = -0.03 * s * p
        prm["ear.L.fwd"] -= 30.0 * p
        prm["ear.R.fwd"] -= 30.0 * p
        out.append(prm)
    return out


def hound_stagger(rig, n=24):
    """A lurch to the side: it reels, a fore and a hind foot stumble out to catch it, the head
    shaking, and it rights itself."""
    s = rig.s
    out = []
    for f in range(n):
        t = f / (n - 1)
        reel = math.sin(math.pi * t) ** 1.2
        prm = hound_stance(rig)
        _add(prm, body__x=0.05 * s * reel, body__z=-0.035 * s * reel, hips__side=-9.0 * reel, chest__side=-6.0 * reel,
             spine__twist=-8.0 * reel, neck__twist=-14.0 * reel, neck__flex=12.0 * reel)
        prm["head.side"] = 14.0 * reel * math.sin(f * 1.3)
        prm["jaw.open"] = 10.0 + 14.0 * reel
        for k, start, dx in (("FL", 3, 0.07), ("HL", 8, 0.06)):
            st = min(1.0, max(0.0, (f - start) / 6.0))
            back = min(1.0, max(0.0, (f - start - 10) / 6.0))
            pos = ease(st) - ease(back)
            prm[f"foot.{k}.x"] = dx * s * pos
            prm[f"foot.{k}.z"] = 0.05 * s * math.sin(math.pi * st) + 0.04 * s * math.sin(math.pi * back)
            prm[f"foot.{k}.can"] = 40.0 * (math.sin(math.pi * st) + math.sin(math.pi * back)) * (1 if k[0] == "F" else -0.5)
        out.append(prm)
    return out


def hound_dead(rig, side: float) -> dict:
    """Lying on its side (side +1: the left side down), legs loose, head on the ground, jaws
    agape."""
    prm = {"root.roll": 86.0 * side, "neck.flex": 4.0, "neck2.flex": -8.0, "head.flex": -14.0, "neck.twist": 8.0 * side,
           "head.side": -6.0 * side, "jaw.open": 22.0, "tail.lift": 4.0, "tail2.lift": 6.0, "spine.flex": -4.0,
           "ear.L.fwd": -20.0, "ear.R.fwd": -20.0}
    for k, a in (("FL", (0, -14, 12, 18, 25)), ("FR", (0, -30, 18, 22, 30)), ("HL", (0, -12, 26, -14, 30)),
                 ("HR", (0, -26, 34, -20, 34))):
        prm[f"blend.{k}"] = 1.0
        for i, v in enumerate(a):
            prm[f"leg.{k}.{i}"] = float(v)
    return prm


def hound_death(rig, n=40, front=True):
    """Shot from in front: it rears back, the forelegs buckle and it crashes over onto its left
    side. From behind: the hindquarters drop, the front scrabbles, and it rolls onto its right."""
    s = rig.s
    side = 1.0 if front else -1.0
    stand = hound_stance(rig)
    dead = hound_dead(rig, side)
    if front:
        jolt = {"body.y": 0.05 * s, "hips.flex": -12.0, "neck.flex": -24.0, "head.flex": -20.0, "jaw.open": 30.0}
        buckle = {"body.z": -0.20 * s, "hips.flex": 18.0, "neck.flex": 30.0, "head.flex": -10.0, "jaw.open": 24.0, "root.roll": 18.0 * side,
                  "blend.FL": 1.0, "blend.FR": 1.0, "leg.FL.1": 30.0, "leg.FL.2": -80.0, "leg.FL.3": 90.0, "leg.FR.1": 20.0,
                  "leg.FR.2": -60.0, "leg.FR.3": 70.0, "leg.FL.4": 20.0, "leg.FR.4": 20.0}
        keys = [(0, {}), (5, jolt, "snap"), (14, buckle, "in"), (26, dead, "in"), (n - 1, dead)]
    else:
        jolt = {"body.y": -0.04 * s, "body.z": -0.06 * s, "hips.flex": -16.0, "neck.flex": -10.0, "head.flex": -16.0, "jaw.open": 28.0,
                "neck.twist": 20.0, "tail.lift": -30.0}
        buckle = {"body.z": -0.16 * s, "hips.flex": -24.0, "neck.flex": -6.0, "jaw.open": 30.0, "root.roll": 12.0 * side,
                  "blend.HL": 1.0, "blend.HR": 1.0, "leg.HL.1": -60.0, "leg.HL.2": 110.0, "leg.HL.3": -90.0, "leg.HR.1": -55.0,
                  "leg.HR.2": 105.0, "leg.HR.3": -85.0, "neck.twist": 12.0, "tail.lift": -30.0}
        keys = [(0, {}), (5, jolt, "snap"), (14, buckle, "in"), (27, dead, "in"), (n - 1, dead)]
    fr = _keys(stand, keys, n)
    out = []
    for f, prm in enumerate(fr):
        for k in ("FL", "FR", "HL", "HR"):
            prm.setdefault(f"blend.{k}", 0.0)
        # the last kicks
        kick = CA.smooth_pulse(f, n * 0.74, 2, 1, 5)
        prm["leg.HL.2"] = prm.get("leg.HL.2", 0.0) + 28.0 * kick
        prm["leg.FR.2"] = prm.get("leg.FR.2", 0.0) - 20.0 * kick
        lying = min(1.0, max(0.0, (f - 10) / 16.0))
        out.append(_ground(rig, prm, center=ease(lying)))
    return out


def hound_curl(rig) -> dict:
    """Asleep, curled nose to tail: lying on its left side with the back rounded, forelegs folded,
    hind legs drawn up, the head tucked down to the paws and the tail wrapped round under it."""
    prm = {"root.roll": 80.0, "hips.flex": -8.0, "spine.flex": 24.0, "chest.flex": 24.0, "neck.flex": 42.0, "neck2.flex": 24.0,
           "head.flex": 18.0, "head.twist": -8.0, "jaw.open": 2.0, "tail.lift": -55.0, "tail2.lift": -50.0,
           "ear.L.fwd": -10.0, "ear.R.fwd": -10.0}
    for k, a in (("FL", (0, 40, -4, -105, 115, 30)), ("FR", (0, 30, 6, -95, 100, 30)),
                 ("HL", (0, -88, -4, 118, -70, 30)), ("HR", (0, -78, 8, 110, -62, 30))):
        prm[f"blend.{k}"] = 1.0
        prm[f"leg.{k}.0"] = float(a[0])
        prm[f"leg.{k}.1"] = float(a[1])
        prm[f"leg.{k}.1a"] = float(a[2])
        prm[f"leg.{k}.2"] = float(a[3])
        prm[f"leg.{k}.3"] = float(a[4])
        prm[f"leg.{k}.4"] = float(a[5])
    return prm


def hound_sleep(rig, n=90):
    """Two slow breaths a loop; dreaming: a forepaw paddles and the lips twitch once."""
    base = _ground(rig, hound_curl(rig), center=1.0)
    out = []
    for f in range(n):
        w = 2 * math.pi * f / n
        prm = dict(base)
        prm["chest.flex"] = prm.get("chest.flex", 0.0) + 1.4 * math.sin(2 * w)
        prm["spine.flex"] = prm.get("spine.flex", 0.0) + 0.8 * math.sin(2 * w - 0.4)
        d = CA.smooth_pulse(f, n * 0.45, 3, 2, 6)
        prm["leg.FL.2"] += 14.0 * d * math.sin(f * 1.6)
        prm["leg.FL.4"] += 10.0 * d
        prm["jaw.open"] += 5.0 * CA.smooth_pulse(f, n * 0.7, 2, 1, 4)
        prm["ear.L.fwd"] += -12.0 * CA.smooth_pulse(f, n * 0.2, 2, 1, 4)
        prm["tail2.side"] = prm.get("tail2.side", 0.0) + 4.0 * math.sin(w)
        out.append(prm)
    return out


def hound_wake(rig, n=36):
    """Up from the curl: the head comes up, it rolls up onto its chest, the forelegs push the front
    end up, then the hind end rises."""
    curl = _ground(rig, hound_curl(rig), center=1.0)
    stand = hound_stance(rig)
    for k in ("FL", "FR", "HL", "HR"):
        stand[f"blend.{k}"] = 0.0
    head_up = dict(curl, **{"neck.twist": 10.0, "neck2.twist": 0.0, "head.twist": 0.0, "head.side": 0.0, "neck.flex": -12.0,
                            "head.flex": 4.0, "jaw.open": 6.0, "tail.side": 30.0, "tail2.side": 20.0})
    sternal = dict(head_up, **{"root.roll": 6.0, "hips.twist": 0.0, "spine.twist": 4.0, "chest.twist": 2.0, "neck.twist": 0.0,
                               "spine.flex": 0.0, "chest.flex": 0.0, "body.x": 0.0})
    # sitting up on the folded hind legs, the forelegs straight
    front_up = dict(sternal, **{"root.roll": 0.0, "blend.FL": 0.0, "blend.FR": 0.0, "hips.flex": -30.0, "body.y": 0.06 * rig.s,
                                "body.z": -0.30 * rig.s, "neck.flex": 4.0, "head.flex": -6.0})
    fr = _keys(curl, [(0, {}), (8, head_up), (16, sternal), (26, front_up), (n - 1, stand, "inout")], n)
    out = []
    for prm in fr:
        out.append(_ground(rig, prm))
    return out


def hound_eat(rig, n=60):
    """Head down over a kill, a forepaw pinning it: it bites in, braces and tears a strip away
    with a shake of the head, gulps, and goes back down."""
    s = rig.s
    out = []
    for f in range(n):
        w = 2 * math.pi * f / n
        prm = hound_stance(rig)
        prm.update({"body.z": -0.05 * s, "body.y": 0.02 * s, "hips.flex": 5.0, "neck.flex": 52.0, "neck2.flex": 24.0, "head.flex": 20.0,
                    "foot.FL.y": -0.10 * s, "foot.FL.z": 0.035 * s, "foot.FL.can": 30.0, "foot.FL.hoof": 20.0,
                    "foot.FR.x": -0.02 * s, "foot.FR.y": -0.03 * s, "tail.lift": -14.0})
        for at in (0.0, 0.5):
            u = ((f / n) - at) % 1.0
            pull = math.sin(math.pi * min(1.0, u / 0.32)) if u < 0.32 else 0.0
            # the jaws open wide just before each bite (u 0.35..0.5 of a half-loop), clamped while it tears
            gape = math.sin(math.pi * (u - 0.35) / 0.15) ** 2 if 0.35 <= u < 0.5 else 0.0
            _add(prm, neck__flex=-20.0 * pull, head__flex=-18.0 * pull, body__y=0.035 * s * pull, hips__flex=-4.0 * pull)
            prm["neck.twist"] = prm.get("neck.twist", 0.0) + 12.0 * pull * math.sin(u * n * 1.9)
            prm["head.side"] = prm.get("head.side", 0.0) + 14.0 * pull * math.sin(u * n * 1.9 + 0.6)
            prm["jaw.open"] = prm.get("jaw.open", 0.0) + 26.0 * gape
        prm["jaw.open"] = max(2.0, prm["jaw.open"] + 4.0 * max(0.0, math.sin(w * 8)))
        out.append(prm)
    return out


HOUND_ACTIONS = [
    ("idle", 90, True, hound_idle),
    ("walk", 20, True, hound_walk),
    ("run", 12, True, hound_run),
    ("track", 30, True, hound_track),
    ("attack_a", 21, False, hound_attack_a),
    ("attack_b", 27, False, hound_attack_b),
    ("attack_structure", 30, True, hound_attack_structure),
    ("scream", 66, False, hound_scream),
    ("hit_front", 12, False, lambda r, n: hound_hit(r, n, True)),
    ("hit_back", 12, False, lambda r, n: hound_hit(r, n, False)),
    ("stagger", 24, False, hound_stagger),
    ("death_front", 40, False, lambda r, n: hound_death(r, n, True)),
    ("death_back", 40, False, lambda r, n: hound_death(r, n, False)),
    ("idle_sleep_lie", 90, True, hound_sleep),
    ("wake_lie", 36, False, hound_wake),
    ("eat", 60, True, hound_eat),
]


def actions_table(species: str):
    """name, frames, loop, builder(rig, n). Locomotion frame counts set the cycle time."""
    if species == "hound":
        return HOUND_ACTIONS
    common = [
        ("idle", 90, True, act_idle),
        ("graze", 120, True, act_graze),
        ("alert", 60, True, act_alert),
        ("bed", 90, True, act_bed),
        ("bed_down", 40, False, act_bed_down),
        ("get_up", 32, False, act_get_up),
        ("death", 36, False, act_death),
        ("hit", 12, False, act_hit),
    ]
    if species == "deer":
        return common + [
            ("walk", 34, True, lambda r, n: gait_frames(r, "walk", n)),
            ("trot", 18, True, lambda r, n: gait_frames(r, "trot", n)),
            ("gallop", 14, True, lambda r, n: gait_frames(r, "gallop", n, {"tail.lift": 40.0, "neck.flex": -6.0})),
        ]
    return common + [
        ("walk", 20, True, lambda r, n: gait_frames(r, "hop", n)),
        ("gallop", 11, True, lambda r, n: gait_frames(r, "bound", n, {"ear.L.fwd": -40.0, "ear.R.fwd": -40.0})),
    ]


def build_all(arm_obj, skel, params: dict, only=None, probes=None) -> dict:
    """probes: a hound's Probes (skinned hide points) for grounding lying poses."""
    rig = QuadRig(skel, params)
    if probes is not None:
        rig.probes = probes
    lengths = {}
    for name, nf, loop, fn in actions_table(rig.species):
        if only and name not in only:
            continue
        frames = fn(rig, nf)
        baked = []
        for prm in frames:
            Q, off = rig.evaluate(prm)
            # Blender keys the pelvis offset in its parent's posed frame: undo the root's roll
            baked.append((Q, Q["root"].T @ off))
        CA.write_action(arm_obj, skel, name, baked)
        lengths[name] = nf / FPS
    arm_obj.animation_data.action = None
    for pb in arm_obj.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    return lengths
