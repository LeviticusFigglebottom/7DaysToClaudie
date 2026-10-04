"""POI kit floors (docs/POI_KIT.md): 1 x 1 slab (origin = top centre, down to -0.2), broken slab with
a passable jagged hole, rotten sagging slab, Voronoi fracture set and a floor/ceiling hatch whose lid
is a separate node ("hatch_lid", origin on the hinge axis, rotate about local X).

params: kind ("floor" | "broken" | "rotten" | "frac" | "hatch"), name, seed, pieces (frac)
Side tagging (UVSide u): top face 0 (floor finish), bottom face 1 (ceiling finish), sides 0.5.
"""
from __future__ import annotations

import math

import bpy
from mathutils import Vector

from lib import common, fracture
from lib import kit_poly as P
from lib.kit_dims import LATH_T, LATH_W, SLAB_T
from lib.kit_geo import (SIDE_A, SIDE_B, SIDE_N, KitMesh, bake_colors, collision_box, collision_mesh, export_glb,
                         fix_chunks)
from lib.kit_parts import board, nail, sliver

S = 0.5            # half tile
TOP_T = 0.025      # finish + subfloor boards
CEIL_T = 0.02      # ceiling plaster
JOIST_W = 0.045


def _slab_sides():
    return {"+z": SIDE_A, "-z": SIDE_B, "-x": SIDE_N, "+x": SIDE_N, "-y": SIDE_N, "+y": SIDE_N}


def build_floor(p: dict, name: str, outputs: list[str]) -> None:
    km = KitMesh(name)
    km.part(0.0)
    km.box((-S, -S, -SLAB_T), (S, S, 0.0), "kit_floor", sides=_slab_sides())
    obj = km.build()
    bake_colors(obj, ground_z=None, samples=8)
    export_glb(outputs[0], [obj, collision_box(f"{name}_col0", (-S, -S, -SLAB_T), (S, S, 0.0))])


def _boundary_filter(a, b) -> bool:
    if abs(a[0] - b[0]) < 1e-6 and abs(abs(a[0]) - S) < 1e-6:
        return False
    if abs(a[1] - b[1]) < 1e-6 and abs(abs(a[1]) - S) < 1e-6:
        return False
    return True


def _perimeter(km: KitMesh, inner_mat: str = "wood_raw") -> None:
    """Outer side faces (like floor_1m) + inward-facing blocking faces closing the cavity."""
    km.part(0.0)
    z0, z1 = -SLAB_T, 0.0
    c = [(-S, -S), (S, -S), (S, S), (-S, S)]
    for i in range(4):
        (ax, ay), (bx, by) = c[i], c[(i + 1) % 4]
        km.quad([(ax, ay, z0), (bx, by, z0), (bx, by, z1), (ax, ay, z1)], "kit_floor", side=SIDE_N)
    km.part(0.4)
    zi0, zi1 = -SLAB_T + CEIL_T, -TOP_T
    t = S - 0.038   # rim joists / blocking are 3.8 cm thick
    ci = [(-t, -t), (t, -t), (t, t), (-t, t)]
    for i in range(4):
        (ax, ay), (bx, by) = ci[i], ci[(i + 1) % 4]
        km.quad([(bx, by, zi0), (ax, ay, zi0), (ax, ay, zi1), (bx, by, zi1)], inner_mat, side=SIDE_N,
                grain="x" if ay == by else "y")


def _board_hole(rng, cx: float, cy: float, rx: float, ry: float, bw: float = 0.09):
    """Hole in a floor of boards running along X: every board row breaks at its own length, with
    splintered (toothed) ends, giving a stepped outline. Returns (CCW polygon, [(x, y, dir, width)] ends)."""
    rows = []
    y = -S
    while y < S - 1e-6:
        y0, y1 = y, min(S, y + bw)
        yc = (y0 + y1) / 2
        f = 1 - ((yc - cy) / ry) ** 2
        if f > 0.05 and y0 > -S + 0.04 and y1 < S - 0.04:
            hl = rx * math.sqrt(f) * rng.uniform(0.8, 1.12)
            sh = rng.uniform(-0.05, 0.05)
            xl = max(-S + 0.06, cx + sh - hl)
            xr = min(S - 0.06, cx + sh + hl)
            if xr - xl > 0.08:
                rows.append((y0, y1, xl, xr))
        y += bw
    left, right, ends = [], [], []
    for y0, y1, xl, xr in rows:
        e = 0.003
        left += [(xl + rng.uniform(-0.015, 0.015), y0 + e), (xl + rng.uniform(0.0, 0.04), (y0 + y1) / 2 + rng.uniform(-0.02, 0.02)),
                 (xl + rng.uniform(-0.015, 0.015), y1 - e)]
        right += [(xr + rng.uniform(-0.015, 0.015), y0 + e), (xr - rng.uniform(0.0, 0.04), (y0 + y1) / 2 + rng.uniform(-0.02, 0.02)),
                  (xr + rng.uniform(-0.015, 0.015), y1 - e)]
        ends.append((xl, (y0 + y1) / 2, 1.0, y1 - y0))
        ends.append((xr, (y0 + y1) / 2, -1.0, y1 - y0))
    poly = list(reversed(left)) + right
    return P.ccw(poly), ends


def build_broken(p: dict, name: str, outputs: list[str]) -> None:
    seed = int(p.get("seed", 1))
    rng = common.rng(seed)
    km = KitMesh(name)
    rect = [(-S, -S), (S, -S), (S, S), (-S, S)]
    cx, cy = rng.uniform(-0.04, 0.04), rng.uniform(-0.04, 0.04)
    top_hole, row_ends = _board_hole(rng, cx, cy, 0.38, 0.37)
    ceil_hole = P.star(cx + rng.uniform(-0.03, 0.03), cy + rng.uniform(-0.03, 0.03), 0.42, 0.41, 15, rng, rough=0.14,
                       teeth=0.2)
    top_hole = [(max(-0.45, min(0.45, x)), max(-0.45, min(0.45, y))) for x, y in top_hole]
    ceil_hole = [(max(-0.46, min(0.46, x)), max(-0.46, min(0.46, y))) for x, y in ceil_hole]
    # Floor boards / subfloor layer (finish on top) and ceiling plaster layer.
    km.part(0.0)
    km.prism([rect, top_hole], -TOP_T, 0.0, axis="z", mat="wood_raw", mat_back="kit_floor", mat_rim="wood_raw",
             side=(SIDE_N, SIDE_A, SIDE_N), rim_filter=_boundary_filter, grain="x")
    km.part(0.0)
    km.prism([rect, ceil_hole], -SLAB_T, -SLAB_T + CEIL_T, axis="z", mat="kit_floor", mat_back="kit_wall_inner",
             mat_rim="kit_wall_inner", side=(SIDE_B, SIDE_N, SIDE_N), rim_filter=_boundary_filter)
    _perimeter(km)
    jz0, jz1 = -SLAB_T + CEIL_T, -TOP_T
    # Joists run along X; the ones crossing the hole are snapped and sag into it.
    for jy in (-0.2 + rng.uniform(-0.03, 0.03), 0.2 + rng.uniform(-0.03, 0.03)):
        xs = P.x_span_at(ceil_hole, jy)
        zc = (jz0 + jz1) / 2
        dz = jz1 - jz0
        if len(xs) < 2:
            km.part(rng.uniform(0.3, 0.7))
            km.box((-S + 0.038, jy - JOIST_W / 2, jz0), (S - 0.038, jy + JOIST_W / 2, jz1), "wood_raw", grain="x",
                   skip=("-x", "+x"))
            continue
        for side_x, edge in ((-1, xs[0]), (1, xs[-1])):
            km.part(rng.uniform(0.3, 0.7))
            # intact part under the floor, then a bent broken piece hanging into the hole
            e = edge - side_x * 0.02
            a = Vector((side_x * (S - 0.038), jy, zc))
            b = Vector((e, jy, zc))
            board(km, a, b, (0, 1, 0), JOIST_W, dz, mat="wood_raw", rng=rng)
            out = rng.uniform(0.08, 0.2)
            ang = rng.uniform(0.25, 0.6)
            tip = b + Vector((-side_x * math.cos(ang) * out, rng.uniform(-0.02, 0.02), -math.sin(ang) * out))
            km.part(rng.uniform(0.3, 0.7))
            board(km, b, tip, (0, 1, 0), JOIST_W, dz * 0.92, mat="wood_raw", rng=rng, end1=rng.uniform(0.04, 0.09),
                  teeth=2)
            sliver(km, tip + Vector((0, 0, 0.02)), (-side_x * 0.5, rng.uniform(-0.3, 0.3), -1.0), rng.uniform(0.05, 0.12),
                   0.01, rng, mat="wood_raw")
    # Broken board ends bending down into the hole (boards run along X).
    for (ex, ey, d, bw) in row_ends:
        if rng.random() > 0.45:
            continue
        dv = Vector((d, 0.0, 0.0))
        start = Vector((ex, ey, -TOP_T / 2)) - dv * 0.03
        out = rng.uniform(0.04, 0.15)
        dip = rng.uniform(0.15, 0.55)
        tip = start + (dv * math.cos(dip) - Vector((0, 0, math.sin(dip)))) * (out + 0.03)
        km.part(rng.uniform(0.2, 0.8))
        board(km, start, tip, (0, 1, 0), bw * rng.uniform(0.55, 0.95), TOP_T * 0.85, mat="wood_raw", rng=rng,
              end1=rng.uniform(0.03, 0.07), teeth=1)
    # Ceiling lath hanging from the plaster edge.
    for k in range(4):
        a = math.tau * (k + rng.uniform(0.1, 0.9)) / 4
        r = P.ray_hit(ceil_hole, (cx, cy), a)
        ex, ey = cx + math.cos(a) * r, cy + math.sin(a) * r
        d = Vector((-math.cos(a), -math.sin(a), 0.0))
        start = Vector((ex, ey, -SLAB_T + CEIL_T + LATH_T / 2)) - d * 0.03
        out = rng.uniform(0.08, 0.2)
        dip = rng.uniform(0.6, 1.2)
        tip = start + (d * math.cos(dip) - Vector((0, 0, math.sin(dip)))) * out
        km.part(rng.uniform(0.2, 0.8))
        board(km, start, tip, Vector((-d.y, d.x, 0)), LATH_W, LATH_T, mat="wood_raw", rng=rng,
              end1=rng.uniform(0.01, 0.03), teeth=0)
    obj = km.build()
    bake_colors(obj, ground_z=None, samples=16, distance=0.3, strength=0.85, seed=seed)

    def col(k: KitMesh) -> None:
        k.prism([rect, top_hole], -SLAB_T, 0.0, axis="z", mat="collision")

    export_glb(outputs[0], [obj, collision_mesh(f"{name}_col0", col)])


def build_rotten(p: dict, name: str, outputs: list[str]) -> None:
    """Water-rotted floor: the walking surface sags (grid surface, finish projected by the shader), one
    board has rotted through (slot showing the joist and cavity), plus fungus-soft broken ends."""
    seed = int(p.get("seed", 1))
    rng = common.rng(seed)
    km = KitMesh(name)
    n = 10
    sag = rng.uniform(0.035, 0.055)
    sx, sy = rng.uniform(-0.15, 0.15), rng.uniform(-0.15, 0.15)

    def zf(x, y):
        fx = max(0.0, 1 - ((x - sx * (1 - (2 * x) ** 2)) / S) ** 2)
        fy = max(0.0, 1 - ((y - sy * (1 - (2 * y) ** 2)) / S) ** 2)
        return -sag * (fx * fy) ** 0.8
    # rotted slot: cells (i, j) removed along one board row (boards along X, 0.1 wide)
    row = rng.randint(3, 6)
    c0 = rng.randint(2, 4)
    c1 = c0 + rng.randint(2, 3)
    holes = {(i, row) for i in range(c0, c1)}
    step = 2 * S / n
    pts = []
    for j in range(n + 1):
        for i in range(n + 1):
            x, y = -S + i * step, -S + j * step
            pts.append((x, y, zf(x, y)))
    polys = []
    for j in range(n):
        for i in range(n):
            if (i, j) in holes:
                continue
            a = j * (n + 1) + i
            polys.append(([a, a + 1, a + n + 2, a + n + 1], "kit_floor", SIDE_A, True))
    km.part(0.0)
    km.emit(pts, polys)
    # slot rims (board edges) down through the boards
    km.part(0.5)
    x0, x1 = -S + c0 * step, -S + c1 * step
    y0, y1 = -S + row * step, -S + (row + 1) * step
    rim = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    for k in range(4):
        (ax, ay), (bx, by) = rim[k], rim[(k + 1) % 4]
        km.quad([(bx, by, zf(bx, by) - TOP_T), (ax, ay, zf(ax, ay) - TOP_T), (ax, ay, zf(ax, ay)),
                 (bx, by, zf(bx, by))], "wood_raw", side=SIDE_N, grain="x")
    # broken soft board ends at the slot ends
    for xe, d in ((x0, 1), (x1, -1)):
        km.part(rng.uniform(0.3, 0.7))
        a = Vector((xe - d * 0.03, (y0 + y1) / 2, zf(xe, (y0 + y1) / 2) - TOP_T / 2))
        b = Vector((xe + d * rng.uniform(0.03, 0.07), (y0 + y1) / 2, a.z - rng.uniform(0.01, 0.04)))
        board(km, a, b, (0, 1, 0), step * 0.92, TOP_T * 0.8, mat="wood_raw", rng=rng, end1=0.03, teeth=2)
    # under the boards: cavity bottom (ceiling plaster back) and a joist under the slot
    km.part(0.3)
    km.box((-S, -S, -SLAB_T), (S, S, -SLAB_T + CEIL_T), "kit_floor", sides={"-z": SIDE_B, "+z": SIDE_N},
           mats={"+z": "kit_wall_inner"}, skip=("-x", "+x", "-y", "+y"))
    km.part(rng.uniform(0.3, 0.7))
    jy = (y0 + y1) / 2 + rng.choice((-1, 1)) * 0.03
    km.box((-S + 0.038, jy - JOIST_W / 2, -SLAB_T + CEIL_T), (S - 0.038, jy + JOIST_W / 2, -TOP_T - 0.01), "wood_raw",
           grain="x", skip=("-x", "+x", "-z"))
    _perimeter(km)
    obj = km.build()
    bake_colors(obj, ground_z=None, samples=12, distance=0.25, strength=0.85, seed=seed)
    def col(k: KitMesh) -> None:
        k.emit(pts, [(q, "collision", SIDE_N, False) for q, _, _, _ in polys])

    export_glb(outputs[0], [obj, collision_mesh(f"{name}_col0", col)])


def build_frac(p: dict, name: str, outputs: list[str]) -> None:
    seed = int(p.get("seed", 1))
    km = KitMesh(name + "_src")
    km.part(0.0)
    km.box((-S, -S, -SLAB_T), (S, S, 0.0), "kit_floor", sides=_slab_sides())
    src = km.build()
    chunks = fracture.fracture(src, int(p.get("pieces", 7)), seed, "wood_raw", margin=0.003, bias=(1.0, 1.0, 0.0))
    bpy.data.objects.remove(src, do_unlink=True)
    fix_chunks(chunks, "wood_raw", seed=seed, grain="x")
    export_glb(outputs[0], chunks)


def build_hatch(p: dict, name: str, outputs: list[str]) -> None:
    seed = int(p.get("seed", 1))
    rng = common.rng(seed)
    km = KitMesh(name)
    w = 0.70                 # clear opening
    lin = 0.02               # lining boards
    r = w / 2 + lin
    rect = [(-S, -S), (S, -S), (S, S), (-S, S)]
    hole = [(-r, -r), (r, -r), (r, r), (-r, r)]
    km.part(0.0)
    km.prism([rect, hole], -SLAB_T, 0.0, axis="z", mat="kit_floor", side=(SIDE_B, SIDE_A, SIDE_N))
    # Lining boards (full depth) and a ledge the lid rests on.
    km.part(rng.uniform(0.3, 0.7))
    h = w / 2
    for lo, hi, g in (((-r, -r, -SLAB_T), (r, -h, 0.0), "x"), ((-r, h, -SLAB_T), (r, r, 0.0), "x"),
                      ((-r, -h, -SLAB_T), (-h, h, 0.0), "y"), ((h, -h, -SLAB_T), (r, h, 0.0), "y")):
        km.box(lo, hi, "kit_trim", side=SIDE_N, grain=g)
    km.part(rng.uniform(0.3, 0.7))
    lz0, lz1 = -0.065, -0.045
    e = 0.022
    for lo, hi, g in (((-h, -h, lz0), (h, -h + e, lz1), "x"), ((-h, h - e, lz0), (h, h, lz1), "x"),
                      ((-h, -h + e, lz0), (-h + e, h - e, lz1), "y"), ((h - e, -h + e, lz0), (h, h - e, lz1), "y")):
        km.box(lo, hi, "kit_trim", side=SIDE_N, grain=g)
    # Ceiling-side casing (the hatch reads from the room below too).
    km.part(rng.uniform(0.3, 0.7))
    cw_, ct = 0.07, 0.015
    zc0, zc1 = -SLAB_T - ct, -SLAB_T
    for lo, hi, g in (((-h - cw_, -h - cw_, zc0), (h + cw_, -h, zc1), "x"), ((-h - cw_, h, zc0), (h + cw_, h + cw_, zc1), "x"),
                      ((-h - cw_, -h, zc0), (-h, h, zc1), "y"), ((h, -h, zc0), (h + cw_, h, zc1), "y")):
        km.box(lo, hi, "kit_trim", side=SIDE_B, grain=g, skip=("+z",))
    frame_obj = km.build()
    bake_colors(frame_obj, ground_z=None, samples=12, distance=0.25, seed=seed)
    # Lid: separate node with its origin on the hinge axis (+Y edge of the opening, floor level), built
    # directly in hinge space: x across, y from -lw (free edge) to 0 (hinge), z from -0.043 to 0.
    lk = KitMesh("hatch_lid")
    lw = w - 0.01
    hy = h - 0.004
    nb = 5
    bw = lw / nb
    for i in range(nb):
        lk.part(rng.uniform(0.2, 0.8))
        x0 = -lw / 2 + i * bw + 0.002
        lk.box((x0, -lw, -0.022), (x0 + bw - 0.004, 0.0, 0.0), "wood_raw", grain="y",
               uv_off=(rng.uniform(0, 3), rng.uniform(0, 3)))
    for by in (-lw * 0.82, -lw * 0.18):
        lk.part(rng.uniform(0.2, 0.8))
        lk.box((-lw / 2 + 0.03, by - 0.04, -0.043), (lw / 2 - 0.03, by + 0.04, -0.022), "wood_raw", grain="x")
    lk.part(0.5)
    for hx in (-lw / 2 + 0.12, lw / 2 - 0.12):
        lk.box((hx - 0.018, -0.2, 0.0), (hx + 0.018, 0.016, 0.003), "metal_steel")
        nail(lk, (hx, -0.17, 0.003), (0, 0, 1), rng, head=0.007, proud=0.002)
        nail(lk, (hx, -0.05, 0.003), (0, 0, 1), rng, head=0.007, proud=0.002)
    ring_c = Vector((0.0, -lw + 0.075, 0.003))
    lk.box((-0.022, ring_c.y - 0.008, 0.0), (0.022, ring_c.y + 0.008, 0.004), "metal_steel")
    segs = 8
    for k in range(segs):
        a0, a1 = math.tau * k / segs, math.tau * (k + 1) / segs
        p0 = ring_c + Vector((math.cos(a0) * 0.028, math.sin(a0) * 0.028 - 0.028, 0.004))
        p1 = ring_c + Vector((math.cos(a1) * 0.028, math.sin(a1) * 0.028 - 0.028, 0.004))
        board(lk, p0, p1, (0, 0, 1), 0.006, 0.006, mat="metal_steel", rng=rng, uv_jitter=False)
    lid = lk.build("hatch_lid")
    lid.location = (0.0, hy, 0.0)
    bpy.context.view_layer.update()
    bake_colors(lid, occluders=[frame_obj], ground_z=None, samples=12, distance=0.2, seed=seed)
    cols = []
    for i, (lo, hi) in enumerate((((-S, -S, -SLAB_T), (S, -r, 0.0)), ((-S, r, -SLAB_T), (S, S, 0.0)),
                                  ((-S, -r, -SLAB_T), (-r, r, 0.0)), ((r, -r, -SLAB_T), (S, r, 0.0)))):
        cols.append(collision_box(f"{name}_col{i}", lo, hi))
    lid_col = collision_box("hatch_lid_col", (-lw / 2, -lw, -0.043), (lw / 2, 0.0, 0.0))
    lid_col.parent = lid
    bpy.context.view_layer.update()
    export_glb(outputs[0], [frame_obj, lid, lid_col] + cols)


def build(params: dict, outputs: list[str]) -> None:
    name = params.get("name", "floor")
    kind = params.get("kind", "floor")
    {"floor": build_floor, "broken": build_broken, "rotten": build_rotten, "frac": build_frac,
     "hatch": build_hatch}[kind](params, name, outputs)
