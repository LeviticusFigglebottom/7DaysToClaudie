"""Stone surfaces: weathered granite (object moss lives in gen/moss.py)."""
from __future__ import annotations

import numpy as np

from .. import texlib as T
from ..registry import texture


def _level_lines(n: np.ndarray, width_px: float) -> np.ndarray:
    """1 on the median level set of n, falling to 0 at width_px pixels (uniform-width lines)."""
    m = float(np.median(n))
    gx = (np.roll(n, -1, 1) - np.roll(n, 1, 1)) * 0.5
    gy = (np.roll(n, -1, 0) - np.roll(n, 1, 0)) * 0.5
    d = np.abs(n - m) / (np.sqrt(gx * gx + gy * gy) + 1e-6)
    return np.clip(1.0 - d / width_px, 0.0, 1.0).astype(np.float32)


@texture("rock_granite", size=1024, seed=11)
def rock_granite(size: int, seed: int, out) -> None:
    """Weathered grey granite: salt-and-pepper mineral speckle (feldspar, quartz, biotite) over
    broad mottling, a few long natural fractures (sparse, wandering, partly healed), vertical
    weathering/rain streaks (v is up on box-projected sides) and crusty lichen patches."""
    r = T.rng(seed)
    broad = T.spectral(size, 2.6, seed)
    mid = T.spectral(size, 1.8, seed + 1)
    fine = T.spectral(size, 1.0, seed + 2)
    # minerals: two independent high-frequency fields carve feldspar / biotite grains
    g1 = T.spectral(size, 0.25, seed + 3)
    g2 = T.spectral(size, 0.35, seed + 4)
    g3 = T.spectral(size, 0.3, seed + 5)
    base = T.gradient(T.normalize(0.65 * broad + 0.35 * mid), [(0.0, "#6d6a64"), (0.5, "#85817a"), (1.0, "#9a958c")])
    feld = T.smoothstep(0.62, 0.7, g1)
    bio = T.smoothstep(0.74, 0.8, g2)
    quartz = T.smoothstep(0.66, 0.74, g3) * (1 - feld)
    pinkish = T.smoothstep(0.55, 0.75, T.spectral(size, 2.2, seed + 6))
    feld_col = T.mix(np.ones_like(base) * _gc("#c9c3b8"), np.ones_like(base) * _gc("#c8b4a4"), pinkish * 0.6)
    alb = T.mix(base, feld_col, feld * 0.9)
    alb = T.mix(alb, np.ones_like(base) * _gc("#a7a8a6"), quartz * 0.6)
    alb = T.mix(alb, np.ones_like(base) * _gc("#1e1c1a"), bio * 0.95)
    # broad tonal mottling (weathering rind vs fresher rock)
    alb = alb * (0.86 + 0.24 * broad)[..., None]
    # vertical rain streaks: dark grey-brown runs
    streak = T.spectral(size, 1.5, seed + 7, anisotropy=(9.0, 1.0))
    sm = T.smoothstep(0.58, 0.8, streak) * T.smoothstep(0.35, 0.65, T.spectral(size, 2.0, seed + 8))
    alb = T.mix(alb, alb * np.array([0.7, 0.68, 0.64], np.float32), sm * 0.55)
    # long natural fractures: level sets of wandering noise, gated so only some segments crack
    wx, wy = T.spectral(size, 2.2, seed + 9), T.spectral(size, 2.2, seed + 10)
    n = T.warp(T.spectral(size, 2.5, seed + 20, fmin=1.0), wx, wy, size * 0.03)
    crack = _level_lines(n, 1.8) * T.smoothstep(0.5, 0.6, T.spectral(size, 2.2, seed + 30))
    n2 = T.warp(T.spectral(size, 2.3, seed + 21, fmin=2.0), wx, wy, size * 0.02)
    crack = np.maximum(crack, _level_lines(n2, 1.2) * T.smoothstep(0.62, 0.7, T.spectral(size, 2.2, seed + 31)) * 0.8)
    # crack halo: weathered, slightly darker/stained band along fractures
    halo = T.blur(crack, 4.0)
    alb = alb * (1.0 - 0.18 * np.clip(halo * 3, 0, 1))[..., None]
    alb = T.mix(alb, np.ones_like(alb) * _gc("#1d1b18"), crack * 0.85)
    # lichen: crusty roundish patches, mostly pale grey-green, some yellow-green, rare orange
    lich_n = T.spectral(size, 0.9, seed + 11)
    f1, f2, cid = T.worley(size, 150, seed + 12, jitter=0.8)
    rad = (r.uniform(0.2, 1.0, 150) ** 1.5)[cid] * size * 0.03
    blob = T.smoothstep(0.0, 0.12, 1.0 - f1 / np.maximum(rad, 1.0) + (lich_n - 0.5) * 0.7)
    pick = (np.sin(cid * 91.7) * 43758.5) % 1.0
    keep = (pick < 0.5).astype(np.float32)
    lcol = np.where((pick < 0.38)[..., None], _gc("#8f9482")[None, None, :] * np.ones_like(alb),
                    np.where((pick < 0.5)[..., None], _gc("#93915a")[None, None, :] * np.ones_like(alb),
                             _gc("#9c6a3c")[None, None, :] * np.ones_like(alb)))
    cluster = T.smoothstep(0.4, 0.6, T.spectral(size, 2.0, seed + 13))
    lich = blob * keep * cluster * (0.55 + 0.45 * T.smoothstep(0.3, 0.7, fine))
    alb = T.mix(alb, lcol * (0.9 + 0.2 * lich_n)[..., None], lich * 0.38)
    height = 0.45 * broad + 0.25 * mid + 0.12 * fine + 0.05 * feld - 0.04 * bio + 0.06 * lich - 0.35 * crack
    height = T.normalize(height)
    rough = np.clip(0.82 + 0.08 * (fine - 0.5) - 0.12 * quartz + 0.08 * lich + 0.05 * crack, 0, 1)
    ao = np.clip(T.cavity_ao(height, radius=6, strength=1.2) * (1.0 - 0.3 * crack), 0, 1)
    T.save_rgb(out.with_name(out.name + "_albedo.png"), np.clip(alb, 0, 1))
    T.save_rgb(out.with_name(out.name + "_normal.png"), T.height_to_normal(height, 4.0))
    T.save_orm(out.with_name(out.name + "_orm.png"), ao, rough, 0.0)


def _gc(h: str) -> np.ndarray:
    return T.hex_rgb(h)
