"""Trees: grey fir (Douglas-fir-like), hollow larch (western-larch-like), paper birch, dead snag.

build(params, outputs) writes outputs[0..2] = LOD0, LOD1, LOD2 (.glb). Origin = trunk base centre
(root flare dips below 0). Bark material "bark_*" (bark shader), foliage cards "foliage_*"
(foliage shader) mapped into the atlas rects passed in params["atlas"] (from
textures/gen/vegetation.py LAYOUTS).

params: species (fir|larch|birch|snag), seed, height (m), dbh_r (trunk radius at 1.3 m),
        crown_base (fraction of height where the live crown starts), crown_r (max crown radius
        as a fraction of height), lean (deg), stems (birch), density (card density multiplier),
        atlas {region: [u0, v0, u1, v1]}.
"""
from __future__ import annotations

import math

from mathutils import Vector, noise

from lib import common, export
from lib.veg_mesh import UP, horiz, rot_axis
from lib.veg_tree import Branch, Card, Crown, Stem, Tree, assemble, lerp, smooth

GOLDEN = 2.399963


def _aspect(atlas: dict, region: str) -> float:
    u0, v0, u1, v1 = atlas[region]
    return (u1 - u0) / max(1e-6, (v1 - v0))


def _wobble_table(seed: int, off: Vector, z_max: float, amp: float, freq: float, step: float = 0.25):
    """Samples a smooth 2D wobble once (mathutils.noise uses a global seed that later code
    changes) and returns an interpolating lookup z -> (dx, dy)."""
    noise.seed_set(seed % 100000)
    n = int(z_max / step) + 3
    tab = []
    for i in range(n):
        z = i * step
        tab.append((noise.noise(Vector((off.x, off.y, z * freq))) * amp,
                    noise.noise(Vector((off.x + 7.1, off.y, z * freq))) * amp))

    def look(z: float) -> tuple[float, float]:
        f = max(0.0, z) / step
        i = min(int(f), n - 2)
        t = min(1.0, f - i)
        return (tab[i][0] + (tab[i + 1][0] - tab[i][0]) * t, tab[i][1] + (tab[i + 1][1] - tab[i][1]) * t)
    return look


# ---------------------------------------------------------------------------------------------
# Shared conifer pieces
# ---------------------------------------------------------------------------------------------

def conifer_trunk(rng, H, r_dbh, *, mat, lean_deg=0.0, flare=0.62, flare_h=0.62, nlobes=(5, 7), seed=0,
                  top_r=0.012, z_end=None, wobble=0.05):
    """Straight tapering trunk with root flare. Returns (Stem, axis(z) -> Vector, radius(z))."""
    lean_dir = rng.uniform(0, 2 * math.pi)
    lean = math.radians(lean_deg)
    w_off = Vector((rng.uniform(0, 50), rng.uniform(0, 50), 0.0))
    wob = _wobble_table(seed + 3, w_off, H + 2.0, wobble, 0.18)

    def axis(z):
        zz = max(0.0, z)
        off = math.tan(lean) * (zz ** 1.4) / max(H, 1.0) ** 0.4
        wx, wy = wob(zz)
        ramp = smooth(0.0, 3.0, zz)
        return Vector((math.cos(lean_dir) * off + wx * ramp, math.sin(lean_dir) * off + wy * ramp, z))

    def radius(z):
        if z >= 1.3:
            core = r_dbh * max(0.0, (H - z) / (H - 1.3)) ** 0.78
        else:
            core = r_dbh * (1.0 + 0.05 * (1.3 - z))
        fl = r_dbh * flare * math.exp(-(max(z, -0.3) + 0.1) / flare_h)
        return max(top_r, core + fl)

    z_top = H if z_end is None else z_end
    zs = [-0.32, -0.14, 0.0, 0.12, 0.27, 0.45, 0.7, 1.0, 1.35, 1.8]
    z = 2.4
    while z < z_top - 0.9:
        zs.append(z)
        z += rng.uniform(1.4, 2.0) if z < z_top * 0.6 else rng.uniform(1.0, 1.4)
    if z_end is None:
        zs += [H - 0.6, H - 0.25]
    else:
        zs.append(z_end)
    pts = [axis(z) for z in zs]
    radii = [radius(z) for z in zs]
    n = rng.randint(*nlobes)
    a0 = rng.uniform(0, 2 * math.pi)
    # buttress lobes over the main roots: the trunk spreads into them over its first metre
    lobes = [(a0 + 2 * math.pi * i / n + rng.uniform(-0.35, 0.35), rng.uniform(0.25, 0.5)) for i in range(n)]
    st = Stem(pts=pts, radii=radii, mat=mat, lobes=lobes, lobe_height=0.9,
              u_repeats=max(1, round(2 * math.pi * r_dbh / 0.95)), noise_seed=seed, noise_amp=0.012)
    return st, axis, radius


def surface_roots(rng, lobes, r_dbh, axis, mat, count=5):
    roots = []
    for a, k in sorted(lobes, key=lambda t: -t[1])[:count]:
        d = Vector((math.cos(a), math.sin(a), 0.0))
        L = r_dbh * rng.uniform(2.2, 3.6) * (0.8 + 0.6 * k)
        c = axis(0.0)
        c.z = 0.0
        # out of the buttress, along the surface, then down into the soil (no tip left in the air)
        pts = [c + d * (0.3 * r_dbh) + Vector((0, 0, 0.8)),
               c + d * (1.05 * r_dbh) + Vector((0, 0, 0.32)),
               c + d * (1.5 * r_dbh) + Vector((0, 0, 0.1)),
               c + d * (1.5 * r_dbh + 0.45 * L) + Vector((0, 0, 0.01)),
               c + d * (1.5 * r_dbh + L) + Vector((0, 0, -0.3))]
        # gentle meander
        side = Vector((-d.y, d.x, 0.0))
        for i in range(2, 5):
            pts[i] = pts[i] + side * rng.uniform(-0.12, 0.12) * L
        s = 0.8 + 0.5 * k
        radii = [0.48 * r_dbh * s, 0.4 * r_dbh * s, 0.29 * r_dbh * s, 0.16 * r_dbh * s, 0.07 * r_dbh * s]
        roots.append(Branch(pts=pts, radii=radii, mat=mat, wind0=0.0, wind1=0.0, sides=(5, 4, 0),
                            min_len_lod=(0.0, 0.0, 99.0), tip=True, moss=1.2))
    return roots


def conifer_branch_path(start, phi, L, elev0, droop, upturn, rng, n=5, wander=0.06):
    pts = [start]
    p = start.copy()
    a = phi
    for i in range(1, n):
        s = i / (n - 1)
        elev = elev0 - droop * s + upturn * smooth(0.55, 1.0, s)
        a += rng.uniform(-wander, wander)
        d = Vector((math.cos(elev) * math.cos(a), math.cos(elev) * math.sin(a), math.sin(elev)))
        p = p + d * (L / (n - 1))
        pts.append(p)
    return pts


def dead_branches(rng, tree, axis, radius, z_lo, z_hi, count, mat, atlas_dead=True, long_frac=0.25, max_len=2.0,
                  card_scale=1.0):
    """Self-pruned lower trunk: short broken stubs and a few longer dead branches near the crown."""
    for k in range(count):
        z = lerp(z_lo, z_hi, rng.random() ** 0.8)
        phi = rng.uniform(0, 2 * math.pi)
        near = smooth(z_hi - 4.0, z_hi, z)
        long_b = rng.random() < long_frac + 0.45 * near
        c = axis(z)
        r_t = radius(z)
        d0 = Vector((math.cos(phi), math.sin(phi), 0.0))
        start = c + d0 * (r_t * 0.7)
        if long_b:
            L = rng.uniform(0.5, max_len) * (0.5 + 0.5 * near)
            elev = rng.uniform(-0.55, 0.05)
            pts = conifer_branch_path(start, phi, L, elev, rng.uniform(0.0, 0.3), 0.0, rng, n=3, wander=0.15)
            r0 = 0.018 + 0.013 * L
            # most dead limbs have snapped somewhere along their length: a blunt end, not a spike
            snapped = rng.random() < 0.6
            b = Branch(pts=pts, radii=[r0 * 1.25, r0 * 0.7, r0 * (0.5 if snapped else 0.3)], mat=mat, wind0=0.08,
                       wind1=0.35, sides=(4, 3, 0), min_len_lod=(0.0, 1.6, 99.0), broken=snapped)
            tree.branches.append(b)
            # a couple of dead twigs
            for j in range(rng.randint(1, 3)):
                s = rng.uniform(0.35, 0.85)
                p, t, r = b.at(s)
                ta = phi + rng.choice((-1, 1)) * rng.uniform(0.5, 1.1)
                tl = L * rng.uniform(0.2, 0.4)
                tp = conifer_branch_path(p, ta, tl, rng.uniform(-0.5, 0.2), 0.2, 0.0, rng, n=2, wander=0.2)
                tree.branches.append(Branch(pts=tp, radii=[r * 0.6, r * 0.25], mat=mat, wind0=0.2,
                                            wind1=0.4, sides=(3, 0, 0)))
            if atlas_dead and rng.random() < 0.6:
                p, t, r = b.at(rng.uniform(0.4, 0.8))
                ln = rng.uniform(0.5, 0.9) * card_scale
                dd = (t + Vector((0, 0, rng.uniform(-0.2, 0.1)))).normalized()
                tree.cards[0].append(Card(base=p, direction=dd, side=UP.cross(horiz(dd)), length=ln,
                                          width=ln * 2.0, region="dead", droop=0.1, segs=1, wind0=0.3, wind1=0.6,
                                          prio=0.15, shade=0.8))
        else:
            # self-pruned stub: short and stout, a collar where it leaves the trunk, broken off blunt
            L = rng.uniform(0.05, 0.4) * rng.uniform(0.4, 1.0)
            elev = rng.uniform(-0.4, 0.08)
            d = Vector((math.cos(elev) * d0.x, math.cos(elev) * d0.y, math.sin(elev)))
            r0 = rng.uniform(0.018, 0.045)
            pts = [start, start + d * (r_t * 0.3 + L * 0.3), start + d * (r_t * 0.3 + L)]
            tree.branches.append(Branch(pts=pts, radii=[r0 * 1.7, r0, r0 * 0.82], mat=mat, wind0=0.02, wind1=0.05,
                                        sides=(5, 0, 0), min_len_lod=(0.0, 99, 99), broken=True))


# ---------------------------------------------------------------------------------------------
# Grey fir (Douglas-fir-like)
# ---------------------------------------------------------------------------------------------

def build_fir(p: dict) -> Tree:
    rng = common.rng(p["seed"])
    atlas = p["atlas"]
    H = float(p["height"])
    r_dbh = float(p["dbh_r"])
    z_cb = H * float(p["crown_base"])
    Rmax = H * float(p["crown_r"])
    dens = float(p.get("density", 1.35))   # candidates beyond the budget are trimmed by priority
    bark = "bark_grey_fir"
    st, axis, radius = conifer_trunk(rng, H, r_dbh, mat=bark, lean_deg=float(p.get("lean", 1.0)), seed=p["seed"])
    # LOD0 budget: the full crown (every spray card) plus the broken stubs of the bare lower trunk
    tree = Tree(name=p["name"], stems=[st], foliage_mat="foliage_fir", atlas=atlas, height=H, crown_base=z_cb,
                seed=int(p["seed"]), moss_dir=rng.uniform(0, 2 * math.pi), moss_height=rng.uniform(1.8, 3.2),
                budgets=(10800, 3000, 800))
    tree.roots = surface_roots(rng, st.lobes, r_dbh, axis, bark, count=rng.randint(4, 6))

    def R(z):
        t = max(0.0, min(1.0, (H - z) / max(1e-3, H - z_cb)))
        return Rmax * (t ** 0.85) * (0.8 + 0.2 * smooth(0.0, 0.15, 1.0 - t)) + 0.15

    def profile(z):
        c = axis(z)
        return c.x, c.y, R(z)
    tree.crown = Crown(z_cb - 0.6, H, profile, up_bias=0.45)

    sprays = ("spray_a", "spray_a", "spray_b", "spray_c")
    # ---- live crown: whorls ------------------------------------------------------------------
    z = z_cb + rng.uniform(0.0, 0.3)
    k = 0
    while z < H - 0.55:
        hz = (z - z_cb) / max(1e-3, H - z_cb)
        n = rng.choice((3, 4, 4, 5))
        a0 = k * GOLDEN + rng.uniform(-0.3, 0.3)
        members = [(a0 + 2 * math.pi * i / n + rng.uniform(-0.35, 0.35), 1.0) for i in range(n)]
        # an intermediate (inter-whorl) branch or two
        for _ in range(rng.choice((0, 0, 1))):
            members.append((rng.uniform(0, 2 * math.pi), rng.uniform(0.45, 0.7)))
        for phi, lscale in members:
            if rng.random() < 0.3 * (1.0 - smooth(0.0, 0.2, hz)) + 0.07:
                continue  # dying/missing branches (gaps), more at the bottom of the crown
            zz = z if lscale == 1.0 else z + rng.uniform(0.15, 0.4)
            reach = R(zz) * rng.uniform(0.6, 1.1) * lscale * (1.28 if rng.random() < 0.12 else 1.0)
            if reach < 0.25:
                continue
            elev0 = lerp(-0.05, 0.75, hz ** 1.25) + rng.uniform(-0.12, 0.12)
            droop = lerp(0.95, 0.25, hz) * rng.uniform(0.75, 1.2)
            upturn = lerp(0.55, 0.05, hz) * rng.uniform(0.5, 1.2)
            L = reach / max(0.55, math.cos(elev0 - droop * 0.5))
            c = axis(zz)
            start = c + Vector((math.cos(phi), math.sin(phi), 0.0)) * (radius(zz) * 0.6)
            pts = conifer_branch_path(start, phi, L, elev0, droop, upturn, rng, n=4 if L > 1.8 else 3)
            r0 = min(0.13, 0.012 + 0.022 * L)
            radii = [r0 * f for f in ((1.0, 0.62, 0.36, 0.18) if len(pts) == 4 else (1.0, 0.5, 0.2))]
            wind0 = 0.12 + 0.2 * hz
            hidden = hz > 0.55 and L < 2.0
            br = Branch(pts=pts, radii=radii, mat=bark, wind0=wind0, wind1=0.55, tip=False,
                        sides=(0 if hidden else (4 if L > 2.6 else (3 if L > 1.1 else 0)), 3, 0),
                        min_len_lod=(1.1, 2.3, 99.0))
            tree.branches.append(br)
            _fir_branch_cards(tree, br, rng, hz, sprays, dens, atlas)
        z += rng.uniform(0.55, 0.88) * lerp(1.0, 0.6, hz)
        k += 1
    # a few straggling live branches below the crown base soften the transition
    for i in range(rng.randint(3, 6)):
        zz = z_cb - rng.uniform(0.3, 2.8)
        phi = rng.uniform(0, 2 * math.pi)
        reach = R(z_cb) * rng.uniform(0.35, 0.75)
        L = reach / 0.8
        c = axis(zz)
        start = c + Vector((math.cos(phi), math.sin(phi), 0.0)) * (radius(zz) * 0.6)
        pts = conifer_branch_path(start, phi, L, rng.uniform(-0.25, 0.05), rng.uniform(0.6, 1.0), 0.3, rng, n=3)
        r0 = 0.012 + 0.02 * L
        br = Branch(pts=pts, radii=[r0, r0 * 0.5, r0 * 0.2], mat=bark, wind0=0.1, wind1=0.5, tip=False,
                    sides=(3, 3, 0), min_len_lod=(0.5, 1.5, 99.0))
        tree.branches.append(br)
        _fir_branch_cards(tree, br, rng, 0.0, sprays, dens * 0.45, atlas)
    # ---- leader / top ------------------------------------------------------------------------
    top = axis(H - 0.25)
    for i in range(6):
        a = i * GOLDEN + rng.uniform(-0.2, 0.2)
        zz = H - rng.uniform(0.3, 1.4)
        c = axis(zz)
        d = Vector((math.cos(a) * 0.5, math.sin(a) * 0.5, 1.0)).normalized()
        ln = rng.uniform(0.45, 0.7)
        tree.cards[0].append(Card(base=c, direction=d, side=Vector((-math.sin(a), math.cos(a), 0.0)), length=ln,
                                  width=ln * _aspect(atlas, "spray_b"), region="spray_b", droop=0.02, segs=2,
                                  wind0=0.4, wind1=1.0, prio=1.5))
        if i < 3:
            tree.cards[1].append(Card(base=c, direction=d, side=Vector((-math.sin(a), math.cos(a), 0.0)),
                                      length=ln * 1.2, width=ln * 1.2 * _aspect(atlas, "spray_b"), region="spray_b",
                                      droop=0.02, segs=1, wind0=0.4, wind1=1.0, prio=1.5))
    tree.cards[0].append(Card(base=top, direction=UP, side=Vector((1, 0, 0)), length=0.6,
                              width=0.3, region="spray_b", droop=0.0, segs=1, wind0=0.5, wind1=1.0, prio=1.6))
    tree.cards[2].append(Card(base=axis(H - 2.2), direction=UP, side=Vector((1, 0, 0)), length=2.3,
                              width=1.0, region="branch", droop=0.0, segs=1, wind0=0.5, wind1=1.0, prio=1.6))
    tree.cards[2].append(Card(base=axis(H - 2.2), direction=UP, side=Vector((0, 1, 0)), length=2.3,
                              width=1.0, region="branch", droop=0.0, segs=1, wind0=0.5, wind1=1.0, prio=1.6))
    # ---- dead lower branches ----------------------------------------------------------------------
    dead_branches(rng, tree, axis, radius, 1.4, z_cb + 0.4, int(H * 2.2), bark, max_len=min(2.6, Rmax * 0.65),
                  long_frac=0.3)
    return tree


def _fir_branch_cards(tree, br, rng, hz, sprays, dens, atlas):
    L = br.length
    spray_len = max(0.55, min(1.35, 0.35 * L + 0.5)) * lerp(1.0, 0.72, hz)
    s0 = max(0.12, min(0.5, 1.0 - 2.4 / max(L, 0.1)))
    step = rng.uniform(0.3, 0.4) / max(L, 0.3) / dens
    s = s0 + rng.uniform(0.0, step)
    while s < 0.97:
        pnt, t, r = br.at(s)
        th = horiz(t)
        for sd in (1, -1):
            if rng.random() > 0.88:
                continue
            yaw = sd * rng.uniform(0.6, 1.1) * lerp(1.0, 0.75, s)
            d = rot_axis(t, UP, yaw)
            d.z -= rng.uniform(0.3, 1.0) * lerp(0.45, 0.1, hz)
            d.normalize()
            ln = spray_len * rng.uniform(0.75, 1.12) * lerp(0.85, 1.0, s)
            reg = sprays[rng.randrange(len(sprays))]
            side = rot_axis(UP.cross(horiz(d)), d, rng.gauss(0.0, 0.38))
            tree.cards[0].append(Card(base=pnt, direction=d, side=side, length=ln, width=ln * _aspect(atlas, reg),
                                      region=reg, droop=rng.uniform(0.08, 0.3), fold=0.0,
                                      segs=2, wind0=lerp(br.wind0, br.wind1, s), wind1=1.0,
                                      prio=0.4 + 0.5 * s + rng.uniform(0.0, 0.25)))
        # hanging spray under the branch (fills the side view, darker)
        if hz < 0.8 and L > 1.1 and rng.random() < 0.3:
            d = (t * 0.45 + Vector((0, 0, -1.0))).normalized()
            ln = spray_len * rng.uniform(0.7, 0.95)
            tree.cards[0].append(Card(base=pnt, direction=d, side=UP.cross(th), length=ln,
                                      width=ln * _aspect(atlas, "spray_c"), region="spray_c", droop=0.0, segs=2,
                                      wind0=lerp(br.wind0, br.wind1, s), wind1=1.0, prio=0.35 + rng.uniform(0, 0.2),
                                      shade=0.8))
        s += step * rng.uniform(0.8, 1.2)
    # terminal spray
    pnt, t, r = br.at(1.0)
    d = (t + Vector((0, 0, -0.1))).normalized()
    ln = spray_len * rng.uniform(1.0, 1.25)
    tree.cards[0].append(Card(base=pnt - t * (ln * 0.15), direction=d, side=rot_axis(UP.cross(horiz(d)), d, rng.gauss(0, 0.25)),
                              length=ln, width=ln * _aspect(atlas, "spray_a"), region="spray_a", droop=0.15, fold=-0.16,
                              segs=2, wind0=br.wind1, wind1=1.0, prio=1.2))
    # LOD1: whole-branch cards (+ crossed one for big branches) and the terminal spray
    b0 = s0 * 0.6
    pnt, t, r = br.at(b0)
    tip, tt, _ = br.at(1.0)
    dvec = (tip - pnt)
    ln1 = dvec.length + spray_len * 0.6
    d1 = dvec.normalized()
    roll = rng.gauss(0.0, 0.3)
    vol = Card(base=pnt, direction=d1, side=rot_axis(UP.cross(horiz(d1)), d1, roll), length=ln1,
               width=ln1 * 0.95, region="branch", droop=0.12, segs=2, wind0=br.wind0, wind1=1.0,
               prio=0.6 + 0.2 * min(1.0, L / 3.0))
    tree.cards[1].append(vol)
    tree.cards[0].append(Card(**{**vol.__dict__, "prio": 2.0, "shade": 0.85, "length": ln1 * 0.92, "width": ln1 * 0.82,
                                 "twist": rng.uniform(-0.45, 0.45), "droop": 0.18}))
    if L > 1.4:
        cross = Card(base=pnt, direction=d1, side=rot_axis(UP.cross(horiz(d1)), d1, roll + 1.35),
                     length=ln1 * 0.85, width=ln1 * 0.8, region="branch", droop=0.1, segs=2,
                     wind0=br.wind0, wind1=1.0, prio=0.45, shade=0.85)
        tree.cards[1].append(cross)
        tree.cards[0].append(Card(**{**cross.__dict__, "prio": 1.9, "shade": 0.75, "twist": rng.uniform(-0.4, 0.4)}))
    if L > 0.9:
        tree.cards[1].append(Card(base=tip - tt * spray_len * 0.2, direction=(tt + Vector((0, 0, -0.1))).normalized(),
                                  side=UP.cross(horiz(tt)), length=spray_len * 1.2,
                                  width=spray_len * 1.2 * _aspect(atlas, "spray_a"), region="spray_a", droop=0.15,
                                  segs=1, wind0=br.wind1, wind1=1.0, prio=0.3))
    # LOD2: one flat whole-branch card, crossed card on the larger ones
    tree.cards[2].append(Card(base=pnt, direction=d1, side=rot_axis(UP.cross(horiz(d1)), d1, roll * 0.5),
                              length=ln1 * 1.05, width=ln1 * 1.0, region="branch", droop=0.08, segs=1,
                              wind0=br.wind0, wind1=1.0, prio=0.5 + 0.3 * min(1.0, L / 3.0)))
    if L > 1.8:
        tree.cards[2].append(Card(base=pnt, direction=d1, side=rot_axis(UP.cross(horiz(d1)), d1, 1.4),
                                  length=ln1 * 0.9, width=ln1 * 0.8, region="branch", droop=0.05, segs=1,
                                  wind0=br.wind0, wind1=1.0, prio=0.3, shade=0.85))


# ---------------------------------------------------------------------------------------------

# Hollow larch (western-larch-like): tall clean bole, narrow sparse crown of short horizontal
# branches with pendulous twigs.
# ---------------------------------------------------------------------------------------------

def build_larch(p: dict) -> Tree:
    rng = common.rng(p["seed"])
    atlas = p["atlas"]
    H = float(p["height"])
    r_dbh = float(p["dbh_r"])
    z_cb = H * float(p["crown_base"])
    Rmax = H * float(p["crown_r"])
    dens = float(p.get("density", 1.3))
    bark = "bark_larch"
    st, axis, radius = conifer_trunk(rng, H, r_dbh, mat=bark, lean_deg=float(p.get("lean", 1.0)), seed=p["seed"],
                                     flare=0.38, flare_h=0.5, wobble=0.08)
    tree = Tree(name=p["name"], stems=[st], foliage_mat="foliage_larch", atlas=atlas, height=H, crown_base=z_cb,
                seed=int(p["seed"]), moss_dir=rng.uniform(0, 2 * math.pi), moss_height=rng.uniform(1.0, 2.2),
                ao_range=(0.45, 1.0), trunk_ao_crown=0.7)
    tree.roots = surface_roots(rng, st.lobes, r_dbh, axis, bark, count=rng.randint(3, 5))

    def R(z):
        t = max(0.0, min(1.0, (H - z) / max(1e-3, H - z_cb)))
        return Rmax * (t ** 0.8) * (0.8 + 0.2 * smooth(0.0, 0.2, 1.0 - t)) + 0.1

    def profile(z):
        c = axis(z)
        return c.x, c.y, R(z)
    tree.crown = Crown(z_cb - 0.5, H, profile, up_bias=0.35)
    twigs = ("twig_a", "twig_b", "twig_c", "twig_d")
    z = z_cb + rng.uniform(0.0, 0.3)
    while z < H - 0.45:
        hz = (z - z_cb) / max(1e-3, H - z_cb)
        for i in range(rng.choice((1, 2, 2, 3))):
            if rng.random() < 0.12:
                continue
            phi = rng.uniform(0, 2 * math.pi)
            reach = R(z) * rng.uniform(0.5, 1.08) * (1.35 if rng.random() < 0.1 else 1.0)
            if reach < 0.2:
                continue
            elev0 = lerp(-0.08, 0.45, hz) + rng.uniform(-0.15, 0.12)
            droop = lerp(0.4, 0.12, hz) * rng.uniform(0.7, 1.3)
            upturn = lerp(0.35, 0.05, hz) * rng.uniform(0.5, 1.2)
            L = reach / 0.9
            c = axis(z)
            start = c + Vector((math.cos(phi), math.sin(phi), 0.0)) * (radius(z) * 0.6)
            pts = conifer_branch_path(start, phi, L, elev0, droop, upturn, rng, n=4 if L > 1.4 else 3, wander=0.12)
            r0 = min(0.09, 0.01 + 0.02 * L)
            radii = [r0 * f for f in ((1.0, 0.62, 0.36, 0.18) if len(pts) == 4 else (1.0, 0.5, 0.2))]
            br = Branch(pts=pts, radii=radii, mat=bark, wind0=0.12 + 0.2 * hz, wind1=0.55, tip=False,
                        sides=(4 if L > 1.8 else 3, 3, 0), min_len_lod=(0.35, 1.4, 99.0))
            tree.branches.append(br)
            _larch_branch_cards(tree, br, rng, hz, twigs, dens, atlas)
        z += rng.uniform(0.25, 0.5) * lerp(1.0, 0.7, hz)
    # leader
    for i in range(5):
        a = i * GOLDEN + rng.uniform(-0.2, 0.2)
        c = axis(H - rng.uniform(0.2, 1.3))
        d = Vector((math.cos(a) * 0.45, math.sin(a) * 0.45, 1.0)).normalized()
        ln = rng.uniform(0.4, 0.65)
        tree.cards[0].append(Card(base=c, direction=d, side=Vector((-math.sin(a), math.cos(a), 0.0)), length=ln,
                                  width=ln * _aspect(atlas, "twig_b"), region="twig_b", droop=0.04, segs=2,
                                  wind0=0.4, wind1=1.0, prio=1.5))
        if i < 3:
            tree.cards[1].append(Card(base=c, direction=d, side=Vector((-math.sin(a), math.cos(a), 0.0)),
                                      length=ln * 1.2, width=ln * 1.2 * _aspect(atlas, "twig_b"), region="twig_b",
                                      droop=0.04, segs=1, wind0=0.4, wind1=1.0, prio=1.5))
    for ang in (0.0, math.pi / 2):
        tree.cards[2].append(Card(base=axis(H - 1.8), direction=UP, side=Vector((math.cos(ang), math.sin(ang), 0)),
                                  length=1.9, width=0.9, region="branch", droop=0.0, segs=1, wind0=0.5, wind1=1.0,
                                  prio=1.6))
    dead_branches(rng, tree, axis, radius, 2.0, z_cb + 0.2, int(H * 1.1), bark, atlas_dead=False, long_frac=0.12,
                  max_len=min(1.6, Rmax * 0.6))
    return tree


def _larch_branch_cards(tree, br, rng, hz, twigs, dens, atlas):
    L = br.length
    tl = max(0.5, min(1.1, 0.3 * L + 0.5)) * lerp(1.0, 0.78, hz)
    step = rng.uniform(0.2, 0.28) / max(L, 0.3) / dens
    s = 0.12 + rng.uniform(0.0, step)
    while s < 0.95:
        pnt, t, r = br.at(s)
        th = horiz(t)
        for sd in (1, -1):
            if rng.random() > 0.85:
                continue
            d = rot_axis(t, UP, sd * rng.uniform(0.5, 1.2))
            d.z -= rng.uniform(0.1, 0.45)
            d.normalize()
            reg = twigs[rng.randrange(4)]
            ln = tl * rng.uniform(0.75, 1.2)
            tree.cards[0].append(Card(base=pnt, direction=d, side=rot_axis(UP.cross(horiz(d)), d, rng.gauss(0.0, 0.5)),
                                      length=ln, width=ln * _aspect(atlas, reg), region=reg, droop=rng.uniform(0.1, 0.3),
                                      segs=2, wind0=lerp(br.wind0, br.wind1, s), wind1=1.0,
                                      prio=0.4 + 0.5 * s + rng.uniform(0, 0.25)))
        if rng.random() < 0.75:  # pendulous twig hanging under the branch
            d = (t * 0.25 + Vector((rng.uniform(-0.15, 0.15), rng.uniform(-0.15, 0.15), -1.0))).normalized()
            reg = ("twig_b", "twig_c")[rng.randrange(2)]
            ln = tl * rng.uniform(0.9, 1.35)
            tree.cards[0].append(Card(base=pnt, direction=d, side=rot_axis(UP.cross(th), d, rng.uniform(-0.5, 0.5)),
                                      length=ln, width=ln * _aspect(atlas, reg), region=reg, droop=0.0, segs=2,
                                      wind0=lerp(br.wind0, br.wind1, s), wind1=1.0, prio=0.45 + rng.uniform(0, 0.3),
                                      shade=0.9))
        s += step * rng.uniform(0.8, 1.2)
    pnt, t, r = br.at(1.0)
    d = (t + Vector((0, 0, -0.1))).normalized()
    ln = tl * rng.uniform(1.0, 1.3)
    tree.cards[0].append(Card(base=pnt - t * (ln * 0.15), direction=d, side=UP.cross(horiz(d)), length=ln,
                              width=ln * _aspect(atlas, "twig_a"), region="twig_a", droop=0.12, segs=2,
                              wind0=br.wind1, wind1=1.0, prio=1.2))
    # LOD1 / LOD2 whole-branch cards
    pnt, t, r = br.at(0.08)
    tip, tt, _ = br.at(1.0)
    dvec = tip - pnt
    ln1 = dvec.length + tl * 0.8
    d1 = dvec.normalized()
    roll = rng.gauss(0.0, 0.35)
    vol = Card(base=pnt, direction=d1, side=rot_axis(UP.cross(horiz(d1)), d1, roll), length=ln1, width=ln1 * 1.05,
               region="branch", droop=0.1, segs=2, wind0=br.wind0, wind1=1.0, prio=0.6 + 0.2 * min(1.0, L / 2.5))
    tree.cards[1].append(vol)
    tree.cards[0].append(Card(**{**vol.__dict__, "prio": 2.0, "shade": 0.9}))
    if L > 1.0:
        cross = Card(base=pnt, direction=d1, side=rot_axis(UP.cross(horiz(d1)), d1, roll + 1.4), length=ln1 * 0.85,
                     width=ln1 * 0.8, region="branch", droop=0.08, segs=2, wind0=br.wind0, wind1=1.0, prio=0.45,
                     shade=0.9)
        tree.cards[1].append(cross)
    tree.cards[2].append(Card(base=pnt, direction=d1, side=rot_axis(UP.cross(horiz(d1)), d1, roll * 0.5),
                              length=ln1 * 1.05, width=ln1, region="branch", droop=0.06, segs=1, wind0=br.wind0,
                              wind1=1.0, prio=0.5 + 0.3 * min(1.0, L / 2.5)))
    if L > 1.3:
        tree.cards[2].append(Card(base=pnt, direction=d1, side=rot_axis(UP.cross(horiz(d1)), d1, 1.45),
                                  length=ln1 * 0.9, width=ln1 * 0.8, region="branch", droop=0.04, segs=1,
                                  wind0=br.wind0, wind1=1.0, prio=0.3, shade=0.9))


# ---------------------------------------------------------------------------------------------
# Paper birch: 1-3 slender leaning stems from one base, ascending arching branches, rounded
# airy crown of leaf clusters.
# ---------------------------------------------------------------------------------------------

def birch_stem(rng, base: Vector, H, r_dbh, lean_dir, lean_deg, mat, seed):
    lean = math.radians(lean_deg)
    off = Vector((rng.uniform(0, 40), rng.uniform(0, 40), 0.0))
    d = Vector((math.cos(lean_dir), math.sin(lean_dir), 0.0))
    wob = _wobble_table(seed + 5, off, H + 2.0, 0.08, 0.35)

    def axis(z):
        zz = max(0.0, z)
        # leans out, then curves back up (phototropic sweep)
        lateral = math.tan(lean) * (zz - 0.35 * zz * zz / max(H, 1.0))
        wx, wy = wob(zz)
        wx *= smooth(0.0, 2.0, zz)
        wy *= smooth(0.0, 2.0, zz)
        return Vector((base.x + d.x * lateral + wx, base.y + d.y * lateral + wy, z))

    def radius(z):
        core = r_dbh * max(0.0, (H - z) / (H - 1.3)) ** 0.85 if z >= 1.3 else r_dbh * (1.0 + 0.04 * (1.3 - z))
        return max(0.01, core + r_dbh * 0.28 * math.exp(-(max(z, -0.3) + 0.1) / 0.4))

    zs = [-0.25, 0.0, 0.2, 0.5, 0.9, 1.4]
    z = 2.0
    while z < H - 0.8:
        zs.append(z)
        z += rng.uniform(0.9, 1.4)
    zs += [H - 0.45]
    n = rng.randint(3, 5)
    a0 = rng.uniform(0, 2 * math.pi)
    lobes = [(a0 + 2 * math.pi * i / n + rng.uniform(-0.4, 0.4), rng.uniform(0.1, 0.25)) for i in range(n)]
    st = Stem(pts=[axis(z) for z in zs], radii=[radius(z) for z in zs], mat=mat, lobes=lobes, lobe_height=0.45,
              u_repeats=max(1, round(2 * math.pi * r_dbh / 0.6)), noise_seed=seed, noise_amp=0.01,
              sides=(10, 7, 5), keep_all_below=1.0)
    return st, axis, radius


def build_birch(p: dict) -> Tree:
    rng = common.rng(p["seed"])
    atlas = p["atlas"]
    H = float(p["height"])
    r_dbh = float(p["dbh_r"])
    nst = int(p.get("stems", 2))
    dens = float(p.get("density", 1.3))
    bark = "bark_birch"
    tree = Tree(name=p["name"], stems=[], foliage_mat="foliage_birch", atlas=atlas, height=H, crown_base=H * 0.45,
                seed=int(p["seed"]), moss_dir=rng.uniform(0, 2 * math.pi), moss_height=rng.uniform(0.8, 1.4),
                ao_range=(0.42, 1.0), trunk_ao_crown=0.75, normal_bend=(0.55, 0.65, 0.8))
    a0 = rng.uniform(0, 2 * math.pi)
    stems = []
    for i in range(nst):
        ang = a0 + 2 * math.pi * i / nst + rng.uniform(-0.4, 0.4)
        off = 0.0 if nst == 1 else rng.uniform(0.07, 0.13)
        base = Vector((math.cos(ang) * off, math.sin(ang) * off, 0.0))
        Hi = H * (1.0 if i == 0 else rng.uniform(0.74, 0.92))
        ri = r_dbh * (1.0 if i == 0 else rng.uniform(0.72, 0.9))
        lean = rng.uniform(2.0, 5.0) if nst == 1 else rng.uniform(5.0, 12.0)
        st, axis, radius = birch_stem(rng, base, Hi, ri, ang, lean, bark, int(p["seed"]) + i * 7)
        tree.stems.append(st)
        stems.append((st, axis, radius, Hi, ri, ang))
    # crown envelope: ellipsoid around the upper stems
    tops = [ax(Hi * 0.9) for _, ax, _, Hi, _, _ in stems]
    cx = sum(t.x for t in tops) / len(tops)
    cy = sum(t.y for t in tops) / len(tops)
    z0c, z1c = H * 0.38, H * 1.02
    zc = (z0c + z1c) * 0.5
    hc = (z1c - z0c) * 0.5
    Rc = H * float(p.get("crown_r", 0.2)) + (0.6 if nst > 1 else 0.0)

    def R(z):
        q = max(0.0, 1.0 - ((z - zc) / hc) ** 2)
        return max(0.35, Rc * math.sqrt(q))

    tree.crown = Crown(z0c, z1c, lambda z: (cx, cy, R(z)), up_bias=0.3)
    clusters = ("cluster_a", "cluster_b", "cluster_c")
    for st, axis, radius, Hi, ri, sang in stems:
        z = Hi * rng.uniform(0.36, 0.44)
        while z < Hi * 0.93:
            hz = (z - Hi * 0.4) / (Hi * 0.55)
            for _ in range(rng.choice((1, 1, 2))):
                # branches grow away from the clump centre
                phi = sang + rng.gauss(0.0, 1.1) if nst > 1 else rng.uniform(0, 2 * math.pi)
                c = axis(z)
                start = c + Vector((math.cos(phi), math.sin(phi), 0.0)) * radius(z) * 0.6
                reach = max(0.5, R(z) * rng.uniform(0.65, 1.05) - Vector((c.x - cx, c.y - cy, 0)).length * 0.5)
                elev0 = math.radians(rng.uniform(35, 62)) + 0.2 * hz
                droop = rng.uniform(0.5, 0.95)
                L = reach / max(0.45, math.cos(elev0 - droop * 0.6))
                pts = conifer_branch_path(start, phi, L, elev0, droop, 0.0, rng, n=4, wander=0.15)
                r0 = min(ri * 0.45, 0.012 + 0.016 * L)
                br = Branch(pts=pts, radii=[r0, r0 * 0.65, r0 * 0.4, r0 * 0.18], mat=bark, wind0=0.15 + 0.15 * hz,
                            wind1=0.6, tip=False, sides=(4 if L > 2.2 else 3, 3, 0), min_len_lod=(0.0, 1.6, 99.0))
                tree.branches.append(br)
                subs = [br]
                for k in range(rng.randint(1, 3) if L > 1.4 else 0):
                    sp, stt, sr = br.at(rng.uniform(0.3, 0.75))
                    sphi = math.atan2(stt.y, stt.x) + rng.choice((-1, 1)) * rng.uniform(0.5, 1.0)
                    sl = L * rng.uniform(0.3, 0.5)
                    spts = conifer_branch_path(sp, sphi, sl, rng.uniform(0.1, 0.6), rng.uniform(0.5, 0.9), 0.0, rng,
                                               n=3, wander=0.2)
                    sb = Branch(pts=spts, radii=[sr * 0.7, sr * 0.4, sr * 0.15], mat=bark, wind0=0.3, wind1=0.7,
                                tip=False, sides=(3, 0, 0), min_len_lod=(0.0, 99, 99))
                    tree.branches.append(sb)
                    subs.append(sb)
                _birch_cards(tree, br, subs, rng, clusters, dens, atlas)
            z += rng.uniform(0.35, 0.7)
        # top of each stem
        top = axis(Hi - 0.45)
        for i in range(3):
            a = i * 2.1 + rng.uniform(-0.3, 0.3)
            d = Vector((math.cos(a) * 0.6, math.sin(a) * 0.6, 1.0)).normalized()
            ln = rng.uniform(0.6, 0.9)
            tree.cards[0].append(Card(base=top, direction=d, side=Vector((-math.sin(a), math.cos(a), 0)), length=ln,
                                      width=ln, region=clusters[i % 3], droop=0.1, segs=2, wind0=0.4, wind1=1.0,
                                      prio=1.5))
            tree.cards[1].append(Card(base=top, direction=d, side=Vector((-math.sin(a), math.cos(a), 0)), length=ln * 1.3,
                                      width=ln * 1.3, region="branch", droop=0.1, segs=1, wind0=0.4, wind1=1.0, prio=1.5))
            if i < 2:
                tree.cards[2].append(Card(base=top, direction=d, side=Vector((-math.sin(a), math.cos(a), 0)),
                                          length=ln * 1.5, width=ln * 1.5, region="branch", droop=0.05, segs=1,
                                          wind0=0.4, wind1=1.0, prio=1.5))
        # a few dead twigs low on the stem
        for k in range(rng.randint(3, 7)):
            z = rng.uniform(1.5, Hi * 0.4)
            phi = rng.uniform(0, 2 * math.pi)
            c = axis(z)
            d = Vector((math.cos(phi), math.sin(phi), rng.uniform(-0.2, 0.3))).normalized()
            Ls = rng.uniform(0.08, 0.5)
            r0 = rng.uniform(0.008, 0.02)
            tree.branches.append(Branch(pts=[c + d * radius(z) * 0.6, c + d * (radius(z) + Ls)], radii=[r0, r0 * 0.5],
                                        mat=bark, wind0=0.05, wind1=0.1, sides=(3, 0, 0), min_len_lod=(0.0, 99, 99)))
    return tree


def _birch_cards(tree, br, subs, rng, clusters, dens, atlas):
    L = br.length
    cl = max(0.45, min(0.85, 0.2 * L + 0.35))
    for b in subs:
        bl = b.length
        step = rng.uniform(0.28, 0.38) / max(bl, 0.3) / dens
        s = 0.3 + rng.uniform(0.0, step)
        while s < 1.0:
            pnt, t, r = b.at(min(s, 1.0))
            for _ in range(2 if s > 0.6 else 1):
                axis_t = t.normalized()
                d = rot_axis(axis_t, UP, rng.uniform(-1.2, 1.2))
                d.z += rng.uniform(-0.6, 0.5)
                d.normalize()
                side = rot_axis(UP.cross(horiz(d)), d, rng.gauss(0.0, 0.6))
                ln = cl * rng.uniform(0.75, 1.15)
                tree.cards[0].append(Card(base=pnt, direction=d, side=side, length=ln, width=ln,
                                          region=clusters[rng.randrange(3)], droop=rng.uniform(0.08, 0.25), segs=2,
                                          wind0=lerp(b.wind0, b.wind1, s), wind1=1.0,
                                          prio=0.4 + 0.5 * s + rng.uniform(0, 0.3)))
            s += step * rng.uniform(0.8, 1.2)
        pnt, t, r = b.at(1.0)
        d = (t + Vector((0, 0, -0.15))).normalized()
        ln = cl * rng.uniform(0.95, 1.2)
        tree.cards[0].append(Card(base=pnt - t * ln * 0.2, direction=d, side=UP.cross(horiz(d)), length=ln, width=ln,
                                  region=clusters[rng.randrange(3)], droop=0.15, segs=2, wind0=b.wind1, wind1=1.0,
                                  prio=1.2))
    # LOD1 / LOD2: whole-branch cards along the primary
    pnt, t, r = br.at(0.25)
    tip, tt, _ = br.at(1.0)
    dvec = tip - pnt
    ln1 = dvec.length + cl * 0.6
    d1 = dvec.normalized()
    roll = rng.gauss(0.0, 0.5)
    vol = Card(base=pnt, direction=d1, side=rot_axis(UP.cross(horiz(d1)), d1, roll), length=ln1, width=ln1 * 0.95,
               region="branch", droop=0.12, segs=2, wind0=br.wind0, wind1=1.0, prio=0.7)
    tree.cards[1].append(vol)
    tree.cards[1].append(Card(base=pnt, direction=d1, side=rot_axis(UP.cross(horiz(d1)), d1, roll + 1.4),
                              length=ln1 * 0.9, width=ln1 * 0.85, region="branch", droop=0.1, segs=2, wind0=br.wind0,
                              wind1=1.0, prio=0.5, shade=0.9))
    tree.cards[0].append(Card(**{**vol.__dict__, "prio": 1.8, "shade": 0.85}))
    for b in subs:
        bp, bt, _ = b.at(1.0)
        d = (bt + Vector((0, 0, -0.1))).normalized()
        ln = cl * 1.25
        tree.cards[1].append(Card(base=bp - bt * ln * 0.3, direction=d, side=rot_axis(UP.cross(horiz(d)), d, rng.gauss(0, 0.5)),
                                  length=ln, width=ln, region=clusters[rng.randrange(3)], droop=0.12, segs=1,
                                  wind0=b.wind1, wind1=1.0, prio=0.6))
    tree.cards[2].append(Card(base=pnt, direction=d1, side=rot_axis(UP.cross(horiz(d1)), d1, roll), length=ln1 * 1.15,
                              width=ln1 * 1.1, region="branch", droop=0.06, segs=1, wind0=br.wind0, wind1=1.0, prio=0.6))
    tree.cards[2].append(Card(base=pnt, direction=d1, side=rot_axis(UP.cross(horiz(d1)), d1, roll + 1.45),
                              length=ln1 * 1.05, width=ln1, region="branch", droop=0.04, segs=1, wind0=br.wind0,
                              wind1=1.0, prio=0.4, shade=0.9))


# ---------------------------------------------------------------------------------------------
# Dead snag: dead conifer with a broken, splintered top and a few bare grey branches.
# ---------------------------------------------------------------------------------------------

def _jagged_top(rng, mat, spikes=(2, 3)):
    def fn(mb, ring, pts, lod, v_end):
        m = mb.mat(mat)
        n = len(ring)
        center = pts[-1]
        rr = [(Vector(mb.co[i]) - center) for i in ring]
        rad = sum(v.length for v in rr) / n
        tall = set(rng.sample(range(n), min(n, rng.randint(*spikes)))) if lod == 0 else set(range(0, n, max(1, n // 2)))
        hs = []
        for j in range(n):
            h = rng.uniform(0.05, 0.35) * rad * 3.0
            if j in tall:
                h = rng.uniform(0.6, 1.6) * (1.0 if lod == 0 else 0.8)
            hs.append(h)
        u_rep = 2.0
        rows = [ring]
        nrows = 2 if lod == 0 else 1
        for k in range(1, nrows + 1):
            f = k / nrows
            row = []
            for j in range(n):
                inward = rng.uniform(0.15, 0.4) * f if j not in tall else 0.25 * f
                q = center + rr[j] * (1.0 - inward) + Vector((0, 0, hs[j] * f))
                q += Vector((rng.uniform(-0.02, 0.02), rng.uniform(-0.02, 0.02), 0.0))
                row.append(mb.v(q, (0.75, 0.0, 0.0, 0.2)))
            rows.append(row)
        for k in range(len(rows) - 1):
            for j in range(n):
                j2 = (j + 1) % n
                u0, u1 = u_rep * j / n, u_rep * (j + 1) / n
                va, vb = v_end + k * 0.3, v_end + (k + 1) * 0.3
                mb.f((rows[k][j], rows[k][j2], rows[k + 1][j2], rows[k + 1][j]),
                     ((u0, va), (u1, va), (u1, vb), (u0, vb)), m)
        # broken heartwood surface: jagged fan to a low centre
        c = mb.v(center + Vector((0, 0, min(hs) * 0.4)), (0.6, 0.0, 0.0, 0.2))
        top = rows[-1]
        for j in range(n):
            j2 = (j + 1) % n
            a = Vector(mb.co[top[j]]) - center
            b = Vector(mb.co[top[j2]]) - center
            mb.f((top[j], top[j2], c), ((0.5 + a.x, 0.5 + a.y), (0.5 + b.x, 0.5 + b.y), (0.5, 0.5)), m)
    return fn


def build_snag(p: dict) -> Tree:
    rng = common.rng(p["seed"])
    H = float(p["height"])
    r_dbh = float(p["dbh_r"])
    H_full = H * float(p.get("full_height", 1.7))
    bark = "bark_dead"
    st, axis, radius = conifer_trunk(rng, H_full, r_dbh, mat=bark, lean_deg=float(p.get("lean", 3.0)),
                                     seed=p["seed"], z_end=H, flare=0.5, wobble=0.07)
    st.tip = False
    st.break_top = _jagged_top(rng, bark)
    st.noise_amp = 0.02
    tree = Tree(name=p["name"], stems=[st], foliage_mat="foliage_fir", atlas={}, height=H, crown_base=H * 2.0,
                seed=int(p["seed"]), moss_dir=rng.uniform(0, 2 * math.pi), moss_height=rng.uniform(1.0, 2.0),
                trunk_ao_crown=1.0)
    tree.roots = surface_roots(rng, st.lobes, r_dbh, axis, bark, count=rng.randint(4, 6))
    # a few bare dead branches, longer ones higher up, some broken short
    for k in range(rng.randint(6, 11)):
        z = H * rng.uniform(0.35, 0.95)
        phi = rng.uniform(0, 2 * math.pi)
        broken = rng.random() < 0.4
        L = rng.uniform(0.6, 1.2) if broken else rng.uniform(1.2, 3.2) * (1.0 - 0.4 * (z / H))
        c = axis(z)
        start = c + Vector((math.cos(phi), math.sin(phi), 0.0)) * radius(z) * 0.6
        pts = conifer_branch_path(start, phi, L, rng.uniform(-0.4, 0.25), rng.uniform(0.0, 0.4), rng.uniform(0, 0.3),
                                  rng, n=4, wander=0.25)
        r0 = min(0.12, 0.03 + 0.026 * L)
        br = Branch(pts=pts, radii=[r0, r0 * 0.7, r0 * 0.48, r0 * (0.4 if broken else 0.2)], mat=bark, wind0=0.05,
                    wind1=0.25, tip=not broken, sides=(5 if L > 2 else 4, 3, 3 if L > 2.4 else 0),
                    min_len_lod=(0.0, 0.9, 2.4), broken=broken)
        tree.branches.append(br)
        if not broken:
            for j in range(rng.randint(1, 3)):
                sp, stt, sr = br.at(rng.uniform(0.3, 0.8))
                sphi = math.atan2(stt.y, stt.x) + rng.choice((-1, 1)) * rng.uniform(0.5, 1.2)
                sl = L * rng.uniform(0.25, 0.45)
                spts = conifer_branch_path(sp, sphi, sl, rng.uniform(-0.3, 0.5), 0.2, 0.0, rng, n=3, wander=0.3)
                tree.branches.append(Branch(pts=spts, radii=[sr * 0.6, sr * 0.35, sr * 0.15], mat=bark, wind0=0.1,
                                            wind1=0.3, sides=(3, 0, 0), min_len_lod=(0.0, 99, 99)))
    dead_branches(rng, tree, axis, radius, 1.2, H * 0.9, int(H * 2.4), bark, atlas_dead=False, long_frac=0.18,
                  max_len=1.4)
    return tree


# ---------------------------------------------------------------------------------------------

BUILDERS = {"fir": build_fir, "larch": build_larch, "birch": build_birch, "snag": build_snag}


def build(params: dict, outputs: list[str]) -> None:
    tree = BUILDERS[params["species"]](params)
    rng = common.rng(str(params["seed"]) + "lod")
    names = [tree.name, tree.name + "_lod1", tree.name + "_lod2"]
    objs = []
    for lod, name in enumerate(names[:len(outputs)]):
        mb = assemble(tree, lod, rng)
        obj = mb.build(name)
        objs.append(obj)
        print(f"[veg_tree] {name}: {mb.tris()} tris")
    for obj, out in zip(objs, outputs):
        export.export_glb(out, [obj])
