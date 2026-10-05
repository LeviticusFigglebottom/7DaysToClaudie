"""Part builders for the wilderness / industrial props family (generators/props_wild*.py): timber and
steel members between two points, round stock, hex bolts, rolled steel sections (I-beam, channel,
angle), spoked wheels, chain, saw plates with teeth, bark-on logs and hanging cloth.

Most helpers take the build context and register the part themselves (``ctx.add``) so UVs are
computed in the part's own frame before it is oriented (grain follows every member). They return
the registered object. Raw builders (``*_obj``) return an unregistered Object.

Non-tiling texture rects (Blender UV space, v up):
  wild_firefinder_map  : disc centred at (0.5, 0.5), radius MAP_DISC_R.
  wild_radio_panel     : front panel in RADIO_RECT (the image band v 0.3..0.7).
Log ends use the shared vegetation end-grain disc (``wood_log_end``): bark rim at radius END_R.
"""
from __future__ import annotations

import math
import random

import bmesh
from mathutils import Matrix, Vector, noise

from . import materials as M
from . import props_ext_kit as K

MAP_DISC_R = 0.47
RADIO_RECT = (0.0, 0.3, 1.0, 0.7)
END_R = 0.497

# Blender-only preview colours (dev_preview); Godot swaps in the real materials.
M.PREVIEW_COLORS.update({
    "wild_lumber_fresh": (0.55, 0.4, 0.22), "wild_lumber_weathered": (0.35, 0.32, 0.28), "wild_lumber_dark": (0.25, 0.18, 0.11),
    "wild_sawdust": (0.55, 0.42, 0.25), "wild_cast_iron": (0.06, 0.06, 0.055), "wild_cast_iron_rust": (0.15, 0.08, 0.05),
    "wild_saw_steel": (0.5, 0.5, 0.52), "wild_saw_steel_rust": (0.35, 0.22, 0.15), "wild_paint_mill_green": (0.13, 0.18, 0.12),
    "wild_paint_mill_grey": (0.3, 0.31, 0.3), "wild_paint_skidder_yellow": (0.55, 0.38, 0.06), "wild_paint_red_oxide": (0.3, 0.08, 0.04),
    "wild_fur_brown": (0.2, 0.12, 0.06), "wild_fur_dark": (0.1, 0.06, 0.04), "wild_fur_fox": (0.4, 0.15, 0.05),
    "wild_hide": (0.6, 0.48, 0.32), "wild_wool_grey": (0.3, 0.29, 0.27), "wild_wool_red": (0.4, 0.08, 0.06),
    "wild_wool_green": (0.15, 0.2, 0.12), "wild_enamel_blue": (0.25, 0.32, 0.45), "wild_enamel_white": (0.7, 0.7, 0.68),
    "wild_tarpaper": (0.04, 0.04, 0.04), "wild_map_disc": (0.6, 0.55, 0.42), "wild_radio_face": (0.25, 0.26, 0.27),
    "wild_log_bark": (0.14, 0.1, 0.08), "wild_log_bark_larch": (0.2, 0.11, 0.07), "wild_jerky": (0.2, 0.06, 0.03),
    "wild_fish_smoked": (0.45, 0.3, 0.15), "wild_canvas_green": (0.1, 0.16, 0.1),
})


# --------------------------------------------------------------------------------------------
# Orientation helpers
# --------------------------------------------------------------------------------------------

def up_for(d: Vector, up=(0, 0, 1)) -> Vector:
    """A usable 'up' for a member along d (falls back when up is nearly parallel to d)."""
    dn = Vector(d).normalized()
    u = Vector(up).normalized()
    if abs(dn.dot(u)) > 0.95:
        u = Vector((0, 1, 0)) if abs(dn.y) < 0.9 else Vector((1, 0, 0))
    return u


def V3(p) -> Vector:
    return Vector(p) if not isinstance(p, Vector) else p.copy()


# --------------------------------------------------------------------------------------------
# Members
# --------------------------------------------------------------------------------------------

def bar(ctx, name, a, b, w, t, mat, *, up=(0, 0, 1), bevel=0.0, cuts=0, ext=0.0, **kw):
    """Rectangular member from a to b: `w` across, `t` along `up`, long axis (grain) a->b.
    ext lengthens both ends (overlapping joints)."""
    a, b = V3(a), V3(b)
    d = b - a
    o = K.box(name, (d.length + 2 * ext, w, t), bevel=bevel, cuts=(cuts, 0, 0))
    return ctx.add(o, mat, long_axis=0, ori=(d.normalized(), up_for(d, up), (a + b) / 2), **kw)


def bar_obj(name, a, b, w, t, *, up=(0, 0, 1), bevel=0.0, cuts=0, ext=0.0):
    """Unregistered rectangular member (to merge or deform before ctx.add, uv=box later)."""
    a, b = V3(a), V3(b)
    d = b - a
    o = K.box(name, (d.length + 2 * ext, w, t), bevel=bevel, cuts=(cuts, 0, 0))
    K.orient(o, d.normalized(), up_for(d, up), (a + b) / 2)
    return o


def rod(ctx, name, a, b, r, mat, *, segs=8, r2=None, caps=True, uv_scale=1.0, smooth=50, **kw):
    """Round stock / pipe / pole from a to b (r at a, r2 at b)."""
    a, b = V3(a), V3(b)
    d = b - a
    o = K.cyl(name, r, d.length, segs=segs, axis="X", r_top=r2, caps=caps)
    return ctx.add(o, mat, uv="cyl", uv_axis=0, uv_scale=uv_scale, smooth=smooth,
                   ori=(d.normalized(), up_for(d), (a + b) / 2), **kw)


def rod_obj(name, a, b, r, *, segs=8, r2=None, caps=True):
    a, b = V3(a), V3(b)
    d = b - a
    o = K.cyl(name, r, d.length, segs=segs, axis="X", r_top=r2, caps=caps)
    K.orient(o, d.normalized(), up_for(d), (a + b) / 2)
    return o


def pole(ctx, name, pts, r, mat, *, segs=7, r_end=None, seed=0, wobble=0.0, uv_scale=1.0, **kw):
    """Crooked round pole (bark-on poles, branches) through a polyline, tapering to r_end."""
    pts = [V3(p) for p in pts]
    n = len(pts)
    radii = [r + ((r_end if r_end is not None else r) - r) * i / max(1, n - 1) for i in range(n)]
    if wobble > 0:
        rr = random.Random(seed)
        pts = [p if i in (0, n - 1) else p + Vector((rr.uniform(-1, 1), rr.uniform(-1, 1), rr.uniform(-1, 1))) * wobble
               for i, p in enumerate(pts)]
    o = K.tube(name, pts, radii, segs=segs)
    return ctx.add(o, mat, uv_scale=uv_scale, smooth=55, **kw)


def bolts_obj(name, items, r=0.011, h=0.008, segs=6):
    """Hex bolt heads / rivets: items = [(pos, outward_normal)], merged into one object."""
    parts = []
    for i, (p, n) in enumerate(items):
        c = K.cyl(f"{name}{i}", r, h, segs=segs, center=(0, 0, h / 2))
        nn = Vector(n).normalized()
        K.orient(c, nn.orthogonal().normalized(), nn, V3(p))
        parts.append(c)
    return K.merge_parts(parts, name)


def bolts(ctx, name, items, mat, r=0.011, h=0.008, segs=6, **kw):
    if not items:
        return None
    return ctx.add(bolts_obj(name, items, r, h, segs), mat, uv_scale=2.0, wear=0.8, **kw)


# --------------------------------------------------------------------------------------------
# Rolled steel sections (profiles in (y, z), extruded along X, centred on the a->b line)
# --------------------------------------------------------------------------------------------

def prof_i(h, w, tf, tw):
    return [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, -h / 2 + tf), (tw / 2, -h / 2 + tf), (tw / 2, h / 2 - tf),
            (w / 2, h / 2 - tf), (w / 2, h / 2), (-w / 2, h / 2), (-w / 2, h / 2 - tf), (-tw / 2, h / 2 - tf),
            (-tw / 2, -h / 2 + tf), (-w / 2, -h / 2 + tf)]


def prof_c(h, w, t):
    """Channel opening toward +y (web on -y)."""
    return [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, -h / 2 + t), (-w / 2 + t, -h / 2 + t), (-w / 2 + t, h / 2 - t),
            (w / 2, h / 2 - t), (w / 2, h / 2), (-w / 2, h / 2)]


def prof_l(a, t):
    """Angle with its corner at the origin, legs along +y and +z."""
    return [(0, 0), (a, 0), (a, t), (t, t), (t, a), (0, a)]


def section(ctx, name, a, b, prof, mat, *, up=(0, 0, 1), **kw):
    a, b = V3(a), V3(b)
    d = b - a
    o = K.prism(name, prof, d.length, plane="YZ")
    return ctx.add(o, mat, long_axis=0, ori=(d.normalized(), up_for(d, up), (a + b) / 2), **kw)


# --------------------------------------------------------------------------------------------
# Wheels, chain
# --------------------------------------------------------------------------------------------

def ring_obj(name, r_in, r_out, width, segs=24, bevel=0.0):
    """Flat ring (rim / tyre band / hoop) around Z, centred."""
    b = min(bevel, (r_out - r_in) * 0.4, width * 0.4)
    if b > 0:
        prof = [(r_in, -width / 2), (r_out - b, -width / 2), (r_out, -width / 2 + b), (r_out, width / 2 - b),
                (r_out - b, width / 2), (r_in, width / 2)]
    else:
        prof = [(r_in, -width / 2), (r_out, -width / 2), (r_out, width / 2), (r_in, width / 2)]
    return K.lathe(name, prof, segs=segs, close_profile=True)


def spokes_obj(name, r0, r1, n, w, t, phase=0.0, curve=0.0):
    """n radial spokes in the XY plane (axle Z) from r0 to r1; curve bends them (cast wheels)."""
    parts = []
    for k in range(n):
        a = phase + math.tau * k / n
        if curve:
            pts = []
            for i in range(4):
                s = i / 3
                rr = r0 + (r1 - r0) * s
                aa = a + curve * math.sin(math.pi * s)
                pts.append(Vector((rr * math.cos(aa), rr * math.sin(aa), 0.0)))
            o = K.tube(f"{name}{k}", pts, w * 0.5, segs=6, flat=(1.0, t / w))
        else:
            o = K.box(f"{name}{k}", (r1 - r0, w, t), center=((r0 + r1) / 2, 0, 0))
            K.place(o, rot=(0, 0, math.degrees(a)))
        parts.append(o)
    return K.merge_parts(parts, name)


def chain_obj(name, pts, link=0.055, wire=0.0055, sides=4):
    """Chain along a polyline: alternating stadium links every 0.82 * link."""
    pts = [V3(p) for p in pts]
    lens = [0.0]
    for a, b in zip(pts[:-1], pts[1:]):
        lens.append(lens[-1] + (b - a).length)
    total = lens[-1]
    step = link * 0.82
    n = max(1, int(total / step))
    parts = []
    n0 = None
    for i in range(n):
        s = (i + 0.5) * total / n
        k = 0
        while k < len(lens) - 2 and lens[k + 1] < s:
            k += 1
        seg = pts[k + 1] - pts[k]
        t = (s - lens[k]) / max(1e-6, seg.length)
        p = pts[k].lerp(pts[k + 1], t)
        tan = seg.normalized()
        if n0 is None:
            n0 = tan.orthogonal().normalized()
        nrm = (n0 - tan * n0.dot(tan)).normalized()
        if i % 2:
            nrm = tan.cross(nrm).normalized()
        loop = []
        for j in range(6):
            a = math.tau * j / 6
            loop.append(p + tan * (math.cos(a) * link * 0.5) + nrm * (math.sin(a) * link * 0.3))
        parts.append(K.tube(f"{name}{i}", loop, wire, segs=sides, closed=True))
    return K.merge_parts(parts, name)


# --------------------------------------------------------------------------------------------
# Saw plates
# --------------------------------------------------------------------------------------------

def saw_outline(L, H, pitch, depth, *, belly=0.0, raker_every=0, raker_depth=None, back_curve=0.0):
    """(x, z) outline of a saw plate along X: the back edge at z = H (optionally arched), the
    toothed edge along z = 0 sagging by `belly` in the middle. Every `raker_every`-th tooth is a
    shorter square raker (crosscut saws)."""
    pts_top = []
    for i in range(9):
        x = -L / 2 + L * i / 8
        pts_top.append((x, H + back_curve * (1 - (2 * x / L) ** 2)))
    bottom = []
    n = max(2, int(L / pitch))
    rd = raker_depth if raker_depth is not None else depth * 0.75
    for k in range(n):
        x0 = -L / 2 + L * k / n
        x1 = -L / 2 + L * (k + 1) / n
        xm = (x0 + x1) / 2

        def base(x):
            return -belly * (1 - (2 * x / L) ** 2)
        if raker_every and k % raker_every == raker_every - 1:
            bottom += [(x0, base(x0)), (x0 + (x1 - x0) * 0.3, base(x0) - rd), (x0 + (x1 - x0) * 0.42, base(x0) - rd * 0.8),
                       (x0 + (x1 - x0) * 0.58, base(x0) - rd * 0.8), (x0 + (x1 - x0) * 0.7, base(x0) - rd)]
        else:
            bottom += [(x0, base(x0)), (xm, base(xm) - depth)]
    bottom.append((L / 2, -belly * 0.0))
    # Outline: along the toothed edge left -> right, then back along the top right -> left.
    return bottom + list(reversed(pts_top))


def saw_plate_obj(name, outline, t):
    """Thin plate (thickness t along Y) from an (x, z) outline."""
    return K.prism(name, outline, t, plane="XZ")


# --------------------------------------------------------------------------------------------
# Logs (bark + end grain, two material slots)
# --------------------------------------------------------------------------------------------

def log_obj(name, L, R, seed, *, sides=12, rings=7, taper=0.08, bow=0.02, bark="wild_log_bark",
            end="wood_log_end", cut_face=None, knots=2):
    """Bark-on log along X centred at the origin: noisy, slightly bowed and tapered, both ends
    sawn (end-grain disc UVs, bark rim on the rim). cut_face=(axis_dir, offset): a flat sawn
    face (a cant on the carriage), mapped with the third material slot 'wild_lumber_fresh'."""
    rr = random.Random(seed)
    noise.seed_set(seed % 100000)
    off = Vector((rr.uniform(0, 40), rr.uniform(0, 40), 0))
    bow_dir = rr.uniform(0, math.tau)
    u_rep = max(1, round(math.tau * R / 0.55))
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    ring_v = []
    for i in range(rings):
        s = i / (rings - 1)
        x = -L / 2 + L * s
        rad = R * (1 + taper * 0.5 - taper * s)
        b = math.sin(math.pi * s) * bow
        c = Vector((x, math.cos(bow_dir) * b, math.sin(bow_dir) * b))
        ring = []
        for j in range(sides):
            a = math.tau * j / sides
            k = 1.0 + 0.05 * noise.noise(Vector((math.cos(a) * 1.3 + off.x, math.sin(a) * 1.3 + off.y, s * 5.0)))
            ring.append(bm.verts.new(c + Vector((0, math.cos(a), math.sin(a))) * rad * k))
        ring_v.append((ring, c, rad))
    for i in range(rings - 1):
        ra, rb = ring_v[i][0], ring_v[i + 1][0]
        xa = -L / 2 + L * i / (rings - 1)
        xb = -L / 2 + L * (i + 1) / (rings - 1)
        for j in range(sides):
            j2 = (j + 1) % sides
            f = bm.faces.new((ra[j], ra[j2], rb[j2], rb[j]))
            f.material_index = 0
            u0, u1 = j / sides * u_rep, (j + 1) / sides * u_rep
            for loop, uv in zip(f.loops, ((u0, xa / 0.55), (u1, xa / 0.55), (u1, xb / 0.55), (u0, xb / 0.55))):
                loop[uvl].uv = uv
    for idx, flip in ((0, True), (rings - 1, False)):
        ring, c, _rad = ring_v[idx]
        cv = bm.verts.new(c)
        for j in range(sides):
            j2 = (j + 1) % sides
            tri = (cv, ring[j2], ring[j]) if flip else (cv, ring[j], ring[j2])
            f = bm.faces.new(tri)
            f.material_index = 1
            for loop in f.loops:
                if loop.vert is cv:
                    loop[uvl].uv = (0.5, 0.5)
                else:
                    jj = ring.index(loop.vert)
                    a = math.tau * jj / sides
                    loop[uvl].uv = (0.5 + END_R * math.cos(a), 0.5 + END_R * math.sin(a))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = K._obj_raw(name, bm)
    M.assign(o, bark)
    M.assign(o, end)
    if cut_face is not None:
        axis, offset = cut_face
        M.assign(o, "wild_lumber_fresh")
        K.cut_plane(o, Vector(axis) * offset, Vector(axis), keep="below", fill=True)
        me = o.data
        uvd = me.uv_layers.active.data
        ax = Vector(axis).normalized()
        for p in me.polygons:
            if p.normal.dot(ax) > 0.95:
                p.material_index = 2
                for li in p.loop_indices:
                    co = me.vertices[me.loops[li].vertex_index].co
                    uvd[li].uv = (co.x, co.y if abs(ax.z) > 0.5 else co.z)
    return o


def add_log(ctx, name, L, R, seed, *, at=(0, 0, 0), rot=(0, 0, 0), smooth=50, moss=0.0, **kw):
    o = log_obj(name, L, R, seed, **kw)
    K.place(o, at, rot)
    return ctx.add(o, None, uv=None, smooth=smooth, patches=0.3, edge=0.6, moss=moss)


# --------------------------------------------------------------------------------------------
# Cloth
# --------------------------------------------------------------------------------------------

def drape_obj(name, L, W, top_z, half_w, *, nx=14, ny=10, hang=0.18, fold_at=None, seed=0, rumple=0.012):
    """Blanket over a mattress: a sheet L x W (X, Y) centred, flat on top at top_z within
    |y| < half_w and hanging `hang` down over the sides. fold_at: x beyond which the sheet is
    turned back over itself (a folded-down top). UVs in metres, set before shaping."""
    o = K.grid(name, L, W, nx, ny)
    K.uv_planar(o, 2, scale=1.0)

    def shape(co):
        y = co.y
        z = top_z
        if abs(y) > half_w:
            d = abs(y) - half_w
            dz = min(d, hang)
            z = top_z - dz - max(0.0, d - hang) * 0.15
            y = math.copysign(half_w + max(0.0, d - dz) * 0.35 + 0.012, y)
        return Vector((co.x, y, z))
    K.map_verts(o, shape)
    if fold_at is not None:
        K.bisect(o, (fold_at, 0, 0), (1, 0, 0))

        def fold(co):
            s = co.x - fold_at
            if s <= 1e-5:
                return co
            return Vector((fold_at - s, co.y, co.z + 0.022 + 0.01 * min(1.0, s / 0.2)))
        K.map_verts(o, fold)
    K.crumple(o, rumple, scale=5.0, seed=seed)
    K.solidify(o, 0.008, offset=-1.0, even=False)
    return o
