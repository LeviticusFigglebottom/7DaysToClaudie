"""Forest set pieces, round 4: props of the Cordon transport wreck (w4_cordon_plane_wreck).

A twin-engine transport that came down in the timber and broke in two: the forward fuselage shell (a rounded
grey-green aluminium tube round the crew bay, the cargo hold and the flight deck's hump, rivet lines and frames,
torn wing roots, the windscreen, the emergency exit, the torn end round the cargo ramp's lip, CORDON stencils), its
nose buried in a bank of earth, the tail section's shell lying crosswise (the torn end lashed shut with a tarp) and
its tail cone and fin, a torn wing section, an engine nacelle nosed into the dirt, the cargo parachute in the trees,
the burst medical supply pallet, jump seats, the flight deck's console and seats, the sample case and the trunks the
wreck snapped coming down.

Conventions (docs/ASSET_PIPELINE.md): metres, Z up, front -Y, origin bottom centre (floor props are centred on the
origin: PoiBuilder's collision box is the def's size centred there). Shells: origin at the kit rooms' plan centre on
the ground (lib.props_outskirts_parts.Room), skin outside the kit walls, openings where the plan's doors and windows
are (the catalog passes them). The fuselage cross-section is a superellipse (exponent SE_N) so the skin hugs the kit
rooms' walls; over the crew bay a second lobe rises to cover the flight deck (the "hump"). The lettered faces map
cells of the w3_signs atlas (textures/gen/wild3.py; ATLAS mirrors the two cells used).
'clean' is the wreck as it came down, 'worn' a season later.
"""
from __future__ import annotations

import math
import random

from mathutils import Matrix, Vector

from lib import props_ext_kit as K
from lib import props_outskirts_parts as O
from lib import props_wild_parts as W
from lib import materials as MAT

SKIN = "w4_plane_skin"
ALU = "road_alu"
DARK = "road_steel_dark"
GLASS = "road_glass"
SIGNS = "w3_signs"

MAT.PREVIEW_COLORS.update({"w4_plane_skin": (0.42, 0.45, 0.4), "w4_plane_webbing": (0.5, 0.15, 0.12)})

# w3_signs cells (textures/gen/wild3.py CELLS): CORDON / COMMAND - UNIT 4, and the QUARANTINE notice.
UNIT = 256
ATLAS_PX = 2048.0
ATLAS = {"cordon_cmd": (3, 5, 3, 1), "quarantine": (4, 4, 4, 1)}

SE_N = 3.5          # superellipse exponent of the fuselage section
HOLD_A = 2.4        # half width of the forward fuselage
HOLD_B = 2.2        # half height of one lobe
LOBE_UP = 3.0       # how far the flight deck lobe rises over the hold lobe (one storey)
K1 = 8              # ring points per lobe and side


def _rect(name: str, sub=None, inset: float = 2.0) -> tuple[float, float, float, float]:
    x, y, w, h = [v * UNIT for v in ATLAS[name]]
    if sub:
        fx0, fy0, fx1, fy1 = sub
        x, y, w, h = x + fx0 * w, y + fy0 * h, (fx1 - fx0) * w, (fy1 - fy0) * h
    x0, y0, x1, y1 = x + inset, y + inset, x + w - inset, y + h - inset
    return (x0 / ATLAS_PX, 1.0 - y1 / ATLAS_PX, x1 / ATLAS_PX, 1.0 - y0 / ATLAS_PX)


def _face(ctx, name, w, h, rect, loc, rot_z=0.0):
    """Flat lettered face (w x h) facing -Y with an atlas rect mapped edge to edge; rot_z 90 faces +X."""
    o = K.quad_sheet(name, (-w / 2, 0, -h / 2), (w / 2, 0, -h / 2), (w / 2, 0, h / 2), (-w / 2, 0, h / 2), 2, 2)
    K.uv_planar(o, 1, rect=rect)
    K.place(o, (0, 0, 0), (0, 0, rot_z))
    K.place(o, loc)
    return ctx.add(o, SIGNS, uv=None, wear=0.6, patches=0.35, edge=0.6)


# ============================================================================================
# Fuselage sections
# ============================================================================================

def _se_pt(t: float, a: float, b: float, zc: float) -> tuple[float, float]:
    c, s = math.cos(t), math.sin(t)
    x = a * math.copysign(abs(c) ** (2.0 / SE_N), c)
    z = zc + b * math.copysign(abs(s) ** (2.0 / SE_N), s)
    return x, z


def _se_hw(dz: float, a: float, b: float) -> float:
    """Half width of a superellipse lobe at dz above (or below) its centre."""
    t = abs(dz) / b
    return 0.0 if t >= 1.0 else a * (1.0 - t ** SE_N) ** (1.0 / SE_N)


def _ring(y: float, a: float, b: float, z1: float, z2: float, jitter=None) -> list[tuple[float, float, float]]:
    """Closed section at station y: the union of a lobe centred at z1 and one at z2 >= z1 (a single lobe when
    they meet), from the keel up the right side over the crown and down the left. A constant point count."""
    zm = (z1 + z2) / 2.0
    tw = math.asin(min(1.0, ((zm - z1) / b) ** (SE_N / 2.0))) if z2 > z1 else 0.0
    right = []
    for i in range(K1 + 1):
        t = -math.pi / 2 + (tw + math.pi / 2) * i / K1
        right.append(_se_pt(t, a, b, z1))
    for i in range(1, K1 + 1):
        t = -tw + (math.pi / 2 + tw) * i / K1
        right.append(_se_pt(t, a, b, z2))
    left = [(-x, z) for (x, z) in reversed(right[1:-1])]
    pts = right + left
    out = []
    for k, (x, z) in enumerate(pts):
        yy = y + (jitter(k) if jitter else 0.0)
        out.append((x, yy, z))
    return out


def _union_hw(z: float, a: float, b: float, z1: float, z2: float) -> float:
    zm = (z1 + z2) / 2.0
    return _se_hw(z - (z1 if z <= zm else z2), a, b)


def _hull(ctx, name, stations, *, holes=(), mat=SKIN, thick=0.04, rivets=True):
    """Skin lofted through stations (y, a, b, z1, z2[, jitter]); faces whose centre falls in a hole box
    (x0, x1, y0, y1, z0, z1) are cut out. Raised rivet lines along it and frame rings every other station."""
    rings = [_ring(s[0], s[1], s[2], s[3], s[4], s[5] if len(s) > 5 else None) for s in stations]
    o = K.loft(name, rings, cap_start=False, cap_end=False)
    if holes:
        def inside(c, _n):
            return any(h[0] < c.x < h[1] and h[2] < c.y < h[3] and h[4] < c.z < h[5] for h in holes)
        K.delete_faces(o, inside)
    K.solidify(o, thick, offset=0.0)
    ctx.add(o, mat, uv="box", uv_scale=1.0, patches=0.5, smooth=35)
    if not rivets:
        return
    n = len(rings[0])
    clean = [r for s, r in zip(stations, rings) if len(s) <= 5]

    def out_pt(p, s, k=1.012):
        zc = (s[3] + s[4]) / 2.0
        return (p[0] * k, p[1], zc + (p[2] - zc) * k)
    st_clean = [s for s in stations if len(s) <= 5]
    for idx in (3, K1, 2 * K1 - 3, n - 3, n - K1, n - 2 * K1 + 3):
        pts = [out_pt(r[idx % n], s) for r, s in zip(clean, st_clean)]
        if len(pts) > 1:
            t = K.tube(f"{name}_rivet{idx}", pts, 0.011, segs=4, caps=False)
            ctx.add(t, ALU, uv="box", uv_scale=3.0, patches=0.3)
    for j in range(0, len(clean), 2):
        s = st_clean[j]
        pts = [out_pt(p, s, 1.008) for p in clean[j]]
        if holes and any(h[2] - 0.05 < s[0] < h[3] + 0.05 for h in holes):
            continue
        t = K.tube(f"{name}_frame{j}", pts, 0.012, segs=4, closed=True)
        ctx.add(t, SKIN, uv="box", uv_scale=2.0, patches=0.4)


def _cap(ctx, name, y, hw, z_lo, z_hi, holes, mat, *, step=0.25, thick=0.03):
    """A flat end across the section at station y: bands between z_lo and z_hi bounded by hw(z) on both sides,
    cut round holes (x0, x1, z0, z1)."""
    cuts = {z_lo, z_hi}
    z = z_lo
    while z < z_hi:
        cuts.add(round(z, 4))
        z += step
    for h in holes:
        for zz in (h[2], h[3]):
            if z_lo < zz < z_hi:
                cuts.add(zz)
    cuts = sorted(cuts)
    parts = []
    hl = [(h[0], h[1], h[2], h[3]) for h in holes]
    for i in range(len(cuts) - 1):
        za, zb = cuts[i], cuts[i + 1]
        if zb - za < 0.005:
            continue
        wa, wb = hw(za), hw(zb)
        wm = max(wa, wb)
        if wm < 0.02:
            continue
        for s0, s1 in O.clip_spans(-wm, wm, za + 0.001, zb - 0.001, hl, min_len=0.01):
            x0a, x0b = (-wa, -wb) if s0 <= -wm + 1e-6 else (s0, s0)
            x1a, x1b = (wa, wb) if s1 >= wm - 1e-6 else (s1, s1)
            q = K.quad_sheet(f"{name}{i}_{s0:.2f}", (x0a, y, za), (x1a, y, za), (x1b, y, zb), (x0b, y, zb), thickness=thick)
            parts.append(q)
    if parts:
        o = K.merge_parts(parts, name)
        ctx.add(o, mat, uv="box", uv_scale=1.0, patches=0.5)


def _reveal(ctx, name, side, y0, y1, z_top, wall_x, skin_hw, *, z_bot=0.0):
    """Lines a door cut in the skin back to the kit wall: two jambs and a head between |x| = wall_x and the skin
    (skin_hw(z)), on the side sign `side`."""
    parts = []
    n = 6
    for k, y in enumerate((y0, y1)):
        for i in range(n):
            za = z_bot + (z_top - z_bot) * i / n
            zb = z_bot + (z_top - z_bot) * (i + 1) / n
            q = K.quad_sheet(f"{name}j{k}{i}", (side * wall_x, y, za), (side * (skin_hw(za) + 0.03), y, za),
                             (side * (skin_hw(zb) + 0.03), y, zb), (side * wall_x, y, zb), thickness=0.025)
            parts.append(q)
    q = K.quad_sheet(f"{name}head", (side * wall_x, y0, z_top), (side * (skin_hw(z_top) + 0.03), y0, z_top),
                     (side * (skin_hw(z_top) + 0.03), y1, z_top), (side * wall_x, y1, z_top), thickness=0.025)
    parts.append(q)
    ctx.add(K.merge_parts(parts, name), SKIN, uv="box", uv_scale=1.0, patches=0.5)
    for y in (y0, y1):
        W.bar(ctx, f"{name}frame{y:.2f}", (side * (skin_hw(z_bot) + 0.04), y, z_bot),
              (side * (skin_hw(z_top) + 0.04), y, z_top), 0.07, 0.05, DARK, up=(side, 0, 0))
    W.bar(ctx, f"{name}lintel", (side * (skin_hw(z_top) + 0.04), y0, z_top), (side * (skin_hw(z_top) + 0.04), y1, z_top),
          0.07, 0.05, DARK, up=(side, 0, 0))


def _porthole(ctx, name, side, y, z, hw):
    x = side * (hw + 0.01)
    g = K.cyl(f"{name}g", 0.17, 0.03, segs=14, center=(x, y, z), axis="X")
    ctx.add(g, GLASS, uv="box", uv_scale=2.0)
    ring = W.ring_obj(f"{name}r", 0.17, 0.22, 0.04, segs=14)
    K.place(ring, (0, 0, 0), (0, 90, 0))
    K.place(ring, (x + side * 0.01, y, z))
    ctx.add(ring, ALU, uv="box", uv_scale=3.0)


def _torn_jitter(seed: int, depth: float):
    rr = random.Random(seed)
    cache = {}

    def j(k):
        if k not in cache:
            cache[k] = -rr.uniform(0.0, depth) if rr.random() < 0.8 else -rr.uniform(depth, depth * 1.6)
        return cache[k]
    return j


def w4_plane_fuselage_fwd(ctx: K.Ctx) -> None:
    """The forward fuselage round the crew bay, the cargo hold and the flight deck (params w, d, floor,
    deck_rows, openings). The flight deck lobe rises over the first deck_rows rows; the torn end (S) is a frame
    round the hold's open end with the ramp's hinge lip over its pony walls; the N end is the windscreen. No
    collision: the kit walls hold."""
    fh = float(ctx.param("floor", 0.08))
    room = O.Room(int(ctx.param("w", 4)), int(ctx.param("d", 14)), fh)
    deck = int(ctx.param("deck_rows", 4))
    ops = [tuple(o) for o in ctx.param("openings", [])]
    hw, hd = room.w / 2, room.d / 2
    a, b = HOLD_A, HOLD_B
    z1 = fh + 1.5
    y_deck = hd - deck          # the crew bay / hold bulkhead line
    ramp0, ramp1 = y_deck - 2.7, y_deck - 0.3

    def z2_at(y):
        if y >= ramp1:
            return z1 + LOBE_UP
        if y <= ramp0:
            return z1
        u = (y - ramp0) / (ramp1 - ramp0)
        return z1 + LOBE_UP * (u * u * (3 - 2 * u))
    ys = [-hd - 0.15] + [-hd + 0.5 * i for i in range(int(room.d * 2) + 1)] + [hd + 0.15]
    ys += [ramp0 + (ramp1 - ramp0) * k / 6 for k in range(1, 6)]
    ys = sorted(set(round(y, 4) for y in ys))
    torn = _torn_jitter(ctx.seed, 0.45)
    stations = []
    for y in ys:
        st = (y, a, b, z1, z2_at(y))
        if y <= -hd - 0.1:
            st = st + (torn,)
        stations.append(st)
    # Doors cut in the skin (W/E sides), with their reveals back to the kit wall.
    holes = []
    for (side, idx, kind, lvl) in ops:
        if kind != "door" or side not in ("E", "W"):
            continue
        yc = hd - (idx + 0.5)
        sx = -1 if side == "W" else 1
        holes.append((-9 if sx < 0 else 0, 0 if sx < 0 else 9, yc - 0.5, yc + 0.5, -1.0, fh + 2.28 + lvl * 3.0))
    _hull(ctx, "hull", stations, holes=holes)
    for (x0, x1, y0, y1, zz0, zz1) in holes:
        sx = -1 if x1 <= 0 else 1
        _reveal(ctx, f"door{y0:.1f}", sx, y0, y1, zz1, hw + 0.09, lambda z: _union_hw(z, a, b, z1, z1))
    # The windscreen end: a flat front over the whole section, cut for the flight deck's windows.
    wins = []
    for (side, idx, kind, lvl) in ops:
        if side == "N" and kind == "window":
            c = -hw + idx + 0.5
            base = fh + lvl * 3.0
            wins.append((c - 0.425, c + 0.425, base + 0.825, base + 2.075))
    z2n = z1 + LOBE_UP
    _cap(ctx, "front", hd + 0.15, lambda z: _union_hw(z, a, b, z1, z2n), 0.0, z2n + b - 0.002, wins, SKIN)
    for (x0, x1, zz0, zz1) in wins:
        for xx in (x0, x1):
            W.bar(ctx, f"wsj{xx:.2f}", (xx, hd + 0.19, zz0), (xx, hd + 0.19, zz1), 0.07, 0.05, DARK, up=(0, 1, 0))
        for zz in (zz0, zz1):
            W.bar(ctx, f"wsh{x0:.2f}{zz:.1f}", (x0, hd + 0.19, zz), (x1, hd + 0.19, zz), 0.07, 0.05, DARK, up=(0, 1, 0))
    if wins:
        top = max(w[3] for w in wins)
        visor = K.box("visor", (2.6, 0.45, 0.07), center=(0, hd + 0.38, top + 0.12), bevel=0.02)
        ctx.add(visor, SKIN, uv="box", uv_scale=1.0, patches=0.5)
        for sx in (-1, 1):
            wiper = W.bar(ctx, f"wiper{sx}", (sx * 0.5, hd + 0.2, top - 1.0), (sx * 0.5 + 0.25, hd + 0.2, top - 0.45),
                          0.02, 0.015, DARK, up=(0, 1, 0))
            _ = wiper
    # The torn end: a frame round the hold's open end, the ramp's hinge lip over the pony walls.
    _cap(ctx, "torn_frame", -hd - 0.12, lambda z: _union_hw(z, a, b, z1, z1), 0.0, z1 + b - 0.002,
         [(-hw - 0.13, hw + 0.13, -1.0, fh + 3.08)], ALU, step=0.3, thick=0.05)
    lip = K.box("ramp_lip", (2 * hw + 0.2, 0.05, fh + 1.0), center=(0, -hd - 0.14, (fh + 1.0) / 2), bevel=0.01)
    ctx.add(lip, ALU, uv="box", uv_scale=1.5, patches=0.6)
    hinge = K.cyl("ramp_hinge", 0.07, 2 * hw + 0.3, segs=8, center=(0, -hd - 0.22, fh + 0.05), axis="X")
    ctx.add(hinge, DARK, uv="box", uv_scale=2.0, patches=0.5)
    rr = ctx.rnd("torn")
    for k in range(7):
        # Stringers sticking out of the tear.
        x = -hw - 0.1 + rr.uniform(0, 2 * hw + 0.2)
        side = 1 if x > 0 else -1
        z = rr.uniform(fh + 3.2, z1 + b - 0.2)
        x = side * min(abs(x), _union_hw(z, a, b, z1, z1) - 0.05)
        W.bar(ctx, f"stringer{k}", (x, -hd - 0.1, z), (x * 1.02, -hd - 0.5 - rr.uniform(0, 0.5), z - rr.uniform(0, 0.4)),
              0.04, 0.03, ALU, up=(0, 0, 1))
    for k in range(3):
        y0 = -hd - 0.1
        x = rr.uniform(-1.5, 1.5)
        cable = K.tube(f"cable{k}", [(x, y0, fh + 3.1), (x + 0.1, y0 - 0.25, fh + 2.4), (x + 0.15, y0 - 0.3, fh + 1.6)],
                       0.015, segs=5)
        ctx.add(cable, "road_rubber", uv="box", uv_scale=3.0, smooth=40)
    # The wing roots torn off on top of the hold.
    yw = y_deck - 4.2
    wing = K.prism("wing_root", [(-1.3, 0.0), (1.1, 0.0), (1.3, 0.12), (0.7, 0.34), (-0.7, 0.38), (-1.3, 0.18)],
                   6.8, plane="YZ")
    K.place(wing, (0, yw, z1 + b - 0.22))
    ctx.add(wing, SKIN, uv="box", uv_scale=1.0, patches=0.6)
    for sx in (-1, 1):
        for k in range(4):
            yy = yw - 1.0 + k * 0.6
            W.bar(ctx, f"spar{sx}{k}", (sx * 3.35, yy, z1 + b), (sx * (3.5 + rr.uniform(0, 0.3)), yy, z1 + b - 0.1 + rr.uniform(0, 0.25)),
                  0.06, 0.05, ALU, up=(0, 0, 1))
    # Portholes along the hold, the CORDON stencils, a QUARANTINE notice by the exit.
    for sx in (-1, 1):
        for y in (-5.5, -1.5, 0.5):
            if any(h[2] - 0.3 < y < h[3] + 0.3 for h in holes):
                continue
            _porthole(ctx, f"port{sx}{y:.1f}", sx, y, fh + 1.75, _union_hw(fh + 1.75, a, b, z1, z1))
        zc = fh + 2.45
        _face(ctx, f"cordon{sx}", 2.4, 0.66, _rect("cordon_cmd", (0.0, 0.0, 1.0, 0.55)),
              (sx * (_union_hw(zc, a, b, z1, z1) + 0.05), -3.4 + sx * 0.0 + (1.6 if sx < 0 else 0.0), zc), 90.0 * sx)
        stripe = K.box(f"stripe{sx}", (0.03, 6.0, 0.16), center=(sx * (_union_hw(fh + 1.25, a, b, z1, z1) + 0.03), -2.5, fh + 1.25))
        ctx.add(stripe, "road_paint_red", uv="box", uv_scale=1.0, patches=0.5)
    for (x0, x1, y0, y1, zz0, zz1) in holes:
        sx = -1 if x1 <= 0 else 1
        _face(ctx, f"qnotice{y0:.1f}", 0.9, 0.225, _rect("quarantine"), (sx * (_union_hw(fh + 1.6, a, b, z1, z1) + 0.05),
              y1 + 0.75, fh + 1.6), 90.0 * sx)
    if ctx.worn:
        for k in range(5):
            mud = K.blob(f"mud{k}", 0.6, subdiv=1, scale=(0.35, 1.2, 0.25), center=(rr.choice((-1, 1)) * 2.3, rr.uniform(-6, 5), 0.05),
                         rough=0.2, seed=ctx.seed + k)
            ctx.add(mud, "out_earth", uv="box", uv_scale=1.5, patches=0.4)


def w4_plane_fuselage_tail(ctx: K.Ctx) -> None:
    """The tail section round the tail cabin and the sample bay (params w, d, floor, openings, turn), built along
    local y and turned `turn` degrees: the torn end (local S) lashed shut with a tarp and cargo net, the bay end
    (local N) closed where the tail cone carries on, the side door cut with its reveal. No collision."""
    fh = float(ctx.param("floor", 0.08))
    room = O.Room(int(ctx.param("w", 3)), int(ctx.param("d", 7)), fh)
    ops = [tuple(o) for o in ctx.param("openings", [])]
    hw, hd = room.w / 2, room.d / 2
    z1 = fh + 1.5

    def ab(y):
        u = (y + hd + 0.15) / (2 * hd + 0.3)
        u = max(0.0, min(1.0, u))
        return HOLD_A + (1.95 - HOLD_A) * u, HOLD_B + (2.05 - HOLD_B) * u
    ys = sorted(set([-hd - 0.15] + [-hd + 0.5 * i for i in range(int(room.d * 2) + 1)] + [hd + 0.15]))
    torn = _torn_jitter(ctx.seed, 0.35)
    stations = []
    for y in ys:
        a, b = ab(y)
        st = (y, a, b, z1, z1)
        if y <= -hd - 0.1:
            st = st + (torn,)
        stations.append(st)
    holes = []
    for (side, idx, kind, lvl) in ops:
        if kind != "door" or side not in ("E", "W"):
            continue
        yc = hd - (idx + 0.5)
        sx = -1 if side == "W" else 1
        holes.append((-9 if sx < 0 else 0, 0 if sx < 0 else 9, yc - 0.5, yc + 0.5, -1.0, fh + 2.28))
    _hull(ctx, "hull", stations, holes=holes)
    for (x0, x1, y0, y1, zz0, zz1) in holes:
        sx = -1 if x1 <= 0 else 1
        a, b = ab((y0 + y1) / 2)
        _reveal(ctx, f"door{y0:.1f}", sx, y0, y1, zz1, hw + 0.09, lambda z, a=a, b=b: _se_hw(z - z1, a, b))
        _face(ctx, f"qdoor{y0:.1f}", 0.9, 0.225, _rect("quarantine"), (sx * (_se_hw(fh + 1.6, a, b) + 0.05), y1 + 0.7, fh + 1.6),
              90.0 * sx)
    a0, b0 = ab(-hd)
    _cap(ctx, "tarp", -hd - 0.12, lambda z: _se_hw(z - z1, a0, b0), 0.0, z1 + b0 - 0.002, [], "canvas_olive", step=0.3)
    rr = ctx.rnd("lash")
    for k in range(6):
        xa, xb = rr.uniform(-2.2, 2.2), rr.uniform(-2.2, 2.2)
        za, zb = rr.uniform(0.2, 1.4), rr.uniform(2.2, 3.4)
        xa = math.copysign(min(abs(xa), _se_hw(za - z1, a0, b0) - 0.05), xa)
        xb = math.copysign(min(abs(xb), _se_hw(zb - z1, a0, b0) - 0.05), xb)
        W.rod(ctx, f"net{k}", (xa, -hd - 0.17, za), (xb, -hd - 0.17, zb), 0.012, "out_net", segs=4)
    a1, b1 = ab(hd)
    _cap(ctx, "aft", hd + 0.12, lambda z: _se_hw(z - z1, a1, b1), 0.0, z1 + b1 - 0.002, [], SKIN)
    for sx in (-1, 1):
        a, b = ab(1.8)
        _face(ctx, f"quarantine{sx}", 1.6, 0.4, _rect("quarantine"), (sx * (_se_hw(fh + 2.1, a, b) + 0.05), 1.8, fh + 2.1), 90.0 * sx)
        stripe = K.box(f"stripe{sx}", (0.03, 2.4, 0.16), center=(sx * (_se_hw(fh + 1.25 - z1, a, b) + 0.03), 2.0, fh + 1.25))
        ctx.add(stripe, "road_paint_red", uv="box", uv_scale=1.0, patches=0.5)
    turn = float(ctx.param("turn", 0.0))
    if turn:
        m = Matrix.Rotation(math.radians(turn), 4, "Z")
        for o in ctx.parts:
            o.data.transform(m)
            o.data.update()


def w4_plane_nose(ctx: K.Ctx) -> None:
    """The nose cone and radome running on from the forward fuselage's front (at local y = -1.9) and drooping
    into a bank of earth and stones that buries its tip; the nose gear folded under it."""
    fh = float(ctx.param("floor", 0.08))
    z1 = fh + 1.5
    stations = []
    n = 9
    for i in range(n + 1):
        s = i / n
        y = -1.95 + 3.4 * s
        f = max(0.03, (1.0 - s ** 2.2) ** 0.5)
        stations.append((y, HOLD_A * f, HOLD_B * f, z1 - 1.0 * s, z1 - 1.0 * s))
    _hull(ctx, "nose", stations, rivets=False, thick=0.05)
    seam = [(p[0] * 1.01, p[1], p[2] * 1.0) for p in _ring(-1.95 + 3.4 * 0.45, HOLD_A * (1 - 0.45 ** 2.2) ** 0.5,
                                                            HOLD_B * (1 - 0.45 ** 2.2) ** 0.5, z1 - 0.45, z1 - 0.45)]
    ctx.add(K.tube("radome_seam", seam, 0.02, segs=4, closed=True), DARK, uv="box", uv_scale=3.0)
    berm = K.blob("berm", 1.0, subdiv=3, scale=(2.5, 1.0, 1.1), center=(0.0, 0.95, 0.15), rough=0.25, seed=ctx.seed)
    ctx.add(berm, "out_earth", uv="box", uv_scale=1.2, patches=0.4, moss=0.3)
    rr = ctx.rnd("stones")
    for k in range(9):
        O.add_stone(ctx, f"stone{k}", (rr.uniform(-2.3, 2.3), rr.uniform(0.0, 1.6), rr.uniform(0.05, 0.6)), rr.uniform(0.18, 0.4),
                    ctx.seed + k * 7)
    for sx in (-1, 1):
        W.bar(ctx, f"gear{sx}", (sx * 0.4, -1.6, 0.05), (sx * 0.3, -0.4, 0.35), 0.1, 0.1, DARK, up=(0, 0, 1))
    tyre = K.cyl("gear_tyre", 0.35, 0.22, segs=14, center=(0.0, -0.3, 0.3), axis="X")
    ctx.add(tyre, "road_rubber", uv="box", uv_scale=2.0)


def w4_plane_tail_cone(ctx: K.Ctx) -> None:
    """The tail cone sweeping up from the tail section's aft end (local y = -1.85, turned so it meets it at +X)
    to the fin, the rudder hanging askew, one tailplane snapped short."""
    fh = float(ctx.param("floor", 0.08))
    z1 = fh + 1.5
    stations = []
    n = 8
    for i in range(n + 1):
        s = i / n
        y = -1.85 + 3.6 * s
        a = 1.95 + (0.3 - 1.95) * s ** 0.9
        b = 2.05 + (0.35 - 2.05) * s ** 0.9
        zc = z1 + (3.2 - z1) * s ** 1.4
        stations.append((y, a, b, zc, zc))
    _hull(ctx, "cone", stations, thick=0.05)
    end = K.cyl("cone_tip", 0.3, 0.1, segs=12, center=(0, 1.78, 3.2), axis="Y")
    ctx.add(end, SKIN, uv="box", uv_scale=1.5)
    fin = K.prism("fin", [(-1.6, 3.2), (1.75, 3.15), (1.85, 7.45), (0.75, 7.45)], 0.22, plane="YZ")
    ctx.add(fin, SKIN, uv="box", uv_scale=1.0, patches=0.6)
    rudder = K.box("rudder", (0.12, 0.7, 3.3), center=(0.0, 0.0, 0.0), bevel=0.02)
    K.place(rudder, (0, 0, 0), (0, 0, 18))
    K.place(rudder, (0.08, 1.72, 5.2))
    ctx.add(rudder, SKIN, uv="box", uv_scale=1.0, patches=0.6)
    stripe = K.box("fin_stripe", (0.24, 2.0, 0.3), center=(0, 0.9, 6.4))
    ctx.add(stripe, "road_paint_red", uv="box", uv_scale=1.0, patches=0.5)
    for sx, L in ((1, 2.4), (-1, 0.7)):
        tp = K.prism(f"tailplane{sx}", [(-0.2, 0.0), (1.4, 0.0), (1.5, 0.1), (0.1, 0.14)], L, plane="YZ")
        K.place(tp, (sx * (L / 2 + 0.15), 0.3, 3.0))
        ctx.add(tp, SKIN, uv="box", uv_scale=1.0, patches=0.6)
    for k in range(3):
        W.bar(ctx, f"tp_spar{k}", (-0.85, 0.5 + k * 0.4, 3.05), (-1.0, 0.45 + k * 0.42, 2.9), 0.05, 0.04, ALU, up=(0, 0, 1))
    m = Matrix.Rotation(math.radians(90.0), 4, "Z")
    for o in ctx.parts:
        o.data.transform(m)
        o.data.update()


# ============================================================================================
# Debris
# ============================================================================================

def w4_plane_wing_section(ctx: K.Ctx) -> None:
    """Seven metres of torn wing lying in the brush: one end dug in, the other lifted on its broken spar, the flap
    hanging off its tracks, lines out of the torn root (worn: dented, a season of needles on it)."""
    parts_before = len(ctx.parts)
    wing = K.prism("wing", [(-1.3, 0.0), (1.1, -0.02), (1.3, 0.06), (0.7, 0.3), (-0.6, 0.34), (-1.3, 0.16)], 6.6, plane="YZ")
    if ctx.worn:
        K.crumple(wing, 0.03, scale=3.0, seed=ctx.seed)
    ctx.add(wing, SKIN, uv="box", uv_scale=1.0, patches=0.6)
    flap = K.box("flap", (2.6, 0.5, 0.06), center=(-0.8, -1.55, 0.0))
    K.place(flap, (0, 0, 0), (-25, 0, 0))
    K.place(flap, (0, 0, -0.05))
    ctx.add(flap, SKIN, uv="box", uv_scale=1.0, patches=0.6)
    rr = ctx.rnd("root")
    for k in range(5):
        y = -1.0 + k * 0.5
        W.bar(ctx, f"rib{k}", (3.3, y, 0.15), (3.5 + rr.uniform(0, 0.3), y + rr.uniform(-0.1, 0.1), 0.1 + rr.uniform(0, 0.25)),
              0.05, 0.04, ALU, up=(0, 0, 1))
    for k in range(3):
        line = K.tube(f"line{k}", [(3.3, -0.4 + k * 0.3, 0.18), (3.7, -0.3 + k * 0.3, 0.1), (3.9, -0.5 + k * 0.35, 0.02)], 0.02, segs=5)
        ctx.add(line, "road_rubber", uv="box", uv_scale=3.0, smooth=40)
    tip = K.box("tip_light", (0.12, 0.3, 0.1), center=(-3.36, 0.0, 0.15))
    ctx.add(tip, "lens_red", uv="box", uv_scale=3.0)
    m = Matrix.Translation((0, 0, 0.45)) @ Matrix.Rotation(math.radians(-6.0), 4, "Y") @ Matrix.Rotation(math.radians(5.0), 4, "X")
    for o in ctx.parts[parts_before:]:
        o.data.transform(m)
        o.data.update()
    dirt = K.blob("dirt", 0.8, subdiv=2, scale=(1.0, 1.6, 0.35), center=(-3.2, 0.0, 0.05), rough=0.25, seed=ctx.seed)
    ctx.add(dirt, "out_earth", uv="box", uv_scale=1.5, patches=0.4, moss=0.3)


def w4_plane_engine(ctx: K.Ctx) -> None:
    """A turboprop nacelle nosed into the dirt: the cowling split, the spinner and its four blades bent back."""
    tilt = Matrix.Translation((0, 0, 0.0)) @ Matrix.Rotation(math.radians(-12.0), 4, "X")
    start = len(ctx.parts)
    body = K.cyl("nacelle", 0.55, 2.8, segs=16, center=(0, 0.3, 0.9), axis="Y", r_top=0.4)
    if ctx.worn:
        K.crumple(body, 0.03, scale=3.0, seed=ctx.seed)
    ctx.add(body, SKIN, uv="cyl", uv_axis=1, uv_scale=1.0, patches=0.6, smooth=40)
    intake = K.cyl("intake", 0.3, 0.3, segs=12, center=(0, -1.1, 0.6), axis="Y")
    ctx.add(intake, DARK, uv="box", uv_scale=2.0)
    spinner = K.cyl("spinner", 0.26, 0.5, segs=14, center=(0, -1.35, 0.9), axis="Y", r_top=0.05)
    K.place(spinner, (0, 0, 0))
    ctx.add(spinner, SKIN, uv="box", uv_scale=2.0, smooth=40)
    rr = ctx.rnd("blades")
    for k in range(4):
        ang = k * 90 + 20
        bl = K.box(f"blade{k}", (0.2, 0.05, 1.25), center=(0, 0, 0.62), bevel=0.01)
        K.place(bl, (0, 0, 0), (rr.uniform(25, 60), 0, 0))
        K.place(bl, (0, 0, 0), (0, ang, 0))
        K.place(bl, (0, -1.25, 0.9))
        ctx.add(bl, "road_paint_black", uv="box", uv_scale=2.0, patches=0.6)
    for k in range(3):
        W.bar(ctx, f"mount{k}", (-0.3 + k * 0.3, 1.6, 1.2), (-0.35 + k * 0.32, 2.0, 1.45), 0.06, 0.06, ALU, up=(0, 0, 1))
    for o in ctx.parts[start:]:
        o.data.transform(tilt)
        o.data.update()
    mound = K.blob("mound", 0.8, subdiv=2, scale=(1.5, 1.0, 0.45), center=(0, -1.25, 0.05), rough=0.3, seed=ctx.seed)
    ctx.add(mound, "out_earth", uv="box", uv_scale=1.5, patches=0.4, moss=0.25)


def w4_plane_parachute(ctx: K.Ctx) -> None:
    """A cargo canopy caught high in the trees: a crumpled dome sagging on one side, rigging lines down to a torn
    harness and a split strap on the ground (clean: white; worn: olive, weathered)."""
    R = 3.0
    o = K.grid("canopy", 6.0, 6.0, 16, 16)
    K.uv_planar(o, 2, scale=1.0)

    def shape(co):
        x, y = co.x, co.y
        r = min(1.0, math.hypot(x, y) / R)
        z = 5.2 - 1.5 * r * r
        if y < 0:
            z -= 2.0 * (-y / R) ** 2
        z += 0.25 * math.sin(x * 2.1) * r
        return Vector((x * 0.95, y * 0.9, z))
    K.map_verts(o, shape)
    K.crumple(o, 0.12, scale=2.0, seed=ctx.seed)
    K.solidify(o, 0.01, offset=0.0, even=False)
    ctx.add(o, "w3_canvas_white" if ctx.clean else "canvas_olive", uv=None, smooth=50, patches=0.5)
    harness = (1.2, -0.8, 0.08)
    rr = ctx.rnd("lines")
    for k in range(10):
        a = 2 * math.pi * k / 10
        top = (math.cos(a) * 2.6 * 0.95, math.sin(a) * 2.6 * 0.9, 0.0)
        r = min(1.0, math.hypot(top[0], top[1]) / R)
        z = 5.2 - 1.5 * r * r - (2.0 * (-top[1] / R) ** 2 if top[1] < 0 else 0.0)
        W.rod(ctx, f"line{k}", (top[0], top[1], z - 0.05), (harness[0] + rr.uniform(-0.1, 0.1), harness[1], 0.45), 0.008, "road_rope", segs=4)
    box = K.box("harness", (0.6, 0.4, 0.1), center=harness, bevel=0.02)
    ctx.add(box, "canvas_olive", uv="box", uv_scale=2.0)
    strap = K.box("strap", (1.4, 0.07, 0.01), center=(0.4, -1.1, 0.02))
    K.place(strap, (0, 0, 0))
    ctx.add(strap, "canvas_olive", uv="box", uv_scale=2.0)


def w4_plane_cargo_pallet(ctx: K.Ctx) -> None:
    """An aluminium cargo pallet that burst on landing: cartons stacked two and three high in a split net, some
    tipped off its side, red crosses on the cartons."""
    plate = K.box("plate", (2.2, 2.7, 0.06), center=(0, 0, 0.03), bevel=0.01)
    ctx.add(plate, ALU, uv="box", uv_scale=1.0, patches=0.5)
    for sx in (-1, 1):
        W.bar(ctx, f"rail{sx}", (sx * 1.1, -1.35, 0.06), (sx * 1.1, 1.35, 0.06), 0.06, 0.06, DARK, up=(0, 0, 1))
    rr = ctx.rnd("cartons")
    tops = []
    for i in range(3):
        for j in range(4):
            x = -0.7 + i * 0.7
            y = -1.0 + j * 0.66
            h = 3 if (i + j) % 3 else 2
            if ctx.worn and j == 0 and i == 2:
                h = 1
            for k in range(h):
                cb = K.box(f"c{i}{j}{k}", (0.62, 0.58, 0.36), center=(x + rr.uniform(-0.03, 0.03), y + rr.uniform(-0.03, 0.03), 0.06 + 0.18 + k * 0.37),
                           bevel=0.01)
                K.place(cb, (0, 0, 0))
                ctx.add(cb, "road_cardboard", uv="box", uv_scale=1.5, patches=0.6)
                if k == h - 1:
                    tops.append((x, y, 0.06 + 0.36 + k * 0.37))
            if i == 0:
                for bar in ((0.36, 0.08), (0.08, 0.36)):
                    rc = K.box(f"x{i}{j}{bar[0]}", (0.005, bar[0] * 0.6, bar[1] * 0.6), center=(x - 0.315, y, 0.06 + 0.18 + (h - 1) * 0.37))
                    ctx.add(rc, "road_paint_red", uv="box", uv_scale=2.0)
    for k in range(4):
        x0, y0, z0 = tops[k * 2]
        x1, y1, z1 = tops[(k * 2 + 5) % len(tops)]
        W.rod(ctx, f"net{k}", (x0, y0, z0 + 0.01), (x1, y1, z1 + 0.01), 0.012, "out_net", segs=4)
    for k in range(3):
        cb = K.box(f"spill{k}", (0.6, 0.55, 0.36), center=(0, 0, 0.18), bevel=0.01)
        K.place(cb, (0, 0, 0), (rr.uniform(-15, 15), rr.uniform(70, 95) if k == 0 else 0, rr.uniform(0, 90)))
        K.place(cb, (1.15 - k * 0.35 if k else 0.85, -1.15 + k * 0.5 if k else 1.05, 0.0))
        K.lift_min(cb, 0.0)
        ctx.add(cb, "road_cardboard", uv="box", uv_scale=1.5, patches=0.6)


# ============================================================================================
# Inside
# ============================================================================================

def w4_plane_seat_row(ctx: K.Ctx) -> None:
    """Two metres of troop jump seats: four red webbing seats on an aluminium tube frame, the back webbing laced to
    a rail at the wall (origin bottom centre, back at +y)."""
    for x in (-0.98, -0.5, 0.0, 0.5, 0.98):
        W.rod(ctx, f"leg{x:.2f}", (x, -0.2, 0.0), (x, -0.2, 0.42), 0.014, ALU, segs=6)
        W.rod(ctx, f"strut{x:.2f}", (x, -0.2, 0.42), (x, 0.22, 0.42), 0.012, ALU, segs=6)
    W.rod(ctx, "front_rail", (-1.0, -0.2, 0.42), (1.0, -0.2, 0.42), 0.016, ALU, segs=6)
    W.rod(ctx, "back_rail", (-1.0, 0.22, 0.42), (1.0, 0.22, 0.42), 0.016, ALU, segs=6)
    W.rod(ctx, "top_rail", (-1.0, 0.23, 1.06), (1.0, 0.23, 1.06), 0.016, ALU, segs=6)
    for k, x in enumerate((-0.75, -0.25, 0.25, 0.75)):
        sag = 0.02 if ctx.clean else 0.05
        seat = K.box(f"seat{k}", (0.46, 0.42, 0.012), center=(x, 0.01, 0.42 - sag), cuts=(2, 2, 0))
        ctx.add(seat, "w4_plane_webbing", uv="box", uv_scale=2.0, patches=0.5)
        back = K.box(f"back{k}", (0.46, 0.012, 0.52), center=(x, 0.21, 0.78), cuts=(2, 0, 2))
        ctx.add(back, "w4_plane_webbing", uv="box", uv_scale=2.0, patches=0.5)
    if ctx.worn:
        strap = K.box("strap", (0.04, 0.3, 0.005), center=(0.3, -0.25, 0.3))
        K.place(strap, (0, 0, 0))
        ctx.add(strap, "canvas_olive", uv="box", uv_scale=3.0)


def w4_plane_cockpit_console(ctx: K.Ctx) -> None:
    """The instrument panel under its glare shield along the windscreen wall (back at +y), the centre pedestal
    with throttles and radio heads reaching back between the seats, gauges (worn: cracked, a panel hanging)."""
    panel = K.box("panel", (3.2, 0.42, 0.86), center=(0, 0.29, 0.43), bevel=0.02)
    ctx.add(panel, "road_paint_black", uv="box", uv_scale=1.5, patches=0.4)
    shield = K.box("shield", (3.1, 0.3, 0.1), center=(0, 0.1, 0.94), bevel=0.02)
    ctx.add(shield, "road_paint_black", uv="box", uv_scale=1.5, patches=0.4)
    ped = K.box("pedestal", (0.5, 0.92, 0.72), center=(0, -0.04, 0.36), bevel=0.02)
    ctx.add(ped, DARK, uv="box", uv_scale=1.5, patches=0.4)
    rr = ctx.rnd("gauges")
    for sx in (-1, 1):
        for i in range(3):
            for j in range(2):
                g = K.cyl(f"g{sx}{i}{j}", 0.055, 0.02, segs=10, center=(sx * (0.6 + i * 0.2), 0.075, 0.58 + j * 0.16), axis="Y")
                ctx.add(g, GLASS if (ctx.clean or rr.random() < 0.6) else "road_paint_white", uv="box", uv_scale=3.0)
    for k in range(4):
        W.rod(ctx, f"throttle{k}", (-0.15 + k * 0.1, -0.2, 0.72), (-0.15 + k * 0.1, -0.3, 0.86), 0.012, ALU, segs=5)
        knob = K.box(f"knob{k}", (0.04, 0.04, 0.04), center=(-0.15 + k * 0.1, -0.3, 0.88))
        ctx.add(knob, "road_paint_black" if k % 2 else "road_paint_red", uv="box", uv_scale=3.0)
    for j in range(3):
        rad = K.box(f"radio{j}", (0.4, 0.02, 0.1), center=(0, -0.5, 0.18 + j * 0.15))
        ctx.add(rad, "road_paint_black", uv="box", uv_scale=3.0)
    if ctx.worn:
        hang = K.box("hanging_panel", (0.5, 0.02, 0.3), center=(0.9, 0.06, 0.25))
        K.place(hang, (0, 0, 0))
        ctx.add(hang, "road_paint_black", uv="box", uv_scale=2.0)


def w4_plane_pilot_seat(ctx: K.Ctx) -> None:
    """A flight deck seat on its pedestal rail: steel bucket, grey cushion, headrest, harness straps."""
    base = K.box("base", (0.4, 0.5, 0.3), center=(0, 0.0, 0.15), bevel=0.02)
    ctx.add(base, DARK, uv="box", uv_scale=2.0, patches=0.4)
    cush = K.box("cushion", (0.52, 0.5, 0.14), center=(0, -0.02, 0.41), bevel=0.04, bevel_segs=2)
    ctx.add(cush, "road_vinyl_black", uv="box", uv_scale=2.0, smooth=40, patches=0.4)
    back = K.box("back", (0.52, 0.12, 0.7), center=(0, 0.25, 0.85), bevel=0.04, bevel_segs=2)
    K.place(back, (0, 0, 0))
    ctx.add(back, "road_vinyl_black", uv="box", uv_scale=2.0, smooth=40, patches=0.4)
    head = K.box("head", (0.3, 0.12, 0.2), center=(0, 0.27, 1.15), bevel=0.03)
    ctx.add(head, "road_vinyl_black", uv="box", uv_scale=2.0, smooth=40)
    for sx in (-1, 1):
        W.bar(ctx, f"arm{sx}", (sx * 0.28, -0.2, 0.62), (sx * 0.28, 0.2, 0.62), 0.05, 0.04, DARK, up=(0, 0, 1))
        W.bar(ctx, f"strap{sx}", (sx * 0.15, 0.2, 1.1), (sx * 0.12, -0.05 if ctx.clean else 0.0, 0.5), 0.05, 0.008, "canvas_olive",
              up=(0, -1, 0))


def w4_plane_sample_case(ctx: K.Ctx) -> None:
    """A steel cold-chain flight case on a low stand: corner caps, latches, a red seal, QUARANTINE on its front."""
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.rod(ctx, f"leg{sx}{sy}", (sx * 0.38, sy * 0.22, 0.0), (sx * 0.38, sy * 0.22, 0.22), 0.015, ALU, segs=5)
    shelf = K.box("stand", (0.86, 0.52, 0.03), center=(0, 0, 0.22))
    ctx.add(shelf, ALU, uv="box", uv_scale=2.0)
    case = K.box("case", (0.8, 0.48, 0.48), center=(0, 0, 0.475), bevel=0.02, cuts=(2, 1, 1))
    ctx.add(case, ALU, uv="box", uv_scale=1.5, patches=0.4)
    for sx in (-1, 1):
        lat = K.box(f"latch{sx}", (0.06, 0.03, 0.08), center=(sx * 0.25, -0.25, 0.62))
        ctx.add(lat, DARK, uv="box", uv_scale=3.0)
    seal = K.box("seal", (0.08, 0.02, 0.05), center=(0.0, -0.25, 0.69))
    ctx.add(seal, "road_paint_red", uv="box", uv_scale=3.0)
    _face(ctx, "label", 0.6, 0.15, _rect("quarantine"), (0.0, -0.245, 0.43))
    if ctx.worn:
        dent = K.box("frost", (0.7, 0.45, 0.005), center=(0, 0, 0.72))
        ctx.add(dent, "road_paint_white", uv="box", uv_scale=3.0)


def w4_plane_snapped_trunk(ctx: K.Ctx) -> None:
    """A fir snapped off about 2.6 m up: bark-on trunk, the break a fan of raw splinters (worn: greyed, moss)."""
    O.add_log_between(ctx, "trunk", (0, 0, -0.05), (0.03, 0.02, 2.6), 0.3, ctx.seed, mat_bark="w3_log_bark",
                      mat_end="wood_log_end", sides=10, rings=4, taper=0.05, moss=0.25 if ctx.clean else 0.5)
    rr = ctx.rnd("splinters")
    for k in range(9):
        a = 2 * math.pi * k / 9 + rr.uniform(-0.2, 0.2)
        r = rr.uniform(0.08, 0.24)
        x, y = math.cos(a) * r, math.sin(a) * r
        h = rr.uniform(0.25, 0.6)
        sp = K.cyl(f"spl{k}", rr.uniform(0.04, 0.07), h, segs=5, r_top=0.005, center=(0, 0, h / 2))
        K.place(sp, (0, 0, 0), (rr.uniform(-12, 12), rr.uniform(-12, 12), 0))
        K.place(sp, (x + 0.03, y + 0.02, 2.55))
        ctx.add(sp, "out_log_peeled", uv="box", uv_scale=2.0, patches=0.4)


BUILDERS = {
    "w4_plane_fuselage_fwd": w4_plane_fuselage_fwd,
    "w4_plane_fuselage_tail": w4_plane_fuselage_tail,
    "w4_plane_nose": w4_plane_nose,
    "w4_plane_tail_cone": w4_plane_tail_cone,
    "w4_plane_wing_section": w4_plane_wing_section,
    "w4_plane_engine": w4_plane_engine,
    "w4_plane_parachute": w4_plane_parachute,
    "w4_plane_cargo_pallet": w4_plane_cargo_pallet,
    "w4_plane_seat_row": w4_plane_seat_row,
    "w4_plane_cockpit_console": w4_plane_cockpit_console,
    "w4_plane_pilot_seat": w4_plane_pilot_seat,
    "w4_plane_sample_case": w4_plane_sample_case,
    "w4_plane_snapped_trunk": w4_plane_snapped_trunk,
}


def build(params: dict, outputs: list[str]) -> None:
    K.run(params, outputs, BUILDERS)
