"""Town props IV, pool round 2 - set pieces of five rural buildings, 1990s-2000s, abandoned since the Bloom.

Cannery: the horizontal steam retort (riveted drum, hinged round door, basket rail), a roller conveyor, the
rotary can filler and seamer, a shrink-wrapped pallet of unlabelled cans, the stainless sorting table and
stacked fish totes.
Water works pump house: a centrifugal pump and motor on a concrete plinth, a valved pipe manifold (floor and
wall runs), the chlorinator (gas cylinders chained on a scale, regulator panel on the wall), the wall
relay / control cabinet.
Quarry office: the explosives day magazine on skids, a core-tray rack, the drill steel rack, the
weighbridge readout desk and its chair.
Pawn & Gun: the handgun display counter, the wall long-gun rack behind a cable lock, mixed pawn shelving
(guitars, power tools, a TV, jewellery boxes), a folding security grille and the ammunition shelf.
VFW post: the honor wall, a two-flag stand (plain generic flags), the memorial case and the back bar with
its tap tower.

Built on the interior-props framework (lib/props_int_core.py: Prop, variants clean / worn / destroyed, wear
/ AO vertex colours, collision boxes; lib/props_int_mesh.py geometry, lib/props_int_furn.py assemblies).
Graphics come from textures/gen/town4.py: town4_print (ATLAS below mirrors PRINT_RECTS) and the tiling can
stack sides / tops (CAN_* below mirror its tile). No readable text, brands, logos or real flags anywhere.

params: prop (id), seed, variants, mount, budget (see blender_catalogs/props_town4.py).
"""
from __future__ import annotations

import math

import bmesh
from mathutils import Matrix, Vector, noise

from lib import materials
from lib import props_int_core as core
from lib import props_int_furn as F
from lib import props_int_mesh as G
from lib.props_int_core import M, Prop


class C:
    """Material ids: town4_* from game/data/materials/props_town4.json, the rest from other families."""
    PRINT = "town4_print"
    CAN_SIDE = "town4_can_side"
    CAN_TOP = "town4_can_top"
    TIN = "town4_tin"
    RETORT = "town4_retort_steel"
    GREEN = "town4_machine_green"
    PUMP = "town4_pump_blue"
    PIPE = "town4_pipe_blue"
    YELLOW = "town4_safety_yellow"
    MAGAZINE = "town4_magazine_red"
    PANEL = "town4_panel_grey"
    CYL_GREY = "town4_cylinder_grey"
    AMMO_CAN = "town4_ammo_can"
    GUITAR_RED = "town4_guitar_red"
    TOOL_TEAL = "town4_tool_teal"
    TOOL_YELLOW = "town4_tool_yellow"
    TOTE_BLUE = "town4_tote_blue"
    TOTE_GREY = "town4_tote_grey"
    WRAP = "town4_shrink_wrap"
    CORE = "town4_core_rock"
    CORE_DARK = "town4_core_dark"
    LENS_G = "town4_lens_green"
    HELMET = "town4_helmet_olive"
    # shared
    OAK = "civic_oak"
    OAK_DARK = "civic_oak_dark"
    MAHOGANY = "civic_mahogany"
    BRASS = "civic_brass"
    BRONZE = "civic_bronze"
    FELT_RED = "civic_felt_red"
    FELT_GREEN = "civic_felt_green"
    GALV = "metal_galvanized"
    STEEL = "road_steel"
    CONCRETE = "road_concrete"
    PAINT_RED = "paint_red"
    PAINT_BLACK = "paint_black"
    PAINT_GREY = "paint_grey"
    PAINT_OLIVE = "paint_olive"
    PL_BLACK = "plastic_black"
    PL_ORANGE = "plastic_orange"
    PL_YELLOW = "plastic_yellow"
    LENS_R = "lens_red"
    LENS_A = "lens_amber"
    LENS_C = "lens_clear"
    RUBBER = "rubber_black"
    WOOD_OLD = "wood_weathered"
    MIRROR = "mirror_dirty"
    BOTTLE_BROWN = "glass_brown"
    BOTTLE_GREEN = "glass_green"
    CARDBOARD = "cardboard"
    CHAIN = "trap_chain"
    GUN_STEEL = "item_steel_blued"
    GUN_STOCK = "trap_gun_stock"


# Blender-only preview colours for dev_preview renders (Godot swaps in the real materials).
materials.PREVIEW_COLORS.update({
    C.RETORT: (0.2, 0.22, 0.2), C.GREEN: (0.07, 0.15, 0.09), C.PUMP: (0.04, 0.12, 0.25), C.PIPE: (0.25, 0.4, 0.52),
    C.YELLOW: (0.6, 0.38, 0.03), C.MAGAZINE: (0.27, 0.05, 0.03), C.PANEL: (0.36, 0.38, 0.39), C.TIN: (0.65, 0.65, 0.62),
    C.TOTE_BLUE: (0.03, 0.12, 0.35), C.TOTE_GREY: (0.27, 0.29, 0.28), C.WRAP: (0.8, 0.82, 0.82), C.CORE: (0.35, 0.32, 0.28),
    C.CAN_SIDE: (0.55, 0.55, 0.52), C.CAN_TOP: (0.5, 0.5, 0.48), C.PRINT: (0.5, 0.5, 0.5),
})

# town4_print atlas rects (x0, y0, x1, y1) in pixels of the 1024 px texture - mirror of
# textures/gen/town4.py PRINT_RECTS.
ATLAS: dict[str, tuple[int, int, int, int]] = {
    "gauge": (0, 0, 128, 128),
    "gauge_red": (128, 0, 256, 128),
    "gauge_black": (256, 0, 384, 128),
    "can_end": (384, 0, 512, 128),
    "pict_explosive": (512, 0, 640, 128),
    "pict_flame": (640, 0, 768, 128),
    "pict_gas": (768, 0, 896, 128),
    "pict_warn": (896, 0, 1024, 128),
    "chart": (0, 128, 256, 384),
    "mimic": (256, 128, 768, 384),
    "nameplate": (768, 128, 1024, 256),
    "lcd": (768, 256, 1024, 320),
    "hazard": (768, 320, 1024, 384),
    "photo0": (0, 384, 128, 544),
    "photo1": (128, 384, 256, 544),
    "photo2": (256, 384, 384, 544),
    "photo3": (384, 384, 512, 544),
    "photo4": (512, 384, 640, 544),
    "photo5": (640, 384, 768, 544),
    "plaque": (768, 384, 896, 544),
    "certificate": (896, 384, 1024, 544),
    "flag_a": (0, 544, 256, 704),
    "flag_b": (256, 544, 512, 704),
    "sunburst": (512, 544, 672, 704),
    "ribbon0": (672, 544, 736, 640),
    "ribbon1": (736, 544, 800, 640),
    "ribbon2": (800, 544, 864, 640),
    "ribbon3": (864, 544, 928, 640),
    "velvet": (928, 544, 1024, 640),
    "felt_black": (672, 640, 800, 704),
    "price_tag": (800, 640, 928, 704),
    "velvet_red": (928, 640, 1024, 704),
    "ammo0": (0, 704, 192, 800),
    "ammo1": (192, 704, 384, 800),
    "ammo2": (384, 704, 576, 800),
    "ammo3": (576, 704, 768, 800),
    "ammo_end": (768, 704, 896, 800),
    "fish_slime": (896, 704, 1024, 800),
    "painting": (0, 800, 256, 1024),
    "site_plan": (256, 800, 512, 1024),
    "clip_sheet": (512, 800, 768, 1024),
    "emblem": (768, 800, 1024, 1024),
}

# Tiling can stacks - mirror of textures/gen/town4.py CAN_TILE_*: one tile is 8 cans across, 4 tiers up.
CAN_D = 0.078  # 1 lb tall can, 301 x 411
CAN_H = 0.116
CAN_TIER = 0.12  # can + tier sheet
CAN_TX = 8 * CAN_D
CAN_TZ = 4 * CAN_TIER


def atlas(name: str, inset: float = 1.0) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = ATLAS[name]
    return core._px_rect(x0 + inset, y0 + inset, x1 - inset, y1 - inset)


# ------------------------------------------------------------------------------------------------
# shared helpers
# ------------------------------------------------------------------------------------------------

DIRS = {"-Y": Vector((0, -1, 0)), "Y": Vector((0, 1, 0)), "+Y": Vector((0, 1, 0)), "X": Vector((1, 0, 0)),
        "+X": Vector((1, 0, 0)), "-X": Vector((-1, 0, 0)), "Z": Vector((0, 0, 1)), "+Z": Vector((0, 0, 1)),
        "-Z": Vector((0, 0, -1))}


def _rot_for(facing: str) -> tuple[float, float, float]:
    return {"-Y": (0, 0, 0), "+Y": (0, 0, 180), "+X": (0, 0, 90), "-X": (0, 0, -90), "+Z": (-90, 0, 0),
            "-Z": (90, 0, 0)}[facing]


def plate(p: Prop, w: float, h: float, center, uvrect, *, t: float = 0.002, mat: str = C.PRINT, facing: str = "-Y",
          tags=(), wear: float = 0.35, bevel: float = 0.0, rot=None) -> core.Part:
    """Thin printed panel w x h (built in the XZ plane facing -Y, then turned to `facing`) whose front face
    shows `uvrect`; the back mirrors it and the edges sample the rect's edge."""
    obj = G.box(p._name("plate"), (w, t, h), (0, 0, 0), bevel)
    u0, v0, u1, v1 = uvrect
    edge = (u0, v0, u0 + (u1 - u0) * 0.03, v1)

    def fr(poly):
        n = poly.normal
        if n.y < -0.9:
            return (u0, v0, u1, v1, 0, 2, False)
        if n.y > 0.9:
            return (u0, v0, u1, v1, 0, 2, True)
        return (*edge, 0 if abs(n.x) < 0.5 else 1, 2, False)

    core.set_face_uvs(obj, fr)
    G.xform(obj, rot=rot if rot is not None else _rot_for(facing), loc=center)
    return p.add(obj, mat, uv="keep", tags=tags, wear=wear)


def disc_face(p: Prop, r: float, t: float, center, uvrect, *, axis: str = "-Y", mat: str = C.PRINT, segs: int = 16,
              tags=()) -> core.Part:
    """Round printed face (gauge / dial / chart): a short cylinder whose caps show uvrect (planar)."""
    obj = G.cyl(p._name("disc"), r, t, (0, 0, 0), "Z", segs)
    u0, v0, u1, v1 = uvrect
    me = obj.data
    uvl = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if poly.normal.z > 0.5:
                tu, tv = 0.5 + co.x / (2 * r), 0.5 + co.y / (2 * r)
            elif poly.normal.z < -0.5:
                tu, tv = 0.5 - co.x / (2 * r), 0.5 + co.y / (2 * r)
            else:
                tu, tv = 0.02, 0.5
            uvl.data[li].uv = (u0 + tu * (u1 - u0), v0 + tv * (v1 - v0))
    obj.data.transform(G._axis_matrix(axis))
    G.xform(obj, loc=center)
    return p.add(obj, mat, uv="keep", tags=tags, wear=0.3)


def bar(p: Prop, a, b, w: float, d: float, mat: str, **kw) -> core.Part:
    """Rectangular beam from point a to b (w across, d in the bar's 'up' direction)."""
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


def sphere(p: Prop, r: float, center, mat: str, segs: int = 10, rings: int = 6, **kw) -> core.Part:
    prof = [(0.0, -r)] + [(r * math.sin(math.pi * i / rings), -r * math.cos(math.pi * i / rings)) for i in range(1, rings)] + [(0.0, r)]
    return p.lathe(prof, center, mat, segs=segs, **kw)


def torus(p: Prop, R: float, r: float, center, mat: str, *, axis: str = "Z", segs: int = 20, rsegs: int = 6,
          arc: float = 360.0, a0: float = 0.0, **kw) -> core.Part:
    """Ring of radius R (tube radius r) around `axis` through center; arc < 360 gives an open arc."""
    n = segs if arc >= 360.0 else segs + 1
    pts = [(R * math.cos(math.radians(a0 + arc * i / segs)), R * math.sin(math.radians(a0 + arc * i / segs)), 0.0)
           for i in range(n)]
    obj = G.tube(p._name("torus"), pts, r, rsegs, cap=arc < 360.0, closed=arc >= 360.0)
    obj.data.transform(G._axis_matrix(axis))
    G.xform(obj, loc=center)
    kw.setdefault("edge_deg", 50.0)
    return p.add(obj, mat, **kw)


def rivet(p: Prop, pos, normal, r: float = 0.012, mat: str = C.RETORT) -> core.Part:
    """Snap-head rivet (5-sided dome) on a surface at pos with outward normal."""
    obj = G.lathe(p._name("rivet"), [(r, 0.0), (0.0, r * 0.7)], 6, (0, 0, 0), "Z", False, False)
    q = Vector((0, 0, 1)).rotation_difference(Vector(normal).normalized())
    obj.data.transform(Matrix.Translation(Vector(pos)) @ q.to_matrix().to_4x4())
    obj.data.update()
    return p.add(obj, mat, wear=1.6, edge_deg=40.0)


def place(parts, matrix: Matrix) -> None:
    for q in parts:
        q.obj.data.transform(matrix)
        q.obj.data.update()


def frame_to(axis: str, center) -> Matrix:
    """Local +Z -> axis, then translate to center (for assemblies built about the Z axis)."""
    return Matrix.Translation(Vector(center)) @ G._axis_matrix(axis)


def handwheel(p: Prop, c, R: float, axis: str = "Z", mat: str = C.PAINT_RED, spokes: int = 3) -> list:
    """Valve handwheel: rim, hub and spokes, built about Z and turned to `axis`."""
    out = [torus(p, R, max(0.006, R * 0.09), (0, 0, 0), mat, segs=14 if R > 0.15 else 10, rsegs=4, wear=1.2)]
    out.append(p.cyl(R * 0.2, R * 0.35, (0, 0, 0), mat, segs=8))
    for k in range(spokes):
        a = 2 * math.pi * k / spokes + 0.3
        out.append(bar(p, (math.cos(a) * R * 0.15, math.sin(a) * R * 0.15, 0), (math.cos(a) * R * 0.95, math.sin(a) * R * 0.95, 0),
                       R * 0.12, R * 0.07, mat, bevel=0.0))
    place(out, frame_to(axis, c))
    return out


def flange(p: Prop, c, r: float, axis: str, mat: str, *, t: float | None = None, bolts: int = 8, bolt_mat: str = C.STEEL) -> list:
    """Pipe flange (disc) with its bolt heads on both faces, about `axis` at c."""
    t = t if t is not None else max(0.025, r * 0.35)
    R = r * 1.75
    out = [p.cyl(R, t, (0, 0, 0), mat, segs=12 if r > 0.08 else 10)]
    if bolts:
        for k in range(bolts):
            a = 2 * math.pi * (k + 0.5) / bolts
            x, y = math.cos(a) * R * 0.8, math.sin(a) * R * 0.8
            out.append(p.cyl(R * 0.09, t + 0.03, (x, y, 0), bolt_mat, segs=6, wear=1.4))
    place(out, frame_to(axis, c))
    return out


def gate_valve(p: Prop, c, r: float, *, matrix: Matrix | None = None, body: str = C.PIPE, wheel: str = C.PAINT_RED,
               rising: bool = True, stem_turn: float = 0.0) -> list:
    """Flanged gate valve built with the pipe along X and the stem up +Z at the origin, then moved by `matrix`
    (rotation) and translated to c. Body, bonnet, yoke, rising stem and handwheel."""
    L = r * 3.2
    out = []
    nb = 4 if r < 0.06 else 8
    out += flange(p, (-L / 2, 0, 0), r, "X", body, bolts=nb)
    out += flange(p, (L / 2, 0, 0), r, "X", body, bolts=nb)
    sg = 12 if r > 0.08 else 10
    out.append(p.cyl(r * 1.2, L * 0.85, (0, 0, 0), body, axis="X", segs=sg))
    out.append(p.lathe([(r * 1.35, -r * 0.6), (r * 1.45, 0.0), (r * 1.2, r * 1.2), (r * 0.9, r * 1.5), (0.0, r * 1.5)],
                       (0, 0, 0), body, segs=sg))
    out.append(p.cyl(r * 1.2, r * 0.18, (0, 0, r * 1.55), body, segs=sg))
    top = r * 1.6
    yh = r * 3.0
    for sx in (-1, 1):
        out.append(bar(p, (sx * r * 0.7, 0, top), (sx * r * 0.45, 0, top + yh), r * 0.25, r * 0.3, body))
    out.append(p.box((r * 1.3, r * 0.45, r * 0.3), (0, 0, top + yh), body, bevel=0.004))
    stem_top = top + yh + (r * 1.6 if rising else r * 0.4)
    out.append(p.cyl(r * 0.12, stem_top - top, (0, 0, (top + stem_top) / 2), M.CHROME, segs=6))
    out += handwheel(p, (0, 0, top + yh + r * 0.35), r * 1.6, "Z", wheel)
    m = Matrix.Translation(Vector(c)) @ (matrix if matrix is not None else Matrix.Identity(4))
    if stem_turn:
        m = m @ Matrix.Rotation(math.radians(stem_turn), 4, "X")
    place(out, m)
    return out


def gauge(p: Prop, c, r: float, cell: str = "gauge", facing: str = "-Y", depth: float = 0.045, stem: float = 0.05,
          bezel: str = M.CHROME) -> list:
    """Dial gauge: a case (cylinder) with the printed face in front and a stem out of the back."""
    d = DIRS[facing]
    cv = Vector(c)
    ax = facing.lstrip("+")
    out = [p.cyl(r, depth, tuple(cv), bezel, axis=ax.strip("-"), segs=14)]
    out.append(disc_face(p, r * 0.9, 0.004, tuple(cv + d * (depth / 2 + 0.001)), atlas(cell), axis=facing if facing != "+Y" else "Y",
                         segs=14))
    if stem > 0:
        out.append(p.cyl(r * 0.18, stem, tuple(cv - d * (depth / 2 + stem / 2)), C.BRASS, axis=ax.strip("-"), segs=6))
    return out


def tin_can(p: Prop, center, rot=(0, 0, 0), r: float = CAN_D / 2, h: float = CAN_H, segs: int = 8, dent: float = 0.0) -> core.Part:
    """Unlabelled tinplate can: tin sides (metre UVs), printed seamed ends (atlas can_end)."""
    obj = G.cyl(p._name("can"), r * 0.985, h, (0, 0, 0), "Z", segs)
    me = obj.data
    uvl = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
    lid = atlas("can_end", 3.0)
    for poly in me.polygons:
        if abs(poly.normal.z) > 0.9:
            for li in poly.loop_indices:
                co = me.vertices[me.loops[li].vertex_index].co
                uvl.data[li].uv = (lid[0] + (co.x / r * 0.5 + 0.5) * (lid[2] - lid[0]),
                                   lid[1] + (co.y / r * 0.5 + 0.5) * (lid[3] - lid[1]))
            continue
        angs = [math.atan2(me.vertices[me.loops[li].vertex_index].co.y, me.vertices[me.loops[li].vertex_index].co.x)
                for li in poly.loop_indices]
        for k, li in enumerate(poly.loop_indices):
            a = angs[k]
            if a - angs[0] > math.pi:
                a -= 2 * math.pi
            elif a - angs[0] < -math.pi:
                a += 2 * math.pi
            co = me.vertices[me.loops[li].vertex_index].co
            uvl.data[li].uv = (a * r, co.z)
    if dent > 0:
        for v in me.vertices:
            if v.co.x > r * 0.5:
                v.co.x -= dent * (1.0 - abs(v.co.z) / (h * 0.5))
    part = p.add(obj, C.TIN, uv="keep", tags=("goods",), wear=0.8, edge_deg=40.0)
    p.set_mat(part, C.PRINT, lambda poly: abs(poly.normal.z) > 0.9)
    G.xform(obj, rot=rot, loc=center)
    return part


def can_on_floor(p: Prop, x: float, y: float, r_: "object", z: float = 0.0, lying: bool | None = None) -> core.Part:
    """A loose can on a surface at height z: standing, or lying on its side (r_ = Random)."""
    if lying is None:
        lying = r_.random() < 0.6
    if lying:
        return tin_can(p, (x, y, z + CAN_D / 2 * 0.985), rot=(90, 0, r_.uniform(0, 180)))
    return tin_can(p, (x, y, z + CAN_H / 2), rot=(0, 0, r_.uniform(0, 90)))


def stack_block(p: Prop, x0: float, x1: float, y0: float, y1: float, z0: float, z1: float, *, top: bool = True) -> core.Part:
    """A solid block of stowed cans (tiling can_side texture on the sides, can_top on the top), its UVs
    aligned so whole cans start at the block's -X / -Y edges and tiers start at z0."""
    obj = G.box(p._name("stack"), (x1 - x0, y1 - y0, z1 - z0), ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), 0.0)
    me = obj.data
    uvl = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        n = poly.normal
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if abs(n.z) > 0.9:
                uvl.data[li].uv = ((co.x - x0) / CAN_TX, (co.y - y0) / CAN_TX)
            elif abs(n.y) > 0.9:
                uvl.data[li].uv = ((co.x - x0) / CAN_TX, (co.z - z0) / CAN_TZ)
            else:
                uvl.data[li].uv = ((co.y - y0) / CAN_TX, (co.z - z0) / CAN_TZ)
    part = p.add(obj, C.CAN_SIDE, uv="keep", tags=("goods",), wear=0.2)
    p.set_mat(part, C.CAN_TOP if top else C.CARDBOARD, lambda poly: poly.normal.z > 0.9)
    return part


def scatter_papers(p: Prop, c, n: int, spread: float, key: str, z: float = 0.0) -> list:
    r = p.vrng(key)
    out = []
    for i in range(n):
        s = p.box((r.uniform(0.18, 0.22), r.uniform(0.25, 0.29), 0.0015),
                  (c[0] + r.uniform(-spread, spread), c[1] + r.uniform(-spread, spread), z + 0.001 + i * 0.0012),
                  M.PAPER, bevel=0.0, uv="planar", uv_axis="Z", rect=core.note_rect(i % 4))
        G.xform(s.obj, rot=(0, 0, r.uniform(0, 180)), pivot=(c[0], c[1], z))
        out.append(s)
    return out


def sheet(p: Prop, path, z0: float, z1: float, nz: int, mat: str, *, key: str, keep=None, wrinkle: float = 0.0,
          out_dirs=None, uv_scale: float = 1.0, top_fold: float = 0.0, closed: bool = True) -> core.Part | None:
    """A thin single-layer sheet (shrink wrap, tarp) swept around a polyline `path` [(x, y), ...] from z0 to
    z1 in nz rows; wrinkle pushes vertices outward by noise (out_dirs[i] = outward 2D normal per path point);
    keep(u, v) -> False drops a cell (tears); top_fold folds the top row inward by that much."""
    n = len(path)
    cols = n if closed else n - 1
    lens = [0.0]
    for i in range(1, n + (1 if closed else 0)):
        a, b = Vector(path[(i - 1) % n]), Vector(path[i % n])
        lens.append(lens[-1] + (b - a).length)
    total = lens[-1]
    rows = nz + (1 if top_fold > 0 else 0)
    noise.seed_set(p.seed % 9973 + 11)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    grid = {}
    for j in range(rows + 1):
        for i in range(n):
            x, y = path[i]
            od = Vector(out_dirs[i]) if out_dirs else Vector((0, 0))
            if j <= nz:
                z = z0 + (z1 - z0) * j / nz
                pos = Vector((x, y, z))
            else:
                pos = Vector((x - od.x * top_fold, y - od.y * top_fold, z1 + 0.004))
            if wrinkle > 0:
                w = noise.noise(pos * 9.0 + Vector((p.seed * 0.13, 0.7, 1.3)))
                pos += Vector((od.x, od.y, 0)) * (0.5 + 0.5 * w) * wrinkle
            grid[(i, j)] = bm.verts.new(pos)
    for j in range(rows):
        for i in range(cols):
            u = (lens[i] + lens[i + 1]) * 0.5 / total
            v = (j + 0.5) / rows
            if keep is not None and not keep(u, v):
                continue
            i2 = (i + 1) % n
            vs = [grid[(i, j)], grid[(i2, j)], grid[(i2, j + 1)], grid[(i, j + 1)]]
            f = bm.faces.new(vs)
            for lp, (ii, jj) in zip(f.loops, ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))):
                lp[uvl].uv = (lens[ii] * uv_scale, (z0 + (z1 - z0) * min(jj, nz) / nz + (0.05 if jj > nz else 0.0)) * uv_scale)
    if not bm.faces:
        bm.free()
        return None
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    obj = G._obj(p._name(key), bm)
    return p.add(obj, mat, uv="keep", wear=0.2, edge_deg=60.0)


def rect_path(w: float, d: float, r: float, per_side: int = 4, cx: float = 0.0, cy: float = 0.0):
    """Rounded-rectangle outline (CCW from above) subdivided per_side times along each straight side, with
    the outward normal of each point."""
    pts, nrm = [], []
    corners = ((w / 2 - r, -d / 2 + r, -90), (w / 2 - r, d / 2 - r, 0), (-w / 2 + r, d / 2 - r, 90), (-w / 2 + r, -d / 2 + r, 180))
    for k, (qx, qy, a0) in enumerate(corners):
        for i in range(3):
            a = math.radians(a0 + 90 * i / 2)
            pts.append((cx + qx + r * math.cos(a), cy + qy + r * math.sin(a)))
            nrm.append((math.cos(a), math.sin(a)))
        nx, ny, _ = corners[(k + 1) % 4]
        a = math.radians(a0 + 90)
        for i in range(1, per_side):
            t = i / per_side
            pts.append((cx + qx + r * math.cos(a) + (nx - qx) * t, cy + qy + r * math.sin(a) + (ny - qy) * t))
            nrm.append((math.cos(a), math.sin(a)))
    return pts, nrm


def tote(p: Prop, center, *, yaw: float = 0.0, mat: str = C.TOTE_BLUE, rot=None, w: float = 0.8, d: float = 0.52,
         h: float = 0.3) -> list:
    """Stackable fish tote: a tapered moulded tub with a rolled lip, hand slots at the ends and a stacking
    rib round the body; built at the origin (bottom centre), turned and moved to center."""
    t = 0.012
    rings = [G.rrect_ring(w - 0.08, d - 0.08, 0.05, 0.0, 2), G.rrect_ring(w - 0.01, d - 0.01, 0.07, h - 0.03, 2),
             G.rrect_ring(w + 0.02, d + 0.02, 0.08, h - 0.028, 2), G.rrect_ring(w + 0.02, d + 0.02, 0.08, h, 2),
             G.rrect_ring(w - 0.01 - 2 * t, d - 0.01 - 2 * t, 0.06, h, 2),
             G.rrect_ring(w - 0.08 - 2 * t, d - 0.08 - 2 * t, 0.04, t, 2)]
    body = p.add(G.loft(p._name("tote"), rings, cap_bottom=True, cap_top=True), mat, wear=0.5, edge_deg=35.0)
    out = [body]
    for sx in (-1, 1):
        out.append(p.box((0.012, 0.14, 0.045), (sx * (w / 2 - 0.006), 0, h - 0.07), C.PL_BLACK, bevel=0.0, wear=0.0))
    out.append(p.add(G.loft(p._name("rib"), [G.rrect_ring(w - 0.035, d - 0.035, 0.06, h * 0.45, 2),
                                             G.rrect_ring(w - 0.03, d - 0.03, 0.06, h * 0.45 + 0.012, 2)],
                            cap_bottom=False, cap_top=False), mat, wear=0.5, edge_deg=35.0))
    m = Matrix.Translation(Vector(center)) @ Matrix.Rotation(math.radians(yaw), 4, "Z")
    if rot is not None:
        m = m @ G.rot_matrix(rot)
    place(out, m)
    return out


# ================================================================================================
# Cannery
# ================================================================================================


def cannery_retort(p: Prop) -> None:
    """Horizontal still retort (1.7 x 2.5 x 3.9): a riveted steel pressure drum 1.4 m across and about 3 m
    long on two saddles, a dished back head and a dished door on the front (-Y) hung from a davit hinge with
    a centre handwheel and clamp lugs round the flange. On top: the steam inlet with its globe valve, the
    vent line, the safety valve and the pressure gauge; on the left the recording thermometer (round chart)
    and the glass thermometer; the drain under the back; two basket rails inside, carried out the door onto a
    short transfer stand. Worn: rusted through the paint, the door swung wide open and a basket of cans
    half rolled out on the rails."""
    R, zc = 0.7, 1.1
    y0, y1 = -1.35, 1.3
    sh = C.RETORT
    prof = [(0.0, 1.5), (0.35, 1.46), (0.55, 1.39), (0.64, 1.32), (R - 0.04, 1.22), (R - 0.04, y0 - 0.08), (0.8, y0 - 0.08),
            (0.8, y0), (R, y0), (R, 1.22), (R - 0.02, 1.35), (0.6, 1.47), (0.38, 1.56), (0.0, 1.6)]
    p.lathe(prof, (0, 0, zc), sh, segs=24, axis="Y", cap_bottom=False, cap_top=False, uv="box")
    # riveted circumferential straps and a longitudinal seam
    for yb in (-0.45, 0.45):
        p.lathe([(R - 0.005, -0.045), (R + 0.014, -0.04), (R + 0.014, 0.04), (R - 0.005, 0.045)], (0, yb, zc), sh, segs=24,
                axis="Y", cap_bottom=False, cap_top=False, uv="box")
        for k in range(15):
            a = 2 * math.pi * k / 15
            n = Vector((math.cos(a), 0, math.sin(a)))
            rivet(p, Vector((0, yb, zc)) + n * (R + 0.014), n, 0.011)
    for k in range(12):
        y = y0 + 0.12 + k * 0.21
        if abs(abs(y) - 0.45) < 0.06:
            continue
        a = math.radians(115)
        n = Vector((math.cos(a), 0, math.sin(a)))
        rivet(p, Vector((0, y, zc)) + n * R, n, 0.01)
    # saddles + legs
    for ys in (-0.8, 0.85):
        arc = [(0.71 * math.cos(math.radians(a)), zc + 0.71 * math.sin(math.radians(a))) for a in range(340, 199, -20)]
        poly = [(0.6, 0.32), (0.6, zc + 0.71 * math.sin(math.radians(340)))] + arc[1:-1] + \
               [(-0.6, zc + 0.71 * math.sin(math.radians(200))), (-0.6, 0.32)]
        p.prism(poly, 0.14, sh, plane="XZ", offset=ys - 0.07)
        p.box((1.3, 0.24, 0.02), (0, ys, 0.32), sh, bevel=0.003)
        for sx in (-1, 1):
            p.box((0.12, 0.12, 0.31), (sx * 0.5, ys, 0.165), sh, bevel=0.006, grain="Z")
            p.box((0.22, 0.22, 0.015), (sx * 0.5, ys, 0.0075), sh, bevel=0.003)
        p.box((0.9, 0.06, 0.06), (0, ys, 0.15), sh, bevel=0.004, grain="X")
    # front flange clamp lugs (shell side)
    for k in range(8):
        a = 2 * math.pi * (k + 0.5) / 8
        if abs(math.cos(a)) > 0.9 and math.cos(a) > 0:
            continue
        c = Vector((math.cos(a) * 0.83, y0 - 0.04, zc + math.sin(a) * 0.83))
        lug = p.box((0.07, 0.07, 0.09), (0, 0, 0), sh, bevel=0.006)
        G.xform(lug.obj, rot=(0, -math.degrees(a) + 90, 0), loc=c)
    # door (closed), davit hinge on +X
    yd = y0 - 0.08
    door = [p.lathe([(0.0, 0.0), (0.8, 0.0), (0.8, 0.07), (0.7, 0.095), (0.55, 0.16), (0.3, 0.215), (0.0, 0.235)], (0, yd, zc), sh,
                    segs=24, axis="-Y", cap_bottom=False, cap_top=False, uv="box")]
    for k in range(7):
        a = 2 * math.pi * (k + 0.5) / 8
        if math.cos(a) > 0.9:
            continue
        c = Vector((math.cos(a) * 0.83, yd - 0.04, zc + math.sin(a) * 0.83))
        lug = p.box((0.06, 0.06, 0.08), (0, 0, 0), M.CAST_IRON, bevel=0.006)
        G.xform(lug.obj, rot=(0, -math.degrees(a) + 90, 0), loc=c)
        door.append(lug)
    for k in range(12):
        a = 2 * math.pi * k / 12
        n = Vector((0, -1, 0))
        door.append(rivet(p, (math.cos(a) * 0.74, yd - 0.071, zc + math.sin(a) * 0.74), n, 0.011))
    door.append(p.cyl(0.05, 0.12, (0, yd - 0.28, zc), M.CAST_IRON, axis="Y", segs=10))
    door += handwheel(p, (0, yd - 0.34, zc), 0.24, "-Y", C.PAINT_RED, spokes=4)
    hx, hy = 0.93, yd - 0.07
    for dz in (-0.3, 0.3):
        door.append(bar(p, (hx, hy, zc + dz), (0.05, yd - 0.24, zc + dz * 0.5), 0.08, 0.04, sh, grain="X"))
        p.box((0.16, 0.08, 0.1), (0.85, y0 - 0.04, zc + dz), sh, bevel=0.008)
    p.cyl(0.03, 0.85, (hx, hy, zc), M.CHROME, segs=8)
    for dz in (-0.42, 0.42):
        p.cyl(0.045, 0.05, (hx, hy, zc + dz), sh, segs=8)
    # transfer rails: inside on cradles, and out front on a stand
    rz = 0.53
    for sx in (-1, 1):
        x = sx * 0.28
        p.box((0.05, y1 - 0.15 - y0, 0.035), (x, (y0 + y1 - 0.15) / 2, rz - 0.0175), M.CAST_IRON, bevel=0.003, grain="Y")
        for yc in (-0.9, 0.0, 0.9):
            p.box((0.07, 0.05, rz - 0.035 - (zc - R + 0.04) + 0.03), (x, yc, (rz - 0.035 + zc - R + 0.02) / 2), M.CAST_IRON, bevel=0.003)
        p.box((0.05, 0.85, 0.035), (x, -1.9, rz - 0.0175), M.CAST_IRON, bevel=0.003, grain="Y")
        for yl in (-1.55, -2.25):
            p.box((0.06, 0.06, rz - 0.035), (x, yl, (rz - 0.035) / 2), sh, bevel=0.004, grain="Z")
            p.box((0.14, 0.14, 0.012), (x, yl, 0.006), sh, bevel=0.002)
    for yl in (-1.55, -2.25):
        p.box((0.62, 0.05, 0.05), (0, yl, rz - 0.06), sh, bevel=0.004, grain="X")
    p.box((0.62, 0.05, 0.05), (0, -1.9, 0.12), sh, bevel=0.004, grain="X")
    # piping on top
    zt = zc + R
    p.cyl(0.09, 0.04, (0, 0.5, zt + 0.005), sh, segs=10)
    p.tube([(0, 0.5, zt), (0, 0.5, 2.3), (0, 0.8, 2.3), (0, 1.75, 2.3)], 0.045, C.STEEL, segs=10, fillet_r=0.1)
    gate_valve(p, (0, 0.5, 2.02), 0.045, matrix=Matrix.Rotation(math.pi / 2, 4, "Y") @ Matrix.Rotation(math.pi / 2, 4, "X"),
               body=M.CAST_IRON, wheel=C.PAINT_RED)
    p.tube([(-0.25, -0.95, zc + 0.65), (-0.25, -0.95, 2.42), (-0.25, -0.7, 2.42), (-0.25, 1.75, 2.42)], 0.032, C.STEEL, segs=8,
           fillet_r=0.08)
    gate_valve(p, (-0.25, -0.95, 2.1), 0.032, matrix=Matrix.Rotation(math.pi / 2, 4, "Y") @ Matrix.Rotation(math.pi / 2, 4, "X"),
               body=M.CAST_IRON, wheel=C.PAINT_RED)
    # safety valve
    p.cyl(0.03, 0.12, (0.2, -0.35, zt + 0.04), C.STEEL, segs=8)
    p.lathe([(0.055, 0.0), (0.06, 0.06), (0.045, 0.1), (0.035, 0.24), (0.05, 0.26), (0.03, 0.3), (0.0, 0.31)], (0.2, -0.35, zt + 0.1),
            C.BRASS, segs=10)
    rod(p, (0.2, -0.35, zt + 0.36), (0.32, -0.35, zt + 0.22), 0.006, C.BRASS, segs=5)
    # pressure gauge on a siphon riser
    p.tube([(0.3, -1.05, zc + 0.62), (0.3, -1.05, 1.95), (0.3, -1.1, 2.0)], 0.012, C.BRASS, segs=6, fillet_r=0.03)
    torus(p, 0.035, 0.008, (0.3, -1.05, 1.88), C.BRASS, axis="X", segs=10, rsegs=4)
    gauge(p, (0.3, -1.17, 2.06), 0.11, "gauge_red", "-Y", depth=0.06, stem=0.05)
    # recording thermometer (round chart) on a bracket on the left, facing the front
    bx = -0.93
    p.box((0.46, 0.15, 0.5), (bx, -1.0, 1.42), C.RETORT, bevel=0.02)
    disc_face(p, 0.19, 0.006, (bx, -1.078, 1.44), atlas("chart"), axis="-Y", segs=20)
    torus(p, 0.195, 0.012, (bx, -1.082, 1.44), M.CHROME, axis="Y", segs=20, rsegs=4)
    p.box((0.44, 0.004, 0.48), (bx, -1.083, 1.42), M.GLASS, bevel=0.0, wear=0.0)
    bar(p, (-0.69, -1.0, 1.25), (bx + 0.2, -1.0, 1.25), 0.05, 0.05, sh, grain="X")
    bar(p, (-0.66, -1.0, 1.55), (bx + 0.2, -1.0, 1.55), 0.05, 0.05, sh, grain="X")
    p.tube([(bx + 0.1, -0.93, 1.2), (bx + 0.1, -0.85, 1.05), (-0.69, -0.75, 1.0)], 0.006, M.CHROME, segs=4, fillet_r=0.05)
    # glass thermometer in its brass case beside it
    p.box((0.06, 0.05, 0.38), (-0.74, -1.22, 1.15), C.BRASS, bevel=0.006)
    p.box((0.02, 0.003, 0.3), (-0.74, -1.247, 1.16), M.GLASS, bevel=0.0, wear=0.0)
    p.tube([(-0.74, -1.22, 0.96), (-0.74, -1.2, 0.93), (-0.66, -1.2, 0.93)], 0.012, C.BRASS, segs=6)
    # nameplate on the shell side
    plate(p, 0.3, 0.15, (-R - 0.006, 0.0, zc), atlas("nameplate"), t=0.006, facing="-X", wear=0.5)
    # drain + water inlet
    p.tube([(0, 1.0, zc - R + 0.01), (0, 1.0, 0.14), (0, 1.3, 0.14), (0, 1.75, 0.14)], 0.04, C.STEEL, segs=8, fillet_r=0.08)
    gate_valve(p, (0, 1.0, 0.27), 0.04, matrix=Matrix.Rotation(math.pi / 2, 4, "Y") @ Matrix.Rotation(-math.pi / 2, 4, "X"),
               body=M.CAST_IRON, wheel=C.PAINT_RED)
    p.tube([(-R + 0.01, 0.9, zc + 0.25), (-0.86, 0.9, zc + 0.25), (-0.86, 1.1, zc + 0.25), (-0.86, 1.75, zc + 0.25)], 0.035,
           C.STEEL, segs=8, fillet_r=0.08)
    if p.worn:
        p.rotate(door, rot=(0, 0, 112), pivot=(hx, hy, 0))
        # a retort basket of cans rolled half out onto the transfer stand
        by = -1.45
        bw, bd, bh = 0.76, 1.0, 0.72
        bz = rz + 0.06
        basket = [p.hollow((bw, bd, bh), (0, by, bz + bh / 2), C.GALV, wall=0.012, open_face="+Z", bevel=0.0)]
        basket.append(stack_block(p, -bw / 2 + 0.02, bw / 2 - 0.02, by - bd / 2 + 0.02, by + bd / 2 - 0.02, bz + 0.015,
                                  bz + 0.015 + 5 * CAN_TIER - 0.004))
        for sx in (-1, 1):
            for yy in (by - 0.35, by + 0.35):
                p.cyl(0.03, 0.03, (sx * 0.28, yy, rz + 0.03), M.CAST_IRON, axis="X", segs=8)
            p.box((0.02, bd, 0.05), (sx * (bw / 2 + 0.01), by, bz + bh - 0.04), C.GALV, bevel=0.002)
        p.box((bw - 0.1, 0.03, 0.03), (0, by - bd / 2 - 0.03, bz + bh - 0.05), C.GALV, bevel=0.003)
        r = p.vrng("cans")
        for i in range(2):
            can_on_floor(p, r.uniform(-0.6, 0.6), -2.45 + r.uniform(-0.15, 0.15), r, lying=True)
        p.collider((1.25, -1.95, 1.1), (0.8, 0.9, 1.7))
    p.collider((0, 0.1, 1.23), (1.75, 3.3, 2.46))
    p.collider((0, -1.92, 0.3), (0.8, 0.85, 0.6))


def cannery_conveyor(p: Prop) -> None:
    """Gravity roller conveyor section (3.0 x 0.85 x 0.6): galvanised rollers between channel side frames,
    three leg stands with braces and levelling feet, round can guides on brackets either side. Clean: a
    file of cans on the rollers. Worn: a few cans left, some toppled, two on the floor. Destroyed: the far
    stand gone and the middle one buckled, the section dropped to the floor at one end, cans spilled."""
    L, W, top = 3.0, 0.46, 0.84
    frame = []
    for sy in (-1, 1):
        frame.append(p.box((L, 0.04, 0.11), (0, sy * (W / 2 + 0.02), top - 0.055), C.GALV, bevel=0.003, grain="X"))
        frame.append(p.box((L, 0.06, 0.008), (0, sy * (W / 2 + 0.01), top - 0.11), C.GALV, bevel=0.0, grain="X"))
    n = 30
    for i in range(n):
        x = -L / 2 + 0.05 + i * (L - 0.1) / (n - 1)
        frame.append(p.cyl(0.024, W, (x, 0, top - 0.024), C.GALV, axis="Y", segs=7))
    for sy in (-1, 1):
        y = sy * (W / 2 - 0.12)
        frame.append(p.tube([(-L / 2, y, top + 0.07), (L / 2, y, top + 0.07)], 0.008, M.CHROME, segs=5))
        for x in (-1.3, 0.0, 1.3):
            frame.append(bar(p, (x, sy * (W / 2 + 0.02), top), (x, y, top + 0.07), 0.02, 0.006, M.CHROME, grain="Y"))
    legs = {}
    for x in (-1.35, 0.0, 1.35):
        grp = []
        for sy in (-1, 1):
            y = sy * (W / 2 + 0.02)
            grp.append(p.box((0.04, 0.04, top - 0.16), (x, y, (top - 0.11 + 0.05) / 2), C.GALV, bevel=0.003, grain="Z"))
            grp.append(p.cyl(0.025, 0.04, (x, y, 0.02), C.RUBBER, segs=6))
        grp.append(p.box((0.035, W + 0.04, 0.035), (x, 0, 0.25), C.GALV, bevel=0.003, grain="Y"))
        grp.append(bar(p, (x, -W / 2 - 0.02, 0.27), (x, W / 2 + 0.02, top - 0.14), 0.025, 0.02, C.GALV))
        legs[x] = grp
    r = p.vrng("cans")
    cans = []
    if not p.worn:
        for i in range(14):
            cans.append(tin_can(p, (-1.25 + i * 0.081, 0.0, top + CAN_H / 2), rot=(0, 0, i * 37 % 90)))
    elif not p.destroyed:
        for i, x in enumerate((-1.2, -1.12, -0.6, 0.35, 0.43, 1.1)):
            if i in (2, 4):
                cans.append(tin_can(p, (x, r.uniform(-0.08, 0.08), top + CAN_D / 2 * 0.985), rot=(90, 0, r.uniform(-40, 40))))
            else:
                cans.append(tin_can(p, (x, 0.0, top + CAN_H / 2), rot=(0, 0, r.uniform(0, 90))))
        for i in range(2):
            can_on_floor(p, r.uniform(-0.5, 0.8), -0.5 - r.uniform(0, 0.2), r, lying=True)
    if p.destroyed:
        p.remove(legs[1.35])
        mid = legs[0.0]
        p.remove(mid)
        b = p.box((0.04, 0.04, 0.6), (0, 0, 0), C.GALV, bevel=0.003)
        p.lay_on_floor([b], rot=(0, 90, 0), at=(0.4, -0.55), yaw=25)
        p.settle(frame, (-1.35, 0, top - 0.11), (0, 1, 0), max_deg=40)
        for i in range(9):
            can_on_floor(p, r.uniform(0.6, 2.0), r.uniform(-0.6, 0.6), r)
        p.collider((0.1, 0, 0.45), (3.0, 0.9, 0.9))
    else:
        p.collider((0, 0, top / 2 + 0.05), (L, W + 0.1, top + 0.1))


def cannery_filler(p: Prop) -> None:
    """Rotary can filler and double seamer (1.6 x 2.0 x 1.0): a green machine base with access panels, a
    stainless deck; on the left the filler carousel with twelve filling valves under a conical product
    hopper on its column, an infeed starwheel, on the right the seamer head in its housing; the drive
    motor and belt guard at the back, a pendant control box with start / stop buttons at the front.
    Worn: the hopper lid knocked off onto the floor, cans jammed in the starwheel, toppled and spilled."""
    W, D, H = 1.5, 0.8, 0.86
    g = C.GREEN
    p.box((W, D, H - 0.06), (0, 0, (H - 0.06) / 2 + 0.06), g, bevel=0.01)
    for x in (-0.7, 0.7):
        for y in (-0.33, 0.33):
            p.cyl(0.035, 0.06, (x, y, 0.03), M.CHROME, segs=8)
    for x0, x1 in ((-0.7, -0.05), (0.05, 0.7)):
        p.box((x1 - x0, 0.015, H - 0.26), ((x0 + x1) / 2, -D / 2 - 0.007, 0.48), g, bevel=0.006)
        p.box((0.1, 0.03, 0.03), ((x0 + x1) / 2, -D / 2 - 0.025, 0.72), M.CHROME, bevel=0.006)
    p.box((W + 0.05, D + 0.05, 0.03), (0, 0, H + 0.015), M.STAINLESS, bevel=0.005)
    zd = H + 0.03
    # filler carousel
    fx = -0.3
    p.lathe([(0.0, 0.0), (0.44, 0.0), (0.44, 0.05), (0.4, 0.07), (0.38, 0.12), (0.0, 0.12)], (fx, 0, zd + 0.02), M.STAINLESS, segs=24)
    p.cyl(0.2, 0.02, (fx, 0, zd + 0.01), M.CAST_IRON, segs=14)
    for k in range(12):
        a = 2 * math.pi * k / 12
        x, y = fx + math.cos(a) * 0.36, math.sin(a) * 0.36
        p.cyl(0.028, 0.1, (x, y, zd + 0.19), M.STAINLESS, segs=6)
        p.cyl(0.012, 0.05, (x, y, zd + 0.115), M.STAINLESS, segs=5)
        p.cyl(0.04, 0.008, (x, y, zd + 0.02), M.CHROME, segs=8)
    p.cyl(0.07, 0.75, (fx, 0, zd + 0.5), M.STAINLESS, segs=10)
    hop_z = zd + 0.82
    p.lathe([(0.0, 0.0), (0.13, 0.0), (0.13, 0.08), (0.42, 0.42), (0.44, 0.42), (0.44, 0.45), (0.4, 0.45), (0.12, 0.12), (0.0, 0.1)],
            (fx, 0, hop_z), M.STAINLESS, segs=20)
    lid = [p.lathe([(0.0, 0.0), (0.45, 0.0), (0.45, 0.03), (0.2, 0.06), (0.0, 0.07)], (fx, 0, hop_z + 0.45), M.STAINLESS, segs=20)]
    lid.append(p.tube([(fx - 0.08, 0, hop_z + 0.52), (fx - 0.06, 0, hop_z + 0.57), (fx + 0.06, 0, hop_z + 0.57), (fx + 0.08, 0, hop_z + 0.52)],
                      0.008, M.CHROME, segs=5))
    gauge(p, (fx - 0.3, -0.29, hop_z + 0.2), 0.05, "gauge", "-Y", depth=0.03, stem=0.03)
    p.tube([(fx - 0.3, -0.24, hop_z + 0.2), (fx - 0.3, -0.12, hop_z + 0.24)], 0.008, M.CHROME, segs=5)
    # product feed pipe from the back into the hopper
    p.tube([(fx, 0.55, 0.6), (fx, 0.55, hop_z + 0.65), (fx, 0.1, hop_z + 0.65), (fx, 0.1, hop_z + 0.42)], 0.04, M.STAINLESS, segs=10,
           fillet_r=0.1)
    # infeed starwheel + seamer
    p.cyl(0.16, 0.02, (0.17, -0.12, zd + 0.06), M.STAINLESS, segs=12)
    p.cyl(0.04, 0.12, (0.17, -0.12, zd + 0.06), M.CAST_IRON, segs=8)
    sx = 0.45
    p.box((0.5, 0.55, 0.45), (sx, 0.05, zd + 0.225), g, bevel=0.012)
    p.box((0.52, 0.57, 0.03), (sx, 0.05, zd + 0.46), g, bevel=0.006)
    p.cyl(0.13, 0.36, (sx, 0.0, zd + 0.66), M.STAINLESS, segs=14)
    p.lathe([(0.15, 0.0), (0.15, 0.04), (0.1, 0.1), (0.0, 0.11)], (sx, 0.0, zd + 0.84), g, segs=14)
    p.cyl(0.06, 0.2, (sx, -0.2, zd + 0.15), M.STAINLESS, segs=8)
    p.box((0.32, 0.02, 0.3), (sx, -0.235, zd + 0.24), M.GLASS, bevel=0.0, wear=0.0)
    # discharge rails off the right edge
    for yy in (-0.27, -0.13):
        p.tube([(sx + 0.25, yy, zd + 0.09), (W / 2 + 0.15, yy, zd + 0.09)], 0.008, M.CHROME, segs=5)
    p.box((0.4, 0.2, 0.01), (W / 2 - 0.05, -0.2, zd + 0.005), M.STAINLESS, bevel=0.0)
    # drive motor + belt guard at the back
    p.cyl(0.14, 0.38, (0.35, D / 2 + 0.16, 0.42), g, axis="X", segs=12)
    p.cyl(0.15, 0.04, (0.15, D / 2 + 0.16, 0.42), g, axis="X", segs=12)
    p.box((0.12, 0.12, 0.08), (0.35, D / 2 + 0.16, 0.6), g, bevel=0.008)
    p.box((0.3, 0.28, 0.03), (0.35, D / 2 + 0.16, 0.25), g, bevel=0.004)
    p.box((0.08, 0.16, 0.62), (0.58, D / 2 + 0.1, 0.55), C.YELLOW, bevel=0.012)
    # pendant control station at the front right
    px_ = 0.68
    p.cyl(0.02, 0.55, (px_, -D / 2 + 0.05, zd + 0.27), M.CHROME, segs=6)
    p.box((0.18, 0.12, 0.26), (px_, -D / 2 + 0.02, zd + 0.65), C.PANEL, bevel=0.01)
    for k, (mat, r_) in enumerate(((C.PAINT_RED, 0.03), (C.PAINT_GREY, 0.018), (C.PL_BLACK, 0.018))):
        z = zd + 0.72 - k * 0.07
        p.lathe([(r_ * 0.7, 0.0), (r_ * 0.7, 0.015), (r_, 0.02), (r_ * 0.9, 0.035), (0.0, 0.04 if k == 0 else 0.03)],
                (px_, -D / 2 - 0.04, z), mat, segs=10, axis="-Y")
    plate(p, 0.1, 0.1, (px_ - 0.25, -D / 2 - 0.016, H - 0.2), atlas("pict_warn"), t=0.002)
    r = p.vrng("cans")
    if p.worn:
        p.remove(lid)
        lid = [p.lathe([(0.0, 0.0), (0.45, 0.0), (0.45, 0.03), (0.2, 0.06), (0.0, 0.07)], (0, 0, 0), M.STAINLESS, segs=20)]
        p.lay_on_floor(lid, rot=(14, 0, 0), at=(-0.75, -0.75))
        for k in (1, 2, 5, 9):
            a = 2 * math.pi * k / 12
            tin_can(p, (fx + math.cos(a) * 0.36, math.sin(a) * 0.36, zd + 0.024 + CAN_H / 2), rot=(0, 0, k * 13))
        tin_can(p, (0.17 + 0.1, -0.25, zd + 0.03 + CAN_D / 2), rot=(90, 0, 70), dent=0.01)
        tin_can(p, (0.08, -0.3, zd + 0.03 + CAN_H / 2), rot=(0, 18, 20))
        for i in range(6):
            can_on_floor(p, r.uniform(-0.5, 0.9), -0.55 - r.uniform(0, 0.35), r)
    else:
        for k in (0, 3, 4, 7, 8, 11):
            a = 2 * math.pi * k / 12
            tin_can(p, (fx + math.cos(a) * 0.36, math.sin(a) * 0.36, zd + 0.024 + CAN_H / 2), rot=(0, 0, k * 13))
        for i in range(3):
            tin_can(p, (sx + 0.32 + i * 0.081, -0.2, zd + 0.01 + CAN_H / 2))
    p.collider((0, 0.05, 1.0), (W + 0.1, D + 0.25, 2.0))


def _pallet(p: Prop, W: float = 1.2, D: float = 1.0) -> float:
    """Stringer pallet (GMA-style): 7 deck boards, 3 stringers, 3 bottom boards. Returns the deck top z."""
    wd = C.WOOD_OLD
    for k in range(3):
        p.box((W, 0.09, 0.016), (0, -D / 2 + 0.045 + k * (D - 0.09) / 2, 0.008), wd, bevel=0.002, grain="X")
    for k in range(3):
        y = -D / 2 + 0.019 + k * (D - 0.038) / 2
        st = p.box((W, 0.038, 0.09), (0, y, 0.016 + 0.045), wd, bevel=0.003, grain="X")
        del st
    for k in range(7):
        y = -D / 2 + 0.045 + k * (D - 0.09) / 6
        p.box((W, 0.09, 0.016), (0, y, 0.106 + 0.008), wd, bevel=0.002, grain="X")
    return 0.122


def cannery_can_pallet(p: Prop) -> None:
    """Pallet load of unlabelled tall cans (1.2 x 1.0 x 1.15): eight tiers on tier sheets, cardboard corner
    boards and a chipboard top, the whole load shrink wrapped. Worn: the wrap slit and peeled back down the
    front, part of the top tier taken, a few cans left standing on the tier below. Destroyed: the wrap
    shredded, the top three tiers slumped off sideways and cans spilled across the floor."""
    z0 = _pallet(p)
    nx, ny = 15, 12
    w, d = nx * CAN_D, ny * CAN_D
    x0, y0 = -w / 2, -d / 2
    tiers = 8
    top = z0 + tiers * CAN_TIER
    r = p.vrng("load")
    if not p.destroyed:
        if p.worn:
            stack_block(p, x0, x0 + w, y0, y0 + d, z0, top - CAN_TIER)
            stack_block(p, x0, x0 + w, y0 + 5 * CAN_D, y0 + d, top - CAN_TIER, top, top=False)
            for i in range(5):
                c = p.vrng("left")
                tin_can(p, (x0 + CAN_D * (2.5 + i * 2.3), y0 + CAN_D * (1.5 + (i % 2) * 2), top - CAN_TIER + CAN_H / 2 + 0.004),
                        rot=(0, 0, c.uniform(0, 90)))
            p.box((w + 0.01, 7 * CAN_D, 0.006), (0, y0 + 5 * CAN_D + 3.5 * CAN_D, top + 0.003), C.CARDBOARD, bevel=0.0)
        else:
            stack_block(p, x0, x0 + w, y0, y0 + d, z0, top, top=False)
            p.box((w + 0.01, d + 0.01, 0.006), (0, 0, top + 0.003), C.CARDBOARD, bevel=0.0)
        for sx in (-1, 1):
            for sy in (-1, 1):
                cb = p.prism([(0.0, 0.0), (0.05, 0.0), (0.05, 0.004), (0.004, 0.004), (0.004, 0.05), (0.0, 0.05)], top - z0 - 0.02,
                             C.CARDBOARD, plane="XY", offset=0.0)
                G.xform(cb.obj, rot=(0, 0, {(-1, -1): 0, (1, -1): 90, (1, 1): 180, (-1, 1): 270}[(sx, sy)]),
                        loc=(sx * (w / 2 + 0.004), sy * (d / 2 + 0.004), z0 + 0.01))
        path, nrm = rect_path(w + 0.03, d + 0.03, 0.04, per_side=6)

        def keep(u, v):
            if not p.worn:
                return True
            # u runs right side 0..0.22, back ..0.5, left ..0.72, front ..1: slit down the front and peeled away
            return not (0.78 < u < 0.95 and v > 0.25) and not (0.58 < u < 0.62 and v > 0.7)

        sheet(p, path, z0 - 0.03, top + 0.004, 9, C.WRAP, key="wrap", keep=keep, wrinkle=0.012, out_dirs=nrm, uv_scale=2.0,
              top_fold=0.09)
        if p.worn:
            flap = sheet(p, [(x0 + 0.05, y0 - 0.03), (x0 + 0.3, y0 - 0.05), (x0 + 0.5, y0 - 0.12)], z0 + 0.1, z0 + 0.4, 3, C.WRAP,
                         key="flap", wrinkle=0.02, out_dirs=[(0, -1), (0, -1), (0, -1)], closed=False)
            del flap
        p.collider((0, 0, (top + 0.01) / 2), (1.2, 1.0, top + 0.01))
    else:
        low = 5
        stack_block(p, x0, x0 + w, y0, y0 + d, z0, z0 + low * CAN_TIER)
        upper = [stack_block(p, x0, x0 + w, y0 + 3 * CAN_D, y0 + d, z0 + low * CAN_TIER, z0 + (low + 2) * CAN_TIER)]
        upper.append(p.box((w, d - 3 * CAN_D, 0.006), (0, y0 + 3 * CAN_D + (d - 3 * CAN_D) / 2, z0 + (low + 2) * CAN_TIER + 0.003),
                           C.CARDBOARD, bevel=0.0))
        p.rotate(upper, rot=(0, -9, 4), pivot=(x0 + w, 0, z0 + low * CAN_TIER))
        p.move(upper, (0.22, 0.05, -0.02))
        path, nrm = rect_path(w + 0.03, d + 0.03, 0.04, per_side=6)
        rr = p.rng("shred")
        holes = [rr.random() for _ in range(64)]
        sheet(p, path, z0 - 0.03, z0 + 0.35, 4, C.WRAP, key="wrap", keep=lambda u, v: holes[int(u * 31) + 32 * int(v * 2)] > 0.3,
              wrinkle=0.015, out_dirs=nrm, uv_scale=2.0)
        for i in range(18):
            can_on_floor(p, r.uniform(-1.0, 1.3), r.uniform(-1.1, -0.55), r)
        for i in range(6):
            can_on_floor(p, 0.75 + r.uniform(0, 0.5), r.uniform(-0.5, 0.5), r)
        p.collider((0.05, 0, 0.55), (1.35, 1.0, 1.1))


def cannery_sorting_table(p: Prop) -> None:
    """Stainless fish sorting table (2.4 x 0.9 x 0.9): a lipped tray top draining to one end, the drain
    hose down into a floor bucket, round legs with bullet feet, an undershelf with two fish totes, a white
    cutting board and a fillet knife, gurry stains. Worn: a tote tipped on the top, the knife gone, heavier
    stains. Destroyed: the legs at one end buckled so the top slumps to the floor, totes thrown off."""
    L, D, H = 2.4, 0.9, 0.9
    st = M.STAINLESS
    tbl = [p.hollow((L, D, 0.07), (0, 0, H - 0.035), st, wall=0.012, open_face="+Z", bevel=0.002)]
    tbl.append(p.box((L - 0.04, D - 0.04, 0.03), (0, 0, H - 0.085), st, bevel=0.002))
    tbl.append(plate(p, 0.7, 0.45, (-0.4, 0.05, H - 0.057), atlas("fish_slime", 4), t=0.002, facing="+Z", wear=0.0))
    if p.worn:
        tbl.append(plate(p, 0.6, 0.4, (0.55, -0.1, H - 0.0565), atlas("fish_slime", 4), t=0.002, facing="+Z", wear=0.0,
                         rot=(-90, 0, 180)))
    dx = L / 2 - 0.12
    tbl.append(p.cyl(0.04, 0.012, (dx, 0, H - 0.063), M.CAST_IRON, segs=12))
    hose = p.tube([(dx, 0, H - 0.08), (dx, 0, 0.55), (dx + 0.05, 0, 0.35), (dx + 0.1, 0.05, 0.3)], 0.022, M.RUBBER, segs=8,
                  fillet_r=0.12)
    if p.destroyed:
        p.remove(hose)
        p.lay_on_floor([p.tube([(0, 0, 0), (0.3, 0.05, 0), (0.55, 0.0, 0)], 0.022, M.RUBBER, segs=8, fillet_r=0.1)], at=(dx - 0.2, 0.3),
                       yaw=40)
    p.lathe([(0.0, 0.0), (0.13, 0.0), (0.15, 0.32), (0.155, 0.33), (0.14, 0.33), (0.125, 0.012), (0.0, 0.012)], (dx + 0.1, 0.05, 0.0),
            C.TOTE_GREY, segs=14)
    legs = []
    for x in (-L / 2 + 0.1, 0.0, L / 2 - 0.1):
        for sy in (-1, 1):
            y = sy * (D / 2 - 0.08)
            legs.append(p.cyl(0.021, H - 0.12, (x, y, (H - 0.12) / 2 + 0.03), st, segs=8))
            legs.append(p.lathe([(0.0, 0.0), (0.02, 0.0), (0.025, 0.03), (0.021, 0.06)], (x, y, 0.0), st, segs=8, cap_top=False))
        legs.append(p.cyl(0.016, D - 0.16, (x, 0, 0.2), st, axis="Y", segs=6))
    shelf = p.box((L - 0.2, D - 0.18, 0.02), (0, 0, 0.21), st, bevel=0.003)
    for sy in (-1, 1):
        p.cyl(0.016, L - 0.2, (0, sy * (D / 2 - 0.08), 0.2), st, axis="X", segs=6)
    totes = []
    if not p.destroyed:
        totes += tote(p, (-0.5, 0, 0.22), yaw=0, mat=C.TOTE_BLUE, h=0.28)
        if not p.worn:
            totes += tote(p, (0.45, 0.02, 0.22), yaw=0, mat=C.TOTE_GREY, h=0.28)
    tbl.append(p.box((0.5, 0.35, 0.015), (0.35, -0.05, H - 0.0475), M.PL_WHITE, bevel=0.003))
    if not p.worn:
        tbl.append(p.box((0.18, 0.016, 0.002), (0.45, -0.12, H - 0.039), M.STAINLESS, bevel=0.0))
        tbl.append(p.box((0.12, 0.022, 0.02), (0.3, -0.12, H - 0.03), M.PL_BLACK, bevel=0.004))
    elif not p.destroyed:
        tbl += tote(p, (0.0, 0.0, 0.0), mat=C.TOTE_GREY, h=0.28, rot=(97, 0, 0))
        lo, hi = p.bounds(tbl[-4:])
        p.move(tbl[-4:], (-0.6 - (lo.x + hi.x) / 2, 0.05 - (lo.y + hi.y) / 2, H - 0.055 - lo.z))
    if p.destroyed:
        r = p.vrng("collapse")
        p.remove([q for q in legs if q.obj.data.vertices[0].co.x > -0.5])
        p.remove(shelf)
        for i in range(2):
            b = p.cyl(0.021, 0.7, (0, 0, 0), st, segs=8)
            p.lay_on_floor([b], rot=(0, 90, 0), at=(0.2 + i * 0.5, -0.2 + i * 0.35), yaw=r.uniform(-40, 40))
        p.settle(tbl, (-L / 2 + 0.1, 0, H - 0.1), (0, 1, 0), max_deg=30)
        for i, mat in enumerate((C.TOTE_BLUE, C.TOTE_GREY)):
            grp = tote(p, (0, 0, 0), mat=mat, h=0.28)
            p.lay_on_floor(grp, rot=(0, 0 if i == 0 else 100, 0), at=(0.3 + i * 0.8, -0.85 - i * 0.2), yaw=r.uniform(-30, 30))
        p.collider((0, -0.2, 0.45), (L + 0.2, D + 0.6, 0.9))
    else:
        p.collider((0, 0, H / 2), (L, D, H))


def cannery_tote_stack(p: Prop) -> None:
    """Stacked plastic fish totes (0.85 x 1.3 x 0.56): five tapered tubs, blue and grey, each riding on the
    rim of the one below, a little out of true. Worn: the top two lifted off, one tipped on its side on the
    floor beside the stack, the other upside down in front of it."""
    r = p.rng("stack")
    mats = [C.TOTE_BLUE, C.TOTE_BLUE, C.TOTE_GREY, C.TOTE_BLUE, C.TOTE_GREY]
    n = 3 if p.worn else 5
    for i in range(n):
        tote(p, (r.uniform(-0.02, 0.02), r.uniform(-0.015, 0.015), i * 0.26), yaw=r.uniform(-3, 3), mat=mats[i])
    if p.worn:
        a = tote(p, (0, 0, 0), mat=mats[3])
        p.lay_on_floor(a, rot=(0, 92, 0), at=(0.62, -0.25), yaw=-18)
        b = tote(p, (0, 0, 0), mat=mats[4])
        p.lay_on_floor(b, rot=(180, 0, 0), at=(-0.2, -0.75), yaw=24)
        p.collider((0.15, -0.25, 0.4), (1.3, 1.1, 0.8))
    else:
        p.collider((0, 0, 0.67), (0.84, 0.56, 1.34))


# ================================================================================================
# Water works pump house
# ================================================================================================


def _pipe_run(p: Prop, pts, r: float, mat: str = C.PIPE, fillet: float | None = None) -> core.Part:
    return p.tube(pts, r, mat, segs=12, fillet_r=fillet if fillet is not None else r * 1.6, steps=3, uv="cyl", uv_axis="X",
                  wear=0.8)


def pump_station_pump(p: Prop) -> None:
    """Horizontal end-suction centrifugal pump and its motor (2.6 x 1.55 x 1.3) on a steel baseplate on a
    concrete plinth: a finned TEFC motor with its fan cowl and terminal box, the coupling under a yellow
    guard, the bearing frame, the volute with the suction nozzle out the end into a flanged elbow down
    through the floor and the discharge rising through a check valve and a gate valve to a header elbow at
    the back; gauges on suction and discharge. Worn: paint gone to rust and scale, the coupling guard off
    and dropped against the plinth, a mineral stain down the volute."""
    pc = C.PUMP
    p.box((2.5, 1.1, 0.3), (0, 0, 0.15), C.CONCRETE, bevel=0.02)
    zb = 0.3
    for sy in (-1, 1):
        p.box((2.2, 0.1, 0.1), (0, sy * 0.33, zb + 0.05), pc, bevel=0.004, grain="X")
    for x in (-0.95, -0.2, 0.55, 1.0):
        p.box((0.08, 0.66, 0.1), (x, 0, zb + 0.05), pc, bevel=0.004, grain="Y")
    for x in (-1.0, 1.0):
        for sy in (-1, 1):
            p.cyl(0.018, 0.04, (x, sy * 0.33, zb + 0.12), C.STEEL, segs=6)
    zt = zb + 0.1
    # motor (+X): finned frame as an extruded star, cowl, end bell, feet, terminal box, eye bolt
    ax = 0.55
    mz = zt + 0.36
    star = []
    for k in range(36):
        a = 2 * math.pi * k / 36
        rr = 0.31 if k % 2 == 0 else 0.285
        star.append((math.cos(a) * rr, math.sin(a) * rr))
    body = p.prism(star, 0.62, pc, plane="YZ", offset=ax)
    G.xform(body.obj, loc=(0, 0, mz))
    p.lathe([(0.0, -0.01), (0.27, -0.01), (0.29, 0.03), (0.29, 0.05), (0.15, 0.08), (0.0, 0.09)], (ax, 0, mz), pc, segs=20, axis="-X")
    p.lathe([(0.0, 0.0), (0.3, 0.0), (0.3, 0.2), (0.27, 0.24), (0.0, 0.25)], (ax + 0.62, 0, mz), pc, segs=20, axis="X")
    for k in range(10):
        p.box((0.005, 0.5, 0.012), (ax + 0.865, 0, mz - 0.22 + k * 0.048), C.STEEL, bevel=0.0, wear=0.4)
    for x in (ax + 0.1, ax + 0.52):
        p.box((0.12, 0.56, 0.06), (x, 0, zt + 0.03), pc, bevel=0.005)
        p.box((0.08, 0.1, 0.2), (x, -0.2, zt + 0.13), pc, bevel=0.005)
        p.box((0.08, 0.1, 0.2), (x, 0.2, zt + 0.13), pc, bevel=0.005)
    p.box((0.22, 0.2, 0.16), (ax + 0.3, 0.0, mz + 0.36), pc, bevel=0.012)
    p.cyl(0.03, 0.1, (ax + 0.3, -0.14, mz + 0.38), C.STEEL, axis="Y", segs=6)
    torus(p, 0.035, 0.008, (ax + 0.15, 0, mz + 0.35), C.STEEL, axis="Y", segs=10, rsegs=4)
    plate(p, 0.16, 0.08, (ax + 0.33, -0.3, mz + 0.06), atlas("nameplate"), t=0.003, facing="-Y", rot=(-12, 0, 0))
    p.cyl(0.04, 0.12, (ax - 0.06, 0, mz), C.STEEL, axis="X", segs=8)
    # coupling + guard
    p.cyl(0.09, 0.12, (ax - 0.17, 0, mz), M.CAST_IRON, axis="X", segs=10)
    guard = [p.lathe([(0.0, 0.0), (0.15, 0.0), (0.15, 0.4), (0.0, 0.4)], (ax - 0.37, 0, mz), C.YELLOW, segs=10, axis="X")]
    guard.append(p.box((0.36, 0.3, 0.02), (ax - 0.17, 0, zt + 0.01), C.YELLOW, bevel=0.003))
    for x in (ax - 0.34, ax):
        guard.append(p.box((0.03, 0.06, mz - zt - 0.15), (x, 0.12, zt + (mz - zt - 0.15) / 2), C.YELLOW, bevel=0.003))
    # bearing frame + volute
    p.cyl(0.03, 0.2, (ax - 0.32, 0, mz), C.STEEL, axis="X", segs=6)
    p.cyl(0.11, 0.4, (-0.05, 0, mz), pc, axis="X", segs=12)
    p.box((0.3, 0.32, mz - zt - 0.1), (-0.05, 0, zt + (mz - zt - 0.1) / 2), pc, bevel=0.01)
    vx = -0.42
    p.lathe([(0.12, -0.15), (0.36, -0.12), (0.4, -0.06), (0.41, 0.0), (0.4, 0.06), (0.36, 0.12), (0.12, 0.15)], (vx, 0, mz), pc,
            segs=20, axis="X")
    p.lathe([(0.1, -0.13), (0.3, -0.11), (0.34, 0.0), (0.3, 0.11), (0.1, 0.13)], (vx, -0.05, mz + 0.07), pc, segs=16, axis="X")
    p.box((0.3, 0.5, 0.06), (vx, 0, zt + 0.03), pc, bevel=0.006)
    p.box((0.12, 0.3, mz - zt - 0.35), (vx, 0, zt + (mz - zt - 0.35) / 2 + 0.03), pc, bevel=0.006)
    rivet(p, (vx + 0.155, 0.0, mz + 0.42), (0, 0, 1), 0.015, C.STEEL)
    # suction: axial out the end (-X), flanges, elbow down into the floor
    p.cyl(0.13, 0.12, (vx - 0.21, 0, mz), pc, axis="X", segs=14)
    flange(p, (vx - 0.29, 0, mz), 0.13, "X", pc, bolts=8)
    _pipe_run(p, [(vx - 0.3, 0, mz), (-1.15, 0, mz), (-1.15, 0, 0.0)], 0.13, fillet=0.22)
    flange(p, (-0.82, 0, mz), 0.13, "X", C.PIPE, bolts=8)
    flange(p, (-1.15, 0, 0.32), 0.13, "Z", C.PIPE, bolts=8)
    gauge(p, (-0.72, -0.17, mz + 0.18), 0.06, "gauge_black", "-Y", depth=0.035, stem=0.03)
    p.tube([(-0.72, -0.12, mz + 0.18), (-0.72, -0.04, mz + 0.1)], 0.008, C.BRASS, segs=5)
    # discharge: tangential nozzle up, check valve, gate valve, elbow to the back
    dz = mz + 0.42
    p.cyl(0.1, 0.12, (vx, 0, dz - 0.02), pc, segs=14)
    flange(p, (vx, 0, dz + 0.05), 0.1, "Z", pc, bolts=8)
    gate_valve(p, (vx, 0, dz + 0.22), 0.1, matrix=Matrix.Rotation(math.pi / 2, 4, "Y") @ Matrix.Rotation(math.pi / 2, 4, "X"),
               body=C.PIPE, wheel=C.PAINT_RED, rising=True)
    _pipe_run(p, [(vx, 0, dz + 0.38), (vx, 0, 1.25), (vx, 0.3, 1.25), (vx, 0.78, 1.25)], 0.1, fillet=0.18)
    flange(p, (vx, 0.6, 1.25), 0.1, "Y", C.PIPE, bolts=8)
    flange(p, (vx, 0.77, 1.25), 0.1, "Y", C.PIPE, bolts=8)
    gauge(p, (vx + 0.2, -0.05, dz + 0.5), 0.07, "gauge_red", "-Y", depth=0.04, stem=0.03)
    p.tube([(vx + 0.2, 0.0, dz + 0.5), (vx + 0.2, 0.0, dz + 0.45), (vx + 0.1, 0.0, dz + 0.45)], 0.008, C.BRASS, segs=5)
    # conduit from the terminal box down to the floor at the back
    p.tube([(ax + 0.3, 0.1, mz + 0.44), (ax + 0.3, 0.45, mz + 0.44), (ax + 0.3, 0.58, mz + 0.2), (ax + 0.3, 0.58, 0.0)], 0.022, C.GALV,
           segs=6, fillet_r=0.1)
    if p.worn:
        p.remove(guard)
        g = [p.lathe([(0.0, 0.0), (0.15, 0.0), (0.15, 0.4), (0.0, 0.4)], (0, 0, 0), C.YELLOW, segs=10, axis="X")]
        p.lay_on_floor(g, rot=(0, 0, 0), at=(ax - 0.2, -0.72), yaw=18)
        plate(p, 0.3, 0.25, (vx, -0.415, mz - 0.05), atlas("fish_slime", 6), t=0.002, wear=0.0)
    p.collider((0, 0, 0.15), (2.5, 1.1, 0.3))
    p.collider((0.1, 0, 0.8), (2.4, 0.9, 1.0))
    p.collider((vx, 0.35, 1.25), (0.35, 0.9, 0.3))


def _manifold(p: Prop, wall: bool) -> None:
    pc = C.PIPE
    r = 0.13 if not wall else 0.1
    if not wall:
        zh = 0.62
        y = 0.0
        _pipe_run(p, [(-1.45, y, zh), (1.45, y, zh)], r)
        flange(p, (-1.45, y, zh), r, "X", pc)
        flange(p, (1.45, y, zh), r, "X", pc)
        p.cyl(r * 1.75, 0.03, (1.49, y, zh), pc, axis="X", segs=12)
        for x in (-0.9, 0.9):
            p.box((0.3, 0.3, 0.06), (x, y, 0.03), C.CONCRETE, bevel=0.01)
            p.box((0.08, 0.08, zh - r - 0.06), (x, y, 0.06 + (zh - r - 0.06) / 2), pc, bevel=0.004, grain="Z")
            p.box((0.36, 0.12, 0.03), (x, y, zh - r - 0.015), pc, bevel=0.004)
            torus(p, r + 0.012, 0.008, (x, y, zh), C.STEEL, axis="X", segs=12, rsegs=4, arc=180, a0=0)
        for k, x in enumerate((-0.45, 0.45)):
            # branch out the front, a gate valve, an elbow down into the floor
            p.cyl(r * 0.95, 0.2, (x, -0.15, zh), pc, axis="Y", segs=12)
            gate_valve(p, (x, -0.47, zh), r * 0.8, matrix=Matrix.Rotation(-math.pi / 2, 4, "Z"), body=pc,
                       wheel=C.PAINT_RED if k == 0 else C.PAINT_BLACK)
            _pipe_run(p, [(x, -0.62, zh), (x, -0.9, zh), (x, -0.9, 0.0)], r * 0.8, fillet=0.18)
            flange(p, (x, -0.7, zh), r * 0.8, "Y", pc)
            flange(p, (x, -0.9, 0.12), r * 0.8, "Z", pc)
        # riser to the ceiling at the back, a gauge tapping and a hose bib
        p.cyl(r * 0.95, 0.25, (0.0, 0.18, zh), pc, axis="Y", segs=12)
        _pipe_run(p, [(0, 0.3, zh), (0, 0.45, zh), (0, 0.45, 1.6)], r, fillet=0.2)
        flange(p, (0, 0.45, 1.0), r, "Z", pc)
        gauge(p, (-0.2, -0.05, zh + 0.27), 0.07, "gauge", "-Y", depth=0.04, stem=0.03)
        p.tube([(-0.2, 0.0, zh + 0.27), (-0.2, 0.0, zh + 0.1)], 0.01, C.BRASS, segs=5)
        p.lathe([(0.02, 0.0), (0.02, 0.06), (0.03, 0.08), (0.0, 0.1)], (1.2, -r, zh - 0.02), C.BRASS, segs=8, axis="-Y")
        p.collider((0, -0.2, 0.55), (3.0, 1.4, 1.1))
        p.collider((0, 0.45, 1.2), (0.35, 0.35, 0.8))
        return
    # wall run: two pipes on brackets 0.3 m off the wall, a butterfly valve on each with a gear operator
    ys = -0.3
    for k, (zp, mat) in enumerate(((0.35, pc), (1.15, C.PAINT_OLIVE))):
        _pipe_run(p, [(-1.3, ys, zp), (1.3, ys, zp)], r, mat)
        for x in (-1.3, 1.3):
            flange(p, (x, ys, zp), r, "X", mat)
        for x in (-1.0, 1.0):
            p.box((0.06, abs(ys) - r, 0.06), (x, ys / 2 - r / 2, zp - r - 0.03), C.STEEL, bevel=0.004, grain="Y")
            p.box((0.16, 0.012, 0.2), (x, -0.006, zp - r - 0.03), C.STEEL, bevel=0.003)
            torus(p, r + 0.01, 0.007, (x, ys, zp), C.STEEL, axis="X", segs=12, rsegs=4, arc=180, a0=180)
        bx = -0.25 + k * 0.5
        flange(p, (bx - 0.06, ys, zp), r, "X", mat)
        flange(p, (bx + 0.06, ys, zp), r, "X", mat)
        p.cyl(r * 1.4, 0.1, (bx, ys, zp), M.CAST_IRON, axis="X", segs=12)
        p.cyl(0.03, 0.12, (bx, ys, zp + r * 1.4 + 0.05), M.CAST_IRON, segs=6)
        p.box((0.16, 0.14, 0.14), (bx, ys, zp + r * 1.4 + 0.17), M.CAST_IRON, bevel=0.01)
        p.cyl(0.02, 0.12, (bx, ys - 0.13, zp + r * 1.4 + 0.17), C.STEEL, axis="Y", segs=6)
        handwheel(p, (bx, ys - 0.2, zp + r * 1.4 + 0.17), 0.13, "-Y", C.PAINT_RED)
    # cross tie between the runs with its own gate valve, a gauge
    _pipe_run(p, [(0.9, ys, 0.35), (0.9, ys, 1.15)], r * 0.7, pc)
    gate_valve(p, (0.9, ys, 0.75), r * 0.7, matrix=Matrix.Rotation(math.pi / 2, 4, "Y") @ Matrix.Rotation(math.pi / 2, 4, "X"), body=pc,
               wheel=C.PAINT_RED)
    gauge(p, (-0.8, ys - r - 0.08, 1.15 + 0.15), 0.07, "gauge", "-Y", depth=0.04, stem=0.03)
    p.tube([(-0.8, ys - r - 0.03, 1.3), (-0.8, ys, 1.3), (-0.8, ys, 1.15 + r)], 0.009, C.BRASS, segs=5, fillet_r=0.02)
    p.collider((0, -0.25, 0.8), (2.7, 0.5, 1.6))


def pump_pipe_manifold(p: Prop) -> None:
    """Floor manifold (3.0 x 1.6 x 1.4): a 10-inch potable-water header (AWWA light blue) on concrete-footed
    saddles, two branches out the front through gate valves (rising stems, red and black handwheels) and
    flanged elbows down into the floor, a riser at the back to the ceiling, a gauge tap and a hose bib.
    Worn: the paint gone to rust bloom and white mineral crust (material wear)."""
    _manifold(p, False)


def pump_pipe_manifold_wall(p: Prop) -> None:
    """Wall pipe run (2.75 x 1.5 x 0.55, origin on the wall plane): a treated-water line (light blue) and a
    raw-water line (olive) on wall brackets with U-straps, a butterfly valve with a gear operator and
    handwheel on each, a valved cross tie between them and a pressure gauge. Hang at ~0.2 m."""
    _manifold(p, True)


def _cylinder(p: Prop, c, *, hood: bool, h: float = 1.35, r: float = 0.135) -> list:
    """150 lb chlorine cylinder: grey body, yellow shoulder, the valve, a protective hood (or the yoke
    regulator when in service)."""
    x, y, z = c
    out = [p.lathe([(0.0, 0.0), (r - 0.02, 0.0), (r, 0.02), (r, h - 0.22), (r * 0.8, h - 0.1), (0.05, h - 0.04), (0.0, h - 0.04)],
                   (x, y, z), C.CYL_GREY, segs=14)]
    out.append(p.lathe([(r + 0.002, h - 0.3), (r + 0.002, h - 0.22), (r * 0.8 + 0.002, h - 0.1), (0.05, h - 0.035)], (x, y, z),
                       C.YELLOW, segs=14, cap_bottom=False, cap_top=False))
    out.append(p.lathe([(r + 0.004, 0.02), (r + 0.006, 0.05), (r + 0.004, 0.08)], (x, y, z), C.STEEL, segs=14, cap_bottom=False,
                       cap_top=False))
    out.append(p.cyl(0.025, 0.08, (x, y, z + h), C.BRASS, segs=8))
    if hood:
        out.append(p.lathe([(0.0, 0.0), (0.08, 0.0), (0.085, 0.14), (0.06, 0.17), (0.0, 0.18)], (x, y, z + h - 0.06), C.YELLOW, segs=10))
    else:
        out.append(p.box((0.07, 0.06, 0.12), (x, y - 0.05, z + h + 0.06), M.CAST_IRON, bevel=0.008))
        out.append(p.cyl(0.05, 0.05, (x, y - 0.1, z + h + 0.08), C.PL_BLACK, axis="Y", segs=10))
    return out


def pump_chlorinator(p: Prop) -> None:
    """Gas chlorinator corner (1.4 x 2.0 x 0.95, stands against a wall): two chlorine cylinders on a
    platform scale with its dial head, chained to the wall rail, a spare with its hood on, the regulator
    panel on a backboard (rotameter tube, vacuum regulator, PVC lines, the ejector), a toxic-gas placard
    and a gas mask on a hook. Worn: the spare toppled and lying on the floor, a chain hanging loose, the
    mask dropped."""
    yb = 0.38
    # backboard on the wall
    p.box((1.3, 0.025, 1.1), (0, yb + 0.03, 1.45), M.PARTICLE, bevel=0.003, wear=0.4)
    for x in (-0.62, 0.62):
        p.box((0.04, 0.03, 1.1), (x, yb + 0.005, 1.45), C.PANEL, bevel=0.003, grain="Z")
    # wall rail + chains
    p.box((1.3, 0.04, 0.05), (0, yb, 1.05), C.STEEL, bevel=0.004, grain="X")
    p.box((1.3, 0.04, 0.05), (0, yb, 0.55), C.STEEL, bevel=0.004, grain="X")
    # platform scale
    p.box((0.75, 0.45, 0.08), (-0.2, 0.08, 0.04), C.PANEL, bevel=0.008)
    p.box((0.7, 0.4, 0.012), (-0.2, 0.08, 0.086), C.STEEL, bevel=0.002)
    p.box((0.06, 0.06, 0.75), (-0.62, 0.22, 0.45), C.PANEL, bevel=0.004, grain="Z")
    p.box((0.2, 0.08, 0.22), (-0.62, 0.2, 0.92), C.PANEL, bevel=0.012)
    gauge(p, (-0.62, 0.155, 0.93), 0.08, "gauge", "-Y", depth=0.02, stem=0.0)
    cyls = []
    for x in (-0.36, -0.04):
        cyls += _cylinder(p, (x, 0.12, 0.092), hood=False)
    spare = _cylinder(p, (0.5, 0.15, 0.0), hood=True)
    links = []
    for x in (-0.2, 0.5):
        for z, rr in ((1.0, 0.18 if x < 0 else 0.15), (0.6, 0.18 if x < 0 else 0.15)):
            links.append(torus(p, rr if x < 0 else 0.15, 0.006, (x, 0.12 if x < 0 else 0.15, z), p_chain_mat(), segs=14, rsegs=3,
                               arc=200, a0=-10))
    # regulator panel: rotameter, regulator, lines
    p.box((0.18, 0.06, 0.45), (-0.1, yb - 0.01, 1.55), C.PL_BLACK, bevel=0.01)
    p.box((0.03, 0.01, 0.34), (-0.1, yb - 0.045, 1.55), M.GLASS, bevel=0.0, wear=0.0)
    p.cyl(0.012, 0.02, (-0.1, yb - 0.04, 1.5), C.PL_ORANGE, segs=6)
    p.cyl(0.11, 0.08, (0.2, yb - 0.03, 1.55), M.PL_WHITE, axis="Y", segs=14)
    p.cyl(0.03, 0.06, (0.2, yb - 0.09, 1.55), C.PL_BLACK, axis="Y", segs=8)
    gauge(p, (0.45, yb - 0.05, 1.7), 0.06, "gauge_black", "-Y", depth=0.03, stem=0.03)
    for x in (-0.36, -0.04):
        p.tube([(x, 0.02, 1.53), (x, 0.0, 1.7), (x * 0.5 - 0.05, yb - 0.04, 1.85), (-0.1, yb - 0.04, 1.8)], 0.008, M.PL_WHITE, segs=5,
               fillet_r=0.1)
    p.tube([(-0.1, yb - 0.04, 1.32), (-0.1, yb - 0.04, 1.2), (0.2, yb - 0.04, 1.2), (0.2, yb - 0.04, 1.45)], 0.01, M.PL_WHITE, segs=5,
           fillet_r=0.05)
    p.tube([(0.3, yb - 0.04, 1.55), (0.6, yb - 0.04, 1.55), (0.6, yb - 0.04, 0.0)], 0.013, M.PL_GREY, segs=6, fillet_r=0.06)
    plate(p, 0.22, 0.22, (-0.42, yb + 0.015, 1.78), atlas("pict_gas"), t=0.002, facing="-Y")
    plate(p, 0.16, 0.16, (0.45, yb + 0.015, 1.25), atlas("pict_warn"), t=0.002, facing="-Y")
    # gas mask on a hook
    p.cyl(0.006, 0.05, (0.42, yb, 1.95), C.STEEL, axis="Y", segs=5)
    mask = [p.rbox((0.17, 0.09, 0.2), (0.42, yb - 0.06, 1.82), C.PL_BLACK, radius=0.05, inner=(2, 1, 2))]
    for sx in (-1, 1):
        mask.append(p.cyl(0.03, 0.02, (0.42 + sx * 0.04, yb - 0.11, 1.86), M.GLASS, axis="Y", segs=10))
    mask.append(p.cyl(0.045, 0.08, (0.42, yb - 0.13, 1.74), C.PL_YELLOW if False else C.YELLOW, axis="Y", segs=10))
    if p.worn:
        p.remove(spare)
        sp = _cylinder(p, (0, 0, 0), hood=True)
        p.lay_on_floor(sp, rot=(0, 90, 0), at=(0.35, -0.45), yaw=-12)
        p.remove(links[2])
        lo, hi = p.bounds(mask)
        p.lay_on_floor(mask, rot=(80, 0, 0), at=(-0.6, -0.3), yaw=30)
        p.tube([(0.5 - 0.15, 0.15 + 0.02, 1.0), (0.38, -0.05, 0.75), (0.4, -0.1, 0.45)], 0.006, C.CHAIN, segs=3)
        p.collider((0, -0.1, 0.9), (1.4, 1.0, 1.8))
    else:
        p.collider((0, 0.1, 1.0), (1.4, 0.65, 2.0))


def p_chain_mat() -> str:
    return C.CHAIN


def pump_control_panel(p: Prop) -> None:
    """Wall control cabinet (1.0 x 1.2 x 0.32, origin on the wall plane): ANSI-grey steel with a drip lip,
    the door carries the pump mimic diagram with run lamps in each pump symbol, two ammeters, hand-off-auto
    selector switches and the quarter-turn latches. Hang at ~0.9 m. Worn: the door hanging open on its
    lower hinge, the relay rack, terminal strips and wiring looms inside, a lamp lens smashed."""
    W, H, D = 1.0, 1.2, 0.3
    pg = C.PANEL
    p.hollow((W, D, H), (0, -D / 2, H / 2), pg, wall=0.015, open_face="-Y", bevel=0.004)
    p.box((W + 0.04, D + 0.03, 0.025), (0, -D / 2 - 0.015, H + 0.012), pg, bevel=0.005)
    p.box((W - 0.06, 0.01, H - 0.06), (0, -0.02, H / 2), M.PL_WHITE, bevel=0.0, wear=0.0)
    yf = -D - 0.02
    door = [p.box((W - 0.01, 0.02, H - 0.01), (0, -D - 0.01, H / 2), pg, bevel=0.005)]
    door.append(plate(p, 0.8, 0.4, (0, yf - 0.002, H * 0.62), atlas("mimic"), t=0.003))
    # lamps in the pump symbols (atlas px 130 / 230 / 330 of 512 at y 150 of 256)
    lamps = []
    for k, px in enumerate((130, 230, 330)):
        x = -0.4 + 0.8 * px / 512
        z = H * 0.62 + 0.2 - 0.4 * 150 / 256
        door.append(p.cyl(0.024, 0.02, (x, yf - 0.013, z), M.CHROME, axis="Y", segs=10))
        lamps.append(p.lathe([(0.018, 0.0), (0.016, 0.012), (0.0, 0.018)], (x, yf - 0.023, z),
                             (C.LENS_G, C.LENS_R, C.LENS_A)[k], segs=10, axis="-Y"))
    door += lamps
    for k, x in enumerate((-0.25, 0.25)):
        door.append(p.box((0.14, 0.03, 0.14), (x, yf - 0.015, 0.33), M.PL_BLACK, bevel=0.006))
        door.append(disc_face(p, 0.055, 0.003, (x, yf - 0.031, 0.335), atlas("gauge_black" if k else "gauge"), axis="-Y", segs=14))
    for k in range(3):
        x = -0.25 + k * 0.25
        door.append(p.cyl(0.03, 0.02, (x, yf - 0.01, 0.13), M.PL_BLACK, axis="Y", segs=10))
        door.append(p.box((0.012, 0.03, 0.045), (x, yf - 0.035, 0.13), M.PL_BLACK, bevel=0.003))
    for z in (0.25, H - 0.25):
        door.append(p.cyl(0.018, 0.02, (W / 2 - 0.06, yf - 0.01, z), M.CHROME, axis="Y", segs=8))
        p.cyl(0.012, 0.08, (-W / 2 - 0.005, -D - 0.01, z), M.CHROME, segs=6)
    door.append(plate(p, 0.14, 0.14, (W / 2 - 0.12, yf - 0.002, H - 0.12), atlas("pict_warn"), t=0.002))
    p.tube([(0.3, -0.15, 0.0), (0.3, -0.15, -0.02)], 0.03, C.GALV, segs=8)
    p.tube([(-0.3, -0.12, 0.0), (-0.3, -0.12, -0.3)], 0.025, C.GALV, segs=8)
    if p.worn:
        # the guts: relays on DIN rails, terminal strips, looms
        for k, z in enumerate((0.95, 0.72, 0.49)):
            p.box((W - 0.15, 0.012, 0.035), (0, -0.035, z - 0.06), C.GALV, bevel=0.0)
            for i in range(7):
                p.box((0.07, 0.07, 0.09), (-0.33 + i * 0.11, -0.065, z), M.PL_BEIGE if (i + k) % 3 else M.PL_GREY, bevel=0.006)
        for i in range(12):
            p.box((0.012, 0.03, 0.05), (-0.3 + i * 0.05, -0.05, 0.25), M.PL_GREY, bevel=0.002)
        p.tube([(-0.43, -0.05, 1.05), (-0.43, -0.06, 0.3), (-0.3, -0.06, 0.22)], 0.025, M.PL_BLACK, segs=6, fillet_r=0.08)
        p.tube([(0.43, -0.05, 1.05), (0.44, -0.07, 0.4), (0.3, -0.06, 0.24)], 0.02, M.PL_GREY, segs=6, fillet_r=0.08)
        door.remove(lamps[1])
        p.remove(lamps[1])
        F.hang(p, door, -W / 2 - 0.005, -D - 0.02, 0.25, 100.0, -12.0)
    p.collider((0, -D / 2 - 0.01, H / 2), (W, D + 0.03, H))


# ================================================================================================
# Quarry office
# ================================================================================================


def quarry_magazine(p: Prop) -> None:
    """Type 2 explosives day box (1.3 x 0.95 x 1.0): a squat welded steel box painted oxide red on two
    timber skids, a hinged lid on a piano hinge, a padlock hood shielding the hasp, lifting lugs at the
    corners, wood lining inside, orange explosive-diamond and no-flame pictograms (no words). Worn: the hasp
    cut, lid propped open on its stay over a few empty fibreboard cases. Destroyed: the lid torn off and on
    the ground, the box dented, the lining split."""
    W, D, H = 1.2, 0.8, 0.82
    rd = C.MAGAZINE
    for sy in (-1, 1):
        p.box((W + 0.12, 0.1, 0.1), (0, sy * (D / 2 - 0.1), 0.05), C.WOOD_OLD, bevel=0.008, grain="X")
    zb = 0.1
    p.hollow((W, D, H), (0, 0, zb + H / 2), rd, wall=0.02, open_face="+Z", bevel=0.004)
    p.box((W - 0.04, D - 0.04, 0.02), (0, 0, zb + 0.03), C.WOOD_OLD, bevel=0.002, grain="X")
    for sx in (-1, 1):
        p.box((0.02, D - 0.05, H - 0.06), (sx * (W / 2 - 0.03), 0, zb + H / 2), C.WOOD_OLD, bevel=0.002, grain="Y")
    for sy in (-1, 1):
        p.box((W - 0.08, 0.02, H - 0.06), (0, sy * (D / 2 - 0.03), zb + H / 2), C.WOOD_OLD, bevel=0.002, grain="X")
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.box((0.05, 0.012, 0.06), (sx * (W / 2 - 0.08), sy * (D / 2 + 0.006), zb + H - 0.08), rd, bevel=0.003)
    ztop = zb + H
    lid = [p.box((W + 0.05, D + 0.05, 0.03), (0, 0, ztop + 0.015), rd, bevel=0.006)]
    lid.append(p.box((W + 0.05, 0.02, 0.07), (0, -D / 2 - 0.035, ztop - 0.005), rd, bevel=0.004))
    for sx in (-1, 1):
        lid.append(p.box((0.02, D + 0.05, 0.07), (sx * (W / 2 + 0.035), 0, ztop - 0.005), rd, bevel=0.004))
    lid.append(plate(p, 0.2, 0.2, (0, -0.15, ztop + 0.031), atlas("pict_flame"), t=0.002, facing="+Z"))
    p.cyl(0.012, W - 0.1, (0, D / 2 + 0.02, ztop), C.STEEL, axis="X", segs=6)
    # hasp + padlock hood on the front
    hood = [p.hollow((0.16, 0.08, 0.14), (0, -D / 2 - 0.04, ztop - 0.09), rd, wall=0.008, open_face="-Z", bevel=0.002)]
    hasp = [p.box((0.05, 0.012, 0.12), (0, -D / 2 - 0.05, ztop - 0.02), C.STEEL, bevel=0.002)]
    if not p.worn:
        hasp.append(p.box((0.05, 0.025, 0.06), (0, -D / 2 - 0.055, ztop - 0.13), C.BRASS, bevel=0.006))
        hasp.append(torus(p, 0.017, 0.005, (0, -D / 2 - 0.055, ztop - 0.1), M.CHROME, axis="Y", segs=8, rsegs=3, arc=180))
    plate(p, 0.32, 0.32, (-0.35, -D / 2 - 0.002, zb + 0.4), atlas("pict_explosive"), t=0.002)
    plate(p, 0.32, 0.32, (0.35, -D / 2 - 0.002, zb + 0.4), atlas("pict_explosive"), t=0.002)
    plate(p, 0.3, 0.3, (W / 2 + 0.002, 0, zb + 0.42), atlas("pict_explosive"), t=0.002, facing="+X")
    plate(p, 0.3, 0.3, (-W / 2 - 0.002, 0, zb + 0.42), atlas("pict_explosive"), t=0.002, facing="-X")
    r = p.vrng("box")
    if p.worn and not p.destroyed:
        p.rotate(lid + hasp, rot=(-100, 0, 0), pivot=(0, D / 2 + 0.02, ztop))
        p.tube([(W / 2 - 0.05, -0.2, ztop - 0.15), (W / 2 - 0.05, -0.05, ztop + 0.45)], 0.006, C.STEEL, segs=4)
        cut = p.box((0.05, 0.012, 0.05), (0, 0, 0), C.STEEL, bevel=0.002)
        p.lay_on_floor([cut], at=(0.2, -0.65), yaw=30)
        for i in range(3):
            c = p.box((0.45, 0.3, 0.2), (-0.3 + i * 0.35, 0.1 - (i % 2) * 0.15, zb + 0.05 + 0.1), C.CARDBOARD, bevel=0.004)
            G.xform(c.obj, rot=(0, 0, r.uniform(-10, 10)), pivot=(-0.3 + i * 0.35, 0.1, 0))
    if p.destroyed:
        p.remove(lid)
        nl = [p.box((W + 0.05, D + 0.05, 0.03), (0, 0, 0.015), rd, bevel=0.006),
              p.box((W + 0.05, 0.02, 0.07), (0, -D / 2 - 0.035, -0.005), rd, bevel=0.004)]
        p.lay_on_floor(nl, rot=(172, 4, 0), at=(0.35, -1.0), yaw=21)
        c = p.box((0.45, 0.3, 0.2), (0, 0, 0), C.CARDBOARD, bevel=0.004)
        p.lay_on_floor([c], rot=(0, 0, 0), at=(-0.6, -0.8), yaw=40)
        scatter_papers(p, (-0.3, -0.7), 3, 0.3, "litter")
        p.collider((0, -0.3, 0.5), (1.4, 1.6, 1.0))
    elif p.worn:
        p.collider((0, 0.05, 0.5), (1.32, 1.0, 1.0))
    else:
        p.collider((0, 0, (ztop + 0.03) / 2), (W + 0.12, D + 0.1, ztop + 0.03))


def quarry_core_rack(p: Prop) -> None:
    """Core-tray rack (1.75 x 0.65 x 1.9): slotted-angle uprights and six shelves of shallow wooden core
    trays, each with five channels of grey and dark drill core broken into runs, blank marker blocks
    between runs. Worn: one tray pulled half out and tipped, its core spilled on the floor; a tray gone."""
    W, D = 1.7, 0.6
    st = M.STEEL_GREY
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.box((0.04, 0.04, 1.9), (sx * (W / 2 - 0.02), sy * (D / 2 - 0.02), 0.95), st, bevel=0.002, grain="Z")
    levels = [0.1 + k * 0.32 for k in range(6)]
    r = p.rng("core")
    vr = p.vrng("tray")
    for k, z in enumerate(levels):
        for sy in (-1, 1):
            p.box((W, 0.04, 0.03), (0, sy * (D / 2 - 0.02), z - 0.015), st, bevel=0.002, grain="X")
        if p.worn and k == 3:
            continue
        tray = [p.hollow((1.55, 0.5, 0.045), (0, 0, z + 0.0225), C.WOOD_OLD, wall=0.012, open_face="+Z", bevel=0.0)]
        for j in range(1, 5):
            tray.append(p.box((1.52, 0.008, 0.03), (0, -0.25 + j * 0.1, z + 0.027), C.WOOD_OLD, bevel=0.0, grain="X"))
        for j in range(5):
            y = -0.2 + j * 0.1
            x = -0.74
            while x < 0.72:
                ln = min(0.72 - x, r.uniform(0.18, 0.6))
                if ln > 0.05:
                    mat = C.CORE if r.random() < 0.7 else C.CORE_DARK
                    tray.append(p.cyl(0.028, ln - 0.008, (x + ln / 2, y, z + 0.04), mat, axis="X", segs=5, cap=True))
                x += ln
                if r.random() < 0.25:
                    tray.append(p.box((0.02, 0.06, 0.04), (x + 0.012, y, z + 0.03), M.PL_WHITE, bevel=0.0))
                    x += 0.03
        tray.append(plate(p, 0.12, 0.04, (0, -0.258, z + 0.03), atlas("price_tag", 2), t=0.002))
        if p.worn and k == 1:
            p.move(tray, (0, -0.45, 0))
            p.rotate(tray, rot=(-24, 0, 4), pivot=(0, -0.3, z))
            for i in range(9):
                c = p.cyl(0.024, vr.uniform(0.08, 0.3), (0, 0, 0), C.CORE if i % 3 else C.CORE_DARK, axis="X", segs=6)
                p.lay_on_floor([c], at=(vr.uniform(-0.6, 0.6), -0.75 - vr.uniform(0, 0.4)), yaw=vr.uniform(0, 180))
    p.collider((0, 0, 0.95), (W, D, 1.9))


def quarry_drill_steel_rack(p: Prop) -> None:
    """Drill steel rack (1.6 x 2.1 x 0.6): a welded stand with a base trough and a notched top rail
    holding a row of hex drill steels with their shank collars, a shelf of button bits and spare
    couplings. Worn: half the steels fallen out across the floor in a heap, the others leaning askew."""
    W = 1.5
    st = C.YELLOW
    for sx in (-1, 1):
        p.box((0.06, 0.06, 2.0), (sx * W / 2, 0.15, 1.0), st, bevel=0.004, grain="Z")
        p.box((0.06, 0.55, 0.06), (sx * W / 2, 0.0, 0.03), st, bevel=0.004, grain="Y")
        bar(p, (sx * W / 2, -0.25, 0.06), (sx * W / 2, 0.12, 0.9), 0.05, 0.05, st)
    p.box((W, 0.08, 0.06), (0, 0.15, 1.95), st, bevel=0.004, grain="X")
    p.hollow((W, 0.3, 0.12), (0, 0.05, 0.12), st, wall=0.01, open_face="+Z", bevel=0.0)
    p.box((W, 0.22, 0.02), (0, -0.14, 0.85), C.STEEL, bevel=0.003, grain="X")
    p.box((W, 0.02, 0.06), (0, -0.25, 0.88), C.STEEL, bevel=0.002, grain="X")
    r = p.rng("steel")
    vr = p.vrng("fall")
    n = 11
    for i in range(n):
        x = -W / 2 + 0.1 + i * (W - 0.2) / (n - 1)
        ln = r.uniform(1.75, 1.95)
        fallen = p.worn and i % 2 == 1
        grp = [p.cyl(0.0125, ln, (0, 0, ln / 2), C.GUN_STEEL, segs=6),
               p.cyl(0.02, 0.1, (0, 0, 0.12), C.STEEL, segs=8),
               p.cyl(0.022, 0.04, (0, 0, 0.02), C.STEEL, segs=8)]
        if fallen:
            p.lay_on_floor(grp, rot=(0, 90, 0), at=(vr.uniform(-0.35, 0.35), -0.55 - vr.uniform(0, 0.35)), yaw=vr.uniform(-25, 25),
                           z=0.0 if i < 5 else 0.03)
        else:
            tilt = vr.uniform(-6, 6) if p.worn else r.uniform(-1.5, 1.5)
            p.rotate(grp, rot=(-4 + (vr.uniform(-3, 3) if p.worn else 0), tilt, 0))
            p.move(grp, (x, 0.1, 0.07))
    for i in range(6):
        x = -0.62 + i * 0.17
        p.lathe([(0.0, 0.0), (0.024, 0.0), (0.024, 0.06), (0.04, 0.08), (0.045, 0.11), (0.02, 0.12), (0.0, 0.12)], (x, -0.15, 0.86),
                C.GUN_STEEL, segs=8)
        for k in range(3):
            a = 2 * math.pi * k / 3
            sphere(p, 0.008, (x + math.cos(a) * 0.022, -0.15 + math.sin(a) * 0.022, 0.982), M.CHROME, segs=5, rings=3)
    for i in range(3):
        p.cyl(0.025, 0.14, (0.42 + i * 0.1, -0.15, 0.93), C.STEEL, segs=8)
    p.collider((0, 0.05, 1.0), (W + 0.06, 0.6, 2.0))


def _swivel_chair(p: Prop) -> list:
    """Typist chair at the origin facing -Y: five-star base on casters, gas lift, seat, backrest."""
    out = []
    for k in range(5):
        a = 2 * math.pi * k / 5 + 0.3
        out.append(bar(p, (0, 0, 0.08), (math.cos(a) * 0.3, math.sin(a) * 0.3, 0.06), 0.04, 0.03, M.PL_BLACK))
        out.append(p.cyl(0.025, 0.03, (math.cos(a) * 0.3, math.sin(a) * 0.3, 0.03), M.PL_BLACK, axis="X", segs=8))
    out.append(p.cyl(0.03, 0.3, (0, 0, 0.23), M.CHROME, segs=8))
    out.append(p.rbox((0.46, 0.44, 0.08), (0, 0, 0.44), M.VINYL_BLACK, radius=0.03, inner=(2, 2, 1)))
    out.append(bar(p, (0, 0.18, 0.4), (0, 0.24, 0.62), 0.06, 0.02, M.PL_BLACK))
    out.append(p.rbox((0.42, 0.07, 0.36), (0, 0.25, 0.8), M.VINYL_BLACK, radius=0.03, inner=(2, 1, 2)))
    return out


def quarry_scale_terminal(p: Prop) -> None:
    """Weighbridge operator's desk (1.3 x 1.4 x 1.2 with its chair): a steel desk under the window, the scale
    indicator (LCD of dashes, membrane keypad), the ticket printer with a curl of ticket, the remote
    readout on a post, a beige phone, the blast plan pinned under a clip, a clipboard log, a hard hat; the
    operator's swivel chair in front. Worn: the chair rolled back and turned, tickets on the floor, the
    hard hat on the floor."""
    W, D, H = 1.3, 0.7, 0.75
    st = C.PANEL
    p.box((W, D, 0.03), (0, 0, H - 0.015), M.LAMINATE, bevel=0.004, grain="X")
    p.box((0.42, D - 0.04, H - 0.03), (W / 2 - 0.23, 0, (H - 0.03) / 2), st, bevel=0.004)
    for k in range(3):
        F.drawer(p, W / 2 - 0.42, 0.05 + k * 0.22, W / 2 - 0.04, 0.25 + k * 0.22, -D / 2 - 0.02, 0.5, st, t=0.02, style="slab",
                 handle="bar", handle_mat=M.CHROME, key=f"dr{k}")
    p.box((0.03, D - 0.04, H - 0.03), (-W / 2 + 0.02, 0, (H - 0.03) / 2), st, bevel=0.003)
    p.box((W - 0.45, 0.02, 0.45), (-0.2, D / 2 - 0.03, H - 0.27), st, bevel=0.003)
    # indicator
    ix, iy = -0.15, 0.1
    p.box((0.38, 0.22, 0.24), (ix, iy, H + 0.12), C.PANEL, bevel=0.015)
    ind = p.box((0.38, 0.03, 0.14), (0, 0, 0), C.PANEL, bevel=0.006)
    G.xform(ind.obj, loc=(ix, iy - 0.11, H + 0.17))
    plate(p, 0.3, 0.075, (ix, iy - 0.127, H + 0.2), atlas("lcd"), t=0.003)
    for row in range(3):
        for col in range(5):
            p.box((0.03, 0.01, 0.018), (ix - 0.1 + col * 0.05, iy - 0.115, H + 0.09 - row * 0.0 - 0.0) if False else
                  (ix - 0.1 + col * 0.05, iy - 0.18 + row * 0.03, H + 0.012 + row * 0.006), C.PL_BLACK if col < 4 else C.PAINT_RED,
                  bevel=0.002)
    p.box((0.3, 0.11, 0.02), (ix, iy - 0.15, H + 0.005), C.PANEL, bevel=0.004)
    # ticket printer
    p.box((0.25, 0.3, 0.14), (0.25, 0.1, H + 0.07), M.PL_BEIGE, bevel=0.015)
    p.box((0.16, 0.01, 0.01), (0.25, -0.052, H + 0.11), M.PL_BLACK, bevel=0.0)
    curl = [(0.25, -0.05, H + 0.11), (0.25, -0.1, H + 0.1), (0.25, -0.13, H + 0.06), (0.25, -0.12, H + 0.02)]
    p.add(G.tube(p._name("curl"), curl, 0.004, 4, False), M.PAPER, wear=0.1)
    p.box((0.075, 0.003, 0.1), (0.25, -0.12, H + 0.06), M.PAPER, bevel=0.0)
    # phone
    p.box((0.2, 0.22, 0.07), (-0.48, 0.12, H + 0.035), M.PL_BEIGE, bevel=0.015)
    p.rbox((0.06, 0.22, 0.05), (-0.52, 0.12, H + 0.09), M.PL_BEIGE, radius=0.02, inner=(1, 2, 1))
    # papers
    plate(p, 0.42, 0.42, (-0.1, -0.15, H + 0.0015), atlas("site_plan", 2), t=0.001, facing="+Z")
    p.box((0.24, 0.32, 0.006), (0.45, -0.12, H + 0.003), M.PARTICLE, bevel=0.002)
    plate(p, 0.22, 0.28, (0.45, -0.13, H + 0.007), atlas("clip_sheet", 2), t=0.001, facing="+Z")
    p.box((0.1, 0.03, 0.02), (0.45, 0.02, H + 0.015), M.CHROME, bevel=0.004)
    # remote readout on a post at the back corner
    p.cyl(0.02, 0.5, (-0.55, D / 2 - 0.05, H + 0.25), M.CHROME, segs=6)
    p.box((0.3, 0.1, 0.12), (-0.55, D / 2 - 0.05, H + 0.55), C.PANEL, bevel=0.01)
    plate(p, 0.26, 0.06, (-0.55, D / 2 - 0.101, H + 0.55), atlas("lcd"), t=0.002)
    hat = [p.lathe([(0.0, 0.0), (0.16, 0.0), (0.16, 0.012), (0.12, 0.02), (0.12, 0.08), (0.09, 0.13), (0.0, 0.15)], (0, 0, 0),
                   C.PL_ORANGE, segs=12)]
    chair = _swivel_chair(p)
    if p.worn:
        p.lay_on_floor(hat, rot=(0, 160, 0), at=(-0.5, -0.9), yaw=20)
        p.rotate(chair, rot=(0, 0, 145))
        p.move(chair, (0.55, -1.0, 0))
        scatter_papers(p, (0.1, -0.6), 4, 0.3, "tickets")
    else:
        p.move(hat, (0.5, 0.18, H + 0.003))
        p.rotate(chair, rot=(0, 0, 180 + 8))
        p.move(chair, (-0.15, -0.68, 0))
    p.collider((0, 0, (H + 0.3) / 2), (W, D, H + 0.3))
    p.collider((-0.15 if not p.worn else 0.55, -0.68 if not p.worn else -1.0, 0.5), (0.6, 0.6, 1.0))


# ================================================================================================
# Pawn & Gun
# ================================================================================================


def _flat(p: Prop, parts, at, yaw: float, z: float) -> None:
    """Lays a group built in the XZ plane (side profile, thickness along Y) flat on a surface at height z."""
    p.lay_on_floor(parts, rot=(-90, 0, 0), at=at, yaw=yaw, z=z)


def _pistol(p: Prop, two_tone: bool = False) -> list:
    """Semi-automatic pistol, side profile in XZ (muzzle +X), at the origin."""
    out = [p.box((0.19, 0.028, 0.034), (0.02, 0, 0.1), C.GUN_STEEL if not two_tone else M.STAINLESS, bevel=0.003),
           p.box((0.13, 0.026, 0.022), (0.0, 0, 0.073), C.GUN_STEEL, bevel=0.003)]
    g = p.box((0.034, 0.026, 0.11), (-0.055, 0, 0.03), C.PL_BLACK, bevel=0.004)
    G.xform(g.obj, rot=(0, -16, 0), pivot=(-0.055, 0, 0.07))
    out.append(g)
    out.append(torus(p, 0.02, 0.003, (0.0, 0, 0.062), C.GUN_STEEL, axis="Y", segs=8, rsegs=3, arc=180, a0=180))
    out.append(p.box((0.008, 0.006, 0.018), (-0.005, 0, 0.055), C.GUN_STEEL, bevel=0.0))
    return out


def _revolver(p: Prop, long: bool = False) -> list:
    """Revolver, side profile in XZ (muzzle +X), at the origin."""
    bl = 0.15 if long else 0.09
    out = [p.cyl(0.008, bl, (0.035 + bl / 2, 0, 0.095), C.GUN_STEEL, axis="X", segs=6),
           p.box(((bl * 0.9), 0.012, 0.01), (0.035 + bl * 0.45, 0, 0.108), C.GUN_STEEL, bevel=0.0),
           p.cyl(0.019, 0.042, (0.005, 0, 0.088), C.GUN_STEEL, axis="X", segs=8),
           p.box((0.08, 0.022, 0.045), (-0.005, 0, 0.083), C.GUN_STEEL, bevel=0.004)]
    g = p.box((0.032, 0.026, 0.095), (-0.06, 0, 0.035), C.GUN_STOCK, bevel=0.006)
    G.xform(g.obj, rot=(0, -28, 0), pivot=(-0.05, 0, 0.07))
    out.append(g)
    out.append(torus(p, 0.017, 0.003, (-0.012, 0, 0.058), C.GUN_STEEL, axis="Y", segs=8, rsegs=3, arc=180, a0=180))
    out.append(p.box((0.012, 0.008, 0.02), (-0.045, 0, 0.11), C.GUN_STEEL, bevel=0.0))
    return out


def _long_gun(p: Prop, kind: str) -> list:
    """Long gun standing butt-down, side profile in the XZ plane (top of the gun toward +X), thickness Y.
    kind: rifle (scoped bolt gun), carbine (box magazine), pump (pump shotgun), double (side-by-side)."""
    out = []
    wood = C.GUN_STOCK
    stock = [(-0.055, 0.0), (0.045, 0.0), (0.04, 0.1), (0.02, 0.33), (0.015, 0.4), (-0.012, 0.4), (-0.03, 0.34), (-0.055, 0.14)]
    out.append(p.prism(stock, 0.036, wood if kind != "carbine" else C.PL_BLACK, plane="XZ", offset=-0.018))
    out.append(p.box((0.1, 0.04, 0.012), (-0.005, 0, 0.006), C.RUBBER, bevel=0.002))
    out.append(p.box((0.034, 0.03, 0.22), (0.005, 0, 0.5), C.GUN_STEEL, bevel=0.004, grain="Z"))
    out.append(torus(p, 0.022, 0.003, (-0.02, 0, 0.44), C.GUN_STEEL, axis="Y", segs=8, rsegs=3, arc=180, a0=90))
    blen = {"rifle": 0.62, "carbine": 0.45, "pump": 0.58, "double": 0.6}[kind]
    out.append(p.cyl(0.009 if kind in ("rifle", "carbine") else 0.012, blen, (0.008, 0, 0.6 + blen / 2), C.GUN_STEEL, segs=6))
    if kind in ("rifle", "carbine"):
        out.append(p.box((0.03, 0.032, 0.26), (-0.005, 0, 0.72), wood if kind == "rifle" else C.PL_BLACK, bevel=0.006, grain="Z"))
    if kind == "rifle":
        out.append(p.cyl(0.015, 0.3, (0.05, 0, 0.55), C.GUN_STEEL, segs=8))
        for z in (0.4, 0.7):
            out.append(p.cyl(0.02, 0.05, (0.05, 0, z), C.GUN_STEEL, segs=8))
        out.append(p.cyl(0.006, 0.05, (-0.03, 0.02, 0.56), C.GUN_STEEL, axis="Y", segs=5))
    elif kind == "carbine":
        out.append(p.box((0.07, 0.022, 0.035), (-0.045, 0, 0.53), C.GUN_STEEL, bevel=0.003))
        out.append(p.box((0.025, 0.006, 0.03), (0.035, 0, 0.62), C.GUN_STEEL, bevel=0.0))
    elif kind == "pump":
        out.append(p.cyl(0.01, blen - 0.08, (-0.016, 0, 0.6 + (blen - 0.08) / 2), C.GUN_STEEL, segs=6))
        out.append(p.cyl(0.02, 0.16, (-0.012, 0, 0.75), wood, segs=8))
    else:
        out.append(p.box((0.03, 0.034, 0.24), (-0.004, 0, 0.7), wood, bevel=0.006, grain="Z"))
        out.append(p.cyl(0.012, blen, (0.008, 0.012, 0.6 + blen / 2), C.GUN_STEEL, segs=6))
    return out


def _price_tag(p: Prop, c, rot=(0, 0, 0)) -> core.Part:
    return plate(p, 0.05, 0.025, c, atlas("price_tag", 2), t=0.0008, facing="+Z", rot=(-90, 0, rot[2]), wear=0.1)


def pawn_gun_case(p: Prop) -> None:
    """Handgun showcase counter (1.5 x 1.0 x 0.6): a black-laminate cabinet with an aluminium-framed glass top
    and front, a red felt deck of pistols and revolvers with string tags, glass sliding doors and a lock on
    the staff side (+Y). Worn: the front pane cracked, three guns left. Destroyed: the top and front smashed
    out, glass on the deck and the floor, one revolver left."""
    W, D, zb, zt = 1.5, 0.6, 0.72, 0.99
    body = M.LAM_WOOD
    p.box((W, D, zb - 0.08), (0, 0, (zb - 0.08) / 2 + 0.08), M.PL_BLACK, bevel=0.004)
    p.box((W - 0.04, D - 0.06, 0.08), (0, 0.01, 0.04), M.PL_BLACK, bevel=0.002, wear=0.4)
    p.box((W + 0.01, D + 0.01, 0.04), (0, 0, zb - 0.02), body, bevel=0.004, grain="X")
    for x in (-0.37, 0.37):
        p.box((0.7, 0.012, zb - 0.2), (x, D / 2 + 0.006, zb / 2 + 0.02), M.PL_BLACK, bevel=0.003)
        p.box((0.025, 0.02, 0.025), (x - 0.3, D / 2 + 0.02, zb / 2 + 0.05), M.CHROME, bevel=0.003)
    p.box((W - 0.03, D - 0.03, 0.01), (0, 0, zb + 0.005), C.FELT_RED, bevel=0.002, wear=0.2)
    # aluminium frame
    al = "road_alu"
    for sy in (-1, 1):
        for z in (zb + 0.01, zt):
            p.box((W, 0.02, 0.02), (0, sy * (D / 2 - 0.01), z), al, bevel=0.002, grain="X")
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.box((0.02, 0.02, zt - zb), (sx * (W / 2 - 0.01), sy * (D / 2 - 0.01), (zt + zb) / 2 + 0.005), al, bevel=0.002, grain="Z")
        p.box((0.02, D, 0.02), (sx * (W / 2 - 0.01), 0, zt), al, bevel=0.002, grain="Y")
        p.box((0.004, D - 0.04, zt - zb - 0.02), (sx * (W / 2 - 0.01), 0, (zt + zb) / 2 + 0.005), M.GLASS, bevel=0.0, wear=0.0)
    # staff-side sliding glass doors + lock
    for k, x in enumerate((-0.37, 0.37)):
        p.box((0.75, 0.004, zt - zb - 0.03), (x, D / 2 - 0.015 - k * 0.008, (zt + zb) / 2 + 0.005), M.GLASS, bevel=0.0, wear=0.0)
    p.box((0.04, 0.012, 0.05), (0.0, D / 2 - 0.004, (zt + zb) / 2), M.CHROME, bevel=0.004)
    gw, gh = W - 0.04, zt - zb - 0.02
    front_c = (0, -D / 2 + 0.01, (zt + zb) / 2 + 0.005)
    top_c = (0, 0, zt + 0.003)
    if p.destroyed:
        F.shatter_pane(p, gw, gh, front_c, M.GLASS, t=0.005, impact=(0.15, 0.02), key="front", missing_inner=1.0, missing_outer=0.55,
                       floor_shards=6, floor_at=(0.1, -0.65))
        top = F.shatter_pane(p, gw, D - 0.04, (0, 0, 0), M.GLASS, t=0.005, impact=(-0.2, 0.0), key="top", missing_inner=1.0,
                             missing_outer=0.6, floor_shards=0)
        p.rotate(top, rot=(90, 0, 0))
        p.move(top, top_c)
        r = p.vrng("shards")
        for i in range(6):
            sh = p.prism([(0, 0), (r.uniform(0.04, 0.09), 0.0), (r.uniform(0.0, 0.05), r.uniform(0.04, 0.08))], 0.005, M.GLASS,
                         plane="XY", offset=0.0, uv="planar", uv_axis="Z")
            G.xform(sh.obj, rot=(0, 0, r.uniform(0, 360)), loc=(r.uniform(-0.6, 0.6), r.uniform(-0.22, 0.22), zb + 0.011))
    elif p.worn:
        F.shatter_pane(p, gw, gh, front_c, M.GLASS, t=0.005, impact=(0.3, -0.03), spokes=8, rings=3, key="front", missing_inner=0.6,
                       missing_outer=0.0)
        p.box((gw, D - 0.04, 0.005), top_c, M.GLASS, bevel=0.0, wear=0.0)
    else:
        p.box((gw, 0.005, gh), front_c, M.GLASS, bevel=0.0, wear=0.0)
        p.box((gw, D - 0.04, 0.005), top_c, M.GLASS, bevel=0.0, wear=0.0)
    za = zb + 0.01
    guns = [("p", -0.55, -0.05, 20), ("r", -0.25, 0.05, -10), ("p2", 0.05, -0.04, 15), ("rl", 0.35, 0.06, -5), ("p", 0.6, -0.02, 25)]
    keep = range(5) if not p.worn else ((0, 3, 4) if not p.destroyed else (3,))
    for i, (kind, x, y, yaw) in enumerate(guns):
        if i not in keep:
            if p.worn:
                _price_tag(p, (x + 0.02, y - 0.12, za + 0.001), (0, 0, yaw + 40))
            continue
        g = _pistol(p, kind == "p2") if kind.startswith("p") else _revolver(p, kind == "rl")
        _flat(p, g, (x, y), yaw, za)
        _price_tag(p, (x + 0.04, y - 0.13, za + 0.001), (0, 0, yaw))
    if p.destroyed:
        g = _pistol(p)
        _flat(p, g, (-0.4, -0.75), 70, 0.0)
        p.collider((0, -0.1, 0.5), (W, D + 0.3, 1.0))
    else:
        p.collider((0, 0, zt / 2), (W, D, zt))


def pawn_long_gun_rack(p: Prop) -> None:
    """Wall long-gun rack (1.6 x 1.35 x 0.2, origin on the wall plane): a green-carpeted backboard, a felt
    butt shelf with a lip, a notched upper rail, six long guns (scoped bolt rifles, a carbine, pump and
    side-by-side shotguns) with a plastic-sheathed steel cable run through every trigger guard between eye
    bolts and padlocked. Hang at ~0.5 m. Worn: three guns gone, the cable cut and hanging slack, one gun
    leaning askew in its slot."""
    W, H = 1.6, 1.35
    p.box((W, 0.018, H), (0, -0.009, H / 2), C.FELT_GREEN, bevel=0.003, wear=0.3)
    for z in (0.0, H):
        p.box((W + 0.02, 0.04, 0.04), (0, -0.02, z + (0.02 if z == 0 else -0.02)), C.OAK_DARK, bevel=0.004, grain="X")
    for sx in (-1, 1):
        p.box((0.04, 0.04, H), (sx * (W / 2 - 0.0), -0.02, H / 2), C.OAK_DARK, bevel=0.004, grain="Z")
    p.box((W - 0.06, 0.13, 0.03), (0, -0.083, 0.06), C.OAK_DARK, bevel=0.004, grain="X")
    p.box((W - 0.06, 0.12, 0.004), (0, -0.083, 0.077), C.FELT_GREEN, bevel=0.0)
    p.box((W - 0.06, 0.012, 0.05), (0, -0.142, 0.095), C.OAK_DARK, bevel=0.003, grain="X")
    rail_z = 0.98
    p.box((W - 0.06, 0.09, 0.04), (0, -0.063, rail_z), C.OAK_DARK, bevel=0.004, grain="X")
    kinds = ["rifle", "pump", "carbine", "rifle", "double", "pump"]
    xs = [-0.6 + i * 0.24 for i in range(6)]
    gone = (1, 3, 4) if p.worn else ()
    for i, (x, kind) in enumerate(zip(xs, kinds)):
        p.box((0.05, 0.01, 0.04), (x, -0.112, rail_z), C.FELT_GREEN, bevel=0.0)
        if i in gone:
            continue
        g = _long_gun(p, kind)
        p.rotate(g, rot=(0, 0, 90))
        lean = 4.0 if not (p.worn and i == 2) else 11.0
        p.rotate(g, rot=(lean, 0, 0))
        side = 0.0 if not (p.worn and i == 2) else 8.0
        p.rotate(g, rot=(0, side, 0))
        p.move(g, (x, -0.075, 0.08))
    zc = 0.5
    for sx in (-1, 1):
        torus(p, 0.018, 0.005, (sx * (W / 2 - 0.07), -0.03, zc), M.CHROME, axis="Z", segs=8, rsegs=3)
        p.cyl(0.006, 0.03, (sx * (W / 2 - 0.07), -0.015, zc), M.CHROME, axis="Y", segs=5)
    if not p.worn:
        p.tube([(-W / 2 + 0.07, -0.05, zc), (-0.6, -0.12, zc - 0.05), (0.6, -0.12, zc - 0.05), (W / 2 - 0.07, -0.05, zc)], 0.005,
               M.PL_BLACK, segs=4, fillet_r=0.05)
        p.box((0.045, 0.02, 0.055), (W / 2 - 0.07, -0.06, zc - 0.05), C.BRASS, bevel=0.006)
        torus(p, 0.015, 0.004, (W / 2 - 0.07, -0.06, zc - 0.012), M.CHROME, axis="Y", segs=8, rsegs=3, arc=180)
    else:
        p.tube([(-W / 2 + 0.07, -0.05, zc), (-0.62, -0.1, zc - 0.25), (-0.4, -0.12, zc - 0.33), (-0.15, -0.13, zc - 0.36)], 0.005,
               M.PL_BLACK, segs=4, fillet_r=0.08)
        p.tube([(W / 2 - 0.07, -0.05, zc), (0.68, -0.1, zc - 0.2), (0.55, -0.12, zc - 0.3)], 0.005, M.PL_BLACK, segs=4, fillet_r=0.08)
    p.collider((0, -0.1, H / 2), (W, 0.2, H))


def _guitar(p: Prop, electric: bool) -> list:
    """Guitar standing at the origin (bottom of the body on the floor), face toward -Y."""
    out = []
    if electric:
        prof = [(0.0, 0.0), (0.13, 0.02), (0.16, 0.12), (0.12, 0.22), (0.15, 0.33), (0.1, 0.4), (0.06, 0.34), (0.03, 0.38),
                (-0.04, 0.36), (-0.1, 0.42), (-0.14, 0.32), (-0.11, 0.22), (-0.16, 0.12), (-0.12, 0.02)]
        t = 0.042
        out.append(p.prism(prof, t, C.GUITAR_RED, plane="XZ", offset=-t / 2))
        for z in (0.16, 0.24):
            out.append(p.box((0.08, 0.01, 0.02), (0, -t / 2 - 0.004, z), M.PL_BLACK, bevel=0.002))
        out.append(p.box((0.06, 0.008, 0.02), (0, -t / 2 - 0.004, 0.09), M.CHROME, bevel=0.002))
        top = 0.38
    else:
        def hw(z):
            return 0.19 * math.exp(-((z - 0.14) / 0.11) ** 2) + 0.145 * math.exp(-((z - 0.4) / 0.08) ** 2) + 0.06
        zs = [0.0, 0.03, 0.07, 0.12, 0.17, 0.22, 0.27, 0.31, 0.35, 0.4, 0.44, 0.47, 0.49]
        prof = [(min(0.2, hw(z)) * (0.5 if z in (0.0, 0.49) else 1.0), z) for z in zs]
        prof = prof + [(-x, z) for x, z in reversed(prof)]
        t = 0.1
        body = p.prism(prof, t, C.OAK, plane="XZ", offset=-t / 2)
        rect = atlas("sunburst", 4)
        me = body.obj.data
        uvl = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
        for poly in me.polygons:
            for li in poly.loop_indices:
                co = me.vertices[me.loops[li].vertex_index].co
                uvl.data[li].uv = (rect[0] + (co.x / 0.42 + 0.5) * (rect[2] - rect[0]), rect[1] + (co.z / 0.5) * (rect[3] - rect[1]))
        body.uv = "keep"
        body.mat = C.PRINT
        p.set_mat(body, C.PRINT)
        p.set_mat(body, C.MAHOGANY, lambda poly: abs(poly.normal.y) < 0.9)
        out.append(body)
        out.append(p.cyl(0.045, 0.004, (0, -t / 2 - 0.001, 0.33), M.PL_BLACK, axis="Y", segs=12))
        out.append(p.box((0.1, 0.012, 0.02), (0, -t / 2 - 0.006, 0.13), C.MAHOGANY, bevel=0.003))
        top = 0.47
    out.append(p.box((0.05, 0.022, 0.48), (0, -0.005, top + 0.22), C.MAHOGANY, bevel=0.004, grain="Z"))
    out.append(p.box((0.045, 0.004, 0.46), (0, -0.018, top + 0.22), C.OAK_DARK, bevel=0.0, grain="Z"))
    out.append(p.box((0.08, 0.018, 0.16), (0, 0.0, top + 0.53), C.OAK_DARK if not electric else C.GUITAR_RED, bevel=0.006))
    for k in range(3):
        for sx in (-1, 1):
            out.append(p.box((0.02, 0.01, 0.01), (sx * 0.05, 0.0, top + 0.48 + k * 0.045), M.CHROME, bevel=0.0))
    return out


def _crt_tv(p: Prop) -> list:
    out = [p.box((0.42, 0.36, 0.34), (0, 0, 0.17), M.PL_BLACK, bevel=0.02)]
    out.append(p.box((0.3, 0.2, 0.24), (0, 0.24, 0.15), M.PL_BLACK, bevel=0.03))
    out.append(p.box((0.31, 0.005, 0.24), (-0.035, -0.181, 0.185), M.CRT, bevel=0.0, uv="planar", uv_axis="Y"))
    for k in range(3):
        out.append(p.cyl(0.008, 0.01, (0.17, -0.18, 0.25 - k * 0.04), M.PL_GREY, axis="Y", segs=6))
    out.append(p.tube([(0.1, 0.05, 0.34), (0.16, 0.05, 0.6)], 0.003, M.CHROME, segs=4))
    return out


def _drill(p: Prop, mat: str) -> list:
    out = [p.rbox((0.2, 0.06, 0.07), (0.0, 0, 0.21), mat, radius=0.025, inner=(1, 1, 1))]
    g = p.rbox((0.045, 0.05, 0.14), (0.04, 0, 0.11), M.PL_BLACK, radius=0.018, inner=(1, 1, 1))
    G.xform(g.obj, rot=(0, 12, 0), pivot=(0.04, 0, 0.17))
    out.append(g)
    out.append(p.box((0.1, 0.075, 0.06), (0.06, 0, 0.03), M.PL_BLACK, bevel=0.01))
    out.append(p.cyl(0.018, 0.05, (-0.12, 0, 0.215), M.PL_BLACK, axis="X", segs=8))
    out.append(p.cyl(0.004, 0.06, (-0.17, 0, 0.215), M.CHROME, axis="X", segs=5))
    return out


def _tool_case(p: Prop, w: float, mat: str) -> list:
    out = [p.rbox((w, 0.12, 0.3), (0, 0, 0.15), mat, radius=0.03, inner=(1, 1, 1))]
    out.append(p.box((0.12, 0.03, 0.03), (0, 0, 0.32), M.PL_BLACK, bevel=0.008))
    for sx in (-1, 1):
        out.append(p.box((0.03, 0.02, 0.04), (sx * w * 0.3, -0.065, 0.26), M.PL_BLACK, bevel=0.004))
    return out


def _jewel_box(p: Prop, c, w: float, d: float, h: float, open_lid: bool, cell: str = "velvet") -> list:
    x, y, z = c
    out = [p.box((w, d, h), (x, y, z + h / 2), M.PL_BLACK, bevel=0.003)]
    if open_lid:
        out.append(plate(p, w - 0.008, d - 0.008, (x, y, z + h + 0.0005), atlas(cell, 3), t=0.001, facing="+Z", wear=0.0))
        lid = p.box((w, 0.012, d), (x, y + d / 2, z + h + d / 2), M.PL_BLACK, bevel=0.003)
        G.xform(lid.obj, rot=(-12, 0, 0), pivot=(x, y + d / 2, z + h))
        out.append(lid)
        out.append(torus(p, 0.012, 0.003, (x, y, z + h + 0.012), C.BRASS, axis="Y", segs=8, rsegs=3))
    else:
        out.append(p.box((w + 0.004, d + 0.004, 0.015), (x, y, z + h + 0.0075), M.PL_BLACK, bevel=0.003))
    return out


def pawn_shelf_mixed(p: Prop) -> None:
    """Pawn shop shelving (1.9 x 1.9 x 0.5): a grey steel shelving unit of four shelves, an acoustic guitar
    (sunburst top) on a floor stand at one end and an electric leaning on the other, blow-moulded power tool
    cases, cordless drills, a portable CRT television, ring and watch boxes, every item with a string tag.
    Worn: picked over, a drill and the TV gone, a case fallen. Destroyed: a shelf collapsed at one end, the
    goods slid onto the floor, the electric guitar face down."""
    W, D = 1.2, 0.45
    st = M.STEEL_GREY
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.box((0.035, 0.035, 1.85), (sx * (W / 2 - 0.0175), sy * (D / 2 - 0.0175), 0.925), st, bevel=0.002, grain="Z")
    shelves = {}
    for k, z in enumerate((0.1, 0.55, 1.0, 1.45, 1.84)):
        shelves[k] = p.box((W - 0.01, D - 0.01, 0.02), (0, 0, z), st, bevel=0.002)
    r = p.vrng("goods")
    goods: dict = {0: [], 1: [], 2: [], 3: []}
    goods[0] += [*_tool_case(p, 0.42, C.TOOL_TEAL)]
    p.move(goods[0][-4:], (-0.3, 0.02, 0.11))
    tc = _tool_case(p, 0.36, C.TOOL_YELLOW)
    p.move(tc, (0.22, 0.04, 0.11))
    goods[0] += tc
    if not p.worn:
        tv = _crt_tv(p)
        p.move(tv, (-0.2, 0.0, 0.56))
        goods[1] += tv
    goods[1].append(_price_tag(p, (0.15, -0.15, 0.562)))
    for i, (mat, x) in enumerate(((C.TOOL_TEAL, -0.35), (C.TOOL_YELLOW, -0.05), (C.TOOL_TEAL, 0.3))):
        if p.worn and i == 1:
            continue
        d = _drill(p, mat)
        p.rotate(d, rot=(0, 0, 90 + r.uniform(-10, 10)))
        p.move(d, (x, 0.0, 1.01))
        goods[2] += d
        goods[2].append(_price_tag(p, (x + 0.06, -0.17, 1.012), (0, 0, 10)))
    for i in range(5):
        x = -0.42 + i * 0.2
        goods[3] += _jewel_box(p, (x, -0.08 + (i % 2) * 0.12, 1.46), 0.1 if i % 3 else 0.14, 0.09, 0.05, i % 2 == 0,
                               "velvet" if i % 3 else "velvet_red")
    goods[3].append(_price_tag(p, (0.1, -0.18, 1.462)))
    # acoustic guitar on a floor stand at the right end
    gx = W / 2 + 0.3
    stand = [p.tube([(gx - 0.15, -0.12, 0.02), (gx, 0.05, 0.02), (gx + 0.15, -0.12, 0.02)], 0.008, M.PL_BLACK, segs=5),
             p.tube([(gx, 0.05, 0.02), (gx, 0.12, 0.6)], 0.009, M.PL_BLACK, segs=5),
             torus(p, 0.035, 0.006, (gx, 0.1, 0.62), M.PL_BLACK, axis="Y", segs=8, rsegs=3, arc=180, a0=180)]
    for sx in (-1, 1):
        stand.append(p.tube([(gx + sx * 0.1, -0.12, 0.02), (gx + sx * 0.1, -0.1, 0.12)], 0.009, M.RUBBER, segs=5))
    ac = _guitar(p, False)
    p.rotate(ac, rot=(-14, 0, 0))
    p.move(ac, (gx, -0.07, 0.1))
    el = _guitar(p, True)
    if p.destroyed:
        p.lay_on_floor(el, rot=(90, 0, 0), at=(-0.4, -0.85), yaw=70)
    else:
        p.rotate(el, rot=(0, 13, 0))
        p.move(el, (-W / 2 - 0.2, -0.05, 0.0))
    if p.worn and not p.destroyed:
        c = _tool_case(p, 0.36, C.TOOL_YELLOW)
        p.lay_on_floor(c, rot=(90, 0, 0), at=(0.1, -0.55), yaw=12)
    if p.destroyed:
        # shelf 2 dropped at its left end: its goods slide off onto the floor
        p.rotate([shelves[2]] + goods[2], rot=(0, -24, 0), pivot=(W / 2, 0, 1.0))
        p.remove(goods[3][:8])
        for i in range(3):
            jb = _jewel_box(p, (0, 0, 0), 0.1, 0.09, 0.05, i == 0)
            p.lay_on_floor(jb, rot=(r.uniform(0, 90), 0, 0), at=(r.uniform(-0.6, 0.4), r.uniform(-0.75, -0.4)), yaw=r.uniform(0, 180))
        scatter_papers(p, (0.0, -0.6), 2, 0.3, "manuals")
        p.collider((0, -0.2, 0.93), (1.9, 0.9, 1.86))
    else:
        p.collider((0, 0, 0.93), (W, D, 1.86))
        p.collider((gx, -0.05, 0.6), (0.4, 0.3, 1.2))


def pawn_security_grille(p: Prop) -> None:
    """Folding scissor security gate (1.2 x 2.1, origin on the wall plane): black-painted channel pickets
    joined by riveted scissor lattice bars at four heights, top and bottom track, a latch post with a
    padlocked hasp. No collision (it dresses a doorway or window). Worn: concertinaed half open toward the
    left, a picket bent out where it was pried, the padlock cut and hanging."""
    W, H = 1.2, 2.1
    bk = M.STEEL_BLACK
    y = -0.06
    p.box((W + 0.06, 0.06, 0.05), (0, y, H - 0.025), bk, bevel=0.003, grain="X")
    p.box((W + 0.06, 0.06, 0.02), (0, y, 0.01), bk, bevel=0.002, grain="X")
    n = 9
    span = W if not p.worn else W * 0.55
    x0 = -W / 2
    xs = [x0 + span * i / (n - 1) for i in range(n)]
    for i, x in enumerate(xs):
        pk = p.box((0.025, 0.02, H - 0.08), (x, y, H / 2), bk, bevel=0.002, grain="Z")
        if p.worn and i == 5:
            pk.obj.data.transform(Matrix.Identity(4))
            for v in pk.obj.data.vertices:
                t = math.sin(max(0.0, min(1.0, (v.co.z - 0.4) / 1.2)) * math.pi)
                v.co.y -= 0.12 * t
    rise = 0.22
    for z in (0.3, 0.75, 1.25, 1.75):
        for i in range(n - 1):
            a, b = xs[i], xs[i + 1]
            for sgn in (-1, 1):
                bar(p, (a, y - 0.016, z - sgn * rise / 2), (b, y - 0.016, z + sgn * rise / 2), 0.02, 0.006, bk, bevel=0.0)
            rivet(p, ((a + b) / 2, y - 0.02, z), (0, -1, 0), 0.007, M.CHROME)
    lx = xs[-1] + 0.03
    p.box((0.05, 0.04, H - 0.08), (lx, y, H / 2), bk, bevel=0.003, grain="Z")
    p.box((0.05, 0.04, H - 0.08), (W / 2 + 0.01, y, H / 2), bk, bevel=0.003, grain="Z")
    if not p.worn:
        p.box((0.045, 0.02, 0.055), (W / 2 - 0.02, y - 0.04, 1.0), C.BRASS, bevel=0.006)
        torus(p, 0.016, 0.004, (W / 2 - 0.02, y - 0.04, 1.035), M.CHROME, axis="Y", segs=8, rsegs=3, arc=180)
    else:
        lk = [p.box((0.045, 0.02, 0.055), (W / 2 + 0.01, y - 0.05, 0.94), C.BRASS, bevel=0.006),
              torus(p, 0.016, 0.004, (W / 2 + 0.01, y - 0.05, 0.975), M.CHROME, axis="Y", segs=8, rsegs=3, arc=150)]
        p.rotate(lk, rot=(0, 25, 0), pivot=(W / 2 + 0.01, y - 0.05, 1.0))


def _carton(p: Prop, size, center, front: str, *, rot=(0, 0, 0)) -> core.Part:
    """Ammunition carton: the front / back faces show an ammo atlas cell, the rest the plain end card."""
    obj = G.box(p._name("ammo"), size, (0, 0, 0), 0.0)
    fr, en = atlas(front, 2), atlas("ammo_end", 2)

    def face_rect(poly):
        n = poly.normal
        if abs(n.y) > 0.9:
            return (*fr, 0, 2, n.y > 0)
        if abs(n.x) > 0.9:
            return (*en, 1, 2, False)
        return (*en, 0, 1, False)

    core.set_face_uvs(obj, face_rect)
    G.xform(obj, rot=rot, loc=center)
    return p.add(obj, C.PRINT, uv="keep", tags=("goods",), wear=0.6)


def _ammo_can(p: Prop, c, yaw: float = 0.0) -> list:
    x, y, z = c
    out = [p.box((0.28, 0.14, 0.17), (0, 0, 0.085), C.AMMO_CAN, bevel=0.006),
           p.box((0.29, 0.15, 0.03), (0, 0, 0.175), C.AMMO_CAN, bevel=0.006),
           p.tube([(-0.05, 0, 0.19), (-0.05, 0, 0.2), (0.05, 0, 0.2), (0.05, 0, 0.19)], 0.006, C.AMMO_CAN, segs=4),
           p.box((0.04, 0.03, 0.06), (0.13, -0.08, 0.16), C.AMMO_CAN, bevel=0.004)]
    place(out, Matrix.Translation((x, y, z)) @ Matrix.Rotation(math.radians(yaw), 4, "Z"))
    return out


def pawn_ammo_shelf(p: Prop) -> None:
    """Ammunition shelf (1.0 x 1.8 x 0.4): a heavy grey steel shelf of five levels stocked with cartons of
    handgun, rifle and shotgun ammunition (coloured boxes, cartridge pictograms, no words) and three surplus
    ammo cans on the bottom. Worn: picked over, cartons knocked flat, a few on the floor. Destroyed: the
    third shelf dropped at one end and its stock spilled across the floor, most of the rest gone."""
    W, D = 1.0, 0.4
    st = M.STEEL_GREY
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.box((0.04, 0.04, 1.8), (sx * (W / 2 - 0.02), sy * (D / 2 - 0.02), 0.9), st, bevel=0.002, grain="Z")
        p.box((0.01, D - 0.04, 1.75), (sx * (W / 2 - 0.005), 0, 0.9), st, bevel=0.0)
    levels = (0.08, 0.45, 0.82, 1.19, 1.56)
    shelf = {}
    for k, z in enumerate(levels):
        shelf[k] = p.box((W - 0.01, D - 0.01, 0.025), (0, 0, z), st, bevel=0.002)
        p.box((W - 0.02, 0.01, 0.04), (0, -D / 2 + 0.005, z - 0.01), st, bevel=0.002)
    p.box((W - 0.01, D - 0.01, 0.025), (0, 0, 1.8), st, bevel=0.002)
    r = p.rng("stock")
    vr = p.vrng("take")
    stock = {k: [] for k in range(1, 5)}
    sizes = {1: (0.11, 0.11, 0.065), 2: (0.13, 0.08, 0.05), 3: (0.1, 0.065, 0.04), 4: (0.1, 0.065, 0.04)}
    for k in range(1, 5):
        z = levels[k] + 0.0125
        sw, sd, sh = sizes[k]
        ncol = int((W - 0.1) / (sw + 0.01))
        for c in range(ncol):
            x = -W / 2 + 0.06 + sw / 2 + c * (sw + 0.01)
            cell = f"ammo{(c // 2 + k) % 4}"
            nrow = 2 if k != 1 else 1
            for row in range(nrow):
                y = -D / 2 + 0.03 + sd / 2 + row * (sd + 0.03)
                h = 3 if k > 1 else 2
                if p.worn:
                    h = vr.choice((0, 0, 1, 2)) if k != 1 else vr.choice((0, 1, 1))
                for j in range(h):
                    stock[k].append(_carton(p, (sw, sd, sh), (x + r.uniform(-0.004, 0.004), y, z + sh / 2 + j * sh), cell,
                                            rot=(0, 0, r.uniform(-2, 2))))
            if p.worn and vr.random() < 0.25:
                stock[k].append(_carton(p, (sw, sd, sh), (x, -D / 2 + 0.06, z + sd / 2), cell, rot=(90, 0, vr.uniform(-20, 20))))
    for i, x in enumerate((-0.3, 0.02, 0.33)):
        if p.destroyed and i == 1:
            continue
        _ammo_can(p, (x, 0.0, levels[0] + 0.0125), r.uniform(-3, 3))
    if p.worn:
        for i in range(5 if not p.destroyed else 3):
            _carton(p, (0.1, 0.065, 0.04), (vr.uniform(-0.4, 0.4), -0.45 - vr.uniform(0, 0.3), 0.02), f"ammo{i % 4}",
                    rot=(0, 0, vr.uniform(0, 180)))
    if p.destroyed:
        p.remove(stock[4])
        p.remove(stock[1][::2])
        p.rotate([shelf[3]] + stock[3], rot=(0, -20, 0), pivot=(W / 2 - 0.02, 0, levels[3]))
        for i in range(12):
            _carton(p, (0.13, 0.08, 0.05), (0, 0, 0), f"ammo{i % 4}")
        for q in p.parts[-12:]:
            lo, hi = p.bounds([q])
            p.lay_on_floor([q], rot=(vr.choice((0, 90, 0)), 0, 0), at=(vr.uniform(-0.6, 0.2), vr.uniform(-0.85, -0.3)),
                           yaw=vr.uniform(0, 180))
        p.collider((0, -0.15, 0.9), (W, D + 0.4, 1.8))
    else:
        p.collider((0, 0, 0.9), (W, D, 1.8))


# ================================================================================================
# VFW post
# ================================================================================================


def _frame(p: Prop, w: float, h: float, c, cell: str, *, wood: str = C.OAK_DARK, fw: float = 0.025, tilt: float = 0.0,
           glass: bool = True) -> list:
    """Picture frame on the wall (front -Y), its print from the atlas, a moulding frame and glass."""
    x, y, z = c
    out = [plate(p, w - fw, h - fw, (x, y - 0.004, z), atlas(cell, 2), t=0.004)]
    for sz in (-1, 1):
        out.append(p.box((w, 0.018, fw), (x, y - 0.009, z + sz * (h - fw) / 2), wood, bevel=0.004, grain="X"))
        out.append(p.box((fw, 0.018, h - 2 * fw), (x + sz * (w - fw) / 2, y - 0.009, z), wood, bevel=0.004, grain="Z"))
    if glass:
        out.append(p.box((w - 2 * fw, 0.002, h - 2 * fw), (x, y - 0.012, z), M.GLASS, bevel=0.0, wear=0.0))
    if tilt:
        p.rotate(out, rot=(0, tilt, 0), pivot=(x, y, z + h / 2))
    return out


def vfw_honor_wall(p: Prop) -> None:
    """Honor wall (2.4 x 1.5 x 0.1, origin on the wall plane): the post emblem in bronze at the top centre,
    a triangular oak flag case with the folded post flag, rows of framed service photographs (platoon,
    portrait, aircraft, jeep, camp, ship), walnut-and-brass plaques and framed certificates on a picture
    rail. Hang at ~0.9 m. Worn: frames knocked crooked, two gone (nails left), one photo dropped in its
    frame. No words anywhere."""
    W = 2.4
    p.box((W, 0.025, 0.04), (0, -0.0125, 1.48), C.OAK_DARK, bevel=0.004, grain="X")
    disc_face(p, 0.16, 0.025, (0, -0.0125, 1.25), atlas("emblem"), axis="-Y", segs=20)
    # flag case
    tri = [(-0.3, 0.0), (0.3, 0.0), (0.0, 0.3)]
    p.prism(tri, 0.07, C.OAK, plane="XZ", offset=-0.07).obj.data.transform(Matrix.Translation((0, 0, 0.72)))
    inner = p.prism([(-0.25, 0.03), (0.25, 0.03), (0.0, 0.26)], 0.03, C.PRINT, plane="XZ", offset=-0.075, uv="planar", uv_axis="Y",
                    rect=atlas("velvet", 6))
    inner.obj.data.transform(Matrix.Translation((0, 0, 0.72)))
    p.box((0.62, 0.08, 0.03), (0, -0.04, 0.705), C.OAK, bevel=0.004, grain="X")
    plate(p, 0.16, 0.035, (0, -0.081, 0.705), atlas("plaque", 20), t=0.002)
    r = p.rng("wall")
    vr = p.vrng("crooked")
    layout = [  # (x, z, w, h, cell)
        (-1.0, 1.18, 0.24, 0.3, "photo0"), (-0.68, 1.2, 0.2, 0.26, "photo1"), (-0.38, 1.18, 0.24, 0.3, "photo2"),
        (-1.0, 0.8, 0.24, 0.3, "certificate"), (-0.68, 0.78, 0.2, 0.26, "plaque"), (-0.4, 0.8, 0.2, 0.26, "photo5"),
        (-0.84, 0.42, 0.28, 0.24, "painting"), (-0.45, 0.42, 0.2, 0.26, "plaque"),
        (0.38, 1.18, 0.24, 0.3, "photo3"), (0.68, 1.2, 0.2, 0.26, "photo4"), (1.0, 1.18, 0.24, 0.3, "photo1"),
        (0.4, 0.8, 0.2, 0.26, "plaque"), (0.68, 0.78, 0.2, 0.26, "certificate"), (1.0, 0.8, 0.24, 0.3, "photo0"),
        (0.45, 0.42, 0.2, 0.26, "photo5"), (0.84, 0.42, 0.28, 0.24, "certificate"),
    ]
    missing = (2, 13) if p.worn else ()
    for i, (x, z, w, h, cell) in enumerate(layout):
        if i in missing:
            p.cyl(0.003, 0.02, (x, -0.01, z + h / 2 - 0.02), M.CHROME, axis="Y", segs=4)
            continue
        tilt = vr.uniform(-9, 9) if p.worn and i % 3 == 1 else r.uniform(-0.8, 0.8)
        if cell == "plaque":
            pl = plate(p, w * 0.8, h * 0.85, (x, -0.011, z), atlas(cell, 2), t=0.02, bevel=0.004, wear=0.6)
            if tilt:
                p.rotate([pl], rot=(0, tilt, 0), pivot=(x, 0, z + h / 2))
        else:
            _frame(p, w, h, (x, 0.0, z), cell, tilt=tilt, wood=C.OAK_DARK if i % 2 else M.PL_BLACK, glass=False)
        if p.worn and i == 9:
            p.parts[-6].obj.data.transform(Matrix.Translation((0, 0, -0.04)))
    lo, hi = p.bounds()
    p.move(p.parts, (0, 0, -lo.z))
    p.collider((0, -0.05, (hi.z - lo.z) / 2), (W, 0.1, hi.z - lo.z))


def _flag_cloth(p: Prop, top, side: float, cell: str, *, W: float = 1.1, H: float = 0.7, torn: bool = False) -> core.Part:
    """Indoor flag hanging from a pole at `top` (top of the hoist): the hoist runs down the pole, the fly
    droops toward the floor in soft folds on the `side` (+1 / -1 in X). Two-sided sheet."""
    nx, ny = 10, 6
    rect = atlas(cell, 2)
    top = Vector(top)
    t = 0.003
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    grid = {}

    def pos(u, v):
        hang = u ** 1.2
        x = side * (W * 0.24 * u + 0.03 * math.sin(u * math.pi))
        z = -(1 - v) * H * (1 - 0.15 * u) - W * 0.62 * hang * (0.6 + 0.4 * v)
        y = math.sin(u * math.pi * 3.5 + v * 0.6) * 0.07 * u + 0.015 * math.sin(v * 5 + u * 3)
        return top + Vector((x, y, z))

    for sd in (0, 1):
        for j in range(ny + 1):
            for i in range(nx + 1):
                grid[(sd, i, j)] = bm.verts.new(pos(i / nx, j / ny) + Vector((0, t if sd else 0, 0)))
    for sd in (0, 1):
        for j in range(ny):
            for i in range(nx):
                if torn and i >= nx - 3 and (j + i) % 3 != 0:
                    continue
                ids = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
                vs = [grid[(sd, a, b)] for a, b in ids]
                if (sd == 0) == (side > 0):
                    vs, ids = list(reversed(vs)), list(reversed(ids))
                f = bm.faces.new(vs)
                for lp, (a, b) in zip(f.loops, ids):
                    uu = a / nx if side > 0 else 1 - a / nx
                    lp[uvl].uv = (rect[0] + uu * (rect[2] - rect[0]), rect[1] + b / ny * (rect[3] - rect[1]))
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    obj = G._obj(p._name("flag"), bm)
    return p.add(obj, C.PRINT, uv="keep", wear=0.3, edge_deg=60.0)


def vfw_flag_stand(p: Prop) -> None:
    """Two-flag floor stand (1.6 x 2.6 x 0.6): a weighted brass base with two angled sockets, oak poles with
    brass ball-and-spear finials, the post flag (navy, gold border, chevron disc) and a plain maroon-white
    banded flag hanging in folds. Generic flags, no real national flag. Worn: dusty and faded, the banded
    flag's fly torn ragged, its pole leaning further."""
    p.lathe([(0.0, 0.0), (0.26, 0.0), (0.26, 0.03), (0.22, 0.06), (0.12, 0.09), (0.06, 0.16), (0.0, 0.17)], (0, 0, 0), C.BRASS, segs=18)
    L = 2.45
    for k, side in enumerate((-1, 1)):
        ang = side * (8 if not (p.worn and side > 0) else 13)
        base = Vector((side * 0.04, 0, 0.12))
        d = Vector((math.sin(math.radians(ang)), 0, math.cos(math.radians(ang))))
        top = base + d * L
        rod(p, base, base + d * 0.12, 0.024, C.BRASS, segs=8)
        rod(p, base, top, 0.016, C.OAK, segs=8)
        fin = [p.lathe([(0.0, 0.0), (0.018, 0.0), (0.03, 0.03), (0.035, 0.05), (0.025, 0.08), (0.008, 0.09), (0.008, 0.12), (0.025, 0.13),
                        (0.0, 0.22)], (0, 0, 0), C.BRASS, segs=8)]
        q = Vector((0, 0, 1)).rotation_difference(d)
        place(fin, Matrix.Translation(top) @ q.to_matrix().to_4x4())
        cell = "flag_a" if k == 0 else "flag_b"
        _flag_cloth(p, top - d * 0.05, side, cell, torn=p.worn and k == 1)
        for z in (0.95, 0.55):
            rod(p, top - d * z, top - d * z + Vector((side * 0.02, 0, 0)), 0.012, C.BRASS, segs=6)
    p.collider((0, 0, 1.3), (0.6, 0.6, 2.6))


def _helmet(p: Prop) -> list:
    """Steel-pot helmet at the origin (rim on z = 0): dome, flared rim, chin strap."""
    out = [p.lathe([(0.0, 0.17), (0.07, 0.165), (0.12, 0.13), (0.145, 0.07), (0.15, 0.02), (0.165, 0.0), (0.16, -0.006), (0.14, 0.012),
                    (0.0, 0.012)], (0, 0, 0.006), C.HELMET, segs=16)]
    out.append(p.tube([(-0.14, 0.0, 0.03), (-0.1, -0.06, -0.0), (0.0, -0.09, 0.0), (0.1, -0.06, 0.0), (0.14, 0.0, 0.03)], 0.006,
                      M.BURLAP, segs=4))
    return out


def vfw_memorial_case(p: Prop) -> None:
    """Memorial display case (1.0 x 1.45 x 0.55): a mahogany pedestal cabinet under a glass case framed in
    oak, on a navy velvet deck: a steel-pot helmet, a row of medals on their ribbons, dog tags on a chain, a
    portrait in a standing frame and a folded letter. Worn: dusty, the front glass cracked. Destroyed: the
    glass smashed out, the helmet knocked to the floor, the medals taken but one, shards everywhere."""
    W, D, zb, zt = 1.0, 0.5, 0.9, 1.42
    p.box((W, D, zb - 0.1), (0, 0, (zb - 0.1) / 2 + 0.1), C.MAHOGANY, bevel=0.006, grain="X")
    p.box((W - 0.04, D - 0.06, 0.1), (0, 0.01, 0.05), C.OAK_DARK, bevel=0.004, grain="X")
    for x in (-0.24, 0.24):
        p.box((0.42, 0.015, 0.6), (x, -D / 2 - 0.005, 0.47), C.MAHOGANY, bevel=0.004, grain="Z")
        p.box((0.32, 0.01, 0.5), (x, -D / 2 - 0.013, 0.47), C.MAHOGANY, bevel=0.008, grain="Z")
        p.cyl(0.012, 0.02, (x + (0.16 if x < 0 else -0.16), -D / 2 - 0.02, 0.6), C.BRASS, axis="Y", segs=8)
    p.box((W + 0.04, D + 0.04, 0.04), (0, 0, zb - 0.02), C.MAHOGANY, bevel=0.006, grain="X")
    p.box((W - 0.04, D - 0.04, 0.01), (0, 0, zb + 0.005), C.PRINT, bevel=0.0, uv="planar", uv_axis="Z", rect=atlas("velvet", 6))
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.box((0.03, 0.03, zt - zb), (sx * (W / 2 - 0.015), sy * (D / 2 - 0.015), (zt + zb) / 2), C.OAK, bevel=0.003, grain="Z")
    for sy in (-1, 1):
        p.box((W, 0.03, 0.03), (0, sy * (D / 2 - 0.015), zt), C.OAK, bevel=0.003, grain="X")
    for sx in (-1, 1):
        p.box((0.03, D, 0.03), (sx * (W / 2 - 0.015), 0, zt), C.OAK, bevel=0.003, grain="Y")
    gh = zt - zb - 0.03
    za = zb + 0.01
    if p.destroyed:
        F.shatter_pane(p, W - 0.06, gh, (0, -D / 2 + 0.015, (zt + zb) / 2), M.GLASS, t=0.004, impact=(0.1, 0.05), key="front",
                       missing_inner=1.0, missing_outer=0.6, floor_shards=6, floor_at=(0.0, -0.6))
        r = p.vrng("shards")
        for i in range(5):
            sh = p.prism([(0, 0), (r.uniform(0.04, 0.09), 0.0), (r.uniform(0.0, 0.05), r.uniform(0.04, 0.08))], 0.004, M.GLASS,
                         plane="XY", offset=0.0, uv="planar", uv_axis="Z")
            G.xform(sh.obj, rot=(0, 0, r.uniform(0, 360)), loc=(r.uniform(-0.4, 0.4), r.uniform(-0.2, 0.2), za + 0.001))
    elif p.worn:
        F.shatter_pane(p, W - 0.06, gh, (0, -D / 2 + 0.015, (zt + zb) / 2), M.GLASS, t=0.004, impact=(-0.25, 0.08), spokes=7, rings=3,
                       key="front", missing_inner=0.3, missing_outer=0.0)
    else:
        p.box((W - 0.06, 0.004, gh), (0, -D / 2 + 0.015, (zt + zb) / 2), M.GLASS, bevel=0.0, wear=0.0)
    if not p.destroyed:
        p.box((W - 0.06, D - 0.06, 0.004), (0, 0, zt + 0.004), M.GLASS, bevel=0.0, wear=0.0)
    for sx in (-1, 1):
        p.box((0.004, D - 0.06, gh), (sx * (W / 2 - 0.015), 0, (zt + zb) / 2), M.GLASS, bevel=0.0, wear=0.0)
    p.box((W - 0.06, 0.004, gh), (0, D / 2 - 0.015, (zt + zb) / 2), M.GLASS, bevel=0.0, wear=0.0)
    hel = _helmet(p)
    if p.destroyed:
        p.lay_on_floor(hel, rot=(0, 115, 0), at=(0.45, -0.65), yaw=30)
    else:
        p.move(hel, (-0.28, 0.06, za))
    # medals: ribbon bar + hanging medal
    nm = 4 if not p.destroyed else 1
    for k in range(nm):
        x = 0.05 + k * 0.1
        plate(p, 0.035, 0.05, (x, -0.02, za + 0.002), atlas(f"ribbon{k}", 2), t=0.002, facing="+Z")
        if k % 2 == 0:
            p.cyl(0.02, 0.004, (x, -0.075, za + 0.003), C.BRONZE, segs=10)
        else:
            star = [(math.cos(math.radians(90 + 36 * i)) * (0.024 if i % 2 == 0 else 0.011),
                     math.sin(math.radians(90 + 36 * i)) * (0.024 if i % 2 == 0 else 0.011)) for i in range(10)]
            sp = p.prism(star, 0.004, C.BRASS, plane="XY", offset=0.0)
            G.xform(sp.obj, loc=(x, -0.075, za + 0.001))
    # dog tags on a ball chain
    for k in range(2):
        tag = p.rbox((0.05, 0.028, 0.003), (0.1 + k * 0.025, 0.14 + k * 0.01, za + 0.003 + k * 0.003), M.STAINLESS, radius=0.008,
                     inner=(1, 1, 1))
        G.xform(tag.obj, rot=(0, 0, 20 + k * 15), pivot=(0.1, 0.14, za))
    p.add(G.tube(p._name("chain"), [(0.07, 0.13, za + 0.004), (0.02, 0.18, za + 0.004), (0.06, 0.2, za + 0.004), (0.12, 0.17, za + 0.004)],
                 0.0025, 4, False), C.CHAIN, wear=0.4)
    # standing portrait + folded letter
    pf = _frame(p, 0.14, 0.18, (0.0, 0.0, 0.0), "photo1", glass=False)
    p.rotate(pf, rot=(-12, 0, 0))
    p.move(pf, (0.36, 0.17, za + 0.09))
    p.box((0.008, 0.03, 0.08), (0.36, 0.2, za + 0.04), C.OAK_DARK, bevel=0.0)
    lt = p.box((0.12, 0.09, 0.003), (0.32, -0.12, za + 0.002), M.PAPER, bevel=0.0, uv="planar", uv_axis="Z", rect=core.note_rect(3))
    G.xform(lt.obj, rot=(0, 0, -12), pivot=(0.32, -0.12, za))
    if p.destroyed:
        p.collider((0, -0.05, 0.71), (W + 0.04, D + 0.2, 1.42))
    else:
        p.collider((0, 0, 0.72), (W + 0.04, D + 0.04, 1.44))


def _bottle(p: Prop, c, mat: str, h: float = 0.3, r: float = 0.04, broken: bool = False) -> core.Part:
    if broken:
        prof = [(0.0, 0.0), (r, 0.0), (r, h * 0.35), (r * 0.9, h * 0.42), (r * 0.6, h * 0.38), (r * 0.8, h * 0.3)]
        return p.lathe(prof, c, mat, segs=8, cap_top=False, edge_deg=60)
    prof = [(0.0, 0.0), (r, 0.0), (r, h * 0.6), (r * 0.8, h * 0.7), (r * 0.32, h * 0.8), (r * 0.3, h * 0.97), (r * 0.34, h), (0.0, h)]
    return p.lathe(prof, c, mat, segs=8)


def vfw_bar_taps(p: Prop) -> None:
    """Post back bar (2.1 x 2.2 x 0.62, origin on the wall plane; stands on the floor, hang at 0): a mahogany
    back-bar cabinet with a stainless keg-cooler section and panelled doors, a three-faucet T tap tower
    with odd tap handles over its drip tray, and above it a framed back-bar mirror with a carved crown and
    glass bottle shelves either side. Worn: the mirror cracked out in places, bottles mostly gone and one
    broken on the top, a tap handle missing."""
    W, D, H = 2.0, 0.55, 0.92
    mh = C.MAHOGANY
    yc = -D / 2
    p.box((W, D - 0.02, H - 0.1), (0, yc + 0.01, (H - 0.1) / 2 + 0.1), mh, bevel=0.004, grain="X")
    p.box((W - 0.04, D - 0.06, 0.1), (0, yc + 0.03, 0.05), C.OAK_DARK, bevel=0.004, grain="X")
    p.box((W + 0.05, D + 0.04, 0.045), (0, yc - 0.01, H - 0.0225), mh, bevel=0.008, grain="X")
    yf = -D
    for k, x in enumerate((-0.75, -0.3)):
        p.box((0.42, 0.02, 0.62), (x, yf - 0.01, 0.48), M.STAINLESS, bevel=0.004)
        p.tube([(x + 0.15, yf - 0.02, 0.3), (x + 0.15, yf - 0.05, 0.32), (x + 0.15, yf - 0.05, 0.64), (x + 0.15, yf - 0.02, 0.66)],
               0.008, M.CHROME, segs=5, fillet_r=0.02)
    for x in (0.25, 0.75):
        p.box((0.42, 0.02, 0.62), (x, yf - 0.01, 0.48), mh, bevel=0.004, grain="Z")
        p.box((0.32, 0.012, 0.5), (x, yf - 0.024, 0.48), mh, bevel=0.01, grain="Z")
        p.cyl(0.012, 0.02, (x - 0.15 if x > 0.5 else x + 0.15, yf - 0.03, 0.62), C.BRASS, axis="Y", segs=8)
    # tap tower
    tx, ty = -0.52, -0.3
    p.box((0.5, 0.14, 0.02), (tx, ty - 0.06, H + 0.01), M.STAINLESS, bevel=0.004)
    p.box((0.46, 0.1, 0.006), (tx, ty - 0.06, H + 0.022), M.CAST_IRON, bevel=0.0)
    p.cyl(0.06, 0.02, (tx, ty, H + 0.01), M.CHROME, segs=12)
    p.cyl(0.035, 0.36, (tx, ty, H + 0.18), M.CHROME, segs=10)
    p.cyl(0.035, 0.5, (tx, ty, H + 0.38), M.CHROME, axis="X", segs=10)
    for sx in (-1, 1):
        sphere(p, 0.036, (tx + sx * 0.25, ty, H + 0.38), M.CHROME, segs=10, rings=4)
    handles = [(C.PL_BLACK, 0.16), (C.OAK, 0.2), (C.PAINT_RED, 0.12)]
    for k, (mat, hl) in enumerate(handles):
        x = tx - 0.16 + k * 0.16
        p.cyl(0.012, 0.06, (x, ty - 0.06, H + 0.38), M.CHROME, axis="Y", segs=6)
        p.lathe([(0.014, 0.0), (0.014, 0.05), (0.008, 0.07), (0.006, 0.09)], (x, ty - 0.09, H + 0.38), M.CHROME, segs=6, axis="-Z")
        if p.worn and k == 1:
            continue
        p.lathe([(0.012, 0.0), (0.016, 0.02), (0.02, hl * 0.6), (0.024, hl), (0.0, hl + 0.005)], (x, ty - 0.09, H + 0.4), mat, segs=8)
    # mirror unit
    mz0, mz1 = 1.05, 2.1
    p.box((W, 0.03, mz1 - mz0), (0, -0.015, (mz0 + mz1) / 2), mh, bevel=0.004, grain="X")
    mw, mhh = 1.1, 0.75
    mc = (0, -0.035, 1.5)
    if p.worn:
        F.shatter_pane(p, mw, mhh, mc, C.MIRROR, t=0.004, impact=(0.2, 0.1), spokes=9, rings=3, key="mirror", missing_inner=0.7,
                       missing_outer=0.15, uv="planar")
    else:
        p.box((mw, 0.004, mhh), mc, C.MIRROR, bevel=0.0, uv="planar", uv_axis="Y", wear=0.0)
    for sz in (-1, 1):
        p.box((mw + 0.12, 0.05, 0.06), (0, -0.045, 1.5 + sz * (mhh / 2 + 0.03)), C.OAK_DARK, bevel=0.01, grain="X")
    for sx in (-1, 1):
        p.box((0.06, 0.05, mhh + 0.12), (sx * (mw / 2 + 0.03), -0.045, 1.5), C.OAK_DARK, bevel=0.01, grain="Z")
        p.lathe([(0.035, 0.0), (0.03, 0.05), (0.04, 0.08), (0.03, 0.9), (0.045, 0.93), (0.03, 0.98), (0.0, 1.0)],
                (sx * (W / 2 - 0.05), -0.06, mz0), C.OAK_DARK, segs=8)
    crown = [(-W / 2, 0.0), (W / 2, 0.0), (W / 2, 0.06), (0.3, 0.1), (0.0, 0.2), (-0.3, 0.1), (-W / 2, 0.06)]
    cr = p.prism(crown, 0.08, C.OAK_DARK, plane="XZ", offset=-0.09)
    G.xform(cr.obj, loc=(0, 0, mz1))
    disc_face(p, 0.07, 0.015, (0, -0.095, mz1 + 0.09), atlas("emblem"), axis="-Y", segs=14)
    # bottle shelves
    r = p.rng("bottles")
    vr = p.vrng("gone")
    for sx in (-1, 1):
        for z in (1.2, 1.6):
            p.box((0.32, 0.16, 0.008), (sx * 0.78, -0.11, z), M.GLASS, bevel=0.0, wear=0.0)
            for bx in (-0.12, 0.12):
                p.box((0.012, 0.15, 0.03), (sx * 0.78 + bx, -0.1, z - 0.02), C.BRASS, bevel=0.002)
            for i in range(3):
                if p.worn and vr.random() < 0.65:
                    continue
                mat = (C.BOTTLE_BROWN, C.BOTTLE_GREEN, M.GLASS)[r.randrange(3)]
                _bottle(p, (sx * 0.78 - 0.09 + i * 0.09, -0.1, z + 0.004), mat, h=r.uniform(0.26, 0.32))
    if p.worn:
        _bottle(p, (0.3, -0.25, H), C.BOTTLE_GREEN, h=0.3, broken=True)
        for i in range(4):
            sh = p.prism([(0, 0), (vr.uniform(0.02, 0.05), 0.0), (vr.uniform(0.0, 0.03), vr.uniform(0.02, 0.04))], 0.003, C.BOTTLE_GREEN,
                         plane="XY", offset=0.0)
            G.xform(sh.obj, rot=(0, 0, vr.uniform(0, 360)), loc=(0.3 + vr.uniform(-0.15, 0.15), -0.25 + vr.uniform(-0.1, 0.1), H + 0.001))
    else:
        p.lathe([(0.0, 0.0), (0.03, 0.0), (0.035, 0.14), (0.0, 0.14)], (0.35, -0.3, H), M.GLASS, segs=10, cap_top=False)
    p.collider((0, -D / 2, (H + 0.45) / 2), (W + 0.05, D + 0.04, H + 0.45))
    p.collider((0, -0.06, (mz0 + mz1 + 0.2) / 2), (W, 0.12, mz1 + 0.2 - mz0))


# ================================================================================================
# registry
# ================================================================================================

BUILDERS = {
    "cannery_retort": cannery_retort,
    "cannery_conveyor": cannery_conveyor,
    "cannery_filler": cannery_filler,
    "cannery_can_pallet": cannery_can_pallet,
    "cannery_sorting_table": cannery_sorting_table,
    "cannery_tote_stack": cannery_tote_stack,
    "pump_station_pump": pump_station_pump,
    "pump_pipe_manifold": pump_pipe_manifold,
    "pump_pipe_manifold_wall": pump_pipe_manifold_wall,
    "pump_chlorinator": pump_chlorinator,
    "pump_control_panel": pump_control_panel,
    "quarry_magazine": quarry_magazine,
    "quarry_core_rack": quarry_core_rack,
    "quarry_drill_steel_rack": quarry_drill_steel_rack,
    "quarry_scale_terminal": quarry_scale_terminal,
    "pawn_gun_case": pawn_gun_case,
    "pawn_long_gun_rack": pawn_long_gun_rack,
    "pawn_shelf_mixed": pawn_shelf_mixed,
    "pawn_security_grille": pawn_security_grille,
    "pawn_ammo_shelf": pawn_ammo_shelf,
    "vfw_honor_wall": vfw_honor_wall,
    "vfw_flag_stand": vfw_flag_stand,
    "vfw_memorial_case": vfw_memorial_case,
    "vfw_bar_taps": vfw_bar_taps,
}


def build(params: dict, outputs: list[str]) -> None:
    core.build_variants(params, outputs, BUILDERS[params.get("builder", params["prop"])])
