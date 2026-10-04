"""POI kit stairs, banister, landing railing and wall ladder (docs/POI_KIT.md).

params: kind ("stairs" | "stair_railing" | "railing" | "ladder"), name, seed
  stairs:        12 risers x 0.25 over 4.0 m, origin = bottom-front edge centre, ascends +Y,
                 x in [-0.5, 0.5]. Stained treads (M_kit_stairs), painted risers / closed stringers /
                 soffit (M_kit_trim). Collision = convex ramp through the tread midpoints.
  stair_railing: banister for stairs_straight, centred on x = 0: place it at x = +-0.48 relative to the
                 stairs origin (the centre line of a stringer). Same y/z origin as the stairs.
  railing:       1.0 m landing railing, 0.95 tall, origin bottom centre, runs along X (chainable).
  ladder:        0.5 x 3.0 wooden wall ladder, origin on the wall plane (bottom centre), ladder at -Y.
"""
from __future__ import annotations

import math

from mathutils import Matrix, Vector

from lib import common
from lib.kit_dims import (HANDRAIL_ABOVE_NOSING, RAILING_H, STAIR_NOSING, STAIR_RISE, STAIR_RISERS, STAIR_RUN,
                          STAIR_W, STRINGER_DEPTH, STRINGER_T, stair_nosing_z, stringer_top_z)
from lib.kit_geo import SIDE_N, KitMesh, bake_colors, collision_box, collision_hull, export_glb
from lib.kit_parts import board

TREAD_T = 0.03
RISER_T = 0.02


def _tread_profile(y0: float, y1: float, z1: float) -> list:
    """Tread cross-section (y, z) with a rounded nosing at the front (y0)."""
    t = TREAD_T
    r = 0.009
    return [(y0 + r, z1 - t), (y1, z1 - t), (y1, z1), (y0 + r, z1), (y0 + r * 0.3, z1 - r * 0.3), (y0, z1 - r),
            (y0, z1 - t + r), (y0 + r * 0.3, z1 - t + r * 0.3)]


def build_stairs(p: dict, name: str, outputs: list[str]) -> None:
    seed = int(p.get("seed", 1))
    rng = common.rng(seed)
    km = KitMesh(name)
    xi = STAIR_W / 2 - STRINGER_T
    top_z = STAIR_RISERS * STAIR_RISE
    total = STAIR_RISERS * STAIR_RUN
    for i in range(1, STAIR_RISERS + 1):
        y_nose = (i - 1) * STAIR_RUN
        z_top = i * STAIR_RISE
        y_back = min(total, i * STAIR_RUN + STAIR_NOSING)
        km.part(rng.uniform(0.25, 0.75))
        km.prism([_tread_profile(y_nose, y_back, z_top)], -xi, xi, axis="x", mat="kit_stairs", side=(SIDE_N,) * 3,
                 grain="x", uv_off=(rng.uniform(0, 4), rng.uniform(0, 4)))
        # riser below the tread (from the previous tread top / floor)
        yr = y_nose + STAIR_NOSING
        z0 = (i - 1) * STAIR_RISE
        km.part(rng.uniform(0.3, 0.7))
        km.box((-xi, yr, z0), (xi, yr + RISER_T, z_top - TREAD_T), "kit_trim", grain="x", skip=("-x", "+x", "-z", "+z"))
    # Closed stringers (profile in the YZ plane) and the soffit.
    def zb(y):  # stringer bottom edge (parallel to the pitch line)
        return stair_nosing_z(y) + 0.06 - STRINGER_DEPTH

    yb0 = (STRINGER_DEPTH - STAIR_RISE - 0.06) / (STAIR_RISE / STAIR_RUN)
    prof = [(0.0, 0.0), (max(0.0, yb0), 0.0), (total, zb(total)), (total, stringer_top_z(total))]
    y_cap = (top_z + 0.06 - (STAIR_RISE + 0.06)) / (STAIR_RISE / STAIR_RUN)
    prof += [(y_cap, stringer_top_z(y_cap)), (0.0, stringer_top_z(0.0))]
    prof = [(y, max(0.0, z)) for y, z in prof]
    for x0, x1 in ((-STAIR_W / 2, -xi), (xi, STAIR_W / 2)):
        km.part(rng.uniform(0.3, 0.7))
        km.prism([prof], x0, x1, axis="x", mat="kit_trim", side=(SIDE_N,) * 3, grain="y")
    km.part(0.5)
    zb_end = prof[2][1]
    km.quad([(xi, max(0.0, yb0), 0.0), (-xi, max(0.0, yb0), 0.0), (-xi, total, zb_end), (xi, total, zb_end)],
            "kit_trim", grain="y")
    obj = km.build()
    bake_colors(obj, ground_z=0.0, samples=16, distance=0.35, strength=0.8, seed=seed)
    mid = STAIR_RISE / 2
    y_flat = (top_z - mid) / (STAIR_RISE / STAIR_RUN)
    pts = []
    for x in (-STAIR_W / 2, STAIR_W / 2):
        pts += [(x, 0.0, 0.0), (x, 0.0, mid), (x, y_flat, top_z), (x, total, top_z), (x, total, 0.0)]
    export_glb(outputs[0], [obj, collision_hull(f"{name}_col0", pts)])


def _baluster(km: KitMesh, x: float, y: float, z0: float, z1: float, s: float = 0.032) -> None:
    km.box((x - s / 2, y - s / 2, z0), (x + s / 2, y + s / 2, z1), "kit_trim", grain="z", skip=("-z", "+z"))


def _newel(km: KitMesh, y: float, z0: float, z1: float, rng) -> None:
    km.part(rng.uniform(0.3, 0.7))
    s = 0.045
    km.box((-s, y - s, z0), (s, y + s, z1 - 0.035), "kit_stairs", grain="z", skip=("-z",))
    c = 0.058
    km.box((-c, y - c, z1 - 0.035), (c, y + c, z1 - 0.012), "kit_stairs", grain="x")
    km.box((-c + 0.012, y - c + 0.012, z1 - 0.012), (c - 0.012, y + c - 0.012, z1), "kit_stairs", grain="x", skip=("-z",))


def build_stair_railing(p: dict, name: str, outputs: list[str]) -> None:
    seed = int(p.get("seed", 1))
    rng = common.rng(seed)
    km = KitMesh(name)
    top_z = STAIR_RISERS * STAIR_RISE
    total = STAIR_RISERS * STAIR_RUN
    yb, yt = 0.045, total - 0.07

    def hz(y):  # handrail top
        return stair_nosing_z(y) + HANDRAIL_ABOVE_NOSING

    _newel(km, yb, 0.0, hz(yb) + 0.12, rng)
    _newel(km, yt, top_z - 0.3, top_z + RAILING_H + 0.08, rng)
    # Handrail (stained) between the newels.
    km.part(rng.uniform(0.3, 0.7))
    a = Vector((0.0, yb + 0.045, hz(yb + 0.045) - 0.03))
    b = Vector((0.0, yt - 0.045, hz(yt - 0.045) - 0.03))
    board(km, a, b, (1, 0, 0), 0.062, 0.052, mat="kit_stairs", rng=rng)
    # Shoe rail on the stringer and balusters (2 per tread).
    km.part(rng.uniform(0.3, 0.7))
    sa = Vector((0.0, yb + 0.045, stringer_top_z(yb + 0.045) + 0.012))
    sb = Vector((0.0, min(yt - 0.045, 3.6), stringer_top_z(min(yt - 0.045, 3.6)) + 0.012))
    board(km, sa, sb, (1, 0, 0), 0.05, 0.024, mat="kit_trim", rng=rng)
    km.part(rng.uniform(0.4, 0.6))
    for i in range(STAIR_RISERS - 1):
        for f in (0.28, 0.78):
            y = (i + f) * STAIR_RUN
            if not (yb + 0.08 < y < yt - 0.08):
                continue
            z0 = stringer_top_z(y) + 0.015
            z1 = hz(y) - 0.055
            _baluster(km, 0.0, y, z0, z1)
    obj = km.build()
    bake_colors(obj, ground_z=0.0, samples=12, distance=0.25, strength=0.6, seed=seed)
    pts = []
    for x in (-0.035, 0.035):
        pts += [(x, yb, 0.0), (x, yb, hz(yb) + 0.12), (x, yt, top_z + RAILING_H), (x, yt, top_z - 0.3)]
    export_glb(outputs[0], [obj, collision_hull(f"{name}_col0", pts)])


def build_railing(p: dict, name: str, outputs: list[str]) -> None:
    seed = int(p.get("seed", 1))
    rng = common.rng(seed)
    km = KitMesh(name)
    L = float(p.get("length", 1.0))
    km.part(rng.uniform(0.3, 0.7))
    km.box((-L / 2, -0.028, 0.0), (L / 2, 0.028, 0.035), "kit_trim", grain="x", skip=("-z",))
    km.part(rng.uniform(0.3, 0.7))
    prof = [(-0.032, RAILING_H - 0.05), (0.032, RAILING_H - 0.05), (0.032, RAILING_H - 0.012), (0.02, RAILING_H),
            (-0.02, RAILING_H), (-0.032, RAILING_H - 0.012)]
    km.prism([prof], -L / 2, L / 2, axis="x", mat="kit_stairs", side=(SIDE_N,) * 3, grain="x")
    km.part(rng.uniform(0.4, 0.6))
    n = int(round(L / 0.125))
    for k in range(n):
        x = -L / 2 + 0.0625 + k * 0.125
        _baluster(km, x, 0.0, 0.035, RAILING_H - 0.05)
    obj = km.build()
    bake_colors(obj, ground_z=0.0, samples=12, distance=0.2, strength=0.6, seed=seed)
    export_glb(outputs[0], [obj, collision_box(f"{name}_col0", (-L / 2, -0.035, 0.0), (L / 2, 0.035, RAILING_H))])


def build_ladder(p: dict, name: str, outputs: list[str]) -> None:
    seed = int(p.get("seed", 1))
    rng = common.rng(seed)
    km = KitMesh(name)
    H = float(p.get("height", 3.0))
    W = 0.5
    rt, rd = 0.035, 0.07
    y0, y1 = -0.16, -0.16 + rd
    for sx in (-1, 1):
        km.part(rng.uniform(0.3, 0.7))
        xa, xb = sorted((sx * W / 2, sx * (W / 2 - rt)))
        prof = [(y0, 0.0), (y1, 0.0), (y1, H - 0.02), (y1 - 0.02, H), (y0, H)]
        km.prism([prof], xa, xb, axis="x", mat="wood_raw", side=(SIDE_N,) * 3, grain="z",
                 uv_off=(rng.uniform(0, 3), rng.uniform(0, 3)))
        for zc in (0.22, H - 0.25):
            km.part(rng.uniform(0.3, 0.7))
            km.box((xa, y1, zc - 0.045), (xb, 0.0, zc + 0.045), "wood_raw", grain="y", skip=("+y",))
    yc = (y0 + y1) / 2
    k = 1
    while k * 0.3 < H - 0.15:
        km.part(rng.uniform(0.2, 0.8))
        z = k * 0.3
        sag = rng.uniform(-0.004, 0.004)
        fr = Matrix.Translation((-(W / 2 - rt / 2), yc, z + sag)) @ Matrix.Rotation(math.pi / 2, 4, "Y")
        km.lathe([(0.0165, 0.0), (0.0165, W - rt)], mat="wood_raw", segments=8, frame=fr, cap_bottom=False,
                 cap_top=False, axis_u=True)
        k += 1
    obj = km.build()
    bake_colors(obj, ground_z=0.0, samples=12, distance=0.25, strength=0.7, seed=seed)
    export_glb(outputs[0], [obj, collision_box(f"{name}_col0", (-W / 2, y0, 0.0), (W / 2, 0.0, H))])


def build(params: dict, outputs: list[str]) -> None:
    name = params.get("name", "stairs")
    kind = params.get("kind", "stairs")
    {"stairs": build_stairs, "stair_railing": build_stair_railing, "railing": build_railing,
     "ladder": build_ladder}[kind](params, name, outputs)
