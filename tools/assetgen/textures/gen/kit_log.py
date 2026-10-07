"""Log wall finish for the POI kit (TD-236): `log_chinked`, bark-on logs stacked 4 to the metre with pale
lime chinking in the seams, for log buildings' exterior walls and gables (Elk Ridge Lodge, cabins).

It is an extra slice of the kit wall finish arrays built in textures/gen/kit.py (appended after the rock
finishes, never reordered: game/data/materials/kit_finishes.json is the contract). The courses match the
w3_lodge_shell log model (blender/generators/props_wild3.py: 0.25 m pitch, 0.165 m logs with 4 cm chinking
tubes) so the kit wall seen between and round the shell's logs, and the gables above them, read as the
same wall. The tone is the shell's tinted bark (w3_log_bark: bark_grey_fir x #e6c09a): mid grey-brown, so
the lodge no longer reads near-black at distance as the dark interior panelling did.

Features: per-course tone and a gentle wander of each log's edge (logs are not straight), bark fissures
running along the log, patches where the bark has sloughed to silver-grey checked wood, the shaded
underside of each log's curve, and chinking that is wider and cracked in places with a dark gap where it
has shrunk from the log above. Kit walls tile every 1 m (kit_wall.gdshader projects in world space).

Like kit_rock.py, the function has its own seed offset, so kit.py's house finishes keep theirs. This
module imports only texlib: kit.py imports it at load time.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage

from .. import texlib as T

LOG_WALL_FINISHES = ["log_chinked"]

PITCH = 0.25          # m per course (w3_lodge_shell)


@dataclass
class LogFinish:
    albedo: np.ndarray
    height: np.ndarray
    rough: np.ndarray
    metal: np.ndarray | float = 0.0
    normal_strength: float = 4.0
    ao_strength: float = 1.0


def _coords(size: int) -> tuple[np.ndarray, np.ndarray]:
    c = (np.arange(size, dtype=np.float32) + 0.5) / size
    return c[None, :].repeat(size, 0), c[:, None].repeat(size, 1)


def _col(h: str) -> np.ndarray:
    return T.hex_rgb(h)[None, None, :].astype(np.float32)


def _sn(size: int, beta: float, seed: int, aniso=(1.0, 1.0), fmin: float = 1.0) -> np.ndarray:
    return T.spectral(size, beta, seed, anisotropy=aniso, fmin=fmin).astype(np.float32)


def _hash(k: int, salt: int) -> float:
    x = (k * 0x9E3779B1 + salt * 0x85EBCA6B) & 0xFFFFFFFF
    x ^= x >> 15
    x = (x * 0x2C1B3C6D) & 0xFFFFFFFF
    x ^= x >> 12
    return (x & 0xFFFFFF) / float(0x1000000)


def log_chinked(size: int, seed: int) -> LogFinish:
    x, y = _coords(size)
    n_rows = int(round(1.0 / PITCH))
    # Each seam (row boundary) wanders a little along the wall: two low harmonics (periodic in 1 m)
    # plus band-limited noise; the chinking's width varies along it too.
    seam_off = np.zeros((size, size), np.float32)
    seam_w = np.zeros((size, size), np.float32)
    lane = _sn(size, 2.6, seed + 1, (1.0, 12.0))           # smooth along x
    lane2 = _sn(size, 2.2, seed + 2, (1.0, 10.0))
    for r in range(n_rows):
        a1, a2 = _hash(r, seed + 3), _hash(r, seed + 4)
        p1, p2 = _hash(r, seed + 5) * 6.283, _hash(r, seed + 6) * 6.283
        off = 0.006 * (2 * a1 - 1) * np.sin(x * 6.283 + p1) + 0.004 * (2 * a2 - 1) * np.sin(x * 12.566 + p2)
        row_band = (np.floor(y / PITCH + 0.5).astype(np.int32) % n_rows) == r
        seam_off = np.where(row_band, off + 0.006 * (lane - 0.5), seam_off)
        seam_w = np.where(row_band, 0.042 + 0.022 * (lane2 - 0.5) + 0.008 * (2 * _hash(r, seed + 7) - 1), seam_w)
    # Position within the course, measured from the seam (round y / PITCH to the nearest seam).
    yy = y + seam_off
    t = yy / PITCH
    row = np.floor(t).astype(np.int32) % n_rows
    v = t - np.floor(t)                                     # 0 at the seam above, 1 at the seam below
    d_seam = np.minimum(v, 1.0 - v) * PITCH                 # metres to the nearest seam
    half_w = seam_w * 0.5
    chink = 1.0 - T.smoothstep(half_w - 0.002, half_w + 0.002, d_seam)
    # Log profile across the face (0 at the chinking edge, 1 on the crown).
    u = np.clip((d_seam - half_w) / np.maximum(PITCH * 0.5 - half_w, 1e-3), 0.0, 1.0)
    crown = np.sqrt(1.0 - (1.0 - u) ** 2)
    lower = (v > 0.5).astype(np.float32)                   # the log's underside (image rows run down)

    rt = np.array([_hash(r, seed + 11) for r in range(n_rows)], np.float32)[row]
    # Bark: furrows (the level lines of a noise stretched along the log) between scaly plates.
    fiss = _sn(size, 1.1, seed + 12, (1.0, 16.0))
    plates = _sn(size, 1.6, seed + 13, (1.0, 6.0))
    fissure = (1.0 - T.smoothstep(0.0, 0.035, np.abs(fiss - 0.5))) * T.smoothstep(0.3, 0.6, _sn(size, 1.4, seed + 18, (1.0, 4.0)))
    fine = _sn(size, 0.5, seed + 19, (1.0, 10.0))
    bark_t = T.normalize(0.45 * plates + 0.25 * rt + 0.15 * _sn(size, 2.0, seed + 14) + 0.15 * fine)
    bark = T.gradient(bark_t, [(0.0, "#4a3a2b"), (0.45, "#67523d"), (0.8, "#7d654c"), (1.0, "#8d775e")])
    bark *= (1.0 - 0.5 * fissure)[..., None]
    # Sloughed bark: strips of silver-grey weathered wood with checks along them.
    slough_n = _sn(size, 1.7, seed + 15, (1.0, 7.0))
    slough = T.smoothstep(0.7, 0.74, slough_n + 0.1 * (rt - 0.5))
    checks = T.smoothstep(0.84, 0.9, _sn(size, 0.6, seed + 16, (1.0, 30.0)))
    wood = T.gradient(T.normalize(_sn(size, 1.2, seed + 17, (1.0, 12.0))), [(0.0, "#80755f"), (1.0, "#a39580")])
    wood *= (1.0 - 0.45 * checks)[..., None]
    log_col = T.mix(bark, wood, slough)
    # Weathering: the crown is sun-bleached, the underside darker and dirtier.
    log_col *= (0.72 + 0.28 * crown)[..., None]
    log_col *= (1.0 - 0.12 * lower * (1.0 - crown))[..., None]
    log_col *= (0.92 + 0.16 * rt)[..., None]

    # Chinking: lime mortar, trowelled, cracked and shrunk away from the log above in places.
    lime_t = _sn(size, 1.8, seed + 21)
    lime = T.gradient(lime_t, [(0.0, "#a9a08c"), (0.6, "#c4bba5"), (1.0, "#d2cab6")])
    dirt = T.smoothstep(0.5, 0.9, _sn(size, 2.0, seed + 22, (1.0, 3.0)))
    lime *= (1.0 - 0.25 * dirt)[..., None]
    gap_n = _sn(size, 1.4, seed + 23, (1.0, 8.0))
    shrink = T.smoothstep(0.66, 0.74, gap_n)
    # The gap opens at the top of the chinking band (against the log above: v near 1 means below it).
    gap = shrink * chink * T.smoothstep(half_w * 0.2, half_w * 0.9, d_seam) * (v > 0.5)
    crk = T.smoothstep(0.86, 0.92, _sn(size, 0.7, seed + 24))
    lime *= (1.0 - 0.4 * crk)[..., None]
    lime = T.mix(lime, _col("#1d1712") * np.ones_like(lime), gap * 0.85)

    col = T.mix(log_col, lime, chink)
    # Shadow on the chinking under each log's overhang (the band's top edge, against the log above).
    over = chink * T.smoothstep(0.0, half_w, d_seam) * (v > 0.5)
    col *= (1.0 - 0.25 * over)[..., None]

    height = np.where(chink > 0.5, 0.12 + 0.04 * lime_t - 0.1 * gap,
                      0.2 + 0.78 * crown - 0.08 * fissure * (1 - slough) - 0.03 * checks * slough + 0.04 * plates * (1 - slough) - 0.03 * slough)
    height = ndimage.gaussian_filter(height.astype(np.float32), 0.8, mode="wrap")
    rough = np.clip(0.88 - 0.12 * slough + 0.06 * fissure + chink * 0.05, 0, 1)
    return LogFinish(np.clip(col, 0, 1).astype(np.float32), np.clip(height, 0, 1).astype(np.float32),
                     rough.astype(np.float32), normal_strength=7.0, ao_strength=1.5)


LOG_FINISH_FNS = {"log_chinked": log_chinked}


def log_finish(name: str, size: int, seed: int) -> LogFinish:
    """The finish `name` with its own seed offset (kit.py's house finishes keep theirs untouched)."""
    return LOG_FINISH_FNS[name](size, seed + 6271 * (LOG_WALL_FINISHES.index(name) + 1) + 900)
