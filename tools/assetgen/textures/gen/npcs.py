"""Living people (the trader-post NPCs): what a healthy human needs that the Hollowed never had.

Only the eye is new: skin, cloth, hair and boots reuse the character sets (characters.py),
tinted per material in game/data/materials/npcs.json.
"""
from __future__ import annotations

import numpy as np

from .. import texlib as T
from ..registry import texture


def _c(h):
    return T.hex_rgb(h)[None, None, :]


@texture("npc_eye", size=512, seed=1211)
def npc_eye(size: int, seed: int, out) -> None:
    """A living eye (planar decal, centre = cornea, same layout as eyes_hollow): clean off-white
    sclera with a few fine vessels towards the corners (a tired man), a hazel-brown fibrous iris
    with a darker limbal ring, a sharp black pupil."""
    y, x = np.mgrid[0:size, 0:size].astype(np.float32)
    c = (size - 1) / 2
    r = np.sqrt((x - c) ** 2 + (y - c) ** 2) / (size / 2)
    ang = np.arctan2(y - c, x - c)
    sclera = T.gradient(T.spectral(size, 2.0, seed), [(0.0, "#d9d2c4"), (1.0, "#ebe6dc")])
    # a little redness only out at the corners (the eye's sides, where the lids meet)
    corner = T.smoothstep(0.62, 0.98, r) * (0.4 + 0.6 * np.abs(np.cos(ang)))
    fine = T.smoothstep(0.80, 0.95, T.spectral(size, 0.7, seed + 1, anisotropy=(1.0, 6.0)))
    sclera = T.mix(sclera, _c("#c08a7c") * np.ones_like(sclera), np.clip(corner * (0.25 + 0.6 * fine), 0, 1) * 0.6)
    iris_r = 0.40
    fib = 0.5 + 0.5 * np.sin(ang * 70 + T.spectral(size, 1.0, seed + 2) * 7)
    t = np.clip(r / iris_r, 0, 1)
    iris_in = T.mix(_c("#6e5426") * np.ones_like(sclera), _c("#8c6a32") * np.ones_like(sclera), fib[..., None] * 0.7)
    iris_out = T.mix(_c("#4a3a24") * np.ones_like(sclera), _c("#5e4a2c") * np.ones_like(sclera), fib[..., None] * 0.6)
    iris = T.mix(iris_in, iris_out, T.smoothstep(0.35, 0.95, t))
    iris_m = 1 - T.smoothstep(iris_r - 0.015, iris_r + 0.008, r)
    col = T.mix(sclera, iris, iris_m)
    limbus = np.exp(-((r - iris_r + 0.01) / 0.025) ** 2)
    col *= (1 - 0.45 * limbus)[..., None]
    pupil_m = 1 - T.smoothstep(0.135, 0.150, r)
    col = T.mix(col, _c("#080706") * np.ones_like(col), pupil_m)
    height = np.clip(1 - r, 0, 1) * 0.3
    rough = np.full((size, size), 0.08, np.float32)
    T.save_pbr_set(out, np.clip(col, 0, 1), height.astype(np.float32), rough, normal_strength=0.6)


@texture("npc_ripstop", size=1024, seed=1221)
def npc_ripstop(size: int, seed: int, out) -> None:
    """Issue ripstop cotton (neutral, tinted olive / khaki per material): a fine twill with the
    reinforcing grid every few millimetres, faded along the ridges, only faint wear (kept clean by
    someone who still does laundry, unlike the Hollowed's drill)."""
    y, x = np.mgrid[0:size, 0:size].astype(np.float32) / size
    count = 180
    weave = T.normalize(0.75 * (0.5 + 0.5 * np.cos((x + y) * count * 2 * np.pi))
                        + 0.25 * (0.5 + 0.5 * np.cos(x * count * 2 * np.pi)))
    cells = 48
    gx = np.abs(((x * cells) % 1.0) - 0.5)
    gy = np.abs(((y * cells) % 1.0) - 0.5)
    grid = np.maximum(T.smoothstep(0.43, 0.49, gx), T.smoothstep(0.43, 0.49, gy))
    slub = T.spectral(size, 1.1, seed + 1, anisotropy=(7.0, 1.0))
    col = T.gradient(T.normalize(0.7 * T.spectral(size, 2.3, seed + 2) + 0.3 * slub),
                     [(0.0, "#9c9c96"), (0.5, "#aaaaa4"), (1.0, "#b6b5ae")])
    col *= (1.0 + 0.06 * grid)[..., None]
    worn = T.smoothstep(0.6, 0.92, T.spectral(size, 2.0, seed + 3))
    col = T.mix(col, _c("#c8c6bc") * np.ones_like(col), worn * 0.25 * (0.5 + 0.5 * weave))
    stain = T.smoothstep(0.7, 0.9, T.spectral(size, 2.2, seed + 4)) * 0.25
    col = T.mix(col, _c("#5a5244") * np.ones_like(col), stain * 0.5)
    height = T.normalize(0.6 * weave + 0.25 * grid + 0.15 * slub)
    rough = np.clip(0.82 - 0.04 * grid + 0.05 * stain, 0.5, 1.0)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=3.0)


@texture("npc_hair", size=1024, seed=1231)
def npc_hair(size: int, seed: int, out) -> None:
    """Clean, short, grizzled hair and beard (strands along V): mid brown going grey, lighter and
    drier than the Hollowed's matted hair."""
    strands = T.spectral(size, 0.9, seed, anisotropy=(40.0, 1.0))
    clumps = T.spectral(size, 1.6, seed + 1, anisotropy=(6.0, 1.0))
    s = T.normalize(0.65 * strands + 0.35 * clumps)
    col = T.gradient(s, [(0.0, "#2a2018"), (0.5, "#4a3a2c"), (0.85, "#6a5846"), (1.0, "#8a7a68")])
    grey = T.smoothstep(0.62, 0.9, T.spectral(size, 0.6, seed + 2, anisotropy=(30.0, 1.0)))
    col = T.mix(col, _c("#a8a49c") * np.ones_like(col), grey * 0.6)
    height = s
    rough = np.clip(0.55 + 0.3 * (1 - s), 0.4, 0.95)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=2.5)


@texture("ezra_hair", size=1024, seed=1241)
def ezra_hair(size: int, seed: int, out) -> None:
    """Ezra Vane's hair and beard (ADR-0058; strands along V): an older man's, mostly grey going
    white, a few darker strands left, coarse and dry."""
    strands = T.spectral(size, 0.9, seed, anisotropy=(40.0, 1.0))
    clumps = T.spectral(size, 1.6, seed + 1, anisotropy=(6.0, 1.0))
    s = T.normalize(0.65 * strands + 0.35 * clumps)
    col = T.gradient(s, [(0.0, "#4a4640"), (0.4, "#7c7870"), (0.8, "#a8a49c"), (1.0, "#cfcbc2")])
    dark = T.smoothstep(0.7, 0.92, T.spectral(size, 0.6, seed + 2, anisotropy=(30.0, 1.0)))
    col = T.mix(col, _c("#3a3229") * np.ones_like(col), dark * 0.5)
    height = s
    rough = np.clip(0.6 + 0.3 * (1 - s), 0.45, 0.95)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=2.5)
