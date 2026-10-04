"""Resource pickups: stick, stone, plant fibre, cordage coil, bough bundle, log, plank, cloth rag, bone,
box of nails, scrap metal, duct tape, Program scrip. Origin bottom centre, settled. params: kind, name, seed."""
from __future__ import annotations

import math

from mathutils import Matrix, Vector, noise

from lib import common, item_kit as K, item_props as P


def _cord_v(r):
    return 1.0 / (2 * math.pi * r) / 3


def broken_end(mb, ring, center, axis, length, seed, mat="item_wood_raw"):
    """Splintered end: the ring's vertices are joined to jagged spikes along the axis."""
    r = common.rng(seed)
    axis = Vector(axis).normalized()
    c = Vector(center)
    n = len(ring)
    tips = []
    for k in range(n):
        p = mb.co[ring[k]]
        q = c + (p - c) * r.uniform(0.25, 0.7) + axis * length * r.uniform(0.15, 1.0)
        tips.append(mb.vert(q))
    mid = mb.vert(c + axis * length * 0.35)
    for k in range(n):
        k2 = (k + 1) % n
        mb.face((ring[k], ring[k2], tips[k2], tips[k]), None, mat, False)
        mb.face((tips[k], tips[k2], mid), None, mat, False)


def stick(p):
    seed = int(p["seed"])
    mb = K.MB()
    pts = K.branch_path(0.72, seed, bend=0.02, n=12, axis="X", start=(-0.36, 0, 0.0))
    rings = K.stick(mb, pts, 0.0145, 0.0105, sides=9, seed=seed, caps=(True, False), lumpy=0.05)
    f0 = len(mb.faces)
    broken_end(mb, rings[-1], pts[-1], pts[-1] - pts[-2], 0.03, seed)
    K.reproject_box(mb, f0, 1.0)
    # two trimmed side-branch stubs
    for k, t in enumerate((0.3, 0.62)):
        i = int(t * (len(pts) - 1))
        base = pts[i]
        d = (Vector((0.35, 1 if k == 0 else -1, 0.6))).normalized()
        K.stick(mb, [base, base + d * 0.025, base + d * 0.04], 0.0058, 0.0048, sides=6, seed=seed + k + 3, lumpy=0.05)
    return [mb.build("stick", sharp_deg=55)], {}


def stone(p):
    seed = int(p["seed"])
    s = K.pebble("stone", (0.102, 0.08, 0.062), seed, mat="item_stone", subdiv=3, flat_bottom=0.2, lump=0.09)
    return [s], {}


def plant_fiber(p):
    seed = int(p["seed"])
    r = common.rng(seed)
    mb = K.MB()
    for k in range(6):
        a = r.uniform(-0.25, 0.25)
        d = Vector((math.cos(a), math.sin(a), 0.0))
        base = Vector((-0.15 + r.uniform(-0.02, 0.02), r.uniform(-0.025, 0.025), 0.002 + k * 0.0012))
        K.card(mb, base, d, (0, 0, 1), 0.3, r.uniform(0.035, 0.05), mat="item_plant_fiber", droop=-0.012, nu=1, nv=6,
               rect=(0.0, 0.0, 1.0, 1.0), twist=r.uniform(-0.4, 0.4))
    # a tie of twisted fibre around the middle
    K.lashing(mb, (-0.012, 0, 0.012), (0.012, 0, 0.012), 0.012, cord=0.0018, turns=3, per_turn=10, mat="item_cordage", seed=seed,
              up=Vector((0, 0, 1)))
    return [mb.build("plant_fiber", sharp_deg=None)], {"settle": None}


def cordage(p):
    seed = int(p["seed"])
    mb = K.MB()
    P.coil(mb, (0, 0, 0), 0.052, 6.0, cord=0.0029, seed=seed, mat="item_cordage", per_turn=20)
    tail = K.bezier((0.052, 0.0, 0.004), (0.08, -0.03, 0.004), (0.1, -0.05, 0.003), (0.14, -0.045, 0.003), 10)
    K.tube(mb, tail, 0.0029, sides=5, mat="item_cordage", u_tile=1.0, v_scale=_cord_v(0.0029))
    # binding wrap holding the coil together
    K.lashing(mb, (-0.052, -0.01, 0.009), (-0.052, 0.01, 0.009), 0.012, cord=0.0025, turns=4, per_turn=10, mat="item_cordage",
              seed=seed, up=Vector((0, 0, 1)))
    return [mb.build("cordage", sharp_deg=60)], {"settle": None}


def leaf_bundle(p):
    seed = int(p["seed"])
    r = common.rng(seed)
    mb = K.MB()
    stems = K.MB()
    for k in range(6):
        a = r.uniform(-0.28, 0.28)
        d = Vector((math.cos(a), math.sin(a), 0.08))
        base = Vector((-0.24, r.uniform(-0.02, 0.02), 0.02 + k * 0.006))
        K.card(mb, base + d * 0.04, d, (0, 0, 1), r.uniform(0.48, 0.56), r.uniform(0.2, 0.26), mat="item_fir_bough", droop=0.07, nu=2,
               nv=4, curl=0.18, twist=r.uniform(-0.3, 0.3))
        K.stick(stems, [base - d * 0.03, base + d * 0.06], 0.0045, 0.004, sides=5, seed=seed + k, lumpy=0.05)
    K.lashing(stems, (-0.235, 0, 0.032), (-0.205, 0, 0.032), 0.03, cord=0.0028, turns=4, per_turn=12, mat="item_cordage", seed=seed,
              up=Vector((0, 0, 1)))
    return [stems.build("stems", sharp_deg=60)], {"settle": None, "foliage": [mb.build("boughs", sharp_deg=None)]}


def log(p):
    seed = int(p["seed"])
    r = common.rng(seed)
    noise.seed_set(seed)
    mb = K.MB()
    L, R = 2.4, 0.152
    n = 18
    pts = [Vector((-L / 2 + L * i / (n - 1), 0, R)) for i in range(n)]
    for i, q in enumerate(pts):
        t = i / (n - 1)
        q.y += 0.025 * math.sin(t * 2.6 + seed) * t
        q.z += 0.012 * math.sin(t * 3.1 + 1.0)
    radii = [R * (1.0 - 0.1 * i / (n - 1)) * (1 + 0.025 * noise.noise(Vector((i * 0.7, 0.3, 0.1)))) for i in range(n)]
    rings = K.tube(mb, pts, radii, sides=16, mat="item_bark", caps=(True, False), cap_mat="item_wood_end", cap_uv="disc", rot=0.2)
    # axe-chopped far end: two cut facets meeting in a blunt ridge
    end = pts[-1]
    tip = []
    for k, vi in enumerate(rings[-1]):
        v = mb.co[vi]
        rel = v - end
        tip.append(mb.vert(end + Vector((0.11 - abs(rel.y) * 0.55 + abs(rel.z) * 0.1, rel.y * 0.22, rel.z * 0.9))))
    nk = len(rings[-1])
    f0 = len(mb.faces)
    for k in range(nk):
        k2 = (k + 1) % nk
        mb.face((rings[-1][k], rings[-1][k2], tip[k2], tip[k]), None, "item_wood_raw", False)
    mb.face(tip, None, "item_wood_raw", False)
    K.reproject_box(mb, f0, 2.0)
    # limb stubs, axe-trimmed flush-ish
    for k in range(4):
        t = r.uniform(0.2, 0.85)
        i = int(t * (n - 1))
        a = r.uniform(0.3, 2.8) * (1 if k % 2 == 0 else -1)
        base = pts[i] + Vector((0, math.cos(a) * radii[i] * 0.8, math.sin(a) * radii[i] * 0.8))
        d = Vector((0.4, math.cos(a), math.sin(a))).normalized()
        K.stick(mb, [base, base + d * 0.05], 0.022, 0.02, sides=8, seed=seed + 20 + k, bark="item_bark", end_mat="item_wood_raw",
                lumpy=0.05)
    return [mb.build("log", sharp_deg=50)], {"settle": 6.0}


def plank(p):
    seed = int(p["seed"])
    mb = K.MB()
    P.plank(mb, 1.2, 0.14, 0.025, center=(0, 0, 0.0125), seed=seed, warp=0.6)
    return [mb.build("wood_plank", sharp_deg=40)], {}


def cloth(p):
    seed = int(p["seed"])
    r = common.rng(seed)
    noise.seed_set(seed)
    mb = K.MB()
    W, D = 0.36, 0.27
    off = [r.uniform(0, 10) for _ in range(4)]

    def pos(u, v):
        # torn, ragged outline: border vertices pulled inward by jagged noise
        x = (u - 0.5) * W
        y = (v - 0.5) * D
        if u <= 0.0 or u >= 1.0:
            x -= math.copysign(1.0, u - 0.5) * W * (0.03 + 0.07 * abs(noise.noise(Vector((v * 9 + off[0], u * 3, 0.5)))) +
                                                    0.03 * (int(v * 14) % 2))
        if v <= 0.0 or v >= 1.0:
            y -= math.copysign(1.0, v - 0.5) * D * (0.03 + 0.08 * abs(noise.noise(Vector((u * 9 + off[1], v * 3, 1.5)))) +
                                                    0.03 * (int(u * 18) % 2))
        z = 0.004 + 0.012 * max(0.0, math.sin(u * 7 + off[2]) * math.sin(v * 5 + off[3])) + 0.004 * noise.noise(Vector((u * 9, v * 9, 3.0)))
        fold = max(0.0, u - 0.72)
        if fold > 0:   # one flap folded back over
            z += 0.006 + fold * 0.05 * math.sin(v * 3)
        return Vector((x, y, z))
    K.sheet(mb, 18, 14, pos, thickness=0.0015, mat_top="item_cloth_rag", uv_top=lambda u, v: (u * W, v * D),
            uv_bottom=lambda u, v: (u * W, v * D))
    return [mb.build("cloth", sharp_deg=None)], {"settle": None}


def bone(p):
    seed = int(p["seed"])
    noise.seed_set(seed)
    mb = K.MB()
    prof = [(0.004, 0.0), (0.013, 0.004), (0.018, 0.016), (0.0175, 0.03), (0.0125, 0.06), (0.0105, 0.1), (0.0098, 0.15),
            (0.0102, 0.2), (0.0118, 0.24), (0.016, 0.265), (0.0195, 0.28), (0.017, 0.292), (0.006, 0.298)]
    K.lathe(mb, prof, segments=14, mat="item_bone", cap_bottom=True, cap_top=True,
            radial_fn=lambda k, i, rr, z: 1.0 + 0.12 * noise.noise(Vector((math.cos(k * 0.45) * 2, math.sin(k * 0.45) * 2, z * 20))))
    obj = mb.build("bone_shaft", sharp_deg=70)
    head = K.pebble("bone_head", (0.032, 0.03, 0.03), seed + 1, mat="item_bone", subdiv=2, flat_bottom=0.0, lump=0.05,
                    center=(0.012, 0.0, 0.285))
    c1 = K.pebble("condyle_a", (0.024, 0.022, 0.026), seed + 2, mat="item_bone", subdiv=2, flat_bottom=0.0, lump=0.05,
                  center=(0.009, 0.0, -0.006))
    c2 = K.pebble("condyle_b", (0.024, 0.022, 0.026), seed + 3, mat="item_bone", subdiv=2, flat_bottom=0.0, lump=0.05,
                  center=(-0.009, 0.0, -0.006))
    return [obj, head, c1, c2], {"ground": Matrix.Rotation(math.radians(90), 4, "Y"), "settle": 25.0}


def nails(p):
    seed = int(p["seed"])
    r = common.rng(seed)
    mb = K.MB()
    Wd, Dp, H = 0.092, 0.056, 0.042
    # box: printed front/back, plain kraft sides/bottom; open top with four flaps folded out
    K.box(mb, (Wd, Dp, H), (0, 0, H / 2), mat="item_cardboard", bevel=0.0008)
    for side in (1, -1):
        mb.push(Matrix.Translation((0, side * (Dp / 2 + 0.0003), H / 2)) @ Matrix.Rotation(math.radians(90 * side), 4, "X"))
        K.extrude(mb, [(-Wd / 2 + 0.002, -H / 2 + 0.002), (Wd / 2 - 0.002, -H / 2 + 0.002), (Wd / 2 - 0.002, H / 2 - 0.002),
                       (-Wd / 2 + 0.002, H / 2 - 0.002)], 0.0004, mat="item_box_print", uv_rect=(0.0, 0.0, 1.0, 1.0))
        mb.pop()
    for (ax, sgn, w, ang) in (("x", 1, Dp, 120), ("x", -1, Dp, 115), ("y", 1, Wd, 110), ("y", -1, Wd, 125)):
        flap = 0.026
        if ax == "x":
            m = Matrix.Translation((sgn * Wd / 2, 0, H)) @ Matrix.Rotation(math.radians(-sgn * (180 - ang)), 4, "Y")
            outline = [(0, -w / 2), (sgn * flap, -w / 2 + 0.003), (sgn * flap, w / 2 - 0.003), (0, w / 2)]
        else:
            m = Matrix.Translation((0, sgn * Dp / 2, H)) @ Matrix.Rotation(math.radians(sgn * (180 - ang)), 4, "X")
            outline = [(-w / 2, 0), (w / 2, 0), (w / 2 - 0.003, sgn * flap), (-w / 2 + 0.003, sgn * flap)]
        mb.push(m)
        K.extrude(mb, outline, 0.0008, mat="item_cardboard", uv_scale=1.0)
        mb.pop()
    # nails heaped inside (heads up near the rim) and a few spilled on the ground
    for k in range(10):
        x, y = r.uniform(-0.035, 0.035), r.uniform(-0.019, 0.019)
        d = Vector((r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-0.25, 0.1))).normalized()
        P.nail(mb, (x - d.x * 0.03, y - d.y * 0.012, H - 0.004 + r.uniform(0, 0.006)), d, 0.064, sides=5)
    for k in range(4):
        a = r.uniform(0, math.tau)
        d = Vector((math.cos(a), math.sin(a), 0.0))
        start = Vector((0.07 + r.uniform(-0.02, 0.03), -0.045 + k * 0.022, 0.0034))
        P.nail(mb, start, d, 0.064, sides=5, bent=0.25 if k == 1 else 0.0)
    return [mb.build("nails", sharp_deg=40)], {"settle": None}


def scrap(p):
    mb = K.MB()
    # bent painted sheet offcut
    K.sheet(mb, 8, 5, lambda u, v: Vector(((u - 0.5) * 0.24, (v - 0.5) * 0.14, 0.004 + 0.05 * max(0.0, u - 0.62) ** 1.3 + 0.004 * math.sin(v * 7))),
            thickness=0.0012, mat_top="item_paint_grey", mat_bottom="item_rust", mat_edge="item_rust",
            uv_top=lambda u, v: (u * 0.24, v * 0.14), uv_bottom=lambda u, v: (u * 0.24, v * 0.14))
    # L bracket with holes
    mb.push(Matrix.Translation((-0.03, 0.07, 0.0)) @ Matrix.Rotation(0.5, 4, "Z") @ Matrix.Rotation(math.radians(90), 4, "X"))
    K.extrude(mb, [(0.0, 0.0), (0.09, 0.0), (0.09, 0.004), (0.004, 0.004), (0.004, 0.05), (0.0, 0.05)], 0.03, mat="item_rust", uv_scale=4.0)
    mb.pop()
    # flat strip and a short pipe stub
    mb.push(Matrix.Translation((0.07, -0.13, 0.0)) @ Matrix.Rotation(-0.35, 4, "Z"))
    K.box(mb, (0.16, 0.022, 0.003), (0, 0, 0.0015), mat="item_galvanized", bevel=0.0005)
    mb.pop()
    mb.push(Matrix.Translation((-0.1, -0.06, 0.0135)) @ Matrix.Rotation(0.3, 4, "Z") @ Matrix.Rotation(math.radians(90), 4, "Y") @
            Matrix.Translation((0, 0, -0.05)))
    K.lathe(mb, [(0.0105, 0.0), (0.0135, 0.0), (0.0135, 0.1), (0.0105, 0.1)], segments=14, mat="item_rust", cap_bottom=False, cap_top=False)
    K.lathe(mb, [(0.0105, 0.1), (0.0105, 0.0)], segments=14, mat="item_rust", cap_bottom=False, cap_top=False)
    mb.pop()
    return [mb.build("scrap_metal", sharp_deg=40)], {"settle": None}


def duct_tape(p):
    mb = K.MB()
    Ro, Ri, W = 0.046, 0.038, 0.048
    K.lathe(mb, [(Ri, 0.0), (Ro, 0.0), (Ro, W), (Ri, W)], segments=28, mat="item_duct_tape", cap_bottom=False, cap_top=False)
    K.lathe(mb, [(Ri, W), (Ri - 0.0035, W), (Ri - 0.0035, 0.0), (Ri, 0.0)], segments=28, mat="item_cardboard", cap_bottom=False, cap_top=False)
    # peeled loose end
    K.sheet(mb, 5, 2, lambda u, v: Vector((math.cos(-1.2 + u * 0.5) * (Ro + 0.0004 + u * u * 0.012),
                                           math.sin(-1.2 + u * 0.5) * (Ro + 0.0004 + u * u * 0.012), 0.001 + v * (W - 0.002))),
            thickness=0.0004, mat_top="item_duct_tape", uv_top=lambda u, v: (u * 0.03, v * W))
    return [mb.build("duct_tape", sharp_deg=40)], {"settle": None}


def scrip(p):
    seed = int(p["seed"])
    r = common.rng(seed)
    mb = K.MB()
    w, d, t = 0.066, 0.034, 0.0005
    for k in range(8):
        a = r.uniform(-0.12, 0.12)
        mb.push(Matrix.Translation((r.uniform(-0.003, 0.003), r.uniform(-0.002, 0.002), t * (k + 0.5) * 1.6)) @ Matrix.Rotation(a, 4, "Z"))
        K.extrude(mb, [(-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2)], t, mat="item_scrip", side_mat="item_paper",
                  uv_rect=(0.0, 0.0, 1.0, 1.0))
        mb.pop()
    # rubber band around the stack
    H = t * 8 * 1.6
    band = []
    for i in range(24):
        a = 2 * math.pi * i / 24
        c, s = math.cos(a), math.sin(a)
        band.append(Vector((0.012, math.copysign(abs(c) ** 0.2, c) * (d / 2 + 0.0012), H / 2 + math.copysign(abs(s) ** 0.2, s) * (H / 2 + 0.0012))))
    K.tube(mb, band, (0.0022, 0.0006), profile=K.rect_profile(1, 1, 0.3), mat="item_rubber", closed=True, up=Vector((1, 0, 0)))
    return [mb.build("scrip", sharp_deg=40)], {"settle": None}


BUILDERS = {
    "stick": stick, "stone": stone, "plant_fiber": plant_fiber, "cordage": cordage, "leaf_bundle": leaf_bundle, "log": log,
    "plank": plank, "cloth": cloth, "bone": bone, "nails": nails, "scrap": scrap, "duct_tape": duct_tape, "scrip": scrip,
}


def build(params: dict, outputs: list[str]) -> None:
    parts, opts = BUILDERS[params["kind"]](params)
    K.publish(outputs, name=params.get("name", params["kind"]), parts=parts, seed=int(params["seed"]),
              ground_rot=opts.get("ground"), settle_deg=opts.get("settle", 20.0), foliage=opts.get("foliage", ()))
