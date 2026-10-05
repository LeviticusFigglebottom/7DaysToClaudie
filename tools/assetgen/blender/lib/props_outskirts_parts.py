"""Part builders for the outskirts props (generators/props_outskirts.py and props_outskirts_ashen.py):
opening-aware log, pole and board walls for the shell props that dress a POI's kit rooms, sharpened
stakes, bones, skulls and antlers, rawhide lashings, hide sheets, river stones and plank decks.

Shell contract (game/data/props/outskirts.json): a shell wraps a kit room whose edge lines are
the room's outline; the kit walls stand centred on those lines, 0.16 m thick, with casing trim 2 cm
proud, so anything that hides them stays >= 0.10 m off the line. Walls built here take the room
outline in Blender metres (x east, y = -plan z), openings as (side, index, kind) and cut every log,
pole or board around each opening's clear size plus its trim.

Most helpers register their parts with the build context (``ctx.add``) and return them.
"""
from __future__ import annotations

import math
import random

import bmesh
from mathutils import Matrix, Vector, noise

from . import materials as M
from . import props_ext_kit as K
from . import props_ext_parts as P
from . import props_wild_parts as W

# Blender-only preview colours (dev_preview); Godot swaps in the real materials.
M.PREVIEW_COLORS.update({
    "out_bark_ash": (0.16, 0.13, 0.11), "out_log_peeled": (0.42, 0.38, 0.32), "out_log_smoked": (0.12, 0.09, 0.07),
    "out_bark_slab": (0.15, 0.11, 0.08), "out_sod": (0.16, 0.2, 0.08), "out_earth": (0.2, 0.15, 0.1),
    "out_bone": (0.62, 0.57, 0.47), "out_bone_ash": (0.55, 0.53, 0.5), "out_antler": (0.45, 0.38, 0.3),
    "out_hide": (0.48, 0.36, 0.22), "out_hide_ash": (0.42, 0.38, 0.33), "out_fur": (0.18, 0.12, 0.08),
    "out_rawhide": (0.55, 0.45, 0.3), "out_sinew": (0.6, 0.5, 0.35), "out_chinking": (0.3, 0.3, 0.18),
    "out_boughs": (0.07, 0.13, 0.06), "out_algae": (0.12, 0.16, 0.06), "out_dock_wood": (0.32, 0.3, 0.27),
    "out_pile": (0.18, 0.13, 0.1), "out_ammo_green": (0.16, 0.2, 0.12), "out_kapok_orange": (0.6, 0.22, 0.04),
    "out_net": (0.3, 0.32, 0.25), "out_cork": (0.45, 0.32, 0.2), "out_boat_green": (0.12, 0.25, 0.16),
    "out_boat_white": (0.7, 0.7, 0.66), "out_boat_red": (0.4, 0.07, 0.05), "out_outboard_blue": (0.1, 0.18, 0.35),
    "out_signs": (0.6, 0.55, 0.45), "out_rv_shell": (0.7, 0.66, 0.56), "out_rv_stripe_a": (0.42, 0.2, 0.08),
    "out_rv_stripe_b": (0.6, 0.38, 0.1), "out_alu_siding": (0.7, 0.7, 0.68), "out_awning": (0.4, 0.45, 0.3),
    "out_tent_orange": (0.65, 0.3, 0.06), "out_tent_blue": (0.1, 0.2, 0.4), "out_tent_green": (0.15, 0.3, 0.12),
    "out_tent_canvas": (0.45, 0.4, 0.28), "out_steel_black": (0.06, 0.06, 0.06), "out_steel_brown": (0.22, 0.17, 0.12),
    "out_bear_box": (0.3, 0.32, 0.3), "out_tent_fly": (0.2, 0.25, 0.3), "out_lure": (0.6, 0.2, 0.1),
    "out_trim_brown": (0.25, 0.15, 0.08), "out_stripe_white": (0.75, 0.75, 0.7), "out_stripe_red": (0.5, 0.06, 0.05),
})


def V3(p) -> Vector:
    return Vector(p) if not isinstance(p, Vector) else p.copy()


# ============================================================================================
# Rooms, openings and clipping
# ============================================================================================

# Kit opening clear sizes (POI_KIT.md): kind -> (width, sill, top). The trim adds TRIM on each side.
OPENING = {"door": (0.86, 0.0, 2.1), "window": (0.70, 0.90, 2.0), "window2": (1.60, 0.85, 2.05),
           "breach": (0.86, 0.0, 1.75), "open": (1.0, 0.0, 2.8)}
TRIM = 0.075


class Room:
    """A kit room outline in Blender metres: plan cells w (x) by d (plan z), centred on the origin;
    plan +z is Blender -y. Sides N (plan -z, Blender +y), S, E, W. index = cell along the side,
    counted from plan -x (N/S sides) or plan -z (E/W sides)."""

    def __init__(self, w: int, d: int, floor: float = 0.0):
        self.w, self.d, self.floor = w, d, floor

    def side_line(self, side: str, off: float) -> tuple[Vector, Vector, Vector]:
        """(start, along, outward) of a side's edge line pushed `off` metres outward (2D, z = 0).
        `along` runs in increasing cell index."""
        hw, hd = self.w / 2, self.d / 2
        if side == "N":
            return Vector((-hw, hd + off, 0)), Vector((1, 0, 0)), Vector((0, 1, 0))
        if side == "S":
            return Vector((-hw, -hd - off, 0)), Vector((1, 0, 0)), Vector((0, -1, 0))
        if side == "W":
            return Vector((-hw - off, hd, 0)), Vector((0, -1, 0)), Vector((-1, 0, 0))
        return Vector((hw + off, hd, 0)), Vector((0, -1, 0)), Vector((1, 0, 0))

    def length(self, side: str) -> float:
        return float(self.w if side in ("N", "S") else self.d)


def holes_on(side: str, openings, *, pad: float = TRIM, floor: float = 0.0, extra_top: float = 0.0):
    """Holes (t0, t1, z0, z1) along a side for the room's openings: each kit opening's clear size
    plus its casing trim, lifted by the floor height. 2 m openings span index and index+1."""
    out = []
    for o in openings:
        s, idx, kind = o[0], o[1], o[2]
        if s != side:
            continue
        span = 2.0 if kind.endswith("2") or kind == "door2" else 1.0
        w, sill, top = OPENING.get(kind.rstrip("2") if kind == "door2" else kind, OPENING["door"])
        if kind == "window2":
            w, sill, top = OPENING["window2"]
        if kind == "open":
            out.append((idx - 0.02, idx + span + 0.02, -1.0, 9.0))
            continue
        c = idx + span / 2
        out.append((c - w / 2 - pad, c + w / 2 + pad, (floor + sill - pad) if sill > 0 else -1.0,
                    floor + top + pad + extra_top))
    return out


def clip_spans(t0: float, t1: float, z0: float, z1: float, holes, *, min_len: float = 0.04) -> list[tuple[float, float]]:
    """The parts of [t0, t1] not covered by a hole whose height range overlaps [z0, z1]."""
    spans = [(t0, t1)]
    for (a, b, hz0, hz1) in holes:
        if hz1 <= z0 or hz0 >= z1:
            continue
        nxt = []
        for s0, s1 in spans:
            if b <= s0 or a >= s1:
                nxt.append((s0, s1))
                continue
            if a > s0:
                nxt.append((s0, a))
            if b < s1:
                nxt.append((b, s1))
        spans = nxt
    return [s for s in spans if s[1] - s[0] >= min_len]


def clip_vertical(z0: float, z1: float, t: float, half: float, holes) -> list[tuple[float, float]]:
    """The parts of a vertical member [z0, z1] at position t (half-width `half`) outside holes."""
    spans = [(z0, z1)]
    for (a, b, hz0, hz1) in holes:
        if t + half <= a or t - half >= b:
            continue
        nxt = []
        for s0, s1 in spans:
            if hz1 <= s0 or hz0 >= s1:
                nxt.append((s0, s1))
                continue
            if hz0 > s0:
                nxt.append((s0, hz0))
            if hz1 < s1:
                nxt.append((hz1, s1))
        spans = nxt
    return [s for s in spans if s[1] - s[0] > 0.05]


# ============================================================================================
# Logs, poles, stakes
# ============================================================================================

def add_log_between(ctx, name, a, b, r, seed, *, mat_bark="out_bark_ash", mat_end="wood_log_end", sides=10,
                    rings=4, taper=0.06, bow=0.012, moss=0.0, **kw):
    """Bark-on log from a to b (end grain at both ends)."""
    a, b = V3(a), V3(b)
    d = b - a
    L = max(0.05, d.length)
    o = W.log_obj(name, L, r, seed, sides=sides, rings=rings, taper=taper, bow=bow, bark=mat_bark, end=mat_end)
    K.orient(o, d.normalized(), W.up_for(d), (a + b) / 2)
    return ctx.add(o, None, uv=None, smooth=50, patches=kw.pop("patches", 0.35), edge=kw.pop("edge", 0.6), moss=moss, **kw)


def stake_obj(name, h, r, seed, *, sides=9, point=0.38, facets=5, lean=(0.0, 0.0), char=0.0):
    """Palisade stake standing on z = 0: a bark-on log `h` tall with an axe-cut point (faceted cone,
    peeled wood showing on the facets). Returns an unregistered object with three material slots:
    0 bark, 1 axe-cut facets ('out_log_peeled'), 2 unused."""
    rr = random.Random(seed)
    noise.seed_set(seed % 100000)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    shaft_h = h - point * r / 0.13
    rings = 5
    ring_v = []
    off = Vector((rr.uniform(0, 30), rr.uniform(0, 30), 0))
    u_rep = max(1, round(math.tau * r / 0.5))
    for i in range(rings):
        s = i / (rings - 1)
        z = shaft_h * s
        rad = r * (1.04 - 0.08 * s)
        ring = []
        for j in range(sides):
            a = math.tau * j / sides
            k = 1.0 + 0.06 * noise.noise(Vector((math.cos(a) * 1.4 + off.x, math.sin(a) * 1.4 + off.y, s * 4)))
            ring.append(bm.verts.new((math.cos(a) * rad * k, math.sin(a) * rad * k, z)))
        ring_v.append(ring)
    for i in range(rings - 1):
        for j in range(sides):
            j2 = (j + 1) % sides
            f = bm.faces.new((ring_v[i][j], ring_v[i][j2], ring_v[i + 1][j2], ring_v[i + 1][j]))
            f.material_index = 0
            z0, z1 = shaft_h * i / (rings - 1), shaft_h * (i + 1) / (rings - 1)
            for loop, uv in zip(f.loops, ((j / sides * u_rep, z0 / 0.5), ((j + 1) / sides * u_rep, z0 / 0.5),
                                          ((j + 1) / sides * u_rep, z1 / 0.5), (j / sides * u_rep, z1 / 0.5))):
                loop[uvl].uv = uv
    # The point: facets from the top ring to an off-centre tip.
    tip = bm.verts.new((rr.uniform(-0.25, 0.25) * r, rr.uniform(-0.25, 0.25) * r, h))
    top = ring_v[-1]
    for j in range(sides):
        j2 = (j + 1) % sides
        f = bm.faces.new((top[j], top[j2], tip))
        f.material_index = 1
        for loop in f.loops:
            co = loop.vert.co
            loop[uvl].uv = (co.x * 2.0 + co.z * 0.3, co.y * 2.0 + co.z)
    bottom = bm.verts.new((0, 0, 0))
    for j in range(sides):
        j2 = (j + 1) % sides
        f = bm.faces.new((ring_v[0][j2], ring_v[0][j], bottom))
        f.material_index = 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = K._obj_raw(name, bm)
    M.assign(o, "out_bark_ash" if char < 0.5 else "wood_charred")
    M.assign(o, "out_log_peeled" if char < 0.5 else "wood_charred")
    if lean != (0.0, 0.0):
        K.place(o, rot=(lean[0], lean[1], 0))
    return o


def add_stake(ctx, name, x, y, h, r, seed, *, lean=(0.0, 0.0), char=0.0, moss=0.0, z=0.0):
    o = stake_obj(name, h, r, seed, lean=lean, char=char)
    K.place(o, (x, y, z))
    return ctx.add(o, None, uv=None, smooth=48, patches=0.45, edge=0.9, moss=moss, low=0.6, low_h=0.5)


def lash(ctx, name, center, axis, r, *, turns=3, width=0.05, mat="out_rawhide", seed=0):
    """Rawhide wrapping round a member: `turns` thin rings spread over `width` along `axis`."""
    c = V3(center)
    ax = Vector(axis).normalized()
    rr = random.Random(seed)
    parts = []
    for k in range(turns):
        t = (k - (turns - 1) / 2) * width / max(1, turns)
        pts = []
        n0 = ax.orthogonal().normalized()
        n1 = ax.cross(n0).normalized()
        for i in range(10):
            a = math.tau * i / 10
            pts.append(c + ax * (t + 0.004 * math.sin(a * 2 + k)) + (n0 * math.cos(a) + n1 * math.sin(a)) * (r + 0.006))
        parts.append(K.tube(f"{name}{k}", pts, 0.006 + rr.uniform(0, 0.002), segs=4, closed=True))
    o = K.merge_parts(parts, name)
    return ctx.add(o, mat, uv="box", uv_scale=4.0, smooth=40, patches=0.3)


# ============================================================================================
# Bones, skulls, antlers
# ============================================================================================

def long_bone_obj(name, L, r, seed):
    """A long bone along X centred: a shaft with knobbed epiphyses (femur / humerus stand-in)."""
    prof = [(0.0, -L / 2), (r * 1.5, -L / 2 + r * 0.25), (r * 1.9, -L / 2 + r * 1.1), (r * 1.15, -L / 2 + r * 2.4),
            (r * 0.95, -L * 0.2), (r * 0.9, 0.0), (r * 0.95, L * 0.2), (r * 1.2, L / 2 - r * 2.3),
            (r * 1.75, L / 2 - r * 1.0), (r * 1.3, L / 2 - r * 0.2), (0.0, L / 2)]
    o = K.lathe(name, prof, segs=8)
    K.noise_disp(o, r * 0.18, scale=12.0, seed=seed)
    K.place(o, rot=(0, 90, 0))
    return o


def add_bone(ctx, name, a, b, r, seed, *, mat="out_bone", **kw):
    a, b = V3(a), V3(b)
    d = b - a
    o = long_bone_obj(name, d.length, r, seed)
    K.orient(o, d.normalized(), W.up_for(d), (a + b) / 2)
    return ctx.add(o, mat, uv="box", uv_scale=4.0, smooth=50, patches=0.4, edge=0.8, **kw)


def vertebra_obj(name, s, seed):
    """A vertebra: a body disc with a spinous process and two transverse processes."""
    parts = [K.cyl(f"{name}b", s * 0.5, s * 0.55, segs=8)]
    sp = K.box(f"{name}s", (s * 0.18, s * 0.9, s * 0.25), center=(0, -s * 0.65, 0), bevel=s * 0.05)
    parts.append(sp)
    for sx in (-1, 1):
        tp = K.box(f"{name}t{sx}", (s * 0.75, s * 0.16, s * 0.2), center=(sx * s * 0.55, -s * 0.2, 0), bevel=s * 0.04)
        parts.append(tp)
    o = K.merge_parts(parts, name)
    K.noise_disp(o, s * 0.05, scale=20.0, seed=seed)
    return o


def tooth_obj(name, s, seed):
    o = K.lathe(name, [(0.0, 0.0), (s * 0.28, s * 0.15), (s * 0.34, s * 0.55), (s * 0.22, s * 0.9), (0.0, s * 1.2)], segs=6)
    K.place(o, rot=(random.Random(seed).uniform(-20, 20), 0, 0))
    return o


def skull_obj(name, s, seed, *, kind="deer"):
    """Deer/elk skull facing -Y, the brain case at the origin: a cranium blob, a long tapered snout,
    orbits, nasal openings hinted by dents, cheek bones. s ~ 0.24 for a deer, 0.34 for an elk."""
    rr = random.Random(seed)
    cran = K.blob(f"{name}c", s * 0.5, subdiv=2, scale=(0.8, 0.95, 0.75), center=(0, 0, 0), rough=0.05, seed=seed)
    L = s * (1.45 if kind == "elk" else 1.3)
    rings = []
    for i in range(6):
        t = i / 5
        y = -s * 0.25 - L * t
        w = s * (0.36 - 0.24 * t)
        hgt = s * (0.32 - 0.2 * t)
        zc = s * (0.05 - 0.15 * t)
        ring = []
        for k in range(8):
            a = math.tau * k / 8
            ring.append((math.cos(a) * w, y, zc + math.sin(a) * hgt * (1.0 if math.sin(a) > 0 else 0.7)))
        rings.append(ring)
    snout = K.loft(f"{name}n", rings)
    parts = [cran, snout]
    for sx in (-1, 1):
        cheek = K.blob(f"{name}k{sx}", s * 0.13, subdiv=1, scale=(1.0, 1.6, 0.8), center=(sx * s * 0.33, -s * 0.38, -s * 0.08))
        parts.append(cheek)
    o = K.merge_parts(parts, name)
    for sx in (-1, 1):
        K.dent(o, (sx * s * 0.34, -s * 0.28, s * 0.12), s * 0.16, s * 0.07)
    K.dent(o, (0, -s * 0.25 - L, s * 0.0), s * 0.14, s * 0.06)
    K.noise_disp(o, s * 0.015, scale=14.0, seed=seed + 3)
    _ = rr
    return o


def antler_obj(name, s, seed, *, side=1, tines=4, spread=1.0):
    """One antler beat rising from a burr at the origin, sweeping back and out (+x for side 1) with
    `tines` forward-pointing tines. s ~ 0.6 (deer) .. 1.0 (elk)."""
    rr = random.Random(seed)
    beam = []
    for i in range(7):
        t = i / 6
        x = side * s * (0.12 + 0.55 * t) * spread
        y = s * (0.05 + 0.35 * t - 0.25 * t * t)
        z = s * (0.15 + 0.85 * t - 0.1 * t * t)
        beam.append(Vector((x, y, z)))
    radii = [s * (0.045 - 0.03 * i / 6) for i in range(7)]
    parts = [K.tube(f"{name}beam", beam, radii, segs=6)]
    parts.append(K.blob(f"{name}burr", s * 0.06, subdiv=1, scale=(1, 1, 0.6), center=beam[0], rough=0.3, seed=seed))
    for k in range(tines):
        t = 0.25 + 0.6 * k / max(1, tines - 1)
        i = min(5, int(t * 6))
        p = beam[i].lerp(beam[i + 1], t * 6 - i)
        L = s * rr.uniform(0.22, 0.38) * (1.0 - 0.3 * t)
        d = Vector((side * rr.uniform(0.0, 0.25), -rr.uniform(0.5, 0.9), rr.uniform(0.6, 1.0))).normalized()
        q = p + d * L
        mid = p.lerp(q, 0.5) + Vector((0, 0, L * 0.12))
        parts.append(K.tube(f"{name}t{k}", [p, mid, q], [s * 0.028, s * 0.02, s * 0.006], segs=5))
    o = K.merge_parts(parts, name)
    K.noise_disp(o, s * 0.006, scale=25.0, seed=seed + 1)
    return o


def add_skull(ctx, name, at, rot, s, seed, *, kind="deer", antlers=True, tines=4, ash=0.0, broken_tine=False):
    """Skull (+ antlers) placed at `at` (the brain case), rotated (deg) - facing -Y before rotation."""
    sk = skull_obj(f"{name}sk", s, seed, kind=kind)
    K.place(sk, at, rot)
    out = [ctx.add(sk, "out_bone_ash" if ash > 0.5 else "out_bone", uv="box", uv_scale=4.0, smooth=55, patches=0.5,
                   edge=0.9, base=ash * 0.4)]
    if antlers:
        for side in (-1, 1):
            a = antler_obj(f"{name}a{side}", s * (3.0 if kind == "elk" else 2.4), seed + side * 7, side=side,
                           tines=(tines - 1 if (broken_tine and side > 0) else tines))
            K.place(a, (side * s * 0.18, s * 0.1, s * 0.3))
            K.place(a, at, rot)
            out.append(ctx.add(a, "out_antler", uv="box", uv_scale=3.0, smooth=50, patches=0.5, edge=1.0))
    return out


def rib_obj(name, r, seed, *, arc=200.0, side=1):
    """A curved rib: an arc of radius r in the XZ plane (half a hoop), flattened section."""
    pts = []
    for i in range(8):
        a = math.radians(-90 + arc * i / 7) * side
        pts.append((math.cos(a) * r * side, 0.0, math.sin(a) * r * 0.9))
    o = K.tube(name, pts, [r * 0.06, r * 0.07, r * 0.07, r * 0.065, r * 0.06, r * 0.05, r * 0.04, r * 0.03], segs=5,
               flat=(1.0, 0.45))
    K.noise_disp(o, r * 0.01, scale=20.0, seed=seed)
    return o


def bone_string(ctx, name, top, length, seed, *, n=5, mat_cord="out_sinew", kinds=("tooth", "vert", "bone", "tine")):
    """A sinew string hanging from `top` with bones, teeth and antler tines threaded along it."""
    rr = random.Random(seed)
    top = V3(top)
    bot = top - Vector((rr.uniform(-0.02, 0.02), rr.uniform(-0.02, 0.02), length))
    cord = K.tube(f"{name}c", [top, top.lerp(bot, 0.5) + Vector((0.004, 0, 0)), bot], 0.0035, segs=4)
    ctx.add(cord, mat_cord, uv="cyl", uv_axis=2, smooth=40, patches=0.2)
    for k in range(n):
        t = 0.2 + 0.8 * (k + rr.uniform(0, 0.6)) / n
        p = top.lerp(bot, min(1.0, t))
        kind = kinds[rr.randrange(len(kinds))]
        if kind == "tooth":
            o = tooth_obj(f"{name}t{k}", rr.uniform(0.025, 0.04), seed + k)
            K.place(o, rot=(180, 0, rr.uniform(0, 360)))
            mat = "out_bone"
        elif kind == "vert":
            o = vertebra_obj(f"{name}v{k}", rr.uniform(0.03, 0.05), seed + k)
            K.place(o, rot=(rr.uniform(-20, 20), rr.uniform(-20, 20), rr.uniform(0, 360)))
            mat = "out_bone"
        elif kind == "tine":
            L = rr.uniform(0.09, 0.16)
            o = K.tube(f"{name}n{k}", [(0, 0, 0), (0.01, 0, -L * 0.5), (0.0, 0.005, -L)], [0.011, 0.008, 0.002], segs=5)
            mat = "out_antler"
        else:
            o = long_bone_obj(f"{name}b{k}", rr.uniform(0.08, 0.14), 0.008, seed + k)
            K.place(o, rot=(0, rr.uniform(60, 120), rr.uniform(0, 360)))
            mat = "out_bone"
        K.place(o, p)
        ctx.add(o, mat, uv="box", uv_scale=6.0, smooth=50, patches=0.4)
    return bot


# ============================================================================================
# Sheets: hides, cloth
# ============================================================================================

def hide_obj(name, w, h, seed, *, nx=10, ny=12, ragged=0.12):
    """An animal hide: a ragged outline (legs, neck) on an XZ sheet (facing -Y), w x h, centred."""
    o = K.grid(name, w, h, nx, ny)
    K.uv_planar(o, 2, scale=1.0)
    K.place(o, rot=(90, 0, 0))
    rr = random.Random(seed)
    lobes = [(rr.uniform(0, math.tau), rr.uniform(0.0, ragged), rr.randint(3, 6)) for _ in range(3)]

    def outside(p, _n):
        a = math.atan2(p.z / (h / 2), p.x / (w / 2))
        k = 0.92 - sum(amp * (0.5 + 0.5 * math.sin(f * a + ph)) for ph, amp, f in lobes)
        # legs: four lobes at the corners survive
        leg = max(0.0, abs(math.sin(2 * a)) - 0.7) * 0.6
        return (p.x / (w / 2)) ** 2 + (p.z / (h / 2)) ** 2 > (k + leg) ** 2
    K.delete_faces(o, outside)
    K.crumple(o, 0.012, scale=5.0, seed=seed)
    return o


def stone_obj(name, s, seed, *, flat=0.6):
    return K.chunk(name, s, random.Random(seed), n=14, flat=flat, elong=random.Random(seed + 1).uniform(1.0, 1.4))


def add_stone(ctx, name, at, s, seed, *, flat=0.6, mat="stone_river", rot=None):
    o = stone_obj(name, s, seed, flat=flat)
    K.subdivide(o, 1, smooth=0.6)
    K.place(o, at, rot or (0, 0, random.Random(seed).uniform(0, 360)))
    return ctx.add(o, mat, uv="box", uv_scale=2.0, smooth=60, patches=0.3, moss=0.3)


# ============================================================================================
# Decks and boards
# ============================================================================================

def plank_deck(ctx, x0, x1, y0, y1, z_top, *, board=0.14, gap=0.012, thick=0.04, along="y", mat="out_dock_wood",
               seed=0, missing=(), sag=0.0, nails=True):
    """Deck boards over [x0, x1] x [y0, y1], top at z_top, boards running `along` (x or y)."""
    rr = random.Random(seed)
    span = (x1 - x0) if along == "y" else (y1 - y0)
    n = max(1, int(round(span / (board + gap))))
    w = span / n - gap
    out = []
    for i in range(n):
        if i in missing:
            continue
        c = (x0 if along == "y" else y0) + (i + 0.5) * span / n
        L = (y1 - y0) if along == "y" else (x1 - x0)
        o = P.plank(f"deck{i}", L + rr.uniform(-0.01, 0.01), w, thick, bevel=0.004, cuts=4)
        if sag:
            K.bend(o, 2, -sag, along=0, origin=0.0)
        K.place(o, rot=(rr.uniform(-0.6, 0.6), rr.uniform(-0.5, 0.5), 90 if along == "y" else 0))
        cx, cy = (c, (y0 + y1) / 2) if along == "y" else ((x0 + x1) / 2, c)
        K.place(o, (cx, cy, z_top - thick / 2 + rr.uniform(-0.004, 0.003)))
        out.append(ctx.add(o, mat, long_axis=None, uv_scale=1.0, patches=0.6, edge=1.2, moss=0.25))
    return out
