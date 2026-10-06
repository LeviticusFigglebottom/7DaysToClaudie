"""Base-building holders, stairs and door (ADR-0035): log rack, stick rack, stone pile, log stairs, stick
door. Built from the building-log toolkit in structure_logs (same bark field, axe-cut ends, hewn
faces, rope lashings) so they sit with the log walls.

Frames (Blender, exported Z-up -> Godot Y-up): front faces Blender -Y = Godot +Z, origin bottom
centre unless stated.
  * Racks: what they hold are separate mesh nodes `fill_01`.. in fill order (the game shows the
    first N); each node's origin is the centre of what it holds. Their AO is baked against the
    frame but the frame's own AO is baked alone, so an empty rack has no ghost shadows.
  * log_stairs: origin at ground level at the centre of the front edge of the first step; the
    flight climbs toward Godot +Z (Blender -Y): 8 risers of 0.29 m over 8 treads of 0.45 m, 1.2 m
    wide. No collision proxy (the game builds the step collision).
  * stick_door: nodes `frame` and `leaf`; the leaf's origin is the hinge axis at the inner face of
    the left post (Godot (-0.5, 0, 0)); closed it spans +X from the hinge, 1.0 x 2.0 m, in the frame
    plane (z = 0 in Godot).
params: kind, name, seed."""
from __future__ import annotations

import math
import random

import bpy
from mathutils import Matrix, Vector

from generators import structure_logs as L
from lib import item_kit as K, vcolor


def _finish(outputs, name, frame_parts, seed, fills, *, colliders=(), pivots=None, foliage=()):
    """structure_logs.finish, but the frame's AO ignores the fills (they come and go)."""
    obj = K.join(frame_parts, name)
    fol = [o for o in foliage if o is not None]
    for i, o in enumerate([obj] + list(fills) + fol):
        K.bake_wear_and_masks(o, wear_deg=35.0, seed=seed + i * 17)
    for o in [obj] + list(fills):
        vcolor.set_channel(o, 2, L.moss_mask(seed))
    for o in fol:
        zmin = min(v.co.z for v in o.data.vertices)
        K.foliage_wind(o, base_z=zmin, height=0.6, amount=0.3)
    K.bake_ao([obj] + fol, ground=True, samples=16)
    if fills:
        vcolor.bake_ao(list(fills), samples=16, distance=0.35, strength=0.9, ground=True, extra_occluders=[obj])
    pivots = pivots or {}
    for o in fills:
        piv = pivots.get(o.name)
        if piv is None:
            V = K.world_verts([o])
            lo, hi = V.min(0), V.max(0)
            piv = Vector(((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2))
        piv = Vector(piv)
        o.data.transform(Matrix.Translation(-piv))
        o.location = piv
    bpy.context.view_layer.update()
    meshes = [obj] + fol + list(fills)
    K.export_objects(outputs[0], meshes + [c for c in colliders if c is not None])
    print(f"[structure] {name}: {K.tri_count(meshes)} tris -> {outputs[0]}")
    for o in meshes:
        V = K.world_verts([o])
        lo, hi = V.min(0), V.max(0)
        print(f"[structure]   node {o.name}: {K.tri_count([o])} tris, bounds {tuple(round(float(a), 3) for a in lo)} .. "
              f"{tuple(round(float(a), 3) for a in hi)}, origin {tuple(round(a, 3) for a in o.location)}")


# ------------------------------------------------------------------------------------------------
# Log rack (The Forest's log holder)
# ------------------------------------------------------------------------------------------------

LOG_D = 2 * 0.168
RACK_ROWS = (5, 4, 3)


def log_rack(p, outputs):
    """A sled-like cradle: three sill logs across (Y) keep the logs off the ground, a pair of lashed
    stakes rises at each end of every sill, and a rail along each side ties the stake tops. Twelve
    full 4 m logs lie along X in a 5-4-3 pyramid (fill_01..05 bottom row, 06..09, 10..12)."""
    seed = int(p["seed"])
    r = random.Random(seed)
    mb = K.MB()
    sill_r = 0.075
    half_w = 2.5 * LOG_D                              # outer log faces
    stake_y = half_w + 0.05
    for k, x in enumerate((-1.55, 0.0, 1.55)):
        x += r.uniform(-0.04, 0.04)
        L.pole(mb, (x, -stake_y - 0.06, sill_r * 0.85), (x + r.uniform(-0.03, 0.03), stake_y + 0.06, sill_r * 0.85), sill_r, sill_r * 0.92,
               seed + k, sides=10, bend=0.012)
        for sgn in (-1, 1):
            base = Vector((x + sgn * 0.0, sgn * stake_y, -0.06))
            top = Vector((x + r.uniform(-0.03, 0.03), sgn * (stake_y + 0.01), 1.27 + r.uniform(-0.03, 0.03)))
            L.pole(mb, base, top, 0.045, 0.039, seed + 10 + k * 2 + (sgn > 0), sides=8, bend=0.01, caps=(False, False))
            # pointed top
            d = (top - base).normalized()
            K.tube(mb, [top, top + d * 0.05], [0.04, 0.008], sides=8, mat="struct_log_hewn", caps=(False, True), smooth=False)
            # lashed to the sill, and to the side rail
            L.bind(mb, (x, sgn * stake_y, sill_r * 1.1), (0, 0, 1), 0.05, seed + 20 + k, turns=3, cord=0.005, width=0.05, per_turn=7)
            L.cross_lash(mb, (x, sgn * (stake_y + 0.035), 1.13), (0, 0, 1), (1, 0, 0), 0.05, seed + 30 + k)
    for sgn in (-1, 1):
        L.pole(mb, (-2.08, sgn * (stake_y + 0.074), 1.13), (2.08, sgn * (stake_y + 0.074), 1.15 + r.uniform(-0.02, 0.02)), 0.034, 0.03,
               seed + 50 + (sgn > 0), sides=8, n=7, bend=0.02)
    frame = mb.build("log_rack", sharp_deg=55)
    fills = []
    z0 = sill_r * 1.7 + 0.168
    n = 0
    for row, count in enumerate(RACK_ROWS):
        z = z0 + row * LOG_D * 0.866
        for j in range(count):
            y = (j - (count - 1) / 2) * LOG_D
            n += 1
            o = L.light_log(f"fill_{n:02d}", seed + 100 + n, knots=2)
            m = Matrix.Translation((r.uniform(-0.06, 0.06), y, z)) @ Matrix.Rotation(r.uniform(-0.012, 0.012), 4, "Z") @ \
                Matrix.Rotation(r.uniform(0, 6.28), 4, "X")
            L.place(o, m)
            fills.append(o)
    col = K.collider_box("log_rack", (-2.1, -stake_y - 0.11, 0.0), (2.1, stake_y + 0.11, 1.3))
    _finish(outputs, "log_rack", [frame], seed, fills, colliders=[col])


# ------------------------------------------------------------------------------------------------
# Stick rack
# ------------------------------------------------------------------------------------------------

def _stick_bundle(name: str, seed: int, center, height: float) -> bpy.types.Object:
    """Six or seven sticks standing on end, leaning together, bound with a cord band."""
    r = random.Random(seed)
    mb = K.MB()
    c = Vector(center)
    count = r.choice((6, 7))
    for k in range(count):
        a = 2 * math.pi * k / count + r.uniform(-0.3, 0.3)
        d = 0.045 if k else 0.0
        if k == 0:
            d = 0.0
        foot = c + Vector((math.cos(a) * (d + 0.012), math.sin(a) * (d + 0.012), 0.0))
        h = height * r.uniform(0.78, 1.0)
        lean = Vector((math.cos(a) * r.uniform(0.01, 0.05), math.sin(a) * r.uniform(0.01, 0.05), h))
        rr = r.uniform(0.016, 0.022)
        pts = [foot, foot + lean * 0.5 + Vector((r.uniform(-0.008, 0.008), r.uniform(-0.008, 0.008), 0)), foot + lean]
        K.stick(mb, pts, rr, rr * 0.8, sides=5, seed=seed + k, bark="item_bark_twig", lumpy=0.08)
    L.bind(mb, c + Vector((0, 0, height * 0.52)), (0, 0, 1), 0.075, seed + 50, turns=3, cord=0.0035, width=0.04, mat="item_cordage",
           per_turn=10)
    return mb.build(name, sharp_deg=55)


def stick_rack(p, outputs):
    """An upright lashed frame (four corner posts, floor slats, side rails) holding eight bundles of
    sticks standing on end: fill_01..04 the back row left to right, fill_05..08 the front row."""
    seed = int(p["seed"])
    r = random.Random(seed)
    mb = K.MB()
    px, py = 0.46, 0.25
    for k, (sx, sy) in enumerate(((-1, -1), (1, -1), (-1, 1), (1, 1))):
        L.pole(mb, (sx * px, sy * py, -0.04), (sx * px + r.uniform(-0.01, 0.01), sy * py, 1.17), 0.034, 0.03, seed + k, sides=7, n=4)
    for sy in (-1, 1):
        for z in (0.09, 0.62, 1.08):
            L.pole(mb, (-px - 0.06, sy * (py + 0.03), z), (px + 0.06, sy * (py + 0.03), z + r.uniform(-0.01, 0.01)), 0.02, 0.018,
                   seed + 10 + int(z * 10) + (sy > 0), bark="item_bark_twig", sides=6, n=4)
            for sx in (-1, 1):
                L.bind(mb, (sx * px, sy * (py + 0.015), z), (1, 0, 0), 0.038, seed + 20 + int(z * 10), turns=3, cord=0.0035, width=0.05,
                       mat="item_cordage", per_turn=7)
    for sx in (-1, 1):
        for z in (0.09, 1.08):
            L.pole(mb, (sx * (px + 0.03), -py - 0.06, z + 0.03), (sx * (px + 0.03), py + 0.06, z + 0.03), 0.019, 0.017,
                   seed + 30 + int(z * 10) + (sx > 0), bark="item_bark_twig", sides=6, n=3)
    # floor slats the bundles stand on
    for k, x in enumerate((-0.33, -0.11, 0.11, 0.33)):
        L.pole(mb, (x, -py - 0.02, 0.135), (x + r.uniform(-0.02, 0.02), py + 0.02, 0.135), 0.022, 0.02, seed + 40 + k,
               bark="item_bark_twig", sides=6, n=3)
    frame = mb.build("stick_rack", sharp_deg=55)
    fills = []
    n = 0
    for y in (0.115, -0.115):                         # back row first (Blender +Y = Godot back)
        for x in (-0.33, -0.11, 0.11, 0.33):
            n += 1
            fills.append(_stick_bundle(f"fill_{n:02d}", seed + 100 + n, (x + r.uniform(-0.01, 0.01), y, 0.155), 1.0))
    col = K.collider_box("stick_rack", (-0.5, -0.3, 0.0), (0.5, 0.3, 1.2))
    _finish(outputs, "stick_rack", [frame], seed, fills, colliders=[col])


# ------------------------------------------------------------------------------------------------
# Stone pile
# ------------------------------------------------------------------------------------------------

def stone_pile(p, outputs):
    """A low ring of sharpened stakes woven with two withies, holding loose stones built up from the
    bottom: fill_01..10, one or two stones each."""
    seed = int(p["seed"])
    r = random.Random(seed)
    mb = K.MB()
    R = 0.52
    ns = 13
    tops = []
    for k in range(ns):
        a = 2 * math.pi * k / ns + r.uniform(-0.05, 0.05)
        base = Vector((math.cos(a) * R, math.sin(a) * R, -0.05))
        h = r.uniform(0.5, 0.58)
        top = Vector((math.cos(a) * (R + 0.03), math.sin(a) * (R + 0.03), h))
        L.pole(mb, base, top, 0.026, 0.022, seed + k, sides=6, n=3, caps=(False, True))
        tops.append(a)
    # withies woven in and out of the stakes
    for j, z in enumerate((0.13, 0.36)):
        for strand in range(2):
            pts = []
            steps = ns * 6
            for i in range(steps):
                a = 2 * math.pi * i / steps
                weave = 0.028 * math.cos(ns * a + (j + strand) * math.pi)
                pts.append(Vector((math.cos(a) * (R + 0.01 + weave), math.sin(a) * (R + 0.01 + weave),
                                   z + strand * 0.03 + 0.01 * math.sin(3 * a + j))))
            K.tube(mb, pts, 0.014 - strand * 0.002, sides=4, mat="item_bark_twig", closed=True, up=Vector((0, 0, 1)))
    frame = mb.build("stone_pile", sharp_deg=55)
    # stones: (angle, distance, layer) per fill; one or two stones each, bottom layer first
    layout = [
        [(0.3, 0.28, 0)], [(1.6, 0.27, 0), (2.3, 0.33, 0)], [(3.3, 0.28, 0)], [(4.5, 0.3, 0), (5.3, 0.26, 0)], [(0.0, 0.0, 0)],
        [(0.9, 0.18, 1), (2.0, 0.2, 1)], [(3.4, 0.19, 1)], [(4.6, 0.2, 1), (5.7, 0.17, 1)], [(1.2, 0.07, 2)], [(4.0, 0.08, 2), (2.6, 0.12, 2)],
    ]
    fills = []
    for n, group in enumerate(layout, start=1):
        parts = []
        for j, (a, d, layer) in enumerate(group):
            sz = (r.uniform(0.17, 0.24), r.uniform(0.14, 0.2), r.uniform(0.11, 0.15))
            z = [0.0, 0.11, 0.22][layer]
            cen = (math.cos(a) * d, math.sin(a) * d, z)
            st = L.stone(f"s{n}_{j}", sz, seed + 200 + n * 7 + j, cen, mat="item_stone_fire", tris=110, lump=0.22)
            st.data.transform(Matrix.Translation(cen) @ Matrix.Rotation(r.uniform(0, 6.28), 4, "Z") @
                              Matrix.Rotation(r.uniform(-0.25, 0.25), 4, "X") @ Matrix.Translation(-Vector(cen)))
            parts.append(st)
        fills.append(K.join(parts, f"fill_{n:02d}"))
    col = K.collider_box("stone_pile", (-0.6, -0.6, 0.0), (0.6, 0.6, 0.5))
    _finish(outputs, "stone_pile", [frame], seed, fills, colliders=[col])


# ------------------------------------------------------------------------------------------------
# Log stairs
# ------------------------------------------------------------------------------------------------

RISE, RUN, STEPS, WIDTH = 0.29, 0.45, 8, 1.2


def log_stairs(p, outputs):
    """Two log stringers on the slope, eight split-log treads (flat face up, round underside seated on
    the stringers) pegged to them, and a rough pole handrail on posts lashed to the right stringer."""
    seed = int(p["seed"])
    r = random.Random(seed)
    parts = []
    mb = K.MB()
    tread_r = 0.215
    tread_depth = 0.88
    slope = RISE / RUN
    sx = 0.43
    sr = 0.12
    cosang = RUN / math.hypot(RUN, RISE)

    def line_z(run: float) -> float:                  # underside of the treads along the flight
        return slope * run + RISE * 0.5 - tread_r * tread_depth
    for k, sgn in enumerate((-1, 1)):
        a = Vector((sgn * sx, 0.05, line_z(-0.05) - sr / cosang))
        b = Vector((sgn * sx, -(RUN * STEPS - 0.06), line_z(RUN * STEPS - 0.06) - sr / cosang))
        # sink the foot into the ground a little
        st = L.light_log(f"stringer{k}", seed + 10 + k, length=(b - a).length, crown=sr, sides=12, step=0.3, knots=2)
        L.place(st, L.axis_matrix(a, b))
        parts.append(st)
    for i in range(STEPS):
        top = (i + 1) * RISE
        y = -(i + 0.5) * RUN
        mb.push(Matrix.Translation((r.uniform(-0.015, 0.015), y + r.uniform(-0.01, 0.01), top)) @
                Matrix.Rotation(r.uniform(-0.01, 0.01), 4, "Y") @ Matrix.Rotation(r.uniform(-0.02, 0.02), 4, "Z"))
        L.half_log(mb, WIDTH + r.uniform(-0.02, 0.02), tread_r, seed + 20 + i, sides=10, steps=4, depth=tread_depth)
        mb.pop()
        # wooden pegs through the tread into each stringer
        for sgn in (-1, 1):
            for dy in (-0.06, 0.07):
                c = Vector((sgn * sx + r.uniform(-0.01, 0.01), y + dy, top + 0.004))
                K.tube(mb, [c - Vector((0, 0, 0.012)), c], 0.016, sides=7, mat="struct_log_end", cap_mat="struct_log_end", cap_uv="disc",
                       caps=(False, True), smooth=False)
    # handrail on the right (+X): posts lashed to the stringer, a rail pole along the slope
    hx = sx + sr + 0.045
    posts = (0, 3, 6)
    rail_pts = []
    for j, i in enumerate(posts):
        y = -(i + 0.5) * RUN
        zb = line_z(-y) - sr / cosang - 0.12
        zt = (i + 1) * RISE + 0.92
        L.pole(mb, (hx, y, zb), (hx + r.uniform(-0.01, 0.01), y, zt), 0.045, 0.04, seed + 40 + j, sides=8, n=4)
        L.bind(mb, (hx - 0.02, y, line_z(-y) - sr / cosang + 0.01), (0, 0, 1), 0.07, seed + 45 + j, turns=4, cord=0.0055, width=0.07)
        rail_pts.append(Vector((hx, y, zt - 0.03)))
    d = (rail_pts[-1] - rail_pts[0]).normalized()
    ra = rail_pts[0] - d * 0.25
    rb = rail_pts[-1] + d * 0.55
    L.pole(mb, ra + Vector((0.0, 0, 0.0)), rb, 0.04, 0.034, seed + 50, sides=8, n=7, bend=0.015)
    for j, q in enumerate(rail_pts):
        L.cross_lash(mb, q + Vector((0, 0, 0.005)), (0, 0, 1), d, 0.045, seed + 60 + j, cord=0.0055)
    parts.append(mb.build("log_stairs", sharp_deg=55))
    L.finish(outputs, "log_stairs", parts, seed, ground=True, ao_samples=16)


# ------------------------------------------------------------------------------------------------
# Stick door
# ------------------------------------------------------------------------------------------------

DOOR_W, DOOR_H = 1.0, 2.0
POST_X = 0.55
POST_R = 0.05


def stick_door(p, outputs):
    """Frame: two posts and a lashed lintel (1.2 x 2.2 m). Leaf: lashed vertical sticks with two cross
    battens and a diagonal brace on the back, rope hinges on the left post, a rope pull in front."""
    seed = int(p["seed"])
    r = random.Random(seed)
    fm = K.MB()
    for k, sgn in enumerate((-1, 1)):
        L.pole(fm, (sgn * POST_X, 0.0, 0.0), (sgn * POST_X + r.uniform(-0.008, 0.008), r.uniform(-0.008, 0.008), 2.2 - 0.005), POST_R * 1.05,
               POST_R * 0.92, seed + k, sides=10, n=5, bend=0.008)
    lz = 2.2 - 0.045 - 0.03
    L.pole(fm, (-0.62, 0.0, lz), (0.62, 0.0, lz + r.uniform(-0.01, 0.01)), 0.045, 0.04, seed + 5, sides=10, n=5, bend=0.01)
    for k, sgn in enumerate((-1, 1)):
        L.cross_lash(fm, (sgn * POST_X, 0.0, lz), (0, 0, 1), (1, 0, 0), 0.055, seed + 10 + k, cord=0.0055)
    # rope hinges: a few turns of rope round the left post and the leaf's hinge stick together
    hinge_x = -POST_X + POST_R + 0.04
    cxm, ax_ = (-POST_X + hinge_x) / 2, (hinge_x + POST_X) / 2 + 0.05
    for j, z in enumerate((0.35, 1.65)):
        for t in range(3):
            pts = [Vector((cxm + math.cos(2 * math.pi * i / 16) * ax_, math.sin(2 * math.pi * i / 16) * 0.058,
                           z + t * 0.013 + 0.004 * math.sin(4 * math.pi * i / 16))) for i in range(16)]
            K.tube(fm, pts, 0.0055, sides=5, mat="item_rope", closed=True, up=Vector((0, 0, 1)))
    frame = fm.build("frame", sharp_deg=55)
    # leaf, modelled in place (closed): x from -0.5 to 0.5
    lm = K.MB()
    n = 11
    x0 = -POST_X + POST_R
    for k in range(n):
        x = x0 + 0.045 + (DOOR_W - 0.09) * k / (n - 1) + r.uniform(-0.004, 0.004)
        rr = r.uniform(0.036, 0.047)
        top = DOOR_H - r.uniform(0.04, 0.1)
        xt = x + r.uniform(-0.012, 0.012)
        L.pole(lm, (x, 0.0, 0.03 + r.uniform(0, 0.02)), (xt, 0.0, top), rr, rr * 0.88,
               seed + 20 + k, sides=8, n=4, bend=0.0, caps=(True, False))
        # axe-pointed tops
        K.tube(lm, [Vector((xt, 0.0, top)), Vector((xt, 0.0, top + r.uniform(0.04, 0.08)))], [rr * 0.88, rr * 0.12], sides=8,
               mat="struct_log_hewn", caps=(False, True), smooth=False)
    by = 0.08
    battens = (0.38, 1.62)
    for j, z in enumerate(battens):
        L.pole(lm, (x0 + 0.02, by, z), (x0 + DOOR_W - 0.02, by, z + r.uniform(-0.01, 0.01)), 0.036, 0.032, seed + 40 + j, sides=8, n=5)
        for k in range(0, n, 2):
            x = x0 + 0.045 + (DOOR_W - 0.09) * k / (n - 1)
            L.bind(lm, (x, by * 0.5, z), (0, 1, 0), 0.03, seed + 50 + k + j * 20, turns=2, cord=0.004, width=0.03, mat="item_cordage",
                   per_turn=8)
    # diagonal brace: low on the hinge side up to high on the latch side (in compression)
    a = Vector((x0 + 0.1, by, battens[0] + 0.07))
    b = Vector((x0 + DOOR_W - 0.1, by, battens[1] - 0.07))
    L.pole(lm, a, b, 0.032, 0.03, seed + 60, sides=8, n=5)
    # rope pull on the front (Blender -Y) at the latch side
    pull = [Vector((x0 + DOOR_W - 0.12, -0.05, 1.08)), Vector((x0 + DOOR_W - 0.09, -0.1, 1.0)), Vector((x0 + DOOR_W - 0.12, -0.11, 0.92)),
            Vector((x0 + DOOR_W - 0.15, -0.05, 0.9))]
    K.tube(lm, K.polyline_resample(pull, 9), 0.008, sides=6, mat="item_rope")
    leaf = lm.build("leaf", sharp_deg=55)
    hinge = Vector((-POST_X + POST_R, 0.0, 0.0))
    L.finish(outputs, "frame", [frame], seed, separate=[leaf], pivots={"leaf": hinge}, ground=True, ao_samples=16)


BUILDERS = {"log_rack": log_rack, "stick_rack": stick_rack, "stone_pile": stone_pile, "log_stairs": log_stairs, "stick_door": stick_door}


def build(params: dict, outputs: list[str]) -> None:
    BUILDERS[params["kind"]](params, outputs)
