"""Larch Hollow outskirts (agent H2): the out_signs lettering atlas and the Ashen's ash decals.

  * out_signs           2048 px, 256 px units (OUT below): the Larch Pond Bait & Boat sign, its LIVE
                        BAIT board and BOAT RENTAL board, the tackle-wall label band and lure cards, the
                        outboard's cowling decal, the Tamsin River Campground entrance sign, site numbers,
                        the CAMP HOST sign, the fee-station and rules boards, the bear-box label, the
                        motorhome's badge and the CAMPGROUND CLOSED notice. The cell rectangles are the
                        contract with blender/generators/props_outskirts.py (ATLAS_OUT, keep both in sync).
  * decal_out_ash_hand  512 px albedo: a hand pressed onto a wall in wet lichen-ash paste.
  * decal_out_ash_ward  1024 px albedo: the Ashen's ward daubed in ash: a broken ring round an antler
                        sign, finger-dabs round it.
Lettering uses the roadside stroke font (textures/gen/roadside.py: no font files), weathering its
_age(); decal helpers come from textures/gen/decals.py.
"""
from __future__ import annotations

import math

import numpy as np

from .. import texlib as T
from ..registry import texture
from . import decals as DC
from . import roadside as RS

UNIT = 256
OUT = {
    "bait_sign": (0, 0, 6, 2), "bait_board": (6, 0, 2, 2),
    "boat_rental": (0, 2, 4, 1), "camp_host": (4, 2, 2, 1), "fee_station": (6, 2, 2, 2),
    "tackle_labels": (0, 3, 4, 1), "motor_decal": (4, 3, 2, 1),
    "camp_sign": (0, 4, 6, 2), "site_numbers": (6, 4, 2, 2),
    "rv_badge": (0, 6, 4, 1), "bear_label": (4, 6, 2, 1), "kiosk_rules": (6, 6, 2, 2),
    "lure_cards": (0, 7, 4, 1), "closed_notice": (4, 7, 2, 1),
}
GREEN = "#2d5a3b"
RED = "#a3302a"
CREAM = "#e6dfcd"
BROWN = "#5b3a22"
INK = "#1b1a18"


def _cell(name: str) -> tuple[int, int]:
    return int(OUT[name][2] * UNIT), int(OUT[name][3] * UNIT)


def _t(s, x, y, cap, stroke, **kw):
    d = {"s": s, "x": x, "y": y, "cap": cap, "stroke": stroke, "align": kw.pop("align", "center")}
    d.update(kw)
    return d


def _trout(w, h, x0, y0, s, flip=False):
    """A jumping trout silhouette (body arc, tail, fins) as polygons, s = body length in px."""
    pts = []
    for i in range(17):
        t = i / 16
        a = math.pi * (0.15 + 0.7 * t)
        bx = x0 + s * t
        by = y0 - s * 0.32 * math.sin(a)
        th = s * 0.11 * math.sin(math.pi * min(1.0, t * 1.08)) ** 0.7 + s * 0.012
        pts.append((bx, by - th, bx, by + th))
    top = [(p[0], p[1]) for p in pts]
    bot = [(p[2], p[3]) for p in reversed(pts)]
    tail_x, tail_y = pts[-1][0], (pts[-1][1] + pts[-1][3]) / 2
    tail = [(tail_x - s * 0.02, tail_y), (tail_x + s * 0.16, tail_y - s * 0.12), (tail_x + s * 0.1, tail_y),
            (tail_x + s * 0.16, tail_y + s * 0.12)]
    fin = [(x0 + s * 0.45, y0 - s * 0.36), (x0 + s * 0.55, y0 - s * 0.48), (x0 + s * 0.6, y0 - s * 0.34)]
    polys = [top + bot, tail, fin]
    if flip:
        polys = [[(2 * x0 + s - x, y) for x, y in p] for p in polys]
    return RS._poly_mask(w, h, polys)


def _border(w, h, inset, width, radius=0.0):
    outer = RS._rect_mask(w, h, [(inset, inset, w - inset, h - inset)], radius=radius)
    inner = RS._rect_mask(w, h, [(inset + width, inset + width, w - inset - width, h - inset - width)],
                          radius=max(0.0, radius - width))
    return np.clip(outer - inner, 0, 1)


def _bait_sign(seed):
    w, h = _cell("bait_sign")
    col = RS._fill(h, w, CREAM)
    col = RS._over(col, GREEN, _border(w, h, 14, 18, radius=10))
    col = RS._over(col, GREEN, RS._text_mask(w, h, [_t("LARCH POND", 610, 70, 112, 20, track=10, fit=1000)]))
    col = RS._over(col, RED, RS._text_mask(w, h, [_t("BAIT & BOAT", 610, 228, 150, 28, track=8, fit=1060)]))
    col = RS._over(col, INK, RS._text_mask(w, h, [_t("CRAWLERS - MINNOWS - TACKLE - RENTALS", 610, 418, 36, 7, track=4,
                                                     fit=1060)]))
    col = RS._over(col, "#3f6e8c", RS._rect_mask(w, h, [(1150, 330, 1470, 345)]), 0.8)
    col = RS._over(col, "#5d6f45", _trout(w, h, 1140, 300, 270))
    col = RS._over(col, CREAM, RS._ellipse_mask(w, h, [(1172, 222, 7, 7)]))
    return RS._age(col, seed, fade=0.35, grime=0.4, runs=0.45, scratches=70)


def _bait_board(seed):
    w, h = _cell("bait_board")
    col = RS._fill(h, w, "#2f3a33")
    col = RS._over(col, "#7a5a3a", _border(w, h, 0, 20))
    col = RS._over(col, CREAM, RS._text_mask(w, h, [_t("LIVE BAIT", w / 2, 50, 62, 12, track=5, fit=440)]))
    col = RS._over(col, CREAM, RS._rect_mask(w, h, [(60, 132, w - 60, 138)]), 0.8)
    items = ["CRAWLERS", "MINNOWS", "LEECHES", "ICE", "LICENSES"]
    col = RS._over(col, "#e9d9a8", RS._text_mask(w, h, [_t(s, w / 2, 160 + i * 64, 36, 6, track=3, fit=400)
                                                         for i, s in enumerate(items)]))
    return RS._age(col, seed, fade=0.25, grime=0.35, runs=0.3, scratches=50)


def _boat_rental(seed):
    w, h = _cell("boat_rental")
    col = RS._fill(h, w, "#dcd5c0")
    col = RS._over(col, "#2f4f7a", _border(w, h, 8, 10))
    col = RS._over(col, "#2f4f7a", RS._text_mask(w, h, [_t("BOAT RENTAL", 380, 70, 92, 17, track=6, fit=640)]))
    col = RS._over(col, RED, RS._text_mask(w, h, [_t("$5 HR", 860, 70, 100, 19, track=4, fit=230)]))
    return RS._age(col, seed, fade=0.3, grime=0.45, runs=0.4, scratches=40)


def _camp_host(seed):
    w, h = _cell("camp_host")
    col = RS._fill(h, w, "#6a4428")
    col = RS._over(col, "#e7d9b0", _border(w, h, 10, 6, radius=8))
    col = RS._over(col, "#e7d9b0", RS._text_mask(w, h, [_t("CAMP HOST", w / 2, 60, 70, 13, track=6, fit=440),
                                                         _t("SITE 1", w / 2, 160, 36, 7, track=4)]))
    return RS._age(col, seed, fade=0.25, grime=0.3, runs=0.2, scratches=30)


def _fee_station(seed):
    w, h = _cell("fee_station")
    col = RS._fill(h, w, "#6a4428")
    col = RS._over(col, "#e7d9b0", _border(w, h, 10, 8, radius=8))
    col = RS._over(col, "#e7d9b0", RS._text_mask(w, h, [_t("FEE STATION", w / 2, 44, 52, 11, track=4, fit=440)]))
    col = RS._over(col, "#e7d9b0", RS._rect_mask(w, h, [(40, 118, w - 40, 124)]))
    lines = [("PAY HERE", 48), ("$8 NIGHT", 56), ("SELF REGISTER", 30), ("ENVELOPES IN BOX", 26), ("TAMSIN CO PARKS", 26)]
    y = 150
    items = []
    for s, cap in lines:
        items.append(_t(s, w / 2, y, cap, max(5, cap * 0.18), track=3, fit=430))
        y += cap + 30
    col = RS._over(col, "#f0e6c4", RS._text_mask(w, h, items))
    return RS._age(col, seed, fade=0.3, grime=0.35, runs=0.3, scratches=40)


def _tackle_labels(seed):
    w, h = _cell("tackle_labels")
    col = RS._fill(h, w, "#2c4e74")
    labels = ["LURES", "HOOKS", "SINKERS", "LINE"]
    cw = w / 4
    items = [_t(s, cw * (i + 0.5), 70, 96, 18, track=6, fit=cw - 30) for i, s in enumerate(labels)]
    col = RS._over(col, "#f2ead2", RS._text_mask(w, h, items))
    for i in range(1, 4):
        col = RS._over(col, "#f2ead2", RS._rect_mask(w, h, [(cw * i - 3, 30, cw * i + 3, h - 30)]), 0.7)
    return RS._age(col, seed, fade=0.2, grime=0.3, runs=0.0, scratches=20)


def _motor_decal(seed):
    w, h = _cell("motor_decal")
    col = RS._fill(h, w, "#2d5089")
    col = RS._over(col, "#f2f0e8", RS._text_mask(w, h, [_t("TIDEWELL", 195, 70, 82, 15, track=4, italic=0.22, fit=330)]))
    col = RS._over(col, "#e3b23c", RS._text_mask(w, h, [_t("9.9", 440, 74, 70, 14, fit=100)]))
    col = RS._over(col, "#f2f0e8", RS._rect_mask(w, h, [(30, 190, w - 30, 198)]))
    return RS._age(col, seed, fade=0.25, grime=0.3, runs=0.0, scratches=60)


def _camp_sign(seed):
    w, h = _cell("camp_sign")
    # Routed cedar: grain stripes, letters cut in and painted cream-yellow.
    grain = RS._noise(h, w, 1.6, seed + 3, aniso=(14.0, 1.0))
    col = T.mix(T.hex_rgb("#6b4126")[None, None, :] * np.ones((h, w, 3), np.float32),
                T.hex_rgb("#8a5a36")[None, None, :] * np.ones((h, w, 3), np.float32), grain)
    letters = RS._text_mask(w, h, [_t("TAMSIN RIVER", 768, 56, 132, 26, track=12, fit=1180),
                                   _t("CAMPGROUND", 768, 238, 118, 24, track=12, fit=1100),
                                   _t("COUNTY PARK", 768, 405, 44, 9, track=8, fit=500)])
    col = RS._over(col, "#e8cf7a", letters)
    for x in (110, 1426):
        pine = [[(x, 120 + k * 50), (x + 40 + k * 14, 190 + k * 52), (x - 40 - k * 14, 190 + k * 52)] for k in range(4)]
        trunk = [[(x - 10, 360), (x + 10, 360), (x + 10, 410), (x - 10, 410)]]
        col = RS._over(col, "#e8cf7a", RS._poly_mask(w, h, pine + trunk))
    hgt_cut = 1.0 - 0.6 * letters
    c, hh, r = RS._age(col, seed, fade=0.3, grime=0.35, runs=0.25, scratches=40)
    return c, np.clip(hh * hgt_cut + 0.1 * grain, 0, 1), r


def _site_numbers(seed):
    w, h = _cell("site_numbers")
    col = RS._fill(h, w, "#6a4428")
    cw, ch = w / 4, h / 2
    items = []
    for i in range(8):
        cx, cy = cw * (i % 4 + 0.5), ch * (i // 4)
        items.append(_t(str(i + 1), cx, cy + 50, 140, 26))
    col = RS._over(col, "#e7d9b0", RS._text_mask(w, h, items))
    for i in range(1, 4):
        col = RS._over(col, "#3d2716", RS._rect_mask(w, h, [(cw * i - 2, 0, cw * i + 2, h)]))
    col = RS._over(col, "#3d2716", RS._rect_mask(w, h, [(0, ch - 2, w, ch + 2)]))
    return RS._age(col, seed, fade=0.3, grime=0.35, runs=0.2, scratches=30)


def _rv_badge(seed):
    w, h = _cell("rv_badge")
    col = RS._fill(h, w, "#e1dbc9")
    col = RS._over(col, "#6a391d", RS._text_mask(w, h, [_t("TRAILHAWK", 470, 64, 104, 17, track=5, italic=0.28, fit=760)]))
    swoosh = []
    for i in range(24):
        t = i / 23
        swoosh.append((60 + 900 * t, 205 - 40 * math.sin(math.pi * t)))
    m = RS._mask(w, h, lambda d, k: d.line([(x * k, y * k) for x, y in swoosh], fill=255, width=int(9 * k)))
    col = RS._over(col, "#c9792a", m)
    return RS._age(col, seed, fade=0.4, grime=0.35, runs=0.3, scratches=30)


def _bear_label(seed):
    w, h = _cell("bear_label")
    col = RS._fill(h, w, "#e2b93b")
    col = RS._over(col, INK, _border(w, h, 8, 8))
    col = RS._over(col, INK, RS._text_mask(w, h, [_t("FOOD STORAGE", w / 2, 34, 50, 10, track=3, fit=440),
                                                   _t("BEARS IN AREA", w / 2, 110, 36, 7, track=3, fit=420),
                                                   _t("KEEP LATCHED", w / 2, 172, 36, 7, track=3, fit=420)]))
    return RS._age(col, seed, fade=0.3, grime=0.3, runs=0.2, scratches=50)


def _kiosk_rules(seed):
    w, h = _cell("kiosk_rules")
    col = RS._fill(h, w, "#efe9da")
    col = RS._over(col, "#2d5a3b", RS._rect_mask(w, h, [(0, 0, w, 96)]))
    col = RS._over(col, "#efe9da", RS._text_mask(w, h, [_t("CAMPGROUND RULES", w / 2, 30, 38, 8, track=3, fit=460)]))
    rules = ["QUIET HOURS 10PM-6AM", "FIRES IN RINGS ONLY", "FOOD IN LOCKERS", "CHECKOUT 12 NOON", "NO PETS OFF LEASH",
             "14 DAY LIMIT"]
    col = RS._over(col, INK, RS._text_mask(w, h, [_t(s, 40, 130 + i * 60, 28, 5.5, align="left", fit=430)
                                                   for i, s in enumerate(rules)]))
    return RS._age(col, seed, fade=0.35, grime=0.4, runs=0.35, scratches=30)


def _lure_cards(seed):
    w, h = _cell("lure_cards")
    col = np.zeros((h, w, 3), np.float32)
    names = ["SPOON", "SPINNER", "JIG", "PLUG", "FLY", "HOOKS", "BOBBER", "SINKER"]
    bgs = ["#c8352c", "#2c5a8a", "#e0b23a", "#3d7a46", "#7a3d8a", "#d06a28", "#2a2a2a", "#3f8a8a"]
    cw, ch = w // 4, h // 2
    rr = np.random.default_rng(seed)
    for i, (nm, bg) in enumerate(zip(names, bgs)):
        x0, y0 = (i % 4) * cw, (i // 4) * ch
        sub = RS._fill(ch, cw, bg)
        sub = RS._over(sub, "#f2ecd8", RS._rect_mask(cw, ch, [(10, 8, cw - 10, 40)], radius=4))
        sub = RS._over(sub, INK, RS._text_mask(cw, ch, [_t(nm, cw / 2, 14, 22, 4.5, track=2, fit=cw - 30)]))
        # The blister with a lure inside: a clear dome over a spoon / plug shape.
        sub = RS._over(sub, "#e8e8e2", RS._ellipse_mask(cw, ch, [(cw / 2, 85, 70, 30)]), 0.35)
        hue = ["#d8d8d0", "#e0a030", "#d0402c", "#2d6aa0"][int(rr.integers(0, 4))]
        sub = RS._over(sub, hue, RS._ellipse_mask(cw, ch, [(cw / 2, 85, 50, 13)]))
        sub = RS._over(sub, INK, RS._ellipse_mask(cw, ch, [(cw / 2 - 38, 82, 4, 4)]))
        col[y0:y0 + ch, x0:x0 + cw] = sub
    return RS._age(col, seed, fade=0.2, grime=0.3, runs=0.0, scratches=30)


def _closed_notice(seed):
    w, h = _cell("closed_notice")
    col = RS._fill(h, w, "#efede6")
    col = RS._over(col, RED, RS._text_mask(w, h, [_t("CAMPGROUND", w / 2, 26, 48, 10, track=3, fit=440),
                                                   _t("CLOSED", w / 2, 92, 66, 13, track=6, fit=400)]))
    col = RS._over(col, INK, RS._text_mask(w, h, [_t("BY ORDER OF THE CORDON", w / 2, 190, 24, 4.5, track=2, fit=440)]))
    return RS._age(col, seed, fade=0.2, grime=0.45, runs=0.5, scratches=20)


@texture("out_signs", size=2048, seed=9601, sources=["tools/assetgen/textures/gen/roadside.py"])
def out_signs(size: int, seed: int, out) -> None:
    """Outskirts signage atlas (layout OUT, 256 px units)."""
    cv = RS._canvas(size)
    makers = {"bait_sign": _bait_sign, "bait_board": _bait_board, "boat_rental": _boat_rental, "camp_host": _camp_host,
              "fee_station": _fee_station, "tackle_labels": _tackle_labels, "motor_decal": _motor_decal,
              "camp_sign": _camp_sign, "site_numbers": _site_numbers, "rv_badge": _rv_badge, "bear_label": _bear_label,
              "kiosk_rules": _kiosk_rules, "lure_cards": _lure_cards, "closed_notice": _closed_notice}
    for i, (name, fn) in enumerate(makers.items()):
        c, hh, r = fn(seed + i * 41)
        RS._put(cv, OUT[name], UNIT, c, hh, r)
    RS._save_canvas(out, cv)


# --------------------------------------------------------------------------------------------
# Ash decals
# --------------------------------------------------------------------------------------------

ASH = "#d3cec5"


@texture("decal_out_ash_hand", size=512, seed=9611, kind="albedo", sources=["tools/assetgen/textures/gen/decals.py"])
def decal_out_ash_hand(size: int, seed: int, out) -> None:
    """A left hand pressed flat on a wall in wet lichen-ash paste: palm, spread fingers and thumb,
    powdery and patchy where the paste ran thin, a drag-mark under the heel (+V down)."""
    n = size
    xx, yy = DC._grid(n, n)
    U = n * 0.0031
    cx, cy = n * 0.5, n * 0.58
    X = -(xx - cx) / U   # mirrored: a left hand
    Y = (yy - cy) / U
    palm = np.minimum.reduce([DC._ellipse(X, Y, -20, 8, 24, 40, 0.1), DC._ellipse(X, Y, 22, 14, 26, 32, -0.45),
                              DC._ellipse(X, Y, 0, 28, 34, 22, 0.0), DC._ellipse(X, Y, 0, -20, 42, 20, 0.05)])
    contact = DC._ss(1.08, 0.9, palm + 0.1 * (DC._noise(n, n, 1.2, seed + 1) - 0.5))
    fingers = [(-30, -32, -1.95, 60, 16), (-11, -40, -1.7, 72, 17.5), (9, -40, -1.45, 70, 17), (28, -33, -1.2, 54, 15)]
    for fx, fy, a, L, wd in fingers:
        bx, by = fx + np.cos(a) * L, fy + np.sin(a) * L
        d, t = DC._capsule(X, Y, fx, fy, bx, by)
        contact = np.maximum(contact, DC._ss(wd * 0.56, wd * 0.4, d) * (0.8 + 0.4 * np.exp(-((t - 0.88) / 0.1) ** 2)))
    d, t = DC._capsule(X, Y, 36, 4, 70, -26)
    contact = np.maximum(contact, DC._ss(10.5, 8.0, d))
    blot = DC._noise(n, n, 1.6, seed + 3)
    fine = DC._noise(n, n, 0.5, seed + 6)
    dens = contact * np.clip(0.25 + 1.1 * blot + 0.6 * (fine - 0.5), 0, 1.1)
    # The paste dragged downward from the heel of the hand.
    streak = DC._noise(n, n, 0.8, seed + 4, aniso=(10.0, 1.0))
    drag = DC._smear(dens * DC._ss(cy + 10 * U, cy + 40 * U, yy), 30, axis=0, streak=streak)
    dens = np.maximum(dens, np.clip(drag, 0, 0.5) * DC._ss(cy, cy + 40 * U, yy))
    a = np.clip(dens, 0, 1) * 0.92 * DC._border_fade(n, n, 0.04)
    c = np.ones((n, n, 3), np.float32) * DC._hex(ASH)[None, None]
    c = c * (0.86 + 0.2 * fine)[..., None] - 0.12 * (1 - np.clip(dens, 0, 1))[..., None]
    DC._save(out, c, a)


@texture("decal_out_ash_ward", size=1024, seed=9612, kind="albedo", sources=["tools/assetgen/textures/gen/decals.py"])
def decal_out_ash_ward(size: int, seed: int, out) -> None:
    """The Ashen ward, daubed with three fingers in ash paste: a ring left open at the bottom, an
    antler sign inside it (a stem with three pairs of tines and a dot above), finger-dabs round the
    ring and soot smudged at the edges of the strokes."""
    n = size
    r = DC._rng(seed)
    ring = DC._arc(n * 0.5, n * 0.5, n * 0.36, np.pi * 0.62, np.pi * 0.62 + 2 * np.pi * 0.84, 70, 0.05, r)
    strokes = [ring, np.array([[0.5, 0.78], [0.5, 0.52], [0.505, 0.3]]) * n]
    for k, (y, spread, up) in enumerate(((0.62, 0.17, 0.12), (0.5, 0.15, 0.11), (0.38, 0.11, 0.09))):
        for s in (-1, 1):
            strokes.append(np.array([[0.5, y], [0.5 + s * spread * 0.55, y - up * 0.6], [0.5 + s * spread, y - up]]) * n)
    dens = DC._spray(n, strokes, r, width=n * 0.016, seed=seed, drips=0.35, shake=2.0)
    xx, yy = DC._grid(n, n)
    dabs = np.zeros((n, n), np.float32)
    for k in range(9):
        a = 2 * np.pi * k / 9 + 0.3
        px, py = n * 0.5 + np.cos(a) * n * 0.45, n * 0.5 + np.sin(a) * n * 0.45
        dabs = np.maximum(dabs, DC._ss(n * 0.022, n * 0.012, np.hypot(xx - px, yy - py)))
    dabs = np.maximum(dabs, DC._ss(n * 0.026, n * 0.014, np.hypot(xx - n * 0.505, yy - n * 0.22)))
    dens = np.maximum(dens, dabs * (0.7 + 0.5 * DC._noise(n, n, 1.0, seed + 2)))
    fine = DC._noise(n, n, 0.6, seed + 9)
    a = (1 - np.exp(-2.8 * dens)) * 0.9 * (0.75 + 0.35 * fine) * DC._border_fade(n, n, 0.03)
    soot = np.clip(DC._blur(dens, n * 0.006) - dens, 0, 1)
    c = np.ones((n, n, 3), np.float32) * DC._hex(ASH)[None, None]
    c = c * (0.88 + 0.16 * fine)[..., None] - (0.55 * soot)[..., None]
    a = np.maximum(a, soot * 0.5 * DC._border_fade(n, n, 0.03))
    DC._save(out, c, a)
