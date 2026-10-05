"""Wildlife (ADR-0027): neutral strand and feather sets for the fur shader, and the hard parts.

  animal_fur_short   a deer's coat: short, dense, hollow guard hairs lying along V (image rows)
                     in faint ripples, agouti bands; neutral grey around 0.5 (the coat colour comes
                     from vertex colour and the material's tints). 1 tile ~ 0.11 m at uv_scale 9.
  animal_fur_soft    a hare's coat: finer, longer and fluffier, in tufts that part.
  animal_feathers    contour feathers: overlapping scalloped vanes with rachis and barbs.
  animal_antler      antler bone: grooves and pearling along V, polished tines, blood-dark seams.
  animal_hoof        keratin: growth rings across V, vertical striations, scuffs and dried mud.
"""
from __future__ import annotations

import numpy as np

from .. import texlib as T
from ..registry import texture


def _neutral(s: np.ndarray, lo: float = 0.32, hi: float = 0.68) -> np.ndarray:
    v = lo + (hi - lo) * s
    return np.stack([v, v * 0.985, v * 0.96], -1).astype(np.float32)


def _strands(size: int, seed: int, length: float, density: float, wave: float):
    """Hair strands along V: anisotropic noise (long in V), sharpened, with a slow sideways wave so
    the hairs lie in locks rather than ruled lines."""
    a = T.spectral(size, 0.7, seed, anisotropy=(length, 1.0))
    w = T.spectral(size, 2.6, seed + 1)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    a = T.warp(a, w, np.full_like(w, 0.5), wave * size / 64.0)
    fine = T.spectral(size, 0.5, seed + 2, anisotropy=(length * 0.6, 1.0))
    s = T.normalize(0.65 * a + 0.35 * fine)
    return T.levels(s, 0.5 - 0.5 / density, 0.5 + 0.5 / density), yy, xx


@texture("animal_fur_short", size=1024, seed=2701)
def animal_fur_short(size: int, seed: int, out) -> None:
    s, _, _ = _strands(size, seed, 22.0, 1.5, 1.5)
    clumps = T.spectral(size, 1.6, seed + 5, anisotropy=(3.0, 1.0))
    # agouti: dark tips and pale bands, so the coat reads grizzled close up
    band = T.smoothstep(0.55, 0.8, T.spectral(size, 1.2, seed + 6, anisotropy=(8.0, 1.0)))
    v = np.clip(0.55 * s + 0.25 * clumps + 0.25 * band - 0.05, 0, 1)
    col = _neutral(v, 0.30, 0.70)
    height = T.normalize(0.7 * s + 0.3 * clumps)
    rough = np.clip(0.78 + 0.18 * (1 - s), 0.55, 1.0)
    T.save_pbr_set(out, col, height, rough, normal_strength=3.0, ao_strength=0.6)


@texture("animal_fur_soft", size=1024, seed=2702)
def animal_fur_soft(size: int, seed: int, out) -> None:
    s, _, _ = _strands(size, seed, 14.0, 1.2, 3.0)
    tufts = T.spectral(size, 2.0, seed + 5, anisotropy=(2.0, 1.0))
    parts = T.smoothstep(0.78, 0.92, T.spectral(size, 1.8, seed + 6, anisotropy=(4.0, 1.0)))
    v = np.clip(0.6 * s + 0.35 * tufts - 0.35 * parts, 0, 1)
    col = _neutral(v, 0.30, 0.70)
    height = T.normalize(0.6 * s + 0.4 * tufts - 0.5 * parts)
    rough = np.clip(0.85 + 0.12 * (1 - s), 0.6, 1.0)
    T.save_pbr_set(out, col, height, rough, normal_strength=2.4, ao_strength=0.8)


@texture("animal_feathers", size=1024, seed=2703)
def animal_feathers(size: int, seed: int, out) -> None:
    """Rows of overlapping feathers (8 x 8 per tile, offset alternately) along V: each a rounded
    vane with a rachis down its middle and barbs angled off it."""
    r = T.rng(seed)
    n = 8
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) / size
    cell = 1.0 / n
    row = np.floor(yy / cell)
    off = (row % 2) * 0.5
    u = ((xx / cell + off) % 1.0) - 0.5            # across the feather
    v = (yy / cell) % 1.0                           # along it (tip at v = 1)
    jitter = r.uniform(-0.06, 0.06, (n, n)).astype(np.float32)
    ci = np.clip(np.floor(xx / cell + off).astype(int) % n, 0, n - 1)
    rj = row.astype(int) % n
    u = u + jitter[rj, ci]
    width = 0.42 * np.sqrt(np.clip(v, 0, 1)) * (1.15 - 0.3 * v)
    vane = T.smoothstep(0.02, -0.02, np.abs(u) - width)
    rachis = T.smoothstep(0.03, 0.0, np.abs(u))
    barbs = 0.5 + 0.5 * np.sin((v * 1.0 + np.abs(u) * 0.9) * 2 * np.pi * 22.0)
    edge = T.smoothstep(0.0, 0.08, width - np.abs(u))
    tone = r.uniform(-0.08, 0.08, (n, n)).astype(np.float32)[rj, ci]
    shade = 0.35 + 0.45 * v * vane + tone * vane   # each feather lies over the base of the next row
    val = np.clip(shade + 0.12 * barbs * vane - 0.1 * rachis + 0.08 * T.spectral(size, 1.4, seed + 3), 0, 1)
    col = _neutral(val, 0.28, 0.72)
    height = T.normalize(0.6 * shade + 0.15 * barbs * vane + 0.25 * rachis + 0.2 * edge)
    rough = np.clip(0.62 + 0.25 * (1 - vane) - 0.1 * rachis, 0.4, 0.95)
    T.save_pbr_set(out, col, height, rough, normal_strength=2.0, ao_strength=0.7)


@texture("animal_antler", size=1024, seed=2704)
def animal_antler(size: int, seed: int, out) -> None:
    grooves = T.spectral(size, 0.9, seed, anisotropy=(18.0, 1.0))
    pearl = T.smoothstep(0.62, 0.82, T.spectral(size, 1.1, seed + 1))
    stain = T.spectral(size, 2.2, seed + 2)
    col = T.gradient(T.normalize(0.5 * grooves + 0.5 * stain),
                     [(0.0, "#3d2c1d"), (0.35, "#6a5038"), (0.7, "#9a8062"), (1.0, "#c8b494")])
    col = T.mix(col, T.hex_rgb("#d9cdb4") * np.ones_like(col), pearl * 0.35)
    height = T.normalize(0.6 * grooves + 0.5 * pearl)
    rough = np.clip(0.55 + 0.3 * (1 - pearl) - 0.15 * grooves, 0.3, 0.95)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=4.0)


@texture("animal_hoof", size=512, seed=2705)
def animal_hoof(size: int, seed: int, out) -> None:
    rings = T.spectral(size, 0.8, seed, anisotropy=(1.0, 30.0))
    stri = T.spectral(size, 0.8, seed + 1, anisotropy=(30.0, 1.0))
    mud = T.smoothstep(0.55, 0.8, T.spectral(size, 2.0, seed + 2))
    col = T.gradient(T.normalize(0.5 * rings + 0.5 * stri), [(0.0, "#141110"), (0.6, "#2b2420"), (1.0, "#4a3e34")])
    col = T.mix(col, T.hex_rgb("#4a3a28") * np.ones_like(col), mud * 0.6)
    height = T.normalize(0.5 * rings + 0.3 * stri + 0.3 * mud)
    rough = np.clip(0.5 + 0.35 * mud + 0.1 * rings, 0.3, 0.95)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=2.5)


@texture("item_meat", size=512, seed=2706)
def item_meat(size: int, seed: int, out) -> None:
    """Raw venison: dark red muscle in fibre bundles along V, silverskin and fat marbling, wet."""
    fibres = T.spectral(size, 0.9, seed, anisotropy=(14.0, 1.0))
    bundles = T.spectral(size, 1.8, seed + 1, anisotropy=(4.0, 1.0))
    marble = T.smoothstep(0.7, 0.85, T.spectral(size, 1.4, seed + 2, anisotropy=(3.0, 1.0)))
    col = T.gradient(T.normalize(0.6 * fibres + 0.4 * bundles), [(0.0, "#3a0d0b"), (0.5, "#5e1814"), (1.0, "#7e2a20")])
    col = T.mix(col, T.hex_rgb("#d8c3b0") * np.ones_like(col), marble * 0.7)
    height = T.normalize(0.6 * fibres + 0.3 * bundles + 0.3 * marble)
    rough = np.clip(0.25 + 0.25 * marble + 0.15 * (1 - fibres), 0.15, 0.7)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=2.5)


@texture("item_meat_cooked", size=512, seed=2707)
def item_meat_cooked(size: int, seed: int, out) -> None:
    """Fire-roasted meat: a cracked brown crust, charred ridges, glistening fat."""
    crust = T.spectral(size, 1.3, seed)
    cracks = T.smoothstep(0.08, 0.0, np.abs(T.spectral(size, 1.6, seed + 1) - 0.5))
    char = T.smoothstep(0.68, 0.85, T.spectral(size, 1.5, seed + 2))
    col = T.gradient(crust, [(0.0, "#3b2012"), (0.5, "#6b3a1c"), (1.0, "#93582c")])
    col = T.mix(col, T.hex_rgb("#140c08") * np.ones_like(col), np.clip(char * 0.9 + cracks * 0.5, 0, 1))
    height = T.normalize(0.6 * crust - 0.5 * cracks + 0.2 * char)
    rough = np.clip(0.5 + 0.3 * char - 0.2 * crust, 0.25, 0.9)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=3.0)
