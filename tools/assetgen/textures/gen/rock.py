"""Stone and earth surfaces: granite, mossy rock, river stone."""
from __future__ import annotations

import numpy as np

from .. import texlib as T
from ..registry import texture


@texture("rock_granite", size=1024, seed=11)
def rock_granite(size: int, seed: int, out) -> None:
    # Large slabby structure + crystalline speckle (feldspar/quartz/biotite) + fine fractures.
    broad = T.spectral(size, 2.6, seed)
    mid = T.spectral(size, 1.8, seed + 1)
    f1, f2, cid = T.worley(size, 36, seed + 2, jitter=0.9)
    cracks = T.smoothstep(0.0, 6.0, (f2 - f1))  # 0 on cell borders
    speck = T.spectral(size, 0.4, seed + 3)
    grains = T.spectral(size, 0.9, seed + 4)
    height = 0.55 * broad + 0.3 * mid + 0.15 * grains
    height = height * (0.82 + 0.18 * cracks)
    height = T.normalize(height)
    base = T.gradient(T.normalize(0.6 * broad + 0.4 * mid), [(0.0, "#6c6862"), (0.5, "#8a857d"), (1.0, "#a49e95")])
    # Mineral speckle: dark biotite flecks and pale feldspar.
    dark = (speck > 0.78).astype(np.float32)
    pale = (speck < 0.14).astype(np.float32)
    base = T.mix(base, T.hex_rgb("#2b2826")[None, None, :] * np.ones_like(base), dark * 0.85)
    base = T.mix(base, T.hex_rgb("#c9c2b6")[None, None, :] * np.ones_like(base), pale * 0.6)
    # Cell-to-cell tint and dark cracks.
    tint = (np.sin(cid * 12.9898) * 43758.5453) % 1.0
    base *= (0.92 + 0.12 * tint)[..., None]
    base *= (0.55 + 0.45 * cracks)[..., None]
    rough = np.clip(0.78 + 0.15 * (1 - cracks) - 0.18 * pale + 0.05 * (grains - 0.5), 0, 1)
    T.save_pbr_set(out, np.clip(base, 0, 1), height, rough, normal_strength=5.0)


@texture("moss", size=1024, seed=21)
def moss(size: int, seed: int, out) -> None:
    clumps = T.spectral(size, 1.6, seed)
    fine = T.spectral(size, 0.5, seed + 1)
    f1, f2, _ = T.worley(size, 900, seed + 2)
    tufts = 1.0 - T.normalize(f1)
    height = T.normalize(0.45 * clumps + 0.35 * tufts + 0.2 * fine)
    col = T.gradient(T.normalize(0.7 * clumps + 0.3 * fine), [(0.0, "#2a3514"), (0.45, "#46561d"), (0.8, "#6a7a2a"), (1.0, "#8a8a3a")])
    col *= (0.75 + 0.35 * tufts)[..., None]
    rough = np.full((size, size), 0.92, np.float32)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=3.0, ao_strength=1.5)
