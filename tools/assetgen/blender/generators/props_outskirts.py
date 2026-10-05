"""Outskirts props (Larch Hollow): Larch Pond Bait & Boat (dock sections and pilings, rowboats, the
boathouse's water doors, bait tanks, the tackle wall, rod racks, life jackets, an outboard motor, net
heaps, the roadside sign, a mounted pike) and Tamsin River Campground (a cab-over motorhome, dome
and cabin tents, fire rings, tent pads, bear boxes, the camp host's trailer shell, the comfort
station roof, the fee station shell, the entrance sign and gate arm, a water spigot, camp chairs and
the host's cash box). The Ashen watch camp lives in props_outskirts_ashen.py.

Conventions (docs/ASSET_PIPELINE.md): metres, Z up, front -Y (Godot +Z), origin bottom centre.
Wall-mounted props have their origin on the wall plane and stand off it towards -Y. Dock props have
their deck at the top of the model (the POI places them y = -height so the deck is at the pad) and
the lake 0.6 m under the deck (the placement's freeboard, ADR-0024): their waterline is at
height - 0.6 and the piles are slimed below it. Shells (out_*_shell) wrap a POI kit room: origin
at the room's plan centre on the ground (lib.props_outskirts_parts.Room), siding 0.11 m outside
the kit walls' edge lines, cut round the plan's openings, roofs on the kit ceiling (floor + 3 m).
Lettered faces map rectangles of the out_signs atlas (textures/gen/outskirts.py: ATLAS_OUT below
must match that module's OUT).

clean     : left one summer -- dust, sun-fade, light rust and algae.
worn      : a hard winter -- dents, peeling paint, tears, things knocked about.
destroyed : smashed, burnt, sunk or collapsed.
"""
from __future__ import annotations

import math
import random

import bmesh
from mathutils import Matrix, Vector

from lib import materials as M
from lib import props_ext_kit as K
from lib import props_ext_parts as P
from lib import props_outskirts_parts as O
from lib import props_wild_parts as W

# --------------------------------------------------------------------------------------------
# The out_signs atlas (units of 256 px in a 2048 px image; textures/gen/outskirts.py OUT)
# --------------------------------------------------------------------------------------------

UNIT = 256
ATLAS_PX = 2048
ATLAS_OUT = {
    "bait_sign": (0, 0, 6, 2), "bait_board": (6, 0, 2, 2),
    "boat_rental": (0, 2, 4, 1), "camp_host": (4, 2, 2, 1), "fee_station": (6, 2, 2, 2),
    "tackle_labels": (0, 3, 4, 1), "motor_decal": (4, 3, 2, 1),
    "camp_sign": (0, 4, 6, 2), "site_numbers": (6, 4, 2, 2),
    "rv_badge": (0, 6, 4, 1), "bear_label": (4, 6, 2, 1), "kiosk_rules": (6, 6, 2, 2),
    "lure_cards": (0, 7, 4, 1), "closed_notice": (4, 7, 2, 1),
}
SIGNS = "out_signs"
WATERLINE = 0.6  # the lake is this far under a dock prop's deck


def _rect(name: str, sub=None, inset: float = 2.0) -> tuple[float, float, float, float]:
    """Blender UV rect (u0, v0, u1, v1; v up) of an atlas cell, or of a sub-rectangle given as
    fractions (fx0, fy0, fx1, fy1) of the cell with y measured from the top of the image."""
    x, y, w, h = [v * UNIT for v in ATLAS_OUT[name]]
    if sub:
        fx0, fy0, fx1, fy1 = sub
        x, y, w, h = x + fx0 * w, y + fy0 * h, (fx1 - fx0) * w, (fy1 - fy0) * h
    x0, y0, x1, y1 = x + inset, y + inset, x + w - inset, y + h - inset
    return (x0 / ATLAS_PX, 1.0 - y1 / ATLAS_PX, x1 / ATLAS_PX, 1.0 - y0 / ATLAS_PX)


def _face(ctx, name, w, h, rect, loc, rot_z=0.0, *, wear=0.6, patches=0.35, edge=0.6, nu=2, nv=2, mat=SIGNS):
    """Flat lettered face (w x h) facing -Y with an atlas rect mapped edge to edge; rot_z 180 faces
    +Y, 90 faces +X."""
    o = K.quad_sheet(name, (-w / 2, 0, -h / 2), (w / 2, 0, -h / 2), (w / 2, 0, h / 2), (-w / 2, 0, h / 2), nu, nv)
    K.uv_planar(o, 1, rect=rect)
    K.place(o, (0, 0, 0), (0, 0, rot_z))
    K.place(o, loc)
    return ctx.add(o, mat, uv=None, wear=wear, patches=patches, edge=edge)


def _interp(keys, t):
    for (t0, v0), (t1, v1) in zip(keys[:-1], keys[1:]):
        if t <= t1:
            f = (t - t0) / max(1e-6, t1 - t0)
            return v0 + (v1 - v0) * f
    return keys[-1][1]


def _swing(objs, pivot, deg: float) -> None:
    """Rigid turn of already-added parts about the vertical line through `pivot` (a door on its
    hinges)."""
    p = Vector(pivot)
    m = Matrix.Translation(p) @ Matrix.Rotation(math.radians(deg), 4, "Z") @ Matrix.Translation(-p)
    for o in objs:
        o.data.transform(m)
        o.data.update()


def _tri(name, a, b, c, thickness=0.0):
    """One triangle (a, b, c counter-clockwise seen from its front), optionally solidified."""
    bm = bmesh.new()
    vs = [bm.verts.new(Vector(p)) for p in (a, b, c)]
    bm.faces.new(vs)
    o = K._obj(name, bm)
    if thickness > 0:
        K.solidify(o, thickness, offset=-1.0)
    return o


def _wall_rects(t0, t1, z0, z1, holes):
    """Rectangles (ta, tb, za, zb) covering [t0, t1] x [z0, z1] minus the holes."""
    cuts = sorted({t0, t1, *[c for h in holes for c in (h[0], h[1]) if t0 < c < t1]})
    out = []
    for a, b in zip(cuts[:-1], cuts[1:]):
        if b - a < 0.01:
            continue
        m = (a + b) / 2
        spans = [(z0, z1)]
        for (ha, hb, hz0, hz1) in holes:
            if not (ha <= m <= hb):
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
        out += [(a, b, s0, s1) for s0, s1 in spans if s1 - s0 > 0.01]
    return out


def _siding(ctx, room, side, openings, *, off, z0, z1, th=0.03, mat, ext=0.0, seed=0, wear=1.0, dents=0, moss=0.0,
            trim_mat=None, trim_w=0.06, uv_scale=1.0, hole_pad=O.TRIM):
    """A clad wall `off` m outside a side's edge line from z0 to z1, cut round the side's openings
    (each opening's clear size plus its trim), with flat trim boards round each hole."""
    start, along, out = room.side_line(side, off + th / 2)
    L = room.length(side)
    holes = O.holes_on(side, openings, floor=room.floor, pad=hole_pad)
    rr = random.Random(seed)
    parts = []
    for (a, b, za, zb) in _wall_rects(-ext, L + ext, z0, z1, holes):
        c = start + along * ((a + b) / 2) + Vector((0, 0, (za + zb) / 2))
        size = (abs(along.x) * (b - a) + abs(out.x) * th, abs(along.y) * (b - a) + abs(out.y) * th, zb - za)
        o = K.box(f"{side}clad{a:.2f}_{za:.2f}", size, center=c, cuts=(max(1, int(size[0] * 2)), max(1, int(size[1] * 2)),
                                                                          max(1, int((zb - za) * 2))))
        for _ in range(dents):
            if rr.random() < 0.5:
                p = c + along * rr.uniform(-(b - a) / 2, (b - a) / 2) + Vector((0, 0, rr.uniform(-(zb - za) / 2, (zb - za) / 2)))
                K.dent(o, p + out * th, rr.uniform(0.12, 0.3), rr.uniform(0.01, 0.025), -out)
        parts.append(ctx.add(o, mat, uv="box", uv_scale=uv_scale, wear=wear, patches=0.45, edge=0.8, moss=moss,
                             low=0.4, low_h=0.6))
    if trim_mat:
        for (a, b, hz0, hz1) in holes:
            if hz0 < -0.5 and hz1 > 5:
                continue
            for t in (a + trim_w / 2, b - trim_w / 2):
                p = start + along * t + out * (th / 2 + 0.008)
                W.bar(ctx, f"{side}trimv{t:.2f}", (p.x, p.y, max(z0, hz0)), (p.x, p.y, hz1), trim_w, 0.016, trim_mat,
                      up=tuple(out), bevel=0.003)
            for z in ((hz1 - trim_w / 2,) if hz0 < z0 + 0.01 else (hz0 + trim_w / 2, hz1 - trim_w / 2)):
                pa = start + along * a + out * (th / 2 + 0.008)
                pb = start + along * b + out * (th / 2 + 0.008)
                W.bar(ctx, f"{side}trimh{a:.2f}{z:.2f}", (pa.x, pa.y, z), (pb.x, pb.y, z), trim_w, 0.016, trim_mat,
                      up=tuple(out), bevel=0.003)
    return parts


# ============================================================================================
# Larch Pond Bait & Boat: the water side
# ============================================================================================

def _pile(ctx, name, x, y, z0, z1, r, seed, *, waterline, lean=(0.0, 0.0), mat="wood_creosote"):
    """A creosoted pile from z0 to z1, slimed with weed and algae below the waterline (two parts so
    the green band reads at the water)."""
    rr = random.Random(seed)
    top = Vector((x + math.sin(math.radians(lean[0])) * (z1 - z0), y + math.sin(math.radians(lean[1])) * (z1 - z0), z1))
    base = Vector((x, y, z0))
    wl = waterline + rr.uniform(0.0, 0.08)
    f = (wl - z0) / max(0.01, z1 - z0)
    mid = base.lerp(top, f)
    lo = W.rod_obj(f"{name}_wet", base, mid, r * 1.03, segs=10)
    K.noise_disp(lo, 0.006, scale=6.0, seed=seed)
    ctx.add(lo, "out_algae", uv="cyl", uv_axis=0, uv_scale=1.0, smooth=50, patches=0.5, moss=0.0)
    hi = W.rod_obj(f"{name}_dry", mid, top, r, segs=10, r2=r * 0.97)
    ctx.add(hi, mat, uv="cyl", uv_axis=0, uv_scale=1.0, smooth=50, patches=0.5, edge=0.6, low=0.6, low_h=0.5)
    cap = K.cyl(f"{name}_top", r * 0.98, 0.02, segs=10, center=top + Vector((0, 0, -0.01)))
    ctx.add(cap, "wood_log_end", uv="box", uv_scale=2.0, patches=0.4)
    return top


def out_dock_section(ctx: K.Ctx) -> None:
    """Four metres of plank dock (2 m wide, deck at z 3.2): creosoted piles slimed below the
    waterline, cap beams, three stringers, deck boards across, fascia boards and a cast cleat.
    Worn: boards gone and sagging, a pile leaning, more weed."""
    r = ctx.rnd("dock")
    top = 3.2
    wl = top - WATERLINE
    for i, (x, y) in enumerate(((-0.86, -1.72), (0.86, -1.72), (-0.86, 1.72), (0.86, 1.72))):
        lean = (r.uniform(-1, 1), r.uniform(-1, 1))
        if ctx.worn and i == 2:
            lean = (-3.5, 1.0)
        _pile(ctx, f"pile{i}", x, y, 0.0, top - 0.2, 0.12 * r.uniform(0.94, 1.05), ctx.seed + i, waterline=wl, lean=lean)
    for y in (-1.72, 1.72):
        W.bar(ctx, f"cap{y}", (-1.0, y, top - 0.27), (1.0, y, top - 0.27), 0.12, 0.14, "wood_creosote", up=(0, 0, 1),
              bevel=0.008, patches=0.5)
    for x in (-0.82, 0.0, 0.82):
        W.bar(ctx, f"stringer{x}", (x, -2.0, top - 0.12), (x, 2.0, top - 0.12), 0.06, 0.16, "wood_weathered",
              up=(0, 0, 1), bevel=0.006, patches=0.5, moss=0.2)
    missing = ()
    if ctx.worn:
        dr = ctx.drnd("boards")
        missing = tuple(dr.sample(range(2, 26), 3))
    O.plank_deck(ctx, -1.0, 1.0, -2.0, 2.0, top, board=0.14, gap=0.012, thick=0.035, along="x", mat="wood_weathered",
                 seed=ctx.seed, missing=missing, sag=0.015 if ctx.worn else 0.004)
    for x in (-1.02, 1.02):
        W.bar(ctx, f"fascia{x}", (x, -2.0, top - 0.11), (x, 2.0, top - 0.11), 0.2, 0.035, "wood_weathered",
              up=(1, 0, 0), bevel=0.004, patches=0.6, moss=0.3)
    # A cast cleat on the east edge, a bumper tyre hung on the west fascia.
    cl = K.box("cleat_base", (0.06, 0.2, 0.03), center=(0.9, 0.3, top + 0.015), bevel=0.008)
    horn = K.tube("cleat_horn", [(0.9, 0.16, top + 0.04), (0.9, 0.22, top + 0.07), (0.9, 0.38, top + 0.07),
                                 (0.9, 0.44, top + 0.04)], 0.016, segs=8)
    ctx.add(K.merge_parts([cl, horn], "cleat"), "wild_cast_iron_rust", uv="box", uv_scale=4.0, smooth=40, edge=1.2)
    tyre = P.tyre("bumper_tyre", 0.3, 0.17, 0.16, segs=14)
    K.place(tyre, (0, 0, 0), (0, 0, 90))
    K.place(tyre, (-1.12, -0.6, top - 0.38), (0, 8, 0))
    ctx.add(tyre, "tyre_rubber", uv="box", uv_scale=2.0, smooth=50, patches=0.5)
    rope = K.tube("tyre_rope", [(-1.1, -0.6, top - 0.09), (-1.08, -0.6, top - 0.06), (-1.04, -0.6, top + 0.0)], 0.01, segs=5)
    ctx.add(rope, "road_rope", uv="cyl", uv_axis=2, smooth=40)
    ctx.col_box((-1.02, -2.0, top - 0.3), (1.02, 2.0, top))


def out_dock_piles(ctx: K.Ctx) -> None:
    """A bent of two piles (x = +-0.9) under a cap beam whose top is the model's top (3.2), with an
    X-brace below it; slimed under the waterline. Worn: a brace board gone, a pile out of true."""
    r = ctx.rnd("bent")
    top = 3.2
    wl = top - WATERLINE + 0.1  # placed 0.1 lower than a dock section (under the building's floor)
    for i, x in enumerate((-0.9, 0.9)):
        lean = (r.uniform(-1, 1), r.uniform(-1, 1)) if not (ctx.worn and i == 1) else (2.5, -1.5)
        _pile(ctx, f"pile{i}", x, 0.0, 0.0, top - 0.16, 0.12 * r.uniform(0.95, 1.05), ctx.seed + i, waterline=wl, lean=lean)
    W.bar(ctx, "cap", (-1.0, 0.0, top - 0.08), (1.0, 0.0, top - 0.08), 0.14, 0.16, "wood_creosote", up=(0, 0, 1), bevel=0.008)
    for k, (a, b) in enumerate((((-0.9, -0.15, top - 0.3), (0.9, -0.15, wl - 0.2)), ((-0.9, 0.15, wl - 0.2), (0.9, 0.15, top - 0.3)))):
        if ctx.worn and k == 1:
            continue
        W.bar(ctx, f"brace{k}", a, b, 0.15, 0.035, "wood_creosote", up=(0, 1, 0), bevel=0.004, patches=0.6, moss=0.2)


def _hull_parts(ctx, *, broken=False, swamped=False):
    """A lapstrake-look wooden rowboat, 3.7 m (bow at -Y), as raw parts [(obj, mat, kw)]: the hull
    skin (painted green over red bottom paint, white inside), transom, gunwale rails, three
    thwarts, floorboards, oarlocks, a pair of oars and the painter."""
    r = ctx.rnd("hull")
    L = 3.7
    beam = [(0, 0.02), (0.08, 0.26), (0.2, 0.48), (0.36, 0.62), (0.55, 0.66), (0.75, 0.63), (0.9, 0.57), (1.0, 0.5)]
    sheer = [(0, 0.74), (0.15, 0.66), (0.5, 0.58), (0.85, 0.6), (1.0, 0.62)]
    keel = [(0, 0.5), (0.05, 0.24), (0.14, 0.08), (0.3, 0.02), (0.5, 0.0), (0.8, 0.02), (1.0, 0.07)]
    n_st, n_u = 16, 13

    def ring(t, inset=0.0):
        b = max(0.015, _interp(beam, t) - inset)
        zs = _interp(sheer, t)
        zk = _interp(keel, t) + inset * 1.1
        pts = []
        for j in range(n_u):
            u = -1 + 2 * j / (n_u - 1)
            au = abs(u)
            x = math.copysign(b * au ** 0.75, u)
            z = zk + (zs - zk) * au ** 1.7
            # Lapstrake: three shallow steps up each side.
            z += 0.008 * math.floor(au * 4) if au < 0.99 else 0.0
            pts.append((x, -L / 2 + L * t, z))
        return pts

    ts = [i / (n_st - 1) for i in range(n_st)]
    outer = K.loft("hull_out", [ring(t) for t in ts], closed_ring=False, cap_start=False, cap_end=False, recalc=False)
    inner = K.loft("hull_in", [ring(t, 0.022) for t in ts], closed_ring=False, cap_start=False, cap_end=False, recalc=False)
    for o in (outer, inner):
        K.subdivide(o, 1)
    # Bottom paint below the waterline on the outside: a second slot by face height.
    M.assign(outer, "out_boat_green")
    M.assign(outer, "out_boat_red")
    for f in outer.data.polygons:
        f.material_index = 1 if f.center.z < 0.13 else 0
    # Normals: the outer skin faces out, the inner faces in (the loft's winding is arbitrary).
    for o, want_out in ((outer, True), (inner, False)):
        bm = bmesh.new()
        bm.from_mesh(o.data)
        flip = []
        for f in bm.faces:
            c = f.calc_center_median()
            out_dir = Vector((c.x, 0, c.z - 0.6)).normalized()
            if (f.normal.dot(out_dir) > 0) != want_out:
                flip.append(f)
        bmesh.ops.reverse_faces(bm, faces=flip)
        bm.to_mesh(o.data)
        bm.free()
    if broken:
        K.jagged_hole(outer, (0.42, 0.35, 0.12), 0.2, ctx.seed, axis=0, jag=0.5)
        K.jagged_hole(inner, (0.42, 0.35, 0.12), 0.18, ctx.seed, axis=0, jag=0.5)
    parts = [(outer, None, dict(uv="box", uv_scale=1.0, smooth=35, patches=0.6, edge=0.6, moss=0.15)),
             (inner, "out_boat_white", dict(uv="box", uv_scale=1.0, smooth=35, patches=0.6, low=0.8, low_h=0.25))]
    # Transom: the stern ring's outline as a board.
    st = ring(1.0)
    poly = [(p[0], p[2]) for p in st]
    tr = K.prism("transom", poly, 0.035, plane="XZ", offset=L / 2 - 0.0175)
    parts.append((tr, "out_boat_white", dict(uv="box", uv_scale=1.0, patches=0.6, edge=1.0)))
    # Gunwale rails and stem.
    for side in (-1, 1):
        pts = []
        for t in ts:
            p = ring(t)[0 if side < 0 else -1]
            pts.append(Vector(p) + Vector((0, 0, 0.012)))
        g = K.tube(f"gunwale{side}", pts, 0.026, segs=6, flat=(1.0, 0.7))
        parts.append((g, "wood_furniture_dark", dict(uv="box", uv_scale=1.5, smooth=45, patches=0.6, edge=1.2)))
    stem = K.tube("stem", [Vector(ring(t)[n_u // 2]) + Vector((0, -0.01, 0)) for t in (0.0, 0.03, 0.08, 0.15)], 0.025, segs=6)
    parts.append((stem, "wood_furniture_dark", dict(uv="box", uv_scale=2.0, smooth=45, edge=1.2)))
    # Thwarts, floorboards.
    for k, (t, z) in enumerate(((0.24, 0.4), (0.5, 0.36), (0.82, 0.38))):
        b = _interp(beam, t)
        zs, zk = _interp(sheer, t), _interp(keel, t)
        au = ((z - zk) / max(0.01, zs - zk)) ** (1 / 1.7)
        half = b * au ** 0.75 - 0.03
        y = -L / 2 + L * t
        th = P.plank(f"thwart{k}", 2 * half, 0.22, 0.026, bevel=0.004, cuts=2)
        if broken and k == 1:
            P.break_end(th, half * 0.2, ctx.drnd("thwart"), side=1, depth=0.1, axis=0)
            K.place(th, rot=(0, -12, 0))
        K.place(th, (0, y, z))
        parts.append((th, "wood_weathered", dict(uv="box", uv_scale=1.0, long_axis=0, patches=0.6, edge=1.2)))
    for k, x in enumerate((-0.16, 0.0, 0.16)):
        fb = P.plank(f"floorboard{k}", 2.1, 0.12, 0.02, bevel=0.003)
        K.place(fb, (0, 0, 0), (0, 0, 90))
        K.place(fb, (x, 0.15, 0.05 + abs(x) * 0.25))
        parts.append((fb, "wood_weathered", dict(uv="box", uv_scale=1.0, long_axis=1, patches=0.6, low=0.5, low_h=0.2)))
    # Oarlocks and oars.
    for side in (-1, 1):
        t = 0.56
        p = Vector(ring(t)[0 if side < 0 else -1])
        lock = K.tube(f"oarlock{side}", [p + Vector((0, -0.05, 0.1)), p + Vector((0, -0.05, 0.03)), p + Vector((0, 0, 0.0)),
                                         p + Vector((0, 0.05, 0.03)), p + Vector((0, 0.05, 0.1))], 0.008, segs=6)
        parts.append((lock, "wild_cast_iron_rust", dict(uv="box", uv_scale=4.0, smooth=40)))
        y0 = -0.95 if side < 0 else -0.85
        shaft = W.rod_obj(f"oar{side}", (side * 0.22, y0, 0.44), (side * 0.3, y0 + 1.75, 0.42), 0.022, segs=8)
        blade = K.box(f"blade{side}", (0.15, 0.52, 0.012), center=(side * 0.31, y0 + 2.0, 0.42), bevel=0.004, cuts=(0, 2, 0))
        K.taper(blade, 1, lambda t: 0.6 + 0.4 * t)
        parts.append((shaft, "wild_lumber_weathered", dict(uv="cyl", uv_axis=0, smooth=45, patches=0.5)))
        parts.append((blade, "wild_lumber_weathered", dict(uv="box", uv_scale=2.0, patches=0.5, edge=1.2)))
    # The painter: a rope from the bow eye coiled on the bow seat.
    bow = Vector((0, -L / 2 + 0.06, _interp(sheer, 0.0) - 0.06))
    coil = K.tube("painter_coil", [Vector((math.cos(a) * 0.12, -1.05 + math.sin(a) * 0.1, 0.44 + a * 0.004))
                                   for a in [i * 0.4 for i in range(40)]], 0.009, segs=5)
    lead = K.tube("painter", [bow, bow + Vector((0, 0.3, -0.05)), Vector((0.08, -1.12, 0.45))], 0.009, segs=5)
    parts.append((coil, "road_rope", dict(uv="box", uv_scale=4.0, smooth=40)))
    parts.append((lead, "road_rope", dict(uv="box", uv_scale=4.0, smooth=40)))
    if swamped:
        water = K.grid("bilge", 1.0, 2.6, 4, 8, center=(0, 0.1, 0.16))
        K.delete_faces(water, lambda p, _n: abs(p.x) > _interp(beam, (p.y + L / 2) / L) * 0.62)
        parts.append((water, "road_water_grey", dict(uv="planar", uv_axis=2, uv_scale=1.0, smooth=None, ao=False)))
    return parts


def _add_parts(ctx, parts, *, loc=(0, 0, 0), rot=None):
    for o, mat, kw in parts:
        if rot is not None:
            K.place(o, (0, 0, 0), rot)
        K.place(o, loc)
        ctx.add(o, mat, **kw)


def out_rowboat(ctx: K.Ctx) -> None:
    """The rental rowboat afloat (its waterline about 0.12 over the keel). Worn: peeling, rainwater
    in the bilge. Destroyed: holed and swamped, a thwart broken (the POI sinks it to the gunwales)."""
    ctx.ground_clamp = False
    parts = _hull_parts(ctx, broken=ctx.destroyed, swamped=ctx.worn)
    _add_parts(ctx, parts)
    ctx.col_box((-0.66, -1.85, 0.0), (0.66, 1.85, 0.62))


def out_rowboat_hauled(ctx: K.Ctx) -> None:
    """A rowboat hauled out upside down on two sawhorses for scraping; a scraper and a paint tin."""
    r = ctx.rnd("hauled")
    for k, y in enumerate((-0.95, 0.95)):
        top = 0.72
        W.bar(ctx, f"horse_beam{k}", (-0.55, y, top - 0.05), (0.55, y, top - 0.05), 0.09, 0.1, "wood_weathered",
              up=(0, 0, 1), bevel=0.006)
        for sx in (-1, 1):
            for sy in (-1, 1):
                W.bar(ctx, f"horse_leg{k}{sx}{sy}", (sx * 0.42, y, top - 0.1), (sx * 0.52, y + sy * 0.22, 0.0), 0.08, 0.04,
                      "wood_weathered", up=(0, 1, 0), bevel=0.005)
    parts = _hull_parts(ctx)
    keep = [p for p in parts if not p[0].name.startswith(("oar", "blade", "painter"))]
    for o, _m, _kw in parts:
        if o.name.startswith(("oar", "blade", "painter")):
            K.remove(o)
    _add_parts(ctx, keep, loc=(0, 0, 0.72 + 0.74), rot=(0, 180, 0))
    scr = K.box("scraper", (0.08, 0.2, 0.01), center=(0.45, -1.3, 0.005), bevel=0.002)
    ctx.add(scr, "road_steel", uv="box", uv_scale=4.0)
    tin = K.cyl("paint_tin", 0.085, 0.12, segs=14, center=(-0.5, 1.35, 0.06))
    ctx.add(tin, "metal_galvanized", uv="cyl", uv_scale=4.0, smooth=40, patches=0.5)
    ctx.col_box((-0.68, -1.85, 0.0), (0.68, 1.85, 1.38))


def out_fishing_rod(ctx: K.Ctx) -> None:
    """A spinning rod lying on its side: tapered blank, cork grip, reel seat, an open-face reel and
    snake guides; worn: the tip snapped off and the line tangled."""
    blank = K.tube("blank", [(-0.62, 0, 0.012), (0.2, 0, 0.011), (0.97, 0, 0.006)], [0.0065, 0.0042, 0.0016], segs=8)
    ctx.add(blank, "plastic_black", uv="cyl", uv_axis=0, smooth=40, patches=0.3)
    grip = K.tube("grip", [(-0.97, 0, 0.012), (-0.8, 0, 0.012), (-0.68, 0, 0.012)], [0.011, 0.012, 0.0095], segs=10)
    ctx.add(grip, "furn_cork", uv="cyl", uv_axis=0, uv_scale=4.0, smooth=50, patches=0.6)
    seat = K.cyl("seat", 0.009, 0.08, segs=10, axis="X", center=(-0.63, 0, 0.012))
    ctx.add(seat, "chrome_pitted", uv="cyl", uv_axis=0, smooth=40)
    # Reel hanging off the seat, sideways (+Y) since the rod lies on its side.
    foot = K.box("reel_foot", (0.05, 0.05, 0.006), center=(-0.63, 0.03, 0.012))
    spool = K.cyl("spool", 0.024, 0.03, segs=14, axis="X", center=(-0.6, 0.06, 0.03))
    body = K.blob("reel_body", 0.022, subdiv=2, scale=(1.2, 0.8, 1.0), center=(-0.63, 0.062, 0.03))
    crank = K.tube("crank", [(-0.64, 0.062, 0.03), (-0.64, 0.1, 0.03), (-0.64, 0.1, 0.07)], 0.003, segs=5)
    ctx.add(K.merge_parts([foot, spool, body, crank], "reel"), "road_alu", uv="box", uv_scale=6.0, smooth=40, patches=0.5)
    line = K.cyl("line_spool", 0.02, 0.026, segs=14, axis="X", center=(-0.6, 0.06, 0.03))
    ctx.add(line, "out_net", uv="cyl", uv_axis=0, uv_scale=8.0, smooth=40)
    for k, x in enumerate((-0.4, -0.15, 0.08, 0.3, 0.5, 0.68, 0.83, 0.95)):
        if ctx.worn and x > 0.8:
            continue
        rad = 0.012 - k * 0.001
        g = K.tube(f"guide{k}", [(x, 0.0, 0.012), (x, 0.0, 0.012 + rad), (x + 0.01, 0.0, 0.012 + 2 * rad)], 0.0012, segs=4)
        ctx.add(g, "chrome_pitted", uv="box", uv_scale=8.0, smooth=40)
    if ctx.worn:
        tip = K.tube("tip", [(0.84, 0.02, 0.004), (0.97, 0.07, 0.004)], 0.0016, segs=6)
        ctx.add(tip, "plastic_black", uv="cyl", uv_axis=0, smooth=40)
        tangle = K.tube("tangle", [Vector((0.6 + 0.08 * math.cos(a), 0.04 + 0.05 * math.sin(a * 1.3), 0.004 + 0.002 * math.sin(a * 3)))
                                   for a in [i * 0.5 for i in range(30)]], 0.0008, segs=3, caps=False)
        ctx.add(tangle, "out_net", uv="box", uv_scale=8.0, smooth=40)


def out_boat_doors(ctx: K.Ctx) -> None:
    """The boathouse's water doors over the slip mouth (4 m): two board-and-batten leaves hung on
    jamb posts under a header with a fascia up to the loft floor; battens and Z-braces on the
    inside (-Y), strap hinges outside (+Y); weed on the bottom boards. Worn: the east leaf swung
    out and sagging, boards gone from the west one. The lake is at z -0.2 (placed y = -0.4)."""
    r = ctx.rnd("bdoors")
    ctx.ground_clamp = False
    for x in (-2.02, 2.02):
        W.bar(ctx, f"jamb{x}", (x, 0.0, -0.6), (x, 0.0, 3.0), 0.16, 0.16, "wood_creosote", up=(1, 0, 0), bevel=0.01,
              low=0.6, low_h=0.8)
    W.bar(ctx, "header", (-2.3, 0.0, 2.92), (2.3, 0.0, 2.92), 0.2, 0.18, "wood_weathered", up=(0, 0, 1), bevel=0.01)
    fascia = K.box("fascia", (4.6, 0.03, 0.55), center=(0, 0.1, 3.27), cuts=(8, 0, 1))
    ctx.add(fascia, "wood_weathered", uv="box", uv_scale=1.0, patches=0.5, moss=0.3)
    for side in (-1, 1):
        hinge_x = side * 1.94
        leaf = []
        n = 13
        for k in range(n):
            if ctx.worn and side < 0 and k in (4, 9):
                continue
            x = hinge_x - side * (0.075 + k * 0.148)
            bd = P.plank(f"board{side}{k}", 2.62 + r.uniform(-0.02, 0.02), 0.14, 0.022, bevel=0.003, cuts=2)
            K.place(bd, rot=(90, -90, 0))
            K.place(bd, (x, 0.04, 0.14 + 1.31))
            leaf.append(ctx.add(bd, "wood_weathered", uv="box", uv_scale=1.0, long_axis=2, patches=0.6, edge=1.0,
                                moss=0.4, low=1.0, low_h=0.5))
        x_in, x_out = hinge_x - side * 0.04, hinge_x - side * 1.9
        for z in (0.45, 1.45, 2.45):
            leaf.append(W.bar(ctx, f"batten{side}{z}", (x_in, 0.01, z), (x_out, 0.01, z), 0.14, 0.025, "wood_weathered",
                              up=(0, 1, 0), bevel=0.004, patches=0.5))
        for k, (z0, z1) in enumerate(((0.5, 1.4), (1.5, 2.4))):
            leaf.append(W.bar(ctx, f"zbrace{side}{k}", (x_out, 0.012, z0), (x_in, 0.012, z1), 0.12, 0.022, "wood_weathered",
                              up=(0, 1, 0), bevel=0.004))
        for z in (0.45, 2.45):
            st = K.box(f"strap{side}{z}", (0.6, 0.006, 0.05), center=(hinge_x - side * 0.25, 0.058, z), bevel=0.002)
            leaf.append(ctx.add(st, "wild_cast_iron_rust", uv="box", uv_scale=4.0, patches=0.6))
        if ctx.worn and side > 0:
            # Swung out over the lake on its hinges, the free end sagging.
            _swing(leaf, (hinge_x, 0.06, 0.0), -62)
            K.kink(leaf, (hinge_x, 0.0, 0.0), (0, -2.5, 0), axis=2, blend=3.0)
    # The hasp in the middle (closed) and a boom log chained across the slip at the water.
    hasp = K.box("hasp", (0.12, 0.012, 0.05), center=(0.0, 0.065, 1.4), bevel=0.003)
    ctx.add(hasp, "wild_cast_iron_rust", uv="box", uv_scale=4.0)
    boom = W.log_obj("boom", 4.2, 0.13, ctx.seed + 9, sides=9, rings=4, bark="out_algae", end="wood_log_end")
    K.orient(boom, Vector((1, 0, 0)), Vector((0, 0, 1)), (0, 0.55, -0.22))
    ctx.add(boom, None, uv=None, smooth=45, patches=0.5)


def out_bait_tank(ctx: K.Ctx) -> None:
    """A fibreglass minnow tank on a galvanized stand: water inside with an aerator bubbling, a hinged
    lid half up, a dip net on the rim. Worn: grime line, lid off on the floor. Destroyed: cracked
    and dry, the stand buckled."""
    r = ctx.rnd("tank")
    w, d, h = 1.2, 0.58, 0.52
    z0 = 0.38
    tilt = 4.0 if ctx.destroyed else 0.0
    parts0 = len(ctx.parts)
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.rod(ctx, f"leg{sx}{sy}", (sx * (w / 2 - 0.05), sy * (d / 2 - 0.05), 0.0),
                  (sx * (w / 2 - 0.05), sy * (d / 2 - 0.05), z0), 0.018, "metal_galvanized", segs=8, patches=0.6)
    for sy in (-1, 1):
        W.rod(ctx, f"rail{sy}", (-w / 2 + 0.05, sy * (d / 2 - 0.05), 0.12), (w / 2 - 0.05, sy * (d / 2 - 0.05), 0.12), 0.012,
              "metal_galvanized", segs=6)
    shell = K.box("tank", (w, d, h), center=(0, 0, z0 + h / 2), bevel=0.05, bevel_segs=3, cuts=(3, 2, 2))
    inner = K.box("tank_in", (w - 0.06, d - 0.06, h), center=(0, 0, z0 + h / 2 + 0.03), bevel=0.04, bevel_segs=2)
    K.delete_faces(inner, lambda p, n: n.z > 0.9)
    # The liner is seen from inside the tank: turn its faces inward.
    bm = bmesh.new()
    bm.from_mesh(inner.data)
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(inner.data)
    bm.free()
    K.delete_faces(shell, lambda p, n: n.z > 0.9 and abs(p.x) < w / 2 - 0.03 and abs(p.y) < d / 2 - 0.03)
    if ctx.destroyed:
        K.dent(shell, (0.35, -d / 2, z0 + 0.25), 0.18, 0.04, (0, 1, 0))
    ctx.add(shell, "plastic_white", uv="box", uv_scale=1.0, smooth=40, patches=0.6, low=0.6, low_h=0.6)
    ctx.add(inner, "plastic_white", uv="box", uv_scale=1.0, smooth=40, patches=0.7, base=0.25)
    rim = K.tube("rim", [(-w / 2 + 0.02, -d / 2 + 0.02, z0 + h), (w / 2 - 0.02, -d / 2 + 0.02, z0 + h),
                         (w / 2 - 0.02, d / 2 - 0.02, z0 + h), (-w / 2 + 0.02, d / 2 - 0.02, z0 + h)], 0.022, segs=6,
                 closed=True)
    ctx.add(rim, "plastic_white", uv="box", uv_scale=2.0, smooth=40, patches=0.6)
    if not ctx.destroyed:
        water = K.grid("water", w - 0.07, d - 0.07, 6, 3, center=(0, 0, z0 + h - 0.1))
        K.noise_disp(water, 0.004, scale=6.0, seed=ctx.seed, along_normal=False)
        ctx.add(water, "road_water_grey", uv="planar", uv_axis=2, smooth=60, ao=False)
        for k in range(9):
            b = K.blob(f"bubble{k}", 0.008, subdiv=1, center=(0.4 + r.uniform(-0.05, 0.05), r.uniform(-0.1, 0.1),
                                                              z0 + h - 0.095))
            ctx.add(b, "plastic_white", uv="box", uv_scale=4.0, smooth=60, ao=False)
        pump = K.box("pump", (0.16, 0.1, 0.1), center=(0.42, d / 2 + 0.02, z0 + h + 0.05), bevel=0.01)
        ctx.add(pump, "plastic_grey", uv="box", uv_scale=4.0, smooth=40, patches=0.5)
        hose = K.tube("air_hose", [(0.4, d / 2 + 0.02, z0 + h + 0.04), (0.4, d / 2 - 0.08, z0 + h + 0.06),
                                   (0.4, 0.0, z0 + h - 0.05), (0.4, 0.0, z0 + 0.06)], 0.006, segs=5)
        ctx.add(hose, "plastic_black", uv="box", uv_scale=4.0, smooth=40)
    lid = K.box("lid", (w / 2 - 0.02, d - 0.02, 0.02), center=(0, 0, 0), bevel=0.006)
    if ctx.worn:
        K.place(lid, (-0.3, -d / 2 - 0.45, 0.012), (0, 0, 20))
    else:
        K.place(lid, (0, 0, 0), (0, -55, 0))
        K.place(lid, (-w / 4 - 0.13, 0, z0 + h + 0.22))
    ctx.add(lid, "plastic_white", uv="box", uv_scale=1.0, patches=0.6, edge=1.0)
    net = K.tube("net_handle", [(w / 2 - 0.08, -0.18, z0 + h - 0.05), (w / 2 + 0.25, -0.2, z0 + h + 0.35)], 0.008, segs=6)
    hoop = K.tube("net_hoop", [Vector((w / 2 - 0.12 + 0.1 * math.cos(a), -0.18 + 0.1 * math.sin(a), z0 + h - 0.06))
                               for a in [i * math.tau / 12 for i in range(12)]], 0.004, segs=4, closed=True)
    ctx.add(K.merge_parts([net, hoop], "dipnet"), "road_alu", uv="box", uv_scale=4.0, smooth=40)
    bag = K.blob("net_bag", 0.09, subdiv=2, scale=(1.0, 1.0, 1.3), center=(w / 2 - 0.12, -0.18, z0 + h - 0.16))
    ctx.add(bag, "out_net", uv="box", uv_scale=6.0, smooth=50)
    if tilt:
        K.kink(ctx.parts[parts0:], (0, 0, 0), (tilt, 0, 0), axis=2, blend=0.4)
    ctx.col_box((-w / 2, -d / 2, 0), (w / 2, d / 2, z0 + h))


def out_tackle_wall(ctx: K.Ctx) -> None:
    """A pegboard of tackle on the shop wall (2 x 1.5 m, wall-mounted, origin on the wall): rows of
    carded lures on hooks, spools of line on a rod, a shelf of boxes below. Worn: half the cards
    gone, a few on the floor... (they lie at the base, z >= 0)."""
    r = ctx.rnd("tackle")
    pb = K.box("pegboard", (2.0, 0.012, 1.4), center=(0, -0.026, 0.75), cuts=(4, 0, 3))
    ctx.add(pb, "furn_pegboard", uv="planar", uv_axis=1, uv_scale=1.0, patches=0.4)
    for x in (-0.98, 0.98):
        W.bar(ctx, f"frame{x}", (x, -0.03, 0.04), (x, -0.03, 1.46), 0.04, 0.03, "wood_furniture_dark", up=(0, 1, 0), bevel=0.004)
    for z in (0.04, 1.46):
        W.bar(ctx, f"frameh{z}", (-1.0, -0.03, z), (1.0, -0.03, z), 0.04, 0.03, "wood_furniture_dark", up=(0, 1, 0), bevel=0.004)
    lbl = _face(ctx, "label_band", 1.9, 0.12, _rect("tackle_labels"), (0, -0.034, 1.37))
    cards = 0
    for row, z in enumerate((1.12, 0.86, 0.6)):
        for k in range(9):
            x = -0.86 + k * 0.215
            if ctx.worn and ctx.drnd(f"c{row}{k}").random() < 0.45:
                continue
            hook = K.tube(f"peg{row}{k}", [(x, -0.03, z + 0.1), (x, -0.13, z + 0.12)], 0.003, segs=4)
            ctx.add(hook, "chrome_pitted", uv="box", uv_scale=6.0, smooth=40)
            for j in range(r.randint(1, 3)):
                ci = r.randrange(8)
                card = K.quad_sheet(f"card{row}{k}{j}", (-0.06, 0, -0.1), (0.06, 0, -0.1), (0.06, 0, 0.06), (-0.06, 0, 0.06))
                K.uv_planar(card, 1, rect=_rect("lure_cards", ((ci % 4) / 4, (ci // 4) / 2, (ci % 4 + 1) / 4, (ci // 4 + 1) / 2)))
                K.place(card, (0, 0, 0), (r.uniform(-4, 4), 0, 0))
                K.place(card, (x, -0.05 - j * 0.025, z + 0.06))
                ctx.add(card, SIGNS, uv=None, patches=0.3)
                cards += 1
    # Spools of line on a dowel, a shelf with boxes of hooks and sinkers.
    W.rod(ctx, "dowel", (-0.9, -0.08, 0.32), (-0.2, -0.08, 0.32), 0.008, "wood_furniture_dark")
    for k in range(6):
        if ctx.worn and k in (1, 4):
            continue
        sp = K.lathe(f"spool{k}", [(0.035, -0.03), (0.035, -0.026), (0.026, -0.024), (0.026, 0.024), (0.035, 0.026),
                                   (0.035, 0.03)], segs=14, cap_bottom=True, cap_top=True)
        K.place(sp, (0, 0, 0), (0, 90, 0))
        K.place(sp, (-0.84 + k * 0.11, -0.08, 0.32))
        ctx.add(sp, ["plastic_white", "plastic_blue", "plastic_red", "plastic_yellow"][k % 4], uv="box", uv_scale=6.0,
                smooth=40)
    W.bar(ctx, "shelf", (-0.05, -0.12, 0.2), (0.95, -0.12, 0.2), 0.18, 0.02, "wood_furniture_dark", up=(0, 0, 1),
          bevel=0.003)
    for k in range(5):
        bx = K.box(f"box{k}", (0.15, 0.1, 0.06 + 0.03 * (k % 2)), center=(0.05 + k * 0.19, -0.12, 0.24 + 0.015 * (k % 2)),
                   bevel=0.004)
        ctx.add(bx, ["cardboard", "plastic_red", "cardboard", "plastic_grey", "cardboard"][k], uv="box", uv_scale=3.0,
                patches=0.5)


def out_rod_rack(ctx: K.Ctx) -> None:
    """A pine floor rack with eight rods standing in it (butts in the base holes, blanks in the top
    rail's notches). Worn: three rods gone. Destroyed: the rack knocked flat, rods across the floor."""
    r = ctx.rnd("rack")
    parts0 = len(ctx.parts)
    base = K.box("base", (1.1, 0.4, 0.08), center=(0, 0, 0.04), bevel=0.01, cuts=(4, 1, 0))
    ctx.add(base, "wood_stained", uv="box", uv_scale=1.0, patches=0.5, edge=1.0)
    for x in (-0.52, 0.52):
        W.bar(ctx, f"upright{x}", (x, 0.12, 0.08), (x, 0.12, 1.3), 0.05, 0.05, "wood_stained", up=(1, 0, 0), bevel=0.005)
    rail = K.box("rail", (1.1, 0.12, 0.05), center=(0, 0.1, 1.25), bevel=0.008)
    ctx.add(rail, "wood_stained", uv="box", uv_scale=1.0, patches=0.5, edge=1.0)
    for k in range(8):
        if ctx.worn and k in (1, 4, 6):
            continue
        x = -0.44 + k * 0.125
        L = r.uniform(1.75, 1.95)
        top = Vector((x + r.uniform(-0.02, 0.02), 0.1 + r.uniform(-0.02, 0.02), 0.06 + L))
        blank = K.tube(f"rod{k}", [Vector((x, 0.0, 0.06)), Vector((x, 0.05, 1.25)), top], [0.007, 0.0045, 0.0018], segs=6)
        ctx.add(blank, ["plastic_black", "road_plastic_brown", "plastic_black", "road_plastic_green"][k % 4], uv="cyl", uv_axis=2,
                smooth=40)
        grip = K.cyl(f"grip{k}", 0.012, 0.3, segs=8, center=(x, 0.0, 0.25))
        ctx.add(grip, "furn_cork", uv="cyl", uv_scale=4.0, smooth=40, patches=0.5)
        if k % 2 == 0:
            reel = K.blob(f"reel{k}", 0.025, subdiv=1, scale=(1.0, 1.3, 1.0), center=(x, -0.045, 0.45))
            ctx.add(reel, "road_alu", uv="box", uv_scale=6.0, smooth=40, patches=0.5)
    if ctx.destroyed:
        K.kink(ctx.parts[parts0:], (0, -0.25, 0.0), (82, 0, 8), axis=0, blend=0.001)
        for o in ctx.parts[parts0:]:
            K.lift_min(o, 0.0)
    if ctx.destroyed:
        ctx.col_box((-0.6, -2.0, 0), (0.6, 0.3, 0.45))
    else:
        ctx.col_box((-0.55, -0.2, 0), (0.55, 0.2, 1.3))


def _vest_parts(ctx, name, seed, at, yaw, tilt):
    """One kapok life vest lying face up: a back panel, two front panels either side of the zip
    gap (a V at the neck), the collar roll, two webbing straps with buckles across the front."""
    rr = random.Random(seed)
    pads = []
    back = K.box(f"{name}_back", (0.44, 0.52, 0.045), center=(0, 0, 0.023), bevel=0.02, bevel_segs=2, cuts=(2, 2, 0))
    pads.append(back)
    for sx in (-1, 1):
        fr = K.box(f"{name}_front{sx}", (0.19, 0.42, 0.06), center=(sx * 0.115, -0.04, 0.075), bevel=0.026, bevel_segs=2,
                   cuts=(1, 3, 0))
        # The V-neck: the inner top corner of each front panel cut away.
        K.cut_plane(fr, (sx * 0.02, 0.17, 0), Vector((-sx * 0.8, 1.0, 0.0)).normalized(), keep="below")
        pads.append(fr)
    collar = K.tube(f"{name}_collar", [(-0.17, 0.2, 0.06), (-0.09, 0.26, 0.07), (0.09, 0.26, 0.07), (0.17, 0.2, 0.06)], 0.034,
                    segs=8)
    pads.append(collar)
    vest = K.merge_parts(pads, name)
    K.noise_disp(vest, 0.007, scale=6.0, seed=seed)
    straps = []
    for k, y in enumerate((-0.06, -0.19)):
        st = K.box(f"{name}_strap{k}", (0.44, 0.032, 0.006), center=(0, y, 0.108), cuts=(4, 0, 0))
        K.map_verts(st, lambda co: Vector((co.x, co.y, co.z - 0.02 * (abs(co.x) / 0.22) ** 2)))
        buckle = K.box(f"{name}_buckle{k}", (0.05, 0.04, 0.012), center=(rr.uniform(-0.03, 0.03), y, 0.112), bevel=0.003)
        straps += [st, buckle]
    sm = K.merge_parts(straps, f"{name}_straps")
    for o in (vest, sm):
        K.place(o, (0, 0, 0), (tilt[0], tilt[1], yaw))
        K.place(o, at)
    ctx.add(vest, "out_kapok_orange", uv="box", uv_scale=2.0, smooth=50, patches=0.6, low=0.5, low_h=0.1)
    ctx.add(sm, "nylon_navy", uv="box", uv_scale=4.0, smooth=30, patches=0.5)


def out_life_jackets(ctx: K.Ctx) -> None:
    """A heap of orange kapok life vests, straps and buckles across them (walk-over clutter)."""
    r = ctx.rnd("vests")
    n = 6 if ctx.clean else 5
    for k in range(n):
        at = (r.uniform(-0.36, 0.36), r.uniform(-0.26, 0.26), 0.02 + k * 0.05)
        _vest_parts(ctx, f"vest{k}", ctx.seed + k, at, r.uniform(0, 360), (r.uniform(-12, 12), r.uniform(-12, 12)))
    for o in ctx.parts:
        K.lift_min(o, 0.0)


def out_outboard_motor(ctx: K.Ctx) -> None:
    """A 9.9 hp outboard clamped to a wooden motor stand: blue cowling with its decal, midsection,
    lower unit with skeg and a three-blade prop, tiller arm. Worn: chipped, the prop nicked.
    Destroyed: cowling off on the floor, the powerhead open, the prop gone."""
    r = ctx.rnd("outboard")
    # Stand: an A-frame sawhorse with a transom board at the top.
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.bar(ctx, f"leg{sx}{sy}", (sx * 0.24, sy * 0.08, 1.0), (sx * 0.33, sy * 0.4, 0.0), 0.07, 0.035, "wood_weathered",
                  up=(1, 0, 0), bevel=0.004)
    W.bar(ctx, "transom", (-0.36, 0.0, 0.93), (0.36, 0.0, 0.93), 0.05, 0.2, "wood_weathered", up=(0, 0, 1), bevel=0.006)
    W.bar(ctx, "spreader", (-0.3, 0.0, 0.35), (0.3, 0.0, 0.35), 0.05, 0.04, "wood_weathered", up=(0, 0, 1), bevel=0.004)
    # Motor: clamp bracket over the transom (motor hangs at -Y).
    y = -0.12
    clamp = K.box("clamp", (0.18, 0.12, 0.22), center=(0, -0.04, 0.98), bevel=0.012)
    ctx.add(clamp, "out_outboard_blue", uv="box", uv_scale=3.0, patches=0.6, edge=1.2)
    for sx in (-1, 1):
        sc = K.tube(f"screw{sx}", [(sx * 0.06, 0.1, 0.92), (sx * 0.06, 0.06, 0.92)], 0.008, segs=6)
        hd = K.box(f"screwhd{sx}", (0.07, 0.015, 0.025), center=(sx * 0.06, 0.11, 0.92), bevel=0.004)
        ctx.add(K.merge_parts([sc, hd], f"clampscrew{sx}"), "road_steel", uv="box", uv_scale=4.0, smooth=40)
    mid = K.box("midsection", (0.13, 0.16, 0.62), center=(0, y, 0.6), bevel=0.03, bevel_segs=2)
    ctx.add(mid, "out_outboard_blue", uv="box", uv_scale=2.0, smooth=35, patches=0.6, edge=1.0)
    lower = K.box("lower_unit", (0.1, 0.26, 0.2), center=(0, y - 0.02, 0.22), bevel=0.035, bevel_segs=2)
    ctx.add(lower, "out_outboard_blue", uv="box", uv_scale=2.0, smooth=35, patches=0.7, edge=1.2)
    torp = K.lathe("torpedo", [(0.0, -0.17), (0.04, -0.14), (0.055, -0.06), (0.055, 0.1), (0.035, 0.16), (0.0, 0.18)],
                   segs=12)
    K.place(torp, (0, 0, 0), (90, 0, 0))
    K.place(torp, (0, y - 0.02, 0.15))
    ctx.add(torp, "out_outboard_blue", uv="box", uv_scale=2.0, smooth=40, patches=0.7, edge=1.2)
    skeg = K.prism("skeg", [(-0.06, 0.0), (0.08, 0.0), (0.04, 0.09), (-0.06, 0.09)], 0.012, plane="YZ")
    K.place(skeg, (0, 0, 0), (0, 0, 90))
    K.place(skeg, (0, y - 0.02, 0.0))
    ctx.add(skeg, "road_steel", uv="box", uv_scale=4.0, patches=0.6, edge=1.2)
    if not ctx.destroyed:
        hub = K.cyl("prop_hub", 0.03, 0.08, segs=10, axis="Y", center=(0, y + 0.17, 0.15))
        ctx.add(hub, "road_steel", uv="box", uv_scale=4.0, smooth=40)
        for k in range(3):
            bl = K.box(f"blade{k}", (0.07, 0.012, 0.13), center=(0, 0, 0.08), bevel=0.01, cuts=(1, 0, 2))
            K.taper(bl, 2, lambda t: 1.0 - 0.3 * abs(t))
            K.place(bl, (0, 0, 0), (0, k * 120 + 15, 0))
            K.place(bl, (0, 0, 0), (0, 0, 0))
            K.place(bl, (0, y + 0.18, 0.15), (25, 0, 0))
            if ctx.worn and k == 1:
                K.cut_plane(bl, (0, y + 0.18, 0.23), (0, 0.2, 1), keep="below")
            ctx.add(bl, "road_steel", uv="box", uv_scale=4.0, smooth=30, patches=0.6, edge=1.4)
    # Cowling over the powerhead (or on the floor, destroyed).
    head = K.box("powerhead", (0.28, 0.4, 0.26), center=(0, y - 0.03, 1.06), bevel=0.04, bevel_segs=2)
    ctx.add(head, "wild_cast_iron" if ctx.destroyed else "out_outboard_blue", uv="box", uv_scale=2.0, smooth=35, patches=0.6)
    cowl = K.box("cowling", (0.34, 0.48, 0.3), center=(0, 0, 0.15), bevel=0.09, bevel_segs=3, cuts=(1, 1, 1))
    K.map_verts(cowl, lambda co: Vector((co.x * (1.0 - 0.12 * max(0.0, co.z - 0.15) / 0.15), co.y, co.z)))
    if ctx.destroyed:
        K.place(cowl, (0, 0, 0), (180, 0, 30))
        K.place(cowl, (0.08, -0.45, 0.3))
        K.dent(cowl, (0.1, -0.5, 0.2), 0.12, 0.03)
    else:
        K.place(cowl, (0, y - 0.03, 1.05))
    ctx.add(cowl, "out_outboard_blue", uv="box", uv_scale=2.0, smooth=35, patches=0.6, edge=1.0)
    if not ctx.destroyed:
        _face(ctx, "decal_l", 0.3, 0.1, _rect("motor_decal"), (0.171, y - 0.03, 1.27), 90, wear=0.4)
        _face(ctx, "decal_r", 0.3, 0.1, _rect("motor_decal"), (-0.171, y - 0.03, 1.27), -90, wear=0.4)
    else:
        for k in range(4):
            pl = K.cyl(f"plug{k}", 0.008, 0.07, segs=6, axis="X", center=(r.uniform(-0.3, 0.3), r.uniform(-0.4, 0.3), 0.008))
            ctx.add(pl, "road_steel", uv="box", uv_scale=6.0, smooth=40)
    tiller = K.tube("tiller", [(0, y + 0.08, 1.0), (0, y + 0.3, 1.0), (0, y + 0.52, 0.98)], [0.025, 0.022, 0.02], segs=8)
    ctx.add(tiller, "plastic_black", uv="box", uv_scale=3.0, smooth=40, patches=0.5)
    ctx.col_box((-0.36, -0.42, 0), (0.36, 0.42, 1.35))


def out_net_pile(ctx: K.Ctx) -> None:
    """A heap of gill net with a cork line strung over it and a coil of rope; worn: weed in it."""
    r = ctx.rnd("net")
    heap = K.blob("heap", 0.5, subdiv=3, scale=(1.45, 1.1, 0.42), center=(0, 0, 0.0), rough=0.35, seed=ctx.seed,
                  noise_scale=2.4)
    # Folds: ridges of net dragged over the heap, then a fine crumple.
    for k in range(5):
        a = r.uniform(0, math.pi)
        c = Vector((r.uniform(-0.4, 0.4), r.uniform(-0.3, 0.3), 0))
        d = Vector((math.cos(a), math.sin(a), 0))
        amp = r.uniform(0.03, 0.06)
        K.map_verts(heap, lambda co, c=c, d=d, amp=amp: co + Vector((0, 0, amp * max(0.0, co.z) / 0.2 *
                                                                      math.exp(-((co - c).cross(d).length / 0.12) ** 2))))
    K.crumple(heap, 0.035, scale=9.0, seed=ctx.seed)
    ctx.add(heap, "out_net", uv="box", uv_scale=3.0, smooth=60, patches=0.5, moss=0.5 if ctx.worn else 0.2)
    for k in range(4):
        lump = K.blob(f"lump{k}", r.uniform(0.12, 0.2), subdiv=2, scale=(1.6, 1.0, 0.5), rough=0.4, seed=ctx.seed + 10 + k)
        K.crumple(lump, 0.02, scale=9.0, seed=k)
        a = r.uniform(0, math.tau)
        K.place(lump, (math.cos(a) * 0.62, math.sin(a) * 0.45, 0.02), (0, 0, math.degrees(a)))
        ctx.add(lump, "out_net", uv="box", uv_scale=3.0, smooth=60, patches=0.5)
    pts = []
    for k in range(14):
        t = k / 13
        a = -1.2 + 2.4 * t
        x = 0.68 * math.sin(a)
        y = 0.42 * math.cos(a * 1.3) - 0.1
        z = max(0.03, 0.21 * (1 - (x / 0.72) ** 2 - (y / 0.55) ** 2) + 0.015)
        pts.append(Vector((x, y, z)))
    line = K.tube("corkline", pts, 0.006, segs=4)
    ctx.add(line, "road_rope", uv="box", uv_scale=4.0, smooth=40)
    for k, p in enumerate(pts[1:-1]):
        c = K.blob(f"cork{k}", 0.035, subdiv=1, scale=(1.0, 1.6, 0.8), center=p + Vector((0, 0, 0.01)))
        ctx.add(c, "out_cork", uv="box", uv_scale=4.0, smooth=50, patches=0.5)
    coil = K.tube("rope_coil", [Vector((0.55 + 0.17 * math.cos(a), -0.42 + 0.14 * math.sin(a), 0.015 + a * 0.0035))
                                for a in [i * 0.35 for i in range(60)]], 0.012, segs=5)
    ctx.add(coil, "road_rope", uv="box", uv_scale=4.0, smooth=40, patches=0.5)


def out_bait_sign(ctx: K.Ctx) -> None:
    """The roadside sign: a plywood panel (LARCH POND BAIT & BOAT, a jumping trout) on two 4x4
    posts, a BOAT RENTAL board hung under it on S-hooks. Worn: weathered, the board hanging by one
    hook, a post out of true."""
    r = ctx.rnd("baitsign")
    lean = 3.0 if ctx.worn else 0.0
    parts0 = len(ctx.parts)
    for x in (-1.15, 1.15):
        W.bar(ctx, f"post{x}", (x, 0.04, 0.0), (x, 0.04, 2.55), 0.09, 0.09, "wood_weathered", up=(1, 0, 0), bevel=0.008,
              low=0.8, low_h=0.5, moss=0.3)
        cap = K.prism(f"cap{x}", [(-0.05, 0.0), (0.05, 0.0), (0.0, 0.05)], 0.1, plane="XZ")
        K.place(cap, (x, 0.04, 2.55))
        ctx.add(cap, "wood_weathered", uv="box", uv_scale=2.0, patches=0.5)
    panel = K.box("panel", (2.44, 0.025, 0.82), center=(0, -0.02, 2.0), bevel=0.004, cuts=(4, 0, 2))
    ctx.add(panel, "road_plywood", uv="box", uv_scale=1.0, patches=0.5, edge=1.0)
    _face(ctx, "face", 2.4, 0.8, _rect("bait_sign"), (0, -0.034, 2.0), wear=0.8)
    for x in (-1.24, 1.24):
        W.bar(ctx, f"edge{x}", (x, -0.02, 1.58), (x, -0.02, 2.42), 0.04, 0.04, "paint_white_wood", up=(0, 1, 0), bevel=0.004)
    board = K.box("rental_board", (1.4, 0.02, 0.35), center=(0, 0, 0), bevel=0.003)
    face = K.quad_sheet("rental_face", (-0.69, 0, -0.17), (0.69, 0, -0.17), (0.69, 0, 0.17), (-0.69, 0, 0.17), 2, 1)
    K.uv_planar(face, 1, rect=_rect("boat_rental"))
    K.place(face, (0, -0.011, 0))
    hang = (0, 0, -14) if ctx.worn else (0, 0, 0)
    for o in (board, face):
        K.place(o, (0, 0, 0), (0, hang[2], 0))
        K.place(o, (0.05 if ctx.worn else 0.0, -0.03, 1.36 if not ctx.worn else 1.31))
    ctx.add(board, "road_plywood", uv="box", uv_scale=1.0, patches=0.5)
    ctx.add(face, SIGNS, uv=None, patches=0.4)
    for x in (-0.6, 0.6):
        if ctx.worn and x > 0:
            continue
        hk = K.tube(f"hook{x}", [(x, -0.03, 1.59), (x, -0.045, 1.56), (x, -0.03, 1.53)], 0.004, segs=4)
        ctx.add(hk, "wild_cast_iron_rust", uv="box", uv_scale=6.0, smooth=40)
    if lean:
        K.kink(ctx.parts[parts0:], (0, 0, 0), (lean, 0, -2.0), axis=2, blend=0.3)
    ctx.col_box((-1.25, -0.08, 0), (1.25, 0.1, 2.5))


def out_trophy_fish(ctx: K.Ctx) -> None:
    """A varnished pike on an oak plaque (wall-mounted, 0.85 m): lofted body, fins, a toothy jaw
    and glass eyes (worn: one gone, the varnish crazed)."""
    plaque = K.box("plaque", (0.85, 0.025, 0.3), center=(0, -0.0125, 0.16), bevel=0.012, bevel_segs=2)
    ctx.add(plaque, "wood_furniture_dark", uv="box", uv_scale=2.0, patches=0.4, edge=1.0)
    rings = []
    n = 14
    for i in range(n):
        t = i / (n - 1)
        x = -0.38 + 0.74 * t
        hh = 0.075 * math.sin(math.pi * min(1.0, t * 1.05)) ** 0.6 * (1 - 0.35 * t) + 0.006
        ww = 0.04 * math.sin(math.pi * min(1.0, t * 1.05)) ** 0.7 + 0.004
        ring = [(x, -0.03 - ww * (1 + math.cos(a)) * 0.5 - 0.004, 0.16 + hh * math.sin(a)) for a in
                [j * math.tau / 10 for j in range(10)]]
        rings.append(ring)
    body = K.loft("pike", rings, closed_ring=True, cap_start=True, cap_end=True)
    ctx.add(body, "out_pike", uv="box", uv_scale=4.0, smooth=50, patches=0.4)
    tail = K.prism("tail", [(0.0, -0.06), (0.12, -0.1), (0.09, 0.0), (0.12, 0.1), (0.0, 0.06)], 0.006, plane="XZ")
    K.place(tail, (0.35, -0.035, 0.16))
    fins = [tail]
    for k, (x, z, s) in enumerate(((0.12, 0.23, 1.0), (0.1, 0.09, -1.0), (-0.12, 0.1, -0.7))):
        f = K.prism(f"fin{k}", [(0.0, 0.0), (0.07, 0.0), (0.03, 0.05 * s)], 0.005, plane="XZ")
        K.place(f, (x, -0.04, z))
        fins.append(f)
    ctx.add(K.merge_parts(fins, "fins"), "out_pike", uv="box", uv_scale=6.0, smooth=40, patches=0.5)
    if ctx.worn:
        # The glass eye has gone: an empty socket.
        hole = K.cyl("eye_hole", 0.008, 0.004, segs=8, axis="Y", center=(-0.33, -0.073, 0.175))
        ctx.add(hole, "plastic_black", uv="box", uv_scale=8.0)
    else:
        eye = K.blob("eye", 0.009, subdiv=1, center=(-0.33, -0.075, 0.175))
        ctx.add(eye, "lens_amber", uv="box", uv_scale=8.0, smooth=60)
    jaw = K.box("jaw", (0.07, 0.035, 0.012), center=(-0.385, -0.045, 0.15), bevel=0.004)
    ctx.add(jaw, "out_pike", uv="box", uv_scale=6.0, smooth=40)


# ============================================================================================
# Tamsin River Campground
# ============================================================================================

def _wheel(ctx, name, x, y, r_out, width, *, flat=0.0, burnt=False, dual=False, axle_z=None):
    """Tyre + steel rim on an axle along X (outer face at x)."""
    axle_z = r_out if axle_z is None else axle_z
    side = 1 if x > 0 else -1
    for k in range(2 if dual else 1):
        xc = x - side * (width / 2 + k * (width + 0.02))
        if not burnt:
            ty = P.tyre(f"{name}_tyre{k}", r_out, r_out * 0.62, width, segs=20, tread=True)
            K.place(ty, (xc, y, axle_z))
            if flat:
                P.flatten_tyre(ty, axle_z, r_out, amount=flat)
            ctx.add(ty, "tyre_rubber", uv="box", uv_scale=2.0, smooth=40, patches=0.6, low=0.6, low_h=0.3)
        rim = P.steel_rim(f"{name}_rim{k}", r_out * 0.6, width * 0.9)
        K.place(rim, (xc, y, axle_z - (r_out * 0.38 if burnt else 0.0)))
        ctx.add(rim, "car_burnt" if burnt else "paint_white", uv="box", uv_scale=3.0, smooth=40, patches=0.6, edge=1.0)


def out_rv(ctx: K.Ctx) -> None:
    """A 1980s cab-over motorhome (7.4 m, cab at -Y): fibreglass coach on a truck chassis, the
    cab-over bunk's rounded nose and its wrap-around window, brown and orange stripes, the entry door
    on the right (-X) with a step, an awning roll, roof air conditioner, vent, ladder and spare at the
    back, dual rear wheels. Worn: the awning torn and hanging, the door open, a flat, faded and
    streaked. Destroyed: burnt to the shell (no glass, no tyres)."""
    r = ctx.rnd("rv")
    burnt = ctx.destroyed
    shell_m = "car_burnt" if burnt else "out_rv_shell"
    hw = 1.2
    # Chassis and running gear.
    for x in (-0.45, 0.45):
        W.bar(ctx, f"frame{x}", (x, -3.5, 0.55), (x, 3.55, 0.55), 0.08, 0.18, "underbody", up=(0, 0, 1), bevel=0.005)
    fl = 0.3 if ctx.worn and not burnt else 0.0
    _wheel(ctx, "front_l", hw - 0.08, -2.35, 0.4, 0.22, flat=0.0, burnt=burnt)
    _wheel(ctx, "front_r", -hw + 0.08, -2.35, 0.4, 0.22, flat=fl, burnt=burnt)
    _wheel(ctx, "rear_l", hw - 0.02, 1.55, 0.4, 0.2, burnt=burnt, dual=True)
    _wheel(ctx, "rear_r", -hw + 0.02, 1.55, 0.4, 0.2, burnt=burnt, dual=True)
    for y in (-2.35, 1.55):
        W.rod(ctx, f"axle{y}", (-hw + 0.3, y, 0.4), (hw - 0.3, y, 0.4), 0.05, "underbody", segs=8)
    # Cab: hood, grille, windshield (cab at y -3.7 .. -2.1).
    cab = K.box("cab", (2.3, 1.6, 1.45), center=(0, -2.9, 1.28), bevel=0.08, bevel_segs=2, cuts=(2, 3, 2))

    def cab_shape(co):
        # Slope the windshield and the hood: the front-top edge pulled back.
        f = max(0.0, (co.z - 1.25) / 0.75)
        if co.y < -3.0:
            co.y += f * 0.55
        return co
    K.map_verts(cab, cab_shape)
    ctx.add(cab, shell_m, uv="box", uv_scale=1.0, smooth=30, patches=0.6, edge=0.8, low=0.5, low_h=0.8)
    hood = K.box("hood", (2.1, 0.7, 0.55), center=(0, -3.4, 0.98), bevel=0.06, bevel_segs=2, cuts=(1, 1, 0))
    ctx.add(hood, shell_m, uv="box", uv_scale=1.0, smooth=30, patches=0.6, edge=0.8)
    if not burnt:
        grille = K.box("grille", (1.2, 0.03, 0.32), center=(0, -3.76, 0.92), bevel=0.01)
        ctx.add(grille, "chrome_pitted", uv="box", uv_scale=3.0, patches=0.6, edge=1.0)
        for sx in (-1, 1):
            hl = K.cyl(f"headlight{sx}", 0.085, 0.03, segs=14, axis="Y", center=(sx * 0.82, -3.76, 0.95))
            ctx.add(hl, "lens_clear", uv="box", uv_scale=3.0, smooth=50)
        ws = K.box("windshield", (2.0, 0.02, 0.62), center=(0, -3.13, 1.68), cuts=(2, 0, 1))
        K.place(ws, (0, 0, 0), None)
        K.map_verts(ws, lambda co: Vector((co.x, co.y + (co.z - 1.68) * 0.65, co.z)))
        ctx.add(ws, "window_grime", uv="box", uv_scale=1.0, smooth=None, ao=False)
    bumper_f = K.box("bumper_f", (2.3, 0.14, 0.18), center=(0, -3.78, 0.62), bevel=0.03)
    ctx.add(bumper_f, "car_burnt" if burnt else "chrome_pitted", uv="box", uv_scale=2.0, patches=0.6, edge=1.0)
    # Coach body with the cab-over nose.
    coach = K.box("coach", (2.4, 6.2, 2.55), center=(0, 0.6, 1.95), bevel=0.1, bevel_segs=3, cuts=(3, 10, 4))
    ctx.add(coach, shell_m, uv="box", uv_scale=1.0, smooth=30, patches=0.6, edge=0.8, low=0.5, low_h=1.0)
    nose = K.box("nose", (2.36, 1.3, 1.05), center=(0, -2.75, 2.66), bevel=0.28, bevel_segs=4, cuts=(2, 2, 2))
    ctx.add(nose, shell_m, uv="box", uv_scale=1.0, smooth=35, patches=0.6, edge=0.8)
    if not burnt:
        nw = K.box("nose_window", (1.7, 0.04, 0.32), center=(0, -3.38, 2.72), bevel=0.06, bevel_segs=2)
        ctx.add(nw, "window_grime", uv="box", uv_scale=1.0, ao=False)
    # Stripes down both sides (and across the back).
    for k, (z, hgt, mat) in enumerate(((1.38, 0.12, "out_rv_stripe_a"), (1.55, 0.06, "out_rv_stripe_b"),
                                        (1.63, 0.03, "out_rv_stripe_a"))):
        if burnt:
            break
        for sx in (-1, 1):
            st = K.box(f"stripe{k}{sx}", (0.006, 6.0, hgt), center=(sx * (hw + 0.003), 0.55, z), cuts=(0, 6, 0))
            ctx.add(st, mat, uv="box", uv_scale=1.0, patches=0.7, wear=1.2)
        sb = K.box(f"stripe_back{k}", (2.2, 0.006, hgt), center=(0, 3.703, z))
        ctx.add(sb, mat, uv="box", uv_scale=1.0, patches=0.7)
    # Windows (dark glass, aluminium frames) and the door on the right (-X).
    wins = [(-1, -1.6, 0.9, 0.6), (-1, 2.6, 1.0, 0.6), (1, -1.3, 1.4, 0.6), (1, 1.0, 1.1, 0.6), (1, 2.9, 0.6, 0.45)]
    for k, (sx, y, w, h) in enumerate(wins):
        fr = K.box(f"winframe{k}", (0.03, w + 0.06, h + 0.06), center=(sx * (hw + 0.012), y, 2.2), bevel=0.012)
        ctx.add(fr, "car_burnt" if burnt else "road_alu", uv="box", uv_scale=2.0, patches=0.5)
        if not burnt:
            gl = K.box(f"glass{k}", (0.012, w, h), center=(sx * (hw + 0.027), y, 2.2))
            ctx.add(gl, "window_grime", uv="box", uv_scale=1.0, ao=False)
    door_y0, door_y1 = 0.25, 0.95
    dz0, dz1 = 0.7, 2.62
    dw = door_y1 - door_y0
    # The leaf is built hinged at its front edge (y = door_y0); worn, it hangs open 100 degrees.
    leaf = K.box("door", (0.035, dw, dz1 - dz0), center=(-hw - 0.02, door_y0 + dw / 2, (dz0 + dz1) / 2), bevel=0.02,
                 cuts=(0, 1, 2))
    dwin = K.box("door_window", (0.01, 0.36, 0.42), center=(-hw - 0.04, door_y0 + dw / 2, (dz0 + dz1) / 2 + 0.5))
    ctx.add(leaf, shell_m, uv="box", uv_scale=1.0, patches=0.6, edge=1.0)
    door_parts = [leaf]
    if not burnt:
        door_parts.append(ctx.add(dwin, "window_grime", uv="box", uv_scale=1.0, ao=False))
    else:
        K.remove(dwin)
    if ctx.worn:
        _swing(door_parts, (-hw - 0.02, door_y0, 0.0), 100)
    dark = K.box("doorway", (0.01, door_y1 - door_y0 - 0.04, dz1 - dz0 - 0.04), center=(-hw + 0.004, (door_y0 + door_y1) / 2,
                                                                                        (dz0 + dz1) / 2))
    ctx.add(dark, "plastic_black", uv="box", uv_scale=1.0, ao=False)
    step = K.box("step", (0.32, 0.6, 0.04), center=(-hw - 0.14, (door_y0 + door_y1) / 2, 0.45), bevel=0.005)
    ctx.add(step, "road_tread" if not burnt else "car_burnt", uv="box", uv_scale=4.0, patches=0.6, edge=1.0)
    # Awning: the roll along the right side (and in worn, its fabric hanging torn).
    if not burnt:
        roll = W.rod_obj("awning_roll", (-hw - 0.08, -1.9, 2.78), (-hw - 0.08, 2.9, 2.78), 0.06, segs=10)
        ctx.add(roll, "out_awning", uv="cyl", uv_axis=0, uv_scale=1.0, smooth=40, patches=0.6)
        for y in (-1.9, 2.9):
            arm = W.rod_obj(f"awning_arm{y}", (-hw - 0.02, y, 0.9), (-hw - 0.08, y, 2.72), 0.018, segs=6)
            ctx.add(arm, "road_alu", uv="cyl", uv_axis=0, smooth=40)
        if ctx.worn:
            sheet = K.quad_sheet("awning_rag", (-hw - 0.1, -0.8, 2.74), (-hw - 0.1, 1.4, 2.74), (-hw - 0.55, 1.2, 1.6),
                                 (-hw - 0.3, -0.6, 1.3), 6, 4)
            K.crumple(sheet, 0.03, scale=4.0, seed=ctx.seed)
            K.jagged_hole(sheet, (-hw - 0.35, 0.4, 2.0), 0.35, ctx.seed, axis=0, jag=0.6)
            K.solidify(sheet, 0.004, even=False)
            ctx.add(sheet, "out_awning", uv="box", uv_scale=1.0, smooth=40, patches=0.6)
    # Roof: air conditioner, vent, ladder, rear bumper and spare.
    ac = K.box("roof_ac", (0.75, 0.95, 0.3), center=(0, 0.2, 3.37), bevel=0.06, bevel_segs=2)
    ctx.add(ac, "car_burnt" if burnt else "plastic_white", uv="box", uv_scale=2.0, smooth=35, patches=0.6)
    vent = K.box("roof_vent", (0.4, 0.4, 0.1), center=(0, 2.4, 3.27), bevel=0.02)
    ctx.add(vent, "car_burnt" if burnt else "plastic_white", uv="box", uv_scale=2.0, patches=0.6)
    for x in (0.55, 0.85):
        W.rod(ctx, f"ladder_rail{x}", (x, 3.74, 0.9), (x, 3.74, 3.2), 0.014, "car_burnt" if burnt else "road_alu", segs=6)
    for k in range(7):
        W.rod(ctx, f"rung{k}", (0.55, 3.74, 1.1 + k * 0.32), (0.85, 3.74, 1.1 + k * 0.32), 0.011,
              "car_burnt" if burnt else "road_alu", segs=6)
    bumper_r = K.box("bumper_r", (2.4, 0.16, 0.16), center=(0, 3.76, 0.7), bevel=0.02)
    ctx.add(bumper_r, "car_burnt" if burnt else "paint_black", uv="box", uv_scale=2.0, patches=0.6)
    if not burnt:
        spare = P.tyre("spare", 0.38, 0.24, 0.2, segs=20, tread=True)
        K.place(spare, (0, 0, 0), (0, 0, 90))
        K.place(spare, (-0.45, 3.82, 1.25), (90, 0, 0))
        ctx.add(spare, "tyre_rubber", uv="box", uv_scale=2.0, smooth=40, patches=0.6)
        cover = K.cyl("spare_cover", 0.39, 0.2, segs=20, axis="Y", center=(-0.45, 3.84, 1.25))
        ctx.add(cover, "out_rv_stripe_a", uv="box", uv_scale=2.0, smooth=40, patches=0.6)
        for sx in (-1, 1):
            tl = K.box(f"taillight{sx}", (0.12, 0.03, 0.3), center=(sx * 1.05, 3.71, 1.0), bevel=0.01)
            ctx.add(tl, "lens_red", uv="box", uv_scale=3.0)
        for sx in (-1, 1):
            _face(ctx, f"badge{sx}", 1.1, 0.27, _rect("rv_badge"), (sx * (hw + 0.008), -0.6, 1.85), -90 * sx, wear=0.5)
        _face(ctx, "badge_back", 1.1, 0.27, _rect("rv_badge"), (0.25, 3.708, 2.6), 180, wear=0.5)
    else:
        for k in range(6):
            c = K.chunk(f"char{k}", r.uniform(0.1, 0.25), r, n=10, flat=0.5)
            K.place(c, (r.uniform(-1.6, 1.6), r.uniform(-3.5, 3.5), 0.04))
            ctx.add(c, "ash_burnt", uv="box", uv_scale=2.0, patches=0.3)
    ctx.col_box((-hw, -3.8, 0.0), (hw, 3.8, 3.3))


def _dome_sheet(name, w, d, h, nx, ny, *, sag=0.0, collapse=0.0, seed=0):
    """A dome tent's skin over a w x d floor: a raised cosine cap with sag between the poles."""
    o = K.grid(name, w, d, nx, ny)
    rr = random.Random(seed)

    def f(co):
        u, v = co.x / (w / 2), co.y / (d / 2)
        base = math.cos(u * math.pi / 2) * math.cos(v * math.pi / 2)
        z = h * max(0.0, base) ** 0.75
        # sag between the crossing poles (along the diagonals the poles hold the skin up)
        diag = min(abs(abs(u) - abs(v)), 1.0)
        z -= sag * diag * base
        if collapse:
            # A snapped pole: the east half of the dome caves in onto the floor.
            z *= max(0.12, 1.0 - collapse * K.smooth01(-0.45, 0.35, u))
            z += 0.03 * collapse * math.sin(co.y * 9.0 + u * 5.0) * K.smooth01(0.0, 0.5, u)
        return Vector((co.x * (1 + 0.04 * (1 - base)), co.y * (1 + 0.04 * (1 - base)), max(0.005, z)))
    K.map_verts(o, f)
    K.uv_sheet(o, scale=1.0)
    return o


def out_tent_dome(ctx: K.Ctx) -> None:
    """A two-person nylon dome: orange skin on two crossing shock-corded poles, a grey bathtub floor,
    the zipped door on the front (-Y), guy lines to pegs. Worn: a pole snapped, half the dome down,
    the fly gone. Destroyed: flattened and torn open, stuff spilling out."""
    r = ctx.rnd("dome")
    w = d = 2.0
    h = 1.15
    flat = ctx.destroyed
    collapse = 0.75 if ctx.worn and not flat else 0.0
    skin = _dome_sheet("skin", w, d, h if not flat else 0.14, 14, 14, sag=0.06, collapse=collapse, seed=ctx.seed)
    if flat:
        K.crumple(skin, 0.05, scale=3.0, seed=ctx.seed)
        K.jagged_hole(skin, (-0.3, -0.4, 0.1), 0.45, ctx.seed, axis=2, jag=0.6)
    K.solidify(skin, 0.004, even=False)
    ctx.add(skin, "out_tent_orange", uv=None, smooth=50, patches=0.7, low=0.6, low_h=0.3, moss=0.2 if ctx.worn else 0.0)
    tub = K.box("floor", (w, d, 0.1), center=(0, 0, 0.05), cuts=(4, 4, 0))
    K.delete_faces(tub, lambda p, n: n.z > 0.9)
    ctx.add(tub, "tarp_blue" if not flat else "out_tent_fly", uv="box", uv_scale=1.0, smooth=None, patches=0.6)
    if not flat:
        for k, (a, b) in enumerate((((-1, -1), (1, 1)), ((-1, 1), (1, -1)))):
            pts = []
            for i in range(13):
                t = i / 12
                x = (a[0] + (b[0] - a[0]) * t) * w / 2 * 1.02
                y = (a[1] + (b[1] - a[1]) * t) * d / 2 * 1.02
                z = h * math.sin(math.pi * t) * 1.02 + 0.01
                if collapse and x > -0.3:
                    z *= 1.0 - collapse * (x + 0.3) / 1.3
                pts.append(Vector((x, y, z)))
            if collapse and k == 0:
                pts = pts[:8]
            pole = K.tube(f"pole{k}", pts, 0.0065, segs=5)
            ctx.add(pole, "road_alu", uv="box", uv_scale=4.0, smooth=40)
        # The door panel follows the skin: for each (x, z) on it, the y where the dome passes.
        door = K.quad_sheet("door", (-0.42, 0.0, 0.06), (0.42, 0.0, 0.06), (0.22, 0.0, 0.88), (-0.22, 0.0, 0.88), 4, 6)

        def on_skin(co):
            u = co.x / (w / 2)
            cu = max(0.05, math.cos(u * math.pi / 2))
            k = min(1.0, (co.z / h) ** (1 / 0.75) / cu)
            v = (2 / math.pi) * math.acos(k)
            return Vector((co.x * (1 + 0.04 * (1 - k * cu)), -(d / 2) * v * (1 + 0.04 * (1 - k * cu)) - 0.012, co.z))
        K.map_verts(door, on_skin)
        if collapse:
            K.map_verts(door, lambda co: Vector((co.x, co.y, co.z * max(0.12, 1.0 - collapse * K.smooth01(-0.45, 0.35, co.x / (w / 2))))))
        ctx.add(door, "out_tent_fly", uv="box", uv_scale=2.0, smooth=40, patches=0.6)
    for k, (x, y) in enumerate(((-1.35, -1.35), (1.35, -1.35), (1.35, 1.35), (-1.35, 1.35))):
        peg = K.cyl(f"peg{k}", 0.006, 0.12, segs=5, center=(x, y, 0.04))
        ctx.add(peg, "road_alu", uv="box", uv_scale=6.0)
        if not flat and not (collapse and x > 0):
            gl = K.tube(f"guy{k}", [(x, y, 0.06), (x * 0.62, y * 0.62, h * 0.55)], 0.002, segs=3)
            ctx.add(gl, "road_rope", uv="box", uv_scale=8.0)
    if flat:
        bag = K.blob("sleeping_bag", 0.25, subdiv=2, scale=(2.6, 1.0, 0.35), center=(0.4, -1.2, 0.06), rough=0.2, seed=3)
        ctx.add(bag, "nylon_navy", uv="box", uv_scale=2.0, smooth=50, patches=0.6)


def out_tent_cabin(ctx: K.Ctx) -> None:
    """A canvas family cabin tent (2.8 x 2.4 m, walls 1.6 m, ridge 2.05 m) on a steel frame, with a
    front awning on two poles, mesh windows and a zipped door. Worn: the west side down, the canvas
    sagging off a bent leg. Destroyed: collapsed over its frame."""
    r = ctx.rnd("cabin")
    W2, D2, wall, ridge = 1.4, 1.2, 1.6, 2.05
    down = ctx.worn and not ctx.destroyed
    flat = ctx.destroyed

    def zf(x, z):
        if flat:
            return 0.12 + 0.05 * math.sin(x * 3.1) + 0.03 * z
        if down and x < -0.1:
            # The west legs buckled: that side of the tent slumps to the ground.
            return z * max(0.1, 1.0 - 0.85 * min(1.0, (-0.1 - x) / 1.0))
        return z

    def roof_z(x):
        return wall + (ridge - wall) * (1 - abs(x) / W2) if True else wall
    # Canvas: four walls and the two roof planes as sheets.
    sheets = []
    for k, (p0, p1) in enumerate((((-W2, -D2), (W2, -D2)), ((W2, -D2), (W2, D2)), ((W2, D2), (-W2, D2)), ((-W2, D2), (-W2, -D2)))):
        s = K.quad_sheet(f"wall{k}", (p0[0], p0[1], 0.0), (p1[0], p1[1], 0.0), (p1[0], p1[1], wall), (p0[0], p0[1], wall), 8, 5)
        sheets.append(s)
    for sx in (-1, 1):
        s = K.quad_sheet(f"roof{sx}", (sx * W2, -D2, wall), (0, -D2, ridge), (0, D2, ridge), (sx * W2, D2, wall), 6, 8)
        sheets.append(s)
    for sy in (-1, 1):
        g = K.prism(f"gable{sy}", [(-W2, wall), (W2, wall), (0.0, ridge)], 0.004, plane="XZ", offset=sy * D2)
        sheets.append(g)
    canvas = K.merge_parts(sheets, "canvas")
    K.subdivide(canvas, 1)
    K.map_verts(canvas, lambda co: Vector((co.x, co.y, zf(co.x, co.z))))
    K.crumple(canvas, 0.02 if not flat else 0.05, scale=3.0, seed=ctx.seed)
    if flat:
        K.jagged_hole(canvas, (0.4, -0.3, 0.2), 0.4, ctx.seed, axis=2, jag=0.5)
    K.solidify(canvas, 0.005, even=False)
    ctx.add(canvas, "out_tent_canvas", uv="box", uv_scale=1.0, smooth=45, patches=0.7, low=0.7, low_h=0.5,
            moss=0.3 if ctx.worn else 0.1)
    if not flat:
        # Frame legs at the corners and the ridge pole; mesh windows; the door.
        for k, (x, y) in enumerate(((-W2, -D2), (W2, -D2), (W2, D2), (-W2, D2))):
            top = Vector((x, y, zf(x, wall)))
            if down and x < 0:
                top = Vector((x + 0.25, y, zf(x, wall)))
            W.rod(ctx, f"leg{k}", (x, y, 0.0), top, 0.012, "road_steel", segs=6)
        W.rod(ctx, "ridge", (0, -D2, zf(0, ridge)), (0, D2, zf(0, ridge)), 0.014, "road_steel", segs=6)
        for k, (x, y, rot) in enumerate(((0.75, -D2 - 0.008, 0), (W2 + 0.008, 0.2, 90), (0.3, D2 + 0.008, 180))):
            win = K.quad_sheet(f"window{k}", (-0.35, 0, 0.8), (0.35, 0, 0.8), (0.35, 0, 1.3), (-0.35, 0, 1.3), 1, 1)
            K.place(win, (0, 0, 0), (0, 0, rot))
            K.place(win, (x, y, 0))
            ctx.add(win, "chainlink", uv="box", uv_scale=4.0, ao=False)
        door = K.quad_sheet("door", (-0.95, 0, 0.02), (-0.25, 0, 0.02), (-0.25, 0, 1.75), (-0.95, 0, 1.75), 1, 3)
        K.place(door, (0, -D2 - 0.01, 0))
        ctx.add(door, "out_tent_fly", uv="box", uv_scale=2.0, patches=0.6)
        # The front awning on two poles with guy lines.
        aw = K.quad_sheet("awning", (-W2, -D2, wall - 0.05), (W2, -D2, wall - 0.05), (W2, -D2 - 1.4, 1.75), (-W2, -D2 - 1.4, 1.75),
                          6, 3)
        K.map_verts(aw, lambda co: Vector((co.x, co.y, co.z - 0.08 * math.sin((co.x / W2 + 1) * math.pi / 2) * (1 if not down else 3.0)
                                           * max(0.0, -(co.y + D2)) / 1.4)))
        K.solidify(aw, 0.004, even=False)
        ctx.add(aw, "out_tent_canvas", uv="box", uv_scale=1.0, smooth=45, patches=0.7)
        for x in (-W2, W2):
            if down and x < 0:
                W.rod(ctx, "awning_pole_fallen", (x + 0.2, -D2 - 1.3, 0.02), (x + 1.0, -D2 - 0.4, 0.02), 0.012, "road_steel")
                continue
            W.rod(ctx, f"awning_pole{x}", (x, -D2 - 1.4, 0.0), (x, -D2 - 1.4, 1.76), 0.012, "road_steel", segs=6)
            gl = K.tube(f"guy{x}", [(x, -D2 - 1.4, 1.74), (x * 1.25, -D2 - 2.1, 0.02)], 0.002, segs=3)
            ctx.add(gl, "road_rope", uv="box", uv_scale=8.0)
    else:
        for k in range(4):
            a = W.rod_obj(f"frame{k}", (r.uniform(-1.2, 1.2), r.uniform(-1.0, 1.0), 0.03),
                          (r.uniform(-1.2, 1.2), r.uniform(-1.0, 1.0), 0.05), 0.012, segs=6)
            ctx.add(a, "road_steel", uv="cyl", uv_axis=0, smooth=40)


def out_fire_ring(ctx: K.Ctx) -> None:
    """A park fire ring: a rolled-steel ring with a flared lip, a swing-over cooking grate on a
    pivot post, ash and half-burnt wood inside. Worn: rusted through in places, the grate off."""
    r = ctx.rnd("ring")
    ring = K.lathe("ring", [(0.47, 0.0), (0.47, 0.26), (0.5, 0.3), (0.53, 0.3), (0.5, 0.27), (0.5, 0.0)], segs=28,
                   cap_bottom=False, cap_top=False)
    if ctx.worn:
        K.dent(ring, (0.5, 0.0, 0.2), 0.12, 0.03)
    ctx.add(ring, "wild_cast_iron_rust", uv="cyl", uv_scale=2.0, smooth=40, patches=0.7, edge=1.0, low=0.6, low_h=0.2)
    ash = K.blob("ash", 0.45, subdiv=3, scale=(1.0, 1.0, 0.12), center=(0, 0, 0.0), rough=0.3, seed=ctx.seed)
    ctx.add(ash, "ash_burnt", uv="box", uv_scale=1.5, smooth=60)
    for k in range(4):
        lg = W.log_obj(f"brand{k}", r.uniform(0.35, 0.6), r.uniform(0.04, 0.06), ctx.seed + k, sides=7, rings=3,
                       bark="wood_charred", end="wood_charred")
        a = r.uniform(0, math.tau)
        K.place(lg, (math.cos(a) * 0.12, math.sin(a) * 0.12, 0.08), (0, r.uniform(-12, 12), math.degrees(a) + r.uniform(-30, 30)))
        ctx.add(lg, None, uv=None, smooth=45, patches=0.5)
    post = K.cyl("pivot", 0.025, 0.42, segs=8, center=(0.52, 0.0, 0.21))
    ctx.add(post, "wild_cast_iron_rust", uv="cyl", uv_scale=3.0, smooth=40)
    gr = []
    rot = 0 if ctx.clean else 70
    frame = K.tube("grate_frame", [(0.52, 0.0, 0.36), (0.3, -0.25, 0.36), (-0.25, -0.25, 0.36), (-0.25, 0.25, 0.36),
                                   (0.3, 0.25, 0.36), (0.52, 0.0, 0.36)], 0.009, segs=5)
    gr.append(frame)
    for k in range(10):
        x = -0.22 + k * 0.055
        gr.append(K.cyl(f"bar{k}", 0.005, 0.5, segs=4, axis="Y", center=(x, 0.0, 0.36)))
    g = K.merge_parts(gr, "grate")
    K.place(g, (-0.52, 0, 0))
    K.place(g, (0, 0, 0), (0, 0, rot))
    K.place(g, (0.52, 0, 0))
    ctx.add(g, "wild_cast_iron", uv="box", uv_scale=4.0, smooth=40, patches=0.6)
    ctx.col_box((-0.53, -0.53, 0), (0.53, 0.53, 0.3))


def out_tent_pad(ctx: K.Ctx) -> None:
    """A gravel tent pad (3.4 m square) edged with treated timbers spiked at the corners."""
    r = ctx.rnd("pad")
    s = 1.7
    for k, (a, b) in enumerate((((-s, -s), (s, -s)), ((s, -s), (s, s)), ((s, s), (-s, s)), ((-s, s), (-s, -s)))):
        W.bar(ctx, f"timber{k}", (a[0], a[1], 0.07), (b[0], b[1], 0.07), 0.14, 0.14, "wood_stained", up=(0, 0, 1), bevel=0.01,
              ext=0.07, patches=0.6, moss=0.4 if ctx.worn else 0.2)
    gravel = K.grid("gravel", 2 * s - 0.12, 2 * s - 0.12, 12, 12, center=(0, 0, 0.1))
    K.noise_disp(gravel, 0.02, scale=3.0, seed=ctx.seed, along_normal=False)
    ctx.add(gravel, "out_gravel", uv="planar", uv_axis=2, uv_scale=1.0, smooth=60, patches=0.5, moss=0.3 if ctx.worn else 0.0)
    for k in range(10):
        c = O.stone_obj(f"stone{k}", r.uniform(0.04, 0.08), ctx.seed + k)
        K.place(c, (r.uniform(-s + 0.2, s - 0.2), r.uniform(-s + 0.2, s - 0.2), 0.1))
        ctx.add(c, "stone_river", uv="box", uv_scale=3.0, patches=0.4)


def out_bear_box(ctx: K.Ctx) -> None:
    """A galvanized food locker: a ribbed steel box on skids, a sloped lid with the bear-proof latch
    in its recess and a FOOD STORAGE label. Worn: dented, scratched. Destroyed: the lid wrenched up
    and buckled, claw scores down the front."""
    r = ctx.rnd("bearbox")
    w, d, h = 1.2, 0.66, 0.82
    for x in (-0.5, 0.5):
        W.bar(ctx, f"skid{x}", (x, -d / 2, 0.04), (x, d / 2, 0.04), 0.08, 0.08, "wood_creosote", up=(0, 0, 1), bevel=0.006)
    body = K.box("body", (w, d, h - 0.08), center=(0, 0, 0.08 + (h - 0.08) / 2), bevel=0.012, cuts=(6, 2, 3))
    if ctx.worn:
        for k in range(3):
            K.dent(body, (r.uniform(-0.5, 0.5), -d / 2, r.uniform(0.3, 0.8)), r.uniform(0.08, 0.15), r.uniform(0.01, 0.025))
    ctx.add(body, "metal_galvanized", uv="box", uv_scale=1.0, patches=0.6, edge=1.0, low=0.5, low_h=0.3)
    for k in range(5):
        rib = K.box(f"rib{k}", (0.03, 0.012, h - 0.2), center=(-0.48 + k * 0.24, -d / 2 - 0.006, 0.46), bevel=0.004)
        ctx.add(rib, "metal_galvanized", uv="box", uv_scale=2.0, patches=0.6, edge=1.2)
    lid = K.box("lid", (w + 0.04, d + 0.06, 0.06), center=(0, 0, 0), bevel=0.01, cuts=(4, 2, 0))
    K.map_verts(lid, lambda co: Vector((co.x, co.y, co.z + 0.06 * (co.y / (d / 2)))))
    if ctx.destroyed:
        K.place(lid, (0, 0, 0), (-65, 0, 6))
        K.place(lid, (0, d / 2 + 0.05 - (d / 2) * math.cos(math.radians(65)), h + (d / 2) * math.sin(math.radians(65))))
        K.dent(lid, (0.2, 0.0, h + 0.3), 0.2, 0.05)
    else:
        K.place(lid, (0, 0, h + 0.03))
    ctx.add(lid, "metal_galvanized", uv="box", uv_scale=1.0, patches=0.6, edge=1.0)
    recess = K.box("latch_recess", (0.22, 0.02, 0.1), center=(0, -d / 2 - 0.011, h - 0.12), bevel=0.006)
    ctx.add(recess, "paint_black", uv="box", uv_scale=4.0, patches=0.5)
    latch = K.tube("latch", [(-0.06, -d / 2 - 0.022, h - 0.15), (-0.06, -d / 2 - 0.04, h - 0.1), (0.06, -d / 2 - 0.04, h - 0.1),
                             (0.06, -d / 2 - 0.022, h - 0.15)], 0.008, segs=6)
    ctx.add(latch, "road_steel", uv="box", uv_scale=6.0, smooth=40, patches=0.6)
    _face(ctx, "label", 0.5, 0.25, _rect("bear_label"), (0.3, -d / 2 - 0.013, 0.5), wear=0.6)
    if ctx.destroyed:
        for k in range(4):
            sc = K.box(f"claw{k}", (0.012, 0.004, 0.32), center=(-0.35 + k * 0.05, -d / 2 - 0.013, 0.55), bevel=0.001)
            K.place(sc, (0, 0, 0), None)
            ctx.add(sc, "road_steel", uv="box", uv_scale=4.0, ao=False)
    ctx.col_box((-w / 2, -d / 2, 0), (w / 2, d / 2, h + 0.06))


def out_host_trailer_shell(ctx: K.Ctx) -> None:
    """The camp host's park-model trailer over its two kit rooms (plan cols 6..14, rows 36..38: a
    9 x 3 m room pair, floor 0.35): ribbed aluminium siding 0.11 m outside the kit walls cut round
    the plan's doors and windows, white trim, vinyl skirting, a low gabled metal roof on the kit
    ceiling, little awnings over the windows, a canopy over the door, wooden steps, the hitch and
    two propane bottles at the west end, a CAMP HOST sign. Worn: dented, a skirting panel gone,
    the canopy sagging."""
    r = ctx.rnd("trailer")
    room = O.Room(9, 3, 0.35)
    ops = [("N", 2, "door"), ("N", 4, "window2"), ("N", 7, "window"), ("S", 1, "window"), ("S", 4, "window"),
           ("S", 7, "window"), ("W", 1, "window"), ("E", 1, "door")]
    top = 3.35
    for side in ("N", "S", "E", "W"):
        _siding(ctx, room, side, ops, off=0.11, z0=0.4, z1=top + 0.06, mat="out_alu_siding", ext=0.14, seed=r.randint(0, 999),
                dents=3 if ctx.worn else 0, trim_mat="paint_white", wear=0.8)
        # Vinyl skirting from the ground to the siding, minus a panel (worn).
        start, along, out = room.side_line(side, 0.13)
        L = room.length(side)
        n = max(1, int(L / 1.2))
        for k in range(n):
            if ctx.worn and side == "S" and k == 2:
                continue
            a, b = -0.14 + (L + 0.28) * k / n, -0.14 + (L + 0.28) * (k + 1) / n
            c = start + along * ((a + b) / 2) + Vector((0, 0, 0.21))
            sk = K.box(f"skirt{side}{k}", (abs(along.x) * (b - a - 0.01) + abs(out.x) * 0.012,
                                           abs(along.y) * (b - a - 0.01) + abs(out.y) * 0.012, 0.42), center=c, cuts=(2, 2, 0))
            ctx.add(sk, "plastic_white", uv="box", uv_scale=1.0, patches=0.6, low=1.0, low_h=0.4, moss=0.3)
    # Corner trim.
    for sx in (-1, 1):
        for sy in (-1, 1):
            c = Vector((sx * (4.5 + 0.14), sy * (1.5 + 0.14), 0))
            W.bar(ctx, f"corner{sx}{sy}", (c.x, c.y, 0.42), (c.x, c.y, top + 0.06), 0.05, 0.05, "paint_white", up=(1, 0, 0),
                  bevel=0.004)
    # Roof: a low gable along X with a rolled edge, on the kit ceiling.
    hw, hd = 4.5 + 0.3, 1.5 + 0.3
    rise = 0.32
    for sy in (-1, 1):
        sh = K.quad_sheet(f"roof{sy}", (-hw, sy * hd, top + 0.08), (hw, sy * hd, top + 0.08), (hw, 0, top + 0.08 + rise),
                          (-hw, 0, top + 0.08 + rise), 10, 3, thickness=0.03)
        ctx.add(sh, "roof_metal", uv="box", uv_scale=1.0, patches=0.6, moss=0.2)
        edge = W.rod_obj(f"roof_edge{sy}", (-hw, sy * hd, top + 0.07), (hw, sy * hd, top + 0.07), 0.025, segs=8)
        ctx.add(edge, "paint_white", uv="cyl", uv_axis=0, smooth=40, patches=0.5)
    for sx in (-1, 1):
        g = K.prism(f"gable{sx}", [(-hd, 0.0), (hd, 0.0), (0.0, rise)], 0.03, plane="YZ", offset=sx * (4.5 + 0.13))
        K.place(g, (0, 0, top + 0.06))
        ctx.add(g, "out_alu_siding", uv="box", uv_scale=1.0, patches=0.5)
    fascia = K.box("fascia_infill", (9.25, 3.25, 0.1), center=(0, 0, top + 0.06))
    ctx.add(fascia, "out_alu_siding", uv="box", uv_scale=1.0, patches=0.5)
    # Window awnings (aluminium, striped) over the windows, and the door canopy with posts.
    for (side, idx, kind) in ops:
        if kind == "door":
            continue
        start, along, out = room.side_line(side, 0.16)
        span = 2.0 if kind == "window2" else 1.0
        c = start + along * (idx + span / 2)
        w = O.OPENING[kind][0] + 0.3
        aw = K.quad_sheet(f"winawn{side}{idx}", c - along * (w / 2) + Vector((0, 0, 2.62)), c + along * (w / 2) + Vector((0, 0, 2.62)),
                          c + along * (w / 2) + out * 0.42 + Vector((0, 0, 2.38)), c - along * (w / 2) + out * 0.42 + Vector((0, 0, 2.38)),
                          3, 1, thickness=0.012)
        ctx.add(aw, "out_awning", uv="box", uv_scale=1.0, patches=0.6)
    start, along, out = room.side_line("N", 0.14)
    door_c = start + along * 2.5
    canopy = K.quad_sheet("canopy", door_c - along * 1.6 + Vector((0, 0, 2.9)), door_c + along * 1.6 + Vector((0, 0, 2.9)),
                          door_c + along * 1.6 + out * 2.0 + Vector((0, 0, 2.62 if not ctx.worn else 2.3)),
                          door_c - along * 1.6 + out * 2.0 + Vector((0, 0, 2.62)), 6, 4, thickness=0.02)
    if ctx.worn:
        K.crumple(canopy, 0.02, scale=3.0, seed=ctx.seed)
    ctx.add(canopy, "out_awning", uv="box", uv_scale=1.0, patches=0.6)
    for s in (-1.5, 1.5):
        p = door_c + along * s + out * 1.95
        W.rod(ctx, f"canopy_post{s}", (p.x, p.y, 0.0), (p.x, p.y, 2.6 if not (ctx.worn and s > 0) else 2.3), 0.025, "road_alu",
              segs=8)
    for k, (dz, dy) in enumerate(((0.12, 0.62), (0.24, 0.36))):
        st = K.box(f"step{k}", (1.0, 0.28, 0.04), center=door_c + out * (dy - 0.05) + Vector((0, 0, dz)), bevel=0.004)
        ctx.add(st, "wood_weathered", uv="box", uv_scale=1.0, patches=0.6)
    for sx in (-0.45, 0.45):
        p = door_c + along * sx + out * 0.42
        W.bar(ctx, f"stringer{sx}", (p.x, p.y + 0.3, 0.0), (p.x, p.y - 0.25, 0.3), 0.04, 0.12, "wood_weathered", up=(1, 0, 0))
    # East door: a single step (the bolted back door, the shortcut out).
    start, along, out = room.side_line("E", 0.14)
    bc = start + along * 1.5
    st = K.box("back_step", (0.3, 0.9, 0.2), center=bc + out * 0.14 + Vector((0, 0, 0.1)), bevel=0.01)
    ctx.add(st, "concrete_barrier", uv="box", uv_scale=1.0, patches=0.6)
    # Hitch and propane bottles at the west end.
    for sy in (-0.45, 0.45):
        W.bar(ctx, f"tongue{sy}", (-4.62, sy, 0.3), (-5.6, 0.0, 0.3), 0.08, 0.1, "paint_black", up=(0, 0, 1), bevel=0.006)
    jack = K.cyl("jack", 0.035, 0.32, segs=8, center=(-5.5, 0.0, 0.16))
    ctx.add(jack, "road_steel", uv="cyl", uv_scale=3.0, smooth=40)
    for k, y in enumerate((-0.2, 0.2)):
        bt = K.lathe(f"propane{k}", [(0.0, 0.0), (0.15, 0.02), (0.155, 0.08), (0.155, 0.5), (0.13, 0.58), (0.06, 0.62),
                                     (0.04, 0.68), (0.0, 0.68)], segs=16)
        K.place(bt, (-5.0, y, 0.36))
        ctx.add(bt, "paint_white", uv="cyl", uv_scale=2.0, smooth=40, patches=0.7)
    _face(ctx, "host_sign", 0.6, 0.3, _rect("camp_host"), door_c + along * 1.0 + out * 0.03 + Vector((0, 0, 1.75)), 180, wear=0.5)


def out_block_roof(ctx: K.Ctx) -> None:
    """The comfort station's roof over its 8 x 5 m block (origin on the kit ceiling, z = 0 at the
    wall tops): a low gable of corrugated metal on rafter tails, painted fascia, two vent stacks and
    a fibreglass skylight; birds' nests under the eaves."""
    r = ctx.rnd("blockroof")
    hw, hd = 4.0 + 0.3, 2.5 + 0.3
    rise = 0.75
    for sy in (-1, 1):
        sh = K.quad_sheet(f"roof{sy}", (-hw, sy * hd, 0.1), (hw, sy * hd, 0.1), (hw, 0, 0.1 + rise), (-hw, 0, 0.1 + rise), 12, 4,
                          thickness=0.03)
        ctx.add(sh, "roof_metal", uv="box", uv_scale=1.0, patches=0.6, moss=0.35)
        fa = W.bar_obj(f"fascia{sy}", (-hw, sy * hd, 0.06), (hw, sy * hd, 0.06), 0.03, 0.18, up=(0, 0, 1))
        ctx.add(fa, "wood_stained", uv="box", uv_scale=1.0, patches=0.6)
        for k in range(15):
            x = -hw + 0.15 + k * (2 * hw - 0.3) / 14
            W.bar(ctx, f"rafter{sy}{k}", (x, sy * (2.4), 0.04), (x, sy * hd, 0.09), 0.05, 0.12, "wood_stained", up=(0, 0, 1))
    for sx in (-1, 1):
        g = K.prism(f"gable{sx}", [(-hd + 0.3, 0.0), (hd - 0.3, 0.0), (0.0, rise - 0.02)], 0.18, plane="YZ", offset=sx * 3.98)
        K.place(g, (0, 0, 0.06))
        ctx.add(g, "wood_stained", uv="box", uv_scale=1.0, patches=0.6)
        vent = K.box(f"gable_vent{sx}", (0.02, 0.5, 0.3), center=(sx * 4.08, 0, 0.35), bevel=0.004)
        ctx.add(vent, "metal_galvanized", uv="box", uv_scale=2.0, patches=0.6)
    for k, x in enumerate((-2.2, 1.8)):
        st = K.cyl(f"stack{k}", 0.05, 0.6, segs=10, center=(x, 0.9, 0.1 + rise * (1 - 0.9 / hd) + 0.2))
        cap = K.cyl(f"stackcap{k}", 0.09, 0.05, segs=10, center=(x, 0.9, 0.1 + rise * (1 - 0.9 / hd) + 0.52), r_top=0.03)
        ctx.add(K.merge_parts([st, cap], f"vent_stack{k}"), "metal_galvanized", uv="cyl", uv_scale=3.0, smooth=40, patches=0.6)
    sky = K.box("skylight", (1.0, 0.8, 0.08), center=(0.3, -1.1, 0.1 + rise * (1 - 1.1 / hd) + 0.06), bevel=0.02)
    K.place(sky, (0, 0, 0), None)
    K.map_verts(sky, lambda co: Vector((co.x, co.y, co.z + (co.y + 1.1) * rise / hd)))
    ctx.add(sky, "road_lens_frost", uv="box", uv_scale=1.0, patches=0.5)
    for k in range(2):
        nest = K.blob(f"nest{k}", 0.1, subdiv=2, scale=(1.2, 1.0, 0.6), center=(-3.2 + k * 5.9, -2.45, -0.02), rough=0.4, seed=k)
        ctx.add(nest, "farm_hay_old", uv="box", uv_scale=4.0, smooth=50)


def out_kiosk_shell(ctx: K.Ctx) -> None:
    """The fee station over its 3 x 2 m kit room (plan cols 27..29, rows 37..38, floor 0.35): cedar
    board-and-batten 0.11 m outside the kit walls, cut round the pay window (W), the north window
    and the door (E), a hip roof of brown shingles, the FEE STATION board on the road side (S),
    the rules board by the door, a drop slot and a pay-envelope box. Worn: battens missing, moss."""
    r = ctx.rnd("kiosk")
    room = O.Room(3, 2, 0.35)
    ops = [("W", 0, "window"), ("N", 1, "window"), ("E", 1, "door")]
    top = 3.35
    for side in ("N", "S", "E", "W"):
        _siding(ctx, room, side, ops, off=0.11, z0=0.0, z1=top, mat="farm_wood_cedar", ext=0.14, seed=r.randint(0, 999),
                trim_mat="wood_stained", moss=0.3 if ctx.worn else 0.1, wear=0.8)
        start, along, out = room.side_line(side, 0.14 + 0.012)
        L = room.length(side)
        holes = O.holes_on(side, ops, floor=room.floor)
        n = int((L + 0.28) / 0.3)
        for k in range(n + 1):
            t = -0.14 + (L + 0.28) * k / n
            if ctx.worn and ctx.drnd(f"b{side}{k}").random() < 0.15:
                continue
            for z0, z1 in O.clip_vertical(0.02, top, t, 0.03, holes):
                p = start + along * t
                W.bar(ctx, f"batten{side}{k}_{z0:.1f}", (p.x, p.y, z0), (p.x, p.y, z1), 0.05, 0.02, "farm_wood_cedar",
                      up=tuple(out), bevel=0.003, patches=0.6, moss=0.4 if ctx.worn else 0.15)
    # Hip roof.
    hw, hd = 1.5 + 0.4, 1.0 + 0.4
    apex_a, apex_b = Vector((-0.5, 0, top + 0.1 + 0.85)), Vector((0.5, 0, top + 0.1 + 0.85))
    c = [Vector((-hw, -hd, top + 0.1)), Vector((hw, -hd, top + 0.1)), Vector((hw, hd, top + 0.1)), Vector((-hw, hd, top + 0.1))]
    planes = [(c[0], c[1], apex_b, apex_a), (c[2], c[3], apex_a, apex_b), (c[1], c[2], apex_b, apex_b),
              (c[3], c[0], apex_a, apex_a)]
    for k, (p0, p1, p2, p3) in enumerate(planes):
        if p2 == p3:
            sh = _tri(f"hip{k}", p0, p1, p2, thickness=0.04)
        else:
            sh = K.quad_sheet(f"hip{k}", p0, p1, p2, p3, 4, 2, thickness=0.04)
        ctx.add(sh, "roof_shingle_brown", uv="box", uv_scale=1.0, patches=0.6, moss=0.5 if ctx.worn else 0.25)
    soffit = K.box("soffit", (2 * hw - 0.05, 2 * hd - 0.05, 0.08), center=(0, 0, top + 0.06))
    ctx.add(soffit, "wood_stained", uv="box", uv_scale=1.0, patches=0.5)
    # Boards: FEE STATION on the road side (S), the rules by the door (E), the envelope box.
    start, along, out = room.side_line("S", 0.16)
    _face(ctx, "fee_sign", 1.2, 1.2, _rect("fee_station"), start + along * 1.5 + out * 0.012 + Vector((0, 0, 1.9)), 0, wear=0.7)
    start, along, out = room.side_line("E", 0.16)
    _face(ctx, "rules", 0.55, 0.55, _rect("kiosk_rules"), start + along * 0.5 + out * 0.012 + Vector((0, 0, 1.55)), 90, wear=0.7)
    start, along, out = room.side_line("S", 0.16)
    ib = K.box("iron_ranger", (0.22, 0.16, 0.32), center=start + along * 0.55 + out * 0.08 + Vector((0, 0, 1.1)), bevel=0.01)
    ctx.add(ib, "wild_cast_iron_rust", uv="box", uv_scale=3.0, patches=0.6, edge=1.0)
    slot = K.box("slot", (0.1, 0.01, 0.012), center=start + along * 0.55 + out * 0.165 + Vector((0, 0, 1.2)))
    ctx.add(slot, "plastic_black", uv="box", uv_scale=4.0, ao=False)


def out_camp_sign(ctx: K.Ctx) -> None:
    """TAMSIN RIVER CAMPGROUND, COUNTY PARK: a routed cedar board between two log posts under a little
    shingled cap, river stones round the post feet. Worn: faded, a corner split off, moss."""
    r = ctx.rnd("campsign")
    for x in (-1.45, 1.45):
        lg = W.log_obj(f"post{x}", 2.35, 0.12, ctx.seed + int(x * 10), sides=10, rings=4, taper=0.04, bark="wild_log_bark",
                       end="wood_log_end")
        K.orient(lg, Vector((0, 0, 1)), Vector((0, -1, 0)), (x, 0.0, 1.175))
        ctx.add(lg, None, uv=None, smooth=50, patches=0.5, moss=0.4 if ctx.worn else 0.2)
        for k in range(6):
            a = math.tau * k / 6 + r.uniform(-0.3, 0.3)
            O.add_stone(ctx, f"stone{x}{k}", (x + math.cos(a) * 0.22, math.sin(a) * 0.22, 0.04), r.uniform(0.12, 0.2),
                        ctx.seed + k, flat=0.5)
    board = K.box("board", (2.8, 0.07, 0.9), center=(0, 0.0, 1.55), bevel=0.012, cuts=(4, 0, 2))
    if ctx.worn:
        K.cut_plane(board, (1.25, 0, 1.98), Vector((0.6, 0, 1.0)).normalized(), keep="below")
    ctx.add(board, "farm_wood_cedar", uv="box", uv_scale=1.0, patches=0.6, edge=1.0, moss=0.3 if ctx.worn else 0.1)
    _face(ctx, "face", 2.7, 0.82, _rect("camp_sign"), (0, -0.037, 1.55), wear=0.8)
    _face(ctx, "back", 2.7, 0.82, _rect("camp_sign"), (0, 0.037, 1.55), 180, wear=0.8)
    for sy in (-1, 1):
        cap = K.quad_sheet(f"cap{sy}", (-1.62, sy * 0.24, 2.12), (1.62, sy * 0.24, 2.12), (1.62, 0, 2.3), (-1.62, 0, 2.3), 4, 1,
                           thickness=0.03)
        ctx.add(cap, "roof_shingle_brown", uv="box", uv_scale=1.0, patches=0.6, moss=0.6 if ctx.worn else 0.3)
    ctx.col_box((-1.6, -0.15, 0), (1.6, 0.15, 2.3))


def out_gate_arm(ctx: K.Ctx) -> None:
    """The entrance gate: a striped steel arm (4 m) pivoting on a post with a counterweight box,
    resting in a forked post, a CAMPGROUND CLOSED notice wired to it. Worn: snapped at the rest
    post side and hanging to the ground, the rest post knocked crooked."""
    r = ctx.rnd("gatearm")
    W.bar(ctx, "post", (-1.95, 0.0, 0.0), (-1.95, 0.0, 1.05), 0.12, 0.12, "paint_grey", up=(1, 0, 0), bevel=0.008)
    hinge = K.box("hinge", (0.16, 0.16, 0.1), center=(-1.95, 0.0, 1.06), bevel=0.01)
    ctx.add(hinge, "paint_grey", uv="box", uv_scale=3.0, patches=0.6)
    cw = K.box("counterweight", (0.28, 0.14, 0.2), center=(-2.18, 0.0, 1.0), bevel=0.01)
    ctx.add(cw, "paint_grey", uv="box", uv_scale=3.0, patches=0.6, edge=1.0)
    rest_tilt = 12 if ctx.worn else 0
    rp = W.bar_obj("rest_post", (1.95, 0.0, 0.0), (1.95 + math.sin(math.radians(rest_tilt)) * 0.9, 0.0, 0.9), 0.08, 0.08, up=(1, 0, 0))
    ctx.add(rp, "paint_grey", uv="box", uv_scale=2.0, patches=0.6)
    fork = K.tube("fork", [(1.88, 0.0, 1.02), (1.88, 0.0, 0.9), (2.02, 0.0, 0.9), (2.02, 0.0, 1.02)], 0.012, segs=5)
    K.place(fork, (0, 0, 0), None)
    ctx.add(fork, "paint_grey", uv="box", uv_scale=4.0, smooth=40)
    segs = 10
    pts = [Vector((-1.9 + 3.95 * i / segs, 0.0, 1.07)) for i in range(segs + 1)]
    if ctx.worn:
        brk = 6
        pivot = pts[brk]
        for i in range(brk, segs + 1):
            d = pts[i] - pivot
            pts[i] = pivot + Vector((d.x * 0.25, d.x * 0.1, -d.x * 0.95))
    for i in range(segs):
        if ctx.worn and i == 6:
            continue
        sg = W.rod_obj(f"arm{i}", pts[i], pts[i + 1], 0.035, segs=10)
        ctx.add(sg, "paint_red" if i % 2 == 0 else "paint_white", uv="cyl", uv_axis=0, uv_scale=2.0, smooth=40, patches=0.6,
                edge=1.0)
    nc = (pts[3] + pts[4]) / 2 + Vector((0, -0.04, -0.18))
    _face(ctx, "notice", 0.5, 0.25, _rect("closed_notice"), nc, 0, wear=0.7)
    for x in (-0.18, 0.18):
        wire = K.tube(f"wire{x}", [nc + Vector((x, 0.0, 0.12)), nc + Vector((x, 0.03, 0.18))], 0.002, segs=3)
        ctx.add(wire, "road_steel", uv="box", uv_scale=8.0)


def out_water_spigot(ctx: K.Ctx) -> None:
    """A frost-free hydrant over a gravel sump: green standpipe, lever head, spout and bucket hook."""
    r = ctx.rnd("spigot")
    for k in range(8):
        a = math.tau * k / 8 + r.uniform(-0.2, 0.2)
        O.add_stone(ctx, f"sump{k}", (math.cos(a) * 0.2, math.sin(a) * 0.2, 0.03), r.uniform(0.08, 0.12), ctx.seed + k, flat=0.5)
    pipe = K.cyl("standpipe", 0.03, 0.95, segs=12, center=(0, 0, 0.475))
    ctx.add(pipe, "paint_green", uv="cyl", uv_scale=2.0, smooth=40, patches=0.7, low=0.8, low_h=0.3)
    head = K.box("head", (0.09, 0.09, 0.12), center=(0, 0, 0.99), bevel=0.012)
    ctx.add(head, "paint_green", uv="box", uv_scale=3.0, smooth=35, patches=0.7, edge=1.0)
    lever = K.tube("lever", [(0, 0.03, 1.04), (0, 0.06, 1.1), (0, 0.2, 1.12)], 0.009, segs=6)
    ctx.add(lever, "paint_green", uv="box", uv_scale=4.0, smooth=40, patches=0.6)
    spout = K.tube("spout", [(0, -0.04, 0.96), (0, -0.1, 0.95), (0, -0.12, 0.89)], 0.014, segs=8)
    ctx.add(spout, "furn_brass", uv="box", uv_scale=4.0, smooth=40, patches=0.6)
    hook = K.tube("hook", [(0.03, -0.02, 0.85), (0.08, -0.02, 0.85), (0.1, -0.02, 0.8), (0.08, -0.02, 0.76)], 0.005, segs=5)
    ctx.add(hook, "road_steel", uv="box", uv_scale=6.0, smooth=40)
    ctx.col_box((-0.05, -0.05, 0), (0.05, 0.05, 1.05))


def out_camp_chair(ctx: K.Ctx) -> None:
    """A folding camp chair (seat 0.42 m): X-braced steel legs, a polyester sling seat and back,
    arms with a mesh cup holder. Destroyed: crushed flat on the ground."""
    r = ctx.rnd("chair")
    flat = ctx.destroyed
    hs = 0.27
    seat_z = 0.42
    parts0 = len(ctx.parts)
    legs = [((-hs, -0.25), (-hs, 0.22)), ((hs, -0.25), (hs, 0.22))]
    for k, (a, b) in enumerate(legs):
        W.rod(ctx, f"legx{k}a", (a[0], a[1], 0.0), (b[0], b[1] - 0.05, seat_z), 0.009, "paint_black", segs=6)
        W.rod(ctx, f"legx{k}b", (b[0], b[1], 0.0), (a[0], a[1] + 0.05, seat_z), 0.009, "paint_black", segs=6)
        W.rod(ctx, f"arm{k}", (a[0], a[1] - 0.02, seat_z + 0.2), (b[0], b[1] + 0.02, seat_z + 0.22), 0.01, "paint_black", segs=6)
        W.rod(ctx, f"armpost{k}", (a[0], a[1] - 0.02, seat_z), (a[0], a[1] - 0.02, seat_z + 0.2), 0.008, "paint_black", segs=6)
    for sy in (-1, 1):
        W.rod(ctx, f"cross{sy}", (-hs, sy * 0.24, 0.02), (hs, sy * 0.24, 0.02), 0.008, "paint_black", segs=6)
    for sx in (-1, 1):
        W.rod(ctx, f"backpost{sx}", (sx * hs, 0.22, seat_z - 0.05), (sx * hs * 1.05, 0.3, seat_z + 0.45), 0.009, "paint_black", segs=6)
    seat = K.quad_sheet("seat", (-hs, -0.24, seat_z), (hs, -0.24, seat_z), (hs, 0.2, seat_z - 0.03), (-hs, 0.2, seat_z - 0.03), 4, 4)
    K.map_verts(seat, lambda co: Vector((co.x, co.y, co.z - 0.04 * (1 - (co.x / hs) ** 2))))
    back = K.quad_sheet("back", (-hs, 0.21, seat_z), (hs, 0.21, seat_z), (hs * 1.05, 0.29, seat_z + 0.43),
                        (-hs * 1.05, 0.29, seat_z + 0.43), 4, 4)
    K.map_verts(back, lambda co: Vector((co.x, co.y + 0.03 * (1 - (co.x / hs) ** 2), co.z)))
    sling = K.merge_parts([seat, back], "sling")
    K.solidify(sling, 0.004, even=False)
    ctx.add(sling, ["out_tent_green", "out_tent_blue", "nylon_navy"][r.randrange(3)], uv="box", uv_scale=2.0, smooth=40,
            patches=0.6)
    cup = K.lathe("cupholder", [(0.035, 0.0), (0.04, 0.08)], segs=10, cap_bottom=True, cap_top=False)
    K.place(cup, (hs + 0.04, -0.1, seat_z + 0.13))
    ctx.add(cup, "chainlink", uv="box", uv_scale=6.0, ao=False)
    if flat:
        for o in ctx.parts[parts0:]:
            K.map_verts(o, lambda co: Vector((co.x * 1.1, co.y + co.z * 0.6, co.z * 0.12 + 0.01)))


def out_lockbox(ctx: K.Ctx) -> None:
    """The host's grey steel cash box: lid seam, a folding top handle, a key lock on the front."""
    w, d, h = 0.4, 0.3, 0.14
    body = K.box("body", (w, d, h * 0.62), center=(0, 0, h * 0.31), bevel=0.008, cuts=(1, 1, 0))
    ctx.add(body, "paint_grey", uv="box", uv_scale=3.0, patches=0.5, edge=1.0)
    lid = K.box("lid", (w + 0.006, d + 0.006, h * 0.38), center=(0, 0, h * 0.62 + h * 0.19 + 0.002), bevel=0.01, cuts=(1, 1, 0))
    ctx.add(lid, "paint_grey", uv="box", uv_scale=3.0, patches=0.5, edge=1.0)
    handle = K.tube("handle", [(-0.08, 0.0, h + 0.005), (-0.07, 0.0, h + 0.03), (0.07, 0.0, h + 0.03), (0.08, 0.0, h + 0.005)],
                    0.006, segs=6)
    ctx.add(handle, "road_steel", uv="box", uv_scale=6.0, smooth=40)
    lock = K.cyl("lock", 0.013, 0.012, segs=12, axis="Y", center=(0, -d / 2 - 0.005, h * 0.62))
    ctx.add(lock, "furn_brass", uv="box", uv_scale=6.0, smooth=40, patches=0.5)
    key = K.box("keyway", (0.003, 0.004, 0.012), center=(0, -d / 2 - 0.012, h * 0.62))
    ctx.add(key, "plastic_black", uv="box", uv_scale=8.0, ao=False)
    ctx.col_box((-w / 2, -d / 2, 0), (w / 2, d / 2, h))


BUILDERS = {
    "out_dock_section": out_dock_section,
    "out_dock_piles": out_dock_piles,
    "out_rowboat": out_rowboat,
    "out_rowboat_hauled": out_rowboat_hauled,
    "out_fishing_rod": out_fishing_rod,
    "out_boat_doors": out_boat_doors,
    "out_bait_tank": out_bait_tank,
    "out_tackle_wall": out_tackle_wall,
    "out_rod_rack": out_rod_rack,
    "out_life_jackets": out_life_jackets,
    "out_outboard_motor": out_outboard_motor,
    "out_net_pile": out_net_pile,
    "out_bait_sign": out_bait_sign,
    "out_trophy_fish": out_trophy_fish,
    "out_rv": out_rv,
    "out_tent_dome": out_tent_dome,
    "out_tent_cabin": out_tent_cabin,
    "out_fire_ring": out_fire_ring,
    "out_tent_pad": out_tent_pad,
    "out_bear_box": out_bear_box,
    "out_host_trailer_shell": out_host_trailer_shell,
    "out_block_roof": out_block_roof,
    "out_kiosk_shell": out_kiosk_shell,
    "out_camp_sign": out_camp_sign,
    "out_gate_arm": out_gate_arm,
    "out_water_spigot": out_water_spigot,
    "out_camp_chair": out_camp_chair,
    "out_lockbox": out_lockbox,
}


def build(params: dict, outputs: list[str]) -> None:
    K.run(params, outputs, BUILDERS)
