"""Camp structures: campfire, lean-to, bough bed, stake barricade, can chime, grill rack.
Origin bottom centre, front = -Y. Fir boughs are alpha cards (foliage shader) in a separate node.
params: kind, name, seed."""
from __future__ import annotations

import math

from mathutils import Matrix, Vector

from lib import common, item_kit as K, item_props as P


def _cord_v(r):
    return 1.0 / (2 * math.pi * r) / 3


def _decimated_pebble(name, size, seed, mat, center, tris=150, subdiv=3, lump=0.12, flat=0.3):
    o = K.pebble(name, size, seed, mat=mat, subdiv=subdiv, lump=lump, flat_bottom=flat, center=center)
    if common.triangle_count(o) > tris:
        mod = o.modifiers.new("dec", "DECIMATE")
        mod.ratio = tris / common.triangle_count(o)
        common.apply_modifiers(o)
        common.shade_smooth(o, angle_deg=60.0)
    return o


def _pole(mb, a, b, r0, r1, seed, *, bark="item_bark_twig", n=6, bend=0.01, sides=8, caps=(True, True)):
    a, b = Vector(a), Vector(b)
    d = b - a
    side = d.orthogonal().normalized()
    rr = common.rng(seed)
    ph = rr.uniform(0, 6.28)
    pts = [a + d * (i / (n - 1)) + side * bend * math.sin(i / (n - 1) * math.pi + ph) for i in range(n)]
    return K.stick(mb, pts, r0, r1, sides=sides, seed=seed, bark=bark, caps=caps, lumpy=0.04)


def _bind(mb, center, axis, radius, seed, turns=4, cord=0.004):
    c = Vector(center)
    ax = Vector(axis).normalized() * 0.025
    K.lashing(mb, c - ax, c + ax, radius, cord=cord, turns=turns, per_turn=9, sides=4, mat="item_cordage", seed=seed)


def campfire(p):
    seed = int(p["seed"])
    r = common.rng(seed)
    parts = []
    n = 11
    for k in range(n):
        a = 2 * math.pi * k / n + r.uniform(-0.08, 0.08)
        rad = 0.44 + r.uniform(-0.03, 0.03)
        sx, sy, sz = r.uniform(0.18, 0.26), r.uniform(0.13, 0.18), r.uniform(0.09, 0.14)
        st = _decimated_pebble(f"stone{k}", (sx, sy, sz), seed + k, "item_stone_fire", (0, 0, 0), tris=150, lump=0.22, flat=0.4)
        st.data.transform(Matrix.Translation((math.cos(a) * rad, math.sin(a) * rad, -0.015)) @ Matrix.Rotation(a + math.pi / 2, 4, "Z"))
        parts.append(st)
    mb = K.MB()
    # ash bed + ring of scorched earth
    K.lathe(mb, [(0.38, 0.0), (0.33, 0.012), (0.2, 0.022), (0.08, 0.028), (0.02, 0.029)], segments=20, mat="item_ash", cap_bottom=False,
            cap_top=True, radial_fn=lambda k, i, rr, z: 1.0 + 0.06 * math.sin(k * 1.9 + seed))
    # collapsed teepee of charred sticks (charred inner half, bark outer half)
    for k in range(7):
        a = 2 * math.pi * k / 7 + r.uniform(-0.2, 0.2)
        out = Vector((math.cos(a) * r.uniform(0.34, 0.5), math.sin(a) * r.uniform(0.34, 0.5), 0.02))
        top = Vector((math.cos(a + 2.6) * 0.05, math.sin(a + 2.6) * 0.05, r.uniform(0.16, 0.3)))
        mid = out.lerp(top, 0.45)
        rr = r.uniform(0.016, 0.026)
        K.stick(mb, [out, out.lerp(mid, 0.5), mid], rr, rr * 0.95, sides=7, seed=seed + 30 + k, caps=(True, False), lumpy=0.06)
        K.tube(mb, [mid, mid.lerp(top, 0.5), top], [rr * 0.95, rr * 0.8, rr * 0.35], sides=7, mat="item_wood_charred", caps=(False, True))
    ash = mb.build("ashbed", sharp_deg=55)
    parts.append(ash)
    for k in range(9):
        a, d = r.uniform(0, 6.28), r.uniform(0.0, 0.22)
        ch = _decimated_pebble(f"coal{k}", (r.uniform(0.03, 0.06), r.uniform(0.025, 0.045), r.uniform(0.02, 0.035)), seed + 60 + k,
                               "item_charcoal", (math.cos(a) * d, math.sin(a) * d, 0.012), tris=40, subdiv=1, lump=0.25)
        parts.append(ch)
    col = K.collider_hull("campfire", parts[:n], max_faces=40)
    return parts, {"colliders": [col], "keep_xy": True}


def lean_to(p):
    seed = int(p["seed"])
    r = common.rng(seed)
    mb = K.MB()
    ridge_y, ridge_z = -0.95, 1.78
    # forked uprights
    for k, x in enumerate((-1.12, 1.12)):
        base = Vector((x, ridge_y, -0.05))
        crotch = Vector((x + r.uniform(-0.02, 0.02), ridge_y, ridge_z - 0.06))
        _pole(mb, base, crotch, 0.045, 0.038, seed + k)
        for sgn in (1, -1):
            tip = crotch + Vector((r.uniform(-0.02, 0.02), sgn * 0.11, 0.17))
            K.stick(mb, [crotch - Vector((0, 0, 0.03)), crotch.lerp(tip, 0.5), tip], 0.026, 0.018, sides=7, seed=seed + 5 + k, lumpy=0.05)
    # ridge pole lying in the forks, lashed
    _pole(mb, (-1.32, ridge_y, ridge_z + 0.035), (1.32, ridge_y, ridge_z + 0.035), 0.048, 0.04, seed + 9, n=8, bend=0.015)
    for k, x in enumerate((-1.12, 1.12)):
        _bind(mb, (x, ridge_y, ridge_z + 0.03), (0, 0.6, 1), 0.06, seed + 11 + k, turns=4)
    # leaning poles from the ridge down to the ground at the back
    back_y = 1.18
    poles = []
    for k in range(9):
        x = -1.08 + 2.16 * k / 8 + r.uniform(-0.04, 0.04)
        top = Vector((x, ridge_y - 0.12, ridge_z + 0.12))
        bot = Vector((x + r.uniform(-0.05, 0.05), back_y + r.uniform(-0.05, 0.05), -0.03))
        _pole(mb, bot, top, 0.03, 0.022, seed + 20 + k, n=6)
        poles.append((bot, top))
    # two cross purlins lashed across the poles
    for f in (0.35, 0.68):
        a = poles[0][0].lerp(poles[0][1], f) + Vector((-0.08, 0.0, 0.03))
        b = poles[-1][0].lerp(poles[-1][1], f) + Vector((0.08, 0.0, 0.03))
        _pole(mb, a, b, 0.022, 0.018, seed + 40 + int(f * 10), n=6)
    wood = mb.build("lean_to", sharp_deg=55)
    # bough thatch: shingled rows, stems up-slope, tips down-slope; plus a bough bed inside
    th = K.MB()
    slope = (Vector((0, back_y, 0)) - Vector((0, ridge_y, ridge_z))).normalized()
    nrm = Vector((0, -slope.z, slope.y)) * -1
    if nrm.z < 0:
        nrm = -nrm
    rows = 6
    for layer in range(2):
        for row in range(rows):
            f = (row + 0.55 + 0.45 * layer) / (rows + 0.3)
            for k in range(8):
                x = -1.05 + 2.1 * k / 7 + r.uniform(-0.06, 0.06) + (0.13 if (row + layer) % 2 else 0.0)
                if abs(x) > 1.22:
                    continue
                base = Vector((x, ridge_y + (back_y - ridge_y) * (f - 0.16), ridge_z * (1 - (f - 0.16)))) + nrm * (0.055 + 0.012 * row + 0.03 * layer)
                d = (slope + Vector((r.uniform(-0.18, 0.18), 0, 0))).normalized()
                K.card(th, base, d, nrm, r.uniform(0.6, 0.72), r.uniform(0.48, 0.58), mat="item_fir_bough", droop=0.04, nu=2, nv=3,
                       curl=0.12)
    for k in range(4):
        base = Vector((-0.6 + 0.4 * k, -0.2 + r.uniform(-0.1, 0.1), 0.03))
        K.card(th, base, (r.uniform(-0.2, 0.2), 1, 0.05), (0, 0, 1), 0.75, 0.42, mat="item_fir_bough", droop=-0.02, nu=2, nv=3, curl=0.15)
    thatch = th.build("thatch", sharp_deg=None)
    roof = K.collider_box("lean_to_roof", (-1.25, -0.08, -0.04), (1.25, 0.08, 2.8))
    ang = math.atan2(ridge_z, back_y - ridge_y)
    roof.data.transform(Matrix.Translation((0, (ridge_y + back_y) / 2, ridge_z / 2)) @ Matrix.Rotation(math.pi / 2 - ang, 4, "X") @
                        Matrix.Translation((0, 0, -1.4)))
    return [wood], {"foliage": [thatch], "colliders": [roof], "keep_xy": True}


def bough_bed(p):
    seed = int(p["seed"])
    r = common.rng(seed)
    mb = K.MB()
    for x in (-0.4, 0.4):
        _pole(mb, (x, -0.98, 0.06), (x, 0.98, 0.065), 0.062, 0.055, seed + int(x * 10), n=7, bend=0.012)
    for y in (-0.88, 0.88):
        _pole(mb, (-0.47, y, 0.135), (0.47, y, 0.13), 0.05, 0.046, seed + int(y * 10) + 5, n=5, bend=0.008)
    for (x, y) in ((-0.47, -0.88), (0.47, -0.88), (-0.47, 0.88), (0.47, 0.88)):
        _pole(mb, (x * 1.12, y + 0.06, -0.06), (x * 1.12, y + 0.06, 0.2), 0.022, 0.018, seed + int(x * 7 + y * 13), n=3, bend=0.0)
    frame = mb.build("bough_bed", sharp_deg=55)
    th = K.MB()
    for layer in range(3):
        for k in range(8):
            y = -0.82 + 1.64 * (k + 0.5 * (layer % 2)) / 8
            x = r.uniform(-0.2, 0.2)
            base = Vector((x, y + 0.1, 0.07 + layer * 0.045))
            d = Vector((r.uniform(-0.35, 0.35), -1.0, 0.0)).normalized()
            K.card(th, base, d, (0, 0, 1), r.uniform(0.55, 0.65), r.uniform(0.42, 0.5), mat="item_fir_bough", droop=-0.04, nu=2, nv=3,
                   curl=-0.12)
    bed = th.build("boughs", sharp_deg=None)
    col = K.collider_box("bough_bed", (-0.47, -1.0, 0.0), (0.47, 1.0, 0.2))
    return [frame], {"foliage": [bed], "colliders": [col], "keep_xy": True}


def spike_barrier(p):
    seed = int(p["seed"])
    r = common.rng(seed)
    mb = K.MB()
    _pole(mb, (-1.8, 0.12, 0.11), (1.8, 0.12, 0.11), 0.11, 0.1, seed, bark="item_bark", n=8, bend=0.02, sides=12)
    for k, x0 in enumerate((-1.44, -0.72, 0.0, 0.72, 1.44)):
        for sgn in (1, -1):
            base = Vector((x0 + sgn * 0.24, 0.30, -0.02))
            tip = Vector((x0 - sgn * 0.26 + r.uniform(-0.04, 0.04), -0.55 + r.uniform(-0.04, 0.04), 1.35 + r.uniform(-0.06, 0.06)))
            d = (tip - base)
            shaft_end = base + d * 0.84
            rr = r.uniform(0.05, 0.062)
            _pole(mb, base, shaft_end, rr, rr * 0.9, seed + 10 * k + (sgn > 0), n=6, bend=0.01, caps=(True, False))
            # sharpened, fire-hardened point
            K.tube(mb, [shaft_end, shaft_end.lerp(tip, 0.55)], [rr * 0.9, rr * 0.42], sides=8, mat="item_wood_raw", caps=(False, False),
                   smooth=False)
            K.tube(mb, [shaft_end.lerp(tip, 0.55), tip], [rr * 0.42, rr * 0.02], sides=8, mat="item_wood_charred", caps=(False, True),
                   smooth=False)
        cross = Vector((x0, -0.12, 0.65))
        _bind(mb, cross, (0, -0.85, 1.37), 0.085, seed + 50 + k, turns=4, cord=0.0045)
    obj = mb.build("spike_barrier", sharp_deg=55)
    col = K.collider_hull("spike_barrier", [obj], max_faces=48)
    return [obj], {"colliders": [col], "keep_xy": True}


def can_chime(p):
    seed = int(p["seed"])
    r = common.rng(seed)
    mb = K.MB()
    top_z = 0.58
    for x in (-1.0, 1.0):
        _pole(mb, (x, 0.0, -0.12), (x + r.uniform(-0.02, 0.02), 0.0, top_z + 0.04), 0.022, 0.019, seed + int(x * 3), n=4, bend=0.005)
        _bind(mb, (x, 0.0, top_z - 0.005), (0, 0, 1), 0.024, seed + 7, turns=3, cord=0.0028)
    cord = [Vector((-1.0 + 2.0 * t, 0.0, top_z - 0.07 * math.sin(math.pi * t))) for t in [i / 24 for i in range(25)]]
    K.tube(mb, cord, 0.0028, sides=5, mat="item_cordage", u_tile=1.0, v_scale=_cord_v(0.0028))
    R, H = 0.037, 0.105
    for k, x in enumerate((-0.42, -0.34, 0.28, 0.37, 0.45)):
        t = (x + 1.0) / 2.0
        cz = top_z - 0.07 * math.sin(math.pi * t)
        hang = r.uniform(0.07, 0.13)
        top = Vector((x, 0.0, cz))
        bottom_of_can = top + Vector((0, 0, -hang))
        K.tube(mb, [top, top.lerp(bottom_of_can, 0.5) + Vector((0.004, 0, 0)), bottom_of_can], 0.0016, sides=4, mat="item_cordage")
        # can hangs upside down by its punched bottom, swinging a little
        m = Matrix.Translation(bottom_of_can) @ Matrix.Rotation(r.uniform(-0.15, 0.15), 4, "Y") @ Matrix.Rotation(math.pi, 4, "X") @ \
            Matrix.Rotation(r.uniform(0, 6.28), 4, "Z")
        mb.push(m)
        P.can(mb, R, H, label=None, seed=seed + k, state="open", dent=0.0, segments=12, beads=False, simple=True)
        mb.pop()
    obj = mb.build("can_chime", sharp_deg=50)
    return [obj], {"keep_xy": True}


def grill(p):
    seed = int(p["seed"])
    r = common.rng(seed)
    parts = []
    for side in (-1, 1):
        z = 0.0
        for k in range(3):
            h = r.uniform(0.09, 0.12)
            st = _decimated_pebble(f"slab{side}{k}", (r.uniform(0.2, 0.26), r.uniform(0.3, 0.38), h), seed + k + (side > 0) * 10,
                                   "item_stone_fire", (side * 0.39 + r.uniform(-0.02, 0.02), r.uniform(-0.02, 0.02), z), tris=140,
                                   lump=0.08, flat=0.45)
            parts.append(st)
            z += h * 0.88
    top = 0.31
    mb = K.MB()
    # iron grate: frame + bars
    frame = [Vector((-0.44, -0.24, top)), Vector((0.44, -0.24, top)), Vector((0.44, 0.24, top)), Vector((-0.44, 0.24, top))]
    K.tube(mb, K.polyline_resample(frame + [frame[0]], 17)[:-1], 0.007, sides=6, mat="item_steel_dark", closed=True)
    for k in range(10):
        x = -0.4 + 0.8 * k / 9
        K.tube(mb, [Vector((x, -0.24, top + 0.004)), Vector((x, 0.24, top + 0.004))], 0.0045, sides=5, mat="item_steel_dark")
    # fire bed under the grate
    K.lathe(mb, [(0.25, 0.0), (0.2, 0.012), (0.08, 0.02), (0.02, 0.021)], segments=16, mat="item_ash", cap_bottom=False, cap_top=True)
    for k in range(3):
        a = r.uniform(-0.5, 0.5) + k * 1.0
        out = Vector((math.cos(a) * 0.24, math.sin(a) * 0.2, 0.02))
        K.tube(mb, [out, out * 0.2 + Vector((0, 0, 0.04))], [0.018, 0.014], sides=6, mat="item_wood_charred")
    # dented steel pot with a bail handle on the grate
    mb.push(Matrix.Translation((0.1, 0.02, top + 0.012)))
    K.lathe(mb, [(0.07, 0.0), (0.078, 0.008), (0.082, 0.1), (0.086, 0.106), (0.08, 0.106), (0.076, 0.012), (0.06, 0.01)], segments=20,
            mat="item_steel_dark", regions=[(4, 6, "item_rust", "metric")], cap_bottom=True, cap_top=True, cap_mat_top="item_stew")
    bail = [Vector((0.082 * math.cos(t), 0.0, 0.1 + 0.07 * math.sin(t))) for t in [math.pi * i / 12 for i in range(13)]]
    K.tube(mb, bail, 0.0025, sides=5, mat="item_steel_tool")
    mb.pop()
    parts.append(mb.build("grill", sharp_deg=50))
    col = K.collider_box("grill", (-0.55, -0.25, 0.0), (0.55, 0.25, top + 0.02))
    return parts, {"colliders": [col], "keep_xy": True}


BUILDERS = {"campfire": campfire, "lean_to": lean_to, "bough_bed": bough_bed, "spike_barrier": spike_barrier, "can_chime": can_chime,
            "grill": grill}


def build(params: dict, outputs: list[str]) -> None:
    parts, opts = BUILDERS[params["kind"]](params)
    K.publish(outputs, name=params.get("name", params["kind"]), parts=parts, seed=int(params["seed"]), settle_deg=None,
              keep_xy=opts.get("keep_xy", True), foliage=opts.get("foliage", ()), colliders=opts.get("colliders", ()),
              separate=opts.get("separate", ()), pivot_bottom=opts.get("pivot_bottom", ()), wear_deg=35.0, ao_samples=16,
              drop=False)
