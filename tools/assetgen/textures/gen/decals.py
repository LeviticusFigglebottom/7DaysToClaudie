"""Decals: blood, grime, mould, water stains, scorch, cracks, bullet holes, survivor marks, footprints.

All decals are RGBA albedo with straight (non-premultiplied) alpha whose colour is bled outward
under transparent pixels (no dark fringes under filtering/mips). Content fades out well before the
borders. kind="pbr_alpha" decals add a tangent-space normal (OpenGL, flat where alpha = 0) and an
ORM map (R = AO, G = roughness, B = metallic = 0) -- e.g. fresh blood is glossy, dried blood satin.

Physical model used for blood: a thickness field T (0 = none, ~1 = a few mm). Colour goes from a thin,
brighter, translucent red to a thick near-black red; alpha = 1 - exp(-k T) (thin films let the surface
show through); height = T for the normal map; dried stains get a darker drying ring at the rim.
Suggested decal sizes live in game/data/materials/decals.json.
"""
from __future__ import annotations

import pathlib

import numpy as np
from scipy import ndimage

from .. import texlib as T
from ..registry import texture

# --------------------------------------------------------------------------------------------------
# Helpers (decal canvases are NOT periodic)
# --------------------------------------------------------------------------------------------------


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed & 0xFFFFFFFF)


def _ss(e0, e1, x):
    return T.smoothstep(e0, e1, x)


def _hex(h: str) -> np.ndarray:
    return T.hex_rgb(h).astype(np.float32)


def _noise(h: int, w: int, beta: float, seed: int, fmin: float = 1.0, fmax: float | None = None,
           aniso=(1.0, 1.0)) -> np.ndarray:
    """Rectangular 1/f^beta noise normalised to 0..1 (frequencies in cycles per canvas)."""
    r = _rng(seed)
    fy = np.fft.fftfreq(h)[:, None] * h / aniso[1]
    fx = np.fft.fftfreq(w)[None, :] * w / aniso[0]
    f = np.sqrt(fx * fx * (h / w) ** 2 + fy * fy) if w != h else np.sqrt(fx * fx + fy * fy)
    f[0, 0] = 1.0
    amp = 1.0 / np.power(f, beta)
    amp[f < fmin] = 0.0
    if fmax is not None:
        amp[f > fmax] = 0.0
    amp[0, 0] = 0.0
    ph = r.uniform(0, 2 * np.pi, (h, w))
    out = np.real(np.fft.ifft2(amp * np.exp(1j * ph)))
    return T.normalize(out).astype(np.float32)


def _noise1(count: int, beta: float, seed: int, fmin: float = 1.0) -> np.ndarray:
    """1-D 1/f^beta noise (0..1) of `count` samples."""
    r = _rng(seed)
    f = np.abs(np.fft.fftfreq(count) * count)
    f[0] = 1.0
    amp = 1.0 / np.power(f, beta)
    amp[f < fmin] = 0.0
    amp[0] = 0.0
    out = np.real(np.fft.ifft(amp * np.exp(1j * r.uniform(0, 2 * np.pi, count))))
    return T.normalize(out).astype(np.float32)


def _blur(a: np.ndarray, s) -> np.ndarray:
    if np.all(np.asarray(s) <= 0):
        return a
    if a.ndim == 3:
        return np.stack([ndimage.gaussian_filter(a[..., c], s, mode="nearest") for c in range(a.shape[2])], -1)
    return ndimage.gaussian_filter(a, s, mode="nearest")


def _grid(h: int, w: int):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    return xx + 0.5, yy + 0.5


def _border_fade(h: int, w: int, margin: float = 0.04) -> np.ndarray:
    xx, yy = _grid(h, w)
    mx = max(4.0, margin * w)
    my = max(4.0, margin * h)
    fx = _ss(0, mx, np.minimum(xx, w - xx))
    fy = _ss(0, my, np.minimum(yy, h - yy))
    return (fx * fy).astype(np.float32)


def _bleed(rgb: np.ndarray, a: np.ndarray) -> np.ndarray:
    """Pushes colour into fully transparent pixels (normalised convolution at growing radii) so
    bilinear filtering / mip-maps never pull in black."""
    out = rgb.copy()
    known = (a > 0.004).astype(np.float32)
    filled = known.copy()
    acc = rgb * known[..., None]
    for s in (2, 6, 18, 54):
        wsum = _blur(known, s)
        csum = _blur(acc, s)
        est = csum / np.maximum(wsum, 1e-6)[..., None]
        take = (filled < 0.5) & (wsum > 1e-4)
        out[take] = est[take]
        filled[take] = 1.0
    if (filled < 0.5).any():
        mean = (rgb * known[..., None]).sum((0, 1)) / max(known.sum(), 1.0)
        out[filled < 0.5] = mean
    return out


def _normal(hgt: np.ndarray, strength: float) -> np.ndarray:
    """OpenGL normal from a (non-periodic) height field; strength = slope scale."""
    gy, gx = np.gradient(hgt.astype(np.float32))
    nx = -gx * strength
    ny = gy * strength
    nz = np.ones_like(hgt)
    inv = 1 / np.sqrt(nx * nx + ny * ny + nz * nz)
    return np.stack([nx * inv, ny * inv, nz * inv], -1) * 0.5 + 0.5


def _save(out, rgb: np.ndarray, a: np.ndarray, *, height: np.ndarray | None = None, strength: float = 4.0,
          rough: np.ndarray | float | None = None, ao: np.ndarray | None = None) -> None:
    """Writes <out>_albedo.png (RGBA) and, when rough is given, <out>_normal.png + <out>_orm.png."""
    out = pathlib.Path(out)
    a = np.clip(a, 0, 1).astype(np.float32)
    rgb = _bleed(np.clip(rgb, 0, 1).astype(np.float32), a)
    T.save_rgba(out.with_name(out.name + "_albedo.png"), np.concatenate([rgb, a[..., None]], -1))
    if rough is None:
        return
    hgt = height if height is not None else np.zeros_like(a)
    nrm = _normal(hgt, strength)
    flat = np.array([0.5, 0.5, 1.0], np.float32)
    nrm = nrm * a[..., None] + flat * (1 - a[..., None])
    T.save_rgb(out.with_name(out.name + "_normal.png"), nrm)
    if not isinstance(rough, np.ndarray):
        rough = np.full_like(a, float(rough))
    ao = ao if ao is not None else np.ones_like(a)
    T.save_orm(out.with_name(out.name + "_orm.png"), np.clip(ao, 0, 1), np.clip(rough, 0.02, 1), 0.0)


def _stamp_max(canvas: np.ndarray, cx, cy, P: int, fn, params: dict, chunk: int = 2_000_000) -> None:
    """Union-stamps small shapes (max) into a non-periodic canvas. fn(dx, dy, p) -> value (b,P,P)."""
    H, W = canvas.shape
    flat = canvas.reshape(-1)
    cx = np.asarray(cx, np.float64)
    cy = np.asarray(cy, np.float64)
    step = max(1, chunk // (P * P))
    g = np.arange(P)
    for s in range(0, cx.size, step):
        sl = slice(s, s + step)
        ox = np.floor(cx[sl]).astype(np.int64) - P // 2
        oy = np.floor(cy[sl]).astype(np.int64) - P // 2
        X = ox[:, None, None] + g[None, None, :]
        Y = oy[:, None, None] + g[None, :, None]
        dx = (X + 0.5 - cx[sl][:, None, None]).astype(np.float32)
        dy = (Y + 0.5 - cy[sl][:, None, None]).astype(np.float32)
        p = {k: (np.asarray(v)[sl][:, None, None] if np.ndim(v) else v) for k, v in params.items()}
        val = np.broadcast_to(fn(dx, dy, p), (X.shape[0], P, P))
        ok = (X >= 0) & (X < W) & (Y >= 0) & (Y < H) & (val > 1e-4)
        idx = (np.broadcast_to(Y, ok.shape) * W + np.broadcast_to(X, ok.shape))[ok]
        np.maximum.at(flat, idx, val[ok].astype(canvas.dtype))


def _stroke_dist(xx, yy, pts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Distance from every pixel to a polyline pts (k,2) and the normalised arc position 0..1."""
    best = np.full(xx.shape, 1e9, np.float32)
    pos = np.zeros(xx.shape, np.float32)
    seg = np.hypot(np.diff(pts[:, 0]), np.diff(pts[:, 1]))
    cum = np.concatenate([[0], np.cumsum(seg)])
    total = max(cum[-1], 1e-6)
    for i in range(len(pts) - 1):
        ax, ay = pts[i]
        bx, by = pts[i + 1]
        abx, aby = bx - ax, by - ay
        l2 = max(abx * abx + aby * aby, 1e-9)
        t = np.clip(((xx - ax) * abx + (yy - ay) * aby) / l2, 0, 1)
        d = np.hypot(xx - (ax + t * abx), yy - (ay + t * aby))
        m = d < best
        best = np.where(m, d, best)
        pos = np.where(m, (cum[i] + t * seg[i]) / total, pos)
    return best, pos


def _blood_colour(Tk: np.ndarray, *, dried: float = 0.0, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Thickness -> (rgb, alpha). dried 0..1 shifts from fresh crimson to brown-black."""
    h, w = Tk.shape
    thin = _hex("#8e1c14") * (1 - dried) + _hex("#5a2216") * dried
    mid = _hex("#5c0807") * (1 - dried) + _hex("#3a120a") * dried
    thick = _hex("#2a0404") * (1 - dried) + _hex("#1e0a06") * dried
    t = np.clip(Tk, 0, None)
    c = T.lerp(thin[None, None], mid[None, None], _ss(0.0, 0.45, t)[..., None])
    c = T.lerp(c, thick[None, None], _ss(0.45, 1.4, t)[..., None])
    var = _noise(h, w, 1.4, seed + 1)
    c = c * (0.9 + 0.2 * var)[..., None]
    a = 1 - np.exp(-6.0 * t)
    return c.astype(np.float32), a.astype(np.float32)


def _drying_ring(Tk: np.ndarray, amount: float) -> np.ndarray:
    """Coffee-ring effect: dried drops concentrate pigment at their rims."""
    m = (Tk > 0.02).astype(np.float32)
    inner = _blur(m, 2.0)
    rim = np.clip(m - inner, 0, 1) * 2.5 + np.clip(inner - _blur(m, 5.0), 0, 1) * 0.5
    return np.clip(rim, 0, 1) * amount


def _drop_fn(dx, dy, p):
    """Blood droplet: ellipse elongated along `ang` (impact angle), scalloped (crenated) rim on the
    bigger drops, a tapering tail in the direction of travel (+u) and optionally a detached
    satellite dot ahead of it (the 'exclamation mark' of oblique impacts). Returns thickness."""
    ca, sa = np.cos(p["ang"]), np.sin(p["ang"])
    u = dx * ca + dy * sa
    v = -dx * sa + dy * ca
    rx = p["r"] * p["el"]
    ry = p["r"]
    th = np.arctan2(v / ry, u / rx)
    cren = 1 + p["cren"] * np.sin(p["k"] * th + p["ph"])
    q = np.sqrt((u / rx) ** 2 + (v / ry) ** 2) / cren
    aa = 1.0 / np.maximum(ry, 1)
    body = np.clip(1 - q * q, 0, 1) ** 0.4 * _ss(1.0 + aa, 1.0 - aa, q)
    rim = np.exp(-((q - 0.85) / 0.12) ** 2) * 0.25 * _ss(1.0 + aa, 1.0 - aa, q)
    tl = p["tail"]
    tu = np.clip((u - rx * 0.5) / np.maximum(tl, 1e-3), 0, 1)
    tw = ry * 0.5 * (1 - tu) ** 1.4
    tail = (u > 0) * (tl > 0) * _ss(tw + 0.6, tw - 0.3, np.abs(v)) * (1 - 0.6 * tu) * 0.8
    sat_r = ry * 0.35
    sd = np.hypot(u - rx - tl * 1.15, v)
    sat = (p["sat"] > 0.5) * (tl > 0) * np.clip(1 - (sd / np.maximum(sat_r, 0.6)) ** 2, 0, 1) ** 0.5 * 0.8
    return np.maximum(np.maximum(body + rim, tail), sat) * p["t"]


def _drops(Tk, r, x, y, ang, rad, el, tail, thick, sat_frac=0.3):
    cnt = np.size(x)
    if cnt == 0:
        return
    rad = np.asarray(rad, np.float64)
    params = {"ang": ang, "r": rad, "el": el, "tail": tail, "t": thick,
              "cren": np.where(rad > 4, 0.04 + 0.08 * r.random(cnt), 0.0), "k": r.integers(9, 22, cnt).astype(np.float64),
              "ph": r.random(cnt) * 6.28, "sat": (r.random(cnt) < sat_frac).astype(np.float64)}
    ext = rad * np.asarray(el) + np.asarray(tail) * 1.6 + rad * 0.5
    order = np.argsort(ext)
    # bin by size so small drops use small patches
    for lo, hi in ((0, 6), (6, 14), (14, 30), (30, 70), (70, 1e9)):
        m = (ext >= lo) & (ext < hi)
        if not m.any():
            continue
        idx = order[np.isin(order, np.nonzero(m)[0])]
        P = int(np.ceil(ext[idx].max() * 2 + 6))
        _stamp_max(Tk, np.asarray(x)[idx], np.asarray(y)[idx], P, _drop_fn, {k: np.asarray(v)[idx] for k, v in params.items()})


def _disk_fn(dx, dy, p):
    d = np.hypot(dx, dy)
    return np.clip(1 - (d / np.maximum(p["r"], 0.5)) ** 2, 0, 1) ** 0.5 * _ss(p["r"] + 0.8, p["r"] - 0.4, d) * p["t"]


def _stroke(Tk, pts: np.ndarray, w0: float, w1: float, thick: float, *, step: float = 0.7) -> None:
    """Tapered round stroke along a polyline, stamped as dense disks (union)."""
    seg = np.hypot(np.diff(pts[:, 0]), np.diff(pts[:, 1]))
    cum = np.concatenate([[0], np.cumsum(seg)])
    if cum[-1] < 1e-3:
        return
    s = np.arange(0, cum[-1], step)
    px = np.interp(s, cum, pts[:, 0])
    py = np.interp(s, cum, pts[:, 1])
    t = s / cum[-1]
    w = w0 + (w1 - w0) * t ** 0.8
    _stamp_max(Tk, px, py, int(np.ceil(max(w0, w1) * 2 + 6)), _disk_fn, {"r": w, "t": np.full(t.size, thick) * (1 - 0.3 * t)})


def _curve(r, x0, y0, ang, L, k=6, bend=0.12):
    a = ang + np.cumsum(np.concatenate([[0], r.normal(0, bend, k - 1)]))
    st = L / (k - 1)
    xs = x0 + np.concatenate([[0], np.cumsum(np.cos(a[1:]) * st)])
    ys = y0 + np.concatenate([[0], np.cumsum(np.sin(a[1:]) * st)])
    return np.stack([xs, ys], 1)


def _stain(xx, yy, cx, cy, R, seed, *, lobes=0.2, cren=0.05, spikes=24, spike_len=0.35, aniso=1.0, ang=0.0):
    """Main stain: low-order lobes + crenated (scalloped) rim + short narrow spikes. Returns the
    signed distance-ish field (px, > 0 inside) and the polar angle."""
    r = _rng(seed)
    dx, dy = xx - cx, yy - cy
    ca, sa = np.cos(ang), np.sin(ang)
    u = (dx * ca + dy * sa) / aniso
    v = -dx * sa + dy * ca
    th = np.arctan2(v, u)
    rr = np.hypot(u, v)
    mod = np.zeros_like(th)
    for k in range(2, 7):
        mod += lobes / 2.5 * np.sin(k * th + r.random() * 6.28) * r.random()
    for k in (24, 33, 47, 61):
        mod += cren * np.sin(k * th + r.random() * 6.28) * (0.5 + 0.5 * r.random())
    sp = np.zeros_like(th)
    for _ in range(spikes):
        a0 = r.random() * 2 * np.pi
        wdt = 0.012 + 0.03 * r.random()
        dth = np.angle(np.exp(1j * (th - a0)))
        sp = np.maximum(sp, spike_len * (0.3 + 0.7 * r.random() ** 2) * np.exp(-np.abs(dth) / wdt))
    rad = R * (1 + mod + sp)
    return (rad - rr).astype(np.float32), th.astype(np.float32), rad


def _signed_dist(mask: np.ndarray) -> np.ndarray:
    """Signed pixel distance to the boundary of a mask (> 0 inside)."""
    return (ndimage.distance_transform_edt(mask) - ndimage.distance_transform_edt(~mask)).astype(np.float32)


def _stain_thickness(edge, n, seed, rim=0.3):
    inner = _ss(0.0, 30.0, edge)
    pool = 0.35 + 0.5 * inner * (0.6 + 0.6 * _noise(n, n, 1.5, seed))
    rimk = rim * np.exp(-(np.maximum(edge, 0) / 4.0) ** 2)
    return np.where(edge > -0.5, (pool + rimk) * _ss(-0.8, 0.8, edge), 0).astype(np.float32)


def _satellites(Tk, r, cx, cy, count, rmin, rmax, dmin, dmax, thick, *, dir_ang=None, spread=np.pi, elong=2.2,
                tail=1.0, sat_frac=0.3):
    """Radial satellite drops: smaller and more elongated with distance, tails toward travel."""
    if dir_ang is None:
        ang = r.random(count) * 2 * np.pi
    else:
        ang = dir_ang + (r.random(count) - 0.5) * 2 * spread
    f = r.random(count) ** 1.5
    dist = dmin + (dmax - dmin) * f
    x = cx + np.cos(ang) * dist
    y = cy + np.sin(ang) * dist
    rad = rmin + (rmax - rmin) * r.random(count) ** 3.5 * (1 - 0.6 * f)
    el = 1 + (elong - 1) * (0.3 + 0.7 * f) * r.random(count)
    tl = rad * el * tail * r.random(count) * 2.5 * f
    _drops(Tk, r, x, y, ang + (r.random(count) - 0.5) * 0.25, rad, el, tl, thick * (0.55 + 0.6 * r.random(count)), sat_frac)


def _mist(Tk, r, cx, cy, count, dmax, rmax_px, thick, *, dir_ang=None, spread=np.pi):
    ang = r.random(count) * 2 * np.pi if dir_ang is None else dir_ang + (r.random(count) - 0.5) * 2 * spread
    dist = dmax * np.sqrt(r.random(count))
    rad = 0.5 + (rmax_px - 0.5) * r.random(count) ** 4
    _drops(Tk, r, cx + np.cos(ang) * dist, cy + np.sin(ang) * dist, ang, rad, 1 + 0.8 * r.random(count),
           np.zeros(count), thick * (0.35 + 0.65 * r.random(count)), 0.0)


def _runs(Tk, r, starts_x, starts_y, lengths, widths, thick, wander_seed, *, bulb=1.35):
    """Gravity runs (rivulets) flowing down (+y): wandering, thinning, with beads and a tear-drop end."""
    h, w = Tk.shape
    for i, (x0, y0, L, wd) in enumerate(zip(starts_x, starts_y, lengths, widths)):
        k = max(6, int(L / 12))
        drift = np.cumsum(r.normal(0, 0.9, k))
        ys = np.linspace(y0, min(h - 10.0, y0 + L), k)
        xs = x0 + drift
        pts = np.stack([xs, ys], 1)
        _stroke(Tk, pts, wd, wd * (0.35 + 0.2 * r.random()), thick)
        # beads where the flow paused
        nb = r.integers(0, 4)
        for _ in range(nb):
            t = 0.2 + 0.7 * r.random()
            bx, by = np.interp(t * (k - 1), np.arange(k), xs), np.interp(t * (k - 1), np.arange(k), ys)
            _stamp_max(Tk, [bx], [by], int(wd * 3 + 8), _disk_fn, {"r": [wd * (0.8 + 0.3 * r.random())], "t": [thick]})
        _stamp_max(Tk, [xs[-1]], [ys[-1] + wd * 0.5], int(wd * bulb * 2 + 8), _disk_fn,
                   {"r": [wd * bulb * (0.8 + 0.4 * r.random())], "t": [thick * 1.1]})


def _smear(Tk: np.ndarray, length: float, axis: int = 1, streak: np.ndarray | None = None) -> np.ndarray:
    """One-sided exponential smear (pigment dragged toward +axis), optionally striated."""
    L = int(length * 3)
    kern = np.exp(-np.arange(L) / max(length, 1.0)).astype(np.float32)
    kern /= kern.sum()
    k2 = np.concatenate([np.zeros(L - 1, np.float32), kern])
    sm = ndimage.convolve1d(Tk, k2, axis=axis, mode="constant")
    if streak is not None:
        sm = sm * (0.4 + 0.9 * streak)
    return sm


def _blood_finish(out, Tk, *, dried=0.0, seed=0, ring=0.0, gloss=(0.12, 0.45), extra_alpha=None, fade=0.04):
    h, w = Tk.shape
    Tk = Tk * _border_fade(h, w, fade)
    col, a = _blood_colour(Tk, dried=dried, seed=seed)
    if ring > 0:
        rg = _drying_ring(Tk, ring)
        col = col * (1 - 0.5 * rg[..., None])
        a = np.maximum(a, rg * 0.85 * (Tk > 0.01))
    if extra_alpha is not None:
        a = np.clip(a * extra_alpha, 0, 1)
    rough = gloss[0] + (gloss[1] - gloss[0]) * (1 - _ss(0.05, 0.6, Tk))
    rough = rough * (1 - dried) + (0.5 + 0.2 * (1 - _ss(0.05, 0.6, Tk))) * dried
    hgt = _blur(Tk, 0.7) * (1 - 0.7 * dried)
    _save(out, col, a, height=hgt, strength=3.0, rough=rough)


# --------------------------------------------------------------------------------------------------
# Blood
# --------------------------------------------------------------------------------------------------


@texture("decal_blood_splatter_a", size=1024, seed=5101, kind="pbr_alpha")
def decal_blood_splatter_a(size: int, seed: int, out) -> None:
    """Impact spatter (fresh): irregular scalloped stain with short spines, a dense halo of satellite
    drops elongated away from the centre, and a fine mist."""
    n = size
    r = _rng(seed)
    xx, yy = _grid(n, n)
    cx, cy = n * 0.5, n * 0.52
    edge, th, rad = _stain(xx, yy, cx, cy, n * 0.085, seed, lobes=0.35, cren=0.04, spikes=34, spike_len=0.45)
    Tk = _stain_thickness(edge, n, seed + 1)
    for _ in range(18):
        a0 = r.random() * 2 * np.pi
        R0 = n * 0.085 * (0.85 + 0.2 * r.random())
        pts = _curve(r, cx + np.cos(a0) * R0, cy + np.sin(a0) * R0, a0, n * (0.03 + 0.09 * r.random() ** 1.5), 5, 0.1)
        _stroke(Tk, pts, 2.0 + 3.5 * r.random(), 0.4, 0.6)
        if r.random() < 0.5:
            ex, ey = pts[-1]
            _drops(Tk, r, [ex + np.cos(a0) * 6], [ey + np.sin(a0) * 6], [a0], [2 + 3 * r.random()], [1.8], [6.0], [0.7], 0.0)
    _satellites(Tk, r, cx, cy, 650, 0.8, 9.0, n * 0.08, n * 0.44, 0.85, elong=2.6, tail=1.0)
    _mist(Tk, r, cx, cy, 3000, n * 0.4, 1.8, 0.3)
    _blood_finish(out, Tk, dried=0.1, seed=seed, ring=0.15, gloss=(0.1, 0.4))


@texture("decal_blood_splatter_b", size=1024, seed=5102, kind="pbr_alpha")
def decal_blood_splatter_b(size: int, seed: int, out) -> None:
    """Cast-off: a curved line of discrete elongated drops flung from a swinging weapon (shrinking
    along the swing, tails in the direction of travel), plus a smaller directional impact."""
    n = size
    r = _rng(seed)
    xx, yy = _grid(n, n)
    Tk = np.zeros((n, n), np.float32)
    k = 34
    t = np.sort(r.random(k)) * 0.95
    ax = n * (0.14 + 0.74 * t)
    ay = n * (0.62 - 0.36 * np.sin(np.pi * (0.12 + 0.75 * t)) + 0.05 * t)
    tang = np.arctan2(np.gradient(ay), np.gradient(ax))
    rad = (2.0 + 7.5 * (1 - t) ** 1.3) * (0.6 + 0.6 * r.random(k))
    el = 1.6 + 2.6 * t * (0.8 + 0.4 * r.random(k))
    tl = rad * (1.5 + 4 * t) * (0.5 + 0.8 * r.random(k))
    jit = (r.random((2, k)) - 0.5) * 10
    _drops(Tk, r, ax + jit[0], ay + jit[1], tang + (r.random(k) - 0.5) * 0.12, rad, el, tl, 0.75 + 0.3 * r.random(k), 0.45)
    m2 = 70
    t2 = r.random(m2) * 0.95
    x2 = n * (0.14 + 0.74 * t2) + (r.random(m2) - 0.5) * 50
    y2 = n * (0.62 - 0.36 * np.sin(np.pi * (0.12 + 0.75 * t2)) + 0.05 * t2) + (r.random(m2) - 0.5) * 50
    a2 = np.interp(t2, t, tang)
    r2 = 0.8 + 2.5 * r.random(m2) ** 2
    _drops(Tk, r, x2, y2, a2, r2, 1.5 + 2 * r.random(m2), r2 * 4 * r.random(m2), 0.5 + 0.4 * r.random(m2), 0.2)
    cx, cy = n * 0.2, n * 0.7
    edge, _, _ = _stain(xx, yy, cx, cy, n * 0.035, seed + 7, lobes=0.4, spikes=18, spike_len=0.6, aniso=1.7, ang=-0.7)
    Tk = np.maximum(Tk, _stain_thickness(edge, n, seed + 8))
    _satellites(Tk, r, cx, cy, 220, 0.8, 6.0, n * 0.03, n * 0.24, 0.75, dir_ang=-0.7, spread=0.6, elong=2.8)
    _mist(Tk, r, cx, cy, 900, n * 0.2, 1.6, 0.3, dir_ang=-0.7, spread=0.55)
    _blood_finish(out, Tk, dried=0.25, seed=seed, ring=0.3, gloss=(0.15, 0.45))


@texture("decal_blood_splatter_c", size=1024, seed=5103, kind="pbr_alpha")
def decal_blood_splatter_c(size: int, seed: int, out) -> None:
    """Heavy wet splash on a wall: large irregular stain, satellites, and the excess running down in
    rivulets of different lengths (+V = down)."""
    n = size
    r = _rng(seed)
    xx, yy = _grid(n, n)
    cx, cy = n * 0.5, n * 0.32
    edge, th, rad = _stain(xx, yy, cx, cy, n * 0.12, seed, lobes=0.5, cren=0.05, spikes=26, spike_len=0.4, aniso=1.25)
    Tk = _stain_thickness(edge, n, seed + 1, rim=0.4) * 1.1
    for _ in range(10):
        a0 = r.random() * 2 * np.pi
        R0 = n * 0.12 * (0.9 + 0.25 * r.random())
        pts = _curve(r, cx + np.cos(a0) * R0 * 1.25, cy + np.sin(a0) * R0, a0, n * (0.03 + 0.07 * r.random()), 5, 0.1)
        _stroke(Tk, pts, 2.5 + 3 * r.random(), 0.5, 0.65)
    k = 11
    xs = cx + (r.random(k) - 0.5) * n * 0.3
    ys = np.zeros(k)
    for i in range(k):
        colm = np.nonzero(edge[:, int(np.clip(xs[i], 0, n - 1))] > 2)[0]
        ys[i] = (colm.max() - 4) if colm.size else cy
    _runs(Tk, r, xs, ys, n * (0.08 + 0.45 * r.random(k) ** 1.4), 2.5 + 6 * r.random(k), 0.9, seed + 4)
    _satellites(Tk, r, cx, cy, 380, 0.8, 9.0, n * 0.12, n * 0.45, 0.85, elong=2.2)
    _mist(Tk, r, cx, cy, 1500, n * 0.4, 1.8, 0.3)
    _blood_finish(out, Tk, dried=0.0, seed=seed, ring=0.1, gloss=(0.08, 0.35))


@texture("decal_blood_splatter_d", size=1024, seed=5104, kind="pbr_alpha")
def decal_blood_splatter_d(size: int, seed: int, out) -> None:
    """Old, dried spatter that somebody tried to wipe away: brown-black, a translucent pinkish-brown
    smear streaked in the wiping direction, flaking cracks where it was thick."""
    n = size
    r = _rng(seed)
    xx, yy = _grid(n, n)
    cx, cy = n * 0.42, n * 0.5
    edge, _, _ = _stain(xx, yy, cx, cy, n * 0.08, seed, lobes=0.4, spikes=22, spike_len=0.4)
    Tk = _stain_thickness(edge, n, seed + 1)
    _satellites(Tk, r, cx, cy, 380, 0.8, 7.0, n * 0.08, n * 0.4, 0.75, elong=2.2)
    _mist(Tk, r, cx, cy, 1200, n * 0.36, 1.6, 0.3)
    wipe = _ss(n * 0.17, n * 0.08, np.abs(yy - (n * 0.53 + 0.1 * (xx - n * 0.5)))) * _ss(n * 0.3, n * 0.36, xx)
    streak = _noise(n, n, 1.1, seed + 5, aniso=(1.0, 5.0))
    sm = _blur(_smear(_blur(Tk, 6.0), n * 0.12, axis=1, streak=streak), 1.5) * 2.4
    Tk = Tk * (1 - 0.85 * wipe) + np.clip(sm, 0, 0.35) * wipe
    f1, f2, _ = T.worley(n, 2600, seed + 6)
    crack = (1 - _ss(0.0, 1.2, f2 - f1)) * _ss(0.5, 0.8, Tk)
    Tk = Tk * (1 - 0.85 * crack)
    _blood_finish(out, Tk, dried=1.0, seed=seed, ring=0.55, gloss=(0.4, 0.6), extra_alpha=0.95)


@texture("decal_blood_drip", size=1024, seed=5110, kind="pbr_alpha")
def decal_blood_drip(size: int, seed: int, out) -> None:
    """Blood running down a wall from a smeared contact mark at the top (512 x 1024, +V = down)."""
    h, w = size, size // 2
    r = _rng(seed)
    xx, yy = _grid(h, w)
    top = h * 0.12
    edge, _, _ = _stain(xx, yy, w * 0.5, top, w * 0.16, seed, lobes=0.55, cren=0.05, spikes=22, spike_len=0.45,
                        aniso=1.4)
    Tk = np.where(edge > -0.5, (0.35 + 0.55 * _ss(0, 25, edge)) * (0.7 + 0.5 * _noise(h, w, 1.5, seed + 2))
                  * _ss(-0.8, 0.8, edge), 0).astype(np.float32)
    _satellites(Tk, r, w * 0.5, top, 160, 0.8, 5.0, w * 0.15, w * 0.45, 0.75, elong=2.2)
    k = 13
    covered = np.nonzero((edge > 2).any(0))[0]
    xs = np.sort(covered[r.integers(0, covered.size, k)] + 0.5 + (r.random(k) - 0.5))
    ys = np.zeros(k)
    for i in range(k):
        colm = np.nonzero(edge[:, int(np.clip(xs[i], 0, w - 1))] > 1)[0]
        ys[i] = (colm.max() - 3) if colm.size else top
    _runs(Tk, r, xs, ys, h * (0.12 + 0.66 * r.random(k) ** 1.2), 2.0 + 6.0 * r.random(k) ** 1.5, 0.95, seed + 3)
    _satellites(Tk, r, w * 0.5, top, 70, 0.8, 4.0, w * 0.32, w * 0.55, 0.6, elong=1.6)
    _blood_finish(out, Tk, dried=0.15, seed=seed, ring=0.2, gloss=(0.1, 0.4))


@texture("decal_blood_trail", size=1024, seed=5111, kind="pbr_alpha")
def decal_blood_trail(size: int, seed: int, out) -> None:
    """Drag trail along +V (512 x 1024): overlapping smeared swaths with fine drag striations, blood
    accumulated along the swath edges, gaps where contact broke, smudged hand marks and stray drops.
    Ends are soft so several can be chained."""
    h, w = size, size // 2
    r = _rng(seed)
    xx, yy = _grid(h, w)
    stri = _noise(h, w, 0.7, seed + 1, aniso=(14.0, 1.0))
    stri2 = _noise(h, w, 1.2, seed + 2, aniso=(6.0, 1.0))
    Tk = np.zeros((h, w), np.float32)
    for s_, (off, wid, strength) in enumerate(((0.0, 0.2, 1.0), (0.12, 0.09, 0.8))):
        cl = w * (0.5 + off) + (_noise1(h, 2.4, seed + 10 + s_)[:, None] - 0.5) * w * 0.22
        hw = w * wid * (0.7 + 0.6 * _noise1(h, 1.8, seed + 20 + s_)[:, None])
        edge_n = (_noise(h, w, 1.4, seed + 3 + s_) - 0.5) * w * 0.1
        d = np.abs(xx - cl + edge_n)
        body = _ss(hw + 8, hw - 22, d)
        cover = _ss(0.2, 0.6, _noise(h, w, 1.8, seed + 4 + s_, aniso=(2.5, 1.0)))
        dens = (0.22 + 0.5 * stri ** 1.3 + 0.3 * stri2) * (0.35 + 0.65 * cover)
        acc = np.exp(-((d - hw * 0.9) / 7.0) ** 2) * 0.22 * _ss(0.4, 0.7, _noise(h, w, 1.5, seed + 5 + s_))
        y0 = h * (0.0 if s_ == 0 else 0.25 + 0.2 * r.random())
        y1 = h * (1.0 if s_ == 0 else 0.6 + 0.3 * r.random())
        span = _ss(y0, y0 + h * 0.08, yy) * _ss(y1, y1 - h * 0.12, yy)
        Tk = np.maximum(Tk, body * (dens + acc) * span * strength)
    # smudged hand marks (palm streaks) and stray drops
    for _ in range(2):
        hx, hy = w * (0.35 + 0.3 * r.random()), h * (0.25 + 0.5 * r.random())
        for f in range(4):
            pts = np.array([[hx - 24 + f * 15, hy], [hx - 24 + f * 15 + r.normal(0, 3), hy + 70 + 40 * r.random()]])
            _stroke(Tk, pts, 4.5, 2.0, 0.55)
    _satellites(Tk, r, w * 0.5, h * 0.5, 120, 0.8, 5.0, w * 0.25, w * 0.55, 0.6, elong=1.4, tail=0.6)
    Tk = Tk * _ss(0, h * 0.1, yy) * _ss(0, h * 0.1, h - yy)
    _blood_finish(out, Tk, dried=0.35, seed=seed, ring=0.12, gloss=(0.2, 0.5), fade=0.03)


def _ellipse(xx, yy, cx, cy, rx, ry, ang):
    ca, sa = np.cos(ang), np.sin(ang)
    u = (xx - cx) * ca + (yy - cy) * sa
    v = -(xx - cx) * sa + (yy - cy) * ca
    return np.hypot(u / rx, v / ry)


def _capsule(xx, yy, ax, ay, bx, by):
    abx, aby = bx - ax, by - ay
    t = np.clip(((xx - ax) * abx + (yy - ay) * aby) / (abx * abx + aby * aby), 0, 1)
    return np.hypot(xx - (ax + t * abx), yy - (ay + t * aby)), t


@texture("decal_blood_handprint", size=512, seed=5120, kind="pbr_alpha")
def decal_blood_handprint(size: int, seed: int, out) -> None:
    """Bloody right-hand print sliding down a wall: continuous palm (thenar / hypothenar / heel) and
    fingers, thin gaps at the finger joints and palm creases, weak contact in the palm hollow,
    strong fingertip pads, patchy transfer and a downward slide smear with drips."""
    n = size
    r = _rng(seed)
    xx, yy = _grid(n, n)
    U = n * 0.0031           # px per mm: 512 px over ~0.3 m (hand ~190 mm long -> ~300 px)
    cx, cy = n * 0.5, n * 0.6
    X = (xx - cx) / U         # mm, fingers toward -Y
    Y = (yy - cy) / U
    palm = np.minimum.reduce([
        _ellipse(X, Y, -22, 8, 22, 42, 0.12),       # hypothenar (pinky side)
        _ellipse(X, Y, 24, 14, 26, 32, -0.5),       # thenar (thumb side)
        _ellipse(X, Y, 0, 30, 34, 20, 0.0),         # heel
        _ellipse(X, Y, 0, -22, 42, 20, 0.05),       # metacarpal band under the fingers
        _ellipse(X, Y, 0, 0, 38, 34, 0.0),
    ])
    inside = _ss(1.08, 0.92, palm + 0.08 * (_noise(n, n, 1.2, seed + 1) - 0.5))
    hollow = np.exp(-(((X - 4) / 22) ** 2 + ((Y + 2) / 20) ** 2))
    contact = inside * (1 - 0.6 * hollow)
    gaps = np.zeros((n, n), np.float32)
    gn1 = _noise(n, n, 1.2, seed + 7)
    gn2 = _noise(n, n, 1.0, seed + 8)
    # fingers: base (x, y), direction, length, width (mm); joints at ~45 % and ~72 %
    fingers = [(-30, -34, -1.78, 62, 17), (-11, -40, -1.64, 74, 18.5), (8, -40, -1.52, 71, 18), (26, -33, -1.38, 56, 16)]
    for fx, fy, a, L, wd in fingers:
        bx, by = fx + np.cos(a) * L, fy + np.sin(a) * L
        d, t = _capsule(X, Y, fx, fy, bx, by)
        f = _ss(wd * 0.55, wd * 0.42, d + 1.2 * (_noise(n, n, 1.0, seed + 2) - 0.5))
        tip = np.exp(-((t - 0.88) / 0.1) ** 2)
        contact = np.maximum(contact, f * (0.75 + 0.45 * tip))
        for jt in (0.45, 0.72):
            gw = 0.8 + 1.6 * gn1
            gaps = np.maximum(gaps, f * np.exp(-((t - jt) * L / gw) ** 2) * _ss(0.3, 0.6, gn2)
                              * np.exp(-(d / (wd * (0.25 + 0.2 * gn1))) ** 2))
    # thumb
    d, t = _capsule(X, Y, 36, 4, 66, -34)
    f = _ss(10.5, 8.0, d)
    contact = np.maximum(contact, f * (0.8 + 0.4 * np.exp(-((t - 0.85) / 0.12) ** 2)))
    gaps = np.maximum(gaps, f * np.exp(-((t - 0.5) * 48 / 1.5) ** 2))
    # palm creases (heart, head, life lines) as thin low-contact curves
    for (a0, a1, a2, x0, x1) in ((-18, 0.10, 0.004, -40, 22), (-6, 0.32, 0.003, -38, 30), (8, -0.9, -0.012, 8, 34)):
        if x0 < 0:
            curve = Y - (a0 + a1 * X + a2 * X * X)
            span = (X > x0) & (X < x1)
        else:
            curve = X - (x0 + 0.35 * (Y - a0) + 0.006 * (Y - a0) ** 2)
            span = (Y > -20) & (Y < 40)
        gaps = np.maximum(gaps, np.exp(-(curve / (1.2 + 1.8 * gn1)) ** 2) * span * inside * _ss(0.35, 0.65, gn2))
    blot = _noise(n, n, 1.8, seed + 3)
    fine = _noise(n, n, 0.9, seed + 6)
    transfer = np.clip(0.15 + 1.15 * blot + 0.35 * (fine - 0.5), 0, 1.2)
    Tk = np.clip(contact * transfer * (1 - 0.85 * gaps), 0, 1)
    Tk = Tk * _ss(0.12, 0.32, Tk + 0.12 * (fine - 0.5)) * 0.32
    # slide: pigment dragged downward from the lower palm, a few drips
    streak = _noise(n, n, 0.8, seed + 4, aniso=(10.0, 1.0))
    sm = _smear(Tk, 26, axis=0, streak=streak) * 1.7
    Tk = np.maximum(Tk, np.clip(sm, 0, 0.45) * _ss(cy - 10 * U, cy + 30 * U, yy))
    _runs(Tk, r, cx + np.array([-24.0, 12.0]) * U, cy + np.array([52.0, 46.0]) * U, n * np.array([0.1, 0.17]),
          np.array([2.2, 2.8]), 0.7, seed + 5)
    _blood_finish(out, Tk, dried=0.3, seed=seed, ring=0.25, gloss=(0.2, 0.5), fade=0.05)


@texture("decal_blood_pool", size=1024, seed=5130, kind="pbr_alpha")
def decal_blood_pool(size: int, seed: int, out) -> None:
    """Pooled blood on a floor: irregular lobed outline that has crept along the floor, thick glossy
    body with a meniscus, darker coagulating clots, a broken pale serum seep at the rim, a darker
    drying margin and satellite drips."""
    n = size
    r = _rng(seed)
    xx, yy = _grid(n, n)
    cx, cy = n * 0.5, n * 0.5
    shape = 1 - np.hypot((xx - cx) / (n * 0.3), (yy - cy) / (n * 0.26))
    shape = shape + 0.5 * (_noise(n, n, 2.2, seed + 1, fmin=1.5, fmax=10) - 0.5)
    shape = shape + 0.05 * (_noise(n, n, 1.4, seed + 2) - 0.5)
    field = _signed_dist(shape > 0)
    Tk = np.where(field > -0.5, (0.45 + 0.9 * _ss(0, 70, field)) * _ss(-0.8, 0.8, field), 0).astype(np.float32)
    clots = _ss(0.66, 0.8, _noise(n, n, 1.1, seed + 4)) * _ss(10, 60, field)
    Tk = Tk + 0.35 * clots
    _satellites(Tk, r, cx, cy, 55, 2.0, 9.0, n * 0.3, n * 0.46, 0.9, elong=1.2, tail=0.2)
    meniscus = _ss(0.0, 5.0, field) * _ss(16.0, 5.0, field)
    serum = _ss(-7.0, -1.0, field) * _ss(1.0, -1.0, field) * _ss(0.45, 0.65, _noise(n, n, 1.5, seed + 5))
    margin = _ss(-1.0, 3.0, field) * _ss(12.0, 2.0, field)
    hgt = Tk * 0.5 + meniscus * 0.5
    Tk = Tk * _border_fade(n, n, 0.04)
    col, a = _blood_colour(Tk, dried=0.0, seed=seed)
    col = col * (1 - 0.35 * clots[..., None])
    col = T.lerp(col, _hex("#3a140c")[None, None], (margin * 0.5)[..., None])
    col = T.lerp(col, _hex("#8a5446")[None, None], (serum * 0.7)[..., None])
    a = np.maximum(a, serum * 0.22)
    rough = 0.05 + 0.25 * margin + 0.3 * (1 - _ss(0.05, 0.4, Tk)) + 0.2 * serum
    _save(out, col, a, height=_blur(hgt, 1.0), strength=6.0, rough=rough)


# --------------------------------------------------------------------------------------------------
# Grime, mould, water stain, scorch
# --------------------------------------------------------------------------------------------------


@texture("decal_grime_streaks", size=1024, seed=5201, kind="albedo")
def decal_grime_streaks(size: int, seed: int, out) -> None:
    """Rain-washed dirt streaks running down a wall from drip points along a ledge (+V = down):
    streaks of different widths / lengths with fine vertical striation, patchy grime under the ledge."""
    n = size
    r = _rng(seed)
    xx, yy = _grid(n, n)
    stri = _noise(n, n, 0.8, seed + 1, aniso=(30.0, 1.0))
    a = np.zeros((n, n), np.float32)
    top = n * 0.06
    k = 26
    xs = np.sort(r.random(k)) * n * 0.9 + n * 0.05
    for x0 in xs:
        wdt = 4 + 30 * r.random() ** 2
        L = n * (0.15 + 0.75 * r.random() ** 1.3)
        strength = 0.25 + 0.6 * r.random()
        wob = (_noise1(n, 2.2, int(x0 * 7) + seed) - 0.5)[:, None] * 12
        d = np.abs(xx - x0 - wob)
        prof = np.exp(-(d / wdt) ** 2)
        along = _ss(top - 6, top + 10, yy) * _ss(top + L, top + L * 0.3, yy) * (1 - 0.5 * (yy - top) / max(L, 1))
        a = np.maximum(a, prof * along * strength)
    a = a * (0.55 + 0.6 * stri)
    under = _ss(top + n * 0.12, top, yy) * _ss(top - 8, top + 4, yy) * _ss(0.35, 0.7, _noise(n, n, 1.6, seed + 2))
    a = np.clip(np.maximum(a, under * 0.55) * (0.8 + 0.3 * _noise(n, n, 1.4, seed + 3)), 0, 1)
    a = a * _border_fade(n, n, 0.04)
    c = T.gradient(_noise(n, n, 1.5, seed + 4), [(0.0, "#1c1a16"), (0.5, "#2a2820"), (1.0, "#3a3628")])
    algae = _ss(0.6, 0.8, _noise(n, n, 1.8, seed + 5))
    c = T.lerp(c, _hex("#2a3420")[None, None], (algae * 0.5)[..., None])
    _save(out, c, a * 0.85)


@texture("decal_mold_patch", size=1024, seed=5202, kind="pbr_alpha")
def decal_mold_patch(size: int, seed: int, out) -> None:
    """Black mould: clustered round colonies with fuzzy edges merging into dark patches where dense,
    sparse speckle at the front, grey-green / white fuzz at the margins, faint yellow damp halo."""
    n = size
    r = _rng(seed)
    xx, yy = _grid(n, n)
    shape = 1 - np.hypot((xx - n / 2) / (n * 0.42), (yy - n / 2) / (n * 0.36))
    shape = shape + 0.6 * (_noise(n, n, 2.0, seed + 1, fmin=1.5, fmax=12) - 0.5)
    dens = np.clip(shape * 1.6, 0, 1) ** 1.2
    halo = _ss(-0.15, 0.25, shape) * 0.3
    fuzz_n = _noise(n, n, 0.7, seed + 2)
    col_field = np.zeros((n, n), np.float32)
    cnt = 5200
    px = r.random(cnt * 3) * n
    py = r.random(cnt * 3) * n
    keep = r.random(cnt * 3) < dens[np.clip(py.astype(int), 0, n - 1), np.clip(px.astype(int), 0, n - 1)] ** 1.1
    px, py = px[keep][:cnt], py[keep][:cnt]
    m = px.size
    rad = 1.0 + 11 * r.random(m) ** 4
    fz = fuzz_n.reshape(-1)

    def colony(dx, dy, p):
        d = np.hypot(dx, dy) / p["r"]
        return np.clip(1.15 - d, 0, 1) ** 0.8 * p["t"]
    _stamp_max(col_field, px, py, int(np.ceil(rad.max() * 2.4 + 6)), colony, {"r": rad, "t": 0.55 + 0.45 * r.random(m)})
    col_field = col_field * (0.75 + 0.5 * fuzz_n)
    stain = _blur(col_field, 6) * 1.4
    fringe = np.clip(_blur(col_field, 3) * 1.6 - col_field, 0, 1) * (1 - _ss(0.5, 0.9, dens))
    a = np.clip(halo * (0.5 + 0.5 * _noise(n, n, 1.2, seed + 3)) + col_field + stain * 0.5 + fringe * 0.4, 0, 1)
    a = a * _border_fade(n, n, 0.05)
    c = np.ones((n, n, 3), np.float32) * _hex("#8a7a4c")[None, None]
    c = T.lerp(c, _hex("#4e5040")[None, None], _ss(0.0, 0.3, stain + fringe)[..., None])
    c = T.lerp(c, _hex("#b4b4a2")[None, None], (fringe * _ss(0.65, 0.85, fuzz_n))[..., None])
    c = T.lerp(c, _hex("#171812")[None, None], _ss(0.05, 0.5, col_field + stain * 0.3)[..., None])
    hgt = col_field * 0.6 + fringe * 0.3 * fuzz_n
    _save(out, c, a, height=_blur(hgt, 0.8), strength=3.0, rough=0.93)


@texture("decal_water_stain", size=1024, seed=5203, kind="albedo")
def decal_water_stain(size: int, seed: int, out) -> None:
    """Ceiling / wall water damage: irregular stain with several uneven brown tide lines (the outer one
    darkest), nearly clear yellowed interior, a few satellite stains."""
    n = size
    r = _rng(seed)
    xx, yy = _grid(n, n)
    shape = 1 - np.hypot((xx - n * 0.5) / (n * 0.4), (yy - n * 0.48) / (n * 0.36))
    shape = shape + 0.55 * (_noise(n, n, 2.0, seed + 1, fmin=1.5, fmax=10) - 0.5)
    for _ in range(3):
        sx, sy = n * (0.2 + 0.6 * r.random()), n * (0.2 + 0.6 * r.random())
        shape = np.maximum(shape, 0.22 - np.hypot(xx - sx, yy - sy) / (n * 0.25) + 0.2 * (_noise(n, n, 2.0, seed + 9) - 0.5))
    sd = _signed_dist(shape > 0)
    wob = (_noise(n, n, 1.6, seed + 2) - 0.5) * 18
    lines = np.zeros((n, n), np.float32)
    for i, (dist, wd, st) in enumerate(((1.0, 2.4, 0.8), (26.0, 1.7, 0.42), (70.0, 1.5, 0.3))):
        wob_i = (_noise(n, n, 1.7, seed + 20 + i) - 0.5) * (14 + 30 * i)
        dd = sd - dist - (wob_i if i else 0)
        broken = _ss(0.25, 0.55, _noise(n, n, 1.5, seed + 10 + i)) if i else 1.0
        ln = np.exp(-(dd / wd) ** 2) * st * (0.6 + 0.6 * _noise(n, n, 1.3, seed + 30 + i)) * broken
        lines = np.maximum(lines, ln * (sd > -2))
        lines = np.maximum(lines, _ss(dist + 8, dist, sd + (wob_i if i else 0)) * _ss(dist - 40, dist, sd) * st * 0.2 * (sd > 0) * broken)
    interior = _ss(0, 30, sd) * (0.06 + 0.06 * _noise(n, n, 1.4, seed + 4))
    a = np.clip(lines + interior, 0, 1) * _border_fade(n, n, 0.03)
    c = T.lerp(np.ones((n, n, 3), np.float32) * _hex("#a68a52")[None, None], _hex("#5e4024")[None, None],
               _ss(0.05, 0.5, lines)[..., None])
    _save(out, c, a)


@texture("decal_scorch", size=1024, seed=5204, kind="pbr_alpha")
def decal_scorch(size: int, seed: int, out) -> None:
    """Fire / blast scorch: charred crackled centre, patchy soot fading out with soft irregular blast
    streaks, brown heat discolouration and soot speckle at the margin."""
    n = size
    r = _rng(seed)
    xx, yy = _grid(n, n)
    dx, dy = xx - n / 2, yy - n / 2
    rr = np.hypot(dx, dy) / (n * 0.42)
    th = np.arctan2(dy, dx)
    rays = np.zeros_like(th)
    for _ in range(40):
        a0 = r.random() * 2 * np.pi
        wdt = 0.03 + 0.1 * r.random()
        dth = np.angle(np.exp(1j * (th - a0)))
        rays = np.maximum(rays, (0.05 + 0.12 * r.random()) * np.exp(-(dth / wdt) ** 2))
    patch = _noise(n, n, 1.8, seed + 1, fmin=2)
    rw = rr * (1 - rays) + 0.3 * (patch - 0.5)
    soot = np.clip(1 - rw, 0, 1) ** 1.4 * (0.75 + 0.35 * _noise(n, n, 1.2, seed + 2))
    char = _ss(0.55, 0.8, np.clip(1 - rw, 0, 1)) * _ss(0.35, 0.6, patch + 0.3)
    f1, f2, _ = T.worley(n, 900, seed + 3)
    crackle = (1 - _ss(0.0, 1.8, f2 - f1)) * char
    speck = _ss(0.8, 0.92, _noise(n, n, 0.5, seed + 4)) * _ss(0.1, 0.4, soot) * _ss(0.8, 0.4, soot)
    heat = np.exp(-((rw - 0.95) / 0.12) ** 2) * 0.35
    a = np.clip(soot * 1.15 + speck * 0.5 + heat, 0, 1) * _border_fade(n, n, 0.04)
    c = T.lerp(np.ones((n, n, 3), np.float32) * _hex("#6a4c30")[None, None], _hex("#1c1814")[None, None],
               _ss(0.05, 0.45, soot)[..., None])
    c = T.lerp(c, _hex("#0a0908")[None, None], char[..., None])
    c = T.lerp(c, _hex("#2e2824")[None, None], (crackle * 0.7)[..., None])
    hgt = char * (0.3 + 0.4 * _noise(n, n, 1.0, seed + 5)) - crackle * 0.5
    _save(out, c, a, height=_blur(hgt, 0.8), strength=4.0, rough=0.96 - 0.08 * crackle)


def _jagged_path(r, start, ang, length, step=3.0, jag=0.45, pull=0.12):
    pts = [np.array(start, np.float64)]
    a = ang
    for _ in range(int(length / step)):
        a = a + r.normal(0, jag)
        a = a + (ang - a) * pull
        pts.append(pts[-1] + step * np.array([np.cos(a), np.sin(a)]))
    return np.array(pts)


@texture("decal_crack_wall", size=1024, seed=5301, kind="pbr_alpha")
def decal_crack_wall(size: int, seed: int, out) -> None:
    """Plaster / concrete crack: a jagged primary fissure of varying width, a few short branches and
    hairlines, flakes spalled off along it exposing lighter material; V-groove in the normal map."""
    n = size
    r = _rng(seed)
    xx, yy = _grid(n, n)
    paths = [(_jagged_path(r, (n * 0.06, n * 0.16), 0.7, n * 1.6, jag=0.35, pull=0.08), 3.2)]
    main = paths[0][0]
    for _ in range(5):
        i = r.integers(len(main) // 6, len(main) * 5 // 6)
        a0 = np.arctan2(*(main[min(i + 3, len(main) - 1)] - main[i])[::-1]) + r.choice([-1, 1]) * (0.5 + 0.7 * r.random())
        paths.append((_jagged_path(r, main[i], a0, n * (0.06 + 0.2 * r.random())), 1.4 + 0.8 * r.random()))
    for _ in range(6):
        i = r.integers(0, len(main))
        a0 = r.random() * 2 * np.pi
        paths.append((_jagged_path(r, main[i], a0, n * (0.03 + 0.08 * r.random()), jag=0.5), 0.6))
    core = np.zeros((n, n), np.float32)
    groove = np.zeros((n, n), np.float32)

    def disk(dx, dy, p):
        return _ss(p["r"] + 1.0, p["r"] - 0.4, np.hypot(dx, dy))

    def grv(dx, dy, p):
        return np.clip(1 - np.hypot(dx, dy) / p["r"], 0, 1) ** 2

    wn = _noise1(4096, 1.6, seed + 3)
    for pts, w0 in paths:
        seg = np.hypot(np.diff(pts[:, 0]), np.diff(pts[:, 1]))
        cum = np.concatenate([[0], np.cumsum(seg)])
        sm = np.arange(0, cum[-1], 0.7)
        px_ = np.interp(sm, cum, pts[:, 0])
        py_ = np.interp(sm, cum, pts[:, 1])
        t = sm / max(cum[-1], 1e-6)
        wv = w0 * (0.55 + 0.9 * wn[(np.arange(sm.size) * 3) % 4096]) * (1 - 0.65 * t) + 0.35
        _stamp_max(core, px_, py_, int(np.ceil(wv.max() * 2 + 6)), disk, {"r": wv})
        gr = wv * 3.0 + 3
        _stamp_max(groove, px_, py_, int(np.ceil(gr.max() * 2 + 4)), grv, {"r": gr})
    # spalls: small Voronoi flakes next to the main crack, randomly missing
    f1, f2, cid = T.worley(n, 7000, seed + 4)
    near = ndimage.distance_transform_edt(core < 0.5)
    flake_on = ((np.sin(cid * 12.9898) * 43758.5453) % 1.0) < 0.42
    chips = (near < 12) & flake_on & (near > 0.5)
    chips = _blur(chips.astype(np.float32), 0.7)
    a = np.clip(core + chips * 0.9 + groove * 0.3, 0, 1) * _border_fade(n, n, 0.03)
    c = np.ones((n, n, 3), np.float32) * _hex("#8a8478")[None, None]
    c = T.lerp(c, _hex("#c4bfb2")[None, None], (chips * (0.6 + 0.4 * _noise(n, n, 1.0, seed + 5)))[..., None])
    c = T.lerp(c, _hex("#5e5a52")[None, None], (groove * 0.55)[..., None])
    c = T.lerp(c, _hex("#121110")[None, None], core[..., None])
    hgt = -(core * 1.0 + groove * 0.35 + chips * 0.4)
    ao = 1 - 0.7 * core - 0.3 * groove
    _save(out, c, a, height=_blur(hgt, 0.7), strength=5.0, rough=0.9, ao=ao)


@texture("decal_bullet_holes", size=1024, seed=5302, kind="pbr_alpha")
def decal_bullet_holes(size: int, seed: int, out) -> None:
    """Cluster of bullet impacts (authored for ~1 m: bores ~1 cm, craters 3-7 cm): dark bore, an
    irregular spalled crater of chipped flakes exposing fresh light material, grey bullet-wipe soot,
    a few hairline cracks."""
    n = size
    r = _rng(seed)
    xx, yy = _grid(n, n)
    hgt = np.zeros((n, n), np.float32)
    bore = np.zeros((n, n), np.float32)
    crater = np.zeros((n, n), np.float32)
    smudge = np.zeros((n, n), np.float32)
    cracks = np.zeros((n, n), np.float32)
    f1, f2, cid = T.worley(n, 9000, seed + 9)
    cell_r = ((np.sin(cid * 78.233) * 43758.5453) % 1.0).astype(np.float32)
    holes = [(0.35, 0.33), (0.58, 0.42), (0.46, 0.58), (0.68, 0.66), (0.3, 0.7), (0.62, 0.22), (0.78, 0.45)]
    for (hx, hy) in holes:
        cx = hx * n + (r.random() - 0.5) * 40
        cy = hy * n + (r.random() - 0.5) * 40
        br = 4.5 + 2.5 * r.random()
        cr = br * (3.2 + 3.0 * r.random())
        x0, x1 = int(max(0, cx - cr * 3)), int(min(n, cx + cr * 3))
        y0, y1 = int(max(0, cy - cr * 3)), int(min(n, cy + cr * 3))
        sl = (slice(y0, y1), slice(x0, x1))
        sx, sy = xx[sl], yy[sl]
        d = np.hypot(sx - cx, sy - cy)
        th = np.arctan2(sy - cy, sx - cx)
        # crater = flakes (Voronoi cells) whose centre falls inside a noisy radius
        lim = cr * (0.75 + 0.5 * cell_r[sl])
        crat = _blur(((d < lim) & (d > br * 0.6)).astype(np.float32), 0.6)
        prof = -np.clip(1 - d / (cr * 1.05), 0, 1) ** 1.4 * 0.6 * crat
        b = _ss(br + 1.0, br - 1.0, d)
        prof = prof - b * 0.9
        sm = np.exp(-((d - cr * 1.1) / (cr * 0.55)) ** 2) * 0.45 * (0.6 + 0.4 * np.cos(th * 3 + r.random() * 6))
        rad = np.zeros_like(d)
        for _ in range(r.integers(2, 5)):
            a0 = r.random() * 2 * np.pi
            L = cr * (1.3 + 1.5 * r.random())
            dth = np.abs(np.angle(np.exp(1j * (th - a0 - 0.05 * np.sin(d * 0.25)))))
            rad = np.maximum(rad, _ss(1.0, 0.2, dth * d) * (d < L) * (d > cr * 0.7) * (1 - d / L))
        hgt[sl] = np.minimum(hgt[sl], prof - rad * 0.12)
        bore[sl] = np.maximum(bore[sl], b)
        crater[sl] = np.maximum(crater[sl], crat)
        smudge[sl] = np.maximum(smudge[sl], sm)
        cracks[sl] = np.maximum(cracks[sl], rad)
    fine = _noise(n, n, 0.7, seed + 3)
    a = np.clip(crater * 0.95 + smudge * 0.55 + cracks * 0.7 + bore, 0, 1) * _border_fade(n, n, 0.03)
    c = np.ones((n, n, 3), np.float32) * _hex("#4a4844")[None, None]
    c = T.lerp(c, _hex("#bdb6a8")[None, None], (crater * (0.65 + 0.35 * fine))[..., None])
    depth_dark = np.clip(-hgt, 0, 1)
    c = c * (1 - 0.5 * depth_dark)[..., None]
    c = T.lerp(c, _hex("#383634")[None, None], (cracks * 0.8)[..., None])
    c = T.lerp(c, _hex("#0c0b0a")[None, None], bore[..., None])
    ao = np.clip(1 - 0.8 * depth_dark - 0.6 * bore, 0, 1)
    _save(out, c, a, height=_blur(hgt, 0.6), strength=12.0, rough=0.88 - 0.2 * smudge, ao=ao)


# --------------------------------------------------------------------------------------------------
# Survivor marks (spray paint): arrows, crosses, circles, tallies -- no words
# --------------------------------------------------------------------------------------------------


def _spray(n: int, strokes: list[np.ndarray], r: np.random.Generator, *, width: float, seed: int,
           drips: float = 1.0, shake: float = 3.0) -> np.ndarray:
    """Simulates a spray can: shaky stroke paths deposit a gaussian core + wide overspray + droplet
    speckle; where paint pools past a threshold it runs downward. Returns paint density 0..~1."""
    xx, yy = _grid(n, n)
    dens = np.zeros((n, n), np.float32)
    wob = _noise1(4096, 2.0, seed)
    for si, pts in enumerate(strokes):
        L = np.hypot(np.diff(pts[:, 0]), np.diff(pts[:, 1])).sum()
        k = max(8, int(L / 6))
        t = np.linspace(0, 1, k)
        seg = np.concatenate([[0], np.cumsum(np.hypot(np.diff(pts[:, 0]), np.diff(pts[:, 1])))])
        seg = seg / max(seg[-1], 1e-6)
        px = np.interp(t, seg, pts[:, 0])
        py = np.interp(t, seg, pts[:, 1])
        off = (si * 997) % 3000
        nx = (wob[(off + np.arange(k)) % 4096] - 0.5) * 2 * shake
        ny = (wob[(off + 500 + np.arange(k)) % 4096] - 0.5) * 2 * shake
        px, py = px + nx, py + ny
        spd = 0.75 + 0.5 * wob[(off + 1000 + np.arange(k)) % 4096]
        start_heavy = np.exp(-t * 10) * 0.8 + np.exp(-(1 - t) * 12) * 0.5
        m = width * 10 + 2
        x0, x1 = int(max(0, px.min() - m)), int(min(n, px.max() + m + 1))
        y0, y1 = int(max(0, py.min() - m)), int(min(n, py.max() + m + 1))
        if x1 <= x0 or y1 <= y0:
            continue
        d, pos = _stroke_dist(xx[y0:y1, x0:x1], yy[y0:y1, x0:x1], np.stack([px, py], 1))
        wloc = width * np.interp(pos, t, spd)
        core = np.exp(-(d / wloc) ** 4)
        over = np.exp(-(d / (wloc * 3.2)) ** 2) * 0.12
        heavy = np.interp(pos, t, start_heavy)
        dens[y0:y1, x0:x1] = np.maximum(dens[y0:y1, x0:x1], core * (0.85 + 0.6 * heavy) + over)
    # overspray droplets
    sp = _noise(n, n, 0.15, seed + 7)
    halo = _ss(0.02, 0.25, _blur(dens, width * 1.5))
    dens = np.maximum(dens, (sp > 0.93) * halo * 0.7)
    # runs where it pooled
    if drips > 0:
        excess = np.clip(dens - 1.05, 0, None)
        if excess.max() > 0:
            ys, xs = np.nonzero(excess > 0.05)
            sel = r.choice(len(xs), min(len(xs), 24), replace=False) if len(xs) else []
            for i in sel:
                L = (30 + 160 * r.random()) * drips * float(excess[ys[i], xs[i]] + 0.3)
                wdt = width * (0.2 + 0.15 * r.random())
                x0, y0 = xs[i] + 0.5, ys[i] + 0.5
                y1 = min(n - 10, y0 + L)
                yl, yh = int(y0), int(min(n, y1 + wdt * 4))
                xl, xh = int(max(0, x0 - 12)), int(min(n, x0 + 12))
                if yh <= yl or xh <= xl:
                    continue
                sx, sy = xx[yl:yh, xl:xh], yy[yl:yh, xl:xh]
                t = np.clip((sy - y0) / max(y1 - y0, 1), 0, 1)
                wd = wdt * (1 - 0.5 * t)
                run = (sy <= y1) * _ss(wd + 0.8, wd - 0.4, np.abs(sx - x0)) * 0.9
                bulb = _ss(wdt * 1.4 + 0.8, wdt * 1.4 - 0.5, np.hypot(sx - x0, sy - y1)) * 0.95
                dens[yl:yh, xl:xh] = np.maximum(dens[yl:yh, xl:xh], np.maximum(run, bulb))
    return dens


def _paint_save(out, n, dens, colour: str, seed: int, alpha=0.95):
    a = (1 - np.exp(-3.2 * dens)) * alpha
    var = _noise(n, n, 1.2, seed + 11)
    a = a * (0.82 + 0.18 * var) * _border_fade(n, n, 0.03)
    c = np.ones((n, n, 3), np.float32) * _hex(colour)[None, None]
    c = c * (0.9 + 0.15 * var)[..., None]
    _save(out, c, a)


def _arc(cx, cy, rad, a0, a1, k=40, wob=0.0, r=None):
    t = np.linspace(a0, a1, k)
    rr = rad * (1 + (wob * (r.random(k) - 0.5) if r is not None else 0))
    return np.stack([cx + np.cos(t) * rr, cy + np.sin(t) * rr], 1)


@texture("decal_survivor_marks_a", size=1024, seed=5401, kind="albedo")
def decal_survivor_marks_a(size: int, seed: int, out) -> None:
    """Red spray-paint arrow pointing right with two groups of tally marks under it."""
    n = size
    r = _rng(seed)
    strokes = [np.array([[0.12, 0.34], [0.45, 0.32], [0.74, 0.335]]) * n,
               np.array([[0.62, 0.2], [0.78, 0.33], [0.64, 0.47]]) * n]
    tx = 0.2
    for g in range(2):
        for i in range(4):
            x = tx + g * 0.3 + i * 0.045 + (r.random() - 0.5) * 0.01
            strokes.append(np.array([[x, 0.58 + (r.random() - 0.5) * 0.02], [x + 0.01, 0.78 + (r.random() - 0.5) * 0.02]]) * n)
        strokes.append(np.array([[tx + g * 0.3 - 0.03, 0.74], [tx + g * 0.3 + 0.18, 0.6]]) * n)
    for i in range(3):
        x = 0.8 + i * 0.045
        strokes.append(np.array([[x, 0.59], [x + 0.008, 0.77]]) * n)
    dens = _spray(n, strokes, r, width=n * 0.011, seed=seed, drips=1.0, shake=3.5)
    _paint_save(out, n, dens, "#8e1712", seed)


@texture("decal_survivor_marks_b", size=1024, seed=5402, kind="albedo")
def decal_survivor_marks_b(size: int, seed: int, out) -> None:
    """White spray-paint circle crossed with an X (danger / cleared), dripping."""
    n = size
    r = _rng(seed)
    circle = _arc(n * 0.5, n * 0.48, n * 0.32, -2.2, -2.2 + 2 * np.pi * 0.97, 60, 0.04, r)
    strokes = [circle, np.array([[0.27, 0.24], [0.5, 0.47], [0.74, 0.73]]) * n,
               np.array([[0.73, 0.22], [0.5, 0.49], [0.26, 0.74]]) * n]
    dens = _spray(n, strokes, r, width=n * 0.013, seed=seed, drips=1.4, shake=4.0)
    _paint_save(out, n, dens, "#d8d6cf", seed, alpha=0.92)


@texture("decal_survivor_marks_c", size=1024, seed=5403, kind="albedo")
def decal_survivor_marks_c(size: int, seed: int, out) -> None:
    """Faded orange spray marks: a triangle with a dot (shelter sign), a downward arrow and three
    dots, plus a long scratch tally line."""
    n = size
    r = _rng(seed)
    tri = np.array([[0.2, 0.62], [0.36, 0.3], [0.52, 0.62], [0.2, 0.625]]) * n
    dot = _arc(n * 0.36, n * 0.53, n * 0.012, 0, 2 * np.pi, 12)
    arrow = [np.array([[0.72, 0.18], [0.73, 0.58]]) * n, np.array([[0.62, 0.47], [0.73, 0.6], [0.84, 0.46]]) * n]
    dots = [_arc(n * (0.62 + i * 0.1), n * 0.78, n * 0.01, 0, 2 * np.pi, 10) for i in range(3)]
    tally = [np.array([[0.14 + i * 0.035, 0.84], [0.15 + i * 0.035, 0.93]]) * n for i in range(6)]
    strokes = [tri, dot] + arrow + dots + tally
    dens = _spray(n, strokes, r, width=n * 0.01, seed=seed, drips=0.8, shake=3.0)
    fade = 0.55 + 0.45 * _ss(0.3, 0.7, _noise(n, n, 1.5, seed + 3))
    _paint_save(out, n, dens * fade, "#c2541c", seed, alpha=0.9)


# --------------------------------------------------------------------------------------------------
# Muddy boot prints
# --------------------------------------------------------------------------------------------------


def _sole(u, v, left: bool):
    """Boot sole SDF in normalised coords (u along length -0.5..0.5 heel->toe, v across)."""
    if left:
        v = -v
    fore = np.hypot((u - 0.2) / 0.3, (v - 0.02) / 0.19) - 1
    heel = np.hypot((u + 0.31) / 0.19, v / 0.155) - 1
    waist = np.maximum(np.abs(v + 0.01) / 0.13 - 1, np.abs(u + 0.05) / 0.22 - 1)
    return np.minimum(np.minimum(fore, heel), waist)


@texture("decal_footprints_mud", size=1024, seed=5501, kind="pbr_alpha")
def decal_footprints_mud(size: int, seed: int, out) -> None:
    """Two muddy boot prints (left/right, walking toward -V): lug-block tread (chevron rows under the
    forefoot, blocks at the heel), blotchy uneven mud transfer heavier at heel and ball, ragged
    outline, raised mud deposit. Authored for ~1.1 m."""
    n = size
    r = _rng(seed)
    xx, yy = _grid(n, n)
    dep = np.zeros((n, n), np.float32)
    L = n * 0.27
    blot = _noise(n, n, 1.7, seed + 1)
    fine = _noise(n, n, 0.6, seed + 2)
    edge_n = _noise(n, n, 1.2, seed + 3)
    for k, (fx, fy, left, ang) in enumerate(((0.38, 0.68, True, -1.62), (0.6, 0.31, False, -1.52))):
        cx, cy = fx * n, fy * n
        ca, sa = np.cos(ang), np.sin(ang)
        u = ((xx - cx) * ca + (yy - cy) * sa) / L
        v = (-(xx - cx) * sa + (yy - cy) * ca) / L
        sd = _sole(u, v, left) + 0.09 * (edge_n - 0.5)
        inside = _ss(0.02, -0.03, sd)
        fore = u > -0.12
        uc = np.where(fore, u + 0.55 * np.abs(v), u)
        ru = uc / 0.075
        row = np.floor(ru)
        fu = ru - row - 0.5
        cv = v / 0.085 + 0.5 * (row % 2)
        fv = cv - np.floor(cv) - 0.5
        lug = _ss(0.36, 0.28, np.abs(fu)) * _ss(0.42, 0.33, np.abs(fv))
        rim = _ss(-0.1, -0.06, sd) * 0.6
        tread = np.maximum(lug, rim * 0.9)
        heavy = np.exp(-((u + 0.3) / 0.15) ** 2) + 0.9 * np.exp(-((u - 0.2) / 0.18) ** 2)
        transfer = np.clip(1.6 * (blot - 0.38) + 0.35 * (fine - 0.5), 0, 1) * (0.4 + 0.7 * heavy)
        dep = np.maximum(dep, inside * (tread * 0.8 + 0.1) * transfer)
    dep = dep * (0.7 + 0.5 * fine)
    a = _ss(0.06, 0.38, dep) * _border_fade(n, n, 0.03)
    c = T.gradient(np.clip(0.55 * dep + 0.45 * _noise(n, n, 1.5, seed + 5), 0, 1),
                   [(0.0, "#6e5e4a"), (0.5, "#4c3e2e"), (1.0, "#30271d")])
    rough = 0.85 - 0.3 * _ss(0.35, 0.9, dep)
    _save(out, c, a, height=_blur(dep, 0.8) * 0.6, strength=3.0, rough=rough)
