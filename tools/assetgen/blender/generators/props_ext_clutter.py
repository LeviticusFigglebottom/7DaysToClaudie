"""Exterior props family — clutter and containers (boxes, crates, pallets, drums, bags, scatter,
junk heaps, small carry items). Each builder takes a props_ext_kit.Ctx and registers parts; the
kit builds one GLB per condition (clean / worn / destroyed).

params: prop (id), conditions, seed, [paint] (material id override)."""
from __future__ import annotations

import math

from mathutils import Vector

from lib import props_ext_kit as K
from lib import props_ext_parts as P


# ============================================================================================
# Containers
# ============================================================================================

def _barrel_profile(lid: bool) -> list[tuple[float, float]]:
    R = 0.286
    pts = [(0.0, 0.014), (0.262, 0.014), (0.272, 0.004), (0.287, 0.0), (0.294, 0.012), (0.293, 0.028), (R, 0.04)]
    pts += [(R, z) for z in (0.1, 0.16, 0.22)] + [(R, 0.268), (0.297, 0.28), (0.297, 0.29), (R, 0.302)]
    pts += [(R, z) for z in (0.365, 0.43, 0.495)] + [(R, 0.556), (0.297, 0.568), (0.297, 0.578), (R, 0.59)]
    pts += [(R, z) for z in (0.65, 0.71, 0.77)] + [(R, 0.818), (0.293, 0.832), (0.295, 0.848), (0.29, 0.862),
                                                   (0.274, 0.86)]
    if lid:
        pts += [(0.268, 0.846), (0.0, 0.846)]
    return pts


def barrel_metal(ctx: K.Ctx) -> None:
    """55-gallon steel drum: rolling hoops, rolled chimes, bung caps. Worn: dents + rust.
    Destroyed: lid gone, crushed, lying on its side."""
    paint = ctx.param("paint", "paint_blue")
    r = ctx.rnd("barrel")
    lid = not ctx.destroyed
    body = K.lathe("drum", _barrel_profile(lid), segs=20)
    if not lid:
        K.solidify(body, 0.0025, offset=-1.0)
    if ctx.worn:
        dr = ctx.drnd("dents")
        for k in range(3 if not ctx.destroyed else 5):
            a = dr.uniform(0, math.tau)
            z = dr.uniform(0.12, 0.75)
            K.dent(body, (math.cos(a) * 0.29, math.sin(a) * 0.29, z), dr.uniform(0.07, 0.16), dr.uniform(0.012, 0.035))
    parts = [body]
    if lid:
        for (x, y, rad) in ((0.19, 0.02, 0.032), (-0.2, -0.04, 0.016)):
            parts.append(K.cyl("bung", rad, 0.012, segs=10, center=(x, y, 0.851)))
    if ctx.destroyed:
        # Crushed flank, then tipped over: drum axis along X, open end towards +X.
        K.dent(body, (0.29, 0.0, 0.45), 0.32, 0.12)
        K.dent(body, (0.2, 0.22, 0.75), 0.18, 0.06)
        K.place(body, rot=(0, 90, r.uniform(-20, 20)))
        K.drop_to_ground(body)
        ctx.add(body, paint, uv="cyl", uv_axis=0, smooth=50, patches=0.8, low=0.0)
        ctx.col_hull([body], max_points=48)
        return
    obj = K.merge_parts(parts, "drum")
    ctx.add(obj, paint, uv="cyl", uv_axis=2, smooth=50, patches=0.7, low=0.7, low_h=0.35)
    pts = [(math.cos(a) * 0.295, math.sin(a) * 0.295, z) for a in [i * math.tau / 12 for i in range(12)] for z in (0.0, 0.862)]
    ctx.col_hull(pts)


def cardboard_box(ctx: K.Ctx) -> None:
    """Taped moving/shipping box. Worn: rain-soaked, sagging, dented, tape peeling.
    Destroyed: crushed flat and split open."""
    r = ctx.rnd("box")
    L, W, H = 0.5, 0.38, 0.34
    mat = "cardboard_wet" if ctx.worn else "cardboard"
    cuts = (7, 5, 5) if ctx.destroyed else (4, 3, 3)
    body = P.cardboard_shell("box", L, W, H, cuts)
    # Seam where the top flaps meet.
    K.map_verts(body, lambda co: Vector((co.x, co.y, co.z - 0.004)) if co.z > H - 0.002 and abs(co.y) < 0.004 else co)
    P.box_bulge(body, L, W, H)
    tape_top = K.box("tape", (L + 0.006, 0.05, 0.0012), center=(0, 0, H - 0.003))
    ends = [K.box("tape_e", (0.0012, 0.05, 0.075), center=(s * (L / 2 + 0.0035), 0, H - 0.04)) for s in (-1, 1)]
    if ctx.worn:
        dr = ctx.drnd("box")
        sag = 0.035 if not ctx.destroyed else 0.0

        def sagf(co: Vector) -> Vector:
            k = max(0.0, 1 - (2 * co.x / L) ** 2) * max(0.0, 1 - (2 * co.y / W) ** 2)
            co.z -= sag * k * (co.z / H) ** 3
            return co
        for o in [body, tape_top]:
            K.map_verts(o, sagf)
        K.dent(body, (L / 2, -W / 2, H), 0.14, 0.05, direction=(-0.5, 0.4, -0.6))
        K.crumple(body, 0.006, scale=9.0, seed=dr.randint(0, 999))
        # One tape tail peeled off and curling away.
        K.place(ends[1], (-(L / 2 + 0.0035), 0, -(H - 0.005)))
        K.place(ends[1], rot=(0, 35, 0))
        K.place(ends[1], (L / 2 + 0.0035, 0, H - 0.005))
    if ctx.destroyed:
        dr = ctx.drnd("crush")
        K.jagged_hole(body, (0.08, -W / 2, 0.16), 0.11, dr.randint(0, 999), axis=1)
        for o in [body, tape_top] + ends:
            K.map_verts(o, lambda co: Vector((co.x * 1.1 + co.z * 0.25, co.y * 1.12, co.z * 0.33)))
        K.crumple(body, 0.02, scale=6.0, seed=dr.randint(0, 999))
        K.solidify(body, 0.004)
    ctx.add(body, mat, uv_scale=1.0, smooth=35 if ctx.worn else None, patches=0.0, edge=0.6)
    for t in [tape_top] + ends:
        ctx.add(t, "packing_tape", uv_scale=1.0, wear=0.3)
    if ctx.destroyed:
        ctx.col_box((-L * 0.6, -W * 0.6, 0), (L * 0.6, W * 0.6, H * 0.36))
    else:
        ctx.col_box((-L / 2, -W / 2, 0), (L / 2, W / 2, H))


def _board(name, L, Wd, T, r, *, cuts=0, bow=0.0, twist=0.0):
    return P.plank(name, L, Wd, T, bevel=0.002, cuts=cuts, bow=bow, twist=twist)


def pallet(ctx: K.Ctx) -> None:
    """GMA 48x40 in stringer pallet (1.22 x 1.02 x 0.13 m). Worn: grey, mossy, a board missing,
    another split. Destroyed: snapped stringer, boards torn off and lying around."""
    r = ctx.rnd("pallet")
    L, Wd = 1.22, 1.02
    bt, bw = 0.019, 0.089
    sh, sw = 0.095, 0.038
    wood = "wood_fresh" if ctx.clean else "wood_weathered"
    moss = 0.0 if ctx.clean else 0.6
    dr = ctx.drnd("pallet")
    notch = [(-L / 2, 0), (-0.445, 0), (-0.445, 0.036), (-0.215, 0.036), (-0.215, 0), (0.215, 0), (0.215, 0.036),
             (0.445, 0.036), (0.445, 0), (L / 2, 0), (L / 2, sh), (-L / 2, sh)]
    broken_stringer = 2 if ctx.destroyed else -1
    for i, y in enumerate((-Wd / 2 + sw / 2, 0.0, Wd / 2 - sw / 2)):
        s = K.prism(f"stringer{i}", notch, sw, plane="XZ", offset=0.0)
        K.place(s, (0, y, bt))
        if i == broken_stringer:
            P.break_end(s, 0.12, dr, side=1, depth=0.05)
            stub = K.prism("stringer_b", notch, sw, plane="XZ")
            P.break_end(stub, 0.16, dr, side=-1, depth=0.05)
            K.place(stub, (0, y, bt))
            K.place(stub, (-0.35, 0, -bt), rot=(0, -9, 4))
            K.place(stub, (0.35, 0, bt + 0.03))
            ctx.add(stub, wood, long_axis=0, moss=moss, patches=0.3)
        ctx.add(s, wood, long_axis=0, moss=moss, patches=0.3)
    nt = 7
    missing = set()
    split = -1
    if ctx.worn:
        missing.add(dr.choice([1, 5]))
        split = 3
    if ctx.destroyed:
        missing |= {0, 2, 4}
    for i in range(nt):
        x = -L / 2 + bw / 2 + 0.005 + i * (L - bw - 0.01) / (nt - 1)
        if i in missing:
            continue
        rr = ctx.rnd(f"top{i}")
        b = _board(f"top{i}", Wd, bw * rr.uniform(0.95, 1.05), bt, rr, cuts=3, bow=rr.uniform(-0.004, 0.004),
                   twist=rr.uniform(-1.5, 1.5))
        if i == split:
            P.break_end(b, 0.18, dr, side=1, depth=0.08)
        ctx.add(b, wood, long_axis=0, moss=moss, patches=0.35, ori=("y", "z", (x, 0, bt + sh + bt / 2)),
                at=((0, 0, 0), (0, 0, rr.uniform(-0.6, 0.6))))
    for i, x in enumerate((-L / 2 + 0.07, 0.0, L / 2 - 0.07)):
        rr = ctx.rnd(f"bot{i}")
        b = _board(f"bot{i}", Wd, 0.14, bt, rr, cuts=2)
        ctx.add(b, wood, long_axis=0, moss=moss * 0.3, patches=0.35, ori=("y", "z", (x, 0, bt / 2)))
    if ctx.destroyed:
        # Torn-off boards lying beside the pallet.
        for k in range(3):
            rr = ctx.drnd(f"loose{k}")
            b = _board(f"loose{k}", Wd * rr.uniform(0.45, 1.0), bw, bt, rr)
            if rr.random() < 0.7:
                P.break_end(b, 0.0, rr, side=1 if rr.random() < 0.5 else -1, depth=0.1)
            ctx.add(b, wood, long_axis=0, moss=0.3, patches=0.4,
                    at=((rr.uniform(-0.9, 0.9), -Wd / 2 - 0.25 - k * 0.12, bt / 2), (0, rr.uniform(-4, 4), rr.uniform(-60, 60))))
    ctx.col_box((-L / 2, -Wd / 2, 0), (L / 2, Wd / 2, bt * 2 + sh))


def crate_wood(ctx: K.Ctx) -> None:
    """Slatted shipping/produce crate with lid (0.6 x 0.42 x 0.42). Worn: grey, a slat missing,
    lid ajar. Destroyed: smashed — walls burst outward, lid and slats on the ground."""
    L, Wd, H = 0.6, 0.42, 0.42
    t, post = 0.012, 0.028
    wood = "wood_fresh" if ctx.clean else "wood_weathered"
    dr = ctx.drnd("crate")
    smashed = ctx.destroyed
    # Corner posts.
    for sx in (-1, 1):
        for sy in (-1, 1):
            h = H - 0.02
            if smashed and sx > 0 and sy < 0:
                h = H * 0.55
            p = K.box("post", (post, post, h), center=(sx * (L / 2 - post / 2 - t), sy * (Wd / 2 - post / 2 - t), h / 2),
                      bevel=0.002, cuts=(0, 0, 2))
            ctx.add(p, wood, long_axis=2, patches=0.3)
    slat_z = (0.065, 0.2, 0.335)
    missing = {("front", 1)} if ctx.worn else set()
    for side, (n, ln) in {"front": ("-y", L), "back": ("y", L), "left": ("-x", Wd - 2 * t), "right": ("x", Wd - 2 * t)}.items():
        nv = K.AXES[n]
        along = "x" if side in ("front", "back") else "y"
        for k, z in enumerate(slat_z):
            if (side, k) in missing:
                continue
            rr = ctx.rnd(f"{side}{k}")
            s = _board(f"{side}{k}", ln, 0.105, t, rr, cuts=2, bow=rr.uniform(-0.002, 0.002))
            off = (L / 2 - t / 2) if side in ("left", "right") else (Wd / 2 - t / 2)
            loc = nv * off + Vector((0, 0, z))
            if smashed and side in ("front", "right"):
                sr = ctx.drnd(f"smash{side}{k}")
                P.break_end(s, sr.uniform(-0.1, 0.15), sr, side=1 if sr.random() < 0.5 else -1, depth=0.08)
                K.uv_box(s, 1.0, long_axis=0, offset=(sr.uniform(0, 5), sr.uniform(0, 5)))
                K.orient(s, along, n)
                K.place(s, rot=(sr.uniform(-25, 25), sr.uniform(-30, 30), sr.uniform(-20, 20)))
                K.place(s, loc + nv * sr.uniform(0.05, 0.25) - Vector((0, 0, z * sr.uniform(0.3, 0.9))))
                K.lift_min(s)
                ctx.add(s, wood, uv=None, patches=0.4)
                continue
            ctx.add(s, wood, long_axis=0, patches=0.35, ori=(along, n, loc))
    # Bottom slats.
    for k, y in enumerate((-0.13, 0.0, 0.13)):
        b = _board(f"bot{k}", L - 2 * t, 0.1, t, ctx.rnd(f"b{k}"))
        ctx.add(b, wood, long_axis=0, patches=0.3, at=((0, y, t / 2), None))
    # Lid: three slats on two battens.
    lid = []
    for k, y in enumerate((-0.135, 0.0, 0.135)):
        lid.append(_board(f"lid{k}", L, 0.13, t, ctx.rnd(f"l{k}")))
        K.place(lid[-1], (0, y, t / 2 + 0.022))
    for x in (-L / 2 + 0.07, L / 2 - 0.07):
        bat = K.box("batten", (0.05, Wd - 0.06, 0.022), center=(x, 0, 0.011), bevel=0.002)
        lid.append(bat)
    lid_obj = K.merge_parts(lid, "lid")
    if ctx.destroyed:
        K.place(lid_obj, rot=(178, 0, 25))
        K.place(lid_obj, (-0.3, 0.42, 0.0))
        K.lift_min(lid_obj)
    elif ctx.worn:
        K.place(lid_obj, (L / 2, 0, 0))
        K.place(lid_obj, rot=(0, -12, 4))
        K.place(lid_obj, (-L / 2 + 0.05, 0.02, H - 0.012))
    else:
        K.place(lid_obj, (0, 0, H - 0.022))
    ctx.add(lid_obj, wood, long_axis=0, patches=0.35)
    if ctx.destroyed:
        ctx.col_box((-L / 2, -Wd / 2, 0), (L / 2, Wd / 2, H * 0.6))
    else:
        ctx.col_box((-L / 2, -Wd / 2, 0), (L / 2, Wd / 2, H))


def cardboard_box_open(ctx: K.Ctx) -> None:
    """Opened box, flaps folded out, crumpled paper inside. Worn: soaked, a flap torn off, flaps
    hanging. Destroyed: trodden flat, flaps splayed on the floor."""
    L, W, H = 0.46, 0.34, 0.30
    mat = "cardboard_wet" if ctx.worn else "cardboard"
    shell = K.box("shell", (L, W, H), center=(0, 0, H / 2), cuts=(3, 2, 2))
    K.delete_faces(shell, lambda c, n: n.z > 0.9 and c.z > H - 0.001)
    P.box_bulge(shell, L, W, H, 0.006)
    K.solidify(shell, 0.004, offset=-1.0)
    hinges = {
        "front": ((-L / 2, -W / 2, H), (L / 2, -W / 2, H), (0, -1, 0)),
        "back": ((L / 2, W / 2, H), (-L / 2, W / 2, H), (0, 1, 0)),
        "left": ((-L / 2, W / 2, H), (-L / 2, -W / 2, H), (-1, 0, 0)),
        "right": ((L / 2, -W / 2, H), (L / 2, W / 2, H), (1, 0, 0)),
    }
    if ctx.destroyed:
        angles = {"front": -2, "back": -4, "left": -3, "right": None}
    elif ctx.worn:
        angles = {"front": -55, "back": 25, "left": None, "right": -35}
    else:
        angles = {"front": 30, "back": 62, "left": 18, "right": 48}
    flaps = []
    for k, (a, b, o) in hinges.items():
        ang = angles[k]
        if ang is None:
            continue
        flaps.append(P.flap(f"flap_{k}", a, b, o, W / 2 * 0.98, ang))
    contents = []
    if not ctx.destroyed:
        cr = ctx.rnd("contents")
        for i in range(4):
            w = P.paper_wad(f"wad{i}", cr, cr.uniform(0.045, 0.07))
            K.place(w, (cr.uniform(-L / 2 + 0.08, L / 2 - 0.08), cr.uniform(-W / 2 + 0.07, W / 2 - 0.07),
                        H * cr.uniform(0.55, 0.8)), (cr.uniform(0, 90), 0, cr.uniform(0, 360)))
            contents.append(w)
    allp = [shell] + flaps
    if ctx.worn:
        dr = ctx.drnd("sag")
        for o in allp:
            K.crumple(o, 0.006, scale=8.0, seed=dr.randint(0, 999))
    if ctx.destroyed:
        dr = ctx.drnd("flat")
        for o in allp:
            K.map_verts(o, lambda co: Vector((co.x * 1.08 + co.z * 0.45, co.y * 1.1, co.z * 0.22)))
            K.crumple(o, 0.012, scale=7.0, seed=dr.randint(0, 999))
    ctx.add(shell, mat, uv_scale=1.0, smooth=30 if ctx.worn else None, patches=0.0, edge=0.5)
    for f in flaps:
        ctx.add(f, mat, uv_scale=1.0, smooth=30 if ctx.worn else None, patches=0.0, edge=0.5)
    for w in contents:
        ctx.add(w, "paper_trash", uv_scale=2.0, smooth=60, patches=0.0, edge=0.3)
    h = H * 0.3 if ctx.destroyed else H
    ctx.col_box((-L / 2, -W / 2, 0), (L / 2, W / 2, h))


def trash_bag(ctx: K.Ctx) -> None:
    """Tied garbage bag. Worn: torn open on one side, trash spilling. Destroyed: burst and
    trampled flat, contents strewn."""
    r = ctx.rnd("bag")
    dr = ctx.drnd("bag")
    if ctx.destroyed:
        bag = P.add_bag(ctx, "bag", r, "plastic_bag_black", size=(0.58, 0.52, 0.55), segs=18, burst=True, flat=0.45,
                   rotz=30.0)
        P.add_litter(ctx, dr, 10, extent=(0.5, 0.35), center=(0.05, -0.38), kinds=("paper", "wad", "can", "paper", "bottle"))
        ctx.col_box((-0.4, -0.35, 0), (0.4, 0.35, 0.3))
        return
    bag = P.add_bag(ctx, "bag", r, "plastic_bag_black", size=(0.5, 0.44, 0.62), segs=18, torn=ctx.worn)
    if ctx.worn:
        P.add_litter(ctx, dr, 5, extent=(0.22, 0.12), center=(0.0, -0.38), kinds=("wad", "paper", "can"))
    ctx.col_hull([bag], max_points=40)


def trash_pile(ctx: K.Ctx) -> None:
    """Curbside heap of garbage bags with a crushed box and loose junk (~1.6 x 1.4 x 0.75 m).
    Worn: bags split and slumped, litter spread wider."""
    r = ctx.rnd("pile")
    dr = ctx.drnd("pile")
    spots = [((-0.42, 0.12, 0), (0.55, 0.48, 0.6), 20, "plastic_bag_black"),
             ((0.18, 0.28, 0), (0.5, 0.45, 0.58), 140, "plastic_bag_green"),
             ((0.45, -0.18, 0), (0.48, 0.42, 0.55), 75, "plastic_bag_black"),
             ((-0.12, -0.32, 0), (0.46, 0.42, 0.5), 250, "plastic_bag_black"),
             ((-0.05, 0.02, 0.32), (0.5, 0.44, 0.56), 310, "plastic_bag_green"),
             ((0.32, 0.12, 0.25), (0.42, 0.38, 0.48), 200, "plastic_bag_black")]
    bags = []
    for i, (loc, size, rz, mat) in enumerate(spots):
        rr = ctx.rnd(f"bag{i}")
        torn = ctx.worn and i in (0, 3)
        flat = 0.35 if (ctx.worn and i == 2) else 0.0
        bags.append(P.add_bag(ctx, f"bag{i}", rr, mat, size=size, segs=12, torn=torn, flat=flat, loc=loc, rotz=rz,
                         tilt=(rr.uniform(-12, 12), rr.uniform(-12, 12)) if loc[2] > 0 else (0, 0)))
    # Crushed box leaning on the heap.
    box = P.cardboard_shell("pbox", 0.45, 0.35, 0.3, (3, 2, 2))
    K.map_verts(box, lambda co: Vector((co.x * 1.05 + co.z * 0.3, co.y, co.z * 0.4)))
    K.crumple(box, 0.012, scale=7.0, seed=r.randint(0, 999))
    K.place(box, rot=(0, -14, 35))
    K.place(box, (-0.62, -0.4, 0.0))
    K.lift_min(box)
    ctx.add(box, "cardboard_wet", uv_scale=1.0, smooth=30, patches=0.0, edge=0.4)
    P.add_litter(ctx, dr, 8 if ctx.worn else 6, extent=(0.85, 0.7) if ctx.worn else (0.7, 0.55), center=(0, -0.1),
            kinds=("paper", "can", "wad", "bottle", "paper"))
    ctx.col_hull([b for b in bags], max_points=48)


def _plaster_slab(name, r, size):
    """Broken drywall / plaster-and-lath fragment: thin irregular slab."""
    n = r.randint(5, 7)
    pts = []
    for k in range(n):
        a = math.tau * k / n + r.uniform(-0.3, 0.3)
        rr = size * r.uniform(0.55, 1.0)
        pts.append((math.cos(a) * rr, math.sin(a) * rr))
    return K.prism(name, pts, r.uniform(0.012, 0.022), plane="XY")


def debris_pile(ctx: K.Ctx) -> None:
    """Rubble heap from a collapsed ceiling/wall: plaster lumps, brick bits, broken lath, a stud.
    Worn: bigger, flatter spread with more splintered wood."""
    r = ctx.rnd("debris")
    sx, sy, h = (1.0, 0.8, 0.5) if ctx.clean else (1.15, 0.95, 0.42)
    base = K.blob("mound", 0.5, subdiv=3, scale=(sx * 1.7, sy * 1.7, h * 1.6), rough=0.25, seed=r.randint(0, 999),
                  noise_scale=2.5)
    K.place(base, (0, 0, -h * 0.25))
    K.cut_plane(base, (0, 0, 0.002), (0, 0, -1), keep="below", fill=False)  # removes everything under the floor
    ctx.add(base, "plaster_rubble", uv_scale=1.0, smooth=50, patches=0.0, edge=0.3)
    chunks = P.rubble_heap(r, 26 if ctx.clean else 30, extent=(sx * 0.9, sy * 0.9), height=h * 0.9, size=(0.05, 0.2),
                           flat=0.55)
    for i, c in enumerate(chunks):
        mat = "brick_rubble" if i % 6 == 0 else "plaster_rubble"
        ctx.add(c, mat, uv_scale=1.0, patches=0.0, edge=0.6)
    for i in range(5):
        s = _plaster_slab(f"slab{i}", r, r.uniform(0.12, 0.25))
        K.place(s, (r.uniform(-sx, sx) * 0.8, r.uniform(-sy, sy) * 0.8, r.uniform(0.05, h * 0.7)),
                (r.uniform(-35, 35), r.uniform(-35, 35), r.uniform(0, 360)))
        ctx.add(s, "plaster_rubble", uv_scale=1.0, patches=0.0, edge=0.6)
    nl = 6 if ctx.clean else 9
    for i in range(nl):
        rr = ctx.rnd(f"lath{i}")
        ln = rr.uniform(0.5, 1.2)
        lath = P.plank(f"lath{i}", ln, 0.035, 0.009, cuts=2, bow=rr.uniform(-0.01, 0.01))
        P.break_end(lath, ln / 2 - 0.03, rr, side=1, depth=0.05)
        ctx.add(lath, "wood_weathered", long_axis=0, patches=0.2,
                at=((rr.uniform(-sx, sx) * 0.7, rr.uniform(-sy, sy) * 0.7, rr.uniform(0.08, h * 0.8)),
                    (rr.uniform(-25, 25), rr.uniform(-20, 20), rr.uniform(0, 360))))
    if ctx.worn:
        stud = P.plank("stud", 1.6, 0.089, 0.038, cuts=3)
        P.break_end(stud, 0.7, r, side=1, depth=0.1)
        ctx.add(stud, "wood_weathered", long_axis=0, patches=0.3, at=((0.1, 0.05, 0.28), (8, -24, 30)))
    ctx.col_hull([base], max_points=40)


def plank_pile(ctx: K.Ctx) -> None:
    """Salvaged lumber pile: 2x4s and 1x6 boards. Worn: silvered, mossy, broken, scattered."""
    r = ctx.rnd("planks")
    wood = "wood_fresh" if ctx.clean else "wood_weathered"
    moss = 0.0 if ctx.clean else 0.6
    z = 0.0
    layers = [(5, 0.0), (4, 90.0 if ctx.worn else 6.0), (3, -8.0)]
    for li, (n, rot) in enumerate(layers):
        th = 0.038 if li != 1 else 0.019
        for i in range(n):
            rr = ctx.rnd(f"p{li}_{i}")
            ln = rr.uniform(1.7, 2.4) if li != 1 else rr.uniform(1.2, 1.9)
            wd = 0.089 if th > 0.03 else 0.14
            pl = P.plank(f"pl{li}_{i}", ln, wd, th, cuts=3, bow=rr.uniform(-0.01, 0.01), twist=rr.uniform(-2, 2))
            if ctx.worn and rr.random() < 0.35:
                P.break_end(pl, ln / 2 - rr.uniform(0.1, 0.5), rr, side=1, depth=0.08)
            off = (i - (n - 1) / 2) * (wd + rr.uniform(0.005, 0.06))
            spread = 1.6 if ctx.worn else 1.0
            sx = rr.uniform(-0.15, 0.15) * spread if li else 0.0
            # Lay the board along X at its slot, then turn the whole layer.
            K.uv_box(pl, 1.0, long_axis=0, offset=(rr.uniform(0, 7), rr.uniform(0, 7)))
            K.place(pl, (sx, off, th / 2), (rr.uniform(-1, 1), rr.uniform(-1.5, 1.5), rr.uniform(-4, 4) * spread))
            K.place(pl, (0, 0, z), (0, 0, rot))
            ctx.add(pl, wood, uv=None, moss=moss, patches=0.35)
        z += th
    ctx.col_box((-1.15, -0.4, 0), (1.15, 0.4, z + 0.02))


def plaster_chunks(ctx: K.Ctx) -> None:
    """Floor scatter of fallen plaster lumps and flakes (~1.2 x 1.0 m, no collision)."""
    r = ctx.rnd("chunks")
    for i in range(22):
        s = r.uniform(0.025, 0.12) * (1.0 if i % 5 else 1.6)
        c = K.chunk(f"c{i}", s, r, n=r.randint(7, 11), flat=r.uniform(0.35, 0.7), elong=r.uniform(0.9, 1.7))
        rad = math.sqrt(r.random())
        a = r.uniform(0, math.tau)
        K.place(c, (math.cos(a) * rad * 0.55, math.sin(a) * rad * 0.45, 0), (r.uniform(-10, 10), r.uniform(-10, 10), r.uniform(0, 360)))
        K.lift_min(c)
        ctx.add(c, "plaster_rubble", uv_scale=1.5, patches=0.0, edge=0.6)
    for i in range(4):
        s = _plaster_slab(f"f{i}", r, r.uniform(0.06, 0.14))
        K.place(s, (r.uniform(-0.5, 0.5), r.uniform(-0.4, 0.4), 0), (r.uniform(-6, 6), r.uniform(-6, 6), r.uniform(0, 360)))
        K.lift_min(s)
        ctx.add(s, "plaster_rubble", uv_scale=1.5, patches=0.0, edge=0.6)


def glass_shards(ctx: K.Ctx) -> None:
    """Broken window glass on the floor: flat shards, a few propped on others (~1.0 x 0.8 m)."""
    r = ctx.rnd("glass")
    for i in range(26):
        size = r.uniform(0.02, 0.09) * (2.0 if i < 3 else 1.0)
        n = r.randint(3, 5)
        a0 = r.uniform(0, math.tau)
        pts = []
        for k in range(n):
            a = a0 + math.tau * k / n + r.uniform(-0.35, 0.35)
            rr = size * r.uniform(0.4, 1.0) * (1.8 if k == 0 else 1.0)
            pts.append((math.cos(a) * rr, math.sin(a) * rr))
        s = K.prism(f"g{i}", pts, 0.003, plane="XY")
        rad = math.sqrt(r.random())
        a = r.uniform(0, math.tau)
        tilt = (r.uniform(-14, 14), r.uniform(-14, 14)) if i % 4 == 0 else (r.uniform(-2, 2), r.uniform(-2, 2))
        K.place(s, (math.cos(a) * rad * 0.48, math.sin(a) * rad * 0.38, 0.0), (tilt[0], tilt[1], r.uniform(0, 360)))
        K.lift_min(s)
        ctx.add(s, "glass_clear", uv_scale=1.0, patches=0.0, edge=0.0, wear=0.0)


def paper_scatter(ctx: K.Ctx) -> None:
    """Loose sheets, a newspaper and a few wads (~1.5 x 1.2 m). Worn: soggy, crumpled, torn."""
    r = ctx.rnd("papers")
    cells = list(K.ATLAS_PAPER.items())
    for i in range(11):
        name, cell = cells[i % 4]
        big = name == "news"
        w, h = (0.38, 0.29) if big else (0.216, 0.279)
        if ctx.worn and r.random() < 0.4:
            w, h = w * r.uniform(0.5, 0.8), h * r.uniform(0.5, 0.8)
        s = K.grid(f"s{i}", w, h, 4, 3)
        K.uv_planar(s, 2, rect=cell)
        curl = r.uniform(0.0, 0.04)
        K.map_verts(s, lambda co, c=curl, w2=w: Vector((co.x, co.y, c * (2 * co.x / w2) ** 2)))
        K.crumple(s, 0.008 if ctx.clean else 0.02, scale=9.0, seed=r.randint(0, 999))
        K.map_verts(s, lambda co: Vector((co.x, co.y, abs(co.z) + 0.002)))
        rad = math.sqrt(r.random())
        a = r.uniform(0, math.tau)
        K.place(s, (math.cos(a) * rad * 0.6, math.sin(a) * rad * 0.48, 0.0), (0, 0, r.uniform(0, 360)))
        K.solidify(s, 0.0008)
        ctx.add(s, "paper_trash", uv=None, smooth=40, patches=0.0, edge=0.0)
    for i in range(3 if ctx.clean else 6):
        w = P.paper_wad(f"w{i}", r, r.uniform(0.04, 0.07))
        K.place(w, (r.uniform(-0.6, 0.6), r.uniform(-0.5, 0.5), 0.0))
        K.lift_min(w)
        ctx.add(w, "paper_trash", uv_scale=2.0, smooth=60, patches=0.0, edge=0.2)


def cans_scatter(ctx: K.Ctx) -> None:
    """Empty drink/food cans, some crushed (~0.8 x 0.6 m). Worn: flattened and rust-spotted."""
    r = ctx.rnd("cans")
    mats = ["can_red", "can_blue", "can_green", "can_alu", "can_red", "can_alu", "can_blue", "can_green"]
    for i in range(8):
        crushed = r.uniform(0.0, 0.5) if ctx.clean else r.uniform(0.4, 1.0)
        if i == 2:  # a taller food tin
            c = P.can(f"c{i}", r, crushed=crushed * 0.5, h=0.112, rad=0.042, segs=10)
        else:
            c = P.can(f"c{i}", r, crushed=crushed, segs=8)
        upright = r.random() < 0.25 and crushed < 0.5
        if not upright:
            K.place(c, rot=(90, 0, 0))
            K.place(c, rot=(0, 0, r.uniform(0, 360)))
        K.lift_min(c)
        rad = math.sqrt(r.random())
        a = r.uniform(0, math.tau)
        K.place(c, (math.cos(a) * rad * 0.36, math.sin(a) * rad * 0.26, 0))
        K.drop_to_ground(c)
        ctx.add(c, mats[i] if i != 2 else "can_alu", uv="cyl", uv_axis=2, uv_scale=1.0, smooth=45,
                patches=0.5 if ctx.worn else 0.0)


def bottles_scatter(ctx: K.Ctx) -> None:
    """Beer and liquor bottles, one smashed with shards (~0.8 x 0.6 m). Worn: more broken."""
    r = ctx.rnd("bottles")
    specs = [("beer", "glass_brown"), ("beer", "glass_green"), ("liquor", "glass_clear"), ("beer", "glass_brown"),
             ("beer", "glass_brown"), ("liquor", "glass_green")]
    for i, (kind, mat) in enumerate(specs):
        broken = (i == 1) or (ctx.worn and i in (3, 4))
        b = P.bottle(f"b{i}", r, broken=broken, kind=kind)
        upright = (i == 2 and ctx.clean) or (i == 4 and not broken)
        if not upright:
            K.place(b, rot=(90, 0, 0))
            K.place(b, rot=(0, 0, r.uniform(0, 360)))
        K.drop_to_ground(b)
        rad = math.sqrt(r.random())
        a = r.uniform(0, math.tau)
        K.place(b, (math.cos(a) * rad * 0.34, math.sin(a) * rad * 0.24, 0))
        ctx.add(b, mat, uv="cyl", uv_axis=2, uv_scale=1.0, smooth=50, patches=0.0, edge=0.2, wear=0.4)
        if broken:
            for k in range(5):
                s = r.uniform(0.01, 0.035)
                n = 3 + k % 2
                pts = [(math.cos(math.tau * j / n + r.uniform(-0.4, 0.4)) * s * r.uniform(0.5, 1.0),
                        math.sin(math.tau * j / n + r.uniform(-0.4, 0.4)) * s * r.uniform(0.5, 1.0)) for j in range(n)]
                sh = K.prism(f"sh{i}_{k}", pts, 0.003, plane="XY")
                c = Vector((sum(v.co.x for v in b.data.vertices), sum(v.co.y for v in b.data.vertices), 0)) / len(b.data.vertices)
                K.place(sh, (c.x + r.uniform(-0.12, 0.12), c.y + r.uniform(-0.12, 0.12), 0), (0, 0, r.uniform(0, 360)))
                ctx.add(sh, mat, uv_scale=1.0, patches=0.0, edge=0.0, wear=0.0)


def books_scatter(ctx: K.Ctx) -> None:
    """Dropped hardbacks and paperbacks, one splayed open, loose pages (~0.9 x 0.7 m)."""
    r = ctx.rnd("books")
    mats = ["book_red", "book_blue", "book_green", "book_brown", "book_blue", "book_red", "book_brown"]
    placed = []
    for i in range(7):
        w, h, t = r.uniform(0.13, 0.17), r.uniform(0.19, 0.25), r.uniform(0.018, 0.045)
        opened = 168.0 if i == 0 else (150.0 if (ctx.worn and i == 4) else 0.0)
        cov, pg = P.book(f"bk{i}", r, w=w, h=h, t=t, opened=opened)
        if ctx.worn:
            for o in (cov, pg):
                K.crumple(o, 0.004, scale=12.0, seed=r.randint(0, 999))
        rad = math.sqrt(r.random())
        a = r.uniform(0, math.tau)
        x, y = math.cos(a) * rad * 0.38, math.sin(a) * rad * 0.28
        z = 0.0
        if i == 3 and placed:  # stacked on a previous book
            x, y, z = placed[1][0] + r.uniform(-0.03, 0.03), placed[1][1] + r.uniform(-0.03, 0.03), placed[1][2]
        rz = r.uniform(0, 360)
        tilt = (r.uniform(-2, 2), r.uniform(-2, 2))
        for o in (cov, pg):
            K.place(o, rot=(tilt[0], tilt[1], rz))
            K.place(o, (x, y, z))
        placed.append((x, y, z + t))
        ctx.add(cov, mats[i], uv_scale=1.0, patches=0.3, edge=0.7)
        ctx.add(pg, "paper_pages", uv_scale=1.0, patches=0.0, edge=0.3)
    for i in range(2 if ctx.clean else 4):
        s = K.grid(f"pg{i}", 0.14, 0.21, 3, 3)
        K.uv_planar(s, 2, rect=K.ATLAS_PAPER["note"])
        K.crumple(s, 0.01, scale=10.0, seed=r.randint(0, 999))
        K.map_verts(s, lambda co: Vector((co.x, co.y, abs(co.z) + 0.002)))
        K.place(s, (r.uniform(-0.45, 0.45), r.uniform(-0.35, 0.35), 0), (0, 0, r.uniform(0, 360)))
        K.solidify(s, 0.0008)
        ctx.add(s, "paper_trash", uv=None, smooth=40, patches=0.0, edge=0.0)


def clothes_pile(ctx: K.Ctx) -> None:
    """Heap of dumped clothes (jeans, flannel, sweater, tee, jacket). Worn: grimier, spread out."""
    garments = [("jeans", "denim_bloody" if ctx.worn else "canvas_denim"), ("shirt", "flannel_red"),
                ("sweater", "canvas_grey"), ("tee", "canvas_khaki"), ("shirt", "canvas_olive"), ("tee", "canvas_navy")]
    spread = 1.6 if ctx.worn else 1.0
    for i, (kind, mat) in enumerate(garments):
        rr = ctx.rnd(f"g{i}")
        c = P.garment(f"cl{i}", kind, rr, fold=rr.random() < 0.7)
        ang = rr.uniform(0, math.tau)
        rad = rr.uniform(0.0, 0.16) * spread
        cx, cy = math.cos(ang) * rad, math.sin(ang) * rad
        layer = i * 0.022 / spread

        def heap(co, layer=layer):
            d2 = ((co.x) / (0.45 * spread)) ** 2 + ((co.y) / (0.36 * spread)) ** 2
            co.z += max(0.0, (0.14 / spread) * (1 - d2)) + layer * max(0.0, 1 - d2)
            return co
        K.place(c, rot=(0, 0, math.degrees(rr.uniform(0, math.tau))))
        K.place(c, (cx, cy, 0))
        K.map_verts(c, heap)
        K.crumple(c, 0.018, scale=7.0, seed=rr.randint(0, 999))
        K.drop_to_ground(c)
        ctx.add(c, mat, uv=None, smooth=55, patches=0.0, edge=0.2, base=0.0,
                extra=(lambda co, n: 0.55 * max(0.0, math.sin(co.x * 9) * math.cos(co.y * 7))) if mat.endswith("bloody") else None)
    ctx.col_box((-0.45 * spread, -0.35 * spread, 0), (0.45 * spread, 0.35 * spread, 0.2))


def toolbox(ctx: K.Ctx) -> None:
    """Red steel hip-roof toolbox with latches and handle. Worn: rusted, dented, lid ajar.
    Destroyed: lid ripped off, body dented, tools spilled."""
    r = ctx.rnd("toolbox")
    L, W, Hb = 0.51, 0.22, 0.15
    body = K.box("body", (L, W, Hb), center=(0, 0, Hb / 2), bevel=0.006, cuts=(3, 1, 1))
    lid_parts = [K.loft("lid", [
        [(-L / 2, -W / 2, 0), (L / 2, -W / 2, 0), (L / 2, W / 2, 0), (-L / 2, W / 2, 0)],
        [(-L / 2, -W / 2, 0.025), (L / 2, -W / 2, 0.025), (L / 2, W / 2, 0.025), (-L / 2, W / 2, 0.025)],
        [(-L / 2 + 0.03, -W / 2 + 0.05, 0.06), (L / 2 - 0.03, -W / 2 + 0.05, 0.06), (L / 2 - 0.03, W / 2 - 0.05, 0.06),
         (-L / 2 + 0.03, W / 2 - 0.05, 0.06)]])]
    handle = K.tube("handle", [(-0.11, 0, 0.06), (-0.1, 0, 0.1), (-0.07, 0, 0.115), (0.07, 0, 0.115), (0.1, 0, 0.1),
                               (0.11, 0, 0.06)], 0.009, segs=6)
    grip = K.cyl("grip", 0.016, 0.13, segs=8, axis="X", center=(0, 0, 0.115))
    latches = [K.box("latch", (0.035, 0.012, 0.05), center=(s * 0.16, -W / 2 - 0.005, Hb - 0.005), bevel=0.002) for s in (-1, 1)]
    hinge = K.cyl("hinge", 0.006, L - 0.04, segs=6, axis="X", center=(0, W / 2 + 0.004, Hb))
    paint = "paint_red"
    if ctx.worn:
        dr = ctx.drnd("dents")
        for k in range(3):
            K.dent(body, (dr.uniform(-0.2, 0.2), -W / 2, dr.uniform(0.03, 0.12)), 0.06, 0.012)
    lid_group = lid_parts + [handle, grip]
    if ctx.destroyed:
        dr = ctx.drnd("lid")
        for o in lid_group:
            K.place(o, rot=(180, 0, 0))
            K.place(o, rot=(0, 0, 40))
            K.place(o, (0.42, 0.25, 0.062))
        K.dent(body, (0.1, -W / 2, Hb), 0.12, 0.04)
        # Spilled tools: a wrench and a screwdriver.
        wr = K.merge_parts([K.box("wr", (0.2, 0.018, 0.006), center=(0, 0, 0.003)),
                            K.cyl("wr1", 0.017, 0.007, segs=8, center=(0.1, 0, 0.0035)),
                            K.cyl("wr2", 0.014, 0.007, segs=8, center=(-0.1, 0, 0.0035))], "wrench")
        K.place(wr, (-0.1, -0.3, 0), (0, 0, 25))
        ctx.add(wr, "chrome_pitted", uv_scale=1.0, patches=0.4)
        sd_h = K.cyl("sdh", 0.014, 0.09, segs=8, axis="X", center=(0.05, 0, 0.014))
        sd_s = K.cyl("sds", 0.0035, 0.12, segs=6, axis="X", center=(-0.055, 0, 0.014))
        K.place(sd_h, (0.15, -0.28, 0), (0, 0, -60))
        K.place(sd_s, (0.15, -0.28, 0), (0, 0, -60))
        ctx.add(sd_h, "plastic_yellow", uv_scale=1.0, smooth=40)
        ctx.add(sd_s, "chrome_pitted", uv_scale=1.0)
    else:
        # Rotate about the hinge line (back top edge): negative angle lifts the front edge.
        ajar = -14.0 if ctx.worn else 0.0
        for o in lid_group:
            K.place(o, (0, -W / 2, 0))
            K.place(o, rot=(ajar, 0, 0))
            K.place(o, (0, W / 2, Hb))
    ctx.add(body, paint, uv_scale=1.0, smooth=35, patches=0.7, low=0.4, low_h=0.08)
    ctx.add(K.merge_parts(lid_parts, "lid"), paint, uv_scale=1.0, smooth=35, patches=0.7)
    ctx.add(handle, "chrome_pitted", uv_scale=1.0, smooth=40)
    ctx.add(grip, "plastic_black", uv="cyl", uv_axis=0, smooth=40)
    for la in latches:
        ctx.add(la, "chrome_pitted", uv_scale=1.0)
    ctx.add(hinge, "chrome_pitted", uv="cyl", uv_axis=0, smooth=40)
    ctx.col_box((-L / 2, -W / 2, 0), (L / 2, W / 2, Hb + 0.06))


def duffel_bag(ctx: K.Ctx) -> None:
    """Canvas duffel lying on its side, webbing handles and zip. Worn: half-empty, slumped, grimy."""
    r = ctx.rnd("duffel")
    Lh = 0.36
    prof = [(0.0, -Lh), (0.1, -Lh + 0.004), (0.15, -Lh + 0.03), (0.165, -Lh + 0.08), (0.17, -0.15), (0.172, 0.0),
            (0.17, 0.15), (0.165, Lh - 0.08), (0.15, Lh - 0.03), (0.1, Lh - 0.004), (0.0, Lh)]
    body = K.lathe("duffel", prof, segs=16)
    K.place(body, rot=(0, 90, 0))
    sag = 0.3 if ctx.worn else 0.12

    def settle(co):
        co.z = co.z * (1 - sag) if co.z > 0 else co.z * 0.65
        if co.z < -0.1:
            co.x *= 1.0
            co.y *= 1.0 + (-0.1 - co.z) * 0.8
        return co
    K.map_verts(body, settle)
    K.crumple(body, 0.012 if ctx.clean else 0.022, scale=6.0, seed=r.randint(0, 999))
    K.drop_to_ground(body)
    top = max(v.co.z for v in body.data.vertices)
    zip_ = K.box("zip", (0.56, 0.022, 0.006), center=(0, 0, top - 0.002), cuts=(4, 0, 0))
    K.map_verts(zip_, lambda co: Vector((co.x, co.y, co.z - 0.06 * (2 * co.x / 0.56) ** 4)))
    straps = []
    for s in (-1, 1):
        pts = []
        for k in range(9):
            a = math.pi * k / 8
            pts.append((s * 0.12, -0.19 * math.cos(a), 0.04 + (top - 0.04 + 0.06) * math.sin(a) * (0.9 if ctx.worn else 1.0)))
        straps.append(K.tube(f"strap{s}", pts, 0.012, segs=4, flat=(0.25, 1.0)))
    ctx.add(body, "canvas_olive", uv_scale=1.0, smooth=55, patches=0.0, edge=0.4)
    ctx.add(zip_, "plastic_black", uv_scale=1.0, wear=0.2)
    for s in straps:
        ctx.add(s, "plastic_black", uv_scale=1.0, smooth=40, wear=0.2)
    ctx.col_box((-0.37, -0.2, 0), (0.37, 0.2, top))


def backpack_dropped(ctx: K.Ctx) -> None:
    """90s daypack lying on its back: main body, front pocket, top handle, straps splayed.
    Worn: grimy, slumped, a strap torn loose."""
    r = ctx.rnd("pack")
    W, Lp, D = 0.32, 0.44, 0.16
    body = K.box("pack", (W, Lp, D), center=(0, 0, D / 2), bevel=0.05, bevel_segs=3)
    K.noise_disp(body, 0.012, scale=5.0, seed=r.randint(0, 999))
    K.map_verts(body, lambda co: Vector((co.x * (1 + 0.08 * max(0.0, co.z / D)), co.y, co.z * (0.85 if ctx.worn else 1.0))))
    pocket = K.box("pocket", (0.24, 0.2, 0.06), center=(0, -0.08, D * (0.85 if ctx.worn else 1.0) - 0.012), bevel=0.025,
                   bevel_segs=2)
    handle = K.tube("handle", [(-0.04, Lp / 2 - 0.02, D * 0.8), (-0.03, Lp / 2 + 0.03, D * 0.85),
                               (0.03, Lp / 2 + 0.03, D * 0.85), (0.04, Lp / 2 - 0.02, D * 0.8)], 0.008, segs=4,
                    flat=(0.3, 1.0))
    straps = []
    for s in (-1, 1):
        torn = ctx.worn and s > 0
        pts = [(s * 0.08, Lp / 2 - 0.06, 0.02), (s * 0.17, Lp / 2 - 0.1, 0.012), (s * 0.24, 0.05, 0.008),
               (s * 0.25 + (0.12 if torn else 0.0) * s, -0.12, 0.006), (s * 0.2 + (0.2 if torn else 0.0) * s, -0.3, 0.006)]
        straps.append(K.tube(f"strap{s}", pts, 0.025, segs=4, flat=(1.0, 0.18)))
    dz = 0.85 if ctx.worn else 1.0
    # Side bottle pockets, leather-look bottom panel, zip track round the lid, compression straps.
    sides = [K.box("side", (0.05, 0.16, 0.1), center=(s * (W / 2 + 0.012), -0.1, 0.06), bevel=0.02, bevel_segs=1)
             for s in (-1, 1)]
    bottom = K.box("bottom", (W * 0.92, 0.06, D * 0.9 * dz), center=(0, -Lp / 2 + 0.02, D * 0.45 * dz), bevel=0.025,
                   bevel_segs=2)
    zp = [(-W / 2 + 0.03, -Lp / 2 + 0.06), (-W / 2 + 0.035, Lp / 2 - 0.08), (-0.06, Lp / 2 - 0.035),
          (0.06, Lp / 2 - 0.035), (W / 2 - 0.035, Lp / 2 - 0.08), (W / 2 - 0.03, -Lp / 2 + 0.06)]
    zipper = K.sweep("zip", [(x, y, D * dz + 0.004) for x, y in zp], [(-0.006, -0.002), (0.006, -0.002), (0.006, 0.002),
                                                                      (-0.006, 0.002)], up=(0, 0, 1))
    comp = []
    for x in (-0.07, 0.07):
        comp.append(K.tube("cstrap", [(x, -Lp / 2 + 0.01, D * 0.5 * dz), (x, -0.2, D * dz + 0.004), (x, 0.03, D * dz + 0.03),
                                      (x, 0.06, D * dz + 0.01)], 0.012, segs=4, flat=(1.0, 0.2)))
    ctx.add(body, "canvas_navy", uv_scale=1.0, smooth=50, patches=0.0, edge=0.5)
    ctx.add(pocket, "canvas_khaki", uv_scale=1.0, smooth=50, patches=0.0, edge=0.5)
    for o in sides:
        ctx.add(o, "canvas_khaki", uv_scale=1.0, smooth=50, patches=0.0, edge=0.5)
    ctx.add(bottom, "leather_dark", uv_scale=1.0, smooth=45, patches=0.2, edge=0.6)
    ctx.add(handle, "plastic_black", uv_scale=1.0, smooth=40, wear=0.2)
    for s in straps + comp + [zipper]:
        ctx.add(s, "plastic_black", uv_scale=1.0, smooth=40, wear=0.2)
    ctx.col_box((-W / 2, -Lp / 2, 0), (W / 2, Lp / 2, D + 0.05))


def bucket(ctx: K.Ctx) -> None:
    """Galvanised steel pail with wire bail. Worn: dented and rusty. Destroyed: stomped flat,
    lying on its side."""
    r = ctx.rnd("bucket")
    b = P.bucket("bucket", top_r=0.15, bot_r=0.125, h=0.29, segs=16)
    ears = [K.box("ear", (0.02, 0.012, 0.03), center=(s * 0.155, 0, 0.265)) for s in (-1, 1)]
    if ctx.destroyed:
        bail_pts = [(-0.155, 0, 0.265), (-0.2, -0.06, 0.2), (-0.12, -0.18, 0.12), (0.05, -0.2, 0.1), (0.155, 0, 0.265)]
    else:
        lean = 0.0 if ctx.clean else 0.12
        bail_pts = [(-0.155, 0, 0.265)]
        for k in range(1, 8):
            a = math.pi * k / 8
            bail_pts.append((-0.155 * math.cos(a), -lean * math.sin(a), 0.265 + 0.155 * math.sin(a) * (1 - lean)))
        bail_pts.append((0.155, 0, 0.265))
    bail = K.tube("bail", bail_pts, 0.0035, segs=5, caps=False)
    group = [b] + ears + [bail]
    if ctx.worn:
        dr = ctx.drnd("dents")
        for k in range(2 if not ctx.destroyed else 4):
            a = dr.uniform(0, math.tau)
            K.dent(b, (math.cos(a) * 0.15, math.sin(a) * 0.15, dr.uniform(0.08, 0.24)), 0.07, 0.015)
    if ctx.destroyed:
        for o in group:
            K.map_verts(o, lambda co: Vector((co.x, co.y * 0.55, co.z)))
            K.place(o, rot=(90, 0, 30))
        for o in group:
            K.lift_min(o)
        zmin = min(min(v.co.z for v in o.data.vertices) for o in group)
        for o in group:
            K.place(o, (0, 0, -zmin))
    ctx.add(b, "metal_galvanized", uv="cyl", uv_axis=2 if not ctx.destroyed else 1, uv_scale=1.0, smooth=45,
            patches=0.6, low=0.5, low_h=0.1)
    for e in ears:
        ctx.add(e, "metal_galvanized", uv_scale=1.0)
    ctx.add(bail, "metal_galvanized", uv_scale=1.0, smooth=40)
    if ctx.destroyed:
        ctx.col_hull([b], max_points=32)
    else:
        ctx.col_hull([(math.cos(a) * 0.158, math.sin(a) * 0.158, z) for a in [i * math.tau / 10 for i in range(10)]
                      for z in (0.0, 0.29)])


def gas_can(ctx: K.Ctx) -> None:
    """5-gallon plastic jerry can with carry handle, spout and vent. Worn: sun-faded, grimy, cap
    missing. Destroyed: knocked over, split and crumpled."""
    r = ctx.rnd("gascan")
    L, W, H = 0.36, 0.19, 0.29
    body = K.box("can", (L, W, H), center=(0, 0, H / 2), bevel=0.03, bevel_segs=2, cuts=(2, 0, 2))
    # Moulded side panels (shallow recess).
    K.map_verts(body, lambda co: Vector((co.x, co.y * (0.97 if abs(co.x) < L / 2 - 0.05 and 0.05 < co.z < H - 0.05 else 1.0), co.z)))
    posts = [K.box("post", (0.03, 0.04, 0.05), center=(s * 0.085, 0.0, H + 0.02), bevel=0.008) for s in (-1, 1)]
    bar = K.box("bar", (0.2, 0.04, 0.028), center=(0, 0, H + 0.052), bevel=0.01)
    neck = K.cyl("neck", 0.022, 0.045, segs=10, center=(0.135, 0, H + 0.012))
    cap = K.cyl("cap", 0.027, 0.028, segs=10, center=(0.135, 0, H + 0.045), bevel=0.003)
    vent = K.cyl("vent", 0.01, 0.02, segs=8, center=(-0.145, 0.0, H + 0.005))
    # Moulded X stiffening ribs on both flanks.
    ribs = []
    for s in (-1, 1):
        for a in (38.0, -38.0):
            rib = K.box("rib", (0.3, 0.008, 0.022), center=(0, 0, 0), bevel=0.003)
            K.place(rib, rot=(0, a, 0))
            K.place(rib, (0, s * (W / 2 - 0.002), H / 2))
            ribs.append(rib)
    hard = [body] + posts + [bar, neck, vent] + ribs
    caps = [cap] if not ctx.worn else []
    allp = hard + caps
    if ctx.destroyed:
        dr = ctx.drnd("can")
        K.dent(body, (0.0, -W / 2, H * 0.5), 0.16, 0.05)
        K.crumple(body, 0.012, scale=8.0, seed=dr.randint(0, 999))
        for o in allp:
            K.place(o, rot=(-90, 0, 20))
        zmin = min(min(v.co.z for v in o.data.vertices) for o in allp)
        for o in allp:
            K.place(o, (0, 0, -zmin))
    elif ctx.worn:
        K.crumple(body, 0.004, scale=8.0, seed=r.randint(0, 999))
    plastic = "plastic_red"
    ctx.add(body, plastic, uv_scale=1.0, smooth=40, patches=0.0, edge=0.6)
    for o in posts + [bar] + ribs:
        ctx.add(o, plastic, uv_scale=1.0, smooth=40, patches=0.0, edge=0.6)
    ctx.add(neck, plastic, uv="cyl", uv_scale=1.0, smooth=40)
    ctx.add(vent, "plastic_black", uv="cyl", uv_scale=1.0, smooth=40)
    for c in caps:
        ctx.add(c, "plastic_yellow", uv="cyl", uv_scale=1.0, smooth=40)
    if ctx.destroyed:
        ctx.col_hull([body], max_points=32)
    else:
        ctx.col_box((-L / 2, -W / 2, 0), (L / 2, W / 2, H + 0.07))


def propane_tank_small(ctx: K.Ctx) -> None:
    """20 lb barbecue cylinder: domed tank, foot ring, protective collar with hand holes, valve.
    Worn: rust bloom at the base and collar, grime."""
    R = 0.152
    prof = [(0.0, 0.032), (0.07, 0.035), (0.118, 0.048), (0.143, 0.068), (R, 0.1), (R, 0.17), (R, 0.24), (R, 0.31),
            (0.147, 0.34), (0.13, 0.37), (0.1, 0.395), (0.06, 0.41), (0.0, 0.415)]
    tank = K.lathe("tank", prof, segs=18)
    foot = K.lathe("foot", [(0.115, 0.0), (0.118, 0.0), (0.118, 0.05), (0.112, 0.05)], segs=18,
                   cap_bottom=False, cap_top=False)
    K.solidify(foot, 0.003)
    collar = K.lathe("collar", [(0.1, 0.38), (0.1, 0.455), (0.1, 0.505), (0.1, 0.52)], segs=18, cap_bottom=False,
                     cap_top=False)
    # Hand holes on two sides of the collar.
    K.delete_faces(collar, lambda c, n: 0.455 < c.z < 0.505 and abs(c.y) > 0.085)
    K.solidify(collar, 0.003)
    valve = K.cyl("valve", 0.018, 0.07, segs=10, center=(0, 0, 0.45))
    wheel = K.tube("wheel", [(math.cos(a) * 0.028, math.sin(a) * 0.028, 0.49) for a in [i * math.tau / 10 for i in range(10)]],
                   0.005, segs=5, closed=True)
    outlet = K.cyl("outlet", 0.011, 0.04, segs=8, axis="X", center=(0.03, 0, 0.455))
    ctx.add(tank, "paint_white", uv="cyl", uv_scale=1.0, smooth=45, patches=0.5, low=0.8, low_h=0.12)
    ctx.add(foot, "paint_white", uv="cyl", uv_scale=1.0, smooth=45, patches=0.6, low=1.0, low_h=0.06)
    ctx.add(collar, "paint_white", uv="cyl", uv_scale=1.0, smooth=45, patches=0.6)
    for o in (valve, outlet):
        ctx.add(o, "chrome_pitted", uv="cyl", uv_scale=1.0, smooth=40)
    ctx.add(wheel, "paint_black", uv_scale=1.0, smooth=40)
    ctx.col_hull([(math.cos(a) * R, math.sin(a) * R, z) for a in [i * math.tau / 10 for i in range(10)] for z in (0.0, 0.42)]
                 + [(0, 0, 0.52)])


def tire(ctx: K.Ctx) -> None:
    """Dumped car tyre lying flat. Worn: cut and squashed, sidewall cracked (grimier)."""
    r = ctx.rnd("tire")
    # Closed cross-section: bead, flat sidewall, square shoulder, grooved tread, shoulder, sidewall,
    # bead, inner liner.
    prof = [(0.19, 0.03), (0.205, 0.008), (0.26, 0.0), (0.3, 0.004), (0.317, 0.016), (0.323, 0.036),
            (0.323, 0.062), (0.316, 0.064), (0.316, 0.07), (0.323, 0.072), (0.323, 0.128), (0.316, 0.13),
            (0.316, 0.136), (0.323, 0.138), (0.323, 0.164), (0.317, 0.184), (0.3, 0.196), (0.26, 0.2),
            (0.205, 0.192), (0.19, 0.17), (0.18, 0.15), (0.2, 0.12), (0.2, 0.08), (0.18, 0.05)]
    t = K.lathe("tyre", prof, segs=22, close_profile=True)
    if ctx.worn:
        K.map_verts(t, lambda co: Vector((co.x * 1.06, co.y * 0.93, co.z)))
        K.delete_faces(t, lambda c, n: c.z > 0.15 and -0.12 < math.atan2(c.y, c.x) < 0.12)
        K.place(t, rot=(4, -3, 0))
        K.lift_min(t)
    ctx.add(t, "tyre_rubber", uv="cyl", uv_axis=2, uv_scale=1.0, smooth=50, patches=0.0, edge=0.0)
    ctx.col_hull([(math.cos(a) * 0.32, math.sin(a) * 0.32, z) for a in [i * math.tau / 12 for i in range(12)] for z in (0.0, 0.2)])


BUILDERS = {
    "barrel_metal": barrel_metal,
    "cardboard_box": cardboard_box,
    "cardboard_box_open": cardboard_box_open,
    "pallet": pallet,
    "crate_wood": crate_wood,
    "trash_bag": trash_bag,
    "trash_pile": trash_pile,
    "debris_pile": debris_pile,
    "plank_pile": plank_pile,
    "plaster_chunks": plaster_chunks,
    "glass_shards": glass_shards,
    "paper_scatter": paper_scatter,
    "cans_scatter": cans_scatter,
    "bottles_scatter": bottles_scatter,
    "books_scatter": books_scatter,
    "clothes_pile": clothes_pile,
    "toolbox": toolbox,
    "duffel_bag": duffel_bag,
    "backpack_dropped": backpack_dropped,
    "bucket": bucket,
    "gas_can": gas_can,
    "propane_tank_small": propane_tank_small,
    "tire": tire,
}


def build(params: dict, outputs: list[str]) -> None:
    K.run(params, outputs, BUILDERS)
