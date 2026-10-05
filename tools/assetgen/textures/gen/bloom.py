"""The Bloom on the land (ADR-0025): mycelium textures.

Outputs
  bloom_web_mask     forest-floor web, 1.6 m tile (terrain.gdshader `bloom_web_*`). Linear RGBA:
                     R coverage priority, G age, B cottony mat, A thread body (see below)
  bloom_web_normal   its relief (tangent space, OpenGL)
  bloom_web_cov      the web's thread masks at a third, two thirds and all of full growth (RGB; see
                     below), A unused
  bloom_bark_mask    threads on bark, ~1 m of trunk per tile (bark.gdshader `bloom_*`): R priority,
                     G age, B bracket-like crusts, A thread body
  bloom_bark_normal  its relief
  bloom_bark_cov     the bark threads' masks at three growths (RGB) and A: all threads plus the felt
                     sheath that binds the most colonised trunks
  bloom_cap          fruiting-body flesh (caps, stems, gills; bloom_fungus.gdshader): radial fibrils
                     along V, so caps mapped polar (U around, V out from the stem) show them radiating
  bloom_mound        the felted mycelium of a rooting mound: litter and soil bound in white threads

How the shaders read a mask: the priority (R) is rank-equalised, so a threshold t reveals exactly
the share 1 - t of the tile in importance order: the main cords first, then their branches and the
fans at their growing tips, then the fine net (and on the ground the cotton mat, B). Pixels no
thread covers rank below every thread pixel, ordered by their distance to one, so mipmaps of the
mask thicken threads into a haze instead of dropping them. The shaders set the threshold from the
Bloom field: the web grows across the ground, and up a trunk, as the field rises.

Thresholds only hold while a texel covers a pixel or more: mipmapped priorities average threads and
gaps, and a threshold on the average turns the web into blotches. So each mask has a coverage map:
the very masks those thresholds reveal at a third, two thirds and all of full growth, binary at full
resolution, so the GPU's mipmaps hold the exact share of threads in a footprint. Past a pixel or two
the shaders read the share at the current growth from it (and fade it, the threads being hair-thin).

Threads are stroked as anti-aliased capsules on a periodic canvas (seamless tiles). Directions on
bark: Blender's V runs up the trunk and the glTF export flips it, so "up the trunk" is up the image
(toward row 0): cords climb toward row 0 and fans open that way.
"""
from __future__ import annotations

import functools
import math

import numpy as np

from .. import texlib as T
from ..registry import texture

WEB_TILE_M = 1.6
BARK_TILE_M = 1.0


# --------------------------------------------------------------------------------------------------
# Strokes on a periodic canvas
# --------------------------------------------------------------------------------------------------

class Strokes:
    """Accumulates tapered round strokes (polylines in pixels, any coordinates: the canvas wraps)
    with a per-stroke priority, age and body, then rasterises them in one pass."""

    def __init__(self) -> None:
        self.ax: list[float] = []
        self.ay: list[float] = []
        self.bx: list[float] = []
        self.by: list[float] = []
        self.ra: list[float] = []
        self.rb: list[float] = []
        self.pri: list[float] = []
        self.age: list[float] = []
        self.body: list[float] = []

    def line(self, pts, r0: float, r1: float, pri0: float, pri1: float, age0: float, age1: float, body: float) -> None:
        k = len(pts) - 1
        for i in range(k):
            s0, s1 = i / k, (i + 1) / k
            self.ax.append(pts[i][0])
            self.ay.append(pts[i][1])
            self.bx.append(pts[i + 1][0])
            self.by.append(pts[i + 1][1])
            self.ra.append(r0 + (r1 - r0) * s0)
            self.rb.append(r0 + (r1 - r0) * s1)
            self.pri.append(pri0 + (pri1 - pri0) * (s0 + s1) * 0.5)
            self.age.append(age0 + (age1 - age0) * (s0 + s1) * 0.5)
            self.body.append(body)

    def raster(self, n: int, chunk_px: int = 1_500_000) -> dict[str, np.ndarray]:
        """cov: coverage (max), pri: priority x core profile of the strongest covering stroke,
        age: coverage-weighted mean age, body: max body x coverage, h: height (round profile)."""
        f32 = np.float32
        ax, ay = np.asarray(self.ax, np.float64), np.asarray(self.ay, np.float64)
        bx, by = np.asarray(self.bx, np.float64), np.asarray(self.by, np.float64)
        ra, rb = np.asarray(self.ra, f32), np.asarray(self.rb, f32)
        pri, age, body = np.asarray(self.pri, f32), np.asarray(self.age, f32), np.asarray(self.body, f32)
        N = n * n
        cov = np.zeros(N, f32)
        prim = np.zeros(N, f32)
        bod = np.zeros(N, f32)
        hgt = np.zeros(N, f32)
        age_w = np.zeros(N, np.float64)
        w_sum = np.zeros(N, np.float64)
        ext = np.maximum(np.abs(bx - ax), np.abs(by - ay)) + 2 * np.maximum(ra, rb) + 4
        Pk = (np.ceil(ext / 4) * 4).astype(np.int64)
        for P in np.unique(Pk):
            ids = np.nonzero(Pk == P)[0]
            step = max(1, chunk_px // int(P * P))
            g = np.arange(P, dtype=np.int64)
            for st in range(0, ids.size, step):
                k = ids[st:st + step]
                cx = (ax[k] + bx[k]) * 0.5
                cy = (ay[k] + by[k]) * 0.5
                ox = np.floor(cx).astype(np.int64) - P // 2
                oy = np.floor(cy).astype(np.int64) - P // 2
                X = ox[:, None, None] + g[None, None, :]
                Y = oy[:, None, None] + g[None, :, None]
                px = (X + 0.5 - ax[k][:, None, None]).astype(f32)
                py = (Y + 0.5 - ay[k][:, None, None]).astype(f32)
                ux = (bx[k] - ax[k]).astype(f32)[:, None, None]
                uy = (by[k] - ay[k]).astype(f32)[:, None, None]
                l2 = np.maximum(ux * ux + uy * uy, f32(1e-6))
                t = np.clip((px * ux + py * uy) / l2, 0, 1)
                qx = px - t * ux
                qy = py - t * uy
                d = np.sqrt(qx * qx + qy * qy)
                rr = ra[k][:, None, None] + (rb[k] - ra[k])[:, None, None] * t
                c = np.where(rr >= 0.5, np.clip(rr + 0.5 - d, 0, 1), 2 * rr * np.clip(1 - d, 0, 1))
                prof = np.sqrt(np.clip(1 - (d / np.maximum(rr, f32(0.5))) ** 2, 0, 1))
                idx = ((Y % n) * n + (X % n)).reshape(-1)
                cf = c.reshape(-1)
                sel = cf > 0.004
                idx = idx[sel]
                cf = cf[sel]
                pf = (pri[k][:, None, None] * (0.55 + 0.45 * prof) * (c > 0.3)).reshape(-1)[sel]
                bf = (body[k][:, None, None] * c).reshape(-1)[sel]
                hf = (rr * prof * (0.4 + 0.6 * body[k][:, None, None])).reshape(-1)[sel]
                af = np.broadcast_to(age[k][:, None, None], c.shape).reshape(-1)[sel]
                np.maximum.at(cov, idx, cf)
                np.maximum.at(prim, idx, pf)
                np.maximum.at(bod, idx, bf)
                np.maximum.at(hgt, idx, hf.astype(f32))
                np.add.at(age_w, idx, (af * cf).astype(np.float64))
                np.add.at(w_sum, idx, cf.astype(np.float64))
        agem = np.where(w_sum > 0, age_w / np.maximum(w_sum, 1e-9), 0.0).astype(f32)
        sh = (n, n)
        return {"cov": cov.reshape(sh), "pri": prim.reshape(sh), "age": agem.reshape(sh), "body": bod.reshape(sh),
                "h": hgt.reshape(sh)}


def _walk(r: np.random.Generator, x: float, y: float, ang: float, length: float, step: float, curl: float,
          pull: tuple[float, float] | None = None) -> list[tuple[float, float]]:
    """A wandering thread: persistent direction with a random turn per step; `pull` = (angle,
    strength) bends it back toward a preferred heading (up the trunk)."""
    pts = [(x, y)]
    steps = max(2, int(length / step))
    for _ in range(steps):
        ang += r.normal(0.0, curl)
        if pull is not None:
            d = math.atan2(math.sin(pull[0] - ang), math.cos(pull[0] - ang))
            ang += d * pull[1]
        x += math.cos(ang) * step
        y += math.sin(ang) * step
        pts.append((x, y))
    return pts


def _along(pts, s: float) -> tuple[float, float, float]:
    """Point and heading at fraction s of a polyline (by vertex count; steps are even)."""
    i = min(len(pts) - 2, max(0, int(s * (len(pts) - 1))))
    (x0, y0), (x1, y1) = pts[i], pts[i + 1]
    return x0, y0, math.atan2(y1 - y0, x1 - x0)


def _rank(values: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """Stable rank of `values` mapped evenly onto [lo, hi)."""
    order = np.argsort(values, kind="stable")
    out = np.empty(values.size, np.float32)
    out[order] = lo + (hi - lo) * (np.arange(values.size, dtype=np.float32) + 0.5) / values.size
    return out


def _priority(st: dict[str, np.ndarray], n: int, threshold: float = 0.3) -> tuple[np.ndarray, float]:
    """Rank-equalised priority: thread pixels over [1 - F, 1) by their stroke priority (cores above
    margins), the rest over [0, 1 - F) by closeness to a thread. Returns (map, F)."""
    cov = st["cov"]
    thread = cov > threshold
    F = float(thread.mean())
    prox = T.blur(cov, 2.5) + 0.25 * T.blur(cov, 8.0)
    out = np.zeros(n * n, np.float32)
    tf = thread.ravel()
    out[tf] = _rank(st["pri"].ravel()[tf] + 1e-4 * cov.ravel()[tf], 1.0 - F, 1.0)
    out[~tf] = _rank(prox.ravel()[~tf], 0.0, 1.0 - F)
    return out.reshape(n, n), F


def _save_mask(out, r: np.ndarray, g: np.ndarray, b: np.ndarray, a: np.ndarray) -> None:
    T.save_rgba(str(out) + ".png", np.stack([r, g, b, a], -1))


def _coverage(pri: np.ndarray, F: float, sheath: float = 0.0) -> tuple[np.ndarray, ...]:
    """The masks a priority threshold reveals at a third, two thirds and all of full growth (the
    shaders' t = 1 - growth * F), and all threads plus `sheath` of the closest gap ranks below them
    (a soft felt the bark shader grows around the cords; 0 = the full-growth mask again)."""
    layers = [(pri > 1.0 - F * k).astype(np.float32) for k in (1.0 / 3.0, 2.0 / 3.0, 1.0)]
    a = T.smoothstep(1.0 - F - sheath, 1.0 - F, pri).astype(np.float32) if sheath > 0.0 else layers[2]
    return (*layers, a)


# --------------------------------------------------------------------------------------------------
# Forest-floor web
# --------------------------------------------------------------------------------------------------

def _merge(a: dict[str, np.ndarray], b: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Two stroke rasters as one (max coverage, priority, body and height; age by coverage)."""
    w = a["cov"] + b["cov"]
    out = {k: np.maximum(a[k], b[k]) for k in ("cov", "pri", "body", "h")}
    out["age"] = np.where(w > 0, (a["age"] * a["cov"] + b["age"] * b["cov"]) / np.maximum(w, 1e-6), 0.0).astype(np.float32)
    return out


def _web(n: int, seed: int) -> dict[str, np.ndarray]:
    """Cords radiating from colony points spread evenly over the tile (a jittered grid, so no part
    of a repeat is bare), branching and opening into feathery fans at their growing tips; a fine net
    bridging the gaps near the cords (what binds the needles and leaves); small cottony tufts
    gathered along the cords."""
    r = T.rng(seed)
    px_m = WEB_TILE_M / n
    S = Strokes()
    mm = lambda v: v / 1000.0 / px_m  # noqa: E731  (millimetres -> pixels)

    def cord(x, y, ang, length, rad, pri, age, depth):
        pts = _walk(r, x, y, ang, length, mm(8.0), 0.14)
        S.line(pts, rad, rad * 0.5, pri, pri - 0.12, age, age - 0.4, 1.0)
        s = r.uniform(0.1, 0.25)
        side = 1.0 if r.random() < 0.5 else -1.0
        while s < 0.9 and depth < 3:
            bx, by, ba = _along(pts, s)
            rem = (1.0 - s) * length
            cord(bx, by, ba + side * r.uniform(0.4, 1.0), rem * r.uniform(0.35, 0.65), rad * r.uniform(0.55, 0.72),
                 pri - 0.1, age - 0.15 * s - 0.05, depth + 1)
            side = -side
            s += r.uniform(mm(45.0), mm(110.0)) / max(length, 1.0)
        # The growing tip opens forward into a feathery fan.
        tx, ty = pts[-1]
        _, _, ta = _along(pts, 1.0)
        for _ in range(int(r.integers(10, 20))):
            a = ta + r.normal(0.0, 0.35)
            S.line(_walk(r, tx, ty, a, mm(r.uniform(20.0, 60.0)), mm(4.0), 0.12), mm(0.8), mm(0.45),
                   pri - 0.2, pri - 0.28, 0.0, 0.0, 0.6)

    g = 4
    tips: list[tuple[float, float]] = []
    for gy in range(g):
        for gx in range(g):
            cx = (gx + 0.5 + r.uniform(-0.35, 0.35)) * n / g
            cy = (gy + 0.5 + r.uniform(-0.35, 0.35)) * n / g
            a0 = r.uniform(0, 2 * math.pi)
            arms = int(r.integers(3, 6))
            for k in range(arms):
                a = a0 + 2 * math.pi * k / arms + r.normal(0.0, 0.35)
                ln = mm(r.uniform(220.0, 480.0))
                cord(cx, cy, a, ln, mm(r.uniform(1.8, 3.0)), r.uniform(0.9, 1.0), r.uniform(0.75, 1.0), 0)
                tips.append((cx + math.cos(a) * ln * 0.8, cy + math.sin(a) * ln * 0.8))
    # Anastomoses: cords from neighbouring colonies grow into each other and fuse into a net.
    for i, (x0, y0) in enumerate(tips):
        for x1, y1 in tips[i + 1:]:
            dx = (x1 - x0 + n / 2) % n - n / 2
            dy = (y1 - y0 + n / 2) % n - n / 2
            d = math.hypot(dx, dy)
            if mm(60.0) < d < mm(200.0) and r.random() < 0.45:
                a = math.atan2(dy, dx)
                pts = _walk(r, x0, y0, a, d, mm(8.0), 0.1)
                S.line(pts, mm(1.0), mm(0.8), 0.86, 0.82, 0.5, 0.45, 0.9)
    cords = S.raster(n)
    # The fine net bridges gaps near the cords: hair-fine threads from points the cords pass close to.
    near = T.blur(cords["cov"], 10.0)
    near = near / max(float(near.max()), 1e-6)
    cdf = np.cumsum((near.ravel() + 0.03) ** 1.4)
    picks = np.searchsorted(cdf, r.uniform(0.0, cdf[-1], 7000))
    N2 = Strokes()
    for idx in picks:
        x, y = float(idx % n) + r.uniform(0, 1), float(idx // n) + r.uniform(0, 1)
        a = r.uniform(0, 2 * math.pi)
        N2.line(_walk(r, x, y, a, mm(r.uniform(12.0, 50.0)), mm(4.0), 0.35), mm(0.8), mm(0.55),
                r.uniform(0.3, 0.6), r.uniform(0.25, 0.5), r.uniform(0.2, 0.5), r.uniform(0.1, 0.4), 0.5)
    st = _merge(cords, N2.raster(n))
    # Cotton: small tufts (a few cm) gathered along the cords, none of them tile-sized.
    tufts = T.smoothstep(0.46, 0.74, T.spectral(n, 1.6, seed + 1, fmin=6.0))
    fluff = T.smoothstep(0.25, 0.9, T.spectral(n, 1.1, seed + 2, fmin=12.0))
    st["cotton"] = np.clip(tufts * (0.25 + 0.75 * T.smoothstep(0.08, 0.5, near)) * (0.55 + 0.45 * fluff), 0, 1)
    return st


@functools.lru_cache(maxsize=1)
def _web_maps(size: int, seed: int) -> tuple:
    """(priority, age, cotton, body, height, F); cached, every web texture is cut from one raster."""
    st = _web(size, seed)
    pri, F = _priority(st, size)
    print(f"[bloom] web: threads cover {F:.3f} of the tile (terrain.gdshader bloom_web_cover)")
    # G: age, old cream near the colony centres, fresh white at the growing tips.
    age = np.clip(st["age"] + 0.2 * (T.spectral(size, 1.8, seed + 3) - 0.5), 0, 1)
    age = np.where(st["cov"] > 0.02, age, T.blur(age, 3.0))
    body = np.clip(T.blur(st["body"], 0.6) * 1.15, 0, 1)
    h = st["h"] * 0.6 + st["cotton"] * 1.4 * T.spectral(size, 1.0, seed + 4)
    return pri, age, st["cotton"], body, h, F


@texture("bloom_web_mask", size=1024, seed=2501, kind="single", import_kind="mask")
def bloom_web_mask(size: int, seed: int, out) -> None:
    pri, age, cotton, body, _, _ = _web_maps(size, seed)
    _save_mask(out, pri, age, cotton, body)


@texture("bloom_web_normal", size=1024, seed=2501, kind="single", import_kind="normal")
def bloom_web_normal(size: int, seed: int, out) -> None:
    h = _web_maps(size, seed)[4]
    T.save_rgb(str(out) + ".png", T.height_to_normal(T.blur(h, 0.6), 0.9))


@texture("bloom_web_cov", size=1024, seed=2501, kind="single", import_kind="mask")
def bloom_web_cov(size: int, seed: int, out) -> None:
    maps = _web_maps(size, seed)
    _save_mask(out, *_coverage(maps[0], maps[5]))


# --------------------------------------------------------------------------------------------------
# Threads on bark
# --------------------------------------------------------------------------------------------------

UP = -math.pi / 2  # up the trunk = toward row 0


def _bark(n: int, seed: int) -> dict[str, np.ndarray]:
    """Cords climbing the trunk (periodic in V, so they run on across tiles), branches that climb
    away from them and open into feathery fans, a fine net following the bark, and crusts."""
    r = T.rng(seed)
    px_m = BARK_TILE_M / n
    S = Strokes()
    mm = lambda v: v / 1000.0 / px_m  # noqa: E731

    def feather(x, y, ang, length, pri):
        """A fan: a spine with fine threads leaving it at small angles, widest toward its tip."""
        spine = _walk(r, x, y, ang, length, mm(6.0), 0.08, pull=(UP, 0.05))
        S.line(spine, mm(1.8), mm(0.9), pri, pri - 0.08, 0.3, 0.1, 0.8)
        for _ in range(int(length / mm(2.5))):
            s0 = r.uniform(0.05, 1.0)
            bx, by, ba = _along(spine, s0)
            side = 1.0 if r.random() < 0.5 else -1.0
            S.line(_walk(r, bx, by, ba + side * r.uniform(0.15, 0.55), mm(r.uniform(12.0, 45.0)) * (0.4 + s0), mm(4.0), 0.15),
                   mm(0.9), mm(0.45), pri - 0.12, pri - 0.2, 0.15, 0.0, 0.6)

    def branch(x, y, ang, length, rad, pri, age, depth):
        pts = _walk(r, x, y, ang, length, mm(8.0), 0.1, pull=(UP, 0.07))
        S.line(pts, rad, rad * 0.5, pri, pri - 0.1, age, age - 0.3, 1.0)
        if depth < 2:
            s = r.uniform(0.25, 0.5)
            while s < 0.85:
                bx, by, ba = _along(pts, s)
                side = 1.0 if r.random() < 0.5 else -1.0
                branch(bx, by, ba + side * r.uniform(0.3, 0.7), length * (1.0 - s) * r.uniform(0.5, 0.8), rad * 0.65,
                       pri - 0.1, age - 0.1, depth + 1)
                s += r.uniform(0.25, 0.45)
        tx, ty = pts[-1]
        _, _, ta = _along(pts, 1.0)
        feather(tx, ty, ta, mm(r.uniform(50.0, 130.0)), pri - 0.18)

    # Main cords: u(v) a sum of random harmonics of the tile height (periodic, so seamless), wandering
    # like roots along the bark furrows, swelling and thinning.
    cords = int(r.integers(6, 9))
    for _ in range(cords):
        u0 = r.uniform(0, n)
        harm = [(k, r.uniform(0.4, 1.0) * mm(34.0) / k ** 1.1, r.uniform(0, 2 * math.pi)) for k in range(1, 8)]
        wph = r.uniform(0, 2 * math.pi, 2)
        k_pts = 160
        pts = []
        for i in range(k_pts + 1):
            th = 2 * math.pi * i / k_pts
            u = u0 + sum(a * math.sin(k * th + ph) for k, a, ph in harm)
            pts.append((u, n - n * i / k_pts))
        rad = mm(r.uniform(5.0, 8.5))
        pri = r.uniform(0.94, 1.0)
        for i in range(k_pts):
            th = 2 * math.pi * (i + 0.5) / k_pts
            w = 0.75 + 0.25 * math.sin(2 * th + wph[0]) + 0.12 * math.sin(5 * th + wph[1])
            S.line(pts[i:i + 2], rad * w, rad * w, pri, pri, 0.9, 0.9, 1.0)
        for _ in range(int(r.integers(2, 5))):
            bx, by, _ = _along(pts, r.uniform(0.0, 1.0))
            side = 1.0 if r.random() < 0.5 else -1.0
            branch(bx, by, UP + side * r.uniform(0.35, 0.8), mm(r.uniform(120.0, 340.0)), rad * r.uniform(0.45, 0.65),
                   pri - 0.08, 0.7, 0)
    # Free fans opening up the trunk.
    for _ in range(int(r.integers(6, 10))):
        feather(r.uniform(0, n), r.uniform(0, n), UP + r.normal(0.0, 0.25), mm(r.uniform(90.0, 220.0)), r.uniform(0.6, 0.78))
    cords = S.raster(n)
    # The fine net clings around the cords and fans, mostly along the trunk: a cobweb film that
    # binds the bark's ridges.
    near = T.blur(cords["cov"], 8.0)
    near = near / max(float(near.max()), 1e-6)
    cdf = np.cumsum((near.ravel() + 0.02) ** 1.5)
    N2 = Strokes()
    for idx in np.searchsorted(cdf, r.uniform(0.0, cdf[-1], 2600)):
        x, y = float(idx % n) + r.uniform(0, 1), float(idx // n) + r.uniform(0, 1)
        a = UP + r.normal(0.0, 0.45) + (math.pi if r.random() < 0.3 else 0.0)
        N2.line(_walk(r, x, y, a, mm(r.uniform(20.0, 70.0)), mm(5.0), 0.3), mm(0.8), mm(0.5),
                r.uniform(0.25, 0.5), r.uniform(0.2, 0.45), r.uniform(0.2, 0.6), r.uniform(0.2, 0.6), 0.45)
    st = _merge(cords, N2.raster(n))
    # Crusts: lumpy, lobed shelves, wider than tall, zoned like a bracket's cap, with a thick lower
    # lip over a shadowed underside (the shader shows them low on the most colonised trunks).
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    lumps = T.spectral(n, 2.0, seed + 5)
    grain = T.spectral(n, 1.2, seed + 6)
    crust = np.zeros((n, n), np.float32)
    ch = np.zeros((n, n), np.float32)
    zone = np.zeros((n, n), np.float32)
    for _ in range(int(r.integers(3, 5))):
        cx, cy = r.uniform(0, n), r.uniform(0, n)
        w, hgt = mm(r.uniform(60.0, 140.0)), mm(r.uniform(30.0, 60.0))
        dx = (xx - cx + n / 2) % n - n / 2
        dy = (yy - cy + n / 2) % n - n / 2
        ang = np.arctan2(dy / hgt, dx / w)
        lobes = 0.12 * np.sin(ang * float(r.integers(3, 6)) + r.uniform(0, 6.28))
        e = np.sqrt((dx / w) ** 2 + (dy / hgt) ** 2) + (lumps - 0.5) * 0.45 + lobes
        m = T.smoothstep(1.0, 0.85, e)
        # The shelf rises toward its lower margin (it grows out from the bark), then drops off.
        lip = T.smoothstep(0.2, 0.9, dy / hgt + 0.2 * (lumps - 0.5)) * m
        crust = np.maximum(crust, m)
        ch = np.maximum(ch, m * (0.5 + 0.5 * np.clip(1 - e, 0, 1)) + lip * 0.9)
        zone = np.maximum(zone, m * (0.5 + 0.5 * np.sin(e * 22.0 + grain * 3.0)))
    st["crust"] = crust
    st["crust_h"] = ch
    st["crust_zone"] = zone
    return st


@functools.lru_cache(maxsize=1)
def _bark_maps(size: int, seed: int) -> tuple:
    """(priority, age, crust, body, height, F); cached like the web's."""
    st = _bark(size, seed)
    pri, F = _priority(st, size)
    print(f"[bloom] bark: threads cover {F:.3f} of the tile")
    age = np.clip(st["age"] + 0.2 * (T.spectral(size, 1.8, seed + 3) - 0.5), 0, 1)
    age = np.where(st["cov"] > 0.02, age, T.blur(age, 3.0))
    age = np.clip(age * (1.0 - st["crust"]) + st["crust"] * (0.35 + 0.6 * st["crust_zone"]), 0, 1)
    body = np.clip(T.blur(st["body"], 0.6) * 1.15, 0, 1)
    h = st["h"] * 0.7 + st["crust_h"] * 9.0
    return pri, age, st["crust"], body, h, F


@texture("bloom_bark_mask", size=1024, seed=2511, kind="single", import_kind="mask")
def bloom_bark_mask(size: int, seed: int, out) -> None:
    pri, age, crust, body, _, _ = _bark_maps(size, seed)
    _save_mask(out, pri, age, crust, body)


@texture("bloom_bark_normal", size=1024, seed=2511, kind="single", import_kind="normal")
def bloom_bark_normal(size: int, seed: int, out) -> None:
    h = _bark_maps(size, seed)[4]
    T.save_rgb(str(out) + ".png", T.height_to_normal(T.blur(h, 0.7), 0.8))


# The felt sheath (A): the gap ranks within this much of the threads (bark.gdshader's sheath ramp).
BARK_SHEATH = 0.3


@texture("bloom_bark_cov", size=1024, seed=2511, kind="single", import_kind="mask")
def bloom_bark_cov(size: int, seed: int, out) -> None:
    maps = _bark_maps(size, seed)
    _save_mask(out, *_coverage(maps[0], maps[5], BARK_SHEATH))


# --------------------------------------------------------------------------------------------------
# Fruiting-body flesh and the mound's felt
# --------------------------------------------------------------------------------------------------

@texture("bloom_cap", size=512, seed=2521, kind="pbr")
def bloom_cap(size: int, seed: int, out) -> None:
    """Pale, waxy, faintly translucent flesh with radial fibrils (streaks along V) and a few darker
    water-soaked streaks; the cap's centre and the gills get their tone from vertex colour."""
    fib = T.spectral(size, 1.4, seed, anisotropy=(7.0, 1.0))
    fine = T.spectral(size, 1.0, seed + 1, anisotropy=(3.0, 1.0))
    soak = T.smoothstep(0.6, 0.85, T.spectral(size, 2.0, seed + 2, anisotropy=(4.0, 1.0)))
    t = np.clip(0.55 * fib + 0.25 * fine + 0.2 * T.spectral(size, 2.5, seed + 3), 0, 1)
    col = T.gradient(t, [(0.0, "#a9a597"), (0.45, "#cfccc0"), (0.8, "#dedbd1"), (1.0, "#e8e6dd")])
    col = T.mix(col, col * np.array([0.82, 0.84, 0.8], np.float32), soak * 0.6)
    h = 0.6 * fib + 0.25 * fine + 0.15 * soak
    rough = np.clip(0.42 + 0.18 * (1 - fine) - 0.1 * soak, 0, 1)
    T.save_pbr_set(out, col, h, rough, normal_strength=2.2, ao_strength=0.4)


@texture("bloom_mound", size=1024, seed=2531, kind="pbr")
def bloom_mound(size: int, seed: int, out) -> None:
    """A rooting mound's skin: a felted shroud of threads over soil and needles, cream where it is
    oldest, with cords standing out of it and the litter it swallowed showing through in places."""
    st = _web(size, seed)
    felt = np.clip(st["cotton"] * 1.6 + 0.85 * T.smoothstep(0.22, 0.62, T.spectral(size, 1.6, seed + 7)), 0, 1)
    cord = st["cov"]
    litter = T.gradient(T.spectral(size, 1.3, seed + 8), [(0.0, "#2a2119"), (0.45, "#3f3024"), (0.75, "#6a4c32"), (1.0, "#86603c")])
    old = T.smoothstep(0.4, 0.8, T.spectral(size, 2.2, seed + 9))
    fine = T.spectral(size, 1.0, seed + 10)
    fresh = T.gradient(fine, [(0.0, "#cfcdc3"), (1.0, "#ebeae3")])
    aged = T.gradient(fine, [(0.0, "#b1a888"), (1.0, "#cdc4a4")])
    web_col = T.mix(fresh, aged, old * 0.8)
    cover = np.clip(felt * 0.9 + cord, 0, 1)
    col = T.mix(litter, web_col, cover)
    # The felt is soft: shallow relief, cords raised over it.
    h = 0.35 * T.spectral(size, 1.6, seed + 11) + 0.3 * felt + 0.7 * st["h"] / max(float(st["h"].max()), 1e-6)
    rough = np.clip(0.78 - 0.18 * cover + 0.08 * old, 0, 1)
    T.save_pbr_set(out, col, h, rough, normal_strength=2.5, ao_strength=0.6)
