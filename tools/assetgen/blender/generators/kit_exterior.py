"""POI kit exterior pieces (docs/POI_KIT.md). Grade = z 0; the ground floor of a raised house sits at 0.6.

params: kind, name, seed
  foundation:  1.0 x 0.2 x 0.6 concrete skirt under exterior walls (M_concrete), origin bottom centre,
               centred on the wall line (faces 2 cm proud of the 0.16 wall), chamfered top edges.
  porch_step:  1 x 1 cell (origin = cell bottom centre), three 0.2 risers ascending toward +Y; the top
               tread (0.6) is flush with porch_deck_1m. Painted treads/risers, sawtooth stringers.
  porch_post:  0.12 x 0.12 x 2.8 turned post (square blocks + turned shaft), origin bottom centre.
  porch_deck:  1 x 1 deck boards along X, top at 0.6 (origin = cell bottom centre at grade), joists,
               beam and a concrete pier below.
  chimney:     0.8 x 0.6 x 4.5 brick chimney with corbelled top, concrete crown and clay flue.
"""
from __future__ import annotations



from lib import common
from lib.kit_dims import CHIMNEY, FOUNDATION, PORCH_H, PORCH_POST
from lib.kit_geo import SIDE_N, KitMesh, bake_colors, collision_box, export_glb


def build_foundation(p: dict, name: str, outputs: list[str]) -> None:
    L, T, H = FOUNDATION
    km = KitMesh(name)
    km.part(0.5)
    c = 0.015
    prof = [(-T / 2, 0.0), (T / 2, 0.0), (T / 2, H - c), (T / 2 - c, H), (-T / 2 + c, H), (-T / 2, H - c)]
    km.prism([prof], -L / 2, L / 2, axis="x", mat="concrete", side=(SIDE_N, SIDE_N, "y"))
    obj = km.build()
    bake_colors(obj, ground_z=0.0, samples=12, distance=0.3, strength=0.6, seed=int(p.get("seed", 1)))
    export_glb(outputs[0], [obj, collision_box(f"{name}_col0", (-L / 2, -T / 2, 0.0), (L / 2, T / 2, H))])


def build_porch_step(p: dict, name: str, outputs: list[str]) -> None:
    seed = int(p.get("seed", 1))
    rng = common.rng(seed)
    km = KitMesh(name)
    S = 0.5
    rise = PORCH_H / 3
    run = 1.0 / 3
    tt = 0.032  # tread boards
    # sawtooth stringers (profile in YZ), three of them
    prof = [(-S + 0.02, 0.0), (S, 0.0), (S, PORCH_H - tt)]
    for k in (3, 2, 1):
        y_front = -S + (k - 1) * run
        prof += [(y_front + 0.0, k * rise - tt), (y_front, (k - 1) * rise - tt if k > 1 else 0.06)]
    prof = [(y, max(0.0, z)) for y, z in prof]
    for x in (-0.46, 0.0, 0.46):
        km.part(rng.uniform(0.3, 0.7))
        km.prism([prof], x - 0.02, x + 0.02, axis="x", mat="wood_raw", side=(SIDE_N,) * 3, grain="y")
    for k in (1, 2, 3):
        y0 = -S + (k - 1) * run
        z = k * rise
        # risers (painted) and two tread boards with a small nosing
        km.part(rng.uniform(0.3, 0.7))
        km.box((-0.5, y0 + 0.02, (k - 1) * rise), (0.5, y0 + 0.04, z - tt), "wood_painted", grain="x", skip=("-z", "+z"))
        for b in range(2):
            km.part(rng.uniform(0.3, 0.7))
            ya = y0 - 0.015 + b * (run / 2 + 0.008)
            yb = ya + run / 2 + 0.004 if b == 0 else min(S, y0 + run)
            km.box((-0.5, ya, z - tt), (0.5, yb - 0.004, z), "wood_painted", grain="x",
                   uv_off=(rng.uniform(0, 3), rng.uniform(0, 3)))
    obj = km.build()
    bake_colors(obj, ground_z=0.0, samples=12, distance=0.3, strength=0.75, seed=seed)
    cols = [collision_box(f"{name}_col{k}", (-0.5, -S + (k - 1) * run, 0.0), (0.5, S, k * rise)) for k in (1, 2, 3)]
    export_glb(outputs[0], [obj] + cols)


def build_porch_post(p: dict, name: str, outputs: list[str]) -> None:
    seed = int(p.get("seed", 1))
    km = KitMesh(name)
    w, _, H = PORCH_POST
    r = w / 2
    km.part(0.5)
    # square base block with a chamfered top, square top block, turned shaft between
    km.lathe([(r, 0.0), (r, 0.52), (r * 0.82, 0.56)], mat="wood_painted", square=True, cap_bottom=False, cap_top=True)
    turn = [(r * 0.8, 0.56), (r * 0.92, 0.6), (r * 0.92, 0.645), (r * 0.76, 0.685), (r * 0.7, 0.8), (r * 0.76, 1.1),
            (r * 0.8, 1.5), (r * 0.75, 1.88), (r * 0.69, 2.03), (r * 0.76, 2.08), (r * 0.92, 2.14), (r * 0.92, 2.18),
            (r * 0.8, 2.22)]
    km.lathe(turn, mat="wood_painted", segments=12, cap_bottom=False, cap_top=False, axis_u=True)
    km.lathe([(r * 0.82, 2.22), (r, 2.26), (r, H - 0.06), (r * 1.18, H - 0.05), (r * 1.18, H)], mat="wood_painted",
             square=True, cap_bottom=True)
    obj = km.build()
    bake_colors(obj, ground_z=0.0, samples=12, distance=0.25, strength=0.6, seed=seed)
    export_glb(outputs[0], [obj, collision_box(f"{name}_col0", (-r, -r, 0.0), (r, r, H))])


def build_porch_deck(p: dict, name: str, outputs: list[str]) -> None:
    seed = int(p.get("seed", 1))
    rng = common.rng(seed)
    km = KitMesh(name)
    S = 0.5
    top = PORCH_H
    bt = 0.025
    n = 7
    pitch = 1.0 / n
    for i in range(n):
        km.part(rng.uniform(0.2, 0.8))
        y0 = -S + i * pitch + 0.003
        y1 = y0 + pitch - 0.006
        dz = rng.uniform(-0.002, 0.0015)
        km.box((-S, y0, top - bt + dz), (S, y1, top + dz), "wood_painted", grain="x",
               uv_off=(rng.uniform(0, 4), rng.uniform(0, 4)))
    jz1 = top - bt
    jz0 = jz1 - 0.18
    for x in (-0.25, 0.25):
        km.part(rng.uniform(0.3, 0.7))
        km.box((x - 0.022, -S, jz0), (x + 0.022, S, jz1), "wood_raw", grain="y", skip=("+z",))
    km.part(rng.uniform(0.3, 0.7))
    bz1 = jz0
    bz0 = bz1 - 0.18
    km.box((-S, -0.045, bz0), (S, 0.045, bz1), "wood_raw", grain="x", skip=("+z",))
    km.part(0.5)
    km.box((-0.12, -0.12, 0.0), (0.12, 0.12, bz0), "concrete", skip=("-z", "+z"))
    obj = km.build()
    bake_colors(obj, ground_z=0.0, samples=12, distance=0.3, strength=0.8, seed=seed)
    export_glb(outputs[0], [obj, collision_box(f"{name}_col0", (-S, -S, 0.0), (S, S, top))])


def build_chimney(p: dict, name: str, outputs: list[str]) -> None:
    seed = int(p.get("seed", 1))
    km = KitMesh(name)
    X, Y, H = CHIMNEY
    hx, hy = X / 2, Y / 2
    course = 1.0 / 15
    z_corbel = 60 * course   # 4.0
    km.part(0.5)
    km.box((-hx, -hy, 0.0), (hx, hy, z_corbel), "brick", skip=("+z",))
    # corbelled courses
    z = z_corbel
    for k, o in enumerate((0.025, 0.05, 0.05, 0.05)):
        z1 = z + course if k < 3 else 4.3
        km.box((-hx - o, -hy - o, z), (hx + o, hy + o, z1), "brick", skip=("-z",) if k >= 2 else ())
        z = z1
    # concrete crown with a wash (sloped top), clay flue liner
    c = 0.06
    crown_t = 0.05
    pts = [(-hx - c, -hy - c, z), (hx + c, -hy - c, z), (hx + c, hy + c, z), (-hx - c, hy + c, z),
           (-hx - c, -hy - c, z + 0.03), (hx + c, -hy - c, z + 0.03), (hx + c, hy + c, z + 0.03), (-hx - c, hy + c, z + 0.03),
           (-0.15, -0.15, z + crown_t + 0.03), (0.15, -0.15, z + crown_t + 0.03), (0.15, 0.15, z + crown_t + 0.03),
           (-0.15, 0.15, z + crown_t + 0.03)]
    polys = [([0, 3, 2, 1], "concrete", SIDE_N, False), ([0, 1, 5, 4], "concrete", SIDE_N, False),
             ([1, 2, 6, 5], "concrete", SIDE_N, False), ([2, 3, 7, 6], "concrete", SIDE_N, False),
             ([3, 0, 4, 7], "concrete", SIDE_N, False), ([4, 5, 9, 8], "concrete", SIDE_N, False),
             ([5, 6, 10, 9], "concrete", SIDE_N, False), ([6, 7, 11, 10], "concrete", SIDE_N, False),
             ([7, 4, 8, 11], "concrete", SIDE_N, False)]
    km.part(0.5)
    km.emit(pts, polys)
    zf = z + crown_t + 0.03
    fo, fi = 0.11, 0.085
    km.part(0.6)
    outer = [(-fo, -fo), (fo, -fo), (fo, fo), (-fo, fo)]
    inner = [(-fi, -fi), (fi, -fi), (fi, fi), (-fi, fi)]
    km.prism([outer, inner], zf - 0.02, H, axis="z", mat="brick", side=(SIDE_N,) * 3, caps=(False, True))
    km.box((-fi, -fi, H - 0.12), (fi, fi, H - 0.1), "concrete", skip=("-z", "-x", "+x", "-y", "+y"))
    obj = km.build()
    bake_colors(obj, ground_z=0.0, samples=12, distance=0.4, strength=0.6, seed=seed)
    export_glb(outputs[0], [obj, collision_box(f"{name}_col0", (-hx, -hy, 0.0), (hx, hy, H))])


def build(params: dict, outputs: list[str]) -> None:
    name = params.get("name", "exterior")
    kind = params["kind"]
    {"foundation": build_foundation, "porch_step": build_porch_step, "porch_post": build_porch_post,
     "porch_deck": build_porch_deck, "chimney": build_chimney}[kind](params, name, outputs)
