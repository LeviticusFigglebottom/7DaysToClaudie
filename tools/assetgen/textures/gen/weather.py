"""Weather particle textures (ADR-0033): snowflakes for the precipitation draw shader.

fx_snowflakes is a 4x4 atlas (128 px cells, row-major) of falling snow as it looks up close: most
cells are aggregates of a few dendritic crystals (six arms with side branches, rimed soft at their
tips) stuck together at angles, the rest are rimed lumps (graupel). White with straight alpha; every
cell fades to 0 well inside its border so mips never bleed between cells.
"""
from __future__ import annotations

import pathlib

import numpy as np
from scipy import ndimage

from .. import texlib as T
from ..registry import texture


def _seg_dist(px: np.ndarray, py: np.ndarray, a: tuple, b: tuple) -> np.ndarray:
    ax, ay = a
    bx, by = b
    vx, vy = bx - ax, by - ay
    ll = max(vx * vx + vy * vy, 1e-9)
    t = np.clip(((px - ax) * vx + (py - ay) * vy) / ll, 0.0, 1.0)
    dx = px - (ax + t * vx)
    dy = py - (ay + t * vy)
    return np.sqrt(dx * dx + dy * dy)


def _dendrite(px, py, cx, cy, R, rot, r: np.random.Generator) -> np.ndarray:
    """Alpha of one six-armed crystal of radius R (pixels) centred at (cx, cy)."""
    a = np.zeros_like(px)
    w = max(0.9, R * 0.045)
    branch_t = sorted(r.uniform(0.25, 0.8, int(r.integers(2, 5))))
    for k in range(6):
        th = rot + k * np.pi / 3.0
        ex, ey = cx + np.cos(th) * R, cy + np.sin(th) * R
        d = _seg_dist(px, py, (cx, cy), (ex, ey))
        a = np.maximum(a, np.clip(1.0 - d / w, 0.0, 1.0))
        for t in branch_t:
            bx, by = cx + np.cos(th) * R * t, cy + np.sin(th) * R * t
            L = R * (1.0 - t) * 0.55
            for s in (-1.0, 1.0):
                tb = th + s * np.pi / 3.0
                d2 = _seg_dist(px, py, (bx, by), (bx + np.cos(tb) * L, by + np.sin(tb) * L))
                a = np.maximum(a, np.clip(1.0 - d2 / (w * 0.8), 0.0, 1.0) * 0.9)
    # A rimed hub.
    hub = np.hypot(px - cx, py - cy)
    a = np.maximum(a, np.clip(1.0 - hub / (R * 0.16), 0.0, 1.0))
    return a


@texture("fx_snowflakes", size=512, seed=6451, kind="single", import_kind="albedo")
def fx_snowflakes(size: int, seed: int, out) -> None:
    n = size // 4
    r = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32) + 0.5
    border = np.minimum(np.minimum(xx, n - xx), np.minimum(yy, n - yy)) / n
    fade = T.smoothstep(0.03, 0.12, border).astype(np.float32)
    cells = []
    for k in range(16):
        a = np.zeros((n, n), np.float32)
        if k % 5 == 4:
            # Graupel: a rimed lump, soft-edged and knobbly.
            nz = T.spectral(n, 1.8, seed + k).astype(np.float32)
            d = np.hypot(xx - n / 2, yy - n / 2) / (n * (0.18 + 0.06 * r.random()))
            a = np.clip(1.3 - d - (nz - 0.5) * 0.9, 0.0, 1.0)
        else:
            # An aggregate: two to four crystals stuck together, seen at angles (squashed).
            for _ in range(int(r.integers(1, 4)) + (1 if k % 3 == 0 else 0)):
                R = n * r.uniform(0.17, 0.3)
                cx = n / 2 + r.normal(0.0, n * 0.07)
                cy = n / 2 + r.normal(0.0, n * 0.07)
                tilt = r.uniform(0.45, 1.0)
                ang = r.uniform(0.0, np.pi)
                ca, sa = np.cos(ang), np.sin(ang)
                # Foreshorten: rotate, squash one axis, rotate back.
                u = (xx - cx) * ca + (yy - cy) * sa
                v = (-(xx - cx) * sa + (yy - cy) * ca) / tilt
                px = cx + u * ca - v * sa
                py = cy + u * sa + v * ca
                a = np.maximum(a, _dendrite(px, py, cx, cy, R, r.uniform(0, np.pi), r) * r.uniform(0.75, 1.0))
            a = ndimage.gaussian_filter(a, 0.7)
        a = np.clip(a, 0.0, 1.0) * fade
        # Thin parts read faintly blue-grey (ice), thick parts white.
        col = np.stack([0.9 + 0.1 * a, 0.93 + 0.07 * a, 0.98 + 0.02 * a], -1).astype(np.float32)
        cells.append(np.concatenate([col, a[..., None]], -1))
    rows = [np.concatenate(cells[i:i + 4], 1) for i in range(0, 16, 4)]
    T.save_rgba(pathlib.Path(str(out) + ".png"), np.concatenate(rows, 0))
