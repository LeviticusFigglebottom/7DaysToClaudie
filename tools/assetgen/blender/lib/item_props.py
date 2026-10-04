"""Reusable small-prop shapes for the item / structure families (cans, bottles, nails, planks, discs).
All builders add into an item_kit.MB at the current transform; origin = bottom centre, axis +Z."""
from __future__ import annotations

import math

from mathutils import Matrix, Vector, noise

from . import common
from . import item_kit as K


def _dent_fn(seed: int, dents: float, R: float, H: float):
    r = common.rng(seed)
    ds = []
    for _ in range(int(math.ceil(dents * 2))):
        ds.append((r.uniform(0, math.tau), r.uniform(0.25, 0.75) * H, r.uniform(0.25, 0.5), r.uniform(0.012, 0.02),
                   r.uniform(0.04, 0.09) * dents))

    def fn(k, i, rr, z, seg=24):
        if z < 0.012 or z > H - 0.012:
            return 1.0
        a = 2 * math.pi * k / seg
        m = 1.0
        for (a0, z0, w, h, d) in ds:
            da = math.atan2(math.sin(a - a0), math.cos(a - a0))
            m -= d * math.exp(-(da / w) ** 2 - ((z - z0) / h) ** 2)
        return m
    return fn


def can(mb: K.MB, R: float, H: float, *, label: str | None = "item_can_label_a", seed: int = 0, dent: float = 0.0,
        segments: int = 24, state: str = "sealed", contents: str | None = None, beads: bool | None = None,
        simple: bool = False) -> dict:
    """Food can (tinplate, double seams). state: 'sealed' | 'open' (lid cut out, rim left) | 'open_full'
    (open with contents surface). Returns info dict (rim height etc.)."""
    tin = "item_can_tin"
    bottom = [(R * 0.78, 0.0032), (R * 0.88, 0.0026), (R * 0.93, 0.0013), (R * 0.975, 0.0), (R * 1.008, 0.0016),
              (R * 1.013, 0.0052), (R * 0.998, 0.0078)]
    beads = (label is None) if beads is None else beads
    body = []
    nb = 1 if simple else 9
    for j in range(nb + 1):
        z = 0.0095 + (H - 0.019) * j / nb
        rr = R * 1.002
        body.append((rr, z))
    if beads:
        body = []
        nbz = 8
        for j in range(nbz * 2 + 1):
            z = 0.0095 + (H - 0.019) * j / (nbz * 2)
            rr = R * (0.995 if j % 2 == 1 and 1 < j < nbz * 2 - 1 else 1.002)
            body.append((rr, z))
    top_seam = [(R * 0.998, H - 0.0078), (R * 1.013, H - 0.0052), (R * 1.008, H - 0.0016), (R * 0.985, H)]
    if state == "sealed":
        top = [(R * 0.956, H - 0.0006), (R * 0.946, H - 0.0042), (R * 0.87, H - 0.0036), (R * 0.83, H - 0.0027), (R * 0.79, H - 0.0036),
               (R * 0.5, H - 0.0038)]
    elif state == "open":
        top = [(R * 0.958, H - 0.0012), (R * 0.952, H - 0.0045), (R * 0.968, H - 0.008)] + \
              [(R * 0.968, z) for z in ((0.012,) if simple else (H * 0.5, 0.012))] + [(R * 0.94, 0.0062), (R * 0.6, 0.0058)]
    else:  # open_full
        top = [(R * 0.958, H - 0.0012), (R * 0.952, H - 0.0045), (R * 0.968, H - 0.008), (R * 0.966, H - 0.0135),
               (R * 0.9, H - 0.0128), (R * 0.6, H - 0.0118), (R * 0.3, H - 0.0112)]
    prof = bottom + body + top_seam + top
    i_label0 = len(bottom)
    i_label1 = len(bottom) + len(body) - 1
    regions = []
    if label is not None:
        regions.append((i_label0, i_label1, label, "label"))
    if state == "open_full" and contents:
        n = len(prof)
        regions.append((n - 4, n - 1, contents, "metric"))
    fn = _dent_fn(seed, dent, R, H) if dent > 0 else None
    K.lathe(mb, prof, segments=segments, mat=tin, regions=regions, cap_bottom=True, cap_top=True,
            cap_mat_top=(contents if (state == "open_full" and contents) else tin), u_tile=None,
            radial_fn=(lambda k, i, rr, z: fn(k, i, rr, z, segments)) if fn else None, angle0=common.rng(seed).uniform(0, 6.28))
    return {"rim": H}


def jagged_disc(mb: K.MB, radius: float, thickness: float, *, segments: int = 20, mat: str = "item_can_tin", jag: float = 0.0,
                seed: int = 0, uv_scale: float = 1.0) -> None:
    """Thin disc in the XY plane centred at the origin (z from 0 to thickness), optional jagged rim."""
    r = common.rng(seed)
    pts = []
    for k in range(segments):
        a = 2 * math.pi * k / segments
        rr = radius * (1 - jag * r.random())
        pts.append((rr * math.cos(a), rr * math.sin(a)))
    mb.push(Matrix.Translation((0, 0, thickness / 2)))
    K.extrude(mb, pts, thickness, mat=mat, uv_scale=uv_scale)
    mb.pop()


def soda_can(mb: K.MB, *, seed: int = 0, label: str = "item_can_label_d", segments: int = 24, opened: bool = False) -> None:
    R, H = 0.0331, 0.1225
    prof = [(R * 0.55, 0.0068), (R * 0.68, 0.0034), (R * 0.80, 0.0006), (R * 0.86, 0.0), (R * 0.93, 0.0022), (R * 0.985, 0.0075),
            (R, 0.012)]
    body = [(R, 0.012 + (0.098 - 0.012) * j / 8) for j in range(9)]
    neck = [(R * 0.96, 0.106), (R * 0.88, 0.1135), (R * 0.82, 0.1185), (R * 0.815, 0.1210), (R * 0.835, 0.1225),
            (R * 0.80, H), (R * 0.765, H - 0.0006), (R * 0.75, H - 0.0055), (R * 0.4, H - 0.0055)]
    prof = prof + body + neck
    i0 = 6
    i1 = 6 + len(body) - 1
    K.lathe(mb, prof, segments=segments, mat="item_aluminium", regions=[(i0, i1, label, "label")], cap_bottom=True, cap_top=True,
            angle0=common.rng(seed).uniform(0, 6.28))
    # pull tab + rivet
    z = H - 0.0055
    tab = [(-0.0065, -0.0105), (0.0065, -0.0105), (0.0085, -0.004), (0.0085, 0.006), (0.004, 0.0105), (-0.004, 0.0105), (-0.0085, 0.006),
           (-0.0085, -0.004)]
    hole = [(-0.0045, 0.0015), (0.0045, 0.0015), (0.0045, 0.0075), (-0.0045, 0.0075)]
    mb.push(Matrix.Translation((0, -0.002, z + 0.0006)))
    K.extrude(mb, tab, 0.0007, holes=[hole], mat="item_aluminium", uv_scale=10.0)
    mb.pop()
    mb.push(Matrix.Translation((0, -0.009, z)))
    K.lathe(mb, [(0.0018, 0.0), (0.0016, 0.0009)], segments=8, mat="item_aluminium", cap_bottom=False)
    mb.pop()
    if opened:
        mb.push(Matrix.Translation((0, -0.017, z + 0.0002)))
        K.extrude(mb, [(-0.0055, -0.004), (0.0055, -0.004), (0.006, 0.002), (0.0, 0.0055), (-0.006, 0.002)], 0.0004, mat="item_rubber")
        mb.pop()


def pet_bottle(mb: K.MB, *, fill: float = 0.0, water: str = "item_bottle_water", seed: int = 0, crush: float = 0.0,
               segments: int = 20) -> None:
    """0.5 l PET water bottle with ribs, label sleeve, shoulder, neck ring and ribbed cap."""
    R = 0.0325
    prof = [(R * 0.35, 0.0045), (R * 0.6, 0.0015), (R * 0.82, 0.0), (R * 0.96, 0.004), (R, 0.012)]
    for j in range(10):
        z = 0.016 + j * 0.0052
        prof.append((R * (0.975 if j % 2 == 0 else 1.0), z))
    label0 = len(prof)
    prof += [(R * 1.004, 0.070), (R * 1.004, 0.095), (R * 1.004, 0.120)]
    label1 = len(prof) - 1
    for j in range(5):
        z = 0.124 + j * 0.005
        prof.append((R * (0.975 if j % 2 == 0 else 1.0), z))
    prof += [(R * 0.97, 0.150), (R * 0.88, 0.162), (R * 0.70, 0.172), (R * 0.52, 0.180), (0.0135, 0.186), (0.0135, 0.190),
             (0.0172, 0.1905), (0.0172, 0.1925), (0.0132, 0.193)]
    cap0 = len(prof)
    prof += [(0.0152, 0.1932), (0.0156, 0.195), (0.0156, 0.207), (0.0148, 0.2085), (0.008, 0.2088)]
    regions = [(label0, label1, "item_plastic_blue", "label"), (cap0 - 1, len(prof) - 1, "item_plastic_blue", "metric")]
    fill_z = 0.004 + fill * 0.17
    if fill > 0:
        for i in range(len(prof) - 1):
            if prof[i + 1][1] <= fill_z and not (label0 <= i < label1):
                regions.append((i, i + 1, water, "metric"))
    fn = None
    if crush > 0:
        rr = common.rng(seed)
        a0 = rr.uniform(0, 6.28)
        z0 = rr.uniform(0.06, 0.12)

        def fn(k, i, r_, z):
            if z > 0.15 or z < 0.01:
                return 1.0
            a = 2 * math.pi * k / segments
            da = math.atan2(math.sin(a - a0), math.cos(a - a0))
            return 1.0 - crush * (math.exp(-(da / 0.6) ** 2 - ((z - z0) / 0.03) ** 2) + 0.4 * math.exp(-((da - 2.6) / 0.5) ** 2 - ((z - z0 - 0.03) / 0.02) ** 2))
    K.lathe(mb, prof, segments=segments, mat="item_plastic_clear", regions=regions, cap_bottom=True, cap_top=True,
            cap_mat_top="item_plastic_blue", radial_fn=fn)


def glass_bottle(mb: K.MB, *, mat: str = "item_glass_brown", segments: int = 20, label: str | None = None) -> None:
    """Long-neck beer bottle (opaque-rendered glass) with crown finish and a dark opening."""
    R = 0.031
    prof = [(R * 0.55, 0.006), (R * 0.75, 0.0035), (R * 0.9, 0.0008), (R * 0.97, 0.0), (R, 0.006), (R, 0.06), (R, 0.125),
            (R * 0.97, 0.138), (R * 0.85, 0.152), (R * 0.62, 0.166), (0.0128, 0.182), (0.0124, 0.205), (0.0128, 0.218),
            (0.0139, 0.2215), (0.0141, 0.2255), (0.0132, 0.2285), (0.0095, 0.2287), (0.0093, 0.222), (0.004, 0.2215)]
    regions = []
    if label:
        regions.append((5, 6, label, "label"))
    K.lathe(mb, prof, segments=segments, mat=mat, regions=regions, cap_bottom=True, cap_top=True, cap_mat_top="item_charcoal")


def nail(mb: K.MB, p0, direction, length: float = 0.075, *, d: float = 0.0035, head: float = 0.0068, mat: str = "item_galvanized",
         sides: int = 6, bent: float = 0.0) -> None:
    """A common nail from p0 (under the head) along direction; optional bend near the point."""
    p0 = Vector(p0)
    dv = Vector(direction).normalized()
    side = dv.orthogonal().normalized()
    pts = []
    n = 4 if bent == 0 else 6
    for i in range(n):
        t = i / (n - 1)
        q = p0 + dv * (length * 0.86 * t)
        if bent:
            q += side * bent * length * max(0.0, t - 0.5) ** 2 * 4
        pts.append(q)
    tip = pts[-1] + (pts[-1] - pts[-2]).normalized() * length * 0.14
    K.tube(mb, pts + [tip], [d / 2] * len(pts) + [d * 0.05], sides=sides, mat=mat, caps=(False, True))
    hp = [p0 - dv * 0.0012, p0 + dv * 0.0003]
    K.tube(mb, hp, [head / 2, head / 2 * 0.92], sides=sides + 4, mat=mat, caps=(True, True))


def plank(mb: K.MB, length: float, width: float, thick: float, *, center=(0, 0, 0), axis: str = "X", mat: str = "item_wood_plank",
          end_mat: str = "item_wood_end", seed: int = 0, warp: float = 0.0, bevel: float = 0.002, uv_off: float = 0.0,
          n: int = 6, on_edge: bool = False) -> None:
    """Rough-sawn board with grain (texture U) along its length; slight warp/twist; chamfered edges.
    Lies flat (thickness vertical) unless on_edge (thickness horizontal, width vertical)."""
    r = common.rng(seed)
    hw, ht = width / 2, thick / 2
    b = min(bevel, ht * 0.8)
    prof = [(ht, -hw + b), (ht, hw - b), (ht - b, hw), (-ht + b, hw), (-ht, hw - b), (-ht, -hw + b), (-ht + b, -hw), (ht - b, -hw)]
    pts = []
    tw = r.uniform(-1, 1) * warp
    bow = r.uniform(-1, 1) * warp
    for i in range(n):
        t = i / (n - 1)
        pts.append(Vector((length * (t - 0.5), 0.0, bow * math.sin(t * math.pi) * length * 0.02)))
    # profile coords: x along N (= +Z for an X path with up hint Z), y along B
    m = {"X": Matrix.Identity(4), "Y": Matrix.Rotation(math.radians(90), 4, "Z"), "Z": Matrix.Rotation(math.radians(-90), 4, "Y")}[axis]
    mb.push(Matrix.Translation(center) @ m)
    f0 = len(mb.faces)
    K.tube(mb, pts, 1.0, profile=prof, mat=mat, cap_mat=end_mat, cap_uv="disc", up=Vector((0, 1, 0)) if on_edge else Vector((0, 0, 1)),
           twist=tw * 0.05,
           u_tile=None, v_offset=uv_off)
    mb.pop()
    # UVs: put the plank length on U (grain along U) for the side faces
    for fi in range(f0, len(mb.faces)):
        if mb.fmat[fi] == mat:
            mb.fuv[fi] = [(v + uv_off, u) for (u, v) in mb.fuv[fi]]


def coil(mb: K.MB, center, radius: float, turns: float, *, cord: float = 0.003, mat: str = "item_cordage",
         per_turn: int = 18, seed: int = 0, sides: int = 5, spiral: bool = False) -> None:
    """Coil of cord around `center` (z = bottom). spiral=True lies flat (radius grows per turn), otherwise
    the loops pile up loosely (each turn a little higher and offset)."""
    r = common.rng(seed)
    c = Vector(center)
    pts = []
    count = int(turns * per_turn)
    noise.seed_set(seed)
    ox, oy = r.uniform(-1, 1), r.uniform(-1, 1)
    for i in range(count + 1):
        t = i / count
        a = 2 * math.pi * turns * t
        wob = 1 + 0.07 * noise.noise(Vector((math.cos(a) * 2 + ox, math.sin(a) * 2 + oy, t * 3)))
        if spiral:
            rr = (radius + 2.05 * cord * turns * t) * wob
            z = cord
        else:
            rr = radius * wob
            z = cord + 1.7 * cord * turns * t + 0.6 * cord * math.sin(a * 0.5)
        shift = Vector((ox, oy, 0)) * cord * 2.0 * turns * t * (0 if spiral else 1)
        pts.append(c + shift + Vector((math.cos(a) * rr, math.sin(a) * rr, z)))
    K.tube(mb, pts, cord, sides=sides, mat=mat, u_tile=1.0, v_scale=1.0 / (2 * math.pi * cord) / 3)
