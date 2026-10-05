"""Traps and lock cues family (POI dungeon mechanics, ADR-0018): the visible half of the traps and
locks PoiBuilder places in buildings. Abandoned 1990s Pacific-Northwest valley: hand-forged steel
gone to rust, sun-greyed fir, tarred cord, a cheap battery alarm from the hardware store.

  trap_bear            long-spring bear trap set open: jaws flat round the pan, both springs
                       compressed, the chain to its ring, half-buried in plaster, paper and splinters
  trap_bear_sprung     the same trap after it fired: jaws standing shut with the teeth meshed,
                       springs relaxed, the debris kicked aside
  trap_shotgun_rig     sawn-off side-by-side lashed with cord to a green kitchen chair on a wood
                       block, barrels over the seat front, a cord from the trigger to a nail in the
                       front stretcher (the game draws the tripwire from that nail to the doorway)
  trap_creaky_boards   1 x 1 m patch of loose, cupped and lifted fir boards with popped nails
  trap_alarm_box       battery door alarm: siren grille, LED, key switch, magnetic contact on a lead
  trap_alarm_bell      brass hand bell hanging on a cord from a screw eye (cord across a passage)
  lock_padlock         hasp, staple and laminated padlock across the gap between leaf and casing
  lock_hasp_open       the hasp left after the padlock is gone: strap swung open, plate on the leaf
  lock_chain           chain between an eye bolt in the leaf and one in the casing, padlocked
  lock_deadbolt        brass keyed deadbolt cylinder and rose
  lock_bolt            sliding barrel bolt with its knob (inside face of a bolted door)

Conventions: front = Blender -Y (Godot +Z), metres. Floor traps: origin bottom centre. Door locks
are mounted on a door leaf: origin = on the leaf face at its latch edge (the leaf runs toward -X,
the casing toward +X and 8 cm proud toward -Y), mount height at z = 0, parts hang below (no
ground clamp / ground AO). Alarm box: origin on the wall plane, bottom centre; bell: origin at the
bell's lip, the cord rising 0.75 m to its screw eye.
"""
from __future__ import annotations

import math
import random

import bpy
from mathutils import Matrix, Vector

from lib import export
from lib import props_ext_kit as K
from lib import props_ext_parts as P

K.materials.PREVIEW_COLORS.update({
    "trap_steel": (0.12, 0.1, 0.09), "trap_spring_steel": (0.2, 0.2, 0.21), "trap_chain": (0.16, 0.13, 0.11),
    "trap_cord": (0.45, 0.38, 0.27), "trap_cord_tarred": (0.12, 0.11, 0.1), "trap_boards": (0.36, 0.29, 0.21),
    "trap_boards_damp": (0.28, 0.23, 0.17), "trap_gun_barrel": (0.08, 0.09, 0.1), "trap_gun_stock": (0.3, 0.17, 0.09),
    "trap_alarm_plastic": (0.6, 0.57, 0.48), "trap_plaster": (0.5, 0.48, 0.45), "trap_alarm_dark": (0.03, 0.03, 0.03), "trap_alarm_led": (0.6, 0.05, 0.03),
    "trap_label": (0.6, 0.28, 0.08), "trap_brass": (0.55, 0.42, 0.2), "lock_steel": (0.4, 0.41, 0.42),
    "lock_zinc": (0.45, 0.45, 0.43),
})

CASING = 0.084  # leaf face -> casing face (recessed leaf, 2 cm trim), toward -Y


def _rect(w: float, t: float) -> list[tuple[float, float]]:
    """CCW rectangle profile for K.sweep (lateral, up)."""
    return [(-w / 2, -t / 2), (w / 2, -t / 2), (w / 2, t / 2), (-w / 2, t / 2)]


def _arc(c, r: float, a0: float, a1: float, n: int, plane: str = "XY") -> list[Vector]:
    """Points of a circular arc (degrees) around c in the XY (flat) or XZ (upright) plane."""
    pts = []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        if plane == "XY":
            pts.append(Vector((c[0] + r * math.cos(a), c[1] + r * math.sin(a), c[2])))
        else:
            pts.append(Vector((c[0] + r * math.cos(a), c[1], c[2] + r * math.sin(a))))
    return pts


def _link(name: str, center, along, normal, *, L: float = 0.032, W: float = 0.016, r: float = 0.0034,
          segs: int = 5) -> object:
    """One oval chain link (stadium loop of round bar) centred at `center`, long axis `along`,
    lying in the plane with normal `normal`."""
    a = Vector(along).normalized()
    n = Vector(normal).normalized()
    b = n.cross(a).normalized()
    half = (L - W) / 2
    rr = W / 2 - r
    pts = []
    for k in range(5):  # one end cap
        t = math.pi / 2 - math.pi * k / 4
        pts.append(a * (half + rr * math.cos(t)) + b * (rr * math.sin(t)))
    for k in range(5):  # other end cap
        t = -math.pi / 2 - math.pi * k / 4
        pts.append(a * (-half + rr * math.cos(t)) + b * (rr * math.sin(t)))
    c = Vector(center)
    return K.tube(name, [c + p for p in pts], r, segs=segs, closed=True)


def _chain(ctx: K.Ctx, pts: list, mat: str = "trap_chain", *, L: float = 0.032, W: float = 0.016, r: float = 0.0034,
           up=(0, 0, 1)) -> None:
    """Links along a polyline, every other one turned 90 degrees about its long axis."""
    path = [Vector(p) for p in pts]
    seg_l = L - 2 * r - 0.004
    out = []
    total = sum((b - a).length for a, b in zip(path[:-1], path[1:]))
    n = max(1, int(total / seg_l))
    for i in range(n):
        d = (i + 0.5) * seg_l
        # point and direction at arc length d
        acc = 0.0
        for a, b in zip(path[:-1], path[1:]):
            sl = (b - a).length
            if acc + sl >= d or (a, b) == (path[-2], path[-1]):
                t = min(1.0, max(0.0, (d - acc) / max(sl, 1e-6)))
                p = a.lerp(b, t)
                along = (b - a).normalized()
                break
            acc += sl
        nrm = Vector(up) if i % 2 == 0 else along.cross(Vector(up)).normalized()
        out.append(_link(f"link{i}", p, along, nrm, L=L, W=W, r=r))
    ctx.add(K.merge_parts(out, ctx.uid("chain")), mat, uv="box", uv_scale=1.0, smooth=40, edge=0.8, patches=0.4)


def _padlock(ctx: K.Ctx, top, *, w: float = 0.05, h: float = 0.045, d: float = 0.022, shackle: float = 0.032,
             through=(1, 0, 0)) -> None:
    """Laminated steel padlock hanging with its shackle top at `top`; the shackle plane faces
    `through` (the bar it is hooked over runs along that axis)."""
    t = Vector(top)
    body_c = t - Vector((0, 0, shackle + h / 2))
    plates = []
    n = 6
    for k in range(n):
        z0 = body_c.z - h / 2 + h * k / n
        plates.append(K.box("lam", (w, d, h / n - 0.0008), center=(body_c.x, body_c.y, z0 + h / n / 2), bevel=0.0018))
    body = K.merge_parts(plates, ctx.uid("padbody"))
    ctx.add(body, "lock_steel", uv="box", uv_scale=1.0, smooth=None, edge=1.0, patches=0.5)
    # Keyway cover and slot on the front face.
    kc = K.cyl("keyc", 0.008, 0.003, segs=10, axis="Y", center=(body_c.x, body_c.y - d / 2 - 0.0012, body_c.z - h * 0.18))
    ctx.add(kc, "trap_brass", uv="box", uv_scale=1.0, smooth=35)
    slot = K.box("slot", (0.0018, 0.002, 0.008), center=(body_c.x, body_c.y - d / 2 - 0.0028, body_c.z - h * 0.18))
    ctx.add(slot, "trap_alarm_dark", uv="box", ao=False)
    # Shackle: an inverted U of round bar rising out of the body top.
    a = Vector(through).normalized()
    s = []
    for k in range(9):
        ang = math.pi * k / 8
        s.append(Vector((body_c.x, body_c.y, t.z - shackle * 0.42)) + a * (math.cos(ang) * w * 0.3) + Vector((0, 0, math.sin(ang) * shackle * 0.42)))
    legs = [Vector((s[0].x, s[0].y, body_c.z + h / 2 - 0.004))] + s + [Vector((s[-1].x, s[-1].y, body_c.z + h / 2 - 0.004))]
    sh = K.tube("shackle", legs, 0.0042, segs=8)
    ctx.add(sh, "lock_steel", uv="cyl", uv_axis=2, smooth=50, edge=0.6)


def _screw(ctx: K.Ctx, at, normal="-y", r: float = 0.0045, mat: str = "lock_zinc") -> None:
    """Domed slotted screw head on a surface facing `normal`."""
    head = K.lathe("screw", [(0.0, 0.0), (r, 0.0), (r * 0.95, 0.0012), (r * 0.6, 0.0022), (0.0, 0.0026)], segs=8)
    n = K.AXES[normal] if isinstance(normal, str) else Vector(normal)
    # Lathe axis Z -> the surface normal.
    rot = Vector((0, 0, 1)).rotation_difference(n).to_matrix().to_4x4()
    head.data.transform(Matrix.Translation(Vector(at)) @ rot)
    ctx.add(head, mat, uv="box", uv_scale=1.0, smooth=40, edge=0.6)


# ============================================================================================
# Bear trap
# ============================================================================================

JAW_R = 0.112
POST_X = 0.118


def _jaw_flat(ctx: K.Ctx, side: int, r: random.Random) -> None:
    """One jaw lying open: a half ring on the +Y (side 1) or -Y (side -1) side, teeth up."""
    a0, a1 = (0.0, 180.0) if side > 0 else (180.0, 360.0)
    pts = _arc((0, 0, 0.012), JAW_R, a0, a1, 18)
    jaw = K.sweep(ctx.uid("jaw"), pts, _rect(0.011, 0.0062), up=(0, 0, 1))
    ctx.add(jaw, "trap_steel", uv="box", uv_scale=1.0, smooth=35, edge=1.0, patches=0.5)
    teeth = []
    for k in range(9):
        a = math.radians(a0 + (a1 - a0) * (k + 0.5) / 9)
        p = Vector((JAW_R * math.cos(a), JAW_R * math.sin(a), 0.0148))
        tang = Vector((-math.sin(a), math.cos(a), 0.0))
        inward = -Vector((math.cos(a), math.sin(a), 0.0))
        tooth = K.prism("tooth", [(-0.0058, 0.0), (0.0058, 0.0), (0.0, 0.0125 + r.uniform(-0.0015, 0.001))], 0.0042, plane="XZ")
        K.orient(tooth, tang, (0, 0, 1), p + inward * 0.002)
        teeth.append(tooth)
    ctx.add(K.merge_parts(teeth, ctx.uid("teeth")), "trap_steel", uv="box", uv_scale=1.0, edge=1.2, patches=0.6)


def _jaw_closed(ctx: K.Ctx, side: int, r: random.Random) -> None:
    """One jaw standing shut: a half ring in the upright XZ plane, teeth meshed with the other's."""
    y = side * 0.0045
    pts = _arc((0, y, 0.016), JAW_R * 0.96, 0.0, 180.0, 18, plane="XZ")
    jaw = K.sweep(ctx.uid("jaw"), pts, _rect(0.011, 0.0062), up=(0, 1, 0))
    ctx.add(jaw, "trap_steel", uv="box", uv_scale=1.0, smooth=35, edge=1.0, patches=0.5)
    teeth = []
    for k in range(9):
        a = math.radians(180.0 * (k + 0.5 + (0.5 if side > 0 else 0.0)) / 9.5)
        p = Vector((JAW_R * 0.96 * math.cos(a), y - side * 0.004, 0.016 + JAW_R * 0.96 * math.sin(a)))
        tang = Vector((-math.sin(a), 0.0, math.cos(a)))
        tooth = K.prism("tooth", [(-0.0058, 0.0), (0.0058, 0.0), (0.0, 0.0115 + r.uniform(-0.0015, 0.001))], 0.0042, plane="XZ")
        K.orient(tooth, tang, (0, -side, 0), p)
        teeth.append(tooth)
    ctx.add(K.merge_parts(teeth, ctx.uid("teeth")), "trap_steel", uv="box", uv_scale=1.0, edge=1.2, patches=0.6)


def _spring(ctx: K.Ctx, sgn: int, open_deg: float) -> None:
    """Long flat spring past one jaw post (sgn = +1 right, -1 left): a strip folded back on itself,
    its eye round the jaw ends. open_deg spreads the upper leaf (compressed ~4, relaxed ~22)."""
    L = 0.205
    x0, x1 = POST_X + 0.012, POST_X + 0.012 + L
    bend_r = 0.009
    lower = [Vector((x0, 0.0, 0.0035)), Vector((x1, 0.0, 0.0035))]
    bend = [Vector((x1 + bend_r * math.sin(math.radians(a)), 0.0, 0.0035 + bend_r - bend_r * math.cos(math.radians(a))))
            for a in range(15, 181, 33)]
    top_z = bend[-1].z + math.tan(math.radians(open_deg)) * L
    upper = [Vector((x1, 0.0, bend[-1].z)), Vector((x0 + 0.03, 0.0, top_z - 0.004)), Vector((x0, 0.0, top_z))]
    path = lower + bend + upper
    if sgn < 0:
        path = [Vector((-p.x, p.y, p.z)) for p in path]
    strip = K.sweep(ctx.uid("spring"), path, [(-0.0026, -0.0135), (0.0026, -0.0135), (0.0026, 0.0135), (-0.0026, 0.0135)], up=(0, 1, 0))
    ctx.add(strip, "trap_spring_steel", uv="box", uv_scale=1.0, smooth=35, edge=0.9, patches=0.5)
    # The eye: a squared loop of strip round the jaw ends, riding on the post.
    ex = sgn * (POST_X + 0.006)
    ez = 0.012 + (top_z - 0.012) * 0.5
    eye = K.tube(ctx.uid("eye"), [(ex, -0.017, ez - 0.012), (ex, 0.017, ez - 0.012), (ex, 0.017, ez + 0.012), (ex, -0.017, ez + 0.012)],
                 0.003, segs=4, closed=True)
    ctx.add(eye, "trap_spring_steel", uv="box", uv_scale=1.0, edge=0.9)


def _bear_base(ctx: K.Ctx, r: random.Random, *, sprung: bool) -> None:
    base = K.box("base", (2 * POST_X + 0.03, 0.03, 0.007), center=(0, 0, 0.0035), bevel=0.0015)
    ctx.add(base, "trap_steel", uv="box", uv_scale=1.0, edge=1.0, patches=0.6)
    for s in (-1, 1):
        post = K.box("post", (0.008, 0.026, 0.03), center=(s * POST_X, 0, 0.02), bevel=0.0015)
        ctx.add(post, "trap_steel", uv="box", uv_scale=1.0, edge=1.0)
        rivet = K.cyl("rivet", 0.004, 0.034, segs=8, axis="Y", center=(s * POST_X, 0, 0.026))
        ctx.add(rivet, "trap_steel", uv="cyl", uv_axis=1, smooth=40)
    # Pan (trigger plate) on its stem, and the dog that holds a jaw down while set.
    pz = 0.004 if sprung else 0.021
    pan = K.cyl("pan", 0.042, 0.004, segs=16, center=(0.0, 0.0, pz + 0.002), bevel=0.001)
    ctx.add(pan, "trap_steel", uv="planar", uv_axis=2, smooth=30, edge=0.8, patches=0.7)
    stem = K.cyl("stem", 0.006, max(0.004, pz), segs=8, center=(0, 0, pz / 2))
    ctx.add(stem, "trap_steel", uv="cyl", smooth=40)
    if sprung:
        dog = K.box("dog", (0.075, 0.01, 0.004), center=(-0.07, 0.03, 0.009), bevel=0.001)
        K.place(dog, rot=(0, 0, 38))
    else:
        dog = K.box("dog", (0.085, 0.01, 0.004), center=(-0.055, -0.004, 0.021), bevel=0.001)
        K.place(dog, rot=(0, 0, -4))
    ctx.add(dog, "trap_steel", uv="box", uv_scale=1.0, edge=1.0)
    # Chain from the left spring end to its ring.
    cx = -(POST_X + 0.24)
    chain_pts = [(cx, 0.0, 0.004), (cx - 0.05, 0.03 if sprung else 0.04, 0.004), (cx - 0.11, 0.075, 0.004), (cx - 0.15, 0.11 if not sprung else 0.06, 0.004)]
    _chain(ctx, chain_pts)
    ring = K.tube(ctx.uid("ring"), _arc((cx - 0.175, 0.125 if not sprung else 0.07, 0.006), 0.024, 0, 360, 14)[:-1], 0.0045, segs=6, closed=True)
    ctx.add(ring, "trap_chain", uv="box", uv_scale=1.0, smooth=40, edge=0.8)


def _debris(ctx: K.Ctx, r: random.Random, *, cover: bool) -> None:
    """Plaster lumps, a newspaper sheet and splinters: over one jaw and spring (cover) or kicked
    aside (sprung)."""
    rr = random.Random(r.random())
    spots = [(-0.17, -0.05), (-0.11, -0.1), (-0.05, -0.12), (0.2, 0.05), (0.27, -0.03), (-0.24, 0.02), (0.08, 0.12)]
    if not cover:
        spots = [(x * 1.6 + 0.04, y * 1.8 - 0.05) for x, y in spots]
    for k, (x, y) in enumerate(spots):
        lump = K.chunk(f"lump{k}", rr.uniform(0.025, 0.055), rr, n=12, flat=0.55)
        K.place(lump, (x + rr.uniform(-0.02, 0.02), y + rr.uniform(-0.02, 0.02), 0.012), rot=(rr.uniform(-20, 20), rr.uniform(-20, 20), rr.uniform(0, 360)))
        K.lift_min(lump, 0.0)
        ctx.add(lump, "trap_plaster", uv="box", uv_scale=2.0, smooth=None, edge=0.8, patches=0.4)
    # Newspaper laid over the left spring and the near jaw (or shoved off to the side).
    px, py = (-0.2, -0.04) if cover else (-0.36, -0.12)
    sheet = K.grid("paper", 0.26, 0.19, 8, 6, center=(0, 0, 0))
    K.uv_planar(sheet, 2, rect=K.ATLAS_PAPER["news"])

    def drape(co):
        # Lies over the jaw ring and spring: humped where steel is under it, curled at the edge.
        hump = 0.02 * math.exp(-((co.x + 0.02) / 0.09) ** 2) if cover else 0.004
        curl = 0.025 * max(0.0, (co.y - 0.06) / 0.035) ** 2
        return Vector((co.x, co.y, 0.004 + hump + curl))
    K.map_verts(sheet, drape)
    K.crumple(sheet, 0.006, scale=9.0, seed=rr.randint(0, 999))
    K.place(sheet, (px, py, 0.0), rot=(0, 0, rr.uniform(-25, 25)))
    K.solidify(sheet, 0.0012, offset=-1.0, even=False)
    ctx.add(sheet, "paper_trash", uv=None, smooth=50, patches=0.0, edge=0.2)
    for k in range(4):
        L = rr.uniform(0.07, 0.16)
        spl = P.plank(f"spl{k}", L, rr.uniform(0.008, 0.016), rr.uniform(0.004, 0.008), bevel=0.0008)
        P.break_end(spl, L / 2 - 0.01, rr, side=1, depth=0.02)
        x, y = rr.uniform(-0.3, 0.3), rr.uniform(-0.13, 0.13)
        K.place(spl, (x, y, 0.006), rot=(rr.uniform(-6, 6), 0, rr.uniform(0, 180)))
        K.lift_min(spl, 0.0)
        ctx.add(spl, "wood_weathered", uv="box", uv_scale=1.0, long_axis=0, edge=0.8)


def trap_bear(ctx: K.Ctx) -> None:
    """Long-spring bear trap set open on the floor, the pan up and the dog across one jaw, half
    under plaster lumps, splinters and a sheet of newspaper; the chain trails to its ring."""
    r = ctx.rnd("bear")
    _bear_base(ctx, r, sprung=False)
    _jaw_flat(ctx, 1, r)
    _jaw_flat(ctx, -1, r)
    for s in (-1, 1):
        _spring(ctx, s, 3.5)
    _debris(ctx, r, cover=True)


def trap_bear_sprung(ctx: K.Ctx) -> None:
    """The bear trap after it fired: jaws stood up and shut with the teeth meshed, the springs
    relaxed open, the pan dropped and the debris scattered."""
    r = ctx.rnd("bear")
    _bear_base(ctx, r, sprung=True)
    _jaw_closed(ctx, 1, r)
    _jaw_closed(ctx, -1, r)
    for s in (-1, 1):
        _spring(ctx, s, 17.0)
    _debris(ctx, r, cover=False)


# ============================================================================================
# Shotgun trip-wire rig
# ============================================================================================

SEAT_Z = 0.455


def _chair(ctx: K.Ctx, r: random.Random) -> None:
    """Spindle-back kitchen chair in flaking green paint."""
    mat = "wood_painted_green"
    seat = K.box("seat", (0.41, 0.39, 0.028), center=(0, 0, SEAT_Z - 0.014), bevel=0.008, bevel_segs=2, cuts=(2, 2, 0))
    ctx.add(seat, mat, uv="box", uv_scale=1.0, long_axis=0, edge=1.2, patches=0.6)
    legs = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            top = SEAT_Z - 0.028
            leg = K.loft("leg", [
                [(sx * 0.17 - 0.013, sy * 0.155 - 0.013, 0.0), (sx * 0.17 + 0.013, sy * 0.155 - 0.013, 0.0),
                 (sx * 0.17 + 0.013, sy * 0.155 + 0.013, 0.0), (sx * 0.17 - 0.013, sy * 0.155 + 0.013, 0.0)],
                [(sx * 0.172 - 0.017, sy * 0.157 - 0.017, top), (sx * 0.172 + 0.017, sy * 0.157 - 0.017, top),
                 (sx * 0.172 + 0.017, sy * 0.157 + 0.017, top), (sx * 0.172 - 0.017, sy * 0.157 + 0.017, top)]])
            legs.append(leg)
    ctx.add(K.merge_parts(legs, ctx.uid("legs")), mat, uv="box", uv_scale=1.0, long_axis=2, edge=1.2, patches=0.6)
    rails = []
    for sx in (-1, 1):
        rails.append(K.cyl("side", 0.009, 0.3, segs=8, axis="Y", center=(sx * 0.172, 0.0, 0.16)))
    rails.append(K.cyl("front", 0.009, 0.34, segs=8, axis="X", center=(0, -0.157, 0.2)))
    rails.append(K.cyl("back", 0.009, 0.34, segs=8, axis="X", center=(0, 0.157, 0.14)))
    ctx.add(K.merge_parts(rails, ctx.uid("rails")), mat, uv="cyl", uv_axis=0, smooth=45, edge=1.0)
    posts = []
    for sx in (-1, 1):
        posts.append(K.tube("post", [(sx * 0.172, 0.157, SEAT_Z - 0.03), (sx * 0.172, 0.172, 0.66), (sx * 0.17, 0.2, 0.88)], [0.017, 0.016, 0.014], segs=8))
    ctx.add(K.merge_parts(posts, ctx.uid("posts")), mat, uv="cyl", uv_axis=2, smooth=45, edge=1.0)
    top = K.box("toprail", (0.37, 0.026, 0.07), center=(0, 0.198, 0.835), bevel=0.006, cuts=(4, 0, 0))
    K.bend(top, 1, 0.5, along=0, origin=0.0)
    ctx.add(top, mat, uv="box", uv_scale=1.0, long_axis=0, edge=1.2, patches=0.6)
    sp = [K.tube("spindle", [(x, 0.165, SEAT_Z), (x, 0.18, 0.66), (x, 0.195, 0.8)], [0.008, 0.0095, 0.008], segs=6) for x in (-0.09, 0.0, 0.09)]
    ctx.add(K.merge_parts(sp, ctx.uid("spindles")), mat, uv="cyl", uv_axis=2, smooth=45, edge=1.0)


def _shotgun(ctx: K.Ctx, r: random.Random) -> dict:
    """Sawn-off side-by-side lying on the seat, barrels forward (-Y) over the seat front.
    Returns key points (muzzle, trigger)."""
    z = SEAT_Z + 0.056  # barrel axis
    y_mz, y_br = -0.465, -0.145
    blen = y_br - y_mz
    barrels = []
    for sx in (-1, 1):
        b = K.lathe("barrel", [(0.0, 0.0), (0.0108, 0.0), (0.0108, blen * 0.4), (0.0102, blen), (0.0088, blen), (0.0088, blen - 0.028),
                               (0.0, blen - 0.028)], segs=12, cap_bottom=False, cap_top=False)
        # Lathe axis +Z -> forward (-Y), breech at y_br.
        b.data.transform(Matrix.Translation((sx * 0.0104, y_br, z)) @ Matrix.Rotation(math.radians(90), 4, "X"))
        b.data.update()
        barrels.append(b)
    ctx.add(K.merge_parts(barrels, ctx.uid("barrels")), "trap_gun_barrel", uv="cyl", uv_axis=1, smooth=40, edge=0.8, patches=0.5)
    rib = K.box("rib", (0.006, blen - 0.01, 0.004), center=(0, (y_mz + y_br) / 2, z + 0.0115), bevel=0.001)
    ctx.add(rib, "trap_gun_barrel", uv="box", uv_scale=1.0, edge=0.8)
    lugs = K.box("lugs", (0.016, blen - 0.02, 0.006), center=(0, (y_mz + y_br) / 2 + 0.01, z - 0.012), bevel=0.001)
    ctx.add(lugs, "trap_gun_barrel", uv="box", uv_scale=1.0, edge=0.8)
    fore = K.box("fore", (0.04, 0.15, 0.022), center=(0, y_br - 0.075, z - 0.019), bevel=0.006, bevel_segs=2, cuts=(0, 2, 0))
    ctx.add(fore, "trap_gun_stock", uv="box", uv_scale=1.0, long_axis=1, smooth=45, edge=0.9)
    rec = K.box("receiver", (0.044, 0.1, 0.05), center=(0, y_br + 0.05, z - 0.004), bevel=0.005, bevel_segs=2)
    ctx.add(rec, "trap_gun_barrel", uv="box", uv_scale=1.0, smooth=35, edge=1.0, patches=0.6)
    lever = K.box("lever", (0.012, 0.045, 0.006), center=(0.004, y_br + 0.105, z + 0.024), bevel=0.0015)
    K.place(lever, rot=(0, 0, 10))
    ctx.add(lever, "trap_gun_barrel", uv="box", uv_scale=1.0, edge=1.0)
    pin = K.cyl("pin", 0.004, 0.05, segs=8, axis="X", center=(0, y_br + 0.006, z - 0.02))
    ctx.add(pin, "trap_gun_barrel", uv="cyl", uv_axis=0, smooth=40)
    gz = z - 0.03
    gy = y_br + 0.075
    guard = K.tube(ctx.uid("guard"), [(0, gy - 0.03, gz + 0.003), (0, gy - 0.03, gz - 0.012), (0, gy - 0.01, gz - 0.024),
                                      (0, gy + 0.02, gz - 0.024), (0, gy + 0.04, gz - 0.012), (0, gy + 0.045, gz + 0.003)], 0.003, segs=5)
    ctx.add(guard, "trap_gun_barrel", uv="cyl", smooth=40, edge=0.8)
    trigs = []
    for k, dy in enumerate((-0.006, 0.012)):
        t = K.tube("trig", [(0, gy + dy, gz), (0, gy + dy - 0.004, gz - 0.01), (0, gy + dy + 0.002, gz - 0.017)], 0.0028, segs=5)
        trigs.append(t)
    ctx.add(K.merge_parts(trigs, ctx.uid("triggers")), "trap_gun_barrel", uv="cyl", smooth=40)
    # Cut-down stock: wrist into a short, sawn butt resting on the seat.
    sy0 = y_br + 0.1
    stock = K.loft("stock", [
        [(-0.018, sy0, z - 0.03), (0.018, sy0, z - 0.03), (0.018, sy0, z + 0.016), (-0.018, sy0, z + 0.016)],
        [(-0.016, sy0 + 0.06, z - 0.034), (0.016, sy0 + 0.06, z - 0.034), (0.016, sy0 + 0.06, z + 0.006), (-0.016, sy0 + 0.06, z + 0.006)],
        [(-0.021, sy0 + 0.12, z - 0.052), (0.021, sy0 + 0.12, z - 0.052), (0.021, sy0 + 0.12, z + 0.008), (-0.021, sy0 + 0.12, z + 0.008)],
        [(-0.022, sy0 + 0.205, z - 0.056), (0.022, sy0 + 0.205, z - 0.056), (0.022, sy0 + 0.205, z + 0.012), (-0.022, sy0 + 0.205, z + 0.012)]])
    ctx.add(stock, "trap_gun_stock", uv="box", uv_scale=1.0, long_axis=1, smooth=40, edge=1.0, patches=0.6)
    return {"muzzle": Vector((0, y_mz, z)), "trigger": Vector((0, gy + 0.012, gz - 0.017)), "z": z}


def trap_shotgun_rig(ctx: K.Ctx) -> None:
    """A sawn-off shotgun lashed to a kitchen chair, barrels over the seat front, raised level on
    a wood block; cord wraps round the barrels and the seat front, round the stock and a spindle,
    and a cord from the front trigger down to a nail in the front stretcher."""
    r = ctx.rnd("rig")
    _chair(ctx, r)
    block = K.box("block", (0.09, 0.05, 0.034), center=(0, -0.155, SEAT_Z + 0.017), bevel=0.003)
    K.place(block, rot=(0, 0, 4))
    ctx.add(block, "wood_weathered", uv="box", uv_scale=1.0, long_axis=0, edge=1.0)
    g = _shotgun(ctx, r)
    z = g["z"]
    cords = []
    # Two wraps round barrels, block and seat front.
    for k, y in enumerate((-0.165, -0.142)):
        loop = [(-0.03, y, z + 0.014), (0.03, y, z + 0.014), (0.05, y + 0.002, SEAT_Z - 0.012), (0.05, y, SEAT_Z - 0.04),
                (-0.05, y, SEAT_Z - 0.04), (-0.05, y + 0.002, SEAT_Z - 0.012)]
        cords.append(K.tube(f"wrap{k}", loop, 0.0035, segs=5, closed=True))
    # Round the wrist and the centre spindle.
    loop2 = [(-0.025, 0.06, z + 0.012), (0.012, 0.075, z + 0.02), (0.012, 0.172, z + 0.035), (-0.012, 0.18, z + 0.03),
             (-0.012, 0.172, z - 0.03), (0.02, 0.07, z - 0.05)]
    cords.append(K.tube("wrap_back", loop2, 0.0035, segs=5, closed=True))
    # Trigger cord down to the nail in the front stretcher.
    t = g["trigger"]
    nail = Vector((0.0, -0.168, 0.2))
    cords.append(K.tube("trig_cord", [t, t + Vector((0, -0.02, -0.03)), Vector((0.0, -0.17, SEAT_Z - 0.06)), nail], 0.0022, segs=4))
    ctx.add(K.merge_parts(cords, ctx.uid("cords")), "trap_cord", uv="cyl", uv_axis=1, smooth=45, patches=0.0, edge=0.3)
    nl = K.cyl("nail", 0.003, 0.012, segs=6, axis="Y", center=(nail.x, nail.y - 0.004, nail.z))
    ctx.add(nl, "lock_zinc", uv="cyl", smooth=40)
    ctx.col_box((-0.21, -0.2, 0.0), (0.21, 0.21, SEAT_Z))


# ============================================================================================
# Floor patches
# ============================================================================================

def trap_creaky_boards(ctx: K.Ctx) -> None:
    """A 1 x 1 m patch of old fir boards come loose: cupped and bowed, one end lifted, nails
    popped half out. Lies on the floor finish (2 cm proud)."""
    r = ctx.rnd("boards")
    n = 7
    w = 0.136
    gap = (1.0 - n * w) / n
    for k in range(n):
        y = -0.5 + gap / 2 + w / 2 + k * (w + gap)
        L = 1.0 - r.uniform(0.0, 0.02)
        bow = r.choice((0.0, 0.0, -0.008, -0.012)) if k not in (2, 5) else 0.0
        cup = r.uniform(0.002, 0.005)
        twist = r.uniform(-1.2, 1.2) if k != 2 else 0.0
        b = P.plank(f"b{k}", L, w, 0.02, bevel=0.0025, cuts=8, bow=bow, cup=cup, twist=twist)
        K.place(b, (r.uniform(-0.01, 0.01), y, 0.01))
        if k == 2:
            # Lifted at one end: rides up over the joist.
            K.map_verts(b, lambda co: Vector((co.x, co.y, co.z + 0.03 * max(0.0, (co.x + 0.1) / 0.6) ** 2)))
        if k == 5:
            K.map_verts(b, lambda co: Vector((co.x, co.y, co.z + 0.012 * math.sin(math.pi * (co.x + 0.5)))))
        ctx.add(b, "trap_boards_damp" if k in (2, 5) else "trap_boards", uv="box", uv_scale=1.0, long_axis=0, smooth=None,
                edge=1.0, patches=0.5)
    nails = []
    for k in range(n):
        y = -0.5 + gap / 2 + w / 2 + k * (w + gap)
        for x in (-0.45, 0.45):
            for dy in (-0.035, 0.035):
                popped = r.random() < 0.3 or (k == 2 and x > 0)
                h = r.uniform(0.006, 0.014) if popped else 0.0
                z0 = 0.021 + (0.03 * max(0.0, (x + 0.1) / 0.6) ** 2 if k == 2 else 0.0)
                if popped:
                    nails.append(K.cyl("shank", 0.0016, h, segs=5, center=(x, y + dy, z0 + h / 2)))
                nails.append(K.cyl("head", 0.0042, 0.0018, segs=7, center=(x, y + dy, z0 + h + 0.0009)))
    ctx.add(K.merge_parts(nails, ctx.uid("nails")), "trap_steel", uv="box", uv_scale=1.0, smooth=None, edge=0.8)


# ============================================================================================
# Alarms
# ============================================================================================

def trap_alarm_box(ctx: K.Ctx) -> None:
    """Battery door/window alarm screwed to a frame: siren grille, red LED, key switch, a hazard
    sticker, and a magnetic contact on a thin lead off to one side."""
    W, D, H = 0.105, 0.036, 0.078
    body = K.box("body", (W, D, H), center=(0, -D / 2, H / 2), bevel=0.006, bevel_segs=2)
    ctx.add(body, "trap_alarm_plastic", uv="box", uv_scale=1.0, smooth=40, edge=0.6, patches=0.6)
    grille = []
    for k in range(6):
        grille.append(K.box("slot", (0.04, 0.003, 0.0032), center=(-0.018, -D - 0.0006, 0.022 + k * 0.0075), bevel=0.0008))
    ctx.add(K.merge_parts(grille, ctx.uid("grille")), "trap_alarm_dark", uv="box", ao=False)
    led = K.lathe("led", [(0.0, 0.0), (0.0035, 0.0), (0.0035, 0.002), (0.0022, 0.0042), (0.0, 0.0048)], segs=10)
    led.data.transform(Matrix.Translation((0.032, -D, 0.058)) @ Matrix.Rotation(math.radians(90), 4, "X"))
    led.data.update()
    ctx.add(led, "trap_alarm_led", uv="box", ao=False, smooth=40)
    key = K.cyl("keysw", 0.0085, 0.006, segs=12, axis="Y", center=(0.032, -D - 0.003, 0.03))
    ctx.add(key, "lock_steel", uv="box", uv_scale=1.0, smooth=40)
    ks = K.box("keyslot", (0.0015, 0.002, 0.007), center=(0.032, -D - 0.0065, 0.03))
    ctx.add(ks, "trap_alarm_dark", uv="box", ao=False)
    label = K.box("label", (0.032, 0.0006, 0.014), center=(-0.018, -D - 0.0003, 0.068))
    ctx.add(label, "trap_label", uv="box", uv_scale=1.0, patches=0.3)
    for sx in (-1, 1):
        _screw(ctx, (sx * 0.04, -D - 0.0002, 0.008), "-y", r=0.0035, mat="lock_zinc")
    # Magnet contact on its lead.
    contact = K.box("contact", (0.042, 0.012, 0.012), center=(0.115, -0.006, 0.012), bevel=0.002)
    ctx.add(contact, "trap_alarm_plastic", uv="box", uv_scale=1.0, smooth=40, patches=0.5)
    magnet = K.box("magnet", (0.03, 0.011, 0.01), center=(0.116, -0.0055, -0.006), bevel=0.002)
    ctx.add(magnet, "trap_alarm_plastic", uv="box", uv_scale=1.0, smooth=40, patches=0.5)
    lead = K.tube("lead", [(0.05, -0.012, 0.012), (0.07, -0.004, 0.006), (0.085, -0.003, 0.01), (0.094, -0.006, 0.012)], 0.0016, segs=4)
    ctx.add(lead, "trap_alarm_dark", uv="cyl", smooth=40)


def trap_alarm_bell(ctx: K.Ctx) -> None:
    """Brass hand bell hung from a screw eye on a cord; the game strings the cord across the
    passage below it."""
    prof = [(0.0, 0.012), (0.036, 0.0), (0.044, 0.0), (0.045, 0.004), (0.038, 0.012), (0.03, 0.035), (0.024, 0.06),
            (0.019, 0.078), (0.01, 0.088), (0.0, 0.09)]
    bell = K.lathe("bell", [(r, z) for r, z in prof], segs=18, cap_bottom=False, cap_top=False)
    ctx.add(bell, "trap_brass", uv="cyl", uv_axis=2, smooth=50, edge=0.8, patches=0.5)
    inner = K.lathe("inner", [(0.0, 0.016), (0.034, 0.004), (0.041, 0.0015)], segs=18, cap_bottom=False, cap_top=False)
    ctx.add(inner, "trap_alarm_dark", uv="cyl", smooth=50, ao=False)
    clap = K.blob("clapper", 0.008, subdiv=1, center=(0.0, 0.0, 0.012))
    ctx.add(clap, "trap_steel", uv="box", uv_scale=1.0, smooth=50)
    rod = K.cyl("rod", 0.0018, 0.07, segs=5, center=(0, 0, 0.05))
    ctx.add(rod, "trap_steel", uv="cyl", smooth=40)
    top = K.tube(ctx.uid("loop"), _arc((0, 0, 0.098), 0.009, 0, 360, 10, plane="XZ")[:-1], 0.0022, segs=5, closed=True)
    ctx.add(top, "trap_brass", uv="box", uv_scale=1.0, smooth=40)
    cord = K.tube("cord", [(0, 0, 0.106), (0.002, 0.001, 0.4), (0.0, 0.0, 0.745)], 0.0024, segs=5)
    ctx.add(cord, "trap_cord", uv="cyl", uv_axis=2, smooth=45, patches=0.0)
    eye = K.tube(ctx.uid("eye"), _arc((0, 0, 0.756), 0.0075, 0, 360, 10, plane="XZ")[:-1], 0.0018, segs=5, closed=True)
    ctx.add(eye, "lock_zinc", uv="box", uv_scale=1.0, smooth=40)
    plate = K.box("plate", (0.06, 0.04, 0.012), center=(0, 0, 0.77), bevel=0.002)
    ctx.add(plate, "wood_weathered", uv="box", uv_scale=1.0, edge=1.0)


# ============================================================================================
# Door lock cues
# ============================================================================================

def _hasp_plate(ctx: K.Ctx) -> None:
    plate = K.box("hplate", (0.13, 0.003, 0.05), center=(-0.105, -0.0015, 0.0), bevel=0.0012)
    ctx.add(plate, "lock_zinc", uv="box", uv_scale=1.0, edge=1.0, patches=0.6)
    for x in (-0.155, -0.115, -0.075):
        for z in (-0.013, 0.013):
            _screw(ctx, (x, -0.003, z))
    knuckle = K.cyl("knuckle", 0.0055, 0.05, segs=8, center=(-0.036, -0.005, 0.0))
    ctx.add(knuckle, "lock_zinc", uv="cyl", smooth=40, edge=0.8)


def _hasp_strap(ctx: K.Ctx, open_deg: float) -> None:
    """The hinged strap from the knuckle across the gap and out to the casing (Z-bent), with its
    slot; open_deg swings it away from the casing about the knuckle (vertical axis)."""
    path = [(-0.036, -0.008, 0.0), (-0.012, -0.01, 0.0), (0.004, -0.04, 0.0), (0.02, -CASING - 0.006, 0.0),
            (0.115, -CASING - 0.006, 0.0)]
    strap = K.sweep(ctx.uid("strap"), path, [(-0.0022, -0.021), (0.0022, -0.021), (0.0022, 0.021), (-0.0022, 0.021)], up=(0, 0, 1))
    if open_deg:
        strap.data.transform(Matrix.Translation((-0.036, -0.005, 0.0)) @ Matrix.Rotation(math.radians(-open_deg), 4, "Z")
                             @ Matrix.Translation((0.036, 0.005, 0.0)))
        strap.data.update()
    ctx.add(strap, "lock_zinc", uv="box", uv_scale=1.0, smooth=None, edge=1.0, patches=0.6)


def lock_padlock(ctx: K.Ctx) -> None:
    """Hasp and staple bridging leaf and casing, a laminated padlock through the staple."""
    ctx.ground_clamp = False
    _hasp_plate(ctx)
    _hasp_strap(ctx, 0.0)
    splate = K.box("splate", (0.06, 0.003, 0.05), center=(0.08, -CASING - 0.0015, 0.0), bevel=0.0012)
    ctx.add(splate, "lock_zinc", uv="box", uv_scale=1.0, edge=1.0, patches=0.6)
    for x in (0.06, 0.1):
        _screw(ctx, (x, -CASING - 0.003, 0.016))
        _screw(ctx, (x, -CASING - 0.003, -0.016))
    staple = K.tube(ctx.uid("staple"), [(0.072, -CASING - 0.002, -0.012), (0.072, -CASING - 0.02, -0.012),
                                         (0.072, -CASING - 0.026, -0.006), (0.072, -CASING - 0.026, 0.006),
                                         (0.072, -CASING - 0.02, 0.012), (0.072, -CASING - 0.002, 0.012)], 0.0035, segs=6)
    ctx.add(staple, "trap_steel", uv="cyl", smooth=40, edge=0.8)
    _padlock(ctx, (0.072, -CASING - 0.02, 0.006), through=(0, 1, 0))


def lock_hasp_open(ctx: K.Ctx) -> None:
    """What is left once the padlock is off: the strap swung open off the staple."""
    ctx.ground_clamp = False
    _hasp_plate(ctx)
    _hasp_strap(ctx, 118.0)


def lock_chain(ctx: K.Ctx) -> None:
    """A chain run from an eye bolt in the leaf to one in the casing, sagging between them, its
    ends joined by a padlock."""
    ctx.ground_clamp = False
    for x, y in ((-0.11, -0.002), (0.075, -CASING - 0.002)):
        rose = K.cyl("rose", 0.014, 0.004, segs=10, axis="Y", center=(x, y, 0.0))
        ctx.add(rose, "lock_zinc", uv="box", uv_scale=1.0, smooth=35)
        shank = K.cyl("shank", 0.004, 0.02, segs=6, axis="Y", center=(x, y - 0.012, 0.0))
        ctx.add(shank, "trap_steel", uv="cyl", smooth=40)
        eye = K.tube(ctx.uid("eyeb"), _arc((x, y - 0.03, 0.0), 0.011, 0, 360, 10, plane="XZ")[:-1], 0.0035, segs=6, closed=True)
        ctx.add(eye, "trap_steel", uv="box", uv_scale=1.0, smooth=40, edge=0.8)
    a = Vector((-0.11, -0.032, -0.012))
    b = Vector((0.075, -CASING - 0.032, -0.012))
    pts = []
    for k in range(9):
        t = k / 8
        p = a.lerp(b, t)
        p.z -= 0.13 * math.sin(math.pi * t) ** 0.9
        pts.append(p)
    lowest = pts[4]
    _chain(ctx, pts[:4] + [lowest + Vector((-0.012, 0, 0.004))], up=(0, 1, 0))
    _chain(ctx, [lowest + Vector((0.012, 0, 0.004))] + pts[5:], up=(0, 1, 0))
    _padlock(ctx, (lowest.x, lowest.y, lowest.z + 0.012), through=(1, 0, 0))


def lock_deadbolt(ctx: K.Ctx) -> None:
    """Keyed brass deadbolt: rose, cylinder collar and the keyway (above the knob)."""
    ctx.ground_clamp = False
    x = -0.065
    rose = K.lathe("rose", [(0.0, 0.0), (0.03, 0.0), (0.03, 0.002), (0.026, 0.006), (0.0, 0.006)], segs=16)
    rose.data.transform(Matrix.Translation((x, 0.0, 0.0)) @ Matrix.Rotation(math.radians(90), 4, "X"))
    rose.data.update()
    ctx.add(rose, "trap_brass", uv="box", uv_scale=1.0, smooth=40, edge=0.8, patches=0.5)
    cyl = K.lathe("cylinder", [(0.0, 0.0), (0.0165, 0.0), (0.0165, 0.012), (0.0145, 0.016), (0.0, 0.016)], segs=16)
    cyl.data.transform(Matrix.Translation((x, -0.006, 0.0)) @ Matrix.Rotation(math.radians(90), 4, "X"))
    cyl.data.update()
    ctx.add(cyl, "trap_brass", uv="box", uv_scale=1.0, smooth=40, edge=0.8, patches=0.5)
    keyway = K.box("keyway", (0.0024, 0.002, 0.013), center=(x, -0.0215, -0.001))
    ctx.add(keyway, "trap_alarm_dark", uv="box", ao=False)
    plug = K.cyl("plug", 0.0095, 0.0015, segs=14, axis="Y", center=(x, -0.0215, 0.0))
    ctx.add(plug, "trap_brass", uv="box", uv_scale=1.0, smooth=40)


def lock_bolt(ctx: K.Ctx) -> None:
    """Sliding barrel bolt on the inside face: back plate, two straps, the bolt thrown into the
    jamb, its knob down in the locking notch."""
    ctx.ground_clamp = False
    plate = K.box("bplate", (0.15, 0.003, 0.042), center=(-0.1, -0.0015, 0.0), bevel=0.0012)
    ctx.add(plate, "lock_zinc", uv="box", uv_scale=1.0, edge=1.0, patches=0.6)
    for x in (-0.165, -0.035):
        for z in (-0.014, 0.014):
            _screw(ctx, (x, -0.003, z))
    straps = [K.box("bstrap", (0.016, 0.014, 0.024), center=(x, -0.009, 0.0), bevel=0.002) for x in (-0.13, -0.07)]
    ctx.add(K.merge_parts(straps, ctx.uid("bstraps")), "lock_zinc", uv="box", uv_scale=1.0, smooth=35, edge=1.0)
    bolt = K.cyl("bolt", 0.0068, 0.19, segs=10, axis="X", center=(-0.075, -0.0095, 0.0))
    ctx.add(bolt, "trap_steel", uv="cyl", uv_axis=0, smooth=40, edge=0.8)
    knob = K.tube("knob", [(-0.1, -0.0095, 0.0), (-0.1, -0.03, -0.004), (-0.1, -0.036, -0.012)], 0.0038, segs=6)
    ctx.add(knob, "trap_steel", uv="cyl", smooth=40)
    ball = K.blob("ball", 0.0075, subdiv=1, center=(-0.1, -0.037, -0.015))
    ctx.add(ball, "trap_steel", uv="box", uv_scale=1.0, smooth=50)


BUILDERS = {
    "trap_bear": trap_bear,
    "trap_bear_sprung": trap_bear_sprung,
    "trap_shotgun_rig": trap_shotgun_rig,
    "trap_creaky_boards": trap_creaky_boards,
    "trap_alarm_box": trap_alarm_box,
    "trap_alarm_bell": trap_alarm_bell,
    "lock_padlock": lock_padlock,
    "lock_hasp_open": lock_hasp_open,
    "lock_chain": lock_chain,
    "lock_deadbolt": lock_deadbolt,
    "lock_bolt": lock_bolt,
}


def build(params: dict, outputs: list[str]) -> None:
    """One GLB per condition, like props_ext_kit.run(), but door- and wall-mounted pieces skip the
    floor-plane AO (params ground_ao false): there is no floor under a padlock."""
    prop = params["prop"]
    fn = BUILDERS[prop]
    conds = params.get("conditions", ["clean"])
    if len(conds) != len(outputs):
        raise ValueError(f"{prop}: {len(conds)} conditions but {len(outputs)} outputs")
    for cond, out in zip(conds, outputs):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        ctx = K.Ctx(params, cond)
        fn(ctx)
        name = prop if cond == "clean" else f"{prop}_{cond}"
        obj = K.finalize(ctx, name, ao_samples=int(params.get("ao_samples", 20)), ao_dist=float(params.get("ao_dist", 0.6)),
                         ao_strength=float(params.get("ao_strength", 1.0)), ground_ao=bool(params.get("ground_ao", True)))
        for k, c in enumerate(ctx.cols):
            c.name = f"{name}_col{k}-convcolonly"
            c.data.name = c.name
            c.data.materials.clear()
            for p in c.data.polygons:
                p.use_smooth = False
        K.report(name, obj, ctx.cols)
        export.export_glb(out, [obj] + ctx.cols)
