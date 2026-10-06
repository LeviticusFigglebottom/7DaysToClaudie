"""Camp structures: campfire, lean-to, bough bed, stake barricade, can chime, grill rack.
Origin bottom centre, front = -Y. Fir boughs are alpha cards (foliage shader) in a separate node.
The campfire, lean-to and bough bed (ADR-0035) use the building-log toolkit in structure_logs (split
and charred logs, rope lashings, the log bark).
params: kind, name, seed."""
from __future__ import annotations

import math

from mathutils import Matrix, Vector

from generators import structure_logs as L
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


def _bough_layer(th, r, base, d, nrm, length, width, *, droop=0.05, curl=0.12):
    K.card(th, base, d, nrm, length, width, mat="item_fir_bough", droop=droop, nu=2, nv=3, curl=curl)


def campfire(p):
    """Stone ring (1.4 m) round a bed of ash and charcoal; half-burnt split logs collapsed toward the
    centre (bark outside, charred and glowing toward the heart), scattered embers; a tripod of three
    lashed poles (~1.3 m) with a pot hook and a hanging pot, and a stick spit on two forked stakes."""
    seed = int(p["seed"])
    r = common.rng(seed)
    parts = []
    n = 11
    for k in range(n):
        a = 2 * math.pi * k / n + r.uniform(-0.08, 0.08)
        rad = 0.46 + r.uniform(-0.03, 0.03)
        sx, sy, sz = r.uniform(0.19, 0.27), r.uniform(0.14, 0.19), r.uniform(0.1, 0.15)
        st = _decimated_pebble(f"stone{k}", (sx, sy, sz), seed + k, "item_stone_fire", (0, 0, 0), tris=150, lump=0.22, flat=0.4)
        st.data.transform(Matrix.Translation((math.cos(a) * rad, math.sin(a) * rad, -0.02)) @ Matrix.Rotation(a + math.pi / 2, 4, "Z") @
                          Matrix.Rotation(r.uniform(-0.15, 0.15), 4, "X"))
        parts.append(st)
    mb = K.MB()
    # ash bed: a low irregular mound, grey ash over charcoal crumbs
    K.lathe(mb, [(0.4, -0.005), (0.36, 0.012), (0.27, 0.026), (0.16, 0.036), (0.06, 0.04), (0.01, 0.041)], segments=24, mat="item_ash",
            cap_bottom=False, cap_top=True, radial_fn=lambda k, i, rr, z: 1.0 + 0.08 * math.sin(k * 1.9 + seed) + 0.04 * math.sin(k * 4.3))
    # half-burnt split logs collapsed toward the centre: bark ends outward, charred ends in the coals
    for k in range(6):
        a = 2 * math.pi * k / 6 + r.uniform(-0.25, 0.25)
        out = Vector((math.cos(a) * r.uniform(0.36, 0.44), math.sin(a) * r.uniform(0.36, 0.44), 0.05))
        tip = Vector((math.cos(a + 2.8) * 0.04, math.sin(a + 2.8) * 0.04, r.uniform(0.12, 0.22) if k % 2 else 0.06))
        length = (tip - out).length
        mb.push(L.axis_matrix(out, tip) @ Matrix.Rotation(r.uniform(-0.6, 0.6) + (math.pi if k % 3 == 0 else 0.0), 4, "X"))
        L.half_log(mb, length, r.uniform(0.045, 0.06), seed + 30 + k, sides=7, steps=4, depth=0.95,
                   flat_mat="item_wood_charred", end_mat="struct_log_end", char_from=r.uniform(0.65, 0.85), char_mat="item_wood_charred",
                   ember_tip="ember_glow")
        mb.pop()
    # two round billets lying across, charred in the middle
    for k in range(2):
        a = r.uniform(0, 6.28)
        c = Vector((r.uniform(-0.06, 0.06), r.uniform(-0.06, 0.06), 0.085 + 0.03 * k))
        d = Vector((math.cos(a), math.sin(a), 0.0)) * 0.27
        pts = [c - d, c - d * 0.33, c + d * 0.33, c + d]
        rr = r.uniform(0.032, 0.04)
        K.tube(mb, pts[:2], [rr, rr * 0.95], sides=7, mat="item_bark", cap_mat="item_wood_end", cap_uv="disc", caps=(True, False))
        K.tube(mb, pts[1:3], [rr * 0.95, rr * 0.7], sides=7, mat="item_wood_charred", caps=(False, False))
        K.tube(mb, pts[2:], [rr * 0.7, rr * 0.9], sides=7, mat="item_wood_charred", cap_mat="ember_glow", cap_uv="disc", caps=(False, True))
    # tripod: three poles crossing just under the apex, lashed, feet between the ring stones
    apex = Vector((0.0, 0.03, 1.27))
    feet = []
    for k in range(3):
        a = math.radians(90 + 120 * k) + r.uniform(-0.08, 0.08)
        foot = Vector((math.cos(a) * 0.64, math.sin(a) * 0.64, -0.03))
        feet.append(foot)
        d = (apex - foot).normalized()
        L.pole(mb, foot, apex + d * r.uniform(0.1, 0.16), 0.024, 0.019, seed + 70 + k, n=5, bend=0.012, sides=7)
    K.lashing(mb, apex - Vector((0, 0, 0.05)), apex + Vector((0, 0, 0.04)), 0.045, cord=0.005, turns=5, per_turn=10, sides=4,
              mat="item_rope", seed=seed + 80, wobble=0.002)
    # pot hook: a cord from the apex to a hooked branch, a blackened pot on it
    hook_top = Vector((0.0, 0.03, 0.86))
    K.tube(mb, [apex - Vector((0, 0, 0.04)), hook_top], 0.004, sides=4, mat="item_rope")
    L.pole(mb, hook_top, hook_top - Vector((0.0, 0.0, 0.2)), 0.012, 0.011, seed + 81, n=3, bend=0.0, sides=6)
    stub = hook_top - Vector((0.0, 0.0, 0.2))
    L.pole(mb, stub, stub + Vector((0.035, 0.0, 0.045)), 0.009, 0.007, seed + 82, n=2, bend=0.0, sides=5)
    pot_top = stub + Vector((0.03, 0.0, 0.0)) - Vector((0, 0, 0.07))
    mb.push(Matrix.Translation(pot_top - Vector((0.0, 0.0, 0.14))))
    K.lathe(mb, [(0.06, 0.0), (0.075, 0.01), (0.085, 0.07), (0.083, 0.13), (0.087, 0.136), (0.08, 0.136), (0.077, 0.02)], segments=16,
            mat="item_steel_dark", cap_bottom=True, cap_top=True, cap_mat_top="item_stew")
    bail = [Vector((0.087 * math.cos(t), 0.0, 0.12 + 0.07 * math.sin(t))) for t in [math.pi * i / 10 for i in range(11)]]
    K.tube(mb, bail, 0.0025, sides=4, mat="item_steel_tool")
    mb.pop()
    # spit: two forked stakes either side, a peeled stick across resting in the forks
    spy = 0.16
    for k, sx in enumerate((-0.56, 0.56)):
        base = Vector((sx, spy, -0.06))
        fork = Vector((sx + r.uniform(-0.01, 0.01), spy, 0.56))
        L.pole(mb, base, fork, 0.022, 0.018, seed + 90 + k, n=4, sides=7, caps=(False, False))
        for sgn in (1, -1):
            K.stick(mb, [fork - Vector((0, 0, 0.02)), fork + Vector((sgn * 0.035, 0.0, 0.08))], 0.014, 0.01, sides=5, seed=seed + 92 + k,
                    bark="item_bark_twig", caps=(False, True))
    K.stick(mb, [Vector((-0.68, spy, 0.585)), Vector((0.0, spy + 0.005, 0.58)), Vector((0.66, spy, 0.585))], 0.012, 0.011, sides=6,
            seed=seed + 95, bark="item_wood_raw")
    ash = mb.build("campfire_wood", sharp_deg=55)
    parts.append(ash)
    # coals: charcoal while cold, glowing near the heart while the fire burns (ember_glow: StructurePiece
    # lights them with the fire, ADR-0023); a few stray embers out on the ash
    for k in range(24):
        a, d = r.uniform(0, 6.28), r.uniform(0.0, 0.32)
        glow = d < 0.17 or k % 5 == 0
        ch = _decimated_pebble(f"coal{k}", (r.uniform(0.025, 0.055), r.uniform(0.02, 0.04), r.uniform(0.015, 0.03)), seed + 60 + k,
                               "ember_glow" if glow else "item_charcoal", (math.cos(a) * d, math.sin(a) * d, 0.035 - d * 0.08), tris=36,
                               subdiv=1, lump=0.3)
        parts.append(ch)
    col = K.collider_hull("campfire", parts[:n], max_faces=40)
    return parts, {"colliders": [col], "keep_xy": True}


def lean_to(p):
    """Forked uprights carrying a lashed ridge pole; leaning poles down to the ground at the back with
    lashed purlins across them (the stick lattice), thatched with dense, shingled fir boughs in three
    layers; a bough floor inside. Open front (-Y)."""
    seed = int(p["seed"])
    r = common.rng(seed)
    mb = K.MB()
    ridge_y, ridge_z = -0.95, 1.78
    # forked uprights
    for k, x in enumerate((-1.12, 1.12)):
        base = Vector((x, ridge_y, -0.05))
        crotch = Vector((x + r.uniform(-0.02, 0.02), ridge_y, ridge_z - 0.06))
        L.pole(mb, base, crotch, 0.05, 0.042, seed + k)
        for sgn in (1, -1):
            tip = crotch + Vector((r.uniform(-0.02, 0.02), sgn * 0.11, 0.17))
            K.stick(mb, [crotch - Vector((0, 0, 0.03)), crotch.lerp(tip, 0.5), tip], 0.028, 0.019, sides=7, seed=seed + 5 + k, lumpy=0.05)
        L.bind(mb, crotch - Vector((0, 0, 0.06)), (0, 0, 1), 0.05, seed + 7 + k, turns=4, cord=0.005, width=0.06)
    # ridge pole lying in the forks, lashed
    L.pole(mb, (-1.3, ridge_y, ridge_z + 0.035), (1.3, ridge_y, ridge_z + 0.035), 0.05, 0.042, seed + 9, n=8, bend=0.015)
    for k, x in enumerate((-1.12, 1.12)):
        L.cross_lash(mb, (x, ridge_y, ridge_z + 0.03), (1, 0, 0), (0, 0.35, 1), 0.058, seed + 11 + k, cord=0.0055)
    # leaning poles from the ridge down to the ground at the back
    back_y = 1.18
    poles = []
    for k in range(11):
        x = -1.1 + 2.2 * k / 10 + r.uniform(-0.03, 0.03)
        top = Vector((x, ridge_y - 0.1, ridge_z + 0.1))
        bot = Vector((x + r.uniform(-0.05, 0.05), back_y + r.uniform(-0.04, 0.04), -0.03))
        L.pole(mb, bot, top, 0.03, 0.022, seed + 20 + k, n=6)
        poles.append((bot, top))
        if k % 2 == 0:
            L.bind(mb, Vector((x, ridge_y + 0.02, ridge_z + 0.08)), (1, 0, 0), 0.06, seed + 120 + k, turns=3, cord=0.0045, width=0.05)
    # cross purlins lashed across the poles (the lattice the boughs hang on)
    for j, f in enumerate((0.22, 0.45, 0.66, 0.85)):
        a = poles[0][0].lerp(poles[0][1], f) + Vector((-0.1, 0.0, 0.03))
        b = poles[-1][0].lerp(poles[-1][1], f) + Vector((0.1, 0.0, 0.03))
        L.pole(mb, a, b, 0.022, 0.018, seed + 40 + j, n=6)
        for k in (0, 5, 10):
            q = poles[k][0].lerp(poles[k][1], f) + Vector((0, 0, 0.03))
            L.bind(mb, q, (b - a), 0.03, seed + 140 + j * 11 + k, turns=3, cord=0.004, width=0.04, mat="item_cordage")
    wood = mb.build("lean_to", sharp_deg=55)
    # bough thatch: shingled rows from the eave up (each row overlaps the one below), stems up-slope,
    # tips down-slope, three layers so the roof reads solid from inside and out
    th = K.MB()
    top_pt = Vector((0.0, ridge_y - 0.1, ridge_z + 0.12))
    bot_pt = Vector((0.0, back_y + 0.05, -0.02))
    slope = (bot_pt - top_pt).normalized()
    nrm = Vector((0.0, slope.z, -slope.y))
    if nrm.z < 0:
        nrm = -nrm
    span = (bot_pt - top_pt).length
    rows = 9
    for layer in range(3):
        for row in range(rows):
            f = (row + 0.25 + 0.4 * layer) / rows
            if f > 1.0:
                continue
            per = 9 + (row + layer) % 2
            for k in range(per):
                x = -0.97 + 1.94 * (k + 0.5) / per + r.uniform(-0.05, 0.05)
                # rows end where the tips reach the eave (the poles' foot), not past it into the ground
                fb = f * (1.0 - 0.8 / span) - 0.02
                base = top_pt + slope * (span * fb) + Vector((x, 0, 0)) + nrm * (0.04 + 0.025 * layer + r.uniform(0, 0.015))
                d = (slope + Vector((r.uniform(-0.12, 0.12), 0, 0))).normalized()
                K.card(th, base, d, nrm, r.uniform(0.62, 0.78), r.uniform(0.46, 0.56), mat="item_fir_bough", droop=0.05, nu=2, nv=3,
                       curl=0.14, twist=r.uniform(-0.2, 0.2))
    # ridge cap: boughs laid over the ridge, hanging a little down the front
    for k in range(8):
        x = -0.95 + 1.9 * k / 7 + r.uniform(-0.04, 0.04)
        base = Vector((x, ridge_y + 0.12, ridge_z + 0.1))
        K.card(th, base, (r.uniform(-0.15, 0.15), -1.0, -0.6), (0, -0.5, 1), r.uniform(0.32, 0.4), r.uniform(0.36, 0.44), mat="item_fir_bough",
               droop=0.08, nu=2, nv=3, curl=0.1)
    # bough floor inside: two overlapping layers, stems toward the back
    for layer in range(2):
        for row in range(4):
            for k in range(5):
                x = -0.95 + 1.9 * (k + 0.5 * ((row + layer) % 2)) / 5 + r.uniform(-0.05, 0.05)
                y = -0.6 + 0.42 * row + r.uniform(-0.05, 0.05)
                base = Vector((x, y + 0.3, 0.025 + 0.02 * layer))
                K.card(th, base, (r.uniform(-0.3, 0.3), -1.0, 0.02), (0, 0, 1), r.uniform(0.6, 0.72), r.uniform(0.42, 0.52), mat="item_fir_bough",
                       droop=-0.015, nu=2, nv=3, curl=0.12)
    thatch = th.build("thatch", sharp_deg=None)
    roof = K.collider_box("lean_to_roof", (-1.25, -0.08, -0.04), (1.25, 0.08, 2.8))
    ang = math.atan2(ridge_z, back_y - ridge_y)
    roof.data.transform(Matrix.Translation((0, (ridge_y + back_y) / 2, ridge_z / 2)) @ Matrix.Rotation(math.pi / 2 - ang, 4, "X") @
                        Matrix.Translation((0, 0, -1.4)))
    return [wood], {"foliage": [thatch], "colliders": [roof], "keep_xy": True}


def bough_bed(p):
    """A lashed log frame (two side logs, two cross logs resting on them, corner stakes) packed with
    four layers of fir boughs, a rolled hide pillow tied with cord at the head (+Y)."""
    seed = int(p["seed"])
    r = common.rng(seed)
    mb = K.MB()
    for k, x in enumerate((-0.38, 0.38)):
        L.pole(mb, (x, -0.99, 0.06), (x, 0.99, 0.062), 0.06, 0.054, seed + k, n=7, bend=0.012)
    for k, y in enumerate((-0.86, 0.86)):
        L.pole(mb, (-0.45, y, 0.155), (0.45, y, 0.15), 0.045, 0.042, seed + 3 + k, n=5, bend=0.008)
        for x in (-0.38, 0.38):
            L.cross_lash(mb, (x, y, 0.105), (0, 1, 0), (1, 0, 0), 0.06, seed + 20 + k * 3 + int(x > 0), cord=0.0045)
    for k, (x, y) in enumerate(((-0.45, -0.96), (0.45, -0.96), (-0.45, 0.96), (0.45, 0.96))):
        L.pole(mb, (x, y, -0.06), (x * 1.0, y, 0.2), 0.022, 0.018, seed + 30 + k, n=3, bend=0.0)
    # rolled hide pillow at the head, tied with two cords
    py, pz, pr = 0.72, 0.19, 0.062
    prof = []
    for k in range(14):
        a = 2 * math.pi * k / 14
        lip = 1.0 + (0.08 if 0.2 < a < 1.3 else 0.0)        # the outer turn's edge
        prof.append((math.cos(a) * lip, math.sin(a) * lip * 0.82))
    K.tube(mb, [Vector((-0.3, py, pz)), Vector((-0.1, py + 0.01, pz + 0.004)), Vector((0.1, py + 0.01, pz + 0.004)), Vector((0.3, py, pz))],
           [pr * 0.92, pr, pr, pr * 0.92], profile=prof, mat="struct_hide", cap_mat="struct_hide", up=Vector((0, 0, 1)))
    for k, x in enumerate((-0.17, 0.17)):
        loop = [Vector((x, py + math.cos(t) * pr * 1.04, pz + math.sin(t) * pr * 0.86)) for t in [2 * math.pi * i / 14 for i in range(14)]]
        K.tube(mb, loop, 0.0035, sides=4, mat="item_cordage", closed=True, up=Vector((1, 0, 0)))
    frame = mb.build("bough_bed", sharp_deg=55)
    th = K.MB()
    for layer in range(4):
        for k in range(9):
            for side in (-1, 1):
                y = -0.4 + 1.3 * (k + 0.5 * (layer % 2)) / 9
                x = side * 0.13 + r.uniform(-0.04, 0.04)
                base = Vector((x, y + 0.08, 0.08 + layer * 0.03))
                d = Vector((side * r.uniform(0.0, 0.18), -1.0, 0.0)).normalized()
                K.card(th, base, d, (0, 0, 1), r.uniform(0.5, 0.58), r.uniform(0.3, 0.36), mat="item_fir_bough", droop=-0.03, nu=2, nv=3,
                       curl=-0.14 if layer % 2 else 0.1)
    bed = th.build("boughs", sharp_deg=None)
    col = K.collider_box("bough_bed", (-0.47, -1.0, 0.0), (0.47, 1.0, 0.22))
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
