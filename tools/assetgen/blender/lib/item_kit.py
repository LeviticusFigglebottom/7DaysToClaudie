"""Geometry + publishing kit for the item / viewmodel / player-structure families.

Everything here is deterministic (seeded RNGs, no unordered iteration) and context-free (no edit-mode
operators). Generators build parts with the MeshBuilder (`MB`) or the object helpers below, then call
`publish()` which joins, shades, bakes vertex colours (lib.vcolor) and exports through lib.export.

Frames (see docs/ASSET_PIPELINE.md#models):
  * Ground items: origin bottom centre, resting pose found by `settle()` (minimum centre-of-mass height).
  * Tool viewmodels ("canonical" frame the tools are modelled in): grip point at the origin, handle
    along +Z with the business end at +Z, blade edge / striking face toward -Y.
  * Pointing viewmodels (lighter, torch, flashlight, revolver): grip at the origin, beam/barrel/flame
    axis along -Y, top of the object +Z.
  * Viewmodels carry empties ("socket_*"); their local +Y (Blender) is aimed along the action axis so
    the node's Godot -Z (forward) points along the beam / barrel / blade.

Materials are all "item_*" ids defined in game/data/materials/items.json.
"""
from __future__ import annotations

import math

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector, geometry, noise

from . import common, export, materials, vcolor

# Linear preview colours for Blender-side previews / glTF fallback (Godot swaps in the real .tres).
PREVIEW: dict[str, tuple[float, float, float]] = {
    "item_bark": (0.09, 0.065, 0.05), "item_bark_twig": (0.09, 0.07, 0.055), "item_lead": (0.25, 0.25, 0.26), "item_wood_end": (0.55, 0.42, 0.26), "item_wood_raw": (0.62, 0.48, 0.31),
    "item_wood_inner": (0.62, 0.48, 0.31), "item_wood_handle": (0.48, 0.30, 0.14), "item_wood_plank": (0.38, 0.30, 0.22),
    "item_wood_grey": (0.30, 0.27, 0.24), "item_wood_charred": (0.03, 0.03, 0.03), "item_ash": (0.35, 0.34, 0.32),
    "item_wood_grip": (0.20, 0.09, 0.04), "item_plywood": (0.55, 0.42, 0.28), "item_plywood_edge": (0.50, 0.40, 0.28),
    "item_cordage": (0.36, 0.28, 0.15), "item_rope": (0.45, 0.37, 0.22), "item_knapped_stone": (0.12, 0.11, 0.10),
    "item_stone_cortex": (0.55, 0.50, 0.42), "item_stone": (0.30, 0.29, 0.27), "item_stone_fire": (0.22, 0.21, 0.20),
    "item_steel_tool": (0.55, 0.55, 0.56), "item_steel_bright": (0.75, 0.75, 0.76), "item_steel_blued": (0.08, 0.09, 0.11),
    "item_steel_dark": (0.12, 0.12, 0.12), "item_galvanized": (0.50, 0.52, 0.53), "item_rust": (0.25, 0.10, 0.04),
    "item_iron_strap": (0.10, 0.08, 0.07), "item_aluminium": (0.70, 0.71, 0.72), "item_alu_anodized": (0.07, 0.07, 0.08),
    "item_chrome": (0.85, 0.85, 0.86), "item_brass": (0.65, 0.45, 0.15), "item_copper": (0.55, 0.25, 0.12),
    "item_paint_olive": (0.13, 0.14, 0.07), "item_paint_grey": (0.25, 0.26, 0.26), "item_paint_red": (0.35, 0.04, 0.03),
    "item_paint_black": (0.03, 0.03, 0.03), "item_paint_green": (0.06, 0.20, 0.08), "item_paint_white": (0.75, 0.74, 0.70),
    "item_paint_stripe": (0.75, 0.68, 0.45), "item_stencil_band": (0.13, 0.14, 0.07), "item_plastic_red": (0.45, 0.03, 0.02),
    "item_plastic_black": (0.02, 0.02, 0.02), "item_plastic_olive": (0.10, 0.11, 0.06), "item_plastic_white": (0.75, 0.75, 0.72),
    "item_plastic_amber": (0.40, 0.15, 0.02), "item_plastic_blue": (0.03, 0.10, 0.40), "item_plastic_clear": (0.55, 0.62, 0.66),
    "item_bottle_water": (0.35, 0.50, 0.60), "item_bottle_dirty": (0.25, 0.27, 0.15), "item_rubber": (0.03, 0.03, 0.03),
    "item_rubber_olive": (0.07, 0.08, 0.05), "item_glass_brown": (0.12, 0.05, 0.01), "item_glass_green": (0.05, 0.18, 0.06),
    "item_glass_clear": (0.55, 0.60, 0.60), "item_glass_lens": (0.40, 0.45, 0.48), "item_canvas_olive": (0.15, 0.15, 0.08),
    "item_canvas_tan": (0.40, 0.33, 0.22), "item_canvas_grey": (0.25, 0.25, 0.23), "item_salvage_roll": (0.15, 0.15, 0.08),
    "item_webbing": (0.10, 0.11, 0.06), "item_leather": (0.25, 0.13, 0.06), "item_cloth_rag": (0.35, 0.08, 0.06),
    "item_cloth_bandage": (0.70, 0.66, 0.58), "item_cloth_torch": (0.15, 0.12, 0.09), "item_cloth_poultice": (0.45, 0.45, 0.32),
    "item_parachute": (0.20, 0.20, 0.12), "item_paper": (0.80, 0.77, 0.68), "item_paper_edge": (0.78, 0.75, 0.68),
    "item_paper_note": (0.80, 0.78, 0.70), "item_paper_ledger": (0.80, 0.78, 0.70), "item_paper_tag": (0.70, 0.58, 0.38),
    "item_schematic_a": (0.78, 0.74, 0.62), "item_schematic_b": (0.78, 0.74, 0.62), "item_schematic_c": (0.78, 0.74, 0.62),
    "item_magazine_a": (0.30, 0.35, 0.20), "item_magazine_b": (0.55, 0.12, 0.10), "item_magazine_back": (0.60, 0.55, 0.45),
    "item_manual_cover": (0.13, 0.14, 0.07), "item_bookcloth": (0.08, 0.15, 0.08), "item_cardboard": (0.38, 0.26, 0.14),
    "item_box_print": (0.45, 0.30, 0.15), "item_ammo_box": (0.45, 0.30, 0.15), "item_can_tin": (0.65, 0.65, 0.66),
    "item_can_label_a": (0.6, 0.2, 0.1), "item_can_label_b": (0.15, 0.25, 0.10), "item_can_label_c": (0.6, 0.5, 0.1),
    "item_can_label_d": (0.6, 0.05, 0.05), "item_foil_ration": (0.12, 0.13, 0.07), "item_foil_blister": (0.6, 0.6, 0.62),
    "item_pill": (0.85, 0.85, 0.82), "item_duct_tape": (0.45, 0.46, 0.47), "item_bone": (0.70, 0.65, 0.52),
    "item_berry": (0.08, 0.04, 0.12), "item_leaf": (0.08, 0.15, 0.04), "item_mushroom_top": (0.45, 0.25, 0.10),
    "item_mushroom_pore": (0.70, 0.62, 0.45), "item_mushroom_cooked": (0.25, 0.12, 0.05), "item_mycelium": (0.75, 0.72, 0.70),
    "item_stew": (0.20, 0.09, 0.04), "item_fir_bough": (0.05, 0.12, 0.05), "item_herb": (0.12, 0.22, 0.06),
    "item_plant_fiber": (0.45, 0.40, 0.25), "item_scrip": (0.30, 0.32, 0.22), "item_screen": (0.02, 0.03, 0.03),
    "item_clay": (0.35, 0.22, 0.12), "item_charcoal": (0.03, 0.03, 0.03), "item_ghost": (0.45, 0.55, 0.60),
    "item_rx_label": (0.80, 0.80, 0.78), "item_flower": (0.85, 0.84, 0.78), "item_stem_green": (0.09, 0.16, 0.04),
}

METALS = ("item_steel", "item_galvanized", "item_aluminium", "item_chrome", "item_brass", "item_copper", "item_can_tin")


def material_slot(obj: bpy.types.Object, mat_id: str) -> int:
    idx = materials.assign(obj, mat_id)
    m = obj.data.materials[idx]
    col = PREVIEW.get(mat_id)
    if col is not None and tuple(round(c, 4) for c in m.diffuse_color[:3]) != tuple(round(c, 4) for c in col):
        m.diffuse_color = (*col, 1.0)
        if m.node_tree is not None:
            for n in m.node_tree.nodes:
                if n.bl_idname == "ShaderNodeMix":
                    n.inputs[6].default_value = (*col, 1.0)
                if n.bl_idname == "ShaderNodeBsdfPrincipled" and mat_id.startswith(METALS):
                    n.inputs["Metallic"].default_value = 1.0
                    n.inputs["Roughness"].default_value = 0.4
    return idx


def mat_all(obj: bpy.types.Object, mat_id: str) -> bpy.types.Object:
    idx = material_slot(obj, mat_id)
    for p in obj.data.polygons:
        p.material_index = idx
    return obj


# ------------------------------------------------------------------------------------------------
# Mesh builder
# ------------------------------------------------------------------------------------------------

class MB:
    """Collects vertices / faces / per-corner UVs / per-face material ids, then builds one object.
    A transform stack (push/pop) applies to every vertex added while active."""

    def __init__(self) -> None:
        self.co: list[Vector] = []
        self.faces: list[tuple[int, ...]] = []
        self.fuv: list[list[tuple[float, float]]] = []
        self.fmat: list[str] = []
        self.fsmooth: list[bool] = []
        self._xf: list[Matrix] = [Matrix.Identity(4)]

    # transform stack ------------------------------------------------------------------------
    def push(self, m: Matrix) -> None:
        self._xf.append(self._xf[-1] @ m)

    def pop(self) -> None:
        self._xf.pop()

    def vert(self, co) -> int:
        self.co.append(self._xf[-1] @ Vector(co))
        return len(self.co) - 1

    def face(self, vs, uvs=None, mat: str = "item_steel_tool", smooth: bool = True) -> None:
        vs = list(vs)
        if uvs is None:
            uvs = [(0.0, 0.0)] * len(vs)
        # drop consecutive duplicates (collapsed tips)
        out_v, out_uv = [], []
        for v, uv in zip(vs, uvs):
            if out_v and out_v[-1] == v:
                continue
            out_v.append(v)
            out_uv.append(tuple(uv))
        if len(out_v) > 1 and out_v[0] == out_v[-1]:
            out_v.pop()
            out_uv.pop()
        if len(out_v) < 3 or len(set(out_v)) != len(out_v):
            return
        self.faces.append(tuple(out_v))
        self.fuv.append(out_uv)
        self.fmat.append(mat)
        self.fsmooth.append(smooth)

    def tri_fan(self, center: int, ring: list[int], uvc, uvr, mat: str, smooth: bool = True, reverse: bool = False) -> None:
        n = len(ring)
        for k in range(n):
            a, b = ring[k], ring[(k + 1) % n]
            ua, ub = uvr[k], uvr[(k + 1) % n]
            if reverse:
                self.face((center, b, a), (uvc, ub, ua), mat, smooth)
            else:
                self.face((center, a, b), (uvc, ua, ub), mat, smooth)

    def extend(self, other: "MB") -> None:
        off = len(self.co)
        self.co += other.co
        self.faces += [tuple(i + off for i in f) for f in other.faces]
        self.fuv += other.fuv
        self.fmat += other.fmat
        self.fsmooth += other.fsmooth

    def build(self, name: str, *, recalc: bool = False, sharp_deg: float | None = 40.0) -> bpy.types.Object:
        me = bpy.data.meshes.new(name)
        me.from_pydata([tuple(c) for c in self.co], [], self.faces)
        me.update()
        obj = common.new_object(name, me)
        uvl = me.uv_layers.new(name="UVMap")
        uvdata = [0.0] * (len(me.loops) * 2)
        for p, uvs in zip(me.polygons, self.fuv):
            assert p.loop_total == len(uvs)
            for k in range(p.loop_total):
                uvdata[(p.loop_start + k) * 2] = uvs[k][0]
                uvdata[(p.loop_start + k) * 2 + 1] = uvs[k][1]
        uvl.data.foreach_set("uv", uvdata)
        slots: dict[str, int] = {}
        for m in self.fmat:
            if m not in slots:
                slots[m] = material_slot(obj, m)
        me.polygons.foreach_set("material_index", [slots[m] for m in self.fmat])
        me.polygons.foreach_set("use_smooth", [bool(s) for s in self.fsmooth])
        if recalc:
            bm = bmesh.new()
            bm.from_mesh(me)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            bm.to_mesh(me)
            bm.free()
        me.update()
        if sharp_deg is not None:
            mark_sharp(obj, sharp_deg)
        return obj


def mark_sharp(obj: bpy.types.Object, angle_deg: float) -> None:
    """Edges sharper than angle_deg (or between flat-shaded / different-material faces) split normals."""
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    lim = math.radians(angle_deg)
    for e in bm.edges:
        if len(e.link_faces) == 2:
            f1, f2 = e.link_faces
            a = f1.normal.angle(f2.normal, 0.0)
            e.smooth = a < lim and f1.smooth and f2.smooth
        else:
            e.smooth = True
    bm.to_mesh(me)
    bm.free()
    me.update()


# ------------------------------------------------------------------------------------------------
# Curves / frames
# ------------------------------------------------------------------------------------------------

def rmf(pts: list[Vector], up: Vector | None = None) -> tuple[list[Vector], list[Vector], list[Vector]]:
    """Rotation-minimising frames (double reflection). Returns tangents, normals, binormals."""
    n = len(pts)
    T = []
    for i in range(n):
        if i == 0:
            t = pts[1] - pts[0]
        elif i == n - 1:
            t = pts[-1] - pts[-2]
        else:
            a = pts[i + 1] - pts[i]
            b = pts[i] - pts[i - 1]
            t = (a.normalized() if a.length > 1e-9 else a) + (b.normalized() if b.length > 1e-9 else b)
        T.append(t.normalized() if t.length > 1e-12 else Vector((0, 0, 1)))
    t0 = T[0]
    ref = up if up is not None else (Vector((0, 0, 1)) if abs(t0.z) < 0.9 else Vector((1, 0, 0)))
    n0 = ref - t0 * ref.dot(t0)
    if n0.length < 1e-6:
        n0 = t0.orthogonal()
    N = [n0.normalized()]
    for i in range(n - 1):
        v1 = pts[i + 1] - pts[i]
        c1 = v1.dot(v1)
        if c1 < 1e-14:
            N.append(N[-1].copy())
            continue
        rL = N[i] - (2.0 / c1) * v1.dot(N[i]) * v1
        tL = T[i] - (2.0 / c1) * v1.dot(T[i]) * v1
        v2 = T[i + 1] - tL
        c2 = v2.dot(v2)
        nn = rL - (2.0 / c2) * v2.dot(rL) * v2 if c2 > 1e-14 else rL
        nn = nn - T[i + 1] * nn.dot(T[i + 1])
        N.append(nn.normalized())
    B = [T[i].cross(N[i]) for i in range(n)]
    return T, N, B


def arclen(pts: list[Vector]) -> list[float]:
    s = [0.0]
    for a, b in zip(pts[:-1], pts[1:]):
        s.append(s[-1] + (b - a).length)
    return s


def bezier(p0, p1, p2, p3, n: int) -> list[Vector]:
    p0, p1, p2, p3 = (Vector(p) for p in (p0, p1, p2, p3))
    out = []
    for i in range(n):
        t = i / (n - 1)
        u = 1 - t
        out.append(p0 * u ** 3 + p1 * 3 * u * u * t + p2 * 3 * u * t * t + p3 * t ** 3)
    return out


def polyline_resample(pts: list[Vector], n: int) -> list[Vector]:
    s = arclen(pts)
    total = s[-1]
    out = []
    j = 0
    for i in range(n):
        target = total * i / (n - 1)
        while j < len(s) - 2 and s[j + 1] < target:
            j += 1
        seg = s[j + 1] - s[j]
        t = 0.0 if seg < 1e-12 else (target - s[j]) / seg
        out.append(pts[j].lerp(pts[j + 1], min(1.0, max(0.0, t))))
    return out


def circle_profile(sides: int, rot: float = 0.0) -> list[tuple[float, float]]:
    return [(math.cos(rot + 2 * math.pi * k / sides), math.sin(rot + 2 * math.pi * k / sides)) for k in range(sides)]


def rect_profile(w: float = 1.0, h: float = 1.0, bevel: float = 0.0) -> list[tuple[float, float]]:
    """Rectangle (+-w, +-h) counter-clockwise; with bevel the corners are chamfered (8 points)."""
    if bevel <= 0:
        return [(w, -h), (w, h), (-w, h), (-w, -h)]
    b = bevel
    return [(w, -h + b), (w, h - b), (w - b, h), (-w + b, h), (-w, h - b), (-w, -h + b), (-w + b, -h), (w - b, -h)]


def tube(mb: MB, pts, radius, *, sides: int = 8, mat: str = "item_wood_raw", profile=None, closed: bool = False,
         caps=(True, True), cap_mat: str | None = None, cap_uv: str = "metric", u_tile: float | None = None,
         v_scale: float = 1.0, v_offset: float = 0.0, twist: float = 0.0, up: Vector | None = None,
         smooth: bool = True, rot: float = 0.0, radius_fn=None) -> list[list[int]]:
    """Sweeps a cross-section along a polyline. radius: float | (rx, ry) | list of those per point.
    profile: 2D points (unit) CCW; default circle with `sides`. u spans the circumference in metres
    (or [0, u_tile]); v = arclength * v_scale. Returns the rings of vertex indices."""
    pts = [Vector(p) for p in pts]
    n = len(pts)
    T, N, B = rmf(pts, up)
    prof = profile if profile is not None else circle_profile(sides, rot)
    ns = len(prof)
    # radius: float or (rx, ry) tuple = constant; a *list* = one value per point
    radii = list(radius) if isinstance(radius, list) else [radius] * n
    if closed:
        # distribute the frame mismatch so the loop closes without a twist seam
        T2, N2, B2 = rmf(pts + [pts[0]], up)
        mis = math.atan2(N2[-1].dot(B[0]), N2[-1].dot(N[0]))
    s = arclen(pts + ([pts[0]] if closed else []))
    total = s[-1]
    rings = []
    rmean = []
    for i in range(n):
        r = radii[i]
        rx, ry = (r, r) if not isinstance(r, (list, tuple)) else r
        if radius_fn is not None:
            f = radius_fn(i, s[i] / max(total, 1e-9))
            rx, ry = rx * f, ry * f
        rmean.append((rx + ry) * 0.5)
        ang = twist * s[i] - (mis * s[i] / total if closed else 0.0)
        ca, sa = math.cos(ang), math.sin(ang)
        ring = []
        for px, py in prof:
            qx, qy = px * ca - py * sa, px * sa + py * ca
            ring.append(mb.vert(pts[i] + N[i] * (qx * rx) + B[i] * (qy * ry)))
        rings.append(ring)
    circ = 2 * math.pi * (sum(rmean) / len(rmean))
    # perimeter fractions of the profile for u
    per = [0.0]
    for k in range(ns):
        a, b = prof[k], prof[(k + 1) % ns]
        per.append(per[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    us = [p / per[-1] * (u_tile if u_tile is not None else circ) for p in per]
    segs = n if closed else n - 1
    for i in range(segs):
        j = (i + 1) % n
        va, vb = s[i] * v_scale + v_offset, s[i + 1] * v_scale + v_offset
        for k in range(ns):
            k2 = (k + 1) % ns
            mb.face((rings[i][k], rings[i][k2], rings[j][k2], rings[j][k]),
                    ((us[k], va), (us[k + 1], va), (us[k + 1], vb), (us[k], vb)), mat, smooth)
    if not closed:
        cm = cap_mat or mat
        for end, ring, rr in ((0, rings[0], radii[0]), (1, rings[-1], radii[-1])):
            if not caps[end]:
                continue
            rx, ry = (rr, rr) if not isinstance(rr, (list, tuple)) else rr
            if cap_uv == "disc":
                uvr = [(0.5 + 0.46 * px, 0.5 + 0.46 * py) for px, py in prof]
            else:
                uvr = [(px * rx, py * ry) for px, py in prof]
            if end == 0:
                mb.face(list(reversed(ring)), list(reversed(uvr)), cm, False)
            else:
                mb.face(ring, uvr, cm, False)
    return rings


def lathe(mb: MB, profile: list[tuple[float, float]], *, segments: int = 24, mat: str = "item_can_tin",
          regions: list[tuple[int, int, str, str]] | None = None, cap_bottom: bool = True, cap_top: bool = True,
          cap_mat_bottom: str | None = None, cap_mat_top: str | None = None, u_tile: float | None = None,
          angle0: float = 0.0, smooth: bool = True, cap_uv: str = "metric", radial_fn=None) -> list[list[int]]:
    """Surface of revolution around local Z. profile = [(r, z)] bottom->top.
    regions = [(i0, i1, mat, uvmode)] for segments i0..i1-1 ("metric" | "label": u 0..1 around, v 0..1 over region).
    radial_fn(k, i, r, z) -> radius multiplier (dents / flutes)."""
    rings = []
    for i, (r, z) in enumerate(profile):
        ring = []
        for k in range(segments):
            a = angle0 + 2 * math.pi * k / segments
            rr = r * (radial_fn(k, i, r, z) if radial_fn else 1.0)
            ring.append(mb.vert((rr * math.cos(a), rr * math.sin(a), z)))
        rings.append(ring)
    s = [0.0]
    for (r0, z0), (r1, z1) in zip(profile[:-1], profile[1:]):
        s.append(s[-1] + math.hypot(r1 - r0, z1 - z0))
    rmax = max(r for r, _ in profile)
    circ = u_tile if u_tile is not None else 2 * math.pi * rmax
    reg = {}
    for entry in (regions or []):
        i0, i1, m, mode = entry[:4]
        utile = entry[4] if len(entry) > 4 else 1.0
        for i in range(i0, i1):
            reg[i] = (m, mode, i0, i1, utile)
    for i in range(len(profile) - 1):
        m, mode, i0, i1, utile = reg.get(i, (mat, "metric", 0, 0, 1.0))
        for k in range(segments):
            k2 = (k + 1) % segments
            if mode == "label":
                z0, z1 = profile[i0][1], profile[i1][1]
                va = (profile[i][1] - z0) / (z1 - z0)
                vb = (profile[i + 1][1] - z0) / (z1 - z0)
                ua, ub = k / segments * utile, (k + 1) / segments * utile
            else:
                va, vb = s[i], s[i + 1]
                ua, ub = k / segments * circ, (k + 1) / segments * circ
            mb.face((rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]),
                    ((ua, va), (ub, va), (ub, vb), (ua, vb)), m, smooth)
    for end, ring, (r, z), cm in ((0, rings[0], profile[0], cap_mat_bottom), (1, rings[-1], profile[-1], cap_mat_top)):
        if (end == 0 and not cap_bottom) or (end == 1 and not cap_top) or r < 1e-6:
            continue
        c = mb.vert((0, 0, z))
        if cap_uv == "disc":
            uvr = [(0.5 + 0.46 * math.cos(angle0 + 2 * math.pi * k / segments),
                    0.5 + 0.46 * math.sin(angle0 + 2 * math.pi * k / segments)) for k in range(segments)]
            uvc = (0.5, 0.5)
        else:
            uvr = [(r * math.cos(angle0 + 2 * math.pi * k / segments), r * math.sin(angle0 + 2 * math.pi * k / segments))
                   for k in range(segments)]
            uvc = (0.0, 0.0)
        mb.tri_fan(c, ring, uvc, uvr, cm or mat, smooth=False, reverse=(end == 0))
    return rings


def extrude(mb: MB, outline: list[tuple[float, float]], depth: float, *, holes: list[list[tuple[float, float]]] | None = None,
            mat: str = "item_steel_tool", side_mat: str | None = None, chamfer: float = 0.0, uv_scale: float = 1.0,
            uv_rect: tuple[float, float, float, float] | None = None, center: float = 0.0, smooth_sides: bool = False) -> None:
    """Extrudes a 2D outline (local X, Y; CCW) along local Z from center-depth/2 to center+depth/2.
    holes: inner loops (any winding). chamfer: inset of the cap faces (bevelled rim, 45 deg).
    UV: caps planar (metres * uv_scale or mapped into uv_rect), sides u = perimeter, v = z."""
    side_mat = side_mat or mat
    loops = [outline] + list(holes or [])
    z0, z1 = center - depth / 2, center + depth / 2
    xs = [p[0] for p in outline]
    ys = [p[1] for p in outline]
    bx0, bx1, by0, by1 = min(xs), max(xs), min(ys), max(ys)

    def cap_uv(p):
        if uv_rect is None:
            return (p[0] * uv_scale, p[1] * uv_scale)
        u = (p[0] - bx0) / max(1e-9, bx1 - bx0)
        v = (p[1] - by0) / max(1e-9, by1 - by0)
        return (uv_rect[0] + u * (uv_rect[2] - uv_rect[0]), uv_rect[1] + v * (uv_rect[3] - uv_rect[1]))

    def signed_area(lp):
        return 0.5 * sum(lp[i][0] * lp[(i + 1) % len(lp)][1] - lp[(i + 1) % len(lp)][0] * lp[i][1] for i in range(len(lp)))

    norm_loops = []
    for li, lp in enumerate(loops):
        ccw = signed_area(lp) > 0
        want_ccw = li == 0
        norm_loops.append(list(lp) if ccw == want_ccw else list(reversed(lp)))

    def inset(lp, d):
        if d <= 0:
            return lp
        out = []
        n = len(lp)
        for i in range(n):
            p0, p1, p2 = Vector(lp[i - 1]), Vector(lp[i]), Vector(lp[(i + 1) % n])
            e0 = (p1 - p0).normalized()
            e1 = (p2 - p1).normalized()
            n0 = Vector((-e0.y, e0.x))
            n1 = Vector((-e1.y, e1.x))
            nb = n0 + n1
            if nb.length < 1e-6:
                nb = n0
            nb.normalize()
            cosh = max(0.35, nb.dot(n0))
            q = p1 + nb * (d / cosh)
            out.append((q.x, q.y))
        return out
    # caps (inset when chamfered; the outer loop's left side is inside for CCW, holes are CW so also inward)
    cap_loops = [inset(lp, chamfer) for lp in norm_loops]
    flat = [p for lp in cap_loops for p in lp]
    top_idx = [mb.vert((p[0], p[1], z1)) for p in flat]
    bot_idx = [mb.vert((p[0], p[1], z0)) for p in flat]
    if len(cap_loops) == 1:
        # single n-gon caps (outer loop is CCW): keeps large faces whole so wear_inset can work on them
        n0 = len(flat)
        mb.face([top_idx[i] for i in range(n0)], [cap_uv(flat[i]) for i in range(n0)], mat, False)
        mb.face([bot_idx[i] for i in reversed(range(n0))], [cap_uv(flat[i]) for i in reversed(range(n0))], mat, False)
        tris = []
    else:
        tris = geometry.tessellate_polygon([[Vector((p[0], p[1], 0.0)) for p in lp] for lp in cap_loops])
    for t in tris:
        a, b, c = t
        pa, pb, pc = Vector(flat[a]), Vector(flat[b]), Vector(flat[c])
        if ((pb.x - pa.x) * (pc.y - pa.y) - (pb.y - pa.y) * (pc.x - pa.x)) > 0:
            ta = (a, b, c)
        else:
            ta = (a, c, b)
        mb.face([top_idx[i] for i in ta], [cap_uv(flat[i]) for i in ta], mat, False)
        mb.face([bot_idx[i] for i in reversed(ta)], [cap_uv(flat[i]) for i in reversed(ta)], mat, False)
    # sides
    off = 0
    for lp, cl in zip(norm_loops, cap_loops):
        n = len(lp)
        per = [0.0]
        for i in range(n):
            per.append(per[-1] + math.dist(lp[i], lp[(i + 1) % n]))
        if chamfer > 0:
            zc0, zc1 = z0 + chamfer, z1 - chamfer
            rims = [[mb.vert((p[0], p[1], zc0)) for p in lp], [mb.vert((p[0], p[1], zc1)) for p in lp]]
            for i in range(n):
                j = (i + 1) % n
                ua, ub = per[i] * uv_scale, per[i + 1] * uv_scale
                # wall
                mb.face((rims[0][i], rims[0][j], rims[1][j], rims[1][i]),
                        ((ua, zc0 * uv_scale), (ub, zc0 * uv_scale), (ub, zc1 * uv_scale), (ua, zc1 * uv_scale)), side_mat, smooth_sides)
                # top chamfer
                mb.face((rims[1][i], rims[1][j], top_idx[off + j], top_idx[off + i]),
                        ((ua, zc1 * uv_scale), (ub, zc1 * uv_scale), (ub, z1 * uv_scale), (ua, z1 * uv_scale)), side_mat, smooth_sides)
                # bottom chamfer
                mb.face((bot_idx[off + i], bot_idx[off + j], rims[0][j], rims[0][i]),
                        ((ua, z0 * uv_scale), (ub, z0 * uv_scale), (ub, zc0 * uv_scale), (ua, zc0 * uv_scale)), side_mat, smooth_sides)
        else:
            for i in range(n):
                j = (i + 1) % n
                ua, ub = per[i] * uv_scale, per[i + 1] * uv_scale
                mb.face((bot_idx[off + i], bot_idx[off + j], top_idx[off + j], top_idx[off + i]),
                        ((ua, z0 * uv_scale), (ub, z0 * uv_scale), (ub, z1 * uv_scale), (ua, z1 * uv_scale)), side_mat, smooth_sides)
        off += n


def box(mb: MB, size, center=(0, 0, 0), *, mat: str = "item_wood_plank", bevel: float = 0.0, uv_scale: float = 1.0,
        uv_rot: bool = False) -> None:
    """Axis-aligned box (optionally chamfered) with metric box-projected UVs."""
    sx, sy, sz = (s / 2 for s in size)
    cx, cy, cz = center
    if bevel <= 0:
        out = [(-sx, -sy), (sx, -sy), (sx, sy), (-sx, sy)]
        mb.push(Matrix.Translation((cx, cy, cz)))
        extrude(mb, out, sz * 2, mat=mat, uv_scale=uv_scale)
        mb.pop()
        _fix_box_uv(mb, len(mb.faces) - 6, uv_scale, uv_rot)
        return
    b = min(bevel, sx * 0.9, sy * 0.9, sz * 0.9)
    out = rect_profile(sx, sy, b)
    out = [(p[0], p[1]) for p in out]
    mb.push(Matrix.Translation((cx, cy, cz)))
    n0 = len(mb.faces)
    extrude(mb, out, sz * 2, mat=mat, chamfer=b, uv_scale=uv_scale)
    mb.pop()
    _fix_box_uv(mb, n0, uv_scale, uv_rot)


def _fix_box_uv(mb: MB, first_face: int, scale: float, rot: bool) -> None:
    """Re-projects UVs of faces from first_face on with a box projection (dominant axis)."""
    for fi in range(max(0, first_face), len(mb.faces)):
        vs = [mb.co[i] for i in mb.faces[fi]]
        nrm = geometry.normal(vs) if len(vs) >= 3 else Vector((0, 0, 1))
        ax = max(range(3), key=lambda i: abs(nrm[i]))
        uvs = []
        for co in vs:
            if ax == 0:
                u, v = (co.y if nrm.x > 0 else -co.y), co.z
            elif ax == 1:
                u, v = (-co.x if nrm.y > 0 else co.x), co.z
            else:
                u, v = co.x, (co.y if nrm.z > 0 else -co.y)
            if rot:
                u, v = v, u
            uvs.append((u * scale, v * scale))
        mb.fuv[fi] = uvs


def reproject_box(mb: MB, first_face: int = 0, scale: float = 1.0, rot: bool = False) -> None:
    _fix_box_uv(mb, first_face, scale, rot)


def sheet(mb: MB, nu: int, nv: int, pos_fn, *, thickness: float = 0.0004, mat_top: str = "item_paper",
          mat_bottom: str | None = None, mat_edge: str | None = None, uv_top=None, uv_bottom=None,
          smooth: bool = True) -> None:
    """Thin double-sided sheet. pos_fn(u, v) -> Vector (u, v in [0,1]). The top side (normal = du x dv)
    gets uv_top(u, v) (default (u, v)), the bottom side uv_bottom(u, v) (default (1-u, v))."""
    mat_bottom = mat_bottom or mat_top
    mat_edge = mat_edge or mat_bottom
    uv_top = uv_top or (lambda u, v: (u, v))
    uv_bottom = uv_bottom or (lambda u, v: (1 - u, v))
    P = [[Vector(pos_fn(i / nu, j / nv)) for j in range(nv + 1)] for i in range(nu + 1)]
    Nrm = [[None] * (nv + 1) for _ in range(nu + 1)]
    for i in range(nu + 1):
        for j in range(nv + 1):
            du = P[min(nu, i + 1)][j] - P[max(0, i - 1)][j]
            dv = P[i][min(nv, j + 1)] - P[i][max(0, j - 1)]
            n = du.cross(dv)
            Nrm[i][j] = n.normalized() if n.length > 1e-12 else Vector((0, 0, 1))
    h = thickness / 2
    top = [[mb.vert(P[i][j] + Nrm[i][j] * h) for j in range(nv + 1)] for i in range(nu + 1)]
    bot = [[mb.vert(P[i][j] - Nrm[i][j] * h) for j in range(nv + 1)] for i in range(nu + 1)]
    for i in range(nu):
        for j in range(nv):
            u0, u1, v0, v1 = i / nu, (i + 1) / nu, j / nv, (j + 1) / nv
            mb.face((top[i][j], top[i + 1][j], top[i + 1][j + 1], top[i][j + 1]),
                    (uv_top(u0, v0), uv_top(u1, v0), uv_top(u1, v1), uv_top(u0, v1)), mat_top, smooth)
            mb.face((bot[i][j], bot[i][j + 1], bot[i + 1][j + 1], bot[i + 1][j]),
                    (uv_bottom(u0, v0), uv_bottom(u0, v1), uv_bottom(u1, v1), uv_bottom(u1, v0)), mat_bottom, smooth)
    # rim
    border = [(i, 0) for i in range(nu)] + [(nu, j) for j in range(nv)] + [(i, nv) for i in range(nu, 0, -1)] + [(0, j) for j in range(nv, 0, -1)]
    for k in range(len(border)):
        a = border[k]
        b = border[(k + 1) % len(border)]
        uvs = ((k * 0.01, 0.0), ((k + 1) * 0.01, 0.0), ((k + 1) * 0.01, thickness), (k * 0.01, thickness))
        mb.face((bot[a[0]][a[1]], bot[b[0]][b[1]], top[b[0]][b[1]], top[a[0]][a[1]]), uvs, mat_edge, False)


def blade(mb: MB, stations: list[dict], *, mat_flat: str = "item_steel_tool", mat_bevel: str = "item_steel_bright",
          mat_spine: str | None = None, tip: bool = True, uv_scale: float = 1.0) -> None:
    """Blade in the canonical frame: length along +Z, edge toward -Y, flats facing +-X.
    station keys: z, ys (spine y), ye (edge y), ts (spine thickness), tsh (thickness at shoulder),
    fsh (shoulder position 0..1 from spine to edge). Optional 'x' lateral offset."""
    mat_spine = mat_spine or mat_flat
    rings = []
    for st in stations:
        z, ys, ye = st["z"], st["ys"], st["ye"]
        ts, tsh, fsh = st["ts"], st.get("tsh", st["ts"] * 0.8), st.get("fsh", 0.7)
        x0 = st.get("x", 0.0)
        ysh = ys + (ye - ys) * fsh
        te = st.get("te", 0.0002)
        y1 = ys + (ysh - ys) * 0.12
        y2 = ys + (ysh - ys) * 0.5
        y3 = ys + (ysh - ys) * 0.88
        t1 = ts + (tsh - ts) * 0.12
        t2 = ts + (tsh - ts) * 0.5
        t3 = ts + (tsh - ts) * 0.88
        pts = [(x0 + ts / 2, ys), (x0 + t1 / 2, y1), (x0 + t2 / 2, y2), (x0 + t3 / 2, y3), (x0 + tsh / 2, ysh), (x0 + te, ye),
               (x0 - te, ye), (x0 - tsh / 2, ysh), (x0 - t3 / 2, y3), (x0 - t2 / 2, y2), (x0 - t1 / 2, y1), (x0 - ts / 2, ys)]
        rings.append([mb.vert((p[0], p[1], z)) for p in pts])
    mats = [mat_flat] * 4 + [mat_bevel] * 3 + [mat_flat] * 4 + [mat_spine]
    nk = 12
    for i in range(len(rings) - 1):
        za, zb = stations[i]["z"], stations[i + 1]["z"]
        for k in range(nk):
            k2 = (k + 1) % nk
            ra, rb = rings[i], rings[i + 1]
            ya = mb.co[ra[k]].y
            yb = mb.co[ra[k2]].y
            mb.face((ra[k], rb[k], rb[k2], ra[k2]),
                    ((ya * uv_scale, za * uv_scale), (ya * uv_scale, zb * uv_scale), (yb * uv_scale, zb * uv_scale),
                     (yb * uv_scale, za * uv_scale)), mats[k], k != 5)
    # base cap (faces -Z) and tip cap (faces +Z); rings run clockwise seen from +Z
    r0 = rings[0]
    mb.face(r0, [(mb.co[i].x * uv_scale, mb.co[i].y * uv_scale) for i in r0], mat_flat, False)
    if tip:
        rl = rings[-1]
        mb.face(list(reversed(rl)), [(mb.co[i].x * uv_scale, mb.co[i].y * uv_scale) for i in reversed(rl)], mat_flat, False)


def helix(p0, p1, radius: float, turns: float, *, phase: float = 0.0, per_turn: int = 12, up: Vector | None = None,
          radius_end: float | None = None) -> list[Vector]:
    """Points of a helix wound around the axis p0->p1 (for lashings / coils)."""
    p0, p1 = Vector(p0), Vector(p1)
    ax = p1 - p0
    a = ax.normalized()
    ref = up if up is not None else (Vector((0, 0, 1)) if abs(a.z) < 0.9 else Vector((1, 0, 0)))
    n1 = (ref - a * ref.dot(a)).normalized()
    n2 = a.cross(n1)
    count = max(4, int(turns * per_turn) + 1)
    out = []
    for i in range(count):
        t = i / (count - 1)
        r = radius if radius_end is None else radius + (radius_end - radius) * t
        th = phase + 2 * math.pi * turns * t
        out.append(p0 + ax * t + (n1 * math.cos(th) + n2 * math.sin(th)) * r)
    return out


def lashing(mb: MB, p0, p1, core_radius: float, *, cord: float = 0.0028, turns: float = 6, per_turn: int = 10,
            sides: int = 5, mat: str = "item_cordage", phase: float = 0.0, up=None, wobble: float = 0.0, seed: int = 0) -> None:
    """A wound cord binding around a (roughly) cylindrical core between p0 and p1, with tucked ends."""
    pts = helix(p0, p1, core_radius + cord * 0.85, turns, phase=phase, per_turn=per_turn, up=up)
    if wobble > 0:
        noise.seed_set(seed)
        pts = [p + Vector((noise.noise(p * 40.0), noise.noise(p * 40.0 + Vector((5, 1, 3))), noise.noise(p * 40.0 + Vector((2, 9, 4))))) * wobble
               for p in pts]
    # tuck the ends under (pull them slightly toward the core)
    ax = (Vector(p1) - Vector(p0)).normalized()
    for idx in (0, -1):
        c = Vector(p0) if idx == 0 else Vector(p1)
        p = pts[idx]
        radial = (p - c) - ax * (p - c).dot(ax)
        pts[idx] = p - radial.normalized() * cord * 1.2
    circ = 2 * math.pi * cord
    tube(mb, pts, cord, sides=sides, mat=mat, u_tile=1.0, v_scale=1.0 / circ / 3.0, caps=(True, True), up=up)


# ------------------------------------------------------------------------------------------------
# Organic / natural helpers
# ------------------------------------------------------------------------------------------------

def branch_path(length: float, seed, *, bend: float = 0.03, n: int = 10, axis: str = "Z", start=(0, 0, 0)) -> list[Vector]:
    """A gently crooked stick centre line along +axis, starting at `start`."""
    r = common.rng(seed)
    a1 = r.uniform(0, math.tau)
    a2 = r.uniform(0, math.tau)
    pts = []
    for i in range(n):
        t = i / (n - 1)
        off = Vector((math.sin(t * math.pi + a1) * bend * 0.6 + math.sin(t * 2.7 * math.pi + a2) * bend * 0.25,
                      math.cos(t * 1.3 * math.pi + a2) * bend * 0.5, 0.0))
        off -= Vector((math.sin(a1) * bend * 0.6 + math.sin(a2) * bend * 0.25, math.cos(a2) * bend * 0.5, 0.0))
        p = Vector((off.x, off.y, t * length))
        if axis == "X":
            p = Vector((p.z, p.y, p.x))
        elif axis == "Y":
            p = Vector((p.x, p.z, p.y))
        pts.append(p + Vector(start))
    return pts


def stick(mb: MB, pts, r0: float, r1: float | None = None, *, sides: int = 8, seed: int = 0, bark: str = "item_bark_twig",
          end_mat: str = "item_wood_end", knots: int = 0, lumpy: float = 0.06, caps=(True, True)) -> list[list[int]]:
    """A barked stick along a polyline with taper r0 -> r1 and per-ring lumpiness; end-grain caps."""
    r1 = r0 if r1 is None else r1
    r = common.rng(seed)
    n = len(pts)
    radii = []
    for i in range(n):
        t = i / (n - 1)
        rr = (r0 + (r1 - r0) * t) * (1.0 + r.uniform(-lumpy, lumpy))
        radii.append(rr)
    rings = tube(mb, pts, radii, sides=sides, mat=bark, cap_mat=end_mat, cap_uv="disc", caps=caps, rot=r.uniform(0, 6.28))
    return rings


def jitter_verts(obj: bpy.types.Object, amount: float, scale: float, seed: int, *, mask=None) -> None:
    noise.seed_set(seed)
    me = obj.data
    for v in me.vertices:
        if mask is not None and not mask(v.co):
            continue
        d = Vector((noise.noise(v.co * scale), noise.noise(v.co * scale + Vector((7.1, 3.3, 1.7))),
                    noise.noise(v.co * scale + Vector((2.9, 8.4, 5.2)))))
        v.co += d * amount
    me.update()


def pebble(name: str, size, seed, *, mat: str = "item_stone", subdiv: int = 2, flat_bottom: float = 0.25,
           lump: float = 0.10, center=(0, 0, 0)) -> bpy.types.Object:
    """Rounded stone (river / field stone): displaced icosphere scaled to `size`, slightly flattened base."""
    r = common.rng(seed)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    obj = common.mesh_from_bmesh(name, bm)
    noise.seed_set(int(r.uniform(0, 1e5)))
    off = Vector((r.uniform(0, 50), r.uniform(0, 50), r.uniform(0, 50)))
    sx, sy, sz = (s / 2 for s in size)
    me = obj.data
    for v in me.vertices:
        d = v.co.normalized()
        f = 1.0 + noise.fractal(d * 1.3 + off, 0.5, 2.0, 3) * lump
        p = Vector((d.x * sx, d.y * sy, d.z * sz)) * f
        if p.z < -sz * (1 - flat_bottom):
            p.z = -sz * (1 - flat_bottom) + (p.z + sz * (1 - flat_bottom)) * 0.3
        v.co = p
    me.update()
    zs = [v.co.z for v in me.vertices]
    me.transform(Matrix.Translation((center[0], center[1], center[2] - min(zs))))
    mat_all(obj, mat)
    from . import uv as _uv
    _uv.box_project(obj, scale=1.0)
    common.shade_smooth(obj, angle_deg=70.0)
    return obj


def knapped(name: str, *, length: float, width: float, thickness: float, seed: int, scars: int = 40,
            edge_side: str = "-Y", mat: str = "item_knapped_stone", cortex_mat: str = "item_stone_cortex",
            cortex: float = 0.25, subdiv: int = 4, taper_power: float = 1.4, tris: int = 1300) -> bpy.types.Object:
    """Bifacially knapped stone head. Length along Y (cutting edge at -Y), width along Z, thickness X.
    A flattened lens is worked with planar flake removals (like real percussion flaking): rim flakes
    tilted toward the edge, cut alternately from both faces (giving a crisp, sinuous edge), then a few
    shallow invasive flakes across each face. Each scar gets a slight conchoidal hollow. The butt end
    keeps chalky cortex (`cortex` fraction of the length)."""
    r = common.rng(seed)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    obj = common.mesh_from_bmesh(name, bm)
    me = obj.data
    L, W, Tk = length / 2, width / 2, thickness / 2
    noise.seed_set(seed % 100000)
    off = Vector((r.uniform(0, 40), r.uniform(0, 40), r.uniform(0, 40)))
    for v in me.vertices:
        d = v.co.normalized()
        y = d.y * L
        t_edge = (y / L + 1.0) * 0.5          # 0 at the bit, 1 at the butt
        thick = Tk * (0.22 + 0.78 * t_edge ** (1.0 / taper_power))
        wid = W * (1.0 + 0.12 * (1 - t_edge)) * (1.0 - 0.18 * t_edge ** 3)
        lump = 1.0 + noise.fractal(d * 1.6 + off, 0.5, 2.0, 3) * 0.05
        v.co = Vector((d.x * thick * lump, y, d.z * wid * lump))
    me.update()
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)

    def flake(side, phi, inset, tilt, depth, hollow, reach):
        """Planar flake scar bounded to a disc of radius `reach` (YZ) around its start point, feathered
        at the termination; tilted toward the rim by `tilt`."""
        rad = Vector((0.0, math.sin(phi), math.cos(phi)))          # outward in the YZ outline
        n = (Vector((side, 0.0, 0.0)) * math.cos(tilt) + rad * math.sin(tilt)).normalized()
        nn = np.array(n)
        P = np.array([0.0, math.sin(phi) * L * inset, math.cos(phi) * W * inset])
        sel = co[:, 0] * side > 0
        d2 = ((co[:, 1] - P[1]) ** 2 + (co[:, 2] - P[2]) ** 2)
        d2[~sel] = 1e9
        P = co[int(np.argmin(d2))].copy()
        h = float(P @ nn) - depth
        proj = co @ nn
        dyz = np.sqrt((co[:, 1] - P[1]) ** 2 + (co[:, 2] - P[2]) ** 2)
        wgt = np.clip((reach - dyz) / (reach * 0.3), 0.0, 1.0)
        wgt = wgt * wgt * (3 - 2 * wgt)
        cut = sel & (proj > h) & (wgt > 0)
        if not cut.any():
            return
        amt = (proj[cut] - h) * wgt[cut]
        amt += hollow * wgt[cut] * np.clip(1.0 - (dyz[cut] / reach) ** 2, 0.0, 1.0)
        co[cut] -= np.outer(amt, nn)
    k_rim = int(scars * 0.65)
    for i in range(k_rim):
        side = 1 if i % 2 == 0 else -1
        phi = 2 * math.pi * (i + r.uniform(-0.3, 0.3)) / k_rim
        flake(side, phi + math.pi / 2, r.uniform(0.8, 0.95), math.radians(r.uniform(14, 26)),
              r.uniform(0.0022, 0.0038) * (thickness / 0.034), r.uniform(0.0003, 0.0006), r.uniform(0.38, 0.55) * min(L, W) * 1.6)
    for i in range(scars - k_rim):
        side = 1 if i % 2 == 0 else -1
        phi = r.uniform(0, math.tau)
        flake(side, phi, r.uniform(0.15, 0.55), math.radians(r.uniform(3, 8)), r.uniform(0.0012, 0.0022) * (thickness / 0.034),
              r.uniform(0.0002, 0.0005), r.uniform(0.35, 0.5) * min(L, W) * 1.4)
    me.vertices.foreach_set("co", co.ravel())
    me.update()
    if tris and common.triangle_count(obj) > tris:
        mod = obj.modifiers.new("dec", "DECIMATE")
        mod.ratio = tris / common.triangle_count(obj)
        mod.use_collapse_triangulate = True
        common.apply_modifiers(obj)
        me = obj.data
    edge_mat = material_slot(obj, mat)
    cortex_idx = material_slot(obj, cortex_mat) if cortex > 0 else edge_mat
    for p in me.polygons:
        cy = p.center.y / L
        p.material_index = cortex_idx if cy > 1.0 - cortex * 2 and abs(p.center.x) > Tk * 0.25 else edge_mat
    from . import uv as _uv
    _uv.box_project(obj, scale=1.0)
    common.shade_smooth(obj, angle_deg=16.0)
    if edge_side == "+Y":
        me.transform(Matrix.Rotation(math.pi, 4, "Z"))
    return obj


def card(mb: MB, base, direction, normal_hint, length: float, width: float, *, mat: str = "item_fir_bough",
         droop: float = 0.15, nu: int = 2, nv: int = 3, rect=(0.0, 0.0, 1.0, 1.0), curl: float = 0.0, twist: float = 0.0) -> None:
    """Bent foliage card: quad strip from `base` along `direction`, width across. UV v runs base->tip
    within `rect`. droop bends the card along -normal toward the tip (fraction of length)."""
    base = Vector(base)
    d = Vector(direction).normalized()
    nh = Vector(normal_hint)
    side = d.cross(nh)
    if side.length < 1e-6:
        side = d.orthogonal()
    side.normalize()
    nrm = side.cross(d).normalized()
    if nrm.dot(nh) < 0:
        nrm = -nrm
        side = -side
    grid = []
    for j in range(nv + 1):
        t = j / nv
        row = []
        for i in range(nu + 1):
            s = i / nu - 0.5
            ang = twist * t
            sd = side * math.cos(ang) + nrm * math.sin(ang)
            p = base + d * (length * t) + sd * (width * s) - nrm * (droop * length * t * t) + nrm * (curl * width * (s * s) * 2)
            row.append(mb.vert(p))
        grid.append(row)
    u0, v0, u1, v1 = rect
    for j in range(nv):
        for i in range(nu):
            a, b, c, e = grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]
            uv = ((u0 + (u1 - u0) * i / nu, v0 + (v1 - v0) * j / nv), (u0 + (u1 - u0) * (i + 1) / nu, v0 + (v1 - v0) * j / nv),
                  (u0 + (u1 - u0) * (i + 1) / nu, v0 + (v1 - v0) * (j + 1) / nv), (u0 + (u1 - u0) * i / nu, v0 + (v1 - v0) * (j + 1) / nv))
            mb.face((a, b, c, e), uv, mat, True)


# ------------------------------------------------------------------------------------------------
# Object utilities
# ------------------------------------------------------------------------------------------------

def mesh_objects(objs) -> list[bpy.types.Object]:
    return [o for o in objs if o is not None and o.type == "MESH" and not o.name.endswith("colonly")]


def world_verts(objs) -> np.ndarray:
    out = []
    for o in mesh_objects(objs):
        mw = o.matrix_world
        n = len(o.data.vertices)
        co = np.empty(n * 3, np.float64)
        o.data.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        m = np.array(mw)
        out.append(co @ m[:3, :3].T + m[:3, 3])
    return np.concatenate(out) if out else np.zeros((0, 3))


def centroid(objs) -> Vector:
    """Area-weighted centroid of all faces (proxy for the centre of mass)."""
    tot = 0.0
    acc = Vector()
    for o in mesh_objects(objs):
        mw = o.matrix_world
        for p in o.data.polygons:
            a = p.area
            acc += (mw @ p.center) * a
            tot += a
    return acc / tot if tot > 0 else Vector()


def transform_objects(objs, m: Matrix) -> None:
    """Applies m to the mesh data of every object (all kit objects keep identity object transforms;
    going through matrix_world would read stale matrices between depsgraph updates)."""
    for o in objs:
        if o is None or o.type != "MESH":
            continue
        bake_transforms([o])
        o.data.transform(m)
        o.data.update()


def bake_transforms(objs) -> None:
    for o in objs:
        if o is not None and o.type == "MESH" and o.matrix_basis != Matrix.Identity(4):
            common.apply_transforms(o)
            o.data.update()
            bpy.context.view_layer.update()


def settle(objs, *, max_deg: float = 25.0, axes: str = "XY") -> None:
    """Rotates the objects (about their centroid) into the nearby resting pose with the lowest centre
    of mass above the support plane, then drops them to z=0 (bottom centre at the origin)."""
    com = centroid(objs)
    V = world_verts(objs) - np.array(com)
    if len(V) == 0:
        return

    def rot(ax, ay):
        rx = np.array(Matrix.Rotation(math.radians(ax), 3, "X"))
        ry = np.array(Matrix.Rotation(math.radians(ay), 3, "Y"))
        return ry @ rx

    def height(ax, ay):
        R = rot(ax, ay)
        z = V @ R[2]
        return -z.min()
    ang = [0.0, 0.0]
    best = height(*ang)
    for step in (6.0, 3.0, 1.5, 0.75, 0.375):
        improved = True
        guard = 0
        while improved and guard < 40:
            improved = False
            guard += 1
            for a in range(2):
                if "XY"[a] not in axes:
                    continue
                for sgn in (1, -1):
                    cand = list(ang)
                    cand[a] += sgn * step
                    if abs(cand[a]) > max_deg:
                        continue
                    h = height(*cand)
                    if h < best - 1e-7:
                        best, ang = h, cand
                        improved = True
    R = Matrix.Rotation(math.radians(ang[1]), 4, "Y") @ Matrix.Rotation(math.radians(ang[0]), 4, "X")
    m = Matrix.Translation(com) @ R @ Matrix.Translation(-com)
    transform_objects(objs, m)
    drop_to_ground(objs)


def drop_to_ground(objs, *, center_xy: bool = True) -> None:
    V = world_verts(objs)
    lo, hi = V.min(0), V.max(0)
    off = Vector((-(lo[0] + hi[0]) / 2 if center_xy else 0.0, -(lo[1] + hi[1]) / 2 if center_xy else 0.0, -lo[2]))
    transform_objects(objs, Matrix.Translation(off))


def socket(name: str, location, forward=(0, -1, 0)) -> bpy.types.Object:
    """Empty marker; its local +Y is aimed along `forward` (Godot node -Z then points along it)."""
    e = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(e)
    f = Vector(forward).normalized()
    q = f.to_track_quat("Y", "Z")
    e.matrix_world = Matrix.Translation(Vector(location)) @ q.to_matrix().to_4x4()
    e.empty_display_size = 0.02
    return e


# ------------------------------------------------------------------------------------------------
# Finishing + export
# ------------------------------------------------------------------------------------------------

def bake_wear_and_masks(obj: bpy.types.Object, *, wear_deg: float = 30.0, seed: int = 1, variation: float | None = None,
                        wind: float = 1.0, wear_scale: float = 30.0) -> None:
    vcolor.ensure_layer(obj)
    vcolor.bake_wear(obj, convex_threshold_deg=wear_deg, noise_scale=wear_scale, seed=seed)
    if variation is None:
        noise.seed_set(seed % 9973)
        vcolor.set_channel(obj, 2, lambda co, n, li: 0.5 + 0.5 * noise.noise(co * 6.0))
    else:
        vcolor.fill_channel(obj, 2, variation)
    vcolor.fill_channel(obj, 3, wind)


def bake_ao(objs, *, ground: bool, dist: float | None = None, samples: int = 20, strength: float = 0.9) -> None:
    ms = mesh_objects(objs)
    if not ms:
        return
    if dist is None:
        V = world_verts(ms)
        ext = float((V.max(0) - V.min(0)).max()) if len(V) else 0.3
        dist = max(0.025, min(1.0, ext * 0.3))
    vcolor.bake_ao(ms, samples=samples, distance=dist, strength=strength, ground=ground)


def foliage_wind(obj: bpy.types.Object, base_z: float = 0.0, height: float = 1.0, amount: float = 0.35) -> None:
    """Alpha (wind weight) rises with height above base_z for cards that should flutter a little."""
    vcolor.set_channel(obj, 3, lambda co, n, li: min(1.0, max(0.0, (co.z - base_z) / max(height, 1e-3))) * amount)


def finalize_mesh(obj: bpy.types.Object, sharp_deg: float | None = None) -> None:
    if sharp_deg is not None:
        mark_sharp(obj, sharp_deg)
    obj.data.update()


def export_objects(path: str, objs) -> None:
    objs = [o for o in objs if o is not None]
    meshes = [o for o in objs if o.type == "MESH"]
    others = [o for o in objs if o.type != "MESH"]
    export.export_glb(path, meshes + others)


def join(parts, name: str) -> bpy.types.Object:
    parts = [p for p in parts if p is not None]
    if len(parts) == 1:
        parts[0].name = name
        parts[0].data.name = name
        return parts[0]
    return common.join(parts, name)


def tri_count(objs) -> int:
    return sum(common.triangle_count(o) for o in mesh_objects(objs))


def remove(obj) -> None:
    if obj is not None:
        bpy.data.objects.remove(obj, do_unlink=True)


def duplicate(obj: bpy.types.Object, name: str) -> bpy.types.Object:
    me = obj.data.copy()
    me.name = name
    o = common.new_object(name, me)
    o.matrix_world = obj.matrix_world.copy()
    return o


WEAR_MATS = ("M_item_paint_", "M_item_plastic_olive", "M_item_steel_blued", "M_item_alu_anodized", "M_item_iron_strap",
             "M_item_stencil_band", "M_item_steel_dark", "M_item_alu_knurl")


def wear_inset(obj: bpy.types.Object, *, min_area: float | None = None, rel: float = 0.16, lo: float = 0.0012,
               hi: float = 0.03) -> int:
    """Insets large faces that use worn/coated materials so the vertex wear mask (G, baked on convex
    edges) has interior vertices to fall off to: wear then stays a band along the edges instead of
    interpolating across the whole face. Returns the number of faces inset."""
    me = obj.data
    mats = [m.name if m is not None else "" for m in me.materials]
    if not any(m.startswith(WEAR_MATS) for m in mats):
        return 0
    if min_area is None:
        V = world_verts([obj])
        ext = float((V.max(0) - V.min(0)).max()) if len(V) else 0.1
        min_area = (ext * 0.12) ** 2
    bm = bmesh.new()
    bm.from_mesh(me)
    todo = [f for f in bm.faces if f.material_index < len(mats) and mats[f.material_index].startswith(WEAR_MATS)
            and f.calc_area() > min_area]
    for f in todo:
        if not f.is_valid:
            continue
        edge = min(e.calc_length() for e in f.edges)
        t = max(lo, min(hi, rel * math.sqrt(f.calc_area()), edge * 0.3))
        bmesh.ops.inset_individual(bm, faces=[f], thickness=t, use_even_offset=True, use_interpolate=True)
    bm.to_mesh(me)
    bm.free()
    me.update()
    return len(todo)


def publish(outputs: list[str], *, name: str, parts, seed: int = 1, viewmodel: bool = False, ground_rot: Matrix | None = None,
            sockets=(), separate=(), colliders=(), settle_deg: float | None = 25.0, keep_origin: bool = False,
            wear_deg: float = 30.0, ao_samples: int = 20, ao_dist: float | None = None, foliage=(), report: dict | None = None,
            inset: bool = True, keep_xy: bool = False, pivot_bottom=(), drop: bool = True) -> dict:
    """Joins `parts` into one object `name`, bakes vertex colours and exports.

    outputs[0] = ground/world model; outputs[1] (when viewmodel=True) = the viewmodel, exported first in
    the canonical frame the parts were modelled in (with `sockets`). For the ground model the objects
    are rotated by `ground_rot`, settled into a resting pose (unless settle_deg is None) and dropped
    so the origin is the bottom centre (keep_origin=True leaves the frame untouched, e.g. log pieces
    whose origin is their centre). `separate` objects (lids) stay their own nodes; `foliage` objects
    (alpha cards) get a small wind weight instead of A=1. Returns {"tris": n}."""
    obj = join(parts, name)
    seps = [o for o in separate if o is not None]
    fol = [o for o in foliage if o is not None]
    meshes = [obj] + seps + fol
    if inset:
        for o in [obj] + seps:
            wear_inset(o)
    for i, o in enumerate(meshes):
        bake_wear_and_masks(o, wear_deg=wear_deg, seed=seed + i * 17)
    for o in fol:
        zmin = min((o.matrix_world @ v.co).z for v in o.data.vertices)
        foliage_wind(o, base_z=zmin, height=0.6, amount=0.3)
    info = {"tris": tri_count(meshes)}
    if viewmodel and len(outputs) > 1:
        bake_ao(meshes, ground=False, dist=ao_dist, samples=ao_samples)
        export_objects(outputs[1], meshes + list(sockets))
    for s in sockets:
        remove(s)
    cols = [c for c in colliders if c is not None]
    allobjs = meshes + cols
    if ground_rot is not None:
        transform_objects(allobjs, ground_rot)
    if not keep_origin and drop:
        if settle_deg is not None and settle_deg > 0:
            settle(allobjs, max_deg=settle_deg)
        else:
            drop_to_ground(allobjs, center_xy=not keep_xy)
    bake_ao(meshes, ground=not keep_origin, dist=ao_dist, samples=ao_samples)
    # separate parts that the game animates (e.g. a lid) get their node origin at their own bottom centre
    for o in meshes:
        if o.name in pivot_bottom:
            V = world_verts([o])
            lo, hi = V.min(0), V.max(0)
            piv = Vector(((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]))
            o.data.transform(Matrix.Translation(-piv))
            o.location = piv
    bpy.context.view_layer.update()
    export_objects(outputs[0], meshes + cols)
    if report is not None:
        report.update(info)
    print(f"[item_kit] {name}: {info['tris']} tris -> {outputs[0]}")
    return info


def collider_box(name: str, lo, hi) -> bpy.types.Object:
    """Box collision proxy '<name>-convcolonly' spanning lo..hi (no material)."""
    lo, hi = Vector(lo), Vector(hi)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=hi - lo, verts=bm.verts)
    bmesh.ops.translate(bm, vec=(lo + hi) / 2, verts=bm.verts)
    return common.mesh_from_bmesh(name + "-convcolonly", bm)


def collider_hull(name: str, objs, max_faces: int = 64) -> bpy.types.Object:
    """Convex hull collision proxy of the given objects' vertices (decimated)."""
    V = world_verts(objs)
    bm = bmesh.new()
    for p in V:
        bm.verts.new(Vector(p))
    bmesh.ops.convex_hull(bm, input=list(bm.verts))
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    o = common.mesh_from_bmesh(name + "-convcolonly", bm)
    if len(o.data.polygons) > max_faces:
        mod = o.modifiers.new("dec", "DECIMATE")
        mod.ratio = max_faces / len(o.data.polygons)
        common.apply_modifiers(o)
    return o
