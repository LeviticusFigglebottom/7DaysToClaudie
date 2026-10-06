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
from .char_skel import _n, rot_axis

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
        Q["jaw"] = R(X, -g("jaw.open"))
        Q["tail"] = R(Z, g("tail.side")) @ R(X, -g("tail.lift"))
        for sd, sx in (("L", 1.0), ("R", -1.0)):
            Q[f"ear.{sd}"] = R(Z, sx * g(f"ear.{sd}.out")) @ R(X, -g(f"ear.{sd}.fwd"))
        off = np.array([g("body.x"), g("body.y"), g("body.z")])
        for key, (sd, bones, mid, fet, toe) in LEGS.items():
            front = key[0] == "F"
            if front:
                Q[bones[0]] = R(X, g(f"scap.{key}"))
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


def actions_table(species: str):
    """name, frames, loop, builder(rig, n). Locomotion frame counts set the cycle time."""
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


def build_all(arm_obj, skel, params: dict, only=None) -> dict:
    rig = QuadRig(skel, params)
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
