"""The Bloom's growths (ADR-0025): clusters of pale fruiting bodies and the fungal mounds Hum
survivors leave where they rooted into the soil at dawn.

build(params, outputs): outputs[0] = LOD0, outputs[1] = LOD1 (cheaper). Origin = base centre on the
ground (z = 0); stems and skirts run a few centimetres below it so the growths come out of uneven
ground instead of standing on it.

Each mushroom is real geometry: a curved, fibrous stem swelling at its base; a cap of revolution
(bell, convex, flat with an umbo, or old and upturned) with a wavy, sometimes split margin; a thin
underside and radial gills, full and partial. Some are broken: a cap torn half away, a toppled
mushroom, a snapped cap lying gills-up. Caps share one double-sided material (bloom_fungus shader).

Vertex colour (lib.vcolor channels, read by bloom_fungus.gdshader):
  R = baked AO, G = gills / underside (they glow at night and sit in shade), B = thinness (the cap's
  margin and the gills let light through), A = 1 (no wind).
UVs: caps polar (U around, V from the centre out), stems U around / V along, so the bloom_cap
texture's fibrils (streaks along V) radiate over the cap and run up the stem.

params.kind: caps | mound
  caps:  mushrooms: [[x, y, scale, form, lean, angle], ...] (form 0 bell .. 1 old and upturned,
         scale = cap radius in m), broken: [{"kind": "torn"|"toppled"|"cap", ...}], felt (radius of a
         mycelial cushion they grow from, 0 = none), size (scales the whole cluster), mat, felt_mat
  mound: length, width, height, humps (spine of the body under the shroud), caps (count)
"""
from __future__ import annotations

import math

from mathutils import Vector, noise

from lib import common, export, vcolor
from lib.veg_mesh import MeshBuilder, horiz, tube


def _frame(a: Vector) -> tuple[Vector, Vector]:
    e1 = a.orthogonal().normalized()
    return e1, a.cross(e1).normalized()


def _profile(form: float, R: float):
    """Height of the cap's top surface above the stem's apex at radius fraction s (0 centre .. 1
    margin): bells hang their margin below the apex, old caps turn it up, mature ones carry an umbo."""
    apex = R * (0.62 - 0.55 * form)
    margin = R * (-0.55 + 0.75 * form)
    p = 1.3 + 1.6 * form
    umbo = R * 0.13 * math.sin(math.pi * min(1.0, form * 1.4))

    def h(s: float) -> float:
        base = margin + (apex - margin) * max(0.0, 1.0 - s ** p) ** (0.85 - 0.3 * form)
        if form > 0.75:
            # Old caps dish in around the umbo before the upturned margin.
            base -= R * 0.12 * (form - 0.75) * 4.0 * math.sin(math.pi * s) * s
        return base + umbo * math.exp(-(s / 0.22) ** 2)
    return h


def _cap(mb: MeshBuilder, mat: str, top: Vector, a: Vector, R: float, form: float, rng, *, segs: int, rings: int,
         gills: int, arc: float = 2.0 * math.pi, stem_r: float = 0.004, split: float = 0.0) -> None:
    """Cap of revolution about axis `a` from the stem's apex `top`: top surface, margin edge,
    underside and radial gills. `arc` < 2 pi tears part of it away; `split` cracks the margin."""
    m = mb.mat(mat)
    e1, e2 = _frame(a)
    h = _profile(form, R)
    seed_v = Vector((rng.uniform(0, 50), rng.uniform(0, 50), rng.uniform(0, 50)))
    full = arc >= 2.0 * math.pi - 1e-4
    n_ang = segs if full else max(3, int(segs * arc / (2.0 * math.pi)) + 1)
    a0 = rng.uniform(0.0, 2.0 * math.pi)
    T_c = R * 0.16 + 0.002
    T_m = 0.0012

    def ang(j: int) -> float:
        return a0 + (arc * j / segs if full else arc * j / (n_ang - 1))

    def rim(t: float) -> float:
        q = Vector((math.cos(t) * 1.4, math.sin(t) * 1.4, 0.0)) + seed_v
        r = 1.0 + 0.06 * noise.noise(q) + 0.04 * noise.noise(q * 3.1)
        if split > 0.0:
            # A few deep notches where the margin has split.
            r -= split * max(0.0, math.cos(t * 3.0 + seed_v.x)) ** 12
        return r

    def surf(s: float, t: float, under: float) -> Vector:
        rr = R * s * rim(t)
        z = h(s) - under * (T_c * (1.0 - s) + T_m * s)
        d = e1 * math.cos(t) + e2 * math.sin(t)
        return top + d * rr + a * z

    def col_top(s: float) -> tuple:
        return (1.0, 0.0, 0.25 + 0.75 * s ** 2, 1.0)

    def col_under(s: float) -> tuple:
        return (1.0, 1.0, 0.55 + 0.45 * s, 1.0)

    # Top surface: apex fan (shared centre) + rings. UV: U around (the fibrils repeat every ~5 cm of
    # circumference), V out from the centre (5 cm per texture tile).
    ring_s = [(i / rings) ** 0.85 for i in range(1, rings + 1)]
    apex = mb.v(surf(0.0, 0.0, 0.0), col_top(0.0))
    rows_top = [[mb.v(surf(sv, ang(j), 0.0), col_top(sv)) for j in range(n_ang)] for sv in ring_s]
    uk = max(1, round(R * 2.0 * math.pi / 0.05))
    n_div = n_ang if full else n_ang - 1
    vk = R / 0.05

    def u_of(j: int) -> float:
        return uk * j / n_div

    for j in range(n_div):
        j2 = (j + 1) % n_ang
        ua, ub = u_of(j), u_of(j + 1)
        mb.f((apex, rows_top[0][j], rows_top[0][j2]), (((ua + ub) * 0.5, 0.0), (ua, ring_s[0] * vk), (ub, ring_s[0] * vk)), m)
        for i in range(rings - 1):
            va, vb = ring_s[i] * vk, ring_s[i + 1] * vk
            mb.f((rows_top[i][j], rows_top[i + 1][j], rows_top[i + 1][j2], rows_top[i][j2]),
                 ((ua, va), (ua, vb), (ub, vb), (ub, va)), m)
    # Underside, from the stem out to the margin; the margin is thin enough to share the top's rim.
    s_in = min(0.5, stem_r * 1.15 / R)
    under_rows = [[mb.v(surf(s_in, ang(j), 1.0), col_under(s_in)) for j in range(n_ang)], rows_top[-1]]
    for j in range(n_div):
        j2 = (j + 1) % n_ang
        ua, ub = u_of(j), u_of(j + 1)
        mb.f((under_rows[0][j], under_rows[0][j2], under_rows[1][j2], under_rows[1][j]),
             ((ua, s_in * vk), (ub, s_in * vk), (ub, vk), (ua, vk)), m)
    if not full:
        # The torn face where the cap broke away: ragged flesh between top and underside.
        for j in (0, n_ang - 1):
            t = ang(j)
            pts_t = [surf(s, t, 0.0) for s in (0.0, 0.5, 1.0)]
            pts_u = [surf(s, t, 1.0) for s in (s_in, 0.5, 1.0)]
            vt = [mb.v(p, (0.9, 0.3, 0.4, 1.0)) for p in pts_t]
            vu = [mb.v(p, (0.9, 0.3, 0.4, 1.0)) for p in pts_u]
            for k in range(2):
                mb.f((vt[k], vt[k + 1], vu[k + 1], vu[k]), ((0.1 * k, 0.0), (0.1 * k + 0.1, 0.0), (0.1 * k + 0.1, 0.05), (0.1 * k, 0.05)), m)
    # Gills: radial fins hanging from the underside, deepest at mid-radius (two triangles each);
    # every other one a partial gill from mid-radius out.
    if gills > 0:
        for g in range(gills):
            t = a0 + arc * (g + 0.5) / gills
            s0 = s_in * 1.05 if g % 2 == 0 else 0.45
            s1 = 0.96
            sm = (s0 + s1) * 0.5
            depth = R * (0.13 + 0.05 * form) * (1.0 if g % 2 == 0 else 0.7)
            p0, pm, p1 = surf(s0, t, 1.0) - a * 0.0003, surf(sm, t, 1.0) - a * 0.0003, surf(s1, t, 1.0) - a * 0.0003
            pd = pm - a * depth
            v0 = mb.v(p0, (1.0, 1.0, 0.8, 1.0))
            vm = mb.v(pm, (1.0, 1.0, 0.8, 1.0))
            v1 = mb.v(p1, (1.0, 1.0, 0.9, 1.0))
            vd = mb.v(pd, (1.0, 1.0, 1.0, 1.0))
            mb.f((v0, vm, vd), ((s0 * 4.0, 0.0), (sm * 4.0, 0.0), (sm * 4.0, 0.25)), m)
            mb.f((vm, v1, vd), ((sm * 4.0, 0.0), (s1 * 4.0, 0.0), (sm * 4.0, 0.25)), m)


def _stem(mb: MeshBuilder, mat: str, pts: list[Vector], r: float, *, sides: int) -> None:
    """A fibrous stem along `pts` (from below the ground to the cap), swelling at its base."""
    radii = []
    for i in range(len(pts)):
        s = i / (len(pts) - 1)
        radii.append(r * (1.0 + 0.55 * math.exp(-((s - 0.04) / 0.12) ** 2)) * (1.0 - 0.18 * s))

    def col(i, s, a_, p):
        return (1.0, 0.0, 0.2, 1.0)

    tube(mb, pts, radii, sides, mat, u_repeats=1, col_fn=col, tip=False, cap_end=False, up_hint=Vector((1.0, 0.0, 0.0)))


def _stem_path(base: Vector, a: Vector, H: float, rings: int, bend: float) -> list[Vector]:
    """The stem leaves its base along its lean `a` and turns up toward the light as it grows; `bend`
    bows it sideways a little. Starts 2 cm under the ground."""
    side = horiz(Vector((a.y, -a.x, 0.0))) if Vector((a.x, a.y)).length > 1e-4 else Vector((1.0, 0.0, 0.0))
    pts = [base - Vector((0.0, 0.0, 0.02))]
    p = base.copy()
    steps = 8
    for k in range(steps):
        s = (k + 0.5) / steps
        d = (a.lerp(Vector((0.0, 0.0, 1.0)), 0.75 * s ** 1.3) + side * bend * 0.25 * math.cos(math.pi * s)).normalized()
        p = p + d * (H / steps)
        if (k + 1) % max(1, steps // rings) == 0 or k == steps - 1:
            pts.append(p.copy())
    if len(pts) > rings + 1:
        pts = pts[:rings] + [pts[-1]]
    return pts


def _mushroom(mb: MeshBuilder, mat: str, base: Vector, R: float, form: float, lean: float, ang: float, rng, lod: int,
              *, arc: float = 2.0 * math.pi, split: float = 0.0, height_k: float = 1.0) -> None:
    """One mushroom at `base`: stem height ~4 cap radii (taller for bells), leaving the ground leaned
    by `lean` radians toward `ang` and turning up; the cap faces mostly up."""
    H = R * (5.0 - 2.7 * form) * height_k * rng.uniform(0.85, 1.15)
    a = Vector((math.cos(ang) * math.sin(lean), math.sin(ang) * math.sin(lean), math.cos(lean))).normalized()
    sr = max(0.0022, R * rng.uniform(0.09, 0.12))
    pts = _stem_path(base, a, H, 2 if lod == 0 else 1, rng.uniform(-1.0, 1.0))
    top = pts[-1]
    tip_dir = (pts[-1] - pts[-2]).normalized()
    ca = tip_dir.lerp(Vector((0.0, 0.0, 1.0)), 0.5).normalized()
    if lod == 0:
        # Caps under 4 cm across keep a plain underside: nobody sees their gills.
        full = R > 0.02
        _stem(mb, mat, pts, sr, sides=6)
        _cap(mb, mat, top, ca, R, form, rng, segs=12 if full else 9, rings=3 if full else 2,
             gills=12 if full else 0, arc=arc, stem_r=sr, split=split)
    else:
        _stem(mb, mat, pts, sr, sides=4)
        _cap(mb, mat, top, ca, R, form, rng, segs=7, rings=1, gills=0, arc=arc, stem_r=sr, split=0.0)


def _toppled(mb: MeshBuilder, mat: str, base: Vector, R: float, form: float, ang: float, rng, lod: int) -> None:
    """A mushroom that fell over: stem along the ground, cap on its edge."""
    H = R * (4.5 - 2.0 * form)
    d = Vector((math.cos(ang), math.sin(ang), 0.0))
    b0 = base + Vector((0.0, 0.0, 0.004))
    mid = b0 + d * H * 0.5 + Vector((0.0, 0.0, R * 0.12))
    top = b0 + d * H + Vector((0.0, 0.0, R * 0.35))
    sr = max(0.0022, R * 0.11)
    a = (d + Vector((0.0, 0.0, 0.35))).normalized()
    if lod == 0:
        _stem(mb, mat, [b0, mid, top], sr, sides=6)
        _cap(mb, mat, top, a, R, form, rng, segs=12, rings=3, gills=12, stem_r=sr)
    else:
        _stem(mb, mat, [b0, top], sr, sides=4)
        _cap(mb, mat, top, a, R, form, rng, segs=7, rings=1, gills=0, stem_r=sr)


def _loose_cap(mb: MeshBuilder, mat: str, base: Vector, R: float, form: float, rng, lod: int) -> None:
    """A snapped-off cap lying gills-up on the litter, a torn stub of stem still in it."""
    tilt = rng.uniform(2.3, 2.8)
    t_ang = rng.uniform(0.0, 2.0 * math.pi)
    a = Vector((math.cos(t_ang) * math.sin(tilt), math.sin(t_ang) * math.sin(tilt), math.cos(tilt))).normalized()
    top = base + Vector((0.0, 0.0, R * 0.5))
    sr = max(0.0022, R * 0.11)
    if lod == 0:
        _cap(mb, mat, top, a, R, form, rng, segs=12, rings=3, gills=12, stem_r=sr, split=0.4)
        stub = [top + a * (R * 0.05), top - a * (R * 0.7) + Vector((0.0, 0.0, 0.004))]
        _stem(mb, mat, stub, sr * 0.95, sides=6)
    else:
        _cap(mb, mat, top, a, R, form, rng, segs=7, rings=1, gills=0, stem_r=sr)


def _felt(mb: MeshBuilder, mat: str, R: float, H: float, rng, lod: int, seed: int) -> None:
    """A low cushion of felted mycelium the cluster fruits from; its rim frays into the litter."""
    m = mb.mat(mat)
    nr = 5 if lod == 0 else 2
    ns = 28 if lod == 0 else 12
    ox, oy = rng.uniform(0, 40), rng.uniform(0, 40)

    def rim(t: float) -> float:
        q = Vector((math.cos(t) * 1.3 + ox, math.sin(t) * 1.3 + oy, 0.4))
        return R * (1.0 + 0.25 * noise.noise(q) + 0.12 * noise.noise(q * 3.7))

    rows = []
    for i in range(nr + 1):
        s = i / nr
        row = []
        for j in range(ns):
            t = 2.0 * math.pi * j / ns
            rr = rim(t) * s
            x, y = math.cos(t) * rr, math.sin(t) * rr
            z = H * max(0.0, 1.0 - s ** 1.6) ** 1.3 + noise.noise(Vector((x * 9 + ox, y * 9 + oy, 0.0))) * H * 0.25 * (1 - s)
            row.append((mb.v((x, y, z - 0.012 * s), (1.0, 0.0, 0.3 + 0.5 * s, 1.0)), x, y))
        rows.append(row)
    skirt = []
    for j in range(ns):
        t = 2.0 * math.pi * j / ns
        rr = rim(t) * 1.08
        x, y = math.cos(t) * rr, math.sin(t) * rr
        skirt.append((mb.v((x, y, -0.03), (0.6, 0.0, 0.9, 1.0)), x, y))
    rows.append(skirt)
    c0 = rows[0][0]
    uvs = lambda p: (p[1] * 2.0, p[2] * 2.0)  # noqa: E731  (felt texture repeats every 0.5 m)
    for j in range(ns):
        j2 = (j + 1) % ns
        mb.f((c0[0], rows[1][j][0], rows[1][j2][0]), (uvs(c0), uvs(rows[1][j]), uvs(rows[1][j2])), m)
    for i in range(1, len(rows) - 1):
        for j in range(ns):
            j2 = (j + 1) % ns
            a0, a1, b0, b1 = rows[i][j], rows[i][j2], rows[i + 1][j], rows[i + 1][j2]
            mb.f((a0[0], b0[0], b1[0], a1[0]), (uvs(a0), uvs(b0), uvs(b1), uvs(a1)), m)


def build_caps(p: dict, lod: int):
    rng = common.rng(p["seed"])
    noise.seed_set(int(p["seed"]) % 100000)
    mb = MeshBuilder()
    mat = p.get("mat", "bloom_caps")
    k = float(p.get("size", 1.0))
    felt_h = float(p.get("felt_h", 0.05)) * k
    if float(p.get("felt", 0.0)) > 0.0:
        _felt(mb, p.get("felt_mat", "bloom_felt"), float(p["felt"]) * k, felt_h, rng, lod, int(p["seed"]))
    for x, y, R, form, lean, ang in p["mushrooms"]:
        base = Vector((x * k, y * k, felt_h * 0.6 if p.get("felt", 0.0) else 0.0))
        _mushroom(mb, mat, base, float(R) * k, float(form), float(lean), float(ang), rng, lod,
                  split=0.35 if form > 0.8 else 0.0)
    for b in p.get("broken", []):
        base = Vector((b["at"][0] * k, b["at"][1] * k, 0.0))
        if b["kind"] == "torn":
            _mushroom(mb, mat, base, b["r"] * k, b["form"], b.get("lean", 0.15), b.get("ang", 0.0), rng, lod,
                      arc=math.radians(b.get("arc", 210.0)))
        elif b["kind"] == "toppled":
            _toppled(mb, mat, base, b["r"] * k, b["form"], b.get("ang", 0.0), rng, lod)
        else:
            _loose_cap(mb, mat, base, b["r"] * k, b["form"], rng, lod)
    return mb


# ---------------------------------------------------------------------------------------------
# Rooting mound
# ---------------------------------------------------------------------------------------------

def build_mound(p: dict, lod: int):
    """A Hollowed that rooted at dawn: a body-length mound under a shroud of felted mycelium. Soft
    swellings where a head, a shoulder, a hip and a drawn-up knee lie curled on their side say what
    is under it without showing it; caps fruit from its back, and the shroud frays out into the
    litter (the Bloom field spreads the web further, BloomMounds)."""
    rng = common.rng(p["seed"])
    noise.seed_set(int(p["seed"]) % 100000)
    mb = MeshBuilder()
    felt = mb.mat(p.get("felt_mat", "bloom_felt"))
    L, W, Hh = float(p.get("length", 1.7)), float(p.get("width", 0.7)), float(p.get("height", 0.38))
    hl = L * 0.5
    j = lambda k: rng.uniform(-k, k)  # noqa: E731
    # (x, y, rx, ry, height): curled on its side, knees drawn up toward +x.
    parts = [
        (j(0.03) - 0.04, hl * 0.72, 0.13, 0.14, 0.75),   # head
        (j(0.02), hl * 0.32, W * 0.34, hl * 0.36, 1.0),   # shoulders and ribs
        (0.04 + j(0.02), -hl * 0.18, W * 0.3, hl * 0.3, 0.9),  # hip
        (W * 0.3 + j(0.03), -hl * 0.46, W * 0.2, hl * 0.2, 0.72),  # knees drawn up
        (W * 0.12 + j(0.03), -hl * 0.82, W * 0.15, hl * 0.15, 0.42),  # feet
        (-W * 0.3 + j(0.02), hl * 0.1, W * 0.13, hl * 0.32, 0.5),  # an arm along the side
    ]
    ox, oy = rng.uniform(0, 40), rng.uniform(0, 40)

    def body(x: float, y: float) -> float:
        acc = 0.0
        for cx, cy, rx, ry, hz in parts:
            q = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
            if q < 1.0:
                acc += (hz * Hh * (1.0 - q) ** 0.55) ** 4
        z = acc ** 0.25
        # The shroud drapes between the parts instead of dipping to the ground.
        drape = Hh * 0.42 * math.exp(-((x * 1.9 / W) ** 2 + (y / (hl * 0.8)) ** 2) * 1.6)
        z = (z ** 4 + drape ** 4) ** 0.25
        return z + noise.noise(Vector((x * 6.0 + ox, y * 6.0 + oy, 0.3))) * 0.025 * min(1.0, z * 8.0)

    ns = 64 if lod == 0 else 24
    nr = 14 if lod == 0 else 5
    # Outline: march out from the middle until the shroud thins to nothing, per direction.
    edge = []
    for k in range(ns):
        t = 2.0 * math.pi * k / ns
        d = Vector((math.cos(t), math.sin(t)))
        r = 0.05
        while r < L and body(d.x * r, d.y * r) > 0.02:
            r += 0.01
        q = Vector((math.cos(t) * 1.3 + ox, math.sin(t) * 1.3 + oy, 0.7))
        edge.append(r * (1.0 + 0.1 * noise.noise(q) + 0.05 * noise.noise(q * 3.3)))
    rows = [[mb.v((0.0, 0.0, body(0.0, 0.0)), (1.0, 0.0, 0.2, 1.0))]]
    for i in range(1, nr + 1):
        f = i / nr
        row = []
        for k in range(ns):
            t = 2.0 * math.pi * k / ns
            x, y = math.cos(t) * edge[k] * f, math.sin(t) * edge[k] * f
            row.append(mb.v((x, y, body(x, y) - 0.015 * f), (1.0, 0.0, 0.2 + 0.6 * f, 1.0)))
        rows.append(row)
    # Fraying skirt: tongues of felt out over the litter, sinking into it.
    skirt = []
    for k in range(ns):
        t = 2.0 * math.pi * k / ns
        tongue = 1.12 + 0.18 * max(0.0, noise.noise(Vector((math.cos(t) * 2.2 + oy, math.sin(t) * 2.2 + ox, 1.9))))
        x, y = math.cos(t) * edge[k] * tongue, math.sin(t) * edge[k] * tongue
        skirt.append(mb.v((x, y, -0.035), (0.7, 0.0, 1.0, 1.0)))
    rows.append(skirt)
    uvs = lambda vi: (mb.co[vi][0] * 1.6, mb.co[vi][1] * 1.6)  # noqa: E731  (felt tile 0.62 m)
    c0 = rows[0][0]
    for k in range(ns):
        k2 = (k + 1) % ns
        mb.f((c0, rows[1][k], rows[1][k2]), (uvs(c0), uvs(rows[1][k]), uvs(rows[1][k2])), felt)
    for i in range(1, len(rows) - 1):
        for k in range(ns):
            k2 = (k + 1) % ns
            q = (rows[i][k], rows[i + 1][k], rows[i + 1][k2], rows[i][k2])
            mb.f(q, tuple(uvs(v) for v in q), felt)
    # Fruiting bodies from its back, mostly on the shoulder and hip, leaning out of the surface.
    caps_mat = p.get("mat", "bloom_caps")
    n_caps = int(p.get("caps", 9))
    for k in range(n_caps if lod == 0 else (n_caps + 1) // 3):
        cx, cy, rx, ry, _ = parts[[1, 1, 2, 2, 3, 0][int(rng.uniform(0, 6))]]
        x = cx + rng.uniform(-rx, rx) * 0.55
        y = cy + rng.uniform(-ry, ry) * 0.55
        z = body(x, y) - 0.008
        e = 0.02
        nrm = Vector((body(x - e, y) - body(x + e, y), body(x, y - e) - body(x, y + e), 2 * e)).normalized()
        lean = math.acos(max(-1.0, min(1.0, nrm.z))) * 0.7
        _mushroom(mb, caps_mat, Vector((x, y, z)), rng.uniform(0.02, 0.045), rng.uniform(0.15, 0.95), lean,
                  math.atan2(nrm.y, nrm.x), rng, lod, height_k=0.75)
    return mb


def build(params: dict, outputs: list[str]) -> None:
    kind = params["kind"]
    name = params["name"]
    for lod, out in enumerate(outputs):
        mb = {"caps": build_caps, "mound": build_mound}[kind](params, lod)
        obj = mb.build(name + ("" if lod == 0 else f"_lod{lod}"))
        # AO from the cluster itself and the ground: stems shade each other, gills sit in the dark.
        vcolor.bake_ao([obj], samples=20 if lod == 0 else 10, distance=float(params.get("ao_dist", 0.12)),
                       strength=0.9)
        print(f"[veg_fungus] {name} lod{lod}: {common.triangle_count(obj)} tris")
        export.export_glb(out, [obj])
