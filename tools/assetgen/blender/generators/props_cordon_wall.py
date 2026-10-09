"""The Cordon wall (DESIGN section 1): the precast line the government stood round the valley, and the
pieces of it on the main map's south edge (region D7) where Route 9 and the Tamsin leave the valley.

  cordon_wall_panel      6.0 m of wall: four 1.5 m precast T-wall segments (inverted-T section: a 1.5 m
                         base, a stem tapering from 0.36 to 0.22 m, 6.0 m tall) on one line, a concertina
                         coil and three barbed strands on outrigger posts along the top, the valley face's
                         QUARANTINE BOUNDARY band, the outer face's CORDON AUTHORITY band, a segment mark.
                         Its ends are flush at x = +-3.0: panels tile end to end at a 6.0 m pitch.
  cordon_wall_gate       12.0 m (two panels' pitch): a T-wall pier at each end, a steel gantry between them
                         carrying the CORDON GATE - ROUTE 9 plate and two floodlights, a pair of barred
                         swing leaves (9.0 m between the piers) chained and padlocked in the middle with a drop
                         rod into the road, a concertina coil over them; on the valley side, in front of the
                         right pier, the checkpoint booth (enterable, door on its road side).
  cordon_river_gate      one 6.0 m bay of the culvert that carries the wall over the river: half a pier at each
                         end (two bays side by side make a full 0.8 m pier and its cutwater on the valley,
                         upstream side), a concrete apron, the lintel wall over a 5.2 x 3.6 m water opening
                         filled by a steel trash-rack grate (water passes, people don't), the DANGER - SLUICE
                         plate, a waterline stain; 8.0 m tall from the river bed. Bays tile at 6.0 m.
  cordon_river_abutment  3.0 m end block standing in the bank at each end of a run of bays, with wingwalls
                         flaring upstream and downstream to hold the bank; 8.0 m tall from the bed; symmetric
                         front to back, so the far bank's is the same prop turned 180 degrees.
  cordon_notice_board    the Program's notice board for Waystation 9: a steel-framed board under a tin hood
                         (wall-mounted: origin on the wall plane), PROGRAM NOTICES header, the roundel, two
                         typed notices and scrawled slips.

Built on the interior-props framework (lib/props_int_core.py) and the Waystation kit's helpers
(generators/props_waystation.py: concertina coil, bars, plates, sandbags, floodlight heads). Conventions:
metres, Z up, front -Y (Godot +Z) = the VALLEY side (inside the Cordon). Origin: on the wall line, at the
foot (bottom centre of the stem's line); the river pieces' origin is on the river bed. Graphics come from
textures/gen/cordon.py (cordon_print; ATLAS below mirrors PRINT_RECTS there) and the waystation atlas.

params: prop (id), seed, variants, mount, budget (see blender_catalogs/props_cordon_wall.py).
"""
from __future__ import annotations

import math

from mathutils import Matrix, Vector

from generators.props_waystation import C, bar, coil, lamp_head, place, plate, rod, roof_sheet, sandbag_row, sheet_box
from generators.props_waystation import atlas as ws_atlas
from lib import materials
from lib import props_int_core as core
from lib import props_int_mesh as G
from lib.props_int_core import Prop


class W:
    """Material ids of this family (game/data/materials/props_cordon.json)."""
    PRINT = "cw_print"
    CONC = "cw_concrete"
    WET = "cw_concrete_wet"
    STEEL_DARK = "cw_steel_dark"


materials.PREVIEW_COLORS.update({
    W.PRINT: (0.6, 0.6, 0.55), W.CONC: (0.42, 0.41, 0.38), W.WET: (0.22, 0.24, 0.2), W.STEEL_DARK: (0.12, 0.12, 0.11),
})

# cordon_print atlas rects (x0, y0, x1, y1) in pixels of the 2048 px texture - mirror of
# textures/gen/cordon.py PRINT_RECTS.
ATLAS_SIZE = 2048.0
ATLAS: dict[str, tuple[int, int, int, int]] = {
    "valley": (0, 0, 2048, 512),
    "outer": (0, 512, 2048, 768),
    "gate": (0, 768, 1536, 1024),
    "segment": (1536, 768, 2048, 1024),
    "sluice": (0, 1024, 1536, 1280),
    "booth": (1536, 1024, 2048, 1152),
    "notices": (1536, 1152, 2048, 1280),
    "notice0": (0, 1280, 384, 1792),
    "notice1": (384, 1280, 768, 1792),
    "roundel": (768, 1280, 1280, 1792),
    "chevron": (1280, 1280, 2048, 1536),
}

# The wall: everything the game data repeats (data/props/cordon.json sizes and boxes) comes from here.
PITCH = 6.0            # panel length = tiling pitch along the wall line
SEG = 1.5              # one precast T-wall segment
JOINT = 0.015          # half the gap between segments
H = 6.0                # top of the concrete above the foot
BASE_D = 1.5           # base depth (front to back), centred on the wall line
BASE_H = 0.36
STEM_B, STEM_T = 0.36, 0.22   # stem thickness at the haunch and at the top
WIRE_H = 0.9           # coil and strands above the top
RIVER_H = 8.0          # river pieces: top above the bed
OPEN_W, OPEN_H = 5.2, 3.6     # a bay's water opening
PIER_D = 2.4           # culvert depth (front to back)


def atlas(name: str, inset: float = 1.5) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = ATLAS[name]
    return core._px_rect(x0 + inset, y0 + inset, x1 - inset, y1 - inset, ATLAS_SIZE)


def _profile() -> list[tuple[float, float]]:
    """The T-wall's section in (y, z), counter-clockwise seen from +X: base with chamfered top edges, haunches,
    the tapering stem."""
    b, hb = BASE_D / 2, BASE_H
    return [(-b, 0.0), (b, 0.0), (b, hb - 0.04), (b - 0.04, hb), (STEM_B / 2 + 0.16, hb), (STEM_B / 2, hb + 0.22),
            (STEM_T / 2, H), (-STEM_T / 2, H), (-STEM_B / 2, hb + 0.22), (-STEM_B / 2 - 0.16, hb), (-b + 0.04, hb),
            (-b, hb - 0.04)]


def stem_half(z: float) -> float:
    """Half the stem's thickness at height z (the face planes are y = -+stem_half(z))."""
    z0 = BASE_H + 0.22
    if z <= z0:
        return STEM_B / 2
    return STEM_B / 2 + (STEM_T / 2 - STEM_B / 2) * (z - z0) / (H - z0)


def t_segment(p: Prop, x0: float, x1: float, *, mat: str = W.CONC) -> core.Part:
    """One precast segment between x0 and x1 (joint chamfers on its ends), its two lifting anchors."""
    part = p.prism(_profile(), x1 - x0, mat, plane="YZ", offset=x0, bevel=0.02, uv_scale=0.5, wear=0.5)
    cx = (x0 + x1) / 2
    for dx in (-0.35, 0.35):
        p.box((0.09, 0.09, 0.012), (cx + dx, 0, H + 0.003), W.STEEL_DARK, bevel=0.0, wear=0.2)
    return part


def wall_face_plate(p: Prop, w: float, h: float, x: float, zc: float, rect, *, front: bool = True,
                    mat: str = W.PRINT, wear: float = 0.5) -> core.Part:
    """A painted band on the stem: on the valley face (front, -Y) or the outer face, tilted to the stem's
    taper and standing 4 mm proud of it."""
    tilt = math.degrees(math.atan((STEM_B / 2 - STEM_T / 2) / (H - BASE_H - 0.22)))
    y = stem_half(zc) + 0.004
    if front:
        return plate(p, w, h, (x, -y, zc), rect, t=0.002, rot=(-tilt, 0, 0), mat=mat, wear=wear)
    return plate(p, w, h, (x, y, zc), rect, t=0.002, rot=(-tilt, 0, 180), mat=mat, wear=wear)


def wire_top(p: Prop, x0: float, x1: float, z: float, *, key: str, posts: list[float], sag: float = 0.0) -> None:
    """Outrigger posts bolted to the top, three barbed strands and a concertina coil between x0 and x1 (the
    coil runs to the ends so neighbours meet)."""
    for x in posts:
        p.box((0.05, 0.05, WIRE_H), (x, 0.0, z + WIRE_H / 2), C.OLIVE, bevel=0.003, wear=0.8)
        p.box((0.16, 0.12, 0.012), (x, 0.0, z + 0.006), C.OLIVE, bevel=0.0)
    for k, (dy, dz) in enumerate(((-0.03, 0.3), (0.03, 0.6), (0.0, WIRE_H - 0.04))):
        rod(p, (x0, dy, z + dz), (x1, dy, z + dz), 0.004, C.STEEL, segs=3, cap=False, wear=0.4)
    coil(p, (x0, 0, z + 0.3), (x1, 0, z + 0.3), 0.3, 0.22, key=key, per_turn=8, sag=sag, wobble=0.08 if not sag else 0.14)


def rubble(p: Prop, x: float, y: float, n: int, key: str, mat: str = W.CONC) -> None:
    """Spalled concrete chunks at a foot (worn)."""
    r = p.vrng(key)
    for i in range(n):
        s = r.uniform(0.08, 0.2)
        part = p.rbox((s * 1.3, s, s * 0.7), (0, 0, 0), mat, radius=s * 0.25, inner=(1, 1, 1), wrinkle=0.01,
                      seed=p.seed + i, uv_scale=0.5)
        G.xform(part.obj, rot=(r.uniform(-20, 20), r.uniform(-20, 20), r.uniform(0, 180)),
                loc=(x + r.uniform(-0.4, 0.4), y + r.uniform(-0.15, 0.15), s * 0.3))


# ================================================================================================
# 1. the wall panel
# ================================================================================================

def wall_colliders(p: Prop, x0: float, x1: float) -> None:
    """Base, stem and wire boxes between x0 and x1 (mirrored in data/props/cordon.json boxes)."""
    w, cx = x1 - x0, (x0 + x1) / 2
    p.collider((cx, 0, BASE_H / 2), (w, BASE_D, BASE_H))
    p.collider((cx, 0, BASE_H + (H - BASE_H) / 2), (w, STEM_B, H - BASE_H))
    p.collider((cx, 0, H + WIRE_H / 2), (w, 0.7, WIRE_H))


def cordon_wall_panel(p: Prop) -> None:
    """Wall panel (6.0 x 6.9 x 1.5): four T-wall segments, the wire, the painted bands. Worn: grime, a spalled
    base with chunks at its foot, the coil sagging, a stain run down from an anchor."""
    worn = p.worn
    half = PITCH / 2
    for k in range(4):
        x0 = -half + k * SEG
        t_segment(p, x0 + JOINT, x0 + SEG - JOINT)
    wire_top(p, -half, half, H, key="coil", posts=[-half + SEG * (k + 0.5) for k in range(4)], sag=0.12 if worn else 0.0)
    wall_face_plate(p, 4.0, 1.0, 0.0, 2.75, atlas("valley"), front=True, wear=0.7 if worn else 0.4)
    wall_face_plate(p, 4.0, 0.5, 0.0, 4.6, atlas("outer"), front=False)
    wall_face_plate(p, 0.8, 0.4, 2.25, 0.95, atlas("segment"), front=True)
    if worn:
        rubble(p, -1.2, -BASE_D / 2 - 0.1, 4, "spall")
        p.box((0.06, 0.004, 1.8), (0.4, -stem_half(4.9) - 0.003, 4.9), W.WET, bevel=0.0, wear=0.0)
    wall_colliders(p, -half, half)


# ================================================================================================
# 2. the Route 9 gate
# ================================================================================================

BOOTH = (3.85, 5.85, -3.05, -1.05)   # booth x0, x1, y0 (front), y1 (back) in Blender metres


def _leaf(p: Prop, x0: float, x1: float, z0: float, z1: float, *, key: str, sag: float = 0.0) -> list:
    """One barred swing leaf between x0 and x1 (hinge at x0's side when x0 is the outer end): a box-section
    frame, a mid rail, vertical bars every ~0.2 m, a diagonal brace and a chevron kick plate on the valley face."""
    out = []
    t = 0.08
    w = x1 - x0
    out.append(p.box((w, t, t), ((x0 + x1) / 2, 0, z0 + t / 2), C.OLIVE, bevel=0.004, grain="X"))
    out.append(p.box((w, t, t), ((x0 + x1) / 2, 0, z1 - t / 2), C.OLIVE, bevel=0.004, grain="X"))
    out.append(p.box((w, 0.06, 0.06), ((x0 + x1) / 2, 0, (z0 + z1) / 2), C.OLIVE, bevel=0.004, grain="X"))
    for x in (x0 + t / 2, x1 - t / 2):
        out.append(p.box((t, t, z1 - z0), (x, 0, (z0 + z1) / 2), C.OLIVE, bevel=0.004))
    n = int(round((w - 2 * t) / 0.2))
    for i in range(1, n):
        x = x0 + t + (w - 2 * t) * i / n
        out.append(p.box((0.025, 0.025, z1 - z0 - 2 * t), (x, 0, (z0 + z1) / 2), C.OLIVE, bevel=0.0, wear=0.6))
    out.append(bar(p, (x0 + t, -0.05, z0 + t), (x1 - t, -0.05, z1 - t), 0.05, 0.05, C.OLIVE))
    out.append(plate(p, w - 2 * t, 0.42, ((x0 + x1) / 2, -0.045, z0 + t + 0.22), atlas("chevron"), t=0.004, mat=W.PRINT, wear=0.8))
    if sag:
        place(out, Matrix.Translation((x0, 0, z0)) @ Matrix.Rotation(math.radians(sag), 4, "Y") @ Matrix.Translation((-x0, 0, -z0)))
    return out


def _booth(p: Prop, worn: bool) -> None:
    """Checkpoint booth on the valley side: a concrete slab, an olive steel cabin with a band of windows on the
    front and the road side, a door opening on the road (-X) side, a tin roof with the CHECKPOINT 9 board, a
    shelf with a field phone and a log, a stool, sandbags along the front."""
    x0, x1, y0, y1 = BOOTH
    z_top = 2.55
    p.box((x1 - x0 + 0.2, y1 - y0 + 0.2, 0.12), ((x0 + x1) / 2, (y0 + y1) / 2, 0.06), C.CONCRETE, bevel=0.01)
    zf = 0.12
    t = 0.04
    # corner posts
    for x in (x0 + 0.04, x1 - 0.04):
        for y in (y0 + 0.04, y1 - 0.04):
            p.box((0.08, 0.08, z_top - zf), (x, y, (zf + z_top) / 2), C.OLIVE, bevel=0.004)
    # walls: back full height, the right (+X) full height, the front and the road side with a window band
    WIN0, WIN1 = 1.05, 2.0
    sheet_box(p, x0, x1, y1 - t, y1, zf, z_top)
    sheet_box(p, x1 - t, x1, y0, y1, zf, z_top)
    sheet_box(p, x0, x1, y0, y0 + t, zf, WIN0)
    sheet_box(p, x0, x1, y0, y0 + t, WIN1, z_top)
    DOOR0, DOOR1 = y0 + 0.7, y0 + 1.6     # door gap on the road side (-X wall)
    sheet_box(p, x0, x0 + t, y0, DOOR0, zf, WIN0)
    sheet_box(p, x0, x0 + t, y0, DOOR0, WIN1, z_top)
    sheet_box(p, x0, x0 + t, DOOR1, y1, zf, z_top)
    sheet_box(p, x0, x0 + t, DOOR0, DOOR1, 2.1, z_top)
    # glazing (one pane cracked out when worn)
    p.box((x1 - x0 - 0.16, 0.008, WIN1 - WIN0), ((x0 + x1) / 2, y0 + 0.02, (WIN0 + WIN1) / 2), C.LENS, bevel=0.0, wear=0.0)
    if not worn:
        p.box((0.008, DOOR0 - y0 - 0.1, WIN1 - WIN0), (x0 + 0.02, (y0 + DOOR0) / 2, (WIN0 + WIN1) / 2), C.LENS, bevel=0.0, wear=0.0)
    p.box((x1 - x0, 0.06, 0.05), ((x0 + x1) / 2, y0 + 0.03, WIN0 - 0.02), C.OLIVE, bevel=0.003, grain="X")
    # roof and its board
    roof_sheet(p, x0 - 0.25, x1 + 0.12, y0 - 0.35, z_top + 0.05, y1 + 0.1, z_top + 0.2, C.ROOF_RUST if worn else C.ROOF)
    plate(p, 1.6, 0.4, ((x0 + x1) / 2, y0 - 0.37, z_top - 0.12), atlas("booth"), t=0.01, mat=W.PRINT)
    # inside: a shelf under the front window, the field phone, a log book, a stool
    p.box((x1 - x0 - 0.2, 0.35, 0.03), ((x0 + x1) / 2 + 0.05, y0 + 0.22, 1.0), C.PLY, bevel=0.003, grain="X")
    p.box((0.22, 0.16, 0.1), (x1 - 0.5, y0 + 0.2, 1.065), C.OLIVE, bevel=0.01)
    p.box((0.05, 0.22, 0.05), (x1 - 0.5, y0 + 0.2, 1.14), C.PL_BLACK, bevel=0.01)
    p.box((0.3, 0.22, 0.03), (x0 + 0.9, y0 + 0.22, 1.03), C.CARD, bevel=0.002)
    p.cyl(0.17, 0.03, (x0 + 1.0, y0 + 0.95, 0.75), C.WOOD, segs=10)
    for a in range(3):
        ang = math.radians(90 + a * 120)
        rod(p, (x0 + 1.0 + math.cos(ang) * 0.06, y0 + 0.95 + math.sin(ang) * 0.06, 0.74),
            (x0 + 1.0 + math.cos(ang) * 0.17, y0 + 0.95 + math.sin(ang) * 0.17, zf), 0.015, C.STEEL, segs=4)
    # sandbags along the front, two courses (a gap where a bag split when worn)
    for row in range(2):
        sandbag_row(p, (x0 + 0.1 + row * 0.15, y0 - 0.35, row * 0.17), x1 - x0 - 0.3 - row * 0.15, 5 - row,
                    mat=C.BAG_TAN if row == 0 else C.BAG_OLIVE, key=f"bb{row}", slump=0.6 if worn else 0.0,
                    skip=(2,) if worn and row == 1 else ())
    # colliders: the walls (door gap left open), the roof, the bags
    p.collider(((x0 + x1) / 2, y1 - t / 2, z_top / 2), (x1 - x0, 0.1, z_top))
    p.collider((x1 - t / 2, (y0 + y1) / 2, z_top / 2), (0.1, y1 - y0, z_top))
    p.collider(((x0 + x1) / 2, y0 + t / 2, z_top / 2), (x1 - x0, 0.1, z_top))
    p.collider((x0 + t / 2, (y0 + DOOR0) / 2, z_top / 2), (0.1, DOOR0 - y0, z_top))
    p.collider((x0 + t / 2, (DOOR1 + y1) / 2, z_top / 2), (0.1, y1 - DOOR1, z_top))
    p.collider(((x0 + x1) / 2, (y0 + y1) / 2, z_top + 0.12), (x1 - x0 + 0.3, y1 - y0 + 0.4, 0.15))
    p.collider(((x0 + x1) / 2, y0 - 0.35, 0.17), (x1 - x0 - 0.2, 0.32, 0.34))


GATE_W = 12.0
PIER_W = 1.5
LEAF_TOP = 4.3


def cordon_wall_gate(p: Prop) -> None:
    """Route 9 gate (12.0 x 6.9 x 3.75): T-wall piers, the gantry, the chained leaves, the booth. Worn: the
    right leaf sags on its hinges, a floodlight smashed, rust, grime, chunks at the piers' feet."""
    worn = p.worn
    half = GATE_W / 2
    inner = half - PIER_W
    for sx in (-1, 1):
        a, b = sorted((sx * half, sx * inner))
        t_segment(p, a + JOINT, b - JOINT)
        wire_top(p, a, b, H, key=f"pcoil{sx}", posts=[(a + b) / 2])
        wall_face_plate(p, 0.8, 0.4, (a + b) / 2, 0.95, atlas("segment"), front=True)
    # gantry: brackets bolted to the piers' inner ends, a box beam across, the plate and two floodlights
    BZ = 5.55
    for sx in (-1, 1):
        x = sx * (inner - 0.02)
        p.box((0.3, 0.3, 0.6), (x + sx * 0.14, 0, BZ), C.STEEL, bevel=0.006)
    p.box((2 * inner + 0.2, 0.26, 0.4), (0, 0, BZ + 0.05), C.OLIVE, bevel=0.008, grain="X")
    p.box((2 * inner + 0.2, 0.3, 0.03), (0, 0, BZ + 0.265), C.OLIVE, bevel=0.003, grain="X")
    p.box((3.7, 0.04, 0.68), (0, -0.16, BZ - 0.05), C.OLIVE, bevel=0.004)
    plate(p, 3.6, 0.6, (0, -0.185, BZ - 0.05), atlas("gate"), t=0.006, mat=W.PRINT)
    for k, sx in enumerate((-1, 1)):
        lamp_head(p, (sx * 2.9, -0.32, BZ - 0.18), tilt=32, yaw=sx * -6, broken=worn and sx > 0)
        bar(p, (sx * 2.9, -0.13, BZ - 0.05), (sx * 2.9, -0.32, BZ - 0.05), 0.05, 0.05, C.OLIVE)
    p.tube([(-2.9, -0.2, BZ - 0.12), (-2.9, -0.14, BZ + 0.25), (2.9, -0.14, BZ + 0.25), (2.9, -0.2, BZ - 0.12)], 0.012,
           C.RUBBER, segs=4, wear=0.2)
    # the leaves: hinged on the piers, meeting in the middle
    Z0 = 0.12
    for sx in (-1, 1):
        x_h = sx * inner
        for z in (0.5, 2.2, 3.9):
            p.cyl(0.035, 0.18, (x_h - sx * 0.02, 0.0, z), C.STEEL, segs=8)
            p.box((0.12, 0.05, 0.12), (x_h + sx * 0.05, 0.0, z), C.STEEL, bevel=0.004)
        a, b = sorted((x_h - sx * 0.04, sx * 0.03))
        hinge = a if sx < 0 else b
        lf = _leaf(p, a, b, Z0, LEAF_TOP, key=f"leaf{sx}", sag=0.0)
        if worn and sx > 0:
            place(lf, Matrix.Translation((hinge, 0, LEAF_TOP)) @ Matrix.Rotation(math.radians(-0.9), 4, "Y")
                  @ Matrix.Translation((-hinge, 0, -LEAF_TOP)))
    # chain round the two meeting stiles, the padlock, the drop rod
    CZ = 1.25
    loop = []
    for k in range(13):
        a = 2 * math.pi * k / 12
        loop.append((math.cos(a) * 0.13, math.sin(a) * 0.075, CZ + math.sin(a * 2) * 0.03 - k * 0.004))
    p.tube(loop, 0.01, C.CHAIN, segs=4, wear=0.5)
    p.tube([(0.05, -0.07, CZ - 0.04), (0.06, -0.1, CZ - 0.25), (0.08, -0.08, CZ - 0.5)], 0.01, C.CHAIN, segs=4, wear=0.5)
    p.box((0.06, 0.03, 0.07), (0.0, -0.09, CZ - 0.07), "trap_brass", bevel=0.006)
    p.box((0.025, 0.025, 0.95), (-0.12, -0.06, 0.48), C.STEEL, bevel=0.0)
    p.box((0.08, 0.04, 0.04), (-0.12, -0.06, 0.95), C.STEEL, bevel=0.003)
    # concertina over the leaves (on a light rail between the piers)
    rod(p, (-inner, 0, LEAF_TOP + 0.02), (inner, 0, LEAF_TOP + 0.02), 0.012, C.STEEL, segs=4)
    coil(p, (-inner, 0, LEAF_TOP + 0.28), (inner, 0, LEAF_TOP + 0.28), 0.28, 0.24, key="gcoil", per_turn=8,
         sag=0.08 if worn else 0.0)
    # road rail the leaves close onto
    p.box((2 * inner, 0.12, 0.03), (0, 0, 0.015), W.STEEL_DARK, bevel=0.002, grain="X")
    _booth(p, worn)
    if worn:
        rubble(p, -inner - 0.6, -BASE_D / 2 - 0.1, 3, "spall_l")
    # colliders: piers (as wall), the leaves (to the top of their coil), the gantry; the booth's own above
    for sx in (-1, 1):
        a, b = sorted((sx * half, sx * inner))
        wall_colliders(p, a, b)
    p.collider((0, 0, (LEAF_TOP + 0.56) / 2), (2 * inner, 0.2, LEAF_TOP + 0.56))
    p.collider((0, 0, BZ + 0.05), (2 * inner, 0.3, 0.45))


# ================================================================================================
# 3. the river gate: one culvert bay, and the abutment
# ================================================================================================

def _nose(p: Prop, x: float, sx: int, mat: str) -> None:
    """Half a cutwater on the upstream (valley, -Y) face of the half-pier at the bay end x (sx: which side of x
    the half lies on), up to 4.2 m (above the design flood)."""
    y0 = -PIER_D / 2
    poly = [(0.0, y0), (0.0, y0 - 0.55), (sx * 0.4, y0)] if sx > 0 else [(0.0, y0), (sx * 0.4, y0), (0.0, y0 - 0.55)]
    # prism in XY extruded along +Z: counter-clockwise seen from above
    p.prism([(x + u, v) for u, v in poly], 4.2, mat, plane="XY", offset=0.0, uv_scale=0.5, wear=0.6)
    p.prism([(x + u, v) for u, v in poly], 0.25, W.CONC, plane="XY", offset=4.2, uv_scale=0.5, wear=0.6)


def cordon_river_gate(p: Prop) -> None:
    """River bay (6.0 x 8.9 x 2.95 from the bed): the apron, two half-piers with half cutwaters, the lintel
    wall, the trash rack, the plate, the wire. Worn: drift caught on the rack (a log and branches), the rack
    rusted, a bar bent, grime streaks."""
    worn = p.worn
    half = PITCH / 2
    OW = OPEN_W / 2
    WL = 2.0   # waterline stain height
    # apron (under the water)
    p.box((PITCH, PIER_D, 0.3), (0, 0, -0.15), W.WET, bevel=0.01, uv_scale=0.5, wear=0.3)
    for sx in (-1, 1):
        a, b = sorted((sx * half, sx * OW))
        cx = (a + b) / 2
        p.box((b - a, PIER_D, WL), (cx, 0, WL / 2), W.WET, bevel=0.01, uv_scale=0.5, wear=0.6)
        p.box((b - a, PIER_D, RIVER_H - WL), (cx, 0, WL + (RIVER_H - WL) / 2), W.CONC, bevel=0.01, uv_scale=0.5, wear=0.6)
        _nose(p, sx * half, -sx, W.WET)
        # grate guide channels on the pier faces
        p.box((0.1, 0.16, OPEN_H + 0.2), (sx * (OW - 0.05), -0.42, (OPEN_H + 0.2) / 2), W.STEEL_DARK, bevel=0.004)
    # the lintel wall over the opening, a beam course at its foot
    LT = 0.6
    p.box((OPEN_W, LT + 0.3, 0.6), (0, 0, OPEN_H + 0.3), W.CONC, bevel=0.02, uv_scale=0.5, wear=0.6, grain="X")
    p.box((OPEN_W, LT, RIVER_H - OPEN_H - 0.6), (0, 0, OPEN_H + 0.6 + (RIVER_H - OPEN_H - 0.6) / 2), W.CONC, bevel=0.01,
          uv_scale=0.5, wear=0.5)
    plate(p, 4.2, 0.7, (0, -LT / 2 - 0.004, OPEN_H + 1.25), atlas("sluice"), t=0.002, mat=W.PRINT, wear=0.6)
    plate(p, 3.4, 0.425, (0, LT / 2 + 0.004, RIVER_H - 1.2), atlas("outer"), t=0.002, mat=W.PRINT, rot=(0, 0, 180))
    # trash rack: flat bars on two horizontal bearers, across the whole opening
    GY = -0.42
    nb = 28
    bent = p.vrng("bent").randrange(4, nb - 4) if worn else -1
    for i in range(nb + 1):
        x = -OW + 0.06 + (OPEN_W - 0.12) * i / nb
        bb = p.box((0.02, 0.08, OPEN_H), (x, GY, OPEN_H / 2), C.STEEL if not worn else W.STEEL_DARK, bevel=0.0, wear=0.8)
        if i == bent:
            G.xform(bb.obj, rot=(9, 0, 0), pivot=(x, GY, OPEN_H))
    for z in (0.35, 1.8, OPEN_H - 0.15):
        p.box((OPEN_W, 0.1, 0.08), (0, GY + 0.06, z), W.STEEL_DARK, bevel=0.003, grain="X")
    # wire along the top (runs to the ends: neighbouring bays meet)
    wire_top(p, -half, half, RIVER_H, key="rcoil", posts=[-1.5, 1.5], sag=0.1 if worn else 0.0)
    if worn:
        r = p.vrng("drift")
        log = p.cyl(0.16, 3.6, (0, 0, 0), "w3_log_bark", axis="X", segs=8)
        G.xform(log.obj, rot=(0, 7, r.uniform(-4, 4)), loc=(-0.4, GY - 0.25, 1.15))
        for k in range(4):
            br = rod(p, (0, 0, 0), (r.uniform(0.9, 1.6), 0, 0), 0.03, C.WOOD, segs=4)
            G.xform(br.obj, rot=(0, r.uniform(-50, -20), r.uniform(-30, 30)), loc=(r.uniform(-2.2, 2.0), GY - 0.12, r.uniform(0.6, 1.5)))
        p.box((0.05, 0.004, 2.6), (1.2, -LT / 2 - 0.003, RIVER_H - 1.4), W.WET, bevel=0.0, wear=0.0)
    # colliders (data/props/cordon.json mirrors them)
    for sx in (-1, 1):
        a, b = sorted((sx * half, sx * OW))
        p.collider(((a + b) / 2, 0, RIVER_H / 2), (b - a, PIER_D, RIVER_H))
        p.collider(((a + b) / 2, -PIER_D / 2 - 0.275, 4.45 / 2), (b - a, 0.55, 4.45))
    p.collider((0, 0, OPEN_H + (RIVER_H - OPEN_H) / 2), (OPEN_W, LT + 0.3, RIVER_H - OPEN_H))
    p.collider((0, GY, OPEN_H / 2), (OPEN_W, 0.14, OPEN_H))
    p.collider((0, 0, RIVER_H + WIRE_H / 2), (PITCH, 0.7, WIRE_H))


ABUT_L = 3.0
WING_L = 2.6
WING_A = 32.0     # degrees the wingwalls flare away from the river (toward -X, the land)


def cordon_river_abutment(p: Prop) -> None:
    """Abutment (3.0 m along the wall, 8.0 m from the bed; wingwalls to y = +-3.4): a mass concrete block whose
    river face is x = +1.5 (a bay butts on it), wingwalls stepping down from 8.0 to 3.0 m. Worn: grime, the
    waterline, chunks spalled at the river foot."""
    worn = p.worn
    half = ABUT_L / 2
    WL = 2.0
    p.box((ABUT_L, PIER_D, WL), (0, 0, WL / 2), W.WET, bevel=0.01, uv_scale=0.5, wear=0.6)
    p.box((ABUT_L, PIER_D, RIVER_H - WL), (0, 0, WL + (RIVER_H - WL) / 2), W.CONC, bevel=0.015, uv_scale=0.5, wear=0.6)
    p.box((ABUT_L, PIER_D + 0.1, 0.18), (0, 0, RIVER_H - 0.09), W.CONC, bevel=0.01, uv_scale=0.5, wear=0.6)
    # wingwalls: a sloped-top slab from each river-side corner, turned away from the river
    T = 0.45
    for sy in (-1, 1):
        poly = [(0.0, 0.0), (WING_L, 0.0), (WING_L, 3.0), (0.0, RIVER_H - 0.3)]
        wing = p.prism(poly, T, W.CONC, plane="XZ", offset=-T / 2, uv_scale=0.5, wear=0.6)
        # built along +X in the XZ plane, T thick in Y: turned to run outward (+-Y), flared WING_A toward the
        # land (-X), standing at the river face's corner
        G.xform(wing.obj, rot=(0, 0, _wing_yaw(sy)), loc=_wing_root(sy))
    plate(p, 0.8, 0.4, (-0.6, -PIER_D / 2 - 0.006, 2.6), atlas("segment"), t=0.002, mat=W.PRINT)
    plate(p, 0.8, 0.4, (-0.6, PIER_D / 2 + 0.006, 2.6), atlas("segment"), t=0.002, mat=W.PRINT, rot=(0, 0, 180))
    wire_top(p, -half, half, RIVER_H, key="acoil", posts=[0.0], sag=0.1 if worn else 0.0)
    if worn:
        rubble(p, half - 0.2, -PIER_D / 2 - 0.2, 3, "spall_a", W.WET)
    p.collider((0, 0, RIVER_H / 2), (ABUT_L, PIER_D, RIVER_H))
    p.collider((0, 0, RIVER_H + WIRE_H / 2), (ABUT_L, 0.7, WIRE_H))
    for sy in (-1, 1):
        yaw = _wing_yaw(sy)
        d = Vector((math.cos(math.radians(yaw)), math.sin(math.radians(yaw)), 0.0))
        c = Vector(_wing_root(sy)) + d * (WING_L / 2)
        p.collider((c.x, c.y, 2.75), (WING_L, T, 5.5), rot=(0, 0, yaw))


def _wing_yaw(sy: int) -> float:
    """Degrees about Z turning +X onto a wingwall's run: outward along sy*Y, flared WING_A toward -X."""
    return sy * (90.0 + WING_A)


def _wing_root(sy: int) -> tuple[float, float, float]:
    return (ABUT_L / 2 - 0.45 / 2, sy * PIER_D / 2, 0.0)


# ================================================================================================
# 4. the Program's notice board (wall-mounted)
# ================================================================================================

def cordon_notice_board(p: Prop) -> None:
    """Program notice board (1.7 x 1.45 x 0.24; wall-mounted, origin on the wall plane at the board's bottom
    centre - hang it at ~1.0 m): a steel channel frame on two wall brackets, a plywood back, the PROGRAM NOTICES
    header between two roundels, two typed notices, the waystation atlas's sheets and slips, a tin hood. Worn: a
    notice hanging by one pin, the hood rusted."""
    worn = p.worn
    W_, H_ = 1.6, 1.2
    Y = -0.05   # board face plane (in front of the wall at y = 0)
    for sx in (-1, 1):
        p.box((0.06, 0.03, H_ + 0.1), (sx * (W_ / 2 - 0.25), -0.015, H_ / 2), C.STEEL, bevel=0.003)
    p.box((W_, 0.02, H_), (0, Y + 0.01, H_ / 2), C.PLY, bevel=0.003, grain="X")
    for z in (0.02, H_ - 0.02):
        p.box((W_ + 0.06, 0.05, 0.04), (0, Y - 0.005, z), C.OLIVE, bevel=0.004, grain="X")
    for sx in (-1, 1):
        p.box((0.04, 0.05, H_), (sx * (W_ / 2 + 0.01), Y - 0.005, H_ / 2), C.OLIVE, bevel=0.004)
    plate(p, 1.0, 0.25, (0.0, Y - 0.004, H_ - 0.2), atlas("notices"), t=0.003, mat=W.PRINT)
    plate(p, 0.26, 0.26, (-0.64, Y - 0.004, H_ - 0.2), atlas("roundel"), t=0.003, mat=W.PRINT)
    plate(p, 0.26, 0.26, (0.64, Y - 0.004, H_ - 0.2), atlas("roundel"), t=0.003, mat=W.PRINT)
    plate(p, 0.36, 0.48, (-0.5, Y - 0.002, 0.52), atlas("notice0"), t=0.001, mat=W.PRINT, rot=(0, 1.5, 0))
    n1 = plate(p, 0.36, 0.48, (-0.05, Y - 0.002, 0.5), atlas("notice1"), t=0.001, mat=W.PRINT, rot=(0, -1.0, 0))
    if worn:
        G.xform(n1.obj, rot=(0, 14, 0), pivot=(-0.2, Y, 0.74))
    plate(p, 0.27, 0.36, (0.38, Y - 0.002, 0.58), ws_atlas("sheet1"), t=0.001, rot=(0, 2.0, 0))
    plate(p, 0.15, 0.15, (0.64, Y - 0.002, 0.3), ws_atlas("note2"), t=0.001, rot=(0, -6.0, 0))
    plate(p, 0.15, 0.15, (0.3, Y - 0.002, 0.2), ws_atlas("note0"), t=0.001, rot=(0, 4.0, 0))
    # tin hood on two struts
    for sx in (-1, 1):
        bar(p, (sx * 0.75, 0.0, H_ + 0.25), (sx * 0.75, -0.24, H_ + 0.12), 0.03, 0.03, C.OLIVE)
    roof_sheet(p, -0.85, 0.85, -0.26, H_ + 0.1, 0.0, H_ + 0.28, C.ROOF_RUST if worn else C.ROOF, t=0.01)
    p.collider((0, -0.12, (H_ + 0.3) / 2), (W_ + 0.1, 0.24, H_ + 0.3))


# ================================================================================================
# registry
# ================================================================================================

BUILDERS = {
    "cordon_wall_panel": cordon_wall_panel,
    "cordon_wall_gate": cordon_wall_gate,
    "cordon_river_gate": cordon_river_gate,
    "cordon_river_abutment": cordon_river_abutment,
    "cordon_notice_board": cordon_notice_board,
}


def build(params: dict, outputs: list[str]) -> None:
    core.build_variants(params, outputs, BUILDERS[params.get("builder", params["prop"])])
