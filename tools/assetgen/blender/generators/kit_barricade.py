"""POI kit furniture barricade (docs/POI_KIT.md): a dresser, an upturned chair on top, a table on its
side with its legs out, a chair on its side and planks wedged diagonally across the front, blocking a
doorway. 1.6 (X) x 1.4 (Z) x 0.8 (Y), origin bottom centre, front (-Y) faces the attackers' side.

params: name, seed
Materials: M_door_wood (dresser, table), M_kit_trim (painted chair), M_wood_raw (planks, chair 2),
M_metal_steel (drawer pulls, nails).
"""
from __future__ import annotations

import math

from mathutils import Matrix, Vector

from lib import common
from lib.kit_geo import KitMesh, bake_colors, collision_box, export_glb
from lib.kit_parts import board, nail


def _dresser(km: KitMesh, m: Matrix, rng) -> None:
    w, d, h = 0.85, 0.4, 0.8
    km.part(rng.uniform(0.3, 0.7))
    km.box((-w / 2, -d / 2 + 0.01, 0.07), (w / 2, d / 2, h - 0.022), "door_wood", frame=m, grain="x")
    km.box((-w / 2 + 0.03, -d / 2 + 0.03, 0.0), (w / 2 - 0.03, d / 2 - 0.02, 0.07), "door_wood", frame=m, grain="x",
           skip=("-z", "+z"))
    km.box((-w / 2 - 0.015, -d / 2 - 0.006, h - 0.022), (w / 2 + 0.015, d / 2 + 0.004, h), "door_wood", frame=m, grain="x")
    # three drawers; the middle one hangs open and askew
    dz = (h - 0.022 - 0.09) / 3
    for k in range(3):
        km.part(rng.uniform(0.3, 0.7))
        z0 = 0.09 + k * dz + 0.006
        z1 = z0 + dz - 0.012
        pull = 0.0
        tilt = Matrix.Identity(4)
        if k == 1:
            pull = rng.uniform(0.12, 0.2)
            tilt = Matrix.Rotation(rng.uniform(-0.06, 0.06), 4, "Z")
        f = m @ Matrix.Translation((0, -pull, 0)) @ tilt
        km.box((-w / 2 + 0.025, -d / 2 - 0.006, z0), (w / 2 - 0.025, -d / 2 + 0.012, z1), "door_wood", frame=f, grain="x")
        if pull > 0:
            # drawer box sides visible when pulled out
            km.box((-w / 2 + 0.04, -d / 2 + 0.012, z0 + 0.01), (-w / 2 + 0.055, -d / 2 + 0.012 + pull + 0.05, z1 - 0.02),
                   "wood_raw", frame=f, grain="y")
            km.box((w / 2 - 0.055, -d / 2 + 0.012, z0 + 0.01), (w / 2 - 0.04, -d / 2 + 0.012 + pull + 0.05, z1 - 0.02),
                   "wood_raw", frame=f, grain="y")
            km.box((-w / 2 + 0.055, -d / 2 + 0.012, z0 + 0.01), (w / 2 - 0.055, -d / 2 + 0.012 + pull + 0.05, z0 + 0.02),
                   "wood_raw", frame=f, grain="x")
        km.part(0.5)
        for px in (-0.22, 0.22):
            km.box((px - 0.035, -d / 2 - 0.02, (z0 + z1) / 2 - 0.008), (px + 0.035, -d / 2 - 0.006, (z0 + z1) / 2 + 0.008),
                   "metal_steel", frame=f)


def _chair(km: KitMesh, m: Matrix, rng, mat: str) -> None:
    """Kitchen chair, seat top at 0.45, back toward +Y, origin under the seat centre."""
    sw, sd, sh = 0.42, 0.4, 0.45
    lg = 0.034
    km.part(rng.uniform(0.3, 0.7))
    km.box((-sw / 2, -sd / 2, sh - 0.03), (sw / 2, sd / 2, sh), mat, frame=m, grain="x")
    for sx in (-1, 1):
        for sy in (-1, 1):
            x = sx * (sw / 2 - 0.03)
            y = sy * (sd / 2 - 0.03)
            top = sh - 0.03 if sy < 0 else 0.92
            km.box((x - lg / 2, y - lg / 2, 0.0), (x + lg / 2, y + lg / 2, top), mat, frame=m, grain="z",
                   skip=("+z",) if sy < 0 else ())
    for z in (0.62, 0.74, 0.86):
        km.box((-sw / 2 + 0.03, sd / 2 - 0.045, z), (sw / 2 - 0.03, sd / 2 - 0.018, z + (0.05 if z > 0.8 else 0.035)), mat,
               frame=m, grain="x")
    km.box((-sw / 2 + 0.03, -sd / 2 + 0.02, 0.16), (sw / 2 - 0.03, -sd / 2 + 0.04, 0.19), mat, frame=m, grain="x")


def _table(km: KitMesh, m: Matrix, rng) -> None:
    """Small kitchen table (0.75 square, 0.74 tall), origin bottom centre."""
    s, h = 0.375, 0.74
    km.part(rng.uniform(0.3, 0.7))
    km.box((-s, -s, h - 0.03), (s, s, h), "door_wood", frame=m, grain="x")
    for sx in (-1, 1):
        km.box((sx * (s - 0.045) - 0.012, -s + 0.05, h - 0.12), (sx * (s - 0.045) + 0.012, s - 0.05, h - 0.03), "door_wood",
               frame=m, grain="y")
        km.box((-s + 0.05, sx * (s - 0.045) - 0.012, h - 0.12), (s - 0.05, sx * (s - 0.045) + 0.012, h - 0.03), "door_wood",
               frame=m, grain="x")
        for sy in (-1, 1):
            x, y = sx * (s - 0.05), sy * (s - 0.05)
            km.box((x - 0.022, y - 0.022, 0.0), (x + 0.022, y + 0.022, h - 0.03), "door_wood", frame=m, grain="z",
                   skip=("+z",))


def _nightstand(km: KitMesh, m: Matrix, rng) -> None:
    """Small nightstand (0.42 x 0.35 x 0.55), origin bottom centre, drawer facing -Y."""
    w, d, h = 0.42, 0.35, 0.55
    km.part(rng.uniform(0.3, 0.7))
    km.box((-w / 2, -d / 2, 0.0), (w / 2, d / 2, h - 0.02), "kit_trim", frame=m, grain="z")
    km.box((-w / 2 - 0.01, -d / 2 - 0.01, h - 0.02), (w / 2 + 0.01, d / 2 + 0.005, h), "kit_trim", frame=m, grain="x")
    km.box((-w / 2 + 0.02, -d / 2 - 0.012, h - 0.17), (w / 2 - 0.02, -d / 2, h - 0.04), "kit_trim", frame=m, grain="x")
    km.box((-w / 2 + 0.02, -d / 2 - 0.004, 0.04), (w / 2 - 0.02, -d / 2, h - 0.2), "kit_trim", frame=m, grain="z")
    km.part(0.5)
    km.box((-0.012, -d / 2 - 0.03, h - 0.112), (0.012, -d / 2 - 0.012, h - 0.098), "metal_steel", frame=m)


def build(params: dict, outputs: list[str]) -> None:
    name = params.get("name", "barricade_furniture")
    seed = int(params.get("seed", 1))
    rng = common.rng(seed)
    km = KitMesh(name)
    # Dresser (left half, pushed against the doorway at the back).
    md = Matrix.Translation((-0.375, 0.2, 0.0)) @ Matrix.Rotation(rng.uniform(-0.03, 0.02), 4, "Z")
    _dresser(km, md, rng)
    # Upturned chair on the dresser, its back hanging down behind it.
    mc = md @ Matrix.Translation((rng.uniform(-0.1, 0.06), 0.06, 0.8 + 0.45)) @ Matrix.Rotation(math.pi, 4, "Y") @ \
        Matrix.Rotation(rng.uniform(-0.2, 0.2), 4, "Z")
    _chair(km, mc, rng, "kit_trim")
    # Table on its side (top at the back, facing +Y), legs sticking out toward -Y.
    mt = Matrix.Translation((0.425, 0.385, 0.38)) @ Matrix.Rotation(rng.uniform(-0.05, 0.05), 4, "Z") @ \
        Matrix.Rotation(-math.pi / 2, 4, "X") @ Matrix.Translation((0.0, 0.0, -0.74))
    _table(km, mt, rng)
    # Tipped-over nightstand in front of the dresser.
    mn = Matrix.Translation((-0.42, -0.21, 0.21)) @ Matrix.Rotation(rng.uniform(-0.1, 0.1), 4, "Z") @ \
        Matrix.Rotation(-math.pi / 2, 4, "Y") @ Matrix.Translation((0.0, 0.0, -0.275))
    _nightstand(km, mn, rng)
    # Planks wedged diagonally across the front, nailed to the furniture.
    for k in range(3):
        km.part(rng.uniform(0.2, 0.8))
        x0 = rng.uniform(-0.75, -0.55) if k % 2 == 0 else rng.uniform(0.55, 0.75)
        a = Vector((x0, -0.385 + 0.025 * k, 0.012))
        b = Vector((-x0 * rng.uniform(0.75, 0.95), -0.06 + 0.02 * k, rng.uniform(0.95, 1.2)))
        wd = (b - a).cross(Vector((0, 1, 0))).normalized()
        board(km, a, b, wd, rng.choice((0.14, 0.18)), 0.022, mat="wood_raw", rng=rng,
              end1=rng.uniform(0.02, 0.05) if rng.random() < 0.4 else None, teeth=1)
        n = (b - a).cross(wd).normalized()
        if n.y > 0:
            n = -n
        for t in (0.82, 0.88):
            nail(km, a + (b - a) * t + n * 0.011, n, rng)
    obj = km.build()
    bake_colors(obj, ground_z=0.0, samples=16, distance=0.35, strength=0.85, seed=seed)
    cols = [collision_box(f"{name}_col0", (-0.8, -0.4, 0.0), (0.8, 0.4, 1.2))]
    export_glb(outputs[0], [obj] + cols)
