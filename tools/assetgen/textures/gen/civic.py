"""Civic props of Pell's Crossing (church, tavern, post office, grange hall): church woods, bar mahogany,
felt, headstone granite and marble, wrought iron, bell bronze, tarnished brass, army wool, and three
atlases with the town's printed, painted and carved graphics.

Everything is procedural (numpy). Lettering is rendered with the repo's open-licensed fonts
(game/assets/fonts, see THIRD_PARTY.md) through Pillow/FreeType - the same faces the game uses for its
printed documents - and then weathered here. Tileables use near-neutral bases where materials tint
them (felt, wool, marble), because a tint can only darken.

Atlases (pixel rects, y down, are a contract with blender/generators/props_civic.py ATLAS):
  civic_print     1024 px: dartboard, jukebox panels, bottle / tap labels, hymn board cards, relief-crate
                  and mailbox stencils, the Cordon notice, signs (post office, church letter board, grange
                  banner), altar frontal, piano fallboard, trophy plaques, scale dial, hymnal, pool balls.
  civic_engrave   1024 px, 4 x 2 portrait cells of 256 x 512: carved headstone faces (granite speckle,
                  V-cut lettering, lichen, rain streaks). Tinted per material (granite / marble).
  civic_po_boxes  1024 px over a 1.0 x 1.5 m face (drawn 1:1.5 so doors read square): 8 x 12 brass box
                  doors numbered 101-196 with glazed windows, combination dials and number plates.
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

# PO box doors drawn pried open (empty recess); props_civic.py models their leaves hanging open.
PRIED_DOORS = (7, 32, 54, 62, 70, 71, 95)

# Atlas rects (x0, y0, x1, y1) in pixels of the 1024 px civic_print texture. Mirrored in
# blender/generators/props_civic.py (ATLAS) - change both together.
PRINT_RECTS: dict[str, tuple[int, int, int, int]] = {
    "dart": (0, 0, 256, 256),
    "juke_cards": (256, 0, 512, 128),
    "juke_grille": (256, 128, 512, 256),
    "labels": (512, 0, 768, 256),        # 8 bottle labels of 256 x 32, top to bottom
    "taps": (768, 0, 1024, 128),         # 4 tap-handle labels of 64 x 128, left to right
    "hymn_header": (768, 128, 1024, 160),
    "hymn_cards": (768, 160, 1024, 256),  # 3 number cards of 256 x 32
    "relief_side": (0, 256, 256, 384),
    "relief_end": (0, 384, 256, 512),
    "mail_front": (256, 256, 384, 512),
    "mail_side": (384, 256, 512, 512),
    "notice": (512, 256, 640, 432),
    "alms": (512, 432, 640, 464),
    "closed_sign": (512, 464, 640, 512),
    "po_sign": (640, 256, 1024, 320),
    "church_sign": (640, 320, 1024, 512),
    "altar_frontal": (0, 512, 256, 640),
    "fallboard": (256, 512, 512, 544),
    "plaques": (256, 544, 512, 640),      # 3 brass plaques of 256 x 32
    "scale_dial": (512, 512, 640, 640),
    "hymnal": (640, 512, 704, 608),
    "hymnal_spine": (704, 512, 720, 608),
    "sort_labels": (720, 512, 1024, 640),  # 8 route labels of 152 x 32 (2 columns x 4 rows)
    "banner": (0, 640, 512, 768),
    "juke_arch": (512, 640, 768, 768),
    "photo": (768, 640, 896, 768),
    "keg_stamp": (896, 640, 1024, 768),
    "pool_balls": (0, 768, 512, 800),      # 16 balls of 32 x 32
    "relief_lid": (0, 800, 256, 928),
    "cot_tag": (256, 800, 384, 864),
    "felt_board": (384, 800, 512, 1024),
    "ledger": (512, 768, 768, 1024),
    "wood_plain": (768, 768, 1024, 1024),
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


def _font(name: str, px: int, var: str | None = None) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONTS / name), max(4, int(px)))
    if var:
        f.set_variation_by_name(var)
    return f


def _text(w: int, h: int, items) -> np.ndarray:
    """Anti-aliased text mask (h, w) in [0, 1]. items: (x, y, text, font[, anchor]) in pixels."""
    im = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(im)
    for it in items:
        x, y, s, f = it[:4]
        anchor = it[4] if len(it) > 4 else "mm"
        d.text((x, y), s, font=f, fill=255, anchor=anchor)
    return np.asarray(im, np.float32) / 255.0


def _fit(name: str, text: str, max_w: float, px: int, var: str | None = None) -> ImageFont.FreeTypeFont:
    """Largest font size <= px whose rendering of text fits max_w pixels."""
    while px > 6:
        f = _font(name, px, var)
        x0, _, x1, _ = f.getbbox(text)
        if x1 - x0 <= max_w:
            return f
        px -= 1
    return _font(name, px, var)


def _rect(xx, yy, x0, y0, x1, y1, soft: float = 1.0) -> np.ndarray:
    m = np.minimum(np.minimum(xx - x0, x1 - xx), np.minimum(yy - y0, y1 - yy))
    return np.clip(m / soft + 0.5, 0, 1)


def _disc(xx, yy, cx, cy, r, soft: float = 1.0) -> np.ndarray:
    return np.clip((r - np.hypot(xx - cx, yy - cy)) / soft + 0.5, 0, 1)


def _noise(w: int, h: int, beta: float, seed: int) -> np.ndarray:
    """Non-tiling helper noise for atlas cells (crop of a tileable field)."""
    s = 1 << int(np.ceil(np.log2(max(w, h, 8))))
    return T.spectral(s, beta, seed)[:h, :w]


def _stamp(canvas: np.ndarray, cx: float, cy: float, half: float, fn) -> None:
    """max-blends fn(dx, dy) (offsets from the centre, pixels) into a wrapped window of the canvas."""
    s = canvas.shape[0]
    n = int(np.ceil(half)) + 2
    xs = np.arange(int(np.floor(cx)) - n, int(np.floor(cx)) + n + 1)
    ys = np.arange(int(np.floor(cy)) - n, int(np.floor(cy)) + n + 1)
    dx, dy = np.meshgrid(xs + 0.5 - cx, ys + 0.5 - cy)
    ix, iy = np.ix_(ys % s, xs % s)
    canvas[ix, iy] = np.maximum(canvas[ix, iy], fn(dx.astype(np.float32), dy.astype(np.float32)))


def _scratches(size: int, seed: int, count: int, length, width: float = 0.7, angle: float | None = None,
               spread: float = 3.14) -> np.ndarray:
    """Tileable fine scratch lines."""
    r = T.rng(seed)
    out = np.zeros((size, size), np.float32)
    for _ in range(count):
        x, y = r.uniform(0, size), r.uniform(0, size)
        a = (angle if angle is not None else 0.0) + r.uniform(-spread, spread)
        ln = r.uniform(*length)
        ex, ey = np.cos(a) * ln, np.sin(a) * ln
        wd = width * r.uniform(0.6, 1.3)
        amp = r.uniform(0.3, 1.0)

        def seg(dx, dy, ex=ex, ey=ey, wd=wd, amp=amp):
            t = np.clip((dx * ex + dy * ey) / max(ex * ex + ey * ey, 1e-6), 0, 1)
            return np.clip(wd - np.hypot(dx - t * ex, dy - t * ey) + 0.5, 0, 1) * amp

        _stamp(out, x, y, ln + wd + 2, seg)
    return out


def _paste(dst: np.ndarray, rect, src: np.ndarray) -> None:
    x0, y0, x1, y1 = rect
    dst[y0:y1, x0:x1] = src


def _wear_mask(w: int, h: int, seed: int, amount: float) -> np.ndarray:
    """Patchy wear / flaking mask for printed and painted graphics."""
    a = _noise(w, h, 1.2, seed)
    b = _noise(w, h, 0.4, seed + 1)
    return np.clip(T.smoothstep(1.0 - amount, 1.0 - amount * 0.5, 0.65 * a + 0.35 * b), 0, 1)


# ------------------------------------------------------------------------------------------------
# woods
# ------------------------------------------------------------------------------------------------


def _straight_grain(size: int, seed: int, lines: int, wave: float):
    """Straight, tight grain along U (image x), tileable: fine growth lines + slow waviness."""
    xx, yy = _grid(size)
    w1 = T.spectral(size, 2.6, seed, anisotropy=(1.0, 6.0))
    w2 = T.spectral(size, 1.4, seed + 1, anisotropy=(1.0, 30.0))
    v = yy / size * lines + (w1 - 0.5) * wave + (w2 - 0.5) * 0.6
    ring = v - np.floor(v)
    late = T.smoothstep(0.55, 0.9, ring) * (1.0 - T.smoothstep(0.92, 1.0, ring))
    return late, w2


@texture("civic_oak_qsawn", size=1024, seed=9101)
def civic_oak_qsawn(size: int, seed: int, out) -> None:
    """Quarter-sawn white oak, varnished honey-amber (church woodwork, pews, pulpit, organ, cases): tight,
    dead-straight grain along U, the silvery medullary-ray 'flake' figure crossing it in ribbons, open
    pores, amber varnish pooled dark in the pores. 1 tile ~ 1 m."""
    r = T.rng(seed)
    late, streak = _straight_grain(size, seed, 150, 0.6)
    pore = T.spectral(size, 0.45, seed + 4, anisotropy=(1.0, 40.0))
    pore_m = T.smoothstep(0.62, 0.8, pore)
    broad = T.spectral(size, 2.8, seed + 5, anisotropy=(1.0, 3.0))
    tone = np.clip(0.4 * late + 0.35 * streak + 0.25 * broad, 0, 1)
    col = T.gradient(T.normalize(tone), [(0.0, "#a8733a"), (0.45, "#946232"), (0.8, "#7a4f27"), (1.0, "#5f3c1d")])
    # ray flake: lighter, slightly lustrous ribbons and flecks lying a few degrees off the grain, in
    # drifting bands (the log's rays come and go across a board)
    flake = np.zeros((size, size), np.float32)
    for _ in range(520):
        cx, cy = r.uniform(0, size), r.uniform(0, size)
        ln, wd = r.uniform(8, 50), r.uniform(2.0, 7.5)
        ang = r.uniform(-0.3, 0.3)
        amp = r.uniform(0.35, 1.0)

        def blob(dx, dy, ln=ln, wd=wd, ang=ang, amp=amp):
            u = dx * np.cos(ang) + dy * np.sin(ang)
            v = -dx * np.sin(ang) + dy * np.cos(ang)
            return np.clip(1.0 - (u / ln) ** 2 - (v / wd) ** 2, 0, 1) ** 0.7 * amp

        _stamp(flake, cx, cy, ln + 2, blob)
    band = T.spectral(size, 2.2, seed + 6, anisotropy=(4.0, 1.0))
    flake *= T.smoothstep(0.35, 0.7, band) * (0.55 + 0.45 * T.spectral(size, 0.8, seed + 7))
    col = T.mix(col, _fill(size, size, "#d1a66c"), flake * 0.7)
    col *= (1.0 - 0.35 * pore_m)[..., None]
    height = T.normalize(0.45 * (1 - late) + 0.25 * flake - 0.6 * pore_m)
    rough = np.clip(0.36 + 0.05 * (streak - 0.5) + 0.25 * pore_m - 0.14 * flake, 0, 1)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=1.3)


@texture("civic_mahogany", size=1024, seed=9111)
def civic_mahogany(size: int, seed: int, out) -> None:
    """Varnished mahogany bar wood: interlocked ribbon-stripe figure along U, deep red-brown, glossy, with
    faint glass rings and fine scratches in the finish."""
    r = T.rng(seed)
    late, streak = _straight_grain(size, seed, 90, 1.2)
    xx, yy = _grid(size)
    ribbon = 0.5 + 0.5 * np.sin(yy / size * 2 * np.pi * 11 + (T.spectral(size, 2.6, seed + 2, anisotropy=(1.0, 4.0)) - 0.5) * 4.0)
    ribbon = T.smoothstep(0.2, 0.8, ribbon)
    broad = T.spectral(size, 2.6, seed + 3)
    tone = np.clip(0.35 * late + 0.25 * streak + 0.25 * ribbon + 0.15 * broad, 0, 1)
    col = T.gradient(T.normalize(tone), [(0.0, "#7a3a22"), (0.45, "#64301c"), (0.8, "#4c2415"), (1.0, "#36190e")])
    rings = np.zeros((size, size), np.float32)
    for _ in range(18):
        cx, cy, rad = r.uniform(0, size), r.uniform(0, size), r.uniform(14, 30)
        amp = r.uniform(0.3, 0.8)
        _stamp(rings, cx, cy, rad + 3, lambda dx, dy, rad=rad, amp=amp: np.clip(1.6 - np.abs(np.hypot(dx, dy) - rad), 0, 1) * amp)
    scr = _scratches(size, seed + 4, 160, (8, 60), width=0.55)
    col = T.mix(col, _fill(size, size, "#a9705a"), np.clip(rings * 0.35 + scr * 0.3, 0, 1))
    height = T.normalize(0.4 * (1 - late) + 0.2 * ribbon - 0.4 * scr - 0.2 * rings)
    rough = np.clip(0.2 + 0.05 * streak + 0.3 * scr + 0.2 * rings, 0, 1)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=0.9)


# ------------------------------------------------------------------------------------------------
# soft goods
# ------------------------------------------------------------------------------------------------


@texture("civic_felt", size=512, seed=9121)
def civic_felt(size: int, seed: int, out) -> None:
    """Pressed wool felt / baize, near white (tinted per material: pool-table green, altar red): matted fibre
    noise, faint nap direction, soft mottling."""
    fib = T.spectral(size, 0.25, seed)
    nap = T.spectral(size, 0.8, seed + 1, anisotropy=(1.0, 5.0))
    mottle = T.spectral(size, 2.4, seed + 2)
    col = _fill(size, size, "#ebe8e2") * (0.9 + 0.06 * fib[..., None] + 0.04 * nap[..., None]) * (0.95 + 0.07 * mottle[..., None])
    h = T.normalize(0.6 * fib + 0.4 * nap)
    T.save_pbr_set(out, np.clip(col, 0, 1), h, np.clip(0.9 + 0.06 * fib, 0, 1), normal_strength=1.1)


@texture("civic_wool", size=512, seed=9131)
def civic_wool(size: int, seed: int, out) -> None:
    """Army surplus wool blanket, near white (tinted grey / olive / brown): 2/2 twill ribs on the diagonal,
    fuzz and pilling."""
    xx, yy = _grid(size)
    n = 64
    twill = 0.5 + 0.5 * np.sin((xx + yy) / size * n * 2 * np.pi)
    weave = 0.5 + 0.5 * np.sin(xx / size * n * 2 * np.pi * 2) * np.sin(yy / size * n * 2 * np.pi * 2)
    fuzz = T.spectral(size, 0.35, seed)
    f1, f2, _ = T.worley(size, 900, seed + 1)
    pill = np.clip(1.0 - f1 / 3.0, 0, 1) * T.smoothstep(0.55, 0.8, T.spectral(size, 1.8, seed + 2))
    mottle = T.spectral(size, 2.2, seed + 3)
    col = _fill(size, size, "#d8d5ce") * (0.82 + 0.1 * twill[..., None] + 0.06 * fuzz[..., None]) * (0.94 + 0.08 * mottle[..., None])
    col = T.mix(col, _fill(size, size, "#c9c5bd"), pill * 0.4)
    h = T.normalize(0.5 * twill + 0.2 * weave + 0.3 * fuzz + 0.4 * pill)
    T.save_pbr_set(out, np.clip(col, 0, 1), h, np.clip(0.93 + 0.05 * fuzz, 0, 1), normal_strength=1.6)


# ------------------------------------------------------------------------------------------------
# stone
# ------------------------------------------------------------------------------------------------


def _granite(w: int, h: int, seed: int, crystal_px: float = 4.0):
    """Salt-and-pepper grey granite colour + height: mostly mid-grey feldspar, white quartz, black biotite
    specks, faint pink grains; crystal size ~crystal_px pixels. Tileable when w == h is a power of two."""
    size = 1 << int(np.ceil(np.log2(max(w, h))))
    f1, f2, cid = T.worley(size, int(size * size / (crystal_px * crystal_px)), seed, jitter=1.0)
    hue = (np.sin(cid * 12.9898 + 0.31) * 43758.5453) % 1.0
    base = T.gradient(hue, [(0.0, "#87857f"), (0.5, "#9a9790"), (0.82, "#aaa69e"), (0.86, "#b0a197"), (0.9, "#d3d0c9"),
                            (0.94, "#d9d6d0"), (0.95, "#383633"), (1.0, "#2c2a28")])
    crystal = T.smoothstep(0.0, 2.0, f2 - f1)
    base *= (0.94 + 0.06 * crystal)[..., None]
    base = np.stack([T.blur(base[..., i], 0.6) for i in range(3)], -1)
    big = T.spectral(size, 2.6, seed + 1)
    base *= (0.93 + 0.1 * big)[..., None]
    height = T.normalize(0.5 * crystal + 0.5 * T.spectral(size, 1.0, seed + 2))
    return base[:h, :w], height[:h, :w]


def _coverage(field: np.ndarray, cover: float, soft: float = 0.06) -> np.ndarray:
    """Mask of the top `cover` fraction of a field (soft edge), independent of the field's range."""
    t = float(np.quantile(field, 1.0 - cover))
    return T.smoothstep(t - soft * 0.5, t + soft * 0.5, field)


def _lichen(w: int, h: int, seed: int, amount: float):
    """Crustose lichen: lobed grey-green patches grown from warped rosettes, with a paler margin; sparse
    rusty-orange spots. amount 0..1 ~ fraction of the surface covered (x0.22). Returns (green, orange)."""
    size = 1 << int(np.ceil(np.log2(max(w, h))))
    a = T.spectral(size, 1.8, seed)
    b = T.spectral(size, 0.8, seed + 1)
    f1, _, _ = T.worley(size, 70, seed + 2)
    ros = np.clip(1.0 - f1 / (size * 0.07), 0, 1)
    ros = T.warp(ros, T.spectral(size, 1.7, seed + 4), T.spectral(size, 1.7, seed + 5), size * 0.025)
    fine = T.spectral(size, 0.6, seed + 6)
    field = 0.55 * ros + 0.3 * a + 0.15 * b + 0.12 * fine
    g = _coverage(field, 0.22 * amount, 0.025)
    margin = np.clip(g - T.blur(g, 2.0), 0, 1)
    g = np.clip(g * (0.7 + 0.3 * b) + margin * 0.6, 0, 1)
    o_field = 0.6 * T.spectral(size, 1.4, seed + 3) + 0.25 * b + 0.15 * fine
    o = _coverage(o_field, 0.04 * amount, 0.03)
    return g[:h, :w], o[:h, :w]


@texture("civic_granite", size=1024, seed=9141)
def civic_granite(size: int, seed: int, out) -> None:
    """Weathered grey headstone granite (1 tile ~ 0.5 m at uv_scale 2): salt-and-pepper crystals, rain
    streaks running down V, grey-green and orange crustose lichen, a dull weathered finish."""
    col, height = _granite(size, size, seed, 4.0)
    streak = T.spectral(size, 1.2, seed + 5, anisotropy=(14.0, 1.0))
    col *= (0.9 + 0.14 * streak[..., None])
    g, o = _lichen(size, size, seed + 7, 0.8)
    col = T.mix(col, np.ones_like(col) * _col("#a5ab8f"), g * 0.8)
    col = T.mix(col, np.ones_like(col) * _col("#c47b33"), o * 0.85)
    height = T.normalize(height + 0.6 * g + 0.4 * o)
    rough = np.clip(0.62 + 0.1 * streak + 0.2 * g, 0, 1)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=2.2)


@texture("civic_marble", size=1024, seed=9151)
def civic_marble(size: int, seed: int, out) -> None:
    """Old white marble (memorials, baptismal font, altar mensa): soft grey clouded veining with a few fine
    dark veins, sugary weathering, faint grey-green biofilm running down V."""
    xx, yy = _grid(size)
    turb = T.fbm(size, seed, octaves=6, base_freq=3)
    turb2 = T.fbm(size, seed + 1, octaves=5, base_freq=5)
    v1 = np.sin((xx + yy * 0.5) / size * 2 * np.pi * 2 + turb * 7.0)
    v2 = np.sin((xx * 0.4 - yy) / size * 2 * np.pi * 3 + turb2 * 9.0)
    soft = (1.0 - np.abs(v1)) ** 5
    fine = (1.0 - np.abs(v2)) ** 40
    cloud = T.spectral(size, 2.2, seed + 2)
    sugar = T.spectral(size, 0.3, seed + 3)
    col = _fill(size, size, "#ebe8e1") * (0.94 + 0.05 * sugar[..., None])
    col = T.mix(col, _fill(size, size, "#a9aaa7"), np.clip(soft * 0.75 + T.smoothstep(0.6, 1.0, cloud) * 0.3, 0, 1))
    col = T.mix(col, _fill(size, size, "#7d7f80"), np.clip(T.blur(fine, 0.8) * 0.4, 0, 1))
    bio = T.blur(T.spectral(size, 1.0, seed + 4, anisotropy=(18.0, 1.0)), 2.0)
    bio_m = _coverage(bio, 0.18, 0.2) * (0.5 + 0.5 * T.spectral(size, 2.0, seed + 5))
    col = T.mix(col, _fill(size, size, "#6e7262"), bio_m * 0.35)
    height = T.normalize(0.5 * sugar - 0.2 * fine + 0.3 * turb)
    rough = np.clip(0.5 + 0.22 * sugar + 0.1 * bio_m, 0, 1)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=1.0)


# ------------------------------------------------------------------------------------------------
# metals
# ------------------------------------------------------------------------------------------------


@texture("civic_wrought_iron", size=512, seed=9161)
def civic_wrought_iron(size: int, seed: int, out) -> None:
    """Black-painted wrought iron (graveyard railings, bell yoke straps, stove fronts): satin enamel over a
    hammered surface, small rust blooms with thin streaks bleeding down V (the wear layer adds rust on
    edges)."""
    ham = T.blur(T.spectral(size, 0.9, seed), 1.5)
    bloom_f = 0.7 * T.spectral(size, 1.3, seed + 1) + 0.3 * T.spectral(size, 0.5, seed + 4)
    bloom = _coverage(bloom_f, 0.07, 0.05)
    streak = T.blur(T.spectral(size, 1.0, seed + 2, anisotropy=(12.0, 1.0)), 1.0)
    run = _coverage(streak, 0.08, 0.06) * T.smoothstep(0.3, 0.7, T.spectral(size, 2.0, seed + 5))
    rust = np.clip(bloom + run * 0.6, 0, 1)
    col = _fill(size, size, "#1e1e1d") * (0.85 + 0.25 * ham[..., None])
    rc = T.gradient(T.spectral(size, 0.8, seed + 3), [(0.0, "#3a2416"), (0.5, "#6a3a1c"), (1.0, "#8e5226")])
    col = T.mix(col, rc, rust * 0.9)
    h = T.normalize(0.6 * ham + 0.4 * bloom)
    rough = np.clip(0.45 + 0.1 * ham + 0.4 * rust, 0, 1)
    T.save_pbr_set(out, np.clip(col, 0, 1), h, rough, metal=np.clip(0.2 - rust * 0.2, 0, 1), normal_strength=2.0)


@texture("civic_bronze", size=512, seed=9171)
def civic_bronze(size: int, seed: int, out) -> None:
    """Cast bell bronze: dark brown patina over golden metal, verdigris weeping down along U (lathe
    parts map U along their axis), casting pits."""
    pat = T.spectral(size, 2.0, seed)
    fine = T.spectral(size, 0.7, seed + 1)
    weep = T.blur(T.spectral(size, 1.2, seed + 2, anisotropy=(1.0, 10.0)), 1.0)
    verd = np.clip(_coverage(weep, 0.22, 0.12) * (0.4 + 0.6 * T.smoothstep(0.3, 0.7, pat)), 0, 1)
    f1, _, _ = T.worley(size, 260, seed + 3)
    pits = np.clip(1.0 - f1 / 2.2, 0, 1) * T.smoothstep(0.6, 0.8, T.spectral(size, 1.5, seed + 4))
    metal_c = T.gradient(fine, [(0.0, "#6b4d2a"), (0.5, "#8c6a3a"), (1.0, "#a7834a")])
    col = T.mix(metal_c, _fill(size, size, "#3c3024"), T.smoothstep(0.3, 0.8, pat) * 0.7)
    col = T.mix(col, _fill(size, size, "#5d9a84"), verd * 0.85)
    col *= (1.0 - 0.4 * pits)[..., None]
    metal = np.clip(0.9 - 0.6 * T.smoothstep(0.3, 0.8, pat) - 0.9 * verd, 0, 1)
    rough = np.clip(0.35 + 0.35 * T.smoothstep(0.3, 0.8, pat) + 0.3 * verd + 0.2 * pits, 0, 1)
    T.save_pbr_set(out, np.clip(col, 0, 1), T.normalize(fine * 0.4 + verd * 0.4 - pits), rough, metal=metal, normal_strength=1.6)


@texture("civic_brass_tarnish", size=512, seed=9181)
def civic_brass_tarnish(size: int, seed: int, out) -> None:
    """Old brass hardware (counter grilles, PO box doors, plaques, foot rails): brown tarnish blooms,
    polished where hands rubbed it, fine scratches."""
    t1 = T.spectral(size, 1.7, seed)
    t2 = T.spectral(size, 0.8, seed + 1)
    tarn = T.smoothstep(0.45, 0.9, 0.6 * t1 + 0.4 * t2) * 0.85
    scr = _scratches(size, seed + 2, 120, (6, 40), width=0.5)
    col = T.mix(_fill(size, size, "#c09a52"), _fill(size, size, "#5d4a2b"), tarn * 0.85)
    col = T.mix(col, _fill(size, size, "#e1c07a"), scr * 0.4)
    rough = np.clip(0.22 + 0.45 * tarn + 0.1 * t2 - 0.1 * scr, 0, 1)
    T.save_pbr_set(out, np.clip(col, 0, 1), T.normalize(-scr + 0.3 * tarn), rough,
                   metal=np.clip(1.0 - 0.35 * tarn, 0, 1), normal_strength=0.8)


# ------------------------------------------------------------------------------------------------
# civic_print atlas
# ------------------------------------------------------------------------------------------------


def _dartboard(n: int) -> tuple[np.ndarray, np.ndarray]:
    xx, yy = _grid(n)
    cx = cy = n / 2
    rr = np.hypot(xx - cx, yy - cy) / (n / 2)
    ang = (np.degrees(np.arctan2(xx - cx, -(yy - cy))) + 9.0) % 360.0
    sector = (ang // 18).astype(int)
    alt = (sector % 2).astype(np.float32)
    black, cream, red, green = _col("#1c1b1a"), _col("#d9cfae"), _col("#a3241f"), _col("#2c6a3c")
    col = np.ones((n, n, 3), np.float32) * _col("#141312")
    board = rr < 0.76
    single = np.where(alt[..., None] > 0.5, cream, black)
    ring_col = np.where(alt[..., None] > 0.5, green, red)
    col = np.where(board[..., None], single, col)
    treble = (rr > 0.42) & (rr < 0.47)
    double = (rr > 0.71) & (rr < 0.76)
    col = np.where((treble | double)[..., None], ring_col, col)
    col = np.where((rr < 0.075)[..., None], green, col)
    col = np.where((rr < 0.032)[..., None], red, col)
    wire = np.zeros((n, n), np.float32)
    for edge in (0.032, 0.075, 0.42, 0.47, 0.71, 0.76):
        wire = np.maximum(wire, np.clip(1.2 - np.abs(rr - edge) * n / 2, 0, 1))
    fa = (ang % 18.0)
    spoke = np.clip(1.0 - np.minimum(fa, 18.0 - fa) * rr * n / 2 * np.pi / 180.0, 0, 1) * ((rr > 0.075) & (rr < 0.76))
    wire = np.maximum(wire, spoke)
    col = T.mix(col, np.ones_like(col) * _col("#b9b9b4"), wire * 0.85)
    order = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5]
    f = _font(SERIF, int(n * 0.07), "Bold")
    items = []
    for i, num in enumerate(order):
        a = np.radians(i * 18)
        items.append((cx + np.sin(a) * n * 0.43, cy - np.cos(a) * n * 0.43, str(num), f))
    nums = _text(n, n, items)
    col = T.mix(col, np.ones_like(col) * _col("#e8e4d8"), nums)
    # sisal fibres + dart holes
    fib = _noise(n, n, 0.3, 77)
    col *= (0.86 + 0.18 * fib)[..., None]
    holes = T.smoothstep(0.86, 0.9, _noise(n, n, 0.2, 78)) * (rr < 0.6)
    col *= (1.0 - 0.6 * holes)[..., None]
    h = 0.5 * fib + 0.6 * wire - 0.5 * holes
    return col, h


def _jukebox_cards(w: int, h: int, seed: int) -> np.ndarray:
    r = T.rng(seed)
    col = _fill(w, h, "#2a2622")
    titles = ["TIMBER WALTZ", "COLD CREEK", "LONG HAUL HOME", "SAWDUST HEART", "RIVER IN MAY", "RAIN ON RT 9",
              "LAST SHIFT", "LARCH GOLD", "NORTHBOUND", "BACK ROAD BLUES", "HOLLOW MOON", "ONE MORE ROUND"]
    acts = ["The Larch Boys", "Dot Haskins", "Tamsin Ramblers", "Earl & Junie", "Cord Wheeler", "The Fallers"]
    cw, ch = w // 4, h // 3
    f1 = _font(MONO, 11)
    f2 = _font(MONO_R, 9)
    xx, yy = _grid(w, h)
    for i in range(12):
        cx, cy = (i % 4) * cw, (i // 4) * ch
        card = _rect(xx, yy, cx + 3, cy + 3, cx + cw - 3, cy + ch - 3)
        tint = _col(["#f1e7c9", "#f3dfd2", "#e2ecd8", "#f2ecd8"][i % 4])
        col = T.mix(col, np.ones_like(col) * tint, card)
        band = _rect(xx, yy, cx + 3, cy + ch / 2 - 2, cx + cw - 3, cy + ch / 2 + 1)
        col = T.mix(col, np.ones_like(col) * _col(["#b8322a", "#2a5aa0"][i % 2]), band * 0.8)
        act = acts[int(r.integers(0, len(acts)))]
        t = _text(w, h, [(cx + cw / 2, cy + ch * 0.28, titles[i], _fit(MONO, titles[i], cw - 10, 11)),
                         (cx + cw / 2, cy + ch * 0.74, act, _fit(MONO_R, act, cw - 10, 9))])
        col = T.mix(col, np.ones_like(col) * _col("#1d1b18"), t * 0.85)
    del f1
    return col


def _jukebox_grille(w: int, h: int) -> tuple[np.ndarray, np.ndarray]:
    """Speaker grille: oxblood cloth behind vertical chrome bars, an arched chrome frame and a central
    star-burst medallion."""
    xx, yy = _grid(w, h)
    u, v = xx / w, yy / h
    cloth = _fill(w, h, "#5a2b22") * (0.78 + 0.22 * _noise(w, h, 0.3, 91))[..., None]
    weave = 0.5 + 0.5 * np.sin(xx * 2.2) * np.sin(yy * 2.2)
    cloth *= (0.9 + 0.1 * weave)[..., None]
    bars = np.clip(1.6 - np.abs(((xx + 8) % 16) - 8), 0, 1) * (v > 0.12)
    arch = np.clip(1.0 - np.abs(np.hypot((u - 0.5) * 1.3, (v - 0.95) * 1.0) - 0.82) * 60, 0, 1)
    rim = np.clip(1.0 - np.abs(np.hypot((u - 0.5) * 1.3, (v - 0.95) * 1.0) - 0.88) * 80, 0, 1)
    inside = np.hypot((u - 0.5) * 1.3, (v - 0.95)) < 0.82
    rr = np.hypot(xx - w / 2, yy - h * 0.55)
    ang = np.arctan2(yy - h * 0.55, xx - w / 2)
    star = np.clip((14 + 6 * np.cos(ang * 8) - rr) * 0.6, 0, 1)
    metal = np.clip(bars * inside + arch + rim + star, 0, 1)
    col = T.mix(cloth, np.ones_like(cloth) * _col("#cfcabd"), metal)
    return col, metal


def _labels(w: int, seed: int) -> np.ndarray:
    names = [("OLD SAWBACK", "SOUR MASH WHISKEY", "#e2c98a", "#5a1d14"),
             ("CORVANE", "DRY GIN", "#e8eee8", "#1f4a3a"),
             ("LARCH HOLLOW", "STRAIGHT RYE", "#d8b06a", "#2a1a10"),
             ("NORTH FORK", "VODKA", "#f2f2f0", "#1f3570"),
             ("TAMSIN GOLD", "DARK RUM", "#1e1a16", "#d9a548"),
             ("HARROW", "LAGER BEER", "#e9dfc7", "#8a1f1c"),
             ("PELL'S", "PEPPERMINT SCHNAPPS", "#f0f0ea", "#2b7a3c"),
             ("MILE 9", "COFFEE LIQUEUR", "#3a2418", "#e8d3a8")]
    col = np.zeros((32 * 8, w, 3), np.float32)
    xx, yy = _grid(w, 32)
    for k, (a, b, bg, fg) in enumerate(names):
        c = _fill(w, 32, bg)
        border = 1.0 - _rect(xx, yy, 3, 2, w - 3, 30)
        c = T.mix(c, np.ones_like(c) * _col(fg), border * 0.9)
        t = _text(w, 32, [(w / 2, 11, a, _fit(SERIF, a, w - 30, 16, "Bold")), (w / 2, 24, b, _fit(MONO, b, w - 40, 9))])
        c = T.mix(c, np.ones_like(c) * _col(fg), t)
        c *= (0.8 + 0.2 * _noise(w, 32, 1.5, seed + k))[..., None]
        col[k * 32:(k + 1) * 32] = c
    return col


def _tap_labels(seed: int) -> np.ndarray:
    names = [("HARROW", "LAGER", "#e9dfc7", "#8a1f1c"), ("TAMSIN", "AMBER", "#d39a3a", "#2a160c"),
             ("SAWBACK", "STOUT", "#1d1a17", "#e6d6b0"), ("COLD", "CREEK", "#cfe0e6", "#1f4a6a")]
    col = np.zeros((128, 256, 3), np.float32)
    xx, yy = _grid(64, 128)
    for k, (a, b, bg, fg) in enumerate(names):
        c = _fill(64, 128, bg)
        oval = np.clip((1.0 - np.hypot((xx - 32) / 28, (yy - 64) / 58)) * 20, 0, 1)
        c = T.mix(np.ones_like(c) * _col(fg), c, oval)
        t = _text(64, 128, [(32, 52, a, _fit(SERIF, a, 50, 15, "Bold")), (32, 76, b, _fit(MONO, b, 46, 11))])
        c = T.mix(c, np.ones_like(c) * _col(fg), t)
        c *= (0.82 + 0.18 * _noise(64, 128, 1.5, seed + k))[..., None]
        col[:, k * 64:(k + 1) * 64] = c
    return col


def _stencil(w: int, h: int, items, ground: np.ndarray, ink: str, seed: int, wear: float) -> np.ndarray:
    """Spray-stencilled text onto a ground (soft overspray, patchy coverage)."""
    t = _text(w, h, items)
    cover = 1.0 - _wear_mask(w, h, seed, wear) * 0.8
    return T.mix(ground, np.ones_like(ground) * _col(ink), np.clip(t * cover * 0.92, 0, 1))


def _relief_side(w: int, h: int, seed: int) -> np.ndarray:
    xx, yy = _grid(w, h)
    wood = _fill(w, h, "#5d6b47") * (0.85 + 0.15 * _noise(w, h, 1.0, seed))[..., None]
    plank = (np.abs(((yy / h) * 4) % 1.0 - 0.5) > 0.47).astype(np.float32)
    wood *= (1.0 - 0.35 * plank)[..., None]
    sq = _rect(xx, yy, 14, 22, 82, 90)
    wood = T.mix(wood, np.ones_like(wood) * _col("#e9e6dc"), sq * 0.95)
    cross = np.maximum(_rect(xx, yy, 40, 30, 56, 82), _rect(xx, yy, 22, 48, 74, 64))
    wood = T.mix(wood, np.ones_like(wood) * _col("#2f7d43"), cross)
    items = [(168, 30, "EMERGENCY", _font(MONO, 17)), (168, 50, "RELIEF SUPPLIES", _font(MONO, 13)),
             (168, 74, "SAWBACK COUNTY", _font(MONO_R, 11)), (168, 88, "EMERGENCY SERVICES", _font(MONO_R, 10)),
             (128, 114, "BLANKETS - WATER - FIRST AID", _font(MONO_R, 10))]
    return _stencil(w, h, items, wood, "#ebe7da", seed + 3, 0.45)


def _relief_end(w: int, h: int, seed: int) -> np.ndarray:
    xx, yy = _grid(w, h)
    wood = _fill(w, h, "#5d6b47") * (0.85 + 0.15 * _noise(w, h, 1.0, seed))[..., None]
    plank = (np.abs(((yy / h) * 4) % 1.0 - 0.5) > 0.47).astype(np.float32)
    wood *= (1.0 - 0.35 * plank)[..., None]
    items = [(128, 26, "THIS SIDE UP", _font(MONO, 15)), (128, 54, "LOT 0412  -  24 x 1 L", _font(MONO_R, 12)),
             (128, 76, "DO NOT STACK > 4", _font(MONO_R, 12)), (128, 102, "PELL'S CROSSING GRANGE", _font(MONO_R, 11))]
    head = np.clip((np.minimum(yy - 22, 0) + 12 - np.abs(xx - 25) * 0.9) * 0.0 + ((yy - 22) * 0.9 - np.abs(xx - 25)) * 0.8, 0, 1) * (yy > 22) * (yy < 44)
    arrow = np.maximum(_rect(xx, yy, 21, 40, 29, 100), head)
    wood = T.mix(wood, np.ones_like(wood) * _col("#ebe7da"), arrow * 0.85)
    return _stencil(w, h, items, wood, "#ebe7da", seed + 5, 0.4)


def _relief_lid(w: int, h: int, seed: int) -> np.ndarray:
    xx, yy = _grid(w, h)
    wood = _fill(w, h, "#5a6844") * (0.85 + 0.15 * _noise(w, h, 1.0, seed))[..., None]
    plank = (np.abs(((xx / w) * 3) % 1.0 - 0.5) > 0.48).astype(np.float32)
    wood *= (1.0 - 0.35 * plank)[..., None]
    items = [(128, 34, "SHELTER STOCK", _font(MONO, 18)), (128, 64, "PROPERTY OF THE GRANGE", _font(MONO_R, 12)),
             (128, 90, "DO NOT REMOVE", _font(MONO, 14))]
    out = _stencil(w, h, items, wood, "#ebe7da", seed + 7, 0.5)
    hand = _text(w, h, [(150, 114, "COUNTED 3/14 - JB", _font(HAND, 16, "Bold"))])
    return T.mix(out, np.ones_like(out) * _col("#1f2a44"), hand * 0.85)


def _mail_front(w: int, h: int, seed: int) -> np.ndarray:
    xx, yy = _grid(w, h)
    paint = _fill(w, h, "#26466e") * (0.9 + 0.1 * _noise(w, h, 1.5, seed))[..., None]
    plate = _rect(xx, yy, 14, 30, w - 14, 70)
    paint = T.mix(paint, np.ones_like(paint) * _col("#9ea3a6"), plate)
    slot = _rect(xx, yy, 22, 44, w - 22, 56)
    paint = T.mix(paint, np.ones_like(paint) * _col("#0d0f12"), slot)
    t = _text(w, h, [(w / 2, 108, "MAIL", _font(SERIF, 40, "Bold"))])
    paint = T.mix(paint, np.ones_like(paint) * _col("#e8e6df"), t)
    card = _rect(xx, yy, 20, 150, w - 20, 236)
    paint = T.mix(paint, np.ones_like(paint) * _col("#e9e3d0"), card)
    ct = _text(w, h, [(w / 2, 162, "COLLECTION", _font(MONO, 10)), (w / 2, 180, "MON-FRI  4:30 PM", _font(MONO_R, 9)),
                      (w / 2, 196, "SAT  11:00 AM", _font(MONO_R, 9)), (w / 2, 220, "LAST PICKUP", _font(MONO_R, 9))])
    paint = T.mix(paint, np.ones_like(paint) * _col("#1d2430"), ct)
    scrawl = _text(w, h, [(w / 2, 222, "NONE", _font(HAND, 22, "Bold"))])
    paint = T.mix(paint, np.ones_like(paint) * _col("#8a1f1a"), scrawl * 0.9)
    return paint


def _mail_side(w: int, h: int, seed: int) -> np.ndarray:
    """Collection-box side: a post-horn emblem (coiled horn, flared bell, cord) over the town name."""
    paint = _fill(w, h, "#26466e") * (0.9 + 0.1 * _noise(w, h, 1.5, seed))[..., None]
    horn = np.zeros((h, w), np.float32)
    im = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(im)
    d.ellipse((34, 66, 84, 116), outline=255, width=7)                      # coil
    d.line((60, 116, 98, 104), fill=255, width=7)                           # lead pipe
    d.polygon([(94, 92), (118, 80), (118, 128), (94, 116)], fill=255)        # bell
    d.line((34, 90, 18, 84), fill=255, width=5)                             # mouthpiece
    d.arc((40, 100, 110, 150), 200, 340, fill=255, width=3)                 # cord
    horn = np.asarray(im, np.float32) / 255.0
    paint = T.mix(paint, np.ones_like(paint) * _col("#e2e0d8"), horn * 0.92)
    t = _text(w, h, [(64, 172, "PELL'S", _font(SERIF, 20, "Bold")), (64, 196, "CROSSING", _font(SERIF, 17, "Bold"))])
    return T.mix(paint, np.ones_like(paint) * _col("#e2e0d8"), t)


def _paper(w: int, h: int, seed: int, tone: str = "#ece6d4") -> np.ndarray:
    p = _fill(w, h, tone)
    p *= (0.9 + 0.1 * _noise(w, h, 1.6, seed))[..., None]
    stain = T.smoothstep(0.7, 0.95, _noise(w, h, 2.2, seed + 1))
    return T.mix(p, np.ones_like(p) * _col("#b89a62"), stain * 0.4)


def _notice(w: int, h: int, seed: int) -> np.ndarray:
    p = _paper(w, h, seed, "#efeee8")
    lines = [(w / 2, 14, "NOTICE", _font(SERIF, 16, "Bold")), (w / 2, 30, "BY ORDER OF THE", _font(MONO_R, 7)),
             (w / 2, 40, "CORDON AUTHORITY", _font(MONO, 9))]
    body = ["All residents of", "Pell's Crossing are to", "assemble at the GRANGE", "HALL for evacuation.", "Bring one bag only.",
            "Persons who are sick or", "have been bitten must", "report to the medical", "tent. Do not approach", "anyone with symptoms."]
    for i, s in enumerate(body):
        lines.append((10, 56 + i * 11, s, _font(TYPE, 9), "lm"))
    t = _text(w, h, lines)
    p = T.mix(p, np.ones_like(p) * _col("#18181a"), t * 0.9)
    hand = _text(w, h, [(w / 2, 168, "NO BUSES CAME", _font(HAND, 15, "Bold"))])
    return T.mix(p, np.ones_like(p) * _col("#7a1414"), hand * 0.9)


def _sign_board(w: int, h: int, seed: int, text: str, sub: str, bg: str, fg: str) -> np.ndarray:
    xx, yy = _grid(w, h)
    c = _fill(w, h, bg) * (0.85 + 0.15 * _noise(w, h, 1.3, seed))[..., None]
    border = 1.0 - _rect(xx, yy, 5, 5, w - 5, h - 5)
    c = T.mix(c, np.ones_like(c) * _col(fg), border * 0.8)
    t = _text(w, h, [(w / 2, h * 0.42, text, _fit(SERIF, text, w - 40, int(h * 0.5), "Bold")),
                     (w / 2, h * 0.8, sub, _fit(SERIF, sub, w - 80, int(h * 0.22), "SemiBold"))])
    cover = 1.0 - _wear_mask(w, h, seed + 3, 0.35) * 0.7
    return T.mix(c, np.ones_like(c) * _col(fg), t * cover)


def _church_letters(w: int, h: int, seed: int) -> np.ndarray:
    xx, yy = _grid(w, h)
    felt = _fill(w, h, "#18191a")
    grooves = (np.abs((yy % 12) - 6) < 0.8).astype(np.float32)
    felt *= (0.85 + 0.15 * _noise(w, h, 0.6, seed))[..., None] * (1.0 - 0.3 * grooves)[..., None]
    head = _text(w, h, [(w / 2, 20, "ST. ANSEL'S EPISCOPAL CHURCH", _fit(SERIF, "ST. ANSEL'S EPISCOPAL CHURCH", w - 30, 22, "Bold"))])
    felt = T.mix(felt, np.ones_like(felt) * _col("#d7b45a"), head)
    rows = ["SUNDAY EUCHARIST 10 AM", "FOOD PANTRY TUE & SAT", "AL  ARE W LCOME", "PRAY FOR OUR VALLEY"]
    f = _font(MONO, 17)
    items = [(w / 2, 58 + i * 34, s, f) for i, s in enumerate(rows)]
    t = _text(w, h, items)
    felt = T.mix(felt, np.ones_like(felt) * _col("#ecebe6"), t)
    # one tilted, slipping letter
    slip = _text(w, h, [(318, 154, "E", f)])
    slip = np.asarray(Image.fromarray((slip * 255).astype(np.uint8)).rotate(-25, center=(318, 154)), np.float32) / 255.0
    return T.mix(felt, np.ones_like(felt) * _col("#ecebe6"), slip)


def _altar_frontal(w: int, h: int, seed: int) -> np.ndarray:
    xx, yy = _grid(w, h)
    c = _fill(w, h, "#7c1d22") * (0.85 + 0.15 * _noise(w, h, 0.5, seed))[..., None]
    gold = _col("#c9a24f")
    orph = np.maximum(_rect(xx, yy, 0, 10, w, 16), _rect(xx, yy, 0, h - 16, w, h - 10))
    cross = np.maximum(_rect(xx, yy, w / 2 - 6, 30, w / 2 + 6, 104), _rect(xx, yy, w / 2 - 26, 50, w / 2 + 26, 62))
    vine = np.zeros((h, w), np.float32)
    for k in range(2):
        yc = 24 if k == 0 else h - 24
        vine = np.maximum(vine, np.clip(1.6 - np.abs(yy - yc - 4 * np.sin(xx / 9.0)), 0, 1))
    deco = np.clip(orph + cross + vine * 0.8, 0, 1)
    c = T.mix(c, np.ones_like(c) * gold, deco * 0.9)
    fringe = (yy > h - 8) * (0.5 + 0.5 * np.sin(xx * 1.7))
    return T.mix(c, np.ones_like(c) * gold, fringe * 0.7)


def _plaques(w: int, seed: int) -> np.ndarray:
    texts = [("LOGGERS' JAMBOREE 1987", "AXE THROW - FIRST PLACE"), ("GRANGE HARVEST FAIR 1993", "BLUE RIBBON - PIES"),
             ("PELL'S CROSSING V.F.D.", "25 YEARS - W. BENNING")]
    col = np.zeros((96, w, 3), np.float32)
    xx, yy = _grid(w, 32)
    for k, (a, b) in enumerate(texts):
        c = _fill(w, 32, "#b8924c") * (0.8 + 0.2 * _noise(w, 32, 1.4, seed + k))[..., None]
        bev = 1.0 - _rect(xx, yy, 2, 2, w - 2, 30)
        c *= (1.0 - 0.3 * bev)[..., None]
        t = _text(w, 32, [(w / 2, 11, a, _fit(SERIF, a, w - 20, 13, "Bold")), (w / 2, 24, b, _fit(SERIF, b, w - 30, 10))])
        c = T.mix(c, np.ones_like(c) * _col("#2e2416"), t)
        col[k * 32:(k + 1) * 32] = c
    return col


def _scale_dial(n: int, seed: int) -> np.ndarray:
    xx, yy = _grid(n)
    cx = cy = n / 2
    rr = np.hypot(xx - cx, yy - cy)
    c = _fill(n, n, "#ece8dc")
    c = T.mix(c, np.ones_like(c) * _col("#262626"), np.clip(1.0 - np.abs(rr - n * 0.47) / 2.0, 0, 1))
    ang = np.degrees(np.arctan2(xx - cx, -(yy - cy)))
    tick = np.zeros((n, n), np.float32)
    items = []
    f = _font(MONO, 9)
    for i in range(26):
        a = -135 + i * (270 / 25)
        d = np.abs(((ang - a) + 180) % 360 - 180)
        long = 0.34 if i % 5 == 0 else 0.4
        tick = np.maximum(tick, np.clip(1.0 - d * rr * np.pi / 180, 0, 1) * (rr > n * long) * (rr < n * 0.44))
        if i % 5 == 0:
            ar = np.radians(a)
            items.append((cx + np.sin(ar) * n * 0.27, cy - np.cos(ar) * n * 0.27, str(i), f))
    items.append((cx, cy + n * 0.2, "POUNDS", _font(MONO_R, 8)))
    c = T.mix(c, np.ones_like(c) * _col("#1d1d1d"), np.clip(tick + _text(n, n, items), 0, 1))
    na = np.radians(-135 + 7 * 10.8)
    nx, ny = np.sin(na), -np.cos(na)
    t = np.clip((xx - cx) * nx + (yy - cy) * ny, 0, n * 0.42)
    needle = np.clip(1.5 - np.hypot(xx - cx - t * nx, yy - cy - t * ny), 0, 1)
    c = T.mix(c, np.ones_like(c) * _col("#a51e1a"), needle)
    c = T.mix(c, np.ones_like(c) * _col("#2a2a2a"), _disc(xx, yy, cx, cy, 5))
    return c * (0.9 + 0.1 * _noise(n, n, 1.8, seed))[..., None]


def _hymnal(seed: int) -> tuple[np.ndarray, np.ndarray]:
    xx, yy = _grid(64, 96)
    cover = _fill(64, 96, "#5a1a1e") * (0.85 + 0.15 * _noise(64, 96, 0.6, seed))[..., None]
    gold = _col("#c3a050")
    cross = np.maximum(_rect(xx, yy, 29, 22, 35, 58), _rect(xx, yy, 21, 32, 43, 38))
    t = _text(64, 96, [(32, 74, "HYMNAL", _font(SERIF, 11, "Bold"))])
    border = 1.0 - _rect(xx, yy, 4, 4, 60, 92)
    cover = T.mix(cover, np.ones_like(cover) * gold, np.clip(cross + t + border * 0.4, 0, 1) * 0.85)
    xs, ys = _grid(16, 96)
    spine = _fill(16, 96, "#4e1619") * (0.85 + 0.15 * _noise(16, 96, 0.6, seed + 1))[..., None]
    bands = _rect(xs, ys, 0, 10, 16, 13) + _rect(xs, ys, 0, 82, 16, 85)
    spine = T.mix(spine, np.ones_like(spine) * gold, np.clip(bands, 0, 1))
    return cover, spine


def _sort_labels(seed: int) -> np.ndarray:
    names = ["RURAL RT 1", "RURAL RT 2", "MILL ST", "TAMSIN RD", "RT 9 NORTH", "RT 9 SOUTH", "HOLD", "CORDON - HOLD"]
    col = np.zeros((128, 304, 3), np.float32)
    for k, s in enumerate(names):
        cx, cy = (k % 2) * 152, (k // 2) * 32
        c = _fill(152, 32, "#efe9d8" if k < 6 else "#f1d77a")
        t = _text(152, 32, [(76, 16, s, _fit(MONO, s, 140, 14))])
        c = T.mix(c, np.ones_like(c) * _col("#1b1b1b"), t)
        col[cy:cy + 32, cx:cx + 152] = c * (0.88 + 0.12 * _noise(152, 32, 1.5, seed + k))[..., None]
    return col


def _banner(w: int, h: int, seed: int) -> np.ndarray:
    xx, yy = _grid(w, h)
    c = _fill(w, h, "#5c1b25") * (0.85 + 0.15 * _noise(w, h, 0.5, seed))[..., None]
    gold = _col("#caa556")
    border = 1.0 - _rect(xx, yy, 8, 8, w - 8, h - 8)
    border2 = (1.0 - _rect(xx, yy, 14, 14, w - 14, h - 14)) * _rect(xx, yy, 12, 12, w - 12, h - 12)
    t = _text(w, h, [(w / 2, 44, "PELL'S CROSSING GRANGE", _fit(SERIF, "PELL'S CROSSING GRANGE", w - 60, 40, "Bold")),
                     (w / 2, 84, "No. 412  -  EST. 1911", _font(SERIF, 22, "SemiBold")),
                     (w / 2, 110, "NEIGHBOURS IN NEED", _font(SERIF, 14, "SemiBold"))])
    c = T.mix(c, np.ones_like(c) * gold, np.clip(t + border * 0.8 + border2 * 0.8, 0, 1))
    return c


def _juke_arch(w: int, h: int, seed: int) -> np.ndarray:
    """Translucent coloured plastic of the jukebox arch and pilasters (unlit: power is out): warm amber,
    cherry and lime bands with moulded ribs and trapped bubbles. U runs along the arch."""
    xx, yy = _grid(w, h)
    u = xx / w
    stops = [(0.0, "#c9781f"), (0.16, "#d8a23a"), (0.3, "#a8282a"), (0.44, "#d27b2a"), (0.56, "#d8a23a"),
             (0.7, "#5f9a3a"), (0.84, "#2f6aa0"), (1.0, "#c9781f")]
    c = T.gradient(u, stops)
    rib = 0.5 + 0.5 * np.sin(yy / h * 2 * np.pi * 6)
    c *= (0.78 + 0.22 * rib)[..., None]
    bub = np.zeros((h, w), np.float32)
    r = T.rng(seed)
    for _ in range(60):
        cx, cy, rad = r.uniform(0, w), r.uniform(0, h), r.uniform(1.5, 4.0)
        bub = np.maximum(bub, np.clip(1.0 - np.abs(np.hypot(xx - cx, yy - cy) - rad), 0, 1))
    return T.mix(c, np.ones_like(c) * _col("#f6efdc"), bub * 0.6)


def _photo(n: int, seed: int) -> np.ndarray:
    xx, yy = _grid(n)
    c = _fill(n, n, "#d7c9a6")
    img = _rect(xx, yy, 8, 8, n - 8, n - 24)
    blur = T.blur(_noise(n, n, 1.2, seed), 1.5)
    people = np.zeros((n, n), np.float32)
    for i in range(7):
        px = 20 + i * 15
        people = np.maximum(people, _disc(xx, yy, px, 52, 5) + _rect(xx, yy, px - 6, 58, px + 6, 92))
    tone = T.mix(np.ones((n, n, 3), np.float32) * _col("#a08766"), np.ones((n, n, 3), np.float32) * _col("#3e3020"),
                 np.clip(people * 0.85 + blur * 0.25, 0, 1))
    c = T.mix(c, tone, img)
    t = _text(n, n, [(n / 2, n - 12, "1987 CREW", _font(HAND, 14, "Bold"))])
    return T.mix(c, np.ones_like(c) * _col("#2d2418"), t)


def _keg_stamp(n: int, seed: int) -> np.ndarray:
    xx, yy = _grid(n)
    c = _fill(n, n, "#b9bbbb") * (0.85 + 0.15 * _noise(n, n, 1.0, seed))[..., None]
    t = _text(n, n, [(n / 2, 40, "PROPERTY OF", _font(MONO, 11)), (n / 2, 60, "HARROW", _font(MONO, 18)),
                     (n / 2, 80, "BREWING CO.", _font(MONO, 11)), (n / 2, 104, "1/2 BBL", _font(MONO_R, 10))])
    ring = np.clip(1.0 - np.abs(np.hypot(xx - n / 2, yy - n / 2) - 56) / 1.5, 0, 1)
    return T.mix(c, np.ones_like(c) * _col("#4a4c4c"), np.clip(t + ring, 0, 1) * 0.8)


def _pool_balls() -> np.ndarray:
    cols = ["#f2efe6", "#e8c22a", "#2a4fa8", "#c8281f", "#5a2a7a", "#e2701f", "#2a7a3c", "#7a1f1f", "#151515",
            "#e8c22a", "#2a4fa8", "#c8281f", "#5a2a7a", "#e2701f", "#2a7a3c", "#7a1f1f"]
    out = np.zeros((32, 512, 3), np.float32)
    xx, yy = _grid(32)
    f = _font(MONO, 9)
    for k in range(16):
        base = _col(cols[k])
        c = np.ones((32, 32, 3), np.float32) * base
        if k >= 9:  # stripes: white ball with a coloured band
            band = (np.abs(yy - 16) < 7).astype(np.float32)
            c = T.mix(np.ones_like(c) * _col("#f2efe6"), c, band)
        if k > 0:
            c = T.mix(c, np.ones_like(c) * _col("#f2efe6"), _disc(xx, yy, 16, 16, 6.5))
            t = _text(32, 32, [(16, 16, str(k), f)])
            c = T.mix(c, np.ones_like(c) * _col("#151515"), t)
        out[:, k * 32:(k + 1) * 32] = c
    return out


def _cot_tag(w: int, h: int, seed: int) -> np.ndarray:
    p = _paper(w, h, seed, "#e9dcb4")
    t = _text(w, h, [(w / 2, 18, "COT 23", _font(MONO, 14)), (w / 2, 42, "M. Okafor + 2", _font(HAND, 18, "Bold"))])
    return T.mix(p, np.ones_like(p) * _col("#1d2233"), t * 0.9)


def _felt_board(w: int, h: int, seed: int) -> np.ndarray:
    """Grange shelter roll-call board (letter board) - names struck through."""
    xx, yy = _grid(w, h)
    felt = _fill(w, h, "#1a1b1c") * (0.85 + 0.15 * _noise(w, h, 0.6, seed))[..., None]
    rows = ["SHELTER", "BEDS 64", "TAKEN 61", "SICK BAY UP", "BUS 0900", "BUS 0900", "BUS ????"]
    f = _font(MONO, 13)
    t = _text(w, h, [(w / 2, 18 + i * 29, s, f) for i, s in enumerate(rows)])
    return T.mix(felt, np.ones_like(felt) * _col("#e9e8e3"), t)


def _ledger(w: int, h: int, seed: int) -> np.ndarray:
    p = _paper(w, h, seed, "#e6dfc6")
    xx, yy = _grid(w, h)
    rule = ((yy % 16) < 1.0).astype(np.float32) * (yy > 30)
    p = T.mix(p, np.ones_like(p) * _col("#93a9bd"), rule * 0.7)
    p = T.mix(p, np.ones_like(p) * _col("#c48a8a"), (np.abs(xx - 24) < 0.8).astype(np.float32))
    names = ["Okafor x3", "Lindqvist", "Brandt x2", "Delgado", "Merrow kids", "Haskett", "Benning", "Tamsin crew x6",
             "Pell", "Calder", "Sorensen x4", "Reyes", "Nakamura x2"]
    items = [(w / 2, 14, "PANTRY SIGN-OUT", _font(MONO, 12))]
    for i, s in enumerate(names):
        items.append((30, 37 + i * 16, s, _font(HAND, 15, "Bold"), "lm"))
        items.append((w - 20, 37 + i * 16, ["2 cans", "1 box", "4 cans", "rice", "milk pwd", "-"][i % 6], _font(HAND, 14), "rm"))
    t = _text(w, h, items)
    return T.mix(p, np.ones_like(p) * _col("#1e2747"), t * 0.85)


@texture("civic_print", size=1024, seed=9201, sources=FONT_SOURCES)
def civic_print(size: int, seed: int, out) -> None:
    """Atlas of the town's printed / painted / engraved graphics (rects: PRINT_RECTS)."""
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

    dc, dh = _dartboard(256)
    put("dart", dc, dh, 0.9)
    put("juke_cards", _jukebox_cards(256, 128, seed + 1), None, 0.35)
    gc, gm = _jukebox_grille(256, 128)
    put("juke_grille", gc, gm * 0.6, np.clip(0.8 - gm * 0.55, 0, 1), gm)
    put("labels", _labels(256, seed + 2), None, 0.55)
    put("taps", _tap_labels(seed + 3), None, 0.35)
    xx, yy = _grid(256, 32)
    hh = _fill(256, 32, "#4a2c18") * (0.85 + 0.15 * _noise(256, 32, 1.0, seed + 4))[..., None]
    ht = _text(256, 32, [(128, 16, "HYMNS", _font(SERIF, 22, "Bold"))])
    put("hymn_header", T.mix(hh, np.ones_like(hh) * _col("#d4b062"), ht), ht * 0.5, 0.45, ht * 0.8)
    cards = np.zeros((96, 256, 3), np.float32)
    for k, num in enumerate(("412", "88", "305")):
        c = _fill(256, 32, "#141414")
        t = _text(256, 32, [(128, 16, num, _font(SERIF, 28, "Bold"))])
        cards[k * 32:(k + 1) * 32] = T.mix(c, np.ones_like(c) * _col("#efede6"), t) * (0.9 + 0.1 * _noise(256, 32, 1.4, seed + 10 + k))[..., None]
    put("hymn_cards", cards, None, 0.6)
    put("relief_side", _relief_side(256, 128, seed + 20), _noise(256, 128, 1.0, seed + 21) * 0.4, 0.85)
    put("relief_end", _relief_end(256, 128, seed + 22), _noise(256, 128, 1.0, seed + 23) * 0.4, 0.85)
    put("relief_lid", _relief_lid(256, 128, seed + 24), _noise(256, 128, 1.0, seed + 25) * 0.4, 0.85)
    put("mail_front", _mail_front(128, 256, seed + 26), None, 0.55)
    put("mail_side", _mail_side(128, 256, seed + 27), None, 0.55)
    put("notice", _notice(128, 176, seed + 28), None, 0.85)
    xx, yy = _grid(128, 32)
    ab = _fill(128, 32, "#b38d4a") * (0.8 + 0.2 * _noise(128, 32, 1.4, seed + 46))[..., None]
    ab *= (1.0 - 0.3 * (1.0 - _rect(xx, yy, 2, 2, 126, 30)))[..., None]
    at = _text(128, 32, [(64, 16, "ALMS FOR THE POOR", _fit(SERIF, "ALMS FOR THE POOR", 112, 14, "Bold"))])
    put("alms", T.mix(ab, np.ones_like(ab) * _col("#2b2114"), at), None, 0.35, 0.85)
    xx, yy = _grid(128, 48)
    cs = _paper(128, 48, seed + 47, "#e8e2cf")
    ct = _text(128, 48, [(64, 22, "CLOSED", _font(HAND, 34, "Bold")), (64, 41, "til further notice", _font(HAND, 13))])
    put("closed_sign", T.mix(cs, np.ones_like(cs) * _col("#8a1a16"), ct * 0.9), None, 0.85)
    put("po_sign", _sign_board(384, 64, seed + 29, "POST OFFICE", "PELL'S CROSSING", "#1f3b2a", "#e6dcc0"), None, 0.7)
    put("church_sign", _church_letters(384, 192, seed + 30), None, 0.8)
    put("altar_frontal", _altar_frontal(256, 128, seed + 31), _noise(256, 128, 0.5, seed + 32) * 0.3, 0.85)
    fb = _fill(256, 32, "#111111")
    ft = _text(256, 32, [(128, 16, "Harwick & Sons  -  Portland", _font(SERIF, 17, "SemiBold"))])
    put("fallboard", T.mix(fb, np.ones_like(fb) * _col("#c9a75a"), ft), None, 0.3, ft * 0.9)
    put("plaques", _plaques(256, seed + 33), None, 0.35, 0.85)
    put("scale_dial", _scale_dial(128, seed + 34), None, 0.3)
    hc, hs = _hymnal(seed + 35)
    put("hymnal", hc, None, 0.75)
    put("hymnal_spine", hs, None, 0.75)
    put("sort_labels", _sort_labels(seed + 36), None, 0.8)
    put("banner", _banner(512, 128, seed + 37), _noise(512, 128, 0.5, seed + 38) * 0.3, 0.85)
    put("juke_arch", _juke_arch(256, 128, seed + 39), None, 0.25)
    put("photo", _photo(128, seed + 40), None, 0.4)
    put("keg_stamp", _keg_stamp(128, seed + 41), None, 0.4, 0.9)
    put("pool_balls", _pool_balls(), None, 0.18)
    put("cot_tag", _cot_tag(128, 64, seed + 42), None, 0.85)
    put("felt_board", _felt_board(128, 224, seed + 43), None, 0.9)
    put("ledger", _ledger(256, 256, seed + 44), None, 0.85)
    wp = T.gradient(_noise(256, 256, 1.2, seed + 45), [(0.0, "#6b4626"), (1.0, "#8a5f35")])
    put("wood_plain", wp, None, 0.6)
    grime = T.spectral(size, 2.2, seed + 99)
    col *= (0.9 + 0.1 * grime[..., None])
    T.save_pbr_set(out, np.clip(col, 0, 1), np.clip(height + 0.05 * grime, 0, 1), np.clip(rough, 0, 1), metal=metal,
                   normal_strength=1.2)


# ------------------------------------------------------------------------------------------------
# civic_engrave atlas: carved headstone faces
# ------------------------------------------------------------------------------------------------

EPITAPHS = [
    ("IN LOVING MEMORY", "AUGUST", "LINDQVIST", "1871 - 1923", "FELLED BY THE", "TIMBER HE LOVED"),
    ("BELOVED WIFE", "MARY ELLEN", "PELL", "1889 - 1951", "SHE KEPT THE", "LAMP LIT"),
    ("", "EINAR", "BRANDT", "1898 - 1937", "LOST IN THE", "CORVANE DEEP"),
    ("OUR DARLING", "INFANT DAUGHTER", "OF J. & R. HASKETT", "1958", "SAFE IN", "HIS ARMS"),
    ("IN MEMORY OF", "THOMAS", "CALDER", "1902 - 1944", "HE GAVE", "HIS ALL"),
    ("AT REST", "HELEN", "MERROW", "1921 - 1989", "GONE HOME", ""),
    ("", "WILLIAM J.", "SORENSEN", "1866 - 1919", "THE FLU TOOK HIM", "THE SPRING CAME ANYWAY"),
    ("REST IN PEACE", "", "", "", "", ""),
]


@texture("civic_engrave", size=1024, seed=9211, sources=FONT_SOURCES)
def civic_engrave(size: int, seed: int, out) -> None:
    """Carved headstone faces, 4 x 2 portrait cells of 256 x 512 (cell k at column k % 4, row k // 4).
    Light stone with granite speckle (tinted per material), V-cut lettering with dirt in the grooves, rain
    streaks and lichen. Cell 7 is a plain face with a carved cross."""
    cw, ch = size // 4, size // 2
    col = np.zeros((size, size, 3), np.float32)
    height = np.zeros((size, size), np.float32)
    rough = np.zeros((size, size), np.float32)
    base, bh = _granite(size, size, seed, 2.2)
    base = np.clip(0.55 * base / np.maximum(base.mean(), 1e-3) * 0.8 + 0.45 * 0.8, 0, 1)  # low-contrast, light
    for k, lines in enumerate(EPITAPHS):
        cx0, cy0 = (k % 4) * cw, (k // 4) * ch
        xx, yy = _grid(cw, ch)
        items = []
        y = 120.0
        sizes = [17, 30, 30, 20, 15, 15]
        weights = ["SemiBold", "Bold", "Bold", "SemiBold", "Medium", "Medium"]
        gaps = [34, 38, 40, 46, 26, 26]
        for i, s in enumerate(lines):
            if s:
                items.append((cw / 2, y, s, _fit(SERIF, s, cw - 40, sizes[i], weights[i])))
            y += gaps[i]
        mask = _text(cw, ch, items)
        if k == 7:
            cross = np.maximum(_rect(xx, yy, cw / 2 - 9, 150, cw / 2 + 9, 330, 1.5), _rect(xx, yy, cw / 2 - 48, 196, cw / 2 + 48, 214, 1.5))
            mask = np.maximum(mask, cross)
            rest = _text(cw, ch, [(cw / 2, 380, "REST IN PEACE", _fit(SERIF, "REST IN PEACE", cw - 50, 20, "SemiBold"))])
            mask = np.maximum(mask, rest)
        # V-cut: blurred mask as depth, the groove floors collect dirt
        groove = T.blur(mask, 1.2)
        frame = (1.0 - _rect(xx, yy, 18, 18, cw - 18, ch - 18, 1.0)) * _rect(xx, yy, 14, 14, cw - 14, ch - 14, 1.0)
        streak = _noise(cw, ch, 1.1, seed + 30 + k)
        sv = T.blur(np.clip(streak - 0.4, 0, 1), 3.0)
        g, o = _lichen(cw, ch, seed + 50 + k, 0.35 + 0.12 * (k % 3))
        c = base[cy0:cy0 + ch, cx0:cx0 + cw].copy()
        c *= (0.9 + 0.12 * streak)[..., None]
        lip = np.clip(T.blur(mask, 2.4) - groove, 0, 1)
        c = T.mix(c, np.ones_like(c) * _col("#3e3c37"), np.clip(groove ** 0.8 * 0.9 + frame * 0.35, 0, 1))
        c = T.mix(c, np.ones_like(c) * _col("#e6e3dc"), lip * 0.35)
        c = T.mix(c, np.ones_like(c) * _col("#a4a98c"), g * 0.7)
        c = T.mix(c, np.ones_like(c) * _col("#c27a35"), o * 0.7)
        c = T.mix(c, np.ones_like(c) * _col("#3d3c36"), sv * 0.35)
        col[cy0:cy0 + ch, cx0:cx0 + cw] = c
        height[cy0:cy0 + ch, cx0:cx0 + cw] = 0.55 * bh[cy0:cy0 + ch, cx0:cx0 + cw] * 0.4 - groove * 0.8 - frame * 0.3 + g * 0.2
        rough[cy0:cy0 + ch, cx0:cx0 + cw] = np.clip(0.7 + 0.1 * streak + 0.15 * g + 0.1 * groove, 0, 1)
    T.save_pbr_set(out, np.clip(col, 0, 1), T.normalize(height), rough, normal_strength=3.0)


# ------------------------------------------------------------------------------------------------
# civic_po_boxes atlas: a bank of brass post-office box doors
# ------------------------------------------------------------------------------------------------


@texture("civic_po_boxes", size=1024, seed=9221, sources=FONT_SOURCES)
def civic_po_boxes(size: int, seed: int, out) -> None:
    """8 x 12 brass PO box doors numbered 101-196 (row-major from the top left) over a 1.0 x 1.5 m face:
    drawn on a 1024 x 1536 canvas (square doors) and squeezed to 1024 px, so the model maps the sheet 0..1
    over its 1.0 x 1.5 m front. Each door: bevelled frame, reeded glass window (dark, dusty), a combination
    dial with ticks and an arrow, the stamped number plate. Some doors pried open (dark recess)."""
    W, H = size, size * 3 // 2
    cols, rows = 8, 12
    dw, dh = W // cols, H // rows
    r = T.rng(seed)
    col = np.zeros((H, W, 3), np.float32)
    height = np.zeros((H, W), np.float32)
    rough = np.zeros((H, W), np.float32)
    metal = np.zeros((H, W), np.float32)
    xx, yy = _grid(dw, dh)
    tarn = T.spectral(1024, 2.2, seed)
    tarn = np.vstack([tarn, tarn[:512]])
    f_num = _font(MONO, 13)
    pried = set(PRIED_DOORS)
    for k in range(96):
        cx0, cy0 = (k % cols) * dw, (k // cols) * dh
        t = tarn[cy0:cy0 + dh, cx0:cx0 + dw]
        frame = 1.0 - _rect(xx, yy, 6, 6, dw - 6, dh - 6, 1.5)
        door = _rect(xx, yy, 8, 8, dw - 8, dh - 8, 1.0)
        win = _rect(xx, yy, 22, 16, dw - 22, 60, 1.0)
        reed = 0.5 + 0.5 * np.sin(xx * 1.4)
        dial = _disc(xx, yy, dw / 2, 86, 13, 1.0)
        dial_ring = np.clip(1.0 - np.abs(np.hypot(xx - dw / 2, yy - 86) - 13) / 1.5, 0, 1)
        ang = np.degrees(np.arctan2(xx - dw / 2, -(yy - 86)))
        ticks = (np.abs(((ang + 360) % 18) - 9) > 7.5) * (np.hypot(xx - dw / 2, yy - 86) > 9) * dial
        arrow = np.clip(1.0 - np.abs(xx - dw / 2) - np.maximum(0, yy - 75) * 0.3, 0, 1) * (yy > 70) * (yy < 78)
        plate = _rect(xx, yy, 34, 104, dw - 34, 120, 1.0)
        num = _text(dw, dh, [(dw / 2, 112, str(101 + k), f_num)])
        brass = T.mix(np.ones((dh, dw, 3), np.float32) * _col("#b8924d"), np.ones((dh, dw, 3), np.float32) * _col("#5a4628"),
                      T.smoothstep(0.35, 0.85, t) * 0.8)
        c = brass.copy()
        c = T.mix(c, np.ones_like(c) * _col("#2a2924") * (0.5 + 0.3 * reed[..., None]), win)
        c = T.mix(c, np.ones_like(c) * _col("#7a776e"), T.smoothstep(0.6, 0.9, t) * win * 0.6)
        c = T.mix(c, np.ones_like(c) * _col("#cfc9b8"), dial * 0.5)
        c = T.mix(c, np.ones_like(c) * _col("#2b2620"), np.clip(ticks + dial_ring * 0.8 + arrow, 0, 1))
        c = T.mix(c, np.ones_like(c) * _col("#d9bf7c"), plate * 0.6)
        c = T.mix(c, np.ones_like(c) * _col("#1f1a12"), num)
        c = T.mix(c, np.ones_like(c) * _col("#4d3d24"), frame)
        hgt = 0.5 * door - 0.3 * win + 0.1 * reed * win + 0.4 * dial - 0.2 * frame + 0.2 * plate - 0.2 * num
        ro = np.clip(0.3 + 0.45 * T.smoothstep(0.35, 0.85, t) - 0.2 * win, 0, 1)
        me = np.clip(1.0 - win - dial * 0.5, 0, 1)
        if k in pried:
            hole = _rect(xx, yy, 8, 8, dw - 8, dh - 8, 1.0)
            c = T.mix(c, np.ones_like(c) * _col("#0e0d0b"), hole)
            env = _rect(xx, yy, 18, 70, dw - 26, 112, 1.0)
            c = T.mix(c, np.ones_like(c) * _col("#cfc4a8"), env * 0.7)
            hgt = hgt * (1 - hole) - hole * 0.6
            me = me * (1 - hole)
            ro = np.where(hole > 0.5, 0.95, ro)
        col[cy0:cy0 + dh, cx0:cx0 + dw] = c
        height[cy0:cy0 + dh, cx0:cx0 + dw] = hgt
        rough[cy0:cy0 + dh, cx0:cx0 + dw] = ro
        metal[cy0:cy0 + dh, cx0:cx0 + dw] = me

    def squeeze(a):
        if a.ndim == 3:
            return np.stack([squeeze(a[..., i]) for i in range(a.shape[2])], -1)
        im = Image.fromarray(a.astype(np.float32), mode="F").resize((size, size), Image.BILINEAR)
        return np.asarray(im, np.float32)

    T.save_pbr_set(out, np.clip(squeeze(col), 0, 1), T.normalize(squeeze(height)), np.clip(squeeze(rough), 0, 1),
                   metal=np.clip(squeeze(metal), 0, 1), normal_strength=2.5)


# ------------------------------------------------------------------------------------------------
# exterior: welded mesh, cedar shingles, dug soil
# ------------------------------------------------------------------------------------------------


@texture("civic_wire_mesh", size=512, seed=9231, kind="pbr_alpha")
def civic_wire_mesh(size: int, seed: int, out) -> None:
    """Welded square wire mesh (parcel cage panels), alpha cut-out: 20 squares across the tile -> 1 tile =
    0.5 m (25 mm mesh). Galvanised grey with rust at the welds."""
    xx, yy = _grid(size)
    s = size / 20.0
    dx = np.abs(((xx + 0.5) % s) - s / 2)
    dy = np.abs(((yy + 0.5) % s) - s / 2)
    rad = 1.8
    wire_x = np.clip((rad - (s / 2 - dx)) + 0.5, 0, 1)
    wire_y = np.clip((rad - (s / 2 - dy)) + 0.5, 0, 1)
    alpha = np.maximum(wire_x, wire_y)
    hx = np.sqrt(np.clip(1.0 - ((s / 2 - dx) / rad) ** 2, 0, 1))
    hy = np.sqrt(np.clip(1.0 - ((s / 2 - dy) / rad) ** 2, 0, 1))
    h = np.maximum(hx * 0.8, hy)
    weld = np.exp(-(((s / 2 - dx) / 2.5) ** 2 + ((s / 2 - dy) / 2.5) ** 2))
    rust = np.clip(T.smoothstep(0.55, 0.85, T.spectral(size, 1.5, seed)) * 0.7 + weld * 0.5, 0, 1)
    alb = _fill(size, size, "#a3a6a4") * (0.75 + 0.3 * h[..., None])
    alb = T.mix(alb, _fill(size, size, "#7b4a2a"), rust * 0.6)
    T.save_pbr_set(out, np.clip(alb, 0, 1), np.clip(h + 0.3 * weld, 0, 1), np.clip(0.45 + 0.4 * rust, 0, 1),
                   metal=np.clip(0.8 * (1 - rust), 0, 1), normal_strength=3.0, ao_strength=0.3, alpha=alpha)


@texture("civic_shingle", size=1024, seed=9241)
def civic_shingle(size: int, seed: int, out) -> None:
    """Weathered cedar shingles (steeple spire): 8 courses per tile (1 tile ~ 1.2 m), staggered random
    widths, silver-grey weathering with brown undertone, split shingles, moss in the butt lines (V up the
    roof = image up)."""
    r = T.rng(seed)
    courses = 8
    ch = size // courses
    col = np.zeros((size, size, 3), np.float32)
    h = np.zeros((size, size), np.float32)
    xx, yy = _grid(size)
    grain = T.spectral(size, 1.0, seed + 1, anisotropy=(30.0, 1.0))
    for c in range(courses):
        y0 = c * ch
        x = r.uniform(0, size)
        edges = []
        while len(edges) < 40:
            edges.append(x % size)
            x += r.uniform(size * 0.05, size * 0.13)
            if x - edges[0] >= size - size * 0.04:
                break
        edges = sorted(edges)
        for i, e0 in enumerate(edges):
            e1 = edges[(i + 1) % len(edges)] + (size if i == len(edges) - 1 else 0)
            tone = r.uniform(0.0, 1.0)
            base = T.mix(_col("#857a6c")[0, 0], _col("#6a5644")[0, 0], np.float32(tone))
            sl_x = (np.arange(int(e0), int(e1)) % size)
            sub = (slice(y0, y0 + ch), sl_x)
            t = (yy[y0:y0 + ch, :1] - y0) / ch  # 0 at the top of the course (thin) .. 1 at the butt
            shade = 0.75 + 0.3 * t
            blk = np.ones((ch, len(sl_x), 3), np.float32) * base[None, None, :] * shade[..., None]
            col[y0:y0 + ch][:, sl_x] = blk
            h[y0:y0 + ch][:, sl_x] = 0.2 + 0.8 * t
            gap = np.zeros((ch, len(sl_x)), np.float32)
            gap[:, :2] = 1.0
            col[y0:y0 + ch][:, sl_x] *= (1.0 - 0.7 * gap)[..., None]
            h[y0:y0 + ch][:, sl_x] -= gap * 0.5
            if r.random() < 0.12:
                sx = int(r.uniform(4, max(5, len(sl_x) - 4)))
                col[y0 + ch // 3:y0 + ch, sl_x[sx:sx + 2]] *= 0.3
    col *= (0.85 + 0.2 * grain[..., None])
    butt = ((yy % ch) > ch - 6).astype(np.float32)
    moss = butt * T.smoothstep(0.5, 0.8, T.spectral(size, 1.5, seed + 2))
    col = T.mix(col, _fill(size, size, "#4f5a2c"), moss * 0.7)
    T.save_pbr_set(out, np.clip(col, 0, 1), T.normalize(h + 0.2 * grain), np.clip(0.8 + 0.1 * grain, 0, 1), normal_strength=2.5)


@texture("civic_soil", size=512, seed=9251)
def civic_soil(size: int, seed: int, out) -> None:
    """Freshly dug grave soil: crumbly dark loam in small clods, pale clay smears, pebbles, root threads."""
    f1, f2, cid = T.worley(size, 1400, seed)
    edge = T.smoothstep(0.0, 2.5, f2 - f1)
    tone = (np.sin(cid * 3.1) * 4375.85) % 1.0
    grain = T.spectral(size, 0.35, seed + 6)
    big = T.spectral(size, 1.8, seed + 1)
    t = T.normalize(0.35 * tone + 0.35 * big + 0.3 * grain)
    col = T.gradient(t, [(0.0, "#211a14"), (0.45, "#33281e"), (0.8, "#4a3a29"), (1.0, "#665036")])
    col *= (0.82 + 0.18 * edge)[..., None]
    clay = T.smoothstep(0.78, 0.92, T.spectral(size, 1.3, seed + 2, anisotropy=(3.0, 1.0)))
    col = T.mix(col, _fill(size, size, "#7f6b4e"), clay * 0.45)
    pf1, _, _ = T.worley(size, 600, seed + 3)
    peb = np.clip(1.0 - pf1 / 2.5, 0, 1) * T.smoothstep(0.72, 0.86, T.spectral(size, 0.5, seed + 4))
    col = T.mix(col, _fill(size, size, "#86827a"), peb * 0.75)
    roots = _scratches(size, seed + 5, 40, (20, 70), width=0.8)
    col = T.mix(col, _fill(size, size, "#5e4733"), roots * 0.5)
    h = T.normalize(0.4 * edge + 0.4 * grain + 0.3 * big + 0.5 * peb + 0.2 * roots)
    T.save_pbr_set(out, np.clip(col, 0, 1), h, np.clip(0.9 + 0.06 * grain - 0.2 * peb, 0, 1), normal_strength=3.0)
