"""2D polygon helpers for the POI kit (pure Python, deterministic).

Polygons are lists of (x, y) tuples (no repeated closing point). Used for wall skins with jagged
holes and cracks, broken glass shards, splintered board ends and Voronoi-style splits.
"""
from __future__ import annotations

import math
import random

Pt = tuple[float, float]


def area(poly: list[Pt]) -> float:
    """Signed area (> 0 for counter-clockwise)."""
    s = 0.0
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        s += x0 * y1 - x1 * y0
    return s * 0.5


def ccw(poly: list[Pt]) -> list[Pt]:
    return list(poly) if area(poly) >= 0 else list(reversed(poly))


def cw(poly: list[Pt]) -> list[Pt]:
    return list(poly) if area(poly) < 0 else list(reversed(poly))


def centroid(poly: list[Pt]) -> Pt:
    a = area(poly)
    if abs(a) < 1e-12:
        return (sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly))
    cx = cy = 0.0
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        c = x0 * y1 - x1 * y0
        cx += (x0 + x1) * c
        cy += (y0 + y1) * c
    return (cx / (6 * a), cy / (6 * a))


def bounds(poly: list[Pt]) -> tuple[float, float, float, float]:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def point_in(poly: list[Pt], p: Pt) -> bool:
    x, y = p
    inside = False
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            t = (y - y0) / (y1 - y0)
            if x < x0 + t * (x1 - x0):
                inside = not inside
    return inside


def _seg_intersect(a: Pt, b: Pt, c: Pt, d: Pt) -> bool:
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    o1, o2, o3, o4 = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
    return (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0)


def segment_hits(poly: list[Pt], a: Pt, b: Pt) -> bool:
    n = len(poly)
    return any(_seg_intersect(a, b, poly[i], poly[(i + 1) % n]) for i in range(n))


def is_simple(poly: list[Pt]) -> bool:
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            if _seg_intersect(a, b, poly[j], poly[(j + 1) % n]):
                return False
    return True


def min_dist(poly: list[Pt], p: Pt) -> float:
    best = 1e9
    n = len(poly)
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        dx, dy = bx - ax, by - ay
        L = dx * dx + dy * dy
        t = 0.0 if L < 1e-18 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L))
        qx, qy = ax + t * dx, ay + t * dy
        best = min(best, math.hypot(p[0] - qx, p[1] - qy))
    return best


def clip_halfplane(poly: list[Pt], nx: float, ny: float, c: float) -> list[Pt]:
    """Keeps the part with nx*x + ny*y <= c (Sutherland-Hodgman)."""
    out: list[Pt] = []
    n = len(poly)
    for i in range(n):
        p, q = poly[i], poly[(i + 1) % n]
        dp = nx * p[0] + ny * p[1] - c
        dq = nx * q[0] + ny * q[1] - c
        if dp <= 0:
            out.append(p)
        if (dp < 0 < dq) or (dq < 0 < dp):
            t = dp / (dp - dq)
            out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return out


def voronoi_cells(region: list[Pt], seeds: list[Pt], gap: float = 0.0) -> list[list[Pt]]:
    """Convex region split into Voronoi cells of `seeds` (cells shrunk by gap/2 on every cut)."""
    cells = []
    for i, s in enumerate(seeds):
        cell = list(region)
        for j, t in enumerate(seeds):
            if i == j or not cell:
                continue
            nx, ny = t[0] - s[0], t[1] - s[1]
            L = math.hypot(nx, ny)
            if L < 1e-9:
                continue
            nx, ny = nx / L, ny / L
            mx, my = (s[0] + t[0]) / 2, (s[1] + t[1]) / 2
            cell = clip_halfplane(cell, nx, ny, nx * mx + ny * my - gap / 2)
        if len(cell) >= 3 and abs(area(cell)) > 1e-6:
            cells.append(cell)
    return cells


def star(cx: float, cy: float, rx: float, ry: float, n: int, rng: random.Random, *, rough: float = 0.35,
         teeth: float = 0.0, phase: float | None = None, squash_bottom: bool = False) -> list[Pt]:
    """Jagged star-shaped (hence simple) polygon around (cx, cy). `rough` = radial noise fraction,
    `teeth` alternates inner/outer radii for sharp broken edges. Counter-clockwise."""
    ph = rng.uniform(0, math.tau) if phase is None else phase
    pts = []
    low = [rng.uniform(-1, 1) for _ in range(4)]
    for i in range(n):
        a = ph + math.tau * (i + rng.uniform(-0.3, 0.3)) / n
        # low-frequency wobble + per-vertex noise + alternating teeth
        wob = 1.0 + 0.18 * (low[0] * math.sin(a + low[1] * 3) + low[2] * math.sin(2 * a + low[3] * 3))
        r = wob * (1.0 + rough * rng.uniform(-1, 1)) * (1.0 - teeth * (i % 2) * rng.uniform(0.5, 1.0))
        x, y = math.cos(a) * rx * r, math.sin(a) * ry * r
        pts.append((cx + x, cy + y))
    return ccw(pts)


def jagged_path(p0: Pt, p1: Pt, n: int, amp: float, rng: random.Random, *, teeth: float = 0.5) -> list[Pt]:
    """Points from p0 to p1 (exclusive of both ends) displaced sideways: a broken edge."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy)
    nx, ny = -dy / L, dx / L
    pts = []
    for i in range(1, n):
        t = (i + rng.uniform(-0.3, 0.3)) / n
        off = amp * rng.uniform(-1, 1)
        if i % 2 == 0:
            off *= (1 - teeth)
        else:
            off = math.copysign(abs(off) * (0.5 + teeth), off)
        pts.append((p0[0] + dx * t + nx * off, p0[1] + dy * t + ny * off))
    return pts


def crack_polyline(start: Pt, direction: float, length: float, rng: random.Random, *, step: float = 0.05,
                   wander: float = 0.45) -> list[Pt]:
    pts = [start]
    a = direction
    travelled = 0.0
    while travelled < length - 1e-6:
        s = min(step * rng.uniform(0.6, 1.3), length - travelled)
        a += rng.uniform(-wander, wander)
        a = direction + max(-0.9, min(0.9, a - direction))
        x, y = pts[-1]
        pts.append((x + math.cos(a) * s, y + math.sin(a) * s))
        travelled += s
    return pts


def thick_polyline(line: list[Pt], w0: float, w1: float) -> tuple[list[Pt], list[Pt]]:
    """Left/right offset sides of a polyline with width tapering w0 -> w1 (tip excluded)."""
    left, right = [], []
    n = len(line)
    for k in range(n - 1):
        if k == 0:
            tx, ty = line[1][0] - line[0][0], line[1][1] - line[0][1]
        else:
            tx, ty = line[k + 1][0] - line[k - 1][0], line[k + 1][1] - line[k - 1][1]
        L = math.hypot(tx, ty) or 1.0
        nx, ny = -ty / L, tx / L
        w = (w0 + (w1 - w0) * k / max(1, n - 1)) / 2
        left.append((line[k][0] + nx * w, line[k][1] + ny * w))
        right.append((line[k][0] - nx * w, line[k][1] - ny * w))
    return left, right


def crack_lens(line: list[Pt], width: float) -> list[Pt]:
    """Closed thin crack polygon pointed at both ends (a free-standing crack)."""
    n = len(line)
    left, right = [], []
    for k in range(1, n - 1):
        tx, ty = line[k + 1][0] - line[k - 1][0], line[k + 1][1] - line[k - 1][1]
        L = math.hypot(tx, ty) or 1.0
        nx, ny = -ty / L, tx / L
        w = width / 2 * math.sin(math.pi * k / (n - 1)) ** 0.7
        left.append((line[k][0] + nx * w, line[k][1] + ny * w))
        right.append((line[k][0] - nx * w, line[k][1] - ny * w))
    return ccw([line[0]] + right + [line[-1]] + list(reversed(left)))


def add_crack_to_hole(hole: list[Pt], edge: int, length: float, rng: random.Random, *, width: float = 0.006,
                      avoid: list[list[Pt]] | None = None, keep_inside: tuple[float, float, float, float] | None = None
                      ) -> list[Pt]:
    """Inserts a tapering crack running outward from edge `edge` of a CCW hole polygon.
    The crack is truncated before it would hit the hole itself, any polygon in `avoid` or leave the
    rectangle keep_inside=(x0, y0, x1, y1) (with a 2 cm margin)."""
    hole = ccw(hole)
    n = len(hole)
    a, b = hole[edge % n], hole[(edge + 1) % n]
    ex, ey = b[0] - a[0], b[1] - a[1]
    L = math.hypot(ex, ey)
    if L < width * 2.5:
        return hole
    ex, ey = ex / L, ey / L
    m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    out_dir = math.atan2(-ex, ey)  # right normal of a CCW edge points out of the hole
    line = crack_polyline(m, out_dir, length, rng, step=0.045)
    # Truncate where the crack would intersect anything.
    others = [hole] + list(avoid or [])
    good = [line[0]]
    for k in range(1, len(line)):
        p = line[k]
        bad = False
        if keep_inside is not None:
            x0, y0, x1, y1 = keep_inside
            bad = not (x0 + 0.02 < p[0] < x1 - 0.02 and y0 + 0.02 < p[1] < y1 - 0.02)
        if not bad:
            for o in others:
                seg_a = good[-1] if k > 1 else (m[0] + math.cos(out_dir) * 0.004, m[1] + math.sin(out_dir) * 0.004)
                if point_in(o, p) or segment_hits(o, seg_a, p) or min_dist(o, p) < 0.012:
                    bad = True
                    break
        if bad:
            break
        good.append(p)
    if len(good) < 3:
        return hole
    left, right = thick_polyline(good, width, width * 0.25)
    # root points sit on the hole edge
    half = width / 2
    root_r = (m[0] - ex * half, m[1] - ey * half)
    root_l = (m[0] + ex * half, m[1] + ey * half)
    crack = [root_r] + right[1:] + [good[-1]] + list(reversed(left[1:])) + [root_l]
    new = hole[:edge + 1] + crack + hole[edge + 1:]
    if not is_simple(new):
        return hole
    return new


def ray_hit(poly: list[Pt], origin: Pt, ang: float) -> float:
    """Distance from origin along direction `ang` to the polygon boundary (first hit)."""
    dx, dy = math.cos(ang), math.sin(ang)
    best = 1e9
    n = len(poly)
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        ex, ey = bx - ax, by - ay
        den = dx * ey - dy * ex
        if abs(den) < 1e-12:
            continue
        t = ((ax - origin[0]) * ey - (ay - origin[1]) * ex) / den
        u = ((ax - origin[0]) * dy - (ay - origin[1]) * dx) / den
        if t > 1e-9 and -1e-9 <= u <= 1 + 1e-9:
            best = min(best, t)
    return best


def sector_split(outer: list[Pt], hole: list[Pt], center: Pt, angles: list[float], arc_steps: int = 3,
                 gap: float = 0.0) -> list[list[Pt]]:
    """Splits the ring between a star-shaped `hole` and a star-shaped `outer` (both around `center`)
    into pieces between consecutive `angles` (radians, ascending), each narrowed by `gap` radians on
    both sides (cracks between pieces). Returns simple CCW polygons (invalid slivers are dropped)."""
    pieces = []
    k = len(angles)

    def arc(poly, a0, a1):
        pts = []
        steps = max(1, arc_steps)
        for s in range(steps + 1):
            a = a0 + (a1 - a0) * s / steps
            r = ray_hit(poly, center, a)
            pts.append((center[0] + math.cos(a) * r, center[1] + math.sin(a) * r))
        return pts

    for i in range(k):
        a0 = angles[i] + gap
        a1 = angles[(i + 1) % k] + (math.tau if i == k - 1 else 0.0) - gap
        if a1 - a0 < 0.05:
            continue
        # include the polygon's own vertices that fall inside the sector for crisp outlines
        def verts_in(poly):
            out = []
            for p in poly:
                a = math.atan2(p[1] - center[1], p[0] - center[0])
                while a < a0:
                    a += math.tau
                while a >= a0 + math.tau:
                    a -= math.tau
                if a0 < a < a1:
                    out.append((a, p))
            out.sort()
            return [p for _, p in out]
        inner_pts = [arc(hole, a0, a0)[0]] + verts_in(hole) + [arc(hole, a1, a1)[0]]
        outer_pts = [arc(outer, a0, a0)[0]] + verts_in(outer) + [arc(outer, a1, a1)[0]]
        poly = outer_pts + list(reversed(inner_pts))
        poly = _dedupe(poly)
        if len(poly) >= 3 and abs(area(poly)) > 1e-5 and is_simple(poly):
            pieces.append(ccw(poly))
    return pieces


def _dedupe(poly: list[Pt], eps: float = 1e-6) -> list[Pt]:
    out: list[Pt] = []
    for p in poly:
        if not out or abs(p[0] - out[-1][0]) > eps or abs(p[1] - out[-1][1]) > eps:
            out.append(p)
    if len(out) > 1 and abs(out[0][0] - out[-1][0]) < eps and abs(out[0][1] - out[-1][1]) < eps:
        out.pop()
    return out


def shrink(poly: list[Pt], amount: float) -> list[Pt]:
    """Moves vertices toward the centroid (cheap inset for small gaps between shards)."""
    cx, cy = centroid(poly)
    out = []
    for x, y in poly:
        dx, dy = x - cx, y - cy
        L = math.hypot(dx, dy) or 1.0
        f = max(0.0, (L - amount) / L)
        out.append((cx + dx * f, cy + dy * f))
    return out


def x_span_at(poly: list[Pt], y: float) -> list[float]:
    """Sorted x coordinates where the horizontal line at height y crosses the polygon boundary."""
    xs = []
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            t = (y - y0) / (y1 - y0)
            xs.append(x0 + t * (x1 - x0))
    return sorted(xs)
