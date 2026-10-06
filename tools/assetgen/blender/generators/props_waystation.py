"""Waystation 9 props - the Remand Program's trader relay post built into the Cordon wall where the river leaves
the valley. Military / quarantine checkpoint kit a year into the collapse: olive-drab corrugated steel, hesco
cages of mesh and earth, sandbags, Program yellow-black hazard paint, stencils, floodlights on a generator.

  waystation_counter       the trader's kiosk: a corrugated booth with a wide serving hatch (counter shelf at
                           1.05 m, the roll-up mesh grille rolled away above it), a chalk price board, stock on
                           a shelving unit and a high shelf, a side doorway behind a canvas curtain. The
                           quartermaster stands INSIDE: TRADER_SPOT below is kept clear (no part, no collider).
  waystation_board         contracts notice board: two posts, plywood under a tin roof, pinned sheets and a map
  waystation_tower         guard tower: four splayed legs, X bracing, a sandbagged deck with a corrugated skirt,
                           tin roof, floodlight, back ladder
  waystation_barrier       hesco-style cage segment (three cells) with concertina wire; destroyed: a burst cell
  waystation_gate          checkpoint boom gate: counterweighted pedestal, hazard-striped arm, rest fork, HALT plate
  waystation_sign          WAYSTATION 9 / REMAND PROGRAM on two posts (atlas sign / sign_worn)
  waystation_floodlight    twin-head floodlight pole, its cable run to a portable generator at its foot
  waystation_supply_stack  Program crates, drums and ammo cans strapped on a pallet

Built on the interior-props framework (lib/props_int_core.py: Prop, variants clean / worn / destroyed, wear /
AO vertex colours, collision boxes; lib/props_int_mesh.py geometry, canonical element order). Graphics come
from textures/gen/waystation.py (ATLAS below mirrors PRINT_RECTS there).

params: prop (id), seed, variants, mount, budget (see blender_catalogs/props_waystation.py).
"""
from __future__ import annotations

import math

import bmesh
from mathutils import Matrix, Vector

from lib import materials
from lib import props_int_core as core
from lib import props_int_mesh as G
from lib.props_int_core import Prop


class C:
    """Material ids: ws_* from game/data/materials/props_waystation.json, the rest from other families."""
    PRINT = "ws_print"
    HAZ = "ws_hazard"
    CORR = "ws_corrugated_olive"
    OLIVE = "ws_paint_olive"
    YELLOW = "ws_paint_yellow"
    BLACK = "ws_paint_black"
    WHITE = "ws_paint_white"
    LINER = "ws_geotextile"
    BAG_TAN = "ws_sandbag_tan"
    BAG_OLIVE = "ws_sandbag_olive"
    FLOOD = "ws_flood_glow"
    BULB = "ws_bulb_glow"
    # shared
    ROOF = "farm_corrugated_galv"
    ROOF_RUST = "farm_corrugated_rust"
    MESH = "ws_hesco_mesh"
    EARTH = "out_earth"
    CONCRETE = "road_concrete"
    STEEL = "road_steel"
    PLY = "road_plywood"
    WOOD = "wood_weathered"
    GALV = "metal_galvanized"
    CANVAS = "canvas_olive"
    RUBBER = "rubber_black"
    LENS = "lens_clear"
    LENS_A = "lens_amber"
    AMMO = "town4_ammo_can"
    TIN = "town4_tin"
    CARD = "cardboard"
    SHELF = "metal_shelf_grey"
    STRAP = "plastic_yellow"
    PL_BLACK = "plastic_black"
    CHAIN = "trap_chain"
    RED = "paint_red"


# Blender-only preview colours for dev_preview renders (Godot swaps in the real materials).
materials.PREVIEW_COLORS.update({
    C.HAZ: (0.6, 0.45, 0.05), C.CORR: (0.17, 0.19, 0.1), C.OLIVE: (0.1, 0.11, 0.05), C.YELLOW: (0.65, 0.42, 0.04),
    C.BLACK: (0.03, 0.03, 0.03), C.WHITE: (0.7, 0.68, 0.62), C.LINER: (0.38, 0.35, 0.27), C.BAG_TAN: (0.45, 0.38, 0.24),
    C.BAG_OLIVE: (0.22, 0.22, 0.12), C.FLOOD: (1.0, 1.0, 1.0), C.BULB: (1.0, 0.9, 0.7), C.PRINT: (0.5, 0.5, 0.5),
    C.MESH: (0.4, 0.4, 0.4), C.EARTH: (0.25, 0.19, 0.13),
})

# waystation_print atlas rects (x0, y0, x1, y1) in pixels of the 2048 px texture - mirror of
# textures/gen/waystation.py PRINT_RECTS.
ATLAS_SIZE = 2048.0
ATLAS: dict[str, tuple[int, int, int, int]] = {
    "sign": (0, 0, 1024, 512),
    "sign_worn": (1024, 0, 2048, 512),
    "map": (0, 512, 512, 1024),
    "price": (512, 512, 960, 1024),
    "emblem": (960, 512, 1216, 768),
    "gen_panel": (1216, 512, 1472, 768),
    "crate_end": (1472, 512, 1728, 768),
    "crate_top": (1728, 512, 1984, 768),
    "halt": (960, 768, 1472, 1024),
    "crate_side": (1472, 768, 1984, 1024),
    "sheet0": (0, 1024, 192, 1280),
    "sheet1": (192, 1024, 384, 1280),
    "sheet2": (384, 1024, 576, 1280),
    "sheet3": (576, 1024, 768, 1280),
    "note0": (768, 1024, 896, 1152),
    "note1": (896, 1024, 1024, 1152),
    "note2": (1024, 1024, 1152, 1152),
    "note3": (1152, 1024, 1280, 1152),
    "plate": (768, 1152, 1024, 1280),
    "header": (1280, 1024, 2048, 1152),
}

# Kiosk: where the trader stands (Blender metres from the prop origin: x right, y back; floor z). The
# standing box TRADER_BOX (x0, y0, x1, y1) stays free of parts and colliders. Godot: (x, floor, -y).
TRADER_SPOT = (-0.3, 0.05, 0.0)
TRADER_BOX = (-1.0, -0.3, 0.45, 0.76)


def atlas(name: str, inset: float = 1.5) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = ATLAS[name]
    return core._px_rect(x0 + inset, y0 + inset, x1 - inset, y1 - inset, ATLAS_SIZE)


# ------------------------------------------------------------------------------------------------
# shared helpers
# ------------------------------------------------------------------------------------------------


def _rot_for(facing: str) -> tuple[float, float, float]:
    return {"-Y": (0, 0, 0), "+Y": (0, 0, 180), "+X": (0, 0, 90), "-X": (0, 0, -90), "+Z": (-90, 0, 0)}[facing]


def plate(p: Prop, w: float, h: float, center, uvrect, *, t: float = 0.002, mat: str = C.PRINT, facing: str = "-Y",
          wear: float = 0.35, rot=None, back=None) -> core.Part:
    """Thin printed panel w x h (built in the XZ plane facing -Y, then turned by `rot` or to `facing`) whose
    front face shows `uvrect`; the back shows `back` (a rect) or the rect's edge colour."""
    obj = G.box(p._name("plate"), (w, t, h), (0, 0, 0), 0.0)
    u0, v0, u1, v1 = uvrect
    edge = (u0, v0, u0 + (u1 - u0) * 0.02, v0 + (v1 - v0) * 0.02)

    def fr(poly):
        n = poly.normal
        if n.y < -0.9:
            return (u0, v0, u1, v1, 0, 2, False)
        if n.y > 0.9 and back is not None:
            return (*back, 0, 2, True)
        return (*edge, 0 if abs(n.x) < 0.5 else 1, 2, False)

    core.set_face_uvs(obj, fr)
    G.xform(obj, rot=rot if rot is not None else _rot_for(facing), loc=center)
    return p.add(obj, mat, uv="keep", wear=wear)


def bar(p: Prop, a, b, w: float, d: float, mat: str, **kw) -> core.Part:
    """Rectangular beam from point a to b (w x d section)."""
    a, b = Vector(a), Vector(b)
    v = b - a
    obj = G.box(p._name("bar"), (w, d, v.length), (0, 0, 0), kw.pop("bevel", 0.003))
    q = Vector((0, 0, 1)).rotation_difference(v.normalized())
    obj.data.transform(Matrix.Translation((a + b) * 0.5) @ q.to_matrix().to_4x4())
    obj.data.update()
    kw.setdefault("grain", "Z")
    return p.add(obj, mat, **kw)


def rod(p: Prop, a, b, r: float, mat: str, segs: int = 8, cap: bool = True, **kw) -> core.Part:
    """Round rod from a to b."""
    a, b = Vector(a), Vector(b)
    v = b - a
    obj = G.cyl(p._name("rod"), r, v.length, (0, 0, 0), "Z", segs, None, 0.0, 1, cap)
    q = Vector((0, 0, 1)).rotation_difference(v.normalized())
    obj.data.transform(Matrix.Translation((a + b) * 0.5) @ q.to_matrix().to_4x4())
    obj.data.update()
    kw.setdefault("edge_deg", 40.0)
    return p.add(obj, mat, **kw)


def shift(p: Prop, dx: float, dy: float) -> None:
    """Moves every part and collider so the footprint is centred on the origin (the game's box stand-ins
    and def colliders are centred there)."""
    for q in p.parts:
        G.xform(q.obj, loc=(dx, dy, 0.0))
    p.colliders = [(c + Vector((dx, dy, 0.0)), s, r) for c, s, r in p.colliders]


def mesh_panel(p: Prop, size, center, mat: str = C.MESH, wear: float = 0.5) -> core.Part:
    """Single-sided quad of alpha-cut wire mesh (the foliage shader draws both sides; a thin box would draw
    the wire twice, a moire of doubled lattice). size: (x, y, z) with one zero (the panel's normal axis)."""
    sx, sy, sz = (s * 0.5 for s in size)
    if size[1] == 0.0:
        pts = [(-sx, 0, -sz), (sx, 0, -sz), (sx, 0, sz), (-sx, 0, sz)]
    else:
        pts = [(0, -sy, -sz), (0, sy, -sz), (0, sy, sz), (0, -sy, sz)]
    bm = bmesh.new()
    bm.faces.new([bm.verts.new(Vector(q) + Vector(center)) for q in pts])
    return p.add(G._obj(p._name("mesh"), bm), mat, uv_scale=0.66, wear=wear)


def place(parts, matrix: Matrix) -> None:
    for q in parts:
        q.obj.data.transform(matrix)
        q.obj.data.update()


def sheet_box(p: Prop, x0: float, x1: float, y0: float, y1: float, z0: float, z1: float, mat: str = C.CORR,
              grain: str = "Z", **kw) -> core.Part:
    """Axis-aligned sheet / slab between the given bounds. Corrugated sheets: grain Z on walls gives
    vertical ribs (farm_corrugated ribs run across V)."""
    kw.setdefault("wear", 0.9)
    return p.box((x1 - x0, y1 - y0, z1 - z0), ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), mat,
                 bevel=kw.pop("bevel", 0.002), grain=grain, **kw)


def roof_sheet(p: Prop, x0: float, x1: float, y0: float, z0: float, y1: float, z1: float, mat: str, t: float = 0.012,
               lift: float = 0.0) -> core.Part:
    """Corrugated roof sheet from the eave (y0, z0) to (y1, z1) across x0..x1, ribs running down the slope.
    lift (degrees) tips the sheet up about its (y1) edge (a loose, wind-lifted sheet)."""
    L = math.hypot(y1 - y0, z1 - z0)
    part = p.box((x1 - x0, L, t), (0, 0, 0), mat, bevel=0.002, grain="Y", wear=0.9)
    ang = math.degrees(math.atan2(z1 - z0, y1 - y0))
    G.xform(part.obj, rot=(ang, 0, 0), loc=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2 + t / 2))
    if lift:
        G.xform(part.obj, rot=(lift, 0, 0), pivot=((x0 + x1) / 2, y1, z1))
    return part


def bolt(p: Prop, pos, axis: str = "-Y", r: float = 0.012, mat: str = C.STEEL) -> core.Part:
    return p.cyl(r, 0.012, pos, mat, axis=axis.strip("-+"), segs=6, wear=1.5)


def sandbag_row(p: Prop, start, length: float, n: int, *, yaw: float = 0.0, w: float = 0.3, h: float = 0.17,
                mat: str = C.BAG_TAN, key: str = "bags", slump: float = 0.0, skip=()) -> list:
    """A course of n sandbags laid end to end along local +X from `start` (bottom of the course), turned by
    yaw: one skinned strip per run of bags, pinched at every seam (8-sided superellipse sections, 4 spans a
    bag). slump (worn): per-bag sag and sideways lean. skip: bag indices left out (gaps)."""
    r = p.rng(key)
    vr = p.vrng(key)
    bl = length / n
    out = []
    runs, cur = [], []
    for i in range(n):
        if i in skip:
            if cur:
                runs.append(cur)
            cur = []
        else:
            cur.append(i)
    if cur:
        runs.append(cur)
    m = Matrix.Translation(Vector(start)) @ Matrix.Rotation(math.radians(yaw), 4, "Z")
    for run in runs:
        rings = []
        for i in run:
            hs = r.uniform(0.9, 1.05) * (1.0 - (vr.uniform(0.0, 0.35) * slump))
            dy = r.uniform(-0.015, 0.015) + vr.uniform(-1, 1) * slump * 0.03
            tilt = vr.uniform(-1, 1) * slump * 0.04
            fr = [0.0, 0.18, 0.5, 0.82] if i != run[-1] else [0.0, 0.18, 0.5, 0.82, 1.0]
            for f in fr:
                pinch = f in (0.0, 1.0)
                s = 0.62 if pinch else (0.93 if f != 0.5 else 1.0)
                hh = h * hs * (0.7 if pinch else s)
                ww = w * s
                x = (i + f) * bl
                ring = []
                for k in range(8):
                    a = 2 * math.pi * (k + 0.5) / 8
                    c, sn = math.cos(a), math.sin(a)
                    yy = ww / 2 * math.copysign(abs(c) ** 0.5, c)
                    zz = hh / 2 * math.copysign(abs(sn) ** 0.5, sn)
                    ring.append(Vector((x, yy + dy + zz * tilt, zz + hh / 2)))
                rings.append(ring)
        bm = bmesh.new()
        vs = [[bm.verts.new(m @ q) for q in ring] for ring in rings]
        for a_, b_ in zip(vs[:-1], vs[1:]):
            for k in range(8):
                j = (k + 1) % 8
                bm.faces.new((a_[k], a_[j], b_[j], b_[k]))
        bm.faces.new(vs[0])
        bm.faces.new(list(reversed(vs[-1])))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        out.append(p.add(G._obj(p._name(key), bm), mat, wear=0.5, edge_deg=45.0, uv_scale=1.0))
    return out


def coil(p: Prop, a, b, R: float, pitch: float, *, key: str, mat: str = C.STEEL, per_turn: int = 10, wire: float = 0.005,
         sag: float = 0.0, wobble: float = 0.06) -> core.Part:
    """Concertina razor wire: a jittered helix of radius R from a to b (pitch m per turn), sagging by `sag`
    in the middle, as a thin 3-sided tube."""
    A, B = Vector(a), Vector(b)
    u = (B - A)
    L = u.length
    u.normalize()
    v = Vector((0, 0, 1)).cross(u)
    if v.length < 1e-6:
        v = Vector((0, 1, 0))
    v.normalize()
    w = u.cross(v)
    r = p.rng(key)
    n = max(4, int(L / pitch * per_turn))
    pts = []
    for i in range(n + 1):
        t = i / n
        th = 2 * math.pi * L / pitch * t
        rr = R * (1.0 + r.uniform(-wobble, wobble))
        q = A + u * (L * t) + (v * math.cos(th) + w * math.sin(th)) * rr
        q.z -= sag * 4 * t * (1 - t)
        pts.append(q)
    return p.tube(pts, wire, mat, segs=3, cap=False, wear=0.4)


def crate(p: Prop, size, center, yaw: float = 0.0, rot=None) -> core.Part:
    """Program supply crate: olive planked faces from the atlas (stencilled sides, arrowed ends, plank top),
    center = bottom centre."""
    sx, sy, sz = size
    obj = G.box(p._name("crate"), size, (0, 0, sz / 2), 0.004)
    side, end, top = atlas("crate_side", 3), atlas("crate_end", 3), atlas("crate_top", 3)
    flip = sx < sy  # long axis along Y: the stencilled cell goes on the X faces

    def fr(poly):
        n = poly.normal
        if abs(n.y) > 0.9:
            return (*(end if flip else side), 0, 2, n.y > 0)
        if abs(n.x) > 0.9:
            return (*(side if flip else end), 1, 2, n.x < 0)
        return (*top, 0, 1, False)

    core.set_face_uvs(obj, fr)
    G.xform(obj, rot=rot if rot is not None else (0, 0, yaw), loc=center)
    return p.add(obj, C.PRINT, uv="keep", wear=0.9)


def drum(p: Prop, c, r: float = 0.29, h: float = 0.88, mat: str = C.OLIVE, dent: float = 0.0, rot=None) -> list:
    """Steel drum with two rolling hoops, chimes and the two bungs; c = bottom centre."""
    prof = [(r * 0.96, 0.0), (r, 0.015), (r, h * 0.33 - 0.012), (r * 1.025, h * 0.33), (r, h * 0.33 + 0.012),
            (r, h * 0.67 - 0.012), (r * 1.025, h * 0.67), (r, h * 0.67 + 0.012), (r, h - 0.015), (r * 0.96, h),
            (r * 0.9, h - 0.008), (0.0, h - 0.008)]
    body = p.lathe(prof, (0, 0, 0), mat, segs=16, wear=1.0)
    if dent:
        for vtx in body.obj.data.vertices:
            if vtx.co.x > r * 0.6 and 0.2 * h < vtx.co.z < 0.8 * h:
                vtx.co.x -= dent * (1.0 - abs(vtx.co.z - h * 0.5) / (h * 0.3)) * (vtx.co.x / r)
    out = [body, p.cyl(0.03, 0.02, (r * 0.55, 0, h), C.STEEL, segs=6), p.cyl(0.018, 0.02, (-r * 0.55, 0, h), C.STEEL, segs=6)]
    m = Matrix.Translation(Vector(c))
    if rot is not None:
        m = m @ G.rot_matrix(rot)
    place(out, m)
    return out


def ammo_can(p: Prop, c, yaw: float = 0.0) -> list:
    x, y, z = c
    out = [p.box((0.28, 0.14, 0.17), (0, 0, 0.085), C.AMMO, bevel=0.006),
           p.box((0.29, 0.15, 0.03), (0, 0, 0.175), C.AMMO, bevel=0.006),
           p.box((0.1, 0.02, 0.012), (0, 0, 0.196), C.AMMO, bevel=0.002),
           p.box((0.04, 0.03, 0.06), (0.13, -0.08, 0.16), C.AMMO, bevel=0.004)]
    place(out, Matrix.Translation((x, y, z)) @ Matrix.Rotation(math.radians(yaw), 4, "Z"))
    return out


def pallet(p: Prop, cx: float, cy: float, W: float = 1.2, D: float = 1.0) -> float:
    """Stringer pallet: 7 deck boards, 3 stringers, 3 bottom boards. Returns the deck top z."""
    wd = C.WOOD
    for k in range(3):
        p.box((W, 0.09, 0.016), (cx, cy - D / 2 + 0.045 + k * (D - 0.09) / 2, 0.008), wd, bevel=0.002, grain="X")
        p.box((W, 0.038, 0.09), (cx, cy - D / 2 + 0.019 + k * (D - 0.038) / 2, 0.061), wd, bevel=0.003, grain="X")
    for k in range(7):
        p.box((W, 0.09, 0.016), (cx, cy - D / 2 + 0.045 + k * (D - 0.09) / 6, 0.114), wd, bevel=0.002, grain="X")
    return 0.122


def tin(p: Prop, x: float, y: float, z: float, r: float = 0.038, h: float = 0.11) -> core.Part:
    return p.cyl(r, h, (x, y, z + h / 2), C.TIN, segs=8, wear=0.8)


def lamp_head(p: Prop, pivot, *, tilt: float = 20.0, yaw: float = 0.0, broken: bool = False, w: float = 0.34,
              h: float = 0.26) -> list:
    """Floodlight head: a finned housing with a bezel, lens and the glowing reflector, in a U yoke whose pin is
    at `pivot`; the head faces -Y tilted down by `tilt` degrees, then the whole turns by yaw."""
    d = 0.16
    head = [p.rbox((w, d, h), (0, 0.01, 0), C.BLACK, radius=0.02, inner=(1, 1, 1))]
    for sz in (-1, 1):
        head.append(p.box((w + 0.02, 0.03, 0.025), (0, -d / 2 + 0.005, sz * (h / 2 - 0.0)), C.BLACK, bevel=0.004))
    for sx in (-1, 1):
        head.append(p.box((0.025, 0.03, h), (sx * (w / 2), -d / 2 + 0.005, 0), C.BLACK, bevel=0.004))
    head.append(p.box((w - 0.05, 0.004, h - 0.05), (0, -d / 2 + 0.012, 0), C.FLOOD, bevel=0.0, wear=0.0))
    if not broken:
        head.append(p.box((w - 0.03, 0.006, h - 0.03), (0, -d / 2 - 0.004, 0), C.LENS, bevel=0.0, wear=0.0))
    else:
        tri = p.prism([(-w / 2 + 0.02, -h / 2 + 0.02), (0.02, -h / 2 + 0.02), (-w / 2 + 0.02, 0.03)], 0.006, C.LENS, plane="XZ",
                      offset=-d / 2 - 0.007, wear=0.0)
        head.append(tri)
    for k in range(5):
        head.append(p.box((0.006, 0.05, h - 0.06), (-w / 2 + 0.06 + k * (w - 0.12) / 4, d / 2 + 0.03, 0), C.BLACK, bevel=0.0))
    G_rot = Matrix.Rotation(math.radians(tilt), 4, "X")
    place(head, G_rot)
    yoke = [rod(p, (-w / 2 - 0.03, 0, 0), (w / 2 + 0.03, 0, 0), 0.012, C.STEEL, segs=6),
            bar(p, (-w / 2 - 0.03, 0, 0.01), (-w / 2 - 0.03, 0, -h / 2 - 0.06), 0.012, 0.04, C.OLIVE),
            bar(p, (w / 2 + 0.03, 0, 0.01), (w / 2 + 0.03, 0, -h / 2 - 0.06), 0.012, 0.04, C.OLIVE),
            bar(p, (-w / 2 - 0.036, 0, -h / 2 - 0.06), (w / 2 + 0.036, 0, -h / 2 - 0.06), 0.04, 0.012, C.OLIVE),
            p.cyl(0.02, 0.06, (0, 0, -h / 2 - 0.09), C.STEEL, segs=6)]
    allp = head + yoke
    place(allp, Matrix.Translation(Vector(pivot)) @ Matrix.Rotation(math.radians(yaw), 4, "Z"))
    return allp


# ================================================================================================
# 1. the trader's kiosk
# ================================================================================================

def waystation_counter(p: Prop) -> None:
    """Trade kiosk (3.0 x 2.6 x 1.7): an olive corrugated booth on a steel frame. The front wall has the
    serving hatch (1.8 x 1.0 opening over a plank counter shelf whose top is at 1.05 m, a hazard-striped lip,
    steel brackets outside), the roll-up mesh grille rolled up under a hood above it in its guide rails, the
    chalk price board on the right, the Program roundel plate low on the front and a hazard kick band. The
    roof (galvanised, rusted when worn) overhangs the counter. Inside: a steel shelving unit of stock on the
    right wall, crates in the corners, a high shelf of tins and a radio on the back wall, a work lamp hanging
    from the roof, a side doorway on the left with its canvas curtain bunched back. TRADER_BOX (1.45 x 1.06 m
    behind the hatch) is left empty for the quartermaster."""
    worn = p.worn
    FW, BW = -0.55, 0.8           # front / back wall planes (outer faces at FW - 0.01, BW + 0.0)
    XL, XR = -1.5, 1.5
    H = 2.45
    HX0, HX1, HZ0, HZ1 = -1.2, 0.6, 1.05, 2.05
    t = 0.02

    def roof_z(y):
        return 2.62 - (y + 0.9) * (0.15 / 1.85)

    # frame
    for x in (XL + 0.035, XR - 0.035):
        for y in (FW + 0.035, BW - 0.035):
            p.box((0.07, 0.07, H), (x, y, H / 2), C.OLIVE, bevel=0.004)
    for x in (HX0 - 0.03, HX1 + 0.03):
        p.box((0.06, 0.06, H), (x, FW + 0.03, H / 2), C.OLIVE, bevel=0.004)
    # front wall
    sheet_box(p, XL, XR, FW - t / 2, FW + t / 2, 0.25, HZ0 - 0.05)
    sheet_box(p, XL, XR, FW - 0.024, FW - t / 2, 0.0, 0.25, mat=C.HAZ, grain="X")
    sheet_box(p, XL, HX0, FW - t / 2, FW + t / 2, HZ0 - 0.05, H)
    sheet_box(p, HX1, XR, FW - t / 2, FW + t / 2, HZ0 - 0.05, H)
    sheet_box(p, HX0, HX1, FW - t / 2, FW + t / 2, HZ1 + 0.03, H)
    p.box((XR - XL, 0.04, roof_z(FW) - H), (0, FW, (H + roof_z(FW)) / 2), C.OLIVE, bevel=0.003, grain="X")
    # back wall
    sheet_box(p, XL, XR, BW - t, BW, 0.0, roof_z(BW))
    # side walls: right full, left with the doorway (y -0.05 .. 0.65, 2.0 high)
    DY0, DY1, DZ = -0.05, 0.65, 2.0
    sheet_box(p, XR - t, XR, FW, BW, 0.0, H)
    sheet_box(p, XL, XL + t, FW, DY0, 0.0, H)
    sheet_box(p, XL, XL + t, DY1, BW, 0.0, H)
    sheet_box(p, XL, XL + t, DY0, DY1, DZ, H)
    for y in (DY0 - 0.03, DY1 + 0.03):
        p.box((0.06, 0.06, H), (XL + 0.03, y, H / 2), C.OLIVE, bevel=0.004)
    for x0 in (XL, XR - t):
        p.prism([(FW, H), (BW, H), (BW, roof_z(BW)), (FW, roof_z(FW))], t, C.CORR, plane="YZ", offset=x0, grain="Z")
    # roof on three purlins
    for y in (-0.5, 0.15, 0.75):
        p.box((XR - XL + 0.1, 0.05, 0.07), (0, y, roof_z(y) - 0.035), C.OLIVE, bevel=0.003, grain="X")
    roof_sheet(p, -1.62, 0.02, -0.92, roof_z(-0.92), 0.95, roof_z(0.95), C.ROOF_RUST if worn else C.ROOF,
               lift=4.0 if worn else 0.0)
    roof_sheet(p, -0.02, 1.62, -0.92, roof_z(-0.92) + 0.006, 0.95, roof_z(0.95) + 0.006, C.ROOF_RUST if worn else C.ROOF)
    # counter shelf, hazard lip, brackets
    sheet_box(p, HX0 - 0.04, HX1 + 0.04, -0.88, -0.3, HZ0 - 0.05, HZ0, mat=C.WOOD, grain="X")
    sheet_box(p, HX0 - 0.04, HX1 + 0.04, -0.886, -0.88, HZ0 - 0.06, HZ0 + 0.004, mat=C.HAZ, grain="X")
    for x in (HX0 + 0.2, (HX0 + HX1) / 2, HX1 - 0.2):
        p.prism([(FW - t / 2, HZ0 - 0.05), (FW - t / 2, HZ0 - 0.35), (-0.84, HZ0 - 0.05)], 0.03, C.OLIVE, plane="YZ",
                offset=x - 0.015)
    # roll-up grille: guide rails, the roll under its hood, bottom bar and the open padlock
    for x in (HX0 - 0.02, HX1 + 0.02):
        p.box((0.05, 0.04, HZ1 - HZ0 + 0.1), (x, FW - 0.03, (HZ0 + HZ1) / 2 + 0.05), C.GALV, bevel=0.003)
    L = HX1 - HX0 + 0.06
    cx = (HX0 + HX1) / 2
    p.cyl(0.05, L - 0.04, (cx, FW - 0.11, 2.2), C.GALV, axis="X", segs=10)
    p.cyl(0.095, L - 0.06, (cx, FW - 0.11, 2.2), C.MESH, axis="X", segs=14, uv_scale=0.66, wear=0.3)
    for sx in (-1, 1):
        p.cyl(0.11, 0.012, (cx + sx * L / 2, FW - 0.11, 2.2), C.OLIVE, axis="X", segs=12)
    hood = p.box((L + 0.02, 0.24, 0.008), (cx, FW - 0.12, 2.33), C.OLIVE, bevel=0.0, grain="X")
    G.xform(hood.obj, rot=(-12, 0, 0), pivot=(cx, FW, 2.33))
    p.box((L - 0.06, 0.03, 0.035), (cx, FW - 0.11, 2.085), C.GALV, bevel=0.004, grain="X")
    p.box((0.04, 0.02, 0.05), (cx, FW - 0.13, 2.04), C.STEEL, bevel=0.004)
    p.add(G.tube(p._name("shackle"), [(cx - 0.012, FW - 0.13, 2.065), (cx - 0.012, FW - 0.13, 2.09), (cx + 0.012, FW - 0.13, 2.09)],
                 0.004, 4, True), C.STEEL, edge_deg=50.0)
    if worn:
        # a torn strip of the grille has dropped out of the roll and hangs down one side of the hatch
        flap = mesh_panel(p, (0.45, 0.0, 0.62), (HX1 - 0.3, FW - 0.13, 2.06 - 0.31), wear=0.3)
        G.xform(flap.obj, rot=(0, -8, 0), pivot=(HX1 - 0.1, FW - 0.13, 2.06))
    # price board (chalk) in a timber frame on the right of the hatch
    bx, bz = 1.05, 1.55
    plate(p, 0.62, 0.71, (bx, FW - t / 2 - 0.012, bz), atlas("price"), t=0.012, wear=0.2)
    for sz in (-1, 1):
        p.box((0.7, 0.03, 0.04), (bx, FW - t / 2 - 0.02, bz + sz * 0.375), C.WOOD, bevel=0.004, grain="X")
    for sx in (-1, 1):
        p.box((0.04, 0.03, 0.79), (bx + sx * 0.33, FW - t / 2 - 0.02, bz), C.WOOD, bevel=0.004, grain="Z")
    p.box((0.5, 0.05, 0.015), (bx, FW - t / 2 - 0.04, bz - 0.4), C.WOOD, bevel=0.003, grain="X")
    p.box((0.05, 0.012, 0.012), (bx - 0.1, FW - t / 2 - 0.045, bz - 0.386), C.WHITE, bevel=0.002)
    # Program roundel plate and data plate
    plate(p, 0.42, 0.42, (-0.3, FW - t / 2 - 0.004, 0.62), atlas("emblem"), t=0.006, mat=C.PRINT)
    for sx in (-1, 1):
        for sz in (-1, 1):
            bolt(p, (-0.3 + sx * 0.18, FW - t / 2 - 0.009, 0.62 + sz * 0.18), r=0.008)
    plate(p, 0.24, 0.12, (XR + 0.003, 0.3, 1.5), atlas("plate"), t=0.004, facing="+X")
    # inside: right-wall shelving unit with stock
    sx0, sx1, sy0, sy1 = 1.02, 1.46, -0.44, 0.74
    for x in (sx0 + 0.015, sx1 - 0.015):
        for y in (sy0 + 0.015, sy1 - 0.015):
            p.box((0.03, 0.03, 1.95), (x, y, 0.975), C.SHELF, bevel=0.0)
    r = p.rng("stock")
    vr = p.vrng("stock")
    levels = (0.1, 0.55, 1.0, 1.45, 1.9)
    for z in levels:
        p.box((sx1 - sx0, sy1 - sy0, 0.02), ((sx0 + sx1) / 2, (sy0 + sy1) / 2, z), C.SHELF, bevel=0.0, grain="Y")
    for li, z in enumerate(levels[:-1]):
        y = sy0 + 0.04
        zt = z + 0.01
        while y < sy1 - 0.12:
            kind = r.randrange(4)
            gone = worn and vr.random() < 0.4
            if kind == 0:  # tins in a block
                for i in range(3):
                    if not gone:
                        tin(p, sx0 + 0.1 + i * 0.09, y + 0.045, zt)
                        if i < 2:
                            tin(p, sx0 + 0.145 + i * 0.09, y + 0.045, zt + 0.11)
                y += 0.12
            elif kind == 1:
                if not gone:
                    ammo_can(p, ((sx0 + sx1) / 2 + 0.02, y + 0.08, zt), 90)
                y += 0.18
            elif kind == 2:
                bw = r.uniform(0.18, 0.3)
                bh = min(0.4, r.uniform(0.15, 0.3))
                if not gone:
                    p.box((0.32, bw, bh), ((sx0 + sx1) / 2 + 0.02, y + bw / 2, zt + bh / 2), C.CARD, bevel=0.004)
                y += bw + 0.02
            else:  # water jugs
                if not gone:
                    p.rbox((0.2, 0.12, 0.28), ((sx0 + sx1) / 2, y + 0.07, zt + 0.14), C.WHITE, radius=0.02, inner=(1, 1, 1))
                y += 0.16
    # crates in the front-right corner and under the counter at the left
    crate(p, (0.34, 0.5, 0.3), (0.8, -0.24, 0.0))
    crate(p, (0.3, 0.42, 0.26), (0.8, -0.25, 0.3), yaw=4 if not worn else 14)
    crate(p, (0.36, 0.3, 0.3), (-1.27, -0.36, 0.0))
    p.rbox((0.17, 0.33, 0.46), (-1.25, 0.1, 0.23), C.OLIVE, radius=0.03, inner=(1, 1, 1))  # jerrycan
    p.box((0.03, 0.12, 0.03), (-1.25, 0.1, 0.475), C.OLIVE, bevel=0.005)
    # high back shelf: tins, a field radio, a first-aid box (above head height)
    p.box((1.9, 0.22, 0.02), (-0.3, BW - t - 0.11, 1.98), C.WOOD, bevel=0.003, grain="X")
    for x in (-1.1, 0.5):
        p.prism([(BW - t, 1.97), (BW - t - 0.2, 1.97), (BW - t, 1.8)], 0.03, C.OLIVE, plane="YZ", offset=x - 0.015)
    for i in range(6):
        if worn and vr.random() < 0.5:
            continue
        tin(p, -1.15 + i * 0.09, BW - t - 0.1, 1.99)
    p.box((0.32, 0.16, 0.22), (-0.35, BW - t - 0.1, 2.1), C.OLIVE, bevel=0.01)
    p.cyl(0.03, 0.02, (-0.28, BW - t - 0.19, 2.12), C.PL_BLACK, axis="Y", segs=8)
    rod(p, (-0.47, BW - t - 0.1, 2.2), (-0.5, BW - t - 0.1, 2.5), 0.004, C.PL_BLACK, segs=4)
    if not worn:
        p.box((0.26, 0.14, 0.14), (0.25, BW - t - 0.1, 2.06), C.WHITE, bevel=0.008)
        p.box((0.05, 0.002, 0.016), (0.25, BW - t - 0.172, 2.06), C.RED, bevel=0.0)
        p.box((0.016, 0.002, 0.05), (0.25, BW - t - 0.172, 2.06), C.RED, bevel=0.0)
    # counter top: ledger, cash tin
    if not worn:
        p.box((0.3, 0.22, 0.03), (HX0 + 0.3, -0.55, HZ0 + 0.015), C.CARD, bevel=0.004)
        p.box((0.31, 0.225, 0.006), (HX0 + 0.3, -0.55, HZ0 + 0.033), C.BLACK, bevel=0.002)
    else:
        sh = p.box((0.21, 0.28, 0.0015), (HX0 + 0.35, -0.6, HZ0 + 0.002), "furn_paper_notes", bevel=0.0, uv="planar",
                   uv_axis="Z", rect=core.note_rect(1))
        G.xform(sh.obj, rot=(0, 0, 23), pivot=(HX0 + 0.35, -0.6, HZ0))
    p.box((0.26, 0.18, 0.09), (HX1 - 0.22, -0.5, HZ0 + 0.045), C.OLIVE, bevel=0.006)
    # work lamp hanging inside (the prop's light)
    lx, ly = TRADER_SPOT[0], 0.1
    rod(p, (lx, ly, roof_z(ly) - 0.07), (lx, ly, 2.27), 0.005, C.PL_BLACK, segs=4)
    p.lathe([(0.012, 0.0), (0.03, -0.02), (0.11, -0.1), (0.1, -0.105)], (lx, ly, 2.28), C.OLIVE, segs=12, cap_bottom=False)
    if worn:
        p.cyl(0.035, 0.05, (lx, ly, 2.2), C.BULB, segs=8)
    else:
        p.lathe([(0.0, 0.0), (0.03, -0.02), (0.035, -0.06), (0.0, -0.09)], (lx, ly, 2.25), C.BULB, segs=8)
    # doorway curtain bunched back, on its rod
    rod(p, (XL - 0.03, DY0, DZ - 0.04), (XL - 0.03, DY1, DZ - 0.04), 0.012, C.GALV, segs=6)
    p.rbox((0.07, 0.16, DZ - 0.12), (XL - 0.04, DY1 - 0.1, (DZ - 0.04) / 2 + 0.04), C.CANVAS, radius=0.03,
           inner=(1, 2, 4), wrinkle=0.012, seed=p.seed)
    # colliders: walls, counter, roof, shelving (the standing box stays free)
    p.collider((0, -0.66, 0.53), (3.0, 0.24, 1.06))
    p.collider(((XL + HX0) / 2, FW, (HZ0 + H) / 2), (HX0 - XL, 0.05, H - HZ0))
    p.collider(((HX1 + XR) / 2, FW - 0.02, (HZ0 + H) / 2), (XR - HX1, 0.09, H - HZ0))
    p.collider((cx, FW - 0.08, (HZ1 + H) / 2 + 0.05), (HX1 - HX0, 0.2, H - HZ1 + 0.1))
    p.collider((XL + 0.02, (FW + DY0) / 2, H / 2), (0.06, DY0 - FW, H))
    p.collider((XL + 0.02, (DY1 + BW) / 2, H / 2), (0.06, BW - DY1, H))
    p.collider((XR - 0.02, (FW + BW) / 2, H / 2), (0.06, BW - FW, H))
    p.collider((0, BW - 0.02, H / 2), (3.0, 0.06, H))
    p.collider((0, 0.015, 2.55), (3.25, 1.88, 0.14))
    p.collider(((sx0 + sx1) / 2, (sy0 + sy1) / 2, 0.98), (sx1 - sx0, sy1 - sy0, 1.96))
    p.collider((0.8, -0.24, 0.28), (0.34, 0.5, 0.56))
    p.collider((-1.27, -0.2, 0.25), (0.36, 0.7, 0.5))


# ================================================================================================
# 2. contracts board
# ================================================================================================

def waystation_board(p: Prop) -> None:
    """Contracts notice board (2.3 x 2.45 x 0.6): two weathered 4x4 posts in concrete collars, a plywood
    board framed in battens with the yellow CONTRACTS header above it, a small tin roof. Pinned: the valley
    map with red rings, a Program bulletin, a contract form, a bounty sheet, a handwritten list, slips.
    Worn: sheets gone or curling, one blown down to the foot of the board, a rusted roof."""
    worn = p.worn
    for sx in (-1, 1):
        p.box((0.1, 0.1, 2.32), (sx * 1.0, 0.06, 1.16), C.WOOD, bevel=0.006, grain="Z")
        p.cyl(0.13, 0.1, (sx * 1.0, 0.06, 0.05), C.CONCRETE, segs=10)
    p.box((1.94, 0.018, 1.18), (0, 0.0, 1.38), C.PLY, bevel=0.002, grain="X")
    p.box((2.1, 0.03, 0.06), (0, -0.02, 0.76), C.WOOD, bevel=0.004, grain="X")
    p.box((2.1, 0.03, 0.06), (0, -0.02, 2.0), C.WOOD, bevel=0.004, grain="X")
    for sx in (-1, 1):
        p.box((0.06, 0.03, 1.18), (sx * 0.94, -0.02, 1.38), C.WOOD, bevel=0.004, grain="Z")
    # ledge for chalk / pins
    p.box((1.9, 0.08, 0.02), (0, -0.06, 0.8), C.WOOD, bevel=0.003, grain="X")
    # header strip on its backing
    p.box((1.94, 0.018, 0.26), (0, 0.0, 2.16), C.PLY, bevel=0.002, grain="X")
    plate(p, 1.5, 0.25, (0, -0.012, 2.16), atlas("header"), t=0.003)
    # roof: two rafters on the post tops, one sheet sloping back
    for sx in (-1, 1):
        bar(p, (sx * 1.0, -0.3, 2.37), (sx * 1.0, 0.36, 2.29), 0.06, 0.08, C.WOOD, grain="Y")
    roof_sheet(p, -1.17, 1.17, -0.33, 2.42, 0.38, 2.33, C.ROOF_RUST if worn else C.ROOF, lift=0.0)
    # pinned paper
    r = p.rng("sheets")
    vr = p.vrng("sheets")
    items = [("map", -0.5, 1.4, 0.52, 0.52, -2.0), ("sheet0", 0.06, 1.64, 0.21, 0.28, 3.0), ("sheet1", 0.34, 1.6, 0.21, 0.28, -4.0),
             ("sheet2", 0.64, 1.63, 0.21, 0.28, 2.5), ("sheet3", 0.12, 1.15, 0.21, 0.28, -3.0), ("note0", 0.42, 1.2, 0.13, 0.13, 6.0),
             ("note1", 0.6, 1.12, 0.12, 0.12, -5.0), ("note2", 0.8, 1.3, 0.13, 0.13, 3.0), ("note3", -0.84, 1.0, 0.13, 0.13, -8.0),
             ("sheet1", 0.72, 1.0, 0.21, 0.28, 4.0)]
    fallen = None
    for k, (cell, x, z, w, h, ang) in enumerate(items):
        y = -0.011 - (k % 3) * 0.0012
        if worn:
            q = vr.random()
            if q < 0.18:
                continue
            if q < 0.28 and fallen is None:
                fallen = (cell, w, h)
                continue
        tip = (vr.uniform(6, 14) if worn and vr.random() < 0.35 else 0.0)
        plate(p, w, h, (x, y - (0.02 if tip else 0.0), z), atlas(cell), t=0.0015, rot=(tip, ang, 0), wear=0.1)
        pin = (C.RED, C.STRAP)[r.randrange(2)]
        a = math.radians(ang)
        p.cyl(0.007, 0.012, (x - math.sin(a) * (h / 2 - 0.02), y - 0.006, z + math.cos(a) * (h / 2 - 0.02)), pin, axis="Y", segs=6)
    if fallen:
        cell, w, h = fallen
        plate(p, w, h, (0.35, -0.35, 0.002), atlas(cell), t=0.0015, rot=(-90, 0, 27), wear=0.1)
    p.collider((0, 0.03, 1.2), (2.1, 0.16, 2.4))


# ================================================================================================
# 3. guard tower
# ================================================================================================

def waystation_tower(p: Prop) -> None:
    """Guard tower (3.3 x 7.6 x 3.4): four splayed timber legs on concrete pads with hazard-striped feet, two
    tiers of X bracing, a plank deck at 4.5 m with an olive corrugated skirt and three courses of sandbags
    behind it on the front and sides, roof posts carrying a tin roof at ~7.1 m, a whip antenna, a floodlight
    on the front-right post with its cable, a steel ladder up the back to the gap in the skirt.
    Worn: slumped and missing bags, a lifted rusty roof sheet, a snapped brace, a missing rung, the lamp's
    lens broken."""
    worn = p.worn
    DZ = 4.5
    B, T_ = 1.5, 1.32
    r = p.rng("tower")
    vr = p.vrng("tower")

    def leg_xy(sx, sy, z):
        f = z / DZ
        return (sx * (B + (T_ - B) * f), sy * (B + (T_ - B) * f))

    for sx in (-1, 1):
        for sy in (-1, 1):
            p.box((0.46, 0.46, 0.14), (sx * B, sy * B, 0.07), C.CONCRETE, bevel=0.01)
            x0, y0 = leg_xy(sx, sy, 0.14)
            x1, y1 = leg_xy(sx, sy, 0.9)
            x2, y2 = leg_xy(sx, sy, DZ)
            bar(p, (x0, y0, 0.14), (x1, y1, 0.9), 0.155, 0.155, C.HAZ, bevel=0.006)
            bar(p, (x1, y1, 0.9), (x2, y2, DZ - 0.08), 0.15, 0.15, C.WOOD, bevel=0.006)
            p.box((0.13, 0.13, 6.95 - DZ), (sx * T_, sy * T_, (DZ + 6.95) / 2), C.WOOD, bevel=0.006, grain="Z")
    # bracing: girts and X braces on every face
    broken = (1, 0) if worn else None
    for face in range(4):
        for tier, (za, zb) in enumerate(((0.5, 2.45), (2.45, DZ - 0.15))):
            if face == 0:
                ends = [((-1, -1), (1, -1))]
            elif face == 1:
                ends = [((1, -1), (1, 1))]
            elif face == 2:
                ends = [((1, 1), (-1, 1))]
            else:
                ends = [((-1, 1), (-1, -1))]
            (a, b) = ends[0]
            pa0, pb0 = leg_xy(*a, za), leg_xy(*b, za)
            pa1, pb1 = leg_xy(*a, zb), leg_xy(*b, zb)
            inset = 0.09
            bar(p, (pa1[0], pa1[1], zb), (pb1[0], pb1[1], zb), 0.07, 0.12, C.WOOD, grain="auto")
            for k, (s, e) in enumerate((((pa0, za), (pb1, zb)), ((pb0, za), (pa1, zb)))):
                (sp, sz), (ep, ez) = s, e
                sv = Vector((sp[0], sp[1], sz))
                ev = Vector((ep[0], ep[1], ez))
                n = Vector((0, 0, 0))
                mid = (sv + ev) / 2
                n.x, n.y = mid.x * inset / max(1e-6, abs(mid.x) + abs(mid.y)), mid.y * inset / max(1e-6, abs(mid.x) + abs(mid.y))
                if broken and face == broken[0] and tier == 0 and k == broken[1]:
                    # snapped: the lower half hangs from its bolt
                    mv = (sv + ev) / 2
                    bar(p, mv + n, ev + n, 0.05, 0.1, C.WOOD)
                    piece = bar(p, sv + n, mv + n, 0.05, 0.1, C.WOOD)
                    G.xform(piece.obj, matrix=Matrix.Rotation(math.radians(-38), 4, (ev - sv).cross(Vector((0, 0, 1))).normalized()),
                            pivot=mv + n)
                    continue
                bar(p, sv + n, ev + n, 0.05, 0.1, C.WOOD)
    # deck: bearers and planks
    for y in (-1.25, 0.0, 1.25):
        p.box((2.8, 0.1, 0.14), (0, y, DZ - 0.13), C.WOOD, bevel=0.004, grain="X")
    npl = 14
    for k in range(npl):
        y = -1.43 + (k + 0.5) * 2.86 / npl
        p.box((2.9, 2.86 / npl - 0.012, 0.05), (r.uniform(-0.01, 0.01), y, DZ - 0.035), C.WOOD, bevel=0.003, grain="X")
    # corrugated skirt (front, sides, back either side of the ladder gap) with its top rail
    SZ0, SZ1 = DZ - 0.32, DZ + 0.45
    E = 1.47
    sheet_box(p, -E, E, -E - 0.02, -E, SZ0, SZ1)
    for sx in (-1, 1):
        sheet_box(p, E if sx > 0 else -E - 0.02, E + 0.02 if sx > 0 else -E, -E, E, SZ0, SZ1)
        sheet_box(p, 0.42 if sx > 0 else -E, E if sx > 0 else -0.42, E, E + 0.02, SZ0, SZ1)
    for (a, b) in (((-E, -E - 0.04), (E, -E - 0.04)), ((-E - 0.04, -E), (-E - 0.04, E)), ((E + 0.04, -E), (E + 0.04, E)),
                   ((-E, E + 0.04), (-0.42, E + 0.04)), ((0.42, E + 0.04), (E, E + 0.04))):
        bar(p, (a[0], a[1], SZ1 + 0.03), (b[0], b[1], SZ1 + 0.03), 0.06, 0.12, C.WOOD, grain="auto", bevel=0.004)
    plate(p, 0.55, 0.55, (0, -E - 0.024, DZ + 0.06), atlas("emblem"), t=0.006)
    # sandbags inside the skirt: three courses front and sides
    bh = 0.17
    for row in range(3):
        z = DZ + row * bh
        off = 0.15 if row % 2 else 0.0
        skip_f = tuple(i for i in range(5) if worn and row == 2 and vr.random() < 0.35)
        sandbag_row(p, (-1.4 + off, -1.28, z), 2.65 - off, 5 if not off else 4, mat=C.BAG_TAN if row != 1 else C.BAG_OLIVE,
                    key=f"bf{row}", slump=0.6 if worn else 0.0, skip=skip_f)
        for sx in (-1, 1):
            skip_s = tuple(i for i in range(4) if worn and row == 2 and vr.random() < 0.3)
            sandbag_row(p, (sx * 1.28, -1.0 + off, z), 2.3 - off, 4, yaw=90, mat=C.BAG_OLIVE if row != 1 else C.BAG_TAN,
                        key=f"bs{row}{sx}", slump=0.6 if worn else 0.0, skip=skip_s)
    # roof: rafters and two sheets, the antenna
    RZ = 6.95
    for sx in (-1, 1):
        bar(p, (sx * T_, -1.55, RZ + 0.12), (sx * T_, 1.55, RZ - 0.06), 0.08, 0.14, C.WOOD, grain="Y")
    for sy in (-1, 1):
        p.box((2.8, 0.1, 0.12), (0, sy * T_, RZ + 0.03 - sy * 0.08), C.WOOD, bevel=0.004, grain="X")
    roof_sheet(p, -1.65, 0.02, -1.62, RZ + 0.2, 1.62, RZ + 0.02, C.ROOF_RUST if worn else C.ROOF)
    roof_sheet(p, -0.02, 1.65, -1.62, RZ + 0.206, 1.62, RZ + 0.026, C.ROOF_RUST if worn else C.ROOF, lift=7.0 if worn else 0.0)
    rod(p, (-1.25, 1.3, RZ + 0.1), (-1.25, 1.3, 7.62), 0.008, C.PL_BLACK, segs=5)
    p.cyl(0.025, 0.08, (-1.25, 1.3, RZ + 0.14), C.PL_BLACK, segs=6)
    # floodlight on the front-right post
    lamp_head(p, (T_ - 0.05, -T_ - 0.28, 6.55), tilt=28, yaw=-20, broken=worn)
    bar(p, (T_, -T_ - 0.06, 6.38), (T_ - 0.05, -T_ - 0.28, 6.38), 0.05, 0.05, C.OLIVE)
    p.tube([(T_ + 0.08, -T_ - 0.2, 6.5), (T_ + 0.09, -T_ - 0.05, 6.4), (T_ + 0.08, -T_ + 0.0, 6.2), (T_ + 0.08, -T_ + 0.0, DZ + 0.5)],
           0.01, C.RUBBER, segs=4, fillet_r=0.05, wear=0.2)
    # ladder up the back
    LY = 1.66
    for sx in (-1, 1):
        p.box((0.05, 0.03, DZ + 0.95), (sx * 0.24, LY, (DZ + 0.95) / 2), C.OLIVE, bevel=0.004)
        bar(p, (sx * 0.24, LY, DZ - 0.1), (sx * 0.24, E + 0.02, DZ - 0.1), 0.04, 0.04, C.OLIVE)
        bar(p, (sx * 0.24, LY, 2.45), (sx * 0.24, B + (T_ - B) * 2.45 / DZ + 0.06, 2.45), 0.04, 0.04, C.OLIVE)
    gone = int(vr.uniform(4, 10)) if worn else -1
    for k in range(int((DZ + 0.6) / 0.3)):
        if k == gone:
            continue
        p.cyl(0.015, 0.48, (0, LY, 0.3 + k * 0.3), C.STEEL, axis="X", segs=6)
    # colliders
    p.collider((0, 0, DZ + 0.15), (3.0, 3.0, 0.9))
    p.collider((0, 0, RZ + 0.1), (3.3, 3.3, 0.25))
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.collider((sx * 1.41, sy * 1.41, DZ / 2), (0.2, 0.2, DZ))
            p.collider((sx * T_, sy * T_, (DZ + RZ) / 2), (0.14, 0.14, RZ - DZ))
    p.collider((0, LY, (DZ + 0.95) / 2), (0.55, 0.08, DZ + 0.95))


# ================================================================================================
# 4. hesco barrier
# ================================================================================================

def _hesco_cell(p: Prop, cx: float, w: float, d: float, h: float, fill: float, *, key: str, ends=(False, False),
                torn: bool = False) -> None:
    """One cage: geotextile liner bulging between the mesh walls, earth fill on top, welded mesh panels,
    coil-hinge corner rods and the top rim."""
    p.rbox((w - 0.07, d - 0.07, fill), (cx, 0, fill / 2), C.LINER, radius=0.04, inner=(3, 3, 2), bulge=(0.025, 0.025, 0.0),
           wrinkle=0.006, seed=p.seed + int(cx * 10), wear=0.4)
    p.rbox((w - 0.1, d - 0.1, 0.1), (cx, 0, fill - 0.03), C.EARTH, radius=0.04, inner=(2, 2, 1), wrinkle=0.02,
           seed=p.seed + 3 + int(cx * 10), bulge=(0, 0, 0.03), wear=0.2)
    for sy in (-1, 1):
        mesh_panel(p, (w - 0.012, 0.0, h), (cx, sy * d / 2, h / 2), wear=0.5)
    for sx, on in zip((-1, 1), ends):
        if on:
            mesh_panel(p, (0.0, d - 0.012, h), (cx + sx * w / 2, 0, h / 2), wear=0.5)
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.cyl(0.007, h, (cx + sx * (w / 2 - 0.004), sy * (d / 2 - 0.004), h / 2), C.STEEL, segs=4, wear=0.6)
    for sy in (-1, 1):
        rod(p, (cx - w / 2, sy * d / 2, h), (cx + w / 2, sy * d / 2, h), 0.005, C.STEEL, segs=4)
    if torn:
        # a slit in the liner face with earth bulging out of it, a spill at its foot
        p.rbox((0.3, 0.08, 0.2), (cx + 0.1, -d / 2 + 0.02, 0.55), C.EARTH, radius=0.04, inner=(2, 1, 1), wrinkle=0.02, seed=p.seed + 9)
        p.rbox((0.6, 0.35, 0.12), (cx + 0.1, -d / 2 - 0.12, 0.05), C.EARTH, radius=0.05, inner=(2, 2, 1), wrinkle=0.03,
               seed=p.seed + 10, bulge=(0, 0, 0.05))


def waystation_barrier(p: Prop) -> None:
    """Hesco-style barrier segment (3.0 x 1.9 x 1.1): three earth-filled mesh cages lined with geotextile,
    1.37 m tall, a coil of concertina wire along the top on U-pickets. Worn: the fill settled, a torn liner
    spilling earth, the wire sagging. Destroyed: the right cell has burst - its front panel thrown down, the
    side panel leaning out, the liner slumped and the earth spilled forward; the wire is cut there and its
    tail trails to the ground."""
    worn, dest = p.worn, p.destroyed
    w, d, h = 1.0, 1.06, 1.37
    fills = (1.3, 1.24 if worn else 1.3, 1.28)
    if dest:
        fills = (1.26, 1.12, 0.0)
    for i, cx in enumerate((-1.0, 0.0, 1.0)):
        if dest and i == 2:
            continue
        _hesco_cell(p, cx, w, d, h, fills[i], key=f"cell{i}", ends=(i == 0, i == 2), torn=worn and i == 1)
    if dest:
        cx = 1.0
        p.rbox((w + 0.1, d + 0.2, 0.55), (cx, -0.05, 0.27), C.LINER, radius=0.08, inner=(3, 3, 2), bulge=(0.06, 0.08, 0.0),
               wrinkle=0.03, seed=p.seed + 21, sag=0.12, sag_r=0.4)
        p.rbox((1.5, 1.0, 0.42), (cx + 0.05, -0.85, 0.12), C.EARTH, radius=0.12, inner=(3, 3, 1), wrinkle=0.05, seed=p.seed + 22,
               bulge=(0, 0, 0.12))
        p.rbox((0.7, 0.5, 0.3), (cx - 0.2, -0.3, 0.42), C.EARTH, radius=0.1, inner=(2, 2, 1), wrinkle=0.04, seed=p.seed + 23,
               bulge=(0, 0, 0.08))
        fp = mesh_panel(p, (w - 0.012, 0.0, h), (cx, -d / 2, h / 2), wear=0.8)
        G.xform(fp.obj, rot=(72, 0, 4), pivot=(cx, -d / 2, 0.0))
        G.xform(fp.obj, loc=(0, 0, 0.12))
        bp = mesh_panel(p, (w - 0.012, 0.0, h), (cx, d / 2, h / 2), wear=0.8)
        G.xform(bp.obj, rot=(-14, 0, 0), pivot=(cx, d / 2, 0.0))
        sp = mesh_panel(p, (0.0, d - 0.012, h), (cx + w / 2, 0, h / 2), wear=0.8)
        G.xform(sp.obj, rot=(0, 34, 0), pivot=(cx + w / 2, 0, 0.0))
        for sy in (-1, 1):
            st = p.cyl(0.007, h, (cx + w / 2 - 0.004, sy * (d / 2 - 0.004), h / 2), C.STEEL, segs=4, wear=0.8)
            G.xform(st.obj, rot=(0, 34, 0), pivot=(cx + w / 2, 0, 0.0))
    # wire: U-pickets and the coil
    R = 0.24
    zc = h + R - 0.02
    for x in ((-1.45, 0.45) if dest else (-1.45, 1.45)):
        bar(p, (x, 0.0, h - 0.45), (x, 0.0, h + 2 * R + 0.02), 0.04, 0.02, C.OLIVE, bevel=0.002)
    if dest:
        coil(p, (-1.5, 0, zc), (0.5, 0, zc), R, 0.17, key="wire", sag=0.04)
        coil(p, (0.55, -0.1, zc - 0.1), (1.6, -0.9, 0.25), R * 0.8, 0.22, key="tail", wobble=0.15)
    else:
        coil(p, (-1.5, 0, zc), (1.5, 0, zc), R, 0.17 if not worn else 0.2, key="wire", sag=0.12 if worn else 0.02,
             wobble=0.12 if worn else 0.05)
    if dest:
        p.collider((-0.5, 0, h / 2), (2.0, d, h))
        p.collider((1.0, -0.35, 0.3), (1.1, 1.6, 0.6))
    else:
        p.collider((0, 0, h / 2), (3.0, d, h))
        p.collider((0, 0, zc), (3.0, 2 * R, 2 * R))


# ================================================================================================
# 5. boom gate
# ================================================================================================

def waystation_gate(p: Prop) -> None:
    """Checkpoint boom gate (4.55 x 1.27 x 0.7): a Program-yellow pedestal on a concrete pad with an amber
    beacon, a hazard-striped box-section arm on its pivot hub, steel counterweight plates on the short tail,
    a rest fork at the far end and the HALT / SHOW PASS plate hanging from the arm on two chains.
    Worn: the arm sags off the fork, the beacon lens is smashed, the plate hangs from one chain."""
    worn = p.worn
    PX, PZ, AY = -1.85, 0.95, -0.24
    p.box((0.7, 0.7, 0.15), (PX, 0, 0.075), C.CONCRETE, bevel=0.012)
    p.box((0.38, 0.32, 0.95), (PX, 0, 0.15 + 0.475), C.YELLOW, bevel=0.012)
    p.box((0.3, 0.004, 0.55), (PX, -0.162, 0.6), C.BLACK, bevel=0.0)
    p.box((0.42, 0.36, 0.03), (PX, 0, 1.115), C.YELLOW, bevel=0.006)
    for sx in (-1, 1):
        for sy in (-1, 1):
            bolt(p, (PX + sx * 0.28, sy * 0.28, 0.155), axis="Z", r=0.015)
    plate(p, 0.2, 0.1, (PX, -0.164, 0.3), atlas("plate"), t=0.003)
    # beacon
    p.cyl(0.06, 0.03, (PX + 0.08, 0, 1.145), C.BLACK, segs=10)
    if worn:
        p.lathe([(0.05, 0.0), (0.05, 0.03), (0.035, 0.045)], (PX + 0.08, 0, 1.16), C.LENS_A, segs=10, cap_top=False)
    else:
        p.lathe([(0.05, 0.0), (0.05, 0.08), (0.03, 0.11), (0.0, 0.12)], (PX + 0.08, 0, 1.16), C.LENS_A, segs=10)
    # pivot hub
    p.cyl(0.09, 0.08, (PX, -0.2, PZ), C.BLACK, axis="Y", segs=12)
    arm = []
    arm.append(p.box((4.0, 0.09, 0.11), (PX + 0.1 + 2.0, AY, PZ), C.HAZ, bevel=0.008, grain="X"))
    arm.append(p.box((0.12, 0.004, 0.08), (PX + 4.05, AY - 0.046, PZ), "lens_red", bevel=0.0))
    arm.append(p.box((0.5, 0.08, 0.1), (PX - 0.15, AY, PZ), C.OLIVE, bevel=0.006, grain="X"))
    for k in range(4):
        arm.append(p.box((0.05, 0.16, 0.28), (PX - 0.2 - k * 0.055, AY, PZ - 0.02), C.BLACK, bevel=0.004))
    arm.append(p.cyl(0.012, 0.25, (PX - 0.28, AY, PZ - 0.02), C.STEEL, axis="X", segs=6))
    # HALT plate on two chains
    HX = 0.45
    hang = [p.box((0.52, 0.006, 0.27), (HX, AY - 0.06, PZ - 0.32), C.YELLOW, bevel=0.002)]
    hang.append(plate(p, 0.5, 0.25, (HX, AY - 0.064, PZ - 0.32), atlas("halt"), t=0.002, back=atlas("halt")))
    links = []
    for sx in (-1, 1):
        links.append(rod(p, (HX + sx * 0.2, AY - 0.05, PZ - 0.185), (HX + sx * 0.2, AY - 0.05, PZ - 0.05), 0.004, C.CHAIN, segs=4))
    if worn:
        p.remove([links[1]])
        place(hang, Matrix.Translation((HX - 0.2, AY - 0.06, PZ - 0.185)) @ Matrix.Rotation(math.radians(-28), 4, "Y")
              @ Matrix.Translation((-(HX - 0.2), -(AY - 0.06), -(PZ - 0.185))))
    arm += hang + links[:1 if worn else 2]
    if worn:
        place(arm, Matrix.Translation((PX, AY, PZ)) @ Matrix.Rotation(math.radians(-1.6), 4, "Y") @ Matrix.Translation((-PX, -AY, -PZ)))
    # rest fork
    RX = 2.05
    p.box((0.3, 0.3, 0.08), (RX, AY, 0.04), C.CONCRETE, bevel=0.01)
    p.box((0.07, 0.07, 0.78), (RX, AY, 0.08 + 0.39), C.YELLOW, bevel=0.006)
    p.box((0.05, 0.2, 0.03), (RX, AY, 0.85), C.YELLOW, bevel=0.004)
    for sy in (-1, 1):
        p.box((0.05, 0.02, 0.14), (RX, AY + sy * 0.09, 0.92), C.YELLOW, bevel=0.003)
    p.box((0.05, 0.12, 0.012), (RX, AY, 0.871), C.RUBBER, bevel=0.0)
    p.collider((PX, 0, 0.6), (0.7, 0.7, 1.2))
    p.collider((0.2, AY, PZ), (4.1, 0.12, 0.14))
    p.collider((RX, AY, 0.5), (0.3, 0.3, 1.0))


# ================================================================================================
# 6. the sign
# ================================================================================================

def waystation_sign(p: Prop) -> None:
    """WAYSTATION 9 sign (3.0 x 2.8 x 0.4): a printed steel face (atlas sign / sign_worn: stencils, roundel,
    hazard band, rust runs) on an olive backing with two stiffener rails, bolted to two olive box posts in
    concrete footings; bolt heads where the print's bolts are. Worn: the weathered print, the panel dropped
    on one side where a bolt sheared, a bent bottom corner."""
    worn = p.worn
    W, H, Z0 = 2.9, 1.45, 1.27
    for sx in (-1, 1):
        p.box((0.1, 0.1, Z0 + H + 0.05), (sx * 1.15, 0.07, (Z0 + H + 0.05) / 2), C.OLIVE, bevel=0.005)
        p.cyl(0.18, 0.12, (sx * 1.15, 0.07, 0.06), C.CONCRETE, segs=12, bevel=0.01)
    panel = []
    panel.append(p.box((W, 0.02, H), (0, 0.0, Z0 + H / 2), C.OLIVE, bevel=0.004, grain="X"))
    panel.append(plate(p, W - 0.004, H - 0.004, (0, -0.0115, Z0 + H / 2), atlas("sign_worn" if worn else "sign", 0.5), t=0.003,
                       wear=0.6))
    for z in (Z0 + 0.35, Z0 + H - 0.35):
        panel.append(p.box((W - 0.1, 0.04, 0.06), (0, 0.03, z), C.OLIVE, bevel=0.004, grain="X"))
    for i, bx in enumerate((40, 512, 984)):
        for j, by in enumerate((34, 482)):
            if worn and i == 2 and j == 0:
                continue
            x = (bx / 1024 - 0.5) * W
            z = Z0 + H - by / 512 * H
            panel.append(bolt(p, (x, -0.019, z), r=0.013))
    if worn:
        place(panel, Matrix.Translation((-1.15, 0, Z0 + 0.2)) @ Matrix.Rotation(math.radians(1.8), 4, "Y")
              @ Matrix.Translation((1.15, 0, -(Z0 + 0.2))))
    p.collider((0, 0.03, Z0 + H / 2), (W, 0.12, H))
    for sx in (-1, 1):
        p.collider((sx * 1.15, 0.07, (Z0 + H) / 2), (0.14, 0.14, Z0 + H))


# ================================================================================================
# 7. floodlight
# ================================================================================================

def _generator(p: Prop, c, worn: bool) -> list:
    """Portable generator (0.62 x 0.46 x 0.52) in its tube frame: engine, olive tank, control panel facing -Y,
    muffler, pull start; c = bottom centre."""
    x, y, z = c
    out = []
    W, D, H = 0.62, 0.46, 0.5
    for sx in (-1, 1):
        out.append(p.tube([(sx * W / 2, -D / 2, 0.0), (sx * W / 2, -D / 2, H), (sx * W / 2, D / 2, H), (sx * W / 2, D / 2, 0.0)],
                          0.014, C.BLACK, segs=6, fillet_r=0.05, cap=True, wear=1.0))
        for sy in (-1, 1):
            out.append(p.box((0.06, 0.06, 0.02), (sx * (W / 2 - 0.02), sy * (D / 2 - 0.02), 0.01), C.RUBBER, bevel=0.004))
    for sy in (-1, 1):
        out.append(rod(p, (-W / 2, sy * D / 2, 0.015), (W / 2, sy * D / 2, 0.015), 0.012, C.BLACK, segs=6))
        out.append(rod(p, (-W / 2, sy * D / 2, H), (W / 2, sy * D / 2, H), 0.012, C.BLACK, segs=6))
    out.append(p.box((0.36, 0.3, 0.3), (-0.06, 0.02, 0.2), C.BLACK, bevel=0.02))
    out.append(p.cyl(0.08, 0.16, (0.18, 0.02, 0.2), C.STEEL, axis="X", segs=10))
    out.append(p.rbox((0.5, 0.36, 0.13), (0, 0, H - 0.04), C.OLIVE if not worn else C.YELLOW, radius=0.04, inner=(1, 1, 1)))
    if not worn:
        out.append(p.cyl(0.03, 0.02, (0.12, 0.05, H + 0.03), C.BLACK, segs=8))
    out.append(p.box((0.3, 0.05, 0.22), (-0.08, -D / 2 + 0.05, 0.24), C.OLIVE, bevel=0.006))
    out.append(plate(p, 0.26, 0.19, (-0.08, -D / 2 + 0.022, 0.24), atlas("gen_panel"), t=0.003))
    out.append(p.cyl(0.05, 0.18, (-0.16, D / 2 - 0.08, 0.3), C.STEEL, axis="X", segs=8))
    out.append(p.cyl(0.03, 0.02, (-0.26, 0.02, 0.25), C.PL_BLACK, axis="X", segs=8))
    place(out, Matrix.Translation((x, y, z)))
    return out


FLOOD_SHIFT = -0.33  # pole x after centring the footprint (pole + generator)


def waystation_floodlight(p: Prop) -> None:
    """Floodlight pole (1.7 x 4.6 x 1.0): a steel pole on a base plate bolted to a concrete block, a crossarm
    carrying two floodlight heads aimed forward and down, the cable taped down the pole and run across the
    ground to the portable generator at the foot, a jerrycan beside it. Worn: one head knocked down on its
    yoke with a broken lens, the generator's tank swapped for a scavenged yellow one, the can on its side."""
    worn = p.worn
    p.box((0.5, 0.5, 0.3), (0, 0, 0.15), C.CONCRETE, bevel=0.015)
    p.box((0.3, 0.3, 0.02), (0, 0, 0.31), C.OLIVE, bevel=0.003)
    for sx in (-1, 1):
        for sy in (-1, 1):
            bolt(p, (sx * 0.11, sy * 0.11, 0.326), axis="Z", r=0.012)
    TOP = 4.25
    p.cyl(0.06, TOP - 0.32, (0, 0, (TOP + 0.32) / 2), C.OLIVE, segs=16, r_top=0.05, wear=0.3)
    p.cyl(0.055, 0.01, (0, 0, TOP + 0.005), C.OLIVE, segs=12)
    p.box((1.0, 0.07, 0.07), (0, 0, TOP - 0.1), C.OLIVE, bevel=0.005, grain="X")
    for sx in (-1, 1):
        bar(p, (0, 0, TOP - 0.45), (sx * 0.3, 0, TOP - 0.14), 0.03, 0.03, C.OLIVE)
    for sx in (-1, 1):
        knocked = worn and sx > 0
        lamp_head(p, (sx * 0.38, -0.02, TOP + 0.16 if not knocked else TOP - 0.3), tilt=22 if not knocked else 75,
                  yaw=sx * -8 if not knocked else 30, broken=knocked)
        if knocked:
            rod(p, (sx * 0.38, 0, TOP - 0.06), (sx * 0.38, -0.02, TOP - 0.3 + 0.2), 0.01, C.STEEL, segs=4)
    # cable: from the heads, down the pole, across the ground to the generator
    GX, GY = 0.85, 0.3
    p.tube([(-0.38, 0.1, TOP + 0.05), (0.0, 0.08, TOP - 0.15), (0.07, 0.07, TOP - 0.4), (0.07, 0.07, 0.6), (0.12, 0.12, 0.33),
            (0.26, 0.2, 0.31), (0.32, 0.26, 0.02), (0.5, 0.42, 0.012), (0.62, 0.4, 0.012), (GX - 0.18, GY + 0.05, 0.2),
            (GX - 0.12, GY - 0.05, 0.28)], 0.011, C.RUBBER, segs=5, fillet_r=0.06, wear=0.2)
    p.tube([(0.38, 0.1, TOP + 0.05), (0.0, 0.08, TOP - 0.15)], 0.01, C.RUBBER, segs=5, wear=0.2)
    for z in (1.0, 1.8, 2.6, 3.4):
        p.cyl(0.066, 0.03, (0, 0, z), C.PL_BLACK, segs=10)
    _generator(p, (GX, GY, 0.0), worn)
    if worn:
        jc = p.rbox((0.17, 0.35, 0.47), (0, 0, 0), C.OLIVE, radius=0.03, inner=(1, 1, 1))
        G.xform(jc.obj, rot=(0, 90, 20), loc=(0.55, -0.35, 0.085))
    else:
        p.rbox((0.17, 0.35, 0.47), (0.42, -0.25, 0.235), C.OLIVE, radius=0.03, inner=(1, 1, 1))
        p.box((0.03, 0.12, 0.03), (0.42, -0.25, 0.48), C.OLIVE, bevel=0.005)
    p.collider((0, 0, TOP / 2), (0.5, 0.5, TOP))
    p.collider((GX, GY, 0.26), (0.66, 0.5, 0.52))
    shift(p, FLOOD_SHIFT, 0.0)


# ================================================================================================
# 8. supply stack
# ================================================================================================

def waystation_supply_stack(p: Prop) -> None:
    """Program supply stack (1.7 x 1.5 x 1.1): a pallet carrying two drums (olive, yellow) at the back, a
    two-high wall of stencilled crates at the front under a yellow ratchet strap, a long crate across the
    drums with ammo cans on it, and a 30-gallon drum standing by the pallet. Worn: the long crate gone and its
    ammo cans tumbled, the strap cut and hanging, a dented drum."""
    worn = p.worn
    vr = p.vrng("stack")
    PX = -0.2
    z0 = pallet(p, PX, 0.0)
    drum(p, (PX - 0.3, 0.2, z0), mat=C.OLIVE, dent=0.03 if worn else 0.0)
    drum(p, (PX + 0.3, 0.2, z0), mat=C.YELLOW)
    for k, x in enumerate((PX - 0.3, PX + 0.3)):
        crate(p, (0.58, 0.4, 0.32), (x, -0.29, z0), yaw=(-2 + 3 * k))
        crate(p, (0.56, 0.38, 0.3), (x + 0.01, -0.29, z0 + 0.32), yaw=(1 - 2 * k) + (6 if worn and k else 0))
    ztop = z0 + 0.62
    if not worn:
        crate(p, (1.05, 0.48, 0.3), (PX, 0.18, z0 + 0.88 + 0.004))
        ammo_can(p, (PX - 0.25, 0.18, z0 + 1.184), 5)
        ammo_can(p, (PX + 0.15, 0.2, z0 + 1.184), -4)
        ammo_can(p, (PX - 0.1, -0.28, ztop), 88)
    else:
        ammo_can(p, (PX - 0.1, -0.28, ztop), 80)
        can = ammo_can(p, (0.0, 0.0, 0.0), 0)
        p.rotate(can, rot=(90, 0, 0))
        p.lay_on_floor(can, at=(0.15, -0.75), yaw=33)
    # strap over the front crates: down the front, across the top, ratchet buckle
    SX = PX + 0.02
    sy0, sy1 = -0.5, -0.08
    if not worn:
        p.box((0.05, 0.004, ztop - 0.02), (SX, sy0 - 0.003, (ztop + 0.02) / 2 + 0.01), C.STRAP, bevel=0.0)
        p.box((0.05, sy1 - sy0, 0.004), (SX, (sy0 + sy1) / 2, ztop + 0.002), C.STRAP, bevel=0.0)
        p.box((0.07, 0.03, 0.1), (SX, sy0 - 0.018, z0 + 0.35), C.STEEL, bevel=0.005)
    else:
        p.box((0.05, 0.004, 0.5), (SX, sy0 - 0.003, z0 + 0.15), C.STRAP, bevel=0.0)
        tail = p.box((0.05, 0.004, 0.45), (SX, sy0 - 0.003, ztop - 0.25), C.STRAP, bevel=0.0)
        G.xform(tail.obj, rot=(0, 12, 0), pivot=(SX, sy0, ztop))
    # the loose 30-gallon drum
    drum(p, (0.66, -0.12, 0.0), r=0.23, h=0.72, mat=C.OLIVE, dent=0.025 if worn else 0.0)
    p.collider((PX, 0.0, 0.7), (1.2, 1.0, 1.4))
    p.collider((0.66, -0.12, 0.36), (0.48, 0.48, 0.72))
    shift(p, -0.045, 0.0)
    del vr


# ================================================================================================
# registry
# ================================================================================================

BUILDERS = {
    "waystation_counter": waystation_counter,
    "waystation_board": waystation_board,
    "waystation_tower": waystation_tower,
    "waystation_barrier": waystation_barrier,
    "waystation_gate": waystation_gate,
    "waystation_sign": waystation_sign,
    "waystation_floodlight": waystation_floodlight,
    "waystation_supply_stack": waystation_supply_stack,
}


def build(params: dict, outputs: list[str]) -> None:
    core.build_variants(params, outputs, BUILDERS[params.get("builder", params["prop"])])
