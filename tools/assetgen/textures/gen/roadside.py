"""Route 9 roadside family (Cordon Gas & Garage, Timberline Motel, Tamsin Valley Clinic).

Lettered signage is drawn with our own **stroke font** (``GLYPHS`` below: polylines on a 10-unit cap
height, rendered as round-capped strokes with PIL at 4x supersampling) -- no font files, no
third-party glyphs. Atlases are non-tiling; their cell rectangles are the contract with the Blender
generator ``blender/generators/props_roadside.py`` (``ATLAS_*`` tables there, keep both in sync):

  * road_signs        2048 px, 256 px units: gas pylon brand + price boards, canopy band, pump faces,
                      vending front, ice merchandiser, newspaper box, air pump, x-ray / exit labels,
                      motor-oil labels, supply-box labels.
  * road_signs_motel  2048 px, 256 px units: Timberline sign faces, vacancy / NO / rates panels,
                      office / laundry / ice plaques, room numbers, clinic fascia sign, quarantine
                      notice, chest x-ray films, eye chart, room-rates card.
  * road_spray        1024 px, 2 x 4 sheets of 512 x 256: survivor spray paint on plywood.
Tileable sets: road_bedspread (90s quilted motel polyester), road_tread_plate (diamond plate).
Decal: decal_road_oil_stain (pbr_alpha, garage floors and forecourt).
Everything is sun-faded and grimy to fit a valley abandoned for a winter: no clean sign anywhere.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw

from .. import texlib as T
from ..registry import texture


# --------------------------------------------------------------------------------------------
# Stroke font: char -> (advance width in units, [polyline, ...]); cap height = 10 units, y down.
# --------------------------------------------------------------------------------------------

def _arc(cx: float, cy: float, rx: float, ry: float, a0: float, a1: float, step: float = 12.0) -> list:
    """Points on an elliptical arc from angle a0 to a1 (degrees, screen space: 0 = +x, 90 = down)."""
    n = max(2, int(math.ceil(abs(a1 - a0) / step)) + 1)
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / (n - 1))),
             cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / (n - 1)))) for i in range(n)]


def _cat(*parts) -> list:
    out = []
    for p in parts:
        out += list(p)
    return out


_S_STROKE = _cat(_arc(3.1, 2.6, 2.9, 2.6, -25, -270), _arc(3.1, 7.5, 3.1, 2.5, -90, 155))
_P_BOWL = _cat([(0, 10), (0, 0), (3.5, 0)], _arc(3.5, 2.75, 2.6, 2.75, -90, 90), [(3.5, 5.5), (0, 5.5)])
_O_RING = _arc(3.4, 5, 3.4, 5, 0, 360)

GLYPHS: dict[str, tuple[float, list]] = {
    "A": (6.4, [[(0, 10), (3.2, 0), (6.4, 10)], [(1.15, 6.6), (5.25, 6.6)]]),
    "B": (6.2, [_cat([(0, 10), (0, 0), (3.4, 0)], _arc(3.4, 2.5, 2.4, 2.5, -90, 90), [(3.4, 5.0), (0, 5.0)]),
                _cat([(0, 5.0), (3.7, 5.0)], _arc(3.7, 7.5, 2.5, 2.5, -90, 90), [(3.7, 10), (0, 10)])]),
    "C": (6.4, [_arc(3.3, 5, 3.3, 5, -48, -312)]),
    "D": (6.0, [_cat([(0, 0), (0, 10), (2.4, 10)], _arc(2.4, 5, 3.6, 5, 90, -90), [(2.4, 0), (0, 0)])]),
    "E": (5.6, [[(5.6, 0), (0, 0), (0, 10), (5.6, 10)], [(0, 5), (4.6, 5)]]),
    "F": (5.4, [[(5.6, 0), (0, 0), (0, 10)], [(0, 5), (4.6, 5)]]),
    "G": (6.6, [_cat(_arc(3.3, 5, 3.3, 5, -45, -360)), [(6.6, 5.0), (3.7, 5.0)]]),
    "H": (6.0, [[(0, 0), (0, 10)], [(6, 0), (6, 10)], [(0, 5), (6, 5)]]),
    "I": (0.0, [[(0, 0), (0, 10)]]),
    "J": (4.6, [_cat([(4.6, 0), (4.6, 7.0)], _arc(2.3, 7.0, 2.3, 3.0, 0, 180))]),
    "K": (6.0, [[(0, 0), (0, 10)], [(5.8, 0), (0, 6.4)], [(2.1, 4.3), (6.0, 10)]]),
    "L": (5.4, [[(0, 0), (0, 10), (5.4, 10)]]),
    "M": (7.0, [[(0, 10), (0, 0), (3.5, 7.0), (7.0, 0), (7.0, 10)]]),
    "N": (6.0, [[(0, 10), (0, 0), (6, 10), (6, 0)]]),
    "O": (6.8, [_O_RING]),
    "P": (6.1, [_P_BOWL]),
    "Q": (6.8, [_O_RING, [(3.9, 7.2), (6.6, 10.6)]]),
    "R": (6.1, [_P_BOWL, [(2.8, 5.5), (6.1, 10)]]),
    "S": (6.2, [_S_STROKE]),
    "T": (6.4, [[(0, 0), (6.4, 0)], [(3.2, 0), (3.2, 10)]]),
    "U": (6.0, [_cat([(0, 0), (0, 6.8)], _arc(3, 6.8, 3, 3.2, 180, 0), [(6, 6.8), (6, 0)])]),
    "V": (6.4, [[(0, 0), (3.2, 10), (6.4, 0)]]),
    "W": (8.0, [[(0, 0), (1.9, 10), (4.0, 2.5), (6.1, 10), (8.0, 0)]]),
    "X": (6.0, [[(0, 0), (6, 10)], [(6, 0), (0, 10)]]),
    "Y": (6.4, [[(0, 0), (3.2, 5.4), (6.4, 0)], [(3.2, 5.4), (3.2, 10)]]),
    "Z": (6.0, [[(0.2, 0), (6, 0), (0, 10), (6, 10)]]),
    "0": (6.0, [_arc(3, 5, 3, 5, 0, 360)]),
    "1": (6.0, [[(1.6, 2.2), (3.8, 0), (3.8, 10)]]),
    "2": (6.0, [_cat(_arc(3, 3, 3, 3, -170, 25), [(0, 10), (6.2, 10)])]),
    "3": (6.0, [_cat(_arc(3, 2.6, 2.8, 2.6, -160, 90), _arc(3, 7.5, 3, 2.5, -90, 160))]),
    "4": (6.0, [[(4.6, 10), (4.6, 0), (0, 7.0), (6.2, 7.0)]]),
    "5": (6.0, [_cat([(5.6, 0), (0.8, 0), (0.4, 4.5)], _arc(3, 6.9, 3, 3.1, -120, 160))]),
    "6": (6.0, [_arc(3, 7, 3, 3, 0, 360), [(0.05, 6.6), (0.6, 3.6), (1.8, 1.3), (3.3, 0.1), (5.2, 0.4)]]),
    "7": (6.0, [[(0, 0), (6, 0), (2.2, 10)]]),
    "8": (6.0, [_arc(3, 2.5, 2.6, 2.5, 0, 360), _arc(3, 7.4, 3, 2.6, 0, 360)]),
    "9": (6.0, [_arc(3, 3, 3, 3, 0, 360), [(5.95, 3.4), (5.4, 6.4), (4.2, 8.7), (2.7, 9.9), (0.8, 9.6)]]),
    ".": (0.4, [[(0.2, 9.5), (0.2, 9.7)]]),
    ",": (0.6, [[(0.6, 9.3), (0.0, 11.2)]]),
    "-": (3.6, [[(0, 5.4), (3.6, 5.4)]]),
    "/": (4.6, [[(4.6, -0.3), (0, 10.3)]]),
    "&": (6.6, [[(6.6, 10), (1.6, 3.9), (1.2, 1.9), (2.2, 0.3), (3.8, 0.2), (4.6, 1.6), (4.2, 3.3), (0.8, 6.0),
                 (0.5, 8.4), (1.9, 9.9), (3.9, 9.9), (6.4, 6.6)]]),
    "$": (6.2, [_S_STROKE, [(3.1, -1.3), (3.1, 11.3)]]),
    "!": (0.4, [[(0.2, 0), (0.2, 7.0)], [(0.2, 9.5), (0.2, 9.7)]]),
    ":": (0.4, [[(0.2, 3.0), (0.2, 3.2)], [(0.2, 9.5), (0.2, 9.7)]]),
    "'": (0.4, [[(0.2, 0), (0.2, 2.8)]]),
    "(": (2.0, [_arc(4.0, 5, 4.0, 6.0, -125, -235)]),
    ")": (2.0, [_arc(-2.0, 5, 4.0, 6.0, -55, 55)]),
    "*": (0.4, [[(0.2, 5.0), (0.2, 5.2)]]),  # middle dot
    "+": (6.0, [[(0, 5), (6, 5)], [(3, 2), (3, 8)]]),
    "#": (6.0, [[(1.6, 0), (1.0, 10)], [(4.6, 0), (4.0, 10)], [(0, 3.3), (6, 3.3)], [(0, 6.7), (6, 6.7)]]),
    ">": (7.2, [[(0, 5), (7.0, 5)], [(4.4, 2.2), (7.2, 5), (4.4, 7.8)]]),  # arrow right
    "<": (7.2, [[(7.2, 5), (0.2, 5)], [(2.8, 2.2), (0, 5), (2.8, 7.8)]]),  # arrow left
    "%": (6.6, [[(6.0, 0), (0.6, 10)], _arc(1.4, 2.2, 1.4, 2.0, 0, 360), _arc(5.2, 7.8, 1.4, 2.0, 0, 360)]),
}
SPACE = 3.4


def text_width(s: str, cap: float, stroke: float, track: float = 0.0, condense: float = 1.0) -> float:
    k = cap / 10.0 * condense
    w = 0.0
    for i, ch in enumerate(s):
        if ch == " ":
            w += SPACE * k + track
            continue
        adv, _ = GLYPHS.get(ch, GLYPHS["-"])
        w += adv * k + stroke + (track if i < len(s) - 1 else 0.0)
    return w


def _draw_text(d: ImageDraw.ImageDraw, ss: int, s: str, x: float, y: float, cap: float, stroke: float, *,
               track: float = 0.0, condense: float = 1.0, align: str = "left", italic: float = 0.0,
               jitter=None) -> float:
    """Draws `s` with its cap-height box top at y (pixels). align: left|center|right of x.
    jitter(x, y) -> (dx, dy) wobbles every vertex (spray paint, marker). Returns the drawn width."""
    w = text_width(s, cap, stroke, track, condense)
    if align == "center":
        x -= w / 2
    elif align == "right":
        x -= w
    k = cap / 10.0
    pen = x + stroke / 2
    rad = stroke * ss / 2
    for ch in s:
        if ch == " ":
            pen += SPACE * k * condense + track
            continue
        adv, lines = GLYPHS.get(ch, GLYPHS["-"])
        for line in lines:
            pts = []
            for (gx, gy) in line:
                px = pen + gx * k * condense + italic * (10 - gy) * k
                py = y + gy * k
                if jitter is not None:
                    dx, dy = jitter(px, py)
                    px, py = px + dx, py + dy
                pts.append((px * ss, py * ss))
            if len(pts) > 1:
                d.line(pts, fill=255, width=max(1, int(round(stroke * ss))), joint="curve")
            for (px, py) in (pts[0], pts[-1]) if len(pts) > 1 else pts:
                d.ellipse((px - rad, py - rad, px + rad, py + rad), fill=255)
            if len(pts) > 2:
                for (px, py) in pts[1:-1]:
                    d.ellipse((px - rad * 0.98, py - rad * 0.98, px + rad * 0.98, py + rad * 0.98), fill=255)
        pen += adv * k * condense + stroke + track
    return w


def _mask(w: int, h: int, fn, ss: int = 4) -> np.ndarray:
    """Anti-aliased mask (0..1, h x w): fn(draw, ss) draws white at ss x resolution."""
    img = Image.new("L", (w * ss, h * ss), 0)
    fn(ImageDraw.Draw(img), ss)
    img = img.resize((w, h), Image.BOX)
    return np.asarray(img, np.float32) / 255.0


def _fit(it: dict) -> dict:
    """Shrinks an item's cap height / stroke / tracking so the text is at most it["fit"] px wide,
    keeping its vertical centre."""
    mw = it.get("fit")
    if not mw:
        return it
    tw = text_width(it["s"], it["cap"], it["stroke"], it.get("track", 0.0), it.get("condense", 1.0))
    if tw <= mw:
        return it
    k = mw / tw
    out = dict(it)
    out["cap"] = it["cap"] * k
    out["stroke"] = it["stroke"] * k
    out["track"] = it.get("track", 0.0) * k
    out["y"] = it["y"] + (it["cap"] - out["cap"]) / 2
    return out


def _text_mask(w: int, h: int, items: list[dict], ss: int = 4) -> np.ndarray:
    """items: dicts with s, x, y, cap, stroke (+ track, condense, align, italic, jitter, fit)."""
    def fn(d, k):
        for it in items:
            it = _fit(it)
            _draw_text(d, k, it["s"], it["x"], it["y"], it["cap"], it["stroke"], track=it.get("track", 0.0),
                       condense=it.get("condense", 1.0), align=it.get("align", "left"), italic=it.get("italic", 0.0),
                       jitter=it.get("jitter"))
    return _mask(w, h, fn, ss)


def _rect_mask(w: int, h: int, rects, radius: float = 0.0) -> np.ndarray:
    def fn(d, k):
        for (x0, y0, x1, y1) in rects:
            if radius > 0:
                d.rounded_rectangle((x0 * k, y0 * k, x1 * k, y1 * k), radius=radius * k, fill=255)
            else:
                d.rectangle((x0 * k, y0 * k, x1 * k, y1 * k), fill=255)
    return _mask(w, h, fn)


def _poly_mask(w: int, h: int, polys) -> np.ndarray:
    def fn(d, k):
        for poly in polys:
            d.polygon([(x * k, y * k) for x, y in poly], fill=255)
    return _mask(w, h, fn)


def _ellipse_mask(w: int, h: int, ells) -> np.ndarray:
    def fn(d, k):
        for (cx, cy, rx, ry) in ells:
            d.ellipse(((cx - rx) * k, (cy - ry) * k, (cx + rx) * k, (cy + ry) * k), fill=255)
    return _mask(w, h, fn)


def _c(h: str) -> np.ndarray:
    return T.hex_rgb(h)[None, None, :]


def _fill(h: int, w: int, col: str) -> np.ndarray:
    return np.ones((h, w, 3), np.float32) * _c(col)


def _over(base: np.ndarray, col, mask: np.ndarray, a: float = 1.0) -> np.ndarray:
    c = _c(col) if isinstance(col, str) else col
    return base + (c - base) * (mask[..., None] * a)


def _noise(h: int, w: int, beta: float, seed: int, aniso=(1.0, 1.0)) -> np.ndarray:
    """Rectangular (non-periodic use is fine) 1/f noise in [0, 1]."""
    r = T.rng(seed)
    fy = np.fft.fftfreq(h)[:, None] * h / aniso[1]
    fx = np.fft.fftfreq(w)[None, :] * w / aniso[0]
    f = np.sqrt(fx * fx + fy * fy)
    f[0, 0] = 1.0
    amp = 1.0 / np.power(f, beta)
    amp[0, 0] = 0.0
    ph = r.uniform(0, 2 * np.pi, (h, w))
    return T.normalize(np.real(np.fft.ifft2(amp * np.exp(1j * ph)))).astype(np.float32)


def _scratch_mask(h: int, w: int, seed: int, n: int, length=(10, 60), width=(0.5, 1.1)) -> np.ndarray:
    r = T.rng(seed)

    def fn(d, k):
        for _ in range(n):
            x, y = r.uniform(0, w), r.uniform(0, h)
            ang = r.uniform(0, np.pi)
            L = r.uniform(*length)
            wd = r.uniform(*width)
            pts = [(x * k, y * k)]
            for _ in range(4):
                ang += r.normal(0, 0.25)
                x, y = x + math.cos(ang) * L / 4, y + math.sin(ang) * L / 4
                pts.append((x * k, y * k))
            d.line(pts, fill=255, width=max(1, int(wd * k)))
    return _mask(w, h, fn, 2)


def _age(col: np.ndarray, seed: int, *, fade: float = 0.25, grime: float = 0.35, runs: float = 0.3,
         scratches: int = 60, holes: int = 0, dirt_col: str = "#4a4236", rust_col: str = "#6b3a1e"):
    """Weathers a sign face: sun fade, grime collecting low, rain runs, rust streaks from the top,
    fine scratches and (optionally) bullet holes. Returns (colour, height, roughness)."""
    h, w, _ = col.shape
    low = _noise(h, w, 2.4, seed)
    mid = _noise(h, w, 1.6, seed + 1)
    fine = _noise(h, w, 0.8, seed + 2)
    lum = col.mean(-1, keepdims=True)
    f = fade * (0.6 + 0.6 * low[..., None])
    col = col + ((col * 0.62 + lum * 0.38 + 0.1) - col) * f
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    gmask = np.clip(T.smoothstep(0.45, 1.0, yy + 0.25 * (mid - 0.5)) * 0.8 + 0.35 * T.smoothstep(0.55, 0.95, low), 0, 1)
    col = _over(col, dirt_col, gmask * grime)
    streak = _noise(h, w, 1.4, seed + 3, aniso=(12.0, 1.0))
    rmask = T.smoothstep(0.66, 0.94, streak) * (1.0 - yy * 0.6) * runs
    col = _over(col, rust_col, rmask * 0.55)
    scr = _scratch_mask(h, w, seed + 4, scratches) if scratches else np.zeros((h, w), np.float32)
    col = _over(col, "#c9c6bd", scr * 0.45)
    height = 0.55 + 0.05 * fine + 0.04 * mid - 0.12 * scr
    rough = 0.45 + 0.25 * gmask * grime + 0.12 * rmask + 0.2 * scr + 0.05 * fine
    if holes:
        r = T.rng(seed + 5)
        ells = []
        rings = []
        for _ in range(holes):
            cx, cy, rr = r.uniform(0.1, 0.9) * w, r.uniform(0.15, 0.85) * h, r.uniform(3.0, 5.5)
            ells.append((cx, cy, rr, rr))
            rings.append((cx, cy, rr * 2.6, rr * 2.6))
        ring = _ellipse_mask(w, h, rings)
        hole = _ellipse_mask(w, h, ells)
        col = _over(col, "#cfcdc8", ring * 0.7)
        col = _over(col, "#0b0a09", hole)
        height = height - 0.45 * hole + 0.12 * ring
        rough = rough + 0.25 * ring
    col = col * (0.96 + 0.06 * fine[..., None])
    return np.clip(col, 0, 1), np.clip(height, 0, 1), np.clip(rough, 0, 1)


def _put(canvas: dict, rect_units, unit: int, col: np.ndarray, height: np.ndarray, rough: np.ndarray,
         metal: np.ndarray | float = 0.0) -> None:
    x, y, w, h = [int(v * unit) for v in rect_units]
    canvas["alb"][y:y + h, x:x + w] = col
    canvas["h"][y:y + h, x:x + w] = height
    canvas["r"][y:y + h, x:x + w] = rough
    canvas["m"][y:y + h, x:x + w] = metal


def _canvas(size: int) -> dict:
    return {"alb": np.full((size, size, 3), 0.5, np.float32), "h": np.full((size, size), 0.5, np.float32),
            "r": np.full((size, size), 0.6, np.float32), "m": np.zeros((size, size), np.float32)}


def _save_canvas(out, cv: dict, *, normal_strength: float = 3.0) -> None:
    T.save_pbr_set(out, np.clip(cv["alb"], 0, 1), np.clip(cv["h"], 0, 1), np.clip(cv["r"], 0, 1), metal=cv["m"],
                   normal_strength=normal_strength, ao_strength=0.8)


def _emboss(mask: np.ndarray, amount: float = 0.25) -> np.ndarray:
    """Raised letters / applied vinyl: height bump with a soft shoulder."""
    from scipy import ndimage
    return amount * ndimage.gaussian_filter(mask, 0.8)


# --------------------------------------------------------------------------------------------
# Atlas layouts (units of `UNIT` px). Keep in sync with props_roadside.py ATLAS_GAS / ATLAS_MOTEL.
# --------------------------------------------------------------------------------------------

UNIT = 256
GAS = {
    "gas_brand": (0, 0, 6, 2), "vending": (6, 0, 2, 4), "gas_prices": (0, 2, 4, 2), "pump_face": (4, 2, 2, 2),
    "canopy_band": (0, 4, 8, 1), "pump_vintage": (0, 5, 2, 3), "ice_front": (2, 5, 3, 1), "air_pump": (2, 6, 1, 2),
    "xray_label": (3, 6, 1, 1), "exit_sign": (4, 6, 1, 1), "oil_label": (3, 7, 2, 1), "newspaper": (5, 5, 2, 3),
    "box_labels": (7, 5, 1, 3),
}
MOTEL = {
    "motel_main": (0, 0, 5, 3), "vacancy": (5, 0, 3, 1), "no_box": (5, 1, 1, 1), "weekly": (6, 1, 2, 1),
    "amenities": (5, 2, 3, 1), "office": (0, 3, 2, 1), "laundry": (2, 3, 2, 1), "ice_label": (4, 3, 2, 1),
    "room_numbers": (6, 3, 2, 1), "clinic_sign": (0, 4, 6, 1), "clinic_hours": (6, 4, 2, 2),
    "quarantine": (0, 5, 2, 3), "xray_films": (2, 5, 2, 2), "eye_chart": (4, 5, 1, 2), "rates": (5, 5, 1, 2),
    "dnd": (7, 6, 1, 2), "staff_only": (2, 7, 2, 1), "lobby_strip": (4, 7, 3, 1),
}

GREEN = "#1f4a33"
CREAM = "#ece2c6"
RED = "#b3312a"
INK = "#1a1918"


def _cell(rect_units) -> tuple[int, int]:
    return int(rect_units[2] * UNIT), int(rect_units[3] * UNIT)


# --------------------------------------------------------------------------------------------
# road_signs: gas station + roadside machines
# --------------------------------------------------------------------------------------------

def _gas_brand(seed: int):
    w, h = _cell(GAS["gas_brand"])
    col = _fill(h, w, GREEN)
    band = _rect_mask(w, h, [(0, 330, w, 470)])
    col = _over(col, CREAM, band)
    pin = _rect_mask(w, h, [(0, 18, w, 30), (0, 302, w, 314)])
    col = _over(col, CREAM, pin * 0.9)
    chev = _poly_mask(w, h, [[(60, 60), (200, 60), (290, 175), (200, 290), (60, 290), (150, 175)]])
    col = _over(col, RED, chev)
    shadow = _text_mask(w, h, [{"s": "CORDON", "x": 880 + 9, "y": 62 + 9, "cap": 200, "stroke": 38, "track": 18, "align": "center"}])
    col = _over(col, "#0e2418", shadow * 0.8)
    t1 = _text_mask(w, h, [{"s": "CORDON", "x": 880, "y": 62, "cap": 200, "stroke": 38, "track": 18, "align": "center"}])
    col = _over(col, CREAM, t1)
    t2 = _text_mask(w, h, [{"s": "GAS & GARAGE", "x": w / 2, "y": 358, "cap": 84, "stroke": 17, "track": 14, "align": "center"}])
    col = _over(col, RED, t2)
    c, hh, r = _age(col, seed, fade=0.3, grime=0.3, runs=0.35, scratches=50, holes=3)
    return c, hh + _emboss(t1 + t2, 0.2), r


def _gas_prices(seed: int):
    w, h = _cell(GAS["gas_prices"])
    col = _fill(h, w, "#e8e3d4")
    border = 1.0 - _rect_mask(w, h, [(16, 16, w - 16, h - 16)])
    col = _over(col, GREEN, border)
    rows = [("REGULAR", "1.27"), ("PREMIUM", "1.39"), ("DIESEL", "1.19")]
    items = []
    digits = []
    tiles = []
    for i, (name, price) in enumerate(rows):
        y = 44 + i * 122
        items.append({"s": name, "x": 52, "y": y + 22, "cap": 52, "stroke": 11, "track": 6})
        x = 560
        for k, ch in enumerate(price):
            if ch == ".":
                digits.append({"s": ".", "x": x - 14, "y": y, "cap": 92, "stroke": 16})
                x += 18
                continue
            if not (i == 1 and k == 3):  # PREMIUM's last digit fell off: holes and a clean patch
                digits.append({"s": ch, "x": x + 6, "y": y, "cap": 92, "stroke": 16})
            tiles.append((x - 6, y - 10, x + 76, y + 102))
            x += 92
        digits.append({"s": "9", "x": x + 8, "y": y - 4, "cap": 40, "stroke": 7})
        items.append({"s": "/10", "x": x + 4, "y": y + 44, "cap": 26, "stroke": 5})
    col = _over(col, "#f4f1e8", _rect_mask(w, h, tiles, radius=6) * 0.55)
    tm = _text_mask(w, h, items)
    dm = _text_mask(w, h, digits)
    col = _over(col, INK, tm)
    col = _over(col, RED, dm)
    # Dale's cardboard strip zip-tied across the bottom: marker, uneven.
    r = T.rng(seed + 9)
    strip = _poly_mask(w, h, [[(120, 418), (900, 410), (904, 492), (118, 500)]])
    col = _over(col, "#a77d4f", strip)
    jit = lambda x, y: (r.normal(0, 1.6), r.normal(0, 1.6))  # noqa: E731
    marker = _text_mask(w, h, [{"s": "CASH ONLY - 10 GAL MAX", "x": 510, "y": 432, "cap": 42, "stroke": 8, "track": 3,
                                "align": "center", "italic": 0.12, "jitter": jit}])
    col = _over(col, INK, marker * strip)
    c, hh, rr = _age(col, seed, fade=0.35, grime=0.32, runs=0.25, scratches=40)
    return c, hh + _emboss(dm + tm, 0.15) - 0.1 * strip, rr + 0.25 * strip


def _canopy_band(seed: int):
    w, h = _cell(GAS["canopy_band"])
    col = _fill(h, w, GREEN)
    col = _over(col, CREAM, _rect_mask(w, h, [(0, 14, w, 24), (0, h - 24, w, h - 14)]))
    for cx in (110, w - 110):
        col = _over(col, RED, _poly_mask(w, h, [[(cx - 60, 60), (cx + 10, 60), (cx + 60, 128), (cx + 10, 196), (cx - 60, 196),
                                                 (cx - 10, 128)]]))
    t = _text_mask(w, h, [{"s": "CORDON GAS & GARAGE", "x": w / 2, "y": 70, "cap": 116, "stroke": 22, "track": 16,
                           "align": "center", "fit": w - 420}])
    col = _over(col, "#0e2418", np.roll(np.roll(t, 6, 0), 6, 1) * 0.7)
    col = _over(col, CREAM, t)
    c, hh, r = _age(col, seed, fade=0.3, grime=0.3, runs=0.5, scratches=30)
    return c, hh + _emboss(t, 0.2), r


def _lcd(col, w, h, rects, txt_items):
    m = _rect_mask(w, h, rects, radius=4)
    col = _over(col, "#3d4632", m)
    col = _over(col, "#59654a", _text_mask(w, h, txt_items) * m * 0.8)
    return col


def _pump_face(seed: int):
    w, h = _cell(GAS["pump_face"])
    col = _fill(h, w, "#d9d5c8")
    col = _over(col, GREEN, _rect_mask(w, h, [(0, 0, w, 92)]))
    col = _over(col, CREAM, _text_mask(w, h, [{"s": "CORDON", "x": w / 2, "y": 24, "cap": 48, "stroke": 10, "track": 6,
                                                "align": "center"}]))
    col = _over(col, RED, _rect_mask(w, h, [(0, 92, w, 104)]))
    labels = [{"s": "TOTAL SALE", "x": 40, "y": 124, "cap": 18, "stroke": 4, "track": 2},
              {"s": "GALLONS", "x": 40, "y": 236, "cap": 18, "stroke": 4, "track": 2},
              {"s": "PRICE PER GALLON", "x": 40, "y": 340, "cap": 14, "stroke": 3, "track": 2}]
    col = _over(col, INK, _text_mask(w, h, labels))
    col = _lcd(col, w, h, [(40, 150, 472, 222), (40, 262, 472, 326), (40, 362, 300, 404)],
               [{"s": "88.88", "x": 456, "y": 160, "cap": 52, "stroke": 8, "align": "right", "italic": 0.15},
                {"s": "88.888", "x": 456, "y": 270, "cap": 46, "stroke": 7, "align": "right", "italic": 0.15},
                {"s": "1.279", "x": 292, "y": 368, "cap": 30, "stroke": 5, "align": "right", "italic": 0.15}])
    col = _over(col, "#c9a332", _rect_mask(w, h, [(318, 360, 472, 406)], radius=6))
    col = _over(col, INK, _text_mask(w, h, [{"s": "UNLEADED", "x": 395, "y": 373, "cap": 20, "stroke": 4, "align": "center"}]))
    col = _over(col, INK, _text_mask(w, h, [{"s": "PLEASE PAY CASHIER FIRST", "x": w / 2, "y": 432, "cap": 18, "stroke": 4,
                                              "align": "center", "track": 2},
                                             {"s": "NO SMOKING * STOP ENGINE", "x": w / 2, "y": 466, "cap": 16, "stroke": 3,
                                              "align": "center", "track": 2}]))
    c, hh, r = _age(col, seed, fade=0.25, grime=0.4, runs=0.2, scratches=70)
    return c, hh, r


def _pump_vintage(seed: int):
    w, h = _cell(GAS["pump_vintage"])
    col = _fill(h, w, "#e9e4d6")
    col = _over(col, RED, _rect_mask(w, h, [(0, 0, w, 150)]))
    col = _over(col, CREAM, _text_mask(w, h, [{"s": "CORDON", "x": w / 2, "y": 40, "cap": 70, "stroke": 14, "track": 8,
                                                "align": "center"}]))
    col = _over(col, GREEN, _rect_mask(w, h, [(0, 150, w, 166)]))
    for i, (lbl, y) in enumerate((("SALE", 196), ("GALLONS", 386))):
        col = _over(col, INK, _text_mask(w, h, [{"s": lbl, "x": w / 2, "y": y, "cap": 26, "stroke": 5, "align": "center", "track": 4}]))
        win = _rect_mask(w, h, [(56, y + 40, w - 56, y + 150)], radius=10)
        col = _over(col, "#181816", win)
        for k in range(4):
            x0 = 72 + k * 94
            col = _over(col, "#e6e0d0", _rect_mask(w, h, [(x0, y + 50, x0 + 80, y + 140)], radius=4))
            dg = "0129"[k] if i == 0 else "0738"[k]
            col = _over(col, INK, _text_mask(w, h, [{"s": dg, "x": x0 + 40, "y": y + 64, "cap": 62, "stroke": 9, "align": "center"}]))
    col = _over(col, INK, _text_mask(w, h, [{"s": "PRICE PER GAL", "x": w / 2, "y": 590, "cap": 20, "stroke": 4,
                                              "align": "center", "track": 3}]))
    col = _over(col, "#181816", _rect_mask(w, h, [(156, 626, 356, 690)], radius=6))
    col = _over(col, CREAM, _text_mask(w, h, [{"s": "1.19", "x": w / 2, "y": 636, "cap": 42, "stroke": 7, "align": "center"}]))
    col = _over(col, GREEN, _rect_mask(w, h, [(0, 716, w, h)]))
    col = _over(col, CREAM, _text_mask(w, h, [{"s": "REGULAR", "x": w / 2, "y": 728, "cap": 26, "stroke": 5,
                                                "align": "center", "track": 5}]))
    return _age(col, seed, fade=0.4, grime=0.4, runs=0.3, scratches=80)


def _vending(seed: int):
    w, h = _cell(GAS["vending"])
    col = _fill(h, w, "#a3231f")
    pw = 360
    col = _over(col, "#2a2624", _rect_mask(w, h, [(pw, 0, w, h)]))
    # Swoosh band + logo.
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    wave = np.abs(xx - (300 + 40 * np.sin(yy / h * 6.0 + 0.6))) < 22
    col = _over(col, "#f1ece0", (wave & (xx < pw)).astype(np.float32) * 0.95)
    col = _over(col, "#f1ece0", _text_mask(w, h, [{"s": "ICE COLD", "x": pw / 2, "y": 34, "cap": 40, "stroke": 8,
                                                    "align": "center", "track": 4, "fit": pw - 50}]))
    # "TAMSIN" set vertically (drawn on its side, rotated into the panel), "SPRINGS" under it.
    side = Image.new("L", (760 * 4, 200 * 4), 0)
    _draw_text(ImageDraw.Draw(side), 4, "TAMSIN", 380, 24, 140, 28, track=12, align="center", italic=0.18)
    side = side.resize((760, 200), Image.BOX).transpose(Image.Transpose.ROTATE_90)
    vm = np.zeros((h, w), np.float32)
    vm[118:118 + 760, 80:80 + 200] = np.asarray(side, np.float32) / 255.0
    col = _over(col, "#140f0e", np.roll(np.roll(vm, 7, 0), 7, 1) * 0.6)
    col = _over(col, "#f6f1e6", vm)
    col = _over(col, "#140f0e", _rect_mask(w, h, [(24, 908, pw - 24, 980)], radius=8) * 0.55)
    col = _over(col, "#f1ece0", _text_mask(w, h, [{"s": "SPRINGS", "x": pw / 2, "y": 926, "cap": 36, "stroke": 7,
                                                    "align": "center", "track": 8, "fit": pw - 70}]))
    flavours = ["COLA", "DIET", "ROOT BR", "ORANGE", "LEMON", "WATER"]
    for i, fl in enumerate(flavours):
        y0 = 70 + i * 120
        col = _over(col, ["#8f1d1a", "#c8c4bb", "#5a3220", "#d0752b", "#d9c24a", "#5d86b0"][i],
                     _rect_mask(w, h, [(pw + 22, y0, w - 22, y0 + 56)], radius=4))
        col = _over(col, "#f6f1e6" if i not in (1, 4) else INK,
                    _text_mask(w, h, [{"s": fl, "x": (pw + w) / 2, "y": y0 + 16, "cap": 22, "stroke": 4, "align": "center"}]))
    col = _over(col, "#e8e2d2", _text_mask(w, h, [{"s": "$.75", "x": (pw + w) / 2, "y": 820, "cap": 34, "stroke": 6,
                                                    "align": "center"}]))
    col = _over(col, "#9a958c", _rect_mask(w, h, [(pw + 50, 880, w - 50, 900), (pw + 60, 930, w - 60, 990)], radius=3))
    return _age(col, seed, fade=0.35, grime=0.3, runs=0.2, scratches=90)


def _ice_front(seed: int):
    w, h = _cell(GAS["ice_front"])
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    col = (_c("#2f6c9c") * (1 - yy) + _c("#8fc1de") * yy) * np.ones((h, w, 3), np.float32)
    flakes = []
    r = T.rng(seed + 3)
    for _ in range(14):
        cx, cy, s = r.uniform(40, w - 40), r.uniform(30, h - 30), r.uniform(10, 22)
        for k in range(3):
            a = k * math.pi / 3
            flakes.append((cx - s * math.cos(a), cy - s * math.sin(a), cx + s * math.cos(a), cy + s * math.sin(a)))

    def draw_flakes(d, k):
        for (x0, y0, x1, y1) in flakes:
            d.line([(x0 * k, y0 * k), (x1 * k, y1 * k)], fill=255, width=3 * k)
    col = _over(col, "#dcecf5", _mask(w, h, draw_flakes) * 0.55)
    t = _text_mask(w, h, [{"s": "ICE", "x": w / 2, "y": 34, "cap": 150, "stroke": 34, "track": 30, "align": "center"}])
    col = _over(col, "#163a57", np.roll(np.roll(t, 7, 0), 7, 1) * 0.8)
    col = _over(col, "#f4f8fa", t)
    col = _over(col, "#f4f8fa", _text_mask(w, h, [{"s": "PARTY ICE", "x": 120, "y": 200, "cap": 26, "stroke": 5, "track": 4,
                                                    "align": "center"},
                                                   {"s": "10 LB $1.49", "x": w - 130, "y": 200, "cap": 26, "stroke": 5,
                                                    "track": 3, "align": "center"}]))
    return _age(col, seed, fade=0.3, grime=0.3, runs=0.4, scratches=60)


def _newspaper(seed: int):
    w, h = _cell(GAS["newspaper"])
    col = _fill(h, w, "#2b4f86")
    col = _over(col, "#f0ebdc", _text_mask(w, h, [{"s": "TAMSIN VALLEY", "x": w / 2, "y": 20, "cap": 40, "stroke": 8,
                                                    "track": 4, "align": "center"},
                                                   {"s": "COURIER", "x": w / 2, "y": 74, "cap": 52, "stroke": 10,
                                                    "track": 10, "align": "center"},
                                                   {"s": "50 CENTS", "x": w / 2, "y": 140, "cap": 18, "stroke": 4,
                                                    "track": 4, "align": "center"}]))
    # Window: a yellowed front page.
    px0, py0, px1, py1 = 40, 180, w - 40, 600
    col = _over(col, "#141414", _rect_mask(w, h, [(px0 - 10, py0 - 10, px1 + 10, py1 + 10)], radius=6))
    page = _rect_mask(w, h, [(px0, py0, px1, py1)])
    col = _over(col, "#d8cfb4", page)
    ink = [{"s": "THE TAMSIN VALLEY COURIER", "x": w / 2, "y": py0 + 14, "cap": 20, "stroke": 4, "track": 1, "align": "center"},
           {"s": "ROUTE 9 CLOSED", "x": w / 2, "y": py0 + 58, "cap": 44, "stroke": 8, "track": 2, "align": "center",
            "fit": px1 - px0 - 30},
           {"s": "AT CORDON", "x": w / 2, "y": py0 + 112, "cap": 44, "stroke": 8, "track": 2, "align": "center"},
           {"s": "GUARD SETS ROADBLOCK - MINE ILLNESS", "x": w / 2, "y": py0 + 170, "cap": 12, "stroke": 2.6, "align": "center"},
           {"s": "SPREADS TO PELL'S CROSSING", "x": w / 2, "y": py0 + 190, "cap": 12, "stroke": 2.6, "align": "center"}]
    col = _over(col, "#1d1b18", _text_mask(w, h, ink) * page)
    col = _over(col, "#77736a", _rect_mask(w, h, [(px0 + 16, py0 + 218, px0 + 200, py1 - 20)]) * 0.9)
    lines = [(px0 + 214, py0 + 222 + k * 13, px1 - 16 - (40 if k % 6 == 5 else 0), py0 + 226 + k * 13) for k in range(13)]
    col = _over(col, "#3a3732", _rect_mask(w, h, lines) * 0.75)
    col = _over(col, "#cfcfcf", _rect_mask(w, h, [(px0, py0, px1, py1)]) * 0.12)  # glass sheen
    col = _over(col, "#f0ebdc", _text_mask(w, h, [{"s": "QUARTERS ONLY", "x": w / 2, "y": 640, "cap": 22, "stroke": 4,
                                                    "track": 3, "align": "center"},
                                                   {"s": "TAKE ONE", "x": w / 2, "y": 690, "cap": 18, "stroke": 4,
                                                    "track": 3, "align": "center"}]))
    return _age(col, seed, fade=0.3, grime=0.4, runs=0.3, scratches=70)


def _air_pump(seed: int):
    w, h = _cell(GAS["air_pump"])
    col = _fill(h, w, "#b02c25")
    col = _over(col, "#f0ebe0", _text_mask(w, h, [{"s": "AIR", "x": w / 2, "y": 40, "cap": 92, "stroke": 18, "track": 8,
                                                    "align": "center"},
                                                   {"s": "WATER", "x": w / 2, "y": 160, "cap": 36, "stroke": 7, "track": 4,
                                                    "align": "center"}]))
    col = _over(col, "#f0ebe0", _rect_mask(w, h, [(30, 230, w - 30, 236)]))
    col = _over(col, "#f0ebe0", _text_mask(w, h, [{"s": "$.75", "x": w / 2, "y": 260, "cap": 54, "stroke": 10,
                                                    "align": "center"},
                                                   {"s": "4 MINUTES", "x": w / 2, "y": 340, "cap": 20, "stroke": 4,
                                                    "align": "center", "track": 2},
                                                   {"s": "QUARTERS", "x": w / 2, "y": 380, "cap": 20, "stroke": 4,
                                                    "align": "center", "track": 2}]))
    col = _over(col, "#1d1b19", _rect_mask(w, h, [(80, 430, 176, 470)], radius=6))
    return _age(col, seed, fade=0.35, grime=0.4, runs=0.4, scratches=50)


def _trefoil(w, h, cx, cy, r):
    polys = []
    for k in range(3):
        a0 = math.radians(-90 + k * 120 - 30)
        a1 = math.radians(-90 + k * 120 + 30)
        pts = [(cx + r * 0.32 * math.cos(a0), cy + r * 0.32 * math.sin(a0))]
        for i in range(9):
            a = a0 + (a1 - a0) * i / 8
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        pts.append((cx + r * 0.32 * math.cos(a1), cy + r * 0.32 * math.sin(a1)))
        polys.append(pts)
    return np.clip(_poly_mask(w, h, polys) + _ellipse_mask(w, h, [(cx, cy, r * 0.2, r * 0.2)]), 0, 1)


def _xray_label(seed: int):
    w, h = _cell(GAS["xray_label"])
    col = _fill(h, w, "#e2c23a")
    col = _over(col, INK, 1.0 - _rect_mask(w, h, [(10, 10, w - 10, h - 10)]))
    col = _over(col, "#6a1e6e", _trefoil(w, h, w / 2, 100, 70))
    col = _over(col, INK, _text_mask(w, h, [{"s": "CAUTION", "x": w / 2, "y": 186, "cap": 24, "stroke": 5, "align": "center", "track": 2},
                                             {"s": "X-RAY", "x": w / 2, "y": 218, "cap": 22, "stroke": 5, "align": "center", "track": 3}]))
    return _age(col, seed, fade=0.2, grime=0.2, runs=0.0, scratches=20)


def _exit_sign(seed: int):
    w, h = _cell(GAS["exit_sign"])
    col = _fill(h, w, "#e8e4da")
    col = _over(col, "#b8261f", _text_mask(w, h, [{"s": "EXIT", "x": w / 2, "y": 70, "cap": 78, "stroke": 15, "track": 6,
                                                   "align": "center"},
                                                  {"s": ">", "x": w / 2, "y": 172, "cap": 46, "stroke": 9, "align": "center"}]))
    return _age(col, seed, fade=0.15, grime=0.35, runs=0.0, scratches=10)


def _oil_label(seed: int):
    w, h = _cell(GAS["oil_label"])
    col = np.zeros((h, w, 3), np.float32)
    grades = [("10W-30", "#1d3f6e"), ("10W-40", "#7a1f1b"), ("5W-30", "#2f5f36"), ("30", "#2a2a2a")]
    cw = w // 4
    for i, (g, bg) in enumerate(grades):
        sl = (slice(0, h), slice(i * cw, (i + 1) * cw))
        col[sl] = _c(bg)
        sub = col[sl]
        m = _text_mask(cw, h, [{"s": "CORDON", "x": cw / 2, "y": 30, "cap": 22, "stroke": 4, "align": "center", "track": 2,
                                "fit": cw - 14},
                               {"s": "MOTOR OIL", "x": cw / 2, "y": 64, "cap": 14, "stroke": 3, "align": "center", "track": 2,
                                "fit": cw - 14},
                               {"s": g, "x": cw / 2, "y": 110, "cap": 40, "stroke": 8, "align": "center", "fit": cw - 16},
                               {"s": "1 QT", "x": cw / 2, "y": 196, "cap": 18, "stroke": 4, "align": "center"}])
        sub = _over(sub, "#e9c94a", _rect_mask(cw, h, [(0, 168, cw, 180)]))
        col[sl] = _over(sub, "#f2ede1", m)
    return _age(col, seed, fade=0.2, grime=0.3, runs=0.0, scratches=30)


def _box_labels(seed: int):
    w, h = _cell(GAS["box_labels"])
    col = _fill(h, w, "#c49a64")
    labels = ["GAUZE", "GLOVES", "SYRINGES", "SALINE", "SPLINTS", "MASKS"]
    for i, s in enumerate(labels):
        y0 = i * 128
        col = _over(col, "#e7e2d4", _rect_mask(w, h, [(18, y0 + 22, w - 18, y0 + 106)], radius=4))
        col = _over(col, "#2c4f7a", _text_mask(w, h, [{"s": s, "x": w / 2 + 10, "y": y0 + 46, "cap": 30, "stroke": 6,
                                                       "align": "center", "track": 2, "fit": w - 80}]))
        col = _over(col, RED, _rect_mask(w, h, [(28, y0 + 30, 44, y0 + 98)]))
    return _age(col, seed, fade=0.15, grime=0.4, runs=0.0, scratches=40)


@texture("road_signs", size=2048, seed=9101)
def road_signs(size: int, seed: int, out) -> None:
    """Gas station + roadside machine signage atlas (layout GAS, 256 px units)."""
    cv = _canvas(size)
    makers = {"gas_brand": _gas_brand, "gas_prices": _gas_prices, "canopy_band": _canopy_band, "pump_face": _pump_face,
              "pump_vintage": _pump_vintage, "vending": _vending, "ice_front": _ice_front, "newspaper": _newspaper,
              "air_pump": _air_pump, "xray_label": _xray_label, "exit_sign": _exit_sign, "oil_label": _oil_label,
              "box_labels": _box_labels}
    for i, (name, fn) in enumerate(makers.items()):
        c, hh, r = fn(seed + i * 37)
        _put(cv, GAS[name], UNIT, c, hh, r)
    _save_canvas(out, cv)


# --------------------------------------------------------------------------------------------
# road_signs_motel: Timberline Motel + Tamsin Valley Clinic
# --------------------------------------------------------------------------------------------

def _larch(w, h, x0, y0, s):
    """Golden larch silhouette (stacked drooping tiers) with a trunk."""
    polys = []
    for k in range(6):
        top = y0 + k * 0.15 * s
        half = 0.1 * s + k * 0.055 * s
        polys.append([(x0, top), (x0 + half, top + 0.24 * s), (x0 + half * 0.35, top + 0.2 * s),
                      (x0 - half * 0.35, top + 0.2 * s), (x0 - half, top + 0.24 * s)])
    trunk = [(x0 - 0.035 * s, y0 + 0.95 * s), (x0 + 0.035 * s, y0 + 0.95 * s), (x0 + 0.035 * s, y0 + 1.12 * s),
             (x0 - 0.035 * s, y0 + 1.12 * s)]
    return _poly_mask(w, h, polys), _poly_mask(w, h, [trunk])


def _motel_main(seed: int):
    w, h = _cell(MOTEL["motel_main"])
    col = _fill(h, w, "#18382a")
    ring = _rect_mask(w, h, [(22, 22, w - 22, h - 22)], radius=40) * (1.0 - _rect_mask(w, h, [(36, 36, w - 36, h - 36)], radius=30))
    col = _over(col, "#c9762c", ring)
    tree, trunk = _larch(w, h, 232, 100, 480)
    col = _over(col, "#d9a336", tree)
    col = _over(col, "#5a3a22", trunk)
    sh = _text_mask(w, h, [{"s": "TIMBERLINE", "x": 790 + 8, "y": 110 + 8, "cap": 150, "stroke": 30, "track": 12,
                            "align": "center", "italic": 0.12, "fit": 860}])
    col = _over(col, "#07150e", sh * 0.8)
    t1 = _text_mask(w, h, [{"s": "TIMBERLINE", "x": 790, "y": 110, "cap": 150, "stroke": 30, "track": 12, "align": "center",
                            "italic": 0.12, "fit": 860}])
    col = _over(col, "#efe5c8", t1)
    t2 = _text_mask(w, h, [{"s": "MOTEL", "x": 790, "y": 330, "cap": 190, "stroke": 40, "track": 40, "align": "center",
                            "fit": 800}])
    col = _over(col, "#efe5c8", np.clip(_grow(t2, 7), 0, 1))
    col = _over(col, "#c23b23", t2)
    col = _over(col, "#efe5c8", _text_mask(w, h, [{"s": "EST. 1961", "x": 790, "y": 620, "cap": 40, "stroke": 8, "track": 10,
                                                    "align": "center"}]))
    c, hh, r = _age(col, seed, fade=0.35, grime=0.3, runs=0.45, scratches=60, holes=4)
    return c, hh + _emboss(t1 + t2, 0.25), r


def _grow(m: np.ndarray, px: int) -> np.ndarray:
    from scipy import ndimage
    return ndimage.grey_dilation(m, size=(px * 2 + 1, px * 2 + 1))


def _panel(rect_name: str, seed: int, text: str, fg: str, bg: str, cap: float, stroke: float, *, track=8.0, border=None,
           fade=0.3, runs=0.3, y=None):
    w, h = _cell(MOTEL[rect_name])
    col = _fill(h, w, bg)
    if border:
        col = _over(col, border, 1.0 - _rect_mask(w, h, [(14, 14, w - 14, h - 14)], radius=10))
    t = _text_mask(w, h, [{"s": text, "x": w / 2, "y": (h - cap) / 2 if y is None else y, "cap": cap, "stroke": stroke,
                           "track": track, "align": "center", "fit": w - 70}])
    col = _over(col, fg, t)
    c, hh, r = _age(col, seed, fade=fade, grime=0.3, runs=runs, scratches=40)
    return c, hh + _emboss(t, 0.2), r


def _room_numbers(seed: int):
    w, h = _cell(MOTEL["room_numbers"])
    col = np.zeros((h, w, 3), np.float32)
    for i in range(8):
        cx, cy = (i % 4) * 128 + 64, (i // 4) * 128 + 64
        sub = np.zeros((128, 128, 3), np.float32) + _c("#b8954c")
        ring = 1.0 - _rect_mask(128, 128, [(8, 8, 120, 120)], radius=12)
        sub = _over(sub, "#6e5528", ring)
        t = _text_mask(128, 128, [{"s": str(i + 1), "x": 64, "y": 26, "cap": 76, "stroke": 13, "align": "center"}])
        sub = _over(sub, "#2a2015", t)
        col[cy - 64:cy + 64, cx - 64:cx + 64] = sub
    c, hh, r = _age(col, seed, fade=0.1, grime=0.45, runs=0.1, scratches=30)
    return c, hh, r * 0.8, 0.6


def _clinic_sign(seed: int):
    w, h = _cell(MOTEL["clinic_sign"])
    col = _fill(h, w, "#e9e6dd")
    col = _over(col, "#2c4f7a", _rect_mask(w, h, [(0, 0, w, 26), (0, h - 26, w, h)]))
    cross = _rect_mask(w, h, [(70, 98, 190, 158), (100, 68, 160, 188)])
    col = _over(col, "#b8261f", cross)
    t = _text_mask(w, h, [{"s": "TAMSIN VALLEY CLINIC", "x": (w + 240) / 2, "y": 78, "cap": 100, "stroke": 18, "track": 10,
                           "align": "center", "fit": w - 300}])
    col = _over(col, "#2c4f7a", t)
    c, hh, r = _age(col, seed, fade=0.25, grime=0.35, runs=0.4, scratches=40)
    return c, hh + _emboss(t + cross, 0.2), r


def _clinic_hours(seed: int):
    w, h = _cell(MOTEL["clinic_hours"])
    col = _fill(h, w, "#2c4f7a")
    col = _over(col, "#e9e6dd", _text_mask(w, h, [
        {"s": "TAMSIN VALLEY", "x": w / 2, "y": 40, "cap": 40, "stroke": 8, "align": "center", "track": 4, "fit": w - 60},
        {"s": "CLINIC", "x": w / 2, "y": 94, "cap": 40, "stroke": 8, "align": "center", "track": 6},
        {"s": "MON - FRI  8 - 5", "x": w / 2, "y": 210, "cap": 30, "stroke": 6, "align": "center"},
        {"s": "SAT  9 - 12", "x": w / 2, "y": 258, "cap": 30, "stroke": 6, "align": "center"},
        {"s": "WALK-INS WELCOME", "x": w / 2, "y": 330, "cap": 24, "stroke": 5, "align": "center", "track": 2},
        {"s": "DR. A. VOSS", "x": w / 2, "y": 410, "cap": 26, "stroke": 5, "align": "center", "track": 3}]))
    col = _over(col, "#b8261f", _rect_mask(w, h, [(232, 160, 280, 174), (249, 144, 263, 190)]))
    return _age(col, seed, fade=0.3, grime=0.3, runs=0.3, scratches=40)


def _quarantine(seed: int):
    w, h = _cell(MOTEL["quarantine"])
    col = _fill(h, w, "#e6e0cf")
    col = _over(col, "#b8261f", _rect_mask(w, h, [(24, 24, w - 24, 150)]))
    col = _over(col, "#f4efe2", _text_mask(w, h, [{"s": "NOTICE", "x": w / 2, "y": 50, "cap": 74, "stroke": 14, "track": 10,
                                                    "align": "center"}]))
    body = [("QUARANTINE", 190, 50, 9), ("IN EFFECT", 256, 40, 8), ("NO ENTRY OR EXIT", 340, 28, 5.5),
            ("WITHOUT AUTHORIZATION", 380, 22, 4.5), ("CORDON MEDICAL", 470, 30, 6), ("AUTHORITY", 512, 30, 6),
            ("BY ORDER OF THE COUNTY", 590, 18, 3.6), ("HEALTH OFFICER  03/12", 618, 18, 3.6),
            ("DO NOT REMOVE", 700, 24, 5)]
    col = _over(col, INK, _text_mask(w, h, [{"s": s, "x": w / 2, "y": y, "cap": c, "stroke": st, "align": "center", "track": 2}
                                            for s, y, c, st in body]))
    # Staple holes, a damp fold line, tape at the corners.
    col = _over(col, "#cbbf96", _rect_mask(w, h, [(10, 10, 70, 40), (w - 70, 10, w - 10, 40)]) * 0.8)
    col = _over(col, "#a89c80", _rect_mask(w, h, [(0, 380, w, 383)]) * 0.5)
    return _age(col, seed, fade=0.25, grime=0.45, runs=0.25, scratches=10, dirt_col="#6b5d44", rust_col="#8a6a40")


def _xray_films(seed: int):
    w, h = _cell(MOTEL["xray_films"])
    col = _fill(h, w, "#dde4e6")
    r = T.rng(seed + 7)
    for k in range(2):
        x0 = 12 + k * 250
        film = _rect_mask(w, h, [(x0, 40, x0 + 238, 470)], radius=4)
        col = _over(col, "#0d1114", film)
        cx = x0 + 119
    
        def ribs_fn(d, s, cx=cx):
            for i in range(9):
                y = 120 + i * 33
                for sgn in (-1, 1):
                    pts = [(cx + sgn * 10, y), (cx + sgn * 55, y - 14 + i), (cx + sgn * 92, y + 4 + i * 2),
                           (cx + sgn * 98, y + 30 + i * 2)]
                    d.line([(px * s, py * s) for px, py in pts], fill=200, width=5 * s, joint="curve")
            d.line([(cx * s, 70 * s), (cx * s, 430 * s)], fill=230, width=14 * s)
            d.line([((cx - 70) * s, 100 * s), ((cx - 20) * s, 92 * s)], fill=210, width=9 * s)
            d.line([((cx + 70) * s, 100 * s), ((cx + 20) * s, 92 * s)], fill=210, width=9 * s)
        bones = _mask(w, h, ribs_fn)
        lungs = _ellipse_mask(w, h, [(cx - 50, 255, 42, 135), (cx + 50, 255, 42, 135)])
        col = _over(col, "#3d4a52", lungs * film * 0.5)
        # The Bloom: cotton-wool mottling that worsens from film 1 to film 2.
        ells = [(cx + r.uniform(-85, 85), r.uniform(150, 380), r.uniform(5, 16) * (1 + k), r.uniform(5, 14) * (1 + k))
                for _ in range(10 + 18 * k)]
        mottle = _ellipse_mask(w, h, ells) * lungs
        col = _over(col, "#c9d2d6", T.blur(mottle, 2.0) * 0.85)
        col = _over(col, "#d9e0e3", bones * film * 0.8)
        col = _over(col, "#e5e8e8", _text_mask(w, h, [{"s": ("PT 1  03/02" if k == 0 else "PT 1  03/09"), "x": x0 + 14,
                                                        "y": 50, "cap": 16, "stroke": 3.4}]))
        col = _over(col, "#e5e8e8", _text_mask(w, h, [{"s": "L" if k else "R", "x": x0 + 210, "y": 430, "cap": 22, "stroke": 4}]))
    return _age(col, seed, fade=0.05, grime=0.2, runs=0.0, scratches=20)


def _eye_chart(seed: int):
    w, h = _cell(MOTEL["eye_chart"])
    col = _fill(h, w, "#efebe0")
    rows = ["E", "FP", "TOZ", "LPED", "PECFD", "EDFCZP", "FELOPZD"]
    items = []
    y = 26
    for i, s in enumerate(rows):
        cap = [92, 56, 40, 30, 23, 18, 14][i]
        items.append({"s": s, "x": w / 2, "y": y, "cap": cap, "stroke": max(2.4, cap * 0.17), "align": "center",
                      "track": cap * 0.4})
        y += cap + [26, 22, 20, 18, 16, 14, 12][i]
    col = _over(col, INK, _text_mask(w, h, items))
    col = _over(col, "#b8261f", _rect_mask(w, h, [(20, y + 6, w - 20, y + 9)]))
    return _age(col, seed, fade=0.25, grime=0.25, runs=0.0, scratches=10)


def _rates(seed: int):
    w, h = _cell(MOTEL["rates"])
    col = _fill(h, w, "#3a2a1c")
    col = _over(col, "#b8954c", 1.0 - _rect_mask(w, h, [(16, 16, w - 16, h - 16)], radius=12))
    lines = [("ROOM", 40, 36, 7), ("RATES", 84, 36, 7), ("SINGLE $29", 160, 30, 6), ("DOUBLE $34", 206, 30, 6),
             ("WEEKLY $140", 252, 30, 6), ("CHECK OUT", 330, 22, 4.5), ("11 AM", 360, 22, 4.5), ("NO PETS", 408, 22, 4.5),
             ("CASH ONLY", 450, 22, 4.5)]
    col = _over(col, "#efe5c8", _text_mask(w, h, [{"s": s, "x": w / 2, "y": y, "cap": c, "stroke": st, "align": "center",
                                                    "track": 2, "fit": w - 50} for s, y, c, st in lines]))
    return _age(col, seed, fade=0.1, grime=0.35, runs=0.0, scratches=30)


def _dnd(seed: int):
    w, h = _cell(MOTEL["dnd"])
    col = _fill(h, w, "#c84a2b")
    col = _over(col, "#f1e9d6", _ellipse_mask(w, h, [(w / 2, 70, 44, 44)]))
    col = _over(col, "#c84a2b", _ellipse_mask(w, h, [(w / 2, 70, 30, 30)]))
    col = _over(col, "#f1e9d6", _text_mask(w, h, [{"s": "PLEASE", "x": w / 2, "y": 170, "cap": 28, "stroke": 5, "align": "center", "track": 3},
                                                   {"s": "DO NOT", "x": w / 2, "y": 230, "cap": 40, "stroke": 8, "align": "center", "track": 3},
                                                   {"s": "DISTURB", "x": w / 2, "y": 290, "cap": 40, "stroke": 8, "align": "center", "track": 1}]))
    return _age(col, seed, fade=0.25, grime=0.3, runs=0.0, scratches=30)


def _lobby_strip(seed: int):
    w, h = _cell(MOTEL["lobby_strip"])
    col = _fill(h, w, "#efe9da")
    col = _over(col, "#18382a", _rect_mask(w, h, [(0, 0, w, 40), (0, h - 40, w, h)]))
    col = _over(col, "#18382a", _text_mask(w, h, [{"s": "PLEASE RING BELL", "x": w / 2, "y": 70, "cap": 40, "stroke": 8,
                                                    "align": "center", "track": 6},
                                                   {"s": "FOR SERVICE", "x": w / 2, "y": 134, "cap": 40, "stroke": 8,
                                                    "align": "center", "track": 6}]))
    return _age(col, seed, fade=0.15, grime=0.3, runs=0.0, scratches=30)


@texture("road_signs_motel", size=2048, seed=9201)
def road_signs_motel(size: int, seed: int, out) -> None:
    """Timberline Motel + Tamsin Valley Clinic signage atlas (layout MOTEL, 256 px units)."""
    cv = _canvas(size)
    G, C2 = "#18382a", "#efe5c8"
    jobs = {
        "motel_main": lambda s: _motel_main(s),
        "vacancy": lambda s: _panel("vacancy", s, "VACANCY", "#c23b23", C2, 120, 24, track=14, border=G),
        "no_box": lambda s: _panel("no_box", s, "NO", C2, "#c23b23", 120, 26, track=10, border=G),
        "weekly": lambda s: _panel("weekly", s, "WEEKLY RATES", C2, G, 64, 13, track=6, border="#c9762c"),
        "amenities": lambda s: _panel("amenities", s, "COLOR TV * ICE * PHONES", G, C2, 58, 12, track=5, border=G),
        "office": lambda s: _panel("office", s, "OFFICE", C2, G, 110, 22, track=14, border="#c9762c"),
        "laundry": lambda s: _panel("laundry", s, "GUEST LAUNDRY", G, C2, 58, 12, track=5, border=G),
        "ice_label": lambda s: _panel("ice_label", s, "ICE", "#f4f8fa", "#2f6c9c", 140, 30, track=26, border="#f4f8fa"),
        "room_numbers": _room_numbers,
        "clinic_sign": _clinic_sign,
        "clinic_hours": _clinic_hours,
        "quarantine": _quarantine,
        "xray_films": _xray_films,
        "eye_chart": _eye_chart,
        "rates": _rates,
        "dnd": _dnd,
        "staff_only": lambda s: _panel("staff_only", s, "STAFF ONLY", "#f1ede2", "#2c4f7a", 74, 15, track=8, border="#f1ede2"),
        "lobby_strip": _lobby_strip,
    }
    for i, (name, fn) in enumerate(jobs.items()):
        res = fn(seed + i * 41)
        metal = res[3] if len(res) > 3 else 0.0
        _put(cv, MOTEL[name], UNIT, res[0], res[1], res[2], metal)
    _save_canvas(out, cv)


# --------------------------------------------------------------------------------------------
# road_spray: survivor spray paint on plywood (2 x 4 sheets of 512 x 256)
# --------------------------------------------------------------------------------------------

SPRAY = [
    (("SICK INSIDE", "DO NOT OPEN"), "#8e1f17"),
    (("NO GAS", "NO CASH"), "#141312"),
    (("QUARANTINE", "KEEP OUT"), "#8e1f17"),
    (("USE BATHROOMS", ">"), "#141312"),
    (("STAY OFF", "WALKWAY"), "#8e1f17"),
    (("HELP", "ROOM 6"), "#141312"),
    (("DEAD INSIDE",), "#8e1f17"),
    (("GONE TO", "CORDON"), "#141312"),
]


@texture("road_spray", size=1024, seed=9301)
def road_spray(size: int, seed: int, out) -> None:
    """Weathered exterior plywood sheets (512 x 256 cells, row-major from the top-left) with
    spray-painted survivor messages in the stroke font: shaky, oversprayed, dripping."""
    r = T.rng(seed)
    warp = T.spectral(size, 2.0, seed)
    band = T.spectral(size, 1.2, seed + 1, anisotropy=(1.0, 5.0))
    # Plywood face veneer: grain runs along the sheet (x).
    fig = 0.5 + 0.5 * np.sin(2 * np.pi * ((np.arange(size, dtype=np.float32)[:, None] / size) * 9 + warp * 2.5 + band * 0.6))
    t = T.normalize(0.5 * fig + 0.5 * band)
    alb = T.gradient(t, [(0, "#7d6a4f"), (0.5, "#a08661"), (1, "#b79d75")])
    grey = T.smoothstep(0.35, 0.8, T.spectral(size, 2.2, seed + 2))
    alb = T.mix(alb, _c("#8d877b") * np.ones_like(alb), grey * 0.55)
    yy = (np.arange(size)[:, None] % 256) / 256.0
    edge = T.smoothstep(0.72, 1.0, yy + 0.15 * (T.spectral(size, 1.8, seed + 3) - 0.5)) * np.ones((1, size))
    alb = T.mix(alb, _c("#4e4335") * np.ones_like(alb), edge * 0.55)
    paint = np.zeros((size, size), np.float32)
    pcol = np.zeros((size, size, 3), np.float32)
    for i, (lines, colour) in enumerate(SPRAY):
        cx0, cy0 = (i % 2) * 512, (i // 2) * 256
        ph = r.uniform(0, 6.28, 4)
        # A shaky hand: smooth, low-frequency wobble (independent per-vertex noise reads as bubbles).
        jit = lambda x, y, ph=ph: (2.4 * math.sin(0.045 * y + ph[0]) + 1.2 * math.sin(0.11 * x + ph[1]),  # noqa: E731
                                   2.0 * math.sin(0.05 * x + ph[2]) + 1.0 * math.sin(0.13 * y + ph[3]))
        items = []
        caps = [70, 54] if len(lines) > 1 else [92]
        y = cy0 + (34 if len(lines) > 1 else 80)
        for k, s in enumerate(lines):
            cap = caps[k] if s != ">" else 70
            items.append({"s": s, "x": cx0 + 256 + r.uniform(-12, 12), "y": y, "cap": cap, "stroke": cap * 0.2,
                          "track": cap * 0.18, "align": "center", "italic": r.uniform(-0.05, 0.12), "jitter": jit,
                          "fit": 440})
            y += cap + 36
        core = _text_mask(size, size, items)
        over = T.blur(core, 3.5) * 0.55
        # Drips under heavy strokes.
        drips = []
        for _ in range(int(r.integers(4, 9))):
            ys, xs = np.nonzero(core[cy0:cy0 + 256, cx0:cx0 + 512] > 0.9)
            if xs.size == 0:
                break
            j = int(r.integers(0, xs.size))
            x, y0 = cx0 + xs[j], cy0 + ys[j]
            drips.append((x, y0, x + r.normal(0, 0.8), min(cy0 + 250, y0 + r.uniform(12, 55)), r.uniform(1.5, 2.6)))

        def dfn(d, k, drips=drips):
            for (x0, y0, x1, y1, wd) in drips:
                d.line([(x0 * k, y0 * k), (x1 * k, y1 * k)], fill=255, width=max(1, int(wd * 2 * k)))
                d.ellipse(((x1 - wd) * k, (y1 - wd) * k, (x1 + wd) * k, (y1 + wd * 1.4) * k), fill=255)
        dm = _mask(size, size, dfn, 2)
        m = np.clip(np.maximum(core, np.maximum(over, dm)), 0, 1)
        sel = np.zeros_like(m)
        sel[cy0:cy0 + 256, cx0:cx0 + 512] = 1.0
        m *= sel
        upd = m > paint
        pcol[upd] = T.hex_rgb(colour)
        np.maximum(paint, m, out=paint)
    fade = T.spectral(size, 1.3, seed + 9)
    paint = paint * (0.72 + 0.28 * fade) * (1 - 0.4 * T.smoothstep(0.7, 0.95, T.spectral(size, 0.8, seed + 10)))
    alb = T.mix(alb, pcol, paint[..., None] * 0.95)
    height = 0.5 + 0.25 * fig * (1 - paint) + 0.1 * band - 0.1 * edge
    rough = 0.9 - 0.25 * paint
    T.save_pbr_set(out, np.clip(alb, 0, 1), np.clip(height, 0, 1), np.clip(rough, 0, 1), normal_strength=3.0)


# --------------------------------------------------------------------------------------------
# Tileable sets
# --------------------------------------------------------------------------------------------

@texture("road_bedspread", size=1024, seed=9401)
def road_bedspread(size: int, seed: int, out) -> None:
    """90s motel bedspread: quilted polyester with a big abstract tropical-leaf print in teal, mauve
    and rust on cream; diamond quilting stitches in the height; pilling and old stains. Tileable."""
    r = T.rng(seed)
    n = size
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32) / n
    base = np.ones((n, n, 3), np.float32) * _c("#d9ceb5")
    # Periodic leaf blobs: sums of rotated periodic sine fields thresholded into fronds.
    lay = np.zeros((n, n), np.float32)
    cols = ["#2f7270", "#8a4a62", "#b0582f", "#6f8f5a"]
    for k in range(4):
        fx, fy = int(r.integers(1, 3)), int(r.integers(1, 3))
        ph1, ph2 = r.uniform(0, 6.28, 2)
        f = (np.sin(2 * np.pi * (fx * xx + fy * yy) + ph1 + 1.8 * np.sin(2 * np.pi * (2 * yy - xx) + ph2))
             * np.cos(2 * np.pi * (fy * xx - fx * yy) + ph2))
        veins = 0.5 + 0.5 * np.sin(2 * np.pi * (14 * xx + 9 * yy) + 4 * f)
        m = T.smoothstep(0.35, 0.5, f) * (0.75 + 0.25 * veins)
        m = m * (1 - lay)
        base = T.mix(base, _c(cols[k]) * np.ones_like(base), m * 0.9)
        lay = np.clip(lay + m, 0, 1)
    # Diamond quilting (periodic: 8 diamonds per tile).
    d1 = np.abs(((xx + yy) * 8) % 1.0 - 0.5)
    d2 = np.abs(((xx - yy) * 8) % 1.0 - 0.5)
    stitch = np.maximum(T.smoothstep(0.47, 0.5, d1), T.smoothstep(0.47, 0.5, d2))
    puff = (1 - np.minimum(d1, d2) * 2) ** 0.5
    weave = T.spectral(n, 0.5, seed + 3)
    pill = T.smoothstep(0.82, 0.95, T.spectral(n, 0.3, seed + 4))
    stains = T.smoothstep(0.75, 0.92, T.spectral(n, 2.4, seed + 5))
    base *= (0.9 + 0.1 * puff[..., None])
    base = T.mix(base, _c("#8c7a5a") * np.ones_like(base), stains * 0.35)
    base = T.mix(base, _c("#efe8d8") * np.ones_like(base), pill * 0.3)
    base *= (1 - 0.18 * stitch[..., None])
    height = 0.35 * puff + 0.15 * weave - 0.3 * stitch + 0.05 * pill
    rough = 0.82 + 0.08 * weave - 0.05 * puff
    T.save_pbr_set(out, np.clip(base, 0, 1), T.normalize(height), np.clip(rough, 0, 1), normal_strength=3.5)


@texture("road_tread_plate", size=512, seed=9411)
def road_tread_plate(size: int, seed: int, out) -> None:
    """Steel diamond (tread) plate: raised lugs in a herringbone grid, scuffed bright on top, rust
    and grease in the hollows. Tileable; 10 x 10 lugs per tile (~0.25 m at uv_scale 4)."""
    n = size
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32) / n
    k = 10
    cx = (xx * k) % 1.0
    cy = (yy * k) % 1.0
    odd = (np.floor(xx * k) + np.floor(yy * k)) % 2
    # Lugs: elongated diamonds rotated +-45 degrees on a checkerboard.
    a = np.where(odd > 0, 1.0, -1.0)
    u = ((cx - 0.5) + a * (cy - 0.5)) / math.sqrt(2)
    v = ((cx - 0.5) - a * (cy - 0.5)) / math.sqrt(2)
    lug = T.smoothstep(0.0, 0.07, 0.44 - np.abs(u) - np.abs(v) * 2.6)
    lug = np.clip(lug, 0, 1)
    rust = T.smoothstep(0.55, 0.85, T.spectral(n, 2.0, seed)) * (1 - lug)
    grime = T.spectral(n, 1.5, seed + 1)
    scuff = T.spectral(n, 0.6, seed + 2)
    col = np.ones((n, n, 3), np.float32) * _c("#7f8284")
    col *= (0.85 + 0.15 * grime[..., None])
    col = T.mix(col, _c("#b9bcbd") * np.ones_like(col), lug * (0.4 + 0.4 * scuff))
    col = T.mix(col, _c("#6a3c22") * np.ones_like(col), rust * 0.7)
    col = T.mix(col, _c("#2a2622") * np.ones_like(col), (1 - lug) * T.smoothstep(0.4, 0.9, grime) * 0.4)
    height = 0.3 + 0.6 * lug + 0.05 * scuff
    rough = 0.55 - 0.25 * lug * scuff + 0.35 * rust
    metal = np.clip(0.85 - rust * 0.8, 0, 1)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, np.clip(rough, 0, 1), metal=metal, normal_strength=5.0)


# --------------------------------------------------------------------------------------------
# Decal
# --------------------------------------------------------------------------------------------

@texture("decal_road_oil_stain", size=1024, seed=9501, kind="pbr_alpha")
def decal_road_oil_stain(size: int, seed: int, out) -> None:
    """Old motor-oil stain on concrete: a dark soaked core, a brown halo with a tide line, drips
    and splashes. Glossy where fresh, satin where dried; fades well before the edges."""
    n = size
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32) / n - 0.5
    rr = np.hypot(xx * 1.15, yy)
    warp = _noise(n, n, 2.2, seed) - 0.5
    warp2 = _noise(n, n, 1.4, seed + 1) - 0.5
    field = rr + 0.24 * warp + 0.07 * warp2
    core = 1 - T.smoothstep(0.12, 0.26, field)
    halo = 1 - T.smoothstep(0.22, 0.4, field)
    tide = np.exp(-((field - 0.33) / 0.012) ** 2) * (halo > 0.05)
    r = T.rng(seed + 2)
    spl = np.zeros((n, n), np.float32)
    for _ in range(40):
        a, d = r.uniform(0, 6.28), r.uniform(0.25, 0.42)
        cx, cy, s = 0.5 + math.cos(a) * d, 0.5 + math.sin(a) * d, r.uniform(0.004, 0.016)
        spl = np.maximum(spl, 1 - T.smoothstep(s * 0.6, s, np.hypot(xx + 0.5 - cx, yy + 0.5 - cy)))
    alpha = np.clip(0.92 * core + 0.55 * halo + 0.35 * tide + 0.6 * spl, 0, 1)
    alpha *= 1 - T.smoothstep(0.38, 0.48, rr)
    col = np.ones((n, n, 3), np.float32) * _c("#3a2d20")
    col = T.mix(col, _c("#120e0b") * np.ones_like(col), core)
    col = T.mix(col, _c("#5a442c") * np.ones_like(col), tide * 0.6)
    height = 0.4 + 0.2 * core + 0.1 * tide
    rough = 0.55 - 0.4 * core + 0.2 * (1 - halo)
    # Bleed colour under transparent texels (no dark fringes when filtered).
    T.save_pbr_set(out, np.clip(col, 0, 1), np.clip(height, 0, 1), np.clip(rough, 0, 1), alpha=np.clip(alpha, 0, 1),
                   normal_strength=2.0, ao_strength=0.3)
