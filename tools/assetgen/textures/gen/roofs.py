"""Roof coverings for POI roofs (game/src/poi/roof_builder.gd picks `style.roof.material`, default
roof_shingle; materials in game/data/materials/roofs.json).

All sets tile every 2 m. Pitched-roof UVs run in metres with V increasing UP the slope, and V grows
down the image, so on a roof the image's top edge faces the eave: the pitched sets are drawn with the
eave toward the bottom of the image (like the wall siding) and flipped at the end.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

from .. import texlib as T
from ..registry import texture
from . import kit as K

TILE = 2.0
SRC = ["tools/assetgen/textures/gen/kit.py"]


def _flip(albedo: np.ndarray, height: np.ndarray, rough: np.ndarray, metal=0.0):
    """Eave-down drawing -> roof UV orientation (eave toward the image top)."""
    m = metal[::-1].copy() if isinstance(metal, np.ndarray) else metal
    return albedo[::-1].copy(), height[::-1].copy(), rough[::-1].copy(), m


def _moss_lichen(n: int, seed: int, col: np.ndarray, height: np.ndarray, rough: np.ndarray, where: np.ndarray,
                 amount: float) -> None:
    """Pacific-Northwest roof growth, in place: moss cushions rooted where `where` allows (butts, gaps)
    and spilling a little over the course below, and irregular lichen rosettes (grey-green, a few
    yellow) anywhere."""
    root = np.clip(ndimage.gaussian_filter(where.astype(np.float32), 5.0, mode="wrap") * 2.2, 0, 1)
    clus = K._warp(K._sn(n, 1.8, seed), seed + 1, 18.0)
    cush = T.smoothstep(0.58, 0.68, 0.7 * clus + 0.3 * K._sn(n, 0.7, seed + 2)) * root * amount
    cush = np.clip(cush, 0, 1)
    tips = K._sn(n, 0.3, seed + 3)
    moss = T.gradient(T.normalize(0.6 * tips + 0.4 * clus), [(0.0, "#252b16"), (0.5, "#3e4a20"), (1.0, "#61702e")])
    col[:] = T.mix(col, moss, np.clip(cush * 1.3, 0, 1))
    height += 0.2 * cush * (0.5 + 0.5 * tips)
    rough[:] = np.maximum(rough, cush * 0.97)
    f1, _, cid = T.worley(n, 140, seed + 4)
    wob = 1.0 + 0.45 * (K._sn(n, 0.9, seed + 5) - 0.5)
    rad = 4.0 + 9.0 * K._hash_arr(cid, seed + 6)
    lich = (1.0 - T.smoothstep(rad * 0.6, rad, f1 * wob)) * (K._hash_arr(cid, seed + 7) < 0.6) * amount
    yellow = (K._hash_arr(cid, seed + 8) < 0.2).astype(np.float32)
    lcol = T.gradient(K._sn(n, 0.8, seed + 9), [(0.0, "#6f7562"), (1.0, "#8d927c")])
    lcol = T.mix(lcol, T.hex_rgb("#9a8344")[None, None, :] * np.ones_like(lcol), yellow)
    col[:] = T.mix(col, lcol, np.clip(lich, 0, 1) * 0.45)
    height += 0.025 * lich


# =================================================================================================
# Asphalt shingles (3-tab)
# =================================================================================================

def _shingles(n: int, seed: int, palette: list, *, rows: int = 14, tabs: int = 7, moss: float = 1.0):
    x, y = K._coords(n, TILE)
    e = TILE / rows
    r = np.floor(y / e).astype(np.int32)
    vin = (y - r * e) / e                      # 0 under the row above's butt .. 1 at this row's butt
    tw = TILE / tabs
    off = np.where(r % 2 == 1, tw * 0.5, 0.0) + K._hash_arr(r % rows, seed) * tw * 0.12
    xs = (x + off) % TILE
    t = np.floor(xs / tw).astype(np.int32)
    tid = (r % rows) * tabs + (t % tabs)
    gx = xs - t * tw
    slot = 1.0 - T.smoothstep(0.0028, 0.0042, np.minimum(gx, tw - gx))
    tr = K._hash_arr(tid, seed + 1)
    tr2 = K._hash_arr(tid, seed + 2)
    # Mineral granules: speckled, a few bright grains.
    gran = K._sn(n, 0.12, seed + 3)
    grit = K._sn(n, 0.02, seed + 30)                  # individual granules
    sparkle = T.smoothstep(0.86, 0.95, K._sn(n, 0.05, seed + 4))
    base = T.gradient(T.normalize(0.55 * tr + 0.45 * K._sn(n, 1.8, seed + 5)), palette)
    base *= (0.8 + 0.25 * gran + 0.22 * grit)[..., None]
    base = T.mix(base, T.hex_rgb("#8c877e")[None, None, :] * np.ones_like(base), sparkle * 0.35)
    newer = (tr2 > 0.95).astype(np.float32)          # replaced tabs: darker, crisper
    faded = (tr2 < 0.05).astype(np.float32)          # sun-baked tabs that lost granules
    base = T.mix(base, base * 0.72, newer)
    base = T.mix(base, base * 0.85 + T.hex_rgb("#6e675d")[None, None, :] * 0.25, faded)
    col = base
    # Missing tabs show black felt and nail heads; curled tabs lift at the butt corners.
    missing = (K._hash_arr(tid, seed + 6) < 0.018).astype(np.float32)
    felt = T.gradient(K._sn(n, 0.6, seed + 7), [(0.0, "#141312"), (1.0, "#262422")])
    nails = ((np.abs(vin - 0.62) < 0.05) & ((np.abs(gx - tw * 0.2) < 0.005) | (np.abs(gx - tw * 0.8) < 0.005))).astype(np.float32)
    felt = T.mix(felt, T.hex_rgb("#5a5048")[None, None, :] * np.ones_like(felt), nails)
    col = T.mix(col, felt, missing)
    curl = (K._hash_arr(tid, seed + 8) < 0.07).astype(np.float32)
    corner = np.maximum(1.0 - T.smoothstep(0.0, tw * 0.3, gx), 1.0 - T.smoothstep(0.0, tw * 0.3, tw - gx))
    lift = curl * corner * T.smoothstep(0.55, 1.0, vin)
    # Shade under the butt of the row above; dark slots.
    shade = 1.0 - T.smoothstep(0.0, 0.16, vin)
    col *= (1.0 - 0.32 * shade - 0.25 * lift * 0.5)[..., None]
    col = T.mix(col, T.hex_rgb("#0f0e0d")[None, None, :] * np.ones_like(col), slot * 0.85)
    # Algae streaks (Gloeocapsa) running down the slope.
    streak = T.smoothstep(0.55, 0.85, K._sn(n, 1.5, seed + 9, (16.0, 1.0))) * T.smoothstep(0.35, 0.75, K._sn(n, 2.2, seed + 10))
    col *= (1.0 - 0.38 * streak)[..., None]
    height = 0.3 + 0.55 * vin + 0.06 * gran + 0.25 * lift - 0.45 * slot - 0.3 * missing * (1 - nails)
    rough = np.clip(0.86 + 0.08 * (gran - 0.5) - 0.06 * newer + 0.05 * missing, 0, 1)
    where = np.clip(T.smoothstep(0.7, 1.0, vin) + slot, 0, 1) * (1 - missing)
    _moss_lichen(n, seed + 20, col, height, rough, where, moss)
    return _flip(np.clip(col, 0, 1), np.clip(height, 0, 1), rough)


@texture("roof_shingle", size=1024, seed=7600, sources=SRC)
def roof_shingle(size: int, seed: int, out) -> None:
    """Weathered charcoal 3-tab asphalt shingles: speckled granules, replaced and missing tabs, curled
    corners, algae streaks down the slope, moss along the butts and slots, lichen rosettes."""
    alb, h, r, _ = _shingles(size, seed, [(0.0, "#2c2a28"), (0.5, "#3b3835"), (1.0, "#4d4843")], moss=0.6)
    T.save_pbr_set(out, alb, h, r, normal_strength=5.0, ao_strength=1.4)


@texture("roof_shingle_brown", size=1024, seed=7610, sources=SRC)
def roof_shingle_brown(size: int, seed: int, out) -> None:
    """Older brown-blend shingles, mossier."""
    alb, h, r, _ = _shingles(size, seed, [(0.0, "#3a2c22"), (0.5, "#4f3c2d"), (1.0, "#665040")], moss=1.0)
    T.save_pbr_set(out, alb, h, r, normal_strength=5.0, ao_strength=1.4)


# =================================================================================================
# Corrugated metal
# =================================================================================================

def _corrugated(n: int, seed: int, paint: list | None):
    x, y = K._coords(n, TILE)
    pitch = TILE / 26
    wave = 0.5 + 0.5 * np.cos(2 * np.pi * x / pitch)       # crests at 1
    sheet_w = pitch * 9
    sx = x % sheet_w
    lap = (1.0 - T.smoothstep(0.0, pitch * 0.6, np.minimum(sx, sheet_w - sx))).astype(np.float32)
    end_lap = (1.0 - T.smoothstep(0.0, 0.012, np.minimum(y % TILE, TILE - y % TILE))).astype(np.float32)
    # Screws on every second crest of each purlin row (4 per tile), with a rust ring.
    rows_y = np.array([0.25, 0.75, 1.25, 1.75], np.float32)
    dy = K._wrapdist_x(y, rows_y, TILE)
    crest_i = np.round(x / pitch)
    dx = np.abs(x - crest_i * pitch)
    on = (crest_i % 2 == 0).astype(np.float32)
    rr = np.sqrt(dx * dx + dy * dy)
    screw = (1.0 - T.smoothstep(0.0045, 0.006, rr)) * on
    ring = (1.0 - T.smoothstep(0.006, 0.016, rr)) * on * (1 - screw)
    # Rust bleeding down the slope from the screws (image down = down-slope before the flip).
    src = (screw > 0.5).astype(np.float32) * (0.75 + 0.25 * K._hash_arr(crest_i.astype(np.int64) * 7 + np.round(y / 0.5).astype(np.int64), seed))
    tails = K._run_down(src, 1.0 / 260.0)
    tails = np.maximum(tails, np.roll(tails, 1, 1) * 0.7)
    tails = np.maximum(tails, np.roll(tails, -1, 1) * 0.7)
    tails *= T.smoothstep(0.2, 0.6, K._sn(n, 1.2, seed + 1, (10.0, 1.0)))
    rfield = K._warp(K._sn(n, 2.1, seed + 2), seed + 3, 24.0) + 0.08 * K._sn(n, 0.6, seed + 16)
    rust_big = T.smoothstep(0.66, 0.69, rfield) + 0.3 * T.smoothstep(0.55, 0.69, rfield)   # crisp edge, stained halo
    pits = T.smoothstep(0.62, 0.72, K._sn(n, 0.5, seed + 4))
    rust = np.clip(rust_big + 0.6 * rust_big * pits + 0.8 * tails + 0.7 * ring + 0.35 * lap * T.smoothstep(0.4, 0.7, K._sn(n, 1.4, seed + 5)), 0, 1)
    rcol = T.gradient(T.normalize(K._sn(n, 1.0, seed + 6) + 0.4 * pits), [(0.0, "#3f1f10"), (0.4, "#6b3518"), (0.75, "#8e4a22"), (1.0, "#a8642e")])
    f1, _, cid = T.worley(n, 220, seed + 7)
    spangle = K._hash_arr(cid, seed + 8)
    galv = T.gradient(T.normalize(0.85 * K._sn(n, 2.0, seed + 9) + 0.15 * spangle), [(0.0, "#7c8284"), (0.6, "#959b9c"), (1.0, "#adb2b1")])
    oxide = T.smoothstep(0.6, 0.8, K._sn(n, 1.7, seed + 10)) * (1 - rust)
    galv = T.mix(galv, T.hex_rgb("#c3c6c1")[None, None, :] * np.ones_like(galv), oxide * 0.6)
    metal = np.clip(0.85 - 0.6 * oxide, 0, 1)
    rough = np.clip(0.42 + 0.06 * spangle + 0.25 * oxide, 0, 1)
    col = galv
    if paint is not None:
        pcol = T.gradient(T.normalize(0.7 * K._sn(n, 2.4, seed + 11) + 0.3 * K._sn(n, 0.8, seed + 12)), paint)
        chalk = T.smoothstep(0.5, 0.9, K._sn(n, 2.6, seed + 13))       # sun-chalked, pinkish
        pcol = T.mix(pcol, pcol * 0.8 + T.hex_rgb("#b88a80")[None, None, :] * 0.3, chalk * 0.5)
        flaked = T.smoothstep(0.66, 0.7, K._warp(K._sn(n, 1.6, seed + 14, (1.0, 2.5)), seed + 15, 10.0))
        painted = 1.0 - flaked
        col = T.mix(galv, pcol, painted)
        metal = metal * (1 - painted)
        rough = T.lerp(rough, 0.72 + 0.1 * chalk, painted)
    col = T.mix(col, rcol, rust)
    metal = metal * (1 - rust)
    rough = T.lerp(rough, 0.88, rust)
    col = T.mix(col, T.hex_rgb("#5c5f5f")[None, None, :] * np.ones_like(col), screw * 0.9)
    col *= (0.8 + 0.2 * wave)[..., None]                    # grime settles in the troughs
    col *= (1.0 - 0.3 * end_lap)[..., None]
    height = 0.2 + 0.6 * wave + 0.1 * lap + 0.12 * screw - 0.05 * pits * rust - 0.15 * end_lap
    return _flip(np.clip(col, 0, 1), np.clip(height, 0, 1), np.clip(rough, 0, 1), np.clip(metal, 0, 1))


@texture("roof_metal", size=1024, seed=7620, sources=SRC)
def roof_metal(size: int, seed: int, out) -> None:
    """Galvanised corrugated sheets: spangle, white oxide, rust patches and streaks bleeding down from
    the screws, darker lap seams."""
    alb, h, r, m = _corrugated(size, seed, None)
    T.save_pbr_set(out, alb, h, r, metal=m, normal_strength=7.0, ao_strength=1.2)


@texture("roof_metal_red", size=1024, seed=7630, sources=SRC)
def roof_metal_red(size: int, seed: int, out) -> None:
    """Barn-red painted corrugated metal, chalky and flaking to galvanised steel and rust."""
    alb, h, r, m = _corrugated(size, seed, [(0.0, "#5e221b"), (0.6, "#76302a"), (1.0, "#8c3d30")])
    T.save_pbr_set(out, alb, h, r, metal=m, normal_strength=7.0, ao_strength=1.2)


# =================================================================================================
# Cedar shakes
# =================================================================================================

@texture("roof_cedar", size=1024, seed=7640, sources=SRC)
def roof_cedar(size: int, seed: int, out) -> None:
    """Hand-split cedar shakes weathered silver: random widths, split grain down the slope, dark gaps,
    thick butts with shadow, moss in the keyways and along the butts."""
    n = size
    b = K._boards(n, TILE, 0.25, seed + 1, min_len=0.09, max_len=0.3, gap=0.006)
    vin = b["vin"]
    pr = K._piece_rand(b["piece"], seed)
    gap = 1.0 - T.smoothstep(0.0025, 0.0045, b["joint"])
    split = K._sn(n, 0.9, seed + 2, (22.0, 1.0))             # split grain along the shake
    ridges = K._sn(n, 1.4, seed + 3, (9.0, 1.0))
    tone = T.normalize(0.45 * pr + 0.35 * split + 0.2 * K._sn(n, 2.0, seed + 4))
    col = T.gradient(tone, [(0.0, "#5d5850"), (0.45, "#77726a"), (0.8, "#8f8a80"), (1.0, "#a39d91")])
    fresh = (K._hash_arr(b["piece"], seed + 5) > 0.93).astype(np.float32)   # newer shakes still brown
    col = T.mix(col, T.gradient(split, [(0.0, "#6b4a33"), (1.0, "#8e6646")]), fresh * 0.8)
    wet = T.smoothstep(0.75, 1.0, vin)
    col *= (1.0 - 0.18 * wet)[..., None]
    shade = 1.0 - T.smoothstep(0.0, 0.14, vin)
    col *= (1.0 - 0.35 * shade)[..., None]
    col = T.mix(col, T.hex_rgb("#141210")[None, None, :] * np.ones_like(col), gap * 0.9)
    height = 0.25 + 0.6 * vin + 0.08 * ridges + 0.05 * split - 0.5 * gap
    rough = np.clip(0.88 + 0.06 * split, 0, 1)
    where = np.clip(T.smoothstep(0.65, 1.0, vin) + gap, 0, 1)
    _moss_lichen(n, seed + 20, col, height, rough, where, 1.0)
    alb, h, r, _ = _flip(np.clip(col, 0, 1), np.clip(height, 0, 1), rough)
    T.save_pbr_set(out, alb, h, r, normal_strength=6.0, ao_strength=1.6)


# =================================================================================================
# Tar and gravel (flat roofs)
# =================================================================================================

@texture("roof_tar", size=1024, seed=7650, sources=SRC)
def roof_tar(size: int, seed: int, out) -> None:
    """Built-up flat roof: pea gravel bedded in tar, washed bare in patches (alligator-cracked tar
    beneath), ponding rings of dried silt, membrane laps every metre."""
    n = size
    x, y = K._coords(n, TILE)
    f1, f2, cid = T.worley(n, 30000, seed + 1)           # ~1 cm pea gravel
    stone = 1.0 - T.smoothstep(0.55, 0.95, f1 / np.maximum(f2, 1e-3))
    sr = K._hash_arr(cid, seed + 2)
    scol = T.gradient(sr, [(0.0, "#5f5a52"), (0.4, "#857e72"), (0.75, "#a39b8c"), (1.0, "#bdb4a3")])
    bare = T.smoothstep(0.6, 0.72, K._warp(K._sn(n, 2.2, seed + 3), seed + 4, 30.0))
    keep = (1.0 - bare) * (K._hash_arr(cid, seed + 5) < 0.85)
    tar = T.gradient(K._sn(n, 1.2, seed + 6), [(0.0, "#141312"), (1.0, "#2a2826")])
    cr = K._cracks(n, seed + 7, 40, 1.4, 0.8) * bare
    tar *= (1.0 - 0.5 * cr)[..., None]
    col = T.mix(tar, scol, stone * keep)
    pond = K._sn(n, 2.4, seed + 8)
    rings = (0.5 + 0.5 * np.cos(pond * 2 * np.pi * 9.0)) ** 10 * T.smoothstep(0.55, 0.7, pond)
    silt = T.smoothstep(0.62, 0.72, pond)
    col = T.mix(col, col * 0.7 + T.hex_rgb("#7d766a")[None, None, :] * 0.3, np.clip(silt * 0.5 + rings * 0.5, 0, 1))
    seam = 1.0 - T.smoothstep(0.0, 0.01, K._wrapdist_x(y, np.array([0.0, 1.0], np.float32), TILE))
    col *= (1.0 - 0.25 * seam)[..., None]
    height = 0.3 + 0.5 * stone * keep + 0.08 * seam - 0.2 * cr
    rough = np.clip(0.82 + 0.1 * stone * keep - 0.15 * silt * (1 - stone), 0, 1)
    T.save_pbr_set(out, np.clip(col, 0, 1), np.clip(height, 0, 1), rough, normal_strength=4.0, ao_strength=1.6)
