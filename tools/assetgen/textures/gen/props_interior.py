"""Interior props: furniture woods, laminates, enamel, metals, fabrics, ceramics, paper and print atlases.

Everything is procedural (numpy), tileable unless marked "atlas" (UV 0..1 over a part or atlas cells
addressed by the Blender generators in lib/props_int_core.py). Neutral/light base colours are used where
materials tint the texture (painted steel, plastics, vinyl, cotton), because a tint can only darken.

Atlases (cell layout is a contract with lib/props_int_core.py ATLAS_* constants):
  cardboard_print  4x4 cells of 256 px: cells 0..13 package art, 14 corrugated cardboard, 15 can-lid metal.
  book_spines      hardcover spines (2x32 cells of 32x256), paperbacks (2x32 of 32x128), page edges.
  pi_paper_notes   2x2 cells: lined note, flyer, sticky note, child's drawing.
"""
from __future__ import annotations

import numpy as np

from .. import texlib as T
from ..registry import texture

# ------------------------------------------------------------------------------------------------
# small tileable drawing helpers
# ------------------------------------------------------------------------------------------------


def _grid(size: int) -> tuple[np.ndarray, np.ndarray]:
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    return xx, yy


def _wrapd(a: np.ndarray, c: float, size: int) -> np.ndarray:
    """Signed wrapped distance from coordinate array a to c on a periodic axis."""
    return (a - c + size * 0.5) % size - size * 0.5


def _stamp_max(canvas: np.ndarray, x0: int, y0: int, patch: np.ndarray) -> None:
    """Writes max(canvas, patch) at (x0, y0) with wrap-around (patch smaller than canvas)."""
    s = canvas.shape[0]
    ys = (np.arange(patch.shape[0]) + y0) % s
    xs = (np.arange(patch.shape[1]) + x0) % s
    sub = canvas[np.ix_(ys, xs)]
    canvas[np.ix_(ys, xs)] = np.maximum(sub, patch)


def _segment_mask(size: int, p0, p1, width: float, soft: float = 1.0) -> tuple[int, int, np.ndarray]:
    """Anti-aliased capsule (line segment) patch; returns (x0, y0, patch) for _stamp_max."""
    x0 = int(np.floor(min(p0[0], p1[0]) - width - 2))
    y0 = int(np.floor(min(p0[1], p1[1]) - width - 2))
    x1 = int(np.ceil(max(p0[0], p1[0]) + width + 2))
    y1 = int(np.ceil(max(p0[1], p1[1]) + width + 2))
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    ax, ay = p0
    bx, by = p1
    dx, dy = bx - ax, by - ay
    ll = dx * dx + dy * dy
    t = np.clip(((xx - ax) * dx + (yy - ay) * dy) / max(ll, 1e-6), 0, 1)
    d = np.hypot(xx - (ax + t * dx), yy - (ay + t * dy))
    return x0, y0, np.clip((width - d) / soft + 0.5, 0, 1)


def _polyline(canvas: np.ndarray, pts, width: float, soft: float = 1.0) -> None:
    for a, b in zip(pts[:-1], pts[1:]):
        x0, y0, patch = _segment_mask(canvas.shape[0], a, b, width, soft)
        _stamp_max(canvas, x0, y0, patch)


def _scribble_line(rng: np.random.Generator, x: float, y: float, length: float, amp: float, step: float = 3.0):
    """Handwriting-like wavy stroke (no letters): x advances with random bumps."""
    pts = []
    n = max(2, int(length / step))
    ph = rng.uniform(0, 6.28)
    for i in range(n + 1):
        px = x + length * i / n
        py = y + np.sin(ph + i * rng.uniform(0.9, 1.9)) * amp * rng.uniform(0.3, 1.0)
        pts.append((px, py))
    return pts


def _rect_mask(xx, yy, x0, y0, x1, y1, soft: float = 1.0) -> np.ndarray:
    m = np.minimum(np.minimum(xx - x0, x1 - xx), np.minimum(yy - y0, y1 - yy))
    return np.clip(m / soft + 0.5, 0, 1)


def _weave(size: int, threads: int, *, depth: float = 1.0) -> np.ndarray:
    """Plain-weave height pattern: `threads` threads per tile in each direction (tileable)."""
    xx, yy = _grid(size)
    u = xx / size * threads * 2 * np.pi
    v = yy / size * threads * 2 * np.pi
    warp = 0.5 + 0.5 * np.cos(v) * np.sign(np.sin(u * 0.5 + 1e-3))
    weft = 0.5 + 0.5 * np.cos(u) * -np.sign(np.sin(v * 0.5 + 1e-3))
    return T.normalize((np.maximum(warp * (0.5 + 0.5 * np.abs(np.sin(u))), weft * (0.5 + 0.5 * np.abs(np.sin(v)))))) * depth


def _scratches(size: int, seed: int, count: int, length: tuple[float, float], width: float = 0.7,
               angle: float | None = None, spread: float = 3.14) -> np.ndarray:
    r = T.rng(seed)
    out = np.zeros((size, size), np.float32)
    for _ in range(count):
        x, y = r.uniform(0, size), r.uniform(0, size)
        a = (angle if angle is not None else 0.0) + r.uniform(-spread, spread)
        ln = r.uniform(*length)
        x0, y0, patch = _segment_mask(size, (x, y), (x + np.cos(a) * ln, y + np.sin(a) * ln), width * r.uniform(0.6, 1.3))
        _stamp_max(out, x0, y0, patch * r.uniform(0.3, 1.0))
    return out


def _col(h: str) -> np.ndarray:
    return T.hex_rgb(h)[None, None, :]


def _fill(size: int, h: str) -> np.ndarray:
    return np.ones((size, size, 3), np.float32) * _col(h)


# ------------------------------------------------------------------------------------------------
# woods
# ------------------------------------------------------------------------------------------------


def _wood(size: int, seed: int, *, rings: int, stops, pores: float, warp_amt: float, rough_base: float,
          figure: float = 1.0):
    """Flat-sawn grain running along U (image x), 1 tile ~ 1 m. Rings are contour lines of
    y*rings + smooth elongated 2D noise, which yields nested 'cathedral' arches. Tileable: integer
    ring count + periodic noise."""
    xx, yy = _grid(size)
    w1 = T.spectral(size, 3.2, seed, anisotropy=(1.0, 2.5), fmax=10)
    w2 = T.spectral(size, 2.2, seed + 1, anisotropy=(1.0, 8.0), fmin=3)
    v = yy / size * rings + (w1 - 0.5) * warp_amt * figure + (w2 - 0.5) * warp_amt * 0.12
    ring = v - np.floor(v)
    late = T.smoothstep(0.62, 0.93, ring) * (1.0 - T.smoothstep(0.95, 1.0, ring))
    early = ring ** 2
    fibre = T.spectral(size, 1.1, seed + 2, anisotropy=(1.0, 40.0))
    streak = T.spectral(size, 1.8, seed + 3, anisotropy=(1.0, 12.0))
    pore = T.spectral(size, 0.5, seed + 4, anisotropy=(1.0, 24.0))
    pore_mask = T.smoothstep(0.66, 0.8, pore) * pores
    broad = T.spectral(size, 2.8, seed + 5)
    tone = np.clip(0.38 * late + 0.17 * early + 0.27 * fibre + 0.18 * streak, 0, 1)
    col = T.gradient(T.normalize(tone), stops)
    col *= (0.9 + 0.14 * broad[..., None])
    col *= (1.0 - 0.3 * pore_mask)[..., None]
    height = T.normalize(0.45 * (1 - late) + 0.35 * fibre - 0.5 * pore_mask)
    rough = np.clip(rough_base + 0.06 * (fibre - 0.5) + 0.15 * pore_mask + 0.04 * late, 0, 1)
    return col, height, rough


@texture("wood_furniture_oak", size=1024, seed=4101)
def wood_furniture_oak(size: int, seed: int, out) -> None:
    """Golden-oak finished veneer (90s furniture), grain along U."""
    col, h, r = _wood(size, seed, rings=56, warp_amt=3.6, pores=1.0, rough_base=0.46,
                      stops=[(0.0, "#c99a5e"), (0.45, "#b9874d"), (0.8, "#a1703d"), (1.0, "#80542b")])
    T.save_pbr_set(out, np.clip(col, 0, 1), h, r, normal_strength=1.4)


@texture("wood_furniture_dark", size=1024, seed=4111)
def wood_furniture_dark(size: int, seed: int, out) -> None:
    """Dark walnut / cherry stained veneer, grain along U."""
    col, h, r = _wood(size, seed, rings=48, warp_amt=4.5, pores=0.55, rough_base=0.4,
                      stops=[(0.0, "#6f472d"), (0.45, "#5c3824"), (0.8, "#482a1a"), (1.0, "#331d10")])
    T.save_pbr_set(out, np.clip(col, 0, 1), h, r, normal_strength=1.2)


@texture("pi_wood_raw", size=512, seed=4121)
def pi_wood_raw(size: int, seed: int, out) -> None:
    """Raw pine / splintered wood (wear layer under paint and veneer, break faces, lumber)."""
    col, h, r = _wood(size, seed, rings=18, warp_amt=4.0, pores=0.15, rough_base=0.82,
                      stops=[(0.0, "#e2c597"), (0.5, "#d4b07c"), (0.8, "#b98a52"), (1.0, "#9a6c3a")])
    fib = T.spectral(size, 0.8, seed + 9, anisotropy=(1.0, 30.0))
    h = T.normalize(h + 0.6 * fib)
    col *= (0.92 + 0.12 * fib)[..., None]
    T.save_pbr_set(out, np.clip(col, 0, 1), h, np.clip(r + 0.05 * fib, 0, 1), normal_strength=2.5)


@texture("pi_wood_scuffed", size=512, seed=4125)
def pi_wood_scuffed(size: int, seed: int, out) -> None:
    """Scuffed-through veneer / paint: dull mid-tan raw wood with ground-in dirt (wear layer)."""
    col, h, r = _wood(size, seed, rings=26, warp_amt=3.0, pores=0.3, rough_base=0.8,
                      stops=[(0.0, "#b9966a"), (0.5, "#a7845a"), (0.85, "#8d6c45"), (1.0, "#76593a")])
    dirt = T.spectral(size, 1.6, seed + 3)
    col *= (0.82 + 0.2 * dirt[..., None])
    scr = _scratches(size, seed + 4, 160, (4, 25), width=0.6, angle=0.0, spread=0.5)
    col = T.mix(col, _fill(size, "#d2b58a"), scr * 0.35)
    T.save_pbr_set(out, np.clip(col, 0, 1), T.normalize(h - 0.5 * scr), np.clip(r + 0.1 * dirt, 0, 1), normal_strength=2.0)


@texture("pi_particleboard", size=512, seed=4131)
def pi_particleboard(size: int, seed: int, out) -> None:
    f1, f2, cid = T.worley(size, 7000, seed, jitter=1.0)
    chip = T.normalize(f2 - f1)
    tint = (np.sin(cid * 12.9898) * 43758.5453) % 1.0
    base = T.gradient(T.normalize(tint * 0.7 + 0.3 * T.spectral(size, 1.5, seed + 1)),
                      [(0.0, "#8a6a44"), (0.5, "#b08d5e"), (1.0, "#cfb07f")])
    base *= (0.75 + 0.25 * T.smoothstep(0.0, 0.25, chip))[..., None]
    h = T.normalize(0.6 * tint + 0.4 * T.smoothstep(0.0, 0.3, chip))
    T.save_pbr_set(out, np.clip(base, 0, 1), h, np.full((size, size), 0.9, np.float32), normal_strength=4.0)


@texture("pi_paint_wood", size=512, seed=4141)
def pi_paint_wood(size: int, seed: int, out) -> None:
    """Brushed enamel paint on wood, near white (tinted by materials)."""
    brush = T.spectral(size, 1.6, seed, anisotropy=(1.0, 10.0))
    grain = T.spectral(size, 1.9, seed + 1, anisotropy=(1.0, 4.0))
    blot = T.spectral(size, 2.8, seed + 2)
    col = _fill(size, "#efebe2") * (0.94 + 0.06 * brush[..., None]) * (0.96 + 0.05 * blot[..., None])
    col = T.mix(col, _fill(size, "#e2d7bf"), T.smoothstep(0.6, 0.95, blot) * 0.4)
    h = T.normalize(0.5 * brush + 0.3 * grain)
    r = np.clip(0.48 + 0.1 * (brush - 0.5) + 0.08 * blot, 0, 1)
    T.save_pbr_set(out, np.clip(col, 0, 1), h, r, normal_strength=1.2)


# ------------------------------------------------------------------------------------------------
# hard surfaces
# ------------------------------------------------------------------------------------------------


@texture("laminate_counter", size=512, seed=4201)
def laminate_counter(size: int, seed: int, out) -> None:
    """90s speckled high-pressure laminate (light neutral beige, tinted per material)."""
    base = _fill(size, "#ebe4d4")
    cloud = T.spectral(size, 2.2, seed)
    base *= (0.95 + 0.07 * cloud[..., None])
    for i, (h, thr, amt) in enumerate((("#7a6d5c", 0.86, 0.9), ("#a99a83", 0.8, 0.6), ("#ffffff", 0.84, 0.5),
                                         ("#5d5a55", 0.9, 0.9))):
        n = T.normalize(T.blur(T.spectral(size, 0.25, seed + 10 + i), 0.7))
        m = T.smoothstep(thr - 0.04, thr - 0.01, n) * amt
        base = T.mix(base, _fill(size, h), m)
    scr = _scratches(size, seed + 30, 70, (10, 60), width=0.6)
    base = T.mix(base, _fill(size, "#f7f4ec"), scr * 0.35)
    h = T.normalize(0.2 * cloud - 0.8 * scr)
    r = np.clip(0.36 + 0.08 * cloud + 0.25 * scr, 0, 1)
    T.save_pbr_set(out, np.clip(base, 0, 1), h, r, normal_strength=0.8)


@texture("enamel_appliance", size=512, seed=4211)
def enamel_appliance(size: int, seed: int, out) -> None:
    """Off-white baked enamel (appliances, bathtubs): orange peel, slight yellowing."""
    peel = T.blur(T.spectral(size, 0.7, seed), 1.2)
    yel = T.spectral(size, 2.6, seed + 1)
    col = T.mix(_fill(size, "#ece7da"), _fill(size, "#ddd1b3"), T.smoothstep(0.45, 0.95, yel) * 0.6)
    scr = _scratches(size, seed + 2, 40, (8, 40), width=0.6)
    col = T.mix(col, _fill(size, "#bfb7a6"), scr * 0.3)
    r = np.clip(0.26 + 0.06 * peel + 0.12 * T.smoothstep(0.5, 1.0, yel) + 0.25 * scr, 0, 1)
    T.save_pbr_set(out, np.clip(col, 0, 1), T.normalize(peel - 0.6 * scr), r, normal_strength=0.6)


@texture("pi_metal_smooth", size=512, seed=4221)
def pi_metal_smooth(size: int, seed: int, out) -> None:
    """Polished metal (chrome / brass via tint): smudges, fine scratches, pitting. Metallic."""
    smudge = T.spectral(size, 2.4, seed)
    scr = _scratches(size, seed + 1, 140, (6, 50), width=0.5)
    pits = T.smoothstep(0.88, 0.95, T.spectral(size, 0.3, seed + 2))
    col = _fill(size, "#d7d7d6") * (0.92 + 0.08 * smudge[..., None])
    col = T.mix(col, _fill(size, "#6b645c"), pits * 0.6)
    r = np.clip(0.14 + 0.18 * T.smoothstep(0.45, 0.9, smudge) + 0.2 * scr + 0.4 * pits, 0, 1)
    T.save_pbr_set(out, np.clip(col, 0, 1), T.normalize(-scr - pits), r, metal=1.0, normal_strength=0.8)


@texture("pi_metal_brushed", size=512, seed=4231)
def pi_metal_brushed(size: int, seed: int, out) -> None:
    """Brushed stainless steel (sinks, griddles, appliances). Metallic, streaks along U."""
    streak = T.spectral(size, 0.9, seed, anisotropy=(1.0, 60.0))
    smudge = T.spectral(size, 2.2, seed + 1)
    scr = _scratches(size, seed + 2, 90, (10, 80), width=0.5)
    col = _fill(size, "#c4c4c2") * (0.9 + 0.1 * streak[..., None]) * (0.93 + 0.07 * smudge[..., None])
    r = np.clip(0.3 + 0.1 * streak + 0.15 * T.smoothstep(0.5, 0.9, smudge) + 0.15 * scr, 0, 1)
    T.save_pbr_set(out, np.clip(col, 0, 1), T.normalize(streak - scr), r, metal=1.0, normal_strength=0.7)


@texture("pi_rust", size=512, seed=4241)
def pi_rust(size: int, seed: int, out) -> None:
    """Rust over bare steel (wear layer of painted steel / enamel / chrome)."""
    big = T.spectral(size, 2.0, seed)
    fine = T.spectral(size, 0.8, seed + 1)
    f1, f2, _ = T.worley(size, 300, seed + 2)
    pit = 1.0 - T.normalize(f1)
    t = T.normalize(0.6 * big + 0.4 * fine)
    col = T.gradient(t, [(0.0, "#3c3a38"), (0.35, "#5a3a24"), (0.65, "#8a4a22"), (1.0, "#b0682e")])
    col *= (0.8 + 0.25 * pit)[..., None]
    metal = np.clip(1.0 - T.smoothstep(0.25, 0.45, t) * 1.2, 0, 1) * 0.8
    r = np.clip(0.75 + 0.2 * fine - 0.35 * metal, 0, 1)
    T.save_pbr_set(out, np.clip(col, 0, 1), T.normalize(0.6 * fine + 0.4 * pit), r, metal=metal, normal_strength=3.0)


@texture("pi_paint_steel", size=512, seed=4251)
def pi_paint_steel(size: int, seed: int, out) -> None:
    """Baked powder-coat / enamel on sheet steel, light neutral grey (tinted per material)."""
    peel = T.blur(T.spectral(size, 0.6, seed), 1.0)
    cloud = T.spectral(size, 2.4, seed + 1)
    scr = _scratches(size, seed + 2, 60, (8, 50), width=0.6)
    col = _fill(size, "#dcdcda") * (0.95 + 0.06 * cloud[..., None])
    col = T.mix(col, _fill(size, "#8c8c8a"), scr * 0.35)
    r = np.clip(0.42 + 0.06 * peel + 0.06 * cloud + 0.2 * scr, 0, 1)
    T.save_pbr_set(out, np.clip(col, 0, 1), T.normalize(peel - scr), r, normal_strength=0.7)


@texture("ceramic_white", size=512, seed=4261)
def ceramic_white(size: int, seed: int, out) -> None:
    """Glazed vitreous china (toilets, sinks, plates): glossy, faint crazing and mineral stains."""
    f1, f2, _ = T.worley(size, 260, seed)
    craze = 1.0 - T.smoothstep(0.0, 0.9, f2 - f1)  # hairline crazing, colour only (glaze stays smooth)
    stain = T.spectral(size, 2.5, seed + 1)
    wave = T.blur(T.spectral(size, 1.2, seed + 2), 2.0)
    col = T.mix(_fill(size, "#f1eee8"), _fill(size, "#d8ccb2"), T.smoothstep(0.55, 1.0, stain) * 0.5)
    col = T.mix(col, _fill(size, "#b9b2a5"), craze * 0.025)
    r = np.clip(0.1 + 0.12 * T.smoothstep(0.55, 1.0, stain) + 0.03 * craze, 0, 1)
    T.save_pbr_set(out, np.clip(col, 0, 1), wave * 0.15, r, normal_strength=0.3)


@texture("pi_plastic", size=512, seed=4271)
def pi_plastic(size: int, seed: int, out) -> None:
    """Injection-moulded plastic with fine texture (tinted per material)."""
    grain = T.blur(T.spectral(size, 0.4, seed), 0.8)
    cloud = T.spectral(size, 2.4, seed + 1)
    scr = _scratches(size, seed + 2, 50, (6, 30), width=0.5)
    col = _fill(size, "#e6e4df") * (0.95 + 0.05 * cloud[..., None])
    col = T.mix(col, _fill(size, "#ffffff"), scr * 0.15)
    r = np.clip(0.5 + 0.08 * grain + 0.05 * cloud - 0.1 * scr, 0, 1)
    T.save_pbr_set(out, np.clip(col, 0, 1), T.normalize(grain - scr * 0.5), r, normal_strength=0.6)


@texture("pi_glass", size=512, seed=4281)
def pi_glass(size: int, seed: int, out) -> None:
    """Opaque stand-in for dirty glass: dark reflective base with dust and finger smears."""
    dust = T.normalize(0.6 * T.spectral(size, 1.2, seed) + 0.4 * T.spectral(size, 0.6, seed + 2))
    smear = T.spectral(size, 1.8, seed + 1, anisotropy=(1.0, 3.0))
    col = T.mix(_fill(size, "#1d2225"), _fill(size, "#5e5e58"), T.smoothstep(0.5, 0.9, dust) * 0.4)
    r = np.clip(0.06 + 0.4 * T.smoothstep(0.5, 0.95, dust) + 0.15 * T.smoothstep(0.6, 0.9, smear), 0, 1)
    T.save_pbr_set(out, np.clip(col, 0, 1), dust * 0.1, r, normal_strength=0.2)


@texture("pi_screen_crt", size=512, seed=4291)
def pi_screen_crt(size: int, seed: int, out) -> None:
    """Dead CRT face (atlas 0..1 over the screen): grey-green phosphor glass, vignette, dust."""
    xx, yy = _grid(size)
    u, v = xx / size * 2 - 1, yy / size * 2 - 1
    vign = np.clip(1.0 - (u * u + v * v) * 0.35, 0, 1)
    dust = T.spectral(size, 1.5, seed)
    col = _fill(size, "#3a423d") * (0.6 + 0.4 * vign[..., None])
    col = T.mix(col, _fill(size, "#8a8a80"), T.smoothstep(0.6, 0.95, dust) * 0.35)
    r = np.clip(0.07 + 0.35 * T.smoothstep(0.6, 0.95, dust), 0, 1)
    T.save_pbr_set(out, np.clip(col, 0, 1), dust * 0.05, r, normal_strength=0.2)


@texture("mirror_dirty", size=512, seed=4301)
def mirror_dirty(size: int, seed: int, out) -> None:
    """Mirror (atlas 0..1 over the glass): silvering with desilvered edges, spots and smears."""
    xx, yy = _grid(size)
    u, v = xx / size, yy / size
    edge = np.minimum(np.minimum(u, 1 - u), np.minimum(v, 1 - v))
    n = T.spectral(size, 1.6, seed)
    spots = T.smoothstep(0.9, 0.93, T.spectral(size, 0.9, seed + 1))
    patchy = T.smoothstep(0.45, 0.7, T.spectral(size, 1.8, seed + 3))
    desilver = np.clip(T.smoothstep(0.05, 0.0, edge + (n - 0.5) * 0.06) * patchy + T.smoothstep(0.008, 0.0, edge) + spots * 0.7, 0, 1)
    smear = T.spectral(size, 1.8, seed + 2, anisotropy=(1.0, 2.5))
    col = T.mix(_fill(size, "#d5d8d6"), _fill(size, "#3b3428"), desilver * 0.85)
    r = np.clip(0.04 + 0.25 * T.smoothstep(0.55, 0.9, smear) + 0.5 * desilver, 0, 1)
    metal = np.clip(1.0 - desilver * 0.8, 0, 1)
    T.save_pbr_set(out, np.clip(col, 0, 1), desilver * 0.2, r, metal=metal, normal_strength=0.3)


# ------------------------------------------------------------------------------------------------
# fabrics & soft goods
# ------------------------------------------------------------------------------------------------


def _flower_patch(rng: np.random.Generator, radius: float, petals: int):
    n = int(radius * 2 + 6)
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32) - n / 2
    ang = np.arctan2(yy, xx) + rng.uniform(0, 6.28)
    rr = np.hypot(xx, yy)
    shape = radius * (0.55 + 0.45 * np.abs(np.cos(ang * petals / 2)))
    petal = np.clip((shape - rr) / 1.5 + 0.5, 0, 1)
    inner = np.clip((radius * 0.42 * (0.8 + 0.2 * np.cos(ang * petals)) - rr) / 1.5 + 0.5, 0, 1)
    centre = np.clip((radius * 0.16 - rr) / 1.2 + 0.5, 0, 1)
    vein = (0.5 + 0.5 * np.cos(ang * petals * 2)) * petal * (rr / max(radius, 1))
    return petal, inner, centre, vein


def _leaf_patch(rng: np.random.Generator, length: float, width: float, angle: float):
    n = int(length * 2 + 6)
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32) - n / 2
    ca, sa = np.cos(angle), np.sin(angle)
    lx = xx * ca + yy * sa
    ly = -xx * sa + yy * ca
    t = np.clip(lx / length, -1, 1)
    half = width * np.sqrt(np.clip(1 - t * t, 0, 1))
    leaf = np.clip((half - np.abs(ly)) / 1.2 + 0.5, 0, 1) * (np.abs(lx) < length)
    rib = np.clip((0.8 - np.abs(ly)) / 0.8, 0, 1) * leaf
    return leaf, rib


@texture("upholstery_floral", size=1024, seed=4401)
def upholstery_floral(size: int, seed: int, out) -> None:
    """Early-90s floral tapestry upholstery: tone-on-tone damask ground with dense, soft-edged dusty
    rose / mauve blooms, shaded petals and sage leaves, woven texture and fading."""
    r = T.rng(seed)
    xx, yy = _grid(size)
    cloud = T.spectral(size, 2.2, seed + 1)
    # tone-on-tone ground: scrolling vine damask from warped sine contours
    w = T.spectral(size, 2.6, seed + 2)
    dam = np.sin((xx / size * 6 + (w - 0.5) * 2.5) * 2 * np.pi) * np.sin((yy / size * 6 + (w - 0.5) * 2.0) * 2 * np.pi)
    dam = T.smoothstep(0.55, 0.75, np.abs(dam))
    ground = T.mix(_fill(size, "#d3c4a2"), _fill(size, "#bfae8a"), dam * 0.7)
    ground *= (0.92 + 0.1 * cloud[..., None])
    leaf_m = np.zeros((size, size), np.float32)
    leaf_rib = np.zeros((size, size), np.float32)
    pet_a = np.zeros((size, size), np.float32)
    pet_b = np.zeros((size, size), np.float32)
    shade = np.zeros((size, size), np.float32)
    centre = np.zeros((size, size), np.float32)
    cells = 5
    cs = size / cells
    for gy in range(cells):
        for gx in range(cells):
            cx = (gx + 0.5 + (0.5 if gy % 2 else 0.0)) * cs + r.uniform(-cs * 0.15, cs * 0.15)
            cy = (gy + 0.5) * cs + r.uniform(-cs * 0.15, cs * 0.15)
            rad = r.uniform(0.2, 0.27) * cs
            for k in range(int(r.integers(4, 7))):
                ang = r.uniform(0, 6.28)
                ln = rad * r.uniform(0.8, 1.3)
                lp, lr = _leaf_patch(r, ln * 0.62, ln * 0.22, ang)
                ox = cx + np.cos(ang) * rad * 1.1 - lp.shape[1] / 2
                oy = cy + np.sin(ang) * rad * 1.1 - lp.shape[0] / 2
                _stamp_max(leaf_m, int(ox), int(oy), lp)
                _stamp_max(leaf_rib, int(ox), int(oy), lr)
            for layer in range(2):  # two overlapping petal whorls give depth
                petals = int(r.integers(5, 8))
                rr = rad * (1.0 if layer == 0 else 0.62)
                p_, i_, c_, v_ = _flower_patch(r, rr, petals)
                n = p_.shape[0]
                ly, lx = np.mgrid[0:n, 0:n].astype(np.float32) - n / 2
                radial = np.clip(np.hypot(lx, ly) / max(rr, 1), 0, 1)
                target = pet_a if (gx + gy + layer) % 2 == 0 else pet_b
                ox, oy = int(cx - n / 2), int(cy - n / 2)
                _stamp_max(target, ox, oy, p_)
                _stamp_max(shade, ox, oy, p_ * (1 - radial) * (0.6 + 0.4 * v_))
                if layer == 1:
                    _stamp_max(centre, ox, oy, c_)
            for _ in range(3):  # buds and sprigs filling the gaps
                bx = cx + r.uniform(-0.6, 0.6) * cs
                by = cy + r.uniform(0.35, 0.6) * cs * (1 if r.random() < 0.5 else -1)
                bp, _, bc, _ = _flower_patch(r, rad * r.uniform(0.22, 0.35), 5)
                _stamp_max(pet_b if r.random() < 0.5 else pet_a, int(bx - bp.shape[1] / 2), int(by - bp.shape[0] / 2), bp)
    soft = lambda m: T.blur(m, 1.4)
    leaf_m, leaf_rib, pet_a, pet_b, shade, centre = map(soft, (leaf_m, leaf_rib, pet_a, pet_b, shade, centre))
    col = T.mix(ground, _fill(size, "#76825d"), leaf_m * 0.9)
    col = T.mix(col, _fill(size, "#55613f"), leaf_rib * 0.5)
    col = T.mix(col, _fill(size, "#b77a7c"), pet_a * 0.92)
    col = T.mix(col, _fill(size, "#906784"), pet_b * 0.92)
    col = T.mix(col, _fill(size, "#6b3a4a"), shade * 0.45)
    col = T.mix(col, _fill(size, "#c9a35a"), centre * 0.8)
    weave = _weave(size, 128)
    col *= (0.84 + 0.2 * weave[..., None])
    fade = T.spectral(size, 2.6, seed + 7)
    col = T.mix(col, _fill(size, "#cbc1ad"), T.smoothstep(0.55, 1.0, fade) * 0.3)
    h = T.normalize(0.75 * weave + 0.15 * (pet_a + pet_b + leaf_m) + 0.1 * dam)
    T.save_pbr_set(out, np.clip(col, 0, 1), h, np.clip(0.88 + 0.06 * weave, 0, 1), normal_strength=2.0)


@texture("upholstery_brown", size=512, seed=4411)
def upholstery_brown(size: int, seed: int, out) -> None:
    """Corduroy / velour upholstery in a light warm tan (darkened by material tint)."""
    xx, yy = _grid(size)
    wales = 0.5 + 0.5 * np.cos(xx / size * 64 * 2 * np.pi)
    fuzz = T.spectral(size, 0.5, seed)
    crush = T.spectral(size, 2.0, seed + 1, anisotropy=(3.0, 1.0))
    col = _fill(size, "#c7a684") * (0.78 + 0.22 * wales[..., None]) * (0.9 + 0.12 * fuzz[..., None])
    col *= (0.9 + 0.14 * crush[..., None])
    h = T.normalize(0.75 * wales + 0.25 * fuzz)
    T.save_pbr_set(out, np.clip(col, 0, 1), h, np.clip(0.9 - 0.12 * crush, 0, 1), normal_strength=2.6)


@texture("pi_vinyl", size=512, seed=4421)
def pi_vinyl(size: int, seed: int, out) -> None:
    """Pebble-grain upholstery vinyl, light neutral (tinted red/black/teal per material)."""
    f1, f2, _ = T.worley(size, 5000, seed, jitter=1.0)
    peb = T.smoothstep(0.0, 2.5, f2 - f1)
    cloud = T.spectral(size, 2.3, seed + 1)
    creases = _scratches(size, seed + 2, 30, (20, 90), width=0.9)
    col = _fill(size, "#e8e2dc") * (0.95 + 0.05 * peb[..., None]) * (0.94 + 0.08 * cloud[..., None])
    col = T.mix(col, _fill(size, "#ffffff"), creases * 0.18)
    r = np.clip(0.42 + 0.12 * (1 - peb) + 0.1 * cloud + 0.15 * creases, 0, 1)
    T.save_pbr_set(out, np.clip(col, 0, 1), T.normalize(peb - creases), r, normal_strength=1.6)


@texture("pi_foam", size=512, seed=4431)
def pi_foam(size: int, seed: int, out) -> None:
    """Aged polyurethane foam (exposed under torn upholstery / cracked vinyl)."""
    f1, f2, _ = T.worley(size, 3000, seed, jitter=1.0)
    cell = T.normalize(f1)
    age = T.spectral(size, 2.2, seed + 1)
    col = T.gradient(T.normalize(age), [(0.0, "#e2c97e"), (0.6, "#cfa955"), (1.0, "#a77e34")])
    col *= (0.7 + 0.35 * (1 - cell))[..., None]
    T.save_pbr_set(out, np.clip(col, 0, 1), 1 - cell, np.full((size, size), 0.97, np.float32), normal_strength=3.0)


@texture("pi_cotton", size=512, seed=4441)
def pi_cotton(size: int, seed: int, out) -> None:
    """Plain-weave cotton / linen, off-white (sheets, pillows, towels, lamp shades; tinted)."""
    weave = _weave(size, 96)
    slub = T.spectral(size, 1.2, seed, anisotropy=(1.0, 8.0))
    cloud = T.spectral(size, 2.4, seed + 1)
    col = _fill(size, "#ebe7df") * (0.9 + 0.1 * weave[..., None]) * (0.95 + 0.06 * slub[..., None])
    col *= (0.95 + 0.06 * cloud[..., None])
    T.save_pbr_set(out, np.clip(col, 0, 1), T.normalize(weave + 0.3 * slub), np.full((size, size), 0.9, np.float32),
                   normal_strength=1.5)


@texture("pi_fabric_worn", size=512, seed=4445)
def pi_fabric_worn(size: int, seed: int, out) -> None:
    """Threadbare, grimy upholstery (wear layer for fabrics): dull grey-brown with exposed weave."""
    weave = _weave(size, 80)
    dirt = T.spectral(size, 1.8, seed)
    fuzz = T.spectral(size, 0.6, seed + 1)
    col = _fill(size, "#7d7062") * (0.78 + 0.25 * weave[..., None]) * (0.85 + 0.2 * dirt[..., None])
    col *= (0.92 + 0.1 * fuzz[..., None])
    T.save_pbr_set(out, np.clip(col, 0, 1), T.normalize(weave + 0.3 * fuzz), np.full((size, size), 0.95, np.float32),
                   normal_strength=2.0)


@texture("mattress_ticking", size=1024, seed=4451)
def mattress_ticking(size: int, seed: int, out) -> None:
    """Damask-quilted mattress ticking with stripes, tufting dimples and old urine/water stains."""
    xx, yy = _grid(size)
    stripe = 0.5 + 0.5 * np.cos(xx / size * 24 * 2 * np.pi)
    col = T.mix(_fill(size, "#ecebe4"), _fill(size, "#a9b2bd"), T.smoothstep(0.75, 0.95, stripe) * 0.8)
    # diamond quilting stitch lines
    u = (xx + yy) / size * 8
    v = (xx - yy) / size * 8
    du = np.abs(u - np.round(u))
    dv = np.abs(v - np.round(v))
    stitch = np.clip(1 - np.minimum(du, dv) * 40, 0, 1)
    puff = 1 - np.clip(np.minimum(du, dv) * 2.2, 0, 1) ** 0.5
    weave = _weave(size, 160)
    col *= (0.92 + 0.08 * weave[..., None])
    col = T.mix(col, _fill(size, "#8f8a80"), stitch * 0.35)
    # stains: several water/urine stains with darker tide lines, plus a few dark body-shaped blotches
    st = T.spectral(size, 2.5, seed + 3, fmin=2.0)
    st2 = T.spectral(size, 2.2, seed + 4, fmin=2.0)
    big = T.spectral(size, 2.8, seed + 6)
    blob = T.smoothstep(0.7, 0.8, st)
    tide = T.smoothstep(0.69, 0.705, st) * (1 - T.smoothstep(0.71, 0.73, st))
    blob2 = T.smoothstep(0.78, 0.84, st2)
    faint = T.smoothstep(0.6, 0.8, big)
    col = T.mix(col, _fill(size, "#cdb57c"), faint * 0.3)
    col = T.mix(col, _fill(size, "#c9a964"), blob * 0.55)
    col = T.mix(col, _fill(size, "#7a5a2c"), tide * 0.65)
    col = T.mix(col, _fill(size, "#5e4234"), blob2 * 0.45)
    grime = T.spectral(size, 2.6, seed + 5)
    col *= (0.86 + 0.14 * grime[..., None])
    h = T.normalize(puff * 0.8 + 0.2 * weave - 0.5 * stitch)
    T.save_pbr_set(out, np.clip(col, 0, 1), h, np.clip(0.88 - 0.1 * blob2, 0, 1), normal_strength=2.2)


@texture("bedding_quilt", size=1024, seed=4461)
def bedding_quilt(size: int, seed: int, out) -> None:
    """Patchwork quilt: 8x8 squares of muted calicos/checks, stitched seams, puffy batting."""
    r = T.rng(seed)
    xx, yy = _grid(size)
    n = 8
    cs = size // n
    palette = ["#8c3b3b", "#c9b48a", "#4f6178", "#7d8b6a", "#b98a5a", "#d8cfb8", "#6a4f6e", "#a35d3f", "#c2c7b8"]
    col = np.zeros((size, size, 3), np.float32)
    lx, ly = xx % cs, yy % cs
    for gy in range(n):
        for gx in range(n):
            c = T.hex_rgb(palette[int(r.integers(0, len(palette)))])
            c2 = T.hex_rgb(palette[int(r.integers(0, len(palette)))])
            kind = int(r.integers(0, 4))
            sl = (slice(gy * cs, (gy + 1) * cs), slice(gx * cs, (gx + 1) * cs))
            px, py = lx[sl], ly[sl]
            if kind == 0:
                m = ((np.floor(px / 8) + np.floor(py / 8)) % 2).astype(np.float32)
            elif kind == 1:
                m = (np.hypot((px % 16) - 8, (py % 16) - 8) < 2.5).astype(np.float32)
            elif kind == 2:
                m = ((px // 6) % 2).astype(np.float32)
            else:
                m = np.zeros_like(px)
            col[sl] = c[None, None, :] * (1 - m[..., None] * 0.6) + c2[None, None, :] * m[..., None] * 0.6
    seam_d = np.minimum(np.minimum(lx, cs - 1 - lx), np.minimum(ly, cs - 1 - ly))
    seam = np.clip(1 - seam_d / 2.0, 0, 1)
    dash = ((xx + yy) // 6 % 2).astype(np.float32)
    stitch = np.clip(1 - np.abs(seam_d - 6) / 1.0, 0, 1) * dash
    puff = np.sin(np.clip(seam_d / (cs * 0.5), 0, 1) * np.pi * 0.5)
    col *= (0.75 + 0.25 * puff[..., None])
    col = T.mix(col, _fill(size, "#3b332b"), seam * 0.5)
    col = T.mix(col, _fill(size, "#e8e0cc"), stitch * 0.6)
    weave = _weave(size, 160)
    col *= (0.9 + 0.1 * weave[..., None])
    fade = T.spectral(size, 2.4, seed + 1)
    col = T.mix(col, _fill(size, "#b3aa98"), T.smoothstep(0.45, 1.0, fade) * 0.45)
    lum = col.mean(axis=-1, keepdims=True)
    col = col * 0.62 + lum * 0.38  # washed-out, sun-faded dyes
    grime = T.spectral(size, 2.0, seed + 2)
    col *= (0.8 + 0.14 * grime[..., None])
    h = T.normalize(puff + 0.15 * weave - 0.3 * seam)
    T.save_pbr_set(out, np.clip(col, 0, 1), h, np.full((size, size), 0.92, np.float32), normal_strength=2.5)


@texture("carpet_rug", size=1024, seed=4471)
def carpet_rug(size: int, seed: int, out) -> None:
    """Rectangular area rug (atlas: UV 0..1 over the rug): oriental-style geometric field, border,
    medallion, worn traffic path. Generic ornament only."""
    xx, yy = _grid(size)
    u, v = xx / size, yy / size
    du, dv = np.abs(u - 0.5), np.abs(v - 0.5)
    edge = np.minimum(np.minimum(u, 1 - u), np.minimum(v, 1 - v))
    col = _fill(size, "#6b1f22")
    # field lattice of small diamonds
    fu, fv = (u * 18) % 1.0 - 0.5, (v * 12) % 1.0 - 0.5
    dia = np.clip(1 - (np.abs(fu) + np.abs(fv)) * 4.0, 0, 1)
    col = T.mix(col, _fill(size, "#2c3b5a"), T.smoothstep(0.2, 0.3, dia))
    col = T.mix(col, _fill(size, "#d7c497"), T.smoothstep(0.7, 0.8, dia))
    # stepped central medallion
    md = np.maximum(np.abs(u - 0.5) * 1.6, np.abs(v - 0.5) * 2.2) * 0.5 + (du + dv) * 0.5
    step_odd = (np.floor(md * 48).astype(np.int32) % 2 == 0).astype(np.float32)
    col = T.mix(col, _fill(size, "#2c3b5a"), (md < 0.2).astype(np.float32))
    col = T.mix(col, _fill(size, "#c7a25a"), ((md < 0.13) & (md > 0.1)).astype(np.float32))
    col = T.mix(col, _fill(size, "#8a2a2a"), (md < 0.08).astype(np.float32))
    col = T.mix(col, _fill(size, "#e2d3ad"), step_odd * (md < 0.2) * (md > 0.16) * 0.7)
    # border bands
    band = (edge < 0.11).astype(np.float32)
    col = T.mix(col, _fill(size, "#26324c"), band)
    bord_m = (np.abs((np.where(du > dv, v, u) * 40) % 1.0 - 0.5) < 0.22).astype(np.float32) * band * (edge > 0.035)
    col = T.mix(col, _fill(size, "#b5813e"), bord_m * 0.85)
    for e0, e1, c in ((0.028, 0.036, "#e2d3ad"), (0.104, 0.112, "#e2d3ad"), (0.12, 0.128, "#c7a25a")):
        col = T.mix(col, _fill(size, c), ((edge > e0) & (edge < e1)).astype(np.float32))
    # pile, wear and dirt
    pile = T.spectral(size, 0.5, seed)
    col *= (0.85 + 0.2 * pile[..., None])
    path = np.exp(-((u - 0.45 - 0.08 * np.sin(v * 6)) ** 2) / 0.02) * 0.6
    wear = T.spectral(size, 2.0, seed + 1)
    worn = np.clip(path * (0.5 + wear) + T.smoothstep(0.75, 1.0, wear) * 0.4, 0, 1)
    col = T.mix(col, _fill(size, "#8c7a64"), worn * 0.45)
    dirt = T.spectral(size, 2.4, seed + 2)
    col *= (0.82 + 0.18 * dirt[..., None])
    h = T.normalize(pile - 0.3 * worn)
    T.save_pbr_set(out, np.clip(col, 0, 1), h, np.full((size, size), 0.96, np.float32), normal_strength=2.0)


@texture("pi_rug_braided", size=512, seed=4481)
def pi_rug_braided(size: int, seed: int, out) -> None:
    """Braided rag-rug strands: rows along U (oval rugs map V to the radial distance)."""
    r = T.rng(seed)
    xx, yy = _grid(size)
    rows = 16
    rh = size / rows
    ry = yy % rh / rh
    row = (yy // rh).astype(int)
    pal = ["#5b3a2a", "#7a6a4e", "#3f4a3a", "#8a3a2e", "#4a4f63", "#a28a62", "#2f2a28", "#6b5a4a"]
    seq = [T.hex_rgb(pal[int(r.integers(0, len(pal)))]) for _ in range(rows)]
    base = np.stack(seq)[row]
    chev = np.abs(((xx / rh * 1.5 + np.where(ry < 0.5, ry, 1 - ry) * 2.0) % 1.0) - 0.5) * 2
    tube = np.sin(ry * np.pi)
    strand = (0.6 + 0.4 * chev) * tube
    col = base * (0.55 + 0.6 * strand[..., None])
    fuzz = T.spectral(size, 0.6, seed + 1)
    col *= (0.88 + 0.16 * fuzz[..., None])
    T.save_pbr_set(out, np.clip(col, 0, 1), T.normalize(strand + 0.1 * fuzz), np.full((size, size), 0.95, np.float32),
                   normal_strength=3.0)


@texture("pi_burlap", size=512, seed=4491)
def pi_burlap(size: int, seed: int, out) -> None:
    """Coarse woven sacking (feed sacks)."""
    weave = _weave(size, 40)
    fuzz = T.spectral(size, 0.7, seed)
    cloud = T.spectral(size, 2.2, seed + 1)
    col = _fill(size, "#b79d6c") * (0.7 + 0.35 * weave[..., None]) * (0.9 + 0.12 * fuzz[..., None])
    col *= (0.9 + 0.12 * cloud[..., None])
    T.save_pbr_set(out, np.clip(col, 0, 1), T.normalize(weave + 0.2 * fuzz), np.full((size, size), 0.96, np.float32),
                   normal_strength=3.0)


# ------------------------------------------------------------------------------------------------
# paper / print / boards (atlases)
# ------------------------------------------------------------------------------------------------


def _package_cell(rng: np.random.Generator, n: int, kind: int) -> np.ndarray:
    """One 256 px package face: colour fields, bands and abstract emblems; no text or brands."""
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    u, v = xx / n, yy / n
    pals = [("#c23b22", "#f2d16b", "#ffffff"), ("#1f4e8c", "#f0f0f0", "#e3b23c"), ("#2f7d4a", "#f4e7c5", "#c0392b"),
            ("#f2b134", "#6b2c1a", "#ffffff"), ("#6a3d7a", "#f6e6c8", "#3fa7a0"), ("#e8e3d3", "#c0392b", "#2b2b2b"),
            ("#3a8fc0", "#ffffff", "#f2c14e"), ("#8c2f39", "#e9d8a6", "#1d3557")]
    a, b, c = (T.hex_rgb(h) for h in pals[kind % len(pals)])
    col = np.ones((n, n, 3), np.float32) * a
    style = kind % 4
    if style == 0:  # diagonal band + sun disc
        band = (np.abs((u - v) * 1.0 + rng.uniform(-0.1, 0.1)) < 0.12).astype(np.float32)
        col = T.mix(col, np.ones_like(col) * b, band)
        disc = (np.hypot(u - 0.62, v - 0.36) < 0.17).astype(np.float32)
        col = T.mix(col, np.ones_like(col) * c, disc)
    elif style == 1:  # horizontal stripes + window rectangle
        st = ((v * 7).astype(int) % 2 == 0).astype(np.float32) * (v < 0.3)
        col = T.mix(col, np.ones_like(col) * b, st)
        win = ((u > 0.2) & (u < 0.8) & (v > 0.42) & (v < 0.8)).astype(np.float32)
        col = T.mix(col, np.ones_like(col) * (b * 0.6 + c * 0.4), win)
        blob = (np.hypot((u - 0.5) * 1.4, v - 0.61) < 0.13).astype(np.float32) * win
        col = T.mix(col, np.ones_like(col) * c, blob)
    elif style == 2:  # big emblem ring + chevrons
        rr = np.hypot(u - 0.5, v - 0.45)
        ring = ((rr > 0.22) & (rr < 0.3)).astype(np.float32)
        col = T.mix(col, np.ones_like(col) * b, ring)
        col = T.mix(col, np.ones_like(col) * c, (rr < 0.15).astype(np.float32))
        chev = (np.abs(((u * 6 + np.abs(v - 0.88) * 6) % 1.0) - 0.5) < 0.18).astype(np.float32) * (v > 0.8)
        col = T.mix(col, np.ones_like(col) * b, chev)
    else:  # wave field + label plate
        wave = (v > 0.55 + 0.06 * np.sin(u * 12.0 + kind)).astype(np.float32)
        col = T.mix(col, np.ones_like(col) * b, wave)
        plate = ((u > 0.15) & (u < 0.85) & (v > 0.18) & (v < 0.4)).astype(np.float32)
        col = T.mix(col, np.ones_like(col) * c, plate)
    # abstract "title" bar blocks (not letters) and a generic barcode patch
    for i in range(int(rng.integers(2, 5))):
        x0, y0 = rng.uniform(0.12, 0.4), 0.06 + i * 0.045
        bar = ((u > x0) & (u < x0 + rng.uniform(0.2, 0.45)) & (v > y0) & (v < y0 + 0.022)).astype(np.float32)
        col = T.mix(col, np.ones_like(col) * (c if i == 0 else b), bar * 0.9)
    bc = ((u > 0.68) & (u < 0.9) & (v > 0.86) & (v < 0.95)).astype(np.float32)
    col = T.mix(col, np.ones_like(col), bc)
    lines = ((np.sin(u * n * 1.7 + np.floor(u * 37) * 3.1) > 0.2) & (bc > 0)).astype(np.float32)
    col = T.mix(col, np.zeros_like(col), lines * 0.85)
    return col


@texture("cardboard_print", size=1024, seed=4501)
def cardboard_print(size: int, seed: int, out) -> None:
    """Atlas of generic packaging faces (4x4 cells): 0..13 printed art, 14 corrugated kraft, 15 tin."""
    r = T.rng(seed)
    n = size // 4
    col = np.zeros((size, size, 3), np.float32)
    height = np.zeros((size, size), np.float32)
    for k in range(16):
        cy, cx = divmod(k, 4)
        sl = (slice(cy * n, (cy + 1) * n), slice(cx * n, (cx + 1) * n))
        if k < 14:
            col[sl] = _package_cell(r, n, k)
        elif k == 14:
            yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
            flute = 0.5 + 0.5 * np.cos(xx / n * 40 * 2 * np.pi)
            col[sl] = T.hex_rgb("#a77d4f")[None, None, :] * (0.88 + 0.1 * flute[..., None])
            height[sl] = flute * 0.3
        else:
            yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
            rr = np.hypot(xx - n / 2, yy - n / 2) / (n / 2)
            rim = 0.5 + 0.5 * np.cos(rr * 18)
            col[sl] = T.hex_rgb("#b8b6b0")[None, None, :] * (0.8 + 0.2 * rim[..., None])
            height[sl] = rim * 0.4
    grime = T.spectral(size, 2.3, seed + 1)
    col *= (0.86 + 0.14 * grime[..., None])
    scuff = _scratches(size, seed + 2, 120, (5, 30), width=0.8)
    col = T.mix(col, _fill(size, "#d9cbb0"), scuff * 0.3)
    T.save_pbr_set(out, np.clip(col, 0, 1), height + 0.1 * grime, np.clip(0.7 + 0.1 * grime, 0, 1), normal_strength=1.2)


@texture("book_spines", size=1024, seed=4511)
def book_spines(size: int, seed: int, out) -> None:
    """Atlas (contract with lib/props_int_core.py BOOK_*):
      y   0..512  hardcover spines, 2 rows x 32 (32x256 px): cloth colours, gilt bands, title dashes
      y 512..768  paperback spines, 2 rows x 32 (32x128 px)
      y 768..1024 page edges (cream, fine lines)
    Book side faces sample a small band-free patch of their own spine cell so covers match spines."""
    r = T.rng(seed)
    col = np.zeros((size, size, 3), np.float32)
    h = np.zeros((size, size), np.float32)
    pal = ["#5c1f1f", "#1f3a5c", "#2e4a2e", "#6b5a3a", "#3b2a4a", "#8a6a2a", "#202020", "#7a7a72", "#a33a2a",
           "#c8b890", "#2a5a5a", "#4a3020", "#d0c8b0", "#5a6a7a"]
    sw = size // 32
    gold = T.hex_rgb("#c9a44a")
    for row in range(2):
        sh = size // 4
        for i in range(32):
            base = T.hex_rgb(pal[int(r.integers(0, len(pal)))])
            yy, xx = np.mgrid[0:sh, 0:sw].astype(np.float32)
            shade = 0.82 + 0.18 * np.sin(xx / sw * np.pi)
            c = np.ones((sh, sw, 3), np.float32) * base * shade[..., None]
            light = np.clip(base * 1.8 + 0.25, 0, 1) if base.mean() < 0.45 else np.clip(base * 0.35, 0, 1)
            acc = gold if r.random() < 0.5 else light
            for b in range(int(r.integers(1, 3))):
                by = r.uniform(0.04, 0.2) if b == 0 else r.uniform(0.75, 0.92)
                band = ((yy / sh > by) & (yy / sh < by + r.uniform(0.01, 0.03))).astype(np.float32)
                c = T.mix(c, np.ones_like(c) * acc, band)
            ty, tl = r.uniform(0.28, 0.42), r.uniform(0.25, 0.42)
            dash = ((yy / sh > ty) & (yy / sh < ty + tl) & (np.abs(xx - sw / 2) < sw * 0.18)).astype(np.float32)
            dash *= ((yy // 5) % 3 != 0).astype(np.float32)
            c = T.mix(c, np.ones_like(c) * acc, dash * 0.85)
            col[row * sh:(row + 1) * sh, i * sw:(i + 1) * sw] = c
            h[row * sh:(row + 1) * sh, i * sw:(i + 1) * sw] = shade * 0.3
    for row in range(2):
        sh = size // 8
        y0 = size // 2 + row * sh
        for i in range(32):
            base = np.clip(T.hex_rgb(pal[int(r.integers(0, len(pal)))]) * 0.7 + T.hex_rgb("#e0d8c0") * 0.35 * r.random(), 0, 1)
            yy, xx = np.mgrid[0:sh, 0:sw].astype(np.float32)
            c = np.ones((sh, sw, 3), np.float32) * base * (0.85 + 0.15 * np.sin(xx / sw * np.pi))[..., None]
            dash = ((yy > 20) & (yy < 96) & (np.abs(xx - sw / 2) < sw * 0.16) & ((yy // 4) % 3 != 0)).astype(np.float32)
            c = T.mix(c, np.ones_like(c) * (0.1 if base.mean() > 0.5 else 0.9), dash * 0.8)
            col[y0:y0 + sh, i * sw:(i + 1) * sw] = c
    yy, xx = np.mgrid[0:size // 4, 0:size].astype(np.float32)
    wob = T.spectral(size, 1.0, seed + 3)[:size // 4]
    pages = 0.5 + 0.5 * np.sin(yy * 1.7 + wob * 4)
    col[3 * size // 4:] = T.hex_rgb("#e6dcc0")[None, None, :] * (0.85 + 0.12 * pages[..., None])
    h[3 * size // 4:] = pages * 0.4
    grime = T.spectral(size, 2.2, seed + 1)
    col *= (0.84 + 0.16 * grime[..., None])
    T.save_pbr_set(out, np.clip(col, 0, 1), h, np.full((size, size), 0.8, np.float32), normal_strength=1.0)


@texture("chalkboard", size=1024, seed=4521)
def chalkboard(size: int, seed: int, out) -> None:
    """Diner menu chalkboard (atlas 0..1 over the slate): eraser haze, abstract chalk 'menu' rows
    (wavy strokes, no letters), price dots, a coffee-cup doodle and a border line."""
    r = T.rng(seed)
    xx, yy = _grid(size)
    col = _fill(size, "#1e2723")
    haze = T.spectral(size, 2.0, seed, anisotropy=(1.0, 2.5))
    swipe = T.spectral(size, 1.4, seed + 1, anisotropy=(1.0, 12.0))
    col = T.mix(col, _fill(size, "#58625c"), np.clip(T.smoothstep(0.45, 1.0, haze) * 0.5 + T.smoothstep(0.6, 1.0, swipe) * 0.25, 0, 1))
    chalk = np.zeros((size, size), np.float32)
    # border
    m = 40
    for a, b in (((m, m), (size - m, m)), ((size - m, m), (size - m, size - m)), ((size - m, size - m), (m, size - m)),
                 ((m, size - m), (m, m))):
        _polyline(chalk, [a, b], 2.2)
    # heading scribble (big)
    _polyline(chalk, _scribble_line(r, 230, 120, 560, 14, 6), 4.5)
    _polyline(chalk, _scribble_line(r, 300, 175, 420, 6, 5), 1.8)
    # menu rows: item scribble + dotted leader + price blob
    y = 260
    while y < size - 140:
        ln = r.uniform(220, 420)
        _polyline(chalk, _scribble_line(r, 90, y, ln, 7, 4), 2.6)
        for dx in np.arange(90 + ln + 20, size - 220, 22):
            _polyline(chalk, [(dx, y + 6), (dx + 3, y + 6)], 1.8)
        _polyline(chalk, _scribble_line(r, size - 200, y, 90, 8, 5), 3.2)
        y += r.uniform(62, 80)
    # coffee cup doodle
    cx, cy = size - 170, size - 110
    pts = [(cx - 40 + 80 * t, cy - 30 + 6 * np.sin(t * 3)) for t in np.linspace(0, 1, 8)]
    _polyline(chalk, [(cx - 40, cy - 30), (cx - 32, cy + 30), (cx + 32, cy + 30), (cx + 40, cy - 30)], 2.5)
    _polyline(chalk, pts, 2.5)
    _polyline(chalk, [(cx + 40 + 18 * np.cos(a), cy + 18 * np.sin(a)) for a in np.linspace(-1.4, 1.4, 8)], 2.5)
    for k in range(3):
        _polyline(chalk, [(cx - 15 + k * 15 + 6 * np.sin(t * 6), cy - 45 - t * 40) for t in np.linspace(0, 1, 7)], 1.6)
    grain = T.spectral(size, 0.3, seed + 5)
    chalk *= (0.55 + 0.6 * grain)
    col = T.mix(col, _fill(size, "#e8e6dc"), np.clip(chalk, 0, 1))
    r_map = np.clip(0.86 + 0.08 * chalk, 0, 1)
    T.save_pbr_set(out, np.clip(col, 0, 1), haze * 0.1 + chalk * 0.05, r_map, normal_strength=0.6)


@texture("pi_cork", size=512, seed=4531)
def pi_cork(size: int, seed: int, out) -> None:
    f1, f2, cid = T.worley(size, 4000, seed, jitter=1.0)
    gran = (np.sin(cid * 7.13) * 4375.85) % 1.0
    col = T.gradient(T.normalize(gran * 0.7 + 0.3 * T.spectral(size, 1.8, seed + 1)),
                     [(0.0, "#6e4a2a"), (0.5, "#a77a4a"), (1.0, "#c99d68")])
    col *= (0.75 + 0.25 * T.smoothstep(0.0, 3.0, f2 - f1))[..., None]
    T.save_pbr_set(out, np.clip(col, 0, 1), T.normalize(gran + T.smoothstep(0.0, 3.0, f2 - f1)),
                   np.full((size, size), 0.95, np.float32), normal_strength=3.5)


@texture("pi_paper_notes", size=512, seed=4541)
def pi_paper_notes(size: int, seed: int, out) -> None:
    """2x2 atlas of pinned papers: lined note, flyer with photo block, yellow sticky, crayon drawing."""
    r = T.rng(seed)
    n = size // 2
    col = np.zeros((size, size, 3), np.float32)
    for k in range(4):
        cy, cx = divmod(k, 2)
        yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
        ink = np.zeros((n, n), np.float32)
        if k == 0:
            c = np.ones((n, n, 3), np.float32) * T.hex_rgb("#e9e4d6")
            c = T.mix(c, np.ones_like(c) * T.hex_rgb("#9db4c8"), ((yy % 14) < 1.2).astype(np.float32) * (yy > 30))
            c = T.mix(c, np.ones_like(c) * T.hex_rgb("#c98a8a"), (np.abs(xx - 34) < 1.0).astype(np.float32))
            for y in range(44, n - 20, 14):
                if r.random() < 0.85:
                    _polyline(ink, _scribble_line(r, 40, y - 4, r.uniform(80, 190), 2.5, 3), 0.9)
            c = T.mix(c, np.ones_like(c) * T.hex_rgb("#283a6a"), ink * 0.85)
        elif k == 1:
            c = np.ones((n, n, 3), np.float32) * T.hex_rgb("#efece4")
            photo = _rect_mask(xx, yy, 50, 50, n - 50, 150)
            c = T.mix(c, np.ones_like(c) * T.hex_rgb("#4a4642") * (0.7 + 0.3 * T.spectral(n, 2.0, seed + k)[..., None]), photo)
            bar = _rect_mask(xx, yy, 40, 14, n - 40, 36)
            c = T.mix(c, np.ones_like(c) * T.hex_rgb("#1a1a1a"), bar)
            for y in range(170, n - 20, 16):
                _polyline(ink, _scribble_line(r, 40, y, r.uniform(120, 170), 2.0, 3), 1.0)
            c = T.mix(c, np.ones_like(c) * T.hex_rgb("#2a2a2a"), ink * 0.8)
        elif k == 2:
            c = np.ones((n, n, 3), np.float32) * T.hex_rgb("#e8d77a")
            for y in range(50, n - 30, 26):
                _polyline(ink, _scribble_line(r, 36, y, r.uniform(90, 170), 4.0, 4), 1.6)
            c = T.mix(c, np.ones_like(c) * T.hex_rgb("#2a2a40"), ink * 0.85)
        else:
            c = np.ones((n, n, 3), np.float32) * T.hex_rgb("#f2efe6")
            house = [(60, 170), (60, 110), (110, 70), (160, 110), (160, 170), (60, 170)]
            _polyline(ink, house, 2.4)
            sun = [(200 + 22 * np.cos(a), 60 + 22 * np.sin(a)) for a in np.linspace(0, 6.3, 12)]
            _polyline(ink, sun, 2.4)
            for fx in (190, 222):  # two stick figures holding hands
                _polyline(ink, [(fx, 160), (fx, 205)], 2.4)
                _polyline(ink, [(fx - 14, 172), (fx + 14, 172)], 2.4)
                _polyline(ink, [(fx, 205), (fx - 9, 232)], 2.4)
                _polyline(ink, [(fx, 205), (fx + 9, 232)], 2.4)
                _polyline(ink, [(fx + 9 * np.cos(t), 148 + 9 * np.sin(t)) for t in np.linspace(0, 6.3, 9)], 2.0)
            c = T.mix(c, np.ones_like(c) * T.hex_rgb("#a83a2a"), ink * 0.9)
        col[cy * n:(cy + 1) * n, cx * n:(cx + 1) * n] = c
    grime = T.spectral(size, 2.0, seed + 9)
    col *= (0.86 + 0.14 * grime[..., None])
    T.save_pbr_set(out, np.clip(col, 0, 1), grime * 0.2, np.full((size, size), 0.85, np.float32), normal_strength=0.8)


@texture("pi_pegboard", size=512, seed=4551)
def pi_pegboard(size: int, seed: int, out) -> None:
    """Tempered hardboard pegboard: brown fibre board with a 1-inch grid of holes (16 holes per tile ->
    a tile is ~0.4 m at uv_scale 2.5)."""
    xx, yy = _grid(size)
    n = 16
    cs = size / n
    dx = (xx % cs) - cs / 2
    dy = (yy % cs) - cs / 2
    rr = np.hypot(dx, dy)
    hole = np.clip((cs * 0.16 - rr) / 1.2 + 0.5, 0, 1)
    rim = np.clip((cs * 0.22 - rr) / 1.5 + 0.5, 0, 1) - hole
    fib = T.spectral(size, 1.0, seed)
    cloud = T.spectral(size, 2.4, seed + 1)
    col = T.gradient(T.normalize(0.6 * fib + 0.4 * cloud), [(0.0, "#5e4630"), (0.5, "#755a3d"), (1.0, "#8a6c4a")])
    col = T.mix(col, _fill(size, "#140e0a"), hole)
    col *= (1.0 - 0.15 * rim)[..., None]
    h = T.normalize(0.2 * fib - hole)
    T.save_pbr_set(out, np.clip(col, 0, 1), h, np.clip(0.75 + 0.1 * fib, 0, 1), normal_strength=2.5)
