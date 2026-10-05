"""Game taken in the valley (ADR-0027): venison and hare, raw and roast, a rolled deer hide, a hare
pelt, sinew and rawhide strips. Ground pickups: origin bottom centre, settled resting pose.
params: kind, name, seed."""
from __future__ import annotations

import math

from mathutils import Matrix, Vector, noise

from lib import common, item_kit as K


def _haunch(name, size, seed, mat, fat=None, center=(0, 0, 0)):
    """A lumpy cut of muscle; with `fat`, a thin cap of fat over its top."""
    parts = [K.pebble(name, size, seed, mat=mat, subdiv=3, flat_bottom=0.35, lump=0.22, center=center)]
    if fat:
        cap = K.pebble(name + "_fat", (size[0] * 0.92, size[1] * 0.8, size[2] * 0.55), seed + 3, mat=fat, subdiv=2,
                       flat_bottom=0.6, lump=0.18, center=(center[0] + size[0] * 0.04, center[1] + size[1] * 0.08, center[2] + size[2] * 0.38))
        parts.append(cap)
    return parts


def venison(p, cooked=False):
    seed = int(p["seed"])
    meat = "item_meat_cooked" if cooked else "item_meat_raw"
    parts = _haunch("cut", (0.17, 0.11, 0.055), seed, meat, None if cooked else "item_meat_fat")
    mb = K.MB()
    # the leg bone's knuckle sticking out of one end
    end = Vector((0.085, 0.006, 0.026))
    K.tube(mb, [end - Vector((0.03, 0, 0)), end + Vector((0.03, 0, 0.004))], [0.011, 0.012], sides=9,
           mat="item_bone" if not cooked else "item_wood_charred", caps=(False, True))
    knob = K.pebble("knuckle", (0.026, 0.03, 0.026), seed + 5, mat="item_bone", subdiv=2, lump=0.12,
                    center=(end.x + 0.034, end.y, end.z - 0.013))
    parts += [mb.build("bone", sharp_deg=None), knob]
    return parts, {}


def hare_meat(p, cooked=False):
    seed = int(p["seed"])
    r = common.rng(seed)
    meat = "item_meat_cooked" if cooked else "item_meat_raw_lean"
    parts = []
    if cooked:
        mb = K.MB()
        pts = [Vector((-0.16 + 0.32 * i / 7, 0.0, 0.006)) for i in range(8)]
        K.stick(mb, pts, 0.0052, 0.0045, sides=7, seed=seed, lumpy=0.05)
        parts.append(mb.build("spit", sharp_deg=60))
        for k, x in enumerate((-0.045, 0.03)):
            h = K.pebble(f"leg{k}", (0.075, 0.042, 0.034), seed + k * 11, mat=meat, subdiv=3, lump=0.2,
                         center=(x, r.uniform(-0.003, 0.003), 0.0))
            h.data.transform(Matrix.Translation((0, 0, -0.008)))
            parts.append(h)
        return parts, {}
    for k, (x, rot) in enumerate(((-0.02, 0.3), (0.03, -0.25))):
        h = K.pebble(f"leg{k}", (0.085, 0.045, 0.034), seed + k * 11, mat=meat, subdiv=3, lump=0.18, flat_bottom=0.4,
                     center=(x, k * 0.03 - 0.015, 0.0))
        h.data.transform(Matrix.Rotation(rot, 4, "Z"))
        parts.append(h)
        mb = K.MB()
        tip = Vector((x - 0.05 * math.cos(rot), k * 0.03 - 0.015 - 0.05 * math.sin(rot), 0.014))
        K.tube(mb, [tip, tip - Vector((0.025 * math.cos(rot), 0.025 * math.sin(rot), 0))], [0.005, 0.0045], sides=7,
               mat="item_bone", caps=(False, True))
        parts.append(mb.build(f"bone{k}", sharp_deg=None))
    return parts, {}


def deer_hide(p):
    """Rolled hair-in and tied with a thong: the flesh side outside, a spiral of hair at the ends."""
    seed = int(p["seed"])
    noise.seed_set(seed)
    mb = K.MB()
    L, R = 0.34, 0.062
    n_a, n_l = 20, 10
    rings = []
    for i in range(n_l + 1):
        x = -L / 2 + L * i / n_l
        ring = []
        for j in range(n_a + 1):
            a = math.tau * j / n_a
            w = 1.0 + 0.07 * noise.noise(Vector((a * 0.8, x * 12, 0.3))) + 0.04 * math.sin(a * 3 + x * 9)
            ring.append(mb.vert((x, math.cos(a) * R * w, R + math.sin(a) * R * w * 0.85)))
        rings.append(ring)
    for i in range(n_l):
        for j in range(n_a):
            uv = ((i / n_l * L * 3, j / n_a), ((i + 1) / n_l * L * 3, j / n_a), ((i + 1) / n_l * L * 3, (j + 1) / n_a), (i / n_l * L * 3, (j + 1) / n_a))
            mb.face((rings[i][j], rings[i + 1][j], rings[i + 1][j + 1], rings[i][j + 1]), uv, "item_hide_flesh")
    # the ends: a spiral of hair and hide
    for side, ring in ((-1, rings[0]), (1, rings[-1])):
        c = mb.vert((side * L / 2 + side * 0.004, 0.0, R))
        for j in range(n_a):
            q = (ring[j], ring[j + 1], c) if side < 0 else (ring[j + 1], ring[j], c)
            mb.face(q, None, "item_hide_hair", True)
    obj = mb.build("hide", sharp_deg=None)
    tie = K.MB()
    for x in (-0.09, 0.09):
        pts = [Vector((x, math.cos(a) * (R + 0.003), R + math.sin(a) * (R + 0.003) * 0.85)) for a in [math.tau * k / 16 for k in range(17)]]
        K.tube(tie, pts, 0.0035, sides=5, mat="item_rawhide")
    return [obj, tie.build("thong", sharp_deg=None)], {"settle": None}


def hare_pelt(p):
    seed = int(p["seed"])
    noise.seed_set(seed)
    mb = K.MB()

    def pos(u, v):
        x = (u - 0.5) * 0.26
        y = (v - 0.5) * 0.16 * (1.0 - 0.35 * abs(u - 0.5) * 2)
        z = 0.004 + 0.01 * noise.noise(Vector((u * 3, v * 3, 0.5))) + 0.012 * max(0.0, u - 0.8) * 5
        return (x, y, z)
    K.sheet(mb, 12, 8, pos, thickness=0.006, mat_top="item_pelt_hair", mat_bottom="item_hide_flesh",
            uv_top=lambda u, v: (u * 0.26 * 4, v * 0.16 * 4), uv_bottom=lambda u, v: (u * 0.26, v * 0.16))
    return [mb.build("pelt", sharp_deg=None)], {"settle": None}


def sinew(p):
    seed = int(p["seed"])
    r = common.rng(seed)
    mb = K.MB()
    for k in range(9):
        y0 = r.uniform(-0.008, 0.008)
        z0 = r.uniform(0.002, 0.009)
        pts = [Vector((-0.12 + 0.24 * i / 8, y0 + 0.004 * math.sin(i * 0.9 + k), z0 + 0.002 * math.sin(i * 1.3 + k * 2))) for i in range(9)]
        K.tube(mb, pts, [0.0018 * (1 - 0.4 * abs(i / 8 - 0.5) * 2) + 0.0006 for i in range(9)], sides=5, mat="item_sinew", caps=(True, True))
    K.lashing(mb, Vector((-0.02, 0, 0.006)), Vector((0.02, 0, 0.006)), 0.011, cord=0.0018, turns=4, per_turn=8)
    return [mb.build("sinew", sharp_deg=None)], {}


def rawhide_strips(p):
    mb = K.MB()
    pts = K.helix(Vector((0, 0, 0.004)), Vector((0, 0, 0.03)), 0.04, 3.2, per_turn=18)
    K.tube(mb, pts, 0.0028, sides=4, mat="item_rawhide", profile=K.rect_profile(3.2, 0.7, 0.1))
    return [mb.build("strips", sharp_deg=None)], {}


BUILDERS = {
    "venison": lambda p: venison(p, False), "venison_cooked": lambda p: venison(p, True),
    "hare": lambda p: hare_meat(p, False), "hare_cooked": lambda p: hare_meat(p, True),
    "deer_hide": deer_hide, "hare_pelt": hare_pelt, "sinew": sinew, "rawhide_strips": rawhide_strips,
}


def build(params: dict, outputs: list[str]) -> None:
    parts, opts = BUILDERS[params["kind"]](params)
    K.publish(outputs, name=params.get("name", params["kind"]), parts=parts, seed=int(params["seed"]),
              ground_rot=opts.get("ground"), settle_deg=opts.get("settle", 20.0), wear_deg=30.0, inset=opts.get("inset", True))
