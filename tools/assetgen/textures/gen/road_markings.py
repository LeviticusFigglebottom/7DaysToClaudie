"""Painted road lines (game/src/world/road_markings.gd projects them as decals along asphalt roads).

One worn white line per texture; the decal's modulate tints the centre line yellow. The canvas is
1024 x 128: X runs 3 m along the line, the line itself fills the middle 70 % of Y (15 cm wide on a
decal sized to that). Paint is a raised film: it wears through where the aggregate peaks and where
tyres run, cracks in the asphalt break it, and road grime darkens it toward the edges.
"""
from __future__ import annotations

import numpy as np

from .. import texlib as T
from ..registry import texture
from . import decals as D

W, H = 1024, 128


def _line(seed: int, wear: float):
    r = D._rng(seed)
    xx, yy = D._grid(H, W)
    v = np.abs(yy - H * 0.5) / (H * 0.35)                       # 0 at the centre line, 1 at its edge
    ragged = 0.06 * (D._noise(H, W, 1.2, seed + 1) - 0.5) + 0.03 * (D._noise(H, W, 0.4, seed + 2) - 0.5)
    body = D._ss(1.0 + ragged + 0.04, 1.0 + ragged - 0.04, v)
    # Ends: short ragged fade (continuous lines butt-join segments, so keep it short).
    end = D._ss(0.0, W * 0.012, np.minimum(xx, W - xx) + 6.0 * (D._noise(H, W, 1.0, seed + 3) - 0.5))
    # Wear: aggregate peaks through the film, a broad tyre-worn patch, flaking clusters.
    grit = D._noise(H, W, 0.15, seed + 4)
    patch = D._noise(H, W, 2.0, seed + 5)
    flakes = D._noise(H, W, 1.4, seed + 6)
    loss = np.clip(D._ss(0.62, 0.78, grit) * 0.7 + D._ss(0.55, 0.8, patch) * wear + D._ss(0.7, 0.76, flakes) * wear, 0, 1)
    # Asphalt cracks crossing the line: thin meandering gaps, mostly transverse.
    cracks = np.zeros((H, W), np.float32)
    for _ in range(int(r.integers(2, 5))):
        x0 = r.uniform(0.05, 0.95) * W
        wob = D._noise1(H, 1.5, int(r.integers(1 << 30))) - 0.5
        cx = x0 + wob[:, None] * r.uniform(10, 40)
        cracks = np.maximum(cracks, 1.0 - D._ss(0.6, 2.2, np.abs(xx - cx)))
    alpha = body * end * (1.0 - 0.85 * loss) * (1.0 - cracks)
    # Colour: bead-blasted white paint, greyed by grime at its edges and in the worn patches.
    tone = 0.86 + 0.08 * (D._noise(H, W, 1.0, seed + 7) - 0.5)
    rgb = np.ones((H, W, 3), np.float32) * tone[..., None]
    grime = np.clip(D._ss(0.4, 1.0, v) * 0.35 + loss * 0.3, 0, 1)
    rgb = T.mix(rgb, D._hex("#7d786e")[None, None, :] * np.ones_like(rgb), grime)
    height = alpha * (0.6 + 0.4 * grit)
    rough = 0.5 + 0.35 * loss
    return rgb, alpha, height, rough


@texture("decal_road_line_a", size=1024, seed=5301, kind="pbr_alpha")
def decal_road_line_a(size: int, seed: int, out) -> None:
    """Moderately worn line."""
    rgb, a, h, rough = _line(seed, 0.45)
    D._save(out, rgb, a, height=h, strength=2.0, rough=rough)


@texture("decal_road_line_b", size=1024, seed=5302, kind="pbr_alpha")
def decal_road_line_b(size: int, seed: int, out) -> None:
    """Heavily worn line: broad gaps where tyres run."""
    rgb, a, h, rough = _line(seed, 0.8)
    D._save(out, rgb, a, height=h, strength=2.0, rough=rough)
