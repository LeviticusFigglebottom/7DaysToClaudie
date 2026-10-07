"""POI building kit textures (docs/POI_KIT.md).

Finish texture ARRAYS (Texture2DArray, vertical strip, 1024 px slices, slice order = the lists below and
game/data/materials/kit_finishes.json, never reorder):
  kit_wall_finishes_{albedo,normal,orm}   1 m per tile  (siding 10 cm exposure, 16 brick courses / m)
  kit_floor_finishes_{albedo,normal,orm}  2 m per tile
Decay masks (kit_wall.gdshader builds every stain, drip, grime gradient, mould colony and paint peel
from them in world space, so the finishes themselves stay clean and tile without visible repeats):
  kit_decay_albedo  RGBA uniform coverage priorities: grime, water stains + drips, mould, peel (2.5 m tile)
  kit_decay_orm     RGB detail: macro tone, substrate grain + cracks, scuff strokes
(The file names predate the masks; poi_parts.gd loads them by these names.)
Standard PBR sets: kit_plaster (preview for kit_wall / kit_floor), kit_trim, door_wood, glass (RGBA),
wood_raw, kit_stairs, concrete, brick, metal_painted, kit_wall_inner. Wood textures run the grain along U.

Every finish function returns a Finish (albedo sRGB float HxWx3, height [0,1], roughness, metallic) and
is tileable and deterministic for (size, seed).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import scipy.fft as sfft
from scipy import ndimage

from .. import texlib as T
from ..registry import texture

WALL_FINISHES = [
    "plaster_white", "plaster_grey", "paint_mustard", "paint_sage", "paint_slate_blue",
    "wallpaper_floral_rose", "wallpaper_stripe_green", "wallpaper_damask_brown", "wood_paneling_dark",
    "tile_bathroom_white", "tile_kitchen_check", "siding_white", "siding_pale_blue", "siding_barn_red",
    "brick_red", "concrete_block",
]
FLOOR_FINISHES = [
    "wood_oak", "wood_pine", "carpet_brown", "carpet_blue_worn", "linoleum_check", "linoleum_beige",
    "tile_white_small", "concrete",
]
# Rock finishes for mine drifts and caves, appended after the house finishes (textures/gen/kit_rock.py).
from .kit_rock import ROCK_FINISH_FNS, ROCK_FLOOR_FINISHES, ROCK_WALL_FINISHES, rock_finish  # noqa: E402
WALL_FINISHES += ROCK_WALL_FINISHES
FLOOR_FINISHES += ROCK_FLOOR_FINISHES
# Log walls (TD-236), after the rock finishes (textures/gen/kit_log.py).
from .kit_log import LOG_FINISH_FNS, LOG_WALL_FINISHES, log_finish  # noqa: E402
WALL_FINISHES += LOG_WALL_FINISHES
_ROCK_SOURCES = ["tools/assetgen/textures/gen/kit_rock.py"]
_WALL_SOURCES = _ROCK_SOURCES + ["tools/assetgen/textures/gen/kit_log.py"]


def _check_slice_order() -> None:
    """The slice order is a contract with the POI builder (game/data/materials/kit_finishes.json)."""
    import json
    import pathlib
    f = pathlib.Path(__file__).resolve().parents[4] / "game" / "data" / "materials" / "kit_finishes.json"
    if f.exists():
        data = json.loads(f.read_text())
        if data.get("wall") != WALL_FINISHES or data.get("floor") != FLOOR_FINISHES:
            raise ValueError("kit finish slice order differs from game/data/materials/kit_finishes.json")


_check_slice_order()


_AMP_CACHE: dict = {}


@dataclass
class Finish:
    albedo: np.ndarray
    height: np.ndarray
    rough: np.ndarray
    metal: np.ndarray | float = 0.0
    normal_strength: float = 4.0
    ao_strength: float = 1.0


# =================================================================================================
# Helpers (all periodic)
# =================================================================================================

def _coords(size: int, tile: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """Pixel-centre coordinates in metres (x right, y down the image)."""
    c = (np.arange(size, dtype=np.float32) + 0.5) / size * tile
    return c[None, :].repeat(size, 0), c[:, None].repeat(size, 1)


def _col(h: str) -> np.ndarray:
    return T.hex_rgb(h)[None, None, :]


def _hash(*v) -> float:
    """Deterministic pseudo-random [0,1) from integers."""
    x = 0x9E3779B9
    for k in v:
        x = (x ^ (int(k) & 0xFFFFFFFF)) * 0x85EBCA6B & 0xFFFFFFFF
        x ^= x >> 13
    return (x & 0xFFFFFF) / float(0x1000000)


def _hash_arr(k, salt: int) -> np.ndarray:
    """Vectorized deterministic pseudo-random [0,1) per integer (works on scalars and arrays)."""
    x = (np.asarray(k).astype(np.uint64) * np.uint64(0x9E3779B1) + np.uint64((salt * 0x85EBCA6B) & 0xFFFFFFFF))
    x &= np.uint64(0xFFFFFFFF)
    x ^= x >> np.uint64(15)
    x = (x * np.uint64(0x2C1B3C6D)) & np.uint64(0xFFFFFFFF)
    x ^= x >> np.uint64(12)
    x = (x * np.uint64(0x297A2D39)) & np.uint64(0xFFFFFFFF)
    x ^= x >> np.uint64(15)
    return ((x & np.uint64(0xFFFFFF)).astype(np.float64) / float(0x1000000)).astype(np.float32)


def _sn(size: int, beta: float, seed: int, aniso=(1.0, 1.0), fmin: float = 1.0, fmax: float | None = None) -> np.ndarray:
    """Tileable 1/f^beta noise in [0,1] (same parameters as texlib.spectral, ~8x faster: cached
    amplitude grid, single-precision real FFT)."""
    amp = _amp_grid(size, float(beta), float(aniso[0]), float(aniso[1]), float(fmin), None if fmax is None else float(fmax))
    r = np.random.default_rng(seed & 0xFFFFFFFF)
    ph = r.random(amp.shape, dtype=np.float32) * np.float32(2 * np.pi)
    spec = (amp * np.cos(ph)) + 1j * (amp * np.sin(ph))
    out = sfft.irfft2(spec.astype(np.complex64), s=(size, size))
    return T.normalize(out)


def _warp(field: np.ndarray, seed: int, amount: float, beta: float = 2.2) -> np.ndarray:
    s = field.shape[0]
    return T.warp(field, _sn(s, beta, seed), _sn(s, beta, seed + 1), amount)


def _wrapdist_x(x: np.ndarray, pos: np.ndarray, period: float) -> np.ndarray:
    """Distance (periodic) from x to the nearest of positions `pos` (1D)."""
    d = np.abs(x[..., None] - pos[None, None, :]) % period
    return np.minimum(d, period - d).min(-1)


def _peel(size: int, seed: int, coverage: float, *, aniso=(1.0, 1.0), scale_beta: float = 1.8, sharp: float = 0.03,
          warp: float = 6.0) -> tuple[np.ndarray, np.ndarray]:
    """Peeling-paint mask (1 = paint gone) and an edge ring (lifted / curled paint edge)."""
    n = 0.75 * _sn(size, scale_beta, seed, aniso) + 0.25 * _sn(size, 1.0, seed + 7, aniso)
    n = _warp(n, seed + 3, warp)
    t = float(np.quantile(n, 1.0 - coverage)) if coverage > 0 else 2.0
    m = T.smoothstep(t - sharp, t + sharp, n)
    ring = T.smoothstep(t - 0.06, t - sharp * 0.2, n) * (1.0 - m)
    return m.astype(np.float32), ring.astype(np.float32)


def _cracks(size: int, seed: int, cells: int, width: float, keep: float, warp: float = 14.0) -> np.ndarray:
    """Meandering hairline cracks: level set (0.5) of a warped band-limited noise, kept where a coarse
    mask allows (`keep` = fraction of the network). `cells` sets the crack density, `width` ~ pixels."""
    f0 = max(1.0, math.sqrt(cells) * 0.8)
    n = _sn(size, 2.8, seed, fmin=f0)
    n = _warp(n, seed + 2, warp * 0.35, beta=0.9)          # small-scale jaggedness only
    gy, gx = np.gradient(n)
    g = np.sqrt(gx * gx + gy * gy) + 1e-6
    d = np.abs(n - 0.5) / g
    line = 1.0 - T.smoothstep(0.0, width, d)
    sel = T.smoothstep(1 - keep - 0.04, 1 - keep + 0.04, _sn(size, 2.0, seed + 1))
    return np.clip(line * sel, 0, 1).astype(np.float32)


def _grain(size: int, seed: int, tile: float, *, rings_per_m: float = 60.0, figure: float = 0.4,
           v_off: np.ndarray | float = 0.0, u_off: np.ndarray | float = 0.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Flat-sawn wood grain running along X. `figure` scales how far the growth rings wander (gentle
    cathedral arcs). Returns (late-wood tone 0..1, fibre streaks, pores)."""
    x, y = _coords(size, tile)
    n_rings = max(1, round(rings_per_m * tile))
    sp = tile / n_rings
    w1 = _sn(size, 2.4, seed, (1.0, 3.0))
    w2 = _sn(size, 1.4, seed + 1, (1.0, 8.0))
    disp = (w1 - 0.5) * sp * (2.0 + 10.0 * figure) + (w2 - 0.5) * sp * 0.8
    n_arc = max(1, round(tile / 0.45))
    arc = np.sin((x + u_off) / tile * 2 * np.pi * n_arc + w1 * 4.0) * sp * 3.0 * figure
    r = (y + v_off + disp + arc) / sp
    p = r - np.floor(r)
    late = T.smoothstep(0.6, 0.82, p) * (1.0 - T.smoothstep(0.9, 1.0, p))
    fib = _sn(size, 0.9, seed + 2, (1.0, 14.0))
    pores = (_sn(size, 0.3, seed + 3, (1.0, 8.0)) > 0.8).astype(np.float32)
    return late.astype(np.float32), fib, pores


def _boards(size: int, tile: float, board_w: float, seed: int, *, min_len: float, max_len: float, vertical: bool = False,
            gap: float = 0.001) -> dict:
    """Board layout along X (or Y with vertical=True): rows of boards with random butt joints.
    Returns per-pixel: row, piece id, distance to joints / row edges (m), position inside the row (0..1)."""
    rng = T.rng(seed)
    n_rows = max(1, int(round(tile / board_w)))
    bw = tile / n_rows
    x, y = _coords(size, tile)
    if vertical:
        x, y = y, x
    row = np.minimum((y / bw).astype(np.int32), n_rows - 1)
    vin = (y - row * bw) / bw
    piece = np.zeros((size, size), np.int32)
    jd = np.full((size, size), 9.0, np.float32)
    for r in range(n_rows):
        lens = []
        while sum(lens) < tile:
            lens.append(rng.uniform(min_len, max_len))
        lens = np.array(lens) * (tile / sum(lens))
        off = rng.uniform(0, tile)
        bounds = (off + np.concatenate([[0.0], np.cumsum(lens)[:-1]])) % tile
        m = row == r
        xs = x[m]
        rel = (xs - off) % tile
        idx = np.searchsorted(np.cumsum(lens), rel, side="right")
        piece[m] = r * 64 + idx
        d = np.abs(xs[:, None] - bounds[None, :]) % tile
        jd[m] = np.minimum(d, tile - d).min(-1)
    edge = np.minimum(vin, 1.0 - vin) * bw
    out = {"row": row, "piece": piece, "joint": jd, "edge": edge, "vin": vin, "bw": bw, "n_rows": n_rows}
    if vertical:
        out = {k: (v.T.copy() if isinstance(v, np.ndarray) else v) for k, v in out.items()}
    return out


def _piece_rand(piece: np.ndarray, salt: int) -> np.ndarray:
    return _hash_arr(piece, salt)


def _grime(size: int, seed: int, amount: float, beta: float = 2.4) -> np.ndarray:
    """Multiplicative low-frequency dirt (1 = clean)."""
    g = _sn(size, beta, seed)
    return (1.0 - amount * T.smoothstep(0.35, 0.95, g)).astype(np.float32)


def _paper(size: int, seed: int) -> np.ndarray:
    return (0.6 * _sn(size, 0.6, seed) + 0.4 * _sn(size, 1.2, seed + 1)).astype(np.float32)


def _stamp_grid(size: int, tile: float, cols: int, rows: int, motif, *, half_drop: bool = True) -> np.ndarray:
    """Evaluates motif(dx, dy) (metres from the motif centre) on a periodic lattice (max over the 4
    nearest lattice points). Returns a [0,1] mask."""
    x, y = _coords(size, tile)
    cw, ch = tile / cols, tile / rows
    out = np.zeros((size, size), np.float32)
    for oi in (-1, 0, 1):
        ci = np.floor(x / cw).astype(np.int32) + oi
        cx = (ci + 0.5) * cw
        drop = np.where((ci % 2 == 1) & half_drop, ch / 2, 0.0)
        for oj in (-1, 0, 1):
            cj = np.floor((y - drop) / ch).astype(np.int32) + oj
            cy = (cj + 0.5) * ch + drop
            out = np.maximum(out, motif(x - cx, y - cy, (ci % cols) * 31 + (cj % rows) * 7))
    return out


def _flakes(size: int, seed: int, coverage: float, *, aniso=(1.0, 1.0), cluster: float = 0.9) -> tuple:
    """Clustered paint flakes. Returns (field, threshold(coverage)) so callers can take nested layers:
    mask = smoothstep(t - e, t + e, field)."""
    cl = _sn(size, 2.2, seed, aniso)
    fine = _warp(_sn(size, 1.25, seed + 1, aniso), seed + 2, 4.0, beta=1.5)
    f = fine + cluster * (cl - 0.5)
    t = float(np.quantile(f, 1.0 - coverage))
    return f.astype(np.float32), t


def _rose(dx: np.ndarray, dy: np.ndarray, R: float, ph: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Printed cabbage rose: (mask, tone 0 light..1 dark, outline) from layered scalloped petal rings."""
    r = np.sqrt(dx * dx + dy * dy)
    a = np.arctan2(dy, dx)
    mask = np.zeros(r.shape, np.float32)
    tone = np.zeros(r.shape, np.float32)
    line = np.zeros(r.shape, np.float32)
    rings = (1.0, 0.76, 0.54, 0.34)
    edges = []
    for i, f in enumerate(rings):
        n = 5 + i
        c = np.abs(np.cos(n * (a + ph * (1 + i)) / 2))
        edges.append(R * f * (0.8 + 0.2 * c ** 0.6))
    for i, e in enumerate(edges):
        inside = (r < e).astype(np.float32)
        inner = edges[i + 1] if i + 1 < len(edges) else e * 0.4
        depth = np.clip((e - r) / np.maximum(1e-4, e - inner), 0, 1)
        tone = np.where(inside > 0, 0.15 + 0.7 * depth ** 1.4 + 0.1 * i, tone)
        line = np.maximum(line, inside * (1.0 - T.smoothstep(0.0, 0.0012, np.abs(r - e))))
        mask = np.maximum(mask, inside)
    centre = 1.0 - T.smoothstep(R * 0.1, R * 0.16, r)
    tone = np.clip(np.maximum(tone, centre), 0, 1)
    return mask, tone, line


def _splat(canvas: np.ndarray, size: int, tile: float, cx: float, cy: float, half: float, fn, mode: str = "max") -> None:
    """Evaluates fn(dx, dy) (metres from the stamp centre) in a window around (cx, cy) and merges it
    into a periodic canvas (indices wrap). mode "max" or "set" (fn returns (mask, value))."""
    px = size / tile
    ix0, ix1 = int(math.floor((cx - half) * px)), int(math.ceil((cx + half) * px))
    iy0, iy1 = int(math.floor((cy - half) * px)), int(math.ceil((cy + half) * px))
    xs = (np.arange(ix0, ix1, dtype=np.float32) + 0.5) / px - cx
    ys = (np.arange(iy0, iy1, dtype=np.float32) + 0.5) / px - cy
    dx, dy = np.meshgrid(xs, ys)
    rows = np.arange(iy0, iy1) % size
    cols = np.arange(ix0, ix1) % size
    sel = np.ix_(rows, cols)
    if mode == "max":
        canvas[sel] = np.maximum(canvas[sel], fn(dx, dy))
    else:
        m, v = fn(dx, dy)
        canvas[sel] = np.where(m > 0, v, canvas[sel])


def _amp_grid(size: int, beta: float, ax: float, ay: float, fmin: float, fmax: float | None) -> np.ndarray:
    key = (size, beta, ax, ay, fmin, fmax)
    hit = _AMP_CACHE.get(key)
    if hit is not None:
        return hit
    fx = np.fft.rfftfreq(size)[None, :] * size / ax
    fy = np.fft.fftfreq(size)[:, None] * size / ay
    f = np.sqrt(fx * fx + fy * fy)
    f[0, 0] = 1.0
    amp = np.power(f, -beta)
    amp[f < fmin] = 0.0
    if fmax is not None:
        amp[f > fmax] = 0.0
    amp[0, 0] = 0.0
    amp = amp.astype(np.float32)
    _AMP_CACHE[key] = amp
    return amp


# =================================================================================================
# Wall finishes (1 m per tile)
# =================================================================================================

def _plaster_core(size: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Trowelled plaster relief (height) and its fine sand."""
    trowel = _warp(_sn(size, 2.8, seed, (1.0, 1.6)), seed + 1, 18.0)
    marks = _sn(size, 1.5, seed + 2, (3.0, 1.0))
    sand = _sn(size, 0.25, seed + 3)
    h = 0.35 * trowel + 0.15 * marks + 0.5 * sand
    return T.normalize(h), sand


def plaster_white(size: int, seed: int) -> Finish:
    h, sand = _plaster_core(size, seed)
    cr = _cracks(size, seed + 10, 7, 1.2, 0.1)
    tone = _sn(size, 2.2, seed + 11)
    col = T.gradient(tone, [(0.0, "#dcd6c9"), (0.5, "#e2ddd1"), (1.0, "#e8e4d9")])
    col *= (0.98 + 0.03 * sand)[..., None]
    f, t = _flakes(size, seed + 12, 0.006)  # large flaking comes from the decay masks
    flake = T.smoothstep(t - 0.008, t + 0.008, f)
    ring = T.smoothstep(t - 0.04, t - 0.008, f) * (1 - flake)
    col = T.mix(col, _col("#c3baa6") * np.ones_like(col), flake * 0.85)
    col *= (1.0 - 0.12 * ring - 0.3 * cr)[..., None]
    col *= _grime(size, seed + 13, 0.05)[..., None]
    height = np.clip(0.45 + 0.35 * h - 0.25 * cr - 0.1 * flake + 0.06 * ring, 0, 1)
    rough = np.clip(0.8 + 0.06 * (sand - 0.5) + 0.08 * flake, 0, 1)
    return Finish(np.clip(col, 0, 1), height, rough, normal_strength=1.8)


def plaster_grey(size: int, seed: int) -> Finish:
    h, sand = _plaster_core(size, seed)
    patches = T.smoothstep(0.6, 0.66, _warp(_sn(size, 2.0, seed + 20), seed + 21, 20.0))  # newer repair patches
    cr = _cracks(size, seed + 22, 6, 1.4, 0.12)
    tone = _sn(size, 1.9, seed + 23)
    col = T.gradient(tone, [(0.0, "#99958c"), (0.5, "#a39f96"), (1.0, "#ada99f")])
    col = T.mix(col, _col("#b6b1a5") * np.ones_like(col), patches * 0.2)
    col *= (0.94 + 0.1 * sand)[..., None]
    col *= (1.0 - 0.3 * cr)[..., None]
    col *= _grime(size, seed + 24, 0.08)[..., None]
    height = np.clip(0.4 + 0.45 * h + patches * 0.04 - cr * 0.3, 0, 1)
    rough = np.clip(0.88 + 0.07 * (sand - 0.5), 0, 1)
    return Finish(np.clip(col, 0, 1), height, rough, normal_strength=2.2)


def _painted_wall(size: int, seed: int, paint: list, peel_cov: float, older: str) -> Finish:
    """Roller-painted plaster: the top coat flakes off in clusters revealing an OLDER paint colour,
    and in the worst spots the bare plaster; lifted flake edges catch light."""
    h, sand = _plaster_core(size, seed)
    stipple = _sn(size, 0.55, seed + 30)
    fade = _sn(size, 2.6, seed + 31)
    col = T.gradient(T.normalize(0.75 * fade + 0.25 * stipple), paint)
    # Only small chips here: the 1 m tile would repeat big peels; the shader peels at room scale.
    peel_cov *= 0.15
    f, t1 = _flakes(size, seed + 32, peel_cov)
    t2 = float(np.quantile(f, 1.0 - peel_cov * 0.35))
    top_gone = T.smoothstep(t1 - 0.006, t1 + 0.006, f)
    all_gone = T.smoothstep(t2 - 0.006, t2 + 0.006, f)
    ring = T.smoothstep(t1 - 0.035, t1 - 0.006, f) * (1 - top_gone)
    old = T.gradient(_sn(size, 1.5, seed + 33), [(0.0, older), (1.0, older)]) * (0.95 + 0.06 * stipple)[..., None]
    plaster = T.gradient(_sn(size, 1.5, seed + 34), [(0.0, "#c9c1b0"), (1.0, "#d9d2c3")])
    col = T.mix(col, old, top_gone)
    col = T.mix(col, plaster, all_gone)
    col *= (1.0 - 0.18 * ring)[..., None]
    cr = _cracks(size, seed + 35, 7, 1.1, 0.08)
    col *= (1.0 - 0.3 * cr)[..., None]
    col *= _grime(size, seed + 36, 0.07)[..., None]
    height = np.clip(0.45 + 0.3 * h + 0.06 * stipple - 0.05 * top_gone - 0.05 * all_gone + 0.07 * ring - 0.25 * cr, 0, 1)
    rough = np.clip(0.58 + 0.08 * (stipple - 0.5) + 0.12 * top_gone + 0.15 * all_gone, 0, 1)
    return Finish(np.clip(col, 0, 1), height, rough, normal_strength=2.6)


def paint_mustard(size: int, seed: int) -> Finish:
    return _painted_wall(size, seed, [(0.0, "#b08a3a"), (0.5, "#c19b48"), (1.0, "#cca95a")], 0.07, "#a7ad95")


def paint_sage(size: int, seed: int) -> Finish:
    return _painted_wall(size, seed, [(0.0, "#7f8a6e"), (0.5, "#8c987b"), (1.0, "#98a387")], 0.06, "#d6cfb8")


def paint_slate_blue(size: int, seed: int) -> Finish:
    return _painted_wall(size, seed, [(0.0, "#536173"), (0.5, "#5e6d7f"), (1.0, "#69788a")], 0.08, "#c7b58a")


def _wallpaper(size: int, seed: int, pattern_rgb: np.ndarray, pattern_h: np.ndarray, *, gloss: np.ndarray | None = None
               ) -> Finish:
    """Common wallpaper treatment: paper fibre, 0.5 m roll seams (slightly open, lifting), aging,
    foxing spots, a few torn patches exposing older paper / plaster with glue stains."""
    x, y = _coords(size, 1.0)
    paper = _paper(size, seed + 40)
    seams = _wrapdist_x(x, np.array([0.0, 0.5]), 1.0)
    seam_line = 1.0 - T.smoothstep(0.0005, 0.0015, seams)
    lift = (1.0 - T.smoothstep(0.0, 0.01, seams)) * T.smoothstep(0.6, 0.85, _sn(size, 2.2, seed + 41, (6.0, 1.0)))
    age = _sn(size, 2.4, seed + 42)
    fox = (T.smoothstep(0.8, 0.87, _sn(size, 1.1, seed + 43)) * 0.6).astype(np.float32)
    f, t = _flakes(size, seed + 44, 0.004, cluster=1.2)  # torn patches come from the decay masks
    tear = T.smoothstep(t - 0.004, t + 0.004, f)
    ring = T.smoothstep(t - 0.02, t - 0.004, f) * (1 - tear)
    col = pattern_rgb * (0.95 + 0.07 * paper)[..., None]
    yellow = _col("#c8b27a") * np.ones_like(col)
    col = T.mix(col, col * 0.78 + yellow * 0.22, T.smoothstep(0.3, 0.9, age) * 0.8)
    col = T.mix(col, _col("#8c6a3e") * np.ones_like(col), fox * 0.18)
    col *= (1.0 - 0.4 * seam_line - 0.1 * lift)[..., None]
    under = T.gradient(_sn(size, 1.6, seed + 45), [(0.0, "#a99f8b"), (0.6, "#c2b8a3"), (1.0, "#cfc5b0")])
    glue = T.smoothstep(0.5, 0.8, _sn(size, 1.2, seed + 47))
    under = T.mix(under, _col("#9a8059") * np.ones_like(under), glue * 0.35)
    col = T.mix(col, under, tear)
    col *= (1.0 - 0.25 * ring)[..., None]
    col *= _grime(size, seed + 46, 0.06)[..., None]
    height = np.clip(0.5 + 0.1 * paper + 0.1 * pattern_h - 0.25 * seam_line + 0.15 * lift - 0.12 * tear + 0.12 * ring,
                     0, 1)
    rough = np.clip(0.78 + 0.08 * (paper - 0.5) + 0.08 * tear - (0.0 if gloss is None else 0.25 * gloss), 0, 1)
    return Finish(np.clip(col, 0, 1), height, rough, normal_strength=2.5)


def wallpaper_floral_rose(size: int, seed: int) -> Finish:
    """Trailing-rose wallpaper: meandering vertical vines with alternating leaves, cabbage roses and buds
    (half-drop between neighbouring vines), faint ticking stripes on a cream ground."""
    x, y = _coords(size, 1.0)
    cols, lam, amp = 8, 0.25, 0.022
    cw = 1.0 / cols
    stems = np.zeros((size, size), np.float32)
    leaves = np.zeros((size, size), np.float32)
    midrib = np.zeros((size, size), np.float32)
    rose_m = np.zeros((size, size), np.float32)
    rose_t = np.zeros((size, size), np.float32)
    rose_l = np.zeros((size, size), np.float32)
    bud = np.zeros((size, size), np.float32)
    for i in range(cols):
        phase = (i % 2) * lam / 2
        cx = (i + 0.5) * cw

        def vx(yy, cx=cx, phase=phase):
            return cx + amp * np.sin(2 * np.pi * (yy + phase) / lam)

        dx = (x - vx(y) + 0.5) % 1.0 - 0.5
        slope = amp * 2 * np.pi / lam * np.cos(2 * np.pi * (y + phase) / lam)
        stems = np.maximum(stems, 1.0 - T.smoothstep(0.0009, 0.0016, np.abs(dx) / np.sqrt(1 + slope * slope)))
        n_leaf = int(round(1.0 / lam)) * 4
        for k in range(n_leaf):
            yk = (k + 0.25) * lam / 4
            xk = float(vx(yk))
            side = 1 if k % 2 == 0 else -1
            tang = math.atan2(1.0, amp * 2 * math.pi / lam * math.cos(2 * math.pi * (yk + phase) / lam))
            ang = tang + side * 0.75 + (_hash(i, k, seed) - 0.5) * 0.4
            lx, ly = xk + math.cos(ang) * 0.016, yk + math.sin(ang) * 0.016
            ca, sa = math.cos(ang), math.sin(ang)

            def leaf(ddx, ddy, ca=ca, sa=sa):
                u = ddx * ca + ddy * sa
                v = -ddx * sa + ddy * ca
                return (np.abs(v) < 0.0075 * np.clip(1 - (u / 0.017) ** 2, 0, 1) ** 0.8).astype(np.float32)

            def rib(ddx, ddy, ca=ca, sa=sa):
                u = ddx * ca + ddy * sa
                v = -ddx * sa + ddy * ca
                return ((np.abs(v) < 0.0007) & (np.abs(u) < 0.015)).astype(np.float32)

            _splat(leaves, size, 1.0, lx, ly, 0.02, leaf)
            _splat(midrib, size, 1.0, lx, ly, 0.02, rib)
        for kk in range(int(round(1.0 / lam))):
            ry = kk * lam + lam * 0.5 - phase
            rx = float(vx(ry))
            ph = _hash(i, kk, seed + 1) * 6.28
            _splat(rose_m, size, 1.0, rx, ry, 0.03, lambda a, b, ph=ph: _rose(a, b, 0.024, ph)[0])
            _splat(rose_t, size, 1.0, rx, ry, 0.03, lambda a, b, ph=ph: _rose(a, b, 0.024, ph)[:2], mode="set")
            _splat(rose_l, size, 1.0, rx, ry, 0.03, lambda a, b, ph=ph: _rose(a, b, 0.024, ph)[2])
            by = ry + lam * 0.5
            bx = float(vx(by)) + 0.012
            _splat(bud, size, 1.0, bx, by, 0.012,
                   lambda a, b: (((a / 0.0065) ** 2 + (b / 0.009) ** 2) < 1).astype(np.float32))
    ground = T.gradient(_sn(size, 2.0, seed + 50), [(0.0, "#e0d4bb"), (1.0, "#e9ddc4")])
    tick = 0.5 + 0.5 * np.cos(x * 2 * np.pi * 64)
    ground *= (0.985 + 0.02 * tick)[..., None]
    aa = lambda m: ndimage.gaussian_filter(m, 0.55, mode="wrap")  # noqa: E731
    stems, leaves, midrib, rose_m, bud, rose_l = (aa(v) for v in (stems, leaves, midrib, rose_m, bud, rose_l))
    col = ground
    col = T.mix(col, _col("#7d8656") * np.ones_like(col), stems * 0.9)
    leafc = T.gradient(_sn(size, 1.2, seed + 52), [(0.0, "#748660"), (1.0, "#93a27a")])
    col = T.mix(col, leafc, leaves)
    col = T.mix(col, _col("#566444") * np.ones_like(col), midrib * 0.8)
    rosec = T.gradient(np.clip(rose_t, 0, 1), [(0.0, "#e3b0a6"), (0.45, "#c88780"), (0.8, "#a1605e"), (1.0, "#7b4246")])
    col = T.mix(col, rosec, rose_m)
    col = T.mix(col, _col("#7b4246") * np.ones_like(col), rose_l * 0.6)
    col = T.mix(col, _col("#b9716c") * np.ones_like(col), bud)
    ph_ = np.clip(rose_m * 0.8 + leaves * 0.5 + bud * 0.4, 0, 1)
    return _wallpaper(size, seed, col, ph_)


def wallpaper_stripe_green(size: int, seed: int) -> Finish:
    x, _ = _coords(size, 1.0)
    period = 1.0 / 16
    u = (x % period) / period
    wide = (u < 0.46).astype(np.float32)
    pin1 = ((u > 0.56) & (u < 0.59)).astype(np.float32)
    pin2 = ((u > 0.85) & (u < 0.88)).astype(np.float32)
    aa = lambda m: ndimage.gaussian_filter(m, 0.6, mode="wrap")  # noqa: E731
    wide, pin1, pin2 = aa(wide), aa(pin1), aa(pin2)
    mid = T.gradient(_sn(size, 2.0, seed + 60), [(0.0, "#7d9a7c"), (1.0, "#8ba887")])
    col = mid
    dark = T.gradient(_sn(size, 1.4, seed + 61, (1.0, 4.0)), [(0.0, "#2f4c3a"), (1.0, "#3b5a45")])
    col = T.mix(col, dark, wide)
    col = T.mix(col, _col("#e3dcc4") * np.ones_like(col), pin1 * 0.9 + pin2 * 0.9)
    # moire-like satin texture inside the wide stripes
    sat = _sn(size, 0.8, seed + 62, (1.0, 10.0))
    col *= (1.0 + 0.05 * (sat - 0.5) * wide)[..., None]
    return _wallpaper(size, seed, col, wide * 0.3, gloss=wide * 0.5)


def wallpaper_damask_brown(size: int, seed: int) -> Finish:
    """Tone-on-tone damask: mirror-symmetric filigree medallions (contour scrolls inside an ogee outline)
    on a half-drop lattice, with small diamond fleurons between them; the figure is satin (glossier)."""
    rng = T.rng(seed + 70)
    ms = 384
    f = T.blur(rng.random((ms, ms)).astype(np.float32), 14.0)
    f = T.normalize(f + 0.45 * T.normalize(T.blur(rng.random((ms, ms)).astype(np.float32), 6.0)))
    f = np.maximum(f, f[:, ::-1])                       # bilateral symmetry
    yy, xx = np.mgrid[0:ms, 0:ms].astype(np.float32) / ms * 2 - 1
    ax = np.abs(xx)
    prof = 0.86 * np.clip(1 - yy ** 2, 0, 1) ** 0.75 * (1 - 0.35 * np.clip(-yy, 0, 1))   # ogee / teardrop
    e = ax / np.maximum(prof, 1e-3)
    env = 1.0 - T.smoothstep(0.9, 1.0, e)
    outline = (np.abs(e - 0.93) < 0.035).astype(np.float32) * (np.abs(yy) < 0.97)
    contours = (np.abs((f * 7.0) % 1.0 - 0.5) > 0.38).astype(np.float32)
    fill = T.smoothstep(0.66, 0.7, f)
    spine = ((ax < 0.025) & (np.abs(yy) < 0.75)).astype(np.float32)
    motif_img = np.clip((contours * 0.9 + fill) * env + outline + spine, 0, 1)
    motif_img = ndimage.gaussian_filter(motif_img, 0.8)

    def sample(dx, dy, w, h):
        u = np.clip((dx / w * 0.5 + 0.5) * (ms - 1), 0, ms - 1).astype(np.int32)
        v = np.clip((dy / h * 0.5 + 0.5) * (ms - 1), 0, ms - 1).astype(np.int32)
        inside = (np.abs(dx) < w) & (np.abs(dy) < h)
        return np.where(inside, motif_img[v, u], 0.0).astype(np.float32)

    big = _stamp_grid(size, 1.0, 4, 3, lambda dx, dy, k: sample(dx, dy, 0.1, 0.15))

    def fleuron(dx, dy, k):
        d = np.abs(dx) / 0.02 + np.abs(dy - 0.1667) / 0.035
        d2 = np.abs(dx) / 0.02 + np.abs(dy + 0.1667) / 0.035
        return np.maximum((d < 1).astype(np.float32), (d2 < 1).astype(np.float32))

    small = _stamp_grid(size, 1.0, 4, 3, fleuron)
    m = np.clip(big + small, 0, 1)
    ground = T.gradient(_sn(size, 2.0, seed + 71), [(0.0, "#56412f"), (1.0, "#624b38")])
    fig = T.gradient(_sn(size, 1.5, seed + 72), [(0.0, "#836548"), (1.0, "#957657")])
    sheen = _sn(size, 1.0, seed + 73, (1.0, 6.0))
    fig *= (0.95 + 0.1 * sheen)[..., None]
    col = T.mix(ground, fig, m)
    return _wallpaper(size, seed, col, m * 0.4, gloss=m * 0.8)


def wood_paneling_dark(size: int, seed: int) -> Finish:
    x, y = _coords(size, 1.0)
    rng = T.rng(seed + 80)
    pos = [0.0]
    while True:
        nxt = pos[-1] + rng.choice([0.1016, 0.1524, 0.2032]) * rng.uniform(0.97, 1.03)
        if nxt > 0.94:
            break
        pos.append(nxt)
    pos = np.array(pos, np.float32)
    d = _wrapdist_x(x, pos, 1.0)
    groove = 1.0 - T.smoothstep(0.0012, 0.0032, d)
    idx = np.searchsorted(pos, x % 1.0, side="right")
    late, fib, pores = _grain(size, seed + 81, 1.0, rings_per_m=90.0, figure=0.5, v_off=idx.T * 0.137)
    late_v, fib_v, pores_v = late.T, fib.T, pores.T
    pr = _hash_arr(idx, seed)
    tone = T.normalize(0.5 * late_v + 0.35 * fib_v + 0.15 * pr)
    base = T.gradient(tone, [(0.0, "#5f3f27"), (0.5, "#4a301d"), (1.0, "#2e1c11")])
    base *= (0.9 + 0.18 * pr)[..., None]
    base *= (1.0 - 0.2 * pores_v)[..., None]
    col = T.mix(base, _col("#1a100a") * np.ones_like(base), groove)
    col *= _grime(size, seed + 82, 0.1)[..., None]
    scuff = T.smoothstep(0.84, 0.93, _sn(size, 1.0, seed + 83, (4.0, 1.0)))
    col = T.mix(col, col * 1.3 + 0.03, scuff * 0.35)
    warp_bulge = T.smoothstep(0.7, 0.9, _sn(size, 2.6, seed + 84, (1.0, 3.0)))   # delaminating veneer
    col = T.mix(col, col * 0.85 + _col("#6b5a45") * 0.15, warp_bulge * 0.5)
    height = np.clip(0.6 + 0.06 * fib_v - 0.5 * groove - 0.04 * pores_v + 0.08 * warp_bulge, 0, 1)
    rough = np.clip(0.42 + 0.1 * fib_v + 0.3 * groove + 0.2 * scuff + 0.15 * warp_bulge, 0, 1)
    return Finish(np.clip(col, 0, 1), height, rough, normal_strength=3.5)


def _tiles(size: int, seed: int, tile: float, n: int, grout_w: float, colors, *, check: bool = False,
           grout_col: str = "#a8a396", gloss: float = 0.1, crack_frac: float = 0.04) -> Finish:
    x, y = _coords(size, tile)
    p = tile / n
    gx = (x % p) / p
    gy = (y % p) / p
    ix = np.floor(x / p).astype(np.int32)
    iy = np.floor(y / p).astype(np.int32)
    tid = (iy % n) * n + (ix % n)
    dist = np.minimum(np.minimum(gx, 1 - gx), np.minimum(gy, 1 - gy)) * p
    grout = 1.0 - T.smoothstep(grout_w * 0.5, grout_w * 0.5 + 0.0012, dist)
    pillow = T.smoothstep(grout_w * 0.5, grout_w * 0.5 + 0.004, dist)
    tr = _hash_arr(tid, seed)
    if check:
        which = ((ix + iy) % 2).astype(np.float32)
        base = T.mix(_col(colors[0]) * np.ones((size, size, 3), np.float32), _col(colors[1]) * np.ones((size, size, 3), np.float32), which)
    else:
        base = _col(colors[0]) * np.ones((size, size, 3), np.float32)
    base *= (0.96 + 0.06 * tr)[..., None]
    glaze = _sn(size, 2.0, seed + 90)
    base *= (0.98 + 0.04 * glaze)[..., None]
    # cracked tiles
    cr = _cracks(size, seed + 91, 30, 1.2, crack_frac * 3)
    crt = (_hash_arr(tid, seed + 5) < crack_frac).astype(np.float32)
    crk = cr * crt
    dirt = T.smoothstep(0.3, 0.9, _sn(size, 2.0, seed + 92))
    gcol = T.mix(_col(grout_col) * np.ones_like(base), _col("#5f5a4f") * np.ones_like(base), dirt * 0.7)
    col = T.mix(base, gcol, grout)
    col *= (1.0 - 0.5 * crk)[..., None]
    col *= _grime(size, seed + 93, 0.08)[..., None]
    tilt = (tr - 0.5) * 0.04 * (gx - 0.5) + (_hash_arr(tid, seed + 7) - 0.5) * 0.04 * (gy - 0.5)
    height = np.clip(0.45 + 0.4 * pillow + tilt - 0.3 * crk, 0, 1)
    rough = np.clip(gloss + 0.04 * glaze + grout * (0.85 - gloss) + 0.2 * crk + 0.15 * dirt * grout, 0, 1)
    return Finish(np.clip(col, 0, 1), height.astype(np.float32), rough, normal_strength=5.0)


def tile_bathroom_white(size: int, seed: int) -> Finish:
    return _tiles(size, seed, 1.0, 10, 0.003, ["#e9e7e0"], grout_col="#b4ae9f", gloss=0.08)


def tile_kitchen_check(size: int, seed: int) -> Finish:
    return _tiles(size, seed, 1.0, 10, 0.003, ["#e3dcc8", "#3c6450"], check=True, grout_col="#a59f90", gloss=0.12)


def _siding(size: int, seed: int, paint: list, *, peel_cov: float = 0.025) -> Finish:
    x, y = _coords(size, 1.0)
    b = _boards(size, 1.0, 0.1, seed + 100, min_len=1.2, max_len=4.5)
    v = b["vin"]                     # 0 at the top of a board, 1 at its butt edge
    late, fib, pores = _grain(size, seed + 101, 1.0, rings_per_m=60, figure=0.5, v_off=b["row"] * 0.31)
    joint = 1.0 - T.smoothstep(0.0006, 0.002, b["joint"])
    paint_col = T.gradient(T.normalize(0.6 * _sn(size, 2.4, seed + 102) + 0.4 * fib), paint)
    peel, ring = _peel(size, seed + 103, peel_cov, aniso=(1.0, 7.0), sharp=0.01, warp=4.0)
    wood = T.gradient(T.normalize(0.6 * late + 0.4 * fib), [(0.0, "#8a8579"), (0.5, "#76705f"), (1.0, "#5a5446")])
    col = T.mix(paint_col, wood, peel)
    col *= (1.0 - 0.2 * ring)[..., None]
    # vertical water streaks + grime under each lap
    streak = T.smoothstep(0.55, 0.9, _sn(size, 1.6, seed + 104, (12.0, 1.0)))
    col *= (1.0 - 0.12 * streak)[..., None]
    shadow = T.smoothstep(0.72, 1.0, v) * 0.0 + T.smoothstep(0.0, 0.08, v)
    col *= (0.72 + 0.28 * shadow)[..., None]          # dark under the overlap of the board above
    col *= (1.0 - 0.6 * joint)[..., None]
    col *= _grime(size, seed + 105, 0.1)[..., None]
    lap = 0.25 + 0.75 * v                              # board face thickens toward the butt
    lap = np.where(v > 0.985, lap * (1 - (v - 0.985) / 0.015), lap)
    height = np.clip(0.75 * lap + 0.06 * fib * peel + 0.03 * fib - 0.06 * peel + 0.04 * ring - 0.2 * joint, 0, 1)
    rough = np.clip(0.62 + 0.25 * peel + 0.06 * fib, 0, 1)
    return Finish(np.clip(col, 0, 1), height, rough, normal_strength=6.0, ao_strength=1.6)


def siding_white(size: int, seed: int) -> Finish:
    return _siding(size, seed, [(0.0, "#d4d1c7"), (0.6, "#e2dfd5"), (1.0, "#ebe8df")])


def siding_pale_blue(size: int, seed: int) -> Finish:
    return _siding(size, seed, [(0.0, "#8fa3b2"), (0.6, "#a3b6c4"), (1.0, "#b2c3cf")])


def siding_barn_red(size: int, seed: int) -> Finish:
    return _siding(size, seed, [(0.0, "#6b2a22"), (0.6, "#7f3a2e"), (1.0, "#93503f")], peel_cov=0.02)


def _brick_layout(size: int, tile: float, per_row: int, courses: int, mortar: float, seed: int, jitter: float = 0.003):
    x, y = _coords(size, tile)
    ch = tile / courses
    bl = tile / per_row
    row = np.floor(y / ch).astype(np.int32)
    off = (row % 2) * bl / 2
    xs = (x + off) % tile
    col_i = np.floor(xs / bl).astype(np.int32)
    gx = xs - col_i * bl
    gy = y - row * ch
    bid = (row % courses) * per_row + (col_i % per_row)
    # irregular brick edges
    ex = (_sn(size, 1.2, seed) - 0.5) * jitter
    ey = (_sn(size, 1.2, seed + 1) - 0.5) * jitter
    dx = np.minimum(gx, bl - gx) + ex
    dy = np.minimum(gy, ch - gy) + ey
    d = np.minimum(dx, dy)
    mortar_m = 1.0 - T.smoothstep(mortar * 0.5 - 0.001, mortar * 0.5 + 0.001, d)
    return bid, mortar_m.astype(np.float32), d


def brick_red(size: int, seed: int) -> Finish:
    bid, mort, d = _brick_layout(size, 1.0, 5, 16, 0.009, seed + 110)
    br = _hash_arr(bid, seed)
    br2 = _hash_arr(bid, seed + 3)
    br3 = _hash_arr(bid, seed + 4)
    tone = T.normalize(0.6 * br + 0.25 * _sn(size, 1.6, seed + 111) + 0.15 * _sn(size, 0.6, seed + 118))
    base = T.gradient(tone, [(0.0, "#5e2619"), (0.3, "#7d3424"), (0.6, "#934530"), (0.85, "#a8573b"), (1.0, "#b46a4c")])
    clinker = (br2 > 0.88).astype(np.float32)
    base = T.mix(base, _col("#3e1e16") * np.ones_like(base), clinker * 0.75)
    pale = (br3 > 0.92).astype(np.float32)
    base = T.mix(base, _col("#b98266") * np.ones_like(base), pale * 0.55)
    pits = T.smoothstep(0.7, 0.85, _sn(size, 0.4, seed + 112))
    base *= (1.0 - 0.3 * pits)[..., None]
    chip = T.smoothstep(0.62, 0.7, _sn(size, 0.9, seed + 119)) * (1.0 - T.smoothstep(0.004, 0.012, d))
    spall = T.smoothstep(0.6, 0.68, _sn(size, 1.8, seed + 113)) * (br2 < 0.12)
    base = T.mix(base, _col("#b8714f") * np.ones_like(base), np.clip(spall * 0.7 + chip * 0.5, 0, 1))
    mcol = T.gradient(_sn(size, 1.5, seed + 114), [(0.0, "#7d7466"), (0.6, "#9d9482"), (1.0, "#aea48f")])
    eroded = T.smoothstep(0.55, 0.75, _sn(size, 1.7, seed + 120))
    mcol = T.mix(mcol, _col("#4f483e") * np.ones_like(mcol), eroded * 0.5)
    col = T.mix(base, mcol, mort)
    eff = T.smoothstep(0.62, 0.85, _sn(size, 2.4, seed + 115)) * 0.35
    col = T.mix(col, _col("#d9d4c8") * np.ones_like(col), eff * (0.35 + 0.65 * mort))
    soot = T.smoothstep(0.55, 0.9, _sn(size, 1.6, seed + 121, (10.0, 1.0)))
    col *= (1.0 - 0.25 * soot)[..., None]
    col *= _grime(size, seed + 116, 0.15)[..., None]
    face = T.smoothstep(0.0, 0.004, d)
    height = np.clip(0.28 + 0.5 * face - 0.1 * pits - 0.15 * spall - 0.18 * chip - 0.08 * eroded * mort
                     + 0.05 * _sn(size, 0.8, seed + 117), 0, 1)
    rough = np.clip(0.82 + 0.1 * mort + 0.05 * pits, 0, 1)
    return Finish(np.clip(col, 0, 1), height, rough, normal_strength=6.0, ao_strength=1.5)


def concrete_block(size: int, seed: int) -> Finish:
    bid, mort, d = _brick_layout(size, 1.0, 2, 4, 0.01, seed + 120, jitter=0.002)
    br = _hash_arr(bid, seed)
    pores = T.smoothstep(0.72, 0.8, _sn(size, 0.35, seed + 121))
    agg = _sn(size, 0.6, seed + 122)
    paint = T.gradient(T.normalize(0.5 * _sn(size, 2.2, seed + 123) + 0.5 * agg), [(0.0, "#c9c4b6"), (1.0, "#dad5c8")])
    paint *= (0.97 + 0.04 * br)[..., None]
    worn, ring = _peel(size, seed + 124, 0.015, sharp=0.02)
    raw = T.gradient(agg, [(0.0, "#7c7a74"), (1.0, "#9a978f")])
    col = T.mix(paint, raw, worn)
    col *= (1.0 - 0.35 * pores)[..., None]
    mcol = _col("#b6b1a3") * np.ones_like(col)
    col = T.mix(col, mcol * 0.92, mort)
    cr = _cracks(size, seed + 125, 5, 1.6, 0.3) * T.smoothstep(0.5, 0.7, _sn(size, 2.0, seed + 126))
    col *= (1.0 - 0.4 * cr)[..., None]
    col *= _grime(size, seed + 127, 0.12)[..., None]
    face = T.smoothstep(0.0, 0.006, d)
    height = np.clip(0.35 + 0.45 * face - 0.12 * pores + 0.05 * agg - 0.2 * cr, 0, 1)
    rough = np.clip(0.75 + 0.1 * worn + 0.1 * pores, 0, 1)
    return Finish(np.clip(col, 0, 1), height, rough, normal_strength=5.0)


# =================================================================================================
# Floor finishes (2 m per tile)
# =================================================================================================

def _floorboards(size: int, seed: int, board_w: float, palette: list, *, min_len: float, max_len: float, knots: bool,
                 rings: float, gap: float, wear: float, figure: float = 0.4) -> Finish:
    tile = 2.0
    b = _boards(size, tile, board_w, seed + 200, min_len=min_len, max_len=max_len)
    pr = _piece_rand(b["piece"], seed)
    late, fib, pores = _grain(size, seed + 201, tile, rings_per_m=rings, figure=figure, v_off=pr * 0.37, u_off=pr * 1.7)
    tone = T.normalize(0.5 * late + 0.3 * fib + 0.2 * pr)
    col = T.gradient(tone, palette)
    col *= (0.88 + 0.22 * pr)[..., None]
    col *= (1.0 - 0.18 * pores)[..., None]
    if knots:
        f1, _, kid = T.worley(size, 18, seed + 202)
        ksel = (_hash_arr(kid, seed + 9) < 0.45).astype(np.float32)
        kn = (1.0 - T.smoothstep(0.0, 7.0, f1)) * ksel
        kring = (0.5 + 0.5 * np.cos(f1 * 1.3)) * (1.0 - T.smoothstep(4.0, 14.0, f1)) * ksel
        col = T.mix(col, _col("#4a2e17") * np.ones_like(col), np.clip(kn + 0.25 * kring, 0, 1))
    seam = (1.0 - T.smoothstep(gap * 0.5, gap * 0.5 + 0.0015, np.minimum(b["edge"], b["joint"]))).astype(np.float32)
    col = T.mix(col, _col("#1d140c") * np.ones_like(col), seam * 0.85)
    worn = T.smoothstep(0.45, 0.85, _sn(size, 2.3, seed + 203)) * wear
    col = T.mix(col, col * 0.85 + _col("#8d7a63") * 0.15, worn)
    scratch = T.smoothstep(0.86, 0.93, _sn(size, 0.7, seed + 204, (10.0, 1.0)))
    col *= (1.0 + 0.1 * scratch)[..., None]
    col *= _grime(size, seed + 205, 0.15)[..., None]
    height = np.clip(0.65 + 0.06 * fib - 0.04 * pores - 0.6 * seam - 0.03 * scratch, 0, 1)
    rough = np.clip(0.38 + 0.25 * worn + 0.1 * fib + 0.4 * seam + 0.1 * scratch, 0, 1)
    return Finish(np.clip(col, 0, 1), height, rough, normal_strength=4.0)


def wood_oak(size: int, seed: int) -> Finish:
    return _floorboards(size, seed, 2.0 / 26, [(0.0, "#7a5532"), (0.5, "#9b7044"), (1.0, "#b48a58")],
                        min_len=0.3, max_len=1.4, knots=False, rings=110, gap=0.0012, wear=0.6, figure=0.35)


def wood_pine(size: int, seed: int) -> Finish:
    f = _floorboards(size, seed, 2.0 / 13, [(0.0, "#8d5f2f"), (0.5, "#ad7d45"), (1.0, "#c79a5d")],
                     min_len=0.8, max_len=2.0, knots=True, rings=55, gap=0.002, wear=0.8, figure=0.5)
    x, y = _coords(size, 2.0)
    rows = 2.0 / 13
    vin = (y % rows) / rows
    nails = ((_wrapdist_x(x, np.arange(0.0, 2.0, 0.4, dtype=np.float32), 2.0) < 0.004) &
             ((np.abs(vin - 0.25) < 0.035) | (np.abs(vin - 0.75) < 0.035))).astype(np.float32)
    nails = ndimage.gaussian_filter(nails, 0.6, mode="wrap")
    f.albedo = T.mix(f.albedo, _col("#2a2420") * np.ones_like(f.albedo), np.clip(nails * 2, 0, 1))
    f.height = np.clip(f.height - 0.2 * nails, 0, 1)
    return f


def _carpet(size: int, seed: int, yarns: list[str], *, loop: bool, wear: float) -> Finish:
    """Heathered pile (per-tuft yarn colours), gentle pile-lay shading, matted traffic areas and a few
    soft stains."""
    tile = 2.0
    x, y = _coords(size, tile)
    h1 = _sn(size, 0.1, seed + 211)
    h2 = _sn(size, 0.1, seed + 212)
    base = _col(yarns[0]) * np.ones((size, size, 3), np.float32)
    base = T.mix(base, _col(yarns[1]) * np.ones_like(base), T.smoothstep(0.5, 0.6, h1))
    base = T.mix(base, _col(yarns[2]) * np.ones_like(base), T.smoothstep(0.72, 0.8, h2))
    tuft = _sn(size, 0.8, seed + 213)
    lay = _warp(_sn(size, 2.0, seed + 214, (1.0, 2.0)), seed + 215, 20.0)
    col = base * (0.93 + 0.1 * lay + 0.06 * tuft)[..., None]
    traffic = T.smoothstep(0.55, 0.85, _sn(size, 2.6, seed + 216)) * wear
    col = T.mix(col, col * 0.85 + _col("#8a857a") * 0.15, traffic * 0.8)
    st = T.smoothstep(0.86, 0.9, _warp(_sn(size, 1.9, seed + 217), seed + 218, 30.0))
    ring = T.smoothstep(0.85, 0.87, _warp(_sn(size, 1.9, seed + 217), seed + 218, 30.0)) * (1 - st)
    col = T.mix(col, col * 0.7 + _col("#4a3520") * 0.1, st * 0.35)
    col *= (1.0 - 0.15 * ring)[..., None]
    col *= _grime(size, seed + 219, 0.12)[..., None]
    rows = (0.5 + 0.5 * np.cos(y * 2 * np.pi * 125)).astype(np.float32) if loop else 0.0
    height = np.clip(0.45 + 0.25 * tuft + 0.15 * h1 + 0.04 * rows - 0.2 * traffic, 0, 1)
    rough = np.clip(0.94 + 0.04 * h1, 0, 1)
    return Finish(np.clip(col, 0, 1), height.astype(np.float32), rough, normal_strength=1.5, ao_strength=1.6)


def carpet_brown(size: int, seed: int) -> Finish:
    return _carpet(size, seed, ["#4b3826", "#5f4831", "#7a6045"], loop=False, wear=0.6)


def carpet_blue_worn(size: int, seed: int) -> Finish:
    return _carpet(size, seed, ["#33425a", "#405172", "#5a6880"], loop=True, wear=1.0)


def linoleum_check(size: int, seed: int) -> Finish:
    tile = 2.0
    x, y = _coords(size, tile)
    n = 6
    p = tile / n
    ix, iy = np.floor(x / p).astype(np.int32), np.floor(y / p).astype(np.int32)
    which = ((ix + iy) % 2).astype(np.float32)
    tid = (iy % n) * n + (ix % n)
    gx, gy = (x % p) / p, (y % p) / p
    dist = np.minimum(np.minimum(gx, 1 - gx), np.minimum(gy, 1 - gy)) * p
    seam = 1.0 - T.smoothstep(0.0006, 0.002, dist)
    marble = _warp(_sn(size, 1.3, seed + 220, (1.0, 3.0)), seed + 221, 30.0)
    white = T.gradient(marble, [(0.0, "#cfc8b4"), (1.0, "#e2dccb")])
    black = T.gradient(marble, [(0.0, "#141414"), (1.0, "#2b2a28")])
    col = T.mix(white, black, which)
    tr = _hash_arr(tid, seed)
    col *= (0.95 + 0.08 * tr)[..., None]
    # broken / lifted tiles show black adhesive and the subfloor
    broken = (_hash_arr(tid, seed + 2) < 0.03).astype(np.float32)
    chip = T.smoothstep(0.55, 0.6, _warp(_sn(size, 1.5, seed + 222), seed + 223, 20.0)) * broken
    col = T.mix(col, _col("#2a2118") * np.ones_like(col), chip)
    scuff = T.smoothstep(0.8, 0.9, _sn(size, 0.8, seed + 224, (5.0, 1.0)))
    col = T.mix(col, _col("#3a3530") * np.ones_like(col), scuff * 0.25 * (1 - which))
    wax = T.smoothstep(0.4, 0.9, _sn(size, 2.4, seed + 225))
    col *= (1.0 - 0.12 * wax)[..., None]
    col *= (1.0 - 0.6 * seam)[..., None]
    col *= _grime(size, seed + 226, 0.15)[..., None]
    height = np.clip(0.6 - 0.3 * seam - 0.25 * chip + 0.02 * marble, 0, 1)
    rough = np.clip(0.35 + 0.2 * scuff + 0.2 * wax + 0.4 * chip, 0, 1)
    return Finish(np.clip(col, 0, 1), height, rough, normal_strength=3.0)


def linoleum_beige(size: int, seed: int) -> Finish:
    tile = 2.0
    x, y = _coords(size, tile)
    speck = _sn(size, 0.2, seed + 230)
    chips = (speck > 0.75).astype(np.float32) * 0.6 + (speck < 0.2).astype(np.float32) * -0.4
    base = T.gradient(_sn(size, 2.0, seed + 231), [(0.0, "#c8b796"), (1.0, "#d8c8a8")])
    base *= (1.0 + 0.08 * chips)[..., None]
    p = tile / 8
    gx, gy = (x % p) / p, (y % p) / p
    dist = np.minimum(np.minimum(gx, 1 - gx), np.minimum(gy, 1 - gy)) * p
    faux = 1.0 - T.smoothstep(0.002, 0.004, dist)          # embossed faux grout
    col = T.mix(base, _col("#a99878") * np.ones_like(base), faux * 0.7)
    seam_y = np.abs(((y - 0.7) % tile)) < 0.0015
    col *= (1.0 - 0.4 * seam_y.astype(np.float32))[..., None]
    yellow = T.smoothstep(0.4, 0.9, _sn(size, 2.5, seed + 232))
    col = T.mix(col, col * 0.8 + _col("#b39a5a") * 0.2, yellow)
    scuff = T.smoothstep(0.84, 0.92, _sn(size, 0.8, seed + 233, (6.0, 1.0)))
    col = T.mix(col, _col("#57504a") * np.ones_like(col), scuff * 0.3)
    tear, ring = _peel(size, seed + 234, 0.004, sharp=0.01)
    col = T.mix(col, _col("#3a2c1e") * np.ones_like(col), tear)
    col *= _grime(size, seed + 235, 0.15)[..., None]
    height = np.clip(0.6 - 0.15 * faux - 0.3 * tear + 0.08 * ring + 0.02 * speck, 0, 1)
    rough = np.clip(0.45 + 0.15 * scuff + 0.1 * yellow + 0.4 * tear, 0, 1)
    return Finish(np.clip(col, 0, 1), height, rough, normal_strength=3.0)


def tile_white_small(size: int, seed: int) -> Finish:
    """1-inch hex mosaic (2 m tile: 80 x 96 cells, lattice squashed 3.8 % to tile) with black rosettes."""
    tile = 2.0
    x, y = _coords(size, tile)
    cols_n, rows_n = 80, 96
    w = tile / cols_n
    h = tile / rows_n
    best = np.full((size, size), 9.0, np.float32)
    second = np.full((size, size), 9.0, np.float32)
    rid = np.zeros((size, size), np.int32)
    cidx = np.zeros((size, size), np.int32)
    r0 = np.floor(y / h).astype(np.int32)
    k = w / (h * 2 / math.sqrt(3))
    for dr in (-1, 0, 1):
        r = r0 + dr
        off = (r % 2) * w / 2
        c0 = np.floor((x - off) / w).astype(np.int32)
        for dc in (-1, 0, 1):
            c = c0 + dc
            cx = (c + 0.5) * w + off
            cy = (r + 0.5) * h
            dx = np.abs(x - cx)
            dy = np.abs(y - cy) * k
            dd = np.maximum(dx, dx * 0.5 + dy * math.sqrt(3) / 2)
            closer = dd < best
            second = np.where(closer, best, np.minimum(second, dd))
            rid = np.where(closer, r % rows_n, rid)
            cidx = np.where(closer, c % cols_n, cidx)
            best = np.where(closer, dd, best)
    edge = second - best
    grout = 1.0 - T.smoothstep(0.0012, 0.0024, edge)
    cid = rid * cols_n + cidx
    tr = _hash_arr(cid, seed)
    rm, cm = rid % 16, cidx % 16
    petal = (((rm == 0) & ((cm == 1) | (cm == 15))) | (((rm == 1) | (rm == 15)) & ((cm == 15) | (cm == 0))) |
             ((rm == 8) & ((cm == 7) | (cm == 9))) | (((rm == 7) | (rm == 9)) & ((cm == 7) | (cm == 8))))
    accent = petal.astype(np.float32)
    base = T.mix(_col("#e6e3dc") * np.ones((size, size, 3), np.float32), _col("#232426") * np.ones((size, size, 3), np.float32), accent)
    base *= (0.95 + 0.07 * tr)[..., None]
    dirt = T.smoothstep(0.35, 0.9, _sn(size, 2.0, seed + 240))
    gcol = T.mix(_col("#9a968b") * np.ones_like(base), _col("#4b473f") * np.ones_like(base), dirt)
    col = T.mix(base, gcol, grout)
    stain = T.smoothstep(0.78, 0.86, _warp(_sn(size, 1.8, seed + 241), seed + 242, 20.0))
    col = T.mix(col, col * 0.75 + _col("#7a6440") * 0.25, stain * 0.25)
    missing = (_hash_arr(cid, seed + 11) < 0.006).astype(np.float32) * (1 - grout)
    col = T.mix(col, _col("#3b362d") * np.ones_like(col), missing)
    col *= _grime(size, seed + 243, 0.12)[..., None]
    height = np.clip(0.4 + 0.45 * T.smoothstep(0.0012, 0.004, edge) - 0.1 * grout - 0.4 * missing, 0, 1)
    rough = np.clip(0.15 + 0.7 * grout + 0.15 * stain + 0.7 * missing, 0, 1)
    return Finish(np.clip(col, 0, 1), height, rough, normal_strength=4.0)


def concrete(size: int, seed: int, tile: float = 2.0) -> Finish:
    trowel = _warp(_sn(size, 2.6, seed + 250), seed + 251, 30.0)
    burn = _sn(size, 1.8, seed + 259, (3.0, 1.0))            # power-trowel burnish swirls
    agg = _sn(size, 0.5, seed + 252)
    pits = T.smoothstep(0.8, 0.86, _sn(size, 0.3, seed + 253))
    tone = T.normalize(0.45 * trowel + 0.25 * agg + 0.15 * burn + 0.15 * _sn(size, 1.6, seed + 254))
    col = T.gradient(tone, [(0.0, "#716e68"), (0.5, "#86837c"), (1.0, "#99968e")])
    stains = _warp(_sn(size, 1.6, seed + 255), seed + 256, 25.0)
    oil = T.smoothstep(0.88, 0.92, stains)
    col = T.mix(col, _col("#3e3a34") * np.ones_like(col), oil * 0.35)
    damp = T.smoothstep(0.75, 0.88, _sn(size, 2.0, seed + 260))
    col *= (1.0 - 0.12 * damp)[..., None]
    cr = _cracks(size, seed + 257, 5, 1.2, 0.2)
    col *= (1.0 - 0.45 * cr)[..., None]
    col *= (1.0 - 0.25 * pits)[..., None]
    col *= _grime(size, seed + 258, 0.12)[..., None]
    height = np.clip(0.55 + 0.12 * trowel + 0.08 * agg - 0.25 * pits - 0.3 * cr, 0, 1)
    rough = np.clip(0.7 + 0.12 * agg - 0.15 * burn - 0.2 * oil + 0.1 * pits, 0, 1)
    return Finish(np.clip(col, 0, 1), height, rough, normal_strength=3.0)


FINISH_FNS = {f.__name__: f for f in (
    plaster_white, plaster_grey, paint_mustard, paint_sage, paint_slate_blue, wallpaper_floral_rose,
    wallpaper_stripe_green, wallpaper_damask_brown, wood_paneling_dark, tile_bathroom_white, tile_kitchen_check,
    siding_white, siding_pale_blue, siding_barn_red, brick_red, concrete_block, wood_oak, wood_pine, carpet_brown,
    carpet_blue_worn, linoleum_check, linoleum_beige, tile_white_small, concrete)}


def _finish(name: str, size: int, seed: int) -> Finish:
    if name in ROCK_FINISH_FNS:
        return rock_finish(name, size, seed)
    if name in LOG_FINISH_FNS:
        return log_finish(name, size, seed)
    return FINISH_FNS[name](size, seed + 1009 * (sorted(FINISH_FNS).index(name) + 1))


def _write_array(out, size: int, seed: int, names: list[str], channel: str, slices: int) -> None:
    assert slices == len(names)
    tiles = []
    for n in names:
        f = _finish(n, size, seed)
        if channel == "albedo":
            tiles.append(np.clip(f.albedo, 0, 1))
        elif channel == "normal":
            tiles.append(T.height_to_normal(f.height, f.normal_strength))
        else:
            metal = f.metal if isinstance(f.metal, np.ndarray) else np.full_like(f.height, float(f.metal))
            tiles.append(np.stack([T.cavity_ao(f.height, strength=f.ao_strength), np.clip(f.rough, 0, 1), metal], -1))
    # Large strip (1024 x 16384): fast zlib level, still lossless and deterministic.
    from PIL import Image
    strip = (np.clip(np.concatenate(tiles, 0), 0, 1) * 255.0 + 0.5).astype(np.uint8)
    Image.fromarray(strip, "RGB").save(str(out) + ".png", optimize=False, compress_level=1)


@texture("kit_wall_finishes_albedo", size=1024, seed=7100, kind="array", import_kind="albedo", slices=len(WALL_FINISHES), sources=_WALL_SOURCES)
def kit_wall_finishes_albedo(size: int, seed: int, out, slices: int) -> None:
    _write_array(out, size, seed, WALL_FINISHES, "albedo", slices)


@texture("kit_wall_finishes_normal", size=1024, seed=7100, kind="array", import_kind="normal", slices=len(WALL_FINISHES), sources=_WALL_SOURCES)
def kit_wall_finishes_normal(size: int, seed: int, out, slices: int) -> None:
    _write_array(out, size, seed, WALL_FINISHES, "normal", slices)


@texture("kit_wall_finishes_orm", size=1024, seed=7100, kind="array", import_kind="data", slices=len(WALL_FINISHES), sources=_WALL_SOURCES)
def kit_wall_finishes_orm(size: int, seed: int, out, slices: int) -> None:
    _write_array(out, size, seed, WALL_FINISHES, "orm", slices)


@texture("kit_floor_finishes_albedo", size=1024, seed=7200, kind="array", import_kind="albedo", slices=len(FLOOR_FINISHES), sources=_ROCK_SOURCES)
def kit_floor_finishes_albedo(size: int, seed: int, out, slices: int) -> None:
    _write_array(out, size, seed, FLOOR_FINISHES, "albedo", slices)


@texture("kit_floor_finishes_normal", size=1024, seed=7200, kind="array", import_kind="normal", slices=len(FLOOR_FINISHES), sources=_ROCK_SOURCES)
def kit_floor_finishes_normal(size: int, seed: int, out, slices: int) -> None:
    _write_array(out, size, seed, FLOOR_FINISHES, "normal", slices)


@texture("kit_floor_finishes_orm", size=1024, seed=7200, kind="array", import_kind="data", slices=len(FLOOR_FINISHES), sources=_ROCK_SOURCES)
def kit_floor_finishes_orm(size: int, seed: int, out, slices: int) -> None:
    _write_array(out, size, seed, FLOOR_FINISHES, "orm", slices)


# =================================================================================================
# Decay masks (kit_wall.gdshader composes stains, grime, mould and peeling paint from these)
# =================================================================================================

DECAY_TILE_M = 2.5


def _equalize(f: np.ndarray) -> np.ndarray:
    """Rank transform to a uniform [0,1] distribution: a shader threshold t then reveals exactly 1 - t of
    the area, so decay -> coverage stays predictable whatever the noise statistics."""
    flat = f.ravel()
    ranks = np.empty(flat.size, np.int64)
    ranks[np.argsort(flat, kind="stable")] = np.arange(flat.size)
    return (ranks.astype(np.float32) / (flat.size - 1)).reshape(f.shape)


def _run_down(src: np.ndarray, fall: float) -> np.ndarray:
    """Propagates values down the image (+rows = down a wall), losing `fall` per pixel: a stain at value
    v leaves a tail that stays above a threshold t for (v - t) / fall pixels. Periodic in rows."""
    n = src.shape[0]
    out = src.copy()
    cur = src[-1].copy()
    for _ in range(2):  # second lap carries tails across the wrap
        for r in range(n):
            cur = np.maximum(src[r], cur - fall)
            out[r] = np.maximum(out[r], cur)
    return out


def _decay_masks(size: int, seed: int) -> np.ndarray:
    """RGBA coverage priorities, each uniform in [0,1] (2.5 m per tile, +rows = down):
    R grime (broad soft dirt), G water stains (vertically elongated blots with drip trails running down
    from them), B mould (speckled colonies), A peeling (clustered flakes)."""
    n = size
    grime = 0.55 * _sn(n, 2.4, seed + 1) + 0.3 * _warp(_sn(n, 1.6, seed + 2), seed + 3, 20.0) + 0.15 * _sn(n, 0.9, seed + 4)
    # Several blots of 0.3-1 m per tile (fmin drops the tile-sized swell), taller than wide.
    blots = 0.8 * _sn(n, 2.0, seed + 5, (1.0, 0.6), fmin=3.0) + 0.2 * _sn(n, 1.6, seed + 15, fmin=6.0)
    blots = _warp(blots, seed + 6, 30.0, beta=1.7)
    blots = _equalize(_warp(blots, seed + 7, 8.0, beta=1.2))
    # Drips: thin vertical runs that start inside the stronger stains and run down, each tail a little
    # weaker than its source so longer drips appear as decay grows.
    lines = T.smoothstep(0.68, 0.8, _sn(n, 1.5, seed + 8, (14.0, 1.0)))
    tails = _run_down(np.where(blots > 0.55, blots, 0.0).astype(np.float32), 0.0007)
    stains = np.maximum(blots, tails * lines * 0.995)
    clusters = _warp(_sn(n, 1.9, seed + 9), seed + 10, 25.0)
    mould = 0.62 * clusters + 0.38 * _sn(n, 0.3, seed + 11)
    cl = _sn(n, 2.2, seed + 12)
    fine = _warp(_sn(n, 1.25, seed + 13), seed + 14, 4.0, beta=1.5)
    peel = fine + 0.9 * (cl - 0.5)
    return np.stack([_equalize(grime), stains, _equalize(mould), _equalize(peel)], -1).astype(np.float32)


def _decay_detail(size: int, seed: int) -> np.ndarray:
    """RGB: R macro tone (sampled at ~1/12 scale to break the 1-2 m finish tiling), G fine substrate
    grain + hairline cracks (exposed plaster, flake edges), B scuff strokes (floors, baseboards)."""
    n = size
    macro = T.normalize(0.7 * _sn(n, 2.0, seed + 21) + 0.3 * _sn(n, 1.4, seed + 22))
    grain = T.normalize(0.6 * _sn(n, 0.45, seed + 23) + 0.4 * _sn(n, 1.1, seed + 24))
    grain = np.clip(grain - 0.5 * _cracks(n, seed + 25, 12, 1.2, 0.35), 0, 1)
    scuffs = np.maximum(T.smoothstep(0.8, 0.92, _sn(n, 0.9, seed + 26, (1.0, 9.0))),
                        T.smoothstep(0.82, 0.93, _sn(n, 0.9, seed + 27, (9.0, 1.0))))
    scuffs *= T.smoothstep(0.35, 0.7, _sn(n, 2.0, seed + 28))
    return np.stack([macro, grain, scuffs], -1).astype(np.float32)


# Masks: linear, BC7 ("mask" import) so four unrelated channels survive compression.
@texture("kit_decay_albedo", size=1024, seed=7300, kind="single", import_kind="mask")
def kit_decay_albedo(size: int, seed: int, out) -> None:  # -> textures/kit_decay_albedo.png (masks, not colour)
    T.save_rgba(str(out) + ".png", _decay_masks(size, seed))


@texture("kit_decay_orm", size=1024, seed=7310, kind="single", import_kind="mask")
def kit_decay_orm(size: int, seed: int, out) -> None:  # -> textures/kit_decay_orm.png (detail, not ORM)
    T.save_rgb(str(out) + ".png", _decay_detail(size, seed))


# =================================================================================================
# Standard PBR sets
# =================================================================================================

def _save(out, f: Finish, alpha=None) -> None:
    T.save_pbr_set(out, np.clip(f.albedo, 0, 1), f.height, np.clip(f.rough, 0, 1), metal=f.metal,
                   normal_strength=f.normal_strength, ao_strength=f.ao_strength, alpha=alpha)


@texture("kit_plaster", size=1024, seed=7400)
def kit_plaster(size: int, seed: int, out) -> None:
    _save(out, plaster_white(size, seed))


def _wood_base(size: int, seed: int, palette: list, rings: float, figure: float) -> tuple:
    late, fib, pores = _grain(size, seed, 1.0, rings_per_m=rings, figure=figure)
    tone = T.normalize(0.3 * late + 0.45 * fib + 0.25 * _sn(size, 2.0, seed + 5, (1.0, 4.0)))
    return T.gradient(tone, palette), late, fib, pores


@texture("kit_trim", size=1024, seed=7410)
def kit_trim(size: int, seed: int, out) -> None:
    wood, late, fib, pores = _wood_base(size, seed, [(0.0, "#6e6457"), (1.0, "#958a78")], 110, 0.2)
    brush = _sn(size, 0.7, seed + 1, (1.0, 18.0))
    paint = T.gradient(T.normalize(0.5 * _sn(size, 2.4, seed + 2) + 0.5 * brush), [(0.0, "#d6d1c3"), (1.0, "#e7e3d8")])
    f, t = _flakes(size, seed + 3, 0.05, aniso=(1.0, 4.0), cluster=1.1)
    chips = T.smoothstep(t - 0.006, t + 0.006, f)
    ring = T.smoothstep(t - 0.03, t - 0.006, f) * (1 - chips)
    col = T.mix(paint, wood, chips)
    col *= (1.0 - 0.2 * ring)[..., None]
    grain_dirt = 1.0 - 0.12 * late * (1 - chips)          # paint settles into the grain
    col *= grain_dirt[..., None]
    alligator = _cracks(size, seed + 5, 40, 1.0, 0.12) * (1 - chips)
    col *= (1.0 - 0.25 * alligator)[..., None]
    col *= _grime(size, seed + 4, 0.1)[..., None]
    h = np.clip(0.6 + 0.05 * brush + 0.04 * fib - 0.12 * chips + 0.06 * ring + 0.03 * late - 0.1 * alligator, 0, 1)
    rough = np.clip(0.42 + 0.06 * brush + 0.35 * chips + 0.1 * alligator, 0, 1)
    _save(out, Finish(col, h, rough, normal_strength=3.0))


@texture("door_wood", size=1024, seed=7420)
def door_wood(size: int, seed: int, out) -> None:
    col, late, fib, pores = _wood_base(size, seed, [(0.0, "#3d2414"), (0.45, "#5c3820"), (1.0, "#7a5030")], 95, 0.2)
    col *= (1.0 - 0.22 * pores)[..., None]
    worn = T.smoothstep(0.55, 0.9, _sn(size, 2.2, seed + 1)) * 0.5
    col = T.mix(col, col * 0.8 + _col("#8a7458") * 0.2, worn)
    scratch = T.smoothstep(0.88, 0.94, _sn(size, 0.6, seed + 2, (8.0, 1.0)))
    col *= (1.0 + 0.2 * scratch)[..., None]
    col *= _grime(size, seed + 3, 0.15)[..., None]
    h = np.clip(0.6 + 0.05 * fib - 0.05 * pores + 0.04 * late - 0.04 * scratch, 0, 1)
    rough = np.clip(0.35 + 0.3 * worn + 0.08 * fib + 0.15 * scratch, 0, 1)
    _save(out, Finish(col, h, rough, normal_strength=3.0))


@texture("kit_stairs", size=1024, seed=7430)
def kit_stairs(size: int, seed: int, out) -> None:
    col, late, fib, pores = _wood_base(size, seed, [(0.0, "#4a2c17"), (0.5, "#6b4425"), (1.0, "#8a5d35")], 110, 0.18)
    col *= (1.0 - 0.28 * pores)[..., None]
    worn = T.smoothstep(0.4, 0.85, _sn(size, 2.0, seed + 1, (2.0, 1.0))) * 0.7
    col = T.mix(col, col * 0.75 + _col("#9c8566") * 0.25, worn)
    scuff = T.smoothstep(0.85, 0.93, _sn(size, 0.7, seed + 2, (6.0, 1.0)))
    col = T.mix(col, _col("#2a1d14") * np.ones_like(col), scuff * 0.3)
    col *= _grime(size, seed + 3, 0.2)[..., None]
    h = np.clip(0.6 + 0.05 * fib - 0.05 * pores + 0.03 * late, 0, 1)
    rough = np.clip(0.4 + 0.35 * worn + 0.08 * fib, 0, 1)
    _save(out, Finish(col, h, rough, normal_strength=3.0))


@texture("wood_raw", size=1024, seed=7440)
def wood_raw(size: int, seed: int, out) -> None:
    """Weathered softwood lumber: silver-grey surface with brown undertones, raised (eroded) grain,
    drying checks along the grain, knots and rusty nail-hole stains."""
    col, late, fib, pores = _wood_base(size, seed, [(0.0, "#5f574c"), (0.4, "#7f7568"), (1.0, "#a09685")], 70, 0.2)
    brown = T.smoothstep(0.4, 0.8, _sn(size, 2.3, seed + 1, (1.0, 3.0)))
    col = T.mix(col, col * 0.7 + _col("#8a6a48") * 0.3, brown * 0.55)
    checks = T.smoothstep(0.9, 0.95, _sn(size, 0.5, seed + 2, (1.0, 30.0))) * T.smoothstep(0.4, 0.6, _sn(size, 2.0, seed + 3))
    col *= (1.0 - 0.55 * checks)[..., None]
    f1, _, kid = T.worley(size, 10, seed + 4)
    ksel = (_hash_arr(kid, seed) < 0.4).astype(np.float32)
    knot = (1.0 - T.smoothstep(0.0, 9.0, f1)) * ksel
    kring = (0.5 + 0.5 * np.cos(f1 * 1.1)) * (1.0 - T.smoothstep(6.0, 22.0, f1)) * ksel
    col = T.mix(col, _col("#3a3128") * np.ones_like(col), np.clip(knot * 0.85 + kring * 0.2, 0, 1))
    rust = (1.0 - T.smoothstep(2.0, 12.0, f1)) * (1 - ksel) * T.smoothstep(0.6, 0.8, _sn(size, 1.0, seed + 5))
    col = T.mix(col, _col("#6b3f20") * np.ones_like(col), rust * 0.55)
    col *= _grime(size, seed + 6, 0.15)[..., None]
    h = np.clip(0.55 + 0.15 * fib + 0.12 * (1 - late) - 0.4 * checks + 0.05 * knot, 0, 1)
    rough = np.clip(0.82 + 0.1 * fib, 0, 1)
    _save(out, Finish(col, h, rough, normal_strength=4.5))


@texture("glass", size=512, seed=7450, kind="pbr_alpha")
def glass(size: int, seed: int, out) -> None:
    x, y = _coords(size, 1.0)
    edge = np.minimum(np.minimum(x, 1 - x), np.minimum(y, 1 - y))
    edge_dirt = 1.0 - T.smoothstep(0.0, 0.18, edge + 0.05 * _sn(size, 1.5, seed))
    smudge = T.smoothstep(0.55, 0.85, _warp(_sn(size, 1.7, seed + 1), seed + 2, 12.0))
    streak = T.smoothstep(0.55, 0.85, _sn(size, 1.2, seed + 3, (10.0, 1.0))) * T.smoothstep(0.3, 1.0, y)
    spots = T.smoothstep(0.82, 0.9, _sn(size, 0.5, seed + 4))
    dirt = np.clip(0.75 * edge_dirt + 0.35 * smudge + 0.3 * streak + 0.4 * spots, 0, 1)
    tint = _col("#9fb3ad") * np.ones((size, size, 3), np.float32)
    grime = _col("#6d6658") * np.ones_like(tint)
    col = T.mix(tint, grime, dirt)
    alpha = np.clip(0.2 + 0.7 * dirt, 0, 1)
    h = 0.5 + 0.02 * _sn(size, 2.8, seed + 5) + 0.03 * dirt
    rough = np.clip(0.04 + 0.7 * dirt, 0, 1)
    _save(out, Finish(col, h.astype(np.float32), rough, normal_strength=1.5), alpha=alpha)


@texture("concrete", size=1024, seed=7460)
def concrete_set(size: int, seed: int, out) -> None:
    f = concrete(size, seed, 1.0)
    x, y = _coords(size, 1.0)
    # form-board lines and tie holes (50 cm grid) of an old poured foundation
    board = 1.0 - T.smoothstep(0.0008, 0.002, _wrapdist_x(y, np.arange(0.0, 1.0, 0.2, dtype=np.float32), 1.0))
    tie = 1.0 - T.smoothstep(0.004, 0.006, np.sqrt(_wrapdist_x(x, np.array([0.25, 0.75], np.float32), 1.0) ** 2 +
                                                 _wrapdist_x(y, np.array([0.3, 0.8], np.float32), 1.0) ** 2))
    eff = T.smoothstep(0.6, 0.85, _sn(size, 2.2, seed + 9)) * 0.4
    f.albedo = T.mix(f.albedo, _col("#d2cfc6") * np.ones_like(f.albedo), eff)
    f.albedo *= (1.0 - 0.25 * board - 0.6 * tie)[..., None]
    f.height = np.clip(f.height - 0.15 * board - 0.4 * tie, 0, 1)
    _save(out, f)


@texture("brick", size=1024, seed=7470)
def brick(size: int, seed: int, out) -> None:
    _save(out, brick_red(size, seed))


@texture("metal_painted", size=1024, seed=7480)
def metal_painted(size: int, seed: int, out) -> None:
    """Painted steel (institutional green-grey), chipped to primer / bare steel / rust, run-off rust
    streaks, scratches and shallow dents."""
    paint = T.gradient(T.normalize(0.6 * _sn(size, 2.3, seed) + 0.4 * _sn(size, 0.8, seed + 1)),
                       [(0.0, "#3b4b40"), (0.5, "#47584b"), (1.0, "#536558")])
    f, t = _flakes(size, seed + 2, 0.06, cluster=1.3)
    t2 = float(np.quantile(f, 1.0 - 0.03))
    chips = T.smoothstep(t - 0.006, t + 0.006, f)
    deep = T.smoothstep(t2 - 0.006, t2 + 0.006, f)
    ring = T.smoothstep(t - 0.03, t - 0.006, f) * (1 - chips)
    primer = _col("#8a7b62") * np.ones_like(paint)
    rust = T.gradient(_sn(size, 0.9, seed + 3), [(0.0, "#4a2614"), (0.5, "#6e3a1c"), (1.0, "#8c5228")])
    bare = T.smoothstep(0.55, 0.8, _sn(size, 1.0, seed + 4))
    steel = T.mix(rust, _col("#6f6e6a") * np.ones_like(rust), bare * 0.6)
    col = T.mix(paint, primer, chips)
    col = T.mix(col, steel, deep)
    col *= (1.0 - 0.25 * ring)[..., None]
    streak = T.smoothstep(0.62, 0.9, _sn(size, 1.4, seed + 5, (12.0, 1.0)))
    col = T.mix(col, _col("#6a3c1e") * np.ones_like(col), streak * 0.22)
    scratch = T.smoothstep(0.9, 0.95, _sn(size, 0.5, seed + 6, (1.0, 9.0)))
    col = T.mix(col, _col("#8a8a86") * np.ones_like(col), scratch * 0.45)
    dent = _sn(size, 2.8, seed + 7)
    col *= _grime(size, seed + 8, 0.12)[..., None]
    h = np.clip(0.55 + 0.1 * dent - 0.08 * chips - 0.06 * deep + 0.06 * ring - 0.04 * scratch, 0, 1)
    rough = np.clip(0.5 + 0.2 * chips + 0.2 * deep * (1 - bare * 0.4) + 0.05 * _sn(size, 0.6, seed + 9), 0, 1)
    metal = np.clip(deep * bare * 0.9 + scratch * 0.6, 0, 1).astype(np.float32)
    _save(out, Finish(col, h, rough, metal=metal, normal_strength=2.5))


@texture("kit_wall_inner", size=1024, seed=7490)
def kit_wall_inner(size: int, seed: int, out) -> None:
    """Broken wall section: crumbling gypsum plaster with sand and voids, splintered lath scraps (horizontal
    streaks), fluffy fibreglass insulation tufts, dust. Used on hole rims, cavities and fracture insides."""
    crumble = T.normalize(0.5 * _sn(size, 0.45, seed + 1) + 0.5 * _sn(size, 1.3, seed + 2))
    voids = T.smoothstep(0.74, 0.8, _warp(_sn(size, 0.9, seed + 3), seed + 4, 6.0))
    plaster = T.gradient(T.normalize(crumble + 0.5 * _sn(size, 2.0, seed + 5)),
                         [(0.0, "#968e7f"), (0.45, "#bdb6a7"), (1.0, "#d8d2c5")])
    late, fib, _ = _grain(size, seed + 6, 1.0, rings_per_m=90, figure=0.3)
    wood = T.gradient(T.normalize(0.5 * late + 0.5 * fib), [(0.0, "#5e4630"), (1.0, "#93744f")])
    lath = T.smoothstep(0.66, 0.7, _warp(_sn(size, 1.6, seed + 7, (1.0, 7.0)), seed + 8, 8.0))
    fluff = _warp(_sn(size, 0.6, seed + 9), seed + 10, 6.0)
    insul_m = T.smoothstep(0.8, 0.85, _warp(_sn(size, 2.0, seed + 11), seed + 12, 20.0)) * T.smoothstep(0.3, 0.55, fluff)
    insul = T.gradient(fluff, [(0.0, "#b57d70"), (0.6, "#dba796"), (1.0, "#efc9b9")])
    col = T.mix(plaster, wood, lath)
    col = T.mix(col, insul, insul_m)
    col *= (1.0 - 0.45 * voids * (1 - insul_m))[..., None]
    dust = T.smoothstep(0.4, 0.9, _sn(size, 2.2, seed + 13))
    col = T.mix(col, _col("#8f877a") * np.ones_like(col), dust * 0.2)
    h = np.clip(0.5 + 0.3 * crumble * (1 - insul_m) - 0.35 * voids + 0.1 * lath + 0.2 * fluff * insul_m, 0, 1)
    rough = np.clip(0.9 + 0.05 * fluff, 0, 1)
    _save(out, Finish(col, h, rough, normal_strength=4.0, ao_strength=1.5))

