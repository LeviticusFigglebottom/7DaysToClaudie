"""Traps and lock cues family (POI dungeon mechanics, ADR-0018): tileable PBR sets for the
generated bear traps, shotgun trip-wire rigs, alarm boxes, loose/rotten floorboards and door locks.

  * trap_forged_steel — blackened forged steel: hammer peen, mill-scale patches, pitting and
                        orange rust blooms (metallic where bare, rough rust where not). Used for
                        bear-trap jaws, springs, chains, hasps and staples (tinted per material).
  * trap_twine        — twisted cord / tripwire twine along U (light, tinted per material).
  * trap_old_boards   — loose fir floorboards along U, 1 m tile: grain, rings, knots, grime in the
                        grain, nail holes and water marks (creaky and weak floor patches).
Metre-scaled UVs: uv_scale = 1 / tile size in game/data/materials/props_traps.json.
"""
from __future__ import annotations

import numpy as np

from .. import texlib as T
from ..registry import texture


def _c(h: str) -> np.ndarray:
    return T.hex_rgb(h)[None, None, :]


def _hash01(ids: np.ndarray, k: int = 0) -> np.ndarray:
    """Deterministic pseudo-random value in [0, 1) per integer id (vectorised integer hash)."""
    x = (ids.astype(np.int64) * 374761393 + (k + 1) * 668265263) & 0xFFFFFFFF
    x = ((x ^ (x >> 13)) * 1274126177) & 0xFFFFFFFF
    x = x ^ (x >> 16)
    return (x & 0xFFFFFF).astype(np.float32) / float(0x1000000)


def _save(out, albedo, height, rough, *, metal=0.0, normal_strength=4.0, ao_strength=1.0):
    T.save_pbr_set(out, np.clip(albedo, 0, 1), np.clip(height, 0, 1), np.clip(rough, 0, 1), metal=metal,
                   normal_strength=normal_strength, ao_strength=ao_strength)


@texture("trap_forged_steel", size=1024, seed=7101)
def trap_forged_steel(size: int, seed: int, out) -> None:
    """Hand-forged trap steel left a year in a damp house: a blue-black mill-scale skin flaking off
    bare grey steel, shallow hammer peen dimples, pits, and orange-brown rust blooming out of the
    pits and along the low spots (rust is matte and non-metallic)."""
    broad = T.spectral(size, 2.4, seed)
    mid = T.spectral(size, 1.9, seed + 1, fmin=3.0)
    fine = T.spectral(size, 0.6, seed + 2)
    # Hammer peen: soft, shallow cellular dimples (fine and blurred: big sharp-edged cells catch
    # the light as facets on thin jaws).
    f1, f2, cid = T.worley(size, 900, seed + 3)
    peen = T.blur(np.clip(1.0 - f1 / (np.median(f2) * 0.85), 0.0, 1.0) ** 1.4, 1.5)
    # Mill scale: blotchy blue-black skin, flaked off where `scale` is low.
    flake = T.spectral(size, 1.7, seed + 6, fmin=4.0)
    scale = T.smoothstep(0.44, 0.6, 0.5 * mid + 0.5 * flake)
    scale_edge = np.exp(-((0.5 * mid + 0.5 * flake - 0.52) / 0.02) ** 2)
    # Pits: small dark craters, denser where the rust is.
    p1, _, pid = T.worley(size, 1400, seed + 4)
    prad = 0.8 + 2.6 * _hash01(pid, 1) ** 2
    pits = T.smoothstep(prad + 0.7, prad - 0.7, p1) * (_hash01(pid, 2) > 0.55)
    # Rust: blooms in the low, flaked-off areas and around the pits; crusty, lumpy and streaked.
    bloom = T.spectral(size, 2.0, seed + 7, fmin=2.0)
    rust_field = 0.55 * (1.0 - broad) + 0.45 * bloom + 0.5 * T.blur(pits, 4.0) + 0.12 * (fine - 0.5) - 0.18 * scale
    rust = T.smoothstep(0.56, 0.72, rust_field)  # ~20 % cover: a damp year, not a decade outdoors
    crust = T.spectral(size, 0.9, seed + 5)
    ones = np.ones((size, size, 3), np.float32)
    steel = T.mix(_c("#5c5f63") * ones, _c("#3f4246") * ones, mid)
    alb = T.mix(steel, _c("#26282c") * ones, scale * 0.75)
    alb = T.mix(alb, _c("#74787d") * ones, scale_edge * 0.3)
    alb = alb * (0.9 + 0.18 * (fine[..., None] - 0.5))
    rust_col = T.gradient(crust, [(0.0, "#2e1a10"), (0.35, "#4f2c17"), (0.65, "#6e3d1d"), (1.0, "#8a5530")])
    alb = T.mix(alb, rust_col, rust * 0.9)
    alb = T.mix(alb, _c("#0d0c0b") * ones, pits * 0.75)
    height = 0.55 - 0.07 * peen + 0.04 * fine + 0.14 * rust * crust - 0.3 * pits + 0.05 * scale
    rough = 0.38 + 0.12 * scale + 0.45 * rust + 0.08 * (fine - 0.5) + 0.12 * pits
    metal = np.clip(0.92 * (1.0 - rust) * (1.0 - 0.3 * scale), 0.0, 1.0)
    _save(out, alb, height, rough, metal=metal, normal_strength=3.0, ao_strength=0.8)


@texture("trap_twine", size=512, seed=7111)
def trap_twine(size: int, seed: int, out) -> None:
    """Three-ply twisted cord running along U (one twist period every 1/12 tile): light fibre colour
    for tinting (jute, tarred line, nylon), fibre fuzz and grime caught in the lay."""
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    u, v = (xx + 0.5) / size, (yy + 0.5) / size
    fibres = T.spectral(size, 0.5, seed, anisotropy=(1.0, 10.0))
    wobble = T.spectral(size, 2.5, seed + 3)
    twist = 0.5 + 0.5 * np.sin(2.0 * np.pi * (u * 12.0 + v * 3.0 + (wobble - 0.5) * 0.6))
    plies = T.smoothstep(0.0, 1.0, twist)
    fuzz = T.spectral(size, 1.2, seed + 1)
    dirt = T.smoothstep(0.55, 0.9, T.spectral(size, 2.2, seed + 2))
    base = _c("#cdb48a") * np.ones((size, size, 3), np.float32)
    alb = base * (0.8 + 0.22 * plies[..., None]) * (0.88 + 0.24 * (fibres[..., None] - 0.5))
    alb = T.mix(alb, _c("#4b3f30") * np.ones_like(alb), (1.0 - plies) * 0.22 + dirt * 0.3)
    height = 0.4 + 0.4 * plies + 0.12 * fibres + 0.06 * fuzz
    rough = 0.82 + 0.1 * fuzz - 0.05 * plies + 0.05 * dirt
    _save(out, alb, height, rough, normal_strength=3.0, ao_strength=1.0)


@texture("trap_old_boards", size=1024, seed=7121)
def trap_old_boards(size: int, seed: int, out) -> None:
    """Old fir floorboard (grain along U, one 1 m board-length per tile): greyed, scuffed face, dark
    grime packed into the grain and around knots, nail holes and tide-mark water stains."""
    grain = T.spectral(size, 1.0, seed, anisotropy=(1.0, 24.0))
    # Edge-grain fir: growth rings run nearly straight along the board, wandering a little.
    yy0, _ = np.mgrid[0:size, 0:size].astype(np.float32)
    wander = T.spectral(size, 2.6, seed + 6, anisotropy=(1.0, 6.0))
    phase = yy0 / size * 34.0 + (wander - 0.5) * 3.0 + (grain - 0.5) * 0.35
    rings = 0.5 + 0.5 * np.sin(2.0 * np.pi * phase)
    rings = T.smoothstep(0.1, 0.95, rings) ** 1.6
    f1, _, kid = T.worley(size, 6, seed + 3)
    knot_r = 7.0 + 12.0 * _hash01(kid, 1)
    knots = T.smoothstep(knot_r * 1.6, knot_r * 0.4, f1) * (_hash01(kid, 2) > 0.5)
    stain = T.spectral(size, 2.8, seed + 4)
    tide = np.exp(-((stain - 0.66) / 0.012) ** 2) * 0.6
    wet = T.smoothstep(0.62, 0.7, stain)
    scuff = T.smoothstep(0.6, 0.85, T.spectral(size, 1.6, seed + 5, anisotropy=(4.0, 1.0)))
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    holes = np.zeros((size, size), np.float32)
    for cx, cy in ((0.07, 0.3), (0.07, 0.7), (0.57, 0.3), (0.57, 0.7)):
        d = np.hypot(xx - cx * size, yy - cy * size)
        holes = np.maximum(holes, T.smoothstep(5.5, 3.0, d))
    base = T.gradient(rings * 0.7 + grain * 0.3, [(0.0, "#5a4532"), (0.45, "#806649"), (1.0, "#a88d6a")])
    alb = base * (0.88 + 0.24 * (grain[..., None] - 0.5))
    alb = alb + (_c("#948f86") - alb) * 0.22  # greyed by years of dust
    ones = np.ones_like(alb)
    alb = T.mix(alb, _c("#3a2c1e") * ones, knots * 0.75)
    alb = T.mix(alb, _c("#2b241b") * ones, (1.0 - rings) * 0.18 + tide * 0.5)
    alb = T.mix(alb, _c("#4f4234") * ones, wet * 0.3)
    alb = T.mix(alb, _c("#c2b9a7") * ones, scuff * 0.15)
    alb = T.mix(alb, _c("#141210") * ones, holes * 0.9)
    height = 0.5 + 0.16 * rings + 0.1 * grain - 0.12 * knots - 0.4 * holes + 0.05 * scuff
    rough = 0.72 + 0.12 * (1.0 - rings) - 0.08 * scuff + 0.08 * wet
    _save(out, alb, height, rough, normal_strength=3.2, ao_strength=0.9)
