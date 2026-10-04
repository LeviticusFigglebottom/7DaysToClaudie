"""Exterior props family — street furniture and yard props of a 1990s logging town: utility pole,
street lamp, road signs, rural mailbox, fences, dumpster, picnic table, hydrant, bench, sawhorse
barricade, jersey barrier, woodpile, wheelbarrow, hand well pump, shopping cart, bicycle, payphone.

Front faces -Y; fence sections run along X (2.0 m, origin at the bottom centre of the line).
No text or logos: signs use the paint_red_sign atlas (blank faces), flyers use paper_trash."""
from __future__ import annotations

import math

import bmesh
from mathutils import Matrix, Vector

from lib import props_ext_kit as K
from lib import props_ext_parts as P


def _inset_rect(rect, mx: float, my: float | None = None):
    """Shrinks an atlas rect by fractions of its own size (mx horizontally, my vertically)."""
    my = mx if my is None else my
    u0, v0, u1, v1 = rect
    w, h = u1 - u0, v1 - v0
    return (u0 + w * mx, v0 + h * my, u1 - w * mx, v1 - h * my)


def _lean(objs, angle_x: float = 0.0, angle_y: float = 0.0, pivot=(0, 0, 0)):
    """Rotates parts about a ground pivot (leaning posts, tilted poles)."""
    p = Vector(pivot)
    m = Matrix.Translation(p) @ K.rot_matrix((angle_x, angle_y, 0)) @ Matrix.Translation(-p)
    for o in objs:
        o.data.transform(m)
        o.data.update()


def _flyers(ctx, r, n: int, radius: float, z0: float, z1: float, *, center=(0.0, 0.0), torn: bool = False):
    """Faded paper notices stapled around a pole (illegible: paper_trash atlas)."""
    cells = [K.ATLAS_PAPER["flyer"], K.ATLAS_PAPER["note"], K.ATLAS_PAPER["news"]]
    for i in range(n):
        a = r.uniform(-1.2, 1.2) + math.pi * 1.5  # mostly facing the street (-Y)
        w, h = r.uniform(0.18, 0.24), r.uniform(0.24, 0.3)
        if torn and i % 2:
            h *= 0.55
        z = r.uniform(z0, z1)
        sheet = K.quad_sheet(f"flyer{i}", (-w / 2, 0, -h / 2), (w / 2, 0, -h / 2), (w / 2, 0, h / 2), (-w / 2, 0, h / 2), 3, 2)
        K.uv_planar(sheet, 1, rect=cells[i % 3])
        # Wrap around the pole: bend the sheet onto the cylinder.
        def wrap(co, rad=radius):
            ang = co.x / rad
            return Vector((math.sin(ang) * (rad + 0.002), -math.cos(ang) * (rad + 0.002), co.z))
        K.map_verts(sheet, wrap)
        K.crumple(sheet, 0.004, scale=12.0, seed=r.randint(0, 999))
        K.place(sheet, (center[0], center[1], z), (0, 0, math.degrees(a) - 270 + r.uniform(-15, 15)))
        ctx.add(sheet, "paper_trash", uv=None, smooth=40, patches=0.0, edge=0.0)


# ============================================================================================
# Utility pole
# ============================================================================================

def utility_pole(ctx: K.Ctx) -> None:
    """Creosoted wood pole (10.5 m) with crossarm, braces, glass insulators, pole transformer,
    secondary rack, step bolts, ground wire and stapled flyers. Worn: leaning, crossarm skewed,
    an insulator gone, a cut line dangling down the pole."""
    r = ctx.rnd("pole")
    H = 10.5
    pole = K.cyl("pole", 0.15, H, segs=10, center=(0, 0, H / 2), r_top=0.11, cuts=8)
    parts = []
    ctx.add(pole, "wood_creosote", uv="cyl", uv_scale=1.0, smooth=50, patches=0.3, low=0.6, low_h=1.0,
            moss=0.3)
    parts.append(pole)
    arm_z = H - 0.6
    arm = P.plank("crossarm", 2.44, 0.11, 0.09, cuts=2)
    ctx.add(arm, "wood_weathered", long_axis=0, patches=0.3, at=((0, -0.16, arm_z), None))
    parts.append(arm)
    for s in (-1, 1):
        br = K.tube("brace", [(s * 0.62, -0.16, arm_z - 0.04), (0.0, -0.13, arm_z - 0.62)], 0.012, segs=4, flat=(1.0, 0.3))
        ctx.add(br, "metal_galvanized", uv_scale=1.0, wear=0.8)
        parts.append(br)
    ins_x = [-1.05, -0.35, 1.05]
    if ctx.worn:
        ins_x = [-1.05, 1.05]
    for x in ins_x:
        pin = K.cyl("pin", 0.012, 0.08, segs=6, center=(x, -0.16, arm_z + 0.08))
        ins = K.lathe("insulator", [(0.0, 0.0), (0.055, 0.0), (0.06, 0.03), (0.04, 0.05), (0.05, 0.075),
                                    (0.03, 0.1), (0.022, 0.13), (0.0, 0.135)], segs=10)
        K.place(ins, (x, -0.16, arm_z + 0.1))
        ctx.add(pin, "metal_galvanized", uv_scale=1.0)
        ctx.add(ins, "glass_green", uv="cyl", uv_scale=1.0, smooth=50, wear=0.2)
        parts += [pin, ins]
    # Transformer can on a bracket.
    tz = H - 2.0
    can = K.lathe("xfmr", [(0.0, 0.0), (0.22, 0.0), (0.24, 0.03), (0.24, 0.78), (0.25, 0.8), (0.2, 0.86), (0.0, 0.88)], segs=14)
    K.place(can, (0, -0.42, tz))
    ctx.add(can, "paint_grey", uv="cyl", uv_scale=1.0, smooth=45, patches=0.5)
    for k, x in enumerate((-0.1, 0.1)):
        bush = K.lathe("bushing", [(0.0, 0.0), (0.03, 0.0), (0.03, 0.04), (0.022, 0.06), (0.03, 0.08), (0.02, 0.1), (0.0, 0.11)], segs=8)
        K.place(bush, (x, -0.42, tz + 0.88))
        ctx.add(bush, "plastic_grey", uv="cyl", uv_scale=1.0, smooth=40, wear=0.2)
    brk = K.box("bracket", (0.12, 0.3, 0.6), center=(0, -0.22, tz + 0.4))
    ctx.add(brk, "metal_galvanized", uv_scale=1.0)
    parts += [can, brk]
    # Secondary rack with spools.
    rack = K.box("rack", (0.05, 0.03, 0.7), center=(0, -0.15, tz - 0.7))
    ctx.add(rack, "metal_galvanized", uv_scale=1.0)
    for k in range(3):
        sp = K.cyl("spool", 0.035, 0.06, segs=8, axis="Y", center=(0, -0.2, tz - 0.95 + k * 0.22))
        ctx.add(sp, "plastic_white", uv_scale=1.0)
    # Cut drop line hanging down the pole (worn) or a short stub (clean).
    if ctx.worn:
        pts = [(0.02, -0.25, tz - 0.95)]
        for k in range(1, 10):
            t = k / 9
            pts.append((0.05 + 0.25 * math.sin(t * 2.5), -0.25 - 0.4 * t, (tz - 0.95) * (1 - t) + 0.05 * t))
        line = K.tube("dropline", pts, 0.008, segs=4)
        ctx.add(line, "rubber_black", uv_scale=1.0, wear=0.2)
    for k in range(9):
        z = 2.4 + k * 0.42
        s = 1 if k % 2 else -1
        bolt = K.cyl("step", 0.011, 0.2, segs=5, axis="X", center=(s * 0.18, 0, z))
        ctx.add(bolt, "metal_galvanized", uv_scale=1.0, wear=0.8)
    gw = K.cyl("ground", 0.005, H - 0.7, segs=4, center=(0.0, 0.152, (H - 0.7) / 2))
    ctx.add(gw, "chrome_pitted", uv_scale=1.0)
    _flyers(ctx, ctx.rnd("flyers"), 4 if ctx.clean else 6, 0.142, 1.3, 1.8, torn=ctx.worn)
    if ctx.worn:
        _lean(ctx.parts, 3.5, -1.5)
    ctx.col_box((-0.16, -0.16, 0), (0.16, 0.16, H))


# ============================================================================================
# Street lamp (light)
# ============================================================================================

def street_lamp(ctx: K.Ctx) -> None:
    """Galvanised davit pole on a concrete footing with a cobra-head luminaire over the road (-Y).
    Worn: lens smashed, base rusted, pole slightly out of plumb. Destroyed: hit by a vehicle —
    pole buckled near the base, head hanging near the ground."""
    r = ctx.rnd("lamp")
    H = 7.6
    base = K.cyl("footing", 0.26, 0.3, segs=12, center=(0, 0, 0.15), bevel=0.02)
    plate = K.box("plate", (0.3, 0.3, 0.025), center=(0, 0, 0.3125), bevel=0.004)
    nuts = [K.cyl("nut", 0.018, 0.04, segs=6, center=(sx * 0.11, sy * 0.11, 0.345)) for sx in (-1, 1) for sy in (-1, 1)]
    pole = K.cyl("pole", 0.085, H - 0.33, segs=10, center=(0, 0, 0.325 + (H - 0.33) / 2), r_top=0.055, cuts=6)
    arm_pts = [(0, 0, H - 0.4), (0, -0.05, H - 0.05), (0, -0.25, H + 0.2), (0, -0.7, H + 0.32), (0, -1.6, H + 0.38)]
    arm = K.tube("arm", arm_pts, 0.04, segs=8)
    head = K.lathe("head", [(0.0, -0.35), (0.12, -0.33), (0.2, -0.2), (0.22, 0.0), (0.2, 0.2), (0.14, 0.36), (0.0, 0.42)], segs=12)
    K.map_verts(head, lambda co: Vector((co.x * 1.0, co.y * 0.55, co.z)))  # flattened teardrop
    K.place(head, rot=(90, 0, 0))
    K.map_verts(head, lambda co: Vector((co.x, co.y, co.z * 0.55 if co.z > 0 else co.z * 0.35)))
    K.place(head, (0, -1.98, H + 0.38))
    lens = K.blob("lens", 0.5, subdiv=2, scale=(0.3, 0.55, 0.12), center=(0, -2.0, H + 0.33))
    K.cut_plane(lens, (0, 0, H + 0.335), (0, 0, 1), keep="below")
    lamp_parts = [arm, head, lens]
    if ctx.destroyed:
        # Buckled at 0.9 m by an impact: everything above folds over towards +X.
        K.kink([pole] + lamp_parts, (0, 0, 0.9), (0, 62, 15), blend=0.12)
        K.map_verts(pole, lambda co: Vector((co.x + 0.05 * max(0.0, 1 - abs(co.z - 0.9) * 5), co.y, co.z)))
    ctx.add(base, "concrete_barrier", uv_scale=1.0, smooth=40, patches=0.3)
    ctx.add(plate, "metal_galvanized", uv_scale=1.0, low=1.0, low_h=0.6)
    for n in nuts:
        ctx.add(n, "metal_galvanized", uv_scale=1.0, wear=1.0)
    ctx.add(pole, "metal_galvanized", uv="cyl", uv_scale=1.0, smooth=50, patches=0.4, low=1.0, low_h=1.2)
    ctx.add(arm, "metal_galvanized", uv_scale=1.0, smooth=50, patches=0.4)
    ctx.add(head, "paint_grey", uv_scale=1.0, smooth=40, patches=0.5)
    if not ctx.worn:
        ctx.add(lens, "lamp_glow", uv_scale=1.0, smooth=50, wear=0.0, ao=False)
    else:
        # Smashed refractor: a few shards left in the rim.
        K.jagged_hole(lens, (0, -2.0, H + 0.3), 0.22, r.randint(0, 999), axis=2)
        ctx.add(lens, "glass_clear", uv_scale=1.0, smooth=50, wear=0.0)
    _flyers(ctx, ctx.rnd("flyers"), 3, 0.082, 1.3, 1.75, torn=ctx.worn)
    if ctx.worn and not ctx.destroyed:
        _lean(ctx.parts[3:], 0.0, 2.0)
    ctx.col_box((-0.27, -0.27, 0), (0.27, 0.27, 0.3))
    if ctx.destroyed:
        ctx.col_hull([pole], max_points=24)
    else:
        ctx.col_box((-0.09, -0.09, 0.3), (0.09, 0.09, H))


# ============================================================================================
# Road signs
# ============================================================================================

def _uchannel_post(name: str, h: float) -> object:
    prof = [(-0.04, 0.0), (0.04, 0.0), (0.04, 0.012), (0.026, 0.012), (0.026, 0.028), (0.04, 0.028), (0.04, 0.035),
            (0.02, 0.035), (0.016, 0.016), (-0.016, 0.016), (-0.02, 0.035), (-0.04, 0.035), (-0.04, 0.028),
            (-0.026, 0.028), (-0.026, 0.012), (-0.04, 0.012)]
    o = K.prism(name, prof, h, plane="XY", offset=0.0)
    K.place(o, (0, 0.006, 0))
    return o


def _sign(ctx, kind: str, *, post_h: float, face_w: float, face_h: float, cell: str) -> None:
    r = ctx.rnd("sign")
    dr = ctx.drnd("sign")
    post = _uchannel_post("post", post_h + face_h * 0.85)
    if kind == "stop":
        rad = face_w / 2 / math.cos(math.pi / 8)
        outline = [(rad * math.cos(math.pi / 8 + k * math.pi / 4), rad * math.sin(math.pi / 8 + k * math.pi / 4))
                   for k in range(8)]
        m = 6.0 / 512.0
        rect = _inset_rect(K.ATLAS_SIGN[cell], m)
    else:
        outline = [(-face_w / 2, -face_h / 2), (face_w / 2, -face_h / 2), (face_w / 2, face_h / 2), (-face_w / 2, face_h / 2)]
        rect = _inset_rect(K.ATLAS_SIGN[cell], 56.0 / 512.0, 6.0 / 512.0)
    cz = post_h + face_h / 2
    plate = K.prism("plate", outline, 0.003, plane="XZ", offset=0.0)
    bm = bmesh.new()
    vs = [bm.verts.new((x, -0.0021, z)) for x, z in outline]
    bm.faces.new(vs)  # CCW in (x, z) seen from -Y: normal faces the street (-Y)
    face = K._obj_raw("face", bm)
    K.uv_planar(face, 1, rect=rect)
    bolts = [K.cyl("bolt", 0.012, 0.012, segs=6, axis="Y", center=(0, -0.008, dz)) for dz in (-face_h * 0.36, face_h * 0.36)]
    sign_parts = [plate, face] + bolts
    for o in sign_parts:
        K.place(o, (0, -0.005, cz))
    if ctx.worn:
        # Bent plate and twisted on its post.
        for o in sign_parts:
            K.map_verts(o, lambda co: Vector((co.x, co.y + 0.02 * ((co.x / (face_w / 2)) ** 2) * (1 if co.z > cz else 0.4), co.z)))
            K.place(o, (0, 0, -cz))
            K.place(o, rot=(0, 0, 13 if kind == "stop" else -9))
            K.place(o, (0, 0, cz))
    allp = [post] + sign_parts
    if ctx.destroyed:
        K.kink(allp, (0, 0, 0.35), (-68, 0, 12))
    elif ctx.worn:
        _lean(allp, -6.0, 3.0)
    ctx.add(post, "metal_galvanized", uv_scale=1.0, patches=0.5, low=0.8, low_h=0.5)
    ctx.add(plate, "metal_galvanized", uv_scale=1.0, patches=0.3)
    ctx.add(face, "paint_red_sign", uv=None, wear=0.0)
    for b in bolts:
        ctx.add(b, "metal_galvanized", uv_scale=1.0, wear=1.0)
    if ctx.destroyed:
        ctx.col_hull([post] + sign_parts, max_points=24)
    else:
        ctx.col_box((-0.05, -0.05, 0), (0.05, 0.05, post_h + face_h))


def road_sign_stop(ctx: K.Ctx) -> None:
    """Blank stop sign (red octagon, white border, no text) on a U-channel post. Worn: faded,
    shot up, bent and twisted. Destroyed: post folded over by an impact."""
    _sign(ctx, "stop", post_h=2.1, face_w=0.76, face_h=0.76, cell="stop_worn" if ctx.worn else "stop")


def road_sign_speed(ctx: K.Ctx) -> None:
    """Blank regulatory sign (white, black border, no legend) on a U-channel post."""
    _sign(ctx, "speed", post_h=2.1, face_w=0.61, face_h=0.76, cell="blank_worn" if ctx.worn else "blank")


# ============================================================================================
# Rural mailbox (container: desk)
# ============================================================================================

def _mailbox_outline(w: float = 0.165, h: float = 0.115, n: int = 8) -> list[tuple[float, float]]:
    pts = [(-w / 2, 0.0), (w / 2, 0.0)]
    for k in range(n + 1):
        a = math.pi * k / n
        pts.append((math.cos(a) * w / 2, h + math.sin(a) * w / 2))
    return pts


def mailbox_rural(ctx: K.Ctx) -> None:
    """Galvanised tunnel mailbox on a 4x4 post with a red flag. Worn: door hanging open, rusty,
    post leaning. Destroyed: post snapped, box knocked into the ditch and crushed."""
    r = ctx.rnd("mailbox")
    post_h = 1.0
    L = 0.48
    post = P.plank("post", post_h, 0.089, 0.089, cuts=3)
    K.uv_box(post, 1.0, long_axis=0, offset=(0.3, 1.7))  # grain along the post
    K.orient(post, "z", "-y")
    K.place(post, (0, 0, post_h / 2))
    shelf = P.plank("shelf", 0.5, 0.14, 0.028)
    K.uv_box(shelf, 1.0, long_axis=0, offset=(2.1, 0.4))
    K.orient(shelf, "y", "z", (0, -0.03, post_h + 0.014))
    out = _mailbox_outline()
    box = K.prism("box", out, L, plane="XZ", offset=0.0)
    K.delete_faces(box, lambda c, n: n.y < -0.9)  # open front (door covers it)
    K.solidify(box, 0.002, offset=-1.0)
    K.place(box, (0, -0.03, post_h + 0.028))
    door = K.prism("door", out, 0.004, plane="XZ")
    door_pivot = Vector((0, -0.03 - L / 2 - 0.002, post_h + 0.028))
    K.place(door, door_pivot)
    latch = K.box("latch", (0.03, 0.01, 0.02), center=(0, door_pivot.y - 0.006, post_h + 0.028 + 0.17))
    flag = K.prism("flag", [(0.0, 0.0), (0.12, 0.0), (0.12, 0.06), (0.05, 0.06), (0.05, 0.16), (0.0, 0.16)], 0.004, plane="YZ")
    K.place(flag, rot=(0, 0, 0))
    K.place(flag, (0.085, -0.13, post_h + 0.08))
    box_parts = [box, door, latch, flag]
    if ctx.worn and not ctx.destroyed:
        # Door hangs open on its bottom hinge.
        for o in (door, latch):
            K.place(o, -door_pivot)
            K.place(o, rot=(-100, 0, 0))
            K.place(o, door_pivot)
        dr = ctx.drnd("dent")
        K.dent(box, (0.08, -0.1, post_h + 0.16), 0.1, 0.02)
        _lean([post, shelf] + box_parts, -7.0, 4.0)
    if ctx.destroyed:
        P.break_end(post, 0.3, ctx.drnd("snap"), side=1, depth=0.05, axis=2)
        stub = P.plank("post_top", 0.6, 0.089, 0.089, cuts=2)
        P.break_end(stub, -0.25, ctx.drnd("snap2"), side=-1, depth=0.05)
        ctx.add(stub, "wood_weathered", long_axis=0, moss=0.4, patches=0.4, at=((0.25, 0.45, 0.045), (0, 0, 25)))
        for o in box_parts + [shelf]:
            K.place(o, (0, 0.03, -(post_h + 0.028)))
            K.place(o, rot=(0, -96, 50))
            K.place(o, (-0.35, 0.3, 0.09))
            K.lift_min(o)
        K.dent(box, (-0.25, 0.32, 0.18), 0.15, 0.05)
    ctx.add(post, "wood_weathered", uv=None, moss=0.4, patches=0.4)
    ctx.add(shelf, "wood_weathered", uv=None, moss=0.4, patches=0.4)
    ctx.add(box, "metal_galvanized", uv_scale=1.0, smooth=40, patches=0.6, low=0.0)
    ctx.add(door, "metal_galvanized", uv_scale=1.0, patches=0.6)
    ctx.add(latch, "metal_galvanized", uv_scale=1.0)
    ctx.add(flag, "paint_red", uv_scale=1.0, patches=0.4)
    if ctx.destroyed:
        ctx.col_box((-0.6, -0.1, 0), (0.3, 0.7, 0.3))
    else:
        ctx.col_box((-0.1, -0.3, 0), (0.1, 0.25, post_h + 0.3))


# ============================================================================================
# Fences (2.0 m sections along X)
# ============================================================================================

def _post4x4(name, h):
    p = P.plank(name, h, 0.089, 0.089, cuts=4)
    K.orient(p, "z", "-y")
    K.place(p, (0, 0, h / 2))
    return p


def fence_picket_2m(ctx: K.Ctx) -> None:
    """White picket fence section: two 4x4 posts, two rails, 13 pointed pickets. Worn: peeling to
    grey wood, pickets missing or hanging, a rail sagging. Destroyed: knocked flat."""
    mat = "paint_white_wood"
    L = 2.0
    ph = 1.15
    parts_static = []
    for s in (-1, 1):
        p = _post4x4("post", ph)
        K.place(p, (s * (L / 2 - 0.045), 0.03, 0))
        parts_static.append(("post", p))
    for z in (0.22, 0.78):
        rail = P.plank("rail", L - 0.09, 0.089, 0.038, cuts=4)
        K.orient(rail, "x", "-y", (0, 0.03 - 0.0445 + 0.019 + 0.0, z))
        parts_static.append(("rail", rail))
    n = 13
    pw, pt, phgt = 0.075, 0.019, 1.0
    pickets = []
    gap = (L - 0.09 * 2 - n * pw) / (n + 1)
    missing = set()
    loose = {}
    if ctx.worn:
        dr = ctx.drnd("pickets")
        missing = {3, 4, 9}
        loose = {8: dr.uniform(15, 30), 2: -dr.uniform(10, 20)}
    for i in range(n):
        if i in missing and not ctx.destroyed:
            continue
        x = -L / 2 + 0.09 + gap + pw / 2 + i * (pw + gap)
        rr = ctx.rnd(f"pk{i}")
        outline = [(-pw / 2, 0.0), (pw / 2, 0.0), (pw / 2, phgt - 0.05), (0.0, phgt), (-pw / 2, phgt - 0.05)]
        pk = K.prism(f"picket{i}", outline, pt, plane="XZ")
        K.uv_box(pk, 1.0, long_axis=2, offset=(rr.uniform(0, 5), rr.uniform(0, 5)))
        hgt = rr.uniform(0.02, 0.06)
        K.place(pk, (x, -0.03 + 0.003, hgt))
        if i in loose and not ctx.destroyed:
            piv = Vector((x, -0.04, hgt + 0.78))
            K.place(pk, -piv)
            K.place(pk, rot=(0, loose[i], 0))
            K.place(pk, piv)
            K.lift_min(pk)
        pickets.append(pk)
    allp = [p for _, p in parts_static] + pickets
    if ctx.destroyed:
        # Section pushed over: rotates about the bottom-front edge, posts snapped.
        piv = Vector((0, -0.05, 0.0))
        m = Matrix.Translation(piv) @ K.rot_matrix((-78, 0, 4)) @ Matrix.Translation(-piv)
        for o in allp[2:]:
            o.data.transform(m)
            o.data.update()
        for k, (kind, p) in enumerate(parts_static[:2]):
            P.break_end(p, ctx.drnd(f"snap{k}").uniform(0.25, 0.45), ctx.drnd(f"s{k}"), side=1, depth=0.05, axis=2)
        for o in allp:
            K.lift_min(o)
    elif ctx.worn:
        _lean(allp[2:], -4.0, 0.0)
        K.map_verts(allp[3], lambda co: Vector((co.x, co.y, co.z - 0.05 * max(0.0, 1 - (co.x / 0.95) ** 2))))
    for kind, p in parts_static:
        ctx.add(p, mat, long_axis=2 if kind == "post" else 0, moss=0.35, patches=0.6, edge=0.6)
    for pk in pickets:
        ctx.add(pk, mat, uv=None, moss=0.35, patches=0.6, low=0.6, low_h=0.3, edge=0.4)
    if ctx.destroyed:
        ctx.col_box((-L / 2, -1.1, 0), (L / 2, 0.08, 0.12))
    else:
        ctx.col_box((-L / 2, -0.05, 0), (L / 2, 0.08, 1.05))


def fence_wood_2m(ctx: K.Ctx) -> None:
    """Dog-eared cedar privacy fence (1.8 m). Worn: boards missing/hanging, moss low down, lean.
    Destroyed: smashed through — boards broken out at mid height, rail split."""
    mat = "wood_stained"
    L, Hh = 2.0, 1.8
    posts = []
    for s in (-1, 1):
        p = _post4x4("post", Hh + 0.05)
        K.place(p, (s * (L / 2 - 0.045), 0.05, 0))
        posts.append(p)
    rails = []
    for z in (0.22, 0.95, 1.62):
        rail = P.plank("rail", L - 0.09, 0.089, 0.038, cuts=4)
        K.orient(rail, "x", "-y", (0, 0.05 - 0.0445 + 0.019, z))
        rails.append(rail)
    n = 14
    bw, bt = 0.136, 0.016
    boards = []
    missing, hanging, broken = set(), {}, set()
    if ctx.worn:
        dr = ctx.drnd("boards")
        missing = {5}
        hanging = {9: dr.uniform(6, 14)}
    if ctx.destroyed:
        missing = set()
        broken = {5, 6, 7, 8}
    for i in range(n):
        if i in missing:
            continue
        rr = ctx.rnd(f"bd{i}")
        x = -L / 2 + bw / 2 + i * (L / n) + 0.002
        top = Hh - 0.02 + rr.uniform(-0.01, 0.01)
        outline = [(-bw / 2, 0.0), (bw / 2, 0.0), (bw / 2, top - 0.03), (bw / 2 - 0.03, top), (-bw / 2 + 0.03, top),
                   (-bw / 2, top - 0.03)]
        b = K.prism(f"board{i}", outline, bt, plane="XZ")
        K.uv_box(b, 1.0, long_axis=2, offset=(rr.uniform(0, 5), rr.uniform(0, 5)))
        K.place(b, (x, -0.0, rr.uniform(0.02, 0.05)))
        if i in broken:
            br = ctx.drnd(f"br{i}")
            hz = br.uniform(0.35, 0.6)
            top_piece = K.duplicate(b, f"board{i}_top")
            P.break_end(b, hz, br, side=1, depth=0.12, axis=2)
            P.break_end(top_piece, hz + br.uniform(0.45, 0.7), br, side=-1, depth=0.12, axis=2)
            if i in (6, 7):
                K.remove(top_piece)
            else:
                boards.append(top_piece)
            # broken pieces on the ground behind the fence
            frag = P.plank(f"frag{i}", br.uniform(0.3, 0.6), bw, bt, cuts=1)
            P.break_end(frag, 0.1, br, side=1, depth=0.08)
            ctx.add(frag, mat, long_axis=0, moss=0.3, patches=0.5,
                    at=((x + br.uniform(-0.2, 0.2), -0.35 - br.uniform(0, 0.5), bt / 2), (0, 0, br.uniform(0, 180))))
        if i in hanging:
            piv = Vector((x, 0.0, 1.62))
            K.place(b, -piv)
            K.place(b, rot=(0, hanging[i], 0))
            K.place(b, piv)
            K.lift_min(b)
        boards.append(b)
    if ctx.destroyed:
        P.break_end(rails[1], 0.05, ctx.drnd("rail"), side=1, depth=0.1)
        piece = P.plank("railpiece", 0.7, 0.089, 0.038)
        ctx.add(piece, mat, long_axis=0, moss=0.3, patches=0.5, at=((0.3, -0.6, 0.02), (0, 0, 25)))
    allp = posts + rails + boards
    if ctx.worn and not ctx.destroyed:
        _lean(allp, -3.0, 0.0)
    for p in posts:
        ctx.add(p, mat, long_axis=2, moss=0.45, patches=0.5, low=0.6, low_h=0.4)
    for rl in rails:
        ctx.add(rl, mat, long_axis=0, moss=0.45, patches=0.5)
    for b in boards:
        ctx.add(b, mat, uv=None, moss=0.45, patches=0.5, low=0.7, low_h=0.35)
    ctx.col_box((-L / 2, -0.03, 0), (L / 2, 0.1, Hh))


def fence_chainlink_2m(ctx: K.Ctx) -> None:
    """Galvanised chain-link section (1.85 m): two posts with caps, top rail, tension wire, alpha
    fabric. Worn: fabric sagging and peeled up at a corner, rust. Destroyed: fabric cut and folded
    down, top rail bent, a post kinked."""
    L, Hh = 2.0, 1.85
    posts = []
    for s in (-1, 1):
        p = K.cyl("post", 0.03, Hh, segs=8, center=(s * (L / 2), 0, Hh / 2), cuts=3)
        cap = K.blob("cap", 0.034, subdiv=2, scale=(1, 1, 0.7), center=(s * L / 2, 0, Hh))
        posts += [p, cap]
    rail = K.cyl("toprail", 0.021, L, segs=8, axis="X", center=(0, 0, Hh - 0.04))
    tw = K.tube("tension", [(-L / 2, 0, 0.06), (0, 0.004, 0.05), (L / 2, 0, 0.06)], 0.0035, segs=4)
    nx, nz = 10, 8
    fab = K.quad_sheet("fabric", (-L / 2 + 0.03, 0, 0.04), (L / 2 - 0.03, 0, 0.04), (L / 2 - 0.03, 0, Hh - 0.05),
                       (-L / 2 + 0.03, 0, Hh - 0.05), nx, nz)
    # 1 texture tile = 0.5 m (foliage shader has no uv_scale).
    me = fab.data
    uvl = me.uv_layers.active
    for li in range(len(uvl.data)):
        u, v = uvl.data[li].uv
        uvl.data[li].uv = (u * 2.0, v * 2.0)
    dr = ctx.drnd("fabric")
    if ctx.worn and not ctx.destroyed:
        def sag(co):
            fx = max(0.0, 1 - (co.x / (L / 2)) ** 2)
            fz = max(0.0, 1 - ((co.z - Hh / 2) / (Hh / 2)) ** 2)
            co.y -= 0.12 * fx * fz
            # bottom corner peeled up and out
            if co.x > 0.35 and co.z < 0.6:
                t = min(1.0, (co.x - 0.35) / 0.6) * (1 - co.z / 0.6)
                co.y -= 0.35 * t
                co.z += 0.25 * t
            return co
        K.map_verts(fab, sag)
        K.map_verts(rail, lambda co: Vector((co.x, co.y, co.z - 0.05 * max(0.0, 1 - (co.x / (L / 2)) ** 2))))
        _lean(posts[:2], -3.0, 0.0)
    if ctx.destroyed:
        # Cut along the left post and folded down towards the street.
        def fold(co):
            t = (co.x + L / 2) / L
            ang = math.radians(75) * t
            z = co.z
            co.y -= math.sin(ang) * z * 0.9
            co.z = math.cos(ang) * z * 0.9 + 0.02
            return co
        K.map_verts(fab, fold)
        K.crumple(fab, 0.03, scale=3.0, seed=dr.randint(0, 999))
        K.map_verts(rail, lambda co: Vector((co.x, co.y - 0.12 * max(0.0, 1 - (co.x / (L / 2)) ** 2),
                                             co.z - 0.35 * max(0.0, 1 - (co.x / (L / 2)) ** 2))))
        K.kink(posts[2:], (L / 2, 0, 0.5), (-14, -8, 0), blend=0.1)
    for o in posts:
        ctx.add(o, "metal_galvanized", uv="cyl", uv_scale=1.0, smooth=50, patches=0.5, low=0.8, low_h=0.4)
    ctx.add(rail, "metal_galvanized", uv="cyl", uv_axis=0, uv_scale=1.0, smooth=50, patches=0.5)
    ctx.add(tw, "metal_galvanized", uv_scale=1.0, smooth=50)
    ctx.add(fab, "chainlink", uv=None, smooth=60, wear=0.0, ao=False)
    if ctx.destroyed:
        ctx.col_box((-L / 2 - 0.04, -0.04, 0), (-L / 2 + 0.04, 0.04, Hh))
        ctx.col_box((L / 2 - 0.15, -0.3, 0), (L / 2 + 0.04, 0.04, Hh))
    else:
        ctx.col_box((-L / 2, -0.04, 0), (L / 2, 0.04, Hh))


def fence_post(ctx: K.Ctx) -> None:
    """Lone 4x4 fence post (1.4 m) with a pyramid cap and a nailed rail stub. Worn: leaning,
    cracked, moss."""
    h = 1.4
    p = _post4x4("post", h)
    cap = K.loft("cap", [[(-0.05, -0.05, h), (0.05, -0.05, h), (0.05, 0.05, h), (-0.05, 0.05, h)],
                         [(-0.05, -0.05, h + 0.015), (0.05, -0.05, h + 0.015), (0.05, 0.05, h + 0.015), (-0.05, 0.05, h + 0.015)],
                         [(-0.003, -0.003, h + 0.05), (0.003, -0.003, h + 0.05), (0.003, 0.003, h + 0.05), (-0.003, 0.003, h + 0.05)]])
    stub = P.plank("stub", 0.35, 0.089, 0.038, cuts=1)
    P.break_end(stub, 0.12, ctx.rnd("stub"), side=1, depth=0.06)
    K.orient(stub, "x", "-y", (0.17, -0.064, 0.9))
    parts = [p, cap, stub]
    if ctx.worn:
        _lean(parts, -7.0, 5.0)
    ctx.add(p, "wood_weathered", long_axis=2, moss=0.6, patches=0.5, low=0.7, low_h=0.4)
    ctx.add(cap, "wood_weathered", uv_scale=1.0, moss=0.6, patches=0.5)
    ctx.add(stub, "wood_weathered", long_axis=0, moss=0.5, patches=0.5)
    ctx.col_box((-0.05, -0.05, 0), (0.05, 0.05, h))


# ============================================================================================
# Dumpster (container: trash_pile)
# ============================================================================================

def dumpster(ctx: K.Ctx) -> None:
    """2-yard front-load dumpster: sloped front, top rim channel, side ribs, fork pockets, skids,
    two plastic lids. Clean: lids down, a bag propping one open. Worn: lid thrown back, rust,
    dents, bags spilling over the rim."""
    W, H = 1.83, 1.12
    yf_bot, yf_top, yb = -0.42, -0.6, 0.55
    prof = [(yf_bot, 0.12), (yb, 0.12), (yb, H), (yf_top, H)]
    body = K.prism("body", prof, W, plane="YZ")
    K.delete_faces(body, lambda c, n: n.z > 0.9)
    K.subdivide(body, 2)
    dr = ctx.drnd("dents")
    if ctx.worn:
        for (x, y, z, rad, d) in [(-0.4, -0.52, 0.7, 0.25, 0.05), (0.92, 0.1, 0.5, 0.2, 0.04), (0.3, 0.56, 0.8, 0.22, 0.04)]:
            K.dent(body, (x, y, z), rad, d)
    K.solidify(body, 0.012, offset=-1.0)
    paint = "paint_green"
    ctx.add(body, paint, uv_scale=1.0, patches=0.6, low=0.9, low_h=0.5, edge=1.0)
    rims = [K.box("rim_f", (W + 0.08, 0.06, 0.07), center=(0, yf_top - 0.02, H - 0.03)),
            K.box("rim_b", (W + 0.08, 0.06, 0.07), center=(0, yb + 0.02, H - 0.03)),
            K.box("rim_l", (0.06, yb - yf_top + 0.1, 0.07), center=(-W / 2 - 0.02, (yb + yf_top) / 2, H - 0.03)),
            K.box("rim_r", (0.06, yb - yf_top + 0.1, 0.07), center=(W / 2 + 0.02, (yb + yf_top) / 2, H - 0.03))]
    for rm in rims:
        ctx.add(rm, paint, uv_scale=1.0, patches=0.7, edge=1.2)
    for s in (-1, 1):
        for y in (-0.15, 0.3):
            rib = K.box("rib", (0.05, 0.06, H - 0.2), center=(s * (W / 2 + 0.02), y, 0.12 + (H - 0.2) / 2))
            ctx.add(rib, paint, uv_scale=1.0, patches=0.7, low=0.8, low_h=0.4)
        pocket = K.box("pocket", (0.1, 0.95, 0.13), center=(s * (W / 2 + 0.06), -0.02, 0.74), bevel=0.01)
        K.delete_faces(pocket, lambda c, n: abs(n.y) > 0.9)
        K.solidify(pocket, 0.006)
        ctx.add(pocket, paint, uv_scale=1.0, patches=0.7)
        skid = K.box("skid", (0.1, 1.05, 0.12), center=(s * 0.62, -0.02, 0.06))
        ctx.add(skid, "car_rust", uv_scale=1.0)
    hinge_y, hinge_z = yb + 0.03, H + 0.02
    bags = []
    for i, x in enumerate((-W / 4, W / 4)):
        lid = K.box("lid", (W / 2 - 0.02, yb - yf_top + 0.08, 0.035), center=(x, (yb + yf_top) / 2, H + 0.035), bevel=0.01,
                    cuts=(2, 2, 0))
        ribs = [K.box("lidrib", (0.05, yb - yf_top, 0.02), center=(x + dx, (yb + yf_top) / 2, H + 0.06)) for dx in (-0.25, 0.25)]
        grp = [lid] + ribs
        if ctx.worn and i == 0:
            ang = -200.0  # flipped over the back, hanging against the rear wall
        elif ctx.clean and i == 1:
            ang = -14.0
        else:
            ang = 0.0
        if ang:
            for o in grp:
                K.place(o, (0, -hinge_y, -hinge_z))
                K.place(o, rot=(ang, 0, 0))
                K.place(o, (0, hinge_y, hinge_z))
        for o in grp:
            ctx.add(o, "plastic_black", uv_scale=1.0, wear=0.4, patches=0.0)
    # Garbage inside / spilling out.
    br = ctx.rnd("bags")
    if ctx.clean:
        bags.append(P.add_bag(ctx, "dbag0", br, "plastic_bag_black", size=(0.5, 0.45, 0.55), segs=12, loc=(W / 4, -0.05, H - 0.3),
                         rotz=40))
    else:
        bags.append(P.add_bag(ctx, "dbag0", br, "plastic_bag_black", size=(0.55, 0.48, 0.6), segs=12, loc=(-W / 4, 0.0, H - 0.25),
                         rotz=10, tilt=(10, -8)))
        bags.append(P.add_bag(ctx, "dbag1", br, "plastic_bag_green", size=(0.5, 0.45, 0.5), segs=12, loc=(-0.15, -0.95, 0.0),
                         rotz=70, torn=True))
        bags.append(P.add_bag(ctx, "dbag2", br, "plastic_bag_black", size=(0.45, 0.42, 0.5), segs=12, loc=(0.45, -0.9, 0.0),
                         rotz=200, flat=0.3))
    ctx.col_box((-W / 2 - 0.1, yf_top, 0), (W / 2 + 0.1, yb + 0.05, H + 0.06))


# ============================================================================================
# Picnic table
# ============================================================================================

def _bar(name, a, b, w, t, normal=(1, 0, 0)):
    """Rectangular bar from a to b; thickness `t` along `normal`, width `w` across."""
    a, b = Vector(a), Vector(b)
    o = P.plank(name, (b - a).length, w, t, cuts=1)
    K.uv_box(o, 1.0, long_axis=0, offset=(a.x * 3.1 + a.y * 1.7, a.z * 2.3 + b.y))  # grain follows the bar
    K.orient(o, b - a, normal, (a + b) / 2)
    return o


def picnic_table(ctx: K.Ctx) -> None:
    """Classic A-frame picnic table with attached benches (1.83 m). Worn: boards missing/split,
    mossy. Destroyed: one A-frame collapsed, table pitched onto the ground."""
    wood = "wood_weathered"
    L, top_z, seat_z = 1.83, 0.76, 0.45
    parts = []
    missing = {1} if ctx.worn else set()
    for i in range(5):
        if i in missing:
            continue
        rr = ctx.rnd(f"top{i}")
        b = P.plank(f"top{i}", L, 0.14, 0.038, cuts=4, bow=rr.uniform(-0.006, 0.004), twist=rr.uniform(-1, 1))
        if ctx.worn and i == 3:
            P.break_end(b, 0.55, ctx.drnd("split"), side=1, depth=0.12)
        K.uv_box(b, 1.0, long_axis=0, offset=(rr.uniform(0, 7), rr.uniform(0, 7)))
        K.place(b, (0, -0.29 + i * 0.145, top_z - 0.019))
        parts.append(b)
    for s in (-1, 1):
        for k in range(2):
            if ctx.worn and s > 0 and k == 1:
                continue
            rr = ctx.rnd(f"seat{s}{k}")
            b = P.plank("seat", L, 0.14, 0.038, cuts=4, bow=rr.uniform(-0.01, 0.002))
            K.uv_box(b, 1.0, long_axis=0, offset=(rr.uniform(0, 7), rr.uniform(0, 7)))
            K.place(b, (0, s * (0.5 + k * 0.145), seat_z - 0.019))
            parts.append(b)
    for x in (-0.62, 0.62):
        for o in (_bar("tsup", (x, -0.36, top_z - 0.08), (x, 0.36, top_z - 0.08), 0.089, 0.038),
                  _bar("ssup", (x, -0.78, seat_z - 0.083), (x, 0.78, seat_z - 0.083), 0.089, 0.038),
                  _bar("leg", (x, -0.27, top_z - 0.04), (x, -0.7, 0.0), 0.14, 0.038),
                  _bar("leg", (x, 0.27, top_z - 0.04), (x, 0.7, 0.0), 0.14, 0.038)):
            parts.append(o)
        brace = _bar("brace", (x * 0.92, 0.0, seat_z - 0.12), (0.0, 0.0, top_z - 0.06), 0.089, 0.038, normal=(0, 1, 0))
        parts.append(brace)
    if ctx.destroyed:
        # The +X A-frame gave way: pivot the whole table about the -X feet.
        piv = Vector((-0.62, 0, 0))
        m = Matrix.Translation(piv) @ K.rot_matrix((0, 28, 3)) @ Matrix.Translation(-piv)
        for o in parts:
            o.data.transform(m)
            o.data.update()
        for o in parts:
            K.lift_min(o)
    for o in parts:
        ctx.add(o, wood, uv=None, moss=0.5, patches=0.45)
    if ctx.destroyed:
        ctx.col_hull(parts, max_points=40)
    else:
        ctx.col_box((-L / 2, -0.8, 0), (L / 2, 0.8, seat_z))
        ctx.col_box((-L / 2, -0.37, seat_z), (L / 2, 0.37, top_z))


# ============================================================================================
# Fire hydrant
# ============================================================================================

def fire_hydrant(ctx: K.Ctx) -> None:
    """Dry-barrel hydrant: flanged base with bolts, barrel, bonnet, pentagon operating nut, two
    hose nozzles and a pumper nozzle with caps. Worn: peeling to rust, a cap missing, leaning."""
    barrel = K.lathe("barrel", [(0.0, 0.0), (0.13, 0.0), (0.13, 0.045), (0.1, 0.055), (0.088, 0.075), (0.088, 0.2),
                                (0.088, 0.35), (0.09, 0.5), (0.11, 0.515), (0.11, 0.55), (0.0, 0.55)], segs=16)
    bonnet = K.lathe("bonnet", [(0.0, 0.55), (0.1, 0.55), (0.1, 0.57), (0.088, 0.58), (0.08, 0.63), (0.06, 0.68),
                                (0.035, 0.705), (0.0, 0.71)], segs=16)
    nut = K.cyl("nut", 0.026, 0.035, segs=5, center=(0, 0, 0.725))
    bolts = [K.cyl("bolt", 0.009, 0.02, segs=6, center=(math.cos(a) * 0.115, math.sin(a) * 0.115, 0.055))
             for a in [k * math.tau / 6 for k in range(6)]]
    hose = []
    caps = []
    for s in (-1, 1):
        hose.append(K.cyl("hose", 0.034, 0.07, segs=10, axis="X", center=(s * 0.115, 0, 0.42)))
        if not (ctx.worn and s > 0):
            caps.append(K.cyl("cap", 0.044, 0.035, segs=10, axis="X", center=(s * 0.165, 0, 0.42), bevel=0.004))
            caps.append(K.cyl("capnut", 0.016, 0.02, segs=5, axis="X", center=(s * 0.19, 0, 0.42)))
    hose.append(K.cyl("pumper", 0.05, 0.08, segs=12, axis="Y", center=(0, -0.12, 0.38)))
    caps.append(K.cyl("pcap", 0.064, 0.04, segs=12, axis="Y", center=(0, -0.175, 0.38), bevel=0.005))
    caps.append(K.cyl("pnut", 0.022, 0.025, segs=5, axis="Y", center=(0, -0.205, 0.38)))
    allp = [barrel, bonnet, nut] + bolts + hose + caps
    if ctx.worn:
        _lean(allp, -2.5, 3.0)
    ctx.add(barrel, "paint_red", uv="cyl", uv_scale=1.0, smooth=45, patches=0.6, low=0.8, low_h=0.25)
    ctx.add(bonnet, "paint_white", uv="cyl", uv_scale=1.0, smooth=45, patches=0.6)
    ctx.add(nut, "paint_white", uv_scale=1.0, edge=1.3)
    for o in bolts:
        ctx.add(o, "car_rust", uv_scale=1.0)
    for o in hose:
        ctx.add(o, "paint_red", uv="cyl", uv_axis=0, uv_scale=1.0, smooth=45, patches=0.6)
    for o in caps:
        ctx.add(o, "paint_white", uv="cyl", uv_axis=0, uv_scale=1.0, smooth=45, patches=0.6, edge=1.2)
    ctx.col_box((-0.14, -0.14, 0), (0.14, 0.14, 0.74))


# ============================================================================================
# Park bench
# ============================================================================================

def bench_park(ctx: K.Ctx) -> None:
    """Cast-iron end frames with wooden slats (1.8 m). Worn: a slat gone, one split, rust.
    Destroyed: an end frame snapped, seat collapsed to the ground at that end."""
    L = 1.8
    frame = []
    for x in (-0.82, 0.82):
        for a, b in [((-0.27, 0.0), (-0.24, 0.42)), ((0.26, 0.0), (0.2, 0.42)), ((-0.29, 0.42), (0.23, 0.4)),
                     ((0.19, 0.4), (0.31, 0.86)), ((-0.31, 0.63), (0.23, 0.66)), ((-0.26, 0.42), (-0.28, 0.63))]:
            frame.append(_bar("frame", (x, a[0], a[1]), (x, b[0], b[1]), 0.045, 0.035))
        frame.append(_bar("foot", (x, -0.33, 0.012), (x, 0.32, 0.012), 0.025, 0.06))
    slats = []
    missing = {1} if ctx.worn else set()
    for k, y in enumerate((-0.22, -0.1, 0.02, 0.14)):
        if k in missing:
            continue
        rr = ctx.rnd(f"slat{k}")
        s = P.plank("slat", L, 0.085, 0.034, cuts=4, bow=rr.uniform(-0.012, 0.0))
        if ctx.worn and k == 2:
            P.break_end(s, 0.25, ctx.drnd("split"), side=1, depth=0.1)
        K.uv_box(s, 1.0, long_axis=0, offset=(rr.uniform(0, 7), rr.uniform(0, 7)))
        K.place(s, (0, y, 0.44 - 0.03 * (y + 0.22)))
        slats.append(s)
    for k, t in enumerate((0.35, 0.72)):
        rr = ctx.rnd(f"back{k}")
        y, z = 0.19 + (0.31 - 0.19) * t, 0.4 + (0.86 - 0.4) * t
        s = P.plank("bslat", L, 0.085, 0.03, cuts=4)
        K.uv_box(s, 1.0, long_axis=0, offset=(rr.uniform(0, 7), rr.uniform(0, 7)))
        K.orient(s, "x", (0, -0.97, 0.25), (0, y - 0.025, z))
        slats.append(s)
    allp = frame + slats
    if ctx.destroyed:
        piv = Vector((-0.82, 0, 0))
        m = Matrix.Translation(piv) @ K.rot_matrix((0, 16, 0)) @ Matrix.Translation(-piv)
        for o in frame[7:] + slats:
            o.data.transform(m)
            o.data.update()
            K.lift_min(o)
    for o in frame:
        ctx.add(o, "paint_black", uv=None, patches=0.6, edge=1.2, low=0.6, low_h=0.3)
    for o in slats:
        ctx.add(o, "wood_weathered", uv=None, moss=0.4, patches=0.4)
    ctx.col_box((-L / 2, -0.33, 0), (L / 2, 0.33, 0.45))
    ctx.col_box((-L / 2, 0.15, 0.45), (L / 2, 0.33, 0.86))


# ============================================================================================
# Sawhorse barricade
# ============================================================================================

def _clip_rect(poly, x0, x1, z0, z1):
    def clip(pts, inside, inter):
        out = []
        for i in range(len(pts)):
            a, b = pts[i - 1], pts[i]
            ia, ib = inside(a), inside(b)
            if ib:
                if not ia:
                    out.append(inter(a, b))
                out.append(b)
            elif ia:
                out.append(inter(a, b))
        return out

    def ix(xc):
        return lambda a, b: (xc, a[1] + (b[1] - a[1]) * (xc - a[0]) / (b[0] - a[0]))

    def iz(zc):
        return lambda a, b: (a[0] + (b[0] - a[0]) * (zc - a[1]) / (b[1] - a[1]), zc)
    p = poly
    for inside, inter in ((lambda q: q[0] >= x0, ix(x0)), (lambda q: q[0] <= x1, ix(x1)),
                          (lambda q: q[1] >= z0, iz(z0)), (lambda q: q[1] <= z1, iz(z1))):
        if not p:
            return []
        p = clip(p, inside, inter)
    return p


def _striped_board(ctx, L, h, t, center, *, stripe_w=0.15, worn=False, broken=None, seed=0):
    k = 0
    c = -L / 2 - h
    parts = []
    while c < L / 2 + h:
        poly = [(c, -h / 2), (c + stripe_w, -h / 2), (c + stripe_w + h, h / 2), (c + h, h / 2)]
        pc = _clip_rect(poly, -L / 2, L / 2, -h / 2, h / 2)
        if len(pc) >= 3:
            o = K.prism(f"stripe{k}", pc, t, plane="XZ")
            K.place(o, center)
            parts.append((o, "paint_orange_wood" if k % 2 == 0 else "paint_white_wood"))
        c += stripe_w
        k += 1
    return parts


def sawhorse_barricade(ctx: K.Ctx) -> None:
    """Type II road barricade: two orange/white striped rails on wooden A-frame legs.
    Worn: faded, lower rail split and hanging. Destroyed: knocked flat, rail broken."""
    L = 1.2
    parts = []
    for (z, broken) in ((0.98, False), (0.62, ctx.worn)):
        for o, m in _striped_board(ctx, L, 0.2, 0.025, (0, -0.045, z)):
            if broken:
                # Lower rail hangs from its left end (one nail gave).
                piv = Vector((-L / 2 + 0.06, -0.045, z))
                K.place(o, -piv)
                K.place(o, rot=(0, 24, 0))
                K.place(o, piv)
            parts.append((o, m))
    for x in (-0.5, 0.5):
        for s in (-1, 1):
            leg = _bar("leg", (x, s * 0.03, 1.08), (x + 0.0, s * 0.36, 0.0), 0.089, 0.038, normal=(1, 0, 0))
            parts.append((leg, "wood_fresh"))
        brace = _bar("brace", (x, -0.26, 0.28), (x, 0.26, 0.28), 0.06, 0.02, normal=(1, 0, 0))
        parts.append((brace, "wood_fresh"))
    top = P.plank("cap", L * 0.95, 0.089, 0.038)
    K.place(top, (0, 0.0, 1.1))
    parts.append((top, "wood_fresh"))
    objs = [o for o, _ in parts]
    if ctx.destroyed:
        piv = Vector((0, -0.36, 0))
        m = Matrix.Translation(piv) @ K.rot_matrix((-88, 0, 18)) @ Matrix.Translation(-piv)
        for o in objs:
            o.data.transform(m)
            o.data.update()
        zmin = min(min(v.co.z for v in o.data.vertices) for o in objs)
        for o in objs:
            K.place(o, (0, 0, -zmin))
    for o, m in parts:
        bar_uv = o.name.startswith(("leg", "brace"))  # _bar parts already carry grain-aligned UVs
        stripe = m.startswith("paint_")
        ctx.add(o, m, uv=None if bar_uv else "box", uv_scale=1.0, long_axis=0, patches=0.25 if stripe else 0.5,
                edge=0.3 if stripe else 1.0, moss=0.2)  # thin boards: every vertex is on an edge
    if ctx.destroyed:
        ctx.col_hull(objs, max_points=24)
    else:
        ctx.col_box((-L / 2, -0.36, 0), (L / 2, 0.36, 1.12))


# ============================================================================================
# Jersey barrier
# ============================================================================================

JERSEY = [(-0.305, 0.0), (0.305, 0.0), (0.305, 0.076), (0.127, 0.33), (0.076, 0.81), (-0.076, 0.81), (-0.127, 0.33),
          (-0.305, 0.076)]


def jersey_barrier(ctx: K.Ctx) -> None:
    """Precast New Jersey-profile concrete barrier (3.0 m) with base drain slots. Worn: chipped
    arrises, stained. Destroyed: snapped in two, exposed rebar, one half pitched over."""
    L = 3.0
    dr = ctx.drnd("chips")

    slot_h, slot_w, half = 0.045, 0.3, 0.305

    def make(name, x0, x1):
        """Profile prism with edge loops every ~0.3 m and the drain slots (scuppers) built straight
        into the base (a boolean here re-triangulates the whole barrier differently every run)."""
        o = K.prism(name, [(-y, z) for y, z in JERSEY], x1 - x0, plane="YZ", offset=(x0 + x1) / 2)
        bm = bmesh.new()
        bm.from_mesh(o.data)
        slots = [x for x in (-0.8, 0.8) if x0 + 0.25 < x < x1 - 0.25]
        n = max(2, int((x1 - x0) / 0.3))
        cuts = [x0 + (x1 - x0) * k / (n + 1) for k in range(1, n + 1)]
        cuts = [c for c in cuts if all(abs(c - x) > slot_w / 2 + 0.06 for x in slots)]
        cuts += [x + s * slot_w / 2 for x in slots for s in (-1, 1)]
        for c in sorted(cuts):
            K.slice_at(bm, 0, c)
        if slots:
            K.slice_at(bm, 2, slot_h)
            for x in slots:
                a, b = x - slot_w / 2, x + slot_w / 2
                kill = [f for f in bm.faces if a < f.calc_center_median().x < b and f.calc_center_median().z < slot_h]
                bmesh.ops.delete(bm, geom=kill, context="FACES")
                at = {tuple(round(c, 4) for c in v.co): v for v in bm.verts}
                for quad in (((a, -half, slot_h), (b, -half, slot_h), (b, half, slot_h), (a, half, slot_h)),
                             ((a, -half, 0.0), (a, half, 0.0), (a, half, slot_h), (a, -half, slot_h)),
                             ((b, -half, 0.0), (b, -half, slot_h), (b, half, slot_h), (b, half, 0.0))):
                    bm.faces.new([at[tuple(round(c, 4) for c in p)] for p in quad])
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        return K.write_bm(bm, o)
    bodies = []
    if ctx.destroyed:
        a = make("left", -L / 2, 0.2)
        b = make("right", 0.2, L / 2)
        P.break_end(a, 0.1, dr, side=1, depth=0.2)
        P.break_end(b, 0.3, dr, side=-1, depth=0.2)
        piv = Vector((L / 2, 0.305, 0))
        m = Matrix.Translation(piv) @ K.rot_matrix((24, 0, -14)) @ Matrix.Translation(-piv)
        b.data.transform(m)
        b.data.update()
        K.lift_min(b)
        bodies = [a, b]
        for k in range(5):
            rr = ctx.drnd(f"rebar{k}")
            y, z = rr.uniform(-0.12, 0.12), rr.uniform(0.15, 0.65)
            bar = K.tube("rebar", [(0.08, y, z), (0.25 + rr.uniform(0, 0.2), y + rr.uniform(-0.05, 0.05), z + rr.uniform(-0.1, 0.05)),
                                   (0.4 + rr.uniform(0, 0.25), y + rr.uniform(-0.1, 0.1), z + rr.uniform(-0.25, 0.05))], 0.008, segs=4)
            ctx.add(bar, "car_rust", uv_scale=1.0)
    else:
        bodies = [make("barrier", -L / 2, L / 2)]
    for o in bodies:
        if ctx.worn:
            for k in range(7):
                x = dr.uniform(-L / 2 + 0.1, L / 2 - 0.1)
                s = dr.choice((-1, 1))
                K.dent(o, (x, s * 0.076, 0.81), dr.uniform(0.05, 0.12), dr.uniform(0.01, 0.03))
            for s in (-1, 1):
                K.dent(o, (s * L / 2, 0.0, 0.7), 0.12, 0.03)
        ctx.add(o, "concrete_barrier", uv_scale=1.0, patches=0.5, low=0.6, low_h=0.3, moss=0.25)
    if ctx.destroyed:
        ctx.col_hull([bodies[0]], max_points=24)
        ctx.col_hull([bodies[1]], max_points=24)
    else:
        ctx.col_hull([(x, y, z) for x in (-L / 2, L / 2) for y, z in JERSEY])


# ============================================================================================
# Woodpile
# ============================================================================================

def _firewood(name, L, R, r, kind):
    o = P.log_split(name, L, R, r, kind=kind, segs=6)
    import lib.materials as M
    i_bark = M.assign(o, "bark_firewood")
    i_wood = M.assign(o, "wood_fresh")
    for p in o.data.polygons:
        c = p.center
        if abs(p.normal.x) > 0.9:
            p.material_index = i_wood
        elif math.hypot(c.y, c.z) > R * 0.75:
            p.material_index = i_bark
        else:
            p.material_index = i_wood
    return o


def woodpile(ctx: K.Ctx) -> None:
    """Stacked split firewood between stakes on runners, tarp over the top (logging town winter
    supply). Worn: tarp blown half off, front rows collapsed onto the ground, mossy."""
    r = ctx.rnd("wood")
    W, D, H = 1.8, 0.42, 1.0
    for x in (-W / 2 - 0.04, W / 2 + 0.04):
        stake = P.plank("stake", 1.2, 0.089, 0.038, cuts=2)
        K.orient(stake, "z", "x", (x, 0.0, 0.6))
        ctx.add(stake, "wood_weathered", long_axis=2, moss=0.4, patches=0.4)
    for y in (-0.12, 0.12):
        run = P.plank("runner", W + 0.2, 0.089, 0.038)
        ctx.add(run, "wood_weathered", long_axis=0, moss=0.5, patches=0.4, at=((0, y, 0.019), None))
    z = 0.038
    row = 0
    collapsed = []
    stacked = []
    while z < H - 0.05:
        x = -W / 2 + 0.07
        while x < W / 2 - 0.06:
            rr = ctx.rnd(f"log{row}_{int(x * 100)}")
            R = rr.uniform(0.055, 0.08)
            kind = rr.choice(["half", "quarter", "round", "half"])
            lg = _firewood("log", D * rr.uniform(0.9, 1.05), R, rr, kind)
            K.place(lg, rot=(rr.uniform(0, 360), 0, 0))
            K.place(lg, rot=(0, 0, 90 + rr.uniform(-4, 4)))
            pos = Vector((x + R, rr.uniform(-0.03, 0.03), z + R * 0.9))
            if ctx.worn and row >= 4 and x > 0.1 and rr.random() < 0.6:
                # Fallen off the front of the stack.
                K.place(lg, rot=(0, 0, rr.uniform(-60, 60)))
                pos = Vector((x + rr.uniform(-0.2, 0.3), -D / 2 - rr.uniform(0.1, 0.6), 0.0))
                K.place(lg, pos)
                K.lift_min(lg)
                collapsed.append(lg)
            else:
                K.place(lg, pos)
            ctx.add(lg, None, uv="box", uv_scale=1.0, long_axis=1, moss=0.35, patches=0.3)
            if lg not in collapsed:
                stacked.append(lg)
            x += 2 * R * 0.95
        z += 0.115
        row += 1
    # Tarp.
    tarp = K.grid("tarp", W + 0.3, D + 0.5, 12, 6)
    K.uv_planar(tarp, 2, scale=1.0)
    top = max(max(v.co.z for v in o.data.vertices) for o in stacked) + 0.025  # clear the highest log

    def drape(co):
        dy = abs(co.y) - D / 2
        zz = top - max(0.0, dy) * 1.6 + 0.03 * math.sin(co.x * 9.0) * math.cos(co.y * 7.0)
        if ctx.worn and co.x > -0.2:
            # Blown back over the rear: hangs down behind the stack.
            t = min(1.0, (co.x + 0.2) / 0.5)
            zz = zz * (1 - t) + (top - (co.y + D) * 0.9 - 0.2) * t
            co.y = co.y * (1 - t) + (D / 2 + 0.05 + max(0.0, co.y + 0.3) * 0.2) * t
        co.z = max(0.02, zz)
        return co
    K.map_verts(tarp, drape)
    K.crumple(tarp, 0.02, scale=4.0, seed=r.randint(0, 999))
    K.solidify(tarp, 0.003)
    ctx.add(tarp, "tarp_blue", uv=None, smooth=50, patches=0.0, edge=0.3)
    ctx.col_box((-W / 2 - 0.06, -D / 2, 0), (W / 2 + 0.06, D / 2, top))


# ============================================================================================
# Wheelbarrow
# ============================================================================================

def wheelbarrow(ctx: K.Ctx) -> None:
    """Contractor wheelbarrow: steel tray, wooden handles, pneumatic wheel at the front (-Y).
    Worn: rusted through in places, flat tyre, grimy."""
    r = ctx.rnd("wb")
    rings = [[(-0.22, -0.22, 0.34), (0.22, -0.22, 0.34), (0.22, 0.2, 0.34), (-0.22, 0.2, 0.34)],
             [(-0.3, -0.45, 0.5), (0.3, -0.45, 0.5), (0.31, 0.27, 0.5), (-0.31, 0.27, 0.5)],
             [(-0.36, -0.62, 0.64), (0.36, -0.62, 0.64), (0.36, 0.32, 0.64), (-0.36, 0.32, 0.64)]]
    tray = K.loft("tray", rings, cap_start=True, cap_end=False)
    K.subdivide(tray, 2)
    if ctx.worn:
        K.dent(tray, (0.2, -0.3, 0.5), 0.15, 0.03)
    K.solidify(tray, 0.004, offset=-1.0)
    rim = K.tube("rim", [Vector(p) + Vector((0, 0, 0.004)) for p in rings[-1]], 0.012, segs=6, closed=True)
    wz = 0.2
    handles = []
    for s in (-1, 1):
        h = K.tube("handle", [(s * 0.16, -0.78, wz + 0.02), (s * 0.2, -0.3, 0.3), (s * 0.24, 0.3, 0.42), (s * 0.27, 0.95, 0.56)],
                   0.022, segs=6, flat=(1.0, 1.15))
        handles.append(h)
        grip = K.cyl("grip", 0.025, 0.14, segs=8, axis="Y", center=(s * 0.27, 0.9, 0.555))
        K.place(grip, (-s * 0.27, -0.9, -0.555))
        K.place(grip, rot=(12, 0, 0))
        K.place(grip, (s * 0.27, 0.9, 0.555))
        ctx.add(grip, "rubber_black", uv="cyl", uv_axis=1, uv_scale=1.0, smooth=40)
        leg = K.tube("leg", [(s * 0.24, 0.18, 0.4), (s * 0.27, 0.26, 0.0)], 0.012, segs=5, flat=(1.0, 0.4))
        ctx.add(leg, "paint_black", uv_scale=1.0, patches=0.6)
        fork = K.tube("fork", [(s * 0.16, -0.62, 0.27), (s * 0.06, -0.78, wz)], 0.01, segs=5)
        ctx.add(fork, "paint_black", uv_scale=1.0, patches=0.6)
    for h in handles:
        ctx.add(h, "wood_fresh" if ctx.clean else "wood_weathered", uv="box", long_axis=1, patches=0.4)
    t = P.tyre("wheel", 0.2, 0.1, 0.085, segs=14)
    K.place(t, (0, -0.78, wz))
    if ctx.worn:
        K.place(t, (0, 0, -0.05))
        P.flatten_tyre(t, wz - 0.05, 0.2, amount=0.5, bulge=0.012)
    ctx.add(t, "tyre_rubber", uv="cyl", uv_axis=0, uv_scale=1.0, smooth=50, patches=0.0)
    hub = K.cyl("hub", 0.1, 0.07, segs=12, axis="X", center=(0, -0.78, wz - (0.05 if ctx.worn else 0.0)))
    ctx.add(hub, "paint_black", uv_scale=1.0, patches=0.5)
    axle = K.cyl("axle", 0.008, 0.36, segs=6, axis="X", center=(0, -0.78, wz))
    ctx.add(axle, "metal_galvanized", uv_scale=1.0)
    ctx.add(tray, "paint_green", uv_scale=1.0, smooth=40, patches=0.7, low=0.8, low_h=0.45)
    ctx.add(rim, "paint_green", uv_scale=1.0, smooth=40, patches=0.7)
    ctx.col_box((-0.37, -0.98, 0), (0.37, 0.98, 0.66))


# ============================================================================================
# Hand well pump
# ============================================================================================

def well_pump(ctx: K.Ctx) -> None:
    """Cast-iron pitcher pump on a casing over a concrete well pad. Worn: handle snapped off and
    lying on the pad, heavy rust, a cracked pad corner."""
    pad = K.box("pad", (0.9, 0.9, 0.15), center=(0, 0, 0.075), bevel=0.02, cuts=(3, 3, 0))
    if ctx.worn:
        K.dent(pad, (0.45, -0.45, 0.15), 0.18, 0.05)
    ctx.add(pad, "concrete_barrier", uv_scale=1.0, patches=0.4, moss=0.5)
    casing = K.cyl("casing", 0.06, 0.12, segs=10, center=(0, 0, 0.21))
    ctx.add(casing, "metal_galvanized", uv="cyl", uv_scale=1.0, smooth=45, patches=0.6)
    body = K.lathe("pump", [(0.0, 0.27), (0.1, 0.27), (0.1, 0.3), (0.075, 0.31), (0.07, 0.5), (0.068, 0.7),
                            (0.072, 0.84), (0.085, 0.85), (0.085, 0.9), (0.05, 0.92), (0.0, 0.925)], segs=12)
    spout = K.tube("spout", [(0, -0.05, 0.66), (0, -0.16, 0.66), (0, -0.25, 0.62), (0, -0.29, 0.55)], [0.03, 0.028, 0.025, 0.022],
                   segs=8)
    bracket = K.box("pivot", (0.04, 0.08, 0.1), center=(0, 0.06, 0.96))
    rod = K.cyl("rod", 0.009, 0.12, segs=6, center=(0, 0.0, 0.97))
    parts = [body, spout, bracket, rod]
    pts = [(0, 0.02, 0.98), (0, 0.25, 1.06), (0, 0.5, 1.14), (0, 0.66, 1.17)]
    if ctx.worn:
        handle = K.tube("handle", [(0, 0, 0), (0, 0.3, 0.02), (0, 0.55, 0.0)], 0.016, segs=6)
        K.place(handle, (0.2, -0.15, 0.17), (0, 0, 35))
        K.lift_min(handle, 0.15)
    else:
        handle = K.tube("handle", pts, 0.016, segs=6)
    parts.append(handle)
    for o in parts:
        ctx.add(o, "paint_black", uv="box", uv_scale=1.0, smooth=45, patches=0.8 if ctx.worn else 0.5, edge=1.2)
    ctx.col_box((-0.45, -0.45, 0), (0.45, 0.45, 0.15))
    ctx.col_box((-0.1, -0.3, 0.15), (0.1, 0.12, 0.95))


# ============================================================================================
# Shopping cart
# ============================================================================================

def _wire_panel(ctx, p0, p1, p2, p3, nu, nv, r=0.0028, mat="metal_galvanized"):
    """Wires across a quad panel: nu wires from edge p0-p3 to p1-p2 and nv from p0-p1 to p3-p2."""
    P0, P1, P2, P3 = (Vector(p) for p in (p0, p1, p2, p3))
    objs = []
    for i in range(1, nu):
        t = i / nu
        a, b = P0.lerp(P1, t), P3.lerp(P2, t)
        objs.append(K.tube("w", [a, b], r, segs=3, caps=False))
    for j in range(1, nv):
        t = j / nv
        a, b = P0.lerp(P3, t), P1.lerp(P2, t)
        objs.append(K.tube("w", [a, b], r, segs=3, caps=False))
    return objs


def shopping_cart(ctx: K.Ctx) -> None:
    """Nesting wire shopping cart: tapered basket, swing gate, bottom rack, red handle, casters.
    Worn: rusty, bent, a caster gone (sagging corner), loaded with a survivor's belongings.
    Destroyed: tipped on its side, basket crushed."""
    bx0, bx1 = 0.28, 0.23
    yb, yf = 0.42, -0.47
    zb_back, zb_front, ztop = 0.52, 0.6, 0.98
    c = {"bbl": (-bx0, yb, zb_back), "bbr": (bx0, yb, zb_back), "bfl": (-bx1, yf, zb_front), "bfr": (bx1, yf, zb_front),
         "tbl": (-bx0 - 0.02, yb + 0.02, ztop), "tbr": (bx0 + 0.02, yb + 0.02, ztop), "tfl": (-bx1, yf - 0.02, ztop),
         "tfr": (bx1, yf - 0.02, ztop)}
    wires = []
    wires += _wire_panel(ctx, c["bfl"], c["bfr"], c["bbr"], c["bbl"], 6, 10)              # floor
    wires += _wire_panel(ctx, c["bfl"], c["bbl"], c["tbl"], c["tfl"], 10, 5)              # left
    wires += _wire_panel(ctx, c["bbr"], c["bfr"], c["tfr"], c["tbr"], 10, 5)              # right
    wires += _wire_panel(ctx, c["bfr"], c["bfl"], c["tfl"], c["tfr"], 6, 5)               # front
    wires += _wire_panel(ctx, c["bbl"], c["bbr"], c["tbr"], c["tbl"], 7, 5)               # back gate
    frame = []
    top = [c["tfl"], c["tfr"], c["tbr"], c["tbl"]]
    frame.append(K.tube("toprim", top, 0.007, segs=6, closed=True))
    frame.append(K.tube("botrim", [c["bfl"], c["bfr"], c["bbr"], c["bbl"]], 0.006, segs=5, closed=True))
    # Chassis: U-frame with casters, uprights to the basket and handle.
    zr = 0.13
    chassis = [(-0.22, -0.4, zr), (0.22, -0.4, zr), (0.26, 0.38, zr), (-0.26, 0.38, zr)]
    frame.append(K.tube("base", chassis, 0.011, segs=6, closed=True))
    for s in (-1, 1):
        frame.append(K.tube("upright", [(s * 0.26, 0.38, zr), (s * 0.27, 0.42, zb_back), (s * 0.3, 0.5, ztop + 0.02)], 0.011,
                            segs=6))
        frame.append(K.tube("fstrut", [(s * 0.22, -0.4, zr), (s * 0.22, -0.42, zb_front)], 0.009, segs=5))
    rack = _wire_panel(ctx, chassis[0], chassis[1], chassis[2], chassis[3], 4, 8, r=0.0025)
    handle = K.cyl("handle", 0.016, 0.62, segs=8, axis="X", center=(0, 0.52, ztop + 0.04))
    casters = []
    corner = [(-0.22, -0.4), (0.22, -0.4), (0.26, 0.38), (-0.26, 0.38)]
    missing = 1 if ctx.worn and not ctx.destroyed else -1
    for i, (x, y) in enumerate(corner):
        if i == missing:
            continue
        wh = K.cyl("caster", 0.055, 0.028, segs=10, axis="X", center=(x, y + 0.02, 0.055))
        fk = K.box("fork", (0.04, 0.03, 0.07), center=(x, y, 0.1))
        casters += [wh, fk]
    loose = []
    if ctx.worn and not ctx.destroyed:
        P.add_bag(ctx, "cbag", ctx.rnd("cartbag"), "plastic_bag_black", size=(0.4, 0.36, 0.45), segs=12, loc=(-0.05, 0.12, zb_back + 0.02),
             rotz=20)
        box = K.box("cbox", (0.32, 0.26, 0.22), center=(0.04, -0.22, zb_front + 0.12), cuts=(2, 1, 1))
        K.crumple(box, 0.008, scale=8.0, seed=3)
        loose.append(box)
    allp = wires + frame + rack + [handle] + casters + loose
    if ctx.worn and not ctx.destroyed:
        # Missing caster: the cart sags onto that corner.
        piv = Vector((0, 0, 0.0))
        m = Matrix.Translation(piv) @ K.rot_matrix((-3.0, 4.0, 0)) @ Matrix.Translation(-piv)
        for o in allp:
            o.data.transform(m)
            o.data.update()
        for o in wires + frame[:2]:
            K.dent(o, (0.28, -0.1, 0.85), 0.25, 0.05, direction=(-1, 0, -0.2))
    if ctx.destroyed:
        piv = Vector((0.3, 0, 0))
        m = Matrix.Translation(piv) @ K.rot_matrix((0, -90, 0)) @ Matrix.Translation(-piv)
        for o in allp:
            o.data.transform(m)
            o.data.update()
        for o in wires + frame:
            K.dent(o, (0.6, -0.1, 0.55), 0.35, 0.1, direction=(0, 0, -1))
        zmin = min(min(v.co.z for v in o.data.vertices) for o in allp)
        for o in allp:
            K.place(o, (0, 0, -zmin))
    for o in wires + rack:
        ctx.add(o, "metal_galvanized", uv_scale=1.0, wear=1.0, patches=0.6, ao=True)
    for o in frame + [f for f in casters if f.name.startswith("fork")]:
        ctx.add(o, "metal_galvanized", uv_scale=1.0, smooth=45, patches=0.6)
    ctx.add(handle, "plastic_red", uv="cyl", uv_axis=0, uv_scale=1.0, smooth=45, patches=0.3)
    for o in casters:
        if o.name.startswith("caster"):
            ctx.add(o, "rubber_black", uv="cyl", uv_axis=0, uv_scale=1.0, smooth=45)
    for o in loose:
        ctx.add(o, "cardboard_wet", uv_scale=1.0, smooth=30, patches=0.0)
    ctx.col_hull(allp, max_points=32)


# ============================================================================================
# Bicycle
# ============================================================================================

def _wheel_bike(name, center, R=0.33, spokes=16):
    c = Vector(center)
    tyre = K.tube(name + "_tyre", [c + Vector((0, math.cos(a) * (R - 0.022), math.sin(a) * (R - 0.022)))
                                   for a in [k * math.tau / 22 for k in range(22)]], 0.024, segs=6, closed=True)
    rim = K.tube(name + "_rim", [c + Vector((0, math.cos(a) * (R - 0.05), math.sin(a) * (R - 0.05)))
                                 for a in [k * math.tau / 22 for k in range(22)]], 0.011, segs=4, closed=True, flat=(0.6, 1.0))
    hub = K.cyl(name + "_hub", 0.022, 0.1, segs=8, axis="X", center=center)
    sp = []
    for k in range(spokes):
        a = k * math.tau / spokes
        side = 0.035 if k % 2 else -0.035
        sp.append(K.tube(name + "_spoke", [c + Vector((side, 0, 0)), c + Vector((0, math.cos(a) * (R - 0.055), math.sin(a) * (R - 0.055)))],
                         0.0018, segs=3, caps=False))
    return tyre, rim, hub, sp


def bicycle_rusty(ctx: K.Ctx) -> None:
    """Rusty 90s mountain bike. Clean: on its kickstand. Worn: dumped on its side, chain hanging,
    saddle split. Destroyed: on its side, front wheel folded, saddle gone."""
    R = 0.33
    ax = R
    rear, front = Vector((0, 0.52, ax)), Vector((0, -0.53, ax))
    bb = Vector((0, 0.06, 0.29))
    seat = Vector((0, 0.2, 0.84))
    head_t, head_b = Vector((0, -0.37, 0.88)), Vector((0, -0.41, 0.74))
    frame = [K.tube("top", [seat, head_t], 0.019, segs=8), K.tube("down", [bb, head_b], 0.022, segs=8),
             K.tube("seat_t", [bb, seat + Vector((0, 0.01, 0.04))], 0.018, segs=8), K.tube("head", [head_b, head_t + Vector((0, 0.01, 0.04))], 0.022, segs=8)]
    for s in (-1, 1):
        frame.append(K.tube("cstay", [bb + Vector((s * 0.02, 0, 0)), rear + Vector((s * 0.06, 0, 0))], 0.011, segs=6))
        frame.append(K.tube("sstay", [seat + Vector((s * 0.015, -0.01, -0.03)), rear + Vector((s * 0.06, 0, 0))], 0.01, segs=6))
        frame.append(K.tube("fork", [head_b + Vector((s * 0.03, 0, 0)), head_b + Vector((s * 0.05, -0.05, -0.2)),
                                     front + Vector((s * 0.05, 0, 0))], 0.013, segs=6))
    post = K.tube("post", [seat, seat + Vector((0, 0.04, 0.16))], 0.013, segs=6)
    saddle = K.blob("saddle", 0.5, subdiv=2, scale=(0.15, 0.27, 0.06), center=(0, 0.26, 1.02))
    stem = K.tube("stem", [head_t + Vector((0, 0.01, 0.04)), head_t + Vector((0, -0.05, 0.12))], 0.014, segs=6)
    bar = K.tube("bar", [(-0.29, -0.43, 1.02), (-0.1, -0.43, 1.0), (0.1, -0.43, 1.0), (0.29, -0.43, 1.02)], 0.011, segs=6)
    grips = [K.cyl("grip", 0.016, 0.11, segs=8, axis="X", center=(s * 0.25, -0.43, 1.017)) for s in (-1, 1)]
    ring = K.tube("chainring", [bb + Vector((0.06, math.cos(a) * 0.09, math.sin(a) * 0.09)) for a in [k * math.tau / 14 for k in range(14)]],
                  0.006, segs=4, closed=True)
    cranks = [K.tube("crank", [bb + Vector((s * 0.07, 0, 0)), bb + Vector((s * 0.08, s * 0.1, -s * 0.13))], 0.01, segs=5)
              for s in (-1, 1)]
    pedals = [K.box("pedal", (0.1, 0.06, 0.02), center=bb + Vector((s * 0.13, s * 0.1, -s * 0.13))) for s in (-1, 1)]
    chain_pts = [bb + Vector((0.06, 0.0, 0.09)), rear + Vector((0.06, 0, 0.04)), rear + Vector((0.06, 0.03, -0.04)),
                 bb + Vector((0.06, 0.02, -0.09))]
    if ctx.worn:
        chain_pts = [bb + Vector((0.06, 0.0, 0.09)), rear + Vector((0.06, 0, 0.04)), rear + Vector((0.06, -0.15, -0.2)),
                     bb + Vector((0.06, 0.1, -0.22))]
    chain = K.tube("chain", chain_pts, 0.005, segs=3, caps=False)
    wheels = []
    for name, ctr in (("rw", rear), ("fw", front)):
        tyre, rim, hub, sp = _wheel_bike(name, ctr, R)
        if ctx.destroyed and name == "fw":
            for o in [tyre, rim] + sp:
                K.map_verts(o, lambda co, c=ctr: Vector((co.x + 0.12 * math.sin((co.y - c.y) / R * 1.6) * ((co.z - c.z) / R),
                                                         co.y, co.z)))
        wheels.append((tyre, rim, hub, sp))
    stand = K.tube("stand", [bb + Vector((-0.04, 0.12, -0.02)), Vector((-0.17, 0.35, 0.0))], 0.008, segs=5)
    parts_frame = frame + [stem]
    metal = [post, bar, ring] + cranks + [chain]
    rubber = grips + [w[0] for w in wheels]
    rims = [w[1] for w in wheels] + [w[2] for w in wheels] + [s for w in wheels for s in w[3]]
    others = pedals + ([stand] if ctx.clean else [])
    seat_parts = [saddle] if not ctx.destroyed else []
    allp = parts_frame + metal + rubber + rims + others + seat_parts
    if ctx.clean:
        _lean(allp, 0.0, -9.0, pivot=(0, 0, 0))
    else:
        m = K.rot_matrix((0, 84, 20))
        for o in allp:
            o.data.transform(m)
            o.data.update()
        zmin = min(min(v.co.z for v in o.data.vertices) for o in allp)
        for o in allp:
            K.place(o, (0, 0, -zmin))
    for o in parts_frame:
        ctx.add(o, "paint_red", uv_scale=1.0, smooth=45, patches=0.8, edge=1.3)
    for o in metal:
        ctx.add(o, "chrome_pitted", uv_scale=1.0, smooth=45, patches=0.7)
    for o in rubber:
        ctx.add(o, "rubber_black", uv_scale=1.0, smooth=45, patches=0.0)
    for o in rims:
        ctx.add(o, "chrome_pitted", uv_scale=1.0, smooth=45, patches=0.8)
    for o in others:
        ctx.add(o, "paint_black", uv_scale=1.0, patches=0.6)
    for o in seat_parts:
        ctx.add(o, "leather_dark", uv_scale=1.0, smooth=50, patches=0.3)
    ctx.col_hull(allp, max_points=32)


# ============================================================================================
# Payphone (booth-less pedestal phone)
# ============================================================================================

def payphone(ctx: K.Ctx) -> None:
    """90s pedestal payphone: steel post, half-shroud with hood and blank colour-block header,
    stainless housing with keypad, coin slot/return, hook and armoured cord. Worn: handset
    ripped off, dangling by the cord; dents, rust. Destroyed: post bent over, housing smashed open,
    a side panel torn off and lying on the ground."""
    post = K.box("post", (0.1, 0.1, 1.02), center=(0, 0.08, 0.51), cuts=(0, 0, 3))
    plate = K.box("plate", (0.26, 0.26, 0.02), center=(0, 0.08, 0.01))
    z0, z1 = 1.0, 1.66
    back = K.box("back", (0.52, 0.03, z1 - z0), center=(0, 0.015, (z0 + z1) / 2), cuts=(2, 0, 2))
    wings = []
    for s in (-1, 1):
        w = K.box("wing", (0.025, 0.3, z1 - z0), center=(0, -0.15, (z0 + z1) / 2), cuts=(0, 1, 2))
        K.place(w, rot=(0, 0, -s * 12))
        K.place(w, (s * 0.255, 0.0, 0))
        wings.append(w)
    hood = K.box("hood", (0.58, 0.36, 0.035), center=(0, -0.15, z1 + 0.0175), bevel=0.006)
    header = K.box("header", (0.56, 0.05, 0.14), center=(0, -0.3, z1 + 0.1))
    stripe = K.box("stripe", (0.56, 0.004, 0.035), center=(0, -0.327, z1 + 0.1))
    shelf = K.box("shelf", (0.44, 0.26, 0.03), center=(0, -0.13, z0 + 0.06), bevel=0.005)
    housing = K.box("housing", (0.2, 0.11, 0.42), center=(0, -0.055, z0 + 0.12 + 0.21), bevel=0.012)
    keys = []
    for row in range(4):
        for col in range(3):
            keys.append(K.box("key", (0.026, 0.012, 0.022), center=(-0.035 + col * 0.035, -0.112, z0 + 0.42 - row * 0.032),
                              bevel=0.003))
    slot = K.box("coin", (0.035, 0.014, 0.012), center=(0.06, -0.112, z0 + 0.5))
    ret = K.box("return", (0.05, 0.03, 0.04), center=(0.04, -0.12, z0 + 0.19))
    hook = K.box("hook", (0.03, 0.05, 0.12), center=(-0.115, -0.08, z0 + 0.42))
    phone_parts = [housing, slot, ret, hook] + keys
    # Handset (capsule) + armoured cord.
    hs_pts = [(-0.135, -0.09, z0 + 0.5), (-0.14, -0.1, z0 + 0.42), (-0.14, -0.1, z0 + 0.32), (-0.135, -0.09, z0 + 0.25)]
    cord_end = Vector((-0.135, -0.09, z0 + 0.24))
    if ctx.worn and not ctx.destroyed:
        base = Vector((-0.2, -0.45, 0.06))
        hs_pts = [base + Vector((0, 0, 0.0)), base + Vector((0.06, -0.04, 0.0)), base + Vector((0.14, -0.05, 0.0)),
                  base + Vector((0.2, -0.03, 0.0))]
        cord_end = Vector(hs_pts[-1]) + Vector((0.02, 0.02, 0.0))
    handset = K.tube("handset", hs_pts, [0.024, 0.016, 0.016, 0.024], segs=8)
    cord_start = Vector((-0.08, -0.1, z0 + 0.16))
    cpts = [cord_start]
    for k in range(1, 9):
        t = k / 9
        p = cord_start.lerp(cord_end, t)
        sag = 0.15 if not ctx.worn else 0.05
        cpts.append(p + Vector((0, -0.02 * math.sin(t * math.pi), -sag * math.sin(t * math.pi))))
    cpts.append(cord_end)
    cord = K.tube("cord", cpts, 0.007, segs=5)
    for o in [back] + wings:
        if ctx.worn:
            K.dent(o, (0.2, -0.2, z0 + 0.3), 0.18, 0.02)
    detached = []
    if ctx.destroyed:
        # Housing smashed open: front plate gone (keys, slot lost), handset gone, a wing torn off.
        phone_parts = [hook, ret]
        guts = K.box("guts", (0.17, 0.08, 0.36), center=(0, -0.04, z0 + 0.12 + 0.21))
        phone_parts.append(guts)
        for k in range(4):
            wire = K.tube("wire", [(-0.05 + k * 0.03, -0.08, z0 + 0.3), (-0.08 + k * 0.05, -0.18, z0 + 0.2 - k * 0.03),
                                   (-0.1 + k * 0.06, -0.22, z0 + 0.05)], 0.003, segs=3)
            detached.append(wire)
        wing = wings.pop(0)
        K.place(wing, (0.255, 0.0, -(z0 + z1) / 2))
        K.place(wing, rot=(90, 0, 30))
        K.place(wing, (-0.55, -0.35, 0.02))
        K.lift_min(wing)
        detached.append(wing)
        handset = None
        cord = K.tube("cord", [cord_start, cord_start + Vector((0.0, -0.08, -0.25)), cord_start + Vector((0.02, -0.06, -0.45))],
                      0.007, segs=5)
    upper = [back] + wings + [hood, header, stripe, shelf] + phone_parts + [cord]
    if ctx.destroyed:
        K.kink([post] + upper + [d for d in detached if d.name.startswith("wire")], (0, 0.08, 0.35), (-24, 6, 0), blend=0.1)
    ctx.add(post, "paint_grey", uv_scale=1.0, patches=0.6, low=0.9, low_h=0.5)
    ctx.add(plate, "paint_grey", uv_scale=1.0, patches=0.7)
    for o in [back] + wings + [hood, shelf]:
        ctx.add(o, "paint_grey", uv_scale=1.0, patches=0.55, edge=1.1)
    ctx.add(header, "plastic_blue", uv_scale=1.0, wear=0.4)
    ctx.add(stripe, "plastic_white", uv_scale=1.0, wear=0.4)
    for o in phone_parts:
        ctx.add(o, "chrome_pitted" if o.name.startswith(("housing", "hook", "return")) else "plastic_black", uv_scale=1.5,
                wear=0.5)
    if handset is not None:
        ctx.add(handset, "plastic_black", uv_scale=1.0, smooth=45, wear=0.3)
    ctx.add(cord, "chrome_pitted", uv_scale=1.0, smooth=45, wear=0.3)
    for o in detached:
        ctx.add(o, "paint_grey" if o.name.startswith("wing") else "plastic_red", uv_scale=1.0, patches=0.6)
    _flyers(ctx, ctx.rnd("flyers"), 2, 0.07, 0.6, 0.9, center=(0, 0.08), torn=ctx.worn)
    ctx.col_box((-0.3, -0.36, 0), (0.3, 0.14, 1.84 if not ctx.destroyed else 1.6))


BUILDERS = {
    "utility_pole": utility_pole,
    "street_lamp": street_lamp,
    "road_sign_stop": road_sign_stop,
    "road_sign_speed": road_sign_speed,
    "mailbox_rural": mailbox_rural,
    "fence_picket_2m": fence_picket_2m,
    "fence_chainlink_2m": fence_chainlink_2m,
    "fence_wood_2m": fence_wood_2m,
    "fence_post": fence_post,
    "dumpster": dumpster,
    "picnic_table": picnic_table,
    "fire_hydrant": fire_hydrant,
    "bench_park": bench_park,
    "sawhorse_barricade": sawhorse_barricade,
    "jersey_barrier": jersey_barrier,
    "woodpile": woodpile,
    "wheelbarrow": wheelbarrow,
    "well_pump": well_pump,
    "shopping_cart": shopping_cart,
    "bicycle_rusty": bicycle_rusty,
    "payphone": payphone,
}


def build(params: dict, outputs: list[str]) -> None:
    K.run(params, outputs, BUILDERS)
