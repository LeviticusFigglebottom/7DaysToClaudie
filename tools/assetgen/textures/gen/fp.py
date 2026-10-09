"""First-person arms (ADR-0029): the convict's skin, the grime worked into it, the Remand jumpsuit
twill, the tether's housing and its standby screen.

Seen at 30-50 cm all game, so these carry fine detail: pores and the skin's crease net, forearm
hair, freckles and veins; twill threads, sun-fading and stains. Tile sizes are set by uv_scale in
game/data/materials/fp.json (the arms use metre UVs).
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from ...core.paths import GAME
from .. import texlib as T
from ..registry import texture

FONT = GAME / "assets" / "fonts" / "IBMPlexMono-Bold.ttf"
FONT_SOURCES = ["game/assets/fonts/IBMPlexMono-Bold.ttf"]


def _c(h):
    return T.hex_rgb(h)[None, None, :]


def _strokes(size: int, n: int, seed: int, length: tuple[float, float], width: float, angle: float, spread: float,
             curve: float = 0.25) -> np.ndarray:
    """Coverage (0..1) of `n` short slightly curved strokes (hairs, fibres), tiling. `angle` is the
    mean direction in radians (0 = along +u), `spread` its jitter."""
    r = T.rng(seed)
    img = Image.new("L", (size * 3, size * 3), 0)
    d = ImageDraw.Draw(img)
    for _ in range(n):
        x, y = r.uniform(0, size), r.uniform(0, size)
        a = angle + r.normal(0.0, spread)
        ln = r.uniform(*length)
        bend = r.normal(0.0, curve)
        pts = []
        for k in range(6):
            t = k / 5
            aa = a + bend * t
            pts.append((x + np.cos(aa) * ln * t, y + np.sin(aa) * ln * t))
        shade = int(r.uniform(140, 255))
        for ox in (0, size, 2 * size):
            for oy in (0, size, 2 * size):
                d.line([(px + ox, py + oy) for px, py in pts], fill=shade, width=max(1, int(round(width))))
    a3 = np.asarray(img, np.float32) / 255.0
    out = np.zeros((size, size), np.float32)
    for ox in (0, size, 2 * size):
        for oy in (0, size, 2 * size):
            out = np.maximum(out, a3[oy:oy + size, ox:ox + size])
    return out


def _crease_net(size: int, cells: int, seed: int, width: float = 1.4) -> np.ndarray:
    """The skin's fine polygonal crease net (1 = in a crease)."""
    f1, f2, _ = T.worley(size, cells, seed, jitter=0.9)
    return (1.0 - T.smoothstep(0.0, width, f2 - f1)).astype(np.float32)


@texture("fp_skin", size=1024, seed=4471)
def fp_skin(size: int, seed: int, out) -> None:
    """A working man's forearms and hands (0.2 m tile): sun-weathered warm skin, freckles and the odd
    mole, dark forearm hair along the arm, faint veins, pores, the crease net at two scales and fine
    tension wrinkles across the arm."""
    broad = T.spectral(size, 2.6, seed)
    mid = T.spectral(size, 1.7, seed + 1)
    fine = T.spectral(size, 0.9, seed + 2)
    tone = T.normalize(0.6 * broad + 0.4 * mid)
    col = T.gradient(tone, [(0.0, "#9c6a52"), (0.45, "#b17b5f"), (0.8, "#bf8a6c"), (1.0, "#c99876")])
    # flushed patches and sallow ones
    flush = T.smoothstep(0.55, 0.85, T.spectral(size, 2.3, seed + 3, fmin=2.0))
    col = T.mix(col, col * np.array([1.06, 0.88, 0.84], np.float32), flush * 0.55)
    sallow = T.smoothstep(0.6, 0.9, T.spectral(size, 2.2, seed + 4, fmin=2.0))
    col = T.mix(col, col * np.array([0.98, 0.98, 0.86], np.float32), sallow * 0.4)
    # freckles (clustered) and a few moles
    f1, _, _ = T.worley(size, 900, seed + 5)
    fr = (1.0 - T.smoothstep(1.2, 3.2, f1)) * T.smoothstep(0.5, 0.8, T.spectral(size, 2.0, seed + 6))
    col = T.mix(col, _c("#7d4a33") * np.ones_like(col), np.clip(fr, 0, 1) * 0.55)
    m1, _, _ = T.worley(size, 14, seed + 7)
    mole = 1.0 - T.smoothstep(2.0, 4.5, m1)
    col = T.mix(col, _c("#4e2c20") * np.ones_like(col), mole * 0.7)
    # veins: faint blue-green branching lines, broad and soft
    vn = T.warp(T.spectral(size, 2.0, seed + 8, anisotropy=(1.0, 3.0)), T.spectral(size, 2.0, seed + 9),
                T.spectral(size, 2.0, seed + 10), size * 0.03)
    gx = (np.roll(vn, -1, 1) - np.roll(vn, 1, 1)) * 0.5
    gy = (np.roll(vn, -1, 0) - np.roll(vn, 1, 0)) * 0.5
    vein = np.clip(1.0 - np.abs(vn - 0.5) / (np.sqrt(gx * gx + gy * gy) * 3.2 + 1e-6), 0, 1)
    vein = T.blur(vein, 1.5) * T.smoothstep(0.35, 0.7, T.spectral(size, 2.0, seed + 11))
    col = T.mix(col, col * np.array([0.82, 0.88, 0.96], np.float32), vein * 0.35)
    # hair: dark, fine, running along the arm (v), sparser in patches
    hair = _strokes(size, 2600, seed + 12, (9.0, 20.0), 1.0, np.pi / 2, 0.35)
    hair *= T.smoothstep(0.25, 0.65, T.spectral(size, 2.0, seed + 13))
    col = T.mix(col, _c("#2e1d14") * np.ones_like(col), hair * 0.55)
    # pores and the crease net (two scales: the ~3.5 mm net and the ~2 mm one inside it, which is
    # what stops skin reading as smooth plastic at arm's length), a touch redder in the creases
    crease = _crease_net(size, 3200, seed + 14)
    micro = _crease_net(size, 11000, seed + 19, 1.0) * (0.6 + 0.4 * T.spectral(size, 1.6, seed + 20))
    deep = _crease_net(size, 220, seed + 15, 1.0) * T.smoothstep(0.45, 0.75, T.spectral(size, 1.8, seed + 16))
    p1, _, _ = T.worley(size, 7000, seed + 17)
    pore = 1.0 - T.smoothstep(0.6, 1.6, p1)
    p2, _, _ = T.worley(size, 22000, seed + 21)
    pore2 = (1.0 - T.smoothstep(0.3, 1.0, p2)) * 0.6
    # tension wrinkles: long, fine, wavy lines across the arm (v runs along it), in patches - the
    # skin's slack over the wrist and the backs of the joints; the shader's `crease_boost` deepens
    # them (and the nets) where vertex B marks the knuckles and finger joints
    wn = T.warp(T.spectral(size, 1.0, seed + 22, anisotropy=(1.0, 8.0), fmin=8.0, fmax=20.0), T.spectral(size, 2.0, seed + 23),
                T.spectral(size, 2.0, seed + 24), size * 0.012)
    # the noise's mid-level contours, ~1 px wide (distance to the contour in pixels)
    wgx = (np.roll(wn, -1, 1) - np.roll(wn, 1, 1)) * 0.5
    wgy = (np.roll(wn, -1, 0) - np.roll(wn, 1, 0)) * 0.5
    wrinkle = 1.0 - T.smoothstep(0.4, 1.4, np.abs(wn - 0.5) / (np.sqrt(wgx * wgx + wgy * wgy) + 1e-6))
    wrinkle *= 0.35 + 0.65 * T.smoothstep(0.35, 0.7, T.spectral(size, 2.0, seed + 25, fmin=2.0))
    lines = np.clip(0.35 * crease + 0.25 * micro + 0.6 * deep + 0.3 * wrinkle, 0, 1)
    col = T.mix(col, col * np.array([0.9, 0.82, 0.8], np.float32), lines * 0.4)
    col *= (1.0 - 0.07 * pore - 0.04 * pore2)[..., None]
    col *= (0.95 + 0.07 * fine)[..., None]
    height = T.normalize(0.30 * mid + 0.25 * fine + 0.08 * T.blur(vein, 3.0) - 0.08 * crease - 0.06 * micro
                         - 0.12 * deep - 0.10 * wrinkle - 0.06 * pore - 0.03 * pore2 + 0.05 * hair)
    rough = np.clip(0.50 + 0.10 * (1 - tone) + 0.06 * crease + 0.04 * micro + 0.08 * deep + 0.04 * wrinkle
                    - 0.06 * vein + 0.05 * fine, 0.32, 0.8)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=3.2, ao_strength=0.7)


@texture("fp_grime", size=1024, seed=4472)
def fp_grime(size: int, seed: int, out) -> None:
    """What works into a salvager's skin and cuffs: soil, soot and dried blood, crusted (the fp_*
    materials' wear layer, revealed by the arms' vertex dirt mask)."""
    b = T.spectral(size, 1.6, seed)
    m = T.spectral(size, 2.2, seed + 1)
    col = T.gradient(T.normalize(0.6 * b + 0.4 * m), [(0.0, "#1f1712"), (0.5, "#3b2a1d"), (1.0, "#5a4532")])
    soot = T.smoothstep(0.6, 0.85, T.spectral(size, 2.0, seed + 2))
    col = T.mix(col, _c("#141110") * np.ones_like(col), soot * 0.7)
    blood = T.smoothstep(0.68, 0.9, T.spectral(size, 2.3, seed + 3, fmin=3.0))
    col = T.mix(col, _c("#3d1009") * np.ones_like(col), blood * 0.75)
    crust = T.smoothstep(0.55, 0.8, T.spectral(size, 0.8, seed + 4))
    height = T.normalize(0.5 * b + 0.5 * crust)
    rough = np.clip(0.88 - 0.25 * blood + 0.05 * crust, 0.5, 1.0)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=3.0)


@texture("fp_sleeve", size=1024, seed=4473)
def fp_sleeve(size: int, seed: int, out) -> None:
    """Remand Program jumpsuit (0.25 m tile): heavy 2/1 cotton twill in Program orange, washed and
    sun-bleached to a dull rust, grimed, stained and scuffed pale where it wears."""
    y, x = np.mgrid[0:size, 0:size].astype(np.float32)
    count = 256                                     # threads per tile each way (~1 mm)
    u = x * count / size
    v = y * count / size
    # twill: the warp float steps one thread per pick, so ribs run diagonally
    rib = np.sin((u + v) / 3.0 * 2 * np.pi)
    thread_u = np.abs(np.sin(u * np.pi))
    thread_v = np.abs(np.sin(v * np.pi))
    weave = 0.55 * (0.5 + 0.5 * rib) + 0.25 * thread_u + 0.2 * thread_v
    slub = T.spectral(size, 1.0, seed, anisotropy=(9.0, 1.0))
    weave = weave * (0.85 + 0.3 * slub)
    fade = T.spectral(size, 2.4, seed + 1)
    col = T.gradient(T.normalize(0.55 * fade + 0.25 * T.spectral(size, 1.6, seed + 2) + 0.2 * slub),
                     [(0.0, "#7c3f22"), (0.4, "#93502b"), (0.75, "#a7643a"), (1.0, "#b2774f")])
    bleach = T.smoothstep(0.55, 0.9, T.spectral(size, 2.2, seed + 3))
    col = T.mix(col, _c("#b48f74") * np.ones_like(col), bleach * 0.45)
    grime = T.smoothstep(0.5, 0.85, T.spectral(size, 2.1, seed + 4))
    col = T.mix(col, _c("#3e2a1e") * np.ones_like(col), grime * 0.45)
    # oil and blood stains with darker rims
    st = T.warp(T.spectral(size, 2.2, seed + 5, fmin=6.0), T.spectral(size, 1.8, seed + 8), T.spectral(size, 1.8, seed + 9), size * 0.02)
    stain = T.smoothstep(0.80, 0.86, st)
    rim = T.smoothstep(0.78, 0.80, st) * (1 - T.smoothstep(0.80, 0.83, st))
    col = T.mix(col, col * np.array([0.62, 0.5, 0.44], np.float32), stain * 0.45 + rim * 0.2)
    # abrasion: raised fibres go pale and fuzzy
    fuzz = _strokes(size, 1400, seed + 6, (4.0, 10.0), 1.0, 0.0, 1.6, 0.6) * T.smoothstep(0.45, 0.8, T.spectral(size, 1.8, seed + 7))
    col = T.mix(col, _c("#c9a487") * np.ones_like(col), fuzz * 0.35)
    col *= (0.8 + 0.35 * weave)[..., None]
    height = T.normalize(0.75 * weave + 0.15 * slub + 0.1 * fuzz)
    rough = np.clip(0.86 + 0.06 * grime - 0.12 * stain * 0.5, 0.6, 1.0)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=2.6, ao_strength=0.8)


@texture("fp_tether", size=512, seed=4474)
def fp_tether(size: int, seed: int, out) -> None:
    """The tether's housing: bead-blasted Program polymer, charcoal going grey where it's handled,
    scuffed, with grime packed into the texture."""
    bead = T.spectral(size, 0.6, seed)
    b = T.spectral(size, 2.0, seed + 1)
    col = T.gradient(T.normalize(0.7 * b + 0.3 * bead), [(0.0, "#1d2022"), (0.6, "#2a2e31"), (1.0, "#383d40")])
    worn = T.smoothstep(0.6, 0.9, T.spectral(size, 2.2, seed + 2))
    col = T.mix(col, _c("#55595a") * np.ones_like(col), worn * 0.4)
    scuff = _strokes(size, 60, seed + 3, (8.0, 30.0), 1.0, 0.3, 0.8, 0.2)
    col = T.mix(col, _c("#6a6e70") * np.ones_like(col), scuff * 0.3)
    grime = T.smoothstep(0.55, 0.85, T.spectral(size, 1.8, seed + 4))
    col = T.mix(col, _c("#2a2219") * np.ones_like(col), grime * 0.35)
    height = T.normalize(0.4 * bead + 0.3 * b - 0.3 * scuff)
    rough = np.clip(0.62 + 0.15 * grime - 0.25 * scuff - 0.1 * worn, 0.25, 0.9)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=1.6)


@texture("fp_tether_screen", size=512, seed=4475, sources=FONT_SOURCES)
def fp_tether_screen(size: int, seed: int, out) -> None:
    """The tether at rest on the wrist, before the live UI takes over: a dim green standby frame
    (Program header, the salvager's number, the Hum countdown, a heart trace), scanlines."""
    w, h = size, size
    img = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(img)
    f_s = ImageFont.truetype(str(FONT), 30)
    f_l = ImageFont.truetype(str(FONT), 92)
    d.text((24, 22), "REMAND SALVAGE", fill=200, font=f_s)
    d.text((24, 58), "#4471  CORDON D6", fill=150, font=f_s)
    d.text((24, 150), "HUM", fill=170, font=f_s)
    d.text((24, 184), "-71:24", fill=255, font=f_l)
    r = T.rng(seed)
    base_y = 400
    pts = []
    for xi in range(24, w - 24, 4):
        k = (xi // 4) % 40
        yv = base_y
        if k == 6:
            yv -= 46
        elif k == 7:
            yv += 30
        elif k == 8:
            yv -= 12
        pts.append((xi, yv + r.normal(0, 1.2)))
    d.line(pts, fill=230, width=3)
    a = np.asarray(img, np.float32) / 255.0
    glow = T.blur(a, 2.5)
    y = np.mgrid[0:h, 0:w][0]
    scan = 0.82 + 0.18 * (y % 4 < 2)
    level = np.clip(0.10 + 0.9 * a + 0.45 * glow, 0, 1) * scan
    col = np.stack([level * 0.28, level * 0.95, level * 0.55], -1)
    col = col * 0.85 + _c("#03100a") * 0.15
    T.save_pbr_set(out, np.clip(col, 0, 1).astype(np.float32), np.zeros((h, w), np.float32),
                   np.full((h, w), 0.12, np.float32), normal_strength=0.0)
