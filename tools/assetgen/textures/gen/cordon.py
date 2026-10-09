"""The Cordon wall (DESIGN section 1: the government sealed the valley behind the Cordon; Waystation 9 is
the relay post built into it where the river leaves the valley): the sprayed stencils on the precast wall
panels, the Route 9 gate and the river sluice, for blender/generators/props_cordon_wall.py.

  * cordon_print   2048 px atlas (PRINT_RECTS below, a contract with the generator's ATLAS). Every cell is
                   a painted primer patch with its stencils, so it reads on the bare concrete it is laid on
                   (std_surface has no alpha): the valley face's QUARANTINE BOUNDARY band, the outer face's
                   CORDON AUTHORITY band, the segment mark, the Route 9 gate's CLOSED BY ORDER 14 plate, the
                   sluice's DANGER plate, the checkpoint booth's name board, the Program notice board's
                   header and two typed Program notices pinned on it.
  * cordon_concrete 1024 px tileable precast concrete (1 tile = 2 m at uv_scale 1): form-board seams,
                   bug holes, a little aggregate, rain-darkened, grimy low.

Lettering is the roadside stroke font cut into stencils (waystation._stencil); typed notices use the
bundled Special Elite font (OFL). The Cordon Authority and the Remand Program are the game's own; nothing
here names the outbreak's cause (docs/LORE_TRAIL.md "What early places must not say").
"""
from __future__ import annotations

import numpy as np

from .. import texlib as T
from ..registry import texture
from .roadside import _age
from .waystation import (BLACK, HAND, TYPE, YELLOW, _emblem_mask, _fill, _font, _font_text, _grid, _hazard_stripes,
                         _ink, _n, _overspray, _print_lines, _rect, _stencil)

SOURCES = ["tools/assetgen/textures/gen/waystation.py", "tools/assetgen/textures/gen/roadside.py",
           f"game/assets/fonts/{HAND}", f"game/assets/fonts/{TYPE}"]

# Atlas rects (x0, y0, x1, y1) in pixels of the 2048 px cordon_print texture (y down). Mirrored in
# blender/generators/props_cordon_wall.py ATLAS - change both together.
PRINT_RECTS: dict[str, tuple[int, int, int, int]] = {
    "valley": (0, 0, 2048, 512),        # 4 : 1  the valley face's band (4.0 x 1.0 m on the panel)
    "outer": (0, 512, 2048, 768),       # 8 : 1  the outer face's band (4.0 x 0.5 m)
    "gate": (0, 768, 1536, 1024),       # 6 : 1  the gate's plate on the gantry (3.6 x 0.6 m)
    "segment": (1536, 768, 2048, 1024),  # 2 : 1  segment mark (0.8 x 0.4 m)
    "sluice": (0, 1024, 1536, 1280),    # 6 : 1  the river gate's lintel plate (4.2 x 0.7 m)
    "booth": (1536, 1024, 2048, 1152),  # 4 : 1  CHECKPOINT 9 board
    "notices": (1536, 1152, 2048, 1280),  # 4 : 1  PROGRAM NOTICES header
    "notice0": (0, 1280, 384, 1792),    # 3 : 4  typed notice (A4-ish)
    "notice1": (384, 1280, 768, 1792),  # 3 : 4  typed notice
    "roundel": (768, 1280, 1280, 1792),  # 1 : 1  the Program roundel, yellow on olive
    "chevron": (1280, 1280, 2048, 1536),  # 3 : 1  hazard chevrons for the gate leaves and pier noses
}

PRIMER = "#cfcab9"
RED = "#9e2a1f"
OLIVE = "#4f5536"


def _primer(w: int, h: int, seed: int, colour: str = PRIMER) -> np.ndarray:
    """A sprayed primer patch: slightly uneven coverage, darker where it thins out toward the edges."""
    xx, yy = _grid(w, h)
    col = _fill(w, h, colour) * (0.9 + 0.1 * _n(w, h, 1.4, seed))[..., None]
    edge = np.minimum(np.minimum(xx, w - 1 - xx), np.minimum(yy, h - 1 - yy))
    thin = np.clip(1.0 - edge / (0.06 * min(w, h)), 0, 1) * (0.5 + 0.5 * _n(w, h, 1.0, seed + 1))
    return T.mix(col, _fill(w, h, "#8d8a80"), thin * 0.45)


def _valley(w: int, h: int, seed: int) -> np.ndarray:
    """The valley face: QUARANTINE BOUNDARY in red over DO NOT APPROACH THE WALL, the authority line, hazard
    ends."""
    xx, yy = _grid(w, h)
    col = _primer(w, h, seed)
    ends = (xx < 150) | (xx > w - 150)
    col = _ink(col, ends * _hazard_stripes(xx, yy, 96.0), BLACK, 0.9)
    t = _stencil(w, h, [{"s": "QUARANTINE BOUNDARY", "x": w / 2, "y": 46, "cap": 150, "stroke": 26, "track": 20,
                         "condense": 0.86, "align": "center", "fit": w - 380}])
    col = _ink(col, _overspray(t, seed + 1), RED, 0.95)
    t2 = _stencil(w, h, [{"s": "DO NOT APPROACH THE WALL", "x": w / 2, "y": 250, "cap": 92, "stroke": 16, "track": 14,
                          "condense": 0.88, "align": "center", "fit": w - 420},
                         {"s": "CORDON AUTHORITY - ORDER 14", "x": w / 2, "y": 392, "cap": 58, "stroke": 10, "track": 12,
                          "align": "center", "fit": w - 520}])
    col = _ink(col, _overspray(t2, seed + 2), BLACK, 0.92)
    col, _, _ = _age(col, seed + 3, fade=0.3, grime=0.45, runs=0.6, scratches=80)
    return col


def _outer(w: int, h: int, seed: int) -> np.ndarray:
    """The outer face: CORDON AUTHORITY - RESTRICTED LINE in black on yellow primer."""
    col = _primer(w, h, seed, "#c9a63a")
    t = _stencil(w, h, [{"s": "CORDON AUTHORITY - RESTRICTED LINE", "x": w / 2, "y": 50, "cap": 120, "stroke": 22,
                         "track": 18, "condense": 0.86, "align": "center", "fit": w - 120}])
    col = _ink(col, _overspray(t, seed + 1), BLACK, 0.95)
    col, _, _ = _age(col, seed + 2, fade=0.35, grime=0.4, runs=0.5, scratches=50)
    return col


def _gate(w: int, h: int, seed: int) -> np.ndarray:
    """The gate's plate: CORDON GATE - ROUTE 9 over CLOSED BY ORDER 14, white on red, a white keyline."""
    xx, yy = _grid(w, h)
    col = _fill(w, h, "#8a2219") * (0.88 + 0.12 * _n(w, h, 1.3, seed))[..., None]
    col = _ink(col, _rect(xx, yy, 12, 12, w - 12, h - 12) * (1 - _rect(xx, yy, 24, 24, w - 24, h - 24)), "#ddd8cc")
    t = _stencil(w, h, [{"s": "CORDON GATE - ROUTE 9", "x": w / 2, "y": 40, "cap": 88, "stroke": 16, "track": 14,
                         "condense": 0.88, "align": "center", "fit": w - 120},
                        {"s": "CLOSED BY ORDER 14", "x": w / 2, "y": 160, "cap": 56, "stroke": 10, "track": 12,
                         "align": "center", "fit": w - 200}])
    col = _ink(col, t, "#ddd8cc")
    col, _, _ = _age(col, seed + 1, fade=0.35, grime=0.35, runs=0.5, scratches=80, holes=3)
    return col


def _segment(w: int, h: int, seed: int) -> np.ndarray:
    """A segment mark: C9 over a run of tally strokes, black on primer."""
    col = _primer(w, h, seed)
    t = _stencil(w, h, [{"s": "LINE 9", "x": w / 2, "y": 40, "cap": 96, "stroke": 18, "track": 12, "align": "center",
                         "fit": w - 60},
                        {"s": "SEG - INSPECTED", "x": w / 2, "y": 170, "cap": 40, "stroke": 7, "track": 6, "align": "center",
                         "fit": w - 60}])
    col = _ink(col, _overspray(t, seed + 1), BLACK, 0.9)
    col, _, _ = _age(col, seed + 2, fade=0.3, grime=0.45, runs=0.6, scratches=30)
    return col


def _sluice(w: int, h: int, seed: int) -> np.ndarray:
    """The river gate's lintel: DANGER - SLUICE 9 - NO ENTRY between hazard ends, over DEEP WATER - GRATES
    LOCKED."""
    xx, yy = _grid(w, h)
    col = _primer(w, h, seed)
    ends = (xx < 120) | (xx > w - 120)
    col = _ink(col, ends * _hazard_stripes(xx, yy, 80.0), BLACK, 0.9)
    t = _stencil(w, h, [{"s": "DANGER - SLUICE 9 - NO ENTRY", "x": w / 2, "y": 36, "cap": 96, "stroke": 17, "track": 14,
                         "condense": 0.88, "align": "center", "fit": w - 300}])
    col = _ink(col, _overspray(t, seed + 1), RED, 0.95)
    t2 = _stencil(w, h, [{"s": "DEEP WATER - GRATES LOCKED", "x": w / 2, "y": 166, "cap": 52, "stroke": 9, "track": 10,
                          "align": "center", "fit": w - 340}])
    col = _ink(col, _overspray(t2, seed + 2), BLACK, 0.9)
    col, _, _ = _age(col, seed + 3, fade=0.3, grime=0.6, runs=0.7, scratches=40)
    return col


def _board(w: int, h: int, seed: int, text: str) -> np.ndarray:
    """A name board: black stencils on Program yellow between hazard-striped ends."""
    xx, yy = _grid(w, h)
    col = _fill(w, h, YELLOW) * (0.9 + 0.1 * _n(w, h, 1.3, seed))[..., None]
    ends = (xx < 56) | (xx > w - 56)
    col = _ink(col, ends * _hazard_stripes(xx, yy, 32.0), BLACK)
    t = _stencil(w, h, [{"s": text, "x": w / 2, "y": 30, "cap": 64, "stroke": 12, "track": 8, "condense": 0.85,
                         "align": "center", "fit": w - 140}])
    col = _ink(col, _overspray(t, seed + 1), BLACK)
    col, _, _ = _age(col, seed + 2, fade=0.25, grime=0.3, runs=0.35, scratches=24)
    return col


def _notice(w: int, h: int, seed: int, k: int) -> np.ndarray:
    """A typed Program notice: the roundel, a title in type, blocks of small print (illegible at range; the
    readable text is the note item pinned in front of it)."""
    r = np.random.default_rng(seed)
    col = _fill(w, h, "#e4dfcc") * (0.92 + 0.08 * _n(w, h, 1.1, seed))[..., None]
    em = np.zeros((h, w), np.float32)
    em[24:120, 24:120] = _emblem_mask(96)
    col = _ink(col, em, "#2b2b29", 0.85)
    title = ("NOTICE TO SALVAGERS", "STANDING ORDERS")[k % 2]
    t = _font_text(w, h, [(136, 56, "REMAND PROGRAM", _font(TYPE, 22), "lm"), (136, 92, title, _font(TYPE, 20), "lm")])
    col = _ink(col, t, "#1e1e1c")
    col = _ink(col, _print_lines(w, h, r, 26, w - 26, 160, h - 70, 15.0, 3.2), "#3a3936", 0.8)
    col = _ink(col, _print_lines(w, h, r, w - 170, w - 30, h - 52, h - 30, 12.0, 3.0), RED, 0.7)
    col, _, _ = _age(col, seed + 1, fade=0.35, grime=0.25, runs=0.45, scratches=10)
    return col


def _roundel(n: int, seed: int) -> np.ndarray:
    col = _fill(n, n, OLIVE) * (0.9 + 0.1 * _n(n, n, 1.3, seed))[..., None]
    col = _ink(col, _overspray(_emblem_mask(n), seed + 1), YELLOW)
    col, _, _ = _age(col, seed + 2, fade=0.25, grime=0.35, runs=0.4, scratches=30)
    return col


def _chevron(w: int, h: int, seed: int) -> np.ndarray:
    """Red-white chevrons (a gate leaf's and a pier nose's warning band)."""
    xx, yy = _grid(w, h)
    period = 128.0
    t = ((xx + np.abs(yy - h / 2)) / period) % 1.0
    red = np.clip((np.minimum(t, 1.0 - t) - 0.25) / (1.5 / period) + 0.5, 0, 1)
    col = T.mix(_fill(w, h, "#d8d3c6"), _fill(w, h, "#a1271c"), red)
    col, _, _ = _age(col, seed, fade=0.35, grime=0.4, runs=0.4, scratches=60)
    return col


@texture("cordon_print", size=2048, seed=9811, sources=SOURCES)
def cordon_print(size: int, seed: int, out) -> None:
    """Atlas of the Cordon wall's painted stencils and notices (rects: PRINT_RECTS)."""
    col = np.ones((size, size, 3), np.float32) * 0.6
    height = np.full((size, size), 0.5, np.float32)
    rough = np.full((size, size), 0.8, np.float32)
    R = PRINT_RECTS

    def put(name, c, ro=None):
        x0, y0, x1, y1 = R[name]
        col[y0:y1, x0:x1] = c[:y1 - y0, :x1 - x0]
        if ro is not None:
            rough[y0:y1, x0:x1] = ro

    def wh(name):
        x0, y0, x1, y1 = R[name]
        return x1 - x0, y1 - y0

    put("valley", _valley(*wh("valley"), seed + 1), 0.85)
    put("outer", _outer(*wh("outer"), seed + 2), 0.85)
    put("gate", _gate(*wh("gate"), seed + 3), 0.55)
    put("segment", _segment(*wh("segment"), seed + 4), 0.85)
    put("sluice", _sluice(*wh("sluice"), seed + 5), 0.85)
    put("booth", _board(*wh("booth"), seed + 6, "CHECKPOINT 9"), 0.6)
    put("notices", _board(*wh("notices"), seed + 7, "PROGRAM NOTICES"), 0.6)
    put("notice0", _notice(*wh("notice0"), seed + 8, 0), 0.92)
    put("notice1", _notice(*wh("notice1"), seed + 9, 1), 0.92)
    put("roundel", _roundel(wh("roundel")[0], seed + 10), 0.7)
    put("chevron", _chevron(*wh("chevron"), seed + 11), 0.55)
    T.save_pbr_set(out, np.clip(col, 0, 1), np.clip(height, 0, 1), np.clip(rough, 0, 1), normal_strength=1.0)


@texture("cordon_concrete", size=1024, seed=9812)
def cordon_concrete(size: int, seed: int, out) -> None:
    """Tileable precast concrete, 1 tile = 2 m: a pale grey with low-frequency blotching, form-board seams
    every 0.5 m (horizontal), pinhole bug holes and fine aggregate; rough."""
    n1 = T.spectral(size, 1.6, seed)
    n2 = T.spectral(size, 0.9, seed + 1)
    n3 = T.spectral(size, 0.2, seed + 2)
    xx, yy = _grid(size, size)
    base = _fill(size, size, "#a7a49b") * (0.86 + 0.14 * n1)[..., None]
    base = base * (0.95 + 0.05 * n2)[..., None]
    seam_y = (yy % (size / 4.0))
    seam = np.clip(1.0 - np.minimum(seam_y, size / 4.0 - seam_y) / 1.8, 0, 1) * (0.5 + 0.5 * n2)
    base = T.mix(base, _fill(size, size, "#7f7c74"), seam * 0.5)
    holes = T.smoothstep(0.86, 0.93, n3) * T.smoothstep(0.4, 0.7, n2)
    base = T.mix(base, _fill(size, size, "#5e5b55"), holes * 0.8)
    height = 0.5 + 0.08 * (n1 - 0.5) + 0.1 * (n3 - 0.5) - holes * 0.3 - seam * 0.08
    rough = np.clip(0.82 + 0.1 * n2, 0, 1)
    T.save_pbr_set(out, np.clip(base, 0, 1), np.clip(height, 0, 1), rough, normal_strength=1.6)
