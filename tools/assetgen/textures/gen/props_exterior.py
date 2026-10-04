"""Exterior props family (streets, yards, survivor camps of an abandoned 1990s logging town).

Tileable PBR sets (albedo / normal / ORM) for vehicles, street furniture, clutter and story props,
plus three non-tiling atlases mapped by planar UV rects:
  * paint_red_sign  — 2x2 atlas: stop octagon clean | blank white sign clean (top row),
                      stop octagon worn | blank white sign worn (bottom row). No text anywhere.
  * paper_trash     — 2x2 atlas: newsprint | ruled notebook | kraft bag | colour flyer (illegible).
  * plywood_marks   — 2x2 atlas: plain | red X | black arrow | tally marks + circle (spray paint).
Neutral, light base colours (car_paint, canvas_tarp, plastic_molded, sleeping_bag_nylon, plastic_bag)
are tinted per material in game/data/materials/props_exterior.json.
Atlas regions in Blender UV space are documented in lib/props_ext_kit.py (ATLAS_*).
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from .. import texlib as T
from ..registry import texture


# --------------------------------------------------------------------------------------------
# Local helpers (tileable unless stated)
# --------------------------------------------------------------------------------------------

def _c(h: str) -> np.ndarray:
    return T.hex_rgb(h)[None, None, :]


def _uv(size: int) -> tuple[np.ndarray, np.ndarray]:
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    return (xx + 0.5) / size, (yy + 0.5) / size


def _hash01(ids: np.ndarray, k: int = 0) -> np.ndarray:
    """Deterministic pseudo-random value in [0, 1) per integer id (vectorised integer hash)."""
    x = (ids.astype(np.int64) * 374761393 + (k + 1) * 668265263) & 0xFFFFFFFF
    x = ((x ^ (x >> 13)) * 1274126177) & 0xFFFFFFFF
    x = x ^ (x >> 16)
    return (x & 0xFFFFFF).astype(np.float32) / float(0x1000000)


def _ridged(size: int, beta: float, seed: int, anisotropy=(1.0, 1.0)) -> np.ndarray:
    n = T.spectral(size, beta, seed, anisotropy=anisotropy)
    return 1.0 - np.abs(n * 2.0 - 1.0)


def _segments(size: int, segs, soft: float = 0.8, wrap: bool = True) -> np.ndarray:
    """Anti-aliased capsule strokes. segs: iterable of (x0, y0, x1, y1, half_width[, value])."""
    m = np.zeros((size, size), np.float32)
    for s in segs:
        x0, y0, x1, y1, w = s[:5]
        val = s[5] if len(s) > 5 else 1.0
        xs = np.arange(int(np.floor(min(x0, x1) - w - 2)), int(np.ceil(max(x0, x1) + w + 2)) + 1)
        ys = np.arange(int(np.floor(min(y0, y1) - w - 2)), int(np.ceil(max(y0, y1) + w + 2)) + 1)
        if not wrap:
            xs = xs[(xs >= 0) & (xs < size)]
            ys = ys[(ys >= 0) & (ys < size)]
            if xs.size == 0 or ys.size == 0:
                continue
        X, Y = np.meshgrid(xs + 0.5, ys + 0.5)
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy + 1e-9
        t = np.clip(((X - x0) * dx + (Y - y0) * dy) / L2, 0.0, 1.0)
        d = np.hypot(X - (x0 + t * dx), Y - (y0 + t * dy))
        a = np.clip((w - d) / soft + 0.5, 0.0, 1.0) * val
        iy, ix = np.mod(ys, size), np.mod(xs, size)
        sub = m[np.ix_(iy, ix)]
        m[np.ix_(iy, ix)] = np.maximum(sub, a)
    return m


def _shapes(w: int, h: int, draw_fn, ss: int = 4) -> np.ndarray:
    """Non-tiling anti-aliased mask: draw_fn(ImageDraw, scale) draws with fill=255 at ss x size."""
    img = Image.new("L", (w * ss, h * ss), 0)
    draw_fn(ImageDraw.Draw(img), ss)
    img = img.resize((w, h), Image.BOX)
    return np.asarray(img, np.float32) / 255.0


def _random_walk_strokes(r: np.random.Generator, n: int, size: int, length: tuple[float, float],
                         width: tuple[float, float], bend: float = 0.25):
    """Slightly curved scratch strokes as short segment chains."""
    segs = []
    for _ in range(n):
        x, y = r.uniform(0, size, 2)
        ang = r.uniform(0, np.pi)
        L = r.uniform(*length)
        w = r.uniform(*width)
        steps = max(2, int(L / 12))
        for _ in range(steps):
            ang += r.normal(0, bend)
            nx, ny = x + np.cos(ang) * L / steps, y + np.sin(ang) * L / steps
            segs.append((x, y, nx, ny, w))
            x, y = nx, ny
    return segs


def _stain_rings(field: np.ndarray, level: float, width: float = 0.012) -> tuple[np.ndarray, np.ndarray]:
    """Water-stain look from a smooth field: (inside mask, tide-mark rim)."""
    inside = T.smoothstep(level - 0.01, level + 0.01, field)
    rim = np.exp(-((field - level) / width) ** 2)
    return inside, rim


def _save(out, albedo, height, rough, *, metal=0.0, normal_strength=4.0, ao_strength=1.0, alpha=None):
    T.save_pbr_set(out, np.clip(albedo, 0, 1), np.clip(height, 0, 1), np.clip(rough, 0, 1), metal=metal,
                   normal_strength=normal_strength, ao_strength=ao_strength, alpha=alpha)


# --------------------------------------------------------------------------------------------
# Vehicles
# --------------------------------------------------------------------------------------------

@texture("car_paint", size=1024, seed=301)
def car_paint(size: int, seed: int, out) -> None:
    """Faded, oxidised single-stage paint (neutral light grey; tinted per material) with chips,
    scratches and grimy rain runs. Pairs with car_rust as the wear layer."""
    r = T.rng(seed)
    broad = T.spectral(size, 2.8, seed)
    mid = T.spectral(size, 1.9, seed + 1)
    fine = T.spectral(size, 0.7, seed + 2)
    runs = T.spectral(size, 1.5, seed + 3, anisotropy=(8.0, 1.0))
    fade = T.smoothstep(0.42, 0.82, 0.65 * broad + 0.35 * mid)
    alb = np.full((size, size, 3), 0.80, np.float32) * (0.94 + 0.10 * (mid[..., None] - 0.5))
    alb = T.mix(alb, _c("#dedbd4") * np.ones_like(alb), fade * 0.5)
    dirt = T.smoothstep(0.58, 0.92, runs) * (0.45 + 0.55 * broad)
    alb = T.mix(alb, _c("#6a6156") * np.ones_like(alb), dirt * 0.38)
    # Small chips down to grey primer / dark bare steel.
    f1, _, cid = T.worley(size, 260, seed + 4)
    rad = 0.8 + 3.2 * _hash01(cid, 1) ** 3
    chip = T.smoothstep(rad + 0.8, rad - 0.8, f1) * (_hash01(cid, 2) > 0.55)
    bare = chip * (_hash01(cid, 3) > 0.6)
    alb = T.mix(alb, _c("#8b8c88") * np.ones_like(alb), chip * 0.9)
    alb = T.mix(alb, _c("#3b3530") * np.ones_like(alb), bare * 0.8)
    scr = _segments(size, _random_walk_strokes(r, 70, size, (20, 110), (0.5, 1.1)))
    alb = T.mix(alb, _c("#efede6") * np.ones_like(alb), scr * 0.35)
    height = 0.55 + 0.06 * fine + 0.04 * mid - 0.25 * chip - 0.1 * scr
    rough = 0.36 + 0.36 * fade + 0.16 * dirt + 0.25 * chip + 0.15 * scr + 0.05 * (fine - 0.5)
    _save(out, alb, height, rough, normal_strength=2.0, ao_strength=0.6)


@texture("car_rust", size=1024, seed=311)
def car_rust(size: int, seed: int, out) -> None:
    """Flaking sheet-steel rust: blistered scale, pitting, orange blooms over dark oxide.
    High-contrast brightness so the std_surface wear threshold breaks up irregularly."""
    b = T.spectral(size, 2.4, seed)
    m = T.spectral(size, 1.6, seed + 1)
    f = T.spectral(size, 0.8, seed + 2)
    f1, f2, cid = T.worley(size, 700, seed + 3)
    wx, wy = T.spectral(size, 2.0, seed + 10), T.spectral(size, 2.0, seed + 11)
    edge = T.warp(T.smoothstep(0.0, 3.0, f2 - f1), wx, wy, 14.0)
    flake = T.warp(_hash01(cid, 5), wx, wy, 14.0)
    scale_mask = T.smoothstep(0.45, 0.7, m)  # flaking only in patches, elsewhere smooth oxide
    t = T.normalize(0.5 * b + 0.3 * m + 0.2 * f)
    col = T.gradient(t, [(0.0, "#1e150f"), (0.3, "#33231a"), (0.55, "#4c3221"), (0.78, "#69432a"), (1.0, "#875a37")])
    col = col * (1.0 + (0.08 * flake - 0.04) * scale_mask)[..., None]
    col = col * (1.0 - 0.12 * (1.0 - edge) * scale_mask)[..., None]
    pf1, _, pid = T.worley(size, 900, seed + 4)
    prad = 0.6 + 1.8 * _hash01(pid, 7) ** 2
    pits = T.smoothstep(prad + 0.6, prad - 0.6, pf1) * (_hash01(pid, 8) > 0.5)
    col = T.mix(col, _c("#140b07") * np.ones_like(col), pits * 0.85)
    bloom = T.smoothstep(0.62, 0.85, T.spectral(size, 1.3, seed + 5))
    col = T.mix(col, _c("#94542c") * np.ones_like(col), bloom * 0.28)
    height = 0.45 * b + 0.25 * flake * edge * scale_mask + 0.2 * f + 0.1 * m - 0.3 * pits
    rough = 0.84 + 0.1 * f - 0.1 * bloom
    metal = 0.15 * T.smoothstep(0.85, 1.0, f) * (1 - pits)
    _save(out, col, T.normalize(height), rough, metal=metal, normal_strength=6.0, ao_strength=1.4)


@texture("tyre_rubber", size=512, seed=321)
def tyre_rubber(size: int, seed: int, out) -> None:
    fine = T.spectral(size, 0.6, seed)
    low = T.spectral(size, 2.2, seed + 1)
    f1, f2, _ = T.worley(size, 400, seed + 2)
    wx, wy = T.spectral(size, 1.8, seed + 10), T.spectral(size, 1.8, seed + 11)
    cracks = T.warp(1.0 - T.smoothstep(0.0, 1.0, f2 - f1), wx, wy, 6.0)
    cracks *= T.smoothstep(0.55, 0.8, T.spectral(size, 1.8, seed + 3))
    alb = _c("#262422") * np.ones((size, size, 3), np.float32) * (0.85 + 0.3 * fine[..., None])
    dust = T.smoothstep(0.55, 0.95, low)
    alb = T.mix(alb, _c("#5f574d") * np.ones_like(alb), dust * 0.45)
    alb = T.mix(alb, _c("#0d0c0b") * np.ones_like(alb), cracks * 0.5)
    height = 0.6 + 0.15 * fine - 0.3 * cracks
    rough = 0.86 + 0.08 * dust
    _save(out, alb, height, rough, normal_strength=3.0)


@texture("chrome_pitted", size=512, seed=331)
def chrome_pitted(size: int, seed: int, out) -> None:
    smudge = T.spectral(size, 1.8, seed)
    fine = T.spectral(size, 0.5, seed + 1)
    f1, _, cid = T.worley(size, 420, seed + 2)
    rad = 0.7 + 2.6 * _hash01(cid, 1) ** 3
    pit = T.smoothstep(rad + 0.7, rad - 0.7, f1) * (_hash01(cid, 2) > 0.45)
    halo = T.smoothstep(rad * 2.6, rad, f1) * (_hash01(cid, 2) > 0.45) * (1 - pit)
    blotch = T.smoothstep(0.66, 0.9, T.spectral(size, 2.0, seed + 3))
    alb = _c("#c6c7c8") * np.ones((size, size, 3), np.float32) * (0.92 - 0.12 * smudge[..., None])
    rust = np.clip(halo * 0.6 + blotch * 0.55, 0, 1)
    alb = T.mix(alb, _c("#7a4a2c") * np.ones_like(alb), rust)
    alb = T.mix(alb, _c("#2a1a10") * np.ones_like(alb), pit)
    rough = 0.2 + 0.22 * smudge + 0.06 * fine + 0.55 * np.maximum(pit, rust)
    metal = np.clip(1.0 - 0.9 * np.maximum(pit, rust), 0, 1)
    height = 0.6 + 0.03 * fine - 0.4 * pit + 0.08 * blotch
    _save(out, alb, height, rough, metal=metal, normal_strength=3.0, ao_strength=0.8)


@texture("window_grime", size=512, seed=341)
def window_grime(size: int, seed: int, out) -> None:
    """Dirty automotive/window glass seen from outside: dark, glossy, dusty film and rain runs."""
    low = T.spectral(size, 2.4, seed)
    mid = T.spectral(size, 1.4, seed + 1)
    runs = T.spectral(size, 1.4, seed + 2, anisotropy=(9.0, 1.0))
    film = T.smoothstep(0.35, 0.85, 0.6 * low + 0.4 * mid)
    streak = T.smoothstep(0.6, 0.9, runs)
    alb = _c("#1b2226") * np.ones((size, size, 3), np.float32) * (0.9 + 0.2 * mid[..., None])
    alb = T.mix(alb, _c("#4d4a43") * np.ones_like(alb), film * 0.45 + streak * 0.12)
    rough = 0.06 + 0.4 * film + 0.12 * streak
    height = 0.5 + 0.08 * film * mid
    _save(out, alb, height, rough, normal_strength=1.0, ao_strength=0.3)


# --------------------------------------------------------------------------------------------
# Clutter
# --------------------------------------------------------------------------------------------

@texture("cardboard", size=512, seed=351)
def cardboard(size: int, seed: int, out) -> None:
    u, v = _uv(size)
    fib = T.spectral(size, 0.9, seed, anisotropy=(1.0, 3.0))
    low = T.spectral(size, 2.3, seed + 1)
    mid = T.spectral(size, 1.5, seed + 2)
    flutes = 0.5 + 0.5 * np.sin(2 * np.pi * v * 64)
    alb = T.gradient(T.normalize(0.55 * fib + 0.45 * mid), [(0.0, "#7c5d3c"), (0.5, "#9c7a52"), (1.0, "#b5946a")])
    stain = T.spectral(size, 1.9, seed + 1, fmin=3.0)
    inside, rim = _stain_rings(stain, 0.78, 0.01)
    alb = alb * (1 - 0.12 * inside[..., None]) * (1 - 0.12 * rim[..., None])
    alb = alb * (0.93 + 0.1 * low[..., None])
    scuff = _segments(size, _random_walk_strokes(T.rng(seed + 3), 14, size, (10, 40), (0.6, 1.2)))
    alb = T.mix(alb, _c("#c7ae86") * np.ones_like(alb), scuff * 0.3)
    height = 0.5 + 0.12 * flutes + 0.2 * fib - 0.05 * rim
    rough = 0.9 - 0.04 * inside
    _save(out, alb, height, rough, normal_strength=1.6)


@texture("plastic_bag", size=512, seed=361)
def plastic_bag(size: int, seed: int, out) -> None:
    """Crinkled polyethylene film (neutral; tinted black / green per material)."""
    c1 = _ridged(size, 1.7, seed, anisotropy=(1.0, 2.5))
    c2 = _ridged(size, 1.6, seed + 1, anisotropy=(3.0, 1.0))
    c3 = _ridged(size, 1.5, seed + 2)
    creases = np.maximum(c1 ** 4, np.maximum(c2 ** 4, c3 ** 5))
    soft = T.spectral(size, 2.2, seed + 3)
    height = 0.35 * soft + 0.55 * creases + 0.1 * T.spectral(size, 1.0, seed + 4)
    alb = np.ones((size, size, 3), np.float32) * (0.5 + 0.08 * soft[..., None] + 0.16 * creases[..., None])
    dust = T.smoothstep(0.6, 0.95, T.spectral(size, 1.7, seed + 5))
    alb = T.mix(alb, _c("#b9b2a5") * np.ones_like(alb), dust * 0.3)
    rough = 0.3 + 0.15 * (1 - creases) + 0.35 * dust
    _save(out, alb, T.normalize(height), rough, normal_strength=9.0, ao_strength=0.5)


@texture("canvas_tarp", size=512, seed=371)
def canvas_tarp(size: int, seed: int, out) -> None:
    """Woven canvas / cotton duck (neutral; tinted per material). Also used for clothes, bags."""
    u, v = _uv(size)
    n = 96
    jit = T.spectral(size, 1.6, seed) - 0.5
    wu = np.sin(2 * np.pi * (u * n + jit * 0.6))
    wv = np.sin(2 * np.pi * (v * n + jit * 0.6))
    weave = 0.5 + 0.5 * wu * wv
    threads = 0.5 + 0.25 * (np.abs(wu) + np.abs(wv))
    mott = T.spectral(size, 2.1, seed + 1)
    slub = T.spectral(size, 1.0, seed + 2, anisotropy=(1.0, 12.0))
    alb = np.ones((size, size, 3), np.float32) * 0.72
    alb = alb * (0.88 + 0.14 * threads[..., None] + 0.08 * (slub[..., None] - 0.5))
    dirt = T.smoothstep(0.5, 0.95, mott)
    alb = T.mix(alb, _c("#5d5446") * np.ones_like(alb), dirt * 0.35)
    height = 0.6 * weave + 0.25 * threads + 0.15 * slub
    rough = 0.86 + 0.08 * dirt
    _save(out, alb, T.normalize(height), rough, normal_strength=2.5)


@texture("sleeping_bag_nylon", size=512, seed=381)
def sleeping_bag_nylon(size: int, seed: int, out) -> None:
    """Ripstop nylon shell: fine weave + reinforcement grid, soft sheen, wrinkles."""
    u, v = _uv(size)
    fine = 0.5 + 0.5 * np.sin(2 * np.pi * u * 170) * np.sin(2 * np.pi * v * 170)
    gu = np.abs(((u * 22) % 1.0) - 0.5)
    gv = np.abs(((v * 22) % 1.0) - 0.5)
    grid = np.maximum(T.smoothstep(0.43, 0.49, gu), T.smoothstep(0.43, 0.49, gv))
    wr = _ridged(size, 2.0, seed, anisotropy=(1.0, 2.0)) ** 3
    low = T.spectral(size, 2.2, seed + 1)
    alb = np.ones((size, size, 3), np.float32) * (0.74 + 0.06 * low[..., None] - 0.05 * grid[..., None])
    dirt = T.smoothstep(0.6, 0.95, T.spectral(size, 1.6, seed + 2))
    alb = T.mix(alb, _c("#4d473d") * np.ones_like(alb), dirt * 0.4)
    height = 0.35 * wr + 0.15 * fine + 0.2 * grid + 0.3 * low
    rough = 0.42 + 0.1 * (1 - wr) + 0.3 * dirt
    _save(out, alb, T.normalize(height), rough, normal_strength=3.0)


@texture("plastic_molded", size=512, seed=391)
def plastic_molded(size: int, seed: int, out) -> None:
    """Injection-moulded / blow-moulded plastic: fine stipple, scuffs, grime (neutral, tinted)."""
    r = T.rng(seed)
    stip = T.spectral(size, 0.35, seed)
    low = T.spectral(size, 2.0, seed + 1)
    scuff = _segments(size, _random_walk_strokes(r, 55, size, (15, 80), (0.6, 1.6)))
    alb = np.ones((size, size, 3), np.float32) * (0.78 + 0.05 * low[..., None])
    grime = T.smoothstep(0.55, 0.95, T.spectral(size, 1.5, seed + 2))
    alb = T.mix(alb, _c("#4a4439") * np.ones_like(alb), grime * 0.35)
    alb = T.mix(alb, _c("#d9d6cf") * np.ones_like(alb), scuff * 0.3)
    height = 0.55 + 0.08 * stip - 0.15 * scuff
    rough = 0.48 + 0.08 * stip + 0.25 * grime + 0.15 * scuff
    _save(out, alb, height, rough, normal_strength=1.5, ao_strength=0.5)


@texture("mattress_ticking", size=512, seed=397)
def mattress_ticking(size: int, seed: int, out) -> None:
    """Quilted mattress cover: diamond stitch quilting, faint woven stripes, tide-marked stains."""
    u, v = _uv(size)
    q = 4
    d1 = np.abs(((u + v) * q) % 1.0 - 0.5)
    d2 = np.abs(((u - v) * q) % 1.0 - 0.5)
    stitch = np.maximum(T.smoothstep(0.47, 0.5, d1), T.smoothstep(0.47, 0.5, d2))
    puff = (np.minimum(0.5 - d1, 0.5 - d2) * 2.0) ** 0.5
    stripes = 0.5 + 0.5 * np.sin(2 * np.pi * u * 16)
    alb = _c("#d6d1c4") * np.ones((size, size, 3), np.float32)
    alb = T.mix(alb, _c("#9fb0b8") * np.ones_like(alb), T.smoothstep(0.75, 0.95, stripes)[..., None] * 0.35)
    alb = alb * (1 - 0.25 * stitch[..., None])
    low = T.spectral(size, 1.9, seed)
    inside, rim = _stain_rings(low, 0.7, 0.01)
    inside2, rim2 = _stain_rings(T.spectral(size, 1.7, seed + 1), 0.76, 0.008)
    stain = np.clip(inside * 0.5 + inside2 * 0.4, 0, 1) * (0.7 + 0.3 * low)
    alb = T.mix(alb, _c("#ab9563") * np.ones_like(alb), stain * 0.45)
    alb = alb * (1 - 0.18 * np.clip(rim + rim2, 0, 1)[..., None])
    dirt = T.smoothstep(0.55, 0.95, T.spectral(size, 1.4, seed + 2))
    alb = T.mix(alb, _c("#5e5547") * np.ones_like(alb), dirt * 0.3)
    height = 0.7 * puff - 0.3 * stitch + 0.05 * T.spectral(size, 0.6, seed + 3)
    rough = 0.85 + 0.05 * dirt
    _save(out, alb, T.normalize(height), rough, normal_strength=4.0)


@texture("paper_trash", size=512, seed=401)
def paper_trash(size: int, seed: int, out) -> None:
    """2x2 atlas (256 px cells): newsprint | ruled notebook / kraft bag | colour flyer.
    Text is suggested only by grey bars and pencil squiggles — nothing legible."""
    r = T.rng(seed)
    h = size // 2
    alb = np.zeros((size, size, 3), np.float32)
    crumple = T.normalize(0.6 * _ridged(size, 1.4, seed) ** 3 + 0.4 * T.spectral(size, 2.0, seed + 1))
    yy, xx = np.mgrid[0:h, 0:h].astype(np.float32)
    # Newsprint: columns of grey bars + a halftone photo block.
    news = np.ones((h, h, 3), np.float32) * T.hex_rgb("#c9c2ad")
    bars = np.zeros((h, h), np.float32)
    for col in range(3):
        x0 = 14 + col * 78
        for row in range(26):
            y0 = 16 + row * 8.5
            if 120 < y0 < 175 and col == 1:
                continue
            ln = r.uniform(0.55, 1.0) * 66
            bars[int(y0):int(y0) + 3, int(x0):int(x0 + ln)] = r.uniform(0.55, 0.85)
    bars[120:175, 95:160] = 0.45 + 0.25 * (np.sin(xx[120:175, 95:160] * 1.7) * np.sin(yy[120:175, 95:160] * 1.7) > 0)
    news = news * (1 - 0.6 * bars[..., None])
    # Notebook: ruled lines, margin, pencil squiggles.
    note = np.ones((h, h, 3), np.float32) * T.hex_rgb("#dcd9cf")
    for k in range(10, h, 11):
        note[k:k + 1, :, :] = note[k:k + 1, :, :] * 0.7 + T.hex_rgb("#7d9bb8") * 0.3
    note[:, 34:35, :] = note[:, 34:35, :] * 0.5 + T.hex_rgb("#c0504a") * 0.5
    sq = []
    for row in range(4, 18):
        x = 40.0
        y = row * 11 + 7.5
        while x < r.uniform(150, 240):
            nx = x + r.uniform(3, 7)
            sq.append((x, y + r.uniform(-2.5, 2.5), nx, y + r.uniform(-2.5, 2.5), 0.55))
            x = nx
    note = note * (1 - 0.45 * _segments(h, sq, wrap=False)[..., None])
    # Kraft paper bag.
    kraft = T.gradient(T.normalize(T.spectral(h, 1.0, seed + 2, anisotropy=(1, 3))), [(0, "#8d6a43"), (1, "#b08b5e")])
    # Flyer: faded colour blocks and grey bars.
    fly = np.ones((h, h, 3), np.float32) * T.hex_rgb("#d8d2c2")
    fly[20:110, 20:236] = T.hex_rgb("#b0574a")
    fly[125:200, 20:120] = T.hex_rgb("#4f6f93")
    for row in range(8):
        y0 = 128 + row * 10
        fly[y0:y0 + 4, 135:int(135 + r.uniform(50, 100))] *= 0.55
    fly[212:240, 20:236] = T.hex_rgb("#d6b24a")
    alb[:h, :h] = news
    alb[:h, h:] = note
    alb[h:, :h] = kraft
    alb[h:, h:] = fly
    low = T.spectral(size, 2.2, seed + 3)
    inside, rim = _stain_rings(low, 0.64)
    yel = T.smoothstep(0.3, 0.9, T.spectral(size, 2.6, seed + 4))
    alb = alb * (1 - 0.12 * yel[..., None]) + _c("#8a6d32") * (0.12 * yel[..., None])
    alb = alb * (1 - 0.15 * inside[..., None]) * (1 - 0.3 * rim[..., None])
    alb = alb * (0.86 + 0.14 * crumple[..., None])
    glossy = ((np.arange(size)[None, :] >= h) & (np.arange(size)[:, None] >= h)).astype(np.float32)
    rough = 0.88 - 0.25 * glossy + 0.0 * crumple
    _save(out, alb, crumple, rough, normal_strength=5.0, ao_strength=0.8)


# --------------------------------------------------------------------------------------------
# Wood, metal, concrete
# --------------------------------------------------------------------------------------------

@texture("wood_weathered", size=1024, seed=411)
def wood_weathered(size: int, seed: int, out) -> None:
    """Sun-silvered softwood (fence boards, pallets, poles). Grain runs along U (image x):
    dark latewood lines on a gently wandering coordinate, raised grain, checks and knots."""
    r = T.rng(seed)
    u, v = _uv(size)
    low = T.spectral(size, 2.4, seed, anisotropy=(1.0, 3.0))
    wander = T.spectral(size, 2.6, seed + 1, anisotropy=(1.0, 4.0))
    fibre = T.spectral(size, 0.9, seed + 2, anisotropy=(1.0, 30.0))
    f1, _, cid = T.worley(size, 6, seed + 5)
    kr = 9 + 12 * _hash01(cid, 3)
    has_knot = (_hash01(cid, 4) > 0.4).astype(np.float32)
    knot = np.exp(-(f1 / kr) ** 2) * has_knot
    swirl = np.exp(-(f1 / (kr * 3.5)) ** 2) * has_knot
    g = v * 52.0 + 3.2 * (wander - 0.5) + 0.45 * (fibre - 0.5) + 2.2 * swirl
    p = g - np.floor(g)
    strength = 0.55 + 0.45 * T.spectral(size, 1.6, seed + 3, anisotropy=(1.0, 8.0))
    late = (T.smoothstep(0.0, 0.05, p) * (1.0 - T.smoothstep(0.12, 0.3, p))) * strength
    checks = _segments(size, [(x, y, x + L, y + r.normal(0, 1.2), w)
                              for x, y, L, w in zip(r.uniform(0, size, 70), r.uniform(0, size, 70),
                                                    r.uniform(25, 170, 70), r.uniform(0.4, 1.0, 70))], soft=0.7)
    t = T.normalize(0.6 * low + 0.4 * fibre)
    alb = T.gradient(t, [(0.0, "#625c52"), (0.45, "#7f796d"), (0.8, "#9a9385"), (1.0, "#ada698")])
    brown = T.smoothstep(0.5, 0.9, T.spectral(size, 2.0, seed + 6)) * (1 - late)
    alb = T.mix(alb, _c("#7a6248") * np.ones_like(alb), brown * 0.35)
    alb = T.mix(alb, _c("#4a4239") * np.ones_like(alb), late[..., None] * 0.42)
    alb = alb * (0.92 + 0.12 * (fibre[..., None] - 0.5))
    alb = T.mix(alb, _c("#352c24") * np.ones_like(alb), np.clip(knot * 0.85, 0, 1))
    alb = T.mix(alb, _c("#2a241d") * np.ones_like(alb), checks * 0.6)
    height = 0.5 + 0.25 * late + 0.12 * fibre + 0.1 * low - 0.55 * checks + 0.1 * knot
    rough = 0.84 + 0.08 * (1 - late) + 0.05 * checks
    _save(out, alb, height, rough, normal_strength=6.0, ao_strength=1.2)


@texture("metal_galvanized", size=512, seed=421)
def metal_galvanized(size: int, seed: int, out) -> None:
    """Hot-dip galvanised steel: spangle crystals, white-rust bloom, grime."""
    f1, f2, cid = T.worley(size, 420, seed)
    cell = _hash01(cid, 1)
    edge = T.smoothstep(0.0, 1.5, f2 - f1)
    fine = T.spectral(size, 0.7, seed + 1)
    white = T.smoothstep(0.68, 0.88, T.spectral(size, 1.6, seed + 2, fmin=3.0)) * (0.6 + 0.4 * fine)
    grime = T.smoothstep(0.55, 0.92, T.spectral(size, 1.7, seed + 3, fmin=2.0))
    alb = _c("#a6a9a8") * np.ones((size, size, 3), np.float32) * (0.86 + 0.14 * cell[..., None])
    alb = alb * (0.92 + 0.08 * edge[..., None])
    alb = T.mix(alb, _c("#cfccc4") * np.ones_like(alb), white * 0.45)
    alb = T.mix(alb, _c("#4b4740") * np.ones_like(alb), grime * 0.32)
    rough = 0.34 + 0.18 * cell + 0.45 * white + 0.25 * grime + 0.05 * fine
    metal = np.clip(0.9 - 0.75 * white - 0.4 * grime, 0, 1)
    height = 0.5 + 0.06 * cell + 0.05 * fine + 0.15 * white
    _save(out, alb, height, rough, metal=metal, normal_strength=1.5, ao_strength=0.6)


@texture("chainlink", size=512, seed=431, kind="pbr_alpha")
def chainlink(size: int, seed: int, out) -> None:
    """Chain-link fence fabric (alpha cut-out). 10 diamonds across the tile; map 1 tile = 0.5 m."""
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    xx += 0.5
    yy += 0.5
    s = size / 10.0
    a = (xx + yy) / s
    b = (xx - yy) / s
    da = np.abs(a - np.round(a)) * s / np.sqrt(2.0)
    db = np.abs(b - np.round(b)) * s / np.sqrt(2.0)
    rad = 3.0
    # Wires bow slightly between knuckles (zig-zag weave).
    wob = 0.6 * np.sin(np.pi * (b - np.floor(b)))
    wob2 = 0.6 * np.sin(np.pi * (a - np.floor(a)))
    d = np.minimum(np.abs(da - wob * 0.0), np.abs(db - wob2 * 0.0))
    alpha = np.clip((rad - d) / 1.0 + 0.5, 0.0, 1.0)
    h = np.sqrt(np.clip(1.0 - (d / rad) ** 2, 0.0, 1.0))
    # Knuckle bumps at intersections.
    knot = np.exp(-((da / 3.5) ** 2 + (db / 3.5) ** 2))
    h = np.clip(h + 0.4 * knot, 0, 1)
    rust = T.smoothstep(0.6, 0.9, T.spectral(size, 1.6, seed))
    alb = _c("#9fa2a1") * np.ones((size, size, 3), np.float32) * (0.75 + 0.35 * h[..., None])
    alb = T.mix(alb, _c("#7b4a2a") * np.ones_like(alb), rust * 0.6)
    rough = 0.45 + 0.4 * rust
    metal = 0.8 * (1 - rust)
    _save(out, alb, h, rough, metal=metal, normal_strength=3.0, ao_strength=0.3, alpha=alpha)


@texture("concrete_barrier", size=1024, seed=441)
def concrete_barrier(size: int, seed: int, out) -> None:
    """Precast highway concrete: aggregate, bug-holes, form lines, rain stains."""
    u, v = _uv(size)
    low = T.spectral(size, 2.4, seed)
    mid = T.spectral(size, 1.5, seed + 1)
    agg = T.spectral(size, 0.3, seed + 2)
    f1, _, cid = T.worley(size, 1600, seed + 3)
    rad = 0.6 + 2.6 * _hash01(cid, 1) ** 3
    holes = T.smoothstep(rad + 0.7, rad - 0.7, f1) * (_hash01(cid, 2) > 0.55)
    runs = T.smoothstep(0.55, 0.9, T.spectral(size, 1.4, seed + 4, anisotropy=(9.0, 1.0)))
    form = T.smoothstep(0.985, 1.0, 0.5 + 0.5 * np.cos(2 * np.pi * v * 3))
    alb = T.gradient(T.normalize(0.5 * low + 0.5 * mid), [(0, "#7f7d77"), (0.5, "#99968f"), (1, "#aeaba3")])
    alb = alb * (0.92 + 0.12 * agg[..., None])
    alb = T.mix(alb, _c("#5d5a52") * np.ones_like(alb), runs * 0.35)
    alb = T.mix(alb, _c("#3c3a36") * np.ones_like(alb), holes * 0.8)
    alb = alb * (1 - 0.12 * form[..., None])
    height = 0.55 + 0.1 * mid + 0.08 * agg - 0.45 * holes - 0.1 * form
    rough = 0.88 + 0.06 * agg
    _save(out, alb, height, rough, normal_strength=3.0, ao_strength=1.2)


@texture("plywood_marks", size=1024, seed=451)
def plywood_marks(size: int, seed: int, out) -> None:
    """2x2 atlas (512 px cells) of weathered exterior plywood: plain | red X / black arrow |
    tally marks + circle — crude spray-painted survivor marks, never words."""
    r = T.rng(seed)
    h = size // 2
    u, v = _uv(size)
    warp = T.spectral(size, 2.0, seed)
    band = T.spectral(size, 1.2, seed + 1, anisotropy=(1.0, 5.0))
    fig = 0.5 + 0.5 * np.sin(2 * np.pi * (v * 9 + warp * 2.5 + band * 0.6))
    t = T.normalize(0.5 * fig + 0.5 * band)
    alb = T.gradient(t, [(0, "#7d6a4f"), (0.5, "#a08661"), (1, "#b79d75")])
    grey = T.smoothstep(0.35, 0.8, T.spectral(size, 2.2, seed + 2))
    alb = T.mix(alb, _c("#8d877b") * np.ones_like(alb), grey * 0.55)
    # Water stains creeping up from the bottom edge of every cell.
    yy = (np.arange(size)[:, None] % h) / h
    edge = T.smoothstep(0.7, 1.0, yy + 0.15 * (T.spectral(size, 1.8, seed + 3) - 0.5)) * np.ones((1, size))
    alb = T.mix(alb, _c("#4e4335") * np.ones_like(alb), edge * 0.6)
    paint = np.zeros((size, size), np.float32)
    pcol = np.zeros((size, size, 3), np.float32)

    def spray(cx, cy, strokes, colour, width):
        segs = []
        drips = []
        for (x0, y0, x1, y1) in strokes:
            n = 10
            for k in range(n):
                ta, tb = k / n, (k + 1) / n
                jx, jy = r.normal(0, 2.0, 2)
                segs.append((cx + x0 + (x1 - x0) * ta + jx, cy + y0 + (y1 - y0) * ta + jy,
                             cx + x0 + (x1 - x0) * tb + jx, cy + y0 + (y1 - y0) * tb + jy, width * r.uniform(0.85, 1.1)))
            for _ in range(r.integers(1, 4)):
                tt = r.uniform(0, 1)
                px, py = cx + x0 + (x1 - x0) * tt, cy + y0 + (y1 - y0) * tt
                L = r.uniform(15, 70)
                drips.append((px, py, px + r.normal(0, 1.0), py + L, r.uniform(1.6, 3.0)))
        m = _segments(size, segs, soft=3.0, wrap=False)
        m = np.maximum(m, _segments(size, drips, soft=1.2, wrap=False))
        over = np.zeros_like(m)
        for (x0, y0, x1, y1) in strokes:
            for _ in range(160):
                tt = r.uniform(0, 1)
                px = cx + x0 + (x1 - x0) * tt + r.normal(0, width * 1.6)
                py = cy + y0 + (y1 - y0) * tt + r.normal(0, width * 1.6)
                over = np.maximum(over, _segments(size, [(px, py, px, py, r.uniform(0.6, 1.5))], soft=0.8, wrap=False))
        m = np.clip(np.maximum(m, over * 0.75), 0, 1)
        m = m * (0.75 + 0.25 * T.spectral(size, 1.0, int(cx + cy)))
        upd = m > paint
        pcol[upd] = colour
        np.maximum(paint, m, out=paint)

    red = T.hex_rgb("#8e1f17")
    black = T.hex_rgb("#141312")
    # Cell (1,0) top-right: big red X.
    spray(h + h / 2, h / 2, [(-170, -170, 170, 170), (170, -170, -170, 170)], red, 22)
    # Cell (0,1) bottom-left: black arrow pointing right.
    spray(h / 2, h + h / 2, [(-180, 0, 150, 0), (150, 0, 60, -95), (150, 0, 60, 95)], black, 20)
    # Cell (1,1) bottom-right: tally marks + circle with a slash (black / red).
    marks = [(-150 + k * 38, -60, -150 + k * 38 + r.uniform(-8, 8), 70) for k in range(4)]
    marks.append((-175, 40, 5, -30))
    spray(h + h / 2, h + h / 2 - 60, marks, black, 12)
    circ = []
    for k in range(18):
        a0, a1 = 2 * np.pi * k / 18, 2 * np.pi * (k + 1) / 18
        circ.append((np.cos(a0) * 85, np.sin(a0) * 85, np.cos(a1) * 85, np.sin(a1) * 85))
    circ.append((-60, 60, 60, -60))
    spray(h + h / 2 + 90, h + h / 2 + 120, circ, red, 11)
    fadeN = T.spectral(size, 1.3, seed + 9)
    paint = paint * (0.7 + 0.3 * fadeN) * (1 - 0.5 * T.smoothstep(0.7, 0.95, T.spectral(size, 0.8, seed + 10)))
    alb = T.mix(alb, pcol, paint[..., None] * 0.95)
    height = 0.5 + 0.25 * fig * (1 - paint) + 0.1 * band - 0.1 * edge
    rough = 0.9 - 0.25 * paint
    _save(out, alb, height, rough, normal_strength=3.0)


@texture("paint_red_sign", size=1024, seed=461)
def paint_red_sign(size: int, seed: int, out) -> None:
    """2x2 atlas of sign faces (512 px cells; no text): top-left stop octagon (clean),
    top-right blank white regulatory sign (clean), bottom row = the same two faces worn
    (faded, scratched, rust streaks, bullet holes)."""
    r = T.rng(seed)
    h = size // 2
    m = 6.0
    # Octagon geometry (flat top) inside a cell.
    def octagon(ox, oy, inset):
        rad = (h / 2 - m - inset) / np.cos(np.pi / 8)
        return [(ox + h / 2 + rad * np.cos(np.pi / 8 + k * np.pi / 4), oy + h / 2 + rad * np.sin(np.pi / 8 + k * np.pi / 4)) for k in range(8)]

    def mk(draw_list):
        def fn(d, ss):
            for poly, val in draw_list:
                d.polygon([(x * ss, y * ss) for x, y in poly], fill=int(val * 255))
        return fn

    alb = np.zeros((size, size, 3), np.float32)
    alb[:] = T.hex_rgb("#a9aba9")
    red = T.hex_rgb("#a3241c")
    white = T.hex_rgb("#e6e4dc")
    black = T.hex_rgb("#171717")
    for row in (0, 1):
        oy = row * h
        outer = _shapes(size, size, mk([(octagon(0, oy, 0), 1.0)]))
        band = _shapes(size, size, mk([(octagon(0, oy, 6), 1.0)]))
        inner = _shapes(size, size, mk([(octagon(0, oy, 24), 1.0)]))
        col = T.mix(alb, red * np.ones_like(alb), outer[..., None])
        col = T.mix(col, white * np.ones_like(alb), band[..., None])
        col = T.mix(col, red * np.ones_like(alb), inner[..., None])
        sel = np.zeros((size, size, 1), np.float32)
        sel[oy:oy + h, :h] = 1
        alb = alb * (1 - sel) + col * sel
        # Blank white regulatory sign (portrait 0.8 aspect) with black border.
        w2, h2 = 400, 500
        x0, y0 = h + (h - w2) / 2, oy + (h - h2) / 2

        def rect(inset):
            return [(x0 + inset, y0 + inset), (x0 + w2 - inset, y0 + inset), (x0 + w2 - inset, y0 + h2 - inset), (x0 + inset, y0 + h2 - inset)]
        o2 = _shapes(size, size, mk([(rect(0), 1.0)]))
        b2 = _shapes(size, size, mk([(rect(9), 1.0)]))
        i2 = _shapes(size, size, mk([(rect(19), 1.0)]))
        col = T.mix(alb, white * np.ones_like(alb), o2[..., None])
        col = T.mix(col, black * np.ones_like(alb), b2[..., None])
        col = T.mix(col, white * np.ones_like(alb), i2[..., None])
        sel = np.zeros((size, size, 1), np.float32)
        sel[oy:oy + h, h:] = 1
        alb = alb * (1 - sel) + col * sel
    low = T.spectral(size, 2.3, seed)
    fine = T.spectral(size, 0.8, seed + 1)
    dirt = T.smoothstep(0.5, 0.95, low) * 0.25
    worn = np.zeros((size, size), np.float32)
    worn[h:, :] = 1.0
    # Worn row: sun-faded (red -> salmon), scratches, rust runs, bullet holes.
    fade = worn * (0.35 + 0.35 * T.spectral(size, 1.8, seed + 2))
    lum = alb.mean(-1, keepdims=True)
    alb = T.mix(alb, (alb * 0.6 + lum * 0.4 + 0.12), fade[..., None])
    scr = _segments(size, [s for s in _random_walk_strokes(r, 90, size, (20, 120), (0.5, 1.2)) if s[1] > h + 4 and s[3] > h + 4])
    alb = T.mix(alb, _c("#b9bbb8") * np.ones_like(alb), scr * 0.7)
    runs = T.smoothstep(0.62, 0.92, T.spectral(size, 1.5, seed + 3, anisotropy=(10.0, 1.0))) * worn
    alb = T.mix(alb, _c("#6b3a1e") * np.ones_like(alb), runs * 0.45)
    holes = []
    rings = []
    for cx0 in (h / 2, h + h / 2):
        for _ in range(int(r.integers(3, 7))):
            cx, cy = cx0 + r.uniform(-170, 170), h + h / 2 + r.uniform(-170, 170)
            rr = r.uniform(4, 7)
            holes.append((cx, cy, cx, cy, rr))
            rings.append((cx, cy, cx, cy, rr * r.uniform(2.0, 3.0)))
    ring = _segments(size, rings, soft=2.0)
    hole = _segments(size, holes, soft=1.0)
    alb = T.mix(alb, _c("#c8cac8") * np.ones_like(alb), ring * 0.85)
    alb = T.mix(alb, _c("#0b0a09") * np.ones_like(alb), hole)
    alb = T.mix(alb, _c("#4d473c") * np.ones_like(alb), dirt[..., None] * (0.4 + worn[..., None]))
    alb = alb * (0.96 + 0.06 * fine[..., None])
    height = 0.6 + 0.04 * fine - 0.5 * hole + 0.15 * ring - 0.08 * scr
    rough = 0.42 + 0.3 * worn + 0.2 * dirt + 0.2 * scr
    metal = 0.5 * ring + 0.0 * hole
    _save(out, alb, height, rough, metal=metal, normal_strength=3.0, ao_strength=0.8)


# --------------------------------------------------------------------------------------------
# Story props
# --------------------------------------------------------------------------------------------

@texture("corpse", size=1024, seed=471)
def corpse(size: int, seed: int, out) -> None:
    """Long-dead, desiccated skin: leathery, mottled grey-brown with dark livor patches."""
    low = T.spectral(size, 2.5, seed)
    mid = T.spectral(size, 1.7, seed + 1)
    fine = T.spectral(size, 0.9, seed + 2)
    t = T.normalize(0.5 * low + 0.35 * mid + 0.15 * fine)
    alb = T.gradient(t, [(0.0, "#2c241e"), (0.3, "#4a3d2f"), (0.6, "#6a5c45"), (0.85, "#7c7458"), (1.0, "#8d8768")])
    dark = T.smoothstep(0.6, 0.85, T.spectral(size, 2.2, seed + 3))
    alb = T.mix(alb, _c("#2a1d20") * np.ones_like(alb), dark * 0.6)
    w1 = _ridged(size, 1.2, seed + 4, anisotropy=(1.0, 3.0)) ** 4
    w2 = _ridged(size, 1.0, seed + 5, anisotropy=(3.0, 1.0)) ** 4
    wr = np.maximum(w1, w2)
    f1, f2, _ = T.worley(size, 260, seed + 6)
    crack = 1.0 - T.smoothstep(0.0, 1.8, f2 - f1)
    crack *= T.smoothstep(0.5, 0.8, low)
    alb = alb * (0.9 + 0.15 * wr[..., None]) * (1 - 0.4 * crack[..., None])
    height = 0.35 * wr + 0.3 * mid + 0.2 * fine - 0.3 * crack
    rough = 0.62 + 0.18 * (1 - t) + 0.1 * crack
    _save(out, alb, T.normalize(height), rough, normal_strength=4.5, ao_strength=1.3)


@texture("blood_dried", size=512, seed=481)
def blood_dried(size: int, seed: int, out) -> None:
    """Dried blood: crusted and cracked where thick, brown and matte where thin.
    Used as a full surface (pools) and as the wear layer that stains cloth via vertex G."""
    t = T.normalize(0.7 * T.spectral(size, 2.0, seed) + 0.3 * T.spectral(size, 1.0, seed + 1))
    f1, f2, _ = T.worley(size, 180, seed + 2)
    crack = (1.0 - T.smoothstep(0.0, 1.5, f2 - f1)) * T.smoothstep(0.55, 0.8, t)
    alb = T.gradient(t, [(0.0, "#5a2a1a"), (0.45, "#4a1310"), (0.8, "#2c0807"), (1.0, "#1a0404")])
    alb = alb * (1 - 0.5 * crack[..., None])
    rough = 0.72 - 0.42 * T.smoothstep(0.5, 0.9, t) + 0.3 * crack
    height = 0.5 * t - 0.3 * crack + 0.1 * T.spectral(size, 0.6, seed + 3)
    _save(out, alb, T.normalize(height), rough, normal_strength=3.0)


@texture("ash_burnt", size=1024, seed=491)
def ash_burnt(size: int, seed: int, out) -> None:
    """Burnt-out surfaces: alligatored char, soot, grey-white ash drifts, heat-rust blotches."""
    f1, f2, cid = T.worley(size, 900, seed)
    wx, wy = T.spectral(size, 2.0, seed + 10), T.spectral(size, 2.0, seed + 11)
    edge = T.warp(T.smoothstep(0.0, 3.0, f2 - f1), wx, wy, 10.0)
    cell = T.warp(_hash01(cid, 2), wx, wy, 10.0)
    low = T.spectral(size, 2.0, seed + 1)
    fine = T.spectral(size, 0.8, seed + 2)
    char_mask = T.smoothstep(0.35, 0.6, T.spectral(size, 1.8, seed + 4))
    edge = 1.0 - (1.0 - edge) * char_mask
    ash = T.smoothstep(0.6, 0.85, low) * (0.5 + 0.5 * T.smoothstep(0.3, 0.7, fine))
    rust = T.smoothstep(0.68, 0.9, T.spectral(size, 1.9, seed + 3))
    alb = _c("#151312") * np.ones((size, size, 3), np.float32) * (0.75 + 0.6 * cell[..., None] * edge[..., None])
    alb = alb * (0.4 + 0.6 * edge[..., None])
    alb = T.mix(alb, _c("#5a2c18") * np.ones_like(alb), rust * 0.6)
    alb = T.mix(alb, _c("#8c8780") * np.ones_like(alb), ash * (0.55 + 0.35 * fine))
    height = 0.45 * edge * (0.6 + 0.4 * cell) + 0.3 * ash + 0.15 * fine
    rough = 0.9 + 0.08 * ash
    _save(out, alb, T.normalize(height), rough, normal_strength=5.0, ao_strength=1.4)


@texture("plaid_flannel", size=512, seed=501)
def plaid_flannel(size: int, seed: int, out) -> None:
    """Worn red/black buffalo-check flannel (the logging-town work shirt). 4 checks per tile."""
    u, v = _uv(size)
    sx = ((u * 4) % 1.0) < 0.5
    sy = ((v * 4) % 1.0) < 0.5
    both = (sx & sy).astype(np.float32)
    one = (sx ^ sy).astype(np.float32)
    red = T.hex_rgb("#7d211b")
    blk = T.hex_rgb("#191514")
    alb = red * np.ones((size, size, 3), np.float32)
    alb = T.mix(alb, blk * np.ones_like(alb), both[..., None])
    alb = T.mix(alb, (red * 0.45 + blk * 0.55) * np.ones_like(alb), one[..., None])
    twill = 0.5 + 0.5 * np.sin(2 * np.pi * (u + v) * 128)
    fuzz = T.spectral(size, 0.6, seed)
    alb = alb * (0.85 + 0.12 * twill[..., None] + 0.1 * (fuzz[..., None] - 0.5))
    pill = T.smoothstep(0.5, 0.95, T.spectral(size, 1.8, seed + 1))
    alb = T.mix(alb, _c("#6d6255") * np.ones_like(alb), pill * 0.3)
    height = 0.5 + 0.3 * twill + 0.2 * fuzz
    rough = 0.92
    _save(out, alb, height, np.full((size, size), rough, np.float32), normal_strength=1.5)
