"""Rock finishes for the POI kit: mine drifts and natural caves (the Corvane Mining Co.'s Larkspur
Exploration Adit and the limestone cave its tunnels broke into).

These are extra slices of the kit finish arrays built in textures/gen/kit.py (appended after the house
finishes, never reordered: game/data/materials/kit_finishes.json is the contract):
  wall  rock_drift       blasted grey-brown granite: angular blast facets, fracture edges, the half-barrels
                         of drill holes, iron-stain and seep streaks; rough and dark
  wall  rock_limestone   pale wet limestone: solution pockets, faint bedding, cream flowstone curtains
  floor rock_floor       broken rock and gravel, fines between the stones, mud lying in the low ground
  floor cave_mud         wet clay mud, smeared and dimpled, with standing puddles (glossy)
Walls tile every 1 m, floors every 2 m (kit_wall.gdshader projects them in world space). Ceilings take a
WALL finish by name, so the two walls double as drift / cave ceilings. Nothing here is big or distinctive
enough to read as a repeat at that scale: features are many and small (facets 5-30 cm, stones 2-15 cm), the
drill barrels are short segments at irregular spacing, and the shader's macro tone and decay masks break
the rest.

The same functions feed the props' own rock textures (textures/gen/mine.py: mine_rock_drift,
mine_limestone) so the rock-face props match the kit walls they stand against.

Every function returns a RockFinish (duck-typed like kit.Finish: albedo sRGB float HxWx3, height [0,1],
roughness, metal, normal_strength, ao_strength) and is tileable and deterministic for (size, seed). This
module imports only texlib: kit.py imports it at load time.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

from .. import texlib as T

ROCK_WALL_FINISHES = ["rock_drift", "rock_limestone"]
ROCK_FLOOR_FINISHES = ["rock_floor", "cave_mud"]


@dataclass
class RockFinish:
    albedo: np.ndarray
    height: np.ndarray
    rough: np.ndarray
    metal: np.ndarray | float = 0.0
    normal_strength: float = 4.0
    ao_strength: float = 1.0


# =================================================================================================
# helpers (all periodic over the tile)
# =================================================================================================

def _coords(size: int, tile: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """Pixel-centre coordinates in metres (x right, y down the image = down a wall)."""
    c = (np.arange(size, dtype=np.float32) + 0.5) / size * tile
    return c[None, :].repeat(size, 0), c[:, None].repeat(size, 1)


def _col(h: str) -> np.ndarray:
    return T.hex_rgb(h)[None, None, :].astype(np.float32)


def _fill(size: int, h: str) -> np.ndarray:
    return np.ones((size, size, 3), np.float32) * _col(h)


def _sn(size: int, beta: float, seed: int, aniso=(1.0, 1.0), fmin: float = 1.0) -> np.ndarray:
    return T.spectral(size, beta, seed, anisotropy=aniso, fmin=fmin).astype(np.float32)


def _hash_arr(k, salt: int) -> np.ndarray:
    """Deterministic pseudo-random [0,1) per integer."""
    x = (np.asarray(k).astype(np.uint64) * np.uint64(0x9E3779B1) + np.uint64((salt * 0x85EBCA6B) & 0xFFFFFFFF))
    x &= np.uint64(0xFFFFFFFF)
    x ^= x >> np.uint64(15)
    x = (x * np.uint64(0x2C1B3C6D)) & np.uint64(0xFFFFFFFF)
    x ^= x >> np.uint64(12)
    x = (x * np.uint64(0x297A2D39)) & np.uint64(0xFFFFFFFF)
    x ^= x >> np.uint64(15)
    return ((x & np.uint64(0xFFFFFF)).astype(np.float64) / float(0x1000000)).astype(np.float32)


def _cells(size: int, points: int, seed: int, jitter: float = 0.85, aspect: tuple[float, float] = (1.0, 1.0)):
    """Tileable Voronoi cells with the offset of every pixel from its cell's feature point.
    Returns (F1, F2, cell id, dx, dy) with distances / offsets in pixels. aspect stretches the metric
    (e.g. (1, 0.6) makes cells taller than wide)."""
    r = T.rng(seed)
    g = int(np.ceil(np.sqrt(points)))
    base = np.stack(np.meshgrid(np.arange(g), np.arange(g)), -1).reshape(-1, 2)[:points].astype(np.float64)
    pts = (base + 0.5 + (r.random((points, 2)) - 0.5) * jitter) * (size / g)
    pts %= size
    ax, ay = aspect
    tiled = np.concatenate([pts + np.array([dx, dy]) * size for dx in (-1, 0, 1) for dy in (-1, 0, 1)])
    ids = np.tile(np.arange(points), 9)
    tree = cKDTree(tiled * np.array([ax, ay]))
    yy, xx = np.mgrid[0:size, 0:size]
    q = np.stack([xx.ravel() + 0.5, yy.ravel() + 0.5], -1)
    d, idx = tree.query(q * np.array([ax, ay]), k=2)
    near = tiled[idx[:, 0]]
    f1 = d[:, 0].reshape(size, size).astype(np.float32)
    f2 = d[:, 1].reshape(size, size).astype(np.float32)
    cid = ids[idx[:, 0]].reshape(size, size)
    ox = (q[:, 0] - near[:, 0]).reshape(size, size).astype(np.float32)
    oy = (q[:, 1] - near[:, 1]).reshape(size, size).astype(np.float32)
    return f1, f2, cid, ox, oy


def _facets(size: int, points: int, seed: int, slope: float, aspect=(1.0, 1.0)):
    """Blast facets: every cell is a tilted plane at its own level (broken planes meeting in sharp
    ridges and steps). Returns (height, edge distance F2-F1 in px, cell id)."""
    f1, f2, cid, ox, oy = _cells(size, points, seed, aspect=aspect)
    sx = (_hash_arr(cid, seed + 1) - 0.5) * 2.0
    sy = (_hash_arr(cid, seed + 2) - 0.5) * 2.0
    lvl = _hash_arr(cid, seed + 3)
    cell_px = size / np.sqrt(points)
    h = lvl * 0.6 + (sx * ox + sy * oy) / cell_px * slope
    return h.astype(np.float32), (f2 - f1).astype(np.float32), cid


def _wrap(d: np.ndarray, period: float) -> np.ndarray:
    """Signed periodic difference in [-period/2, period/2)."""
    return (d + period * 0.5) % period - period * 0.5


def _blur(a: np.ndarray, s: float) -> np.ndarray:
    return ndimage.gaussian_filter(a, s, mode="wrap").astype(np.float32)


def _drill_barrels(size: int, seed: int, tile: float, n: int):
    """Half-barrels of blast holes on a drift wall: short vertical grooves (38 mm bits) left where the
    round broke along the hole, at irregular spacing and slight angles, each with the bit's rifling.
    Returns (depth 0..1 inside the groove, groove mask, rifling)."""
    x, y = _coords(size, tile)
    r = T.rng(seed)
    depth = np.zeros((size, size), np.float32)
    rifle = np.zeros((size, size), np.float32)
    # Spread the holes over the tile so no two line up (a drilled round: holes ~25-45 cm apart).
    xs = (np.arange(n) + r.uniform(0.15, 0.85, n)) / n * tile
    for k in range(n):
        x0 = float(xs[k])
        y0 = float(r.uniform(0, tile))
        length = float(r.uniform(0.28, 0.6))
        rad = float(r.uniform(0.017, 0.021))
        tilt = float(r.uniform(-0.12, 0.12))
        dy = (y - y0) % tile                        # along the hole
        xc = x0 + tilt * dy
        dx = _wrap(x - xc, tile)
        t = np.clip(np.abs(dx) / rad, 0.0, 1.0)
        prof = np.sqrt(np.clip(1.0 - t * t, 0.0, 1.0))
        # ends fade out raggedly (the barrel breaks out of the face)
        ends = T.smoothstep(0.0, 0.06, dy) * (1.0 - T.smoothstep(length - 0.08, length, dy))
        g = prof * ends * (np.abs(dx) < rad)
        depth = np.maximum(depth, g.astype(np.float32))
        rifle = np.maximum(rifle, (g > 0.05) * (0.5 + 0.5 * np.cos(dy * 2 * np.pi / 0.021 + dx * 40.0)))
    mask = (depth > 0.02).astype(np.float32)
    return depth, mask, rifle.astype(np.float32)


# =================================================================================================
# walls (1 m per tile)
# =================================================================================================

def rock_drift(size: int, seed: int) -> RockFinish:
    """Blasted granite drift wall: grey-brown, dark, rough; angular facets at two scales, pale fresh
    fracture edges, drill-hole half-barrels, iron-stain streaks and dark seeps running down."""
    big, big_e, big_id = _facets(size, 18, seed + 1, 0.8, aspect=(1.0, 0.8))
    mid, mid_e, mid_id = _facets(size, 52, seed + 2, 0.7)
    small, small_e, _ = _facets(size, 220, seed + 3, 0.5)
    grain = _sn(size, 1.0, seed + 4)
    bumps = _sn(size, 1.9, seed + 5)
    h = 0.4 * big + 0.32 * mid + 0.1 * small + 0.08 * bumps + 0.04 * grain
    h = _blur(h, 1.2)
    # fresh fracture ridges / steps between facets: slightly raised lips that chip pale
    edge_big = 1.0 - T.smoothstep(0.0, 5.0, big_e)
    edge_mid = 1.0 - T.smoothstep(0.0, 3.0, mid_e)
    barrels, bmask, rifle = _drill_barrels(size, seed + 6, 1.0, 3)
    h = h - 0.12 * barrels + 0.01 * rifle * bmask
    height = T.normalize(h)

    # colour: granite (grey-brown groundmass, pink-grey feldspar, black biotite, glassy quartz)
    tone = T.normalize(0.55 * T.normalize(big + 0.5 * mid) + 0.25 * bumps + 0.2 * _sn(size, 2.4, seed + 7))
    col = T.gradient(tone, [(0.0, "#2f2b27"), (0.35, "#463f39"), (0.7, "#5b534b"), (1.0, "#6e665d")])
    col *= (0.9 + 0.2 * _hash_arr(mid_id, seed + 8))[..., None]
    spk = _sn(size, 0.25, seed + 9)
    spk2 = _sn(size, 0.25, seed + 10)
    spk3 = _sn(size, 0.3, seed + 11)
    col = T.mix(col, _fill(size, "#7f6f63"), T.smoothstep(0.66, 0.74, spk) * 0.55)    # feldspar
    col = T.mix(col, _fill(size, "#141312"), T.smoothstep(0.7, 0.78, spk2) * 0.7)     # biotite
    col = T.mix(col, _fill(size, "#8d8b86"), T.smoothstep(0.78, 0.84, spk3) * 0.45)   # quartz
    # fresh broken edges and the dust-polished drill barrels read paler
    col = T.mix(col, _fill(size, "#7a7268"), np.clip(edge_big * 0.3 + edge_mid * 0.12, 0, 1))
    col = T.mix(col, _fill(size, "#625c55"), bmask * 0.2)
    col *= (1.0 - 0.18 * (barrels ** 2) * bmask)[..., None]        # the groove's shaded floor
    # iron staining and seeps run DOWN the wall (image rows = down): vertically stretched noise
    iron = T.smoothstep(0.62, 0.86, _sn(size, 1.5, seed + 12, (7.0, 1.0))) * T.smoothstep(0.4, 0.7, _sn(size, 2.2, seed + 13))
    col = T.mix(col, col * 0.55 + _col("#5e3a20") * 0.45, iron * 0.7)
    seep = T.smoothstep(0.66, 0.9, _sn(size, 1.7, seed + 14, (9.0, 1.0)))
    col *= (1.0 - 0.35 * seep)[..., None]
    # blast soot in hollows
    hollow = 1.0 - T.smoothstep(0.25, 0.5, height)
    col *= (1.0 - 0.25 * hollow)[..., None]
    rough = np.clip(0.9 + 0.05 * grain - 0.3 * seep - 0.12 * bmask - 0.05 * edge_big, 0, 1)
    return RockFinish(np.clip(col, 0, 1), height, rough, normal_strength=9.0, ao_strength=1.6)


def rock_limestone(size: int, seed: int) -> RockFinish:
    """Pale wet cave limestone: smooth rounded relief, solution pockets, faint bedding, cream-to-tan
    flowstone curtains running down (glossy wet) and white moonmilk spots."""
    x, y = _coords(size, 1.0)
    relief = _sn(size, 2.3, seed + 1)
    lumps = _sn(size, 1.6, seed + 2)
    f1, f2, cid, _, _ = _cells(size, 34, seed + 3, aspect=(1.0, 0.75))
    sel = (_hash_arr(cid, seed + 4) < 0.45).astype(np.float32)
    rad = size / np.sqrt(34) * (0.25 + 0.2 * _hash_arr(cid, seed + 5))
    pocket = (1.0 - T.smoothstep(0.0, 1.0, f1 / rad)) ** 1.5 * sel
    # bedding: gently wavy horizontal partings (3 per metre keeps the tile periodic)
    wav = (_sn(size, 2.4, seed + 6) - 0.5) * 0.08
    bed_ph = ((y + wav) * 3.0) % 1.0
    bedding = (1.0 - T.smoothstep(0.0, 0.025, np.abs(bed_ph - 0.5))) * T.smoothstep(0.4, 0.65, _sn(size, 2.0, seed + 7))
    # flowstone: curtains of calcite draping down, with fine ridged runnels
    drape = _sn(size, 1.7, seed + 8, (8.0, 1.0))
    cover = T.smoothstep(0.45, 0.75, _sn(size, 2.4, seed + 9))
    flow = T.smoothstep(0.5, 0.72, drape) * cover
    runnels = _sn(size, 1.1, seed + 10, (14.0, 1.0))
    h = 0.45 * relief + 0.25 * lumps - 0.2 * pocket - 0.06 * bedding + flow * (0.18 + 0.1 * runnels)
    height = T.normalize(_blur(h, 1.0))

    tone = T.normalize(0.5 * relief + 0.3 * lumps + 0.2 * _sn(size, 0.9, seed + 11))
    col = T.gradient(tone, [(0.0, "#8f897d"), (0.4, "#a8a194"), (0.75, "#bdb6a8"), (1.0, "#cbc4b5")])
    col = T.mix(col, _fill(size, "#8f877a"), pocket * 0.25)                 # damp, dirty pockets
    col *= (1.0 - 0.08 * bedding)[..., None]
    fcol = T.gradient(runnels, [(0.0, "#a98d63"), (0.5, "#c3a77b"), (1.0, "#d6c29c")])
    col = T.mix(col, fcol, flow * 0.85)
    stain = T.smoothstep(0.7, 0.92, _sn(size, 1.4, seed + 12, (10.0, 1.0))) * (0.4 + 0.6 * cover)
    col = T.mix(col, col * 0.6 + _col("#6b4f2f") * 0.4, stain * 0.5)      # iron / clay streaks
    milk = T.smoothstep(0.78, 0.86, _sn(size, 1.2, seed + 13)) * (1.0 - flow)
    col = T.mix(col, _fill(size, "#ddd8cc"), milk * 0.6)                   # moonmilk
    wet = T.smoothstep(0.35, 0.75, _sn(size, 2.2, seed + 14, (4.0, 1.0)))
    col *= (1.0 - 0.18 * wet)[..., None]
    rough = np.clip(0.55 - 0.25 * flow - 0.2 * wet + 0.25 * milk + 0.1 * pocket, 0.08, 1)
    return RockFinish(np.clip(col, 0, 1), height, rough, normal_strength=6.0, ao_strength=1.3)


# =================================================================================================
# floors (2 m per tile)
# =================================================================================================

def rock_floor(size: int, seed: int) -> RockFinish:
    """Drift floor: broken rock and gravel (round-edged stones 2-8 cm, angular rock 10-20 cm), dark fines
    between them, and wet mud lying in the low ground (the stones that stand proud poke through)."""
    tile = 2.0
    # gravel: domed stones of two sizes
    g1, g2, gid, _, _ = _cells(size, 1400, seed + 1, jitter=1.0)
    gr = size / np.sqrt(1400)
    stone = T.smoothstep(0.0, gr * 0.35, g2 - g1) * (_hash_arr(gid, seed + 2) < 0.5)
    dome = np.sqrt(np.clip(stone, 0, 1))
    f1, f2, fid, _, _ = _cells(size, 260, seed + 3, jitter=1.0)
    fr = size / np.sqrt(260)
    coarse = T.smoothstep(0.0, fr * 0.3, f2 - f1) * (_hash_arr(fid, seed + 4) < 0.35)
    # angular broken rock: faceted cells, a few per square metre
    rk, rk_e, rk_id = _facets(size, 70, seed + 5, 0.6)
    rsel = (_hash_arr(rk_id, seed + 6) < 0.32).astype(np.float32)
    rock = T.smoothstep(1.0, 5.0, rk_e) * rsel
    fines = _sn(size, 1.2, seed + 7)
    h = 0.12 * fines + 0.22 * dome + 0.3 * np.maximum(coarse, dome * 0.5)
    h = h * (1.0 - rock) + rock * (0.55 + 0.35 * rk)
    stone = stone * (1.0 - rock)
    coarse = coarse * (1.0 - rock)
    # mud in the low ground (broad, low-frequency): fills to a level, stones above it stay dry
    low = _sn(size, 2.6, seed + 8)
    mud_lvl = 0.18 + 0.32 * T.smoothstep(0.42, 0.7, low)
    mud = T.smoothstep(-0.02, 0.04, mud_lvl - h)
    h = np.maximum(h, mud_lvl + 0.02 * _sn(size, 1.8, seed + 9))
    height = T.normalize(_blur(h, 0.8))

    gcol = T.gradient(_hash_arr(gid, seed + 10), [(0.0, "#4e4943"), (0.5, "#6a645b"), (0.8, "#7e776c"), (1.0, "#8d857a")])
    ccol = T.gradient(_hash_arr(fid, seed + 11), [(0.0, "#46423d"), (0.6, "#605a52"), (1.0, "#7a7166")])
    rcol = T.gradient(_hash_arr(rk_id, seed + 12), [(0.0, "#3e3934"), (0.5, "#544c45"), (1.0, "#6c645a")])
    col = _fill(size, "#2c2722") * (0.85 + 0.3 * fines)[..., None]                # fines / grit
    col = T.mix(col, gcol * (0.8 + 0.25 * dome)[..., None], np.clip(stone * 1.4, 0, 1))
    col = T.mix(col, ccol * (0.8 + 0.25 * coarse)[..., None], np.clip(coarse * 1.4, 0, 1))
    col = T.mix(col, rcol * (0.85 + 0.3 * rk)[..., None], rock)
    mcol = T.gradient(_sn(size, 1.6, seed + 13), [(0.0, "#2a2119"), (0.6, "#3a2d21"), (1.0, "#4a3a2a")])
    col = T.mix(col, mcol, mud * 0.92)
    # splashed mud film on the stones near it, wet dark rims
    film = T.smoothstep(0.0, 0.12, mud_lvl + 0.1 - h) * (1.0 - mud)
    col = T.mix(col, col * 0.7 + mcol * 0.3, film * 0.6)
    rough = np.clip(0.85 - 0.5 * mud - 0.15 * film + 0.05 * fines, 0.2, 1)
    return RockFinish(np.clip(col, 0, 1), height, rough, normal_strength=5.0, ao_strength=1.8)


def cave_mud(size: int, seed: int) -> RockFinish:
    """Wet cave clay: a smooth, smeared, dimpled surface (brown-ochre, darker where wetter), a few
    pebbles, faint drip pits, and puddles standing in the hollows with a glossy flat surface."""
    tile = 2.0
    base = _sn(size, 2.5, seed + 1)
    smear = _sn(size, 1.5, seed + 2, (1.0, 5.0))                  # dragged / slumped streaks
    dimple = _sn(size, 1.0, seed + 3)
    f1, f2, pid, _, _ = _cells(size, 300, seed + 4, jitter=1.0)
    pr = size / np.sqrt(300)
    pebble = T.smoothstep(0.0, pr * 0.25, f2 - f1) * (_hash_arr(pid, seed + 5) < 0.08)
    d1, d2, did, _, _ = _cells(size, 500, seed + 6, jitter=1.0)
    drip = (1.0 - T.smoothstep(0.0, 4.0, d1)) * (_hash_arr(did, seed + 7) < 0.3)  # drip pits under the roof
    h = 0.6 * base + 0.18 * smear + 0.06 * dimple + 0.25 * pebble - 0.08 * drip
    # puddles: water fills the hollows to a level that varies over the tile
    lvl = float(np.quantile(h, 0.2))
    pud = T.smoothstep(0.0, 0.012, lvl - h)
    hh = np.maximum(h, lvl)
    height = T.normalize(_blur(hh, 1.0))

    tone = T.normalize(0.5 * base + 0.3 * smear + 0.2 * _sn(size, 0.8, seed + 8))
    col = T.gradient(tone, [(0.0, "#3d2d1e"), (0.35, "#523d29"), (0.7, "#674e35"), (1.0, "#7a5e40")])
    ochre = T.smoothstep(0.6, 0.85, _sn(size, 2.0, seed + 9, (3.0, 1.0)))
    col = T.mix(col, _fill(size, "#7f6236"), ochre * 0.35)
    wet_rim = T.smoothstep(0.0, 0.08, lvl + 0.08 - h) * (1.0 - pud)  # darker, wetter clay round the water
    col *= (1.0 - 0.3 * wet_rim)[..., None]
    col = T.mix(col, T.gradient(_hash_arr(pid, seed + 10), [(0.0, "#3f3a33"), (1.0, "#5e574d")]), pebble * 0.7)
    col *= (1.0 - 0.25 * drip)[..., None]
    # standing water: dark, slightly grey-brown (it mirrors whatever light there is)
    water = col * 0.4 + _col("#1c1712") * 0.4
    col = T.mix(col, water, pud * 0.9)
    rough = np.clip(0.42 - 0.12 * wet_rim + 0.15 * pebble + 0.05 * dimple, 0, 1)
    rough = rough * (1.0 - pud) + 0.04 * pud
    return RockFinish(np.clip(col, 0, 1), height, np.clip(rough, 0.03, 1), normal_strength=3.0, ao_strength=1.2)


ROCK_FINISH_FNS = {f.__name__: f for f in (rock_drift, rock_limestone, rock_floor, cave_mud)}
_ORDER = ROCK_WALL_FINISHES + ROCK_FLOOR_FINISHES


def rock_finish(name: str, size: int, seed: int) -> RockFinish:
    """The finish `name` with its own seed offset (kit.py's house finishes keep theirs untouched)."""
    return ROCK_FINISH_FNS[name](size, seed + 7919 * (_ORDER.index(name) + 1) + 500)
