"""Terrain surface layers (boreal valley in autumn) + terrain helper maps.

Contract with the terrain shader: game/data/materials/terrain_layers.json (layer order, tile sizes).
Outputs
  terrain_albedo_array  RGBA strip (RGB albedo sRGB, A = height 0..1 for height blending)
  terrain_normal_array  RGB strip, tangent space OpenGL (+Y up)
  terrain_orm_array     RGB strip (R = AO, G = roughness, B = metallic = 0)
  terrain_<layer>       per-layer PBR set (preview / prop use; same pixels as the array slice)
  terrain_macro_variation, terrain_detail_normal

Every layer is built physically: a height field in metres at the real texel size (tile_m / size),
litter / stones / cracks are rasterised objects composited with a z-buffer (so needles lie on
leaves, twigs on needles ...), normals come from that height at true scale, AO from multi-scale
horizon estimates. Everything is periodic (wrap-around stamping, FFT noise) so tiles are seamless.
"""
from __future__ import annotations

import json
import pathlib

import numpy as np
from scipy import ndimage

from .. import texlib as T
from ..registry import texture

# --------------------------------------------------------------------------------------------------
# Layer contract (must match game/data/materials/terrain_layers.json; checked when the arrays build)
# --------------------------------------------------------------------------------------------------
LAYERS = ["forest_floor", "moss_ground", "grass_ground", "dirt", "mud", "gravel", "rock_cliff", "sand",
          "snow", "asphalt_cracked", "concrete_slab"]
TILE_M = {"forest_floor": 3.0, "moss_ground": 2.5, "grass_ground": 2.5, "dirt": 2.5, "mud": 3.0, "gravel": 2.0,
          "rock_cliff": 6.0, "sand": 2.0, "snow": 3.0, "asphalt_cracked": 4.0, "concrete_slab": 4.0}
# Mean linear albedo luminance per layer (measured-material ballpark values).
TARGET_LUM = {"forest_floor": 0.085, "moss_ground": 0.085, "grass_ground": 0.13, "dirt": 0.10, "mud": 0.055,
              "gravel": 0.17, "rock_cliff": 0.16, "sand": 0.21, "snow": 0.72, "asphalt_cracked": 0.075,
              "concrete_slab": 0.24}
LAYERS_JSON = pathlib.Path(__file__).resolve().parents[4] / "game" / "data" / "materials" / "terrain_layers.json"


# --------------------------------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------------------------------

def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed & 0xFFFFFFFF)


def _cols(hexes) -> np.ndarray:
    return np.stack([T.hex_rgb(h) for h in hexes]).astype(np.float32)


def _pal(r: np.random.Generator, count: int, hexes, weights=None, jit: float = 0.08, blend: float = 0.5) -> np.ndarray:
    """Per-object colours: weighted palette pick, blended toward a second pick, brightness jitter."""
    cols = _cols(hexes)
    w = np.asarray(weights if weights is not None else [1.0] * len(hexes), np.float64)
    w = w / w.sum()
    i = r.choice(len(cols), count, p=w)
    j = r.choice(len(cols), count, p=w)
    t = (r.random(count) * blend)[:, None]
    c = cols[i] * (1 - t) + cols[j] * t
    c *= (1.0 + (r.random(count) - 0.5) * 2.0 * jit)[:, None]
    return c.astype(np.float32)


def _sample(field: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    n0, n1 = field.shape[:2]
    return field[np.floor(y).astype(np.int64) % n0, np.floor(x).astype(np.int64) % n1]


def _bilinear(field: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    return ndimage.map_coordinates(field, [np.asarray(y) - 0.5, np.asarray(x) - 0.5], order=1, mode="grid-wrap")


def _points(r: np.random.Generator, n: int, count: int, density: np.ndarray | None = None,
            power: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """`count` random points (pixel coords) distributed by a periodic density field in [0, 1]."""
    if count <= 0:
        return np.zeros(0, np.float64), np.zeros(0, np.float64)
    if density is None:
        return r.random(count) * n, r.random(count) * n
    xs, ys, got = [], [], 0
    while got < count:
        m = int((count - got) * 3) + 64
        x = r.random(m) * n
        y = r.random(m) * n
        keep = r.random(m) < np.clip(_sample(density, x, y), 0, 1) ** power
        xs.append(x[keep])
        ys.append(y[keep])
        got += int(keep.sum())
    return np.concatenate(xs)[:count], np.concatenate(ys)[:count]


def _jittered(r: np.random.Generator, n: int, k: int, jitter: float = 0.8, keep: float = 1.0):
    """Stratified (blue-ish noise) points: one per k x k cell, randomly dropped with 1-keep."""
    g = (np.arange(k) + 0.5) * (n / k)
    X, Y = np.meshgrid(g, g)
    X = X.ravel() + (r.random(k * k) - 0.5) * jitter * n / k
    Y = Y.ravel() + (r.random(k * k) - 0.5) * jitter * n / k
    m = r.random(k * k) < keep
    return X[m] % n, Y[m] % n


def _spec(n: int, beta: float, seed: int, fmin: float = 1.0, fmax: float | None = None, aniso=(1.0, 1.0)) -> np.ndarray:
    return T.spectral(n, beta, seed, fmin=fmin, fmax=fmax, anisotropy=aniso)


def _band(n: int, f0: float, f1: float, seed: int, beta: float = 1.0) -> np.ndarray:
    """Band-limited periodic noise with features between f0..f1 cycles per tile, normalized 0..1."""
    return T.spectral(n, beta, seed, fmin=f0, fmax=f1)


def _fft_gauss(shape, s: float) -> np.ndarray:
    fy = np.fft.fftfreq(shape[0])[:, None]
    fx = np.fft.rfftfreq(shape[1])[None, :]
    return np.exp(-2 * np.pi ** 2 * s * s * (fy * fy + fx * fx))


def _blur(a: np.ndarray, s: float) -> np.ndarray:
    """Periodic gaussian blur (exact wrap). FFT for large sigmas, separable filter for small ones."""
    if s <= 0:
        return a
    if s > 5.0:
        g = _fft_gauss(a.shape[:2], s)
        if a.ndim == 3:
            return np.fft.irfft2(np.fft.rfft2(a, axes=(0, 1)) * g[..., None], s=a.shape[:2], axes=(0, 1)).astype(np.float32)
        return np.fft.irfft2(np.fft.rfft2(a) * g, s=a.shape).astype(np.float32)
    if a.ndim == 3:
        return np.stack([ndimage.gaussian_filter(a[..., c], s, mode="wrap") for c in range(a.shape[2])], -1)
    return ndimage.gaussian_filter(a, s, mode="wrap")


def _lum(c: np.ndarray) -> np.ndarray:
    return c[..., 0] * 0.2126 + c[..., 1] * 0.7152 + c[..., 2] * 0.0722


def _ss(e0, e1, x):
    return T.smoothstep(e0, e1, x)


# --------------------------------------------------------------------------------------------------
# Ground: z-buffered object compositing on a periodic canvas (height in metres)
# --------------------------------------------------------------------------------------------------

TAG_BASE, TAG_UNDER, TAG_NEEDLE, TAG_LEAF, TAG_TWIG, TAG_CONE, TAG_BARK, TAG_MOSS, TAG_STONE, TAG_GRASS, \
    TAG_LICHEN, TAG_WATER, TAG_MISC = range(13)


class Ground:
    def __init__(self, n: int, tile_m: float):
        self.n = n
        self.px = tile_m / n  # metres per texel
        self.h = np.zeros(n * n, np.float32)
        self.col = np.zeros((n * n, 3), np.float32)
        self.rough = np.full(n * n, 0.9, np.float32)
        self.tag = np.zeros(n * n, np.uint8)

    # views
    def H(self) -> np.ndarray:
        return self.h.reshape(self.n, self.n)

    def C(self) -> np.ndarray:
        return self.col.reshape(self.n, self.n, 3)

    def R(self) -> np.ndarray:
        return self.rough.reshape(self.n, self.n)

    def TAG(self) -> np.ndarray:
        return self.tag.reshape(self.n, self.n)

    def smooth(self, sigma: float) -> np.ndarray:
        return _blur(self.H(), sigma)

    def m(self, metres: float) -> float:
        """metres -> pixels"""
        return metres / self.px

    # ---------------------------------------------------------------------------------------------
    def composite(self, idx, cov, hz, col, rough, tag: int, *, opaque: float = 0.97) -> None:
        """Writes object pixels that are above the current surface. Fully covered pixels are
        z-buffered (highest object wins); partially covered (anti-aliased) pixels are blended with an
        order-independent 'over' (transmittance product + coverage-weighted mean colour), so thin
        needles/blades get smooth edges and overlapping fringes never drop each other."""
        shp = cov.shape
        idx = np.broadcast_to(idx, shp).reshape(-1)
        cov = cov.reshape(-1)
        sel = cov > 0.008
        if not sel.any():
            return
        idx = idx[sel]
        cov = cov[sel]
        hz = np.broadcast_to(hz, shp).reshape(-1)[sel].astype(np.float32)
        col = np.broadcast_to(col, shp + (3,)).reshape(-1, 3)[sel]
        rough = np.broadcast_to(rough, shp).reshape(-1)[sel]
        above = hz > self.h[idx]
        op = above & (cov >= opaque)
        if op.any():
            oi = idx[op]
            oz = hz[op]
            zb = self.h.copy()
            np.maximum.at(zb, oi, oz)
            win = oz >= zb[oi]
            wi = oi[win]
            self.h[wi] = oz[win]
            self.col[wi] = col[op][win]
            self.rough[wi] = rough[op][win]
            self.tag[wi] = tag
        fr = above & ~op
        if fr.any():
            fi = idx[fr]
            fz = hz[fr]
            keep = fz > self.h[fi]
            fi = fi[keep]
            fz = fz[keep]
            a = np.minimum(cov[fr][keep], 0.995).astype(np.float64)
            c = col[fr][keep]
            ro = rough[fr][keep]
            N = self.h.size
            sa = np.bincount(fi, a, N)
            u = np.nonzero(sa)[0]
            if u.size == 0:
                return
            tr = np.exp(np.bincount(fi, np.log1p(-a), N)[u])
            inv = 1.0 / sa[u]
            cb = 1.0 - tr
            for k in range(3):
                ck = np.bincount(fi, a * c[:, k], N)[u] * inv
                self.col[u, k] = self.col[u, k] * tr + ck * cb
            hk = np.bincount(fi, a * fz, N)[u] * inv
            self.h[u] = self.h[u] * tr + hk * cb
            rk = np.bincount(fi, a * ro, N)[u] * inv
            self.rough[u] = self.rough[u] * tr + rk * cb
            self.tag[u[cb > 0.5]] = tag

    # ---------------------------------------------------------------------------------------------
    def _grid(self, cx, cy, P):
        n = self.n
        ox = np.floor(cx).astype(np.int64) - P // 2
        oy = np.floor(cy).astype(np.int64) - P // 2
        g = np.arange(P, dtype=np.int64)
        X = ox[:, None, None] + g[None, None, :]
        Y = oy[:, None, None] + g[None, :, None]
        dx = (X + 0.5 - cx[:, None, None]).astype(np.float32)
        dy = (Y + 0.5 - cy[:, None, None]).astype(np.float32)
        idx = (Y % n) * n + (X % n)
        return idx, dx, dy

    def polylines(self, xs, ys, r0, r1, z, dz, c0, c1, rough, tag: int, *, flat: float = 0.0,
                  drape: np.ndarray | None = None, chunk_px: int = 1_500_000, opaque: float = 0.97,
                  rib: float = 0.0) -> None:
        """Tapered round strokes along polylines xs, ys (cnt, K+1) in pixels. Each segment is stamped in
        its own small patch with butt joints (round caps only at the stroke ends), so long thin strokes
        are cheap and anti-aliased joints never double up.
        r0/r1 radius px at start/end, z base height (m) per object or per vertex (cnt, K+1), dz thickness
        (m), c0/c1 colour at start/end, flat: 0 round cross-section .. 1 flat strip, drape: smoothed
        height map added to z per pixel (stroke follows the ground)."""
        xs = np.asarray(xs, np.float64)
        ys = np.asarray(ys, np.float64)
        if xs.ndim == 1:
            xs, ys = xs[:, None], ys[:, None]
        cnt, kp = xs.shape
        if cnt == 0:
            return
        K = kp - 1
        f32 = np.float32
        bc = lambda a, shp: np.broadcast_to(np.asarray(a, f32), shp)  # noqa: E731
        r0, r1, dz, rough = bc(r0, (cnt,)), bc(r1, (cnt,)), bc(dz, (cnt,)), bc(rough, (cnt,))
        z = np.asarray(z, f32)
        zv = bc(z[:, None] if z.ndim == 1 else z, (cnt, kp)) if z.ndim else bc(z, (cnt, kp))
        c0, c1 = bc(c0, (cnt, 3)), bc(c1, (cnt, 3))
        # flatten to segments
        j = np.tile(np.arange(K), cnt)
        o = np.repeat(np.arange(cnt), K)
        s0 = (j / K).astype(f32)
        s1 = ((j + 1) / K).astype(f32)
        ax, ay = xs[:, :-1].ravel(), ys[:, :-1].ravel()
        bx, by = xs[:, 1:].ravel(), ys[:, 1:].ravel()
        ra = r0[o] + (r1[o] - r0[o]) * s0
        rb = r0[o] + (r1[o] - r0[o]) * s1
        za, zb = zv[:, :-1].ravel(), zv[:, 1:].ravel()
        ca = c0[o] + (c1[o] - c0[o]) * s0[:, None]
        cb = c0[o] + (c1[o] - c0[o]) * s1[:, None]
        capa = j == 0
        capb = j == K - 1
        ext = np.maximum(np.abs(bx - ax), np.abs(by - ay)) + 2 * np.maximum(ra, rb) + 4
        Pk = (np.ceil(ext / 4) * 4).astype(np.int64)
        for P in np.unique(Pk):
            ids = np.nonzero(Pk == P)[0]
            step = max(1, chunk_px // int(P * P))
            for st in range(0, ids.size, step):
                k = ids[st:st + step]
                cx = (ax[k] + bx[k]) * 0.5
                cy = (ay[k] + by[k]) * 0.5
                idx, dx, dy = self._grid(cx, cy, int(P))
                e = lambda a: a[k].astype(f32)[:, None, None]  # noqa: E731
                pax, pay = e(ax - (ax + bx) * 0.5), e(ay - (ay + by) * 0.5)
                abx, aby = e(bx - ax), e(by - ay)
                l2 = np.maximum(abx * abx + aby * aby, f32(1e-6))
                px_ = dx - pax
                py_ = dy - pay
                t = (px_ * abx + py_ * aby) / l2
                tc = np.clip(t, 0, 1)
                qx = px_ - tc * abx
                qy = py_ - tc * aby
                d = np.sqrt(qx * qx + qy * qy)
                rr = e(ra) + (e(rb) - e(ra)) * tc
                cov = np.where(rr >= 0.5, np.clip(rr + 0.5 - d, 0, 1), 2 * rr * np.clip(1 - d, 0, 1))
                valid = ((t >= 0) | capa[k][:, None, None]) & ((t < 1) | capb[k][:, None, None])
                cov = cov * valid
                prof = np.sqrt(np.clip(1 - (d / np.maximum(rr, f32(0.5))) ** 2, 0, 1))
                if flat:
                    prof = prof + (1 - prof) * f32(flat)
                zz = e(za) + (e(zb) - e(za)) * tc
                if drape is not None:
                    zz = zz + drape.reshape(-1)[idx]
                hz = zz + e(dz[o]) * prof
                cka = ca[k][:, None, None, :]
                ckb = cb[k][:, None, None, :]
                col = cka + (ckb - cka) * tc[..., None]
                if rib:
                    # lighter core / darker margins: reads as a rounded needle or a folded blade
                    col = col * (1 + f32(rib) * (0.5 - np.clip(d / np.maximum(rr, f32(0.5)), 0, 1)))[..., None]
                ro = np.broadcast_to(e(rough[o]), cov.shape)
                self.composite(idx, cov, hz, col, ro, tag, opaque=opaque)

    def segments(self, x0, y0, x1, y1, r0, r1, z, dz, c0, c1, rough, tag: int, **kw) -> None:
        xs = np.stack([np.asarray(x0, np.float64), np.asarray(x1, np.float64)], 1)
        ys = np.stack([np.asarray(y0, np.float64), np.asarray(y1, np.float64)], 1)
        self.polylines(xs, ys, r0, r1, z, dz, c0, c1, rough, tag, **kw)

    def shapes(self, cx, cy, P: int, fn, params: dict, tag: int, *, z=None, drape: np.ndarray | None = None,
               chunk_px: int = 2_500_000) -> None:
        """Generic stamp: fn(dx, dy, p, idx) -> (cov, hz_rel, col (..,3), rough) with p = params sliced
        to the chunk, each shaped (b,1,1) (or (b,1,1,3) for colours)."""
        cx = np.asarray(cx, np.float64)
        cy = np.asarray(cy, np.float64)
        cnt = cx.size
        if cnt == 0:
            return
        step = max(1, chunk_px // (P * P))
        for s in range(0, cnt, step):
            sl = slice(s, s + step)
            idx, dx, dy = self._grid(cx[sl], cy[sl], P)
            p = {}
            for k, v in params.items():
                v = np.asarray(v)
                v = v[sl].astype(np.float32) if v.dtype.kind == "f" else v[sl]
                p[k] = v[:, None, None, :] if v.ndim == 2 else v[:, None, None]
            cov, hrel, col, ro = fn(dx, dy, p, idx)
            if drape is not None:
                base = drape.reshape(-1)[idx]
                if z is not None:
                    base = base + np.asarray(z, np.float32)[sl][:, None, None]
            else:
                base = np.asarray(z, np.float32)[sl][:, None, None]
            hz = base + hrel
            ro = np.broadcast_to(ro, cov.shape)
            col = np.broadcast_to(col, cov.shape + (3,))
            self.composite(idx, cov, hz, col, ro, tag)


def _polyline(r, x, y, ang, length, segs: int, bend: float):
    """Random gently-curving polylines: returns arrays (cnt, segs+1) of x, y."""
    cnt = x.size
    step = (length / segs)[:, None]
    dang = (r.random((cnt, segs)) - 0.5) * 2 * bend
    dang[:, 0] = 0
    a = ang[:, None] + np.cumsum(dang, 1)
    xs = np.concatenate([np.zeros((cnt, 1)), np.cumsum(np.cos(a) * step, 1)], 1)
    ys = np.concatenate([np.zeros((cnt, 1)), np.cumsum(np.sin(a) * step, 1)], 1)
    xs -= xs[:, -1:] * 0.5
    ys -= ys[:, -1:] * 0.5
    return xs + x[:, None], ys + y[:, None]


# --------------------------------------------------------------------------------------------------
# Object recipes (litter)
# --------------------------------------------------------------------------------------------------

def _envelope(G: Ground, size: int = 3, sigma: float = 1.0) -> np.ndarray:
    """Smoothed upper envelope of the current surface: rigid litter rests on this."""
    mx = ndimage.maximum_filter(G.H(), size=size, mode="wrap")
    return _blur(mx, sigma)


def _vertex_z(env: np.ndarray, xs: np.ndarray, ys: np.ndarray, lift) -> np.ndarray:
    """Per-vertex resting height (cnt, K+1) sampled from an envelope."""
    z = _bilinear(env, xs.ravel(), ys.ravel()).reshape(xs.shape).astype(np.float32)
    return z + np.asarray(lift, np.float32).reshape(-1, 1) if np.ndim(lift) else z + lift


def _age_colors(r, x, y, age, stops, jit=0.15, bright=0.08):
    a = np.clip(_sample(age, x, y) + jit * r.standard_normal(x.size), 0, 1) if age is not None else r.random(x.size)
    c = T.gradient(a, stops).astype(np.float32)
    return c * (1.0 + bright * r.standard_normal(x.size)).clip(0.75, 1.3)[:, None]


def _needles(G: Ground, r, count, density, stops, lengths_m, radius_px, *, age=None, age_jit=0.15, pair=0.0,
             mode="rest", lift=0.0003, thick_m=0.0011, bend=0.25, rough=(0.76, 0.9), tag=TAG_NEEDLE, dark_tip=0.25,
             align=None, align_amt=0.0, env=None, segs=2, x=None, y=None, rib=0.2):
    """Conifer needles (slightly curved, darker tip). Colour from an age field through `stops`.
    mode 'rest': each vertex rests on the litter envelope (needle lies on top, then gets covered by later
    passes); 'drape': follows the smoothed surface and is partly buried by bumps (matted under-layer).
    pair = fraction emitted as 2-needle fascicles (pine)."""
    n = G.n
    if x is None:
        x, y = _points(r, n, count, density)
    count = x.size
    ang = r.random(count) * 2 * np.pi
    if align is not None and align_amt > 0:
        a0 = _sample(align, x, y) * 4 * np.pi
        ang = np.where(r.random(count) < align_amt, a0 + (r.random(count) - 0.5) * 0.8, ang)
    L = G.m(1.0) * (lengths_m[0] + (lengths_m[1] - lengths_m[0]) * r.random(count))
    col = _age_colors(r, x, y, age, stops, age_jit)
    tip = col * (1.0 - dark_tip * (0.5 + 0.5 * r.random(count)))[:, None]
    base = col * (1.0 + 0.10 * r.random(count))[:, None]
    rad = radius_px[0] + (radius_px[1] - radius_px[0]) * r.random(count)
    ro = rough[0] + (rough[1] - rough[0]) * r.random(count)
    np_ = int(count * pair)
    if np_ > 0:
        sel = r.choice(count, np_, replace=False)
        bx = x[sel] - np.cos(ang[sel]) * L[sel] * 0.5
        by = y[sel] - np.sin(ang[sel]) * L[sel] * 0.5
        a2 = ang[sel] + np.where(r.random(np_) < 0.5, -1, 1) * (0.12 + 0.35 * r.random(np_))
        x = np.concatenate([x, bx + np.cos(a2) * L[sel] * 0.5])
        y = np.concatenate([y, by + np.sin(a2) * L[sel] * 0.5])
        ang = np.concatenate([ang, a2])
        L = np.concatenate([L, L[sel] * (0.95 + 0.05 * r.random(np_))])
        tip = np.concatenate([tip, tip[sel]])
        base = np.concatenate([base, base[sel] * 0.97])
        rad = np.concatenate([rad, rad[sel]])
        ro = np.concatenate([ro, ro[sel]])
    xs, ys = _polyline(r, x, y, ang, L, segs, bend)
    dz = np.full(x.size, thick_m, np.float32)
    if mode == "drape":
        z = (lift + r.random(x.size) * 0.0005).astype(np.float32)
        G.polylines(xs, ys, rad, rad * 0.6, z, dz, base, tip, ro, tag, drape=G.smooth(1.2), rib=rib)
    else:
        env = env if env is not None else _envelope(G, 3, 1.0)
        z = _vertex_z(env, xs, ys, lift)
        G.polylines(xs, ys, rad, rad * 0.6, z, dz, base, tip, ro, tag, rib=rib)


def _twigs(G: Ground, r, count, len_m, rad_m, stops, *, branch=0.6, density=None, tag=TAG_TWIG, age=None, segs=5,
           bend=0.35, lichen=0.0):
    n = G.n
    x, y = _points(r, n, count, density)
    ang = r.random(count) * 2 * np.pi
    L = G.m(1.0) * (len_m[0] + (len_m[1] - len_m[0]) * r.random(count) ** 1.6)
    rad = G.m(1.0) * (rad_m[0] + (rad_m[1] - rad_m[0]) * r.random(count))
    col = _age_colors(r, x, y, age, stops, 0.3, 0.1)
    xs, ys = _polyline(r, x, y, ang, L, segs, bend)
    env = _envelope(G, 5, 2.0)
    dz = (rad * G.px * 2.0).astype(np.float32)
    z = _vertex_z(env, xs, ys, -dz * 0.25)
    ro = 0.8 + 0.1 * r.random(count)
    G.polylines(xs, ys, rad, rad * 0.55, z, dz, col * 1.05, col * 0.88, ro, tag)
    nb = int(count * branch * 2)
    if nb:
        par = r.integers(0, count, nb)
        tpos = 0.15 + 0.6 * r.random(nb)
        seg = np.minimum((tpos * segs).astype(int), segs - 1)
        fr = tpos * segs - seg
        bx = xs[par, seg] + (xs[par, seg + 1] - xs[par, seg]) * fr
        by = ys[par, seg] + (ys[par, seg + 1] - ys[par, seg]) * fr
        bz = z[par, seg] + (z[par, seg + 1] - z[par, seg]) * fr
        pa = np.arctan2(ys[par, -1] - ys[par, 0], xs[par, -1] - xs[par, 0])
        ba = pa + np.where(r.random(nb) < 0.5, -1, 1) * (0.45 + 0.5 * r.random(nb))
        bl = L[par] * (0.1 + 0.28 * r.random(nb))
        brad = np.maximum(rad[par] * (0.45 + 0.2 * r.random(nb)), 0.32)
        bxs = bx[:, None] + np.cos(ba)[:, None] * bl[:, None] * np.array([0.0, 0.5, 1.0])[None, :]
        bys = by[:, None] + np.sin(ba)[:, None] * bl[:, None] * np.array([0.0, 0.5, 1.0])[None, :]
        bxs[:, 2] += np.cos(ba + 1.57) * bl * 0.06 * (r.random(nb) - 0.5)
        bys[:, 2] += np.sin(ba + 1.57) * bl * 0.06 * (r.random(nb) - 0.5)
        bzv = np.stack([bz, bz - dz[par] * 0.3, bz - dz[par] * 0.6], 1).astype(np.float32)
        G.polylines(bxs, bys, brad, brad * 0.5, bzv, dz[par] * 0.55, col[par] * 1.0, col[par] * 0.85, ro[par], tag)


def _leaf_fn(noise):
    """Pinnate leaf (birch/aspen/bilberry/willow-like): serrated outline, petiole, midrib + lateral veins,
    decay blotches, darker margins, cupped/curled relief."""
    nflat = noise.reshape(-1)

    def fn(dx, dy, p, idx):
        ca, sa = np.cos(p["ang"]), np.sin(p["ang"])
        u = dx * ca + dy * sa
        v = -dx * sa + dy * ca
        L, W = p["L"], p["W"]
        s = np.clip(u / L + 0.5, 0, 1)
        shape = np.maximum(np.sin(np.pi * s), 0) ** p["round"] * (1.0 - p["tipk"] * s)
        teeth = 1.0 - p["serr"] * (0.5 + 0.5 * np.cos(2 * np.pi * p["teeth"] * s))
        vv = v - p["asym"] * L * (s - 0.5) ** 2
        w = 0.5 * W * shape * teeth
        sd_leaf = np.maximum(np.abs(vv) - w, np.abs(u) - L * 0.5)
        pl = p["pet"]
        sd_pet = np.maximum(np.abs(v) - 0.4, np.maximum(-(u + L * 0.5) - pl, (u + L * 0.5) - 1.0))
        sd = np.minimum(sd_leaf, sd_pet)
        cov = np.clip(0.5 - sd, 0, 1)
        an = np.clip(np.abs(vv) / np.maximum(w, 0.6), 0, 1)
        mid = np.clip(1.0 - np.abs(vv) / 0.6, 0, 1) * (s < 0.97)
        lat = np.abs(((s * p["nv"] - an * 0.6 + 0.25) % 1.0) - 0.5)
        lat = np.clip(1.0 - lat / 0.11, 0, 1) * (an < 0.9) * (s > 0.05) * (s < 0.93)
        nz = nflat[idx]
        blot = np.clip((nz - p["spot"]) * 5.0, 0, 1)
        grain = nflat[(idx * 7919 + 13) % nflat.size]
        col = p["col"] * (1.0 + 0.10 * (0.5 - an) + 0.07 * (grain - 0.5))[..., None]
        col = col + (p["vcol"] - col) * (np.maximum(mid * 0.55, lat * 0.22))[..., None]
        col = col + (p["dcol"] - col) * (blot * 0.85)[..., None]
        edge = np.clip((an - 0.75) / 0.25, 0, 1) * p["edgedark"]
        col = col + (p["dcol"] - col) * (0.6 * edge)[..., None]
        hrel = p["thick"] + p["curl"] * an ** 2 + p["fold"] * (1 - an) - 0.00015 * lat
        ro = p["rough"] - 0.06 * (1 - blot) + 0.0 * cov
        return cov, hrel, col, ro
    return fn


LEAF_SPECS = {
    # length m, width/length, serration, teeth, roundness exp, tip taper, palette, weights
    "birch": (0.052, 0.72, 0.10, 16, 0.75, 0.40, ["#bf9c40", "#b8963c", "#a97a32", "#c6a552", "#957236", "#755a34"],
              [3, 3, 2, 2, 1.5, 1.2]),
    "aspen": (0.056, 0.95, 0.07, 11, 0.62, 0.18, ["#c49f42", "#b57834", "#9a4e30", "#b28a3c", "#7c5230"],
              [3, 2, 1.2, 2, 1.2]),
    "bilberry": (0.03, 0.62, 0.04, 12, 0.85, 0.30, ["#843024", "#94402a", "#743026", "#9e5a32", "#683c2a"],
                 [3, 2, 2, 1, 1]),
    "willow": (0.080, 0.28, 0.03, 22, 0.90, 0.45, ["#b49a44", "#9a8a3c", "#7e6a34", "#c2a34a"], [2, 2, 1, 1]),
    "dead": (0.05, 0.75, 0.08, 14, 0.7, 0.3, ["#5e4632", "#4e3a2a", "#6a5038", "#433428"], [2, 2, 1, 1]),
    "herb": (0.032, 0.36, 0.05, 9, 0.9, 0.35, ["#5f6e30", "#6d7a36", "#556428", "#7a6a34", "#7c4a30"], [3, 2, 2, 1, 0.6]),
    "clover": (0.012, 0.95, 0.0, 1, 0.55, 0.0, ["#4f6a2c", "#5c7634", "#486026"], [2, 2, 1]),
}


def _leaves(G: Ground, r, count, kind_w: dict, density=None, noise=None, lift=0.0005, age_bias=0.0, size=1.0,
            x=None, y=None, ang=None, tag=TAG_LEAF):
    """Leaves lie on the litter (drape on a smoothed envelope); later passes partly cover them."""
    n = G.n
    if x is None:
        x, y = _points(r, n, count, density)
    count = x.size
    kinds = list(kind_w.keys())
    w = np.array([kind_w[k] for k in kinds], float)
    w /= w.sum()
    ki = r.choice(len(kinds), count, p=w)
    L = np.zeros(count)
    W = np.zeros(count)
    serr = np.zeros(count)
    teeth = np.zeros(count)
    rnd = np.zeros(count)
    tipk = np.zeros(count)
    col = np.zeros((count, 3), np.float32)
    for i, k in enumerate(kinds):
        m = ki == i
        c = int(m.sum())
        if not c:
            continue
        lm, wr, se, te, ro_, tk, pal, pw = LEAF_SPECS[k]
        L[m] = G.m(lm) * size * (0.75 + 0.5 * r.random(c))
        W[m] = L[m] * wr * (0.85 + 0.3 * r.random(c))
        serr[m] = se
        teeth[m] = te
        rnd[m] = ro_
        tipk[m] = tk
        col[m] = _pal(r, c, pal, pw, jit=0.08, blend=0.35)
    age = np.clip(r.random(count) + age_bias, 0, 1)
    dark = _cols(["#3b2a1d"])[0]
    col = col * (1 - 0.55 * age[:, None] ** 2.5) + dark * (0.55 * age[:, None] ** 2.5)
    col = col * 0.82 + _cols(["#6a4a2c"])[0] * 0.18
    curled = r.random(count) < 0.18
    W = np.where(curled, W * 0.6, W)
    params = {
        "ang": r.random(count) * 2 * np.pi if ang is None else np.asarray(ang), "L": L, "W": W, "serr": serr,
        "teeth": teeth, "round": rnd, "tipk": tipk, "asym": (r.random(count) - 0.5) * 0.12,
        "pet": L * (0.12 + 0.12 * r.random(count)), "nv": np.clip(L / 3.5, 3, 9) * (0.9 + 0.2 * r.random(count)),
        "spot": 0.66 + 0.25 * r.random(count) - 0.3 * age, "col": col,
        "vcol": np.clip(col * 1.18 + 0.02, 0, 1),
        "dcol": dark[None, :].repeat(count, 0) * (0.75 + 0.5 * r.random(count))[:, None] + col * 0.15,
        "edgedark": 0.25 + 0.75 * r.random(count) * (0.3 + age),
        "thick": np.full(count, 0.0004),
        "curl": np.where(curled, 0.004 + 0.003 * r.random(count), 0.0006 + 0.0018 * r.random(count) ** 2),
        "fold": 0.0006 * r.random(count),
        "rough": 0.66 + 0.2 * r.random(count) + 0.08 * age,
    }
    noise = noise if noise is not None else _spec(n, 1.6, 977)
    P = int(np.ceil(L.max() * 1.3 + 6) // 2 * 2)
    env = np.maximum(_blur(_envelope(G, 7, 2.0), 2.0), G.H() + 0.0002)
    G.shapes(x, y, P, _leaf_fn(noise), params, tag, z=np.full(count, lift), drape=env)


def _cone_fn(noise):
    nflat = noise.reshape(-1)

    def fn(dx, dy, p, idx):
        ca, sa = np.cos(p["ang"]), np.sin(p["ang"])
        u = dx * ca + dy * sa
        v = -dx * sa + dy * ca
        s = u / (p["L"] * 0.5)
        wfac = 1.0 + p["egg"] * s
        t = v / (p["W"] * 0.5 * np.maximum(wfac, 0.3))
        r2 = s * s + t * t
        sd = (np.sqrt(r2) - 1.0) * np.minimum(p["W"] * 0.5, p["L"] * 0.5)
        cov = np.clip(0.5 - sd, 0, 1)
        dome = np.sqrt(np.clip(1 - r2, 0, 1))
        phi = np.arcsin(np.clip(t, -1, 1))
        a = s * p["rows"] + phi * p["spir"]
        b = s * p["rows"] - phi * p["spir"]
        sc = (0.5 + 0.5 * np.cos(2 * np.pi * a)) * (0.5 + 0.5 * np.cos(2 * np.pi * b))
        gap = 1.0 - np.clip((sc - 0.04) / 0.3, 0, 1)
        lip = np.clip(np.sin(2 * np.pi * (a + b) * 0.5 + 1.2), 0, 1) * (1 - gap)
        nz = nflat[idx]
        col = p["col"] * (0.72 + 0.4 * dome[..., None]) * (1.0 + 0.1 * (nz[..., None] - 0.5))
        col = col * (1 - 0.45 * gap[..., None]) + (p["tcol"] - col) * (0.35 * lip[..., None])
        hrel = p["H"] * (dome ** 0.8) + 0.0012 * sc * dome
        ro = 0.8 + 0.12 * gap
        return cov, hrel, col, ro
    return fn


def _cones(G: Ground, r, count, *, x=None, y=None, spruce_frac=0.7, scale=1.0):
    n = G.n
    if x is None:
        x, y = _jittered(r, n, int(np.ceil(np.sqrt(count * 1.3))), 0.9, keep=count / max(1, int(np.ceil(np.sqrt(count * 1.3))) ** 2))
    count = x.size
    spruce = r.random(count) < spruce_frac
    L = np.where(spruce, G.m(0.065) + G.m(0.04) * r.random(count), G.m(0.042) + G.m(0.018) * r.random(count)) * scale
    W = np.where(spruce, L * (0.36 + 0.06 * r.random(count)), L * (0.62 + 0.1 * r.random(count)))
    col = np.where(spruce[:, None], _pal(r, count, ["#8a5f3a", "#7a5232", "#94683f", "#6e4a2e"], jit=0.1),
                   _pal(r, count, ["#6e5842", "#7a6249", "#5e4a38"], jit=0.1))
    tcol = col * 0.5 + _cols(["#c0a07a"])[0] * 0.5
    age = r.random(count)
    col = col * (1 - 0.35 * age[:, None]) + _cols(["#4a4038"])[0] * (0.35 * age[:, None])
    params = {"ang": r.random(count) * 2 * np.pi, "L": L, "W": W, "egg": np.where(spruce, -0.12, -0.25) + 0.05 * r.random(count),
              "rows": np.clip(L * 0.5 / 3.6, 2.5, 8), "spir": np.clip(W * 0.5 / 3.6, 1.0, 4),
              "col": col, "tcol": tcol,
              "H": W * G.px * (0.85 + 0.15 * r.random(count))}
    P = int(np.ceil(L.max() * 1.2 + 6) // 2 * 2)
    env = _blur(_envelope(G, 7, 3.0), 4.0)
    z = _bilinear(env, x, y).astype(np.float32) - 0.003
    G.shapes(x, y, P, _cone_fn(_spec(n, 1.2, 4242)), params, TAG_CONE, z=z)


def _blob_fn(noise, kind: str = "flake", noise2=None):
    """Irregular objects with a harmonic-perturbed elliptic outline.
    kind: 'pebble' rounded dome, 'flake' flat bark plate with cracks, 'clod' lumpy earth clump,
    'lichen' porous coral-like clump (Cladonia)."""
    nflat = noise.reshape(-1)
    n2 = (noise2 if noise2 is not None else noise).reshape(-1)

    def fn(dx, dy, p, idx):
        ca, sa = np.cos(p["ang"]), np.sin(p["ang"])
        u = dx * ca + dy * sa
        v = -dx * sa + dy * ca
        th = np.arctan2(v / p["ry"], u / p["rx"])
        rr = 1.0 + p["h1"] * np.cos(2 * th + p["p1"]) + p["h2"] * np.cos(3 * th + p["p2"]) + p["h3"] * np.cos(5 * th + p["p3"])
        q = np.sqrt((u / p["rx"]) ** 2 + (v / p["ry"]) ** 2) / rr
        nz = nflat[idx]
        if kind in ("lichen", "clod"):
            q = q + 0.35 * (n2[idx] - 0.5)
        sd = (q - 1.0) * np.minimum(p["rx"], p["ry"])
        cov = np.clip(0.5 - sd, 0, 1)
        if kind == "pebble":
            dome = np.sqrt(np.clip(1 - q * q, 0, 1)) ** p["sharp"]
            hrel = p["H"] * dome
            col = p["col"] * (0.86 + 0.24 * dome[..., None]) * (1 + 0.16 * (nz[..., None] - 0.5))
        elif kind == "lichen":
            dome = np.sqrt(np.clip(1 - q * q, 0, 1))
            holes = np.clip((0.42 - nz) / 0.14, 0, 1)
            hrel = p["H"] * dome ** 0.6 * (0.7 + 0.3 * nz)
            col = p["col"] * (0.8 + 0.28 * dome[..., None]) * (1 - 0.6 * holes[..., None])
        elif kind == "clod":
            dome = np.sqrt(np.clip(1 - q * q, 0, 1)) ** 0.7
            hrel = p["H"] * dome * (0.8 + 0.4 * nz)
            col = p["col"] * (0.85 + 0.3 * dome[..., None]) * (1 + 0.25 * (nz[..., None] - 0.5))
        else:  # flake: flat top, rounded rim, cracks
            dome = np.clip((1 - q) * 3.0, 0, 1)
            crack = np.clip(1 - np.abs(((u * 0.35 + nz * 3) % 1.0) - 0.5) / 0.08, 0, 1)
            hrel = p["H"] * dome * (1 - 0.3 * crack)
            col = p["col"] * (1 + 0.2 * (nz[..., None] - 0.5)) * (1 - 0.35 * crack[..., None])
        ro = p["rough"] + 0.0 * cov
        return cov, hrel, col, ro
    return fn


def _blobs(G: Ground, r, count, size_m, pal, *, kind="flake", density=None, H_ratio=0.15, rough=(0.8, 0.9), x=None,
           y=None, tag=TAG_BARK, sharp=0.6, zoff=-0.0005, aspect=(0.5, 1.0), irregular=1.0, noise=None, drape=None,
           weights=None, tint=None, tint_amt=0.0, noise2=None, size_pow=1.8):
    n = G.n
    if x is None:
        x, y = _points(r, n, count, density)
    count = x.size
    if count == 0:
        return
    s = G.m(1.0) * (size_m[0] + (size_m[1] - size_m[0]) * r.random(count) ** size_pow)
    asp = aspect[0] + (aspect[1] - aspect[0]) * r.random(count)
    rx = s * 0.5
    ry = s * 0.5 * asp
    col = _pal(r, count, pal, weights, jit=0.12)
    if tint is not None and tint_amt > 0:
        col = col * (1 - tint_amt) + _cols([tint])[0] * tint_amt
    params = {"ang": r.random(count) * 2 * np.pi, "rx": rx, "ry": ry,
              "h1": (r.random(count) * 0.16) * irregular, "h2": (r.random(count) * 0.10) * irregular,
              "h3": (r.random(count) * 0.05) * irregular,
              "p1": r.random(count) * 6.28, "p2": r.random(count) * 6.28, "p3": r.random(count) * 6.28,
              "col": col, "H": s * G.px * H_ratio * (0.7 + 0.6 * r.random(count)),
              "sharp": np.full(count, sharp), "rough": rough[0] + (rough[1] - rough[0]) * r.random(count)}
    grow = 1.0 + 0.31 * irregular + (0.2 if kind in ("lichen", "clod") else 0.0)
    P = int(np.ceil(s.max() * grow + 6) // 2 * 2)
    noise = noise if noise is not None else _spec(n, 0.7, 5151)
    fn = _blob_fn(noise, kind, noise2)
    if drape is not None:
        G.shapes(x, y, P, fn, params, tag, z=np.full(count, zoff, np.float32), drape=drape)
    else:
        sm = G.smooth(3.0)
        z = _bilinear(sm, x, y).astype(np.float32) + zoff
        G.shapes(x, y, P, fn, params, tag, z=z)


# --------------------------------------------------------------------------------------------------
# Map derivation
# --------------------------------------------------------------------------------------------------

def _normal(h_m: np.ndarray, px_m: float, exag: float = 1.0, pre_blur: float = 0.6, max_slope: float = 2.2) -> np.ndarray:
    """OpenGL tangent-space normal from a periodic height field in metres (true scale x exag).
    Slopes are soft-limited to `max_slope` so 1-px features never turn into black lines."""
    h = _blur(h_m, pre_blur) if pre_blur > 0 else h_m
    # Sobel-like (smoother than central differences)
    hx = (np.roll(h, -1, 1) - np.roll(h, 1, 1))
    hy = (np.roll(h, -1, 0) - np.roll(h, 1, 0))
    hx = (2 * hx + np.roll(hx, 1, 0) + np.roll(hx, -1, 0)) / 8.0
    hy = (2 * hy + np.roll(hy, 1, 1) + np.roll(hy, -1, 1)) / 8.0
    k = exag / px_m
    nx = -hx * k
    ny = hy * k
    g = np.sqrt(nx * nx + ny * ny)
    lim = 1.0 / np.sqrt(1.0 + (g / max_slope) ** 2)
    nx *= lim
    ny *= lim
    nz = np.ones_like(h)
    inv = 1.0 / np.sqrt(nx * nx + ny * ny + nz * nz)
    return np.stack([nx * inv, ny * inv, nz * inv], -1) * 0.5 + 0.5


def _ao(h_m: np.ndarray, px_m: float, radii=(1.5, 4, 10, 24), strength: float = 1.0) -> np.ndarray:
    """Multi-scale horizon-ish occlusion: how much the neighbourhood rises above each texel,
    relative to the distance, averaged over scales."""
    occ = np.zeros_like(h_m)
    wsum = 0.0
    for i, rad in enumerate(radii):
        b = _blur(h_m, rad)
        d = np.clip(b - h_m, 0, None) / (rad * px_m * 1.5)
        w = 1.0 / (1 + 0.35 * i)
        occ += w * (d / np.sqrt(1 + d * d))
        wsum += w
    return np.clip(1.0 - strength * occ / wsum * 1.6, 0.0, 1.0)


def _detile(albedo: np.ndarray, amount: float = 0.7, sigma_frac: float = 0.12, chroma: float = 0.6) -> np.ndarray:
    """Removes most of the tile-scale (1-3 cycles/tile) brightness and hue variation, which is what
    makes a tiled texture show its grid at distance. Mid/fine-scale patchiness is kept."""
    n = albedo.shape[0]
    low = np.maximum(_blur(albedo, n * sigma_frac), 1e-3)
    mean = albedo.reshape(-1, 3).mean(0)
    ll = _lum(low)
    gain_l = (_lum(albedo).mean() / ll) ** amount
    # hue part: per-channel ratio relative to luminance
    hue_low = low / ll[..., None]
    hue_mean = mean / max(float(_lum(mean[None, None, :])[0, 0]), 1e-3)
    gain_c = (hue_mean[None, None, :] / hue_low) ** chroma
    return albedo * gain_l[..., None] * gain_c


def _detile_scalar(a: np.ndarray, amount: float = 0.7, sigma_frac: float = 0.16) -> np.ndarray:
    n = a.shape[0]
    low = _blur(a, n * sigma_frac)
    return a + (a.mean() - low) * amount


class Layer:
    """Finished layer maps. albedo sRGB (n,n,3), height01 (n,n), normal (n,n,3) in 0..1, ao, rough."""

    def __init__(self, albedo, height01, normal, ao, rough):
        self.albedo = np.clip(albedo, 0, 1).astype(np.float32)
        self.height = np.clip(height01, 0, 1).astype(np.float32)
        self.normal = normal.astype(np.float32)
        self.ao = np.clip(ao, 0, 1).astype(np.float32)
        self.rough = np.clip(rough, 0.02, 1).astype(np.float32)


def _to_lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((np.maximum(c, 0) + 0.055) / 1.055) ** 2.4)


def _to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def _expose(albedo_srgb: np.ndarray, target_lum: float) -> np.ndarray:
    """Scales albedo in linear space so the mean linear luminance equals `target_lum` (keeps every
    layer of the set physically consistent: snow ~0.75, fresh asphalt ~0.05 ...)."""
    lin = _to_lin(albedo_srgb)
    m = float(_lum(lin).mean())
    return _to_srgb(lin * (target_lum / max(m, 1e-5)))


def _finish(albedo, h_m, rough, px_m, *, exag=1.0, ao_strength=1.0, ao_bake=0.45, detile=0.7, pre_blur=0.6,
            ao_radii=(1.5, 4, 10, 24), height_lo=0.5, height_hi=99.7, rough_detile=0.5, target=None,
            chroma=0.6, max_slope=2.2, nrm_h=None) -> Layer:
    ao = _ao(h_m, px_m, ao_radii, ao_strength)
    nrm = _normal(h_m if nrm_h is None else nrm_h, px_m, exag, pre_blur, max_slope)
    alb = albedo * (ao ** ao_bake)[..., None]
    if detile > 0:
        alb = _detile(alb, detile, chroma=chroma)
        rough = _detile_scalar(rough, rough_detile)
    if target is not None:
        alb = _expose(np.clip(alb, 0, 1), target)
    lo, hi = np.percentile(h_m, [height_lo, height_hi])
    h01 = np.clip((h_m - lo) / max(hi - lo, 1e-9), 0, 1)
    # order-preserving remap so every layer's height median sits near 0.5 (balanced height blends)
    med = float(np.median(h01))
    if 0.0 < med < 1.0:
        h01 = h01 ** float(np.clip(np.log(0.5) / np.log(med), 0.4, 2.5))
    return Layer(alb, h01, nrm, ao, rough)


# --------------------------------------------------------------------------------------------------
# Layers
# --------------------------------------------------------------------------------------------------

NEEDLE_STOPS = [(0.0, "#b5763e"), (0.2, "#a16236"), (0.45, "#865d3d"), (0.7, "#725f4d"), (1.0, "#56493f")]
LARCH_STOPS = [(0.0, "#b8994e"), (0.5, "#a3844a"), (1.0, "#86683e")]
UNDER_STOPS = [(0.0, "#6a5240"), (0.5, "#534131"), (1.0, "#3b2f25")]
TWIG_STOPS = [(0.0, "#6a5848"), (0.5, "#4f4136"), (1.0, "#3a3029")]


def layer_forest_floor(n: int, seed: int) -> Layer:
    G = Ground(n, TILE_M["forest_floor"])
    r = _rng(seed)
    # --- base relief: gentle undulation (roots / buried wood) + humus crumbs ------------------------
    und = _band(n, 3, 14, seed + 1, 2.0)
    f1, _, _ = T.worley(n, 2600, seed + 2)
    crumbs = np.clip(1.0 - f1 / (n / np.sqrt(2600) * 0.8), 0, 1)
    fine = _spec(n, 1.2, seed + 3)
    G.h[:] = (0.012 * und + 0.0025 * crumbs + 0.0008 * fine).ravel()
    damp = _band(n, 5, 14, seed + 4, 1.5)
    base = T.gradient(T.normalize(0.5 * crumbs + 0.5 * fine), [(0.0, "#241b14"), (0.5, "#33281e"), (1.0, "#46382b")])
    G.col[:] = base.reshape(-1, 3)
    G.rough[:] = 0.88
    # --- distribution fields (mid-scale, 2-12 cycles per tile) --------------------------------------
    age = T.normalize(0.55 * _band(n, 4, 14, seed + 6, 1.2) + 0.45 * _band(n, 12, 48, seed + 7, 1.0))
    leafy = _ss(0.45, 0.85, _band(n, 4, 10, seed + 8, 1.2))
    larchy = _ss(0.55, 0.9, _band(n, 5, 12, seed + 9, 1.2))
    thick = 0.6 + 0.4 * _band(n, 4, 12, seed + 10, 1.0)
    flow = _spec(n, 3.0, seed + 11)
    noise = _spec(n, 1.6, seed + 12)
    # --- 1 matted, partly buried under-layer -------------------------------------------------------
    _needles(G, r, 30000, thick, UNDER_STOPS, (0.006, 0.018), (0.36, 0.48), age=age, mode="drape", lift=0.0006,
             thick_m=0.0006, bend=0.5, rough=(0.85, 0.95), tag=TAG_UNDER, dark_tip=0.1)
    _needles(G, r, 12000, thick, NEEDLE_STOPS, (0.012, 0.022), (0.4, 0.5), age=np.clip(age + 0.35, 0, 1),
             mode="drape", lift=0.001, thick_m=0.0009, rough=(0.8, 0.92))
    # --- 2 decomposing leaves, bark flakes ---------------------------------------------------------
    _leaves(G, r, 200, {"dead": 3, "birch": 1, "aspen": 1}, density=leafy * 0.6 + 0.4, noise=noise, age_bias=0.45)
    _blobs(G, r, 80, (0.008, 0.03), ["#7a4a30", "#6a4030", "#8a5a3a", "#5a3a28"], kind="flake", H_ratio=0.06,
           rough=(0.8, 0.9), tag=TAG_BARK, noise=noise)
    # --- 3 main needle mat (rests on the litter) ---------------------------------------------------
    env = _envelope(G)
    _needles(G, r, 15000, thick, NEEDLE_STOPS, (0.012, 0.022), (0.42, 0.52), age=age, env=env, thick_m=0.0012)
    _needles(G, r, 5000, thick, NEEDLE_STOPS, (0.045, 0.075), (0.48, 0.58), age=age, env=env, pair=0.5,
             align=flow, align_amt=0.2, bend=0.15, thick_m=0.0012)
    _twigs(G, r, 140, (0.02, 0.07), (0.0012, 0.0025), TWIG_STOPS, branch=0.25, age=age, segs=3)
    # --- 4 fresh leaves (clustered) + golden larch patches ------------------------------------------
    _leaves(G, r, 150, {"birch": 3, "aspen": 1.4, "bilberry": 2.2, "willow": 0.5, "dead": 1.5}, density=leafy * 0.8 + 0.2,
            noise=noise, age_bias=0.15)
    env = _envelope(G)
    _needles(G, r, 4500, larchy * 0.6 + 0.08, LARCH_STOPS, (0.015, 0.03), (0.38, 0.48), age=age, env=env,
             thick_m=0.0008, bend=0.3, rough=(0.7, 0.85), dark_tip=0.15)
    # --- 5 sticks and cones ----------------------------------------------------------------------
    _twigs(G, r, 28, (0.12, 0.45), (0.0025, 0.006), TWIG_STOPS, branch=0.9, age=age)
    _cones(G, r, 9)
    # --- 6 top sprinkle of fresh needles (ties everything together) ---------------------------------
    env = _envelope(G)
    _needles(G, r, 5000, None, NEEDLE_STOPS, (0.012, 0.022), (0.42, 0.52), age=np.clip(age - 0.2, 0, 1), env=env,
             thick_m=0.0012)
    _needles(G, r, 1800, None, NEEDLE_STOPS, (0.045, 0.075), (0.48, 0.58), age=np.clip(age - 0.2, 0, 1), env=env,
             pair=0.5, bend=0.15, thick_m=0.0012)
    # --- post --------------------------------------------------------------------------------------
    h = G.H().copy()
    col = G.C().copy()
    rough = G.R().copy()
    tag = G.TAG()
    low = ((tag == TAG_BASE) | (tag == TAG_UNDER)).astype(np.float32)
    dmp = _ss(0.55, 0.85, damp) * low
    col *= (1.0 - 0.2 * dmp)[..., None]
    rough -= 0.1 * dmp
    col *= (0.95 + 0.1 * _band(n, 4, 16, seed + 13))[..., None]
    return _finish(col, h, rough, G.px, exag=1.4, ao_strength=2.0, ao_bake=0.6, ao_radii=(1.0, 2.5, 6, 16),
                   target=TARGET_LUM["forest_floor"])


# --------------------------------------------------------------------------------------------------
# More recipes: moss shoots, grass blades, roots
# --------------------------------------------------------------------------------------------------

def _fronds(G: Ground, r, count, density, len_m, stops, *, age=None, env=None, nb=7, stem_r=0.42, br_r=0.36,
            lift=0.0004, thick=0.0012, tag=TAG_MOSS, bend=0.45, branch_len=0.32, rough=(0.8, 0.92), age_jit=0.12):
    """Feather-moss shoots (Hylocomium / Pleurozium-like): curved stem with alternating pinnate
    branchlets, darker base, lighter yellow-green growing tips."""
    n = G.n
    x, y = _points(r, n, count, density)
    count = x.size
    ang = r.random(count) * 2 * np.pi
    L = G.m(1.0) * (len_m[0] + (len_m[1] - len_m[0]) * r.random(count))
    K = 3
    xs, ys = _polyline(r, x, y, ang, L, K, bend)
    c = _age_colors(r, x, y, age, stops, age_jit, 0.08)
    dark = c * 0.6
    tipc = np.clip(c * 1.2 + 0.02, 0, 1)
    env = env if env is not None else _envelope(G, 3, 1.0)
    z = _vertex_z(env, xs, ys, lift)
    ro = rough[0] + (rough[1] - rough[0]) * r.random(count)
    G.polylines(xs, ys, np.full(count, stem_r), np.full(count, stem_r * 0.7), z, thick, dark, tipc, ro, tag)
    tp = np.linspace(0.1, 0.92, nb)[None, :] + (r.random((count, nb)) - 0.5) * 0.05
    tp = np.clip(tp, 0, 0.999)
    seg = np.minimum((tp * K).astype(np.int64), K - 1)
    fr = tp * K - seg
    i = np.arange(count)[:, None]
    px = xs[i, seg] + (xs[i, seg + 1] - xs[i, seg]) * fr
    py = ys[i, seg] + (ys[i, seg + 1] - ys[i, seg]) * fr
    pz = z[i, seg] + (z[i, seg + 1] - z[i, seg]) * fr
    da = np.arctan2(ys[i, seg + 1] - ys[i, seg], xs[i, seg + 1] - xs[i, seg])
    side = np.where(np.arange(nb)[None, :] % 2 == 0, 1.0, -1.0) * np.where(r.random((count, 1)) < 0.5, 1.0, -1.0)
    ab = da + side * (0.85 + 0.35 * r.random((count, nb)))
    bl = L[:, None] * branch_len * (1.0 - 0.65 * tp) * (0.7 + 0.6 * r.random((count, nb)))
    ex = px + np.cos(ab) * bl
    ey = py + np.sin(ab) * bl
    cs = dark[:, None, :] + (tipc - dark)[:, None, :] * tp[..., None]
    ce = np.clip(cs * 1.12, 0, 1)
    G.segments(px.ravel(), py.ravel(), ex.ravel(), ey.ravel(), br_r, br_r * 0.75, pz.ravel(), thick * 0.8,
               cs.reshape(-1, 3), ce.reshape(-1, 3), np.repeat(ro, nb), tag)


def _blades(G: Ground, r, count, density, len_m, width_m, stops, *, age=None, flow=None, flow_amt=0.7, tufts=None,
            tuft_amt=0.0, env=None, mode="rest", lift=0.0006, thick=0.0009, bend=0.22, rough=(0.62, 0.85),
            tag=TAG_GRASS, K=4, tipc=1.12, basec=0.78, age_jit=0.15, flat=0.65, rib=0.3):
    """Flattened grass blades: tapered flat strips, base darker, tip paler. Direction from a flow
    field (wind/snow-flattened) or radiating from tussock centres."""
    n = G.n
    x, y = _points(r, n, count, density)
    count = x.size
    ang = r.random(count) * 2 * np.pi
    L = G.m(1.0) * (len_m[0] + (len_m[1] - len_m[0]) * r.random(count) ** 1.3)
    if flow is not None:
        a0 = _sample(flow, x, y) * 4 * np.pi
        m = r.random(count) < flow_amt
        ang = np.where(m, a0 + (r.random(count) - 0.5) * 0.9, ang)
    if tufts is not None and tuft_amt > 0:
        m = r.random(count) < tuft_amt
        ti = r.integers(0, tufts[0].size, count)
        tx, ty = tufts[0][ti], tufts[1][ti]
        a1 = r.random(count) * 2 * np.pi
        rr0 = G.m(0.02) * r.random(count)
        sx = tx + np.cos(a1) * rr0
        sy = ty + np.sin(a1) * rr0
        a2 = a1 + (r.random(count) - 0.5) * 0.8
        if flow is not None:
            fa = _sample(flow, sx, sy) * 4 * np.pi
            a2 = np.arctan2(np.sin(a2) + 0.6 * np.sin(fa), np.cos(a2) + 0.6 * np.cos(fa))
        x = np.where(m, sx + np.cos(a2) * L * 0.5, x)
        y = np.where(m, sy + np.sin(a2) * L * 0.5, y)
        ang = np.where(m, a2, ang)
    W = G.m(1.0) * (width_m[0] + (width_m[1] - width_m[0]) * r.random(count)) * 0.5
    c = _age_colors(r, x, y, age, stops, age_jit, 0.08)
    xs, ys = _polyline(r, x, y, ang, L, K, bend)
    ro = rough[0] + (rough[1] - rough[0]) * r.random(count)
    if mode == "drape":
        z = (lift + r.random(count) * 0.0006).astype(np.float32)
        G.polylines(xs, ys, W, W * 0.3, z, thick, c * basec, np.clip(c * tipc, 0, 1), ro, tag, flat=flat, rib=rib,
                    drape=G.smooth(1.5))
    else:
        env = env if env is not None else _envelope(G, 3, 1.2)
        z = _vertex_z(env, xs, ys, lift)
        z[:, 1:] += np.linspace(0, 1, K)[None, :].astype(np.float32) * (r.random((count, 1)) * 0.002).astype(np.float32)
        G.polylines(xs, ys, W, W * 0.3, z, thick, c * basec, np.clip(c * tipc, 0, 1), ro, tag, flat=flat, rib=rib)


def _roots(G: Ground, r, count, len_m, rad_m, cols, *, bury=0.0015, tag=TAG_TWIG):
    """Exposed roots: long wiggly strokes draped over the ground, partly buried."""
    n = G.n
    x, y = _points(r, n, count)
    ang = r.random(count) * 2 * np.pi
    L = G.m(1.0) * (len_m[0] + (len_m[1] - len_m[0]) * r.random(count))
    rad = G.m(1.0) * (rad_m[0] + (rad_m[1] - rad_m[0]) * r.random(count))
    xs, ys = _polyline(r, x, y, ang, L, 10, 0.45)
    c = _pal(r, count, cols, jit=0.1)
    dz = (rad * G.px * 1.6).astype(np.float32)
    z = (-bury * (0.3 + 0.7 * r.random(count))).astype(np.float32)
    G.polylines(xs, ys, rad, rad * 0.4, z, dz, c, c * 0.8, np.full(count, 0.75), tag, drape=G.smooth(3.0))


# --------------------------------------------------------------------------------------------------
# moss_ground
# --------------------------------------------------------------------------------------------------

MOSS_STOPS = [(0.0, "#38411a"), (0.3, "#4f5c22"), (0.55, "#66722e"), (0.8, "#7f893a"), (1.0, "#99944f")]
MOSS_DEAD = [(0.0, "#55492c"), (0.5, "#6e6038"), (1.0, "#857546")]
LICHEN_COLS = ["#9da48c", "#a8ae98", "#b0b4a0", "#8f9880", "#a0a890"]


def layer_moss_ground(n: int, seed: int) -> Layer:
    G = Ground(n, TILE_M["moss_ground"])
    r = _rng(seed)
    hum = _band(n, 3, 10, seed + 1, 2.0)
    f1, _, _ = T.worley(n, 300, seed + 2)
    cell = n / np.sqrt(300)
    cush = _blur(np.clip(1 - (f1 / (cell * 0.85)) ** 2, 0, 1), 4.0)
    fine = _spec(n, 0.8, seed + 3)
    G.h[:] = (0.028 * hum + 0.008 * cush + 0.0012 * fine).ravel()
    age = T.normalize(0.5 * hum + 0.25 * cush + 0.25 * _band(n, 8, 30, seed + 4))
    under = T.gradient(np.clip(0.6 * age + 0.4 * fine, 0, 1), MOSS_STOPS) * 0.5
    G.col[:] = under.reshape(-1, 3)
    G.rough[:] = 0.9
    G.tag[:] = TAG_MOSS
    dens = 0.75 + 0.25 * _band(n, 4, 14, seed + 5)
    dead = _ss(0.62, 0.85, _band(n, 5, 14, seed + 6, 1.3))
    _fronds(G, r, 9000, dens, (0.025, 0.06), MOSS_STOPS, age=age, nb=9)
    _fronds(G, r, 2200, dead, (0.025, 0.055), MOSS_DEAD, age=age, nb=9, lift=0.0005)
    # reindeer lichen (Cladonia) clumps on the drier hummock tops
    lich = _ss(0.6, 0.82, _band(n, 4, 12, seed + 7, 1.3)) * _ss(0.4, 0.75, hum)
    hi = _spec(n, 0.45, seed + 8)
    _blobs(G, r, 200, (0.012, 0.04), LICHEN_COLS, kind="lichen", density=lich, H_ratio=0.28, rough=(0.88, 0.95),
           tag=TAG_LICHEN, zoff=0.001, irregular=1.4, noise=hi, noise2=_spec(n, 1.2, seed + 9),
           drape=_envelope(G, 5, 1.5))
    _blobs(G, r, 600, (0.004, 0.012), LICHEN_COLS, kind="lichen", density=lich * 0.8 + 0.05, H_ratio=0.25,
           rough=(0.88, 0.95), tag=TAG_LICHEN, zoff=0.0008, irregular=1.4, noise=hi, noise2=_spec(n, 1.2, seed + 9),
           drape=_envelope(G, 3, 1.0))
    _fronds(G, r, 7000, dens, (0.02, 0.05), MOSS_STOPS, age=np.clip(age + 0.1, 0, 1), nb=8, lift=0.0006)
    noise = _spec(n, 1.6, seed + 10)
    env = _envelope(G)
    nage = _band(n, 4, 14, seed + 11)
    _needles(G, r, 2400, None, NEEDLE_STOPS, (0.012, 0.022), (0.4, 0.5), age=nage, env=env)
    _needles(G, r, 450, None, NEEDLE_STOPS, (0.045, 0.07), (0.45, 0.55), age=nage, env=env, pair=0.5, bend=0.15)
    _leaves(G, r, 40, {"birch": 3, "bilberry": 3, "aspen": 1, "dead": 1}, noise=noise)
    _twigs(G, r, 9, (0.06, 0.3), (0.0018, 0.004), TWIG_STOPS, branch=0.8)
    _cones(G, r, 2)
    h = G.H().copy()
    col = G.C().copy()
    rough = G.R().copy()
    wet = 1 - _ss(0.2, 0.6, hum)
    mossm = (G.TAG() == TAG_MOSS).astype(np.float32)
    col *= (1 - 0.12 * wet * mossm)[..., None]
    rough -= 0.08 * wet * mossm
    return _finish(col, h, rough, G.px, exag=1.3, ao_strength=1.8, ao_bake=0.6, ao_radii=(1.0, 2.5, 6, 16),
                   target=TARGET_LUM["moss_ground"])


# --------------------------------------------------------------------------------------------------
# grass_ground
# --------------------------------------------------------------------------------------------------

GRASS_DRY = [(0.0, "#c9b98c"), (0.3, "#b6a26c"), (0.55, "#9e8858"), (0.8, "#887660"), (1.0, "#6f604e")]
GRASS_GREEN = [(0.0, "#879448"), (0.5, "#6a783c"), (1.0, "#4e5b2d")]
THATCH = [(0.0, "#8f7f60"), (0.5, "#776a51"), (1.0, "#5b5040")]
SOIL_STOPS = [(0.0, "#3a2c20"), (0.35, "#4f3c2b"), (0.65, "#654e38"), (1.0, "#7d654a")]


def layer_grass_ground(n: int, seed: int) -> Layer:
    G = Ground(n, TILE_M["grass_ground"])
    r = _rng(seed)
    und = _band(n, 3, 12, seed + 1, 2.0)
    fine = _spec(n, 1.0, seed + 2)
    G.h[:] = (0.015 * und + 0.0015 * fine).ravel()
    G.col[:] = T.gradient(T.normalize(0.6 * fine + 0.4 * und), SOIL_STOPS).reshape(-1, 3) * 0.75
    G.rough[:] = 0.88
    flow = _spec(n, 3.2, seed + 3)
    age = T.normalize(0.5 * _band(n, 4, 14, seed + 4, 1.2) + 0.5 * _band(n, 14, 50, seed + 5, 1.0))
    green = _ss(0.45, 0.8, _band(n, 4, 12, seed + 6, 1.2))
    tx, ty = _jittered(r, n, 10, 0.9, keep=0.7)
    # dead thatch (matted, partly buried)
    _blades(G, r, 14000, None, (0.03, 0.09), (0.002, 0.0035), THATCH, age=age, mode="drape", lift=0.0008,
            flow=flow, flow_amt=0.35, rough=(0.75, 0.9), K=2, bend=0.35)
    _blades(G, r, 4500, green * 0.8 + 0.2, (0.04, 0.12), (0.0025, 0.004), GRASS_GREEN, age=age, flow=flow,
            flow_amt=0.6, tufts=(tx, ty), tuft_amt=0.3, K=3, rough=(0.55, 0.75))
    rc, nl = 26, 7
    rx, ry = _points(r, n, rc)
    ra = r.random((rc, 1)) * 6.28 + np.arange(nl)[None, :] * (2 * np.pi / nl) + (r.random((rc, nl)) - 0.5) * 0.4
    rl = G.m(0.016) * (0.7 + 0.6 * r.random((rc, nl)))
    _leaves(G, r, rc * nl, {"herb": 1}, x=(rx[:, None] + np.cos(ra) * rl).ravel(),
            y=(ry[:, None] + np.sin(ra) * rl).ravel(), ang=ra.ravel())
    _leaves(G, r, 160, {"clover": 1}, density=green)
    env = _envelope(G, 3, 1.2)
    _blades(G, r, 7500, None, (0.06, 0.22), (0.0025, 0.0045), GRASS_DRY, age=age, flow=flow, flow_amt=0.7,
            tufts=(tx, ty), tuft_amt=0.2, env=env, K=5)
    _leaves(G, r, 40, {"birch": 3, "aspen": 2, "willow": 1, "dead": 1}, noise=_spec(n, 1.6, seed + 7))
    _twigs(G, r, 8, (0.05, 0.2), (0.0015, 0.0035), TWIG_STOPS, branch=0.5)
    env = _envelope(G, 3, 1.2)
    _blades(G, r, 2800, None, (0.08, 0.24), (0.0025, 0.004), GRASS_DRY, age=np.clip(age - 0.15, 0, 1), flow=flow,
            flow_amt=0.75, env=env, K=5)
    h = G.H().copy()
    col = G.C().copy()
    rough = G.R().copy()
    return _finish(col, h, rough, G.px, exag=1.2, ao_strength=1.8, ao_bake=0.6, ao_radii=(1.0, 2.5, 6, 16),
                   target=TARGET_LUM["grass_ground"])


# --------------------------------------------------------------------------------------------------
# dirt
# --------------------------------------------------------------------------------------------------

PEBBLE_COLS = ["#7d7a74", "#6a6660", "#8c857a", "#5a5650", "#9a948a", "#7a6a58", "#a49c90", "#4e4a46"]


def layer_dirt(n: int, seed: int) -> Layer:
    G = Ground(n, TILE_M["dirt"])
    r = _rng(seed)
    und = _band(n, 3, 12, seed + 1, 2.0)
    med = _band(n, 15, 60, seed + 2, 1.2)
    gran = _spec(n, 0.45, seed + 4)
    dry = _ss(0.3, 0.8, _band(n, 4, 12, seed + 5, 1.5))
    packed = _ss(0.5, 0.8, _band(n, 3, 9, seed + 6, 1.5))
    g1, g2, _ = T.worley(n, 160, seed + 7)
    wx, wy = _spec(n, 2.0, seed + 8), _spec(n, 2.0, seed + 9)
    cr = T.warp(g2 - g1, wx, wy, 14.0)
    crack = (1 - _ss(0.0, 1.6, cr)) * dry * (1 - packed) * _ss(0.55, 0.75, _band(n, 4, 12, seed + 10))
    crack *= _ss(0.3, 0.6, _spec(n, 1.4, seed + 11))
    amp = 1.0 - 0.5 * packed
    h = 0.012 * und + (0.003 * med + 0.0007 * gran) * amp - 0.0025 * crack
    G.h[:] = h.ravel()
    t = np.clip(0.45 * _spec(n, 1.6, seed + 12) + 0.3 * med + 0.25 * gran, 0, 1)
    col = T.gradient(t, SOIL_STOPS)
    col *= (0.9 + 0.16 * dry)[..., None]
    col = col * (1 - 0.4 * crack)[..., None]
    red = _ss(0.55, 0.85, _band(n, 4, 12, seed + 13))
    col = col * (1 + np.stack([0.06 * red, -0.01 * red, -0.06 * red], -1))
    G.col[:] = col.reshape(-1, 3)
    G.rough[:] = (0.93 - 0.1 * (1 - dry) - 0.05 * packed).ravel()
    soil = ["#5e4836", "#6e5640", "#54402f", "#7a6048", "#4a3a2c", "#665040"]
    noise = _spec(n, 0.8, seed + 14)
    n2 = _spec(n, 1.3, seed + 15)
    loose = 1 - 0.75 * packed
    _roots(G, r, 12, (0.25, 0.8), (0.002, 0.005), ["#5a3a28", "#6a4430", "#4a3226"])
    # soil aggregate structure: crumbs -> small aggregates -> clods (crisp granular relief)
    _blobs(G, r, 26000, (0.002, 0.006), soil, kind="clod", density=loose, H_ratio=0.35, rough=(0.88, 0.96),
           tag=TAG_MISC, noise=gran, noise2=n2, aspect=(0.6, 1.0), irregular=1.0, zoff=-0.0006, size_pow=1.5)
    _blobs(G, r, 3800, (0.006, 0.015), soil, kind="clod", density=loose, H_ratio=0.32, rough=(0.88, 0.96),
           tag=TAG_MISC, noise=gran, noise2=n2, aspect=(0.6, 1.0), irregular=1.2, zoff=-0.0012)
    _blobs(G, r, 380, (0.015, 0.045), soil, kind="clod", density=loose, H_ratio=0.3, rough=(0.88, 0.95),
           tag=TAG_MISC, noise=gran, noise2=n2, aspect=(0.6, 1.0), irregular=1.2, zoff=-0.002)
    _blobs(G, r, 1700, (0.003, 0.016), PEBBLE_COLS, kind="pebble", H_ratio=0.4, rough=(0.6, 0.8), tag=TAG_STONE,
           noise=noise, aspect=(0.55, 1.0), irregular=1.2, zoff=-0.0025, sharp=0.6, tint="#5e4836", tint_amt=0.45)
    _blobs(G, r, 80, (0.02, 0.05), PEBBLE_COLS, kind="pebble", H_ratio=0.35, rough=(0.6, 0.8), tag=TAG_STONE,
           noise=noise, aspect=(0.55, 1.0), irregular=1.2, zoff=-0.006, sharp=0.5, tint="#5e4836", tint_amt=0.35)
    age = _band(n, 4, 14, seed + 16)
    _needles(G, r, 1400, None, NEEDLE_STOPS, (0.008, 0.022), (0.4, 0.5), age=np.clip(age + 0.4, 0, 1), mode="drape",
             lift=0.0004, thick_m=0.0007)
    _leaves(G, r, 18, {"dead": 3, "birch": 1, "aspen": 1}, noise=_spec(n, 1.6, seed + 17), age_bias=0.4, size=0.8)
    _twigs(G, r, 12, (0.03, 0.15), (0.0012, 0.003), TWIG_STOPS, branch=0.3, segs=3)
    hh = G.H().copy()
    col = G.C().copy()
    rough = G.R().copy()
    return _finish(col, hh, rough, G.px, exag=1.3, ao_strength=1.6, ao_bake=0.6, ao_radii=(1.0, 2.5, 6, 16),
                   target=TARGET_LUM["dirt"])


# --------------------------------------------------------------------------------------------------
# mud
# --------------------------------------------------------------------------------------------------

MUD_STOPS = [(0.0, "#2c241c"), (0.4, "#3b3127"), (0.75, "#4b3f31"), (1.0, "#5e503e")]


def _imprint(h: np.ndarray, px_m: float, cx: float, cy: float, ang: float, kind: str, size: float, depth: float,
             rim: float, r: np.random.Generator, wx: np.ndarray, wy: np.ndarray, rn: np.ndarray) -> None:
    """Presses one imprint (boot / hoof / slide / squish) into a periodic height field (in place). The
    outline is domain-warped, the floor tilts (heel deeper), displaced mud forms an irregular rim and
    the print partly slumps back (old, half-erased prints)."""
    n = h.shape[0]
    L = size / px_m
    P = int(L * 1.9) + 10
    ox, oy = int(np.floor(cx)) - P // 2, int(np.floor(cy)) - P // 2
    ys = (np.arange(P) + oy) % n
    xs = (np.arange(P) + ox) % n
    gy, gx = np.mgrid[0:P, 0:P].astype(np.float32)
    wpx = (wx[np.ix_(ys, xs)] - 0.5) * 2
    wpy = (wy[np.ix_(ys, xs)] - 0.5) * 2
    warp = 0.06 * L + 2.0
    dx = gx + ox + 0.5 - cx + wpx * warp
    dy = gy + oy + 0.5 - cy + wpy * warp
    ca, sa = np.cos(ang), np.sin(ang)
    u = (dx * ca + dy * sa) / L
    v = (-dx * sa + dy * ca) / L
    lug = np.zeros_like(u)
    if kind == "boot":
        q1 = np.sqrt(((u - 0.2) / 0.33) ** 2 + (v / 0.19) ** 2)
        q2 = np.sqrt(((u + 0.3) / 0.2) ** 2 + (v / 0.15) ** 2)
        q3 = np.sqrt((u / 0.45) ** 2 + (v / 0.13) ** 2)
        q = np.minimum(np.minimum(q1, q2), q3)
        lug = (np.sin(2 * np.pi * (u * 9 + np.abs(v) * 7)) > 0.3).astype(np.float32) * 0.07 * r.random()
        tilt = -0.35 * u
    elif kind == "hoof":
        sp = 0.16 + 0.1 * r.random()
        q1 = np.sqrt(((u - 0.05) / 0.45) ** 2 + ((v - sp) / 0.17) ** 2)
        q2 = np.sqrt(((u - 0.05) / 0.45) ** 2 + ((v + sp) / 0.17) ** 2)
        q = np.minimum(q1, q2) * (1 - 0.25 * np.clip(u, 0, 1))
        q = np.minimum(q, np.sqrt(((u + 0.05) / 0.4) ** 2 + (v / (sp + 0.1)) ** 2) * 1.15)
        tilt = 0.4 * u
    elif kind == "slide":
        q = np.sqrt((u / 0.5) ** 2 + (v / 0.12) ** 2)
        tilt = 0.8 * u
    else:
        q = np.sqrt((u / 0.5) ** 2 + (v / (0.5 * (0.45 + 0.5 * r.random()))) ** 2)
        tilt = 0.3 * u * (r.random() - 0.5)
    patch = h[np.ix_(ys, xs)]
    level = float(np.median(patch))
    inside = np.clip((1.0 - q) / 0.18, 0, 1)
    floor = level - depth * (1.0 - 0.3 * q ** 3 + tilt) - depth * lug
    pressed = np.minimum(patch, floor)
    slump = r.random() ** 1.5 * 0.75
    pressed = pressed + (patch - pressed) * slump
    out = patch * (1 - inside) + pressed * inside
    noise_rim = rn[np.ix_(ys, xs)]
    ring = np.exp(-((q - 1.1) / 0.2) ** 2) * (q > 0.85) * (0.3 + 1.2 * noise_rim)
    out = out + rim * ring * (1 - slump)
    h[np.ix_(ys, xs)] = out


def layer_mud(n: int, seed: int) -> Layer:
    G = Ground(n, TILE_M["mud"])
    r = _rng(seed)
    big = _band(n, 2, 8, seed + 1, 2.2)
    lumps = _band(n, 10, 40, seed + 2, 1.6)
    fine = _spec(n, 1.0, seed + 3)
    h = (0.03 * big + 0.007 * lumps + 0.0006 * fine).astype(np.float32)
    wx, wy = _spec(n, 1.6, seed + 4), _spec(n, 1.6, seed + 5)
    rn = _spec(n, 1.4, seed + 6)
    cnt = 300
    kinds = r.choice(4, cnt, p=[0.06, 0.06, 0.22, 0.66])
    xs, ys = _points(r, n, cnt, _ss(0.3, 0.7, _band(n, 2, 6, seed + 7)) * 0.8 + 0.2)
    for i in range(cnt):
        k = ("boot", "hoof", "slide", "squish")[kinds[i]]
        size = {"boot": 0.29, "hoof": 0.12, "slide": 0.2 + 0.3 * r.random(), "squish": 0.05 + 0.3 * r.random() ** 2}[k]
        depth = {"boot": 0.016, "hoof": 0.026, "slide": 0.01, "squish": 0.01}[k] * (0.4 + r.random())
        _imprint(h, G.px, xs[i], ys[i], r.random() * 6.283, k, size * (0.9 + 0.2 * r.random()), depth, depth * 0.3,
                 r, wx, wy, rn)
    wx2, wy2 = _spec(n, 1.3, seed + 8), _spec(n, 1.3, seed + 9)
    h = T.warp(h, wx2, wy2, 3.0)
    churn = 1 - np.abs(2 * _band(n, 15, 60, seed + 14, 1.2) - 1)
    churn = T.warp(churn, wx2, wy2, 6.0) ** 2
    h = _blur(h, 1.0) + 0.0005 * fine + 0.0012 * _band(n, 30, 120, seed + 10, 1.0) + 0.003 * churn
    G.h[:] = h.ravel()
    hn = T.normalize(h - _blur(h, 24))
    t = np.clip(0.08 * hn + 0.52 * _spec(n, 1.5, seed + 11) + 0.4 * _band(n, 8, 40, seed + 15), 0, 1)
    G.col[:] = T.gradient(t, MUD_STOPS).reshape(-1, 3)
    G.rough[:] = 0.5
    noise = _spec(n, 1.6, seed + 12)
    _blobs(G, r, 600, (0.004, 0.025), PEBBLE_COLS, kind="pebble", H_ratio=0.35, rough=(0.45, 0.65), tag=TAG_STONE,
           noise=noise, irregular=1.2, zoff=-0.004, tint="#3b3127", tint_amt=0.5)
    age = _band(n, 4, 14, seed + 13)
    _needles(G, r, 1300, None, NEEDLE_STOPS, (0.01, 0.06), (0.4, 0.55), age=np.clip(age + 0.5, 0, 1), mode="drape",
             lift=0.0002, thick_m=0.0008, rough=(0.4, 0.6))
    _leaves(G, r, 50, {"birch": 2, "aspen": 2, "dead": 3, "willow": 1}, noise=noise, age_bias=0.45)
    _twigs(G, r, 8, (0.05, 0.25), (0.0015, 0.004), TWIG_STOPS, branch=0.4)
    hh = G.H().copy()
    col = G.C().copy()
    tag = G.TAG()
    # standing water in the deepest dents: flat, glossy, dark muddy water
    wl = np.percentile(hh, 7)
    depth = np.clip(wl - hh, 0, None)
    water = _ss(0.0, 0.0015, depth)
    shore = _ss(0.006, 0.0, hh - wl) * (1 - water)
    debris = np.isin(tag, [TAG_LEAF, TAG_NEEDLE, TAG_TWIG, TAG_STONE]).astype(np.float32)
    col = col * (1 - 0.3 * debris)[..., None]
    hi = _ss(0.6, 0.95, T.normalize(hh - _blur(hh, 20)))
    col = col * (1 - 0.15 * shore)[..., None] * (1 + 0.3 * hi * (1 - debris))[..., None]
    rough = np.where(debris > 0, G.R() - 0.15, 0.3 - 0.1 * shore + 0.4 * hi)
    wcol = col * 0.72 + _cols(["#2e2a22"])[0] * 0.15
    col = col * (1 - water[..., None]) + wcol * water[..., None]
    rough = rough * (1 - water) + 0.05 * water
    hh = np.maximum(hh, wl)
    return _finish(col, hh, rough, G.px, exag=1.0, ao_strength=1.3, ao_bake=0.45, target=TARGET_LUM["mud"],
                   rough_detile=0.0, max_slope=1.6)


# --------------------------------------------------------------------------------------------------
# Field helpers for the mineral layers
# --------------------------------------------------------------------------------------------------

def _hash(cid: np.ndarray, k: int) -> np.ndarray:
    """Deterministic per-cell random in [0,1)."""
    return ((np.sin(cid * 12.9898 + k * 78.233) * 43758.5453) % 1.0).astype(np.float32)


def _ripples(n: int, kx: int, ky: int, seed: int, warp: float = 2.5, asym: float = 0.35) -> tuple[np.ndarray, np.ndarray]:
    """Tileable asymmetric ripples along integer wave vector (kx, ky) cycles/tile with sinuous crests.
    Returns (profile -1..1, phase)."""
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    ph = 2 * np.pi * (kx * xx + ky * yy) / n + warp * 2 * np.pi * (_band(n, 1, 4, seed, 2.0) - 0.5)
    ph = ph + 0.6 * (_band(n, 4, 12, seed + 1, 1.5) - 0.5)
    prof = np.sin(ph) + asym * np.sin(2 * ph + 0.8)
    return (prof / (1 + asym)).astype(np.float32), ph


# --------------------------------------------------------------------------------------------------
# gravel (crushed-rock logging road)
# --------------------------------------------------------------------------------------------------

GRAVEL_COLS = ["#8a8780", "#5d5b57", "#a8a49c", "#8c7a64", "#9a7a5a", "#6e7278", "#c4c0b6", "#47464a", "#7a746c"]
GRAVEL_W = [4, 3, 2, 1.5, 0.8, 1.5, 0.7, 1.2, 3]


def _facet_fn(noise, noise2, nfac: int = 6):
    """Crushed angular stone: soft-min of facet planes gives a convex, slightly rounded polyhedral top
    and a polygonal outline; facets get individual tints (fresh fracture faces), mineral speckle."""
    nf = noise.reshape(-1)
    n2 = noise2.reshape(-1)

    def fn(dx, dy, p, idx):
        ca, sa = np.cos(p["ang"]), np.sin(p["ang"])
        u = (dx * ca + dy * sa) / p["R"]
        v = (-dx * sa + dy * ca) / (p["R"] * p["asp"])
        hks = [p["top"] - (p[f"a{k}"] * u + p[f"b{k}"] * v) for k in range(nfac)]
        hmin = hks[0]
        fid = np.zeros(hmin.shape, np.int8)
        for k in range(1, nfac):
            m = hks[k] < hmin
            hmin = np.where(m, hks[k], hmin)
            fid = np.where(m, np.int8(k), fid)
        acc = sum(np.exp(-9.0 * (hk - hmin)) for hk in hks)
        hs = hmin - np.log(acc) / 9.0
        sd = -hs * p["R"] / 1.3
        cov = np.clip(0.5 - sd, 0, 1)
        hrel = p["H"] * np.clip(hs / p["top"], 0, 1) ** 0.85
        ft = np.zeros_like(hs)
        for k in range(nfac):
            ft = np.where(fid == k, p[f"t{k}"], ft)
        sp = nf[idx]
        s2 = n2[idx]
        col = p["col"] * (1 + ft)[..., None] * (0.88 + 0.24 * s2)[..., None]
        col = col * (1 - 0.45 * (sp > 0.8))[..., None]
        col = col + (0.78 - col) * (0.35 * (sp < 0.12))[..., None]
        ro = p["rough"] - 0.08 * ft
        return cov, hrel, col, ro
    return fn


def _gravel(G: Ground, r, count, size_m, *, density=None, embed=0.45, cols=GRAVEL_COLS, weights=GRAVEL_W, tint=None,
            tint_amt=0.0, noise=None, noise2=None, H_ratio=0.55, rough=(0.6, 0.8), nfac=6, tag=TAG_STONE):
    n = G.n
    x, y = _points(r, n, count, density)
    count = x.size
    R = G.m(1.0) * 0.5 * (size_m[0] + (size_m[1] - size_m[0]) * r.random(count) ** 1.6)
    col = _pal(r, count, cols, weights, jit=0.1)
    if tint is not None:
        col = col * (1 - tint_amt) + _cols([tint])[0] * tint_amt
    params = {"ang": r.random(count) * 2 * np.pi, "R": R, "asp": 0.6 + 0.4 * r.random(count),
              "top": 0.9 + 0.3 * r.random(count), "col": col, "H": 2 * R * G.px * H_ratio * (0.7 + 0.5 * r.random(count)),
              "rough": rough[0] + (rough[1] - rough[0]) * r.random(count)}
    base = r.random(count) * 2 * np.pi
    for k in range(nfac):
        th = base + 2 * np.pi * k / nfac + (r.random(count) - 0.5) * 0.7
        sl = 0.9 + 0.7 * r.random(count)
        params[f"a{k}"] = np.cos(th) * sl
        params[f"b{k}"] = np.sin(th) * sl
        params[f"t{k}"] = (r.random(count) - 0.5) * 0.26
    P = int(np.ceil(R.max() * 2.6 + 6) // 2 * 2)
    noise = noise if noise is not None else _spec(n, 0.3, 4747)
    noise2 = noise2 if noise2 is not None else _spec(n, 1.0, 4748)
    sm = G.smooth(2.0)
    z = (_bilinear(sm, x, y) - params["H"] * embed).astype(np.float32)
    G.shapes(x, y, P, _facet_fn(noise, noise2, nfac), params, tag, z=z)


def layer_gravel(n: int, seed: int) -> Layer:
    G = Ground(n, TILE_M["gravel"])
    r = _rng(seed)
    und = _band(n, 3, 12, seed + 1, 2.0)
    fines = _spec(n, 0.6, seed + 2)
    G.h[:] = (0.006 * und + 0.0008 * fines).ravel()
    dustc = T.gradient(np.clip(0.5 * fines + 0.5 * _spec(n, 1.5, seed + 3), 0, 1),
                       [(0.0, "#6a6156"), (0.5, "#7d7366"), (1.0, "#93897a")])
    G.col[:] = dustc.reshape(-1, 3)
    G.rough[:] = 0.92
    sp = _spec(n, 0.3, seed + 4)
    s2 = _spec(n, 1.0, seed + 5)
    dens = 0.75 + 0.25 * _band(n, 3, 10, seed + 6)
    # packed road surface: stones touching, fines only in the interstices (embed = fraction sunk)
    _gravel(G, r, 1100, (0.025, 0.05), density=dens, embed=0.25, noise=sp, noise2=s2)
    _gravel(G, r, 7500, (0.012, 0.026), density=dens, embed=0.22, noise=sp, noise2=s2)
    _gravel(G, r, 19000, (0.005, 0.013), density=dens, embed=0.2, noise=sp, noise2=s2, nfac=5)
    _gravel(G, r, 14000, (0.003, 0.007), embed=0.2, noise=sp, noise2=s2, nfac=5, tint="#7d7366", tint_amt=0.3)
    age = _band(n, 4, 14, seed + 7)
    _needles(G, r, 260, None, NEEDLE_STOPS, (0.012, 0.06), (0.4, 0.55), age=np.clip(age + 0.3, 0, 1),
             env=_envelope(G), pair=0.3)
    _leaves(G, r, 10, {"birch": 2, "aspen": 1, "dead": 2}, noise=_spec(n, 1.6, seed + 8), age_bias=0.3)
    h = G.H().copy()
    col = G.C().copy()
    rough = G.R().copy()
    # road dust settles in the hollows and dulls everything a little
    cav = np.clip((_blur(h, 3) - h) / 0.004, 0, 1)
    dust = np.clip(0.25 + 0.5 * cav + 0.25 * (_band(n, 3, 10, seed + 9) - 0.5), 0, 1) * 0.55
    col = col * (1 - dust[..., None]) + dustc * dust[..., None]
    rough = rough + (0.92 - rough) * dust
    return _finish(col, h, rough, G.px, exag=1.1, ao_strength=1.6, ao_bake=0.6, ao_radii=(1.0, 2.5, 6, 16),
                   target=TARGET_LUM["gravel"])


def _edt_wrap(mask: np.ndarray, margin: int = 64) -> np.ndarray:
    """Periodic Euclidean distance (px) to the nearest True pixel of `mask`."""
    m = np.pad(mask, margin, mode="wrap")
    d = ndimage.distance_transform_edt(~m)
    return d[margin:-margin, margin:-margin].astype(np.float32)


def _crack_dist(n: int, cells: int, seed: int, warp_px: float, keep: float = 1.0, keep_freq=(2, 6),
                margin: int = 64) -> np.ndarray:
    """Pixel distance to a tileable network of meandering 1-px crack lines (warped Worley borders;
    `keep` < 1 removes parts of the network so cracks start and stop)."""
    f1, f2, _ = T.worley(n, cells, seed)
    wx, wy = _spec(n, 2.2, seed + 1), _spec(n, 2.2, seed + 2)
    d = T.warp(f2 - f1, wx, wy, warp_px)
    wx2, wy2 = _spec(n, 1.1, seed + 3), _spec(n, 1.1, seed + 4)
    d = T.warp(d, wx2, wy2, 1.5 + warp_px * 0.06)
    line = d < 1.0
    if keep < 1.0:
        line &= _band(n, keep_freq[0], keep_freq[1], seed + 5, 1.2) > (1 - keep)
    if not line.any():
        return np.full((n, n), 1e3, np.float32)
    return _edt_wrap(line, margin)


# --------------------------------------------------------------------------------------------------
# rock_cliff (weathered granite / gneiss, triplanar)
# --------------------------------------------------------------------------------------------------

ROCK_STOPS = [(0.0, "#5c5853"), (0.35, "#6f6a63"), (0.7, "#827c73"), (1.0, "#958e83")]


def _pyramids(n: int, count: int, seed: int, px: float, slope=(0.3, 0.9), hrange: float = 0.1, sx: float = 1.0,
              sy: float = 1.0, k: int = 7, res: int = 2):
    """Angular faceted relief: upper envelope (max) of randomly rotated asymmetric 4-sided pyramids
    centred on tileable feature points. Evaluated at n/res and upsampled (creases soften slightly).
    Returns (height m, valley distance px -- 0 along the valleys between pyramids, facet id)."""
    from scipy.spatial import cKDTree
    r = _rng(seed)
    m = n // res
    pm = px * res
    pts = r.random((count, 2)) * m
    offs = np.array([(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)], np.float64) * m
    tiled = (pts[None, :, :] + offs[:, None, :]).reshape(-1, 2)
    ids = np.tile(np.arange(count), 9)
    th = r.random(count) * 2 * np.pi
    s = (slope[0] + (slope[1] - slope[0]) * r.random((count, 4))).astype(np.float32)
    hh = ((r.random(count) - 0.5) * 2 * hrange).astype(np.float32)
    sc = np.array([sx, sy])
    tree = cKDTree(tiled * sc)
    yy, xx = np.mgrid[0:m, 0:m]
    q = np.stack([xx.ravel() + 0.5, yy.ravel() + 0.5], -1)
    _, ix = tree.query(q * sc, k=k)
    cid = ids[ix]
    dx = (q[:, 0:1] - tiled[ix, 0]).astype(np.float32) * pm
    dy = (q[:, 1:2] - tiled[ix, 1]).astype(np.float32) * pm
    c, sn = np.cos(th[cid]).astype(np.float32), np.sin(th[cid]).astype(np.float32)
    u = dx * c + dy * sn
    v = -dx * sn + dy * c
    sl = s[cid]
    t0 = sl[..., 0] * np.maximum(u, 0)
    t1 = sl[..., 1] * np.maximum(-u, 0)
    t2 = sl[..., 2] * np.maximum(v, 0)
    t3 = sl[..., 3] * np.maximum(-v, 0)
    tmax = np.maximum(np.maximum(t0, t1), np.maximum(t2, t3))
    face = np.where(tmax == t0, 0, np.where(tmax == t1, 1, np.where(tmax == t2, 2, 3)))
    val = hh[cid] - (t0 + t1 + t2 + t3) * 0.7 - tmax * 0.3
    best = np.argmax(val, 1)
    rows = np.arange(val.shape[0])
    v1 = val[rows, best]
    val[rows, best] = -1e9
    v2 = val.max(1)
    fid = (cid[rows, best] * 4 + face[rows, best]).reshape(m, m)
    gap = (v1 - v2).reshape(m, m)
    # valley distance: gap grows ~ (slope_a + slope_b) per metre away from the valley line
    vd = gap / (1.3 * px * float(np.mean(slope)) * 2 / 1.3)
    height = v1.reshape(m, m)
    if res > 1:
        up = lambda a, o: ndimage.zoom(a, res, order=o, mode="grid-wrap", grid_mode=True)  # noqa: E731
        height, vd, fid = up(height, 1), up(vd, 1), up(fid, 0)
    return height.astype(np.float32), vd.astype(np.float32), fid


def layer_rock_cliff(n: int, seed: int) -> Layer:
    px = TILE_M["rock_cliff"] / n
    r = _rng(seed)
    # three scales of angular fracture facets (blocks -> slabs -> chips), sheeting slightly horizontal
    h1, v1, f1 = _pyramids(n, 30, seed + 1, px, (0.15, 0.5), 0.08, 1.0, 1.5)
    h2, _, f2 = _pyramids(n, 220, seed + 2, px, (0.25, 0.75), 0.03, 1.0, 1.2)
    h3, _, _ = _pyramids(n, 1500, seed + 3, px, (0.25, 0.8), 0.012)
    wx, wy = _spec(n, 2.0, seed + 4), _spec(n, 2.0, seed + 5)
    h = h1 + 0.35 * h2 + 0.12 * h3
    h = T.warp(h, wx, wy, 5.0)
    rid = 1 - np.abs(2 * _band(n, 10, 40, seed + 25, 1.4) - 1)
    h = h + 0.012 * rid ** 2
    v1 = T.warp(v1, wx, wy, 5.0)
    grain = _band(n, 100, 500, seed + 6, 0.8)
    pits = _ss(0.8, 0.92, _spec(n, 0.6, seed + 7))
    # open joints along part of the big valleys (continuous lines from the valley distance)
    keep = _ss(0.58, 0.68, _band(n, 2, 7, seed + 8, 1.2))
    jw = 0.4 + 2.6 * _spec(n, 1.8, seed + 9) ** 2
    joint = _ss(jw + 1.5, jw - 0.6, v1) * keep * (0.55 + 0.45 * _spec(n, 1.5, seed + 25))
    h = h + 0.004 * grain - 0.0015 * pits - 0.05 * joint
    h = _blur(h, 0.8)
    # colour: subtle per-facet tint, granular speckle, gently lighter convex edges
    t = np.clip(0.3 * _band(n, 2, 10, seed + 10) + 0.1 * _hash(f2, 1) + 0.1 * _hash(f1, 2)
                + 0.25 * _band(n, 20, 80, seed + 11) + 0.25 * _band(n, 80, 320, seed + 26), 0, 1)
    col = T.gradient(t, ROCK_STOPS)
    warm = _ss(0.55, 0.85, _band(n, 2, 6, seed + 12, 1.5)) * 0.7
    col = col * (1 + np.stack([0.06 * warm, 0.005 * warm, -0.05 * warm], -1))
    gsp = _spec(n, 0.3, seed + 13)
    col = col * (0.93 + 0.14 * gsp)[..., None]
    col = col * (1 - 0.28 * (gsp > 0.9))[..., None] * (1 - 0.3 * pits)[..., None]
    hb = _blur(h, 2.0)
    curv = hb - _blur(hb, 6.0)
    col = col * (1 + 0.12 * np.clip(curv / 0.008, -1, 1))[..., None]
    col = col * (1 - 0.45 * joint)[..., None]
    src = np.clip(joint + np.clip(-curv / 0.012, 0, 1) * 0.3, 0, 1)
    streak = ndimage.gaussian_filter(src, (40, 1.5), mode="wrap")
    streak = np.roll(streak, 40, 0) * _ss(0.4, 0.75, _band(n, 6, 30, seed + 14, 1.0))
    st = np.clip(streak * 2.5, 0, 1)
    col = col * (1 - 0.3 * st)[..., None]
    lic = _ss(0.5, 0.72, _band(n, 8, 40, seed + 15, 1.2)) * _ss(0.2, 0.5, _band(n, 2, 6, seed + 16)) * 0.5
    lcol = T.gradient(_spec(n, 1.0, seed + 17), [(0.0, "#8a9180"), (0.5, "#a4a996"), (1.0, "#b8bba9")])
    col = col * (1 - lic[..., None]) + lcol * lic[..., None]
    darkl = _ss(0.8, 0.86, _band(n, 30, 140, seed + 18, 1.0)) * 0.5
    col = col * (1 - 0.5 * darkl)[..., None]
    orange = _ss(0.86, 0.9, _band(n, 30, 120, seed + 19, 1.0)) * _ss(0.65, 0.8, _band(n, 2, 6, seed + 20)) * 0.8
    col = col * (1 - orange[..., None]) + _cols(["#b5793c"])[0] * orange[..., None]
    valley = np.clip(-curv / 0.012, 0, 1)
    moss = np.clip(_blur(joint, 2.0) * 1.5 + 0.4 * valley, 0, 1) * _ss(0.45, 0.7, _band(n, 4, 20, seed + 21))
    moss *= _ss(0.35, 0.6, _spec(n, 1.0, seed + 22))
    mcol = T.gradient(_spec(n, 0.9, seed + 23), [(0.0, "#3e4a1e"), (0.6, "#56662a"), (1.0, "#74803a")])
    col = col * (1 - moss[..., None]) + mcol * moss[..., None]
    h = h + 0.004 * moss * _spec(n, 0.8, seed + 24)
    rough = 0.8 + 0.06 * (gsp - 0.5) - 0.2 * st
    rough = rough * (1 - lic) + 0.88 * lic
    rough = rough * (1 - moss) + 0.92 * moss
    return _finish(col, h, rough, px, exag=1.0, ao_strength=1.1, ao_bake=0.35, ao_radii=(2, 5, 14, 36),
                   target=TARGET_LUM["rock_cliff"], max_slope=2.6)


# --------------------------------------------------------------------------------------------------
# sand (riverbank)
# --------------------------------------------------------------------------------------------------

SAND_STOPS = [(0.0, "#8d8372"), (0.4, "#9d9381"), (0.75, "#aba18e"), (1.0, "#b8ae9b")]
RIVER_PEBBLES = ["#7d7a74", "#5f5c58", "#9a948a", "#8a7a66", "#b8b2a6", "#4e4c4a", "#7a6e62", "#a39a8c"]


def layer_sand(n: int, seed: int) -> Layer:
    G = Ground(n, TILE_M["sand"])
    r = _rng(seed)
    # two current-ripple trains with different heading / wavelength, blended by a soft mask
    rip_a, _ = _ripples(n, 13, 4, seed + 1, 3.0, 0.4)
    rip_b, _ = _ripples(n, 9, -7, seed + 2, 3.0, 0.4)
    mix_ab = _ss(0.35, 0.65, _band(n, 1, 4, seed + 3, 2.0))
    rip = rip_a * (1 - mix_ab) + rip_b * mix_ab
    fade = 0.3 + 0.7 * _ss(0.25, 0.7, _band(n, 2, 6, seed + 4, 1.5))
    grain = _spec(n, 0.35, seed + 5)
    und = _band(n, 2, 10, seed + 6, 2.0)
    h = 0.012 * und + 0.0045 * fade * rip + 0.0003 * grain
    G.h[:] = h.ravel()
    t = np.clip(0.3 * _band(n, 4, 24, seed + 7, 1.5) + 0.45 * grain + 0.25 * und, 0, 1)
    col = T.gradient(t, SAND_STOPS)
    g2 = _spec(n, 0.2, seed + 8)
    g3 = _spec(n, 0.2, seed + 9)
    col = col * (1 - 0.45 * (g2 > 0.86))[..., None]
    col = col + (0.86 - col) * (0.35 * (g2 < 0.09))[..., None]
    col = col + (_cols(["#a88a78"])[0] - col) * (0.45 * ((g3 > 0.46) & (g3 < 0.5)))[..., None]
    trough = _ss(0.0, -0.9, rip) * fade
    col = col * (1 - 0.08 * trough)[..., None]
    damp = _ss(0.6, 0.85, _band(n, 4, 12, seed + 10, 1.4))
    col = col * (1 - 0.1 * damp)[..., None]
    G.col[:] = col.reshape(-1, 3)
    G.rough[:] = (0.9 - 0.22 * damp).ravel()
    noise = _spec(n, 0.6, seed + 11)
    _blobs(G, r, 320, (0.004, 0.03), RIVER_PEBBLES, kind="pebble", H_ratio=0.35, rough=(0.5, 0.7), tag=TAG_STONE,
           noise=noise, aspect=(0.55, 0.95), irregular=0.6, zoff=-0.003, sharp=0.5)
    _blobs(G, r, 1500, (0.002, 0.005), RIVER_PEBBLES, kind="pebble", H_ratio=0.4, rough=(0.55, 0.75), tag=TAG_STONE,
           noise=noise, aspect=(0.6, 1.0), irregular=0.8, zoff=-0.0008, sharp=0.6)
    age = _band(n, 4, 14, seed + 12)
    _needles(G, r, 200, 0.25 + 0.75 * trough, NEEDLE_STOPS, (0.008, 0.03), (0.38, 0.48), age=np.clip(age + 0.3, 0, 1),
             mode="drape", lift=-0.0001, thick_m=0.0006)
    _leaves(G, r, 12, {"dead": 3, "birch": 1, "willow": 2}, noise=_spec(n, 1.6, seed + 13), age_bias=0.4)
    _twigs(G, r, 6, (0.04, 0.2), (0.002, 0.006), [(0.0, "#8a8274"), (0.5, "#76705f"), (1.0, "#5e584c")], branch=0.3)
    hh = G.H().copy()
    col = G.C().copy()
    rough = G.R().copy()
    return _finish(col, hh, rough, G.px, exag=1.5, ao_strength=1.2, ao_bake=0.45, target=TARGET_LUM["sand"])


# --------------------------------------------------------------------------------------------------
# snow
# --------------------------------------------------------------------------------------------------

def layer_snow(n: int, seed: int) -> Layer:
    G = Ground(n, TILE_M["snow"])
    r = _rng(seed)
    drift = _band(n, 2, 8, seed + 1, 2.4)
    wind, _ = _ripples(n, 9, 3, seed + 2, 1.6, 0.5)
    wfade = _ss(0.35, 0.75, _band(n, 2, 6, seed + 3, 1.5))
    f1, _, _ = T.worley(n, 900, seed + 4)
    cell = n / np.sqrt(900)
    cups = np.clip(f1 / (cell * 0.7), 0, 1) ** 2
    grain = _spec(n, 0.8, seed + 5)
    h = 0.03 * drift + 0.0025 * wfade * wind + 0.0012 * cups + 0.0004 * grain
    G.h[:] = h.ravel()
    t = np.clip(0.5 * _spec(n, 1.6, seed + 6) + 0.5 * grain, 0, 1)
    col = T.gradient(t, [(0.0, "#e6eaee"), (0.5, "#edf0f3"), (1.0, "#f4f6f7")])
    dirty = _ss(0.7, 0.88, _band(n, 4, 14, seed + 7, 1.3)) * 0.22
    col = col * (1 - dirty[..., None]) + _cols(["#d8d4cc"])[0] * dirty[..., None]
    G.col[:] = col.reshape(-1, 3)
    sparkle = _spec(n, 0.2, seed + 8)
    crust = _ss(0.6, 0.75, _band(n, 3, 10, seed + 9, 1.4))
    G.rough[:] = (0.68 - 0.12 * (sparkle > 0.8) - 0.28 * crust).ravel()
    age = _band(n, 4, 14, seed + 10)
    soft = [(0.0, "#8a6a50"), (0.5, "#7a6352"), (1.0, "#6a5c50")]
    _needles(G, r, 320, None, soft, (0.01, 0.022), (0.36, 0.45), age=age, mode="drape", lift=-0.00035,
             thick_m=0.0006)
    _needles(G, r, 60, None, soft, (0.04, 0.07), (0.4, 0.48), age=age, mode="drape", lift=-0.0003, thick_m=0.0008,
             pair=0.5)
    _needles(G, r, 80, None, [(0.0, "#4a4440"), (1.0, "#38322e")], (0.008, 0.02), (0.3, 0.38), mode="drape",
             lift=-0.0002, thick_m=0.0004, bend=0.9, segs=3, tag=TAG_LICHEN)
    _blobs(G, r, 180, (0.002, 0.004), ["#6a5a4a", "#5a4e42", "#7a6452"], kind="flake", H_ratio=0.1, rough=(0.8, 0.9),
           tag=TAG_MISC, zoff=-0.0004, drape=G.smooth(1.0))
    _leaves(G, r, 6, {"dead": 2, "birch": 1}, noise=_spec(n, 1.6, seed + 11), age_bias=0.5, lift=-0.0003)
    _twigs(G, r, 4, (0.04, 0.16), (0.0012, 0.003), TWIG_STOPS, branch=0.6)
    hh = G.H().copy()
    col = G.C().copy()
    rough = G.R().copy()
    # fine snow drifted over the debris edges: soften their contrast
    deb = (G.TAG() != TAG_BASE).astype(np.float32)
    cover = _blur(deb, 1.2) * 0.35 * deb
    col = col * (1 - cover[..., None]) + _cols(["#eceff2"])[0] * cover[..., None]
    return _finish(col, hh, rough, G.px, exag=1.2, ao_strength=0.8, ao_bake=0.25, target=TARGET_LUM["snow"],
                   detile=0.5)


# --------------------------------------------------------------------------------------------------
# asphalt_cracked (aged 1990s small-town road)
# --------------------------------------------------------------------------------------------------

AGG_COLS = ["#74726e", "#86837d", "#5f5d5a", "#94908a", "#827970", "#6a6763", "#a29e96", "#55534f"]


def layer_asphalt_cracked(n: int, seed: int) -> Layer:
    px = TILE_M["asphalt_cracked"] / n
    r = _rng(seed)
    # exposed aggregate in an oxidised, dusty binder
    f1, _, cid = T.worley(n, 60000, seed + 1)
    cell = n / np.sqrt(60000)
    stone = np.clip(1 - f1 / (cell * 0.6), 0, 1)
    wear = _ss(0.3, 0.8, _band(n, 3, 12, seed + 2, 1.3))
    expo = _ss(0.2, 0.55, stone) * (0.25 + 0.4 * wear)
    acol = _cols(AGG_COLS)[(_hash(cid, 1) * len(AGG_COLS)).astype(np.int64) % len(AGG_COLS)]
    acol = acol * (0.88 + 0.24 * _hash(cid, 2))[..., None]
    binder = T.gradient(np.clip(0.6 * _spec(n, 1.3, seed + 3) + 0.4 * _band(n, 20, 80, seed + 30), 0, 1),
                        [(0.0, "#363533"), (0.5, "#42413e"), (1.0, "#4f4d49")])
    binder = binder * (1 + 0.18 * wear)[..., None]
    col = binder * (1 - expo[..., None]) + acol * expo[..., None]
    pores = _ss(0.8, 0.92, _spec(n, 0.4, seed + 4)) * (1 - stone)
    col = col * (1 - 0.35 * pores)[..., None]
    h = 0.0012 * expo * stone - 0.0012 * pores + 0.004 * _band(n, 2, 8, seed + 5, 2.0) + 0.0004 * _spec(n, 0.7, seed + 6)
    rough = 0.88 - 0.04 * expo + 0.05 * pores
    # cracks: long meandering cracks (some sealed with tar), alligator patches, hairlines
    d_long = _crack_dist(n, 10, seed + 10, 45.0, keep=0.62, keep_freq=(2, 5))
    d_alli = _crack_dist(n, 650, seed + 20, 7.0)
    alli_m = _ss(0.6, 0.7, _band(n, 2, 6, seed + 26, 1.5))
    d_hair = _crack_dist(n, 110, seed + 30, 18.0, keep=0.45, keep_freq=(3, 8))
    w_long = 0.6 + 1.1 * _spec(n, 1.8, seed + 31)
    sealed = _ss(0.42, 0.58, _band(n, 2, 5, seed + 40, 1.2))
    crack_long = _ss(w_long + 0.9, w_long - 0.4, d_long)
    crack_alli = _ss(1.2, 0.2, d_alli) * alli_m
    crack_hair = _ss(0.9, 0.0, d_hair) * 0.6
    seal_w = 6.0 + 2.5 * _spec(n, 2.0, seed + 41)
    seal = _ss(seal_w + 1.2, seal_w - 1.2, d_long) * sealed
    crack = np.maximum(np.maximum(crack_long * (1 - sealed), crack_alli), crack_hair) * (1 - seal)
    fill = _ss(0.45, 0.7, _spec(n, 1.5, seed + 42))
    ccol = _cols(["#1d1c1b"])[0] * (1 - fill[..., None]) + _cols(["#544b40"])[0] * fill[..., None]
    col = col * (1 - crack[..., None]) + ccol * crack[..., None]
    # ravelled shoulders along open cracks: binder lost, aggregate loose, lighter and coarser
    rav = _ss(w_long + 4.0, w_long + 0.8, d_long) * (1 - sealed) * (1 - crack)
    rav = np.maximum(rav, _ss(2.5, 1.0, d_alli) * alli_m * (1 - crack) * 0.6)
    col = col * (1 + 0.12 * rav)[..., None]
    h = h - 0.008 * crack - 0.0012 * rav
    rough = rough * (1 - crack) + 0.95 * crack
    green = crack * _ss(0.72, 0.82, _band(n, 8, 40, seed + 43, 1.0))
    gcol = T.gradient(_spec(n, 0.8, seed + 44), [(0.0, "#3a4a1e"), (1.0, "#6a7a30")])
    col = col * (1 - green[..., None]) + gcol * green[..., None]
    h = h + 0.006 * green
    # tar sealant overband: black, slightly raised, smooth, semi-glossy, worn at the edges
    swear = _ss(0.3, 0.6, _spec(n, 1.4, seed + 46))
    seal = seal * (0.55 + 0.45 * swear)
    scol = T.gradient(_spec(n, 1.6, seed + 45), [(0.0, "#161616"), (1.0, "#272624")])
    col = col * (1 - seal[..., None]) + scol * seal[..., None]
    h = h * (1 - seal) + (_blur(h, 3) + 0.0012) * seal
    rough = rough * (1 - seal) + 0.48 * seal
    # oil drips, dried puddle rings
    oil = _ss(0.88, 0.93, _band(n, 6, 24, seed + 47, 1.3)) * _ss(0.55, 0.7, _band(n, 2, 5, seed + 48)) * 0.8
    col = col * (1 - 0.35 * oil)[..., None]
    rough = rough - 0.3 * oil
    pud = _ss(0.6, 0.75, _band(n, 2, 6, seed + 49, 1.8))
    ring = np.clip(1 - np.abs(pud - 0.5) / 0.12, 0, 1) * 0.5
    col = col * (1 + 0.07 * ring)[..., None] * (1 - 0.05 * pud)[..., None]
    low = np.clip((_blur(h, 6) - h) / 0.0025, 0, 1) * (1 - seal)
    col = col * (1 - 0.3 * low[..., None]) + _cols(["#6e6658"])[0] * (0.3 * low[..., None])
    G = Ground(n, TILE_M["asphalt_cracked"])
    G.h[:] = h.ravel()
    G.col[:] = col.reshape(-1, 3)
    G.rough[:] = rough.ravel()
    age = _band(n, 4, 14, seed + 50)
    _leaves(G, r, 8, {"birch": 2, "dead": 3, "aspen": 1}, noise=_spec(n, 1.6, seed + 51), age_bias=0.35)
    _needles(G, r, 120, None, NEEDLE_STOPS, (0.012, 0.05), (0.4, 0.5), age=np.clip(age + 0.3, 0, 1), env=_envelope(G))
    return _finish(G.C().copy(), G.H().copy(), G.R().copy(), px, exag=1.0, ao_strength=1.1, ao_bake=0.45,
                   target=TARGET_LUM["asphalt_cracked"], rough_detile=0.2)


# --------------------------------------------------------------------------------------------------
# concrete_slab (2 m slabs, saw-cut joints on the tile borders and the middle)
# --------------------------------------------------------------------------------------------------

def layer_concrete_slab(n: int, seed: int) -> Layer:
    px = TILE_M["concrete_slab"] / n
    r = _rng(seed)
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    half = n // 2
    jx = (xx + 0.5) % half
    jy = (yy + 0.5) % half
    jx = np.minimum(jx, half - jx)
    jy = np.minimum(jy, half - jy)
    jd = np.minimum(jx, jy)
    slab = ((xx // half) + 2 * (yy // half)).astype(np.int64)
    sp_n = _spec(n, 1.2, seed + 1)
    jw = 1.6 + 2.6 * _ss(0.65, 0.9, sp_n)
    joint = _ss(jw + 0.8, jw - 0.8, jd)
    tx_ = (_hash(slab, 1) - 0.5) * 0.004
    ty_ = (_hash(slab, 2) - 0.5) * 0.004
    lx = ((xx + 0.5) % half) / half - 0.5
    ly = ((yy + 0.5) % half) / half - 0.5
    h = tx_ * lx + ty_ * ly + 0.0015 * _hash(slab, 3) + 0.0008 * (lx * lx + ly * ly)
    paste = _spec(n, 0.9, seed + 2)
    streak_a = _spec(n, 1.0, seed + 3, aniso=(1.0, 7.0))
    streak_b = _spec(n, 1.0, seed + 4, aniso=(7.0, 1.0))
    broom = np.where(_hash(slab, 4) > 0.5, streak_a, streak_b)
    wear = _ss(0.35, 0.8, _band(n, 3, 12, seed + 5, 1.3))
    h = h + 0.0004 * paste + 0.00025 * broom * (1 - wear)
    f1, _, cid = T.worley(n, 40000, seed + 6)
    cell = n / np.sqrt(40000)
    stone = np.clip(1 - f1 / (cell * 0.55), 0, 1)
    expo = _ss(0.25, 0.55, stone) * wear * 0.45
    tint = (0.95 + 0.1 * _hash(slab, 5))[..., None] * (1 + np.stack([0.02, 0.0, -0.02])[None, None, :] * (_hash(slab, 6) - 0.5)[..., None] * 2)
    base = T.gradient(np.clip(0.5 * paste + 0.25 * broom + 0.25 * _band(n, 4, 20, seed + 7), 0, 1),
                      [(0.0, "#83807a"), (0.5, "#8f8c86"), (1.0, "#9b9891")]) * tint
    acol = _cols(AGG_COLS)[(_hash(cid, 3) * len(AGG_COLS)).astype(np.int64) % len(AGG_COLS)] * 1.1
    col = base * (1 - expo[..., None]) + acol * expo[..., None]
    h = h + 0.0006 * expo * stone
    pits = _ss(0.88, 0.94, _spec(n, 0.5, seed + 8)) * (0.3 + 0.7 * wear)
    col = col * (1 - 0.3 * pits)[..., None]
    h = h - 0.0015 * pits
    d_c = _crack_dist(n, 9, seed + 10, 40.0, keep=0.4, keep_freq=(2, 5))
    d_h = _crack_dist(n, 60, seed + 20, 14.0, keep=0.25, keep_freq=(3, 8))
    crack = np.maximum(_ss(1.1, 0.2, d_c), _ss(0.8, 0.0, d_h) * 0.55) * (1 - joint)
    wet = np.clip(_blur(np.maximum(joint, crack), 10) * 2.5, 0, 1) * _ss(0.3, 0.7, _band(n, 3, 10, seed + 11))
    col = col * (1 - 0.16 * wet)[..., None]
    rust = _ss(0.84, 0.92, _band(n, 5, 20, seed + 12, 1.3)) * _ss(0.6, 0.8, _band(n, 2, 6, seed + 13)) * 0.6
    col = col * (1 - 0.5 * rust[..., None]) + _cols(["#8a5a36"])[0] * (0.5 * rust[..., None])
    oil = _ss(0.88, 0.94, _band(n, 5, 18, seed + 14, 1.3)) * _ss(0.6, 0.75, _band(n, 2, 5, seed + 15)) * 0.7
    col = col * (1 - 0.3 * oil)[..., None]
    eff = np.clip(_blur(crack, 3) * 3, 0, 1) * _ss(0.5, 0.7, _band(n, 4, 12, seed + 16))
    col = col + (0.84 - col) * (0.18 * eff)[..., None]
    dirt = np.clip(1 - jd / 18.0, 0, 1) ** 2
    col = col * (1 - 0.2 * dirt)[..., None]
    col = col * (1 - 0.75 * crack[..., None]) + _cols(["#3a3834"])[0] * (0.75 * crack[..., None])
    h = h - 0.004 * crack
    jcol = T.gradient(_spec(n, 1.2, seed + 17), [(0.0, "#2a2620"), (0.6, "#3e3628"), (1.0, "#4e4a30")])
    jmoss = joint * _ss(0.5, 0.75, _band(n, 6, 30, seed + 18, 1.0))
    jcol = jcol * (1 - jmoss[..., None]) + _cols(["#4f5f24"])[0] * jmoss[..., None]
    col = col * (1 - joint[..., None]) + jcol * joint[..., None]
    h = h - 0.009 * joint + 0.004 * jmoss
    rough = 0.9 - 0.05 * expo + 0.05 * joint - 0.22 * oil - 0.08 * wet
    G = Ground(n, TILE_M["concrete_slab"])
    G.h[:] = h.ravel()
    G.col[:] = col.reshape(-1, 3)
    G.rough[:] = rough.ravel()
    lich = _ss(0.55, 0.75, _band(n, 3, 10, seed + 19, 1.2))
    _blobs(G, r, 700, (0.006, 0.03), ["#bdbcb0", "#b0b1a3", "#c4c1ac", "#a6aa9a", "#b9b495"], kind="flake",
           density=lich, H_ratio=0.02, rough=(0.88, 0.95), tag=TAG_LICHEN, aspect=(0.75, 1.0), irregular=0.8,
           zoff=0.0001, drape=G.smooth(1.0), noise=_spec(n, 0.8, seed + 20))
    _blobs(G, r, 400, (0.004, 0.01), ["#4a4a44", "#3e3e3a", "#55554c"], kind="flake", density=lich * 0.7 + 0.1,
           H_ratio=0.02, rough=(0.9, 0.95), tag=TAG_LICHEN, aspect=(0.75, 1.0), irregular=0.8, zoff=0.0001,
           drape=G.smooth(1.0))
    age = _band(n, 4, 14, seed + 21)
    _leaves(G, r, 10, {"birch": 2, "dead": 3, "aspen": 1}, noise=_spec(n, 1.6, seed + 22), age_bias=0.35)
    _needles(G, r, 150, None, NEEDLE_STOPS, (0.012, 0.05), (0.4, 0.5), age=np.clip(age + 0.3, 0, 1), env=_envelope(G))
    return _finish(G.C().copy(), G.H().copy(), G.R().copy(), px, exag=1.0, ao_strength=1.0, ao_bake=0.4,
                   target=TARGET_LUM["concrete_slab"], detile=0.5, rough_detile=0.2)


LAYER_FUNCS = {
    "forest_floor": layer_forest_floor,
    "moss_ground": layer_moss_ground,
    "grass_ground": layer_grass_ground,
    "dirt": layer_dirt,
    "mud": layer_mud,
    "gravel": layer_gravel,
    "rock_cliff": layer_rock_cliff,
    "sand": layer_sand,
    "snow": layer_snow,
    "asphalt_cracked": layer_asphalt_cracked,
    "concrete_slab": layer_concrete_slab,
}

LAYER_SEEDS = {name: 1000 + 37 * i for i, name in enumerate(LAYERS)}


def build_layer(name: str, n: int) -> Layer:
    return LAYER_FUNCS[name](n, LAYER_SEEDS[name])


_CHANNELS = ("albedo", "height", "normal", "ao", "rough")
# Every consumer of a layer: its PBR set + the three arrays. The cache entry is deleted after the last.
_CONSUMERS = ("set", "albedo_array", "normal_array", "orm_array")


def _quantize(L: Layer) -> dict:
    return {k: (np.clip(getattr(L, k), 0, 1) * 255.0 + 0.5).astype(np.uint8) for k in _CHANNELS}


def _dequantize(q: dict) -> Layer:
    """uint8 -> float32 in 0..1. Writers re-quantize with texlib (x * 255 + 0.5), which reproduces the
    same bytes exactly, so outputs are identical whether a layer came from the cache or not."""
    f = {k: q[k].astype(np.float32) / np.float32(255.0) for k in _CHANNELS}
    L = Layer.__new__(Layer)
    for k in _CHANNELS:
        setattr(L, k, f[k])
    return L


def cached_layer(name: str, n: int, consumer: str) -> Layer:
    """build_layer(), shared between the 4 tasks that need each layer (its set + 3 arrays): the first
    task computes it under a file lock and stores the 8-bit quantized maps in
    <GEN_ROOT>/.cache/terrain (keyed by the terrain.py + texlib.py source hash); the others load it. The
    entry is deleted once all 4 consumers have used it. Every path returns the dequantized maps, so the
    written files are byte-identical with or without the cache (--check-determinism builds into a
    fresh GEN_ROOT and verifies it)."""
    try:
        import fcntl
        import hashlib
        import os
        from ...core.paths import GEN_ROOT
    except ImportError:  # pragma: no cover (non-POSIX): just compute
        return _dequantize(_quantize(build_layer(name, n)))
    src = hashlib.sha256(pathlib.Path(__file__).read_bytes() + pathlib.Path(T.__file__).read_bytes()).hexdigest()[:16]
    d = GEN_ROOT / ".cache" / "terrain"
    d.mkdir(parents=True, exist_ok=True)
    key = f"{name}_{n}_{LAYER_SEEDS[name]}_{src}"
    path = d / f"{key}.npz"
    used = d / f"{key}.used"
    with open(d / f"{name}.lock", "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            for old in sorted(d.glob(f"{name}_{n}_*")):
                if not old.name.startswith(key):
                    old.unlink(missing_ok=True)
            if path.exists():
                with np.load(path) as z:
                    q = {k: z[k] for k in _CHANNELS}
            else:
                q = _quantize(build_layer(name, n))
                tmp = d / f"{key}.tmp.npz"
                np.savez_compressed(tmp, **q)
                os.replace(tmp, path)
            seen = set(used.read_text().split()) if used.exists() else set()
            seen.add(consumer)
            if seen >= set(_CONSUMERS):
                path.unlink(missing_ok=True)
                used.unlink(missing_ok=True)
            else:
                used.write_text("\n".join(sorted(seen)) + "\n")
            return _dequantize(q)
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


# --------------------------------------------------------------------------------------------------
# Writers / registration
# --------------------------------------------------------------------------------------------------

def _save_layer_set(out, L: Layer) -> None:
    out = pathlib.Path(out)
    T.save_rgb(out.with_name(out.name + "_albedo.png"), L.albedo)
    T.save_rgb(out.with_name(out.name + "_normal.png"), L.normal)
    T.save_orm(out.with_name(out.name + "_orm.png"), L.ao, L.rough, 0.0)


def _register_layer(name: str) -> None:
    @texture(f"terrain_{name}", size=1024, seed=LAYER_SEEDS[name], kind="pbr")
    def _gen(size: int, seed: int, out, _name=name) -> None:
        assert seed == LAYER_SEEDS[_name]
        _save_layer_set(out, cached_layer(_name, size, "set"))


for _ln in LAYER_FUNCS:
    _register_layer(_ln)


def _check_contract() -> None:
    """The array slice order / tile sizes are a contract with the terrain shader: fail loudly if the
    generator and game/data/materials/terrain_layers.json disagree."""
    data = json.loads(LAYERS_JSON.read_text())
    if data.get("layers") != LAYERS:
        raise ValueError(f"terrain_layers.json layer order {data.get('layers')} != generator {LAYERS}")
    tm = data.get("tile_metres", {})
    bad = [k for k in LAYERS if abs(float(tm.get(k, -1)) - TILE_M[k]) > 1e-6]
    if bad:
        raise ValueError(f"terrain_layers.json tile_metres disagree with the generator for {bad}")


def _save_strip(out, rows: list[np.ndarray]) -> None:
    strip = np.concatenate(rows, 0)
    path = pathlib.Path(str(out) + ".png")
    if strip.shape[-1] == 4:
        T.save_rgba(path, strip)
    else:
        T.save_rgb(path, strip)


@texture("terrain_albedo_array", size=1024, seed=1, kind="array", import_kind="albedo", slices=len(LAYERS), sources=["game/data/materials/terrain_layers.json"])
def terrain_albedo_array(size: int, seed: int, out, slices: int) -> None:
    """RGB = albedo (sRGB), A = height 0..1 (for height-based blending)."""
    _check_contract()
    assert slices == len(LAYERS)
    rows = {}
    for name in LAYERS:
        L = cached_layer(name, size, "albedo_array")
        rows[name] = np.concatenate([L.albedo, L.height[..., None]], -1)
    _save_strip(out, [rows[k] for k in LAYERS])


@texture("terrain_normal_array", size=1024, seed=1, kind="array", import_kind="normal", slices=len(LAYERS), sources=["game/data/materials/terrain_layers.json"])
def terrain_normal_array(size: int, seed: int, out, slices: int) -> None:
    """Tangent-space normals, OpenGL convention (+Y up)."""
    _check_contract()
    rows = {name: cached_layer(name, size, "normal_array").normal for name in LAYERS[::-1]}  # other order: overlap work
    _save_strip(out, [rows[k] for k in LAYERS])


@texture("terrain_orm_array", size=1024, seed=1, kind="array", import_kind="data", slices=len(LAYERS), sources=["game/data/materials/terrain_layers.json"])
def terrain_orm_array(size: int, seed: int, out, slices: int) -> None:
    """R = AO, G = roughness, B = metallic (0)."""
    _check_contract()
    rows = {}
    for name in LAYERS[5:] + LAYERS[:5]:
        L = cached_layer(name, size, "orm_array")
        rows[name] = np.stack([L.ao, L.rough, np.zeros_like(L.ao)], -1)
    _save_strip(out, [rows[k] for k in LAYERS])


@texture("terrain_macro_variation", size=1024, seed=7301, kind="single", import_kind="data")
def terrain_macro_variation(size: int, seed: int, out) -> None:
    """Large-scale variation map (tileable; meant to cover ~128 m per tile, see terrain_layers.json):
    R brightness (0.5 = neutral), G warm/cool hue shift (0.5 = neutral), B damp/patch mask 0..1,
    A mid-scale breakup noise for dissolving height blends and anti-tiling."""
    n = size
    bright = T.normalize(0.55 * _band(n, 1, 6, seed + 1, 2.0) + 0.3 * _band(n, 4, 24, seed + 2, 1.6)
                         + 0.15 * _band(n, 20, 96, seed + 3, 1.2))
    bright = 0.5 + (bright - bright.mean()) * 1.4
    hue = T.normalize(0.6 * _band(n, 1, 8, seed + 4, 2.0) + 0.4 * _band(n, 6, 32, seed + 5, 1.5))
    hue = 0.5 + (hue - hue.mean()) * 1.4
    wx, wy = _spec(n, 2.5, seed + 6), _spec(n, 2.5, seed + 7)
    damp = T.warp(_band(n, 2, 16, seed + 8, 1.6), wx, wy, 40.0)
    damp = _ss(0.45, 0.75, damp)
    brk = T.normalize(_band(n, 8, 64, seed + 9, 1.3) * 0.7 + _band(n, 48, 200, seed + 10, 1.0) * 0.3)
    T.save_rgba(pathlib.Path(str(out) + ".png"), np.stack([np.clip(bright, 0, 1), np.clip(hue, 0, 1), damp, brk], -1))


@texture("terrain_detail_normal", size=1024, seed=7401, kind="single", import_kind="normal")
def terrain_detail_normal(size: int, seed: int, out) -> None:
    """Generic tileable micro detail (grit, crumbs, tiny creases), authored for ~0.6 m per tile and
    meant to be blended over every layer up close (OpenGL normal)."""
    n = size
    px = 0.6 / n
    f1, _, cid = T.worley(n, 22000, seed + 1)
    cell = n / np.sqrt(22000)
    grit = np.clip(1 - (f1 / (cell * 0.65)) ** 2, 0, 1) * (0.4 + 0.6 * _hash(cid, 1))
    f1b, _, cidb = T.worley(n, 2600, seed + 2)
    cellb = n / np.sqrt(2600)
    crumbs = np.clip(1 - (f1b / (cellb * 0.6)) ** 2, 0, 1) ** 0.7 * _ss(0.4, 0.7, _hash(cidb, 2))
    crease = 1 - np.abs(2 * _band(n, 6, 40, seed + 3, 1.3) - 1)
    h = (0.00025 * grit + 0.0006 * crumbs + 0.0004 * crease ** 3 + 0.0002 * _band(n, 2, 12, seed + 4, 2.0)
         + 0.00008 * _spec(n, 0.6, seed + 5))
    T.save_rgb(pathlib.Path(str(out) + ".png"), _normal(h.astype(np.float32), px, 1.0, 0.5, 2.0))
