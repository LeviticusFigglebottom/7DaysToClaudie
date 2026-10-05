"""The Remand Program's kit (ADR-0023): the heavy-lift supply drone's livery and carbon frame.

  * program_livery  1024 px atlas, 128 px units (cells in LIVERY below; keep in sync with
                    blender/generators/props_ext_program.py ATLAS). Off-white Program livery panels
                    with high-vis orange bands and black stencils: REMAND SALVAGE PROGRAM, the unit
                    number, the Cordon Authority roundel, a rotor caution strip, hazard chevrons and a
                    data plate. Weathered: rain streaks from rivets and seams, scuffs, exhaust grime.
                    Lettering uses the roadside family's stroke font (no font files).
  * program_carbon  512 px tileable 2x2 twill carbon-fibre weave under clear resin (arms, blades).
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

from .. import texlib as T
from ..registry import texture
from .roadside import _ellipse_mask, _emboss, _noise, _over, _poly_mask, _rect_mask, _text_mask

UNIT = 128
LIVERY = {
    "side": (0, 0, 8, 1), "side_b": (0, 1, 8, 1), "top": (0, 2, 4, 4), "chevron": (4, 2, 4, 1),
    "caution": (4, 3, 4, 1), "roundel": (4, 4, 2, 2), "plate": (6, 4, 2, 1), "warning": (6, 5, 2, 1),
    "nose": (4, 6, 4, 2), "panel": (0, 6, 4, 2),
}
WHITE = "#d8d5cb"
ORANGE = "#d0571c"
BLACK = "#1d1d1c"
YELLOW = "#d9ae2c"


def _cell(name: str) -> tuple[int, int]:
    _, _, w, h = LIVERY[name]
    return w * UNIT, h * UNIT


def _weather(col: np.ndarray, h: np.ndarray, seed: int, *, streaks: float = 0.5) -> tuple[np.ndarray, np.ndarray]:
    """Rain streaks running down from the top edge and from rivet lines, scuffs and a grimy bottom."""
    hh, ww = col.shape[:2]
    n1 = _noise(hh, ww, 1.6, seed)
    streak = _noise(hh, ww, 1.2, seed + 1, aniso=(0.08, 2.5))
    yy = np.linspace(0, 1, hh)[:, None]
    grime = np.clip((streak - 0.55) * 3.0, 0, 1) * streaks * (0.4 + 0.6 * yy) + np.clip((yy - 0.75) * 2.0, 0, 1) * 0.35
    grime *= 0.6 + 0.4 * n1
    dirt = np.array([0.24, 0.21, 0.17], np.float32)
    col = col * (1 - grime[..., None] * 0.55) + dirt * grime[..., None] * 0.55
    scuff = np.clip((_noise(hh, ww, 0.9, seed + 2) - 0.86) * 8.0, 0, 1)
    col = col * (1 - scuff[..., None] * 0.35) + np.array([0.55, 0.55, 0.53], np.float32) * scuff[..., None] * 0.35
    return col, h - scuff * 0.04


def _base(w: int, h: int, fill: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    col = np.ones((h, w, 3), np.float32) * T.hex_rgb(fill)[None, None, :]
    return col, np.full((h, w), 0.5, np.float32), np.full((h, w), 0.42, np.float32)


def _rivets(w: int, h: int, xs, ys, r: float = 3.0) -> np.ndarray:
    return _ellipse_mask(w, h, [(x, y, r, r) for x in xs for y in ys])


def _side(seed: int):
    """Body side band: white panel, orange stripe low, the stencilled Program name and unit number."""
    w, h = _cell("side")
    col, ht, ro = _base(w, h, WHITE)
    stripe = _rect_mask(w, h, [(0, 92, w, 118)])
    col = _over(col, ORANGE, stripe)
    pin = _rect_mask(w, h, [(0, 86, w, 89)])
    col = _over(col, BLACK, pin)
    txt = _text_mask(w, h, [{"s": "REMAND", "x": 40, "y": 18, "cap": 46, "stroke": 9, "track": 10},
                            {"s": "SALVAGE PROGRAM", "x": 336, "y": 34, "cap": 22, "stroke": 4.2, "track": 5},
                            {"s": "RP-HL 09", "x": w - 40, "y": 22, "cap": 40, "stroke": 7.5, "track": 6, "align": "right"},
                            {"s": "CORDON AUTHORITY", "x": w - 40, "y": 98, "cap": 13, "stroke": 2.6, "track": 3, "align": "right"}])
    col = _over(col, BLACK, txt * (1.0 - stripe))
    col = _over(col, WHITE, txt * stripe)
    seam = _rect_mask(w, h, [(300, 0, 302, 86), (700, 0, 702, 86)])
    col = _over(col, "#9a978f", seam)
    riv = _rivets(w, h, [8, 296, 306, 696, 706, w - 8], [8, 80])
    col = _over(col, "#a8a59c", riv)
    ht = ht + _emboss(riv, 0.3) - seam * 0.15
    col, ht = _weather(col, ht, seed)
    return col, ht, ro


def _top(seed: int):
    """Top deck: hazard border, the big aerial unit number, NO STEP by the battery bays."""
    w, h = _cell("top")
    col, ht, ro = _base(w, h, WHITE)
    yy, xx = np.mgrid[0:h, 0:w]
    border = ((xx < 34) | (xx > w - 34) | (yy < 34) | (yy > h - 34)).astype(np.float32)
    chev = ((((xx + yy) // 24) % 2) == 0).astype(np.float32)
    col = _over(col, ORANGE, border * chev)
    col = _over(col, BLACK, border * (1 - chev))
    num = _text_mask(w, h, [{"s": "09", "x": w / 2, "y": 110, "cap": 230, "stroke": 38, "track": 18, "align": "center"},
                            {"s": "RP-HL", "x": w / 2, "y": 372, "cap": 40, "stroke": 7, "track": 9, "align": "center"},
                            {"s": "NO STEP", "x": w / 2, "y": 60, "cap": 18, "stroke": 3.4, "track": 5, "align": "center"}])
    col = _over(col, BLACK, num)
    col, ht = _weather(col, ht, seed, streaks=0.3)
    return col, ht, ro


def _chevron(seed: int):
    w, h = _cell("chevron")
    yy, xx = np.mgrid[0:h, 0:w]
    stripes = ((((xx + yy * 0.9) // 32) % 2) == 0).astype(np.float32)
    col, ht, ro = _base(w, h, BLACK)
    col = _over(col, ORANGE, stripes)
    col, ht = _weather(col, ht, seed, streaks=0.2)
    return col, ht, ro


def _caution(seed: int):
    w, h = _cell("caution")
    col, ht, ro = _base(w, h, YELLOW)
    txt = _text_mask(w, h, [{"s": "CAUTION  ROTOR BLADES", "x": w / 2, "y": 30, "cap": 34, "stroke": 6.5, "track": 6,
                             "align": "center", "fit": w - 120},
                            {"s": "KEEP CLEAR WHILE ARMED", "x": w / 2, "y": 80, "cap": 18, "stroke": 3.4, "track": 4,
                             "align": "center"}])
    tri = _poly_mask(w, h, [[(18, 104), (46, 24), (74, 104)], [(w - 74, 104), (w - 46, 24), (w - 18, 104)]])
    col = _over(col, BLACK, np.clip(txt + tri, 0, 1))
    excl = _text_mask(w, h, [{"s": "!", "x": 46, "y": 52, "cap": 40, "stroke": 7, "align": "center"},
                             {"s": "!", "x": w - 46, "y": 52, "cap": 40, "stroke": 7, "align": "center"}])
    col = _over(col, YELLOW, excl)
    col, ht = _weather(col, ht, seed, streaks=0.3)
    return col, ht, ro


def _roundel(seed: int):
    """Cordon Authority roundel: a gate in a fence ring, the authority's name around it."""
    w, h = _cell("roundel")
    col, ht, ro = _base(w, h, WHITE)
    cx, cy = w / 2, h / 2
    ring = _ellipse_mask(w, h, [(cx, cy, 120, 120)]) * (1 - _ellipse_mask(w, h, [(cx, cy, 82, 82)]))
    col = _over(col, BLACK, ring)
    disc = _ellipse_mask(w, h, [(cx, cy, 74, 74)])
    col = _over(col, ORANGE, disc)
    posts = _rect_mask(w, h, [(cx - 52, cy - 40, cx - 42, cy + 44), (cx + 42, cy - 40, cx + 52, cy + 44)])
    wire = _rect_mask(w, h, [(cx - 60, cy - 30, cx + 60, cy - 25), (cx - 60, cy - 5, cx + 60, cy), (cx - 60, cy + 20, cx + 60, cy + 25)])
    col = _over(col, BLACK, np.clip(posts + wire, 0, 1))
    # Stamped letters (upright) along the ring, each arc reading left to right: the authority
    # over the top, the Program under it.
    items = []
    for text, a0, a1, cap in (("CORDON AUTHORITY", np.radians(194), np.radians(346), 14.0), ("REMAND", np.radians(140), np.radians(40), 18.0)):
        for i, ch in enumerate(text):
            if ch == " ":
                continue
            a = a0 + (a1 - a0) * i / (len(text) - 1)
            items.append({"s": ch, "x": cx + np.cos(a) * 101, "y": cy + np.sin(a) * 101 - cap / 2, "cap": cap, "stroke": cap * 0.19,
                          "align": "center"})
    for a in (np.radians(10), np.radians(170)):
        items.append({"s": "*", "x": cx + np.cos(a) * 101, "y": cy + np.sin(a) * 101 - 9, "cap": 18, "stroke": 5.0, "align": "center"})
    col = _over(col, WHITE, _text_mask(w, h, items))
    col, ht = _weather(col, ht, seed, streaks=0.2)
    return col, ht, ro


def _plate(seed: int):
    w, h = _cell("plate")
    col, ht, ro = _base(w, h, "#9fa3a3")
    txt = _text_mask(w, h, [{"s": "UNIT RP-HL 09", "x": 14, "y": 14, "cap": 16, "stroke": 2.6, "track": 3},
                            {"s": "MTOW 210 KG  LIFT 60 KG", "x": 14, "y": 44, "cap": 11, "stroke": 2.0, "track": 2},
                            {"s": "PROPERTY OF THE CORDON", "x": 14, "y": 66, "cap": 11, "stroke": 2.0, "track": 2},
                            {"s": "AUTHORITY - DO NOT TAMPER", "x": 14, "y": 88, "cap": 11, "stroke": 2.0, "track": 2, "fit": w - 28}])
    col = _over(col, BLACK, txt)
    riv = _rivets(w, h, [7, w - 7], [7, h - 7], 3.0)
    col = _over(col, "#c9cccc", riv)
    ht = ht + _emboss(txt, 0.15) + _emboss(riv, 0.3)
    ro = ro * 0.0 + 0.32
    return col, ht, ro


def _warning(seed: int):
    w, h = _cell("warning")
    col, ht, ro = _base(w, h, ORANGE)
    txt = _text_mask(w, h, [{"s": "DO NOT APPROACH", "x": w / 2, "y": 24, "cap": 24, "stroke": 4.4, "track": 4, "align": "center", "fit": w - 24},
                            {"s": "REPORT FINDS TO", "x": w / 2, "y": 64, "cap": 14, "stroke": 2.6, "track": 3, "align": "center"},
                            {"s": "WAYSTATION 9", "x": w / 2, "y": 88, "cap": 18, "stroke": 3.4, "track": 3, "align": "center"}])
    col = _over(col, BLACK, txt)
    col, ht = _weather(col, ht, seed, streaks=0.4)
    return col, ht, ro


def _nose(seed: int):
    """Nose fairing: orange with a black anti-glare panel and the Program's name small."""
    w, h = _cell("nose")
    col, ht, ro = _base(w, h, ORANGE)
    glare = _rect_mask(w, h, [(0, 0, w, 70)])
    col = _over(col, BLACK, glare)
    txt = _text_mask(w, h, [{"s": "REMAND", "x": w / 2, "y": 120, "cap": 40, "stroke": 7.5, "track": 8, "align": "center"},
                            {"s": "09", "x": w / 2, "y": 180, "cap": 46, "stroke": 8.5, "track": 6, "align": "center"}])
    col = _over(col, WHITE, txt)
    col, ht = _weather(col, ht, seed, streaks=0.5)
    return col, ht, ro


def _panel(seed: int):
    """Plain white panel with an access hatch, latches and a vent grille (fills big shell faces)."""
    w, h = _cell("panel")
    col, ht, ro = _base(w, h, WHITE)
    hatch = _rect_mask(w, h, [(60, 40, 300, 210)], radius=12) * (1 - _rect_mask(w, h, [(64, 44, 296, 206)], radius=10))
    col = _over(col, "#8f8c84", hatch)
    vent = np.zeros((h, w), np.float32)
    for k in range(7):
        vent += _rect_mask(w, h, [(340, 60 + k * 20, 480, 70 + k * 20)])
    col = _over(col, "#2a2a29", vent)
    latch = _rect_mask(w, h, [(170, 30, 190, 48), (170, 202, 190, 220)])
    col = _over(col, "#5a5a58", latch)
    ht = ht - hatch * 0.2 - vent * 0.35 + _emboss(latch, 0.3)
    col, ht = _weather(col, ht, seed)
    return col, ht, ro


@texture("program_livery", size=1024, seed=17201, sources=["tools/assetgen/textures/gen/roadside.py"])
def program_livery(size: int, seed: int, out) -> None:
    alb = np.full((size, size, 3), 0.5, np.float32)
    hgt = np.full((size, size), 0.5, np.float32)
    rgh = np.full((size, size), 0.45, np.float32)
    makers = {"side": _side, "side_b": _side, "top": _top, "chevron": _chevron, "caution": _caution,
              "roundel": _roundel, "plate": _plate, "warning": _warning, "nose": _nose, "panel": _panel}
    for i, (name, fn) in enumerate(makers.items()):
        c, h, r = fn(seed + i * 41)
        x, y, w, hh = [v * UNIT for v in LIVERY[name]]
        alb[y:y + hh, x:x + w] = c
        hgt[y:y + hh, x:x + w] = h
        rgh[y:y + hh, x:x + w] = r
    T.save_pbr_set(out, np.clip(alb, 0, 1), np.clip(hgt, 0, 1), np.clip(rgh, 0.05, 1), normal_strength=2.5, ao_strength=0.6)


@texture("program_carbon", size=512, seed=17202)
def program_carbon(size: int, seed: int, out) -> None:
    """2x2 twill: 32 tows across the tile, each tow's fibres running along it, glossy resin over."""
    n = size
    tows = 32
    p = n // tows
    yy, xx = np.mgrid[0:n, 0:n]
    cx, cy = xx // p, yy // p
    # Twill: a tow is warp (vertical) when (cx + cy) mod 4 < 2.
    warp = (((cx + cy) % 4) < 2).astype(np.float32)
    fx = (xx % p) / p
    fy = (yy % p) / p
    # Each tow is a rounded ridge across its width, with fine fibre lines along it.
    across = np.where(warp > 0, fx, fy)
    along = np.where(warp > 0, fy, fx)
    ridge = np.sin(np.pi * across) ** 0.6
    r = T.rng(seed)
    fib = ndimage.gaussian_filter(r.random((n, n)).astype(np.float32), (0.6, 0.6))
    fib = np.where(warp > 0, ndimage.gaussian_filter(fib, (4.0, 0.3)), ndimage.gaussian_filter(fib, (0.3, 4.0)))
    height = 0.5 + 0.35 * ridge + 0.06 * (fib - fib.mean()) / (fib.std() + 1e-6) * 0.2 - 0.05 * np.sin(np.pi * along) ** 8
    sheen = 0.06 + 0.05 * ridge * (0.6 + 0.4 * warp)
    alb = np.stack([sheen, sheen, sheen * 1.06], -1).astype(np.float32)
    rough = (0.28 + 0.1 * (1 - ridge)).astype(np.float32)
    T.save_pbr_set(out, alb, np.clip(height, 0, 1).astype(np.float32), rough, normal_strength=2.0, ao_strength=0.5)
