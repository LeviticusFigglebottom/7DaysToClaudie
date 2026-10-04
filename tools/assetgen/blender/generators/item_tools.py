"""Hand tools and melee weapons (items + first-person viewmodels).

Modelled in the viewmodel frame: grip (rear hand) at the origin, handle along +Z with the business
end up (+Z), blade edge / striking face toward -Y, flats facing +-X. The ground pickup is the same
mesh rotated to lie on its side (+90 deg about Y) and settled. The torch is a "pointing" item: grip at
the origin, shaft along -Y with the burning head forward (-Y).

params: kind, name, seed (+ optional per-kind knobs).
"""
from __future__ import annotations

import math

from mathutils import Matrix, Vector

from lib import common, item_kit as K

LAY_FLAT = Matrix.Rotation(math.radians(90), 4, "Y")


# ------------------------------------------------------------------------------------------------
# shared bits
# ------------------------------------------------------------------------------------------------

def _hafted_handle(mb, z0, z1, *, rx, ry, seed, mat="item_wood_handle", sides=12, knob=0.0, sweep=0.0, end_mat="item_wood_end",
                   top_cap=True):
    """Shaped tool handle along Z: oval section (rx across X, ry across Y), flared knob at the butt,
    gentle S-sweep in Y. Returns the centre-line points."""
    n = 16
    pts, radii = [], []
    for i in range(n):
        t = i / (n - 1)
        z = z0 + (z1 - z0) * t
        y = sweep * math.sin(t * math.pi) - sweep * 0.4 * math.sin(t * 2 * math.pi)
        flare = 1.0 + knob * max(0.0, 1.0 - t / 0.12) ** 2
        neck = 1.0 - 0.08 * math.exp(-((t - 0.75) / 0.12) ** 2)
        pts.append(Vector((0.0, y, z)))
        radii.append((rx * flare * neck, ry * flare * neck))
    K.tube(mb, pts, radii, sides=sides, mat=mat, cap_mat=end_mat, cap_uv="disc", caps=(True, top_cap))
    return pts


def _wedge_cord(mb, p0, p1, radius, turns, seed, cord=0.0026, mat="item_cordage"):
    K.lashing(mb, p0, p1, radius, cord=cord, turns=turns, per_turn=9, sides=5, mat=mat, phase=seed * 0.7, wobble=0.0007, seed=seed)


def _split_halves(mb, z0, z1, *, r, gap_fn, seed, bark="item_bark", inner="item_wood_raw", sides=7):
    """Two half-round stick halves (split haft) from z0 to z1, pushed apart along X by gap_fn(t)."""
    for side in (1, -1):
        # D profile: arc on the outer side (+X for side=1), flat face toward the gap
        arc = [(math.cos(a), math.sin(a)) for a in [(-math.pi / 2 + math.pi * k / (sides - 1)) for k in range(sides)]]
        prof = [(0.0, -1.0)] + [(0.08 + 0.92 * c, s) for c, s in arc[1:-1]] + [(0.0, 1.0)]
        if side < 0:
            prof = [(-x, -y) for x, y in prof]
        n = 8
        pts, radii = [], []
        for i in range(n):
            t = i / (n - 1)
            z = z0 + (z1 - z0) * t
            pts.append(Vector((side * gap_fn(t), 0.0, z)))
            radii.append(r * (1.0 - 0.1 * t))
        K.tube(mb, pts, radii, profile=prof, mat=bark, cap_mat="item_wood_end", cap_uv="disc")
        # flat faces get the split-wood material: the profile's first and last points form the flat
        # side, i.e. the quads between profile index -1 and 0 of every segment.
        nf = len(prof)
        segs = n - 1
        first = len(mb.faces) - segs * nf - 2
        for i in range(segs):
            fi = first + i * nf + (nf - 1)
            mb.fmat[fi] = inner


def _sock(name, loc, fwd):
    return K.socket(name, loc, fwd)


# ------------------------------------------------------------------------------------------------
# builders: return (parts, sockets)
# ------------------------------------------------------------------------------------------------

def stone_axe(p):
    seed = int(p["seed"])
    mb = K.MB()
    hr = 0.0158
    # lower round haft, slightly crooked branch
    pts = K.branch_path(0.32, seed, bend=0.006, n=9, start=(0, 0, -0.085))
    K.stick(mb, pts, hr * 1.04, hr * 0.98, sides=10, seed=seed, caps=(True, False), lumpy=0.03)
    top = pts[-1]
    # split halves embracing the stone (gap opens around the head, closes above it)
    zc = 0.300
    hz0, hz1 = top.z, 0.372

    def gap(t):
        z = hz0 + (hz1 - hz0) * t
        bulge = math.exp(-((z - zc) / 0.034) ** 2)
        return 0.0012 + 0.0145 * bulge
    mb.push(Matrix.Translation((top.x, top.y, 0)))
    _split_halves(mb, hz0, hz1, r=hr * 0.97, gap_fn=gap, seed=seed)
    mb.pop()
    # lashings below / above the head and an X binding over the stone faces
    _wedge_cord(mb, (top.x, top.y, 0.226), (top.x, top.y, 0.262), hr + 0.001, 6.5, seed)
    _wedge_cord(mb, (top.x, top.y, 0.334), (top.x, top.y, 0.362), hr + 0.0015, 5.5, seed + 1)
    rr = hr * 0.97 + 0.0022
    for side in (1, -1):
        for diag in (1, -1):
            for k in range(2):
                off = (k - 0.5) * 0.0055
                pts_c = []
                for i in range(11):
                    t = i / 10
                    z = 0.262 + (0.336 - 0.262) * t + off
                    th = diag * (1.25 - 2.5 * t)
                    g = gap(min(1.0, max(0.0, (z - hz0) / (hz1 - hz0))))
                    pts_c.append(Vector((top.x + side * (g + rr * math.cos(th)), top.y + rr * math.sin(th), z)))
                K.tube(mb, pts_c, 0.0023, sides=5, mat="item_cordage", u_tile=1.0, v_scale=1.0 / (2 * math.pi * 0.0023) / 3)
    handle = mb.build("haft", sharp_deg=60)
    head = K.knapped("head", length=0.148, width=0.08, thickness=0.029, seed=seed + 5, scars=44, cortex=0.22)
    head.data.transform(Matrix.Translation((top.x, -0.022 + top.y, zc)) @ Matrix.Rotation(math.radians(-4), 4, "X"))
    sockets = [_sock("socket_head", (0, -0.09, zc), (0, -1, 0))]
    return [handle, head], sockets


def hatchet(p):
    seed = int(p["seed"])
    mb = K.MB()
    _hafted_handle(mb, -0.075, 0.272, rx=0.0118, ry=0.0165, seed=seed, knob=0.32, sweep=0.006, sides=12)
    # head: stations along Y from poll (+Y) to bit (-Y); 12-point chamfered section in XZ (interior
    # points on the cheeks keep the vertex wear mask on the chamfers)
    zc = 0.245
    st = [  # y, half-thickness, z_top, z_bot, material of the following segment
        (0.050, 0.0112, 0.0185, -0.0185, "item_paint_red"),
        (0.047, 0.0124, 0.0212, -0.0212, "item_paint_red"),
        (0.030, 0.0134, 0.0236, -0.0236, "item_paint_red"),
        (0.012, 0.0135, 0.0246, -0.0246, "item_paint_red"),
        (-0.008, 0.0128, 0.0240, -0.0262, "item_paint_red"),
        (-0.022, 0.0106, 0.0222, -0.0290, "item_paint_red"),
        (-0.040, 0.0080, 0.0250, -0.0360, "item_paint_red"),
        (-0.060, 0.0054, 0.0320, -0.0460, "item_paint_red"),
        (-0.078, 0.0034, 0.0400, -0.0540, "item_steel_bright"),
        (-0.088, 0.0016, 0.0440, -0.0580, "item_steel_bright"),
        (-0.095, 0.0003, 0.0460, -0.0600, None),
    ]
    rings = []
    for (y, tx, zt, zb, _m) in st:
        ch = min(0.0028, tx * 0.45)
        h = zt - zb
        ring_pts = [(tx, zb + ch), (tx, zb + h * 0.35), (tx, zb + h * 0.65), (tx, zt - ch), (tx - ch, zt), (-tx + ch, zt),
                    (-tx, zt - ch), (-tx, zb + h * 0.65), (-tx, zb + h * 0.35), (-tx, zb + ch), (-tx + ch, zb), (tx - ch, zb)]
        ring = []
        for x, z in ring_pts:
            # convex bit: the middle of the edge protrudes
            curve = 0.0 if y > -0.05 else (1 - ((z - (zt + zb) / 2) / (h / 2 + 1e-6)) ** 2) * 0.008 * (-0.05 - y) / 0.045
            ring.append(mb.vert((x, y - curve, zc + z)))
        rings.append(ring)
    f0 = len(mb.faces)
    nk = 12
    for i in range(len(rings) - 1):
        m = st[i][4]
        for k in range(nk):
            a, b = rings[i][k], rings[i][(k + 1) % nk]
            c, d = rings[i + 1][(k + 1) % nk], rings[i + 1][k]
            mb.face((a, b, c, d), None, m, True)
    mb.face(list(reversed(rings[0])), None, "item_steel_tool", False)
    mb.face(rings[-1], None, "item_steel_bright", False)
    K.reproject_box(mb, f0, 1.0)
    # handle top with a steel wedge through the eye
    K.box(mb, (0.0016, 0.022, 0.006), (0, 0.0, 0.272), mat="item_steel_tool")
    obj = mb.build("hatchet", sharp_deg=35)
    sockets = [_sock("socket_head", (0, -0.103, zc - 0.007), (0, -1, 0))]
    return [obj], sockets


def crude_spear(p):
    seed = int(p["seed"])
    mb = K.MB()
    r1, r2 = 0.0152, 0.0128
    lo = K.branch_path(1.16, seed, bend=0.01, n=14, start=(0, 0, -0.71))
    K.stick(mb, lo, r1, r1 * 0.9, sides=9, seed=seed, lumpy=0.04)
    # upper stick: overlaps the lower one for ~0.24 m on its +X side, then bends onto the axis
    up = []
    for i in range(16):
        t = i / 15
        z = 0.205 + t * 0.80
        x = (r1 + r2) * 0.96 * (1 - common.smoothstep(0.30, 0.55, t))
        up.append(Vector((x + lo[-1].x * common.smoothstep(0.3, 0.6, t), lo[-1].y * common.smoothstep(0.3, 0.6, t), z)))
    K.stick(mb, up, r2, r2 * 0.88, sides=9, seed=seed + 1, caps=(True, False), lumpy=0.04)
    # carved, fire-hardened point (faceted)
    base = up[-1]
    rr = r2 * 0.88
    carve = [base + Vector((0, 0, 0.13 * t)) for t in (0.0, 0.25, 0.5, 0.72)]
    char = [base + Vector((0, 0, 0.13 * t)) for t in (0.72, 0.86, 0.96, 1.0)]
    K.tube(mb, carve, [rr * (1 - 0.72 * t) for t in (0.0, 0.25, 0.5, 0.72)], sides=7, mat="item_wood_raw", caps=(False, False), smooth=False, rot=0.3)
    K.tube(mb, char, [rr * (1 - 0.72) * (1 - (t - 0.72) / 0.28 * 0.97) for t in (0.72, 0.86, 0.96, 1.0)], sides=7, mat="item_wood_charred",
           caps=(False, True), smooth=False, rot=0.3)
    # two lashings around both sticks (elliptical wraps)
    for k, (za, zb) in enumerate(((0.225, 0.262), (0.372, 0.405))):
        cx = (r1 + r2) * 0.48
        pts = []
        turns = 6
        for i in range(turns * 12 + 1):
            t = i / (turns * 12)
            th = 2 * math.pi * turns * t + seed
            pts.append(Vector((cx + math.cos(th) * (r1 + r2) * 1.02, math.sin(th) * r1 * 1.12, za + (zb - za) * t)))
        K.tube(mb, pts, 0.0026, sides=5, mat="item_cordage", u_tile=1.0, v_scale=1.0 / (2 * math.pi * 0.0026) / 3)
    obj = mb.build("crude_spear", sharp_deg=55)
    sockets = [_sock("socket_head", tuple(base + Vector((0, 0, 0.13))), (0, 0, 1))]
    return [obj], sockets


def stone_club(p):
    seed = int(p["seed"])
    mb = K.MB()
    hr = 0.0195
    pts = K.branch_path(0.47, seed, bend=0.008, n=10, start=(0, 0, -0.075))
    K.stick(mb, pts, hr * 1.06, hr * 0.92, sides=10, seed=seed, caps=(True, False), lumpy=0.05)
    top = pts[-1]
    zc = 0.505
    stone_r = (0.032, 0.05, 0.045)  # half sizes x, y, z

    def gap(t):
        z = top.z + (0.585 - top.z) * t
        bulge = math.exp(-((z - zc) / 0.045) ** 2)
        return 0.0015 + (stone_r[0] + 0.004) * bulge
    mb.push(Matrix.Translation((top.x, top.y, 0)))
    _split_halves(mb, top.z, 0.585, r=hr * 0.85, gap_fn=gap, seed=seed)
    mb.pop()
    _wedge_cord(mb, (top.x, top.y, 0.40), (top.x, top.y, 0.452), hr + 0.001, 9, seed)
    _wedge_cord(mb, (top.x, top.y, 0.558), (top.x, top.y, 0.582), hr * 0.9 + 0.0015, 4.5, seed + 2)
    # cross lashing over the stone (front/back of the stone, in Y)
    for k in range(4):
        side = 1 if k % 2 == 0 else -1
        off = (k // 2 - 0.5) * 0.008
        a = Vector((0.0, 0, 0.452 + off))
        b = Vector((0.02 * side, side * (stone_r[1] + 0.004), zc - 0.02))
        c = Vector((-0.02 * side, side * (stone_r[1] + 0.004), zc + 0.02))
        d = Vector((0.0, 0, 0.558 + off))
        path = K.bezier(a + Vector((0, side * 0.02, 0)), b, c, d + Vector((0, side * 0.02, 0)), 9)
        K.tube(mb, path, 0.0028, sides=5, mat="item_cordage", u_tile=1.0, v_scale=1.0 / (2 * math.pi * 0.0028) / 3)
    obj = mb.build("haft", sharp_deg=60)
    stone = K.pebble("club_stone", (stone_r[0] * 2.3, stone_r[1] * 2, stone_r[2] * 2), seed + 9, mat="item_stone", subdiv=3,
                     flat_bottom=0.0, lump=0.08)
    stone.data.transform(Matrix.Translation((top.x, top.y, zc - stone_r[2])))
    sockets = [_sock("socket_head", (0, -stone_r[1], zc), (0, -1, 0))]
    return [obj, stone], sockets


def steel_pipe(p):
    mb = K.MB()
    ro, ri = 0.0167, 0.0133
    z0, z1 = -0.10, 0.60
    # pipe body with an open, deburred butt end (inner wall visible)
    prof = [(ri, z0 + 0.03), (ri, z0 + 0.0005), (ri + 0.0008, z0), (ro - 0.0008, z0), (ro, z0 + 0.0008),
            (ro, z1 - 0.022)]
    # threads into the fitting
    for k in range(6):
        zt = z1 - 0.021 + k * 0.0035
        prof += [(ro * 0.985, zt), (ro * 0.955, zt + 0.0017)]
    prof += [(ro * 0.95, z1 + 0.003)]
    K.lathe(mb, prof, segments=16, mat="item_iron_strap", cap_bottom=True, cap_top=False, cap_mat_bottom="item_rust")
    # tape wrap on the grip (with raised overlapping edges)
    tz0, tz1 = -0.085, 0.105
    tp = []
    n = 14
    for i in range(n + 1):
        t = i / n
        z = tz0 + (tz1 - tz0) * t
        tp.append((ro + 0.0009 + (0.0004 if i % 2 == 0 else 0.0), z))
    K.lathe(mb, [(ro + 0.0002, tz0 - 0.001)] + tp + [(ro + 0.0002, tz1 + 0.001)], segments=16, mat="item_duct_tape",
            cap_bottom=False, cap_top=False, angle0=0.1)
    # loose tape tail
    K.sheet(mb, 3, 2, lambda u, v: Vector((math.cos(-0.5 + u * 0.5) * (ro + 0.0013 + u * 0.002), math.sin(-0.5 + u * 0.5) * (ro + 0.0013 + u * 0.004),
                                           tz1 - 0.012 + v * 0.024 - u * 0.006)), thickness=0.0004, mat_top="item_duct_tape")
    # galvanised tee fitting on the business end
    fz = z1 + 0.01
    run = [(0.0222, fz - 0.026), (0.0236, fz - 0.0235), (0.0236, fz - 0.020), (0.0212, fz - 0.017), (0.0212, fz + 0.017),
           (0.0236, fz + 0.020), (0.0236, fz + 0.0235), (0.0222, fz + 0.026)]
    K.lathe(mb, run, segments=16, mat="item_galvanized", cap_bottom=True, cap_top=True)
    mb.push(Matrix.Translation((0, 0, fz)) @ Matrix.Rotation(math.radians(90), 4, "X"))
    branch = [(0.0205, 0.0), (0.0212, 0.031), (0.0236, 0.034), (0.0236, 0.0375), (0.0222, 0.040), (0.0165, 0.040), (0.0165, 0.030)]
    K.lathe(mb, branch, segments=16, mat="item_galvanized", cap_bottom=False, cap_top=True, cap_mat_top="item_rust")
    mb.pop()
    obj = mb.build("steel_pipe", sharp_deg=50)
    sockets = [_sock("socket_head", (0, -0.035, fz), (0, -1, 0))]
    return [obj], sockets


def machete(p):
    mb = K.MB()
    zb0, ztip = 0.072, 0.535
    stations = []
    n = 18
    for i in range(n):
        t = i / (n - 1)
        z = zb0 + (ztip - zb0) * t
        ys = 0.013 if z < 0.49 else 0.013 - (z - 0.49) / (ztip - 0.49) * 0.017
        if z < 0.43:
            ye = -0.034 - 0.003 * math.sin(t * math.pi * 0.9)
        else:
            k = (z - 0.43) / (ztip - 0.43)
            ye = -0.036 + (0.036 + ys) * (1 - math.sqrt(max(0.0, 1 - k * k)))
        if i == 0:
            ye = -0.026
        ts = 0.0026 * (1 - 0.35 * t)
        stations.append({"z": z, "ys": ys, "ye": min(ye, ys - 0.0015), "ts": ts, "tsh": ts * 0.75, "fsh": 0.72})
    stations[-1]["ys"] = stations[-1]["ye"] + 0.0012
    K.blade(mb, stations, mat_flat="item_paint_black", mat_bevel="item_steel_bright", mat_spine="item_paint_black")
    # riveted handle (bird's-head pommel), finger swell at the front (-Y)
    hp, hr = [], []
    m = 12
    for i in range(m):
        t = i / (m - 1)
        z = -0.072 + 0.146 * t
        y = -0.004 + 0.004 * math.sin(t * math.pi) - (0.008 * (1 - t / 0.15) if t < 0.15 else 0)
        ry = 0.0155 + 0.0025 * math.exp(-((t - 0.9) / 0.08) ** 2) + 0.004 * max(0, 1 - t / 0.12)
        rx = 0.0115 - 0.0015 * t
        hp.append(Vector((0, y, z)))
        hr.append((rx, ry))
    K.tube(mb, hp, hr, profile=K.rect_profile(1.0, 1.0, 0.45), mat="item_plastic_black", caps=(True, True))
    for z in (-0.045, 0.0, 0.045):
        for side in (1, -1):
            mb.push(Matrix.Translation((side * 0.0112, -0.003 + 0.002 * math.sin((z + 0.072) / 0.146 * math.pi), z)) @
                    Matrix.Rotation(math.radians(90 * side), 4, "Y"))
            K.lathe(mb, [(0.0035, -0.0004), (0.0035, 0.0002), (0.0026, 0.0008)], segments=10, mat="item_steel_tool",
                    cap_bottom=False, cap_top=True)
            mb.pop()
    obj = mb.build("machete", sharp_deg=32)
    sockets = [_sock("socket_head", (0, -0.035, 0.36), (0, -1, 0))]
    return [obj], sockets


def kitchen_knife(p):
    mb = K.MB()
    zb0, ztip = 0.078, 0.29
    stations = []
    n = 16
    for i in range(n):
        t = i / (n - 1)
        z = zb0 + (ztip - zb0) * t
        ys = 0.009 - max(0.0, (z - 0.2)) / (ztip - 0.2) * 0.013
        heel = -0.036
        if z < 0.17:
            ye = heel + 0.002 * t
        else:
            k = (z - 0.17) / (ztip - 0.17)
            ye = heel + 0.002 + (ys - heel) * (k ** 1.7)
        ts = 0.0021 * (1 - 0.6 * t)
        stations.append({"z": z, "ys": ys, "ye": min(ye, ys - 0.001), "ts": ts, "tsh": ts * 0.7, "fsh": 0.35})
    stations[-1]["ye"] = stations[-1]["ys"] - 0.0006
    K.blade(mb, stations, mat_flat="item_steel_tool", mat_bevel="item_steel_bright", mat_spine="item_steel_tool")
    # bolster
    K.box(mb, (0.006, 0.03, 0.008), (0, -0.007, 0.074), mat="item_steel_bright", bevel=0.0015)
    # scales + tang
    hp, hr = [], []
    m = 12
    for i in range(m):
        t = i / (m - 1)
        z = -0.058 + 0.128 * t
        y = -0.004 - 0.003 * math.sin(t * math.pi * 0.9) - 0.002 * t
        ry = 0.0118 + 0.0018 * math.exp(-((t - 0.15) / 0.12) ** 2)
        hp.append(Vector((0, y, z)))
        hr.append(ry)
    for side in (1, -1):
        prof = [(0.0, -1.0), (0.55, -0.98), (0.9, -0.75), (1.0, -0.3), (1.0, 0.3), (0.9, 0.75), (0.55, 0.98), (0.0, 1.0)]
        if side < 0:
            prof = [(-x, -y) for x, y in prof]
        K.tube(mb, [q + Vector((side * 0.0016, 0, 0)) for q in hp], [(0.0078, rr) for rr in hr], profile=prof,
               mat="item_plastic_black", caps=(True, True))
    K.tube(mb, hp, [(0.0016, rr * 0.995) for rr in hr], profile=K.rect_profile(1.0, 1.0, 0.0), mat="item_steel_tool", caps=(True, True))
    for z in (-0.036, 0.0, 0.036):
        y = -0.004 - 0.003 * math.sin((z + 0.058) / 0.128 * math.pi * 0.9)
        for side in (1, -1):
            mb.push(Matrix.Translation((side * 0.0093, y, z)) @ Matrix.Rotation(math.radians(90 * side), 4, "Y"))
            K.lathe(mb, [(0.0028, -0.0006), (0.0028, 0.0001), (0.0022, 0.0003)], segments=10, mat="item_steel_bright",
                    cap_bottom=False, cap_top=True)
            mb.pop()
    obj = mb.build("kitchen_knife", sharp_deg=30)
    sockets = [_sock("socket_head", (0, -0.03, 0.2), (0, -1, 0))]
    return [obj], sockets


def claw_hammer(p):
    seed = int(p["seed"])
    mb = K.MB()
    _hafted_handle(mb, -0.052, 0.262, rx=0.0118, ry=0.0158, seed=seed, knob=0.25, sweep=0.0, sides=12)
    zc = 0.248
    # face + neck: lathe along -Y
    mb.push(Matrix.Translation((0, 0.0, zc)) @ Matrix.Rotation(math.radians(90), 4, "X"))
    prof = [(0.0125, 0.017), (0.0108, 0.028), (0.0112, 0.038), (0.0138, 0.046), (0.0148, 0.050), (0.0146, 0.0565),
            (0.0128, 0.058)]
    # built along +Z then rotated +90 deg about X: +Z -> -Y, so the striking face looks forward (-Y)
    K.lathe(mb, prof, segments=16, mat="item_steel_tool", cap_bottom=False, cap_top=True, cap_mat_top="item_steel_bright",
            regions=[(5, 6, "item_steel_bright", "metric")])
    mb.pop()
    K.box(mb, (0.0215, 0.036, 0.034), (0, 0.0, zc), mat="item_steel_tool", bevel=0.0035)
    # claw: two curved tapered tines with a V gap
    for side in (1, -1):
        pts = K.bezier((side * 0.0042, 0.015, zc + 0.006), (side * 0.0047, 0.045, zc + 0.008), (side * 0.0052, 0.068, zc - 0.006),
                       (side * 0.0058, 0.080, zc - 0.036), 9)
        radii = []
        for i in range(len(pts)):
            t = i / (len(pts) - 1)
            radii.append((0.0062 * (1 - 0.55 * t), 0.0105 * (1 - 0.75 * t) + 0.0012))
        prof = [(1.0, -0.2), (0.6, 0.85), (0.0, 1.0), (-0.95, 0.4), (-0.95, -0.4), (0.0, -1.0), (0.6, -0.85)]
        if side < 0:
            prof = [(-x, y) for x, y in reversed(prof)]
        K.tube(mb, pts, radii, profile=prof, mat="item_steel_tool", up=Vector((side, 0, 0)))
    obj = mb.build("claw_hammer", sharp_deg=40)
    sockets = [_sock("socket_head", (0, -0.058, zc), (0, -1, 0))]
    return [obj], sockets


def shovel(p):
    mb = K.MB()
    # ash handle: butt at z=-0.08, into the socket at z=1.06
    pts = [Vector((0, 0, -0.085 + 1.16 * t)) for t in [i / 13 for i in range(14)]]
    radii = [0.0172 + 0.0028 * t + 0.0016 * max(0, 1 - t / 0.04) for t in [i / 13 for i in range(14)]]
    K.tube(mb, pts, radii, sides=12, mat="item_wood_handle", cap_mat="item_wood_end", cap_uv="disc")
    # steel socket (frog), tapered with a rivet
    sp = [(0.0198, 0.975), (0.0206, 0.98), (0.0215, 1.04), (0.0245, 1.10), (0.026, 1.13)]
    K.lathe(mb, [(0.0192, 0.974)] + sp, segments=14, mat="item_paint_green", cap_bottom=False, cap_top=False)
    for side in (1, -1):
        mb.push(Matrix.Translation((side * 0.0212, 0, 1.0)) @ Matrix.Rotation(math.radians(90 * side), 4, "Y"))
        K.lathe(mb, [(0.0035, -0.0006), (0.0035, 0.0003), (0.0026, 0.0011)], segments=8, mat="item_steel_tool",
                cap_bottom=False, cap_top=True)
        mb.pop()
    # dished round-point blade, tilted forward (lift), front (scoop) face toward -Y
    lift = math.radians(18)
    w, L = 0.118, 0.30
    zb = 1.115

    def blade_pos(u, v):
        x = (u - 0.5) * 2 * w
        z = v * L
        half = w * (1 - (max(0.0, v - 0.35) / 0.65) ** 1.9) ** 0.5 if v > 0.35 else w
        x = (u - 0.5) * 2 * max(half, 0.004)
        dish = 0.028 * (x / w) ** 2 + 0.006 * math.sin(v * math.pi)
        y = -dish
        q = Vector((x, y, z))
        q = Matrix.Rotation(lift, 3, "X") @ q
        return q + Vector((0, -0.012, zb))
    K.sheet(mb, 10, 12, blade_pos, thickness=0.0022, mat_top="item_paint_green", mat_bottom="item_paint_green", mat_edge="item_steel_tool",
            uv_top=lambda u, v: (u * 0.24, v * 0.3), uv_bottom=lambda u, v: (u * 0.24, v * 0.3))
    # rolled step on the top edge
    step = [blade_pos(u, 0.0) + Vector((0, 0.009, 0.004)) for u in [i / 10 for i in range(11)]]
    K.tube(mb, step, (0.0045, 0.0028), sides=6, mat="item_paint_green", caps=(True, True))
    obj = mb.build("shovel", sharp_deg=45)
    sockets = [_sock("socket_head", tuple(blade_pos(0.5, 1.0)), (0, 0, 1))]
    return [obj], sockets


def torch(p):
    """Pointing item: grip at origin, shaft along -Y, cloth-wrapped head forward."""
    seed = int(p["seed"])
    mb = K.MB()
    pts = K.branch_path(0.58, seed, bend=0.006, n=10, start=(0, 0, -0.17))
    K.stick(mb, pts, 0.0152, 0.0138, sides=9, seed=seed, lumpy=0.04)
    tip = pts[-1]
    # bulgy cloth wrap (lathe around the shaft end) + spiral strip edges
    zc0, zc1 = 0.25, 0.405
    prof = [(0.0145, zc0 - 0.004)]
    nseg = 12
    for i in range(nseg + 1):
        t = i / nseg
        z = zc0 + (zc1 - zc0) * t
        bulge = 0.024 + 0.008 * math.sin(t * math.pi) + 0.003 * math.sin(t * math.pi * 5 + seed)
        prof.append((bulge, z))
    prof.append((0.012, zc1 + 0.008))
    mb.push(Matrix.Translation((tip.x, tip.y, 0)))
    from mathutils import noise
    noise.seed_set(seed)
    K.lathe(mb, prof, segments=14, mat="item_cloth_torch", cap_bottom=False, cap_top=True, cap_mat_top="item_wood_charred",
            radial_fn=lambda k, i, rr, z: 1.0 + 0.09 * noise.noise(Vector((math.cos(k * 0.449) * 2, math.sin(k * 0.449) * 2, z * 30))))
    hel = K.helix((0, 0, zc0 + 0.01), (0, 0, zc1 - 0.01), 0.029, 2.2, per_turn=14)
    K.tube(mb, hel, (0.0035, 0.009), sides=6, mat="item_cloth_torch", u_tile=0.05)
    mb.pop()
    _wedge_cord(mb, (tip.x, tip.y, zc0 - 0.012), (tip.x, tip.y, zc0 + 0.004), 0.0175, 4, seed)
    _wedge_cord(mb, (tip.x, tip.y, zc1 - 0.03), (tip.x, tip.y, zc1 - 0.016), 0.03, 3, seed + 1)
    obj = mb.build("torch", sharp_deg=60)
    # rotate into the pointing frame: +Z (head) -> -Y
    obj.data.transform(Matrix.Rotation(math.radians(90), 4, "X"))
    sockets = [_sock("socket_flame", (tip.x, -(zc1 - 0.04), tip.y), (0, -1, 0))]
    return [obj], sockets


BUILDERS = {
    "stone_axe": (stone_axe, LAY_FLAT),
    "hatchet": (hatchet, LAY_FLAT),
    "crude_spear": (crude_spear, LAY_FLAT),
    "stone_club": (stone_club, LAY_FLAT),
    "steel_pipe": (steel_pipe, LAY_FLAT),
    "machete": (machete, LAY_FLAT),
    "kitchen_knife": (kitchen_knife, LAY_FLAT),
    "claw_hammer": (claw_hammer, LAY_FLAT),
    "shovel": (shovel, LAY_FLAT),
    "torch": (torch, Matrix.Rotation(math.radians(90), 4, "Z")),
}


def build(params: dict, outputs: list[str]) -> None:
    fn, ground = BUILDERS[params["kind"]]
    parts, sockets = fn(params)
    K.publish(outputs, name=params.get("name", params["kind"]), parts=parts, seed=int(params["seed"]),
              viewmodel=True, ground_rot=ground, sockets=sockets, settle_deg=float(params.get("settle", 25.0)),
              wear_deg=float(params.get("wear_deg", 14.0 if params["kind"] == "stone_axe" else 28.0)))
