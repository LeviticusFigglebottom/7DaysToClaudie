"""Exterior props family — vehicle wrecks: a 90s mid-size sedan and a 90s full-size pickup.

Body = lofted lower shell (rings along Y; wheel arches cut into the sides; the deck is open over
the cabin) + lofted greenhouse (horizontal slices whose labelled points put pillars/windows in
the right places; windows are inset, then intact, cracked-out or gone) + bumpers, lamps, grille,
mirrors, handles, wipers, wheel wells, simple interior, flat tyres. Front faces -Y (Godot +Z).

clean     : abandoned — flat tyres, grime, light rust on sills and arches, one side window out.
worn      : heavy rust, dents, most glass broken, hubcaps and a mirror gone, bumper sagging.
destroyed : burnt-out shell on bare rims, no glass, charred interior, sagging roof.
No badges, plates or text anywhere (blank plate recess only).
"""
from __future__ import annotations

import math

import bmesh
from mathutils import Vector

from lib import common, materials
from lib import props_ext_kit as K
from lib import props_ext_parts as P


# ============================================================================================
# Small helpers
# ============================================================================================

def _interp(keys: list[tuple[float, float]], x: float) -> float:
    """Piecewise interpolation with cosine easing between keys (smooth body curves)."""
    if x <= keys[0][0]:
        return keys[0][1]
    for (x0, v0), (x1, v1) in zip(keys[:-1], keys[1:]):
        if x <= x1:
            t = (x - x0) / max(1e-9, x1 - x0)
            t = 0.5 - 0.5 * math.cos(math.pi * t)
            return v0 + (v1 - v0) * t
    return keys[-1][1]


def _mesh_with_mats(name: str, bm: bmesh.types.BMesh, mats: list[str]):
    me_obj = K._obj_raw(name, bm)
    for m in mats:
        materials.assign(me_obj, m)
    return me_obj


# ============================================================================================
# Lower body shell
# ============================================================================================

TOP_SEGS = (5, 6, 7, 8)  # ring segments forming the deck/hood/trunk top surface


def _half_width(S: dict, y: float) -> float:
    W = S["W"]
    yf, yr = S["y_front"], S["y_rear"]
    rf, rr = S["rc_front"], S["rc_rear"]
    w = W
    if y < yf + rf:
        d = (yf + rf - y) / rf
        w = W - rf + rf * math.sqrt(max(0.0, 1 - d * d))
    if y > yr - rr:
        d = (y - (yr - rr)) / rr
        w = W - rr + rr * math.sqrt(max(0.0, 1 - d * d))
    t = (y - yf) / (yr - yf)
    return w - S.get("taper", 0.03) * (1 - math.sin(math.pi * t)) ** 2


def _stations(S: dict, y0: float, y1: float) -> list[float]:
    ys = []
    n = max(2, int((y1 - y0) / 0.2))
    ys += [y0 + (y1 - y0) * i / n for i in range(n + 1)]
    for yc, R in zip(S["axles"], S["arch_r"]):
        ys += [yc + R * math.cos(math.pi * k / 8) for k in range(9)]
        ys += [yc - R - 0.03, yc + R + 0.03]
    for k in range(1, 4):
        ys.append(S["y_front"] + S["rc_front"] * (1 - math.cos(k * math.pi / 6)))
        ys.append(S["y_rear"] - S["rc_rear"] * (1 - math.cos(k * math.pi / 6)))
    for s in S.get("seams", []):
        ys += [s - 0.004, s + 0.004]
    ys += list(S.get("cabin", ()))
    ys += list(S.get("trunk", ()))
    ys += [k for k, _ in S["top"]]
    ys = sorted(y for y in ys if y0 - 1e-6 <= y <= y1 + 1e-6)
    out = []
    for y in ys:
        if not out or y - out[-1] > 0.006:
            out.append(y)
    if y1 - out[-1] > 1e-6:
        out.append(y1)
    return out


def _ring(S: dict, y: float, zoff: float, axle_z: float) -> list[tuple[float, float, float]]:
    w = _half_width(S, y)
    zt = _interp(S["top"], y) + zoff
    cr = _interp(S["crown"], y)
    zb = _interp(S["bot"], y) + zoff
    zlo = zb
    for yc, R in zip(S["axles"], S["arch_r"]):
        dy = y - yc
        if abs(dy) < R:
            zlo = max(zlo, axle_z + math.sqrt(R * R - dy * dy) * S.get("arch_squash", 1.0))
    hz = zt - zlo
    half = [(w - 0.04, zlo), (w, zlo + min(0.05, 0.15 * hz)), (w + 0.006, zlo + 0.45 * hz),
            (w, zt - min(0.07, 0.2 * hz)), (w - 0.025, zt - min(0.012, 0.06 * hz)), (w - 0.08, zt),
            (w * 0.5, zt + cr * 0.75), (0.0, zt + cr)]
    left = [(-x, y, z) for x, z in half]
    right = [(x, y, z) for x, z in reversed(half[:-1])]
    return left + right


def lower_body(S: dict, zoff: float, axle_z: float, *, y0=None, y1=None, open_cabin=True, cap_front=True,
               cap_rear=True, name="body", open_trunk=False):
    y0 = S["y_front"] if y0 is None else y0
    y1 = S["y_rear"] if y1 is None else y1
    st = _stations(S, y0, y1)
    bm = bmesh.new()
    rings = [[bm.verts.new(p) for p in _ring(S, y, zoff, axle_z)] for y in st]
    n = len(rings[0])
    holes = []
    if open_cabin:
        holes.append(S.get("cabin", (1e9, -1e9)))
    if open_trunk:
        holes.append(S["trunk"])
    for i in range(len(rings) - 1):
        ym = (st[i] + st[i + 1]) / 2
        for k in range(n - 1):
            if k in TOP_SEGS and any(a < ym < b for a, b in holes):
                continue
            bm.faces.new((rings[i][k], rings[i][k + 1], rings[i + 1][k + 1], rings[i + 1][k]))
    if cap_front:
        bm.faces.new(list(reversed(rings[0])))
    if cap_rear:
        bm.faces.new(rings[-1])
    return K._obj_raw(name, bm), st


# ============================================================================================
# Greenhouse (cabin glass + pillars + roof)
# ============================================================================================

WINDOWS = {
    "windshield": [("LC1", "LF1"), ("LF1", "F0"), ("F0", "F1"), ("F1", "C1")],
    "front_r": [("S1", "S2")], "rear_r": [("S3", "S4")],
    "front_l": [("LS2", "LS1")], "rear_l": [("LS4", "LS3")],
    "rear": [("C4", "R1"), ("R1", "R0"), ("R0", "LR1"), ("LR1", "LC4")],
}


def _gh_ring(G: dict, i: int, zoff: float) -> list[tuple[str, tuple[float, float, float]]]:
    zs = G["z"]
    z = zs[i] + zoff
    f = min(1.0, (zs[i] - zs[0]) / (zs[2] - zs[0]))
    ws0, ws1 = G["ws"]
    rw0, rw1 = G["rw"]
    if i <= 2:
        yF = ws0 + (ws1 - ws0) * f
        yR = rw0 + (rw1 - rw0) * f
    else:
        yF = ws1 + G["roof_round"][i - 3][0]
        yR = rw1 - G["roof_round"][i - 3][1]
    w = G["w"][i]
    rc = G["rc"] * (1.0 - 0.2 * f)
    a1 = yF + rc + 0.07
    b0, b1 = G["b"]
    c0 = G["c"][0] + (G["c"][1] - G["c"][0]) * f
    s5 = yR - rc - 0.02
    c0 = min(c0, s5 - 0.05)
    b1 = min(b1, c0 - 0.05)
    b0 = min(b0, b1 - 0.06)
    a1 = min(a1, b0 - 0.03)
    right = [("F1", (w * 0.5, yF + 0.035)), ("C1", (w - rc, yF + 0.07)), ("C2", (w - 0.29 * rc, yF + 0.07 + 0.71 * rc)),
             ("S1", (w, a1)), ("S2", (w, b0)), ("S3", (w, b1)), ("S4", (w, c0)), ("S5", (w, s5)),
             ("C3", (w - 0.29 * rc, yR - 0.05 - 0.71 * rc)), ("C4", (w - rc, yR - 0.05)), ("R1", (w * 0.5, yR - 0.025))]
    ring = [("F0", (0.0, yF, z))]
    ring += [(lab, (x, y, z)) for lab, (x, y) in right]
    ring.append(("R0", (0.0, yR, z)))
    ring += [("L" + lab, (-x, y, z)) for lab, (x, y) in reversed(right)]
    return ring


def greenhouse(G: dict, zoff: float, paint: str, broken: dict[str, str], *, glass: str = "window_grime",
               seed: int = 0, sag: float = 0.0):
    """broken: window name -> 'gone' | 'jagged'. Returns the greenhouse object (solidified)."""
    import random
    rr = random.Random(seed)
    bm = bmesh.new()
    rings = []
    labels = None
    for i in range(len(G["z"])):
        rl = _gh_ring(G, i, zoff)
        labels = [lab for lab, _ in rl]
        rings.append([bm.verts.new(p) for _, p in rl])
    n = len(labels)
    seg_face: dict[tuple[str, str], bmesh.types.BMFace] = {}
    for i in range(len(rings) - 1):
        for k in range(n):
            j = (k + 1) % n
            f = bm.faces.new((rings[i][k], rings[i][j], rings[i + 1][j], rings[i + 1][k]))
            if i == G.get("window_band", 1):
                seg_face[(labels[k], labels[j])] = f
    bm.faces.new(rings[-1])
    if sag > 0:
        ymid = (G["ws"][1] + G["rw"][1]) / 2
        half = (G["rw"][1] - G["ws"][1]) / 2 + 0.2
        for v in bm.verts:
            if v.co.z > G["z"][2] + zoff - 0.01:
                t = max(0.0, 1 - ((v.co.y - ymid) / half) ** 2)
                v.co.z -= sag * t
    glass_faces = {}
    for wname, segs in WINDOWS.items():
        faces = [seg_face[s] for s in segs if s in seg_face]
        if not faces:
            continue
        bmesh.ops.inset_region(bm, faces=faces, thickness=0.024, depth=-0.012, use_even_offset=True)
        glass_faces[wname] = faces
    for wname, faces in glass_faces.items():
        for f in faces:
            f.material_index = 1
    # Break windows.
    for wname, mode in broken.items():
        faces = [f for f in glass_faces.get(wname, []) if f.is_valid]
        if not faces:
            continue
        if mode == "gone":
            bmesh.ops.delete(bm, geom=faces, context="FACES")
            continue
        c = sum((f.calc_center_median() for f in faces), Vector()) / len(faces)
        size = max((v.co - c).length for f in faces for v in f.verts)
        # Ordered, de-duplicated edge list (a set of BMEdges iterates in memory order: not deterministic).
        seen, edges = set(), []
        for f in faces:
            for e in f.edges:
                if e not in seen:
                    seen.add(e)
                    edges.append(e)
        bmesh.ops.subdivide_edges(bm, edges=edges, cuts=2, use_grid_fill=True)
        region = [f for f in bm.faces if f.material_index == 1 and (f.calc_center_median() - c).length < size * 1.2]
        lobes = [(rr.uniform(0, math.tau), rr.uniform(0.1, 0.3), rr.randint(2, 5)) for _ in range(3)]
        kill = []
        for f in region:
            d = f.calc_center_median() - c
            a = math.atan2(d.z, d.x + d.y)
            k = 0.62 + sum(amp * math.sin(fr * a + ph) for ph, amp, fr in lobes)
            if d.length < size * k:
                kill.append(f)
        if kill:
            bmesh.ops.delete(bm, geom=kill, context="FACES")
    obj = _mesh_with_mats("greenhouse", bm, [paint, glass])
    K.solidify(obj, 0.014, offset=-1.0)
    return obj


# ============================================================================================
# Shared parts
# ============================================================================================

def wheel(ctx: K.Ctx, x: float, y: float, axle_z: float, S: dict, *, hubcap: bool, tyre: bool, flat: float,
          rim_mat: str = "paint_black") -> list:
    side = 1.0 if x > 0 else -1.0
    out = []
    w = S["tyre_w"]
    if tyre:
        t = P.tyre("tyre", S["r_out"], S["r_rim"] - 0.005, w, segs=16)
        K.place(t, (x, y, axle_z if flat <= 0 else S["r_out"]))
        if flat > 0:
            K.place(t, (0, 0, axle_z - S["r_out"]))
            P.flatten_tyre(t, axle_z, S["r_out"], amount=flat, bulge=0.022)
        ctx.add(t, "tyre_rubber", uv="cyl", uv_axis=0, uv_scale=1.0, smooth=50, patches=0.0, edge=0.2)
        out.append(t)
    rim = P.steel_rim("rim", S["r_rim"], w * 0.85, segs=14)
    if side > 0:
        K.place(rim, rot=(0, 0, 180))
    K.place(rim, (x, y, axle_z))
    ctx.add(rim, rim_mat, uv="cyl", uv_axis=0, uv_scale=1.0, smooth=40, patches=0.7, low=0.6, low_h=0.3)
    out.append(rim)
    if hubcap:
        h = P.hubcap("hubcap", S["r_rim"] * 0.95, segs=14)
        if side > 0:
            K.place(h, rot=(0, 0, 180))
        K.place(h, (x + side * w * 0.43, y, axle_z))
        ctx.add(h, "chrome_pitted", uv="planar", uv_axis=0, uv_scale=2.0, smooth=40, patches=0.5)
        out.append(h)
    return out


def wheel_well(ctx: K.Ctx, xo: float, y: float, z: float, R: float, depth: float, side: float, mat: str = "underbody"):
    """Inner fender liner: half-cylinder shell + inner wall, visible through the arch."""
    bm = bmesh.new()
    n = 9
    x0, x1 = xo - side * depth, xo
    outer = []
    inner = []
    for k in range(n + 1):
        a = math.pi * k / n
        yy, zz = y + R * math.cos(a), z + R * math.sin(a) * 0.95
        outer.append(bm.verts.new((x1, yy, zz)))
        inner.append(bm.verts.new((x0, yy, zz)))
    for k in range(n):
        if side > 0:
            bm.faces.new((inner[k], outer[k], outer[k + 1], inner[k + 1]))
        else:
            bm.faces.new((outer[k], inner[k], inner[k + 1], outer[k + 1]))
    c = bm.verts.new((x0, y, z - 0.05))
    for k in range(n):
        if side > 0:
            bm.faces.new((c, inner[k], inner[k + 1]))
        else:
            bm.faces.new((c, inner[k + 1], inner[k]))
    o = K._obj_raw("well", bm)
    ctx.add(o, mat, uv_scale=1.0, wear=0.0)
    return o


def bumper(ctx, pts, z: float, height: float, depth: float, mat: str, strip: bool = True, sag=None):
    prof = [(-depth * 0.4, -height / 2), (depth * 0.45, -height / 2), (depth * 0.6, -height * 0.3),
            (depth * 0.62, 0.0), (depth * 0.6, height * 0.3), (depth * 0.45, height / 2), (-depth * 0.4, height / 2)]
    path = [(x, y, z) for x, y in pts]
    b = K.sweep("bumper", path, prof)
    parts = [b]
    if strip:
        sp = [(-0.004, -0.022), (0.016, -0.02), (0.02, 0.0), (0.016, 0.02), (-0.004, 0.022)]
        s = K.sweep("strip", [(x, y, z + height * 0.05) for x, y in pts[1:-1]],
                    [(a + depth * 0.6, b2) for a, b2 in sp])
        parts.append(s)
    if sag is not None:
        for o in parts:
            sag(o)
    ctx.add(b, mat, uv_scale=1.0, smooth=50, patches=0.7, low=0.0)
    if strip:
        ctx.add(parts[1], "plastic_black", uv_scale=1.0, smooth=50, wear=0.3)
    return parts


def mirror(ctx, x: float, y: float, z: float, side: float, mat="plastic_black"):
    h = K.box("mirror", (0.07, 0.17, 0.11), center=(x + side * 0.07, y, z + 0.02), bevel=0.02, bevel_segs=1)
    st = K.box("stalk", (0.08, 0.04, 0.03), center=(x + side * 0.02, y, z))
    glass = K.box("mglass", (0.004, 0.14, 0.085), center=(x + side * 0.07, y + 0.088, z + 0.02))
    ctx.add(h, mat, uv_scale=1.0, smooth=40, wear=0.5)
    ctx.add(st, mat, uv_scale=1.0, wear=0.5)
    ctx.add(glass, "chrome_pitted", uv_scale=2.0, wear=0.2)


def seat(ctx, x: float, y: float, z: float, w: float, d: float, *, back_h=0.6, mat="car_upholstery", torn=0.0, recline=14.0):
    cush = K.box("cushion", (w, d, 0.13), center=(x, y, z + 0.065), bevel=0.03, bevel_segs=2)
    back = K.box("back", (w, 0.13, back_h), center=(0, 0, back_h / 2), bevel=0.03, bevel_segs=2)
    K.place(back, rot=(-recline, 0, 0))
    K.place(back, (x, y + d / 2 - 0.04, z + 0.08))
    ctx.add(cush, mat, uv_scale=1.0, smooth=40, patches=torn, edge=0.6)
    ctx.add(back, mat, uv_scale=1.0, smooth=40, patches=torn, edge=0.6)


def steering(ctx, x: float, y: float, z: float, mat="plastic_black"):
    ring = K.tube("wheel", [(math.cos(a) * 0.19, math.sin(a) * 0.19, 0.0) for a in [i * math.tau / 14 for i in range(14)]],
                  0.016, segs=5, closed=True)
    spoke = K.box("spoke", (0.36, 0.03, 0.012))
    hub = K.cyl("hub", 0.05, 0.05, segs=8)
    col = K.cyl("column", 0.03, 0.42, segs=6, center=(0, 0, -0.21))
    parts = [ring, spoke, hub, col]
    for o in parts:
        K.place(o, rot=(60, 0, 0))
        K.place(o, (x, y, z))
    ctx.add(K.merge_parts(parts, "steer"), mat, uv_scale=1.0, smooth=40, wear=0.4)


def lamp(ctx, center, size, lens: str, bezel: str = "chrome_pitted", rot=None):
    sx, sy, sz = size
    lb = K.box("lens", (sx, sy, sz), bevel=0.006)
    bz = K.box("bezel", (sx + 0.02, sy * 0.6, sz + 0.02), center=(0, sy * 0.3, 0), bevel=0.004)
    for o in (lb, bz):
        if rot:
            K.place(o, rot=rot)
        K.place(o, center)
    ctx.add(lb, lens, uv_scale=2.0, wear=0.3, patches=0.0)
    ctx.add(bz, bezel, uv_scale=2.0, wear=0.6)


SEDAN_LEN = 4.78


def seam_hook(S: dict, zoff: float, yscale: float = 1.0):
    """Post-AO: darkens door gaps (vertical strips on the body sides) and the hood/trunk cut lines."""
    seams = [s * yscale for s in S.get("seams", [])]
    cuts = [s * yscale for s in S.get("top_cuts", [])]
    zb = min(z for _, z in S["bot"]) + zoff + 0.03
    zt = S["gh"]["z"][0] + zoff - 0.02

    def fn(obj):
        def pred(c, n):
            if abs(n.x) > 0.55 and zb < c.z < zt:
                return any(abs(c.y - s) < 0.0045 for s in seams)
            if n.z > 0.6:
                return any(abs(c.y - s) < 0.0045 for s in cuts)
            return False
        K.darken_faces(obj, pred, 0.12)
    return fn


# ============================================================================================
# Sedan
# ============================================================================================

SEDAN = {
    "W": 0.9, "y_front": -2.375, "y_rear": 2.375, "rc_front": 0.14, "rc_rear": 0.12,
    "axles": (-1.425, 1.265), "arch_r": (0.385, 0.375), "track": 0.755,
    "r_out": 0.32, "r_rim": 0.178, "tyre_w": 0.2,
    "top": [(-2.375, 0.70), (-2.33, 0.785), (-2.2, 0.825), (-1.4, 0.875), (-0.8, 0.92), (-0.7, 0.95), (1.5, 0.95),
            (1.6, 0.985), (2.25, 0.975), (2.33, 0.93), (2.375, 0.84)],
    "crown": [(-2.375, 0.0), (-2.2, 0.022), (-0.8, 0.028), (-0.7, 0.0), (1.55, 0.0), (1.65, 0.018), (2.3, 0.012),
              (2.375, 0.0)],
    "bot": [(-2.375, 0.37), (-2.25, 0.29), (-2.0, 0.245), (2.05, 0.245), (2.3, 0.31), (2.375, 0.39)],
    "cabin": (-0.62, 1.47),
    "trunk": (1.63, 2.27),
    "seams": [-0.74, 0.43, 0.97],
    "top_cuts": [-0.78, 1.6],
    "gh": {"z": [0.95, 0.975, 1.315, 1.36, 1.385], "ws": (-0.74, 0.02), "rw": (1.56, 1.0),
           "w": [0.835, 0.83, 0.715, 0.68, 0.62], "b": (0.38, 0.47), "c": (0.98, 0.76), "rc": 0.12,
           "roof_round": [(0.06, 0.05), (0.16, 0.13)]},
}


def _open_trunk(ctx: K.Ctx, S: dict, zoff: float, body_mat: str, burnt: bool) -> None:
    """Looted trunk: deck opening (lower_body open_trunk), inward-facing tub, lid swung up on its
    front hinge following the deck crown, spare tyre left in the well."""
    t0, t1 = S["trunk"]
    z0 = _interp(S["top"], t0) + zoff
    wt = _half_width(S, (t0 + t1) / 2) - 0.1
    tub = K.box("trunk_tub", (2 * wt, t1 - t0, 0.46), center=(0, (t0 + t1) / 2, z0 - 0.23), cuts=(2, 1, 0))
    K.delete_faces(tub, lambda c, n: n.z > 0.9)
    bm = bmesh.new()
    bm.from_mesh(tub.data)
    bmesh.ops.reverse_faces(bm, faces=list(bm.faces))  # seen from inside
    K.write_bm(bm, tub)
    ctx.add(tub, "car_burnt" if burnt else "underbody", uv_scale=1.0, wear=0.0)
    nu, nv = 6, 4
    bm = bmesh.new()
    rows = []
    for j in range(nv + 1):
        y = t0 + (t1 - t0) * j / nv
        zt = _interp(S["top"], y) + zoff
        cr = _interp(S["crown"], y)
        w = _half_width(S, y) - 0.08
        rows.append([bm.verts.new((x, y, zt + cr * (1 - (x / (w + 0.08)) ** 2)))
                     for x in [-w + 2 * w * i / nu for i in range(nu + 1)]])
    for j in range(nv):
        for i in range(nu):
            bm.faces.new((rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]))
    lid = K._obj_raw("trunk_lid", bm)
    K.solidify(lid, 0.014, offset=-1.0)
    hinge = Vector((0.0, t0, z0 + _interp(S["crown"], t0)))
    K.place(lid, -hinge)
    K.place(lid, rot=(64 if not burnt else 38, 0, 0))
    K.place(lid, hinge)
    ctx.add(lid, body_mat, uv_scale=1.0, smooth=38, patches=0.5, noise_scale=2.8)
    if not burnt:
        spare = P.tyre("spare", 0.3, 0.17, 0.18, segs=14)
        K.place(spare, rot=(0, 90, 0))
        K.place(spare, (0.18, (t0 + t1) / 2 + 0.05, z0 - 0.46 + 0.09))
        ctx.add(spare, "tyre_rubber", uv="cyl", uv_axis=2, uv_scale=1.0, smooth=50, patches=0.0)


def _sedan(ctx: K.Ctx) -> None:
    S = SEDAN
    paint = ctx.param("paint", "car_paint_maroon")
    burnt = ctx.destroyed
    body_mat = "car_burnt" if burnt else paint
    flat = 0.0 if burnt else 0.45
    axle_z = S["r_rim"] + 0.012 if burnt else S["r_out"] - 0.07
    zoff = axle_z - S["r_out"]
    dr = ctx.drnd("damage")
    # --- lower shell -----------------------------------------------------------------------
    body, _st = lower_body(S, zoff, axle_z, open_trunk=ctx.worn)
    if ctx.worn:
        for (x, y, z, rad, d) in [(-0.9, -1.0, 0.62, 0.28, 0.045), (0.9, 0.75, 0.6, 0.3, 0.04), (0.9, -1.9, 0.75, 0.2, 0.03),
                                  (-0.9, 1.9, 0.7, 0.25, 0.05)]:
            K.dent(body, (x, y, z + zoff), rad, d * (1.6 if burnt else 1.0))
    if burnt:
        K.noise_disp(body, 0.012, scale=3.0, seed=dr.randint(0, 999))
    materials.assign_all(body, body_mat)
    ctx.add(body, None, uv_scale=1.0, smooth=38, patches=0.5, low=0.9, low_h=0.45 + zoff, noise_scale=2.8)
    if ctx.worn:
        _open_trunk(ctx, S, zoff, body_mat, burnt)
    # --- greenhouse --------------------------------------------------------------------------
    if burnt:
        broken = {k: "gone" for k in WINDOWS}
    elif ctx.worn:
        broken = {"front_l": "gone", "rear_r": "jagged", "rear": "jagged", "windshield": "jagged", "front_r": "jagged"}
    else:
        broken = {"rear_l": "jagged"}
    gh = greenhouse(S["gh"], zoff, body_mat, broken, seed=ctx.seed, sag=0.07 if burnt else 0.0)
    ctx.add(gh, None, uv_scale=1.0, smooth=35, patches=0.45, noise_scale=2.8)
    # --- interior ------------------------------------------------------------------------------
    im = "car_burnt" if burnt else "car_upholstery"
    dash = "car_burnt" if burnt else "plastic_black"
    floor = K.box("floor", (1.68, 2.1, 0.05), center=(0, 0.42, 0.3 + zoff))
    ctx.add(floor, dash, uv_scale=1.0, wear=0.0)
    dsh = K.prism("dash", [(-0.66, 0.0), (-0.42, 0.0), (-0.40, 0.3), (-0.62, 0.36)], 1.6, plane="YZ")
    K.place(dsh, (0, 0, 0.62 + zoff))
    ctx.add(dsh, dash, uv_scale=1.0, wear=0.3)
    if not burnt:
        steering(ctx, -0.38, -0.33, 0.9 + zoff)
    for sx in (-0.38, 0.38):
        seat(ctx, sx, 0.12, 0.36 + zoff, 0.52, 0.5, mat=im, torn=0.4 if ctx.worn else 0.0,
             back_h=0.42 if burnt else 0.6)
    seat(ctx, 0.0, 1.0, 0.36 + zoff, 1.42, 0.48, mat=im, torn=0.4 if ctx.worn else 0.0, back_h=0.4 if burnt else 0.55,
         recline=20)
    for s in (-1, 1):
        dp = K.box("door_panel", (0.03, 1.55, 0.45), center=(s * 0.83, 0.25, 0.68 + zoff))
        ctx.add(dp, im, uv_scale=1.0, wear=0.0)
    shelf = K.box("shelf", (1.5, 0.2, 0.03), center=(0, 1.42, 0.93 + zoff))
    ctx.add(shelf, dash, uv_scale=1.0, wear=0.0)
    # --- wheels + wells ----------------------------------------------------------------------
    for yc, R in zip(S["axles"], S["arch_r"]):
        for s in (-1, 1):
            wheel_well(ctx, s * (S["W"] - 0.035), yc, axle_z, R + 0.015, 0.3, s)
            hub = (not ctx.worn) and not (s > 0 and yc > 0)
            wheel(ctx, s * S["track"], yc, axle_z, S, hubcap=hub, tyre=not burnt, flat=flat,
                  rim_mat="car_rust" if burnt else "paint_black")
    under = K.box("under", (1.6, 3.9, 0.06), center=(0, 0.0, 0.27 + zoff))
    ctx.add(under, "underbody", uv_scale=1.0, wear=0.0)
    # --- bumpers --------------------------------------------------------------------------
    bmat = "car_rust" if burnt else "chrome_pitted"
    fpts = [(-0.86, -2.18), (-0.84, -2.33), (-0.62, -2.425), (0.0, -2.44), (0.62, -2.425), (0.84, -2.33), (0.86, -2.18)]
    rpts = [(0.86, 2.2), (0.84, 2.34), (0.62, 2.43), (0.0, 2.445), (-0.62, 2.43), (-0.84, 2.34), (-0.86, 2.2)]
    fsag = None
    if ctx.worn:
        def fsag(o, k=0.18 if burnt else 0.1):
            K.map_verts(o, lambda co: Vector((co.x, co.y, co.z - k * max(0.0, (co.x + 0.9) / 1.8) ** 2)))
    bumper(ctx, fpts, 0.43 + zoff, 0.17, 0.08, bmat, strip=not burnt, sag=fsag)
    bumper(ctx, rpts, 0.47 + zoff, 0.17, 0.08, bmat, strip=not burnt)
    # --- lamps / grille --------------------------------------------------------------------
    lens_c = "car_burnt" if burnt else "lens_clear"
    lens_a = "car_burnt" if burnt else "lens_amber"
    lens_r = "car_burnt" if burnt else "lens_red"
    fy = S["y_front"] - 0.004
    for s in (-1, 1):
        lamp(ctx, (s * 0.5, fy, 0.63 + zoff), (0.36, 0.03, 0.12), lens_c)
        lamp(ctx, (s * 0.79, fy + 0.07, 0.63 + zoff), (0.1, 0.03, 0.11), lens_a, rot=(0, 0, s * 52))
        lamp(ctx, (s * 0.52, S["y_rear"] + 0.004, 0.8 + zoff), (0.44, 0.03, 0.15), lens_r, rot=(0, 0, 180))
    gr = K.box("grille", (0.56, 0.04, 0.13), center=(0, fy, 0.63 + zoff), bevel=0.005)
    ctx.add(gr, "car_burnt" if burnt else "plastic_black", uv_scale=1.0, wear=0.2)
    for k in range(3):
        bar = K.box("gbar", (0.56, 0.012, 0.012), center=(0, fy - 0.022, 0.59 + k * 0.04 + zoff))
        ctx.add(bar, bmat, uv_scale=2.0, wear=0.6)
    plate = K.box("plate", (0.32, 0.02, 0.16), center=(0, S["y_rear"] + 0.002, 0.63 + zoff))
    ctx.add(plate, "car_burnt" if burnt else "plastic_black", uv_scale=1.0, wear=0.2)
    # --- mirrors, handles, wipers, antenna, exhaust -------------------------------------------
    trim = "car_burnt" if burnt else "plastic_black"
    for s in (-1, 1):
        if not (ctx.worn and s < 0) and not burnt:
            mirror(ctx, s * 0.86, -0.56, 1.0 + zoff, s, trim)
        for y in (0.28, 0.86):
            hd = K.box("handle", (0.016, 0.13, 0.028), center=(s * 0.913, y, 0.86 + zoff), bevel=0.004)
            ctx.add(hd, "car_rust" if burnt else "chrome_pitted", uv_scale=2.0, wear=0.6)
    if not burnt:
        # Rubber body-side mouldings along the doors (path reversed on the left so the profile faces out).
        mprof = [(-0.004, -0.02), (0.007, -0.018), (0.011, 0.0), (0.007, 0.018), (-0.004, 0.02)]
        for s in (-1, 1):
            path = [(s * 0.906, y, 0.6 + zoff) for y in (-0.99, -0.4, 0.3, 0.84)]
            mold = K.sweep("molding", path if s > 0 else list(reversed(path)), mprof)
            ctx.add(mold, "plastic_black", uv_scale=1.0, smooth=40, wear=0.4)
        for x0 in (-0.42, 0.18):
            wp = K.box("wiper", (0.5, 0.014, 0.01), center=(x0, -0.69, 0.968 + zoff))
            K.place(wp, (-x0, 0.69, -0.968 - zoff))
            K.place(wp, rot=(-28, 0, 4))
            K.place(wp, (x0, -0.69, 0.968 + zoff))
            ctx.add(wp, "plastic_black", uv_scale=1.0, wear=0.3)
        ant_tip = (0.7, -0.95, 1.55 + zoff) if ctx.clean else (0.98, -0.75, 1.15 + zoff)
        ant = K.tube("antenna", [(0.7, -0.9, 0.9 + zoff), ((0.7 + ant_tip[0]) / 2, -0.92, 1.2 + zoff), ant_tip], 0.003,
                     segs=4)
        ctx.add(ant, "chrome_pitted", uv_scale=1.0, wear=0.3)
    ex = K.tube("exhaust", [(0.45, 1.6, 0.28 + zoff), (0.47, 2.2, 0.27 + zoff), (0.48, 2.46, 0.29 + zoff)], 0.025, segs=6)
    ctx.add(ex, "car_rust", uv_scale=1.0, smooth=40)
    # --- collision --------------------------------------------------------------------------
    ctx.col_box((-0.92, -2.45, 0.0), (0.92, 2.45, 0.98 + zoff))
    ctx.col_hull([(sx * 0.82, y, 0.95 + zoff) for sx in (-1, 1) for y in (-0.75, 1.56)] +
                 [(sx * 0.66, y, 1.37 + zoff) for sx in (-1, 1) for y in (0.05, 0.98)])
    # The spec is laid out at 4.75 m body length; scale to a 4.75 m overall length incl. bumpers.
    ys = SEDAN_LEN / 4.97
    for o in ctx.parts + ctx.cols:
        K.map_verts(o, lambda co: Vector((co.x, co.y * ys, co.z)))
    ctx.post.append(seam_hook(S, zoff, ys))


# ============================================================================================
# Pickup
# ============================================================================================

PICKUP = {
    "W": 0.975, "y_front": -2.63, "y_rear": 0.6, "rc_front": 0.1, "rc_rear": 0.02, "taper": 0.0,
    "axles": (-1.73, 1.62), "arch_r": (0.43, 0.43), "track": 0.82,
    "r_out": 0.37, "r_rim": 0.192, "tyre_w": 0.235,
    "top": [(-2.63, 0.98), (-2.6, 1.1), (-2.5, 1.13), (-1.0, 1.15), (-0.92, 1.18), (0.6, 1.18)],
    "crown": [(-2.63, 0.0), (-2.5, 0.015), (-1.0, 0.02), (-0.92, 0.0), (0.6, 0.0)],
    "bot": [(-2.63, 0.5), (-2.5, 0.42), (-2.2, 0.38), (0.6, 0.38)],
    "cabin": (-0.86, 0.5),
    "seams": [-0.95, 0.42],
    "top_cuts": [-0.97],
    "gh": {"z": [1.18, 1.2, 1.74, 1.79, 1.81], "ws": (-0.96, -0.34), "rw": (0.56, 0.5),
           "w": [0.9, 0.895, 0.83, 0.8, 0.76], "b": (2.0, 2.0), "c": (2.0, 2.0), "rc": 0.1,
           "roof_round": [(0.05, 0.03), (0.12, 0.06)]},
}


def _pickup_bed(ctx, S, zoff, axle_z, mat, *, tailgate_down: bool, burnt: bool, dr):
    y0, y1 = 0.66, 2.6
    W = S["W"]
    wall_t = 0.05
    zf = 0.82 + zoff
    zt = 1.2 + zoff
    yc, R = S["axles"][1], S["arch_r"][1]
    parts = []
    for s in (-1, 1):
        # Outer side panel with the rear wheel arch: ring-like strip built as a prism outline in YZ.
        pts = [(y0, zf - 0.32)]
        for k in range(9):
            a = math.pi - math.pi * k / 8
            pts.append((yc + (R + 0.02) * math.cos(a), axle_z + (R + 0.02) * math.sin(a)))
        pts[1] = (yc - R - 0.02, zf - 0.32)
        pts[-1] = (yc + R + 0.02, zf - 0.32)
        pts += [(y1, zf - 0.32), (y1, zt), (y0, zt)]
        side = K.prism("bedside", [(p[0], p[1]) for p in pts], wall_t, plane="YZ")
        K.place(side, (s * (W - wall_t / 2), 0, 0))
        parts.append(side)
        rail = K.box("rail", (0.09, y1 - y0, 0.035), center=(s * (W - 0.045), (y0 + y1) / 2, zt + 0.0175), bevel=0.008)
        parts.append(rail)
        wh = K.box("wheelhouse", (0.26, 2 * R + 0.06, 0.32), center=(s * (W - 0.18), yc, zf + 0.08), bevel=0.04)
        parts.append(wh)
    floor = K.box("bedfloor", (2 * W - 0.1, y1 - y0, 0.04), center=(0, (y0 + y1) / 2, zf), cuts=(4, 0, 0))
    front = K.box("bedfront", (2 * W, wall_t, zt - zf + 0.32), center=(0, y0 + wall_t / 2, (zt + zf - 0.32) / 2))
    parts += [floor, front]
    tg = K.box("tailgate", (2 * W - 0.02, 0.06, zt - zf + 0.04), center=(0, 0, (zt - zf + 0.04) / 2), bevel=0.01,
               cuts=(3, 0, 1))
    tgh = K.box("tg_handle", (0.2, 0.025, 0.05), center=(0, 0.035, zt - zf - 0.06), bevel=0.006)
    for o in (tg, tgh):
        if tailgate_down:
            K.place(o, rot=(95, 0, 0))
            K.place(o, (0, y1 - 0.03, zf - 0.04))
        else:
            K.place(o, (0, y1 - 0.03, zf - 0.02))
    parts.append(tg)
    for o in parts:
        ctx.add(o, mat, uv_scale=1.0, smooth=35, patches=0.65, low=0.8, low_h=0.5 + zoff)
    ctx.add(tgh, "car_rust" if burnt else "chrome_pitted", uv_scale=2.0, wear=0.6)
    # Junk in the bed: a tire and a couple of planks (story: hauling salvage).
    if not burnt:
        t = P.tyre("bedtyre", 0.33, 0.19, 0.21, segs=14)
        K.place(t, rot=(0, 90, 0))
        K.place(t, (-0.35, 1.9, zf + 0.12))
        ctx.add(t, "tyre_rubber", uv="cyl", uv_axis=2, uv_scale=1.0, smooth=50, patches=0.0)
        for k in range(2):
            pl = P.plank("bedplank", 1.6, 0.14, 0.025, cuts=2)
            ctx.add(pl, "wood_weathered", long_axis=0, patches=0.3,
                    at=((0.3 + k * 0.16, 1.55, zf + 0.035 + k * 0.026), (0, k * 3.0, 90 + dr.uniform(-6, 6))))


def _pickup(ctx: K.Ctx) -> None:
    S = PICKUP
    paint = ctx.param("paint", "car_paint_blue")
    burnt = ctx.destroyed
    body_mat = "car_burnt" if burnt else paint
    flat = 0.0 if burnt else 0.4
    axle_z = S["r_rim"] + 0.012 if burnt else S["r_out"] - 0.075
    zoff = axle_z - S["r_out"]
    dr = ctx.drnd("damage")
    body, _ = lower_body(S, zoff, axle_z)
    if ctx.worn:
        for (x, y, z, rad, d) in [(0.97, -1.2, 0.85, 0.3, 0.05), (-0.97, -2.2, 0.8, 0.22, 0.035), (0.97, 0.1, 0.7, 0.25, 0.04)]:
            K.dent(body, (x, y, z + zoff), rad, d * (1.5 if burnt else 1.0))
    if burnt:
        K.noise_disp(body, 0.012, scale=3.0, seed=dr.randint(0, 999))
    materials.assign_all(body, body_mat)
    ctx.add(body, None, uv_scale=1.0, smooth=38, patches=0.5, low=0.9, low_h=0.55 + zoff, noise_scale=2.8)
    # Cab greenhouse: regular cab, no B pillar or rear side windows.
    G = dict(S["gh"])
    if burnt:
        broken = {k: "gone" for k in WINDOWS}
    elif ctx.worn:
        broken = {"windshield": "jagged", "front_r": "gone", "rear": "jagged"}
    else:
        broken = {"front_l": "jagged"}
    gh = greenhouse_cab(G, zoff, body_mat, broken, seed=ctx.seed, sag=0.06 if burnt else 0.0)
    ctx.add(gh, None, uv_scale=1.0, smooth=35, patches=0.45, noise_scale=2.8)
    # Interior: bench seat, dash, wheel.
    im = "car_burnt" if burnt else "car_upholstery"
    dash = "car_burnt" if burnt else "plastic_black"
    floor = K.box("floor", (1.84, 1.3, 0.05), center=(0, -0.2, 0.45 + zoff))
    ctx.add(floor, dash, uv_scale=1.0, wear=0.0)
    dsh = K.prism("dash", [(-0.86, 0.0), (-0.6, 0.0), (-0.58, 0.32), (-0.82, 0.38)], 1.8, plane="YZ")
    K.place(dsh, (0, 0, 0.82 + zoff))
    ctx.add(dsh, dash, uv_scale=1.0, wear=0.3)
    if not burnt:
        steering(ctx, -0.42, -0.5, 1.1 + zoff)
    seat(ctx, 0.0, 0.12, 0.52 + zoff, 1.65, 0.5, mat=im, torn=0.4 if ctx.worn else 0.0, back_h=0.45 if burnt else 0.6,
         recline=10)
    for s in (-1, 1):
        dp = K.box("door_panel", (0.03, 1.1, 0.5), center=(s * 0.91, -0.25, 0.92 + zoff))
        ctx.add(dp, im, uv_scale=1.0, wear=0.0)
    _pickup_bed(ctx, S, zoff, axle_z, body_mat, tailgate_down=ctx.worn, burnt=burnt, dr=dr)
    # Wheels, wells, frame.
    for i, (yc, R) in enumerate(zip(S["axles"], S["arch_r"])):
        for s in (-1, 1):
            if i == 0:
                wheel_well(ctx, s * (S["W"] - 0.035), yc, axle_z, R + 0.015, 0.32, s)
            hub = (not ctx.worn) and not (s < 0 and i == 0)
            # White steel wheels under the hubcaps; on the rotted wreck they have rusted through (a
            # clean white disc in a rust-brown truck read as a sticker).
            wheel(ctx, s * S["track"], yc, axle_z, S, hubcap=hub, tyre=not burnt, flat=flat,
                  rim_mat="car_rust" if burnt or ctx.worn else "paint_white")
    for s in (-1, 1):
        rail = K.box("frame", (0.08, 5.0, 0.16), center=(s * 0.5, 0.0, 0.45 + zoff))
        ctx.add(rail, "underbody", uv_scale=1.0, wear=0.0)
    # Front: big chrome grille with quad lamps, chrome bumper; rear step bumper.
    bmat = "car_rust" if burnt else "chrome_pitted"
    fy = S["y_front"] - 0.004
    gr = K.box("grille", (1.1, 0.05, 0.36), center=(0, fy, 0.84 + zoff), bevel=0.01)
    ctx.add(gr, "car_burnt" if burnt else "plastic_black", uv_scale=1.0, wear=0.2)
    for k in range(4):
        bar = K.box("gbar", (1.08, 0.015, 0.02), center=(0, fy - 0.03, 0.72 + k * 0.08 + zoff))
        ctx.add(bar, bmat, uv_scale=2.0, wear=0.6)
    for k in range(5):
        bar = K.box("gvbar", (0.02, 0.015, 0.34), center=(-0.44 + k * 0.22, fy - 0.03, 0.84 + zoff))
        ctx.add(bar, bmat, uv_scale=2.0, wear=0.6)
    lens_c = "car_burnt" if burnt else "lens_clear"
    lens_a = "car_burnt" if burnt else "lens_amber"
    lens_r = "car_burnt" if burnt else "lens_red"
    for s in (-1, 1):
        for k in range(2):
            lamp(ctx, (s * (0.62 + k * 0.17), fy, 0.9 + zoff), (0.15, 0.03, 0.11), lens_c)
        lamp(ctx, (s * 0.7, fy, 0.74 + zoff), (0.3, 0.03, 0.06), lens_a)
        lamp(ctx, (s * (S["W"] - 0.03), 2.58, 1.0 + zoff), (0.05, 0.04, 0.3), lens_r)
    fpts = [(-1.0, -2.45), (-0.98, -2.66), (-0.7, -2.72), (0.0, -2.73), (0.7, -2.72), (0.98, -2.66), (1.0, -2.45)]
    fsag = None
    if ctx.worn:
        def fsag(o, k=0.16 if burnt else 0.08):
            K.map_verts(o, lambda co: Vector((co.x, co.y, co.z - k * max(0.0, (1.0 - co.x) / 2.0) ** 2)))
    bumper(ctx, fpts, 0.56 + zoff, 0.2, 0.1, bmat, strip=False, sag=fsag)
    rb = K.box("rbumper", (2.0, 0.16, 0.18), center=(0, 2.7, 0.6 + zoff), bevel=0.02)
    ctx.add(rb, bmat, uv_scale=1.0, smooth=40, patches=0.7)
    trim = "car_burnt" if burnt else "plastic_black"
    for s in (-1, 1):
        if not burnt and not (ctx.worn and s > 0):
            mirror(ctx, s * 0.94, -0.82, 1.28 + zoff, s, trim)
        hd = K.box("handle", (0.016, 0.14, 0.03), center=(s * 0.985, 0.25, 1.08 + zoff), bevel=0.004)
        ctx.add(hd, "car_rust" if burnt else "chrome_pitted", uv_scale=2.0, wear=0.6)
    if not burnt:
        for x0 in (-0.45, 0.2):
            wp = K.box("wiper", (0.52, 0.014, 0.01), center=(0, 0, 0))
            K.place(wp, rot=(-34, 0, 4))
            K.place(wp, (x0, -0.92, 1.2 + zoff))
            ctx.add(wp, "plastic_black", uv_scale=1.0, wear=0.3)
    ctx.post.append(seam_hook(S, zoff))
    ctx.col_box((-1.0, -2.75, 0.0), (1.0, 2.75, 1.2 + zoff))
    ctx.col_hull([(sx * 0.9, y, 1.18 + zoff) for sx in (-1, 1) for y in (-0.96, 0.56)] +
                 [(sx * 0.78, y, 1.8 + zoff) for sx in (-1, 1) for y in (-0.3, 0.5)])


def greenhouse_cab(G: dict, zoff: float, paint: str, broken: dict[str, str], *, seed: int, sag: float):
    """Regular-cab variant: side glass runs from the A pillar to the cab back (no B/C pillar)."""
    G = dict(G)
    G["b"] = (0.42, 0.43)
    G["c"] = (0.44, 0.44)
    return greenhouse(G, zoff, paint, {("front_r" if k == "front_r" else k): v for k, v in broken.items()}, seed=seed,
                      sag=sag)


BUILDERS = {"car_sedan_wreck": _sedan, "pickup_wreck": _pickup}


def build(params: dict, outputs: list[str]) -> None:
    K.run(params, outputs, BUILDERS)
