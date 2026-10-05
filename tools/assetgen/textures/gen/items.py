"""Item / viewmodel / player-structure surfaces (Hollowmere). Every name is prefixed item_* so it never
collides with other families. Tiling sets are periodic; "sheet" textures (labels, covers, schematics,
the salvage-roll layout) are full-object prints mapped 0..1 by the generators (image row 0 = top =
Blender v 1). No text anywhere: printed matter uses colour blocks, pictograms and illegible bars.

Material bindings live in game/data/materials/items.json (uv_scale there = 1 / tile size in metres,
since item UVs are metre-scaled)."""
from __future__ import annotations

import math

import numpy as np
from scipy import ndimage

from .. import texlib as T
from ..registry import texture

# ------------------------------------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------------------------------------


def _uv(size: int):
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    return (xx + 0.5) / size, (yy + 0.5) / size


def _rgb(h: str) -> np.ndarray:
    return T.hex_rgb(h)[None, None, :]


def _fill(size: int, h: str) -> np.ndarray:
    return np.ones((size, size, 3), np.float32) * _rgb(h)


def _rot45(field_fn, size: int) -> np.ndarray:
    """Samples a periodic field in a 45-degree rotated frame (still periodic): f((x+y), (y-x))."""
    f = field_fn
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    u = (xx + yy) % size
    v = (yy - xx) % size
    return ndimage.map_coordinates(f, [v, u], order=1, mode="grid-wrap")


def _seg(cov: np.ndarray, x0, y0, x1, y1, w: float, val: float = 1.0, soft: float = 0.75, wrap: bool = False) -> None:
    """Anti-aliased line segment into a coverage buffer (max-composited)."""
    h, wd = cov.shape
    pad = w * 0.5 + soft + 1.0
    xa = int(math.floor(min(x0, x1) - pad))
    xb = int(math.ceil(max(x0, x1) + pad))
    ya = int(math.floor(min(y0, y1) - pad))
    yb = int(math.ceil(max(y0, y1) + pad))
    if not wrap:
        xa, xb, ya, yb = max(0, xa), min(wd, xb), max(0, ya), min(h, yb)
        if xa >= xb or ya >= yb:
            return
    yy, xx = np.mgrid[ya:yb, xa:xb].astype(np.float32)
    yy += 0.5
    xx += 0.5
    dx, dy = x1 - x0, y1 - y0
    l2 = dx * dx + dy * dy
    if l2 < 1e-9:
        t = np.zeros_like(xx)
    else:
        t = np.clip(((xx - x0) * dx + (yy - y0) * dy) / l2, 0.0, 1.0)
    d = np.hypot(xx - (x0 + t * dx), yy - (y0 + t * dy))
    a = np.clip((w * 0.5 - d) / soft + 0.5, 0.0, 1.0) * val
    if wrap:
        iy = np.arange(ya, yb) % h
        ix = np.arange(xa, xb) % wd
        sub = cov[np.ix_(iy, ix)]
        cov[np.ix_(iy, ix)] = np.maximum(sub, a)
    else:
        np.maximum(cov[ya:yb, xa:xb], a, out=cov[ya:yb, xa:xb])


def _poly(cov, pts, w, val=1.0, closed=False, wrap=False, soft=0.75):
    n = len(pts)
    for i in range(n - (0 if closed else 1)):
        a, b = pts[i], pts[(i + 1) % n]
        _seg(cov, a[0], a[1], b[0], b[1], w, val, soft=soft, wrap=wrap)


def _hand(cov, p0, p1, w, r: np.random.Generator, wobble=1.2, val=0.85, step=10.0, overshoot=3.0):
    """Hand-drawn pencil line: wobbly, pressure-varying, slight overshoot."""
    p0 = np.array(p0, np.float32)
    p1 = np.array(p1, np.float32)
    d = p1 - p0
    L = float(np.hypot(*d))
    if L < 1e-3:
        return
    dirv = d / L
    nrm = np.array([-dirv[1], dirv[0]])
    p0 = p0 - dirv * r.uniform(0, overshoot)
    p1 = p1 + dirv * r.uniform(0, overshoot)
    L = float(np.hypot(*(p1 - p0)))
    n = max(2, int(L / step) + 1)
    ph1, ph2 = r.uniform(0, 6.28, 2)
    f1, f2 = r.uniform(0.6, 1.6), r.uniform(2.0, 4.0)
    pts = []
    for i in range(n):
        t = i / (n - 1)
        off = (math.sin(t * math.pi * f1 + ph1) * 0.7 + math.sin(t * math.pi * f2 + ph2) * 0.3) * wobble
        pts.append(p0 + (p1 - p0) * t + nrm * off)
    pr = val * r.uniform(0.75, 1.0)
    for i in range(n - 1):
        t = i / max(1, n - 2)
        pv = pr * (0.75 + 0.25 * math.sin(t * math.pi))
        _seg(cov, pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], w, pv)


def _circle(cov, cx, cy, rad, w, val=1.0, n=None, r=None, wobble=0.0, arc=(0.0, 1.0)):
    n = n or max(12, int(rad * 0.8))
    pts = []
    ph = r.uniform(0, 6.28) if r is not None else 0.0
    for i in range(n + 1):
        t = arc[0] + (arc[1] - arc[0]) * i / n
        a = t * 2 * math.pi
        rr = rad + (math.sin(a * 3 + ph) * wobble if wobble else 0.0)
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    _poly(cov, pts, w, val)


def _rect_fill(img, x0, y0, x1, y1, col, alpha=1.0):
    h, w = img.shape[:2]
    xa, xb = int(max(0, round(x0))), int(min(w, round(x1)))
    ya, yb = int(max(0, round(y0))), int(min(h, round(y1)))
    if xa >= xb or ya >= yb:
        return
    c = T.hex_rgb(col) if isinstance(col, str) else np.asarray(col, np.float32)
    img[ya:yb, xa:xb] = img[ya:yb, xa:xb] * (1 - alpha) + c * alpha


def _mask_rect(size_h, size_w, x0, y0, x1, y1, soft=1.0):
    yy, xx = np.mgrid[0:size_h, 0:size_w].astype(np.float32) + 0.5
    m = np.minimum(np.minimum(xx - x0, x1 - xx), np.minimum(yy - y0, y1 - yy))
    return np.clip(m / soft + 0.5, 0, 1)


def _ellipse_mask(h, w, cx, cy, rx, ry, soft=1.5):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    d = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
    return np.clip((1.0 - d) * min(rx, ry) / soft + 0.5, 0, 1)


def _bars(img, height_map, x0, y0, x1, y1, line_h, r, col="#3a3a38", gap=0.55, density=1.0, alpha=0.85):
    """Illegible 'text': rows of word-length bars (greeked copy)."""
    y = y0
    while y + line_h * gap <= y1:
        x = x0 + r.uniform(0, line_h * 0.5)
        end = x1 - r.uniform(0, (x1 - x0) * 0.25)
        while x < end:
            wl = r.uniform(line_h * 0.8, line_h * 3.5) * density
            if x + wl > end:
                wl = end - x
            if wl > line_h * 0.4:
                _rect_fill(img, x, y, x + wl, y + line_h * gap, col, alpha)
                if height_map is not None:
                    height_map[int(y):int(y + line_h * gap), int(x):int(x + wl)] -= 0.02
            x += wl + line_h * r.uniform(0.35, 0.6)
        y += line_h


def _barcode(img, x0, y0, x1, y1, r, bg="#f2efe6"):
    _rect_fill(img, x0, y0, x1, y1, bg)
    x = x0 + (x1 - x0) * 0.08
    while x < x1 - (x1 - x0) * 0.08:
        bw = r.choice([1.0, 1.0, 2.0, 3.0]) * (x1 - x0) / 90.0
        _rect_fill(img, x, y0 + (y1 - y0) * 0.12, x + bw, y1 - (y1 - y0) * 0.12, "#1c1c1c")
        x += bw + r.choice([1.0, 2.0, 2.0, 3.0]) * (x1 - x0) / 90.0


def _scribble(cov, x0, x1, y, h, r, w=1.6, val=0.85):
    """Cursive-looking but illegible handwriting along a baseline."""
    x = x0
    while x < x1:
        word = r.uniform(h * 1.5, h * 5.0)
        xe = min(x1, x + word)
        n = max(6, int((xe - x) / 1.5))
        ph = r.uniform(0, 6.28)
        fr = r.uniform(0.9, 1.4)
        pts = []
        for i in range(n):
            t = i / (n - 1)
            xx = x + (xe - x) * t
            loop = math.sin(t * (xe - x) / h * math.pi * fr + ph)
            asc = 1.0 + 0.9 * max(0.0, math.sin(t * 7.3 + ph * 2)) ** 6
            yy = y - (0.5 + 0.5 * loop) * h * 0.55 * asc + math.cos(t * (xe - x) / h * math.pi * fr * 2 + ph) * h * 0.08
            xx += math.cos(t * (xe - x) / h * math.pi * fr + ph) * h * 0.18
            pts.append((xx, yy))
        _poly(cov, pts, w, val * r.uniform(0.8, 1.0))
        x = xe + r.uniform(h * 0.5, h * 1.0)


def _stains(size, seed, count, rmin, rmax, ring=False):
    """Soft blotches (0..1) — water marks, grease, dirt. ring=True gives coffee-ring edges."""
    r = T.rng(seed)
    out = np.zeros((size, size), np.float32)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    warp = T.spectral(size, 2.0, seed + 5)
    for _ in range(count):
        cx, cy = r.uniform(0, size, 2)
        rad = r.uniform(rmin, rmax) * size
        dx = (xx - cx + size / 2) % size - size / 2
        dy = (yy - cy + size / 2) % size - size / 2
        d = np.sqrt(dx * dx + dy * dy) / rad + (warp - 0.5) * 0.5
        if ring:
            out = np.maximum(out, np.exp(-((d - 1.0) / 0.06) ** 2) * 0.8 + np.clip(1 - d, 0, 1) * 0.25)
        else:
            out = np.maximum(out, np.clip(1.0 - d, 0, 1) ** 0.7)
    return out


def _weave(size, n, seed, *, slub=0.25):
    """Plain weave height (n threads per tile each way). Returns (height, warp_on_top mask)."""
    r = T.rng(seed)
    c = (np.arange(size, dtype=np.float32) + 0.5) * n / size
    ci = np.floor(c).astype(int)
    cf = c - ci
    prof = np.sin(np.pi * cf) ** 0.7
    tw = 0.8 + 0.4 * r.random(n).astype(np.float32)
    tf = 0.8 + 0.4 * r.random(n).astype(np.float32)
    slub_w = T.spectral(size, 1.4, seed + 1, anisotropy=(8.0, 1.0)) if slub > 0 else np.full((size, size), 0.5, np.float32)
    slub_f = T.spectral(size, 1.4, seed + 2, anisotropy=(1.0, 8.0)) if slub > 0 else np.full((size, size), 0.5, np.float32)
    warp = (prof * tw[ci % n])[None, :] * (1 + (slub_w - 0.5) * slub)
    weft = (prof * tf[ci % n])[:, None] * (1 + (slub_f - 0.5) * slub)
    over = ((ci[None, :] + ci[:, None]) % 2) == 0
    arch_y = np.sin(np.pi * cf)[:, None]
    arch_x = np.sin(np.pi * cf)[None, :]
    hw = warp * np.where(over, 0.65 + 0.35 * arch_y, 0.3 * (1 - arch_y))
    hf = weft * np.where(~over, 0.65 + 0.35 * arch_x, 0.3 * (1 - arch_x))
    return np.maximum(hw, hf).astype(np.float32), over


def _scratches(size, seed, count, lmin, lmax, w=1.0, angle=None, spread=math.pi):
    r = T.rng(seed)
    cov = np.zeros((size, size), np.float32)
    for _ in range(count):
        x, y = r.uniform(0, size, 2)
        a = r.uniform(0, spread) if angle is None else angle + r.uniform(-spread, spread)
        L = r.uniform(lmin, lmax) * size
        _seg(cov, x, y, x + math.cos(a) * L, y + math.sin(a) * L, w * r.uniform(0.6, 1.3), r.uniform(0.3, 1.0), wrap=True)
    return cov


def _save(out, albedo, height, rough, metal=0.0, ns=4.0, ao=1.0, alpha=None):
    T.save_pbr_set(out, np.clip(albedo, 0, 1).astype(np.float32), T.normalize(height), np.clip(rough, 0.02, 1.0).astype(np.float32),
                   metal=metal if not isinstance(metal, np.ndarray) else np.clip(metal, 0, 1), normal_strength=ns,
                   ao_strength=ao, alpha=alpha)


def _grime(size, seed, amt=0.15):
    g = T.spectral(size, 1.8, seed)
    return 1.0 - amt * T.levels(g, 0.4, 1.0)


# ------------------------------------------------------------------------------------------------
# Wood, bark, charcoal, ash
# ------------------------------------------------------------------------------------------------

def _worley_aniso(size, points, seed, stretch=3):
    """Periodic Worley with cells elongated `stretch` times along V (rows). Returns F1, F2, id."""
    from scipy.spatial import cKDTree
    r = T.rng(seed)
    W, H = float(size), float(size) / stretch
    pts = r.random((points, 2)) * np.array([W, H])
    tiled = np.concatenate([pts + np.array([dx * W, dy * H]) for dx in (-1, 0, 1) for dy in (-1, 0, 1)])
    ids = np.tile(np.arange(points), 9)
    tree = cKDTree(tiled)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    q = np.stack([xx.ravel() + 0.5, (yy.ravel() + 0.5) / stretch], -1)
    d, idx = tree.query(q, k=2)
    return (d[:, 0].reshape(size, size).astype(np.float32), d[:, 1].reshape(size, size).astype(np.float32),
            ids[idx[:, 0]].reshape(size, size))


@texture("item_bark", size=1024, seed=301)
def item_bark(size, seed, out):
    """Grey-brown conifer bark: vertically elongated scaly plates split by deep dark fissures,
    flaky plate surfaces, sparse lichen (tile 0.6 m; V runs along the trunk)."""
    f1, f2, cid = _worley_aniso(size, 70, seed, stretch=4)
    warp = T.spectral(size, 2.0, seed + 9) - 0.5
    gap = (f2 - f1) + warp * 6.0
    fiss = T.smoothstep(1.0, 9.0, gap)                    # 0 in fissures
    rnd = (np.sin(cid * 12.9898) * 43758.5453) % 1.0
    rnd2 = (np.sin(cid * 78.233) * 12345.678) % 1.0
    yy = np.tile((np.arange(size)[:, None] + 0.5) / size, (1, size))
    layers = 0.5 + 0.5 * np.sin(2 * math.pi * (yy * 18 + rnd * 3.0) + T.spectral(size, 1.5, seed + 2) * 4)
    flakes = T.spectral(size, 1.1, seed + 4, anisotropy=(2.0, 1.0))
    fine = T.spectral(size, 0.8, seed + 3)
    plate_h = 0.55 + 0.45 * rnd2
    height = T.normalize(fiss * plate_h * (0.8 + 0.06 * layers + 0.14 * flakes) + 0.08 * fine)
    col = T.gradient(T.normalize(0.6 * flakes + 0.32 * fine + 0.08 * layers),
                     [(0.0, "#4a3c31"), (0.45, "#66574a"), (0.8, "#7d6e60"), (1.0, "#93857a")])
    col *= (0.85 + 0.3 * rnd)[..., None]
    col = T.mix(col, _fill(size, "#1b1410"), (1 - fiss) * 0.9)
    inner = (1 - T.smoothstep(0.0, 0.35, fiss)) * T.smoothstep(0.0, 0.05, fiss)
    col = T.mix(col, _fill(size, "#6a3a22"), inner * 0.5)
    lich = T.levels(T.spectral(size, 1.3, seed + 5), 0.8, 0.9) * fiss
    col = T.mix(col, _fill(size, "#8e9479"), lich * 0.45)
    rough = 0.88 + 0.1 * (1 - fiss)
    _save(out, col, height, rough, ns=7.0, ao=2.0)


@texture("item_wood_end", size=1024, seed=302)
def item_wood_end(size, seed, out):
    """Sawn end grain, rings centred (UV disc radius 0.46), pith, radial checks, saw kerf marks."""
    u, v = _uv(size)
    x, y = (u - 0.5) * 2, (v - 0.5) * 2
    warp = T.spectral(size, 2.2, seed) - 0.5
    rad = np.sqrt(x * x + y * y) / 0.92 + warp * 0.06
    ang = np.arctan2(y, x)
    rings_n = 26
    rr = rad * rings_n + (T.spectral(size, 2.6, seed + 1) - 0.5) * 1.2
    ringf = rr - np.floor(rr)
    late = T.smoothstep(0.62, 0.9, ringf) * (1 - T.smoothstep(0.92, 1.0, ringf))
    col = T.gradient(np.clip(rad, 0, 1), [(0.0, "#a8865a"), (0.5, "#c9a877"), (0.85, "#d8bb8a"), (0.96, "#b99a6c"), (1.0, "#3b2a1c")])
    col = T.mix(col, col * _rgb("#a97f50") / _rgb("#d8bb8a") * 0.85, late * 0.75)
    pith = np.clip(1 - rad / 0.03, 0, 1)
    col = T.mix(col, _fill(size, "#5a3d22"), pith)
    # radial checks
    r = T.rng(seed + 2)
    checks = np.zeros((size, size), np.float32)
    for _ in range(5):
        a0 = r.uniform(-math.pi, math.pi)
        da = np.abs(((ang - a0 + math.pi) % (2 * math.pi)) - math.pi)
        width = 0.004 + 0.02 * rad
        reach = r.uniform(0.35, 0.95)
        checks = np.maximum(checks, np.clip(1 - da / np.maximum(width, 1e-4), 0, 1) * T.smoothstep(reach, reach * 0.4, rad) * T.smoothstep(0.05, 0.2, rad))
    col *= (1 - 0.7 * checks)[..., None]
    saw = 0.5 + 0.5 * np.sin((x * 0.9 + y * 0.2) * 260 + (T.spectral(size, 2.0, seed + 3) - 0.5) * 8)
    col *= (0.93 + 0.07 * saw)[..., None]
    grime = T.levels(T.spectral(size, 1.7, seed + 4), 0.5, 1.0)
    col *= (1 - 0.18 * grime)[..., None]
    height = T.normalize(0.4 * late + 0.25 * saw - 1.2 * checks + 0.2 * T.spectral(size, 0.8, seed + 5))
    rough = 0.82 + 0.1 * checks
    _save(out, col, height, rough, ns=3.0)


@texture("item_wood_raw", size=1024, seed=303)
def item_wood_raw(size, seed, out):
    """Freshly split / peeled softwood, grain along V (tile 0.5 m)."""
    grain = T.spectral(size, 1.8, seed, anisotropy=(14.0, 1.0))
    fib = T.spectral(size, 0.6, seed + 1, anisotropy=(20.0, 1.0))
    streak = T.spectral(size, 2.0, seed + 2, anisotropy=(6.0, 1.0))
    lines = 0.5 + 0.5 * np.sin((np.arange(size)[None, :] / size) * 2 * math.pi * 38 + (grain - 0.5) * 4)
    col = T.gradient(T.normalize(0.5 * grain + 0.3 * streak + 0.2 * fib), [(0.0, "#a07a50"), (0.5, "#c19a6a"), (1.0, "#d8b585")])
    col *= (0.88 + 0.12 * lines)[..., None]
    dirt = _grime(size, seed + 3, 0.18)
    col *= dirt[..., None]
    height = T.normalize(0.5 * fib + 0.3 * lines + 0.2 * grain)
    rough = 0.78 + 0.12 * fib
    _save(out, col, height, rough, ns=3.0)


@texture("item_wood_handle", size=512, seed=304)
def item_wood_handle(size, seed, out):
    """Varnished hickory tool handle, straight grain along V, worn and grimy (tile 0.3 m)."""
    grain = T.spectral(size, 1.8, seed, anisotropy=(16.0, 1.0))
    lines = 0.5 + 0.5 * np.sin(np.tile((np.arange(size)[None, :] / size) * 2 * math.pi * 24, (size, 1)) + (grain - 0.5) * 4)
    col = T.gradient(T.normalize(0.6 * grain + 0.4 * lines), [(0.0, "#6e4426"), (0.55, "#9c6a3c"), (1.0, "#c08c55")])
    grime = T.levels(T.spectral(size, 1.6, seed + 1), 0.45, 1.0)
    col *= (1 - 0.3 * grime)[..., None]
    sc = _scratches(size, seed + 2, 40, 0.02, 0.1, 1.0, angle=math.pi / 2, spread=0.3)
    col = T.mix(col, col * 1.25, sc * 0.5)
    height = T.normalize(0.6 * lines + 0.4 * grain - 0.3 * sc)
    rough = 0.42 + 0.25 * grime + 0.1 * sc
    _save(out, col, height, rough, ns=1.5)


@texture("item_wood_plank", size=1024, seed=305)
def item_wood_plank(size, seed, out):
    """Rough-sawn, weathered softwood board: grain along U, circular-saw arcs, grey weathering (tile 1 m)."""
    grain = T.spectral(size, 1.8, seed, anisotropy=(1.0, 14.0))
    fib = T.spectral(size, 0.9, seed + 1, anisotropy=(1.0, 20.0))
    yy = np.tile((np.arange(size)[:, None] / size), (1, size))
    lines = 0.5 + 0.5 * np.sin(yy * 2 * math.pi * 30 + (grain - 0.5) * 5)
    late = T.smoothstep(0.7, 0.95, lines)
    u, v = _uv(size)
    # circular-saw arcs cross the grain (periodic: straight lines bent by a periodic sag)
    saw = 0.5 + 0.5 * np.sin(2 * math.pi * (36 * u + 0.9 * np.sin(2 * math.pi * v)) + (fib - 0.5) * 3)
    col = T.gradient(T.normalize(0.5 * grain + 0.5 * fib), [(0.0, "#6b5440"), (0.5, "#8c7055"), (1.0, "#a7896a")])
    col = T.mix(col, col * 0.72, late * 0.8)
    weather = T.levels(T.spectral(size, 1.9, seed + 2), 0.35, 0.9)
    col = T.mix(col, _fill(size, "#7d776e"), weather * 0.55)
    col *= (0.94 + 0.06 * saw)[..., None]
    stain = _stains(size, seed + 3, 6, 0.04, 0.12)
    col *= (1 - 0.2 * stain)[..., None]
    height = T.normalize(0.4 * fib + 0.3 * late + 0.2 * saw + 0.1 * grain)
    rough = 0.86 + 0.08 * fib
    _save(out, col, height, rough, ns=4.0)


@texture("item_plywood", size=512, seed=306)
def item_plywood(size, seed, out):
    """Rotary-cut plywood face veneer (tile 0.6 m) with pencil marks and grime."""
    w = T.spectral(size, 2.4, seed)
    yy = np.tile((np.arange(size)[:, None] / size), (1, size))
    fig = 0.5 + 0.5 * np.sin(yy * 2 * math.pi * 7 + (w - 0.5) * 18)
    fine = T.spectral(size, 1.0, seed + 1, anisotropy=(1.0, 10.0))
    col = T.gradient(T.normalize(0.65 * fig + 0.35 * fine), [(0.0, "#a6835a"), (0.6, "#c4a275"), (1.0, "#d6b88c")])
    r = T.rng(seed + 2)
    # football patches
    for _ in range(3):
        cx, cy = r.uniform(0.1, 0.9, 2) * size
        m = _ellipse_mask(size, size, cx, cy, size * 0.04, size * 0.016, 2.0)
        col = T.mix(col, _fill(size, "#c9ab7c"), m * 0.9)
    pen = np.zeros((size, size), np.float32)
    for _ in range(5):
        x0, y0 = r.uniform(0.05, 0.95, 2) * size
        _hand(pen, (x0, y0), (x0 + r.uniform(-120, 120), y0 + r.uniform(-30, 30)), 1.4, r, val=0.6)
    col *= (1 - 0.55 * pen)[..., None]
    col *= _grime(size, seed + 3, 0.2)[..., None]
    height = T.normalize(0.5 * fine + 0.5 * fig)
    rough = 0.82 - 0.2 * pen
    _save(out, col, height, rough, ns=2.0)


@texture("item_plywood_edge", size=512, seed=307)
def item_plywood_edge(size, seed, out):
    """Plies seen on a plywood edge: horizontal bands (5 plies over 1 tile in V), along-U fibres."""
    v = np.tile((np.arange(size)[:, None] + 0.5) / size, (1, size))
    ply = np.floor(v * 5).astype(int)
    endgrain = (ply % 2 == 1)
    fib = T.spectral(size, 1.0, seed, anisotropy=(1.0, 10.0))
    dots = T.spectral(size, 0.6, seed + 1)
    col = np.where(endgrain[..., None], T.gradient(dots, [(0, "#8a6a44"), (1, "#a8865c")]), T.gradient(fib, [(0, "#b39066"), (1, "#d2b080")]))
    glue = np.abs(((v * 5) % 1.0) - 0.0) < 0.03
    col = np.where(glue[..., None], _fill(size, "#5a4630"), col)
    height = T.normalize(np.where(endgrain, dots * 0.6, fib) - glue * 0.5)
    _save(out, col, height, np.full((size, size), 0.88, np.float32), ns=2.0)


@texture("item_wood_charred", size=512, seed=308)
def item_wood_charred(size, seed, out):
    """Charcoal / charred wood: alligator-cracked black blocks with grey ash in the cracks."""
    f1, f2, cid = T.worley(size, 110, seed, jitter=0.85)
    crack = 1 - T.smoothstep(0.0, 5.0, f2 - f1)
    blocks = T.spectral(size, 1.3, seed + 1)
    col = T.gradient(blocks, [(0.0, "#0d0c0b"), (0.7, "#1b1917"), (1.0, "#2b2622")])
    tint = ((np.sin(cid * 12.9898) * 43758.5453) % 1.0)[..., None]
    col *= 0.85 + 0.3 * tint
    ash = T.levels(T.spectral(size, 1.6, seed + 2), 0.55, 0.9)
    col = T.mix(col, _fill(size, "#6a6560"), np.clip(crack * 0.7 + ash * 0.35, 0, 1))
    brown = T.levels(T.spectral(size, 2.2, seed + 3), 0.75, 0.95)
    col = T.mix(col, _fill(size, "#3a2516"), brown * 0.6)
    height = T.normalize(blocks * 0.5 + (1 - crack) * 1.0)
    rough = 0.75 + 0.2 * crack
    _save(out, col, height, rough, ns=5.0, ao=1.5)


@texture("item_ash", size=512, seed=309)
def item_ash(size, seed, out):
    """Fire-pit ash bed with charcoal crumbs (tile 0.5 m)."""
    soft = T.spectral(size, 2.0, seed)
    fine = T.spectral(size, 0.7, seed + 1)
    f1, f2, cid = T.worley(size, 260, seed + 2)
    crumbs = (((np.sin(cid * 78.233) * 43758.5453) % 1.0) > 0.72) & (f1 < 3.5)
    col = T.gradient(T.normalize(0.6 * soft + 0.4 * fine), [(0.0, "#2e2c2a"), (0.5, "#575450"), (1.0, "#7e7a74")])
    col = np.where(crumbs[..., None], _fill(size, "#141210"), col)
    ember = T.levels(T.spectral(size, 1.9, seed + 3), 0.85, 0.97)
    col = T.mix(col, _fill(size, "#3b1e10"), ember * 0.6)
    height = T.normalize(0.6 * soft + 0.25 * fine + 0.3 * crumbs)
    _save(out, col, height, np.full((size, size), 0.96, np.float32), ns=2.5)


# ------------------------------------------------------------------------------------------------
# Stone, bone, organics
# ------------------------------------------------------------------------------------------------

@texture("item_knapped_stone", size=1024, seed=310)
def item_knapped_stone(size, seed, out):
    """Flint / chert: waxy dark grey-brown with mottling, faint banding and conchoidal ripple."""
    mott = T.spectral(size, 2.2, seed)
    band = 0.5 + 0.5 * np.sin(np.tile(np.arange(size)[:, None] / size * 2 * math.pi * 5, (1, size)) + (T.spectral(size, 2.4, seed + 1) - 0.5) * 14)
    speck = T.spectral(size, 0.3, seed + 2)
    col = T.gradient(T.normalize(0.6 * mott + 0.25 * band + 0.15 * T.spectral(size, 1.2, seed + 3)),
                     [(0.0, "#2c2825"), (0.45, "#423b35"), (0.75, "#594d42"), (1.0, "#726352")])
    col = T.mix(col, _fill(size, "#a59a8a"), (speck > 0.86).astype(np.float32) * 0.5)
    r = T.rng(seed + 4)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    rip = np.zeros((size, size), np.float32)
    for _ in range(9):
        cx, cy = r.uniform(0, size, 2)
        dx = (xx - cx + size / 2) % size - size / 2
        dy = (yy - cy + size / 2) % size - size / 2
        d = np.sqrt(dx * dx + dy * dy)
        reach = r.uniform(0.15, 0.35) * size
        rip += np.sin(d / r.uniform(5.0, 9.0)) * np.clip(1 - d / reach, 0, 1) ** 2
    height = T.normalize(0.55 * rip + 0.3 * mott + 0.15 * speck)
    rough = 0.36 + 0.14 * T.normalize(mott) + 0.1 * (speck > 0.86)
    _save(out, col, height, rough, ns=1.6)


@texture("item_stone_cortex", size=512, seed=311)
def item_stone_cortex(size, seed, out):
    """Chalky cortex rind of a flint nodule: pale, pitted, rough."""
    pits = T.spectral(size, 0.8, seed)
    lump = T.spectral(size, 2.0, seed + 1)
    col = T.gradient(T.normalize(0.5 * lump + 0.5 * pits), [(0.0, "#9a8d77"), (0.5, "#c7bba2"), (1.0, "#ddd3bd")])
    col *= _grime(size, seed + 2, 0.25)[..., None]
    height = T.normalize(0.6 * lump + 0.4 * pits)
    _save(out, col, height, np.full((size, size), 0.95, np.float32), ns=3.0)


@texture("item_bone", size=512, seed=312)
def item_bone(size, seed, out):
    """Weathered bone: ivory with longitudinal micro-cracks (along V), pores and earthy stains."""
    cracks = 1 - np.abs(2 * T.spectral(size, 1.2, seed, anisotropy=(10.0, 1.0)) - 1)
    cr = T.smoothstep(0.965, 1.0, cracks) * T.levels(T.spectral(size, 1.6, seed + 7), 0.4, 0.8)
    pores = T.spectral(size, 0.5, seed + 1)
    stain = T.levels(T.spectral(size, 2.0, seed + 2), 0.45, 1.0)
    col = T.gradient(T.normalize(T.spectral(size, 1.8, seed + 3)), [(0.0, "#b9ab8c"), (0.6, "#d6caa9"), (1.0, "#e5dcc2")])
    col = T.mix(col, _fill(size, "#8a6e48"), stain * 0.45)
    col *= (1 - 0.3 * cr)[..., None]
    col *= (0.94 + 0.06 * pores)[..., None]
    height = T.normalize(0.5 * pores - 0.8 * cr + 0.3 * T.spectral(size, 1.6, seed + 4))
    rough = 0.6 + 0.2 * stain
    _save(out, col, height, rough, ns=2.0)


@texture("item_berry", size=512, seed=313)
def item_berry(size, seed, out):
    """Huckleberry skin: deep blue-purple with a dusty waxy bloom."""
    bloom = T.levels(T.spectral(size, 1.2, seed), 0.35, 0.9)
    col = T.gradient(T.normalize(T.spectral(size, 2.0, seed + 1)), [(0.0, "#1a0d24"), (0.6, "#2c1838"), (1.0, "#3d2246")])
    col = T.mix(col, _fill(size, "#6a6584"), bloom * 0.45)
    height = T.normalize(T.spectral(size, 1.0, seed + 2))
    rough = 0.35 + 0.4 * bloom
    _save(out, col, height, rough, ns=0.8)


@texture("item_mushroom_top", size=512, seed=314)
def item_mushroom_top(size, seed, out):
    """Bracket-fungus cap: concentric growth zones along U (tile 0.12 m), velvety."""
    u = np.tile((np.arange(size)[None, :] + 0.5) / size, (size, 1))
    w = T.spectral(size, 2.2, seed) - 0.5
    z = (u * 5 + w * 0.6) % 1.0
    zone = np.floor((u * 5 + w * 0.6)).astype(int) % 4
    pal = np.stack([T.hex_rgb(c) for c in ("#6e4628", "#86592f", "#a3784a", "#5c3b22")])
    col = pal[zone]
    edge = T.smoothstep(0.85, 1.0, z) + (1 - T.smoothstep(0.0, 0.08, z))
    col = ndimage.gaussian_filter(col, (3, 3, 0), mode="wrap")
    col *= (1 - 0.18 * np.clip(edge, 0, 1))[..., None]
    vel = T.spectral(size, 0.5, seed + 1)
    col *= (0.9 + 0.12 * vel)[..., None]
    margin = T.smoothstep(0.86, 0.95, u + w * 0.05)
    col = T.mix(col, _fill(size, "#c9b38a"), margin * 0.85)
    height = T.normalize(0.5 * (1 - np.clip(edge, 0, 1)) + 0.5 * vel)
    _save(out, col, height, np.full((size, size), 0.86, np.float32), ns=2.0)


@texture("item_mushroom_pore", size=512, seed=315)
def item_mushroom_pore(size, seed, out):
    """Pore surface under a bracket fungus: cream with tiny dark pores."""
    f1, f2, _ = T.worley(size, 2400, seed, jitter=0.7)
    pore = 1 - T.smoothstep(0.0, 2.2, f1)
    col = T.gradient(T.normalize(T.spectral(size, 2.0, seed + 1)), [(0.0, "#b39a72"), (1.0, "#dcc9a2")])
    col *= (1 - 0.45 * pore)[..., None]
    height = T.normalize(1 - pore)
    _save(out, col, height, np.full((size, size), 0.9, np.float32), ns=2.0)


@texture("item_mycelium", size=512, seed=316)
def item_mycelium(size, seed, out):
    """Bloom mycelium: pale cottony filaments with a faint violet cast."""
    r = T.rng(seed)
    cov = np.zeros((size, size), np.float32)
    for _ in range(420):
        x, y = r.uniform(0, size, 2)
        a = r.uniform(0, math.tau)
        pts = []
        for i in range(10):
            a += r.uniform(-0.5, 0.5)
            x += math.cos(a) * 9
            y += math.sin(a) * 9
            pts.append((x, y))
        _poly(cov, pts, r.uniform(0.6, 1.6), r.uniform(0.4, 1.0), wrap=True)
    base = T.spectral(size, 1.6, seed + 1)
    col = T.gradient(base, [(0.0, "#a69aa6"), (1.0, "#cfc4c9")])
    col = T.mix(col, _fill(size, "#f1ece6"), cov)
    height = T.normalize(0.6 * cov + 0.4 * base)
    _save(out, col, height, 0.82 - 0.1 * cov, ns=2.0)


@texture("item_stew", size=512, seed=317)
def item_stew(size, seed, out):
    """Canned stew surface: glossy brown gravy with beef, carrot and potato chunks."""
    f1, f2, cid = T.worley(size, 70, seed, jitter=0.9)
    rnd = (np.sin(cid * 12.9898) * 43758.5453) % 1.0
    chunk = T.smoothstep(14.0, 4.0, f1) * (rnd > 0.25)
    kind = np.where(rnd > 0.75, 2, np.where(rnd > 0.5, 1, 0))
    pal = np.stack([T.hex_rgb("#4a2716"), T.hex_rgb("#b8641e"), T.hex_rgb("#c8ae7a")])
    gravy = T.gradient(T.spectral(size, 1.8, seed + 1), [(0.0, "#3a1d0e"), (1.0, "#5e3218")])
    col = T.mix(gravy, pal[kind], chunk)
    fat = T.levels(T.spectral(size, 0.9, seed + 2), 0.8, 0.95)
    col = T.mix(col, _fill(size, "#c99a55"), fat * 0.5 * (1 - chunk))
    height = T.normalize(chunk * (0.6 + 0.4 * T.spectral(size, 1.0, seed + 3)))
    rough = 0.22 + 0.45 * chunk
    _save(out, col, height, rough, ns=3.0)


# ------------------------------------------------------------------------------------------------
# Fibre, fabric, cordage
# ------------------------------------------------------------------------------------------------

@texture("item_cordage", size=512, seed=320)
def item_cordage(size, seed, out):
    """Hand-twisted 2-ply plant cord. U = once around the cord, V = along it (cord UVs: v = length /
    circumference / 3). Plies run diagonally; fibres follow the plies."""
    u, v = _uv(size)
    s = (u + v) * 3.0
    sf = s - np.floor(s)
    ply = np.sin(np.pi * sf) ** 0.6
    fib_src = T.spectral(size, 1.0, seed, anisotropy=(10.0, 1.0))
    fib = _rot45(fib_src, size)
    hair = _rot45(T.spectral(size, 0.6, seed + 1, anisotropy=(14.0, 1.0)), size)
    plyid = np.floor(s).astype(int) % 2
    col = T.gradient(T.normalize(0.6 * fib + 0.4 * hair), [(0.0, "#5c4a2c"), (0.5, "#85704a"), (1.0, "#a99467")])
    col = np.where(plyid[..., None] == 1, col * 0.9, col)
    col *= (0.55 + 0.45 * ply)[..., None]
    green = T.levels(T.spectral(size, 2.0, seed + 2), 0.6, 0.9)
    col = T.mix(col, col * _rgb("#8f9a5a") / _rgb("#85704a"), green * 0.35)
    height = T.normalize(0.75 * ply + 0.25 * fib)
    rough = 0.88 + 0.08 * (1 - ply)
    _save(out, col, height, rough, ns=5.0, ao=1.4)


@texture("item_plant_fiber", size=512, seed=321, kind="pbr_alpha")
def item_plant_fiber(size, seed, out):
    """Loose stripped fireweed / nettle fibres as an alpha strip card (fibres run along V)."""
    r = T.rng(seed)
    cov = np.zeros((size, size), np.float32)
    shade = np.zeros((size, size), np.float32)
    for i in range(70):
        x = r.uniform(0.08, 0.92) * size
        pts = []
        drift = r.uniform(-0.15, 0.15)
        ph = r.uniform(0, 6.28)
        y0 = r.uniform(0, 0.08) * size
        y1 = size - r.uniform(0, 0.1) * size
        for k in range(16):
            t = k / 15
            pts.append((x + drift * t * size * 0.3 + math.sin(t * 5 + ph) * 6, y0 + (y1 - y0) * t))
        w = r.uniform(1.2, 3.2)
        tmp = np.zeros_like(cov)
        _poly(tmp, pts, w, 1.0)
        shade = np.where(tmp > cov, r.uniform(0.6, 1.0), shade)
        cov = np.maximum(cov, tmp)
    col = T.gradient(T.spectral(size, 1.2, seed + 1, anisotropy=(8.0, 1.0)), [(0.0, "#6d6339"), (0.5, "#9a8c5a"), (1.0, "#b8aa78")])
    col *= (0.6 + 0.4 * shade)[..., None]
    height = cov * shade
    _save(out, col, height, np.full((size, size), 0.9, np.float32), ns=2.0, alpha=(cov > 0.5).astype(np.float32))


@texture("item_canvas", size=1024, seed=322)
def item_canvas(size, seed, out):
    """Cotton duck canvas, neutral khaki (tinted per material), 96 threads per tile (tile 0.12 m)."""
    h, over = _weave(size, 96, seed)
    mott = T.spectral(size, 1.9, seed + 3)
    col = T.gradient(T.normalize(0.7 * mott + 0.3 * h), [(0.0, "#9c9479"), (0.6, "#b8ae92"), (1.0, "#cbc2a6")])
    col *= (0.82 + 0.18 * h)[..., None]
    st = _stains(size, seed + 4, 5, 0.05, 0.16)
    col *= (1 - 0.22 * st)[..., None]
    grease = T.levels(T.spectral(size, 2.0, seed + 5), 0.7, 0.95)
    col *= (1 - 0.25 * grease)[..., None]
    rough = 0.9 - 0.15 * grease
    _save(out, col, 0.85 * h + 0.15 * mott, rough, ns=3.0)


@texture("item_webbing", size=512, seed=323)
def item_webbing(size, seed, out):
    """Nylon webbing: twill ribs (diagonal) running along U (tile 0.05 m), neutral (tinted)."""
    u, v = _uv(size)
    rib = 0.5 + 0.5 * np.sin(2 * math.pi * (24 * v + 6 * u))
    fine = T.spectral(size, 1.0, seed, anisotropy=(1.0, 10.0))
    col = T.gradient(T.normalize(0.6 * rib + 0.4 * fine), [(0.0, "#8a8a80"), (1.0, "#b4b4a8")])
    col *= _grime(size, seed + 1, 0.2)[..., None]
    height = T.normalize(0.8 * rib + 0.2 * fine)
    _save(out, col, height, 0.72 + 0.1 * fine, ns=3.0)


@texture("item_cloth_rag", size=512, seed=324)
def item_cloth_rag(size, seed, out):
    """Faded red plaid flannel (torn shirt): twill-ish weave + checks + stains (tile 0.24 m)."""
    h, over = _weave(size, 128, seed, slub=0.4)
    u, v = _uv(size)

    def stripes(t):
        a = ((t * 4) % 1.0)
        dark = (a > 0.55) & (a < 0.85)
        thin = (np.abs(a - 0.2) < 0.02)
        return dark.astype(np.float32), thin.astype(np.float32)
    dx, tx = stripes(u)
    dy, ty = stripes(v)
    base = _fill(size, "#8e2b22")
    col = T.mix(base, _fill(size, "#3a1513"), np.clip(dx * 0.6 + dy * 0.6, 0, 1))
    col = T.mix(col, _fill(size, "#1c1a1a"), dx * dy)
    col = T.mix(col, _fill(size, "#c8b48c"), np.clip(tx + ty, 0, 1) * 0.6)
    fade = T.levels(T.spectral(size, 2.0, seed + 1), 0.3, 1.0)
    col = T.mix(col, col * 0.6 + 0.25, fade * 0.35)
    st = _stains(size, seed + 2, 4, 0.05, 0.14)
    col = T.mix(col, col * _rgb("#5a4a38") * 1.4, st * 0.5)
    col *= (0.85 + 0.15 * h)[..., None]
    fuzz = T.spectral(size, 0.5, seed + 3)
    _save(out, col, 0.7 * h + 0.3 * fuzz, np.full((size, size), 0.96, np.float32), ns=2.0)


@texture("item_cloth_bandage", size=512, seed=325)
def item_cloth_bandage(size, seed, out):
    """Off-white cotton strips (bandage / torch wrap base): open weave, faint rust-brown stains."""
    h, over = _weave(size, 80, seed, slub=0.5)
    col = T.gradient(T.spectral(size, 2.0, seed + 1), [(0.0, "#cfc6b0"), (1.0, "#e6dfcc")])
    col *= (0.75 + 0.25 * h)[..., None]
    st = _stains(size, seed + 2, 3, 0.04, 0.1)
    col = T.mix(col, _fill(size, "#8a4a32"), st * 0.35)
    dirt = T.levels(T.spectral(size, 1.6, seed + 3), 0.5, 1.0)
    col *= (1 - 0.15 * dirt)[..., None]
    _save(out, col, h, np.full((size, size), 0.95, np.float32), ns=2.5)


@texture("item_parachute", size=512, seed=326)
def item_parachute(size, seed, out):
    """Ripstop nylon: reinforcement grid every ~6 mm (tile 0.1 m), neutral (tinted)."""
    u, v = _uv(size)
    gx = (np.abs(((u * 16) % 1.0) - 0.5) > 0.46).astype(np.float32)
    gy = (np.abs(((v * 16) % 1.0) - 0.5) > 0.46).astype(np.float32)
    grid = np.clip(gx + gy, 0, 1)
    fine = T.spectral(size, 0.6, seed)
    col = T.gradient(T.spectral(size, 2.0, seed + 1), [(0.0, "#a7a596"), (1.0, "#c4c1b0")])
    col *= (0.92 + 0.08 * grid)[..., None]
    height = T.normalize(0.7 * grid + 0.3 * fine)
    _save(out, col, height, 0.55 + 0.1 * fine, ns=1.5)


@texture("item_duct_tape", size=512, seed=327)
def item_duct_tape(size, seed, out):
    """Silver duct tape: poly coating over a cloth scrim (tile 0.05 m)."""
    h, _ = _weave(size, 40, seed, slub=0.2)
    wr = T.spectral(size, 1.5, seed + 1, anisotropy=(1.0, 3.0))
    col = T.gradient(T.normalize(0.5 * h + 0.5 * wr), [(0.0, "#7c8085"), (1.0, "#a3a7ab")])
    dirt = T.levels(T.spectral(size, 1.8, seed + 2), 0.55, 1.0)
    col *= (1 - 0.3 * dirt)[..., None]
    _save(out, col, 0.6 * h + 0.4 * wr, 0.35 + 0.3 * dirt, metal=0.35, ns=1.5)


# ------------------------------------------------------------------------------------------------
# Metals
# ------------------------------------------------------------------------------------------------

@texture("item_steel_tool", size=1024, seed=330)
def item_steel_tool(size, seed, out):
    """Worn tool steel: directional grinding (along U), scratches, pits and patina (tile 0.25 m)."""
    brush = T.spectral(size, 1.1, seed, anisotropy=(1.0, 16.0))
    mott = T.spectral(size, 2.0, seed + 1)
    sc = _scratches(size, seed + 2, 260, 0.01, 0.08, 1.0)
    pits = T.levels(T.spectral(size, 0.5, seed + 3), 0.9, 1.0)
    patina = T.levels(T.spectral(size, 2.2, seed + 4), 0.55, 0.95)
    col = T.gradient(T.normalize(0.5 * brush + 0.5 * mott), [(0.0, "#8e9195"), (0.6, "#a9acb0"), (1.0, "#bfc2c5")])
    col = T.mix(col, _fill(size, "#4a3a2c"), patina * 0.45)
    col = T.mix(col, col * 1.2, sc * 0.6)
    col *= (1 - 0.6 * pits)[..., None]
    height = T.normalize(0.4 * brush - 0.4 * sc - 0.6 * pits + 0.2 * mott)
    rough = 0.32 + 0.18 * patina + 0.12 * brush - 0.08 * sc + 0.2 * pits
    metal = 1.0 - 0.5 * patina - 0.4 * pits
    _save(out, col, height, rough, metal=metal, ns=1.2)


@texture("item_rust", size=1024, seed=331)
def item_rust(size, seed, out):
    """Layered rust: flaking orange-brown scale with dark pitting (tile 0.3 m)."""
    f1, f2, cid = T.worley(size, 160, seed, jitter=0.9)
    flake = T.smoothstep(0.0, 4.0, f2 - f1)
    layer = T.spectral(size, 1.6, seed + 1)
    fine = T.spectral(size, 0.6, seed + 2)
    pits = T.levels(T.spectral(size, 0.8, seed + 3), 0.8, 1.0)
    col = T.gradient(T.normalize(0.6 * layer + 0.4 * fine), [(0.0, "#2e1a10"), (0.35, "#5a2e16"), (0.7, "#8a4a1f"), (1.0, "#b0702e")])
    tint = ((np.sin(cid * 12.9898) * 43758.5453) % 1.0)[..., None]
    col *= 0.85 + 0.25 * tint
    col *= (0.8 + 0.2 * flake)[..., None]
    col *= (1 - 0.5 * pits)[..., None]
    height = T.normalize(0.25 * flake + 0.45 * layer + 0.3 * fine - 0.5 * pits)
    rough = 0.88 + 0.1 * fine
    _save(out, col, height, rough, metal=0.05, ns=4.0, ao=1.3)


@texture("item_paint_metal", size=512, seed=332)
def item_paint_metal(size, seed, out):
    """Painted steel: near-white enamel (tinted per material), orange peel, dirt and fine chips."""
    peel = T.spectral(size, 1.4, seed)
    dirt = T.levels(T.spectral(size, 1.4, seed + 1), 0.55, 1.0)
    chips = T.levels(T.spectral(size, 0.9, seed + 2), 0.9, 0.97)
    col = T.gradient(T.normalize(T.spectral(size, 2.2, seed + 3)), [(0.0, "#cdcdc7"), (1.0, "#dcdcd6")])
    col *= (1 - 0.14 * dirt)[..., None]
    col = T.mix(col, _fill(size, "#3a2a20"), chips * 0.8)
    sc = _scratches(size, seed + 4, 60, 0.01, 0.05, 1.0)
    col = T.mix(col, col * 0.75, sc * 0.5)
    height = T.normalize(0.5 * peel - 0.6 * chips - 0.3 * sc)
    rough = 0.5 + 0.25 * dirt + 0.2 * chips
    _save(out, col, height, rough, metal=0.0, ns=1.0)


@texture("item_aluminium", size=512, seed=333)
def item_aluminium(size, seed, out):
    """Bare / anodised aluminium: fine lathe lines along U, scuffs (tile 0.15 m). Neutral, tinted."""
    lathe = T.spectral(size, 1.0, seed, anisotropy=(1.0, 20.0))
    sc = _scratches(size, seed + 1, 140, 0.01, 0.06, 1.0)
    mott = T.spectral(size, 2.0, seed + 2)
    col = T.gradient(T.normalize(0.4 * lathe + 0.6 * mott), [(0.0, "#a2a5a8"), (1.0, "#c3c6c9")])
    col = T.mix(col, col * 1.15, sc * 0.5)
    dirt = T.levels(T.spectral(size, 1.6, seed + 3), 0.5, 1.0)
    col *= (1 - 0.2 * dirt)[..., None]
    height = T.normalize(0.5 * lathe - 0.4 * sc)
    rough = 0.3 + 0.15 * dirt + 0.1 * lathe
    _save(out, col, height, rough, metal=1.0, ns=0.8)


@texture("item_knurl", size=512, seed=334)
def item_knurl(size, seed, out):
    """Diamond knurling (tile 0.02 m): pyramids from crossed grooves; light metal (tinted)."""
    u, v = _uv(size)
    n = 12
    a = np.abs(((u + v) * n) % 1.0 - 0.5)
    b = np.abs(((u - v) * n) % 1.0 - 0.5)
    pyr = np.minimum(a, b) * 2
    wear = T.levels(T.spectral(size, 1.8, seed), 0.5, 1.0)
    col = T.gradient(pyr, [(0.0, "#5a5c5e"), (1.0, "#b5b8bb")])
    col = T.mix(col, _fill(size, "#c8cacc"), (pyr > 0.85) * wear * 0.6)
    _save(out, col, pyr, 0.35 + 0.25 * (1 - pyr), metal=1.0, ns=2.5)


@texture("item_brass", size=512, seed=335)
def item_brass(size, seed, out):
    """Brass with tarnish and fingerprint smudges (tile 0.08 m)."""
    tarn = T.levels(T.spectral(size, 1.9, seed), 0.4, 0.95)
    sc = _scratches(size, seed + 1, 80, 0.01, 0.06, 1.0)
    col = T.gradient(T.normalize(T.spectral(size, 2.2, seed + 2)), [(0.0, "#a07a32"), (1.0, "#c8a352")])
    col = T.mix(col, _fill(size, "#5a4a2a"), tarn * 0.5)
    col = T.mix(col, col * 1.2, sc * 0.4)
    height = T.normalize(T.spectral(size, 1.0, seed + 3) - sc * 0.5)
    rough = 0.3 + 0.3 * tarn
    _save(out, col, height, rough, metal=1.0 - 0.3 * tarn, ns=0.6)


@texture("item_galvanized", size=512, seed=336)
def item_galvanized(size, seed, out):
    """Hot-dip galvanised spangle (flat crystal cells), white-rust spots (tile 0.2 m)."""
    f1, f2, cid = T.worley(size, 160, seed, jitter=0.95)
    rnd = (np.sin(cid * 12.9898) * 43758.5453) % 1.0
    edge = 1 - T.smoothstep(0.0, 2.0, f2 - f1)
    col = (T.hex_rgb("#8d9397")[None, None, :] + (rnd[..., None] - 0.5) * 0.07)
    col *= (1 - 0.2 * edge)[..., None]
    wr = T.levels(T.spectral(size, 1.4, seed + 1), 0.78, 0.95)
    col = T.mix(col, _fill(size, "#c9c8c0"), wr * 0.6)
    height = T.normalize(rnd * 0.3 - edge * 0.5 + wr * 0.4)
    rough = 0.35 + 0.3 * rnd + 0.3 * wr
    _save(out, col, height, rough, metal=1.0 - 0.6 * wr, ns=0.8)


@texture("item_can_tin", size=512, seed=337)
def item_can_tin(size, seed, out):
    """Tinplate can steel: lacquered, faint drawing lines along U, scuffs (tile 0.1 m)."""
    lines = T.spectral(size, 1.0, seed, anisotropy=(1.0, 24.0))
    sc = _scratches(size, seed + 1, 90, 0.01, 0.07, 1.0)
    col = T.gradient(T.normalize(lines), [(0.0, "#a9aaa6"), (1.0, "#c9c8c0")])
    col = col * (0.75 + 0.25 * _rgb("#d6c9a4") / _rgb("#c9c8c0"))
    col = T.mix(col, col * 0.75, sc * 0.4)
    spots = T.levels(T.spectral(size, 1.2, seed + 2), 0.85, 0.97)
    col = T.mix(col, _fill(size, "#6a4024"), spots * 0.7)
    height = T.normalize(0.4 * lines - 0.5 * sc - 0.3 * spots)
    _save(out, col, height, 0.22 + 0.2 * sc + 0.5 * spots, metal=1.0 - 0.7 * spots, ns=0.8)


@texture("item_foil", size=512, seed=338)
def item_foil(size, seed, out):
    """Crinkled foil laminate: faceted creases (tile 0.12 m), silver (tinted for ration wrappers)."""
    f1, f2, cid = T.worley(size, 240, seed, jitter=0.95)
    rnd = (np.sin(cid * 12.9898) * 43758.5453) % 1.0
    rnd2 = (np.sin(cid * 78.233) * 12345.678) % 1.0
    crease = 1 - T.smoothstep(0.0, 2.5, f2 - f1)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) / size
    facet = (rnd - 0.5) * np.sin(xx * 6.28 * 3) + (rnd2 - 0.5) * np.cos(yy * 6.28 * 3)
    col = T.gradient(T.normalize(rnd * 0.6 + T.spectral(size, 1.5, seed + 1) * 0.4), [(0.0, "#8d8e90"), (1.0, "#d4d5d7")])
    height = T.normalize(facet * 0.6 + rnd * 0.4 - crease * 0.6)
    _save(out, col, height, 0.25 + 0.2 * crease, metal=0.85, ns=2.5)


# ------------------------------------------------------------------------------------------------
# Plastic, rubber, glass, leather
# ------------------------------------------------------------------------------------------------

@texture("item_plastic", size=512, seed=340)
def item_plastic(size, seed, out):
    """Moulded plastic: near-white (tinted per material), faint mould texture and scuffs (tile 0.15 m)."""
    stip = T.spectral(size, 0.7, seed)
    sc = _scratches(size, seed + 1, 70, 0.01, 0.05, 1.0)
    dirt = T.levels(T.spectral(size, 1.3, seed + 2), 0.6, 1.0)
    col = T.gradient(T.normalize(T.spectral(size, 2.2, seed + 3)), [(0.0, "#d6d6d2"), (1.0, "#e2e2de")])
    col *= (1 - 0.1 * dirt)[..., None]
    col = T.mix(col, col * 1.1, sc * 0.4)
    height = T.normalize(0.4 * stip - 0.5 * sc)
    rough = 0.42 + 0.1 * stip + 0.2 * dirt + 0.15 * sc
    _save(out, col, height, rough, ns=0.6)


@texture("item_rubber", size=512, seed=341)
def item_rubber(size, seed, out):
    """Black rubber / rubberised grip with fine stipple (tile 0.08 m)."""
    stip = T.spectral(size, 0.4, seed)
    dust = T.levels(T.spectral(size, 1.7, seed + 1), 0.5, 1.0)
    col = T.gradient(T.normalize(T.spectral(size, 2.0, seed + 2)), [(0.0, "#1a1a1a"), (1.0, "#262626")])
    col = T.mix(col, _fill(size, "#58544c"), dust * 0.3)
    _save(out, col, stip, 0.8 + 0.1 * dust, ns=1.5)


@texture("item_glass", size=512, seed=342)
def item_glass(size, seed, out):
    """Bottle glass (rendered opaque): smooth with faint scuffs and dried water spots (tile 0.2 m)."""
    sc = _scratches(size, seed, 60, 0.01, 0.05, 1.0)
    spots = _stains(size, seed + 1, 12, 0.01, 0.04, ring=True)
    dirt = T.levels(T.spectral(size, 1.3, seed + 2), 0.6, 1.0)
    col = T.gradient(T.spectral(size, 2.4, seed + 3), [(0.0, "#e2e6e4"), (1.0, "#eef1ef")])
    col *= (1 - 0.1 * dirt)[..., None]
    col = T.mix(col, col * 1.1, spots * 0.3)
    height = T.normalize(T.spectral(size, 2.6, seed + 4) * 0.5 - sc * 0.5)
    rough = 0.06 + 0.25 * dirt + 0.3 * sc + 0.2 * spots
    _save(out, col, height, rough, ns=0.5)


@texture("item_leather", size=512, seed=343)
def item_leather(size, seed, out):
    """Worn brown leather: pebble grain, creases, scuffed lighter edges (tile 0.12 m)."""
    f1, f2, _ = T.worley(size, 900, seed, jitter=0.9)
    peb = T.smoothstep(0.0, 4.0, f2 - f1)
    crease = 1 - np.abs(2 * T.spectral(size, 1.4, seed + 1, anisotropy=(3.0, 1.0)) - 1)
    cr = T.smoothstep(0.93, 1.0, crease)
    col = T.gradient(T.normalize(T.spectral(size, 2.0, seed + 2)), [(0.0, "#3a2214"), (0.6, "#5e3a22"), (1.0, "#7a4e2e")])
    col *= (0.85 + 0.15 * peb)[..., None]
    col *= (1 - 0.35 * cr)[..., None]
    scuff = T.levels(T.spectral(size, 1.7, seed + 3), 0.6, 0.95)
    col = T.mix(col, _fill(size, "#8c6a4a"), scuff * 0.35)
    height = T.normalize(0.6 * peb - 0.8 * cr)
    _save(out, col, height, 0.55 + 0.2 * scuff, ns=2.5)


@texture("item_bloom_gel", size=512, seed=344)
def item_bloom_gel(size, seed, out):
    """Sample-vial contents: pale filament suspended in cloudy fluid (rendered opaque)."""
    r = T.rng(seed)
    cov = np.zeros((size, size), np.float32)
    for _ in range(140):
        x, y = r.uniform(0, size, 2)
        a = r.uniform(0, math.tau)
        pts = []
        for i in range(12):
            a += r.uniform(-0.6, 0.6)
            x += math.cos(a) * 8
            y += math.sin(a) * 8
            pts.append((x, y))
        _poly(cov, pts, r.uniform(0.8, 2.0), r.uniform(0.5, 1.0), wrap=True)
    cloud = T.spectral(size, 2.0, seed + 1)
    col = T.gradient(cloud, [(0.0, "#8e8a8c"), (1.0, "#b3aab0")])
    col = T.mix(col, _fill(size, "#ece4e6"), cov)
    _save(out, col, cov * 0.5 + cloud * 0.5, 0.12 + 0.1 * cov, ns=0.8)


# ------------------------------------------------------------------------------------------------
# Printed matter (no text: colour blocks, pictograms, greeked bars)
# ------------------------------------------------------------------------------------------------

def _paper_base(size, seed, tone=("#ddd5c0", "#ece6d4"), age=0.35):
    fib = T.spectral(size, 0.9, seed)
    mott = T.spectral(size, 2.2, seed + 1)
    col = T.gradient(T.normalize(0.4 * fib + 0.6 * mott), [(0.0, tone[0]), (1.0, tone[1])])
    u, v = _uv(size)
    edge = np.minimum(np.minimum(u, 1 - u), np.minimum(v, 1 - v))
    yell = (1 - T.smoothstep(0.0, 0.12, edge)) * age
    col = T.mix(col, _fill(size, "#b89c66"), yell)
    fox = T.levels(T.spectral(size, 0.8, seed + 2), 0.93, 0.99)
    col = T.mix(col, _fill(size, "#a07a48"), fox * 0.5)
    return col, fib


def _crease(size, pos, axis, width=3.0):
    """Fold crease: returns (shade, height) along a line at fractional pos (axis 'x' = vertical line)."""
    c = (np.arange(size) + 0.5) - pos * size
    prof = np.exp(-(c / width) ** 2)
    if axis == "x":
        prof = np.tile(prof[None, :], (size, 1))
    else:
        prof = np.tile(prof[:, None], (1, size))
    return prof


def _label(size, seed, out, *, bg, band, accent, ink, motif, metal=0.0, rough=0.55):
    """Generic can label (U wraps around the can, V spans the label: row 0 = top)."""
    r = T.rng(seed)
    img = _fill(size, bg)
    height = np.zeros((size, size), np.float32)
    s = size
    _rect_fill(img, 0, 0, s, s * 0.15, band)
    _rect_fill(img, 0, s * 0.85, s, s, band)
    _rect_fill(img, 0, s * 0.165, s, s * 0.18, accent)
    _rect_fill(img, 0, s * 0.82, s, s * 0.835, accent)
    # swash across the front
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
    sw = (np.abs((yy - s * 0.30) - (xx - s * 0.25) * 0.12) < s * 0.035) & (xx < s * 0.5) & (xx > 0.0)
    img = T.mix(img, _fill(s, accent), sw.astype(np.float32) * 0.9)
    # vignette
    cx, cy = s * 0.25, s * 0.55
    m = _ellipse_mask(s, s, cx, cy, s * 0.16, s * 0.22, 2.0)
    ring = _ellipse_mask(s, s, cx, cy, s * 0.175, s * 0.235, 2.0) - m
    img = T.mix(img, _fill(s, accent), ring)
    motif(img, m, cx, cy, r)
    # back panel: nutrition-like greeked block + barcode
    _rect_fill(img, s * 0.6, s * 0.24, s * 0.92, s * 0.76, "#f1ece0")
    _bars(img, None, s * 0.62, s * 0.27, s * 0.9, s * 0.6, s * 0.035, r, col=ink, gap=0.45)
    _barcode(img, s * 0.66, s * 0.63, s * 0.86, s * 0.74, r)
    # small brand-free emblem block above the vignette
    _rect_fill(img, s * 0.12, s * 0.2, s * 0.38, s * 0.26, ink)
    _rect_fill(img, s * 0.13, s * 0.215, s * 0.37, s * 0.245, bg)
    _bars(img, None, s * 0.145, s * 0.222, s * 0.36, s * 0.242, s * 0.02, r, col=ink, gap=0.7, density=1.4)
    # wear: scuffs to white paper, water tide line at the bottom, fading, glue seam at u=0
    sc = _scratches(s, seed + 7, 14, 0.01, 0.05, 1.5)
    img = T.mix(img, _fill(s, "#e8e2d2"), sc * 0.45)
    u, v = _uv(s)
    tide = T.smoothstep(0.86, 0.97, v + (T.spectral(s, 2.0, seed + 8) - 0.5) * 0.08)
    img = T.mix(img, img * _rgb("#a08860") / 0.75, tide * 0.35)
    img = T.mix(img, img * 0.85 + 0.12, T.levels(T.spectral(s, 2.2, seed + 9), 0.4, 1.0) * 0.3)
    seam = np.exp(-((xx - 2.0) / 2.0) ** 2)
    img *= (1 - 0.25 * seam)[..., None]
    height += 0.3 * T.spectral(s, 1.0, seed + 10) - 0.6 * sc
    rgh = rough + 0.25 * sc + 0.15 * tide
    _save(out, img, height, rgh, metal=metal, ns=0.6)


def _motif_beans(img, m, cx, cy, r):
    s = img.shape[0]
    img[:] = T.mix(img, _fill(s, "#6b2a17"), m)
    for _ in range(46):
        a, d = r.uniform(0, 6.28), r.uniform(0, 1) ** 0.6
        x, y = cx + math.cos(a) * d * s * 0.13, cy + math.sin(a) * d * s * 0.19
        bm = _ellipse_mask(s, s, x, y, s * 0.018, s * 0.012, 1.0) * m
        img[:] = T.mix(img, _fill(s, r.choice(["#a5502c", "#b8643a", "#94401f"])), bm)
        hl = _ellipse_mask(s, s, x - s * 0.005, y - s * 0.004, s * 0.006, s * 0.003, 1.0) * m
        img[:] = T.mix(img, _fill(s, "#e8b894"), hl * 0.8)


def _motif_stew(img, m, cx, cy, r):
    s = img.shape[0]
    img[:] = T.mix(img, _fill(s, "#3c2010"), m)
    for _ in range(24):
        a, d = r.uniform(0, 6.28), r.uniform(0, 1) ** 0.6
        x, y = cx + math.cos(a) * d * s * 0.12, cy + math.sin(a) * d * s * 0.18
        col = r.choice(["#6a3218", "#7a3c1c", "#c8701e", "#d8c08a"])
        bm = _ellipse_mask(s, s, x, y, s * r.uniform(0.015, 0.03), s * r.uniform(0.012, 0.025), 1.0) * m
        img[:] = T.mix(img, _fill(s, col), bm)
    steam = _ellipse_mask(s, s, cx, cy - s * 0.16, s * 0.1, s * 0.03, 6.0)
    img[:] = T.mix(img, _fill(s, "#f0e6d0"), steam * 0.25)


def _motif_dog(img, m, cx, cy, r):
    s = img.shape[0]
    img[:] = T.mix(img, _fill(s, "#2a4a8a"), m)
    bowl = _ellipse_mask(s, s, cx, cy + s * 0.08, s * 0.12, s * 0.06, 1.5) * m
    img[:] = T.mix(img, _fill(s, "#b8322a"), bowl)
    for _ in range(30):
        x, y = cx + r.uniform(-0.09, 0.09) * s, cy + s * 0.04 + r.uniform(-0.03, 0.03) * s
        km = _ellipse_mask(s, s, x, y, s * 0.012, s * 0.009, 1.0) * m
        img[:] = T.mix(img, _fill(s, r.choice(["#6a3a1c", "#8a5226", "#5a2e14"])), km)
    # paw-print pictogram
    px, py = cx, cy - s * 0.09
    img[:] = T.mix(img, _fill(s, "#f2e8d0"), _ellipse_mask(s, s, px, py + s * 0.02, s * 0.03, s * 0.025, 1.0) * m)
    for dx, dy in ((-0.035, -0.02), (-0.012, -0.04), (0.012, -0.04), (0.035, -0.02)):
        img[:] = T.mix(img, _fill(s, "#f2e8d0"), _ellipse_mask(s, s, px + dx * s, py + dy * s, s * 0.011, s * 0.014, 1.0) * m)


def _motif_soda(img, m, cx, cy, r):
    s = img.shape[0]
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
    wave = np.abs(yy - (s * 0.5 + np.sin(xx / s * 2 * math.pi * 2) * s * 0.12)) < s * 0.06
    img[:] = T.mix(img, _fill(s, "#f2f0ea"), wave.astype(np.float32))
    wave2 = np.abs(yy - (s * 0.5 + np.sin(xx / s * 2 * math.pi * 2) * s * 0.12)) < s * 0.025
    img[:] = T.mix(img, _fill(s, "#1f3c8c"), wave2.astype(np.float32))
    for _ in range(18):
        x, y = r.uniform(0.05, 0.45) * s, r.uniform(0.25, 0.45) * s
        img[:] = T.mix(img, _fill(s, "#f6e6e0"), _ellipse_mask(s, s, x, y, s * 0.008, s * 0.008, 1.0) * 0.8)


@texture("item_can_label_a", size=512, seed=350)
def item_can_label_a(size, seed, out):
    """Beans: cream label, brick-red bands, navy accents."""
    _label(size, seed, out, bg="#e6d9b8", band="#a5302a", accent="#24345a", ink="#2a2a2a", motif=_motif_beans)


@texture("item_can_label_b", size=512, seed=351)
def item_can_label_b(size, seed, out):
    """Stew: forest-green label, gold bands, maroon accents."""
    _label(size, seed, out, bg="#2f4a30", band="#c9a24a", accent="#6a1e1e", ink="#1e1e1e", motif=_motif_stew)


@texture("item_can_label_c", size=512, seed=352)
def item_can_label_c(size, seed, out):
    """Dog food: mustard label, blue bands, red accents, paw pictogram."""
    _label(size, seed, out, bg="#d9ad38", band="#2a4a8a", accent="#b8322a", ink="#1e1e1e", motif=_motif_dog)


@texture("item_can_label_d", size=512, seed=353)
def item_can_label_d(size, seed, out):
    """Soda: printed aluminium, red with a white/blue wave (metallic print)."""
    _label(size, seed, out, bg="#b3222a", band="#8a1820", accent="#1f3c8c", ink="#2a2a2a", motif=_motif_soda, metal=0.6, rough=0.3)


@texture("item_paper", size=512, seed=354)
def item_paper(size, seed, out):
    """Plain off-white paper (backs of sheets, labels), faint fibres and smudges (tile 0.25 m)."""
    fib = T.spectral(size, 0.9, seed)
    col = T.gradient(T.normalize(0.5 * fib + 0.5 * T.spectral(size, 2.0, seed + 1)), [(0.0, "#d9d2be"), (1.0, "#ebe6d6")])
    sm = T.levels(T.spectral(size, 1.8, seed + 2), 0.6, 1.0)
    col *= (1 - 0.12 * sm)[..., None]
    _save(out, col, fib, np.full((size, size), 0.86, np.float32), ns=0.6)


@texture("item_paper_edge", size=512, seed=355)
def item_paper_edge(size, seed, out):
    """Edge of a page block: thin page lines along U (64 per tile in V; tile 0.016 m)."""
    v = (np.arange(size) + 0.5) / size
    k = np.floor(v * 64).astype(int)
    r = T.rng(seed)
    shade = 0.82 + 0.18 * r.random(64).astype(np.float32)
    fr = (v * 64) % 1.0
    line = np.where(fr < 0.15, 0.55, 1.0) * shade[k]
    line = np.tile(line[:, None], (1, size)).astype(np.float32)
    fib = T.spectral(size, 1.0, seed + 1, anisotropy=(1.0, 10.0))
    col = T.gradient(fib, [(0.0, "#cfc6b0"), (1.0, "#e8e2d0")]) * line[..., None]
    dirt = T.levels(T.spectral(size, 1.8, seed + 2), 0.5, 1.0)
    col *= (1 - 0.25 * dirt)[..., None]
    _save(out, col, line, np.full((size, size), 0.9, np.float32), ns=1.5)


@texture("item_paper_note", size=1024, seed=356)
def item_paper_note(size, seed, out):
    """Torn notebook page: ruled lines, red margin, illegible pen scrawl, fold crease, tape."""
    r = T.rng(seed)
    col, fib = _paper_base(size, seed, age=0.25)
    s = size
    for k in range(4, 30):
        y = k * s / 30
        _rect_fill(col, 0, y, s, y + 1.6, "#8ea6c8", 0.6)
    _rect_fill(col, s * 0.14, 0, s * 0.14 + 2, s, "#c86a6a", 0.6)
    ink = np.zeros((s, s), np.float32)
    for k in range(5, 20):
        y = k * s / 30 - 3
        x0 = s * 0.17 if k != 5 else s * 0.2
        x1 = s * r.uniform(0.6, 0.92) if k not in (19,) else s * 0.5
        _scribble(ink, x0, x1, y, s / 30 * 0.7, r, w=2.0, val=0.9)
    pencil = np.zeros((s, s), np.float32)
    for k in range(22, 26):
        y = k * s / 30 - 3
        _scribble(pencil, s * 0.2, s * r.uniform(0.5, 0.75), y, s / 30 * 0.5, r, w=1.6, val=0.7)
    col = T.mix(col, _fill(s, "#22306a"), ink * 0.85)
    col = T.mix(col, _fill(s, "#555558"), pencil * 0.6)
    # tape strip at the top
    tape = _mask_rect(s, s, s * 0.38, 0, s * 0.62, s * 0.07, 2.0)
    col = T.mix(col, col * _rgb("#e8d48a") / 0.9, tape * 0.5)
    cr = _crease(s, 0.5, "y", 3.0)
    col *= (1 - 0.12 * cr)[..., None]
    st = _stains(s, seed + 3, 2, 0.06, 0.12, ring=True)
    col = T.mix(col, _fill(s, "#a07a48"), st * 0.35)
    height = 0.3 * fib - 0.6 * cr + 0.1 * ink
    _save(out, col, height, 0.85 - 0.2 * pencil - 0.3 * tape, ns=1.5)


@texture("item_paper_ledger", size=1024, seed=357)
def item_paper_ledger(size, seed, out):
    """Dispensary ledger page: green ruled columns, typed (greeked) rows, pencil note across the foot."""
    r = T.rng(seed)
    col, fib = _paper_base(size, seed, tone=("#dcdcc6", "#ecebd8"), age=0.3)
    s = size
    _rect_fill(col, s * 0.06, s * 0.08, s * 0.94, s * 0.13, "#7a9a82", 0.5)
    for k in range(0, 26):
        y = s * 0.13 + k * s * 0.03
        _rect_fill(col, s * 0.06, y, s * 0.94, y + 1.5, "#8fb09a", 0.7)
    for x in (0.06, 0.18, 0.55, 0.72, 0.94):
        _rect_fill(col, s * x, s * 0.08, s * x + 2, s * 0.91, "#6a9a7a", 0.8)
    for k in range(1, 9):
        y = s * 0.13 + k * s * 0.03 - s * 0.022
        for (x0, x1) in ((0.075, 0.16), (0.2, 0.52), (0.57, 0.7), (0.74, 0.9)):
            _bars(col, None, s * x0, y, s * x1 * r.uniform(0.85, 1.0), y + s * 0.018, s * 0.02, r, col="#2b2b2e", gap=0.6, density=0.9, alpha=0.8)
    pen = np.zeros((s, s), np.float32)
    for k in range(0, 3):
        y = s * (0.78 + k * 0.045)
        _scribble(pen, s * 0.1, s * r.uniform(0.6, 0.88), y, s * 0.028, r, w=2.2, val=0.9)
    col = T.mix(col, _fill(s, "#4a4a50"), pen * 0.75)
    for hy in (0.2, 0.5, 0.8):
        hm = _ellipse_mask(s, s, s * 0.03, s * hy, s * 0.012, s * 0.012, 1.0)
        col = T.mix(col, _fill(s, "#8a8478"), hm * 0.6)
    st = _stains(s, seed + 3, 2, 0.05, 0.1)
    col = T.mix(col, _fill(s, "#a88a58"), st * 0.25)
    _save(out, col, 0.3 * fib - 0.2 * pen, 0.85 - 0.25 * pen, ns=1.0)


def _schematic_base(size, seed):
    col, fib = _paper_base(size, seed, tone=("#d8cfb6", "#e9e2cc"), age=0.45)
    s = size
    u, v = _uv(s)
    g1 = (np.abs(((u * 24) % 1.0) - 0.5) > 0.485) | (np.abs(((v * 24) % 1.0) - 0.5) > 0.485)
    col = T.mix(col, _fill(s, "#9aaab4"), g1.astype(np.float32) * 0.35)
    cx = _crease(s, 0.5, "x", 3.0)
    cy = _crease(s, 0.5, "y", 2.5)
    col *= (1 - 0.1 * np.clip(cx + cy, 0, 1))[..., None]
    return col, fib, cx, cy


def _finish_schematic(out, col, fib, cx, cy, pencil, seed):
    s = col.shape[0]
    grain = T.spectral(s, 0.4, seed + 50)
    pencil = ndimage.grey_dilation(pencil, size=(3, 3)) * 0.6 + pencil * 0.4
    pc = np.clip(pencil * (0.75 + 0.45 * grain) * 1.15, 0, 1)
    col = T.mix(col, _fill(s, "#2e2e34"), pc * 0.9)
    sm = T.levels(blur_wrap(pencil, 6.0), 0.05, 0.5)
    col = T.mix(col, _fill(s, "#77777a"), sm * 0.12)
    st = _stains(s, seed + 51, 1, 0.07, 0.11, ring=True)
    col = T.mix(col, _fill(s, "#9a7442"), st * 0.3)
    height = 0.25 * fib - 0.7 * np.clip(cx + cy, 0, 1) - 0.15 * pc
    _save(out, col, height, 0.86 - 0.35 * pc, ns=1.8)


def blur_wrap(a, sigma):
    return ndimage.gaussian_filter(a, sigma, mode="wrap")


def _dim(cov, r, x0, y0, x1, y1, off=26):
    """Dimension line with ticks/arrow heads (horizontal or vertical)."""
    horiz = abs(y1 - y0) < abs(x1 - x0)
    if horiz:
        y = y0 + off
        _hand(cov, (x0, y0 + 6), (x0, y + 10), 1.4, r, val=0.6)
        _hand(cov, (x1, y1 + 6), (x1, y + 10), 1.4, r, val=0.6)
        _hand(cov, (x0, y), (x1, y), 1.5, r, val=0.7)
        for x, d in ((x0, 1), (x1, -1)):
            _seg(cov, x, y, x + 14 * d, y - 6, 1.5, 0.7)
            _seg(cov, x, y, x + 14 * d, y + 6, 1.5, 0.7)
        _bars_cov(cov, (x0 + x1) / 2 - 22, y - 16, 44, r)
    else:
        x = x0 + off
        _hand(cov, (x0 + 6, y0), (x + 10, y0), 1.4, r, val=0.6)
        _hand(cov, (x1 + 6, y1), (x + 10, y1), 1.4, r, val=0.6)
        _hand(cov, (x, y0), (x, y1), 1.5, r, val=0.7)
        for y, d in ((y0, 1), (y1, -1)):
            _seg(cov, x, y, x - 6, y + 14 * d, 1.5, 0.7)
            _seg(cov, x, y, x + 6, y + 14 * d, 1.5, 0.7)


def _bars_cov(cov, x, y, w, r):
    """Tiny illegible scrawl (a 'measurement') — squiggle, not glyphs."""
    _scribble(cov, x, x + w, y + 8, 9, r, w=1.3, val=0.7)


def _stake(cov, r, base, tip, w=14):
    b, t = np.array(base, np.float32), np.array(tip, np.float32)
    d = t - b
    L = float(np.hypot(*d))
    d /= L
    n = np.array([-d[1], d[0]]) * w / 2
    pt = t
    sh = b + d * (L - w * 2.2)
    _hand(cov, b + n, sh + n, 1.8, r)
    _hand(cov, b - n, sh - n, 1.8, r)
    _hand(cov, sh + n, pt, 1.8, r)
    _hand(cov, sh - n, pt, 1.8, r)
    for k in range(4):
        q = sh + d * (k * 5.0)
        _seg(cov, *(q + n * 0.8), *(q - n * 0.8), 1.0, 0.35)


@texture("item_schematic_a", size=1024, seed=360)
def item_schematic_a(size, seed, out):
    """Sketch: stake barricade (front elevation + side detail), pencil on aged graph paper."""
    r = T.rng(seed)
    col, fib, cx, cy = _schematic_base(size, seed)
    cov = np.zeros((size, size), np.float32)
    _hand(cov, (60, 760), (960, 760), 2.0, r)
    for x in range(70, 960, 26):
        _seg(cov, x, 766, x - 14, 790, 1.2, 0.4)
    _hand(cov, (140, 690), (880, 692), 2.0, r)
    _hand(cov, (140, 738), (880, 736), 2.0, r)
    _circle(cov, 140, 714, 24, 2.0, r=r, wobble=1.0)
    _circle(cov, 140, 714, 12, 1.2, val=0.6)
    _circle(cov, 880, 714, 24, 2.0, r=r, wobble=1.0)
    for x in (230, 380, 530, 680, 820):
        _stake(cov, r, (x - 70, 750), (x + 95, 330))
        _stake(cov, r, (x + 70, 750), (x - 95, 330))
        for k in range(4):
            _seg(cov, x - 16, 600 + k * 7, x + 16, 606 + k * 7, 1.6, 0.8)
    _dim(cov, r, 140, 800, 880, 800, 30)
    _dim(cov, r, 900, 330, 900, 760, 30)
    # side detail inset
    _hand(cov, (640, 70), (960, 70), 1.6, r, val=0.6)
    _hand(cov, (640, 70), (640, 270), 1.6, r, val=0.6)
    _hand(cov, (960, 70), (960, 270), 1.6, r, val=0.6)
    _hand(cov, (640, 270), (960, 270), 1.6, r, val=0.6)
    _hand(cov, (660, 250), (940, 250), 1.6, r)
    _circle(cov, 760, 230, 20, 1.8, r=r, wobble=0.6)
    _stake(cov, r, (760, 250), (880, 100), w=12)
    _hand(cov, (640, 300), (560, 420), 1.2, r, val=0.5)
    _circle(cov, 530, 640, 60, 1.2, val=0.4, r=r, wobble=2.0)
    for k in range(6):
        _scribble(cov, 70, 70 + r.uniform(160, 300), 120 + k * 34, 18, r, w=1.5, val=0.6)
    _finish_schematic(out, col, fib, cx, cy, cov, seed)


@texture("item_schematic_b", size=1024, seed=361)
def item_schematic_b(size, seed, out):
    """Sketch: trapper's cabin elevation (stacked logs, round log ends, gable of poles) + plan inset."""
    r = T.rng(seed)
    col, fib, cx, cy = _schematic_base(size, seed)
    cov = np.zeros((size, size), np.float32)
    _hand(cov, (60, 820), (970, 820), 2.0, r)
    for x in range(70, 960, 30):
        _seg(cov, x, 826, x - 14, 850, 1.2, 0.4)
    y = 820
    for row in range(7):
        top = y - 52
        _hand(cov, (180, top), (840, top + r.uniform(-2, 2)), 1.9, r)
        ex = 150 if row % 2 == 0 else 165
        _circle(cov, ex, top + 26, 25, 1.9, r=r, wobble=1.0)
        _circle(cov, ex, top + 26, 13, 1.1, val=0.5, r=r)
        _circle(cov, 1024 - ex, top + 26, 25, 1.9, r=r, wobble=1.0)
        _circle(cov, 1024 - ex, top + 26, 13, 1.1, val=0.5, r=r)
        y = top
    _hand(cov, (450, 820), (450, 560), 2.0, r)
    _hand(cov, (580, 820), (580, 560), 2.0, r)
    _hand(cov, (450, 560), (580, 560), 2.0, r)
    _hand(cov, (120, 460), (512, 230), 2.2, r)
    _hand(cov, (904, 460), (512, 230), 2.2, r)
    for k in range(1, 4):
        _hand(cov, (120 + k * 30, 460 + 4), (512, 230 + k * 22), 1.3, r, val=0.6)
        _hand(cov, (904 - k * 30, 460 + 4), (512, 230 + k * 22), 1.3, r, val=0.6)
    _dim(cov, r, 150, 860, 874, 860, 24)
    _dim(cov, r, 930, 460, 930, 820, 24)
    # plan inset
    for (a, b) in (((80, 80), (300, 80)), ((80, 250), (300, 250)), ((100, 60), (100, 270)), ((280, 60), (280, 270))):
        _hand(cov, a, b, 1.7, r)
    _hand(cov, (165, 250), (215, 250), 4.0, r, val=0.3)
    for k in range(5):
        _scribble(cov, 360, 360 + r.uniform(140, 260), 90 + k * 32, 16, r, w=1.5, val=0.6)
    _finish_schematic(out, col, fib, cx, cy, cov, seed)


@texture("item_schematic_c", size=1024, seed=362)
def item_schematic_c(size, seed, out):
    """Sketch: can chime (two stakes, sagging cord, hanging cans, rattle marks) + knot detail."""
    r = T.rng(seed)
    col, fib, cx, cy = _schematic_base(size, seed)
    cov = np.zeros((size, size), np.float32)
    _hand(cov, (60, 780), (970, 780), 2.0, r)
    for x in range(80, 960, 22):
        _seg(cov, x, 780, x + r.uniform(-6, 6), 780 - r.uniform(8, 22), 1.1, 0.45)
    for x in (170, 850):
        _hand(cov, (x - 9, 430), (x - 9, 790), 1.9, r)
        _hand(cov, (x + 9, 430), (x + 9, 790), 1.9, r)
        _hand(cov, (x - 9, 430), (x + 9, 430), 1.9, r)
        _hand(cov, (x - 9, 790), (x, 840), 1.3, r, val=0.45)
        _hand(cov, (x + 9, 790), (x, 840), 1.3, r, val=0.45)
    pts = [(170 + (850 - 170) * t, 450 + math.cosh((t - 0.5) * 2.2) * -40 + 40 + 60 * (1 - (2 * t - 1) ** 2)) for t in np.linspace(0, 1, 40)]
    _poly(cov, pts, 1.8, 0.85)
    for x in (360, 410, 610, 660):
        t = (x - 170) / 680
        yc = 450 + 60 * (1 - (2 * t - 1) ** 2) + 2
        _hand(cov, (x, yc), (x, yc + 60), 1.2, r, val=0.7)
        top = yc + 60
        _hand(cov, (x - 22, top + 6), (x - 22, top + 86), 1.8, r)
        _hand(cov, (x + 22, top + 6), (x + 22, top + 86), 1.8, r)
        _circle(cov, x, top + 6, 22, 1.4, r=r, n=24)
        _circle(cov, x, top + 86, 22, 1.4, r=r, n=24, arc=(0.0, 0.5))
        for k in range(3):
            _circle(cov, x + 34 + k * 7, top + 46, 12 + k * 6, 1.2, val=0.55, n=10, arc=(-0.12, 0.12))
    _dim(cov, r, 170, 860, 850, 860, 24)
    _hand(cov, (650, 90), (950, 90), 1.6, r, val=0.6)
    _hand(cov, (650, 90), (650, 300), 1.6, r, val=0.6)
    _hand(cov, (950, 90), (950, 300), 1.6, r, val=0.6)
    _hand(cov, (650, 300), (950, 300), 1.6, r, val=0.6)
    _circle(cov, 800, 200, 60, 2.0, r=r, wobble=1.0)
    _circle(cov, 800, 200, 8, 1.6, r=r)
    _hand(cov, (800, 120), (800, 192), 1.6, r)
    _circle(cov, 800, 120, 10, 1.6, r=r)
    _hand(cov, (650, 300), (430, 560), 1.2, r, val=0.5)
    for k in range(5):
        _scribble(cov, 80, 80 + r.uniform(160, 320), 110 + k * 34, 18, r, w=1.5, val=0.6)
    _finish_schematic(out, col, fib, cx, cy, cov, seed)


def _photo_landscape(img, x0, y0, x1, y1, r, seed, *, sky=("#9fb2bf", "#ddd8c6"), hills="#6f7f8c", forest="#23361f",
                     ground="#5a4630", logs=True, hiker=False):
    s = img.shape[0]
    h = int(y1 - y0)
    w = int(x1 - x0)
    sub = np.zeros((h, w, 3), np.float32)
    t = np.linspace(0, 1, h)[:, None]
    sub[:] = (T.hex_rgb(sky[0]) * (1 - t) + T.hex_rgb(sky[1]) * t)[:, None, :][:, 0, :][:, None, :]
    xs = np.arange(w)
    rr = T.rng(seed)
    ridge = h * 0.45 + np.cumsum(rr.normal(0, 1.4, w))
    ridge = ndimage.gaussian_filter1d(ridge, 6)
    yy = np.arange(h)[:, None]
    sub[yy > ridge[None, :]] = T.hex_rgb(hills)
    horizon = int(h * 0.62)
    for _ in range(90):
        cx = rr.uniform(0, w)
        ch = rr.uniform(0.08, 0.22) * h
        base = horizon + rr.uniform(-0.03, 0.06) * h
        tri = (yy > base - ch) & (yy < base) & (np.abs(xs[None, :] - cx) < (yy - (base - ch)) * 0.32)
        sub[tri] = T.hex_rgb(forest) * rr.uniform(0.8, 1.15)
    sub[np.broadcast_to(yy > horizon + h * 0.05, (h, w))] = T.hex_rgb(ground)
    if logs:
        for row in range(4):
            for k in range(5 - row):
                cxl = w * 0.62 + k * h * 0.075 + row * h * 0.037
                cyl = h * 0.94 - row * h * 0.07
                m = ((xs[None, :] - cxl) ** 2 + (yy - cyl) ** 2) < (h * 0.035) ** 2
                sub[m] = T.hex_rgb("#c9a26a")
                m2 = ((xs[None, :] - cxl) ** 2 + (yy - cyl) ** 2) < (h * 0.012) ** 2
                sub[m2] = T.hex_rgb("#8a6238")
    if hiker:
        hx, hy = w * 0.68, h * 0.5
        body = (np.abs(xs[None, :] - hx) < h * 0.02) & (yy > hy) & (yy < hy + h * 0.12)
        pack = (np.abs(xs[None, :] - (hx + h * 0.025)) < h * 0.02) & (yy > hy + h * 0.01) & (yy < hy + h * 0.07)
        head = ((xs[None, :] - hx) ** 2 + (yy - (hy - h * 0.015)) ** 2) < (h * 0.017) ** 2
        sub[body | pack | head] = T.hex_rgb("#1c1c1e")
    noise_ = T.spectral(s, 1.4, seed + 1)[:h, :w]
    sub *= (0.92 + 0.12 * noise_)[..., None]
    img[int(y0):int(y0) + h, int(x0):int(x0) + w] = sub


def _cover(size, seed, out, *, mast, accent, accent2, photo_kw, badge=False):
    r = T.rng(seed)
    s = size
    img = _fill(s, "#f0ece2")
    _photo_landscape(img, 0, s * 0.17, s, s, r, seed, **photo_kw)
    _rect_fill(img, 0, 0, s, s * 0.16, mast)
    _rect_fill(img, s * 0.05, s * 0.03, s * 0.7, s * 0.12, "#f2ede0", 0.92)
    _rect_fill(img, s * 0.07, s * 0.045, s * 0.68, s * 0.105, mast, 0.35)
    _rect_fill(img, 0, s * 0.16, s, s * 0.175, accent)
    _rect_fill(img, s * 0.76, s * 0.03, s * 0.95, s * 0.12, accent2)
    for k, cy in enumerate((0.26, 0.38, 0.5)):
        _rect_fill(img, s * 0.05, s * cy, s * 0.42, s * (cy + 0.085), accent if k % 2 == 0 else "#f2ede0", 0.9)
        _bars(img, None, s * 0.07, s * (cy + 0.015), s * 0.4, s * (cy + 0.075), s * 0.025, r,
              col="#f2ede0" if k % 2 == 0 else "#202020", gap=0.6)
    _barcode(img, s * 0.05, s * 0.86, s * 0.25, s * 0.96, r)
    if badge:
        bx, by = s * 0.84, s * 0.3
        _rect_fill(img, bx - s * 0.08, by - s * 0.08, bx + s * 0.08, by + s * 0.08, "#1f7a3a")
        _rect_fill(img, bx - s * 0.02, by - s * 0.06, bx + s * 0.02, by + s * 0.06, "#f6f2e8")
        _rect_fill(img, bx - s * 0.06, by - s * 0.02, bx + s * 0.06, by + s * 0.02, "#f6f2e8")
    sc = _scratches(s, seed + 3, 50, 0.01, 0.08, 1.5)
    img = T.mix(img, _fill(s, "#e6e0d0"), sc * 0.5)
    u, v = _uv(s)
    corner = (1 - T.smoothstep(0.0, 0.06, np.minimum(1 - u, v))) * 0.6
    img = T.mix(img, img * 0.75 + 0.15, corner)
    gloss = T.levels(T.spectral(s, 2.0, seed + 4), 0.3, 1.0)
    height = 0.2 * T.spectral(s, 0.9, seed + 5) - 0.5 * sc
    _save(out, img, height, 0.35 + 0.2 * gloss + 0.3 * sc, ns=0.8)


@texture("item_magazine_a", size=1024, seed=363)
def item_magazine_a(size, seed, out):
    """Timber & Trade Monthly cover: green masthead, forest + log-pile photo, orange cover blocks."""
    _cover(size, seed, out, mast="#2f4a2a", accent="#d8742a", accent2="#e8c14a",
           photo_kw=dict(sky=("#a9b8c0", "#e2dccb"), hills="#71808c", forest="#22351f", ground="#5c4630", logs=True))


@texture("item_magazine_b", size=1024, seed=364)
def item_magazine_b(size, seed, out):
    """Backcountry Medicine Quarterly cover: red masthead, ridge-line hiker photo, first-aid badge."""
    _cover(size, seed, out, mast="#a52a24", accent="#1f4e8a", accent2="#f2ede0",
           photo_kw=dict(sky=("#8fb0cc", "#e8e2d0"), hills="#5c6a58", forest="#30482a", ground="#6a5a40", logs=False, hiker=True),
           badge=True)


@texture("item_magazine_back", size=512, seed=365)
def item_magazine_back(size, seed, out):
    """Generic back-cover advert: colour field, product silhouette, greeked copy."""
    r = T.rng(seed)
    s = size
    t = np.linspace(0, 1, s)[:, None, None]
    img = np.ones((s, s, 3), np.float32) * (T.hex_rgb("#b8642a") * (1 - t) + T.hex_rgb("#3a1e12") * t)
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
    boot = ((xx - s * 0.5) ** 2 / (s * 0.22) ** 2 + (yy - s * 0.62) ** 2 / (s * 0.08) ** 2 < 1) | \
           ((np.abs(xx - s * 0.42) < s * 0.09) & (yy > s * 0.3) & (yy < s * 0.62))
    img[boot] = T.hex_rgb("#1a1410")
    _rect_fill(img, s * 0.08, s * 0.08, s * 0.92, s * 0.2, "#f2ede0", 0.9)
    _bars(img, None, s * 0.1, s * 0.11, s * 0.9, s * 0.18, s * 0.035, r, col="#3a1e12", gap=0.6)
    _bars(img, None, s * 0.1, s * 0.8, s * 0.6, s * 0.92, s * 0.03, r, col="#f2ede0", gap=0.5)
    _save(out, img, T.spectral(s, 1.0, seed + 1) * 0.2, np.full((s, s), 0.4, np.float32), ns=0.5)


@texture("item_manual_cover", size=512, seed=366)
def item_manual_cover(size, seed, out):
    """Remand Field Manual cover: olive drab board, broken stencil stripes, stencil emblem, a taped
    label with someone's marker scrawl, worn corners."""
    r = T.rng(seed)
    s = size
    img = T.gradient(T.spectral(s, 2.0, seed), [(0.0, "#454a2c"), (1.0, "#575d38")])
    u, v = _uv(s)

    def stencil_band(y0, y1):
        m = _mask_rect(s, s, -10, s * y0, s + 10, s * y1, 1.2)
        bridges = (np.abs(((u * 7) % 1.0) - 0.5) > 0.47)
        return m * (~bridges)
    st = np.clip(stencil_band(0.12, 0.17) + stencil_band(0.2, 0.23), 0, 1)
    img = T.mix(img, _fill(s, "#d8cfae"), st * 0.9)
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
    d = np.hypot(xx - s * 0.5, yy - s * 0.48)
    ring = (np.abs(d - s * 0.14) < s * 0.016) & ~(np.abs(xx - s * 0.5) < s * 0.012) & ~(np.abs(yy - s * 0.48) < s * 0.012)
    chev = (np.abs(yy - s * 0.52 + np.abs(xx - s * 0.5) * 0.7) < s * 0.018) & (np.abs(xx - s * 0.5) < s * 0.08) & ~(np.abs(xx - s * 0.5) < s * 0.01)
    img[ring | chev] = T.hex_rgb("#d8cfae")
    _rect_fill(img, s * 0.18, s * 0.72, s * 0.82, s * 0.86, "#e6e0cc")
    pen = np.zeros((s, s), np.float32)
    _scribble(pen, s * 0.22, s * 0.78, s * 0.8, s * 0.04, r, w=2.5)
    img = T.mix(img, _fill(s, "#151518"), pen * 0.85)
    edge = np.minimum(np.minimum(u, 1 - u), np.minimum(v, 1 - v))
    wear = (1 - T.smoothstep(0.0, 0.05, edge)) * T.levels(T.spectral(s, 1.0, seed + 1), 0.3, 0.8)
    img = T.mix(img, _fill(s, "#8f8a72"), wear * 0.7)
    stn = _stains(s, seed + 2, 1, 0.08, 0.12, ring=True)
    img = T.mix(img, _fill(s, "#2e2a1a"), stn * 0.4)
    h = T.spectral(s, 0.9, seed + 3) * 0.4 + st * 0.1 - wear * 0.3
    _save(out, img, h, 0.75 - 0.2 * st, ns=1.2)


@texture("item_cardboard", size=512, seed=374)
def item_cardboard(size, seed, out):
    """Plain kraft board (box sides, tubes, cores): fibres, faint flute lines along U, scuffs (tile 0.3 m)."""
    fib = T.spectral(size, 0.9, seed)
    v = np.tile((np.arange(size)[:, None] + 0.5) / size, (1, size))
    flute = 0.5 + 0.5 * np.sin(v * 2 * math.pi * 60)
    col = T.gradient(T.normalize(0.6 * T.spectral(size, 2.0, seed + 1) + 0.4 * fib), [(0.0, "#8e6640"), (1.0, "#b48a5c")])
    col *= (0.96 + 0.04 * flute)[..., None]
    sc = _scratches(size, seed + 2, 50, 0.01, 0.06, 1.5)
    col = T.mix(col, _fill(size, "#c8a478"), sc * 0.5)
    st = _stains(size, seed + 3, 4, 0.04, 0.1)
    col = T.mix(col, col * 0.7, st * 0.5)
    _save(out, col, 0.4 * fib + 0.3 * flute - 0.3 * sc, np.full((size, size), 0.9, np.float32), ns=1.0)


@texture("item_box_print", size=512, seed=367)
def item_box_print(size, seed, out):
    """Printed hardware box face (nails): kraft board, red band, white panel with a nail pictogram."""
    r = T.rng(seed)
    s = size
    img = T.gradient(T.spectral(s, 1.6, seed), [(0.0, "#94683e"), (1.0, "#b08052")])
    _rect_fill(img, 0, 0, s, s * 0.2, "#a8302a")
    _rect_fill(img, 0, s * 0.92, s, s, "#a8302a")
    _rect_fill(img, s * 0.08, s * 0.28, s * 0.92, s * 0.82, "#efe9dc")
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
    shank = (np.abs(yy - s * 0.5) < s * 0.025) & (xx > s * 0.2) & (xx < s * 0.72)
    head = (np.abs(xx - s * 0.2) < s * 0.015) & (np.abs(yy - s * 0.5) < s * 0.09)
    point = (xx >= s * 0.72) & (xx < s * 0.82) & (np.abs(yy - s * 0.5) < (s * 0.82 - xx) * 0.25)
    img[shank | head | point] = T.hex_rgb("#4a4c50")
    _bars(img, None, s * 0.12, s * 0.64, s * 0.88, s * 0.78, s * 0.04, r, col="#2a2a2a", gap=0.5)
    _rect_fill(img, s * 0.7, s * 0.04, s * 0.95, s * 0.16, "#e8c14a")
    sc = _scratches(s, seed + 1, 40, 0.01, 0.06, 1.5)
    img = T.mix(img, _fill(s, "#c8a070"), sc * 0.5)
    _save(out, img, T.spectral(s, 0.8, seed + 2) * 0.3 - sc * 0.3, np.full((s, s), 0.82, np.float32), ns=1.0)


@texture("item_scrip", size=512, seed=368)
def item_scrip(size, seed, out):
    """Program trade chit: grey-green card, guilloche waves, stencil stripe band, emblem, serial bars."""
    r = T.rng(seed)
    s = size
    img = T.gradient(T.spectral(s, 2.0, seed), [(0.0, "#b9bca6"), (1.0, "#cfd1bc")])
    u, v = _uv(s)
    for k in range(10):
        w = np.abs(v - (0.25 + k * 0.055) - 0.02 * np.sin(u * 2 * math.pi * 6 + k)) < 0.0025
        img[w] = img[w] * 0.8
    band = (u > 0.06) & (u < 0.3)
    stripes = band & (((u + v * 0.4) * 22) % 1.0 > 0.5)
    img[band] = T.hex_rgb("#5a6038")
    img[stripes] = T.hex_rgb("#d8cfae")
    d = np.hypot(u - 0.62, v - 0.45)
    img[np.abs(d - 0.12) < 0.012] = T.hex_rgb("#3e4426")
    img[(np.abs(v - 0.47 + np.abs(u - 0.62) * 0.7) < 0.014) & (np.abs(u - 0.62) < 0.07)] = T.hex_rgb("#3e4426")
    frame = (np.minimum(np.minimum(u, 1 - u), np.minimum(v, 1 - v)) < 0.03) & (np.minimum(np.minimum(u, 1 - u), np.minimum(v, 1 - v)) > 0.02)
    img[frame] = T.hex_rgb("#3e4426")
    _barcode(img, s * 0.5, s * 0.74, s * 0.92, s * 0.9, r, bg="#cfd1bc")
    _rect_fill(img, s * 0.06, s * 0.82, s * 0.3, s * 0.88, "#a8302a")
    wear = T.levels(T.spectral(s, 1.6, seed + 1), 0.5, 1.0)
    img *= (1 - 0.2 * wear)[..., None]
    _save(out, img, T.spectral(s, 0.8, seed + 2) * 0.3, np.full((s, s), 0.8, np.float32), ns=0.8)


@texture("item_tag_print", size=512, seed=369)
def item_tag_print(size, seed, out):
    """Manila evidence tag: red border + header band, reinforcing ring, marker scrawl."""
    r = T.rng(seed)
    s = size
    img = T.gradient(T.spectral(s, 1.8, seed), [(0.0, "#c9ad74"), (1.0, "#dcc38c")])
    u, v = _uv(s)
    edge = np.minimum(np.minimum(u, 1 - u), np.minimum(v, 1 - v))
    img[(edge > 0.04) & (edge < 0.06)] = T.hex_rgb("#a8302a")
    hb = (v > 0.26) & (v < 0.36) & (u > 0.08) & (u < 0.92)
    img[hb] = T.hex_rgb("#a8302a")
    gaps = hb & (((u * 13) % 1.0) > 0.8)
    img[gaps] = T.hex_rgb("#dcc38c")
    d = np.hypot(u - 0.5, v - 0.12)
    img[(d > 0.035) & (d < 0.065)] = T.hex_rgb("#b89a62")
    pen = np.zeros((s, s), np.float32)
    for k in range(4):
        _scribble(pen, s * 0.12, s * r.uniform(0.6, 0.88), s * (0.5 + k * 0.1), s * 0.035, r, w=2.2)
    img = T.mix(img, _fill(s, "#1a1a20"), pen * 0.85)
    st = _stains(s, seed + 1, 2, 0.05, 0.12)
    img = T.mix(img, _fill(s, "#8a6a3a"), st * 0.3)
    _save(out, img, T.spectral(s, 0.8, seed + 2) * 0.3, np.full((s, s), 0.85, np.float32), ns=0.8)


@texture("item_rx_label", size=512, seed=370)
def item_rx_label(size, seed, out):
    """Prescription vial label: white paper, blue header band, greeked lines, small barcode, red band."""
    r = T.rng(seed)
    s = size
    img = _fill(s, "#ece9e0")
    _rect_fill(img, 0, 0, s, s * 0.16, "#2a4a8a")
    _bars(img, None, s * 0.06, s * 0.24, s * 0.94, s * 0.7, s * 0.07, r, col="#2a2a2a", gap=0.45)
    _barcode(img, s * 0.62, s * 0.74, s * 0.94, s * 0.88, r, bg="#ece9e0")
    _rect_fill(img, 0, s * 0.9, s, s, "#c8322a")
    sc = _scratches(s, seed + 1, 30, 0.01, 0.06, 1.5)
    img = T.mix(img, _fill(s, "#d0c8b8"), sc * 0.5)
    _save(out, img, T.spectral(s, 0.8, seed + 2) * 0.3, np.full((s, s), 0.6, np.float32), ns=0.5)


@texture("item_screen", size=512, seed=371)
def item_screen(size, seed, out):
    """Tether LCD: dark green-grey, faint pixel grid, dim bar-graph segments (no digits), glare."""
    s = size
    u, v = _uv(s)
    img = _fill(s, "#1c2420")
    grid = (np.abs(((u * 96) % 1.0) - 0.5) > 0.42) | (np.abs(((v * 64) % 1.0) - 0.5) > 0.42)
    img[grid] *= 0.85
    for k in range(10):
        on = k < 6
        x0 = 0.12 + k * 0.075
        m = _mask_rect(s, s, s * x0, s * 0.62, s * (x0 + 0.055), s * 0.8, 1.0)
        img = T.mix(img, _fill(s, "#4a6a52" if on else "#26302b"), m)
    m = _mask_rect(s, s, s * 0.12, s * 0.25, s * 0.86, s * 0.45, 1.0)
    img = T.mix(img, _fill(s, "#2b3a32"), m)
    m2 = _mask_rect(s, s, s * 0.14, s * 0.29, s * 0.62, s * 0.41, 1.0)
    img = T.mix(img, _fill(s, "#4f7458"), m2)
    glare = np.clip(1 - np.abs((u + v) - 0.7) / 0.25, 0, 1) * 0.08
    img += glare[..., None]
    _save(out, img, np.zeros((s, s), np.float32) + grid * 0.2, 0.08 + 0.05 * grid, ns=0.3)


@texture("item_stencil_band", size=512, seed=372)
def item_stencil_band(size, seed, out):
    """Program stencil stripes on olive paint: U along the band (tile 0.5 m), V across the band (0..1)."""
    s = size
    u, v = _uv(s)
    base = T.gradient(T.spectral(s, 1.8, seed), [(0.0, "#4a4f2e"), (1.0, "#5c6238")])
    soft = T.spectral(s, 1.2, seed + 1) * 0.02
    m1 = T.smoothstep(0.17, 0.19, v + soft) * (1 - T.smoothstep(0.41, 0.43, v + soft))
    m2 = T.smoothstep(0.57, 0.59, v + soft) * (1 - T.smoothstep(0.81, 0.83, v + soft))
    bridges = T.smoothstep(0.455, 0.47, np.abs(((u * 6) % 1.0) - 0.5))
    st = np.clip(m1 + m2, 0, 1) * (1 - bridges)
    col = T.mix(base, _fill(s, "#d6cdaa"), st * 0.92)
    chips = T.levels(T.spectral(s, 0.9, seed + 2), 0.88, 0.95)
    col = T.mix(col, _fill(s, "#2a241e"), chips * 0.8)
    dirt = T.levels(T.spectral(s, 1.8, seed + 3), 0.45, 1.0)
    col *= (1 - 0.25 * dirt)[..., None]
    _save(out, col, T.spectral(s, 1.4, seed + 4) * 0.5 - chips * 0.5 + st * 0.1, 0.55 + 0.25 * dirt + 0.2 * chips, ns=1.0)


@texture("item_clay", size=512, seed=373)
def item_clay(size, seed, out):
    """Dried clay daub with shrinkage cracks and straw bits (tile 0.4 m)."""
    f1, f2, cid = T.worley(size, 70, seed, jitter=0.9)
    crack = 1 - T.smoothstep(0.0, 3.0, f2 - f1)
    lump = T.spectral(size, 1.8, seed + 1)
    col = T.gradient(T.normalize(lump), [(0.0, "#6a4a30"), (0.6, "#8a6440"), (1.0, "#a57a4e")])
    col *= (1 - 0.6 * crack)[..., None]
    straw = _scratches(size, seed + 2, 120, 0.01, 0.03, 1.5)
    col = T.mix(col, _fill(size, "#b89a5a"), straw * 0.6)
    _save(out, col, lump * 0.6 - crack * 0.8 + straw * 0.2, 0.92 - 0.0 * crack, ns=3.0, ao=1.4)


# ------------------------------------------------------------------------------------------------
# Foliage cards (alpha) — foliage shader
# ------------------------------------------------------------------------------------------------

@texture("item_fir_bough", size=1024, seed=380, kind="pbr_alpha")
def item_fir_bough(size, seed, out):
    """One flat fir spray: stem from the bottom (v=0) to the tip (v=1), alternating branchlets with
    two rows of needles. Alpha cut-out."""
    r = T.rng(seed)
    s = size
    cov = np.zeros((s, s), np.float32)
    tone = np.zeros((s, s), np.float32)
    stem = np.zeros((s, s), np.float32)

    def needle_row(p0, p1, length, density, side_angle):
        p0 = np.array(p0, np.float32)
        p1 = np.array(p1, np.float32)
        d = p1 - p0
        L = float(np.hypot(*d))
        if L < 1:
            return
        d /= L
        n = np.array([-d[1], d[0]])
        k = int(L / density)
        for i in range(k):
            t = (i + r.uniform(0, 0.6)) / max(1, k)
            base = p0 + d * L * t
            fade = 0.55 + 0.45 * (1 - t) ** 0.5
            ln = length * fade * r.uniform(0.8, 1.1)
            for sd in (1, -1):
                a = side_angle * r.uniform(0.85, 1.15)
                dirn = d * math.cos(a) + n * sd * math.sin(a)
                tip = base + dirn * ln
                tmp_val = r.uniform(0.75, 1.0)
                _seg(cov, base[0], base[1], tip[0], tip[1], 5.5, 1.0)
                _seg(tone, base[0], base[1], tip[0], tip[1], 5.5, tmp_val * (0.85 + 0.3 * t))
        # dense inner needle mass along the twig so the spray stays solid at low mips
        _seg(cov, p0[0], p0[1], p0[0] + d[0] * L, p0[1] + d[1] * L, length * 1.25, 1.0)
        _seg(tone, p0[0], p0[1], p0[0] + d[0] * L, p0[1] + d[1] * L, length * 1.25, 0.55)

    pts = []
    ph = r.uniform(0, 6.28)
    for i in range(24):
        t = i / 23
        pts.append((s * 0.5 + math.sin(t * 2.4 + ph) * s * 0.035, s * (0.985 - 0.95 * t)))
    _poly(stem, pts, 7.0, 1.0)
    _poly(cov, pts, 7.0, 1.0)
    for i in range(1, 23):
        t = i / 23
        x, y = pts[i]
        side = 1 if i % 2 == 0 else -1
        L = s * (0.47 * (1 - t) ** 0.62 + 0.09)
        ang = math.radians(r.uniform(56, 70))
        dx, dy = math.sin(ang) * side, -math.cos(ang)
        end = (x + dx * L, y + dy * L)
        mid = (x + dx * L * 0.5 + r.uniform(-6, 6), y + dy * L * 0.5 + r.uniform(-6, 6))
        _poly(stem, [(x, y), mid, end], 3.5, 1.0)
        _poly(cov, [(x, y), mid, end], 3.5, 1.0)
        needle_row((x, y), mid, s * 0.034, 6.0, math.radians(62))
        needle_row(mid, end, s * 0.031, 6.0, math.radians(58))
        if L > s * 0.2:
            for f in (0.35, 0.6):
                bx, by = x + dx * L * f, y + dy * L * f
                sl = L * 0.35 * (1 - f)
                a2 = ang + math.radians(35)
                e2 = (bx + math.sin(a2) * side * sl, by - math.cos(a2) * sl)
                _seg(stem, bx, by, e2[0], e2[1], 2.5, 1.0)
                needle_row((bx, by), e2, s * 0.024, 6.5, math.radians(60))
    needle_row(pts[-6], pts[-1], s * 0.026, 6.0, math.radians(55))
    alpha = (cov > 0.45).astype(np.float32)
    shade = np.clip(tone, 0, 1.3)
    col = T.gradient(np.clip(shade - 0.4, 0, 1) / 0.9, [(0.0, "#1d3318"), (0.5, "#2f4d24"), (1.0, "#4f7038")])
    col = T.mix(col, _fill(s, "#5a3e24"), np.clip(stem, 0, 1))
    tipmask = T.levels(T.spectral(s, 1.8, seed + 1), 0.7, 0.95)
    col = T.mix(col, _fill(s, "#6a8a3e"), tipmask * 0.3 * (1 - stem))
    height = 0.6 * cov + 0.6 * stem
    _save(out, col, height, np.full((s, s), 0.72, np.float32), ns=2.0, alpha=alpha)


@texture("item_herb_atlas", size=512, seed=381, kind="pbr_alpha")
def item_herb_atlas(size, seed, out):
    """Atlas (quadrants, UV origin bottom-left): [0,.5]x[.5,1] yarrow leaf, [.5,1]x[.5,1] huckleberry
    leaf, [0,.5]x[0,.5] yarrow flower head (top view), [.5,1]x[0,.5] yarrow flower head (side view)."""
    r = T.rng(seed)
    s = size
    h = s // 2
    cov = np.zeros((s, s), np.float32)
    col = np.zeros((s, s, 3), np.float32)
    # yarrow leaf: image top-left quadrant, base at its bottom
    leaf = np.zeros((s, s), np.float32)
    x0, yb, yt = h * 0.5, h * 0.98, h * 0.04
    _seg(leaf, x0, yb, x0, yt, 3.0, 1.0)
    for k in range(26):
        t = k / 25
        y = yb + (yt - yb) * t
        L = h * 0.32 * (1 - abs(t - 0.4) * 1.1) + 6
        for sd in (1, -1):
            ex, ey = x0 + sd * L, y - L * 0.35
            _seg(leaf, x0, y, ex, ey, 2.2, 1.0)
            for j in range(4):
                f = (j + 1) / 5
                bx, by = x0 + sd * L * f, y - L * 0.35 * f
                _seg(leaf, bx, by, bx + sd * 7, by - 9, 1.6, 1.0)
                _seg(leaf, bx, by, bx + sd * 2, by - 11, 1.6, 1.0)
    cov = np.maximum(cov, leaf)
    col = np.where(leaf[..., None] > 0, T.hex_rgb("#56743a")[None, None, :] * np.ones_like(col), col)
    # huckleberry leaf: image top-right
    cx, cy = h * 1.5, h * 0.5
    lm = _ellipse_mask(s, s, cx, cy, h * 0.2, h * 0.42, 1.5)
    lm[:, :h] = 0
    lm[h:, :] = 0
    cov = np.maximum(cov, lm)
    vein = np.zeros((s, s), np.float32)
    _seg(vein, cx, cy + h * 0.42, cx, cy - h * 0.42, 2.0, 1.0)
    for k in range(7):
        yv = cy + h * 0.32 - k * h * 0.1
        _seg(vein, cx, yv, cx - h * 0.16, yv - h * 0.08, 1.2, 0.8)
        _seg(vein, cx, yv, cx + h * 0.16, yv - h * 0.08, 1.2, 0.8)
    lc = T.gradient(T.spectral(s, 1.6, seed + 1), [(0.0, "#3e5a22"), (1.0, "#5a7a30")])
    edge = lm * (1 - _ellipse_mask(s, s, cx, cy, h * 0.17, h * 0.38, 2.0))
    lc = T.mix(lc, _fill(s, "#7a3a22"), np.clip(edge, 0, 1) * 0.6)
    lc = T.mix(lc, _fill(s, "#8aa060"), vein * 0.5)
    col = np.where(lm[..., None] > 0.5, lc, col)
    # flower heads: bottom-left (top view) and bottom-right (side view)
    fl = np.zeros((s, s), np.float32)
    ctr = np.zeros((s, s), np.float32)
    for _ in range(70):
        a, d = r.uniform(0, 6.28), r.uniform(0, 1) ** 0.6
        x, y = h * 0.5 + math.cos(a) * d * h * 0.4, h * 1.5 + math.sin(a) * d * h * 0.4
        fl = np.maximum(fl, _ellipse_mask(s, s, x, y, 9, 9, 1.0))
        ctr = np.maximum(ctr, _ellipse_mask(s, s, x, y, 3, 3, 1.0))
    for _ in range(55):
        x = h * 1.5 + r.uniform(-0.42, 0.42) * h
        top = h * 1.35 + (abs(x - h * 1.5) / h) ** 2 * h * 0.5
        y = top + r.uniform(0, 0.12) * h
        fl = np.maximum(fl, _ellipse_mask(s, s, x, y, 9, 7, 1.0))
        ctr = np.maximum(ctr, _ellipse_mask(s, s, x, y, 2.5, 2.5, 1.0))
    st2 = np.zeros((s, s), np.float32)
    for _ in range(12):
        x = h * 1.5 + r.uniform(-0.3, 0.3) * h
        _seg(st2, h * 1.5, s * 0.98, x, h * 1.5, 2.0, 1.0)
    cov = np.maximum(cov, np.maximum(fl, st2))
    fc = T.mix(_fill(s, "#e9e6da"), _fill(s, "#c9b98a"), ctr)
    col = np.where(fl[..., None] > 0.3, fc, col)
    col = np.where((st2[..., None] > 0.3) & (fl[..., None] <= 0.3), T.hex_rgb("#56743a")[None, None, :] * np.ones_like(col), col)
    alpha = (cov > 0.45).astype(np.float32)
    _save(out, col, cov + 0.3 * vein, np.full((s, s), 0.8, np.float32), ns=1.5, alpha=alpha)


# ------------------------------------------------------------------------------------------------
# Salvage roll (inventory mat) layout — 1.4 x 0.9 m, u = (x+0.7)/1.4, v = (y+0.45)/0.9 (Blender XY)
# Keep in sync with generators/item_ui.py (ROLL_* constants).
# ------------------------------------------------------------------------------------------------

ROLL_W, ROLL_D = 1.4, 0.9
ROLL_HEM = 0.03
ROLL_POCKET_Y = (-0.42, -0.17)
ROLL_POCKETS = [0.10, 0.16, 0.20, 0.14, 0.24, 0.18, 0.16, 0.16]
ROLL_FLAP_Y = 0.30


def _weave2(size, nx, ny, seed):
    r = T.rng(seed)
    cx = (np.arange(size, dtype=np.float32) + 0.5) * nx / size
    cy = (np.arange(size, dtype=np.float32) + 0.5) * ny / size
    ix, iy = np.floor(cx).astype(int), np.floor(cy).astype(int)
    fx, fy = cx - ix, cy - iy
    tw = 0.8 + 0.4 * r.random(nx).astype(np.float32)
    tf = 0.8 + 0.4 * r.random(ny).astype(np.float32)
    warp = (np.sin(np.pi * fx) ** 0.7 * tw[ix % nx])[None, :]
    weft = (np.sin(np.pi * fy) ** 0.7 * tf[iy % ny])[:, None]
    over = ((ix[None, :] + iy[:, None]) % 2) == 0
    ay = np.sin(np.pi * fy)[:, None]
    ax = np.sin(np.pi * fx)[None, :]
    hw = warp * np.where(over, 0.65 + 0.35 * ay, 0.3 * (1 - ay))
    hf = weft * np.where(~over, 0.65 + 0.35 * ax, 0.3 * (1 - ax))
    return np.maximum(hw, hf).astype(np.float32)


@texture("item_salvage_roll", size=2048, seed=390)
def item_salvage_roll(size, seed, out):
    """Top face of the unrolled salvage roll: olive duck canvas, doubled hems with twin stitching,
    pocket strip with bound top edge and divider stitching, cover flap seam, broken stencil stripes,
    roll creases, grease and water stains, scuffed edges."""
    s = size

    def X(x):
        return (x + ROLL_W / 2) / ROLL_W * s

    def Y(y):
        return (1.0 - (y + ROLL_D / 2) / ROLL_D) * s
    weave = _weave2(s, 520, 340, seed)
    mott = T.spectral(s, 2.0, seed + 1)
    col = T.gradient(T.normalize(0.7 * mott + 0.3 * weave), [(0.0, "#4b4e2f"), (0.6, "#5a5e38"), (1.0, "#686c43")])
    col *= (0.84 + 0.16 * weave)[..., None]
    height = 0.5 * weave
    stitch = np.zeros((s, s), np.float32)

    def stitch_line(x0, y0, x1, y1, pitch=0.006):
        L = math.hypot(x1 - x0, y1 - y0)
        n = int(L / pitch)
        for i in range(n):
            t0 = (i + 0.15) / n
            t1 = (i + 0.7) / n
            _seg(stitch, X(x0 + (x1 - x0) * t0), Y(y0 + (y1 - y0) * t0), X(x0 + (x1 - x0) * t1), Y(y0 + (y1 - y0) * t1), 2.6, 1.0)
    hw, hd = ROLL_W / 2, ROLL_D / 2
    # doubled hem: slightly darker, two stitch rows
    u, v = _uv(s)
    xm = u * ROLL_W - hw
    ym = (1 - v) * ROLL_D - hd
    edge_d = np.minimum(np.minimum(xm + hw, hw - xm), np.minimum(ym + hd, hd - ym))
    hem = (edge_d < ROLL_HEM).astype(np.float32)
    col *= (1 - 0.1 * hem)[..., None]
    height += 0.15 * hem
    for d in (0.008, 0.024):
        stitch_line(-hw + d, -hd + d, hw - d, -hd + d)
        stitch_line(-hw + d, hd - d, hw - d, hd - d)
        stitch_line(-hw + d, -hd + d, -hw + d, hd - d)
        stitch_line(hw - d, -hd + d, hw - d, hd - d)
    # pocket strip
    py0, py1 = ROLL_POCKET_Y
    pocket = ((ym > py0) & (ym < py1) & (np.abs(xm) < hw - ROLL_HEM)).astype(np.float32)
    col = T.mix(col, col * 0.9, pocket)
    binding = ((ym > py1 - 0.014) & (ym < py1) & (np.abs(xm) < hw - ROLL_HEM)).astype(np.float32)
    col = T.mix(col, _fill(s, "#3e4128") * (0.85 + 0.15 * weave[..., None]), binding)
    stitch_line(-hw + ROLL_HEM, py1 - 0.018, hw - ROLL_HEM, py1 - 0.018)
    stitch_line(-hw + ROLL_HEM, py0 + 0.006, hw - ROLL_HEM, py0 + 0.006)
    x = -hw + ROLL_HEM
    for wdt in ROLL_POCKETS[:-1]:
        x += wdt
        stitch_line(x - 0.003, py0 + 0.004, x - 0.003, py1 - 0.016)
        stitch_line(x + 0.003, py0 + 0.004, x + 0.003, py1 - 0.016)
    # flap seam
    stitch_line(-hw + ROLL_HEM, ROLL_FLAP_Y, hw - ROLL_HEM, ROLL_FLAP_Y)
    stitch_line(-hw + ROLL_HEM, ROLL_FLAP_Y + 0.012, hw - ROLL_HEM, ROLL_FLAP_Y + 0.012)
    flap = (ym > ROLL_FLAP_Y).astype(np.float32)
    col *= (1 + 0.05 * flap)[..., None]
    # stencil stripes (left end), with bridges
    for (xa, xb) in ((-0.63, -0.60), (-0.585, -0.555)):
        m = ((xm > xa) & (xm < xb) & (ym > -0.15) & (ym < 0.27)).astype(np.float32)
        br = (np.abs(((ym + 0.15) / 0.09 % 1.0) - 0.5) > 0.44).astype(np.float32)
        sm = m * (1 - br) * (0.75 + 0.25 * T.levels(T.spectral(s, 1.2, seed + 2), 0.2, 0.8))
        col = T.mix(col, _fill(s, "#cfc6a2"), sm * 0.85)
    # stencil emblem on the flap (ring + chevron, bridged)
    ex, ey = 0.5, 0.375
    d = np.hypot(xm - ex, ym - ey)
    ringm = (np.abs(d - 0.045) < 0.006) & ~(np.abs(xm - ex) < 0.004) & ~(np.abs(ym - ey) < 0.004)
    chev = (np.abs((ym - ey) + 0.012 - np.abs(xm - ex) * 0.7) < 0.007) & (np.abs(xm - ex) < 0.028) & ~(np.abs(xm - ex) < 0.004)
    col[ringm | chev] = col[ringm | chev] * 0.2 + T.hex_rgb("#cfc6a2") * 0.8
    # creases where the roll is folded/rolled
    for cxp in (-0.35, 0.0, 0.35):
        cr = np.exp(-((xm - cxp - 0.01 * np.sin(ym * 20)) / 0.004) ** 2)
        col *= (1 + 0.08 * cr)[..., None]
        height -= 0.25 * cr
    stn = _stains(s, seed + 3, 6, 0.03, 0.08)
    col = T.mix(col, col * 0.62, stn * 0.6)
    tide = _stains(s, seed + 4, 3, 0.04, 0.09, ring=True)
    col = T.mix(col, col * _rgb("#8a8060") / 0.55, tide * 0.25)
    scuff = (1 - T.smoothstep(0.0, 0.05, edge_d)) * T.levels(T.spectral(s, 1.0, seed + 5), 0.3, 0.8)
    col = T.mix(col, _fill(s, "#8c8a6c"), scuff * 0.45)
    col = T.mix(col, _fill(s, "#3a3a26") * (0.9 + 0.1 * weave[..., None]), stitch * 0.85)
    height += 0.35 * stitch
    rough = 0.9 - 0.25 * stn - 0.1 * stitch
    _save(out, col, height, rough, ns=3.0)


@texture("item_river_stone", size=512, seed=375)
def item_river_stone(size, seed, out):
    """Water-worn river stone: smooth mottled grey, fine mineral speckle, faint quartz veins (tile 0.15 m)."""
    mott = T.spectral(size, 2.3, seed)
    mid = T.spectral(size, 1.5, seed + 1)
    speck = T.spectral(size, 0.3, seed + 2)
    vein = 1 - np.abs(2 * T.spectral(size, 1.9, seed + 3) - 1)
    vein = T.smoothstep(0.96, 1.0, vein)
    col = T.gradient(T.normalize(0.65 * mott + 0.35 * mid), [(0.0, "#5f5c57"), (0.5, "#7b7770"), (1.0, "#958f86")])
    col = T.mix(col, _fill(size, "#3a3835"), (speck > 0.8).astype(np.float32) * 0.5)
    col = T.mix(col, _fill(size, "#c9c4b8"), (speck < 0.12).astype(np.float32) * 0.35)
    col = T.mix(col, _fill(size, "#d8d2c6"), vein * 0.7)
    stain = T.levels(T.spectral(size, 1.8, seed + 4), 0.6, 0.95)
    col = T.mix(col, _fill(size, "#6b5a40"), stain * 0.3)
    height = T.normalize(0.5 * mid + 0.3 * speck + 0.2 * vein)
    rough = 0.58 + 0.15 * T.normalize(mid) - 0.1 * vein
    _save(out, col, height, rough, ns=0.8)


@texture("item_bark_twig", size=512, seed=376)
def item_bark_twig(size, seed, out):
    """Young branch / sapling bark: smooth grey-brown skin, fine wrinkles along V, horizontal lenticels,
    a few darker weathered streaks and flaking patches (tile 0.2 m; V runs along the stick)."""
    wr = T.spectral(size, 1.2, seed, anisotropy=(10.0, 1.0))
    streak = T.spectral(size, 1.8, seed + 1, anisotropy=(6.0, 1.0))
    mott = T.spectral(size, 2.2, seed + 2)
    r = T.rng(seed + 3)
    len_cov = np.zeros((size, size), np.float32)
    for _ in range(140):
        x, y = r.uniform(0, size, 2)
        w = r.uniform(5, 14)
        _seg(len_cov, x - w, y, x + w, y, r.uniform(1.6, 2.8), 1.0, wrap=True)
    flake = T.levels(T.spectral(size, 1.4, seed + 4, anisotropy=(3.0, 1.0)), 0.72, 0.85)
    col = T.gradient(T.normalize(0.5 * mott + 0.3 * streak + 0.2 * wr), [(0.0, "#4a3d33"), (0.5, "#66574a"), (1.0, "#857565")])
    col = T.mix(col, _fill(size, "#a59a88"), len_cov * 0.6)
    col = T.mix(col, _fill(size, "#3a2a1e"), flake * 0.55)
    lich = T.levels(T.spectral(size, 1.5, seed + 5), 0.82, 0.92)
    col = T.mix(col, _fill(size, "#8e9479"), lich * 0.4)
    height = T.normalize(0.45 * wr + 0.25 * len_cov - 0.3 * flake + 0.2 * mott)
    _save(out, col, height, 0.82 + 0.1 * flake, ns=3.0)


# ------------------------------------------------------------------------------------------------
# First-person close range (ADR-0029): the stone axe's flint and its rawhide lashing
# ------------------------------------------------------------------------------------------------

@texture("item_flint", size=1024, seed=390_1)
def item_flint(size, seed, out):
    """Knapped flint seen at 40 cm (0.1 m tile): glassy blue-black to smoky brown in clouded zones,
    pale chalky inclusions and specks, the concentric ripple rings of each conchoidal flake scar,
    and a waxy sheen (low roughness) that makes the facets catch the light."""
    mott = T.spectral(size, 2.4, seed)
    cloud = T.warp(T.spectral(size, 2.0, seed + 1), T.spectral(size, 2.0, seed + 2), T.spectral(size, 2.0, seed + 3), size * 0.04)
    col = T.gradient(T.normalize(0.6 * cloud + 0.4 * mott),
                     [(0.0, "#16171a"), (0.35, "#26262a"), (0.6, "#3a332e"), (0.85, "#4e4237"), (1.0, "#5d5044")])
    # chalky inclusions (fossil specks, cortex flecks) and fine light speckle
    f1, _, _ = T.worley(size, 60, seed + 4)
    inc = (1.0 - T.smoothstep(2.0, 9.0, f1)) * T.smoothstep(0.55, 0.8, T.spectral(size, 1.6, seed + 5))
    col = T.mix(col, _fill(size, "#a79d8d"), np.clip(inc, 0, 1) * 0.7)
    speck = (T.spectral(size, 0.25, seed + 6) > 0.9).astype(np.float32)
    col = T.mix(col, _fill(size, "#8a8277"), speck * 0.35)
    # ripple rings of the flake scars (centres scattered; periodic distances)
    r = T.rng(seed + 7)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    rip = np.zeros((size, size), np.float32)
    for _ in range(14):
        cx, cy = r.uniform(0, size, 2)
        dx = (xx - cx + size / 2) % size - size / 2
        dy = (yy - cy + size / 2) % size - size / 2
        d = np.sqrt(dx * dx + dy * dy)
        reach = r.uniform(0.2, 0.45) * size
        rip += np.sin(d / r.uniform(3.5, 7.0) + r.uniform(0, 6.3)) * np.clip(1 - d / reach, 0, 1) ** 1.5
    col *= (0.93 + 0.07 * T.normalize(rip))[..., None]
    height = T.normalize(0.6 * rip + 0.25 * mott + 0.15 * inc)
    rough = np.clip(0.24 + 0.12 * T.normalize(mott) + 0.35 * inc + 0.15 * speck, 0.15, 0.9)
    _save(out, col, height, rough, ns=1.4, ao=0.6)


@texture("item_flint_edge", size=512, seed=390_2)
def item_flint_edge(size, seed, out):
    """The thin knapped edges of flint: translucent, so lighter and warmer (smoky grey-brown), with
    tiny step fractures. The wear layer the edge mask reveals on item_flint."""
    b = T.spectral(size, 1.8, seed)
    col = T.gradient(T.normalize(b), [(0.0, "#4d4640"), (0.5, "#6a5f55"), (1.0, "#857869")])
    steps = T.levels(T.spectral(size, 0.7, seed + 1, anisotropy=(1.0, 4.0)), 0.6, 0.95)
    col = T.mix(col, _fill(size, "#a39484"), steps * 0.4)
    height = T.normalize(0.6 * b + 0.4 * steps)
    _save(out, col, height, np.clip(0.22 + 0.1 * steps, 0.1, 0.6), ns=1.2)


@texture("item_rawhide", size=512, seed=390_3)
def item_rawhide(size, seed, out):
    """Rawhide lashing, wetted, wound on and shrunk dry (u around the strip, v along it): amber to
    bone translucent hide, fibres along the strip, darker where hair roots and grime remain, glossy
    where it pulled taut."""
    fib = T.spectral(size, 1.0, seed, anisotropy=(1.0, 12.0))
    patch = T.spectral(size, 2.2, seed + 1)
    col = T.gradient(T.normalize(0.5 * fib + 0.5 * patch), [(0.0, "#6d4a26"), (0.4, "#8f6a3c"), (0.75, "#b08c5c"), (1.0, "#c6a676")])
    roots = T.levels(T.spectral(size, 0.5, seed + 2), 0.82, 0.97)
    col = T.mix(col, _fill(size, "#3a2716"), roots * 0.45)
    dirt = T.smoothstep(0.55, 0.85, T.spectral(size, 1.8, seed + 3))
    col = T.mix(col, _fill(size, "#3b2a1c"), dirt * 0.35)
    taut = T.smoothstep(0.5, 0.8, T.spectral(size, 2.0, seed + 4, anisotropy=(1.0, 4.0)))
    height = T.normalize(0.55 * fib + 0.25 * patch - 0.2 * roots)
    rough = np.clip(0.62 - 0.3 * taut + 0.15 * dirt, 0.2, 0.95)
    _save(out, col, height, rough, ns=2.2, ao=0.8)
