"""Consumables and medical items: ration bar, cans, soda, bottles, berries, mushrooms, bandage,
first-aid tin, blister pack, pill bottle, yarrow, poultice, Bloom sample vial and mycelium.
Ground pickups: origin bottom centre, settled resting pose. params: kind, name, seed (+ per kind)."""
from __future__ import annotations

import math

from mathutils import Matrix, Vector, noise

from lib import common, item_kit as K, item_props as P

LIE_X = Matrix.Rotation(math.radians(90), 4, "Y")       # +Z axis -> +X (lie a standing object on its side)


def _cord_v(r):
    return 1.0 / (2 * math.pi * r) / 3


def ration_bar(p):
    mb = K.MB()
    n = 14
    L = 0.132
    pts = [Vector((-L / 2 + L * i / (n - 1), 0, 0.0)) for i in range(n)]
    rad = []
    for i in range(n):
        t = i / (n - 1)
        e = min(t, 1 - t)
        f = common.smoothstep(0.0, 0.11, e)
        rad.append((0.0238 * (0.92 + 0.08 * f), 0.0006 + 0.0086 * f))
    prof = [(math.copysign(abs(math.cos(a)) ** 0.45, math.cos(a)), math.copysign(abs(math.sin(a)) ** 0.8, math.sin(a)))
            for a in [2 * math.pi * k / 16 for k in range(16)]]
    K.tube(mb, pts, rad, profile=prof, mat="item_foil_ration", up=Vector((0, 1, 0)), caps=(True, True))
    # serrated crimp edges at both ends
    for side in (1, -1):
        x_in = side * (L / 2 - 0.004)
        zig = [(side * (L / 2 + (0.0035 if k % 2 == 0 else 0.0)), -0.025 + 0.05 * k / 12) for k in range(13)]
        K.extrude(mb, [(x_in, -0.025)] + zig + [(x_in, 0.025)], 0.0009, mat="item_foil_ration", uv_scale=8.0)
    # two cream stencil stripes around the middle
    for x0 in (-0.006, 0.004):
        band = [Vector((x0, 0, 0)), Vector((x0 + 0.0045, 0, 0))]
        K.tube(mb, band, (0.0238 * 1.012, 0.0092 * 1.04), profile=prof, mat="item_paint_stripe", up=Vector((0, 1, 0)), caps=(False, False))
    obj = mb.build("ration_bar", sharp_deg=55)
    return [obj], {}


def can_item(p):
    seed = int(p["seed"])
    d, h = p["size"]
    mb = K.MB()
    P.can(mb, d / 2, h, label=p.get("label"), seed=seed, dent=float(p.get("dent", 0.0)), state="sealed")
    return [mb.build(p["name"], sharp_deg=50)], {}


def can_open(p):
    seed = int(p["seed"])
    d, h = p["size"]
    R = d / 2
    mb = K.MB()
    contents = p.get("contents")
    P.can(mb, R, h, label=p.get("label"), seed=seed, state="open_full" if contents else "open", dent=0.25)
    # the cut lid, still hinged on the far rim and bent back
    hinge = Matrix.Translation((0, R * 0.92, h - 0.002)) @ Matrix.Rotation(math.radians(-112 if contents else -128), 4, "X") @ \
        Matrix.Translation((0, -R * 0.93, 0))
    mb.push(hinge)
    P.jagged_disc(mb, R * 0.93, 0.0004, segments=22, jag=0.04, seed=seed, uv_scale=10.0)
    mb.pop()
    if contents:
        # wire bail hooked through two punched holes: the can was hung over the fire
        bail = [Vector((math.cos(t) * (R + 0.0035), 0.0, h - 0.008 + math.sin(t) * 0.062)) for t in [math.pi * i / 16 for i in range(17)]]
        K.tube(mb, bail, 0.0011, sides=5, mat="item_steel_dark")
        for sx in (1, -1):
            loop = [Vector((sx * (R + 0.0035) + math.cos(a) * 0.003 * sx, math.sin(a) * 0.003, h - 0.008 + math.sin(a) * 0.0)) for a in
                    [2 * math.pi * i / 8 for i in range(8)]]
            K.tube(mb, loop, 0.0009, sides=4, mat="item_steel_dark", closed=True)
    parts = [mb.build(p["name"], sharp_deg=50)]
    if contents:
        r = common.rng(seed)
        for k in range(3):
            parts.append(K.pebble(f"chunk{k}", (0.016, 0.012, 0.008), seed + 40 + k, mat=contents, subdiv=1, lump=0.2,
                                  center=(r.uniform(-0.015, 0.015), r.uniform(-0.015, 0.015), h - 0.0135)))
    return parts, {}


def soda(p):
    mb = K.MB()
    P.soda_can(mb, seed=int(p["seed"]))
    return [mb.build("soda_can", sharp_deg=50)], {}


def bottle(p):
    seed = int(p["seed"])
    mb = K.MB()
    fill = float(p.get("fill", 0.0))
    P.pet_bottle(mb, fill=fill, water=p.get("water", "item_bottle_water"), seed=seed, crush=0.0 if fill > 0 else 0.22)
    obj = mb.build(p["name"], sharp_deg=50)
    return [obj], {"ground": LIE_X @ Matrix.Translation((0, 0, -0.1)), "settle": 30.0}


def glass_bottle(p):
    mb = K.MB()
    P.glass_bottle(mb, mat="item_glass_brown")
    return [mb.build("glass_bottle", sharp_deg=50)], {"ground": LIE_X @ Matrix.Translation((0, 0, -0.11)), "settle": 30.0}


def berries(p):
    seed = int(p["seed"])
    r = common.rng(seed)
    mb = K.MB()
    # leaves first (huckleberry leaf atlas quadrant), lying flat with a little curl
    for k in range(3):
        a = r.uniform(0, math.tau)
        base = Vector((math.cos(a) * 0.012, math.sin(a) * 0.012, 0.0012))
        d = Vector((math.cos(a + 0.4), math.sin(a + 0.4), 0.05))
        K.card(mb, base, d, (0, 0, 1), 0.056, 0.042, mat="item_herb", droop=-0.08, nu=2, nv=3, rect=(0.5, 0.5, 1.0, 1.0), curl=0.25)
    obj_leaves = mb.build("leaves", sharp_deg=None)
    spots = []
    for i in range(12):
        for _ in range(30):
            x, y = r.uniform(-0.016, 0.016), r.uniform(-0.016, 0.016)
            rr = r.uniform(0.0042, 0.0055)
            z = rr
            for (sx, sy, sz, sr) in spots:
                dd = math.hypot(x - sx, y - sy)
                if dd < sr + rr:
                    z = max(z, sz + math.sqrt(max(0.0, (sr + rr) ** 2 - dd * dd)) * 0.92)
            if z < 0.014:
                break
        spots.append((x, y, z, rr))
    bm_all = []
    for i, (x, y, z, rr) in enumerate(spots):
        b = K.pebble(f"berry{i}", (rr * 2, rr * 2, rr * 1.9), seed + i, mat="item_berry", subdiv=2, flat_bottom=0.0, lump=0.04,
                     center=(x, y, z - rr))
        bm_all.append(b)
    return [obj_leaves] + bm_all, {"settle": None}


def mushroom(p):
    seed = int(p["seed"])
    noise.seed_set(seed)
    mb = K.MB()
    R = 0.068
    na, nr = 14, 8
    th0, th1 = math.radians(-72), math.radians(72)
    top, bot = [], []
    for i in range(nr + 1):
        rho = R * (0.06 + 0.94 * i / nr)
        rt, rb = [], []
        for j in range(na + 1):
            th = th0 + (th1 - th0) * j / na
            wav = 1 + 0.06 * math.sin(th * 5 + seed) + 0.04 * noise.noise(Vector((th * 2, rho * 30, 0.5)))
            rr = rho * wav
            x, y = math.cos(th) * rr, math.sin(th) * rr
            t = i / nr
            thick = 0.024 * math.sqrt(max(0.0, 1 - t ** 2.2)) + 0.004 + 0.006 * (1 - t)
            ridge = 0.0007 * math.sin(t * math.pi * 6) * (1 - t * 0.5)
            zb = 0.003 + 0.004 * (1 - t) * 0.5 + 0.0035 * t * t
            rt.append(mb.vert((x, y, zb + thick + ridge)))
            rb.append(mb.vert((x, y, zb)))
        top.append(rt)
        bot.append(rb)
    for i in range(nr):
        for j in range(na):
            u0, u1 = i / nr, (i + 1) / nr
            v0, v1 = j / na * 0.2, (j + 1) / na * 0.2
            mb.face((top[i][j], top[i + 1][j], top[i + 1][j + 1], top[i][j + 1]), ((u0, v0), (u1, v0), (u1, v1), (u0, v1)), "item_mushroom_top")
            mb.face((bot[i][j], bot[i][j + 1], bot[i + 1][j + 1], bot[i + 1][j]),
                    ((u0 * 0.3, v0), (u0 * 0.3, v1), (u1 * 0.3, v1), (u1 * 0.3, v0)), "item_mushroom_pore")
    for j in range(na):   # margin rim
        mb.face((bot[nr][j], bot[nr][j + 1], top[nr][j + 1], top[nr][j]), ((j * 0.01, 0), ((j + 1) * 0.01, 0), ((j + 1) * 0.01, 0.01), (j * 0.01, 0.01)),
                "item_mushroom_top")
    for i in range(nr):   # flanks
        for (j, rev) in ((0, False), (na, True)):
            q = (bot[i][j], bot[i + 1][j], top[i + 1][j], top[i][j])
            mb.face(tuple(reversed(q)) if rev else q, None, "item_mushroom_top")
    # torn attachment face
    ring = [bot[0][j] for j in range(na + 1)] + [top[0][j] for j in range(na, -1, -1)]
    mb.face(list(reversed(ring)), None, "item_wood_raw", False)
    obj = mb.build("wild_mushroom", sharp_deg=60)
    return [obj], {}


def mushroom_skewer(p):
    seed = int(p["seed"])
    r = common.rng(seed)
    mb = K.MB()
    pts = [Vector((-0.15 + 0.3 * i / 7, 0.0, 0.006)) for i in range(8)]
    K.stick(mb, pts, 0.0048, 0.0042, sides=7, seed=seed, lumpy=0.05)
    tip = pts[-1]
    K.tube(mb, [tip, tip + Vector((0.03, 0, 0))], [0.0042, 0.0003], sides=7, mat="item_wood_charred", caps=(False, True), smooth=False)
    obj = mb.build("skewer", sharp_deg=60)
    parts = [obj]
    for k, x in enumerate((-0.02, 0.022, 0.062)):
        ch = K.pebble(f"chunk{k}", (0.034, 0.03, 0.022), seed + k * 7, mat="item_mushroom_cooked", subdiv=2, lump=0.22,
                      center=(x, r.uniform(-0.003, 0.003), 0.0))
        ch.data.transform(Matrix.Translation((0, 0, -0.005)))
        parts.append(ch)
    return parts, {}


def bandage(p):
    seed = int(p["seed"])
    mb = K.MB()
    R, W = 0.024, 0.05
    prof = [(0.007, 0.0)]
    for k in range(5):
        prof += [(0.009 + k * 0.003, 0.0004 * (k % 2)), (0.0105 + k * 0.003, 0.0)]
    prof += [(R, 0.0008), (R, W - 0.0008)]
    for k in range(5):
        prof += [(R - k * 0.003 - 0.0015, W - 0.0004 * (k % 2)), (R - k * 0.003 - 0.003, W)]
    prof += [(0.007, W)]
    mb.push(Matrix.Translation((0, 0, R)) @ Matrix.Rotation(math.radians(90), 4, "X") @ Matrix.Translation((0, 0, -W / 2)))
    K.lathe(mb, prof, segments=22, mat="item_cloth_bandage", cap_bottom=False, cap_top=False)
    K.lathe(mb, [(0.007, W), (0.007, 0.0)], segments=22, mat="item_cloth_bandage", cap_bottom=False, cap_top=False)
    mb.pop()
    # loose tail unrolled along the ground
    K.sheet(mb, 10, 2, lambda u, v: Vector((0.0 + u * 0.13, -W / 2 + v * W * (1 - 0.06 * u),
                                            0.0012 + 0.003 * math.sin(u * 9 + seed) * u + (0.02 * (1 - u) ** 6))),
            thickness=0.0008, mat_top="item_cloth_bandage", uv_top=lambda u, v: (u * 0.13, v * W), uv_bottom=lambda u, v: (u * 0.13, v * W))
    return [mb.build("cloth_bandage", sharp_deg=60)], {"settle": None}


def first_aid(p):
    mb = K.MB()
    Wd, D, Hb, Hl = 0.205, 0.13, 0.046, 0.022
    K.box(mb, (Wd, D, Hb), (0, 0, Hb / 2), mat="item_paint_white", bevel=0.004)
    K.box(mb, (Wd - 0.006, D - 0.006, 0.002), (0, 0, Hb + 0.001), mat="item_steel_dark", bevel=0.0005)
    K.box(mb, (Wd + 0.002, D + 0.002, Hl), (0, 0, Hb + 0.002 + Hl / 2), mat="item_paint_white", bevel=0.005)
    top = Hb + 0.002 + Hl
    # green panel with a white cross (ISO first-aid sign, no text)
    K.box(mb, (0.07, 0.07, 0.0008), (0.0, 0.0, top + 0.0004), mat="item_paint_green")
    K.box(mb, (0.042, 0.013, 0.0006), (0.0, 0.0, top + 0.0011), mat="item_paint_white")
    K.box(mb, (0.013, 0.042, 0.0006), (0.0, 0.0, top + 0.0011), mat="item_paint_white")
    # latches (front, -Y), hinge barrels (back), folding wire handle on the lid
    for sx in (-0.06, 0.06):
        K.box(mb, (0.018, 0.005, 0.024), (sx, -D / 2 - 0.002, Hb), mat="item_steel_tool", bevel=0.0012)
        K.box(mb, (0.012, 0.004, 0.006), (sx, -D / 2 - 0.0035, Hb + 0.008), mat="item_steel_tool", bevel=0.0008)
        hp = [Vector((sx - 0.02, D / 2 + 0.002, Hb + 0.001)), Vector((sx + 0.02, D / 2 + 0.002, Hb + 0.001))]
        K.tube(mb, hp, 0.0032, sides=8, mat="item_steel_tool")
    hp = K.bezier((-0.045, -0.02, top + 0.002), (-0.045, -0.045, top + 0.003), (0.045, -0.045, top + 0.003), (0.045, -0.02, top + 0.002), 10)
    K.tube(mb, hp, 0.0022, sides=6, mat="item_steel_tool")
    return [mb.build("first_aid_kit", sharp_deg=40)], {"inset": True}


def blister(p):
    mb = K.MB()
    # cut card outline (scissored on one side)
    outline = [(-0.046, -0.024), (0.004, -0.024), (0.010, -0.012), (0.002, -0.003), (0.012, 0.008), (0.006, 0.024), (-0.046, 0.024)]
    mb.push(Matrix.Translation((0, 0, 0.0004)))
    K.extrude(mb, outline, 0.0008, mat="item_foil_blister", uv_scale=8.0)
    mb.pop()
    cells = [(-0.034, -0.011), (-0.034, 0.011), (-0.017, -0.011), (-0.017, 0.011), (0.0, 0.011)]
    for k, (x, y) in enumerate(cells):
        popped = k in (1, 2)
        mb.push(Matrix.Translation((x, y, 0.0008)))
        if popped:
            K.lathe(mb, [(0.0068, 0.0), (0.0062, 0.0012), (0.0042, 0.0017), (0.002, 0.0012)], segments=14, mat="item_plastic_clear",
                    cap_bottom=False, cap_top=True, radial_fn=lambda k_, i, rr, z: 1.0 + 0.15 * math.sin(k_ * 2.1 + i))
        else:
            K.lathe(mb, [(0.0068, 0.0), (0.0066, 0.0015), (0.0058, 0.0034), (0.0040, 0.0047), (0.0015, 0.0051)], segments=14,
                    mat="item_plastic_clear", regions=[(2, 4, "item_pill", "metric")], cap_bottom=False, cap_top=True,
                    cap_mat_top="item_pill")
        mb.pop()
    return [mb.build("painkillers", sharp_deg=50)], {"settle": None}


def pill_bottle(p):
    mb = K.MB()
    prof = [(0.0145, 0.0), (0.0158, 0.0015), (0.0160, 0.006), (0.0160, 0.012), (0.0160, 0.052), (0.0160, 0.058), (0.0150, 0.060),
            (0.0150, 0.066)]
    K.lathe(mb, prof, segments=20, mat="item_plastic_amber", regions=[(3, 4, "item_rx_label", "label")], cap_bottom=True, cap_top=False)
    cap = [(0.0172, 0.0585), (0.0176, 0.060)]
    for k in range(12):
        cap.append((0.0178 if k % 2 == 0 else 0.0174, 0.0605 + k * 0.0011))
    cap += [(0.0174, 0.0745), (0.016, 0.0752)]
    K.lathe(mb, cap, segments=20, mat="item_plastic_white", cap_bottom=True, cap_top=True)
    return [mb.build("antifungal", sharp_deg=50)], {"ground": LIE_X @ Matrix.Translation((0, 0, -0.037)), "settle": 30.0}


def yarrow(p):
    seed = int(p["seed"])
    r = common.rng(seed)
    mb = K.MB()
    for s in range(4):
        y0 = r.uniform(-0.012, 0.012)
        L = r.uniform(0.2, 0.26)
        ang = r.uniform(-0.12, 0.12)
        d = Vector((math.cos(ang), math.sin(ang), 0.0))
        side = Vector((-d.y, d.x, 0))
        base = Vector((-0.12, y0, 0.0025 + s * 0.0012))
        pts = [base + d * (L * t) + Vector((0, 0, 0.004 * math.sin(t * math.pi))) for t in [i / 6 for i in range(7)]]
        K.tube(mb, pts, 0.0016, sides=5, mat="item_stem_green", cap_mat="item_stem_green")
        # leaves along the stem
        for k in range(4):
            t = 0.15 + k * 0.17
            q = base + d * (L * t) + Vector((0, 0, 0.004))
            sd = 1 if (k + s) % 2 == 0 else -1
            K.card(mb, q, side * sd + d * 0.6 + Vector((0, 0, 0.15)), (0, 0, 1), 0.06, 0.03, mat="item_herb", droop=0.15, nu=1, nv=2,
                   rect=(0.0, 0.5, 0.5, 1.0))
        tip = pts[-1]
        # flower head: two crossed side-view cards + one face-on card
        for a in (0.0, math.pi / 2):
            nh = Vector((0, math.cos(a), math.sin(a)))
            K.card(mb, tip - d * 0.006, d, nh, 0.022, 0.05, mat="item_herb", droop=0.0, nu=1, nv=1, rect=(0.5, 0.02, 1.0, 0.48))
        K.card(mb, tip + d * 0.012 - Vector((0, 0.022, 0)), Vector((0, 1, 0)), d, 0.044, 0.044, mat="item_herb", droop=0.0, nu=1, nv=1,
               rect=(0.0, 0.0, 0.5, 0.5))
    return [mb.build("yarrow", sharp_deg=None)], {"settle": None}


def poultice(p):
    seed = int(p["seed"])
    mb = K.MB()
    body = K.pebble("bundle", (0.06, 0.055, 0.042), seed, mat="item_cloth_poultice", subdiv=3, flat_bottom=0.3, lump=0.16)
    # gathered neck + tuft
    noise.seed_set(seed)
    neck = [(0.012, 0.036), (0.0085, 0.044), (0.008, 0.050), (0.011, 0.055), (0.019, 0.062), (0.022, 0.066), (0.010, 0.065)]
    K.lathe(mb, neck, segments=14, mat="item_cloth_poultice", cap_bottom=False, cap_top=True,
            radial_fn=lambda k, i, rr, z: 1.0 + (0.35 if i >= 4 else 0.12) * math.sin(k * 2.7 + seed) * (0.5 + 0.5 * math.cos(k * 1.3)))
    K.lashing(mb, (0, 0, 0.0435), (0, 0, 0.0505), 0.0086, cord=0.0019, turns=3.2, per_turn=10, mat="item_cordage", seed=seed)
    tail = K.bezier((0.009, 0.0, 0.047), (0.03, -0.01, 0.045), (0.045, -0.02, 0.01), (0.05, -0.03, 0.002), 8)
    K.tube(mb, tail, 0.0019, sides=5, mat="item_cordage", u_tile=1.0, v_scale=_cord_v(0.0019))
    return [body, mb.build("tie", sharp_deg=60)], {}


def vial(p):
    mb = K.MB()
    prof = [(0.0035, 0.0006), (0.0065, 0.0026), (0.0079, 0.0072), (0.0080, 0.012), (0.0080, 0.060), (0.0080, 0.066)]
    K.lathe(mb, prof, segments=16, mat="item_bloom_vial", cap_bottom=True, cap_top=False)
    cap = [(0.0090, 0.0648), (0.0094, 0.0656)]
    for k in range(10):
        cap.append((0.0096 if k % 2 == 0 else 0.0092, 0.066 + k * 0.0013))
    cap += [(0.0092, 0.080), (0.0080, 0.0806)]
    K.lathe(mb, cap, segments=16, mat="item_plastic_olive", cap_bottom=True, cap_top=True)
    # sealing tape band + Program stripe
    K.lathe(mb, [(0.0082, 0.0585), (0.0082, 0.0655)], segments=16, mat="item_paint_stripe", cap_bottom=False, cap_top=False)
    return [mb.build("bloom_sample", sharp_deg=50)], {"ground": LIE_X @ Matrix.Translation((0, 0, -0.04)), "settle": 25.0}


def mycelium(p):
    seed = int(p["seed"])
    r = common.rng(seed)
    noise.seed_set(seed)
    core = K.pebble("core", (0.06, 0.046, 0.022), seed, mat="item_mycelium", subdiv=3, flat_bottom=0.35, lump=0.3)
    mb = K.MB()
    for k in range(18):
        a = r.uniform(0, math.tau)
        start = Vector((math.cos(a) * 0.018, math.sin(a) * 0.014, r.uniform(0.004, 0.014)))
        pts = [start]
        d = Vector((math.cos(a), math.sin(a), r.uniform(-0.1, 0.25))).normalized()
        L = r.uniform(0.03, 0.075)
        for i in range(1, 8):
            d = (d + Vector((r.uniform(-0.5, 0.5), r.uniform(-0.5, 0.5), r.uniform(-0.3, 0.2)))).normalized()
            q = pts[-1] + d * (L / 7)
            q.z = max(0.0008, q.z)
            pts.append(q)
        K.tube(mb, pts, [0.0012 * (1 - 0.7 * i / 7) for i in range(8)], sides=4, mat="item_mycelium", caps=(False, True))
    return [core, mb.build("threads", sharp_deg=None)], {"settle": None}


BUILDERS = {
    "ration_bar": ration_bar, "can": can_item, "can_open": can_open, "soda": soda, "bottle": bottle, "glass_bottle": glass_bottle,
    "berries": berries, "mushroom": mushroom, "mushroom_skewer": mushroom_skewer, "bandage": bandage, "first_aid": first_aid,
    "blister": blister, "pill_bottle": pill_bottle, "yarrow": yarrow, "poultice": poultice, "vial": vial, "mycelium": mycelium,
}


def build(params: dict, outputs: list[str]) -> None:
    parts, opts = BUILDERS[params["kind"]](params)
    K.publish(outputs, name=params.get("name", params["kind"]), parts=parts, seed=int(params["seed"]),
              ground_rot=opts.get("ground"), settle_deg=opts.get("settle", 20.0), wear_deg=30.0, inset=opts.get("inset", True))
