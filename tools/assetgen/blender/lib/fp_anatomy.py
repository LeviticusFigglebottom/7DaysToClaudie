"""Anatomical check of the first-person hands (player report 5, ADR-0061): every key of every
fp_* action, solved as character_fp_arms bakes it, measured joint by joint.

Pure numpy (no Blender): tools/fp_hands_check.py runs it, the bake runs it
after solving and fails on a violation, so a pose that bends a finger past what a hand can do,
or pushes a digit at the lens, never ships.

Angles are flexion in degrees (+ curls toward the palm), measured from the posed bones: the
skeleton's rest curl included, so a limit is a real joint's.
"""
from __future__ import annotations

import math

import numpy as np

from . import char_fp as F

# What a working adult hand reaches (degrees of flexion; negative = hyperextension). The finger
# PIP is the joint that reads as "crooked": it does not hyperextend, and past ~105 degrees the
# middle phalanx folds flat onto the first. The DIP can go back a little; the thumb's IP more.
LIMITS = {
    "mcp": (-15.0, 90.0),
    "pip": (0.0, 105.0),
    "dip": (-8.0, 80.0),
    "th_mcp": (-10.0, 60.0),
    "th_ip": (-20.0, 80.0),
}
# Side swing at a finger's knuckle either way of its rest line (degrees).
ABDUCT_MAX = 25.0
# The nearest a digit's tip in view may come to the eye (m). The arms are drawn in the world's
# perspective: a thumb 0.2 m from the lens is drawn half again as big as the fingers at 0.3 m
# (the lighter's "massive thumb"). A tip outside the view (the bow's drawing hand at the cheek, a
# bottle's hand at the mouth) is not drawn and does not count. Exempt (action prefix -> hands):
# climbing hands reach up past the view, and a bow's string hand is drawn to the jaw past the eye.
NEAR_TIP = 0.20
NEAR_EXEMPT = {"fp_climb": "RL", "fp_draw_bow": "R", "fp_bow_drawn": "R", "fp_release_bow": "R"}
# The view the check uses: viewmodel.json `fov` (vertical, degrees) on a 16:9 screen.
VIEW_FOV = 58.0
VIEW_ASPECT = 16.0 / 9.0
# The thumb may be drawn at most this many times the index finger's width (end joints, as seen
# from the eye). Side by side an adult's is ~1.3; nearer the lens it grows. Report 5's lighter: 1.6.
LOOM_MAX = 1.5
# The thumb's end segment in view at least this far (degrees) off the line to the eye: nearer
# along it, the pad or tip is seen end-on (report 5's lighter thumb, aimed ~20 degrees off).
AIM_MIN = 35.0
# Until the tether-reading hand and the punch are re-posed, a thumb aimed at the eye is reported
# (prefixed WARN), not failed: see is_failure().
AIM_STRICT = False
WARN = "warn: "
# Neighbouring fingers may press together this far (m: skin gives), no further.
CROSS_MAX = 0.002
# A sliver past a limit is rounding, not a pose.
SLACK = 0.5


def _seg_dist(p1, q1, p2, q2):
    """(distance, s, t) between segments p1q1 and p2q2 at their closest points p1+s(q1-p1)..."""
    d1, d2, r = q1 - p1, q2 - p2, p1 - p2
    a, e, f = float(d1 @ d1), float(d2 @ d2), float(d2 @ r)
    c, b = float(d1 @ r), float(d1 @ d2)
    den = a * e - b * b
    s = min(1.0, max(0.0, (b * f - c * e) / den)) if den > 1e-12 else 0.0
    t = (b * s + f) / e
    if t < 0.0:
        t, s = 0.0, min(1.0, max(0.0, -c / a))
    elif t > 1.0:
        t, s = 1.0, min(1.0, max(0.0, (b - c) / a))
    return float(np.linalg.norm(p1 + d1 * s - p2 - d2 * t)), s, t


def _seen(p) -> float:
    """Distance (m) from the eye of a point in view; out of view, 9 (Blender: camera at the origin
    looking -Y, Z up). A fingertip's skin reaches ~1 cm past its joint: that much out still shows."""
    fwd = -float(p[1])
    if fwd <= 0.0:
        return 9.0
    t = math.tan(math.radians(VIEW_FOV) * 0.5)
    m = 0.01 / fwd
    if abs(float(p[2])) / fwd > t + m or abs(float(p[0])) / fwd > t * VIEW_ASPECT + m:
        return 9.0
    return float(np.linalg.norm(p))


def _rest_dir(sk, sd: str, key: str) -> np.ndarray:
    """A finger's metacarpal direction at rest (fp_joints' `d`): what its MCP bends from."""
    j = sk.j
    lo = F.FINGERS[key][0]
    return F._n(j[f"axis.{sd}"] + j[f"lat.{sd}"] * lo * 1.2)


def measure(sk, Q: dict) -> dict:
    """Per side: {"R.index.mcp": deg, ..., "R.index.abd": deg, "R.thumb.ip": deg,
    "R.tip.index": metres from the eye, ...} for one evaluated pose."""
    acc, pos = sk.fk(Q)
    out = {}

    def seg(b):
        # posed direction of bone b (head to tail) and its bend axis (posed x)
        R = acc[b] @ sk.rest[b]
        return R[:, 1], R[:, 0]

    def flex(parent_dir, child_dir, axis):
        # signed angle from parent to child about the bend axis; curling is a negative turn
        p = parent_dir - axis * float(parent_dir @ axis)
        c = child_dir - axis * float(child_dir @ axis)
        s = float(np.cross(p, c) @ axis)
        return -math.degrees(math.atan2(s, float(p @ c)))

    for sd, _ in F.SIDES:
        hand = acc[f"hand.{sd}"]
        for key, name in F.FINGER_BONES:
            d0 = hand @ _rest_dir(sk, sd, key)
            d1, x1 = seg(f"{name}_1.{sd}")
            d2, x2 = seg(f"{name}_2.{sd}")
            d3, x3 = seg(f"{name}_3.{sd}")
            out[f"{sd}.{name}.mcp"] = flex(d0, d1, x1)
            # sideways: the part of the first phalanx off the bend plane
            out[f"{sd}.{name}.abd"] = math.degrees(math.asin(max(-1.0, min(1.0, float(d1 @ x1)))) -
                                                   math.asin(max(-1.0, min(1.0, float(d0 @ x1)))))
            out[f"{sd}.{name}.pip"] = flex(d1, d2, x2)
            out[f"{sd}.{name}.dip"] = flex(d2, d3, x3)
            tip = sk.point(acc, pos, f"{name}_3.{sd}", sk.tail[f"{name}_3.{sd}"])
            out[f"{sd}.tip.{name}"] = _seen(tip)
        # Neighbouring fingers through each other: their middle and end phalanges as capsules
        # (the mesh's radii), overlap in metres (+ = into each other).
        caps = {}
        for key, name in F.FINGER_BONES:
            r = F.FINGER_SHAPE[key][0]
            pts = [pos[f"{name}_2.{sd}"], pos[f"{name}_3.{sd}"],
                   sk.point(acc, pos, f"{name}_3.{sd}", sk.tail[f"{name}_3.{sd}"])]
            caps[name] = [(pts[0], pts[1], r[1], r[2]), (pts[1], pts[2], r[2], r[3])]
        for a, b in zip(F.FINGER_NAMES[:-1], F.FINGER_NAMES[1:]):
            ov = -1.0
            for pa, qa, ra0, ra1 in caps[a]:
                for pb, qb, rb0, rb1 in caps[b]:
                    d, s, t = _seg_dist(pa, qa, pb, qb)
                    ov = max(ov, (ra0 + (ra1 - ra0) * s) + (rb0 + (rb1 - rb0) * t) - d)
            out[f"{sd}.cross.{a}_{b}"] = ov
        t1, _ = seg(f"thumb_1.{sd}")
        t2, x2 = seg(f"thumb_2.{sd}")
        t3, x3 = seg(f"thumb_3.{sd}")
        out[f"{sd}.thumb.mcp"] = flex(t1, t2, x2)
        out[f"{sd}.thumb.ip"] = flex(t2, t3, x3)
        tip = sk.point(acc, pos, f"thumb_3.{sd}", sk.tail[f"thumb_3.{sd}"])
        out[f"{sd}.tip.thumb"] = _seen(tip)
        # How much wider than the index finger the thumb is drawn: its end joint's width over its
        # distance from the eye, against the index finger's (the mesh and the pose together).
        # How square to the view ray the thumb's end segment lies (degrees, 90 = side-on): a
        # thumb aimed along the ray shows its round pad or tip head-on and foreshortening makes it
        # read huge whatever its width (the hub on report 5's lighter). 90 when out of view.
        ip3, tip3 = pos[f"thumb_3.{sd}"], tip
        seg3 = tip3 - ip3
        ray = tip3 / max(1e-9, float(np.linalg.norm(tip3)))
        c = abs(float(seg3 @ ray)) / max(1e-9, float(np.linalg.norm(seg3)))
        out[f"{sd}.aim.thumb"] = 90.0 if _seen(tip3) > 8.0 else math.degrees(math.acos(min(1.0, c)))
        # (A thumb out of view looms over nothing.)
        th_ip = _seen(pos[f"thumb_3.{sd}"])
        ix_dip = float(np.linalg.norm(pos[f"index_3.{sd}"]))
        out[f"{sd}.loom.thumb"] = 0.0 if th_ip > 8.0 else \
            (F.THUMB_RADII[2] / th_ip) / (F.FINGER_SHAPE["ix"][0][2] / ix_dip)
    return out


def violations(name: str, frame: int, m: dict) -> list[str]:
    """What in one measured pose is outside a hand's range."""
    bad = []
    for k, v in m.items():
        sd, part, joint = k.split(".")
        if part == "cross":
            if v > CROSS_MAX:
                bad.append(f"{name}@{frame} {sd} {joint.replace('_', ' and ')} {v * 1000:.0f} mm into each other")
            continue
        if part == "aim":
            if v < AIM_MIN:
                bad.append(f"{'' if AIM_STRICT else WARN}{name}@{frame} {sd} thumb aimed {v:.0f} deg off the view ray (min {AIM_MIN:.0f})")
            continue
        if part == "loom":
            if v > LOOM_MAX:
                bad.append(f"{name}@{frame} {sd} thumb drawn {v:.2f}x the index finger's width (max {LOOM_MAX:.2f})")
            continue
        if part == "tip":
            exempt = any(name.startswith(a) and sd in sides for a, sides in NEAR_EXEMPT.items())
            if not exempt and v < NEAR_TIP - 1e-4:
                bad.append(f"{name}@{frame} {sd} {joint} tip {v * 100:.1f} cm from the eye (min {NEAR_TIP * 100:.0f})")
            continue
        if joint == "abd":
            if abs(v) > ABDUCT_MAX + SLACK:
                bad.append(f"{name}@{frame} {sd}.{part} knuckle swung {v:.0f} deg (max {ABDUCT_MAX:.0f})")
            continue
        lo, hi = LIMITS[("th_" if part == "thumb" else "") + joint]
        if v < lo - SLACK or v > hi + SLACK:
            bad.append(f"{name}@{frame} {sd}.{part}.{joint} {v:.0f} deg (range {lo:.0f}..{hi:.0f})")
    return bad


def check(cfg: dict | None = None, params: dict | None = None, every: int = 1, only: tuple = ()):
    """(violations, {action: {measure: (min, max)}}) over every frame (every `every`th) of every action."""
    cfg = cfg if cfg is not None else F.load_config()
    sk = F.FPSkeleton(F.fp_joints(params or {}), params or {}, bones=F.FP_BONES)
    rig = F.FPRig(sk)
    solver = F.PoseSolver(rig, cfg.get("wrist"))
    bad: list[str] = []
    summary: dict = {}
    for name, n, _loop, frames in F.fp_actions(cfg):
        if only and not name.startswith(only):
            continue
        solver.reset()
        worst: dict = {}
        for i, hands in enumerate(frames):
            prm = solver.solve(hands)
            if i % every and i != len(frames) - 1:
                continue
            m = measure(sk, rig.evaluate(prm)[0])
            bad += violations(name, i, m)
            for k, v in m.items():
                lo, hi = worst.get(k, (v, v))
                worst[k] = (min(lo, v), max(hi, v))
        summary[name] = worst
    return bad, summary


def summarize(bad: list[str], limit: int = 40) -> list[str]:
    """Violations grouped per action and joint: "fp_x R.pinky.pip 144 deg (range 0..102) x12 frames"
    (the worst-looking first frame of each group kept), at most `limit` lines."""
    groups: dict = {}
    for b in bad:
        head, rest = b[len(WARN):].split(" ", 1) if b.startswith(WARN) else b.split(" ", 1)
        action = head.split("@")[0]
        what = " ".join(rest.split(" ")[:2])
        key = (action, what)
        if key not in groups:
            groups[key] = [b, 0]
        groups[key][1] += 1
    lines = [f"{first} (x{n} frames)" for first, n in groups.values()]
    return lines[:limit] + ([f"... {len(lines) - limit} more"] if len(lines) > limit else [])


def is_failure(v: str) -> bool:
    """A violation that fails the bake (not a warning)."""
    return not v.startswith(WARN)
