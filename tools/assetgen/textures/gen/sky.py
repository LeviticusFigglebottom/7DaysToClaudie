"""Sky textures: tileable cloud noise, an equirectangular star field with a faint galactic band, and the
moon disc.

sky_cloud_noise  2048^2 RGBA, linear, tileable. Channels are increasingly fine "Perlin-Worley" octaves:
                 R = base shapes (billowy, ~3-12 features per tile), G = mid, B = fine, A = erosion
                 detail. A cloud shader typically does: base = remap(R, ...); detail = mix(B, A, ...);
                 density = saturate(remap(base, detail * k, 1, 0, 1)).
sky_stars        4096 x 2048 equirect (u = longitude 0..1 wraps, v = 0 at the zenith/north pole),
                 black background, additive. Imported lossless without mip-maps (import_kind "ui"):
                 block compression smears single-pixel stars and bands the faint galactic glow. Stars are rendered on the sphere so they stay round
                 at every latitude; the galactic band is tilted ~62 deg to the equator.
moon_disc        1024^2 RGBA, full-moon albedo seen orthographically (alpha = disc), north up.
"""
from __future__ import annotations

import pathlib

import numpy as np
from scipy import ndimage

from .. import texlib as T
from ..registry import texture


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed & 0xFFFFFFFF)


def _ss(e0, e1, x):
    return T.smoothstep(e0, e1, x)


def _hex(h: str) -> np.ndarray:
    return T.hex_rgb(h).astype(np.float32)


def _remap(a: np.ndarray, gamma: float = 1.0) -> np.ndarray:
    """Normalise to 0..1 by robust percentiles, then gamma so the median lands near 0.5."""
    lo, hi = np.percentile(a, [0.3, 99.7])
    a = np.clip((a - lo) / max(hi - lo, 1e-9), 0, 1)
    med = float(np.median(a))
    if 0 < med < 1:
        a = a ** float(np.clip(np.log(0.5) / np.log(med), 0.5, 2.0))
    return a.astype(np.float32)


# --------------------------------------------------------------------------------------------------
# Clouds
# --------------------------------------------------------------------------------------------------

def _billow(n: int, cells: int, seed: int) -> np.ndarray:
    f1, _, _ = T.worley(n, cells, seed)
    cell = n / np.sqrt(cells)
    return np.clip(1 - f1 / (cell * 0.9), 0, 1) ** 1.5


@texture("sky_cloud_noise", size=2048, seed=8101, kind="single", import_kind="data")
def sky_cloud_noise(size: int, seed: int, out) -> None:
    n = size
    perlin_lo = T.spectral(n, 2.0, seed + 1, fmin=2, fmax=24)
    perlin_mid = T.spectral(n, 1.6, seed + 2, fmin=8, fmax=96)
    perlin_hi = T.spectral(n, 1.3, seed + 3, fmin=32, fmax=320)
    perlin_x = T.spectral(n, 1.0, seed + 4, fmin=100, fmax=900)
    # Perlin-Worley: perlin dilated by inverted worley gives billowy cauliflower tops
    w1 = 0.6 * _billow(n, 24, seed + 5) + 0.4 * _billow(n, 96, seed + 6)
    w2 = 0.6 * _billow(n, 96, seed + 7) + 0.4 * _billow(n, 384, seed + 8)
    w3 = _billow(n, 1500, seed + 9)
    R = _remap(perlin_lo * 0.55 + w1 * 0.45 + 0.15 * perlin_lo * w1)
    G = _remap(perlin_mid * 0.5 + w2 * 0.5)
    B = _remap(perlin_hi * 0.5 + w3 * 0.5)
    A = _remap(perlin_x)
    T.save_rgba(pathlib.Path(str(out) + ".png"), np.stack([R, G, B, A], -1))


# --------------------------------------------------------------------------------------------------
# Stars
# --------------------------------------------------------------------------------------------------

def _value_noise3(p: np.ndarray, seed: int, lattice: int = 64) -> np.ndarray:
    """Smooth 3-D value noise at points p (..., 3) (any real coords; lattice wraps every `lattice`)."""
    r = _rng(seed)
    g = r.random((lattice, lattice, lattice)).astype(np.float32)
    i0 = np.floor(p).astype(np.int64)
    f = (p - i0).astype(np.float32)
    f = f * f * (3 - 2 * f)
    out = np.zeros(p.shape[:-1], np.float32)
    for dx in (0, 1):
        wx = f[..., 0] if dx else 1 - f[..., 0]
        for dy in (0, 1):
            wy = f[..., 1] if dy else 1 - f[..., 1]
            for dz in (0, 1):
                wz = f[..., 2] if dz else 1 - f[..., 2]
                out += wx * wy * wz * g[(i0[..., 0] + dx) % lattice, (i0[..., 1] + dy) % lattice, (i0[..., 2] + dz) % lattice]
    return out


def _fbm3(p: np.ndarray, seed: int, octaves: int = 5, base: float = 2.0, gain: float = 0.5) -> np.ndarray:
    out = np.zeros(p.shape[:-1], np.float32)
    amp, tot, fr = 1.0, 0.0, base
    for o in range(octaves):
        out += amp * _value_noise3(p * fr + 17.3 * o, seed + 31 * o)
        tot += amp
        amp *= gain
        fr *= 2.03
    return out / tot


def _galactic_frame():
    """Unit vectors of the galactic frame expressed in sky coordinates (y = up / north pole)."""
    tilt = np.radians(62.0)
    gn = np.array([0.0, np.cos(tilt), np.sin(tilt)])          # galactic north pole
    gc = np.array([np.cos(np.radians(30)), 0.0, 0.0])
    gc = gc - gn * gc.dot(gn)
    gc /= np.linalg.norm(gc)                                    # galactic centre direction
    gy = np.cross(gn, gc)
    return gn, gc, gy


@texture("sky_stars", size=4096, seed=8201, kind="single", import_kind="ui")
def sky_stars(size: int, seed: int, out) -> None:
    W, H = size, size // 2
    r = _rng(seed)
    gn, gc, gy = _galactic_frame()
    # --- galactic band (computed at half resolution, smooth) -------------------------------------
    w2, h2 = W // 2, H // 2
    lon = (np.arange(w2) + 0.5) / w2 * 2 * np.pi
    lat = np.pi / 2 - (np.arange(h2) + 0.5) / h2 * np.pi
    LON, LAT = np.meshgrid(lon, lat)
    d = np.stack([np.cos(LAT) * np.cos(LON), np.sin(LAT), np.cos(LAT) * np.sin(LON)], -1).astype(np.float32)
    gb = np.arcsin(np.clip(d @ gn, -1, 1))
    gl = np.arctan2(d @ gy, d @ gc)
    width = np.radians(9.0) * (1 + 0.9 * np.exp(-(gl / 0.6) ** 2))
    band = np.exp(-(gb / width) ** 2)
    bright = 0.45 + 0.55 * np.exp(-(gl / 1.1) ** 2)
    clouds = _fbm3(d * 3.0, seed + 1, 6)
    clumps = _ss(0.35, 0.75, clouds)
    lanes = _fbm3(d * 5.0, seed + 2, 5)
    rift = np.exp(-((gb - np.radians(1.5) * np.sin(gl * 2)) / (width * 0.35)) ** 2) * _ss(0.4, 0.7, lanes)
    glow = band * bright * (0.35 + 0.65 * clumps) * (1 - 0.75 * rift)
    glow = ndimage.zoom(glow.astype(np.float32), 2, order=1, mode="grid-wrap", grid_mode=True)
    gcol = np.stack([0.80 + 0.06 * glow, 0.78 + 0.04 * glow, 0.86 - 0.02 * glow], -1)
    img = gcol * (glow * 0.075)[..., None]
    # --- stars -------------------------------------------------------------------------------------
    N = 26000
    u = r.random(N * 2)
    z = 2 * u - 1
    ph = r.random(N * 2) * 2 * np.pi
    pts = np.stack([np.sqrt(1 - z * z) * np.cos(ph), z, np.sqrt(1 - z * z) * np.sin(ph)], -1)
    # extra concentration toward the galactic plane
    gbp = np.abs(np.arcsin(np.clip(pts @ gn, -1, 1)))
    keep = r.random(N * 2) < (0.35 + 0.65 * np.exp(-(gbp / np.radians(14)) ** 2))
    pts = pts[keep][:N]
    n = pts.shape[0]
    mag = r.random(n) ** 3.2
    b = 0.05 + 1.6 * mag ** 2.2
    bright_idx = r.choice(n, 45, replace=False)
    b[bright_idx] = 1.2 + 2.5 * r.random(45)
    pal = np.stack([_hex(h) for h in ["#a9bcff", "#cad7ff", "#f8f7ff", "#fff4e8", "#ffe7c4", "#ffd0a0", "#ffb38a"]])
    w = np.array([0.6, 1.0, 2.0, 1.6, 1.2, 0.7, 0.35])
    ci = r.choice(len(pal), n, p=w / w.sum())
    col = pal[ci] * (0.85 + 0.3 * r.random(n))[:, None]
    slat = np.arcsin(np.clip(pts[:, 1], -1, 1))
    slon = np.mod(np.arctan2(pts[:, 2], pts[:, 0]), 2 * np.pi)
    sx = slon / (2 * np.pi) * W
    sy = (np.pi / 2 - slat) / np.pi * H
    sig = 0.55 + 0.6 * np.clip(b - 0.4, 0, 2) ** 0.5
    stretch = 1 / np.maximum(np.cos(slat), 0.04)
    acc = np.zeros((H, W, 3), np.float32)
    flat = acc.reshape(-1, 3)
    for k in range(n):
        sxk = sig[k] * stretch[k]
        rx = int(np.ceil(sxk * 3.2)) + 1
        ry = int(np.ceil(sig[k] * 3.2)) + 1
        x0, y0 = int(np.floor(sx[k])), int(np.floor(sy[k]))
        xs = np.arange(x0 - rx, x0 + rx + 1)
        ys = np.arange(max(0, y0 - ry), min(H, y0 + ry + 1))
        if ys.size == 0:
            continue
        gx = np.exp(-0.5 * ((xs + 0.5 - sx[k]) / sxk) ** 2)
        gyy = np.exp(-0.5 * ((ys + 0.5 - sy[k]) / sig[k]) ** 2)
        wgt = (gyy[:, None] * gx[None, :]).astype(np.float32)
        wgt *= b[k] / max(wgt.sum(), 1e-6) * (2 * np.pi * sig[k] * sig[k]) ** 0.5
        idx = (ys[:, None] * W + (xs[None, :] % W)).ravel()
        np.add.at(flat, idx, (wgt.ravel()[:, None] * col[k][None, :]))
    img = img + acc
    img = 1 - np.exp(-img * 1.4)
    # dither: the band is very faint, keep 8-bit quantisation from drawing contour lines
    img = img + (r.random(img.shape[:2]).astype(np.float32)[..., None] - 0.5) / 255.0
    T.save_rgb(pathlib.Path(str(out) + ".png"), np.clip(img, 0, 1))


# --------------------------------------------------------------------------------------------------
# Moon
# --------------------------------------------------------------------------------------------------

def _dir(lon_deg: float, lat_deg: float) -> np.ndarray:
    lo, la = np.radians(lon_deg), np.radians(lat_deg)
    return np.array([np.cos(la) * np.sin(lo), np.sin(la), np.cos(la) * np.cos(lo)], np.float32)


# approximate near-side maria: (selenographic lon, lat, angular radius deg, elongation)
MARIA = [(-17, 33, 18, 1.0), (17, 28, 10, 1.0), (30, 8, 13, 1.2), (59, 17, 8, 1.2), (51, -4, 10, 0.8),
         (34, -15, 6, 1.0), (-55, 10, 24, 0.55), (-17, -20, 10, 1.1), (-39, -24, 6, 1.0), (0, 57, 6, 3.5),
         (4, 13, 5, 1.0), (-38, -2, 9, 0.8), (-23, 50, 5, 1.6)]


@texture("moon_disc", size=1024, seed=8301, kind="single", import_kind="albedo")
def moon_disc(size: int, seed: int, out) -> None:
    n = size
    r = _rng(seed)
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    R = n * 0.47
    x = (xx + 0.5 - n / 2) / R
    y = -(yy + 0.5 - n / 2) / R
    rr = np.sqrt(x * x + y * y)
    rc = np.maximum(rr, 1.0)            # outside the disc: evaluate on the limb (clean colour bleed)
    z = np.sqrt(np.clip(1 - rr * rr, 0, 1))
    P = np.stack([x / rc, y / rc, z], -1)
    # maria: soft spherical caps with noisy outlines
    edge_n = _fbm3(P * 4.0, seed + 1, 5)
    mare = np.zeros((n, n), np.float32)
    for lon, lat, rad, el in MARIA:
        c = _dir(lon, lat)
        ang = np.degrees(np.arccos(np.clip(P @ c, -1, 1)))
        # elongation along the local east-west direction
        east = np.cross(np.array([0, 1, 0], np.float32), c)
        if np.linalg.norm(east) < 1e-3:
            east = np.array([1, 0, 0], np.float32)
        east /= np.linalg.norm(east)
        th_e = np.degrees(np.arcsin(np.clip(P @ east, -1, 1)))
        th_n2 = np.maximum(ang * ang - th_e * th_e, 0)
        ang = np.sqrt(th_n2 + (th_e / el) ** 2)
        m = _ss(rad * 1.35, rad * 0.45, ang + (edge_n - 0.5) * rad * 1.1) * (0.75 + 0.25 * _ss(rad, rad * 0.4, ang))
        mare = np.maximum(mare, m)
    # craters (on the sphere): dark floor, bright rim, ejecta; fewer inside maria
    cr_rim = np.zeros((n, n), np.float32)
    cr_floor = np.zeros((n, n), np.float32)
    rays = np.zeros((n, n), np.float32)
    cnt = 700
    v = r.normal(size=(cnt * 3, 3))
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    v = v[v[:, 2] > 0.05][:cnt]
    sizes = 0.3 + 4.5 * r.random(v.shape[0]) ** 7
    for k in range(v.shape[0]):
        c = v[k].astype(np.float32)
        rad = np.radians(sizes[k])
        # local window in pixels around the projected centre
        cx, cy = c[0] * R + n / 2, -c[1] * R + n / 2
        wpx = int(rad * R * 2.2) + 3
        x0, x1 = int(max(0, cx - wpx)), int(min(n, cx + wpx))
        y0, y1 = int(max(0, cy - wpx)), int(min(n, cy + wpx))
        if x1 <= x0 or y1 <= y0:
            continue
        sub = P[y0:y1, x0:x1]
        ang = np.arccos(np.clip(sub @ c, -1, 1)) / rad
        rim = np.exp(-((ang - 1.0) / 0.12) ** 2)
        floor = _ss(1.0, 0.7, ang)
        cr_rim[y0:y1, x0:x1] = np.maximum(cr_rim[y0:y1, x0:x1], rim * (0.6 + 0.4 * r.random()))
        cr_floor[y0:y1, x0:x1] = np.maximum(cr_floor[y0:y1, x0:x1], floor * (0.3 + 0.4 * r.random()))
    # ray systems: Tycho, Copernicus, Kepler
    for lon, lat, cnt_r, length in ((-11, -43, 26, 70.0), (-20, 10, 18, 28.0), (-38, 8, 12, 18.0)):
        c = _dir(lon, lat)
        ang_d = np.degrees(np.arccos(np.clip(P @ c, -1, 1)))
        north = np.array([0, 1, 0], np.float32) - c * c[1]
        north /= np.linalg.norm(north)
        east = np.cross(north, c)
        az = np.arctan2(P @ east, P @ north)
        ray = np.zeros((n, n), np.float32)
        for _ in range(cnt_r):
            a0 = r.random() * 2 * np.pi
            wdt = 0.03 + 0.09 * r.random()
            dth = np.abs(np.angle(np.exp(1j * (az - a0))))
            L = length * (0.35 + 0.65 * r.random())
            ray = np.maximum(ray, np.exp(-(dth / wdt) ** 2) * np.exp(-(ang_d / L) ** 2) * _ss(0.5, 2.0, ang_d)
                             * (0.4 + 0.6 * r.random()))
        halo = np.exp(-(ang_d / (length * 0.12)) ** 2)
        rays = np.maximum(rays, ray * 0.8 + halo * 0.6)
    tex = _fbm3(P * 9.0, seed + 2, 5)
    fine = _fbm3(P * 40.0, seed + 3, 3)
    high = T.gradient(np.clip(0.6 * tex + 0.4 * fine, 0, 1), [(0.0, "#8c8984"), (0.5, "#a7a39b"), (1.0, "#c2bdb2")])
    mar = T.gradient(np.clip(0.6 * tex + 0.4 * fine, 0, 1), [(0.0, "#55575a"), (0.5, "#636466"), (1.0, "#737270")])
    mvar = _fbm3(P * 5.0, seed + 4, 4)
    mare = np.clip(mare * (0.8 + 0.4 * mvar), 0, 1)
    mar = mar * (0.88 + 0.24 * mvar)[..., None] * (1 + np.stack([-0.02, 0.0, 0.03]) * (mvar - 0.5)[..., None] * 2)
    col = high * (1 - mare[..., None]) + mar * mare[..., None]
    col = col * (1 - 0.07 * cr_floor * (1 - mare))[..., None] + 0.035 * cr_rim[..., None] * (1 - 0.5 * mare[..., None])
    col = col + (np.array([0.86, 0.84, 0.8], np.float32) - col) * (0.38 * np.clip(rays, 0, 1))[..., None]
    col = col * (0.9 + 0.1 * z)[..., None]
    a = _ss(1.0 + 1.0 / R, 1.0 - 1.0 / R, rr)
    T.save_rgba(pathlib.Path(str(out) + ".png"), np.concatenate([np.clip(col, 0, 1), a[..., None]], -1))
