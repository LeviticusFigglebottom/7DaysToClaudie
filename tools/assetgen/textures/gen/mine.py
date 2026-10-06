"""Larkspur Exploration Adit (the Corvane Mining Co.'s small hard-rock exploration mine, 1950s-80s equipment,
abandoned during the quarantine): textures for the props in blender/generators/props_mine.py.

  * mine_print       1024 px atlas (PRINT_RECTS below, a contract with the generator's ATLAS): the safety
                     board's typed SAFETY FIRST notice, its chalk shift tally and the numbered check-tag
                     board, the explosives box's stencilled side, end and lid, the hoist's maker's plate,
                     the cage's capacity plate, the headframe's shaft sign and the ore car's number.
  * mine_rock_drift  1024 px PBR set, 1 m per tile: the kit's rock_drift wall finish (blasted granite)
  * mine_limestone   1024 px PBR set, 1 m per tile: the kit's rock_limestone wall finish
                     (both from textures/gen/kit_rock.py, so rock-face props match the walls behind them)

Lettering: the roadside stroke font cut into stencils (waystation._stencil), typewriter text in Special Elite
and chalk / handwriting in Caveat (game/assets/fonts, OFL). Every name is invented: the Corvane Mining Co.
and the Larkspur Adit are the game's own.
"""
from __future__ import annotations

import numpy as np

from .. import texlib as T
from ..registry import texture
from .kit_rock import rock_finish
from .waystation import (HAND, TYPE, _fill, _font, _font_text, _grid, _ink, _n, _overspray, _print_lines, _rect,
                         _shape, _stencil)
from .roadside import _age, _text_mask

SOURCES = ["tools/assetgen/textures/gen/waystation.py", "tools/assetgen/textures/gen/roadside.py",
           f"game/assets/fonts/{HAND}", f"game/assets/fonts/{TYPE}"]
ROCK_SOURCES = ["tools/assetgen/textures/gen/kit_rock.py"]

# Atlas rects (x0, y0, x1, y1) in pixels of the 1024 px mine_print texture (y down). Mirrored in
# blender/generators/props_mine.py ATLAS - change both together.
PRINT_RECTS: dict[str, tuple[int, int, int, int]] = {
    "notice": (0, 0, 512, 512),
    "tally": (512, 0, 1024, 256),
    "tags": (512, 256, 1024, 512),
    "box_side": (0, 512, 512, 768),
    "box_end": (512, 512, 768, 768),
    "plate": (768, 512, 1024, 640),
    "cage": (768, 640, 1024, 768),
    "shaft": (0, 768, 512, 1024),
    "car_no": (512, 768, 768, 1024),
    "box_lid": (768, 768, 1024, 1024),
}



def TAG_HOOK(k: int) -> tuple[float, float]:
    """Pixel position (in the 512 x 256 "tags" cell) of check-tag hook k (0..29, 10 x 3); the generator
    puts its hooks and brass tags there."""
    row, c = divmod(k, 10)
    return 34.0 + c * 49.5, 80.0 + row * 58.0


PAPER = "#e3dcc6"
INK = "#26241f"
RED = "#a3271c"
WHITE = "#dcd8cc"
CHALK = "#e6e4dc"
PLY_GREEN = "#2f3a2e"


def _wood(w: int, h: int, seed: int, base: str = "#a27e52", boards: int = 3, vertical: bool = False) -> np.ndarray:
    """Plain boards (box sides): grain streaks along the board, dark joints between them."""
    xx, yy = _grid(w, h)
    along, across = (yy, xx) if vertical else (xx, yy)
    span = (w if vertical else h) / boards
    k = np.floor(across / span)
    fib = _n(w, h, 1.0, seed)
    streak = T.normalize(np.sin(across * 0.35 + 6.0 * _n(w, h, 2.0, seed + 1)) * 0.5 + fib * 0.8)
    col = _fill(w, h, base) * (0.82 + 0.25 * streak)[..., None] * (0.92 + 0.08 * ((k * 7919) % 13 / 13.0))[..., None]
    joint = np.abs(across - np.round(across / span) * span) < 1.6
    col = _ink(col, joint.astype(np.float32), "#3a2a1a", 0.8)
    return col


def _notice(n: int, seed: int) -> np.ndarray:
    """SAFETY FIRST: a typed company notice on yellowed paper, red header band, a signature."""
    xx, yy = _grid(n, n)
    r = np.random.default_rng(seed)
    col = _fill(n, n, PAPER) * (0.88 + 0.12 * _n(n, n, 1.4, seed))[..., None]
    col = _ink(col, _rect(xx, yy, 18, 18, n - 18, 92), RED)
    col = _ink(col, _stencil(n, n, [{"s": "SAFETY FIRST", "x": n / 2, "y": 30, "cap": 50, "stroke": 9, "track": 6,
                                     "align": "center", "fit": n - 60}]), WHITE)
    ft = _font(TYPE, 19)
    fb = _font(TYPE, 24)
    items = [(n / 2, 118, "CORVANE MINING CO.", fb), (n / 2, 146, "LARKSPUR EXPLORATION ADIT", ft)]
    rules = ["1. CHECK IN AND OUT ON THE TAG BOARD.", "2. NO SMOKING OR OPEN FLAME", "    BEYOND THE PORTAL.",
             "3. BAR DOWN LOOSE BEFORE YOU WORK.", "4. HARD HAT AND CAP LAMP AT", "    ALL TIMES UNDERGROUND.",
             "5. NEVER RIDE THE CAGE WITH", "    POWDER OR CAPS.", "6. REPORT BAD AIR AND BAD GROUND", "    TO THE SHIFT BOSS.",
             "7. NO ONE ENTERS THE OLD CAVE", "    WORKINGS. BY ORDER."]
    for i, s in enumerate(rules):
        items.append((34, 190 + i * 22, s, ft, "lm"))
    col = _ink(col, _font_text(n, n, items), INK, 0.9)
    col = _ink(col, _rect(xx, yy, 34, 166, n - 34, 168), INK, 0.6)
    col = _ink(col, _print_lines(n, n, r, 34, n - 34, 462, 476, 6, 1.6), INK, 0.6)
    sig = _font_text(n, n, [(n - 120, 492, "R. Harlan, supt.", _font(HAND, 26, "Bold"))])
    col = _ink(col, sig, "#1f2c5a", 0.85)
    # damp: tide marks and foxing toward the bottom, a darker water line
    damp = T.smoothstep(0.55, 1.0, yy / n + 0.25 * (_n(n, n, 1.8, seed + 1) - 0.5))
    col = _ink(col, damp, "#a58d5a", 0.4)
    fox = T.smoothstep(0.8, 0.9, _n(n, n, 0.7, seed + 2))
    col = _ink(col, fox, "#8a6a3a", 0.35)
    # drawing pins
    col = _ink(col, _shape(n, n, ellipses=[(8, 8, 22, 22), (n - 22, 8, n - 8, 22), (8, n - 22, 22, n - 8),
                                           (n - 22, n - 22, n - 8, n - 8)]), "#7a7468")
    return col


def _tally(w: int, h: int, seed: int) -> np.ndarray:
    """Shift tally painted on board as blackboard: SHIFT TALLY header, DAY / SWING / GRAVE rows of chalk
    tally marks per week, and the days-without-accident line, its count wiped to 0."""
    xx, yy = _grid(w, h)
    r = np.random.default_rng(seed)
    col = _fill(w, h, "#252b26") * (0.85 + 0.15 * _n(w, h, 1.0, seed))[..., None]
    col = _ink(col, T.smoothstep(0.55, 0.9, _n(w, h, 1.8, seed + 1)), "#5c635c", 0.35)
    fh = _font(HAND, 34, "Bold")
    fs = _font(HAND, 26, "Bold")
    items = [(w / 2, 24, "SHIFT TALLY  -  CARS OF ORE", fh)]
    for i, s in enumerate(("DAY", "SWING", "GRAVE")):
        items.append((20, 72 + i * 46, s, fs, "lm"))
    items.append((20, h - 26, "DAYS W/O LOST TIME ACCIDENT:", fs, "lm"))
    items.append((w - 46, h - 28, "0", _font(HAND, 40, "Bold")))
    t = _font_text(w, h, items)
    marks = []
    for i in range(3):
        x = 120
        y = 72 + i * 46
        for g in range(int(r.integers(3, 7))):
            n_m = 5 if g < 4 else int(r.integers(1, 5))
            for k in range(min(n_m, 4)):
                xk = x + k * 8 + r.uniform(-1, 1)
                marks.append(([(xk, y - 14 + r.uniform(-2, 2)), (xk + r.uniform(-2, 2), y + 14)], 2.6))
            if n_m == 5:
                marks.append(([(x - 4, y + 8), (x + 30, y - 8)], 2.6))
            x += 50
    grid = [([(110, 48), (110, h - 50)], 2.0), ([(14, h - 50), (w - 14, h - 50)], 2.0)]
    m = np.clip(t + _shape(w, h, lines=marks + grid), 0, 1)
    grain = T.smoothstep(0.25, 0.75, _n(w, h, 0.3, seed + 2))
    col = _ink(col, m * (0.55 + 0.45 * grain), CHALK, 0.9)
    # the wiped-out old count round the 0
    col = _ink(col, _shape(w, h, ellipses=[(w - 90, h - 56, w - 4, h - 2)]) * 0.5, "#6f756f", 0.5)
    col = _ink(col, _rect(xx, yy, 0, 0, w, h) * (1 - _rect(xx, yy, 6, 6, w - 6, h - 6)), "#5e4a30")
    return col


def _tags(w: int, h: int, seed: int) -> np.ndarray:
    """Check-tag board: green painted ply, CHECK BOARD - IN / OUT header and 30 numbered hook places
    (10 x 3; the props hang a brass tag on most hooks: those without are men who went down)."""
    xx, yy = _grid(w, h)
    col = _fill(w, h, PLY_GREEN) * (0.88 + 0.12 * _n(w, h, 1.2, seed))[..., None]
    t = _stencil(w, h, [{"s": "CHECK BOARD", "x": w / 2, "y": 12, "cap": 26, "stroke": 4.6, "track": 5, "align": "center"},
                        {"s": "TAG ON = OUT    TAG OFF = UNDERGROUND", "x": w / 2, "y": 46, "cap": 12, "stroke": 2.2,
                         "track": 2, "align": "center", "fit": w - 30}])
    items = []
    f = _font(TYPE, 15)
    for k in range(30):
        row, c = divmod(k, 10)
        cx, cy = TAG_HOOK(k)
        items.append((cx, cy + 32, f"{k + 1}", f))
    nums = _font_text(w, h, items)
    col = _ink(col, np.clip(t + nums, 0, 1), WHITE, 0.9)
    col, _, _ = _age(col, seed + 3, fade=0.2, grime=0.35, runs=0.2, scratches=40)
    return col


def _box_side(w: int, h: int, seed: int) -> np.ndarray:
    """Explosives box long side: boards, red HIGH EXPLOSIVES - DANGEROUS stencils, a hazard diamond."""
    col = _wood(w, h, seed, "#a9865a", 3)
    t = _stencil(w, h, [{"s": "HIGH EXPLOSIVES", "x": w / 2 + 40, "y": 40, "cap": 46, "stroke": 8.5, "track": 5,
                         "align": "center", "fit": w - 150},
                        {"s": "DANGEROUS", "x": w / 2 + 40, "y": 112, "cap": 40, "stroke": 7.5, "track": 6, "align": "center"},
                        {"s": "HANDLE CAREFULLY - KEEP FIRE AWAY", "x": w / 2 + 40, "y": 176, "cap": 15, "stroke": 3.0,
                         "track": 2, "align": "center", "fit": w - 150},
                        {"s": "CORVANE MINING CO.", "x": w / 2 + 40, "y": 212, "cap": 14, "stroke": 2.8, "track": 2,
                         "align": "center"}])
    col = _ink(col, _overspray(t, seed + 1), RED, 0.92)
    dia = _shape(w, h, polys=[[(62, 70), (112, 128), (62, 186), (12, 128)]])
    inner = _shape(w, h, polys=[[(62, 82), (101, 128), (62, 174), (23, 128)]])
    col = _ink(col, dia, RED)
    col = _ink(col, inner, "#c9a46a")
    col = _ink(col, _stencil(w, h, [{"s": "1", "x": 62, "y": 110, "cap": 34, "stroke": 6, "align": "center"}]), INK)
    col, _, _ = _age(col, seed + 2, fade=0.2, grime=0.4, runs=0.15, scratches=50, dirt_col="#3e3426")
    return col


def _box_end(n: int, seed: int) -> np.ndarray:
    col = _wood(n, n, seed, "#a27f55", 2)
    t = _stencil(n, n, [{"s": "50 LBS", "x": n / 2, "y": 40, "cap": 40, "stroke": 7.5, "track": 4, "align": "center"},
                        {"s": "DYNAMITE", "x": n / 2, "y": 108, "cap": 30, "stroke": 6.0, "track": 4, "align": "center",
                         "fit": n - 30},
                        {"s": "LOT 6-114", "x": n / 2, "y": 170, "cap": 18, "stroke": 3.4, "track": 3, "align": "center"}])
    col = _ink(col, _overspray(t, seed + 1), RED, 0.9)
    col, _, _ = _age(col, seed + 2, fade=0.2, grime=0.4, runs=0.1, scratches=30, dirt_col="#3e3426")
    return col


def _box_lid(n: int, seed: int) -> np.ndarray:
    col = _wood(n, n, seed, "#a8845a", 3, vertical=True)
    t = _stencil(n, n, [{"s": "THIS SIDE UP", "x": n / 2, "y": 30, "cap": 22, "stroke": 4.0, "track": 3, "align": "center",
                         "fit": n - 30}])
    arrow = _shape(n, n, polys=[[(n / 2, 80), (n / 2 + 46, 140), (n / 2 + 16, 140), (n / 2 + 16, 210), (n / 2 - 16, 210),
                                 (n / 2 - 16, 140), (n / 2 - 46, 140)]])
    col = _ink(col, _overspray(np.clip(t + arrow, 0, 1), seed + 1), INK, 0.85)
    col, _, _ = _age(col, seed + 2, fade=0.2, grime=0.45, runs=0.1, scratches=40, dirt_col="#3e3426")
    return col


def _plate(w: int, h: int, seed: int, lines: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """Cast / stamped data plate: raised letters on a dark ground, four rivets."""
    xx, yy = _grid(w, h)
    col = _fill(w, h, "#3a3936") * (0.88 + 0.12 * _n(w, h, 1.0, seed))[..., None]
    items = []
    for i, s in enumerate(lines):
        items.append({"s": s, "x": w / 2, "y": 16 + i * 26, "cap": 14 if i else 16, "stroke": 2.6, "track": 2,
                      "align": "center", "fit": w - 34})
    t = _text_mask(w, h, items)
    rim = _rect(xx, yy, 3, 3, w - 3, h - 3) * (1 - _rect(xx, yy, 8, 8, w - 8, h - 8))
    raised = np.clip(t + rim, 0, 1)
    col = _ink(col, raised, "#a9a499", 0.85)
    riv = _shape(w, h, ellipses=[(10, 10, 20, 20), (w - 20, 10, w - 10, 20), (10, h - 20, 20, h - 10), (w - 20, h - 20, w - 10, h - 10)])
    col = _ink(col, riv, "#7c776d")
    return col, raised * 0.35 + riv * 0.4


def _shaft(w: int, h: int, seed: int) -> np.ndarray:
    """LARKSPUR No.1 SHAFT: white stencils on a red-oxide steel board, rust runs."""
    col = _fill(w, h, "#6e3524") * (0.85 + 0.15 * _n(w, h, 1.3, seed))[..., None]
    t = _stencil(w, h, [{"s": "LARKSPUR", "x": w / 2, "y": 34, "cap": 70, "stroke": 13, "track": 10, "align": "center",
                         "fit": w - 50},
                        {"s": "NO. 1 SHAFT", "x": w / 2, "y": 128, "cap": 46, "stroke": 9, "track": 8, "align": "center"},
                        {"s": "CORVANE MINING CO. - KEEP CLEAR OF COLLAR", "x": w / 2, "y": 204, "cap": 15, "stroke": 3.0,
                         "track": 2, "align": "center", "fit": w - 40}])
    col = _ink(col, _overspray(t, seed + 1), WHITE, 0.92)
    col, _, _ = _age(col, seed + 2, fade=0.35, grime=0.35, runs=0.55, scratches=60, rust_col="#4a2414")
    return col


def _car_no(n: int, seed: int) -> np.ndarray:
    """Ore car side: a big stencilled number on dark steel and the company initials."""
    col = _fill(n, n, "#3b3a37") * (0.85 + 0.15 * _n(n, n, 1.2, seed))[..., None]
    t = _stencil(n, n, [{"s": "17", "x": n / 2, "y": 40, "cap": 120, "stroke": 20, "track": 14, "align": "center"},
                        {"s": "C.M.CO.", "x": n / 2, "y": 190, "cap": 30, "stroke": 5.5, "track": 6, "align": "center"}])
    col = _ink(col, _overspray(t, seed + 1), "#c9b46a", 0.85)
    col, _, _ = _age(col, seed + 2, fade=0.3, grime=0.45, runs=0.5, scratches=50, rust_col="#5a2f17")
    return col


@texture("mine_print", size=1024, seed=6101, sources=SOURCES)
def mine_print(size: int, seed: int, out) -> None:
    """Atlas of the Larkspur Adit graphics (rects: PRINT_RECTS)."""
    col = np.ones((size, size, 3), np.float32) * 0.5
    height = np.full((size, size), 0.5, np.float32)
    rough = np.full((size, size), 0.8, np.float32)
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

    put("notice", _notice(512, seed + 1), None, 0.92)
    put("tally", _tally(512, 256, seed + 2), None, 0.95)
    put("tags", _tags(512, 256, seed + 3), None, 0.7)
    put("box_side", _box_side(512, 256, seed + 4), None, 0.85)
    put("box_end", _box_end(256, seed + 5), None, 0.85)
    pc, ph = _plate(256, 128, seed + 6, ["CORVANE MINING CO.", "DOUBLE DRUM HOIST NO. 2", "75 HP  440 V  60 CY", "SER. 5531  1958"])
    put("plate", pc, ph + 0.4, 0.45, 0.7)
    cc, ch = _plate(256, 128, seed + 7, ["CAGE", "CAPACITY 6 MEN", "NO RIDING WITH", "POWDER OR CAPS"])
    put("cage", cc, ch + 0.4, 0.5, 0.6)
    put("shaft", _shaft(512, 256, seed + 8), None, 0.7)
    put("car_no", _car_no(256, seed + 9), None, 0.75)
    put("box_lid", _box_lid(256, seed + 10), None, 0.85)
    T.save_pbr_set(out, np.clip(col, 0, 1), np.clip(height, 0, 1), np.clip(rough, 0, 1), metal=np.clip(metal, 0, 1),
                   normal_strength=2.0)


def _rock_set(name: str, size: int, seed: int, out) -> None:
    f = rock_finish(name, size, seed)
    T.save_pbr_set(out, np.clip(f.albedo, 0, 1), f.height, np.clip(f.rough, 0, 1), metal=0.0,
                   normal_strength=f.normal_strength, ao_strength=f.ao_strength)


@texture("mine_rock_drift", size=1024, seed=7100, sources=ROCK_SOURCES)
def mine_rock_drift(size: int, seed: int, out) -> None:
    """The kit's rock_drift finish as a standard PBR set (1 m per tile): rock-face props, rock piles."""
    _rock_set("rock_drift", size, seed, out)


@texture("mine_limestone", size=1024, seed=7100, sources=ROCK_SOURCES)
def mine_limestone(size: int, seed: int, out) -> None:
    """The kit's rock_limestone finish as a standard PBR set (1 m per tile): stalagmites, cave rock faces."""
    _rock_set("rock_limestone", size, seed, out)
