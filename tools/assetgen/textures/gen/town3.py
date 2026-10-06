"""Printed and painted graphics of the town pool buildings (ADR-0030 pool, DESIGN section 11 "Pool
buildings"): Suds & Spin Laundromat, Hollowmere Grocery, Bracken Lumber & Feed, Pell County Library and
KHLW Valley Radio. One 1024 px atlas, town3_print: facade signs, the laundromat's control panels, rates
card and change machine, the grocery's aisle cards, deli banner, price strips and the reefer trailer's
livery, the lumber yard's forklift plate and grain-bin plate, the library's catalogue drawer labels,
hours plaque and children's poster, and the radio station's console, transmitter and rack faces, tape
labels, mast plate and the Cordon's broadcast schedule.

Models: tools/assetgen/blender/generators/props_town3.py (ATLAS mirrors PRINT_RECTS: change both
together). Materials: game/data/materials/props_town3.json (t3_print). All names are invented.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from ...core.paths import GAME
from .. import texlib as T
from ..registry import texture

FONTS = GAME / "assets" / "fonts"
SERIF = "EBGaramond-Variable.ttf"
MONO = "IBMPlexMono-Bold.ttf"
MONO_R = "IBMPlexMono-Regular.ttf"
TYPE = "SpecialElite-Regular.ttf"
HAND = "Caveat-Variable.ttf"
FONT_SOURCES = [f"game/assets/fonts/{n}" for n in (SERIF, MONO, MONO_R, TYPE, HAND)]

# Atlas rects (x0, y0, x1, y1) in pixels of the 1024 px town3_print texture. Mirrored in
# blender/generators/props_town3.py (ATLAS) - change both together.
PRINT_RECTS: dict[str, tuple[int, int, int, int]] = {
    "sign_suds": (0, 0, 512, 128),
    "sign_grocery": (512, 0, 1024, 128),
    "sign_lumber": (0, 128, 512, 256),
    "sign_library": (512, 128, 1024, 256),
    "sign_khlw": (0, 256, 512, 384),
    "on_air": (512, 256, 768, 320),
    "deli": (768, 256, 1024, 320),
    "aisles": (512, 320, 1024, 384),       # 4 aisle cards of 128 x 64, left to right
    "coin_panel": (0, 384, 256, 448),
    "rates": (256, 384, 384, 512),
    "changer": (384, 384, 512, 512),
    "soap": (512, 384, 640, 512),
    "card_labels": (640, 384, 1024, 448),  # 24 drawer labels of 64 x 16 (6 columns x 4 rows)
    "reefer": (0, 512, 512, 640),
    "forklift": (640, 448, 768, 512),
    "mast_plate": (768, 448, 896, 512),
    "console": (512, 512, 1024, 576),
    "transmitter": (512, 576, 768, 704),
    "rack_front": (768, 576, 1024, 704),
    "tape_labels": (0, 640, 256, 704),     # 4 reel labels of 64 x 64
    "notice_cordon": (256, 640, 512, 832),
    "kids_poster": (512, 704, 768, 832),
    "library_hours": (768, 704, 1024, 832),
    "grain_plate": (0, 704, 256, 768),
    "price_tags": (0, 832, 512, 864),
    "packets": (512, 832, 1024, 896),      # 8 soap / seed packet faces of 64 x 64
    "spines_ref": (0, 864, 512, 1024),     # bound reference volumes (archive ledgers), 16 spines of 32 x 160
    "wood_plain": (768, 896, 1024, 1024),
}


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


def _font(name: str, px: int, var: str | None = None) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONTS / name), max(4, int(px)))
    if var:
        f.set_variation_by_name(var)
    return f


def _fit(name: str, text: str, max_w: float, px: int, var: str | None = None) -> ImageFont.FreeTypeFont:
    while px > 6:
        f = _font(name, px, var)
        x0, _, x1, _ = f.getbbox(text)
        if x1 - x0 <= max_w:
            return f
        px -= 1
    return _font(name, px, var)


def _text(w: int, h: int, items) -> np.ndarray:
    """Anti-aliased text mask (h, w) in [0, 1]. items: (x, y, text, font[, anchor])."""
    im = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(im)
    for it in items:
        x, y, s, f = it[:4]
        d.text((x, y), s, font=f, fill=255, anchor=it[4] if len(it) > 4 else "mm")
    return np.asarray(im, np.float32) / 255.0


def _rect(xx, yy, x0, y0, x1, y1, soft: float = 1.0) -> np.ndarray:
    m = np.minimum(np.minimum(xx - x0, x1 - xx), np.minimum(yy - y0, y1 - yy))
    return np.clip(m / soft + 0.5, 0, 1)


def _disc(xx, yy, cx, cy, r, soft: float = 1.0) -> np.ndarray:
    return np.clip((r - np.hypot(xx - cx, yy - cy)) / soft + 0.5, 0, 1)


def _noise(w: int, h: int, beta: float, seed: int) -> np.ndarray:
    s = 1 << int(np.ceil(np.log2(max(w, h, 8))))
    return T.spectral(s, beta, seed)[:h, :w]


def _wear(w: int, h: int, seed: int, amount: float) -> np.ndarray:
    """Patchy flaking mask (1 = paint gone)."""
    a = _noise(w, h, 1.2, seed)
    b = _noise(w, h, 0.4, seed + 1)
    return np.clip(T.smoothstep(1.0 - amount, 1.0 - amount * 0.5, 0.65 * a + 0.35 * b), 0, 1)


def _ink(c: np.ndarray, mask: np.ndarray, colour: str, amount: float = 1.0) -> np.ndarray:
    return T.mix(c, np.ones_like(c) * _col(colour), np.clip(mask * amount, 0, 1))


def _board(w: int, h: int, seed: int, bg: str, rim: str | None, wear: float = 0.3) -> np.ndarray:
    xx, yy = _grid(w, h)
    c = _fill(w, h, bg) * (0.86 + 0.14 * _noise(w, h, 1.4, seed))[..., None]
    if rim:
        c = _ink(c, 1.0 - _rect(xx, yy, 6, 6, w - 6, h - 6), rim, 0.9)
    # sun-fade toward the top, rain streaks down from the top edge
    streak = np.clip(_noise(w, h, 0.2, seed + 7) * 1.4 - 0.5, 0, 1) * np.clip(1.0 - yy / h, 0, 1)
    return c * (1.0 - 0.18 * streak[..., None]) * (1.0 - 0.15 * _wear(w, h, seed + 3, wear)[..., None])


def _paper(w: int, h: int, seed: int, tone: str = "#ece6d4") -> np.ndarray:
    return _fill(w, h, tone) * (0.9 + 0.1 * _noise(w, h, 1.6, seed))[..., None]


# ------------------------------------------------------------------------------------------------
# cells
# ------------------------------------------------------------------------------------------------


def _sign(w, h, seed, title, sub, bg, fg, rim, font=SERIF, var="Bold", sub_var="SemiBold", wear=0.35):
    c = _board(w, h, seed, bg, rim, wear)
    t = _text(w, h, [(w / 2, h * 0.4, title, _fit(font, title, w - 44, int(h * 0.52), var)),
                     (w / 2, h * 0.8, sub, _fit(font, sub, w - 90, int(h * 0.2), sub_var))])
    return _ink(c, t * (1.0 - 0.75 * _wear(w, h, seed + 11, wear)), fg)


def _suds(seed: int) -> np.ndarray:
    w, h = 512, 128
    xx, yy = _grid(w, h)
    c = _board(w, h, seed, "#e9e4d6", "#1b6f78", 0.35)
    # bubbles rising off the lettering
    for i, (bx, by, br) in enumerate([(40, 40, 14), (62, 22, 9), (78, 48, 6), (470, 36, 12), (448, 18, 7), (488, 60, 6)]):
        ring = _disc(xx, yy, bx, by, br) - _disc(xx, yy, bx, by, br - 2.5)
        c = _ink(c, ring, "#1b6f78", 0.85)
    t = _text(w, h, [(w / 2, 52, "SUDS & SPIN", _fit(SERIF, "SUDS & SPIN", 360, 64, "ExtraBold")),
                     (w / 2, 103, "COIN LAUNDRY  -  OPEN 7 TO 9", _font(MONO, 17))])
    c = _ink(c, t, "#1b6f78")
    return _ink(c, _wear(w, h, seed + 5, 0.4) * 0.5, "#8d877a")


def _aisles(seed: int) -> np.ndarray:
    out = np.zeros((64, 512, 3), np.float32)
    names = [("1", "CANNED GOODS"), ("2", "CEREAL - BAKING"), ("3", "HOUSEHOLD"), ("4", "PET - PAPER")]
    for k, (num, label) in enumerate(names):
        c = _board(128, 64, seed + k, "#f2efe6", "#a5282a", 0.2)
        t = _text(128, 64, [(64, 22, num, _font(MONO, 30)), (64, 50, label, _fit(MONO, label, 112, 13))])
        out[:, k * 128:(k + 1) * 128] = _ink(c, t, "#a5282a")
    return out


def _coin_panel(seed: int) -> np.ndarray:
    w, h = 256, 64
    xx, yy = _grid(w, h)
    c = _fill(w, h, "#d9d7cf") * (0.9 + 0.1 * _noise(w, h, 1.2, seed))[..., None]
    c = _ink(c, _rect(xx, yy, 8, 8, 120, 56), "#2a2c2e", 0.9)
    t = _text(w, h, [(64, 22, "WASH", _font(MONO, 16)), (64, 42, "$1.75", _font(MONO, 18)),
                     (190, 18, "HOT  WARM  COLD", _font(MONO_R, 11)), (190, 46, "INSERT QUARTERS", _font(MONO, 12))])
    c = _ink(c, t * _rect(xx, yy, 8, 8, 120, 56), "#e4d26a")
    c = _ink(c, t * (1.0 - _rect(xx, yy, 8, 8, 120, 56)), "#2a2c2e")
    for i, cx in enumerate((150, 190, 230)):
        c = _ink(c, _disc(xx, yy, cx, 32, 6), ["#b23a2e", "#d39b2b", "#2e5f9a"][i])
    return c


def _rates(seed: int) -> np.ndarray:
    w, h = 128, 128
    c = _paper(w, h, seed, "#efe9d8")
    lines = [(64, 14, "RATES", _font(MONO, 15)), (64, 36, "WASH ......... 1.75", _font(MONO_R, 10)),
             (64, 50, "BIG WASH ..... 3.00", _font(MONO_R, 10)), (64, 64, "DRY .. 25c / 8 MIN", _font(MONO_R, 10)),
             (64, 82, "NO DYEING", _font(MONO, 10)), (64, 96, "NOT RESPONSIBLE FOR", _font(MONO_R, 8)),
             (64, 106, "LOST ARTICLES", _font(MONO_R, 8))]
    c = _ink(c, _text(w, h, lines), "#1d1c1a")
    hand = _text(w, h, [(64, 120, "dryer 3 broken - D.", _font(HAND, 13, "Bold"))])
    return _ink(c, hand, "#1f3d8a", 0.85)


def _changer(seed: int) -> np.ndarray:
    w, h = 128, 128
    xx, yy = _grid(w, h)
    c = _fill(w, h, "#2f4f8a") * (0.88 + 0.12 * _noise(w, h, 1.0, seed))[..., None]
    c = _ink(c, _rect(xx, yy, 14, 52, 114, 74), "#151617")
    c = _ink(c, _rect(xx, yy, 40, 92, 88, 120), "#c9c7c0")
    t = _text(w, h, [(64, 18, "CHANGE", _font(MONO, 18)), (64, 38, "$1  $5  $10", _font(MONO_R, 12)),
                     (64, 63, "INSERT BILL", _font(MONO_R, 9)), (64, 84, "QUARTERS BELOW", _font(MONO_R, 9))])
    return _ink(c, t, "#f1efe6")


def _soap(seed: int) -> np.ndarray:
    w, h = 128, 128
    xx, yy = _grid(w, h)
    c = _fill(w, h, "#d8d3c4")
    cols = ["#d23b2f", "#2d7bc4", "#f0b82e", "#3c9a52", "#8a3fa0", "#e46c22"]
    for r in range(3):
        for k in range(4):
            x0, y0 = 8 + k * 29, 12 + r * 38
            c = _ink(c, _rect(xx, yy, x0, y0, x0 + 24, y0 + 30), cols[(r * 4 + k) % len(cols)])
            c = _ink(c, _rect(xx, yy, x0 + 4, y0 + 8, x0 + 20, y0 + 16), "#f6f3ea")
    t = _text(w, h, [(64, 122, "SOAP 75c", _font(MONO, 9))])
    return _ink(c, t, "#1d1c1a")


def _card_labels(seed: int) -> np.ndarray:
    out = np.zeros((64, 384, 3), np.float32)
    ranges = ["A-Am", "An-Ba", "Be-Bu", "C-Ch", "Ci-Cu", "D-Di", "Do-E", "F-Fo", "Fr-G", "H-Hi", "Ho-I", "J-K",
              "L-Le", "Li-Ma", "Me-Mu", "N-O", "P-Pe", "Pi-Q", "R-Ri", "Ro-Sa", "Se-St", "Su-T", "U-W", "X-Z"]
    f = _font(TYPE, 11)
    for i, s in enumerate(ranges):
        cx, cy = i % 6, i // 6
        c = _paper(64, 16, seed + i, "#e9e1c8")
        c = _ink(c, _text(64, 16, [(32, 8, s, f)]), "#262320")
        out[cy * 16:(cy + 1) * 16, cx * 64:(cx + 1) * 64] = c
    return out


def _reefer(seed: int) -> np.ndarray:
    w, h = 512, 128
    xx, yy = _grid(w, h)
    c = _fill(w, h, "#eceae4") * (0.92 + 0.08 * _noise(w, h, 1.0, seed))[..., None]
    c = _ink(c, _rect(xx, yy, 0, 96, w, 108), "#1f5a8a")
    c = _ink(c, _rect(xx, yy, 0, 110, w, 114), "#c33a2c")
    t = _text(w, h, [(w / 2, 44, "NORTHLINE FOODS", _fit(SERIF, "NORTHLINE FOODS", 420, 58, "ExtraBold")),
                     (w / 2, 82, "FRESH & FROZEN  -  SERVING THE VALLEY", _font(MONO, 15))])
    c = _ink(c, t, "#1f5a8a")
    dirt = np.clip(yy / h, 0, 1) ** 2 * (0.5 + 0.5 * _noise(w, h, 1.0, seed + 3))
    return c * (1.0 - 0.35 * dirt[..., None])


def _plate(w, h, seed, lines, bg="#b9b5aa", ink="#1d1c1a"):
    xx, yy = _grid(w, h)
    c = _fill(w, h, bg) * (0.85 + 0.15 * _noise(w, h, 1.6, seed))[..., None]
    c = _ink(c, 1.0 - _rect(xx, yy, 3, 3, w - 3, h - 3), "#57544d", 0.8)
    for sx in (7, w - 7):
        for sy in (7, h - 7):
            c = _ink(c, _disc(xx, yy, sx, sy, 2.5), "#3b3934")
    return _ink(c, _text(w, h, lines), ink)


def _console(seed: int) -> np.ndarray:
    w, h = 512, 64
    xx, yy = _grid(w, h)
    c = _fill(w, h, "#3a3b3d") * (0.9 + 0.1 * _noise(w, h, 1.2, seed))[..., None]
    names = ["MIC 1", "MIC 2", "CART A", "CART B", "TT 1", "TT 2", "REEL", "LINE", "PHONE", "EBS", "MON", "PGM"]
    for i, s in enumerate(names):
        x0 = 6 + i * 42
        c = _ink(c, _rect(xx, yy, x0, 4, x0 + 38, 14), "#d8d4c6")
        c = _ink(c, _text(w, h, [(x0 + 19, 9, s, _font(MONO, 8))]), "#1a1a1a")
        c = _ink(c, _rect(xx, yy, x0 + 17, 20, x0 + 21, 58), "#101112")
        knob_y = 26 + (i * 7 % 26)
        c = _ink(c, _rect(xx, yy, x0 + 12, knob_y, x0 + 26, knob_y + 6), "#e8e6df" if i != 9 else "#c0392b")
    return c


def _transmitter(seed: int) -> np.ndarray:
    w, h = 256, 128
    xx, yy = _grid(w, h)
    c = _fill(w, h, "#8c9089") * (0.9 + 0.1 * _noise(w, h, 1.2, seed))[..., None]
    for i, cx in enumerate((50, 128, 206)):
        c = _ink(c, _disc(xx, yy, cx, 52, 30), "#efe9d6")
        c = _ink(c, _disc(xx, yy, cx, 52, 30) - _disc(xx, yy, cx, 52, 28), "#1d1c1a")
        ang = -0.9 + i * 0.5
        needle = np.clip(1.2 - np.abs((xx - cx) * np.cos(ang) - (yy - 70) * np.sin(ang)), 0, 1) * (yy < 70) * (yy > 30)
        c = _ink(c, needle * _disc(xx, yy, cx, 52, 29), "#a3231d")
    t = _text(w, h, [(50, 96, "PLATE V", _font(MONO, 10)), (128, 96, "PLATE I", _font(MONO, 10)),
                     (206, 96, "FWD PWR", _font(MONO, 10)), (128, 116, "KHLW  1340 kHz  1 kW", _font(MONO, 12))])
    return _ink(c, t, "#1d1c1a")


def _rack_front(seed: int) -> np.ndarray:
    w, h = 256, 128
    xx, yy = _grid(w, h)
    c = _fill(w, h, "#26282a") * (0.88 + 0.12 * _noise(w, h, 1.2, seed))[..., None]
    for r in range(4):
        y0 = 4 + r * 31
        c = _ink(c, _rect(xx, yy, 4, y0, 252, y0 + 27), ["#3d4043", "#545650", "#2f3133", "#4b4d49"][r])
        for k in range(6):
            c = _ink(c, _disc(xx, yy, 20 + k * 12, y0 + 9, 3), ["#2fbf4a", "#d9a21f", "#c0392b"][(r + k) % 3])
        c = _ink(c, _text(w, h, [(170, y0 + 13, ["EXCITER", "AUDIO PROC", "EBS ENC/DEC", "STL RCVR"][r], _font(MONO, 11))]), "#d8d4c6")
    return c


def _tape_labels(seed: int) -> np.ndarray:
    out = np.zeros((64, 256, 3), np.float32)
    for k, (a, b) in enumerate([("CORDON", "DAY 3"), ("CORDON", "DAY 9"), ("EBS", "TEST"), ("DO NOT", "ERASE")]):
        xx, yy = _grid(64, 64)
        c = _paper(64, 64, seed + k, "#f1ecd9")
        c = _ink(c, 1.0 - _disc(xx, yy, 32, 32, 30), "#262626")
        c = _ink(c, _disc(xx, yy, 32, 32, 5), "#262626")
        c = _ink(c, _text(64, 64, [(32, 18, a, _font(HAND, 14, "Bold")), (32, 47, b, _font(HAND, 14, "Bold"))]), "#1f3d8a")
        out[:, k * 64:(k + 1) * 64] = c
    return out


def _cordon_notice(seed: int) -> np.ndarray:
    w, h = 256, 192
    c = _paper(w, h, seed, "#f0ead8")
    lines = [(128, 16, "TAMSIN VALLEY CORDON", _font(MONO, 14)), (128, 34, "EMERGENCY BROADCAST", _font(MONO, 14)),
             (128, 50, "KHLW 1340 AM", _font(MONO_R, 11)), (14, 72, "ON THE HOUR: ROAD STATUS", _font(TYPE, 11), "lm"),
             (14, 88, ":15 BOIL WATER / CURFEW", _font(TYPE, 11), "lm"), (14, 104, ":30 ASSEMBLY POINTS", _font(TYPE, 11), "lm"),
             (14, 120, ":45 NAMES OF THE MISSING", _font(TYPE, 11), "lm"), (14, 140, "READ AS WRITTEN. NO", _font(TYPE, 11), "lm"),
             (14, 154, "COMMENTARY. - LT. VOSS", _font(TYPE, 11), "lm")]
    c = _ink(c, _text(w, h, lines), "#1d1c1a")
    hand = _text(w, h, [(128, 178, "nobody is coming", _font(HAND, 20, "Bold"))])
    return _ink(c, hand, "#8a1a16", 0.9)


def _kids_poster(seed: int) -> np.ndarray:
    w, h = 256, 128
    xx, yy = _grid(w, h)
    c = _fill(w, h, "#f3d77a") * (0.9 + 0.1 * _noise(w, h, 1.0, seed))[..., None]
    c = _ink(c, _disc(xx, yy, 46, 60, 34), "#e0643a")
    c = _ink(c, _disc(xx, yy, 210, 84, 26), "#4f8fd1")
    c = _ink(c, _rect(xx, yy, 150, 20, 190, 52), "#5fae5a")
    t = _text(w, h, [(128, 64, "READ!", _font(SERIF, 58, "ExtraBold")), (128, 112, "STORY TIME SATURDAYS 10AM", _font(MONO, 11))])
    return _ink(c, t, "#3a2a6a")


def _hours(seed: int) -> np.ndarray:
    w, h = 256, 128
    c = _board(w, h, seed, "#2a2622", "#a88a4e", 0.2)
    lines = [(128, 20, "PELL COUNTY LIBRARY", _font(SERIF, 18, "Bold")), (128, 46, "MON - FRI  10 - 6", _font(SERIF, 15, "SemiBold")),
             (128, 66, "SAT  10 - 2", _font(SERIF, 15, "SemiBold")), (128, 86, "BOOK RETURN AT SIDE", _font(SERIF, 12)),
             (128, 108, "Ida Lindqvist, Librarian", _font(SERIF, 13, "Medium"))]
    return _ink(c, _text(w, h, lines), "#d9c48a")


def _price_tags(seed: int) -> np.ndarray:
    w, h = 512, 32
    xx, yy = _grid(w, h)
    c = _fill(w, h, "#f4f1e8")
    for i in range(16):
        x0 = i * 32
        c = _ink(c, _rect(xx, yy, x0 + 2, 3, x0 + 30, 29), "#fbe46a" if i % 3 == 0 else "#ffffff")
        c = _ink(c, _text(w, h, [(x0 + 16, 16, [".99", "1.29", "2.49", ".79", "3.19", "1.89"][i % 6], _font(MONO, 9))]), "#c0392b" if i % 3 == 0 else "#1d1c1a")
    return c


def _packets(seed: int) -> np.ndarray:
    out = np.zeros((64, 512, 3), np.float32)
    cols = ["#2d7bc4", "#d23b2f", "#3c9a52", "#f0b82e", "#e46c22", "#8a3fa0", "#7a5a3a", "#1f5a8a"]
    names = ["SNOW", "BRITE", "CORN", "OATS", "BEANS", "BLOOM", "LAYER", "CHICK"]
    for k in range(8):
        xx, yy = _grid(64, 64)
        c = _fill(64, 64, cols[k]) * (0.9 + 0.1 * _noise(64, 64, 1.2, seed + k))[..., None]
        c = _ink(c, _disc(xx, yy, 32, 36, 16), "#f6f3ea")
        c = _ink(c, _text(64, 64, [(32, 12, names[k], _font(MONO, 11))]), "#f6f3ea")
        out[:, k * 64:(k + 1) * 64] = c
    return out


def _spines(seed: int) -> np.ndarray:
    out = np.zeros((160, 512, 3), np.float32)
    cols = ["#5a1f1a", "#1f3b2a", "#2a2f4a", "#4a3a22", "#3b1d2e", "#22343a", "#5b4a2a", "#3a3a3a"]
    years = ["1931", "1938", "1946", "1951", "1957", "1962", "1968", "1974", "1979", "1983", "1988", "1992", "1997", "2003", "2009", "2014"]
    for k in range(16):
        xx, yy = _grid(32, 160)
        c = _fill(32, 160, cols[k % len(cols)]) * (0.8 + 0.2 * _noise(32, 160, 1.0, seed + k))[..., None]
        for by in (14, 22, 138, 146):
            c = _ink(c, _rect(xx, yy, 2, by, 30, by + 3), "#c9a75a", 0.85)
        im = Image.new("L", (160, 32), 0)
        ImageDraw.Draw(im).text((80, 16), "COUNTY REC. " + years[k], font=_font(SERIF, 12, "Bold"), fill=255, anchor="mm")
        t = np.asarray(im.rotate(90, expand=True), np.float32) / 255.0
        c = _ink(c, t, "#d8c27a", 0.9)
        out[:, k * 32:(k + 1) * 32] = c
    return out


@texture("town3_print", size=1024, seed=9601, sources=FONT_SOURCES)
def town3_print(size: int, seed: int, out) -> None:
    """Atlas of the pool buildings' printed and painted graphics (rects: PRINT_RECTS)."""
    col = np.ones((size, size, 3), np.float32) * 0.5
    height = np.zeros((size, size), np.float32)
    rough = np.full((size, size), 0.7, np.float32)
    metal = np.zeros((size, size), np.float32)
    R = PRINT_RECTS

    def put(name, c, ro=0.7, me=0.0, h=None):
        x0, y0, x1, y1 = R[name]
        col[y0:y1, x0:x1] = c[:y1 - y0, :x1 - x0]
        rough[y0:y1, x0:x1] = ro if np.isscalar(ro) else ro[:y1 - y0, :x1 - x0]
        metal[y0:y1, x0:x1] = me if np.isscalar(me) else me[:y1 - y0, :x1 - x0]
        if h is not None:
            height[y0:y1, x0:x1] = h[:y1 - y0, :x1 - x0]

    put("sign_suds", _suds(seed + 1), 0.55)
    put("sign_grocery", _sign(512, 128, seed + 2, "HOLLOWMERE GROCERY", "MEAT  -  PRODUCE  -  DELI  -  FEED THE FAMILY", "#f1ece0", "#a5282a", "#a5282a"), 0.5)
    put("sign_lumber", _sign(512, 128, seed + 3, "BRACKEN LUMBER & FEED", "EST. 1946  -  YARD  -  FEED  -  SEED  -  FENCING", "#2f4a2c", "#efe6c8", "#efe6c8", var="ExtraBold", wear=0.45), 0.75)
    put("sign_library", _sign(512, 128, seed + 4, "PELL COUNTY LIBRARY", "A GIFT OF THE PEOPLE OF THE VALLEY  -  1931", "#3a2f25", "#d9c48a", "#a88a4e", wear=0.25), 0.45, 0.35)
    put("sign_khlw", _sign(512, 128, seed + 5, "KHLW 1340 AM", "THE VOICE OF THE TAMSIN VALLEY", "#1c2f4f", "#f2efe6", "#c0392b", font=MONO, var=None, sub_var=None), 0.5)
    w, h = 256, 64
    xx, yy = _grid(w, h)
    oa = _fill(w, h, "#3a0d0b") * (0.85 + 0.15 * _noise(w, h, 1.0, seed + 6))[..., None]
    oa = _ink(oa, _text(w, h, [(w / 2, h / 2, "ON AIR", _font(MONO, 44))]), "#f4d9cf")
    put("on_air", oa, 0.25)
    put("deli", _sign(256, 64, seed + 7, "MEAT & DELI", "CUT TO ORDER", "#7a1f1d", "#f2e6d0", "#f2e6d0", wear=0.2), 0.5)
    put("aisles", _aisles(seed + 8), 0.45)
    put("coin_panel", _coin_panel(seed + 9), 0.4, 0.3)
    put("rates", _rates(seed + 10), 0.85)
    put("changer", _changer(seed + 11), 0.45, 0.4)
    put("soap", _soap(seed + 12), 0.6)
    put("card_labels", _card_labels(seed + 13), 0.85)
    put("reefer", _reefer(seed + 14), 0.45)
    put("forklift", _plate(128, 64, seed + 15, [(64, 16, "CAPACITY", _font(MONO, 12)), (64, 34, "5000 LB @ 24 IN", _font(MONO_R, 11)),
                                               (64, 52, "LP GAS - NO RIDERS", _font(MONO, 9))], bg="#e5c33a"), 0.5, 0.4)
    put("mast_plate", _plate(128, 64, seed + 16, [(64, 14, "ASR 1047755", _font(MONO, 11)), (64, 30, "KHLW  HT 46 M", _font(MONO_R, 10)),
                                                 (64, 50, "DANGER - HIGH RF", _font(MONO, 11))], bg="#d8d3c4", ink="#8a1a16"), 0.5, 0.5)
    put("console", _console(seed + 17), 0.45, 0.2)
    put("transmitter", _transmitter(seed + 18), 0.4, 0.4)
    put("rack_front", _rack_front(seed + 19), 0.4, 0.5)
    put("tape_labels", _tape_labels(seed + 20), 0.8)
    put("notice_cordon", _cordon_notice(seed + 21), 0.85)
    put("kids_poster", _kids_poster(seed + 22), 0.7)
    put("library_hours", _hours(seed + 23), 0.4, 0.3)
    put("grain_plate", _plate(256, 64, seed + 24, [(128, 18, "BRACKEN LUMBER & FEED", _font(MONO, 14)), (128, 42, "5000 BU  -  CORN  OATS  MIX", _font(MONO_R, 12))],
                                bg="#c9c4b5"), 0.55, 0.5)
    put("price_tags", _price_tags(seed + 25), 0.5)
    put("packets", _packets(seed + 26), 0.6)
    put("spines_ref", _spines(seed + 27), 0.6)
    wp = T.gradient(_noise(256, 128, 1.2, seed + 28), [(0.0, "#6b4626"), (1.0, "#8a5f35")])
    put("wood_plain", wp, 0.6)
    grime = T.spectral(size, 2.2, seed + 99)
    col *= (0.9 + 0.1 * grime[..., None])
    T.save_pbr_set(out, np.clip(col, 0, 1), np.clip(height + 0.05 * grime, 0, 1), np.clip(rough, 0, 1), metal=metal,
                   normal_strength=1.2)
