"""POI kit board-ups (docs/POI_KIT.md): weathered planks nailed across window / door openings.

Origin = bottom centre of the CLEAR opening on the wall centre plane (same as the glass pieces; for
doors that is the floor). Planks lie on the side A (-Y) casing face (y = -0.10) and stack outward;
rotate 180 deg about Z to board up side B instead.

params: target ("window_1m" | "window_2m" | "door_1m"), name, seed, frac (bool)
  frac: every plank broken into 2-3 splintered pieces (chunk_00..), nails stay with the pieces.
"""
from __future__ import annotations

import math

from mathutils import Matrix, Vector

from lib import common
from lib.kit_dims import CASING_T, CASING_W, HALF_T, OPENINGS
from lib.kit_geo import KitMesh, bake_colors, collision_box, export_glb
from lib.kit_parts import board, nail

PLANK_T = 0.02


def _layout(target: str, rng) -> list[dict]:
    w, h, _ = OPENINGS[target]
    span = w + 2 * CASING_W
    planks = []
    if target == "window_1m":
        zs = [0.1, 0.42, 0.74, 1.04]
        widths = [0.14, 0.18, 0.14, 0.14]
    elif target == "window_2m":
        zs = [0.14, 0.62, 1.06]
        widths = [0.18, 0.18, 0.14]
    else:  # door
        zs = [0.32, 0.72, 1.12, 1.52, 1.92]
        widths = [0.14, 0.18, 0.14, 0.14, 0.18]
    for k, (z, wd) in enumerate(zip(zs, widths)):
        length = min(span + rng.uniform(0.02, 0.1), 0.99 if target != "window_2m" else 1.98)
        planks.append({"z": z + rng.uniform(-0.04, 0.04), "w": wd, "len": length, "ang": rng.uniform(-0.12, 0.12),
                       "dx": rng.uniform(-0.03, 0.03), "layer": k % 2})
    if target == "window_2m":
        # a long diagonal brace across the lot (outermost layer)
        planks.append({"z": h * 0.55, "w": 0.14, "len": 1.95, "ang": math.radians(rng.choice((-1, 1)) * rng.uniform(20, 26)),
                       "dx": 0.0, "layer": 2, "max_half": 0.98})
    return planks


def _plank_frame(p: dict) -> tuple[Matrix, float]:
    y = -(HALF_T + CASING_T) - PLANK_T / 2 - p["layer"] * (PLANK_T + 0.001)
    m = Matrix.Translation((p["dx"], y, p["z"])) @ Matrix.Rotation(p["ang"], 4, "Y")
    return m, y


def build(params: dict, outputs: list[str]) -> None:
    name = params.get("name", "boards")
    target = params.get("target", "window_1m")
    seed = int(params.get("seed", 1))
    rng = common.rng(seed)
    frac = bool(params.get("frac", False))
    planks = _layout(target, rng)
    objs = []
    km = KitMesh(name)
    ymin = 0.0
    for i, p in enumerate(planks):
        m, y = _plank_frame(p)
        L = p["len"]
        if "max_half" in p:
            # keep the diagonal brace inside the piece footprint
            L = min(L, 2 * p["max_half"] / max(0.2, abs(math.cos(p["ang"]))) - 0.02)
        ymin = min(ymin, y - PLANK_T / 2)
        nails = [(-L / 2 + 0.035, s * p["w"] * 0.28) for s in (-1, 1)] + [(L / 2 - 0.035, s * p["w"] * 0.28) for s in (-1, 1)]
        if frac:
            cuts = sorted(rng.uniform(-L * 0.3, L * 0.3) for _ in range(rng.randint(1, 2)))
            xs = [-L / 2] + cuts + [L / 2]
            for j in range(len(xs) - 1):
                k = KitMesh(f"chunk_{len(objs):02d}")
                k.part(rng.uniform(0.2, 0.8))
                a = m @ Vector((xs[j], 0.0, 0.0))
                b = m @ Vector((xs[j + 1], 0.0, 0.0))
                board(k, a, b, m.to_3x3() @ Vector((0, 0, 1)), p["w"], PLANK_T, mat="wood_raw", rng=rng,
                      end0=None if j == 0 else rng.uniform(0.03, 0.08), end1=None if j == len(xs) - 2 else rng.uniform(0.03, 0.08),
                      teeth=1)
                for nx, nz in nails:
                    if xs[j] < nx < xs[j + 1]:
                        nail(k, m @ Vector((nx, -PLANK_T / 2, nz)), m.to_3x3() @ Vector((0, -1, 0)), rng)
                o = k.build(f"chunk_{len(objs):02d}")
                c = sum((v.co for v in o.data.vertices), Vector()) / len(o.data.vertices)
                o.data.transform(Matrix.Translation(-c))
                o.location = c
                bake_colors(o, ground_z=None, samples=8, distance=0.1, seed=seed + len(objs))
                objs.append(o)
            continue
        km.part(rng.uniform(0.15, 0.85))
        a = m @ Vector((-L / 2, 0.0, 0.0))
        b = m @ Vector((L / 2, 0.0, 0.0))
        broken_end = rng.random() < 0.25
        board(km, a, b, m.to_3x3() @ Vector((0, 0, 1)), p["w"], PLANK_T, mat="wood_raw", rng=rng,
              end1=rng.uniform(0.02, 0.05) if broken_end else None, teeth=1)
        km.part(0.5)
        for nx, nz in nails:
            nail(km, m @ Vector((nx, -PLANK_T / 2, nz)), m.to_3x3() @ Vector((0, -1, 0)), rng)
    if frac:
        export_glb(outputs[0], objs)
        return
    obj = km.build()
    bake_colors(obj, ground_z=None, samples=12, distance=0.12, strength=0.7, seed=seed)
    w, h, _ = OPENINGS[target]
    zlo = min(p["z"] - p["w"] for p in planks)
    zhi = max(p["z"] + p["w"] for p in planks)
    col = collision_box(f"{name}_col0", (-w / 2 - CASING_W, ymin, max(0.0, zlo)), (w / 2 + CASING_W, -HALF_T, zhi))
    export_glb(outputs[0], [obj, col])
