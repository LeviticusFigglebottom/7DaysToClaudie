"""Farm props family (the Okafor farm: barn, farmhouse, yard and root cellar).

Tileable PBR sets (albedo / normal / ORM):
  * farm_hay         — baled straw: packed golden stalks along U, chaff, grey sun-bleached ends.
  * farm_corrugated  — galvanised corrugated steel, ridges along V (image rows: horizontal rings
                       on a grain bin with cylinder UVs), spangle, white-rust bloom, rust runs.
  * farm_quilt       — hand-pieced patchwork: 8 x 8 faded calico / gingham / stripe / floral
                       squares per tile, seams, diagonal quilting stitches, wear on the fold.
  * farm_leather     — oiled saddle leather: pebbled grain, creases, scuffs, darker oil stains.
  * farm_produce     — mottled skin for root-cellar produce (potatoes, apples, onions; tinted).
  * farm_preserve    — packed fruit / vegetable chunks in syrup behind jar glass (tinted).
  * farm_feed_sack   — multiwall kraft feed-sack paper with a faded printed band and blocks of
                       illegible type (no text, no logos).
Neutral or light base colours are tinted per material in game/data/materials/props_farm.json.
"""
from __future__ import annotations

import numpy as np

from .. import texlib as T
from ..registry import texture


def _c(h: str) -> np.ndarray:
    return T.hex_rgb(h)[None, None, :]


def _uv(size: int) -> tuple[np.ndarray, np.ndarray]:
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    return (xx + 0.5) / size, (yy + 0.5) / size


def _hash01(ids: np.ndarray, k: int = 0) -> np.ndarray:
    """Deterministic pseudo-random value in [0, 1) per integer id (vectorised integer hash)."""
    x = (ids.astype(np.int64) * 374761393 + (k + 1) * 668265263) & 0xFFFFFFFF
    x = ((x ^ (x >> 13)) * 1274126177) & 0xFFFFFFFF
    x = x ^ (x >> 16)
    return (x & 0xFFFFFF).astype(np.float32) / float(0x1000000)


def _segments(size: int, segs, soft: float = 0.8) -> np.ndarray:
    """Anti-aliased capsule strokes, wrapping. segs: iterable of (x0, y0, x1, y1, half_width[, value])."""
    m = np.zeros((size, size), np.float32)
    for s in segs:
        x0, y0, x1, y1, w = s[:5]
        val = s[5] if len(s) > 5 else 1.0
        xs = np.arange(int(np.floor(min(x0, x1) - w - 2)), int(np.ceil(max(x0, x1) + w + 2)) + 1)
        ys = np.arange(int(np.floor(min(y0, y1) - w - 2)), int(np.ceil(max(y0, y1) + w + 2)) + 1)
        X, Y = np.meshgrid(xs + 0.5, ys + 0.5)
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy + 1e-9
        t = np.clip(((X - x0) * dx + (Y - y0) * dy) / L2, 0.0, 1.0)
        d = np.hypot(X - (x0 + t * dx), Y - (y0 + t * dy))
        a = np.clip((w - d) / soft + 0.5, 0.0, 1.0) * val
        iy, ix = np.mod(ys, size), np.mod(xs, size)
        sub = m[np.ix_(iy, ix)]
        m[np.ix_(iy, ix)] = np.maximum(sub, a)
    return m


def _save(out, albedo, height, rough, *, metal=0.0, normal_strength=4.0, ao_strength=1.0):
    T.save_pbr_set(out, np.clip(albedo, 0, 1), np.clip(height, 0, 1), np.clip(rough, 0, 1), metal=metal,
                   normal_strength=normal_strength, ao_strength=ao_strength)


# --------------------------------------------------------------------------------------------
# Hay / straw
# --------------------------------------------------------------------------------------------

@texture("farm_hay", size=1024, seed=1101)
def farm_hay(size: int, seed: int, out) -> None:
    """Compressed stalks running along U (image x): thousands of short tapered strokes in three
    layers, hollow-stalk highlights, dark gaps between them, chaff flecks and grey bleaching."""
    r = T.rng(seed)
    layers = []
    for k, (n, w, L) in enumerate(((2600, (0.9, 1.8), (40, 140)), (1800, (1.2, 2.6), (60, 200)), (900, (1.6, 3.2), (90, 260)))):
        segs = []
        for x, y, ln, wd, ang, val in zip(r.uniform(0, size, n), r.uniform(0, size, n), r.uniform(*L, n), r.uniform(*w, n),
                                           r.normal(0.0, 0.16, n), r.uniform(0.55, 1.0, n)):
            segs.append((x, y, x + np.cos(ang) * ln, y + np.sin(ang) * ln, wd, val))
        layers.append(_segments(size, segs, soft=0.9))
    stalk = np.maximum(np.maximum(layers[0] * 0.8, layers[1] * 0.9), layers[2])
    top = layers[2]
    gaps = 1.0 - T.smoothstep(0.05, 0.5, stalk)
    tone = T.spectral(size, 2.0, seed + 1)
    bleach = T.smoothstep(0.55, 0.85, T.spectral(size, 2.2, seed + 2, anisotropy=(3.0, 1.0)))
    chaff = (T.rng(seed + 3).random((size, size)) > 0.985).astype(np.float32)
    chaff = T.blur(chaff, 0.7)
    alb = T.gradient(T.normalize(stalk * 0.7 + tone * 0.3), [(0.0, "#6d5428"), (0.4, "#a4823f"), (0.75, "#cfae63"), (1.0, "#e6cf8c")])
    alb = T.mix(alb, _c("#9a9480") * np.ones_like(alb), bleach * 0.45)
    alb = T.mix(alb, _c("#2d2416") * np.ones_like(alb), gaps * 0.75)
    alb = T.mix(alb, _c("#efe2b0") * np.ones_like(alb), np.clip(top * 0.25, 0, 1))
    alb = T.mix(alb, _c("#3b2f1a") * np.ones_like(alb), np.clip(chaff * 2.0, 0, 1) * 0.6)
    height = 0.25 + 0.35 * layers[0] + 0.45 * layers[1] + 0.6 * layers[2] - 0.3 * gaps
    rough = 0.82 + 0.1 * gaps - 0.08 * top
    _save(out, alb, T.normalize(height), rough, normal_strength=7.0, ao_strength=1.6)


# --------------------------------------------------------------------------------------------
# Corrugated galvanised steel
# --------------------------------------------------------------------------------------------

@texture("farm_corrugated", size=1024, seed=1111)
def farm_corrugated(size: int, seed: int, out) -> None:
    """15 corrugation waves per tile along V (≈ 6.7 cm pitch at 1 m tiles), galvanised spangle,
    white-rust bloom in the troughs, orange rust runs streaking down from fastener rows."""
    u, v = _uv(size)
    waves = 15.0
    prof = 0.5 + 0.5 * np.sin(v * np.pi * 2.0 * waves)
    f1, f2, cid = T.worley(size, 900, seed)
    spangle = _hash01(cid, 1)
    fine = T.spectral(size, 0.8, seed + 1)
    trough = 1.0 - prof
    white = T.smoothstep(0.62, 0.85, T.spectral(size, 1.7, seed + 2, anisotropy=(4.0, 1.0))) * trough
    # Rust runs: vertical streaks starting at rows of rivets (every 1/3 tile), fading downward.
    runs_src = T.smoothstep(0.7, 0.95, T.spectral(size, 1.2, seed + 3, anisotropy=(1.0, 60.0)))
    phase = (v * 3.0) % 1.0
    runs = runs_src * (1.0 - T.smoothstep(0.0, 0.9, phase)) * T.smoothstep(0.55, 0.8, T.spectral(size, 2.0, seed + 4))
    blotch = T.smoothstep(0.74, 0.95, T.spectral(size, 2.1, seed + 5)) * (0.6 + 0.4 * trough)
    rust = np.clip(runs * 1.2 + blotch * 0.45, 0, 1)
    alb = _c("#a3a6a4") * np.ones((size, size, 3), np.float32) * (0.86 + 0.14 * spangle[..., None])
    alb = alb * (0.82 + 0.25 * prof[..., None])
    alb = T.mix(alb, _c("#d4d1c8") * np.ones_like(alb), white * 0.5)
    alb = T.mix(alb, _c("#7b4022") * np.ones_like(alb), rust * 0.8)
    alb = T.mix(alb, _c("#4d2a17") * np.ones_like(alb), np.clip(rust - 0.6, 0, 1) * 0.9)
    rough = 0.35 + 0.15 * spangle + 0.4 * white + 0.45 * rust + 0.05 * fine
    metal = np.clip(0.88 - 0.6 * white - 0.85 * rust, 0, 1)
    height = 0.15 + 0.7 * prof + 0.04 * fine - 0.05 * rust
    _save(out, alb, height, rough, metal=metal, normal_strength=5.0, ao_strength=0.8)


# --------------------------------------------------------------------------------------------
# Patchwork quilt
# --------------------------------------------------------------------------------------------

_QUILT_COLORS = ["#8e3b33", "#3f5f7a", "#c9a64b", "#5e7d4f", "#d8cbb0", "#7a4f6d", "#b5664a", "#46617f",
                 "#a38d63", "#6f7f5a", "#c47d6a", "#efe6d2"]


@texture("farm_quilt", size=1024, seed=1121)
def farm_quilt(size: int, seed: int, out) -> None:
    """8 x 8 squares per tile; each square gets a colour and a print (calico dots, gingham,
    stripes, small florals or plain). Sashing seams, diagonal hand quilting, fading and grime."""
    r = T.rng(seed)
    u, v = _uv(size)
    n = 8
    cx = np.floor(u * n).astype(np.int64)
    cy = np.floor(v * n).astype(np.int64)
    cid = cx + cy * n
    fu = u * n - cx
    fv = v * n - cy
    h0 = _hash01(cid, 1)
    h1 = _hash01(cid, 2)
    h2 = _hash01(cid, 3)
    cols = np.stack([T.hex_rgb(c) for c in _QUILT_COLORS])
    base = cols[(h0 * len(_QUILT_COLORS)).astype(int) % len(_QUILT_COLORS)]
    second = cols[(h1 * len(_QUILT_COLORS)).astype(int) % len(_QUILT_COLORS)]
    kind = (h2 * 5).astype(int)
    px = u * size
    py = v * size
    pat = np.zeros((size, size), np.float32)
    # 0: calico dots
    dots = ((np.sin(px * 0.9 + h1 * 9) * np.sin(py * 0.9 + h0 * 7)) > 0.82).astype(np.float32)
    # 1: gingham
    ging = ((np.sin(px * 0.38) > 0).astype(np.float32) + (np.sin(py * 0.38) > 0).astype(np.float32)) * 0.5
    # 2: stripes
    stripes = (np.sin((px + py * (h1 > 0.5)) * 0.55) > 0.3).astype(np.float32)
    # 3: small florals (worley blossoms)
    f1, _, _ = T.worley(size, 1400, seed + 5)
    flor = T.smoothstep(4.5, 2.0, f1)
    pat = np.where(kind == 0, dots, pat)
    pat = np.where(kind == 1, ging, pat)
    pat = np.where(kind == 2, stripes, pat)
    pat = np.where(kind == 3, flor, pat)
    alb = base * (1.0 - pat[..., None] * 0.55) + second * (pat[..., None] * 0.55)
    # Seams between squares and the quilting lines across them.
    edge = np.minimum(np.minimum(fu, 1 - fu), np.minimum(fv, 1 - fv))
    seam = 1.0 - T.smoothstep(0.012, 0.03, edge)
    diag = np.abs(((fu + fv) * 3.0) % 1.0 - 0.5)
    stitch_on = (np.sin((fu - fv) * 120.0) > 0.0).astype(np.float32)
    quilting = (1.0 - T.smoothstep(0.004, 0.012, diag / 3.0)) * stitch_on
    puff = T.smoothstep(0.0, 0.18, np.minimum(edge, diag / 3.0 + 0.05))
    fade = T.spectral(size, 2.0, seed + 6)
    wear = T.smoothstep(0.6, 0.9, T.spectral(size, 1.8, seed + 7))
    weave = T.spectral(size, 0.6, seed + 8, fmin=180.0)
    alb = T.mix(alb, _c("#efe8d8") * np.ones_like(alb), (0.18 + 0.2 * fade) * 0.6)
    alb = T.mix(alb, _c("#3a3128") * np.ones_like(alb), seam * 0.55)
    alb = T.mix(alb, _c("#e9e0cc") * np.ones_like(alb), quilting * 0.5)
    alb = T.mix(alb, _c("#6b5f4f") * np.ones_like(alb), wear * 0.25)
    alb = alb * (0.94 + 0.08 * weave[..., None])
    height = 0.3 + 0.55 * puff - 0.25 * seam - 0.2 * quilting + 0.05 * weave
    rough = 0.9 - 0.04 * weave
    _save(out, alb, T.normalize(height), rough, normal_strength=4.0, ao_strength=1.2)


# --------------------------------------------------------------------------------------------
# Leather
# --------------------------------------------------------------------------------------------

@texture("farm_leather", size=512, seed=1131)
def farm_leather(size: int, seed: int, out) -> None:
    """Pebbled hide grain, fold creases, pale scuffs and dark oiled patches (tinted per material)."""
    r = T.rng(seed)
    f1, f2, cid = T.worley(size, 6000, seed)
    pebble = T.blur(T.smoothstep(0.0, 3.0, f2 - f1), 0.6)
    cell = _hash01(cid, 1)
    creases = T.blur(_segments(size, [(x, y, x + np.cos(a) * L, y + np.sin(a) * L, w) for x, y, a, L, w in
                                      zip(r.uniform(0, size, 26), r.uniform(0, size, 26), r.uniform(0, np.pi, 26),
                                          r.uniform(20, 70, 26), r.uniform(0.4, 0.9, 26))], soft=1.4), 0.8)
    scuff = T.smoothstep(0.62, 0.9, T.spectral(size, 1.6, seed + 2)) * T.smoothstep(0.4, 0.8, T.spectral(size, 0.9, seed + 3))
    oil = T.smoothstep(0.55, 0.85, T.spectral(size, 2.3, seed + 4))
    tone = T.spectral(size, 2.0, seed + 5)
    alb = T.gradient(tone, [(0.0, "#8a7a6a"), (0.5, "#a89582"), (1.0, "#bba893")])
    alb = alb * (0.96 + 0.04 * cell[..., None]) * (0.94 + 0.06 * pebble[..., None])
    alb = T.mix(alb, _c("#5a4c40") * np.ones_like(alb), oil * 0.45)
    alb = T.mix(alb, _c("#d9ccb9") * np.ones_like(alb), scuff * 0.45)
    alb = T.mix(alb, _c("#4a3e34") * np.ones_like(alb), creases * 0.3)
    height = 0.5 + 0.12 * pebble - 0.3 * creases + 0.08 * tone
    rough = 0.55 + 0.15 * (1 - pebble) - 0.18 * oil + 0.2 * scuff
    _save(out, alb, height, rough, normal_strength=3.5, ao_strength=0.8)


# --------------------------------------------------------------------------------------------
# Produce and preserves
# --------------------------------------------------------------------------------------------

@texture("farm_produce", size=512, seed=1141)
def farm_produce(size: int, seed: int, out) -> None:
    """Mottled skin with eyes/lenticels, dried soil smears and bruises (light, tinted per crop)."""
    f1, _, cid = T.worley(size, 260, seed)
    eyes = T.smoothstep(3.5, 1.0, f1) * (_hash01(cid, 1) > 0.55)
    mott = T.spectral(size, 1.9, seed + 1)
    soil = T.smoothstep(0.6, 0.85, T.spectral(size, 2.0, seed + 2))
    bruise = T.smoothstep(0.7, 0.92, T.spectral(size, 2.4, seed + 3))
    fine = T.spectral(size, 0.8, seed + 4)
    alb = T.gradient(mott, [(0.0, "#bdb4a3"), (0.5, "#d8d0bf"), (1.0, "#ece6d8")])
    alb = T.mix(alb, _c("#5d4a35") * np.ones_like(alb), soil * 0.55)
    alb = T.mix(alb, _c("#6e5a4a") * np.ones_like(alb), bruise * 0.4)
    alb = T.mix(alb, _c("#4e3f30") * np.ones_like(alb), eyes * 0.6)
    alb = alb * (0.95 + 0.06 * fine[..., None])
    height = 0.55 + 0.1 * mott - 0.45 * eyes + 0.06 * fine + 0.08 * soil
    rough = 0.6 + 0.25 * soil + 0.05 * fine
    _save(out, alb, height, rough, normal_strength=3.0, ao_strength=0.8)


@texture("farm_preserve", size=512, seed=1151)
def farm_preserve(size: int, seed: int, out) -> None:
    """Packed halves and slices pressed against the glass, syrup between them, a few seeds."""
    # Fewer, bigger pieces with thin dark syrup seams: wide bright grooves read as grouted tile.
    f1, f2, cid = T.worley(size, 40, seed, jitter=0.8)
    chunk = T.smoothstep(0.0, 6.0, f2 - f1)
    tone = _hash01(cid, 1)
    seeds = T.smoothstep(2.2, 0.8, T.worley(size, 500, seed + 1)[0]) * (T.spectral(size, 2.0, seed + 2) > 0.6)
    alb = T.gradient(T.normalize(chunk * 0.75 + tone * 0.25), [(0.0, "#3e3a34"), (0.35, "#a39c8d"), (1.0, "#ebe6da")])
    alb = T.mix(alb, _c("#3b342b") * np.ones_like(alb), seeds * 0.6)
    height = 0.3 + 0.6 * chunk
    rough = 0.38 + 0.12 * chunk
    _save(out, alb, height, rough, normal_strength=1.6, ao_strength=1.0)


# --------------------------------------------------------------------------------------------
# Feed sack paper
# --------------------------------------------------------------------------------------------

@texture("farm_feed_sack", size=1024, seed=1161)
def farm_feed_sack(size: int, seed: int, out) -> None:
    """Kraft multiwall paper: fibre, crinkles, a faded green printed band across the middle with
    blocks of illegible type and a pale diamond badge (no letters), damp stains, grime."""
    r = T.rng(seed)
    u, v = _uv(size)
    fibre = T.spectral(size, 0.7, seed, anisotropy=(6.0, 1.0))
    crinkle = T.spectral(size, 1.4, seed + 1)
    band = T.smoothstep(0.33, 0.36, v) * (1.0 - T.smoothstep(0.62, 0.65, v))
    stripe = T.smoothstep(0.27, 0.29, v) * (1.0 - T.smoothstep(0.31, 0.33, v))
    stripe += T.smoothstep(0.67, 0.69, v) * (1.0 - T.smoothstep(0.71, 0.73, v))
    # "Type": short dark bars in rows inside the band, illegible at any distance.
    rows = []
    for row_v in (0.42, 0.47, 0.55):
        x = r.uniform(0.08, 0.12) * size
        while x < size * 0.92:
            w = r.uniform(6, 28)
            rows.append((x, row_v * size, x + w, row_v * size, r.uniform(2.0, 3.2)))
            x += w + r.uniform(5, 14)
    typ = _segments(size, rows, soft=0.8)
    du, dv = np.abs(u - 0.5) * 2.0, np.abs(v - 0.49) * 2.0
    badge = 1.0 - T.smoothstep(0.17, 0.18, du * 0.55 + dv * 0.9)
    stain = T.smoothstep(0.6, 0.85, T.spectral(size, 2.1, seed + 2))
    alb = T.gradient(T.normalize(fibre * 0.6 + crinkle * 0.4), [(0.0, "#9c7b52"), (0.6, "#b8966a"), (1.0, "#c9a97c")])
    alb = T.mix(alb, _c("#4f6b4a") * np.ones_like(alb), np.clip(band + stripe, 0, 1) * 0.7)
    alb = T.mix(alb, _c("#d9d0b5") * np.ones_like(alb), badge * band * 0.65)
    alb = T.mix(alb, _c("#ece3c6") * np.ones_like(alb), typ * band * (1 - badge) * 0.7)
    alb = T.mix(alb, _c("#5d4630") * np.ones_like(alb), stain * 0.35)
    height = 0.5 + 0.25 * crinkle + 0.08 * fibre
    rough = 0.86 + 0.06 * fibre - 0.1 * stain
    _save(out, alb, height, rough, normal_strength=3.5, ao_strength=0.9)
