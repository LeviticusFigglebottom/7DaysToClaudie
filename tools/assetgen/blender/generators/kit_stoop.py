"""POI kit stoops (TD-221): the steps PoiBuilder puts up to a raised exterior doorway (PoiBuilder.stoops).

params: kind (wood | concrete), steps (1-3), width (1 or 2 m), seed
Origin = the wall end of the stoop at grade, centred on the doorway; the stoop runs out along -Y (Godot
+Z, away from the wall) and its top stands at steps x RISE (the builder scales Z to the doorway's real
rise, picking `steps` = the rise / RISE rounded, 1..3; past three steps it lengthens the run too).
  wood:      open timber steps: sawtooth stringers (3 for 1 m, 4 for 2 m), painted risers, two tread
             boards a step with a small nosing; TREAD deep a step, no landing (the threshold is the
             landing). Three steps get a plain handrail on posts at one side (both for 2 m).
  concrete:  a cast stoop: a LANDING deep top slab at the sill, then TREAD steps down, a chamfered
             nosing on each, solid cheeks to the ground, a footing lip; two or more steps get painted
             pipe rails down both sides.
Collision: one box per step (PoiBuilder adds its own walkable ramp and landing; these keep the model
usable as a free-standing prop).
"""
from __future__ import annotations

from mathutils import Vector

from lib import common
from lib.kit_geo import SIDE_N, KitMesh, axis_frame, bake_colors, collision_box, export_glb

RISE = 0.2        # nominal riser (m)
TREAD = 0.3       # tread depth (m)
LANDING = 0.9     # concrete landing depth (m)


def depth(kind: str, steps: int) -> float:
    """Run of the stoop out from the wall (m): PoiBuilder mirrors this (STOOP_TREAD / STOOP_LANDING)."""
    return (LANDING + TREAD * (steps - 1)) if kind == "concrete" else TREAD * steps


def _wood(km: KitMesh, rng, n: int, W: float) -> list:
    hw = W / 2
    tt = 0.032
    D = depth("wood", n)
    H = n * RISE
    # Sawtooth stringer profile (Y, Z): back at the wall (y 0) up to the top tread, down the steps.
    prof = [(-D + 0.02, 0.0), (0.0, 0.0), (0.0, H - tt)]
    for k in range(n, 0, -1):                      # step k (1 = bottom) has its tread at k * RISE
        y_front = -TREAD * (n - k + 1)
        prof += [(y_front, k * RISE - tt), (y_front, (k - 1) * RISE - tt if k > 1 else 0.06)]
    prof = [(y, max(0.0, z)) for y, z in prof]
    count = 3 if W <= 1.01 else 4
    for i in range(count):
        x = -hw + 0.04 + i * (W - 0.08) / (count - 1)
        km.part(rng.uniform(0.3, 0.7))
        km.prism([prof], x - 0.02, x + 0.02, axis="x", mat="wood_raw", side=(SIDE_N,) * 3, grain="y")
    for k in range(1, n + 1):
        y_back = -TREAD * (n - k)                   # tread k spans y_back - TREAD .. y_back
        y_front = y_back - TREAD
        z = k * RISE
        km.part(rng.uniform(0.3, 0.7))
        km.box((-hw, y_front + 0.02, (k - 1) * RISE), (hw, y_front + 0.04, z - tt), "wood_painted", grain="x",
               skip=("-z", "+z"))
        for b in range(2):
            km.part(rng.uniform(0.3, 0.7))
            ya = y_front - 0.015 + b * (TREAD / 2 + 0.008)
            yb = ya + TREAD / 2 + 0.004 if b == 0 else y_back
            km.box((-hw, ya, z - tt), (hw, yb - 0.004, z), "wood_painted", grain="x",
                   uv_off=(rng.uniform(0, 3), rng.uniform(0, 3)))
    if n >= 3:
        rail_h = 0.86
        for sx in ((1,) if W <= 1.01 else (1, -1)):
            x = sx * (hw - 0.03)
            km.part(rng.uniform(0.3, 0.7))
            foot = (-D + 0.1, RISE * 0.5)
            for (py, pz) in (foot, (-0.06, H)):
                km.box((x - 0.035, py - 0.035, 0.0), (x + 0.035, py + 0.035, pz + rail_h), "wood_raw", grain="z")
            # the rail: a 2x4 on edge along the slope from the foot post to the top post
            a = Vector((x, foot[0], foot[1] + rail_h - 0.02))
            b = Vector((x, -0.06, H + rail_h - 0.02))
            along = (b - a)
            L = along.length
            fr = axis_frame(a, (0.0, along.y / L, along.z / L), (1.0, 0.0, 0.0))
            km.box((-0.05, -0.02, -0.04), (L + 0.05, 0.02, 0.04), "wood_raw", frame=fr, grain="x")
    return [collision_box(f"col{k}", (-hw, -TREAD * (n - k + 1), 0.0), (hw, 0.0, k * RISE)) for k in range(1, n + 1)]


def _concrete(km: KitMesh, rng, n: int, W: float) -> list:
    hw = W / 2
    D = depth("concrete", n)
    H = n * RISE
    c = 0.018                                       # nosing chamfer
    # Side profile (Y, Z) of the whole stoop: landing at the top, steps down to the yard.
    prof = [(0.0, 0.0), (0.0, H)]
    y = -LANDING
    prof += [(y + c, H), (y, H - c)]
    for k in range(n - 1, 0, -1):                   # the step whose top is k * RISE
        prof += [(y, k * RISE)]
        y -= TREAD
        prof += [(y + c, k * RISE), (y, k * RISE - c)]
    prof += [(y, 0.0)]
    km.part(rng.uniform(0.35, 0.65))
    km.prism([prof], -hw, hw, axis="x", mat="concrete", side=(SIDE_N,) * 3, grain="y")
    # A footing lip round the foot (a little proud and rough, half buried).
    km.part(rng.uniform(0.3, 0.6))
    km.box((-hw - 0.03, -D - 0.03, -0.05), (hw + 0.03, 0.0, 0.03), "concrete", skip=("-z", "+y"))
    cols = [collision_box("col_landing", (-hw, -LANDING, 0.0), (hw, 0.0, H))]
    for k in range(1, n):
        cols.append(collision_box(f"col{k}", (-hw, -LANDING - TREAD * (n - k), 0.0), (hw, -LANDING, k * RISE)))
    if n >= 2:
        rail_h = 0.86
        r = 0.021
        for sx in (1, -1):
            x = sx * (hw - 0.06)
            km.part(rng.uniform(0.3, 0.7))
            top = (-0.12, H)
            mid = (-LANDING + 0.06, H)
            foot = (-D + 0.12, RISE)
            for py, pz in (top, mid, foot):
                # lathe works about the local origin: shift each post into place
                km.lathe([(r, pz - 0.02), (r, pz + rail_h)], mat="metal_painted", segments=8)
                _shift_last(km, 16, (x, py, 0.0))
            for (a2, b2) in ((top, mid), (mid, foot)):
                a = Vector((x, a2[0], a2[1] + rail_h))
                b = Vector((x, b2[0], b2[1] + rail_h))
                along = b - a
                L = along.length
                fr = axis_frame(a, (0.0, along.y / L, along.z / L), (1.0, 0.0, 0.0))
                km.box((-0.02, -r, -r), (L + 0.02, r, r), "metal_painted", frame=fr)
    return cols


def _shift_last(km: KitMesh, npts: int, off) -> None:
    """Moves the last `npts` points by `off` (lathe builds about the origin)."""
    v = Vector(off)
    for i in range(len(km.co) - npts, len(km.co)):
        km.co[i] = km.co[i] + v


def build(params: dict, outputs: list[str]) -> None:
    name = params.get("name", "stoop")
    kind = params["kind"]
    n = max(1, min(3, int(params.get("steps", 1))))
    W = float(params.get("width", 1.0))
    seed = int(params.get("seed", 1))
    rng = common.rng(seed)
    km = KitMesh(name)
    cols = _concrete(km, rng, n, W) if kind == "concrete" else _wood(km, rng, n, W)
    obj = km.build()
    bake_colors(obj, ground_z=0.0, samples=12, distance=0.3, strength=0.7, seed=seed)
    export_glb(outputs[0], [obj] + [_named(c, name) for c in cols])


def _named(col, name: str):
    col.name = f"{name}_{col.name}"
    return col
