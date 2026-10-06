"""Waystation 9 (the Remand Program's trader relay post in the Cordon wall, DESIGN section 2): printed,
painted and stencilled graphics for the props in blender/generators/props_waystation.py.

  * waystation_print   2048 px atlas (PRINT_RECTS below, a contract with the generator's ATLAS): the
                       WAYSTATION 9 sign face (clean and a year-weathered copy), the contracts board's
                       pinned sheets (a Program bulletin, a contract form, a bounty sheet, a handwritten
                       list, four slips, a valley map with red rings) and its CONTRACTS header, the
                       kiosk's chalk price board, the Program stencil emblem, a HALT plate, supply crate
                       faces, a generator control panel and a data plate.
  * waystation_hazard  512 px tileable yellow-black hazard stripes (45 degrees, 1 tile = 1 m at uv_scale 1,
                       four stripe pairs per tile), chipped and grimy.

Big lettering is the roadside family's stroke font (roadside.GLYPHS: no font file) cut into stencil
letters here: STENCIL_CUTS bridges each closed or joined stroke the way a sprayed stencil plate must.
Handwriting and chalk use the bundled Caveat font (game/assets/fonts, OFL). Every name is invented: the
Remand Program and the Cordon Authority are the game's own.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from ...core.paths import GAME
from .. import texlib as T
from ..registry import texture
from .roadside import GLYPHS, SPACE, _age, _fit, _noise, _text_mask, text_width

FONTS = GAME / "assets" / "fonts"
HAND = "Caveat-Variable.ttf"
TYPE = "SpecialElite-Regular.ttf"
SOURCES = ["tools/assetgen/textures/gen/roadside.py", f"game/assets/fonts/{HAND}", f"game/assets/fonts/{TYPE}"]

# Atlas rects (x0, y0, x1, y1) in pixels of the 2048 px waystation_print texture (y down). Mirrored in
# blender/generators/props_waystation.py ATLAS - change both together.
PRINT_RECTS: dict[str, tuple[int, int, int, int]] = {
    "sign": (0, 0, 1024, 512),
    "sign_worn": (1024, 0, 2048, 512),
    "map": (0, 512, 512, 1024),
    "price": (512, 512, 960, 1024),
    "emblem": (960, 512, 1216, 768),
    "gen_panel": (1216, 512, 1472, 768),
    "crate_end": (1472, 512, 1728, 768),
    "crate_top": (1728, 512, 1984, 768),
    "halt": (960, 768, 1472, 1024),
    "crate_side": (1472, 768, 1984, 1024),
    "sheet0": (0, 1024, 192, 1280),
    "sheet1": (192, 1024, 384, 1280),
    "sheet2": (384, 1024, 576, 1280),
    "sheet3": (576, 1024, 768, 1280),
    "note0": (768, 1024, 896, 1152),
    "note1": (896, 1024, 1024, 1152),
    "note2": (1024, 1024, 1152, 1152),
    "note3": (1152, 1024, 1280, 1152),
    "plate": (768, 1152, 1024, 1280),
    "header": (1280, 1024, 2048, 1152),
}

OLIVE = "#4f5536"
OLIVE_LT = "#636a45"
YELLOW = "#d9ae2c"
BLACK = "#1d1d1c"
WHITE = "#d8d5cb"
PAPER = "#e6e0cc"
RED_INK = "#b0281f"


# ------------------------------------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------------------------------------


def _grid(w: int, h: int) -> tuple[np.ndarray, np.ndarray]:
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    return xx, yy


def _col(h: str) -> np.ndarray:
    return T.hex_rgb(h)[None, None, :]


def _fill(w: int, h: int, c: str) -> np.ndarray:
    return np.ones((h, w, 3), np.float32) * _col(c)


def _ink(c: np.ndarray, mask: np.ndarray, colour: str, amount: float = 1.0) -> np.ndarray:
    return T.mix(c, np.ones_like(c) * _col(colour), np.clip(mask * amount, 0, 1))


def _rect(xx, yy, x0, y0, x1, y1, soft: float = 1.0) -> np.ndarray:
    m = np.minimum(np.minimum(xx - x0, x1 - xx), np.minimum(yy - y0, y1 - yy))
    return np.clip(m / soft + 0.5, 0, 1)


def _disc(xx, yy, cx, cy, r, soft: float = 1.0) -> np.ndarray:
    return np.clip((r - np.hypot(xx - cx, yy - cy)) / soft + 0.5, 0, 1)


def _ring(xx, yy, cx, cy, r, w, soft: float = 1.0) -> np.ndarray:
    return np.clip((w * 0.5 - np.abs(np.hypot(xx - cx, yy - cy) - r)) / soft + 0.5, 0, 1)


def _n(w: int, h: int, beta: float, seed: int) -> np.ndarray:
    return _noise(h, w, beta, seed)


def _shape(w: int, h: int, polys=(), ellipses=(), lines=(), rings=(), ss: int = 4) -> np.ndarray:
    """Anti-aliased mask of polygons [(pts)], ellipses [(x0, y0, x1, y1)], lines [(pts, width)] and ellipse
    outlines [((x0, y0, x1, y1), width)] in pixels (4x supersampled)."""
    im = Image.new("L", (w * ss, h * ss), 0)
    d = ImageDraw.Draw(im)
    for pts in polys:
        d.polygon([(x * ss, y * ss) for x, y in pts], fill=255)
    for x0, y0, x1, y1 in ellipses:
        d.ellipse((x0 * ss, y0 * ss, x1 * ss, y1 * ss), fill=255)
    for (x0, y0, x1, y1), lw in rings:
        d.ellipse((x0 * ss, y0 * ss, x1 * ss, y1 * ss), outline=255, width=max(1, int(lw * ss)))
    for pts, lw in lines:
        d.line([(x * ss, y * ss) for x, y in pts], fill=255, width=max(1, int(lw * ss)), joint="curve")
    im = im.resize((w, h), Image.BOX)
    return np.asarray(im, np.float32) / 255.0


def _font(name: str, px: int, var: str | None = None) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONTS / name), max(4, int(px)))
    if var:
        f.set_variation_by_name(var)
    return f


def _font_text(w: int, h: int, items, rot: float = 0.0) -> np.ndarray:
    """Font text mask. items: (x, y, text, font[, anchor]); rot = degrees (whole layer, about the centre)."""
    im = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(im)
    for it in items:
        x, y, s, f = it[:4]
        d.text((x, y), s, font=f, fill=255, anchor=it[4] if len(it) > 4 else "mm")
    if rot:
        im = im.rotate(rot, resample=Image.BILINEAR, center=(w / 2, h / 2))
    return np.asarray(im, np.float32) / 255.0


def _scribble(r: np.random.Generator, x0: float, y: float, x1: float, amp: float) -> list:
    """An illegible hand-written stroke: a jittered wave along a ruled line (no letter shapes)."""
    n = max(4, int((x1 - x0) / 4))
    return [(x0 + (x1 - x0) * i / n, y + math.sin(i * 1.9 + r.uniform(0, 1.0)) * amp * r.uniform(0.4, 1.0)) for i in range(n + 1)]


def _print_lines(w: int, h: int, r: np.random.Generator, x0: float, x1: float, y0: float, y1: float, pitch: float,
                 thick: float) -> np.ndarray:
    """Blocks of grey bars standing in for small print (illegible at any distance)."""
    lines = []
    y = y0
    while y < y1:
        if r.random() < 0.12:
            y += pitch
            continue
        xe = x1 if r.random() < 0.75 else x0 + (x1 - x0) * r.uniform(0.3, 0.8)
        x = x0
        while x < xe:
            wl = r.uniform(6, 26) * thick / 2.0
            lines.append(([(x, y), (min(xe, x + wl), y)], thick))
            x += wl + thick * 1.6
        y += pitch
    return _shape(w, h, lines=lines)


# ------------------------------------------------------------------------------------------------
# stencil lettering (stroke font with bridges)
# ------------------------------------------------------------------------------------------------

# Bridges cut through each glyph, in glyph units (cap height 10, y down): segments erased with a width of
# STENCIL_GAP x the stroke. A stencil plate needs a tie wherever a counter or an island would fall out.
STENCIL_GAP = 0.42
STENCIL_CUTS: dict[str, list] = {
    "A": [((3.2, -1.5), (3.2, 1.6)), ((3.2, 5.6), (3.2, 7.6))],
    "B": [((1.5, -1.0), (1.5, 11.0))],
    "C": [((3.3, -1.0), (3.3, 1.2))],
    "D": [((1.5, -1.0), (1.5, 1.2)), ((1.5, 8.8), (1.5, 11.0))],
    "E": [((1.5, -1.0), (1.5, 11.0))],
    "F": [((1.5, -1.0), (1.5, 6.0))],
    "G": [((3.3, -1.0), (3.3, 1.2)), ((3.3, 8.8), (3.3, 11.0))],
    "H": [((1.5, 4.0), (1.5, 6.0))],
    "K": [((0.0, 5.2), (2.0, 4.0))],
    "M": [((-1.0, 1.0), (1.0, 1.0)), ((6.0, 1.0), (8.0, 1.0))],
    "N": [((-1.0, 1.2), (1.2, 1.2)), ((4.8, 8.8), (7.0, 8.8))],
    "O": [((3.4, -1.0), (3.4, 11.0))],
    "P": [((1.5, -1.0), (1.5, 6.5))],
    "Q": [((3.4, -1.0), (3.4, 1.2))],
    "R": [((1.5, -1.0), (1.5, 6.5))],
    "S": [((3.1, -1.0), (3.1, 1.0)), ((3.1, 9.0), (3.1, 11.0))],
    "T": [((2.0, 1.3), (4.4, 1.3))],
    "U": [((3.0, 8.8), (3.0, 11.0))],
    "Y": [((2.2, 5.6), (4.2, 5.6))],
    "0": [((3.0, -1.0), (3.0, 11.0))],
    "4": [((3.3, 6.0), (3.3, 8.0))],
    "6": [((3.0, 3.0), (3.0, 11.0))],
    "8": [((3.0, -1.0), (3.0, 11.0))],
    "9": [((3.0, -1.0), (3.0, 7.0))],
}


def _stencil(w: int, h: int, items: list[dict]) -> np.ndarray:
    """Stencil text mask: roadside stroke-font items (s, x, y, cap, stroke, track, condense, align, fit)
    minus the STENCIL_CUTS bridges of every glyph."""
    text = _text_mask(w, h, items)
    cuts = []
    for it in items:
        it = _fit(it)
        s, cap, stroke = it["s"], it["cap"], it["stroke"]
        track, cond = it.get("track", 0.0), it.get("condense", 1.0)
        x = it["x"]
        tw = text_width(s, cap, stroke, track, cond)
        if it.get("align", "left") == "center":
            x -= tw / 2
        elif it.get("align") == "right":
            x -= tw
        k = cap / 10.0
        pen = x + stroke / 2
        for ch in s:
            if ch == " ":
                pen += SPACE * k * cond + track
                continue
            adv, _ = GLYPHS.get(ch, GLYPHS["-"])
            for (ax, ay), (bx, by) in STENCIL_CUTS.get(ch, []):
                cuts.append(([(pen + ax * k * cond, it["y"] + ay * k), (pen + bx * k * cond, it["y"] + by * k)],
                             max(1.5, stroke * STENCIL_GAP)))
            pen += adv * k * cond + stroke + track
    if not cuts:
        return text
    return text * (1.0 - _shape(w, h, lines=cuts))


def _overspray(mask: np.ndarray, seed: int, amount: float = 0.35) -> np.ndarray:
    """Sprayed stencil paint: soft halo of mist round the letters, a little patchiness inside them."""
    h, w = mask.shape
    halo = T.blur(mask, 2.2) * 0.35
    patch = 0.85 + 0.15 * _n(w, h, 1.2, seed)
    return np.clip(np.maximum(mask * patch, halo * amount * 2.0), 0, 1)


def _hazard_stripes(xx, yy, period: float, phase: float = 0.0) -> np.ndarray:
    """1 on the black stripes of 45-degree hazard stripes (anti-aliased)."""
    t = ((xx + yy + phase) / period) % 1.0
    edge = 1.2 / period
    return np.clip((np.minimum(t, 1.0 - t) - 0.25) / edge + 0.5, 0, 1)


# ------------------------------------------------------------------------------------------------
# cells
# ------------------------------------------------------------------------------------------------


def _emblem_mask(n: int, *, letters: bool = True) -> np.ndarray:
    """The Remand Program roundel as a one-colour stencil: a bridged ring, a gate between two fence posts
    with three wires, REMAND round the bottom and PROGRAM round the top."""
    xx, yy = _grid(n, n)
    c = n / 2
    s = n / 256.0
    ring = _ring(xx, yy, c, c, 104 * s, 12 * s)
    ang = np.degrees(np.arctan2(yy - c, xx - c))
    for a0 in (0, 90, 180, -90):
        d = np.abs(((ang - a0) + 180) % 360 - 180)
        ring *= np.clip((d - 4.0) / 1.0, 0, 1)
    inner = _ring(xx, yy, c, c, 64 * s, 8 * s)
    for a0 in (45, 135, -45, -135):
        d = np.abs(((ang - a0) + 180) % 360 - 180)
        inner *= np.clip((d - 6.0) / 1.0, 0, 1)
    posts = _rect(xx, yy, c - 36 * s, c - 36 * s, c - 26 * s, c + 40 * s) + _rect(xx, yy, c + 26 * s, c - 36 * s, c + 36 * s, c + 40 * s)
    wires = sum(_rect(xx, yy, c - 22 * s, c + yo * s, c + 22 * s, c + (yo + 6) * s) for yo in (-24, -4, 16))
    m = np.clip(ring + inner + posts + wires, 0, 1)
    if letters:
        items = []
        for text, a0, a1, cap in (("PROGRAM", 205, 335, 15.0), ("REMAND", 145, 35, 15.0)):
            for i, ch in enumerate(text):
                a = math.radians(a0 + (a1 - a0) * i / (len(text) - 1))
                items.append({"s": ch, "x": c + math.cos(a) * 84 * s, "y": c + math.sin(a) * 84 * s - cap * s / 2, "cap": cap * s,
                              "stroke": 3.2 * s, "align": "center"})
        m = np.clip(m + _stencil(n, n, items), 0, 1)
    return m


def _sign(w: int, h: int, seed: int, worn: bool) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """WAYSTATION 9 / REMAND PROGRAM: off-white stencils on olive-drab steel, a yellow keyline, the Program
    roundel, a yellow-black hazard band along the bottom. Worn: chalky fade, flaking, heavy rust runs
    from the bolts, bullet strikes."""
    xx, yy = _grid(w, h)
    col = _fill(w, h, OLIVE) * (0.9 + 0.1 * _n(w, h, 1.4, seed))[..., None]
    band = 418
    key = _rect(xx, yy, 14, 14, w - 14, band - 10) * (1 - _rect(xx, yy, 22, 22, w - 22, band - 18))
    col = _ink(col, key, YELLOW, 0.9)
    title = _stencil(w, h, [{"s": "WAYSTATION 9", "x": w / 2, "y": 52, "cap": 150, "stroke": 26, "track": 10, "condense": 0.78,
                             "align": "center", "fit": w - 90}])
    col = _ink(col, _overspray(title, seed + 1), WHITE)
    em = _emblem_mask(128)
    emb = np.zeros((h, w), np.float32)
    emb[262:390, 46:174] = em
    col = _ink(col, _overspray(emb, seed + 2), YELLOW)
    sub = _stencil(w, h, [{"s": "REMAND PROGRAM", "x": 600, "y": 272, "cap": 56, "stroke": 11, "track": 14, "condense": 0.85,
                           "align": "center", "fit": 760},
                          {"s": "TRADE  -  CONTRACTS  -  CHECKPOINT", "x": 600, "y": 356, "cap": 22, "stroke": 4.5, "track": 6,
                           "align": "center", "fit": 760}])
    col = _ink(col, _overspray(sub, seed + 3), WHITE)
    # hazard band
    hz = _rect(xx, yy, -2, band, w + 2, h + 2)
    col = _ink(col, hz, YELLOW)
    col = _ink(col, hz * _hazard_stripes(xx, yy, 96.0), BLACK)
    col = _ink(col, _rect(xx, yy, -2, band - 4, w + 2, band + 2), BLACK, 0.8)
    # bolt heads (the panel's bolts sit here on the model) and their rust
    bolts = []
    for bx in (40, w / 2, w - 40):
        for by in (34, h - 30):
            bolts.append((bx - 7, by - 7, bx + 7, by + 7))
    bm = _shape(w, h, ellipses=bolts)
    col = _ink(col, bm, "#5d5a50")
    runs = np.zeros((h, w), np.float32)
    r = np.random.default_rng(seed + 5)
    streak = _n(w, h, 1.3, seed + 6)
    for (x0, y0, x1, y1) in bolts:
        cx = (x0 + x1) / 2
        ln = r.uniform(60, 180) * (1.8 if worn else 1.0)
        wd = r.uniform(5, 10)
        prof = np.clip(1 - np.abs(xx - cx) / wd, 0, 1) * np.clip(1 - (yy - y1) / ln, 0, 1) * (yy > y0)
        runs = np.maximum(runs, prof * (0.6 + 0.4 * streak))
    col = _ink(col, runs, "#6b3a1e", 0.75 if worn else 0.45)
    col, height, rough = _age(col, seed + 7, fade=0.45 if worn else 0.2, grime=0.45 if worn else 0.25,
                              runs=0.65 if worn else 0.3, scratches=140 if worn else 50, holes=7 if worn else 0,
                              rust_col="#6e3b1c")
    if worn:
        flake = T.smoothstep(0.7, 0.8, 0.65 * _n(w, h, 1.1, seed + 8) + 0.35 * _n(w, h, 0.5, seed + 9))
        col = _ink(col, flake, "#5c3b24", 0.85)
        col = _ink(col, flake * T.smoothstep(0.5, 0.9, _n(w, h, 0.7, seed + 10)), "#8a8a84", 0.5)
        height = height - flake * 0.08
        rough = np.clip(rough + flake * 0.3, 0, 1)
    height = height + T.blur(bm, 1.0) * 0.4
    return col, height, rough


def _map(n: int, seed: int) -> np.ndarray:
    """A folded valley map: pale paper, contour lines, the river leaving through the Cordon line (a heavy
    dashed bar), roads, a grid, a few red marker rings and crosses, fold creases and pin wear."""
    xx, yy = _grid(n, n)
    col = _fill(n, n, "#e3dcc2") * (0.92 + 0.08 * _n(n, n, 1.5, seed))[..., None]
    terrain = T.blur(_n(n, n, 2.6, seed + 1), 3.0)
    iso = np.abs(((terrain * 14.0) % 1.0) - 0.5)
    contour = np.clip((iso - 0.44) / 0.04, 0, 1)
    col = _ink(col, contour, "#a07a4e", 0.55)
    col = _ink(col, T.smoothstep(0.65, 0.95, terrain), "#b9c49a", 0.25)
    for g in range(0, n, 64):
        col = _ink(col, _rect(xx, yy, g, 0, g + 1, n, 0.6) + _rect(xx, yy, 0, g, n, g + 1, 0.6), "#7d93ad", 0.35)
    r = np.random.default_rng(seed + 2)
    river = []
    x, y = 30.0, 60.0
    while x < n + 10:
        river.append((x, y))
        x += 18
        y += r.uniform(-6, 18)
    col = _ink(col, _shape(n, n, lines=[(river, 7)]), "#4a7aa8", 0.9)
    roads = []
    for _ in range(3):
        pts = [(r.uniform(0, n), 0.0)]
        for k in range(1, 7):
            pts.append((pts[-1][0] + r.uniform(-60, 60), k * n / 6))
        roads.append((pts, 3))
    col = _ink(col, _shape(n, n, lines=roads), "#3a3631", 0.8)
    # the Cordon line: heavy dashed bar across the lower third
    dash = []
    cy0 = n * 0.72
    for k in range(0, n, 28):
        dash.append(([(k, cy0 + 0.05 * k), (k + 16, cy0 + 0.05 * (k + 16))], 7))
    col = _ink(col, _shape(n, n, lines=dash), "#5a2d22", 0.9)
    # Waystation 9: a black square where the river meets the line
    col = _ink(col, _rect(xx, yy, river[len(river) * 2 // 3][0] - 9, cy0 + 8, river[len(river) * 2 // 3][0] + 9, cy0 + 26), BLACK)
    # red rings and crosses (marker, wobbly)
    rings, crosses = [], []
    for _ in range(4):
        cx, cy, rr = r.uniform(60, n - 60), r.uniform(60, n * 0.62), r.uniform(18, 32)
        pts = [(cx + math.cos(a) * rr * (1 + 0.08 * math.sin(a * 3 + cx)), cy + math.sin(a) * rr * 0.85)
               for a in np.linspace(0, 2 * math.pi * 1.08, 30)]
        rings.append((pts, 4))
    for _ in range(2):
        cx, cy = r.uniform(60, n - 60), r.uniform(60, n * 0.6)
        crosses += [([(cx - 9, cy - 9), (cx + 9, cy + 9)], 4), ([(cx + 9, cy - 9), (cx - 9, cy + 9)], 4)]
    col = _ink(col, _shape(n, n, lines=rings + crosses), RED_INK, 0.92)
    # folds
    for f in (n / 2,):
        col = col * (1 - 0.12 * np.exp(-((xx - f) / 2.0) ** 2))[..., None]
        col = col * (1 - 0.1 * np.exp(-((yy - f) / 2.0) ** 2))[..., None]
    col = col * (1 - 0.18 * T.smoothstep(0.5, 1.0, np.maximum(np.abs(xx - n / 2), np.abs(yy - n / 2)) / (n / 2)))[..., None]
    return col


def _price(w: int, h: int, seed: int) -> np.ndarray:
    """Chalk price board: slate with old smudges, a chalk heading and rows of goods and scrip prices."""
    xx, yy = _grid(w, h)
    col = _fill(w, h, "#2b302c") * (0.85 + 0.15 * _n(w, h, 1.0, seed))[..., None]
    smudge = T.smoothstep(0.55, 0.9, _n(w, h, 1.8, seed + 1))
    col = _ink(col, smudge, "#6d736d", 0.35)
    f = _font(HAND, 46, "Bold")
    f2 = _font(HAND, 34, "Bold")
    rows = [("diesel / L", "8"), ("9mm  x10", "12"), ("meds kit", "25"), ("tins", "3"), ("water filt.", "6"),
            ("batteries", "4"), ("hides", "-2")]
    items = [(w / 2, 42, "SCRIP RATES", f)]
    for i, (a, b) in enumerate(rows):
        y = 104 + i * 50
        items.append((30, y, a, f2, "lm"))
        items.append((w - 34, y, b, f2, "rm"))
    items.append((w / 2, h - 34, "no credit", f2))
    t = _font_text(w, h, items)
    dots = []
    for i in range(len(rows)):
        y = 108 + i * 50
        dots.append(([(220, y), (w - 90, y)], 1.5))
    t = np.clip(t + _shape(w, h, lines=dots) * 0.5 + _shape(w, h, lines=[([(60, 70), (w - 60, 70)], 2.5)]) * 0.8, 0, 1)
    grain = T.smoothstep(0.25, 0.75, _n(w, h, 0.3, seed + 2))
    col = _ink(col, t * (0.55 + 0.45 * grain), "#e9e7df", 0.92)
    col = _ink(col, _rect(xx, yy, 0, 0, w, h) * (1 - _rect(xx, yy, 10, 10, w - 10, h - 10)), "#6d5638")
    return col


def _sheet(w: int, h: int, seed: int, kind: int) -> np.ndarray:
    """Pinned A4 sheets. 0: Program bulletin (black header bar, roundel, small print), 1: contract form
    (boxes, handwriting, red OPEN stamp), 2: bounty sheet (a Hollowed head sketched in, tear-off tabs),
    3: handwritten list on ruled paper with a mug ring."""
    xx, yy = _grid(w, h)
    r = np.random.default_rng(seed)
    col = _fill(w, h, PAPER if kind != 3 else "#e9e3c4") * (0.9 + 0.1 * _n(w, h, 1.4, seed))[..., None]
    if kind == 0:
        col = _ink(col, _rect(xx, yy, 10, 10, w - 10, 44), BLACK)
        col = _ink(col, _stencil(w, h, [{"s": "NOTICE", "x": w / 2 + 16, "y": 18, "cap": 18, "stroke": 3.4, "track": 4,
                                         "align": "center"}]), WHITE)
        em = np.zeros((h, w), np.float32)
        em[12:42, 14:44] = _emblem_mask(30, letters=False)
        col = _ink(col, em, YELLOW)
        col = _ink(col, _print_lines(w, h, r, 16, w - 16, 62, 150, 7, 2.2), "#33312d", 0.85)
        col = _ink(col, _rect(xx, yy, 16, 160, w - 16, 162), "#33312d", 0.8)
        col = _ink(col, _print_lines(w, h, r, 16, w - 16, 172, h - 30, 7, 2.2), "#33312d", 0.85)
        col = _ink(col, _shape(w, h, lines=[(_scribble(r, w - 90, h - 18, w - 24, 3.0), 1.6)]), "#1f2c5a", 0.8)
    elif kind == 1:
        col = _ink(col, _stencil(w, h, [{"s": "CONTRACT", "x": w / 2, "y": 14, "cap": 16, "stroke": 3.0, "track": 3,
                                         "align": "center"}]), BLACK)
        boxes = np.zeros((h, w), np.float32)
        for y0 in (44, 84, 124, 164):
            boxes = np.maximum(boxes, _rect(xx, yy, 12, y0, w - 12, y0 + 32) * (1 - _rect(xx, yy, 13.5, y0 + 1.5, w - 13.5, y0 + 30.5)))
        col = _ink(col, boxes, "#3a3834", 0.8)
        hand = []
        for y0 in (44, 84, 124, 164):
            hand.append((_scribble(r, 20, y0 + 18, 20 + r.uniform(70, w - 40), 2.5), 1.8))
        col = _ink(col, _shape(w, h, lines=hand), "#22306a", 0.85)
        stamp = _stencil(w, h, [{"s": "OPEN", "x": w / 2, "y": 208, "cap": 22, "stroke": 4.0, "track": 4, "align": "center"}])
        frame = _rect(xx, yy, w / 2 - 50, 200, w / 2 + 50, 238) * (1 - _rect(xx, yy, w / 2 - 46, 204, w / 2 + 46, 234))
        st = np.clip(stamp + frame, 0, 1) * (0.6 + 0.4 * _n(w, h, 0.6, seed + 1))
        im = Image.fromarray((st * 255).astype(np.uint8)).rotate(-9, resample=Image.BILINEAR, center=(w / 2, 219))
        col = _ink(col, np.asarray(im, np.float32) / 255.0, RED_INK, 0.85)
    elif kind == 2:
        col = _ink(col, _stencil(w, h, [{"s": "BOUNTY", "x": w / 2, "y": 12, "cap": 22, "stroke": 4.0, "track": 3,
                                         "align": "center"}]), RED_INK)
        head = _shape(w, h, ellipses=[(w / 2 - 38, 52, w / 2 + 38, 140)],
                      polys=[[(w / 2 - 30, 120), (w / 2 + 30, 120), (w / 2 + 50, 170), (w / 2 - 50, 170)]])
        hatch = 0.6 + 0.4 * (np.sin((xx + yy) * 0.9) > 0)
        col = _ink(col, head * hatch * 0.8, "#2b2a28")
        eyes = _shape(w, h, ellipses=[(w / 2 - 22, 84, w / 2 - 8, 96), (w / 2 + 8, 84, w / 2 + 22, 96)])
        col = _ink(col, eyes, "#d9d2bd")
        col = _ink(col, _print_lines(w, h, r, 16, w - 16, 184, 214, 7, 2.0), "#33312d", 0.85)
        tabs = np.zeros((h, w), np.float32)
        for k in range(6):
            x0 = 6 + k * (w - 12) / 6
            tabs = np.maximum(tabs, _rect(xx, yy, x0, 226, x0 + 1.2, h - 4))
        col = _ink(col, tabs, "#6a665e", 0.7)
        col = _ink(col, _rect(xx, yy, 6, 224, w - 6, 225.5), "#6a665e", 0.7)
        torn = _rect(xx, yy, 6 + 2 * (w - 12) / 6 + 1, 226, 6 + 3 * (w - 12) / 6, h + 2)
        col = _ink(col, torn, "#7c6a4a", 1.0)  # a torn-off tab shows the plywood
    else:
        for y in range(40, h - 10, 16):
            col = _ink(col, _rect(xx, yy, 8, y, w - 8, y + 1.0, 0.6), "#8fa6c0", 0.7)
        col = _ink(col, _rect(xx, yy, 26, 0, 27.2, h, 0.6), "#c27a74", 0.7)
        hand = []
        for y in range(40, h - 30, 16):
            if r.random() < 0.85:
                hand.append((_scribble(r, 32, y - 5, 32 + r.uniform(50, w - 50), 2.4), 1.7))
        col = _ink(col, _shape(w, h, lines=hand), "#2a2a2a", 0.8)
        mug = _ring(xx, yy, w * 0.68, h * 0.7, 34, 5) * (0.5 + 0.5 * _n(w, h, 0.8, seed + 2))
        col = _ink(col, mug, "#8a6438", 0.45)
    # damp and sun: yellowing to the edges, a water line
    edge = T.smoothstep(0.6, 1.0, np.maximum(np.abs(xx - w / 2) / (w / 2), np.abs(yy - h / 2) / (h / 2)))
    col = _ink(col, edge, "#b7a676", 0.35)
    return col


def _note(n: int, seed: int, kind: int) -> np.ndarray:
    """Small slips: ruled scrap, yellow sticky note, torn cardboard, a scrawled sketch-map with an arrow."""
    xx, yy = _grid(n, n)
    r = np.random.default_rng(seed)
    bg = ("#ece5cf", "#e6cf5a", "#a88d62", "#ddd6c2")[kind]
    col = _fill(n, n, bg) * (0.9 + 0.1 * _n(n, n, 1.3, seed))[..., None]
    lines = []
    if kind == 3:
        lines.append(([(14, n - 20), (40, 70), (90, 60), (110, 18)], 2.5))
        lines.append(([(100, 22), (110, 18), (114, 30)], 2.5))
        lines.append(([(56, 80), (70, 94)], 2.5))
        lines.append(([(70, 80), (56, 94)], 2.5))
        ink = "#1f1f1f"
    else:
        for y in range(26, n - 16, 18):
            lines.append((_scribble(r, 12, y, 12 + r.uniform(50, n - 24), 2.2), 1.8 if kind != 2 else 2.6))
        ink = ("#1f2c5a", "#262626", "#111111")[kind]
    col = _ink(col, _shape(n, n, lines=lines), ink, 0.85)
    if kind == 2:
        col = _ink(col, T.smoothstep(0.6, 0.9, _n(n, n, 0.9, seed + 1)), "#6b5536", 0.5)
    return col


def _header(w: int, h: int, seed: int) -> np.ndarray:
    """CONTRACTS strip: black stencils on Program yellow between hazard-striped ends."""
    xx, yy = _grid(w, h)
    col = _fill(w, h, YELLOW) * (0.9 + 0.1 * _n(w, h, 1.3, seed))[..., None]
    ends = (xx < 96) | (xx > w - 96)
    col = _ink(col, ends * _hazard_stripes(xx, yy, 48.0), BLACK)
    t = _stencil(w, h, [{"s": "CONTRACTS", "x": w / 2, "y": 26, "cap": 76, "stroke": 14, "track": 12, "condense": 0.85,
                         "align": "center", "fit": w - 240}])
    col = _ink(col, _overspray(t, seed + 1), BLACK)
    col, _, _ = _age(col, seed + 2, fade=0.25, grime=0.3, runs=0.35, scratches=30)
    return col


def _halt(w: int, h: int, seed: int) -> np.ndarray:
    """HALT / SHOW PASS plate hung from the boom: black on yellow, a black keyline."""
    xx, yy = _grid(w, h)
    col = _fill(w, h, YELLOW) * (0.9 + 0.1 * _n(w, h, 1.3, seed))[..., None]
    col = _ink(col, _rect(xx, yy, 10, 10, w - 10, h - 10) * (1 - _rect(xx, yy, 20, 20, w - 20, h - 20)), BLACK)
    t = _stencil(w, h, [{"s": "HALT", "x": w / 2, "y": 40, "cap": 112, "stroke": 22, "track": 16, "condense": 0.9,
                         "align": "center", "fit": w - 80},
                        {"s": "SHOW PASS", "x": w / 2, "y": 182, "cap": 40, "stroke": 8, "track": 10, "align": "center"}])
    col = _ink(col, t, BLACK)
    col, _, _ = _age(col, seed + 1, fade=0.25, grime=0.35, runs=0.4, scratches=60)
    return col


def _planks(w: int, h: int, seed: int, n: int, vertical: bool = False) -> np.ndarray:
    """Olive-painted crate boards: n boards with dark gaps, grain streaks, chipped paint."""
    xx, yy = _grid(w, h)
    a = xx if vertical else yy
    L = w if vertical else h
    pitch = L / n
    gap = (np.abs((a % pitch) - pitch) < 2.5) | ((a % pitch) < 2.5)
    grain = _noise(h, w, 1.2, seed, aniso=(1.0, 12.0) if vertical else (12.0, 1.0))
    col = _fill(w, h, OLIVE_LT) * (0.84 + 0.16 * grain)[..., None]
    chip = T.smoothstep(0.78, 0.86, _n(w, h, 0.9, seed + 1))
    col = _ink(col, chip, "#9a8463", 0.8)
    col = np.where(gap[..., None], _fill(w, h, "#1e1f17"), col)
    return col


def _crate_side(w: int, h: int, seed: int) -> np.ndarray:
    col = _planks(w, h, seed, 3)
    t = _stencil(w, h, [{"s": "RP-09", "x": 150, "y": 70, "cap": 64, "stroke": 11, "track": 8, "condense": 0.85, "align": "center"},
                        {"s": "WAYSTATION 9", "x": 150, "y": 160, "cap": 22, "stroke": 4.2, "track": 4, "align": "center"}])
    col = _ink(col, _overspray(t, seed + 2), "#d6d2c4", 0.92)
    em = np.zeros((h, w), np.float32)
    em[40:200, 320:480] = _emblem_mask(160)
    col = _ink(col, _overspray(em, seed + 3), YELLOW, 0.85)
    return col


def _crate_end(n: int, seed: int) -> np.ndarray:
    col = _planks(n, n, seed, 3, vertical=True)
    xx, yy = _grid(n, n)
    arrow = _shape(n, n, polys=[[(n / 2, 40), (n / 2 + 46, 100), (n / 2 + 18, 100), (n / 2 + 18, 170), (n / 2 - 18, 170),
                                 (n / 2 - 18, 100), (n / 2 - 46, 100)]])
    arrow *= 1 - _rect(xx, yy, n / 2 - 30, 112, n / 2 + 30, 118)  # stencil bridge
    col = _ink(col, _overspray(arrow, seed + 1), "#d6d2c4", 0.9)
    t = _stencil(n, n, [{"s": "THIS SIDE UP", "x": n / 2, "y": 196, "cap": 18, "stroke": 3.4, "track": 2, "align": "center",
                         "fit": n - 30}])
    col = _ink(col, t, "#d6d2c4", 0.85)
    return col


def _gen_panel(n: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Portable generator control panel: two meters, outlets, the run switch, a red stop, blank labels."""
    xx, yy = _grid(n, n)
    col = _fill(n, n, "#3d4030") * (0.9 + 0.1 * _n(n, n, 1.2, seed))[..., None]
    h = np.zeros((n, n), np.float32)
    for cx in (66, 190):
        face = _disc(xx, yy, cx, 64, 40)
        col = _ink(col, face, "#e4dfcf")
        col = _ink(col, _ring(xx, yy, cx, 64, 42, 5), "#1c1c1b")
        ang = math.radians(-50 + 30 * (cx // 60))
        col = _ink(col, _shape(n, n, lines=[([(cx, 80), (cx + math.sin(ang) * 32, 80 - math.cos(ang) * 32)], 2.5)]), RED_INK)
        for i in range(9):
            a = math.radians(-60 + 15 * i)
            col = _ink(col, _shape(n, n, lines=[([(cx + math.sin(a) * 28, 66 - math.cos(a) * 28),
                                                  (cx + math.sin(a) * 35, 66 - math.cos(a) * 35)], 1.5)]), "#1c1c1b")
        h += face * 0.3
    for cx in (60, 128, 196):
        sock = _disc(xx, yy, cx, 160, 26)
        col = _ink(col, sock, "#1a1a19")
        slots = _rect(xx, yy, cx - 12, 152, cx - 8, 166) + _rect(xx, yy, cx + 8, 152, cx + 12, 166) + _disc(xx, yy, cx, 174, 3)
        col = _ink(col, slots, "#5f5f5b")
        h += sock * 0.4 - slots * 0.3
    col = _ink(col, _disc(xx, yy, 60, 222, 16), "#a3261c")
    col = _ink(col, _rect(xx, yy, 104, 210, 152, 236), "#1b1b1b")
    col = _ink(col, _rect(xx, yy, 176, 214, 236, 232), "#cfc8b4")
    h += _disc(xx, yy, 60, 222, 16) * 0.6 + _rect(xx, yy, 104, 210, 152, 236) * 0.3
    return col, h


def _plate(w: int, h: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    xx, yy = _grid(w, h)
    col = _fill(w, h, "#9fa3a3") * (0.9 + 0.1 * _n(w, h, 1.0, seed))[..., None]
    t = _text_mask(w, h, [{"s": "CORDON AUTHORITY", "x": 14, "y": 14, "cap": 14, "stroke": 2.4, "track": 2},
                          {"s": "REMAND PROGRAM - WS 9", "x": 14, "y": 44, "cap": 14, "stroke": 2.4, "track": 2, "fit": w - 28},
                          {"s": "ASSET 09-0471", "x": 14, "y": 74, "cap": 14, "stroke": 2.4, "track": 2},
                          {"s": "DO NOT REMOVE", "x": 14, "y": 100, "cap": 12, "stroke": 2.0, "track": 2}])
    col = _ink(col, t, BLACK)
    riv = _shape(w, h, ellipses=[(4, 4, 12, 12), (w - 12, 4, w - 4, 12), (4, h - 12, 12, h - 4), (w - 12, h - 12, w - 4, h - 4)])
    col = _ink(col, riv, "#c9cccc")
    return col, T.blur(t, 0.8) * 0.2 + riv * 0.3


@texture("waystation_print", size=2048, seed=9801, sources=SOURCES)
def waystation_print(size: int, seed: int, out) -> None:
    """Atlas of the Waystation 9 graphics (rects: PRINT_RECTS)."""
    col = np.ones((size, size, 3), np.float32) * 0.5
    height = np.full((size, size), 0.5, np.float32)
    rough = np.full((size, size), 0.75, np.float32)
    metal = np.zeros((size, size), np.float32)
    R = PRINT_RECTS

    def put(name, c, h=None, ro=None, me=None):
        x0, y0, x1, y1 = R[name]
        col[y0:y1, x0:x1] = c[:y1 - y0, :x1 - x0]
        if h is not None:
            height[y0:y1, x0:x1] = h[:y1 - y0, :x1 - x0]
        if ro is not None:
            rough[y0:y1, x0:x1] = ro if np.isscalar(ro) else ro[:y1 - y0, :x1 - x0]
        if me is not None:
            metal[y0:y1, x0:x1] = me if np.isscalar(me) else me[:y1 - y0, :x1 - x0]

    for name, worn in (("sign", False), ("sign_worn", True)):
        c, h, ro = _sign(1024, 512, seed + (11 if worn else 1), worn)
        put(name, c, h, ro)
    put("map", _map(512, seed + 20), None, 0.85)
    put("price", _price(448, 512, seed + 21), _n(448, 512, 1.0, seed + 22) * 0.2 + 0.4, 0.92)
    em = _emblem_mask(256)
    ec = _fill(256, 256, OLIVE) * (0.9 + 0.1 * _n(256, 256, 1.3, seed + 23))[..., None]
    ec = _ink(ec, _overspray(em, seed + 24), YELLOW)
    ec, eh, er = _age(ec, seed + 25, fade=0.2, grime=0.3, runs=0.3, scratches=20)
    put("emblem", ec, eh, er)
    gc, gh = _gen_panel(256, seed + 26)
    put("gen_panel", gc, gh + 0.4, 0.5)
    put("crate_end", _crate_end(256, seed + 27), None, 0.85)
    put("crate_top", _planks(256, 256, seed + 28, 4), None, 0.85)
    put("halt", _halt(512, 256, seed + 29), None, 0.6)
    put("crate_side", _crate_side(512, 256, seed + 30), None, 0.85)
    for k in range(4):
        put(f"sheet{k}", _sheet(192, 256, seed + 40 + k, k), None, 0.9)
        put(f"note{k}", _note(128, seed + 50 + k, k), None, 0.9)
    pc, ph = _plate(256, 128, seed + 60)
    put("plate", pc, ph + 0.4, 0.4, 0.8)
    put("header", _header(768, 128, seed + 61), None, 0.6)
    T.save_pbr_set(out, np.clip(col, 0, 1), np.clip(height, 0, 1), np.clip(rough, 0, 1), metal=np.clip(metal, 0, 1),
                   normal_strength=2.0)


@texture("waystation_hazard", size=512, seed=9802)
def waystation_hazard(size: int, seed: int, out) -> None:
    """Tileable hazard stripes: Program yellow and black at 45 degrees, 4 stripe pairs per tile (1 m at
    uv_scale 1, so 12.5 cm stripes), the paint chipped at random and grimed (tileable noise only)."""
    xx, yy = _grid(size, size)
    period = size / 4.0
    blk = _hazard_stripes(xx, yy, period)
    col = T.mix(_fill(size, size, YELLOW), _fill(size, size, BLACK), blk)
    n1 = T.spectral(size, 1.4, seed)
    n2 = T.spectral(size, 0.6, seed + 1)
    col = col * (0.88 + 0.12 * n1)[..., None]
    chip = T.smoothstep(0.8, 0.88, 0.7 * n2 + 0.3 * n1)
    col = T.mix(col, _fill(size, size, "#8c8c86"), chip * 0.85)
    height = 0.5 - chip * 0.25 + 0.05 * n1
    rough = np.clip(0.45 + 0.3 * chip + 0.1 * n1, 0, 1)
    T.save_pbr_set(out, np.clip(col, 0, 1), np.clip(height, 0, 1), rough, metal=chip * 0.6, normal_strength=2.0)
