"""Player-built structure surfaces (ADR-0035, base-building fidelity): the bark, axe-cut end grain
and hewn wood of the building log (structures/log_piece and everything built from it).

The bark's plates are a periodic anisotropic Worley field defined in metres (one tile = 1 m around
x 1 m along the log). The log generator (blender/generators/structure_logs.py) evaluates the SAME
field at its vertices (same seed, point list, warp and metric: keep `bark_cells` in sync with
structure_logs.BARK_*) and displaces them, so the geometric ridges and furrows sit exactly under
the plates and fissures painted here.

Materials: game/data/materials/structures.json (struct_* ids)."""
from __future__ import annotations

import math
import random

import numpy as np
from scipy.spatial import cKDTree

from .. import texlib as T
from ..registry import texture

# Shared with structure_logs.py (bark_field): change both together.
BARK_SEED = 3517
BARK_CELLS = 34
BARK_STRETCH = 4.2


def bark_points() -> np.ndarray:
    r = random.Random(BARK_SEED)
    return np.array([(r.random(), r.random()) for _ in range(BARK_CELLS)], np.float64)


def bark_warp(u: np.ndarray, v: np.ndarray):
    tau = 2.0 * math.pi
    uw = u + 0.007 * np.sin(tau * (1.0 * v + 3.0 * u) + 1.3) + 0.005 * np.sin(tau * (4.0 * v - 5.0 * u) + 0.4)
    vw = v + 0.030 * np.sin(tau * (3.0 * u + v) + 2.1)
    return uw, vw


def bark_cells(u: np.ndarray, v: np.ndarray):
    """(gap, cell id, cross) at tile coords u (around) / v (along): gap = F2 - F1 in metres (0 on a
    fissure); cross = 1 where the furrow runs round the log (between plates one above the other),
    which the bark bridges over (shallow), 0 for the long furrows."""
    pts = bark_points()
    uw, vw = bark_warp(u, v)
    uw, vw = uw % 1.0, vw % 1.0
    S = BARK_STRETCH
    tiled = np.concatenate([pts + np.array([dx, dy]) for dx in (-1, 0, 1) for dy in (-1, 0, 1)])
    tiled[:, 1] /= S
    ids = np.tile(np.arange(len(pts)), 9)
    tree = cKDTree(tiled)
    d, idx = tree.query(np.stack([uw.ravel(), vw.ravel() / S], -1), k=2)
    sep = tiled[idx[:, 1]] - tiled[idx[:, 0]]
    du, dv = np.abs(sep[:, 0]), np.abs(sep[:, 1])          # in the metric space: the furrow is normal to sep
    cross = np.clip((dv / np.maximum(np.hypot(du, dv), 1e-9) - 0.55) / 0.35, 0.0, 1.0)
    return ((d[:, 1] - d[:, 0]).reshape(u.shape), ids[idx[:, 0]].reshape(u.shape), cross.reshape(u.shape))


def _uv(size: int):
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float64)
    return (xx + 0.5) / size, (yy + 0.5) / size


def _c(h: str) -> np.ndarray:
    return T.hex_rgb(h)[None, None, :]


def _cell_rand(cid: np.ndarray, salt: float) -> np.ndarray:
    return ((np.sin(cid * 12.9898 + salt * 78.233) * 43758.5453) % 1.0).astype(np.float32)


def _save(out, albedo, height, rough, *, ns: float, ao=None) -> None:
    base = out
    T.save_rgb(base.with_name(base.name + "_albedo.png"), np.clip(albedo, 0, 1))
    T.save_rgb(base.with_name(base.name + "_normal.png"), T.height_to_normal(T.normalize(height), ns))
    if ao is None:
        ao = T.cavity_ao(T.normalize(height))
    T.save_orm(base.with_name(base.name + "_orm.png"), np.clip(ao, 0, 1), np.clip(rough, 0.02, 1.0), 0.0)


def _flakes(size: int, points: int, seed: int, stretch_u: float, warp: float = 0.0):
    """Periodic Worley whose cells are `stretch_u` times wider (U) than tall: the overlapping scales
    on a plate. Returns F1, F2 (pixels, in the stretched metric) and cell id."""
    r = T.rng(seed)
    pts = r.random((points, 2)) * size
    tiled = np.concatenate([pts + np.array([dx, dy]) * size for dx in (-1, 0, 1) for dy in (-1, 0, 1)])
    tiled[:, 0] /= stretch_u
    ids = np.tile(np.arange(points), 9)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float64)
    if warp > 0:
        xx = (xx + (T.spectral(size, 1.6, seed + 1) - 0.5) * 2 * warp) % size
        yy = (yy + (T.spectral(size, 1.6, seed + 2) - 0.5) * 2 * warp) % size
    d, idx = cKDTree(tiled).query(np.stack([(xx.ravel() + 0.5) / stretch_u, yy.ravel() + 0.5], -1), k=2)
    return (d[:, 0].reshape(size, size).astype(np.float32), d[:, 1].reshape(size, size).astype(np.float32),
            ids[idx[:, 0]].reshape(size, size))


@texture("struct_log_bark", size=2048, seed=3517)
def struct_log_bark(size, seed, out):
    """Thick conifer bark on a felled building log: long plates (grey-brown weathered crowns built of
    overlapping scales) split by deep, ragged furrows with crumbly cinnamon cork walls and near-black
    bottoms, short cross-checks, soot/wet stains, resin and sparse pale lichen. Tile 1 m; V along the
    log. The plate layout is bark_cells() (shared with the mesh); the ragged detail is texture only."""
    u, v = _uv(size)
    # small warp: ragged furrow paths, still within a centimetre or two of the mesh's furrows
    wu = (T.spectral(size, 1.7, seed + 20) - 0.5) * 0.012
    wv = (T.spectral(size, 1.7, seed + 21) - 0.5) * 0.03
    gap, cid, cross = bark_cells(u + wu, v + wv)
    gap = gap.astype(np.float32)
    cross = T.blur(cross.astype(np.float32), 6.0)
    bridge = 0.75 * cross * cross * (3 - 2 * cross)
    rnd = _cell_rand(cid, 1.0)
    rnd2 = _cell_rand(cid, 2.0)
    rag = (T.spectral(size, 1.05, seed + 1) - 0.5) * 0.016
    g = np.maximum(gap + rag, 0.0)
    width = 0.018 + 0.014 * rnd2                          # furrow half-width varies per plate
    plate = T.smoothstep(0.0, 1.0, np.clip(g / width, 0, 1))
    plate = plate + (1.0 - plate) * bridge                # cross-furrows: the ridge bridges over
    bottom = 1.0 - T.smoothstep(0.0, 0.25, g / width)
    crown = np.maximum(T.smoothstep(0.7, 1.6, g / width), bridge * 0.8)
    # scales on the crowns
    f1, f2, fid = _flakes(size, 2600, seed + 2, 2.4, warp=size * 0.012)
    frnd = _cell_rand(fid, 3.0)
    fedge = (1.0 - T.smoothstep(0.0, 3.5, f2 - f1)) * T.smoothstep(0.35, 0.65, T.spectral(size, 1.2, seed + 14))
    fdome = 1.0 - np.clip(f1 / 20.0, 0, 1)
    # scale tops tilt: lower edge proud (gravity-free here, but reads as layered flakes)
    scale_h = 0.35 * frnd + 0.3 * fdome - 0.35 * fedge
    # cross-checks through some plates
    chk = T.spectral(size, 1.3, seed + 3, anisotropy=(1.0, 7.0), fmin=4.0)
    checks = (1.0 - T.smoothstep(0.0, 0.03, np.abs(chk - 0.5))) * T.smoothstep(0.62, 0.75, T.spectral(size, 1.8, seed + 4)) * crown
    coarse = T.spectral(size, 2.3, seed + 5)
    mid = T.spectral(size, 1.3, seed + 6, anisotropy=(1.0, 2.0))
    fine = T.spectral(size, 0.8, seed + 7)
    crumb = T.spectral(size, 0.9, seed + 8)
    height = (plate * (0.55 + 0.2 * rnd2) + crown * (0.16 * scale_h + 0.05 * mid) + (1 - crown) * plate * 0.06 * crumb
              - 0.2 * checks + 0.05 * coarse + 0.03 * fine)
    height = T.normalize(height)
    # colours
    deep = T.gradient(crumb, [(0.0, "#0b0705"), (1.0, "#1d120c")])
    cork = T.gradient(np.clip(0.6 * crumb + 0.4 * fine, 0, 1), [(0.0, "#241912"), (0.5, "#42291c"), (1.0, "#5a3826")])
    cork *= (0.75 + 0.35 * plate)[..., None]
    crown_c = T.gradient(np.clip(0.45 * coarse + 0.35 * mid + 0.2 * fine, 0, 1),
                         [(0.0, "#2c2723"), (0.35, "#443d37"), (0.7, "#5c544c"), (1.0, "#746a60")])
    crown_c *= (0.82 + 0.3 * rnd)[..., None] * (0.9 + 0.16 * frnd)[..., None]
    crown_c *= (1.0 - 0.3 * fedge)[..., None]
    # where a scale broke off: the fresher reddish layer below
    fresh = (frnd > 0.92) * T.smoothstep(0.5, 0.7, T.spectral(size, 1.5, seed + 9))
    crown_c = T.mix(crown_c, np.ones_like(crown_c) * _c("#6e4430"), fresh * 0.5 * (1 - fedge))
    alb = T.mix(deep, cork, T.smoothstep(0.1, 0.45, plate))
    alb = T.mix(alb, crown_c, T.smoothstep(0.55, 0.95, plate))
    alb = T.mix(alb, alb * 0.35, checks)
    stain = T.smoothstep(0.6, 0.85, T.spectral(size, 2.0, seed + 10, anisotropy=(1.0, 3.0)))
    alb *= (1.0 - 0.3 * stain)[..., None]
    resin = T.smoothstep(0.88, 0.94, T.spectral(size, 1.1, seed + 11)) * (1 - crown) * plate
    alb = T.mix(alb, np.ones_like(alb) * _c("#8a5a1c"), resin * 0.7)
    lich = T.smoothstep(0.76, 0.83, T.spectral(size, 1.25, seed + 12)) * crown
    lich *= T.smoothstep(0.4, 0.6, T.spectral(size, 0.7, seed + 13))
    alb = T.mix(alb, np.ones_like(alb) * _c("#8f977c"), lich * 0.7)
    height = T.normalize(height + 0.03 * lich)
    rough = np.clip(0.93 - 0.06 * crown * frnd - 0.25 * resin + 0.04 * bottom, 0, 1)
    ao = np.clip(T.cavity_ao(height, radius=14, strength=1.6) * (0.25 + 0.75 * plate ** 0.6), 0, 1)
    _save(out, alb, height, rough, ns=14.0, ao=ao)


@texture("struct_log_end", size=1024, seed=3518)
def struct_log_end(size, seed, out):
    """Axe-cut end grain, mapped as a disc (centre 0.5, rim radius 0.46 = the chamfer's inner edge):
    growth rings round an off-centre pith, pale sapwood near the rim, drying checks, the faceted
    scallops of the axe strokes and a sooty, weathered film."""
    u, v = _uv(size)
    x, y = (u - 0.5) / 0.46, (v - 0.5) / 0.46
    pc = (0.06, -0.04)
    dx, dy = x - pc[0], y - pc[1]
    warp = (T.spectral(size, 2.2, seed) - 0.5)
    rad = np.sqrt(dx * dx + dy * dy) + warp * 0.05
    radn = np.sqrt(x * x + y * y)
    ang = np.arctan2(dy, dx)
    rings_n = 34
    rr = rad * rings_n * (1.0 + 0.15 * rad) + (T.spectral(size, 2.5, seed + 1) - 0.5) * 1.6
    rf = rr - np.floor(rr)
    late = T.smoothstep(0.65, 0.9, rf) * (1 - T.smoothstep(0.93, 1.0, rf))
    col = T.gradient(np.clip(radn, 0, 1), [(0.0, "#6e4628"), (0.4, "#86603c"), (0.62, "#97724c"), (0.78, "#a8845c"),
                                            (1.0, "#9c7e58")])
    col = T.mix(col, col * 0.62, late * 0.85)
    pith = np.clip(1 - rad / 0.035, 0, 1)
    col = T.mix(col, np.ones_like(col) * _c("#4a2f1a"), pith)
    # heartwood/sapwood boundary: slightly darker band
    hb = T.smoothstep(0.08, 0.0, np.abs(radn - 0.66))
    col = T.mix(col, col * 0.86, hb * 0.6)
    # drying checks from the rim inward
    r = T.rng(seed + 2)
    checks = np.zeros((size, size), np.float32)
    for k in range(7):
        a0 = r.uniform(-math.pi, math.pi)
        da = np.abs(((ang - a0 + math.pi) % (2 * math.pi)) - math.pi)
        width = 0.002 + 0.012 * np.clip(radn, 0, 1) * (1.4 if k < 2 else 0.7)
        reach = r.uniform(0.15, 0.55) if k < 2 else r.uniform(0.5, 0.85)
        checks = np.maximum(checks, np.clip(1 - da / np.maximum(width, 1e-4), 0, 1) * T.smoothstep(reach - 0.08, reach + 0.12, radn))
    col *= (1 - 0.8 * checks)[..., None]
    # axe scallops: two strike directions, each a train of shallow concave facets with crisp ridges
    sc = np.zeros((size, size), np.float32)
    ridge = np.zeros((size, size), np.float32)
    for ax_ang, pitch, ph in ((0.35, 7.5, 0.2), (-0.45, 6.0, 0.6)):
        t = (x * math.cos(ax_ang) + y * math.sin(ax_ang)) * pitch + ph + (T.spectral(size, 2.4, seed + 3) - 0.5) * 0.8
        f = (t - np.floor(t)).astype(np.float32)
        half = (y * math.cos(ax_ang) - x * math.sin(ax_ang)) > (-0.1 if ax_ang > 0 else 0.15)
        sc = np.where(half, f * f, sc)
        ridge = np.where(half, T.smoothstep(0.93, 1.0, f), ridge)
    col *= (0.9 + 0.12 * sc - 0.1 * ridge)[..., None]
    # weathering: soot, grey and dirt toward the rim
    grey = T.levels(T.spectral(size, 1.8, seed + 4), 0.45, 0.95)
    col = T.mix(col, np.ones_like(col) * _c("#7a7268"), grey * 0.35)
    dirt = T.smoothstep(0.7, 1.0, radn) * T.levels(T.spectral(size, 1.4, seed + 5), 0.3, 0.9)
    col = T.mix(col, col * 0.6, dirt * 0.6)
    fine = T.spectral(size, 0.8, seed + 6)
    col *= 0.86
    height = T.normalize(0.35 * late + 0.35 * sc - 0.25 * ridge - 1.4 * checks + 0.12 * fine)
    rough = np.clip(0.84 + 0.1 * checks + 0.05 * fine, 0, 1)
    _save(out, col, height, rough, ns=4.0)


@texture("struct_log_hewn", size=1024, seed=3519)
def struct_log_hewn(size, seed, out):
    """Axe-hewn / riven softwood (notches, chamfers, split-log faces): torn fibres along U, the
    shallow scallops of axe bites across them with crisp step edges, grey weathering and grime.
    Tile 0.5 m."""
    u, v = _uv(size)
    grain = T.spectral(size, 1.8, seed, anisotropy=(1.0, 14.0))
    fib = T.spectral(size, 0.6, seed + 1, anisotropy=(1.0, 22.0))
    torn = T.spectral(size, 1.2, seed + 2, anisotropy=(1.0, 8.0))
    lines = 0.5 + 0.5 * np.sin(v * 2 * math.pi * 34 + (grain - 0.5) * 5)
    late = T.smoothstep(0.7, 0.95, lines)
    # axe bites: scallops along U (6 per tile), wavy, each with a sharp leading step
    wob = (T.spectral(size, 2.2, seed + 3) - 0.5) * 0.45
    t = (u * 6.0 + 0.25 * np.sin(2 * math.pi * v) + wob)
    f = (t - np.floor(t)).astype(np.float32)
    scallop = f * f
    step = T.smoothstep(0.95, 1.0, f)
    col = T.gradient(T.normalize(0.5 * grain + 0.3 * fib + 0.2 * torn), [(0.0, "#6e5238"), (0.5, "#8c6c4a"), (1.0, "#a6865e")])
    col = T.mix(col, col * 0.75, late * 0.7)
    col *= (0.9 + 0.14 * scallop - 0.18 * step)[..., None]
    weather = T.levels(T.spectral(size, 1.9, seed + 4), 0.4, 0.95)
    col = T.mix(col, np.ones_like(col) * _c("#77695c"), weather * 0.45)
    grime = T.levels(T.spectral(size, 1.6, seed + 5), 0.5, 1.0)
    col *= (1 - 0.2 * grime)[..., None]
    height = T.normalize(0.45 * scallop - 0.3 * step + 0.3 * fib + 0.2 * late + 0.15 * torn)
    rough = np.clip(0.8 + 0.12 * fib, 0, 1)
    _save(out, col, height, rough, ns=5.0)
