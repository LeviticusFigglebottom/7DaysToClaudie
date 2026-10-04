"""Tree skeletons and LOD assembly shared by the vegetation generators (runs inside Blender).

A Tree holds a trunk (one or more stems), roots, branches and *card lists per LOD* (cards are
placed by the species code, which knows its atlas). assemble(tree, lod) turns that description
into one MeshBuilder: bark tubes (sides/rings reduced per LOD) + foliage cards, writing the
vertex colour channels:
    R = AO (ground contact, crown shade, depth inside the crown for cards)
    G = 0 (unused for vegetation)
    B = moss mask on bark (bark shader), per-card random variation on foliage
    A = wind weight: 0 at the trunk base -> ~0.5 at branch tips -> 1 at card tips
Card normals are bent outwards from the crown (crown.outward) so a crown shades like a volume
instead of a pile of flat planes; each card's front face is turned outwards too.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from mathutils import Vector, noise

from .veg_mesh import UP, MeshBuilder, card, tube


def smooth(e0: float, e1: float, x: float) -> float:
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0) if e1 != e0 else 0.0))
    return t * t * (3 - 2 * t)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


@dataclass
class Stem:
    """Trunk or stem: polyline + radii. lobes = [(angle, strength)] root-flare lobes near the base."""
    pts: list
    radii: list
    mat: str
    lobes: list = field(default_factory=list)
    lobe_height: float = 0.9
    u_repeats: int = 2
    tip: bool = True
    break_top: object = None     # optional callable(mb, top_ring, pts, lod, v_end) for broken tops
    noise_amp: float = 0.025
    noise_seed: int = 0
    ring_keep: tuple = (1, 2, 4)  # keep every n-th ring above `keep_all_below` per LOD
    keep_all_below: float = 1.6
    sides: tuple = (12, 8, 5)
    end_cap: object = None      # (mat, uv_fn) for a flat cut top instead of a tip


@dataclass
class Branch:
    pts: list
    radii: list
    mat: str
    wind0: float = 0.15
    wind1: float = 0.55
    sides: tuple = (4, 3, 0)     # sides per LOD (0 = not built)
    min_len_lod: tuple = (0.0, 1.5, 99.0)
    u_repeats: int = 1
    tip: bool = True
    moss: float = 0.0

    @property
    def length(self) -> float:
        return sum((self.pts[i + 1] - self.pts[i]).length for i in range(len(self.pts) - 1))

    def at(self, s: float) -> tuple[Vector, Vector, float]:
        """Point, tangent and radius at fraction s of the length."""
        total = self.length
        d = s * total
        acc = 0.0
        for i in range(len(self.pts) - 1):
            seg = (self.pts[i + 1] - self.pts[i]).length
            if acc + seg >= d or i == len(self.pts) - 2:
                f = 0.0 if seg < 1e-9 else min(1.0, max(0.0, (d - acc) / seg))
                p = self.pts[i].lerp(self.pts[i + 1], f)
                t = (self.pts[i + 1] - self.pts[i]).normalized()
                r = lerp(self.radii[i], self.radii[i + 1], f)
                return p, t, r
            acc += seg
        return self.pts[-1], (self.pts[-1] - self.pts[-2]).normalized(), self.radii[-1]


@dataclass
class Card:
    base: Vector
    direction: Vector
    side: Vector
    length: float
    width: float
    region: str
    droop: float = 0.1
    fold: float = 0.0
    segs: int = 2
    wind0: float = 0.5
    wind1: float = 1.0
    prio: float = 0.5
    shade: float = 1.0      # extra AO multiplier (hanging/inner cards)
    twist: float = 0.0
    mirror: bool = False


class Crown:
    """Crown envelope used for card normals and AO. profile(z) -> (cx, cy, radius) or None."""

    def __init__(self, z0: float, z1: float, profile, up_bias: float = 0.55):
        self.z0, self.z1 = z0, z1
        self.profile = profile
        self.up_bias = up_bias

    def rel(self, p: Vector) -> tuple[float, Vector]:
        """(relative radial depth 0 axis..1 envelope, outward unit vector)."""
        z = min(max(p.z, self.z0), self.z1)
        cx, cy, r = self.profile(z)
        h = Vector((p.x - cx, p.y - cy, 0.0))
        rel = h.length / max(r, 0.05)
        hd = h.normalized() if h.length > 1e-5 else Vector((0.0, 0.0, 0.0))
        hz = (p.z - self.z0) / max(1e-3, self.z1 - self.z0)
        up = self.up_bias + 0.9 * smooth(0.75, 1.0, hz) - 0.6 * (1.0 - smooth(0.0, 0.15, hz))
        o = hd + Vector((0.0, 0.0, up))
        if p.z > self.z1:
            o = Vector((hd.x * 0.3, hd.y * 0.3, 1.0))
        return rel, o.normalized()


@dataclass
class Tree:
    name: str
    stems: list
    roots: list = field(default_factory=list)
    branches: list = field(default_factory=list)
    cards: tuple = field(default_factory=lambda: ([], [], []))
    foliage_mat: str = "foliage_fir"
    atlas: dict = field(default_factory=dict)
    crown: Crown | None = None
    height: float = 20.0
    crown_base: float = 8.0
    budgets: tuple = (9000, 3000, 800)
    normal_bend: tuple = (0.62, 0.72, 0.85)
    ao_range: tuple = (0.32, 1.0)
    moss_dir: float = 0.0
    moss_height: float = 2.5
    trunk_ao_crown: float = 0.55
    seed: int = 0


# ---------------------------------------------------------------------------------------------
# Trunk helpers
# ---------------------------------------------------------------------------------------------

def lobe_factor(lobes: list, ang: float, sharp: float = 3.0) -> float:
    if not lobes:
        return 0.0
    s = 0.0
    for a, k in lobes:
        c = math.cos(ang - a)
        if c > 0.0:
            s += k * c ** (sharp * 2.0)
    return s


def bark_color_fn(tree: Tree, wind0=0.0, wind1=0.15, moss_scale=1.0, base_ao=None):
    """Vertex colours for bark: AO from ground + crown shade, moss mask (B), wind (A).
    (mathutils.noise is seed-independent, so per-tree variety comes from a seed offset.)"""
    H = tree.height
    zc = tree.crown_base
    off = Vector(((tree.seed * 0.1373) % 61.0, (tree.seed * 0.3119) % 53.0, (tree.seed * 0.0711) % 47.0))

    def fn(i, s, ang, p):
        z = p.z
        ao = 0.58 + 0.42 * smooth(-0.2, 2.2, z)
        ao *= lerp(1.0, tree.trunk_ao_crown, smooth(zc - 1.5, zc + 2.5, z))
        if base_ao is not None:
            ao *= base_ao
        # moss: low on the trunk, on one side, broken up by noise
        side = 0.5 + 0.5 * math.cos(math.atan2(p.y, p.x) - tree.moss_dir)
        nz = noise.noise(Vector((p.x * 2.5, p.y * 2.5, p.z * 1.2)) + off)
        mh = tree.moss_height * (0.75 + 0.5 * (0.5 + 0.5 * noise.noise(Vector((p.x * 0.7, p.y * 0.7, 3.3)) + off)))
        moss = (1.0 - smooth(0.2, mh, z)) * (0.35 + 0.65 * side) + nz * 0.35
        moss = max(0.0, min(1.0, moss * moss_scale)) if tree.moss_height > 0.25 else 0.0
        w = lerp(wind0, wind1, max(0.0, min(1.0, z / max(H, 1.0))))
        return (max(0.0, min(1.0, ao)), 0.0, moss, w)
    return fn


def build_stem(mb: MeshBuilder, tree: Tree, st: Stem, lod: int) -> None:
    sides = st.sides[lod]
    keep = st.ring_keep[lod]
    pts, radii = [], []
    for i, (p, r) in enumerate(zip(st.pts, st.radii)):
        if i == 0 or i == len(st.pts) - 1 or p.z < st.keep_all_below or (i % keep) == 0:
            pts.append(p)
            radii.append(r)
    noff = Vector(((st.noise_seed * 0.2131) % 57.0, (st.noise_seed * 0.0917) % 43.0, 0.0))
    amp = st.noise_amp if lod == 0 else st.noise_amp * 0.5
    lobes = st.lobes if lod < 2 else st.lobes[:3]

    def rfn(i, s, ang):
        p = pts[i]
        lf = lobe_factor(lobes, ang) * math.exp(-max(0.0, p.z) / st.lobe_height)
        if p.z < 0.0:
            lf *= 1.0 + (-p.z) * 1.5
        nz = noise.noise(Vector((math.cos(ang) * 1.3, math.sin(ang) * 1.3, p.z * 0.9)) + noff) if amp > 0 else 0.0
        return 1.0 + lf + nz * amp * 4.0

    rings, v_end = tube(mb, pts, radii, sides, st.mat, u_repeats=st.u_repeats, col_fn=bark_color_fn(tree),
                    radius_fn=rfn, tip=st.tip and st.end_cap is None, cap_start=False,
                    cap_end=st.end_cap is not None,
                    end_mat=(st.end_cap[0] if st.end_cap else None),
                    end_cap_uv=(st.end_cap[1] if st.end_cap else None))
    if st.break_top is not None:
        st.break_top(mb, rings[-1], pts, lod, v_end)


def build_branch(mb: MeshBuilder, tree: Tree, b: Branch, lod: int) -> bool:
    sides = b.sides[lod]
    if sides < 3 or b.length < b.min_len_lod[lod]:
        return False
    pts, radii = b.pts, b.radii
    if lod >= 1 and len(pts) > 3:
        idx = sorted(set([0, len(pts) - 1] + list(range(0, len(pts), 2))))
        pts = [pts[i] for i in idx]
        radii = [radii[i] for i in idx]
    fn0 = bark_color_fn(tree, moss_scale=b.moss)

    def col(i, s, ang, p):
        c = fn0(i, s, ang, p)
        return (c[0] * lerp(0.92, 1.0, s), 0.0, c[2], lerp(b.wind0, b.wind1, s))
    tube(mb, pts, radii, sides, b.mat, u_repeats=b.u_repeats, col_fn=col, tip=b.tip)
    return True


# ---------------------------------------------------------------------------------------------
# Cards
# ---------------------------------------------------------------------------------------------

def card_geometry_tris(c: Card) -> int:
    return c.segs * (4 if c.fold != 0.0 else 2)


def add_card(mb: MeshBuilder, tree: Tree, c: Card, lod: int, rnd: float) -> None:
    crown = tree.crown
    rel, outward = crown.rel(c.base) if crown else (1.0, UP)
    bend = tree.normal_bend[lod]
    lo, hi = tree.ao_range

    def ao_at(p: Vector) -> float:
        if crown is None:
            return hi
        r, _ = crown.rel(p)
        hz = smooth(crown.z0, crown.z1, p.z)
        a = lo + (hi - lo) * smooth(0.05, 1.05, r) ** 0.8
        a *= lerp(0.78, 1.0, hz)
        return max(0.0, min(1.0, a * c.shade))

    def col(s, x):
        p = c.base + c.direction * (c.length * s)
        return (ao_at(p), 0.0, rnd, lerp(c.wind0, c.wind1, s))

    def nfn(p, fn):
        if crown is None:
            return fn
        _, o = crown.rel(p)
        f = fn if fn.dot(o) >= 0.0 else -fn
        n = f * (1.0 - bend) + o * bend
        return n.normalized()

    card(mb, c.base, c.direction, c.side, c.length, c.width, tree.atlas[c.region], tree.foliage_mat,
         segs=c.segs, droop=c.droop, fold=c.fold, out=outward, col_fn=col, normal_fn=nfn, mirror=c.mirror,
         twist=c.twist)


def assemble(tree: Tree, lod: int, rng=None) -> MeshBuilder:
    """Bark + cards for one LOD, cards trimmed (lowest priority first) to the triangle budget."""
    mb = MeshBuilder()
    for st in tree.stems:
        build_stem(mb, tree, st, lod)
    t_stem = mb.tris()
    for r in tree.roots:
        build_branch(mb, tree, r, lod)
    t_root = mb.tris() - t_stem
    for b in tree.branches:
        build_branch(mb, tree, b, lod)
    t_br = mb.tris() - t_stem - t_root
    budget = tree.budgets[lod] - mb.tris()
    cards = list(tree.cards[lod])
    order = sorted(range(len(cards)), key=lambda i: -cards[i].prio)
    keep = []
    used = 0
    for i in order:
        t = card_geometry_tris(cards[i])
        if used + t > budget:
            continue
        used += t
        keep.append(i)
    keep.sort()
    for i in keep:
        add_card(mb, tree, cards[i], lod, (i * 0.618034) % 1.0)
    print(f"[veg_tree] {tree.name} lod{lod}: stems {t_stem} roots {t_root} branches {t_br} ({len(tree.branches)}) "
          f"cards {used} ({len(keep)}/{len(cards)} kept)")
    return mb
