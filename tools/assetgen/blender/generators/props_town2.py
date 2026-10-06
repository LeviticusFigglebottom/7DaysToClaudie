"""Town props II - Pell's Crossing School, Pell Volunteer Fire Station, Tamsin Valley Savings & Loan.

School: 1960s combo student desk, steel teacher's desk, wall chalkboard with the Cordon evacuation tallies,
bank of four hallway lockers, gym bleachers, wall-mounted basketball hoop, wall bars, folded gym mats, a
stage lighting batten, a sectional cast-iron boiler, the library card catalog, the flagpole and a 1970s
school bus wreck.
Fire station: 1970s rural pumper wreck, wall hose rack, turnout-gear cubbies, the brass slide pole, drying
hoses in the hose tower, a roof siren, a wall extinguisher.
Bank: the vault-door surround (frame) plus the vault door leaves for the POI kit (models/kit/door_vault*),
teller counter with its brass-and-glass cage, safe-deposit wall, queue stanchions, money bags.

Built on the interior-props framework (lib/props_int_core.py: Prop, variants clean / worn / destroyed,
wear / AO vertex colours, collision boxes). The vehicles use it too (boxy bodies, prism panels with wheel
arches) with the shared exterior vehicle materials (car_rust, chrome_pitted, tyre_rubber, window_grime...).
Graphics come from textures/gen/town2.py: town2_print (ATLAS below mirrors PRINT_RECTS), town2_chalkboard
(top half clean, bottom half smeared), town2_deposit_boxes (DEP_* below mirrors its layout).
No readable text anywhere.

params: prop (id), seed, variants, mount, budget, plus per-prop knobs (see blender_catalogs/props_town2.py).
"""
from __future__ import annotations

import math

import bmesh
from mathutils import Matrix, Vector

from lib import common, export, materials
from lib import props_int_core as core
from lib import props_int_furn as F
from lib import props_int_mesh as G
from lib import props_ext_kit as K
from lib import props_ext_parts as EP
from lib.props_int_core import M, Prop


class C:
    """Material ids: town2_* from game/data/materials/props_town2.json, the rest from other families."""
    PRINT = "town2_print"
    CHALK = "town2_chalkboard"
    DEPOSIT = "town2_deposit_boxes"
    VAULT = "town2_vault_steel"
    BUS_YELLOW = "town2_bus_yellow"
    ENGINE_RED = "town2_engine_red"
    LOCKER = "town2_locker_blue"
    MAT_BLUE = "town2_mat_blue"
    HOSE = "town2_hose_canvas"
    LAGGING = "town2_lagging"
    TURNOUT = "town2_turnout"
    REFLECT = "town2_reflective"
    RIM_ORANGE = "town2_rim_orange"
    BUS_VINYL = "town2_bus_vinyl"
    TANKER = "town2_tanker_grey"
    BOILER = "town2_boiler_iron"
    # shared
    OAK = "civic_oak"
    OAK_DARK = "civic_oak_dark"
    MAHOGANY = "civic_mahogany"
    MARBLE = "civic_marble"
    BRASS = "civic_brass"
    FELT_RED = "civic_felt_red"
    GALV = "metal_galvanized"
    ALU = "road_alu"
    CONCRETE = "road_concrete"
    CHROME = "chrome_pitted"
    TYRE = "tyre_rubber"
    WINDOW = "window_grime"
    UNDER = "underbody"
    RUST = "car_rust"
    BURNT = "car_burnt"
    LENS_C = "lens_clear"
    LENS_R = "lens_red"
    LENS_A = "lens_amber"
    PL_BLACK = "plastic_black"
    PAINT_RED = "paint_red"
    PAINT_BLACK = "paint_black"
    PAINT_GREY = "paint_grey"
    CAR_WHITE = "car_paint_white"
    CANVAS = "canvas_khaki"
    RUBBER = "rubber_black"
    ROPE = "road_rope"
    YELLOW_PL = "plastic_yellow"


# Blender-only preview colours for dev_preview renders (Godot swaps in the real materials).
materials.PREVIEW_COLORS.update({
    C.BUS_YELLOW: (0.55, 0.35, 0.04), C.ENGINE_RED: (0.35, 0.04, 0.03), C.LOCKER: (0.12, 0.2, 0.3),
    C.MAT_BLUE: (0.05, 0.12, 0.35), C.HOSE: (0.55, 0.5, 0.4), C.LAGGING: (0.6, 0.58, 0.52),
    C.TURNOUT: (0.4, 0.33, 0.2), C.REFLECT: (0.6, 0.65, 0.4), C.RIM_ORANGE: (0.6, 0.18, 0.04),
    C.BUS_VINYL: (0.15, 0.2, 0.1), C.TANKER: (0.3, 0.33, 0.3), C.BOILER: (0.12, 0.1, 0.09),
    C.VAULT: (0.55, 0.55, 0.55), C.CHALK: (0.1, 0.16, 0.12), C.DEPOSIT: (0.5, 0.38, 0.15), C.PRINT: (0.5, 0.5, 0.5),
})

# town2_print atlas rects (x0, y0, x1, y1) in pixels of the 1024 px texture - mirror of
# textures/gen/town2.py PRINT_RECTS.
ATLAS: dict[str, tuple[int, int, int, int]] = {
    "gauge": (0, 0, 128, 128),
    "gauge_red": (128, 0, 256, 128),
    "gauge_black": (0, 128, 128, 256),
    "clock": (128, 128, 256, 256),
    "dial": (256, 0, 512, 256),
    "timelock": (512, 0, 1024, 256),
    "backboard": (0, 256, 512, 560),
    "flag": (512, 256, 1024, 544),
    "stop": (0, 576, 256, 832),
    "card_label": (256, 576, 384, 640),
    "cash_top": (384, 576, 640, 704),
    "cash_side": (384, 704, 640, 768),
    "pump_plate": (640, 576, 1024, 832),
    "felt": (256, 640, 384, 704),
}

# Safe-deposit wall layout - mirror of textures/gen/town2.py DEP_*.
DEP_COLS = 8
DEP_ROWS = [0.12] * 7 + [0.18] * 4 + [0.24]
DEP_FACE = 1.8


def atlas(name: str, inset: float = 1.0) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = ATLAS[name]
    return core._px_rect(x0 + inset, y0 + inset, x1 - inset, y1 - inset)


def dep_cells() -> list[tuple[float, float, float, float]]:
    """Door rects (x0, z0, x1, z1) on the 1.8 m face (origin bottom-left), row-major from the top."""
    out = []
    z = DEP_FACE
    cw = DEP_FACE / DEP_COLS
    for rh in DEP_ROWS:
        for c in range(DEP_COLS):
            out.append((c * cw, z - rh, (c + 1) * cw, z))
        z -= rh
    return out


# ------------------------------------------------------------------------------------------------
# shared helpers
# ------------------------------------------------------------------------------------------------


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
    """Round printed face (gauge / dial): a short cylinder whose caps show uvrect (planar)."""
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
    obj = G.box(p._name("bar"), (w, d, v.length), (0, 0, 0), kw.pop("bevel", 0.004))
    q = Vector((0, 0, 1)).rotation_difference(v.normalized())
    obj.data.transform(Matrix.Translation((a + b) * 0.5) @ q.to_matrix().to_4x4())
    obj.data.update()
    kw.setdefault("grain", "Z")
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


def rivets(p: Prop, pts, r: float, mat: str, axis: str = "-Y", h: float = 0.006, segs: int = 6) -> None:
    for c in pts:
        p.lathe([(r, 0.0), (r * 0.8, h * 0.6), (0.0, h)], c, mat, segs=segs, axis=axis, cap_bottom=False, wear=1.5)


def arch_panel(p: Prop, x0: float, t: float, y0: float, y1: float, z0: float, z1: float, arches, axle_z: float,
               mat: str, n: int = 9, **kw) -> core.Part:
    """Vertical side panel in the YZ plane (x from x0 to x0 + t), bottom edge z0 with semicircular wheel
    arches [(y_centre, radius), ...] around axle height axle_z."""
    pts = [(y0, z0)]
    for yc, R in sorted(arches):
        dz = z0 - axle_z
        if abs(dz) >= R:
            continue
        a_s = math.asin(dz / R)
        for i in range(n + 1):
            a = (math.pi - a_s) + ((a_s) - (math.pi - a_s)) * i / n
            pts.append((yc + R * math.cos(a), axle_z + R * math.sin(a)))
    pts += [(y1, z0), (y1, z1), (y0, z1)]
    kw.setdefault("grain", "Y")
    return p.prism(pts, t, mat, plane="YZ", offset=x0, **kw)


def wheel(p: Prop, x: float, y: float, r_out: float, r_rim: float, width: float, *, burnt: bool, flat: float = 0.35,
          rim_mat: str = C.PAINT_BLACK, segs: int = 14, hub: bool = True, outward: float | None = None) -> list:
    """Truck wheel spinning about X at (x, y): flat tyre settled on the floor (or a bare rim when burnt).
    The rim face points to `outward` (sign of x by default)."""
    side = outward if outward is not None else (1.0 if x >= 0 else -1.0)
    w = width / 2
    out = []
    axle_z = r_rim + 0.01 if burnt else r_out - r_out * flat * 0.35
    if not burnt:
        prof = [(r_rim, -w * 0.85), (r_out * 0.94, -w), (r_out, -w * 0.55), (r_out, w * 0.55), (r_out * 0.94, w),
                (r_rim, w * 0.85)]
        t = p.lathe(prof, (x, y, axle_z), C.TYRE, segs=segs, axis="X", cap_bottom=False, cap_top=False, tags=("tyre",))
        EP.flatten_tyre(t.obj, axle_z, r_out, amount=flat, bulge=0.025 * r_out / 0.4)
        out.append(t)
    rp = [(r_rim * 1.02, -w * 0.85), (r_rim, w * 0.7), (r_rim * 0.7, w * 0.62), (r_rim * 0.3, w * 0.8), (0.0, w * 0.8)]
    out.append(p.lathe(rp, (x, y, axle_z), C.RUST if burnt else rim_mat, segs=segs, axis="X" if side > 0 else "-X",
                       cap_bottom=False, cap_top=False, tags=("rim",)))
    if hub:
        out.append(p.lathe([(r_rim * 0.22, 0.0), (r_rim * 0.18, 0.06), (0.0, 0.07)], (x + side * w * 0.8, y, axle_z),
                           C.RUST if burnt else C.CHROME, segs=6, axis="X" if side > 0 else "-X", cap_bottom=False))
    return out


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


def cloth_sheet(p: Prop, w: float, h: float, nx: int, ny: int, fn, mat: str, rect=None, keep=None, t: float = 0.003,
                key: str = "cloth") -> core.Part:
    """Two-sided cloth sheet in the XZ plane (x 0..w, z 0..h, hung from x = 0) displaced by fn(u, v) ->
    (dx, dy, dz) in metres; keep(u, v) -> False drops a cell (tears). UVs map rect (front, mirrored back)."""
    rect = rect or (0.0, 0.0, 1.0, 1.0)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    grid = {}
    for side in (0, 1):
        for j in range(ny + 1):
            for i in range(nx + 1):
                u, v = i / nx, j / ny
                dx, dy, dz = fn(u, v)
                grid[(side, i, j)] = bm.verts.new((u * w + dx, dy + (t if side else 0.0), v * h + dz))
    for side in (0, 1):
        for j in range(ny):
            for i in range(nx):
                if keep is not None and not keep((i + 0.5) / nx, (j + 0.5) / ny):
                    continue
                vs = [grid[(side, i, j)], grid[(side, i + 1, j)], grid[(side, i + 1, j + 1)], grid[(side, i, j + 1)]]
                f = bm.faces.new(vs if side == 0 else list(reversed(vs)))
                for lp in f.loops:
                    co = lp.vert.co
                    uu = min(1.0, max(0.0, (co.x) / w))
                    vv = min(1.0, max(0.0, (co.z) / h))
                    lp[uvl].uv = (rect[0] + uu * (rect[2] - rect[0]), rect[1] + vv * (rect[3] - rect[1]))
    obj = G._obj(p._name(key), bm)
    return p.add(obj, mat, uv="keep", wear=0.4, edge_deg=60.0)


# ================================================================================================
# School
# ================================================================================================


def school_desk(p: Prop) -> None:
    """1960s combo student desk (0.62 x 0.76 x 1.05): chrome tube sled frame, woodgrain laminate top over a
    wire book basket, moulded plywood seat and back joined to the desk by one arm (left). Facing -Y (the
    sitter faces the top). Worn: a book in the basket, scratched. Destroyed: knocked onto its side, the
    seat back snapped off beside it."""
    ch = M.CHROME
    top_z = 0.72
    p.box((0.6, 0.45, 0.022), (0, -0.27, top_z - 0.011), M.LAM_WOOD, bevel=0.005, grain="X", tags=("top",))
    p.box((0.58, 0.43, 0.012), (0, -0.27, top_z - 0.028), M.PL_BROWN, bevel=0.002, tags=("top",))
    # wire book basket under the top
    bz0, bz1, by0, by1 = 0.56, 0.675, -0.47, -0.09
    for i in range(9):
        x = -0.24 + 0.06 * i
        p.tube([(x, by0, bz0 + 0.04), (x, by0 + 0.02, bz0), (x, by1, bz0)], 0.0035, ch, segs=4, cap=False)
    for x in (-0.26, 0.26):
        p.tube([(x, by0, bz1), (x, by0, bz0), (x, by1, bz0), (x, by1, bz1)], 0.0045, ch, segs=4, cap=False)
    p.tube([(-0.26, by0, bz0 + 0.06), (0.26, by0, bz0 + 0.06)], 0.004, ch, segs=4)
    p.tube([(-0.26, by0, bz0), (0.26, by0, bz0)], 0.004, ch, segs=4)
    for sx in (-1, 1):
        x = sx * 0.26
        p.tube([(x, -0.52, 0.05), (x, -0.5, 0.012), (x, 0.47, 0.012), (x, 0.5, 0.05)], 0.011, ch, segs=6, fillet_r=0.03)
        p.tube([(x, -0.36, 0.012), (x, -0.33, top_z - 0.034)], 0.012, ch, segs=6, cap=False)
        p.tube([(x, -0.47, top_z - 0.04), (x, -0.08, top_z - 0.04)], 0.009, ch, segs=6)
        p.tube([(x, 0.15, 0.012), (x, 0.19, 0.415)], 0.011, ch, segs=6, cap=False)
        p.tube([(x * 0.98, 0.07, 0.418), (x * 0.98, 0.44, 0.418)], 0.009, ch, segs=6)
        p.tube([(x * 0.95, 0.44, 0.012), (x * 0.95, 0.43, 0.42), (x * 0.95, 0.465, 0.75)], 0.011, ch, segs=6, fillet_r=0.08, cap=False)
        p.cyl(0.014, 0.012, (x, -0.43, 0.006), M.RUBBER, segs=6)
        p.cyl(0.014, 0.012, (x, 0.42, 0.006), M.RUBBER, segs=6)
    p.tube([(-0.29, -0.12, top_z - 0.04), (-0.29, 0.0, 0.6), (-0.27, 0.09, 0.42)], 0.012, ch, segs=6, fillet_r=0.08)
    p.tube([(-0.26, 0.19, 0.3), (0.26, 0.19, 0.3)], 0.009, ch, segs=6)
    seat = p.rbox((0.4, 0.37, 0.018), (0, 0.25, 0.436), M.OAK, radius=0.008, inner=(3, 3, 1), bulge=(0, 0, -0.006), edge_deg=30,
                  grain="X")
    back = p.rbox((0.4, 0.02, 0.17), (0, 0.475, 0.66), M.OAK, radius=0.008, inner=(3, 1, 2), bulge=(0, 0.01, 0), edge_deg=30,
                  grain="X")
    G.xform(back.obj, rot=(-9, 0, 0), pivot=(0, 0.47, 0.58))
    del seat
    if p.worn and not p.destroyed:
        F.book(p, (0.03, 0.2, 0.26), (0.0, -0.3, bz0 + 0.015), 7, rot=(0, 90, 8))
        F.book(p, (0.02, 0.17, 0.23), (0.05, -0.22, bz0 + 0.04), 11, rot=(0, 90, -5))
    if p.destroyed:
        p.remove([back])
        whole = list(p.parts)
        p.lay_on_floor(whole, rot=(0, 88, 0), at=(0.05, 0.0), yaw=8)
        bk = p.rbox((0.4, 0.02, 0.17), (0, 0, 0), M.OAK, radius=0.008, inner=(3, 1, 2), bulge=(0, 0.01, 0), edge_deg=30, grain="X")
        p.lay_on_floor([bk], rot=(-90, 0, 0), at=(-0.45, 0.35), yaw=30)
        p.collider((0, 0, 0.3), (0.8, 1.05, 0.6))
    else:
        p.collider((0, -0.01, 0.38), (0.62, 1.04, 0.76))


def school_teacher_desk(p: Prop) -> None:
    """Steel 'tanker' teacher's desk (1.5 x 0.76 x 0.75): grey-green pressed steel with a woodgrain lino top,
    two pedestals (two drawers left, three right), a pencil drawer and a modesty panel. Drawers face -Y.
    Worn: a drawer pulled out, a stack of graded papers and a mug. Destroyed: drawers ripped out and
    dumped, papers everywhere, the top skewed."""
    W, D, H = 1.5, 0.75, 0.76
    st = C.TANKER
    yf = -D / 2
    p.box((W, D, 0.028), (0, 0, H - 0.014), M.LAM_WOOD, bevel=0.004, grain="X")
    p.box((W + 0.006, D + 0.006, 0.012), (0, 0, H - 0.034), M.CHROME, bevel=0.003)
    for x0, x1 in ((-0.73, -0.33), (0.33, 0.73)):
        cx = (x0 + x1) / 2
        for xs in (x0 + 0.01, x1 - 0.01):
            p.box((0.02, D - 0.02, H - 0.08), (xs, 0.0, (H - 0.04) / 2 + 0.03), st, bevel=0.004, grain="Z")
        p.box((x1 - x0, D - 0.06, 0.02), (cx, 0.01, 0.07), st, bevel=0.002)
        p.box((x1 - x0 - 0.02, 0.02, 0.06), (cx, yf + 0.05, 0.03), C.PL_BLACK, bevel=0.002)
        p.box((x1 - x0, 0.015, H - 0.08), (cx, D / 2 - 0.02, (H - 0.04) / 2 + 0.03), st, bevel=0.002)
    p.box((0.64, 0.015, 0.46), (0, D / 2 - 0.04, H - 0.26), st, bevel=0.003)
    drawers = {}
    spec = [("l0", -0.72, -0.34, 0.47, 0.69), ("l1", -0.72, -0.34, 0.07, 0.46),
            ("r0", 0.34, 0.72, 0.53, 0.69), ("r1", 0.34, 0.72, 0.33, 0.52), ("r2", 0.34, 0.72, 0.07, 0.32),
            ("c", -0.31, 0.31, 0.64, 0.7)]
    pulls = {"c": 0.0}
    if p.worn and not p.destroyed:
        pulls["r1"] = 0.22
    for k, x0, x1, z0, z1 in spec:
        pull = pulls.get(k, 0.0)
        drawers[k] = F.drawer(p, x0 + 0.004, z0, x1 - 0.004, z1, yf - 0.02, 0.6, st, t=0.02, style="slab", handle="bar",
                              handle_mat=M.CHROME, pull=pull, key=k)
    if p.worn and not p.destroyed:
        stack = p.box((0.22, 0.28, 0.035), (-0.35, 0.05, H + 0.0175), M.PAPER, bevel=0.003, uv="planar", uv_axis="Z",
                      rect=core.note_rect(1))
        G.xform(stack.obj, rot=(0, 0, 8), pivot=(-0.35, 0.05, H))
        p.lathe([(0.0, 0.0), (0.04, 0.0), (0.042, 0.095), (0.038, 0.095), (0.036, 0.006), (0.0, 0.006)], (0.45, 0.12, H), M.CERAMIC,
                segs=12, cap_top=False)
        p.tube([(0.488, 0.12, H + 0.075), (0.515, 0.12, H + 0.065), (0.515, 0.12, H + 0.03), (0.488, 0.12, H + 0.022)], 0.006,
               M.CERAMIC, segs=5, fillet_r=0.01)
        scatter_papers(p, (0.1, -0.05), 2, 0.12, "top", z=H)
    if p.destroyed:
        r = p.vrng("dump")
        for i, k in enumerate(("r0", "l0", "c")):
            grp = drawers[k]
            tray = p.hollow((0.36 if k != "c" else 0.58, 0.55, 0.12 if k != "c" else 0.05), (0, 0, 0), M.PARTICLE, wall=0.012,
                            open_face="+Z", bevel=0.0)
            tray.obj.data.transform(Matrix.Translation((0, 0.3, 0)))
            grp = grp + [tray]
            lo, hi = p.bounds(grp)
            c = (lo + hi) * 0.5
            p.move(grp, (-c.x, -c.y, -c.z))
            p.lay_on_floor(grp, rot=(r.uniform(-20, 20) + (90 if i == 1 else 0), 0, 0),
                           at=(-0.5 + i * 0.55 + r.uniform(-0.1, 0.1), -0.75 - r.uniform(0, 0.3)), yaw=r.uniform(-50, 50))
        scatter_papers(p, (0.0, -0.8), 9, 0.5, "floor")
        p.collider((0, -0.25, 0.38), (1.6, 1.25, 0.76))
    else:
        p.collider((0, 0, H / 2), (W, D, H))


def school_chalkboard(p: Prop) -> None:
    """Wall chalkboard (origin on the wall plane, bottom centre; hang ~0.75 m up): 3.6 x 1.25 slate in an oak
    frame with a chalk tray, chalk and a felt eraser. The board holds the Cordon evacuation roll-call:
    tallies per bus, the bus crossed out, a route map (town2_chalkboard top half). Worn: wiped and smeared,
    scrawled over (bottom half)."""
    W, H = 3.6, 1.25
    bd = 0.022
    plate(p, 3.46, 1.09, (0, -0.016, 0.645), (0.0, 0.5, 1.0, 1.0) if not p.worn else (0.0, 0.0, 1.0, 0.5), t=0.012,
          mat=C.CHALK, wear=0.1)
    p.box((W, 0.012, H), (0, -0.006, H / 2), M.PARTICLE, bevel=0.0, wear=0.2)
    p.box((W, 0.038, 0.06), (0, -0.019, H - 0.03), C.OAK, bevel=0.005, grain="X")
    for sx in (-1, 1):
        p.box((0.07, 0.038, H), (sx * (W / 2 - 0.035), -0.019, H / 2), C.OAK, bevel=0.005, grain="Z")
    p.box((W - 0.14, 0.038, 0.1), (0, -0.019, 0.05), C.OAK, bevel=0.005, grain="X")
    # chalk tray
    p.box((W - 0.1, 0.06, 0.014), (0, -bd - 0.03 - 0.016, 0.083), C.OAK, bevel=0.003, grain="X")
    p.box((W - 0.1, 0.01, 0.028), (0, -bd - 0.078, 0.09), C.OAK, bevel=0.003, grain="X")
    for x in (-1.4, 0.0, 1.4):
        p.box((0.03, 0.06, 0.04), (x, -bd - 0.04, 0.06), C.OAK_DARK, bevel=0.003)
    r = p.vrng("chalk")
    n = 2 if p.worn else 4
    for i in range(n):
        x = r.uniform(-1.4, 1.4)
        ln = r.uniform(0.03, 0.08)
        c = p.cyl(0.0055, ln, (x, -bd - 0.05, 0.096), M.PL_WHITE, axis="X", segs=6)
        G.xform(c.obj, rot=(0, 0, r.uniform(-30, 30)), pivot=(x, -bd - 0.05, 0.096))
    ex = 0.9 if not p.worn else -1.2
    p.box((0.13, 0.05, 0.022), (ex, -bd - 0.045, 0.1 + 0.011 + 0.008), C.OAK_DARK, bevel=0.004, grain="X")
    p.box((0.13, 0.05, 0.008), (ex, -bd - 0.045, 0.094), C.PRINT, bevel=0.002, uv="planar", uv_axis="Z", rect=atlas("felt"))
    if p.worn:
        p.box((0.16, 0.002, 0.11), (1.55, -0.03, 0.95), M.PAPER, bevel=0.0, uv="planar", uv_axis="Y", rect=core.note_rect(2))
        p.box((0.03, 0.003, 0.02), (1.55, -0.032, 1.0), M.PL_WHITE, bevel=0.0)
    p.collider((0, -0.04, H / 2), (W, 0.08, H))


def school_locker_bank(p: Prop) -> None:
    """Bank of four tall hallway lockers (1.25 x 1.85 x 0.45): painted steel cases on a black kick base,
    louvred doors with lift handles, padlock hasps (two padlocked), blank number plates. Worn: one door
    forced and hanging open (hat shelf, a jacket, books inside), dents. Destroyed: two doors torn off, one
    on the floor, contents spilled."""
    n, w, D = 4, 0.305, 0.45
    W = n * w
    z0, z1 = 0.1, 1.85
    p.box((W, D - 0.06, z0), (0, 0.03, z0 / 2), C.PL_BLACK, bevel=0.003)
    p.box((W + 0.01, D + 0.01, 0.02), (0, 0, z1 + 0.01), C.LOCKER, bevel=0.004)
    r = p.vrng("doors")
    open_k = {1} if p.worn else set()
    gone = {}
    if p.destroyed:
        open_k = {1}
        gone = {2: "floor", 3: "hang"}
    for k in range(n):
        cx = -W / 2 + w * (k + 0.5)
        p.hollow((w - 0.004, D, z1 - z0), (cx, 0, (z0 + z1) / 2), C.LOCKER, wall=0.01, open_face="-Y", bevel=0.002)
        if k in open_k or k in gone:
            p.box((w - 0.03, D - 0.04, 0.012), (cx, 0.01, 1.55), C.LOCKER, bevel=0.002)
            p.tube([(cx, D / 2 - 0.02, 1.5), (cx, D / 2 - 0.07, 1.48), (cx, D / 2 - 0.08, 1.52)], 0.004, M.CHROME, segs=4)
            if k == 1:
                p.rbox((0.24, 0.12, 0.6), (cx, 0.1, 1.15), C.CANVAS, radius=0.04, inner=(2, 1, 3), wrinkle=0.012, seed=p.seed + 3,
                       taper_top=0.35)
                F.book(p, (0.03, 0.18, 0.24), (cx - 0.05, 0.05, z0 + 0.13), 3, rot=(0, 0, 90))
                F.book(p, (0.025, 0.17, 0.22), (cx + 0.04, 0.03, z0 + 0.12), 19, rot=(0, -12, 90))
        door = [p.box((w - 0.012, 0.018, z1 - z0 - 0.02), (cx, -D / 2 - 0.009, (z0 + z1) / 2), C.LOCKER, bevel=0.003, grain="Z",
                      tags=("door",))]
        for vz in (z1 - 0.2, z0 + 0.12):
            for i in range(4):
                door.append(p.box((w * 0.55, 0.006, 0.01), (cx, -D / 2 - 0.019, vz + i * 0.024), C.LOCKER, bevel=0.0))
        hx = cx + w / 2 - 0.05
        door.append(p.box((0.035, 0.022, 0.13), (hx, -D / 2 - 0.02, 1.02), M.CHROME, bevel=0.004))
        door.append(p.box((0.012, 0.012, 0.05), (hx, -D / 2 - 0.035, 1.12), M.CHROME, bevel=0.002))
        door.append(p.box((0.08, 0.002, 0.03), (cx - 0.02, -D / 2 - 0.019, z1 - 0.07), C.ALU, bevel=0.0))
        if (k in (0, 3)) and k not in open_k and k not in gone:
            door.append(p.box((0.04, 0.02, 0.045), (hx, -D / 2 - 0.05, 1.06), C.BRASS, bevel=0.005))
            door.append(p.tube([(hx - 0.012, -D / 2 - 0.05, 1.08), (hx - 0.012, -D / 2 - 0.05, 1.11), (hx + 0.012, -D / 2 - 0.05, 1.11),
                                (hx + 0.012, -D / 2 - 0.05, 1.08)], 0.004, M.CHROME, segs=4, fillet_r=0.01))
        for hz in (z0 + 0.2, (z0 + z1) / 2, z1 - 0.2):
            p.cyl(0.007, 0.06, (cx - w / 2 + 0.008, -D / 2 - 0.012, hz), M.CHROME, segs=5)
        hinge = (cx - w / 2 + 0.006, -D / 2 - 0.018)
        if k in open_k:
            F.swing(p, door, hinge[0], hinge[1], -r.uniform(95, 115))
            if p.destroyed:
                p.rotate(door, rot=(0, 4, 0), pivot=(hinge[0], hinge[1], z1))
        elif gone.get(k) == "floor":
            lo, hi = p.bounds(door)
            c = (lo + hi) * 0.5
            p.move(door, (-c.x, -c.y, -c.z))
            p.lay_on_floor(door, rot=(-90, 0, 0), at=(0.25, -0.75), yaw=r.uniform(60, 80))
        elif gone.get(k) == "hang":
            F.hang(p, door, hinge[0], hinge[1], z1 - 0.2, 60.0, 25.0)
    if p.destroyed:
        scatter_papers(p, (-0.2, -0.6), 5, 0.3, "spill")
        F.book(p, (0.03, 0.2, 0.26), (-0.4, -0.55, 0.015), 5, rot=(0, 90, 30))
        p.collider((0, -0.2, 0.93), (1.3, 0.9, 1.86))
    else:
        p.collider((0, 0, 0.93), (W, D, 1.86))


def _tier(k: int) -> tuple[float, float, float]:
    """Bleacher tier k: (y0 of the tier, seat top z, foot board top z)."""
    return -1.2 + 0.6 * k, 0.45 + 0.4 * k, 0.4 * k


def school_bleachers(p: Prop) -> None:
    """Gym bleachers (4.0 x 1.7 x 2.4): four tiers of varnished fir seat and foot boards on a grey steel
    frame of posts, bearers and diagonal braces. Seat k is 0.45 + 0.4 k m up. Worn: a seat board split and
    sagging, a foot board missing."""
    L = 4.0
    frame = C.PAINT_GREY
    broken = p.worn
    for k in range(4):
        y0, zs, zf = _tier(k)
        for i in range(2):
            y = y0 + 0.36 + i * 0.13
            if broken and k == 2 and i == 0:
                for sx in (-1, 1):
                    b = p.box((1.25, 0.12, 0.04), (sx * 1.35, y, zs - 0.02), C.OAK, bevel=0.004, grain="X")
                    G.xform(b.obj, rot=(0, -sx * 7, 0), pivot=(sx * 2.0, y, zs))
                    del b
                p.box((1.5, 0.12, 0.04), (0, y, zs - 0.02), C.OAK, bevel=0.004, grain="X")
                continue
            p.box((L, 0.12, 0.04), (0, y, zs - 0.02), C.OAK, bevel=0.004, grain="X")
        if k > 0:
            for i in range(2):
                if broken and k == 1 and i == 1:
                    continue
                p.box((L, 0.13, 0.035), (0, y0 + 0.08 + i * 0.14, zf - 0.0175), C.OAK, bevel=0.004, grain="X")
    if broken:
        pl = p.box((1.9, 0.13, 0.035), (0, 0, 0), C.OAK, bevel=0.004, grain="X")
        p.lay_on_floor([pl], rot=(0, 0, 0), at=(0.6, -1.45), yaw=12)
    for x in (-1.85, -0.62, 0.62, 1.85):
        for k in range(4):
            y0, zs, zf = _tier(k)
            bar(p, (x, y0 + 0.3, zs - 0.06), (x, y0 + 0.6, zs - 0.06), 0.05, 0.04, frame, grain="Y", bevel=0.003)
            bar(p, (x, y0 + 0.57, 0.0), (x, y0 + 0.57, zs - 0.04), 0.05, 0.05, frame, bevel=0.003)
            bar(p, (x, y0 + 0.33, zs - 0.08), (x, y0 + 0.33, zf), 0.04, 0.04, frame, bevel=0.003)
            if k > 0:
                bar(p, (x, y0, zf - 0.055), (x, y0 + 0.33, zf - 0.055), 0.05, 0.04, frame, grain="Y", bevel=0.003)
        bar(p, (x, -0.88, 0.02), (x, 1.15, 1.55), 0.04, 0.04, frame, bevel=0.003)
        bar(p, (x, -0.88, 0.02), (x, 1.17, 0.02), 0.06, 0.04, frame, grain="Y", bevel=0.003)
    for z in (0.35, 1.0):
        bar(p, (-1.9, 1.17, z), (1.9, 1.17, z), 0.04, 0.04, frame, grain="X", bevel=0.003)
    # centre the footprint on the origin (front plank edge y = -0.9, back posts y = 1.2)
    p.move(list(p.parts), (0, -0.15, 0))
    for k in range(4):
        y0, zs, zf = _tier(k)
        y0 = max(y0, -0.9)
        p.collider((0, (y0 + 1.2) / 2 - 0.15, zs / 2), (L, 1.2 - y0, zs))


def _net(p: Prop, c, z: float, keep_fn) -> None:
    n = 12
    pts = {}
    for i in range(n):
        a0 = 2 * math.pi * i / n
        a1 = a0 + math.pi / n
        pts[("t", i)] = (c[0] + math.cos(a0) * 0.222, c[1] + math.sin(a0) * 0.222, z - 0.005)
        pts[("m", i)] = (c[0] + math.cos(a1) * 0.18, c[1] + math.sin(a1) * 0.18, z - 0.19)
        pts[("b", i)] = (c[0] + math.cos(a0) * 0.15, c[1] + math.sin(a0) * 0.15, z - 0.37)
    segs = []
    for i in range(n):
        j = (i + 1) % n
        segs += [(("t", i), ("m", i)), (("t", j), ("m", i)), (("m", i), ("b", i)), (("m", i), ("b", j))]
    for a, b in segs:
        idx = a[1]
        st = keep_fn(idx, a[0])
        if st == "gone":
            continue
        pa, pb = Vector(pts[a]), Vector(pts[b])
        if st == "dangle":
            pb = pa + Vector((0.0, 0.0, -(pb - pa).length))
        p.tube([pa, (pa + pb) * 0.5 + Vector((0, 0, -0.01)), pb], 0.004, M.LINEN, segs=3, cap=False, wear=0.4)


def school_basketball_hoop(p: Prop) -> None:
    """Wall-mounted basketball goal (origin on the wall plane at the bottom of the bracket; hang the origin
    2.4 m up so the rim sits at 3.05 m): grey steel truss bracket, 1.8 x 1.05 painted backboard (no text),
    orange rim 0.93 m out from the wall with its mount, a torn cotton net. Worn: the net mostly gone, a
    strand dangling, the board chipped."""
    st = C.PAINT_GREY
    by = -0.52
    for sx in (-1, 1):
        x = sx * 0.35
        p.box((0.06, 0.05, 1.5), (x, -0.025, 0.75), st, bevel=0.004, grain="Z")
        p.box((0.16, 0.008, 0.2), (x, -0.004, 0.1), st, bevel=0.002)
        p.box((0.16, 0.008, 0.2), (x, -0.004, 1.38), st, bevel=0.002)
        for z in (0.05, 1.42):
            bar(p, (x, -0.05, z), (x, by, z), 0.05, 0.05, st, grain="Y", bevel=0.003)
        bar(p, (x, -0.05, 0.08), (x, by + 0.02, 1.4), 0.04, 0.04, st, bevel=0.003)
        bar(p, (x, by, 0.05), (x, by, 1.45), 0.05, 0.04, st, bevel=0.003)
    bar(p, (-0.35, by, 0.5), (0.35, by, 0.5), 0.04, 0.04, st, grain="X", bevel=0.003)
    bar(p, (-0.35, by, 1.3), (0.35, by, 1.3), 0.04, 0.04, st, grain="X", bevel=0.003)
    bb = 0.5
    board_y = by - 0.035
    plate(p, 1.8, 1.05, (0, board_y, bb + 0.525), atlas("backboard"), t=0.03, wear=0.6, bevel=0.004)
    p.box((1.8, 0.05, 0.05), (0, board_y - 0.005, bb - 0.01), C.PL_BLACK, bevel=0.012)
    rim_z = bb + 0.15
    front = board_y - 0.015
    rc = (0.0, front - 0.15 - 0.229)
    p.box((0.16, 0.012, 0.13), (0, front - 0.006, rim_z - 0.04), C.RIM_ORANGE, bevel=0.002)
    p.box((0.1, 0.17, 0.008), (0, front - 0.085, rim_z - 0.01), C.RIM_ORANGE, bevel=0.002)
    for sx in (-1, 1):
        p.tube([(sx * 0.04, front - 0.01, rim_z - 0.1), (sx * 0.06, rc[1] + 0.18, rim_z - 0.008)], 0.006, C.RIM_ORANGE, segs=5)
    torus(p, 0.229, 0.0095, (rc[0], rc[1], rim_z), C.RIM_ORANGE, axis="Z", segs=24, rsegs=6)
    for i in range(12):
        a = 2 * math.pi * i / 12
        p.box((0.006, 0.006, 0.02), (rc[0] + math.cos(a) * 0.222, rc[1] + math.sin(a) * 0.222, rim_z - 0.012), C.RIM_ORANGE,
              bevel=0.0)
    r = p.vrng("net")
    lost = 0.85 if p.worn else 0.25

    def keep(i, level):
        a = (i / 12.0 + 0.3) % 1.0
        if p.worn and i in (2, 3) and level == "t":
            return "dangle"
        if a < lost * 0.5 and level != "t":
            return "gone" if r.random() < 0.85 else "dangle"
        if r.random() < lost * 0.25:
            return "gone"
        return "keep"

    _net(p, rc, rim_z, keep)
    p.collider((0, -0.6, 0.85), (1.8, 1.2, 1.7))


def school_wall_bars(p: Prop) -> None:
    """Gym wall bars / Swedish ladder (origin on the wall plane, bottom centre): 0.95 x 2.6, two oak uprights
    on steel wall brackets with 16 oval ash rungs. Worn: one rung snapped, its halves hanging in the
    sockets, varnish rubbed off where hands go."""
    for sx in (-1, 1):
        x = sx * 0.44
        p.box((0.07, 0.06, 2.6), (x, -0.13, 1.3), C.OAK, bevel=0.006, grain="Z")
        for z in (0.3, 1.3, 2.3):
            p.box((0.05, 0.1, 0.06), (x, -0.05, z), C.PAINT_GREY, bevel=0.004)
            p.box((0.09, 0.006, 0.12), (x, -0.003, z), C.PAINT_GREY, bevel=0.002)
    for k in range(16):
        z = 0.14 + 0.155 * k
        if p.worn and k == 5:
            for sx in (-1, 1):
                stub = p.cyl(0.019, 0.25, (sx * 0.28, -0.13, z), M.OAK, axis="X", segs=8)
                G.xform(stub.obj, scale=(1.0, 1.35, 1.0), pivot=(0, -0.13, z))
                G.xform(stub.obj, rot=(0, sx * 18, 0), pivot=(sx * 0.405, -0.13, z))
            continue
        rung = p.cyl(0.019, 0.82, (0, -0.13, z), M.OAK, axis="X", segs=8, wear=1.4)
        G.xform(rung.obj, scale=(1.0, 1.35, 1.0), pivot=(0, -0.13, z))
    p.collider((0, -0.08, 1.3), (0.97, 0.16, 2.6))


def school_gym_mats(p: Prop) -> None:
    """Stack of three folded blue vinyl gym mats (1.8 x 0.45 x 1.2): each mat three 0.6 m sections wide
    and folded into three panels, rounded fold edges alternating front and back, black webbing handles.
    Worn: the top mat's top panel flopped down over the front, scuffed."""
    for m in range(3):
        r = p.rng(f"mat{m}")
        ox, oy, yaw = r.uniform(-0.03, 0.03), r.uniform(-0.03, 0.03), r.uniform(-2.0, 2.0)
        grp = []
        for k in range(3):
            z = m * 0.15 + k * 0.05 + 0.025
            grp.append(p.rbox((1.8, 1.16, 0.046), (0, 0, z), C.MAT_BLUE, radius=0.018, inner=(3, 2, 1),
                              bulge=(0, 0, 0.004), tags=(f"m{m}", f"k{k}")))
            for s in (-0.3, 0.3):
                grp.append(p.box((0.012, 1.1, 0.004), (s, 0, z + 0.0245), C.PL_BLACK, bevel=0.0, wear=0.0, tags=(f"m{m}", f"k{k}")))
            if k < 2:
                fy = 0.58 if (k + m) % 2 == 0 else -0.58
                grp.append(p.cyl(0.024, 1.8, (0, fy, z + 0.025), C.MAT_BLUE, axis="X", segs=8))
        for sx in (-1, 1):
            grp.append(p.box((0.012, 0.3, 0.03), (sx * 0.906, 0, m * 0.15 + 0.075), C.PL_BLACK, bevel=0.003))
        p.rotate(grp, rot=(0, 0, yaw), pivot=(0, 0, 0))
        p.move(grp, (ox, oy, 0))
        if p.worn and m == 2:
            top = [q for q in grp if "k2" in q.tags]
            p.rotate(top, rot=(-158, 0, 0), pivot=(0, -0.6 + oy, 0.425))
    p.collider((0, 0, 0.225), (1.85, 1.25, 0.45))


def _fresnel(p: Prop, x: float, tilt: float, yaw: float, lamp: bool, lens: bool) -> list:
    out = []
    out.append(p.box((0.05, 0.07, 0.07), (x, 0.0, -0.035), C.PAINT_BLACK, bevel=0.006))
    out.append(p.cyl(0.006, 0.09, (x, -0.045, -0.02), M.CHROME, axis="Y", segs=6))
    out.append(p.cyl(0.012, 0.06, (x, 0.0, -0.1), C.PAINT_BLACK, segs=6))
    yoke = [p.tube([(x - 0.125, 0.0, -0.24), (x - 0.125, 0.0, -0.13), (x + 0.125, 0.0, -0.13), (x + 0.125, 0.0, -0.24)], 0.008,
                   C.PAINT_BLACK, segs=5, fillet_r=0.02)]
    head = []
    prof = [(0.0, -0.14), (0.05, -0.14), (0.085, -0.12), (0.1, -0.08), (0.1, 0.11), (0.108, 0.12), (0.108, 0.145), (0.092, 0.145)]
    head.append(p.lathe(prof, (0, 0, 0), C.PAINT_BLACK, segs=14, axis="-Y", cap_top=False))
    if lens:
        head.append(p.cyl(0.092, 0.012, (0, -0.135, 0), C.LENS_C, axis="Y", segs=14))
    head.append(p.box((0.21, 0.012, 0.21), (0, -0.152, 0), C.PAINT_BLACK, bevel=0.003))
    for i in range(4):
        head.append(p.box((0.012, 0.16, 0.012), (-0.045 + i * 0.03, 0.0, 0.103), C.PAINT_BLACK, bevel=0.002))
    for sx in (-1, 1):
        head.append(p.cyl(0.02, 0.025, (sx * 0.112, 0.0, 0.0), C.PAINT_BLACK, axis="X", segs=8))
    head.append(p.box((0.07, 0.03, 0.05), (0.0, 0.14, -0.04), C.PAINT_BLACK, bevel=0.004))
    if lamp:
        pass
    p.rotate(head, rot=(-tilt, 0, 0))
    p.move(head, (x, 0.0, -0.24))
    group = yoke + head
    p.rotate(group, rot=(0, 0, yaw), pivot=(x, 0, 0))
    cab = p.tube([(x, 0.13 * math.cos(math.radians(tilt)), -0.28), (x + 0.05, 0.1, -0.33), (x + 0.12, 0.02, -0.26), (x + 0.15, 0.0, -0.03)],
                 0.006, C.PL_BLACK, segs=4, fillet_r=0.05)
    return out + group + [cab]


def school_stage_lights(p: Prop) -> None:
    """Stage lighting batten (origin at the top centre of the pipe: hang it under the ceiling or a catwalk
    rail): a 2.4 m schedule-40 pipe with four black fresnel spotlights on C-clamps and yokes, aimed down
    at the stage, cables looped back to the pipe. Worn: one lantern gone (its clamp left), one knocked
    askew, a lens missing."""
    p.cyl(0.024, 2.4, (0, 0, -0.024), C.GALV, axis="X", segs=10)
    for sx in (-1, 1):
        p.cyl(0.026, 0.01, (sx * 1.2, 0, -0.024), C.PL_BLACK, axis="X", segs=10)
    xs = (-0.9, -0.3, 0.3, 0.9)
    for i, x in enumerate(xs):
        if p.worn and i == 1:
            p.box((0.05, 0.07, 0.07), (x, 0.0, -0.035), C.PAINT_BLACK, bevel=0.006)
            continue
        tilt = 48.0
        yaw = (-12, 6, -6, 12)[i]
        if p.worn and i == 3:
            tilt, yaw = 95.0, 40.0
        _fresnel(p, x, tilt, yaw, False, not (p.worn and i == 0))
    p.collider((0, -0.05, -0.22), (2.4, 0.4, 0.44))


def school_boiler(p: Prop) -> None:
    """Sectional cast-iron boiler (2.0 x 2.1 x 1.4): seven ribbed iron sections on a steel base, flue
    collector and smoke pipe, red oil burner on the front with its blower, cleanout doors, pressure and
    temperature gauges, a relief valve, the supply riser and return in lagged pipe, the grey expansion
    tank on its stand to the right. Rust everywhere. Worn: lagging fallen in tatters, the burner cover off
    on the floor."""
    iron = C.BOILER
    p.box((1.25, 1.25, 0.14), (-0.1, 0.0, 0.07), C.CONCRETE, bevel=0.01)
    p.box((1.15, 1.15, 0.08), (-0.1, 0.0, 0.18), M.CAST_IRON, bevel=0.006)
    for k in range(7):
        y = -0.48 + k * 0.16
        sec = p.rbox((1.05, 0.15, 1.25), (-0.1, y, 0.22 + 0.625), iron, radius=0.03, inner=(2, 1, 3), edge_deg=30)
        del sec
        for sx in (-1, 1):
            p.box((0.03, 0.12, 1.1), (-0.1 + sx * 0.535, y, 0.85), iron, bevel=0.008)
        p.cyl(0.04, 0.02, (-0.1 - 0.3, y + 0.08, 1.45), M.CAST_IRON, axis="Y", segs=8)
        p.cyl(0.04, 0.02, (-0.1 + 0.3, y + 0.08, 0.32), M.CAST_IRON, axis="Y", segs=8)
    p.box((1.1, 0.06, 1.28), (-0.1, -0.58, 0.85), iron, bevel=0.012)
    for x, z, w, h in ((-0.32, 1.25, 0.32, 0.24), (0.12, 1.25, 0.32, 0.24)):
        p.box((w, 0.035, h), (x, -0.625, z), M.CAST_IRON, bevel=0.008)
        p.box((0.05, 0.03, 0.025), (x + w / 2 - 0.04, -0.655, z), M.CAST_IRON, bevel=0.004)
    p.lathe([(0.02, 0.0), (0.02, 0.03), (0.0, 0.035)], (-0.1, -0.64, 0.95), M.BRASS, segs=8, axis="-Y")
    hood = p.prism([(-0.62, 0.0), (0.42, 0.0), (0.32, 0.22), (-0.52, 0.22)], 1.2, iron, plane="XZ", offset=-0.6)
    G.xform(hood.obj, loc=(0, 0, 1.47))
    p.cyl(0.16, 0.5, (-0.1, 0.25, 1.94), C.GALV, segs=14)
    p.tube([(-0.1, 0.25, 2.1), (-0.1, 0.4, 2.12), (-0.1, 0.72, 2.12)], 0.15, C.GALV, segs=14, fillet_r=0.18, cap=True)
    burner = []
    if not p.worn:
        burner.append(p.rbox((0.34, 0.3, 0.3), (-0.1, -0.78, 0.55), C.PAINT_RED, radius=0.04, inner=(2, 2, 2)))
    burner.append(p.cyl(0.11, 0.24, (-0.1 + 0.26, -0.78, 0.6), C.PAINT_RED, axis="X", segs=12))
    burner.append(p.cyl(0.07, 0.2, (-0.1, -0.68, 0.55), M.CAST_IRON, axis="Y", segs=10))
    burner.append(p.box((0.12, 0.08, 0.14), (-0.33, -0.78, 0.5), C.PL_BLACK, bevel=0.01))
    burner.append(p.tube([(-0.33, -0.78, 0.43), (-0.33, -0.78, 0.25), (-0.6, -0.5, 0.25), (-0.6, 0.3, 0.25)], 0.008, M.CHROME,
                         segs=5, fillet_r=0.05))
    if p.worn:
        cover = p.rbox((0.34, 0.3, 0.3), (0, 0, 0), C.PAINT_RED, radius=0.04, inner=(2, 2, 2))
        p.lay_on_floor([cover], rot=(70, 0, 20), at=(0.35, -0.95))
    # gauges on the front of the top section
    for x, cell in ((-0.4, "gauge"), (0.2, "gauge_red")):
        p.cyl(0.012, 0.06, (x, -0.66, 1.6), C.BRASS, axis="Y", segs=6)
        p.cyl(0.065, 0.04, (x, -0.7, 1.6), C.BRASS, axis="Y", segs=14)
        disc_face(p, 0.058, 0.004, (x, -0.722, 1.6), atlas(cell), axis="-Y", segs=14)
    # relief valve + supply riser + return
    p.lathe([(0.03, 0.0), (0.03, 0.08), (0.045, 0.1), (0.045, 0.18), (0.02, 0.2), (0.0, 0.21)], (0.3, -0.3, 1.69), C.BRASS, segs=8)
    lag = not p.worn
    pipe = C.LAGGING if lag else M.CAST_IRON
    rad = 0.075 if lag else 0.045
    p.tube([(-0.45, -0.1, 1.69), (-0.45, -0.1, 2.1)], rad, pipe, segs=10)
    p.tube([(0.25, 0.1, 1.69), (0.25, 0.1, 1.95), (0.72, 0.1, 1.95)], rad, pipe, segs=10, fillet_r=0.1)
    if p.worn:
        for i, z in enumerate((1.75, 2.0)):
            tat = p.rbox((0.17, 0.17, 0.09), (-0.45, -0.1, z), C.LAGGING, radius=0.04, inner=(2, 2, 1), wrinkle=0.012,
                         seed=p.seed + i)
            del tat
        p.rbox((0.4, 0.3, 0.06), (-0.75, -0.6, 0.03), C.LAGGING, radius=0.02, inner=(3, 2, 1), wrinkle=0.015, seed=p.seed + 5)
    p.tube([(0.45, 0.45, 0.35), (0.62, 0.45, 0.35), (0.62, 0.45, 0.04)], 0.045, M.CAST_IRON, segs=8, fillet_r=0.06)
    p.tube([(-0.65, -0.2, 0.4), (-0.75, -0.2, 0.4), (-0.75, -0.2, 1.3), (-0.65, -0.2, 1.3)], 0.025, M.CAST_IRON, segs=6, fillet_r=0.05)
    p.cyl(0.05, 0.25, (-0.75, -0.2, 0.85), M.CAST_IRON, segs=8)
    # expansion tank on its stand
    tx = 0.78
    p.lathe([(0.0, -0.45), (0.12, -0.44), (0.2, -0.4), (0.22, -0.34), (0.22, 0.34), (0.2, 0.4), (0.12, 0.44), (0.0, 0.45)],
            (tx, 0.1, 1.72), C.PAINT_GREY, segs=14, axis="Y")
    for y in (-0.2, 0.4):
        p.box((0.06, 0.06, 1.5), (tx, y, 0.75), C.PAINT_GREY, bevel=0.004)
        p.tube([(tx - 0.22, y, 1.72), (tx - 0.2, y, 1.55), (tx, y, 1.49), (tx + 0.2, y, 1.55), (tx + 0.22, y, 1.72)], 0.012, C.PAINT_GREY,
               segs=5)
    p.box((0.4, 0.8, 0.02), (tx, 0.1, 0.01), C.PAINT_GREY, bevel=0.004)
    p.lathe([(0.02, 0.0), (0.02, 0.05), (0.04, 0.06), (0.04, 0.12), (0.0, 0.13)], (tx, -0.36, 1.72), C.BRASS, segs=8, axis="-Y")
    disc_face(p, 0.035, 0.004, (tx, -0.495, 1.72), atlas("gauge"), axis="-Y", segs=12)
    p.collider((0.0, 0.05, 1.05), (2.0, 1.4, 2.1))


def school_card_catalog(p: Prop) -> None:
    """Library card catalog (0.9 x 1.3 x 0.5): an oak cabinet of 30 small drawers (5 x 6) with brass cup pulls
    and label holders on a four-legged stand with a stretcher shelf. Worn: three drawers pulled out, one
    on the floor with its cards spilled."""
    W, D = 0.9, 0.48
    z0, z1 = 0.36, 1.27
    p.box((W + 0.04, D + 0.04, 0.03), (0, 0, 1.285), C.OAK, bevel=0.006, grain="X")
    p.box((W, D, 0.04), (0, 0, z0 - 0.02), C.OAK_DARK, bevel=0.004, grain="X")
    for sx in (-1, 1):
        p.box((0.02, D, z1 - z0), (sx * (W / 2 - 0.01), 0, (z0 + z1) / 2), C.OAK, bevel=0.003, grain="Z")
    p.box((W - 0.04, 0.01, z1 - z0), (0, D / 2 - 0.005, (z0 + z1) / 2), M.PARTICLE, bevel=0.0)
    p.box((W - 0.04, D - 0.02, z1 - z0 - 0.01), (0, 0.01, (z0 + z1) / 2), C.OAK_DARK, bevel=0.0, wear=0.0)
    for sx in (-1, 1):
        for sy in (-1, 1):
            F.tapered_leg(p, sx * (W / 2 - 0.04), sy * (D / 2 - 0.04), 0.0, z0 - 0.04, 0.05, 0.035, C.OAK)
    p.box((W - 0.1, D - 0.1, 0.02), (0, 0, 0.12), C.OAK, bevel=0.003, grain="X")
    cols, rows = 5, 6
    dw, dh = (W - 0.06) / cols, (z1 - z0 - 0.02) / rows
    r = p.vrng("pull")
    pulled = {}
    if p.worn:
        pulled = {(1, 2): 0.18, (3, 4): 0.3, (4, 1): "floor"}
    yf = -D / 2
    for c in range(cols):
        for rw in range(rows):
            x = -W / 2 + 0.03 + dw * (c + 0.5)
            z = z1 - 0.01 - dh * (rw + 0.5)
            grp = [p.box((dw - 0.008, 0.02, dh - 0.008), (x, yf - 0.002, z), C.OAK, bevel=0.002, grain="X")]
            grp.append(plate(p, 0.06, 0.03, (x, yf - 0.0135, z + 0.03), atlas("card_label"), t=0.003, mat=C.PRINT, wear=0.4))
            grp.append(p.box((0.04, 0.012, 0.014), (x, yf - 0.018, z - 0.02), C.BRASS, bevel=0.0))
            st = pulled.get((c, rw))
            if st is None:
                continue
            tray = p.hollow((dw - 0.03, 0.42, dh - 0.03), (x, yf + 0.21, z - 0.004), C.OAK_DARK, wall=0.008, open_face="+Z", bevel=0.0)
            grp.append(tray)
            grp.append(p.box((dw - 0.05, 0.34, dh - 0.05), (x, yf + 0.2, z - 0.006), M.PAPER, bevel=0.0, wear=0.2))
            if st == "floor":
                lo, hi = p.bounds(grp)
                cc = (lo + hi) * 0.5
                p.move(grp, (-cc.x, -cc.y, -cc.z))
                p.lay_on_floor(grp, rot=(0, 0, 0), at=(0.15, -0.6), yaw=35)
                rr = p.vrng("cards")
                for i in range(14):
                    cd = p.box((0.125, 0.075, 0.0012), (0.1 + rr.uniform(-0.3, 0.3), -0.75 + rr.uniform(-0.2, 0.2), 0.001 + i * 0.0008),
                               M.PAPER, bevel=0.0, wear=0.2)
                    G.xform(cd.obj, rot=(0, 0, rr.uniform(0, 180)), pivot=(0, -0.75, 0))
            else:
                p.move(grp, (0, -st, 0))
    del r
    p.collider((0, 0, 0.65), (W + 0.04, D + 0.04, 1.3))


def school_flagpole(p: Prop) -> None:
    """Flagpole (origin bottom centre): an 8 m tapered aluminium pole on a round concrete base with a
    collar, a gilt ball truck with its pulley, halyard down to a cleat, and a sun-bleached, rain-streaked
    striped flag gone ragged at the fly end, hanging limp. Worn: half-mast, torn to a third of its length."""
    p.cyl(0.38, 0.22, (0, 0, 0.11), C.CONCRETE, segs=16, bevel=0.02)
    p.cyl(0.12, 0.06, (0, 0, 0.25), C.ALU, segs=12, bevel=0.01)
    p.lathe([(0.065, 0.0), (0.06, 3.0), (0.048, 6.0), (0.04, 8.0), (0.0, 8.0)], (0, 0, 0.22), C.ALU, segs=12, cap_bottom=False)
    p.cyl(0.05, 0.04, (0, 0, 8.24), C.ALU, segs=10)
    sphere(p, 0.065, (0, 0, 8.33), C.BRASS, segs=10, rings=6)
    p.cyl(0.03, 0.02, (0.06, 0, 8.18), C.ALU, axis="Y", segs=8)
    cz = 1.25
    p.box((0.02, 0.03, 0.18), (0.075, 0, cz), M.CAST_IRON, bevel=0.004)
    p.tube([(0.09, 0, cz - 0.08), (0.1, 0, cz), (0.09, 0, cz + 0.08)], 0.006, M.CAST_IRON, segs=5)
    top = 8.18
    hoist = 7.85 if not p.worn else 4.6
    for dx in (0.06, 0.085):
        p.tube([(dx, 0.0, top), (0.075 + (dx - 0.06) * 0.2, -0.01, hoist), (0.1, 0.0, cz + 0.05)], 0.003, C.ROPE, segs=4, cap=False)
    fw, fh = 1.5, 0.9
    tear = 0.62 if p.worn else 0.88
    r = p.rng("flag")
    jag = [r.uniform(-0.12, 0.05) for _ in range(12)]

    def keep(u, v):
        return u < tear + jag[int(v * 11.99)] * (1.0 if p.worn else 0.6)

    def fn(u, v):
        droop = u * u * (0.45 if p.worn else 0.32)
        return (-u * u * fw * 0.3, 0.1 * math.sin(u * 5.0 + v * 1.5) * u, -droop * fw * (0.6 + 0.4 * (1 - v)))

    flag = cloth_sheet(p, fw, fh, 12, 6, fn, C.PRINT, rect=atlas("flag"), keep=keep, key="flag")
    G.xform(flag.obj, loc=(0.075, -0.0015, hoist - fh))
    p.collider((0, 0, 4.15), (0.3, 8.3, 0.3))
    p.collider((0, 0, 0.12), (0.76, 0.24, 0.76))


# ================================================================================================
# Fire station
# ================================================================================================


def _coil(p: Prop, center, R: float = 0.27, r_in: float = 0.07, thick: float = 0.075, mat: str = C.HOSE, axis: str = "-Y",
          ridges: int = 6, segs: int = 16) -> core.Part:
    """Rolled flat hose: a thick disc whose face carries one ridge per wrap (a lathe, closed profile)."""
    prof = [(r_in, 0.0), (r_in, thick)]
    for k in range(1, ridges + 1):
        rr = r_in + (R - r_in) * k / ridges
        prof += [(rr - (R - r_in) / ridges * 0.5, thick - 0.006), (rr, thick)]
    prof += [(R, thick * 0.5), (R, 0.0), (r_in + 0.002, 0.0)]
    return p.lathe(prof, center, mat, segs=segs, axis=axis, cap_bottom=False, cap_top=False, edge_deg=60.0)


def _coupling(p: Prop, center, axis: str, r: float = 0.035) -> core.Part:
    return p.lathe([(r * 0.8, 0.0), (r, 0.005), (r, 0.03), (r * 1.15, 0.035), (r * 1.15, 0.055), (r, 0.06), (r * 0.9, 0.08),
                    (0.0, 0.08)], center, M.BRASS, segs=10, axis=axis, cap_bottom=False)


def _nozzle(p: Prop, base, axis: str = "-Z") -> list:
    """Brass shut-off nozzle with a bale, pointing along axis from base."""
    out = [p.lathe([(0.032, 0.0), (0.034, 0.05), (0.028, 0.06), (0.028, 0.1), (0.036, 0.11), (0.036, 0.15), (0.022, 0.24),
                    (0.016, 0.26), (0.0, 0.262)], base, M.BRASS, segs=10, axis=axis, cap_bottom=True)]
    return out


def fire_hose_rack(p: Prop) -> None:
    """Wall hose rack (origin on the wall plane, bottom centre): red steel back straps with two cradles, each
    holding a rolled cream canvas hose with its brass coupling, two brass nozzles in clips below. Worn: one
    roll gone, the other slumped half off its cradle with a length trailing to the floor."""
    red = C.PAINT_RED
    for sx in (-1, 1):
        p.box((0.08, 0.012, 1.4), (sx * 0.45, -0.006, 0.7), red, bevel=0.003, grain="Z")
    p.box((1.18, 0.012, 0.08), (0, -0.014, 1.33), red, bevel=0.003, grain="X")
    p.box((1.18, 0.012, 0.08), (0, -0.014, 0.6), red, bevel=0.003, grain="X")
    for i, x in enumerate((-0.3, 0.3)):
        for sx in (-1, 1):
            bar(p, (x + sx * 0.18, -0.02, 0.62), (x + sx * 0.12, -0.2, 0.69), 0.03, 0.012, red, bevel=0.002)
        p.tube([(x - 0.12, -0.2, 0.7), (x - 0.05, -0.2, 0.66), (x + 0.05, -0.2, 0.66), (x + 0.12, -0.2, 0.7)], 0.01, red, segs=6)
        p.tube([(x - 0.12, -0.04, 0.7), (x - 0.05, -0.04, 0.66), (x + 0.05, -0.04, 0.66), (x + 0.12, -0.04, 0.7)], 0.01, red, segs=6)
        gone = p.worn and i == 0
        if gone:
            continue
        cz = 0.66 + 0.27
        coil = [_coil(p, (0, 0, 0), axis="-Y")]
        coil.append(_coupling(p, (0.0, -0.035, 0.27), "+X"))
        if p.worn:
            p.rotate(coil, rot=(-14, 0, 22))
            p.move(coil, (x + 0.05, -0.1, cz - 0.03))
            p.tube([(x + 0.3, -0.13, 0.9), (x + 0.4, -0.2, 0.6), (x + 0.38, -0.25, 0.2), (x + 0.2, -0.3, 0.02), (x - 0.2, -0.32, 0.02)],
                   0.035, C.HOSE, segs=8, fillet_r=0.12, cap=True)
        else:
            p.move(coil, (x, -0.11, cz))
    for i, x in enumerate((-0.25, 0.25)):
        p.box((0.06, 0.04, 0.03), (x, -0.03, 0.45), red, bevel=0.004)
        p.tube([(x - 0.03, -0.05, 0.45), (x - 0.03, -0.08, 0.45), (x + 0.03, -0.08, 0.45), (x + 0.03, -0.05, 0.45)], 0.005, M.CHROME, segs=4)
        if p.worn and i == 1:
            continue
        _nozzle(p, (x, -0.08, 0.5), "-Z")
    p.collider((0, -0.17, 0.7), (1.2, 0.34, 1.4))


def _cut(part: core.Part, planes) -> None:
    """Splits a part's faces along planes [(co, no), ...] (so materials can change exactly there)."""
    me = part.obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    for co, no in planes:
        geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no)
    K.canon_bm(bm)  # bisect emits new elements in a run-dependent order
    bm.to_mesh(me)
    bm.free()
    me.update()


def _bands(p: Prop, part: core.Part, zs, h: float = 0.045, mat: str = C.REFLECT) -> None:
    """Reflective trim bands of height h centred on each z in zs (faces recoloured, no extra shells)."""
    _cut(part, [((0, 0, z + k * h / 2), (0, 0, 1)) for z in zs for k in (-1, 1)])
    p.set_mat(part, mat, lambda poly: any(abs(poly.center.z - z) < h / 2 for z in zs))


def _turnout_coat(p: Prop, cx: float, y: float, top: float) -> list:
    body = p.rbox((0.52, 0.22, 0.82), (cx, y, top - 0.42), C.TURNOUT, radius=0.07, inner=(2, 1, 2), wrinkle=0.008,
                  seed=p.seed + int(cx * 10), taper_top=0.12)
    _bands(p, body, (top - 0.76, top - 0.4))
    _cut(body, [((cx - 0.015, 0, 0), (1, 0, 0)), ((cx + 0.015, 0, 0), (1, 0, 0))])
    p.set_mat(body, C.PL_BLACK, lambda poly: abs(poly.center.x - cx) < 0.015 and poly.normal.y < -0.5)
    out = [body]
    for sx in (-1, 1):
        sl = p.rbox((0.13, 0.15, 0.64), (cx + sx * 0.29, y - 0.03, top - 0.4), C.TURNOUT, radius=0.05, inner=(1, 1, 2), wrinkle=0.01,
                    seed=p.seed + 7)
        _bands(p, sl, (top - 0.62,), h=0.04)
        G.xform(sl.obj, rot=(0, sx * 6, 0), pivot=(cx + sx * 0.27, y, top - 0.08))
        out.append(sl)
    for sx in (-1, 1):
        out.append(p.box((0.13, 0.03, 0.14), (cx + sx * 0.14, y - 0.115, top - 0.62), C.TURNOUT, bevel=0.008))
    out.append(p.rbox((0.26, 0.2, 0.09), (cx, y + 0.01, top - 0.01), C.TURNOUT, radius=0.035, inner=(2, 1, 1)))
    return out


def _helmet(p: Prop, c, mat: str) -> list:
    x, y, z = c
    dome = p.lathe([(0.0, 0.17), (0.07, 0.16), (0.115, 0.12), (0.135, 0.05), (0.135, 0.0), (0.0, 0.0)], (x, y, z + 0.015), mat,
                   segs=10, cap_bottom=False)
    brim = p.rbox((0.3, 0.42, 0.016), (x, y + 0.05, z + 0.012), mat, radius=0.007, inner=(2, 2, 1), bulge=(0, 0, -0.03))
    comb = p.box((0.02, 0.26, 0.04), (x, y + 0.01, z + 0.17), mat, bevel=0.008)
    shield = p.box((0.1, 0.012, 0.13), (x, y - 0.13, z + 0.1), C.PL_BLACK, bevel=0.01)
    G.xform(shield.obj, rot=(-14, 0, 0), pivot=(x, y - 0.13, z + 0.04))
    return [dome, brim, comb, shield]


def _bunker_set(p: Prop, cx: float, y: float) -> list:
    """Bunker pants rolled down over the boots, braces hanging, ready to step into."""
    out = []
    for sx in (-1, 1):
        out.append(p.rbox((0.12, 0.3, 0.36), (cx + sx * 0.08, y - 0.03, 0.28), C.RUBBER, radius=0.04, inner=(1, 1, 1)))
        out.append(p.box((0.122, 0.06, 0.025), (cx + sx * 0.08, y - 0.15, 0.115), C.YELLOW_PL, bevel=0.0))
    folds = p.rbox((0.46, 0.34, 0.26), (cx, y, 0.5), C.TURNOUT, radius=0.08, inner=(2, 1, 2), wrinkle=0.02, seed=p.seed + 11,
                   taper_top=0.12)
    _bands(p, folds, (0.44,), h=0.04)
    out.append(folds)
    out.append(p.rbox((0.42, 0.3, 0.06), (cx, y, 0.65), C.TURNOUT, radius=0.025, inner=(1, 1, 1)))
    for sx in (-1, 1):
        out.append(p.tube([(cx + sx * 0.12, y + 0.1, 0.67), (cx + sx * 0.14, y + 0.12, 0.85), (cx + sx * 0.18, y + 0.05, 0.95)], 0.012,
                          C.RUBBER, segs=4, fillet_r=0.08))
    return out


def fire_turnout_locker(p: Prop) -> None:
    """Turnout-gear cubbies (2.4 x 2.0 x 0.6): three open oak bays with a helmet shelf, coat hooks and a
    blank brass name plate; in each a tan turnout coat with reflective bands, a helmet up top, and the bunker
    pants rolled down over the boots ready to step into. Worn: one bay empty (its crew left in a hurry), a
    helmet knocked to the floor."""
    W, D, H = 2.4, 0.6, 2.0
    wood = C.OAK
    for i in range(4):
        x = -W / 2 + 0.02 + i * (W - 0.04) / 3
        p.box((0.03, D, H), (x, 0, H / 2), wood, bevel=0.004, grain="Z")
    p.box((W, D + 0.02, 0.03), (0, 0, H - 0.015), wood, bevel=0.005, grain="X")
    p.box((W, D, 0.1), (0, 0, 0.05), C.OAK_DARK, bevel=0.004, grain="X")
    p.box((W - 0.04, 0.012, H - 0.12), (0, D / 2 - 0.006, H / 2 + 0.04), M.PARTICLE, bevel=0.0)
    bw = (W - 0.04) / 3
    for b in range(3):
        cx = -W / 2 + 0.02 + bw * (b + 0.5)
        p.box((bw - 0.03, D - 0.03, 0.025), (cx, 0.015, 1.68), wood, bevel=0.003, grain="X")
        p.box((0.16, 0.004, 0.04), (cx, -D / 2 - 0.002, H - 0.06), C.BRASS, bevel=0.001)
        p.tube([(cx, D / 2 - 0.02, 1.55), (cx, D / 2 - 0.09, 1.53), (cx, D / 2 - 0.1, 1.58)], 0.007, M.CHROME, segs=5)
        empty = p.worn and b == 2
        if empty:
            continue
        _turnout_coat(p, cx, 0.12, 1.55)
        _bunker_set(p, cx, -0.04)
        hm = [C.PL_BLACK, C.YELLOW_PL, "plastic_red"][b]
        hel = _helmet(p, (cx, 0.0, 1.695), hm)
        if p.worn and b == 1:
            p.lay_on_floor(hel, rot=(0, 160, 0), at=(cx + 0.3, -0.6), yaw=40)
    p.collider((0, 0, H / 2), (W, D, H))


def fire_pole(p: Prop) -> None:
    """Brass slide pole (origin bottom centre): 80 mm polished brass, 6.2 m, a floor flange with a
    rubber landing ring and a ceiling bracket at the top. Worn: tarnished, the landing ring split."""
    p.cyl(0.04, 6.2, (0, 0, 3.1), C.BRASS, segs=16, wear=0.6)
    p.lathe([(0.12, 0.0), (0.12, 0.012), (0.06, 0.02), (0.05, 0.06), (0.0, 0.06)], (0, 0, 0), C.BRASS, segs=16)
    torus(p, 0.085, 0.025, (0, 0, 0.025), C.RUBBER, axis="Z", segs=18, rsegs=6, arc=330.0 if p.worn else 360.0)
    p.lathe([(0.0, 0.0), (0.05, 0.0), (0.06, 0.08), (0.1, 0.11), (0.1, 0.13), (0.0, 0.13)], (0, 0, 6.07), M.CAST_IRON, segs=14)
    for sx in (-1, 1):
        bar(p, (sx * 0.06, 0, 6.12), (sx * 0.12, 0, 6.19), 0.03, 0.02, M.CAST_IRON, bevel=0.003)
    p.collider((0, 0, 3.1), (0.24, 6.2, 0.24))


def fire_hose_hanging(p: Prop) -> None:
    """Drying hoses in the hose tower (origin on the wall plane, bottom centre): a steel arm bracket 3.9 m up
    with three saddles, three long cream canvas hoses hung flat over them in loops, brass couplings at the
    ends. Worn: one hose fallen into a heap on the floor, the others stained."""
    st = C.PAINT_GREY
    p.box((1.0, 0.02, 0.12), (0, -0.01, 3.95), st, bevel=0.004, grain="X")
    for sx in (-1, 1):
        bar(p, (sx * 0.45, -0.02, 3.95), (sx * 0.45, -0.28, 3.95), 0.04, 0.05, st, grain="Y", bevel=0.003)
        bar(p, (sx * 0.45, -0.02, 3.7), (sx * 0.45, -0.26, 3.93), 0.03, 0.03, st, bevel=0.003)
    p.cyl(0.03, 1.0, (0, -0.26, 3.97), st, axis="X", segs=10)
    r = p.rng("hoses")
    for i, x in enumerate((-0.32, 0.0, 0.32)):
        if p.worn and i == 2:
            for k in range(5):
                coil = p.tube([(x + 0.25 * math.cos(a), -0.35 + 0.18 * math.sin(a), 0.04 + k * 0.05) for a in
                               [j * 2 * math.pi / 10 for j in range(10)]], 0.035, C.HOSE, segs=6, closed=True)
                G.xform(coil.obj, scale=(1.0, 1.0, 0.5), pivot=(x, -0.35, 0.04 + k * 0.05))
            continue
        lf, lb = r.uniform(0.15, 0.6), r.uniform(0.4, 1.1)
        sway = r.uniform(-0.04, 0.04)
        pts = [(x + sway, -0.31, lf), (x + sway * 0.5, -0.31, 2.6), (x, -0.305, 3.9), (x, -0.26, 4.0), (x, -0.215, 3.9),
               (x - sway * 0.3, -0.21, 2.8), (x - sway, -0.2, lb)]
        h = p.tube(pts, 0.035, C.HOSE, segs=8, fillet_r=0.06, cap=True)
        # drained hose hangs flat: squash it across the wall direction
        G.xform(h.obj, scale=(1.25, 0.5, 1.0), pivot=(x, -0.26, 0.0))
        _coupling(p, (x + sway, -0.31, lf), "-Z", r=0.038)
        _coupling(p, (x - sway, -0.2, lb), "-Z", r=0.038)
    p.collider((0, -0.15, 2.0), (1.0, 0.3, 4.0))


def fire_siren(p: Prop) -> None:
    """Mechanical roof siren (origin bottom centre): a red rotor drum with stator ports between a flared
    projector bell (-Y) and a finned motor housing (+Y), on a yoke atop a steel pipe post with a roof
    flange. Worn: paint gone to rust, the bell dented, a wire hanging."""
    red = C.PAINT_RED
    p.box((0.3, 0.3, 0.012), (0, 0, 0.006), C.PAINT_GREY, bevel=0.003)
    p.cyl(0.045, 0.8, (0, 0, 0.41), C.PAINT_GREY, segs=10)
    p.cyl(0.06, 0.05, (0, 0, 0.04), C.PAINT_GREY, segs=10)
    cz = 0.98
    p.tube([(-0.2, 0.0, cz), (-0.2, 0.0, 0.82), (0.2, 0.0, 0.82), (0.2, 0.0, cz)], 0.016, red, segs=6, fillet_r=0.04)
    p.cyl(0.05, 0.03, (0, 0, 0.815), red, segs=10)
    for sx in (-1, 1):
        p.cyl(0.03, 0.03, (sx * 0.19, 0, cz), M.CAST_IRON, axis="X", segs=8)
    p.cyl(0.155, 0.17, (0, 0.0, cz), M.CAST_IRON, axis="Y", segs=16)
    for k in range(12):
        a = 2 * math.pi * k / 12
        s = p.box((0.05, 0.17, 0.02), (math.cos(a) * 0.168, 0.0, cz + math.sin(a) * 0.168), red, bevel=0.003)
        G.xform(s.obj, rot=(0, -math.degrees(a), 0), pivot=(math.cos(a) * 0.168, 0.0, cz + math.sin(a) * 0.168))
    for y in (-0.09, 0.09):
        p.cyl(0.18, 0.02, (0, y, cz), red, axis="Y", segs=16, bevel=0.004)
    bell = p.lathe([(0.165, 0.0), (0.168, 0.025), (0.18, 0.06), (0.198, 0.085), (0.198, 0.09), (0.19, 0.09), (0.172, 0.06),
                    (0.15, 0.02)], (0, -0.1, cz), red, segs=16, axis="-Y", cap_bottom=False, cap_top=False)
    p.lathe([(0.0, 0.0), (0.09, 0.0), (0.06, 0.05), (0.0, 0.06)], (0, -0.1, cz), M.CAST_IRON, segs=12, axis="-Y")
    if p.worn:
        for v in bell.obj.data.vertices:
            if v.co.z > cz + 0.13 and v.co.x > 0.05:
                v.co.y += 0.02
                v.co.z -= 0.025
    p.lathe([(0.12, 0.0), (0.12, 0.2), (0.09, 0.24), (0.0, 0.25)], (0, 0.1, cz), red, segs=14, axis="Y", cap_bottom=False)
    for k in range(5):
        p.cyl(0.128, 0.008, (0, 0.13 + k * 0.03, cz), red, axis="Y", segs=14)
    p.box((0.08, 0.06, 0.06), (0, 0.22, cz - 0.12), M.CAST_IRON, bevel=0.006)
    wire = [(0, 0.24, cz - 0.15), (0.02, 0.2, 0.7), (0.05, 0.05, 0.4), (0.046, 0.0, 0.12)]
    if p.worn:
        wire = [(0, 0.24, cz - 0.15), (0.06, 0.26, 0.75), (0.1, 0.24, 0.45), (0.16, 0.18, 0.3)]
    p.tube(wire, 0.006, C.PL_BLACK, segs=4, fillet_r=0.1)
    p.collider((0, 0, 0.6), (0.5, 0.5, 1.2))


def fire_extinguisher(p: Prop) -> None:
    """Wall fire extinguisher (origin on the wall plane, bottom centre; hang ~1 m up): red steel cylinder
    on a strap bracket, chrome valve head with lever and gauge, black hose to a horn clipped at the side.
    Worn: dented and faded, the gauge needle in the red, the pin gone."""
    y = -0.085
    p.box((0.07, 0.012, 0.3), (0, -0.006, 0.3), C.PAINT_BLACK, bevel=0.002)
    p.box((0.05, 0.03, 0.04), (0, -0.025, 0.47), C.PAINT_BLACK, bevel=0.003)
    p.lathe([(0.0, 0.0), (0.062, 0.0), (0.072, 0.012), (0.074, 0.03), (0.074, 0.36), (0.066, 0.4), (0.045, 0.425), (0.022, 0.43),
             (0.0, 0.43)], (0, y, 0.05), M.STEEL_RED, segs=14)
    torus(p, 0.076, 0.004, (0, y, 0.3), C.PAINT_BLACK, axis="Z", segs=14, rsegs=4)
    p.lathe([(0.024, 0.0), (0.024, 0.03), (0.018, 0.04), (0.018, 0.06), (0.0, 0.065)], (0, y, 0.48), M.CHROME, segs=8)
    p.box((0.03, 0.12, 0.012), (0, y - 0.03, 0.548), M.CHROME, bevel=0.003)
    lev = p.box((0.03, 0.1, 0.01), (0, y - 0.02, 0.556), M.CHROME, bevel=0.003)
    G.xform(lev.obj, rot=(-8, 0, 0), pivot=(0, y + 0.03, 0.555))
    p.cyl(0.018, 0.012, (0.03, y, 0.52), M.CHROME, axis="X", segs=10)
    disc_face(p, 0.016, 0.002, (0.037, y, 0.52), atlas("gauge_red"), axis="X", segs=10)
    if not p.worn:
        p.tube([(-0.01, y - 0.025, 0.56), (-0.03, y - 0.025, 0.56)], 0.002, M.CHROME, segs=4)
    p.tube([(0, y - 0.07, 0.53), (0.02, y - 0.09, 0.48), (0.08, y - 0.03, 0.4), (0.085, y, 0.2)], 0.008, C.PL_BLACK, segs=5,
           fillet_r=0.04)
    p.lathe([(0.008, 0.0), (0.012, 0.03), (0.0, 0.03)], (0.085, y, 0.2), C.PL_BLACK, segs=6, axis="-Z")
    p.collider((0, -0.1, 0.3), (0.2, 0.2, 0.6))


# ================================================================================================
# Bank
# ================================================================================================


def bank_vault_door(p: Prop) -> None:
    """Vault entrance surround (origin bottom centre on the wall line, the wall runs through y = 0): a heavy
    2.2 x 2.5 machined steel bezel 0.35 deep with stepped engine-turned frames, a 0.9 x 2.1 m opening
    lined with steel jambs, bolt sockets down the latch jamb, the hinge pillar and a day-gate frame on the
    inner face. The door leaf is a kit door (models/kit/door_vault) hung in the opening. Worn: torch scorch
    round the latch jamb, scratches."""
    W, H, D = 2.2, 2.5, 0.35
    ow, oh = 0.9, 2.1
    yf = -D / 2
    sw = (W - ow) / 2
    for sx in (-1, 1):
        p.box((sw, 0.08, H), (sx * (ow / 2 + sw / 2), yf + 0.04, H / 2), C.VAULT, bevel=0.012, grain="Z")
    p.box((ow, 0.08, H - oh), (0, yf + 0.04, oh + (H - oh) / 2), C.VAULT, bevel=0.012, grain="X")
    for sx in (-1, 1):
        p.box((0.12, 0.05, oh + 0.12), (sx * (ow / 2 + 0.06), yf - 0.02, (oh + 0.12) / 2), C.VAULT, bevel=0.01, grain="Z")
        p.box((0.06, 0.03, H - 0.14), (sx * (W / 2 - 0.1), yf - 0.01, (H - 0.14) / 2), C.VAULT, bevel=0.008, grain="Z")
    p.box((ow + 0.24, 0.05, 0.12), (0, yf - 0.02, oh + 0.06), C.VAULT, bevel=0.01, grain="X")
    p.box((W - 0.14, 0.03, 0.06), (0, yf - 0.01, H - 0.1), C.VAULT, bevel=0.008, grain="X")
    for sx in (-1, 1):
        p.box((0.03, D, oh), (sx * (ow / 2 + 0.015), 0, oh / 2), C.VAULT, bevel=0.004, grain="Z", wear=0.6)
    p.box((ow + 0.06, D, 0.03), (0, 0, oh + 0.015), C.VAULT, bevel=0.004, grain="X")
    p.box((ow, D, 0.012), (0, 0, 0.006), C.VAULT, bevel=0.002, grain="Y")
    for k in range(6):
        z = 0.35 + k * 0.28
        p.cyl(0.03, 0.02, (ow / 2 + 0.001, -0.07, z), C.PL_BLACK, axis="X", segs=10)
        p.cyl(0.03, 0.02, (ow / 2 + 0.001, 0.0, z + 0.14), C.PL_BLACK, axis="X", segs=10)
    for z in (0.3, 1.0, 1.75):
        p.cyl(0.06, 0.32, (-ow / 2 - 0.07, yf - 0.065, z), C.VAULT, segs=14, bevel=0.01)
    for sx in (-1, 1):
        p.box((0.1, 0.05, H - 0.2), (sx * (ow / 2 + 0.05 + 0.04), D / 2 + 0.025, (H - 0.2) / 2), C.PAINT_GREY, bevel=0.006, grain="Z")
    p.box((ow + 0.28, 0.05, 0.1), (0, D / 2 + 0.025, oh + 0.05), C.PAINT_GREY, bevel=0.006, grain="X")
    pts = []
    for sx in (-1, 1):
        for k in range(8):
            pts.append((sx * (W / 2 - 0.035), yf - 0.025 + 0.02, 0.15 + k * 0.31))
    for k in range(6):
        pts.append((-0.85 + k * 0.34, yf - 0.025 + 0.02, H - 0.035))
    rivets(p, [(x, yf - 0.0, z) for x, _, z in pts], 0.014, C.VAULT, axis="-Y", h=0.008, segs=8)
    p.collider((0, 0, H / 2), (W, D, H))


def _vault_leaf(p: Prop, broken: bool) -> None:
    """Kit door leaf (hinged at the origin, bottom of the hinge edge; x 0..0.82, z 0..2.05, centred on
    y = 0). Outer face -Y (Godot +Z), inner face +Y."""
    W, H, T = 0.82, 2.05, 0.14
    hc = (0.43, 1.12)
    hole_r = 0.27
    r = p.rng("leaf")
    if not broken:
        p.rbox((W, T, H), (W / 2, 0, H / 2), C.VAULT, radius=0.025, inner=(2, 1, 4), edge_deg=30)
        p.box((W - 0.14, 0.01, H - 0.2), (W / 2, -T / 2 - 0.003, H / 2), C.VAULT, bevel=0.004)
    else:
        n = 40
        jag = [r.uniform(-0.035, 0.05) for _ in range(n)]
        bm = bmesh.new()
        rings = {}
        for side, yy in (("f", -T / 2), ("b", T / 2)):
            inner, outer = [], []
            for i in range(n):
                a = 2 * math.pi * i / n
                d = Vector((math.cos(a), math.sin(a)))
                rr = hole_r + jag[i] + (0.01 if side == "b" else 0.0)
                inner.append(bm.verts.new((hc[0] + d.x * rr, yy, hc[1] + d.y * rr)))
                tx = ((W if d.x > 0 else 0.0) - hc[0]) / d.x if abs(d.x) > 1e-6 else 1e9
                tz = ((H if d.y > 0 else 0.0) - hc[1]) / d.y if abs(d.y) > 1e-6 else 1e9
                t = min(tx, tz)
                outer.append(bm.verts.new((hc[0] + d.x * t, yy, hc[1] + d.y * t)))
            rings[side] = (inner, outer)
        corners = {}
        for side, yy in (("f", -T / 2), ("b", T / 2)):
            corners[side] = [bm.verts.new((x, yy, z)) for x, z in ((W, H), (0.0, H), (0.0, 0.0), (W, 0.0))]
        ca = [math.atan2(H - hc[1], W - hc[0]), math.atan2(H - hc[1], -hc[0]), math.atan2(-hc[1], -hc[0]), math.atan2(-hc[1], W - hc[0])]
        ca = [a % (2 * math.pi) for a in ca]
        for side in ("f", "b"):
            inner, outer = rings[side]
            for i in range(n):
                j = (i + 1) % n
                a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (j if j else n) / n
                vs = [inner[i], outer[i]]
                for k, a in enumerate(ca):
                    if a0 < a < a1:
                        vs.append(corners[side][k])
                vs += [outer[j], inner[j]]
                f = bm.faces.new(vs if side == "b" else list(reversed(vs)))
                del f
        fi, fo = rings["f"]
        bi, bo = rings["b"]
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((fi[i], fi[j], bi[j], bi[i]))
        bm.faces.new([corners["f"][0], corners["f"][1], corners["b"][1], corners["b"][0]])
        bm.faces.new([corners["f"][1], corners["f"][2], corners["b"][2], corners["b"][1]])
        bm.faces.new([corners["f"][2], corners["f"][3], corners["b"][3], corners["b"][2]])
        bm.faces.new([corners["f"][3], corners["f"][0], corners["b"][0], corners["b"][3]])
        bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-5)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        K.canon_bm(bm)
        slab = G._obj(p._name("slab"), bm)
        part = p.add(slab, C.VAULT, grain="Z")
        hole_faces = lambda poly: (Vector((poly.center.x - hc[0], poly.center.z - hc[1])).length < hole_r + 0.06 and
                                   abs(poly.normal.y) < 0.5)
        p.set_mat(part, C.BURNT, hole_faces)
        # slag and scorch ring around the cut on both faces
        for side, yy in ((-1, -T / 2 - 0.002), (1, T / 2 + 0.002)):
            sb = bmesh.new()
            ring_i, ring_o = [], []
            for i in range(n):
                a = 2 * math.pi * i / n
                ri = hole_r + jag[i] + (0.01 if side > 0 else 0.0) - 0.002
                ro = ri + 0.035 + 0.06 * abs(math.sin(i * 2.3 + side)) + r.uniform(0.0, 0.02)
                ox = min(W - 0.015, max(0.015, hc[0] + math.cos(a) * ro))
                ring_i.append(sb.verts.new((hc[0] + math.cos(a) * ri, yy, hc[1] + math.sin(a) * ri)))
                ring_o.append(sb.verts.new((ox, yy, hc[1] + math.sin(a) * ro)))
            for i in range(n):
                j = (i + 1) % n
                q = [ring_i[i], ring_o[i], ring_o[j], ring_i[j]]
                sb.faces.new(q if side > 0 else list(reversed(q)))
            scorch = p.add(G._obj(p._name("scorch"), sb), C.BURNT, wear=0.3, edge_deg=60.0)
            del scorch
            for k in range(6):
                a = r.uniform(0, 2 * math.pi)
                rr = hole_r + r.uniform(0.0, 0.03)
                sphere(p, r.uniform(0.008, 0.016), (hc[0] + math.cos(a) * rr, yy + side * 0.004, hc[1] + math.sin(a) * rr), C.RUST,
                       segs=5, rings=3)
    # outer face: spoked wheel, combination dial, time-lock plate
    yo = -T / 2
    if not broken:
        p.cyl(0.07, 0.06, (hc[0], yo - 0.03, hc[1]), C.VAULT, axis="Y", segs=14, bevel=0.01)
        p.cyl(0.035, 0.12, (hc[0], yo - 0.1, hc[1]), C.CHROME, axis="Y", segs=10)
        torus(p, 0.22, 0.018, (hc[0], yo - 0.15, hc[1]), C.CHROME, axis="Y", segs=24, rsegs=6)
        for k in range(5):
            a = 2 * math.pi * k / 5 + 0.3
            tip = (hc[0] + math.cos(a) * 0.22, yo - 0.15, hc[1] + math.sin(a) * 0.22)
            p.tube([(hc[0], yo - 0.15, hc[1]), tip], 0.013, C.CHROME, segs=6, cap=False)
            p.lathe([(0.016, 0.0), (0.022, 0.03), (0.02, 0.07), (0.0, 0.075)], tip, C.CHROME, segs=8, axis="-Y")
    dz = 1.62
    p.cyl(0.1, 0.02, (hc[0], yo - 0.01, dz), C.CHROME, axis="Y", segs=20)
    disc_face(p, 0.085, 0.03, (hc[0], yo - 0.035, dz), atlas("dial"), axis="-Y", segs=20)
    p.cyl(0.03, 0.03, (hc[0], yo - 0.06, dz), C.PL_BLACK, axis="Y", segs=10)
    plate(p, 0.4, 0.2, (hc[0], yo - 0.004, 1.88), atlas("timelock"), t=0.008, mat=C.PRINT, bevel=0.002)
    if not broken:
        plate(p, 0.3, 0.06, (hc[0], yo - 0.004, 0.55), atlas("card_label"), t=0.004, mat=C.PRINT)
    # hinge barrels on the hinge edge
    for z in (0.35, 1.0, 1.7):
        p.cyl(0.05, 0.34, (-0.01, yo - 0.02, z), C.VAULT, segs=12, bevel=0.012)
        p.box((0.12, 0.03, 0.28), (0.06, yo - 0.012, z), C.VAULT, bevel=0.006)
    # inner face: bolt-work behind glass
    yi = T / 2
    p.box((0.64, 0.012, 1.3), (0.42, yi + 0.006, 1.12), M.STEEL_BLACK, bevel=0.002)
    bars = []
    for z in (0.6, 1.64):
        bars.append(p.box((0.58, 0.02, 0.05), (0.42, yi + 0.022, z), C.CHROME, bevel=0.004))
    bars.append(p.box((0.06, 0.02, 1.08), (0.7, yi + 0.022, 1.12), C.CHROME, bevel=0.004))
    for z in (0.75, 1.12, 1.5):
        bars.append(p.cyl(0.06, 0.016, (0.3, yi + 0.022, z), M.BRASS, axis="Y", segs=14))
        bars.append(p.cyl(0.035, 0.03, (0.3, yi + 0.03, z), C.CHROME, axis="Y", segs=10))
        bars.append(bar(p, (0.3, yi + 0.032, z), (0.68, yi + 0.032, z + 0.08), 0.025, 0.012, C.CHROME, bevel=0.002))
    if broken:
        for q in bars:
            lo, hi = p.bounds([q])
            c = (lo + hi) * 0.5
            if Vector((c.x - hc[0], c.z - hc[1])).length < hole_r + 0.1:
                p.rotate([q], rot=(0, r.uniform(-25, 25), 0), pivot=(c.x, c.y, c.z))
    if not broken:
        p.box((0.66, 0.006, 1.32), (0.42, yi + 0.05, 1.12), M.GLASS, bevel=0.0)
    for x0, z0, x1, z1 in ((0.08, 0.44, 0.76, 0.48), (0.08, 1.76, 0.76, 1.8), (0.08, 0.44, 0.12, 1.8), (0.72, 0.44, 0.76, 1.8)):
        p.box((x1 - x0, 0.05, z1 - z0), ((x0 + x1) / 2, yi + 0.025, (z0 + z1) / 2), C.CHROME, bevel=0.004)
    # the locking bolts in the latch edge
    for k in range(7):
        z = 0.3 + k * 0.24
        for yb in (-0.035, 0.035):
            b = p.cyl(0.024, 0.07, (W + 0.005, yb, z + (0.12 if yb > 0 else 0.0)), C.CHROME, axis="X", segs=10, bevel=0.005)
            if broken and r.random() < 0.6:
                G.xform(b.obj, rot=(0, r.uniform(-20, 20), r.uniform(-25, 25)), pivot=(W, yb, z))


def door_vault(p: Prop) -> None:
    """Bank vault door leaf for the POI kit (models/kit/door_vault): a 0.14 m engine-turned steel slab, spoked
    wheel, combination dial and brass time-lock plate outside; bolt-work behind glass inside; seven pairs of
    locking bolts in the latch edge, heavy hinge barrels."""
    _vault_leaf(p, False)


def door_vault_broken(p: Prop) -> None:
    """The vault leaf after it was torched open: a ragged slag-rimmed hole where the wheel was, the dial and
    time-lock left, the bolt-work glass gone and the bars bent, bolts twisted."""
    _vault_leaf(p, True)


def bank_teller_counter(p: Prop) -> None:
    """Teller station (3.0 x 2.2 x 0.8): a mahogany counter of raised panels under a white-marble top with a
    brass kick rail, and above it a brass-and-glass teller cage of three bays - glass in brass frames
    either side and the teller's window in the middle with its arched grille, deal trough and bell.
    Behind: cash drawers. Worn: one pane cracked out, papers. Destroyed: the glass smashed out, the grille
    torn and bent down, the marble split, the cash drawer dumped."""
    W, D, H = 3.0, 0.72, 1.05
    wood = C.MAHOGANY
    yf = -D / 2
    p.box((W, D - 0.05, H - 0.1), (0, 0.025, (H - 0.1) / 2 + 0.05), wood, bevel=0.004, grain="X")
    p.box((W - 0.02, D - 0.07, 0.08), (0, 0.03, 0.04), C.OAK_DARK, bevel=0.004, grain="X")
    for i in range(5):
        x = -W / 2 + 0.3 + i * 0.6
        # fielded panel from plain boxes (G.panel's insets come out in a run-dependent face order)
        p.box((0.54, 0.02, 0.62), (x, yf + 0.03, 0.5), wood, bevel=0.003, grain="Z")
        p.box((0.42, 0.012, 0.5), (x, yf + 0.016, 0.5), wood, bevel=0.006, grain="Z")
    for i in range(6):
        p.box((0.04, 0.03, 0.88), (-W / 2 + 0.02 + i * 0.592, yf + 0.03, 0.5), wood, bevel=0.004, grain="Z")
    p.box((W, 0.035, 0.05), (0, yf + 0.03, 0.88), wood, bevel=0.006, grain="X")
    p.tube([(-W / 2 + 0.05, yf - 0.05, 0.15), (W / 2 - 0.05, yf - 0.05, 0.15)], 0.022, C.BRASS, segs=10)
    for x in (-1.2, 0.0, 1.2):
        p.box((0.03, 0.06, 0.03), (x, yf - 0.02, 0.15), C.BRASS, bevel=0.005)
    split = p.destroyed
    if split:
        # the slab cracked through and one half dropped a little
        p.box((1.6, D + 0.08, 0.04), (-0.73 - 0.0, 0.0, H - 0.08), C.MARBLE, bevel=0.006, grain="X")
        q = p.box((1.44, D + 0.08, 0.04), (0.81, 0.0, H - 0.08), C.MARBLE, bevel=0.006, grain="X")
        G.xform(q.obj, rot=(0, 3, -1), pivot=(0.09, 0, H - 0.1))
    else:
        p.box((W + 0.06, D + 0.08, 0.04), (0, 0.0, H - 0.08 + 0.0), C.MARBLE, bevel=0.008, grain="X")
    top = H - 0.06
    # teller cage
    cy = 0.12
    zc0, zc1 = top + 0.06, 2.12
    p.box((W, 0.08, 0.06), (0, cy, top + 0.03), C.MAHOGANY, bevel=0.006, grain="X")
    for x in (-1.5, -0.5, 0.5, 1.5):
        xx = max(-1.48, min(1.48, x))
        p.box((0.04, 0.04, zc1 - zc0), (xx, cy, (zc0 + zc1) / 2), C.BRASS, bevel=0.006, grain="Z")
        p.lathe([(0.03, 0.0), (0.03, 0.02), (0.02, 0.04), (0.035, 0.06), (0.0, 0.08)], (xx, cy, zc1), C.BRASS, segs=8)
    p.box((W, 0.06, 0.06), (0, cy, zc1 - 0.03), C.BRASS, bevel=0.006, grain="X")
    p.box((W, 0.04, 0.03), (0, cy, 1.45), C.BRASS, bevel=0.004, grain="X")
    for bx in (-1.0, 1.0):
        for z0, z1 in ((zc0, 1.43), (1.47, zc1 - 0.06)):
            w, h = 0.94, z1 - z0
            c = (bx, cy, (z0 + z1) / 2)
            if p.destroyed or (p.worn and bx > 0 and z0 < 1.4):
                F.shatter_pane(p, w, h, c, M.GLASS, t=0.005, impact=(0.1, 0.0), key=f"pane{bx}{z0:.1f}",
                               missing_inner=0.95, missing_outer=0.4 if p.destroyed else 0.15, floor_shards=4 if p.destroyed else 0,
                               floor_at=(bx, -0.7))
            else:
                p.box((w, 0.006, h), c, M.GLASS, bevel=0.0)
    # the teller window: arched grille over an opening, glass above
    bars = []
    for i in range(13):
        x = -0.42 + i * 0.07
        za = 1.18 + 0.12 * math.cos((x / 0.45) * math.pi / 2)
        bars.append(p.cyl(0.006, 1.43 - za, (x, cy, (za + 1.43) / 2), C.BRASS, segs=6))
    arch = [(0.45 * math.cos(a), cy, 1.18 + 0.12 * math.sin(a)) for a in [math.pi * i / 10 for i in range(11)]]
    bars.append(p.tube(arch, 0.012, C.BRASS, segs=6))
    if p.destroyed:
        p.rotate(bars, rot=(-55, 0, 8), pivot=(0, cy, 1.43))
    p.box((0.94, 0.006, zc1 - 0.06 - 1.47), (0, cy, (1.47 + zc1 - 0.06) / 2), M.GLASS, bevel=0.0) if not p.destroyed else None
    p.box((0.4, 0.3, 0.02), (0, cy - 0.05, top + 0.01), C.MARBLE, bevel=0.004)
    p.box((0.3, 0.2, 0.02), (0, cy - 0.06, top + 0.025), C.BRASS, bevel=0.003)
    p.lathe([(0.0, 0.0), (0.04, 0.0), (0.04, 0.008), (0.03, 0.02), (0.035, 0.04), (0.012, 0.06), (0.0, 0.065)], (-0.3, -0.2, top),
            C.BRASS, segs=10)
    plate(p, 0.24, 0.05, (0.0, cy - 0.022, 1.5), atlas("card_label"), t=0.004)
    # cash drawers on the teller side
    for i, x in enumerate((-0.9, 0.0, 0.9)):
        pull = 0.0
        if p.worn and i == 1:
            pull = 0.3
        F.drawer(p, x - 0.25, 0.7, x + 0.25, 0.85, D / 2 + 0.02, 0.4, wood, t=0.02, style="slab", handle="bar", handle_mat=C.BRASS,
                 pull=0.0, key=f"cd{i}")
        if pull:
            p.box((0.48, 0.4, 0.1), (x, D / 2 - 0.15, 0.78), wood, bevel=0.003)
    if p.worn:
        scatter_papers(p, (-0.8, 0.0), 3, 0.2, "slips", z=top)
    if p.destroyed:
        scatter_papers(p, (0.5, -0.8), 7, 0.5, "floor")
        tray = p.hollow((0.45, 0.35, 0.08), (0, 0, 0), C.MAHOGANY, wall=0.012, open_face="+Z", bevel=0.0)
        p.lay_on_floor([tray], rot=(160, 0, 0), at=(-0.9, -0.85), yaw=25)
    p.collider((0, 0.0, 1.1), (W + 0.06, D + 0.08, 2.2))


def bank_deposit_boxes(p: Prop) -> None:
    """Safe-deposit wall (2.0 x 2.1 x 0.5): a dark steel cabinet whose 1.8 m face is 96 brass box doors in
    three sizes, two key locks each (town2_deposit_boxes). Worn: six doors pried open on bent hinges, a
    box pulled half out. Destroyed: a whole run of doors jemmied, leaves and emptied boxes on the floor,
    papers strewn."""
    W, D = 2.0, 0.5
    st = M.STEEL_BLACK
    p.box((W, D, 0.15), (0, 0, 0.075), st, bevel=0.006)
    p.box((W, D, 0.15), (0, 0, 2.025), st, bevel=0.006)
    p.box((W + 0.04, D + 0.04, 0.03), (0, 0, 2.115), st, bevel=0.006)
    for sx in (-1, 1):
        p.box((0.1, D, 1.8), (sx * 0.95, 0, 1.05), st, bevel=0.006, grain="Z")
    p.box((1.8, D - 0.02, 1.8), (0, 0.01, 1.05), st, bevel=0.0, wear=0.0)
    face_y = -D / 2 - 0.004
    plate(p, DEP_FACE, DEP_FACE, (0, face_y, 0.15 + DEP_FACE / 2), (0.0, 0.0, 1.0, 1.0), t=0.008, mat=C.DEPOSIT, wear=0.3)
    cells = dep_cells()
    pried = []
    if p.worn:
        pried = [3, 12, 21, 30, 46, 61, 77, 90]
    if p.destroyed:
        pried += [8, 9, 10, 11, 16, 17, 18, 19, 64, 65, 66, 72, 73]
    rr = p.vrng("pry")
    for i, k in enumerate(pried):
        x0, z0, x1, z1 = cells[k]
        x0 -= DEP_FACE / 2
        x1 -= DEP_FACE / 2
        z0 += 0.15
        z1 += 0.15
        w, h = x1 - x0, z1 - z0
        cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
        p.hollow((w - 0.012, 0.03, h - 0.012), (cx, face_y - 0.003 + 0.014, cz), st, wall=0.006, open_face="-Y", bevel=0.0, wear=0.2)
        p.box((w - 0.02, 0.002, h - 0.02), (cx, face_y + 0.028, cz), M.PL_BLACK, bevel=0.0, wear=0.0)
        leaf = p.box((w - 0.012, 0.008, h - 0.012), (0, 0, 0), C.BRASS, bevel=0.002)
        if p.destroyed and rr.random() < 0.55:
            p.lay_on_floor([leaf], rot=(90, 0, 0), at=(cx + rr.uniform(-0.2, 0.2), -0.5 - rr.uniform(0, 0.5)), yaw=rr.uniform(0, 180))
        else:
            G.xform(leaf.obj, loc=((w - 0.012) / 2, 0, 0))
            G.xform(leaf.obj, rot=(0, rr.uniform(-8, 8), -rr.uniform(75, 130)))
            G.xform(leaf.obj, loc=(x0 + 0.006, face_y - 0.008, cz))
        if i % 3 == 0:
            bx = p.hollow((w - 0.03, 0.42, min(0.1, h - 0.03)), (0, 0, 0), C.ALU, wall=0.004, open_face="+Z", bevel=0.0)
            if p.destroyed:
                p.lay_on_floor([bx], rot=(rr.uniform(-10, 10), 0, 0), at=(cx + rr.uniform(-0.3, 0.3), -0.65 - rr.uniform(0, 0.4)),
                               yaw=rr.uniform(-60, 60))
            else:
                G.xform(bx.obj, loc=(cx, face_y + 0.21 - 0.18, cz - h / 2 + 0.06))
    if p.destroyed:
        scatter_papers(p, (0.0, -0.8), 9, 0.55, "papers")
        p.collider((0, -0.3, 1.06), (W + 0.04, D + 0.6, 2.13))
    else:
        p.collider((0, 0, 1.06), (W + 0.04, D + 0.04, 2.13))


def _stanchion(p: Prop, x: float, y: float = 0.0) -> list:
    out = [p.lathe([(0.0, 0.0), (0.155, 0.0), (0.16, 0.012), (0.14, 0.03), (0.09, 0.05), (0.04, 0.065), (0.025, 0.08), (0.0, 0.08)],
                   (x, y, 0), C.BRASS, segs=16)]
    out.append(p.cyl(0.025, 0.86, (x, y, 0.08 + 0.43), C.BRASS, segs=10))
    out.append(p.lathe([(0.0, 0.0), (0.035, 0.0), (0.04, 0.02), (0.03, 0.04), (0.036, 0.06), (0.02, 0.085), (0.0, 0.09)], (x, y, 0.93),
                       C.BRASS, segs=10))
    return out


def bank_stanchions(p: Prop) -> None:
    """Queue posts (2.4 x 1.0 x 0.32): three brass stanchions on domed bases with red velvet ropes slung
    between them on brass snap hooks. Worn: the end post knocked over, its rope trailing on the floor."""
    xs = (-1.04, 0.0, 1.04)
    posts = {i: _stanchion(p, x) for i, x in enumerate(xs)}
    for i in range(2):
        a, b = xs[i] + 0.04, xs[i + 1] - 0.04
        z = 0.9
        fell = p.worn and i == 1
        if fell:
            pts = [(a, 0, z), (a + 0.2, -0.04, 0.4), (a + 0.4, -0.08, 0.03), (a + 0.8, -0.12, 0.02)]
        else:
            pts = [(a + (b - a) * t, 0.0, z - 0.16 * math.sin(math.pi * t)) for t in [k / 8 for k in range(9)]]
        p.tube(pts, 0.018, C.FELT_RED, segs=6, fillet_r=0.1 if fell else 0.0, cap=True)
        p.lathe([(0.02, 0.0), (0.022, 0.04), (0.0, 0.045)], (a + 0.005, 0, z), C.BRASS, segs=8, axis="-X")
        if not fell:
            p.lathe([(0.02, 0.0), (0.022, 0.04), (0.0, 0.045)], (b - 0.005, 0, z), C.BRASS, segs=8, axis="X")
    if p.worn:
        grp = posts[2]
        p.rotate(grp, rot=(0, 0, 0))
        p.lay_on_floor(grp, rot=(0, 88, 0), at=(1.35, -0.15), yaw=-25)
        p.collider((0, -0.05, 0.5), (2.9, 0.45, 1.0))
    else:
        p.collider((0, 0, 0.5), (2.4, 0.32, 1.0))


def _cash_brick(p: Prop, c, yaw: float = 0.0, rot=(0, 0, 0)) -> core.Part:
    obj = G.box(p._name("cash"), (0.16, 0.07, 0.045), (0, 0, 0), 0.002)
    top, side = atlas("cash_top"), atlas("cash_side")

    def fr(poly):
        n = poly.normal
        if abs(n.z) > 0.9:
            return (*top, 0, 1, n.z < 0)
        if abs(n.y) > 0.9:
            return (*side, 0, 2, n.y > 0)
        return (side[0], side[1], side[0] + (side[2] - side[0]) * 0.3, side[3], 1, 2, False)

    core.set_face_uvs(obj, fr)
    G.xform(obj, rot=rot)
    G.xform(obj, rot=(0, 0, yaw), loc=c)
    return p.add(obj, C.PRINT, uv="keep", wear=0.4)


def bank_money_bags(p: Prop) -> None:
    """Money on the floor (0.6 x 0.35 x 0.5): three canvas bank bags tied at the neck and a scatter of
    banded cash bricks. Worn: one bag slit open with bricks spilling out and loose notes."""
    r = p.rng("bags")
    for i, (x, y, s, yaw) in enumerate(((-0.14, 0.08, 1.0, 10), (0.15, 0.1, 0.85, -25), (0.0, -0.1, 0.75, 70))):
        h = 0.3 * s
        bag = p.rbox((0.26 * s, 0.2 * s, h), (x, y, h / 2), C.CANVAS, radius=0.07 * s, inner=(2, 2, 2), wrinkle=0.01, seed=p.seed + i,
                     taper_top=0.55, bulge=(0.01, 0.01, 0.0))
        G.xform(bag.obj, rot=(0, 0, yaw), pivot=(x, y, 0))
        p.cyl(0.03 * s, 0.05 * s, (x, y, h + 0.005), C.CANVAS, segs=8)
        p.rbox((0.09 * s, 0.07 * s, 0.06 * s), (x, y, h + 0.055 * s), C.CANVAS, radius=0.02, inner=(1, 1, 1), wrinkle=0.008,
               seed=p.seed + 20 + i, taper_top=0.3)
        torus(p, 0.03 * s, 0.006, (x, y, h - 0.005), C.ROPE, axis="Z", segs=10, rsegs=4)
        if p.worn and i == 2:
            F.slash(p, (x - 0.08 * s, y - 0.05, h * 0.4), 0.12, 0.4, key="slit")
    bricks = [((-0.05, -0.22, 0.0225), 15), ((0.2, -0.18, 0.0225), -30), ((0.22, -0.18, 0.0675), -24)]
    if p.worn:
        bricks += [((-0.22, -0.2, 0.0225), 50), ((0.05, -0.32, 0.0225), 80), ((-0.1, -0.33, 0.0225), -10)]
        for k in range(5):
            n = p.box((0.156, 0.066, 0.0015), (r.uniform(-0.25, 0.25), r.uniform(-0.35, -0.15), 0.001 + 0.0005 * k), C.PRINT, bevel=0.0,
                      uv="planar", uv_axis="Z", rect=atlas("cash_top"))
            G.xform(n.obj, rot=(0, 0, r.uniform(0, 180)), pivot=n.obj.data.vertices[0].co.copy())
    for c, yaw in bricks:
        _cash_brick(p, c, yaw)
    p.collider((0, -0.05, 0.16), (0.6, 0.5, 0.32))


# ================================================================================================
# Vehicle wrecks
# ================================================================================================


def _glass(p: Prop, w: float, h: float, center, state: str, key: str, axis: str = "X") -> None:
    """A window pane in a side (axis X: pane in the YZ plane) or end wall (axis Y: XZ plane).
    state: 'ok' | 'gone' | 'shattered'."""
    if state == "gone":
        return
    if state == "shattered":
        parts = F.shatter_pane(p, w, h, (0, 0, 0), C.WINDOW, t=0.006, impact=(0.05, -0.1), spokes=4, rings=2,
                               missing_inner=1.0, missing_outer=0.35, key=key)
        if axis == "X":
            p.rotate(parts, rot=(0, 0, 90))
        p.move(parts, center)
        return
    size = (0.008, w, h) if axis == "X" else (w, 0.008, h)
    p.box(size, center, C.WINDOW, bevel=0.0, wear=0.2)


def _win_states(p: Prop, n: int, key: str) -> list[str]:
    r = p.vrng(key)
    out = []
    for i in range(n):
        if p.destroyed:
            out.append("gone")
            continue
        x = r.random()
        if p.worn:
            out.append("gone" if x < 0.55 else ("shattered" if x < 0.68 else "ok"))
        else:
            out.append("gone" if x < 0.1 else ("shattered" if x < 0.17 else "ok"))
    return out


def _lamp(p: Prop, c, r: float, lens: str, axis: str = "-Y", bezel: str = C.CHROME, depth: float = 0.05) -> None:
    p.lathe([(r * 1.2, 0.0), (r * 1.15, depth), (0.0, depth)], c, bezel, segs=8, axis=axis, cap_bottom=False)
    off = Vector((0, 0, 0))
    off["XYZ".index(axis[-1])] = (depth + 0.002) * (-1 if axis.startswith("-") else 1)
    p.lathe([(r, 0.0), (0.0, 0.014)], tuple(Vector(c) + off * 0.7), lens, segs=8, axis=axis, cap_bottom=False)


def school_bus_wreck(p: Prop) -> None:
    """1970s conventional school bus (10.9 x 3.0 x 2.5): yellow body on a nose-hood chassis, black rub rails,
    twenty split-sash side windows, a two-leaf folding entry door, stop arm, crossover and side mirrors,
    warning lamps front and rear, rear emergency door, green vinyl bench seats inside, dual rear wheels on
    flat tyres. Front -Y. Clean: abandoned on flat tyres, a few windows out, the door folded open. Worn:
    rotted - most glass gone, the stop arm hanging out, rust. Destroyed: burnt-out shell on its rims."""
    burnt = p.destroyed
    paint = C.BURNT if burnt else C.BUS_YELLOW
    blk = C.BURNT if burnt else C.PAINT_BLACK
    chrome = C.RUST if burnt else C.CHROME
    seat_m = C.BURNT if burnt else C.BUS_VINYL
    yA, yB = -4.45, 2.35
    r_out = 0.5
    axle_z = 0.3 if burnt else 0.44
    zl = axle_z - 0.47  # body drop on flat tyres / rims
    X = 1.22
    y0, y1 = -3.8, 5.35
    # --- wheels ------------------------------------------------------------------------------
    for sx in (-1, 1):
        wheel(p, sx * 1.0, yA, r_out, 0.29, 0.27, burnt=burnt, flat=0.32, segs=10)
        wheel(p, sx * 1.07, yB, r_out, 0.29, 0.25, burnt=burnt, flat=0.32, segs=10)
        if not burnt:
            p.lathe([(0.29, -0.11), (0.47, -0.12), (0.5, -0.06), (0.5, 0.06), (0.47, 0.12), (0.29, 0.11)], (sx * 0.8, yB, axle_z - 0.02),
                    C.TYRE, segs=8, axis="X", cap_bottom=False, cap_top=False)
    # --- body sides with the rear arch, door gap on the right (-X) -----------------------------
    zb, zw0, zw1, zr = 0.62 + zl, 1.72 + zl, 2.42 + zl, 2.55 + zl
    arches = [(yB, 0.62)]
    arch_panel(p, X - 0.03, 0.03, y0, y1, zb, zw0, arches, axle_z, paint, wear=0.9)
    arch_panel(p, -X, 0.03, -3.05, y1, zb, zw0, arches, axle_z, paint, wear=0.9)
    p.box((0.03, 0.75, zw0 - zb), (-X + 0.015, -3.425, (zb + zw0) / 2), C.UNDER, bevel=0.0, wear=0.0)
    for sx in (-1, 1):
        for z in (0.88, 1.27, 1.66):
            ys = y0 if sx > 0 else -3.05
            p.box((0.03, y1 - ys, 0.055), (sx * (X + 0.012), (ys + y1) / 2, z + zl), blk, bevel=0.008, grain="Y")
    # window band: pillars, sashes, panes
    ws = _win_states(p, 22, "win")
    nwin = 10
    py0, py1 = -2.95, 5.2
    pw = (py1 - py0) / nwin
    for sx in (-1, 1):
        x = sx * (X - 0.02)
        for i in range(nwin + 1):
            y = py0 + i * pw
            p.box((0.04, 0.09, zw1 - zw0), (x, y, (zw0 + zw1) / 2), paint, bevel=0.006, grain="Z")
        if sx < 0:
            p.box((0.04, 0.09, zw1 - zw0), (x, -3.75, (zw0 + zw1) / 2), paint, bevel=0.006, grain="Z")
        else:
            p.box((0.04, py0 - y0, zw1 - zw0), (x, (y0 + py0) / 2, (zw0 + zw1) / 2), paint, bevel=0.0, grain="Y")
        for i in range(nwin):
            y = py0 + (i + 0.5) * pw
            st = ws[i + (0 if sx > 0 else nwin)]
            _glass(p, pw - 0.09, 0.36, (x, y, zw0 + 0.2), st, f"lw{sx}{i}")
            _glass(p, pw - 0.09, 0.3, (x + sx * 0.012, y, zw1 - 0.17), "gone" if st == "gone" and i % 2 else ("ok" if st == "shattered" else st),
                   f"uw{sx}{i}")
            p.box((0.05, pw - 0.08, 0.035), (x, y, zw1 - 0.33), C.ALU if not burnt else C.BURNT, bevel=0.004, grain="Y")
        p.box((0.05, y1 - y0, 0.06), (x + sx * 0.005, (y0 + y1) / 2, zw0 - 0.01), paint, bevel=0.006, grain="Y")
        p.box((0.04, y1 - y0, zr - zw1), (x, (y0 + y1) / 2, (zw1 + zr) / 2), paint, bevel=0.006, grain="Y")
        p.box((0.03, y1 - y0, 0.05), (sx * (X + 0.012), (y0 + y1) / 2, zw1 + 0.06), blk, bevel=0.008, grain="Y")
    # roof
    roof = [(-X, zr)]
    for i in range(1, 12):
        t = -1 + 2 * i / 12
        roof.append((X * t, zr + 0.38 * (1 - abs(t) ** 2.4) ** 0.5))
    roof.append((X, zr))
    roof.append((X - 0.02, zr - 0.13))
    roof.append((-X + 0.02, zr - 0.13))
    rf = p.prism(list(reversed(roof)), y1 - y0 + 0.06, paint, plane="XZ", offset=y0 - 0.03, grain="Y", wear=0.8)
    if burnt:
        for v in rf.obj.data.vertices:
            t = max(0.0, 1 - ((v.co.y - 1.0) / 4.2) ** 2)
            v.co.z -= 0.1 * t
    for yy in (-1.5, 2.6):
        p.box((0.6, 0.6, 0.05), (0, yy, zr + 0.4), C.ALU if not burnt else C.BURNT, bevel=0.01)
    # front wall: cowl, windshield, header with warning lamps and the blank sign box
    p.box((2 * X, 0.04, zw0 - zb), (0, y0, (zb + zw0) / 2), paint, bevel=0.004)
    wst = "gone" if burnt else ("shattered" if p.worn else "ok")
    for sx in (-1, 1):
        _glass(p, 1.08, zw1 - zw0 + 0.05, (sx * 0.58, y0 - 0.01, (zw0 + zw1) / 2 + 0.02), wst if sx > 0 else ("gone" if p.worn else "ok"),
               f"ws{sx}", axis="Y")
        p.box((0.06, 0.05, zw1 - zw0 + 0.1), (sx * (X - 0.03), y0 - 0.02, (zw0 + zw1) / 2 + 0.02), paint, bevel=0.006)
    p.box((0.06, 0.05, zw1 - zw0 + 0.1), (0, y0 - 0.02, (zw0 + zw1) / 2 + 0.02), paint, bevel=0.006)
    p.box((2 * X, 0.05, zr - zw1 + 0.12), (0, y0 - 0.005, (zw1 + zr) / 2 + 0.05), paint, bevel=0.006)
    p.box((1.3, 0.06, 0.3), (0, y0 - 0.06, zr + 0.25), paint, bevel=0.008)
    p.box((1.24, 0.065, 0.24), (0, y0 - 0.065, zr + 0.25), blk, bevel=0.004)
    p.box((1.18, 0.07, 0.19), (0, y0 - 0.068, zr + 0.25), paint, bevel=0.004)
    for sx in (-1, 1):
        for k, lens in enumerate((C.LENS_A, C.LENS_R)):
            _lamp(p, (sx * (0.8 + k * 0.24), y0 - 0.03, zr + 0.22), 0.085, C.BURNT if burnt else lens, bezel=blk)
    # rear wall: emergency door, rear windows, lamps, bumper
    p.box((2 * X, 0.04, zr - zb + 0.05), (0, y1, (zb + zr) / 2), paint, bevel=0.004)
    p.box((0.62, 0.03, 1.75), (0, y1 + 0.025, zb + 0.15 + 0.875), paint, bevel=0.008)
    _glass(p, 0.5, 0.6, (0, y1 + 0.045, zw0 + 0.3), "gone" if p.worn else "ok", "rd", axis="Y")
    for sx in (-1, 1):
        _glass(p, 0.62, 0.6, (sx * 0.78, y1 + 0.025, zw0 + 0.3), "gone" if burnt else ("shattered" if p.worn and sx > 0 else "ok"), f"rw{sx}",
               axis="Y")
        _lamp(p, (sx * 0.95, y1 + 0.02, 1.15 + zl), 0.09, C.BURNT if burnt else C.LENS_R, axis="Y", bezel=blk)
        _lamp(p, (sx * 0.95, y1 + 0.02, 0.92 + zl), 0.07, C.BURNT if burnt else C.LENS_A, axis="Y", bezel=blk)
        for k, lens in enumerate((C.LENS_A, C.LENS_R)):
            _lamp(p, (sx * (0.8 + k * 0.24), y1 + 0.02, zr + 0.18), 0.085, C.BURNT if burnt else lens, axis="Y", bezel=blk)
    p.box((2 * X + 0.06, 0.2, 0.24), (0, y1 + 0.1, 0.62 + zl), blk, bevel=0.02)
    # hood, fenders, grille, headlights, bumper
    hood = p.prism([(-5.25, 0.8), (-3.8, 0.8), (-3.8, 1.62), (-5.12, 1.52), (-5.24, 1.42)], 1.64, paint, plane="YZ", offset=-0.82,
                   grain="Y", wear=0.9)
    G.xform(hood.obj, loc=(0, 0, zl))
    if p.worn:
        for v in hood.obj.data.vertices:
            d = (Vector((v.co.x, v.co.y)) - Vector((0.4, -4.9))).length
            if d < 0.35 and v.co.z > 1.3 + zl:
                v.co.z -= 0.05 * (1 - d / 0.35)
    for sx in (-1, 1):
        x0 = 0.82 if sx > 0 else -1.18
        arch_panel(p, x0, 0.36, -5.18, -3.8, 0.6 + zl, 1.2 + zl, [(yA, 0.6)], axle_z, paint, wear=0.9)
        _lamp(p, (sx * 1.0, -5.2, 1.0 + zl), 0.09, C.BURNT if burnt else C.LENS_C, bezel=chrome)
        _lamp(p, (sx * 1.0, -5.2, 0.82 + zl), 0.05, C.BURNT if burnt else C.LENS_A, bezel=chrome)
        p.tube([(sx * 1.12, -5.0, 1.2 + zl), (sx * 1.12, -5.15, 1.7 + zl), (sx * 1.05, -5.3, 1.85 + zl)], 0.012, blk, segs=5, fillet_r=0.1)
        if not (p.worn and sx > 0):
            p.cyl(0.13, 0.05, (sx * 1.05, -5.33, 1.85 + zl), blk, axis="Y", segs=12)
        p.tube([(sx * X, y0 + 0.1, zw1 - 0.1), (sx * (X + 0.22), y0 - 0.05, zw1 - 0.05), (sx * (X + 0.25), y0 - 0.05, zw1 - 0.2)], 0.012,
               blk, segs=5, fillet_r=0.05)
        if not burnt:
            p.box((0.04, 0.2, 0.32), (sx * (X + 0.25), y0 - 0.05, zw1 - 0.38), blk, bevel=0.01)
    p.box((1.0, 0.04, 0.48), (0, -5.25, 1.1 + zl), chrome, bevel=0.01)
    for k in range(6):
        p.box((0.94, 0.03, 0.025), (0, -5.27, 0.92 + k * 0.07 + zl), blk, bevel=0.0)
    bmp = p.box((2.42, 0.18, 0.22), (0, -5.36, 0.62 + zl), blk, bevel=0.02, grain="X")
    if p.worn:
        G.xform(bmp.obj, rot=(0, 4, 0), pivot=(-1.2, -5.36, 0.62 + zl))
    # entry door (right, -X): two leaves of two glazed panels, folded open unless worn/destroyed
    if not burnt:
        leaves = []
        for k in range(4):
            yk = -3.75 + 0.18 * k + 0.09
            grp = [p.box((0.03, 0.17, 1.65), (-X - 0.005, yk, zb + 0.15 + 0.825), C.BUS_YELLOW, bevel=0.004, grain="Z")]
            grp.append(p.box((0.035, 0.12, 0.7), (-X - 0.005, yk, zb + 1.25), C.WINDOW, bevel=0.0))
            grp.append(p.box((0.035, 0.12, 0.5), (-X - 0.005, yk, zb + 0.55), C.WINDOW, bevel=0.0))
            grp.append(p.box((0.04, 0.01, 1.65), (-X - 0.005, yk + 0.085, zb + 0.15 + 0.825), C.PL_BLACK, bevel=0.0))
            leaves.append(grp)
        ang = 70 if p.cond == "clean" else 80
        for k, grp in enumerate(leaves):
            if k < 2:
                p.rotate(grp, rot=(0, 0, -ang if k == 0 else ang), pivot=(-X, -3.75 + 0.18 * k, 0))
            else:
                p.rotate(grp, rot=(0, 0, ang if k == 3 else -ang), pivot=(-X, -3.75 + 0.18 * (k + 1), 0))
        if p.worn:
            p.remove(leaves[3])
    for k in range(2):
        p.box((0.6, 0.28, 0.04), (-X + 0.3, -3.42, zb + 0.08 + k * 0.28), blk, bevel=0.005)
    # stop arm on the driver's side (+X)
    if not burnt:
        arm = [plate(p, 0.45, 0.45, (0, 0, 0), atlas("stop"), t=0.012, mat=C.PRINT, wear=0.6)]
        oct_obj = arm[0].obj
        for v in oct_obj.data.vertices:
            a = math.atan2(v.co.z, v.co.x)
            seg = math.pi / 4
            k = math.cos(((a + math.pi / 8) % seg) - seg / 2)
            rr = max(abs(v.co.x), abs(v.co.z))
            if rr > 0.2:
                sc = 0.225 / max(1e-6, math.hypot(v.co.x, v.co.z) * k)
                v.co.x *= sc
                v.co.z *= sc
        arm.append(p.box((0.3, 0.02, 0.04), (-0.33, 0, 0), blk, bevel=0.004))
        if p.worn:
            p.rotate(arm, rot=(0, 0, -100))
            p.rotate(arm, rot=(0, 25, 0), pivot=(0, 0, 0))
            p.move(arm, (X + 0.05, -3.0, 1.85 + zl))
            p.rotate(arm, rot=(0, 0, 0))
        else:
            p.rotate(arm, rot=(0, 0, 90))
            p.move(arm, (X + 0.03, -2.7, 1.9 + zl))
    # interior: floor, driver's station, bench seats
    p.box((2 * X - 0.08, y1 - y0, 0.05), (0, (y0 + y1) / 2, 0.95 + zl), C.PL_BLACK if not burnt else C.BURNT, bevel=0.0, wear=0.0)
    p.box((2 * X - 0.1, 0.5, 0.35), (0, y0 + 0.28, 1.6 + zl), C.PL_BLACK if not burnt else C.BURNT, bevel=0.01)
    p.box((0.5, 0.45, 0.12), (0.62, -3.15, 1.35 + zl), seat_m, bevel=0.02)
    p.box((0.5, 0.1, 0.55), (0.62, -2.92, 1.65 + zl), seat_m, bevel=0.02)
    if not burnt:
        wh = torus(p, 0.22, 0.016, (0.62, -3.5, 1.72 + zl), C.PL_BLACK, axis="Z", segs=14, rsegs=4)
        G.xform(wh.obj, rot=(35, 0, 0), pivot=(0.62, -3.5, 1.72 + zl))
        p.tube([(0.62, -3.5, 1.72 + zl), (0.62, -3.68, 1.25 + zl)], 0.03, C.PL_BLACK, segs=6)
    r = p.rng("seats")
    for i in range(11):
        y = -2.6 + i * 0.7
        for sx in (-1, 1):
            if burnt:
                p.box((0.9, 0.4, 0.04), (sx * 0.66, y, 1.32 + zl), C.RUST, bevel=0.0)
                p.box((0.9, 0.04, 0.5), (sx * 0.66, y + 0.2, 1.6 + zl), C.RUST, bevel=0.0)
                continue
            p.box((0.9, 0.4, 0.13), (sx * 0.66, y, 1.37 + zl), seat_m, bevel=0.0)
            p.box((0.9, 0.11, 0.58), (sx * 0.66, y + 0.22, 1.66 + zl), seat_m, bevel=0.0)
            if p.worn and r.random() < 0.3:
                F.stuffing(p, (sx * 0.66 + r.uniform(-0.3, 0.3), y, 1.44 + zl), 0.06, f"st{i}{sx}")
            p.box((0.04, 0.04, 0.35), (sx * 0.24, y - 0.05, 1.12 + zl), C.PAINT_GREY, bevel=0.0)
    # chassis
    for sx in (-1, 1):
        p.box((0.1, 9.8, 0.22), (sx * 0.5, -0.2, 0.62 + zl), C.UNDER, bevel=0.0, wear=0.0)
    p.cyl(0.07, 2.0, (0, yB, axle_z), C.UNDER, axis="X", segs=8)
    p.cyl(0.05, 1.9, (0, yA, axle_z + 0.08), C.UNDER, axis="X", segs=8)
    p.lathe([(0.0, 0.0), (0.18, 0.0), (0.2, 0.05), (0.2, 0.2), (0.0, 0.25)], (0, yB, axle_z - 0.12), C.UNDER, segs=10)
    p.box((0.6, 0.9, 0.45), (0.75, 0.2, 0.68 + zl), blk, bevel=0.03)
    p.tube([(-0.4, -3.8, 0.55 + zl), (-0.45, 3.5, 0.55 + zl), (-0.5, 4.2, 0.5 + zl)], 0.04, C.RUST, segs=6)
    p.collider((0, -0.05, (zr + 0.38) / 2), (2.5, 10.85, zr + 0.4))


def fire_engine_wreck(p: Prop) -> None:
    """1970s rural pumper (8.5 x 3.0 x 2.5) on a cab-over chassis: red cab with a white roof and a red
    light bar, chrome grille and bumper with the siren speaker, a pump panel each side (gauges, colour-keyed
    discharges, the big intake), compartment doors, a hose bed of folded canvas hose, two wooden ground
    ladders on the left, hard suction hoses on the right, tailboard, dual rear wheels on flat tyres. Front
    -Y. Clean: abandoned, a compartment open. Worn: faded and rusted, glass out, a compartment door
    hanging, hose spilling from the bed. Destroyed: burnt-out shell on its rims."""
    burnt = p.destroyed
    red = C.BURNT if burnt else C.ENGINE_RED
    white = C.BURNT if burnt else C.CAR_WHITE
    chrome = C.RUST if burnt else C.CHROME
    blk = C.BURNT if burnt else C.PAINT_BLACK
    yA, yB = -3.0, 1.9
    r_out = 0.5
    axle_z = 0.3 if burnt else 0.44
    zl = axle_z - 0.47
    X = 1.22
    for sx in (-1, 1):
        wheel(p, sx * 1.0, yA, r_out, 0.29, 0.28, burnt=burnt, flat=0.32, segs=10)
        wheel(p, sx * 1.07, yB, r_out, 0.29, 0.25, burnt=burnt, flat=0.32, segs=10)
        if not burnt:
            p.lathe([(0.29, -0.11), (0.47, -0.12), (0.5, -0.06), (0.5, 0.06), (0.47, 0.12), (0.29, 0.11)], (sx * 0.8, yB, axle_z - 0.02),
                    C.TYRE, segs=8, axis="X", cap_bottom=False, cap_top=False)
    # --- cab -----------------------------------------------------------------------------------
    cy0, cy1 = -4.15, -2.45
    zc0, zc1, zc2 = 0.7 + zl, 1.85 + zl, 2.62 + zl
    for sx in (-1, 1):
        x0 = X - 0.03 if sx > 0 else -X
        arch_panel(p, x0, 0.03, cy0, cy1, zc0, zc1, [(yA, 0.6)], axle_z, red, wear=0.9)
    p.box((2 * X, 0.04, zc1 - zc0), (0, cy0, (zc0 + zc1) / 2), red, bevel=0.01)
    p.box((2 * X, 0.04, zc2 - zc0), (0, cy1, (zc0 + zc2) / 2), red, bevel=0.006)
    ws = _win_states(p, 6, "cabwin")
    for sx in (-1, 1):
        for y in (cy0 + 0.04, cy1 - 0.04):
            p.box((0.07, 0.08, zc2 - zc1), (sx * (X - 0.035), y, (zc1 + zc2) / 2), red, bevel=0.008, grain="Z")
        p.box((0.07, 0.07, zc2 - zc1), (sx * (X - 0.035), -3.05, (zc1 + zc2) / 2), red, bevel=0.008, grain="Z")
        _glass(p, 0.95, zc2 - zc1 - 0.1, (sx * (X - 0.03), -3.6, (zc1 + zc2) / 2), ws[0 if sx > 0 else 1], f"dw{sx}")
        _glass(p, 0.5, zc2 - zc1 - 0.1, (sx * (X - 0.03), -2.75, (zc1 + zc2) / 2), ws[2 if sx > 0 else 3], f"qw{sx}")
        _glass(p, 1.08, zc2 - zc1 - 0.06, (sx * 0.56, cy0 - 0.005, (zc1 + zc2) / 2), "gone" if burnt else (ws[4 + (sx > 0)] if p.worn else "ok"),
               f"ws{sx}", axis="Y")
        p.box((0.03, 0.06, 0.28), (sx * (X + 0.02), -3.25, zc1 - 0.25), chrome, bevel=0.005)
        p.tube([(sx * (X + 0.02), -3.98, zc0 + 0.1), (sx * (X + 0.04), -3.98, zc1 - 0.1)], 0.014, chrome, segs=6)
        for k in range(2):
            p.box((0.3, 0.26, 0.035), (sx * (X - 0.12), -3.85, 0.42 + zl + k * 0.3), C.GALV if not burnt else C.BURNT, bevel=0.004)
        p.tube([(sx * X, cy0 + 0.15, zc2 - 0.2), (sx * (X + 0.25), cy0 + 0.05, zc2 - 0.15), (sx * (X + 0.28), cy0 + 0.05, zc1 - 0.1)], 0.012,
               chrome, segs=5, fillet_r=0.06)
        if not burnt:
            p.box((0.05, 0.2, 0.34), (sx * (X + 0.28), cy0 + 0.05, zc1 + 0.15), blk, bevel=0.012)
    p.box((0.08, 0.06, zc2 - zc1), (0, cy0 + 0.0, (zc1 + zc2) / 2), red, bevel=0.008)
    p.box((2 * X, 0.06, 0.08), (0, cy0, zc1 + 0.02), red, bevel=0.01)
    p.rbox((2 * X + 0.02, cy1 - cy0 + 0.04, 0.14), (0, (cy0 + cy1) / 2, zc2 + 0.05), white, radius=0.05, inner=(3, 3, 1))
    p.box((1.7, 0.3, 0.05), (0, -3.85, zc2 + 0.14), chrome, bevel=0.01)
    lb = p.box((1.6, 0.26, 0.13), (0, -3.85, zc2 + 0.23), C.BURNT if burnt else C.LENS_R, bevel=0.02)
    if p.worn and not burnt:
        G.xform(lb.obj, rot=(0, 3, 0), pivot=(-0.8, -3.85, zc2 + 0.17))
    for sx in (-1, 1):
        p.lathe([(0.1, 0.0), (0.1, 0.05), (0.08, 0.15), (0.0, 0.17)], (sx * 0.6, -3.85, zc2 + 0.3), C.BURNT if burnt else C.LENS_R, segs=10)
    # front: grille, lamps, bumper, siren speaker
    p.box((1.1, 0.05, 0.42), (0, cy0 - 0.03, 1.2 + zl), chrome, bevel=0.012)
    for k in range(5):
        p.box((1.02, 0.04, 0.03), (0, cy0 - 0.05, 1.04 + k * 0.08 + zl), blk, bevel=0.0)
    for sx in (-1, 1):
        for k in range(2):
            _lamp(p, (sx * (0.72 + k * 0.22), cy0 - 0.02, 1.3 + zl), 0.08, C.BURNT if burnt else C.LENS_C, bezel=chrome)
        _lamp(p, (sx * 0.83, cy0 - 0.02, 1.08 + zl), 0.06, C.BURNT if burnt else C.LENS_A, bezel=chrome)
        _lamp(p, (sx * 0.55, cy0 - 0.02, zc1 - 0.12), 0.07, C.BURNT if burnt else C.LENS_R, bezel=chrome)
    bmp = p.box((2.5, 0.22, 0.26), (0, -4.3, 0.62 + zl), chrome, bevel=0.03, grain="X")
    if p.worn:
        G.xform(bmp.obj, rot=(0, -3, 0), pivot=(1.25, -4.3, 0.62 + zl))
    p.cyl(0.13, 0.12, (-0.62, -4.45, 0.66 + zl), blk, axis="Y", segs=12)
    p.cyl(0.11, 0.01, (-0.62, -4.515, 0.66 + zl), C.PL_BLACK if not burnt else C.BURNT, axis="Y", segs=12)
    for sx in (-1, 1):
        p.tube([(sx * 0.4, -4.42, 0.55 + zl), (sx * 0.4, -4.5, 0.5 + zl), (sx * 0.4, -4.42, 0.45 + zl)], 0.018, chrome, segs=5, fillet_r=0.03)
    # cab interior
    p.box((2 * X - 0.1, 1.6, 0.04), (0, (cy0 + cy1) / 2, 1.0 + zl), C.PL_BLACK if not burnt else C.BURNT, bevel=0.0, wear=0.0)
    p.box((2 * X - 0.1, 0.4, 0.3), (0, cy0 + 0.25, 1.75 + zl), C.PL_BLACK if not burnt else C.BURNT, bevel=0.01)
    p.box((2 * X - 0.2, 0.45, 0.12), (0, -2.85, 1.42 + zl), C.BURNT if burnt else "car_upholstery", bevel=0.02)
    p.box((2 * X - 0.2, 0.12, 0.6), (0, -2.58, 1.75 + zl), C.BURNT if burnt else "car_upholstery", bevel=0.02)
    if not burnt:
        wh = torus(p, 0.23, 0.016, (0.55, -3.65, 1.75 + zl), C.PL_BLACK, axis="Z", segs=14, rsegs=4)
        G.xform(wh.obj, rot=(-55, 0, 0), pivot=(0.55, -3.65, 1.75 + zl))
    # --- pump panel ------------------------------------------------------------------------------
    py0, py1 = -2.43, -1.73
    p.box((2 * X, py1 - py0, 1.55), (0, (py0 + py1) / 2, 0.7 + zl + 0.775), red, bevel=0.01)
    p.box((2 * X + 0.04, py1 - py0 + 0.04, 0.06), (0, (py0 + py1) / 2, 2.27 + zl), chrome, bevel=0.01)
    for sx in (-1, 1):
        face = sx * (X + 0.01)
        plate(p, 0.62, 0.42, (face, (py0 + py1) / 2, 1.62 + zl), atlas("pump_plate"), t=0.012, mat=C.PRINT if not burnt else C.BURNT,
              facing="+X" if sx > 0 else "-X", wear=0.5)
        for k, cell in enumerate(("gauge", "gauge_black")):
            y = py0 + 0.2 + k * 0.3
            p.cyl(0.085, 0.04, (face + sx * 0.02, y, 1.98 + zl), chrome, axis="X", segs=10)
            if not burnt:
                disc_face(p, 0.075, 0.006, (face + sx * 0.042, y, 1.98 + zl), atlas(cell), axis="X" if sx > 0 else "-X", segs=10)
        for k in range(2):
            y = py0 + 0.2 + k * 0.3
            p.cyl(0.05, 0.12, (face + sx * 0.06, y, 1.05 + zl), chrome, axis="X", segs=10)
            p.lathe([(0.065, 0.0), (0.065, 0.04), (0.055, 0.05), (0.0, 0.05)], (face + sx * 0.12, y, 1.05 + zl), chrome, segs=10,
                    axis="X" if sx > 0 else "-X")
            bar(p, (face + sx * 0.05, y, 1.25 + zl), (face + sx * 0.2, y, 1.25 + zl), 0.025, 0.025, chrome, bevel=0.004)
            bar(p, (face + sx * 0.2, y - 0.07, 1.25 + zl), (face + sx * 0.2, y + 0.07, 1.25 + zl), 0.03, 0.03, C.PL_BLACK if not burnt else C.BURNT,
                bevel=0.006)
        p.cyl(0.11, 0.1, (face + sx * 0.05, (py0 + py1) / 2, 0.85 + zl), chrome, axis="X", segs=12)
        p.lathe([(0.13, 0.0), (0.13, 0.06), (0.11, 0.08), (0.0, 0.08)], (face + sx * 0.1, (py0 + py1) / 2, 0.85 + zl), chrome, segs=12,
                axis="X" if sx > 0 else "-X")
        p.box((0.3, py1 - py0, 0.04), (sx * (X - 0.05), (py0 + py1) / 2, 0.5 + zl), C.GALV if not burnt else C.BURNT, bevel=0.004)
    # --- body: compartments, hose bed ----------------------------------------------------------------
    by0, by1 = -1.73, 3.95
    zb0, zb1, zh = 0.7 + zl, 1.85 + zl, 2.38 + zl
    for sx in (-1, 1):
        x0 = X - 0.03 if sx > 0 else -X
        arch_panel(p, x0, 0.03, by0, by1, zb0, zh, [(yB, 0.62)], axle_z, red, wear=0.9)
        p.box((0.04, by1 - by0, 0.06), (sx * (X + 0.01), (by0 + by1) / 2, zb1 + 0.03), chrome, bevel=0.008, grain="Y")
        doors = [(-1.65, -0.25, zb0 + 0.1, zb1 - 0.05), (-0.2, 1.2, zb0 + 0.1, zb1 - 0.05), (1.35, 2.45, 1.4 + zl, zb1 - 0.05),
                 (2.6, 3.88, zb0 + 0.1, zb1 - 0.05)]
        for k, (d0, d1, dz0, dz1) in enumerate(doors):
            grp = [p.box((0.03, d1 - d0, dz1 - dz0), (sx * (X + 0.015), (d0 + d1) / 2, (dz0 + dz1) / 2), red, bevel=0.003, grain="Z")]
            grp.append(p.box((0.03, 0.12, 0.03), (sx * (X + 0.04), d1 - 0.1, (dz0 + dz1) / 2), chrome, bevel=0.0))
            openk = (not burnt) and ((p.cond == "clean" and sx < 0 and k == 1) or (p.worn and sx > 0 and k == 3))
            if openk:
                p.box((0.02, d1 - d0 - 0.06, dz1 - dz0 - 0.06), (sx * (X - 0.02), (d0 + d1) / 2, (dz0 + dz1) / 2), C.UNDER, bevel=0.0)
                for s in range(2):
                    p.box((0.5, d1 - d0 - 0.1, 0.02), (sx * (X - 0.3), (d0 + d1) / 2, dz0 + 0.3 + s * 0.4), C.GALV, bevel=0.003)
                if p.worn:
                    F.hang(p, grp, sx * (X + 0.015), d0, dz1, 0.0, 0.0)
                    p.rotate(grp, rot=(0, 0, sx * 70), pivot=(sx * (X + 0.015), d0, 0))
                    p.rotate(grp, rot=(sx * 8, 0, 0), pivot=(sx * X, d0, dz1))
                else:
                    p.rotate(grp, rot=(0, 0, -sx * 100), pivot=(sx * (X + 0.015), d1, 0))
    p.box((2 * X, 0.03, zh - zb0), (0, by1, (zb0 + zh) / 2), red, bevel=0.006)
    p.box((2 * X - 0.06, by1 - by0, 0.04), (0, (by0 + by1) / 2, zb1), C.UNDER, bevel=0.0, wear=0.0)
    # folded hose in two lanes
    r = p.rng("hose")
    spill = p.worn and not burnt
    for lane in (-1, 1):
        lx = lane * 0.58
        for k in range(6):
            z = zb1 + 0.04 + k * 0.07
            ya, yb = by0 + 0.1, by1 - 0.1
            if burnt and k > 2:
                continue
            p.box((1.08, yb - ya, 0.05), (lx, (ya + yb) / 2, z), C.BURNT if burnt else C.HOSE, bevel=0.0, grain="Y", wear=0.5)
            if not burnt:
                end = yb if k % 2 == 0 else ya
                p.cyl(0.035, 1.08, (lx, end + (0.02 if k % 2 == 0 else -0.02), z + 0.035), C.HOSE, axis="X", segs=6)
    if spill:
        pts = [(0.58, by1 - 0.1, zb1 + 0.45), (0.6, by1 + 0.15, zb1 + 0.3), (0.65, by1 + 0.35, 0.6), (0.5, by1 + 0.6, 0.04),
               (-0.2, by1 + 0.9, 0.04), (-0.8, by1 + 0.7, 0.04)]
        p.tube(pts, 0.04, C.HOSE, segs=6, fillet_r=0.15, steps=2)
        _coupling(p, (-0.8, by1 + 0.7, 0.045), "-X", r=0.045)
    # ground ladders on the left (+X)
    for li, (lx, ln) in enumerate(((X + 0.07, 4.3), (X + 0.15, 3.6))):
        y0l = -1.6
        rails = [p.box((0.035, ln, 0.07), (lx, y0l + ln / 2, z + zl), C.OAK if not burnt else C.BURNT, bevel=0.0, grain="Y")
                 for z in (1.98, 2.36)]
        del rails
        for k in range(int(ln / 0.3)):
            p.box((0.026, 0.026, 0.31), (lx, y0l + 0.15 + k * 0.3, 2.17 + zl), C.OAK if not burnt else C.BURNT, bevel=0.0, grain="Z")
    for y in (-1.2, 0.8, 2.4):
        p.box((0.22, 0.05, 0.05), (X + 0.1, y, 1.93 + zl), blk, bevel=0.006)
        p.box((0.22, 0.05, 0.05), (X + 0.1, y, 2.42 + zl), blk, bevel=0.006)
    # hard suction hoses on the right (-X)
    for k, z in enumerate((2.02, 2.22)):
        p.cyl(0.07, 3.0, (-X - 0.09, 0.7, z + zl), C.BURNT if burnt else C.RUBBER, axis="Y", segs=10)
        for e in (-0.8, 2.2):
            p.lathe([(0.085, 0.0), (0.085, 0.1), (0.0, 0.1)], (-X - 0.09, e + (0 if e > 0 else 0), z + zl), chrome, segs=10,
                    axis="Y" if e > 0 else "-Y", cap_bottom=False)
    for y in (-0.3, 1.7):
        p.box((0.2, 0.05, 0.45), (-X - 0.09, y, 2.12 + zl), blk, bevel=0.006)
    # rear: tailboard, lamps, beacons, grab rails
    p.box((2 * X + 0.04, 0.32, 0.07), (0, by1 + 0.16, 0.65 + zl), C.GALV if not burnt else C.BURNT, bevel=0.006)
    for sx in (-1, 1):
        _lamp(p, (sx * 0.95, by1 + 0.015, 1.05 + zl), 0.08, C.BURNT if burnt else C.LENS_R, axis="Y", bezel=chrome)
        _lamp(p, (sx * 0.95, by1 + 0.015, 0.85 + zl), 0.06, C.BURNT if burnt else C.LENS_A, axis="Y", bezel=chrome)
        p.lathe([(0.09, 0.0), (0.09, 0.04), (0.07, 0.13), (0.0, 0.15)], (sx * (X - 0.12), by1 - 0.12, zh), C.BURNT if burnt else C.LENS_R,
                segs=10)
        p.tube([(sx * 1.05, by1 + 0.03, 1.2 + zl), (sx * 1.05, by1 + 0.08, 1.25 + zl), (sx * 1.05, by1 + 0.08, 2.0 + zl),
                (sx * 1.05, by1 + 0.03, 2.05 + zl)], 0.016, chrome, segs=6, fillet_r=0.04)
    # chassis
    for sx in (-1, 1):
        p.box((0.1, 8.0, 0.24), (sx * 0.48, -0.1, 0.62 + zl), C.UNDER, bevel=0.0, wear=0.0)
    p.cyl(0.07, 2.0, (0, yB, axle_z), C.UNDER, axis="X", segs=8)
    p.cyl(0.05, 1.9, (0, yA, axle_z + 0.08), C.UNDER, axis="X", segs=8)
    p.lathe([(0.0, 0.0), (0.18, 0.0), (0.2, 0.05), (0.2, 0.2), (0.0, 0.25)], (0, yB, axle_z - 0.12), C.UNDER, segs=10)
    p.box((0.9, 0.7, 0.4), (0.0, (py0 + py1) / 2, 0.55 + zl), C.UNDER, bevel=0.02)
    p.tube([(-0.45, -2.4, 0.5 + zl), (-0.5, 3.0, 0.5 + zl), (-0.6, 3.8, 0.45 + zl)], 0.04, C.RUST, segs=6)
    p.collider((0, -0.05, (zc2 + 0.3) / 2), (2.6, 8.7, zc2 + 0.3))


# ================================================================================================
# registry
# ================================================================================================

BUILDERS = {
    "school_desk": school_desk,
    "school_teacher_desk": school_teacher_desk,
    "school_chalkboard": school_chalkboard,
    "school_locker_bank": school_locker_bank,
    "school_bleachers": school_bleachers,
    "school_basketball_hoop": school_basketball_hoop,
    "school_wall_bars": school_wall_bars,
    "school_gym_mats": school_gym_mats,
    "school_stage_lights": school_stage_lights,
    "school_boiler": school_boiler,
    "school_card_catalog": school_card_catalog,
    "school_flagpole": school_flagpole,
    "school_bus_wreck": school_bus_wreck,
    "fire_engine_wreck": fire_engine_wreck,
    "fire_hose_rack": fire_hose_rack,
    "fire_turnout_locker": fire_turnout_locker,
    "fire_pole": fire_pole,
    "fire_hose_hanging": fire_hose_hanging,
    "fire_siren": fire_siren,
    "fire_extinguisher": fire_extinguisher,
    "bank_vault_door": bank_vault_door,
    "door_vault": door_vault,
    "door_vault_broken": door_vault_broken,
    "bank_teller_counter": bank_teller_counter,
    "bank_deposit_boxes": bank_deposit_boxes,
    "bank_stanchions": bank_stanchions,
    "bank_money_bags": bank_money_bags,
}


def _open_box(self: Prop, size, center, mat, wall=0.018, open_face="-Y", bevel=0.002, back=None, **kw) -> core.Part:
    """Deterministic stand-in for Prop.hollow (G.hollow_box's inset + extrude come out in a run-dependent
    face order, which breaks byte-identical rebuilds): five wall slabs in one mesh, open on open_face."""
    sx, sy, sz = size
    ax = "XYZ".index(open_face[1])
    sign = 1.0 if open_face[0] == "+" else -1.0
    bk = back if back is not None else wall
    bm = bmesh.new()
    slabs = []
    for a in range(3):
        for sd in (-1.0, 1.0):
            if a == ax and sd == sign:
                continue
            t = bk if a == ax else wall
            dims = [sx, sy, sz]
            dims[a] = t
            c = [0.0, 0.0, 0.0]
            c[a] = sd * ([sx, sy, sz][a] / 2 - t / 2)
            slabs.append((dims, c))
    for dims, c in slabs:
        geom = bmesh.ops.create_cube(bm, size=1.0)
        vs = geom["verts"]
        bmesh.ops.scale(bm, vec=Vector(dims), verts=vs)
        bmesh.ops.translate(bm, vec=Vector(c) + Vector(center), verts=vs)
    obj = G._obj(self._name("openbox"), bm)
    return self.add(obj, mat, **kw)


def build(params: dict, outputs: list[str]) -> None:
    fn = BUILDERS[params.get("builder", params["prop"])]
    orig_hollow = Prop.hollow
    Prop.hollow = _open_box
    try:
        _build(params, outputs, fn)
    finally:
        Prop.hollow = orig_hollow


def _build(params: dict, outputs: list[str], fn) -> None:
    if not params.get("no_collision"):
        core.build_variants(params, outputs, fn)
        return
    # Kit pieces (door leaves) carry no collision proxies: the POI builder gives them their own.
    orig = export.export_glb

    def no_cols(path, objs, *a, **kw):
        return orig(path, [o for o in objs if not o.name.endswith("-convcolonly")], *a, **kw)

    export.export_glb = no_cols
    try:
        core.build_variants(params, outputs, fn)
    finally:
        export.export_glb = orig
