"""Reusable part builders for the exterior props family. They return raw Objects (identity
transform, metres, built around the origin) that callers register with ``ctx.add()``.
Conventions: long parts are built along X; wheels/tyres spin around X; heights along Z."""
from __future__ import annotations

import math
import random

import bmesh
from mathutils import Matrix, Vector

from . import props_ext_kit as K


# --------------------------------------------------------------------------------------------
# Lumber
# --------------------------------------------------------------------------------------------

def plank(name: str, L: float, W: float, T: float, *, bevel: float = 0.003, cuts: int = 0,
          bow: float = 0.0, cup: float = 0.0, twist: float = 0.0) -> object:
    """Board along X centred at the origin (width Y, thickness Z). bow: mid-length sag (m);
    cup: across-width curl (m); twist: end rotation (deg). Needs cuts > 0 to bend smoothly."""
    o = K.box(name, (L, W, T), bevel=bevel, cuts=(cuts, 1 if cup else 0, 0))
    if bow or cup or twist:
        half = L / 2

        def f(co: Vector) -> Vector:
            t = co.x / half
            co.z -= bow * (1 - t * t)
            co.z += cup * (co.y / (W / 2)) ** 2
            if twist:
                a = math.radians(twist) * t
                y, z = co.y, co.z
                co.y, co.z = y * math.cos(a) - z * math.sin(a), y * math.sin(a) + z * math.cos(a)
            return co
        K.map_verts(o, f)
    return o


def break_end(obj, x: float, r: random.Random, *, side: int = 1, depth: float = 0.06, axis: int = 0) -> None:
    """Splintered break: cuts the part at `x` along `axis` with two tilted planes (V-shaped jag).
    side=+1 removes everything beyond +x, -1 beyond -x."""
    no = Vector((0, 0, 0))
    no[axis] = side
    tilt_axes = [i for i in range(3) if i != axis]
    vs = [v.co for v in obj.data.vertices]
    center = Vector(tuple((min(v[i] for v in vs) + max(v[i] for v in vs)) / 2 for i in range(3)))
    for k in range(2):
        n = no.copy()
        n[tilt_axes[0]] = r.uniform(-0.9, 0.9)
        n[tilt_axes[1]] = r.uniform(-0.4, 0.4)
        co = center.copy()  # plane anchored on the part, not the world origin
        co[axis] = x + side * r.uniform(0.0, depth)
        K.cut_plane(obj, co, n.normalized(), keep="below")


def log_split(name: str, L: float, R: float, r: random.Random, *, kind: str = "half", segs: int = 8) -> object:
    """Firewood piece along X: 'round' (whole log), 'half' or 'quarter' split (flat split faces)."""
    if kind == "round":
        return K.cyl(name, R, L, segs=segs, axis="X")
    arc = math.pi if kind == "half" else math.pi / 2
    a0 = r.uniform(0, math.tau)
    pts = [(0.0, 0.0)] if kind == "quarter" else []
    n = segs // 2 + 1
    for i in range(n):
        a = a0 + arc * i / (n - 1)
        rr = R * r.uniform(0.92, 1.04)
        pts.append((rr * math.cos(a), rr * math.sin(a)))
    o = K.prism(name, [(p[0], p[1]) for p in pts], L, plane="YZ")
    return o


# --------------------------------------------------------------------------------------------
# Wheels
# --------------------------------------------------------------------------------------------

def tyre(name: str, r_out: float, r_rim: float, width: float, *, segs: int = 16, tread: bool = False) -> object:
    """Tyre around the X axis, centred at the origin. Open towards the rim (rim part closes it)."""
    w = width / 2
    side = r_out - r_rim
    prof = [(r_rim, -w * 0.86), (r_rim + side * 0.3, -w * 0.98), (r_rim + side * 0.72, -w),
            (r_out - side * 0.08, -w * 0.9), (r_out, -w * 0.62), (r_out, 0.0), (r_out, w * 0.62),
            (r_out - side * 0.08, w * 0.9), (r_rim + side * 0.72, w), (r_rim + side * 0.3, w * 0.98), (r_rim, w * 0.86)]
    o = K.lathe(name, prof, segs=segs, cap_bottom=False, cap_top=False)
    K.place(o, rot=(0, 90, 0))
    return o


def flatten_tyre(obj, axle_z: float, r_out: float, *, amount: float = 0.35, bulge: float = 0.025,
                 ground: float = 0.0) -> None:
    """Deflated tyre: the contact patch flattens and the lower sidewalls bulge out (axis = X).
    amount = fraction of the sidewall height lost at the bottom."""
    lim = axle_z - r_out * (1.0 - amount)
    lowest = min(v.co.z for v in obj.data.vertices)
    k = (lim - ground) / max(1e-6, lim - lowest)  # maps the undeflected contact point onto the floor
    cx = sum(v.co.x for v in obj.data.vertices) / max(1, len(obj.data.vertices))
    for v in obj.data.vertices:
        if v.co.z < lim:
            t = (lim - v.co.z) / max(1e-6, lim - lowest)
            v.co.z = lim - (lim - v.co.z) * k
            sx = 1.0 if v.co.x >= cx else -1.0
            v.co.x += sx * bulge * min(1.0, t * 1.5)
    obj.data.update()


def steel_rim(name: str, r: float, width: float, *, segs: int = 16, dish: float = 0.03) -> object:
    """Steel wheel (barrel + dished face) around X, centred at the origin; face towards -X."""
    w = width / 2
    prof = [(0.0, -w + dish * 1.6), (r * 0.25, -w + dish * 1.5), (r * 0.3, -w + dish), (r * 0.62, -w + dish * 0.9),
            (r * 0.7, -w + dish * 0.3), (r * 0.9, -w + dish * 0.25), (r * 0.98, -w), (r * 1.02, -w - 0.006),
            (r * 0.97, -w + 0.01), (r * 0.95, w - 0.01), (r * 1.02, w + 0.006), (r * 0.9, w * 0.8), (0.0, w * 0.6)]
    o = K.lathe(name, prof, segs=segs, cap_bottom=False, cap_top=False)
    K.place(o, rot=(0, -90, 0))
    return o


def hubcap(name: str, r: float, *, segs: int = 16) -> object:
    prof = [(0.0, 0.035), (r * 0.25, 0.034), (r * 0.6, 0.026), (r * 0.9, 0.012), (r, 0.0), (r * 0.97, -0.005)]
    o = K.lathe(name, prof, segs=segs, cap_bottom=False, cap_top=False)
    K.place(o, rot=(0, -90, 0))
    return o


# --------------------------------------------------------------------------------------------
# Small containers
# --------------------------------------------------------------------------------------------

def can_profile(h: float = 0.122, r: float = 0.033) -> list[tuple[float, float]]:
    return [(0.0, 0.004), (r * 0.72, 0.0), (r * 0.95, 0.006), (r, 0.016), (r, h - 0.016), (r * 0.82, h - 0.004),
            (r * 0.8, h), (0.0, h - 0.003)]


def can(name: str, r: random.Random, *, crushed: float = 0.0, h: float = 0.122, rad: float = 0.033,
        segs: int = 10) -> object:
    o = K.lathe(name, can_profile(h, rad), segs=segs)
    if crushed > 0:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) > 0.05],
                                  cuts=4, use_grid_fill=False)
        K.write_bm(bm, o)
        k = 1.0 - 0.55 * crushed
        K.map_verts(o, lambda co: Vector((co.x * (1 + crushed * 0.25), co.y * (1 - crushed * 0.3), co.z * k)))
        K.crumple(o, 0.012 * crushed, scale=40.0, seed=r.randint(0, 9999))
    return o


def bottle(name: str, r: random.Random, *, broken: bool = False, kind: str = "beer", segs: int = 10) -> object:
    if kind == "beer":
        prof = [(0.0, 0.002), (0.027, 0.0), (0.03, 0.01), (0.03, 0.15), (0.026, 0.168), (0.014, 0.19), (0.0125, 0.225),
                (0.0145, 0.229), (0.012, 0.233), (0.0, 0.233)]
    else:  # liquor flask-ish round bottle
        prof = [(0.0, 0.002), (0.036, 0.0), (0.04, 0.012), (0.04, 0.19), (0.03, 0.215), (0.015, 0.23), (0.014, 0.27),
                (0.016, 0.274), (0.0, 0.274)]
    o = K.lathe(name, prof, segs=segs)
    if broken:
        z = r.uniform(0.07, 0.14)
        n = Vector((r.uniform(-0.6, 0.6), r.uniform(-0.6, 0.6), 1.0)).normalized()
        K.cut_plane(o, (0, 0, z), n, keep="below", fill=False)
        K.solidify(o, 0.003)
    return o


def bucket(name: str, *, top_r: float = 0.155, bot_r: float = 0.13, h: float = 0.33, segs: int = 16,
           wall: float = 0.004) -> object:
    prof = [(0.0, 0.0), (bot_r, 0.0), (bot_r + 0.003, 0.012), (top_r, h - 0.02), (top_r + 0.008, h - 0.012),
            (top_r + 0.008, h), (top_r - wall, h), (top_r - wall - 0.003, h - 0.02), (bot_r - wall, 0.012 + wall),
            (0.0, 0.012 + wall)]
    return K.lathe(name, prof, segs=segs, cap_bottom=False, cap_top=False)


# --------------------------------------------------------------------------------------------
# Soft goods
# --------------------------------------------------------------------------------------------

def trash_bag_mesh(name: str, r: random.Random, *, size=(0.5, 0.45, 0.62), tied: bool = True,
                   slump: float = 0.3, segs: int = 16, open_top: bool = False) -> object:
    """Full garbage bag: fat lumpy body sagging on the ground, shoulders gathered into a short
    twisted neck with two knot ears (open_top: neck missing — burst/untied bag)."""
    sx, sy, sz = size
    rx = 0.5
    prof = [(0.0, 0.0), (0.36 * rx, 0.004), (0.46 * rx, 0.025), (0.53 * rx, 0.08), (0.56 * rx, 0.18),
            (0.56 * rx, 0.3), (0.545 * rx, 0.42), (0.5 * rx, 0.53), (0.4 * rx, 0.62), (0.24 * rx, 0.69),
            (0.1 * rx, 0.74), (0.045 * rx, 0.78)]
    if tied:
        prof += [(0.05 * rx, 0.83), (0.06 * rx, 0.87), (0.0, 0.875)]
    elif not open_top:
        prof += [(0.0, 0.775)]
    o = K.lathe(name, [(rr * 1.8, z) for rr, z in prof], segs=segs, cap_bottom=False, cap_top=False)
    seed = r.randint(0, 99999)
    lean = Vector((r.uniform(-1, 1), r.uniform(-1, 1), 0)) * 0.06

    def shape(co: Vector) -> Vector:
        zt = co.z / 0.875
        # Slump: contents settle, base spreads, body leans a little.
        k = 1.0 + slump * 0.3 * max(0.0, 1.0 - zt * 1.6)
        co.x = co.x * sx * k + lean.x * zt * sx
        co.y = co.y * sy * k + lean.y * zt * sy
        co.z = co.z * sz
        return co
    K.map_verts(o, shape)
    # Lumpy contents (boxes, bottles) push the film out; mask keeps the neck/knot tidy.
    body_top = 0.62 * sz
    K.noise_disp(o, 0.075 * max(sx, sy), scale=2.6 / max(sx, sy), seed=seed, octaves=2,
                 mask=lambda co: max(0.0, 1.0 - max(0.0, co.z - body_top) / (0.15 * sz)) * min(1.0, co.z / 0.05 + 0.2))
    for k in range(3):
        a = r.uniform(0, math.tau)
        z = r.uniform(0.2, 0.5) * sz
        K.dent(o, (math.cos(a) * sx * 0.55, math.sin(a) * sy * 0.55, z), r.uniform(0.1, 0.18), -r.uniform(0.015, 0.03))
    K.crumple(o, 0.008, scale=18.0, seed=seed + 1)
    K.drop_to_ground(o)
    if tied:
        top = max(v.co.z for v in o.data.vertices)
        tip = Vector((0, 0, 0))
        n = 0
        for v in o.data.vertices:
            if v.co.z > top - 0.03:
                tip += v.co
                n += 1
        tip /= max(1, n)
        ears = []
        for k in range(2):
            a = r.uniform(0, math.tau) + k * math.pi * r.uniform(0.7, 1.0)
            e = K.blob(f"{name}_ear{k}", 0.05, subdiv=2 if segs >= 14 else 1, scale=(1.5, 0.35, 0.8), rough=0.2,
                       seed=seed + k)
            K.place(e, (0.045, 0, 0.0), (0, -r.uniform(20, 55), 0))
            K.place(e, tip + Vector((0, 0, -0.012)), (0, 0, math.degrees(a)))
            ears.append(e)
        o = K.merge_parts([o] + ears, name)
    return o


GARMENTS = {
    # name: (width, length, inside(u, v) on the unit square; v = 0 hem .. 1 collar/waist)
    "tee": (0.95, 0.72, lambda u, v: (0.22 < u < 0.78 and v < 0.86) or (v > 0.62 and v < 0.86 and 0.02 < u < 0.98)
            or (0.4 < u < 0.6 and v >= 0.86 and v < 0.9)),
    "shirt": (1.25, 0.78, lambda u, v: (0.3 < u < 0.7 and v < 0.9) or (0.68 < v < 0.86)),
    "sweater": (1.35, 0.7, lambda u, v: (0.28 < u < 0.72 and v < 0.92) or (0.7 < v < 0.9)),
    "jeans": (0.48, 1.02, lambda u, v: (v > 0.68 and 0.04 < u < 0.96) or (0.05 < u < 0.47) or (0.53 < u < 0.95)),
}


def garment(name: str, kind: str, r: random.Random, *, nx: int = 12, ny: int = 12, fold: bool = True,
            folds: float = 0.04, thickness: float = 0.005) -> object:
    """Garment lying on the floor (T-shirt, flannel shirt with sleeves, sweater, jeans): grid cut
    to the garment outline and given thickness while flat, then optionally folded over once (a
    180 deg turn about a crease cut into the mesh) and crumpled. UVs set flat first."""
    w, h, inside = GARMENTS[kind]
    o = K.grid(name, w, h, nx, ny)
    K.uv_planar(o, 2, scale=1.0)
    K.delete_faces(o, lambda c, n: not inside(c.x / w + 0.5, c.y / h + 0.5))
    K.solidify(o, thickness, offset=-1.0, even=False)
    seed = r.randint(0, 99999)
    if fold:
        a = r.uniform(0, math.pi)
        nrm = Vector((math.cos(a), math.sin(a), 0.0))
        off = r.uniform(0.05, 0.22) * (w if abs(nrm.x) > 0.5 else h) * 0.5
        K.bisect(o, nrm * off, nrm)

        def fold_fn(co: Vector) -> Vector:
            s = co.dot(nrm) - off
            if s <= 1e-5:
                return co
            flat = co - nrm * (2 * s)
            return Vector((flat.x, flat.y, -co.z + 0.006 + 0.004 * min(1.0, s / 0.1)))
        K.map_verts(o, fold_fn)
    K.noise_disp(o, folds, scale=5.0, seed=seed, along_normal=False)
    K.crumple(o, 0.012, scale=12.0, seed=seed + 1)
    return o


def book(name: str, r: random.Random, *, w: float = 0.15, h: float = 0.22, t: float = 0.03,
         opened: float = 0.0) -> tuple[object, object]:
    """Returns (covers, pages) lying flat (XY), spine along Y at x = -w/2. opened in degrees
    (0 closed; ~170 splayed open face-down)."""
    cover_t = 0.003
    if opened <= 1.0:
        covers = K.box(f"{name}_cov", (w, h, t), center=(0, 0, t / 2), bevel=0.002)
        pages = K.box(f"{name}_pg", (w - 0.006, h - 0.008, t - cover_t * 2), center=(0.004, 0, t / 2))
        return covers, pages
    a = math.radians(opened) / 2
    parts_c, parts_p = [], []
    for s in (-1, 1):
        c = K.box(f"{name}_c{s}", (w, h, cover_t), center=(w / 2, 0, cover_t / 2))
        p = K.box(f"{name}_p{s}", (w - 0.008, h - 0.008, t / 2 - cover_t), center=(w / 2 - 0.002, 0, cover_t + (t / 2 - cover_t) / 2))
        for o in (c, p):
            K.place(o, rot=(0, -s * math.degrees(math.pi / 2 - a) * 1.0, 0))
            if s < 0:
                K.place(o, rot=(0, 0, 180))
        parts_c.append(c)
        parts_p.append(p)
    covers = K.merge_parts(parts_c, f"{name}_cov")
    pages = K.merge_parts(parts_p, f"{name}_pg")
    return covers, pages


# --------------------------------------------------------------------------------------------
# Rubble
# --------------------------------------------------------------------------------------------

def rubble_heap(r: random.Random, n: int, extent=(0.8, 0.6), height: float = 0.4, size=(0.05, 0.22),
                flat: float = 0.6, prefix: str = "rb") -> list[object]:
    """Chunks stacked into a rough mound (bigger pieces low & central)."""
    out = []
    ex, ey = extent
    for i in range(n):
        rr = math.sqrt(r.random())
        a = r.uniform(0, math.tau)
        x, y = math.cos(a) * rr * ex, math.sin(a) * rr * ey
        s = r.uniform(*size) * (1.2 - 0.6 * rr)
        mound = height * (1.0 - rr * rr) * r.uniform(0.6, 1.0)
        c = K.chunk(f"{prefix}{i}", s, r, n=r.randint(8, 14), flat=flat * r.uniform(0.7, 1.3), elong=r.uniform(0.8, 1.8))
        K.place(c, (x, y, max(s * flat * 0.25, mound)), (r.uniform(-25, 25), r.uniform(-25, 25), r.uniform(0, 360)))
        out.append(c)
    return out


def mat_rot(deg_z: float) -> Matrix:
    return Matrix.Rotation(math.radians(deg_z), 4, "Z")


# --------------------------------------------------------------------------------------------
# Registered helpers shared by several generators (they call ctx.add)
# --------------------------------------------------------------------------------------------

def cardboard_shell(name: str, L: float, W: float, H: float, cuts=(4, 3, 3)) -> object:
    o = K.box(name, (L, W, H), center=(0, 0, H / 2), bevel=0.003, cuts=cuts)
    return o


def box_bulge(o, L: float, W: float, H: float, amount: float = 0.008) -> None:
    def f(co: Vector) -> Vector:
        zt = co.z / H * 2 - 1
        fz = max(0.0, 1 - zt * zt)
        if abs(co.x) > L / 2 - 0.006:
            co.x += math.copysign(amount * fz * max(0.0, 1 - (2 * co.y / W) ** 2), co.x)
        if abs(co.y) > W / 2 - 0.006:
            co.y += math.copysign(amount * fz * max(0.0, 1 - (2 * co.x / L) ** 2), co.y)
        return co
    K.map_verts(o, f)


def paper_wad(name: str, r, size: float = 0.05) -> object:
    return K.blob(name, size, subdiv=1, scale=(1.0, r.uniform(0.7, 1.0), r.uniform(0.6, 0.9)), rough=0.35,
                  seed=r.randint(0, 9999), noise_scale=3.0)


def add_bag(ctx, name, r, mat, *, size=(0.5, 0.44, 0.62), segs=16, torn=False, flat=0.0, loc=(0, 0, 0), rotz=0.0,
         tilt=(0.0, 0.0), burst=False):
    """One garbage bag (+ visible contents when torn). Returns the bag object."""
    bag = trash_bag_mesh(name, r, size=size, segs=segs, slump=0.3 + flat, tied=not burst, open_top=burst)
    inner = None
    if torn or burst:
        if burst:
            K.jagged_hole(bag, (0, 0, size[2] * 0.75), size[0] * 0.3, r.randint(0, 999), axis=2, jag=0.5)
        else:
            zc = size[2] * r.uniform(0.3, 0.42)
            K.jagged_hole(bag, (0, -size[1] * 0.5, zc), size[0] * 0.24, r.randint(0, 999), axis=1, jag=0.5)
        inner = K.blob(name + "_in", 0.5, subdiv=2, scale=(size[0] * 0.86, size[1] * 0.82, size[2] * 0.62),
                       rough=0.4, seed=r.randint(0, 999), center=(0, 0, size[2] * 0.3), noise_scale=3.0)
    if flat > 0:
        for o in [bag] + ([inner] if inner else []):
            K.map_verts(o, lambda co: Vector((co.x * (1 + flat * 0.6), co.y * (1 + flat * 0.6), co.z * (1 - flat))))
    for o in [bag] + ([inner] if inner else []):
        K.place(o, rot=(tilt[0], tilt[1], rotz))
        K.place(o, loc)
    ctx.add(bag, mat, uv_scale=1.0, smooth=70, patches=0.0, edge=0.2)
    if inner is not None:
        ctx.add(inner, "paper_trash", uv_scale=2.0, smooth=60, patches=0.0, edge=0.0)
    return bag


def add_litter(ctx, r, n: int, extent=(0.5, 0.4), center=(0, 0), kinds=("paper", "can", "wad")) -> None:
    """Small trash bits around a point (papers, cans, wads, bottle)."""
    for i in range(n):
        kind = kinds[i % len(kinds)]
        x = center[0] + r.uniform(-extent[0], extent[0])
        y = center[1] + r.uniform(-extent[1], extent[1])
        if kind == "paper":
            cell = r.choice(list(K.ATLAS_PAPER.values()))
            w, h = r.uniform(0.15, 0.24), r.uniform(0.2, 0.3)
            s = K.grid(f"lp{i}", w, h, 3, 3)
            K.uv_planar(s, 2, rect=cell)
            K.crumple(s, 0.015, scale=10.0, seed=r.randint(0, 999))
            K.map_verts(s, lambda co: Vector((co.x, co.y, abs(co.z) + 0.003)))
            K.place(s, (x, y, 0), (0, 0, r.uniform(0, 360)))
            ctx.add(s, "paper_trash", uv=None, smooth=50, patches=0.0, edge=0.0)
        elif kind == "can":
            c = can(f"lc{i}", r, crushed=r.uniform(0.3, 1.0), segs=8)
            K.place(c, rot=(90, 0, r.uniform(0, 360)))
            K.lift_min(c)
            K.place(c, (x, y, 0))
            ctx.add(c, r.choice(["can_red", "can_blue", "can_green", "can_alu"]), uv="cyl", uv_axis=2, uv_scale=1.0,
                    smooth=45, patches=0.3)
        elif kind == "wad":
            w = paper_wad(f"lw{i}", r, r.uniform(0.035, 0.06))
            K.place(w, (x, y, 0.03))
            K.lift_min(w)
            ctx.add(w, "paper_trash", uv_scale=2.0, smooth=60, patches=0.0, edge=0.2)
        elif kind == "bottle":
            b = bottle(f"lb{i}", r, broken=r.random() < 0.5)
            K.place(b, rot=(90, 0, r.uniform(0, 360)))
            K.lift_min(b)
            K.place(b, (x, y, 0))
            ctx.add(b, r.choice(["glass_brown", "glass_green"]), uv="cyl", uv_scale=1.0, smooth=50, patches=0.0, edge=0.2)


def flap(name: str, a, b, outward, length: float, angle: float, t: float = 0.004, nv: int = 2) -> object:
    """Thin board hinged on edge a-b, reaching `length` outward, tilted `angle` deg above horizontal."""
    a, b, o = Vector(a), Vector(b), Vector(outward).normalized()
    d = o * math.cos(math.radians(angle)) + Vector((0, 0, 1)) * math.sin(math.radians(angle))
    f = K.quad_sheet(name, a, b, b + d * length, a + d * length, 2, nv)
    K.solidify(f, t, offset=0.0)
    return f
