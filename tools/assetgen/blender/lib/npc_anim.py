"""Animations for living human NPCs (the trader behind his counter): calm, human, no twitching.

Built on the Hollowed animation toolkit (char_anim: pose parameters, Rig with leg and arm IK,
write_action), on the shared skeleton, 30 fps, in place. Clips (docs/CHARACTERS.md):

  idle    standing: slow breathing, a weight shift from foot to foot, the gaze drifting
  idle_b  leaning on the counter with both hands flat on it (counter top COUNTER_H high, its near
          edge COUNTER_Y in front of the origin), breathing, a few fingers drummed
  talk    one hand opens towards the customer, palm up, two beats and two nods
  look    glances off to his left, then scratches the back of his neck

All loop: each starts and ends on its own base pose (idle and talk share theirs).
"""
from __future__ import annotations

import math

import numpy as np

from . import char_anim as A
from .char_anim import SIDES, Keys, Rig, loop_noise, smooth_pulse
from .char_skel import _n, mat_to_quat

COUNTER_H = 1.05        # counter top above the floor (m)
COUNTER_Y = 0.35        # its near edge in front of the origin (m); front is -Y
ARM_BONES = ("upper_arm", "forearm", "hand")


def base_human(p: dict) -> dict:
    """Upright, relaxed, a little heavy: weight on both feet, arms hanging clear of the belly."""
    b = {
        "hips.z": -0.006, "hips.flex": 1.0,
        "spine.flex": 1.0, "chest.flex": 0.5, "neck.flex": 2.0,
        "head.side": 0.0, "head.twist": 0.0, "jaw.open": 0.5,
    }
    for sd, sx in SIDES:
        b.update({
            f"shoulder.{sd}.fwd": 3.0, f"shoulder.{sd}.shrug": -1.0,
            f"upper_arm.{sd}.abd": float(p.get("arm_hang", -33.0)), f"upper_arm.{sd}.flex": 3.0,
            f"upper_arm.{sd}.twist": -4.0,
            f"forearm.{sd}.flex": 12.0, f"forearm.{sd}.twist": 0.0,
            f"hand.{sd}.flex": 6.0, f"hand.{sd}.dev": 0.0,
            f"ik.{sd}": 1.0, f"foot.{sd}.x": 0.0, f"foot.{sd}.y": 0.0, f"foot.{sd}.z": 0.0,
        })
    A.level_head(b, p, 1.0)
    return b


# --------------------------------------------------------------------------------------------
# Rotation helpers (arm FK <-> IK blending, hand aiming)
# --------------------------------------------------------------------------------------------

def _quat_to_mat(q) -> np.ndarray:
    w, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def _slerp_m(Ma, Mb, w: float) -> np.ndarray:
    if w <= 0.0:
        return Ma
    if w >= 1.0:
        return Mb
    qa, qb = mat_to_quat(Ma), mat_to_quat(Mb)
    if float(np.dot(qa, qb)) < 0:
        qb = -qb
    d = min(1.0, float(np.dot(qa, qb)))
    th = math.acos(d)
    if th < 1e-5:
        q = qa
    else:
        q = (math.sin((1 - w) * th) * qa + math.sin(w * th) * qb) / math.sin(th)
    return _quat_to_mat(q / np.linalg.norm(q))


def _blend_arm(Qa: dict, Qb: dict, sd: str, w: float) -> dict:
    out = dict(Qa)
    for b in ARM_BONES:
        n = f"{b}.{sd}"
        out[n] = _slerp_m(Qa.get(n, np.eye(3)), Qb.get(n, np.eye(3)), w)
    return out


def _aim_hand(rig: Rig, Q: dict, off, sd: str, along, back) -> None:
    """Points the hand bone along `along` with the back of the hand towards `back`."""
    rig.sk.aim(Q, f"hand.{sd}", _n(along), _n(back), off)


def _ik_arm(prm: dict, sd: str, target, pole) -> dict:
    out = dict(prm)
    out[f"aik.{sd}"] = 1.0
    out[f"hand.{sd}.tx"], out[f"hand.{sd}.ty"], out[f"hand.{sd}.tz"] = (float(v) for v in target)
    out[f"elbow.{sd}.px"], out[f"elbow.{sd}.py"], out[f"elbow.{sd}.pz"] = (float(v) for v in pole)
    return out


def _posed(rig: Rig, prm: dict):
    Q, off = rig.evaluate(prm)
    acc, pos = rig.sk.fk(Q, off)
    return Q, off, acc, pos


# --------------------------------------------------------------------------------------------
# Clips: each returns the baked frames [(Q, offset)]
# --------------------------------------------------------------------------------------------

def act_idle(rig: Rig, p: dict, n: int = 180):
    base = base_human(p)
    seed = int(p.get("seed", 1))
    out = []
    for f in range(n + 1):
        w = 2 * math.pi * f / n
        br = math.sin(2 * w)                                   # two slow breaths per loop
        shift = math.sin(w)                                    # weight left -> right -> left
        prm = dict(base)
        prm["hips.x"] = 0.022 * shift
        prm["hips.y"] = 0.004 * math.sin(2 * w + 0.7)
        prm["hips.z"] = base["hips.z"] - 0.007 * abs(shift)
        prm["hips.side"] = -2.2 * shift
        prm["spine.side"] = 1.2 * shift
        prm["chest.side"] = 0.8 * shift
        prm["chest.flex"] = base["chest.flex"] - 1.4 * br
        prm["neck.flex"] = base["neck.flex"] + 0.8 * br + 1.2 * loop_noise(seed + 1, f, n)
        prm["head.twist"] = 7.0 * loop_noise(seed + 2, f, n, (1, 2))
        prm["head.side"] = -1.6 * shift + 1.0 * loop_noise(seed + 3, f, n, (1, 3))
        prm["head.flex"] = base["head.flex"] - 0.6 * br + 1.5 * loop_noise(seed + 4, f, n, (2, 3))
        for sd, sx in SIDES:
            lag = w - 0.6
            prm[f"shoulder.{sd}.shrug"] = base[f"shoulder.{sd}.shrug"] + 1.2 * br
            prm[f"upper_arm.{sd}.flex"] = base[f"upper_arm.{sd}.flex"] + 1.5 * math.sin(lag)
            prm[f"upper_arm.{sd}.abd"] = base[f"upper_arm.{sd}.abd"] + sx * 1.2 * math.sin(lag)
            prm[f"forearm.{sd}.flex"] = base[f"forearm.{sd}.flex"] + 2.0 * math.sin(2 * lag + 0.5 * sx)
        out.append(rig.evaluate(prm))
    return out


def lean_pose(rig: Rig, p: dict) -> dict:
    """Both hands flat on the counter top, the trunk tipped over them, elbows a little bent."""
    b = base_human(p)
    s = rig.s
    b.update({"hips.y": 0.05, "hips.z": -0.010, "hips.flex": 7.0, "spine.flex": 7.0, "chest.flex": 6.0,
              "neck.flex": 2.0})
    for sd, sx in SIDES:
        b[f"shoulder.{sd}.shrug"] = 5.0
        b[f"shoulder.{sd}.fwd"] = 8.0
    A.level_head(b, p, 12.0)
    return b


def counter_targets(rig: Rig, p: dict) -> dict:
    """Wrist targets on the counter top for each side (armature space)."""
    s = rig.s
    out = {}
    for sd, sx in SIDES:
        x = sx * float(p.get("lean_hand_x", 0.23)) * s
        y = -(COUNTER_Y + float(p.get("lean_hand_in", 0.13)))
        out[sd] = np.array([x, y, COUNTER_H + 0.028 * s])
    return out


def act_idle_b(rig: Rig, p: dict, n: int = 150):
    base = lean_pose(rig, p)
    seed = int(p.get("seed", 1))
    tg = counter_targets(rig, p)
    out = []
    for f in range(n + 1):
        w = 2 * math.pi * f / n
        br = math.sin(2 * w)
        shift = math.sin(w)
        prm = dict(base)
        prm["hips.x"] = 0.010 * shift
        prm["hips.side"] = -1.5 * shift
        prm["hips.y"] = base["hips.y"] + 0.004 * br
        prm["chest.flex"] = base["chest.flex"] - 1.2 * br
        prm["head.twist"] = 9.0 * loop_noise(seed + 5, f, n, (1, 2))
        prm["head.flex"] = base["head.flex"] + 2.0 * loop_noise(seed + 6, f, n, (1, 3))
        prm["head.side"] = 2.0 * loop_noise(seed + 7, f, n, (1, 2))
        for sd, sx in SIDES:
            prm[f"shoulder.{sd}.shrug"] = base[f"shoulder.{sd}.shrug"] + 1.0 * br
            prm = _ik_arm(prm, sd, tg[sd], (sx * 0.55, 0.8, -0.2))
        Q, off = rig.evaluate(prm)
        for sd, sx in SIDES:
            along = np.array([-sx * 0.22, -1.0, 0.0])
            back = np.array([sx * 0.05, 0.0, 1.0])
            if sd == "R":
                # drumming the fingers: the hand lifts off the counter and comes down, three taps
                tap = sum(smooth_pulse(f, t0, 2, 1, 4) for t0 in (62, 70, 78))
                tilt = math.radians(9.0 * tap)
                along = along * math.cos(tilt) + np.array([0.0, 0.0, 1.0]) * math.sin(tilt)
                back = back * math.cos(tilt) - np.array([0.0, -1.0, 0.0]) * math.sin(tilt)
            _aim_hand(rig, Q, off, sd, along, back)
        out.append((Q, off))
    return out


def act_talk(rig: Rig, p: dict, n: int = 90):
    base = base_human(p)
    seed = int(p.get("seed", 1))
    g_env = Keys({"g": 0.0}, [(0, {"g": 0.0}), (8, {"g": 0.0}), (24, {"g": 1.0}), (64, {"g": 1.0}),
                              (84, {"g": 0.0}), (n, {"g": 0.0})])
    out = []
    for f in range(n + 1):
        g = g_env.at(f)["g"]
        beat = smooth_pulse(f, 32, 4, 2, 9) + 0.8 * smooth_pulse(f, 48, 4, 2, 9)
        nod = smooth_pulse(f, 30, 4, 1, 8) + 0.8 * smooth_pulse(f, 47, 4, 1, 8)
        w = 2 * math.pi * f / n
        prm = dict(base)
        # leaning in a touch towards the customer, turning the open hand's shoulder to him
        prm["chest.flex"] = base["chest.flex"] + 3.0 * g
        prm["spine.flex"] = base["spine.flex"] + 1.5 * g
        prm["chest.twist"] = 6.0 * g
        prm["hips.x"] = 0.008 * g
        prm["neck.flex"] = base["neck.flex"] + 2.0 * nod
        prm["head.flex"] = base["head.flex"] + 8.0 * nod - 2.0 * g
        prm["head.twist"] = -5.0 * g + 1.5 * loop_noise(seed + 8, f, n, (1, 2))
        prm["head.side"] = 3.0 * g
        talking = g * (0.5 + 0.5 * math.sin(f * 0.95)) * (0.6 + 0.4 * math.sin(f * 0.37 + 1.0))
        prm["jaw.open"] = base["jaw.open"] + 4.0 * talking
        # the right hand opens forward, palm up, and gives two beats
        prm["shoulder.R.fwd"] = base["shoulder.R.fwd"] + 6.0 * g
        prm["upper_arm.R.flex"] = base["upper_arm.R.flex"] + float(p.get("talk_ua_flex", 22.0)) * g + 6.0 * beat
        prm["upper_arm.R.abd"] = base["upper_arm.R.abd"] + 16.0 * g
        prm["upper_arm.R.twist"] = base["upper_arm.R.twist"] + float(p.get("talk_ua_twist", 0.0)) * g
        prm["forearm.R.flex"] = base["forearm.R.flex"] + float(p.get("talk_fa_flex", 36.0)) * g - 10.0 * beat
        prm["forearm.R.twist"] = float(p.get("talk_supinate", -95.0)) * g
        prm["hand.R.flex"] = base["hand.R.flex"] + float(p.get("talk_hand_flex", -28.0)) * g + 6.0 * beat
        # the other hand follows a little
        prm["forearm.L.flex"] = base["forearm.L.flex"] + 8.0 * g
        prm["upper_arm.L.flex"] = base["upper_arm.L.flex"] + 3.0 * g
        prm["chest.flex"] += -0.8 * math.sin(2 * w)
        out.append(rig.evaluate(prm))
    return out


def act_look(rig: Rig, p: dict, n: int = 120):
    base = base_human(p)
    s = rig.s
    k = Keys({"t": 0.0, "sc": 0.0}, [
        (0, {"t": 0.0, "sc": 0.0}), (10, {"t": 0.0}), (26, {"t": 1.0}), (44, {"t": 1.0}), (60, {"t": 0.0}),
        (56, {"sc": 0.0}), (74, {"sc": 1.0}), (96, {"sc": 1.0}), (114, {"sc": 0.0}), (n, {"t": 0.0, "sc": 0.0})])
    out = []
    for f in range(n + 1):
        e = k.at(f)
        t, sc = e["t"], e["sc"]
        prm = dict(base)
        # the glance off to his left: eyes lead (no eyes rig), head, neck, then a little chest
        glance = t
        prm["head.twist"] = 30.0 * glance
        prm["neck.twist"] = 12.0 * glance
        prm["chest.twist"] = 5.0 * glance
        prm["head.flex"] = base["head.flex"] - 3.0 * glance + 9.0 * sc
        prm["head.side"] = 2.0 * glance - 6.0 * sc
        prm["neck.flex"] = base["neck.flex"] + 4.0 * sc
        prm["chest.flex"] = base["chest.flex"] - 0.8 * math.sin(4 * math.pi * f / n)
        prm["shoulder.R.shrug"] = base["shoulder.R.shrug"] + 8.0 * sc
        Qa, off = rig.evaluate(prm)
        if sc > 0.0:
            # the scratch: the right hand up to the nape, rubbing side to side
            _, _, acc, pos = _posed(rig, prm)
            sk = rig.sk
            nape_rest = sk.head["neck"] + np.array([0.0, 0.060 * s, 0.075 * s])
            nape = sk.point(acc, pos, "neck", nape_rest)
            rub = math.sin(2 * math.pi * (f - 74) / 7.0) * smooth_pulse(f, 76, 3, 14, 4) if f >= 74 else 0.0
            right = acc["neck"] @ np.array([-1.0, 0.0, 0.0])
            back = acc["neck"] @ np.array([0.0, 1.0, 0.0])
            upv = acc["neck"] @ np.array([0.0, 0.0, 1.0])
            wrist = nape + right * (0.13 + 0.02 * rub) * s + back * 0.07 * s + upv * 0.01 * s
            prm_ik = _ik_arm(prm, "R", wrist, (-0.85, -0.6, -0.15))
            Qb, _ = rig.evaluate(prm_ik)
            _aim_hand(rig, Qb, off, "R", nape + back * 0.02 * s - wrist, back * 0.7 + right * 0.5)
            Q = _blend_arm(Qa, Qb, "R", A.ease(sc))
        else:
            Q = Qa
        out.append((Q, off))
    return out


def actions_table():
    return [
        ("idle", 180, act_idle),
        ("idle_b", 150, act_idle_b),
        ("talk", 90, act_talk),
        ("look", 120, act_look),
    ]


def build_all(arm_obj, skel, params: dict, only=None) -> dict:
    """Writes every clip as a Blender action; -> {name: seconds}."""
    rig = Rig(skel, params)
    lengths = {}
    for name, nf, fn in actions_table():
        if only and name not in only:
            continue
        baked = fn(rig, params, nf)
        A.write_action(arm_obj, skel, name, baked)
        lengths[name] = nf / A.FPS
    arm_obj.animation_data.action = None
    for pb in arm_obj.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    return lengths

