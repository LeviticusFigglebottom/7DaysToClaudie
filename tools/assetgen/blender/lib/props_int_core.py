"""Interior-props framework: a `Prop` build context shared by generators/props_interior_*.py.

A builder function `fn(p: Prop)` creates parts with p.box / p.rbox / p.cyl / ... (each part = mesh object
in final coordinates + material id + tags + UV/wear settings). `build_variants()` runs the builder once per
condition ("clean", "worn", "destroyed"), then `Prop.finish()`:
  1. UVs per part: metre-scaled box projection with wood-grain direction (texture U = grain), cylinder,
     planar 0..1 (rugs, boards, mirrors) or caller-provided atlas UVs ("keep").
  2. Vertex colour per part: G = convex-edge wear x noise x condition (+ scuff patches when worn),
     B = per-part variation, A = 1.
  3. Join, weighted (face-area) custom normals so bevels read soft while big faces stay flat.
  4. R = ray-cast AO against the prop + floor / wall / ceiling plane (mount); worn props get grime
     blotches darkened into R (std_surface collects grime where R is low).
  5. Collision boxes (`-convcolonly`), export via lib.export.export_glb().
Randomness: p.rng(key) is identical across variants (shape choices); p.vrng(key) is per variant.
"""
from __future__ import annotations

import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector, noise

from . import common, export, materials, vcolor
from . import props_int_mesh as G


class M:
    """Material ids (game/data/materials/props_interior.json)."""
    OAK = "wood_furniture_oak"
    DARK = "wood_furniture_dark"
    PAINT_CREAM = "wood_painted_cream"
    PAINT_WHITE = "wood_painted_white"
    PAINT_GREEN = "wood_painted_green"
    WOOD_RAW = "furn_wood_raw"
    PARTICLE = "furn_particleboard"
    LAMINATE = "laminate_counter"
    LAMINATE_DINER = "laminate_diner"
    LAM_WOOD = "laminate_woodgrain"
    ENAMEL = "enamel_appliance"
    TUB = "enamel_tub"
    CHROME = "furn_chrome"
    STAINLESS = "furn_steel_stainless"
    BRASS = "furn_brass"
    CAST_IRON = "furn_cast_iron"
    TIN = "furn_tin"
    STEEL_GREY = "metal_shelf_grey"
    STEEL_GREEN = "steel_locker_green"
    STEEL_BEIGE = "steel_cabinet_beige"
    STEEL_BLACK = "steel_safe_black"
    STEEL_WHITE = "steel_painted_white"
    STEEL_RED = "steel_painted_red"
    FLORAL = "upholstery_floral"
    BROWN = "upholstery_brown"
    TAN = "upholstery_tan"
    VINYL_RED = "vinyl_red"
    VINYL_BLACK = "vinyl_black"
    VINYL_TEAL = "vinyl_teal"
    FOAM = "furn_foam"
    MOLD = "furn_mold"
    TICKING = "mattress_ticking"
    QUILT = "bedding_quilt"
    LINEN = "furn_linen"
    TOWEL = "furn_towel"
    SHADE = "furn_shade_fabric"
    RUG = "carpet_rug"
    RUG_BRAIDED = "rug_braided"
    CERAMIC = "ceramic_white"
    MIRROR = "mirror_dirty"
    CARDBOARD = "cardboard_print"
    BOOKS = "book_spines"
    CHALK = "chalkboard"
    CORK = "furn_cork"
    PEGBOARD = "furn_pegboard"
    PAPER = "furn_paper_notes"
    GLASS = "furn_glass"
    GLASS_FROST = "furn_glass_frosted"
    CRT = "furn_crt_screen"
    PL_BEIGE = "furn_plastic_beige"
    PL_BLACK = "furn_plastic_black"
    PL_WHITE = "furn_plastic_white"
    PL_GREY = "furn_plastic_grey"
    PL_RED = "furn_plastic_red"
    PL_BLUE = "furn_plastic_blue"
    PL_BROWN = "furn_plastic_brown"
    RUBBER = "furn_rubber"
    BURLAP = "furn_burlap"


# Material families: how UVs and wear behave by default.
SOFT = {M.FLORAL, M.BROWN, M.TAN, M.VINYL_RED, M.VINYL_BLACK, M.VINYL_TEAL, M.FOAM, M.TICKING, M.QUILT, M.LINEN,
        M.TOWEL, M.SHADE, M.RUG, M.RUG_BRAIDED, M.BURLAP}
PLANAR01 = {M.RUG, M.CHALK, M.MIRROR, M.CRT}

# Faces narrower than this (bevels, thin edges) carry edge wear on box-like parts.
EDGE_STRIP = 0.012

# Atlas cells (texture pixel rects, 1024 px textures unless noted) -> see textures/gen/props_interior.py
CARD_CELL = 256  # cardboard_print: 4x4 cells; 0..13 art, 14 kraft, 15 tin lid


def card_rect(k: int, inset: float = 4.0) -> tuple[float, float, float, float]:
    cy, cx = divmod(k, 4)
    return _px_rect(cx * CARD_CELL + inset, cy * CARD_CELL + inset, (cx + 1) * CARD_CELL - inset, (cy + 1) * CARD_CELL - inset)


def book_rect(k: int, paperback: bool = False) -> tuple[float, float, float, float]:
    col = k % 32
    if paperback:
        row = (k // 32) % 2
        return _px_rect(col * 32 + 1, 512 + row * 128 + 1, col * 32 + 31, 512 + (row + 1) * 128 - 1)
    row = (k // 32) % 2
    return _px_rect(col * 32 + 1, row * 256 + 1, col * 32 + 31, (row + 1) * 256 - 1)


def book_cover_rect(k: int, paperback: bool = False) -> tuple[float, float, float, float]:
    col = k % 32
    row = (k // 32) % 2
    if paperback:
        y0 = 512 + row * 128
        return _px_rect(col * 32 + 2, y0 + 6, col * 32 + 5, y0 + 14)
    y0 = row * 256
    return _px_rect(col * 32 + 2, y0 + 60, col * 32 + 5, y0 + 69)


BOOK_PAGES = None  # set below


def _px_rect(x0, y0, x1, y1, size: float = 1024.0):
    """Image pixel rect (y down) -> Blender UV rect (u0, v0, u1, v1) with v up."""
    return (x0 / size, 1.0 - y1 / size, x1 / size, 1.0 - y0 / size)


BOOK_PAGES = _px_rect(8, 776, 1016, 1016)


def note_rect(k: int) -> tuple[float, float, float, float]:
    cy, cx = divmod(k % 4, 2)
    return _px_rect(cx * 256 + 6, cy * 256 + 6, (cx + 1) * 256 - 6, (cy + 1) * 256 - 6, 512.0)


# ------------------------------------------------------------------------------------------------


class Part:
    __slots__ = ("obj", "mat", "tags", "uv", "uv_scale", "grain", "wear", "var", "edge_deg", "key", "uv_axis", "rect",
                 "ring", "floor_wear")

    def __init__(self, obj, mat, tags, uv, uv_scale, grain, wear, var, edge_deg, key, uv_axis, rect, ring=0.012):
        self.obj = obj
        self.mat = mat
        self.tags = tuple(tags)
        self.uv = uv
        self.uv_scale = uv_scale
        self.grain = grain
        self.wear = wear
        self.var = var
        self.edge_deg = edge_deg
        self.ring = ring
        self.floor_wear = 0.0
        self.key = key
        self.uv_axis = uv_axis
        self.rect = rect


class Prop:
    def __init__(self, params: dict, cond: str):
        self.params = params
        self.name = params["prop"]
        self.cond = cond
        self.seed = int(params.get("seed", 1))
        self.mount = params.get("mount", "floor")
        self.parts: list[Part] = []
        self.colliders: list[tuple[Vector, Vector, tuple]] = []
        self._n = 0

    # --- condition & randomness ---------------------------------------------------------------
    @property
    def worn(self) -> bool:
        return self.cond != "clean"

    @property
    def destroyed(self) -> bool:
        return self.cond == "destroyed"

    def rng(self, key: str) -> random.Random:
        return random.Random(f"{self.name}:{self.seed}:{key}")

    def vrng(self, key: str) -> random.Random:
        return random.Random(f"{self.name}:{self.seed}:{self.cond}:{key}")

    def chance(self, key: str, prob: float) -> bool:
        return self.vrng(key).random() < prob

    # --- parts ---------------------------------------------------------------------------------
    def _name(self, base: str) -> str:
        self._n += 1
        return f"{base}_{self._n:03d}"

    def add(self, obj, mat: str, *, tags=(), uv: str = "box", uv_scale: float = 1.0, grain: str | int = "auto",
            wear: float = 1.0, var: float | None = None, edge_deg: float = 8.0, uv_axis: str = "Y", rect=None,
            ring: float | None = None) -> Part:
        """edge_deg < 30 marks box-like parts (wear on narrow bevel strips, per corner); larger values mark
        smooth parts (wear from vertex curvature above edge_deg). ring: unused (kept for call compatibility)."""
        slot = materials.assign(obj, mat)
        for poly in obj.data.polygons:
            if poly.material_index >= len(obj.data.materials) or obj.data.materials[poly.material_index] is None:
                poly.material_index = slot
        if len(obj.data.materials) == 1:
            for poly in obj.data.polygons:
                poly.material_index = slot
        key = obj.name
        if var is None:
            var = random.Random(f"{self.name}:{self.seed}:var:{key}").random()
        if mat in SOFT and wear == 1.0:
            wear = 0.6  # fabrics: edges rub dirty / threadbare, not chipped
        ring = 0.0  # wear rings retired: long sliver strips rasterise as visible lines (see _part_colors)
        part = Part(obj, mat, tags, uv, uv_scale, grain, wear, var, edge_deg, key, uv_axis, rect, ring)
        self.parts.append(part)
        return part

    def remove(self, parts) -> None:
        for part in (parts if isinstance(parts, (list, tuple)) else [parts]):
            if part in self.parts:
                self.parts.remove(part)
                bpy.data.objects.remove(part.obj, do_unlink=True)
        bpy.context.view_layer.update()

    def tagged(self, tag: str) -> list[Part]:
        return [q for q in self.parts if tag in q.tags]

    def set_mat(self, part: Part, mat: str, face_filter=None) -> None:
        """Assigns `mat` to faces of `part` passing face_filter(poly) (all faces if None)."""
        slot = materials.assign(part.obj, mat)
        for poly in part.obj.data.polygons:
            if face_filter is None or face_filter(poly):
                poly.material_index = slot

    # convenience builders ------------------------------------------------------------------------
    def box(self, size, center, mat, bevel: float = 0.003, segs: int = 1, **kw) -> Part:
        return self.add(G.box(self._name("box"), size, center, bevel, segs), mat, **kw)

    def rbox(self, size, center, mat, radius: float = 0.03, inner=(2, 2, 1), rs: int = 1, **kw) -> Part:
        shape = {k: kw.pop(k) for k in list(kw) if k in ("bulge", "sag", "sag_at", "sag_r", "wrinkle", "wrinkle_scale",
                                                            "seed", "taper_top", "squash")}
        kw.setdefault("edge_deg", 35.0)
        return self.add(G.rbox(self._name("rbox"), size, center, radius, inner, rs, **shape), mat, **kw)

    def cyl(self, r, h, center, mat, axis: str = "Z", segs: int = 12, r_top=None, bevel: float = 0.0, cap: bool = True,
            **kw) -> Part:
        kw.setdefault("edge_deg", 40.0)
        if "uv" not in kw:
            kw["uv"] = "cyl"
            kw.setdefault("uv_axis", axis.strip("-+"))
        return self.add(G.cyl(self._name("cyl"), r, h, center, axis, segs, r_top, bevel, 1, cap), mat, **kw)

    def lathe(self, profile, center, mat, segs: int = 16, axis: str = "Z", cap_bottom=True, cap_top=True, **kw) -> Part:
        kw.setdefault("edge_deg", 40.0)
        if "uv" not in kw:
            kw["uv"] = "cyl"
            kw.setdefault("uv_axis", axis.strip("-+"))
        return self.add(G.lathe(self._name("lathe"), profile, segs, center, axis, cap_bottom, cap_top), mat, **kw)

    def tube(self, pts, radius, mat, segs: int = 8, fillet_r: float = 0.0, steps: int = 3, cap=True, closed=False,
             **kw) -> Part:
        kw.setdefault("edge_deg", 50.0)
        path = G.fillet(pts, fillet_r, steps) if fillet_r > 0 else pts
        return self.add(G.tube(self._name("tube"), path, radius, segs, cap, closed), mat, **kw)

    def prism(self, poly, depth, mat, plane="XZ", offset=0.0, bevel=0.0, inner_mat=None, inner_edges=(), **kw) -> Part:
        obj = G.prism(self._name("prism"), poly, depth, plane, offset, bevel)
        part = self.add(obj, mat, **kw)
        if inner_mat and inner_edges:
            ids = set(inner_edges)
            attr = obj.data.attributes.get("edge_id")
            if attr is not None:
                vals = [0] * len(obj.data.polygons)
                attr.data.foreach_get("value", vals)
                slot = materials.assign(obj, inner_mat)
                for poly in obj.data.polygons:
                    if vals[poly.index] in ids:
                        poly.material_index = slot
        return part

    def hollow(self, size, center, mat, wall=0.018, open_face="-Y", bevel=0.002, back=None, **kw) -> Part:
        return self.add(G.hollow_box(self._name("hollow"), size, center, wall, open_face, bevel, back), mat, **kw)

    def panel(self, w, h, t, center, mat, style="shaker", frame=0.06, recess=0.006, bevel=0.003, facing="-Y", **kw) -> Part:
        kw.setdefault("grain", "auto")
        return self.add(G.panel(self._name("panel"), w, h, t, center, style, frame, recess, bevel, facing), mat, **kw)

    # hardware ----------------------------------------------------------------------------------
    def knob(self, center, mat=M.BRASS, r: float = 0.015, depth: float = 0.026, facing: str = "-Y", tags=("knob",),
             segs: int = 8) -> Part:
        prof = [(0.0055, 0.0), (0.0055, depth * 0.4), (r, depth * 0.75), (r * 0.78, depth), (0.0, depth + 0.001)]
        return self.lathe(prof, center, mat, segs=segs, axis=facing, cap_bottom=True, tags=tags, wear=1.6)

    def bar_pull(self, center, length: float = 0.128, mat=M.CHROME, r: float = 0.0055, standoff: float = 0.028,
                 axis: str = "X", facing: str = "-Y", tags=("knob",)) -> Part:
        c = Vector(center)
        d = Vector((1, 0, 0)) if axis == "X" else Vector((0, 0, 1))
        out = Vector((0, -1, 0)) if facing == "-Y" else (Vector((0, 1, 0)) if facing == "+Y" else Vector((-1, 0, 0)) if facing == "-X" else Vector((1, 0, 0)))
        pts = [c - d * length / 2, c - d * length / 2 + out * standoff, c + d * length / 2 + out * standoff, c + d * length / 2]
        return self.tube(pts, r, mat, segs=8, fillet_r=0.012, steps=2, tags=tags, wear=1.5)

    def cup_pull(self, center, w: float = 0.08, mat=M.BRASS, facing="-Y", tags=("knob",)) -> Part:
        """Half-moon bin pull (shell) for drawers."""
        c = Vector(center)
        poly = [(-w / 2, 0.0)] + [(-w / 2 * math.cos(a), -0.028 * math.sin(a)) for a in [i * math.pi / 8 for i in range(1, 8)]] + [(w / 2, 0.0), (w / 2 - 0.006, 0.006), (-w / 2 + 0.006, 0.006)]
        part = self.prism([(x, z) for x, z in poly], 0.02, mat, plane="XZ", offset=-0.02, bevel=0.0015, tags=tags, wear=1.5)
        G.xform(part.obj, loc=(c.x, c.y, c.z))
        return part

    # groups / variant helpers ------------------------------------------------------------------
    def move(self, parts, offset) -> None:
        for q in parts:
            G.xform(q.obj, loc=offset)

    def rotate(self, parts, rot=(0, 0, 0), pivot=(0, 0, 0), matrix=None) -> None:
        for q in parts:
            G.xform(q.obj, rot=rot, pivot=pivot, matrix=matrix)

    def bounds(self, parts=None) -> tuple[Vector, Vector]:
        return G.bounds([q.obj for q in (parts if parts is not None else self.parts)])

    def lay_on_floor(self, parts, rot=(0, 0, 0), at=(0.0, 0.0), yaw: float = 0.0, z: float = 0.0) -> None:
        """Rotates a group (about its own centre), then places it so it rests at height z centred on `at`."""
        lo, hi = self.bounds(parts)
        c = (lo + hi) * 0.5
        self.rotate(parts, rot=rot, pivot=c)
        if yaw:
            self.rotate(parts, rot=(0, 0, yaw), pivot=c)
        lo, hi = self.bounds(parts)
        c = (lo + hi) * 0.5
        self.move(parts, (at[0] - c.x, at[1] - c.y, z - lo.z))

    def settle(self, parts, pivot, axis, max_deg: float = 85.0, exclude_r: float = 0.05, floor: float = 0.0) -> float:
        """Rotates `parts` about the line (pivot, axis) until some vertex (farther than exclude_r from the
        axis) touches z=floor. Returns the angle used (degrees)."""
        pv = Vector(pivot)
        ax = Vector(axis).normalized()
        pts = []
        for q in parts:
            for v in q.obj.data.vertices:
                rel = v.co - pv
                radial = rel - ax * rel.dot(ax)
                if radial.length > exclude_r:
                    pts.append(v.co.copy())
        if not pts:
            return 0.0

        def lowest(deg):
            m = Matrix.Translation(pv) @ Matrix.Rotation(math.radians(deg), 4, ax) @ Matrix.Translation(-pv)
            return min((m @ p).z for p in pts)

        lo_deg, hi_deg = 0.0, max_deg
        if lowest(hi_deg) > floor:
            ang = hi_deg
        else:
            for _ in range(30):
                mid = (lo_deg + hi_deg) * 0.5
                if lowest(mid) > floor:
                    lo_deg = mid
                else:
                    hi_deg = mid
            ang = lo_deg
        m = Matrix.Translation(pv) @ Matrix.Rotation(math.radians(ang), 4, ax) @ Matrix.Translation(-pv)
        for q in parts:
            G.xform(q.obj, matrix=m)
        return ang

    def collider(self, center, size, rot=(0, 0, 0)) -> None:
        self.colliders.append((Vector(center), Vector(size), tuple(rot)))

    # --- finishing -------------------------------------------------------------------------------
    def finish(self, out_path: str) -> dict:
        parts = [q for q in self.parts if q.obj is not None and len(q.obj.data.polygons) > 0]
        cond_scale = {"clean": 0.22, "worn": 1.25, "destroyed": 1.45}[self.cond]
        patch_amt = {"clean": 0.0, "worn": 0.5, "destroyed": 0.7}[self.cond]
        for q in parts:
            _apply_uv(q, self)
            _part_colors(q, cond_scale, patch_amt, self.seed)
        main = common.join([q.obj for q in parts], self.name)
        main.data.name = self.name
        _normals(main)
        _bake_ao(main, self.mount)
        if self.worn:
            _grime(main, self.seed, 0.45 if self.cond == "worn" else 0.6)
        out = [main]
        if not self.colliders:
            lo, hi = G.bounds([main])
            self.collider((lo + hi) * 0.5, hi - lo)
        for i, (c, s, rot) in enumerate(self.colliders):
            col = G.box(f"{self.name}_col{i}-convcolonly", tuple(max(0.01, x) for x in s), (0, 0, 0))
            G.xform(col, rot=rot, loc=c)
            col.data.materials.clear()
            out.append(col)
        export.export_glb(out_path, out)
        lo, hi = G.bounds([main])
        tris = sum(len(p.vertices) - 2 for p in main.data.polygons)
        info = {"tris": tris, "size": [round(hi.x - lo.x, 3), round(hi.y - lo.y, 3), round(hi.z - lo.z, 3)]}
        budget = int(self.params.get("budget", 3000))
        flag = "  OVER BUDGET" if tris > budget else ""
        print(f"[props_int] {self.name} {self.cond}: tris={tris}/{budget} size={info['size']}{flag}")
        return info


# ------------------------------------------------------------------------------------------------
# UVs
# ------------------------------------------------------------------------------------------------


def _uv_layer(me):
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    return me.uv_layers.active


def _grain_axis(part: Part) -> int | None:
    g = part.grain
    if g in ("X", "Y", "Z"):
        return "XYZ".index(g)
    if g == "auto":
        lo, hi = G.bounds([part.obj])
        d = hi - lo
        return max(range(3), key=lambda a: d[a])
    return None


def _apply_uv(part: Part, prop: Prop) -> None:
    mode = part.uv
    if mode == "keep":
        return
    obj = part.obj
    me = obj.data
    uvl = _uv_layer(me)
    r = random.Random(f"{prop.name}:{prop.seed}:uv:{part.key}")
    off = (r.random(), r.random())
    s = part.uv_scale
    if mode in ("planar", "planar01"):
        rect = part.rect or (0.0, 0.0, 1.0, 1.0)
        ax = "XYZ".index(part.uv_axis)
        oi = [i for i in range(3) if i != ax]
        lo, hi = G.bounds([obj])
        for li, loop in enumerate(me.loops):
            co = me.vertices[loop.vertex_index].co
            u = (co[oi[0]] - lo[oi[0]]) / max(1e-6, hi[oi[0]] - lo[oi[0]])
            v = (co[oi[1]] - lo[oi[1]]) / max(1e-6, hi[oi[1]] - lo[oi[1]])
            if ax == 1:  # XZ plane seen from -Y: u = x, v = z
                pass
            uvl.data[li].uv = (rect[0] + u * (rect[2] - rect[0]), rect[1] + v * (rect[3] - rect[1]))
        return
    if mode == "cyl":
        ax = "XYZ".index(part.uv_axis)
        oi = [i for i in range(3) if i != ax]
        lo, hi = G.bounds([obj])
        cen = (lo + hi) * 0.5
        for poly in me.polygons:
            n = poly.normal
            if abs(n[ax]) > 0.85:  # caps: planar
                for li in poly.loop_indices:
                    co = me.vertices[me.loops[li].vertex_index].co
                    uvl.data[li].uv = ((co[oi[0]] - cen[oi[0]]) * s + off[0], (co[oi[1]] - cen[oi[1]]) * s + off[1])
                continue
            angs = []
            for li in poly.loop_indices:
                co = me.vertices[me.loops[li].vertex_index].co
                angs.append(math.atan2(co[oi[1]] - cen[oi[1]], co[oi[0]] - cen[oi[0]]))
            ref = angs[0]
            for k, li in enumerate(poly.loop_indices):
                a = angs[k]
                if a - ref > math.pi:
                    a -= 2 * math.pi
                elif a - ref < -math.pi:
                    a += 2 * math.pi
                co = me.vertices[me.loops[li].vertex_index].co
                rad = math.hypot(co[oi[0]] - cen[oi[0]], co[oi[1]] - cen[oi[1]])
                rad = max(rad, 0.02)
                # grain along the axis: U runs along the axis (texture grain = U)
                uvl.data[li].uv = (co[ax] * s + off[0], a * max(rad, 0.03) * s + off[1])
        return
    # box projection; texture U follows the grain axis
    gax = _grain_axis(part)
    for poly in me.polygons:
        n = poly.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if ax == 0:
                u, v = (co.y if n.x > 0 else -co.y), co.z
                uax, vax = 1, 2
            elif ax == 1:
                u, v = (-co.x if n.y > 0 else co.x), co.z
                uax, vax = 0, 2
            else:
                u, v = co.x, (co.y if n.z > 0 else -co.y)
                uax, vax = 0, 1
            if gax is not None and gax == vax:
                u, v = v, u
            uvl.data[li].uv = (u * s + off[0], v * s + off[1])


def set_face_uvs(obj, rect_for_face) -> None:
    """Atlas UVs: rect_for_face(poly) -> (u0, v0, u1, v1, axis_u, axis_v, flip_u) maps each face's
    bounding square in the given axes into the rect."""
    me = obj.data
    uvl = _uv_layer(me)
    for poly in me.polygons:
        spec = rect_for_face(poly)
        if spec is None:
            continue
        u0, v0, u1, v1, au, av, flip = spec
        cos = [me.vertices[me.loops[li].vertex_index].co for li in poly.loop_indices]
        ua = [c[au] for c in cos]
        va = [c[av] for c in cos]
        lu, hu, lv, hv = min(ua), max(ua), min(va), max(va)
        for k, li in enumerate(poly.loop_indices):
            tu = (ua[k] - lu) / max(1e-6, hu - lu)
            tv = (va[k] - lv) / max(1e-6, hv - lv)
            if flip:
                tu = 1 - tu
            uvl.data[li].uv = (u0 + tu * (u1 - u0), v0 + tv * (v1 - v0))


# ------------------------------------------------------------------------------------------------
# vertex colours
# ------------------------------------------------------------------------------------------------


def _part_colors(part: Part, cond_scale: float, patch_amt: float, seed: int) -> None:
    """Writes G (wear), B (variation), A (1) per corner.
    Box-like parts (edge_deg < 30): wear only on narrow faces (bevel / edge strips < EDGE_STRIP wide),
      written per corner so it never bleeds into the big faces next to them.
    Smooth parts (rbox, lathe, tubes): per-vertex convex curvature (their faces are all small).
    Both are broken up with 3D noise; worn variants add scuffed stretches; floor_wear adds rust/scuffs
    creeping up from the floor."""
    obj = part.obj
    me = obj.data
    layer = vcolor.ensure_layer(obj, fill=(1.0, 0.0, part.var, 1.0))
    noise.seed_set(int(seed) % 99991 + 7)
    off = Vector((part.var * 17.0, part.var * 5.0, 3.0))

    def edge_value(co):
        nv = noise.noise(co * 7.0 + off) * 0.5 + 0.5
        g = (0.1 + 1.1 * common.smoothstep(0.38, 0.78, nv)) * cond_scale * part.wear
        if patch_amt > 0:  # scuffed stretches
            pv = noise.noise(co * 2.3 + off * 1.7) * 0.5 + 0.5
            g += common.smoothstep(0.5, 0.8, pv) * patch_amt * min(1.2, part.wear)
        return g

    def floor_value(co):
        if part.floor_wear <= 0.0:
            return 0.0
        fz = noise.noise(co * 4.0 + off * 0.3) * 0.5 + 0.5
        return part.floor_wear * common.smoothstep(0.28, 0.0, co.z - fz * 0.12) * cond_scale

    cols = [0.0] * (len(layer.data) * 4)
    layer.data.foreach_get("color", cols)
    verts = me.vertices
    if part.edge_deg < 30.0:
        for poly in me.polygons:
            vs = [verts[i].co for i in poly.vertices]
            perim = sum((vs[i] - vs[i - 1]).length for i in range(len(vs)))
            width = poly.area / max(1e-9, perim * 0.5)  # ~inradius; ~ half the strip width for long strips
            narrow = width < EDGE_STRIP * 0.5
            for li in poly.loop_indices:
                co = verts[me.loops[li].vertex_index].co
                g = edge_value(co) if narrow else 0.0
                cols[li * 4 + 1] = max(0.0, min(1.0, g + floor_value(co)))
                cols[li * 4 + 2] = part.var
                cols[li * 4 + 3] = 1.0
    else:
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.verts.ensure_lookup_table()
        bm.normal_update()
        acc = [0.0] * len(bm.verts)
        lim = math.radians(part.edge_deg)
        for e in bm.edges:
            lf = e.link_faces
            if len(lf) == 1:
                for v in e.verts:
                    acc[v.index] += math.radians(60)
                continue
            if len(lf) != 2:
                continue
            ang = lf[0].normal.angle(lf[1].normal, 0.0)
            if ang < lim:
                continue
            if (lf[1].calc_center_median() - lf[0].calc_center_median()).dot(lf[0].normal) < -1e-7:
                for v in e.verts:
                    acc[v.index] += ang
        wear = []
        for v in bm.verts:
            curv = min(1.0, acc[v.index] / math.radians(75))
            wear.append(max(0.0, min(1.0, curv * edge_value(v.co) + floor_value(v.co))))
        bm.free()
        for li, loop in enumerate(me.loops):
            cols[li * 4 + 1] = wear[loop.vertex_index]
            cols[li * 4 + 2] = part.var
            cols[li * 4 + 3] = 1.0
    layer.data.foreach_set("color", cols)


def _plane(name, co, size, normal_axis):
    bm = bmesh.new()
    s = size / 2
    if normal_axis == "Y":
        pts = [(-s, 0, -s), (s, 0, -s), (s, 0, s), (-s, 0, s)]
    else:
        pts = [(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)]
    vs = [bm.verts.new(Vector(p) + Vector(co)) for p in pts]
    bm.faces.new(vs)
    return common.mesh_from_bmesh(name, bm)


def _bake_ao(obj, mount: str) -> None:
    extra = []
    if mount == "wall":
        extra.append(_plane("_ao_wall", (0, 0.002, 0), 12.0, "Y"))
    if mount == "ceiling":
        extra.append(_plane("_ao_ceiling", (0, 0, 0.002), 12.0, "Z"))
    lo, hi = G.bounds([obj])
    dist = max(0.25, min(0.9, max(hi - lo) * 0.45))
    vcolor.bake_ao([obj], samples=20, distance=dist, strength=0.95, ground=(mount in ("floor", "surface")),
                   extra_occluders=extra)
    # keep deep cavities (fridge / cabinet interiors) readable: AO floor of 0.22
    layer = obj.data.color_attributes.get(vcolor.ATTR)
    cols = [0.0] * (len(layer.data) * 4)
    layer.data.foreach_get("color", cols)
    for i in range(0, len(cols), 4):
        cols[i] = 0.22 + 0.78 * cols[i]
    layer.data.foreach_set("color", cols)
    for e in extra:
        bpy.data.objects.remove(e, do_unlink=True)
    bpy.context.view_layer.update()


def _grime(obj, seed: int, amount: float) -> None:
    noise.seed_set(int(seed) % 9973 + 3)
    off = Vector((seed * 0.13 % 7, 2.2, 5.1))

    def fn(co):
        g = noise.noise(co * 1.7 + off) * 0.5 + 0.5
        low = max(0.0, 1.0 - co.z / 0.35) * 0.35
        return common.smoothstep(0.52, 0.85, g) * amount + low * amount

    me = obj.data
    layer = me.color_attributes.get(vcolor.ATTR)
    cols = [0.0] * (len(layer.data) * 4)
    layer.data.foreach_get("color", cols)
    for li, loop in enumerate(me.loops):
        co = me.vertices[loop.vertex_index].co
        cols[li * 4] *= 1.0 - min(0.6, fn(co))
    layer.data.foreach_set("color", cols)


def _normals(obj) -> None:
    common.shade_smooth(obj, angle_deg=60.0)
    mod = obj.modifiers.new("wn", "WEIGHTED_NORMAL")
    mod.mode = "FACE_AREA"
    mod.keep_sharp = True
    mod.weight = 50
    common.apply_modifiers(obj)
    obj.data.name = obj.name


# ------------------------------------------------------------------------------------------------
# entry point used by generator modules
# ------------------------------------------------------------------------------------------------


def build_variants(params: dict, outputs: list[str], fn) -> list[dict]:
    conds = params.get("variants", ["clean", "worn"])
    if len(conds) != len(outputs):
        raise ValueError(f"{params.get('prop')}: {len(conds)} variants but {len(outputs)} outputs")
    infos = []
    for cond, out in zip(conds, outputs):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        p = Prop(params, cond)
        fn(p)
        infos.append(p.finish(out))
    return infos
