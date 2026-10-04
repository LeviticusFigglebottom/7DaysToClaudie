"""Procedural texture toolkit (numpy). Everything here is tileable and deterministic.

Conventions:
  * Square power-of-two sizes (512/1024/2048). All generators take `size` and a `seed`.
  * Albedo saved as sRGB PNG; normal maps are tangent space, OpenGL convention (+Y up = green
    up), which is what Godot expects; ORM = R ambient occlusion, G roughness, B metallic (linear).
  * Height fields are float32 in [0, 1].
"""
from __future__ import annotations

import pathlib

import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.spatial import cKDTree


def rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed & 0xFFFFFFFF)


# --------------------------------------------------------------------------------------------
# Noise (all periodic)
# --------------------------------------------------------------------------------------------

def spectral(size: int, beta: float, seed: int, *, anisotropy: tuple[float, float] = (1.0, 1.0),
             fmin: float = 1.0, fmax: float | None = None) -> np.ndarray:
    """Tileable 1/f^beta noise via FFT. beta ~1 = rough, ~2 = smooth clouds, ~3 = very smooth.
    anisotropy stretches frequencies (e.g. (1, 6) gives grain along x). Output normalized [0,1]."""
    r = rng(seed)
    fx = np.fft.fftfreq(size)[None, :] * size / anisotropy[0]
    fy = np.fft.fftfreq(size)[:, None] * size / anisotropy[1]
    f = np.sqrt(fx * fx + fy * fy)
    f[0, 0] = 1.0
    amp = 1.0 / np.power(f, beta / 1.0)
    amp[f < fmin] = 0.0
    if fmax is not None:
        amp[f > fmax] = 0.0
    amp[0, 0] = 0.0
    phase = r.uniform(0, 2 * np.pi, (size, size))
    spec = amp * np.exp(1j * phase)
    out = np.real(np.fft.ifft2(spec))
    return normalize(out)


def fbm(size: int, seed: int, octaves: int = 6, base_freq: int = 4, persistence: float = 0.5,
        lacunarity: int = 2) -> np.ndarray:
    """Tileable fractal value-noise sum (integer frequencies keep it periodic)."""
    out = np.zeros((size, size), np.float32)
    amp, total = 1.0, 0.0
    freq = base_freq
    for o in range(octaves):
        out += amp * value_noise(size, freq, seed + o * 101)
        total += amp
        amp *= persistence
        freq *= lacunarity
        if freq > size // 2:
            break
    return normalize(out / total)


def value_noise(size: int, cells: int, seed: int) -> np.ndarray:
    """Periodic value noise with smooth (cubic) interpolation; `cells` lattice cells per tile."""
    r = rng(seed)
    grid = r.random((cells, cells)).astype(np.float32)
    coords = (np.arange(size, dtype=np.float32) + 0.5) * cells / size - 0.5
    i0 = np.floor(coords).astype(int)
    t = coords - i0
    t = t * t * (3 - 2 * t)
    i0 %= cells
    i1 = (i0 + 1) % cells
    a = grid[i0[:, None], i0[None, :]]
    b = grid[i0[:, None], i1[None, :]]
    c = grid[i1[:, None], i0[None, :]]
    d = grid[i1[:, None], i1[None, :]]
    tx, ty = t[None, :], t[:, None]
    return (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty


def worley(size: int, points: int, seed: int, *, jitter: float = 1.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Tileable cellular noise. Returns (F1, F2, cell_id) where F* are distances in pixels and
    cell_id is the index of the nearest feature point (useful for per-cell colour variation)."""
    r = rng(seed)
    pts = r.random((points, 2)) * size
    if jitter < 1.0:
        g = int(np.ceil(np.sqrt(points)))
        base = np.stack(np.meshgrid(np.arange(g), np.arange(g)), -1).reshape(-1, 2)[:points]
        pts = (base + 0.5 + (r.random((points, 2)) - 0.5) * jitter) * (size / g)
    tiled = np.concatenate([pts + np.array([dx, dy]) * size for dx in (-1, 0, 1) for dy in (-1, 0, 1)])
    ids = np.tile(np.arange(points), 9)
    tree = cKDTree(tiled)
    yy, xx = np.mgrid[0:size, 0:size]
    q = np.stack([xx.ravel() + 0.5, yy.ravel() + 0.5], -1)
    d, idx = tree.query(q, k=2)
    f1 = d[:, 0].reshape(size, size).astype(np.float32)
    f2 = d[:, 1].reshape(size, size).astype(np.float32)
    cid = ids[idx[:, 0]].reshape(size, size)
    return f1, f2, cid


def warp(field: np.ndarray, dx: np.ndarray, dy: np.ndarray, amount: float) -> np.ndarray:
    """Domain warp (periodic) by displacement fields in [0,1] scaled to `amount` pixels."""
    size = field.shape[0]
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    x = (xx + (dx - 0.5) * 2 * amount) % size
    y = (yy + (dy - 0.5) * 2 * amount) % size
    return ndimage.map_coordinates(field, [y, x], order=1, mode="grid-wrap")


def blur(field: np.ndarray, sigma: float) -> np.ndarray:
    return ndimage.gaussian_filter(field, sigma, mode="wrap")


def normalize(a: np.ndarray) -> np.ndarray:
    a = a.astype(np.float32)
    lo, hi = float(a.min()), float(a.max())
    return (a - lo) / (hi - lo) if hi > lo else np.zeros_like(a)


def levels(a: np.ndarray, lo: float, hi: float, gamma: float = 1.0) -> np.ndarray:
    return np.clip((a - lo) / max(1e-6, hi - lo), 0, 1) ** gamma


def smoothstep(e0: float, e1: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def tile_offset(a: np.ndarray, frac: float = 0.5) -> np.ndarray:
    """Roll by half a tile — handy to inspect seams."""
    s = int(a.shape[0] * frac)
    return np.roll(np.roll(a, s, 0), s, 1)


# --------------------------------------------------------------------------------------------
# Colour helpers
# --------------------------------------------------------------------------------------------

def hex_rgb(h: str) -> np.ndarray:
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], np.float32)


def gradient(t: np.ndarray, stops: list[tuple[float, str]]) -> np.ndarray:
    """Maps a [0,1] field through colour stops [(pos, '#rrggbb'), ...] -> (H, W, 3) sRGB floats."""
    pos = np.array([s[0] for s in stops], np.float32)
    cols = np.stack([hex_rgb(s[1]) for s in stops])
    out = np.empty(t.shape + (3,), np.float32)
    for c in range(3):
        out[..., c] = np.interp(t, pos, cols[:, c])
    return out


def mix(a: np.ndarray, b: np.ndarray, t: np.ndarray) -> np.ndarray:
    if t.ndim == a.ndim - 1:
        t = t[..., None]
    return a + (b - a) * t


# --------------------------------------------------------------------------------------------
# PBR map derivation
# --------------------------------------------------------------------------------------------

def height_to_normal(height: np.ndarray, strength: float = 4.0) -> np.ndarray:
    """Tangent-space normal map (OpenGL/Godot convention) from a periodic height field.
    strength ~ pixel-height scale; returns (H, W, 3) in [0,1]."""
    dx = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) * 0.5
    dy = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) * 0.5
    nx = -dx * strength
    ny = dy * strength  # image rows go down; +Y (green) points up in OpenGL convention
    nz = np.ones_like(height)
    n = np.stack([nx, ny, nz], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n * 0.5 + 0.5


def cavity_ao(height: np.ndarray, radius: float = 6.0, strength: float = 1.0) -> np.ndarray:
    """Cheap ambient occlusion: how far below its blurred neighbourhood each texel is."""
    local = height - blur(height, radius)
    return np.clip(1.0 + local * strength * 4.0, 0.0, 1.0)


# --------------------------------------------------------------------------------------------
# Saving
# --------------------------------------------------------------------------------------------

def _to8(a: np.ndarray) -> np.ndarray:
    return (np.clip(a, 0, 1) * 255.0 + 0.5).astype(np.uint8)


def save_rgb(path: str | pathlib.Path, rgb: np.ndarray) -> None:
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(_to8(rgb), "RGB").save(path, optimize=False, compress_level=6)


def save_rgba(path: str | pathlib.Path, rgba: np.ndarray) -> None:
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(_to8(rgba), "RGBA").save(path, optimize=False, compress_level=6)


def save_gray(path: str | pathlib.Path, g: np.ndarray) -> None:
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(_to8(g), "L").save(path, optimize=False, compress_level=6)


def save_orm(path: str | pathlib.Path, ao: np.ndarray, rough: np.ndarray, metal: np.ndarray | float = 0.0) -> None:
    if not isinstance(metal, np.ndarray):
        metal = np.full_like(ao, float(metal))
    save_rgb(path, np.stack([ao, rough, metal], -1))


def save_pbr_set(base: pathlib.Path, albedo: np.ndarray, height: np.ndarray, rough: np.ndarray,
                 *, metal: np.ndarray | float = 0.0, normal_strength: float = 4.0, ao_strength: float = 1.0,
                 alpha: np.ndarray | None = None) -> list[pathlib.Path]:
    """Writes <base>_albedo.png (RGBA if alpha), <base>_normal.png, <base>_orm.png."""
    base = pathlib.Path(base)
    a_path = base.with_name(base.name + "_albedo.png")
    n_path = base.with_name(base.name + "_normal.png")
    o_path = base.with_name(base.name + "_orm.png")
    if alpha is not None:
        save_rgba(a_path, np.concatenate([albedo, alpha[..., None]], -1))
    else:
        save_rgb(a_path, albedo)
    save_rgb(n_path, height_to_normal(height, normal_strength))
    save_orm(o_path, cavity_ao(height, strength=ao_strength), rough, metal)
    return [a_path, n_path, o_path]
