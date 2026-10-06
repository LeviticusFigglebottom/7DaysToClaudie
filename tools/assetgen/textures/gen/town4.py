"""Town props IV ("pool round 2": the cannery, the water works pump house, the quarry office, the Pawn & Gun
and the VFW post): one atlas of small printed / painted graphics.

Everything is procedural (numpy + Pillow shapes). There is no lettering anywhere and no real brand, logo or
national flag: dials carry only ticks and hands, hazard placards carry pictograms only, labels and tags are
blank or carry illegible ruled strokes, photographs are blurred figures, the flags are a plain post flag
and a plain banded flag.

Atlas (pixel rects, y down, are a contract with blender/generators/props_town4.py ATLAS):
  town4_print  1024 px: PRINT_RECTS below.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from .. import texlib as T
from ..registry import texture

PRINT_RECTS: dict[str, tuple[int, int, int, int]] = {
    "gauge": (0, 0, 128, 128),
    "gauge_red": (128, 0, 256, 128),
    "gauge_black": (256, 0, 384, 128),
    "can_end": (384, 0, 512, 128),
    "pict_explosive": (512, 0, 640, 128),
    "pict_flame": (640, 0, 768, 128),
    "pict_gas": (768, 0, 896, 128),
    "pict_warn": (896, 0, 1024, 128),
    "chart": (0, 128, 256, 384),
    "mimic": (256, 128, 768, 384),
    "nameplate": (768, 128, 1024, 256),
    "lcd": (768, 256, 1024, 320),
    "hazard": (768, 320, 1024, 384),
    "photo0": (0, 384, 128, 544),
    "photo1": (128, 384, 256, 544),
    "photo2": (256, 384, 384, 544),
    "photo3": (384, 384, 512, 544),
    "photo4": (512, 384, 640, 544),
    "photo5": (640, 384, 768, 544),
    "plaque": (768, 384, 896, 544),
    "certificate": (896, 384, 1024, 544),
    "flag_a": (0, 544, 256, 704),
    "flag_b": (256, 544, 512, 704),
    "sunburst": (512, 544, 672, 704),
    "ribbon0": (672, 544, 736, 640),
    "ribbon1": (736, 544, 800, 640),
    "ribbon2": (800, 544, 864, 640),
    "ribbon3": (864, 544, 928, 640),
    "velvet": (928, 544, 1024, 640),
    "felt_black": (672, 640, 800, 704),
    "price_tag": (800, 640, 928, 704),
    "velvet_red": (928, 640, 1024, 704),
    "ammo0": (0, 704, 192, 800),
    "ammo1": (192, 704, 384, 800),
    "ammo2": (384, 704, 576, 800),
    "ammo3": (576, 704, 768, 800),
    "ammo_end": (768, 704, 896, 800),
    "fish_slime": (896, 704, 1024, 800),
    "painting": (0, 800, 256, 1024),
    "site_plan": (256, 800, 512, 1024),
    "clip_sheet": (512, 800, 768, 1024),
    "emblem": (768, 800, 1024, 1024),
}


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


def _shape(w: int, h: int, polys=(), ellipses=(), lines=(), ss: int = 4) -> np.ndarray:
    """Anti-aliased mask of polygons [(pts)], ellipses [(x0, y0, x1, y1)] and lines [(pts, width)] in pixels
    (drawn 4x supersampled with Pillow, then box-filtered down)."""
    im = Image.new("L", (w * ss, h * ss), 0)
    d = ImageDraw.Draw(im)
    for pts in polys:
        d.polygon([(x * ss, y * ss) for x, y in pts], fill=255)
    for x0, y0, x1, y1 in ellipses:
        d.ellipse((x0 * ss, y0 * ss, x1 * ss, y1 * ss), fill=255)
    for pts, lw in lines:
        d.line([(x * ss, y * ss) for x, y in pts], fill=255, width=max(1, int(lw * ss)), joint="curve")
    im = im.resize((w, h), Image.BOX)
    return np.asarray(im, np.float32) / 255.0


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


def _scribble(r: np.random.Generator, x0: float, y: float, x1: float, amp: float, n: int = 0) -> list:
    """An illegible hand-written stroke: a jittered wave along a ruled line (never letter shapes)."""
    n = n or max(4, int((x1 - x0) / 5))
    pts = []
    for i in range(n + 1):
        x = x0 + (x1 - x0) * i / n
        pts.append((x, y + np.sin(i * 1.9 + r.uniform(0, 1.0)) * amp * r.uniform(0.4, 1.0)))
    return pts


# ------------------------------------------------------------------------------------------------
# cells
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
        green = _ring(xx, yy, c, c, R * 0.72, R * 0.12) * ((ang > -60) & (ang < 30))
        col = T.mix(col, _fill(n, n, "#3e7a3a"), green)
    tk = _ticks(xx, yy, c, c, R * 0.62, R * 0.8, 21, -135, 135, 1.2)
    col = T.mix(col, _fill(n, n, ink), tk)
    a = np.radians(-60 + 37 * (seed % 5))
    nd = _seg(xx, yy, c - np.sin(a) * R * 0.12, c + np.cos(a) * R * 0.12, c + np.sin(a) * R * 0.7, c - np.cos(a) * R * 0.7, 2.2)
    col = T.mix(col, _fill(n, n, "#1a1a1a" if face != "#141414" else "#d8d2c0"), nd)
    col = T.mix(col, _fill(n, n, "#3a3a38"), _disc(xx, yy, c, c, R * 0.07))
    rim = _ring(xx, yy, c, c, R * 0.96, R * 0.1)
    col = T.mix(col, _fill(n, n, "#8d8a83") * (0.7 + 0.3 * (1 - yy / n))[..., None], rim)
    col = col * (1.0 - 0.2 * T.smoothstep(0.4, 1.0, yy / n) * f)[..., None]
    col = T.mix(col, _fill(n, n, "#ffffff"), _disc(xx, yy, c - R * 0.35, c - R * 0.4, R * 0.25, R * 0.25) * 0.12)
    return col, rim * 0.6 + _disc(xx, yy, c, c, R * 0.07) * 0.4


def _can_end(n: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Tinplate can end seen from above: the double seam rim, the countersink and the expansion rings."""
    xx, yy = _grid(n)
    c = n / 2
    d = np.hypot(xx - c, yy - c) / (n * 0.5)
    h = np.zeros_like(d)
    h += T.smoothstep(0.86, 0.92, d) * T.smoothstep(1.0, 0.95, d) * 1.0  # seam
    h -= T.smoothstep(0.8, 0.86, d) * T.smoothstep(0.92, 0.86, d) * 0.6  # countersink
    for r0 in (0.35, 0.55, 0.7):
        h += np.clip(1.0 - np.abs(d - r0) / 0.03, 0, 1) * 0.35
    shade = 0.62 + 0.45 * np.clip(h, -0.6, 1.0) + 0.2 * (1 - yy / n)
    col = _fill(n, n, "#bdbdb6") * shade[..., None]
    col = col * (0.92 + 0.08 * _noise(n, n, 1.5, seed))[..., None]
    col = T.mix(col, _fill(n, n, "#6d6a62"), T.smoothstep(0.72, 0.9, _noise(n, n, 1.8, seed + 1)) * 0.5)
    return col, h


def _placard(n: int, seed: int, kind: str) -> np.ndarray:
    """Hazard pictogram placards with no words. explosive: orange diamond, black bursting bomb; flame: white
    disc, black flame, red ring-and-slash; gas: white diamond, skull over crossed bones; warn: yellow
    triangle, black exclamation bar and dot."""
    xx, yy = _grid(n)
    c = n / 2
    col = _fill(n, n, "#d8d4c8")
    m = 0.06 * n
    if kind in ("explosive", "gas"):
        dia = _shape(n, n, polys=[[(c, m), (n - m, c), (c, n - m), (m, c)]])
        inner = _shape(n, n, polys=[[(c, m + 6), (n - m - 6, c), (c, n - m - 6), (m + 6, c)]])
        bg = "#e0782a" if kind == "explosive" else "#ecebe4"
        col = T.mix(col, _fill(n, n, "#1b1b1b"), dia)
        col = T.mix(col, _fill(n, n, bg), inner)
        if kind == "explosive":
            pts = []
            for i in range(24):
                a = 2 * np.pi * i / 24
                rr = (0.3 if i % 2 == 0 else 0.15) * n * (1.0 + 0.12 * np.sin(i * 2.7))
                pts.append((c + np.cos(a) * rr, c * 0.86 + np.sin(a) * rr))
            burst = _shape(n, n, polys=[pts])
            col = T.mix(col, _fill(n, n, "#1b1b1b"), burst * inner)
            frag = _shape(n, n, ellipses=[(c - 30, c + 16, c - 24, c + 22), (c + 22, c + 14, c + 28, c + 20),
                                          (c - 4, c + 24, c + 3, c + 31)])
            col = T.mix(col, _fill(n, n, "#1b1b1b"), frag * inner)
        else:
            skull = _shape(n, n, ellipses=[(c - 17, c - 30, c + 17, c + 2)],
                           polys=[[(c - 11, c - 2), (c + 11, c - 2), (c + 9, c + 8), (c - 9, c + 8)]])
            eyes = _shape(n, n, ellipses=[(c - 11, c - 19, c - 3, c - 10), (c + 3, c - 19, c + 11, c - 10)])
            bones = _shape(n, n, lines=[([(c - 22, c + 12), (c + 22, c + 30)], 5), ([(c + 22, c + 12), (c - 22, c + 30)], 5)])
            col = T.mix(col, _fill(n, n, "#1b1b1b"), np.clip(skull + bones, 0, 1) * inner)
            col = T.mix(col, _fill(n, n, "#ecebe4"), eyes * inner)
    elif kind == "flame":
        disc = _disc(xx, yy, c, c, n * 0.44)
        col = T.mix(col, _fill(n, n, "#efece4"), disc)
        fl = _shape(n, n, polys=[[(c, c - 30), (c + 14, c - 6), (c + 18, c + 12), (c + 10, c + 26), (c - 10, c + 26), (c - 18, c + 12),
                                  (c - 10, c - 4), (c - 6, c + 6)]])
        col = T.mix(col, _fill(n, n, "#1b1b1b"), fl)
        ring = _ring(xx, yy, c, c, n * 0.39, n * 0.08)
        slash = _seg(xx, yy, c - n * 0.28, c - n * 0.28, c + n * 0.28, c + n * 0.28, n * 0.08) * disc
        col = T.mix(col, _fill(n, n, "#b4231b"), np.clip(ring + slash, 0, 1))
    else:
        tri = _shape(n, n, polys=[[(c, m + 4), (n - m, n - m - 8), (m, n - m - 8)]])
        inner = _shape(n, n, polys=[[(c, m + 16), (n - m - 10, n - m - 14), (m + 10, n - m - 14)]])
        col = T.mix(col, _fill(n, n, "#1b1b1b"), tri)
        col = T.mix(col, _fill(n, n, "#e6b422"), inner)
        bar = _shape(n, n, polys=[[(c - 5, c - 20), (c + 5, c - 20), (c + 3, c + 16), (c - 3, c + 16)]],
                     ellipses=[(c - 5, c + 22, c + 5, c + 32)])
        col = T.mix(col, _fill(n, n, "#1b1b1b"), bar)
    # weathering: faded, scuffed corners, grime
    col = T.mix(col, _fill(n, n, "#cfc7b4"), T.smoothstep(0.4, 1.0, _noise(n, n, 1.6, seed)) * 0.25)
    col = T.mix(col, _fill(n, n, "#5a5348"), T.smoothstep(0.8, 0.9, _noise(n, n, 0.9, seed + 3)) * 0.7)
    return col


def _chart(n: int, seed: int) -> np.ndarray:
    """Round chart-recorder paper (the retort's time / temperature record): pale paper, concentric rings,
    curved time arcs, a red ink trace climbing to the cook temperature and holding, a hub and a black
    bezel. No numbers."""
    xx, yy = _grid(n)
    c = n / 2
    R = n * 0.48
    d = np.hypot(xx - c, yy - c)
    paper = _disc(xx, yy, c, c, R * 0.93)
    col = _fill(n, n, "#1b1a18")
    col = T.mix(col, _fill(n, n, "#e7e0cb") * (0.92 + 0.08 * _noise(n, n, 1.5, seed))[..., None], paper)
    lines = np.zeros_like(d)
    for k in range(1, 9):
        lines = np.maximum(lines, _ring(xx, yy, c, c, R * (0.2 + 0.09 * k), 1.0) * (0.5 if k % 2 else 0.9))
    ang = np.arctan2(yy - c, xx - c)
    for k in range(24):
        a0 = 2 * np.pi * k / 24
        # curved time arcs: the pen swings on an arc, so the hour lines bow
        bow = a0 + (d / R) * 0.5
        lines = np.maximum(lines, np.clip(1.0 - np.abs(np.angle(np.exp(1j * (ang - bow)))) * d / 1.2, 0, 1) * 0.6 * (d > R * 0.2))
    col = T.mix(col, _fill(n, n, "#7f8f9a"), lines * paper * 0.8)
    r = np.random.default_rng(seed)
    pts = []
    for i in range(140):
        a = -np.pi / 2 + 2 * np.pi * i / 140 * 0.85
        t = i / 140
        rad = 0.25 + 0.6 * min(1.0, t / 0.18) if t < 0.62 else 0.85 - 0.6 * min(1.0, (t - 0.62) / 0.12)
        rad = (rad + r.normal(0, 0.006)) * R
        pts.append((c + np.cos(a) * rad, c + np.sin(a) * rad))
    trace = _shape(n, n, lines=[(pts, 1.6)])
    col = T.mix(col, _fill(n, n, "#b0261f"), trace * paper)
    col = T.mix(col, _fill(n, n, "#4a463d"), _disc(xx, yy, c, c, R * 0.06))
    col = T.mix(col, _fill(n, n, "#262626"), _ring(xx, yy, c, c, R * 0.965, R * 0.07))
    col = col * (1.0 - 0.25 * T.smoothstep(0.5, 1.0, yy / n) * paper)[..., None]
    return col


def _mimic(w: int, h: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Pump-station control panel face: ANSI-grey enamel with a black mimic line diagram (well, pumps,
    clearwell, tower as plain symbols), blank white engraved tag strips and the screw heads."""
    xx, yy = _grid(w, h)
    col = _fill(w, h, "#9aa0a2") * (0.92 + 0.08 * _noise(w, h, 1.4, seed))[..., None]
    height = np.zeros((h, w), np.float32)
    # mimic: a header pipe and drops to three pump circles, a tank square and a tower
    lines = [([(30, 70), (470, 70)], 4), ([(30, 70), (30, 200)], 4), ([(470, 70), (470, 200)], 4)]
    for x in (130, 230, 330):
        lines.append(([(x, 70), (x, 140)], 4))
    m = _shape(w, h, lines=lines, ellipses=[], polys=[])
    rings = sum(_ring(xx, yy, x, 150, 14, 4) for x in (130, 230, 330))
    tank = _rect(xx, yy, 400, 160, 450, 220, 1.0) - _rect(xx, yy, 404, 164, 446, 216, 1.0)
    tower = _shape(w, h, polys=[[(15, 200), (45, 200), (40, 235), (20, 235)]])
    ink = np.clip(m + rings + tank + tower, 0, 1)
    col = T.mix(col, _fill(w, h, "#1c1c1c"), ink)
    # blank engraved tags under each lamp position
    for x in (130, 230, 330):
        for y in (185, 222):
            tag = _rect(xx, yy, x - 30, y, x + 30, y + 14, 1.0)
            col = T.mix(col, _fill(w, h, "#e8e6de"), tag)
            height += tag * 0.3
    for x in (100, 400):
        tag = _rect(xx, yy, x - 40, 12, x + 40, 30, 1.0)
        col = T.mix(col, _fill(w, h, "#e8e6de"), tag)
        height += tag * 0.3
    for sx, sy in ((8, 8), (w - 8, 8), (8, h - 8), (w - 8, h - 8)):
        s = _disc(xx, yy, sx, sy, 5)
        col = T.mix(col, _fill(w, h, "#6a6e70"), s)
        height += s * 0.5
    col = col * (1.0 - 0.3 * T.smoothstep(0.55, 0.9, _noise(w, h, 1.6, seed + 4)))[..., None]
    return col, height


def _nameplate(w: int, h: int, seed: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Cast builder's plate: a raised border, a raised blank cartouche, four rivets; paint in the recesses."""
    xx, yy = _grid(w, h)
    border = _rect(xx, yy, 4, 4, w - 4, h - 4, 1.0) - _rect(xx, yy, 12, 12, w - 12, h - 12, 1.0)
    cart = _rect(xx, yy, 40, 30, w - 40, h - 30, 3.0)
    lines = sum(_rect(xx, yy, 56, y, w - 56, y + 4, 1.0) for y in (48, 64, 80))
    riv = sum(_disc(xx, yy, x, y, 5) for x, y in ((22, 22), (w - 22, 22), (22, h - 22), (w - 22, h - 22)))
    raised = np.clip(border + cart * 0.7 + riv + lines * 0.4, 0, 1)
    base = _fill(w, h, "#2b2c2a") * (0.9 + 0.1 * _noise(w, h, 1.3, seed))[..., None]
    metal = _fill(w, h, "#a59a80") * (0.85 + 0.15 * _noise(w, h, 1.8, seed + 1))[..., None]
    col = T.mix(base, metal, np.clip(border + riv + lines * 0.8, 0, 1))
    col = T.mix(col, _fill(w, h, "#5a5b55"), cart * (1 - lines) * 0.6)
    return col, raised, np.clip(border + riv + lines, 0, 1) * 0.8


def _lcd(w: int, h: int, seed: int) -> np.ndarray:
    """Weighbridge readout: a dark green-grey LCD showing a row of dashes (no digits), unlit segment ghosts."""
    xx, yy = _grid(w, h)
    col = _fill(w, h, "#1b1d1a")
    win = _rect(xx, yy, 8, 8, w - 8, h - 8, 1.0)
    col = T.mix(col, _fill(w, h, "#5f6a58") * (0.9 + 0.1 * _noise(w, h, 1.5, seed))[..., None], win)
    for k in range(6):
        x0 = 22 + k * 37
        ghost = np.zeros_like(xx)
        for y in (16, 30, 44):
            ghost = np.maximum(ghost, _rect(xx, yy, x0 + 4, y - 1.5, x0 + 22, y + 1.5, 0.8))
        for x in (x0 + 2, x0 + 24):
            for y0, y1 in ((17, 29), (31, 43)):
                ghost = np.maximum(ghost, _rect(xx, yy, x - 1.5, y0, x + 1.5, y1, 0.8))
        col = T.mix(col, _fill(w, h, "#535d4d"), ghost * 0.8)
        dash = _rect(xx, yy, x0 + 4, 28, x0 + 22, 32, 0.8)
        col = T.mix(col, _fill(w, h, "#1d211b"), dash)
    return col


def _hazard(w: int, h: int, seed: int) -> np.ndarray:
    xx, yy = _grid(w, h)
    band = ((xx + yy) // 32).astype(int) % 2 == 0
    col = np.where(band[..., None], _fill(w, h, "#d8a91f"), _fill(w, h, "#1d1c19"))
    col = T.mix(col, _fill(w, h, "#7a7266"), T.smoothstep(0.7, 0.85, _noise(w, h, 0.9, seed)) * 0.8)
    return col


def _photo(w: int, h: int, seed: int, kind: int) -> np.ndarray:
    """A small framed photograph: a mat border round a b/w or sepia print of blurred shapes. kind 0: a
    platoon in three rows; 1: a portrait in a service cap; 2: a plane over a strip; 3: two men by a jeep;
    4: tents in a field; 5: a ship at sea. The frame itself is geometry."""
    xx, yy = _grid(w, h)
    r = np.random.default_rng(seed)
    sepia = kind in (0, 3, 4)
    pw, ph = w - 24, h - 24
    px, py = _grid(pw, ph)
    sky = 0.75 - 0.25 * (py / ph)
    img = np.full((ph, pw), 0.6, np.float32)
    if kind == 0:
        img = np.where(py < ph * 0.45, sky, 0.45)
        for row, (y, n, s) in enumerate(((ph * 0.42, 7, 0.9), (ph * 0.58, 8, 1.0), (ph * 0.74, 7, 1.1))):
            for i in range(n):
                x = pw * (0.08 + 0.84 * (i + 0.5 * (row % 2)) / n)
                head = _disc(px, py, x, y, 4.5 * s, 1.5)
                body = _rect(px, py, x - 7 * s, y + 3, x + 7 * s, y + 22 * s, 2.0)
                img = img * (1 - head) + 0.78 * head
                img = img * (1 - body) + (0.18 + 0.05 * r.random()) * body
    elif kind == 1:
        img = 0.55 + 0.2 * (px / pw)
        head = np.clip((1.0 - np.hypot((px - pw / 2) / 20, (py - ph * 0.42) / 25)) * 4, 0, 1)
        cap = _shape(pw, ph, polys=[[(pw / 2 - 26, ph * 0.28), (pw / 2 + 26, ph * 0.28), (pw / 2 + 18, ph * 0.18),
                                     (pw / 2 - 18, ph * 0.16)]])
        body = _shape(pw, ph, polys=[[(pw / 2 - 45, ph), (pw / 2 - 38, ph * 0.72), (pw / 2, ph * 0.64), (pw / 2 + 38, ph * 0.72),
                                      (pw / 2 + 45, ph)]])
        img = img * (1 - head) + 0.72 * head
        img = img * (1 - cap) + 0.15 * cap
        img = img * (1 - body) + 0.2 * body
    elif kind == 2:
        img = sky * np.ones_like(px)
        img = np.where(py > ph * 0.78, 0.4, img)
        plane = _shape(pw, ph, polys=[[(10, 50), (90, 46), (100, 52), (90, 56), (10, 54)],
                                      [(42, 52), (60, 52), (40, 80), (30, 80)], [(42, 48), (60, 48), (40, 22), (30, 22)],
                                      [(10, 50), (16, 38), (20, 50)]])
        img = img * (1 - plane) + 0.15 * plane
    elif kind == 3:
        img = np.where(py < ph * 0.5, sky, 0.5)
        jeep = _shape(pw, ph, polys=[[(18, 95), (18, 75), (40, 72), (52, 60), (60, 72), (90, 74), (92, 95)]],
                      ellipses=[(24, 88, 42, 106), (70, 88, 88, 106)])
        img = img * (1 - jeep) + 0.2 * jeep
        for x in (10, 98):
            head = _disc(px, py, x, 60, 5, 1.5)
            body = _rect(px, py, x - 7, 64, x + 7, 110, 2.0)
            img = img * (1 - head) + 0.75 * head
            img = img * (1 - body) + 0.22 * body
    elif kind == 4:
        img = np.where(py < ph * 0.4, sky, 0.52)
        for i in range(4):
            x = 12 + i * 26
            tent = _shape(pw, ph, polys=[[(x, 90 - i * 4), (x + 12, 62 - i * 4), (x + 24, 90 - i * 4)]])
            img = img * (1 - tent) + (0.3 + 0.04 * i) * tent
    else:
        img = np.where(py < ph * 0.55, sky, 0.35 + 0.05 * np.sin(px * 0.5 + py))
        ship = _shape(pw, ph, polys=[[(8, 70), (96, 70), (88, 80), (16, 80)], [(36, 70), (36, 54), (60, 54), (60, 70)],
                                     [(46, 54), (48, 34), (50, 54)]])
        img = img * (1 - ship) + 0.15 * ship
    img = T.blur(img, 1.1) + (_noise(pw, ph, 0.5, seed) - 0.5) * 0.12
    img = np.clip(img * (1 - 0.35 * np.hypot(px / pw - 0.5, py / ph - 0.5)), 0, 1)
    tone = T.gradient(img, [(0, "#1d1610"), (0.5, "#7d6347"), (1, "#e8dcc1")]) if sepia else \
        T.gradient(img, [(0, "#121212"), (0.5, "#6e6e6a"), (1, "#e4e2da")])
    col = _fill(w, h, "#e6dfcd") * (0.92 + 0.08 * _noise(w, h, 1.3, seed + 3))[..., None]
    col[12:12 + ph, 12:12 + pw] = tone
    col = T.mix(col, _fill(w, h, "#b6a983"), T.smoothstep(0.6, 0.95, _noise(w, h, 1.8, seed + 5)) * 0.35)
    return col


def _plaque(w: int, h: int, seed: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Walnut plaque, bevelled, with a brass plate: an engraved emblem ring and blank ruled lines."""
    xx, yy = _grid(w, h)
    grain = _resize(_noise(16, h, 1.0, seed), w, h) * 0.5 + 0.5 * _noise(w, h, 1.2, seed + 1)
    col = T.mix(_fill(w, h, "#3d2617"), _fill(w, h, "#6a4528"), grain)
    plate = _rect(xx, yy, 18, 22, w - 18, h - 22, 1.0)
    brass = _fill(w, h, "#bb9450") * (0.85 + 0.2 * _noise(w, h, 1.6, seed + 2))[..., None]
    col = T.mix(col, brass, plate)
    eng = _ring(xx, yy, w / 2, 52, 16, 3) + _disc(xx, yy, w / 2, 52, 6)
    for y in (84, 96, 108, 120):
        eng = eng + _rect(xx, yy, 30 + (y % 3) * 4, y, w - 30 - (y % 5) * 3, y + 2.5, 0.8)
    eng = np.clip(eng, 0, 1) * plate
    col = T.mix(col, _fill(w, h, "#3a2a14"), eng)
    height = plate * 0.3 - eng * 0.2 + (1 - _rect(xx, yy, 6, 6, w - 6, h - 6, 6.0)) * -0.3
    return col, height, plate * 0.9


def _certificate(w: int, h: int, seed: int) -> np.ndarray:
    xx, yy = _grid(w, h)
    col = _fill(w, h, "#e9e2cc") * (0.93 + 0.07 * _noise(w, h, 1.3, seed))[..., None]
    border = _rect(xx, yy, 8, 8, w - 8, h - 8, 1.0) - _rect(xx, yy, 12, 12, w - 12, h - 12, 1.0)
    col = T.mix(col, _fill(w, h, "#6d5a32"), border)
    r = np.random.default_rng(seed)
    strokes = [(_scribble(r, 30, 34, w - 30, 2.5), 2.2)]
    for y in (60, 72, 84, 96):
        strokes.append((_scribble(r, 24, y, w - 24 - r.uniform(0, 20), 1.0), 1.0))
    ink = _shape(w, h, lines=strokes)
    col = T.mix(col, _fill(w, h, "#2c2a26"), ink * 0.85)
    seal = _disc(xx, yy, w * 0.7, 130, 13)
    col = T.mix(col, _fill(w, h, "#b4923f"), seal)
    col = T.mix(col, _fill(w, h, "#8a1f1f"), _shape(w, h, polys=[[(w * 0.7 - 8, 138), (w * 0.7 - 2, 138), (w * 0.7 - 10, 156)],
                                                                [(w * 0.7 + 2, 138), (w * 0.7 + 8, 138), (w * 0.7 + 10, 156)]]))
    return col


def _flag(w: int, h: int, seed: int, kind: str) -> np.ndarray:
    """Plain generic flags. a: the post flag - navy field, gold border, a white disc with a gold chevron.
    b: a maroon / white / maroon banded flag with a thin black centre line. Sun-faded, dusty, the fly end
    darker."""
    xx, yy = _grid(w, h)
    if kind == "a":
        col = _fill(w, h, "#22304e")
        edge = 1.0 - _rect(xx, yy, 10, 10, w - 10, h - 10, 1.0)
        col = T.mix(col, _fill(w, h, "#c4a243"), edge)
        disc = _disc(xx, yy, w / 2, h / 2, h * 0.28)
        col = T.mix(col, _fill(w, h, "#e6e1d2"), disc)
        chev = _shape(w, h, lines=[([(w / 2 - 26, h / 2 + 16), (w / 2, h / 2 - 12), (w / 2 + 26, h / 2 + 16)], 9)])
        col = T.mix(col, _fill(w, h, "#c4a243"), chev * disc)
    else:
        band = (yy > h / 3) & (yy < 2 * h / 3)
        col = np.where(band[..., None], _fill(w, h, "#e2ddd0"), _fill(w, h, "#6e2128"))
        col = T.mix(col, _fill(w, h, "#1d1b19"), _rect(xx, yy, -5, h / 2 - 3, w + 5, h / 2 + 3, 1.0))
    weave = 0.95 + 0.05 * np.sin(xx * 2.1) * np.sin(yy * 2.3)
    fade = _noise(w, h, 1.5, seed)
    col = T.mix(col * weave[..., None], _fill(w, h, "#cbc3b2"), T.smoothstep(0.35, 0.95, fade) * 0.3)
    col = col * (1.0 - 0.25 * T.smoothstep(0.75, 1.0, xx / w))[..., None]
    return col


def _sunburst(n: int, seed: int) -> np.ndarray:
    """Guitar-top sunburst: amber centre to near-black edge (radial), with spruce grain lines."""
    xx, yy = _grid(n)
    d = np.hypot(xx - n / 2, (yy - n / 2) * 0.8) / (n / 2)
    col = T.gradient(np.clip(d, 0, 1), [(0, "#d39a45"), (0.55, "#b0662a"), (0.8, "#4a2412"), (1, "#1c0f08")])
    grain = _resize(_noise(n, 8, 1.0, seed), n, n)
    col = col * (0.9 + 0.12 * grain)[..., None]
    return col


def _ribbon(w: int, h: int, seed: int, k: int) -> np.ndarray:
    """Medal ribbon bars: symmetric vertical stripes in faded colours (generic, no real award)."""
    xx, yy = _grid(w, h)
    pal = [["#6e2128", "#e2ddd0", "#2b3d6b"], ["#2f5a3a", "#d9b44a", "#2f5a3a"], ["#3d4e86", "#e2ddd0", "#8a1f1f"],
           ["#d9b44a", "#2b3d6b", "#e2ddd0"]][k % 4]
    u = np.abs(xx - w / 2) / (w / 2)
    idx = np.clip((u * 3).astype(int), 0, 2)
    col = np.zeros((h, w, 3), np.float32)
    for i, c in enumerate(pal):
        col = np.where((idx == i)[..., None], _fill(w, h, c), col)
    col = col * (0.88 + 0.12 * np.sin(yy * 1.7))[..., None]
    return col * (0.9 + 0.1 * _noise(w, h, 1.2, seed))[..., None]


def _velvet(w: int, h: int, seed: int, c: str) -> np.ndarray:
    return _fill(w, h, c) * (0.75 + 0.3 * _noise(w, h, 0.7, seed))[..., None]


def _price_tag(w: int, h: int, seed: int) -> np.ndarray:
    """Pawn tag: manila card, a punched eyelet, two illegible pencil strokes."""
    xx, yy = _grid(w, h)
    col = _fill(w, h, "#d6c08a") * (0.92 + 0.08 * _noise(w, h, 1.3, seed))[..., None]
    col = T.mix(col, _fill(w, h, "#a08a52"), _ring(xx, yy, 14, h / 2, 6, 3))
    col = T.mix(col, _fill(w, h, "#2a2620"), _disc(xx, yy, 14, h / 2, 3.5))
    r = np.random.default_rng(seed)
    ink = _shape(w, h, lines=[(_scribble(r, 30, 22, w - 14, 3.0), 2.0), (_scribble(r, 30, 42, w - 40, 2.5), 2.0)])
    return T.mix(col, _fill(w, h, "#2d2b2a"), ink * 0.8)


def _ammo(w: int, h: int, seed: int, k: int) -> np.ndarray:
    """Cartridge boxes, front face: a coloured box with a white panel showing cartridge silhouettes (no
    words, no brand) and a colour band."""
    xx, yy = _grid(w, h)
    base = ["#a32a1f", "#2c4e8a", "#d0a12b", "#3d6a3a"][k % 4]
    col = _fill(w, h, base) * (0.9 + 0.1 * _noise(w, h, 1.3, seed))[..., None]
    panel = _rect(xx, yy, 14, 14, w * 0.62, h - 14, 1.0)
    col = T.mix(col, _fill(w, h, "#e9e4d6"), panel)
    n = 3 + k % 2
    for i in range(n):
        x0 = 24 + i * (w * 0.52 - 20) / n
        case = _rect(xx, yy, x0, 30, x0 + 10, 66, 1.0)
        bullet = _shape(w, h, polys=[[(x0, 30), (x0 + 10, 30), (x0 + 8, 22), (x0 + 5, 17), (x0 + 2, 22)]])
        col = T.mix(col, _fill(w, h, "#b8913e"), case)
        col = T.mix(col, _fill(w, h, "#8a5a32"), bullet)
    stripe = _rect(xx, yy, w * 0.68, 20, w - 14, 36, 1.0)
    col = T.mix(col, _fill(w, h, "#efe9da"), stripe)
    col = T.mix(col, _fill(w, h, "#1c1c1a"), _rect(xx, yy, w * 0.68, 46, w - 14, 76, 1.0) * 0.85)
    col = T.mix(col, _fill(w, h, "#7d766a"), T.smoothstep(0.78, 0.9, _noise(w, h, 0.9, seed + 2)) * 0.6)
    return col


def _ammo_end(w: int, h: int, seed: int) -> np.ndarray:
    xx, yy = _grid(w, h)
    col = _fill(w, h, "#b3a68a") * (0.9 + 0.1 * _noise(w, h, 1.2, seed))[..., None]
    col = T.mix(col, _fill(w, h, "#1c1c1a"), _rect(xx, yy, 10, h * 0.4, w - 10, h * 0.6, 1.0))
    return col


def _slime(w: int, h: int, seed: int) -> np.ndarray:
    """Dried fish-gurry stain on stainless: dull khaki blotches with darker rims."""
    xx, yy = _grid(w, h)
    n = _noise(w, h, 1.7, seed)
    col = T.mix(_fill(w, h, "#8b8a83"), _fill(w, h, "#6a6347"), T.smoothstep(0.45, 0.6, n))
    return T.mix(col, _fill(w, h, "#3d382a"), np.clip(1.0 - np.abs(n - 0.55) / 0.02, 0, 1) * 0.6)


def _painting(n: int, seed: int) -> np.ndarray:
    """A small landscape print: blue ridges over a lake, a pine shore, in a cream mat."""
    xx, yy = _grid(n)
    col = _fill(n, n, "#e1d8c2")
    pw = n - 40
    px, py = _grid(pw)
    img = T.gradient(py / pw, [(0, "#9fb4c4"), (0.45, "#d8c9a8"), (1, "#d8c9a8")])
    for k, (base, c) in enumerate(((0.4, "#5f7488"), (0.48, "#3f5266"))):
        ridge = base * pw - (np.sin(px * 0.05 + k * 2) * 10 + np.sin(px * 0.13 + k) * 5)
        img = np.where((py > ridge)[..., None], _fill(pw, pw, c), img)
    lake = py > 0.62 * pw
    img = np.where(lake[..., None], T.mix(_fill(pw, pw, "#6c8aa0"), _fill(pw, pw, "#a9bcc6"), np.sin(py * 0.6) * 0.5 + 0.5), img)
    pines = np.zeros((pw, pw), np.float32)
    r = np.random.default_rng(seed)
    for i in range(10):
        x = r.uniform(0, pw)
        hh = r.uniform(30, 60)
        pines = np.maximum(pines, _shape(pw, pw, polys=[[(x - hh * 0.2, 0.66 * pw), (x, 0.66 * pw - hh), (x + hh * 0.2, 0.66 * pw)]]))
    img = T.mix(img, _fill(pw, pw, "#25352a"), pines)
    col[20:20 + pw, 20:20 + pw] = img * (0.9 + 0.1 * _noise(pw, pw, 1.0, seed))[..., None]
    return col


def _site_plan(n: int, seed: int) -> np.ndarray:
    """Quarry blast plan pinned by the scale: blueprint-white paper, contour lines of the pit, a grid of
    drill-hole dots in rows, a pencilled boundary. No words or numbers."""
    xx, yy = _grid(n)
    col = _fill(n, n, "#e4e2d8") * (0.93 + 0.07 * _noise(n, n, 1.3, seed))[..., None]
    f = T.blur(_noise(n, n, 2.4, seed + 1), 4.0)
    cont = np.clip(1.0 - np.abs(((f * 12) % 1.0) - 0.5) * 9.0, 0, 1) * 0.8
    col = T.mix(col, _fill(n, n, "#7d6a4f"), cont * 0.7)
    for row in range(5):
        for i in range(8):
            cx, cy = 50 + i * 22 + (row % 2) * 11, 70 + row * 22
            col = T.mix(col, _fill(n, n, "#1e2a46"), _disc(xx, yy, cx, cy, 3.2))
    r = np.random.default_rng(seed)
    bnd = _shape(n, n, lines=[([(30 + r.uniform(-3, 3), 50), (226, 48 + r.uniform(-3, 3)), (228, 180), (32, 182), (30, 50)], 1.6)])
    col = T.mix(col, _fill(n, n, "#3b3b3b"), bnd * 0.7)
    col = T.mix(col, _fill(n, n, "#b62b22"), _shape(n, n, lines=[([(60, 210), (200, 205)], 3)]))
    return col


def _clip_sheet(n: int, seed: int) -> np.ndarray:
    """A ruled log sheet on a clipboard: columns, illegible pencil strokes in most rows."""
    xx, yy = _grid(n)
    col = _fill(n, n, "#ebe6d6") * (0.94 + 0.06 * _noise(n, n, 1.3, seed))[..., None]
    for y in range(40, n - 10, 14):
        col = T.mix(col, _fill(n, n, "#9db0c8"), _rect(xx, yy, 10, y, n - 10, y + 1.2, 0.6))
    for x in (60, 140, 190):
        col = T.mix(col, _fill(n, n, "#c27a74"), _rect(xx, yy, x, 30, x + 1.2, n - 10, 0.6))
    r = np.random.default_rng(seed)
    strokes = []
    for k, y in enumerate(range(40, n - 40, 14)):
        if r.random() < 0.8:
            for x0, x1 in ((14, 56), (64, 136), (144, 186), (194, n - 14)):
                if r.random() < 0.85:
                    strokes.append((_scribble(r, x0, y - 4, x0 + (x1 - x0) * r.uniform(0.5, 0.95), 1.6), 1.2))
    col = T.mix(col, _fill(n, n, "#3b3a38"), _shape(n, n, lines=strokes) * 0.75)
    return col


def _emblem(n: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Generic post emblem: a bronze disc, a laurel ring of leaves, crossed rifles over a plain shield."""
    xx, yy = _grid(n)
    c = n / 2
    col = _fill(n, n, "#2a2723")
    disc = _disc(xx, yy, c, c, n * 0.46)
    bronze = _fill(n, n, "#9b7a43") * (0.85 + 0.2 * _noise(n, n, 1.6, seed))[..., None]
    col = T.mix(col, bronze, disc)
    leaves = np.zeros_like(xx)
    for i in range(22):
        a = np.pi * 0.15 + i / 22 * np.pi * 1.7
        lx, ly = c + np.cos(a + np.pi / 2) * n * 0.36, c + np.sin(a + np.pi / 2) * n * 0.36
        leaves = np.maximum(leaves, np.clip(1.0 - np.hypot((xx - lx) / 9, (yy - ly) / 5), 0, 1) * 2)
    shield = _shape(n, n, polys=[[(c - 40, c - 50), (c + 40, c - 50), (c + 40, c + 5), (c, c + 50), (c - 40, c + 5)]])
    rifles = _shape(n, n, lines=[([(c - 70, c + 60), (c + 70, c - 60)], 8), ([(c + 70, c + 60), (c - 70, c - 60)], 8)])
    relief = np.clip(leaves, 0, 1) * 0.6 + shield * 0.8 + rifles * 0.5
    col = T.mix(col, _fill(n, n, "#5a4322"), T.blur(np.clip(relief, 0, 1), 2.0) * 0.7 * disc)
    col = T.mix(col, _fill(n, n, "#e0bf7a"), np.clip(relief, 0, 1) * 0.85 * disc)
    col = T.mix(col, _fill(n, n, "#2b2b2b"), _ring(xx, yy, c, c, n * 0.46, 4))
    return col, relief * disc + disc * 0.3


@texture("town4_print", size=1024, seed=9701)
def town4_print(size: int, seed: int, out) -> None:
    """Atlas of the cannery / pump house / quarry / pawn shop / VFW graphics (rects: PRINT_RECTS). No text."""
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
    cc, ch = _can_end(128, seed + 4)
    put("can_end", cc, ch * 0.6, 0.35, 0.85)
    for i, k in enumerate(("explosive", "flame", "gas", "warn")):
        put(f"pict_{k}", _placard(128, seed + 10 + i, k), None, 0.6)
    put("chart", _chart(256, seed + 20), None, 0.8)
    mc, mh = _mimic(512, 256, seed + 21)
    put("mimic", mc, mh, 0.45)
    nc, nh, nm = _nameplate(256, 128, seed + 22)
    put("nameplate", nc, nh, 0.5, nm)
    put("lcd", _lcd(256, 64, seed + 23), None, 0.25)
    put("hazard", _hazard(256, 64, seed + 24), None, 0.6)
    for k in range(6):
        put(f"photo{k}", _photo(128, 160, seed + 30 + k, k), None, 0.35)
    pc, ph, pm = _plaque(128, 160, seed + 40)
    put("plaque", pc, ph, 0.45, pm)
    put("certificate", _certificate(128, 160, seed + 41), None, 0.8)
    put("flag_a", _flag(256, 160, seed + 42, "a"), _noise(256, 160, 0.8, seed + 43) * 0.3, 0.92)
    put("flag_b", _flag(256, 160, seed + 44, "b"), _noise(256, 160, 0.8, seed + 45) * 0.3, 0.92)
    put("sunburst", _sunburst(160, seed + 46), None, 0.25)
    for k in range(4):
        put(f"ribbon{k}", _ribbon(64, 96, seed + 50 + k, k), None, 0.8)
    put("velvet", _velvet(96, 96, seed + 55, "#1f2d55"), _noise(96, 96, 0.7, seed + 56) * 0.2, 0.95)
    put("felt_black", _velvet(128, 64, seed + 57, "#1e1d1c"), None, 0.95)
    put("price_tag", _price_tag(128, 64, seed + 58), None, 0.85)
    put("velvet_red", _velvet(96, 64, seed + 59, "#5a1520"), None, 0.95)
    for k in range(4):
        put(f"ammo{k}", _ammo(192, 96, seed + 60 + k, k), None, 0.6)
    put("ammo_end", _ammo_end(128, 96, seed + 64), None, 0.7)
    put("fish_slime", _slime(128, 96, seed + 65), None, 0.55, 0.5)
    put("painting", _painting(256, seed + 70), None, 0.6)
    put("site_plan", _site_plan(256, seed + 71), None, 0.85)
    put("clip_sheet", _clip_sheet(256, seed + 72), None, 0.85)
    ec, eh = _emblem(256, seed + 73)
    put("emblem", ec, eh, 0.4, np.clip(eh, 0, 1) * 0.7)
    T.save_pbr_set(out, np.clip(col, 0, 1), np.clip(height, 0, 1), np.clip(rough, 0, 1), metal=np.clip(metal, 0, 1),
                   normal_strength=1.5)


# ------------------------------------------------------------------------------------------------
# stacked unlabelled cans (pallet loads, retort baskets): tileable side and top
# ------------------------------------------------------------------------------------------------

# One tile = CAN_TILE_X cans across and CAN_TILE_TIERS tiers up (mirrored in props_town4.py CAN_*).
CAN_TILE_X = 8
CAN_TILE_TIERS = 4


@texture("town4_can_side", size=512, seed=9711)
def town4_can_side(size: int, seed: int, out) -> None:
    """Side of a stack of bright unlabelled tall cans (8 across, 4 tiers per tile): each can a shaded
    cylinder with its double seams top and bottom, dark gaps where the rounds meet, a brown tier sheet
    under every tier, odd cans dulled or spotted with rust."""
    xx, yy = _grid(size)
    cw = size / CAN_TILE_X
    th = size / CAN_TILE_TIERS
    sheet = th * 0.035
    u = (xx % cw) / cw  # 0..1 across a can
    t = (yy % th)  # 0..th down a tier (y down: 0 = top of the tier)
    ci = (xx // cw).astype(int) + 17 * (yy // th).astype(int)
    r = np.random.default_rng(seed)
    dull = r.uniform(0.82, 1.0, CAN_TILE_X * 17 + CAN_TILE_X * CAN_TILE_TIERS * 2)[ci % (CAN_TILE_X * 17)]
    cosv = np.sqrt(np.clip(1.0 - (2 * u - 1) ** 2, 0, 1))
    shade = 0.35 + 0.65 * cosv + 0.35 * np.exp(-((u - 0.32) / 0.07) ** 2)
    can_h = th - sheet
    seam = np.exp(-((t - 0.03 * can_h) / (0.02 * can_h)) ** 2) + np.exp(-((t - 0.97 * can_h) / (0.02 * can_h)) ** 2)
    bead = 0.5 + 0.5 * np.cos(t / can_h * np.pi * 14)
    body = np.clip(shade * (0.92 + 0.06 * bead) + seam * 0.35, 0, 1.4)
    col = _fill(size, size, "#c7c8c2") * (body * dull)[..., None]
    in_sheet = t > can_h
    col = np.where(in_sheet[..., None], _fill(size, size, "#6f5a3c") * (0.85 + 0.15 * _noise(size, size, 1.2, seed))[..., None], col)
    rust = T.smoothstep(0.78, 0.9, T.spectral(size, 1.6, seed + 1)) * (~in_sheet)
    col = T.mix(col, _fill(size, size, "#6b4426"), rust * 0.8)
    height = np.where(in_sheet, 0.0, cosv * 0.7 + seam * 0.3)
    rough = np.where(in_sheet, 0.9, np.clip(0.28 + 0.4 * rust + 0.1 * (1 - dull), 0, 1))
    metal = np.where(in_sheet, 0.0, 0.9 * (1 - rust))
    T.save_pbr_set(out, np.clip(col, 0, 1), T.normalize(height), rough, metal=metal, normal_strength=3.0)


@texture("town4_can_top", size=512, seed=9712)
def town4_can_top(size: int, seed: int, out) -> None:
    """Tops of a tier of cans in square stow (8 x 8 per tile): seamed ends with expansion rings, dark gaps
    between the rounds."""
    xx, yy = _grid(size)
    cw = size / CAN_TILE_X
    lx, ly = (xx % cw) - cw / 2, (yy % cw) - cw / 2
    d = np.hypot(lx, ly) / (cw / 2)
    h = T.smoothstep(0.86, 0.92, d) * T.smoothstep(1.0, 0.95, d)
    h -= T.smoothstep(0.8, 0.86, d) * T.smoothstep(0.92, 0.86, d) * 0.6
    for r0 in (0.35, 0.55, 0.7):
        h += np.clip(1.0 - np.abs(d - r0) / 0.04, 0, 1) * 0.35
    gap = d > 0.99
    col = _fill(size, size, "#c4c5bf") * (0.7 + 0.35 * np.clip(h + 0.4, 0, 1))[..., None]
    col = np.where(gap[..., None], _fill(size, size, "#1c1b18"), col)
    rust = T.smoothstep(0.8, 0.92, T.spectral(size, 1.6, seed)) * (~gap)
    col = T.mix(col, _fill(size, size, "#6b4426"), rust * 0.7)
    height = np.where(gap, -0.5, h)
    rough = np.where(gap, 0.9, 0.3 + 0.4 * rust)
    metal = np.where(gap, 0.0, 0.9 * (1 - rust))
    T.save_pbr_set(out, np.clip(col, 0, 1), T.normalize(height), rough, metal=metal, normal_strength=2.0)
