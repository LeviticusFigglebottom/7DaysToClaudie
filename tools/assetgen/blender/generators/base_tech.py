"""Base traps and electricity (ADR-0052): the spike pit, deadfall and tripwire bell, the generator, work
light, motion floodlight and nail sentry structures, and the electrical items (gas can, wire spool,
electrical parts, work lamp, small engine).

Frames (Blender Z-up, exported to Godot Y-up; front faces Blender -Y = Godot +Z); origin bottom centre,
sizes as game/data/structures/base_tech.json:
  * spike_pit 2.0 x 2.0: a dark pit floor just above z 0 (the pit is not cut into the terrain), a rim of
    spoil, and sharpened stakes up to z ~0.4.
  * deadfall 1.8 x 1.4 x 1.6: two posts and a cross pole at the back, a figure-four trigger, and a separate
    node `log` (1.7 m, r 0.17) hung across at z 1.22; its origin is the log's centre, which the game
    lowers to 0.18 when it drops.
  * tripwire_bell 3.0 x 0.2 x 0.7: two stakes, a cord at z 0.22 between them, a bell on the right stake.
  * generator 1.0 x 0.7 x 0.8: a yellow tube frame round an engine, an alternator and a red tank; a small
    indicator lamp (material road_lamp_glow, lit by the game while it runs).
  * work_light 0.5 x 0.5 x 2.1: a stake with a caged lamp (road_lamp_glow) at the top facing +Z (Godot).
  * floodlight 0.6 x 0.6 x 2.6: a steel pole, a motion sensor, and a separate node `head` (the lamp housing,
    lens road_lamp_glow) whose origin is the pole top; the game turns it in yaw toward what it saw.
  * nail_sentry 0.8 x 0.8 x 1.2: a tripod and a separate node `head` (the nailer on its pan head) whose origin
    is the pan axis at z 1.02; the game turns it toward its target.
  * items/base_tech/<id>: ground pickups (origin bottom centre, settled), published by item_kit.
params: kind (a structure name or "item"), name, seed (+ item for items)."""
from __future__ import annotations

import math
import random

from mathutils import Matrix, Vector

from generators import structure_logs as L
from lib import item_kit as K

GLOW = "road_lamp_glow"
STEEL = "item_steel_tool"
GALV = "item_galvanized"
RUST = "item_rust"
ROPE = "item_rope"
YELLOW = "lab_genset_yellow"
SOIL = "garden_soil"


# ------------------------------------------------------------------------------------------------
# Traps
# ------------------------------------------------------------------------------------------------

def _stake(mb, base, tip, r, seed):
    """A sharpened stake: a pole whose last tenth tapers to a point (hewn), bark below."""
    base, tip = Vector(base), Vector(tip)
    k = base.lerp(tip, 0.82)
    L.pole(mb, tuple(base), tuple(k), r, r * 0.9, seed, n=3, caps=(False, False))
    K.tube(mb, [k, tip], [r * 0.9, 0.003], sides=7, mat=L.MAT_HEWN, caps=(False, False))


def spike_pit(p, outputs):
    seed = int(p["seed"])
    r = random.Random(seed)
    mb = K.MB()
    # The pit floor: dark soil just above ground (the terrain is not cut; it reads as a hole from above).
    K.box(mb, (1.84, 1.84, 0.02), (0.0, 0.0, 0.01), mat=SOIL)
    # Spoil heaped round the rim.
    for k, (sx, sy, w, d) in enumerate(((0, -1, 2.0, 0.18), (0, 1, 2.0, 0.18), (-1, 0, 0.18, 1.64), (1, 0, 0.18, 1.64))):
        K.box(mb, (w, d, 0.07 + r.uniform(0.0, 0.03)), (sx * 0.91, sy * 0.91, 0.04), mat=SOIL, bevel=0.03)
    # Stakes on a jittered 4 x 4 grid, leaning a little.
    for i in range(4):
        for j in range(4):
            x = (i - 1.5) * 0.42 + r.uniform(-0.06, 0.06)
            y = (j - 1.5) * 0.42 + r.uniform(-0.06, 0.06)
            h = r.uniform(0.3, 0.42)
            _stake(mb, (x, y, -0.05), (x + r.uniform(-0.06, 0.06), y + r.uniform(-0.06, 0.06), h), r.uniform(0.022, 0.03), seed + 10 + i * 4 + j)
    parts = [mb.build("spike_pit", sharp_deg=50)]
    col = K.collider_box("spike_pit", (-1.0, -1.0, 0.0), (1.0, 1.0, 0.1))
    L.finish(outputs, "spike_pit", parts, seed, colliders=[col], ground=True)


HANG_Z = 1.22


def deadfall(p, outputs):
    seed = int(p["seed"])
    r = random.Random(seed)
    mb = K.MB()
    back = 0.5   # Godot -Z = Blender +Y: the frame stands behind the log
    for k, x in enumerate((-0.84, 0.84)):
        L.pole(mb, (x, back, -0.1), (x + r.uniform(-0.02, 0.02), back, 1.58), 0.055, 0.045, seed + k, n=4, caps=(False, True))
    L.pole(mb, (-0.95, back, 1.5), (0.95, back, 1.52), 0.045, 0.04, seed + 3, n=4)
    for x in (-0.84, 0.84):
        L.cross_lash(mb, Vector((x, back, 1.51)), Vector((1, 0, 0)), Vector((0, 0, 1)), 0.05, seed + 4)
    # Figure-four trigger under the log's middle: upright, diagonal and bait stick.
    L.pole(mb, (0.0, 0.0, 0.0), (0.0, 0.0, 0.62), 0.02, 0.018, seed + 5, n=2)
    L.pole(mb, (-0.25, 0.0, 0.2), (0.12, 0.0, 0.7), 0.018, 0.016, seed + 6, n=2)
    L.pole(mb, (-0.3, -0.05, 0.22), (0.35, 0.05, 0.18), 0.016, 0.014, seed + 7, n=2)
    # The lift cord from the cross pole down to the log.
    K.tube(mb, [Vector((0.0, back, 1.5)), Vector((0.0, 0.25, 1.36)), Vector((0.0, 0.0, HANG_Z + 0.17))], 0.006, sides=5, mat=ROPE)
    frame = mb.build("deadfall", sharp_deg=50)
    lg = L.light_log("log", seed + 20, length=1.7, crown=0.168, knots=2)
    L.place(lg, Matrix.Translation((0.0, 0.0, HANG_Z)) @ Matrix.Rotation(r.uniform(0, math.tau), 4, "X"))
    col = K.collider_box("deadfall", (-0.9, -0.7, 0.0), (0.9, 0.7, 1.6))
    L.finish(outputs, "deadfall", [frame], seed, separate=[lg], pivots={"log": Vector((0.0, 0.0, HANG_Z))}, colliders=[col], ground=True)


def tripwire_bell(p, outputs):
    seed = int(p["seed"])
    mb = K.MB()
    for k, x in enumerate((-1.5, 1.5)):
        L.pole(mb, (x, 0.0, -0.15), (x, 0.0, 0.55), 0.025, 0.02, seed + k, n=3, caps=(False, True))
    K.tube(mb, [Vector((-1.5, 0.0, 0.22)), Vector((0.0, 0.0, 0.205)), Vector((1.5, 0.0, 0.22))], 0.0035, sides=5, mat=ROPE)
    # A cast bell hung off the right stake on a hook.
    K.tube(mb, [Vector((1.5, 0.0, 0.5)), Vector((1.5, -0.08, 0.5)), Vector((1.5, -0.08, 0.44))], 0.004, sides=5, mat=STEEL)
    frame = mb.build("tripwire_bell", sharp_deg=40)
    bm = K.MB()
    K.lathe(bm, [(0.0, 0.31), (0.015, 0.31), (0.03, 0.33), (0.055, 0.36), (0.06, 0.4), (0.04, 0.43), (0.0, 0.44)], segments=16,
            mat="item_brass", cap_bottom=False, cap_top=False)
    bell = bm.build("bell", sharp_deg=40)
    bell.data.transform(Matrix.Translation((1.5, -0.08, 0.0)))
    col = K.collider_box("tripwire_bell", (-1.5, -0.1, 0.0), (1.5, 0.1, 0.7))
    L.finish(outputs, "tripwire_bell", [frame, bell], seed, colliders=[col], ground=True)


# ------------------------------------------------------------------------------------------------
# Power
# ------------------------------------------------------------------------------------------------

def _frame_box(mb, w, d, h, r, mat):
    """A bent-tube frame: four uprights and top and bottom rings."""
    for z in (0.03, h - r):
        ring = [Vector((-w / 2, -d / 2, z)), Vector((w / 2, -d / 2, z)), Vector((w / 2, d / 2, z)), Vector((-w / 2, d / 2, z))]
        K.tube(mb, ring, r, sides=8, mat=mat, closed=True)
    for sx in (-1, 1):
        for sy in (-1, 1):
            K.tube(mb, [Vector((sx * w / 2, sy * d / 2, 0.03)), Vector((sx * w / 2, sy * d / 2, h - r))], r, sides=8, mat=mat, caps=(False, False))


def generator(p, outputs):
    seed = int(p["seed"])
    mb = K.MB()
    w, d, h = 1.0, 0.7, 0.8
    _frame_box(mb, w - 0.06, d - 0.06, h, 0.018, YELLOW)
    # Engine on the left, alternator on the right, tank across the top.
    K.box(mb, (0.36, 0.34, 0.3), (-0.2, 0.0, 0.2), mat="item_steel_dark", bevel=0.03)
    for k in range(7):
        K.box(mb, (0.2, 0.3, 0.01), (-0.2, 0.0, 0.37 + k * 0.022), mat="item_steel_dark")
    K.box(mb, (0.1, 0.2, 0.16), (-0.42, 0.0, 0.26), mat="item_plastic_black", bevel=0.02)
    K.tube(mb, [Vector((0.06, 0.0, 0.26)), Vector((0.4, 0.0, 0.26))], 0.13, sides=20, mat=YELLOW, cap_mat="item_steel_dark")
    K.box(mb, (0.66, 0.42, 0.16), (0.0, 0.0, h - 0.12), mat="item_paint_red", bevel=0.04)
    K.tube(mb, [Vector((0.2, 0.0, h - 0.04)), Vector((0.2, 0.0, h + 0.01))], 0.035, sides=12, mat="item_plastic_black")
    # Control panel facing front: outlets and the run lamp.
    K.box(mb, (0.22, 0.02, 0.14), (0.25, -0.2, 0.42), mat="item_plastic_black")
    K.box(mb, (0.03, 0.012, 0.02), (0.31, -0.212, 0.46), mat=GLOW)
    for k in range(2):
        K.box(mb, (0.04, 0.012, 0.05), (0.2 + k * 0.06, -0.212, 0.4), mat="item_plastic_white")
    # Exhaust muffler.
    K.tube(mb, [Vector((-0.42, 0.18, 0.4)), Vector((-0.42, 0.18, 0.52))], 0.04, sides=12, mat=RUST)
    obj = mb.build("generator", sharp_deg=40)
    col = K.collider_box("generator", (-0.5, -0.35, 0.0), (0.5, 0.35, 0.8))
    L.finish(outputs, "generator", [obj], seed, colliders=[col], ground=True, wear_deg=25.0)


def work_light(p, outputs):
    seed = int(p["seed"])
    mb = K.MB()
    L.pole(mb, (0.0, 0.0, -0.2), (0.0, 0.0, 2.0), 0.035, 0.03, seed, n=5, caps=(False, True))
    # Clamp, then the lamp on a short arm toward the front (Blender -Y).
    K.box(mb, (0.08, 0.08, 0.1), (0.0, -0.04, 1.86), mat=STEEL)
    K.lathe(mb, [(0.0, 0.0), (0.03, 0.0), (0.075, 0.08), (0.085, 0.12), (0.0, 0.12)], segments=18, mat="item_plastic_amber",
            cap_bottom=False, cap_top=False)
    lamp = mb.build("lamp_shell", sharp_deg=None)
    lamp.data.transform(Matrix.Translation((0.0, -0.1, 1.92)) @ Matrix.Rotation(math.pi / 2, 4, "X"))
    gm = K.MB()
    K.lathe(gm, [(0.0, 0.0), (0.05, 0.02), (0.05, 0.06), (0.0, 0.08)], segments=16, mat=GLOW, cap_bottom=False, cap_top=False)
    for k in range(6):
        a = k * math.tau / 6
        K.tube(gm, [Vector((0.08 * math.cos(a), 0.08 * math.sin(a), 0.1)), Vector((0.06 * math.cos(a), 0.06 * math.sin(a), 0.2))], 0.004,
               sides=5, mat=STEEL)
    bulb = gm.build("bulb", sharp_deg=None)
    bulb.data.transform(Matrix.Translation((0.0, -0.1, 1.92)) @ Matrix.Rotation(math.pi / 2, 4, "X"))
    pole = mb.build("work_light", sharp_deg=40)
    col = K.collider_box("work_light", (-0.25, -0.25, 0.0), (0.25, 0.25, 2.1))
    L.finish(outputs, "work_light", [pole, lamp, bulb], seed, colliders=[col], ground=True)


FLOOD_TOP = 2.4


def floodlight(p, outputs):
    seed = int(p["seed"])
    mb = K.MB()
    K.tube(mb, [Vector((0.0, 0.0, -0.3)), Vector((0.0, 0.0, FLOOD_TOP))], 0.04, sides=12, mat=GALV)
    for k in range(3):
        a = k * math.tau / 3
        K.tube(mb, [Vector((0.0, 0.0, 0.5)), Vector((0.35 * math.cos(a), 0.35 * math.sin(a), 0.0))], 0.018, sides=8, mat=GALV)
    # The motion sensor: a white dome under a hood, facing front.
    K.box(mb, (0.1, 0.06, 0.08), (0.0, -0.06, 1.9), mat="item_plastic_white", bevel=0.01)
    K.lathe(mb, [(0.0, 0.0), (0.03, 0.0), (0.028, 0.02), (0.0, 0.032)], segments=12, mat="item_plastic_clear", cap_bottom=False, cap_top=False)
    pole = mb.build("floodlight", sharp_deg=40)
    hm = K.MB()
    # Lamp housing on a yoke, tilted down 30 degrees toward the front.
    K.tube(hm, [Vector((-0.24, 0.0, 0.0)), Vector((-0.24, 0.0, 0.12)), Vector((0.24, 0.0, 0.12)), Vector((0.24, 0.0, 0.0))], 0.012, sides=8, mat=STEEL)
    K.box(hm, (0.42, 0.16, 0.3), (0.0, -0.02, 0.08), mat="item_paint_grey", bevel=0.02)
    K.box(hm, (0.36, 0.01, 0.24), (0.0, -0.105, 0.08), mat=GLOW)
    head = hm.build("head", sharp_deg=40)
    head.data.transform(Matrix.Rotation(math.radians(-30.0), 4, "X"))
    head.data.transform(Matrix.Translation((0.0, -0.06, FLOOD_TOP)))
    col = K.collider_box("floodlight", (-0.3, -0.3, 0.0), (0.3, 0.3, 2.6))
    L.finish(outputs, "floodlight", [pole], seed, separate=[head], pivots={"head": Vector((0.0, 0.0, FLOOD_TOP))}, colliders=[col], ground=True)


PAN_Z = 1.02


def nail_sentry(p, outputs):
    seed = int(p["seed"])
    mb = K.MB()
    for k in range(3):
        a = k * math.tau / 3 + math.pi / 2
        K.tube(mb, [Vector((0.0, 0.0, PAN_Z - 0.12)), Vector((0.38 * math.cos(a), 0.38 * math.sin(a), 0.0))], 0.02, sides=8, mat=GALV)
        K.box(mb, (0.06, 0.06, 0.02), (0.38 * math.cos(a), 0.38 * math.sin(a), 0.01), mat="item_rubber")
    K.tube(mb, [Vector((0.0, 0.0, PAN_Z - 0.2)), Vector((0.0, 0.0, PAN_Z - 0.02))], 0.04, sides=12, mat=STEEL)
    # A battery-box and a run of cable down one leg.
    K.box(mb, (0.16, 0.1, 0.12), (0.0, 0.0, PAN_Z - 0.3), mat="item_plastic_black", bevel=0.01)
    base = mb.build("nail_sentry", sharp_deg=40)
    hm = K.MB()
    K.lathe(hm, [(0.0, 0.0), (0.07, 0.0), (0.07, 0.03), (0.0, 0.03)], segments=16, mat=STEEL, cap_bottom=False, cap_top=False)
    # The nailer: body, magazine, nose, and a motion sensor on top; pointing front (Blender -Y).
    K.box(hm, (0.12, 0.36, 0.14), (0.0, -0.04, 0.12), mat="item_paint_red", bevel=0.02)
    K.box(hm, (0.05, 0.3, 0.05), (0.0, 0.0, 0.03), mat="item_steel_dark")
    K.tube(hm, [Vector((0.0, -0.22, 0.12)), Vector((0.0, -0.34, 0.12))], 0.022, sides=10, mat=STEEL)
    K.box(hm, (0.06, 0.04, 0.04), (0.0, -0.12, 0.21), mat="item_plastic_white")
    K.box(hm, (0.02, 0.01, 0.015), (0.04, -0.2, 0.17), mat=GLOW)
    head = hm.build("head", sharp_deg=40)
    head.data.transform(Matrix.Translation((0.0, 0.0, PAN_Z)))
    col = K.collider_box("nail_sentry", (-0.4, -0.4, 0.0), (0.4, 0.4, 1.2))
    L.finish(outputs, "nail_sentry", [base], seed, separate=[head], pivots={"head": Vector((0.0, 0.0, PAN_Z))}, colliders=[col], ground=True)


# ------------------------------------------------------------------------------------------------
# Items
# ------------------------------------------------------------------------------------------------

def _gas_can(p):
    """A red steel jerrican: the pressed X on its sides, three handles and a spout cap."""
    mb = K.MB()
    w, d, h = 0.17, 0.34, 0.46
    K.box(mb, (w, d, h), (0.0, 0.0, h / 2), mat="item_paint_red", bevel=0.02)
    for sx in (-1, 1):
        for a in (1, -1):
            K.tube(mb, [Vector((sx * (w / 2 + 0.002), -d * 0.38, h * 0.5 - a * h * 0.38)), Vector((sx * (w / 2 + 0.002), d * 0.38, h * 0.5 + a * h * 0.38))],
                   0.008, sides=5, mat="item_paint_red", caps=(False, False))
    for k in range(3):
        y = (k - 1) * 0.07 - 0.04
        K.tube(mb, [Vector((0.0, y - 0.025, h)), Vector((0.0, y - 0.025, h + 0.04)), Vector((0.0, y + 0.025, h + 0.04)), Vector((0.0, y + 0.025, h))],
               0.009, sides=6, mat="item_paint_red")
    K.tube(mb, [Vector((0.0, d / 2 - 0.05, h)), Vector((0.0, d / 2 - 0.02, h + 0.04))], 0.022, sides=12, mat="item_steel_dark")
    return [mb.build(p["name"], sharp_deg=40)], {"ground": Matrix.Rotation(math.pi / 2, 4, "Y")}


def _copper_wire(p):
    """A plastic spool wound with insulated wire, a loose end trailing."""
    mb = K.MB()
    K.lathe(mb, [(0.03, 0.0), (0.1, 0.0), (0.1, 0.008), (0.03, 0.008)], segments=24, mat="item_plastic_black", cap_bottom=False, cap_top=False)
    K.lathe(mb, [(0.03, 0.092), (0.1, 0.092), (0.1, 0.1), (0.03, 0.1)], segments=24, mat="item_plastic_black", cap_bottom=False, cap_top=False)
    K.lathe(mb, [(0.03, 0.008), (0.085, 0.01), (0.088, 0.05), (0.085, 0.09), (0.03, 0.092)], segments=24, mat="item_plastic_red",
            cap_bottom=False, cap_top=False)
    K.tube(mb, [Vector((0.086, 0.0, 0.05)), Vector((0.12, -0.03, 0.03)), Vector((0.16, -0.02, 0.005))], 0.003, sides=5, mat="item_copper")
    return [mb.build(p["name"], sharp_deg=None)], {"ground": Matrix.Rotation(math.pi / 2, 4, "X")}


def _electrical_parts(p):
    r = random.Random(int(p["seed"]))
    mb = K.MB()
    K.box(mb, (0.07, 0.05, 0.04), (0.0, 0.0, 0.02), mat="item_plastic_black", bevel=0.005)
    K.box(mb, (0.012, 0.02, 0.02), (0.0, 0.0, 0.05), mat="item_plastic_white")
    K.box(mb, (0.05, 0.035, 0.03), (0.07, 0.03, 0.015), mat="item_plastic_blue", bevel=0.004)
    K.box(mb, (0.04, 0.06, 0.015), (-0.06, 0.04, 0.008), mat="item_paint_green")
    for k in range(4):
        a = r.uniform(0, math.tau)
        pts = [Vector((0.0, 0.0, 0.03)), Vector((0.05 * math.cos(a), 0.05 * math.sin(a), 0.02)), Vector((0.11 * math.cos(a + 0.4), 0.11 * math.sin(a + 0.4), 0.004))]
        K.tube(mb, K.polyline_resample(pts, 6), 0.0025, sides=5, mat=("item_plastic_red", "item_plastic_black", "item_copper", "item_plastic_blue")[k])
    return [mb.build(p["name"], sharp_deg=40)], {"settle": None}


def _light_bulb(p):
    mb = K.MB()
    K.lathe(mb, [(0.0, 0.0), (0.03, 0.0), (0.04, 0.04), (0.06, 0.08), (0.062, 0.1), (0.0, 0.11)], segments=18, mat="item_plastic_amber",
            cap_bottom=False, cap_top=False)
    K.lathe(mb, [(0.0, 0.1), (0.04, 0.11), (0.042, 0.16), (0.02, 0.19), (0.0, 0.195)], segments=16, mat="item_glass_clear", cap_bottom=False, cap_top=False)
    for k in range(6):
        a = k * math.tau / 6
        K.tube(mb, [Vector((0.062 * math.cos(a), 0.062 * math.sin(a), 0.1)), Vector((0.05 * math.cos(a), 0.05 * math.sin(a), 0.2))], 0.003, sides=5, mat=STEEL)
    K.tube(mb, [Vector((0.0, 0.0, 0.0)), Vector((0.08, 0.0, -0.005)), Vector((0.18, 0.02, 0.0))], 0.004, sides=5, mat="item_plastic_black")
    return [mb.build(p["name"], sharp_deg=None)], {"ground": Matrix.Rotation(math.pi / 2, 4, "Y")}


def _small_engine(p):
    mb = K.MB()
    K.box(mb, (0.3, 0.26, 0.2), (0.0, 0.0, 0.1), mat="item_steel_dark", bevel=0.02)
    for k in range(6):
        K.box(mb, (0.18, 0.22, 0.008), (0.05, 0.0, 0.22 + k * 0.02), mat="item_steel_dark")
    K.tube(mb, [Vector((-0.15, 0.0, 0.18)), Vector((-0.2, 0.0, 0.18))], 0.11, sides=20, mat="item_paint_red", cap_mat="item_paint_red")
    K.box(mb, (0.12, 0.16, 0.08), (-0.02, 0.0, 0.36), mat="item_paint_red", bevel=0.02)
    K.box(mb, (0.08, 0.12, 0.1), (0.13, 0.08, 0.27), mat="item_plastic_black", bevel=0.015)
    K.tube(mb, [Vector((0.15, 0.0, 0.08)), Vector((0.22, 0.0, 0.08))], 0.012, sides=8, mat=STEEL)
    return [mb.build(p["name"], sharp_deg=40)], {"settle": None}


ITEMS = {"gas_can": _gas_can, "copper_wire": _copper_wire, "electrical_parts": _electrical_parts, "light_bulb": _light_bulb,
         "small_engine": _small_engine}


def item(p, outputs):
    parts, opts = ITEMS[p["item"]](p)
    K.publish(outputs, name=p["name"], parts=parts, seed=int(p["seed"]), ground_rot=opts.get("ground"),
              settle_deg=opts.get("settle", 20.0), wear_deg=30.0, inset=False)


BUILDERS = {"spike_pit": spike_pit, "deadfall": deadfall, "tripwire_bell": tripwire_bell, "generator": generator,
            "work_light": work_light, "floodlight": floodlight, "nail_sentry": nail_sentry, "item": item}


def build(params: dict, outputs: list[str]) -> None:
    BUILDERS[params["kind"]](params, outputs)
