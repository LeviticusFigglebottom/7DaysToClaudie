"""Object moss: the moss that grows on rocks, bark, logs, stumps and moss mounds.

Built with the terrain generator's physical compositor (terrain.Ground): feather-moss shoots are
rasterised with a z-buffer over soft cushions, so the texture has real fronds and hollows instead
of blurred noise. It is the moss_ground terrain recipe without the forest litter (it also grows on
vertical bark and rock faces) at a finer 1.2 m tile, because objects show it up close.
"""
from __future__ import annotations

import numpy as np

from .. import texlib as T
from ..registry import texture
from . import terrain as G_

TILE_M = 1.2


@texture("moss", size=1024, seed=21, kind="pbr", sources=["tools/assetgen/textures/gen/terrain.py"])
def moss(size: int, seed: int, out) -> None:
    """Feather moss over cushions: dark hollows, yellow-green growing tips, a few browned patches
    and a sprinkle of fallen needles caught in it."""
    n = size
    G = G_.Ground(n, TILE_M)
    r = G_._rng(seed)
    hum = G_._band(n, 2, 7, seed + 1, 2.0)
    f1, _, _ = T.worley(n, 160, seed + 2)
    cell = n / np.sqrt(160)
    cush = G_._blur(np.clip(1 - (f1 / (cell * 0.85)) ** 2, 0, 1), 4.0)
    fine = G_._spec(n, 0.8, seed + 3)
    G.h[:] = (0.016 * hum + 0.006 * cush + 0.0008 * fine).ravel()
    age = T.normalize(0.5 * hum + 0.25 * cush + 0.25 * G_._band(n, 6, 24, seed + 4))
    G.col[:] = (T.gradient(np.clip(0.6 * age + 0.4 * fine, 0, 1), G_.MOSS_STOPS) * 0.45).reshape(-1, 3)
    G.rough[:] = 0.9
    G.tag[:] = G_.TAG_MOSS
    dens = 0.8 + 0.2 * G_._band(n, 3, 10, seed + 5)
    dead = G_._ss(0.66, 0.88, G_._band(n, 4, 10, seed + 6, 1.3))
    G_._fronds(G, r, 5200, dens, (0.02, 0.05), G_.MOSS_STOPS, age=age, nb=9)
    G_._fronds(G, r, 1000, dead, (0.02, 0.045), G_.MOSS_DEAD, age=age, nb=9, lift=0.0005)
    G_._fronds(G, r, 4400, dens, (0.016, 0.04), G_.MOSS_STOPS, age=np.clip(age + 0.12, 0, 1), nb=8, lift=0.0006)
    env = G_._envelope(G)
    G_._needles(G, r, 90, None, G_.NEEDLE_STOPS, (0.012, 0.022), (0.4, 0.5), age=G_._band(n, 4, 14, seed + 11), env=env)
    col = G.C().copy()
    wet = 1 - G_._ss(0.2, 0.6, hum)
    col *= (1 - 0.12 * wet)[..., None]
    L = G_._finish(col, G.H().copy(), G.R().copy(), G.px, exag=1.3, ao_strength=1.8, ao_bake=0.6,
                   ao_radii=(1.0, 2.5, 6, 16), target=G_.TARGET_LUM["moss_ground"])
    G_._save_layer_set(out, L)
