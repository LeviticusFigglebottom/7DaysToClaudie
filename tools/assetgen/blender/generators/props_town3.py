"""Props of the town pool buildings (ADR-0030 pool; DESIGN section 11 "Pool buildings"): the set pieces a
random town's lots pick from.

Suds & Spin Laundromat: commercial front-load washer, big 50 lb dryer (drum open, a seat in the drum for
whoever crawled in), folding counter, wire laundry cart, change and soap machine.
Hollowmere Grocery: tall aisle gondola (stocked, picked over, and a collapsed one lying across the aisle),
three-door dairy cooler, refrigerated butcher counter, a reefer pup trailer at the dock.
Bracken Lumber & Feed: propane forklift, cantilever lumber rack, corrugated grain bin with ladder cage.
Pell County Library: double-faced stack section, card catalogue, reading table with banker's lamps,
circulation desk, book truck, children's table.
KHLW Valley Radio: broadcast console desk, equipment rack and transmitter, ON AIR sign (extruded letters
behind a red lens, lit on the station's generator), diesel generator set, square lattice mast with its
beacon, platform railing, relay cabinet.
Facade signs for all five (one builder, atlas cells).

Built on the interior-props framework (lib/props_int_core.py: Prop, variants clean / worn / destroyed,
bevels, wear and vertex AO, collision boxes). Printed faces map rects of the town3_print atlas made by
textures/gen/town3.py; ATLAS below mirrors its PRINT_RECTS (change both together).

params: prop (id), seed, variants, mount, budget, plus per-prop knobs (blender_catalogs/props_town3.py).
"""
from __future__ import annotations

import math
import zlib

import bmesh
import bpy
from mathutils import Matrix, Vector

from lib import common
from lib import props_int_core as core
from lib import props_int_furn as F
from lib import props_int_mesh as G
from lib.props_int_core import M, Prop


class T3:
    """Material ids: t3_* from game/data/materials/props_town3.json, the rest shared families."""
    PRINT = "t3_print"
    ON_AIR = "t3_on_air_glow"
    BEACON = "t3_beacon_glow"
    LED = "t3_led_glow"
    TRAILER = "t3_trailer_white"
    MEAT = "t3_meat_spoiled"
    DRUM = "t3_drum_steel"
    # shared (props_exterior.json, props_farm.json, props_wild.json, props_roadside.json)
    GALV = "metal_galvanized"
    CORR = "farm_corrugated_galv"
    CORR_RUST = "farm_corrugated_rust"
    PAINT_RED = "paint_red"
    PAINT_WHITE = "paint_white"
    PAINT_BLACK = "paint_black"
    PAINT_GREY = "paint_grey"
    PAINT_GREEN = "paint_green"
    YELLOW = "wild_paint_skidder_yellow"
    MILL_GREEN = "wild_paint_mill_green"
    LUMBER = "wild_lumber_fresh"
    LUMBER_OLD = "wild_lumber_weathered"
    LUMBER_DARK = "wild_lumber_dark"
    TYRE = "tyre_rubber"
    RUBBER = "rubber_black"
    LENS_RED = "lens_red"
    LENS_CLEAR = "lens_clear"
    LAMP = "lamp_glow"
    CRT = "road_crt"
    PCB = "road_pcb"
    RAG = "road_rag"
    TOWEL = "road_towel_white"
    UNDER = "underbody"
    FEED = "farm_feed_sack"
    GLASS_GREEN = "glass_green"
    STRAP = "packing_tape"


# town3_print atlas rects (x0, y0, x1, y1) in pixels of the 1024 px texture - mirror of
# textures/gen/town3.py PRINT_RECTS.
ATLAS: dict[str, tuple[int, int, int, int]] = {
    "sign_suds": (0, 0, 512, 128),
    "sign_grocery": (512, 0, 1024, 128),
    "sign_lumber": (0, 128, 512, 256),
    "sign_library": (512, 128, 1024, 256),
    "sign_khlw": (0, 256, 512, 384),
    "on_air": (512, 256, 768, 320),
    "deli": (768, 256, 1024, 320),
    "aisles": (512, 320, 1024, 384),
    "coin_panel": (0, 384, 256, 448),
    "rates": (256, 384, 384, 512),
    "changer": (384, 384, 512, 512),
    "soap": (512, 384, 640, 512),
    "card_labels": (640, 384, 1024, 448),
    "reefer": (0, 512, 512, 640),
    "forklift": (640, 448, 768, 512),
    "mast_plate": (768, 448, 896, 512),
    "console": (512, 512, 1024, 576),
    "transmitter": (512, 576, 768, 704),
    "rack_front": (768, 576, 1024, 704),
    "tape_labels": (0, 640, 256, 704),
    "notice_cordon": (256, 640, 512, 832),
    "kids_poster": (512, 704, 768, 832),
    "library_hours": (768, 704, 1024, 832),
    "grain_plate": (0, 704, 256, 768),
    "price_tags": (0, 832, 512, 864),
    "packets": (512, 832, 1024, 896),
    "spines_ref": (0, 864, 512, 1024),
    "wood_plain": (768, 896, 1024, 1024),
}


def atlas(name: str, k: int | None = None, inset: float = 1.0) -> tuple[float, float, float, float]:
    """UV rect (u0, v0, u1, v1) of an atlas entry; k picks a cell of the strip entries."""
    x0, y0, x1, y1 = ATLAS[name]
    if k is not None:
        if name == "aisles":
            x0, x1 = x0 + 128 * k, x0 + 128 * k + 128
        elif name in ("tape_labels", "packets"):
            x0, x1 = x0 + 64 * k, x0 + 64 * k + 64
        elif name == "card_labels":
            cx, cy = k % 6, (k // 6) % 4
            x0, x1 = x0 + 64 * cx, x0 + 64 * cx + 64
            y0, y1 = y0 + 16 * cy, y0 + 16 * cy + 16
        elif name == "spines_ref":
            x0, x1 = x0 + 32 * k, x0 + 32 * k + 32
        elif name == "price_tags":
            x0, x1 = x0 + 32 * k, x0 + 32 * k + 128
    return core._px_rect(x0 + inset, y0 + inset, x1 - inset, y1 - inset)


# ------------------------------------------------------------------------------------------------
# shared helpers
# ------------------------------------------------------------------------------------------------


def _rot_for(facing: str) -> tuple[float, float, float]:
    return {"-Y": (0, 0, 0), "+Y": (0, 0, 180), "+X": (0, 0, 90), "-X": (0, 0, -90), "+Z": (-90, 0, 0),
            "-Z": (90, 0, 0)}[facing]


def plate(p: Prop, w: float, h: float, center, uvrect, *, t: float = 0.002, mat: str = T3.PRINT, facing: str = "-Y",
          tags=(), wear: float = 0.35, bevel: float = 0.0, rot=None) -> core.Part:
    """Thin printed panel w x h (built in the XZ plane facing -Y, then turned to `facing`) whose front face
    shows `uvrect`; back and edges sample the rect's edge."""
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


def _wheel(p: Prop, c, r: float, w: float, *, axis: str = "X", hub: str = T3.PAINT_GREY, tyre: str = T3.TYRE, segs: int = 16,
           flat: float = 0.0) -> list:
    """Tyre (lathe with a rounded profile) and a steel hub, axle along `axis`."""
    prof = [(r * 0.62, -w / 2), (r * 0.92, -w / 2), (r, -w / 2 + w * 0.2), (r, w / 2 - w * 0.2), (r * 0.92, w / 2), (r * 0.62, w / 2)]
    prof = [(rr, z + w / 2) for rr, z in prof]
    ax = "X" if axis == "X" else "Y"
    cc = Vector(c) - (Vector((w / 2, 0, 0)) if ax == "X" else Vector((0, w / 2, 0)))
    tyre_p = p.lathe(prof, tuple(cc), tyre, segs=segs, axis=ax, cap_bottom=False, cap_top=False, wear=0.4)
    hub_p = p.cyl(r * 0.64, w * 0.7, tuple(c), hub, axis=ax, segs=12, wear=1.2)
    if flat > 0:
        for q in (tyre_p,):
            for v in q.obj.data.vertices:
                if v.co.z < c[2] - r + flat:
                    v.co.z = c[2] - r + flat
    return [tyre_p, hub_p]


def _text_part(p: Prop, s: str, size: float, depth: float, center, mat: str, *, font: str = "IBMPlexMono-Bold.ttf",
               facing: str = "-Y") -> core.Part:
    """Extruded lettering (a Blender text object made mesh), centred on `center`, its face toward `facing`."""
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[4]
    cu = bpy.data.curves.new(p._name("txt"), "FONT")
    cu.body = s
    cu.font = bpy.data.fonts.load(str(root / "game" / "assets" / "fonts" / font))
    cu.size = size
    cu.extrude = depth / 2
    cu.resolution_u = 2
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    ob = bpy.data.objects.new(p._name("txtob"), cu)
    bpy.context.scene.collection.objects.link(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.curves.remove(cu)
    bpy.context.view_layer.update()
    mo = bpy.data.objects.new(p._name("txtmesh"), me)
    bpy.context.scene.collection.objects.link(mo)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    G.xform(mo, rot=(90, 0, 0) if facing == "-Y" else (90, 0, 180))
    G.xform(mo, loc=center)
    return p.add(mo, mat, uv="box", uv_scale=4.0, wear=0.3, edge_deg=40.0)


def _cloth_heap(p: Prop, c, size, mat: str, key: str, wrinkle: float = 0.02) -> core.Part:
    return p.rbox(size, c, mat, radius=min(size) * 0.45, inner=(3, 3, 1), wrinkle=wrinkle, seed=p.seed + zlib.crc32(key.encode()) % 97,
                  bulge=(0.0, 0.0, min(size) * 0.3), edge_deg=40)


def _flip(part: core.Part) -> core.Part:
    """Turns a part's faces inward (a drum or barrel seen from inside)."""
    me = part.obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    return part


def _carton(p: Prop, size, center, cell: int, *, rot=(0, 0, 0), key: str = "pkg") -> core.Part:
    """A printed carton like F.package_box, unbevelled (12 triangles: shelves hold hundreds)."""
    obj = G.box(p._name("pkg"), size, (0, 0, 0), bevel=0.0)
    art = core.card_rect(cell)
    kraft = core.card_rect(14)
    strip = (art[0], art[1], art[0] + (art[2] - art[0]) * 0.18, art[3])

    def face_rect(poly):
        n = poly.normal
        if abs(n.y) > 0.9:
            return (*art, 0, 2, n.y > 0)
        if abs(n.x) > 0.9:
            return (*strip, 1, 2, False)
        return (*kraft, 0, 1, False)

    core.set_face_uvs(obj, face_rect)
    G.xform(obj, rot=rot, loc=center)
    return p.add(obj, M.CARDBOARD, uv="keep", tags=("goods", key), wear=0.7)


def _bolts(p: Prop, pts, mat: str = M.CHROME, r: float = 0.006, facing: str = "-Y") -> None:
    for q in pts:
        p.cyl(r, 0.006, q, mat, axis="Y" if facing in ("-Y", "+Y") else "X", segs=6, wear=1.5)


# ------------------------------------------------------------------------------------------------
# Suds & Spin Laundromat
# ------------------------------------------------------------------------------------------------


def town3_washer(p: Prop) -> None:
    """Commercial front-load washer (0.72 x 0.8 x 1.12): enamel cabinet with a stainless front, a round
    porthole door with a chrome ring and smoked glass, the coin panel and slide on a sloped console, soap
    drawer, plinth. Worn: door hanging open on a sodden load, rust at the feet; destroyed: door torn off
    and lying in front, coin box pried, the load dragged out across the floor."""
    W, D, H = 0.72, 0.78, 0.92
    p.box((W - 0.02, D - 0.02, 0.07), (0, 0, 0.035), M.STEEL_BLACK, bevel=0.004)
    body = p.box((W, D, H - 0.07), (0, 0, 0.07 + (H - 0.07) / 2), M.ENAMEL, bevel=0.01)
    body.floor_wear = 0.6
    front = p.box((W - 0.03, 0.012, H - 0.12), (0, -D / 2 - 0.006, 0.07 + (H - 0.12) / 2 + 0.02), M.STAINLESS, bevel=0.004)
    front.floor_wear = 0.5
    # sloped console
    con = p.prism([(-D / 2, 0.0), (D / 2, 0.0), (D / 2, 0.24), (-D / 2 + 0.16, 0.24)], W, M.ENAMEL, plane="YZ", offset=-W / 2, bevel=0.006)
    G.xform(con.obj, loc=(0, 0, H))
    ang = math.degrees(math.atan2(0.24, 0.16))
    plate(p, W - 0.08, 0.27, (0, -D / 2 + 0.08 - 0.004, H + 0.12), atlas("coin_panel"), t=0.003, rot=(-(90 - ang), 0, 0))
    for k in range(3):
        p.box((0.05, 0.03, 0.03), (0.12 + k * 0.06 - 0.05, -D / 2 + 0.1, H + 0.05), M.CHROME, bevel=0.004, tags=("knob",))
    soap = p.box((0.2, 0.05, 0.07), (-0.2, -D / 2 - 0.012, H - 0.08), M.PL_GREY, bevel=0.006)
    cz, rr = 0.48, 0.21
    door = [p.lathe([(rr - 0.02, 0.0), (rr + 0.03, 0.0), (rr + 0.035, 0.03), (rr - 0.005, 0.045), (rr - 0.03, 0.04)],
                    (0, 0, 0), M.CHROME, segs=24, axis="-Y", cap_bottom=False, cap_top=False, wear=0.9),
            p.lathe([(0.0, 0.05), (rr * 0.6, 0.048), (rr - 0.025, 0.035)], (0, 0, 0), M.GLASS, segs=24, axis="-Y",
                    cap_bottom=False, cap_top=False, wear=0.2),
            p.box((0.05, 0.035, 0.11), (rr + 0.03, -0.03, 0.0), M.PL_BLACK, bevel=0.01, tags=("knob",))]
    p.move(door, (0, -D / 2 - 0.012, cz))
    hole = p.cyl(rr - 0.02, 0.02, (0, -D / 2 - 0.003, cz), M.STEEL_BLACK, axis="Y", segs=24, wear=0.3)
    _flip(p.lathe([(rr - 0.03, 0.0), (rr - 0.03, 0.45), (0.0, 0.46)], (0, -D / 2 + 0.01, cz), T3.DRUM, segs=20, axis="Y",
                  cap_bottom=False, cap_top=False, wear=0.4))
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.cyl(0.025, 0.03, (sx * (W / 2 - 0.06), sy * (D / 2 - 0.06), 0.015), M.RUBBER, segs=8)
    p.box((0.09, 0.012, 0.13), (W / 2 - 0.1, -D / 2 - 0.014, 0.3), M.STEEL_GREY, bevel=0.003)
    p.cyl(0.01, 0.01, (W / 2 - 0.1, -D / 2 - 0.022, 0.33), M.BRASS, axis="Y", segs=8, tags=("knob",))
    r = p.vrng("load")
    if p.destroyed:
        p.lay_on_floor(door, rot=(90, 0, r.uniform(-30, 30)), at=(0.45, -D / 2 - 0.45), yaw=r.uniform(0, 60), z=0.0)
        p.remove(soap)
        for i in range(3):
            _cloth_heap(p, (r.uniform(-0.3, 0.3), -D / 2 - 0.3 - i * 0.25, 0.03), (0.4, 0.3, 0.07), [T3.RAG, T3.TOWEL, M.LINEN][i],
                        f"spill{i}")
    elif p.worn:
        p.rotate(door, rot=(0, 0, -100), pivot=(-rr - 0.04, -D / 2 - 0.02, 0))
        _cloth_heap(p, (0.0, -D / 2 + 0.12, cz - 0.12), (0.3, 0.32, 0.14), T3.RAG, "load")
        _cloth_heap(p, (0.05, -D / 2 - 0.05, cz - rr + 0.02), (0.22, 0.18, 0.06), T3.TOWEL, "hang")
    else:
        _cloth_heap(p, (0.0, -D / 2 + 0.15, cz - 0.13), (0.28, 0.3, 0.12), M.LINEN, "load")
    p.collider((0, 0, (H + 0.24) / 2), (W, D, H + 0.24))


def town3_dryer(p: Prop) -> None:
    """Big single-pocket commercial dryer (0.95 x 1.15 x 1.95): enamel cabinet, a 0.8 m drum door on a
    chrome ring, lint drawer, the coin panel up top and a vent stack behind. Its door stands open (ajar when
    clean) on a perforated drum big enough to crawl into: a seat anchor sits in the drum (the PropDef's
    anchors), so a Hollowed can be found curled up inside with its legs over the lip. Worn: the door wide,
    clothes dragged out; destroyed: the door torn off, the front kicked in."""
    W, D, H = 0.95, 1.12, 1.95
    p.box((W - 0.02, D - 0.02, 0.1), (0, 0, 0.05), M.STEEL_BLACK, bevel=0.004)
    body = p.box((W, D, H - 0.1), (0, 0, 0.1 + (H - 0.1) / 2), M.ENAMEL, bevel=0.012)
    body.floor_wear = 0.6
    # recessed control band
    p.box((W - 0.06, 0.015, 0.3), (0, -D / 2 - 0.007, H - 0.2), M.STAINLESS, bevel=0.004)
    plate(p, 0.5, 0.125, (-0.1, -D / 2 - 0.016, H - 0.17), atlas("coin_panel"), t=0.003)
    plate(p, 0.15, 0.15, (0.32, -D / 2 - 0.016, H - 0.2), atlas("rates"), t=0.002)
    for k in range(2):
        p.box((0.06, 0.03, 0.03), (-0.1 + k * 0.1, -D / 2 - 0.03, H - 0.3), M.CHROME, bevel=0.004, tags=("knob",))
    # lint drawer
    p.box((W - 0.2, 0.02, 0.14), (0, -D / 2 - 0.01, 0.22), M.STAINLESS, bevel=0.004)
    p.box((0.2, 0.03, 0.025), (0, -D / 2 - 0.03, 0.26), M.PL_BLACK, bevel=0.006, tags=("knob",))
    cz, rr = 0.9, 0.4
    # the drum: a perforated stainless barrel open at the front
    p.lathe([(rr, 0.0), (rr + 0.05, 0.0), (rr + 0.05, -0.02), (rr, -0.02)], (0, -D / 2 + 0.005, cz), M.STEEL_BLACK, segs=28, axis="Y",
            cap_bottom=False, cap_top=False, wear=0.3)
    _flip(p.lathe([(rr, 0.0), (rr, 0.86), (0.0, 0.88)], (0, -D / 2 + 0.02, cz), T3.DRUM, segs=24, axis="Y",
                  cap_bottom=False, cap_top=False, wear=0.5))
    for k in range(4):
        a = k * math.pi / 2 + 0.4
        baf = p.box((0.05, 0.8, 0.06), (math.cos(a) * (rr - 0.03), -D / 2 + 0.45, cz + math.sin(a) * (rr - 0.03)), T3.DRUM, bevel=0.01)
        G.xform(baf.obj, rot=(0, -math.degrees(a), 0), pivot=(math.cos(a) * (rr - 0.03), -D / 2 + 0.45, cz + math.sin(a) * (rr - 0.03)))
    ring = p.lathe([(rr - 0.01, 0.0), (rr + 0.06, 0.0), (rr + 0.07, 0.04), (rr + 0.02, 0.06), (rr - 0.02, 0.05)], (0, 0, 0), M.CHROME,
                   segs=28, axis="-Y", cap_bottom=False, cap_top=False, wear=0.9)
    glass = p.lathe([(0.0, 0.06), (rr * 0.7, 0.058), (rr - 0.02, 0.045)], (0, 0, 0), M.GLASS, segs=28, axis="-Y", cap_bottom=False,
                    cap_top=False, wear=0.2)
    handle = p.box((0.06, 0.045, 0.2), (rr + 0.05, -0.04, 0.0), M.PL_BLACK, bevel=0.012, tags=("knob",))
    door = [ring, glass, handle]
    p.move(door, (0, -D / 2 - 0.01, cz))
    hinge = (-rr - 0.07, -D / 2 - 0.02, 0)
    r = p.vrng("door")
    if p.destroyed:
        p.lay_on_floor(door, rot=(90, 0, 0), at=(0.7, -D / 2 - 0.55), yaw=r.uniform(-40, 40), z=0.0)
        p.remove(glass)
        _cloth_heap(p, (0.1, -D / 2 - 0.35, 0.04), (0.5, 0.35, 0.08), T3.RAG, "spill")
    elif p.worn:
        p.rotate(door, rot=(0, 0, -112), pivot=hinge)
        _cloth_heap(p, (-0.15, -D / 2 - 0.25, 0.04), (0.45, 0.3, 0.08), T3.TOWEL, "spill")
    else:
        p.rotate(door, rot=(0, 0, -38), pivot=hinge)
    # a tangle left at the back of the drum, behind whoever sits in it
    _cloth_heap(p, (0.1, -D / 2 + 0.72, cz - rr + 0.1), (0.4, 0.22, 0.14), M.LINEN, "tangle")
    # vent duct up the back
    p.cyl(0.075, 0.6, (0.25, D / 2 - 0.1, H + 0.3), T3.GALV, segs=12, wear=0.6)
    p.cyl(0.08, 0.04, (0.25, D / 2 - 0.1, H), T3.GALV, segs=12)
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.cyl(0.03, 0.02, (sx * (W / 2 - 0.08), sy * (D / 2 - 0.08), 0.01), M.RUBBER, segs=8)
    # collision: the cabinet only (the drum's sitter is posed, not simulated)
    p.collider((0, 0, H / 2), (W, D, H))


def town3_folding_table(p: Prop) -> None:
    """Laundromat folding counter (1.8 x 0.75 x 0.86): laminate top on a steel frame, a lower shelf with a
    plastic basket, folded stacks and a box of detergent left on top. Worn: stacks toppled, a towel hanging;
    destroyed: one end's legs buckled, the top tipped to the floor."""
    L, D, H = 1.8, 0.75, 0.86
    top = [p.box((L, D, 0.035), (0, 0, H - 0.0175), M.LAMINATE, bevel=0.004, grain="X")]
    top.append(p.box((L - 0.04, 0.02, 0.06), (0, -D / 2 + 0.02, H - 0.06), M.STEEL_WHITE, bevel=0.003, grain="X"))
    frame = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            frame.append(p.box((0.04, 0.04, H - 0.035), (sx * (L / 2 - 0.05), sy * (D / 2 - 0.05), (H - 0.035) / 2), M.STEEL_WHITE,
                               bevel=0.004, grain="Z"))
    shelf = p.box((L - 0.12, D - 0.1, 0.02), (0, 0, 0.2), M.STEEL_GREY, bevel=0.003, grain="X")
    basket = p.hollow((0.5, 0.36, 0.26), (-0.45, 0.02, 0.21 + 0.13), M.PL_BLUE, wall=0.012, open_face="+Z", bevel=0.004)
    _cloth_heap(p, (-0.45, 0.02, 0.36), (0.42, 0.3, 0.12), M.LINEN, "basket")
    goods = []
    r = p.rng("stacks")
    x = -0.7
    for i in range(4):
        h = r.uniform(0.08, 0.16)
        goods.append(p.rbox((0.32, 0.28, h), (x, r.uniform(-0.12, 0.1), H + h / 2), [T3.TOWEL, M.LINEN, M.FLORAL, M.TOWEL][i % 4],
                            radius=0.03, inner=(2, 2, 2), wrinkle=0.006, seed=p.seed + i, edge_deg=40))
        x += 0.38
    box = F.package_box(p, (0.2, 0.12, 0.26), (0.72, 0.15, H + 0.13), 3, key="soap")
    goods.append(box)
    if p.destroyed:
        p.remove(frame[2:])
        p.remove(goods[:2])
        p.rotate(top + goods[2:], rot=(0, 28, 0), pivot=(-L / 2, 0, H))
    elif p.worn:
        for q in goods[:2]:
            p.rotate([q], rot=(0, 75, 20), pivot=(0, 0, H))
            p.lay_on_floor([q], at=(r.uniform(-0.6, 0.6), -D / 2 - 0.25), yaw=r.uniform(0, 90))
        _cloth_heap(p, (0.2, -D / 2 - 0.05, H - 0.1), (0.3, 0.06, 0.25), T3.TOWEL, "hang")
    p.collider((0, 0, H / 2), (L, D, H))


def town3_laundry_cart(p: Prop) -> None:
    """Wire laundry cart (0.62 x 0.48 x 1.55): chrome basket of wire on four casters with a hanger rod and a
    couple of wire hangers. Worn: a wheel gone and the cart listing, rags in the basket."""
    W, D = 0.62, 0.46
    z0, z1 = 0.28, 0.72
    rails = []
    for z in (z0, (z0 + z1) / 2, z1):
        pts = [(-W / 2, -D / 2, z), (W / 2, -D / 2, z), (W / 2, D / 2, z), (-W / 2, D / 2, z)]
        rails.append(p.tube(pts, 0.005, M.CHROME, segs=6, closed=True, wear=0.8))
    for k in range(7):
        x = -W / 2 + (k + 0.5) * W / 7
        rails.append(p.tube([(x, -D / 2, z0), (x, -D / 2, z1)], 0.003, M.CHROME, segs=4))
        rails.append(p.tube([(x, D / 2, z0), (x, D / 2, z1)], 0.003, M.CHROME, segs=4))
        rails.append(p.tube([(x, -D / 2, z0), (x, D / 2, z0)], 0.003, M.CHROME, segs=4))
    for k in range(5):
        y = -D / 2 + (k + 0.5) * D / 5
        rails.append(p.tube([(-W / 2, y, z0), (-W / 2, y, z1)], 0.003, M.CHROME, segs=4))
        rails.append(p.tube([(W / 2, y, z0), (W / 2, y, z1)], 0.003, M.CHROME, segs=4))
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.tube([(sx * W / 2, sy * D / 2, 0.08), (sx * W / 2, sy * D / 2, z1)], 0.011, M.CHROME, segs=8)
            p.cyl(0.035, 0.025, (sx * W / 2, sy * D / 2, 0.035), M.RUBBER, axis="X", segs=10)
    p.tube([(-W / 2, D / 2, z1), (-W / 2, D / 2, 1.55), (W / 2, D / 2, 1.55), (W / 2, D / 2, z1)], 0.012, M.CHROME, segs=8,
           fillet_r=0.05)
    for k in range(3):
        x = -0.15 + k * 0.12
        p.tube([(x - 0.18, D / 2, 1.38), (x, D / 2, 1.5), (x + 0.18, D / 2, 1.38), (x - 0.18, D / 2, 1.38)], 0.0025, M.STEEL_GREY,
               segs=4)
        p.tube([(x, D / 2, 1.5), (x, D / 2, 1.55)], 0.0025, M.STEEL_GREY, segs=4)
    if p.worn:
        _cloth_heap(p, (0.05, 0.0, z0 + 0.12), (0.45, 0.35, 0.2), T3.RAG, "rags")
        p.rotate(p.parts, rot=(0, 4, 0), pivot=(-W / 2, 0, 0))
    else:
        _cloth_heap(p, (0.0, 0.0, z0 + 0.08), (0.4, 0.3, 0.12), T3.TOWEL, "towels")
    p.collider((0, 0, 0.78), (W, D, 1.56))


def town3_change_machine(p: Prop) -> None:
    """Bill changer and soap vendor (0.64 x 0.48 x 1.75): a steel cabinet on a plinth, the changer's
    face, bill slot and coin cup over the soap vendor's window of little detergent boxes and its push
    knobs. Worn: dented, the face scratched; destroyed: the door pried open on its hinges, the coin hopper
    empty and quarters on the floor."""
    W, D, H = 0.64, 0.48, 1.75
    p.box((W, D, 0.08), (0, 0, 0.04), M.STEEL_BLACK, bevel=0.004)
    cab = p.box((W, D, H - 0.08), (0, 0.0, 0.08 + (H - 0.08) / 2), M.STEEL_GREY, bevel=0.01)
    cab.floor_wear = 0.6
    door = [plate(p, W - 0.06, 0.6, (0, -D / 2 - 0.004, H - 0.36), atlas("changer"), t=0.008, wear=0.5),
            plate(p, W - 0.1, 0.5, (0, -D / 2 - 0.004, 0.62), atlas("soap"), t=0.008, wear=0.4),
            p.box((0.16, 0.02, 0.012), (0, -D / 2 - 0.012, H - 0.42), M.STEEL_BLACK, bevel=0.003),
            p.box((0.14, 0.07, 0.08), (0, -D / 2 - 0.04, 0.98), M.CHROME, bevel=0.01)]
    for k in range(4):
        door.append(p.cyl(0.018, 0.03, (-0.21 + k * 0.14, -D / 2 - 0.02, 0.3), M.CHROME, axis="Y", segs=10, tags=("knob",)))
    door.append(p.box((0.03, 0.02, 0.06), (W / 2 - 0.06, -D / 2 - 0.012, 1.1), M.BRASS, bevel=0.004, tags=("knob",)))
    if p.destroyed:
        p.rotate(door, rot=(0, 0, 105), pivot=(-W / 2 + 0.01, -D / 2 - 0.01, 0))
        p.box((W - 0.08, 0.3, 0.5), (0, -0.02, 1.2), M.STEEL_BLACK, bevel=0.004)
        r = p.vrng("coins")
        for i in range(14):
            p.cyl(0.012, 0.002, (r.uniform(-0.4, 0.4), -D / 2 - r.uniform(0.05, 0.6), 0.001), M.CHROME, segs=8)
    elif p.worn:
        r = p.vrng("coins")
        for i in range(4):
            p.cyl(0.012, 0.002, (r.uniform(-0.2, 0.2), -D / 2 - r.uniform(0.05, 0.3), 0.001), M.CHROME, segs=8)
    p.collider((0, 0, H / 2), (W, D, H))


def facade_sign(p: Prop) -> None:
    """Wall-mounted shop sign: a painted steel box sign (cell from the town3_print atlas) on stand-off
    brackets, with two gooseneck lamps over it when `lamps`. Origin on the wall plane, bottom centre,
    the face toward -Y. Worn: one end's bracket sheared and the sign hanging askew, rust runs."""
    w, h = float(p.params.get("w", 3.0)), float(p.params.get("h", 0.75))
    cell = str(p.params.get("cell", "sign_suds"))
    dz = 0.12
    box = [p.box((w + 0.06, dz, h + 0.06), (0, -dz / 2 - 0.08, h / 2), M.STEEL_BLACK, bevel=0.01)]
    box.append(plate(p, w, h, (0, -0.08 - dz - 0.002, h / 2), atlas(cell), t=0.004, wear=0.5))
    brackets = []
    for sx in (-1, 1):
        brackets.append(p.box((0.05, 0.09, 0.05), (sx * (w / 2 - 0.2), -0.045, h * 0.75), T3.GALV, bevel=0.005))
        brackets.append(p.box((0.05, 0.09, 0.05), (sx * (w / 2 - 0.2), -0.045, h * 0.25), T3.GALV, bevel=0.005))
    if bool(p.params.get("lamps", False)):
        for sx in (-1, 1):
            x = sx * w * 0.3
            p.tube([(x, -0.01, h + 0.15), (x, -0.25, h + 0.35), (x, -0.45, h + 0.3)], 0.012, T3.PAINT_GREEN, segs=8, fillet_r=0.1)
            p.lathe([(0.0, 0.0), (0.03, 0.0), (0.16, -0.12), (0.17, -0.13), (0.0, -0.08)], (x, -0.5, h + 0.33), T3.PAINT_GREEN,
                    segs=16, cap_bottom=False, cap_top=False)
    if p.worn:
        p.rotate(box + brackets[:2], rot=(0, -6, 0), pivot=(-w / 2 + 0.2, 0, h * 0.75))
    p.collider((0, -0.1, h / 2), (w, 0.2, h))


# ------------------------------------------------------------------------------------------------
# Hollowmere Grocery
# ------------------------------------------------------------------------------------------------


def _stock(p: Prop, x0: float, x1: float, y_edge: float, z: float, depth: float, max_h: float, facing: int, key: str,
           loot: float, cans_only: bool = False) -> list:
    """Low-poly facings of cartons and cans standing on a shelf; front at y_edge (facing -1 = -Y)."""
    r = p.rng(key)
    vr = p.vrng(key)
    out = []
    x = x0 + 0.01
    while x < x1 - 0.06:
        kind = "can" if cans_only or r.random() < 0.35 else "box"
        cell = r.randrange(14)
        if kind == "box":
            w, d, h = r.uniform(0.08, 0.2), min(depth, r.uniform(0.18, 0.3)), min(max_h, r.uniform(0.16, 0.3))
        else:
            w, d, h = 0.08, min(depth, 0.24), min(max_h, r.choice([0.11, 0.12, 0.16]))
        if x + w > x1:
            break
        if loot and vr.random() < loot:
            x += w + 0.01
            continue
        yy = y_edge - facing * (0.012 + d / 2)
        tumble = loot and vr.random() < 0.12
        if kind == "box":
            part = _carton(p, (w, d, h), (x + w / 2, yy, z + (h / 2 if not tumble else d / 2)), cell,
                           rot=((90 if tumble else 0) * facing, 0, 0 if facing < 0 else 180), key=key)
        else:
            # a row of cans read as one tin block (one wrap), stacked two high when short
            part = F.can(p, 0.038, h, (x + w / 2, yy, z + h / 2), cell, segs=8, key=key)
        out.append(part)
        x += w + r.uniform(0.004, 0.012)
    return out


def town3_grocery_shelf(p: Prop) -> None:
    """Tall double-sided grocery gondola (2.0 x 1.0 x 1.95): a base deck, a steel spine, five shelves a side
    with price strips, stocked with cartons and cans; an aisle card on a header at one end. Worn: picked
    over, things knocked flat; destroyed: stripped, a shelf torn out and hanging, its stock on the floor."""
    L, D, H = 2.0, 1.0, 1.95
    steel = M.STEEL_WHITE
    p.box((L - 0.02, 0.06, H - 0.12), (0, 0, 0.12 + (H - 0.12) / 2), M.PEGBOARD, bevel=0.002)
    for sx in (-1, 1):
        up = p.box((0.05, 0.08, H), (sx * (L / 2 - 0.025), 0, H / 2), steel, bevel=0.004, grain="Z")
        up.floor_wear = 0.8
        p.box((0.05, D - 0.02, 0.06), (sx * (L / 2 - 0.025), 0, 0.03), steel, bevel=0.004, grain="Y")
    loot = {"clean": 0.05, "worn": 0.45, "destroyed": 0.85}[p.cond]
    levels = [0.12, 0.5, 0.86, 1.22, 1.58]
    shelves = {}
    for side in (-1, 1):
        kick = p.box((L - 0.02, D / 2 - 0.05, 0.12), (0, side * (D / 4 + 0.02), 0.06), steel, bevel=0.003, grain="X")
        kick.floor_wear = 0.9
        for i, z in enumerate(levels):
            sh = []
            depth = 0.42 if i < 2 else 0.36
            if i > 0:
                sh.append(p.box((L - 0.07, depth, 0.022), (0, side * (0.04 + depth / 2), z - 0.011), steel, bevel=0.002, grain="X"))
            front = side * (0.04 + depth) if i > 0 else side * (D / 2 - 0.04)
            sh.append(plate(p, L - 0.08, 0.035, (0, front + side * 0.004, z - 0.03), atlas("price_tags", (i * 5) % 12), t=0.004,
                            facing="-Y" if side < 0 else "+Y"))
            zl = (levels[i + 1] - 0.03) if i + 1 < len(levels) else H - 0.04
            goods = _stock(p, -L / 2 + 0.05, L / 2 - 0.05, front, z, depth - 0.04, zl - z, side, f"row{side}{i}", loot,
                           cans_only=(i == 2))
            shelves[(side, i)] = (sh, goods)
    hdr = p.box((0.06, 0.5, 0.32), (L / 2 - 0.03, 0, H + 0.16), steel, bevel=0.004)
    k = int(p.params.get("aisle", 0))
    plate(p, 0.48, 0.24, (L / 2 + 0.003, 0, H + 0.16), atlas("aisles", k % 4), t=0.004, facing="+X")
    plate(p, 0.48, 0.24, (L / 2 - 0.063, 0, H + 0.16), atlas("aisles", k % 4), t=0.004, facing="-X")
    if p.destroyed:
        r = p.vrng("wreck")
        sh, goods = shelves[(-1, 3)]
        p.rotate(sh + goods, rot=(0, 16, 0), pivot=(-L / 2, 0, levels[3]))
        p.rotate(sh + goods, rot=(-28, 0, 0), pivot=(0, -0.04, levels[3]))
        for it in shelves[(-1, 2)][1][::2]:
            p.lay_on_floor([it], rot=(r.uniform(-90, 90), r.choice([0, 90]), 0), at=(r.uniform(-0.9, 0.9), -D / 2 - r.uniform(0.1, 0.6)),
                           yaw=r.uniform(0, 180))
    p.collider((0, 0, H / 2), (L, D, H))


def town3_grocery_shelf_fallen(p: Prop) -> None:
    """A grocery gondola toppled across the aisle (2.0 x 0.95 x 1.95 lying): on its side, the top shelves
    crushed, cartons and cans spilled in a fan on the floor. Worn: rained on and picked through."""
    L, H, D = 2.0, 1.95, 0.95
    steel = M.STEEL_WHITE
    grp = [p.box((L - 0.02, 0.06, H - 0.12), (0, 0, 0.12 + (H - 0.12) / 2), M.PEGBOARD, bevel=0.002)]
    for sx in (-1, 1):
        grp.append(p.box((0.05, 0.08, H), (sx * (L / 2 - 0.025), 0, H / 2), steel, bevel=0.004, grain="Z"))
        grp.append(p.box((0.05, D - 0.02, 0.06), (sx * (L / 2 - 0.025), 0, 0.03), steel, bevel=0.004, grain="Y"))
    for i, z in enumerate((0.5, 0.86, 1.22, 1.58)):
        sh = p.box((L - 0.07, 0.4, 0.022), (0, 0.24, z), steel, bevel=0.002, grain="X")
        if i >= 2:
            G.xform(sh.obj, rot=(-25 - i * 6, 0, 0), pivot=(0, 0.04, z))
        grp.append(sh)
    # lying on its +Y face: rotate -90 about X so the spine is horizontal
    p.rotate(grp, rot=(-88, 0, 3), pivot=(0, 0, 0))
    lo, hi = p.bounds(grp)
    p.move(grp, (0, -(lo.y + hi.y) / 2, -lo.z))
    r = p.rng("spill")
    vr = p.vrng("spill")
    for i in range(26 if not p.worn else 16):
        cell = r.randrange(14)
        x, y = r.uniform(-0.95, 0.95), r.uniform(-1.0, 1.05)
        if abs(y) < 0.5:
            y = math.copysign(r.uniform(0.55, 1.05), y if y else 1)
        if r.random() < 0.45:
            it = F.can(p, 0.038, 0.12, (0, 0, 0), cell, segs=8, key="spill")
            p.lay_on_floor([it], rot=(90, 0, 0), at=(x, y), yaw=vr.uniform(0, 180))
        else:
            it = _carton(p, (r.uniform(0.1, 0.2), r.uniform(0.06, 0.1), r.uniform(0.16, 0.28)), (0, 0, 0), cell, key="spill")
            p.lay_on_floor([it], rot=(r.choice([0, 90]), r.uniform(-20, 20), 0), at=(x, y), yaw=vr.uniform(0, 180))
    p.collider((0, 0, 0.5), (L, 1.0, 1.0))


def town3_cooler_case(p: Prop) -> None:
    """Three-door dairy cooler (2.4 x 0.9 x 2.15): enamel case, a lit canopy (dead), three glass doors in
    chrome frames, wire shelves of milk jugs, cartons and bottles behind them, a grille kick plate. Worn:
    one door propped open, stock gone sour and half taken; destroyed: the glass shattered out of every door,
    shelves stripped, a puddle."""
    L, D, H = 2.4, 0.88, 2.15
    p.box((L, D, 0.16), (0, 0, 0.08), M.STEEL_BLACK, bevel=0.004)
    plate(p, L - 0.1, 0.1, (0, -D / 2 - 0.004, 0.09), atlas("price_tags", 2), t=0.002)
    p.box((L, 0.06, H - 0.16), (0, D / 2 - 0.03, 0.16 + (H - 0.16) / 2), M.ENAMEL, bevel=0.006)
    for sx in (-1, 1):
        p.box((0.06, D, H - 0.16), (sx * (L / 2 - 0.03), 0, 0.16 + (H - 0.16) / 2), M.ENAMEL, bevel=0.008)
    p.box((L, D, 0.25), (0, 0, H - 0.125), M.ENAMEL, bevel=0.01)
    plate(p, L - 0.3, 0.16, (0, -D / 2 - 0.004, H - 0.13), atlas("deli"), t=0.003)
    p.box((L - 0.12, D - 0.1, 0.02), (0, 0.0, 0.17), M.STEEL_GREY, bevel=0.002)
    loot = {"clean": 0.1, "worn": 0.5, "destroyed": 0.95}[p.cond]
    vr = p.vrng("stock")
    r = p.rng("stock")
    for i, z in enumerate((0.18, 0.62, 1.04, 1.46)):
        if i:
            for k in range(14):
                x = -L / 2 + 0.1 + k * (L - 0.2) / 13
                p.tube([(x, -D / 2 + 0.12, z), (x, D / 2 - 0.08, z)], 0.004, M.CHROME, segs=4)
            p.tube([(-L / 2 + 0.08, -D / 2 + 0.12, z), (L / 2 - 0.08, -D / 2 + 0.12, z)], 0.006, M.CHROME, segs=6)
        x = -L / 2 + 0.12
        while x < L / 2 - 0.16:
            if vr.random() < loot:
                x += 0.14
                continue
            kind = r.random()
            if kind < 0.45:  # milk jug
                p.lathe([(0.065, 0.0), (0.065, 0.2), (0.025, 0.26), (0.0, 0.28)], (x, -D / 2 + 0.22, z + 0.005),
                        M.PL_WHITE, segs=6, wear=0.3)
                x += 0.15
            elif kind < 0.75:
                _carton(p, (0.09, 0.09, 0.2), (x, -D / 2 + 0.2, z + 0.105), r.randrange(14), key=f"carton{i}")
                x += 0.11
            else:
                p.lathe([(0.032, 0.0), (0.032, 0.15), (0.013, 0.2), (0.0, 0.23)], (x, -D / 2 + 0.2, z + 0.005),
                        T3.GLASS_GREEN, segs=6, wear=0.2)
                x += 0.08
    for k in range(3):
        x0 = -L / 2 + 0.06 + k * (L - 0.12) / 3
        dw = (L - 0.12) / 3
        grp = []
        for (fx, fz, fw, fh) in ((x0 + 0.02, 0.18, 0.04, H - 0.45), (x0 + dw - 0.02, 0.18, 0.04, H - 0.45)):
            grp.append(p.box((fw, 0.05, fh), (fx, -D / 2 - 0.02, fz + fh / 2), M.CHROME, bevel=0.004, grain="Z"))
        for fz in (0.2, H - 0.29):
            grp.append(p.box((dw - 0.04, 0.05, 0.04), (x0 + dw / 2, -D / 2 - 0.02, fz), M.CHROME, bevel=0.004, grain="X"))
        if not p.destroyed:
            grp.append(p.box((dw - 0.08, 0.008, H - 0.52), (x0 + dw / 2, -D / 2 - 0.02, 0.18 + (H - 0.47) / 2), M.GLASS, bevel=0.0,
                             wear=0.2))
        grp.append(p.box((0.03, 0.05, 0.5), (x0 + dw - 0.08, -D / 2 - 0.06, 1.1), M.CHROME, bevel=0.008, tags=("knob",)))
        if p.worn and k == 1:
            p.rotate(grp, rot=(0, 0, -80), pivot=(x0 + dw - 0.02, -D / 2 - 0.045, 0))
    if p.destroyed:
        p.box((1.3, 0.9, 0.004), (0.2, -D / 2 - 0.4, 0.002), "road_water_film", bevel=0.0)
    p.collider((0, 0, H / 2), (L, D, H))


def town3_butcher_counter(p: Prop) -> None:
    """Refrigerated butcher's case (2.4 x 1.1 x 1.3): an enamel base with a stainless kick and a red band,
    a well of white trays of meat gone grey-brown, a curved glass front, a stainless top shelf with a dial
    scale and a roll of butcher paper; sliding doors on the service side (+Y). Worn: the glass cracked and
    a tray tipped; destroyed: the glass smashed in, trays thrown on the floor."""
    L, D, H = 2.4, 1.05, 0.95
    base = p.box((L, D, H - 0.1), (0, 0, 0.1 + (H - 0.1) / 2), M.ENAMEL, bevel=0.01)
    base.floor_wear = 0.7
    p.box((L - 0.04, D - 0.04, 0.1), (0, 0, 0.05), M.STAINLESS, bevel=0.004)
    p.box((L + 0.004, 0.012, 0.12), (0, -D / 2 - 0.004, H - 0.2), M.STEEL_RED, bevel=0.003)
    plate(p, 0.6, 0.15, (-0.7, -D / 2 - 0.012, 0.5), atlas("deli"), t=0.003)
    # service side doors
    for k in range(3):
        p.box((0.7, 0.02, 0.5), (-0.75 + k * 0.75, D / 2 + 0.008, 0.45), M.STAINLESS, bevel=0.004)
        p.box((0.12, 0.03, 0.02), (-0.75 + k * 0.75, D / 2 + 0.02, 0.62), M.CHROME, bevel=0.004, tags=("knob",))
    well = p.hollow((L - 0.08, D - 0.25, 0.08), (0, -0.08, H + 0.0), M.STAINLESS, wall=0.01, open_face="+Z", bevel=0.003)
    r = p.rng("trays")
    vr = p.vrng("trays")
    trays = []
    for k in range(6):
        x = -L / 2 + 0.25 + k * 0.38
        t = [p.hollow((0.34, 0.5, 0.04), (x, -0.1, H + 0.02), M.PL_WHITE, wall=0.008, open_face="+Z", bevel=0.002)]
        for j in range(r.randint(2, 4)):
            t.append(p.rbox((r.uniform(0.1, 0.16), r.uniform(0.1, 0.2), r.uniform(0.03, 0.06)),
                            (x + r.uniform(-0.08, 0.08), -0.1 + r.uniform(-0.15, 0.15), H + 0.05), T3.MEAT, radius=0.02,
                            inner=(2, 2, 1), wrinkle=0.006, seed=p.seed + k * 7 + j, edge_deg=40))
        trays.append(t)
    # curved front glass in three facets
    glass = []
    pts = [(-D / 2 + 0.03, H + 0.02), (-D / 2 + 0.02, H + 0.2), (-D / 2 + 0.1, H + 0.34), (-D / 2 + 0.25, H + 0.4)]
    for i in range(3):
        (y0, z0), (y1, z1) = pts[i], pts[i + 1]
        g = p.box((L - 0.06, 0.008, math.hypot(y1 - y0, z1 - z0)), (0, (y0 + y1) / 2, (z0 + z1) / 2), M.GLASS, bevel=0.0, wear=0.2)
        G.xform(g.obj, rot=(-math.degrees(math.atan2(y1 - y0, z1 - z0)), 0, 0), pivot=(0, (y0 + y1) / 2, (z0 + z1) / 2))
        glass.append(g)
    for sx in (-1, 1):
        p.prism([(-D / 2 + 0.01, H), (D / 2 - 0.2, H), (D / 2 - 0.2, H + 0.42), (-D / 2 + 0.25, H + 0.42), (-D / 2 + 0.01, H + 0.2)],
                0.03, M.ENAMEL, plane="YZ", offset=sx * (L / 2 - 0.015) - 0.015, bevel=0.003)
    p.box((L, 0.35, 0.025), (0, D / 2 - 0.35, H + 0.42), M.STAINLESS, bevel=0.003)
    # scale and paper roll on the top shelf
    p.box((0.32, 0.3, 0.06), (0.6, D / 2 - 0.35, H + 0.465), M.STAINLESS, bevel=0.006)
    p.cyl(0.11, 0.05, (0.6, D / 2 - 0.3, H + 0.58), M.PL_WHITE, axis="Y", segs=16)
    p.cyl(0.1, 0.004, (0.6, D / 2 - 0.33, H + 0.58), M.GLASS, axis="Y", segs=16)
    p.cyl(0.07, 0.5, (-0.6, D / 2 - 0.35, H + 0.51), M.PAPER, axis="X", segs=12)
    if p.destroyed:
        p.remove(glass)
        for t in trays[1::2]:
            p.lay_on_floor(t, rot=(vr.uniform(-160, 160), 0, 0), at=(vr.uniform(-1.0, 1.0), -D / 2 - vr.uniform(0.3, 0.8)),
                           yaw=vr.uniform(0, 180))
        for i in range(5):
            sh = p.box((vr.uniform(0.08, 0.2), vr.uniform(0.06, 0.14), 0.004), (vr.uniform(-1.0, 1.0), -D / 2 - vr.uniform(0.1, 0.9), 0.002),
                       M.GLASS, bevel=0.0, wear=0.2)
            G.xform(sh.obj, rot=(0, 0, vr.uniform(0, 180)), pivot=sh.obj.data.vertices[0].co.copy())
    elif p.worn:
        p.rotate(trays[2], rot=(25, 0, 0), pivot=(0, -0.3, H))
        p.remove(glass[1:2])
    p.collider((0, 0, (H + 0.42) / 2), (L, D, H + 0.42))


def town3_reefer_trailer(p: Prop) -> None:
    """Refrigerated pup trailer (2.6 x 4.0 x 8.6) backed up to a dock: white ribbed box with the Northline
    Foods livery, the reefer unit on the nose, landing legs, a tandem axle under the back, a rear frame with
    two swing doors (toward -Y) and a load of pallets inside. Worn: the doors swung wide on a half-unloaded,
    stinking load, flat tyres, rust streaks."""
    W, L = 2.6, 8.6
    floor_z, top_z = 1.25, 4.0
    y_back, y_front = -L / 2, L / 2
    p.box((0.2, L - 0.4, 0.3), (-0.6, 0.1, floor_z - 0.2), T3.UNDER, bevel=0.01, grain="Y")
    p.box((0.2, L - 0.4, 0.3), (0.6, 0.1, floor_z - 0.2), T3.UNDER, bevel=0.01, grain="Y")
    p.box((W, L, 0.12), (0, 0, floor_z), T3.UNDER, bevel=0.01)
    # walls: ribbed panels (side posts every 0.6 m) over a smooth skin
    for sx in (-1, 1):
        p.box((0.04, L, top_z - floor_z), (sx * (W / 2 - 0.02), 0, (floor_z + top_z) / 2), T3.TRAILER, bevel=0.01, grain="Y")
        k = 0
        y = y_back + 0.35
        while y < y_front - 0.2:
            p.box((0.03, 0.06, top_z - floor_z - 0.1), (sx * (W / 2 + 0.005), y, (floor_z + top_z) / 2), T3.TRAILER, bevel=0.006, grain="Z")
            y += 0.6
            k += 1
        plate(p, 5.2, 1.3, (sx * (W / 2 + 0.025), 0.4, (floor_z + top_z) / 2 + 0.25), atlas("reefer"), t=0.004,
              facing="+X" if sx > 0 else "-X")
        p.box((0.02, L - 0.2, 0.08), (sx * (W / 2 + 0.01), 0, floor_z + 0.1), M.STEEL_RED, bevel=0.003, grain="Y")
    p.box((W, L, 0.06), (0, 0, top_z - 0.03), T3.TRAILER, bevel=0.01)
    p.box((W, 0.06, top_z - floor_z), (0, y_front - 0.03, (floor_z + top_z) / 2), T3.TRAILER, bevel=0.01)
    # reefer unit
    unit = p.box((2.0, 0.55, 1.5), (0, y_front + 0.28, top_z - 0.85), M.PL_WHITE, bevel=0.03)
    p.box((1.6, 0.02, 0.5), (0, y_front + 0.56, top_z - 0.6), M.STEEL_GREY, bevel=0.004)
    for k in range(8):
        p.box((1.5, 0.025, 0.02), (0, y_front + 0.575, top_z - 0.8 + k * 0.055), M.STEEL_BLACK, bevel=0.0)
    p.box((0.5, 0.02, 0.3), (-0.6, y_front + 0.565, top_z - 1.35), M.STEEL_GREY, bevel=0.004)
    # rear frame + doors
    for sx in (-1, 1):
        p.box((0.12, 0.12, top_z - floor_z + 0.1), (sx * (W / 2 - 0.06), y_back + 0.06, (floor_z + top_z) / 2), M.STAINLESS, bevel=0.008,
              grain="Z")
    p.box((W, 0.12, 0.14), (0, y_back + 0.06, top_z - 0.05), M.STAINLESS, bevel=0.008, grain="X")
    p.box((W, 0.2, 0.16), (0, y_back + 0.1, floor_z - 0.06), M.STAINLESS, bevel=0.008, grain="X")
    # bumper / dock guard
    p.box((W - 0.3, 0.12, 0.12), (0, y_back + 0.2, 0.55), M.STEEL_BLACK, bevel=0.01, grain="X")
    for sx in (-1, 1):
        p.box((0.08, 0.08, 0.6), (sx * 0.9, y_back + 0.24, 0.85), M.STEEL_BLACK, bevel=0.006)
    dw = W / 2 - 0.08
    doors = []
    for sx in (-1, 1):
        grp = [p.box((dw, 0.05, top_z - floor_z - 0.2), (sx * (dw / 2 + 0.02), y_back + 0.0, (floor_z + top_z) / 2 - 0.02), T3.TRAILER,
                     bevel=0.01)]
        for z in (floor_z + 0.6, top_z - 0.6):
            grp.append(p.box((dw - 0.1, 0.06, 0.05), (sx * (dw / 2 + 0.02), y_back - 0.03, z), M.STAINLESS, bevel=0.006, grain="X"))
        grp.append(p.tube([(sx * (dw * 0.75), y_back - 0.06, floor_z + 0.1), (sx * (dw * 0.75), y_back - 0.06, top_z - 0.15)], 0.02,
                          M.CHROME, segs=8))
        doors.append((sx, grp))
    if p.worn:
        for sx, grp in doors:
            p.rotate(grp, rot=(0, 0, sx * 100), pivot=(sx * (W / 2 + 0.02), y_back + 0.02, 0))
        r = p.vrng("load")
        for k in range(3):
            y = y_back + 1.6 + k * 1.6
            pal = p.box((1.1, 1.2, 0.14), (r.uniform(-0.5, 0.5), y, floor_z + 0.13), T3.LUMBER_OLD, bevel=0.004)
            for j in range(r.randint(2, 5)):
                _carton(p, (0.5, 0.4, 0.35), (r.uniform(-0.7, 0.7), y + r.uniform(-0.3, 0.3), floor_z + 0.38 + 0.36 * (j // 2)), 14,
                        key="load")
    else:
        for k in range(4):
            y = y_back + 1.2 + k * 1.5
            for j in range(4):
                _carton(p, (0.55, 0.45, 0.4), (-0.55 + (j % 2) * 1.1, y, floor_z + 0.27 + 0.42 * (j // 2)), 14, key="load")
    # landing gear and kingpin plate
    for sx in (-1, 1):
        p.box((0.12, 0.12, floor_z - 0.2), (sx * 0.85, y_front - 1.6, (floor_z - 0.2) / 2 + 0.06), T3.UNDER, bevel=0.008, grain="Z")
        p.box((0.3, 0.3, 0.05), (sx * 0.85, y_front - 1.6, 0.025), T3.UNDER, bevel=0.006)
    p.tube([(-0.85, y_front - 1.6, 0.85), (0.85, y_front - 1.6, 0.85)], 0.03, T3.UNDER, segs=8)
    # tandem axle
    flat = 0.05 if p.worn else 0.0
    for y in (y_back + 1.6, y_back + 2.85):
        p.tube([(-1.0, y, 0.5), (1.0, y, 0.5)], 0.06, T3.UNDER, segs=10)
        for sx in (-1, 1):
            for off in (0.0, 0.3):
                _wheel(p, (sx * (0.95 - off), y, 0.5), 0.5, 0.28, axis="X", hub=M.STEEL_GREY, segs=18, flat=flat)
    p.box((0.4, 2.2, 0.3), (0, y_back + 2.2, 0.85), T3.UNDER, bevel=0.01)
    for sx in (-1, 1):
        p.box((0.6, 0.02, 0.5), (sx * 0.95, y_back + 0.85, 0.75), M.RUBBER, bevel=0.0)
        p.box((0.05, 0.02, 0.15), (sx * 1.1, y_back - 0.02, floor_z - 0.2), T3.LENS_RED, bevel=0.003)
    p.collider((0, 0.1, top_z / 2), (W, L + 0.6, top_z))


# ------------------------------------------------------------------------------------------------
# Bracken Lumber & Feed
# ------------------------------------------------------------------------------------------------


def town3_forklift(p: Prop) -> None:
    """Propane forklift (1.15 x 2.15 x 3.0 with the forks): a yellow chassis over solid tyres, black
    counterweight, vinyl seat, steering wheel and levers under a tubular overhead guard, a two-stage mast with
    its carriage and forks to the front (-Y), the LP tank strapped across the back. Worn: forks up with a
    bundle of boards on them, rust, the seat split."""
    W = 1.1
    body = p.rbox((W, 1.5, 0.75), (0, 0.15, 0.62), T3.YELLOW, radius=0.06, inner=(2, 2, 1), edge_deg=30)
    body.floor_wear = 0.5
    cw = p.rbox((W + 0.04, 0.55, 0.9), (0, 0.85, 0.75), T3.PAINT_BLACK, radius=0.08, inner=(2, 1, 2), edge_deg=30)
    p.box((W - 0.2, 0.9, 0.06), (0, 0.05, 1.0), M.RUBBER, bevel=0.01)
    seat = p.rbox((0.5, 0.45, 0.12), (0, 0.4, 1.1), M.VINYL_BLACK, radius=0.04, inner=(2, 2, 1), edge_deg=40)
    p.rbox((0.48, 0.12, 0.45), (0, 0.6, 1.35), M.VINYL_BLACK, radius=0.04, inner=(2, 1, 2), edge_deg=40)
    # steering column and wheel
    p.tube([(0, -0.2, 1.0), (0, -0.05, 1.45)], 0.03, M.STEEL_BLACK, segs=8)
    p.lathe([(0.17, -0.015), (0.19, 0.0), (0.17, 0.015)], (0, -0.05, 1.46), M.PL_BLACK, segs=20, cap_bottom=False, cap_top=False)
    for k in range(3):
        p.tube([(0.25 + k * 0.05, -0.25, 1.0), (0.25 + k * 0.05, -0.2, 1.3)], 0.008, M.STEEL_BLACK, segs=6)
        p.cyl(0.02, 0.03, (0.25 + k * 0.05, -0.2, 1.32), M.PL_RED if k == 0 else M.PL_BLACK, segs=8, tags=("knob",))
    # overhead guard
    g = T3.YELLOW
    for sx in (-1, 1):
        p.tube([(sx * 0.48, -0.3, 0.95), (sx * 0.48, -0.25, 2.1), (sx * 0.48, 0.65, 2.1), (sx * 0.48, 0.75, 1.15)], 0.035, g, segs=8,
               fillet_r=0.08)
    for k in range(6):
        p.box((0.98, 0.04, 0.03), (0, -0.2 + k * 0.16, 2.12), g, bevel=0.004)
    # mast
    mast = []
    for sx in (-1, 1):
        mast.append(p.box((0.08, 0.12, 2.2), (sx * 0.38, -0.85, 1.15), M.STEEL_BLACK, bevel=0.006, grain="Z"))
        mast.append(p.box((0.06, 0.1, 2.0), (sx * 0.3, -0.87, 1.2), M.STEEL_GREY, bevel=0.006, grain="Z"))
    mast.append(p.box((0.84, 0.1, 0.08), (0, -0.85, 2.2), M.STEEL_BLACK, bevel=0.006))
    p.tube([(0.0, -0.75, 0.6), (0.0, -0.75, 1.6)], 0.04, M.CHROME, segs=10)
    lift = 0.0 if not p.worn else 1.1
    carriage = [p.box((0.9, 0.06, 0.45), (0, -0.98, 0.32 + lift), M.STEEL_BLACK, bevel=0.006)]
    for sx in (-1, 1):
        carriage.append(p.box((0.12, 0.05, 0.5), (sx * 0.28, -1.03, 0.3 + lift), M.STEEL_BLACK, bevel=0.006, grain="Z"))
        carriage.append(p.box((0.12, 1.07, 0.045), (sx * 0.28, -1.58, 0.07 + lift), M.STEEL_BLACK, bevel=0.006, grain="Y"))
    plate(p, 0.16, 0.08, (0.35, -0.6, 0.85), atlas("forklift"), t=0.003)
    # LP tank across the back
    p.cyl(0.16, 0.85, (0, 1.05, 1.45), M.STEEL_WHITE, axis="X", segs=14, wear=1.2)
    for sx in (-1, 1):
        p.lathe([(0.16, 0.0), (0.1, 0.08), (0.0, 0.1)], (sx * 0.425, 1.05, 1.45), M.STEEL_WHITE, segs=14, axis="X" if sx > 0 else "-X",
                cap_bottom=False, cap_top=True)
    p.tube([(0.3, 1.05, 1.61), (0.3, 1.05, 1.68)], 0.02, M.BRASS, segs=6)
    # wheels
    for sx in (-1, 1):
        _wheel(p, (sx * 0.45, -0.45, 0.34), 0.34, 0.22, axis="X", hub=T3.YELLOW, segs=16)
        _wheel(p, (sx * 0.45, 0.65, 0.27), 0.27, 0.18, axis="X", hub=T3.YELLOW, segs=14)
    for sx in (-1, 1):
        p.box((0.12, 0.05, 0.08), (sx * 0.4, -0.62, 1.35), T3.LENS_CLEAR, bevel=0.01)
    if p.worn:
        r = p.vrng("boards")
        for k in range(6):
            p.box((0.95, 0.04 if k % 2 else 0.09, 2.4), (0, -1.6, 0.0), T3.LUMBER, bevel=0.003, grain="Z")
        bundle = p.parts[-6:]
        for k, q in enumerate(bundle):
            G.xform(q.obj, rot=(90, 0, 0), pivot=(0, -1.6, 0))
            G.xform(q.obj, loc=(0, 0, 0.12 + lift + 0.05 + (k // 2) * 0.09 + 0.05))
        p.rotate(bundle, rot=(0, 0, 90), pivot=(0, -1.6, 0))
        seat_rip = p.rbox((0.2, 0.15, 0.04), (0.1, 0.38, 1.17), M.FOAM, radius=0.015, inner=(2, 2, 1), edge_deg=40)
    p.collider((0, -0.4, 1.1), (1.15, 2.4, 2.2))


def town3_lumber_rack(p: Prop) -> None:
    """Cantilever lumber rack (3.0 x 1.3 x 2.8): two steel columns on splayed feet, four levels of arms,
    bundles of dimensional lumber on stickers. Worn: half sold, boards gone grey on top; destroyed: the
    top arms sheared, their boards slid down to the floor in a fan."""
    L, D, H = 3.0, 1.3, 2.8
    cols = []
    for sx in (-1, 1):
        x = sx * 1.0
        cols.append(p.box((0.14, 0.14, H), (x, 0.55, H / 2), T3.MILL_GREEN, bevel=0.006, grain="Z"))
        p.box((0.14, D, 0.12), (x, 0.0, 0.06), T3.MILL_GREEN, bevel=0.006, grain="Y")
    p.box((2.0, 0.08, 0.1), (0, 0.55, 1.6), T3.MILL_GREEN, bevel=0.006, grain="X")
    p.tube([(-1.0, 0.55, 0.3), (1.0, 0.55, 2.4)], 0.025, T3.MILL_GREEN, segs=6)
    levels = [0.55, 1.15, 1.75, 2.35]
    r = p.rng("bundles")
    vr = p.vrng("bundles")
    bundles = []
    for i, z in enumerate(levels):
        arms = []
        for sx in (-1, 1):
            arms.append(p.box((0.1, 1.1, 0.08), (sx * 1.0, -0.05, z), T3.MILL_GREEN, bevel=0.006, grain="Y"))
            arms.append(p.box((0.1, 0.06, 0.12), (sx * 1.0, -0.57, z + 0.08), T3.MILL_GREEN, bevel=0.006))
        grp = list(arms)
        if p.worn and vr.random() < 0.35:
            bundles.append(grp)
            continue
        mat = T3.LUMBER if not p.worn or i < 2 else T3.LUMBER_OLD
        rows = r.randint(2, 4)
        bw, bh = (0.09, 0.04) if r.random() < 0.5 else (0.14, 0.04)
        per = int(0.95 / (bw + 0.004))
        for rr in range(rows):
            for k in range(per):
                if p.worn and rr == rows - 1 and vr.random() < 0.5:
                    continue
                grp.append(p.box((L, bw, bh), (r.uniform(-0.03, 0.03), -0.5 + k * (bw + 0.004) + bw / 2, z + 0.06 + rr * (bh + 0.02) + bh / 2),
                                 mat, bevel=0.0, grain="X", wear=0.6))
            if rr < rows - 1:
                for sx in (-1, 0, 1):
                    grp.append(p.box((0.04, 0.95, 0.02), (sx * 1.2, -0.02, z + 0.06 + rr * (bh + 0.02) + bh + 0.01), T3.LUMBER_OLD, bevel=0.0))
        bundles.append(grp)
    if p.destroyed:
        top = bundles[3] + bundles[2][4:]
        p.rotate(top, rot=(-35, 0, 8), pivot=(0, -0.6, 1.75))
        lo, _hi = p.bounds(top)
        if lo.z < 0:
            p.move(top, (0, 0, -lo.z))
    p.collider((0, 0, H / 2), (L, D, H))


def town3_grain_bin(p: Prop) -> None:
    """Corrugated steel grain bin (3.6 m across, 5.6 m eave, 6.6 m peak): bolted rings of corrugated
    sheet, a ribbed cone roof with its fill cap, a caged ladder up the side to the eave walkway, the access
    door on the ground ring, an unloading auger out at the foot, the maker's plate. Worn: rust blooms on the
    lower rings, the cap gone, a dent."""
    R, Hw = 1.8, 5.6
    rings = int(Hw / 0.8)
    for k in range(rings):
        z = k * 0.8
        mat = T3.CORR_RUST if (p.worn and k < 2) else T3.CORR
        p.lathe([(R, 0.0), (R, 0.8)], (0, 0, z), mat, segs=32, cap_bottom=False, cap_top=False, uv="cyl", uv_scale=1.0, wear=0.8)
        p.lathe([(R + 0.012, -0.02), (R + 0.012, 0.02)], (0, 0, z + 0.8), T3.GALV, segs=32, cap_bottom=False, cap_top=False)
    p.lathe([(R + 0.08, 0.0), (R + 0.08, 0.12), (R, 0.15)], (0, 0, -0.02), T3.GALV, segs=32, cap_bottom=False,
            cap_top=False)
    roof = p.lathe([(R + 0.1, 0.0), (R + 0.06, 0.05), (0.32, 0.92), (0.3, 0.98)], (0, 0, Hw), T3.GALV, segs=32, cap_bottom=True,
                   cap_top=True, uv="cyl", uv_scale=1.0, wear=0.8)
    for k in range(16):
        a = k * math.tau / 16
        rib = p.tube([(math.cos(a) * (R + 0.08), math.sin(a) * (R + 0.08), Hw + 0.05), (math.cos(a) * 0.33, math.sin(a) * 0.33, Hw + 0.95)],
                     0.02, T3.GALV, segs=4)
    if not p.worn:
        p.lathe([(0.34, 0.0), (0.36, 0.04), (0.2, 0.22), (0.0, 0.25)], (0, 0, Hw + 0.98), T3.GALV, segs=16, cap_bottom=True)
    # ladder cage up the -Y side
    ly = -R - 0.25
    for sx in (-1, 1):
        p.tube([(sx * 0.22, ly, 0.0), (sx * 0.22, ly, Hw + 0.3)], 0.022, T3.GALV, segs=6)
    for k in range(int((Hw + 0.2) / 0.3)):
        p.tube([(-0.22, ly, 0.3 + k * 0.3), (0.22, ly, 0.3 + k * 0.3)], 0.014, T3.GALV, segs=6)
    for k in range(5):
        z = 2.2 + k * 0.85
        p.tube([(-0.32, ly + 0.2, z), (-0.32, ly - 0.4, z), (0.32, ly - 0.4, z), (0.32, ly + 0.2, z)], 0.015, T3.GALV, segs=6, fillet_r=0.15)
    for sx in (-1, 0, 1):
        p.tube([(sx * 0.32, ly - 0.4 if sx else ly - 0.45, 2.2), (sx * 0.32, ly - 0.4 if sx else ly - 0.45, Hw + 0.2)], 0.012, T3.GALV, segs=4)
    for sy in (-1, 1):
        p.tube([(sy * 0.22, ly + 0.1, Hw - 0.6), (sy * 0.22, -R + 0.02, Hw - 0.6)], 0.02, T3.GALV, segs=4)
    # eave walkway railing (a quarter round over the ladder)
    for k in range(9):
        a0 = -math.pi / 2 - 0.5 + k * 0.125
        a1 = a0 + 0.125
        if k < 8:
            p.tube([(math.cos(a0) * (R + 0.35), math.sin(a0) * (R + 0.35), Hw + 0.6), (math.cos(a1) * (R + 0.35), math.sin(a1) * (R + 0.35), Hw + 0.6)],
                   0.018, T3.GALV, segs=4)
        p.tube([(math.cos(a0) * (R + 0.35), math.sin(a0) * (R + 0.35), Hw - 0.05), (math.cos(a0) * (R + 0.35), math.sin(a0) * (R + 0.35), Hw + 0.6)],
               0.015, T3.GALV, segs=4)
    # access door
    door = p.box((0.7, 0.06, 0.9), (0.9, -R * 0.9 - 0.06, 0.65), T3.GALV, bevel=0.01)
    G.xform(door.obj, rot=(0, 0, -30), pivot=(0.9, -R * 0.9, 0.65))
    plate(p, 0.6, 0.15, (-0.9, -R * 0.88 - 0.05, 1.6), atlas("grain_plate"), t=0.003, rot=(0, 0, -30))
    # unloading auger and hopper
    p.tube([(R - 0.2, 0.0, 0.3), (R + 2.4, 0.0, 1.9)], 0.11, T3.GALV, segs=10)
    p.lathe([(0.12, 0.0), (0.35, 0.4), (0.38, 0.45)], (R + 0.5, 0.0, 0.0), T3.GALV, segs=12, cap_bottom=True, cap_top=False)
    p.tube([(R + 2.4, 0.0, 1.9), (R + 2.55, 0.0, 1.7)], 0.13, T3.GALV, segs=10)
    p.cyl(0.25, 0.3, (R + 0.9, 0.35, 0.15), T3.MILL_GREEN, axis="Y", segs=12)
    p.collider((0, 0, (Hw + 1.0) / 2), (2 * R, 2 * R, Hw + 1.0))


# ------------------------------------------------------------------------------------------------
# Pell County Library
# ------------------------------------------------------------------------------------------------


def town3_library_stack(p: Prop) -> None:
    """Double-faced library stack section (1.0 x 0.6 x 2.1): oak end panels with a range-label holder,
    beige steel shelves, five shelves of books a side. Worn: gaps, books lying flat and fallen; destroyed:
    the section racked over against its neighbour, a shelf's books slid out across the floor."""
    L, D, H = 1.0, 0.56, 2.1
    side = []
    for sx in (-1, 1):
        side.append(p.box((0.03, D, H), (sx * (L / 2 - 0.015), 0, H / 2), M.OAK, bevel=0.004, grain="Z"))
        side.append(p.box((0.035, D + 0.02, 0.08), (sx * (L / 2 - 0.015), 0, 0.04), M.DARK, bevel=0.004))
    p.box((L - 0.06, 0.012, H - 0.1), (0, 0, 0.05 + (H - 0.1) / 2), M.STEEL_BEIGE, bevel=0.0)
    p.box((L + 0.01, D + 0.04, 0.03), (0, 0, H + 0.015), M.OAK, bevel=0.006)
    plate(p, 0.1, 0.05, (L / 2 + 0.002, -0.1, 1.55), atlas("card_labels", int(p.params.get("label", 0))), t=0.002, facing="+X")
    zs = [0.1, 0.48, 0.86, 1.24, 1.62]
    loot = {"clean": 0.0, "worn": 1.0, "destroyed": 1.0}[p.cond]
    books_all = []
    for sy in (-1, 1):
        for i, z in enumerate(zs):
            p.box((L - 0.06, D / 2 - 0.02, 0.02), (0, sy * (D / 4 + 0.004), z - 0.01), M.STEEL_BEIGE, bevel=0.002, grain="X")
            zl = (zs[i + 1] - 0.04) if i + 1 < len(zs) else H - 0.06
            row = F.book_row(p, -L / 2 + 0.04, L / 2 - 0.04, -0.27, z, zl - z, 0.24, key=f"r{sy}{i}", fill=0.9 if not loot else 0.72,
                             paper_ratio=0.1)
            if sy > 0:
                p.rotate(row, rot=(0, 0, 180), pivot=(0, 0, 0))
            books_all.append(row)
    if p.destroyed:
        r = p.vrng("spill")
        spill = books_all[3]
        for b in spill:
            p.lay_on_floor([b], rot=(r.uniform(-90, 90), 90, 0), at=(r.uniform(-0.5, 0.5), -D / 2 - r.uniform(0.1, 0.7)), yaw=r.uniform(0, 180))
        p.rotate(p.parts, rot=(0, 7, 0), pivot=(L / 2, 0, 0))
    elif p.worn:
        r = p.vrng("fallen")
        for row in books_all[1::3]:
            for b in row[:3]:
                p.lay_on_floor([b], rot=(0, 90, 0), at=(r.uniform(-0.4, 0.4), -D / 2 - r.uniform(0.05, 0.3)), yaw=r.uniform(0, 180))
    p.collider((0, 0, H / 2), (L, D, H))


def town3_card_catalog(p: Prop) -> None:
    """Oak card catalogue (1.0 x 0.55 x 1.4): a 5 x 6 cabinet of small drawers with brass label holders
    and cup pulls on a stand with a pull-out reference shelf. Worn: drawers pulled out, cards fanned on
    top; destroyed: drawers dumped on the floor, index cards everywhere."""
    W, D = 1.0, 0.52
    z0, z1 = 0.62, 1.38
    F.carcass(p, W, -D / 2, D / 2, z0, z1, M.OAK, frame=False, inner=M.DARK)
    p.box((W + 0.04, D + 0.04, 0.03), (0, 0, z1 + 0.015), M.OAK, bevel=0.006)
    for sx in (-1, 1):
        for sy in (-1, 1):
            F.tapered_leg(p, sx * (W / 2 - 0.05), sy * (D / 2 - 0.05), 0.0, z0, 0.06, 0.045, M.OAK)
    p.box((W - 0.06, D - 0.06, 0.03), (0, 0, 0.3), M.OAK, bevel=0.004)
    p.box((W - 0.1, 0.4, 0.025), (0, -0.05, z0 - 0.04), M.OAK, bevel=0.004)
    cols, rows = 5, 6
    dw, dh = (W - 0.04) / cols, (z1 - z0 - 0.04) / rows
    vr = p.vrng("drawers")
    k = 0
    dumped = []
    for c in range(cols):
        for rr in range(rows):
            x0 = -W / 2 + 0.02 + c * dw
            zb = z0 + 0.02 + rr * dh
            pull = 0.0
            if p.worn and vr.random() < 0.18:
                pull = vr.uniform(0.08, 0.3)
            grp = F.drawer(p, x0 + 0.004, zb + 0.004, x0 + dw - 0.004, zb + dh - 0.004, -D / 2 - 0.02, 0.38, M.OAK, style="slab", handle="cup",
                           handle_mat=M.BRASS, pull=pull, key=f"d{k}", contents=False)
            lab = plate(p, 0.06, 0.016, (x0 + dw / 2, -D / 2 - 0.024, zb + dh * 0.72), atlas("card_labels", k % 24), t=0.002)
            grp.append(lab)
            if pull > 0:
                grp.append(p.box((dw - 0.05, 0.3, dh * 0.6), (x0 + dw / 2, -D / 2 + 0.14 - pull, zb + dh * 0.4), M.PAPER, bevel=0.002))
            if p.destroyed and vr.random() < 0.25:
                dumped.append(grp)
            k += 1
    r = p.vrng("dump")
    for grp in dumped:
        p.lay_on_floor(grp, rot=(r.uniform(-30, 30), 0, 0), at=(r.uniform(-0.6, 0.6), -D / 2 - r.uniform(0.2, 0.8)), yaw=r.uniform(0, 180))
    if p.worn:
        for i in range(10 if p.destroyed else 4):
            card = p.box((0.125, 0.075, 0.001), (r.uniform(-0.6, 0.6), -D / 2 - r.uniform(0.1, 0.9), 0.0006), M.PAPER, bevel=0.0)
            G.xform(card.obj, rot=(0, 0, r.uniform(0, 180)), pivot=card.obj.data.vertices[0].co.copy())
    p.collider((0, 0, z1 / 2), (W, D, z1))


def town3_reading_table(p: Prop) -> None:
    """Library reading table (2.4 x 1.0 x 0.76) in oak with an apron and square legs, two brass banker's
    lamps with green glass shades down the middle, a few books and an open ledger. Worn: a lamp knocked
    over, its shade cracked; destroyed: a leg broken, the table down at one corner."""
    L, D, H = 2.4, 1.0, 0.76
    top = [p.box((L, D, 0.04), (0, 0, H - 0.02), M.OAK, bevel=0.006, grain="X")]
    for sy in (-1, 1):
        top.append(p.box((L - 0.2, 0.025, 0.1), (0, sy * (D / 2 - 0.08), H - 0.09), M.OAK, bevel=0.003, grain="X"))
    for sx in (-1, 1):
        top.append(p.box((0.025, D - 0.2, 0.1), (sx * (L / 2 - 0.1), 0, H - 0.09), M.OAK, bevel=0.003, grain="Y"))
    legs = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            legs.append(F.tapered_leg(p, sx * (L / 2 - 0.1), sy * (D / 2 - 0.08), 0.0, H - 0.04, 0.07, 0.055, M.OAK))
    lamps = []
    for sx in (-1, 1):
        x = sx * 0.55
        lp = [p.lathe([(0.07, 0.0), (0.07, 0.015), (0.03, 0.03), (0.012, 0.05)], (x, 0, H), M.BRASS, segs=14, cap_top=False),
              p.tube([(x, 0, H + 0.05), (x, 0, H + 0.36)], 0.01, M.BRASS, segs=8),
              p.tube([(x - 0.17, 0.02, H + 0.36), (x + 0.17, 0.02, H + 0.36)], 0.008, M.BRASS, segs=6)]
        shade = p.prism([(-0.22, 0.0), (0.22, 0.0), (0.18, 0.09), (-0.18, 0.09)], 0.16, T3.GLASS_GREEN, plane="XZ", offset=-0.06, bevel=0.004)
        G.xform(shade.obj, loc=(x, 0.0, H + 0.33))
        lp.append(shade)
        lp.append(p.cyl(0.006, 0.08, (x + 0.04, 0.03, H + 0.29), M.BRASS, segs=6))
        lamps.append(lp)
    r = p.rng("books")
    for k in range(4):
        b = F.book(p, (0.035, 0.18, 0.25), (0, 0, 0), r.randrange(64), key="tb")
        p.lay_on_floor([b], rot=(0, 90, 0), at=(r.uniform(-1.0, 1.0), r.uniform(-0.3, 0.3)), yaw=r.uniform(0, 180), z=H)
    ledger = plate(p, 0.42, 0.3, (0.2, -0.25, H + 0.005), atlas("notice_cordon"), t=0.004, facing="+Z")
    if p.destroyed:
        p.remove(legs[0])
        p.rotate([q for q in p.parts if q not in legs[1:]], rot=(0, -8, -4), pivot=(L / 2, D / 2, 0))
    elif p.worn:
        p.lay_on_floor(lamps[1], rot=(0, 90, 0), at=(0.7, -0.15), yaw=40, z=H)
    p.collider((0, 0, H / 2), (L, D, H))


def town3_circulation_desk(p: Prop) -> None:
    """Library circulation desk (2.6 x 0.85 x 1.05): an oak counter with fielded panels on the patron side
    (-Y), a raised transaction ledge, the book-return slot, the staff side's work top with a date stamp,
    an ink pad, a card file and the hours plaque. Worn: the card file spilled; destroyed: the front panel
    kicked in."""
    L, D = 2.6, 0.85
    Hc, Hl = 0.76, 1.05
    p.box((L, D, 0.04), (0, 0.05, Hc), M.OAK, bevel=0.006, grain="X")
    p.box((L, 0.2, 0.04), (0, -D / 2 + 0.1, Hl), M.OAK, bevel=0.008, grain="X")
    front = []
    for k in range(5):
        x = -L / 2 + (k + 0.5) * L / 5
        front.append(p.panel(L / 5 - 0.03, Hl - 0.12, 0.03, (x, -D / 2 + 0.015, (Hl - 0.12) / 2 + 0.06), M.OAK, style="raised"))
    p.box((L, 0.04, 0.08), (0, -D / 2 + 0.02, 0.04), M.DARK, bevel=0.004)
    for sx in (-1, 1):
        p.box((0.04, D, Hl), (sx * (L / 2 - 0.02), 0, Hl / 2), M.OAK, bevel=0.004, grain="Z")
    p.box((0.4, 0.05, 0.06), (0.9, -D / 2 - 0.0, Hl - 0.2), M.BRASS, bevel=0.004)
    plate(p, 0.36, 0.18, (-0.7, -D / 2 - 0.005, Hl - 0.3), atlas("library_hours"), t=0.004, wear=0.3)
    p.box((0.12, 0.08, 0.02), (0.3, 0.2, Hc + 0.03), M.PL_BLACK, bevel=0.006)
    p.lathe([(0.012, 0.0), (0.012, 0.08), (0.03, 0.1), (0.0, 0.12)], (0.5, 0.2, Hc + 0.02), M.DARK, segs=10)
    p.box((0.16, 0.12, 0.012), (0.5, 0.2, Hc + 0.026), M.STEEL_BLACK, bevel=0.003)
    cf = p.hollow((0.22, 0.3, 0.14), (-0.3, 0.15, Hc + 0.09), M.OAK, wall=0.01, open_face="+Z", bevel=0.003)
    p.box((0.2, 0.28, 0.1), (-0.3, 0.15, Hc + 0.08), M.PAPER, bevel=0.002)
    for x in (-1.0, 1.05):
        p.box((0.45, 0.6, 0.02), (x, 0.08, 0.3), M.OAK, bevel=0.003)
    if p.destroyed:
        for q in front[1:3]:
            G.xform(q.obj, rot=(30, 0, 0), pivot=(0, -D / 2, 0.0))
        p.remove(front[2])
    if p.worn:
        r = p.vrng("cards")
        for i in range(8):
            card = p.box((0.125, 0.075, 0.001), (r.uniform(-0.8, 0.2), r.uniform(0.0, 0.35), Hc + 0.021), M.PAPER, bevel=0.0)
            G.xform(card.obj, rot=(0, 0, r.uniform(0, 180)), pivot=card.obj.data.vertices[0].co.copy())
    p.collider((0, 0, Hl / 2), (L, D, Hl))


def town3_book_cart(p: Prop) -> None:
    """Library book truck (0.9 x 0.4 x 1.0): three slanted shelves of returns on an oak frame with rubber
    casters. Worn: books spilled off the top shelf."""
    L, D, H = 0.9, 0.38, 1.0
    for sx in (-1, 1):
        p.box((0.03, D, H - 0.1), (sx * (L / 2 - 0.015), 0, 0.1 + (H - 0.1) / 2), M.OAK, bevel=0.004, grain="Z")
        for sy in (-1, 1):
            p.cyl(0.04, 0.03, (sx * (L / 2 - 0.06), sy * (D / 2 - 0.06), 0.04), M.RUBBER, axis="X", segs=10)
    for i, z in enumerate((0.2, 0.52, 0.84)):
        sh = p.box((L - 0.06, D - 0.04, 0.02), (0, 0, z), M.OAK, bevel=0.003, grain="X")
        row = F.book_row(p, -L / 2 + 0.04, L / 2 - 0.04, -0.15, z + 0.01, 0.28, 0.24, key=f"cart{i}", fill=0.85, paper_ratio=0.2)
        p.rotate([sh] + row, rot=(-12, 0, 0), pivot=(0, 0, z))
    if p.worn:
        r = p.vrng("spill")
        for b in [q for q in p.parts if "cart2" in q.tags][:4]:
            p.lay_on_floor([b], rot=(0, 90, 0), at=(r.uniform(-0.4, 0.4), -D / 2 - r.uniform(0.1, 0.5)), yaw=r.uniform(0, 180))
    p.collider((0, 0, H / 2), (L, D, H))


def town3_kids_table(p: Prop) -> None:
    """Children's corner: a low round table (1.2 m) with four little chairs in primary colours and picture
    books. Worn: chairs pushed back and one over; destroyed: the table on its side."""
    R, H = 0.6, 0.52
    top = p.cyl(R, 0.03, (0, 0, H - 0.015), M.PL_WHITE, segs=24)
    p.lathe([(R + 0.005, -0.012), (R + 0.012, 0.0), (R + 0.005, 0.012)], (0, 0, H - 0.015), M.PL_RED, segs=24, cap_bottom=False, cap_top=False)
    for k in range(4):
        a = k * math.pi / 2 + math.pi / 4
        p.cyl(0.022, H - 0.03, (math.cos(a) * 0.4, math.sin(a) * 0.4, (H - 0.03) / 2), M.STEEL_WHITE, segs=8)
    cols = [M.PL_RED, M.PL_BLUE, M.PL_WHITE, M.PL_GREY]
    vr = p.vrng("chairs")
    for k in range(4):
        a = k * math.pi / 2
        cx, cy = math.cos(a) * (R + 0.18), math.sin(a) * (R + 0.18)
        ch = [p.box((0.3, 0.28, 0.025), (0, 0, 0.3), cols[k], bevel=0.008), p.box((0.3, 0.025, 0.24), (0, 0.13, 0.45), cols[k], bevel=0.008)]
        for sx in (-1, 1):
            for sy in (-1, 1):
                ch.append(p.tube([(sx * 0.12, sy * 0.11, 0.0), (sx * 0.12, sy * 0.11, 0.3)], 0.01, M.STEEL_WHITE, segs=6))
        ang = math.degrees(a) + 90
        p.rotate(ch, rot=(0, 0, ang), pivot=(0, 0, 0))
        p.move(ch, (cx, cy, 0))
        if p.worn and k == 2:
            p.lay_on_floor(ch, rot=(90, 0, 0), at=(cx * 1.3, cy * 1.3), yaw=vr.uniform(0, 90))
    r = p.rng("books")
    for k in range(3):
        b = F.book(p, (0.02, 0.24, 0.3), (0, 0, 0), r.randrange(64), key="kb")
        p.lay_on_floor([b], rot=(0, 90, 0), at=(r.uniform(-0.3, 0.3), r.uniform(-0.3, 0.3)), yaw=r.uniform(0, 180), z=H)
    p.collider((0, 0, H / 2), (2 * R + 0.3, 2 * R + 0.3, H))


# ------------------------------------------------------------------------------------------------
# KHLW Valley Radio
# ------------------------------------------------------------------------------------------------


def town3_studio_desk(p: Prop) -> None:
    """Broadcast console desk (2.2 x 1.0 x 1.05): a laminate desk with the mixing console sunk into a
    sloped well (channel strips from the town3_print atlas), a broadcast mic on a boom arm with its pop
    shield, a CRT log monitor, a stack of cart machines, headphones and a coffee mug. Worn: the mic arm
    slumped, papers; destroyed: the monitor smashed on the floor, the console's faceplate torn up."""
    L, D, H = 2.2, 0.95, 0.76
    p.box((L, D, 0.04), (0, 0, H - 0.02), M.LAM_WOOD, bevel=0.006, grain="X")
    for sx in (-1, 1):
        p.box((0.04, D - 0.04, H - 0.04), (sx * (L / 2 - 0.02), 0, (H - 0.04) / 2), M.LAM_WOOD, bevel=0.004, grain="Z")
    p.box((L - 0.08, 0.02, H - 0.3), (0, D / 2 - 0.03, (H - 0.04) / 2 + 0.15), M.LAM_WOOD, bevel=0.003)
    con = p.prism([(-0.36, 0.0), (0.12, 0.0), (0.12, 0.14), (-0.36, 0.05)], 1.3, M.STEEL_BLACK, plane="YZ", offset=-0.65, bevel=0.006)
    G.xform(con.obj, loc=(0, 0, H))
    face = plate(p, 1.24, 0.47, (0, -0.12, H + 0.098), atlas("console"), t=0.003, rot=(-79.4, 0, 0))
    # carts
    for k in range(3):
        p.box((0.42, 0.32, 0.12), (0.88, 0.2, H + 0.06 + k * 0.125), M.PL_BEIGE, bevel=0.008)
        p.box((0.16, 0.012, 0.04), (0.88, 0.035, H + 0.07 + k * 0.125), M.PL_BLACK, bevel=0.002)
    # monitor
    mon = [p.rbox((0.42, 0.4, 0.36), (-0.8, 0.2, H + 0.2), M.PL_BEIGE, radius=0.03, inner=(2, 2, 2), edge_deg=30),
           p.box((0.34, 0.01, 0.26), (-0.8, -0.005, H + 0.21), T3.CRT, bevel=0.0)]
    # mic boom
    mic = [p.tube([(-0.35, 0.3, H), (-0.35, 0.3, H + 0.45), (-0.1, -0.05, H + 0.6), (0.05, -0.2, H + 0.42)], 0.012, M.STEEL_BLACK, segs=8,
                  fillet_r=0.05),
           p.cyl(0.035, 0.18, (0.05, -0.22, H + 0.33), M.STEEL_GREY, segs=12),
           p.cyl(0.07, 0.006, (0.05, -0.33, H + 0.36), M.SHADE, axis="Y", segs=16)]
    p.tube([(-0.25, -0.05, H + 0.02), (-0.15, 0.05, H + 0.15), (-0.05, -0.05, H + 0.02)], 0.012, M.PL_BLACK, segs=8, fillet_r=0.04)
    p.lathe([(0.04, 0.0), (0.045, 0.1), (0.0, 0.1)], (0.4, -0.3, H), M.CERAMIC, segs=12, cap_top=False)
    plate(p, 0.22, 0.28, (-0.4, -0.25, H + 0.002), atlas("notice_cordon"), t=0.002, facing="+Z")
    if p.destroyed:
        p.lay_on_floor(mon, rot=(70, 0, 20), at=(-0.6, -D / 2 - 0.5), yaw=30)
        p.remove(mon[1])
        G.xform(face.obj, rot=(25, 0, 0), pivot=(0, -0.3, H + 0.06))
    elif p.worn:
        p.rotate(mic, rot=(0, 0, 40), pivot=(-0.35, 0.3, H))
        p.rotate(mic[1:], rot=(-60, 0, 0), pivot=(0.05, -0.2, H + 0.42))
    p.collider((0, 0, H / 2), (L, D, H))


def _rack_cabinet(p: Prop, W: float, D: float, H: float, cell: str, units: int) -> None:
    p.box((W, D, 0.08), (0, 0, 0.04), M.STEEL_BLACK, bevel=0.004)
    for sx in (-1, 1):
        p.box((0.03, D, H - 0.08), (sx * (W / 2 - 0.015), 0, 0.08 + (H - 0.08) / 2), M.STEEL_GREY, bevel=0.004, grain="Z")
    p.box((W, D, 0.06), (0, 0, H - 0.03), M.STEEL_GREY, bevel=0.006)
    p.box((W - 0.06, 0.02, H - 0.14), (0, D / 2 - 0.01, 0.08 + (H - 0.14) / 2), M.STEEL_GREY, bevel=0.002)
    # louvres up top
    for k in range(6):
        p.box((W - 0.1, 0.01, 0.012), (0, -D / 2 - 0.004, H - 0.12 - k * 0.025), M.STEEL_BLACK, bevel=0.0)
    faces = []
    zb = 0.12
    uh = (H - 0.42) / units
    for k in range(units):
        z = zb + k * uh
        faces.append(plate(p, W - 0.08, uh - 0.02, (0, -D / 2 + 0.015, z + uh / 2), atlas(cell), t=0.012, wear=0.4))
        p.box((W - 0.06, 0.006, 0.012), (0, -D / 2 + 0.006, z + uh - 0.006), M.CHROME, bevel=0.0)
        led = p.box((0.18, 0.004, 0.012), (-W / 2 + 0.15, -D / 2 + 0.004, z + uh - 0.03), T3.LED, bevel=0.0, wear=0.0)
    # cables out the top back
    for k in range(4):
        p.tube([(-0.15 + k * 0.1, D / 2 - 0.08, H), (-0.15 + k * 0.1, D / 2 - 0.1, H + 0.22), (-0.15 + k * 0.1, D / 2 - 0.3, H + 0.3)],
               0.012, M.PL_BLACK, segs=6, fillet_r=0.08)
    return faces


def town3_equipment_rack(p: Prop) -> None:
    """19-inch equipment rack (0.62 x 0.85 x 2.0): a grey steel cabinet of exciter, audio processor, EBS
    encoder and STL receiver (atlas faces) with their status LEDs (they glow while the station's generator
    runs: t3_led_glow), louvres and the cable loom out of the top. Worn: a unit pulled half out on its
    slides; destroyed: units ripped out and dumped, wiring hanging."""
    W, D, H = 0.62, 0.85, 2.0
    faces = _rack_cabinet(p, W, D, H, "rack_front", 5)
    if p.destroyed:
        r = p.vrng("rip")
        for f in faces[1:4]:
            p.lay_on_floor([f], rot=(90, 0, 0), at=(r.uniform(-0.3, 0.3), -D / 2 - r.uniform(0.2, 0.6)), yaw=r.uniform(-40, 40))
        for k in range(3):
            p.tube([(-0.2 + k * 0.15, -D / 2 + 0.05, 1.2), (-0.25 + k * 0.17, -D / 2 - 0.15, 0.6), (-0.3 + k * 0.2, -D / 2 - 0.3, 0.02)], 0.008,
                   M.PL_RED if k == 1 else M.PL_BLACK, segs=6, fillet_r=0.2)
    elif p.worn:
        p.move([faces[2]], (0, -0.3, 0))
    p.collider((0, 0, H / 2), (W, D, H))


def town3_transmitter(p: Prop) -> None:
    """KHLW's 1 kW AM transmitter (1.2 x 0.9 x 2.0): a tall grey cabinet with its three meters (plate
    voltage, plate current, forward power), the frequency plate and the tuning knobs; the RF feed out of
    the top to the mast. Worn: a meter glass cracked, a panel off; destroyed: the front door torn open on
    burnt valves."""
    W, D, H = 1.2, 0.88, 2.0
    p.box((W, D, H), (0, 0, H / 2), M.STEEL_GREY, bevel=0.012)
    door = [plate(p, W - 0.1, 0.62, (0, -D / 2 - 0.006, 1.45), atlas("transmitter"), t=0.012, wear=0.5)]
    for k in range(4):
        door.append(p.cyl(0.035, 0.04, (-0.36 + k * 0.24, -D / 2 - 0.03, 0.98), M.PL_BLACK, axis="Y", segs=14, tags=("knob",)))
    door.append(p.box((W - 0.12, 0.012, 0.75), (0, -D / 2 - 0.006, 0.45), M.STEEL_GREY, bevel=0.004))
    for k in range(10):
        p.box((W - 0.25, 0.008, 0.012), (0, -D / 2 - 0.013, 0.2 + k * 0.06), M.STEEL_BLACK, bevel=0.0)
    p.box((0.18, 0.004, 0.02), (0.45, -D / 2 - 0.009, 1.1), T3.LED, bevel=0.0, wear=0.0)
    p.tube([(0.3, 0.2, H), (0.3, 0.2, H + 0.25), (0.3, -0.25, H + 0.35)], 0.04, M.STEEL_BLACK, segs=10, fillet_r=0.1)
    if p.destroyed:
        p.rotate(door[-1:], rot=(0, 0, 100), pivot=(-W / 2 + 0.06, -D / 2 - 0.01, 0))
        for k in range(4):
            p.lathe([(0.05, 0.0), (0.06, 0.15), (0.03, 0.25), (0.0, 0.26)], (-0.3 + k * 0.2, -0.1, 0.25), M.GLASS_FROST, segs=10)
    elif p.worn:
        p.move(door[-1:], (0.1, -0.15, 0))
        p.rotate(door[-1:], rot=(0, 0, 12), pivot=(0, -D / 2, 0))
    p.collider((0, 0, H / 2), (W, D, H))


def town3_on_air_sign(p: Prop) -> None:
    """ON AIR sign (0.62 x 0.24, 0.13 deep), wall-mounted: a black housing on a bracket with a red acrylic
    face, the letters behind it extruded (t3_on_air_glow: they glow red while the generator runs). Origin on
    the wall plane, bottom centre. Worn: the face scuffed and the housing tipped; destroyed: the face
    smashed out and the letters broken."""
    w, h, d = 0.62, 0.24, 0.12
    y0 = -0.06
    house = [p.box((w, d, h), (0, y0 - d / 2, h / 2), M.PL_BLACK, bevel=0.01)]
    letters = _text_part(p, "ON AIR", 0.145, 0.014, (0, y0 - d - 0.004, h / 2), T3.ON_AIR, font="IBMPlexMono-Bold.ttf")
    face_back = p.box((w - 0.04, 0.004, h - 0.04), (0, y0 - d + 0.006, h / 2), M.STEEL_BLACK, bevel=0.0)
    lens = p.box((w - 0.03, 0.006, h - 0.03), (0, y0 - d - 0.014, h / 2), T3.LENS_RED, bevel=0.0, wear=0.2)
    p.box((0.06, 0.06, 0.06), (0, -0.03, h / 2), M.STEEL_BLACK, bevel=0.006)
    if p.destroyed:
        p.remove(lens)
        G.xform(letters.obj, rot=(0, 18, 0), pivot=(-0.15, y0 - d, h / 2))
    elif p.worn:
        p.rotate(p.parts, rot=(0, -4, 0), pivot=(0, 0, h / 2))
    p.collider((0, -0.1, h / 2), (w, 0.2, h))


def town3_generator(p: Prop) -> None:
    """Diesel standby generator (2.1 x 1.0 x 1.45): a channel-steel skid over its belly fuel tank, the
    engine block with its manifold, the radiator and grille at one end, the alternator drum at the other,
    a control box with gauges and a run lamp on top (t3_print gauge faces; lamp_glow while it runs), and
    the exhaust stack with its rain cap. Worn: oil-black, a panel missing, the rain cap stuck open;
    destroyed: the radiator smashed in, hoses cut, the control box hanging."""
    L, W = 2.1, 0.95
    for sy in (-1, 1):
        p.box((L, 0.1, 0.16), (0, sy * (W / 2 - 0.05), 0.08), T3.PAINT_GREY, bevel=0.006, grain="X")
    p.box((L - 0.1, W - 0.12, 0.3), (0, 0, 0.28), M.STEEL_BLACK, bevel=0.01)
    p.box((0.12, 0.04, 0.08), (0.7, -W / 2 + 0.04, 0.4), M.BRASS, bevel=0.006)
    eng = p.rbox((0.9, 0.62, 0.6), (-0.15, 0, 0.75), T3.MILL_GREEN, radius=0.05, inner=(2, 2, 2), edge_deg=30)
    p.box((0.7, 0.3, 0.12), (-0.15, 0, 1.11), T3.MILL_GREEN, bevel=0.02)
    for k in range(4):
        p.tube([(-0.45 + k * 0.2, -0.32, 0.9), (-0.45 + k * 0.2, -0.42, 0.95), (-0.45 + k * 0.2, -0.42, 1.08)], 0.025, M.CAST_IRON, segs=6,
               fillet_r=0.04)
    p.tube([(-0.5, -0.42, 1.08), (0.15, -0.42, 1.08)], 0.04, M.CAST_IRON, segs=8)
    rad = [p.box((0.18, W - 0.1, 0.85), (-0.85, 0, 0.85), T3.MILL_GREEN, bevel=0.01),
           p.box((0.02, W - 0.25, 0.7), (-0.95, 0, 0.85), M.STEEL_BLACK, bevel=0.0)]
    for k in range(12):
        p.box((0.025, W - 0.26, 0.012), (-0.965, 0, 0.53 + k * 0.055), T3.GALV, bevel=0.0)
    alt = p.cyl(0.3, 0.55, (0.55, 0, 0.78), T3.MILL_GREEN, axis="X", segs=16, wear=1.0)
    for k in range(8):
        a = k * math.tau / 8
        p.box((0.5, 0.03, 0.03), (0.55, math.cos(a) * 0.3, 0.78 + math.sin(a) * 0.3), T3.MILL_GREEN, bevel=0.004)
    box = [p.box((0.5, 0.25, 0.42), (0.55, 0.15, 1.32), T3.PAINT_GREY, bevel=0.01),
           plate(p, 0.4, 0.2, (0.55, 0.15 - 0.127, 1.38), atlas("transmitter"), t=0.003),
           p.cyl(0.03, 0.03, (0.75, 0.15 - 0.14, 1.2), T3.LAMP, axis="Y", segs=10)]
    p.tube([(0.1, 0.25, 1.1), (0.1, 0.25, 1.85)], 0.055, M.CAST_IRON, segs=10)
    cap = p.box((0.13, 0.13, 0.008), (0.1, 0.25, 1.86), M.CAST_IRON, bevel=0.0)
    if p.worn:
        G.xform(cap.obj, rot=(55, 0, 0), pivot=(0.1, 0.32, 1.86))
    if p.destroyed:
        G.xform(rad[1].obj, rot=(0, 25, 0), pivot=(-0.95, 0, 0.5))
        p.rotate(box, rot=(0, 0, 35), pivot=(0.8, 0.28, 1.1))
        p.rotate(box, rot=(25, 0, 0), pivot=(0.8, 0.28, 1.1))
    p.collider((0, 0, 0.72), (L, W, 1.45))


def town3_lattice_mast(p: Prop) -> None:
    """KHLW's square lattice mast (2.2 m faces, 17 m to the beacon): four legs painted in red and white
    bands, girts and K-bracing on every face, a ladder up the inside of the south face, the rest platforms'
    frames every 3 m (the POI's kit floors are the decks), the antenna pole and dipoles over the top, the
    feeder cable and the red aviation beacon (t3_beacon_glow: it burns while the generator runs). Collision
    none: the kit platforms and railings carry the climber. Worn: rust, a brace hanging, the beacon lens
    gone."""
    S, H = 2.2, 15.0
    hs = S / 2
    seg = 1.5
    nseg = int(H / seg)
    for k in range(nseg):
        z0, z1 = k * seg, (k + 1) * seg
        mat = T3.PAINT_RED if (k // 2) % 2 == 0 else T3.PAINT_WHITE
        for sx in (-1, 1):
            for sy in (-1, 1):
                p.tube([(sx * hs, sy * hs, z0), (sx * hs, sy * hs, z1)], 0.045, mat, segs=6)
        # girts and K-braces on the four faces
        for face in range(4):
            if face == 0:
                a, b = (-hs, -hs), (hs, -hs)
            elif face == 1:
                a, b = (hs, -hs), (hs, hs)
            elif face == 2:
                a, b = (hs, hs), (-hs, hs)
            else:
                a, b = (-hs, hs), (-hs, -hs)
            mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            p.tube([(a[0], a[1], z1), (b[0], b[1], z1)], 0.022, mat, segs=4)
            if p.worn and face == 1 and k == 3:
                p.tube([(a[0], a[1], z0), (mid[0] + 0.3, mid[1] - 0.2, z0 - 0.6)], 0.016, mat, segs=4)
                continue
            p.tube([(a[0], a[1], z0), (mid[0], mid[1], z1)], 0.016, mat, segs=4)
            p.tube([(b[0], b[1], z0), (mid[0], mid[1], z1)], 0.016, mat, segs=4)
    # platform frames every 3 m (the decks are the POI's kit floors)
    base = float(p.params.get("floor_height", 0.15))
    for k in range(1, 4):
        z = k * 3.0 + base - 0.26
        for sx in (-1, 1):
            p.box((0.1, S, 0.12), (sx * (hs - 0.05), 0, z), T3.GALV, bevel=0.006, grain="Y")
            p.box((S, 0.1, 0.12), (0, sx * (hs - 0.05), z), T3.GALV, bevel=0.006, grain="X")
    # antenna pole and dipoles
    p.tube([(0, 0, H), (0, 0, H + 2.0)], 0.06, T3.GALV, segs=8)
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.tube([(sx * hs, sy * hs, H), (0, 0, H + 0.6)], 0.02, T3.GALV, segs=4)
    for k in range(3):
        z = H + 0.5 + k * 0.5
        p.tube([(-0.9, 0, z), (0.9, 0, z)], 0.015, T3.GALV, segs=4)
        p.tube([(0, -0.9, z + 0.25), (0, 0.9, z + 0.25)], 0.015, T3.GALV, segs=4)
    p.cyl(0.07, 0.04, (0, 0, H + 2.0), M.STEEL_BLACK, segs=10)
    beacon = p.lathe([(0.08, 0.0), (0.09, 0.08), (0.06, 0.17), (0.0, 0.19)], (0, 0, H + 2.04), T3.BEACON, segs=12)
    if not p.worn:
        p.lathe([(0.1, 0.0), (0.11, 0.1), (0.075, 0.2), (0.0, 0.22)], (0, 0, H + 2.03), T3.LENS_RED, segs=12)
    # feeder cable down the north-east leg
    p.tube([(hs - 0.08, hs - 0.08, 0.2), (hs - 0.08, hs - 0.08, H + 0.4), (0.05, 0.05, H + 1.0)], 0.03, M.PL_BLACK, segs=6, fillet_r=0.3)
    # base plinths and the registration plate
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.box((0.4, 0.4, 0.3), (sx * hs, sy * hs, 0.15), T3.PAINT_GREY, bevel=0.02)
    plate(p, 0.32, 0.16, (0, -hs - 0.05, 1.5), atlas("mast_plate"), t=0.004)
    p.collider((0, 0, 0.15), (S + 0.4, S + 0.4, 0.3))


def town3_mast_rail(p: Prop) -> None:
    """Platform railing section (1.0 x 1.1 x 0.06): galvanised pipe top and mid rails on posts, a toe board.
    Placed along a mast platform's edge so a climber can't step off. Worn: a rail bent outward."""
    L, H = 1.0, 1.1
    for x in (-L / 2 + 0.03, L / 2 - 0.03):
        p.tube([(x, 0, 0.0), (x, 0, H)], 0.022, T3.GALV, segs=8)
    top = p.tube([(-L / 2, 0, H), (L / 2, 0, H)], 0.022, T3.GALV, segs=8)
    mid = p.tube([(-L / 2, 0, H * 0.5), (L / 2, 0, H * 0.5)], 0.018, T3.GALV, segs=8)
    p.box((L, 0.012, 0.12), (0, 0, 0.06), T3.GALV, bevel=0.002, grain="X")
    if p.worn:
        G.xform(mid.obj, rot=(14, 0, 0), pivot=(0, 0, H * 0.5))
    p.collider((0, 0, H / 2), (L, 0.06, H))


def town3_relay_cabinet(p: Prop) -> None:
    """Weatherproof relay cabinet (0.75 x 0.45 x 1.35) on a galvanised stand: a grey steel box with a
    drip hood, louvres, a door with its padlock hasp and the station's label, the coax entry and the
    earth strap. Worn: the door sprung open on its rack of relays; destroyed: the door gone, the guts
    pulled out on their cables."""
    W, D = 0.75, 0.42
    z0, z1 = 0.45, 1.35
    for sx in (-1, 1):
        p.box((0.06, 0.06, z0), (sx * 0.25, 0.1, z0 / 2), T3.GALV, bevel=0.004, grain="Z")
    p.box((W - 0.1, 0.06, 0.06), (0, 0.1, 0.2), T3.GALV, bevel=0.004, grain="X")
    p.box((W, D, z1 - z0), (0, 0, (z0 + z1) / 2), M.STEEL_GREY, bevel=0.01)
    p.box((W + 0.08, D + 0.08, 0.03), (0, -0.02, z1 + 0.02), M.STEEL_GREY, bevel=0.006)
    for k in range(5):
        p.box((W - 0.2, 0.01, 0.012), (0, -D / 2 - 0.005, z0 + 0.1 + k * 0.03), M.STEEL_BLACK, bevel=0.0)
    door = [p.box((W - 0.06, 0.02, z1 - z0 - 0.26), (0, -D / 2 - 0.01, (z0 + z1) / 2 + 0.06), M.STEEL_GREY, bevel=0.006),
            plate(p, 0.2, 0.1, (0, -D / 2 - 0.022, z1 - 0.18), atlas("mast_plate"), t=0.002),
            p.box((0.04, 0.03, 0.08), (W / 2 - 0.08, -D / 2 - 0.03, (z0 + z1) / 2 + 0.06), M.CHROME, bevel=0.004, tags=("knob",))]
    p.tube([(W / 2 - 0.02, 0.1, z0 + 0.15), (W / 2 + 0.04, 0.12, z0 - 0.05), (W / 2 + 0.04, 0.15, 0.02)], 0.025, M.PL_BLACK, segs=6, fillet_r=0.08)
    inside = []
    if p.worn:
        for k in range(4):
            inside.append(p.box((W - 0.14, 0.2, 0.1), (0, 0.0, z0 + 0.2 + k * 0.17), M.PL_BEIGE, bevel=0.004))
            inside.append(p.box((0.1, 0.006, 0.02), (-0.2, -0.105, z0 + 0.22 + k * 0.17), T3.LED, bevel=0.0, wear=0.0))
    if p.destroyed:
        p.remove(door)
        r = p.vrng("guts")
        for q in inside[::2][1:]:
            p.lay_on_floor([q], rot=(r.uniform(-30, 30), 0, 0), at=(r.uniform(-0.3, 0.3), -D / 2 - r.uniform(0.2, 0.5)), yaw=r.uniform(0, 90))
    elif p.worn:
        p.rotate(door, rot=(0, 0, -110), pivot=(-W / 2 + 0.03, -D / 2 - 0.02, 0))
    p.collider((0, 0, z1 / 2), (W, D, z1))


BUILDERS = {
    "town3_washer": town3_washer,
    "town3_dryer": town3_dryer,
    "town3_folding_table": town3_folding_table,
    "town3_laundry_cart": town3_laundry_cart,
    "town3_change_machine": town3_change_machine,
    "facade_sign": facade_sign,
    "town3_grocery_shelf": town3_grocery_shelf,
    "town3_grocery_shelf_fallen": town3_grocery_shelf_fallen,
    "town3_cooler_case": town3_cooler_case,
    "town3_butcher_counter": town3_butcher_counter,
    "town3_reefer_trailer": town3_reefer_trailer,
    "town3_forklift": town3_forklift,
    "town3_lumber_rack": town3_lumber_rack,
    "town3_grain_bin": town3_grain_bin,
    "town3_library_stack": town3_library_stack,
    "town3_card_catalog": town3_card_catalog,
    "town3_reading_table": town3_reading_table,
    "town3_circulation_desk": town3_circulation_desk,
    "town3_book_cart": town3_book_cart,
    "town3_kids_table": town3_kids_table,
    "town3_studio_desk": town3_studio_desk,
    "town3_equipment_rack": town3_equipment_rack,
    "town3_transmitter": town3_transmitter,
    "town3_on_air_sign": town3_on_air_sign,
    "town3_generator": town3_generator,
    "town3_lattice_mast": town3_lattice_mast,
    "town3_mast_rail": town3_mast_rail,
    "town3_relay_cabinet": town3_relay_cabinet,
}


def _face_key(f) -> tuple:
    c = f.calc_center_median()
    n = f.normal
    return (round(c.x, 5), round(c.y, 5), round(c.z, 5), round(n.x, 3), round(n.y, 3), round(n.z, 3), f.material_index)


def _triangulated(fn):
    """Runs a builder, then triangulates every part with fixed diagonals and puts its faces in a canonical
    order: the exporter's own quad split and the face order some bmesh ops leave both varied from run to
    run, which broke byte-identical rebuilds (build_assets.py --check-determinism)."""
    def run(p: Prop) -> None:
        fn(p)
        for q in p.parts:
            if q.obj is None:
                continue
            me = q.obj.data
            bm = bmesh.new()
            bm.from_mesh(me)
            bmesh.ops.triangulate(bm, faces=bm.faces, quad_method="FIXED", ngon_method="EAR_CLIP")
            # Some bmesh ops (inset, extrude) emit faces in a memory-dependent order: sort them by
            # where they are so the joined mesh (and the exported index buffer) is the same every run.
            bm.faces.index_update()
            rank = {f.index: i for i, f in enumerate(sorted(bm.faces, key=_face_key))}
            bm.faces.sort(key=lambda f: rank[f.index])
            bm.to_mesh(me)
            bm.free()
    return run


def build(params: dict, outputs: list[str]) -> None:
    core.build_variants(params, outputs, _triangulated(BUILDERS[params.get("builder", params["prop"])]))
