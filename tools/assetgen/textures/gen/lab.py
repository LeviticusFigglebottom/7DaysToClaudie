"""The Corvane Field Lab (agent Y): the lab_signs lettering atlas.

  * lab_signs  2048 px, 256 px units (CELLS below): the station's painted board at the gate (CORVANE MINING CO. -
               FIELD STATION 2), the Cordon's biohazard signs and fence plates, the airlock and decon-line stencils,
               the specimen vault plate, the emergency exit, the containment notice, the core shed board, the four
               module plates and the module and decon stencils, the core boxes' stencilled ends, the -80 freezer's
               door label, the diesel placard and the generator's control panel. The cell rectangles are the contract
               with blender/generators/props_lab.py (ATLAS, keep both in sync).
Lettering uses the roadside stroke font (textures/gen/roadside.py: no font files), weathered with its _age(). The
biohazard trefoil is drawn here from circles. Every name on it is our own: no real company, brand or emblem.
"""
from __future__ import annotations

import numpy as np

from .. import texlib as T
from ..registry import texture
from . import roadside as RS

UNIT = 256
CELLS = {
    "station": (0, 0, 6, 2),
    "biohazard": (6, 0, 2, 1.5), "fence_plate": (6, 1.5, 2, 1.5),
    "airlock": (0, 2, 3, 1), "decon": (3, 2, 3, 1),
    "vault": (0, 3, 3, 1), "emergency": (3, 3, 2.5, 1), "containment": (5.5, 3, 2.5, 1.75),
    "core_shed": (0, 4, 4, 1), "freezer": (4, 4, 1.5, 1),
    "mod_prep": (0, 5, 2.8, 1), "mod_micro": (2.8, 5, 2.8, 1), "module_stencil": (5.6, 5, 2.4, 1),
    "mod_cold": (0, 6, 2.8, 1), "mod_admin": (2.8, 6, 2.8, 1), "decon_stencil": (5.6, 6, 2.4, 1),
    "box_ends": (0, 7, 4, 1), "diesel": (4, 7, 2, 1), "genpanel": (6, 7, 2, 1),
}
INK = "#1b1a18"
WHITE = "#ecebe4"
YELLOW = "#e0b62c"
ORANGE = "#d0601f"
RED = "#a8281f"
CORVANE = "#2f4a5e"      # the company's slate blue
CORDON = "#3b4a3a"       # the Cordon's field green


def _cell(name: str) -> tuple[int, int]:
    return int(CELLS[name][2] * UNIT), int(CELLS[name][3] * UNIT)


def _t(s, x, y, cap, stroke, **kw):
    d = {"s": s, "x": x, "y": y, "cap": cap, "stroke": stroke, "align": kw.pop("align", "center")}
    d.update(kw)
    return d


def _border(w, h, inset, width, radius=0.0):
    outer = RS._rect_mask(w, h, [(inset, inset, w - inset, h - inset)], radius=radius)
    inner = RS._rect_mask(w, h, [(inset + width, inset + width, w - inset - width, h - inset - width)],
                          radius=max(0.0, radius - width))
    return np.clip(outer - inner, 0, 1)


def _biohazard(w, h, cx, cy, r):
    """The biohazard trefoil: three crescents round a ring, drawn from circles (r = the symbol's radius)."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    m = np.zeros((h, w), np.float32)
    for k in range(3):
        a = np.radians(-90 + 120 * k)
        ca, sa = np.cos(a), np.sin(a)
        # Each lobe: a disc pushed out from the centre, its inner disc cut away further out.
        ox, oy = cx + ca * r * 0.42, cy + sa * r * 0.42
        ix, iy = cx + ca * r * 0.56, cy + sa * r * 0.56
        outer = (xx - ox) ** 2 + (yy - oy) ** 2 <= (r * 0.52) ** 2
        inner = (xx - ix) ** 2 + (yy - iy) ** 2 <= (r * 0.36) ** 2
        m = np.maximum(m, (outer & ~inner).astype(np.float32))
    d2 = (xx - cx) ** 2 + (yy - cy) ** 2
    ring = (d2 <= (r * 0.36) ** 2) & (d2 >= (r * 0.26) ** 2)
    m = np.maximum(m, ring.astype(np.float32))
    m[d2 <= (r * 0.16) ** 2] = 0.0
    # Soften the edge (2x2 box blur).
    m = (m + np.roll(m, 1, 0) + np.roll(m, 1, 1) + np.roll(np.roll(m, 1, 0), 1, 1)) * 0.25
    return np.clip(m, 0, 1)


def _station(seed):
    w, h = _cell("station")
    col = RS._fill(h, w, CORVANE)
    col = RS._over(col, WHITE, _border(w, h, 14, 8))
    # The company mark: a pick and a core run crossed in a circle.
    mark = RS._ellipse_mask(w, h, [(150, 256, 92, 92)]) - RS._ellipse_mask(w, h, [(150, 256, 78, 78)])
    mark += RS._poly_mask(w, h, [[(96, 300), (108, 312), (210, 210), (198, 198)], [(90, 214), (108, 196), (214, 304), (196, 322)]])
    col = RS._over(col, WHITE, np.clip(mark, 0, 1))
    col = RS._over(col, WHITE, RS._text_mask(w, h, [
        _t("CORVANE MINING CO.", 900, 70, 112, 21, track=10, fit=1180),
        _t("FIELD STATION 2", 900, 230, 82, 15, track=12, fit=1080),
        _t("EXPLORATION DIVISION", 700, 360, 40, 7.5, track=6, fit=880)]))
    # The Cordon's notice zip-tied over the corner.
    x0, y0 = 1214, 314
    col = RS._over(col, "#e9e4d6", RS._rect_mask(w, h, [(x0, y0, x0 + 300, y0 + 190)]))
    col = RS._over(col, RED, RS._rect_mask(w, h, [(x0, y0, x0 + 300, y0 + 52)]))
    col = RS._over(col, WHITE, RS._text_mask(w, h, [_t("BIOHAZARD", x0 + 150, y0 + 12, 30, 6, track=4, fit=270)]))
    col = RS._over(col, INK, _biohazard(w, h, x0 + 70, y0 + 122, 50))
    col = RS._over(col, INK, RS._text_mask(w, h, [_t("CORDON", x0 + 200, y0 + 80, 24, 5, fit=170),
                                                   _t("MEDICAL", x0 + 200, y0 + 112, 24, 5, fit=170),
                                                   _t("NO ENTRY", x0 + 200, y0 + 150, 22, 4.5, fit=170)]))
    return RS._age(col, seed, fade=0.35, grime=0.45, runs=0.5, scratches=60, holes=2)


def _biohazard_sign(name, seed, *, plate=False):
    w, h = _cell(name)
    col = RS._fill(h, w, YELLOW if not plate else "#e9e4d6")
    if plate:
        col = RS._over(col, RED, RS._rect_mask(w, h, [(0, 0, w, 96)]))
        col = RS._over(col, WHITE, RS._text_mask(w, h, [_t("BIOHAZARD", w / 2, 24, 48, 10, track=6, fit=470)]))
        col = RS._over(col, INK, _biohazard(w, h, 130, 230, 92))
        col = RS._over(col, INK, RS._text_mask(w, h, [_t("CORDON", 360, 150, 36, 7, fit=250), _t("MEDICAL", 360, 196, 36, 7, fit=250),
                                                       _t("AUTHORITY", 360, 242, 30, 6, fit=250),
                                                       _t("NO ENTRY - LETHAL FORCE", w / 2, 330, 26, 5.5, track=2, fit=480)]))
        col = RS._over(col, INK, _border(w, h, 4, 6))
        return RS._age(col, seed, fade=0.3, grime=0.45, runs=0.55, scratches=40, holes=1)
    col = RS._over(col, INK, _border(w, h, 10, 10, radius=16))
    col = RS._over(col, INK, _biohazard(w, h, w / 2, 150, 110))
    col = RS._over(col, INK, RS._text_mask(w, h, [_t("BIOHAZARD", w / 2, 276, 52, 11, track=6, fit=440),
                                                   _t("CONTAINMENT LEVEL 3", w / 2, 336, 24, 5, track=3, fit=420)]))
    return RS._age(col, seed, fade=0.25, grime=0.35, runs=0.3, scratches=30)


def _stencil_plate(name, lines, seed, base, ink, **age):
    w, h = _cell(name)
    col = RS._fill(h, w, base)
    col = RS._over(col, ink, RS._text_mask(w, h, lines))
    return RS._age(col, seed, **age)


def _airlock(seed):
    w, h = _cell("airlock")
    col = RS._fill(h, w, "#c9ccc8")
    stripes = RS._poly_mask(w, h, [[(x, 0), (x + 40, 0), (x - 30, 60), (x - 70, 60)] for x in range(0, w + 80, 80)])
    col = RS._over(col, YELLOW, RS._rect_mask(w, h, [(0, 0, w, 60)]))
    col = RS._over(col, INK, stripes * RS._rect_mask(w, h, [(0, 0, w, 60)]))
    col = RS._over(col, INK, RS._text_mask(w, h, [_t("AIRLOCK", w / 2, 84, 92, 18, track=18, fit=700),
                                                   _t("ONE DOOR AT A TIME - WAIT FOR GREEN", w / 2, 200, 30, 6, track=3, fit=720)]))
    return RS._age(col, seed, fade=0.2, grime=0.45, runs=0.45, scratches=30)


def _decon(seed):
    w, h = _cell("decon")
    col = RS._fill(h, w, YELLOW)
    cw = w // 3
    items = []
    for i, (n, s) in enumerate((("1", "PPE ON"), ("2", "DECON SHOWER"), ("3", "AIRLOCK"))):
        x = cw * i + cw / 2
        items.append(_t(n, x, 18, 120, 22))
        items.append(_t(s, x, 170, 34, 7, track=3, fit=cw - 36))
    col = RS._over(col, INK, RS._text_mask(w, h, items))
    for i in range(1, 3):
        col = RS._over(col, INK, RS._rect_mask(w, h, [(cw * i - 3, 10, cw * i + 3, h - 10)]))
    col = RS._over(col, INK, _border(w, h, 6, 6))
    return RS._age(col, seed, fade=0.3, grime=0.4, runs=0.35, scratches=30)


def _vault(seed):
    w, h = _cell("vault")
    col = RS._fill(h, w, "#d7d4ca")
    col = RS._over(col, RED, RS._rect_mask(w, h, [(0, 0, w, 70)]))
    col = RS._over(col, WHITE, RS._text_mask(w, h, [_t("SPECIMEN VAULT", w / 2, 14, 46, 9, track=8, fit=700)]))
    col = RS._over(col, INK, _biohazard(w, h, 90, 165, 62))
    col = RS._over(col, INK, RS._text_mask(w, h, [_t("CORDON MEDICAL AUTHORITY", 450, 100, 30, 6, track=2, fit=560),
                                                   _t("CLASS A SPECIMENS - MINUS 80", 450, 150, 26, 5, track=2, fit=560),
                                                   _t("TWO-PERSON RULE", 450, 196, 34, 7, track=4, fit=560)]))
    return RS._age(col, seed, fade=0.15, grime=0.35, runs=0.2, scratches=25)


def _emergency(seed):
    w, h = _cell("emergency")
    col = RS._fill(h, w, "#2f7a45")
    col = RS._over(col, WHITE, _border(w, h, 8, 6))
    col = RS._over(col, WHITE, RS._text_mask(w, h, [_t("EMERGENCY EXIT", 270, 50, 52, 10, track=6, fit=440),
                                                     _t("ESCAPE SHAFT - CLIMB", 270, 150, 30, 6, track=3, fit=420)]))
    arrow = RS._poly_mask(w, h, [[(560, 40), (610, 110), (580, 110), (580, 210), (540, 210), (540, 110), (510, 110)]])
    col = RS._over(col, WHITE, arrow)
    return RS._age(col, seed, fade=0.2, grime=0.4, runs=0.3, scratches=20)


def _containment(seed):
    w, h = _cell("containment")
    col = RS._fill(h, w, WHITE)
    col = RS._over(col, RED, RS._rect_mask(w, h, [(0, 0, w, 120)]))
    col = RS._over(col, WHITE, RS._text_mask(w, h, [_t("CONTAINMENT", w / 2, 30, 62, 12, track=6, fit=600)]))
    col = RS._over(col, INK, _biohazard(w, h, 120, 290, 100))
    col = RS._over(col, INK, RS._text_mask(w, h, [_t("AUTHORIZED", 420, 190, 40, 8, fit=330),
                                                   _t("PERSONNEL", 420, 244, 40, 8, fit=330),
                                                   _t("ONLY", 420, 298, 40, 8, fit=330),
                                                   _t("BY ORDER - CORDON MEDICAL AUTHORITY", w / 2, 392, 22, 4.5, track=2, fit=600)]))
    return RS._age(col, seed, fade=0.2, grime=0.35, runs=0.35, scratches=25)


def _core_shed(seed):
    w, h = _cell("core_shed")
    grain = RS._noise(h, w, 1.5, seed + 3, aniso=(12.0, 1.0))
    col = T.mix(T.hex_rgb("#6f7a74")[None, None, :] * np.ones((h, w, 3), np.float32),
                T.hex_rgb("#5d6862")[None, None, :] * np.ones((h, w, 3), np.float32), grain)
    col = RS._over(col, "#efe9d8", RS._text_mask(w, h, [_t("CORE SHED", w / 2, 36, 120, 22, track=16, fit=900),
                                                         _t("NO SMOKING - BOXES IN ORDER - LOG BEFORE YOU SAW", w / 2, 184, 34, 7, track=4, fit=960)]))
    return RS._age(col, seed, fade=0.35, grime=0.5, runs=0.45, scratches=60)


def _module_plate(name, n, label, seed):
    w, h = _cell(name)
    col = RS._fill(h, w, "#d9d8cf")
    col = RS._over(col, CORVANE, RS._rect_mask(w, h, [(0, 0, 200, h)]))
    col = RS._over(col, WHITE, RS._text_mask(w, h, [_t(n, 100, 40, 150, 26)]))
    col = RS._over(col, INK, RS._text_mask(w, h, [_t(label, 440, 74, 70, 13, track=6, fit=440),
                                                   _t("CORVANE FS-2 / CORDON MEDICAL", 440, 180, 24, 4.5, track=2, fit=440)]))
    return RS._age(col, seed, fade=0.25, grime=0.4, runs=0.4, scratches=30)


def _module_stencil(seed):
    w, h = _cell("module_stencil")
    col = RS._fill(h, w, "#dcdcd3")
    col = RS._over(col, "#3a3f44", RS._text_mask(w, h, [_t("CORVANE", w / 2, 30, 76, 15, track=12, fit=560),
                                                          _t("FS-2  LAB MODULE", w / 2, 150, 44, 9, track=8, fit=560)]))
    return RS._age(col, seed, fade=0.2, grime=0.55, runs=0.65, scratches=20)


def _decon_stencil(seed):
    w, h = _cell("decon_stencil")
    col = RS._fill(h, w, "#8d948f")
    col = RS._over(col, YELLOW, RS._rect_mask(w, h, [(0, 196, w, 236)]))
    col = RS._over(col, INK, RS._poly_mask(w, h, [[(x, 196), (x + 22, 196), (x - 18, 236), (x - 40, 236)] for x in range(0, w + 44, 44)])
                   * RS._rect_mask(w, h, [(0, 196, w, 236)]))
    col = RS._over(col, WHITE, RS._text_mask(w, h, [_t("DECON", w / 2, 24, 96, 19, track=16, fit=560),
                                                     _t("CORDON MEDICAL - UNIT 2", w / 2, 140, 30, 6, track=4, fit=560)]))
    return RS._age(col, seed, fade=0.2, grime=0.5, runs=0.6, scratches=25)


def _box_ends(seed):
    """Eight stencilled core-box ends, 256 x 128 px each (4 across, 2 down): hole, depth run, box number."""
    w, h = _cell("box_ends")
    col = RS._fill(h, w, "#b29a6c")
    cw, ch = w // 4, h // 2
    rr = np.random.default_rng(seed)
    items = []
    depth = 1288
    for i in range(8):
        x = cw * (i % 4) + cw / 2
        y = ch * (i // 4)
        items.append(_t(("BH-7" if i < 6 else "BH-4") + f"  BOX {205 + i}", x, y + 14, 30, 6, fit=cw - 24))
        items.append(_t(f"{depth} - {depth + 18} FT", x, y + 66, 32, 6.5, fit=cw - 24))
        depth += 18 + int(rr.integers(0, 6))
    col = RS._over(col, "#24201a", RS._text_mask(w, h, items))
    for i in range(1, 4):
        col = RS._over(col, "#6a5a3e", RS._rect_mask(w, h, [(cw * i - 2, 0, cw * i + 2, h)]))
    col = RS._over(col, "#6a5a3e", RS._rect_mask(w, h, [(0, ch - 2, w, ch + 2)]))
    return RS._age(col, seed, fade=0.3, grime=0.55, runs=0.3, scratches=40)


def _freezer(seed):
    w, h = _cell("freezer")
    col = RS._fill(h, w, "#eeeee8")
    col = RS._over(col, "#20262a", RS._rect_mask(w, h, [(24, 22, 200, 96)], radius=6))
    col = RS._over(col, "#ff5a3a", RS._text_mask(w, h, [_t("-41", 112, 38, 46, 9, fit=150)]))
    col = RS._over(col, INK, RS._text_mask(w, h, [_t("ULT -80", 290, 30, 30, 6, fit=150),
                                                   _t("CFL SAMPLES", w / 2, 128, 26, 5, track=2, fit=330),
                                                   _t("DO NOT OPEN", w / 2, 172, 26, 5, track=2, fit=330)]))
    col = RS._over(col, YELLOW, RS._rect_mask(w, h, [(250, 80, 360, 116)]))
    col = RS._over(col, INK, _biohazard(w, h, 305, 98, 16))
    col = RS._over(col, "#2b2b2b", RS._text_mask(w, h, [_t("DR. MARCHETTI - DO NOT MOVE", w / 2, 216, 18, 3.5, fit=330,
                                                                 jitter=lambda x, y: (1.2 * np.sin(y * 0.2), 0.8 * np.cos(x * 0.13)))]))
    return RS._age(col, seed, fade=0.1, grime=0.35, runs=0.2, scratches=20)


def _diesel(seed):
    w, h = _cell("diesel")
    col = RS._fill(h, w, "#4a5a45")
    col = RS._over(col, "#e8e0c8", RS._text_mask(w, h, [_t("DIESEL", 170, 30, 80, 15, track=10, fit=300),
                                                         _t("NO SMOKING", 170, 150, 34, 7, track=4, fit=300),
                                                         _t("CAP. 2,000 GAL", 170, 200, 26, 5, fit=300)]))
    # The red diamond placard.
    d = RS._poly_mask(w, h, [[(420, 30), (500, 110), (420, 190), (340, 110)]])
    col = RS._over(col, RED, d)
    col = RS._over(col, WHITE, RS._text_mask(w, h, [_t("3", 420, 54, 40, 8), _t("1202", 420, 130, 22, 4.5)]))
    return RS._age(col, seed, fade=0.35, grime=0.55, runs=0.6, scratches=50)


def _genpanel(seed):
    w, h = _cell("genpanel")
    col = RS._fill(h, w, "#3d4143")
    col = RS._over(col, "#1a1d1e", RS._rect_mask(w, h, [(24, 24, 230, 120)], radius=6))
    col = RS._over(col, "#ffb84a", RS._text_mask(w, h, [_t("0000 7 1 9 4", 127, 52, 30, 6, fit=190)]))
    col = RS._over(col, "#e6e2d6", RS._text_mask(w, h, [_t("HOURS", 127, 134, 18, 3.5),
                                                         _t("AUTO  OFF  RUN", 380, 40, 20, 4, fit=220),
                                                         _t("CORVANE FS-2  GEN 1  60 KVA", w / 2, 210, 22, 4.5, fit=480)]))
    for k, c in enumerate(("#3fa34d", "#d9a521", "#b8261f")):
        col = RS._over(col, c, RS._ellipse_mask(w, h, [(300 + k * 60, 120, 18, 18)]))
    return RS._age(col, seed, fade=0.15, grime=0.6, runs=0.3, scratches=40)


@texture("lab_signs", size=2048, seed=9901, sources=["tools/assetgen/textures/gen/roadside.py"])
def lab_signs(size: int, seed: int, out) -> None:
    """Corvane Field Lab signage atlas (layout CELLS, 256 px units)."""
    cv = RS._canvas(size)
    makers = {
        "station": _station,
        "biohazard": lambda s: _biohazard_sign("biohazard", s),
        "fence_plate": lambda s: _biohazard_sign("fence_plate", s, plate=True),
        "airlock": _airlock, "decon": _decon, "vault": _vault, "emergency": _emergency, "containment": _containment,
        "core_shed": _core_shed, "freezer": _freezer,
        "mod_prep": lambda s: _module_plate("mod_prep", "1", "SAMPLE PREP", s),
        "mod_micro": lambda s: _module_plate("mod_micro", "2", "MICROSCOPY", s),
        "mod_cold": lambda s: _module_plate("mod_cold", "3", "COLD ROOM -80", s),
        "mod_admin": lambda s: _module_plate("mod_admin", "4", "ADMIN - RADIO", s),
        "module_stencil": _module_stencil, "decon_stencil": _decon_stencil,
        "box_ends": _box_ends, "diesel": _diesel, "genpanel": _genpanel,
    }
    for i, (name, fn) in enumerate(makers.items()):
        c, hh, r = fn(seed + i * 41)
        RS._put(cv, CELLS[name], UNIT, c, hh, r)
    RS._save_canvas(out, cv)
