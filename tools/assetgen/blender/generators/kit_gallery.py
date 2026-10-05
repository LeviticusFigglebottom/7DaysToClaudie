"""POI kit gallery edges (ADR-0021, docs/POI_KIT.md): where an upper room looks over a tall room's
open space, the builder lays a fascia over the floor slab's edge and stands a railing on the floor
beside it, with a newel post at every metre of the run.

Blender space: the edge runs along X centred on the origin, the origin is on the edge line at the
gallery's floor top (z = 0), the open space (the void) is at -Y and the gallery floor at +Y. Rails
stand 6.5 cm in from the edge, so their feet are on the slab.

params: kind ("fascia" | "rail" | "post"), style ("balustrade" | "rail"), name, seed, broken
  balustrade: painted shoe and turned balusters (8 per metre) under a stained moulded handrail
              1.0 m up; a square newel with a capped top; a painted fascia with a nosing.
  rail:       rough-sawn timber: two rails between posts (barns, mills); a plain board fascia.
  broken:     the railing broken out over the void (the handrail snapped and sagging, balusters or the
              lower rail gone) - the "breach" opening on a gallery edge.
"""
from __future__ import annotations

import math

from mathutils import Matrix

from lib import common
from lib.kit_geo import SIDE_N, KitMesh, bake_colors, collision_box, export_glb
from lib.kit_parts import board

RAIL_Y = 0.065       # centre line of the railing (in from the edge, over the slab)
HANDRAIL_TOP = 1.0
POST = 0.09


def _baluster(km: KitMesh, x: float, z0: float, z1: float) -> None:
    h = z1 - z0
    # Six-sided and seven rings: a turned silhouette at ~70 triangles, eight to the metre (POI_KIT budgets).
    prof = [(0.017, 0.0), (0.023, 0.1 * h), (0.012, 0.18 * h), (0.012, 0.58 * h), (0.02, 0.66 * h),
            (0.013, 0.74 * h), (0.017, h)]
    km.lathe(prof, mat="kit_trim", segments=6, frame=Matrix.Translation((x, RAIL_Y, z0)), cap_bottom=False, cap_top=False)


def _handrail(km: KitMesh, x0: float, x1: float, frame: Matrix | None = None) -> None:
    t = HANDRAIL_TOP
    prof = [(RAIL_Y - 0.034, t - 0.055), (RAIL_Y + 0.034, t - 0.055), (RAIL_Y + 0.034, t - 0.014), (RAIL_Y + 0.022, t),
            (RAIL_Y - 0.022, t), (RAIL_Y - 0.034, t - 0.014)]
    km.prism([prof], x0, x1, axis="x", mat="kit_stairs", side=(SIDE_N,) * 3, grain="x", frame=frame)


def build_fascia(p: dict, name: str, outputs: list[str]) -> None:
    rng = common.rng(int(p.get("seed", 1)))
    km = KitMesh(name)
    km.part(rng.uniform(0.3, 0.7))
    if p.get("style", "balustrade") == "balustrade":
        km.box((-0.5, -0.026, -0.245), (0.5, 0.0, -0.02), "kit_trim", side=SIDE_N, grain="x")
        # nosing over the floor's edge
        prof = [(-0.04, -0.022), (0.0, -0.022), (0.0, 0.012), (-0.03, 0.012), (-0.04, 0.0)]
        km.prism([prof], -0.5, 0.5, axis="x", mat="kit_stairs", side=(SIDE_N,) * 3, grain="x")
    else:
        km.box((-0.5, -0.032, -0.25), (0.5, 0.0, 0.01), "wood_raw", side=SIDE_N, grain="x",
               uv_off=(rng.uniform(0, 3), rng.uniform(0, 3)))
    obj = km.build()
    bake_colors(obj, ground_z=None, samples=8, distance=0.1, strength=0.5, seed=int(p.get("seed", 1)))
    export_glb(outputs[0], [obj])


def build_rail(p: dict, name: str, outputs: list[str]) -> None:
    seed = int(p.get("seed", 1))
    rng = common.rng(seed)
    broken = bool(p.get("broken", False))
    style = p.get("style", "balustrade")
    km = KitMesh(name)
    if style == "balustrade":
        km.part(rng.uniform(0.3, 0.7))
        km.box((-0.5, RAIL_Y - 0.03, 0.0), (0.5, RAIL_Y + 0.03, 0.045), "kit_trim", side=SIDE_N, grain="x", skip=("-z",))
        km.part(rng.uniform(0.4, 0.6))
        gone = set(rng.sample(range(8), 4)) if broken else set()
        for k in range(8):
            if k in gone:
                continue
            x = -0.5 + 0.0625 + k * 0.125
            if broken and x > 0.05:
                # leaning out over the void, still caught in the shoe
                km.lathe([(0.012, 0.0), (0.012, 0.6)], mat="kit_trim", segments=6,
                         frame=Matrix.Translation((x, RAIL_Y, 0.045)) @ Matrix.Rotation(-0.5, 4, "X"), cap_bottom=False)
                continue
            _baluster(km, x, 0.045, HANDRAIL_TOP - 0.055)
        km.part(rng.uniform(0.3, 0.7))
        if broken:
            # handrail snapped mid-span: the left part holds, the right hangs from the far post
            _handrail(km, -0.5, -0.04)
            hang = Matrix.Translation((0.5, RAIL_Y, HANDRAIL_TOP)) @ Matrix.Rotation(0.42, 4, "Y") @ Matrix.Translation((-0.5, -RAIL_Y, -HANDRAIL_TOP))
            _handrail(km, 0.06, 0.5, frame=hang)
        else:
            _handrail(km, -0.5, 0.5)
    else:
        rails = [(0.48, 0.1), (0.96, 0.11)]
        for k, (z, hgt) in enumerate(rails):
            km.part(rng.uniform(0.2, 0.8))
            sag = rng.uniform(-0.012, 0.012)
            if broken and k == 0:
                continue
            if broken and k == 1:
                board(km, (-0.5, RAIL_Y, z), (0.05, RAIL_Y, z - 0.02), (0, 0, 1), hgt, 0.038, mat="wood_raw", rng=rng,
                      end1=rng.uniform(0.04, 0.1), teeth=2)
                board(km, (0.12, RAIL_Y - 0.05, z - 0.42), (0.5, RAIL_Y, z), (0, 0, 1), hgt, 0.038, mat="wood_raw", rng=rng,
                      end0=rng.uniform(0.04, 0.1), teeth=2)
                continue
            board(km, (-0.5, RAIL_Y, z), (0.5, RAIL_Y, z + sag), (0, 0, 1), hgt, 0.038, mat="wood_raw", rng=rng)
    obj = km.build()
    bake_colors(obj, ground_z=0.0, samples=12, distance=0.2, strength=0.6, seed=seed)
    out = [obj]
    if not broken:
        out.append(collision_box(f"{name}_col0", (-0.5, RAIL_Y - 0.04, 0.0), (0.5, RAIL_Y + 0.04, HANDRAIL_TOP)))
    export_glb(outputs[0], out)


def build_post(p: dict, name: str, outputs: list[str]) -> None:
    seed = int(p.get("seed", 1))
    rng = common.rng(seed)
    km = KitMesh(name)
    km.part(rng.uniform(0.3, 0.7))
    if p.get("style", "balustrade") == "balustrade":
        s = POST / 2
        top = HANDRAIL_TOP + 0.12
        km.box((-s, RAIL_Y - s, 0.0), (s, RAIL_Y + s, top - 0.035), "kit_stairs", grain="z", skip=("-z",))
        c = 0.06
        km.box((-c, RAIL_Y - c, top - 0.035), (c, RAIL_Y + c, top - 0.012), "kit_stairs", grain="x")
        km.box((-c + 0.012, RAIL_Y - c + 0.012, top - 0.012), (c - 0.012, RAIL_Y + c - 0.012, top), "kit_stairs", grain="x", skip=("-z",))
        km.lathe([(0.03, 0.0), (0.03, 0.02), (0.018, 0.05), (0.0, 0.065)], mat="kit_stairs", segments=8,
                 frame=Matrix.Translation((0.0, RAIL_Y, top)), cap_bottom=False)
    else:
        s = 0.05
        lean = rng.uniform(-0.02, 0.02)
        km.box((-s, RAIL_Y - s, 0.0), (s, RAIL_Y + s, HANDRAIL_TOP + 0.1 + lean), "wood_raw", grain="z", skip=("-z",),
               uv_off=(rng.uniform(0, 3), rng.uniform(0, 3)))
    obj = km.build()
    bake_colors(obj, ground_z=0.0, samples=8, distance=0.15, strength=0.6, seed=seed)
    export_glb(outputs[0], [obj, collision_box(f"{name}_col0", (-0.05, RAIL_Y - 0.05, 0.0), (0.05, RAIL_Y + 0.05, HANDRAIL_TOP))])


def build(params: dict, outputs: list[str]) -> None:
    name = params.get("name", "gallery")
    {"fascia": build_fascia, "rail": build_rail, "post": build_post}[params.get("kind", "rail")](params, name, outputs)
