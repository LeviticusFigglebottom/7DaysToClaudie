"""Wilderness set pieces, round 3 (agent X): props for four dungeons random worlds place outside towns.

Camp Tamarack (a church summer camp on a lake, the Cordon's family evacuation point): the routed entrance
arch, cabin and building plaques, a log canoe rack with its canoes, wooden camp bunks, the Cordon's family
registration board, split-log chapel benches and the birch cross by the water.
Elk Ridge Lodge (a two-storey log hunting lodge): the chinked log shell that wraps the lodge's kit rooms,
the fieldstone fireplace and its outside chimney stack, an antler chandelier, elk and deer head mounts, a
bearskin rug, the glass-fronted gun cabinet, the skinning shed's gambrel and the kennel runs, and the
cellar's meat rail.
The Cordon quarantine camp: an open-sided ward tent, restraint cots, the decontamination shower, a light
tower, Cordon fence and gate, sandbags, a scaffold watchtower, the shells of the morgue reefer and the
command trailer, body bags and the morgue's rack, and the ward markers.
The Haldane Place (a homestead held for a long time): scrap-and-log palisade sections and their gate, a
watch platform, raised garden beds, a rain catcher and a row of stakes.

Conventions (docs/ASSET_PIPELINE.md): metres, Z up, front -Y, origin bottom centre (floor props are centred
on the origin: PoiBuilder's collision box is the def's size centred there). Wall props: origin on the wall
plane, bottom centre. Ceiling props: origin on the ceiling plane, hanging below it. Shells: origin at the
kit room's plan centre on the ground (lib.props_outskirts_parts.Room), walls on or outside the edge lines,
openings cut where the plan's doors and windows are (the catalog passes them). Lettered faces map cells of
the w3_signs atlas (textures/gen/wild3.py: ATLAS below mirrors its CELLS).
'clean' is the place as it was kept, 'worn' a season abandoned, 'destroyed' broken or burnt.
"""
from __future__ import annotations

import math
import random

from mathutils import Vector

from lib import props_ext_kit as K
from lib import props_ext_parts as P
from lib import props_outskirts_parts as O
from lib import props_wild_parts as W
from lib import materials as MAT

SIGNS = "w3_signs"
UNIT = 256
ATLAS_PX = 2048.0
ATLAS = {
    "tamarack_arch": (0, 0, 6, 2),
    "sign_loon": (6, 0, 2, 0.5), "sign_heron": (6, 0.5, 2, 0.5), "sign_osprey": (6, 1, 2, 0.5),
    "sign_kestrel": (6, 1.5, 2, 0.5),
    "sign_mess": (0, 2, 2, 0.5), "sign_lodge": (2, 2, 2, 0.5), "sign_infirmary": (4, 2, 2, 0.5),
    "sign_canoes": (6, 2, 2, 0.5),
    "evac_header": (0, 2.5, 4, 0.5), "evac_lists": (0, 3, 4, 1),
    "evac_photos": (4, 2.5, 2, 1.5), "ward_letters": (6, 2.5, 2, 1.5),
    "decon_steps": (0, 4, 4, 1), "quarantine": (4, 4, 4, 1),
    "morgue": (0, 5, 3, 1), "cordon_cmd": (3, 5, 3, 1), "checkpoint": (6, 5, 2, 1),
    "elk_ridge": (0, 6, 4, 1), "haldane_warn": (4, 6, 4, 1),
    "kennel_names": (0, 7, 4, 1), "lodge_rules": (4, 7, 2, 1), "tally": (6, 7, 2, 1),
}

LOG = "w3_log_bark"
HEWN = "w3_log_hewn"
CHINK = "w3_chinking"
STONE = "stone_river"
MORTAR = "w3_chinking"
OD = "w3_canvas_od"

MAT.PREVIEW_COLORS.update({
    "w3_signs": (0.5, 0.4, 0.3), "w3_log_bark": (0.3, 0.2, 0.13), "w3_log_hewn": (0.36, 0.26, 0.17),
    "w3_chinking": (0.62, 0.6, 0.55), "w3_canvas_od": (0.26, 0.27, 0.19), "w3_canvas_white": (0.7, 0.7, 0.66),
    "w3_bag_white": (0.75, 0.75, 0.72),
})


def _rect(name: str, sub=None, inset: float = 2.0) -> tuple[float, float, float, float]:
    """Blender UV rect (u0, v0, u1, v1; v up) of an atlas cell, or of a sub-rectangle given as fractions
    (fx0, fy0, fx1, fy1) of the cell with y measured from the top of the image."""
    x, y, w, h = [v * UNIT for v in ATLAS[name]]
    if sub:
        fx0, fy0, fx1, fy1 = sub
        x, y, w, h = x + fx0 * w, y + fy0 * h, (fx1 - fx0) * w, (fy1 - fy0) * h
    x0, y0, x1, y1 = x + inset, y + inset, x + w - inset, y + h - inset
    return (x0 / ATLAS_PX, 1.0 - y1 / ATLAS_PX, x1 / ATLAS_PX, 1.0 - y0 / ATLAS_PX)


def _face(ctx, name, w, h, rect, loc, rot_z=0.0, *, wear=0.6, patches=0.35, edge=0.6, mat=SIGNS, rot=None):
    """Flat lettered face (w x h) facing -Y with an atlas rect mapped edge to edge; rot_z 180 faces +Y."""
    o = K.quad_sheet(name, (-w / 2, 0, -h / 2), (w / 2, 0, -h / 2), (w / 2, 0, h / 2), (-w / 2, 0, h / 2), 2, 2)
    K.uv_planar(o, 1, rect=rect)
    if rot is not None:
        K.place(o, (0, 0, 0), rot)
    K.place(o, (0, 0, 0), (0, 0, rot_z))
    K.place(o, loc)
    return ctx.add(o, mat, uv=None, wear=wear, patches=patches, edge=edge)


def _board(ctx, name, w, h, t, loc, mat, *, rot=(0, 0, 0), **kw):
    o = K.box(name, (w, t, h), bevel=0.004, cuts=(2, 0, 1))
    K.place(o, loc, rot)
    return ctx.add(o, mat, long_axis=0 if w >= h else 2, **kw)


def _log(ctx, name, a, b, r, seed, *, bark=LOG, end="wood_log_end", moss=0.25, sides=10, rings=4, taper=0.04):
    return O.add_log_between(ctx, name, a, b, r, seed, mat_bark=bark, mat_end=end, sides=sides, rings=rings,
                             taper=taper, moss=moss)


def _post(ctx, name, x, y, h, r, seed, *, bark=LOG, moss=0.3, lean=(0, 0)):
    a = Vector((x, y, -0.05))
    b = Vector((x + math.sin(math.radians(lean[0])) * h, y + math.sin(math.radians(lean[1])) * h, h))
    return _log(ctx, name, a, b, r, seed, bark=bark, moss=moss, rings=5)


def _stones_on_face(ctx, name, origin, u, v, w, h, seed, *, size=0.3, depth=0.1, mat=STONE, flat=0.45,
                    skip=None, courses=None):
    """Fieldstone veneer on a face: rough stones in staggered courses over the rectangle origin + u*[0, w] +
    v*[0, h], each bulging `depth` out along u x v (outward). skip(s, t) -> True leaves a stone out."""
    rr = random.Random(seed)
    u, v = Vector(u).normalized(), Vector(v).normalized()
    n = u.cross(v).normalized()
    out = []
    t = 0.0
    k = 0
    while t < h - 0.02:
        ch = size * rr.uniform(0.6, 0.95) if courses is None else courses
        ch = min(ch, h - t)
        s = -rr.uniform(0.0, size * 0.6) if k % 2 else 0.0
        while s < w - 0.02:
            sw = size * rr.uniform(0.8, 1.5)
            s0, s1 = max(0.0, s), min(w, s + sw)
            if s1 - s0 > 0.06 and not (skip and skip((s0 + s1) / 2, t + ch / 2)):
                c = Vector(origin) + u * ((s0 + s1) / 2) + v * (t + ch / 2) + n * (depth * 0.3)
                st = K.chunk(f"{name}{k}_{len(out)}", 1.0, rr, n=9, flat=1.0, elong=1.0)
                # Unit chunk scaled to the stone (x along the course, y up the face, z its bulge), then
                # turned so local X -> u, local Z -> n (local Y follows v) and moved onto the face.
                K.place(st, (0, 0, 0), scale=((s1 - s0) * 0.55, ch * 0.58, depth))
                K.orient(st, u, n, c)
                out.append(st)
            s += sw
        t += ch
        k += 1
    if not out:
        return None
    o = K.merge_parts(out, name)
    return ctx.add(o, mat, uv="box", uv_scale=1.6, smooth=None, patches=0.4, edge=0.8, moss=0.3)


def _centre_depth(ctx) -> float:
    """Moves every part so the model's depth (Blender Y) is centred on the origin: a prop placed
    `against` a wall is centred half its depth off the wall, so its back meets the wall face."""
    lo, hi = 1e9, -1e9
    for o in ctx.parts:
        for v in o.data.vertices:
            lo = min(lo, v.co.y)
            hi = max(hi, v.co.y)
    shift = -(lo + hi) * 0.5
    for o in ctx.parts:
        K.place(o, (0, shift, 0))
    return hi - lo


# ============================================================================================
# Camp Tamarack
# ============================================================================================

def w3_camp_arch(ctx: K.Ctx) -> None:
    """The camp's entrance: two bark-on posts and a log beam over the drive, the routed cedar sign
    CAMP TAMARACK hung under it on chains, a small cross on the beam, river stones at the post feet."""
    r = ctx.rnd("arch")
    for sx in (-1, 1):
        _post(ctx, f"post{sx}", sx * 2.45, 0.0, 4.25, 0.17, ctx.seed + sx, lean=(r.uniform(-1, 1), r.uniform(-1, 1)))
        for k in range(5):
            a = r.uniform(0, math.tau)
            O.add_stone(ctx, f"foot{sx}{k}", (sx * 2.45 + math.cos(a) * 0.32, math.sin(a) * 0.32, 0.04),
                        r.uniform(0.1, 0.18), ctx.seed + 20 + k + (sx + 1) * 5)
    _log(ctx, "beam", (-2.95, 0.0, 3.92), (2.95, 0.0, 3.95), 0.15, ctx.seed + 3, moss=0.35)
    tilt = 0.0
    if ctx.worn:
        tilt = ctx.drnd("tilt").uniform(4, 9)
    sw, sh = 4.0, 1.34
    board = K.box("board", (sw, 0.07, sh), bevel=0.012, cuts=(4, 0, 2))
    K.place(board, (0, 0, -sh / 2 - 0.42), (0, tilt, 0))
    K.place(board, (0, 0, 3.92))
    ctx.add(board, "civic_oak_dark", long_axis=0, patches=0.5, moss=0.3)
    for side, rz in ((-1, 0.0), (1, 180.0)):
        f = _face(ctx, f"face{side}", sw - 0.08, sh - 0.08, _rect("tamarack_arch"), (0, side * 0.0365, 0), rz)
        K.place(f, (0, 0, -sh / 2 - 0.42), (0, tilt, 0))
        K.place(f, (0, 0, 3.92))
    for sx in (-1, 1):
        x = sx * 1.6
        z0 = 3.92 - 0.42 + (math.sin(math.radians(tilt)) * x * -1.0)
        ch = W.chain_obj(f"chain{sx}", [(x, 0, 3.8), (x, 0, z0 + 0.02)], link=0.05, wire=0.006)
        ctx.add(ch, "trap_chain", uv="box", uv_scale=8.0, smooth=40, patches=0.4)
    # The little cross over the middle of the beam.
    W.bar(ctx, "cross_v", (0, 0, 4.02), (0, 0, 4.88), 0.07, 0.07, "out_log_peeled", up=(0, 1, 0), bevel=0.006)
    W.bar(ctx, "cross_h", (-0.26, 0, 4.58), (0.26, 0, 4.58), 0.07, 0.07, "out_log_peeled", up=(0, 1, 0), bevel=0.006)


def w3_canoe_rack(ctx: K.Ctx) -> None:
    """Two H-frames of peeled poles (posts outside the boats, rungs at 0.7 and 1.45 m, a brace) and three
    canoes keel-up on the rungs, two below and one above; destroyed: one frame down, a canoe fallen off
    and stove in."""
    r = ctx.rnd("rack")
    for k, x in enumerate((-1.55, 1.55)):
        down = ctx.destroyed and k == 1
        for sy in (-1, 1):
            if down:
                W.pole(ctx, f"post{k}{sy}", [(x, sy * 1.0, 0.0), (x + 1.6, sy * 0.9, 0.35)], 0.06, "out_log_peeled", r_end=0.055,
                       seed=ctx.seed + k * 3 + sy)
            else:
                W.pole(ctx, f"post{k}{sy}", [(x, sy * 1.0, -0.03), (x, sy * 1.0, 1.85)], 0.06, "out_log_peeled", r_end=0.055,
                       seed=ctx.seed + k * 3 + sy)
        if down:
            continue
        for z in (0.7, 1.45):
            W.pole(ctx, f"rung{k}{z}", [(x, -1.08, z), (x, 1.08, z)], 0.045, "out_log_peeled", r_end=0.042,
                   seed=ctx.seed + int(z * 10) + k)
            for sy in (-1, 1):
                O.lash(ctx, f"lash{k}{z}{sy}", (x, sy * 1.0, z), (0, 0, 1), 0.065, turns=2, width=0.06, mat="trap_cord",
                       seed=k + sy)
        W.pole(ctx, f"brace{k}", [(x, -1.0, 0.2), (x, 1.0, 1.4)], 0.035, "out_log_peeled", r_end=0.03, seed=ctx.seed + 70 + k)
    hulls = [((0.0, -0.47, 0.74), "out_boat_green"), ((0.0, 0.47, 0.74), "out_boat_red"), ((0.0, -0.47, 1.49), "out_boat_green")]
    for i, (at, paint) in enumerate(hulls):
        if ctx.destroyed and i == 1:
            _canoe(ctx, f"canoe{i}", 4.8, 0.84, 0.34, paint, at=(0.8, 1.55, 0.0), rot=(0, 0, 8), keel_up=False, stove=True)
            continue
        if ctx.destroyed and i == 2:
            continue
        _canoe(ctx, f"canoe{i}", 4.8, 0.84, 0.34, paint, at=at, rot=(0, 0, r.uniform(-1.5, 1.5)), keel_up=True)


def _canoe(ctx, name, L, B, D, paint, *, at, rot=(0, 0, 0), keel_up=True, stove=False):
    """A wood-and-canvas canoe along X: lofted hull (painted canvas outside, cedar inside), gunwales,
    thwarts and seats. keel_up turns it over (rack storage); at = its gunwale plane's centre."""
    n_r, n_s = 15, 9
    rings = []
    for i in range(n_r):
        t = i / (n_r - 1)
        x = -L / 2 + L * t
        bw = B / 2 * max(0.02, math.sin(math.pi * t) ** 0.62)
        sheer = 0.13 * (2 * t - 1) ** 4
        dd = D * max(0.1, math.sin(math.pi * t) ** 0.35)
        ring = []
        for j in range(n_s):
            a = math.pi * j / (n_s - 1)
            ring.append((x, -math.cos(a) * bw, sheer - math.sin(a) * dd * (0.85 + 0.15 * math.sin(a))))
        rings.append(ring)
    hull = K.loft(f"{name}hull", rings, closed_ring=False, cap_start=False, cap_end=False)
    K.solidify(hull, 0.012, offset=-1.0, even=False)
    if stove:
        K.dent(hull, (0.4, -0.2, -0.2), 0.45, 0.12)
    parts = [hull]
    rim = []
    for side in (-1, 1):
        pts = [Vector((rg[0 if side < 0 else -1][0], rg[0 if side < 0 else -1][1], rg[0][2] + 0.01)) for rg in rings]
        g = K.tube(f"{name}gun{side}", pts, 0.018, segs=5)
        rim.append(g)
    th = []
    for xx in (-L * 0.22, 0.0, L * 0.25):
        t = (xx + L / 2) / L
        bw = B / 2 * max(0.02, math.sin(math.pi * t) ** 0.62)
        th.append(K.box(f"{name}th{xx}", (0.07, bw * 2, 0.025), center=(xx, 0, -0.03)))
    flip = (180, 0, 0) if keel_up else (0, 0, 0)
    for o in parts:
        K.place(o, (0, 0, 0), flip)
        K.place(o, (0, 0, 0), rot)
        K.place(o, at)
        ctx.add(o, paint, uv="box", uv_scale=1.0, smooth=60, patches=0.5, edge=0.8, moss=0.2)
    for o in rim + th:
        K.place(o, (0, 0, 0), flip)
        K.place(o, (0, 0, 0), rot)
        K.place(o, at)
        ctx.add(o, "wild_cedar", uv="box", uv_scale=1.0, smooth=40, patches=0.5)


def w3_camp_bunk(ctx: K.Ctx) -> None:
    """A camp double bunk of painted 2x4s and plywood decks, thin striped mattresses, a sleeping bag on
    the lower bunk and a quilt on the upper, a ladder at the foot. Long axis along X."""
    r = ctx.rnd("bunk")
    L, Wd = 1.98, 0.92
    paint = "wood_painted_green" if r.random() < 0.5 else "wood_stained"
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.bar(ctx, f"post{sx}{sy}", (sx * (L / 2 - 0.045), sy * (Wd / 2 - 0.045), 0.0),
                  (sx * (L / 2 - 0.045), sy * (Wd / 2 - 0.045), 1.72), 0.085, 0.085, paint, bevel=0.006)
    decks = (0.32, 1.22)
    for k, z in enumerate(decks):
        for sy in (-1, 1):
            W.bar(ctx, f"rail{k}{sy}", (-L / 2, sy * (Wd / 2 - 0.045), z), (L / 2, sy * (Wd / 2 - 0.045), z), 0.04, 0.13,
                  paint, up=(0, 1, 0), bevel=0.005)
        for sx in (-1, 1):
            W.bar(ctx, f"end{k}{sx}", (sx * (L / 2 - 0.045), -Wd / 2, z), (sx * (L / 2 - 0.045), Wd / 2, z), 0.04, 0.13,
                  paint, up=(1, 0, 0), bevel=0.005)
        ply = K.box(f"ply{k}", (L - 0.12, Wd - 0.1, 0.018), center=(0, 0, z + 0.035))
        ctx.add(ply, "furn_particleboard", long_axis=0, patches=0.4)
        if ctx.destroyed and k == 1:
            continue
        m = K.box(f"mat{k}", (L - 0.16, Wd - 0.16, 0.1), center=(0, 0, z + 0.095), bevel=0.03, cuts=(4, 2, 0))
        K.noise_disp(m, 0.006, scale=4.0, seed=ctx.seed + k)
        ctx.add(m, "mattress_ticking", uv="box", uv_scale=1.0, smooth=50, patches=0.5)
    for sx in (-1, 1):
        W.bar(ctx, f"guard{sx}", (sx * 0.2, -Wd / 2 + 0.02, 1.52), (sx * 0.85, -Wd / 2 + 0.02, 1.52), 0.035, 0.09, paint,
              up=(0, 1, 0), bevel=0.004)
    # Ladder at the foot (+X end).
    for sy in (-0.3, 0.12):
        W.bar(ctx, f"ladder_side{sy}", (L / 2 + 0.03, sy, 0.0), (L / 2 + 0.03, sy, 1.55), 0.035, 0.07, paint, bevel=0.004)
    for k in range(4):
        z = 0.36 + k * 0.32
        W.rod(ctx, f"rung{k}", (L / 2 + 0.03, -0.3, z), (L / 2 + 0.03, 0.12, z), 0.016, paint, segs=6)
    # Bedding: a sleeping bag below, a quilt above (turned back).
    bag = W.drape_obj("bag", 1.55, Wd - 0.12, 0.0, (Wd - 0.2) / 2, nx=12, ny=8, hang=0.06, fold_at=0.45,
                      seed=ctx.seed + 3, rumple=0.02)
    K.place(bag, (-0.12, 0, decks[0] + 0.15))
    ctx.add(bag, "nylon_navy", uv=None, smooth=50, patches=0.4)
    if not ctx.destroyed:
        q = W.drape_obj("quilt", 1.4, Wd - 0.08, 0.0, (Wd - 0.18) / 2, nx=12, ny=8, hang=0.12, fold_at=0.4,
                        seed=ctx.seed + 4, rumple=0.015)
        K.place(q, (0.1, 0, decks[1] + 0.15))
        ctx.add(q, "bedding_quilt", uv=None, smooth=50, patches=0.4)
        pil = K.blob("pillow", 0.2, subdiv=2, scale=(0.9, 1.6, 0.4), center=(-L / 2 + 0.28, 0, decks[1] + 0.2))
        ctx.add(pil, "furn_linen", uv="box", uv_scale=2.0, smooth=60, patches=0.4)
    if ctx.worn:
        for k in range(3):
            c = K.chunk(f"junk{k}", r.uniform(0.06, 0.12), r, n=8)
            K.place(c, (r.uniform(-0.8, 0.8), r.uniform(-0.3, 0.3), decks[0] + 0.2))
            ctx.add(c, "paper_trash", uv="box", uv_scale=3.0, patches=0.4)


def _plaque(ctx: K.Ctx) -> None:
    """A routed cedar plaque screwed to a wall (origin on the wall plane, bottom centre, front -Y)."""
    cell = str(ctx.param("cell", "sign_loon"))
    w, h, t = 0.92, 0.25, 0.035
    tilt = ctx.drnd("tilt").uniform(-3.5, 3.5) if ctx.worn else 0.0
    b = K.box("plank", (w, t, h), bevel=0.008, cuts=(3, 0, 1))
    K.place(b, (0, -t / 2, h / 2), (0, tilt, 0))
    ctx.add(b, "civic_oak_dark", long_axis=0, patches=0.5, moss=0.25)
    f = _face(ctx, "face", w - 0.04, h - 0.03, _rect(cell), (0, -t - 0.0015, h / 2), 0.0, rot=(0, tilt, 0))
    _ = f
    for sx in (-1, 1):
        sc = K.cyl("screw", 0.008, 0.006, segs=6, center=(sx * (w / 2 - 0.05), -t - 0.003, h / 2), axis="Y")
        ctx.add(sc, "metal_galvanized", uv="box", uv_scale=10.0)


def w3_evac_board(ctx: K.Ctx) -> None:
    """The Cordon's family registration board: a plywood board on two 4x4 legs under a little shed roof,
    the blue FAMILY EVACUATION POINT 6 header, three typed lists taped up, a cork panel of snapshots and
    notes, a clipboard on a nail and a pen on a string."""
    r = ctx.rnd("board")
    for sx in (-1, 1):
        W.bar(ctx, f"leg{sx}", (sx * 1.18, 0.0, -0.02), (sx * 1.18, 0.0, 2.3), 0.09, 0.09, "wood_weathered", bevel=0.005)
    _board(ctx, "ply", 2.5, 1.32, 0.018, (0, -0.055, 1.42), "road_plywood", patches=0.5)
    _face(ctx, "header", 2.36, 0.28, _rect("evac_header"), (0, -0.0652, 1.93))
    _face(ctx, "lists", 1.5, 0.9, _rect("evac_lists"), (-0.42, -0.0652, 1.3))
    _face(ctx, "photos", 0.74, 0.62, _rect("evac_photos"), (0.8, -0.0655, 1.22))
    roof = K.box("roof", (2.7, 0.62, 0.02), cuts=(3, 1, 0))
    K.place(roof, (0, -0.08, 2.36), (-14, 0, 0))
    ctx.add(roof, "farm_corrugated_galv", uv="box", uv_scale=1.0, patches=0.5, moss=0.3)
    cb = K.box("clipboard", (0.23, 0.012, 0.32), bevel=0.003)
    K.place(cb, (0.72, -0.08, 0.86), (0, r.uniform(-6, 6), 0))
    ctx.add(cb, "furn_particleboard", uv="box", uv_scale=2.0, patches=0.4)
    sheet = K.quad_sheet("sheet", (-0.1, 0, -0.14), (0.1, 0, -0.14), (0.1, 0, 0.12), (-0.1, 0, 0.12), 1, 1)
    K.uv_planar(sheet, 1, rect=_rect("evac_lists", (0.0, 0.1, 0.33, 0.95)))
    K.place(sheet, (0.72, -0.0875, 0.85))
    ctx.add(sheet, SIGNS, uv=None, patches=0.3)
    W.rod(ctx, "pen_string", (0.95, -0.07, 1.12), (0.97, -0.08, 0.7), 0.002, "trap_cord", segs=4)
    W.rod(ctx, "pen", (0.96, -0.08, 0.7), (0.975, -0.085, 0.57), 0.006, "plastic_blue", segs=6)
    if ctx.worn:
        for k in range(4):
            p = K.quad_sheet(f"loose{k}", (-0.1, 0, -0.14), (0.1, 0, -0.14), (0.1, 0, 0.14), (-0.1, 0, 0.14), 2, 2)
            K.uv_planar(p, 1, rect=_rect("evac_photos", (0.0, 0.0, 0.33, 0.33)))
            K.crumple(p, 0.01, seed=ctx.seed + k)
            K.place(p, (0, 0, 0), (r.uniform(80, 95), 0, r.uniform(0, 360)))
            K.place(p, (r.uniform(-1.2, 1.2), r.uniform(-0.9, -0.3), 0.01))
            ctx.add(p, SIGNS, uv=None, patches=0.6)


def w3_log_bench(ctx: K.Ctx) -> None:
    """A split-log bench on two stumps (chapel and fire ring): flat side up, bark below."""
    r = ctx.rnd("bench")
    L, R = 2.0, 0.21
    pts = [(R * math.cos(math.pi + math.pi * i / 8), R * math.sin(math.pi + math.pi * i / 8) * 0.8) for i in range(9)]
    half = K.prism("seat", [(p[0], p[1]) for p in pts], L, plane="YZ")
    K.place(half, (0, 0, 0.45))
    ctx.add(half, HEWN, uv="box", uv_scale=1.0, long_axis=0, smooth=40, patches=0.5, moss=0.3)
    for sx in (-1, 1):
        st = K.cyl(f"stump{sx}", 0.17, 0.3, segs=10, center=(sx * 0.68, 0, 0.15))
        K.noise_disp(st, 0.012, scale=5.0, seed=ctx.seed + sx)
        ctx.add(st, LOG, uv="cyl", uv_axis=2, smooth=50, patches=0.4, moss=0.5)
    if ctx.worn:
        m = K.blob("moss", 0.18, subdiv=1, scale=(1.6, 0.8, 0.15), center=(r.uniform(-0.6, 0.6), 0.0, 0.452), rough=0.3)
        ctx.add(m, "out_sod", uv="box", uv_scale=2.0, smooth=50, moss=0.9)


def w3_chapel_cross(ctx: K.Ctx) -> None:
    """A rough cross of peeled logs lashed together on a cairn of river stones, by the water."""
    r = ctx.rnd("cross")
    _log(ctx, "upright", (0, 0, 0.0), (0.02, 0.01, 3.1), 0.09, ctx.seed + 1, bark="out_log_peeled", moss=0.15)
    _log(ctx, "arm", (-0.75, -0.08, 2.25), (0.75, -0.08, 2.27), 0.075, ctx.seed + 2, bark="out_log_peeled", moss=0.15)
    O.lash(ctx, "lash", (0, -0.04, 2.26), (0, 1, 0), 0.1, turns=4, width=0.12, mat="trap_cord", seed=3)
    for k in range(14):
        a = k / 14 * math.tau + r.uniform(-0.2, 0.2)
        rad = 0.32 + (k % 3) * 0.12
        O.add_stone(ctx, f"cairn{k}", (math.cos(a) * rad, math.sin(a) * rad, 0.05 + (2 - k % 3) * 0.06),
                    r.uniform(0.13, 0.22), ctx.seed + 30 + k)
    if ctx.worn:
        # A string of the families' tokens tied to the arm: ribbons and a child's mitten.
        for k, x in enumerate((-0.55, -0.3, 0.42, 0.6)):
            W.rod(ctx, f"ribbon{k}", (x, -0.1, 2.2), (x + 0.02, -0.12, 1.85 + 0.05 * k), 0.008,
                  ["plastic_red", "plastic_yellow", "plastic_blue", "plastic_white"][k], segs=4)


# ============================================================================================
# Elk Ridge Lodge
# ============================================================================================

# Kit opening clear sizes (lib/kit_dims.py, kit_tall.py): kind -> (width, sill, top, cells spanned).
OPEN = {"door": (0.86, 0.0, 2.10, 1), "door2": (1.70, 0.0, 2.10, 2), "window": (0.70, 0.90, 2.00, 1),
        "window2": (1.60, 0.85, 2.05, 2), "window_tall": (0.76, 0.80, 3.30, 1), "breach": (0.86, 0.0, 1.75, 1)}
TRIM = 0.075


def _holes(side, openings, floor):
    """Holes (t0, t1, z0, z1) along one side for openings given as (side, index, kind, level)."""
    out = []
    for (s, idx, kind, lvl) in openings:
        if s != side:
            continue
        w, sill, top, span = OPEN[kind]
        c = idx + span / 2
        base = floor + lvl * 3.0
        z0 = base + sill - TRIM if (sill > 0 or lvl > 0) else -1.0
        out.append((c - w / 2 - TRIM, c + w / 2 + TRIM, z0, base + top + TRIM))
    return out


def _log_courses(ctx, room, side, holes, *, z_top, r=0.165, pitch=0.25, seed=0, notch_ext=0.3, odd=0):
    """Horizontal bark-on logs stacked on a side's edge line (they enclose the kit wall inside and out),
    saddle-notched at the corners (every other course runs past them), cut round the openings, lime
    chinking in the seams on both faces, hewn jambs and a sill log under each window."""
    rr = random.Random(seed)
    start, along, out = room.side_line(side, 0.0)
    L = room.length(side)
    k = 0
    z = r * 0.85
    while z < z_top:
        ext = notch_ext if (k + odd) % 2 == 0 else -0.02
        for s0, s1 in O.clip_spans(-ext, L + ext, z - r * 0.6, z + r * 0.6, holes):
            a = start + along * s0 + Vector((0, 0, z))
            b = start + along * s1 + Vector((0, 0, z))
            _log(ctx, f"{side}log{k}_{s0:.1f}", a, b, r * rr.uniform(0.94, 1.05), seed * 131 + k * 7, moss=0.3,
                 rings=max(3, min(6, int((s1 - s0) / 1.4) + 2)))
            if z + pitch < z_top:
                for sgn in (1, -1):
                    pa = a + out * sgn * (r * 0.62) + Vector((0, 0, pitch / 2))
                    pb = b + out * sgn * (r * 0.62) + Vector((0, 0, pitch / 2))
                    ch = K.tube(f"{side}chink{k}{sgn}{s0:.1f}", [pa, pb], 0.04, segs=5, caps=False,
                                flat=(1.0, 0.75))
                    ctx.add(ch, CHINK, uv="box", uv_scale=2.5, smooth=45, patches=0.5, moss=0.25)
        k += 1
        z += pitch
    for (a0, b0, z0, z1) in holes:
        for t in (a0 - 0.06, b0 + 0.06):
            p = start + along * t
            W.bar(ctx, f"{side}jamb{t:.2f}{z0:.1f}", (p.x, p.y, max(0.0, z0)), (p.x, p.y, min(z_top - 0.1, z1 + 0.06)),
                  0.11, 0.38, HEWN, up=tuple(out), bevel=0.01)
        if z0 > 0.2:
            pa, pb = start + along * (a0 - 0.12), start + along * (b0 + 0.12)
            W.bar(ctx, f"{side}sill{a0:.2f}{z0:.1f}", (pa.x, pa.y, z0 - 0.04), (pb.x, pb.y, z0 - 0.04), 0.4, 0.09, HEWN,
                  up=(0, 0, 1), bevel=0.01)


def w3_lodge_shell(ctx: K.Ctx) -> None:
    """Chinked log walls round a lodge's kit rooms (one rectangle w x d cells, `storeys` high): bark-on
    logs saddle-notched at the corners with lime chinking, cut for the plan's doors and windows (params
    openings: [side, index, kind, level]); the kit roof sits on top. No collision: the kit walls hold."""
    fh = float(ctx.param("floor", 0.45))
    room = O.Room(int(ctx.param("w", 16)), int(ctx.param("d", 10)), fh)
    storeys = int(ctx.param("storeys", 2))
    ops = [tuple(o) for o in ctx.param("openings", [])]
    z_top = fh + storeys * 3.0 - 0.05
    for k, side in enumerate(("N", "S", "E", "W")):
        _log_courses(ctx, room, side, _holes(side, ops, fh), z_top=z_top, seed=ctx.seed + k * 11,
                     odd=0 if side in ("N", "S") else 1)
    # A sill log on stones along the bottom of every side (the logs stand on a fieldstone footing).
    rr = ctx.rnd("footing")
    for side in ("N", "S", "E", "W"):
        start, along, out = room.side_line(side, 0.0)
        L = room.length(side)
        t = -0.2
        while t < L + 0.2:
            p = start + along * t + out * rr.uniform(0.02, 0.1)
            O.add_stone(ctx, f"foot{side}{t:.1f}", (p.x, p.y, 0.03), rr.uniform(0.16, 0.24), ctx.seed + int(t * 13),
                        flat=0.5)
            t += rr.uniform(0.38, 0.55)


def w3_stone_fireplace(ctx: K.Ctx) -> None:
    """A fieldstone fireplace for a wall (built from its back plane, then centred in depth so a prop placed
    `against` the wall meets it): raised hearth, a deep firebox with andirons and split logs on an ash bed,
    a log mantel, and the stone breast rising to 5.6 m, narrowing above the mantel."""
    r = ctx.rnd("fp")
    y0 = -0.09
    D, Wd = 0.78, 2.4
    # Core masses (mortar-coloured, mostly hidden by the stones).
    core = K.box("core", (Wd, D, 1.5), center=(0, y0 - D / 2, 0.75))
    ctx.add(core, MORTAR, uv="box", uv_scale=2.0, patches=0.5)
    breast = K.box("breast", (1.7, 0.56, 4.1), center=(0, y0 - 0.28, 1.5 + 2.05))
    ctx.add(breast, MORTAR, uv="box", uv_scale=2.0, patches=0.5)
    hearth = K.box("hearth", (Wd + 0.3, 0.55, 0.22), center=(0, y0 - D - 0.275, 0.11), bevel=0.02, cuts=(4, 2, 0))
    K.noise_disp(hearth, 0.008, scale=4.0, seed=ctx.seed)
    ctx.add(hearth, "civic_granite", uv="box", uv_scale=1.0, patches=0.4)
    # Firebox: a dark recess cut into the front of the core.
    fb_w, fb_h, fb_d = 1.1, 0.95, 0.55
    fb = K.box("firebox", (fb_w, fb_d, fb_h), center=(0, y0 - D + fb_d / 2 - 0.001, 0.22 + fb_h / 2))
    K.delete_faces(fb, lambda c, n: n.y < -0.9)
    for poly in fb.data.polygons:
        poly.flip()
    ctx.add(fb, "wood_charred", uv="box", uv_scale=2.0, patches=0.2, base=0.6)

    def skip_front(s, t):
        return abs(s - Wd / 2) < fb_w / 2 + 0.02 and t < 0.22 + fb_h + 0.03 and t > 0.0
    _stones_on_face(ctx, "front", (-Wd / 2, y0 - D, 0.22), (1, 0, 0), (0, 0, 1), Wd, 1.28, ctx.seed + 1, size=0.32,
                    depth=0.07, skip=skip_front)
    for sx in (-1, 1):
        _stones_on_face(ctx, f"side{sx}", (sx * Wd / 2, y0 - (D if sx < 0 else 0.0), 0.0),
                        (0, 1, 0) if sx < 0 else (0, -1, 0), (0, 0, 1), D, 1.5, ctx.seed + 5 + sx, size=0.3, depth=0.06)
        _stones_on_face(ctx, f"bside{sx}", (sx * 0.85, y0 - (0.56 if sx < 0 else 0.0), 1.5),
                        (0, 1, 0) if sx < 0 else (0, -1, 0), (0, 0, 1), 0.56, 4.1, ctx.seed + 9 + sx, size=0.3, depth=0.05)
    _stones_on_face(ctx, "breast_face", (-0.85, y0 - 0.56, 1.5), (1, 0, 0), (0, 0, 1), 1.7, 4.1, ctx.seed + 3, size=0.34,
                    depth=0.07)
    # The arch stone over the firebox and a log mantel.
    lintel = K.box("lintel", (fb_w + 0.3, 0.2, 0.2), center=(0, y0 - D - 0.03, 0.22 + fb_h + 0.1), bevel=0.02, cuts=(3, 1, 1))
    K.noise_disp(lintel, 0.012, scale=4.0, seed=ctx.seed + 4)
    ctx.add(lintel, STONE, uv="box", uv_scale=1.4, patches=0.4)
    _log(ctx, "mantel", (-1.35, y0 - D - 0.08, 1.48), (1.35, y0 - D - 0.08, 1.49), 0.12, ctx.seed + 6, bark=HEWN,
         moss=0.0)
    # Andirons, logs and the ash bed.
    for sx in (-1, 1):
        W.bar(ctx, f"andiron{sx}", (sx * 0.3, y0 - D + 0.1, 0.3), (sx * 0.3, y0 - D + 0.48, 0.3), 0.03, 0.03, "wild_cast_iron")
        W.rod(ctx, f"andiron_post{sx}", (sx * 0.3, y0 - D + 0.08, 0.22), (sx * 0.3, y0 - D + 0.08, 0.5), 0.022,
              "wild_cast_iron", segs=6)
    ash = K.blob("ash", 0.4, subdiv=2, scale=(1.2, 0.7, 0.12), center=(0, y0 - D + 0.28, 0.23), rough=0.25, seed=ctx.seed)
    ctx.add(ash, "ash_burnt", uv="box", uv_scale=2.0, smooth=50, patches=0.3)
    for k in range(3):
        lg = W.log_obj(f"fire_log{k}", 0.62, 0.065, ctx.seed + 40 + k, sides=8, rings=3, bark="wood_charred",
                       end="ember_glow" if not ctx.worn else "wood_charred")
        K.place(lg, (r.uniform(-0.06, 0.06), y0 - D + 0.25 + k * 0.06, 0.34 + k * 0.05), (0, r.uniform(-8, 8), r.uniform(-12, 12)))
        ctx.add(lg, None, uv=None, smooth=45, patches=0.4)
    if ctx.worn:
        for k in range(4):
            c = K.chunk(f"fallen{k}", r.uniform(0.08, 0.14), r, n=9, flat=0.6)
            K.place(c, (r.uniform(-1.3, 1.3), y0 - D - r.uniform(0.25, 0.5), 0.04))
            ctx.add(c, STONE, uv="box", uv_scale=2.0, patches=0.4)
    _centre_depth(ctx)


def w3_stone_chimney(ctx: K.Ctx) -> None:
    """The lodge's outside chimney stack against a wall (front -Y, away from the wall; centred in depth
    so the prop's collision box, centred on the origin, is the stack's own): a broad fieldstone base,
    stepped shoulders, the stack up past the ridge (params height), a cap slab and the flue."""
    H = float(ctx.param("height", 11.2))
    y0 = -0.17
    segs = [(0.0, 2.4, 2.2, 1.15), (2.4, 3.1, 1.75, 0.95), (3.1, H - 0.25, 1.45, 0.82)]
    for k, (z0, z1, w, d) in enumerate(segs):
        core = K.box(f"core{k}", (w, d, z1 - z0), center=(0, y0 - d / 2, (z0 + z1) / 2))
        ctx.add(core, MORTAR, uv="box", uv_scale=2.0, patches=0.5)
        size = 0.42 if k < 2 else 0.36
        _stones_on_face(ctx, f"front{k}", (-w / 2, y0 - d, z0), (1, 0, 0), (0, 0, 1), w, z1 - z0, ctx.seed + k * 7,
                        size=size, depth=0.06)
        for sx in (-1, 1):
            _stones_on_face(ctx, f"side{k}{sx}", (sx * w / 2, y0 - (d if sx < 0 else 0.0), z0),
                            (0, 1, 0) if sx < 0 else (0, -1, 0), (0, 0, 1), d, z1 - z0, ctx.seed + k * 7 + sx * 3,
                            size=size, depth=0.05)
    cap = K.box("cap", (1.65, 1.0, 0.12), center=(0, y0 - 0.41, H - 0.19), bevel=0.02, cuts=(2, 2, 0))
    K.noise_disp(cap, 0.01, scale=4.0, seed=ctx.seed)
    ctx.add(cap, "civic_granite", uv="box", uv_scale=1.2, patches=0.4, moss=0.4)
    flue = K.box("flue", (0.5, 0.42, 0.14), center=(0, y0 - 0.41, H - 0.06))
    K.delete_faces(flue, lambda c, n: n.z > 0.9)
    ctx.add(flue, "wood_charred", uv="box", uv_scale=2.0, base=0.6)
    for k, z in enumerate((2.4, 3.1)):
        w = segs[k][2]
        sh = K.box(f"shoulder{k}", (w + 0.06, segs[k][3] + 0.06, 0.08), center=(0, y0 - segs[k][3] / 2, z), bevel=0.015)
        ctx.add(sh, "civic_granite", uv="box", uv_scale=1.2, patches=0.4, moss=0.5)
    # Its back then lies ~0.62 m behind the origin: the lodge stands it with that face on the log wall.
    _centre_depth(ctx)


def w3_antler_chandelier(ctx: K.Ctx) -> None:
    """An antler chandelier hanging from a ceiling (origin on the ceiling plane): a chain down to a
    wrought-iron hoop, shed antlers wired round it pointing out and up, eight candle cups with candles."""
    ctx.ground_clamp = False
    r = ctx.rnd("chand")
    drop = float(ctx.param("drop", 1.25))
    ch = W.chain_obj("chain", [(0, 0, 0.0), (0, 0, -drop + 0.12)], link=0.06, wire=0.008)
    ctx.add(ch, "wild_cast_iron", uv="box", uv_scale=6.0, smooth=40, patches=0.3)
    plate = K.cyl("rose", 0.1, 0.03, segs=12, center=(0, 0, -0.015))
    ctx.add(plate, "wild_cast_iron", uv="box", uv_scale=4.0, smooth=40)
    hoop = W.ring_obj("hoop", 0.5, 0.53, 0.03, segs=28)
    K.place(hoop, (0, 0, -drop))
    ctx.add(hoop, "wild_cast_iron", uv="box", uv_scale=4.0, smooth=40)
    for k in range(4):
        a = k / 4 * math.tau + math.pi / 4
        W.rod(ctx, f"stay{k}", (0, 0, -drop + 0.12), (math.cos(a) * 0.5, math.sin(a) * 0.5, -drop), 0.008,
              "wild_cast_iron", segs=5)
    n = 8
    for k in range(n):
        a = k / n * math.tau
        side = 1 if k % 2 else -1
        ant = O.antler_obj(f"antler{k}", r.uniform(0.42, 0.52), ctx.seed + k * 5, side=side, tines=3, spread=0.8)
        K.place(ant, (0, 0, 0), (r.uniform(-15, 5), 0, math.degrees(a) - 90 - side * 30))
        K.place(ant, (math.cos(a) * 0.48, math.sin(a) * 0.48, -drop - 0.06))
        ctx.add(ant, "out_antler", uv="box", uv_scale=3.0, smooth=50, patches=0.5)
    for k in range(n):
        a = (k + 0.5) / n * math.tau
        c = Vector((math.cos(a) * 0.515, math.sin(a) * 0.515, -drop + 0.02))
        cup = K.cyl(f"cup{k}", 0.035, 0.03, segs=8, center=c)
        ctx.add(cup, "wild_cast_iron", uv="box", uv_scale=6.0, smooth=40)
        hgt = r.uniform(0.07, 0.16) if ctx.worn else r.uniform(0.15, 0.2)
        cd = K.cyl(f"candle{k}", 0.019, hgt, segs=8, center=c + Vector((0, 0, 0.015 + hgt / 2)))
        ctx.add(cd, "candle_wax", uv="cyl", uv_axis=2, smooth=50, patches=0.3)
        fl = K.blob(f"flame{k}", 0.012, subdiv=1, scale=(1, 1, 2.2), center=c + Vector((0, 0, 0.015 + hgt + 0.025)))
        ctx.add(fl, "flame_glow", uv="box", uv_scale=10.0, smooth=60, ao=False, patches=0.0)


def _head_mount(ctx, *, s: float, tines: int, elk: bool) -> None:
    """A head mount for a wall (built off its back plane, then centred in depth: place it `against` the wall
    with a `y`): an oak shield, the neck rising off it, the head looking out and a little down, ears, glass
    eyes, a dark nose, the antlers."""
    r = ctx.rnd("mount")
    shield = [(-0.24 * s, 0.0), (0.24 * s, 0.0), (0.3 * s, 0.42 * s), (0.18 * s, 0.7 * s), (0.0, 0.78 * s),
              (-0.18 * s, 0.7 * s), (-0.3 * s, 0.42 * s)]
    sh = K.prism("shield", shield, 0.045, plane="XZ", offset=-0.0225, bevel=0.008)
    ctx.add(sh, "civic_oak_dark", uv="box", uv_scale=2.0, patches=0.4)
    fur = "wild_fur_dark"
    head_c = Vector((0, -0.52 * s, 0.6 * s))
    # The neck: a tapering tube from the shield out to the back of the head.
    neck = K.tube("neck", [(0, -0.02, 0.36 * s), (0, -0.22 * s, 0.46 * s), (0, -0.4 * s, 0.56 * s)],
                  [0.2 * s, 0.17 * s, 0.13 * s], segs=12)
    ctx.add(neck, fur, uv="box", uv_scale=2.0, smooth=60, patches=0.3)
    head = K.blob("head", 0.15 * s, subdiv=2, scale=(0.9, 1.35, 0.95), center=(0, 0, 0))
    K.place(head, (0, 0, 0), (-14, 0, 0))
    K.place(head, head_c)
    ctx.add(head, fur, uv="box", uv_scale=2.0, smooth=60, patches=0.3)
    muzzle = K.blob("muzzle", 0.085 * s, subdiv=2, scale=(0.85, 1.4, 0.8), center=(0, 0, 0))
    K.place(muzzle, head_c + Vector((0, -0.22 * s, -0.07 * s)))
    ctx.add(muzzle, fur, uv="box", uv_scale=2.0, smooth=60, patches=0.3)
    nose = K.blob("nose", 0.045 * s, subdiv=1, scale=(1.1, 0.6, 0.7), center=head_c + Vector((0, -0.33 * s, -0.06 * s)))
    ctx.add(nose, "plastic_black", uv="box", uv_scale=4.0, smooth=60)
    for sx in (-1, 1):
        if not (ctx.worn and sx > 0):
            eye = K.blob(f"eye{sx}", 0.02 * s, subdiv=1, center=head_c + Vector((sx * 0.115 * s, -0.11 * s, 0.05 * s)))
            ctx.add(eye, "eye_animal", uv="box", uv_scale=4.0, smooth=60)
        ear = K.blob(f"ear{sx}", 0.06 * s, subdiv=1, scale=(0.5, 0.25, 1.4), center=(0, 0, 0))
        K.place(ear, (0, 0, 0), (0, sx * 55, 0))
        K.place(ear, head_c + Vector((sx * 0.15 * s, 0.05 * s, 0.12 * s)))
        ctx.add(ear, fur, uv="box", uv_scale=3.0, smooth=55)
        ant = O.antler_obj(f"antler{sx}", (1.0 if elk else 0.62) * s * 0.92, ctx.seed + sx * 9, side=sx,
                           tines=(tines - 1) if (ctx.worn and sx < 0) else tines, spread=1.15 if elk else 0.9)
        # Tilted forward so the beams rise and spread in front of the wall, tines pointing out.
        K.place(ant, (0, 0, 0), (14, 0, 0))
        K.place(ant, head_c + Vector((sx * 0.07 * s, 0.0, 0.12 * s)))
        for v in ant.data.vertices:
            if v.co.y > -0.06:
                v.co.y = -0.06 - (v.co.y + 0.06) * 0.15
        ant.data.update()
        ctx.add(ant, "out_antler", uv="box", uv_scale=3.0, smooth=50, patches=0.5)
    _centre_depth(ctx)
    _ = r


def w3_trophy_elk(ctx: K.Ctx) -> None:
    """A bull elk's head on an oak shield, six points a side (worn: a glass eye gone, a tine broken)."""
    _head_mount(ctx, s=1.0, tines=5, elk=True)


def w3_trophy_deer(ctx: K.Ctx) -> None:
    """A whitetail buck's head on an oak shield, four points a side."""
    _head_mount(ctx, s=0.72, tines=3, elk=False)


def w3_bear_rug(ctx: K.Ctx) -> None:
    """A black-bear skin rug on the floor: the hide spread flat with its legs out, the head mounted at
    one end, mouth open, felt-backed edge."""
    hide = O.hide_obj("hide", 1.5, 2.0, ctx.seed, nx=12, ny=14, ragged=0.08)
    K.place(hide, (0, 0, 0), (-90, 0, 0))
    K.place(hide, (0, 0.1, 0.012))
    K.solidify(hide, 0.02, offset=-1.0, even=False)
    ctx.add(hide, "wild_fur_dark", uv="box", uv_scale=1.5, smooth=50, patches=0.4)
    head = K.blob("head", 0.17, subdiv=2, scale=(1.0, 1.25, 0.7), center=(0, -0.95, 0.12))
    ctx.add(head, "wild_fur_dark", uv="box", uv_scale=2.0, smooth=60, patches=0.3)
    snout = K.blob("snout", 0.08, subdiv=2, scale=(0.9, 1.4, 0.8), center=(0, -1.13, 0.1))
    ctx.add(snout, "wild_fur_dark", uv="box", uv_scale=2.0, smooth=60)
    nose = K.blob("nose", 0.03, subdiv=1, center=(0, -1.24, 0.12))
    ctx.add(nose, "plastic_black", uv="box", uv_scale=4.0, smooth=60)
    for sx in (-1, 1):
        ear = K.blob(f"ear{sx}", 0.045, subdiv=1, scale=(1, 0.5, 1), center=(sx * 0.12, -0.86, 0.24))
        ctx.add(ear, "wild_fur_dark", uv="box", uv_scale=3.0, smooth=55)
        eye = K.blob(f"eye{sx}", 0.014, subdiv=1, center=(sx * 0.07, -1.06, 0.18))
        ctx.add(eye, "eye_animal", uv="box", uv_scale=4.0, smooth=60)
    if ctx.worn:
        stain = K.blob("stain", 0.3, subdiv=2, scale=(1.4, 1.0, 0.03), center=(0.2, 0.3, 0.035))
        ctx.add(stain, "blood_dried", uv="box", uv_scale=2.0, smooth=50)


def w3_gun_cabinet(ctx: K.Ctx) -> None:
    """A glass-fronted oak gun cabinet: rifles stood in a notched rack behind two glazed doors, drawers
    under them; destroyed: glass smashed out and the rack empty."""
    r = ctx.rnd("guns")
    Wd, D, H = 1.18, 0.42, 1.9
    body = K.box("body", (Wd, D, H), center=(0, 0, H / 2), bevel=0.01)
    K.delete_faces(body, lambda c, n: n.y < -0.9 and c.z > 0.62)
    ctx.add(body, "civic_oak_dark", long_axis=2, patches=0.5)
    kick = K.box("kick", (Wd - 0.02, 0.02, 0.62), center=(0, -D / 2 + 0.012, 0.31))
    ctx.add(kick, "civic_oak_dark", long_axis=0, patches=0.5)
    back = K.box("back", (Wd - 0.06, 0.01, H - 0.7), center=(0, D / 2 - 0.03, 0.62 + (H - 0.7) / 2))
    ctx.add(back, "civic_felt_green", uv="box", uv_scale=2.0, patches=0.3)
    crown = K.box("crown", (Wd + 0.08, D + 0.06, 0.08), center=(0, -0.01, H + 0.04), bevel=0.012)
    ctx.add(crown, "civic_oak_dark", long_axis=0, patches=0.5)
    for k in range(2):
        z = 0.12 + k * 0.24
        dr = K.box(f"drawer{k}", (Wd - 0.08, 0.02, 0.2), center=(0, -D / 2 - 0.006, z + 0.1), bevel=0.005)
        ctx.add(dr, "civic_oak", long_axis=0, patches=0.5)
        ctx.add(K.cyl(f"pull{k}", 0.012, 0.02, segs=6, center=(0, -D / 2 - 0.02, z + 0.1), axis="Y"), "civic_brass",
                uv="box", uv_scale=8.0)
    # Notched rack and the rifles.
    W.bar(ctx, "rack", (-Wd / 2 + 0.05, -0.02, 1.48), (Wd / 2 - 0.05, -0.02, 1.48), 0.06, 0.03, "civic_oak_dark")
    n = 0 if ctx.destroyed else (3 if ctx.worn else 5)
    for k in range(n):
        x = -0.42 + k * 0.21
        stock = K.box(f"stock{k}", (0.045, 0.12, 0.42), center=(x, 0.02, 0.84), bevel=0.012)
        K.taper(stock, 2, lambda z: 0.8 + 0.4 * (1.0 - (z - 0.63) / 0.42))
        ctx.add(stock, "trap_gun_stock", uv="box", uv_scale=3.0, smooth=40, patches=0.4)
        W.rod(ctx, f"barrel{k}", (x, 0.04, 1.05), (x + r.uniform(-0.01, 0.01), 0.07, 1.78), 0.011, "item_steel_blued", segs=6)
        rx = K.box(f"action{k}", (0.03, 0.05, 0.16), center=(x, 0.05, 1.12))
        ctx.add(rx, "item_steel_blued", uv="box", uv_scale=4.0)
    for sx in (-1, 1):
        fr = K.box(f"door{sx}", (Wd / 2 - 0.02, 0.025, H - 0.66), center=(sx * Wd / 4, -D / 2 + 0.01, 0.62 + (H - 0.66) / 2))
        K.delete_faces(fr, lambda c, nn: abs(nn.y) > 0.9)
        ctx.add(fr, "civic_oak_dark", long_axis=2, patches=0.5)
        rail = []
        x0, x1 = sx * 0.02, sx * (Wd / 2 - 0.02)
        for z in (0.64, H - 0.06):
            rail.append(K.box(f"rail{sx}{z}", (Wd / 2 - 0.04, 0.03, 0.06), center=((x0 + x1) / 2, -D / 2 + 0.005, z)))
        for x in (x0, x1):
            rail.append(K.box(f"stile{sx}{x}", (0.06, 0.03, H - 0.66), center=(x, -D / 2 + 0.005, 0.62 + (H - 0.66) / 2)))
        ctx.add(K.merge_parts(rail, f"frame{sx}"), "civic_oak_dark", long_axis=2, patches=0.5)
        if not ctx.destroyed:
            g = K.box(f"glass{sx}", (Wd / 2 - 0.1, 0.006, H - 0.8), center=((x0 + x1) / 2, -D / 2 + 0.005, 0.62 + (H - 0.66) / 2))
            ctx.add(g, "glass_clear", uv="box", uv_scale=2.0, patches=0.3)
    if ctx.destroyed:
        for k in range(6):
            sh = K.chunk(f"shard{k}", r.uniform(0.03, 0.07), r, n=6, flat=0.1)
            K.place(sh, (r.uniform(-0.6, 0.6), -D / 2 - r.uniform(0.05, 0.6), 0.005))
            ctx.add(sh, "glass_clear", uv="box", uv_scale=4.0)


def w3_gambrel(ctx: K.Ctx) -> None:
    """The skinning shed's hanging frame: two pole A-frames and a cross pole, a chain to a steel gambrel,
    and an elk carcass hung by its hind legs, the hide peeled down to the shoulders; worn: gone dark and
    furred with pale threads."""
    r = ctx.rnd("gam")
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.pole(ctx, f"leg{sx}{sy}", [(sx * 1.2, sy * 0.55, -0.02), (sx * 1.15, 0.0, 2.95)], 0.07, "out_log_peeled",
                   r_end=0.06, seed=ctx.seed + sx * 2 + sy)
    W.pole(ctx, "cross", [(-1.35, 0, 2.9), (1.35, 0, 2.9)], 0.075, "out_log_peeled", r_end=0.07, seed=ctx.seed + 9)
    ch = W.chain_obj("chain", [(0, 0, 2.82), (0, 0, 2.35)], link=0.05, wire=0.006)
    ctx.add(ch, "trap_chain", uv="box", uv_scale=8.0, smooth=40)
    W.bar(ctx, "gambrel", (-0.32, 0, 2.3), (0.32, 0, 2.3), 0.025, 0.04, "road_steel", bevel=0.004)
    meat = "gore" if not ctx.worn else "t3_meat_spoiled"
    body = K.lathe("carcass", [(0.0, 0.0), (0.12, 0.05), (0.2, 0.3), (0.27, 0.65), (0.29, 0.95), (0.24, 1.2), (0.15, 1.35),
                               (0.0, 1.4)], segs=12)
    K.place(body, (0, 0, 0), (180, 0, 0), scale=(1.0, 0.75, 1.0))
    K.place(body, (0, 0, 2.08))
    K.noise_disp(body, 0.02, scale=3.0, seed=ctx.seed)
    ctx.add(body, meat, uv="box", uv_scale=1.5, smooth=55, patches=0.4)
    for sx in (-1, 1):
        ctx.add(K.tube(f"hind{sx}", [(sx * 0.1, 0, 1.95), (sx * 0.2, 0, 2.15), (sx * 0.3, 0, 2.3)], [0.08, 0.06, 0.035],
                       segs=7), meat, uv="box", uv_scale=1.5, smooth=55)
        ctx.add(K.tube(f"fore{sx}", [(sx * 0.14, -0.05, 0.85), (sx * 0.2, -0.1, 0.55), (sx * 0.22, -0.12, 0.25)],
                       [0.06, 0.045, 0.03], segs=7), meat, uv="box", uv_scale=1.5, smooth=55)
    hide = K.lathe("hide", [(0.31, 0.0), (0.33, 0.12), (0.36, 0.3), (0.42, 0.42)], segs=12, cap_bottom=False, cap_top=False)
    K.place(hide, (0, 0, 0), (180, 0, 0))
    K.place(hide, (0, 0, 1.12))
    K.noise_disp(hide, 0.025, scale=4.0, seed=ctx.seed + 3)
    K.solidify(hide, 0.012, offset=-1.0, even=False)
    ctx.add(hide, "out_hide", uv="box", uv_scale=2.0, smooth=50, patches=0.5)
    tub = K.lathe("tub", [(0.0, 0.0), (0.32, 0.0), (0.36, 0.28), (0.34, 0.28), (0.3, 0.02), (0.0, 0.02)], segs=14)
    K.place(tub, (0.0, 0.05, 0.0))
    ctx.add(tub, "metal_galvanized", uv="cyl", uv_axis=2, smooth=40, patches=0.5)
    if ctx.worn:
        for k in range(10):
            a = r.uniform(0, math.tau)
            z = r.uniform(1.0, 2.0)
            p0 = Vector((math.cos(a) * 0.24, math.sin(a) * 0.18, z))
            ctx.add(K.tube(f"thread{k}", [p0, p0 + Vector((math.cos(a) * 0.05, math.sin(a) * 0.05, -r.uniform(0.15, 0.4)))],
                           0.006, segs=4), "out_bone_ash", uv="box", uv_scale=6.0, smooth=40)


def w3_kennel_run(ctx: K.Ctx) -> None:
    """A dog run: galvanized pipe frame with chain-link panels 2 x 4 m, a plywood doghouse with a shingled
    roof at the back, a steel bowl and a chain; worn: a panel bent out at the bottom where they dug and
    pushed through, the gate hanging open; destroyed: a side flattened."""
    r = ctx.rnd("kennel")
    Wd, D, H = 2.0, 4.0, 1.8
    posts = [(-Wd / 2, -D / 2), (Wd / 2, -D / 2), (-Wd / 2, D / 2), (Wd / 2, D / 2), (-Wd / 2, 0.0), (Wd / 2, 0.0)]
    for k, (x, y) in enumerate(posts):
        W.rod(ctx, f"post{k}", (x, y, 0.0), (x, y, H), 0.024, "metal_galvanized", segs=8)
    for (a, b) in (((-Wd / 2, -D / 2), (Wd / 2, -D / 2)), ((-Wd / 2, D / 2), (Wd / 2, D / 2)),
                   ((-Wd / 2, -D / 2), (-Wd / 2, D / 2)), ((Wd / 2, -D / 2), (Wd / 2, D / 2))):
        W.rod(ctx, f"top{a}{b}", (a[0], a[1], H), (b[0], b[1], H), 0.018, "metal_galvanized", segs=6)
    panels = [("N", (-Wd / 2, D / 2), (Wd / 2, D / 2)), ("W", (-Wd / 2, -D / 2), (-Wd / 2, D / 2)),
              ("E", (Wd / 2, D / 2), (Wd / 2, -D / 2))]
    for name, a, b in panels:
        if ctx.destroyed and name == "E":
            m = K.quad_sheet("flat", (Wd / 2, -D / 2, 0.02), (Wd / 2 + 1.6, -D / 2 + 0.3, 0.05), (Wd / 2 + 1.7, D / 2, 0.05),
                             (Wd / 2, D / 2, 0.02), 4, 4)
            ctx.add(m, "chainlink", uv="planar", uv_axis=2, uv_scale=1.0, patches=0.3)
            continue
        m = K.quad_sheet(f"mesh{name}", (a[0], a[1], 0.03), (b[0], b[1], 0.03), (b[0], b[1], H - 0.03), (a[0], a[1], H - 0.03),
                         6, 4)
        if ctx.worn and name == "W":
            def push(v):
                if v.co.z < 0.6 and abs(v.co.y) < 1.2:
                    v.co.x -= (0.6 - v.co.z) * 0.6 * (1.0 - abs(v.co.y) / 1.2)
            for v in m.data.vertices:
                push(v)
        ctx.add(m, "chainlink", uv=None, patches=0.3)
    # The gate on the front (-Y): a framed mesh leaf.
    swing = 0.0 if not ctx.worn else 70.0
    leaf = []
    gw = Wd - 0.08
    leaf.append(W.rod_obj("gframe0", (0, 0, 0.06), (gw, 0, 0.06), 0.016))
    leaf.append(W.rod_obj("gframe1", (0, 0, H - 0.1), (gw, 0, H - 0.1), 0.016))
    leaf.append(W.rod_obj("gframe2", (gw, 0, 0.06), (gw, 0, H - 0.1), 0.016))
    gf = K.merge_parts(leaf, "gate_frame")
    gm = K.quad_sheet("gate_mesh", (0, 0, 0.07), (gw, 0, 0.07), (gw, 0, H - 0.11), (0, 0, H - 0.11), 4, 4)
    for o, mat in ((gf, "metal_galvanized"), (gm, "chainlink")):
        K.place(o, (0, 0, 0), (0, 0, -swing))
        K.place(o, (-Wd / 2 + 0.04, -D / 2, 0))
        ctx.add(o, mat, uv=None if mat == "chainlink" else "box", uv_scale=2.0, patches=0.4)
    # Doghouse at the back.
    dh = K.box("doghouse", (0.9, 0.8, 0.62), center=(0, D / 2 - 0.5, 0.33), bevel=0.01)
    K.delete_faces(dh, lambda c, n: n.y < -0.9)
    ctx.add(dh, "road_plywood", uv="box", uv_scale=1.0, patches=0.5)
    front = K.box("dh_front", (0.9, 0.02, 0.62), center=(0, D / 2 - 0.9, 0.33))
    K.delete_faces(front, lambda c, n: False)
    ctx.add(front, "road_plywood", uv="box", uv_scale=1.0, patches=0.5)
    for sx in (-1, 1):
        rf = K.box(f"dh_roof{sx}", (0.52, 0.92, 0.02), center=(0, 0, 0))
        K.place(rf, (0, 0, 0), (0, sx * 32, 0))
        K.place(rf, (sx * 0.22, D / 2 - 0.5, 0.78))
        ctx.add(rf, "roof_shingle", uv="box", uv_scale=1.0, patches=0.5, moss=0.4)
    bowl = K.lathe("bowl", [(0.0, 0.0), (0.1, 0.0), (0.13, 0.06), (0.12, 0.06), (0.09, 0.012), (0.0, 0.012)], segs=12)
    K.place(bowl, (0.5, -0.6, 0.0))
    ctx.add(bowl, "road_stainless", uv="cyl", uv_axis=2, smooth=40, patches=0.4)
    ctn = W.chain_obj("tie", [(0.0, D / 2 - 0.92, 0.3), (0.2, 0.6, 0.02), (r.uniform(-0.3, 0.3), -0.2, 0.02)], link=0.05,
                      wire=0.006)
    ctx.add(ctn, "trap_chain", uv="box", uv_scale=8.0, smooth=40)
    if ctx.worn:
        dig = K.blob("dig", 0.45, subdiv=2, scale=(1.0, 1.6, 0.18), center=(-Wd / 2 - 0.15, 0.0, 0.0), rough=0.3)
        ctx.add(dig, "out_earth", uv="box", uv_scale=1.0, smooth=50, patches=0.3)


def w3_meat_rail(ctx: K.Ctx) -> None:
    """The cellar's meat rail: two steel posts and a rail with S-hooks, elk quarters hung on three of them
    over a drip pan; worn: gone black and furred with the Bloom's pale threads."""
    r = ctx.rnd("rail")
    for sx in (-1, 1):
        W.rod(ctx, f"post{sx}", (sx * 1.2, 0, 0.0), (sx * 1.2, 0, 2.3), 0.03, "road_steel", segs=8)
        ctx.add(K.box(f"foot{sx}", (0.2, 0.2, 0.02), center=(sx * 1.2, 0, 0.01)), "road_steel", uv="box", uv_scale=4.0)
    W.rod(ctx, "rail", (-1.3, 0, 2.3), (1.3, 0, 2.3), 0.025, "road_steel", segs=8)
    meat = "gore" if not ctx.worn else "t3_meat_spoiled"
    for k, x in enumerate((-0.75, 0.0, 0.7)):
        hook = K.tube(f"hook{k}", [(x, 0, 2.3), (x, 0.03, 2.2), (x, 0.0, 2.1), (x, -0.03, 2.16)], 0.006, segs=4)
        ctx.add(hook, "road_steel", uv="box", uv_scale=8.0, smooth=40)
        if k == 2 and ctx.worn:
            continue
        q = K.lathe(f"quarter{k}", [(0.0, 0.0), (0.07, 0.04), (0.15, 0.25), (0.18, 0.5), (0.14, 0.75), (0.05, 0.9), (0.0, 0.93)],
                    segs=10)
        K.place(q, (0, 0, 0), (180, 0, r.uniform(0, 90)), scale=(1.0, 0.7, 1.0))
        K.place(q, (x, 0, 2.08))
        K.noise_disp(q, 0.02, scale=3.0, seed=ctx.seed + k)
        ctx.add(q, meat, uv="box", uv_scale=1.5, smooth=55, patches=0.5)
        if ctx.worn:
            for j in range(6):
                a = r.uniform(0, math.tau)
                z = r.uniform(1.3, 1.95)
                p0 = Vector((x + math.cos(a) * 0.14, math.sin(a) * 0.1, z))
                ctx.add(K.tube(f"thread{k}{j}", [p0, p0 + Vector((0, 0, -r.uniform(0.2, 0.5)))], 0.005, segs=4), "out_bone_ash",
                        uv="box", uv_scale=6.0, smooth=40)
    pan = K.box("pan", (2.2, 0.5, 0.06), center=(0, 0, 0.03))
    K.delete_faces(pan, lambda c, n: n.z > 0.9)
    ctx.add(pan, "road_stainless", uv="box", uv_scale=2.0, patches=0.5)
    ctx.add(K.box("pan_floor", (2.18, 0.48, 0.005), center=(0, 0, 0.012)), "blood_dried", uv="box", uv_scale=2.0)


# ============================================================================================
# The Cordon quarantine camp
# ============================================================================================

def w3_ward_tent(ctx: K.Ctx) -> None:
    """An open-sided ward tent (5 x 9.6 m): three centre poles under a 3.4 m ridge, eave poles at 1.8 m,
    olive canvas roof and closed gable ends, the side walls rolled up on their ties for air, guy lines to
    stakes. No collision: the cots under it are what you walk round. Destroyed: half of it fallen in."""
    r = ctx.rnd("tent")
    Wd, L, ridge, eave = 5.0, 9.6, 3.75, 2.25
    hw, hl = Wd / 2, L / 2
    for k, y in enumerate((-hl + 0.1, 0.0, hl - 0.1)):
        W.rod(ctx, f"centre{k}", (0, y, 0.0), (0, y, ridge - 0.02), 0.04, "wood_weathered", segs=8)
    n_e = 5
    for k in range(n_e):
        y = -hl + L * k / (n_e - 1)
        for sx in (-1, 1):
            if ctx.destroyed and sx > 0 and y > 0:
                W.rod(ctx, f"eave{k}{sx}", (sx * hw, y, 0.02), (sx * (hw + 1.6), y + 0.4, 0.06), 0.03, "wood_weathered", segs=6)
                continue
            W.rod(ctx, f"eave{k}{sx}", (sx * hw, y, 0.0), (sx * hw, y, eave), 0.03, "wood_weathered", segs=6)
            # Guy line to its stake.
            st = Vector((sx * (hw + 1.4), y, 0.0))
            W.rod(ctx, f"guy{k}{sx}", (sx * (hw + 0.05), y, eave + 0.02), st + Vector((0, 0, 0.2)), 0.005, "trap_cord", segs=4)
            W.rod(ctx, f"stake{k}{sx}", st, st + Vector((0, 0, 0.28)), 0.018, "road_steel", segs=5)
    # Roof slopes: a sheet per side sagging a little between the eave poles.
    for sx in (-1, 1):
        if ctx.destroyed and sx > 0:
            sheet = K.quad_sheet("roof_fallen", (0, -hl - 0.15, ridge), (0, hl * 0.1, ridge - 0.4), (sx * (hw + 1.2), hl * 0.1, 0.1),
                                 (sx * (hw + 0.25), -hl - 0.15, eave), 12, 8)
            K.crumple(sheet, 0.12, scale=1.5, seed=ctx.seed)
        else:
            sheet = K.quad_sheet(f"roof{sx}", (0, -hl - 0.15, ridge), (0, hl + 0.15, ridge), (sx * (hw + 0.25), hl + 0.15, eave - 0.08),
                                 (sx * (hw + 0.25), -hl - 0.15, eave - 0.08), 16, 4)

            def sag(v):
                f = abs(v.co.x) / (hw + 0.25)
                v.co.z -= 0.06 * math.sin(math.pi * f) * (0.6 + 0.4 * abs(math.sin(v.co.y / (L / (n_e - 1)) * math.pi)))
            for v in sheet.data.vertices:
                sag(v)
        K.solidify(sheet, 0.006, offset=0.0, even=False)
        ctx.add(sheet, OD, uv="box", uv_scale=1.0, smooth=35, patches=0.5)
        # The rolled side wall along the eave, tied up.
        if not (ctx.destroyed and sx > 0):
            roll = K.cyl(f"roll{sx}", 0.09, L, segs=8, center=(sx * (hw + 0.02), 0, eave - 0.12), axis="Y")
            K.noise_disp(roll, 0.015, scale=3.0, seed=ctx.seed + sx)
            ctx.add(roll, OD, uv="cyl", uv_axis=1, smooth=50, patches=0.5)
    # Gable ends: closed canvas triangles above the eave; below it the end walls are rolled and tied back
    # to the corner poles (the wards stand open for air), a narrow fold of canvas at each corner.
    for sy in (-1, 1):
        y = sy * (hl + 0.02)
        tri = K.prism(f"gable{sy}", [(-hw, eave), (hw, eave), (0, ridge)], 0.01, plane="XZ", offset=y)
        ctx.add(tri, OD, uv="box", uv_scale=1.0, patches=0.5)
        valance = K.quad_sheet(f"valance{sy}", (-hw, y, eave - 0.35), (hw, y, eave - 0.35), (hw, y, eave), (-hw, y, eave), 8, 1)
        K.crumple(valance, 0.015, seed=ctx.seed + sy)
        ctx.add(valance, OD, uv="box", uv_scale=1.0, patches=0.5)
        for sx in (-1, 1):
            fold = K.cyl(f"fold{sy}{sx}", 0.11, eave - 0.1, segs=7, center=(sx * (hw - 0.12), y, (eave - 0.1) / 2))
            K.noise_disp(fold, 0.025, scale=3.0, seed=ctx.seed + sy * 3 + sx)
            ctx.add(fold, OD, uv="cyl", uv_axis=2, smooth=50, patches=0.5)
            W.rod(ctx, f"tie{sy}{sx}", (sx * (hw - 0.12), y - 0.12 * sy, 1.2), (sx * (hw - 0.12), y - 0.12 * sy, 1.26), 0.12,
                  "trap_cord", segs=6)
    _ = r


def w3_ward_cot(ctx: K.Ctx) -> None:
    """A Cordon field cot (aluminium frame, X legs, olive canvas bed) with two restraint straps across it,
    a grey blanket and a wristband tag on the foot bar. Long axis along Y."""
    r = ctx.rnd("cot")
    L, Wd, z = 1.9, 0.68, 0.42
    for sx in (-1, 1):
        W.rod(ctx, f"side{sx}", (sx * Wd / 2, -L / 2, z), (sx * Wd / 2, L / 2, z), 0.016, "road_alu", segs=6)
    for k, y in enumerate((-L / 2 + 0.12, 0.0, L / 2 - 0.12)):
        for sx in (-1, 1):
            W.rod(ctx, f"leg{k}{sx}", (sx * Wd / 2, y - 0.14, z), (-sx * Wd / 2 * 0.9, y + 0.14, 0.0), 0.012, "road_alu", segs=5)
    for y in (-L / 2, L / 2):
        W.rod(ctx, f"end{y}", (-Wd / 2, y, z), (Wd / 2, y, z), 0.014, "road_alu", segs=6)
    bed = K.grid("bed", Wd - 0.02, L - 0.04, 6, 12, center=(0, 0, z - 0.01))
    for v in bed.data.vertices:
        v.co.z -= 0.05 * (1.0 - (2 * v.co.x / Wd) ** 2)
    K.solidify(bed, 0.005, offset=0.0, even=False)
    ctx.add(bed, OD, uv="box", uv_scale=2.0, smooth=40, patches=0.5)
    if not ctx.destroyed:
        bl = W.drape_obj("blanket", 1.05, Wd + 0.06, 0.0, Wd / 2 - 0.02, nx=10, ny=8, hang=0.14, fold_at=0.35, seed=ctx.seed,
                         rumple=0.02)
        K.place(bl, (0, 0, 0), (0, 0, 90))
        K.place(bl, (0, 0.35, z - 0.02))
        ctx.add(bl, "civic_wool_grey", uv=None, smooth=50, patches=0.5)
    for k, y in enumerate((-0.35, 0.45)):
        strap = K.box(f"strap{k}", (Wd + 0.1, 0.05, 0.004), center=(0, y, z + 0.005))
        for v in strap.data.vertices:
            v.co.z += 0.0
        ctx.add(strap, "item_webbing_black", uv="box", uv_scale=4.0, patches=0.3)
        for sx in (-1, 1):
            tail = K.box(f"tail{k}{sx}", (0.004, 0.05, 0.22), center=(sx * (Wd / 2 + 0.05), y, z - 0.1))
            ctx.add(tail, "item_webbing_black", uv="box", uv_scale=4.0, patches=0.3)
        bk = K.box(f"buckle{k}", (0.05, 0.06, 0.012), center=(Wd / 2 - 0.08, y, z + 0.012))
        ctx.add(bk, "road_steel", uv="box", uv_scale=6.0)
        if ctx.worn and k == 0:
            ctx.add(K.box(f"torn{k}", (0.004, 0.05, 0.3), center=(-Wd / 2 - 0.06, y, z - 0.15)), "item_webbing_black", uv="box")
    tag = K.box("tag", (0.06, 0.004, 0.09), center=(0.12, L / 2 + 0.01, z - 0.06))
    ctx.add(tag, "paper_trash", uv="box", uv_scale=4.0)
    _ = r


def w3_decon_shower(ctx: K.Ctx) -> None:
    """A decontamination shower: a PVC pipe frame 2.2 x 2.4 m, four spray heads on the top rails, white
    curtains on two sides, a pallet floor over a catch basin, the feed hose and the yellow step sign."""
    r = ctx.rnd("decon")
    Wd, D, H = 2.2, 2.4, 2.35
    hw, hd = Wd / 2, D / 2
    pipe = "plastic_white"
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.rod(ctx, f"leg{sx}{sy}", (sx * hw, sy * hd, 0.0), (sx * hw, sy * hd, H), 0.03, pipe, segs=8)
        W.rod(ctx, f"top_y{sx}", (sx * hw, -hd, H), (sx * hw, hd, H), 0.03, pipe, segs=8)
    for sy in (-1, 1):
        W.rod(ctx, f"top_x{sy}", (-hw, sy * hd, H), (hw, sy * hd, H), 0.03, pipe, segs=8)
    for k, (x, y) in enumerate(((-0.45, -0.5), (0.45, -0.5), (-0.45, 0.5), (0.45, 0.5))):
        W.rod(ctx, f"feed{k}", (x, -hd, H), (x, hd, H), 0.018, pipe, segs=6) if k < 2 else None
        hd_ = K.cyl(f"head{k}", 0.045, 0.06, segs=10, center=(x, y, H - 0.06), r_top=0.02)
        ctx.add(hd_, "road_steel", uv="cyl", uv_axis=2, smooth=40, patches=0.4)
    for sx in (-1, 1):
        cur = K.quad_sheet(f"curtain{sx}", (sx * (hw + 0.04), -hd, 0.35), (sx * (hw + 0.04), hd, 0.35), (sx * (hw + 0.04), hd, H - 0.05),
                           (sx * (hw + 0.04), -hd, H - 0.05), 10, 6)
        for v in cur.data.vertices:
            v.co.x += sx * 0.04 * math.sin(v.co.y * 9.0 + sx) * (0.5 + 0.5 * (H - v.co.z) / H)
        if ctx.worn and sx > 0:
            K.delete_faces(cur, lambda c, n: c.z < 1.2 and c.y > 0.1)
        K.solidify(cur, 0.004, offset=0.0, even=False)
        ctx.add(cur, "w3_canvas_white", uv="box", uv_scale=1.0, smooth=40, patches=0.6)
    basin = K.box("basin", (Wd - 0.1, D - 0.1, 0.12), center=(0, 0, 0.06))
    K.delete_faces(basin, lambda c, n: n.z > 0.9)
    ctx.add(basin, "tarp_blue", uv="box", uv_scale=1.0, patches=0.5)
    for k in range(7):
        y = -hd + 0.2 + k * (D - 0.4) / 6
        pl = P.plank(f"slat{k}", Wd - 0.25, 0.12, 0.025)
        K.place(pl, (0, y, 0.15))
        ctx.add(pl, "wood_weathered", long_axis=0, patches=0.6)
    hose = K.tube("hose", [(-hw, -hd, H), (-hw - 0.15, -hd - 0.1, 1.2), (-hw - 0.3, -hd - 0.6, 0.04), (-hw - 1.2, -hd - 1.0, 0.04)],
                  0.025, segs=6)
    ctx.add(hose, "tyre_rubber", uv="box", uv_scale=3.0, smooth=40)
    sign = K.box("sign_board", (0.9, 0.02, 0.32), center=(0, -hd - 0.03, H - 0.32))
    ctx.add(sign, "road_plywood", uv="box", uv_scale=2.0, patches=0.4)
    _face(ctx, "sign", 0.86, 0.29, _rect("decon_steps", (0.335, 0.0, 0.665, 1.0)), (0, -hd - 0.041, H - 0.32))
    if ctx.worn:
        for k in range(3):
            c = P.garment(f"cloth{k}", "shirt", r)
            K.place(c, (r.uniform(-0.6, 0.6), r.uniform(-0.8, 0.8), 0.17))
            ctx.add(c, "flannel_red" if k % 2 else "canvas_denim", uv="box", uv_scale=2.0, smooth=40, patches=0.5)


def w3_light_tower(ctx: K.Ctx) -> None:
    """A towable light tower: a yellow generator box on a two-wheel trailer with a tongue, outrigger jacks,
    a three-stage mast to 7 m with four floodlights on a cross bar and the cable down it."""
    r = ctx.rnd("lt")
    body = "road_paint_yellow"
    box = K.box("genset", (1.2, 2.2, 1.0), center=(0, 0.1, 0.62), bevel=0.04, cuts=(2, 3, 1))
    ctx.add(box, body, uv="box", uv_scale=1.0, patches=0.6)
    for k in range(6):
        vent = K.box(f"vent{k}", (0.02, 0.5, 0.03), center=(0.61, -0.4 + k * 0.1 * 0 + 0.0, 0.5 + k * 0.06))
        ctx.add(vent, "road_steel_dark", uv="box", uv_scale=4.0)
    frame = K.box("frame", (1.0, 2.6, 0.12), center=(0, 0.1, 0.12))
    ctx.add(frame, "road_steel_dark", uv="box", uv_scale=2.0, patches=0.6)
    for sx in (-1, 1):
        ty = P.tyre(f"tyre{sx}", 0.3, 0.17, 0.18, segs=14)
        K.place(ty, (sx * 0.68, 0.3, 0.3))
        ctx.add(ty, "tyre_rubber", uv="box", uv_scale=2.0, smooth=40)
        rim = K.cyl(f"rim{sx}", 0.17, 0.16, segs=12, center=(sx * 0.68, 0.3, 0.3), axis="X")
        ctx.add(rim, "road_steel", uv="box", uv_scale=3.0)
        for sy in (-1, 1):
            W.bar(ctx, f"out{sx}{sy}", (sx * 0.5, sy * 1.1 + 0.1, 0.25), (sx * 1.05, sy * 1.25 + 0.1, 0.25), 0.06, 0.06, body)
            W.rod(ctx, f"jack{sx}{sy}", (sx * 1.05, sy * 1.25 + 0.1, 0.0), (sx * 1.05, sy * 1.25 + 0.1, 0.5), 0.03, "road_steel", segs=6)
            ctx.add(K.box(f"pad{sx}{sy}", (0.18, 0.18, 0.03), center=(sx * 1.05, sy * 1.25 + 0.1, 0.015)), "road_steel", uv="box")
    W.bar(ctx, "tongue", (0, -1.15, 0.3), (0, -1.75, 0.3), 0.08, 0.08, "road_steel_dark")
    for k, (r0, z0, z1) in enumerate(((0.07, 0.9, 3.2), (0.055, 3.1, 5.2), (0.042, 5.1, 7.0))):
        W.rod(ctx, f"mast{k}", (0, 0.75, z0), (0, 0.75, z1), r0, "metal_galvanized", segs=10)
    W.bar(ctx, "crossbar", (-0.85, 0.75, 6.95), (0.85, 0.75, 6.95), 0.06, 0.06, "road_steel_dark")
    for k, x in enumerate((-0.7, -0.24, 0.24, 0.7)):
        z = 6.95 + (0.22 if k in (1, 2) else -0.05)
        hd = K.box(f"flood{k}", (0.36, 0.16, 0.28), center=(x, 0.62, z), bevel=0.02)
        K.place(hd, (0, 0, 0))
        ctx.add(hd, "road_steel_dark", uv="box", uv_scale=3.0, patches=0.5)
        lens = K.box(f"lens{k}", (0.3, 0.01, 0.22), center=(x, 0.535, z))
        ctx.add(lens, "road_lamp_glow", uv="box", uv_scale=3.0, ao=False)
    cable = K.tube("cable", [(0.08, 0.8, 6.9), (0.12, 0.85, 4.0), (0.1, 0.85, 1.4), (0.3, 0.9, 1.1)], 0.012, segs=5)
    ctx.add(cable, "tyre_rubber", uv="box", uv_scale=4.0, smooth=40)
    _ = r


def _fence_section(ctx, L, *, gate=False):
    r = ctx.rnd("fence")
    H = 2.15
    for sx in (-1, 1):
        x = sx * L / 2
        W.rod(ctx, f"post{sx}", (x, 0, -0.02), (x, 0, H + 0.1), 0.035 if not gate else 0.05, "metal_galvanized", segs=8)
        W.rod(ctx, f"arm{sx}", (x, 0, H + 0.05), (x, 0.42, H + 0.47), 0.018, "metal_galvanized", segs=6)
        ctx.add(K.cyl(f"foot{sx}", 0.12, 0.1, segs=8, center=(x, 0, 0.05)), "road_concrete", uv="box", uv_scale=2.0)
    W.rod(ctx, "top_rail", (-L / 2, 0, H), (L / 2, 0, H), 0.02, "metal_galvanized", segs=6)
    for k in range(3):
        z = H + 0.12 + k * 0.12
        y = 0.12 + k * 0.12
        W.rod(ctx, f"barb{k}", (-L / 2, y, z), (L / 2, y, z + r.uniform(-0.01, 0.01)), 0.003, "metal_galvanized", segs=3)
    # Concertina razor wire along the outriggers: a flattened helix.
    pts = []
    n = int(L / 0.09)
    for i in range(n + 1):
        t = i / n
        a = t * L / 0.32 * math.tau
        pts.append((-L / 2 + L * t, 0.3 + math.cos(a) * 0.22, H + 0.42 + math.sin(a) * 0.22))
    ctx.add(K.tube("razor", pts, 0.006, segs=3), "metal_galvanized", uv="box", uv_scale=6.0, smooth=40, patches=0.6)
    mesh = K.quad_sheet("mesh", (-L / 2, 0, 0.04), (L / 2, 0, 0.04), (L / 2, 0, H - 0.02), (-L / 2, 0, H - 0.02), 8, 4)
    if ctx.destroyed:
        K.delete_faces(mesh, lambda c, nn: abs(c.x) < 0.6 and c.z < 1.5)
        flap = K.quad_sheet("peel", (-0.6, 0, 0.04), (-0.1, -0.5, 0.06), (-0.1, -0.6, 1.4), (-0.6, 0, 1.5), 3, 4)
        ctx.add(flap, "chainlink", uv=None, patches=0.3)
    elif ctx.worn:
        for v in mesh.data.vertices:
            v.co.y -= 0.12 * math.sin(math.pi * (v.co.x + L / 2) / L) * (1.0 - v.co.z / H)
    ctx.add(mesh, "chainlink", uv=None, patches=0.3)
    if not gate and r.random() < 0.6:
        scr = K.quad_sheet("screen", (-L / 2 + 0.05, 0.02, 0.1), (L / 2 - 0.05, 0.02, 0.1), (L / 2 - 0.05, 0.02, 1.7),
                           (-L / 2 + 0.05, 0.02, 1.7), 6, 3)
        if ctx.worn:
            K.delete_faces(scr, lambda c, nn: c.x > L * 0.15 and c.z > 0.7)
        K.crumple(scr, 0.01, seed=ctx.seed)
        ctx.add(scr, "w3_canvas_white", uv="box", uv_scale=1.0, patches=0.6)


def w3_cordon_fence(ctx: K.Ctx) -> None:
    """Three metres of the Cordon's camp fence: galvanized posts on concrete feet, chain-link with a white
    privacy screen on most bays, outriggers with barbed wire and a concertina coil (outward is +Y);
    worn: the mesh sagging, the screen torn; destroyed: cut and peeled back."""
    _fence_section(ctx, 3.0)


def w3_cordon_gate(ctx: K.Ctx) -> None:
    """The camp's double gate (4.4 m) on heavy posts, chained shut in the middle, the QUARANTINE notice
    on one leaf and the STOP / CHECKPOINT sign on its post."""
    L = 4.4
    for sx in (-1, 1):
        W.rod(ctx, f"post{sx}", (sx * (L / 2 + 0.06), 0, -0.02), (sx * (L / 2 + 0.06), 0, 2.55), 0.06, "metal_galvanized", segs=10)
        ctx.add(K.cyl(f"foot{sx}", 0.16, 0.12, segs=8, center=(sx * (L / 2 + 0.06), 0, 0.06)), "road_concrete", uv="box")
        x0, x1 = sx * 0.03, sx * (L / 2 - 0.02)
        frame = [W.rod_obj(f"f{sx}a", (x0, 0, 0.1), (x1, 0, 0.1), 0.022), W.rod_obj(f"f{sx}b", (x0, 0, 2.05), (x1, 0, 2.05), 0.022),
                 W.rod_obj(f"f{sx}c", (x0, 0, 0.1), (x0, 0, 2.05), 0.022), W.rod_obj(f"f{sx}d", (x1, 0, 0.1), (x1, 0, 2.05), 0.022),
                 W.rod_obj(f"f{sx}e", (x0, 0, 0.1), (x1, 0, 2.05), 0.016)]
        ctx.add(K.merge_parts(frame, f"leaf{sx}"), "metal_galvanized", uv="box", uv_scale=2.0, patches=0.5)
        m = K.quad_sheet(f"mesh{sx}", (x0, 0.01, 0.12), (x1, 0.01, 0.12), (x1, 0.01, 2.03), (x0, 0.01, 2.03), 4, 4)
        ctx.add(m, "chainlink", uv=None, patches=0.3)
    ch = W.chain_obj("chain", [(-0.18, -0.03, 1.15), (0.0, -0.06, 1.0), (0.18, -0.03, 1.15)], link=0.05, wire=0.007)
    ctx.add(ch, "trap_chain", uv="box", uv_scale=8.0, smooth=40)
    ctx.add(K.box("lock", (0.06, 0.03, 0.07), center=(0.0, -0.08, 0.96), bevel=0.006), "lock_steel", uv="box")
    ctx.add(K.box("notice_board", (1.0, 0.012, 0.26), center=(-1.1, -0.03, 1.45)), "road_plywood", uv="box")
    _face(ctx, "notice", 0.98, 0.245, _rect("quarantine"), (-1.1, -0.0375, 1.45))
    ctx.add(K.box("stop_board", (0.62, 0.014, 0.31), center=(L / 2 + 0.06, -0.08, 2.2)), "road_steel", uv="box")
    _face(ctx, "stop", 0.6, 0.29, _rect("checkpoint"), (L / 2 + 0.06, -0.088, 2.2))


def _sandbag(name, r, L=0.56, Wd=0.3, H=0.15):
    b = K.box(name, (L, Wd, H), bevel=0.045, bevel_segs=1, cuts=(2, 1, 0))
    K.noise_disp(b, 0.012, scale=6.0, seed=r.randint(0, 9999))
    K.taper(b, 0, lambda x: 1.0 - 0.25 * (2 * x / L) ** 4)
    return b


def w3_sandbags(ctx: K.Ctx) -> None:
    """Two metres of sandbag wall, three courses laid header and stretcher; worn: bags slumped and split,
    sand spilling."""
    r = ctx.rnd("bags")
    L = 2.0
    for c in range(3):
        z = 0.08 + c * 0.145
        x = -L / 2 + (0.28 if c % 2 == 0 else 0.0)
        while x < L / 2 - 0.1:
            for sy in ((-0.16, 0.16) if c == 0 else (0.0,)):
                if ctx.worn and ctx.drnd(f"{c}{x:.1f}{sy}").random() < 0.12:
                    continue
                b = _sandbag(f"bag{c}{x:.2f}{sy}", r)
                K.place(b, (0, 0, 0), (r.uniform(-3, 3), r.uniform(-4, 4), r.uniform(-4, 4)))
                K.place(b, (x + r.uniform(-0.02, 0.02), sy, z))
                ctx.add(b, "canvas_khaki", uv="box", uv_scale=2.0, smooth=50, patches=0.5)
            x += 0.58
    if ctx.worn:
        sp = K.blob("spill", 0.35, subdiv=2, scale=(1.4, 1.0, 0.15), center=(r.uniform(-0.6, 0.6), -0.35, 0.0), rough=0.3)
        ctx.add(sp, "terrain_sand" if False else "out_earth", uv="box", uv_scale=1.0, smooth=50)


def w3_watchtower(ctx: K.Ctx) -> None:
    """A scaffold watchtower: four galvanized legs braced in X, a plank deck at 4.2 m behind a sandbag
    parapet, a tarp roof on poles, a ladder up the front and a searchlight on the rail."""
    r = ctx.rnd("tower")
    s, deck = 1.1, 4.2
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.rod(ctx, f"leg{sx}{sy}", (sx * s, sy * s, 0.0), (sx * s * 0.92, sy * s * 0.92, deck + 1.9), 0.04, "metal_galvanized", segs=8)
            ctx.add(K.box(f"base{sx}{sy}", (0.25, 0.25, 0.04), center=(sx * s, sy * s, 0.02)), "road_steel", uv="box")
    for k, (z0, z1) in enumerate(((0.3, 2.2), (2.2, 4.1))):
        for side in range(4):
            a = [(-s, -s), (s, -s), (s, s), (-s, s)][side]
            b = [(-s, -s), (s, -s), (s, s), (-s, s)][(side + 1) % 4]
            W.rod(ctx, f"x{k}{side}a", (a[0], a[1], z0), (b[0], b[1], z1), 0.018, "metal_galvanized", segs=5)
            W.rod(ctx, f"x{k}{side}b", (b[0], b[1], z0), (a[0], a[1], z1), 0.018, "metal_galvanized", segs=5)
    O.plank_deck(ctx, -s - 0.1, s + 0.1, -s - 0.1, s + 0.1, deck, board=0.2, along="x", mat="wood_weathered", seed=ctx.seed,
                 missing=(4,))
    for side, (cx, cy, rz) in enumerate(((0, s + 0.05, 0), (s + 0.05, 0, 90), (-s - 0.05, 0, 90))):
        for c in range(4):
            for k in range(4):
                b = _sandbag(f"pb{side}{c}{k}", r, L=0.55, Wd=0.26, H=0.14)
                off = -0.83 + k * 0.55 + (0.27 if c % 2 else 0.0)
                if off > 0.85:
                    continue
                K.place(b, (0, 0, 0), (r.uniform(-3, 3), r.uniform(-3, 3), rz + r.uniform(-4, 4)))
                px, py = (cx + off, cy) if rz == 0 else (cx, cy + off)
                K.place(b, (px, py, deck + 0.08 + c * 0.14))
                ctx.add(b, "canvas_khaki", uv="box", uv_scale=2.0, smooth=50, patches=0.5)
    roof = K.quad_sheet("roof", (-s - 0.3, -s - 0.3, deck + 2.0), (s + 0.3, -s - 0.3, deck + 2.0), (s + 0.3, s + 0.3, deck + 2.25),
                        (-s - 0.3, s + 0.3, deck + 2.25), 6, 6)
    K.crumple(roof, 0.03, seed=ctx.seed)
    K.solidify(roof, 0.005, offset=0.0, even=False)
    ctx.add(roof, OD, uv="box", uv_scale=1.0, smooth=35, patches=0.5)
    for sx in (-0.35, 0.35):
        W.rod(ctx, f"ladder{sx}", (sx, -s - 0.12, 0.0), (sx, -s - 0.12, deck + 0.9), 0.022, "metal_galvanized", segs=6)
    for k in range(int(deck / 0.3) + 2):
        W.rod(ctx, f"rung{k}", (-0.35, -s - 0.12, 0.3 + k * 0.3), (0.35, -s - 0.12, 0.3 + k * 0.3), 0.014, "metal_galvanized", segs=5)
    lamp = K.cyl("searchlight", 0.17, 0.32, segs=12, center=(0.7, s * 0.9, deck + 0.95), axis="Y")
    ctx.add(lamp, "road_steel_dark", uv="box", uv_scale=3.0, patches=0.5)
    ctx.add(K.cyl("searchlens", 0.15, 0.01, segs=12, center=(0.7, s * 0.9 - 0.165, deck + 0.95), axis="Y"), "lens_clear", uv="box")


def _shell_box_walls(ctx, room, ops, *, z0, z1, mat, off=0.12, rib=0.0, seed=0):
    """Flat panel walls standing `off` outside a kit room's edge lines from z0 to z1, cut round the
    openings (side, index, kind) with a trim frame; optional vertical ribs every `rib` metres."""
    for side in ("N", "S", "E", "W"):
        start, along, out = room.side_line(side, off)
        L = room.length(side) + 2 * off
        st = start - along * off
        holes = O.holes_on(side, ops, floor=room.floor)
        holes = [(a + off, b + off, hz0, hz1) for (a, b, hz0, hz1) in holes]
        # Horizontal bands between hole heights, then vertical strips: a simple clip of the wall rectangle.
        cuts = sorted({z0, z1} | {max(z0, min(z1, h[2])) for h in holes} | {max(z0, min(z1, h[3])) for h in holes})
        for i in range(len(cuts) - 1):
            za, zb = cuts[i], cuts[i + 1]
            if zb - za < 0.01:
                continue
            for s0, s1 in O.clip_spans(0.0, L, za + 0.001, zb - 0.001, holes, min_len=0.01):
                p0 = st + along * s0
                p1 = st + along * s1
                pan = K.quad_sheet(f"{side}p{i}_{s0:.2f}", (p0.x, p0.y, za), (p1.x, p1.y, za), (p1.x, p1.y, zb), (p0.x, p0.y, zb),
                                   max(1, int((s1 - s0) / 0.4)), max(1, int((zb - za) / 0.4)))
                K.solidify(pan, 0.03, offset=1.0 if side in ("N", "E") else -1.0)
                # Wear patches are per-vertex: on a 1 m grid one patch interpolated across a whole
                # end wall into a single oval of paint in a field of rust (TD-238). A 0.4 m grid and
                # lighter patches give scattered rust spots and runs on a white body.
                ctx.add(pan, mat, uv="box", uv_scale=1.0, patches=0.3)
        for (a, b, hz0, hz1) in holes:
            for t in (a, b):
                p = st + along * t
                W.bar(ctx, f"{side}trim{t:.2f}", (p.x, p.y, max(z0, hz0)), (p.x, p.y, min(z1, hz1)), 0.05, 0.06, "road_steel",
                      up=tuple(out))
            for zz in (hz0, hz1):
                if z0 < zz < z1:
                    pa, pb = st + along * a, st + along * b
                    W.bar(ctx, f"{side}trimh{a:.2f}{zz:.1f}", (pa.x, pa.y, zz), (pb.x, pb.y, zz), 0.05, 0.06, "road_steel",
                          up=tuple(out))
        if rib > 0:
            t = rib
            while t < L - 0.05:
                p = st + along * t + out * 0.035
                if not any(a - 0.05 < t < b + 0.05 and hz0 < z1 for (a, b, hz0, hz1) in holes):
                    W.bar(ctx, f"{side}rib{t:.2f}", (p.x, p.y, z0), (p.x, p.y, z1), 0.04, 0.02, mat, up=tuple(out))
                t += rib


def w3_reefer_shell(ctx: K.Ctx) -> None:
    """A refrigerated semi-trailer body round the morgue's kit room (params w, d, floor, openings): white
    ribbed walls, a roof with rain rails, the reefer unit high on the front (north) wall, the rear doors
    swung back flat against its sides, sat down on railway-tie cribbing where its wheels came off, a
    generator cable to the unit and the MORGUE stencil on both sides."""
    fh = float(ctx.param("floor", 0.35))
    room = O.Room(int(ctx.param("w", 3)), int(ctx.param("d", 8)), fh)
    ops = [tuple(o) for o in ctx.param("openings", [("S", 1, "door")])]
    z0, z1 = fh - 0.18, fh + 3.02
    _shell_box_walls(ctx, room, ops, z0=z0, z1=z1, mat="t3_trailer_white", rib=0.5, seed=ctx.seed)
    hw, hd = room.w / 2 + 0.15, room.d / 2 + 0.15
    # Big flat parts on few vertices: light wear patches, or one interpolated patch rusts them whole
    # (TD-238, as on the walls).
    roof = K.box("roof", (2 * hw + 0.04, 2 * hd + 0.04, 0.05), center=(0, 0, z1 + 0.025), cuts=(6, 18, 0))
    ctx.add(roof, "t3_trailer_white", uv="box", uv_scale=1.0, patches=0.25)
    for sx in (-1, 1):
        W.bar(ctx, f"rail{sx}", (sx * hw, -hd, z1 + 0.06), (sx * hw, hd, z1 + 0.06), 0.06, 0.08, "road_alu")
        W.bar(ctx, f"skirt{sx}", (sx * hw, -hd, z0 - 0.02), (sx * hw, hd, z0 - 0.02), 0.06, 0.12, "road_alu")
    # Cribbing under the body: stacked ties.
    for k, y in enumerate((-hd + 0.6, -hd + 2.4, hd - 2.4, hd - 0.6)):
        for c in range(2):
            tie = K.box(f"tie{k}{c}", (2 * hw - 0.2 if c == 0 else 0.25, 0.25 if c == 0 else 2 * hd * 0.0 + 0.25, 0.09),
                        center=(0, y, 0.05 + c * 0.09))
            ctx.add(tie, "wood_creosote", uv="box", uv_scale=1.0, patches=0.6)
    # The reefer unit on the north wall, above the kit wall's top.
    unit = K.box("unit", (2.0, 0.55, 1.4), center=(0, hd + 0.3, z1 - 0.8), bevel=0.04)
    ctx.add(unit, "t3_trailer_white", uv="box", uv_scale=1.0, patches=0.2)
    grille = K.box("grille", (1.5, 0.02, 0.6), center=(0, hd + 0.58, z1 - 1.0))
    ctx.add(grille, "road_steel_dark", uv="box", uv_scale=4.0)
    fan = W.ring_obj("fan", 0.2, 0.28, 0.02, segs=18)
    K.place(fan, (0, 0, 0), (90, 0, 0))
    K.place(fan, (0.4, hd + 0.59, z1 - 0.45))
    ctx.add(fan, "road_steel_dark", uv="box", uv_scale=4.0)
    cable = K.tube("cable", [(0.7, hd + 0.3, z1 - 1.5), (0.9, hd + 0.5, 0.6), (1.2, hd + 1.3, 0.03), (2.4, hd + 3.0, 0.03)], 0.02, segs=5)
    ctx.add(cable, "tyre_rubber", uv="box", uv_scale=3.0, smooth=40)
    # Rear doors swung back flat against the sides (the kit door is the way in now).
    for sx in (-1, 1):
        lf = K.box(f"rear_leaf{sx}", (0.04, hw - 0.05, z1 - z0 - 0.1), center=(sx * (hw + 0.05), -hd + (hw - 0.05) / 2 + 0.05,
                                                                              (z0 + z1) / 2))
        ctx.add(lf, "t3_trailer_white", uv="box", uv_scale=1.0, patches=0.2)
    for sx in (-1, 1):
        _face(ctx, f"stencil{sx}", 1.8, 0.6, _rect("morgue"), (sx * (hw + 0.035), 0.4, z1 - 1.0), 90.0 * sx)
    _ = math


def w3_command_trailer_shell(ctx: K.Ctx) -> None:
    """A white site-office trailer round the command post's kit rooms (params w, d, floor, openings):
    ribbed walls on a plywood skirt, a low-sloped roof with an antenna mast and its whip, a lamp over the
    door, wooden steps up to it and the CORDON COMMAND stencil."""
    fh = float(ctx.param("floor", 0.35))
    room = O.Room(int(ctx.param("w", 4)), int(ctx.param("d", 9)), fh)
    ops = [tuple(o) for o in ctx.param("openings", [])]
    z0, z1 = fh - 0.05, fh + 3.0
    _shell_box_walls(ctx, room, ops, z0=z0, z1=z1, mat="t3_trailer_white", rib=0.6, seed=ctx.seed)
    hw, hd = room.w / 2 + 0.15, room.d / 2 + 0.15
    for sx in (-1, 1):
        sk = K.box(f"skirt{sx}", (0.02, 2 * hd, z0), center=(sx * hw, 0, z0 / 2))
        ctx.add(sk, "road_plywood", uv="box", uv_scale=1.0, patches=0.6)
    for sy in (-1, 1):
        sk = K.box(f"skirt_e{sy}", (2 * hw, 0.02, z0), center=(0, sy * hd, z0 / 2))
        ctx.add(sk, "road_plywood", uv="box", uv_scale=1.0, patches=0.6)
    roof = K.box("roof", (2 * hw + 0.2, 2 * hd + 0.2, 0.06), center=(0, 0, z1 + 0.05))
    K.place(roof, (0, 0, 0))
    ctx.add(roof, "road_alu", uv="box", uv_scale=1.0, patches=0.5)
    W.rod(ctx, "mast", (hw - 0.3, hd - 0.4, z1), (hw - 0.3, hd - 0.4, z1 + 3.2), 0.025, "metal_galvanized", segs=6)
    W.rod(ctx, "whip", (hw - 0.3, hd - 0.4, z1 + 3.2), (hw - 0.28, hd - 0.4, z1 + 5.0), 0.006, "road_steel_dark", segs=4)
    for sx in (-1, 1):
        _face(ctx, f"stencil{sx}", 1.9, 0.62, _rect("cordon_cmd"), (sx * (hw + 0.035), -1.0, z1 - 0.9), 90.0 * sx)
    for (side, idx, kind) in ops:
        if kind != "door":
            continue
        start, along, out = room.side_line(side, 0.15)
        c = start + along * (idx + 0.5)
        steps = max(1, int(round(fh / 0.18)))
        for k in range(steps):
            d = 0.3 * (steps - k)
            st = K.box(f"step{k}", (1.1, 0.3, 0.05), center=(0, 0, 0))
            K.orient(st, along, (0, 0, 1), c + out * (d - 0.15) + Vector((0, 0, fh - 0.18 * (steps - 1 - k) - 0.025 - 0.18 * 0)))
            ctx.add(st, "wood_weathered", uv="box", uv_scale=1.0, patches=0.6)
        lamp = K.box("door_lamp", (0.16, 0.12, 0.18), center=(0, 0, 0))
        K.place(lamp, c + out * 0.08 + Vector((0, 0, fh + 2.4)))
        ctx.add(lamp, "road_steel_dark", uv="box", uv_scale=3.0)


def w3_body_bag(ctx: K.Ctx) -> None:
    """A zipped body bag lying on the ground (clean: the Cordon's white bags; worn: an older black one),
    the shape of someone inside, carry handles, a zip down the middle and a tag."""
    r = ctx.rnd("bag")
    mat = "w3_bag_white" if not ctx.worn else "plastic_bag_black"
    L = 1.9
    rings = []
    for i in range(11):
        t = i / 10
        y = -L / 2 + L * t
        w = 0.3 * (0.75 + 0.25 * math.sin(math.pi * min(1.0, t * 1.3)))
        if t > 0.85:
            w *= 0.8
        h = 0.11 + 0.08 * math.sin(math.pi * min(1.0, 0.2 + t)) + (0.04 if 0.35 < t < 0.55 else 0.0)
        ring = []
        for j in range(10):
            a = math.pi * j / 9
            ring.append((-math.cos(a) * w, y, 0.012 + math.sin(a) * h))
        rings.append(ring)
    bag = K.loft("bag", rings, closed_ring=False, cap_start=True, cap_end=True)
    K.noise_disp(bag, 0.012, scale=5.0, seed=ctx.seed)
    ctx.add(bag, mat, uv="box", uv_scale=1.5, smooth=45, patches=0.4)
    zp = K.tube("zip", [(0, -L / 2 + 0.1, 0.15), (0, 0, 0.21), (0, L / 2 - 0.1, 0.15)], 0.008, segs=4)
    ctx.add(zp, "road_steel_dark", uv="box", uv_scale=6.0, smooth=30)
    for k, y in enumerate((-0.5, 0.0, 0.5)):
        for sx in (-1, 1):
            ctx.add(K.box(f"handle{k}{sx}", (0.03, 0.12, 0.05), center=(sx * 0.31, y, 0.06)), "item_webbing_black", uv="box")
    ctx.add(K.box("tag", (0.07, 0.1, 0.004), center=(0.12, L / 2 - 0.15, 0.17)), "paper_trash", uv="box", uv_scale=4.0)
    _ = r


def w3_morgue_rack(ctx: K.Ctx) -> None:
    """Steel shelving along the morgue's wall, three shelves, body bags on the lower two."""
    r = ctx.rnd("rack")
    L, D = 2.05, 0.78
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.bar(ctx, f"post{sx}{sy}", (sx * L / 2, sy * D / 2, 0.0), (sx * L / 2, sy * D / 2, 1.8), 0.035, 0.035, "road_steel")
    for k, z in enumerate((0.25, 0.95, 1.65)):
        sh = K.box(f"shelf{k}", (L, D, 0.03), center=(0, 0, z), bevel=0.004)
        ctx.add(sh, "road_steel", uv="box", uv_scale=1.0, patches=0.5)
        if k < 2 and not (ctx.worn and k == 1 and r.random() < 0.0):
            rings = []
            for i in range(9):
                t = i / 8
                x = -0.92 + 1.84 * t
                w = 0.28 * (0.8 + 0.2 * math.sin(math.pi * t))
                h = 0.12 + 0.07 * math.sin(math.pi * t)
                rings.append([(x, -math.cos(math.pi * j / 8) * w, z + 0.016 + math.sin(math.pi * j / 8) * h) for j in range(9)])
            bag = K.loft(f"bag{k}", rings, closed_ring=False)
            K.noise_disp(bag, 0.01, scale=5.0, seed=ctx.seed + k)
            ctx.add(bag, "w3_bag_white" if k == 0 else "plastic_bag_black", uv="box", uv_scale=1.5, smooth=45, patches=0.4)


def _ward_marker(ctx: K.Ctx) -> None:
    """A ward marker: an olive board with a white stencilled letter on a stake driven by a tent door."""
    q = int(ctx.param("quad", 0))
    sub = ((q % 2) * 0.5, (q // 2) * 0.5, (q % 2) * 0.5 + 0.5, (q // 2) * 0.5 + 0.5)
    W.bar(ctx, "stake", (0, 0, -0.05), (0, 0, 1.35), 0.05, 0.05, "wood_weathered", bevel=0.004)
    ctx.add(K.box("board", (0.42, 0.02, 0.42), center=(0, -0.035, 1.2)), "road_plywood", uv="box", uv_scale=2.0)
    _face(ctx, "letter", 0.4, 0.4, _rect("ward_letters", sub), (0, -0.0455, 1.2))


# ============================================================================================
# The Haldane Place
# ============================================================================================

def _scrap_palisade(ctx: K.Ctx, L: float) -> None:
    """A homestead's wall: bark-on posts set in the ground, two rails, and whatever they had nailed and
    wired to them - corrugated sheets, pallets, a car door, plywood - with barbed wire along the top
    (outside is -Y); destroyed: sheets torn off and a post leaning, a gap at the bottom."""
    r = ctx.rnd("scrap")
    n = 3
    for k in range(n):
        x = -L / 2 + 0.1 + (L - 0.2) * k / (n - 1)
        lean = (0, 0)
        if ctx.destroyed and k == 1:
            lean = (14, -10)
        _post(ctx, f"post{k}", x, 0.1, 2.55 + r.uniform(-0.1, 0.15), 0.1, ctx.seed + k, lean=lean, moss=0.25)
    for z in (0.5, 1.9):
        _log(ctx, f"rail{z}", (-L / 2, 0.2, z), (L / 2, 0.2, z + r.uniform(-0.05, 0.05)), 0.06, ctx.seed + int(z * 10), moss=0.2)
    x = -L / 2
    k = 0
    while x < L / 2 - 0.1:
        kind = r.choice(["corr", "corr", "pallet", "ply", "door"])
        w = {"corr": 0.85, "pallet": 1.0, "ply": 0.9, "door": 1.05}[kind]
        w = min(w, L / 2 - x)
        torn = ctx.destroyed and ctx.drnd(f"t{k}").random() < 0.5
        if torn:
            x += w
            k += 1
            continue
        cx = x + w / 2
        tilt = r.uniform(-2.5, 2.5)
        if kind == "corr":
            sh = K.grid(f"corr{k}", w, 2.3, 12, 2, center=(0, 0, 0))
            for v in sh.data.vertices:
                v.co.z += 0.02 * math.sin(v.co.x / w * 12 * math.pi)
            K.place(sh, (0, 0, 0), (90, 0, tilt))
            K.place(sh, (cx, 0.02, 0.05 + 1.15))
            K.solidify(sh, 0.003, offset=0.0, even=False)
            ctx.add(sh, "farm_corrugated_rust" if r.random() < 0.6 else "farm_corrugated_galv", uv="box", uv_scale=1.0, patches=0.6)
        elif kind == "pallet":
            for j in range(5):
                pl = P.plank(f"pal{k}{j}", 1.2, 0.09, 0.02)
                K.place(pl, (0, 0, 0), (0, 90, 0))
                K.place(pl, (x + 0.08 + j * (w - 0.16) / 4, 0.02, 0.15 + 0.6))
                ctx.add(pl, "wood_weathered", long_axis=0, patches=0.6)
            for z in (0.2, 0.75, 1.3):
                ctx.add(P.plank(f"palx{k}{z}", w, 0.09, 0.04), "wood_weathered", long_axis=0, patches=0.6,
                        at=((cx, 0.05, z), (90, 0, 0)))
            ply = K.box(f"palply{k}", (w, 0.012, 1.0), center=(cx, 0.0, 1.85))
            ctx.add(ply, "road_plywood", uv="box", uv_scale=1.0, patches=0.6)
        elif kind == "ply":
            ply = K.box(f"ply{k}", (w, 0.015, 2.2), center=(cx, 0.0, 1.15), cuts=(1, 0, 2))
            K.place(ply, (0, 0, 0))
            ctx.add(ply, "road_plywood", uv="box", uv_scale=1.0, patches=0.7, moss=0.3)
        else:
            door = K.box(f"cardoor{k}", (w, 0.08, 1.05), center=(cx, -0.02, 0.62), bevel=0.03, cuts=(2, 1, 2))
            K.noise_disp(door, 0.01, scale=3.0, seed=ctx.seed + k)
            ctx.add(door, r.choice(["car_paint_blue", "car_paint_tan", "car_paint_maroon"]), uv="box", uv_scale=1.0, patches=0.6)
            win = K.box(f"cardoorwin{k}", (w * 0.8, 0.02, 0.5), center=(cx, -0.03, 1.4))
            ctx.add(win, "window_grime", uv="box", uv_scale=1.0)
            ply2 = K.box(f"ply_top{k}", (w, 0.015, 0.7), center=(cx, 0.03, 2.0))
            ctx.add(ply2, "road_plywood", uv="box", uv_scale=1.0, patches=0.6)
        x += w
        k += 1
    for j in range(3):
        z = 2.45 + j * 0.1
        W.rod(ctx, f"barb{j}", (-L / 2, 0.0, z), (L / 2, 0.0, z + r.uniform(-0.02, 0.02)), 0.003, "metal_galvanized", segs=3)


def w3_scrap_palisade(ctx: K.Ctx) -> None:
    """Two metres of the Haldanes' scrap-and-log wall (see _scrap_palisade)."""
    _scrap_palisade(ctx, 2.0)


def w3_scrap_gate(ctx: K.Ctx) -> None:
    """The homestead's gate: a leaf of pallets and corrugated tin on a pole frame between two heavy posts,
    a chain round the latch post, the TURN BACK sign nailed over it."""
    r = ctx.rnd("sgate")
    for sx in (-1, 1):
        _post(ctx, f"post{sx}", sx * 1.32, 0.15, 2.9, 0.14, ctx.seed + sx, moss=0.3)
    frame = [W.rod_obj("fa", (-1.15, 0, 0.15), (1.15, 0, 0.15), 0.05), W.rod_obj("fb", (-1.15, 0, 2.2), (1.15, 0, 2.2), 0.05),
             W.rod_obj("fc", (-1.15, 0, 0.15), (1.15, 0, 2.2), 0.04)]
    ctx.add(K.merge_parts(frame, "frame"), "out_log_peeled", uv="box", uv_scale=1.0, patches=0.5)
    sh = K.grid("tin", 2.3, 2.0, 14, 2, center=(0, 0, 0))
    for v in sh.data.vertices:
        v.co.z += 0.02 * math.sin(v.co.x / 2.3 * 14 * math.pi)
    K.place(sh, (0, 0, 0), (90, 0, 0))
    K.place(sh, (0, -0.06, 1.18))
    K.solidify(sh, 0.003, offset=0.0, even=False)
    ctx.add(sh, "farm_corrugated_rust", uv="box", uv_scale=1.0, patches=0.6)
    ctx.add(K.box("signboard", (1.6, 0.02, 0.42), center=(0, -0.09, 1.6)), "road_plywood", uv="box")
    _face(ctx, "sign", 1.56, 0.4, _rect("haldane_warn"), (0, -0.101, 1.6))
    ch = W.chain_obj("chain", [(1.1, -0.1, 1.1), (1.28, -0.2, 0.95), (1.45, -0.1, 1.1)], link=0.05, wire=0.007)
    ctx.add(ch, "trap_chain", uv="box", uv_scale=8.0, smooth=40)
    _ = r


def w3_watch_platform(ctx: K.Ctx) -> None:
    """A watch platform the family built against their wall: four posts, a plank deck at 2.4 m behind a
    plywood-and-tin parapet, a ladder, a tarp over a pole, a chair and a coffee can of spent shells."""
    r = ctx.rnd("plat")
    s, deck = 1.0, 2.4
    for sx in (-1, 1):
        for sy in (-1, 1):
            _post(ctx, f"post{sx}{sy}", sx * s, sy * s, deck + (1.1 if sy > 0 else 0.95), 0.09, ctx.seed + sx * 2 + sy, moss=0.25)
    for sx in (-1, 1):
        W.bar(ctx, f"joist{sx}", (sx * s, -s - 0.1, deck - 0.08), (sx * s, s + 0.1, deck - 0.08), 0.08, 0.16, "wood_weathered")
    for sy in (-1, 1):
        W.bar(ctx, f"brace{sy}", (-s, sy * s, 0.4), (s, sy * s, deck - 0.2), 0.05, 0.1, "wood_weathered", up=(0, 1, 0))
    O.plank_deck(ctx, -s - 0.1, s + 0.1, -s - 0.1, s + 0.1, deck, board=0.18, along="x", mat="wood_weathered", seed=ctx.seed)
    for side, (a, b) in enumerate((((-s, -s), (s, -s)), ((-s, -s), (-s, s)), ((s, -s), (s, s)))):
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        L = math.dist(a, b)
        horiz = abs(a[1] - b[1]) < 0.01
        mat = "road_plywood" if side != 1 else "farm_corrugated_galv"
        pan = K.box(f"parapet{side}", (L if horiz else 0.015, 0.015 if horiz else L, 1.0), center=(mid[0], mid[1], deck + 0.5))
        ctx.add(pan, mat, uv="box", uv_scale=1.0, patches=0.6)
    for sx in (-0.25, 0.25):
        W.bar(ctx, f"ladder{sx}", (sx, s + 0.6, 0.0), (sx, s + 0.05, deck + 0.4), 0.05, 0.08, "wood_weathered")
    for k in range(7):
        t = (k + 1) / 8
        y = s + 0.6 - 0.55 * t
        W.bar(ctx, f"rung{k}", (-0.25, y, (deck + 0.4) * t), (0.25, y, (deck + 0.4) * t), 0.04, 0.06, "wood_weathered")
    tarp = K.quad_sheet("tarp", (-s - 0.3, -s - 0.2, deck + 1.9), (s + 0.3, -s - 0.2, deck + 1.9), (s + 0.3, s + 0.4, deck + 1.55),
                        (-s - 0.3, s + 0.4, deck + 1.55), 6, 6)
    K.crumple(tarp, 0.04, seed=ctx.seed)
    K.solidify(tarp, 0.004, offset=0.0, even=False)
    ctx.add(tarp, "tarp_blue", uv="box", uv_scale=1.0, smooth=35, patches=0.6)
    W.rod(ctx, "tarp_pole", (0, 0, deck), (0, 0, deck + 1.9), 0.035, "out_log_peeled", segs=6)
    can = K.cyl("shell_can", 0.07, 0.16, segs=10, center=(0.5, -0.4, deck + 0.08))
    ctx.add(can, "can_red", uv="cyl", uv_axis=2, smooth=40, patches=0.5)
    _ = r


def w3_raised_bed(ctx: K.Ctx) -> None:
    """A raised garden bed of rough planks, 1.2 x 3 m, dark soil and rows of kale and cabbage (clean),
    bolted to seed and yellowing (worn), trampled flat and spilled (destroyed)."""
    r = ctx.rnd("bed")
    Wd, L, H = 1.2, 3.0, 0.42
    for sy in (-1, 1):
        for k in range(2):
            ctx.add(P.plank(f"side{sy}{k}", L, 0.2, 0.04), "wood_weathered", long_axis=0, patches=0.6, moss=0.4,
                    at=((0, sy * Wd / 2, 0.1 + k * 0.2), (90, 0, 0)))
    for sx in (-1, 1):
        for k in range(2):
            ctx.add(P.plank(f"end{sx}{k}", Wd, 0.2, 0.04), "wood_weathered", long_axis=0, patches=0.6, moss=0.4,
                    at=((sx * L / 2, 0, 0.1 + k * 0.2), (90, 0, 90)))
    soil = K.grid("soil", L - 0.06, Wd - 0.06, 12, 5, center=(0, 0, H - 0.06 if not ctx.destroyed else H - 0.14))
    K.noise_disp(soil, 0.025, scale=3.0, seed=ctx.seed, along_normal=False)
    ctx.add(soil, "out_earth", uv="box", uv_scale=1.0, smooth=50, patches=0.4)
    if ctx.destroyed:
        sp = K.blob("spill", 0.4, subdiv=2, scale=(1.5, 1.0, 0.15), center=(0.4, -Wd / 2 - 0.3, 0.0), rough=0.3)
        ctx.add(sp, "out_earth", uv="box", uv_scale=1.0, smooth=50)
        return
    for row in (-0.3, 0.3):
        for k in range(6):
            x = -L / 2 + 0.3 + k * (L - 0.6) / 5
            c = Vector((x + r.uniform(-0.05, 0.05), row + r.uniform(-0.04, 0.04), H - 0.05))
            if ctx.worn:
                st = K.tube(f"bolt{row}{k}", [c, c + Vector((r.uniform(-0.05, 0.05), r.uniform(-0.05, 0.05), r.uniform(0.35, 0.6)))],
                            [0.015, 0.006], segs=4)
                ctx.add(st, "farm_hay", uv="box", uv_scale=3.0, smooth=40)
                lv = K.blob(f"wilt{row}{k}", 0.09, subdiv=1, scale=(1.3, 1.3, 0.35), center=c + Vector((0, 0, 0.03)), rough=0.4,
                            seed=k)
                ctx.add(lv, "farm_hay_old", uv="box", uv_scale=3.0, smooth=50)
            else:
                head = K.blob(f"head{row}{k}", 0.1, subdiv=2, scale=(1.0, 1.0, 0.8), center=c + Vector((0, 0, 0.08)), rough=0.2,
                              seed=k)
                ctx.add(head, "item_stem_green", uv="box", uv_scale=3.0, smooth=55, patches=0.3)
                for j in range(4):
                    a = j / 4 * math.tau + r.uniform(-0.3, 0.3)
                    lf = K.blob(f"leaf{row}{k}{j}", 0.07, subdiv=1, scale=(1.8, 1.0, 0.25), center=(0, 0, 0))
                    K.place(lf, (0, 0, 0), (0, -25, math.degrees(a)))
                    K.place(lf, c + Vector((math.cos(a) * 0.12, math.sin(a) * 0.12, 0.05)))
                    ctx.add(lf, "item_stem_green", uv="box", uv_scale=3.0, smooth=55)


def w3_rain_catcher(ctx: K.Ctx) -> None:
    """A rain catcher: a blue tarp sagged into a funnel on four poles over a blue drum with a tap and a
    plank to stand a bucket on."""
    s = 0.95
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.pole(ctx, f"pole{sx}{sy}", [(sx * s, sy * s, -0.02), (sx * s * 0.98, sy * s * 0.98, 2.05)], 0.04, "out_log_peeled",
                   r_end=0.035, seed=ctx.seed + sx * 2 + sy)
    tarp = K.grid("tarp", 2 * s + 0.2, 2 * s + 0.2, 10, 10, center=(0, 0, 2.0))
    for v in tarp.data.vertices:
        d = max(abs(v.co.x), abs(v.co.y)) / (s + 0.1)
        v.co.z = 2.02 - 0.55 * (1.0 - d) ** 1.6
    K.delete_faces(tarp, lambda c, n: abs(c.x) < 0.06 and abs(c.y) < 0.06)
    K.solidify(tarp, 0.004, offset=0.0, even=False)
    ctx.add(tarp, "tarp_blue", uv="box", uv_scale=1.0, smooth=40, patches=0.6)
    drum = K.lathe("drum", [(0.0, 0.0), (0.29, 0.0), (0.3, 0.05), (0.3, 0.85), (0.28, 0.88), (0.0, 0.88)], segs=16)
    ctx.add(drum, "plastic_blue", uv="cyl", uv_axis=2, smooth=40, patches=0.5)
    W.rod(ctx, "spout", (0, 0, 1.47), (0, 0, 0.9), 0.04, "plastic_black", segs=8)
    W.rod(ctx, "tap", (0, -0.3, 0.12), (0, -0.4, 0.12), 0.015, "road_brass", segs=6)
    ctx.add(P.plank("stand", 0.5, 0.2, 0.04), "wood_weathered", long_axis=0, patches=0.6, at=((0, -0.5, 0.02), (0, 0, 0)))


def w3_fallen_line_pole(ctx: K.Ctx) -> None:
    """A power pole down across the ground (Ezra Vane's camp, ADR-0058): the creosoted pole along X
    (9.4 m, the butt at -X up on a log chock where it was dragged), its crossarm at the top end
    knocked askew with a glass insulator left on it, a cut drop line looped off it in the grass."""
    r = ctx.rnd("fpole")
    L = 9.4
    # lying along X: the butt (r 0.15) at -X, raised on the chock; the top (r 0.11) on the ground
    pole = K.cyl("pole", 0.15, L, segs=10, axis="X", center=(0.0, 0.0, 0.0), r_top=0.11, cuts=8)
    K.place(pole, (0, 0, 0), (0, -1.6, 0))
    K.place(pole, (0.0, 0.0, 0.27))
    ctx.add(pole, "wood_creosote", uv="cyl", uv_scale=1.0, smooth=50, patches=0.4, moss=0.25)
    _log(ctx, "chock", (-L * 0.42, -0.45, 0.1), (-L * 0.42, 0.45, 0.11), 0.11, ctx.seed + 3, moss=0.3)
    arm = P.plank("crossarm", 2.44, 0.11, 0.09, cuts=2)
    K.place(arm, (0, 0, 0), (0, 0, 72.0 + r.uniform(-6, 6)))
    K.place(arm, (L * 0.43, 0.0, 0.2))
    ctx.add(arm, "wood_weathered", long_axis=0, patches=0.4)
    ins = K.lathe("insulator", [(0.0, 0.0), (0.055, 0.0), (0.06, 0.03), (0.04, 0.05), (0.05, 0.075),
                                (0.03, 0.1), (0.022, 0.13), (0.0, 0.135)], segs=10)
    K.place(ins, (0, 0, 0), (90, 0, 0))
    K.place(ins, (L * 0.43 - 0.3, -0.85, 0.24))
    ctx.add(ins, "glass_green", uv="cyl", uv_scale=1.0, smooth=50, wear=0.2)
    pts = [(L * 0.45, 0.1, 0.28)]
    for k in range(1, 14):
        t = k / 13.0
        pts.append((L * 0.45 - 1.2 * t + 0.5 * math.sin(t * 5.0), 0.3 + 1.1 * math.sin(t * 3.0), 0.03 + 0.25 * (1 - t) ** 2))
    line = K.tube("dropline", pts, 0.008, segs=4)
    ctx.add(line, "rubber_black", uv_scale=1.0, wear=0.2)


def w3_tarp_lean(ctx: K.Ctx) -> None:
    """A blue tarp strung lean-to fashion (Ezra Vane's camp, ADR-0058): its back edge tied high (2.0 m)
    along the side of the line truck it stands against (+Y), the front (-Y) on two peeled poles at
    1.3 m, guyed out to stakes; sagging between the ties. 3.2 x 2.4 m."""
    w, d = 3.2, 2.4
    tarp = K.grid("tarp", w, d, 12, 8, center=(0, 0, 0))
    for v in tarp.data.vertices:
        u = (v.co.y + d * 0.5) / d          # 0 front .. 1 back
        x = v.co.x / (w * 0.5)
        v.co.z = 1.3 + 0.7 * u - 0.12 * (1.0 - x * x) * math.sin(math.pi * u) - 0.05 * (1.0 - x * x)
    K.crumple(tarp, 0.02, seed=ctx.seed)
    K.solidify(tarp, 0.004, offset=0.0, even=False)
    ctx.add(tarp, "tarp_blue", uv="box", uv_scale=1.0, smooth=35, patches=0.6)
    for sx in (-1, 1):
        W.pole(ctx, f"pole{sx}", [(sx * (w * 0.5 - 0.1), -d * 0.5, -0.02), (sx * (w * 0.5 - 0.1), -d * 0.5, 1.36)], 0.035,
               "out_log_peeled", r_end=0.03, seed=ctx.seed + sx)
        W.rod(ctx, f"guy{sx}", (sx * (w * 0.5 - 0.1), -d * 0.5, 1.3), (sx * (w * 0.5 + 0.5), -d * 0.5 - 0.9, 0.02), 0.004,
              "rubber_black", segs=4)


def w3_stake_row(ctx: K.Ctx) -> None:
    """Sharpened stakes driven through a log at the foot of the wall, angled out (-Y) at the height of a
    man's chest, the way the player's own stake barricades stand."""
    r = ctx.rnd("stakes")
    _log(ctx, "base", (-1.2, 0.15, 0.13), (1.2, 0.15, 0.14), 0.14, ctx.seed, moss=0.4)
    for k in range(6):
        x = -1.0 + k * 0.4 + r.uniform(-0.05, 0.05)
        st = O.stake_obj(f"stake{k}", 1.55, 0.055, ctx.seed + k)
        K.place(st, (0, 0, 0), (-48 + r.uniform(-5, 5), r.uniform(-6, 6), 0))
        K.place(st, (x, 0.25, 0.0))
        ctx.add(st, None, uv=None, smooth=48, patches=0.45, edge=0.9, moss=0.2)


def _post_sign(ctx: K.Ctx) -> None:
    """A routed sign board on one or two bark-on posts (params cell, w, h, posts, top): the lodge's sign at
    the head of its track (antlers over it), the kennel's name board on a stake."""
    r = ctx.rnd("psign")
    cell = str(ctx.param("cell", "elk_ridge"))
    w, h = float(ctx.param("w", 2.0)), float(ctx.param("h", 0.5))
    posts = int(ctx.param("posts", 2))
    top = float(ctx.param("top", 2.1))
    xs = (-w / 2 - 0.08, w / 2 + 0.08) if posts == 2 else (0.0,)
    for k, x in enumerate(xs):
        _post(ctx, f"post{k}", x, 0.06, top + 0.25, 0.09 if posts == 2 else 0.05, ctx.seed + k, moss=0.3)
    tilt = ctx.drnd("tilt").uniform(-3, 3) if ctx.worn else 0.0
    b = K.box("board", (w, 0.05, h), bevel=0.008, cuts=(3, 0, 1))
    K.place(b, (0, 0, 0), (0, tilt, 0))
    K.place(b, (0, 0.0, top - h / 2))
    ctx.add(b, "civic_oak_dark", long_axis=0, patches=0.5, moss=0.3)
    for side, rz in ((-1, 0.0), (1, 180.0)):
        f = _face(ctx, f"face{side}", w - 0.04, h - 0.03, _rect(cell), (0, side * 0.026, 0), rz)
        K.place(f, (0, 0, 0), (0, tilt, 0))
        K.place(f, (0, 0, top - h / 2))
    if posts == 2 and bool(ctx.param("antlers", False)):
        for side in (-1, 1):
            a = O.antler_obj(f"antler{side}", 0.7, ctx.seed + 20 + side, side=side, tines=5)
            K.place(a, (0, 0, 0), (12, 0, 0))
            K.place(a, (side * 0.06, -0.02, top + 0.02))
            ctx.add(a, "out_antler", uv="box", uv_scale=3.0, smooth=50, patches=0.5)
    _ = r


BUILDERS = {
    "w3_lodge_sign": _post_sign,
    "w3_kennel_sign": _post_sign,
    "w3_camp_arch": w3_camp_arch,
    "w3_canoe_rack": w3_canoe_rack,
    "w3_camp_bunk": w3_camp_bunk,
    "w3_sign_loon": _plaque, "w3_sign_heron": _plaque, "w3_sign_osprey": _plaque, "w3_sign_kestrel": _plaque,
    "w3_sign_mess": _plaque, "w3_sign_lodge": _plaque, "w3_sign_infirmary": _plaque, "w3_sign_canoes": _plaque,
    "w3_evac_board": w3_evac_board,
    "w3_log_bench": w3_log_bench,
    "w3_chapel_cross": w3_chapel_cross,
    "w3_lodge_shell": w3_lodge_shell,
    "w3_stone_fireplace": w3_stone_fireplace,
    "w3_stone_chimney": w3_stone_chimney,
    "w3_antler_chandelier": w3_antler_chandelier,
    "w3_trophy_elk": w3_trophy_elk,
    "w3_trophy_deer": w3_trophy_deer,
    "w3_bear_rug": w3_bear_rug,
    "w3_gun_cabinet": w3_gun_cabinet,
    "w3_gambrel": w3_gambrel,
    "w3_kennel_run": w3_kennel_run,
    "w3_meat_rail": w3_meat_rail,
    "w3_ward_tent": w3_ward_tent,
    "w3_ward_cot": w3_ward_cot,
    "w3_decon_shower": w3_decon_shower,
    "w3_light_tower": w3_light_tower,
    "w3_cordon_fence": w3_cordon_fence,
    "w3_cordon_gate": w3_cordon_gate,
    "w3_sandbags": w3_sandbags,
    "w3_watchtower": w3_watchtower,
    "w3_reefer_shell": w3_reefer_shell,
    "w3_command_trailer_shell": w3_command_trailer_shell,
    "w3_body_bag": w3_body_bag,
    "w3_morgue_rack": w3_morgue_rack,
    "w3_ward_a": _ward_marker, "w3_ward_b": _ward_marker, "w3_ward_c": _ward_marker, "w3_ward_d": _ward_marker,
    "w3_scrap_palisade": w3_scrap_palisade,
    "w3_scrap_gate": w3_scrap_gate,
    "w3_watch_platform": w3_watch_platform,
    "w3_raised_bed": w3_raised_bed,
    "w3_rain_catcher": w3_rain_catcher,
    "w3_stake_row": w3_stake_row,
    "w3_fallen_line_pole": w3_fallen_line_pole,
    "w3_tarp_lean": w3_tarp_lean,
}


def build(params: dict, outputs: list[str]) -> None:
    K.run(params, outputs, BUILDERS)
