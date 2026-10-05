"""Procedural animation library for the Hollowed (and helpers shared with the FP arms).

Every action is built from *pose parameters* (anatomical angles in degrees, offsets in metres)
that are keyed / generated per frame, converted to bone rotations in rest-axes space (see
char_skel) and finally written as Blender actions (one key per frame, 30 fps, in place).

Pose parameter names (missing = base pose value):
  hips.x/y/z (armature-space offset), hips|spine|chest|neck|head .flex/.side/.twist
  jaw.open, shoulder.S.shrug/.fwd, upper_arm.S.flex/.abd/.twist, forearm.S.flex/.twist,
  hand.S.flex/.dev, legs either FK (thigh.S.flex/.abd/.twist, shin.S.flex, foot.S.pitch,
  toe.S.bend) or IK (ik.S = 1 with foot.S.x/y/z ankle offsets from rest, foot.S.pitch,
  foot.S.pivot = 0 ankle | 1 ball | -1 heel), arm IK (aik.S = 1, hand.S.tx/ty/tz absolute target).
Sides S in (L, R). Signs: flex = forward bend / raise forward / knee bend; abd = away from body.
"""
from __future__ import annotations

import math

import numpy as np

from .char_skel import BONE_NAMES, Skeleton, _n, rot_axis

FPS = 30
X = np.array([1.0, 0.0, 0.0])
Y = np.array([0.0, 1.0, 0.0])
Z = np.array([0.0, 0.0, 1.0])
SIDES = (("L", 1.0), ("R", -1.0))


def R(axis, deg):
    return rot_axis(axis, math.radians(deg))


def ease(t, kind="inout"):
    t = min(1.0, max(0.0, t))
    if kind == "lin":
        return t
    if kind == "in":
        return t * t
    if kind == "out":
        return 1 - (1 - t) * (1 - t)
    if kind == "snap":    # fast start, soft settle
        return 1 - (1 - t) ** 3
    return t * t * (3 - 2 * t)


def smooth_pulse(f, start, attack, hold, release):
    """0..1 envelope: rises over `attack` frames from `start`, holds, falls over `release`."""
    if f < start:
        return 0.0
    if f < start + attack:
        return ease((f - start) / attack, "snap")
    if f < start + attack + hold:
        return 1.0
    if f < start + attack + hold + release:
        return 1.0 - ease((f - start - attack - hold) / release)
    return 0.0


class Keys:
    """Key poses -> per-frame interpolation. keys: list of (frame, dict, easing)."""

    def __init__(self, base: dict, keys: list):
        self.base = base
        self.keys = sorted(keys, key=lambda k: k[0])

    def at(self, f: float) -> dict:
        ks = self.keys
        names = set(self.base)
        for _, d, *_ in ks:
            names |= set(d)
        out = {}
        for n in names:
            pts = [(k[0], k[1].get(n, self.base.get(n, 0.0)), k[2] if len(k) > 2 else "inout") for k in ks]
            if f <= pts[0][0]:
                out[n] = pts[0][1]
                continue
            if f >= pts[-1][0]:
                out[n] = pts[-1][1]
                continue
            for (f0, v0, _), (f1, v1, e1) in zip(pts[:-1], pts[1:]):
                if f0 <= f <= f1:
                    t = (f - f0) / max(f1 - f0, 1e-6)
                    out[n] = v0 + (v1 - v0) * ease(t, e1)
                    break
        return out


# --------------------------------------------------------------------------------------------
# Pose evaluation
# --------------------------------------------------------------------------------------------

class Rig:
    def __init__(self, skel: Skeleton, params: dict):
        self.sk = skel
        self.p = params
        j = skel.j
        self.s = float(params.get("height", 1.75)) / 1.75
        self.ankle = {sd: j[f"ankle.{sd}"].copy() for sd, _ in SIDES}
        self.ball = {sd: j[f"ball.{sd}"].copy() for sd, _ in SIDES}
        self.heel = {sd: j[f"heel.{sd}"].copy() for sd, _ in SIDES}
        self.leg_len = {sd: skel.length(f"thigh.{sd}") + skel.length(f"shin.{sd}") for sd, _ in SIDES}
        self.hip_z = j["hip.L"][2]
        self.pel_z = float(skel.head["hips"][2])

    def Q_from(self, prm: dict):
        sk = self.sk
        g = lambda k: float(prm.get(k, 0.0))  # noqa: E731
        Q = {}
        for b in ("hips", "spine", "chest", "neck", "head"):
            Q[b] = R(Z, g(f"{b}.twist")) @ R(Y, g(f"{b}.side")) @ R(X, g(f"{b}.flex"))
        Q["jaw"] = R(X, g("jaw.open"))
        for sd, sx in SIDES:
            Q[f"shoulder.{sd}"] = R(Z, -sx * g(f"shoulder.{sd}.fwd")) @ R(Y, -sx * g(f"shoulder.{sd}.shrug"))
            ua = f"upper_arm.{sd}"
            Q[ua] = R(X, -g(f"{ua}.flex")) @ R(Y, -sx * g(f"{ua}.abd")) @ R(sk.axis(ua), sx * g(f"{ua}.twist"))
            fa = f"forearm.{sd}"
            Q[fa] = R(sk.rest[fa][:, 0], g(f"{fa}.flex")) @ R(sk.axis(fa), sx * g(f"{fa}.twist"))
            hd = f"hand.{sd}"
            Q[hd] = R(sk.rest[hd][:, 0], -g(f"{hd}.flex")) @ R(sk.rest[hd][:, 2], sx * g(f"{hd}.dev"))
            th = f"thigh.{sd}"
            Q[th] = R(X, -g(f"{th}.flex")) @ R(Y, -sx * g(f"{th}.abd")) @ R(sk.axis(th), -sx * g(f"{th}.twist"))
            Q[f"shin.{sd}"] = R(X, g(f"shin.{sd}.flex"))
            Q[f"foot.{sd}"] = R(X, -g(f"foot.{sd}.pitch"))
            Q[f"toe.{sd}"] = R(X, -g(f"toe.{sd}.bend"))
        return Q

    def evaluate(self, prm: dict):
        """-> (Q dict, hips offset) with IK applied."""
        sk = self.sk
        Q = self.Q_from(prm)
        off = np.array([prm.get("hips.x", 0.0), prm.get("hips.y", 0.0), prm.get("hips.z", 0.0)])
        hips_rot = Q["hips"]
        for sd, sx in SIDES:
            if prm.get(f"ik.{sd}", 0.0) > 0.5:
                pitch = float(prm.get(f"foot.{sd}.pitch", 0.0))
                pivot = float(prm.get(f"foot.{sd}.pivot", 0.0))
                yaw = float(prm.get(f"foot.{sd}.yaw", 0.0))
                o = np.array([prm.get(f"foot.{sd}.x", 0.0), prm.get(f"foot.{sd}.y", 0.0), prm.get(f"foot.{sd}.z", 0.0)])
                anc = self.ankle[sd]
                Rf = R(Z, yaw) @ R(X, -pitch)
                if pivot > 0.5:      # roll about the ball of the foot (heel off)
                    piv = np.array([self.ball[sd][0], self.ball[sd][1], 0.0])
                elif pivot < -0.5:   # roll about the heel (toes up at heel strike)
                    piv = np.array([self.heel[sd][0], self.heel[sd][1] + 0.0, 0.0])
                else:
                    piv = anc
                target = piv + Rf @ (anc - piv) + o
                pole = hips_rot @ _n(np.array([sx * 0.18, -1.0, 0.0]))
                pole = R(Z, yaw * 0.5) @ pole
                if f"knee.{sd}.pz" in prm:
                    cust = np.array([prm.get(f"knee.{sd}.px", 0.0), prm.get(f"knee.{sd}.py", 0.0), prm[f"knee.{sd}.pz"]])
                    mag = float(np.linalg.norm(cust))
                    pole = _n(cust + pole * max(0.0, 1.0 - mag))
                sk.solve_two_bone(Q, f"thigh.{sd}", f"shin.{sd}", target, pole, off, z_sign=1.0)
                acc, _ = sk.fk(Q, off)
                O_foot = Rf @ sk.rest[f"foot.{sd}"]
                Q[f"foot.{sd}"] = acc[f"shin.{sd}"].T @ O_foot @ sk.rest[f"foot.{sd}"].T
                tb = float(prm.get(f"toe.{sd}.bend", 0.0))
                Q[f"toe.{sd}"] = R(X, -tb)
            if prm.get(f"aik.{sd}", 0.0) > 0.5:
                tgt = np.array([prm[f"hand.{sd}.tx"], prm[f"hand.{sd}.ty"], prm[f"hand.{sd}.tz"]])
                pole_v = np.array([prm.get(f"elbow.{sd}.px", sx * 0.6), prm.get(f"elbow.{sd}.py", 0.6),
                                   prm.get(f"elbow.{sd}.pz", 0.3)])
                sk.solve_two_bone(Q, f"upper_arm.{sd}", f"forearm.{sd}", tgt, _n(pole_v), off, z_sign=-1.0)
                # keep the hand's own flex relative to the forearm
                hd = f"hand.{sd}"
                Q[hd] = R(sk.rest[hd][:, 0], -float(prm.get(f"{hd}.flex", 0.0)))
        return Q, off


# --------------------------------------------------------------------------------------------
# Base poses
# --------------------------------------------------------------------------------------------

def base_stand(p: dict) -> dict:
    """The Hollowed's idle stance (all actions start/end near this)."""
    hunch = float(p.get("hunch", 0.2))
    tilt = float(p.get("head_tilt", 6.0))
    arm_raise = float(p.get("arm_raise", 0.0))     # one arm half-raised (reaching)
    raise_side = p.get("raise_side", "R")
    b = {
        "hips.z": -0.028, "hips.flex": 4.0,
        "spine.flex": 5.0 + 4 * hunch, "chest.flex": 6.0 + 6 * hunch, "neck.flex": 6.0, "head.flex": -10.0 - 4 * hunch,
        "head.side": tilt, "head.twist": 4.0, "jaw.open": 5.0 + float(p.get("jaw_base", 0.0)),
    }
    for sd, sx in SIDES:
        b.update({
            f"shoulder.{sd}.fwd": 7.0, f"shoulder.{sd}.shrug": -3.0 + (3.0 if sd == "L" else -2.0) * hunch,
            f"upper_arm.{sd}.abd": -36.0, f"upper_arm.{sd}.flex": 8.0, f"upper_arm.{sd}.twist": -8.0,
            f"forearm.{sd}.flex": 16.0, f"forearm.{sd}.twist": 0.0,
            f"hand.{sd}.flex": 14.0, f"hand.{sd}.dev": 0.0,
            f"ik.{sd}": 1.0, f"foot.{sd}.x": 0.0, f"foot.{sd}.y": 0.0, f"foot.{sd}.z": 0.0,
        })
    level_head(b, p, float(p.get("gaze_down", 8.0)))
    if arm_raise > 0:
        sd = raise_side
        b[f"upper_arm.{sd}.flex"] += 45.0 * arm_raise
        b[f"upper_arm.{sd}.abd"] += 8.0 * arm_raise
        b[f"forearm.{sd}.flex"] += 25.0 * arm_raise
        b[f"hand.{sd}.flex"] += 10.0 * arm_raise
    return b


def level_head(prm: dict, p: dict, down_deg: float, strength: float = 1.0) -> dict:
    """Gaze stabilisation: sets head.flex so the head's world pitch is `down_deg` (chin down)
    whatever the trunk lean (rest-pose posture included). Twitch offsets added afterwards stay."""
    hunch = float(p.get("hunch", 0.0))
    hf = float(p.get("head_forward", 0.0))
    rest_pitch = 6.0 * hunch + 2.0 * hf
    trunk = sum(float(prm.get(k, 0.0)) for k in ("hips.flex", "spine.flex", "chest.flex", "neck.flex"))
    want = down_deg - trunk - rest_pitch
    prm["head.flex"] = prm.get("head.flex", 0.0) * (1 - strength) + want * strength
    return prm


def merged(*ds):
    out = {}
    for d in ds:
        out.update(d)
    return out


def add(prm: dict, delta: dict, w: float = 1.0) -> dict:
    out = dict(prm)
    for k, v in delta.items():
        out[k] = out.get(k, 0.0) + v * w
    return out


class Noise1D:
    """Smooth deterministic 1-D noise (sum of incommensurate sines with seeded phases)."""

    def __init__(self, seed: int, n: int = 3):
        r = np.random.default_rng(seed)
        self.ph = r.uniform(0, 2 * math.pi, n)
        self.fr = r.uniform(0.6, 1.6, n)

    def __call__(self, t: float, freq: float = 1.0) -> float:
        return float(sum(math.sin(t * freq * f * 2 * math.pi + ph) for f, ph in zip(self.fr, self.ph)) / len(self.fr))


def loop_noise(seed, f, n_frames, cycles=(1, 2, 3)):
    """Seamless noise over a loop: sum of integer-cycle sines with seeded phases."""
    r = np.random.default_rng(seed)
    v = 0.0
    for c in cycles:
        v += math.sin(2 * math.pi * c * f / n_frames + r.uniform(0, 2 * math.pi)) / c
    return v / sum(1.0 / c for c in cycles)


# --------------------------------------------------------------------------------------------
# Gait
# --------------------------------------------------------------------------------------------

def gait_foot(p_phase, stance, travel, lift, shuffle=0.0, kick=0.0):
    """Ankle offset (y, z) + pitch + pivot for one foot. p_phase in [0,1): 0 = heel strike.
    stance: fraction in contact; travel: stance displacement (m, front->back)."""
    if p_phase < stance:
        u = p_phase / stance
        y = -travel / 2 + travel * u
        z = 0.0
        # heel strike: toes up then flat; toe-off: heel rises (pivot ball)
        if u < 0.15:
            pitch = 12.0 * (1 - u / 0.15) * (1 - shuffle)
            pivot = -1.0
        elif u > 0.75:
            pitch = -22.0 * ease((u - 0.75) / 0.25, "in") * (1 - 0.6 * shuffle)
            pivot = 1.0
        else:
            pitch, pivot = 0.0, 0.0
        return y, z, pitch, pivot
    u = (p_phase - stance) / (1 - stance)
    e = ease(u, "inout")
    y = travel / 2 - travel * e
    z = lift * math.sin(math.pi * u) ** 0.9 + kick * math.sin(math.pi * min(1.0, u * 1.6)) ** 2 * (u < 0.62)
    pitch = -22.0 * (1 - ease(u / 0.35)) + 14.0 * ease((u - 0.6) / 0.4) if u > 0.0 else -22.0
    pitch = pitch * (1 - shuffle) - 25.0 * shuffle
    return y, z, pitch, (1.0 if u < 0.2 else 0.0)


def locomotion(rig: Rig, p: dict, n: int, speed: float, kind: str):
    """walk / walk_b / run frames."""
    base = base_stand(p)
    out = []
    cyc = n / FPS
    limp = p.get("limp_side", "R")
    seed = int(p.get("seed", 1))
    nz = [Noise1D(seed + i) for i in range(6)]
    for f in range(n + 1):
        ph = (f / n) % 1.0
        prm = dict(base)
        if kind == "run":
            stance = {"L": 0.34, "R": 0.32}
            lift = {"L": 0.13, "R": 0.11}
            kick = {"L": 0.22, "R": 0.18}
            shuffle = {"L": 0.0, "R": 0.0}
        elif kind == "walk_b":
            stance = {"L": 0.62, "R": 0.62}
            lift = {"L": 0.07, "R": 0.07}
            kick = {"L": 0.0, "R": 0.0}
            shuffle = {"L": 0.0, "R": 0.0}
            drag = limp
            lift[drag] = 0.004
            shuffle[drag] = 1.0
        else:
            stance = {"L": 0.62, "R": 0.62}
            lift = {"L": 0.075, "R": 0.075}
            kick = {"L": 0.0, "R": 0.0}
            shuffle = {"L": 0.0, "R": 0.0}
            stance[limp] = 0.57
            lift[limp] = 0.035
            shuffle[limp] = 0.35
        for sd, sx in SIDES:
            pp = (ph + (0.0 if sd == "L" else 0.5)) % 1.0
            travel = speed * cyc * stance[sd]
            y, z, pitch, pivot = gait_foot(pp, stance[sd], travel, lift[sd], shuffle[sd], kick[sd])
            prm[f"foot.{sd}.y"] = y
            prm[f"foot.{sd}.z"] = z
            prm[f"foot.{sd}.pitch"] = pitch
            prm[f"foot.{sd}.pivot"] = pivot
            prm[f"foot.{sd}.x"] = sx * (0.012 if kind != "walk_b" or sd != limp else 0.05)
            if kind == "walk_b" and sd == limp:
                prm[f"foot.{sd}.yaw"] = sx * 18.0     # dragged foot turned out
                prm[f"foot.{sd}.pitch"] = -14.0 if pp >= stance[sd] else prm[f"foot.{sd}.pitch"] * 0.4
                prm[f"foot.{sd}.pivot"] = 1.0 if pp >= stance[sd] else prm[f"foot.{sd}.pivot"]
            if kind == "run":
                prm[f"toe.{sd}.bend"] = max(0.0, -pitch) * 0.6
        w = 2 * math.pi * ph
        if kind == "run":
            prm["hips.z"] = -0.075 + 0.035 * math.cos(2 * w + 0.6)
            prm["hips.x"] = 0.012 * math.sin(w)
            prm["hips.flex"] = 14.0
            prm["hips.twist"] = 9.0 * math.sin(w)
            prm["spine.flex"] = 12.0 + 3 * math.cos(2 * w)
            prm["chest.flex"] = 14.0 + 4 * math.cos(2 * w + 0.5)
            prm["chest.twist"] = -11.0 * math.sin(w)
            prm["neck.flex"] = -6.0
            prm["head.flex"] = -14.0 + 5 * math.cos(2 * w + 1.0)
            prm["jaw.open"] = 16.0 + 8 * math.sin(2 * w)
            for sd, sx in SIDES:
                ws = w + (0.0 if sd == "L" else math.pi)
                prm[f"upper_arm.{sd}.flex"] = 30.0 - 55.0 * math.sin(ws) + 6 * nz[0](f / FPS)
                prm[f"upper_arm.{sd}.abd"] = -18.0 + 10 * math.cos(ws)
                prm[f"forearm.{sd}.flex"] = 55.0 + 25 * math.sin(ws + 0.6)
                prm[f"hand.{sd}.flex"] = 20.0
                prm[f"shoulder.{sd}.fwd"] = 10.0 - 8 * math.sin(ws)
        else:
            dip = 0.0
            if kind == "walk":
                # body dips onto the limping leg's stance
                lp = (ph + (0.0 if limp == "L" else 0.5)) % 1.0
                dip = 0.022 * math.sin(math.pi * min(1.0, lp / stance[limp])) if lp < stance[limp] else 0.0
            if kind == "walk_b":
                lp = (ph + (0.0 if limp == "L" else 0.5)) % 1.0
                dip = 0.03 * math.sin(math.pi * min(1.0, lp / stance[limp])) if lp < stance[limp] else 0.0
            lsx = 1.0 if limp == "L" else -1.0
            prm["hips.z"] = -0.040 - 0.012 * math.cos(2 * w) - dip
            prm["hips.x"] = 0.022 * math.sin(w) + lsx * 0.010
            prm["hips.flex"] = 6.0
            prm["hips.twist"] = 6.0 * math.sin(w)
            prm["hips.side"] = 3.5 * math.sin(w + 0.3) + lsx * dip * 120
            prm["spine.flex"] = base["spine.flex"] + 3.0
            prm["spine.side"] = -2.5 * math.sin(w) - lsx * dip * 80
            prm["chest.twist"] = -6.0 * math.sin(w) + 2 * nz[1](f / FPS)
            prm["chest.flex"] = base["chest.flex"] + 4.0 + 2.0 * math.cos(2 * w + 0.7)
            prm["chest.side"] = -lsx * dip * 70
            prm["head.flex"] = base["head.flex"] + 4.0 * math.cos(2 * w + 1.4)
            prm["head.twist"] = base["head.twist"] + 4.0 * math.sin(w + 0.8)
            arm_raise = float(p.get("arm_raise", 0.0))
            for sd, sx in SIDES:
                ws = w + (0.0 if sd == "L" else math.pi)
                amp = 16.0 if kind == "walk" else 10.0
                if sd == p.get("raise_side", "R") and arm_raise > 0:
                    amp *= 0.4
                prm[f"upper_arm.{sd}.flex"] = base[f"upper_arm.{sd}.flex"] - amp * math.sin(ws - 0.5)
                prm[f"upper_arm.{sd}.abd"] = base[f"upper_arm.{sd}.abd"] + 3.0 * math.cos(ws)
                prm[f"forearm.{sd}.flex"] = base[f"forearm.{sd}.flex"] + 8.0 + 8.0 * math.sin(ws - 1.1)
                prm[f"hand.{sd}.flex"] = base[f"hand.{sd}.flex"] + 6.0 * math.sin(ws - 1.6)
            if kind == "walk_b":
                # balance arm out wide on the good side, dragged side shoulder hiked
                good = "L" if limp == "R" else "R"
                prm[f"upper_arm.{good}.abd"] += 14.0
                prm[f"shoulder.{limp}.shrug"] = base[f"shoulder.{limp}.shrug"] + 8.0
                prm["head.side"] = base["head.side"] - lsx * 10.0
        bob = prm.get("head.flex", 0.0) - base.get("head.flex", 0.0)
        level_head(prm, p, float(p.get("gaze_down", 8.0)) + (2.0 if kind == "run" else 4.0))
        prm["head.flex"] += 0.5 * bob
        out.append(prm)
    return out


# --------------------------------------------------------------------------------------------
# Actions
# --------------------------------------------------------------------------------------------

def act_idle(rig, p, n=90):
    base = base_stand(p)
    seed = int(p.get("seed", 1))
    frames = []
    tw1, tw2 = 18 + seed % 9, 55 + seed % 11
    for f in range(n + 1):
        w = 2 * math.pi * f / n
        prm = dict(base)
        prm["hips.x"] = 0.014 * math.sin(w)
        prm["hips.y"] = 0.006 * math.sin(2 * w + 0.4)
        prm["hips.z"] = base["hips.z"] - 0.006 * (0.5 + 0.5 * math.cos(2 * w))
        prm["hips.side"] = 2.2 * math.sin(w + 0.3)
        prm["spine.side"] = -1.8 * math.sin(w + 0.6)
        prm["chest.flex"] = base["chest.flex"] + 1.6 * math.sin(2 * w)          # breathing
        prm["chest.twist"] = 3.0 * loop_noise(seed, f, n)
        prm["neck.flex"] = base["neck.flex"] + 2.0 * loop_noise(seed + 1, f, n)
        prm["head.twist"] = base["head.twist"] + 6.0 * loop_noise(seed + 2, f, n)
        prm["jaw.open"] = base["jaw.open"] + 4.0 * (0.5 + 0.5 * math.sin(3 * w))
        # twitches (head jerk, shoulder hitch)
        t1 = smooth_pulse(f, tw1, 2, 3, 10)
        t2 = smooth_pulse(f, tw2, 2, 2, 12)
        prm["head.twist"] += 16.0 * t1 - 9.0 * t2
        prm["head.side"] = base["head.side"] + 10.0 * t1 + 6.0 * t2
        prm["head.flex"] = base["head.flex"] - 8.0 * t2
        prm["shoulder.L.shrug"] = base["shoulder.L.shrug"] + 9.0 * smooth_pulse(f, tw2 + 3, 2, 3, 9)
        for sd, sx in SIDES:
            lag = w - 0.9
            prm[f"upper_arm.{sd}.flex"] = base[f"upper_arm.{sd}.flex"] + 2.5 * math.sin(2 * lag)
            prm[f"upper_arm.{sd}.abd"] = base[f"upper_arm.{sd}.abd"] - sx * 2.5 * math.sin(lag)
            prm[f"forearm.{sd}.flex"] = base[f"forearm.{sd}.flex"] + 3.0 * math.sin(2 * lag + 0.5)
            prm[f"foot.{sd}.x"] = 0.0
        frames.append(prm)
    return frames


def act_sleep_stand(rig, p, n=90):
    base = base_stand(p)
    pose = merged(base, {"neck.flex": 24.0, "head.flex": 12.0, "head.side": 14.0, "chest.flex": base["chest.flex"] + 8,
                         "spine.flex": base["spine.flex"] + 4, "jaw.open": 12.0,
                         "shoulder.L.shrug": -8.0, "shoulder.R.shrug": -8.0, "shoulder.L.fwd": 12.0, "shoulder.R.fwd": 12.0,
                         "upper_arm.L.abd": -38.0, "upper_arm.R.abd": -38.0, "upper_arm.L.flex": 4.0,
                         "upper_arm.R.flex": 4.0, "forearm.L.flex": 8.0, "forearm.R.flex": 8.0, "hips.z": -0.035})
    seed = int(p.get("seed", 1))
    frames = []
    for f in range(n + 1):
        w = 2 * math.pi * f / n
        prm = dict(pose)
        prm["hips.x"] = 0.018 * math.sin(w)
        prm["hips.y"] = 0.010 * math.sin(w + 1.2)
        prm["hips.side"] = 2.6 * math.sin(w + 0.4)
        prm["chest.flex"] = pose["chest.flex"] + 1.2 * math.sin(2 * w)
        prm["head.side"] = pose["head.side"] + 3.0 * math.sin(w + 2.0)
        prm["head.twist"] = 4.0 * loop_noise(seed + 5, f, n)
        for sd, sx in SIDES:
            prm[f"upper_arm.{sd}.flex"] = pose[f"upper_arm.{sd}.flex"] + 3.0 * math.sin(w - 1.0 + (0 if sd == "L" else 0.4))
            prm[f"upper_arm.{sd}.abd"] = pose[f"upper_arm.{sd}.abd"] - sx * 2.5 * math.sin(w - 1.2)
        frames.append(prm)
    return frames


LIE_Y = 0.45     # pelvis this far behind the origin when lying / sitting, so that getting up
SIT_Y = 0.30     # ends with the feet on the origin (in-place animations, no root motion)
# Seated on a chair, pew, booth or bench (ADR-0022): the origin is on the floor under the feet, the
# pelvis SEAT_Y behind it with the buttocks on a seat SEAT_H high. The game lifts the body by
# (seat height - SEAT_H) for taller seats (stools) and reads both constants from
# data/config/traps.json "sleepers" (keep them in step).
SEAT_H = 0.46
SEAT_Y = 0.40


def lie_pose(rig, p):
    """Lying on the back (sleeper, on the floor or a bed): IK legs extended along the ground, knees
    up-pole, the left hand on the belly and the right arm along the side, so the body fits a cot."""
    d = {"hips.z": -rig.pel_z + 0.12, "hips.y": LIE_Y, "hips.flex": -88.0,
         "spine.flex": 2.0, "chest.flex": 0.0, "neck.flex": 14.0, "head.flex": -4.0, "head.twist": 26.0, "head.side": 6.0,
         "jaw.open": 16.0}
    ext = rig.leg_len["L"] * 0.97
    for sd, sx in SIDES:
        d.update({f"ik.{sd}": 1.0, f"foot.{sd}.x": sx * 0.05, f"foot.{sd}.y": LIE_Y - ext - rig.ankle[sd][1],
                  f"foot.{sd}.z": 0.0, f"foot.{sd}.pitch": 62.0 if sd == "L" else 50.0, f"foot.{sd}.pivot": -1.0,
                  f"foot.{sd}.yaw": sx * (14.0 if sd == "L" else 26.0),
                  f"knee.{sd}.px": sx * 0.5, f"knee.{sd}.py": -0.2, f"knee.{sd}.pz": 1.0,
                  f"shoulder.{sd}.shrug": 6.0, f"shoulder.{sd}.fwd": -4.0,
                  f"hand.{sd}.flex": 24.0})
    d.update({"upper_arm.L.flex": -10.0, "upper_arm.L.abd": -40.0, "upper_arm.L.twist": 60.0, "forearm.L.flex": 100.0,
              "upper_arm.R.flex": -20.0, "upper_arm.R.abd": -40.0, "upper_arm.R.twist": 20.0, "forearm.R.flex": 10.0})
    return d


def sit_pose(rig, p):
    """Slumped sitting on the ground (back against a wall), one leg out, one knee up."""
    d = {"hips.z": -rig.pel_z + 0.125, "hips.y": SIT_Y, "hips.flex": -14.0, "spine.flex": 18.0, "chest.flex": 18.0,
         "chest.side": 6.0, "neck.flex": 30.0, "head.flex": 10.0, "head.side": 20.0, "head.twist": -12.0, "jaw.open": 14.0}
    ext = rig.leg_len["L"] * 0.99
    d.update({"ik.L": 1.0, "foot.L.x": 0.07, "foot.L.y": SIT_Y - ext - rig.ankle["L"][1], "foot.L.z": 0.0,
              "foot.L.pitch": 58.0, "foot.L.pivot": -1.0, "foot.L.yaw": 18.0,
              "knee.L.px": 0.4, "knee.L.py": -0.2, "knee.L.pz": 1.0,
              "ik.R": 1.0, "foot.R.x": -0.05, "foot.R.y": SIT_Y - ext * 0.60 - rig.ankle["R"][1], "foot.R.z": 0.0,
              "foot.R.pitch": 0.0, "foot.R.pivot": 0.0, "foot.R.yaw": -10.0,
              "knee.R.px": -0.45, "knee.R.py": -0.3, "knee.R.pz": 1.0})
    # The left hand rests on the floor beside the outstretched leg (hanging straight it went 0.2 m
    # through the floor); the right forearm lies over the raised knee.
    for sd, sx in SIDES:
        d.update({f"shoulder.{sd}.shrug": -6.0, f"shoulder.{sd}.fwd": 12.0,
                  f"upper_arm.{sd}.abd": -12.0 if sd == "L" else -22.0, f"upper_arm.{sd}.flex": 0.0 if sd == "L" else 28.0,
                  f"upper_arm.{sd}.twist": -10.0, f"forearm.{sd}.flex": 64.0 if sd == "L" else 34.0,
                  f"hand.{sd}.flex": 22.0})
    _lift_hand(rig, d, "R", 0.0)
    return _lift_hand(rig, d, "L", 0.0)


def _hand_low(rig, prm: dict, sd: str) -> float:
    """Height of the lowest point of a hand (wrist or fingertips) in a pose."""
    Q, off = rig.evaluate(prm)
    acc, pos = rig.sk.fk(Q, off)
    tip = rig.sk.point(acc, pos, f"hand.{sd}", rig.sk.tail[f"hand.{sd}"])
    return min(float(tip[2]), float(pos[f"hand.{sd}"][2]))


def _lift_hand(rig, prm: dict, sd: str, floor: float = 0.02, hi: float = 130.0) -> dict:
    """Bends the forearm (FK) just enough that the hand clears the floor. Poses are authored on an
    average body; long-armed ones (the Rammer, Lurchers) hung their hands through the floor."""
    key = f"forearm.{sd}.flex"
    if _hand_low(rig, prm, sd) >= floor:
        return prm
    a, b = float(prm.get(key, 0.0)), hi
    for _ in range(14):
        m = (a + b) * 0.5
        prm[key] = m
        if _hand_low(rig, prm, sd) >= floor:
            b = m
        else:
            a = m
    prm[key] = b
    return prm


def seat_pose(rig, p):
    """Slumped on a chair, pew, booth or bench (ADR-0022): pelvis on a seat SEAT_H high and SEAT_Y
    behind the feet (planted on the floor at the origin), back against the backrest, head lolled,
    the right hand in the lap and the left on the left thigh (nothing sticks out sideways into a
    neighbouring seat or a booth wall)."""
    d = {"hips.z": -rig.pel_z + SEAT_H + 0.125, "hips.y": SEAT_Y, "hips.flex": -18.0, "spine.flex": 12.0, "chest.flex": 14.0,
         "chest.side": -4.0, "neck.flex": 30.0, "head.flex": 12.0, "head.side": 26.0, "head.twist": 12.0, "jaw.open": 16.0}
    for sd, sx in SIDES:
        d.update({f"ik.{sd}": 1.0, f"foot.{sd}.x": sx * 0.05, f"foot.{sd}.y": -0.06 if sd == "L" else 0.02, f"foot.{sd}.z": 0.0,
                  f"foot.{sd}.pitch": 0.0, f"foot.{sd}.pivot": 0.0, f"foot.{sd}.yaw": sx * 12.0,
                  f"knee.{sd}.px": sx * 0.35, f"knee.{sd}.py": -1.0, f"knee.{sd}.pz": 0.3,
                  f"shoulder.{sd}.shrug": -6.0, f"shoulder.{sd}.fwd": 10.0})
    d.update({"upper_arm.L.flex": 15.0, "upper_arm.L.abd": -36.0, "upper_arm.L.twist": -8.0, "forearm.L.flex": 45.0, "hand.L.flex": 10.0,
              "upper_arm.R.flex": 20.0, "upper_arm.R.abd": -48.0, "upper_arm.R.twist": 0.0, "forearm.R.flex": 45.0, "hand.R.flex": 16.0})
    return d


def hunch_pose(rig, p):
    """Hunched forward on a backless seat (stool, mess bench): the seat pose leaning over the knees,
    elbows on the thighs, forearms and hands hanging past the knees, head down."""
    d = seat_pose(rig, p)
    d.update({"hips.y": SEAT_Y - 0.03, "hips.flex": 4.0, "spine.flex": 14.0, "chest.flex": 20.0, "chest.side": 3.0,
              "neck.flex": 24.0, "head.flex": 20.0, "head.side": -10.0, "head.twist": -8.0, "jaw.open": 18.0})
    for sd, sx in SIDES:
        d.update({f"upper_arm.{sd}.flex": 35.0, f"upper_arm.{sd}.abd": -30.0, f"upper_arm.{sd}.twist": -6.0,
                  f"forearm.{sd}.flex": 60.0, f"hand.{sd}.flex": 30.0, f"shoulder.{sd}.fwd": 16.0})
    return d


def crouch_pose(rig, p):
    """Squatting low on the balls of the feet (an ambusher waiting), knees wide, arms hanging with
    the knuckles on the floor, head down."""
    base = base_stand(p)
    d = merged(base, {"hips.z": -0.50, "hips.y": 0.10, "hips.flex": 34.0, "spine.flex": 18.0, "chest.flex": 16.0,
                      "neck.flex": 16.0, "head.flex": 4.0, "head.side": 9.0, "head.twist": -6.0, "jaw.open": 13.0})
    for sd, sx in SIDES:
        d.update({f"ik.{sd}": 1.0, f"foot.{sd}.x": sx * 0.05, f"foot.{sd}.y": 0.02 if sd == "L" else -0.04, f"foot.{sd}.z": 0.0,
                  f"foot.{sd}.pitch": -22.0, f"foot.{sd}.pivot": 1.0, f"foot.{sd}.yaw": sx * 16.0,
                  f"knee.{sd}.px": sx * 0.55, f"knee.{sd}.py": -0.8, f"knee.{sd}.pz": 0.1,
                  f"shoulder.{sd}.shrug": -8.0, f"shoulder.{sd}.fwd": 14.0,
                  f"upper_arm.{sd}.flex": 34.0, f"upper_arm.{sd}.abd": -44.0, f"upper_arm.{sd}.twist": -6.0,
                  f"forearm.{sd}.flex": 30.0, f"hand.{sd}.flex": 24.0})
    for sd, _ in SIDES:
        _lift_hand(rig, d, sd, 0.0)
    return d


def kneel_pose(rig, p):
    """Kneeling upright but sagging: knees on the floor, shins along it behind with the tops of the
    feet down, head bowed, arms hanging."""
    base = base_stand(p)
    th = rig.sk.length("thigh.L")
    sh = rig.sk.length("shin.L")
    d = merged(base, {"hips.z": -rig.pel_z + 0.06 + th * 0.97 + 0.04, "hips.y": 0.02, "hips.flex": 8.0, "spine.flex": 14.0,
                      "chest.flex": 18.0, "neck.flex": 30.0, "head.flex": 16.0, "head.side": -12.0, "head.twist": 8.0, "jaw.open": 15.0})
    for sd, sx in SIDES:
        d.update({f"ik.{sd}": 1.0, f"foot.{sd}.x": sx * 0.01, f"foot.{sd}.y": sh * 0.97 - 0.02, f"foot.{sd}.z": 0.08,
                  f"foot.{sd}.pitch": -122.0, f"foot.{sd}.pivot": 0.0, f"foot.{sd}.yaw": sx * 4.0, f"toe.{sd}.bend": 10.0,
                  f"knee.{sd}.px": sx * 0.15, f"knee.{sd}.py": -1.0, f"knee.{sd}.pz": -0.4,
                  f"shoulder.{sd}.shrug": -10.0, f"shoulder.{sd}.fwd": 10.0,
                  f"upper_arm.{sd}.flex": 6.0, f"upper_arm.{sd}.abd": -32.0, f"upper_arm.{sd}.twist": -4.0,
                  f"forearm.{sd}.flex": 10.0, f"hand.{sd}.flex": 18.0})
    for sd, _ in SIDES:
        _lift_hand(rig, d, sd, 0.03)
    return d


def act_sleep_lie(rig, p, n=60):
    pose = lie_pose(rig, p)
    frames = []
    seed = int(p.get("seed", 1))
    for f in range(n + 1):
        w = 2 * math.pi * f / n
        prm = dict(pose)
        prm["chest.flex"] = pose["chest.flex"] - 0.9 * math.sin(w)       # shallow breathing
        prm["neck.flex"] = pose["neck.flex"] + 0.6 * math.sin(w + 0.5)
        prm["jaw.open"] = pose["jaw.open"] + 1.5 * math.sin(w)
        tw = smooth_pulse(f, 34 + seed % 8, 1, 1, 6)
        prm["forearm.R.flex"] = pose["forearm.R.flex"] + 6.0 * tw
        prm["hand.L.flex"] = pose["hand.L.flex"] + 12.0 * smooth_pulse(f, 12, 2, 2, 8)
        frames.append(prm)
    return frames


def act_sleep_sit(rig, p, n=60):
    pose = sit_pose(rig, p)
    frames = []
    for f in range(n + 1):
        w = 2 * math.pi * f / n
        prm = dict(pose)
        prm["chest.flex"] = pose["chest.flex"] + 1.2 * math.sin(w)
        prm["head.side"] = pose["head.side"] + 1.5 * math.sin(w + 1.0)
        prm["neck.flex"] = pose["neck.flex"] + 1.0 * math.sin(w + 0.3)
        prm["jaw.open"] = pose["jaw.open"] + 2.0 * math.sin(w)
        frames.append(prm)
    return frames


def _breathing(pose: dict, n: int, seed: int, head_sway: float = 1.5) -> list[dict]:
    """A dormant loop over a held pose: shallow breathing, a slow head sway, the jaw working, one
    finger twitch (seeded so bodies side by side don't breathe in step)."""
    frames = []
    ph = (seed % 7) * 0.7
    for f in range(n + 1):
        w = 2 * math.pi * f / n
        prm = dict(pose)
        prm["chest.flex"] = pose.get("chest.flex", 0.0) + 1.2 * math.sin(w + ph)
        prm["head.side"] = pose.get("head.side", 0.0) + head_sway * math.sin(w + 1.0 + ph)
        prm["neck.flex"] = pose.get("neck.flex", 0.0) + 1.0 * math.sin(w + 0.3 + ph)
        prm["jaw.open"] = pose.get("jaw.open", 0.0) + 2.0 * math.sin(w + ph)
        prm["hand.R.flex"] = pose.get("hand.R.flex", 0.0) + 10.0 * smooth_pulse(f, 20 + seed % 13, 2, 2, 8)
        frames.append(prm)
    return frames


def act_sleep_seat(rig, p, n=60):
    return _breathing(seat_pose(rig, p), n, int(p.get("seed", 1)))


def act_sleep_hunch(rig, p, n=60):
    return _breathing(hunch_pose(rig, p), n, int(p.get("seed", 1)) + 1, head_sway=2.0)


def act_sleep_crouch(rig, p, n=60):
    return _breathing(crouch_pose(rig, p), n, int(p.get("seed", 1)) + 3, head_sway=2.5)


def act_sleep_kneel(rig, p, n=60):
    return _breathing(kneel_pose(rig, p), n, int(p.get("seed", 1)) + 5, head_sway=2.0)


def act_wake_seat(rig, p, n=40, start=None):
    """Seated sleeper (feet planted on the origin) jerks its head up, leans forward over its knees,
    pushes off the seat and straightens: it ends standing where its feet were (no root motion).
    `start`: the seated pose it wakes from (seat_pose, or hunch_pose on a backless seat)."""
    base = base_stand(p)
    seat = start if start is not None else seat_pose(rig, p)
    pz = -rig.pel_z
    lift = merged(seat, {"neck.flex": 6.0, "head.flex": -12.0, "head.side": 4.0, "head.twist": 0.0, "chest.side": 0.0, "jaw.open": 24.0,
                         "hips.flex": -10.0})
    lean = merged(seat, {"hips.flex": 22.0, "spine.flex": 24.0, "chest.flex": 16.0, "neck.flex": -2.0, "head.flex": -24.0,
                         "head.side": 0.0, "head.twist": 0.0, "chest.side": 0.0, "jaw.open": 20.0,
                         "foot.L.y": 0.03, "foot.R.y": 0.05, "foot.L.x": 0.04, "foot.R.x": -0.04,
                         "upper_arm.L.flex": 36.0, "upper_arm.R.flex": 34.0, "upper_arm.L.abd": -30.0, "upper_arm.R.abd": -30.0,
                         "forearm.L.flex": 24.0, "forearm.R.flex": 24.0, "hand.L.flex": -20.0, "hand.R.flex": -20.0})
    push = merged(base, {"hips.z": pz + SEAT_H + 0.2, "hips.y": 0.17, "hips.flex": 38.0, "spine.flex": 26.0, "chest.flex": 16.0,
                         "neck.flex": -8.0, "head.flex": -26.0, "jaw.open": 18.0,
                         "foot.L.y": 0.03, "foot.R.y": 0.05, "foot.L.x": 0.04, "foot.R.x": -0.04,
                         "upper_arm.L.flex": 30.0, "upper_arm.R.flex": 28.0, "forearm.L.flex": 30.0, "forearm.R.flex": 30.0})
    rise = merged(base, {"hips.z": -0.12, "hips.y": 0.06, "hips.flex": 16.0, "spine.flex": 14.0, "chest.flex": 12.0,
                         "head.flex": -18.0, "head.twist": -10.0, "jaw.open": 14.0,
                         "foot.L.y": 0.012, "foot.R.y": 0.02})
    ks = Keys(base, [(0, seat), (6, lift, "snap"), (14, lean), (24, push, "inout"), (32, rise, "out"), (40, base, "inout")])
    frames = []
    for f in range(n + 1):
        prm = ks.at(f)
        for sd, _ in SIDES:
            prm[f"ik.{sd}"] = 1.0
            if f >= 14:   # default knee pole (pelvis forward) for the rise
                w = ease((f - 14) / 12.0)
                for c, v in (("px", 0.0), ("py", -1.0), ("pz", 0.0)):
                    prm[f"knee.{sd}.{c}"] = prm.get(f"knee.{sd}.{c}", 0.0) * (1 - w) + v * w
        frames.append(prm)
    return frames


def _foot_ik_pose(base, off_L=(0, 0, 0), off_R=(0, 0, 0)):
    d = {}
    for sd, o in (("L", off_L), ("R", off_R)):
        d.update({f"ik.{sd}": 1.0, f"foot.{sd}.x": o[0], f"foot.{sd}.y": o[1], f"foot.{sd}.z": o[2]})
    return d


def act_wake_lie(rig, p, n=40):
    """Sleeper on its back jerks up to sitting, drags the feet in, rocks over them and stands."""
    base = base_stand(p)
    lie = lie_pose(rig, p)
    pz = -rig.pel_z
    situp = merged(lie, {"hips.flex": -12.0, "hips.z": pz + 0.125, "spine.flex": 24.0, "chest.flex": 18.0, "neck.flex": 4.0,
                         "head.flex": -16.0, "head.twist": 0.0, "head.side": 0.0, "jaw.open": 24.0,
                         "upper_arm.L.flex": -28.0, "upper_arm.R.flex": -32.0, "upper_arm.L.abd": -26.0,
                         "upper_arm.R.abd": -26.0, "upper_arm.L.twist": 0.0, "upper_arm.R.twist": 0.0,
                         "forearm.L.flex": 6.0, "forearm.R.flex": 6.0, "hand.L.flex": -55.0, "hand.R.flex": -55.0})
    tuck = merged(situp, {"spine.flex": 34.0, "chest.flex": 26.0, "hips.flex": 4.0, "head.flex": -24.0,
                          "foot.L.y": 0.08 - rig.ankle["L"][1], "foot.R.y": 0.0 - rig.ankle["R"][1],
                          "foot.L.x": 0.03, "foot.R.x": -0.03, "foot.L.pitch": 0.0, "foot.R.pitch": 0.0,
                          "foot.L.pivot": 0.0, "foot.R.pivot": 0.0, "foot.L.yaw": 0.0, "foot.R.yaw": 0.0,
                          "knee.L.px": 0.3, "knee.L.py": -0.6, "knee.L.pz": 0.8,
                          "knee.R.px": -0.3, "knee.R.py": -0.6, "knee.R.pz": 0.8,
                          "upper_arm.L.flex": 20.0, "upper_arm.R.flex": 24.0, "hand.L.flex": -30.0, "hand.R.flex": -30.0})
    crouch = merged(base, {"hips.z": -0.44, "hips.y": 0.16, "hips.flex": 34.0, "spine.flex": 26.0, "chest.flex": 20.0,
                           "neck.flex": -6.0, "head.flex": -26.0, "jaw.open": 18.0,
                           "foot.L.y": tuck["foot.L.y"], "foot.R.y": tuck["foot.R.y"], "foot.L.x": 0.03, "foot.R.x": -0.03,
                           "upper_arm.L.flex": 30.0, "upper_arm.R.flex": 38.0, "forearm.L.flex": 40.0,
                           "forearm.R.flex": 30.0})
    rise = merged(base, {"hips.z": -0.10, "hips.y": 0.05, "hips.flex": 12.0, "spine.flex": 14.0, "chest.flex": 12.0,
                         "head.flex": -18.0, "head.twist": 12.0, "jaw.open": 14.0,
                         "foot.L.y": tuck["foot.L.y"] * 0.4, "foot.R.y": tuck["foot.R.y"] * 0.4})
    ks = Keys(base, [(0, lie), (10, situp, "snap"), (17, tuck), (26, crouch, "inout"), (34, rise, "out"),
                     (40, base, "inout")])
    frames = []
    for f in range(n + 1):
        prm = ks.at(f)
        for sd, _ in SIDES:
            prm[f"ik.{sd}"] = 1.0
            if f >= 26:   # default knee pole (pelvis forward) for the standing part
                w = ease((f - 26) / 8.0)
                for c, v in (("px", 0.0), ("py", -1.0), ("pz", 0.0)):
                    prm[f"knee.{sd}.{c}"] = prm.get(f"knee.{sd}.{c}", 0.0) * (1 - w) + v * w
        frames.append(prm)
    return frames


def act_wake_sit(rig, p, n=40):
    base = base_stand(p)
    sit = sit_pose(rig, p)
    pz = -rig.pel_z
    lift = merged(sit, {"head.side": 0.0, "neck.flex": 8.0, "head.flex": -14.0, "head.twist": 0.0, "chest.side": 0.0})
    lean = merged(sit, {"hips.flex": 18.0, "spine.flex": 30.0, "chest.flex": 24.0, "neck.flex": 0.0, "head.flex": -20.0,
                        "head.side": 0.0, "head.twist": 0.0, "chest.side": 0.0, "hips.z": pz + 0.15,
                        "foot.L.y": 0.08 - rig.ankle["L"][1], "foot.R.y": 0.0 - rig.ankle["R"][1],
                        "foot.L.x": 0.03, "foot.R.x": -0.03, "foot.L.pitch": 0.0, "foot.L.pivot": 0.0, "foot.L.yaw": 0.0,
                        "foot.R.yaw": 0.0, "knee.L.px": 0.3, "knee.L.py": -0.6, "knee.L.pz": 0.8,
                        "upper_arm.L.flex": 30.0, "upper_arm.R.flex": 36.0, "forearm.L.flex": 20.0, "forearm.R.flex": 20.0,
                        "jaw.open": 20.0})
    crouch = merged(base, {"hips.z": -0.42, "hips.y": 0.14, "hips.flex": 30.0, "spine.flex": 24.0, "chest.flex": 18.0,
                           "head.flex": -22.0, "jaw.open": 16.0, "upper_arm.L.flex": 24.0, "upper_arm.R.flex": 20.0,
                           "foot.L.y": lean["foot.L.y"], "foot.R.y": lean["foot.R.y"], "foot.L.x": 0.03, "foot.R.x": -0.03})
    rise = merged(base, {"hips.z": -0.08, "hips.y": 0.04, "head.twist": -10.0,
                         "foot.L.y": lean["foot.L.y"] * 0.4, "foot.R.y": lean["foot.R.y"] * 0.4})
    ks = Keys(base, [(0, sit), (6, lift, "snap"), (16, lean), (26, crouch), (34, rise), (40, base)])
    frames = []
    for f in range(n + 1):
        prm = ks.at(f)
        for sd, _ in SIDES:
            prm[f"ik.{sd}"] = 1.0
            if f >= 22:
                w = ease((f - 22) / 8.0)
                for c, v in (("px", 0.0), ("py", -1.0), ("pz", 0.0)):
                    prm[f"knee.{sd}.{c}"] = prm.get(f"knee.{sd}.{c}", 0.0) * (1 - w) + v * w
        frames.append(prm)
    return frames


def act_attack_a(rig, p, n=24):
    """Two-handed swipe: wind up high, rake down diagonally across, recover."""
    base = base_stand(p)
    feet = _foot_ik_pose(base, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    wind = merged(base, feet, {"hips.y": 0.05, "hips.z": -0.05, "hips.twist": -10.0, "spine.flex": -2.0, "chest.flex": -6.0,
                               "chest.twist": -16.0, "neck.flex": -4.0, "head.flex": -14.0, "jaw.open": 22.0,
                               "upper_arm.L.flex": 135.0, "upper_arm.L.abd": 10.0, "forearm.L.flex": 60.0,
                               "upper_arm.R.flex": 128.0, "upper_arm.R.abd": 22.0, "forearm.R.flex": 50.0,
                               "hand.L.flex": -20.0, "hand.R.flex": -20.0, "shoulder.L.shrug": 10.0, "shoulder.R.shrug": 12.0})
    strike = merged(base, feet, {"hips.y": -0.12, "hips.z": -0.10, "hips.twist": 12.0, "hips.flex": 14.0, "spine.flex": 18.0,
                                 "chest.flex": 22.0, "chest.twist": 18.0, "neck.flex": 0.0, "head.flex": -22.0, "jaw.open": 30.0,
                                 "upper_arm.L.flex": 28.0, "upper_arm.L.abd": -48.0, "forearm.L.flex": 18.0,
                                 "upper_arm.R.flex": 40.0, "upper_arm.R.abd": -34.0, "forearm.R.flex": 30.0,
                                 "hand.L.flex": 30.0, "hand.R.flex": 26.0, "shoulder.L.fwd": 20.0, "shoulder.R.fwd": 22.0})
    follow = merged(strike, {"chest.twist": 24.0, "upper_arm.L.flex": 4.0, "upper_arm.R.flex": 10.0, "upper_arm.L.abd": -55.0,
                             "upper_arm.R.abd": -40.0, "jaw.open": 12.0})
    ks = Keys(base, [(0, merged(base, feet)), (8, wind, "out"), (12, strike, "in"), (15, follow, "out"),
                     (24, merged(base, feet), "inout")])
    return [ks.at(f) for f in range(n + 1)]


def act_attack_b(rig, p, n=24):
    """Lunge-bite: coil, lunge forward with the head thrust and jaw snapping."""
    base = base_stand(p)
    feet = _foot_ik_pose(base)
    coil = merged(base, feet, {"hips.y": 0.06, "hips.z": -0.09, "spine.flex": 4.0, "chest.flex": 2.0, "neck.flex": -10.0,
                               "head.flex": -8.0, "jaw.open": 10.0, "upper_arm.L.flex": 40.0, "upper_arm.R.flex": 46.0,
                               "forearm.L.flex": 60.0, "forearm.R.flex": 64.0, "upper_arm.L.abd": -20.0, "upper_arm.R.abd": -18.0})
    lunge = merged(base, feet, {"hips.y": -0.20, "hips.z": -0.12, "hips.flex": 18.0, "spine.flex": 20.0, "chest.flex": 22.0,
                                "neck.flex": -18.0, "head.flex": -24.0, "jaw.open": 38.0,
                                "upper_arm.L.flex": 88.0, "upper_arm.R.flex": 92.0, "upper_arm.L.abd": -16.0,
                                "upper_arm.R.abd": -12.0, "forearm.L.flex": 30.0, "forearm.R.flex": 26.0,
                                "hand.L.flex": -10.0, "hand.R.flex": -10.0, "shoulder.L.fwd": 24.0, "shoulder.R.fwd": 24.0})
    bite = merged(lunge, {"jaw.open": 2.0, "head.flex": -14.0, "forearm.L.flex": 64.0, "forearm.R.flex": 66.0,
                          "hand.L.flex": 30.0, "hand.R.flex": 30.0, "hips.y": -0.18})
    ks = Keys(base, [(0, merged(base, feet)), (6, coil), (10, lunge, "snap"), (13, bite, "snap"), (16, bite),
                     (24, merged(base, feet))])
    return [ks.at(f) for f in range(n + 1)]


def act_attack_structure(rig, p, n=30):
    """Pounding a wall/door: alternating overhead hammer blows (loops)."""
    base = base_stand(p)
    feet = _foot_ik_pose(base, (0.0, 0.03, 0.0), (0.0, -0.06, 0.0))
    stance = merged(base, feet, {"hips.y": -0.03, "hips.z": -0.06, "hips.flex": 8.0, "spine.flex": 10.0, "chest.flex": 6.0,
                                 "head.flex": -16.0, "jaw.open": 18.0})
    frames = []
    for f in range(n + 1):
        prm = dict(stance)
        for sd, sx, hit in (("L", 1.0, 8), ("R", -1.0, 23)):
            # phase relative to the impact frame (loop-aware)
            t = ((f - hit + n / 2) % n) - n / 2          # -15..15, 0 = impact
            if t < 0:
                up = ease(min(1.0, (t + 15) / 11.0), "inout")
                raise_amt = up if t > -11 else ease((t + 15) / 4.0) * 0.6
            else:
                raise_amt = max(0.0, 1.0 - ease(t / 2.0, "snap")) * 0.0
            # raise (hand above the head) -> slam forward-down at impact
            r = raise_amt if t < 0 else 0.0
            slam = smooth_pulse(t + 15, 15, 1, 2, 9) if t >= 0 else 0.0
            prm[f"upper_arm.{sd}.flex"] = 40.0 + 110.0 * r + 10.0 * slam
            prm[f"upper_arm.{sd}.abd"] = -20.0 + 14.0 * r
            prm[f"forearm.{sd}.flex"] = 40.0 + 55.0 * r - 10 * slam
            prm[f"hand.{sd}.flex"] = 10.0 - 30 * r + 25 * slam
            prm[f"shoulder.{sd}.shrug"] = 4.0 + 10.0 * r
        imp = max(smooth_pulse(((f - 8) % n), 0, 1, 1, 6), smooth_pulse(((f - 23) % n), 0, 1, 1, 6))
        prm["chest.flex"] = stance["chest.flex"] + 8.0 * imp
        prm["spine.flex"] = stance["spine.flex"] + 4.0 * imp
        prm["hips.z"] = stance["hips.z"] - 0.02 * imp
        prm["chest.twist"] = 8.0 * math.sin(2 * math.pi * (f - 8) / n)
        prm["head.flex"] = stance["head.flex"] + 8.0 * imp
        prm["jaw.open"] = stance["jaw.open"] + 10.0 * imp
        frames.append(prm)
    return frames


def act_scream(rig, p, n=50):
    base = base_stand(p)
    feet = _foot_ik_pose(base)
    inhale = merged(base, feet, {"chest.flex": -6.0, "spine.flex": -2.0, "neck.flex": -8.0, "head.flex": -16.0, "jaw.open": 16.0,
                                 "shoulder.L.shrug": 10.0, "shoulder.R.shrug": 10.0, "shoulder.L.fwd": -6.0,
                                 "shoulder.R.fwd": -6.0, "upper_arm.L.abd": -26.0, "upper_arm.R.abd": -26.0, "hips.z": -0.04})
    scream = merged(base, feet, {"chest.flex": -12.0, "spine.flex": -6.0, "neck.flex": -24.0, "head.flex": -26.0, "jaw.open": 46.0,
                                 "shoulder.L.shrug": 6.0, "shoulder.R.shrug": 6.0, "shoulder.L.fwd": -14.0,
                                 "shoulder.R.fwd": -14.0, "upper_arm.L.abd": -12.0, "upper_arm.R.abd": -12.0,
                                 "upper_arm.L.flex": -12.0, "upper_arm.R.flex": -14.0, "forearm.L.flex": 40.0,
                                 "forearm.R.flex": 44.0, "hand.L.flex": -30.0, "hand.R.flex": -30.0, "hips.z": -0.06,
                                 "hips.y": 0.03})
    ks = Keys(base, [(0, merged(base, feet)), (12, inhale), (17, scream, "snap"), (40, scream), (50, merged(base, feet))])
    frames = []
    seed = int(p.get("seed", 1))
    for f in range(n + 1):
        prm = ks.at(f)
        shake = smooth_pulse(f, 16, 2, 22, 8)
        for i, k in enumerate(("chest.flex", "neck.flex", "head.side", "head.twist", "upper_arm.L.flex", "upper_arm.R.flex",
                               "jaw.open")):
            prm[k] = prm.get(k, 0.0) + shake * (2.2 if "jaw" not in k else 3.0) * math.sin(f * (2.1 + 0.37 * i) + seed + i)
        frames.append(prm)
    return frames


def act_hit(rig, p, n=14, front=True):
    base = base_stand(p)
    feet = _foot_ik_pose(base)
    sgn = -1.0 if front else 1.0
    frames = []
    for f in range(n + 1):
        prm = merged(base, feet)
        # damped spring response to an impulse at frame 0..2
        t = f / FPS
        a = math.exp(-t * 9.0) * math.sin(min(t * 24.0, math.pi * 0.5 + t * 14.0))
        lag = math.exp(-max(0.0, t - 0.04) * 8.0) * math.sin(max(0.0, t - 0.04) * 22.0)
        prm["hips.y"] = -sgn * 0.035 * a
        prm["spine.flex"] = base["spine.flex"] + sgn * 7.0 * a
        prm["chest.flex"] = base["chest.flex"] + sgn * 14.0 * a
        prm["neck.flex"] = base["neck.flex"] + sgn * 10.0 * lag
        prm["head.flex"] = base["head.flex"] + sgn * 16.0 * lag
        prm["head.twist"] = base["head.twist"] + 8.0 * lag
        prm["jaw.open"] = base["jaw.open"] + 14.0 * abs(lag)
        for sd, sx in SIDES:
            prm[f"upper_arm.{sd}.flex"] = base[f"upper_arm.{sd}.flex"] - sgn * 22.0 * lag
            prm[f"upper_arm.{sd}.abd"] = base[f"upper_arm.{sd}.abd"] + 12.0 * abs(lag)
            prm[f"forearm.{sd}.flex"] = base[f"forearm.{sd}.flex"] + 18.0 * abs(lag)
        frames.append(prm)
    # ease the last frames exactly back to the base pose
    for f in range(n - 3, n + 1):
        w = (f - (n - 4)) / 4.0
        frames[f] = {k: frames[f].get(k, 0.0) * (1 - w) + merged(base, feet).get(k, 0.0) * w
                     for k in set(frames[f]) | set(base)}
    return frames


def act_stagger(rig, p, n=30):
    base = base_stand(p)
    feet0 = _foot_ik_pose(base)
    k1 = merged(base, feet0, {"hips.y": 0.06, "hips.z": -0.05, "chest.flex": -14.0, "spine.flex": -4.0, "head.flex": -26.0,
                              "neck.flex": -8.0, "jaw.open": 26.0, "upper_arm.L.abd": -6.0, "upper_arm.R.abd": 4.0,
                              "upper_arm.L.flex": 30.0, "upper_arm.R.flex": 50.0, "forearm.L.flex": 30.0,
                              "forearm.R.flex": 40.0, "hips.side": -6.0, "chest.twist": 10.0})
    # left foot steps back to catch the fall
    k2 = merged(k1, _foot_ik_pose(base, (0.02, 0.26, 0.10), (0.0, 0.0, 0.0)),
                {"hips.y": 0.16, "hips.z": -0.08, "chest.flex": -6.0, "head.flex": -10.0, "hips.side": 4.0})
    k3 = merged(k1, _foot_ik_pose(base, (0.03, 0.30, 0.0), (0.0, 0.02, 0.0)),
                {"hips.y": 0.18, "hips.z": -0.11, "chest.flex": 14.0, "spine.flex": 10.0, "head.flex": -20.0,
                 "upper_arm.L.flex": 20.0, "upper_arm.R.flex": 26.0, "upper_arm.L.abd": -22.0, "upper_arm.R.abd": -20.0,
                 "jaw.open": 14.0, "chest.twist": -6.0, "hips.side": 2.0})
    k4 = merged(base, _foot_ik_pose(base, (0.01, 0.12, 0.09), (0.0, 0.0, 0.0)), {"hips.y": 0.06, "hips.z": -0.05})
    ks = Keys(base, [(0, merged(base, feet0)), (3, k1, "snap"), (9, k2), (14, k3, "out"), (22, k4), (30, merged(base, feet0))])
    frames = [ks.at(f) for f in range(n + 1)]
    for prm in frames:
        prm["foot.L.pitch"] = -10.0 * min(1.0, prm.get("foot.L.z", 0.0) / 0.05)
    return frames


def _fall(rig, p, forward: bool):
    pel_z = rig.pel_z
    sgn = 1.0 if forward else -1.0
    end = {"hips.flex": 86.0 * sgn, "hips.z": -pel_z + 0.11, "hips.y": -0.42 * sgn, "hips.twist": 8.0, "hips.side": 4.0,
           "spine.flex": -4.0 * sgn, "chest.flex": -6.0 * sgn, "neck.flex": (-20.0 if forward else 18.0),
           "head.twist": 60.0 if forward else 30.0, "head.flex": -10.0, "jaw.open": 24.0}
    for sd, sx in SIDES:
        end.update({f"ik.{sd}": 0.0, f"thigh.{sd}.flex": (-4.0 if forward else 10.0) + (6 if sd == "L" else -2),
                    f"thigh.{sd}.abd": 8.0, f"shin.{sd}.flex": 18.0 if sd == "L" else 6.0, f"foot.{sd}.pitch": -30.0,
                    f"upper_arm.{sd}.abd": (-10.0 if forward else 10.0) + (8 if sd == "L" else 0),
                    f"upper_arm.{sd}.flex": (40.0 if forward else 70.0) if sd == "L" else (-10.0 if forward else 120.0),
                    f"forearm.{sd}.flex": 30.0 if sd == "L" else 12.0, f"hand.{sd}.flex": 20.0})
    return end


def act_death(rig, p, n=40, forward=True):
    base = base_stand(p)
    feet = _foot_ik_pose(base)
    pel_z = rig.pel_z
    sgn = 1.0 if forward else -1.0
    buckle = merged(base, feet, {"hips.z": -0.24, "hips.y": 0.02 * sgn, "hips.flex": 18.0 * sgn, "spine.flex": 20.0 * sgn,
                                 "chest.flex": 18.0 * (1 if forward else -0.5), "neck.flex": 20.0, "head.flex": 10.0,
                                 "jaw.open": 26.0, "upper_arm.L.abd": -30.0, "upper_arm.R.abd": -22.0,
                                 "upper_arm.L.flex": 20.0, "upper_arm.R.flex": 6.0, "forearm.L.flex": 20.0,
                                 "forearm.R.flex": 10.0, "head.side": 14.0})
    mid = {"hips.flex": 46.0 * sgn, "hips.z": -pel_z * 0.55, "hips.y": -0.25 * sgn, "spine.flex": 10.0 * sgn,
           "chest.flex": 6.0 * sgn, "neck.flex": 10.0, "head.flex": -6.0, "jaw.open": 30.0, "head.side": 10.0}
    for sd, sx in SIDES:
        mid.update({f"ik.{sd}": 0.0, f"thigh.{sd}.flex": 40.0 if forward else 30.0, f"shin.{sd}.flex": 80.0 if forward else 50.0,
                    f"foot.{sd}.pitch": -10.0, f"upper_arm.{sd}.flex": 50.0 if forward else 60.0,
                    f"upper_arm.{sd}.abd": -10.0, f"forearm.{sd}.flex": 30.0})
    end = _fall(rig, p, forward)
    bounce = merged(end, {"hips.z": end["hips.z"] + 0.03, "hips.flex": end["hips.flex"] - 4.0 * sgn,
                          "neck.flex": end["neck.flex"] * 0.6})
    ks = Keys(base, [(0, merged(base, feet)), (9, buckle, "out"), (18, mid, "in"), (25, end, "in"), (29, bounce, "out"),
                     (34, end, "in"), (40, end)])
    frames = []
    for f in range(n + 1):
        prm = ks.at(f)
        for sd, _ in SIDES:
            prm[f"ik.{sd}"] = 1.0 if f <= 9 else 0.0
        frames.append(prm)
    # the FK legs after the switch start from the solved IK pose: blend thigh/shin from IK values
    return frames


def crawl_pose(rig, p):
    pel_z = rig.pel_z
    d = {"hips.flex": 80.0, "hips.z": -pel_z + 0.15, "hips.y": 0.0, "spine.flex": -10.0, "chest.flex": -14.0,
         "neck.flex": -30.0, "head.flex": -30.0, "jaw.open": 16.0}
    for sd, sx in SIDES:
        d.update({f"ik.{sd}": 0.0, f"thigh.{sd}.flex": -2.0, f"thigh.{sd}.abd": 10.0, f"thigh.{sd}.twist": 25.0,
                  f"shin.{sd}.flex": 12.0 if sd == "L" else 28.0, f"foot.{sd}.pitch": -35.0,
                  f"shoulder.{sd}.fwd": 18.0, f"shoulder.{sd}.shrug": 8.0})
    return d


def _crawl_shoulders(rig, prm):
    Q, off = rig.evaluate(prm)
    acc, pos = rig.sk.fk(Q, off)
    return {sd: pos[f"upper_arm.{sd}"] for sd, _ in SIDES}


def act_crawl(rig, p, n=40):
    """Legless pull along the ground: alternate arms reach, plant and pull (hands IK)."""
    pose = crawl_pose(rig, p)
    s = rig.s
    speed = 0.5
    cyc = n / FPS
    frames = []
    reach = (rig.sk.length("upper_arm.L") + rig.sk.length("forearm.L")) * 0.80
    for f in range(n + 1):
        ph = f / n
        w = 2 * math.pi * ph
        prm = dict(pose)
        prm["hips.twist"] = 7.0 * math.sin(w)
        prm["hips.side"] = 5.0 * math.sin(w)
        prm["chest.twist"] = -5.0 * math.sin(w)
        prm["chest.flex"] = pose["chest.flex"] - 4.0 * math.cos(2 * w)
        prm["hips.z"] = pose["hips.z"] + 0.02 * (0.5 + 0.5 * math.cos(2 * w))
        prm["head.twist"] = 8.0 * math.sin(w + 0.5)
        prm["jaw.open"] = pose["jaw.open"] + 8.0 * (0.5 + 0.5 * math.sin(2 * w))
        shp = _crawl_shoulders(rig, prm)
        for sd, sx in SIDES:
            pp = (ph + (0.0 if sd == "L" else 0.5)) % 1.0
            st = 0.55
            travel = speed * cyc * st
            sh = shp[sd]
            y0 = sh[1] - reach * 0.78          # furthest reach in front of the shoulder
            if pp < st:
                u = pp / st
                y = y0 + travel * u
                z = 0.0
            else:
                u = (pp - st) / (1 - st)
                y = y0 + travel * (1 - ease(u))
                z = 0.10 * s * math.sin(math.pi * u)
            prm[f"aik.{sd}"] = 1.0
            prm[f"hand.{sd}.tx"] = sh[0] + sx * 0.10 * s
            prm[f"hand.{sd}.ty"] = y
            prm[f"hand.{sd}.tz"] = 0.035 * s + z
            prm[f"elbow.{sd}.px"] = sx * 0.9
            prm[f"elbow.{sd}.py"] = 0.35
            prm[f"elbow.{sd}.pz"] = 0.5
            prm[f"hand.{sd}.flex"] = -35.0 if pp < st else 10.0
        frames.append(prm)
    return frames


def act_crawl_attack(rig, p, n=24):
    pose = crawl_pose(rig, p)
    s = rig.s
    reach = (rig.sk.length("upper_arm.L") + rig.sk.length("forearm.L")) * 0.80
    frames = []
    for f in range(n + 1):
        prm = dict(pose)
        lunge = smooth_pulse(f, 3, 6, 6, 9)
        grab = smooth_pulse(f, 7, 3, 6, 8)
        prm["chest.flex"] = pose["chest.flex"] - 16.0 * lunge
        prm["neck.flex"] = pose["neck.flex"] - 10.0 * lunge
        prm["hips.z"] = pose["hips.z"] + 0.05 * lunge
        prm["hips.y"] = -0.10 * lunge
        prm["jaw.open"] = pose["jaw.open"] + 28.0 * smooth_pulse(f, 6, 4, 2, 2) - 10.0 * smooth_pulse(f, 12, 1, 3, 6)
        shp = _crawl_shoulders(rig, prm)
        for sd, sx in SIDES:
            sh = shp[sd]
            prm[f"aik.{sd}"] = 1.0
            prm[f"hand.{sd}.tx"] = sh[0] * (1.0 - 0.8 * grab) + sx * 0.10 * s * (1 - grab)
            prm[f"hand.{sd}.ty"] = sh[1] - reach * (0.70 + 0.25 * lunge)
            prm[f"hand.{sd}.tz"] = 0.035 * s + 0.12 * s * lunge * (1 - grab)
            prm[f"elbow.{sd}.px"] = sx * 0.9
            prm[f"elbow.{sd}.py"] = 0.35
            prm[f"elbow.{sd}.pz"] = 0.5
            prm[f"hand.{sd}.flex"] = -35.0 + 70.0 * grab
        frames.append(prm)
    return frames


def act_eat(rig, p, n=60):
    """Crouched feeding over prey: squat, one hand tears up to the mouth, chewing, head jerks."""
    base = base_stand(p)
    feet = _foot_ik_pose(base, (0.04, 0.10, 0.0), (-0.04, -0.06, 0.0))
    crouch = merged(base, feet, {"hips.z": -0.50, "hips.y": 0.12, "hips.flex": 40.0, "spine.flex": 26.0, "chest.flex": 24.0,
                                 "neck.flex": 10.0, "head.flex": -4.0, "jaw.open": 10.0,
                                 "upper_arm.L.flex": 60.0, "upper_arm.L.abd": -26.0, "forearm.L.flex": 30.0, "hand.L.flex": -20.0,
                                 "upper_arm.R.flex": 50.0, "upper_arm.R.abd": -30.0, "forearm.R.flex": 50.0,
                                 "hand.R.flex": 30.0})
    seed = int(p.get("seed", 1))
    frames = []
    for f in range(n + 1):
        w = 2 * math.pi * f / n
        prm = dict(crouch)
        tear = max(smooth_pulse(f, 8, 4, 4, 10), smooth_pulse(f, 38, 4, 4, 10))
        jerk = max(smooth_pulse(f, 14, 2, 2, 6), smooth_pulse(f, 44, 2, 2, 6))
        prm["upper_arm.R.flex"] = crouch["upper_arm.R.flex"] + 35.0 * tear
        prm["forearm.R.flex"] = crouch["forearm.R.flex"] + 70.0 * tear
        prm["hand.R.flex"] = crouch["hand.R.flex"] + 20.0 * tear
        prm["neck.flex"] = crouch["neck.flex"] - 18.0 * jerk + 6.0 * tear
        prm["head.twist"] = 14.0 * jerk + 5.0 * loop_noise(seed + 9, f, n)
        prm["head.side"] = -10.0 * jerk
        prm["chest.flex"] = crouch["chest.flex"] - 6.0 * jerk
        chew = 0.5 + 0.5 * math.sin(6 * w)
        prm["jaw.open"] = 4.0 + 16.0 * chew + 10.0 * tear
        prm["hips.z"] = crouch["hips.z"] + 0.012 * math.sin(2 * w)
        prm["chest.twist"] = 6.0 * math.sin(w)
        frames.append(prm)
    return frames


# --------------------------------------------------------------------------------------------
# Idle and shamble variants (ADR-0028): EnemyVisual gives each body one of the idles and, for some,
# the hard limp in place of walk_b, so a crowd does not sway in step.
# --------------------------------------------------------------------------------------------

def act_idle_loll(rig, p, n=120):
    """Idle variant: the head lolls slowly over to the weak side and down, hangs there with the
    jaw dropping, then jerks back up; the body sways off its bad leg."""
    base = base_stand(p)
    side = 1.0 if p.get("limp_side", "R") == "L" else -1.0
    seed = int(p.get("seed", 1)) + 17
    frames = []
    for f in range(n + 1):
        w = 2 * math.pi * f / n
        u = f / n
        if u < 0.62:
            lol = ease(u / 0.62, "inout")
        elif u < 0.9:
            lol = 1.0
        else:
            lol = 1.0 - ease((u - 0.9) / 0.1, "snap")
        prm = dict(base)
        prm["hips.x"] = 0.02 * math.sin(w) + side * 0.008
        prm["hips.z"] = base["hips.z"] - 0.008 * (0.5 + 0.5 * math.cos(2 * w))
        prm["hips.side"] = 3.0 * math.sin(w + 0.3)
        prm["spine.side"] = -2.4 * math.sin(w + 0.7)
        prm["chest.flex"] = base["chest.flex"] + 1.4 * math.sin(2 * w)
        prm["chest.twist"] = 2.5 * loop_noise(seed, f, n)
        prm["neck.side"] = side * 11.0 * lol
        prm["head.side"] = base["head.side"] + side * 24.0 * lol
        prm["head.flex"] = base["head.flex"] + 15.0 * lol + 2.0 * loop_noise(seed + 1, f, n)
        prm["head.twist"] = base["head.twist"] + 5.0 * loop_noise(seed + 2, f, n) - side * 6.0 * lol
        prm["jaw.open"] = base["jaw.open"] + 9.0 * lol
        for sd, sx in SIDES:
            lag = w - 0.9
            prm[f"upper_arm.{sd}.flex"] = base[f"upper_arm.{sd}.flex"] + 3.0 * math.sin(lag)
            prm[f"upper_arm.{sd}.abd"] = base[f"upper_arm.{sd}.abd"] - sx * 2.0 * math.sin(lag)
            prm[f"forearm.{sd}.flex"] = base[f"forearm.{sd}.flex"] + 2.5 * math.sin(2 * lag + 0.5)
        frames.append(prm)
    return frames


def act_idle_twitch(rig, p, n=100):
    """Idle variant: still, with a tremor in the hands and jaw, broken by spasms - a head jerk, a
    shoulder hitched to the ear, an arm flung half up - at irregular beats."""
    base = base_stand(p)
    seed = int(p.get("seed", 1)) + 29
    r = np.random.default_rng(seed)
    beats = sorted(int(x) for x in r.choice(np.arange(6, n - 16), 5, replace=False))
    frames = []
    for f in range(n + 1):
        w = 2 * math.pi * f / n
        prm = dict(base)
        prm["hips.x"] = 0.008 * math.sin(w)
        prm["chest.flex"] = base["chest.flex"] + 1.0 * math.sin(2 * w)
        k = [smooth_pulse(f, b, 1, 2, 6) for b in beats]
        prm["head.twist"] = base["head.twist"] + 24.0 * k[0] - 16.0 * k[2] + 1.5 * math.sin(f * 2.9)
        prm["head.side"] = base["head.side"] + 14.0 * k[1] - 10.0 * k[3]
        prm["head.flex"] = base["head.flex"] - 9.0 * k[0] + 6.0 * k[4]
        prm["neck.flex"] = base["neck.flex"] - 6.0 * k[0]
        prm["chest.twist"] = 9.0 * k[4] - 5.0 * k[1]
        prm["jaw.open"] = base["jaw.open"] + 10.0 * k[2] + 1.2 * math.sin(f * 3.7)
        prm["shoulder.R.shrug"] = base["shoulder.R.shrug"] + 14.0 * k[1]
        prm["shoulder.L.shrug"] = base["shoulder.L.shrug"] + 10.0 * k[3]
        prm["upper_arm.L.flex"] = base["upper_arm.L.flex"] + 22.0 * k[3]
        prm["forearm.L.flex"] = base["forearm.L.flex"] + 35.0 * k[3]
        for sd, sx in SIDES:
            prm[f"hand.{sd}.flex"] = base[f"hand.{sd}.flex"] + 4.0 * math.sin(f * (2.3 if sd == "L" else 2.7))
        frames.append(prm)
    return frames


def act_walk_limp(rig, p, n=44):
    """Shamble variant: a hard limp - the bad leg barely leaves the ground and the body drops onto
    it each step, the shoulder on that side hitched, the head thrown to the other."""
    frames = locomotion(rig, p, n, 0.65, "walk")
    limp = p.get("limp_side", "R")
    lsx = 1.0 if limp == "L" else -1.0
    for f, prm in enumerate(frames):
        ph = (f / n) % 1.0
        lp = (ph + (0.0 if limp == "L" else 0.5)) % 1.0
        st = 0.57
        dip = 0.05 * math.sin(math.pi * min(1.0, lp / st)) if lp < st else 0.0
        prm["hips.z"] = prm.get("hips.z", 0.0) - dip
        prm["hips.side"] = prm.get("hips.side", 0.0) + lsx * dip * 150
        prm["spine.side"] = prm.get("spine.side", 0.0) - lsx * dip * 100
        prm["chest.side"] = prm.get("chest.side", 0.0) - lsx * dip * 60
        prm["head.side"] = prm.get("head.side", 0.0) - lsx * dip * 90
        prm[f"foot.{limp}.z"] = prm.get(f"foot.{limp}.z", 0.0) * 0.35
        prm[f"shoulder.{limp}.shrug"] = prm.get(f"shoulder.{limp}.shrug", 0.0) + 200.0 * dip
    return frames


# --------------------------------------------------------------------------------------------
# Action table (name, frames, loop, builder)
# --------------------------------------------------------------------------------------------

def actions_table():
    return [
        ("idle", 90, True, act_idle),
        ("idle_sleep_lie", 60, True, act_sleep_lie),
        ("idle_sleep_sit", 60, True, act_sleep_sit),
        ("idle_sleep_stand", 90, True, act_sleep_stand),
        ("idle_sleep_seat", 60, True, act_sleep_seat),
        ("idle_sleep_crouch", 60, True, act_sleep_crouch),
        ("idle_sleep_kneel", 60, True, act_sleep_kneel),
        ("wake_lie", 40, False, act_wake_lie),
        ("wake_sit", 40, False, act_wake_sit),
        ("wake_seat", 40, False, act_wake_seat),
        ("idle_sleep_hunch", 60, True, act_sleep_hunch),
        ("wake_hunch", 40, False, lambda r, p, n: act_wake_seat(r, p, n, hunch_pose(r, p))),
        ("walk", 36, True, lambda r, p, n: locomotion(r, p, n, 0.9, "walk")),
        ("walk_b", 40, True, lambda r, p, n: locomotion(r, p, n, 0.75, "walk_b")),
        ("run", 20, True, lambda r, p, n: locomotion(r, p, n, 4.5, "run")),
        ("attack_a", 24, False, act_attack_a),
        ("attack_b", 24, False, act_attack_b),
        ("attack_structure", 30, True, act_attack_structure),
        ("scream", 50, False, act_scream),
        ("hit_front", 14, False, lambda r, p, n: act_hit(r, p, n, True)),
        ("hit_back", 14, False, lambda r, p, n: act_hit(r, p, n, False)),
        ("stagger", 30, False, act_stagger),
        ("death_front", 40, False, lambda r, p, n: act_death(r, p, n, True)),
        ("death_back", 40, False, lambda r, p, n: act_death(r, p, n, False)),
        ("crawl", 40, True, act_crawl),
        ("crawl_attack", 24, False, act_crawl_attack),
        ("eat", 60, True, act_eat),
        ("idle_b", 120, True, act_idle_loll),
        ("idle_c", 100, True, act_idle_twitch),
        ("walk_limp", 44, True, act_walk_limp),
    ]


# --------------------------------------------------------------------------------------------
# Writing Blender actions
# --------------------------------------------------------------------------------------------

def bake_frames(rig: Rig, frames: list[dict], continuity_fk_from_ik: bool = True):
    """-> list of (Q dict, offset) per frame. When a leg switches from IK to FK, the FK angles
    are taken relative to the last IK solution so there is no pop."""
    out = []
    last_ik_Q = {}
    for prm in frames:
        Q, off = rig.evaluate(prm)
        out.append((Q, off))
    return out


def write_action(arm_obj, skel: Skeleton, name: str, baked: list):
    import bpy
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    arm_obj.animation_data_create()
    arm_obj.animation_data.action = act
    n = len(baked)
    for pb in arm_obj.pose.bones:
        pb.rotation_mode = "QUATERNION"
    for bname in skel.names:
        qs = np.zeros((n, 4))
        prev = None
        for i, (Q, off) in enumerate(baked):
            q = skel.to_basis(bname, Q.get(bname, np.eye(3)))
            if prev is not None and float(np.dot(q, prev)) < 0:
                q = -q
            qs[i] = q
            prev = q
        path = f'pose.bones["{bname}"].rotation_quaternion'
        for c in range(4):
            fc = act.fcurve_ensure_for_datablock(arm_obj, path, index=c, group_name=bname)
            fc.keyframe_points.add(n)
            co = np.empty(n * 2)
            co[0::2] = np.arange(n)
            co[1::2] = qs[:, c]
            fc.keyframe_points.foreach_set("co", co)
            fc.keyframe_points.foreach_set("interpolation", [1] * n)  # LINEAR
            fc.update()
        if bname == "hips" and "hips" in skel.parent:
            locs = np.array([skel.hips_location(off) for (Q, off) in baked])
            path = f'pose.bones["{bname}"].location'
            for c in range(3):
                fc = act.fcurve_ensure_for_datablock(arm_obj, path, index=c, group_name=bname)
                fc.keyframe_points.add(n)
                co = np.empty(n * 2)
                co[0::2] = np.arange(n)
                co[1::2] = locs[:, c]
                fc.keyframe_points.foreach_set("co", co)
                fc.keyframe_points.foreach_set("interpolation", [1] * n)
                fc.update()
    return act


def build_all(arm_obj, skel: Skeleton, params: dict, only=None):
    rig = Rig(skel, params)
    lengths = {}
    for name, nf, loop, fn in actions_table():
        if only and name not in only:
            continue
        frames = fn(rig, params, nf)
        frames = _ik_fk_handoff(rig, frames)
        frames = _fk_ik_handoff(rig, frames)
        baked = bake_frames(rig, frames)
        write_action(arm_obj, skel, name, baked)
        lengths[name] = nf / FPS
    arm_obj.animation_data.action = None
    for pb in arm_obj.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    return lengths


def _fk_ik_handoff(rig: Rig, frames: list[dict]) -> list[dict]:
    """Where a leg goes FK -> IK, start the IK foot target at the FK foot position and blend."""
    sk = rig.sk
    for sd, sx in SIDES:
        k = f"ik.{sd}"
        for i in range(1, len(frames)):
            if frames[i - 1].get(k, 0.0) <= 0.5 < frames[i].get(k, 0.0):
                Q, off = rig.evaluate(frames[i - 1])
                acc, pos = sk.fk(Q, off)
                ank = pos[f"foot.{sd}"]
                start = ank - rig.ankle[sd]
                blend_n = 6
                for jx in range(i, min(len(frames), i + blend_n)):
                    w = ease((jx - i + 1) / (blend_n + 1))
                    fr = frames[jx]
                    for a, key in enumerate(("x", "y", "z")):
                        kk = f"foot.{sd}.{key}"
                        fr[kk] = start[a] * (1 - w) + fr.get(kk, 0.0) * w
                break
    return frames


def _ik_fk_handoff(rig: Rig, frames: list[dict]) -> list[dict]:
    """Where a leg goes IK -> FK (falls, lying down) convert the IK solution of the last IK frame
    into FK angles and blend from there, so there is no pop at the switch."""
    sk = rig.sk
    for sd, sx in SIDES:
        k = f"ik.{sd}"
        for i in range(1, len(frames)):
            if frames[i - 1].get(k, 0.0) > 0.5 and frames[i].get(k, 0.0) <= 0.5:
                Q, off = rig.evaluate(frames[i - 1])
                acc, pos = sk.fk(Q, off)
                # measure the IK solution's angles in FK parameter space (flex about X etc.)
                th_dir = acc[f"thigh.{sd}"] @ sk.rest[f"thigh.{sd}"][:, 1]
                hip_acc = acc["hips"]
                local = hip_acc.T @ th_dir
                flex = math.degrees(math.atan2(-local[1], -local[2])) - math.degrees(math.atan2(-sk.axis(f"thigh.{sd}")[1], -sk.axis(f"thigh.{sd}")[2]))
                sh_rel = acc[f"thigh.{sd}"].T @ (acc[f"shin.{sd}"] @ sk.rest[f"shin.{sd}"][:, 1])
                rest_rel = sk.rest[f"thigh.{sd}"].T @ sk.rest[f"shin.{sd}"][:, 1]
                knee = math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(_n(sh_rel), _n(rest_rel)))))))
                # blend the next frames from these angles towards their own FK targets
                blend_n = 6
                for jx in range(i, min(len(frames), i + blend_n)):
                    w = ease((jx - i + 1) / blend_n)
                    fr = frames[jx]
                    fr[f"thigh.{sd}.flex"] = flex * (1 - w) + fr.get(f"thigh.{sd}.flex", 0.0) * w
                    fr[f"shin.{sd}.flex"] = knee * (1 - w) + fr.get(f"shin.{sd}.flex", 0.0) * w
                break
    return frames
