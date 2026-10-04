"""POI kit walls (docs/POI_KIT.md): plain walls with openings + casing trim, pony wall, corner post,
layered damaged / water-damaged / breach walls and the Voronoi fracture set.

params:
  kind: "wall" | "post" | "layered" | "frac"
  name, seed
  wall:    length, height (2.8), thickness (0.16), opening (None | window_1m | window_2m | door_1m | door_2m),
           cap (pony-wall cap board)
  layered: mode ("damaged" | "worn" | "breach")
  frac:    pieces
Materials: M_kit_wall (finish faces, side tagged in UVSide), M_kit_trim, M_kit_stairs (threshold),
M_kit_wall_inner (broken plaster / cavity), M_wood_raw (studs, lath).
"""
from __future__ import annotations

import math

import bpy
from mathutils import Vector

from lib import common, fracture
from lib import kit_poly as P
from lib.kit_dims import (CASING_T, CASING_W, HALF_T, HEAD_H, JAMB_T, LATH_PITCH, LATH_T, LATH_W, OPENINGS,
                          PLATE_H, SILL_PROUD, SILL_T, SKIN_T, STUD_D, STUD_W, WALL_H, WALL_T)
from lib.kit_geo import SIDE_A, SIDE_B, SIDE_N, KitMesh, bake_colors, collision_box, export_glb, fix_chunks
from lib.kit_parts import board, plaster_flake, rubble, sliver


# -------------------------------------------------------------------------------------------------
# Plain walls
# -------------------------------------------------------------------------------------------------

def _wall_body(km: KitMesh, L: float, H: float, T: float, opening: str | None) -> tuple:
    """Finish slab with the ROUGH opening (clear opening + jamb linings / sill board)."""
    h2 = T / 2
    rect = [(-L / 2, 0.0), (L / 2, 0.0), (L / 2, H), (-L / 2, H)]
    loops = [rect]
    rough = None
    if opening:
        w, h, s = OPENINGS[opening]
        rx = w / 2 + JAMB_T
        top = s + h + JAMB_T
        if opening.startswith("door"):
            rough = (-rx, rx, 0.0, top)
            loops = [[(-L / 2, 0.0), (-rx, 0.0), (-rx, top), (rx, top), (rx, 0.0), (L / 2, 0.0), (L / 2, H), (-L / 2, H)]]
        else:
            rough = (-rx, rx, s - SILL_T, top)
            loops = [rect, [(-rx, s - SILL_T), (rx, s - SILL_T), (rx, top), (-rx, top)]]
    km.part(0.0)
    km.prism(loops, -h2, h2, axis="y", mat="kit_wall", side=(SIDE_A, SIDE_B, SIDE_N))
    return rough


def _chamfer_board_x(km: KitMesh, x0: float, x1: float, y0: float, y1: float, z0: float, z1: float, mat: str,
                     side: float, ch: float = 0.006, top_only: bool = True) -> None:
    """Board running along X with chamfered top edges (profile in the YZ plane)."""
    ch = min(ch, (y1 - y0) / 3, (z1 - z0) / 2)
    prof = [(y0, z0), (y1, z0), (y1, z1 - ch), (y1 - ch, z1), (y0 + ch, z1), (y0, z1 - ch)]
    if not top_only:
        prof = [(y0, z0 + ch), (y0 + ch, z0), (y1 - ch, z0), (y1, z0 + ch)] + prof[2:]
    km.prism([prof], x0, x1, axis="x", mat=mat, side=(side, side, side), grain="x")


def _casing(km: KitMesh, x0, x1, z0, z1, sy: float, proud: float, side: float, grain: str, ch: float = 0.004,
            skip=()) -> None:
    """Flat trim board on a wall face (sy = -1 side A / +1 side B) with eased front edges."""
    y_in = sy * HALF_T
    y_out = sy * (HALF_T + proud)
    if grain == "z":
        # profile in the XY plane extruded along Z
        e = min(ch, (x1 - x0) / 3)
        prof = [(x0, y_in), (x1, y_in), (x1, y_out - sy * e), (x1 - e, y_out), (x0 + e, y_out), (x0, y_out - sy * e)]
        km.prism([prof], z0, z1, axis="z", mat="kit_trim", side=(side, side, side), grain="z",
                 caps=("-z" not in skip, "+z" not in skip))
    else:
        e = min(ch, (z1 - z0) / 3)
        prof = [(y_in, z0), (y_in, z1), (y_out - sy * e, z1), (y_out, z1 - e), (y_out, z0 + e), (y_out - sy * e, z0)]
        km.prism([prof], x0, x1, axis="x", mat="kit_trim", side=(side, side, side), grain="x")


def _opening_trim(km: KitMesh, opening: str, L: float, rng) -> None:
    w, h, s = OPENINGS[opening]
    door = opening.startswith("door")
    T = HALF_T
    top = s + h
    lim = L / 2
    # Jamb linings (full wall depth, faces into the opening).
    km.part(rng.uniform(0.3, 0.7))
    for sx in (-1, 1):
        xa, xb = sorted((sx * w / 2, sx * (w / 2 + JAMB_T)))
        km.box((xa, -T, s), (xb, T, top), "kit_trim", side=SIDE_N, grain="z",
               skip=("+x" if sx > 0 else "-x", "-y", "+y", "-z", "+z"))
    km.box((-w / 2 - JAMB_T, -T, top), (w / 2 + JAMB_T, T, top + JAMB_T), "kit_trim", side=SIDE_N, grain="x",
           skip=("+z", "-y", "+y", "-x", "+x"))
    # Stops: doors close against stops on the +Y half; sashes run between blind / inner stops.
    if door:
        stops = [(0.022, 0.058, 0.012)]
    else:
        stops = [(-0.052, -0.036, 0.014), (0.038, 0.054, 0.014)]
    for y0, y1, d in stops:
        for sx in (-1, 1):
            xa, xb = sorted((sx * (w / 2 - d), sx * w / 2))
            km.box((xa, y0, s), (xb, y1, top - d), "kit_trim", side=SIDE_N, grain="z", skip=("-z",))
        km.box((-w / 2 + d, y0, top - d), (w / 2 - d, y1, top), "kit_trim", side=SIDE_N, grain="x", skip=("+z",))
    # Casings on both faces.
    for sy, side in ((-1, SIDE_A), (1, SIDE_B)):
        km.part(rng.uniform(0.3, 0.7))
        ext = min(w / 2 + CASING_W, lim)
        for sx in (-1, 1):
            xa, xb = sorted((sx * w / 2, sx * ext))
            _casing(km, xa, xb, s, top, sy, CASING_T, side, "z", skip=("-z", "+z"))
        hx = min(ext + 0.012, lim)
        _casing(km, -hx, hx, top, top + HEAD_H, sy, CASING_T + 0.004, side, "x")
        cx = min(hx + 0.01, lim)
        _casing(km, -cx, cx, top + HEAD_H, top + HEAD_H + 0.022, sy, CASING_T + 0.016, side, "x", ch=0.006)
        if not door:
            ax = ext - 0.006
            _casing(km, -ax, ax, s - SILL_T - 0.075, s - SILL_T, sy, CASING_T - 0.002, side, "x")
    if door:
        km.part(rng.uniform(0.3, 0.7))
        prof = [(-0.088, 0.0), (0.088, 0.0), (0.07, 0.010), (-0.07, 0.010)]
        km.prism([prof], -w / 2, w / 2, axis="x", mat="kit_stairs", side=(SIDE_N, SIDE_N, SIDE_N), grain="x")
    else:
        # Window stool: one board through the opening, projecting on both faces, with horns.
        km.part(rng.uniform(0.3, 0.7))
        sx = min(w / 2 + CASING_W + 0.028, lim)
        sy_ = T + CASING_T + SILL_PROUD
        _chamfer_board_x(km, -sx, sx, -sy_, sy_, s - SILL_T, s, "kit_trim", SIDE_N, ch=0.008, top_only=False)


def build_wall(p: dict, name: str, outputs: list[str]) -> None:
    rng = common.rng(p.get("seed", 1))
    L = float(p.get("length", 1.0))
    H = float(p.get("height", WALL_H))
    T = float(p.get("thickness", WALL_T))
    opening = p.get("opening")
    km = KitMesh(name)
    cap = bool(p.get("cap", False))
    body_h = H - 0.022 if cap else H
    rough = _wall_body(km, L, body_h, T, opening)
    if opening:
        _opening_trim(km, opening, L, rng)
    if cap:
        km.part(rng.uniform(0.3, 0.7))
        _chamfer_board_x(km, -L / 2, L / 2, -T / 2 - 0.028, T / 2 + 0.028, body_h, H, "kit_trim", SIDE_N, ch=0.007,
                         top_only=False)
    obj = km.build()
    bake_colors(obj, ground_z=0.0, ceiling_z=None if H < 2.0 else H, samples=16, distance=0.25, strength=0.7,
                seed=int(p.get("seed", 1)))
    cols = []
    h2 = T / 2
    if rough is None:
        cols.append(collision_box(f"{name}_col0", (-L / 2, -h2, 0.0), (L / 2, h2, H)))
    else:
        x0, x1, z0, z1 = rough
        boxes = [((-L / 2, -h2, 0.0), (x0, h2, H)), ((x1, -h2, 0.0), (L / 2, h2, H)), ((x0, -h2, z1), (x1, h2, H))]
        if z0 > 0.0:
            boxes.append(((x0, -h2, 0.0), (x1, h2, z0)))
        for i, (lo, hi) in enumerate(boxes):
            if hi[0] - lo[0] > 1e-4 and hi[2] - lo[2] > 1e-4:
                cols.append(collision_box(f"{name}_col{i}", lo, hi))
    export_glb(outputs[0], [obj] + cols)


def build_post(p: dict, name: str, outputs: list[str]) -> None:
    """Corner post centred on the grid vertex, 1 mm proud of the wall faces it meets (and 1 mm taller)
    so the junction never z-fights. -X/-Y faces are side A, +X/+Y side B (rotate in 90 deg steps)."""
    s = WALL_T / 2 + 0.001
    H = float(p.get("height", WALL_H)) + 0.001
    km = KitMesh(name)
    km.part(0.0)
    km.box((-s, -s, 0.0), (s, s, H), "kit_wall", sides={"-x": SIDE_A, "-y": SIDE_A, "+x": SIDE_B, "+y": SIDE_B,
                                                         "-z": SIDE_N, "+z": SIDE_N})
    obj = km.build()
    bake_colors(obj, ground_z=0.0, samples=8)
    export_glb(outputs[0], [obj, collision_box(f"{name}_col0", (-s, -s, 0.0), (s, s, H))])


# -------------------------------------------------------------------------------------------------
# Layered construction: damaged / water-damaged / breach
# -------------------------------------------------------------------------------------------------

def _on_rect_edge(L: float, H: float):
    """Rim filter dropping skin edges on the piece boundary (covered by the full-thickness caps)."""
    def keep(a, b) -> bool:
        if abs(a[0] - b[0]) < 1e-6 and abs(abs(a[0]) - L / 2) < 1e-6:
            return False
        if abs(a[1] - b[1]) < 1e-6 and (abs(a[1]) < 1e-6 or abs(a[1] - H) < 1e-6):
            return False
        return True
    return keep


def _top_at(hole: list, x: float) -> float:
    """Highest crossing of the hole outline at abscissa x (the hole's top edge there)."""
    zs = P.x_span_at([(z, xx) for xx, z in hole], x)
    return max(zs) if zs else P.bounds(hole)[3]


def _skin(km: KitMesh, loops, side: str, L: float, H: float, inner_loops=None) -> None:
    """Plaster skin of side A (y -0.08..-0.058) or B (0.058..0.08) with holes. inner_loops = the
    holes without crack slits for the cavity-side face (cracks become blind grooves)."""
    keep = _on_rect_edge(L, H)
    km.part(0.0)
    if side == "A":
        km.prism(loops, -HALF_T, -HALF_T + SKIN_T, axis="y", mat="kit_wall", mat_back="kit_wall_inner",
                 mat_rim="kit_wall_inner", side=(SIDE_A, SIDE_N, SIDE_N), rim_filter=keep, back_loops=inner_loops)
    else:
        km.prism(loops, HALF_T - SKIN_T, HALF_T, axis="y", mat="kit_wall_inner", mat_back="kit_wall",
                 mat_rim="kit_wall_inner", side=(SIDE_N, SIDE_B, SIDE_N), rim_filter=keep, front_loops=inner_loops)


def _caps(km: KitMesh, L: float, H: float) -> None:
    """Full-thickness end / top / bottom faces (same as a plain wall) closing the cavity."""
    km.part(0.0)
    T = HALF_T
    km.quad([(-L / 2, T, 0.0), (-L / 2, -T, 0.0), (-L / 2, -T, H), (-L / 2, T, H)], "kit_wall", side=SIDE_N)
    km.quad([(L / 2, -T, 0.0), (L / 2, T, 0.0), (L / 2, T, H), (L / 2, -T, H)], "kit_wall", side=SIDE_N)
    km.quad([(-L / 2, -T, H), (L / 2, -T, H), (L / 2, T, H), (-L / 2, T, H)], "kit_wall", side=SIDE_N)
    km.quad([(-L / 2, T, 0.0), (L / 2, T, 0.0), (L / 2, -T, 0.0), (-L / 2, -T, 0.0)], "kit_wall", side=SIDE_N)


def _frame_members(km: KitMesh, L: float, H: float, studs: list[float], rng) -> None:
    d = STUD_D
    km.part(rng.uniform(0.3, 0.7))
    km.box((-L / 2, -d, 0.0), (L / 2, d, PLATE_H), "wood_raw", grain="x", skip=("-z", "-x", "+x"))
    km.part(rng.uniform(0.3, 0.7))
    km.box((-L / 2, -d, H - 2 * PLATE_H), (L / 2, d, H), "wood_raw", grain="x", skip=("+z", "-x", "+x"))
    for x in (-L / 2 + STUD_W / 2, L / 2 - STUD_W / 2):
        km.part(rng.uniform(0.3, 0.7))
        km.box((x - STUD_W / 2, -d, PLATE_H), (x + STUD_W / 2, d, H - 2 * PLATE_H), "wood_raw", grain="z",
               skip=("-x",) if x < 0 else ("+x",))
    for x in studs:
        km.part(rng.uniform(0.3, 0.7))
        km.box((x - STUD_W / 2, -d, PLATE_H), (x + STUD_W / 2, d, H - 2 * PLATE_H), "wood_raw", grain="z",
               uv_off=(rng.uniform(0, 3), rng.uniform(0, 3)))


def _lath_rows(z0: float, z1: float) -> list[float]:
    out = []
    z = PLATE_H + LATH_W / 2 + 0.004
    while z < z1 + LATH_PITCH:
        if z > z0 - LATH_PITCH:
            out.append(z)
        z += LATH_PITCH
    return out


def _lath_behind(km: KitMesh, hole: list, side: str, rng, *, broken_frac: float, missing_frac: float,
                 margin: float = 0.07, through: list | None = None) -> None:
    """Lath strips behind a hole of skin `side`. Strips crossing `through` (a polygon where the lath
    itself is knocked out) are cut at its edges with splintered ends."""
    x0, z0, x1, z1 = P.bounds(hole)
    sy = -1 if side == "A" else 1
    yc = sy * (HALF_T - SKIN_T - LATH_T / 2)
    for zc in _lath_rows(z0, z1):
        xs = P.x_span_at(hole, zc)
        if len(xs) < 2:
            # strip passes above/below the hole within the margin: hidden, skip
            continue
        a, b = xs[0] - margin, xs[-1] + margin
        a, b = max(a, -0.49), min(b, 0.49)
        km.part(rng.uniform(0.2, 0.8))
        cut = None
        if through is not None:
            ts = P.x_span_at(through, zc)
            if len(ts) >= 2:
                cut = (ts[0] + rng.uniform(-0.01, 0.03), ts[-1] - rng.uniform(-0.01, 0.03))
        if cut is None and rng.random() < missing_frac:
            m = (xs[0] + xs[-1]) / 2
            cut = (m - rng.uniform(0.02, 0.08), m + rng.uniform(0.02, 0.08))
        elif cut is None and rng.random() < broken_frac:
            m = rng.uniform(xs[0] + 0.02, xs[-1] - 0.02) if xs[-1] - xs[0] > 0.05 else (xs[0] + xs[-1]) / 2
            cut = (m - rng.uniform(0.003, 0.02), m + rng.uniform(0.003, 0.02))
        wd = Vector((0, 0, 1))
        if cut is None or cut[1] <= cut[0]:
            board(km, (a, yc, zc), (b, yc, zc), wd, LATH_W, LATH_T, mat="wood_raw", rng=rng)
        else:
            if cut[0] - a > 0.02:
                board(km, (a, yc, zc), (cut[0], yc, zc), wd, LATH_W, LATH_T, mat="wood_raw", rng=rng,
                      end1=rng.uniform(0.008, 0.03), teeth=1)
            if b - cut[1] > 0.02:
                board(km, (cut[1], yc, zc), (b, yc, zc), wd, LATH_W, LATH_T, mat="wood_raw", rng=rng,
                      end0=rng.uniform(0.008, 0.03), teeth=1)


def _place_hole(rng, existing: list, rx: tuple, rz: tuple, sx: tuple, sz: tuple, L: float, H: float,
                tries: int = 40) -> list | None:
    for _ in range(tries):
        cx = rng.uniform(*rx)
        cz = rng.uniform(*rz)
        hx = rng.uniform(*sx)
        hz = rng.uniform(*sz)
        poly = P.star(cx, cz, hx, hz, rng.randint(11, 15), rng, rough=0.28, teeth=0.35)
        bx0, bz0, bx1, bz1 = P.bounds(poly)
        if bx0 < -L / 2 + 0.05 or bx1 > L / 2 - 0.05 or bz0 < 0.05 or bz1 > H - 0.06:
            continue
        if not P.is_simple(poly):
            continue
        if any(P.min_dist(e, (cx, cz)) < max(hx, hz) + 0.06 or P.point_in(e, (cx, cz)) for e in existing):
            continue
        return poly
    return None


def _free_crack(rng, existing: list, L: float, H: float) -> list | None:
    for _ in range(30):
        start = (rng.uniform(-0.35, 0.35), rng.uniform(0.3, 2.4))
        line = P.crack_polyline(start, rng.uniform(0, math.tau), rng.uniform(0.18, 0.4), rng, step=0.05)
        lens = P.crack_lens(line, rng.uniform(0.004, 0.007))
        x0, z0, x1, z1 = P.bounds(lens)
        if x0 < -L / 2 + 0.04 or x1 > L / 2 - 0.04 or z0 < 0.05 or z1 > H - 0.05:
            continue
        if not P.is_simple(lens):
            continue
        if any(P.min_dist(e, p) < 0.02 or P.point_in(e, p) for e in existing for p in lens):
            continue
        return lens
    return None


def _crack_holes(holes: list, rng, n_cracks: int, L: float, H: float) -> list:
    out = list(holes)
    for _ in range(n_cracks):
        hi = rng.randrange(len(out))
        h = out[hi]
        edge = rng.randrange(len(h))
        others = [o for j, o in enumerate(out) if j != hi]
        out[hi] = P.add_crack_to_hole(h, edge, rng.uniform(0.14, 0.34), rng, width=rng.uniform(0.004, 0.007),
                                      avoid=others, keep_inside=(-L / 2, 0.0, L / 2, H))
    return out


def _breach_outline(rng, cx: float, half_w: float, top: float, n: int = 24) -> list:
    """Jagged arch from the floor (left foot -> over the top -> right foot): a squarish superellipse
    with low-frequency 'bites' and alternating teeth, clamped inside the piece."""
    ph = [rng.uniform(0, math.tau) for _ in range(3)]
    amp = [rng.uniform(0.04, 0.08), rng.uniform(0.03, 0.06), rng.uniform(0.02, 0.04)]
    tilt = rng.uniform(-0.14, 0.14)
    pts = []
    for i in range(n + 1):
        t = i / n
        th = math.pi * (1.0 - t)
        c, s = math.cos(th), math.sin(th)
        ex = 0.45   # superellipse exponent (< 1 = squarer)
        bx = math.copysign(abs(c) ** ex, c)
        bz = abs(s) ** ex
        wob = 1.0 + sum(a * math.sin((k + 2) * th + p) for k, (a, p) in enumerate(zip(amp, ph)))
        tooth = (rng.uniform(0.0, 0.05) if i % 2 else -rng.uniform(0.0, 0.03)) if 0 < i < n else 0.0
        x = cx + half_w * bx * (wob + tooth)
        z = top * bz * (wob + tooth * 0.6) * (1.0 + tilt * c)
        if i in (0, n):
            z = 0.0
        pts.append((max(-0.46, min(0.46, x)), max(0.0, min(WALL_H - 0.2, z))))
    # keep the feet exactly on the floor and the path free of near-duplicates
    out = [pts[0]]
    for p in pts[1:]:
        if math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 0.012:
            out.append(p)
    out[-1] = (out[-1][0], 0.0)
    return out


def _notched(path: list, L: float, H: float) -> list:
    return [(-L / 2, 0.0)] + path + [(L / 2, 0.0), (L / 2, H), (-L / 2, H)]


def build_layered(p: dict, name: str, outputs: list[str]) -> None:
    mode = p.get("mode", "damaged")
    seed = int(p.get("seed", 1))
    rng = common.rng(seed)
    L, H = 1.0, WALL_H
    km = KitMesh(name)
    rect = [(-L / 2, 0.0), (L / 2, 0.0), (L / 2, H), (-L / 2, H)]
    studs = [-0.2 + rng.uniform(-0.03, 0.03), 0.2 + rng.uniform(-0.03, 0.03)]
    debris_a: list = []   # (x, size) of debris spots in front of side A / B
    debris_b: list = []
    cols = []
    if mode == "breach":
        cx = rng.uniform(-0.04, 0.04)
        top_a = 1.7 + rng.uniform(-0.05, 0.05)
        path_a = _breach_outline(rng, cx, 0.40, top_a)
        path_b = _breach_outline(rng, cx + rng.uniform(-0.03, 0.03), 0.42 + rng.uniform(0.0, 0.04),
                                 top_a + rng.uniform(-0.12, 0.08))
        hole_a = path_a  # closed along the floor
        hole_b = path_b
        _skin(km, [_notched(path_a, L, H)], "A", L, H)
        _skin(km, [_notched(path_b, L, H)], "B", L, H)
        _caps(km, L, H)
        # Frame: plates, end studs; the two middle studs are snapped.
        _frame_members(km, L, H, [], rng)
        for sx in studs:
            km.part(rng.uniform(0.3, 0.7))
            zb = rng.uniform(0.12, 0.3)
            tilt = rng.uniform(-0.25, 0.25)
            base = Vector((sx, rng.uniform(-0.01, 0.01), PLATE_H))
            tip = base + Vector((rng.uniform(-0.03, 0.03), math.sin(tilt) * zb, math.cos(tilt) * zb))
            board(km, base, tip, (1, 0, 0), STUD_W, 2 * STUD_D, mat="wood_raw", rng=rng, end1=rng.uniform(0.05, 0.12),
                  teeth=2)
            sliver(km, tip - Vector((0, 0, 0.02)), (rng.uniform(-0.3, 0.3), rng.uniform(-0.5, 0.5), 1.0),
                   rng.uniform(0.05, 0.12), 0.012, rng, mat="wood_raw")
            # upper stub hanging from the top plate (hidden part stays inside the cavity)
            zt = min(_top_at(hole_a, sx), _top_at(hole_b, sx)) - rng.uniform(0.03, 0.18)
            km.part(rng.uniform(0.3, 0.7))
            board(km, (sx, 0.0, zt), (sx, 0.0, H - 2 * 0.04), (1, 0, 0), STUD_W, 2 * STUD_D, mat="wood_raw", rng=rng,
                  end0=rng.uniform(0.06, 0.14), teeth=2)
            sliver(km, (sx, 0.0, zt + 0.03), (rng.uniform(-0.3, 0.3), rng.uniform(-0.4, 0.4), -1.0),
                   rng.uniform(0.06, 0.14), 0.012, rng, mat="wood_raw")
        # Lath stubs along both hole edges (the lath is knocked out across the breach); the free ends
        # are bent away from side A (the blow came from there).
        for side, hole, keep in (("A", hole_a, 0.26), ("B", hole_b, 0.18)):
            sy = -1 if side == "A" else 1
            yc = sy * (HALF_T - SKIN_T - LATH_T / 2)
            for zc in _lath_rows(0.0, P.bounds(hole)[3]):
                xs = P.x_span_at(hole, zc)
                if len(xs) < 2:
                    continue
                for edge, d in ((xs[0], 1), (xs[-1], -1)):
                    if rng.random() > keep:
                        continue
                    out = rng.uniform(0.025, 0.16)
                    bend = rng.uniform(0.0, 0.5) * out
                    a = Vector((edge - d * 0.025, yc, zc))
                    b = Vector((edge + d * out, yc + bend, zc + rng.uniform(-0.25, 0.1) * out))
                    km.part(rng.uniform(0.2, 0.8))
                    if d > 0:
                        board(km, a, b, (0, 0, 1), LATH_W, LATH_T, mat="wood_raw", rng=rng, end1=0.03, teeth=0)
                    else:
                        board(km, b, a, (0, 0, 1), LATH_W, LATH_T, mat="wood_raw", rng=rng, end0=0.03, teeth=0)
        # Debris on both sides (low, walkable), a snapped stud piece and loose lath.
        for sy in (-1, 1):
            for _ in range(6 if sy > 0 else 4):
                x = cx + rng.uniform(-0.45, 0.45)
                y = sy * rng.uniform(0.12, 0.5)
                km.part(rng.uniform(0.3, 0.7))
                if rng.random() < 0.55:
                    plaster_flake(km, (x, y, 0.0), rng.uniform(0.035, 0.08), rng,
                                  finish_side=SIDE_A if sy < 0 else SIDE_B)
                else:
                    rubble(km, (x, y, 0.0), rng.uniform(0.02, 0.045), rng, mat="kit_wall_inner")
            for _ in range(2 if sy > 0 else 1):
                km.part(rng.uniform(0.2, 0.8))
                x = cx + rng.uniform(-0.35, 0.35)
                y = sy * rng.uniform(0.15, 0.45)
                a = rng.uniform(0, math.tau)
                ln = rng.uniform(0.15, 0.4)
                p0 = (x - math.cos(a) * ln / 2, y - math.sin(a) * ln / 2, LATH_T / 2 + 0.001)
                p1 = (x + math.cos(a) * ln / 2, y + math.sin(a) * ln / 2, LATH_T / 2 + 0.001)
                board(km, p0, p1, (-math.sin(a), math.cos(a), 0), LATH_W, LATH_T, mat="wood_raw", rng=rng,
                      end0=rng.uniform(0.01, 0.03), end1=rng.uniform(0.01, 0.03), teeth=1)
        km.part(rng.uniform(0.3, 0.7))
        a = rng.uniform(-0.5, 0.5)
        y = -rng.uniform(0.3, 0.45)
        p0 = Vector((cx - 0.3, y, STUD_W / 2))
        p1 = p0 + Vector((math.cos(a) * 0.55, math.sin(a) * 0.12, 0.0))
        board(km, p0, p1, (0, 0, 1), STUD_W, 2 * STUD_D * 0.9, mat="wood_raw", rng=rng,
              end0=rng.uniform(0.05, 0.1), end1=rng.uniform(0.05, 0.1), teeth=1)
        # Collision: posts left/right of the narrower skin edge, lintel above.
        # passable core = intersection of both skin holes, sampled
        zs = [0.25 + 0.05 * k for k in range(25)]
        spans = [(P.x_span_at(hole_a, z), P.x_span_at(hole_b, z)) for z in zs]
        spans = [(max(a[0], b[0]), min(a[-1], b[-1])) for a, b in spans if len(a) >= 2 and len(b) >= 2]
        xl = max(s[0] for s in spans[:20])
        xr = min(s[1] for s in spans[:20])
        zt = min(min(_top_at(hole_a, x), _top_at(hole_b, x)) for x in [xl + (xr - xl) * k / 8 for k in range(1, 8)])
        cols = [collision_box(f"{name}_col0", (-L / 2, -HALF_T, 0.0), (xl + 0.02, HALF_T, H)),
                collision_box(f"{name}_col1", (xr - 0.02, -HALF_T, 0.0), (L / 2, HALF_T, H)),
                collision_box(f"{name}_col2", (xl + 0.02, -HALF_T, zt), (xr - 0.02, HALF_T, H))]
    else:
        holes_a: list = []
        holes_b: list = []
        if mode == "damaged":
            main = _place_hole(rng, [], (-0.22, 0.22), (1.0, 1.55), (0.12, 0.17), (0.14, 0.2), L, H)
            if main is None:
                main = P.star(0.0, 1.3, 0.14, 0.17, 13, rng, rough=0.2, teeth=0.3)
            base_a = [main]
            kick = _place_hole(rng, base_a, (-0.3, 0.3), (0.18, 0.3), (0.06, 0.09), (0.05, 0.075), L, H)
            if kick:
                base_a.append(kick)
            holes_a = _crack_holes(base_a, rng, 3, L, H)
            lens = _free_crack(rng, holes_a, L, H)
            if lens:
                holes_a.append(lens)
            hb = _place_hole(rng, [], (-0.25, 0.25), (0.7, 1.9), (0.08, 0.12), (0.1, 0.13), L, H)
            if hb is None:
                hb = P.star(0.1, 1.5, 0.1, 0.11, 11, rng, rough=0.2, teeth=0.3)
            base_b = [hb]
            holes_b = _crack_holes(base_b, rng, 2, L, H)
            # lath: exposed at the main hole (a couple of strips broken), knocked through at the kick hole
            _lath_behind(km, main, "A", rng, broken_frac=0.3, missing_frac=0.12)
            if kick:
                inner = P.star(*P.centroid(kick), 0.045, 0.035, 9, rng, rough=0.3, teeth=0.3)
                _lath_behind(km, kick, "A", rng, broken_frac=0.0, missing_frac=0.0, through=inner)
            _lath_behind(km, hb, "B", rng, broken_frac=0.25, missing_frac=0.0)
            debris_a = [(P.centroid(h)[0], 0.06) for h in base_a]
            debris_b = [(P.centroid(hb)[0], 0.05)]
        else:  # worn: water damage, plaster fallen off the lath near the ceiling or the floor
            high = rng.random() < 0.6
            rz = (2.05, 2.3) if high else (0.35, 0.55)
            loss = _place_hole(rng, [], (-0.15, 0.15), rz, (0.2, 0.26), (0.15, 0.2), L, H)
            if loss is None:
                loss = P.star(0.0, sum(rz) / 2, 0.22, 0.16, 13, rng, rough=0.2, teeth=0.3)
            base_a = [loss]
            holes_a = _crack_holes(base_a, rng, 4, L, H)
            lens = _free_crack(rng, holes_a, L, H)
            if lens:
                holes_a.append(lens)
            base_b = []
            holes_b = []
            lens_b = _free_crack(rng, [], L, H)
            if lens_b:
                holes_b.append(lens_b)
            _lath_behind(km, loss, "A", rng, broken_frac=0.08, missing_frac=0.0)
            debris_a = [(P.centroid(loss)[0], 0.09)]
        _skin(km, [rect] + holes_a, "A", L, H, inner_loops=[rect] + base_a)
        _skin(km, [rect] + holes_b, "B", L, H, inner_loops=[rect] + base_b)
        _caps(km, L, H)
        _frame_members(km, L, H, studs, rng)
        for spots, sy in ((debris_a, -1), (debris_b, 1)):
            for x, s in spots:
                for _ in range(rng.randint(2, 3)):
                    km.part(rng.uniform(0.3, 0.7))
                    px = max(-0.45, min(0.45, x + rng.uniform(-0.15, 0.15)))
                    py = sy * rng.uniform(0.11, 0.3)
                    if rng.random() < 0.6:
                        plaster_flake(km, (px, py, 0.0), s * rng.uniform(0.5, 1.0), rng,
                                      finish_side=SIDE_A if sy < 0 else SIDE_B)
                    else:
                        rubble(km, (px, py, 0.0), s * rng.uniform(0.3, 0.5), rng, mat="kit_wall_inner")
        cols = [collision_box(f"{name}_col0", (-L / 2, -HALF_T, 0.0), (L / 2, HALF_T, H))]
    obj = km.build()
    bake_colors(obj, ground_z=0.0, ceiling_z=H, samples=16, distance=0.3, strength=0.85, seed=seed)
    export_glb(outputs[0], [obj] + cols)


# -------------------------------------------------------------------------------------------------
# Fracture set
# -------------------------------------------------------------------------------------------------

def build_frac(p: dict, name: str, outputs: list[str]) -> None:
    seed = int(p.get("seed", 1))
    km = KitMesh(name + "_src")
    km.part(0.0)
    km.box((-0.5, -HALF_T, 0.0), (0.5, HALF_T, WALL_H), "kit_wall",
           sides={"-y": SIDE_A, "+y": SIDE_B, "-x": SIDE_N, "+x": SIDE_N, "-z": SIDE_N, "+z": SIDE_N})
    src = km.build()
    chunks = fracture.fracture(src, int(p.get("pieces", 9)), seed, "kit_wall_inner", margin=0.003,
                               bias=(1.0, 0.0, 1.0))
    bpy.data.objects.remove(src, do_unlink=True)
    fix_chunks(chunks, "kit_wall_inner", seed=seed)
    export_glb(outputs[0], chunks)


def build(params: dict, outputs: list[str]) -> None:
    name = params.get("name", "wall")
    kind = params.get("kind", "wall")
    {"wall": build_wall, "post": build_post, "layered": build_layered, "frac": build_frac}[kind](params, name, outputs)
