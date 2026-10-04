"""Particle / effect textures: smoke + fire flipbooks, embers, sparks, muzzle flashes, rain, splash,
blood spray, dust motes, Bloom spores, dirt / wood chunk atlases, water normals and foam.

Conventions
  * Flipbooks / atlases are row-major (left -> right, top -> bottom), square cells, matching Godot's
    particles_anim_h_frames / v_frames. Every cell fades to alpha 0 well inside its border so
    mip-maps never bleed between frames.
  * RGBA with straight alpha; colour is bled under transparent pixels. For additive blending use
    rgb * a. Lighting baked into chunk sprites comes from the upper left.
  * water_normal_a/b are tileable OpenGL normal maps; water_foam is tileable linear data.
"""
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


def _noise2(n: int, beta: float, seed: int, fmin: float = 1.0, fmax: float | None = None) -> np.ndarray:
    return T.spectral(n, beta, seed, fmin=fmin, fmax=fmax).astype(np.float32)


def _noise3(t: int, h: int, w: int, beta: float, seed: int, tscale: float = 1.0, fmin: float = 1.0,
            fmax: float | None = None) -> np.ndarray:
    """Periodic 3-D 1/f^beta noise (t, h, w) normalised to 0..1. tscale > 1 slows evolution along t."""
    r = _rng(seed)
    ft = np.fft.fftfreq(t)[:, None, None] * t * tscale
    fy = np.fft.fftfreq(h)[None, :, None] * h
    fx = np.fft.fftfreq(w)[None, None, :] * w
    f = np.sqrt(ft * ft + fy * fy + fx * fx)
    f[0, 0, 0] = 1.0
    amp = 1.0 / np.power(f, beta)
    amp[f < fmin] = 0.0
    if fmax is not None:
        amp[f > fmax] = 0.0
    amp[0, 0, 0] = 0.0
    spec = amp * np.exp(1j * r.uniform(0, 2 * np.pi, f.shape))
    out = np.real(np.fft.ifftn(spec)).astype(np.float32)
    out -= out.min()
    out /= max(float(out.max()), 1e-9)
    return out


def _blur(a, s):
    if a.ndim == 3:
        return np.stack([ndimage.gaussian_filter(a[..., c], s, mode="nearest") for c in range(a.shape[2])], -1)
    return ndimage.gaussian_filter(a, s, mode="nearest")


def _grid(n: int):
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    return (xx + 0.5) / n, (yy + 0.5) / n


def _cell_fade(n: int, margin: float = 0.06) -> np.ndarray:
    x, y = _grid(n)
    return (_ss(0, margin, np.minimum(x, 1 - x)) * _ss(0, margin, np.minimum(y, 1 - y))).astype(np.float32)


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


def _atlas(cells: list[np.ndarray], cols: int) -> np.ndarray:
    rows = [np.concatenate(cells[i:i + cols], 1) for i in range(0, len(cells), cols)]
    return np.concatenate(rows, 0)


def _save_rgba(out, rgba: np.ndarray) -> None:
    rgb = _bleed(np.clip(rgba[..., :3], 0, 1).astype(np.float32), rgba[..., 3])
    T.save_rgba(pathlib.Path(str(out) + ".png"), np.concatenate([rgb, np.clip(rgba[..., 3:4], 0, 1)], -1))


def _ramp(t: np.ndarray, stops) -> np.ndarray:
    return T.gradient(np.clip(t, 0, 1), stops).astype(np.float32)


def _light(dens: np.ndarray, dirx: float = -1.0, diry: float = -1.0, steps=(3, 7, 12, 18), k: float = 1.6):
    """Cheap self-shadowing for volumes seen as billboards: density sampled toward the light."""
    acc = np.zeros_like(dens)
    b = _blur(dens, 2.0)
    for s in steps:
        acc += ndimage.shift(b, (-diry * s, -dirx * s), order=1, mode="constant", cval=0.0)
    return np.exp(-k * acc / len(steps))


# --------------------------------------------------------------------------------------------------
# Smoke + fire flipbooks
# --------------------------------------------------------------------------------------------------

@texture("fx_smoke_flipbook", size=2048, seed=6101, kind="single", import_kind="albedo")
def fx_smoke_flipbook(size: int, seed: int, out) -> None:
    """8x8 frames (256 px): a dense billowing puff that rolls outward, rises a little, then thins into
    translucent wisps and dissipates (frame 0 = birth). Self-shadowed, lit from the upper left."""
    frames, n = 64, size // 8
    vol = _noise3(frames, n, n, 2.3, seed, tscale=5.0, fmin=1.5)
    vol2 = _noise3(frames, n, n, 1.7, seed + 1, tscale=3.0, fmin=4.0)
    wx = _noise3(frames, n, n, 2.4, seed + 2, tscale=6.0)
    wy = _noise3(frames, n, n, 2.4, seed + 3, tscale=6.0)
    x, y = _grid(n)
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    cells = []
    for f in range(frames):
        t = f / (frames - 1)
        R = 0.24 + 0.2 * t ** 0.55
        cx, cy = 0.5, 0.56 - 0.08 * t
        warp = 6 + 22 * t
        sx = xx + (wx[f] - 0.5) * 2 * warp
        sy = yy + (wy[f] - 0.5) * 2 * warp
        b1 = ndimage.map_coordinates(vol[f], [sy, sx], order=1, mode="grid-wrap")
        b2 = ndimage.map_coordinates(vol2[f], [sy, sx], order=1, mode="grid-wrap")
        r2 = ((x - cx) ** 2 + ((y - cy) * 1.1) ** 2) / (R * R)
        env = np.exp(-r2 * 1.2)
        billow = 0.55 + 1.1 * (b1 - 0.5) + 0.35 * (b2 - 0.5)
        wisp = 0.15 + 0.55 * t
        dens = np.clip(env * billow * 1.6 - wisp * (1 - env) * 0.6 - 0.08 * t, 0, 1)
        dens = _ss(0.02, 0.75 - 0.25 * t, dens)
        life = _ss(0.0, 0.05, t) * (1 - _ss(0.5, 1.0, t) * 0.97)
        a = np.clip(dens * (0.95 - 0.35 * t), 0, 1) * life * _cell_fade(n, 0.05)
        lit = _light(dens, -0.7, -1.0, steps=(4, 8, 14, 22, 32), k=2.2)
        shade = 0.46 + 0.46 * lit + 0.08 * (b2 - 0.5)
        col = np.stack([shade * 1.0, shade * 0.99, shade * 0.97], -1)
        cells.append(np.concatenate([col, a[..., None]], -1))
    _save_rgba(out, _atlas(cells, 8))


FIRE_RAMP = [(0.0, "#2a0600"), (0.15, "#6e1400"), (0.32, "#b8320a"), (0.5, "#ea6a16"), (0.68, "#ff9c2c"),
             (0.84, "#ffcf6a"), (0.95, "#ffefc0"), (1.0, "#fff8e6")]


@texture("fx_fire_flipbook", size=2048, seed=6102, kind="single", import_kind="albedo")
def fx_fire_flipbook(size: int, seed: int, out) -> None:
    """8x8 seamlessly LOOPING flames (256 px): vertically stretched turbulence (periodic in time and
    scrolled upward by exactly one period per loop) breaks the flame body into licking tongues; a
    hot core at the base, black-body ramp, swaying tips."""
    frames, n = 64, size // 8
    ft = np.fft.fftfreq(frames)[:, None, None] * frames * 4.0
    fy = np.fft.fftfreq(n)[None, :, None] * n * 3.0
    fx = np.fft.fftfreq(n)[None, None, :] * n
    rs = _rng(seed)
    vols = []
    for k, beta in enumerate((1.6, 1.25)):
        f = np.sqrt(ft * ft + fy * fy + fx * fx)
        f[0, 0, 0] = 1.0
        amp = 1.0 / np.power(f, beta)
        amp[f < (2.0 if k == 0 else 5.0)] = 0
        amp[0, 0, 0] = 0
        v = np.real(np.fft.ifftn(amp * np.exp(1j * rs.uniform(0, 2 * np.pi, f.shape)))).astype(np.float32)
        vols.append((v - v.min()) / (v.max() - v.min()))
    sway = _noise3(frames, n, n, 2.4, seed + 3, tscale=4.0)
    x, y = _grid(n)
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    h = 1.0 - y
    cells = []
    for f in range(frames):
        t = f / frames
        scroll = t * n
        sw = (sway[f] - 0.5) * 2
        sx = xx + sw * (4 + 26 * h)
        n1 = ndimage.map_coordinates(vols[0][f], [yy + scroll, sx], order=1, mode="grid-wrap")
        n2 = ndimage.map_coordinates(vols[1][f], [yy + 2 * scroll, sx], order=1, mode="grid-wrap")
        xc = 0.5 + sw * 0.09 * h
        width = (0.25 + 0.1 * (n2 - 0.5)) * (1.0 - h) ** 0.45 + 0.03
        body = 1 - np.abs(x - xc) / width
        I = body * 0.7 - 1.0 * h ** 1.1 + 1.25 * (n1 - 0.5) + 0.45 * (n2 - 0.5) + 0.38
        I = np.clip(I, 0, 1) * _ss(0.0, 0.08, h)
        core = np.clip(1 - np.abs(x - xc) / (width * 0.5), 0, 1) * (1 - _ss(0.05, 0.35, h))
        temp = np.clip(I * (0.75 + 0.35 * core) + 0.25 * core * I, 0, 1)
        col = _ramp(temp, FIRE_RAMP)
        a = _ss(0.02, 0.35, I) * _cell_fade(n, 0.05)
        cells.append(np.concatenate([col, a[..., None]], -1))
    _save_rgba(out, _atlas(cells, 8))


# --------------------------------------------------------------------------------------------------
# Embers, sparks, muzzle flashes
# --------------------------------------------------------------------------------------------------

EMBER_RAMP = [(0.0, "#3a0800"), (0.3, "#a02400"), (0.6, "#ff6a10"), (0.85, "#ffc060"), (1.0, "#fff4d0")]


@texture("fx_embers", size=512, seed=6201, kind="single", import_kind="albedo")
def fx_embers(size: int, seed: int, out) -> None:
    """2x2 atlas of glowing embers: round, motion-streaked, charred flake with glowing rim, tiny cluster."""
    n = size // 2
    r = _rng(seed)
    x, y = _grid(n)
    cells = []
    # 1 round ember
    d = np.hypot(x - 0.5, y - 0.5)
    i = np.exp(-(d / 0.07) ** 2) + 0.35 * np.exp(-(d / 0.2) ** 2)
    cells.append((i, np.clip(i, 0, 1)))
    # 2 streak
    u, v = x - 0.5, y - 0.5
    i = np.exp(-(v / 0.03) ** 2) * np.exp(-(np.maximum(u, 0) / 0.08) ** 2 - (np.minimum(u, 0) / 0.32) ** 2)
    i = i + 0.25 * np.exp(-(v / 0.09) ** 2) * np.exp(-(u / 0.3) ** 2)
    cells.append((i, np.clip(i, 0, 1)))
    # 3 charred flake with glowing edges
    th = np.arctan2(v, u)
    rad = 0.22 * (1 + 0.25 * np.sin(3 * th + 1) + 0.15 * np.sin(5 * th + 2) + 0.08 * np.sin(11 * th))
    inside = _ss(rad + 0.01, rad - 0.01, d)
    edge = np.exp(-((d - rad * 0.85) / 0.03) ** 2) * inside
    crack = _ss(0.75, 0.82, _noise2(n, 1.2, seed + 1)) * inside
    i = np.clip(edge * 0.9 + crack * 0.8, 0, 1)
    flake_col = _ramp(i, EMBER_RAMP) * (0.35 + 0.65 * _ss(0.05, 0.3, i))[..., None] + \
        _hex("#1a1210")[None, None] * (1 - _ss(0.05, 0.3, i))[..., None]
    a3 = np.clip(inside + 0.3 * np.exp(-(d / 0.25) ** 2) * i, 0, 1)
    # 4 tiny cluster
    i4 = np.zeros((n, n), np.float32)
    for _ in range(7):
        px, py = 0.5 + (r.random() - 0.5) * 0.4, 0.5 + (r.random() - 0.5) * 0.4
        s = 0.02 + 0.03 * r.random()
        i4 += np.exp(-(((x - px) ** 2 + (y - py) ** 2) / s ** 2)) * (0.5 + 0.5 * r.random())
    i4 = i4 + 0.2 * np.exp(-(d / 0.25) ** 2)
    out_cells = []
    for k, (ii, aa) in enumerate(cells):
        out_cells.append(np.concatenate([_ramp(np.clip(ii, 0, 1), EMBER_RAMP), (aa * _cell_fade(n))[..., None]], -1))
    out_cells.append(np.concatenate([flake_col, (a3 * _cell_fade(n))[..., None]], -1))
    out_cells.append(np.concatenate([_ramp(np.clip(i4, 0, 1), EMBER_RAMP), (np.clip(i4, 0, 1) * _cell_fade(n))[..., None]], -1))
    _save_rgba(out, _atlas(out_cells, 2))


@texture("fx_spark", size=256, seed=6202, kind="single", import_kind="albedo")
def fx_spark(size: int, seed: int, out) -> None:
    """Single hot spark streak along +X (white core, yellow-orange tail); stretch along velocity."""
    n = size
    x, y = _grid(n)
    u, v = x - 0.62, y - 0.5
    head = np.exp(-(u / 0.05) ** 2 - (v / 0.022) ** 2)
    tail = np.exp(-(v / (0.012 + 0.02 * np.clip(-u, 0, 1))) ** 2) * np.exp(-(np.clip(-u, 0, None) / 0.32) ** 2) * (u < 0.05)
    glow = 0.25 * np.exp(-(u / 0.25) ** 2 - (v / 0.08) ** 2)
    i = np.clip(head * 1.2 + tail * 0.8 + glow, 0, 1)
    col = _ramp(i, [(0.0, "#802000"), (0.35, "#ff7a20"), (0.7, "#ffd070"), (1.0, "#ffffff")])
    a = np.clip(i * 1.3, 0, 1) * _cell_fade(n, 0.04)
    _save_rgba(out, np.concatenate([col, a[..., None]], -1))


MUZZLE_RAMP = [(0.0, "#300800"), (0.25, "#b0300a"), (0.5, "#ff8a20"), (0.75, "#ffd27a"), (1.0, "#fffdf2")]


@texture("fx_muzzle_flash", size=1024, seed=6203, kind="single", import_kind="albedo")
def fx_muzzle_flash(size: int, seed: int, out) -> None:
    """2x2 atlas: two front-view star flashes and two side-view flame cones (pointing +X)."""
    n = size // 2
    r = _rng(seed)
    x, y = _grid(n)
    u, v = x - 0.5, y - 0.5
    d = np.hypot(u, v)
    th = np.arctan2(v, u)
    cells = []
    for k in range(2):
        nz = _noise2(n, 1.3, seed + 10 + k)
        prongs = np.zeros_like(th)
        cnt = 5 if k == 0 else 7
        off = r.random() * 6.28
        for p in range(cnt):
            a0 = off + p * 2 * np.pi / cnt + (r.random() - 0.5) * 0.3
            dth = np.angle(np.exp(1j * (th - a0)))
            L = 0.3 + 0.15 * r.random()
            prongs = np.maximum(prongs, np.exp(-(dth / (0.07 + 0.05 * r.random())) ** 2) * np.clip(1 - d / L, 0, 1))
        core = np.exp(-(d / 0.09) ** 2)
        petals = np.exp(-(d / 0.2) ** 2) * (0.5 + 0.5 * np.cos(th * cnt + off)) * 0.6
        i = np.clip(core * 1.2 + prongs * (0.7 + 0.5 * nz) + petals * (0.6 + 0.6 * nz), 0, 1)
        cells.append(np.concatenate([_ramp(i, MUZZLE_RAMP), (np.clip(i * 1.4, 0, 1) * _cell_fade(n))[..., None]], -1))
    for k in range(2):
        nz = _noise2(n, 1.2, seed + 20 + k)
        uu = x - 0.1
        L = 0.8 - 0.15 * k
        prof = np.clip(uu / L, 0, 1)
        width = 0.03 + 0.17 * prof ** 0.7 * (1 - prof) ** 0.6
        cone = np.exp(-(v / np.maximum(width, 1e-3)) ** 2) * (uu > 0) * (1 - prof) ** 0.4
        lob = np.exp(-((uu - L * 0.35) / 0.18) ** 2 - (v / 0.2) ** 2) * 0.5
        i = np.clip((cone * 1.1 + lob) * (0.65 + 0.6 * nz), 0, 1)
        i = np.maximum(i, np.exp(-((x - 0.1) ** 2 + v ** 2) / 0.004))
        if k == 1:
            smoke = np.exp(-((uu - 0.5) / 0.25) ** 2 - (v / 0.22) ** 2) * _ss(0.4, 0.8, nz) * 0.4
            col = _ramp(i, MUZZLE_RAMP) * (1 - smoke[..., None]) + 0.5 * smoke[..., None]
            a = np.clip(i * 1.4 + smoke, 0, 1)
        else:
            col = _ramp(i, MUZZLE_RAMP)
            a = np.clip(i * 1.4, 0, 1)
        cells.append(np.concatenate([col, (a * _cell_fade(n))[..., None]], -1))
    _save_rgba(out, _atlas(cells, 2))


# --------------------------------------------------------------------------------------------------
# Rain, splash, blood spray
# --------------------------------------------------------------------------------------------------

@texture("fx_rain_streak", size=512, seed=6301, kind="single", import_kind="albedo")
def fx_rain_streak(size: int, seed: int, out) -> None:
    """4x1 atlas (each cell 128 x 512) of motion-blurred rain drops: thin bright core, soft ends.
    Output is 512 x 512 (four 128-px-wide columns)."""
    n = size
    r = _rng(seed)
    cells = []
    yy, xx = np.mgrid[0:n, 0:n // 4].astype(np.float32)
    w = n // 4
    for k in range(4):
        cx = w * (0.5 + (r.random() - 0.5) * 0.1)
        L0, L1 = n * (0.08 + 0.05 * r.random()), n * (0.92 - 0.05 * r.random())
        t = np.clip((yy - L0) / (L1 - L0), 0, 1)
        lean = (r.random() - 0.5) * 6
        dx = xx - cx - lean * t
        width = 1.2 + 1.3 * r.random()
        prof = np.exp(-(dx / width) ** 2)
        ends = _ss(0, 0.15, t) * _ss(1, 0.7, t) * ((yy > L0) & (yy < L1))
        i = prof * ends * (0.6 + 0.4 * np.sin(t * np.pi))
        col = np.stack([0.78 + 0.2 * prof, 0.84 + 0.15 * prof, 0.92 + 0.08 * prof], -1) * np.ones_like(i)[..., None]
        cells.append(np.concatenate([col, (i * 0.85)[..., None]], -1))
    _save_rgba(out, np.concatenate(cells, 1))


@texture("fx_splash", size=1024, seed=6302, kind="single", import_kind="albedo")
def fx_splash(size: int, seed: int, out) -> None:
    """4x4 flipbook (256 px) of a water drop impact seen from the side: crown sheet rises with
    droplets on its rim, collapses, droplets arc away and fall, a ripple spreads."""
    frames, n = 16, size // 4
    r = _rng(seed)
    x, y = _grid(n)
    ground = 0.78
    nd = 18
    ang = np.linspace(0.12, np.pi - 0.12, nd) + (r.random(nd) - 0.5) * 0.15
    spd = 0.6 + 0.6 * r.random(nd)
    dsz = 0.008 + 0.012 * r.random(nd)
    cells = []
    for f in range(frames):
        t = (f + 0.5) / frames
        i = np.zeros((n, n), np.float32)
        hl = np.zeros((n, n), np.float32)
        # crown: thin sheet (ellipse ring seen from the side) rising then collapsing
        ch = 0.22 * np.sin(np.pi * np.clip(t * 1.6, 0, 1)) ** 0.8
        cw = 0.08 + 0.22 * t ** 0.7
        if ch > 0.01:
            u = (x - 0.5) / cw
            band = np.exp(-((np.abs(u) - 1.0) / 0.18) ** 2) * (np.abs(u) < 1.25)
            hgt = ground - ch * (1 - 0.3 * u ** 2)
            sheet = band * (y > hgt) * (y < ground) * (0.35 + 0.65 * _ss(ground, hgt, y))
            back = np.exp(-(u / 0.9) ** 2 * 0.5) * (y > hgt + 0.02) * (y < ground) * 0.18 * (np.abs(u) < 1)
            i = np.maximum(i, sheet * 0.85 + back)
            rim_y = ground - ch * (1 - 0.3 * np.clip(u, -1, 1) ** 2)
            hl = np.maximum(hl, band * np.exp(-((y - rim_y) / 0.012) ** 2))
        # droplets ejected from the rim on ballistic arcs
        for k in range(nd):
            t0 = 0.12 + 0.05 * (k % 3)
            if t < t0:
                continue
            tt = t - t0
            px = 0.5 + np.cos(ang[k]) * (0.1 + spd[k] * 0.42 * tt)
            py = ground - 0.2 * np.sin(np.pi * 0.5) * 0 - (spd[k] * 0.9 * tt * np.sin(ang[k]) - 1.6 * tt * tt) - 0.12
            if py > ground:
                continue
            s = dsz[k] * (1 - 0.3 * tt)
            dd = np.hypot(x - px, (y - py) * 0.9)
            i = np.maximum(i, _ss(s * 1.2, s * 0.7, dd))
            hl = np.maximum(hl, np.exp(-((x - px + s * 0.3) ** 2 + (y - py + s * 0.3) ** 2) / (s * 0.35) ** 2))
        # ripple ring on the surface
        rr = 0.1 + 0.4 * t
        rip = np.exp(-((np.abs(x - 0.5) - rr) / 0.02) ** 2) * np.exp(-((y - ground) / 0.01) ** 2) * (1 - t) * 0.6
        i = np.maximum(i, rip)
        life = 1 - _ss(0.7, 1.0, t)
        a = np.clip(i * 0.75 + hl * 0.6, 0, 1) * life * _cell_fade(n, 0.04)
        col = np.stack([0.72 + 0.28 * hl, 0.8 + 0.2 * hl, 0.88 + 0.12 * hl], -1)
        cells.append(np.concatenate([col, a[..., None]], -1))
    _save_rgba(out, _atlas(cells, 4))


@texture("fx_blood_spray", size=1024, seed=6303, kind="single", import_kind="albedo")
def fx_blood_spray(size: int, seed: int, out) -> None:
    """4x4 flipbook (256 px) of a blood burst spraying toward +X: dense jet, ballistic droplets and a
    fine mist that expands, sags under gravity and fades."""
    frames, n = 16, size // 4
    r = _rng(seed)
    x, y = _grid(n)
    nd = 70
    ang = (r.random(nd) - 0.5) * 0.9
    spd = 0.35 + 0.75 * r.random(nd) ** 0.7
    sz = 0.004 + 0.016 * r.random(nd) ** 2.5
    mist = _noise3(frames, n, n, 1.4, seed + 1, tscale=3.0, fmin=3.0)
    cells = []
    for f in range(frames):
        t = (f + 0.5) / frames
        dens = np.zeros((n, n), np.float32)
        hl = np.zeros((n, n), np.float32)
        ox, oy = 0.12, 0.45
        # jet
        L = 0.15 + 0.5 * t ** 0.6
        u = x - ox
        jet_w = 0.02 + 0.12 * np.clip(u / max(L, 1e-3), 0, 1)
        jet = np.exp(-((y - oy - 0.25 * u * u) / jet_w) ** 2) * (u > 0) * _ss(L, L * 0.6, u) * (1 - _ss(0.2, 0.6, t))
        dens = np.maximum(dens, jet * 0.9)
        for k in range(nd):
            d = spd[k] * 0.75 * t
            px = ox + np.cos(ang[k]) * d
            py = oy + np.sin(ang[k]) * d + 0.5 * t * t
            s = sz[k]
            el = 1 + 2.5 * spd[k] * (1 - t)
            ca, sa = np.cos(ang[k] + t * 0.8), np.sin(ang[k] + t * 0.8)
            uu = (x - px) * ca + (y - py) * sa
            vv = -(x - px) * sa + (y - py) * ca
            q = np.hypot(uu / (s * el), vv / s)
            dens = np.maximum(dens, _ss(1.2, 0.8, q))
            hl = np.maximum(hl, np.exp(-((uu + s * 0.3) ** 2 + (vv + s * 0.3) ** 2) / (s * 0.3) ** 2) * 0.6)
        cloud_r = 0.08 + 0.35 * t
        env = np.exp(-(((x - ox - 0.3 * t ** 0.5) / cloud_r) ** 2 + ((y - oy - 0.15 * t * t) / (cloud_r * 0.7)) ** 2))
        m = env * np.clip((mist[f] - 0.35 - 0.2 * t) * 3, 0, 1) * 0.5 * (1 - t)
        a = np.clip(dens + m, 0, 1) * (1 - _ss(0.75, 1.0, t)) * _cell_fade(n, 0.04)
        col = np.ones((n, n, 3), np.float32) * _hex("#5a0606")[None, None]
        col = T.lerp(col, _hex("#8e1610")[None, None], (m / np.maximum(dens + m, 1e-3))[..., None] * 0.7)
        col = col + hl[..., None] * np.array([0.5, 0.25, 0.22], np.float32)
        cells.append(np.concatenate([col, a[..., None]], -1))
    _save_rgba(out, _atlas(cells, 4))


# --------------------------------------------------------------------------------------------------
# Motes, spores
# --------------------------------------------------------------------------------------------------

@texture("fx_dust_motes", size=512, seed=6401, kind="single", import_kind="albedo")
def fx_dust_motes(size: int, seed: int, out) -> None:
    """2x2 atlas of soft, slightly out-of-focus dust specks (irregular bokeh blobs, fibres)."""
    n = size // 2
    r = _rng(seed)
    x, y = _grid(n)
    cells = []
    for k in range(4):
        nz = _noise2(n, 1.6, seed + k)
        d = np.hypot(x - 0.5, y - 0.5)
        if k == 3:
            u, v = x - 0.5, y - 0.5
            fib = np.exp(-((v - 0.1 * np.sin(u * 9)) / 0.025) ** 2) * np.exp(-(u / 0.3) ** 2)
            a = fib * 0.8
        else:
            rad = 0.18 + 0.08 * k
            a = _ss(rad * (1.1 + 0.25 * (nz - 0.5)), rad * 0.4, d) * (0.6 + 0.4 * nz)
            a = a * (1 - 0.3 * np.exp(-(d / (rad * 0.5)) ** 2) * (k == 1))
        col = np.ones((n, n, 3), np.float32) * _hex("#e8dcc4")[None, None]
        cells.append(np.concatenate([col, (np.clip(a, 0, 1) * 0.8 * _cell_fade(n))[..., None]], -1))
    _save_rgba(out, _atlas(cells, 2))


@texture("fx_bloom_spores", size=512, seed=6402, kind="single", import_kind="albedo")
def fx_bloom_spores(size: int, seed: int, out) -> None:
    """2x2 atlas of pale Bloom spores: luminous pale-green/ivory cores with soft halos and faint
    fungal filaments trailing from them (eerie, organic)."""
    n = size // 2
    r = _rng(seed)
    x, y = _grid(n)
    cells = []
    for k in range(4):
        u, v = x - 0.5, y - 0.5
        d = np.hypot(u, v)
        th = np.arctan2(v, u)
        core_r = 0.06 + 0.03 * k
        lobes = 1 + 0.12 * np.sin(5 * th + k) + 0.06 * np.sin(9 * th + 2 * k)
        core = _ss(core_r * lobes * 1.1, core_r * lobes * 0.7, d)
        halo = np.exp(-(d / (core_r * 3.5)) ** 2) * 0.45
        fil = np.zeros_like(d)
        for _ in range(4 + k):
            a0 = r.random() * 2 * np.pi
            curl = (r.random() - 0.5) * 6
            dth = np.angle(np.exp(1j * (th - a0 - curl * d)))
            fil = np.maximum(fil, np.exp(-(dth * d / 0.006) ** 2) * (d > core_r) * np.exp(-((d - core_r) / (0.12 + 0.15 * r.random())) ** 2))
        i = np.clip(core + halo + fil * 0.6, 0, 1)
        col = T.lerp(np.ones((n, n, 3), np.float32) * _hex("#c8d8a8")[None, None], _hex("#f6f2dc")[None, None], core[..., None])
        a = np.clip(core * 0.95 + halo * 0.6 + fil * 0.5, 0, 1) * _cell_fade(n)
        cells.append(np.concatenate([col * (0.85 + 0.15 * i)[..., None], a[..., None]], -1))
    _save_rgba(out, _atlas(cells, 2))


# --------------------------------------------------------------------------------------------------
# Debris atlases (baked top-left lighting)
# --------------------------------------------------------------------------------------------------

def _shade(height: np.ndarray, strength: float, L=(-0.55, -0.6, 0.6)) -> np.ndarray:
    gy, gx = np.gradient(height)
    nx, ny, nz = -gx * strength, -gy * strength, np.ones_like(height)
    inv = 1 / np.sqrt(nx * nx + ny * ny + nz * nz)
    Lv = np.array(L, np.float32)
    Lv /= np.linalg.norm(Lv)
    ndl = (nx * Lv[0] + ny * Lv[1] + nz * Lv[2]) * inv
    return np.clip(0.35 + 0.75 * np.clip(ndl, 0, 1), 0, 1.2)


def _clump(n: int, r, seed: int, kind: str):
    x, y = _grid(n)
    u, v = x - 0.5, y - 0.5
    ang = r.random() * 6.28
    ca, sa = np.cos(ang), np.sin(ang)
    uu, vv = u * ca + v * sa, -u * sa + v * ca
    th = np.arctan2(vv, uu)
    nz = _noise2(n, 1.4, seed)
    nz2 = _noise2(n, 0.6, seed + 1)
    el = 0.75 + 0.4 * r.random()
    d = np.hypot(uu / el, vv)
    rad = 0.24 * (1 + 0.18 * np.sin(3 * th + r.random() * 6) + 0.12 * np.sin(5 * th + r.random() * 6)
                  + 0.25 * (nz - 0.5))
    inside = _ss(rad + 0.012, rad - 0.012, d)
    hgt = np.sqrt(np.clip(1 - (d / np.maximum(rad, 1e-3)) ** 2, 0, 1)) * (0.75 + 0.5 * nz2) * inside
    return x, y, uu, vv, d, rad, inside, hgt, nz, nz2


@texture("fx_dirt_chunks", size=1024, seed=6501, kind="single", import_kind="albedo")
def fx_dirt_chunks(size: int, seed: int, out) -> None:
    """4x4 atlas of dirt / debris clumps for impacts and digging: soil clods, root-bound sod, wet mud
    blobs, stone chips (baked upper-left light, alpha cut-out)."""
    n = size // 4
    r = _rng(seed)
    cells = []
    kinds = ["soil", "soil", "sod", "mud", "stone", "soil", "sod", "stone", "mud", "soil", "stone", "sod", "soil",
             "mud", "stone", "soil"]
    for k, kind in enumerate(kinds):
        x, y, uu, vv, d, rad, inside, hgt, nz, nz2 = _clump(n, r, seed + 10 * k, kind)
        if kind == "stone":
            facets = np.zeros_like(d)
            for _ in range(6):
                a0 = r.random() * 6.28
                facets = np.maximum(facets, (np.cos(a0) * uu + np.sin(a0) * vv) * (2.5 + r.random()))
            hgt = np.clip(1 - facets * 1.6, 0, 1) * inside
            base = _hex(["#8a8780", "#6a6660", "#9a948a", "#5a5650"][k % 4])
            col = base[None, None] * (0.85 + 0.3 * nz2)[..., None]
        elif kind == "mud":
            base = _hex("#3e3226")
            col = base[None, None] * (0.85 + 0.3 * nz)[..., None]
            hgt = _blur(hgt, 2)
        elif kind == "sod":
            base = _hex("#4a3a2a")
            col = base[None, None] * (0.8 + 0.4 * nz2)[..., None]
            top = _ss(0.0, -0.15, vv) * inside
            grass = _ss(0.55, 0.75, _noise2(n, 0.5, seed + 99 + k))
            col = T.lerp(col, _hex("#6a7a34")[None, None] * (0.8 + 0.4 * nz2)[..., None], (top * grass)[..., None])
            roots = _ss(0.86, 0.9, _noise2(n, 1.0, seed + 77 + k)) * inside
            col = T.lerp(col, _hex("#8a7a5a")[None, None], (roots * 0.7)[..., None])
        else:
            base = _hex(["#5e4836", "#6e5640", "#54402f"][k % 3])
            crumbs = _ss(0.65, 0.8, nz2)
            col = base[None, None] * (0.8 + 0.35 * nz2 + 0.15 * crumbs)[..., None]
            hgt = hgt * (0.85 + 0.3 * crumbs)
        shade = _shade(hgt * 0.35, 12.0)
        col = col * shade[..., None]
        a = inside * _cell_fade(n, 0.04)
        cells.append(np.concatenate([col, a[..., None]], -1))
    _save_rgba(out, _atlas(cells, 4))


@texture("fx_wood_chips", size=1024, seed=6502, kind="single", import_kind="albedo")
def fx_wood_chips(size: int, seed: int, out) -> None:
    """4x4 atlas of wood chips / splinters from axe chops: pale fresh wood with grain, some with a
    strip of dark bark, splintered ends (baked upper-left light, alpha cut-out)."""
    n = size // 4
    r = _rng(seed)
    x, y = _grid(n)
    cells = []
    for k in range(16):
        ang = r.random() * 6.28
        ca, sa = np.cos(ang), np.sin(ang)
        u, v = (x - 0.5) * ca + (y - 0.5) * sa, -(x - 0.5) * sa + (y - 0.5) * ca
        L = 0.28 + 0.14 * r.random()
        W = (0.06 + 0.09 * r.random()) * (0.5 if k % 4 == 3 else 1.0)
        nz = _noise2(n, 1.2, seed + k)
        splinter = 0.35 * np.abs(np.sin(v * 90 + k)) * _ss(L * 0.7, L, np.abs(u))
        taper = 1 - 0.5 * (np.abs(u) / L) ** 2
        edge_jag = 1 + 0.15 * (nz - 0.5) * 2
        inside = _ss(1.02, 0.98, np.abs(u) / (L * (1 - splinter))) * _ss(1.03, 0.97, np.abs(v) / (W * taper * edge_jag))
        grain = 0.5 + 0.5 * np.sin(v * 160 + 6 * (nz - 0.5) + u * 4)
        wood = _hex(["#c9a676", "#bf9a68", "#d2b282", "#b58e5e"][k % 4])
        col = wood[None, None] * (0.85 + 0.2 * grain)[..., None] * (0.9 + 0.2 * nz)[..., None]
        if k % 3 == 0:
            bark = _ss(W * 0.45, W * 0.75, v) * inside
            col = T.lerp(col, _hex("#4e3e30")[None, None] * (0.8 + 0.4 * nz)[..., None], bark[..., None])
        hgt = np.clip(1 - (v / (W + 1e-3)) ** 2, 0, 1) * inside * 0.6 + grain * 0.05
        shade = _shade(hgt * 0.3, 14.0)
        col = col * shade[..., None]
        cells.append(np.concatenate([col, (inside * _cell_fade(n, 0.04))[..., None]], -1))
    _save_rgba(out, _atlas(cells, 4))


# --------------------------------------------------------------------------------------------------
# Water
# --------------------------------------------------------------------------------------------------

def _wave_height(n: int, seed: int, L_px: float, wind=(1.0, 0.25), dir_pow: float = 2.0, iso: float = 0.15,
                 kmax_frac: float = 0.45) -> np.ndarray:
    """Tileable wind-wave height field from a Phillips-like spectrum (random phases)."""
    r = _rng(seed)
    kx = np.fft.fftfreq(n)[None, :] * n
    ky = np.fft.fftfreq(n)[:, None] * n
    k = np.sqrt(kx * kx + ky * ky)
    k[0, 0] = 1.0
    w = np.array(wind, np.float64)
    w /= np.linalg.norm(w)
    kn = n / L_px
    cosw = (kx * w[0] + ky * w[1]) / k
    spec = np.exp(-1.0 / (k / kn) ** 2) / k ** 4 * (np.abs(cosw) ** dir_pow + iso)
    spec *= np.exp(-(k / (n * kmax_frac)) ** 2)
    spec[0, 0] = 0.0
    amp = np.sqrt(spec) * (r.normal(size=(n, n)) + 1j * r.normal(size=(n, n)))
    h = np.real(np.fft.ifft2(amp))
    return (h / np.abs(h).max()).astype(np.float32)


def _normal_periodic(h: np.ndarray, strength: float) -> np.ndarray:
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5
    dy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5
    nx, ny, nz = -dx * strength, dy * strength, np.ones_like(h)
    inv = 1 / np.sqrt(nx * nx + ny * ny + nz * nz)
    return np.stack([nx * inv, ny * inv, nz * inv], -1) * 0.5 + 0.5


@texture("water_normal_a", size=1024, seed=6601, kind="single", import_kind="normal")
def water_normal_a(size: int, seed: int, out) -> None:
    """Wind chop for lakes / slow rivers (authored for ~8 m per tile; scroll along +U for wind)."""
    n = size
    h = _wave_height(n, seed, n / 9.0, wind=(1.0, 0.3), dir_pow=2.0, iso=0.2)
    h2 = _wave_height(n, seed + 1, n / 26.0, wind=(0.9, -0.4), dir_pow=1.0, iso=0.4)
    T.save_rgb(pathlib.Path(str(out) + ".png"), _normal_periodic(h + 0.35 * h2, 6.0))


@texture("water_normal_b", size=1024, seed=6602, kind="single", import_kind="normal")
def water_normal_b(size: int, seed: int, out) -> None:
    """Fine capillary ripples (authored for ~1.5 m per tile), nearly isotropic; layer over A."""
    n = size
    h = _wave_height(n, seed, n / 22.0, wind=(0.7, 0.7), dir_pow=1.0, iso=0.8, kmax_frac=0.35)
    h2 = _wave_height(n, seed + 1, n / 60.0, wind=(-0.5, 0.9), dir_pow=0.5, iso=1.0, kmax_frac=0.45)
    T.save_rgb(pathlib.Path(str(out) + ".png"), _normal_periodic(h + 0.5 * h2, 5.0))


@texture("water_foam", size=1024, seed=6603, kind="single", import_kind="data")
def water_foam(size: int, seed: int, out) -> None:
    """Tileable foam (linear data). R = graded foam density -- threshold it (foam = R > 1 - amount)
    so foam grows from dense cores into lacy edges; G = bubble lace detail; B = large patch breakup."""
    n = size
    f1, f2, cid = T.worley(n, 1800, seed + 1)
    cell = n / np.sqrt(1800)
    lace = 1 - _ss(0.0, cell * 0.12, f2 - f1)
    bub = _ss(cell * 0.45, cell * 0.2, f1) * ((np.sin(cid * 12.9898) * 43758.5453) % 1.0 > 0.6)
    g1, g2, _ = T.worley(n, 9000, seed + 2)
    small = 1 - _ss(0.0, 1.2, g2 - g1)
    patches = T.spectral(n, 2.0, seed + 3, fmin=2, fmax=24)
    wx, wy = T.spectral(n, 2.2, seed + 4), T.spectral(n, 2.2, seed + 5)
    patches = T.warp(patches, wx, wy, 30.0)
    detail = np.clip(0.55 * lace + 0.3 * small + 0.4 * bub, 0, 1)
    dens = np.clip(0.6 * T.normalize(patches) + 0.4 * detail * T.normalize(patches) ** 0.5, 0, 1)
    T.save_rgb(pathlib.Path(str(out) + ".png"), np.stack([T.normalize(dens), detail, T.normalize(patches)], -1))
