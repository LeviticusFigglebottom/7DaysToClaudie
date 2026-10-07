"""Climbable structures (ADR-0057): the hunting stand, the climbing rope's anchor, its knotted 1 m span
and the coiled rope item. Built from the building-log toolkit in structure_logs (bark poles, split-log
deck, rope lashings) so they sit with the log walls.

Frames (Blender, exported Z-up -> Godot Y-up; Godot +Z = Blender -Y), origin bottom centre:
  * hunting_stand: matches data/config/climbing.json `hunting_stand` (the game builds its collision
    from that, so keep them together): four legs at (+-1.06, +-1.06), a split-log deck whose top is
    3.0 m up over 2.4 x 2.4 m with a hatch x -0.45..0.45, z 0.25..1.2 (Godot) at the front, rails
    round it 1 m high, and a pole ladder inside the front of the frame: rails at x +-0.23, z 0.975
    (0.125 m behind the ladder's foot at z 1.1, toward the climber at -Z), rungs every 0.3 m.
  * climbing_rope: the anchor: a stake driven in just behind the origin (Godot +Z) with the rope
    hitched round it and a short tail toward -Z (the game draws the rope from there over the edge).
  * climbing_rope_span: 1 m of rope up Godot +Y from the origin with two hand-hold knots; the game
    repeats it down the drop.
  * climbing_rope_coil: the item: a coil of knotted rope lying flat with the stake through it.
params: kind, name, seed."""
from __future__ import annotations

import math
import random

from mathutils import Matrix, Vector

from generators import structure_logs as L
from lib import item_kit as K

ROPE = "item_rope"
DECK_TOP, HALF, TH = 3.0, 1.2, 0.14
HATCH = (-0.45, 0.45, 0.25, 1.2)
LEG = 1.06
LADDER_Z, LADDER_X = 1.1 - 0.125, 0.23


def G(x: float, y: float, z: float) -> Vector:
    """Godot piece-local -> Blender."""
    return Vector((x, -z, y))


def hunting_stand(p, outputs):
    seed = int(p["seed"])
    r = random.Random(seed)
    mb = K.MB()
    under = DECK_TOP - TH
    # legs, splayed a little at the foot, running on up as the rail posts
    for k, (sx, sz) in enumerate(((-1, -1), (1, -1), (-1, 1), (1, 1))):
        L.pole(mb, G(sx * (LEG + 0.06), -0.05, sz * (LEG + 0.06)), G(sx * LEG, DECK_TOP + 1.0, sz * LEG), 0.085, 0.07, seed + k,
               sides=10, n=6, bend=0.01)
        # knee braces from the leg up to the sills
        a = G(sx * (LEG + 0.03), 2.05, sz * (LEG + 0.03))
        b = G(sx * (LEG - 0.55), under - 0.12, sz * (LEG + 0.01))
        L.pole(mb, a, b, 0.045, 0.04, seed + 10 + k, sides=8, n=4)
        b2 = G(sx * (LEG + 0.01), under - 0.12, sz * (LEG - 0.55))
        L.pole(mb, a, b2, 0.045, 0.04, seed + 14 + k, sides=8, n=4)
    # sills along X front and back, joists along Z either side of the hatch
    for k, sz in enumerate((-1, 1)):
        L.pole(mb, G(-HALF - 0.05, under - 0.07, sz * LEG), G(HALF + 0.05, under - 0.07, sz * LEG), 0.07, 0.065, seed + 20 + k,
               sides=10, n=6, bend=0.008)
        for sx in (-1, 1):
            L.cross_lash(mb, G(sx * LEG, under - 0.07, sz * LEG), (0, 0, 1), (1, 0, 0), 0.08, seed + 22 + k * 2 + (sx > 0))
    for k, x in enumerate((-LEG, HATCH[0] - 0.06, HATCH[1] + 0.06, LEG)):
        L.pole(mb, G(x, under - 0.02, -HALF), G(x, under - 0.02, HALF), 0.05, 0.048, seed + 30 + k, sides=8, n=6)
    # the deck: split logs across X, flat face up at DECK_TOP, cut round the hatch
    n = 12
    w = 2 * HALF / n
    for i in range(n):
        zc = -HALF + w * (i + 0.5)
        spans = [(-HALF, HALF)]
        if HATCH[2] < zc < HATCH[3]:
            spans = [(-HALF, HATCH[0]), (HATCH[1], HALF)]
        for j, (x0, x1) in enumerate(spans):
            mb.push(Matrix.Translation(G((x0 + x1) / 2 + r.uniform(-0.01, 0.01), DECK_TOP, zc)) @
                    Matrix.Rotation(r.uniform(-0.01, 0.01), 4, "Z"))
            L.half_log(mb, (x1 - x0) + r.uniform(-0.02, 0.02), w * 0.52, seed + 40 + i * 2 + j, sides=8, steps=3)
            mb.pop()
    # rails: a top and a middle rail round the four sides, lashed outside the posts
    for k, (y, rr) in enumerate(((DECK_TOP + 0.95, 0.04), (DECK_TOP + 0.5, 0.034))):
        e = LEG + 0.08
        for j, (a, b) in enumerate(((G(-e, y, -e), G(e, y, -e)), (G(-e, y, e), G(e, y, e)),
                                    (G(-e, y, -e), G(-e, y, e)), (G(e, y, -e), G(e, y, e)))):
            L.pole(mb, a, b, rr, rr * 0.9, seed + 70 + k * 4 + j, sides=8, n=6, bend=0.012)
        for sx in (-1, 1):
            for sz in (-1, 1):
                L.bind(mb, G(sx * (LEG + 0.04), y, sz * (LEG + 0.04)), (0, 0, 1), 0.08, seed + 80 + k * 4 + (sx > 0) * 2 + (sz > 0),
                       turns=3, cord=0.005, width=0.05, per_turn=7)
    # the pole ladder: rails from the ground to a hand's height over the deck, lashed rungs
    top = DECK_TOP + 0.9
    for k, sx in enumerate((-1, 1)):
        L.pole(mb, G(sx * LADDER_X, -0.04, LADDER_Z), G(sx * LADDER_X, top, LADDER_Z), 0.04, 0.035, seed + 90 + k, sides=8, n=6,
               bend=0.004)
        L.bind(mb, G(sx * LADDER_X, under - 0.07, LADDER_Z + 0.06), (0, 0, 1), 0.05, seed + 92 + k, turns=4, cord=0.005, width=0.06)
    y = 0.3
    k = 0
    while y < DECK_TOP - 0.1:
        L.pole(mb, G(-LADDER_X - 0.05, y, LADDER_Z), G(LADDER_X + 0.05, y + r.uniform(-0.01, 0.01), LADDER_Z), 0.022, 0.02,
               seed + 100 + k, sides=7, n=3, bend=0.0)
        for sx in (-1, 1):
            L.bind(mb, G(sx * LADDER_X, y, LADDER_Z), (1, 0, 0), 0.03, seed + 130 + k * 2 + (sx > 0), turns=2, cord=0.004,
                   width=0.03, per_turn=6, mat="item_cordage")
        y += 0.3
        k += 1
    L.finish(outputs, "hunting_stand", [mb.build("hunting_stand", sharp_deg=55)], seed, ground=True, ao_samples=16)


def _knot(mb: K.MB, c: Vector, axis: Vector, r: float) -> None:
    """A hand-hold overhand knot: a fat twisted bulge round the rope."""
    axis = axis.normalized()
    side = axis.cross(Vector((1, 0, 0)) if abs(axis.x) < 0.9 else Vector((0, 1, 0))).normalized()
    up = axis.cross(side)
    pts = []
    for i in range(25):
        t = i / 24 * 2 * math.pi * 1.5
        pts.append(c + axis * (0.018 * math.sin(t * 0.66)) + side * (math.cos(t) * r * 1.4) + up * (math.sin(t) * r * 1.4))
    K.tube(mb, pts, r * 0.95, sides=6, mat=ROPE, caps=(True, True))


def _rope_line(mb: K.MB, pts, r: float = 0.012) -> None:
    K.tube(mb, K.polyline_resample([Vector(q) for q in pts], max(4, len(pts) * 4)), r, sides=7, mat=ROPE, twist=6.0)


def climbing_rope(p, outputs):
    seed = int(p["seed"])
    mb = K.MB()
    # stake leaning back from the edge, the rope hitched round it, a tail toward the edge (-Z)
    L.pole(mb, G(0.0, -0.12, 0.16), G(0.0, 0.3, 0.1), 0.028, 0.024, seed, sides=8, n=3)
    for t in range(3):
        pts = [G(math.cos(2 * math.pi * i / 12) * 0.036, 0.1 + t * 0.022 + 0.008 * math.sin(2 * math.pi * i / 12),
                 0.125 + math.sin(2 * math.pi * i / 12) * 0.036) for i in range(12)]
        K.tube(mb, pts, 0.011, sides=6, mat=ROPE, closed=True)
    _rope_line(mb, [G(0.0, 0.12, 0.09), G(0.0, 0.07, 0.03), G(0.0, 0.06, -0.05)])
    # the tail end, coiled loose beside the stake
    for t in range(3):
        rr = 0.12 - t * 0.012
        pts = [G(0.2 + math.cos(2 * math.pi * i / 16) * rr, 0.012 + t * 0.02, 0.15 + math.sin(2 * math.pi * i / 16) * rr) for i in range(16)]
        K.tube(mb, pts, 0.011, sides=6, mat=ROPE, closed=True)
    L.finish(outputs, "climbing_rope", [mb.build("climbing_rope", sharp_deg=55)], seed, ground=True, ao_samples=12)


def climbing_rope_span(p, outputs):
    seed = int(p["seed"])
    mb = K.MB()
    _rope_line(mb, [G(0, 0, 0), G(0, 0.5, 0), G(0, 1.0, 0)])
    for y in (0.25, 0.75):
        _knot(mb, G(0, y, 0), Vector((0, 0, 1)), 0.012)
    L.finish(outputs, "climbing_rope_span", [mb.build("climbing_rope_span", sharp_deg=55)], seed, ground=False, ao_samples=8)


def climbing_rope_coil(p, outputs):
    seed = int(p["seed"])
    r = random.Random(seed)
    mb = K.MB()
    for t in range(6):
        rr = 0.17 + r.uniform(-0.01, 0.01)
        ph = r.uniform(0, 6.28)
        pts = [G(math.cos(ph + 2 * math.pi * i / 20) * rr, 0.013 + (t % 3) * 0.02, math.sin(ph + 2 * math.pi * i / 20) * rr * 0.92)
               for i in range(20)]
        K.tube(mb, pts, 0.012, sides=6, mat=ROPE, closed=True)
    for k, a in enumerate((0.3, 2.4, 4.4)):
        _knot(mb, G(math.cos(a) * 0.17, 0.035, math.sin(a) * 0.17 * 0.92), Vector((-math.sin(a), math.cos(a), 0)), 0.012)
    # binding round the coil and the stake laid across it
    L.bind(mb, G(0.17, 0.035, 0.0), (0, 1, 0), 0.04, seed + 1, turns=3, cord=0.006, width=0.04)
    L.pole(mb, G(-0.24, 0.07, 0.05), G(0.26, 0.07, -0.02), 0.026, 0.022, seed + 2, sides=8, n=3)
    L.finish(outputs, "climbing_rope_coil", [mb.build("climbing_rope_coil", sharp_deg=55)], seed, ground=True, ao_samples=12)


BUILDERS = {"hunting_stand": hunting_stand, "climbing_rope": climbing_rope, "climbing_rope_span": climbing_rope_span,
            "climbing_rope_coil": climbing_rope_coil}


def build(params: dict, outputs: list[str]) -> None:
    BUILDERS[params["kind"]](params, outputs)
