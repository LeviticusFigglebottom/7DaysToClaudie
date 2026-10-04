"""Reusable furniture assemblies for the interior-props family: doors, drawers, legs, shelves, books,
packaged goods, shattered panes and the variant/damage helpers built on them."""
from __future__ import annotations

import math

from mathutils import Matrix, Vector

from . import common
from . import props_int_mesh as G
from .props_int_core import M, BOOK_PAGES, Part, Prop, book_cover_rect, book_rect, card_rect, set_face_uvs


# ------------------------------------------------------------------------------------------------
# carcasses
# ------------------------------------------------------------------------------------------------


def carcass(p: Prop, W: float, y0: float, y1: float, z0: float, z1: float, wood: str, *, top: bool = True,
            bottom: bool = True, back: bool = True, frame: bool = True, t: float = 0.018, frame_w: float = 0.04,
            rails=(), inner: str = M.PARTICLE, top_mat: str | None = None, side_mat: str | None = None) -> dict:
    """Cabinet box from panels: x in [-W/2, W/2], front y0 (face frame front), back y1, z0..z1.
    rails: [(z_centre, height), ...] horizontal face-frame rails (top/bottom rails are added when frame)."""
    D, H = y1 - y0, z1 - z0
    yc, zc = (y0 + y1) / 2, (z0 + z1) / 2
    sm = side_mat or wood
    parts: dict = {}
    parts["left"] = p.box((t, D, H), (-W / 2 + t / 2, yc, zc), sm, bevel=0.002, grain="Z", tags=("panel",))
    parts["right"] = p.box((t, D, H), (W / 2 - t / 2, yc, zc), sm, bevel=0.002, grain="Z", tags=("panel",))
    iw = W - 2 * t
    if bottom:
        parts["bottom"] = p.box((iw, D - 0.025, t), (0, yc + 0.0125, z0 + t / 2), inner, bevel=0.001, wear=0.3)
    if top:
        parts["top"] = p.box((iw, D - 0.025, t), (0, yc + 0.0125, z1 - t / 2), top_mat or wood, bevel=0.001, grain="X")
    if back:
        parts["back"] = p.box((iw, 0.006, H), (0, y1 - 0.003, zc), inner, bevel=0.0, wear=0.2)
    fr = []
    if frame:
        for sx in (-1, 1):
            fr.append(p.box((frame_w, 0.02, H), (sx * (W / 2 - frame_w / 2), y0 + 0.01, zc), wood, bevel=0.002, grain="Z"))
        for z, h in ((z1 - 0.02, 0.04), (z0 + 0.0175, 0.035)) + tuple(rails):
            fr.append(p.box((W - 2 * frame_w + 0.002, 0.02, h), (0, y0 + 0.01, z), wood, bevel=0.002, grain="X"))
    parts["frame"] = fr
    return parts


# ------------------------------------------------------------------------------------------------
# doors & drawers
# ------------------------------------------------------------------------------------------------


def door(p: Prop, x0: float, z0: float, x1: float, z1: float, y_front: float, mat: str, *, t: float = 0.019,
         style: str = "raised", frame: float = 0.055, hinge: str = "left", handle: str = "knob",
         handle_mat: str = M.BRASS, open_deg: float = 0.0, key: str = "door", handle_at: str = "top",
         recess: float = 0.006, handle_inset: float = 0.045) -> list[Part]:
    """Cabinet door in the XZ plane whose front face is at y_front (thickness toward +Y).
    Built closed, then swung outward by open_deg about its hinge edge."""
    w, h = x1 - x0, z1 - z0
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    grp = [p.panel(w, h, t, (cx, y_front + t / 2, cz), mat, style=style, frame=frame, recess=recess,
                   tags=("door", key))]
    if handle != "none":
        hx = x1 - handle_inset if hinge == "left" else x0 + handle_inset
        if handle_at == "top":
            hz = z1 - 0.07
        elif handle_at == "bottom":
            hz = z0 + 0.07
        else:
            hz = cz
        if handle == "knob":
            if not (p.worn and p.chance(f"{key}_knob_missing", 0.18)):
                grp.append(p.knob((hx, y_front, hz), handle_mat, tags=("knob", key)))
        elif handle == "bar_v":
            grp.append(p.bar_pull((hx, y_front, hz), 0.128, handle_mat, axis="Z", tags=("knob", key)))
        elif handle == "bar_h":
            grp.append(p.bar_pull((hx - (0.06 if hinge == "left" else -0.06), y_front, hz), 0.128, handle_mat, axis="X",
                                  tags=("knob", key)))
    if open_deg:
        swing(p, grp, x0 if hinge == "left" else x1, y_front + t, open_deg if hinge == "right" else -open_deg)
    return grp


def swing(p: Prop, grp, hinge_x: float, hinge_y: float, deg: float) -> None:
    p.rotate(grp, rot=(0, 0, deg), pivot=(hinge_x, hinge_y, 0))


def drawer(p: Prop, x0: float, z0: float, x1: float, z1: float, y_front: float, depth: float, mat: str, *,
           t: float = 0.019, style: str = "raised", frame: float = 0.035, handle: str = "knob", handle_mat: str = M.BRASS,
           pull: float = 0.0, key: str = "drawer", box_mat: str = M.PARTICLE, knobs: int = 1, recess: float = 0.005,
           contents: bool = True) -> list[Part]:
    """Drawer front in the XZ plane (front face at y_front) + tray behind it (only built when pulled
    out). pull = how far it sticks out (m)."""
    w, h = x1 - x0, z1 - z0
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    grp = [p.panel(w, h, t, (cx, y_front + t / 2, cz), mat, style=style, frame=frame, recess=recess, tags=("drawer", key))]
    if handle != "none":
        xs = [cx] if knobs == 1 else [x0 + w * 0.25, x1 - w * 0.25]
        for i, hx in enumerate(xs):
            if p.worn and p.chance(f"{key}_knob{i}", 0.15):
                continue
            if handle == "knob":
                grp.append(p.knob((hx, y_front, cz), handle_mat, tags=("knob", key)))
            elif handle == "bar":
                grp.append(p.bar_pull((hx, y_front, cz), min(0.128, w * 0.4), handle_mat, tags=("knob", key)))
            elif handle == "cup":
                grp.append(p.cup_pull((hx, y_front, cz + 0.01), 0.08, handle_mat, tags=("knob", key)))
    if pull > 0.001:
        tw, th = w - 0.04, max(0.04, h - 0.03)
        tray = p.hollow((tw, depth, th), (cx, y_front + t + depth / 2, cz - 0.005), box_mat, wall=0.012,
                        open_face="+Z", bevel=0.0, tags=("drawer_box", key), wear=0.4)
        grp.append(tray)
        if contents:
            r = p.rng(f"{key}_contents")
            for i in range(r.randint(1, 3)):
                cw, cd = r.uniform(0.06, tw * 0.4), r.uniform(0.05, depth * 0.4)
                ch = r.uniform(0.01, th * 0.5)
                c = (cx + r.uniform(-tw / 2 + cw / 2 + 0.015, tw / 2 - cw / 2 - 0.015),
                     y_front + t + 0.015 + cd / 2 + r.uniform(0, depth - cd - 0.03),
                     cz - th / 2 + 0.007 + ch / 2)
                grp.append(p.box((cw, cd, ch), c, [M.PAPER, M.LINEN, M.CARDBOARD][i % 3], bevel=0.002,
                                 tags=("drawer_stuff", key), uv_scale=1.0))
        p.move(grp, (0, -pull, 0))
    return grp


def lay_flat(p: Prop, grp, at, yaw: float = 0.0, face_up: bool = True, z: float = 0.0) -> None:
    """Panel group lying on the floor, front up (or down)."""
    p.lay_on_floor(grp, rot=(-90 if face_up else 90, 0, 0), at=at, yaw=yaw, z=z)


def hang(p: Prop, grp, hinge_x: float, hinge_y: float, top_z: float, open_deg: float, sag_deg: float,
         hinge: str = "left") -> None:
    """Door hanging from its top hinge only: swung open by open_deg, then sagging (free edge drops) by
    sag_deg about the door normal through the top hinge point."""
    th = math.radians(open_deg)
    if hinge == "left":
        swing(p, grp, hinge_x, hinge_y, -open_deg)
        n, s = Vector((-math.sin(th), -math.cos(th), 0.0)), -sag_deg
    else:
        swing(p, grp, hinge_x, hinge_y, open_deg)
        n, s = Vector((math.sin(th), -math.cos(th), 0.0)), sag_deg
    pv = Vector((hinge_x, hinge_y, top_z))
    p.rotate(grp, matrix=Matrix.Translation(pv) @ Matrix.Rotation(math.radians(s), 4, n) @ Matrix.Translation(-pv))


# ------------------------------------------------------------------------------------------------
# legs
# ------------------------------------------------------------------------------------------------


def tapered_leg(p: Prop, x: float, y: float, z0: float, z1: float, top: float, bottom: float, mat: str,
                key: str = "leg", splay=(0.0, 0.0)) -> Part:
    """Square tapered leg from z0 (floor) to z1, optional splay offset of the foot (dx, dy)."""
    hb, ht = bottom / 2, top / 2
    import bmesh
    bm = bmesh.new()
    pts = []
    for zz, hh, dx, dy in ((z0, hb, splay[0], splay[1]), (z1, ht, 0.0, 0.0)):
        pts.append([bm.verts.new((x + dx + sx * hh, y + dy + sy * hh, zz)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
    a, b = pts
    bm.faces.new(list(reversed(a)))
    bm.faces.new(b)
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.bevel(bm, geom=[e for e in bm.edges], offset=min(0.003, bottom * 0.2), offset_type="OFFSET", segments=1,
                    profile=0.5, affect="EDGES", clamp_overlap=True)
    obj = G._obj(p._name("leg"), bm)
    return p.add(obj, mat, tags=("leg", key), grain="Z")


def turned_leg(p: Prop, x: float, y: float, z0: float, z1: float, r: float, mat: str, key: str = "leg",
               style: str = "classic", segs: int = 10) -> Part:
    h = z1 - z0
    if style == "classic":
        # colonial turning: small foot, long elegant taper, a ring and cove under a plain top block
        prof = [(r * 0.5, 0.0), (r * 0.62, 0.025 * h), (r * 0.52, 0.06 * h), (r * 0.6, 0.12 * h), (r * 0.82, 0.6 * h),
                (r * 0.95, 0.66 * h), (r * 0.75, 0.7 * h), (r * 0.8, 0.74 * h), (r * 0.95, 0.76 * h), (r * 0.95, h)]
    elif style == "spindle":
        prof = [(r * 0.55, 0.0), (r * 0.7, 0.15 * h), (r, 0.45 * h), (r * 0.75, 0.75 * h), (r * 0.6, 0.9 * h),
                (r * 0.7, h)]
    else:  # simple taper
        prof = [(r * 0.6, 0.0), (r, h)]
    return p.lathe(prof, (x, y, z0), mat, segs=segs, tags=("leg", key))


# ------------------------------------------------------------------------------------------------
# damage
# ------------------------------------------------------------------------------------------------


def break_off(p: Prop, part: Part, z_cut: float, *, jag: float = 0.02, inner: str = M.WOOD_RAW, key: str = "break",
              keep_piece: bool = True, piece_at=None, piece_yaw: float = 0.0, axis=(0, 0, 1)) -> Part | None:
    """Snaps a vertical-ish part at height z_cut: the part keeps everything above the cut (splintered end);
    the broken-off lower piece (optional) is laid on the floor at piece_at."""
    from . import materials
    piece = None
    if keep_piece:
        me2 = part.obj.data.copy()
        obj2 = common.new_object(p._name("piece"), me2)
        piece = p.add(obj2, part.mat, tags=("debris", key), grain=part.grain, uv=part.uv, uv_axis=part.uv_axis,
                      edge_deg=part.edge_deg)
        slot2 = materials.assign(obj2, inner)
        G.splinter_cut(obj2, (0, 0, z_cut), axis, jag=jag, seed=p.seed + 11, inner_slot=slot2)
    slot = materials.assign(part.obj, inner)
    G.splinter_cut(part.obj, (0, 0, z_cut), tuple(-a for a in axis), jag=jag, seed=p.seed + 7, inner_slot=slot)
    if piece is not None:
        lo, hi = p.bounds([piece])
        at = piece_at if piece_at is not None else (lo.x, lo.y - 0.15)
        p.lay_on_floor([piece], rot=(90, 0, 0), at=at, yaw=piece_yaw)
    return piece


def split_panel(p: Prop, w: float, h: float, t: float, center, mat: str, a, b, *, plane: str = "XZ", inner: str = M.WOOD_RAW,
                teeth: int = 8, amp: float = 0.025, key: str = "split", tags=()) -> tuple[Part, Part]:
    """A flat panel (w x h, thickness t) broken in two along a zig-zag from a to b (2D points on its border,
    local coords centred). Returns the two halves (already positioned at `center`)."""
    q1, q2, b1, b2 = G.jagged_split(w, h, a, b, teeth=teeth, amp=amp, seed=p.seed + len(key))
    halves = []
    for poly, br in ((q1, b1), (q2, b2)):
        part = p.prism(poly, t, mat, plane=plane, offset=-t / 2, inner_mat=inner, inner_edges=br, tags=tags + (key,),
                       grain="auto")
        G.xform(part.obj, loc=center)
        halves.append(part)
    return halves[0], halves[1]


def shatter_pane(p: Prop, w: float, h: float, center, mat: str, *, t: float = 0.003, impact=(0.0, 0.0), spokes: int = 10,
                 rings: int = 3, missing_inner: float = 0.85, missing_outer: float = 0.15, key: str = "pane",
                 plane: str = "XZ", uv: str = "planar", floor_shards: int = 0, floor_at=(0.0, -0.3)) -> list[Part]:
    """Broken pane in a frame: crack cells, the ones near the impact mostly missing, the rest slightly
    tilted/offset. Each shard keeps the UVs of its position on the intact pane (planar 0..1)."""
    r = p.rng(key + "_shatter")
    cells = G.shatter_cells(w, h, impact, spokes, rings, seed=p.seed + 101)
    out = []
    lost = []
    for i, (poly, ring) in enumerate(cells):
        miss = missing_inner if ring == 0 else (missing_inner * 0.45 if ring == 1 else missing_outer)
        if r.random() < miss:
            lost.append(poly)
            continue
        part = p.prism(poly, t, mat, plane=plane, offset=-t / 2, tags=("shard", key), uv="keep")
        _pane_uv(part.obj, w, h, plane)
        cx = sum(q[0] for q in poly) / len(poly)
        cz = sum(q[1] for q in poly) / len(poly)
        tilt = (r.uniform(-4, 4), 0, r.uniform(-2, 2)) if plane == "XZ" else (r.uniform(-3, 3), r.uniform(-3, 3), 0)
        piv = (cx, 0, cz) if plane == "XZ" else (cx, cz, 0)
        G.xform(part.obj, rot=tilt, pivot=piv, loc=(0, r.uniform(-0.002, 0.002), 0) if plane == "XZ" else (0, 0, r.uniform(-0.001, 0.002)))
        G.xform(part.obj, loc=center)
        out.append(part)
    for i in range(min(floor_shards, len(lost))):
        poly = lost[i]
        part = p.prism(poly, t, mat, plane="XY", offset=0.0, tags=("shard", "debris", key), uv="keep")
        _pane_uv(part.obj, w, h, "XY")
        lo, hi = p.bounds([part])
        c = (lo + hi) * 0.5
        G.xform(part.obj, rot=(0, 0, r.uniform(0, 360)), pivot=c)
        G.xform(part.obj, loc=(floor_at[0] + r.uniform(-0.25, 0.25) - c.x, floor_at[1] + r.uniform(-0.2, 0.2) - c.y, 0.0005 * i))
        out.append(part)
    return out


def _pane_uv(obj, w, h, plane):
    me = obj.data
    uvl = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
    for li, loop in enumerate(me.loops):
        co = me.vertices[loop.vertex_index].co
        if plane == "XZ":
            u, v = co.x / w + 0.5, co.z / h + 0.5
        else:
            u, v = co.x / w + 0.5, co.y / h + 0.5
        uvl.data[li].uv = (u, v)


# ------------------------------------------------------------------------------------------------
# books & packaged goods
# ------------------------------------------------------------------------------------------------


def book(p: Prop, size, center, idx: int, *, paperback: bool = False, rot=(0, 0, 0), key: str = "book") -> Part:
    """Book with its spine facing -Y (before rotation). size = (thickness x, depth y, height z)."""
    tx, dy, hz = size
    obj = G.box(p._name("book"), size, (0, 0, 0), bevel=0.0)
    srect = book_rect(idx, paperback)
    crect = book_cover_rect(idx, paperback)

    def face_rect(poly):
        n = poly.normal
        if n.y < -0.9:  # spine
            return (*srect, 0, 2, False)
        if abs(n.x) > 0.9:  # covers
            return (*crect, 1, 2, False)
        return (*BOOK_PAGES, 0, 1 if abs(n.z) > 0.9 else 2, False)

    set_face_uvs(obj, face_rect)
    G.xform(obj, rot=rot, loc=center)
    return p.add(obj, M.BOOKS, uv="keep", tags=("book", key), wear=0.6)


def book_row(p: Prop, x0: float, x1: float, y_front: float, z: float, max_h: float, depth: float, *, key: str = "row",
             fill: float = 0.92, lean_end: bool = True, gaps: bool = True, paper_ratio: float = 0.25) -> list[Part]:
    """Fills a shelf span with books standing on z (spines at y_front facing -Y)."""
    r = p.rng(key)
    out = []
    x = x0 + r.uniform(0.0, 0.02)
    limit = x0 + (x1 - x0) * fill
    while x < limit:
        paper = r.random() < paper_ratio
        th = r.uniform(0.015, 0.03) if paper else r.uniform(0.022, 0.05)
        hh = min(max_h, r.uniform(0.17, 0.2) if paper else r.uniform(0.2, 0.29))
        dd = min(depth, r.uniform(0.11, 0.13) if paper else r.uniform(0.15, 0.22))
        if x + th > x1:
            break
        if gaps and r.random() < 0.06 and x + 0.08 < limit:
            # a book lying flat / gap
            x += r.uniform(0.03, 0.08)
            continue
        idx = r.randrange(64)
        out.append(book(p, (th, dd, hh), (x + th / 2, y_front + dd / 2 + r.uniform(0, 0.01), z + hh / 2), idx,
                        paperback=paper, key=key))
        x += th + r.uniform(0.0, 0.003)
    if lean_end and x + 0.06 < x1:
        th, hh, dd = r.uniform(0.025, 0.04), min(max_h, r.uniform(0.22, 0.27)), min(depth, 0.18)
        ang = r.uniform(12, 24)
        lean = book(p, (th, dd, hh), (0, 0, 0), r.randrange(64), key=key)
        G.xform(lean.obj, rot=(0, ang, 0))
        lo, hi = p.bounds([lean])
        G.xform(lean.obj, loc=(x + 0.004 - lo.x, y_front + dd / 2 - (lo.y + hi.y) / 2, z - lo.z))
        out.append(lean)
    return out


def package_box(p: Prop, size, center, cell: int, *, rot=(0, 0, 0), key: str = "pkg", side_cell: int | None = None) -> Part:
    """Printed carton: front/back faces = art cell, sides = a strip of the same art, top/bottom = kraft."""
    obj = G.box(p._name("pkg"), size, (0, 0, 0), bevel=0.0015)
    art = card_rect(cell)
    kraft = card_rect(14)
    strip = (art[0], art[1], art[0] + (art[2] - art[0]) * 0.18, art[3])

    def face_rect(poly):
        n = poly.normal
        if abs(n.y) > 0.9:
            return (*art, 0, 2, n.y > 0)
        if abs(n.x) > 0.9:
            return (*strip, 1, 2, False)
        if abs(n.z) > 0.9:
            return (*kraft, 0, 1, False)
        return (*kraft, 0, 2, False)

    set_face_uvs(obj, face_rect)
    G.xform(obj, rot=rot, loc=center)
    return p.add(obj, M.CARDBOARD, uv="keep", tags=("goods", key), wear=0.7)


def can(p: Prop, r: float, h: float, center, cell: int, *, segs: int = 10, rot=(0, 0, 0), key: str = "can",
        mat: str = M.CARDBOARD) -> Part:
    """Food / paint can: label (art cell wrapped around), tin lids."""
    obj = G.cyl(p._name("can"), r, h, (0, 0, 0), "Z", segs, None, 0.0, 1, True)
    art = card_rect(cell)
    lid = card_rect(15)
    me = obj.data
    uvl = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        if abs(poly.normal.z) > 0.9:
            for li in poly.loop_indices:
                co = me.vertices[me.loops[li].vertex_index].co
                uvl.data[li].uv = (lid[0] + (co.x / r * 0.5 + 0.5) * (lid[2] - lid[0]), lid[1] + (co.y / r * 0.5 + 0.5) * (lid[3] - lid[1]))
            continue
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            t = math.atan2(co.y, co.x) / (2 * math.pi) + 0.5
            u = 1.0 - abs(2.0 * t - 1.0)  # mirrored wrap: continuous all the way round, no atlas seam
            uvl.data[li].uv = (art[0] + u * (art[2] - art[0]), art[1] + (co.z / h + 0.5) * (art[3] - art[1]))
    G.xform(obj, rot=rot, loc=center)
    return p.add(obj, mat, uv="keep", tags=("goods", key), wear=0.8, edge_deg=40.0)


# ------------------------------------------------------------------------------------------------
# cloth
# ------------------------------------------------------------------------------------------------


def drape(p: Prop, x0: float, x1: float, y0: float, y1: float, top: float, mat: str, *, hang=(0.25, 0.25, 0.3, 0.0),
          res: float = 0.12, wrinkle: float = 0.02, seed: int = 0, thickness: float = 0.012, floor: float = 0.0,
          bulges=(), shift=(0.0, 0.0), uv_scale: float = 1.0, tags=("cloth",)) -> Part:
    """Cloth (quilt / blanket / sheet) lying on a box top [x0,x1]x[y0,y1] at height `top` and hanging
    down the sides. hang = (left, right, front(-Y), back(+Y)) overhang lengths. Wrinkles from noise;
    bulges = [(x, y, radius, height)] soft lumps (pillows / bodies under the cover). Solidified."""
    import bmesh
    from mathutils import Vector, noise
    hl, hr, hf, hb = hang
    ax0, ax1, ay0, ay1 = x0 - hl, x1 + hr, y0 - hf, y1 + hb
    nx = max(2, int((ax1 - ax0) / res))
    ny = max(2, int((ay1 - ay0) / res))
    noise.seed_set(seed % 9973 + 1)
    bm = bmesh.new()
    grid = []
    for i in range(nx + 1):
        col = []
        for j in range(ny + 1):
            u = ax0 + (ax1 - ax0) * i / nx + shift[0]
            v = ay0 + (ay1 - ay0) * j / ny + shift[1]
            cx, cy = min(max(u, x0), x1), min(max(v, y0), y1)
            dx, dy = u - cx, v - cy
            out = math.hypot(dx, dy)
            z = top
            px, py = cx, cy
            if out > 1e-6:
                # fold over the edge with a small radius, then hang straight down
                rr = 0.04
                if out < rr * math.pi / 2:
                    a = out / rr
                    horiz = rr * math.sin(a)
                    z = top - rr * (1 - math.cos(a))
                else:
                    horiz = rr
                    z = top - rr - (out - rr * math.pi / 2)
                px, py = cx + dx / out * horiz, cy + dy / out * horiz
                z = max(z, floor + 0.004)
            for bx, by, br, bh in bulges:
                d = math.hypot(px - bx, py - by)
                if d < br:
                    z += bh * (0.5 + 0.5 * math.cos(math.pi * d / br))
            q = Vector((px, py, z))
            w = noise.noise(q * 3.1 + Vector((0.0, 0.0, 0.7))) * wrinkle + noise.noise(q * 9.0 + Vector((0.0, 0.0, 2.3))) * wrinkle * 0.35
            if out > 0.04:
                # hanging cloth: folds ripple outward from the side it hangs down
                fold = noise.noise(Vector((px * 7.0 + py * 7.0, z * 1.5, 4.1))) * wrinkle * 1.6
                k = min(1.0, (out - 0.04) / 0.1)
                px += dx / out * (w + fold) * k
                py += dy / out * (w + fold) * k
                w *= 1.0 - k
            col.append(bm.verts.new((px, py, z + w + thickness * 0.5)))
        grid.append(col)
    for i in range(nx):
        for j in range(ny):
            bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
    bm.verts.index_update()
    uvl = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        for loop in f.loops:
            # UV from the flat (unfolded) grid position: the pattern follows the cloth
            vi = loop.vert.index
            gi, gj = divmod(vi, ny + 1)
            loop[uvl].uv = ((ax0 + (ax1 - ax0) * gi / nx) * uv_scale, (ay0 + (ay1 - ay0) * gj / ny) * uv_scale)
    if thickness > 0:
        bmesh.ops.solidify(bm, geom=list(bm.faces), thickness=thickness)
    obj = G._obj(p._name("cloth"), bm)
    return p.add(obj, mat, uv="keep", tags=tags, edge_deg=50, wear=0.4)


# ------------------------------------------------------------------------------------------------
# shared shapes: rounded rectangles, upholstery damage, feet
# ------------------------------------------------------------------------------------------------


def rounded_rect(w: float, d: float, r: float, n: int = 4) -> list[tuple[float, float]]:
    """CCW outline of a w x d rectangle with corner radius r (n segments per corner)."""
    pts = []
    for cx, cy, a0 in ((w / 2 - r, -d / 2 + r, -90), (w / 2 - r, d / 2 - r, 0), (-w / 2 + r, d / 2 - r, 90),
                       (-w / 2 + r, -d / 2 + r, 180)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def slash(p: Prop, c, length: float, ang: float, up=(0, 0, 1), key: str = "slash") -> Part:
    """Knife slash with foam bulging out: an elongated wrinkled foam bead on a cushion surface.
    up=(0,0,1): lying on a top surface; otherwise on a front (-Y facing) surface."""
    r = p.rng(key)
    bead = p.rbox((length, 0.065, 0.045), (0, 0, 0), M.FOAM, radius=0.02, inner=(3, 1, 1), wrinkle=0.012,
                  wrinkle_scale=24.0, seed=r.randrange(9999), tags=("foam",), bulge=(0, 0.015, 0.012), taper_top=0.25)
    if tuple(up) == (0, 0, 1):
        G.xform(bead.obj, rot=(0, 0, ang), loc=c)
    else:
        G.xform(bead.obj, rot=(90, 0, 0))
        G.xform(bead.obj, rot=(0, ang, 0), loc=c)
    return bead


def stuffing(p: Prop, c, s: float, key: str) -> Part:
    """Loose tuft of foam / stuffing (debris)."""
    r = p.rng(key)
    return p.rbox((s, s * 0.8, s * 0.6), c, M.FOAM, radius=s * 0.3, inner=(1, 1, 1), wrinkle=s * 0.25, wrinkle_scale=25.0,
                  seed=r.randrange(9999), tags=("foam", "debris"))


def bun_foot(p: Prop, x: float, y: float, h: float = 0.1, mat: str = M.DARK, key: str = "foot") -> Part:
    return p.lathe([(0.026, 0.0), (0.03, 0.2 * h), (0.034, 0.5 * h), (0.03, 0.8 * h), (0.032, h)], (x, y, 0.0), mat,
                   segs=10, tags=("leg", key))
