"""UI textures (import_kind "ui": lossless, no mip-maps): paper, canvas, the tether wrist-device
screen + bezel, map paper and full-screen overlays (vignette, blood, frost).

Screen overlays are authored at 2048 x 1024 (stretch to the viewport); alpha is straight and colour
is bled under transparent pixels. The tether bezel's transparent screen aperture spans
x 0.135..0.865, y 0.12..0.80 of the texture (see ui_tether_bezel docstring)."""
from __future__ import annotations

import pathlib

import numpy as np
from scipy import ndimage

from .. import texlib as T
from ..registry import texture


# --------------------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------------------

def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed & 0xFFFFFFFF)


def _ss(e0, e1, x):
    return T.smoothstep(e0, e1, x)


def _hex(h: str) -> np.ndarray:
    return T.hex_rgb(h).astype(np.float32)


def _noise(h: int, w: int, beta: float, seed: int, fmin: float = 1.0, fmax: float | None = None,
           aniso=(1.0, 1.0)) -> np.ndarray:
    """Rectangular 1/f^beta noise (0..1), periodic in both axes (frequencies per canvas)."""
    r = _rng(seed)
    fy = np.fft.fftfreq(h)[:, None] * h / aniso[1]
    fx = np.fft.fftfreq(w)[None, :] * w / aniso[0]
    f = np.sqrt((fx * h / w) ** 2 + fy * fy)
    f[0, 0] = 1.0
    amp = 1.0 / np.power(f, beta)
    amp[f < fmin] = 0.0
    if fmax is not None:
        amp[f > fmax] = 0.0
    amp[0, 0] = 0.0
    out = np.real(np.fft.ifft2(amp * np.exp(1j * r.uniform(0, 2 * np.pi, (h, w)))))
    return T.normalize(out).astype(np.float32)


def _noise1(count: int, beta: float, seed: int, fmin: float = 1.0) -> np.ndarray:
    """1-D 1/f^beta noise (0..1), periodic over `count` samples."""
    r = _rng(seed)
    f = np.abs(np.fft.fftfreq(count) * count)
    f[0] = 1.0
    amp = 1.0 / np.power(f, beta)
    amp[f < fmin] = 0.0
    amp[0] = 0.0
    out = np.real(np.fft.ifft(amp * np.exp(1j * r.uniform(0, 2 * np.pi, count))))
    return T.normalize(out).astype(np.float32)


def _blur(a, s, mode="nearest"):
    if a.ndim == 3:
        return np.stack([ndimage.gaussian_filter(a[..., c], s, mode=mode) for c in range(a.shape[2])], -1)
    return ndimage.gaussian_filter(a, s, mode=mode)


def _grid(h: int, w: int):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    return xx + 0.5, yy + 0.5


def _bleed(rgb: np.ndarray, a: np.ndarray) -> np.ndarray:
    out = rgb.copy()
    known = (a > 0.004).astype(np.float32)
    filled = known.copy()
    acc = rgb * known[..., None]
    for s in (2, 6, 18, 54):
        wsum = _blur(known, s)
        est = _blur(acc, s) / np.maximum(wsum, 1e-6)[..., None]
        take = (filled < 0.5) & (wsum > 1e-4)
        out[take] = est[take]
        filled[take] = 1.0
    if (filled < 0.5).any():
        mean = (rgb * known[..., None]).sum((0, 1)) / max(known.sum(), 1.0)
        out[filled < 0.5] = mean
    return out


def _save(out, rgb: np.ndarray, a: np.ndarray | None = None) -> None:
    path = pathlib.Path(str(out) + ".png")
    rgb = np.clip(rgb, 0, 1).astype(np.float32)
    if a is None:
        T.save_rgb(path, rgb)
    else:
        a = np.clip(a, 0, 1).astype(np.float32)
        T.save_rgba(path, np.concatenate([_bleed(rgb, a), a[..., None]], -1))


def _paper_base(h: int, w: int, seed: int, tint: str = "#e7dfca", age: float = 0.5) -> np.ndarray:
    """Off-white paper: fibre texture, mottling, yellowing toward the edges, foxing."""
    xx, yy = _grid(h, w)
    fib = _noise(h, w, 0.9, seed + 1, aniso=(1.0, 3.0))
    fib2 = _noise(h, w, 0.6, seed + 2)
    mott = _noise(h, w, 2.0, seed + 3)
    col = np.ones((h, w, 3), np.float32) * _hex(tint)[None, None]
    col = col * (0.965 + 0.04 * fib + 0.025 * fib2)[..., None]
    col = col * (0.97 + 0.05 * mott)[..., None]
    ex = np.minimum(xx, w - xx) / w
    ey = np.minimum(yy, h - yy) / h
    edge = np.clip(1 - np.minimum(ex, ey) / 0.12, 0, 1) ** 2
    yell = np.clip(edge * age + 0.15 * age * _ss(0.4, 0.8, mott), 0, 1)
    col = T.lerp(col, col * _hex("#d9c39a")[None, None] / _hex(tint)[None, None], yell[..., None])
    # foxing spots
    r = _rng(seed + 4)
    sp = np.zeros((h, w), np.float32)
    for _ in range(int(40 * age)):
        cx, cy = r.random() * w, r.random() * h
        rad = 1.5 + 6 * r.random() ** 3
        d = np.hypot(xx - cx, yy - cy)
        sp = np.maximum(sp, np.exp(-(d / rad) ** 2) * (0.3 + 0.5 * r.random()))
    col = T.lerp(col, _hex("#a07a4a")[None, None], (sp * 0.5)[..., None])
    return col


def _stain_ring(h, w, cx, cy, rad, seed, strength=0.3, partial=1.0, colour="#8a5a2a"):
    """Coffee ring: darker rim, faint interior, broken arc."""
    xx, yy = _grid(h, w)
    wx, wy = _noise(h, w, 2.2, seed + 1), _noise(h, w, 2.2, seed + 2)
    d = np.hypot(xx - cx + (wx - 0.5) * rad * 0.15, yy - cy + (wy - 0.5) * rad * 0.15) / rad
    th = np.arctan2(yy - cy, xx - cx)
    arc = _ss(-0.2, 0.3, np.cos(th - seed) + partial - 1.0) if partial < 1 else 1.0
    rim = np.exp(-((d - 1.0) / 0.025) ** 2) * arc
    fill = _ss(1.0, 0.92, d) * 0.25
    return np.clip(rim + fill, 0, 1) * strength, _hex(colour)


def _crease(h, w, x0, y0, x1, y1, width=3.0, finite=False):
    """Fold crease: (line, shade) with shade = light side (+) / dark side (-). finite=True limits the
    crease to the segment x0,y0 -> x1,y1 with soft ends (crumples); otherwise it spans the sheet."""
    xx, yy = _grid(h, w)
    dx, dy = x1 - x0, y1 - y0
    L = np.hypot(dx, dy)
    sd = ((xx - x0) * dy - (yy - y0) * dx) / L
    line = np.exp(-(sd / width) ** 2)
    shade = np.tanh(sd / (width * 2.0)) * np.exp(-(sd / (width * 6)) ** 2)
    if finite:
        al = ((xx - x0) * dx + (yy - y0) * dy) / (L * L)
        m = _ss(-0.05, 0.25, al) * _ss(1.05, 0.75, al)
        line, shade = line * m, shade * m
    return line, shade


# --------------------------------------------------------------------------------------------------
# Paper
# --------------------------------------------------------------------------------------------------

@texture("ui_paper_page", size=1024, seed=9101, kind="single", import_kind="ui")
def ui_paper_page(size: int, seed: int, out) -> None:
    """Aged notebook / manual page (1024 x 1448): fibres, yellowed edges, foxing, a coffee ring and a
    water tide line, a soft horizontal fold, grubby thumb smudges, slightly worn deckle edges."""
    w, h = size, int(round(size * 1.41421356))
    xx, yy = _grid(h, w)
    col = _paper_base(h, w, seed, age=0.55)
    s, c = _stain_ring(h, w, w * 0.78, h * 0.86, w * 0.11, seed + 10, 0.28, partial=0.7)
    col = T.lerp(col, col * c[None, None] / 0.85, s[..., None] * 0.6)
    tide = _noise(h, w, 2.4, seed + 11)
    wd = np.hypot((xx - w * 0.1) / (w * 0.35), (yy - h * 0.08) / (h * 0.2))
    wd = wd + (tide - 0.5) * 0.4
    tl = np.exp(-((wd - 1.0) / 0.02) ** 2) * 0.35 + _ss(1.0, 0.8, wd) * 0.08
    col = T.lerp(col, _hex("#b89a66")[None, None], tl[..., None])
    line, shade = _crease(h, w, 0, h * 0.5 + 6, w, h * 0.5 - 4, 2.5)
    col = col * (1 - 0.06 * line)[..., None] * (1 + 0.035 * shade)[..., None]
    for (tx, ty) in ((0.92, 0.94), (0.08, 0.96)):
        d = np.hypot((xx - w * tx) / (w * 0.06), (yy - h * ty) / (h * 0.035))
        smudge = np.exp(-d ** 2) * _noise(h, w, 0.9, seed + 12) * 0.25
        col = T.lerp(col, _hex("#6a6258")[None, None], smudge[..., None])
    edge_n = _noise(h, w, 1.0, seed + 13)
    ed = np.minimum(np.minimum(xx, w - xx), np.minimum(yy, h - yy))
    a = _ss(0.5, 2.5 + 3 * edge_n, ed)
    col = col * (1 - 0.1 * _ss(14, 0, ed))[..., None]
    _save(out, col, a)


@texture("ui_paper_note", size=1024, seed=9102, kind="single", import_kind="ui")
def ui_paper_note(size: int, seed: int, out) -> None:
    """Torn sheet of lined notebook paper: blue rules, red margin, ragged torn top edge with fibres,
    a few crumple creases and stains."""
    n = size
    r = _rng(seed)
    xx, yy = _grid(n, n)
    col = _paper_base(n, n, seed, tint="#ece6d6", age=0.35)
    rule = 34.0
    ry = (yy - 140) % rule
    rules = np.exp(-((np.minimum(ry, rule - ry)) / 0.9) ** 2) * (yy > 120)
    col = T.lerp(col, _hex("#7e9ec4")[None, None], (rules * 0.55 * (0.8 + 0.2 * _noise(n, n, 1.0, seed + 1)))[..., None])
    margin = np.exp(-((xx - 150) / 1.1) ** 2)
    col = T.lerp(col, _hex("#c46a6a")[None, None], (margin * 0.6)[..., None])
    # crumple creases
    for _ in range(9):
        x0, y0 = r.random() * n, r.random() * n
        a0 = r.random() * np.pi
        L = 90 + 260 * r.random()
        line, shade = _crease(n, n, x0, y0, x0 + np.cos(a0) * L, y0 + np.sin(a0) * L, 1.2 + 2 * r.random(), finite=True)
        col = col * (1 + 0.05 * shade)[..., None] * (1 - 0.035 * line)[..., None]
    s, c = _stain_ring(n, n, n * 0.25, n * 0.72, n * 0.13, seed + 5, 0.22, partial=0.55)
    col = T.lerp(col, col * c[None, None] / 0.85, s[..., None] * 0.6)
    # torn top edge: ragged profile + fibrous fringe
    prof = 30 + 34 * _noise1(n, 1.5, seed + 6) + 7 * _noise1(n, 0.7, seed + 7)
    tear = yy - prof[None, :]
    fringe = _ss(-6, 0, tear) * _ss(0.5, 0.8, _noise(n, n, 0.5, seed + 8, aniso=(1.0, 0.25)))
    a = np.maximum(_ss(-0.5, 1.5, tear), fringe * 0.9)
    torn_white = _ss(10, 0, tear) * (tear > -6)
    col = T.lerp(col, _hex("#f4f1e8")[None, None], (torn_white * 0.7)[..., None])
    side = np.minimum(np.minimum(xx, n - xx), n - yy)
    a = a * _ss(0.5, 2.5, side)
    _save(out, col, a)


@texture("ui_canvas", size=1024, seed=9103, kind="single", import_kind="ui")
def ui_canvas(size: int, seed: int, out) -> None:
    """Tileable heavy cotton duck canvas close-up (salvage roll): plain weave, uneven threads, faded
    olive-khaki dye, grime, worn and stained areas. 48 threads per tile each way."""
    n = size
    threads = 48
    p = n / threads
    xx, yy = _grid(n, n)
    jit_x = (_noise(n, n, 2.0, seed + 1, fmin=1, fmax=40) - 0.5) * 1.6
    jit_y = (_noise(n, n, 2.0, seed + 2, fmin=1, fmax=40) - 0.5) * 1.6
    u = (xx + jit_x) / p
    v = (yy + jit_y) / p
    iu, iv = np.floor(u), np.floor(v)
    fu, fv = u - iu, v - iv
    warp_on_top = ((iu + iv) % 2) == 0
    thick_u = 0.8 + 0.25 * _noise(n, n, 1.6, seed + 3, aniso=(1.0, 0.05))
    thick_v = 0.8 + 0.25 * _noise(n, n, 1.6, seed + 4, aniso=(0.05, 1.0))
    prof_warp = np.clip(1 - ((fu - 0.5) / (0.5 * thick_u)) ** 2, 0, 1) ** 0.5
    prof_weft = np.clip(1 - ((fv - 0.5) / (0.5 * thick_v)) ** 2, 0, 1) ** 0.5
    arch_warp = np.sin(np.pi * fv) ** 0.6
    arch_weft = np.sin(np.pi * fu) ** 0.6
    h_warp = prof_warp * (0.5 + 0.5 * arch_warp * warp_on_top + 0.15 * (~warp_on_top))
    h_weft = prof_weft * (0.5 + 0.5 * arch_weft * (~warp_on_top) + 0.15 * warp_on_top)
    top_is_warp = h_warp >= h_weft
    hgt = np.maximum(h_warp, h_weft)
    fib = _noise(n, n, 0.7, seed + 5)
    twist = np.where(top_is_warp, np.sin((v * 7 + u * 2) * np.pi * 2), np.sin((u * 7 + v * 2) * np.pi * 2))
    base = np.ones((n, n, 3), np.float32) * _hex("#8b8566")[None, None]
    tone = np.where(top_is_warp, 1.0, 0.94)
    col = base * (tone * (0.88 + 0.12 * fib) * (0.97 + 0.03 * twist))[..., None]
    gy, gx = np.gradient(_blur(hgt, 0.6, "wrap"))
    shade = np.clip(1 + (-gx * 0.6 - gy * 0.8) * 3.0, 0.6, 1.3)
    col = col * (0.62 + 0.38 * hgt)[..., None] * shade[..., None]
    fade = _noise(n, n, 2.2, seed + 6)
    col = T.lerp(col, col * 1.18 + 0.02, (_ss(0.6, 0.85, fade) * 0.5)[..., None])
    grime = _ss(0.55, 0.85, _noise(n, n, 1.8, seed + 7)) * 0.35
    col = T.lerp(col, _hex("#3e3a2c")[None, None], grime[..., None])
    stain = _ss(0.72, 0.8, _noise(n, n, 2.0, seed + 8)) * 0.3
    col = T.lerp(col, _hex("#5a4632")[None, None], stain[..., None])
    _save(out, col)


# --------------------------------------------------------------------------------------------------
# Tether device
# --------------------------------------------------------------------------------------------------

@texture("ui_tether_screen", size=512, seed=9201, kind="single", import_kind="ui")
def ui_tether_screen(size: int, seed: int, out) -> None:
    """Dim green monochrome LCD background: pixel grid, scanlines, uneven backlight, vignette."""
    n = size
    xx, yy = _grid(n, n)
    base = _hex("#0b1d10")
    glow = np.exp(-(((xx - n * 0.5) / (n * 0.6)) ** 2 + ((yy - n * 0.45) / (n * 0.55)) ** 2))
    uneven = _noise(n, n, 2.0, seed + 1)
    col = np.ones((n, n, 3), np.float32) * base[None, None]
    col = col * (0.75 + 0.5 * glow + 0.15 * (uneven - 0.5))[..., None]
    gx = ((xx - 0.5) % 4) < 1.0
    gyl = ((yy - 0.5) % 4) < 1.0
    col = col * np.where(gx | gyl, 0.72, 1.0)[..., None]
    scan = 0.94 + 0.06 * np.sin(yy * np.pi)
    col = col * scan[..., None]
    bleed = _hex("#163a1e") * 0.35
    col = col + bleed[None, None] * (glow * 0.4)[..., None]
    vig = _ss(0.75, 0.3, np.hypot((xx - n / 2) / (n / 2), (yy - n / 2) / (n / 2)))
    col = col * (0.55 + 0.45 * vig)[..., None]
    _save(out, col)


@texture("ui_tether_bezel", size=1024, seed=9202, kind="single", import_kind="ui")
def ui_tether_bezel(size: int, seed: int, out) -> None:
    """Rugged wrist-device bezel (baked light from the upper left): rounded rubberised housing,
    recessed screen lip, four screws, a status LED, two rubber buttons, scuffs and grime.
    Transparent outside the housing and in the screen aperture x 0.135..0.865, y 0.12..0.80."""
    n = size
    r = _rng(seed)
    xx, yy = _grid(n, n)

    def rrect(x0, y0, x1, y1, rad):
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        hx, hy = (x1 - x0) / 2 - rad, (y1 - y0) / 2 - rad
        qx = np.abs(xx - cx) - hx
        qy = np.abs(yy - cy) - hy
        return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - rad

    outer = rrect(n * 0.03, n * 0.04, n * 0.97, n * 0.96, n * 0.11)
    screen = rrect(n * 0.135, n * 0.12, n * 0.865, n * 0.80, n * 0.035)
    lip = rrect(n * 0.115, n * 0.1, n * 0.885, n * 0.82, n * 0.05)
    a = _ss(1.0, -1.0, outer) * _ss(-1.0, 1.0, screen)
    # height: rounded housing edge, flat face, recessed lip toward the screen
    hgt = np.clip(-outer / (n * 0.035), 0, 1) ** 0.5
    hgt = hgt - 0.35 * _ss(2.0, -6.0, lip) * _ss(-n * 0.02, 0, -screen)
    stip = _noise(n, n, 0.3, seed + 1)
    hgt = hgt + 0.012 * stip
    # screws and buttons
    screws = [(0.075, 0.08), (0.925, 0.08), (0.075, 0.92), (0.925, 0.92)]
    sc = np.zeros((n, n), np.float32)
    slot = np.zeros((n, n), np.float32)
    for sx, sy in screws:
        d = np.hypot(xx - sx * n, yy - sy * n)
        head = _ss(n * 0.026, n * 0.022, d)
        sc = np.maximum(sc, head)
        ang = r.random() * np.pi
        u = (xx - sx * n) * np.cos(ang) + (yy - sy * n) * np.sin(ang)
        v = -(xx - sx * n) * np.sin(ang) + (yy - sy * n) * np.cos(ang)
        cross = ((np.abs(u) < n * 0.004) | (np.abs(v) < n * 0.004)) & (d < n * 0.016)
        slot = np.maximum(slot, cross.astype(np.float32))
        hgt = hgt + 0.25 * head * np.clip(1 - (d / (n * 0.026)) ** 2, 0, 1) ** 0.5 - 0.2 * cross
    btn = np.zeros((n, n), np.float32)
    for bx in (0.36, 0.64):
        d = rrect(n * (bx - 0.07), n * 0.855, n * (bx + 0.07), n * 0.905, n * 0.02)
        b = _ss(1.0, -1.0, d)
        btn = np.maximum(btn, b)
        hgt = hgt + 0.18 * b * np.clip(-d / (n * 0.012), 0, 1) ** 0.5
    led_d = np.hypot(xx - n * 0.5, yy - n * 0.07)
    led = _ss(n * 0.012, n * 0.009, led_d)
    gy, gx = np.gradient(_blur(hgt, 1.2))
    k = 140.0
    nx, ny = -gx * k, -gy * k
    inv = 1 / np.sqrt(nx * nx + ny * ny + 1)
    L = np.array([-0.5, -0.6, 0.62])
    L /= np.linalg.norm(L)
    ndl = np.clip((nx * L[0] + ny * L[1] + L[2]) * inv, 0, 1)
    base = np.ones((n, n, 3), np.float32) * _hex("#2b2d2b")[None, None]
    base = base * (0.9 + 0.12 * stip)[..., None]
    base = T.lerp(base, _hex("#5d5e58")[None, None], (sc * 0.9)[..., None])
    base = base * (1 - 0.8 * slot)[..., None]
    base = T.lerp(base, _hex("#1c1d1c")[None, None], (btn * 0.8)[..., None])
    wear = _ss(0.6, 0.85, _noise(n, n, 1.0, seed + 2)) * np.exp(-((outer + n * 0.012) / (n * 0.01)) ** 2)
    base = T.lerp(base, _hex("#6a6a62")[None, None], (wear * 0.6)[..., None])
    scratches = _ss(0.93, 0.97, _noise(n, n, 0.8, seed + 3, aniso=(6.0, 1.0))) * 0.25
    base = T.lerp(base, _hex("#7a7a72")[None, None], scratches[..., None])
    grime = _ss(-n * 0.03, 0, -lip) * _ss(-n * 0.003, n * 0.003, lip) * 0.5
    base = T.lerp(base, _hex("#1a1612")[None, None], grime[..., None])
    col = base * (0.45 + 0.75 * ndl)[..., None]
    col = col + np.clip(ndl - 0.9, 0, 1)[..., None] * 0.6
    col = T.lerp(col, _hex("#ffb23a")[None, None], led[..., None])
    col = col + _hex("#ff9a20")[None, None] * (np.exp(-(led_d / (n * 0.02)) ** 2) * 0.25)[..., None]
    _save(out, col, a)


# --------------------------------------------------------------------------------------------------
# Map paper
# --------------------------------------------------------------------------------------------------

@texture("ui_map_paper", size=2048, seed=9301, kind="single", import_kind="ui")
def ui_map_paper(size: int, seed: int, out) -> None:
    """Topographic map paper base: aged paper, faint printed 1 km grid (every 1/8 of the sheet),
    4 x 3 fold creases worn at the crossings, stains. The map content is drawn by the game."""
    n = size
    xx, yy = _grid(n, n)
    col = _paper_base(n, n, seed, tint="#e6dfc9", age=0.45)
    g = n / 8
    gx = np.minimum((xx) % g, g - (xx % g))
    gyy = np.minimum((yy) % g, g - (yy % g))
    grid = np.maximum(np.exp(-(gx / 0.9) ** 2), np.exp(-(gyy / 0.9) ** 2))
    col = T.lerp(col, _hex("#7d8fa0")[None, None], (grid * 0.32)[..., None])
    for i in range(1, 4):
        line, shade = _crease(n, n, n * i / 4, 0, n * i / 4 + 3, n, 2.2)
        col = col * (1 + 0.05 * shade)[..., None] * (1 - 0.07 * line)[..., None]
    for j in range(1, 3):
        line, shade = _crease(n, n, 0, n * j / 3, n, n * j / 3 - 4, 2.2)
        col = col * (1 + 0.05 * shade)[..., None] * (1 - 0.07 * line)[..., None]
    wear = np.zeros((n, n), np.float32)
    for i in range(1, 4):
        for j in range(1, 3):
            d = np.hypot(xx - n * i / 4, yy - n * j / 3)
            wear = np.maximum(wear, np.exp(-(d / 28) ** 2))
    col = T.lerp(col, _hex("#f0ead8")[None, None], (wear * 0.45 * _noise(n, n, 0.8, seed + 1))[..., None])
    s, c = _stain_ring(n, n, n * 0.68, n * 0.3, n * 0.06, seed + 5, 0.25, partial=0.8)
    col = T.lerp(col, col * c[None, None] / 0.85, s[..., None] * 0.6)
    water = _ss(0.72, 0.78, _noise(n, n, 2.4, seed + 6)) * 0.12
    col = T.lerp(col, _hex("#b09a70")[None, None], water[..., None])
    _save(out, col)


# --------------------------------------------------------------------------------------------------
# Overlays
# --------------------------------------------------------------------------------------------------

@texture("ui_vignette", size=1024, seed=9401, kind="single", import_kind="ui")
def ui_vignette(size: int, seed: int, out) -> None:
    """Radial damage vignette: dark arterial red, organic irregular inner edge, heavier corners."""
    n = size
    xx, yy = _grid(n, n)
    u = (xx - n / 2) / (n / 2)
    v = (yy - n / 2) / (n / 2)
    d = np.hypot(u, v)
    th = np.arctan2(v, u)
    nz = _noise(n, n, 1.8, seed + 1)
    rr = d * (1 + 0.12 * (nz - 0.5)) + 0.04 * np.sin(5 * th + 1.3)
    a = _ss(0.55, 1.15, rr) ** 1.4
    col = T.lerp(np.ones((n, n, 3), np.float32) * _hex("#5a0606")[None, None], _hex("#160000")[None, None],
                 _ss(0.8, 1.3, rr)[..., None])
    _save(out, col, a)


@texture("ui_blood_overlay", size=2048, seed=9402, kind="single", import_kind="ui")
def ui_blood_overlay(size: int, seed: int, out) -> None:
    """Low-health blood frame (2048 x 1024): out-of-focus splatters and smears crowding the screen
    edges and corners, a few runs from the top, clear centre."""
    w, h = size, size // 2
    r = _rng(seed)
    xx, yy = _grid(h, w)
    u = (xx - w / 2) / (w / 2)
    v = (yy - h / 2) / (h / 2)
    edge = np.clip(np.maximum(np.abs(u) ** 2.2, np.abs(v) ** 2.2) * 1.1 + (u * u + v * v) * 0.25 - 0.35, 0, 1)
    Tk = np.zeros((h, w), np.float32)
    cnt = 900
    px = r.random(cnt * 4) * w
    py = r.random(cnt * 4) * h
    pe = edge[py.astype(int), px.astype(int)]
    keep = r.random(cnt * 4) < pe ** 1.5
    px, py = px[keep][:cnt], py[keep][:cnt]
    rad = 2 + 40 * r.random(px.size) ** 4
    for x0, y0, rd in zip(px, py, rad):
        # irregular, elongated drops with a tail and a satellite (blood hitting the lens)
        ang = r.random() * 2 * np.pi
        el = 1.0 + 1.6 * r.random() ** 2
        k1, k2 = r.integers(3, 7), r.integers(9, 17)
        p1, p2 = r.random() * 6.28, r.random() * 6.28
        ext = rd * (el + 2.5)
        x_lo, x_hi = int(max(0, x0 - ext)), int(min(w, x0 + ext + 1))
        y_lo, y_hi = int(max(0, y0 - ext)), int(min(h, y0 + ext + 1))
        if x_hi <= x_lo or y_hi <= y_lo:
            continue
        sx, sy = xx[y_lo:y_hi, x_lo:x_hi] - x0, yy[y_lo:y_hi, x_lo:x_hi] - y0
        uu = sx * np.cos(ang) + sy * np.sin(ang)
        vv = -sx * np.sin(ang) + sy * np.cos(ang)
        th = np.arctan2(vv, uu / el)
        rr = rd * (1 + 0.18 * np.sin(k1 * th + p1) + 0.07 * np.sin(k2 * th + p2))
        d = np.hypot(uu / el, vv) / rr
        drop = np.clip(1 - d * d, 0, 1) ** 0.5
        tl = rd * el * 1.6
        tu = np.clip((uu - rd * el * 0.6) / tl, 0, 1)
        tail = (uu > 0) * _ss(rd * 0.45 * (1 - tu) + 0.6, rd * 0.45 * (1 - tu) - 0.4, np.abs(vv)) * (1 - tu) * 0.8
        Tk[y_lo:y_hi, x_lo:x_hi] = np.maximum(Tk[y_lo:y_hi, x_lo:x_hi], np.maximum(drop, tail))
    smear = _ss(0.45, 0.75, _noise(h, w, 1.6, seed + 1, aniso=(3.0, 1.0))) * edge
    Tk = np.maximum(Tk, smear * 0.8)
    # a few runs down from the top edge
    for _ in range(9):
        x0 = r.random() * w
        L = h * (0.1 + 0.3 * r.random())
        wd = 3 + 6 * r.random()
        t = np.clip(yy / L, 0, 1)
        run = (yy < L) * _ss(wd + 1, wd - 1, np.abs(xx - x0 - 6 * np.sin(yy * 0.03))) * (1 - 0.5 * t)
        bulb = _ss(wd * 1.6 + 1, wd * 1.6 - 1, np.hypot(xx - x0 - 6 * np.sin(L * 0.03), yy - L))
        Tk = np.maximum(Tk, np.maximum(run, bulb))
    Tk = _blur(Tk, 2.5)
    Tk = np.maximum(Tk, edge ** 2 * 0.6)
    col = T.lerp(np.ones((h, w, 3), np.float32) * _hex("#7a0c0a")[None, None], _hex("#2a0303")[None, None],
                 _ss(0.2, 1.0, Tk)[..., None])
    col = col * (0.9 + 0.2 * _noise(h, w, 1.5, seed + 2))[..., None]
    a = np.clip(1 - np.exp(-3.5 * Tk), 0, 1) * 0.95
    _save(out, col, a)


@texture("ui_frost_overlay", size=2048, seed=9403, kind="single", import_kind="ui")
def ui_frost_overlay(size: int, seed: int, out) -> None:
    """Cold-screen frost (2048 x 1024): fern-like ice dendrites growing in from the edges and corners
    over a fine crystalline rime, clear centre."""
    w, h = size, size // 2
    r = _rng(seed)
    xx, yy = _grid(h, w)
    u = (xx - w / 2) / (w / 2)
    v = (yy - h / 2) / (h / 2)
    edge = np.clip(np.maximum(np.abs(u) ** 2.5, np.abs(v) ** 2.5) * 1.15 + (u * u + v * v) * 0.3 - 0.3, 0, 1)
    cover = _ss(0.3, 0.7, _noise(h, w, 2.0, seed + 5, fmin=2, fmax=24))
    edge = edge * (0.6 + 0.6 * cover)
    rime = _ss(0.45, 0.9, _noise(h, w, 0.5, seed + 1)) * edge ** 0.8
    rime = np.maximum(rime, edge ** 2.5 * 0.65 * (0.6 + 0.4 * _noise(h, w, 1.2, seed + 6)))
    ferns = np.zeros((h, w), np.float32)
    pts = []

    def grow(x, y, ang, length, depth):
        step = 1.5
        k = int(length / step)
        for i in range(k):
            ang += r.normal(0, 0.08)
            x += np.cos(ang) * step
            y += np.sin(ang) * step
            if not (0 <= x < w and 0 <= y < h):
                return
            pts.append((x, y, max(0.5, 1.6 - depth * 0.45 - i / max(k, 1))))
            if depth < 3 and i % 4 == 2:
                for sgn in (-1, 1):
                    if r.random() < 0.8:
                        grow(x, y, ang + sgn * np.pi / 3, length * (0.22 + 0.12 * r.random()) * (1 - i / k), depth + 1)

    for _ in range(46):
        side = r.integers(0, 4)
        if side == 0:
            x, y = r.random() * w, 0.0
        elif side == 1:
            x, y = r.random() * w, h - 1.0
        elif side == 2:
            x, y = 0.0, r.random() * h
        else:
            x, y = w - 1.0, r.random() * h
        ang = np.arctan2(h / 2 - y, w / 2 - x) + r.normal(0, 0.5)
        grow(x, y, ang, 80 + 260 * r.random() ** 1.5, 0)
    if pts:
        P = np.array(pts, np.float32)
        ix = np.clip(P[:, 0].astype(int), 0, w - 1)
        iy = np.clip(P[:, 1].astype(int), 0, h - 1)
        np.maximum.at(ferns, (iy, ix), P[:, 2] / 1.6)
        ferns = np.maximum(_blur(ferns, 0.7) * 2.6, _blur(ferns, 2.5) * 1.6)
    ferns = np.clip(ferns, 0, 1) * (0.4 + 0.6 * edge ** 0.5)
    i = np.clip(rime * 0.7 + ferns, 0, 1)
    col = T.lerp(np.ones((h, w, 3), np.float32) * _hex("#cfe3f2")[None, None], _hex("#ffffff")[None, None],
                 _ss(0.4, 1.0, i)[..., None])
    a = np.clip(i * 0.9, 0, 1)
    _save(out, col, a)
