"""Signed-distance modelling toolkit for characters (numpy; runs inside Blender's Python).

A body is described as an ordered list of *ops* (union / smooth-union / subtract / intersect) of
primitives, each carrying an integer material label. `Program.eval(points)` returns (distance,
label) arrays. Every primitive has an AABB so a grid evaluation only touches the voxels near it
(this keeps per-segment meshing fast). Distances are metres; negative = inside.

Everything is deterministic (no RNG here; noise is a seeded lattice hash).
"""
from __future__ import annotations

import math

import numpy as np

BIG = 1.0e3


# --------------------------------------------------------------------------------------------
# Small vector helpers
# --------------------------------------------------------------------------------------------

def v3(x) -> np.ndarray:
    return np.asarray(x, dtype=np.float64).reshape(3)


def normalize(v) -> np.ndarray:
    v = v3(v)
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-12 else v


def frame_from_axis(axis, up_hint=(0.0, -1.0, 0.0)) -> np.ndarray:
    """3x3 rotation whose columns are (u, v, w) with w = axis. Rows map world->local."""
    w = normalize(axis)
    up = v3(up_hint)
    if abs(float(np.dot(up, w))) > 0.95:
        up = v3((1.0, 0.0, 0.0)) if abs(w[0]) < 0.9 else v3((0.0, 0.0, 1.0))
    u = normalize(np.cross(up, w))
    v = np.cross(w, u)
    return np.stack([u, v, w], axis=1)


def rot_euler(rx: float = 0.0, ry: float = 0.0, rz: float = 0.0) -> np.ndarray:
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    mx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    my = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    mz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return mz @ my @ mx


# --------------------------------------------------------------------------------------------
# Primitive distance functions (P: (N,3) float arrays). All return (N,) float arrays.
# --------------------------------------------------------------------------------------------

def sd_sphere(P, c, r):
    return np.sqrt(((P - c) ** 2).sum(-1)) - r


def sd_ellipsoid(P, c, radii, R=None):
    q = P - c
    if R is not None:
        q = q @ R  # world -> local (R columns are local axes)
    r = np.asarray(radii, dtype=np.float64)
    k0 = np.sqrt(((q / r) ** 2).sum(-1))
    k1 = np.sqrt(((q / (r * r)) ** 2).sum(-1))
    return np.where(k1 > 1e-9, k0 * (k0 - 1.0) / np.maximum(k1, 1e-9), -float(r.min()))


def sd_capsule(P, a, b, r):
    pa = P - a
    ba = b - a
    h = np.clip((pa @ ba) / max(float(ba @ ba), 1e-12), 0.0, 1.0)
    return np.sqrt(((pa - h[:, None] * ba) ** 2).sum(-1)) - r


def sd_round_cone(P, a, b, r1, r2):
    """Exact SDF of a cone with spherical caps of radii r1 (at a) and r2 (at b) (iq)."""
    ba = b - a
    l2 = float(ba @ ba)
    rr = r1 - r2
    a2 = l2 - rr * rr
    il2 = 1.0 / max(l2, 1e-12)
    pa = P - a
    y = pa @ ba
    z = y - l2
    xv = pa * l2 - y[:, None] * ba
    x2 = (xv * xv).sum(-1)
    y2 = y * y * l2
    z2 = z * z * l2
    k = math.copysign(1.0, rr) * rr * rr * x2
    sx = np.sqrt(np.maximum(x2 * a2 * il2, 0.0))
    out = (np.sqrt(np.maximum(x2 + y2, 0.0)) * il2 - r1)
    res_b = np.sqrt(np.maximum(x2 + z2, 0.0)) * il2 - r2
    res_m = (sx + y * rr) * il2 - r1
    cond_b = np.sign(z) * a2 * z2 > k
    cond_a = np.sign(y) * a2 * y2 < k
    return np.where(cond_b, res_b, np.where(cond_a, out, res_m))


def sd_round_cone_ellip(P, a, b, r1, r2, squash: float = 1.0, up_hint=(0.0, -1.0, 0.0)):
    """Round cone with an elliptical cross-section: the axis perpendicular `v` (from up_hint) is
    scaled by `squash` (<1 flattens). Approximate but well-behaved near the surface."""
    if abs(squash - 1.0) < 1e-6:
        return sd_round_cone(P, a, b, r1, r2)
    R = frame_from_axis(b - a, up_hint)
    q = (P - a) @ R
    q[:, 1] /= squash
    d = sd_round_cone(q, np.zeros(3), np.array([0.0, 0.0, float(np.linalg.norm(b - a))]), r1, r2)
    return d * min(1.0, squash)


def sd_box(P, c, half, R=None, rounding: float = 0.0):
    q = P - c
    if R is not None:
        q = q @ R
    q = np.abs(q) - (np.asarray(half) - rounding)
    outside = np.sqrt((np.maximum(q, 0.0) ** 2).sum(-1))
    inside = np.minimum(np.maximum(q[:, 0], np.maximum(q[:, 1], q[:, 2])), 0.0)
    return outside + inside - rounding


def sd_torus(P, c, R_major, r_minor, R=None):
    q = P - c
    if R is not None:
        q = q @ R
    qx = np.sqrt(q[:, 0] ** 2 + q[:, 1] ** 2) - R_major
    return np.sqrt(qx * qx + q[:, 2] ** 2) - r_minor


def sd_plane(P, point, normal):
    """Half-space: negative on the side opposite the normal."""
    return (P - point) @ normalize(normal)


# --------------------------------------------------------------------------------------------
# Noise (seeded lattice gradient noise, vectorized). Values roughly in [-1, 1].
# --------------------------------------------------------------------------------------------

class Noise:
    def __init__(self, seed: int):
        r = np.random.default_rng(seed & 0xFFFFFFFF)
        self.perm = np.concatenate([r.permutation(256)] * 2).astype(np.int64)
        g = r.normal(size=(256, 3))
        self.grad = g / np.linalg.norm(g, axis=1, keepdims=True)

    def _hash(self, xi, yi, zi):
        p = self.perm
        return p[p[p[xi & 255] + (yi & 255)] + (zi & 255)]

    def noise(self, P, freq: float = 1.0):
        Q = P * freq
        i0 = np.floor(Q).astype(np.int64)
        f = Q - i0
        u = f * f * f * (f * (f * 6 - 15) + 10)
        out = 0.0
        res = np.zeros(len(P))
        for dx in (0, 1):
            wx = u[:, 0] if dx else 1 - u[:, 0]
            for dy in (0, 1):
                wy = u[:, 1] if dy else 1 - u[:, 1]
                for dz in (0, 1):
                    wz = u[:, 2] if dz else 1 - u[:, 2]
                    h = self._hash(i0[:, 0] + dx, i0[:, 1] + dy, i0[:, 2] + dz)
                    g = self.grad[h]
                    d = f - np.array([dx, dy, dz], dtype=np.float64)
                    res += wx * wy * wz * (g * d).sum(-1)
        del out
        return res * 1.6

    def fbm(self, P, freq: float = 1.0, octaves: int = 3, gain: float = 0.5):
        amp, tot = 1.0, 0.0
        res = np.zeros(len(P))
        f = freq
        for o in range(octaves):
            res += amp * self.noise(P + o * 17.31, f)
            tot += amp
            amp *= gain
            f *= 2.03
        return res / tot


# --------------------------------------------------------------------------------------------
# Smooth min / max with label selection
# --------------------------------------------------------------------------------------------

def smin(a, b, k):
    if k <= 0.0:
        return np.minimum(a, b)
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b + (a - b) * h - k * h * (1.0 - h)


def smax(a, b, k):
    return -smin(-a, -b, k)


# --------------------------------------------------------------------------------------------
# Program: ordered ops with AABB culling
# --------------------------------------------------------------------------------------------

class Op:
    __slots__ = ("kind", "fn", "lo", "hi", "k", "label", "keep_label")

    def __init__(self, kind, fn, lo, hi, k, label, keep_label):
        self.kind, self.fn, self.lo, self.hi, self.k = kind, fn, lo, hi, k
        self.label, self.keep_label = label, keep_label


class Program:
    """Ordered SDF ops. Kinds: 'union' (smooth with k), 'sub' (smooth subtract), 'inter',
    'paint' (relabel inside a region without changing distance), 'call' (arbitrary f(d, lab, P))."""

    def __init__(self, base_label: int = 0):
        self.ops: list[Op] = []
        self.base_label = base_label

    def _add(self, kind, fn, lo, hi, k=0.0, label=None, keep_label=False):
        lo = np.asarray(lo, dtype=np.float64) - k - 0.004
        hi = np.asarray(hi, dtype=np.float64) + k + 0.004
        self.ops.append(Op(kind, fn, lo, hi, k, label, keep_label))

    # --- convenience builders -------------------------------------------------------------
    def union(self, fn, lo, hi, k=0.0, label=0):
        self._add("union", fn, lo, hi, k, label)

    def sub(self, fn, lo, hi, k=0.0, label=None):
        """Subtract; label=None keeps the existing label on the carved surface."""
        self._add("sub", fn, lo, hi, k, label)

    def inter(self, fn, lo=None, hi=None, k=0.0):
        lo = (-BIG, -BIG, -BIG) if lo is None else lo
        hi = (BIG, BIG, BIG) if hi is None else hi
        self._add("inter", fn, lo, hi, k, None)

    def paint(self, fn, lo, hi, label):
        """Relabel points where fn(P) < 0 (surface stays the same)."""
        self._add("paint", fn, lo, hi, 0.0, label)

    def displace(self, fn, lo, hi):
        """d += fn(P) inside the box (small amplitude only)."""
        self._add("disp", fn, lo, hi, 0.0, None)

    # primitives -----------------------------------------------------------------------------
    def sphere(self, c, r, k=0.0, label=0, mode="union"):
        c = v3(c)
        self._prim(mode, lambda P: sd_sphere(P, c, r), c - r, c + r, k, label)

    def ellipsoid(self, c, radii, R=None, k=0.0, label=0, mode="union"):
        c = v3(c)
        m = float(max(radii))
        self._prim(mode, lambda P: sd_ellipsoid(P, c, radii, R), c - m, c + m, k, label)

    def capsule(self, a, b, r, k=0.0, label=0, mode="union"):
        a, b = v3(a), v3(b)
        self._prim(mode, lambda P: sd_capsule(P, a, b, r), np.minimum(a, b) - r, np.maximum(a, b) + r, k, label)

    def cone(self, a, b, r1, r2, k=0.0, label=0, mode="union", squash=1.0, up_hint=(0.0, -1.0, 0.0)):
        a, b = v3(a), v3(b)
        m = max(r1, r2)
        if abs(squash - 1.0) < 1e-6:
            fn = lambda P: sd_round_cone(P, a, b, r1, r2)  # noqa: E731
        else:
            fn = lambda P: sd_round_cone_ellip(P, a, b, r1, r2, squash, up_hint)  # noqa: E731
        self._prim(mode, fn, np.minimum(a, b) - m, np.maximum(a, b) + m, k, label)

    def box(self, c, half, R=None, rounding=0.0, k=0.0, label=0, mode="union"):
        c = v3(c)
        m = float(np.linalg.norm(half))
        self._prim(mode, lambda P: sd_box(P, c, half, R, rounding), c - m, c + m, k, label)

    def _prim(self, mode, fn, lo, hi, k, label):
        if mode == "union":
            self.union(fn, lo, hi, k, label)
        elif mode == "sub":
            self.sub(fn, lo, hi, k, label)
        elif mode == "paint":
            self.paint(fn, lo, hi, label)
        else:
            raise ValueError(mode)

    # evaluation -----------------------------------------------------------------------------
    def bounds(self) -> tuple[np.ndarray, np.ndarray]:
        los = [o.lo for o in self.ops if o.kind == "union"]
        his = [o.hi for o in self.ops if o.kind == "union"]
        return np.min(los, axis=0), np.max(his, axis=0)

    @staticmethod
    def _apply(op, cur, curl, Q):
        if op.kind == "union":
            dp = op.fn(Q)
            nl = np.where(dp < cur, np.int16(op.label), curl)
            nd = smin(cur, dp, op.k)
        elif op.kind == "sub":
            dp = -op.fn(Q)
            nl = curl if op.label is None else np.where(dp > cur, np.int16(op.label), curl)
            nd = smax(cur, dp, op.k)
        elif op.kind == "inter":
            dp = op.fn(Q)
            nl = curl
            nd = smax(cur, dp, op.k)
        elif op.kind == "paint":
            dp = op.fn(Q)
            nl = np.where(dp < 0.0, np.int16(op.label), curl)
            nd = cur
        elif op.kind == "disp":
            nd = cur + op.fn(Q)
            nl = curl
        else:
            raise ValueError(op.kind)
        return nd, nl

    def eval(self, P: np.ndarray):
        """Evaluates at points P (N,3). Returns (d, label)."""
        n = len(P)
        d = np.full(n, BIG)
        lab = np.full(n, self.base_label, dtype=np.int16)
        if n == 0:
            return d, lab
        lo_box, hi_box = P.min(0), P.max(0)
        for op in self.ops:
            if np.any(op.hi < lo_box) or np.any(op.lo > hi_box):
                if op.kind == "inter":
                    d[:] = BIG
                continue
            if np.all(op.lo <= lo_box) and np.all(op.hi >= hi_box):
                d, lab = self._apply(op, d, lab, P)
                continue
            m = np.all((P >= op.lo) & (P <= op.hi), axis=1)
            idx = np.nonzero(m)[0]
            if op.kind == "inter":
                out = ~m
                d[out] = BIG
            if len(idx) == 0:
                continue
            nd, nl = self._apply(op, d[idx], lab[idx], P[idx])
            d[idx] = nd
            lab[idx] = nl
        return d, lab

    def eval_grid(self, origin, h: float, shape):
        """Evaluates on a regular grid x_i = origin + i*h. Returns (d, label) of `shape`."""
        origin = np.asarray(origin, dtype=np.float64)
        nx, ny, nz = shape
        d = np.full(shape, BIG)
        lab = np.full(shape, self.base_label, dtype=np.int16)
        axes = [origin[a] + np.arange(shape[a]) * h for a in range(3)]
        for op in self.ops:
            rng = []
            for a in range(3):
                i0 = int(math.floor((op.lo[a] - origin[a]) / h))
                i1 = int(math.ceil((op.hi[a] - origin[a]) / h)) + 1
                rng.append((max(0, i0), min(shape[a], i1)))
            empty = any(r[0] >= r[1] for r in rng)
            if op.kind == "inter":
                mask = np.ones(shape, bool)
                if not empty:
                    mask[rng[0][0]:rng[0][1], rng[1][0]:rng[1][1], rng[2][0]:rng[2][1]] = False
                d[mask] = BIG
            if empty:
                continue
            sl = (slice(*rng[0]), slice(*rng[1]), slice(*rng[2]))
            gx, gy, gz = np.meshgrid(axes[0][sl[0]], axes[1][sl[1]], axes[2][sl[2]], indexing="ij")
            Q = np.stack([gx.ravel(), gy.ravel(), gz.ravel()], -1)
            sub_shape = gx.shape
            nd, nl = self._apply(op, d[sl].ravel(), lab[sl].ravel(), Q)
            d[sl] = nd.reshape(sub_shape)
            lab[sl] = nl.reshape(sub_shape)
        return d, lab
