"""Wilderness / industrial props family (Larch Hollow logging valley: the Tamsin logging camp, the
Larch Hollow sawmill, the Cedar Ridge fire lookout, the trapper's cabin).

Tileable PBR sets (albedo / normal / ORM), all prefixed ``wild_``:
  wild_lumber_sawn   rough-sawn fir: grain along U, band-saw kerf marks across it, torn fibres,
                     knots, pitch streaks (1 tile = 1 m). Pale; tinted fresh / weathered per material.
  wild_sawdust       sawdust and chips with bark crumbs and a few curled shavings (1 tile = 1 m).
  wild_cast_iron     sand-cast iron: pebbled skin, graphite sheen, rust bloom, ash and soot.
  wild_saw_steel     ground saw-plate steel: grind lines along U, heat tint, rust freckles.
  wild_fur           pelt fur: hair runs along V (image rows), clumped guard hairs over underfur.
                     Mid brown, tinted per species.
  wild_wool_blanket  felted camp wool with a band of three stripes per tile (tile = 1 m), light
                     neutral base tinted per material.
  wild_enamel        speckled granite-ware enamel with chips down to black steel and rust rings.
  wild_tarpaper      mineral-surfaced roll roofing with a lap seam and nail line per tile.
and two non-tiling sheets mapped by planar UVs (rects documented in blender/lib/props_wild_parts.py):
  wild_firefinder_map  the fire-finder's map disc: contour map, lakes, creeks, section grid, a
                       printed degree ring and pencilled bearing lines. Disc centred, radius 0.47.
  wild_radio_panel     front panel of a base-station transceiver (dial window, meter, grille,
                       switch plate, knob bezels) in the band v 0.3..0.7 (u 0..1); hammertone above
                       and below. No text anywhere: tick marks and blank plates only.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from .. import texlib as T
from ..registry import texture


# --------------------------------------------------------------------------------------------
# Local helpers (kept here so this family's textures only rebuild when this file changes)
# --------------------------------------------------------------------------------------------

def _c(h: str) -> np.ndarray:
    return T.hex_rgb(h)[None, None, :]


def _full(size: int, h: str) -> np.ndarray:
    return _c(h) * np.ones((size, size, 3), np.float32)


def _uv(size: int) -> tuple[np.ndarray, np.ndarray]:
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    return (xx + 0.5) / size, (yy + 0.5) / size


def _hash01(ids: np.ndarray, k: int = 0) -> np.ndarray:
    """Deterministic pseudo-random value in [0, 1) per integer id (vectorised integer hash)."""
    x = (ids.astype(np.int64) * 374761393 + (k + 1) * 668265263) & 0xFFFFFFFF
    x = ((x ^ (x >> 13)) * 1274126177) & 0xFFFFFFFF
    x = x ^ (x >> 16)
    return (x & 0xFFFFFF).astype(np.float32) / float(0x1000000)


def _segments(size: int, segs, soft: float = 0.8, wrap: bool = True) -> np.ndarray:
    """Anti-aliased capsule strokes. segs: iterable of (x0, y0, x1, y1, half_width[, value])."""
    m = np.zeros((size, size), np.float32)
    for s in segs:
        x0, y0, x1, y1, w = s[:5]
        val = s[5] if len(s) > 5 else 1.0
        xs = np.arange(int(np.floor(min(x0, x1) - w - 2)), int(np.ceil(max(x0, x1) + w + 2)) + 1)
        ys = np.arange(int(np.floor(min(y0, y1) - w - 2)), int(np.ceil(max(y0, y1) + w + 2)) + 1)
        if not wrap:
            xs = xs[(xs >= 0) & (xs < size)]
            ys = ys[(ys >= 0) & (ys < size)]
            if xs.size == 0 or ys.size == 0:
                continue
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


def _dots(f1: np.ndarray, cid: np.ndarray, rmin: float, rmax: float, keep: float, k: int) -> np.ndarray:
    """Soft round spots from a Worley field: radius per cell in [rmin, rmax], `keep` = fraction kept."""
    rad = rmin + (rmax - rmin) * _hash01(cid, k)
    return T.smoothstep(rad + 0.7, rad - 0.7, f1) * (_hash01(cid, k + 1) < keep)


def _save(out, albedo, height, rough, *, metal=0.0, normal_strength=4.0, ao_strength=1.0, alpha=None):
    T.save_pbr_set(out, np.clip(albedo, 0, 1), np.clip(height, 0, 1), np.clip(rough, 0, 1), metal=metal,
                   normal_strength=normal_strength, ao_strength=ao_strength, alpha=alpha)


def _draw(w: int, h: int, fn, ss: int = 4) -> np.ndarray:
    """Non-tiling anti-aliased mask: fn(ImageDraw, scale) draws with fill=255 at ss x size."""
    img = Image.new("L", (w * ss, h * ss), 0)
    fn(ImageDraw.Draw(img), ss)
    img = img.resize((w, h), Image.BOX)
    return np.asarray(img, np.float32) / 255.0


# --------------------------------------------------------------------------------------------
# Wood: rough-sawn lumber, sawdust
# --------------------------------------------------------------------------------------------

@texture("wild_lumber_sawn", size=1024, seed=9101)
def wild_lumber_sawn(size: int, seed: int, out) -> None:
    """Rough-sawn Douglas fir straight off the headrig. Grain runs along U (image x): wavy
    latewood bands, torn fibre fuzz, band-saw kerf marks crossing the grain at a slight angle,
    sparse tight knots with pitch halos and the odd resin streak. Pale fresh colour (tinted)."""
    r = T.rng(seed)
    u, v = _uv(size)
    wander = T.spectral(size, 2.6, seed, anisotropy=(1.0, 5.0))
    fibre = T.spectral(size, 0.8, seed + 1, anisotropy=(1.0, 36.0))
    low = T.spectral(size, 2.3, seed + 2)
    f1, _, cid = T.worley(size, 5, seed + 3)
    kr = 6 + 9 * _hash01(cid, 1)
    has_knot = (_hash01(cid, 2) > 0.45).astype(np.float32)
    knot = np.exp(-(f1 / kr) ** 2) * has_knot
    halo = np.exp(-(f1 / (kr * 3.2)) ** 2) * has_knot
    g = v * 38.0 + 4.0 * (wander - 0.5) + 0.5 * (fibre - 0.5) + 2.6 * halo
    p = g - np.floor(g)
    late = T.smoothstep(0.0, 0.06, p) * (1.0 - T.smoothstep(0.16, 0.36, p))
    # Band-saw marks: fine ridges across the board every ~6 mm, slightly skewed and wavering.
    skew = 0.08
    kerf_w = T.spectral(size, 2.0, seed + 4, anisotropy=(6.0, 1.0))
    kerf_p = (u + skew * v) * 168.0 + 1.8 * (kerf_w - 0.5)
    kerf = 0.5 + 0.5 * np.cos(2 * np.pi * kerf_p)
    kerf = kerf ** 3 * (0.55 + 0.45 * T.spectral(size, 1.4, seed + 5, anisotropy=(4.0, 1.0)))
    # Torn-grain patches (the saw ripped fibres out) and pitch streaks along the grain.
    torn = T.smoothstep(0.72, 0.9, T.spectral(size, 1.6, seed + 6, anisotropy=(1.0, 6.0)))
    pitch = T.smoothstep(0.82, 0.95, T.spectral(size, 2.2, seed + 7, anisotropy=(1.0, 10.0)))
    t = T.normalize(0.55 * low + 0.45 * fibre)
    alb = T.gradient(t, [(0.0, "#b98e5e"), (0.45, "#cfa673"), (0.8, "#dcb784"), (1.0, "#e6c592")])
    alb = T.mix(alb, _full(size, "#9b6a3c"), late[..., None] * 0.5)
    alb = alb * (0.93 + 0.12 * (fibre[..., None] - 0.5))
    alb = T.mix(alb, _full(size, "#8a5a2c"), (halo * 0.25)[..., None])
    alb = T.mix(alb, _full(size, "#4a2c16"), np.clip(knot * 1.1, 0, 1)[..., None])
    alb = T.mix(alb, _full(size, "#a77437"), (pitch * 0.45)[..., None])
    alb = alb * (1.0 - 0.06 * kerf[..., None]) * (1.0 - 0.08 * torn[..., None])
    checks = _segments(size, [(x, y, x + L, y + r.normal(0, 1.0), w)
                              for x, y, L, w in zip(r.uniform(0, size, 26), r.uniform(0, size, 26),
                                                    r.uniform(30, 140, 26), r.uniform(0.4, 0.9, 26))], soft=0.7)
    alb = T.mix(alb, _full(size, "#3a2412"), (checks * 0.55)[..., None])
    height = 0.5 + 0.16 * late + 0.14 * fibre + 0.18 * kerf + 0.12 * torn * (fibre - 0.5) + 0.08 * knot - 0.5 * checks
    rough = 0.86 + 0.06 * torn - 0.18 * pitch + 0.03 * kerf
    _save(out, alb, height, rough, normal_strength=5.0, ao_strength=1.0)


@texture("wild_sawdust", size=1024, seed=9102)
def wild_sawdust(size: int, seed: int, out) -> None:
    """Fresh sawdust heaped under a saw: fine granular dust, small flat chips catching light,
    darker bark crumbs and a few thin curled shavings. Tan (tinted older/greyer per material)."""
    r = T.rng(seed)
    grains = T.blur(r.random((size, size)).astype(np.float32), 0.6)
    grains2 = T.blur(r.random((size, size)).astype(np.float32), 1.4)
    mid = T.spectral(size, 1.2, seed + 1)
    low = T.spectral(size, 2.4, seed + 2)
    f1, f2, cid = T.worley(size, 14000, seed + 3)
    chip = T.smoothstep(0.0, 1.0, f2 - f1) * (_hash01(cid, 4) > 0.78) * _hash01(cid, 5)
    cf1, _, ccid = T.worley(size, 900, seed + 5)
    crumbs = _dots(cf1, ccid, 0.7, 2.0, 0.2, 7)
    shav_segs = []
    for _ in range(22):
        x, y = r.uniform(0, size, 2)
        a = r.uniform(0, np.pi)
        w = r.uniform(1.0, 2.2)
        for k in range(7):
            a += r.normal(0, 0.45)
            nx, ny = x + np.cos(a) * 6, y + np.sin(a) * 6
            shav_segs.append((x, y, nx, ny, w))
            x, y = nx, ny
    shav = _segments(size, shav_segs, soft=1.0)
    t = T.normalize(0.45 * grains + 0.25 * grains2 + 0.3 * mid)
    alb = T.gradient(t, [(0.0, "#9a754a"), (0.4, "#b48d5c"), (0.75, "#c6a06c"), (1.0, "#d6b47f")])
    alb = alb * (0.9 + 0.2 * (low[..., None] - 0.5))
    alb = T.mix(alb, _full(size, "#e0c592"), (chip * 0.6)[..., None])
    alb = T.mix(alb, _full(size, "#e3c895"), (shav * 0.55)[..., None])
    alb = T.mix(alb, _full(size, "#4d3420"), (crumbs * 0.75)[..., None])
    height = 0.4 + 0.25 * grains + 0.15 * grains2 + 0.12 * mid + 0.15 * chip + 0.2 * shav + 0.1 * crumbs
    rough = 0.9 - 0.08 * chip - 0.05 * shav
    _save(out, alb, height, rough, normal_strength=5.0, ao_strength=1.3)


# --------------------------------------------------------------------------------------------
# Metal: cast iron, saw steel, enamelware
# --------------------------------------------------------------------------------------------

@texture("wild_cast_iron", size=1024, seed=9103)
def wild_cast_iron(size: int, seed: int, out) -> None:
    """Sand-cast iron (stoves, machine frames, carriage castings): pebbled casting skin, worn
    graphite sheen on the high points, orange rust bloom in damp patches, grey ash and soot."""
    f1, f2, cid = T.worley(size, 5200, seed)
    peb = T.smoothstep(0.0, 2.2, f2 - f1) * (0.6 + 0.4 * _hash01(cid, 1))
    fine = T.spectral(size, 0.7, seed + 1)
    low = T.spectral(size, 2.5, seed + 2)
    rust_f = T.spectral(size, 1.7, seed + 3)
    rust = T.smoothstep(0.6, 0.8, 0.7 * rust_f + 0.3 * fine)
    rust_core = T.smoothstep(0.72, 0.9, 0.7 * rust_f + 0.3 * fine)
    ash = T.smoothstep(0.72, 0.95, T.spectral(size, 2.0, seed + 4)) * (1 - rust)
    pf1, _, pid = T.worley(size, 1400, seed + 5)
    pits = _dots(pf1, pid, 0.6, 1.8, 0.4, 9)
    base = T.gradient(T.normalize(0.5 * low + 0.3 * peb + 0.2 * fine),
                      [(0.0, "#1d1c1b"), (0.5, "#2d2c2a"), (0.85, "#3c3a37"), (1.0, "#4a4743")])
    sheen = T.smoothstep(0.55, 0.9, peb * (0.6 + 0.4 * fine))
    alb = T.mix(base, _full(size, "#5d5a55"), (sheen * 0.35)[..., None])
    rcol = T.gradient(T.normalize(rust_f + 0.3 * fine), [(0.0, "#3b2216"), (0.5, "#5e3420"), (1.0, "#7f4a2a")])
    alb = T.mix(alb, rcol, rust[..., None] * 0.85)
    alb = T.mix(alb, _full(size, "#8b5a36"), (rust_core * 0.4)[..., None])
    alb = T.mix(alb, _full(size, "#6b6862"), (ash * 0.28)[..., None])
    alb = T.mix(alb, _full(size, "#0d0b0a"), (pits * 0.8)[..., None])
    height = 0.45 + 0.28 * peb + 0.08 * fine + 0.12 * rust * fine - 0.3 * pits
    rough = 0.62 + 0.12 * (1 - sheen) + 0.22 * rust + 0.1 * ash
    metal = np.clip(0.55 * (1 - rust) * (1 - ash) + 0.15 * sheen, 0, 1)
    _save(out, alb, height, rough, metal=metal, normal_strength=3.5, ao_strength=1.0)


@texture("wild_saw_steel", size=512, seed=9104)
def wild_saw_steel(size: int, seed: int, out) -> None:
    """Saw-plate steel (band and circular blades, rails, machine ways): grind lines along U,
    blue-straw heat tint in bands, rust freckles and a dull tarnish."""
    grind = T.spectral(size, 0.6, seed, anisotropy=(1.0, 60.0))
    grind2 = T.spectral(size, 1.1, seed + 1, anisotropy=(1.0, 20.0))
    tarnish = T.smoothstep(0.45, 0.85, T.spectral(size, 2.2, seed + 2))
    heat = T.spectral(size, 2.0, seed + 3, anisotropy=(1.0, 4.0))
    f1, _, cid = T.worley(size, 700, seed + 4)
    freck = _dots(f1, cid, 0.6, 2.4, 0.3, 3)
    blot = T.smoothstep(0.7, 0.88, T.spectral(size, 1.5, seed + 5))
    alb = _full(size, "#a3a6a8") * (0.9 + 0.14 * (grind[..., None] - 0.5) + 0.06 * (grind2[..., None] - 0.5))
    alb = T.mix(alb, _full(size, "#8a7c62"), (T.smoothstep(0.55, 0.75, heat) * 0.25)[..., None])
    alb = T.mix(alb, _full(size, "#5f6a78"), (T.smoothstep(0.75, 0.9, heat) * 0.2)[..., None])
    alb = T.mix(alb, _full(size, "#6d6a63"), (tarnish * 0.4)[..., None])
    rust = np.clip(freck + blot * 0.7, 0, 1)
    alb = T.mix(alb, _full(size, "#6b3b1f"), (rust * 0.85)[..., None])
    height = 0.5 + 0.12 * grind + 0.05 * grind2 + 0.15 * rust
    rough = 0.3 + 0.1 * grind2 + 0.2 * tarnish + 0.5 * rust
    metal = np.clip(0.95 - 0.8 * rust - 0.2 * tarnish, 0, 1)
    _save(out, alb, height, rough, metal=metal, normal_strength=1.6, ao_strength=0.5)


@texture("wild_enamel", size=512, seed=9109)
def wild_enamel(size: int, seed: int, out) -> None:
    """Granite-ware enamel (mess plates, cups, coffee pots, wash basins): mottled grey-blue glaze
    with white and dark speckle, chips through to black steel with rust rings. Tinted per
    material."""
    f1, _, cid = T.worley(size, 5000, seed)
    white = _dots(f1, cid, 0.5, 1.5, 0.35, 1)
    f1b, _, cidb = T.worley(size, 3000, seed + 1)
    dark = _dots(f1b, cidb, 0.4, 1.1, 0.25, 3)
    mott = T.spectral(size, 1.6, seed + 2)
    cf1, _, ccid = T.worley(size, 60, seed + 3)
    wx, wy = T.spectral(size, 1.8, seed + 7), T.spectral(size, 1.8, seed + 8)
    cf1 = T.warp(cf1, wx, wy, 6.0)
    ccid = T.warp(ccid.astype(np.float32), wx, wy, 6.0).round().astype(np.int64)
    crad = 1.5 + 7.5 * _hash01(ccid, 5) ** 3
    keep = _hash01(ccid, 6) < 0.3
    chip = T.smoothstep(crad + 0.8, crad - 0.8, cf1) * keep
    ring = (T.smoothstep(crad + 3.0, crad + 0.6, cf1) - chip).clip(0, 1) * keep
    alb = T.gradient(mott, [(0.0, "#a7b0b6"), (0.5, "#bcc4c9"), (1.0, "#cdd4d8")])
    alb = T.mix(alb, _full(size, "#f1efe8"), (white * 0.85)[..., None])
    alb = T.mix(alb, _full(size, "#3f4850"), (dark * 0.6)[..., None])
    alb = T.mix(alb, _full(size, "#1b1a19"), (chip * 0.95)[..., None])
    alb = T.mix(alb, _full(size, "#6e3a1d"), (ring * 0.7)[..., None])
    height = 0.6 + 0.05 * mott + 0.03 * white - 0.35 * chip
    rough = 0.22 + 0.06 * mott + 0.55 * chip + 0.35 * ring
    metal = np.clip(0.6 * chip, 0, 1)
    _save(out, alb, height, rough, metal=metal, normal_strength=2.5, ao_strength=0.6)


# --------------------------------------------------------------------------------------------
# Soft goods: fur, wool
# --------------------------------------------------------------------------------------------

@texture("wild_fur", size=1024, seed=9105)
def wild_fur(size: int, seed: int, out) -> None:
    """Pelt fur, hair running down V (image rows): fine underfur, clumped and parted guard hairs
    with dark tips, a darker spine band every tile (map 1 tile across a pelt's width)."""
    under = T.spectral(size, 0.7, seed, anisotropy=(14.0, 1.0))
    guard = T.spectral(size, 0.5, seed + 1, anisotropy=(40.0, 1.0))
    clump = T.spectral(size, 1.9, seed + 2, anisotropy=(3.0, 1.0))
    wx, wy = T.spectral(size, 2.2, seed + 3), T.spectral(size, 2.2, seed + 4)
    guard = T.warp(guard, wx, wy, 14.0)
    under = T.warp(under, wx, wy, 10.0)
    parts = T.smoothstep(0.0, 0.18, T.warp(np.abs(clump - 0.5), wx, wy, 20.0))  # hair parting lines
    u, _ = _uv(size)
    spine = np.exp(-((u - 0.5) / 0.18) ** 2)
    tips = T.smoothstep(0.62, 0.85, guard)
    t = T.normalize(0.5 * under + 0.3 * clump + 0.2 * guard)
    alb = T.gradient(t, [(0.0, "#4a3220"), (0.4, "#6b4a2e"), (0.75, "#8a6640"), (1.0, "#a37c52")])
    alb = alb * (0.75 + 0.25 * parts[..., None])
    alb = T.mix(alb, _full(size, "#2a1b11"), (tips * 0.55)[..., None])
    alb = T.mix(alb, alb * 0.62, spine[..., None] * 0.6)
    height = 0.3 + 0.45 * guard * parts + 0.2 * under + 0.05 * clump
    rough = 0.7 + 0.14 * (1 - tips) + 0.06 * under
    _save(out, alb, height, rough, normal_strength=9.0, ao_strength=1.6)


@texture("wild_wool_blanket", size=1024, seed=9106)
def wild_wool_blanket(size: int, seed: int, out) -> None:
    """Felted camp wool blanket: fuzzy fibre, faint twill, pilling, moth holes, and one band of
    three stripes across V per tile (tile = 1 m). Light neutral base so materials tint it."""
    _, v = _uv(size)
    fuzz = T.spectral(size, 0.75, seed)
    low = T.spectral(size, 2.2, seed + 1)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    twill = 0.5 + 0.5 * np.sin(2 * np.pi * (xx + yy) / 6.0)
    f1, _, cid = T.worley(size, 2200, seed + 2)
    pills = _dots(f1, cid, 0.8, 2.2, 0.25, 1)
    stripes = np.zeros((size, size), np.float32)
    wob = 0.004 * (T.spectral(size, 2.0, seed + 3, anisotropy=(6.0, 1.0)) - 0.5)
    for c, w in ((0.12, 0.022), (0.16, 0.008), (0.2, 0.022)):
        d = np.abs(v + wob - c)
        stripes = np.maximum(stripes, T.smoothstep(w + 0.003, w - 0.003, d))
    f1h, _, cidh = T.worley(size, 40, seed + 4)
    holes = _dots(f1h, cidh, 1.0, 3.5, 0.18, 9)
    alb = T.gradient(T.normalize(0.6 * low + 0.4 * fuzz), [(0.0, "#a8a296"), (0.5, "#bdb7aa"), (1.0, "#cdc7ba")])
    alb = alb * (0.93 + 0.1 * (twill[..., None] - 0.5) + 0.1 * (fuzz[..., None] - 0.5))
    alb = T.mix(alb, _full(size, "#2b2724"), (stripes * 0.85)[..., None])
    alb = T.mix(alb, alb * 1.08, pills[..., None] * 0.6)
    alb = T.mix(alb, _full(size, "#141210"), (holes * 0.9)[..., None])
    height = 0.45 + 0.3 * fuzz + 0.1 * twill + 0.2 * pills - 0.4 * holes
    rough = 0.95 - 0.04 * fuzz
    _save(out, alb, height, rough, normal_strength=6.0, ao_strength=1.2)


# --------------------------------------------------------------------------------------------
# Roofing
# --------------------------------------------------------------------------------------------

@texture("wild_tarpaper", size=512, seed=9110)
def wild_tarpaper(size: int, seed: int, out) -> None:
    """Mineral-surfaced roll roofing on sheds and outhouses: dark granules, one lap seam with a
    nail line per tile (tile = 1 m, seam along U), sun-faded patches, cracks and moss in the lap."""
    r = T.rng(seed)
    _, v = _uv(size)
    f1, f2, cid = T.worley(size, 9000, seed)
    gran = T.smoothstep(0.0, 1.2, f2 - f1) * _hash01(cid, 1)
    bright = (_hash01(cid, 2) > 0.92).astype(np.float32) * T.smoothstep(1.4, 0.4, f1)
    fade = T.smoothstep(0.45, 0.9, T.spectral(size, 2.3, seed + 1))
    lap = np.exp(-((v - 0.86) / 0.006) ** 2)
    under_lap = T.smoothstep(0.86, 0.9, v) * (1 - T.smoothstep(0.97, 0.99, v))
    nails = np.zeros((size, size), np.float32)
    for k in range(9):
        cx = (k + 0.5) * size / 9 + r.normal(0, 3)
        nails = np.maximum(nails, _segments(size, [(cx, 0.82 * size, cx, 0.82 * size, 2.2)], soft=0.8))
    cracks = _segments(size, [(x, y, x + r.normal(0, 30), y + r.normal(0, 30), 0.6)
                              for x, y in zip(r.uniform(0, size, 30), r.uniform(0, size, 30))], soft=0.6)
    moss = T.smoothstep(0.55, 0.8, T.spectral(size, 1.8, seed + 2)) * (0.4 * under_lap + 0.6 * lap)
    alb = T.gradient(gran, [(0.0, "#1c1c1d"), (0.6, "#2c2c2c"), (1.0, "#3e3d3b")])
    alb = T.mix(alb, _full(size, "#6b6863"), (bright * 0.7)[..., None])
    alb = T.mix(alb, _full(size, "#4e4b46"), (fade * 0.4)[..., None])
    alb = T.mix(alb, _full(size, "#0d0d0d"), (lap * 0.8 + cracks * 0.7)[..., None].clip(0, 1))
    alb = T.mix(alb, _full(size, "#9a9590"), (nails * 0.8)[..., None])
    alb = T.mix(alb, _full(size, "#3d4a22"), (moss * 0.6)[..., None])
    height = 0.45 + 0.25 * gran + 0.2 * under_lap - 0.3 * lap - 0.3 * cracks + 0.2 * nails
    rough = 0.92 - 0.3 * nails
    metal = 0.6 * nails
    _save(out, alb, height, rough, metal=metal, normal_strength=3.0, ao_strength=1.2)


# --------------------------------------------------------------------------------------------
# Non-tiling sheets
# --------------------------------------------------------------------------------------------

@texture("wild_firefinder_map", size=1024, seed=9107)
def wild_firefinder_map(size: int, seed: int, out) -> None:
    """The Osborne fire-finder's map disc seen from above: cream map paper with brown contour
    lines (every fifth heavier), blue lakes and creeks, a faint section grid, green timber tint,
    a printed degree ring (1/5/10 degree ticks) at the rim and pencilled bearing lines with
    circled fire marks. The disc fills radius 0.47 of the sheet; outside is dark stained wood."""
    r = T.rng(seed)
    u, v = _uv(size)
    dx, dy = u - 0.5, v - 0.5
    rad = np.hypot(dx, dy)
    ang = np.arctan2(dy, dx)
    terrain = T.normalize(0.6 * T.spectral(size, 2.6, seed) + 0.4 * T.spectral(size, 1.9, seed + 1))
    lv = terrain * 22.0
    frac = lv - np.floor(lv)
    grad = np.hypot(*np.gradient(lv)) + 1e-4
    line = T.smoothstep(1.2, 0.3, np.minimum(frac, 1 - frac) / grad)
    index = (np.floor(lv).astype(int) % 5 == 0).astype(np.float32)
    lakes = T.smoothstep(0.205, 0.195, terrain)
    timber = T.smoothstep(0.45, 0.6, T.spectral(size, 2.2, seed + 2)) * (1 - lakes)
    creek_segs = []
    for _ in range(5):
        x, y = r.uniform(0.25, 0.75, 2) * size
        a = r.uniform(0, 2 * np.pi)
        for k in range(26):
            a += r.normal(0, 0.3)
            nx, ny = x + np.cos(a) * 11, y + np.sin(a) * 11
            creek_segs.append((x, y, nx, ny, 0.9 + 0.04 * k))
            x, y = nx, ny
    creeks = _segments(size, creek_segs, soft=0.8, wrap=False)
    grid = np.zeros((size, size), np.float32)
    for k in range(1, 12):
        p = k * size / 12
        grid = np.maximum(grid, _segments(size, [(p, 0, p, size, 0.5), (0, p, size, p, 0.5)], soft=0.6, wrap=False))
    paper = T.gradient(T.spectral(size, 2.0, seed + 3), [(0.0, "#d9cfb2"), (1.0, "#e8dfc4")])
    alb = T.mix(paper, _full(size, "#c9d3a6"), (timber * 0.55)[..., None])
    alb = T.mix(alb, _full(size, "#9db5c4"), lakes[..., None])
    alb = T.mix(alb, _full(size, "#9a9488"), (grid * 0.35)[..., None])
    alb = T.mix(alb, _full(size, "#8a5a32"), (line * (0.45 + 0.4 * index))[..., None])
    alb = T.mix(alb, _full(size, "#4f7891"), (creeks * 0.9)[..., None])
    # Degree ring printed round the rim.
    deg = (np.degrees(ang) + 360.0) % 360.0
    near = np.minimum(deg % 1.0, 1.0 - deg % 1.0)
    tick1 = T.smoothstep(0.12, 0.05, near) * ((rad > 0.452) & (rad < 0.468))
    near5 = np.minimum(deg % 5.0, 5.0 - deg % 5.0)
    tick5 = T.smoothstep(0.16, 0.08, near5) * ((rad > 0.44) & (rad < 0.468))
    near10 = np.minimum(deg % 10.0, 10.0 - deg % 10.0)
    tick10 = T.smoothstep(0.2, 0.1, near10) * ((rad > 0.425) & (rad < 0.468))
    ring_band = ((rad > 0.418) & (rad < 0.47)).astype(np.float32)
    alb = T.mix(alb, _full(size, "#efe7d0"), (ring_band * 0.85)[..., None])
    alb = T.mix(alb, _full(size, "#1e1a14"), np.clip(tick1 + tick5 + tick10, 0, 1)[..., None])
    rim = np.exp(-((rad - 0.418) / 0.0015) ** 2) + np.exp(-((rad - 0.47) / 0.0015) ** 2)
    alb = T.mix(alb, _full(size, "#1e1a14"), np.clip(rim, 0, 1)[..., None])
    # Pencilled bearings from the lookout (the centre) with circled fire marks.
    c = size / 2
    segs, circles = [], []
    for k in range(7):
        a = r.uniform(0, 2 * np.pi)
        L = r.uniform(0.25, 0.41) * size
        segs.append((c, c, c + np.cos(a) * L, c + np.sin(a) * L, 0.9))
        if k < 4:
            t = r.uniform(0.4, 0.9) * L
            px, py = c + np.cos(a) * t, c + np.sin(a) * t
            for j in range(16):
                a0, a1 = 2 * np.pi * j / 16, 2 * np.pi * (j + 1) / 16
                circles.append((px + 9 * np.cos(a0), py + 9 * np.sin(a0), px + 9 * np.cos(a1), py + 9 * np.sin(a1), 0.9))
    pencil = np.maximum(_segments(size, segs, soft=0.8, wrap=False), _segments(size, circles, soft=0.8, wrap=False))
    alb = T.mix(alb, _full(size, "#55524d"), (pencil * 0.7)[..., None])
    cross = _segments(size, [(c - 10, c, c + 10, c, 0.8), (c, c - 10, c, c + 10, 0.8)], soft=0.6, wrap=False)
    alb = T.mix(alb, _full(size, "#1e1a14"), cross[..., None])
    wood = T.gradient(T.spectral(size, 1.0, seed + 4, anisotropy=(1.0, 20.0)), [(0.0, "#2c1d12"), (1.0, "#4a311d")])
    disc = T.smoothstep(0.4705, 0.4685, rad)
    alb = T.mix(wood, alb, disc[..., None])
    stain = T.smoothstep(0.6, 0.85, T.spectral(size, 2.0, seed + 5)) * disc
    alb = T.mix(alb, alb * 0.82, stain[..., None])
    height = 0.5 + 0.02 * terrain - 0.04 * (1 - disc) + 0.02 * pencil
    rough = 0.82 - 0.3 * (1 - disc) * 0.5
    _save(out, alb, height, rough, normal_strength=1.0, ao_strength=0.3)


@texture("wild_radio_panel", size=512, seed=9108)
def wild_radio_panel(size: int, seed: int, out) -> None:
    """Front panel of a 1970s base-station transceiver, drawn into the band v 0.3..0.7 (u 0..1):
    dial window with a tick scale and needle, a small arc meter, perforated speaker grille,
    toggle-switch plate, three knob bezels and corner screws, all on grey hammertone. The rest of
    the sheet is plain hammertone (sides, back). Tick marks and blank plates only, no text."""
    H = size
    W = size
    ham = T.spectral(size, 1.1, seed)
    f1, f2, _ = T.worley(size, 5000, seed + 1)
    dimple = T.blur(T.smoothstep(0.0, 2.0, f2 - f1), 0.8)
    base = T.gradient(T.normalize(0.8 * ham + 0.2 * dimple), [(0.0, "#4d5052"), (0.6, "#5a5d5f"), (1.0, "#65686a")])
    y0, y1 = int(0.3 * H), int(0.7 * H)
    bh = y1 - y0

    def px(fu, fv):
        return fu * W, y0 + fv * bh

    def draw_panel(d, s):
        def box(u0, v0, u1, v1, **kw):
            a = px(u0, v0)
            b = px(u1, v1)
            d.rectangle([a[0] * s, a[1] * s, b[0] * s, b[1] * s], **kw)
        box(0.04, 0.16, 0.5, 0.52, fill=255)          # dial window
        box(0.56, 0.16, 0.72, 0.46, fill=255)         # meter
    windows = _draw(W, H, draw_panel)

    def draw_ticks(d, s):
        for k in range(41):
            x = (0.06 + 0.42 * k / 40) * W
            top = y0 + (0.24 if k % 5 else 0.2) * bh
            d.line([x * s, top * s, x * s, (y0 + 0.32 * bh) * s], fill=255, width=max(1, s))
        cx, cy = 0.64 * W, y0 + 0.44 * bh
        for k in range(11):
            a = np.radians(200 + 140 * k / 10)
            r0, r1 = 0.15 * bh, (0.2 if k % 5 else 0.23) * bh
            d.line([(cx + np.cos(a) * r0) * s, (cy + np.sin(a) * r0) * s, (cx + np.cos(a) * r1) * s,
                    (cy + np.sin(a) * r1) * s], fill=255, width=max(1, s))
        d.line([(0.31 * W) * s, (y0 + 0.18 * bh) * s, (0.3 * W) * s, (y0 + 0.5 * bh) * s], fill=180, width=2 * s)
        a = np.radians(250)
        d.line([cx * s, cy * s, (cx + np.cos(a) * 0.21 * bh) * s, (cy + np.sin(a) * 0.21 * bh) * s], fill=180, width=s)
    ticks = _draw(W, H, draw_ticks)

    def draw_grille(d, s):
        for i in range(14):
            for j in range(7):
                x = (0.78 + 0.014 * i) * W
                y = y0 + (0.18 + 0.1 * j) * bh
                rr = 0.0045 * W
                d.ellipse([(x - rr) * s, (y - rr) * s, (x + rr) * s, (y + rr) * s], fill=255)
    grille = _draw(W, H, draw_grille)

    def draw_bezels(d, s):
        for fu in (0.12, 0.27, 0.42):
            x, y = px(fu, 0.76)
            rr = 0.085 * bh
            d.ellipse([(x - rr) * s, (y - rr) * s, (x + rr) * s, (y + rr) * s], outline=255, width=2 * s)
        for fu in (0.6, 0.66, 0.72):  # toggle switch plates
            x, y = px(fu, 0.74)
            d.rectangle([(x - 0.012 * W) * s, (y - 0.08 * bh) * s, (x + 0.012 * W) * s, (y + 0.08 * bh) * s], outline=255, width=s)
        for fu, fv in ((0.015, 0.06), (0.985, 0.06), (0.015, 0.94), (0.985, 0.94)):
            x, y = px(fu, fv)
            rr = 0.012 * W
            d.ellipse([(x - rr) * s, (y - rr) * s, (x + rr) * s, (y + rr) * s], fill=255)
        x0, yy0 = px(0.8, 0.82)
        x1, yy1 = px(0.97, 0.94)
        d.rectangle([x0 * s, yy0 * s, x1 * s, yy1 * s], outline=255, width=s)  # blank maker plate
    bez = _draw(W, H, draw_bezels)
    alb = base.copy()
    dial_bg = T.gradient(T.spectral(size, 2.0, seed + 2), [(0.0, "#c9b98f"), (1.0, "#dccca2")])
    alb = T.mix(alb, dial_bg, windows[..., None])
    alb = T.mix(alb, _full(size, "#1c1a17"), (ticks * windows)[..., None])
    alb = T.mix(alb, _full(size, "#151515"), grille[..., None])
    alb = T.mix(alb, _full(size, "#2a2b2c"), (bez * 0.85)[..., None])
    grime = T.smoothstep(0.55, 0.9, T.spectral(size, 2.0, seed + 3))
    alb = T.mix(alb, _full(size, "#2f2a22"), (grime * 0.35)[..., None])
    height = 0.55 + 0.05 * dimple - 0.25 * windows - 0.3 * grille + 0.1 * bez
    rough = 0.55 + 0.15 * ham - 0.35 * windows + 0.2 * grime
    metal = np.clip(0.35 * (1 - windows) * (1 - grille), 0, 1)
    _save(out, alb, height, rough, metal=metal, normal_strength=2.0, ao_strength=0.8)
