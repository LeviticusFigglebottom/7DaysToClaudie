"""Crafting / storage stations: workbench, storage crate (lid = separate node "lid"), forge with hand
bellows, chemistry bench. Origin bottom centre on the authored ground plane, front = -Y.
The workbench (ADR-0035) is all bushcraft: split logs, log legs and rope, built with the
building-log toolkit in structure_logs.
params: kind, name, seed."""
from __future__ import annotations

import math

from mathutils import Matrix, Vector, noise

from generators import structure_logs as L
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


def _hatchet(mb, seed: int) -> None:
    """A small hatchet in the canonical frame: handle along +X from the butt at the origin, head at
    the far end, bit toward -Z (so it can be buried in a block)."""
    r = common.rng(seed)
    L_h = 0.36
    K.tube(mb, [Vector((0.0, 0, 0)), Vector((0.12, 0, 0.004)), Vector((0.26, 0, 0.0)), Vector((L_h, 0, -0.002))],
           [0.016, 0.014, 0.013, 0.014], sides=8, mat="item_wood_handle", cap_mat="item_wood_end", cap_uv="disc", up=Vector((0, 0, 1)))
    # forged head: eye round the handle, cheeks tapering to a flared bit pointing down
    hx = L_h - 0.03
    K.box(mb, (0.05, 0.034, 0.05), (hx, 0.0, 0.012), mat="item_steel_dark", bevel=0.006)
    blade = [(hx - 0.022, -0.012), (hx + 0.022, -0.012), (hx + 0.034, -0.085), (hx - 0.036, -0.088)]
    mb.push(Matrix.Translation((0, 0.009, 0)) @ Matrix.Rotation(math.pi / 2, 4, "X"))
    K.extrude(mb, blade, 0.018, mat="item_steel_dark", uv_scale=1.0, chamfer=0.003)
    mb.pop()
    K.box(mb, (0.012, 0.016, 0.03), (hx - 0.03, 0.0, 0.012), mat="item_steel_dark", bevel=0.003)
    del r


def workbench(p):
    """Rustic bench, no sawn planks: three split logs (flat side up) for the top, laid across two
    cross bearers on four log legs; X braces and a stretcher of poles, rope lashings at every joint,
    a stump vice (a split block on the top) holding a hatchet, and a coil of cordage."""
    seed = int(p["seed"])
    r = common.rng(seed)
    mb = K.MB()
    top_z = 0.8
    tr = 0.133
    depth = 0.85
    # split-log top: half logs along X, flat faces up at top_z
    for k, y in enumerate((-0.255, 0.0, 0.255)):
        mb.push(Matrix.Translation((r.uniform(-0.03, 0.03), y + r.uniform(-0.006, 0.006), top_z)) @ Matrix.Rotation(r.uniform(-0.012, 0.012), 4, "Z"))
        L.half_log(mb, 1.74 + r.uniform(-0.04, 0.04), tr, seed + k, sides=10, steps=5, depth=depth)
        mb.pop()
        for x in (-0.66, 0.66):
            c = Vector((x + r.uniform(-0.01, 0.01), y + r.uniform(-0.02, 0.02), top_z + 0.003))
            K.tube(mb, [c - Vector((0, 0, 0.01)), c], 0.015, sides=7, mat="struct_log_end", cap_mat="struct_log_end", cap_uv="disc",
                   caps=(False, True), smooth=False)
    bz = top_z - tr * depth - 0.045
    for k, x in enumerate((-0.66, 0.66)):
        L.pole(mb, (x, -0.36, bz), (x + r.uniform(-0.01, 0.01), 0.36, bz), 0.05, 0.047, seed + 10 + k, n=5, sides=10)
    # log legs, splayed a little, notched under the bearers
    legs = []
    for k, (x, y) in enumerate(((-0.66, -0.3), (0.66, -0.3), (-0.66, 0.3), (0.66, 0.3))):
        foot = Vector((x * 1.08, y * 1.0, -0.03))
        head = Vector((x, y, bz - 0.04))
        L.pole(mb, foot, head + Vector((0, 0, 0.08)), 0.058, 0.052, seed + 20 + k, n=4, sides=10)
        legs.append((foot, head))
        L.cross_lash(mb, (x, y, bz), (0, 0, 1), (0, 1, 0), 0.065, seed + 30 + k, cord=0.0055)
    # X braces on each end, a stretcher pole along the middle
    for k, x in enumerate((-0.66, 0.66)):
        lo, hi = 0.16, bz - 0.12
        for j, sgn in enumerate((1, -1)):
            a = Vector((x * 1.05 + 0.055 * (1 if x > 0 else -1), -0.33 * sgn, lo))
            b = Vector((x + 0.055 * (1 if x > 0 else -1), 0.3 * sgn, hi))
            L.pole(mb, a, b, 0.024, 0.021, seed + 40 + k * 2 + j, n=4, sides=7)
        L.bind(mb, (x * 1.03 + 0.06 * (1 if x > 0 else -1), 0.0, (lo + hi) / 2), (0, 0, 1), 0.035, seed + 44 + k, turns=3, cord=0.004,
               width=0.04, mat="item_cordage")
    L.pole(mb, (-0.75, 0.0, 0.3), (0.75, 0.0, 0.31), 0.032, 0.03, seed + 50, n=6, sides=8)
    for k, x in enumerate((-0.7, 0.7)):
        L.bind(mb, (x, 0.0, 0.3), (1, 0, 0), 0.034, seed + 52 + k, turns=3, cord=0.004, width=0.05, mat="item_cordage")
    # stump vice: a short round block, split across its top, with the hatchet's bit driven into it
    vx, vy = -0.5, -0.05
    bh = 0.09
    mb.push(Matrix.Translation((vx, vy, top_z)))
    L.pole(mb, (0, 0, 0.0), (0, 0, bh), 0.115, 0.11, seed + 60, n=2, sides=12, bend=0.0, caps=(False, False))
    K.lathe(mb, [(0.11, bh), (0.0, bh)], segments=12, mat="struct_log_end", cap_bottom=False, cap_top=False, cap_uv="disc")
    K.box(mb, (0.006, 0.2, 0.06), (0.0, 0.0, bh - 0.025), mat="item_wood_charred", bevel=0.0)     # the split
    mb.pop()
    # butt resting on the top, head end raised onto the block with the bit buried in it
    butt_z = top_z + 0.016
    ang = math.atan2(top_z + bh + 0.02 - butt_z, 0.33)
    mb.push(Matrix.Translation((vx - 0.33, vy, butt_z)) @ Matrix.Rotation(-ang, 4, "Y"))
    _hatchet(mb, seed + 61)
    mb.pop()
    # coil of cordage
    cx, cy = 0.42, 0.06
    coil = []
    for i in range(5 * 18 + 1):
        t = i / 18
        a = 2 * math.pi * t
        rad = 0.085 + 0.004 * math.sin(a * 3.0)
        coil.append(Vector((cx + math.cos(a) * rad, cy + math.sin(a) * rad, top_z + 0.009 + 0.0075 * (t % 5) * 0.9 + 0.002 * math.sin(a * 2))))
    K.tube(mb, coil, 0.0055, sides=5, mat="item_cordage", u_tile=1.0, v_scale=1.0 / (2 * math.pi * 0.0055) / 3)
    for k in range(4):
        a = 2 * math.pi * k / 4 + 0.4
        q = Vector((cx + math.cos(a) * 0.085, cy + math.sin(a) * 0.085, top_z + 0.025))
        K.lashing(mb, q - Vector((0, 0, 0.012)), q + Vector((0, 0, 0.012)), 0.014, cord=0.003, turns=2, per_turn=6, sides=3,
                  mat="item_cordage", seed=seed + 70 + k, up=Vector((math.cos(a), math.sin(a), 0)))
    # loose end trailing off the coil
    end = coil[-1]
    K.tube(mb, [end, end + Vector((0.06, -0.04, -0.004)), end + Vector((0.14, -0.05, -0.02)), Vector((end.x + 0.2, end.y - 0.03, top_z + 0.006))],
           0.0055, sides=5, mat="item_cordage")
    obj = mb.build("workbench", sharp_deg=45)
    col = K.collider_box("workbench", (-0.9, -0.43, 0.0), (0.9, 0.42, top_z))
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
