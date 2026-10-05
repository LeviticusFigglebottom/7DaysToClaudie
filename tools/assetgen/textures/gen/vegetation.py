"""Vegetation textures: tree barks, cut end grain, foliage atlases and the shelf-fungus texture.

  bark_grey_fir, bark_larch, bark_birch, bark_dead      tiling bark PBR sets (u around the trunk)
  wood_log_end[_birch|_dead|_rotten]                     end-grain disc (rim = bark), mapped by angle
  foliage_fir, foliage_larch, foliage_birch, fern,       RGBA cut-out atlases + normal + ORM
  grass, plants
  mushroom                                               red-belted conk: cap top (v 0.5..1), pores (v 0..0.5)

Foliage atlases are *painted*: a small anti-aliased vector painter (tapered capsules, leaf blades,
discs) composites thousands of needles/leaves/petals back to front, keeping a premultiplied
colour, coverage and a height layer. From those we derive

  * albedo RGBA (straight colour bled into transparent texels so mip-maps never show dark
    fringes; alpha slightly boosted so cut-out coverage survives minification),
  * a tangent-space normal map (needle/leaf profiles + overlap steps),
  * ORM (AO from overlap depth, roughness per material, metallic 0).

ATLAS RECTS use Blender's UV convention (u0, v0, u1, v1), v = 0 at the *bottom* of the image.
Every card region is painted with the card's base at the bottom centre and its tip towards the
top, so a card whose local +Y runs from base to tip maps straight onto the rect.
`LAYOUTS` is imported by blender_catalogs/vegetation.py and handed to the Blender generators as
params, so the models always agree with the atlases (and rebuild when a layout changes).
"""
from __future__ import annotations

import math

import numpy as np
from scipy import ndimage

from .. import texlib as T
from ..registry import texture

# --------------------------------------------------------------------------------------------
# Atlas layouts (shared with the Blender generators)
# --------------------------------------------------------------------------------------------

LAYOUTS: dict[str, dict[str, list[float]]] = {
    # Douglas-fir-like sprays (2048 px). spray_* are single sprays for LOD0, branch is a whole
    # branch (top view) for LOD1/LOD2 cards, dead = bare twigs with a few dead needles.
    "foliage_fir": {
        "spray_a": [0.0, 0.25, 0.5, 1.0],
        "spray_b": [0.5, 0.5, 0.75, 1.0],
        "spray_c": [0.75, 0.5, 1.0, 1.0],
        "branch": [0.5, 0.0, 1.0, 0.5],
        "dead": [0.0, 0.0, 0.5, 0.25],
    },
    # Western-larch-like twigs with needle tufts on spur shoots (light yellow-green).
    "foliage_larch": {
        "twig_a": [0.0, 0.25, 0.5, 1.0],
        "twig_b": [0.5, 0.5, 0.75, 1.0],
        "twig_c": [0.75, 0.5, 1.0, 1.0],
        "branch": [0.5, 0.0, 1.0, 0.5],
        "tuft": [0.0, 0.0, 0.25, 0.25],
        "twig_d": [0.25, 0.0, 0.5, 0.25],
    },
    # Paper birch leaf clusters on twigs (light yellow-green; autumn tint turns them yellow).
    "foliage_birch": {
        "cluster_a": [0.0, 0.5, 0.5, 1.0],
        "cluster_b": [0.5, 0.5, 1.0, 1.0],
        "cluster_c": [0.0, 0.0, 0.5, 0.5],
        "branch": [0.5, 0.0, 1.0, 0.5],
    },
    # Sword fern fronds (three variants) + a young curled frond.
    "fern": {
        "frond_a": [0.0, 0.0, 0.3125, 1.0],
        "frond_b": [0.3125, 0.0, 0.625, 1.0],
        "frond_c": [0.625, 0.0, 0.9375, 1.0],
        "young": [0.9375, 0.5, 1.0, 1.0],
        "stipe": [0.9375, 0.0, 1.0, 0.5],
    },
    # Grass clumps (blade cards).
    "grass": {
        "dense": [0.0, 0.5, 1.0, 1.0],
        "tall": [0.0, 0.0, 0.5, 0.5],
        "dry": [0.5, 0.0, 1.0, 0.5],
    },
    # Small plants (2048 px): fireweed stalks, yarrow, huckleberry twigs, woody stem strip.
    "plants": {
        "fireweed_a": [0.0, 0.5, 0.125, 1.0],
        "fireweed_b": [0.125, 0.5, 0.25, 1.0],
        "fireweed_c": [0.25, 0.5, 0.375, 1.0],
        "fireweed_leaf": [0.375, 0.75, 0.5, 1.0],
        "yarrow_a": [0.5, 0.75, 0.625, 1.0],
        "yarrow_b": [0.625, 0.75, 0.75, 1.0],
        "yarrow_top": [0.75, 0.875, 0.875, 1.0],
        "yarrow_top_b": [0.875, 0.875, 1.0, 1.0],
        "yarrow_leaves": [0.75, 0.75, 1.0, 0.875],
        "huckle_a": [0.0, 0.0, 0.25, 0.25],
        "huckle_b": [0.25, 0.0, 0.5, 0.25],
        "huckle_c": [0.0, 0.25, 0.25, 0.5],
        "huckle_d": [0.25, 0.25, 0.5, 0.5],
        "stem": [0.375, 0.5, 0.40625, 0.75],
        "stem_green": [0.40625, 0.5, 0.4375, 0.75],
    },
}


def rect_px(rect: list[float], size: int) -> tuple[int, int, int, int]:
    """Blender-UV rect -> pixel box (x0, y0, x1, y1) with y down."""
    u0, v0, u1, v1 = rect
    return int(round(u0 * size)), int(round((1.0 - v1) * size)), int(round(u1 * size)), int(round((1.0 - v0) * size))


# --------------------------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------------------------

def _c(h: str) -> np.ndarray:
    return T.hex_rgb(h)


def _jit(rng: np.random.Generator, col: np.ndarray, amount: float = 0.08, hue: float = 0.04) -> np.ndarray:
    """Per-element colour jitter: brightness +-amount, small independent channel shifts."""
    b = 1.0 + rng.uniform(-amount, amount)
    ch = 1.0 + rng.uniform(-hue, hue, 3)
    return np.clip(col * b * ch, 0, 1).astype(np.float32)


def aworley(size: int, points: int, seed: int, aspect: float = 1.0, jitter: float = 1.0):
    """Tileable Worley noise with an anisotropic metric: cells are `aspect` times taller (v) than
    wide. Returns F1, F2 (pixel units of the stretched space), cell id."""
    from scipy.spatial import cKDTree
    r = T.rng(seed)
    if jitter < 1.0:
        g = int(math.ceil(math.sqrt(points)))
        base = np.stack(np.meshgrid(np.arange(g), np.arange(g)), -1).reshape(-1, 2)[:points].astype(np.float64)
        pts = (base + 0.5 + (r.random((points, 2)) - 0.5) * jitter) / g
    else:
        pts = r.random((points, 2))
    sx, sy = float(size), float(size) / aspect
    tiled = np.concatenate([(pts + np.array([dx, dy])) * np.array([sx, sy]) for dx in (-1, 0, 1) for dy in (-1, 0, 1)])
    ids = np.tile(np.arange(points), 9)
    tree = cKDTree(tiled)
    yy, xx = np.mgrid[0:size, 0:size]
    q = np.stack([(xx.ravel() + 0.5), (yy.ravel() + 0.5) / aspect], -1)
    d, idx = tree.query(q, k=2)
    f1 = d[:, 0].reshape(size, size).astype(np.float32)
    f2 = d[:, 1].reshape(size, size).astype(np.float32)
    return f1, f2, ids[idx[:, 0]].reshape(size, size)


def worley_vec(size: int, points: int, seed: int, aspect: float = 1.0, warp=None):
    """Tileable anisotropic Worley: (F1, F2, cell id, dx, dy) with dx/dy the pixel offset from the
    nearest feature point (cells `aspect` times taller than wide). warp = (wx, wy) periodic pixel
    displacements of the lookup (ragged, irregular cell edges)."""
    from scipy.spatial import cKDTree
    r = T.rng(seed)
    pts = r.random((points, 2))
    sx, sy = float(size), float(size) / aspect
    tiled = np.concatenate([(pts + np.array([dx, dy])) * np.array([sx, sy]) for dx in (-1, 0, 1) for dy in (-1, 0, 1)])
    ids = np.tile(np.arange(points), 9)
    tree = cKDTree(tiled)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float64)
    if warp is not None:
        xx = (xx + warp[0]) % size
        yy = (yy + warp[1]) % size
    q = np.stack([(xx.ravel() + 0.5), (yy.ravel() + 0.5) / aspect], -1)
    d, idx = tree.query(q, k=2)
    near = tiled[idx[:, 0]]
    dx = (q[:, 0] - near[:, 0]).reshape(size, size).astype(np.float32)
    dy = ((q[:, 1] - near[:, 1]) * aspect).reshape(size, size).astype(np.float32)
    return (d[:, 0].reshape(size, size).astype(np.float32), d[:, 1].reshape(size, size).astype(np.float32),
            ids[idx[:, 0]].reshape(size, size), dx, dy)


def level_ridges(n: np.ndarray, half_width) -> np.ndarray:
    """0 on the median level set of `n` (furrows), rising to 1 at `half_width` pixels away
    (ridges). Distance is |n - m| / |grad n| so furrow width is uniform whatever the noise."""
    m = float(np.median(n))
    gx = (np.roll(n, -1, 1) - np.roll(n, 1, 1)) * 0.5
    gy = (np.roll(n, -1, 0) - np.roll(n, 1, 0)) * 0.5
    g = np.sqrt(gx * gx + gy * gy) + 1e-6
    d = np.abs(n - m) / g
    return np.clip(d / half_width, 0.0, 1.0).astype(np.float32)


def _cell_rand(cid: np.ndarray, salt: float) -> np.ndarray:
    return ((np.sin(cid * 12.9898 + salt * 78.233) * 43758.5453) % 1.0).astype(np.float32)


def _save_set(out, albedo, height, rough, *, normal_strength=4.0, ao=None, alpha=None, metal=0.0):
    base = out
    a_path = base.with_name(base.name + "_albedo.png")
    n_path = base.with_name(base.name + "_normal.png")
    o_path = base.with_name(base.name + "_orm.png")
    if alpha is not None:
        T.save_rgba(a_path, np.concatenate([np.clip(albedo, 0, 1), np.clip(alpha, 0, 1)[..., None]], -1))
    else:
        T.save_rgb(a_path, np.clip(albedo, 0, 1))
    T.save_rgb(n_path, T.height_to_normal(height, normal_strength))
    if ao is None:
        ao = T.cavity_ao(height)
    T.save_orm(o_path, np.clip(ao, 0, 1), np.clip(rough, 0, 1), metal)


# --------------------------------------------------------------------------------------------
# Vector painter (pixel space, y down). Colours are sRGB floats; compositing is premultiplied
# "over" in draw order, so draw back to front.
# --------------------------------------------------------------------------------------------

class Painter:
    def __init__(self, size: int):
        self.w = self.h = size
        self.rgb = np.zeros((size, size, 3), np.float32)
        self.a = np.zeros((size, size), np.float32)
        self.ht = np.zeros((size, size), np.float32)
        self.clip = (0, 0, size, size)

    def set_clip(self, box: tuple[int, int, int, int] | None) -> None:
        self.clip = box if box is not None else (0, 0, self.w, self.h)

    def _box(self, xmin, ymin, xmax, ymax):
        cx0, cy0, cx1, cy1 = self.clip
        x0 = max(cx0, int(math.floor(xmin)))
        y0 = max(cy0, int(math.floor(ymin)))
        x1 = min(cx1, int(math.ceil(xmax)) + 1)
        y1 = min(cy1, int(math.ceil(ymax)) + 1)
        if x1 <= x0 or y1 <= y0:
            return None
        return x0, y0, x1, y1

    def _comp(self, box, cov, col, hgt):
        x0, y0, x1, y1 = box
        sl = (slice(y0, y1), slice(x0, x1))
        c3 = cov[..., None]
        rgb = self.rgb[sl]
        rgb += (col - rgb) * c3
        a = self.a[sl]
        a += cov * (1.0 - a)
        h = self.ht[sl]
        h += (hgt - h) * cov

    def capsule(self, p0, p1, r0, r1, c0, c1=None, h0=0.0, hscale=1.0, opacity=1.0):
        """Tapered round-capped segment from p0 (radius r0, colour c0) to p1 (r1, c1)."""
        (x0, y0), (x1, y1) = p0, p1
        rm = max(r0, r1) + 1.0
        box = self._box(min(x0, x1) - rm, min(y0, y1) - rm, max(x0, x1) + rm, max(y0, y1) + rm)
        if box is None:
            return
        bx0, by0, bx1, by1 = box
        ax = np.arange(bx0, bx1, dtype=np.float32) + np.float32(0.5 - x0)
        ay = np.arange(by0, by1, dtype=np.float32)[:, None] + np.float32(0.5 - y0)
        dx, dy = x1 - x0, y1 - y0
        il2 = 1.0 / (dx * dx + dy * dy + 1e-9)
        t = ax * np.float32(dx * il2) + ay * np.float32(dy * il2)
        np.clip(t, 0.0, 1.0, out=t)
        px = ax - t * np.float32(dx)
        py = ay - t * np.float32(dy)
        d = np.sqrt(px * px + py * py)
        r = np.float32(r0) + np.float32(r1 - r0) * t
        cov = r - d + np.float32(0.5)
        np.clip(cov, 0.0, 1.0, out=cov)
        if min(r0, r1) < 0.5:
            cov *= np.minimum(r * 2.0, 1.0)
        if opacity != 1.0:
            cov *= np.float32(opacity)
        q = d / np.maximum(r, 0.35)
        prof = np.sqrt(np.maximum(1.0 - q * q, 0.0))
        hgt = prof * (np.maximum(r, 0.5) * np.float32(hscale)) + np.float32(h0)
        if c1 is None:
            col = c0
        else:
            col = c0 + (c1 - c0) * t[..., None]
        self._comp(box, cov, col, hgt)

    def polyline(self, pts, radii, cols, h0=0.0, hscale=1.0):
        for i in range(len(pts) - 1):
            self.capsule(pts[i], pts[i + 1], radii[i], radii[i + 1], cols[i], cols[i + 1], h0, hscale)

    def disc(self, c, r, col, h0=0.0, hscale=1.0, shade=0.0, opacity=1.0):
        """Filled disc; shade > 0 darkens towards the rim (berries, buds) with a small highlight."""
        x, y = c
        box = self._box(x - r - 1, y - r - 1, x + r + 1, y + r + 1)
        if box is None:
            return
        bx0, by0, bx1, by1 = box
        yy, xx = np.mgrid[by0:by1, bx0:bx1].astype(np.float32)
        dx = xx + 0.5 - x
        dy = yy + 0.5 - y
        d = np.sqrt(dx * dx + dy * dy)
        cov = np.clip(r - d + 0.5, 0.0, 1.0) * opacity
        if not cov.any():
            return
        q = np.clip(d / max(r, 0.5), 0, 1)
        prof = np.sqrt(np.clip(1.0 - q * q, 0.0, 1.0))
        colr = np.broadcast_to(col, dx.shape + (3,)).astype(np.float32)
        if shade > 0.0:
            spec = np.exp(-(((dx + 0.35 * r) ** 2 + (dy + 0.35 * r) ** 2) / max(0.5, (0.25 * r) ** 2)))
            colr = colr * (1.0 - shade * q[..., None] ** 2) + spec[..., None] * shade * 0.6
        self._comp(box, cov, colr, h0 + prof * r * hscale)

    def blade(self, base, tip, width, c_mid, c_edge, *, a=0.5, b=1.0, teeth=0, serr=0.0, h0=0.0, hscale=0.6,
              vein=None, nveins=0, vein_angle=0.6, curve=0.0, tip_col=None, holes=None, opacity=1.0):
        """Leaf / petal / pinna. Half-width profile w(s) ~ s^a (1-s)^b (normalised), s = 0 at the
        base, 1 at the tip. teeth/serr give a forward-pointing serrated margin; vein draws a
        midrib + nveins lateral veins in colour `vein`; curve bends the midrib sideways."""
        (bx, by), (tx, ty) = base, tip
        L = math.hypot(tx - bx, ty - by)
        if L < 1.0:
            return
        ux, uy = (tx - bx) / L, (ty - by) / L
        vx, vy = -uy, ux
        hw_max = width * 0.5
        pad = hw_max + abs(curve) * L + 2
        xs = [bx, tx]
        ys = [by, ty]
        box = self._box(min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)
        if box is None:
            return
        x0, y0, x1, y1 = box
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        xx += 0.5
        yy += 0.5
        s = ((xx - bx) * ux + (yy - by) * uy) / L
        tt = (xx - bx) * vx + (yy - by) * vy
        if curve != 0.0:
            tt = tt - curve * L * 4.0 * s * (1.0 - s)
        sc = np.clip(s, 0.0, 1.0)
        peak = (a / (a + b)) ** a * (b / (a + b)) ** b
        hw = hw_max * (sc ** a) * ((1.0 - sc) ** b) / peak
        if teeth > 0 and serr > 0.0:
            ph = (sc * teeth) % 1.0
            hw = hw * (1.0 - serr * (1.0 - ph) ** 2)
        inside = hw - np.abs(tt)
        cov = np.clip(inside + 0.5, 0.0, 1.0)
        cov *= np.clip((s * L) + 0.5, 0, 1) * np.clip(((1.0 - s) * L) + 0.5, 0, 1)
        if holes is not None:
            for (hs, ht_, hr) in holes:
                dh = np.sqrt(((s - hs) * L) ** 2 + (tt - ht_ * hw_max) ** 2)
                cov *= np.clip(dh - hr + 0.5, 0, 1)
        cov *= opacity
        if not cov.any():
            return
        q = np.clip(np.abs(tt) / np.maximum(hw, 0.5), 0.0, 1.0)
        col = c_mid + (c_edge - c_mid) * (q[..., None] ** 1.6)
        if tip_col is not None:
            col = col + (tip_col - col) * (np.clip((sc - 0.55) / 0.45, 0, 1) ** 1.5)[..., None]
        hgt = h0 + np.sqrt(np.clip(1.0 - q * q, 0.0, 1.0)) * hw_max * hscale
        if vein is not None:
            mid = np.clip(1.2 - np.abs(tt) / max(0.7, width * 0.025), 0, 1) * (sc < 0.97)
            col = col + (vein - col) * (mid[..., None] * 0.8)
            hgt = hgt - mid * hw_max * 0.035
            if nveins > 0:
                ph = (sc * nveins - np.abs(tt) / max(1.0, hw_max) * vein_angle * nveins / 3.0) % 1.0
                lat = np.clip(1.0 - np.abs(ph - 0.5) * 2.0 * (L / max(1, nveins)) / 1.3, 0, 1) * (q < 0.92)
                col = col + (vein - col) * (lat[..., None] * 0.35)
                hgt = hgt - lat * hw_max * 0.012
        self._comp(box, cov, col, hgt)

    # ---- finishing ------------------------------------------------------------------------

    def straight_rgb(self) -> np.ndarray:
        return self.rgb / np.maximum(self.a, 1e-4)[..., None]


def bleed(rgb: np.ndarray, alpha: np.ndarray, thresh: float = 0.35) -> np.ndarray:
    """Pushes opaque colours into transparent texels (pull-push pyramid) so bilinear filtering
    and mip-maps never pull dark fringes in from cut-out regions."""
    w = (alpha > thresh).astype(np.float32)
    levels = [(rgb * w[..., None], w)]
    while levels[-1][1].shape[0] > 1:
        c, ww = levels[-1]
        h2, w2 = c.shape[0] // 2, c.shape[1] // 2
        c2 = c[:h2 * 2, :w2 * 2].reshape(h2, 2, w2, 2, 3).sum((1, 3))
        ww2 = ww[:h2 * 2, :w2 * 2].reshape(h2, 2, w2, 2).sum((1, 3))
        levels.append((c2, ww2))
    c, ww = levels[-1]
    fill = c / np.maximum(ww, 1e-6)[..., None]
    if ww.max() <= 0:
        fill[:] = 0.3
    for c, ww in reversed(levels[:-1]):
        up = np.repeat(np.repeat(fill, 2, 0), 2, 1)[:c.shape[0], :c.shape[1]]
        up = ndimage.uniform_filter(up, size=(3, 3, 1), mode="nearest")
        own = c / np.maximum(ww, 1e-6)[..., None]
        k = np.clip(ww, 0, 1)[..., None]
        fill = own * k + up * (1 - k)
    return np.where(w[..., None] > 0.5, rgb, fill).astype(np.float32)


def finish_foliage(p: Painter, out, *, rough: float = 0.6, rough_var: float = 0.1, normal_strength: float = 3.0,
                   alpha_boost: float = 1.3, ao_depth: float = 0.55, seed: int = 0, tone=None) -> None:
    alpha = np.clip(p.a * alpha_boost, 0.0, 1.0)
    rgb = p.straight_rgb()
    if tone is not None:
        rgb = tone(rgb)
    rgb = bleed(np.clip(rgb, 0, 1), p.a)
    # Height: painter layers -> normalized; AO darkens texels that sit low in the stack and the
    # cavities between elements (computed before bleeding the height).
    ht = p.ht.copy()
    hmax = float(np.percentile(ht[p.a > 0.5], 99.5)) if (p.a > 0.5).any() else 1.0
    htn = np.clip(ht / max(hmax, 1e-3), 0, 1)
    local = htn - ndimage.gaussian_filter(htn, 3.0)
    ao = np.clip(0.55 + 0.45 * htn + local * 1.2, 0, 1)
    ao = 1.0 - ao_depth * (1.0 - ao)
    ao = np.where(p.a > 0.05, ao, 1.0)
    noise = T.spectral(p.w, 1.2, seed + 77)
    r = np.clip(rough + (noise - 0.5) * rough_var * 2.0, 0, 1)
    nrm_h = ndimage.gaussian_filter(htn, 0.6)
    a_path = out.with_name(out.name + "_albedo.png")
    n_path = out.with_name(out.name + "_normal.png")
    o_path = out.with_name(out.name + "_orm.png")
    T.save_rgba(a_path, np.concatenate([rgb, alpha[..., None]], -1))
    nrm = T.height_to_normal(nrm_h, normal_strength * 40.0 / 2048.0 * p.w)
    nrm[p.a < 0.02] = (0.5, 0.5, 1.0)
    T.save_rgb(n_path, nrm)
    T.save_orm(o_path, ao, r, 0.0)


# --------------------------------------------------------------------------------------------
# Conifer sprays
# --------------------------------------------------------------------------------------------

def _rot(dx, dy, ang):
    c, s = math.cos(ang), math.sin(ang)
    return dx * c - dy * s, dx * s + dy * c


def _twig_points(base, ang, length, n, bend, rng):
    """Polyline from base in direction ang (0 = up/-y), bending by `bend` radians overall."""
    pts = [base]
    x, y = base
    a = ang
    seg = length / (n - 1)
    wob = rng.uniform(-0.04, 0.04)
    for i in range(1, n):
        a += bend / (n - 1) + wob * rng.uniform(-1, 1)
        x += math.sin(a) * seg
        y -= math.cos(a) * seg
        pts.append((x, y))
    return pts


class NeedleStyle:
    def __init__(self, **kw):
        self.needle_len = 40.0       # px
        self.needle_r = 1.15         # px at the base
        self.spacing = 2.8           # px between needles along a twig (per side)
        self.angle = (55.0, 85.0)    # degrees from the twig, forward
        self.dark = _c("#21371b")
        self.mid = _c("#34512a")
        self.young = _c("#58762f")
        self.under = _c("#58705f")
        self.twig = _c("#5a4330")
        self.twig_young = _c("#6a6a3c")
        self.young_amount = 0.6
        self.under_frac = 0.08
        self.top_frac = 0.35
        self.density = 1.0           # probability a needle slot is filled
        self.dead = 0.0              # fraction of needles that are dead/brown
        self.dead_col = _c("#7a4a24")
        self.tufts = False           # larch: needles in rosettes on spur shoots
        self.__dict__.update(kw)


def _needles_on(p: Painter, rng, pts, st: NeedleStyle, scale: float, order: list, tip_young: float):
    """Queues needles along a twig polyline (drawn later in shuffled order)."""
    total = 0.0
    seglens = []
    for i in range(len(pts) - 1):
        l = math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
        seglens.append(l)
        total += l
    if total < 2:
        return
    sp = st.spacing * scale
    n = int(total / sp)
    side = 1
    acc = 0.0
    si = 0
    for k in range(n):
        dist = (k + rng.uniform(0.2, 0.8)) * sp
        while si < len(seglens) - 1 and acc + seglens[si] < dist:
            acc += seglens[si]
            si += 1
        f = (dist - acc) / max(seglens[si], 1e-6)
        x = pts[si][0] + (pts[si + 1][0] - pts[si][0]) * f
        y = pts[si][1] + (pts[si + 1][1] - pts[si][1]) * f
        tdx = (pts[si + 1][0] - pts[si][0]) / max(seglens[si], 1e-6)
        tdy = (pts[si + 1][1] - pts[si][1]) / max(seglens[si], 1e-6)
        s = dist / total
        if rng.random() > st.density:
            side = -side
            continue
        lenf = (0.55 + 0.45 * min(1.0, (1.0 - s) * 4.0)) * min(1.0, 0.45 + s * 6.0) * rng.uniform(0.85, 1.15)
        top = rng.random() < st.top_frac
        if top:
            ang = math.radians(rng.uniform(8, 35)) * (1 if rng.random() < 0.5 else -1)
            lenf *= rng.uniform(0.35, 0.7)
        else:
            ang = math.radians(rng.uniform(*st.angle)) * side
            side = -side
        ndx, ndy = _rot(tdx, tdy, ang)
        L = st.needle_len * scale * lenf
        # needle colour
        c = st.dark + (st.mid - st.dark) * rng.random()
        yt = max(0.0, (s - (1.0 - tip_young)) / max(tip_young, 1e-3)) * st.young_amount
        c = c + (st.young - c) * min(1.0, yt * rng.uniform(0.7, 1.2))
        if rng.random() < st.under_frac:
            c = st.under * rng.uniform(0.9, 1.1)
        if st.dead > 0 and rng.random() < st.dead:
            c = st.dead_col * rng.uniform(0.8, 1.2)
        c = _jit(rng, c, 0.1, 0.05)
        ctip = np.clip(c * rng.uniform(1.05, 1.25), 0, 1)
        r0 = st.needle_r * scale * rng.uniform(0.85, 1.1)
        bxo = x + ndx * r0 * 0.5
        byo = y + ndy * r0 * 0.5
        bend = rng.uniform(-0.15, 0.15)
        mx, my = bxo + ndx * L * 0.5, byo + ndy * L * 0.5
        ex, ey = _rot(ndx, ndy, bend)
        tx, ty = mx + ex * L * 0.5, my + ey * L * 0.5
        order.append((rng.random() + (0.6 if top else 0.0), "n", ((bxo, byo), (mx, my), (tx, ty)), r0, c, ctip))


def _draw_queue(p: Painter, order: list, hbase: float):
    order.sort(key=lambda o: o[0])
    for z, kind, pts, r0, c, ctip in order:
        h0 = hbase + z * 3.0
        if kind == "n":
            p.capsule(pts[0], pts[2], r0, r0 * 0.5, c, ctip, h0, 0.8)
        elif kind == "d":
            p.disc(pts, r0, c, h0, 0.8, shade=0.5)


def conifer_spray(p: Painter, rng, base, ang, length, width, st: NeedleStyle, scale=1.0, *, hbase=0.0,
                  twig_r=3.0, sub=True, bend=0.12, side_density=1.0, side_angle=(48, 68), side_step=(0.032, 0.048)):
    """A flattened conifer spray: main axis + alternate side branchlets (+ tertiary), needled."""
    order: list = []
    twigs = []  # (pts, r0, r1, young)
    n_main = 10
    main = _twig_points(base, ang, length, n_main, bend * rng.uniform(-1, 1), rng)
    twigs.append((main, twig_r, twig_r * 0.35, 1.0))
    # side branchlets
    s = rng.uniform(0.05, 0.09)
    side = 1 if rng.random() < 0.5 else -1
    while s < 0.93:
        if rng.random() < side_density:
            # envelope: widest ~30% from base, short at both ends
            env = math.sin(math.pi * min(1.0, (s + 0.08) * 1.25)) ** 0.8 * (1.0 - 0.55 * s)
            bl = width * 0.5 * env * rng.uniform(0.62, 1.12) / math.sin(math.radians(60))
            if bl > 6:
                idx = min(int(s * (n_main - 1)), n_main - 2)
                f = s * (n_main - 1) - idx
                bx = main[idx][0] + (main[idx + 1][0] - main[idx][0]) * f
                by = main[idx][1] + (main[idx + 1][1] - main[idx][1]) * f
                mdx = main[idx + 1][0] - main[idx][0]
                mdy = main[idx + 1][1] - main[idx][1]
                mang = math.atan2(mdx, -mdy)
                sa = mang + side * math.radians(rng.uniform(*side_angle) - 12 * s)
                bp = _twig_points((bx, by), sa, bl, 6, -side * rng.uniform(0.1, 0.35), rng)
                twigs.append((bp, twig_r * 0.55, twig_r * 0.25, 0.8))
                if sub and bl > 40:
                    ts = rng.uniform(0.18, 0.3)
                    tside = side
                    while ts < 0.8:
                        tl = bl * 0.5 * (1.0 - ts) * rng.uniform(0.7, 1.1)
                        if tl > 10:
                            j = min(int(ts * 5), 4)
                            g = ts * 5 - j
                            tx = bp[j][0] + (bp[j + 1][0] - bp[j][0]) * g
                            ty = bp[j][1] + (bp[j + 1][1] - bp[j][1]) * g
                            bang = math.atan2(bp[j + 1][0] - bp[j][0], -(bp[j + 1][1] - bp[j][1]))
                            tp = _twig_points((tx, ty), bang + tside * math.radians(rng.uniform(35, 55)), tl, 4,
                                              rng.uniform(-0.2, 0.2), rng)
                            twigs.append((tp, twig_r * 0.3, twig_r * 0.18, 0.6))
                        tside = -tside
                        ts += rng.uniform(0.12, 0.18)
        side = -side
        s += rng.uniform(*side_step)
    # twigs below the needles
    for pts, r0, r1, _ in twigs:
        n = len(pts)
        radii = [r0 + (r1 - r0) * i / (n - 1) for i in range(n)]
        cols = [st.twig + (st.twig_young - st.twig) * (i / (n - 1)) for i in range(n)]
        p.polyline(pts, [r * scale for r in radii], cols, hbase, 0.6)
    for pts, r0, r1, young in twigs:
        _needles_on(p, rng, pts, st, scale, order, 0.35 * young)
    _draw_queue(p, order, hbase + 1.0)


def larch_twig(p: Painter, rng, base, ang, length, st: NeedleStyle, scale=1.0, *, hbase=0.0, twig_r=2.6,
               tuft_r=26.0, tufts_per=0.03, side_branches=3):
    """Larch long shoot with knobby spur shoots, each carrying a rosette tuft of soft needles."""
    order: list = []
    main = _twig_points(base, ang, length, 8, rng.uniform(-0.25, 0.25), rng)
    twigs = [(main, twig_r, twig_r * 0.4)]
    for k in range(side_branches):
        s = rng.uniform(0.15, 0.75)
        idx = min(int(s * 7), 6)
        f = s * 7 - idx
        bx = main[idx][0] + (main[idx + 1][0] - main[idx][0]) * f
        by = main[idx][1] + (main[idx + 1][1] - main[idx][1]) * f
        mang = math.atan2(main[idx + 1][0] - main[idx][0], -(main[idx + 1][1] - main[idx][1]))
        side = 1 if k % 2 == 0 else -1
        bl = length * rng.uniform(0.3, 0.5) * (1.0 - 0.5 * s)
        twigs.append((_twig_points((bx, by), mang + side * math.radians(rng.uniform(35, 60)), bl, 5,
                                   rng.uniform(-0.3, 0.3), rng), twig_r * 0.6, twig_r * 0.3))
    for pts, r0, r1 in twigs:
        n = len(pts)
        p.polyline(pts, [(r0 + (r1 - r0) * i / (n - 1)) * scale for i in range(n)],
                   [st.twig + (st.twig_young - st.twig) * (i / (n - 1)) for i in range(n)], hbase, 0.6)
    for pts, r0, r1 in twigs:
        total = sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1))
        nt = max(1, int(total * tufts_per / scale))
        for j in range(nt):
            s = (j + rng.uniform(0.2, 0.8)) / nt
            d = s * total
            acc = 0.0
            for i in range(len(pts) - 1):
                l = math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
                if acc + l >= d or i == len(pts) - 2:
                    f = (d - acc) / max(l, 1e-6)
                    x = pts[i][0] + (pts[i + 1][0] - pts[i][0]) * f
                    y = pts[i][1] + (pts[i + 1][1] - pts[i][1]) * f
                    break
                acc += l
            # spur knob
            order.append((0.05, "d", (x, y), 2.2 * scale, _jit(rng, st.twig * 0.9), None))
            nn = int(rng.integers(14, 26))
            rr = tuft_r * scale * rng.uniform(0.75, 1.15) * (0.75 + 0.25 * (1 - s))
            base_ang = rng.uniform(0, 2 * math.pi)
            for q in range(nn):
                a = base_ang + q * 2.39996 + rng.uniform(-0.2, 0.2)
                L = rr * rng.uniform(0.55, 1.0)
                c = st.dark + (st.mid - st.dark) * rng.random()
                c = c + (st.young - c) * rng.uniform(0.0, st.young_amount)
                c = _jit(rng, c, 0.1, 0.04)
                dx, dy = math.sin(a), -math.cos(a)
                b = (x + dx * 1.5, y + dy * 1.5)
                m = (x + dx * L * 0.5, y + dy * L * 0.5)
                bend = rng.uniform(-0.25, 0.25)
                ex, ey = _rot(dx, dy, bend)
                t = (m[0] + ex * L * 0.5, m[1] + ey * L * 0.5)
                order.append((0.1 + rng.random(), "n", (b, m, t), st.needle_r * scale, c, np.clip(c * 1.15, 0, 1)))
    _draw_queue(p, order, hbase + 1.0)


# --------------------------------------------------------------------------------------------
# Broadleaf clusters
# --------------------------------------------------------------------------------------------

def leaf_twig(p: Painter, rng, base, ang, length, *, leaf_len, leaf_w, n_leaves, cols, twig_col, twig_r=2.5,
              a=0.45, b=1.1, teeth=14, serr=0.22, hbase=0.0, petiole=0.18, spread=(35, 75), droop=0.0,
              side_twigs=2, berries=None, holes_p=0.15, scale=1.0, vein_col=None):
    """A twig with alternate leaves (birch / huckleberry). cols = list of leaf colours to pick
    from. berries=(count, radius, colours) adds berries hanging off the twig."""
    main = _twig_points(base, ang, length, 7, rng.uniform(-0.3, 0.3) + droop, rng)
    twigs = [main]
    for k in range(side_twigs):
        s = rng.uniform(0.2, 0.7)
        i = min(int(s * 6), 5)
        f = s * 6 - i
        bx = main[i][0] + (main[i + 1][0] - main[i][0]) * f
        by = main[i][1] + (main[i + 1][1] - main[i][1]) * f
        mang = math.atan2(main[i + 1][0] - main[i][0], -(main[i + 1][1] - main[i][1]))
        side = 1 if (k % 2 == 0) else -1
        twigs.append(_twig_points((bx, by), mang + side * math.radians(rng.uniform(30, 55)),
                                  length * rng.uniform(0.35, 0.55) * (1 - 0.4 * s), 5, rng.uniform(-0.3, 0.3), rng))
    for ti, pts in enumerate(twigs):
        n = len(pts)
        r0 = twig_r * (1.0 if ti == 0 else 0.6)
        p.polyline(pts, [r0 * (1 - 0.6 * i / (n - 1)) * scale for i in range(n)], [twig_col] * n, hbase, 0.5)
    items = []
    for ti, pts in enumerate(twigs):
        nl = n_leaves if ti == 0 else max(2, n_leaves // 2)
        total = sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1))
        side = 1 if rng.random() < 0.5 else -1
        for j in range(nl):
            s = 0.12 + 0.88 * (j + rng.uniform(0.0, 0.6)) / nl
            if ti == 0 and j == nl - 1:
                s = 1.0
            d = s * total
            acc = 0.0
            x, y, tang = pts[-1][0], pts[-1][1], 0.0
            for i in range(len(pts) - 1):
                l = math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
                if acc + l >= d or i == len(pts) - 2:
                    f = min(1.0, (d - acc) / max(l, 1e-6))
                    x = pts[i][0] + (pts[i + 1][0] - pts[i][0]) * f
                    y = pts[i][1] + (pts[i + 1][1] - pts[i][1]) * f
                    tang = math.atan2(pts[i + 1][0] - pts[i][0], -(pts[i + 1][1] - pts[i][1]))
                    break
                acc += l
            la = tang + side * math.radians(rng.uniform(*spread)) * (0.3 if s >= 0.999 else 1.0)
            side = -side
            L = leaf_len * scale * rng.uniform(0.75, 1.15) * (0.75 + 0.25 * s)
            W = leaf_w * scale * rng.uniform(0.85, 1.1) * L / (leaf_len * scale)
            dx, dy = math.sin(la), -math.cos(la)
            pl = L * petiole
            items.append((rng.random(), (x, y), (x + dx * pl, y + dy * pl),
                          (x + dx * (pl + L), y + dy * (pl + L)), W, cols[int(rng.integers(0, len(cols)))]))
    if berries:
        cnt, br, bcols = berries
        for k in range(cnt):
            pts = twigs[int(rng.integers(0, len(twigs)))]
            i = int(rng.integers(1, len(pts)))
            x, y = pts[i]
            ox, oy = rng.uniform(-1, 1) * br * 2.5, rng.uniform(0.3, 1.5) * br * 1.8
            p.capsule((x, y), (x + ox, y + oy), 0.8 * scale, 0.6 * scale, twig_col, twig_col, hbase + 0.5, 0.4)
            items.append((0.5 + rng.random() * 0.6, "berry", (x + ox, y + oy), br * scale * rng.uniform(0.8, 1.15),
                          bcols[int(rng.integers(0, len(bcols)))], None))
    items.sort(key=lambda it: it[0])
    for it in items:
        if it[1] == "berry":
            p.disc(it[2], it[3], _jit(rng, it[4], 0.12, 0.05), hbase + 2.0 + it[0] * 4, 0.9, shade=0.55)
            continue
        z, pb, pbase, ptip, W, col = it
        c = _jit(rng, col, 0.1, 0.05)
        edge = np.clip(c * rng.uniform(0.75, 0.9), 0, 1)
        p.capsule(pb, pbase, 0.9 * scale, 0.7 * scale, twig_col, c * 0.8, hbase + z * 4, 0.4)
        holes = None
        if rng.random() < holes_p:
            holes = [(rng.uniform(0.3, 0.8), rng.uniform(-0.6, 0.6), rng.uniform(1.5, 4.0) * scale)]
        p.blade(pbase, ptip, W, c, edge, a=a, b=b, teeth=teeth, serr=serr, h0=hbase + 1.0 + z * 4, hscale=0.35,
                vein=(vein_col if vein_col is not None else np.clip(c * 1.25, 0, 1)), nveins=7,
                curve=rng.uniform(-0.06, 0.06), holes=holes)


# ============================================================================================
# Bark textures
# ============================================================================================

@texture("bark_grey_fir", size=1024, seed=3101)
def bark_grey_fir(size: int, seed: int, out) -> None:
    """Douglas-fir-like bark: thick corky ridges that split and rejoin, deep furrows whose walls
    show layered cinnamon-brown cork, cross-fissures that cut the ridges into long blocks, and
    weathered grey-brown scaly ridge crowns with sparse lichen."""
    wx = T.spectral(size, 2.2, seed + 1)
    wy = T.spectral(size, 2.2, seed + 2)
    wvar = T.spectral(size, 2.2, seed + 4)
    t = np.ones((size, size), np.float32)
    for k in range(2):
        n1 = T.spectral(size, 2.0, seed + 13 + k, anisotropy=(5.0, 1.0), fmin=0.6)
        n1 = T.warp(n1, wx, wy, size * 0.015)
        t = np.minimum(t, level_ridges(n1, size * (0.026 + 0.034 * wvar) * (1.0 - 0.3 * k)))
    t = T.blur(t, 1.0)
    # cross-fissures: wavy, mostly horizontal, only through some ridges and only part-way down
    hc = T.warp(T.spectral(size, 1.8, seed + 9, anisotropy=(1.0, 4.0), fmin=1.0), wx, wy, size * 0.012)
    cross = (1.0 - level_ridges(hc, size * 0.007)) * T.smoothstep(0.52, 0.66, T.spectral(size, 2.0, seed + 10))
    tt = t * (1.0 - 0.6 * cross * T.smoothstep(0.35, 0.8, t))
    ridge = T.smoothstep(0.0, 0.8, tt) ** 0.8
    # layered cork on the furrow walls: bands that follow the furrow (contours of t)
    lay_n = T.spectral(size, 1.6, seed + 20)
    bands = 0.5 + 0.5 * np.sin(tt * 2 * np.pi * 3.5 + lay_n * 4.0)
    wall = T.smoothstep(0.08, 0.25, tt) * (1.0 - T.smoothstep(0.5, 0.75, tt))
    # corky crowns: short horizontal checks and layered, crumbly cork (horizontal streak noise)
    hs = T.spectral(size, 1.2, seed + 21, anisotropy=(1.0, 3.5))
    chk_n = T.warp(T.spectral(size, 1.5, seed + 22, anisotropy=(1.0, 6.0), fmin=3.0), wx, wy, size * 0.006)
    checks = (1.0 - level_ridges(chk_n, size * 0.0035)) * T.smoothstep(0.55, 0.7, T.spectral(size, 1.2, seed + 23))
    flake = 1.0 - checks
    fl_h = hs
    coarse = T.spectral(size, 2.4, seed + 5)
    mid = T.spectral(size, 1.4, seed + 6, anisotropy=(2.0, 1.0))
    fine = T.spectral(size, 0.9, seed + 7)
    top = T.smoothstep(0.5, 0.8, tt)
    height = (0.72 * ridge + 0.03 * bands * wall + top * (0.05 * fl_h - 0.05 * checks + 0.05 * mid)
              + 0.025 * fine + 0.06 * coarse)
    height = T.normalize(height)
    # colours
    deep = T.gradient(np.clip(tt * 4.0, 0, 1), [(0.0, "#0d0806"), (1.0, "#22140e")])
    cork = T.mix(np.ones_like(deep) * _c("#2b1911"), np.ones_like(deep) * _c("#5a3322"), bands)
    cork = cork * (0.85 + 0.3 * lay_n)[..., None]
    crown = T.gradient(np.clip(0.45 * coarse + 0.35 * mid + 0.2 * fine, 0, 1),
                       [(0.0, "#352d28"), (0.35, "#4d433c"), (0.7, "#665a51"), (1.0, "#7c7066")])
    crown = crown * (0.84 + 0.28 * fl_h)[..., None] * (1.0 - 0.45 * checks)[..., None]
    soot = T.smoothstep(0.62, 0.86, T.spectral(size, 1.9, seed + 11))
    crown = crown * (1.0 - 0.3 * soot)[..., None]
    alb = T.mix(deep, cork, T.smoothstep(0.06, 0.22, tt))
    alb = T.mix(alb, crown, T.smoothstep(0.48, 0.7, tt))
    alb = T.mix(alb, alb * 0.5, cross * T.smoothstep(0.3, 0.7, t))
    lich = T.smoothstep(0.78, 0.88, T.spectral(size, 1.0, seed + 12)) * top
    alb = T.mix(alb, np.ones_like(alb) * _c("#8d9278"), lich * 0.55)
    rough = np.clip(0.9 + 0.06 * (1.0 - tt) - 0.06 * lich, 0, 1)
    ao = np.clip(T.cavity_ao(height, radius=12, strength=1.5) * (0.35 + 0.65 * tt ** 0.6), 0, 1)
    _save_set(out, alb, height, rough, normal_strength=11.0, ao=ao)


@texture("bark_larch", size=1024, seed=3201)
def bark_larch(size: int, seed: int, out) -> None:
    """Western-larch-like bark: big irregular plates split by deep dark furrows; every plate is a
    stack of thin exfoliating scales that overlap downwards like shingles (lifted, paler lower
    edges, shadowed tops), cinnamon to red-brown, weathered grey-brown where exposed longest."""
    wx = T.spectral(size, 2.2, seed + 1)
    wy = T.spectral(size, 2.2, seed + 2)
    wvar = T.spectral(size, 2.0, seed + 3)
    t = np.ones((size, size), np.float32)
    for k in range(2):
        n = T.spectral(size, 2.0, seed + 10 + k, anisotropy=(3.0, 1.0), fmin=0.8)
        n = T.warp(n, wx, wy, size * 0.015)
        t = np.minimum(t, level_ridges(n, size * (0.014 + 0.014 * wvar)))
    nh = T.spectral(size, 2.0, seed + 20, anisotropy=(1.0, 2.2), fmin=0.9)
    th = level_ridges(T.warp(nh, wx, wy, size * 0.01), size * 0.011)
    gate = T.smoothstep(0.42, 0.6, T.spectral(size, 2.0, seed + 21))
    t = np.minimum(t, 1.0 - (1.0 - th) * gate)
    t = T.blur(t, 1.2)
    plate = T.smoothstep(0.0, 0.85, t) ** 0.75
    # shingled scales
    sw = (T.spectral(size, 1.6, seed + 30) - 0.5) * size * 0.03, (T.spectral(size, 1.6, seed + 31) - 0.5) * size * 0.03
    f1, f2, cid, dx, dy = worley_vec(size, 900, seed + 4, aspect=1.6, warp=sw)
    cell = size / math.sqrt(900)
    ramp = np.clip(0.5 + dy / (cell * 1.3), 0.0, 1.0)            # rises towards each scale's lower edge
    edge = T.smoothstep(0.0, size * 0.004, f2 - f1)                 # 0 right at a scale boundary
    # break the outlines: only some boundaries are open, the rest are fused plate surface
    open_b = T.smoothstep(0.35, 0.6, T.spectral(size, 1.4, seed + 32))
    edge = 1.0 - (1.0 - edge) * open_b
    rnd = _cell_rand(cid, 2.0)
    scale_h = (0.55 * ramp + 0.45 * rnd) * edge
    lip = (1.0 - edge) * (dy > 0)                                   # lower boundary: lifted lip
    fine = T.spectral(size, 0.9, seed + 5)
    coarse = T.spectral(size, 2.2, seed + 6)
    topm = T.smoothstep(0.45, 0.85, t)
    height = 0.62 * plate + topm * (0.085 * scale_h + 0.02 * lip) + 0.07 * coarse + 0.025 * fine
    height = T.normalize(T.blur(height, 0.6))
    plate_col = T.gradient(np.clip(0.4 * rnd + 0.35 * coarse + 0.25 * fine, 0, 1),
                           [(0.0, "#56321f"), (0.4, "#71412a"), (0.75, "#855436"), (1.0, "#976a49")])
    # fresh, paler cinnamon under a lifted lip; shadow at the top of each scale
    plate_col = plate_col * (0.78 + 0.32 * ramp)[..., None]
    plate_col = T.mix(plate_col, np.ones_like(plate_col) * _c("#b37a50"), (lip * 0.5)[..., None][..., 0])
    plate_col = plate_col * (0.7 + 0.3 * edge)[..., None]
    weathered = T.gradient(np.clip(0.6 * coarse + 0.4 * fine, 0, 1), [(0.0, "#4a3f38"), (1.0, "#6f625a")])
    wmask = T.smoothstep(0.45, 0.8, T.spectral(size, 1.7, seed + 7)) * topm
    plate_col = T.mix(plate_col, weathered, wmask * 0.7)
    furrow = T.gradient(np.clip(t * 1.8, 0, 1), [(0.0, "#100805"), (0.6, "#2e180f"), (1.0, "#4d2c1d")])
    alb = T.mix(furrow, plate_col, T.smoothstep(0.42, 0.75, t))
    rough = np.clip(0.86 + 0.08 * (1.0 - t) - 0.04 * lip, 0, 1)
    ao = np.clip(T.cavity_ao(height, radius=9, strength=1.4) * (0.4 + 0.6 * t ** 0.6), 0, 1)
    _save_set(out, alb, height, rough, normal_strength=10.0, ao=ao)


@texture("bark_birch", size=1024, seed=3301)
def bark_birch(size: int, seed: int, out) -> None:
    """Paper birch: chalky white papery bark with faint horizontal layering and pinkish/grey
    smudges, lenticels of varied length, ragged horizontal peeling strips showing salmon-tan inner
    bark under a lifted curl, and black chevron branch scars ('eyes')."""
    r = T.rng(seed)
    base_n = T.spectral(size, 2.0, seed + 1)
    fine = T.spectral(size, 1.0, seed + 2, anisotropy=(1.0, 5.0))
    band = T.spectral(size, 1.6, seed + 3, anisotropy=(1.0, 9.0))
    alb = T.gradient(T.normalize(0.7 * base_n + 0.3 * fine), [(0.0, "#cdc6b9"), (0.5, "#e0dbd1"), (1.0, "#eeebe4")])
    alb = alb * (0.95 + 0.07 * band)[..., None]
    height = 0.25 * base_n + 0.1 * band + 0.05 * fine
    rough = np.full((size, size), 0.62, np.float32)
    smudge = T.smoothstep(0.62, 0.86, T.spectral(size, 1.8, seed + 4))
    alb = T.mix(alb, np.ones_like(alb) * _c("#9d988f"), smudge * 0.25)
    pink = T.smoothstep(0.6, 0.82, T.spectral(size, 2.0, seed + 5))
    alb = alb * (1.0 - pink[..., None] * np.array([0.0, 0.05, 0.08], np.float32))
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    # peeling strips: long thin horizontal bands with ragged ends; curl along the upper edge
    for k in range(7):
        cx, cy = r.uniform(0, size), r.uniform(0, size)
        hw, hh = r.uniform(size * 0.08, size * 0.25), r.uniform(size * 0.006, size * 0.014)
        dx = ((xx - cx + size / 2) % size - size / 2) / hw
        dy = ((yy - cy + size / 2) % size - size / 2) / hh
        rag = T.value_noise(size, 64, seed + 40 + k) - 0.5
        env = np.clip((1.0 - np.abs(dx)) * 4.0, 0, 1)
        prof = np.clip(1.0 - np.abs(dx) ** 3 + rag * 0.8, 0, 1) * env
        m = np.clip((prof - np.abs(dy) + 0.2) * 3.0, 0, 1) * env
        inner = T.gradient(T.spectral(size, 1.4, seed + 60 + k), [(0.0, "#b58a6c"), (1.0, "#cfa688")])
        alb = T.mix(alb, inner, m * 0.85)
        height = height - m * 0.15
        rough = np.where(m > 0.5, 0.72, rough)
        lip = np.clip(1.0 - np.abs(dy + prof + 0.1) * 2.2, 0, 1) * np.clip(prof * 6.0, 0, 1) * env
        alb = T.mix(alb, np.ones_like(alb) * _c("#f6f3ee"), lip * 0.75)
        height = height + lip * 0.35
        sh = np.clip(1.0 - np.abs(dy + prof * 0.55) * 3.0, 0, 1) * m
        alb = alb * (1.0 - 0.3 * sh)[..., None]
    # lenticels: horizontal dashes, many short, some long and thicker, clustered in bands
    bandy = r.uniform(0, size, 9)
    lent = np.zeros((size, size), np.float32)
    for i in range(520):
        if r.random() < 0.6:
            ly = (bandy[r.integers(0, 9)] + r.normal(0, size * 0.03)) % size
        else:
            ly = r.uniform(0, size)
        lx = r.uniform(0, size)
        long_one = r.random() < 0.12
        ll = r.uniform(size * 0.006, size * 0.03) * (2.5 if long_one else 1.0)
        lh = r.uniform(size * 0.0012, size * 0.003) * (1.6 if long_one else 1.0)
        x0, x1 = int(lx - ll) - 2, int(lx + ll) + 3
        y0, y1 = int(ly - lh * 3) - 2, int(ly + lh * 3) + 3
        gy, gx = np.meshgrid(np.arange(y0, y1) + 0.5, np.arange(x0, x1) + 0.5, indexing="ij")
        dxn = (gx - lx) / ll
        thick = lh * np.sqrt(np.clip(1.0 - dxn ** 2, 0, 1)) * (1.0 + 0.3 * np.sin(dxn * 7.0 + i))
        cov = np.clip(thick - np.abs(gy - ly) + 0.5, 0, 1) * r.uniform(0.6, 1.0)
        ys = np.arange(y0, y1) % size
        xs = np.arange(x0, x1) % size
        lent[np.ix_(ys, xs)] = np.maximum(lent[np.ix_(ys, xs)], cov)
    alb = T.mix(alb, np.ones_like(alb) * _c("#3a2f2a"), lent * 0.85)
    height = height + lent * 0.08
    # branch-scar chevrons: black, wide, arms sweeping down and out, ragged
    for k in range(3):
        cx, cy = r.uniform(0, size), r.uniform(0, size)
        w = r.uniform(size * 0.06, size * 0.11)
        dx = ((xx - cx + size / 2) % size - size / 2) / w
        dy = ((yy - cy + size / 2) % size - size / 2) / w
        arm = np.abs(dy - 0.3 * np.abs(dx) ** 1.2) - 0.17 * np.clip(1.0 - np.abs(dx), 0, 1) ** 0.7 - 0.03
        n = T.value_noise(size, 48, seed + 90 + k) - 0.5
        m = np.clip(-(arm + n * 0.08) * 18.0, 0, 1) * np.clip((1.0 - np.abs(dx)) * 3.0, 0, 1)
        knot = np.clip(1.0 - (dx * dx + ((dy + 0.08) * 1.5) ** 2) / 0.012, 0, 1)
        m = np.maximum(m, knot)
        alb = T.mix(alb, np.ones_like(alb) * _c("#1a1512"), m * 0.92)
        height = height - m * 0.2 + knot * 0.25
        rough = np.where(m > 0.5, 0.85, rough)
    height = T.normalize(height)
    ao = T.cavity_ao(height, radius=5, strength=1.0)
    _save_set(out, alb, height, rough, normal_strength=4.0, ao=ao)


@texture("bark_dead", size=1024, seed=3401)
def bark_dead(size: int, seed: int, out) -> None:
    """Silver-grey weathered wood of a dead conifer: crisp long grain lines, deep longitudinal
    checks, a few remnant patches of rough dark bark, faint lichen."""
    wx = T.spectral(size, 2.4, seed + 1)
    wy = T.spectral(size, 2.4, seed + 2)
    coarse = T.spectral(size, 2.2, seed + 3)
    # grain lines: level sets of strongly stretched noise at several scales
    grain = np.zeros((size, size), np.float32)
    for k, (an, fm, w) in enumerate(((14.0, 1.5, 0.004), (10.0, 2.5, 0.003), (18.0, 3.5, 0.002))):
        n = T.warp(T.spectral(size, 1.6, seed + 10 + k, anisotropy=(an, 1.0), fmin=fm), wx, wy, size * 0.01)
        grain = np.maximum(grain, 1.0 - level_ridges(n, size * w))
    fib = T.spectral(size, 1.0, seed + 4, anisotropy=(12.0, 1.0))
    # deep checks: a few long cracks (level set of a lower frequency stretched noise, gated)
    nc = T.warp(T.spectral(size, 2.0, seed + 5, anisotropy=(8.0, 1.0), fmin=0.6), wx, wy, size * 0.015)
    crack = 1.0 - level_ridges(nc, size * (0.004 + 0.006 * T.spectral(size, 2.0, seed + 6)))
    crack *= T.smoothstep(0.4, 0.6, T.spectral(size, 2.0, seed + 7, anisotropy=(4.0, 1.0)))
    height = 0.3 * coarse + 0.25 * fib - 0.12 * grain - 0.6 * crack
    alb = T.gradient(np.clip(0.35 * coarse + 0.65 * fib, 0, 1),
                     [(0.0, "#6b665f"), (0.4, "#878178"), (0.75, "#a19b91"), (1.0, "#b6b0a5")])
    alb = alb * (1.0 - 0.22 * grain)[..., None]
    stain = T.smoothstep(0.55, 0.8, T.spectral(size, 2.0, seed + 8))
    alb = T.mix(alb, alb * np.array([0.86, 0.78, 0.68], np.float32), stain * 0.45)
    bark = np.zeros((size, size), np.float32)
    alb = T.mix(alb, np.ones_like(alb) * _c("#1b1714"), crack * 0.9)
    lich = T.smoothstep(0.8, 0.9, T.spectral(size, 1.0, seed + 11)) * (1 - bark)
    alb = T.mix(alb, np.ones_like(alb) * _c("#9ea68b"), lich * 0.4)
    height = T.normalize(height)
    rough = np.clip(0.82 + 0.12 * crack + 0.05 * bark, 0, 1)
    ao = T.cavity_ao(height, radius=6, strength=1.2)
    _save_set(out, alb, height, rough, normal_strength=5.0, ao=ao)


END_PALETTES = {
    # heart (inner -> outer), sapwood, latewood darkening, bark, check colour, extra
    "conifer": dict(heart=["#87502f", "#99603a", "#a86c42"], sap="#cfa673", late=0.72, bark=["#2b1b12", "#4a3022", "#5e4434"],
                    check="#2a1a10", sap_r=0.66, grey=0.0, rot=0.0, checks=(4, 7)),
    "birch": dict(heart=["#c8a983", "#d2b48d", "#d9bd98"], sap="#e3cfae", late=0.86, bark=["#b9b2a6", "#d8d2c8", "#ece8e0"],
                  check="#5a4636", sap_r=0.5, grey=0.0, rot=0.0, checks=(2, 4)),
    "dead": dict(heart=["#7f7465", "#8d8274", "#998e80"], sap="#a39a8c", late=0.78, bark=["#3a332d", "#4f463e", "#5f564c"],
                 check="#1c1814", sap_r=0.7, grey=0.6, rot=0.0, checks=(7, 11)),
    "rotten": dict(heart=["#4b3424", "#5a4030", "#664a36"], sap="#6e5440", late=0.85, bark=["#211812", "#33251b", "#433127"],
                   check="#140e0a", sap_r=0.72, grey=0.0, rot=1.0, checks=(5, 8)),
}


def _end_grain(size: int, seed: int, out, palette: str) -> None:
    """Cut end grain filling the texture's inscribed circle (mapped by angle onto log/stump cut
    faces so the bark ring sits on the rim): eccentric wobbly growth rings (wide juvenile wood,
    thin dark latewood bands of varying strength), heartwood/sapwood, wedge-shaped drying checks
    from the rim plus a heart check, chainsaw roughness, bark ring with fissures."""
    P = END_PALETTES[palette]
    r = T.rng(seed)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    c = size / 2.0
    px, py = c + r.uniform(-0.06, 0.06) * size, c + r.uniform(-0.06, 0.06) * size
    dxp, dyp = xx + 0.5 - px, yy + 0.5 - py
    ang = np.arctan2(dyp, dxp)
    dxc, dyc = xx + 0.5 - c, yy + 0.5 - c
    rad_c = np.sqrt(dxc ** 2 + dyc ** 2) / (size * 0.5)
    rad_p = np.sqrt(dxp ** 2 + dyp ** 2) / (size * 0.5)
    w = np.clip(rad_c / 0.9, 0, 1) ** 2
    rr = rad_p * (1 - w) + rad_c * w
    # low-frequency angular wobble (rings are never circles) + fine wobble
    wob = (np.sin(ang * 3.0 + r.uniform(0, 6)) * 0.012 + np.sin(ang * 5.0 + r.uniform(0, 6)) * 0.006) * np.clip(rr * 3, 0, 1)
    rr_w = rr + wob + (T.spectral(size, 2.4, seed + 1) - 0.5) * 0.02
    nrings = int(r.integers(34, 48))
    widths = r.uniform(0.55, 1.45, nrings) * (1.0 + 0.9 * np.linspace(0.9, 0.0, nrings))
    edges = np.concatenate([[0.0], np.cumsum(widths)])
    edges = edges / edges[-1] * 0.92
    strength = r.uniform(0.45, 1.0, nrings)
    ridx = np.clip(np.searchsorted(edges, np.clip(rr_w, 0, 0.9199)) - 1, 0, nrings - 1)
    f = np.clip((rr_w - edges[ridx]) / np.maximum(edges[ridx + 1] - edges[ridx], 1e-6), 0, 1)
    latewood = T.smoothstep(0.6, 0.88, f) * (1 - T.smoothstep(0.95, 1.0, f) * 0.6) * strength[ridx]
    heart = T.gradient(np.clip(rr / P["sap_r"], 0, 1), [(0.0, P["heart"][0]), (0.6, P["heart"][1]), (1.0, P["heart"][2])])
    sap = T.smoothstep(P["sap_r"] - 0.04, P["sap_r"] + 0.03, rr + wob * 2)
    alb = T.mix(heart, np.ones_like(heart) * _c(P["sap"]), sap)
    alb = alb * (1.0 - (1.0 - P["late"]) * latewood)[..., None]
    fibre = T.spectral(size, 0.9, seed + 2)
    blot = T.spectral(size, 2.0, seed + 3)
    alb = alb * (0.9 + 0.12 * fibre + 0.08 * (blot - 0.5))[..., None]
    # chainsaw roughness: curved parallel tear-out bands
    saw = np.sin((xx * 0.85 + yy * 0.25 + 40 * np.sin(yy / size * 6.283)) / size * 2 * math.pi * 45 + fibre * 3) * 0.5 + 0.5
    alb = alb * (0.96 + 0.05 * saw)[..., None]
    height = 0.6 - latewood * 0.06 + fibre * 0.06 + saw * 0.03
    # wedge checks from the rim (drying) + one heart check
    for k in range(int(r.integers(*P["checks"]))):
        a0 = r.uniform(-math.pi, math.pi)
        da = np.angle(np.exp(1j * (ang - a0)))
        if k == 0:
            length = r.uniform(0.25, 0.5)
            t = np.clip(rad_p / length, 0, 1)
            half = (0.012 * (1.0 - t) + 0.002) / np.maximum(rad_p, 0.02)
            inside = rad_p < length
        else:
            length = r.uniform(0.12, 0.55)
            t = np.clip((0.9 - rad_c) / length, 0, 1)
            half = (0.02 * (1.0 - t) ** 1.5 + 0.0015) / np.maximum(rad_c, 0.05)
            inside = (rad_c > 0.9 - length) & (rad_c < 0.93)
        jag = (T.value_noise(size, 96, seed + 30 + k) - 0.5) * 0.004 / np.maximum(rad_c, 0.05)
        cr = np.clip(1.0 - np.abs(da + jag) / np.maximum(half, 1e-4), 0, 1) * inside
        cr = np.clip(cr * 1.5, 0, 1)
        alb = T.mix(alb, np.ones_like(alb) * _c(P["check"]), cr * 0.92)
        height = height - cr * 0.5
    # weathering (dead): grey wash, raised grain, many fine checks
    if P["grey"] > 0:
        g = alb.mean(-1, keepdims=True)
        alb = T.mix(alb, np.repeat(g, 3, -1) * np.array([1.0, 0.98, 0.95], np.float32), np.full_like(rad_c, P["grey"]))
        height = height + latewood * 0.08
    # rot (fallen logs): soft dark punky core with stringy fibres and pits
    if P["rot"] > 0:
        pit = T.smoothstep(0.62, 0.78, T.spectral(size, 1.6, seed + 4)) * (1.0 - T.smoothstep(0.5, 0.85, rad_c))
        alb = alb * (1.0 - 0.45 * pit)[..., None]
        height = height - pit * 0.4
        moss = T.smoothstep(0.8, 0.95, rad_c) * T.smoothstep(0.45, 0.7, T.spectral(size, 1.7, seed + 5))
        alb = T.mix(alb, np.ones_like(alb) * _c("#4e5a22"), moss * 0.7)
    # bark ring with fissures and a thin cambium line
    bark_in = 0.9 + (T.value_noise(size, 40, seed + 6) - 0.5) * 0.025
    bm = T.smoothstep(bark_in - 0.008, bark_in + 0.006, rad_c)
    bark_n = T.spectral(size, 1.3, seed + 7)
    fiss = np.clip(1.0 - np.abs(np.sin(ang * r.integers(18, 30) + bark_n * 6.0)) * 6.0, 0, 1) * T.smoothstep(0.93, 0.99, rad_c)
    bark_col = T.gradient(bark_n, [(0.0, P["bark"][0]), (0.5, P["bark"][1]), (1.0, P["bark"][2])])
    bark_col = bark_col * (1.0 - 0.5 * fiss)[..., None]
    cambium = T.smoothstep(bark_in - 0.018, bark_in - 0.006, rad_c) * (1 - bm)
    alb = T.mix(alb, alb * 1.12, cambium * 0.6)
    alb = T.mix(alb, bark_col, bm)
    height = height + bm * (0.18 + 0.2 * bark_n) - fiss * 0.2 * bm
    outside = T.smoothstep(0.985, 0.998, rad_c)
    alb = T.mix(alb, alb * 0.5, outside)
    height = T.normalize(np.clip(height, 0, 2))
    rough = np.clip(0.74 + 0.14 * bm + 0.08 * latewood + 0.1 * P["rot"], 0, 1)
    ao = T.cavity_ao(height, radius=4, strength=1.4)
    _save_set(out, np.clip(alb, 0, 1), height, rough, normal_strength=3.0, ao=ao)


@texture("wood_log_end", size=1024, seed=3501)
def wood_log_end(size: int, seed: int, out) -> None:
    """Fresh conifer end grain (fir/larch logs and stumps)."""
    _end_grain(size, seed, out, "conifer")


@texture("wood_log_end_birch", size=1024, seed=3511)
def wood_log_end_birch(size: int, seed: int, out) -> None:
    """Pale birch end grain with white papery bark rim."""
    _end_grain(size, seed, out, "birch")


@texture("wood_log_end_dead", size=1024, seed=3521)
def wood_log_end_dead(size: int, seed: int, out) -> None:
    """Weathered grey end grain of a long-dead snag, heavily checked."""
    _end_grain(size, seed, out, "dead")


@texture("wood_log_end_rotten", size=1024, seed=3531)
def wood_log_end_rotten(size: int, seed: int, out) -> None:
    """Dark punky rotten end grain for fallen logs (mossy rim)."""
    _end_grain(size, seed, out, "rotten")


# ============================================================================================
# Foliage atlases
# ============================================================================================

def _fir_style(scale: float = 1.0, **kw) -> NeedleStyle:
    st = NeedleStyle(needle_len=34.0, needle_r=1.2, spacing=2.6)
    st.__dict__.update(kw)
    return st


@texture("foliage_fir", size=2048, seed=4101, kind="pbr_alpha")
def foliage_fir(size: int, seed: int, out) -> None:
    rng = T.rng(seed)
    p = Painter(size)
    L = LAYOUTS["foliage_fir"]
    k = size / 2048.0

    def region(name):
        x0, y0, x1, y1 = rect_px(L[name], size)
        p.set_clip((x0, y0, x1, y1))
        return x0, y0, x1, y1

    # big sprays
    for name, sd, wfac in (("spray_a", 1, 0.92), ("spray_b", 2, 0.86), ("spray_c", 3, 0.9)):
        x0, y0, x1, y1 = region(name)
        w, h = x1 - x0, y1 - y0
        r2 = T.rng(seed + sd * 101)
        st = _fir_style(young_amount=0.55 if name != "spray_b" else 0.85)
        conifer_spray(p, r2, (x0 + w * 0.5, y1 - 6 * k), r2.uniform(-0.03, 0.03), h * 0.95, w * wfac, st,
                      scale=k, twig_r=3.4 * k, bend=0.15, side_density=0.88)
    # whole branch (for LOD cards): thick branch with sprays alternating along it
    x0, y0, x1, y1 = region("branch")
    w, h = x1 - x0, y1 - y0
    r2 = T.rng(seed + 501)
    st = _fir_style(needle_len=18.0, needle_r=1.1, spacing=2.2, young_amount=0.5)
    bpts = _twig_points((x0 + w * 0.5, y1 - 4), 0.0, h * 0.97, 9, r2.uniform(-0.1, 0.1), r2)
    sprays = []
    s = 0.12
    side = 1
    while s < 0.9:
        i = min(int(s * 8), 7)
        f = s * 8 - i
        bx = bpts[i][0] + (bpts[i + 1][0] - bpts[i][0]) * f
        by = bpts[i][1] + (bpts[i + 1][1] - bpts[i][1]) * f
        env = math.sin(math.pi * min(1.0, s * 1.1 + 0.1)) ** 0.7
        sl = h * 0.5 * env * r2.uniform(0.85, 1.1)
        sprays.append((r2.random(), (bx, by), side * math.radians(r2.uniform(40, 62)), sl))
        side = -side
        s += r2.uniform(0.05, 0.07)
    sprays.append((0.5, bpts[-2], r2.uniform(-0.1, 0.1), h * 0.3))
    p.polyline(bpts, [7 * k * (1 - 0.7 * i / 8) for i in range(9)], [_c("#4a3a2c")] * 9, 0.0, 0.5)
    for z, b, a, sl in sorted(sprays, key=lambda t: t[0]):
        conifer_spray(p, r2, b, a, sl, sl * 0.75, st, scale=k * 0.55, twig_r=2.4, hbase=z * 4, bend=0.2,
                      sub=True)
    # dead twigs: grey bare branchlets with a few rusty needles
    x0, y0, x1, y1 = region("dead")
    w, h = x1 - x0, y1 - y0
    r2 = T.rng(seed + 601)
    st = _fir_style(density=0.12, dead=1.0, dead_col=_c("#6e4426"), twig=_c("#6d655c"), twig_young=_c("#7f776c"))
    for j in range(3):
        conifer_spray(p, r2, (x0 + w * (0.3 + 0.2 * j), y1 - 4), (j - 1) * 0.5, h * 0.95, w * 0.35, st, scale=k,
                      twig_r=3.0 * k, bend=0.4)
    p.set_clip(None)

    def tone(rgb):
        # gentle darkening towards the spray base (inner foliage is older and shaded)
        return rgb

    finish_foliage(p, out, rough=0.62, rough_var=0.08, normal_strength=2.5, alpha_boost=1.35, seed=seed, tone=tone)


@texture("foliage_larch", size=2048, seed=4201, kind="pbr_alpha")
def foliage_larch(size: int, seed: int, out) -> None:
    """Western-larch twigs: knobby long shoots with rosette tufts of soft needles on spur shoots.
    Painted light yellow-green; the material's autumn tint turns it gold."""
    p = Painter(size)
    L = LAYOUTS["foliage_larch"]
    k = size / 2048.0
    st = NeedleStyle(needle_len=0.0, needle_r=1.35, dark=_c("#6d8a33"), mid=_c("#8ea444"), young=_c("#b3c45e"),
                     twig=_c("#6a4a32"), twig_young=_c("#8a6a44"), young_amount=0.55)

    def region(name):
        x0, y0, x1, y1 = rect_px(L[name], size)
        p.set_clip((x0, y0, x1, y1))
        return x0, y0, x1, y1

    for name, sd, nsides in (("twig_a", 1, 6), ("twig_b", 2, 4), ("twig_c", 3, 4), ("twig_d", 4, 2)):
        x0, y0, x1, y1 = region(name)
        w, h = x1 - x0, y1 - y0
        r2 = T.rng(seed + sd * 97)
        larch_twig(p, r2, (x0 + w * 0.5, y1 - 4), r2.uniform(-0.08, 0.08), h * 0.93, st, scale=k * (1.0 if h > 600 else 0.8),
                   twig_r=3.0, tuft_r=60.0 * (1.0 if h > 600 else 0.85), tufts_per=0.04, side_branches=nsides)
    # single tuft (rosette seen from above) for filler cards
    x0, y0, x1, y1 = region("tuft")
    w, h = x1 - x0, y1 - y0
    r2 = T.rng(seed + 601)
    cx, cy = x0 + w * 0.5, y0 + h * 0.5
    order = []
    for q in range(60):
        a = q * 2.39996 + r2.uniform(-0.15, 0.15)
        Ln = w * 0.46 * r2.uniform(0.6, 1.0)
        c = st.dark + (st.mid - st.dark) * r2.random()
        c = _jit(r2, c + (st.young - c) * r2.uniform(0, 0.5), 0.1, 0.04)
        dx, dy = math.sin(a), -math.cos(a)
        bend = r2.uniform(-0.2, 0.2)
        ex, ey = _rot(dx, dy, bend)
        b = (cx + dx * 3, cy + dy * 3)
        m = (cx + dx * Ln * 0.5, cy + dy * Ln * 0.5)
        t = (m[0] + ex * Ln * 0.5, m[1] + ey * Ln * 0.5)
        order.append((r2.random(), "n", (b, m, t), 2.4 * k, c, np.clip(c * 1.15, 0, 1)))
    _draw_queue(p, order, 1.0)
    p.disc((cx, cy), 6 * k, st.twig, 4.0, 0.8, shade=0.4)
    # whole branch for LOD cards: main branch, drooping twigs hanging off it
    x0, y0, x1, y1 = region("branch")
    w, h = x1 - x0, y1 - y0
    r2 = T.rng(seed + 701)
    bpts = _twig_points((x0 + w * 0.5, y1 - 4), 0.0, h * 0.96, 9, r2.uniform(-0.15, 0.15), r2)
    p.polyline(bpts, [6.0 * k * (1 - 0.75 * i / 8) for i in range(9)], [_c("#5a3e2a")] * 9, 0.0, 0.5)
    s = 0.08
    side = 1
    stb = NeedleStyle(needle_len=0.0, needle_r=1.6, dark=st.dark, mid=st.mid, young=st.young, twig=st.twig,
                      twig_young=st.twig_young, young_amount=0.5)
    while s < 0.95:
        i = min(int(s * 8), 7)
        f = s * 8 - i
        bx = bpts[i][0] + (bpts[i + 1][0] - bpts[i][0]) * f
        by = bpts[i][1] + (bpts[i + 1][1] - bpts[i][1]) * f
        env = math.sin(math.pi * min(1.0, s * 1.05 + 0.1)) ** 0.6
        sl = h * 0.4 * env * r2.uniform(0.8, 1.1)
        larch_twig(p, r2, (bx, by), side * math.radians(r2.uniform(35, 65)), sl, stb, scale=k * 0.5, twig_r=2.2,
                   tuft_r=52.0, tufts_per=0.06, side_branches=3)
        side = -side
        s += r2.uniform(0.045, 0.07)
    p.set_clip(None)
    finish_foliage(p, out, rough=0.7, rough_var=0.08, normal_strength=2.0, alpha_boost=1.4, seed=seed)


@texture("foliage_birch", size=2048, seed=4301, kind="pbr_alpha")
def foliage_birch(size: int, seed: int, out) -> None:
    """Paper-birch leaf clusters: ovate, doubly serrated leaves with fine veins on slender
    twigs. Light yellow-green so the autumn tint turns the crown yellow."""
    p = Painter(size)
    L = LAYOUTS["foliage_birch"]
    k = size / 2048.0
    cols = [_c("#7e9a35"), _c("#8ea83f"), _c("#9ab447"), _c("#a4b850"), _c("#86a03a")]
    twig_col = _c("#5a3d2c")

    def region(name):
        x0, y0, x1, y1 = rect_px(L[name], size)
        p.set_clip((x0, y0, x1, y1))
        return x0, y0, x1, y1

    for name, sd in (("cluster_a", 1), ("cluster_b", 2), ("cluster_c", 3)):
        x0, y0, x1, y1 = region(name)
        w, h = x1 - x0, y1 - y0
        r2 = T.rng(seed + sd * 131)
        # 3-4 twigs fanning from the base
        nt = 5
        for j in range(nt):
            ang = (j - (nt - 1) / 2) * 0.2 + r2.uniform(-0.06, 0.06)
            leaf_twig(p, r2, (x0 + w * 0.5 + r2.uniform(-20, 20), y1 - 6), ang, h * r2.uniform(0.58, 0.74),
                      leaf_len=125 * k, leaf_w=88 * k, n_leaves=10, cols=cols, twig_col=twig_col, twig_r=3.0 * k,
                      a=0.42, b=1.15, teeth=16, serr=0.14, side_twigs=2, scale=1.0, spread=(30, 70),
                      hbase=j * 2.0, holes_p=0.12, vein_col=None)
    x0, y0, x1, y1 = region("branch")
    w, h = x1 - x0, y1 - y0
    r2 = T.rng(seed + 501)
    bpts = _twig_points((x0 + w * 0.5, y1 - 4), 0.0, h * 0.95, 9, r2.uniform(-0.2, 0.2), r2)
    p.polyline(bpts, [6.5 * k * (1 - 0.75 * i / 8) for i in range(9)], [_c("#4c3a30")] * 9, 0.0, 0.5)
    s = 0.1
    side = 1
    while s < 0.97:
        i = min(int(s * 8), 7)
        f = s * 8 - i
        bx = bpts[i][0] + (bpts[i + 1][0] - bpts[i][0]) * f
        by = bpts[i][1] + (bpts[i + 1][1] - bpts[i][1]) * f
        sl = h * 0.36 * math.sin(math.pi * min(1.0, s * 1.1 + 0.08)) ** 0.5 * r2.uniform(0.8, 1.1)
        leaf_twig(p, r2, (bx, by), side * math.radians(r2.uniform(30, 60)), sl, leaf_len=66 * k, leaf_w=46 * k,
                  n_leaves=9, cols=cols, twig_col=twig_col, twig_r=2.0 * k, a=0.42, b=1.15, teeth=12, serr=0.15,
                  side_twigs=2, hbase=s * 6.0, holes_p=0.05)
        side = -side
        s += r2.uniform(0.035, 0.055)
    p.set_clip(None)
    finish_foliage(p, out, rough=0.55, rough_var=0.1, normal_strength=2.0, alpha_boost=1.25, seed=seed)


# --------------------------------------------------------------------------------------------
# Understory
# --------------------------------------------------------------------------------------------

def fern_frond(p: Painter, rng, base, length, width, *, cols, rachis_col, ang=0.0, n_pairs=34, young=0.0, hbase=0.0,
               stipe=0.16):
    """Sword-fern frond: scaly stipe, then alternate falcate pinnae with an upward 'hilt' lobe and
    a finely toothed margin, tapering to the tip."""
    pts = _twig_points(base, ang, length, 14, rng.uniform(-0.12, 0.12), rng)
    total = length
    p.polyline(pts, [3.2 - 2.4 * i / 13 for i in range(14)], [rachis_col] * 14, hbase, 0.5)
    # brown scales on the stipe
    for k in range(int(length * stipe / 6)):
        s = rng.uniform(0.0, stipe)
        i = min(int(s * 13), 12)
        f = s * 13 - i
        x = pts[i][0] + (pts[i + 1][0] - pts[i][0]) * f
        y = pts[i][1] + (pts[i + 1][1] - pts[i][1]) * f
        a = rng.uniform(0, 2 * math.pi)
        p.blade((x, y), (x + math.sin(a) * 7, y - math.cos(a) * 7), 3.5, _c("#5a3a20"), _c("#3a2414"), h0=hbase + 0.5)
    side = 1
    items = []
    for k in range(n_pairs * 2):
        s = stipe + (1.0 - stipe) * (k + rng.uniform(0.0, 0.4)) / (n_pairs * 2)
        if s > 0.985:
            break
        i = min(int(s * 13), 12)
        f = s * 13 - i
        x = pts[i][0] + (pts[i + 1][0] - pts[i][0]) * f
        y = pts[i][1] + (pts[i + 1][1] - pts[i][1]) * f
        tang = math.atan2(pts[i + 1][0] - pts[i][0], -(pts[i + 1][1] - pts[i][1]))
        u = (s - stipe) / (1.0 - stipe)
        env = (math.sin(math.pi * min(1.0, u * 0.92 + 0.08)) ** 0.55) * (1.0 - 0.25 * u)
        L = width * 0.5 * env * rng.uniform(0.9, 1.08) / math.sin(math.radians(68))
        if L < 4:
            side = -side
            continue
        a = tang + side * math.radians(rng.uniform(60, 72) - 20 * u)
        W = L * 0.21
        tip = (x + math.sin(a) * L, y - math.cos(a) * L)
        col = cols[int(rng.integers(0, len(cols)))]
        col = col + (np.clip(col * 1.35, 0, 1) - col) * young
        items.append((rng.random(), (x, y), tip, W, _jit(rng, col, 0.08, 0.04), side, a, L))
        side = -side
    for z, b, t, W, col, sd, a, L in sorted(items, key=lambda q: q[0]):
        edge = np.clip(col * 0.8, 0, 1)
        p.blade(b, t, W, col, edge, a=0.35, b=0.9, teeth=int(10 + L / 8), serr=0.12, h0=hbase + 1.0 + z * 3,
                hscale=0.3, vein=np.clip(col * 1.25, 0, 1), nveins=6, curve=-sd * 0.06)
        # the 'hilt': a small lobe at the base on the upper (tip-ward) side
        ha = a - sd * math.radians(35)
        hl = L * 0.24
        p.blade(b, (b[0] + math.sin(ha) * hl, b[1] - math.cos(ha) * hl), W * 0.8, col, edge, a=0.4, b=0.8,
                h0=hbase + 1.2 + z * 3, hscale=0.3)


@texture("fern", size=1024, seed=5101, kind="pbr_alpha")
def fern(size: int, seed: int, out) -> None:
    p = Painter(size)
    L = LAYOUTS["fern"]
    cols = [_c("#2b4a1f"), _c("#325524"), _c("#3a5e28"), _c("#2f4f22")]
    for name, sd, young in (("frond_a", 1, 0.0), ("frond_b", 2, 0.05), ("frond_c", 3, 0.0)):
        x0, y0, x1, y1 = rect_px(L[name], size)
        p.set_clip((x0, y0, x1, y1))
        r2 = T.rng(seed + sd * 71)
        fern_frond(p, r2, (x0 + (x1 - x0) * 0.5, y1 - 3), (y1 - y0) * 0.96, (x1 - x0) * 0.9, cols=cols,
                   rachis_col=_c("#4a5a2a"), n_pairs=int(r2.integers(30, 38)), young=young)
    x0, y0, x1, y1 = rect_px(L["young"], size)
    p.set_clip((x0, y0, x1, y1))
    r2 = T.rng(seed + 401)
    fern_frond(p, r2, (x0 + (x1 - x0) * 0.5, y1 - 2), (y1 - y0) * 0.95, (x1 - x0) * 0.95, cols=cols,
               rachis_col=_c("#5a6a30"), n_pairs=22, young=0.5, stipe=0.1)
    x0, y0, x1, y1 = rect_px(L["stipe"], size)
    p.set_clip((x0, y0, x1, y1))
    r2 = T.rng(seed + 501)
    yy = np.arange(y0, y1, dtype=np.float32)
    for k in range(3):
        cx = x0 + (x1 - x0) * (0.25 + 0.25 * k)
        p.polyline([(cx, y1), (cx + r2.uniform(-3, 3), (y0 + y1) / 2), (cx, y0)], [5, 4.5, 4], [_c("#4d4a26")] * 3, 0.0, 0.6)
    p.set_clip(None)
    finish_foliage(p, out, rough=0.45, rough_var=0.08, normal_strength=2.0, alpha_boost=1.25, seed=seed)


def grass_blade(p: Painter, rng, base, height, lean, col, tip_col, width, hbase, curl=0.0, segs=8):
    pts = []
    x, y = base
    a = lean
    seg = height / segs
    for i in range(segs + 1):
        pts.append((x, y))
        a += curl / segs + rng.uniform(-0.03, 0.03)
        x += math.sin(a) * seg
        y -= math.cos(a) * seg
    radii = [width * (1.0 - 0.92 * (i / segs) ** 1.3) for i in range(segs + 1)]
    cols = [col + (tip_col - col) * (i / segs) ** 1.5 for i in range(segs + 1)]
    p.polyline(pts, radii, cols, hbase, 0.7)
    return pts


@texture("grass", size=1024, seed=5201, kind="pbr_alpha")
def grass(size: int, seed: int, out) -> None:
    """Grass clump cards: dense green/yellowing blades, a tall clump with seed heads and a dry
    straw clump. Autumn tint pushes the greens towards straw."""
    p = Painter(size)
    L = LAYOUTS["grass"]
    greens = [_c("#4d6b26"), _c("#5d7a2e"), _c("#6b8634"), _c("#55722a"), _c("#7a8c3e")]
    dry = [_c("#9a8d55"), _c("#ab9c62"), _c("#8a7b48"), _c("#b8a872")]
    for name, sd, n, hfac, dryf, heads in (("dense", 1, 260, 0.92, 0.18, 0), ("tall", 2, 120, 0.95, 0.25, 9),
                                           ("dry", 3, 150, 0.85, 0.85, 4)):
        x0, y0, x1, y1 = rect_px(L[name], size)
        p.set_clip((x0, y0, x1, y1))
        r2 = T.rng(seed + sd * 53)
        w, h = x1 - x0, y1 - y0
        blades = []
        for i in range(n):
            bx = x0 + w * 0.5 + r2.normal(0, w * 0.13)
            lean = r2.normal(0, 0.28) + (bx - (x0 + w * 0.5)) / w * 0.9
            hh = h * hfac * r2.uniform(0.35, 1.0) ** 0.7
            is_dry = r2.random() < dryf
            col = (dry if is_dry else greens)[int(r2.integers(0, 5 if not is_dry else 4))]
            col = _jit(r2, col, 0.12, 0.05)
            tip = np.clip(col * np.array([1.25, 1.12, 0.85]), 0, 1) if not is_dry else np.clip(col * 1.1, 0, 1)
            blades.append((r2.random(), bx, lean, hh, col, tip, r2.uniform(2.2, 4.2) * (w / 1024 + 0.5),
                           r2.uniform(-0.5, 0.5)))
        for z, bx, lean, hh, col, tip, wd, curl in sorted(blades, key=lambda b: b[0]):
            grass_blade(p, r2, (bx, y1 - 2), hh, lean, col, tip, wd, z * 3, curl=curl)
        for k in range(heads):
            bx = x0 + w * 0.5 + r2.normal(0, w * 0.1)
            hh = h * r2.uniform(0.75, 0.97)
            pts = grass_blade(p, r2, (bx, y1 - 2), hh, r2.normal(0, 0.15), _c("#7a7a40"), _c("#9a8a52"), 1.6, 3.5,
                              curl=r2.uniform(-0.3, 0.3))
            tx, ty = pts[-1]
            for q in range(26):
                s = q / 26
                a = r2.uniform(-0.7, 0.7)
                sx = tx + r2.uniform(-4, 4)
                sy = ty + s * hh * 0.22
                ln = r2.uniform(10, 22) * (1 - 0.5 * s)
                p.blade((sx, sy), (sx + math.sin(a) * ln, sy - math.cos(a) * ln), 4.5,
                        _jit(r2, _c("#b0a066"), 0.1), _c("#8a7a48"), h0=4.0)
    p.set_clip(None)
    finish_foliage(p, out, rough=0.7, rough_var=0.08, normal_strength=1.5, alpha_boost=1.3, seed=seed)


def fireweed_stalk(p: Painter, rng, base, height, k):
    """Fireweed (Chamerion): reddish stem, alternate narrow leaves, magenta 4-petal flowers on the
    upper raceme (open below, buds above), a few slender reddish seed pods under the flowers."""
    n = 16
    pts = _twig_points(base, rng.uniform(-0.05, 0.05), height, n, rng.uniform(-0.12, 0.12), rng)
    p.polyline(pts, [4.0 * k * (1 - 0.6 * i / (n - 1)) for i in range(n)], [_c("#7a3c34")] * n, 0.0, 0.6)
    leafc = [_c("#3f6328"), _c("#4a6e2c"), _c("#3a5a26")]
    side = 1
    for j in range(22):
        s = 0.08 + 0.55 * j / 22
        i = min(int(s * (n - 1)), n - 2)
        x, y = pts[i]
        tang = math.atan2(pts[i + 1][0] - pts[i][0], -(pts[i + 1][1] - pts[i][1]))
        a = tang + side * math.radians(rng.uniform(35, 60))
        ln = height * rng.uniform(0.11, 0.15) * (1.0 - 0.35 * s)
        col = _jit(rng, leafc[int(rng.integers(0, 3))], 0.1, 0.05)
        if rng.random() < 0.25:
            col = _jit(rng, _c("#8a3a28"), 0.1, 0.05)   # leaves starting to redden
        p.blade((x, y), (x + math.sin(a) * ln, y - math.cos(a) * ln), ln * 0.17, col, np.clip(col * 0.8, 0, 1),
                a=0.6, b=1.1, h0=1.0 + j * 0.05, hscale=0.3, vein=np.clip(col * 1.3, 0, 1), nveins=0,
                curve=side * rng.uniform(0.0, 0.08))
        side = -side
    # seed pods
    for j in range(8):
        s = 0.6 + 0.08 * j / 8
        i = min(int(s * (n - 1)), n - 2)
        x, y = pts[i]
        a = rng.uniform(-0.6, 0.6)
        ln = height * rng.uniform(0.05, 0.08)
        p.capsule((x, y), (x + math.sin(a) * ln, y - math.cos(a) * ln), 1.6 * k, 1.0 * k, _c("#8a4a50"), _c("#a05a62"), 2.0, 0.5)
    # raceme of flowers
    pink = [_c("#c4378a"), _c("#d0479a"), _c("#b82f7c"), _c("#d85aa8")]
    for j in range(34):
        s = 0.66 + 0.33 * j / 34
        i = min(int(s * (n - 1)), n - 2)
        f = s * (n - 1) - i
        x = pts[i][0] + (pts[i + 1][0] - pts[i][0]) * f
        y = pts[i][1] + (pts[i + 1][1] - pts[i][1]) * f
        open_f = s < 0.9
        ox = rng.uniform(-1, 1) * height * 0.035 * (1.2 - s)
        cx, cy = x + ox, y + rng.uniform(-4, 4)
        p.capsule((x, y), (cx, cy), 0.9 * k, 0.8 * k, _c("#7a3c34"), _c("#9a4a50"), 2.5, 0.4)
        if open_f:
            pr = height * rng.uniform(0.016, 0.022)
            base_a = rng.uniform(0, math.pi / 2)
            col = _jit(rng, pink[int(rng.integers(0, 4))], 0.1, 0.05)
            for q in range(4):
                a = base_a + q * math.pi / 2
                p.blade((cx, cy), (cx + math.sin(a) * pr * 2.0, cy - math.cos(a) * pr * 2.0), pr * 1.6, col,
                        np.clip(col * 0.85, 0, 1), a=0.6, b=0.5, h0=3.0 + j * 0.05, hscale=0.3)
            p.disc((cx, cy), pr * 0.35, _c("#e8d8e8"), 3.6, 0.5)
        else:
            p.disc((cx, cy), height * 0.009, _jit(rng, _c("#8a2a5a"), 0.1), 3.0, 0.7, shade=0.4)


def yarrow_head(p: Painter, rng, c, rad, k, flat=True, hbase=3.0):
    """Flat-topped cluster of tiny white florets (side view squashed when flat=True)."""
    sq = 0.32 if flat else 1.0
    for j in range(int(140 * (rad / 40.0) ** 1.2)):
        a = rng.uniform(0, 2 * math.pi)
        rr = rad * math.sqrt(rng.random())
        x = c[0] + math.cos(a) * rr
        y = c[1] + math.sin(a) * rr * sq - (0 if not flat else (1.0 - (rr / rad) ** 2) * rad * 0.12)
        fr = rng.uniform(2.6, 3.8) * k
        col = _jit(rng, _c("#efece0"), 0.06, 0.02)
        for q in range(5):
            aa = q * 1.2566 + rng.uniform(0, 0.3)
            p.disc((x + math.cos(aa) * fr * 0.55, y + math.sin(aa) * fr * 0.55 * sq), fr * 0.55, col, hbase + rng.random(), 0.4)
        p.disc((x, y), fr * 0.35, _c("#d8c99a"), hbase + 1.2, 0.4)


def yarrow_leaf(p: Painter, rng, base, ang, length, col, hbase=0.0):
    """Finely dissected (ferny) yarrow leaf."""
    pts = _twig_points(base, ang, length, 8, rng.uniform(-0.3, 0.3), rng)
    p.polyline(pts, [1.6] * 8, [col] * 8, hbase, 0.5)
    for j in range(int(length / 4)):
        s = 0.05 + 0.95 * j / max(1, int(length / 4))
        i = min(int(s * 7), 6)
        x, y = pts[i]
        tang = math.atan2(pts[i + 1][0] - pts[i][0], -(pts[i + 1][1] - pts[i][1]))
        for sd in (1, -1):
            a = tang + sd * math.radians(rng.uniform(50, 80))
            ln = length * 0.16 * math.sin(math.pi * min(1.0, s * 1.1 + 0.05)) * rng.uniform(0.7, 1.1)
            p.capsule((x, y), (x + math.sin(a) * ln, y - math.cos(a) * ln), 1.4, 0.7, col, np.clip(col * 1.15, 0, 1),
                      hbase + 0.5, 0.5)


@texture("plants", size=2048, seed=5301, kind="pbr_alpha")
def plants(size: int, seed: int, out) -> None:
    """Small plants atlas: fireweed stalks + leaf cluster, yarrow (side cards, top-view flower
    heads, feathery leaves), huckleberry twigs with dark berries, woody and green stem strips."""
    p = Painter(size)
    L = LAYOUTS["plants"]
    k = size / 2048.0

    def region(name):
        x0, y0, x1, y1 = rect_px(L[name], size)
        p.set_clip((x0, y0, x1, y1))
        return x0, y0, x1, y1, x1 - x0, y1 - y0

    for name, sd in (("fireweed_a", 1), ("fireweed_b", 2), ("fireweed_c", 3)):
        x0, y0, x1, y1, w, h = region(name)
        fireweed_stalk(p, T.rng(seed + sd * 37), (x0 + w * 0.5, y1 - 2), h * 0.96, k)
    x0, y0, x1, y1, w, h = region("fireweed_leaf")
    r2 = T.rng(seed + 151)
    for j in range(9):
        a = (j - 4) * 0.28 + r2.uniform(-0.1, 0.1)
        ln = h * r2.uniform(0.5, 0.75)
        col = _jit(r2, _c("#40652a") if r2.random() < 0.7 else _c("#8a3a28"), 0.1)
        p.blade((x0 + w * 0.5, y1 - 2), (x0 + w * 0.5 + math.sin(a) * ln, y1 - 2 - math.cos(a) * ln), ln * 0.16, col,
                np.clip(col * 0.8, 0, 1), a=0.6, b=1.1, h0=j * 0.3, hscale=0.3, vein=np.clip(col * 1.3, 0, 1))
    leafc = _c("#55703a")
    for name, sd in (("yarrow_a", 1), ("yarrow_b", 2)):
        x0, y0, x1, y1, w, h = region(name)
        r2 = T.rng(seed + 200 + sd)
        top = (x0 + w * 0.5 + r2.uniform(-10, 10), y0 + h * 0.18)
        p.polyline([(x0 + w * 0.5, y1 - 2), ((x0 + w * 0.5 + top[0]) * 0.5, (y1 + top[1]) * 0.5), top], [3.0, 2.6, 2.2],
                   [_c("#5a6a3a")] * 3, 0.0, 0.5)
        for j in range(6):
            yy = y1 - h * (0.15 + 0.12 * j)
            yarrow_leaf(p, r2, (x0 + w * 0.5, yy), (1 if j % 2 else -1) * r2.uniform(0.6, 1.0), h * r2.uniform(0.16, 0.24),
                        _jit(r2, leafc, 0.1), 0.5)
        # umbel stalks + flat head
        for j in range(9):
            a = (j - 4) * 0.16
            ln = h * 0.08
            p.capsule(top, (top[0] + math.sin(a) * ln * 2.5, top[1] - math.cos(a) * ln), 1.2, 1.0, _c("#6a7a48"),
                      _c("#6a7a48"), 1.0, 0.4)
        yarrow_head(p, r2, (top[0], top[1] - h * 0.08), w * 0.42, k, flat=True)
    for name, sd in (("yarrow_top", 1), ("yarrow_top_b", 2)):
        x0, y0, x1, y1, w, h = region(name)
        r2 = T.rng(seed + 300 + sd)
        yarrow_head(p, r2, (x0 + w * 0.5, y0 + h * 0.5), w * 0.46, k, flat=False)
    x0, y0, x1, y1, w, h = region("yarrow_leaves")
    r2 = T.rng(seed + 351)
    for j in range(10):
        a = (j - 4.5) * 0.3 + r2.uniform(-0.1, 0.1)
        yarrow_leaf(p, r2, (x0 + w * 0.5, y1 - 2), a, h * r2.uniform(0.6, 0.95), _jit(r2, leafc, 0.12), j * 0.2)
    # huckleberry twigs
    hcols = [_c("#4f7a2c"), _c("#5d8434"), _c("#476e28"), _c("#6a8a3a")]
    berries = [_c("#2a1a3a"), _c("#3a2048"), _c("#1e1830"), _c("#4a2a52")]
    for name, sd, nb in (("huckle_a", 1, 9), ("huckle_b", 2, 6), ("huckle_c", 3, 12), ("huckle_d", 4, 0)):
        x0, y0, x1, y1, w, h = region(name)
        r2 = T.rng(seed + 400 + sd)
        for j in range(3):
            leaf_twig(p, r2, (x0 + w * 0.5 + r2.uniform(-15, 15), y1 - 3), (j - 1) * 0.35 + r2.uniform(-0.1, 0.1),
                      h * r2.uniform(0.7, 0.88), leaf_len=58 * k, leaf_w=30 * k, n_leaves=9, cols=hcols,
                      twig_col=_c("#6a5a3a"), twig_r=2.4 * k, a=0.5, b=0.8, teeth=10, serr=0.06, side_twigs=2,
                      spread=(35, 70), hbase=j * 2.0, holes_p=0.15, berries=(nb // 3, 9 * k, berries) if nb else None)
    for name, col0, col1 in (("stem", "#4e3f30", "#6b5a45"), ("stem_green", "#4a5a2e", "#5e7038")):
        x0, y0, x1, y1, w, h = region(name)
        n = T.spectral(256, 1.2, seed + 7 + len(name), anisotropy=(8.0, 1.0))
        strip = T.gradient(n, [(0.0, col0), (1.0, col1)])
        reps = (h // 256 + 1, w // 256 + 1, 1)
        p.rgb[y0:y1, x0:x1] = np.tile(strip, reps)[:h, :w]
        p.a[y0:y1, x0:x1] = 1.0
        p.ht[y0:y1, x0:x1] = 0.4 + 0.2 * np.tile(n, reps[:2])[:h, :w]
    p.set_clip(None)
    finish_foliage(p, out, rough=0.6, rough_var=0.1, normal_strength=2.0, alpha_boost=1.3, seed=seed)


@texture("mushroom", size=1024, seed=5401)
def mushroom(size: int, seed: int, out) -> None:
    """Red-belted conk (bracket fungus). Upper half (v 0.5..1): cap top, u wraps around the
    bracket, v runs from the attachment (0.5) to the margin (1.0): blackish-brown woody zones near
    the wood, a lacquered red-orange belt, ochre then a cream rounded margin. Lower half (v 0..0.5):
    cream pore surface."""
    r = T.rng(seed)
    H = size // 2
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    # top half in image rows 0..H (v 1..0.5): t = 0 at attachment (row H), 1 at margin (row 0)
    t = np.clip((H - yy) / H, 0, 1)
    wob = (T.spectral(size, 2.2, seed + 1) - 0.5) * 0.08
    tz = t + wob
    zones = 0.5 + 0.5 * np.sin(tz * 2 * math.pi * 9 + T.spectral(size, 1.8, seed + 2) * 2)
    top = T.gradient(np.clip(tz, 0, 1), [(0.0, "#1f1612"), (0.35, "#3a2418"), (0.55, "#7a2a16"), (0.68, "#a83a18"),
                                        (0.8, "#b8742e"), (0.9, "#d8b67a"), (1.0, "#ece2c4")])
    top = top * (0.85 + 0.2 * zones)[..., None]
    crust = T.spectral(size, 1.0, seed + 3)
    top = top * (0.9 + 0.15 * crust)[..., None]
    # lacquer sheen on the belt -> lower roughness there
    belt = T.smoothstep(0.45, 0.6, tz) * (1 - T.smoothstep(0.78, 0.9, tz))
    height_top = 0.5 + 0.1 * zones + 0.08 * crust
    # pore surface (bottom half rows H..size)
    pores_f1, pores_f2, _ = T.worley(size, 9000, seed + 4)
    pore = T.smoothstep(0.0, 3.0, pores_f1)
    under = T.gradient(T.spectral(size, 1.6, seed + 5), [(0.0, "#d6c7a0"), (1.0, "#e8dcbc")])
    under = under * (0.82 + 0.18 * pore)[..., None]
    height_under = 0.5 + 0.15 * pore
    is_top = (yy < H)
    alb = np.where(is_top[..., None], top, under)
    height = np.where(is_top, height_top, height_under)
    rough = np.where(is_top, 0.75 - 0.4 * belt, 0.9)
    _save_set(out, np.clip(alb, 0, 1), T.normalize(height), rough, normal_strength=2.5)
