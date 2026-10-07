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
  hit_front         a blow from the front: head and chest snap back, weight onto the back foot,
                    hands up to guard, back in the stance (14 frames; Enemy stuns for the length)
  hit_back          a blow from behind: shoved forward, the head whips, a glance back over the
                    shoulder, back in the stance (14 frames)
  stagger           rocked back, a stumbling step back with each foot, folded over the knees,
                    a shake of the head, two steps back in (30 frames)
  death_front       struck from behind: the knees go, onto the knees, pitches onto the face
  death_back        struck from the front: the knees buckle, sits down hard, over onto the back
                    (both 40 frames, flat on the ground at the Hollowed's places from frame 34)
drops the Hollowed-only ones (head loll / twitch idles, the hard limp, feeding, crawling, the
Keener's scream - none of which a tribe fighter plays, and idle_b / idle_c / walk_limp would be
picked as variants by EnemyVisual) and keeps the sleep / wake clips (the Ashen are never POI
sleepers, so nothing plays them; they are the Hollowed's).

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

# Clips that key their own IK -> FK leg handoff (_legs_fk), so char_anim's is not applied to them.
OWN_HANDOFF = ("death_front", "death_back")
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


# --- Hits, stagger, deaths ------------------------------------------------------------------
# A fit body takes a blow and recovers at once: the head and chest snap with it in two frames, the
# knees take the weight, the hands come up to guard and it is back in its stance. The clips start
# and end on fight_stance (the idle's) with FK arms, feet planted (IK) except where they step.

def _step(f: float, f0: float, f1: float, y0: float, y1: float, lift: float) -> tuple[float, float, float]:
    """A foot stepping from y0 to y1 between frames f0 and f1: (y, z, pitch). Toes up as it lands."""
    if f <= f0:
        return y0, 0.0, 0.0
    if f >= f1:
        return y1, 0.0, 0.0
    u = (f - f0) / (f1 - f0)
    y = y0 + (y1 - y0) * ease(u, "inout")
    z = lift * math.sin(math.pi * u)
    pitch = -12.0 * math.sin(math.pi * u) if y1 < y0 else 10.0 * math.sin(math.pi * u)
    return y, z, pitch


def _feet(prm: dict, st: dict, steps: dict, f: float) -> dict:
    """Puts each foot where its steps take it: steps {side: [(f0, f1, dy, lift), ...]} with dy
    relative to the foot's place in the stance, accumulating."""
    for sd, _ in SIDES:
        y = st.get(f"foot.{sd}.y", 0.0)
        z = pitch = 0.0
        for f0, f1, dy, lift in steps.get(sd, []):
            if f <= f0:
                break
            y, z, pitch = _step(f, f0, f1, y, y + dy, lift)
            if f < f1:
                break
        prm[f"ik.{sd}"] = 1.0
        prm[f"foot.{sd}.y"] = y
        prm[f"foot.{sd}.z"] = z
        prm[f"foot.{sd}.pitch"] = pitch
        prm[f"foot.{sd}.pivot"] = 0.0
    return prm


def _guard(d: dict, up: float = 1.0) -> dict:
    """Hands up in front of the chest, elbows in (a fighter covering up)."""
    for sd, sx in SIDES:
        d[f"upper_arm.{sd}.flex"] = 6.0 + 14.0 * up
        d[f"upper_arm.{sd}.abd"] = -32.0 - 8.0 * up
        d[f"upper_arm.{sd}.twist"] = -6.0 - 14.0 * up
        d[f"forearm.{sd}.flex"] = 26.0 + 94.0 * up
        d[f"hand.{sd}.flex"] = 4.0 + 6.0 * up
    return d


def act_hit(rig, p, n=14, front=True):
    """A blow lands: from the front (`hit_front`) the head and chest snap back and the weight rocks
    onto the back foot; from behind (`hit_back`) the body is shoved forward with the head whipping
    back and then round to look over the shoulder. Two frames to the peak, the knees take it, the
    hands come up to guard (frame 8) and it is back in its stance at the end (0.47 s at 30 fps)."""
    st = fight_stance(p)
    sg = 1.0 if front else -1.0
    if front:
        imp = {"hips.y": 0.055, "hips.z": -0.05, "hips.flex": -3.0, "spine.flex": -5.0, "chest.flex": -11.0,
               "neck.flex": -4.0, "head.flex": -6.0, "head.twist": 8.0, "head.side": -5.0, "chest.twist": 9.0,
               "jaw.open": 6.0}
        for sd, sx in SIDES:
            imp.update({f"shoulder.{sd}.shrug": 7.0, f"upper_arm.{sd}.flex": -10.0, f"upper_arm.{sd}.abd": -12.0,
                        f"forearm.{sd}.flex": 24.0, f"hand.{sd}.flex": -6.0})
    else:
        imp = {"hips.y": -0.06, "hips.z": -0.045, "hips.flex": 6.0, "spine.flex": 8.0, "chest.flex": 14.0,
               "neck.flex": -8.0, "head.flex": -14.0, "head.twist": -4.0, "chest.twist": -6.0, "jaw.open": 6.0}
        for sd, sx in SIDES:
            imp.update({f"shoulder.{sd}.shrug": 8.0, f"upper_arm.{sd}.flex": -18.0, f"upper_arm.{sd}.abd": -22.0,
                        f"forearm.{sd}.flex": 30.0, f"hand.{sd}.flex": -8.0})
    peak = A.add(merged(st, imp), {"hips.y": 0.012 * sg, "chest.flex": -3.0 * sg, "head.flex": 6.0}, 1.0)
    rec = _guard(merged(st, {"hips.y": 0.02 * sg, "hips.z": -0.06, "hips.flex": 3.0, "spine.flex": 3.0,
                             "chest.flex": 4.0, "neck.flex": 4.0}))
    if not front:      # glances back over the shoulder where the blow came from
        rec.update({"head.twist": 34.0, "chest.twist": 12.0, "hips.twist": st["hips.twist"] + 6.0})
    # the hands come down by the elbows dropping back (not by reaching out)
    drop = merged(rec, {f"upper_arm.{sd}.flex": -8.0 for sd, _ in SIDES}, {f"forearm.{sd}.flex": 48.0 for sd, _ in SIDES},
                  {"head.twist": rec.get("head.twist", 0.0) * 0.5, "chest.twist": (rec.get("chest.twist", 0.0) + st["chest.twist"]) * 0.5})
    ks = Keys(st, [(0, st), (2, merged(st, imp), "snap"), (4, peak, "out"), (8, rec, "inout"), (11, drop, "inout"),
                   (n, st, "inout")])
    frames = []
    for f in range(n + 1):
        prm = ks.at(f)
        if f >= 6:      # the gaze comes back to level as it recovers
            w = ease((f - 6) / (n - 6))
            want = dict(prm)
            A.level_head(want, p, 2.0)
            prm["head.flex"] = prm["head.flex"] * (1 - w) + want["head.flex"] * w
        frames.append(_feet(prm, st, {}, f))
    return frames


def act_stagger(rig, p, n=30):
    """Rocked by a heavy blow (or a charge into a wall): the head and chest thrown back and the arms
    flung out, the back foot stumbles a long step back to catch the weight, the front foot shuffles
    after it, the body folds forward over the knees to get its balance, shakes its head, and the two
    feet step back in to the stance (1.0 s)."""
    st = fight_stance(p)
    k1 = merged(st, {"hips.y": 0.08, "hips.z": -0.05, "hips.flex": -4.0, "spine.flex": -7.0, "chest.flex": -18.0,
                     "neck.flex": -6.0, "head.flex": -10.0, "head.twist": 10.0, "chest.twist": 12.0, "hips.side": -5.0,
                     "jaw.open": 8.0})
    for sd, sx in SIDES:
        k1.update({f"shoulder.{sd}.shrug": 10.0, f"upper_arm.{sd}.flex": 6.0, f"upper_arm.{sd}.abd": -12.0,
                   f"forearm.{sd}.flex": 30.0, f"hand.{sd}.flex": -10.0})
    # caught on the back foot, arms out wide for balance
    k2 = merged(k1, {"hips.y": 0.22, "hips.z": -0.09, "hips.flex": 2.0, "spine.flex": 0.0, "chest.flex": -2.0,
                     "neck.flex": 2.0, "head.flex": -6.0, "hips.side": 4.0, "chest.twist": 4.0, "jaw.open": 2.0})
    for sd, sx in SIDES:
        k2.update({f"upper_arm.{sd}.flex": 12.0, f"upper_arm.{sd}.abd": -4.0, f"forearm.{sd}.flex": 36.0})
    # folded forward over bent knees, the weight between the feet again
    k3 = merged(k2, {"hips.y": 0.26, "hips.z": -0.15, "hips.flex": 14.0, "spine.flex": 10.0, "chest.flex": 14.0,
                     "neck.flex": 6.0, "head.flex": 0.0, "head.twist": -8.0, "hips.side": 1.0, "chest.twist": -4.0})
    for sd, sx in SIDES:
        k3.update({f"upper_arm.{sd}.flex": 10.0, f"upper_arm.{sd}.abd": -22.0, f"forearm.{sd}.flex": 46.0})
    # rising, a shake of the head
    k4 = merged(k3, {"hips.y": 0.20, "hips.z": -0.08, "hips.flex": 6.0, "spine.flex": 4.0, "chest.flex": 4.0,
                     "neck.flex": 4.0, "head.flex": -2.0, "head.twist": 12.0})
    k5 = _guard(merged(st, {"hips.y": 0.08, "hips.z": -0.06, "head.twist": -6.0}), 0.6)
    ks = Keys(st, [(0, st), (3, k1, "snap"), (9, k2, "out"), (14, k3, "inout"), (19, k4, "inout"), (25, k5, "inout"),
                   (n, st, "inout")])
    # feet: R (back) a long step back, L shuffles after it, then L and R step back in
    steps = {"R": [(4, 9, 0.30, 0.10), (23, 28, -0.30, 0.08)],
             "L": [(9, 13, 0.16, 0.07), (19, 24, -0.16, 0.07)]}
    frames = []
    for f in range(n + 1):
        prm = ks.at(f)
        prm["head.twist"] += 10.0 * smooth_shake(f, 16, 24)
        if f >= 20:
            want = dict(prm)
            A.level_head(want, p, 2.0)
            w = ease((f - 20) / (n - 20))
            prm["head.flex"] = prm["head.flex"] * (1 - w) + want["head.flex"] * w
        frames.append(_feet(prm, st, steps, f))
    return frames


def smooth_shake(f: float, f0: float, f1: float) -> float:
    """A quick shake of the head: two swings inside [f0, f1], zero outside."""
    if f <= f0 or f >= f1:
        return 0.0
    u = (f - f0) / (f1 - f0)
    return math.sin(2 * math.pi * 2 * u) * math.sin(math.pi * u)


def _lying_back(rig) -> dict:
    """Dead on the back: flat, the pelvis LIE behind the origin, legs out with the knees a little
    up and apart, the head rolled to one side, arms flung out on the ground."""
    d = {"hips.flex": -86.0, "hips.z": -rig.pel_z + 0.16, "hips.y": 0.42, "hips.twist": -6.0, "hips.side": 3.0,
         "spine.flex": 3.0, "chest.flex": 2.0, "chest.twist": 4.0, "neck.flex": 10.0, "head.flex": -2.0,
         "head.twist": 34.0, "head.side": 8.0, "jaw.open": 7.0}
    for sd, sx in SIDES:
        d.update({f"ik.{sd}": 0.0, f"thigh.{sd}.flex": 6.0 if sd == "L" else 12.0, f"thigh.{sd}.abd": 9.0,
                  f"thigh.{sd}.twist": -12.0, f"shin.{sd}.flex": 8.0 if sd == "L" else 22.0,
                  f"foot.{sd}.pitch": -24.0, f"toe.{sd}.bend": 0.0,
                  f"shoulder.{sd}.shrug": 4.0, f"shoulder.{sd}.fwd": 0.0,
                  f"hand.{sd}.flex": 18.0})
    d.update({"upper_arm.L.flex": 4.0, "upper_arm.L.abd": -18.0, "upper_arm.L.twist": 30.0, "forearm.L.flex": 8.0,
              "upper_arm.R.flex": 0.0, "upper_arm.R.abd": -2.0, "upper_arm.R.twist": 80.0, "forearm.R.flex": 6.0})
    return d


def _lying_front(rig) -> dict:
    """Dead face down: flat, the pelvis in front of the origin, legs straight back with one knee
    drawn a little out, the face turned to the side, one arm under the body's side, one out."""
    d = {"hips.flex": 86.0, "hips.z": -rig.pel_z + 0.17, "hips.y": -0.42, "hips.twist": 7.0, "hips.side": 4.0,
         "spine.flex": -3.0, "chest.flex": -4.0, "chest.twist": -4.0, "neck.flex": -24.0, "head.flex": -6.0,
         "head.twist": 64.0, "head.side": 6.0, "jaw.open": 7.0}
    for sd, sx in SIDES:
        d.update({f"ik.{sd}": 0.0, f"thigh.{sd}.flex": 0.0 if sd == "L" else -6.0, f"thigh.{sd}.abd": 6.0 if sd == "L" else 16.0,
                  f"thigh.{sd}.twist": 10.0, f"shin.{sd}.flex": 4.0 if sd == "L" else 12.0,
                  f"foot.{sd}.pitch": -40.0, f"toe.{sd}.bend": 0.0,
                  f"shoulder.{sd}.shrug": 6.0, f"shoulder.{sd}.fwd": 0.0, f"hand.{sd}.flex": 14.0})
    d.update({"upper_arm.L.flex": -20.0, "upper_arm.L.abd": -22.0, "upper_arm.L.twist": -20.0, "forearm.L.flex": 6.0,
              "upper_arm.R.flex": -4.0, "upper_arm.R.abd": 30.0, "upper_arm.R.twist": 70.0, "forearm.R.flex": 12.0})
    return d


def _legs_fk(rig, prm: dict) -> dict:
    """FK leg angles (thigh flex / abd, shin flex) that put each ankle where the IK legs have it in
    a pose, solved numerically. Keyed on the last IK frame of a fall, the FK legs then interpolate
    from where the legs really are. (char_anim._ik_fk_handoff's measured knee angle comes out near
    straight for these deep buckles, so the legs swung through the ground; the deaths use this
    instead, see build_all.)"""
    sk = rig.sk
    Q, off = rig.evaluate(prm)
    _, pos = sk.fk(Q, off)
    fk = {k: v for k, v in prm.items()}
    out = {}
    names = ("thigh.{}.flex", "shin.{}.flex", "thigh.{}.abd")
    for sd, _ in SIDES:
        fk[f"ik.{sd}"] = 0.0
    for sd, _ in SIDES:
        want = pos[f"foot.{sd}"]
        keys = [n.format(sd) for n in names]
        x = np.array([40.0, 60.0, 0.0])

        def ankle(v):
            d = dict(fk)
            for k, val in zip(keys, v):
                d[k] = float(val)
            q, o = rig.evaluate(d)
            return sk.fk(q, o)[1][f"foot.{sd}"]
        for _ in range(25):
            a0 = ankle(x)
            r = a0 - want
            if float(np.linalg.norm(r)) < 1e-4:
                break
            J = np.zeros((3, 3))
            for i in range(3):
                dx = np.zeros(3)
                dx[i] = 0.5
                J[:, i] = (ankle(x + dx) - a0) / 0.5
            step = np.linalg.solve(J.T @ J + np.eye(3) * 1e-4, -J.T @ r)
            x = x + np.clip(step, -25.0, 25.0)
        out.update({k: float(v) for k, v in zip(keys, x)})
    return out


def act_death(rig, p, n=40, forward=True):
    """Killed standing. Struck from behind (`death_front`): shoved forward, the knees go, it drops
    onto its knees (frame 18) and pitches forward onto its face. Struck from the front
    (`death_back`): rocked back, the knees buckle, it sits down hard (frame 18) and goes over onto
    its back. The arms go limp and fall where they will; a small bounce as the chest lands
    (frames 26-31), then still. Both end flat on the ground (the pelvis 0.16 m up, 0.42 m in
    front of / behind the origin like the Hollowed's), held from frame 34. The feet stay planted
    (IK) to frame 18, so the knees fold over them and never pass through the ground; the FK legs
    of the fall then start from that solution (_legs_fk)."""
    st = fight_stance(p)
    pel_z = rig.pel_z
    sg = 1.0 if forward else -1.0
    imp = merged(st, {"hips.y": -0.06 * sg, "hips.z": -0.05, "hips.flex": 5.0 * sg, "spine.flex": 7.0 * sg,
                      "chest.flex": 14.0 * sg, "neck.flex": -8.0, "head.flex": -16.0, "head.twist": 8.0,
                      "chest.twist": 8.0, "jaw.open": 10.0})
    for sd, sx in SIDES:
        imp.update({f"shoulder.{sd}.shrug": 8.0, f"upper_arm.{sd}.flex": -14.0 if forward else 30.0,
                    f"upper_arm.{sd}.abd": -18.0, f"forearm.{sd}.flex": 30.0 if forward else 44.0})
    buckle = merged(st, {"hips.y": -0.05 * sg + (0.0 if forward else 0.06), "hips.z": -0.30, "hips.flex": 16.0 if forward else -6.0,
                         "spine.flex": 12.0 if forward else 2.0, "chest.flex": 14.0 if forward else 0.0,
                         "neck.flex": 18.0, "head.flex": 8.0, "head.side": 14.0, "head.twist": 4.0, "chest.twist": 2.0,
                         "jaw.open": 8.0})
    for sd, sx in SIDES:
        buckle.update({f"shoulder.{sd}.shrug": -4.0, f"upper_arm.{sd}.flex": 12.0, f"upper_arm.{sd}.abd": -26.0,
                       f"forearm.{sd}.flex": 18.0, f"hand.{sd}.flex": 16.0})
    if forward:
        # on its knees, slumping forward
        mid = {"hips.flex": 22.0, "hips.z": -pel_z + 0.50, "hips.y": -0.10, "hips.twist": 4.0, "spine.flex": 16.0,
               "chest.flex": 16.0, "neck.flex": 22.0, "head.flex": 10.0, "head.side": 12.0, "jaw.open": 8.0}
        for sd, sx in SIDES:     # knees on the ground, shins along it behind
            mid.update({f"ik.{sd}": 1.0, f"foot.{sd}.x": -sx * 0.03, f"foot.{sd}.y": 0.30 if sd == "L" else 0.36,
                        f"foot.{sd}.z": 0.04, f"foot.{sd}.yaw": 0.0, f"foot.{sd}.pitch": 0.0, f"foot.{sd}.pivot": 0.0,
                        f"upper_arm.{sd}.flex": 18.0, f"upper_arm.{sd}.abd": -28.0, f"forearm.{sd}.flex": 20.0})
        mid.update(_legs_fk(rig, merged(st, mid)))
        for sd, _ in SIDES:
            mid.update({f"ik.{sd}": 0.0, f"foot.{sd}.pitch": -45.0})
        end = _lying_front(rig)
    else:
        # sat down hard, going over backwards
        mid = {"hips.flex": -40.0, "hips.z": -pel_z + 0.21, "hips.y": 0.26, "hips.twist": -4.0, "spine.flex": 6.0,
               "chest.flex": 6.0, "neck.flex": 16.0, "head.flex": 6.0, "head.side": 10.0, "jaw.open": 8.0}
        for sd, sx in SIDES:     # feet out in front, knees up
            mid.update({f"ik.{sd}": 1.0, f"foot.{sd}.x": -sx * 0.06, f"foot.{sd}.y": -0.22 if sd == "L" else -0.12,
                        f"foot.{sd}.z": 0.0, f"foot.{sd}.yaw": sx * 8.0, f"foot.{sd}.pitch": 0.0, f"foot.{sd}.pivot": 0.0,
                        f"upper_arm.{sd}.flex": 30.0, f"upper_arm.{sd}.abd": -20.0, f"forearm.{sd}.flex": 30.0})
        mid.update(_legs_fk(rig, merged(st, mid)))
        for sd, _ in SIDES:
            mid.update({f"ik.{sd}": 0.0, f"foot.{sd}.pitch": 10.0})
        end = _lying_back(rig)
    bounce = merged(end, {"hips.z": end["hips.z"] + 0.025, "chest.flex": end["chest.flex"] - 5.0 * sg,
                          "neck.flex": end["neck.flex"] + (8.0 if not forward else -8.0)})
    ks = Keys(st, [(0, st), (3, imp, "snap"), (10, buckle, "inout"), (18, mid, "in"), (26, end, "in"), (29, bounce, "out"),
                   (34, end, "in"), (n, end)])
    frames = []
    for f in range(n + 1):
        prm = ks.at(f)
        for sd, _ in SIDES:
            prm[f"ik.{sd}"] = 1.0 if f <= 18 else 0.0
        frames.append(prm)
    return frames


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
        "hit_front": (14, False, lambda r, p, n: act_hit(r, p, n, True)),
        "hit_back": (14, False, lambda r, p, n: act_hit(r, p, n, False)),
        "stagger": (30, False, act_stagger),
        "death_front": (40, False, lambda r, p, n: act_death(r, p, n, True)),
        "death_back": (40, False, lambda r, p, n: act_death(r, p, n, False)),
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
        if name not in OWN_HANDOFF:
            frames = A._ik_fk_handoff(rig, frames)
        frames = A._fk_ik_handoff(rig, frames)
        A.write_action(arm_obj, skel, name, A.bake_frames(rig, frames))
        lengths[name] = nf / FPS
    arm_obj.animation_data.action = None
    for pb in arm_obj.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    return lengths
