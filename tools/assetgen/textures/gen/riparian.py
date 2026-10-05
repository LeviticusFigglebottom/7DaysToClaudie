"""Riverbank plants and driftwood: the Tamsin's banks (biome `riverbank`).

`riparian` is a foliage atlas in the same painter style as the plants and grass atlases
(vegetation.py): slough sedge (broad arching blades, dark spikes), common rush (stiff round stems
with brown flower clusters), horsetail (jointed stems with whorled branchlets), two Pacific-willow
twig cards (long narrow leaves, silvery undersides) and a strip of willow bark for the stems.
`driftwood` is bleached, sun-checked wood with the grain raised by water, for stripped logs left on
gravel bars. RIPARIAN is imported by blender_catalogs/vegetation.py.
"""
from __future__ import annotations

import math

import numpy as np

from .. import texlib as T
from ..registry import texture
from . import vegetation as V

RIPARIAN: dict[str, list[float]] = {
    "willow_a": [0.0, 0.0, 0.375, 0.5],
    "willow_b": [0.375, 0.0, 0.75, 0.5],
    "stem": [0.75, 0.0, 0.8125, 0.5],
    "sedge": [0.0, 0.5, 0.5, 1.0],
    "rush": [0.5, 0.5, 0.75, 1.0],
    "horsetail": [0.75, 0.5, 1.0, 1.0],
}
SRC = ["tools/assetgen/textures/gen/vegetation.py"]


def _sedge(p: V.Painter, rng, box) -> None:
    """Slough sedge: dense fountain of broad keeled blades arching outward, tips browning, a few
    dark nodding spikes on stiff culms."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    greens = [V._c("#2f4a1d"), V._c("#3a5823"), V._c("#46652a"), V._c("#334f20"), V._c("#55703a")]
    blades = []
    for _ in range(170):
        bx = x0 + w * 0.5 + rng.normal(0, w * 0.08)
        side = (bx - (x0 + w * 0.5)) / w
        lean = rng.normal(0, 0.25) + side * 1.4
        hh = h * rng.uniform(0.45, 0.95)
        col = V._jit(rng, greens[int(rng.integers(0, 5))], 0.1, 0.04)
        tip = np.clip(col * np.array([1.6, 1.35, 0.9]) + np.array([0.05, 0.03, 0.0]), 0, 1)
        curl = (0.9 + rng.uniform(0, 0.8)) * (1 if lean >= 0 else -1)
        blades.append((rng.random(), bx, lean, hh, col, tip, rng.uniform(4.5, 8.0), curl))
    for z, bx, lean, hh, col, tip, wd, curl in sorted(blades, key=lambda b: b[0]):
        V.grass_blade(p, rng, (bx, y1 - 3), hh, lean, col, tip, wd, z * 4, curl=curl, segs=10)
    for _ in range(9):
        bx = x0 + w * 0.5 + rng.normal(0, w * 0.07)
        pts = V.grass_blade(p, rng, (bx, y1 - 3), h * rng.uniform(0.6, 0.9), rng.normal(0, 0.18), V._c("#4a5a2a"),
                            V._c("#5a6a34"), 2.2, 5.0, curl=rng.uniform(-0.4, 0.4))
        tx, ty = pts[-1]
        for k in range(4):
            ang = rng.uniform(2.4, 3.6) if k else math.pi
            ln = rng.uniform(26, 44)
            p.blade((tx, ty + k * 10), (tx + math.sin(ang) * ln * 0.4, ty + k * 10 - math.cos(ang) * ln), 9.0,
                    V._jit(rng, V._c("#2a2018"), 0.1), V._c("#1a140f"), h0=6.0)


def _rush(p: V.Painter, rng, box) -> None:
    """Common rush: stiff, smooth, round stems fanning slightly, brown flower clusters bursting
    from one side two-thirds up."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    for i in range(120):
        bx = x0 + w * 0.5 + rng.normal(0, w * 0.1)
        lean = rng.normal(0, 0.1) + (bx - (x0 + w * 0.5)) / w * 0.5
        hh = h * rng.uniform(0.55, 0.97)
        col = V._jit(rng, V._c("#5a7a2c"), 0.12, 0.04)
        pts = V.grass_blade(p, rng, (bx, y1 - 3), hh, lean, col, np.clip(col * 1.15, 0, 1) * np.array([1.1, 1.0, 0.8]),
                            3.2, rng.random() * 3, curl=rng.uniform(-0.08, 0.08), segs=6)
        if rng.random() < 0.35:
            cx, cy = pts[4]
            for _ in range(10):
                p.disc((cx + rng.uniform(1, 9), cy + rng.uniform(-8, 8)), rng.uniform(1.6, 3.0),
                       V._jit(rng, V._c("#6a5230"), 0.15), 4.0, 0.8, shade=0.4)


def _horsetail(p: V.Painter, rng, box) -> None:
    """Field horsetail: upright jointed stems with dark sheaths at every node and whorls of thin
    branchlets angled up and out (a bottle-brush)."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    for i in range(16):
        bx = x0 + w * 0.5 + rng.normal(0, w * 0.17)
        hh = h * rng.uniform(0.55, 0.95)
        lean = rng.normal(0, 0.07)
        n = 11
        seg = hh / n
        x, y = bx, y1 - 3
        z = rng.random() * 4
        stem_col = V._jit(rng, V._c("#6b8a35"), 0.08, 0.03)
        for k in range(n):
            nx_, ny_ = x + math.sin(lean) * seg, y - math.cos(lean) * seg
            p.capsule((x, y), (nx_, ny_), 3.4 * (1 - 0.5 * k / n), 3.0 * (1 - 0.5 * (k + 1) / n), stem_col, stem_col, z, 0.6)
            p.capsule((nx_, ny_ + 1.5), (nx_, ny_ - 1.5), 3.8 * (1 - 0.5 * k / n), 3.8 * (1 - 0.5 * k / n),
                      V._c("#2c3318"), V._c("#2c3318"), z + 0.5, 0.6)
            if 1 <= k < n - 1:
                ln = seg * rng.uniform(1.6, 2.4) * (1.0 - 0.55 * k / n)
                for j in range(7):
                    a = (j / 7) * math.pi - math.pi * 0.5 + rng.uniform(-0.15, 0.15)
                    side = math.sin(a)
                    up = 0.55 + 0.25 * abs(math.cos(a))
                    tip = (nx_ + side * ln, ny_ - ln * up * 0.5)
                    p.capsule((nx_, ny_), tip, 1.2, 0.6, V._jit(rng, V._c("#7a9a40"), 0.08), V._c("#8faa50"), z + 1.0, 0.5)
            x, y = nx_, ny_


def _willow(p: V.Painter, rng, box, cols, scale) -> None:
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    for t in range(3):
        base = (x0 + w * rng.uniform(0.42, 0.58), y1 - 4)
        V.leaf_twig(p, rng, base, rng.uniform(-0.25, 0.25), h * rng.uniform(0.8, 0.95), leaf_len=h * 0.2,
                    leaf_w=h * 0.032, n_leaves=16, cols=cols, twig_col=V._c("#6e5a32"), twig_r=3.0 * scale,
                    a=0.6, b=1.4, teeth=30, serr=0.06, hbase=t * 3.0, petiole=0.06, spread=(20, 45), droop=0.15,
                    side_twigs=3, holes_p=0.05, scale=scale, vein_col=V._c("#a8b48a"))


@texture("riparian", size=2048, seed=5501, kind="pbr_alpha", sources=SRC)
def riparian(size: int, seed: int, out) -> None:
    p = V.Painter(size)
    r = T.rng(seed)
    for name, fn in (("sedge", _sedge), ("rush", _rush), ("horsetail", _horsetail)):
        box = V.rect_px(RIPARIAN[name], size)
        p.set_clip(box)
        fn(p, T.rng(seed + sum(map(ord, name))), box)  # str hash() is salted per process
    green = [V._c("#6f8a3a"), V._c("#7b9644"), V._c("#5f7a32"), V._c("#8aa04e")]
    silver = [V._c("#9ba58a"), V._c("#8f9a7e"), V._c("#a7b096")]
    for name, cols, sc in (("willow_a", green + silver[:1], 1.6), ("willow_b", green[:2] + silver + [V._c("#a89a4a")], 1.5)):
        box = V.rect_px(RIPARIAN[name], size)
        p.set_clip(box)
        _willow(p, T.rng(seed + len(name) * 31 + int(sc * 10)), box, cols, sc)
    # Willow bark strip for the stems: smooth olive-brown with lenticels and fine vertical cracks.
    x0, y0, x1, y1 = V.rect_px(RIPARIAN["stem"], size)
    p.set_clip((x0, y0, x1, y1))
    bw, bh = x1 - x0, y1 - y0
    tone = T.normalize(T.spectral(max(bw, bh), 1.6, seed + 3)[:bh, :bw])
    col = T.gradient(tone, [(0.0, "#4a3e26"), (0.5, "#5e4e30"), (1.0, "#72603c")])
    p.rgb[y0:y1, x0:x1] = col
    p.a[y0:y1, x0:x1] = 1.0
    p.ht[y0:y1, x0:x1] = 2.0 + tone
    for _ in range(140):
        cx, cy = x0 + r.uniform(0, bw), y0 + r.uniform(0, bh)
        p.disc((cx, cy), r.uniform(1.0, 2.2), V._c("#8a7a58"), 3.0, 0.5)
    p.set_clip(None)
    V.finish_foliage(p, out, rough=0.62, rough_var=0.1, normal_strength=2.0, alpha_boost=1.3, seed=seed)


@texture("driftwood", size=1024, seed=5511, sources=SRC)
def driftwood(size: int, seed: int, out) -> None:
    """Bark-less, water-scoured log wood bleached silver: raised late-wood grain, long drying checks,
    darker damp underside tones and a few iron-stained knots. Grain runs along U."""
    n = size
    x, y = np.meshgrid(np.arange(n) / n, np.arange(n) / n)
    warp = T.spectral(n, 2.2, seed + 1) - 0.5
    rings = 0.5 + 0.5 * np.sin((y + 0.05 * warp) * 2 * np.pi * 34 + 3.0 * (T.spectral(n, 2.6, seed + 2) - 0.5))
    late = T.smoothstep(0.55, 0.95, rings)
    fib = T.spectral(n, 1.0, seed + 3, anisotropy=(1.0, 14.0))     # fibres along U
    checks = np.zeros((n, n), np.float32)
    rr = T.rng(seed + 4)
    for _ in range(9):
        # A drying check: a thin crack along the grain, wandering a little, open over part of its run.
        yc = rr.uniform(0, 1)
        wob = (T.spectral(n, 1.6, int(rr.integers(1 << 30)))[0] - 0.5) * 0.012
        d = np.abs(((y - yc - wob[None, :]) + 0.5) % 1.0 - 0.5)
        run = T.smoothstep(0.3, 0.6, T.spectral(n, 1.8, int(rr.integers(1 << 30)), anisotropy=(1.0, 8.0)))
        checks = np.maximum(checks, (1.0 - T.smoothstep(0.0008, 0.0025, d)) * run)
    tone = T.normalize(0.45 * fib + 0.35 * T.spectral(n, 2.2, seed + 5) + 0.2 * late)
    col = T.gradient(tone, [(0.0, "#6d6a63"), (0.4, "#8c877d"), (0.75, "#a7a196"), (1.0, "#bdb6a9")])
    col = T.mix(col, col * 0.78, late * 0.5)
    knots = T.smoothstep(0.84, 0.9, T.spectral(n, 1.4, seed + 6))
    col = T.mix(col, T.hex_rgb("#5a4632")[None, None, :] * np.ones_like(col), knots * 0.6)
    col *= (1.0 - 0.6 * checks)[..., None]
    height = np.clip(0.5 + 0.25 * late + 0.08 * fib - 0.6 * checks + 0.1 * knots, 0, 1)
    rough = np.clip(0.82 + 0.08 * (fib - 0.5) + 0.1 * checks, 0, 1)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=5.0, ao_strength=1.3)
