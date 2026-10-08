"""Clips only the companion has (ADR-0058, Ezra Vane), on top of the living fighter's set
(living_anim) and the trader's talk / look (npc_anim). Built on the Hollowed toolkit (char_anim:
pose parameters, Rig, Keys, write_action), on the shared skeleton, 30 fps, in place. Front is -Y.

  downed       lying on his back, hurt: laboured breathing, his left hand pressed to his side, his
               head rolling now and then (loops; the pelvis LIE_Y behind the origin, as the
               Hollowed's lying sleep, so the game's "lie" capsule fits him)
  revive       getting up off his back, slowly and stiffly: up onto an elbow, sitting, the feet
               drawn in, a hand on the knee to push up, standing (ends on the living stance)
  sit_injured  sitting on the ground by his fire, the splinted left leg out straight, the right
               knee up with the forearm over it, the head up and watchful (loops)
Phase 2 (gather, fetch, store):
  pickup       down into a crouch over the feet, the right hand to the ground in front, a grip, up
               again with it at the chest (30 frames; the game takes the thing at 50%)
  chop         a felling blow at a trunk at hip height: both hands on the hatchet wind it back over
               the right shoulder, the hips and chest turn through and it lands in front at frame 16
               (45%, where CompanionWork deals the blow), the pull back out, the stance (36 frames,
               played once a blow)
  carry_walk   the living walk with a log on the right shoulder: the right hand up at the shoulder
               steadying it, that shoulder raised, the trunk leaning a little away from the weight,
               the left arm swinging (loops; 0.9 m/s at speed 1 like the walk)
"""
from __future__ import annotations

import math

from . import char_anim as A
from . import living_anim as LA
from .char_anim import SIDES, Keys, ease, merged, smooth_pulse


def downed_pose(rig, p: dict) -> dict:
    """The lying sleep's pose made a hurt man's: mouth near shut, the head turned a little, the left
    hand on his side, the right arm out a little from his body, the right knee drawn up."""
    d = A.lie_pose(rig, p)
    d.update({"jaw.open": 4.0, "head.twist": 16.0, "head.side": 4.0, "neck.flex": 16.0,
              "upper_arm.L.flex": -6.0, "upper_arm.L.abd": -34.0, "upper_arm.L.twist": 70.0, "forearm.L.flex": 104.0,
              "hand.L.flex": 10.0,
              "upper_arm.R.flex": -14.0, "upper_arm.R.abd": -52.0, "upper_arm.R.twist": 30.0, "forearm.R.flex": 24.0})
    # the right knee drawn up a little (the foot comes in along the ground)
    d["foot.R.y"] = d["foot.R.y"] + 0.16
    d["foot.R.pitch"] = 20.0
    return d


def act_downed(rig, p, n=90):
    pose = downed_pose(rig, p)
    frames = []
    for f in range(n + 1):
        w = 2 * math.pi * f / n
        prm = dict(pose)
        # three short, laboured breaths a loop, the chest heaving and the jaw with it
        b = math.sin(3 * w)
        prm["chest.flex"] = pose["chest.flex"] - 2.4 * b
        prm["spine.flex"] = pose["spine.flex"] - 0.8 * b
        prm["jaw.open"] = pose["jaw.open"] + 2.0 * max(0.0, b)
        prm["neck.flex"] = pose["neck.flex"] + 1.2 * math.sin(3 * w + 0.6)
        # the head rolls over and back once
        roll = smooth_pulse(f, 40, 10, 12, 16)
        prm["head.twist"] = pose["head.twist"] - 22.0 * roll
        # the hand presses at the wound
        prm["hand.L.flex"] = pose["hand.L.flex"] + 14.0 * smooth_pulse(f, 18, 4, 6, 10)
        prm["forearm.L.flex"] = pose["forearm.L.flex"] + 4.0 * smooth_pulse(f, 18, 4, 6, 10)
        prm["forearm.R.flex"] = pose["forearm.R.flex"] + 8.0 * smooth_pulse(f, 62, 3, 4, 8)
        frames.append(prm)
    return frames


def act_revive(rig, p, n=72):
    """Up off his back, slowly: onto an elbow (frame 14), sitting (26), the feet drawn in (36), the
    weight over them with a hand pushing on the right knee (50), rising (62), standing (72)."""
    base = LA.base_living(p)
    lie = downed_pose(rig, p)
    pz = -rig.pel_z
    elbow = merged(lie, {"hips.flex": -60.0, "hips.z": pz + 0.13, "spine.flex": 10.0, "chest.flex": 8.0, "chest.twist": 12.0,
                         "neck.flex": 10.0, "head.flex": -10.0, "head.twist": 4.0, "jaw.open": 8.0,
                         "upper_arm.R.flex": 20.0, "upper_arm.R.abd": -40.0, "upper_arm.R.twist": 0.0, "forearm.R.flex": 70.0,
                         "hand.R.flex": -40.0})
    situp = merged(lie, {"hips.flex": -14.0, "hips.z": pz + 0.125, "spine.flex": 22.0, "chest.flex": 16.0, "chest.twist": 0.0,
                         "neck.flex": 6.0, "head.flex": -12.0, "head.twist": 0.0, "head.side": 0.0, "jaw.open": 10.0,
                         "upper_arm.L.flex": -20.0, "upper_arm.R.flex": -26.0, "upper_arm.L.abd": -26.0,
                         "upper_arm.R.abd": -26.0, "upper_arm.L.twist": 0.0, "upper_arm.R.twist": 0.0,
                         "forearm.L.flex": 10.0, "forearm.R.flex": 8.0, "hand.L.flex": -50.0, "hand.R.flex": -50.0})
    tuck = merged(situp, {"spine.flex": 32.0, "chest.flex": 24.0, "hips.flex": 4.0, "head.flex": -20.0,
                          "foot.L.y": 0.08 - rig.ankle["L"][1], "foot.R.y": 0.0 - rig.ankle["R"][1],
                          "foot.L.x": 0.03, "foot.R.x": -0.03, "foot.L.pitch": 0.0, "foot.R.pitch": 0.0,
                          "foot.L.pivot": 0.0, "foot.R.pivot": 0.0, "foot.L.yaw": 0.0, "foot.R.yaw": 0.0,
                          "knee.L.px": 0.3, "knee.L.py": -0.6, "knee.L.pz": 0.8,
                          "knee.R.px": -0.3, "knee.R.py": -0.6, "knee.R.pz": 0.8,
                          "upper_arm.L.flex": 20.0, "upper_arm.R.flex": 30.0, "hand.L.flex": -30.0, "hand.R.flex": -20.0})
    crouch = merged(base, {"hips.z": -0.46, "hips.y": 0.17, "hips.flex": 36.0, "spine.flex": 28.0, "chest.flex": 20.0,
                           "neck.flex": -4.0, "head.flex": -22.0, "jaw.open": 10.0,
                           "foot.L.y": tuck["foot.L.y"], "foot.R.y": tuck["foot.R.y"], "foot.L.x": 0.03, "foot.R.x": -0.03,
                           "upper_arm.L.flex": 26.0, "upper_arm.R.flex": 46.0, "forearm.L.flex": 36.0,
                           "forearm.R.flex": 52.0, "hand.R.flex": -30.0})
    rise = merged(base, {"hips.z": -0.12, "hips.y": 0.06, "hips.flex": 14.0, "spine.flex": 14.0, "chest.flex": 10.0,
                         "head.flex": -12.0, "head.twist": 8.0, "jaw.open": 6.0,
                         "upper_arm.R.flex": 24.0, "forearm.R.flex": 40.0,
                         "foot.L.y": tuck["foot.L.y"] * 0.4, "foot.R.y": tuck["foot.R.y"] * 0.4})
    ks = Keys(base, [(0, lie), (14, elbow, "inout"), (26, situp, "inout"), (36, tuck), (50, crouch, "inout"),
                     (62, rise, "out"), (n, base, "inout")])
    frames = []
    for f in range(n + 1):
        prm = ks.at(f)
        for sd, _ in SIDES:
            prm[f"ik.{sd}"] = 1.0
            if f >= 50:   # the default knee pole (pelvis forward) for the standing part
                w = ease((f - 50) / 10.0)
                for c, v in (("px", 0.0), ("py", -1.0), ("pz", 0.0)):
                    prm[f"knee.{sd}.{c}"] = prm.get(f"knee.{sd}.{c}", 0.0) * (1 - w) + v * w
        frames.append(prm)
    return frames


def sit_injured_pose(rig, p: dict) -> dict:
    """The Hollowed's slumped floor sit, sat up: the chest raised, the head up and level, the mouth
    shut (sit_pose already has the left leg out straight and the right knee up)."""
    d = A.sit_pose(rig, p)
    d.update({"spine.flex": 10.0, "chest.flex": 8.0, "chest.side": 2.0, "neck.flex": 14.0, "head.flex": -6.0,
              "head.side": 4.0, "head.twist": 12.0, "jaw.open": 2.0})
    return d


def act_sit_injured(rig, p, n=150):
    pose = sit_injured_pose(rig, p)
    frames = []
    for f in range(n + 1):
        w = 2 * math.pi * f / n
        prm = dict(pose)
        prm["chest.flex"] = pose["chest.flex"] + 1.4 * math.sin(4 * w)
        prm["neck.flex"] = pose["neck.flex"] + 0.6 * math.sin(4 * w + 0.5)
        # he looks off to the treeline and back, and rubs the splinted thigh once
        look = smooth_pulse(f, 60, 14, 22, 18)
        prm["head.twist"] = pose["head.twist"] - 40.0 * look
        prm["head.flex"] = pose["head.flex"] - 4.0 * look
        rub = smooth_pulse(f, 110, 6, 10, 10)
        prm["forearm.L.flex"] = pose["forearm.L.flex"] + 10.0 * rub * (0.6 + 0.4 * math.sin(f * 0.9))
        frames.append(prm)
    return frames


def act_pickup(rig, p, n=30):
    """Crouch, reach, grip, rise: the knees and hips fold over planted feet (leg IK), the back bends
    over them, the right hand goes to the ground a forearm ahead of the toes (arm IK) and comes up
    to the chest with the thing; the left hand braces on the left knee on the way down."""
    st = merged(LA.base_living(p), LA._REST_L, LA._REST_R)
    low = merged(st, {"hips.z": -0.42, "hips.y": 0.15, "hips.flex": 38.0, "spine.flex": 26.0, "chest.flex": 18.0,
                      "neck.flex": -6.0, "head.flex": -16.0, "chest.twist": -6.0, "shoulder.R.fwd": 10.0,
                      "foot.L.y": -0.06, "foot.R.y": 0.06},
                 LA._arm("R", 1.0, -0.04, -0.34, -0.58, (0.7, 0.5, -0.2)),
                 LA._arm("L", 1.0, -0.10, -0.30, -0.36, (0.8, 0.2, -0.4)))
    grip = merged(low, {"hips.z": -0.44, "head.flex": -18.0}, LA._arm("R", 1.0, -0.06, -0.36, -0.62, (0.7, 0.5, -0.2)))
    rise = merged(st, {"hips.z": -0.10, "hips.y": 0.04, "hips.flex": 12.0, "spine.flex": 8.0, "chest.flex": 4.0},
                  LA._arm("R", 1.0, -0.12, -0.22, -0.30, (0.7, 0.4, -0.6)))
    ks = Keys(st, [(0, st), (11, low, "inout"), (15, grip, "out"), (24, rise, "inout"), (n, st, "inout")])
    frames = LA._arm_offsets(rig, [ks.at(f) for f in range(n + 1)])
    for prm in frames:
        A.level_head(prm, p, 8.0, 0.4)
    return frames


def act_chop(rig, p, n=36):
    """A felling blow at hip height, both hands on the haft (right hand at the head end): wound back
    over the right shoulder with the weight on the back foot, the turn through, the hatchet into
    the trunk in front of him at frame 16, worked loose, back to the stance."""
    st = merged(LA.fight_stance(p), LA._REST_L, LA._REST_R)
    st.update({"foot.L.y": -0.16, "foot.L.x": 0.06, "foot.R.y": 0.14, "foot.R.x": -0.06})
    wind = merged(st, {"hips.y": 0.05, "hips.twist": -16.0, "chest.twist": 30.0, "chest.flex": -4.0, "spine.flex": 2.0,
                       "shoulder.R.shrug": 6.0, "head.twist": -12.0},
                  LA._arm("R", 1.0, 0.16, 0.06, 0.12, (0.8, 0.3, 0.2)),
                  LA._arm("L", 1.0, -0.16, -0.02, 0.02, (0.8, 0.2, -0.3)))
    strike = merged(st, {"hips.y": -0.07, "hips.z": -0.06, "hips.twist": 10.0, "chest.twist": -18.0, "chest.flex": 10.0,
                         "spine.flex": 6.0, "hips.flex": 6.0, "shoulder.R.fwd": 12.0, "head.twist": 6.0},
                    LA._arm("R", 1.0, -0.20, -0.56, -0.40, (0.6, 0.4, -0.6)),
                    LA._arm("L", 1.0, -0.36, -0.46, -0.44, (0.6, 0.4, -0.6)))
    stuck = merged(strike, {"chest.twist": -14.0, "chest.flex": 8.0},
                   LA._arm("R", 1.0, -0.16, -0.50, -0.40, (0.6, 0.4, -0.6)),
                   LA._arm("L", 1.0, -0.32, -0.42, -0.42, (0.6, 0.4, -0.6)))
    ks = Keys(st, [(0, st), (10, wind, "out"), (16, strike, "in"), (22, stuck, "out"), (n, st, "inout")])
    frames = LA._arm_offsets(rig, [ks.at(f) for f in range(n + 1)])
    for prm in frames:
        A.level_head(prm, p, 10.0, 0.5)
    return frames


def act_carry_walk(rig, p, n=LA.WALK_FRAMES):
    """The living walk under a log on the right shoulder: that hand up at the shoulder steadying it
    (arm IK onto the posed shoulder), the shoulder raised, the trunk leaning a little to the left
    and the head tipped away from the log; a heavier, shorter bob."""
    frames = LA._walk(rig, p, n, 1, False)
    s = rig.s
    for prm in frames:
        prm["shoulder.R.shrug"] = 9.0
        prm["shoulder.R.fwd"] = 4.0
        prm["chest.side"] = prm.get("chest.side", 0.0) + 3.0
        prm["spine.side"] = prm.get("spine.side", 0.0) + 1.5
        prm["head.side"] = prm.get("head.side", 0.0) + 7.0
        prm["chest.twist"] = prm.get("chest.twist", 0.0) * 0.5
        prm["hips.z"] = prm["hips.z"] - 0.01
        Q, off = rig.evaluate({k: v for k, v in prm.items() if not k.startswith("aik.R")})
        _, pos = rig.sk.fk(Q, off)
        sh = pos["upper_arm.R"]
        sx = -1.0  # the right side (char_anim.SIDES)
        prm["aik.R"] = 1.0
        prm["hand.R.tx"] = float(sh[0] + sx * -0.02 * s)
        prm["hand.R.ty"] = float(sh[1] - 0.14 * s)
        prm["hand.R.tz"] = float(sh[2] + 0.04 * s)
        prm["elbow.R.px"], prm["elbow.R.py"], prm["elbow.R.pz"] = sx * 0.5, -0.4, -1.0
        prm["hand.R.flex"] = -20.0
    return frames


def actions_table() -> list:
    return [
        ("downed", 90, act_downed),
        ("revive", 72, act_revive),
        ("sit_injured", 150, act_sit_injured),
        ("pickup", 30, act_pickup),
        ("chop", 36, act_chop),
        ("carry_walk", LA.WALK_FRAMES, act_carry_walk),
    ]


def build_all(arm_obj, skel, params: dict, only=None) -> dict:
    """Writes the companion's own clips as Blender actions; -> {name: seconds}."""
    rig = A.Rig(skel, params)
    lengths = {}
    for name, nf, fn in actions_table():
        if only and name not in only:
            continue
        frames = fn(rig, params, nf)
        frames = A._fk_ik_handoff(rig, frames)
        A.write_action(arm_obj, skel, name, A.bake_frames(rig, frames))
        lengths[name] = nf / A.FPS
    arm_obj.animation_data.action = None
    for pb in arm_obj.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    return lengths
