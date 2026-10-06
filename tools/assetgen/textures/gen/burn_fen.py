"""Burnt forest and fen (ADR-0041): fire char for the burnt snags, and the fen's plants.

`bark_char` is the alligatored char of a fire-killed conifer: the bark burnt to charcoal and
cracked into blocks taller than wide (V runs up the trunk, as in every bark set), deep black
fissures between them with grey ash lodged in some, block faces dull black with a silvery sheen
where years of weather polished them, fine crazing on the faces, and a few blocks spalled off
to show the brown under-bark. The bark shader lays it over the silver weathered wood of
`bark_dead` from the roots up to a ragged char line (bark.gdshader, `char_*`).

`fen_plants` is a foliage atlas in the painter style of vegetation.py: cattail (broad strap
leaves and brown seed heads on stiff stalks), hardstem bulrush (tall round stems with brown
spikelet clusters), three skunk-cabbage leaves (big glossy paddles with a pale midrib) and its
yellow spathe, and two bracken fronds (broad triangular, twice-cut, yellowing) with a
fiddlehead. FEN is imported by blender_catalogs/vegetation.py.
"""
from __future__ import annotations

import math

import numpy as np

from .. import texlib as T
from ..registry import texture
from . import vegetation as V

FEN: dict[str, list[float]] = {
    "cattail": [0.0, 0.0, 0.25, 1.0],
    "bulrush": [0.25, 0.0, 0.4375, 1.0],
    "skunk_a": [0.4375, 0.0, 0.625, 0.5],
    "skunk_b": [0.625, 0.0, 0.8125, 0.5],
    "skunk_c": [0.8125, 0.0, 1.0, 0.5],
    "skunk_young": [0.4375, 0.5, 0.5625, 0.75],
    "bracken_young": [0.4375, 0.75, 0.5625, 1.0],
    "bracken_a": [0.5625, 0.5, 0.78125, 1.0],
    "bracken_b": [0.78125, 0.5, 1.0, 1.0],
}
SRC = ["tools/assetgen/textures/gen/vegetation.py"]


@texture("bark_char", size=1024, seed=6101, sources=SRC)
def bark_char(size: int, seed: int, out) -> None:
    n = size
    rr = T.rng(seed)
    # Blocks in columns (fissures run up the trunk), each column cut into blocks of its own height
    # and offset (staggered like the char on a real snag); every edge wanders with two scales of
    # noise so no line is straight. Periodic: whole columns across, whole rows down each column.
    ncol = 21
    cw = n / ncol
    wx = ((T.spectral(n, 2.2, seed + 1) - 0.5) * cw * 1.1 + (T.spectral(n, 1.4, seed + 13) - 0.5) * cw * 0.35
          + (T.spectral(n, 0.9, seed + 11) - 0.5) * 5.0)
    wy = ((T.spectral(n, 2.2, seed + 2) - 0.5) * cw * 1.2 + (T.spectral(n, 1.4, seed + 14) - 0.5) * cw * 0.3
          + (T.spectral(n, 0.9, seed + 12) - 0.5) * 4.0)
    xs = np.arange(n, dtype=np.float32)[None, :] + wx
    ys = np.arange(n, dtype=np.float32)[:, None] + wy
    cx = xs / cw
    ci = np.floor(cx).astype(np.int64) % ncol
    fx = cx - np.floor(cx)
    nrow = rr.integers(14, 23, ncol)
    off = rr.random(ncol) * n
    rh = (n / nrow).astype(np.float32)
    cy = (ys + off[ci]) / rh[ci]
    ri = np.floor(cy).astype(np.int64) % nrow[ci]
    fy = cy - np.floor(cy)
    # Blocks of uneven height: about a quarter of the cross-cracks never opened, so a block runs on
    # into the next (one id for both) and the rows stop reading as a woven grid in game.
    own = (ci * 97 + ri).astype(np.float32)
    below = (ci * 97 + (ri - 1) % nrow[ci]).astype(np.float32)
    joined = V._cell_rand(own, 6.0) < 0.27
    joined_below = V._cell_rand(below, 6.0) < 0.27
    cid = np.where(joined_below, below, own)
    ex = np.minimum(fx, 1.0 - fx) * cw
    ey = np.minimum(np.where(joined, 1e4, (1.0 - fy) * rh[ci] * 1.15), np.where(joined_below, 1e4, fy * rh[ci] * 1.15))
    # Rounded corners (a smooth minimum): charred blocks bulge, they are not cut square.
    k = 4.0
    hm = np.clip(0.5 + 0.5 * (ey - ex) / k, 0.0, 1.0)
    edge = ex * hm + ey * (1.0 - hm) - k * hm * (1.0 - hm)
    wvar = V._cell_rand(cid, 1.0)
    fiss = 1.0 - T.smoothstep(1.0, 3.0 + 3.5 * wvar, edge)
    deep = 1.0 - T.smoothstep(0.0, 1.4, edge)
    # A few blocks are split again by a finer crack.
    g1, g2, gid, _, _ = V.worley_vec(n, 700, seed + 4, aspect=1.4, warp=(wx * 0.5, wy * 0.5))
    sub = (1.0 - T.smoothstep(0.5, 1.8, g2 - g1)) * T.smoothstep(0.35, 0.6, V._cell_rand(cid, 5.0))
    bh = 0.65 + 0.35 * V._cell_rand(cid, 2.0)
    dome = T.smoothstep(0.0, 14.0, edge) ** 0.55
    c1, c2, _ = T.worley(n, 5200, seed + 6)
    craze = 1.0 - T.smoothstep(0.3, 1.2, c2 - c1)
    fine = T.spectral(n, 0.8, seed + 5)
    grain = T.spectral(n, 1.2, seed + 7, anisotropy=(10.0, 1.0))
    # Spalled blocks: the char has flaked away, showing the under-bark a little deeper.
    spall = (V._cell_rand(cid, 3.0) > 0.975).astype(np.float32) * T.smoothstep(2.0, 8.0, edge)
    height = (0.55 * dome * bh + 0.04 * fine + 0.03 * grain - 0.07 * craze * dome - 0.12 * sub - 0.45 * fiss
              - 0.25 * deep - 0.12 * spall)
    height = T.normalize(height)
    tone = np.clip(0.45 * fine + 0.35 * V._cell_rand(cid, 4.0) + 0.2 * grain, 0, 1)
    alb = T.gradient(tone, [(0.0, "#0b0a09"), (0.4, "#131110"), (0.75, "#1b1917"), (1.0, "#262321")])
    # Weathered sheen: the faces of the blocks greyed and polished (silvery highlights on the tops).
    top = T.smoothstep(0.45, 0.9, dome * bh) * (1.0 - craze * 0.6)
    silver = T.smoothstep(0.5, 0.85, T.spectral(n, 1.6, seed + 8))
    alb = T.mix(alb, np.ones_like(alb) * V._c("#3d3b38"), (top * (0.2 + 0.5 * silver))[..., None])
    alb = alb * (1.0 - 0.45 * craze * dome)[..., None]
    under = T.gradient(np.clip(0.6 * fine + 0.4 * grain, 0, 1), [(0.0, "#24170f"), (0.5, "#382417"), (1.0, "#4a321f")])
    alb = T.mix(alb, under, spall[..., None] * 0.55)
    alb = T.mix(alb, np.ones_like(alb) * V._c("#050404"), np.clip(fiss * 0.9 + deep * 0.1, 0, 1)[..., None])
    # Grey ash dust lodged in some fissures.
    ashy = T.smoothstep(0.55, 0.8, T.spectral(n, 1.5, seed + 9)) * fiss * (1.0 - deep)
    alb = T.mix(alb, np.ones_like(alb) * V._c("#5c5853"), ashy[..., None] * 0.55)
    rough = np.clip(0.62 - 0.16 * top * silver + 0.3 * fiss + 0.2 * spall + 0.08 * craze, 0.35, 1.0)
    ao = np.clip(T.cavity_ao(height, radius=8, strength=1.4) * (0.45 + 0.55 * (1.0 - fiss)), 0, 1)
    V._save_set(out, alb, height, rough, normal_strength=9.0, ao=ao)


# --------------------------------------------------------------------------------------------
# Fen plants atlas
# --------------------------------------------------------------------------------------------

def _cattail(p: V.Painter, rng, box) -> None:
    """Broad-leaved cattail: a fan of flat strap leaves twisting a little as they rise, the outer
    ones bowing out; stiff stalks carrying the brown velvet seed head with a thin spike above."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    greens = [V._c("#4b5e2a"), V._c("#566a30"), V._c("#617436"), V._c("#475a26"), V._c("#6c7a3a")]
    blades = []
    for _ in range(46):
        bx = x0 + w * 0.5 + rng.normal(0, w * 0.06)
        side = (bx - (x0 + w * 0.5)) / w
        lean = rng.normal(0, 0.12) + side * 0.9
        hh = h * rng.uniform(0.55, 0.97)
        col = V._jit(rng, greens[int(rng.integers(0, 5))], 0.1, 0.04)
        tip = np.clip(col * np.array([1.45, 1.3, 0.85]) + np.array([0.04, 0.02, 0.0]), 0, 1)
        curl = rng.uniform(0.05, 0.45) * (1 if lean >= 0 else -1)
        blades.append((rng.random(), bx, lean, hh, col, tip, rng.uniform(7.0, 11.0), curl))
    stalks = []
    for _ in range(4):
        bx = x0 + w * 0.5 + rng.normal(0, w * 0.05)
        stalks.append((rng.random() * 0.8, bx, rng.normal(0, 0.05), h * rng.uniform(0.78, 0.96)))
    items = [(b[0], "leaf", b) for b in blades] + [(s[0], "stalk", s) for s in stalks]
    for z, kind, it in sorted(items, key=lambda q: q[0]):
        if kind == "leaf":
            _, bx, lean, hh, col, tip, wd, curl = it
            V.grass_blade(p, rng, (bx, y1 - 3), hh, lean, col, tip, wd, z * 4, curl=curl, segs=12)
        else:
            _, bx, lean, hh = it
            pts = V.grass_blade(p, rng, (bx, y1 - 3), hh, lean, V._c("#5a6a32"), V._c("#6a7438"), 3.6, z * 4 + 2.0,
                                curl=rng.uniform(-0.05, 0.05), segs=10)
            # The seed head: a long brown cylinder two thirds of the way up the last stretch.
            hx0, hy0 = pts[-4]
            hx1, hy1 = pts[-2]
            head_r = rng.uniform(11.0, 14.0)
            col = V._jit(rng, V._c("#5a3a22"), 0.1, 0.05)
            p.capsule((hx0, hy0), (hx1, hy1), head_r, head_r * 0.95, col, col * 1.08, z * 4 + 4.0, 0.9)
            for _ in range(60):
                t = rng.random()
                cx = hx0 + (hx1 - hx0) * t + rng.uniform(-head_r * 0.7, head_r * 0.7)
                cy = hy0 + (hy1 - hy0) * t
                p.disc((cx, cy), rng.uniform(1.0, 2.2), V._jit(rng, V._c("#6e4a2c"), 0.15), z * 4 + 5.0, 0.4)
            # the thin male spike above it
            sx, sy = pts[-1]
            p.capsule((hx1, hy1), (sx, sy - h * 0.04), 2.2, 1.0, V._c("#7a6a40"), V._c("#8a7a4a"), z * 4 + 4.5, 0.6)


def _bulrush(p: V.Painter, rng, box) -> None:
    """Hardstem bulrush: tall smooth round stems, dark blue-green, nearly straight, each ending in
    a loose drooping cluster of brown spikelets just under the tip."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    for _ in range(70):
        bx = x0 + w * 0.5 + rng.normal(0, w * 0.1)
        lean = rng.normal(0, 0.06) + (bx - (x0 + w * 0.5)) / w * 0.35
        hh = h * rng.uniform(0.6, 0.97)
        col = V._jit(rng, V._c("#3f5a2e"), 0.1, 0.04)
        pts = V.grass_blade(p, rng, (bx, y1 - 3), hh, lean, col, np.clip(col * np.array([1.2, 1.1, 0.85]), 0, 1),
                            4.2, rng.random() * 3, curl=rng.uniform(-0.05, 0.05), segs=8)
        if rng.random() < 0.55:
            cx, cy = pts[-2]
            for _ in range(rng.integers(4, 9)):
                ang = rng.uniform(1.6, 4.6)
                ln = rng.uniform(14, 34)
                tx, ty = cx + math.sin(ang) * ln * 0.6, cy - math.cos(ang) * ln
                p.capsule((cx, cy), (tx, ty), 1.2, 0.8, V._c("#5a4a2a"), V._c("#5a4a2a"), 4.0, 0.5)
                p.disc((tx, ty), rng.uniform(3.0, 4.8), V._jit(rng, V._c("#6a4a28"), 0.15), 4.5, 0.8, shade=0.4)


def _skunk_leaf(p: V.Painter, rng, box) -> None:
    """Skunk cabbage leaf: a huge glossy paddle on a short thick stalk, a pale fleshy midrib, the
    lateral veins sunk into the blade so it puckers between them, edges a little ragged."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    base = (x0 + w * 0.5, y1 - 3)
    stalk = h * 0.16
    p.capsule(base, (base[0], base[1] - stalk), w * 0.07, w * 0.055, V._c("#8a9a4a"), V._c("#6f8a3a"), 0.0, 0.5)
    col = V._jit(rng, V._c("#33521f"), 0.06, 0.03)
    holes = [(rng.uniform(0.3, 0.9), rng.uniform(-0.7, 0.7), rng.uniform(2, 6)) for _ in range(int(rng.integers(0, 4)))]
    p.blade((base[0], base[1] - stalk * 0.8), (base[0] + rng.uniform(-4, 4), y0 + 4), w * 0.94, col,
            np.clip(col * 0.72, 0, 1), a=0.55, b=0.42, teeth=0, h0=2.0, hscale=0.18, vein=V._c("#b8c070"),
            nveins=11, vein_angle=0.8, curve=rng.uniform(-0.03, 0.03), tip_col=np.clip(col * 1.15, 0, 1), holes=holes)
    # puckered blade: darker bands between the veins (painted as soft strokes along the veins)
    for k in range(9):
        s = 0.15 + 0.08 * k
        yy = base[1] - stalk * 0.8 - (base[1] - stalk * 0.8 - y0 - 4) * s
        for sd in (-1, 1):
            ln = w * 0.36 * math.sin(math.pi * min(1.0, s * 1.05)) ** 0.6
            p.capsule((base[0], yy), (base[0] + sd * ln, yy - ln * 0.45), 3.5, 1.5, V._c("#2a4419"), V._c("#2a4419"),
                      2.5, 0.2, opacity=0.35)


def _skunk_spathe(p: V.Painter, rng, box) -> None:
    """The yellow spathe hooding the spadix, as the plant flowers out of the muck."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    base = (x0 + w * 0.5, y1 - 3)
    p.capsule(base, (base[0], base[1] - h * 0.25), w * 0.09, w * 0.08, V._c("#7a8a3a"), V._c("#9aa040"), 0.0, 0.6)
    p.blade((base[0], base[1] - h * 0.2), (base[0] + w * 0.08, y0 + 6), w * 0.62, V._c("#d8b830"), V._c("#b8901e"),
            a=0.7, b=0.6, h0=2.0, hscale=0.4, curve=0.05, tip_col=V._c("#e0c048"))
    p.capsule((base[0], base[1] - h * 0.3), (base[0], base[1] - h * 0.55), w * 0.08, w * 0.07, V._c("#a08a30"),
              V._c("#8a7428"), 3.0, 0.7)


def _bracken_frond(p: V.Painter, rng, box, cols) -> None:
    """Bracken: a broad triangular frond, twice cut: alternate pinnae longest at the base, each
    with rows of oblong pinnules, on a straw-coloured rachis."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    pts = V._twig_points((x0 + w * 0.5, y1 - 3), 0.0, h * 0.96, 14, rng.uniform(-0.06, 0.06), rng)
    p.polyline(pts, [4.0 - 3.0 * i / 13 for i in range(14)], [V._c("#8a7a48")] * 14, 0.0, 0.5)
    side = 1
    npin = 22
    for k in range(npin):
        s = 0.08 + 0.9 * (k + rng.uniform(0.0, 0.3)) / npin
        i = min(int(s * 13), 12)
        f = s * 13 - i
        x = pts[i][0] + (pts[i + 1][0] - pts[i][0]) * f
        y = pts[i][1] + (pts[i + 1][1] - pts[i][1]) * f
        tang = math.atan2(pts[i + 1][0] - pts[i][0], -(pts[i + 1][1] - pts[i][1]))
        L = w * 0.5 * (1.0 - s) ** 0.85 * rng.uniform(0.92, 1.05) / math.sin(math.radians(62))
        if L < 6:
            side = -side
            continue
        a = tang + side * math.radians(rng.uniform(55, 66))
        col = V._jit(rng, cols[int(rng.integers(0, len(cols)))], 0.08, 0.04)
        tip = (x + math.sin(a) * L, y - math.cos(a) * L)
        p.capsule((x, y), tip, 2.2, 0.8, V._c("#8a7a48"), V._c("#7a7040"), 1.0, 0.4)
        nsub = max(3, int(L / 9))
        for j in range(nsub):
            t = (j + 0.5) / nsub
            px, py = x + (tip[0] - x) * t, y + (tip[1] - y) * t
            ln = L * 0.2 * (1.0 - 0.75 * t) + 3.0
            for sd in (-1, 1):
                aa = a + sd * math.radians(rng.uniform(58, 72))
                c2 = np.clip(col * rng.uniform(0.9, 1.08), 0, 1)
                p.blade((px, py), (px + math.sin(aa) * ln, py - math.cos(aa) * ln), ln * 0.42, c2, np.clip(c2 * 0.78, 0, 1),
                        a=0.35, b=0.6, h0=1.5 + k * 0.05, hscale=0.25)
        side = -side


def _fiddlehead(p: V.Painter, rng, box) -> None:
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    for k in range(3):
        bx = x0 + w * (0.3 + 0.2 * k)
        top = (bx + rng.uniform(-6, 6), y0 + h * rng.uniform(0.15, 0.35))
        p.capsule((bx, y1 - 3), top, 4.0, 3.0, V._c("#7a8040"), V._c("#8a8a48"), 0.0, 0.6)
        for j in range(10):
            ang = j * 0.7
            rad = 10.0 * (1.0 - j / 12)
            p.disc((top[0] + math.cos(ang) * rad * 0.6, top[1] + math.sin(ang) * rad * 0.6), rad * 0.45,
                   V._c("#6e7a3a"), 1.0 + j * 0.2, 0.6, shade=0.3)


@texture("fen_plants", size=2048, seed=6201, kind="pbr_alpha", sources=SRC)
def fen_plants(size: int, seed: int, out) -> None:
    p = V.Painter(size)
    for name, fn in (("cattail", _cattail), ("bulrush", _bulrush)):
        box = V.rect_px(FEN[name], size)
        p.set_clip(box)
        fn(p, T.rng(seed + sum(map(ord, name))), box)
    for k, name in enumerate(("skunk_a", "skunk_b", "skunk_c")):
        box = V.rect_px(FEN[name], size)
        p.set_clip(box)
        _skunk_leaf(p, T.rng(seed + 300 + k * 17), box)
    box = V.rect_px(FEN["skunk_young"], size)
    p.set_clip(box)
    _skunk_spathe(p, T.rng(seed + 400), box)
    box = V.rect_px(FEN["bracken_young"], size)
    p.set_clip(box)
    _fiddlehead(p, T.rng(seed + 450), box)
    for k, (name, cols) in enumerate((("bracken_a", [V._c("#6a7a2e"), V._c("#7a8634"), V._c("#8a8a3a"), V._c("#5e7028")]),
                                      ("bracken_b", [V._c("#8a8434"), V._c("#9a8a3a"), V._c("#a07a34"), V._c("#7a7a30")]))):
        box = V.rect_px(FEN[name], size)
        p.set_clip(box)
        _bracken_frond(p, T.rng(seed + 500 + k * 23), box, cols)
    p.set_clip(None)
    V.finish_foliage(p, out, rough=0.5, rough_var=0.1, normal_strength=2.2, alpha_boost=1.3, seed=seed)


# --------------------------------------------------------------------------------------------
# Sphagnum hummocks (moss mounds of the fen)
# --------------------------------------------------------------------------------------------

def _sphagnum(size: int, seed: int, out, red_share: float) -> None:
    """A carpet of peat moss: packed shoots ending in star-shaped heads (capitula), red where the
    hummock dries in the sun and green where it stays wet, with dead brown shoots between them and
    a few cranberry leaves. Built on the terrain layers' ground compositor, at 1.2 m a tile."""
    from . import terrain as TR
    n = size
    G = TR.Ground(n, 1.2)
    r = TR._rng(seed)
    hum = TR._band(n, 3, 10, seed + 1, 2.0)
    fine = TR._spec(n, 0.8, seed + 2)
    G.h[:] = (0.02 * hum + 0.001 * fine).ravel()
    G.col[:] = (T.gradient(np.clip(0.6 * hum + 0.4 * fine, 0, 1), TR.FIBRE_STOPS) * 0.45).reshape(-1, 3)
    G.rough[:] = 0.75
    G.tag[:] = TR.TAG_MOSS
    age = TR._band(n, 4, 14, seed + 3)
    zone = TR._band(n, 2, 7, seed + 4, 1.6)
    red = TR._ss(0.55 - 0.9 * (red_share - 0.5), 0.75 - 0.9 * (red_share - 0.5), zone)
    dead = [(0.0, "#4a3422"), (0.5, "#5e4430"), (1.0, "#73563a")]
    TR._fronds(G, r, 2600, None, (0.012, 0.03), dead, age=age, nb=6, lift=0.0004, rough=(0.7, 0.85))
    TR._fronds(G, r, 9000, red * 0.95 + 0.05, (0.01, 0.026), TR.SPHAG_RED, age=age, nb=8, lift=0.0006, rough=(0.62, 0.8))
    TR._fronds(G, r, 9000, (1.0 - red) * 0.95 + 0.05, (0.01, 0.026), TR.SPHAG_GREEN, age=age, nb=8, lift=0.0006,
               rough=(0.62, 0.8))
    # capitula: the dense round heads on top of the carpet
    caps_r = [c for c in ("#7a2a22", "#93382a", "#a8503a", "#6a2420")]
    caps_g = [c for c in ("#6f7c30", "#86903c", "#5f6c28", "#9a9a48")]
    TR._blobs(G, r, 2600, (0.006, 0.012), caps_r, kind="lichen", density=red, H_ratio=0.35, rough=(0.6, 0.75),
              tag=TR.TAG_MOSS, zoff=0.0008, irregular=1.2, drape=TR._envelope(G, 5, 1.5))
    TR._blobs(G, r, 2600, (0.006, 0.012), caps_g, kind="lichen", density=1.0 - red, H_ratio=0.35, rough=(0.6, 0.75),
              tag=TR.TAG_MOSS, zoff=0.0008, irregular=1.2, drape=TR._envelope(G, 5, 1.5))
    TR._leaves(G, r, 25, {"bilberry": 3, "herb": 1}, noise=TR._spec(n, 1.6, seed + 5), size=0.6)
    L = TR._finish(G.C().copy(), G.H().copy(), G.R().copy(), G.px, exag=1.3, ao_strength=1.8, ao_bake=0.6,
                   ao_radii=(1.0, 2.5, 6, 16), target=0.07)
    TR._save_layer_set(out, L)


@texture("sphagnum_red", size=1024, seed=6301, sources=["tools/assetgen/textures/gen/terrain.py"])
def sphagnum_red(size: int, seed: int, out) -> None:
    _sphagnum(size, seed, out, 0.75)


@texture("sphagnum_green", size=1024, seed=6311, sources=["tools/assetgen/textures/gen/terrain.py"])
def sphagnum_green(size: int, seed: int, out) -> None:
    _sphagnum(size, seed, out, 0.25)
