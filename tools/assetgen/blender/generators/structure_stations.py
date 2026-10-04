"""Crafting / storage stations: workbench, storage crate (lid = separate node "lid"), forge with hand
bellows, chemistry bench. Origin bottom centre on the authored ground plane, front = -Y.
params: kind, name, seed."""
from __future__ import annotations

import math

from mathutils import Matrix, Vector, noise

from lib import common, item_kit as K, item_props as P


def _pole(mb, a, b, r0, r1, seed, *, bark="item_bark", n=5, bend=0.008, sides=10, caps=(True, True)):
    a, b = Vector(a), Vector(b)
    d = b - a
    side = d.orthogonal().normalized()
    ph = common.rng(seed).uniform(0, 6.28)
    pts = [a + d * (i / (n - 1)) + side * bend * math.sin(i / (n - 1) * math.pi + ph) for i in range(n)]
    return K.stick(mb, pts, r0, r1, sides=sides, seed=seed, bark=bark, caps=caps, lumpy=0.03)


def _nail_head(mb, at, normal=(0, 0, 1), r=0.0045):
    n = Vector(normal).normalized()
    m = Matrix.Translation(at) @ n.to_track_quat("Z", "X").to_matrix().to_4x4()
    mb.push(m)
    K.lathe(mb, [(r, 0.0), (r * 0.85, 0.0012)], segments=6, mat="item_galvanized", cap_bottom=False, cap_top=True)
    mb.pop()


def workbench(p):
    seed = int(p["seed"])
    r = common.rng(seed)
    mb = K.MB()
    top_z = 0.85
    for k, y in enumerate((-0.285, -0.095, 0.095, 0.285)):
        P.plank(mb, 1.78 + r.uniform(-0.02, 0.02), 0.186, 0.045, center=(r.uniform(-0.01, 0.01), y, top_z - 0.0225), seed=seed + k,
                warp=0.3, n=6)
        for x in (-0.76, 0.76):
            for dy in (-0.05, 0.05):
                _nail_head(mb, (x + r.uniform(-0.01, 0.01), y + dy, top_z + 0.0003))
    for k, (x, y) in enumerate(((-0.76, -0.26), (0.76, -0.26), (-0.76, 0.26), (0.76, 0.26))):
        _pole(mb, (x * 1.02, y * 1.04, -0.04), (x, y, top_z - 0.045), 0.056, 0.052, seed + 10 + k)
    for k, y in enumerate((-0.26, 0.26)):
        _pole(mb, (-0.88, y, top_z - 0.085), (0.88, y, top_z - 0.085), 0.042, 0.04, seed + 20 + k, n=6)
        _pole(mb, (-0.8, y, 0.24), (0.8, y, 0.24), 0.028, 0.026, seed + 25 + k, n=6, bark="item_bark_twig", sides=8)
        for x in (-0.76, 0.76):
            K.lashing(mb, (x - 0.05, y, 0.24), (x + 0.05, y, 0.24), 0.05, cord=0.0035, turns=4, per_turn=9, sides=4, mat="item_cordage",
                      seed=seed + k, up=Vector((0, 0, 1)))
    for k, x in enumerate((-0.76, 0.76)):
        _pole(mb, (x, -0.33, top_z - 0.125), (x, 0.33, top_z - 0.125), 0.036, 0.034, seed + 30 + k, n=5, bark="item_bark_twig")
    # lower shelf planks on the stretchers
    for k, x in enumerate((-0.42, 0.0, 0.42)):
        P.plank(mb, 0.64, 0.17, 0.024, center=(x + r.uniform(-0.03, 0.03), 0.0, 0.24 + 0.028 + 0.012), axis="Y", seed=seed + 40 + k, n=4)
    # leg vice: chop, wooden screw with tommy bar, parallel guide
    vx = -0.62
    K.box(mb, (0.13, 0.05, 0.62), (vx, -0.405, top_z - 0.31), mat="item_wood_plank", bevel=0.006)
    K.tube(mb, [Vector((vx, -0.5, 0.74)), Vector((vx, -0.3, 0.74))], 0.021, sides=10, mat="item_wood_raw", cap_mat="item_wood_end",
           cap_uv="disc")
    K.tube(mb, [Vector((vx - 0.16, -0.49, 0.74)), Vector((vx + 0.16, -0.49, 0.74))], 0.011, sides=8, mat="item_wood_handle",
           cap_mat="item_wood_end", cap_uv="disc")
    K.box(mb, (0.04, 0.2, 0.035), (vx, -0.32, 0.29), mat="item_wood_plank", bevel=0.004)
    # loose nails on the top
    for k in range(6):
        a = r.uniform(0, math.tau)
        P.nail(mb, (0.35 + r.uniform(-0.12, 0.12), -0.15 + r.uniform(-0.1, 0.1), top_z + 0.0034), (math.cos(a), math.sin(a), 0.0), 0.075,
               sides=5)
    obj = mb.build("workbench", sharp_deg=45)
    col = K.collider_box("workbench", (-0.9, -0.43, 0.0), (0.9, 0.35, top_z))
    return [obj], {"colliders": [col]}


def storage_crate(p):
    seed = int(p["seed"])
    mb = K.MB()
    W, D, H = 1.0, 0.7, 0.63
    t = 0.021
    for (x, y) in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        K.box(mb, (0.045, 0.045, H - 0.02), (x * (W / 2 - t - 0.023), y * (D / 2 - t - 0.023), (H - 0.02) / 2 + 0.01),
              mat="item_wood_raw", bevel=0.003)
    hs = (H - 0.015) / 4
    for k in range(4):
        z = 0.01 + hs * (k + 0.5)
        for sgn in (-1, 1):
            P.plank(mb, W, hs - 0.006, t, center=(0, sgn * (D / 2 - t / 2), z), axis="X", seed=seed + k * 4 + (sgn > 0), n=3,
                    on_edge=True)
            P.plank(mb, D - 2 * t, hs - 0.006, t, center=(sgn * (W / 2 - t / 2), 0, z), axis="Y", seed=seed + 40 + k * 4 + (sgn > 0), n=3,
                    on_edge=True)
            for dz in (-0.035, 0.035):
                _nail_head(mb, (W / 2 * 0.955 * -1 + 0.0, sgn * (D / 2 + 0.0002), z + dz), (0, sgn, 0))
                _nail_head(mb, (W / 2 * 0.955, sgn * (D / 2 + 0.0002), z + dz), (0, sgn, 0))
    # floor boards
    for k in range(5):
        y = -D / 2 + t + (D - 2 * t) * (k + 0.5) / 5
        P.plank(mb, W - 2 * t, (D - 2 * t) / 5 - 0.004, 0.018, center=(0, y, 0.012), axis="X", seed=seed + 80 + k, n=3)
    # rope handles on the ends
    for sgn in (-1, 1):
        loop = K.bezier((sgn * (W / 2 + 0.002), -0.09, 0.47), (sgn * (W / 2 + 0.05), -0.08, 0.40), (sgn * (W / 2 + 0.05), 0.08, 0.40),
                        (sgn * (W / 2 + 0.002), 0.09, 0.47), 10)
        K.tube(mb, loop, 0.0075, sides=6, mat="item_rope", u_tile=1.0, v_scale=1.0 / (2 * math.pi * 0.0075) / 3)
    body = mb.build("storage_crate", sharp_deg=45)
    lm = K.MB()
    for k in range(5):
        y = -D / 2 + (D / 5) * (k + 0.5)
        P.plank(lm, W + 0.02, D / 5 - 0.005, 0.022, center=(0, y, H + 0.011), axis="X", seed=seed + 100 + k, n=3)
        for x in (-0.38, 0.38):
            _nail_head(lm, (x, y, H + 0.0222))
    for x in (-0.38, 0.38):
        P.plank(lm, D - 0.08, 0.07, 0.022, center=(x, 0, H - 0.011), axis="Y", seed=seed + 120, n=3, on_edge=False)
    lid = lm.build("lid", sharp_deg=45)
    col = K.collider_box("storage_crate", (-W / 2, -D / 2, 0), (W / 2, D / 2, H + 0.02))
    return [body], {"colliders": [col], "separate": [lid], "pivot_bottom": ("lid",)}


def _stone_block(mb, center, size, seed, mat="item_stone"):
    r = common.rng(seed)
    f0 = len(mb.faces)
    v0 = len(mb.co)
    size = (size[0] * r.uniform(0.82, 1.0), size[1] * r.uniform(0.85, 1.05), size[2] * r.uniform(0.8, 1.0))
    center = (center[0] + r.uniform(-0.015, 0.015), center[1], center[2] + r.uniform(-0.012, 0.012))
    K.box(mb, size, center, mat=mat, bevel=min(size) * 0.3)
    noise.seed_set(seed % 9999)
    for i in range(v0, len(mb.co)):
        q = mb.co[i]
        mb.co[i] = q + Vector((noise.noise(q * 7.0), noise.noise(q * 7.0 + Vector((3, 1, 7))), noise.noise(q * 7.0 + Vector((5, 8, 2))))) * min(size) * 0.28
    K.reproject_box(mb, f0, 1.0)


def forge(p):
    seed = int(p["seed"])
    r = common.rng(seed)
    mb = K.MB()
    hx0, hx1, hy, hh = -0.7, 0.3, 0.38, 0.72
    cx = (hx0 + hx1) / 2
    K.box(mb, (hx1 - hx0 - 0.06, 2 * hy - 0.06, hh), (cx, 0, hh / 2), mat="item_clay", bevel=0.02)
    rows = 3
    rh = hh / rows
    k = 0
    for row in range(rows):
        z = rh * (row + 0.5)
        off = 0.5 if row % 2 else 0.0
        for side in (-1, 1):
            n = 4
            for i in range(n):
                x = hx0 + (hx1 - hx0) * (i + 0.5 + off * 0.5) / (n + off * 0.5)
                _stone_block(mb, (x, side * (hy - 0.05), z), ((hx1 - hx0) / n - 0.025, 0.12, rh - 0.025), seed + k)
                k += 1
            for i in range(3):
                y = -hy + 2 * hy * (i + 0.5) / 3
                x = hx0 + 0.05 if side < 0 else hx1 - 0.05
                _stone_block(mb, (x, y, z), (0.12, 2 * hy / 3 - 0.03, rh - 0.025), seed + k)
                k += 1
    # clay top slab + firepot with charcoal
    K.box(mb, (hx1 - hx0 + 0.04, 2 * hy + 0.04, 0.06), (cx, 0, hh + 0.02), mat="item_clay", bevel=0.015)
    mb.push(Matrix.Translation((cx - 0.05, 0.0, hh + 0.05)))
    K.lathe(mb, [(0.27, 0.0), (0.27, 0.03), (0.24, 0.045), (0.22, 0.03), (0.2, -0.06), (0.12, -0.12), (0.04, -0.13)], segments=20,
            mat="item_clay", regions=[(3, 6, "item_wood_charred", "metric")], cap_bottom=False, cap_top=True, cap_mat_top="item_ash")
    mb.pop()
    hearth = mb.build("forge", sharp_deg=45)
    coals = []
    for i in range(14):
        a, d = r.uniform(0, 6.28), r.uniform(0.0, 0.17)
        coals.append(K.pebble(f"coal{i}", (r.uniform(0.04, 0.07), r.uniform(0.03, 0.05), r.uniform(0.025, 0.04)), seed + 200 + i,
                              mat="item_charcoal", subdiv=1, lump=0.25, center=(cx - 0.05 + math.cos(a) * d, math.sin(a) * d, hh - 0.06 + d * 0.2)))
    # stump stand + hand bellows feeding a tuyere pipe into the firepot
    bm = K.MB()
    _pole(bm, (0.55, 0.02, -0.03), (0.55, 0.02, 0.48), 0.16, 0.15, seed + 300, n=3, bend=0.0, sides=14)
    tuy = [Vector((0.36, 0.02, 0.6)), Vector((0.22, 0.02, 0.66)), Vector((cx - 0.05 + 0.2, 0.0, hh - 0.02))]
    K.tube(bm, K.polyline_resample(tuy, 8), 0.022, sides=10, mat="item_iron_strap")
    # teardrop boards: nozzle end toward the hearth (-X), hinged there, open at the wide end
    board = [(0.2, -0.14), (-0.12, -0.11), (-0.25, -0.04), (-0.27, 0.0), (-0.25, 0.04), (-0.12, 0.11), (0.2, 0.14), (0.26, 0.0)]
    bx, by = 0.67, 0.02
    tilt = math.radians(9.0)
    for z, tl in ((0.505, 0.0), (0.541, -tilt)):
        bm.push(Matrix.Translation((bx - 0.25, by, z)) @ Matrix.Rotation(tl, 4, "Y") @ Matrix.Translation((0.25, 0, 0)))
        K.extrude(bm, board, 0.022, mat="item_wood_plank", uv_scale=1.0, chamfer=0.003)
        bm.pop()
    # pleated leather bag joining the two boards (outline made CCW so the band faces outward)
    outline = K.polyline_resample([Vector((x, y, 0)) for x, y in board] + [Vector((board[0][0], board[0][1], 0))], 25)[:-1]
    area = sum(outline[i].x * outline[(i + 1) % len(outline)].y - outline[(i + 1) % len(outline)].x * outline[i].y for i in range(len(outline)))
    if area < 0:
        outline = list(reversed(outline))
    lower, mid, upper = [], [], []
    for q in outline:
        lower.append(bm.vert((bx + q.x, by + q.y, 0.517)))
        zt = 0.530 + (q.x + 0.25) * math.tan(tilt)
        upper.append(bm.vert((bx + q.x, by + q.y, zt)))
        mid.append(bm.vert((bx + q.x * 1.1, by + q.y * 1.12, (0.517 + zt) / 2)))
    n = len(outline)
    for i in range(n):
        j = (i + 1) % n
        bm.face((lower[i], lower[j], mid[j], mid[i]), None, "item_leather")
        bm.face((mid[i], mid[j], upper[j], upper[i]), None, "item_leather")
    # handles on the wide end and the nozzle into the tuyere
    for z in (0.505, 0.625):
        K.tube(bm, [Vector((0.9, -0.06, z)), Vector((0.98, -0.06, z + 0.02)), Vector((0.98, 0.1, z + 0.02)), Vector((0.9, 0.1, z))], 0.012,
               sides=6, mat="item_wood_raw")
    K.tube(bm, [Vector((0.43, 0.02, 0.523)), Vector((0.40, 0.02, 0.56)), Vector((0.36, 0.02, 0.6))], 0.014, sides=8, mat="item_iron_strap")
    bellows = bm.build("bellows", sharp_deg=50)
    col = K.collider_box("forge", (hx0, -hy - 0.02, 0.0), (0.72, hy + 0.02, hh + 0.05))
    return [hearth, bellows] + coals, {"colliders": [col]}


def chemistry_bench(p):
    seed = int(p["seed"])
    mb = K.MB()
    top = 0.8
    for k, y in enumerate((-0.2, 0.0, 0.2)):
        P.plank(mb, 1.56, 0.196, 0.034, center=(0, y, top - 0.017), seed=seed + k, warp=0.2, n=5)
    for (x, y) in ((-0.72, -0.25), (0.72, -0.25), (-0.72, 0.25), (0.72, 0.25)):
        K.box(mb, (0.06, 0.06, top - 0.034), (x, y, (top - 0.034) / 2), mat="item_wood_plank", bevel=0.004)
    for sgn in (-1, 1):
        P.plank(mb, 1.38, 0.09, 0.022, center=(0, sgn * 0.272, top - 0.08), axis="X", seed=seed + 10 + (sgn > 0), n=3)
        P.plank(mb, 0.44, 0.09, 0.022, center=(sgn * 0.742, 0, top - 0.08), axis="Y", seed=seed + 12 + (sgn > 0), n=3)
    for k, y in enumerate((-0.12, 0.12)):
        P.plank(mb, 1.38, 0.2, 0.022, center=(0, y, 0.22), seed=seed + 20 + k, n=3)
    for sgn in (-1, 1):
        K.box(mb, (1.4, 0.03, 0.03), (0, sgn * 0.24, 0.195), mat="item_wood_plank", bevel=0.003)
    # crude still: alcohol burner under a pot on a tripod, copper condenser coil into a jar
    sx = -0.5
    mb.push(Matrix.Translation((sx, 0.05, top)))
    K.lathe(mb, [(0.035, 0.0), (0.038, 0.004), (0.036, 0.03), (0.012, 0.038), (0.008, 0.05)], segments=12, mat="item_brass", cap_bottom=True,
            cap_top=True, cap_mat_top="item_cloth_torch")
    for k in range(3):
        a = 2 * math.pi * k / 3
        K.tube(mb, [Vector((math.cos(a) * 0.11, math.sin(a) * 0.11, 0.0)), Vector((math.cos(a) * 0.075, math.sin(a) * 0.075, 0.115))], 0.004,
               sides=5, mat="item_iron_strap")
    ringp = [Vector((math.cos(t) * 0.075, math.sin(t) * 0.075, 0.115)) for t in [2 * math.pi * i / 14 for i in range(14)]]
    K.tube(mb, ringp, 0.004, sides=5, mat="item_iron_strap", closed=True)
    mb.push(Matrix.Translation((0, 0, 0.117)))
    K.lathe(mb, [(0.06, 0.0), (0.075, 0.01), (0.08, 0.1), (0.083, 0.104), (0.06, 0.112), (0.03, 0.118)], segments=16, mat="item_steel_dark",
            regions=[(4, 5, "item_steel_tool", "metric")], cap_bottom=True, cap_top=True)
    mb.pop()
    pipe = [Vector((0.0, 0.0, 0.235)), Vector((0.0, 0.0, 0.3)), Vector((0.12, 0.0, 0.34)), Vector((0.25, 0.0, 0.3))]
    K.tube(mb, K.polyline_resample(pipe, 10), 0.006, sides=6, mat="item_copper")
    coil = K.helix((0.32, 0.0, 0.3), (0.32, 0.0, 0.1), 0.055, 3.5, per_turn=12, phase=math.pi)
    K.tube(mb, [Vector((0.25, 0.0, 0.3))] + coil, 0.006, sides=6, mat="item_copper")
    mb.pop()
    mb.push(Matrix.Translation((sx + 0.32, 0.05, top)))
    K.lathe(mb, [(0.045, 0.0), (0.05, 0.006), (0.05, 0.08), (0.042, 0.095), (0.03, 0.1), (0.03, 0.11), (0.027, 0.112)], segments=14,
            mat="item_glass_clear", cap_bottom=True, cap_top=True, cap_mat_top="item_charcoal")
    mb.pop()
    # bottles (glass_bottle cost x4), a jar of herbs, mortar and pestle, a funnel
    mats = ["item_glass_green", "item_glass_brown", "item_glass_clear", "item_glass_green"]
    for k, (x, y, s) in enumerate(((0.12, 0.16, 1.0), (0.24, 0.12, 0.85), (0.36, 0.17, 1.05), (0.5, 0.1, 0.8))):
        mb.push(Matrix.Translation((x, y, top)) @ Matrix.Scale(s, 4))
        P.glass_bottle(mb, mat=mats[k], segments=10)
        mb.pop()
    mb.push(Matrix.Translation((0.62, -0.12, top)))
    K.lathe(mb, [(0.05, 0.0), (0.056, 0.015), (0.05, 0.05), (0.03, 0.06), (0.012, 0.055)], segments=14, mat="item_stone", cap_bottom=True,
            cap_top=True, cap_mat_top="item_herb")
    mb.pop()
    K.tube(mb, [Vector((0.6, -0.12, top + 0.04)), Vector((0.64, -0.06, top + 0.12))], [0.009, 0.012], sides=8, mat="item_wood_raw")
    mb.push(Matrix.Translation((0.05, -0.15, top + 0.035)) @ Matrix.Rotation(math.radians(80), 4, "Y"))
    K.lathe(mb, [(0.008, -0.07), (0.008, -0.01), (0.06, 0.04), (0.062, 0.045)], segments=14, mat="item_aluminium", cap_bottom=True, cap_top=False)
    K.lathe(mb, [(0.062, 0.045), (0.058, 0.044), (0.005, -0.006)], segments=14, mat="item_aluminium", cap_bottom=False, cap_top=False)
    mb.pop()
    obj = mb.build("chemistry_bench", sharp_deg=45)
    col = K.collider_box("chemistry_bench", (-0.8, -0.3, 0.0), (0.8, 0.3, top))
    return [obj], {"colliders": [col]}


BUILDERS = {"workbench": workbench, "storage_crate": storage_crate, "forge": forge, "chemistry_bench": chemistry_bench}


def build(params: dict, outputs: list[str]) -> None:
    parts, opts = BUILDERS[params["kind"]](params)
    K.publish(outputs, name=params.get("name", params["kind"]), parts=parts, seed=int(params["seed"]), settle_deg=None, keep_xy=True,
              colliders=opts.get("colliders", ()), separate=opts.get("separate", ()), pivot_bottom=opts.get("pivot_bottom", ()),
              wear_deg=35.0, ao_samples=16, drop=False)
