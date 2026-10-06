"""Civic props of Pell's Crossing - St. Ansel's Church, the Northwoods Tavern, the post office, the grange
hall, the trailer and the town's street fixtures.

Church: oak pew with hymnal rack and kneeler, altar (marble mensa, frontal, fair linen, brass cross and
candlesticks), hexagonal pulpit with steps, hymn board, votive candle stand, alms box, reed organ,
baptismal font, tower bell in its frame with wheel and rope, steeple, church letter-board sign, iron
graveyard railing on a granite kerb, headstones (8 inscriptions), a fresh grave, a stack of hymnals.
Tavern: bar counter with brass foot rail, back bar with mirror and bottles, beer taps, bar stool, pool
table, jukebox, dartboard cabinet, beer keg, beer crates.
Post office: service counter with brass grille, PO box wall, sorting case, wire parcel cage, mail hamper
cart, mail sacks, parcel scale, blue collection box, post-office sign.
Grange hall: folding table and chair, army cot, relief-supply crate, stage lectern, bentwood coat rack,
upright piano, trophy case, grange banner, shelter roll-call board, blanket pile.
Trailer: ham radio set, antenna mast.

Built on the interior-props framework (lib/props_int_core.py: Prop, variants clean / worn / destroyed,
wear / AO vertex colours, collision boxes). Printed and carved graphics come from three atlases made by
textures/gen/civic.py; their pixel rects are mirrored in ATLAS / ENGRAVE below (keep them in sync).

params: prop (id), seed, variants, mount, budget, plus per-prop knobs (see blender_catalogs/props_civic.py).
"""
from __future__ import annotations

import math

import bmesh
from mathutils import Matrix, Vector

from lib import common
from lib import props_ext_kit as EK
from lib import props_int_core as core
from lib import props_int_furn as F
from lib import props_int_mesh as G
from lib.props_int_core import M, Prop


class C:
    """Material ids: civic_* from game/data/materials/props_civic.json, the rest shared families."""
    OAK = "civic_oak"
    OAK_DARK = "civic_oak_dark"
    MAHOGANY = "civic_mahogany"
    FELT_GREEN = "civic_felt_green"
    FELT_RED = "civic_felt_red"
    GRANITE = "civic_granite"
    MARBLE = "civic_marble"
    ENG_GRANITE = "civic_engrave_granite"
    ENG_MARBLE = "civic_engrave_marble"
    IRON = "civic_iron"
    BRONZE = "civic_bronze"
    BRASS = "civic_brass"
    WOOL_GREY = "civic_wool_grey"
    WOOL_OLIVE = "civic_wool_olive"
    WOOL_BROWN = "civic_wool_brown"
    PRINT = "civic_print"
    PO_BOXES = "civic_po_boxes"
    MAIL_BLUE = "civic_mail_blue"
    CRATE = "civic_crate_olive"
    PIANO = "civic_piano_black"
    IVORY = "civic_ivory"
    EBONY = "civic_ebony"
    VOTIVE = "civic_votive_glass"
    SHINGLE = "civic_shingle"
    SOIL = "civic_soil"
    MESH = "civic_wire_mesh"
    # shared (props_exterior.json)
    WHITE_WOOD = "paint_white_wood"
    WEATHERED = "wood_weathered"
    FRESH_WOOD = "wood_fresh"
    GALV = "metal_galvanized"
    CANVAS_OLIVE = "canvas_olive"
    CANVAS_KHAKI = "canvas_khaki"
    CANVAS_GREY = "canvas_grey"
    CANVAS_NAVY = "canvas_navy"
    GLASS_BROWN = "glass_brown"
    GLASS_GREEN = "glass_green"
    GLASS_CLEAR = "glass_clear"
    CANDLE = "candle_wax"
    LEATHER = "leather_dark"
    RUBBER = "rubber_black"
    FLANNEL = "flannel_red"
    PAPER = "paper_pages"
    PAINT_GREEN = "paint_green"
    PAINT_RED = "paint_red"


# civic_print atlas rects (x0, y0, x1, y1) in pixels of the 1024 px texture - mirror of
# textures/gen/civic.py PRINT_RECTS.
ATLAS: dict[str, tuple[int, int, int, int]] = {
    "dart": (0, 0, 256, 256),
    "juke_cards": (256, 0, 512, 128),
    "juke_grille": (256, 128, 512, 256),
    "labels": (512, 0, 768, 256),
    "taps": (768, 0, 1024, 128),
    "hymn_header": (768, 128, 1024, 160),
    "hymn_cards": (768, 160, 1024, 256),
    "relief_side": (0, 256, 256, 384),
    "relief_end": (0, 384, 256, 512),
    "mail_front": (256, 256, 384, 512),
    "mail_side": (384, 256, 512, 512),
    "notice": (512, 256, 640, 432),
    "alms": (512, 432, 640, 464),
    "closed_sign": (512, 464, 640, 512),
    "po_sign": (640, 256, 1024, 320),
    "church_sign": (640, 320, 1024, 512),
    "altar_frontal": (0, 512, 256, 640),
    "fallboard": (256, 512, 512, 544),
    "plaques": (256, 544, 512, 640),
    "scale_dial": (512, 512, 640, 640),
    "hymnal": (640, 512, 704, 608),
    "hymnal_spine": (704, 512, 720, 608),
    "sort_labels": (720, 512, 1024, 640),
    "banner": (0, 640, 512, 768),
    "juke_arch": (512, 640, 768, 768),
    "photo": (768, 640, 896, 768),
    "keg_stamp": (896, 640, 1024, 768),
    "pool_balls": (0, 768, 512, 800),
    "relief_lid": (0, 800, 256, 928),
    "cot_tag": (256, 800, 384, 864),
    "felt_board": (384, 800, 512, 1024),
    "ledger": (512, 768, 768, 1024),
    "wood_plain": (768, 768, 1024, 1024),
}
# PO box doors drawn pried open in civic_po_boxes (textures/gen/civic.py PRIED_DOORS).
PO_PRIED = (7, 32, 54, 62, 70, 71, 95)


def atlas(name: str, k: int | None = None, inset: float = 1.0) -> tuple[float, float, float, float]:
    """UV rect (u0, v0, u1, v1) of an atlas entry; k picks a sub-cell of the strip entries."""
    x0, y0, x1, y1 = ATLAS[name]
    if k is not None:
        if name in ("labels", "hymn_cards", "plaques"):
            y0, y1 = y0 + 32 * k, y0 + 32 * k + 32
        elif name == "taps":
            x0, x1 = x0 + 64 * k, x0 + 64 * k + 64
        elif name == "pool_balls":
            x0, x1 = x0 + 32 * k, x0 + 32 * k + 32
        elif name == "sort_labels":
            cx, cy = k % 2, k // 2
            x0, x1 = x0 + 152 * cx, x0 + 152 * cx + 152
            y0, y1 = y0 + 32 * cy, y0 + 32 * cy + 32
    return core._px_rect(x0 + inset, y0 + inset, x1 - inset, y1 - inset)


def engrave(k: int, y0: float = 0.0, y1: float = 512.0) -> tuple[float, float, float, float]:
    """UV rect of carved headstone face k (civic_engrave: 4 x 2 cells of 256 x 512 px), optionally only the
    rows y0..y1 of the cell."""
    cx, cy = k % 4, k // 4
    return core._px_rect(cx * 256 + 2, cy * 512 + y0 + 2, cx * 256 + 254, cy * 512 + y1 - 2)


# ------------------------------------------------------------------------------------------------
# shared helpers
# ------------------------------------------------------------------------------------------------


def _rot_for(facing: str) -> tuple[float, float, float]:
    return {"-Y": (0, 0, 0), "+Y": (0, 0, 180), "+X": (0, 0, 90), "-X": (0, 0, -90), "+Z": (-90, 0, 0),
            "-Z": (90, 0, 0)}[facing]


def plate(p: Prop, w: float, h: float, center, uvrect, *, t: float = 0.002, mat: str = C.PRINT, facing: str = "-Y",
          tags=(), wear: float = 0.35, bevel: float = 0.0, rot=None) -> core.Part:
    """Thin printed panel w x h (built in the XZ plane facing -Y, then turned to `facing`) whose front face
    shows `uvrect`; back and edges sample the rect's edge so nothing stretches wildly."""
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


def box_uvs(obj, scale: float = 1.0, skip=None, offset=(0.0, 0.0)) -> None:
    """Metre box projection written as fixed UVs (for parts mixing an atlas face with tiling faces)."""
    me = obj.data
    uvl = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        if skip is not None and skip(poly):
            continue
        n = poly.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if ax == 0:
                u, v = (co.y if n.x > 0 else -co.y), co.z
            elif ax == 1:
                u, v = (-co.x if n.y > 0 else co.x), co.z
            else:
                u, v = co.x, (co.y if n.z > 0 else -co.y)
            uvl.data[li].uv = (u * scale + offset[0], v * scale + offset[1])


def atlas_front(obj, uvrect, normal=(0.0, -1.0, 0.0), axes=(0, 2), flip=False) -> None:
    """Maps the faces of obj facing `normal` onto uvrect (their bounding square in `axes`)."""
    nv = Vector(normal)
    me = obj.data
    uvl = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
    faces = [poly for poly in me.polygons if poly.normal.dot(nv) > 0.9]
    if not faces:
        return
    pts = [me.vertices[i].co for poly in faces for i in poly.vertices]
    lo = [min(c[a] for c in pts) for a in axes]
    hi = [max(c[a] for c in pts) for a in axes]
    u0, v0, u1, v1 = uvrect
    for poly in faces:
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            tu = (co[axes[0]] - lo[0]) / max(1e-6, hi[0] - lo[0])
            tv = (co[axes[1]] - lo[1]) / max(1e-6, hi[1] - lo[1])
            if flip:
                tu = 1.0 - tu
            uvl.data[li].uv = (u0 + tu * (u1 - u0), v0 + tv * (v1 - v0))


def bar(p: Prop, a, b, w: float, d: float, mat: str, **kw) -> core.Part:
    """Rectangular beam / bar from point a to b (w across, d in the 'up' direction of the bar)."""
    a, b = Vector(a), Vector(b)
    v = b - a
    L = v.length
    obj = G.box(p._name("bar"), (w, d, L), (0, 0, 0), kw.pop("bevel", 0.004))
    q = Vector((0, 0, 1)).rotation_difference(v.normalized())
    obj.data.transform(Matrix.Translation((a + b) * 0.5) @ q.to_matrix().to_4x4())
    obj.data.update()
    kw.setdefault("grain", "Z")
    return p.add(obj, mat, **kw)


def sphere(p: Prop, r: float, center, mat: str, segs: int = 10, rings: int = 6, **kw) -> core.Part:
    prof = [(0.0, -r)] + [(r * math.sin(math.pi * i / rings), -r * math.cos(math.pi * i / rings)) for i in range(1, rings)] + [(0.0, r)]
    prof = [(rr, z) for rr, z in prof]
    return p.lathe(prof, center, mat, segs=segs, **kw)


def hymnal(p: Prop, center, rot=(0, 0, 0), size=(0.032, 0.115, 0.17), open_deg: float = 0.0, key: str = "hymnal") -> list:
    """Maroon hymnal standing with its spine toward -Y (before rot): covers on +-X from the atlas, spine
    strip, page block. open_deg > 0 lays it open (two halves) instead."""
    tx, dy, hz = size
    cov, spine, pages = atlas("hymnal"), atlas("hymnal_spine"), atlas("ledger")
    pages = (pages[0], pages[1], pages[0] + 0.004, pages[3])
    out = []
    if open_deg <= 0.0:
        obj = G.box(p._name("hym"), size, (0, 0, 0), 0.0)

        def fr(poly):
            n = poly.normal
            if n.y < -0.9:
                return (*spine, 0, 2, False)
            if abs(n.x) > 0.9:
                return (*cov, 1, 2, n.x < 0)
            return (*pages, 0, 1 if abs(n.z) > 0.9 else 2, False)

        core.set_face_uvs(obj, fr)
        G.xform(obj, rot=rot, loc=center)
        out.append(p.add(obj, C.PRINT, uv="keep", tags=("book", key), wear=0.6))
        return out
    for side in (-1, 1):
        half = G.box(p._name("hymh"), (dy, hz, tx * 0.5), (side * dy * 0.5, 0, tx * 0.25), 0.0)
        core.set_face_uvs(half, lambda poly: (*(pages if poly.normal.z > 0.9 else cov), 0, 1, False))
        G.xform(half, rot=(0, -side * open_deg * 0.12, 0), pivot=(0, 0, 0))
        G.xform(half, rot=rot, loc=center)
        out.append(p.add(half, C.PRINT, uv="keep", tags=("book", key), wear=0.6))
    return out


# Candle flame profile (radius, height above the wick's foot): drawn only while the prop's light
# burns ("flame_glow", ADR-0023), so an unlit candle shows just its wick.
FLAME_PROFILE = [(0.0, 0.0), (0.0045, 0.004), (0.006, 0.011), (0.0042, 0.02), (0.0018, 0.027), (0.0, 0.031)]


def flame(p: Prop, center, scale: float = 1.0, key: str = "flame"):
    """A candle flame standing on `center` (the top of the wick)."""
    prof = [(rr * scale, zz * scale) for rr, zz in FLAME_PROFILE]
    return p.lathe(prof, center, "flame_glow", segs=6, tags=("flame", key))


def candle(p: Prop, center, h: float, r: float = 0.02, burnt: bool = False, key: str = "candle") -> list:
    """Wax candle (burnt: short stub with drips and a pooled foot) with its flame."""
    x, y, z = center
    hh = h * (0.35 if burnt else 1.0)
    out = [p.cyl(r, hh, (x, y, z + hh / 2), C.CANDLE, segs=8, tags=("candle", key))]
    out.append(p.cyl(0.0015, 0.012, (x, y, z + hh + 0.006), M.CAST_IRON, segs=4, tags=("candle", key)))
    out.append(flame(p, (x, y, z + hh + 0.005), key=key))
    if burnt:
        rr = p.rng(key + "drip")
        for i in range(3):
            a = rr.uniform(0, 2 * math.pi)
            out.append(p.box((0.008, 0.008, hh * rr.uniform(0.4, 0.9)), (x + math.cos(a) * r, y + math.sin(a) * r, z + hh * 0.45),
                             C.CANDLE, bevel=0.0, tags=("candle", key)))
        out.append(p.cyl(r * 1.8, 0.004, (x, y, z + 0.002), C.CANDLE, segs=8, tags=("candle", key)))
    return out


def bottle(p: Prop, kind: int, center, label: int | None = None, yaw: float = 0.0, scale: float = 1.0, key: str = "bottle",
           cap: str = M.TIN) -> list:
    """Liquor / beer bottle standing at center (bottom). kind 0 whiskey (squat), 1 wine/spirits (tall), 2 beer,
    3 gin (square-ish shoulder). label = bottle_labels index."""
    x, y, z = center
    s = scale
    if kind == 0:
        prof = [(0.0, 0.0), (0.038, 0.0), (0.04, 0.01), (0.04, 0.17), (0.034, 0.2), (0.015, 0.23), (0.013, 0.27), (0.0, 0.272)]
        glass, lab_z, lab_h, lab_r = C.GLASS_BROWN, 0.1, 0.07, 0.041
    elif kind == 1:
        prof = [(0.0, 0.0), (0.036, 0.0), (0.037, 0.01), (0.037, 0.2), (0.03, 0.24), (0.014, 0.27), (0.012, 0.32), (0.0, 0.322)]
        glass, lab_z, lab_h, lab_r = C.GLASS_CLEAR, 0.11, 0.08, 0.038
    elif kind == 2:
        prof = [(0.0, 0.0), (0.03, 0.0), (0.031, 0.01), (0.031, 0.13), (0.025, 0.16), (0.012, 0.2), (0.011, 0.235), (0.0, 0.237)]
        glass, lab_z, lab_h, lab_r = C.GLASS_BROWN, 0.06, 0.055, 0.032
    else:
        prof = [(0.0, 0.0), (0.04, 0.0), (0.042, 0.01), (0.042, 0.19), (0.03, 0.215), (0.014, 0.23), (0.013, 0.27), (0.0, 0.272)]
        glass, lab_z, lab_h, lab_r = C.GLASS_GREEN, 0.09, 0.075, 0.043
    prof = [(r * s, zz * s) for r, zz in prof]
    out = [p.lathe(prof, (x, y, z), glass, segs=8, tags=("bottle", key), wear=0.3)]
    top = prof[-2][1]
    out.append(p.cyl(prof[-2][0] * 1.15, 0.016 * s, (x, y, z + top), cap, segs=6, tags=("bottle", key)))
    if label is not None:
        out.append(label_arc(p, lab_r * s, lab_h * s, (x, y, z + lab_z * s), atlas("labels", label), yaw=yaw, key=key))
    return out


def label_arc(p: Prop, r: float, h: float, center, uvrect, arc_deg: float = 190.0, segs: int = 8, yaw: float = 0.0,
              key: str = "label") -> core.Part:
    """Paper label wrapped on the front (-Y, then yaw) half of a cylinder, mapped left->right to uvrect."""
    bm = bmesh.new()
    a0 = math.radians(-90.0 - arc_deg / 2)
    rows = []
    for zz in (-h / 2, h / 2):
        rows.append([bm.verts.new((r * math.cos(a0 + math.radians(arc_deg) * i / segs), r * math.sin(a0 + math.radians(arc_deg) * i / segs), zz))
                     for i in range(segs + 1)])
    uvl = bm.loops.layers.uv.new("UVMap")
    u0, v0, u1, v1 = uvrect
    for i in range(segs):
        f = bm.faces.new((rows[0][i], rows[0][i + 1], rows[1][i + 1], rows[1][i]))
        for loop in f.loops:
            idx = rows[0].index(loop.vert) if loop.vert in rows[0] else rows[1].index(loop.vert)
            top = loop.vert in rows[1]
            loop[uvl].uv = (u1 - (u1 - u0) * idx / segs, v1 if top else v0)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = common.mesh_from_bmesh(p._name("label"), bm)
    G.xform(obj, rot=(0, 0, yaw), loc=center)
    return p.add(obj, C.PRINT, uv="keep", tags=("label", key), wear=0.5, edge_deg=50)


def scatter_papers(p: Prop, c, n: int, spread: float, key: str, z_step: float = 0.0012, floor: bool = False) -> list:
    r = p.rng(key)
    out = []
    for i in range(n):
        sh = p.box((0.215, 0.28, 0.0012), (0, 0, 0), M.PAPER, bevel=0.0, uv="keep", tags=("paper",))
        core.set_face_uvs(sh.obj, lambda poly, k=r.randrange(4): (*core.note_rect(k), 0, 1, False))
        rx = r.uniform(-4, 4) if floor else 0.0
        G.xform(sh.obj, rot=(rx, 0, r.uniform(-40, 40)),
                loc=(c[0] + r.uniform(-spread, spread), c[1] + r.uniform(-spread, spread), c[2] + 0.0006 + i * z_step))
        out.append(sh)
    return out


def fold_blanket(p: Prop, center, size=(0.5, 0.35, 0.09), mat: str = C.WOOL_GREY, yaw: float = 0.0, key: str = "blanket") -> core.Part:
    """Folded wool blanket (soft slab with fold lines)."""
    b = p.rbox(size, (0, 0, 0), mat, radius=0.02, inner=(4, 3, 2), bulge=(0, 0, 0.006), wrinkle=0.004, wrinkle_scale=14.0,
               seed=len(key) + p.seed, tags=("cloth", key), edge_deg=30)
    me = b.obj.data
    for v in me.vertices:  # fold creases across the slab
        if abs(v.co.z) > size[2] * 0.3:
            v.co.z -= 0.004 * (1.0 - abs(math.sin(v.co.y / max(1e-3, size[1]) * math.pi * 2)))
    me.update()
    G.xform(b.obj, rot=(0, 0, yaw), loc=(center[0], center[1], center[2] + size[2] / 2))
    return b


# ================================================================================================
# CHURCH
# ================================================================================================


def _pew_end(p: Prop, x0: float, t: float, mat: str, key: str) -> list:
    """Scrolled pew end in the YZ plane, outer face on the side away from the pew centre."""
    prof = [(-0.30, 0.0), (-0.19, 0.0), (-0.17, 0.045), (0.16, 0.045), (0.18, 0.0), (0.31, 0.0), (0.31, 0.93),
            (0.305, 0.965), (0.285, 0.99), (0.25, 1.0), (0.19, 0.995), (0.135, 0.975), (0.09, 0.94), (0.055, 0.885),
            (0.03, 0.81), (0.008, 0.745), (-0.02, 0.705), (-0.06, 0.685), (-0.25, 0.685), (-0.285, 0.675), (-0.305, 0.65),
            (-0.31, 0.62), (-0.3, 0.58), (-0.275, 0.55), (-0.27, 0.13), (-0.29, 0.08), (-0.3, 0.05)]
    end = p.prism(prof, t, mat, plane="YZ", offset=x0, bevel=0.004, tags=("panel", key), grain="Z")
    out = [end]
    side = 1.0 if x0 > 0 else -1.0
    xo = x0 + t if side > 0 else x0
    # raised fielded panel and a carved cross on the outer face
    pn = p.panel(0.32, 0.42, 0.014, (0, 0, 0), mat, style="raised", frame=0.05, recess=0.004, tags=("panel", key))
    G.xform(pn.obj, rot=(0, 0, 90 * side), loc=(xo + side * 0.006, -0.02, 0.33))
    out.append(pn)
    for sz, cz in (((0.012, 0.03, 0.16), 0.86), ((0.012, 0.11, 0.03), 0.89)):
        out.append(p.box(sz, (xo + side * 0.005, 0.17 - (0.03 if sz[1] > 0.05 else 0.0) + 0.03, cz), mat, bevel=0.003, tags=("panel", key)))
    return out


def civic_pew(p: Prop) -> None:
    """Church pew 3.0 x 0.62 (0.73 with the hymnal rack), back 1.0 m: quarter-sawn oak scrolled ends with
    fielded panels and carved crosses, bullnosed seat, raked back with a moulded cap rail, a closed back
    panel with a hymnal rack and a red-felt kneeler for the row behind. Worn: kneeler down, a hymnal and a
    folded army blanket left on the seat (people slept here). Destroyed: seat stove in, back snapped and
    folded forward, an end knocked off, hymnals strewn."""
    L, t = 3.0, 0.05
    wood = C.OAK_DARK
    seat_z = 0.44
    ends = {}
    for side in (-1, 1):
        x0 = side * L / 2 - (t if side > 0 else 0.0)
        ends[side] = _pew_end(p, x0, t, wood, f"end{side}")
    iw = L - 2 * t
    seat_parts = []
    if p.destroyed:
        for side in (-1, 1):  # seat split in the middle, both halves sagging to the floor in a V
            half = p.rbox((iw / 2 - 0.02, 0.4, 0.035), (side * (iw / 4 + 0.01), -0.07, seat_z), wood, radius=0.012, inner=(4, 2, 1),
                          tags=("seat",), grain="X")
            G.xform(half.obj, rot=(0, side * 14, 0), pivot=(side * (iw / 2), -0.07, seat_z))
            seat_parts.append(half)
    else:
        seat_parts.append(p.rbox((iw, 0.4, 0.035), (0, -0.07, seat_z), wood, radius=0.012, inner=(6, 2, 1), tags=("seat",), grain="X"))
    p.box((iw, 0.02, 0.07), (0, -0.255, seat_z - 0.05), wood, bevel=0.003, grain="X")
    p.box((0.05, 0.36, 0.38), (0, -0.04, 0.2), wood, bevel=0.004, grain="Z")
    p.box((iw, 0.05, 0.045), (0, 0.18, 0.04), wood, bevel=0.004, grain="X")
    # closed back below the seat, raked back above it
    p.box((iw, 0.022, 0.43), (0, 0.275, 0.225), wood, bevel=0.003, grain="X")
    back = [p.box((iw, 0.026, 0.44), (0, 0.235, 0.71), wood, bevel=0.003, grain="X", tags=("back",))]
    back.append(p.rbox((iw + 0.01, 0.075, 0.045), (0, 0.235, 0.945), wood, radius=0.016, inner=(6, 1, 1), tags=("back",), grain="X"))
    back.append(p.box((iw, 0.03, 0.025), (0, 0.222, 0.5), wood, bevel=0.003, grain="X", tags=("back",)))
    p.rotate(back, rot=(-10, 0, 0), pivot=(0, 0.25, 0.49))
    # hymnal rack on the back for the row behind
    rack = [p.box((iw - 0.1, 0.12, 0.014), (0, 0.345, 0.66), wood, bevel=0.002, grain="X", tags=("rack",))]
    rack.append(p.box((iw - 0.1, 0.012, 0.075), (0, 0.405, 0.69), wood, bevel=0.002, grain="X", tags=("rack",)))
    for bx in (-iw / 2 + 0.08, 0.0, iw / 2 - 0.08):
        rack.append(p.box((0.014, 0.12, 0.09), (bx, 0.345, 0.69), wood, bevel=0.002, grain="Y", tags=("rack",)))
    r = p.rng("hymnals")
    books = []
    x = -iw / 2 + 0.14
    while x < iw / 2 - 0.14:
        if r.random() < 0.55 and not (p.destroyed and r.random() < 0.6):
            books += hymnal(p, (x, 0.345, 0.667 + 0.085), rot=(0, r.uniform(-6, 6), 180), key=f"h{int(x * 100)}")
        x += r.uniform(0.07, 0.24)
    # kneeler on brackets at the back bottom
    kn = [p.box((iw - 0.2, 0.15, 0.025), (0, 0.0, 0.0), wood, bevel=0.003, grain="X", tags=("kneeler",))]
    kn.append(p.rbox((iw - 0.24, 0.13, 0.04), (0, 0.0, 0.03), C.FELT_RED, radius=0.012, inner=(6, 2, 1), wrinkle=0.002, seed=p.seed,
                     tags=("kneeler",)))
    for bx in (-iw / 2 + 0.15, iw / 2 - 0.15):
        kn.append(p.box((0.03, 0.06, 0.04), (bx, -0.07, 0.0), M.CAST_IRON, bevel=0.003, tags=("kneeler",)))
    if p.worn and not p.destroyed:
        p.move(kn, (0, 0.38, 0.1))
    elif p.destroyed:
        p.lay_on_floor(kn, rot=(0, 0, 0), at=(0.4, 0.65), yaw=p.vrng("kn").uniform(-20, 20))
    else:
        p.rotate(kn, rot=(90, 0, 0), pivot=(0, -0.07, 0.0))
        p.move(kn, (0, 0.31, 0.12))
    if p.cond == "worn":
        fold_blanket(p, (-0.95, -0.07, seat_z + 0.018), (0.55, 0.36, 0.08), C.WOOL_GREY, yaw=4, key="blanket")
        hymnal(p, (0.6, -0.12, seat_z + 0.035), rot=(90, 0, 25), key="seat_hymnal")
    if p.destroyed:
        rr = p.vrng("wreck")
        # the right half of the back snapped and folded forward onto the seat
        bh = p.box((iw / 2 - 0.05, 0.026, 0.42), (iw / 4, 0.05, seat_z + 0.06), wood, bevel=0.003, grain="X", tags=("back",))
        G.xform(bh.obj, rot=(-72, 0, 6), pivot=(iw / 4, 0.2, seat_z))
        for q in back:
            G.splinter_cut(q.obj, (0.05, 0, 0), (1, 0, 0), jag=0.03, seed=p.seed + 3)
        # the left end knocked off and lying on its face
        p.lay_on_floor(ends[-1], rot=(0, 90, 0), at=(-L / 2 - 0.45, -0.1), yaw=rr.uniform(-25, 25))
        for i, bk in enumerate(books[:4]):
            p.lay_on_floor([bk], rot=(90, 0, 0), at=(rr.uniform(-1.2, 1.2), rr.uniform(-0.7, -0.35)), yaw=rr.uniform(0, 180))
        p.collider((0.15, 0.05, 0.3), (L - 0.3, 0.66, 0.6))
    else:
        p.collider((0, 0.03, 0.5), (L, 0.68, 1.0))


def civic_altar(p: Prop) -> None:
    """Oak altar 2.0 x 0.8 x 0.97 with three arched raised panels and pilasters, a white marble mensa, an
    embroidered red frontal, the fair linen hanging off both ends, and on the gradine behind it a brass
    altar cross and two brass candlesticks. Worn: candles burnt to stubs with drips, a missal open on its
    stand. Destroyed: the cross thrown down across the mensa, a candlestick on the floor, the frontal torn
    in two, the linen dragged half off."""
    W, D, H = 2.0, 0.8, 0.9
    wood = C.OAK
    p.box((W + 0.1, D + 0.1, 0.08), (0, 0.0, 0.04), C.OAK_DARK, bevel=0.006, grain="X")
    p.box((W, D, H - 0.08), (0, 0.0, 0.08 + (H - 0.08) / 2), wood, bevel=0.004, grain="X")
    for i, x in enumerate((-0.64, 0.0, 0.64)):
        pn = p.panel(0.5, 0.58, 0.022, (x, -D / 2 - 0.011, 0.47), wood, style="raised", frame=0.055, recess=0.006, tags=("panel",))
        if p.destroyed and i == 2:
            p.remove([pn])
            a, b = F.split_panel(p, 0.5, 0.58, 0.022, (x, -D / 2 - 0.011, 0.47), wood, (-0.25, 0.1), (0.25, -0.12), key="kick")
            G.xform(b.obj, rot=(14, 0, 0), pivot=(x, -D / 2, 0.2))
    for x in (-0.95, -0.32, 0.32, 0.95):
        p.box((0.06, 0.03, H - 0.12), (x, -D / 2 - 0.015, 0.08 + (H - 0.12) / 2), C.OAK_DARK, bevel=0.004, grain="Z")
    p.box((W + 0.04, 0.035, 0.05), (0, -D / 2 - 0.02, H - 0.03), C.OAK_DARK, bevel=0.006, grain="X")
    mensa_z = H + 0.05
    p.box((W + 0.12, D + 0.08, 0.05), (0, 0.0, H + 0.025), C.MARBLE, bevel=0.008, grain="X")
    # gradine (shelf) with cross and candlesticks
    p.box((1.7, 0.22, 0.16), (0, D / 2 - 0.12, mensa_z + 0.08), C.OAK_DARK, bevel=0.005, grain="X")
    g_z = mensa_z + 0.16
    cross = [p.box((0.2, 0.12, 0.03), (0, D / 2 - 0.12, g_z + 0.015), C.BRASS, bevel=0.004),
             p.box((0.14, 0.09, 0.03), (0, D / 2 - 0.12, g_z + 0.045), C.BRASS, bevel=0.004),
             p.box((0.034, 0.03, 0.5), (0, D / 2 - 0.12, g_z + 0.06 + 0.25), C.BRASS, bevel=0.004),
             p.box((0.28, 0.03, 0.034), (0, D / 2 - 0.12, g_z + 0.43), C.BRASS, bevel=0.004)]
    for cx, cz in ((-0.14, g_z + 0.43), (0.14, g_z + 0.43), (0.0, g_z + 0.56)):
        cross.append(sphere(p, 0.022, (cx, D / 2 - 0.12, cz), C.BRASS, segs=8, rings=4))
    sticks = {}
    for side in (-1, 1):
        x = side * 0.62
        prof = [(0.0, 0.0), (0.07, 0.0), (0.07, 0.012), (0.045, 0.03), (0.02, 0.06), (0.016, 0.15), (0.03, 0.17), (0.016, 0.19),
                (0.015, 0.3), (0.045, 0.32), (0.05, 0.335), (0.0, 0.336)]
        grp = [p.lathe(prof, (x, D / 2 - 0.12, g_z), C.BRASS, segs=12)]
        grp += candle(p, (x, D / 2 - 0.12, g_z + 0.336), 0.3, 0.021, burnt=p.worn, key=f"c{side}")
        sticks[side] = grp
    linen_y1 = D / 2 - 0.24
    linen = F.drape(p, -(W + 0.12) / 2, (W + 0.12) / 2, -(D + 0.08) / 2, linen_y1, mensa_z + 0.006, M.LINEN, hang=(0.32, 0.32, 0.05, 0.0),
                    res=0.1, wrinkle=0.003, seed=p.seed, thickness=0.003, shift=(0.12, 0.0) if p.destroyed else (0.0, 0.0))
    if p.destroyed:
        G.xform(linen.obj, rot=(0, 9, 0), pivot=((W + 0.12) / 2, 0, mensa_z))
    if not p.destroyed:
        plate(p, 1.5, 0.52, (0, -D / 2 - 0.035, H - 0.3), atlas("altar_frontal"), t=0.004, tags=("cloth",), wear=0.4)
    else:
        a, b = F.split_panel(p, 1.5, 0.52, 0.004, (0, -D / 2 - 0.035, H - 0.3), C.PRINT, (-0.75, 0.08), (0.2, -0.26), key="frontal")
        for q in (a, b):
            q.uv = "keep"
            me = q.obj.data
            uvl = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
            u0, v0, u1, v1 = atlas("altar_frontal")
            for li, loop in enumerate(me.loops):
                co = me.vertices[loop.vertex_index].co
                uvl.data[li].uv = (u0 + (co.x / 1.5 + 0.5) * (u1 - u0), v0 + ((co.z - (H - 0.3)) / 0.52 + 0.5) * (v1 - v0))
        p.lay_on_floor([b], rot=(-84, 0, 0), at=(0.35, -D / 2 - 0.4), yaw=12)
    if p.worn and not p.destroyed:
        stand = [p.box((0.24, 0.2, 0.012), (0.48, -0.1, mensa_z + 0.06), C.BRASS, bevel=0.002)]
        stand.append(p.box((0.2, 0.03, 0.06), (0.48, -0.03, mensa_z + 0.03), C.BRASS, bevel=0.003))
        p.rotate(stand, rot=(22, 0, 0), pivot=(0.48, -0.03, mensa_z))
        hymnal(p, (0.48, -0.1, mensa_z + 0.085), rot=(22, 0, 0), open_deg=150, key="missal")
    if p.destroyed:
        rr = p.vrng("wreck")
        p.lay_on_floor(cross, rot=(90, 0, 0), at=(-0.25, -0.05), yaw=70, z=mensa_z)
        p.lay_on_floor(sticks[1], rot=(90, 0, 0), at=(1.25, -0.7), yaw=rr.uniform(0, 180))
    p.collider((0, 0.0, 0.55), (W + 0.12, D + 0.1, 1.1))


def civic_pulpit(p: Prop) -> None:
    """Raised hexagonal oak pulpit (tub 1.1 across, floor 0.5 up, rail 1.5): five fielded panels, moulded
    rails and base, a slanted book desk with a red fall, two steps and a handrail up the open back. Worn:
    a sermon in loose pages on the desk, a candle stub. Destroyed: two front panels staved in, the desk
    torn off and lying below, pages everywhere."""
    R = 0.56
    ap = R * math.cos(math.radians(30))
    floor_z, top_z = 0.5, 1.5
    hexpts = [(R * math.cos(math.radians(60 * i)), R * math.sin(math.radians(60 * i))) for i in range(6)]
    p.prism([(x * 1.06, y * 1.06) for x, y in hexpts], 0.07, C.OAK_DARK, plane="XY", offset=0.0, bevel=0.006, grain="X")
    p.prism(hexpts, floor_z - 0.12, C.OAK, plane="XY", offset=0.07, bevel=0.004, grain="Z")
    p.prism([(x * 1.07, y * 1.07) for x, y in hexpts], 0.05, C.OAK_DARK, plane="XY", offset=floor_z - 0.05, bevel=0.006, grain="X")
    panels = {}
    side_len = R
    for k in range(6):
        phi = 60 * k + 30
        if k == 1:  # open back for the steps
            continue
        c = (ap * math.cos(math.radians(phi)), ap * math.sin(math.radians(phi)))
        grp = [p.panel(side_len - 0.04, top_z - floor_z - 0.06, 0.024, (0, 0, 0), C.OAK, style="raised", frame=0.07, recess=0.006,
                       tags=("panel", f"p{k}"))]
        rail = p.box((side_len + 0.07, 0.07, 0.045), (0, 0.005, (top_z - floor_z) / 2 + 0.0), C.OAK_DARK, bevel=0.006, grain="X")
        grp.append(rail)
        for q in grp:
            G.xform(q.obj, rot=(0, 0, phi - 270), loc=(c[0], c[1], floor_z + (top_z - floor_z) / 2 - 0.03))
        panels[k] = grp
    # newel posts at the hexagon corners
    for i, (x, y) in enumerate(hexpts):
        p.lathe([(0.03, 0.0), (0.03, top_z - 0.02), (0.038, top_z), (0.0, top_z + 0.04)], (x, y, 0.0), C.OAK_DARK, segs=8)
    desk = [p.box((0.56, 0.36, 0.025), (0, -ap + 0.1, top_z + 0.08), C.OAK, bevel=0.004, grain="X", tags=("desk",)),
            p.box((0.56, 0.03, 0.045), (0, -ap - 0.065, top_z + 0.095), C.OAK_DARK, bevel=0.004, grain="X", tags=("desk",)),
            p.box((0.5, 0.2, 0.08), (0, -ap + 0.17, top_z + 0.03), C.OAK_DARK, bevel=0.004, grain="X", tags=("desk",))]
    p.rotate(desk[:2], rot=(16, 0, 0), pivot=(0, -ap + 0.28, top_z + 0.08))
    fall = plate(p, 0.4, 0.36, (0, -ap - 0.045, top_z - 0.13), atlas("altar_frontal"), t=0.004, tags=("cloth", "desk"))
    desk.append(fall)
    # steps and handrail at the open back (+Y)
    for i, (y, z) in enumerate(((ap + 0.18, 0.17), (ap + 0.42, 0.0))):
        h = floor_z - 0.17 * i if i == 0 else 0.17 + 0.0
    steps = [p.box((0.62, 0.27, 0.34), (0, ap + 0.18, 0.17), C.OAK, bevel=0.005, grain="X"),
             p.box((0.62, 0.27, 0.17), (0, ap + 0.43, 0.085), C.OAK, bevel=0.005, grain="X")]
    p.box((0.64, 0.29, 0.025), (0, ap + 0.18, 0.345), C.OAK_DARK, bevel=0.004, grain="X")
    p.box((0.64, 0.29, 0.025), (0, ap + 0.43, 0.175), C.OAK_DARK, bevel=0.004, grain="X")
    p.tube([(0.33, ap + 0.55, 0.0), (0.33, ap + 0.55, 0.9), (0.33, ap + 0.05, top_z - 0.05)], 0.018, C.OAK_DARK, segs=6, fillet_r=0.1)
    del steps
    if p.worn and not p.destroyed:
        scatter_papers(p, (0, -ap + 0.07, top_z + 0.045), 4, 0.05, "sermon")
        candle(p, (0.22, -ap + 0.12, top_z + 0.02), 0.12, 0.02, burnt=True, key="stub")
    if p.destroyed:
        for k in (4, 5):
            for q in panels[k][:1]:
                lo, hi = p.bounds([q])
                c = (lo + hi) * 0.5
                G.xform(q.obj, rot=(0, 0, 0), loc=(0, 0, 0))
                G.splinter_cut(q.obj, (c.x, c.y, c.z - 0.05), (0.2, 0.1, 1.0), jag=0.05, seed=p.seed + k)
        rr = p.vrng("wreck")
        p.lay_on_floor(desk, rot=(160, 0, 0), at=(0.15, -ap - 0.6), yaw=rr.uniform(-30, 30))
        scatter_papers(p, (0.0, -ap - 0.7, 0.0), 10, 0.45, "floor", z_step=0.0015, floor=True)
    p.collider((0, 0.25, 0.75), (1.2, 1.55, 1.5))


def civic_hymn_board(p: Prop) -> None:
    """Wall hymn board (origin on the wall, bottom centre) 0.5 x 0.86: gothic-arched oak backboard with a
    beaded edge, a gilt HYMNS header and three black number cards on ledges, an empty fourth slot. Worn:
    the middle card slipped crooked, the last one gone."""
    W, H, t = 0.5, 0.86, 0.03
    arc = [(W / 2 * math.cos(a), 0.66 + 0.2 * math.sin(a)) for a in [math.pi * i / 10 for i in range(11)]]
    poly = [(-W / 2, 0.0), (W / 2, 0.0)] + [(x, z) for x, z in arc] + [(-W / 2, 0.0)]
    poly = poly[:-1]
    p.prism(poly, t, C.OAK, plane="XZ", offset=-t, bevel=0.004, grain="Z")
    for x in (-W / 2 + 0.02, W / 2 - 0.02):
        p.box((0.02, 0.012, 0.62), (x, -t - 0.006, 0.34), C.OAK_DARK, bevel=0.003, grain="Z")
    plate(p, 0.4, 0.05, (0, -t - 0.002, 0.7), atlas("hymn_header"), t=0.003)
    cards = {}
    for i, z in enumerate((0.55, 0.42, 0.29, 0.16)):
        p.box((0.42, 0.03, 0.012), (0, -t - 0.015, z - 0.035), C.OAK_DARK, bevel=0.003, grain="X")
        if i < 3:
            cards[i] = plate(p, 0.38, 0.06, (0, -t - 0.004, z), atlas("hymn_cards", i), t=0.004)
    if p.worn:
        G.xform(cards[1].obj, rot=(0, 9, 0), pivot=(-0.19, -t, 0.39))
        p.remove([cards[2]])
    p.collider((0, -0.02, H / 2), (W, 0.04, H))


def civic_candle_stand(p: Prop) -> None:
    """Votive candle stand 0.9 x 1.0: wrought-iron frame with scroll feet, three stepped trays of red glass
    votive cups, an iron cross on top and an offering box with a slot. Worn: most votives burnt out, wax
    run down the tray fronts, a few cups missing or cracked. Destroyed: knocked over on its back, cups
    scattered."""
    W, D = 0.88, 0.42
    parts = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            top = 0.98 if sy > 0 else 0.7
            parts.append(p.tube([(sx * (W / 2 - 0.02), sy * (D / 2 - 0.03), 0.04), (sx * (W / 2 - 0.03), sy * (D / 2 - 0.05), top)], 0.011,
                                C.IRON, segs=6))
            parts.append(p.tube([(sx * (W / 2 - 0.02), sy * (D / 2 - 0.03), 0.04), (sx * (W / 2 + 0.03), sy * (D / 2 - 0.02), 0.01),
                                 (sx * (W / 2 + 0.06), sy * (D / 2 - 0.03), 0.04), (sx * (W / 2 + 0.04), sy * (D / 2 - 0.05), 0.07)], 0.009,
                                C.IRON, segs=5, fillet_r=0.03))
    r = p.rng("cups")
    lit = p.vrng("lit")
    for k in range(3):
        z = 0.58 + k * 0.13
        y = -0.12 + k * 0.12
        parts.append(p.box((W - 0.04, 0.14, 0.018), (0, y, z), C.IRON, bevel=0.003))
        parts.append(p.box((W - 0.04, 0.008, 0.04), (0, y - 0.07, z + 0.012), C.IRON, bevel=0.002))
        for i in range(7):
            x = -0.33 + i * 0.11 + r.uniform(-0.01, 0.01)
            if p.worn and lit.random() < 0.15:
                continue
            cup = p.lathe([(0.0, 0.0), (0.025, 0.0), (0.03, 0.03), (0.032, 0.065), (0.0, 0.066)], (x, y, z + 0.009), C.VOTIVE, segs=6,
                          tags=("cup",))
            parts.append(cup)
            burnt = p.worn and lit.random() < 0.7
            parts.append(p.cyl(0.022, 0.012 if burnt else 0.035, (x, y, z + 0.015 + (0.006 if burnt else 0.0175)), C.CANDLE, segs=6))
            if not burnt:
                parts.append(flame(p, (x, y, z + 0.052), scale=0.8, key=f"votive{k}_{i}"))
        if p.worn:
            for j in range(3):
                x = lit.uniform(-0.38, 0.38)
                parts.append(p.box((0.012, 0.006, lit.uniform(0.04, 0.09)), (x, y - 0.075, z - 0.02), C.CANDLE, bevel=0.0))
    parts.append(p.box((W - 0.06, 0.32, 0.012), (0, 0.0, 0.3), C.IRON, bevel=0.002))
    for zz in (0.3, 0.98):
        parts.append(p.tube([(-W / 2 + 0.03, D / 2 - 0.05, zz), (W / 2 - 0.03, D / 2 - 0.05, zz)], 0.009, C.IRON, segs=5))
    parts.append(p.box((0.022, 0.022, 0.32), (0, D / 2 - 0.05, 1.12), C.IRON, bevel=0.003))
    parts.append(p.box((0.16, 0.022, 0.022), (0, D / 2 - 0.05, 1.18), C.IRON, bevel=0.003))
    box = [p.box((0.14, 0.1, 0.12), (W / 2 + 0.04, 0.02, 0.86), C.IRON, bevel=0.006),
           p.box((0.06, 0.004, 0.008), (W / 2 + 0.04, 0.02, 0.921), M.PL_BLACK, bevel=0.0)]
    parts += box
    if p.destroyed:
        whole = list(p.parts)
        p.rotate(whole, rot=(-88, 0, 0), pivot=(0, D / 2, 0))
        lo, hi = p.bounds(whole)
        p.move(whole, (0, 0, -lo.z))
        rr = p.vrng("spill")
        for i in range(6):
            p.lathe([(0.0, 0.0), (0.025, 0.0), (0.03, 0.03), (0.032, 0.065), (0.0, 0.066)], (0, 0, 0), C.VOTIVE, segs=6)
            q = p.parts[-1]
            G.xform(q.obj, rot=(90, 0, rr.uniform(0, 360)), loc=(rr.uniform(-0.6, 0.6), rr.uniform(-0.9, -0.4), 0.03))
        p.collider((0, -0.2, 0.25), (1.0, 1.1, 0.5))
    else:
        p.collider((0, 0.0, 0.6), (W + 0.12, D + 0.04, 1.2))


def civic_collection_box(p: Prop) -> None:
    """Alms box on a turned oak post (1.1 m): iron-strapped oak box with a coin slot, hasp and padlock,
    brass ALMS plate. Destroyed: the lid pried up on its hinges, the padlock and hasp torn off on the
    floor, a few coins spilled."""
    p.box((0.3, 0.3, 0.06), (0, 0, 0.03), C.OAK_DARK, bevel=0.008, grain="X")
    p.lathe([(0.065, 0.0), (0.06, 0.03), (0.04, 0.06), (0.038, 0.2), (0.05, 0.23), (0.034, 0.27), (0.03, 0.62), (0.045, 0.66),
             (0.05, 0.7), (0.0, 0.705)], (0, 0, 0.06), C.OAK, segs=10)
    bz = 0.765
    p.box((0.32, 0.24, 0.2), (0, 0, bz + 0.1), C.OAK, bevel=0.006, grain="X")
    for x in (-0.12, 0.12):
        p.box((0.025, 0.25, 0.205), (x, 0, bz + 0.1), C.IRON, bevel=0.002)
    p.box((0.325, 0.245, 0.02), (0, 0, bz + 0.01), C.IRON, bevel=0.002)
    lid = [p.box((0.33, 0.25, 0.035), (0, 0, bz + 0.218), C.OAK_DARK, bevel=0.006, grain="X", tags=("lid",)),
           p.box((0.09, 0.012, 0.008), (0, -0.02, bz + 0.237), M.PL_BLACK, bevel=0.0, tags=("lid",))]
    hasp = [p.box((0.03, 0.006, 0.07), (0, -0.124, bz + 0.18), C.IRON, bevel=0.0015),
            p.box((0.05, 0.02, 0.045), (0, -0.14, bz + 0.13), C.BRASS, bevel=0.004),
            p.tube([(-0.015, -0.14, bz + 0.152), (-0.015, -0.14, bz + 0.175), (0.015, -0.14, bz + 0.175), (0.015, -0.14, bz + 0.152)],
                   0.004, M.CHROME, segs=5, fillet_r=0.01, steps=2)]
    plate(p, 0.14, 0.035, (0, -0.121, bz + 0.07), atlas("alms"), t=0.002)
    if p.destroyed:
        p.rotate(lid, rot=(-105, 0, 0), pivot=(0, 0.125, bz + 0.2))
        rr = p.vrng("wreck")
        p.lay_on_floor(hasp, rot=(90, 0, 0), at=(0.25, -0.35), yaw=rr.uniform(0, 180))
        for i in range(5):
            p.cyl(0.011, 0.0018, (rr.uniform(-0.35, 0.35), rr.uniform(-0.45, -0.15), 0.001), M.BRASS, segs=8)
    p.collider((0, 0, 0.55), (0.34, 0.3, 1.1))


def civic_reed_organ(p: Prop) -> None:
    """Parlour reed (pump) organ 1.2 x 1.62 x 0.6: dark oak case, five-octave keyboard in yellowed ivory and
    ebony, a rail of stop knobs, music desk with an open hymnal, a fretwork crest with turned spindles,
    carpeted treadles and knee swells. Worn: keys missing and sunk, dust. Destroyed: crest snapped off onto
    the keys, keys torn out on the floor, the lower front kicked in, a treadle hanging."""
    W, D = 1.2, 0.55
    wood = C.OAK_DARK
    p.box((W, D - 0.05, 0.7), (0, 0.025, 0.35), wood, bevel=0.005, grain="Z")
    p.box((W + 0.03, D - 0.02, 0.06), (0, 0.025, 0.03), C.OAK, bevel=0.006, grain="X")
    low = p.panel(0.7, 0.4, 0.02, (0, -D / 2 + 0.015, 0.33), wood, style="raised", frame=0.06, tags=("panel",))
    for x in (-0.48, 0.48):
        p.lathe([(0.03, 0.0), (0.03, 0.05), (0.022, 0.1), (0.026, 0.55), (0.034, 0.6), (0.0, 0.61)], (x, -D / 2 + 0.04, 0.06), wood, segs=8)
    treadles = []
    for x in (-0.2, 0.2):
        grp = [p.box((0.26, 0.3, 0.025), (x, -D / 2 - 0.12, 0.09), wood, bevel=0.004, grain="Y", tags=("treadle",)),
               p.box((0.24, 0.27, 0.006), (x, -D / 2 - 0.12, 0.105), C.FELT_RED, bevel=0.0, tags=("treadle",))]
        p.rotate(grp, rot=(22, 0, 0), pivot=(x, -D / 2 + 0.02, 0.06))
        treadles.append(grp)
    # keyboard
    kz = 0.72
    p.box((1.0, 0.3, 0.04), (0, -0.12, kz), wood, bevel=0.004, grain="X")
    for x in (-0.53, 0.53):
        p.box((0.1, 0.32, 0.12), (x, -0.11, kz + 0.06), wood, bevel=0.006, grain="Y")
    keys = []
    rk = p.vrng("keys")
    n_white = 36
    kw_ = 0.0235
    x0 = -n_white * kw_ / 2
    for i in range(n_white):
        if p.worn and rk.random() < 0.05:
            continue
        sink = -0.008 if (p.worn and rk.random() < 0.08) else 0.0
        keys.append(p.box((kw_ - 0.002, 0.14, 0.02), (x0 + (i + 0.5) * kw_, -0.2, kz + 0.03 + sink), C.IVORY, bevel=0.0, tags=("key",)))
    pattern = [1, 1, 0, 1, 1, 1, 0]
    for i in range(n_white - 1):
        if pattern[i % 7]:
            keys.append(p.box((0.012, 0.085, 0.018), (x0 + (i + 1) * kw_, -0.17, kz + 0.048), C.EBONY, bevel=0.0, tags=("key",)))
    p.box((1.0, 0.02, 0.04), (0, -0.28, kz + 0.01), wood, bevel=0.003, grain="X")
    # stop rail and knobs
    p.box((0.98, 0.07, 0.08), (0, -0.02, kz + 0.11), wood, bevel=0.004, grain="X")
    for i in range(10):
        x = -0.4 + i * 0.089
        p.lathe([(0.009, 0.0), (0.009, 0.02), (0.016, 0.025), (0.016, 0.035), (0.0, 0.037)], (x, -0.055, kz + 0.11), wood, segs=8, axis="-Y")
        p.cyl(0.0125, 0.003, (x, -0.094, kz + 0.11), C.IVORY, axis="Y", segs=8)
    # upper case
    upper = [p.box((W, 0.1, 0.48), (0, 0.17, kz + 0.39), wood, bevel=0.005, grain="Z", tags=("upper",))]
    desk = [p.box((0.6, 0.02, 0.24), (0, 0.08, kz + 0.33), C.OAK, bevel=0.003, grain="X", tags=("desk",)),
            p.box((0.62, 0.05, 0.015), (0, 0.06, kz + 0.21), C.OAK, bevel=0.003, grain="X", tags=("desk",))]
    p.rotate(desk, rot=(-12, 0, 0), pivot=(0, 0.1, kz + 0.2))
    if not p.destroyed:
        hymnal(p, (0, 0.04, kz + 0.33), rot=(-90 + 12, 0, 0), open_deg=170, key="organ_hymnal")
    crest = [p.prism([(-W / 2, 0.0), (W / 2, 0.0), (W / 2, 0.12), (0.3, 0.16), (0.12, 0.24), (0.0, 0.26), (-0.12, 0.24), (-0.3, 0.16),
                      (-W / 2, 0.12)], 0.04, wood, plane="XZ", offset=0.14, bevel=0.004, grain="X", tags=("crest",))]
    G.xform(crest[0].obj, loc=(0, 0, kz + 0.63))
    crest.append(p.panel(0.5, 0.14, 0.012, (0, 0.13, kz + 0.72), C.OAK, style="groove", frame=0.03, tags=("crest",)))
    for x in (-0.55, -0.3, 0.3, 0.55):
        crest.append(p.lathe([(0.016, 0.0), (0.012, 0.03), (0.02, 0.09), (0.012, 0.15), (0.018, 0.17), (0.0, 0.2)], (x, 0.12, kz + 0.63), wood,
                             segs=8, tags=("crest",)))
    if p.destroyed:
        rr = p.vrng("wreck")
        p.lay_on_floor(crest, rot=(-80, 0, 15), at=(0.1, -0.18), z=kz + 0.04)
        for q in keys[:8]:
            p.lay_on_floor([q], rot=(rr.uniform(-20, 20), 0, 0), at=(rr.uniform(-0.6, 0.6), rr.uniform(-0.75, -0.45)), yaw=rr.uniform(0, 180))
        p.remove([low])
        a, b = F.split_panel(p, 0.7, 0.4, 0.02, (0, -D / 2 + 0.015, 0.33), wood, (-0.35, 0.05), (0.35, -0.1), key="front")
        G.xform(b.obj, rot=(20, 0, 0), pivot=(0, -D / 2, 0.13))
        p.rotate(treadles[1], rot=(-30, 0, 8), pivot=(0.2, -D / 2, 0.06))
    p.collider((0, 0.0, 0.8), (W + 0.06, D + 0.1, 1.6))


def civic_baptismal_font(p: Prop) -> None:
    """Octagonal white-marble baptismal font on a moulded shaft (1.0 m) with a conical oak lid and brass
    cross finial. Worn: the lid pushed askew, a green water line in the basin. Destroyed: the lid thrown
    down, a chunk broken out of the rim."""
    oct8 = [(0.3 * math.cos(math.radians(22.5 + 45 * i)), 0.3 * math.sin(math.radians(22.5 + 45 * i))) for i in range(8)]
    p.prism(oct8, 0.1, C.MARBLE, plane="XY", offset=0.0, bevel=0.01)
    p.lathe([(0.2, 0.0), (0.2, 0.03), (0.13, 0.08), (0.12, 0.55), (0.16, 0.6), (0.16, 0.63), (0.0, 0.64)], (0, 0, 0.1), C.MARBLE, segs=8)
    bowl = p.lathe([(0.0, 0.0), (0.16, 0.0), (0.27, 0.12), (0.33, 0.2), (0.34, 0.27), (0.3, 0.28), (0.26, 0.2), (0.15, 0.12),
                    (0.0, 0.11)], (0, 0, 0.72), C.MARBLE, segs=8, cap_bottom=False, cap_top=False)
    p.cyl(0.25, 0.004, (0, 0, 0.72 + 0.17), M.MOLD if p.worn else C.GLASS_CLEAR, segs=8)
    lid = [p.lathe([(0.0, 0.0), (0.33, 0.0), (0.33, 0.03), (0.28, 0.05), (0.06, 0.26), (0.04, 0.3), (0.0, 0.31)], (0, 0, 0.99), C.OAK,
                   segs=8, tags=("lid",))]
    lid.append(p.box((0.016, 0.016, 0.14), (0, 0, 0.99 + 0.36), C.BRASS, bevel=0.002, tags=("lid",)))
    lid.append(p.box((0.08, 0.016, 0.016), (0, 0, 0.99 + 0.39), C.BRASS, bevel=0.002, tags=("lid",)))
    if p.cond == "worn":
        p.rotate(lid, rot=(0, 0, 14), pivot=(0, 0, 0))
        p.move(lid, (0.09, -0.05, 0.0))
        p.rotate(lid, rot=(0, 7, 0), pivot=(0.4, 0, 0.99))
    if p.destroyed:
        p.lay_on_floor(lid, rot=(70, 0, 0), at=(0.55, -0.45), yaw=30)
        G.splinter_cut(bowl.obj, (0.24, -0.2, 0.95), (-0.6, 0.6, -0.4), jag=0.03, seed=p.seed)
    p.collider((0, 0, 0.55), (0.68, 0.68, 1.1))


def _bell(p: Prop, center, key: str = "bell") -> list:
    """Bronze church bell, mouth 0.76 m, hanging mouth-down from center (crown top)."""
    x, y, z = center
    prof = [(0.0, 0.56), (0.19, 0.55), (0.215, 0.45), (0.225, 0.33), (0.25, 0.22), (0.3, 0.13), (0.34, 0.05), (0.352, 0.0),
            (0.38, 0.0), (0.385, 0.03), (0.37, 0.075), (0.33, 0.14), (0.285, 0.22), (0.258, 0.32), (0.246, 0.43), (0.25, 0.52),
            (0.225, 0.59), (0.13, 0.625), (0.0, 0.632)]
    h = 0.632
    out = [p.lathe([(r, zz - h) for r, zz in prof], (x, y, z), C.BRONZE, segs=20, cap_bottom=False, cap_top=False, tags=(key,))]
    out.append(p.lathe([(0.262, -h + 0.235), (0.268, -h + 0.25), (0.268, -h + 0.27), (0.258, -h + 0.285)], (x, y, z), C.BRONZE, segs=20,
                       cap_bottom=False, cap_top=False, tags=(key,)))
    for i in range(3):
        a = math.radians(60 * i)
        out.append(p.tube([(x + math.cos(a) * 0.08, y + math.sin(a) * 0.08, z - 0.005), (x + math.cos(a) * 0.1, y + math.sin(a) * 0.1, z + 0.05),
                           (x - math.cos(a) * 0.1, y - math.sin(a) * 0.1, z + 0.05), (x - math.cos(a) * 0.08, y - math.sin(a) * 0.08, z - 0.005)],
                          0.018, C.BRONZE, segs=6, fillet_r=0.03, steps=2, tags=(key,)))
    out.append(p.tube([(x, y, z - 0.08), (x, y, z - h + 0.12)], 0.013, C.IRON, segs=6, tags=(key,)))
    out.append(sphere(p, 0.055, (x, y, z - h + 0.09), C.IRON, segs=8, rings=5, tags=(key,)))
    return out


def civic_church_bell(p: Prop) -> None:
    """Tower bell (0.76 m bronze, verdigris) hung from an oak headstock with iron straps and gudgeons in an
    oak A-frame, with a 1.0 m bell wheel and the rope with its striped sally. Worn: the rope snapped and
    lying coiled under the wheel (it was rung until it broke). Destroyed: the frame collapsed, the bell
    down on its side, cracked, the wheel broken."""
    wood = C.OAK_DARK
    hz = 1.32
    frame = []
    for sx in (-1, 1):
        x = sx * 0.66
        frame.append(bar(p, (x, -0.45, 0.0), (x, 0.0, hz - 0.06), 0.11, 0.11, wood, tags=("frame",)))
        frame.append(bar(p, (x, 0.45, 0.0), (x, 0.0, hz - 0.06), 0.11, 0.11, wood, tags=("frame",)))
        frame.append(bar(p, (x, -0.24, 0.62), (x, 0.24, 0.62), 0.1, 0.09, wood, tags=("frame",)))
        frame.append(p.box((0.14, 0.2, 0.1), (x, 0.0, hz - 0.03), wood, bevel=0.006, grain="Y", tags=("frame",)))
        frame.append(p.box((0.13, 1.1, 0.12), (x, 0.0, 0.06), wood, bevel=0.006, grain="Y", tags=("frame",)))
        frame.append(p.box((0.1, 0.12, 0.05), (x, 0.0, hz + 0.045), C.IRON, bevel=0.004, tags=("frame",)))
    for sy in (-1, 1):
        frame.append(p.box((1.45, 0.12, 0.12), (0, sy * 0.48, 0.06), wood, bevel=0.006, grain="X", tags=("frame",)))
    head = [p.box((1.12, 0.17, 0.18), (0, 0, hz), wood, bevel=0.008, grain="X", tags=("head",))]
    for sx in (-1, 1):
        head.append(p.cyl(0.03, 0.12, (sx * 0.6, 0, hz), C.IRON, axis="X", segs=8, tags=("head",)))
    for x in (-0.12, 0.12):
        head.append(p.box((0.04, 0.2, 0.2), (x, 0, hz - 0.02), C.IRON, bevel=0.002, tags=("head",)))
    bell = _bell(p, (0, 0, hz - 0.09))
    wheel = []
    wx = 0.5
    rim = [(wx, 0.5 * math.cos(math.radians(a)), hz + 0.5 * math.sin(math.radians(a))) for a in range(0, 360, 15)]
    wheel.append(p.tube(rim, 0.022, wood, segs=6, closed=True, tags=("wheel",)))
    for a in range(0, 360, 60):
        wheel.append(p.tube([(wx, 0.04 * math.cos(math.radians(a)), hz + 0.04 * math.sin(math.radians(a))),
                             (wx, 0.48 * math.cos(math.radians(a)), hz + 0.48 * math.sin(math.radians(a)))], 0.014, wood, segs=5, tags=("wheel",)))
    rope = []
    sally = []
    if p.cond == "clean":
        rope.append(p.tube([(wx, -0.5, hz), (wx, -0.52, 0.9), (wx + 0.02, -0.5, 0.05)], 0.011, C.CANVAS_KHAKI, segs=5, fillet_r=0.2))
        sally.append(p.cyl(0.03, 0.45, (wx + 0.012, -0.51, 0.95), C.FLANNEL, segs=8))
    elif p.cond == "worn":
        rope.append(p.tube([(wx, -0.5, hz), (wx, -0.51, 1.05), (wx + 0.03, -0.5, 0.98)], 0.011, C.CANVAS_KHAKI, segs=5, fillet_r=0.05))
        coil = [(wx - 0.2 + 0.18 * math.cos(t * 1.9), -0.75 + 0.14 * math.sin(t * 1.9), 0.012 + 0.008 * t) for t in [i * 0.35 for i in range(24)]]
        rope.append(p.tube(coil, 0.011, C.CANVAS_KHAKI, segs=5))
        s = p.cyl(0.03, 0.42, (0, 0, 0), C.FLANNEL, segs=8)
        G.xform(s.obj, rot=(0, 90, 20), loc=(wx - 0.05, -0.55, 0.03))
    if p.destroyed:
        rr = p.vrng("wreck")
        # frame racked over, headstock dropped, bell on its side and cracked
        p.rotate(frame, rot=(0, 0, 0), pivot=(0, 0, 0))
        for q in frame:
            if q.obj.dimensions.z > 0.9:
                G.xform(q.obj, rot=(rr.uniform(20, 40), 0, rr.uniform(-10, 10)), pivot=(q.obj.location.x, 0, 0))
        p.lay_on_floor(head, rot=(0, 0, 25), at=(0.1, 0.35), yaw=0)
        p.lay_on_floor(bell, rot=(0, 100, 0), at=(-0.3, -0.25), yaw=40)
        G.splinter_cut(bell[0].obj, (-0.3, -0.2, 0.3), (0.3, -0.2, 1.0), jag=0.02, seed=p.seed)
        p.lay_on_floor(wheel, rot=(0, 80, 0), at=(0.55, 0.2), yaw=-20)
        p.collider((0, 0, 0.45), (1.5, 1.1, 0.9))
    else:
        p.collider((0, 0, 0.95), (1.5, 1.05, 1.9))


def _spire_uvs(obj, scale: float = 1.0) -> None:
    """Per-face slope-aligned UVs: U along the face's horizontal, V up its slope (shingle courses)."""
    me = obj.data
    uvl = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
    up = Vector((0, 0, 1))
    for poly in me.polygons:
        n = poly.normal
        t = up.cross(n)
        if t.length < 1e-4:
            t = Vector((1, 0, 0))
        t.normalize()
        b = n.cross(t).normalized()
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uvl.data[li].uv = (co.dot(t) * scale, co.dot(b) * scale)


def civic_steeple(p: Prop) -> None:
    """Broach steeple that sits astride the church ridge (origin at the bottom centre of its base, ~1.3 m of
    which is buried in the roof): white clapboard belfry stage 2.4 m square with corner boards and arched
    louvred openings on all four faces, a moulded cornice, an octagonal cedar-shingled spire with
    triangular broaches rising to 9.3 m, a ball and an iron cross. Worn: louvres missing, the cross
    leaning, moss on the shingles."""
    S = 2.4
    hb = 3.5
    wood = C.WHITE_WOOD
    p.box((S - 0.06, S - 0.06, hb), (0, 0, hb / 2), wood, bevel=0.004, grain="Z")
    r = p.vrng("louvres")
    for k in range(4):
        rot = 90 * k
        grp = []
        # clapboards on this face
        for i in range(15):
            z = 0.1 + i * 0.22
            grp.append(p.box((S - 0.14, 0.03, 0.23), (0, -S / 2 - 0.005, z + 0.11), wood, bevel=0.002, grain="X"))
            G.xform(grp[-1].obj, rot=(-6, 0, 0), pivot=(0, -S / 2, z))
        # arched opening frame + louvres
        ow, oz0, oz1 = 1.0, 1.95, 3.05
        grp.append(p.box((ow + 0.02, 0.06, oz1 - oz0), (0, -S / 2 - 0.02, (oz0 + oz1) / 2), C.EBONY, bevel=0.0))
        for x in (-ow / 2 - 0.06, ow / 2 + 0.06):
            grp.append(p.box((0.1, 0.07, oz1 - oz0 + 0.2), (x, -S / 2 - 0.045, (oz0 + oz1) / 2 + 0.05), wood, bevel=0.004, grain="Z"))
        arch = [((ow / 2 + 0.11) * math.cos(a), oz1 + 0.18 * math.sin(a)) for a in [math.pi * i / 8 for i in range(9)]]
        inner = [((ow / 2) * math.cos(a), oz1 + 0.1 * math.sin(a)) for a in [math.pi * (8 - i) / 8 for i in range(9)]]
        grp.append(p.prism(arch + inner, 0.07, wood, plane="XZ", offset=-S / 2 - 0.08, bevel=0.003))
        grp.append(p.box((ow + 0.22, 0.12, 0.06), (0, -S / 2 - 0.05, oz0 - 0.03), wood, bevel=0.004, grain="X"))
        for j in range(10):
            if p.worn and r.random() < 0.2:
                continue
            sl = p.box((ow, 0.14, 0.012), (0, -S / 2 - 0.03, oz0 + 0.08 + j * 0.105), wood, bevel=0.0, grain="X")
            G.xform(sl.obj, rot=(-38, 0, 0), pivot=(0, -S / 2 - 0.03, oz0 + 0.08 + j * 0.105))
            grp.append(sl)
        for q in grp:
            G.xform(q.obj, rot=(0, 0, rot))
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.box((0.16, 0.16, hb), (sx * (S / 2 - 0.02), sy * (S / 2 - 0.02), hb / 2), wood, bevel=0.004, grain="Z")
    p.box((S + 0.22, S + 0.22, 0.14), (0, 0, hb + 0.07), wood, bevel=0.01, grain="X")
    p.box((S + 0.34, S + 0.34, 0.07), (0, 0, hb + 0.17), wood, bevel=0.012, grain="X")
    # octagonal spire with broaches
    z0, z1 = hb + 0.2, 9.6
    Rs = S / 2 * 0.98
    spire = p.lathe([(Rs, 0.0), (0.06, z1 - z0), (0.0, z1 - z0 + 0.02)], (0, 0, z0), C.SHINGLE, segs=8, uv="keep", cap_bottom=True)
    G.xform(spire.obj, rot=(0, 0, 22.5))
    _spire_uvs(spire.obj, 0.85)
    for k in range(4):
        a = math.radians(45 + 90 * k)
        cx, cy = math.cos(a) * S / 2 * 1.0, math.sin(a) * S / 2 * 1.0
        tip = (math.cos(a) * Rs * 0.38, math.sin(a) * Rs * 0.38, z0 + 1.6)
        e1 = (math.cos(a - math.radians(45)) * S / 2 * 0.98, math.sin(a - math.radians(45)) * S / 2 * 0.98, z0)
        e2 = (math.cos(a + math.radians(45)) * S / 2 * 0.98, math.sin(a + math.radians(45)) * S / 2 * 0.98, z0)
        bm = bmesh.new()
        vs = [bm.verts.new(v) for v in ((cx, cy, z0), e1, tip, e2)]
        bm.faces.new((vs[0], vs[1], vs[2]))
        bm.faces.new((vs[0], vs[2], vs[3]))
        bm.faces.new((vs[1], vs[0], vs[3]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        obj = common.mesh_from_bmesh(p._name("broach"), bm)
        _spire_uvs(obj, 0.85)
        p.add(obj, C.SHINGLE, uv="keep", edge_deg=40)
    top = z1 + 0.02
    finial = [sphere(p, 0.09, (0, 0, top + 0.08), C.BRASS, segs=10, rings=6),
              p.box((0.05, 0.05, 1.0), (0, 0, top + 0.6), C.IRON, bevel=0.006),
              p.box((0.5, 0.05, 0.05), (0, 0, top + 0.82), C.IRON, bevel=0.006)]
    if p.worn:
        p.rotate(finial, rot=(0, 8, 0), pivot=(0, 0, top))
    p.collider((0, 0, 3.0), (S + 0.3, S + 0.3, 6.0))


def civic_church_sign(p: Prop) -> None:
    """St. Ansel's notice board (1.6 x 1.75): white-painted posts and frame with a little shingled gable cap,
    a glazed black letter board (service times, the food pantry, 'AL  ARE W LCOME' with letters gone).
    Destroyed: a post snapped, the board hanging askew, the glass broken out."""
    wood = C.WHITE_WOOD
    posts = []
    for sx in (-1, 1):
        posts.append(p.box((0.1, 0.1, 1.72), (sx * 0.74, 0, 0.86), wood, bevel=0.006, grain="Z"))
        p.box((0.16, 0.16, 0.08), (sx * 0.74, 0, 0.04), C.GRANITE, bevel=0.01)
    board = [p.box((1.42, 0.08, 0.8), (0, 0, 1.12), wood, bevel=0.006, grain="X", tags=("board",))]
    board.append(plate(p, 1.24, 0.62, (0, -0.042, 1.12), atlas("church_sign"), t=0.004, tags=("board",)))
    board.append(p.box((1.42, 0.12, 0.04), (0, 0, 0.7), wood, bevel=0.006, grain="X", tags=("board",)))
    if not p.destroyed:
        board.append(p.box((1.24, 0.004, 0.62), (0, -0.052, 1.12), M.GLASS, bevel=0.0, tags=("board",)))
    else:
        board += F.shatter_pane(p, 1.24, 0.62, (0, -0.052, 1.12), M.GLASS, t=0.004, key="sign", spokes=8, rings=2, missing_inner=0.9,
                                missing_outer=0.4)
    cap = []
    for sx in (-1, 1):
        q = p.box((0.85, 0.24, 0.025), (sx * 0.4, 0, 1.6), C.SHINGLE, bevel=0.003, grain="X", tags=("cap",))
        G.xform(q.obj, rot=(0, sx * 24, 0), pivot=(0, 0, 1.6))
        cap.append(q)
    cap.append(p.box((1.5, 0.1, 0.06), (0, 0, 1.55), wood, bevel=0.005, grain="X", tags=("cap",)))
    if p.destroyed:
        G.splinter_cut(posts[1].obj, (0.74, 0, 0.55), (0, 0, -1), jag=0.03, seed=p.seed)
        p.rotate(board + cap, rot=(0, 18, 0), pivot=(-0.74, 0, 1.5))
    p.collider((0, 0, 0.88), (1.6, 0.2, 1.75))


def civic_iron_fence(p: Prop) -> None:
    """Graveyard railing section 2.0 m on a granite kerb: square posts with urn finials at both ends, flat
    top and bottom rails, 13 round pickets with spear heads, C-scrolls in alternate bays. Worn: rust,
    a picket bent, a spear gone, leaning a little. Destroyed: pushed over, pickets bent and snapped."""
    L = 2.0
    kerb = p.box((L, 0.22, 0.18), (0, 0, 0.09), C.GRANITE, bevel=0.012, grain="X")
    kerb.var = 0.7
    iron = []
    for sx in (-1, 1):
        x = sx * (L / 2 - 0.035)
        iron.append(p.box((0.05, 0.05, 1.18), (x, 0, 0.18 + 0.59), C.IRON, bevel=0.004))
        iron.append(p.lathe([(0.03, 0.0), (0.035, 0.02), (0.028, 0.045), (0.04, 0.08), (0.03, 0.11), (0.012, 0.13), (0.02, 0.15),
                             (0.0, 0.17)], (x, 0, 1.36), C.IRON, segs=8))
    for z in (0.3, 1.13):
        iron.append(p.box((L - 0.1, 0.012, 0.04), (0, 0, z), C.IRON, bevel=0.002))
    r = p.vrng("pickets")
    n = 13
    pickets = []
    for i in range(n):
        x = -L / 2 + 0.12 + i * (L - 0.24) / (n - 1)
        grp = [p.cyl(0.009, 1.06, (x, 0, 0.18 + 0.53), C.IRON, segs=6)]
        if not (p.worn and r.random() < 0.08):
            grp.append(p.lathe([(0.012, 0.0), (0.016, 0.012), (0.009, 0.02), (0.022, 0.035), (0.0, 0.1)], (x, 0, 1.24), C.IRON, segs=6))
        if p.worn and r.random() < 0.1:
            p.rotate(grp, rot=(r.uniform(-14, 14), 0, 0), pivot=(x, 0, 0.3))
        pickets.append(grp)
        iron += grp
    for i in range(0, n - 1, 2):
        xa = -L / 2 + 0.12 + i * (L - 0.24) / (n - 1)
        xb = -L / 2 + 0.12 + (i + 1) * (L - 0.24) / (n - 1)
        xm = (xa + xb) / 2
        for sz in (-1, 1):
            pts = [(xa + 0.012, 0, 1.13 - 0.02), (xm - 0.02, 0, 1.13 - 0.005 + sz * 0.0), (xm, 0, 1.0 + 0.04), (xm + 0.02, 0, 1.13 - 0.005),
                   (xb - 0.012, 0, 1.11)]
            if sz > 0:
                pts = [(xa + 0.012, 0, 0.32), (xm, 0, 0.43), (xb - 0.012, 0, 0.32)]
            iron.append(p.tube(pts, 0.005, C.IRON, segs=4, fillet_r=0.03, steps=2))
    if p.worn and not p.destroyed:
        p.rotate(iron, rot=(3.5, 0, 0), pivot=(0, 0, 0.18))
    if p.destroyed:
        rr = p.vrng("wreck")
        for grp in pickets[3:6]:
            G.splinter_cut(grp[0].obj, (0, 0, 0.6 + rr.uniform(0, 0.3)), (0, 0, 1), jag=0.01, seed=p.seed + len(grp))
        p.rotate(iron, rot=(58, 0, 4), pivot=(0, 0, 0.18))
        p.collider((0, -0.4, 0.4), (L, 1.0, 0.8))
    else:
        p.collider((0, 0, 0.75), (L, 0.24, 1.5))


def _stone_face(p: Prop, poly2d, t: float, mat: str, face_mat: str, uvrect, center=(0, 0, 0), bevel: float = 0.006, key: str = "slab") -> core.Part:
    """Stone slab extruded from a 2D outline (XZ), its front (-Y) face carrying the carved atlas cell."""
    part = p.prism(poly2d, t, mat, plane="XZ", offset=-t / 2, bevel=bevel, uv="keep", tags=(key,), edge_deg=8.0)
    obj = part.obj
    front = lambda poly: poly.normal.y < -0.95 and abs(poly.center.y + t / 2) < 0.002
    box_uvs(obj, 2.0, skip=front, offset=(p.rng(key).random(), p.rng(key + "v").random()))
    p.set_mat(part, face_mat, front)
    me = obj.data
    uvl = me.uv_layers.get("UVMap")
    faces = [poly for poly in me.polygons if front(poly)]
    xs = [x for x, _ in poly2d]
    zs = [z for _, z in poly2d]
    u0, v0, u1, v1 = uvrect
    for poly in faces:
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            tu = (co.x - min(xs)) / max(1e-6, max(xs) - min(xs))
            tv = (co.z - min(zs)) / max(1e-6, max(zs) - min(zs))
            uvl.data[li].uv = (u0 + tu * (u1 - u0), v0 + tv * (v1 - v0))
    G.xform(obj, loc=center)
    return part


def _headstone_outline(shape: str, w: float, h: float) -> list:
    if shape == "round":
        arc = [(w / 2 * math.cos(a), h - w * 0.28 + w * 0.28 * math.sin(a)) for a in [math.pi * i / 12 for i in range(13)]]
        return [(-w / 2, 0.0), (w / 2, 0.0)] + arc[1:-1] + [(-w / 2, h - w * 0.28)]
    if shape == "gothic":
        out = [(-w / 2, 0.0), (w / 2, 0.0), (w / 2, h * 0.7)]
        cx = -w * 0.3
        for i in range(1, 7):
            a = math.radians(i * 70 / 6)
            out.append((cx + w * 0.8 * math.cos(a), h * 0.7 + w * 0.8 * math.sin(a) * 0.62))
        out.append((0.0, h))
        cx = w * 0.3
        for i in range(6, 0, -1):
            a = math.radians(i * 70 / 6)
            out.append((cx - w * 0.8 * math.cos(a), h * 0.7 + w * 0.8 * math.sin(a) * 0.62))
        out.append((-w / 2, h * 0.7))
        return out
    if shape == "tablet":
        out = [(-w / 2, 0.0), (w / 2, 0.0), (w / 2, h - 0.12)]
        for i in range(1, 5):
            a = math.radians(90 * i / 4)
            out.append((w / 2 - 0.08 + 0.08 * math.cos(a), h - 0.12 + 0.06 * math.sin(a)))
        for i in range(1, 8):
            a = math.pi * i / 8
            out.append((0.26 * w * math.cos(a) * 1.4 if abs(math.cos(a)) > 0 else 0.0, h - 0.06 + 0.06 * math.sin(a)))
        for i in range(0, 4):
            a = math.radians(90 + 90 * i / 4)
            out.append((-w / 2 + 0.08 + 0.08 * math.cos(a), h - 0.12 + 0.06 * math.sin(a)))
        out.append((-w / 2, h - 0.12))
        return out
    return [(-w / 2, 0.0), (w / 2, 0.0), (w / 2, h), (-w / 2, h)]


def headstone(p: Prop) -> None:
    """Graveyard headstones (params: shape round | gothic | tablet | cross | small, cell = civic_engrave face,
    stone granite | marble). Granite uprights stand on a bevelled base; marble tablets go straight into the
    turf; the cross stands on a two-step base with the inscription on its die. Worn: leaning with the
    ground's heave. Destroyed: snapped off at the base and lying face-up in front of the stub."""
    shape = p.params.get("shape", "round")
    cell = int(p.params.get("cell", 0))
    marble = p.params.get("stone", "granite") == "marble"
    mat = C.MARBLE if marble else C.GRANITE
    fmat = C.ENG_MARBLE if marble else C.ENG_GRANITE
    r = p.rng("stone")
    var = r.uniform(0.3, 1.0)
    base = []
    if shape == "tablet":
        w, h, t = 0.5, 0.92, 0.06
        slab = _stone_face(p, _headstone_outline("tablet", w, h), t, mat, fmat, engrave(cell, 30, 470), center=(0, 0, -0.05))
        slab.var = var
        body = [slab]
    elif shape == "cross":
        base.append(p.box((0.7, 0.42, 0.14), (0, 0, 0.07), mat, bevel=0.012))
        base.append(p.box((0.52, 0.3, 0.12), (0, 0, 0.2), mat, bevel=0.01))
        die = _stone_face(p, [(-0.2, 0.0), (0.2, 0.0), (0.2, 0.32), (-0.2, 0.32)], 0.22, mat, fmat, engrave(cell, 90, 360),
                          center=(0, 0, 0.26), bevel=0.008)
        base.append(die)
        body = [p.box((0.12, 0.12, 0.82), (0, 0, 0.58 + 0.41), mat, bevel=0.012),
                p.box((0.48, 0.108, 0.11), (0, 0, 1.18), mat, bevel=0.012)]
        ring = [(0.17 * math.cos(math.radians(a)), 0.0, 1.18 + 0.17 * math.sin(math.radians(a))) for a in range(0, 360, 30)]
        body.append(p.tube(ring, 0.025, mat, segs=6, closed=True))
        for q in body + base:
            q.var = var
    else:
        small = shape == "small"
        w, h, t = (0.4, 0.42, 0.1) if small else (0.62, 0.86, 0.12)
        bw = w + 0.16
        base.append(p.box((bw, t + 0.2, 0.15), (0, 0, 0.075), mat, bevel=0.012))
        outline = _headstone_outline("round" if shape in ("round", "small") else ("gothic" if shape == "gothic" else "square"), w, h)
        slab = _stone_face(p, outline, t, mat, fmat, engrave(cell, 20, 500) if not small else engrave(cell, 60, 400),
                           center=(0, 0, 0.15))
        body = [slab]
        if shape == "gothic":
            body.append(p.box((w + 0.04, t + 0.03, 0.05), (0, 0, 0.15 + 0.025), mat, bevel=0.008))
        for q in body + base:
            q.var = var
    if p.cond == "worn":
        whole = list(p.parts)
        rr = p.vrng("lean")
        p.rotate(whole, rot=(rr.uniform(-9, 9), rr.uniform(-5, 5), rr.uniform(-6, 6)), pivot=(0, 0, 0))
        lo, hi = p.bounds(whole)
        p.move(whole, (0, 0, -lo.z - 0.04))
    if p.destroyed:
        rr = p.vrng("wreck")
        if base:
            stub = []
            for q in body:
                me2 = q.obj.data.copy()
                o2 = common.new_object(p._name("stub"), me2)
                stub.append(p.add(o2, q.mat, uv="keep", edge_deg=q.edge_deg))
                G.splinter_cut(o2, (0, 0, (0.27 if shape != "cross" else 0.7)), (0, 0, 1), jag=0.03, seed=p.seed + 1)
            for q in body:
                G.splinter_cut(q.obj, (0, 0, (0.27 if shape != "cross" else 0.7)), (0, 0, -1), jag=0.03, seed=p.seed + 2)
            p.lay_on_floor(body, rot=(-90, 0, 0), at=(rr.uniform(-0.1, 0.1), -0.75), yaw=rr.uniform(-15, 15))
        else:
            p.rotate(body, rot=(-84, 0, rr.uniform(-10, 10)), pivot=(0, -0.05, 0))
            lo, hi = p.bounds(body)
            p.move(body, (0, 0, -lo.z))
    lo, hi = p.bounds()
    c = (lo + hi) * 0.5
    p.collider((c.x, c.y, (hi.z + max(0.0, lo.z)) / 2), (hi.x - lo.x, hi.y - lo.y, hi.z - max(0.0, lo.z)))


def civic_grave_mound(p: Prop) -> None:
    """A fresh grave dug by the shelter: a long mound of dug earth with clods and stones, a cross nailed
    from two boards, a jar of wildflowers. Worn: settled and sunken, the cross leaning, the flowers dead."""
    sunk = 0.07 if p.worn else 0.0
    mound = p.rbox((0.92, 2.0, 0.38), (0, 0.0, 0.01 - sunk), C.SOIL, radius=0.12, inner=(5, 10, 1), bulge=(0.02, 0.02, 0.04),
                   sag=0.05 if p.worn else 0.0, sag_r=0.6, wrinkle=0.045, wrinkle_scale=3.2, seed=p.seed, edge_deg=50,
                   squash=lambda v: Vector((v.x * (1.0 + 0.06 * math.sin(v.y * 3.1)), v.y, v.z)))
    mound.var = 0.6
    r = p.rng("clods")
    for i in range(8):
        a = r.uniform(0, math.pi * 2)
        p.rbox((r.uniform(0.06, 0.14), r.uniform(0.05, 0.12), r.uniform(0.04, 0.07)),
               (math.cos(a) * r.uniform(0.35, 0.5), math.sin(a) * r.uniform(0.6, 1.0), 0.02), C.SOIL, radius=0.025, inner=(1, 1, 1),
               wrinkle=0.01, seed=i)
    for i in range(4):
        sphere(p, r.uniform(0.03, 0.06), (r.uniform(-0.4, 0.4), r.uniform(-0.95, 0.95), 0.0), C.GRANITE, segs=6, rings=4)
    cross = [p.box((0.07, 0.025, 1.0), (0, 0.98, 0.42), C.FRESH_WOOD, bevel=0.003, grain="Z"),
             p.box((0.42, 0.026, 0.07), (0, 0.97, 0.72), C.FRESH_WOOD, bevel=0.003, grain="X")]
    for x in (-0.02, 0.02):
        cross.append(p.cyl(0.004, 0.006, (x, 0.955, 0.72), M.CAST_IRON, axis="Y", segs=4))
    if p.worn:
        p.rotate(cross, rot=(-9, 6, 0), pivot=(0, 0.98, 0))
    jar = p.lathe([(0.0, 0.0), (0.045, 0.0), (0.048, 0.1), (0.035, 0.13), (0.036, 0.15), (0.0, 0.151)], (0.18, 0.82, 0.1 - sunk),
                  C.GLASS_CLEAR, segs=8)
    del jar
    for i in range(7):
        a = i * 0.9
        tip = (0.18 + 0.08 * math.cos(a), 0.82 + 0.08 * math.sin(a), 0.4 - sunk - (0.12 if p.worn else 0.0))
        p.tube([(0.18, 0.82, 0.12 - sunk), (0.18 + 0.03 * math.cos(a), 0.82 + 0.03 * math.sin(a), 0.3 - sunk), tip], 0.0025,
               C.WEATHERED if p.worn else C.CANVAS_OLIVE, segs=3)
        sphere(p, 0.018, tip, C.WOOL_BROWN if p.worn else "plastic_yellow", segs=5, rings=3)
    p.collider((0, 0, 0.12), (0.9, 2.0, 0.24))


def civic_hymnals(p: Prop) -> None:
    """A stack of hymnals with one lying open on top (clutter). Worn: the stack toppled."""
    r = p.rng("stack")
    z = 0.0
    for i in range(4):
        hymnal(p, (r.uniform(-0.02, 0.02), r.uniform(-0.02, 0.02), z + 0.016), rot=(0, 90, r.uniform(-8, 8)), key=f"s{i}")
        z += 0.032
    hymnal(p, (0.0, 0.0, z + 0.004), rot=(0, 0, 12), open_deg=160, key="open")
    if p.worn:
        whole = list(p.parts)
        p.rotate(whole[-2:], rot=(0, 0, 0), pivot=(0, 0, 0))
        p.lay_on_floor(whole[:2], rot=(0, 90, 0), at=(0.25, -0.12), yaw=35)
    p.collider((0, 0, 0.08), (0.3, 0.3, 0.16))


# ================================================================================================
# TAVERN
# ================================================================================================


def tube_uv(part: core.Part, rect, rings: int, segs: int, u_tiles: float = 1.0) -> None:
    """UVs for a G.tube part: U along the path (rings), V around - mapped into an atlas rect."""
    me = part.obj.data
    uvl = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
    u0, v0, u1, v1 = rect
    for li, loop in enumerate(me.loops):
        vi = loop.vertex_index
        ring, k = divmod(vi, segs)
        t = (ring / max(1, rings - 1) * u_tiles) % 1.0001
        uvl.data[li].uv = (u0 + t * (u1 - u0), v0 + (k / segs) * (v1 - v0))
    part.uv = "keep"


def glass_tumbler(p: Prop, center, h: float = 0.1, r: float = 0.035, mat: str = C.GLASS_CLEAR, key: str = "glass") -> core.Part:
    return p.lathe([(0.0, 0.0), (r * 0.85, 0.0), (r, h), (r * 0.9, h), (r * 0.75, 0.01), (0.0, 0.01)], center, mat, segs=8,
                   cap_top=False, tags=(key,))


def civic_bar_counter(p: Prop) -> None:
    """Tavern bar counter section 2.0 x 1.07 (customer side -Y): varnished mahogany top with a rolled arm
    edge, three raised front panels between pilasters, a dark toe kick and a brass foot rail on brackets;
    underbar shelves with glasses and a bus tub on the bartender side. Worn: glasses, a bottle and an
    ashtray left on top. Destroyed: the top split and dropped at one end, a front panel kicked in, the foot
    rail torn off its bracket, broken glass."""
    W, D, H = 2.0, 0.62, 1.07
    wood = C.MAHOGANY
    yf = -D / 2 + 0.1
    p.box((W, 0.04, H - 0.12), (0, yf, 0.1 + (H - 0.22) / 2), wood, bevel=0.003, grain="X")
    p.box((W, 0.05, 0.1), (0, yf + 0.04, 0.05), C.EBONY, bevel=0.003, grain="X")
    panels = []
    for i, x in enumerate((-0.64, 0.0, 0.64)):
        panels.append(p.panel(0.54, 0.62, 0.02, (x, yf - 0.03, 0.55), wood, style="raised", frame=0.06, recess=0.006, tags=("panel",)))
    for x in (-0.97, -0.32, 0.32, 0.97):
        p.box((0.07, 0.04, H - 0.2), (x, yf - 0.035, 0.1 + (H - 0.2) / 2), C.OAK_DARK, bevel=0.004, grain="Z")
    p.box((W, 0.06, 0.05), (0, yf - 0.04, 0.125), C.OAK_DARK, bevel=0.005, grain="X")
    top = [p.box((W + 0.02, D + 0.06, 0.045), (0, -0.01, H - 0.0225), wood, bevel=0.006, grain="X", tags=("top",)),
           p.rbox((W + 0.02, 0.09, 0.07), (0, -D / 2 - 0.03, H - 0.03), wood, radius=0.03, inner=(8, 1, 1), grain="X", tags=("top",))]
    rail_y = -D / 2 - 0.16
    rail = [p.tube([(-W / 2, rail_y, 0.2), (W / 2, rail_y, 0.2)], 0.025, C.BRASS, segs=10, tags=("rail",))]
    for x in (-0.8, 0.0, 0.8):
        rail.append(p.tube([(x, yf - 0.05, 0.27), (x, rail_y + 0.03, 0.26), (x, rail_y, 0.2)], 0.012, C.BRASS, segs=6, fillet_r=0.04,
                           tags=("rail",)))
    # bartender side: end panels, two underbar shelves, glasses, a bus tub
    for x in (-W / 2 + 0.02, W / 2 - 0.02):
        p.box((0.03, D - 0.12, H - 0.06), (x, 0.05, (H - 0.06) / 2), wood, bevel=0.003, grain="Z")
    for z in (0.32, 0.68):
        p.box((W - 0.08, 0.36, 0.02), (0, 0.08, z), C.OAK_DARK, bevel=0.002, grain="X")
    rg = p.rng("glasses")
    for i in range(7):
        glass_tumbler(p, (-0.85 + i * 0.12 + rg.uniform(-0.02, 0.02), 0.12 + rg.uniform(-0.04, 0.04), 0.69), key=f"g{i}")
    p.hollow((0.5, 0.36, 0.17), (0.55, 0.08, 0.33 + 0.085), M.PL_GREY, wall=0.006, open_face="+Z")
    if p.worn and not p.destroyed:
        glass_tumbler(p, (-0.55, -0.12, H), key="t1")
        glass_tumbler(p, (0.25, -0.18, H), h=0.15, r=0.04, key="t2")
        bottle(p, 0, (-0.2, -0.05, H), label=0, key="b1")
        p.lathe([(0.0, 0.0), (0.06, 0.0), (0.065, 0.02), (0.05, 0.025), (0.0, 0.015)], (0.62, -0.08, H), C.GLASS_CLEAR, segs=10)
        for i in range(3):
            p.cyl(0.045, 0.002, (-0.75 + i * 0.5, -0.15, H + 0.001), C.PAPER, segs=10)
    if p.destroyed:
        rr = p.vrng("wreck")
        G.splinter_cut(top[0].obj, (0.35, 0, 0), (1, 0, 0), jag=0.04, seed=p.seed)
        G.splinter_cut(top[1].obj, (0.35, 0, 0), (1, 0, 0), jag=0.04, seed=p.seed + 1)
        piece = p.box((0.64, D + 0.06, 0.045), (0.69, -0.01, H - 0.0225), wood, bevel=0.006, grain="X")
        G.xform(piece.obj, rot=(0, 28, 0), pivot=(1.0, 0, 0.7))
        p.remove([panels[1]])
        a, b = F.split_panel(p, 0.54, 0.62, 0.02, (0.0, yf - 0.03, 0.55), wood, (-0.27, 0.2), (0.27, -0.15), key="kick")
        G.xform(b.obj, rot=(25, 0, 0), pivot=(0, yf, 0.24))
        p.rotate(rail[:1] + rail[3:], rot=(0, -12, 0), pivot=(-0.8, rail_y, 0.2))
        F.shatter_pane(p, 0.4, 0.3, (0.2, -0.75, 0.0), C.GLASS_CLEAR, t=0.003, plane="XY", key="glass", missing_inner=1.0, missing_outer=0.6)
    p.collider((0, -0.03, H / 2), (W, D + 0.12, H))


def civic_back_bar(p: Prop) -> None:
    """Back bar 2.0 x 2.2 x 0.48 (faces the room, -Y): mahogany base cabinet with four doors and a counter,
    an upper mirror between turned columns, glass shelves of labelled liquor bottles either side, a
    moulded cornice. Worn: bottles thinned out, the mirror desilvering. Destroyed: the mirror smashed,
    a shelf collapsed, most bottles broken."""
    W, D = 2.0, 0.46
    wood = C.MAHOGANY
    F.carcass(p, W, -D / 2, D / 2, 0.08, 0.86, wood, top=False, rails=())
    p.box((W + 0.04, D + 0.04, 0.08), (0, 0, 0.04), C.EBONY, bevel=0.004, grain="X")
    for i in range(4):
        x0 = -W / 2 + 0.06 + i * (W - 0.12) / 4
        x1 = x0 + (W - 0.12) / 4 - 0.01
        F.door(p, x0, 0.14, x1, 0.82, -D / 2 - 0.02, wood, style="raised", hinge="left" if i % 2 == 0 else "right", handle="knob",
               handle_mat=C.BRASS, key=f"d{i}", open_deg=(25.0 if (p.worn and i == 2) else 0.0))
    p.box((W + 0.06, D + 0.06, 0.045), (0, 0, 0.885), wood, bevel=0.006, grain="X")
    # upper section
    p.box((W, 0.03, 1.22), (0, D / 2 - 0.1, 0.9 + 0.61), wood, bevel=0.003, grain="X")
    mw, mh = 0.9, 0.85
    mirror = None
    if not p.destroyed:
        mirror = p.box((mw, 0.008, mh), (0, D / 2 - 0.12, 1.42), M.MIRROR, bevel=0.0, uv="planar", uv_axis="Y", tags=("mirror",))
    else:
        F.shatter_pane(p, mw, mh, (0, D / 2 - 0.12, 1.42), M.MIRROR, t=0.006, impact=(0.12, -0.1), key="mirror", spokes=11, rings=3,
                       missing_inner=0.9, missing_outer=0.25, floor_shards=0)
    del mirror
    for x in (-mw / 2 - 0.05, mw / 2 + 0.05, -W / 2 + 0.04, W / 2 - 0.04):
        p.lathe([(0.04, 0.0), (0.035, 0.05), (0.028, 0.12), (0.032, 0.9), (0.042, 0.98), (0.045, 1.04), (0.0, 1.05)], (x, D / 2 - 0.15, 0.91),
                C.OAK_DARK, segs=10)
    p.box((W + 0.1, 0.24, 0.12), (0, D / 2 - 0.2, 2.02), wood, bevel=0.008, grain="X")
    p.box((W + 0.18, 0.3, 0.06), (0, D / 2 - 0.22, 2.11), C.OAK_DARK, bevel=0.01, grain="X")
    r = p.rng("bottles")
    lose = p.vrng("lose")
    for side in (-1, 1):
        xa, xb = (side * (mw / 2 + 0.1), side * (W / 2 - 0.09))
        lo_x, hi_x = min(xa, xb), max(xa, xb)
        for k, z in enumerate((0.93, 1.38, 1.78)):
            sh = p.box((hi_x - lo_x, 0.22, 0.01), ((lo_x + hi_x) / 2, D / 2 - 0.22, z), M.GLASS, bevel=0.0, tags=("shelf",))
            if p.destroyed and side > 0 and k == 1:
                G.xform(sh.obj, rot=(0, 17, 0), pivot=(lo_x, 0, z))
            x = lo_x + 0.05
            while x < hi_x - 0.05:
                kind = r.choice([0, 1, 1, 3, 2])
                keep = not ((p.worn and lose.random() < 0.3) or (p.destroyed and lose.random() < 0.7))
                if keep and not (p.destroyed and side > 0 and k == 1):
                    bottle(p, kind, (x, D / 2 - 0.22 + r.uniform(-0.03, 0.03), z + 0.005), label=r.randrange(8) if kind != 2 else 5,
                           scale=r.uniform(0.92, 1.05), key=f"b{side}{k}{int(x * 100)}")
                x += r.uniform(0.085, 0.11)
    # a till and a row of glasses on the counter
    for i in range(6):
        glass_tumbler(p, (-0.3 + i * 0.12, D / 2 - 0.2, 0.91), key=f"cg{i}")
    if p.destroyed:
        rr = p.vrng("wreck")
        for i in range(6):
            G.splinter_cut(bottle(p, rr.choice([0, 1, 3]), (rr.uniform(-0.9, 0.9), -D / 2 - rr.uniform(0.2, 0.6), 0.0))[0].obj,
                           (0, 0, rr.uniform(0.03, 0.08)), (rr.uniform(-0.3, 0.3), rr.uniform(-0.3, 0.3), 1), jag=0.02, seed=p.seed + i)
    p.collider((0, 0.0, 1.1), (W + 0.1, D + 0.06, 2.2))


def civic_beer_taps(p: Prop) -> None:
    """Draught beer tower for the bar top (surface prop 0.66 x 0.55): chrome T-bar on a column over a
    stainless drip tray with a grate, four faucets with tall labelled tap handles. Worn: one handle gone,
    the tray furred with old beer."""
    p.box((0.62, 0.16, 0.025), (0, -0.04, 0.0125), M.STAINLESS, bevel=0.004, grain="X")
    for i in range(12):
        p.box((0.006, 0.13, 0.004), (-0.28 + i * 0.051, -0.04, 0.027), M.STAINLESS, bevel=0.0)
    p.cyl(0.07, 0.015, (0, 0.06, 0.0075), M.CHROME, segs=12)
    p.cyl(0.04, 0.36, (0, 0.06, 0.195), M.CHROME, segs=12)
    p.cyl(0.036, 0.62, (0, 0.06, 0.39), M.CHROME, axis="X", segs=12)
    for sx in (-1, 1):
        sphere(p, 0.036, (sx * 0.31, 0.06, 0.39), M.CHROME, segs=10, rings=5)
    gone = p.vrng("gone").randrange(4) if p.worn else -1
    for i in range(4):
        x = -0.24 + i * 0.16
        p.tube([(x, 0.03, 0.39), (x, -0.03, 0.39), (x, -0.06, 0.37), (x, -0.06, 0.32)], 0.013, M.CHROME, segs=8, fillet_r=0.03)
        p.cyl(0.015, 0.02, (x, -0.06, 0.32), M.CHROME, segs=8)
        if i == gone:
            continue
        p.lathe([(0.0, 0.0), (0.012, 0.0), (0.014, 0.03), (0.02, 0.05), (0.022, 0.2), (0.016, 0.22), (0.0, 0.225)], (x, -0.025, 0.415),
                C.EBONY, segs=8)
        plate(p, 0.034, 0.08, (x, -0.048, 0.53), atlas("taps", i), t=0.004)
    if p.worn:
        p.box((0.56, 0.13, 0.002), (0, -0.04, 0.03), M.MOLD, bevel=0.0)
    p.collider((0, 0.0, 0.31), (0.66, 0.2, 0.62))


def civic_bar_stool(p: Prop) -> None:
    """Swivel bar stool 0.76 m: four splayed oak legs with a chrome foot ring, swivel plate, round oak seat
    with an oxblood vinyl cushion. Destroyed: tipped over, a leg snapped, the cushion split."""
    H = 0.76
    legs = []
    for i in range(4):
        a = math.radians(45 + 90 * i)
        legs.append(bar(p, (math.cos(a) * 0.21, math.sin(a) * 0.21, 0.0), (math.cos(a) * 0.12, math.sin(a) * 0.12, H - 0.08), 0.035, 0.035,
                        C.OAK_DARK, tags=("leg",)))
    ring = [(0.17 * math.cos(math.radians(a)), 0.17 * math.sin(math.radians(a)), 0.28) for a in range(0, 360, 20)]
    p.tube(ring, 0.011, M.CHROME, segs=6, closed=True)
    p.cyl(0.14, 0.03, (0, 0, H - 0.07), C.OAK_DARK, segs=12)
    p.cyl(0.08, 0.025, (0, 0, H - 0.045), M.CAST_IRON, segs=10)
    seat = [p.lathe([(0.0, 0.0), (0.185, 0.0), (0.19, 0.03), (0.0, 0.031)], (0, 0, H - 0.035), C.OAK, segs=16),
            p.lathe([(0.175, 0.0), (0.18, 0.025), (0.16, 0.045), (0.08, 0.055), (0.0, 0.057)], (0, 0, H - 0.005), M.VINYL_RED, segs=16,
                    cap_bottom=False, edge_deg=45)]
    if p.destroyed:
        G.splinter_cut(legs[1].obj, (0, 0, 0.35), (0, 0, 1), jag=0.02, seed=p.seed)
        F.slash(p, (0.0, 0.0, H + 0.045), 0.18, 40, key="seat")
        whole = list(p.parts)
        p.rotate(whole, rot=(0, 96, 20), pivot=(0, 0, 0))
        lo, hi = p.bounds(whole)
        p.move(whole, (0, 0, -lo.z))
        p.collider((0, 0, 0.21), (0.8, 0.45, 0.42))
    else:
        p.collider((0, 0, H / 2), (0.44, 0.44, H + 0.05))
    del seat


def civic_pool_table(p: Prop) -> None:
    """Seven-foot pool table 2.5 x 1.42 x 0.82: mahogany frame and apron on four turned legs, green baize bed
    and cushions, leather drop pockets, pearl diamond sights, a game in progress (balls from the civic
    atlas), cue and chalk. Worn: balls scattered, beer rings on the rails. Destroyed: a leg snapped so the
    table lists, the cloth slashed, balls on the floor, the cue broken."""
    L, Wt = 2.5, 1.42
    H = 0.8
    wood = C.MAHOGANY
    p.box((L - 0.16, Wt - 0.16, 0.2), (0, 0, H - 0.17), wood, bevel=0.008, grain="X")
    p.box((L - 0.3, Wt - 0.3, 0.06), (0, 0, H - 0.05), C.FELT_GREEN, bevel=0.002, uv_scale=1.0)
    pockets = [(-1, -1), (0, -1), (1, -1), (-1, 1), (0, 1), (1, 1)]
    bx, by = (L - 0.3) / 2, (Wt - 0.3) / 2
    for sy in (-1, 1):
        for sx in (-1, 1):
            seg = (L - 0.3) / 2 - 0.13
            p.rbox((seg, 0.05, 0.045), (sx * (seg / 2 + 0.06), sy * (by - 0.0), H + 0.0), C.FELT_GREEN, radius=0.015, inner=(4, 1, 1))
            p.box((seg + 0.04, 0.13, 0.05), (sx * (seg / 2 + 0.06), sy * (by + 0.085), H + 0.0), wood, bevel=0.008, grain="X")
            for k in range(3):
                p.cyl(0.006, 0.002, (sx * (0.32 + k * 0.32), sy * (by + 0.085), H + 0.026), C.IVORY, segs=6)
    for sx in (-1, 1):
        seg = (Wt - 0.3) - 0.2
        p.rbox((0.05, seg, 0.045), (sx * bx, 0, H), C.FELT_GREEN, radius=0.015, inner=(1, 4, 1))
        p.box((0.13, seg + 0.04, 0.05), (sx * (bx + 0.085), 0, H), wood, bevel=0.008, grain="Y")
    for sx, sy in pockets:
        x = sx * (bx + 0.02) if sx else 0.0
        y = sy * (by + 0.03)
        p.lathe([(0.065, 0.0), (0.06, -0.06), (0.045, -0.12), (0.0, -0.13)], (x, y, H + 0.02), C.LEATHER, segs=10, cap_bottom=False,
                cap_top=False)
        p.lathe([(0.075, 0.0), (0.075, 0.02), (0.06, 0.03), (0.0, 0.03)], (x, y, H - 0.01), M.CAST_IRON, segs=10)
    legs = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            legs.append(p.lathe([(0.075, 0.0), (0.085, 0.04), (0.06, 0.08), (0.05, 0.25), (0.07, 0.32), (0.055, 0.42), (0.065, 0.5),
                                 (0.07, 0.56), (0.0, 0.57)], (sx * (L / 2 - 0.25), sy * (Wt / 2 - 0.22), 0.0), wood, segs=10, tags=("leg",)))
    r = p.vrng("balls")
    balls = []
    n = 9 if not p.destroyed else 5
    for k in range(n):
        idx = [0, 1, 3, 5, 8, 9, 11, 12, 14][k]
        bp = (r.uniform(-bx + 0.15, bx - 0.15), r.uniform(-by + 0.12, by - 0.12), H + 0.0285)
        balls.append(sphere(p, 0.0285, bp, C.PRINT, segs=8, rings=5, uv="planar", uv_axis="Z", rect=atlas("pool_balls", idx)))
    cue = [p.cyl(0.006, 1.45, (0, 0, 0), C.OAK, axis="X", segs=6, r_top=0.014)]
    G.xform(cue[0].obj, rot=(0, 0, 14), loc=(0.1, -0.15, H + 0.04))
    p.box((0.022, 0.022, 0.022), (bx - 0.05, by + 0.08, H + 0.036), M.PL_BLUE, bevel=0.002)
    if p.worn and not p.destroyed:
        for i in range(2):
            p.cyl(0.04, 0.001, (-0.6 + i * 1.1, -(by + 0.085), H + 0.026), M.MOLD, segs=10)
    if p.destroyed:
        rr = p.vrng("wreck")
        G.splinter_cut(legs[1].obj, (0, 0, 0.3), (0, 0, 1), jag=0.03, seed=p.seed)
        for q in balls[:3]:
            lo, hi = p.bounds([q])
            p.move([q], (rr.uniform(-0.5, 0.5), -Wt / 2 - 0.3 - rr.uniform(0, 0.4) - (lo.y + hi.y) / 2 * 0, -lo.z))
        for i in range(2):
            F.slash(p, (rr.uniform(-0.7, 0.7), rr.uniform(-0.3, 0.3), H + 0.03), 0.4, rr.uniform(-40, 40), key=f"s{i}")
        G.splinter_cut(cue[0].obj, (0.25, 0, 0), (1, 0.2, 0), jag=0.01, seed=p.seed + 5)
        whole = [q for q in p.parts if q not in balls[:3]]
        p.rotate(whole, rot=(-6, 0, 0), pivot=(0, -Wt / 2 + 0.22, 0))
        lo, hi = p.bounds(whole)
        p.move(whole, (0, 0, -max(0.0, lo.z)))
    p.collider((0, 0, H / 2 + 0.01), (L, Wt, H + 0.02))


def civic_jukebox(p: Prop) -> None:
    """1950s-style jukebox 0.86 x 1.48 x 0.62: walnut cabinet with chrome trim, a speaker grille, a glazed
    window over the record carousel and the title-card strip, a row of selector buttons and a coin slot,
    and an arch of coloured moulded plastic over the top. Dead with the power. Destroyed: the window
    smashed, the arch cracked, records spilled across the floor."""
    W, D = 0.84, 0.6
    wood = C.MAHOGANY
    p.box((W, D, 0.82), (0, 0.0, 0.41), wood, bevel=0.01, grain="Z")
    p.box((W + 0.02, D + 0.02, 0.05), (0, 0.0, 0.025), C.EBONY, bevel=0.006, grain="X")
    plate(p, 0.62, 0.48, (0, -D / 2 - 0.002, 0.4), atlas("juke_grille"), t=0.006)
    for z in (0.15, 0.66):
        p.box((W - 0.06, 0.02, 0.025), (0, -D / 2 - 0.006, z), M.CHROME, bevel=0.004, grain="X")
    p.box((W - 0.02, D - 0.04, 0.5), (0, 0.02, 0.82 + 0.25), C.EBONY, bevel=0.004)
    # window over the carousel: dark interior, title cards, glass
    p.box((0.6, 0.05, 0.3), (0, -D / 2 + 0.07, 1.04), M.PL_BLACK, bevel=0.0)
    plate(p, 0.56, 0.17, (0, -D / 2 + 0.045, 0.94), atlas("juke_cards"), t=0.003)
    for i in range(3):
        p.cyl(0.09, 0.004, (-0.15 + i * 0.15, -D / 2 + 0.1, 1.12), M.PL_BLACK, axis="Y", segs=12)
    if not p.destroyed:
        p.box((0.62, 0.006, 0.36), (0, -D / 2 + 0.01, 1.03), M.GLASS, bevel=0.0)
    else:
        F.shatter_pane(p, 0.62, 0.36, (0, -D / 2 + 0.01, 1.03), M.GLASS, t=0.005, key="juke", spokes=9, rings=2, missing_inner=0.95,
                       missing_outer=0.5)
    for i in range(10):
        p.box((0.035, 0.03, 0.02), (-0.2 + i * 0.044, -D / 2 - 0.01, 0.8), C.IVORY, bevel=0.003)
    p.box((0.5, 0.04, 0.05), (0, -D / 2 - 0.005, 0.8), M.CHROME, bevel=0.004, grain="X")
    p.box((0.06, 0.02, 0.09), (0.33, -D / 2 - 0.01, 0.73), M.CHROME, bevel=0.003)
    # coloured plastic pilasters and the arch
    for sx in (-1, 1):
        q = p.cyl(0.05, 0.5, (sx * (W / 2 - 0.02), -D / 2 + 0.05, 1.07), C.PRINT, segs=10, uv="planar", uv_axis="Y",
                  rect=atlas("juke_arch"))
        del q
    arch = [(0.4 * math.cos(math.radians(a)), -D / 2 + 0.05, 1.32 + 0.22 * math.sin(math.radians(a))) for a in range(0, 181, 10)]
    tube = p.tube(arch, 0.055, C.PRINT, segs=10, cap=True, tags=("arch",))
    tube_uv(tube, atlas("juke_arch"), len(arch), 10)
    back = p.prism([(0.4 * math.cos(math.radians(a)), 1.32 + 0.22 * math.sin(math.radians(a))) for a in range(0, 181, 15)], D - 0.12,
                   wood, plane="XZ", offset=-D / 2 + 0.1, bevel=0.006, grain="X")
    del back
    p.box((0.12, 0.06, 0.05), (0, -D / 2 + 0.05, 1.58), M.CHROME, bevel=0.01)
    if p.destroyed:
        rr = p.vrng("wreck")
        G.splinter_cut(tube.obj, (0.15, 0, 1.5), (1, 0, 0.4), jag=0.02, seed=p.seed)
        for i in range(6):
            c = (rr.uniform(-0.6, 0.6), rr.uniform(-1.0, -0.45), 0.0015 + i * 0.002)
            p.cyl(0.09, 0.003, c, M.PL_BLACK, segs=12)
            p.cyl(0.04, 0.0035, c, M.PL_RED, segs=10)
    p.collider((0, 0.0, 0.77), (W + 0.04, D + 0.02, 1.54))


def civic_dartboard(p: Prop) -> None:
    """Dartboard cabinet (wall, origin on the wall plane at the bottom centre; hang it ~1.37 m up so the
    bullseye sits at 1.73 m): bristle board with wire spider and number ring, cabinet doors open with
    chalk scoreboards inside, three darts in the board. Worn: two darts gone, scores smeared."""
    D = 0.07
    p.box((0.62, D, 0.72), (0, -D / 2, 0.36), C.OAK_DARK, bevel=0.005, grain="Z")
    board = p.cyl(0.226, 0.04, (0, -D - 0.02, 0.36), C.PRINT, axis="Y", segs=24, uv="planar", uv_axis="Y", rect=atlas("dart"))
    del board
    p.lathe([(0.226, 0.0), (0.232, 0.0), (0.232, 0.042), (0.226, 0.042)], (0, -D, 0.36), M.CAST_IRON, segs=24, axis="-Y", cap_bottom=False,
            cap_top=False)
    for sx in (-1, 1):
        door = p.box((0.31, 0.03, 0.72), (0, 0, 0), C.OAK_DARK, bevel=0.004, grain="Z")
        chalk = p.box((0.25, 0.004, 0.6), (0, 0, 0), M.CHALK, bevel=0.0, uv="planar", uv_axis="Y")
        G.xform(chalk.obj, loc=(0, 0.017, 0))
        for q in (door, chalk):
            G.xform(q.obj, rot=(0, 0, sx * -100), pivot=(0, 0, 0))
            G.xform(q.obj, loc=(sx * 0.31 + sx * math.cos(math.radians(10)) * 0.0, -D - 0.16, 0.36))
    r = p.vrng("darts")
    n = 1 if p.worn else 3
    for i in range(n):
        a = r.uniform(0, math.pi * 2)
        rr = r.uniform(0.0, 0.16)
        tip = (math.cos(a) * rr, -D - 0.045, 0.36 + math.sin(a) * rr)
        tail = (tip[0] + r.uniform(-0.01, 0.01), tip[1] - 0.15, tip[2] + r.uniform(0.0, 0.02))
        p.tube([tip, tail], 0.0035, M.CHROME, segs=5)
        for k in range(3):
            fl = p.box((0.002, 0.04, 0.025), (tail[0], tail[1] + 0.015, tail[2]), C.PAINT_RED, bevel=0.0)
            G.xform(fl.obj, rot=(0, 120 * k, 0), pivot=(tail[0], tail[1], tail[2]))
    p.collider((0, -0.06, 0.36), (0.66, 0.12, 0.72))


def civic_keg(p: Prop) -> None:
    """Stainless half-barrel beer keg (0.41 x 0.6) with rolling rings, a tapped coupler and beer line, and
    the brewery's stamped plate. Destroyed: dented, rolled onto its side."""
    prof = [(0.0, 0.0), (0.19, 0.0), (0.205, 0.01), (0.205, 0.05), (0.198, 0.06), (0.2, 0.17), (0.212, 0.18), (0.212, 0.2),
            (0.203, 0.21), (0.205, 0.39), (0.212, 0.4), (0.212, 0.42), (0.203, 0.43), (0.198, 0.54), (0.205, 0.55), (0.205, 0.59),
            (0.19, 0.6), (0.17, 0.595), (0.06, 0.585), (0.0, 0.585)]
    keg = p.lathe(prof, (0, 0, 0), M.STAINLESS, segs=18, tags=("keg",))
    plate(p, 0.14, 0.14, (0, -0.2, 0.3), atlas("keg_stamp"), t=0.003, tags=("keg",))
    p.cyl(0.035, 0.02, (0, 0, 0.595), M.CHROME, segs=10, tags=("keg",))
    if not p.destroyed:
        p.cyl(0.045, 0.05, (0, 0, 0.63), M.PL_BLACK, segs=10)
        p.tube([(0.03, 0, 0.65), (0.1, 0, 0.66), (0.14, 0, 0.62)], 0.008, M.CHROME, segs=5, fillet_r=0.03)
        p.tube([(0, 0.0, 0.66), (0.0, 0.05, 0.75), (0.1, 0.15, 0.78), (0.3, 0.2, 0.75)], 0.007, M.PL_WHITE, segs=5, fillet_r=0.08)
    else:
        for v in keg.obj.data.vertices:
            d = math.hypot(v.co.x - 0.15, v.co.z - 0.3)
            if v.co.x > 0.1 and d < 0.15:
                v.co.x -= 0.035 * (1 - d / 0.15)
        whole = list(p.parts)
        p.rotate(whole, rot=(0, 90, 30), pivot=(0, 0, 0))
        lo, hi = p.bounds(whole)
        p.move(whole, (0, 0, -lo.z))
    p.collider((0, 0, 0.3), (0.42, 0.42, 0.6))


def civic_beer_crates(p: Prop) -> None:
    """Two stacked returnable beer crates (0.45 x 0.32), the top one full of brown bottles. Worn: the top crate
    slid askew, empties."""
    for k in range(2):
        z = k * 0.27
        c = p.hollow((0.45, 0.32, 0.26), (0, 0, z + 0.13), M.PL_RED if k == 0 else C.PAINT_GREEN, wall=0.008, open_face="+Z", tags=(f"c{k}",))
        if p.worn and k == 1:
            G.xform(c.obj, rot=(0, 0, 9), pivot=(0, 0, 0))
        for sx in (-1, 1):
            p.box((0.004, 0.12, 0.04), (sx * 0.226, 0, z + 0.21), M.PL_BLACK, bevel=0.0)
    r = p.vrng("bottles")
    for i in range(4):
        for j in range(3):
            if p.worn and r.random() < 0.3:
                continue
            bottle(p, 2, (-0.165 + i * 0.11, -0.1 + j * 0.1, 0.27 + 0.01), label=None, key=f"b{i}{j}")
    p.collider((0, 0, 0.3), (0.46, 0.33, 0.6))


# ================================================================================================
# POST OFFICE
# ================================================================================================


def civic_po_counter(p: Prop) -> None:
    """Post-office service counter 2.0 x 2.1 x 0.72 (public side -Y): panelled oak counter with a worn top,
    a brass grille screen above it - bars, posts, arched service windows with marble deal plates - under a
    frosted-glass transom; stamp drawers and pigeonholes on the clerk's side. Worn: a hand-lettered CLOSED
    card hung in a window, a Cordon notice taped to the grille. Destroyed: a window's bars wrenched out
    and bent, the top split."""
    W, D, H = 2.0, 0.62, 1.0
    wood = C.OAK
    p.box((W, D - 0.08, H - 0.1), (0, 0.04, 0.1 + (H - 0.12) / 2), wood, bevel=0.004, grain="X")
    p.box((W, 0.06, 0.1), (0, -D / 2 + 0.1, 0.05), C.OAK_DARK, bevel=0.003, grain="X")
    for x in (-0.66, 0.0, 0.66):
        p.panel(0.56, 0.66, 0.02, (x, -D / 2 + 0.07, 0.52), wood, style="raised", frame=0.06, recess=0.006, tags=("panel",))
    for x in (-0.99, -0.33, 0.33, 0.99):
        p.box((0.06, 0.035, H - 0.14), (x, -D / 2 + 0.06, 0.1 + (H - 0.14) / 2), C.OAK_DARK, bevel=0.004, grain="Z")
    top = p.box((W + 0.04, D + 0.06, 0.05), (0, 0.0, H + 0.025), C.OAK_DARK, bevel=0.006, grain="X", tags=("top",))
    gz = H + 0.05
    grille = []
    for x in (-1.0, 0.0, 1.0):
        grille.append(p.box((0.045, 0.045, 1.05), (x, 0.0, gz + 0.525), C.BRASS, bevel=0.005, tags=("grille",)))
    grille.append(p.box((W + 0.06, 0.06, 0.06), (0, 0.0, gz + 1.08), C.BRASS, bevel=0.006, grain="X", tags=("grille",)))
    grille.append(p.box((W, 0.05, 0.04), (0, 0.0, gz + 0.02), C.BRASS, bevel=0.004, grain="X", tags=("grille",)))
    grille.append(p.box((W, 0.04, 0.035), (0, 0.0, gz + 0.78), C.BRASS, bevel=0.004, grain="X", tags=("grille",)))
    for k in range(4):
        x0 = -1.0 + 0.025 + k * 0.5
        grille.append(p.box((0.45, 0.006, 0.24), (x0 + 0.225, 0.0, gz + 0.93), M.GLASS_FROST, bevel=0.0))
        grille.append(p.box((0.02, 0.03, 0.26), (x0 + 0.46, 0.0, gz + 0.93), C.BRASS, bevel=0.003))
    rk = p.vrng("bars")
    windows = {}
    for bay in (-1, 1):
        cx = bay * 0.5
        win_w, win_top = 0.44, gz + 0.48
        bars = []
        for i in range(17):
            x = cx - 0.47 + i * 0.0588
            inside = abs(x - cx) < win_w / 2
            z0 = win_top + 0.06 * math.cos((x - cx) / (win_w / 2) * math.pi / 2) if inside else gz + 0.04
            bars.append(p.cyl(0.0055, gz + 0.76 - z0, (x, 0.0, (z0 + gz + 0.76) / 2), C.BRASS, segs=6, tags=("bar",)))
        arch = [(cx + win_w / 2 * math.cos(a), 0.0, win_top + 0.06 * math.sin(a)) for a in [math.pi * i / 10 for i in range(11)]]
        bars.append(p.tube([(cx + win_w / 2, 0, gz + 0.04)] + arch + [(cx - win_w / 2, 0, gz + 0.04)], 0.009, C.BRASS, segs=6, tags=("bar",)))
        p.box((win_w + 0.06, 0.3, 0.025), (cx, -0.1, gz + 0.0125), C.MARBLE, bevel=0.004, grain="X")
        windows[bay] = bars
    # clerk side: stamp drawers and pigeonholes
    for i in range(6):
        F.drawer(p, -0.9 + i * 0.3, 0.74, -0.62 + i * 0.3, 0.88, D / 2 - 0.02 + 0.0, 0.3, wood, style="slab", handle="knob",
                 handle_mat=C.BRASS, key=f"sd{i}", contents=False)
    for g in p.tagged("drawer") + p.tagged("knob"):
        G.xform(g.obj, rot=(0, 0, 180), pivot=(g.obj.data.vertices[0].co.x * 0 + 0.0, D / 2 - 0.02, 0))
    if p.worn and not p.destroyed:
        plate(p, 0.24, 0.09, (-0.5, -0.012, gz + 0.36), atlas("closed_sign"), t=0.002, rot=(0, 4, 0))
        p.tube([(-0.6, -0.006, gz + 0.41), (-0.5, -0.006, gz + 0.5), (-0.4, -0.006, gz + 0.41)], 0.0015, C.CANVAS_KHAKI, segs=3)
        plate(p, 0.2, 0.275, (0.62, -0.012, gz + 0.52), atlas("notice"), t=0.001, rot=(0, -3, 0))
    if p.destroyed:
        rr = p.vrng("wreck")
        for q in windows[1][4:13]:
            if rr.random() < 0.5:
                p.remove([q])
            else:
                lo, hi = p.bounds([q])
                G.xform(q.obj, rot=(rr.uniform(-35, -15), 0, 0), pivot=((lo.x + hi.x) / 2, 0, hi.z))
        G.splinter_cut(top.obj, (-0.4, 0, 0), (1, 0.3, 0), jag=0.03, seed=p.seed)
        piece = p.box((0.6, D + 0.06, 0.05), (-0.75, 0.0, H + 0.025), C.OAK_DARK, bevel=0.006, grain="X")
        G.xform(piece.obj, rot=(0, -10, 0), pivot=(-0.45, 0, H))
    p.collider((0, 0.0, 1.05), (W + 0.06, D + 0.06, 2.1))


def civic_po_boxes(p: Prop) -> None:
    """Bank of 96 brass post-office boxes (1.0 x 2.0 x 0.42 oak cabinet against the wall): numbered doors with
    glazed windows and combination dials (civic_po_boxes atlas) between an oak plinth and crown; seven
    doors pried and hanging open. Destroyed: a whole block of doors ripped out, the leaves on the floor."""
    W, D = 1.0, 0.42
    wood = C.OAK_DARK
    p.box((W + 0.06, D, 0.3), (0, 0.0, 0.15), wood, bevel=0.006, grain="X")
    p.box((W + 0.08, D + 0.02, 0.04), (0, -0.005, 0.32), C.OAK, bevel=0.006, grain="X")
    p.box((W + 0.06, D, 1.52), (0, 0.01, 0.34 + 0.76), wood, bevel=0.004, grain="Z")
    p.box((W + 0.12, D + 0.06, 0.08), (0, -0.01, 1.9), C.OAK, bevel=0.01, grain="X")
    p.box((W + 0.16, D + 0.08, 0.04), (0, -0.02, 1.96), wood, bevel=0.008, grain="X")
    face_y = -D / 2 - 0.004
    plate(p, W, 1.5, (0, face_y, 0.34 + 0.75), (0.0, 0.0, 1.0, 1.0), t=0.008, mat=C.PO_BOXES)
    pried = list(PO_PRIED)
    if p.destroyed:
        pried += [33, 34, 35, 40, 41, 42, 43, 48, 49, 50]
    rr = p.vrng("leaves")
    for k in pried:
        col, row = k % 8, k // 8
        x = -W / 2 + (col + 0.5) * (W / 8)
        z = 1.84 - (row + 0.5) * 0.125
        if k not in PO_PRIED:
            p.box((W / 8 - 0.012, 0.01, 0.113), (x, face_y - 0.004, z), M.PL_BLACK, bevel=0.0)
        leaf = p.box((W / 8 - 0.014, 0.006, 0.112), (0, 0, 0), C.BRASS, bevel=0.0015)
        if k in PO_PRIED or rr.random() < 0.4:
            G.xform(leaf.obj, loc=((W / 8 - 0.014) / 2, 0, 0))
            G.xform(leaf.obj, rot=(0, rr.uniform(-6, 6), -rr.uniform(70, 125)))
            G.xform(leaf.obj, loc=(x - W / 16 + 0.007, face_y - 0.012, z))
        else:
            G.xform(leaf.obj, rot=(90, 0, rr.uniform(0, 180)), loc=(rr.uniform(-0.5, 0.5), rr.uniform(-0.9, -0.35), 0.004))
    if p.destroyed:
        scatter_papers(p, (0.0, -0.6, 0.0), 8, 0.35, "letters", z_step=0.0015, floor=True)
    p.collider((0, 0.0, 1.0), (W + 0.12, D + 0.04, 2.0))


def civic_sorting_rack(p: Prop) -> None:
    """Mail sorting case 1.4 x 1.8 x 0.5: an oak pigeonhole case of 6 x 8 slots with route labels, on a table
    with a work ledge and a lower shelf of mail tubs; letters in a good third of the slots. Worn: letters
    left on the ledge. Destroyed: the case wrenched forward off its table, letters strewn."""
    W, D = 1.4, 0.5
    wood = C.OAK
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.box((0.05, 0.05, 0.8), (sx * (W / 2 - 0.04), sy * (D / 2 - 0.04), 0.4), C.OAK_DARK, bevel=0.004, grain="Z")
    p.box((W, D, 0.035), (0, 0, 0.8), wood, bevel=0.004, grain="X")
    p.box((W - 0.08, D - 0.08, 0.02), (0, 0, 0.2), C.OAK_DARK, bevel=0.003, grain="X")
    for i in range(3):
        p.hollow((0.38, 0.3, 0.14), (-0.45 + i * 0.45, 0.0, 0.21 + 0.07), M.PL_GREY, wall=0.006, open_face="+Z")
    case = []
    cz0, cz1 = 0.82, 1.8
    cd = 0.34
    cy = D / 2 - cd / 2 - 0.01
    case.append(p.box((W - 0.04, 0.02, cz1 - cz0), (0, D / 2 - 0.02, (cz0 + cz1) / 2), C.OAK_DARK, bevel=0.002, grain="X", tags=("case",)))
    for i in range(7):
        x = -(W - 0.06) / 2 + i * (W - 0.06) / 6
        case.append(p.box((0.012 if 0 < i < 6 else 0.025, cd, cz1 - cz0), (x, cy, (cz0 + cz1) / 2), wood, bevel=0.0015, grain="Z", tags=("case",)))
    rows = 8
    for j in range(rows + 1):
        z = cz0 + j * (cz1 - cz0) / rows
        case.append(p.box((W - 0.06, cd, 0.01 if 0 < j < rows else 0.025), (0, cy, z), wood, bevel=0.0015, grain="X", tags=("case",)))
        if 0 < j < rows and j % 2 == 0:
            for i in range(6):
                if (i + j) % 3 == 0:
                    lx = -(W - 0.06) / 2 + (i + 0.5) * (W - 0.06) / 6
                    case.append(plate(p, 0.15, 0.025, (lx, cy - cd / 2 - 0.002, z - 0.012), atlas("sort_labels", (i + j) % 8), t=0.002,
                                      tags=("case",)))
    r = p.rng("letters")
    for j in range(rows):
        for i in range(6):
            if r.random() < 0.38:
                lx = -(W - 0.06) / 2 + (i + 0.5) * (W - 0.06) / 6
                lz = cz0 + j * (cz1 - cz0) / rows + 0.006
                n = r.randint(2, 6)
                env = p.box((0.16, 0.012 * n, 0.09), (lx + r.uniform(-0.02, 0.02), cy + r.uniform(-0.05, 0.05), lz + 0.045), C.PAPER,
                            bevel=0.001, tags=("case",))
                G.xform(env.obj, rot=(r.uniform(-8, 8), 0, 0), pivot=(lx, cy, lz))
                case.append(env)
    if p.worn and not p.destroyed:
        scatter_papers(p, (-0.2, -0.05, 0.8175), 5, 0.25, "ledge")
    if p.destroyed:
        p.rotate(case, rot=(-28, 0, 3), pivot=(0, -D / 2 + 0.02, 0.82))
        scatter_papers(p, (0.0, -0.75, 0.0), 14, 0.5, "floor", z_step=0.0015, floor=True)
    p.collider((0, 0, 0.9), (W, D, 1.8))


def civic_parcel_cage(p: Prop) -> None:
    """Welded-mesh parcel cage 1.6 x 2.1 x 1.0 (registered mail and parcels): galvanised square-tube frame,
    mesh panels, a mesh door with a hasp and padlock, parcels and a mail sack inside. Destroyed: the door
    torn off its hinges and folded back, a side panel cut open, parcels pulled out on the floor."""
    W, D, H = 1.6, 1.0, 2.1
    fr = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            fr.append(p.box((0.04, 0.04, H), (sx * (W / 2 - 0.02), sy * (D / 2 - 0.02), H / 2), C.GALV, bevel=0.003))
    for z in (0.04, 1.05, H - 0.02):
        for sy in (-1, 1):
            fr.append(p.box((W, 0.035, 0.035), (0, sy * (D / 2 - 0.02), z), C.GALV, bevel=0.003, grain="X"))
        for sx in (-1, 1):
            fr.append(p.box((0.035, D, 0.035), (sx * (W / 2 - 0.02), 0, z), C.GALV, bevel=0.003, grain="Y"))
    mesh_kw = {"uv_scale": 2.0, "wear": 0.0}
    panels = {}
    panels["back"] = p.box((W - 0.06, 0.004, H - 0.08), (0, D / 2 - 0.02, H / 2), C.MESH, bevel=0.0, **mesh_kw)
    panels["left"] = p.box((0.004, D - 0.06, H - 0.08), (-W / 2 + 0.02, 0, H / 2), C.MESH, bevel=0.0, **mesh_kw)
    panels["right"] = p.box((0.004, D - 0.06, H - 0.08), (W / 2 - 0.02, 0, H / 2), C.MESH, bevel=0.0, **mesh_kw)
    panels["top"] = p.box((W - 0.06, D - 0.06, 0.004), (0, 0, H - 0.02), C.MESH, bevel=0.0, **mesh_kw)
    panels["front"] = p.box((W / 2 - 0.04, 0.004, H - 0.08), (-W / 4, -D / 2 + 0.02, H / 2), C.MESH, bevel=0.0, **mesh_kw)
    door = [p.box((W / 2 - 0.06, 0.004, H - 0.12), (W / 4, -D / 2 + 0.02, H / 2), C.MESH, bevel=0.0, tags=("door",), **mesh_kw)]
    for z in (0.07, H - 0.07):
        door.append(p.box((W / 2 - 0.04, 0.03, 0.03), (W / 4, -D / 2 + 0.02, z), C.GALV, bevel=0.003, tags=("door",)))
    for x in (0.03, W / 2 - 0.03):
        door.append(p.box((0.03, 0.03, H - 0.12), (x, -D / 2 + 0.02, H / 2), C.GALV, bevel=0.003, tags=("door",)))
    door.append(p.box((0.06, 0.012, 0.03), (0.04, -D / 2 - 0.0, 1.05), C.IRON, bevel=0.002, tags=("door",)))
    lock = [p.box((0.045, 0.018, 0.05), (0.03, -D / 2 - 0.02, 1.0), C.BRASS, bevel=0.004),
            p.tube([(0.015, -D / 2 - 0.02, 1.02), (0.015, -D / 2 - 0.02, 1.05), (0.045, -D / 2 - 0.02, 1.05), (0.045, -D / 2 - 0.02, 1.02)],
                   0.004, M.CHROME, segs=5, fillet_r=0.01, steps=2)]
    r = p.rng("parcels")
    z = 0.0
    stuff = []
    for i in range(7):
        sx, sy, sz = r.uniform(0.25, 0.5), r.uniform(0.2, 0.4), r.uniform(0.15, 0.35)
        x = -W / 2 + 0.3 + (i % 3) * 0.42 + r.uniform(-0.05, 0.05)
        y = 0.15 + r.uniform(-0.08, 0.1)
        zz = 0.06 if i < 3 else (0.06 + 0.36 if i < 6 else 0.75)
        stuff.append(F.package_box(p, (sx, sy, sz), (x, y, zz + sz / 2), r.choice([1, 2, 5, 7, 9, 14]), rot=(0, 0, r.uniform(-12, 12)),
                                   key=f"pk{i}"))
    sack = p.rbox((0.5, 0.36, 0.42), (0.35, -0.15, 0.27), C.CANVAS_GREY, radius=0.1, inner=(3, 3, 3), bulge=(0.03, 0.03, 0.02),
                  wrinkle=0.02, wrinkle_scale=8.0, seed=p.seed, taper_top=0.35, tags=("sack",))
    stuff.append(sack)
    if p.destroyed:
        rr = p.vrng("wreck")
        p.rotate(door + lock, rot=(0, 0, -135), pivot=(W / 2 - 0.02, -D / 2 + 0.02, 0))
        p.rotate(door + lock, rot=(0, -5, 0), pivot=(W / 2, -D / 2, H))
        G.splinter_cut(panels["left"].obj, (0, 0, 1.2), (0, 0.3, 1), jag=0.05, seed=p.seed)
        for q in stuff[:3]:
            p.lay_on_floor([q], rot=(0, 0, 0), at=(rr.uniform(-0.6, 0.3), rr.uniform(-1.1, -0.65)), yaw=rr.uniform(0, 90))
    p.collider((0, 0, H / 2), (W, D, H))


def civic_mail_cart(p: Prop) -> None:
    """Canvas mail hamper on a steel frame with casters (0.95 x 0.95 x 0.62), the bag sagging under bundled
    letters and a sack. Destroyed: tipped on its side, mail spilled across the floor."""
    W, D = 0.92, 0.6
    tz = 0.92
    fr = []
    rect = [(-W / 2, -D / 2, tz), (W / 2, -D / 2, tz), (W / 2, D / 2, tz), (-W / 2, D / 2, tz)]
    fr.append(p.tube(rect, 0.012, M.STEEL_GREY, segs=6, closed=True))
    fr.append(p.tube([(x, y, 0.16) for x, y, _ in rect], 0.012, M.STEEL_GREY, segs=6, closed=True))
    for x, y, _ in rect:
        fr.append(p.tube([(x, y, 0.16), (x, y, tz)], 0.012, M.STEEL_GREY, segs=6))
        fr.append(p.box((0.03, 0.05, 0.04), (x, y, 0.13), M.STEEL_GREY, bevel=0.004))
        fr.append(p.cyl(0.045, 0.03, (x, y + 0.02, 0.045), C.RUBBER, axis="X", segs=10))
    bag = p.hollow((W - 0.04, D - 0.04, 0.66), (0, 0, tz - 0.33), C.CANVAS_KHAKI, wall=0.008, open_face="+Z", tags=("bag",))
    for v in bag.obj.data.vertices:
        if v.co.z < tz - 0.5:
            k = (1.0 - (abs(v.co.x) / (W / 2)) ** 2) * (1.0 - (abs(v.co.y) / (D / 2)) ** 2)
            v.co.z -= 0.07 * max(0.0, k)
        if abs(v.co.x) > W / 2 - 0.05 and tz - 0.6 < v.co.z < tz - 0.05:
            v.co.x *= 0.97
    bag.obj.data.update()
    r = p.rng("mail")
    stuff = []
    for i in range(9):
        b = p.box((0.2, 0.1, 0.06), (r.uniform(-0.3, 0.3), r.uniform(-0.18, 0.18), tz - 0.12 + r.uniform(-0.05, 0.05)), C.PAPER, bevel=0.003)
        G.xform(b.obj, rot=(r.uniform(-25, 25), r.uniform(-25, 25), r.uniform(0, 180)), pivot=tuple(p.bounds([b])[0]))
        stuff.append(b)
    stuff.append(p.rbox((0.4, 0.3, 0.3), (0.12, 0.05, tz - 0.2), C.CANVAS_GREY, radius=0.08, inner=(3, 3, 2), wrinkle=0.015, seed=p.seed))
    if p.destroyed:
        whole = [q for q in p.parts if q not in stuff]
        p.rotate(whole, rot=(88, 0, 0), pivot=(0, -D / 2, 0))
        lo, hi = p.bounds(whole)
        p.move(whole, (0, 0, -lo.z))
        rr = p.vrng("spill")
        for q in stuff:
            p.lay_on_floor([q], rot=(0, 0, 0), at=(rr.uniform(-0.5, 0.5), rr.uniform(-1.6, -0.9)), yaw=rr.uniform(0, 180))
        p.collider((0, -0.4, 0.3), (1.0, 1.0, 0.6))
    else:
        p.collider((0, 0, tz / 2), (W + 0.03, D + 0.03, tz + 0.02))


def civic_mail_sacks(p: Prop) -> None:
    """Three canvas mail sacks, necks tied with cord: two lying, one slumped upright. Worn: one split open with
    letters spilling."""
    r = p.rng("sacks")
    for i, (x, y, rotz, upright) in enumerate(((-0.18, 0.0, 15, False), (0.2, 0.06, -10, False), (0.0, 0.12, 0, True))):
        if upright:
            s = p.rbox((0.32, 0.28, 0.48), (x, y, 0.24), C.CANVAS_GREY, radius=0.08, inner=(3, 3, 3), bulge=(0.03, 0.03, 0.0),
                       wrinkle=0.018, wrinkle_scale=9.0, seed=p.seed + i, taper_top=0.55, tags=("sack",))
            p.lathe([(0.05, 0.0), (0.035, 0.04), (0.05, 0.1), (0.0, 0.11)], (x, y, 0.47), C.CANVAS_GREY, segs=8)
            p.tube([(x + 0.04 * math.cos(a), y + 0.04 * math.sin(a), 0.5) for a in [k * math.pi / 5 for k in range(10)]], 0.006, C.CANVAS_KHAKI,
                   segs=4, closed=True)
        else:
            s = p.rbox((0.58, 0.3, 0.22), (x, y - 0.1, 0.11), C.CANVAS_GREY if i else C.CANVAS_NAVY, radius=0.08, inner=(4, 2, 2),
                       bulge=(0.0, 0.02, 0.03), wrinkle=0.016, wrinkle_scale=9.0, seed=p.seed + i, tags=("sack",))
            G.xform(s.obj, rot=(0, 0, rotz), pivot=(x, y, 0))
    if p.worn:
        scatter_papers(p, (0.05, -0.35, 0.0), 6, 0.2, "spill", z_step=0.0015, floor=True)
    p.collider((0, -0.02, 0.2), (0.85, 0.5, 0.4))


def civic_parcel_scale(p: Prop) -> None:
    """Counter parcel scale (surface prop): enamelled cast-iron base and column, steel platform, a round dial
    housing facing the clerk (-Y) with the 0-25 lb face, a small parcel on the plate when worn."""
    p.box((0.32, 0.36, 0.05), (0, 0, 0.025), M.STEEL_GREY, bevel=0.012, grain="X")
    p.box((0.28, 0.3, 0.015), (0, 0.02, 0.0575), M.STAINLESS, bevel=0.003, grain="X")
    p.cyl(0.03, 0.12, (0, -0.12, 0.11), M.STEEL_GREY, segs=10)
    p.cyl(0.105, 0.06, (0, -0.15, 0.24), M.STEEL_GREY, axis="Y", segs=20)
    p.cyl(0.09, 0.004, (0, -0.181, 0.24), C.PRINT, axis="Y", segs=20, uv="planar", uv_axis="Y", rect=atlas("scale_dial"))
    p.cyl(0.092, 0.003, (0, -0.186, 0.24), M.GLASS, axis="Y", segs=20)
    if p.worn:
        F.package_box(p, (0.18, 0.14, 0.1), (0.02, 0.04, 0.065 + 0.05), 7, rot=(0, 0, 12), key="parcel")
    p.collider((0, 0, 0.15), (0.34, 0.38, 0.32))


def civic_collection_mailbox(p: Prop) -> None:
    """Blue street collection box 0.56 x 1.26 x 0.56 on four short legs: arched top, a pull-down chute with a
    handle, MAIL and the collection card on the front (somebody wrote NONE under LAST PICKUP), the post-horn
    emblem and the town's name on the sides. Destroyed: knocked onto its back, the chute torn off, the mail
    spilled."""
    W, D = 0.5, 0.5
    zb = 0.14
    prof = [(-D / 2, zb), (D / 2, zb), (D / 2, 0.98)] + [(D / 2 * math.cos(a), 0.98 + 0.2 * math.sin(a)) for a in
                                                        [math.pi * i / 10 for i in range(1, 10)]] + [(-D / 2, 0.98)]
    body = p.prism(prof, W, C.MAIL_BLUE, plane="YZ", offset=-W / 2, bevel=0.01, grain="Z")
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.box((0.04, 0.04, zb + 0.02), (sx * (W / 2 - 0.04), sy * (D / 2 - 0.04), (zb + 0.02) / 2), C.MAIL_BLUE, bevel=0.004)
    plate(p, W - 0.08, 0.84, (0, -D / 2 - 0.002, zb + 0.04 + 0.42), atlas("mail_front"), t=0.003)
    for sx in (-1, 1):
        plate(p, D - 0.1, 0.84, (sx * (W / 2 + 0.002), 0.0, zb + 0.04 + 0.42), atlas("mail_side"), t=0.003, facing="+X" if sx > 0 else "-X")
    chute = [p.box((W - 0.06, 0.07, 0.17), (0, -D / 2 - 0.04, 0.86), C.MAIL_BLUE, bevel=0.01, tags=("chute",)),
             p.tube([(-0.09, -D / 2 - 0.08, 0.92), (-0.09, -D / 2 - 0.11, 0.92), (0.09, -D / 2 - 0.11, 0.92), (0.09, -D / 2 - 0.08, 0.92)],
                    0.008, M.CHROME, segs=6, fillet_r=0.02, steps=2, tags=("chute",))]
    G.xform(chute[0].obj, rot=(-12, 0, 0), pivot=(0, -D / 2, 0.78))
    del body
    if p.destroyed:
        rr = p.vrng("wreck")
        p.lay_on_floor(chute, rot=(80, 0, 0), at=(0.45, -0.75), yaw=rr.uniform(-40, 40))
        whole = [q for q in p.parts if q not in chute]
        p.rotate(whole, rot=(-90, 0, 0), pivot=(0, D / 2, 0))
        lo, hi = p.bounds(whole)
        p.move(whole, (0, 0, -lo.z))
        scatter_papers(p, (0.0, -1.5, 0.0), 12, 0.45, "mail", z_step=0.0015, floor=True)
        p.collider((0, 0.3, 0.26), (0.6, 1.3, 0.52))
    else:
        p.collider((0, 0, 0.6), (W + 0.04, D + 0.12, 1.2))


def civic_po_sign(p: Prop) -> None:
    """Painted post-office sign board for the front wall (wall prop, 1.62 x 0.3): moulded frame, green ground,
    gold lettering. Worn: a corner of the frame split away, the board slipped on one screw."""
    plate(p, 1.5, 0.25, (0, -0.02, 0.15), atlas("po_sign"), t=0.03, wear=0.4)
    fr = [p.box((1.62, 0.04, 0.04), (0, -0.02, 0.0), C.OAK_DARK, bevel=0.006, grain="X"),
          p.box((1.62, 0.04, 0.04), (0, -0.02, 0.3), C.OAK_DARK, bevel=0.006, grain="X"),
          p.box((0.04, 0.04, 0.3), (-0.79, -0.02, 0.15), C.OAK_DARK, bevel=0.006, grain="Z"),
          p.box((0.04, 0.04, 0.3), (0.79, -0.02, 0.15), C.OAK_DARK, bevel=0.006, grain="Z")]
    if p.worn:
        whole = list(p.parts)
        p.rotate(whole, rot=(0, 3, 0), pivot=(-0.7, 0, 0.25))
        p.remove([fr[3]])
    p.collider((0, -0.02, 0.15), (1.62, 0.05, 0.32))


# ================================================================================================
# GRANGE HALL
# ================================================================================================


def civic_folding_table(p: Prop) -> None:
    """Folding banquet table 1.83 x 0.76 x 0.76: beige laminate top in a steel apron, tubular U legs with
    braces and rubber feet. Worn: the shelter's coffee urn, paper cups, a first-aid tin and a roster.
    Destroyed: one leg folded under, the table collapsed to the floor at that end."""
    L, D, H = 1.83, 0.76, 0.76
    top = [p.box((L, D, 0.025), (0, 0, H - 0.0125), M.LAMINATE, bevel=0.004, grain="X", tags=("top",))]
    for sy in (-1, 1):
        top.append(p.box((L, 0.012, 0.05), (0, sy * (D / 2 - 0.006), H - 0.05), M.STEEL_BEIGE, bevel=0.002, grain="X", tags=("top",)))
    for sx in (-1, 1):
        top.append(p.box((0.012, D, 0.05), (sx * (L / 2 - 0.006), 0, H - 0.05), M.STEEL_BEIGE, bevel=0.002, grain="Y", tags=("top",)))
    legs = {}
    for sx in (-1, 1):
        x = sx * (L / 2 - 0.18)
        grp = [p.tube([(x, -0.3, 0.02), (x, -0.3, H - 0.07), (x, 0.3, H - 0.07), (x, 0.3, 0.02)], 0.013, M.STEEL_GREY, segs=6, fillet_r=0.04,
                      tags=("leg",))]
        grp.append(p.tube([(x, 0.0, 0.25), (x - sx * 0.25, 0.0, H - 0.07)], 0.009, M.STEEL_GREY, segs=5, tags=("leg",)))
        grp.append(p.tube([(x, -0.3, 0.25), (x, 0.3, 0.25)], 0.009, M.STEEL_GREY, segs=5, tags=("leg",)))
        for sy in (-1, 1):
            grp.append(p.cyl(0.016, 0.03, (x, sy * 0.3, 0.015), C.RUBBER, segs=8, tags=("leg",)))
        legs[sx] = grp
    items = []
    if p.worn and not p.destroyed:
        items.append(p.lathe([(0.0, 0.0), (0.13, 0.0), (0.13, 0.04), (0.12, 0.05), (0.12, 0.42), (0.13, 0.45), (0.06, 0.5), (0.0, 0.52)],
                             (-0.6, 0.12, H), M.STAINLESS, segs=14))
        items.append(p.box((0.03, 0.05, 0.03), (-0.6, -0.02, H + 0.08), M.PL_BLACK, bevel=0.004))
        for i in range(4):
            items.append(p.lathe([(0.0, 0.0), (0.028, 0.0), (0.036, 0.09), (0.034, 0.09), (0.026, 0.004), (0.0, 0.004)],
                                 (-0.35 + i * 0.01, 0.15, H + i * 0.012), M.PL_WHITE, segs=8, cap_top=False))
        items.append(p.box((0.24, 0.16, 0.08), (0.3, 0.05, H + 0.04), C.PAINT_RED, bevel=0.01))
        items += scatter_papers(p, (0.6, -0.1, H), 2, 0.05, "roster")
    if p.destroyed:
        p.rotate(legs[1], rot=(0, -80, 0), pivot=(L / 2 - 0.18, 0, H - 0.07))
        whole = list(p.parts)
        p.rotate(whole, rot=(0, -23, 0), pivot=(-L / 2 + 0.18, 0, 0))
        lo, hi = p.bounds(whole)
        p.move(whole, (0, 0, -lo.z))
        p.collider((0, 0, 0.42), (L, D, 0.84))
    else:
        p.collider((0, 0, H / 2), (L, D, H))


def civic_folding_chair(p: Prop) -> None:
    """Steel folding chair (0.45 x 0.8): beige enamel tube frame, pressed-steel seat and back, rubber feet.
    Destroyed: folded flat on the floor."""
    paint = M.STEEL_BEIGE
    parts = []
    for sx in (-1, 1):
        x = sx * 0.2
        parts.append(p.tube([(x, -0.2, 0.0), (x, 0.13, 0.62), (x, 0.17, 0.8)], 0.011, paint, segs=6, fillet_r=0.05))
        parts.append(p.tube([(x * 0.92, 0.22, 0.0), (x * 0.92, -0.08, 0.44)], 0.01, paint, segs=6))
        parts.append(p.cyl(0.014, 0.02, (x, -0.2, 0.01), C.RUBBER, segs=6))
        parts.append(p.cyl(0.013, 0.02, (x * 0.92, 0.22, 0.01), C.RUBBER, segs=6))
    parts.append(p.tube([(-0.2, -0.02, 0.2), (0.2, -0.02, 0.2)], 0.008, paint, segs=5))
    seat = p.rbox((0.4, 0.38, 0.03), (0, 0.01, 0.45), paint, radius=0.012, inner=(3, 3, 1), bulge=(0, 0, -0.005), edge_deg=30)
    back = p.rbox((0.42, 0.025, 0.15), (0, 0.15, 0.72), paint, radius=0.01, inner=(3, 1, 2), bulge=(0, 0.006, 0), edge_deg=30)
    G.xform(back.obj, rot=(-8, 0, 0), pivot=(0, 0.15, 0.65))
    parts += [seat, back]
    if p.destroyed:
        p.lay_on_floor(parts, rot=(-90, 0, 0), at=(0.0, 0.0), yaw=p.vrng("y").uniform(-40, 40))
        p.collider((0, 0, 0.05), (0.5, 0.9, 0.1))
    else:
        p.collider((0, 0.02, 0.4), (0.46, 0.48, 0.8))


def civic_army_cot(p: Prop) -> None:
    """Army surplus folding cot (0.75 x 1.95, canvas bed 0.44 up): wooden side rails, three X-leg frames,
    end bars, sagging olive canvas, a grey wool blanket, a pillow and a manila cot tag on the foot bar
    ('COT 23 - M. Okafor + 2'). Worn: the blanket thrown back half onto the floor. Destroyed: the canvas
    torn, an X frame folded and the cot down at one end."""
    W, L, H = 0.68, 1.9, 0.44
    frame = []
    for sx in (-1, 1):
        frame.append(p.cyl(0.018, L, (sx * W / 2, 0, H), C.OAK, axis="Y", segs=8, tags=("frame",)))
    for sy in (-1, 1):
        frame.append(p.tube([(-W / 2, sy * L / 2 * 0.98, H), (W / 2, sy * L / 2 * 0.98, H)], 0.014, C.OAK, segs=6, tags=("frame",)))
    xs = {}
    for k, y in enumerate((-0.8, 0.0, 0.8)):
        grp = [p.tube([(-W / 2 + 0.02, y, H - 0.02), (W / 2 - 0.02, y, 0.01)], 0.011, C.GALV, segs=6, tags=("legs",)),
               p.tube([(W / 2 - 0.02, y, H - 0.02), (-W / 2 + 0.02, y, 0.01)], 0.011, C.GALV, segs=6, tags=("legs",)),
               p.tube([(-W / 2 + 0.02, y, 0.012), (W / 2 - 0.02, y, 0.012)], 0.009, C.GALV, segs=5, tags=("legs",))]
        xs[k] = grp
    canvas = p.rbox((W - 0.02, L - 0.06, 0.012), (0, 0, H + 0.004), C.CANVAS_OLIVE, radius=0.005, inner=(4, 10, 1), sag=0.05, sag_r=0.7,
                    tags=("canvas",))
    bed = []
    if not p.destroyed:
        hang = (0.14, 0.14, 0.0, 0.05) if p.cond == "clean" else (0.12, 0.3, 0.0, 0.0)
        y0 = -L / 2 + 0.2 if p.cond == "clean" else -L / 2 + 0.6
        bed.append(F.drape(p, -W / 2 + 0.02, W / 2 - 0.02, y0, L / 2 - 0.45, H + 0.02, C.WOOL_GREY, hang=hang, res=0.11, wrinkle=0.012,
                           seed=p.seed, thickness=0.008, floor=0.0, uv_scale=1.0))
        bed.append(p.rbox((0.5, 0.32, 0.12), (0, L / 2 - 0.25, H + 0.07), M.LINEN, radius=0.05, inner=(3, 2, 1), bulge=(0, 0, 0.02),
                          wrinkle=0.008, seed=p.seed + 3, taper_top=0.15))
    plate(p, 0.1, 0.05, (0.12, -L / 2 * 0.98 - 0.016, H - 0.035), atlas("cot_tag"), t=0.002, rot=(0, 6, 0))
    if p.worn and not p.destroyed:
        p.rbox((0.42, 0.3, 0.2), (-0.12, -0.4, 0.1), C.CANVAS_NAVY, radius=0.06, inner=(2, 2, 1), wrinkle=0.01, seed=p.seed + 9)
    if p.destroyed:
        G.splinter_cut(canvas.obj, (0, 0.1, 0), (0, 1, 0), jag=0.08, seed=p.seed)
        flap = p.rbox((W - 0.02, 0.8, 0.012), (0, 0.5, H), C.CANVAS_OLIVE, radius=0.005, inner=(4, 4, 1), wrinkle=0.01, seed=p.seed + 1)
        G.xform(flap.obj, rot=(-60, 0, 0), pivot=(0, 0.1, H))
        p.rotate(xs[2], rot=(70, 0, 0), pivot=(0, 0.8, H))
        whole = list(p.parts)
        p.rotate(whole, rot=(-13, 0, 0), pivot=(0, -0.8, 0))
        lo, hi = p.bounds(whole)
        p.move(whole, (0, 0, -lo.z))
    p.collider((0, 0, 0.25), (W + 0.06, L + 0.04, 0.5))


def civic_relief_crate(p: Prop) -> None:
    """Relief-supply crate 0.9 x 0.55 x 0.55 (olive planks, corner battens, rope handles, stencilled
    EMERGENCY RELIEF / SAWBACK COUNTY with a white-on-green first-aid cross). Worn: lid pried off and leaning
    against it, folded blankets and bottled water inside. Destroyed: the front stove in, contents spilled."""
    W, D, H = 0.9, 0.55, 0.52
    wood = C.CRATE
    sides = {}
    sides["front"] = p.box((W, 0.022, H), (0, -D / 2 + 0.011, H / 2), wood, bevel=0.003, grain="X")
    sides["back"] = p.box((W, 0.022, H), (0, D / 2 - 0.011, H / 2), wood, bevel=0.003, grain="X")
    for sx in (-1, 1):
        p.box((0.022, D - 0.044, H), (sx * (W / 2 - 0.011), 0, H / 2), wood, bevel=0.003, grain="Y")
    p.box((W - 0.044, D - 0.044, 0.02), (0, 0, 0.03), wood, bevel=0.002, grain="X")
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.box((0.05, 0.05, H + 0.01), (sx * (W / 2 - 0.004), sy * (D / 2 - 0.004), H / 2), wood, bevel=0.004, grain="Z")
    for sy in (-1, 1):
        for z in (0.06, H - 0.06):
            p.box((W - 0.1, 0.02, 0.05), (0, sy * (D / 2 + 0.008), z), wood, bevel=0.003, grain="X")
    front_plate = plate(p, 0.6, 0.3, (0, -D / 2 - 0.02, H / 2), atlas("relief_side"), t=0.002)
    plate(p, 0.6, 0.3, (0, D / 2 + 0.02, H / 2), atlas("relief_side"), t=0.002, facing="+Y")
    for sx in (-1, 1):
        plate(p, 0.42, 0.21, (sx * (W / 2 + 0.001), 0, H / 2 + 0.05), atlas("relief_end"), t=0.002, facing="+X" if sx > 0 else "-X")
        loop = [(sx * (W / 2 + 0.03), 0.08 * math.cos(a), H * 0.6 + 0.05 * math.sin(a)) for a in [math.pi * (1 + i / 6) for i in range(7)]]
        p.tube([(sx * (W / 2 + 0.005), -0.08, H * 0.6)] + loop + [(sx * (W / 2 + 0.005), 0.08, H * 0.6)], 0.009, C.CANVAS_KHAKI, segs=5)
    lid = [p.box((W + 0.02, D + 0.02, 0.025), (0, 0, H + 0.0125), wood, bevel=0.003, grain="X", tags=("lid",))]
    lid.append(plate(p, 0.52, 0.26, (0, 0, H + 0.026), atlas("relief_lid"), t=0.002, facing="+Z", tags=("lid",)))
    if p.worn or p.destroyed:
        r = p.rng("contents")
        fold_blanket(p, (-0.18, 0.0, 0.04), (0.4, 0.42, 0.18), C.WOOL_GREY, yaw=0, key="bl1")
        fold_blanket(p, (-0.18, 0.0, 0.22), (0.38, 0.4, 0.15), C.WOOL_OLIVE, yaw=4, key="bl2")
        for i in range(3):
            for j in range(2):
                bottle(p, 1, (0.12 + i * 0.1, -0.1 + j * 0.2, 0.04), label=None, scale=1.05, key=f"w{i}{j}")
        del r
        if p.cond == "worn":
            p.rotate(lid, rot=(-76, 0, 0), pivot=(0, -D / 2 - 0.02, 0.0))
            p.move(lid, (0, -0.32, 0.0))
            lo, hi = p.bounds(lid)
            p.move(lid, (0, 0, -lo.z))
    if p.destroyed:
        rr = p.vrng("wreck")
        p.remove([sides["front"], front_plate])
        a, b = F.split_panel(p, W, H, 0.022, (0, -D / 2 + 0.011, H / 2), wood, (-0.45, 0.06), (0.45, -0.1), key="front")
        G.xform(b.obj, rot=(70, 0, 0), pivot=(0, -D / 2, 0.0))
        p.lay_on_floor(lid, rot=(0, 0, 0), at=(0.3, 0.75), yaw=rr.uniform(-30, 30))
    p.collider((0, 0, H / 2 + 0.01), (W + 0.06, D + 0.06, H + 0.04))


def civic_stage_lectern(p: Prop) -> None:
    """Stage lectern 0.62 x 1.24 x 0.52: mahogany podium flaring toward a slanted reading desk with a lip, a
    raised front panel with the grange's gilt No. 412 plate, a gooseneck microphone. Worn: the speech left
    on it and a glass of water. Destroyed: knocked over on its side, the microphone snapped."""
    wood = C.MAHOGANY
    p.box((0.62, 0.52, 0.06), (0, 0, 0.03), C.OAK_DARK, bevel=0.008, grain="X")
    body = G.loft(p._name("podium"), [G.rrect_ring(0.5, 0.42, 0.02, 0.06, n=2), G.rrect_ring(0.58, 0.46, 0.02, 1.02, n=2)], cap_bottom=True,
                  cap_top=True)
    p.add(body, wood, grain="Z", edge_deg=20)
    p.panel(0.4, 0.62, 0.016, (0, -0.226, 0.56), wood, style="raised", frame=0.05, tags=("panel",))
    banner = ATLAS["banner"]
    rect = core._px_rect(banner[0] + 130, banner[1] + 64, banner[0] + 382, banner[1] + 104)
    plate(p, 0.3, 0.05, (0, -0.236, 0.84), rect, t=0.003)
    desk = [p.box((0.64, 0.5, 0.03), (0, 0.0, 1.06), wood, bevel=0.006, grain="X"),
            p.box((0.64, 0.025, 0.04), (0, -0.25, 1.085), C.OAK_DARK, bevel=0.004, grain="X")]
    p.rotate(desk, rot=(14, 0, 0), pivot=(0, 0.25, 1.04))
    mic = [p.tube([(0.22, 0.12, 1.1), (0.22, 0.1, 1.28), (0.16, -0.05, 1.38), (0.1, -0.12, 1.36)], 0.008, M.PL_BLACK, segs=6, fillet_r=0.08),
           p.lathe([(0.0, 0.0), (0.02, 0.0), (0.024, 0.04), (0.02, 0.07), (0.0, 0.075)], (0.1, -0.13, 1.32), M.CHROME, segs=8)]
    if p.worn and not p.destroyed:
        scatter_papers(p, (-0.05, 0.02, 1.08), 3, 0.03, "speech")
        for q in p.parts[-3:]:
            G.xform(q.obj, rot=(14, 0, 0), pivot=(0, 0.25, 1.04))
        glass_tumbler(p, (-0.24, 0.17, 1.075), key="water")
    if p.destroyed:
        G.splinter_cut(mic[0].obj, (0.2, 0.05, 1.25), (0, -0.3, 1), jag=0.01, seed=p.seed)
        whole = list(p.parts)
        p.rotate(whole, rot=(0, 90, 15), pivot=(0, 0, 0))
        lo, hi = p.bounds(whole)
        p.move(whole, (0, 0, -lo.z))
        p.collider((0, 0, 0.3), (1.3, 0.7, 0.6))
    else:
        p.collider((0, 0, 0.62), (0.64, 0.54, 1.24))


def _coat(p: Prop, hook, mat: str, length: float, key: str) -> list:
    hx, hy, hz = hook
    body = p.rbox((0.4, 0.16, length), (0, 0, 0), mat, radius=0.06, inner=(2, 2, 4), bulge=(0.0, 0.02, 0.0), wrinkle=0.012, wrinkle_scale=8.0,
                  seed=len(key) * 7, taper_top=0.45, tags=("coat", key))
    me = body.obj.data
    for v in me.vertices:  # hanging folds: hem flares, shoulders slope
        t = (v.co.z + length / 2) / length
        v.co.x *= 1.0 + 0.12 * (1.0 - t)
        v.co.y += 0.02 * math.sin(v.co.x * 18.0) * (1.0 - t)
    me.update()
    G.xform(body.obj, loc=(hx, hy + 0.06, hz - length / 2 - 0.02))
    collar = p.rbox((0.2, 0.12, 0.06), (hx, hy + 0.04, hz - 0.03), mat, radius=0.03, inner=(2, 1, 1), wrinkle=0.006, seed=3, tags=("coat", key))
    return [body, collar]


def civic_coat_rack(p: Prop) -> None:
    """Bentwood coat tree 1.85 m: turned pole, four sweeping feet, an umbrella ring, six curled hooks, a
    barn coat, a flannel jacket and an army greatcoat left on it, a felt hat on top. Destroyed: knocked over,
    the coats in a heap."""
    wood = C.OAK_DARK
    p.lathe([(0.03, 0.0), (0.026, 0.05), (0.022, 1.6), (0.03, 1.7), (0.024, 1.78), (0.035, 1.82), (0.0, 1.86)], (0, 0, 0.1), wood, segs=10)
    for k in range(4):
        a = math.radians(45 + 90 * k)
        p.tube([(0.0, 0.0, 0.42), (math.cos(a) * 0.1, math.sin(a) * 0.1, 0.25), (math.cos(a) * 0.26, math.sin(a) * 0.26, 0.03),
                (math.cos(a) * 0.32, math.sin(a) * 0.32, 0.02)], 0.016, wood, segs=6, fillet_r=0.12, steps=4)
    p.tube([(0.17 * math.cos(math.radians(t)), 0.17 * math.sin(math.radians(t)), 0.5) for t in range(0, 360, 30)], 0.009, wood, segs=5,
           closed=True)
    for k in range(4):
        a = math.radians(45 + 90 * k)
        p.tube([(0, 0, 0.55), (math.cos(a) * 0.17, math.sin(a) * 0.17, 0.5)], 0.008, wood, segs=4)
    hooks = []
    for k in range(6):
        a = math.radians(k * 60 + 15)
        c, s_ = math.cos(a), math.sin(a)
        p.tube([(0.0, 0.0, 1.66), (c * 0.08, s_ * 0.08, 1.62), (c * 0.17, s_ * 0.17, 1.66), (c * 0.2, s_ * 0.2, 1.74), (c * 0.17, s_ * 0.17, 1.79)],
               0.011, wood, segs=4, fillet_r=0.05, steps=3)
        hooks.append((c * 0.15, s_ * 0.15, 1.63))
    coats = []
    coats += _coat(p, hooks[0], C.CANVAS_KHAKI, 0.95, "barn")
    coats += _coat(p, hooks[2], C.FLANNEL, 0.7, "flannel")
    coats += _coat(p, hooks[4], C.WOOL_OLIVE, 1.1, "greatcoat")
    hat = [p.lathe([(0.0, 0.0), (0.17, 0.0), (0.17, 0.01), (0.1, 0.02), (0.095, 0.12), (0.06, 0.135), (0.0, 0.13)], (0, 0, 1.92), C.WOOL_BROWN,
                   segs=14)]
    if p.destroyed:
        whole = [q for q in p.parts if q not in coats + hat]
        p.rotate(whole, rot=(0, 86, 30), pivot=(0, 0, 0))
        lo, hi = p.bounds(whole)
        p.move(whole, (0, 0, -lo.z))
        p.lay_on_floor(coats, rot=(90, 0, 0), at=(0.5, -0.3), yaw=40)
        p.lay_on_floor(hat, rot=(0, 0, 0), at=(-0.6, 0.4))
        p.collider((0.3, 0, 0.15), (1.9, 0.8, 0.3))
    else:
        p.collider((0, 0, 0.95), (0.6, 0.6, 1.9))


def civic_upright_piano(p: Prop) -> None:
    """Upright piano 1.52 x 1.3 x 0.62 in ebonised case: 88 keys in yellowed ivory and ebony, key slip and
    cheeks, a fallboard with gilt 'Harwick & Sons - Portland', a fret-panelled upper front with brass swing
    candle sconces, music desk with sheet music, turned front legs on toe blocks, three brass pedals. Worn:
    lid propped, fallboard open, a few keys dead. Destroyed: the fallboard ripped off onto the floor, keys
    smashed out, the lower panel stove in."""
    W, D = 1.52, 0.62
    case = C.PIANO
    for sx in (-1, 1):
        p.box((0.05, D, 1.3), (sx * (W / 2 - 0.025), 0, 0.65), case, bevel=0.006, grain="Z")
    p.box((W - 0.1, 0.06, 1.25), (0, D / 2 - 0.03, 0.66), case, bevel=0.004, grain="Z")
    lidp = [p.box((W + 0.02, D - 0.1, 0.03), (0, 0.05, 1.315), case, bevel=0.008, grain="X", tags=("lid",))]
    up = p.panel(W - 0.1, 0.5, 0.025, (0, -D / 2 + 0.17, 1.03), case, style="raised", frame=0.08, recess=0.008, tags=("panel",))
    del up
    low = p.panel(W - 0.1, 0.42, 0.025, (0, -D / 2 + 0.1, 0.36), case, style="raised", frame=0.07, recess=0.006, tags=("panel",))
    kz = 0.7
    p.box((W - 0.1, 0.32, 0.06), (0, -D / 2 + 0.14, kz - 0.03), case, bevel=0.004, grain="X")
    for sx in (-1, 1):
        p.box((0.07, 0.32, 0.14), (sx * (W / 2 - 0.085), -D / 2 + 0.16, kz + 0.04), case, bevel=0.008, grain="Y")
        p.lathe([(0.04, 0.0), (0.045, 0.04), (0.03, 0.1), (0.028, 0.4), (0.038, 0.47), (0.045, 0.6), (0.0, 0.61)],
                (sx * (W / 2 - 0.09), -D / 2 + 0.04, 0.03), case, segs=10)
        p.box((0.1, 0.2, 0.03), (sx * (W / 2 - 0.09), -D / 2 + 0.08, 0.015), case, bevel=0.006)
    p.box((W - 0.24, 0.025, 0.05), (0, -D / 2 + 0.0, kz - 0.02), case, bevel=0.003, grain="X")
    keys = []
    rk = p.vrng("keys")
    n_white = 52
    kw_ = (W - 0.26) / n_white
    x0 = -n_white * kw_ / 2
    for i in range(n_white):
        sink = -0.008 if (p.worn and rk.random() < 0.05) else 0.0
        keys.append(p.box((kw_ - 0.0015, 0.15, 0.022), (x0 + (i + 0.5) * kw_, -D / 2 + 0.1, kz + 0.011 + sink), C.IVORY, bevel=0.0, tags=("key",)))
    pattern = [1, 0, 1, 1, 0, 1, 1]  # A-B-C... starting on A: A# after A, none after B, C# D# ...
    for i in range(n_white - 1):
        if pattern[i % 7]:
            keys.append(p.box((0.012, 0.09, 0.02), (x0 + (i + 1) * kw_, -D / 2 + 0.125, kz + 0.03), C.EBONY, bevel=0.0, tags=("key",)))
    fall = [p.box((W - 0.24, 0.12, 0.018), (0, 0, 0), case, bevel=0.004, grain="X", tags=("fall",))]
    fall.append(plate(p, 0.42, 0.035, (0, -0.062, 0.0), atlas("fallboard"), t=0.002, tags=("fall",)))
    if p.cond == "clean":
        p.rotate(fall, rot=(-90, 0, 0), pivot=(0, 0, 0))
        p.move(fall, (0, -D / 2 + 0.1, kz + 0.06))
    else:
        p.move(fall, (0, -D / 2 + 0.19, kz + 0.2))
        p.rotate(fall, rot=(-12, 0, 0), pivot=(0, -D / 2 + 0.2, kz + 0.12))
    desk = [p.box((0.6, 0.02, 0.22), (0, -D / 2 + 0.2, kz + 0.38), case, bevel=0.003, grain="X")]
    sheet = p.box((0.42, 0.003, 0.3), (0, -D / 2 + 0.185, kz + 0.43), M.PAPER, bevel=0.0, uv="keep")
    core.set_face_uvs(sheet.obj, lambda poly: (*core.note_rect(1), 0, 2, False))
    p.rotate(desk + [sheet], rot=(-10, 0, 0), pivot=(0, -D / 2 + 0.2, kz + 0.27))
    for sx in (-1, 1):
        x = sx * 0.58
        p.box((0.06, 0.012, 0.08), (x, -D / 2 + 0.155, kz + 0.45), C.BRASS, bevel=0.004)
        p.tube([(x, -D / 2 + 0.15, kz + 0.45), (x + sx * 0.06, -D / 2 + 0.06, kz + 0.42), (x + sx * 0.1, -D / 2 + 0.02, kz + 0.43)], 0.007,
               C.BRASS, segs=5, fillet_r=0.03)
        p.lathe([(0.0, 0.0), (0.035, 0.0), (0.03, 0.015), (0.015, 0.02), (0.013, 0.04), (0.0, 0.041)], (x + sx * 0.1, -D / 2 + 0.02, kz + 0.43),
                C.BRASS, segs=8)
        candle(p, (x + sx * 0.1, -D / 2 + 0.02, kz + 0.47), 0.12, 0.012, burnt=p.worn, key=f"sc{sx}")
    for i, x in enumerate((-0.12, 0.0, 0.12)):
        p.box((0.035, 0.12, 0.02), (x, -D / 2 - 0.02, 0.07), C.BRASS, bevel=0.005)
    p.box((0.5, 0.06, 0.1), (0, -D / 2 + 0.03, 0.05), case, bevel=0.005, grain="X")
    if p.worn and not p.destroyed:
        p.rotate(lidp, rot=(-12, 0, 0), pivot=(0, D / 2 - 0.05, 1.33))
    if p.destroyed:
        rr = p.vrng("wreck")
        p.lay_on_floor(fall, rot=(90, 0, 0), at=(0.35, -D / 2 - 0.55), yaw=rr.uniform(-20, 20))
        for q in keys[18:30]:
            if rr.random() < 0.6:
                p.lay_on_floor([q], rot=(rr.uniform(-30, 30), 0, 0), at=(rr.uniform(-0.6, 0.6), rr.uniform(-1.0, -0.5)), yaw=rr.uniform(0, 180))
        p.remove([low])
        a, b = F.split_panel(p, W - 0.1, 0.42, 0.025, (0, -D / 2 + 0.1, 0.36), case, (-0.4, -0.21), (0.3, 0.21), key="low")
        G.xform(b.obj, rot=(18, 0, 0), pivot=(0, -D / 2 + 0.1, 0.15))
    p.collider((0, 0, 0.66), (W, D + 0.04, 1.32))


def civic_trophy_case(p: Prop) -> None:
    """Grange trophy case 1.2 x 1.9 x 0.45: oak base cabinet with doors under a glazed upper case, three glass
    shelves of brass cups and figurines, engraved plaques on walnut shields, the 1987 crew photo, a ribbon
    rosette. Worn: dust, a cup toppled. Destroyed: the glass smashed out, trophies on the floor, a shelf
    down."""
    W, D = 1.2, 0.42
    wood = C.OAK
    F.carcass(p, W, -D / 2, D / 2, 0.06, 0.62, wood, rails=())
    p.box((W + 0.04, D + 0.04, 0.06), (0, 0, 0.03), C.OAK_DARK, bevel=0.006, grain="X")
    for i, (x0, x1) in enumerate(((-W / 2 + 0.05, -0.01), (0.01, W / 2 - 0.05))):
        F.door(p, x0, 0.1, x1, 0.58, -D / 2 - 0.02, wood, style="raised", hinge="left" if i == 0 else "right", handle="knob", handle_mat=C.BRASS,
               key=f"bd{i}")
    p.box((W + 0.04, D + 0.02, 0.04), (0, 0, 0.64), C.OAK_DARK, bevel=0.006, grain="X")
    uz0, uz1 = 0.66, 1.84
    for sx in (-1, 1):
        p.box((0.04, D - 0.04, uz1 - uz0), (sx * (W / 2 - 0.02), 0.0, (uz0 + uz1) / 2), wood, bevel=0.004, grain="Z")
    p.box((W, 0.02, uz1 - uz0), (0, D / 2 - 0.03, (uz0 + uz1) / 2), C.OAK_DARK, bevel=0.002, grain="Z")
    p.box((W + 0.06, D + 0.04, 0.06), (0, 0, uz1 + 0.03), C.OAK_DARK, bevel=0.01, grain="X")
    p.box((W + 0.1, D + 0.08, 0.03), (0, 0, uz1 + 0.075), wood, bevel=0.008, grain="X")
    shelves = []
    for z in (1.02, 1.42):
        shelves.append(p.box((W - 0.08, D - 0.08, 0.008), (0, 0.0, z), M.GLASS, bevel=0.0))
    r = p.rng("trophies")
    lose = p.vrng("fall")
    trophies = []
    for k, z in enumerate((0.68, 1.024, 1.424)):
        x = -W / 2 + 0.12
        while x < W / 2 - 0.12:
            kind = r.choice(["cup", "cup", "figure", "plaque"])
            if kind == "cup":
                h = r.uniform(0.18, 0.32)
                grp = [p.lathe([(0.0, 0.0), (0.05, 0.0), (0.05, 0.03), (0.02, 0.05), (0.015, h * 0.45), (0.05, h * 0.6), (0.075, h), (0.068, h),
                                (0.0, h * 0.62)], (x, 0.0, z), C.BRASS, segs=8)]
                for sx in (-1, 1):
                    grp.append(p.tube([(x + sx * 0.06, 0.0, z + h * 0.92), (x + sx * 0.1, 0.0, z + h * 0.8), (x + sx * 0.05, 0.0, z + h * 0.6)], 0.006,
                                      C.BRASS, segs=4, fillet_r=0.02, steps=2))
            elif kind == "figure":
                grp = [p.box((0.07, 0.07, 0.05), (x, 0.0, z + 0.025), C.MARBLE, bevel=0.004),
                       p.box((0.03, 0.03, 0.12), (x, 0.0, z + 0.11), C.BRASS, bevel=0.004),
                       sphere(p, 0.025, (x, 0.0, z + 0.2), C.BRASS, segs=6, rings=4)]
            else:
                grp = [p.box((0.16, 0.03, 0.2), (x, 0.08, z + 0.1), C.MAHOGANY, bevel=0.01)]
                grp.append(plate(p, 0.12, 0.03, (x, 0.064, z + 0.12), atlas("plaques", r.randrange(3)), t=0.002))
                G.xform(grp[0].obj, rot=(-12, 0, 0), pivot=(x, 0.1, z))
                G.xform(grp[1].obj, rot=(-12, 0, 0), pivot=(x, 0.1, z))
            if (p.worn and lose.random() < 0.15) or (p.destroyed and lose.random() < 0.5):
                p.lay_on_floor(grp, rot=(90, 0, 0), at=(x, 0.0 if not p.destroyed else -D / 2 - 0.4 - lose.uniform(0, 0.4)),
                               yaw=lose.uniform(0, 180), z=z if not p.destroyed else 0.0)
            trophies += grp
            x += r.uniform(0.18, 0.26)
    photo = plate(p, 0.24, 0.24, (0.32, D / 2 - 0.06, 1.62), atlas("photo"), t=0.012)
    G.xform(photo.obj, rot=(-8, 0, 0), pivot=(0.32, D / 2 - 0.06, 1.5))
    p.lathe([(0.0, 0.0), (0.05, 0.0), (0.0, 0.004)], (-0.35, D / 2 - 0.045, 1.62), C.FELT_RED, segs=10, axis="-Y")
    for i, x in enumerate((-W / 4, W / 4)):
        if p.destroyed:
            F.shatter_pane(p, W / 2 - 0.06, uz1 - uz0 - 0.08, (x, -D / 2 + 0.01, (uz0 + uz1) / 2), M.GLASS, t=0.004, key=f"g{i}", spokes=9, rings=3,
                           missing_inner=0.95, missing_outer=0.5)
        else:
            p.box((W / 2 - 0.06, 0.004, uz1 - uz0 - 0.08), (x, -D / 2 + 0.01, (uz0 + uz1) / 2), M.GLASS, bevel=0.0)
        for z in (uz0 + 0.02, uz1 - 0.02):
            p.box((W / 2 - 0.02, 0.025, 0.03), (x, -D / 2 + 0.01, z), C.OAK_DARK, bevel=0.003, grain="X")
        for xx in (x - W / 4 + 0.02, x + W / 4 - 0.02):
            p.box((0.03, 0.025, uz1 - uz0), (xx, -D / 2 + 0.01, (uz0 + uz1) / 2), C.OAK_DARK, bevel=0.003, grain="Z")
    if p.destroyed:
        G.xform(shelves[0].obj, rot=(0, 14, 0), pivot=(-W / 2 + 0.04, 0, 1.02))
    p.collider((0, 0, 0.95), (W + 0.1, D + 0.08, 1.9))


def civic_grange_banner(p: Prop) -> None:
    """Grange banner (wall, 1.7 x 0.6): maroon felt with gilt lettering and border, gold fringe, on a turned
    rod with finials hung by a cord. Worn: a corner torn and curling, the cloth sagging."""
    bw, bh = 1.6, 0.4
    nx, nz = 16, 4
    bm = bmesh.new()
    grid = []
    rr = p.rng("wave")
    torn = p.worn
    for i in range(nx + 1):
        col = []
        for j in range(nz + 1):
            u, v = i / nx, j / nz
            x = (u - 0.5) * bw
            z = 0.5 - bh * (1.0 - v) - 0.02
            y = -0.025 - 0.012 * math.sin(u * math.pi * 3 + rr.uniform(0, 0.2)) * (1.0 - v)
            if torn and u > 0.85 and v < 0.35:
                y -= 0.05 * (u - 0.85) / 0.15 * (0.35 - v) / 0.35
                z += 0.04 * (u - 0.85) / 0.15
            col.append(bm.verts.new((x, y, z)))
        grid.append(col)
    uvl = bm.loops.layers.uv.new("UVMap")
    u0, v0, u1, v1 = atlas("banner")
    for i in range(nx):
        for j in range(nz):
            f = bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
            for loop in f.loops:
                vi = loop.vert
                for ii in (i, i + 1):
                    for jj in (j, j + 1):
                        if grid[ii][jj] is vi:
                            loop[uvl].uv = (u0 + (ii / nx) * (u1 - u0), v0 + (jj / nz) * (v1 - v0))
    bmesh.ops.solidify(bm, geom=list(bm.faces), thickness=0.004)
    # solidify emits the far side's elements in a run-dependent order
    EK.canon_bm(bm)
    obj = common.mesh_from_bmesh(p._name("banner"), bm)
    EK.canon_loops(obj.data)
    p.add(obj, C.PRINT, uv="keep", wear=0.3, edge_deg=50)
    p.cyl(0.015, 1.72, (0, -0.03, 0.5), C.OAK_DARK, axis="X", segs=8)
    for sx in (-1, 1):
        sphere(p, 0.025, (sx * 0.87, -0.03, 0.5), C.BRASS, segs=8, rings=4)
    p.tube([(-0.84, -0.03, 0.5), (0.0, -0.01, 0.7), (0.84, -0.03, 0.5)], 0.003, C.CANVAS_KHAKI, segs=4)
    for i in range(40):
        x = -bw / 2 + 0.02 + i * (bw - 0.04) / 39
        if torn and x > bw * 0.35:
            continue
        p.box((0.006, 0.004, 0.04), (x, -0.03, 0.5 - bh - 0.04), C.BRASS, bevel=0.0)
    p.collider((0, -0.03, 0.35), (1.76, 0.06, 0.4))


def civic_shelter_board(p: Prop) -> None:
    """The shelter's roll-call letter board (wall, 0.5 x 0.86): black felt with white letters - SHELTER /
    BEDS 64 / TAKEN 61 / SICK BAY UP / BUS 0900 / BUS 0900 / BUS ???? - in an oak frame. Worn: a sign-up
    sheet pinned to the frame."""
    p.box((0.5, 0.03, 0.86), (0, -0.015, 0.43), C.OAK_DARK, bevel=0.006, grain="Z")
    plate(p, 0.42, 0.74, (0, -0.032, 0.43), atlas("felt_board"), t=0.004)
    if p.worn:
        sh = plate(p, 0.2, 0.26, (0.2, -0.04, 0.24), atlas("ledger"), t=0.001, rot=(0, -9, 0))
        del sh
        p.cyl(0.006, 0.01, (0.17, -0.045, 0.36), C.PAINT_RED, axis="Y", segs=6)
    p.collider((0, -0.02, 0.43), (0.5, 0.05, 0.86))


def civic_blanket_pile(p: Prop) -> None:
    """Shelter bedding: three folded army blankets and a pillow (clutter). Worn: the top blanket shaken out
    and slumped over the stack."""
    z = 0.0
    for i, mat in enumerate((C.WOOL_GREY, C.WOOL_OLIVE, C.WOOL_BROWN)):
        fold_blanket(p, (0.01 * i, -0.01 * i, z), (0.55, 0.4, 0.09), mat, yaw=(i - 1) * 6, key=f"b{i}")
        z += 0.09
    if p.worn:
        F.drape(p, -0.27, 0.27, -0.2, 0.2, z, C.WOOL_GREY, hang=(0.1, 0.25, 0.15, 0.05), res=0.07, wrinkle=0.015, seed=p.seed,
                thickness=0.008, floor=0.0)
    else:
        p.rbox((0.5, 0.3, 0.11), (0.0, 0.0, z + 0.055), M.LINEN, radius=0.045, inner=(3, 2, 1), bulge=(0, 0, 0.02), wrinkle=0.006, seed=p.seed)
    p.collider((0, 0, 0.17), (0.6, 0.45, 0.34))


# ================================================================================================
# TRAILER
# ================================================================================================


def civic_ham_radio(p: Prop) -> None:
    """Ham radio station for a desk (surface prop, 0.6 x 0.36): a valve-era transceiver in grey crackle
    finish with tuning dial, knobs and meter, an SWR meter on top, a desk microphone and a straight morse
    key. Worn: the log pad and a coffee mug beside it."""
    paint = M.STEEL_GREY
    p.box((0.38, 0.3, 0.16), (0.0, 0.03, 0.08), paint, bevel=0.006, grain="X")
    p.box((0.38, 0.012, 0.16), (0.0, -0.126, 0.08), M.PL_BLACK, bevel=0.003)
    p.cyl(0.05, 0.01, (-0.08, -0.135, 0.09), C.IVORY, axis="Y", segs=14)
    p.cyl(0.02, 0.025, (-0.08, -0.15, 0.09), M.PL_BLACK, axis="Y", segs=10)
    for i, x in enumerate((0.06, 0.11, 0.16)):
        p.cyl(0.014, 0.02, (x, -0.142, 0.05), M.PL_BLACK, axis="Y", segs=8)
        p.cyl(0.003, 0.004, (x, -0.153, 0.05), M.CHROME, axis="Y", segs=6)
    p.box((0.09, 0.006, 0.05), (0.11, -0.134, 0.115), C.IVORY, bevel=0.0)
    p.box((0.16, 0.12, 0.08), (0.06, 0.05, 0.2), paint, bevel=0.005)
    p.box((0.07, 0.004, 0.045), (0.06, -0.011, 0.2), C.IVORY, bevel=0.0)
    p.cyl(0.045, 0.012, (-0.2, -0.12, 0.006), M.PL_BLACK, segs=12)
    p.tube([(-0.2, -0.12, 0.012), (-0.2, -0.12, 0.12), (-0.2, -0.15, 0.15)], 0.005, M.CHROME, segs=5, fillet_r=0.02)
    p.lathe([(0.0, 0.0), (0.022, 0.0), (0.026, 0.05), (0.02, 0.08), (0.0, 0.085)], (-0.2, -0.155, 0.13), M.CHROME, segs=8, axis="-Y")
    p.box((0.05, 0.1, 0.012), (0.22, -0.16, 0.006), M.PL_BLACK, bevel=0.002)
    p.box((0.012, 0.08, 0.006), (0.22, -0.17, 0.02), C.BRASS, bevel=0.0)
    p.cyl(0.008, 0.012, (0.22, -0.2, 0.03), M.PL_BLACK, segs=8)
    if p.worn:
        scatter_papers(p, (-0.05, -0.32, 0.0), 2, 0.04, "log")
        p.lathe([(0.0, 0.0), (0.04, 0.0), (0.042, 0.1), (0.038, 0.1), (0.036, 0.006), (0.0, 0.006)], (0.3, -0.2, 0.0), M.CERAMIC, segs=10, cap_top=False)
    p.collider((0, -0.02, 0.12), (0.62, 0.4, 0.24))


def civic_antenna_mast(p: Prop) -> None:
    """Ham antenna mast 6.5 m: a galvanised triangular lattice tower (three legs, zig-zag bracing) on a
    concrete pad, a rotator and a five-element Yagi beam, coax down one leg. Worn: rust, the beam turned
    askew, a broken element hanging."""
    H = 6.0
    p.box((0.7, 0.7, 0.12), (0, 0, 0.06), "concrete", bevel=0.01)
    R = 0.2
    legs = [(R * math.cos(math.radians(90 + 120 * k)), R * math.sin(math.radians(90 + 120 * k))) for k in range(3)]
    for x, y in legs:
        p.tube([(x, y, 0.1), (x * 0.7, y * 0.7, H)], 0.016, C.GALV, segs=5)
    steps = 14
    for i in range(steps):
        z0 = 0.1 + i * (H - 0.1) / steps
        z1 = 0.1 + (i + 1) * (H - 0.1) / steps
        f0 = 1.0 - 0.3 * (z0 - 0.1) / (H - 0.1)
        f1 = 1.0 - 0.3 * (z1 - 0.1) / (H - 0.1)
        for k in range(3):
            a = legs[k]
            b = legs[(k + 1) % 3]
            if i % 2 == 0:
                p.tube([(a[0] * f0, a[1] * f0, z0), (b[0] * f1, b[1] * f1, z1)], 0.006, C.GALV, segs=4)
            else:
                p.tube([(b[0] * f0, b[1] * f0, z0), (a[0] * f1, a[1] * f1, z1)], 0.006, C.GALV, segs=4)
    p.cyl(0.05, 0.15, (0, 0, H + 0.075), M.STEEL_GREY, segs=10)
    p.cyl(0.02, 0.8, (0, 0, H + 0.55), C.GALV, segs=6)
    yaw = 25 if p.worn else 0
    beam = [p.cyl(0.018, 2.6, (0, 0, H + 0.9), C.GALV, axis="Y", segs=6)]
    for i, ln in enumerate((1.12, 1.06, 1.0, 0.96, 0.92)):
        y = -1.2 + i * 0.6
        el = p.cyl(0.007, ln, (0, y, H + 0.9), C.GALV, axis="X", segs=4)
        if p.worn and i == 4:
            G.xform(el.obj, rot=(0, 55, 0), pivot=(0, y, H + 0.9))
        beam.append(el)
    p.rotate(beam, rot=(0, 0, yaw), pivot=(0, 0, 0))
    p.tube([(legs[0][0] * 0.7 + 0.03, legs[0][1] * 0.7, H), (legs[0][0] + 0.03, legs[0][1], 0.3), (legs[0][0] + 0.2, legs[0][1] + 0.1, 0.12)],
           0.006, C.RUBBER, segs=4)
    p.collider((0, 0, 3.2), (0.6, 0.6, 6.4))


# ================================================================================================
# registry
# ================================================================================================

BUILDERS = {
    "civic_pew": civic_pew,
    "civic_altar": civic_altar,
    "civic_pulpit": civic_pulpit,
    "civic_hymn_board": civic_hymn_board,
    "civic_candle_stand": civic_candle_stand,
    "civic_collection_box": civic_collection_box,
    "civic_reed_organ": civic_reed_organ,
    "civic_baptismal_font": civic_baptismal_font,
    "civic_church_bell": civic_church_bell,
    "civic_steeple": civic_steeple,
    "civic_church_sign": civic_church_sign,
    "civic_iron_fence": civic_iron_fence,
    "headstone": headstone,
    "civic_grave_mound": civic_grave_mound,
    "civic_hymnals": civic_hymnals,
    "civic_bar_counter": civic_bar_counter,
    "civic_back_bar": civic_back_bar,
    "civic_beer_taps": civic_beer_taps,
    "civic_bar_stool": civic_bar_stool,
    "civic_pool_table": civic_pool_table,
    "civic_jukebox": civic_jukebox,
    "civic_dartboard": civic_dartboard,
    "civic_keg": civic_keg,
    "civic_beer_crates": civic_beer_crates,
    "civic_po_counter": civic_po_counter,
    "civic_po_boxes": civic_po_boxes,
    "civic_sorting_rack": civic_sorting_rack,
    "civic_parcel_cage": civic_parcel_cage,
    "civic_mail_cart": civic_mail_cart,
    "civic_mail_sacks": civic_mail_sacks,
    "civic_parcel_scale": civic_parcel_scale,
    "civic_collection_mailbox": civic_collection_mailbox,
    "civic_po_sign": civic_po_sign,
    "civic_folding_table": civic_folding_table,
    "civic_folding_chair": civic_folding_chair,
    "civic_army_cot": civic_army_cot,
    "civic_relief_crate": civic_relief_crate,
    "civic_stage_lectern": civic_stage_lectern,
    "civic_coat_rack": civic_coat_rack,
    "civic_upright_piano": civic_upright_piano,
    "civic_trophy_case": civic_trophy_case,
    "civic_grange_banner": civic_grange_banner,
    "civic_shelter_board": civic_shelter_board,
    "civic_blanket_pile": civic_blanket_pile,
    "civic_ham_radio": civic_ham_radio,
    "civic_antenna_mast": civic_antenna_mast,
}


def build(params: dict, outputs: list[str]) -> None:
    core.build_variants(params, outputs, BUILDERS[params.get("builder", params["prop"])])
