"""Wilderness set pieces, round 3 (agent X): the w3_signs lettering atlas for Camp Tamarack, Elk Ridge
Lodge, the Cordon quarantine camp and the Haldane Place.

  * w3_signs  2048 px, 256 px units (CELLS below): the camp's routed entrance sign and its cabin and
              building plaques, the Cordon's family evacuation board (header, typed lists, snapshots
              and notes), the quarantine camp's ward letters, decontamination steps, the quarantine
              notice, the MORGUE and CORDON COMMAND stencils and the checkpoint sign, the lodge's
              routed sign and the Haldanes' hand-painted warning. The cell rectangles are the contract
              with blender/generators/props_wild3.py (ATLAS, keep both in sync).
Lettering uses the roadside stroke font (textures/gen/roadside.py: no font files), weathered with its
_age(). Every name on it is our own: no real place, brand or emblem.
"""
from __future__ import annotations

import math

import numpy as np

from .. import texlib as T
from ..registry import texture
from . import roadside as RS

UNIT = 256
CELLS = {
    "tamarack_arch": (0, 0, 6, 2),
    "sign_loon": (6, 0, 2, 0.5), "sign_heron": (6, 0.5, 2, 0.5), "sign_osprey": (6, 1, 2, 0.5),
    "sign_kestrel": (6, 1.5, 2, 0.5),
    "sign_mess": (0, 2, 2, 0.5), "sign_lodge": (2, 2, 2, 0.5), "sign_infirmary": (4, 2, 2, 0.5),
    "sign_canoes": (6, 2, 2, 0.5),
    "evac_header": (0, 2.5, 4, 0.5), "evac_lists": (0, 3, 4, 1),
    "evac_photos": (4, 2.5, 2, 1.5), "ward_letters": (6, 2.5, 2, 1.5),
    "decon_steps": (0, 4, 4, 1), "quarantine": (4, 4, 4, 1),
    "morgue": (0, 5, 3, 1), "cordon_cmd": (3, 5, 3, 1), "checkpoint": (6, 5, 2, 1),
    "elk_ridge": (0, 6, 4, 1), "haldane_warn": (4, 6, 4, 1),
    "kennel_names": (0, 7, 4, 1), "lodge_rules": (4, 7, 2, 1), "tally": (6, 7, 2, 1),
}
CEDAR_A = "#6b4126"
CEDAR_B = "#8a5a36"
CREAM = "#e8d9ad"
INK = "#1b1a18"
OD = "#4f5338"
RED = "#a3302a"
WHITE = "#ece9df"


def _wobble(amp: float, seed: int):
    """A hand-painted wobble for the stroke font (jitter(x, y) -> (dx, dy) in pixels)."""
    return lambda x, y: (amp * math.sin(y * 0.09 + seed) + 0.5 * amp * math.sin(x * 0.031 + seed * 2.1),
                         amp * math.cos(x * 0.11 + seed * 1.7))


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


def _cedar(w, h, seed):
    grain = RS._noise(h, w, 1.6, seed + 3, aniso=(14.0, 1.0))
    a = T.hex_rgb(CEDAR_A)[None, None, :] * np.ones((h, w, 3), np.float32)
    b = T.hex_rgb(CEDAR_B)[None, None, :] * np.ones((h, w, 3), np.float32)
    return T.mix(a, b, grain), grain


def _routed(name, lines, seed, *, motif=None, fade=0.3):
    """Routed cedar board: grain stripes, letters cut in and painted cream; returns the aged set with
    the letters cut into the height map."""
    w, h = _cell(name)
    col, grain = _cedar(w, h, seed)
    letters = RS._text_mask(w, h, lines)
    if motif is not None:
        letters = np.clip(letters + motif(w, h), 0, 1)
    col = RS._over(col, CREAM, letters)
    c, hh, r = RS._age(col, seed, fade=fade, grime=0.35, runs=0.25, scratches=40)
    return c, np.clip(hh * (1.0 - 0.6 * letters) + 0.1 * grain, 0, 1), r


def _pines(xs, top, h_unit):
    def fn(w, h):
        polys = []
        for x in xs:
            for k in range(4):
                polys.append([(x, top + k * h_unit * 0.5), (x + h_unit * (0.45 + k * 0.16), top + h_unit * (0.75 + k * 0.52)),
                              (x - h_unit * (0.45 + k * 0.16), top + h_unit * (0.75 + k * 0.52))])
            polys.append([(x - h_unit * 0.1, top + h_unit * 2.3), (x + h_unit * 0.1, top + h_unit * 2.3),
                          (x + h_unit * 0.1, top + h_unit * 2.75), (x - h_unit * 0.1, top + h_unit * 2.75)])
        return RS._poly_mask(w, h, polys)
    return fn


def _tamarack_arch(seed):
    w, h = _cell("tamarack_arch")
    lines = [_t("CAMP", 768, 40, 92, 18, track=24, fit=600), _t("TAMARACK", 768, 170, 150, 30, track=14, fit=1000),
             _t("EST. ON THE LAKE - ALL WELCOME", 768, 404, 40, 8, track=6, fit=900)]
    return _routed("tamarack_arch", lines, seed, motif=_pines((112, 1424), 110, 96))


def _plaque(name, text, seed):
    w, h = _cell(name)
    return _routed(name, [_t(text, w / 2, h / 2 - 34, 68, 13, track=8, fit=w - 70)], seed, fade=0.35)


def _evac_header(seed):
    w, h = _cell("evac_header")
    col = RS._fill(h, w, WHITE)
    col = RS._over(col, "#1f3f63", RS._rect_mask(w, h, [(0, 0, w, h)]), 1.0)
    col = RS._over(col, WHITE, RS._text_mask(w, h, [_t("FAMILY EVACUATION POINT 6", w / 2, 18, 50, 10, track=6, fit=980),
                                                    _t("REGISTER EVERY PERSON - ONE FAMILY PER CABIN", w / 2, 82, 26, 5, track=3,
                                                       fit=900)]))
    return RS._age(col, seed, fade=0.25, grime=0.35, runs=0.4, scratches=20)


def _evac_lists(seed):
    w, h = _cell("evac_lists")
    col = RS._fill(h, w, "#efeee6")
    rr = np.random.default_rng(seed)
    # Three typed sheets taped side by side, ruled rows of "names" (short bars), a column of ticks.
    items = []
    for sx in range(3):
        x0 = 18 + sx * 336
        col = RS._over(col, "#f7f6ef", RS._rect_mask(w, h, [(x0, 12, x0 + 316, h - 12)]))
        col = RS._over(col, "#d8c27a", RS._rect_mask(w, h, [(x0 + 120, 4, x0 + 196, 22)]), 0.8)
        items.append(_t(["FAMILY", "CABIN", "CONVOY"][sx], x0 + 158, 26, 22, 4.5, track=3, fit=280))
        bars = []
        for row in range(10):
            y = 64 + row * 18
            n = int(rr.integers(2, 5))
            x = x0 + 14
            for _ in range(n):
                L = int(rr.integers(22, 70))
                bars.append((x, y, x + L, y + 6))
                x += L + 8
            if rr.random() < 0.5:
                bars.append((x0 + 286, y - 2, x0 + 300, y + 8))
        col = RS._over(col, "#2a2b30", RS._rect_mask(w, h, bars), 0.85)
        for _ in range(int(rr.integers(1, 4))):
            ry = 64 + int(rr.integers(0, 10)) * 18 + 2
            col = RS._over(col, "#a33a2a", RS._rect_mask(w, h, [(x0 + 8, ry, x0 + 270, ry + 3)]), 0.85)
    col = RS._over(col, INK, RS._text_mask(w, h, items))
    return RS._age(col, seed, fade=0.2, grime=0.3, runs=0.35, scratches=10)


def _evac_photos(seed):
    w, h = _cell("evac_photos")
    col = RS._fill(h, w, "#c8b48a")  # cork
    col = RS._over(col, "#9c875e", (RS._noise(h, w, 2.2, seed) > 0.62).astype(np.float32), 0.5)
    rr = np.random.default_rng(seed + 1)
    for k in range(9):
        cx, cy = 60 + (k % 3) * 160 + int(rr.integers(-14, 14)), 50 + (k // 3) * 120 + int(rr.integers(-10, 10))
        pw, ph = int(rr.integers(84, 112)), int(rr.integers(64, 86))
        col = RS._over(col, "#f2efe6", RS._rect_mask(w, h, [(cx - pw // 2, cy - ph // 2, cx + pw // 2, cy + ph // 2)]))
        if k % 3 != 2:
            hue = ["#5f7d93", "#7e6a4b", "#6d8457", "#8c5a4a", "#55606e"][int(rr.integers(0, 5))]
            col = RS._over(col, hue, RS._rect_mask(w, h, [(cx - pw // 2 + 7, cy - ph // 2 + 7, cx + pw // 2 - 7, cy + ph // 2 - 18)]))
            # Two figures: head and shoulders blobs.
            for f in range(int(rr.integers(1, 4))):
                fx = cx - pw // 4 + f * (pw // 4)
                col = RS._over(col, "#2c2722", RS._ellipse_mask(w, h, [(fx, cy - 4, 9, 11)]), 0.7)
                col = RS._over(col, "#2c2722", RS._ellipse_mask(w, h, [(fx, cy + 18, 17, 12)]), 0.7)
        else:
            lines = [(cx - pw // 2 + 8, cy - ph // 2 + 12 + i * 12, cx - pw // 2 + 8 + int(rr.integers(30, pw - 16)),
                      cy - ph // 2 + 15 + i * 12) for i in range(5)]
            col = RS._over(col, "#2c3570", RS._rect_mask(w, h, lines), 0.8)
        col = RS._over(col, "#c23a2a", RS._ellipse_mask(w, h, [(cx, cy - ph // 2 + 4, 5, 5)]))
    return RS._age(col, seed, fade=0.25, grime=0.3, runs=0.2, scratches=10)


def _ward_letters(seed):
    w, h = _cell("ward_letters")
    col = RS._fill(h, w, OD)
    cw, ch = w // 2, h // 2
    items = []
    for i, s in enumerate("ABCD"):
        items.append(_t(s, cw * (i % 2) + cw / 2, ch * (i // 2) + 36, 120, 22))
    col = RS._over(col, WHITE, RS._text_mask(w, h, items))
    for i in range(1, 2):
        col = RS._over(col, "#2c2f22", RS._rect_mask(w, h, [(cw * i - 3, 0, cw * i + 3, h), (0, ch - 3, w, ch + 3)]))
    return RS._age(col, seed, fade=0.35, grime=0.45, runs=0.4, scratches=30)


def _decon_steps(seed):
    w, h = _cell("decon_steps")
    col = RS._fill(h, w, "#e2b93b")
    cw = w // 3
    items = []
    for i, (n, s) in enumerate((("1", "STRIP"), ("2", "SHOWER"), ("3", "DRESS"))):
        x = cw * i + cw / 2
        items.append(_t(n, x, 20, 110, 20))
        items.append(_t(s, x, 160, 46, 9, track=4, fit=cw - 40))
    col = RS._over(col, INK, RS._text_mask(w, h, items))
    for i in range(1, 3):
        col = RS._over(col, INK, RS._rect_mask(w, h, [(cw * i - 3, 10, cw * i + 3, h - 10)]))
    col = RS._over(col, INK, _border(w, h, 6, 6))
    return RS._age(col, seed, fade=0.3, grime=0.4, runs=0.35, scratches=30)


def _quarantine(seed):
    w, h = _cell("quarantine")
    col = RS._fill(h, w, WHITE)
    col = RS._over(col, RED, RS._rect_mask(w, h, [(0, 0, w, 92)]))
    col = RS._over(col, WHITE, RS._text_mask(w, h, [_t("QUARANTINE", w / 2, 14, 64, 13, track=10, fit=900)]))
    col = RS._over(col, INK, RS._text_mask(w, h, [_t("AUTHORIZED PERSONNEL ONLY", w / 2, 116, 40, 8, track=4, fit=940),
                                                   _t("CORDON MEDICAL AUTHORITY", w / 2, 186, 28, 5.5, track=4, fit=700)]))
    return RS._age(col, seed, fade=0.25, grime=0.4, runs=0.45, scratches=25)


def _stencil(name, lines, seed, base, ink, **age):
    w, h = _cell(name)
    col = RS._fill(h, w, base)
    col = RS._over(col, ink, RS._text_mask(w, h, lines))
    return RS._age(col, seed, **age)


def _morgue(seed):
    w, h = _cell("morgue")
    return _stencil("morgue", [_t("MORGUE", w / 2, 30, 110, 22, track=16, fit=700),
                               _t("DO NOT OPEN - CORDON MEDICAL", w / 2, 176, 34, 7, track=4, fit=700)], seed,
                    "#e4e2dc", "#2a2a2c", fade=0.2, grime=0.5, runs=0.6, scratches=20)


def _cordon_cmd(seed):
    w, h = _cell("cordon_cmd")
    return _stencil("cordon_cmd", [_t("CORDON", w / 2, 26, 96, 19, track=14, fit=700),
                                   _t("COMMAND - UNIT 4", w / 2, 160, 48, 9, track=6, fit=640)], seed,
                    "#e4e2dc", "#26324a", fade=0.2, grime=0.45, runs=0.5, scratches=20)


def _checkpoint(seed):
    w, h = _cell("checkpoint")
    col = RS._fill(h, w, RED)
    col = RS._over(col, WHITE, _border(w, h, 10, 8))
    col = RS._over(col, WHITE, RS._text_mask(w, h, [_t("STOP", w / 2, 30, 96, 19, track=10, fit=420),
                                                    _t("CHECKPOINT", w / 2, 170, 36, 7, track=4, fit=420)]))
    return RS._age(col, seed, fade=0.3, grime=0.4, runs=0.35, scratches=30)


def _elk_ridge(seed):
    w, h = _cell("elk_ridge")

    def antlers(ww, hh):
        polys = []
        for sx in (-1, 1):
            cx = ww / 2 + sx * 430
            polys.append([(cx, 200), (cx + sx * 12, 60), (cx + sx * 26, 60), (cx + sx * 14, 200)])
            for k in range(3):
                y = 170 - k * 40
                polys.append([(cx + sx * 8, y), (cx + sx * 70, y - 36), (cx + sx * 74, y - 26), (cx + sx * 14, y + 8)])
        return RS._poly_mask(ww, hh, polys)
    return _routed("elk_ridge", [_t("ELK RIDGE LODGE", w / 2, 40, 82, 17, track=10, fit=760),
                                 _t("GUIDED HUNTS - CABINS - MEALS", w / 2, 168, 34, 7, track=6, fit=700)], seed, motif=antlers)


def _haldane_warn(seed):
    w, h = _cell("haldane_warn")
    grain = RS._noise(h, w, 1.4, seed + 5, aniso=(10.0, 1.0))
    col = T.mix(T.hex_rgb("#a68b63")[None, None, :] * np.ones((h, w, 3), np.float32),
                T.hex_rgb("#8b7350")[None, None, :] * np.ones((h, w, 3), np.float32), grain)
    lines = [_t("TURN BACK", w / 2 - 20, 22, 92, 22, jitter=_wobble(4.0, seed), fit=860),
             _t("WE ARE ARMED - WE ARE NOT SICK", w / 2, 150, 40, 10, jitter=_wobble(2.5, seed + 1), fit=900)]
    paint = RS._text_mask(w, h, lines)
    col = RS._over(col, "#7d1e18", paint)
    drips = RS._rect_mask(w, h, [(160 + k * 97 % 700, 120, 164 + k * 97 % 700, 120 + 12 + k * 13 % 40) for k in range(9)])
    col = RS._over(col, "#7d1e18", drips, 0.8)
    return RS._age(col, seed, fade=0.3, grime=0.5, runs=0.5, scratches=50, holes=3)


def _kennel_names(seed):
    w, h = _cell("kennel_names")
    cw = w // 4
    items = []
    for i, s in enumerate(("BELLE", "DUKE", "ROSIE", "JACK")):
        items.append(_t(s, cw * i + cw / 2, 90, 46, 9, track=4, fit=cw - 40, jitter=_wobble(1.5, seed + i)))
    col, grain = _cedar(w, h, seed)
    col = RS._over(col, "#f0e6c8", RS._text_mask(w, h, items))
    for i in range(1, 4):
        col = RS._over(col, "#3d2716", RS._rect_mask(w, h, [(cw * i - 3, 0, cw * i + 3, h)]))
    return RS._age(col, seed, fade=0.3, grime=0.4, runs=0.2, scratches=40)


def _lodge_rules(seed):
    w, h = _cell("lodge_rules")
    col = RS._fill(h, w, "#efe9da")
    col = RS._over(col, "#5b3a22", RS._rect_mask(w, h, [(0, 0, w, 64)]))
    col = RS._over(col, "#efe9da", RS._text_mask(w, h, [_t("LODGE RULES", w / 2, 16, 32, 6, track=4, fit=440)]))
    rules = ["GUNS UNLOADED INSIDE", "BOOTS OFF AT THE DOOR", "BREAKFAST AT FIVE", "TAG EVERY ANIMAL"]
    col = RS._over(col, INK, RS._text_mask(w, h, [_t(s, 30, 88 + i * 40, 22, 4.5, align="left", fit=450)
                                                   for i, s in enumerate(rules)]))
    return RS._age(col, seed, fade=0.35, grime=0.4, runs=0.3, scratches=30)


def _tally(seed):
    w, h = _cell("tally")
    col = RS._fill(h, w, "#8f7a5a")
    rr = np.random.default_rng(seed)
    marks = []
    for g in range(9):
        x0 = 20 + g * 54
        y0 = 30 + (g % 2) * 110
        for k in range(4):
            marks.append([(x0 + k * 9, y0), (x0 + k * 9 + 4, y0), (x0 + k * 9 + 6, y0 + 70), (x0 + k * 9 + 2, y0 + 70)])
        marks.append([(x0 - 6, y0 + 50), (x0 + 40, y0 + 14), (x0 + 42, y0 + 19), (x0 - 4, y0 + 55)])
    _ = rr
    col = RS._over(col, "#e3d8c2", RS._poly_mask(w, h, marks), 0.85)
    return RS._age(col, seed, fade=0.2, grime=0.45, runs=0.3, scratches=80)


@texture("w3_signs", size=2048, seed=9801, sources=["tools/assetgen/textures/gen/roadside.py"])
def w3_signs(size: int, seed: int, out) -> None:
    """Round-3 wilderness signage atlas (layout CELLS, 256 px units)."""
    cv = RS._canvas(size)
    makers = {
        "tamarack_arch": _tamarack_arch,
        "sign_loon": lambda s: _plaque("sign_loon", "LOON", s),
        "sign_heron": lambda s: _plaque("sign_heron", "HERON", s),
        "sign_osprey": lambda s: _plaque("sign_osprey", "OSPREY", s),
        "sign_kestrel": lambda s: _plaque("sign_kestrel", "KESTREL", s),
        "sign_mess": lambda s: _plaque("sign_mess", "MESS HALL", s),
        "sign_lodge": lambda s: _plaque("sign_lodge", "STAFF LODGE", s),
        "sign_infirmary": lambda s: _plaque("sign_infirmary", "INFIRMARY", s),
        "sign_canoes": lambda s: _plaque("sign_canoes", "CANOES", s),
        "evac_header": _evac_header, "evac_lists": _evac_lists, "evac_photos": _evac_photos,
        "ward_letters": _ward_letters, "decon_steps": _decon_steps, "quarantine": _quarantine,
        "morgue": _morgue, "cordon_cmd": _cordon_cmd, "checkpoint": _checkpoint,
        "elk_ridge": _elk_ridge, "haldane_warn": _haldane_warn, "kennel_names": _kennel_names,
        "lodge_rules": _lodge_rules, "tally": _tally,
    }
    for i, (name, fn) in enumerate(makers.items()):
        c, hh, r = fn(seed + i * 41)
        RS._put(cv, CELLS[name], UNIT, c, hh, r)
    RS._save_canvas(out, cv)
    _ = math
