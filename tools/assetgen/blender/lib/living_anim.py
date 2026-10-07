"""Clips for living fighters (the Ashen, ADR-0048): the Hollowed's action names, played by the same
Enemy code, but moved like fit people - upright, balanced, purposeful (TD-187).

Built on the Hollowed toolkit (char_anim: pose parameters, Rig with leg and arm IK, the IK/FK
handoffs, write_action), on the shared skeleton, 30 fps, in place. Front is -Y.

The living set replaces these Hollowed clips (docs/CHARACTERS.md):
  idle              an alert upright stance, weight shifting, the head scanning
  walk              an upright, confident walk
  walk_b            a wary stalking walk: knees softer, leaning in, arms ready (EnemyVisual plays
                    it for half the bodies, so a band does not move in step)
  run               a fast upright run, arms pumping
  attack_a          an overhead axe chop (right hand)
  attack_b          a spear thrust that is also the throw (Enemy releases the spear 0.55 s into
                    the clip at 0.9 speed: the arm is at full extension then)
  attack_structure  two-handed chops at a wall or door (loops)
drops the Hollowed-only ones (head loll / twitch idles, the hard limp, feeding, crawling, the
Keener's scream - none of which a tribe fighter plays, and idle_b / idle_c / walk_limp would be
picked as variants by EnemyVisual) and keeps the rest (sleep / wake, hits, stagger, deaths).

Speeds: Enemy plays `walk` / `walk_b` at speed scale sp / 0.9 and `run` at sp / 4.5, so the clips
travel exactly 0.9 m/s and 4.5 m/s at speed 1 (no foot sliding at any playback speed). The walks'
stride is the one a person takes at ~1.4 m/s (the Ashen's walk speed): played at 1.4 / 0.9 their
cadence is a natural ~115 steps a minute. The run's stride and cadence are for ~4.5-5 m/s.
"""
from __future__ import annotations

import math

import numpy as np

from . import char_anim as A
from .char_anim import FPS, SIDES, Keys, ease, loop_noise, merged

WALK_SPEED = 0.9        # m/s at speed scale 1 (Enemy._update_anim: sp / 0.9)
RUN_SPEED = 4.5         # m/s at speed scale 1 (sp / 4.5)
WALK_FRAMES = 46        # one cycle, 1.53 s at speed 1: 1.38 m stride -> 1.0 s at 1.4 m/s
WALK_B_FRAMES = 84      # two cycles (42 frames, 1.26 m stride) so the head scan spans both
RUN_FRAMES = 20         # one cycle, 0.67 s: 3.0 m stride, 180 steps a minute

# Hollowed clips a living fighter never plays (EnemyVisual would pick some as variants).
DROPPED = ("idle_b", "idle_c", "walk_limp", "eat", "crawl", "crawl_attack", "scream")


def base_living(p: dict) -> dict:
    """Upright and ready: chest up, knees soft, feet under the hips, arms hanging loose a hand's
    width off the thighs, the gaze level."""
    b = {
        "hips.z": -0.012, "hips.flex": 1.0,
        "spine.flex": 0.0, "chest.flex": -1.5, "neck.flex": 3.0,
        "head.side": 0.0, "head.twist": 0.0, "jaw.open": 0.0,
    }
    for sd, sx in SIDES:
        b.update({
            f"shoulder.{sd}.fwd": 0.0, f"shoulder.{sd}.shrug": -2.0,
            f"upper_arm.{sd}.abd": -31.0, f"upper_arm.{sd}.flex": 4.0, f"upper_arm.{sd}.twist": -6.0,
            f"forearm.{sd}.flex": 14.0, f"forearm.{sd}.twist": 35.0,
            f"hand.{sd}.flex": 8.0, f"hand.{sd}.dev": 0.0,
            f"ik.{sd}": 1.0, f"foot.{sd}.x": 0.0, f"foot.{sd}.y": 0.0, f"foot.{sd}.z": 0.0,
        })
    A.level_head(b, p, 2.0)
    return b


def fight_stance(p: dict) -> dict:
    """The alert stance the idle and the attacks share: left foot a little forward, right back
    and turned out, knees bent, weight between them, hands up off the thighs."""
    b = base_living(p)
    b.update({"hips.z": -0.035, "hips.y": 0.01, "hips.twist": -6.0, "chest.twist": 4.0, "spine.flex": 2.0,
              "foot.L.y": -0.13, "foot.L.x": 0.02, "foot.R.y": 0.12, "foot.R.x": -0.03, "foot.R.yaw": -14.0,
              "foot.L.yaw": 4.0})
    for sd, sx in SIDES:
        b[f"upper_arm.{sd}.flex"] = 6.0
        b[f"upper_arm.{sd}.abd"] = -32.0
        b[f"forearm.{sd}.flex"] = 26.0
        b[f"hand.{sd}.flex"] = 4.0
    A.level_head(b, p, 2.0)
    return b


def living_foot(pp: float, stance: float, travel: float, lift: float, kick: float, strike: float, toe_off: float):
    """Ankle offset (y, z), pitch and pivot for one foot; pp in [0, 1), 0 = foot strike. The stance
    foot moves back `travel` (so it is planted while the body moves forward at travel / stance
    time); the swing foot lifts `lift` and, running, kicks the heel up `kick` early in the swing."""
    if pp < stance:
        u = pp / stance
        y = -travel / 2 + travel * u
        if u < 0.18:                    # toes coming down after the strike
            return y, 0.0, strike * (1 - ease(u / 0.18)), -1.0 if strike > 0 else 0.0
        if u > 0.62:                    # heel rising onto the ball for the push-off
            return y, 0.0, toe_off * ease((u - 0.62) / 0.38, "in"), 1.0
        return y, 0.0, 0.0, 0.0
    u = (pp - stance) / (1 - stance)
    y = travel / 2 - travel * ease(u, "inout")
    z = lift * math.sin(math.pi * u) ** 0.8 + kick * math.sin(math.pi * min(1.0, u / 0.7)) ** 2 * (u < 0.7)
    # the toes trail at lift-off, level out, and come up for the next strike
    pitch = toe_off * (1 - ease(u / 0.3)) + strike * ease((u - 0.55) / 0.45)
    return y, z, pitch, (1.0 if u < 0.15 else 0.0)


def _legs(prm: dict, ph: float, cyc: float, speed: float, stance: float, lift: float, kick: float,
          strike: float, toe_off: float, bias: float, width: float, toe_bend: float) -> None:
    for sd, sx in SIDES:
        pp = (ph + (0.0 if sd == "L" else 0.5)) % 1.0
        travel = speed * cyc * stance
        y, z, pitch, pivot = living_foot(pp, stance, travel, lift, kick, strike, toe_off)
        prm[f"foot.{sd}.y"] = y + bias
        prm[f"foot.{sd}.z"] = z
        prm[f"foot.{sd}.pitch"] = pitch
        prm[f"foot.{sd}.pivot"] = pivot
        prm[f"foot.{sd}.x"] = -sx * width
        prm[f"toe.{sd}.bend"] = max(0.0, -pitch) * toe_bend


def _swing_arms(rig, prm: dict, fwd: dict, front, back, sag: float, pole) -> None:
    """Arm IK for the gait swing: each wrist moves between `back` (fwd = -1) and `front` (fwd = +1),
    offsets (out, y, z) from its posed shoulder (out is away from the midline, y forward is
    negative), dipping `sag` mid-swing like a pendulum; elbows towards `pole` (out, y, z)."""
    Q, off = rig.evaluate(prm)
    _, pos = rig.sk.fk(Q, off)
    s = rig.s
    for sd, sx in SIDES:
        u = 0.5 + 0.5 * fwd[sd]
        sh = pos[f"upper_arm.{sd}"]
        o = [b + (fr - b) * u for fr, b in zip(front, back)]
        prm[f"aik.{sd}"] = 1.0
        prm[f"hand.{sd}.tx"] = float(sh[0] + sx * o[0] * s)
        prm[f"hand.{sd}.ty"] = float(sh[1] + o[1] * s)
        prm[f"hand.{sd}.tz"] = float(sh[2] + (o[2] - sag * math.sin(math.pi * u)) * s)
        prm[f"elbow.{sd}.px"], prm[f"elbow.{sd}.py"], prm[f"elbow.{sd}.pz"] = sx * pole[0], pole[1], pole[2]


def _walk(rig, p: dict, n: int, cycles: int, wary: bool) -> list[dict]:
    base = base_living(p)
    seed = int(p.get("seed", 1))
    cyc = n / cycles / FPS
    out = []
    for f in range(n + 1):
        t = f / n
        ph = (t * cycles) % 1.0
        w = 2 * math.pi * ph
        prm = dict(base)
        _legs(prm, ph, cyc, WALK_SPEED, stance=0.6, lift=0.085 if not wary else 0.07, kick=0.0, strike=14.0,
              toe_off=-26.0, bias=0.05, width=0.012, toe_bend=0.7)
        # the body is lowest at each foot strike (ph 0, 0.5), highest over the planted foot
        low = 0.022 if not wary else 0.016
        prm["hips.z"] = (-0.030 if not wary else -0.050) - low * math.cos(2 * w)
        prm["hips.x"] = 0.018 * math.sin(w + 0.4)          # over the stance foot
        prm["hips.twist"] = 5.0 * math.cos(w)              # the swing leg's hip comes forward
        prm["hips.side"] = 2.5 * math.sin(w + 0.4)
        prm["hips.flex"] = 3.0 if not wary else 5.0
        prm["spine.flex"] = 1.0 if not wary else 3.0
        prm["spine.side"] = -1.5 * math.sin(w + 0.4)
        prm["chest.flex"] = (0.0 if not wary else 1.0) + 0.8 * math.cos(2 * w)
        prm["chest.twist"] = -7.0 * math.cos(w)            # shoulders against the hips
        prm["head.twist"] = 0.0
        if wary:                                           # scanning: a look left, then right
            prm["head.twist"] = 16.0 * math.sin(2 * math.pi * t) + 3.0 * loop_noise(seed + 7, f, n)
        # an arm swings with the opposite leg: the left leg strikes forward at ph 0 with the right
        # arm forward
        fwd = {sd: -sx * math.cos(w - 0.25) for sd, sx in SIDES}
        for sd, sx in SIDES:
            prm[f"shoulder.{sd}.fwd"] = 3.0 * fwd[sd] + (4.0 if wary else 0.0)
            prm[f"hand.{sd}.flex"] = 6.0 + 4.0 * fwd[sd]
        if not wary:
            _swing_arms(rig, prm, fwd, front=(0.03, -0.20, -0.56), back=(0.06, 0.16, -0.60), sag=0.03,
                        pole=(0.25, 1.0, -0.1))
        else:
            _swing_arms(rig, prm, fwd, front=(0.04, -0.24, -0.46), back=(0.07, 0.06, -0.54), sag=0.02,
                        pole=(0.4, 1.0, -0.3))
        A.level_head(prm, p, 3.0 if not wary else 4.0)
        prm["head.flex"] += 1.5 * math.cos(2 * w + 0.6)
        out.append(prm)
    return out


def act_walk(rig, p, n=WALK_FRAMES):
    return _walk(rig, p, n, 1, False)


def act_walk_b(rig, p, n=WALK_B_FRAMES):
    return _walk(rig, p, n, 2, True)


def act_run(rig, p, n=RUN_FRAMES):
    base = base_living(p)
    cyc = n / FPS
    stance = 0.28
    out = []
    for f in range(n + 1):
        ph = (f / n) % 1.0
        w = 2 * math.pi * ph
        prm = dict(base)
        _legs(prm, ph, cyc, RUN_SPEED, stance=stance, lift=0.24, kick=0.20, strike=4.0, toe_off=-38.0,
              bias=0.08, width=0.004, toe_bend=0.75)
        # lowest at mid-stance (knee loaded), highest in the flight phase
        mid = 2 * math.pi * 2 * (ph - stance / 2)
        prm["hips.z"] = -0.030 - 0.016 * math.cos(mid)
        prm["hips.x"] = 0.008 * math.sin(w + 0.6)
        prm["hips.y"] = -0.02
        prm["hips.flex"] = 9.0
        prm["hips.twist"] = 9.0 * math.cos(w)
        prm["spine.flex"] = 5.0 + 1.5 * math.cos(mid)
        prm["chest.flex"] = 3.0
        prm["chest.twist"] = -14.0 * math.cos(w)
        prm["neck.flex"] = 0.0
        fwd = {sd: -sx * math.cos(w - 0.35) for sd, sx in SIDES}       # +1: this arm drives forward
        for sd, sx in SIDES:
            prm[f"shoulder.{sd}.fwd"] = 6.0 * fwd[sd]
            prm[f"shoulder.{sd}.shrug"] = 0.0
            prm[f"hand.{sd}.flex"] = 4.0
        # elbows at about a right angle: the hand comes up to the chest in front and goes back past
        # the hip, the elbow high behind
        _swing_arms(rig, prm, fwd, front=(-0.06, -0.30, -0.26), back=(0.06, 0.20, -0.46), sag=0.04,
                    pole=(0.3, 1.0, -0.45))
        A.level_head(prm, p, 4.0)
        prm["head.flex"] += 1.0 * math.cos(mid)
        out.append(prm)
    return out


def act_idle(rig, p, n=120):
    """Alert: breathing, the weight rocking between the feet, the head turning to look round and
    the hands flexing."""
    base = fight_stance(p)
    seed = int(p.get("seed", 1))
    out = []
    for f in range(n + 1):
        w = 2 * math.pi * f / n
        br = math.sin(3 * w)
        prm = dict(base)
        prm["hips.x"] = base.get("hips.x", 0.0) + 0.012 * math.sin(w)
        prm["hips.y"] = base["hips.y"] + 0.012 * math.sin(w + 1.1)
        prm["hips.z"] = base["hips.z"] - 0.005 * (0.5 + 0.5 * math.sin(2 * w))
        prm["hips.side"] = -1.6 * math.sin(w)
        prm["spine.side"] = 1.0 * math.sin(w)
        prm["chest.flex"] = base["chest.flex"] - 1.2 * br
        prm["chest.twist"] = base["chest.twist"] + 3.0 * loop_noise(seed, f, n, (1, 2))
        look = loop_noise(seed + 2, f, n, (1, 2))
        prm["head.twist"] = 22.0 * look
        prm["neck.flex"] = base["neck.flex"] + 1.0 * br
        prm["head.side"] = 2.0 * loop_noise(seed + 3, f, n, (1, 3))
        for sd, sx in SIDES:
            prm[f"shoulder.{sd}.shrug"] = base[f"shoulder.{sd}.shrug"] + 1.0 * br
            prm[f"upper_arm.{sd}.flex"] = base[f"upper_arm.{sd}.flex"] + 2.0 * math.sin(w - 0.5 + sx)
            prm[f"forearm.{sd}.flex"] = base[f"forearm.{sd}.flex"] + 4.0 * loop_noise(seed + 4 + int(sx > 0), f, n, (1, 2))
            prm[f"hand.{sd}.flex"] = base[f"hand.{sd}.flex"] + 6.0 * loop_noise(seed + 6 + int(sx > 0), f, n, (2, 3))
        A.level_head(prm, p, 2.0)
        prm["head.flex"] += 2.0 * loop_noise(seed + 9, f, n, (1, 2))
        out.append(prm)
    return out


def _arm(sd: str, w: float, out: float, y: float, z: float, pole=(0.8, 0.3, -0.3)) -> dict:
    """Key values for a hand placed by IK: weight `w` (0 = the FK arm), the wrist at (out, y, z)
    from the posed shoulder (out away from the midline, -y forward, metres for a 1.75 m body) and
    the elbow towards `pole` (out, y, z). See _arm_offsets."""
    return {f"armik.{sd}": w, f"arm.{sd}.out": out, f"arm.{sd}.y": y, f"arm.{sd}.z": z,
            f"elbow.{sd}.pout": pole[0], f"elbow.{sd}.py": pole[1], f"elbow.{sd}.pz": pole[2]}


# where a hanging hand is: keys at the stance use it so the offsets never pass through the shoulder
_REST_L = _arm("L", 0.0, 0.05, -0.10, -0.50)
_REST_R = _arm("R", 0.0, 0.05, -0.10, -0.50)


def _arm_offsets(rig, frames: list[dict]) -> list[dict]:
    """Turns the keyed hand offsets into arm IK targets on the posed body. With weight w < 1 the
    target is blended from where the FK arm puts the hand, so the IK comes in and goes out without
    a pop (the elbow's roll aside)."""
    s = rig.s
    for fr in frames:
        sides = [(sd, sx) for sd, sx in SIDES if fr.get(f"armik.{sd}", 0.0) > 1e-3]
        if not sides:
            continue
        fk = {k: v for k, v in fr.items() if not k.startswith("aik.")}
        Q, off = rig.evaluate(fk)
        _, pos = rig.sk.fk(Q, off)
        for sd, sx in sides:
            w = min(1.0, fr[f"armik.{sd}"])
            sh, hand = pos[f"upper_arm.{sd}"], pos[f"hand.{sd}"]
            tgt = sh + np.array([sx * fr[f"arm.{sd}.out"], fr[f"arm.{sd}.y"], fr[f"arm.{sd}.z"]]) * s
            t = hand * (1 - w) + tgt * w
            fr[f"aik.{sd}"] = 1.0
            fr[f"hand.{sd}.tx"], fr[f"hand.{sd}.ty"], fr[f"hand.{sd}.tz"] = (float(v) for v in t)
            fr[f"elbow.{sd}.px"] = sx * fr.get(f"elbow.{sd}.pout", 0.8)
    return frames


def act_attack_a(rig, p, n=24):
    """Overhead axe chop, right hand: weight back as the axe goes up over the head, then the weight
    onto the front foot and the hand brought straight down in front of the chest; the blow lands at
    frame 11 (Enemy deals the hit 45% into the clip)."""
    st = merged(fight_stance(p), _REST_L, _REST_R)
    wind = merged(st, {"hips.y": 0.05, "hips.z": -0.03, "hips.twist": -12.0, "spine.flex": -3.0, "chest.flex": -8.0,
                       "chest.twist": 14.0, "shoulder.R.shrug": 8.0,
                       "upper_arm.L.flex": 40.0, "upper_arm.L.abd": -22.0, "forearm.L.flex": 40.0},
                  _arm("R", 1.0, -0.04, 0.12, 0.40, (0.8, 0.2, 0.5)))
    strike = merged(st, {"hips.y": -0.09, "hips.z": -0.08, "hips.twist": 8.0, "hips.flex": 6.0, "spine.flex": 6.0,
                         "chest.flex": 10.0, "chest.twist": -12.0, "shoulder.R.fwd": 12.0,
                         "upper_arm.L.flex": -10.0, "upper_arm.L.abd": -30.0, "forearm.L.flex": 46.0},
                    _arm("R", 1.0, -0.14, -0.50, -0.26, (0.6, 0.4, -0.5)))
    follow = merged(strike, {"chest.flex": 13.0, "hips.z": -0.09}, _arm("R", 1.0, -0.12, -0.36, -0.46, (0.6, 0.4, -0.5)))
    ks = Keys(st, [(0, st), (7, wind, "out"), (11, strike, "in"), (14, follow, "out"), (24, st, "inout")])
    return _arm_offsets(rig, [ks.at(f) for f in range(n + 1)])


def act_attack_b(rig, p, n=24):
    """Spear thrust / throw: the right hand draws back above the shoulder while the left arm points
    at the target, then the hips and chest turn through and the arm drives forward to full
    extension (frames 13-16; the throw lets go at 0.55 s of the clip played at 0.9, frame 15)."""
    st = merged(fight_stance(p), _REST_L, _REST_R)
    draw = merged(st, {"hips.y": 0.07, "hips.z": -0.04, "hips.twist": -14.0, "chest.twist": 20.0,
                       "chest.flex": -6.0, "spine.flex": -2.0, "shoulder.R.shrug": 6.0},
                  _arm("R", 1.0, 0.10, 0.28, 0.10, (0.8, 0.3, -0.6)),
                  _arm("L", 1.0, -0.02, -0.52, -0.08, (0.8, 0.2, -0.6)))
    release = merged(st, {"hips.y": -0.11, "hips.z": -0.07, "hips.twist": 10.0, "hips.flex": 5.0, "chest.twist": -16.0,
                          "chest.flex": 8.0, "spine.flex": 5.0, "shoulder.R.fwd": 14.0},
                     _arm("R", 1.0, -0.04, -0.60, 0.04, (0.5, 0.3, -0.9)),
                     _arm("L", 1.0, 0.06, 0.12, -0.44, (0.8, 0.4, -0.2)))
    follow = merged(release, {"hips.z": -0.08, "chest.flex": 11.0},
                    _arm("R", 1.0, -0.10, -0.50, -0.20, (0.5, 0.3, -0.9)))
    ks = Keys(st, [(0, st), (9, draw, "out"), (14, release, "in"), (17, follow, "out"), (24, st, "inout")])
    return _arm_offsets(rig, [ks.at(f) for f in range(n + 1)])


def act_attack_structure(rig, p, n=30):
    """Hacking at a wall or door: two-handed overhead chops, one a second (loops)."""
    st = merged(fight_stance(p), _REST_L, _REST_R)
    up = merged(st, {"hips.y": 0.04, "hips.z": -0.04, "chest.flex": -6.0, "spine.flex": -2.0, "chest.twist": 10.0},
                _arm("R", 1.0, 0.0, 0.06, 0.36, (0.8, 0.2, 0.4)), _arm("L", 1.0, -0.30, 0.04, 0.32, (0.8, 0.2, 0.2)))
    down = merged(st, {"hips.y": -0.07, "hips.z": -0.08, "hips.flex": 6.0, "chest.flex": 10.0, "spine.flex": 6.0,
                       "chest.twist": -4.0},
                  _arm("R", 1.0, -0.10, -0.50, -0.26, (0.6, 0.4, -0.5)), _arm("L", 1.0, -0.22, -0.44, -0.22, (0.6, 0.4, -0.5)))
    lift = merged(down, _arm("R", 1.0, -0.06, -0.46, -0.10, (0.6, 0.4, -0.5)),
                  _arm("L", 1.0, -0.20, -0.40, -0.08, (0.6, 0.4, -0.5)))
    ks = Keys(st, [(0, down), (6, lift, "out"), (20, up, "inout"), (26, down, "in"), (30, down)])
    return _arm_offsets(rig, [ks.at(f) for f in range(n + 1)])


def actions_table() -> list:
    """The Hollowed table with the living clips in place of theirs and the Hollowed-only ones out."""
    living = {
        "idle": (120, True, act_idle),
        "walk": (WALK_FRAMES, True, act_walk),
        "walk_b": (WALK_B_FRAMES, True, act_walk_b),
        "run": (RUN_FRAMES, True, act_run),
        "attack_a": (24, False, act_attack_a),
        "attack_b": (24, False, act_attack_b),
        "attack_structure": (30, True, act_attack_structure),
    }
    out = []
    for name, nf, loop, fn in A.actions_table():
        if name in DROPPED:
            continue
        out.append((name, *living[name]) if name in living else (name, nf, loop, fn))
    return out


def build_all(arm_obj, skel, params: dict, only=None) -> dict:
    """char_anim.build_all over the living table; -> {name: seconds}."""
    rig = A.Rig(skel, params)
    lengths = {}
    for name, nf, loop, fn in actions_table():
        if only and name not in only:
            continue
        frames = fn(rig, params, nf)
        frames = A._ik_fk_handoff(rig, frames)
        frames = A._fk_ik_handoff(rig, frames)
        A.write_action(arm_obj, skel, name, A.bake_frames(rig, frames))
        lengths[name] = nf / FPS
    arm_obj.animation_data.action = None
    for pb in arm_obj.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    return lengths
