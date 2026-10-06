"""Town props II (Pell's Crossing School, Pell Volunteer Fire Station, Tamsin Valley Savings & Loan):
the chalkboard with the Cordon evacuation tallies, the safe-deposit wall, engine-turned vault steel and an
atlas of small printed / painted graphics (gauges, dials, time-lock, backboard, flag, stop arm, card-catalog
label, cash bricks, pump panel).

Everything is procedural (numpy + Pillow line drawing). There is no lettering anywhere: chalk marks are
tally groups, boxes, arrows, crossings-out and map strokes; dials carry only ticks and hands.

Atlases (pixel rects, y down, are a contract with blender/generators/props_town2.py ATLAS / DEP_*):
  town2_print          1024 px: PRINT_RECTS below.
  town2_chalkboard     2048 px: top half = the board as left (clean), bottom half = smeared by an eraser
                       and scrawled over (worn). Each half maps over the 3.4 x 1.1 m writing surface.
  town2_deposit_boxes  1024 px over a 1.8 x 1.8 m face: 8 columns of 0.225 m; rows (top to bottom) 7 x
                       0.12 m, 4 x 0.18 m, 1 x 0.24 m of brass box doors with two key locks each.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from .. import texlib as T
from ..registry import texture

PRINT_RECTS: dict[str, tuple[int, int, int, int]] = {
    "gauge": (0, 0, 128, 128),
    "gauge_red": (128, 0, 256, 128),
    "gauge_black": (0, 128, 128, 256),
    "clock": (128, 128, 256, 256),
    "dial": (256, 0, 512, 256),
    "timelock": (512, 0, 1024, 256),
    "backboard": (0, 256, 512, 560),
    "flag": (512, 256, 1024, 544),
    "stop": (0, 576, 256, 832),
    "card_label": (256, 576, 384, 640),
    "cash_top": (384, 576, 640, 704),
    "cash_side": (384, 704, 640, 768),
    "pump_plate": (640, 576, 1024, 832),
    "felt": (256, 640, 384, 704),
}

# Safe-deposit wall layout (mirrored in props_town2.py).
DEP_COLS = 8
DEP_ROWS = [0.12] * 7 + [0.18] * 4 + [0.24]
DEP_FACE = 1.8


# ------------------------------------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------------------------------------


def _grid(w: int, h: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    yy, xx = np.mgrid[0:(h if h is not None else w), 0:w].astype(np.float32)
    return xx, yy


def _col(h: str) -> np.ndarray:
    return T.hex_rgb(h)[None, None, :]


def _fill(w: int, h: int, c: str) -> np.ndarray:
    return np.ones((h, w, 3), np.float32) * _col(c)


def _rect(xx, yy, x0, y0, x1, y1, soft: float = 1.0) -> np.ndarray:
    m = np.minimum(np.minimum(xx - x0, x1 - xx), np.minimum(yy - y0, y1 - yy))
    return np.clip(m / soft + 0.5, 0, 1)


def _disc(xx, yy, cx, cy, r, soft: float = 1.0) -> np.ndarray:
    return np.clip((r - np.hypot(xx - cx, yy - cy)) / soft + 0.5, 0, 1)


def _ring(xx, yy, cx, cy, r, w, soft: float = 1.0) -> np.ndarray:
    return np.clip((w * 0.5 - np.abs(np.hypot(xx - cx, yy - cy) - r)) / soft + 0.5, 0, 1)


def _noise(w: int, h: int, beta: float, seed: int) -> np.ndarray:
    s = 1 << int(np.ceil(np.log2(max(w, h, 8))))
    return T.spectral(s, beta, seed)[:h, :w]


def _seg(xx, yy, x0, y0, x1, y1, w, soft: float = 1.0) -> np.ndarray:
    ex, ey = x1 - x0, y1 - y0
    t = np.clip(((xx - x0) * ex + (yy - y0) * ey) / max(ex * ex + ey * ey, 1e-6), 0, 1)
    d = np.hypot(xx - x0 - t * ex, yy - y0 - t * ey)
    return np.clip((w * 0.5 - d) / soft + 0.5, 0, 1)


def _resize(a: np.ndarray, w: int, h: int) -> np.ndarray:
    if a.ndim == 3:
        return np.stack([_resize(a[..., i], w, h) for i in range(a.shape[2])], -1)
    im = Image.fromarray(a.astype(np.float32), mode="F").resize((w, h), Image.BILINEAR)
    return np.asarray(im, np.float32)


def _ticks(xx, yy, cx, cy, r0, r1, n, a0, a1, w=1.2) -> np.ndarray:
    """Tick marks on an arc from angle a0 to a1 (degrees, 0 = up, clockwise)."""
    out = np.zeros_like(xx)
    for i in range(n):
        a = np.radians(a0 + (a1 - a0) * i / max(1, n - 1))
        major = (i % 5 == 0)
        rr0 = r0 if major else (r0 + r1) * 0.5
        out = np.maximum(out, _seg(xx, yy, cx + np.sin(a) * rr0, cy - np.cos(a) * rr0, cx + np.sin(a) * r1,
                                   cy - np.cos(a) * r1, w * (1.6 if major else 1.0)))
    return out


# ------------------------------------------------------------------------------------------------
# town2_print atlas cells
# ------------------------------------------------------------------------------------------------


def _gauge(n: int, seed: int, face: str, ink: str, red: bool) -> tuple[np.ndarray, np.ndarray]:
    xx, yy = _grid(n)
    c = n / 2
    R = n * 0.46
    col = _fill(n, n, "#1d1c1a")
    f = _disc(xx, yy, c, c, R * 0.92)
    col = T.mix(col, _fill(n, n, face) * (0.85 + 0.15 * _noise(n, n, 1.6, seed))[..., None], f)
    if red:
        ang = np.degrees(np.arctan2(xx - c, -(yy - c)))
        zone = _ring(xx, yy, c, c, R * 0.72, R * 0.12) * ((ang > 80) & (ang < 135))
        col = T.mix(col, _fill(n, n, "#a3261c"), zone)
    tk = _ticks(xx, yy, c, c, R * 0.62, R * 0.8, 21, -135, 135, 1.2)
    col = T.mix(col, _fill(n, n, ink), tk)
    a = np.radians(-60 + 37 * (seed % 5))
    nd = _seg(xx, yy, c - np.sin(a) * R * 0.12, c + np.cos(a) * R * 0.12, c + np.sin(a) * R * 0.7, c - np.cos(a) * R * 0.7, 2.2)
    col = T.mix(col, _fill(n, n, "#1a1a1a" if face != "#141414" else "#d8d2c0"), nd)
    col = T.mix(col, _fill(n, n, "#3a3a38"), _disc(xx, yy, c, c, R * 0.07))
    rim = _ring(xx, yy, c, c, R * 0.96, R * 0.1)
    col = T.mix(col, _fill(n, n, "#8d8a83") * (0.7 + 0.3 * (1 - yy / n))[..., None], rim)
    # dusty glass: a soft highlight and grime at the bottom
    col = col * (1.0 - 0.18 * T.smoothstep(0.4, 1.0, yy / n) * f)[..., None]
    col = T.mix(col, _fill(n, n, "#ffffff"), _disc(xx, yy, c - R * 0.35, c - R * 0.4, R * 0.25, R * 0.25) * 0.12)
    return col, rim * 0.6 + _disc(xx, yy, c, c, R * 0.07) * 0.4


def _clock(n: int, seed: int) -> np.ndarray:
    xx, yy = _grid(n)
    c = n / 2
    R = n * 0.44
    col = _fill(n, n, "#2a241a")
    col = T.mix(col, _fill(n, n, "#e6e0cc"), _disc(xx, yy, c, c, R))
    col = T.mix(col, _fill(n, n, "#1c1a16"), _ticks(xx, yy, c, c, R * 0.72, R * 0.92, 61, 0, 360, 1.0))
    a1, a2 = np.radians(40 + seed * 47 % 300), np.radians(seed * 131 % 360)
    col = T.mix(col, _fill(n, n, "#1c1a16"), _seg(xx, yy, c, c, c + np.sin(a1) * R * 0.45, c - np.cos(a1) * R * 0.45, 3.0))
    col = T.mix(col, _fill(n, n, "#1c1a16"), _seg(xx, yy, c, c, c + np.sin(a2) * R * 0.7, c - np.cos(a2) * R * 0.7, 2.0))
    col = T.mix(col, _fill(n, n, "#8a6a32"), _ring(xx, yy, c, c, R, 3.0))
    return col


def _dial(n: int, seed: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Combination dial: black face, satin ring with 100 ticks, centre knob boss, index at the top."""
    xx, yy = _grid(n)
    c = n / 2
    R = n * 0.48
    d = np.hypot(xx - c, yy - c)
    col = _fill(n, n, "#111111")
    ring = (d > R * 0.62) & (d < R * 0.98)
    col = np.where(ring[..., None], _fill(n, n, "#b7b5ae") * (0.8 + 0.2 * np.sin(d * 1.3))[..., None], col)
    tk = _ticks(xx, yy, c, c, R * 0.72, R * 0.94, 100, 0, 356.4, 1.1)
    col = T.mix(col, _fill(n, n, "#161616"), tk * ring)
    knob = _disc(xx, yy, c, c, R * 0.42)
    col = T.mix(col, _fill(n, n, "#2c2c2c") * (0.7 + 0.5 * (1 - (yy - c + R) / (2 * R)))[..., None], knob)
    grip = (np.sin(np.arctan2(yy - c, xx - c) * 36) > 0.3) & (d > R * 0.36) & (d < R * 0.42)
    col = np.where(grip[..., None], col * 0.6, col)
    idx = _seg(xx, yy, c, c - R * 0.98, c, c - R * 0.8, 3.0)
    col = T.mix(col, _fill(n, n, "#d9d3c2"), idx)
    h = 0.6 * ring + 0.9 * knob - 0.3 * tk * ring
    metal = ring * 0.9
    return col, h, metal


def _timelock(w: int, h: int, seed: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Time-lock plate: polished brass with a dark glazed window over four movement dials."""
    xx, yy = _grid(w, h)
    t = _noise(w, h, 1.8, seed)
    col = T.mix(_fill(w, h, "#c29a52"), _fill(w, h, "#6b5530"), T.smoothstep(0.45, 0.9, t) * 0.7)
    win = _rect(xx, yy, 24, 40, w - 24, h - 40, 2.0)
    col = T.mix(col, _fill(w, h, "#15140f"), win)
    height = 0.6 - 0.5 * win
    for k in range(4):
        cx = 24 + (w - 48) * (k + 0.5) / 4
        cn = _clock(96, seed + k * 7)
        x0, y0 = int(cx - 48), h // 2 - 48
        col[y0:y0 + 96, x0:x0 + 96] = cn
    # glass highlight + screws
    col = T.mix(col, _fill(w, h, "#ffffff"), _rect(xx, yy, 40, 46, w - 40, 60, 6.0) * 0.12)
    for sx, sy in ((10, 10), (w - 10, 10), (10, h - 10), (w - 10, h - 10)):
        s = _disc(xx, yy, sx, sy, 6)
        col = T.mix(col, _fill(w, h, "#8c7444"), s)
        col = T.mix(col, _fill(w, h, "#2a2214"), _seg(xx, yy, sx - 4, sy, sx + 4, sy, 1.4) * s)
        height = height + s * 0.3
    metal = np.clip(1.0 - win, 0, 1)
    return col, height, metal


def _backboard(w: int, h: int, seed: int) -> np.ndarray:
    """1.8 x 1.05 m board: white paint, a black edge line and the target square (orange) over the rim."""
    xx, yy = _grid(w, h)
    sx, sy = w / 1.8, h / 1.05
    col = _fill(w, h, "#e7e4da") * (0.92 + 0.08 * _noise(w, h, 1.4, seed))[..., None]
    lw = 0.05
    edge = 1.0 - _rect(xx, yy, lw * sx, lw * sy, w - lw * sx, h - lw * sy, 1.0)
    col = T.mix(col, _fill(w, h, "#202020"), edge)
    x0, x1 = w / 2 - 0.305 * sx, w / 2 + 0.305 * sx
    yb, yt = h - 0.15 * sy, h - 0.61 * sy
    outer = _rect(xx, yy, x0, yt, x1, yb, 1.0)
    inner = _rect(xx, yy, x0 + lw * sx, yt + lw * sy, x1 - lw * sx, yb - lw * sy, 1.0)
    col = T.mix(col, _fill(w, h, "#c8481c"), np.clip(outer - inner, 0, 1))
    # chipped paint: grey primer showing through, ball marks
    chips = T.smoothstep(0.78, 0.86, _noise(w, h, 0.9, seed + 3))
    col = T.mix(col, _fill(w, h, "#8d8a80"), chips * 0.8)
    r = np.random.default_rng(seed)
    for _ in range(26):
        cx, cy = r.uniform(0.3, 0.7) * w, r.uniform(0.15, 0.7) * h
        col = col * (1.0 - 0.07 * _disc(xx, yy, cx, cy, r.uniform(5, 9), 4.0))[..., None]
    return col


def _flag(w: int, h: int, seed: int) -> np.ndarray:
    """A sun-bleached striped flag: 13 faded red / grey-white stripes, a washed-out navy canton (no
    stars), grime and rain streaks, the fly end darkened and frayed."""
    xx, yy = _grid(w, h)
    stripe = (np.floor(yy / (h / 13.0)).astype(int) % 2 == 0)
    col = np.where(stripe[..., None], _fill(w, h, "#a8564e"), _fill(w, h, "#d8d2c4"))
    canton = (xx < w * 0.4) & (yy < h * 7 / 13)
    col = np.where(canton[..., None], _fill(w, h, "#36405a"), col)
    weave = 0.94 + 0.06 * np.sin(xx * 2.1) * np.sin(yy * 2.3)
    fade = _noise(w, h, 1.5, seed)
    col = T.mix(col * weave[..., None], _fill(w, h, "#cfc8bb"), T.smoothstep(0.3, 0.9, fade) * 0.45)
    streak = _noise(w, h, 1.2, seed + 1)
    streak = _resize(_resize(streak, w, 8), w, h)
    col = col * (1.0 - 0.25 * T.smoothstep(0.55, 0.9, streak) * (yy / h))[..., None]
    col = col * (1.0 - 0.35 * T.smoothstep(0.7, 1.0, xx / w))[..., None]
    return col


def _stop(n: int, seed: int) -> np.ndarray:
    """Bus stop-arm octagon: red with a white border, no legend."""
    xx, yy = _grid(n)
    c = n / 2
    ang = np.arctan2(yy - c, xx - c)
    d = np.hypot(xx - c, yy - c)
    seg = np.pi / 4
    k = np.cos(((ang + np.pi / 8) % seg) - seg / 2)
    rr = d * k
    col = _fill(n, n, "#b0261d")
    border = (rr > n * 0.40) & (rr < n * 0.46)
    col = np.where(border[..., None], _fill(n, n, "#e3ddd0"), col)
    col = col * (0.85 + 0.15 * _noise(n, n, 1.4, seed))[..., None]
    chips = T.smoothstep(0.8, 0.88, _noise(n, n, 0.9, seed + 2))
    return T.mix(col, _fill(n, n, "#7c7a74"), chips)


def _card_label(w: int, h: int, seed: int) -> np.ndarray:
    xx, yy = _grid(w, h)
    col = _fill(w, h, "#a8843f") * (0.85 + 0.15 * _noise(w, h, 1.6, seed))[..., None]
    card = _rect(xx, yy, 12, 12, w - 12, h - 12, 1.0)
    paper = _fill(w, h, "#d9cfae") * (0.9 + 0.1 * _noise(w, h, 1.0, seed + 1))[..., None]
    col = T.mix(col, paper, card)
    for y in (h * 0.42, h * 0.66):
        col = T.mix(col, _fill(w, h, "#7e7462"), _seg(xx, yy, 22, y, w - 22 - (seed % 3) * 14, y + 1, 1.2) * card * 0.6)
    col = T.mix(col, _fill(w, h, "#3a2c14"), _disc(xx, yy, 6, h / 2, 3) + _disc(xx, yy, w - 6, h / 2, 3))
    return col


def _cash(w: int, h: int, seed: int, side: bool) -> np.ndarray:
    xx, yy = _grid(w, h)
    if side:
        lines = 0.85 + 0.15 * np.sin(yy * 2.7 + _noise(w, h, 1.0, seed) * 4)
        col = _fill(w, h, "#b9bea6") * lines[..., None]
    else:
        col = _fill(w, h, "#a9b29a") * (0.9 + 0.1 * _noise(w, h, 1.2, seed))[..., None]
        border = 1.0 - _rect(xx, yy, 10, 10, w - 10, h - 10, 1.0)
        guil = 0.5 + 0.5 * np.sin(xx * 0.5 + 3 * np.sin(yy * 0.35))
        col = T.mix(col, _fill(w, h, "#4f5e48"), border * guil * 0.8)
        oval = np.clip(1.0 - np.abs(np.hypot((xx - w * 0.3) / 34, (yy - h / 2) / 40) - 1.0) * 10, 0, 1)
        col = T.mix(col, _fill(w, h, "#46553f"), oval * 0.8)
        col = T.mix(col, _fill(w, h, "#d0d2bf"), _disc(xx, yy, w * 0.3, h / 2, 30, 8) * 0.4)
        seal = _ring(xx, yy, w * 0.72, h * 0.5, 16, 3)
        col = T.mix(col, _fill(w, h, "#3d5a40"), seal)
    band = _rect(xx, yy, w * 0.44, -10, w * 0.58, h + 10, 1.0)
    col = T.mix(col, _fill(w, h, "#d3c08f") * (0.9 + 0.1 * _noise(w, h, 1.5, seed + 5))[..., None], band)
    return col


def _pump_plate(w: int, h: int, seed: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Pump operator's panel: brushed aluminium, rivet rows, blank engraved tag plates and the colour
    rings that key each discharge (red, blue, yellow, green, white)."""
    xx, yy = _grid(w, h)
    brush = _resize(_noise(w, 8, 1.0, seed), w, h) * 0.6 + 0.4 * _noise(w, h, 1.0, seed + 1)
    col = _fill(w, h, "#9fa3a3") * (0.85 + 0.2 * brush)[..., None]
    height = 0.3 * brush
    rivets = np.zeros_like(xx)
    for y in (8, h - 8):
        for x in np.arange(10, w, 32):
            rivets = np.maximum(rivets, _disc(xx, yy, x, y, 3.5))
    for x in (8, w - 8):
        for y in np.arange(10, h, 32):
            rivets = np.maximum(rivets, _disc(xx, yy, x, y, 3.5))
    col = T.mix(col, _fill(w, h, "#c8cbc9"), rivets)
    height = height + rivets * 0.6
    cols = ["#b52a1e", "#2d5aa0", "#d2a62a", "#3f8a3c", "#e2ded4"]
    for i, c in enumerate(cols):
        cx = 40 + i * (w - 80) / 4
        tag = _rect(xx, yy, cx - 30, 30, cx + 30, 56, 1.0)
        col = T.mix(col, _fill(w, h, "#1d1d1b"), tag)
        col = T.mix(col, _fill(w, h, "#6c6e6c"), _seg(xx, yy, cx - 20, 43, cx + 12 - i * 3, 43, 2.0) * tag)
        ring = _ring(xx, yy, cx, 150, 34, 9)
        col = T.mix(col, _fill(w, h, c), ring)
        height = height + ring * 0.4 - tag * 0.2
        col = T.mix(col, _fill(w, h, "#2a2a28"), _disc(xx, yy, cx, 150, 26) * 0.85)
    grime = T.smoothstep(0.55, 0.9, _noise(w, h, 1.6, seed + 4))
    col = col * (1.0 - 0.3 * grime)[..., None]
    metal = np.clip(0.85 - 0.8 * np.clip(col.mean(-1) < 0.2, 0, 1), 0, 1)
    return col, height, metal


@texture("town2_print", size=1024, seed=9501)
def town2_print(size: int, seed: int, out) -> None:
    """Atlas of the school / fire station / bank graphics (rects: PRINT_RECTS). No text anywhere."""
    col = np.ones((size, size, 3), np.float32) * 0.5
    height = np.zeros((size, size), np.float32)
    rough = np.full((size, size), 0.7, np.float32)
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

    g, gh = _gauge(128, seed + 1, "#e9e5d8", "#1b1b1b", False)
    put("gauge", g, gh, 0.3)
    g, gh = _gauge(128, seed + 2, "#e2d9bd", "#1b1b1b", True)
    put("gauge_red", g, gh, 0.3)
    g, gh = _gauge(128, seed + 3, "#141414", "#d6d0be", False)
    put("gauge_black", g, gh, 0.3)
    put("clock", _clock(128, seed + 4), None, 0.3)
    dc, dh, dm = _dial(256, seed + 5)
    put("dial", dc, dh, np.clip(0.5 - dm * 0.25, 0, 1), dm)
    tc, th, tm = _timelock(512, 256, seed + 6)
    put("timelock", tc, th, np.clip(0.35 + 0.2 * (1 - tm), 0, 1) * 0 + 0.3, tm)
    put("backboard", _backboard(512, 304, seed + 7), None, 0.55)
    put("flag", _flag(512, 288, seed + 8), _noise(512, 288, 0.8, seed + 9) * 0.3, 0.92)
    put("stop", _stop(256, seed + 10), None, 0.5)
    put("card_label", _card_label(128, 64, seed + 11), None, 0.5, 0.0)
    put("cash_top", _cash(256, 128, seed + 12, False), _noise(256, 128, 1.0, seed + 13) * 0.2, 0.85)
    put("cash_side", _cash(256, 64, seed + 14, True), None, 0.9)
    pc, ph, pm = _pump_plate(384, 256, seed + 15)
    put("pump_plate", pc, ph, 0.45, pm)
    felt = _fill(128, 64, "#56544f") * (0.8 + 0.2 * _noise(128, 64, 0.6, seed + 16))[..., None]
    put("felt", felt, _noise(128, 64, 0.6, seed + 17) * 0.3, 0.98)
    T.save_pbr_set(out, np.clip(col, 0, 1), np.clip(height, 0, 1), np.clip(rough, 0, 1), metal=np.clip(metal, 0, 1),
                   normal_strength=1.5)


# ------------------------------------------------------------------------------------------------
# chalkboard: the Cordon evacuation tallies
# ------------------------------------------------------------------------------------------------

BOARD_W, BOARD_H = 3.4, 1.1


def _jit(r, pts, amt):
    return [(x + r.normal(0, amt), y + r.normal(0, amt)) for x, y in pts]


def _line(r, a, b, n=4, amt=0.003):
    pts = [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n + 1)]
    return _jit(r, pts, amt)


def _tally(r, x, y, n, hgt=0.075, gap=0.022):
    """n tally strokes from (x, y) (top of the marks, board metres, y down): groups of four + a slash."""
    out = []
    k = 0
    while k < n:
        grp = min(5, n - k)
        for i in range(min(4, grp)):
            xx = x + i * gap + r.normal(0, 0.002)
            out.append(_line(r, (xx + r.normal(0, 0.004), y + r.normal(0, 0.004)), (xx + r.normal(0, 0.006), y + hgt), 2))
        if grp == 5:
            out.append(_line(r, (x - 0.012, y + hgt * 0.8), (x + 3 * gap + 0.014, y + hgt * 0.2), 3))
        x += 4 * gap + 0.035
        k += grp
    return out


def _arrow(r, a, b, head=0.05):
    out = [_line(r, a, b, 6, 0.004)]
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = max(1e-6, (dx * dx + dy * dy) ** 0.5)
    ux, uy = dx / L, dy / L
    for s in (-1, 1):
        out.append(_line(r, b, (b[0] - ux * head - uy * head * 0.6 * s, b[1] - uy * head + ux * head * 0.6 * s), 2))
    return out


def _ellipse(r, cx, cy, rx, ry, n=18):
    pts = [(cx + rx * np.cos(2 * np.pi * i / n + 0.3), cy + ry * np.sin(2 * np.pi * i / n + 0.3)) for i in range(n + 2)]
    return [_jit(r, pts, 0.004)]


def _board_strokes(seed: int):
    """Polylines (board metres, origin top-left, y down) of the evacuation tally board."""
    r = np.random.default_rng(seed)
    S = []
    # the roll-call table: 6 columns x 6 rows, header rule doubled
    x0, x1, y0, y1 = 0.14, 2.06, 0.1, 0.94
    cols = [x0 + (x1 - x0) * i / 6 for i in range(7)]
    rows = [y0 + (y1 - y0) * i / 6 for i in range(7)]
    for x in cols:
        S.append(_line(r, (x, y0 - 0.02), (x, y1 + 0.02), 6, 0.004))
    for y in rows:
        S.append(_line(r, (x0 - 0.03, y), (x1 + 0.03, y), 10, 0.003))
    S.append(_line(r, (x0 - 0.03, rows[1] + 0.012), (x1 + 0.03, rows[1] + 0.015), 10, 0.003))
    # header cells: little symbols instead of words (a house, a bus box, a cross, a circle, a check, a wave)
    hx = [(cols[i] + cols[i + 1]) / 2 for i in range(6)]
    hy = (rows[0] + rows[1]) / 2
    S.append(_jit(r, [(hx[0] - 0.04, hy + 0.03), (hx[0] - 0.04, hy - 0.01), (hx[0], hy - 0.045), (hx[0] + 0.04, hy - 0.01),
                      (hx[0] + 0.04, hy + 0.03), (hx[0] - 0.04, hy + 0.03)], 0.003))
    S.append(_jit(r, [(hx[1] - 0.06, hy - 0.03), (hx[1] + 0.06, hy - 0.03), (hx[1] + 0.06, hy + 0.025), (hx[1] - 0.06, hy + 0.025),
                      (hx[1] - 0.06, hy - 0.03)], 0.003))
    S += _ellipse(r, hx[1] - 0.035, hy + 0.035, 0.012, 0.012, 8) + _ellipse(r, hx[1] + 0.035, hy + 0.035, 0.012, 0.012, 8)
    S.append(_line(r, (hx[2], hy - 0.045), (hx[2], hy + 0.045), 2))
    S.append(_line(r, (hx[2] - 0.035, hy - 0.01), (hx[2] + 0.035, hy - 0.01), 2))
    S += _ellipse(r, hx[3], hy, 0.04, 0.035)
    S.append(_jit(r, [(hx[4] - 0.035, hy), (hx[4] - 0.01, hy + 0.035), (hx[4] + 0.04, hy - 0.04)], 0.003))
    for k in (-1, 1):
        S.append(_jit(r, [(hx[5] - 0.06 + 0.01 * i, hy + k * 0.018 + 0.012 * np.sin(i * 0.8)) for i in range(13)], 0.002))
    # body: tally marks per cell, some cells crossed out, a few circled
    for ri in range(1, 6):
        for ci in range(6):
            cx0, cy0 = cols[ci] + 0.03, rows[ri] + 0.03
            roll = r.random()
            if ci == 5 and roll < 0.6:
                S.append(_jit(r, [(cx0 + 0.02, cy0 + 0.05), (cx0 + 0.06, cy0 + 0.09), (cx0 + 0.14, cy0 + 0.01)], 0.004))
                continue
            n = int(r.integers(1, 15)) if ci < 4 else int(r.integers(0, 7))
            S += _tally(r, cx0, cy0, n, 0.07, 0.018)
            if roll < 0.18:
                S.append(_line(r, (cols[ci] + 0.01, rows[ri] + 0.01), (cols[ci + 1] - 0.01, rows[ri + 1] - 0.01), 5, 0.004))
                S.append(_line(r, (cols[ci + 1] - 0.01, rows[ri] + 0.01), (cols[ci] + 0.01, rows[ri + 1] - 0.01), 5, 0.004))
            elif roll < 0.3:
                S += _ellipse(r, (cols[ci] + cols[ci + 1]) / 2, (rows[ri] + rows[ri + 1]) / 2, 0.15, 0.06)
    # totals line under the table with a long run of tallies, underlined twice
    S += _tally(r, x0, 0.97, 22, 0.06, 0.016)
    S.append(_line(r, (x0, 1.045), (1.25, 1.05), 8))
    S.append(_line(r, (x0 + 0.05, 1.065), (1.2, 1.07), 8))
    # arrows from the table to the bus box, which is crossed out
    for k, y in enumerate((0.24, 0.42, 0.6)):
        S += _arrow(r, (2.13, y), (2.5, 0.36 + 0.02 * k))
    bx0, by0, bx1, by1 = 2.56, 0.24, 3.02, 0.46
    S.append(_jit(r, [(bx0, by0), (bx1, by0), (bx1, by1), (bx0, by1), (bx0, by0)], 0.004))
    for i in range(4):
        S.append(_jit(r, [(bx0 + 0.04 + i * 0.1, by0 + 0.04), (bx0 + 0.11 + i * 0.1, by0 + 0.04), (bx0 + 0.11 + i * 0.1, by0 + 0.1),
                          (bx0 + 0.04 + i * 0.1, by0 + 0.1), (bx0 + 0.04 + i * 0.1, by0 + 0.04)], 0.002))
    S += _ellipse(r, bx0 + 0.09, by1 + 0.01, 0.03, 0.03, 10) + _ellipse(r, bx1 - 0.09, by1 + 0.01, 0.03, 0.03, 10)
    S.append(_line(r, (bx0 - 0.05, by0 - 0.05), (bx1 + 0.06, by1 + 0.07), 6, 0.005))
    S.append(_line(r, (bx1 + 0.05, by0 - 0.06), (bx0 - 0.06, by1 + 0.06), 6, 0.005))
    S += _tally(r, 3.08, 0.27, 3, 0.08, 0.02)
    # the route map: river, two roads, the crossing circled with an X, a dotted way out
    S.append(_jit(r, [(2.2 + 0.055 * i, 0.98 - 0.04 * np.sin(i * 0.45)) for i in range(21)], 0.002))
    S.append(_line(r, (2.25, 0.62), (3.3, 0.72), 8))
    S.append(_line(r, (2.7, 0.55), (2.82, 1.04), 8))
    S += _ellipse(r, 2.76, 0.68, 0.06, 0.05)
    S.append(_line(r, (2.71, 0.64), (2.81, 0.72), 2))
    S.append(_line(r, (2.81, 0.64), (2.71, 0.72), 2))
    for i in range(7):
        a = (2.86 + i * 0.06, 0.75 + i * 0.03)
        S.append(_line(r, a, (a[0] + 0.03, a[1] + 0.015), 1))
    S += _arrow(r, (3.25, 0.93), (3.32, 0.97), 0.03)
    return S


def _render_strokes(strokes, w_px: int, h_px: int, width_m: float = 0.008) -> np.ndarray:
    sx, sy = w_px / BOARD_W, h_px / BOARD_H
    im = Image.new("L", (w_px, h_px), 0)
    d = ImageDraw.Draw(im)
    lw = max(2, int(round(width_m * sx)))
    for s in strokes:
        pts = [(x * sx, y * sy) for x, y in s]
        d.line(pts, fill=255, width=lw, joint="curve")
        for p in (pts[0], pts[-1]):
            d.ellipse((p[0] - lw / 2, p[1] - lw / 2, p[0] + lw / 2, p[1] + lw / 2), fill=255)
    return np.asarray(im, np.float32) / 255.0


def _board(w: int, h: int, seed: int, worn: bool) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    wd, hd = int(BOARD_W * 600), int(BOARD_H * 600)  # drawn at 600 px/m, squeezed into the cell
    strokes = _board_strokes(seed)
    chalk = _render_strokes(strokes, wd, hd)
    xx, yy = _grid(wd, hd)
    grain = np.clip(_noise(wd, hd, 0.3, seed + 1) * 1.6 - 0.25, 0, 1)
    chalk = chalk * (0.35 + 0.55 * grain)
    soft = T.blur(chalk, 6.0)
    haze = T.smoothstep(0.3, 0.9, _noise(wd, hd, 1.8, seed + 2)) * 0.18
    if worn:
        r = np.random.default_rng(seed + 7)
        rub = np.zeros_like(chalk)
        for _ in range(9):
            cx, cy = r.uniform(0.3, 3.1) * 600, r.uniform(0.15, 0.95) * 600
            L, Hh = r.uniform(0.5, 1.3) * 600, r.uniform(0.09, 0.16) * 600
            ang = r.uniform(-0.25, 0.25)
            u = (xx - cx) * np.cos(ang) + (yy - cy) * np.sin(ang)
            v = -(xx - cx) * np.sin(ang) + (yy - cy) * np.cos(ang) + 0.00012 * u * u
            band = np.clip(1.0 - np.maximum(np.abs(u) / (L / 2), np.abs(v) / (Hh / 2)) ** 2, 0, 1)
            rub = np.maximum(rub, band * r.uniform(0.6, 0.95))
        smear = T.blur(chalk, 14.0)
        chalk = chalk * (1.0 - rub) + smear * rub * 0.9
        haze = haze + rub * 0.22 * (0.6 + 0.4 * _noise(wd, hd, 1.2, seed + 8))
        # scrawled over afterwards: a hard X across the table and fresh tallies, heavier hand
        r2 = np.random.default_rng(seed + 11)
        late = [_line(r2, (0.3, 0.2), (1.9, 0.85), 10, 0.006), _line(r2, (1.95, 0.18), (0.25, 0.9), 10, 0.006)]
        late += _tally(r2, 2.3, 0.82, 17, 0.1, 0.026)
        late.append(_line(r2, (2.25, 0.79), (3.3, 0.8), 8, 0.004))
        chalk = np.maximum(chalk, _render_strokes(late, wd, hd, 0.011) * (0.6 + 0.4 * grain))
        # water run-marks from the leaking roof
        drips = _resize(_noise(wd, 16, 1.0, seed + 12), wd, hd)
        haze = haze + T.smoothstep(0.7, 0.85, drips) * 0.12 * (yy / hd)
    base = T.mix(_fill(wd, hd, "#24332a"), _fill(wd, hd, "#2f4136"), _noise(wd, hd, 1.6, seed + 3))
    col = T.mix(base, _fill(wd, hd, "#8f9a92"), np.clip(haze, 0, 1))
    col = T.mix(col, _fill(wd, hd, "#e6e4dc"), np.clip(chalk + soft * 0.15, 0, 1))
    height = chalk * 0.4 + _noise(wd, hd, 0.8, seed + 5) * 0.15
    rough = np.clip(0.78 + 0.15 * chalk + 0.05 * haze, 0, 1)
    return _resize(col, w, h), _resize(height, w, h), _resize(rough, w, h)


@texture("town2_chalkboard", size=2048, seed=9511)
def town2_chalkboard(size: int, seed: int, out) -> None:
    """Classroom slate: top half as the Cordon evacuation point left it (roll-call tallies per bus, the
    bus crossed out, the route map); bottom half the same board smeared by an eraser and scrawled over."""
    half = size // 2
    c0, h0, r0 = _board(size, half, seed, False)
    c1, h1, r1 = _board(size, half, seed, True)
    col = np.concatenate([c0, c1], 0)
    height = np.concatenate([h0, h1], 0)
    rough = np.concatenate([r0, r1], 0)
    T.save_pbr_set(out, np.clip(col, 0, 1), np.clip(height, 0, 1), rough, normal_strength=1.0)


# ------------------------------------------------------------------------------------------------
# safe-deposit wall
# ------------------------------------------------------------------------------------------------


def dep_cells() -> list[tuple[float, float, float, float]]:
    """Door rects (x0, z0, x1, z1) in metres on the 1.8 m face, origin bottom-left, row-major from the top."""
    out = []
    z = DEP_FACE
    cw = DEP_FACE / DEP_COLS
    for rh in DEP_ROWS:
        for c in range(DEP_COLS):
            out.append((c * cw, z - rh, (c + 1) * cw, z))
        z -= rh
    return out


@texture("town2_deposit_boxes", size=1024, seed=9521)
def town2_deposit_boxes(size: int, seed: int, out) -> None:
    """Safe-deposit box doors (DEP_COLS x DEP_ROWS): brushed brass in a dark steel grid, hinge knuckles on
    the left, two key locks (renter's + guard's) with round escutcheons, a bar pull on the deeper boxes.
    Blank: no numbers."""
    s = size / DEP_FACE
    col = np.zeros((size, size, 3), np.float32)
    height = np.zeros((size, size), np.float32)
    rough = np.zeros((size, size), np.float32)
    metal = np.zeros((size, size), np.float32)
    tarn = T.spectral(size, 2.2, seed)
    brush = _resize(_noise(size, 8, 1.0, seed + 1), size, size)
    xx, yy = _grid(size)
    col[:] = _col("#1a1814")
    rough[:] = 0.7
    for i, (x0, z0, x1, z1) in enumerate(dep_cells()):
        px0, px1 = x0 * s, x1 * s
        py0, py1 = (DEP_FACE - z1) * s, (DEP_FACE - z0) * s
        ys, ye, xs, xe = int(py0), min(size, int(np.ceil(py1))), int(px0), min(size, int(np.ceil(px1)))
        X, Y = xx[ys:ye, xs:xe], yy[ys:ye, xs:xe]
        door = _rect(X, Y, px0 + 3, py0 + 3, px1 - 3, py1 - 3, 1.0)
        bev = door - _rect(X, Y, px0 + 6, py0 + 6, px1 - 6, py1 - 6, 1.0)
        t = tarn[ys:ye, xs:xe]
        b = brush[ys:ye, xs:xe]
        brass = T.mix(_fill(xe - xs, ye - ys, "#c09a55") * (0.9 + 0.15 * b)[..., None], _fill(xe - xs, ye - ys, "#5f4b2b"),
                      T.smoothstep(0.4, 0.9, t) * 0.75)
        c = T.mix(col[ys:ye, xs:xe], brass, door)
        hgt = door * 0.5 + bev * 0.2
        cy = (py0 + py1) / 2
        cx = (px0 + px1) / 2
        for kx in (px1 - 0.085 * s, px1 - 0.042 * s):
            esc = _disc(X, Y, kx, cy, 0.016 * s)
            c = T.mix(c, _fill(xe - xs, ye - ys, "#d8bd7c"), esc)
            slot = _rect(X, Y, kx - 1.6, cy - 0.009 * s, kx + 1.6, cy + 0.007 * s, 0.8) + _disc(X, Y, kx, cy - 0.006 * s, 2.6)
            c = T.mix(c, _fill(xe - xs, ye - ys, "#0d0b08"), np.clip(slot, 0, 1))
            hgt = hgt + esc * 0.35 - np.clip(slot, 0, 1) * 0.5
        for hz in (py0 + 0.22 * (py1 - py0), py1 - 0.22 * (py1 - py0)):
            kn = _rect(X, Y, px0 + 4, hz - 0.012 * s, px0 + 9, hz + 0.012 * s, 0.8)
            c = T.mix(c, _fill(xe - xs, ye - ys, "#8a7040"), kn)
            hgt = hgt + kn * 0.4
        holder = _rect(X, Y, px0 + 0.03 * s, py0 + 0.022 * s, px0 + 0.085 * s, py0 + 0.045 * s, 0.8)
        hin = _rect(X, Y, px0 + 0.034 * s, py0 + 0.026 * s, px0 + 0.081 * s, py0 + 0.041 * s, 0.8)
        c = T.mix(c, _fill(xe - xs, ye - ys, "#7a6236"), holder)
        c = T.mix(c, _fill(xe - xs, ye - ys, "#cbbd98"), hin * 0.85)
        hgt = hgt + (holder - hin) * 0.3
        col[ys:ye, xs:xe] = c
        height[ys:ye, xs:xe] = np.maximum(height[ys:ye, xs:xe], hgt)
        rough[ys:ye, xs:xe] = np.where(door > 0.5, np.clip(0.28 + 0.45 * T.smoothstep(0.4, 0.9, t), 0, 1), rough[ys:ye, xs:xe])
        metal[ys:ye, xs:xe] = np.maximum(metal[ys:ye, xs:xe], door * 0.95)
    T.save_pbr_set(out, np.clip(col, 0, 1), T.normalize(height), np.clip(rough, 0, 1), metal=np.clip(metal, 0, 1),
                   normal_strength=2.5)


# ------------------------------------------------------------------------------------------------
# vault steel: engine-turned (jewelled) finish
# ------------------------------------------------------------------------------------------------


@texture("town2_vault_steel", size=1024, seed=9531)
def town2_vault_steel(size: int, seed: int, out) -> None:
    """Engine-turned vault-door steel: overlapping rows of circular polishing swirls (each one covering the
    last), over polished steel with faint tarnish and fingerprints. 1 tile = 1 m, spots ~32 mm."""
    pitch = size // 32
    rad = pitch * 0.8
    xx, yy = _grid(size)
    phase = np.zeros((size, size), np.float32)
    d_out = np.full((size, size), 1e9, np.float32)
    n = int(np.ceil(rad)) + 1
    wy, wx = np.mgrid[-n:n + 1, -n:n + 1].astype(np.float32)
    wd = np.hypot(wx, wy)
    inside = wd < rad
    for row in range(32):
        for colu in range(32):
            cx, cy = colu * pitch + (pitch // 2 if row % 2 else 0), row * pitch
            iy = (np.arange(cy - n, cy + n + 1) % size)[:, None]
            ix = (np.arange(cx - n, cx + n + 1) % size)[None, :]
            # later spots overwrite earlier ones where they cover (row-major order)
            phase[iy, ix] = np.where(inside, wd, phase[iy, ix])
            d_out[iy, ix] = np.where(inside, wd, d_out[iy, ix])
    rings = 0.5 + 0.5 * np.sin(phase * 2.2)
    edge = T.smoothstep(rad * 0.75, rad, d_out)
    t = T.spectral(size, 2.0, seed)
    col = _fill(size, size, "#a9abab") * (0.82 + 0.16 * rings + 0.06 * edge)[..., None]
    col = T.mix(col, _fill(size, size, "#6d6a62"), T.smoothstep(0.6, 0.95, t) * 0.5)
    rough = np.clip(0.22 + 0.12 * rings + 0.25 * T.smoothstep(0.6, 0.95, t), 0, 1)
    height = 0.15 * rings - 0.2 * edge
    T.save_pbr_set(out, np.clip(col, 0, 1), T.normalize(height), rough, metal=0.95, normal_strength=0.8)
