"""Gardens and rain collection (ADR-0049): the garden bed and rain catcher structures, every stage of the
garden crops, the dead plant, and the garden items (seed packets and twists, seed potatoes, produce, the
baked potato, the bucket full and empty).

Frames (Blender Z-up, exported to Godot Y-up; front faces Blender -Y = Godot +Z):
  * garden_bed: 2.4 x 1.1 m, one course of building logs (crown 0.17) round a soil fill whose surface
    is at z = 0.33 (the def's size.y 0.36 minus FarmVisual.SOIL_DROP 0.03); origin bottom centre. The
    game puts its four plots in a row along X at (i + 0.5) / 4 - 0.5 of 0.88 x 2.4 m.
  * rain_catcher: a hollowed log barrel (r 0.36, 0.8 m) under a cloth funnel on three lashed poles
    (1.3 x 1.7 m). Separate node `water`: its origin is the barrel's inside floor (z 0.08), modelled
    full (0.66 m deep); the game scales it in height to the level.
  * crops/<crop>_s<n>: one plant; origin at the soil surface under its centre, all of it above
    z = -0.02 (tubers and roots only peek out). Stage n of 4, the last one ripe.
  * crops/dead_plant: dry stalks fallen over the soil.
  * items/garden/<id>: ground pickups (origin bottom centre, settled), published by item_kit.
Foliage uses the shared item_herb atlas (yarrow leaf / huckleberry leaf / yarrow flower quadrants).
params: kind, name, seed (+ crop, stage for crops; band for packets; water for the bucket)."""
from __future__ import annotations

import math
import random

from mathutils import Matrix, Vector

from generators import structure_logs as L
from lib import item_kit as K

# item_herb atlas quadrants (u0, v0, u1, v1), UV origin bottom-left
Q_YARROW_LEAF = (0.0, 0.5, 0.5, 1.0)
Q_BROAD_LEAF = (0.5, 0.5, 1.0, 1.0)
Q_FLOWER_TOP = (0.0, 0.0, 0.5, 0.5)
Q_FLOWER_SIDE = (0.5, 0.0, 1.0, 0.5)

SOIL_Z = 0.33
STAGES = 4


# ------------------------------------------------------------------------------------------------
# Structures
# ------------------------------------------------------------------------------------------------

def garden_bed(p, outputs):
    """Two 2.4 m logs along the sides and two 1.1 m logs across the ends (one course, pegged by a stake
    at each corner), a soil fill mounded a little higher in the middle, a few clods and a scatter of
    bough mulch along the edges."""
    seed = int(p["seed"])
    r = random.Random(seed)
    parts = []
    crown = 0.17
    for k, (length, at, rot) in enumerate(((2.4, (0.0, -0.55 + crown, crown), 0.0), (2.4, (0.0, 0.55 - crown, crown), 0.0),
                                           (1.1 - 4 * crown, (-1.2 + crown, 0.0, crown), math.pi / 2),
                                           (1.1 - 4 * crown, (1.2 - crown, 0.0, crown), math.pi / 2))):
        lg = L.light_log(f"side{k}", seed + 10 + k, length=length, crown=crown, knots=1)
        L.place(lg, Matrix.Translation(at) @ Matrix.Rotation(rot + r.uniform(-0.01, 0.01), 4, "Z") @
                Matrix.Rotation(r.uniform(0, math.tau), 4, "X"))
        parts.append(lg)
    mb = K.MB()
    for k, (sx, sy) in enumerate(((-1, -1), (1, -1), (-1, 1), (1, 1))):
        x, y = sx * (1.2 - 2 * crown - 0.05), sy * (0.55 + 0.05)
        L.pole(mb, (x, y, -0.12), (x + r.uniform(-0.01, 0.01), y, 0.46 + r.uniform(-0.03, 0.03)), 0.035, 0.03, seed + 20 + k,
               sides=7, n=3, caps=(False, True))
    # soil: a slab under the surface, its top gently mounded (a grid so the mound reads)
    nx, ny = 12, 5
    w, d = 2.4 - 4 * crown + 0.12, 1.1 - 4 * crown + 0.1
    grid = []
    for j in range(ny + 1):
        row = []
        for i in range(nx + 1):
            u, v = i / nx - 0.5, j / ny - 0.5
            mound = 0.025 * math.cos(u * math.pi) * math.cos(v * math.pi) + r.uniform(-0.006, 0.006)
            row.append(mb.vert((u * w, v * d, SOIL_Z - 0.02 + mound)))
        grid.append(row)
    for j in range(ny):
        for i in range(nx):
            mb.face((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]),
                    ((i / nx * w, j / ny * d), ((i + 1) / nx * w, j / ny * d), ((i + 1) / nx * w, (j + 1) / ny * d),
                     (i / nx * w, (j + 1) / ny * d)), "garden_soil", True)
    K.box(mb, (w, d, SOIL_Z - 0.05), (0.0, 0.0, (SOIL_Z - 0.05) / 2), mat="garden_soil")
    # bough mulch tucked along the inside of the logs
    for k in range(10):
        x = r.uniform(-w / 2 + 0.05, w / 2 - 0.05)
        y = math.copysign(d / 2 - 0.03, r.uniform(-1, 1))
        dirv = Vector((r.uniform(-1, 1), -math.copysign(0.4, y), 0.15)).normalized()
        K.card(mb, (x, y, SOIL_Z), dirv, (0, 0, 1), 0.22, 0.09, mat="item_fir_bough", droop=0.1)
    parts.append(mb.build("bed", sharp_deg=55))
    for k in range(7):
        c = (r.uniform(-w / 2 + 0.1, w / 2 - 0.1), r.uniform(-d / 2 + 0.08, d / 2 - 0.08), SOIL_Z - 0.03)
        parts.append(K.pebble(f"clod{k}", (r.uniform(0.04, 0.07), r.uniform(0.04, 0.07), 0.035), seed + 40 + k, mat="garden_soil",
                              subdiv=1, lump=0.3, center=c))
    col = K.collider_box("garden_bed", (-1.2, -0.55, 0.0), (1.2, 0.55, 0.36))
    L.finish(outputs, "garden_bed", parts, seed, colliders=[col], ground=True)


def rain_catcher(p, outputs):
    """A log section stood on end and hollowed, three poles leaned together over it and lashed at the
    top, a cloth funnel hung in the poles draining through a hollow-stick spout into the barrel."""
    seed = int(p["seed"])
    r = random.Random(seed)
    mb = K.MB()
    # barrel: outside bark, end-grain rim, hewn inside down to a floor at z 0.08
    prof = [(0.36, 0.0), (0.372, 0.4), (0.36, 0.8), (0.3, 0.8), (0.295, 0.4), (0.3, 0.08), (0.0, 0.08)]
    K.lathe(mb, prof, segments=22, mat=L.MAT_BARK,
            regions=[(0, 2, L.MAT_BARK, "metric"), (2, 3, L.MAT_END, "metric"), (3, 6, L.MAT_HEWN, "metric")],
            cap_bottom=True, cap_top=False)
    apex = Vector((0.0, 0.0, 1.72))
    feet = []
    for k in range(3):
        a = 2 * math.pi * k / 3 + 0.3 + r.uniform(-0.08, 0.08)
        foot = Vector((math.cos(a) * 0.62, math.sin(a) * 0.62, -0.05))
        top = apex + (apex - foot).normalized() * 0.12 + Vector((r.uniform(-0.01, 0.01), r.uniform(-0.01, 0.01), 0))
        L.pole(mb, foot, top, 0.035, 0.028, seed + k, sides=7, n=5, bend=0.012)
        feet.append((foot, top))
    L.bind(mb, apex, (0, 0, 1), 0.06, seed + 10, turns=5, cord=0.005, width=0.08)
    # funnel: a thin shell of cloth, wide mouth at the poles, narrow at the spout
    shell = [(0.09, 1.08), (0.3, 1.24), (0.56, 1.46), (0.575, 1.475), (0.55, 1.47), (0.29, 1.255), (0.08, 1.095)]
    K.lathe(mb, shell, segments=18, mat="furn_burlap", cap_bottom=False, cap_top=False,
            radial_fn=lambda k, i, rr, z: 1.0 + (0.04 * math.sin(k * 1.7 + seed) if i in (2, 3, 4) else 0.0))
    for k, (foot, top) in enumerate(feet):
        t = (1.46 - foot.z) / (top.z - foot.z)
        at = foot.lerp(top, t)
        L.bind(mb, at, (top - foot).normalized(), 0.035, seed + 20 + k, turns=3, cord=0.004, width=0.05, mat="item_cordage")
    K.tube(mb, [Vector((0, 0, 1.09)), Vector((0, 0, 0.86))], 0.032, sides=8, mat=L.MAT_HEWN, cap_mat=L.MAT_END, cap_uv="disc")
    frame = mb.build("rain_catcher", sharp_deg=55)
    wm = K.MB()
    K.lathe(wm, [(0.292, 0.08), (0.292, 0.74)], segments=22, mat="farm_trough_water", cap_bottom=True, cap_top=True)
    water = wm.build("water", sharp_deg=None)
    col = K.collider_box("rain_catcher", (-0.4, -0.4, 0.0), (0.4, 0.4, 0.82))
    L.finish(outputs, "rain_catcher", [frame], seed, separate=[water], pivots={"water": Vector((0.0, 0.0, 0.08))},
             colliders=[col], ground=True)


# ------------------------------------------------------------------------------------------------
# Crops
# ------------------------------------------------------------------------------------------------

def _stem(mb, base, top, r0, r1=None, bend=0.0, seed=0, mat="item_stem_green"):
    base, top = Vector(base), Vector(top)
    mid = base.lerp(top, 0.5) + Vector((bend, bend * 0.5, 0.0))
    pts = K.polyline_resample([base, mid, top], 5)
    K.tube(mb, pts, [r0 + ((r1 if r1 is not None else r0 * 0.6) - r0) * i / 4 for i in range(5)], sides=5, mat=mat, caps=(False, True))


def _leaf(mb, base, direction, length, width, quad, droop=0.15, curl=0.2):
    K.card(mb, base, direction, (0, 0, 1), length, width, mat="item_herb", droop=droop, nu=2, nv=3, rect=quad, curl=curl)


def _rosette(mb, r, center, count, length, width, quad, rise=0.4, droop=0.2, phase=0.0):
    for k in range(count):
        a = phase + 2 * math.pi * k / count + r.uniform(-0.25, 0.25)
        d = Vector((math.cos(a), math.sin(a), rise + r.uniform(-0.1, 0.1))).normalized()
        _leaf(mb, Vector(center), d, length * r.uniform(0.8, 1.1), width, quad, droop=droop)


def _potato(r, stage, seed):
    t = stage / STAGES
    mb = K.MB()
    parts = []
    stems = 2 + stage
    h = 0.55 * (0.3 + 0.7 * t)
    for k in range(stems):
        a = 2 * math.pi * k / stems + r.uniform(-0.3, 0.3)
        lean = 0.12 * t
        top = Vector((math.cos(a) * lean, math.sin(a) * lean, h * r.uniform(0.75, 1.0)))
        _stem(mb, (0, 0, -0.01), top, 0.008 + 0.004 * t, 0.004, bend=0.02, seed=seed + k)
        # compound leaves: leaflets in pairs along the upper stem
        pairs = 1 + stage
        for j in range(pairs):
            f = 0.35 + 0.65 * (j + 1) / pairs
            at = Vector((0, 0, -0.01)).lerp(top, f)
            for sd in (-1, 1):
                d = Vector((math.cos(a + sd * 1.3), math.sin(a + sd * 1.3), 0.25)).normalized()
                _leaf(mb, at, d, 0.07 + 0.05 * t, 0.045 + 0.02 * t, Q_BROAD_LEAF, droop=0.25)
    if stage >= STAGES:
        # ripe: a few tubers heaved up through the soil
        for k in range(3):
            a = 2 * math.pi * k / 3 + r.uniform(-0.4, 0.4)
            c = (math.cos(a) * 0.13, math.sin(a) * 0.13, -0.02)
            parts.append(K.pebble(f"tuber{k}", (0.07, 0.055, 0.045), seed + 50 + k, mat="farm_potato", lump=0.15, center=c))
    return [mb.build("plant", sharp_deg=None)] + parts


def _carrot(r, stage, seed):
    t = stage / STAGES
    mb = K.MB()
    n = 3 + 2 * stage
    for k in range(n):
        a = 2 * math.pi * k / n + r.uniform(-0.2, 0.2)
        d = Vector((math.cos(a) * 0.35, math.sin(a) * 0.35, 1.0)).normalized()
        _leaf(mb, Vector((0, 0, 0.005)), d, 0.08 + 0.25 * t * r.uniform(0.8, 1.0), 0.06 + 0.04 * t, Q_YARROW_LEAF, droop=0.3, curl=0.1)
    parts = [mb.build("plant", sharp_deg=None)]
    if stage >= STAGES - 1:
        # the orange shoulder shows at the soil
        cm = K.MB()
        rr = 0.012 + 0.008 * t
        K.lathe(cm, [(rr * 0.6, -0.02), (rr, 0.0), (rr * 0.85, 0.012), (0.0, 0.016)], segments=10, mat="garden_carrot", cap_bottom=False)
        parts.append(cm.build("shoulder", sharp_deg=None))
    return parts


def _beans(r, stage, seed):
    t = stage / STAGES
    mb = K.MB()
    # the stake is there from the start; the vine climbs it
    L.pole(mb, (0.0, 0.0, -0.05), (r.uniform(-0.02, 0.02), r.uniform(-0.02, 0.02), 1.7), 0.018, 0.014, seed, sides=6, n=4,
           bark="item_bark_twig", caps=(False, True))
    top = 0.15 + 1.5 * t
    pts = K.helix((0, 0, 0.0), (0, 0, top), 0.03, 2.0 + 4.0 * t, per_turn=10)
    K.tube(mb, pts, 0.004, sides=4, mat="item_stem_green", caps=(False, True))
    for i in range(2, len(pts) - 1, 3):
        pnt = pts[i]
        out = Vector((pnt.x, pnt.y, 0.0))
        out = out.normalized() if out.length > 1e-4 else Vector((1, 0, 0))
        d = (out + Vector((0, 0, 0.3))).normalized()
        _leaf(mb, pnt, d, 0.08, 0.06, Q_BROAD_LEAF, droop=0.3)
    if stage >= STAGES:
        for k in range(9):
            z = r.uniform(0.35, top - 0.1)
            a = r.uniform(0, math.tau)
            base = Vector((math.cos(a) * 0.045, math.sin(a) * 0.045, z))
            sway = Vector((math.cos(a) * 0.015, math.sin(a) * 0.015, 0.0))
            pod = [base, base + sway + Vector((0, 0, -0.05)), base + sway * 1.6 + Vector((0, 0, -0.1)), base + sway + Vector((0.004, 0, -0.14))]
            K.tube(mb, K.polyline_resample(pod, 6), [0.004, 0.0055, 0.006, 0.0055, 0.004, 0.001], sides=6, mat="garden_bean_pod",
                   caps=(False, False))
    return [mb.build("plant", sharp_deg=None)]


def _huckleberry(r, stage, seed):
    t = stage / STAGES
    mb = K.MB()
    parts = []
    h = 0.8 * (0.25 + 0.75 * t)
    twigs = 2 + 2 * stage
    tips = []
    for k in range(twigs):
        a = 2 * math.pi * k / twigs + r.uniform(-0.3, 0.3)
        top = Vector((math.cos(a) * h * 0.35, math.sin(a) * h * 0.35, h * r.uniform(0.7, 1.0)))
        pts = K.polyline_resample([Vector((0, 0, -0.01)), Vector((top.x * 0.3, top.y * 0.3, top.z * 0.5)), top], 5)
        K.stick(mb, pts, 0.008 + 0.004 * t, 0.003, sides=5, seed=seed + k, bark="item_bark_twig")
        for j in range(3 + stage):
            f = 0.4 + 0.6 * (j + 1) / (3 + stage)
            at = pts[0].lerp(top, f)
            d = Vector((math.cos(a + j * 2.1), math.sin(a + j * 2.1), 0.2)).normalized()
            _leaf(mb, at, d, 0.05, 0.03, Q_BROAD_LEAF, droop=0.2)
        tips.append(top)
    parts.append(mb.build("plant", sharp_deg=None))
    if stage >= STAGES:
        n = 0
        for top in tips:
            for j in range(3):
                c = top + Vector((r.uniform(-0.04, 0.04), r.uniform(-0.04, 0.04), r.uniform(-0.12, -0.02)))
                parts.append(K.pebble(f"berry{n}", (0.011, 0.011, 0.0105), seed + 100 + n, mat="item_berry", subdiv=2, flat_bottom=0.0,
                                      lump=0.04, center=c))
                n += 1
    return parts


def _yarrow(r, stage, seed):
    t = stage / STAGES
    mb = K.MB()
    _rosette(mb, r, (0, 0, 0.005), 4 + stage, 0.08 + 0.08 * t, 0.05, Q_YARROW_LEAF, rise=0.6, droop=0.25)
    if stage >= STAGES - 1:
        # flower stalks; buds at stage 3, open heads when ripe
        for k in range(2 + stage // 2):
            a = 2 * math.pi * k / 3 + r.uniform(-0.3, 0.3)
            top = Vector((math.cos(a) * 0.06, math.sin(a) * 0.06, 0.5 * r.uniform(0.8, 1.0)))
            _stem(mb, (0, 0, 0.0), top, 0.004, 0.003, bend=0.01, seed=seed + k)
            size = 0.06 if stage >= STAGES else 0.03
            K.card(mb, top - Vector((0, 0, size * 0.3)), (0, 0, 1), (1, 0, 0), size, size * 1.6, mat="item_herb", droop=0.0,
                   nu=1, nv=1, rect=Q_FLOWER_SIDE)
            K.card(mb, top - Vector((size * 0.8, 0, -0.005)), (1, 0, 0), (0, 0, 1), size * 1.6, size * 1.6, mat="item_herb", droop=0.0,
                   nu=1, nv=1, rect=Q_FLOWER_TOP)
    return [mb.build("plant", sharp_deg=None)]


CROPS = {"potato": _potato, "carrot": _carrot, "pole_beans": _beans, "huckleberry": _huckleberry, "yarrow": _yarrow}


def crop(p, outputs):
    seed = int(p["seed"])
    stage = int(p["stage"])
    r = random.Random(seed * 31 + stage)
    parts = CROPS[p["crop"]](r, stage, seed)
    K.publish(outputs, name=p["name"], parts=parts, seed=seed, keep_origin=True, ao_samples=12, inset=False)


def dead_plant(p, outputs):
    """Dry stalks fallen every way over the soil, a few shrivelled leaves."""
    seed = int(p["seed"])
    r = random.Random(seed)
    mb = K.MB()
    for k in range(6):
        a = 2 * math.pi * k / 6 + r.uniform(-0.3, 0.3)
        length = r.uniform(0.2, 0.35)
        up = r.uniform(0.04, 0.12)
        pts = [Vector((0, 0, -0.01)), Vector((math.cos(a) * 0.05, math.sin(a) * 0.05, up)),
               Vector((math.cos(a) * length, math.sin(a) * length, 0.02))]
        K.tube(mb, K.polyline_resample(pts, 5), [0.006, 0.005, 0.004, 0.003, 0.002], sides=5, mat="garden_dead_stalk", caps=(False, True))
    parts = [mb.build("dead_plant", sharp_deg=None)]
    for k in range(4):
        c = (r.uniform(-0.15, 0.15), r.uniform(-0.15, 0.15), 0.0)
        parts.append(K.pebble(f"leaf{k}", (0.04, 0.025, 0.006), seed + k, mat="garden_dead_stalk", subdiv=1, lump=0.3, center=c))
    K.publish(outputs, name="dead_plant", parts=parts, seed=seed, keep_origin=True, ao_samples=12, inset=False)


# ------------------------------------------------------------------------------------------------
# Items
# ------------------------------------------------------------------------------------------------

def _packet(p):
    """A paper seed packet, its lower half printed in the crop's colour band."""
    mb = K.MB()
    K.box(mb, (0.072, 0.0045, 0.11), (0, 0, 0.055), mat="item_paper", bevel=0.001)
    K.box(mb, (0.073, 0.0049, 0.045), (0, 0, 0.03), mat=p["band"])
    return [mb.build(p["name"], sharp_deg=40)], {"ground": Matrix.Rotation(math.radians(90), 4, "X")}


def _twist(p):
    """Seeds wrapped in a twist of paper."""
    mb = K.MB()
    K.lathe(mb, [(0.0, 0.0), (0.018, 0.012), (0.02, 0.03), (0.008, 0.045), (0.004, 0.06), (0.007, 0.07)], segments=12, mat="item_paper",
            cap_top=True, radial_fn=lambda k, i, rr, z: 1.0 + 0.12 * math.sin(k * 2.0 + i))
    return [mb.build(p["name"], sharp_deg=None)], {"ground": Matrix.Rotation(math.radians(80), 4, "Y")}


def _tuber(name, seed, size, mat, center=(0, 0, 0)):
    return K.pebble(name, size, seed, mat=mat, lump=0.16, flat_bottom=0.1, center=center)


def _potato_item(p):
    return [_tuber(p["name"], int(p["seed"]), (0.09, 0.065, 0.055), p.get("mat", "farm_potato"))], {}


def _seed_potatoes(p):
    """Three small potatoes, each with pale sprouts."""
    seed = int(p["seed"])
    r = random.Random(seed)
    parts = []
    mb = K.MB()
    for k, c in enumerate(((0.0, 0.0), (0.06, 0.02), (0.025, 0.055))):
        parts.append(_tuber(f"tuber{k}", seed + k, (0.055, 0.045, 0.04), "farm_potato", center=(c[0], c[1], 0.0)))
        for j in range(2):
            base = Vector((c[0] + r.uniform(-0.01, 0.01), c[1] + r.uniform(-0.01, 0.01), 0.035))
            tip = base + Vector((r.uniform(-0.015, 0.015), r.uniform(-0.015, 0.015), 0.018))
            K.tube(mb, [base, base.lerp(tip, 0.5) + Vector((0.003, 0, 0)), tip], [0.003, 0.0025, 0.0015], sides=5, mat="item_stem_green")
    parts.append(mb.build("sprouts", sharp_deg=None))
    return parts, {}


def _carrot_item(p):
    mb = K.MB()
    K.lathe(mb, [(0.0, 0.0), (0.006, 0.03), (0.012, 0.09), (0.015, 0.13), (0.012, 0.142), (0.0, 0.145)], segments=12, mat="garden_carrot",
            radial_fn=lambda k, i, rr, z: 1.0 + 0.05 * math.sin(k * 3.0 + i * 1.7))
    for k in range(4):
        a = 2 * math.pi * k / 4
        K.tube(mb, [Vector((0, 0, 0.14)), Vector((math.cos(a) * 0.01, math.sin(a) * 0.01, 0.17)),
                    Vector((math.cos(a) * 0.02, math.sin(a) * 0.02, 0.19))], 0.002, sides=4, mat="item_stem_green")
    return [mb.build(p["name"], sharp_deg=None)], {"ground": Matrix.Rotation(math.radians(90), 4, "Y")}


def _beans_item(p):
    seed = int(p["seed"])
    r = random.Random(seed)
    mb = K.MB()
    for k in range(5):
        a = r.uniform(0, math.tau)
        c = Vector((r.uniform(-0.02, 0.02), r.uniform(-0.02, 0.02), 0.006 + 0.008 * (k % 2)))
        d = Vector((math.cos(a), math.sin(a), 0.0))
        side = Vector((-d.y, d.x, 0.0)) * 0.01
        pod = [c - d * 0.06, c - d * 0.02 + side, c + d * 0.02 + side, c + d * 0.06]
        K.tube(mb, K.polyline_resample(pod, 7), [0.002, 0.005, 0.006, 0.006, 0.006, 0.005, 0.0015], sides=6, mat="garden_bean_pod",
               caps=(False, False))
    return [mb.build(p["name"], sharp_deg=None)], {"settle": None}


def _bucket(p):
    """A galvanised pail with a rolled rim and a wire bail; `water` fills it near the brim."""
    mb = K.MB()
    K.lathe(mb, [(0.0, 0.0), (0.12, 0.0), (0.122, 0.005), (0.15, 0.27), (0.158, 0.272), (0.158, 0.282), (0.146, 0.28), (0.118, 0.012),
                 (0.0, 0.012)], segments=28, mat="item_galvanized", cap_bottom=False, cap_top=False)
    pts = [Vector((0.158 * math.cos(a), 0.0, 0.25 + 0.17 * math.sin(a))) for a in [math.pi * i / 16 for i in range(17)]]
    K.tube(mb, pts, 0.0025, sides=5, mat="item_steel_tool")
    for sx in (-1, 1):
        K.box(mb, (0.006, 0.03, 0.03), (sx * 0.152, 0.0, 0.25), mat="item_galvanized")
    if p.get("water"):
        K.lathe(mb, [(0.142, 0.24), (0.0, 0.24)], segments=28, mat="farm_trough_water", cap_bottom=False, cap_top=False)
    return [mb.build(p["name"], sharp_deg=40)], {"settle": None}


ITEMS = {"packet": _packet, "twist": _twist, "potato": _potato_item, "seed_potatoes": _seed_potatoes, "carrot": _carrot_item,
         "beans": _beans_item, "bucket": _bucket}


def item(p, outputs):
    parts, opts = ITEMS[p["item"]](p)
    K.publish(outputs, name=p["name"], parts=parts, seed=int(p["seed"]), ground_rot=opts.get("ground"),
              settle_deg=opts.get("settle", 20.0), wear_deg=30.0, inset=False)


BUILDERS = {"garden_bed": garden_bed, "rain_catcher": rain_catcher, "crop": crop, "dead_plant": dead_plant, "item": item}


def build(params: dict, outputs: list[str]) -> None:
    BUILDERS[params["kind"]](params, outputs)
