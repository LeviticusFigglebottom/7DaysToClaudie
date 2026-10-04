"""Interior props - bedroom: double / single beds with rumpled bedding, bare stained mattress, nightstand,
six-drawer dresser, wardrobe, crib (empty), small student desk, ladder-back wooden chair.

params: prop (id), seed, variants, mount, budget (see blender_catalogs/props_interior.py).
"""
from __future__ import annotations

import math

from lib import props_int_core as core
from lib import props_int_furn as F
from lib import props_int_mesh as G
from lib.props_int_core import M, Prop

T_FRONT = 0.019


def _arch_poly(w: float, h: float, arch: float, n: int = 8):
    """Panel outline (XZ, CCW, bottom edge at z=0) with an arched top."""
    pts = [(-w / 2, 0.0), (w / 2, 0.0)]
    for i in range(n + 1):
        t = i / n
        pts.append((w / 2 - w * t, h + arch * math.sin(math.pi * t)))
    return pts


def _finial(p: Prop, x: float, y: float, z: float, mat: str, r: float = 0.03) -> core.Part:
    return p.lathe([(r * 0.6, 0.0), (r, 0.02), (r * 0.9, 0.04), (r * 0.45, 0.055), (r * 0.7, 0.07), (0.0, 0.085)],
                   (x, y, z), mat, segs=8, tags=("knob",))


# ------------------------------------------------------------------------------------------------
# beds
# ------------------------------------------------------------------------------------------------


def _bed(p: Prop, W: float, L: float, wood: str, *, head_h: float = 1.05, foot_h: float = 0.62, pillows: int = 2,
         quilt: str = M.QUILT) -> dict:
    """Bed frame (headboard at +Y, foot toward -Y), box spring, mattress and bedding. Mattress top 0.63."""
    post = 0.065
    fw = W + 0.1
    hy, fy = L / 2 + 0.045, -L / 2 - 0.045
    parts: dict = {"posts": []}
    for sx in (-1, 1):
        for yy, hh, key in ((hy, head_h, "head"), (fy, foot_h, "foot")):
            parts["posts"].append(p.box((post, post, hh), (sx * (fw / 2 - post / 2), yy, hh / 2), wood, bevel=0.006,
                                        grain="Z", tags=("post", key)))
            _finial(p, sx * (fw / 2 - post / 2), yy, hh, wood)
    iw = fw - 2 * post
    head = p.prism(_arch_poly(iw, 0.42, 0.12), 0.032, wood, plane="XZ", offset=-0.016, bevel=0.004, grain="X",
                   tags=("headboard",))
    G.xform(head.obj, loc=(0, hy, 0.5))
    parts["head"] = head
    p.box((iw, 0.045, 0.09), (0, hy, 0.455), wood, bevel=0.004, grain="X")
    foot = p.panel(iw, 0.3, 0.03, (0, fy, 0.27 + 0.15), wood, style="raised", frame=0.05, tags=("footboard",))
    parts["foot"] = foot
    parts["rails"] = []
    for sx in (-1, 1):
        parts["rails"].append(p.box((0.035, L + 0.02, 0.15), (sx * (W / 2 + 0.03), 0, 0.29), wood, bevel=0.003, grain="Y",
                                    tags=("rail",)))
    parts["spring"] = p.rbox((W, L, 0.18), (0, 0, 0.25 + 0.09), M.LINEN, radius=0.02, inner=(3, 4, 1), edge_deg=40)
    return parts


def _bedding(p: Prop, W: float, L: float, *, pillows: int, quilt: str, top: float = 0.63) -> dict:
    out: dict = {}
    wr = {"clean": 0.018, "worn": 0.028, "destroyed": 0.035}[p.cond]
    r = p.rng("bedding")
    shift = (0.0, 0.0) if p.cond == "clean" else (p.vrng("quilt").uniform(-0.12, 0.12), p.vrng("quilt2").uniform(0.0, 0.08))
    lumps = [(r.uniform(-W / 3, W / 3), r.uniform(-L / 2.5, L / 6), r.uniform(0.15, 0.32), r.uniform(0.03, 0.07)) for _ in range(5)]
    y1 = L / 2 - 0.55
    out["sheet"] = F.drape(p, -W / 2, W / 2, y1 - 0.2, L / 2, top + 0.003, M.LINEN, hang=(0.14, 0.14, 0.0, 0.02),
                           res=0.14, wrinkle=wr * 0.5, seed=p.seed + 1, thickness=0.006)
    out["quilt"] = F.drape(p, -W / 2, W / 2, -L / 2, y1, top + 0.012, quilt, hang=(0.3, 0.3, 0.26, 0.0), res=0.135,
                           wrinkle=wr, seed=p.seed + 2, thickness=0.014, bulges=lumps, shift=shift, uv_scale=1.0)
    roll = p.rbox((W + 0.06, 0.13, 0.05), (shift[0], y1 + 0.02 + shift[1], top + 0.04), quilt, radius=0.024,
                  inner=(6, 1, 1), wrinkle=wr * 0.5, seed=p.seed + 3, tags=("cloth",))
    out["roll"] = roll
    out["pillows"] = []
    for i in range(pillows):
        px = 0.0 if pillows == 1 else (-W / 4 if i == 0 else W / 4)
        pil = p.rbox((min(0.62, W - 0.08), 0.4, 0.13), (0, 0, 0), M.LINEN, radius=0.06, inner=(3, 2, 1), bulge=(0.01, 0.01, 0.03),
                     wrinkle=wr * 0.4, seed=p.seed + 10 + i, tags=("cushion",))
        tilt = 0.0 if p.cond == "clean" else p.vrng(f"pil{i}").uniform(-12, 12)
        G.xform(pil.obj, rot=(-8, 0, tilt), loc=(px, L / 2 - 0.26, top + 0.075))
        out["pillows"].append(pil)
    return out


def _bed_prop(p: Prop, W: float, L: float, wood: str, pillows: int, quilt: str, head_h: float, foot_h: float) -> None:
    fr = _bed(p, W, L, wood, head_h=head_h, foot_h=foot_h, pillows=pillows, quilt=quilt)
    top = 0.63
    sag = 0.0 if p.cond == "clean" else 0.025
    if p.destroyed:
        sag = 0.07
    mat = p.rbox((W, L, 0.2), (0, 0, 0.43 + 0.1), M.TICKING, radius=0.05, inner=(3, 5, 1), sag=sag, sag_at=(0.05, -0.1),
                 sag_r=0.5, bulge=(0.01, 0.01, 0.01), uv_scale=1.0, edge_deg=40)
    if not p.destroyed:
        _bedding(p, W, L, pillows=pillows, quilt=quilt, top=top)
    else:
        r = p.vrng("wreck")
        for i in range(3):
            F.slash(p, (r.uniform(-W / 3, W / 3), r.uniform(-L / 3, L / 3), top - sag * 0.6 + 0.004), r.uniform(0.2, 0.4),
                  r.uniform(0, 180), key=f"mslash{i}")
        # quilt dragged onto the floor in a crumpled heap, one pillow beside it
        F.drape(p, W / 2 + 0.15, W / 2 + 0.75, -0.6, 0.3, 0.09, quilt, hang=(0.12, 0.12, 0.12, 0.12), res=0.1,
                wrinkle=0.045, seed=p.seed + 5, thickness=0.014, bulges=[(W / 2 + 0.45, -0.2, 0.25, 0.08)])
        pil = p.rbox((0.6, 0.4, 0.13), (0, 0, 0), M.LINEN, radius=0.06, inner=(3, 2, 1), bulge=(0.01, 0.01, 0.03),
                     wrinkle=0.01, seed=p.seed + 6, tags=("cushion",))
        p.lay_on_floor([pil], rot=(0, 0, 0), at=(W / 2 + 0.5, 0.65), yaw=r.uniform(0, 60))
        # footboard kicked in: split, one half on the floor
        p.remove([fr["foot"]])
        iw = W + 0.1 - 0.13
        h1, h2 = F.split_panel(p, iw, 0.3, 0.03, (0, -L / 2 - 0.045, 0.42), wood, (-0.1, -0.15), (0.12, 0.15), plane="XZ",
                               key="foot", teeth=6, amp=0.03)
        p.lay_on_floor([h2], rot=(-80, 0, 0), at=(0.25, -L / 2 - 0.45), yaw=r.uniform(-20, 20))
        # side rail cracked: mattress corner dropped toward the floor
        mat_parts = [mat, fr["spring"]] + [q for q in p.parts if "foam" in q.tags and p.bounds([q])[0].z > 0.4]
        p.settle(mat_parts, pivot=(-W / 2, 0, 0.25), axis=(0, -1, 0), max_deg=7, floor=0.06)
        p.rotate([fr["rails"][1]], rot=(-6, 0, 0), pivot=(W / 2 + 0.03, L / 2, 0.36))


def bed_double(p: Prop) -> None:
    """Oak double bed (1.37 x 1.9 mattress), arched headboard, patchwork quilt, two pillows."""
    W, L = 1.37, 1.9
    _bed_prop(p, W, L, M.OAK, 2, M.QUILT, 1.08, 0.64)
    p.collider((0, 0, 0.33), (W + 0.1, L + 0.16, 0.66))
    p.collider((0, L / 2 + 0.045, 0.55), (W + 0.1, 0.07, 1.1))


def bed_single(p: Prop) -> None:
    """White-painted twin bed (0.99 x 1.9 mattress), one pillow, quilt."""
    W, L = 0.99, 1.9
    _bed_prop(p, W, L, M.PAINT_WHITE, 1, M.QUILT, 0.95, 0.6)
    p.collider((0, 0, 0.33), (W + 0.1, L + 0.16, 0.66))
    p.collider((0, L / 2 + 0.045, 0.5), (W + 0.1, 0.07, 1.0))


def mattress_dirty(p: Prop) -> None:
    """Bare double mattress dumped on the floor: stained ticking, tufting, sagging; worn = torn with foam."""
    W, L, T = 1.37, 1.9, 0.2
    sag = 0.03 if p.cond == "clean" else 0.05
    p.rbox((W, L, T), (0, 0, T / 2), M.TICKING, radius=0.06, inner=(4, 6, 1), sag=sag, sag_at=(0.1, 0.0), sag_r=0.6,
           bulge=(0.015, 0.015, 0.02), wrinkle=0.006, seed=p.seed, edge_deg=40)
    for i in range(3):
        for j in range(5):
            x, y = -W / 2 + W * (i + 1) / 4, -L / 2 + L * (j + 1) / 6
            p.cyl(0.012, 0.006, (x, y, T + 0.0 - sag * math.exp(-((x - 0.1) ** 2 + y ** 2) / 0.36) * 0.9), M.LINEN, segs=6)
    if p.worn:
        F.slash(p, (-W / 2 + 0.25, L / 2 - 0.3, T - 0.005), 0.35, 30, key="tear1")
        F.slash(p, (0.3, -0.4, T - 0.03), 0.25, -70, key="tear2")
        F.stuffing(p, (-W / 2 - 0.12, L / 2 - 0.1, 0.03), 0.1, key="tuft")
    p.collider((0, 0, T / 2), (W, L, T))


# ------------------------------------------------------------------------------------------------
# case goods
# ------------------------------------------------------------------------------------------------


def _top(p: Prop, w: float, d: float, t: float, z: float, mat: str, y: float = 0.0) -> core.Part:
    part = p.prism(F.rounded_rect(w, d, 0.012, 2), t, mat, plane="XY", offset=z, bevel=0.004, grain="X")
    G.xform(part.obj, loc=(0, y, 0))
    return part


def _bracket_feet(p: Prop, w: float, d: float, h: float, mat: str, y: float = 0.0) -> list:
    out = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            # ogee bracket profile seen from the front; outer edge flush with the case corner
            prof = [(0.0, 0.0), (0.0, h), (-0.07, h), (-0.07, h * 0.7), (-0.03, h * 0.45), (-0.02, 0.0)]
            prof = [(-x * sx, z) for x, z in prof] if sx < 0 else prof
            if sx < 0:
                prof = list(reversed(prof))
            ft = p.prism(prof, 0.06, mat, plane="XZ", offset=-0.03, bevel=0.002, tags=("leg",))
            G.xform(ft.obj, loc=(sx * (w / 2), y + sy * (d / 2 - 0.03), 0.0))
            out.append(ft)
    return out


def nightstand(p: Prop) -> None:
    """Oak nightstand 0.5 x 0.4 x 0.62: drawer over a door, bun feet."""
    W, D, H = 0.5, 0.4, 0.62
    yf = -D / 2 + 0.02
    F.carcass(p, W, yf, D / 2, 0.08, H - 0.025, M.OAK, top=False, rails=((0.415, 0.03),))
    _top(p, W + 0.02, D + 0.02, 0.025, H - 0.025, M.OAK)
    for sx in (-1, 1):
        for sy in (-1, 1):
            F.bun_foot(p, sx * (W / 2 - 0.05), sy * (D / 2 - 0.06), h=0.08, mat=M.OAK, key=f"f{sx}{sy}")
    pull = 0.0 if p.cond == "clean" else p.vrng("drw").choice([0.0, 0.05, 0.12])
    ang = 0.0 if p.cond == "clean" else p.vrng("door").choice([0.0, 10.0, 35.0])
    drw = F.drawer(p, -W / 2 + 0.015, 0.435, W / 2 - 0.015, H - 0.035, yf - T_FRONT, D - 0.08, M.OAK,
                   pull=0.18 if p.destroyed else pull, key="drawer", frame=0.03)
    door = F.door(p, -W / 2 + 0.015, 0.095, W / 2 - 0.015, 0.4, yf - T_FRONT, M.OAK, hinge="left", open_deg=ang,
                  key="door", handle_at="top")
    if p.worn and not p.destroyed:
        # alarm clock, paperback, glass
        p.rbox((0.14, 0.07, 0.08), (-0.1, 0.02, H + 0.04), M.PL_BROWN, radius=0.01, inner=(2, 1, 1), edge_deg=30)
        p.box((0.08, 0.004, 0.035), (-0.1, -0.016, H + 0.045), M.GLASS, bevel=0.0)
        F.book(p, (0.03, 0.12, 0.18), (0.12, 0.05, H + 0.015), 5, paperback=True, rot=(0, 90, 20))
        p.lathe([(0.03, 0.0), (0.034, 0.11), (0.031, 0.11), (0.027, 0.005), (0.0, 0.005)], (0.15, -0.1, H), M.GLASS,
                segs=10, cap_top=False)
    if p.destroyed:
        r = p.vrng("wreck")
        p.lay_on_floor(drw, rot=(r.uniform(-10, 10), 180, 0), at=(0.35, -0.55), yaw=r.uniform(-40, 40))
        F.hang(p, door, -W / 2 + 0.015, yf, 0.36, open_deg=r.uniform(80, 110), sag_deg=9, hinge="left")
    p.collider((0, 0, H / 2), (W + 0.02, D + 0.02, H))


def dresser(p: Prop) -> None:
    """Oak six-drawer dresser 1.3 x 0.48 x 0.84 with brass bail pulls and bracket feet."""
    W, D, H = 1.3, 0.48, 0.84
    yf = -D / 2 + 0.02
    z0, z1 = 0.09, H - 0.03
    rows = 3
    rh = (z1 - z0) / rows
    rails = tuple((z0 + rh * i, 0.025) for i in range(1, rows))
    F.carcass(p, W, yf, D / 2, z0, z1, M.OAK, top=False, rails=rails)
    p.box((0.03, 0.02, z1 - z0), (0, yf + 0.01, (z0 + z1) / 2), M.OAK, bevel=0.002, grain="Z")
    _top(p, W + 0.03, D + 0.025, 0.03, H - 0.03, M.OAK)
    p.box((W - 0.02, 0.03, 0.06), (0, yf + 0.0, z0 - 0.02), M.OAK, bevel=0.003, grain="X")
    _bracket_feet(p, W - 0.02, D - 0.04, 0.07, M.OAK)
    drawers = []
    for row in range(rows):
        for col in range(2):
            x0 = -W / 2 + 0.035 if col == 0 else 0.017
            x1 = -0.017 if col == 0 else W / 2 - 0.035
            za, zb = z0 + rh * row + 0.016, z0 + rh * (row + 1) - 0.016
            k = f"d{row}{col}"
            pull = 0.0
            if p.cond == "worn":
                pull = p.vrng(k).choice([0.0, 0.0, 0.03, 0.08])
            if p.destroyed:
                pull = p.vrng(k).choice([0.0, 0.15, 0.3])
            drawers.append(F.drawer(p, x0, za, x1, zb, yf - T_FRONT, D - 0.06, M.OAK, pull=pull, key=k, handle="bar",
                                    knobs=1, frame=0.03))
    if p.worn and not p.destroyed:
        p.rbox((0.28, 0.18, 0.1), (-0.38, 0.05, H + 0.05), M.DARK, radius=0.008, inner=(2, 1, 1), edge_deg=25)  # jewelry box
        frame = p.box((0.18, 0.015, 0.23), (0, 0, 0), M.DARK, bevel=0.004)
        G.xform(frame.obj, rot=(-12, 0, 8), loc=(0.3, 0.12, H + 0.115))
        F.drape(p, 0.05, 0.25, -0.12, 0.08, H + 0.002, M.LINEN, hang=(0.04, 0.04, 0.12, 0.0), res=0.06, wrinkle=0.01,
                seed=p.seed, thickness=0.004)
    if p.destroyed:
        r = p.vrng("wreck")
        dump = drawers[2]
        p.lay_on_floor(dump, rot=(r.uniform(-12, 12), 180, 0), at=(-0.35, -0.75), yaw=r.uniform(-30, 30))
        tip = drawers[5]
        lo, hi = p.bounds(tip)
        p.rotate(tip, rot=(-22, 0, 4), pivot=(0, yf, lo.z))
        for i in range(3):  # clothes spilling
            F.drape(p, -0.3 + i * 0.25, -0.1 + i * 0.25, -0.9 - i * 0.1, -0.6 - i * 0.1, 0.06, [M.LINEN, M.TOWEL, M.BROWN][i],
                    hang=(0.08, 0.08, 0.08, 0.08), res=0.07, wrinkle=0.03, seed=p.seed + i, thickness=0.008)
    p.collider((0, 0, H / 2), (W + 0.03, D + 0.025, H))


def wardrobe(p: Prop) -> None:
    """Oak wardrobe 1.0 x 0.6 x 1.95: two tall raised-panel doors, bottom drawer, crown; rod with clothes."""
    W, D, H = 1.0, 0.6, 1.95
    yf = -D / 2 + 0.02
    z0, z1 = 0.08, H - 0.07
    F.carcass(p, W, yf, D / 2, z0, z1, M.OAK, rails=((0.36, 0.03),))
    p.box((W + 0.06, D + 0.04, 0.05), (0, 0.0, H - 0.045), M.OAK, bevel=0.006, grain="X")
    p.box((W + 0.03, D + 0.02, 0.03), (0, 0.0, H - 0.085), M.OAK, bevel=0.004, grain="X")
    p.box((W, 0.03, z0), (0, yf + 0.0, z0 / 2), M.OAK, bevel=0.003, grain="X")
    p.box((W - 0.06, D - 0.06, 0.018), (0, 0.02, 0.38), M.PARTICLE, bevel=0.001)
    p.cyl(0.012, W - 0.05, (0, 0.04, 1.65), M.CHROME, axis="X", segs=8)
    r = p.rng("clothes")
    cols = [M.LINEN, M.TOWEL, M.BROWN, M.FLORAL, M.TAN, M.VINYL_BLACK]
    x = -W / 2 + 0.22
    while x < W / 2 - 0.2:
        ln = r.uniform(0.6, 1.05)
        p.tube([(x - 0.16, 0.04, 1.58), (x, 0.04, 1.63), (x + 0.16, 0.04, 1.58)], 0.003, M.CHROME, segs=4)
        p.rbox((0.36, 0.045, ln), (x, 0.04, 1.6 - ln / 2), cols[r.randrange(len(cols))], radius=0.02, inner=(2, 1, 3),
               taper_top=0.15, wrinkle=0.006, seed=r.randrange(999), tags=("cloth",))
        x += r.uniform(0.07, 0.12)
    dz0, dz1 = 0.39, z1 - 0.015
    open_l = open_r = 0.0
    if p.cond == "worn":
        open_l = p.vrng("dl").choice([0.0, 6.0, 20.0])
        open_r = p.vrng("dr").choice([0.0, 12.0, 40.0])
    left = F.door(p, -W / 2 + 0.03, dz0, -0.005, dz1, yf - T_FRONT, M.OAK, hinge="left", open_deg=open_l, key="dl",
                  handle_at="mid", frame=0.07)
    right = F.door(p, 0.005, dz0, W / 2 - 0.03, dz1, yf - T_FRONT, M.OAK, hinge="right", open_deg=open_r, key="dr",
                   handle_at="mid", frame=0.07)
    pull = 0.0 if p.cond == "clean" else p.vrng("drw").choice([0.0, 0.06])
    F.drawer(p, -W / 2 + 0.03, 0.1, W / 2 - 0.03, 0.34, yf - T_FRONT, D - 0.08, M.OAK, pull=pull, knobs=2, key="drw",
                   frame=0.04)
    if p.destroyed:
        rr = p.vrng("wreck")
        F.lay_flat(p, left, at=(-0.45, -1.15), yaw=rr.uniform(-20, 20))
        F.hang(p, right, W / 2 - 0.03, yf, dz1 - 0.1, open_deg=rr.uniform(95, 120), sag_deg=10, hinge="right")
        for i in range(3):
            F.drape(p, -0.3 + i * 0.22, -0.05 + i * 0.22, -0.75 - i * 0.12, -0.45 - i * 0.12, 0.05,
                    [M.LINEN, M.FLORAL, M.TOWEL][i], hang=(0.08, 0.08, 0.08, 0.08), res=0.1, wrinkle=0.03,
                    seed=p.seed + i, thickness=0.008)
    p.collider((0, 0, H / 2), (W + 0.06, D + 0.04, H))


def crib(p: Prop) -> None:
    """White-painted crib 0.76 x 1.38 x 0.98 with spindle sides; an empty, rumpled little blanket."""
    W, L, H = 0.76, 1.38, 0.98
    wood = M.PAINT_WHITE
    post = 0.05
    posts = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            posts.append(p.box((post, post, H), (sx * (W / 2 - post / 2), sy * (L / 2 - post / 2), H / 2), wood, bevel=0.005,
                               grain="Z", tags=("post",)))
            _finial(p, sx * (W / 2 - post / 2), sy * (L / 2 - post / 2), H, wood, r=0.024)
    rails = {}
    spindles = {}
    for sx in (-1, 1):
        rails[sx] = [p.box((0.035, L - 2 * post, 0.045), (sx * (W / 2 - post / 2), 0, z), wood, bevel=0.004, grain="Y",
                           tags=("rail",)) for z in (0.3, H - 0.06)]
        sp = []
        n = 17
        for i in range(n):
            y = -L / 2 + post + (L - 2 * post) * (i + 0.5) / n
            sp.append(p.cyl(0.011, H - 0.06 - 0.3 - 0.045, (sx * (W / 2 - post / 2), y, (0.3 + H - 0.06) / 2), wood,
                            segs=6, cap=False, tags=("spindle",)))
        spindles[sx] = sp
    for sy in (-1, 1):
        p.panel(W - 2 * post, 0.5, 0.02, (0, sy * (L / 2 - post / 2), 0.33 + 0.25), wood, style="raised", frame=0.05,
                tags=("panel",))
        p.box((W - 2 * post, 0.03, 0.06), (0, sy * (L / 2 - post / 2), H - 0.06), wood, bevel=0.004, grain="X")
    p.box((W - 2 * post, L - 2 * post, 0.03), (0, 0, 0.3), M.WOOD_RAW, bevel=0.0)
    mz = 0.315
    mat_parts = [p.rbox((W - 2 * post - 0.01, L - 2 * post - 0.01, 0.1), (0, 0, mz + 0.05), M.LINEN, radius=0.025,
                        inner=(2, 4, 1), wrinkle=0.003, seed=p.seed, edge_deg=40)]
    mat_parts.append(F.drape(p, -0.22, 0.12, -0.35, 0.05, mz + 0.105, M.TOWEL, hang=(0.05, 0.05, 0.05, 0.05), res=0.06,
                             wrinkle=0.025, seed=p.seed + 3, thickness=0.008, bulges=[(-0.05, -0.15, 0.12, 0.03)]))
    if p.destroyed:
        r = p.vrng("wreck")
        # +X side smashed in: upper rail snapped, spindles broken or gone
        top_rail = rails[1][1]
        p.remove([top_rail])
        for i, sp in enumerate(spindles[1]):
            k = r.random()
            if k < 0.3:
                p.remove([sp])
            elif k < 0.75:
                F.break_off(p, sp, r.uniform(0.38, 0.75), jag=0.015, key=f"sp{i}", keep_piece=False)
        a = p.box((0.035, 0.6, 0.045), (0, 0, 0), wood, bevel=0.004, grain="Y", tags=("debris",))
        b = p.box((0.035, 0.55, 0.045), (0, 0, 0), wood, bevel=0.004, grain="Y", tags=("debris",))
        p.lay_on_floor([a], at=(W / 2 + 0.3, -0.2), yaw=r.uniform(-30, 30))
        p.lay_on_floor([b], at=(W / 2 + 0.45, 0.35), yaw=r.uniform(-60, 60))
        for i in range(4):
            s = p.cyl(0.011, r.uniform(0.15, 0.35), (0, 0, 0), wood, segs=6, cap=True, tags=("debris",))
            p.lay_on_floor([s], rot=(90, 0, 0), at=(W / 2 + r.uniform(0.1, 0.6), r.uniform(-0.6, 0.6)), yaw=r.uniform(0, 180))
        # mattress slid toward the broken side
        p.settle(mat_parts, pivot=(-W / 2, 0, mz), axis=(0, -1, 0), max_deg=9, floor=0.2)
    p.collider((0, 0, H / 2), (W, L, H))


def desk_small(p: Prop) -> None:
    """Woodgrain-laminate student desk 1.0 x 0.55 x 0.75: left pedestal with two drawers, panel leg."""
    W, D, H = 1.0, 0.55, 0.75
    lam = M.LAM_WOOD
    yf = -D / 2 + 0.02
    p.box((W, D, 0.025), (0, 0, H - 0.0125), lam, bevel=0.004, grain="X")
    pw = 0.4
    px = -W / 2 + pw / 2
    car = F.carcass(p, pw, yf, D / 2 - 0.01, 0.02, H - 0.025, lam, top=False, frame=False, inner=lam)
    p.box((pw, 0.02, 0.02), (px + 0.0, yf + 0.01, 0.01), lam, bevel=0.0)
    for part in car.values():
        if isinstance(part, core.Part):
            G.xform(part.obj, loc=(px, 0, 0))
    leg = p.box((0.022, D - 0.04, H - 0.025), (W / 2 - 0.02, 0, (H - 0.025) / 2), lam, bevel=0.003, grain="Z",
                tags=("leg",))
    p.box((W - pw - 0.03, 0.015, 0.38), (px + pw / 2 + (W - pw - 0.03) / 2, D / 2 - 0.03, H - 0.025 - 0.19), lam,
                    bevel=0.002, grain="X")
    drw = []
    for i, (za, zb) in enumerate(((0.38, 0.7), (0.05, 0.36))):
        pull = 0.0 if p.cond == "clean" else p.vrng(f"d{i}").choice([0.0, 0.04, 0.1])
        drw.append(F.drawer(p, px - pw / 2 + 0.005, za, px + pw / 2 - 0.005, zb, yf - T_FRONT + 0.0, D - 0.08, lam,
                            pull=pull, handle="bar", key=f"d{i}", style="slab"))
    F.drawer(p, px + pw / 2 + 0.03, H - 0.09, W / 2 - 0.05, H - 0.03, yf - T_FRONT, D - 0.1, lam, pull=0.0,
                      handle="cup", key="pencil", style="slab")
    if p.worn and not p.destroyed:
        r = p.rng("desk")
        for i in range(4):
            sh = p.box((0.215, 0.28, 0.001), (0, 0, 0), M.PAPER, bevel=0.0, uv="keep")
            core.set_face_uvs(sh.obj, lambda poly, c=i % 4: (*core.note_rect(c), 0, 1, False))
            G.xform(sh.obj, rot=(0, 0, r.uniform(-25, 25)), loc=(0.15 + r.uniform(-0.1, 0.1), -0.05 + r.uniform(-0.05, 0.05),
                                                                H + 0.001 + i * 0.0012))
        F.book(p, (0.035, 0.17, 0.24), (-0.3, 0.1, H + 0.0175), 7, rot=(0, 90, 10))
        F.book(p, (0.03, 0.16, 0.23), (-0.31, 0.1, H + 0.05), 12, rot=(0, 90, -5))
        p.lathe([(0.035, 0.0), (0.035, 0.1), (0.032, 0.1), (0.032, 0.004), (0.0, 0.004)], (0.38, 0.15, H), M.PL_RED,
                segs=10, cap_top=False)
        for i in range(3):
            pn = p.cyl(0.004, 0.17, (0, 0, 0), [M.PL_BLUE, M.PL_BLACK, M.LAM_WOOD][i], segs=6)
            G.xform(pn.obj, rot=(r.uniform(-12, 12), r.uniform(-12, 12), 0), loc=(0.38 + r.uniform(-0.01, 0.01), 0.15, H + 0.09))
    if p.destroyed:
        r = p.vrng("wreck")
        p.lay_on_floor(drw[0], rot=(0, 180, r.uniform(-20, 20)), at=(-0.1, -0.7), yaw=r.uniform(-30, 30))
        # panel leg kicked out: the free end of the desk drops to the floor
        p.lay_on_floor([leg], rot=(0, 90, 0), at=(W / 2 + 0.25, -0.15), yaw=r.uniform(-25, 25))
        body = [q for q in p.parts if "debris" not in q.tags and q is not leg and q not in drw[0]]
        p.settle(body, pivot=(-W / 2 + pw, 0, 0.0), axis=(0, 1, 0), max_deg=45)
    p.collider((0, 0, H / 2), (W, D, H))


def chair_wood(p: Prop) -> None:
    """Dark-wood ladder-back dining chair: seat at 0.46, three curved back slats, box stretchers."""
    sh = 0.46
    wood = M.DARK
    p.rbox((0.43, 0.41, 0.03), (0, -0.01, sh - 0.015), wood, radius=0.008, inner=(2, 2, 1), sag=0.008, sag_r=0.15,
           edge_deg=25, grain="X")
    legs = []
    for sx in (-1, 1):
        legs.append(F.tapered_leg(p, sx * 0.18, -0.17, 0.0, sh - 0.03, 0.036, 0.028, wood, key=f"front{sx}"))
    posts = []
    for sx in (-1, 1):
        post = p.box((0.034, 0.034, 0.98), (sx * 0.18, 0.17, 0.49), wood, bevel=0.004, grain="Z", tags=("leg", f"back{sx}"))
        G.xform(post.obj, rot=(-5, 0, 0), pivot=(sx * 0.18, 0.17, sh))
        posts.append(post)
    for sx in (-1, 1):
        p.box((0.02, 0.32, 0.06), (sx * 0.18, 0.0, sh - 0.06), wood, bevel=0.002, grain="Y")
        p.box((0.018, 0.32, 0.025), (sx * 0.18, 0.0, 0.16), wood, bevel=0.002, grain="Y", tags=("stretcher",))
    p.box((0.34, 0.02, 0.06), (0, -0.17, sh - 0.06), wood, bevel=0.002, grain="X")
    p.box((0.34, 0.018, 0.025), (0, 0.0, 0.2), wood, bevel=0.002, grain="X", tags=("stretcher",))
    slats = []
    for i, z in enumerate((0.62, 0.75, 0.88)):
        sl = p.rbox((0.34, 0.016, 0.06), (0, 0.17 + (z - sh) * 0.087, z), wood, radius=0.006, inner=(4, 1, 1),
                    bulge=(0, 0.02, 0), edge_deg=25, grain="X", tags=("slat",))
        G.xform(sl.obj, rot=(-5, 0, 0), pivot=(0, 0.17 + (z - sh) * 0.087, z))
        slats.append(sl)
    if p.destroyed:
        r = p.vrng("wreck")
        F.break_off(p, legs[0], 0.18, jag=0.02, key="lb", keep_piece=True, piece_at=(0.55, -0.4), piece_yaw=r.uniform(0, 180))
        p.remove([slats[1]])
        whole = [q for q in p.parts if "debris" not in q.tags]
        # knocked over backwards: lying on its back posts
        p.rotate(whole, rot=(-80, 0, 0), pivot=(0, 0.2, 0))
        lo, hi = p.bounds(whole)
        p.move(whole, (0, 0, -lo.z))
        p.rotate(whole, rot=(0, 0, r.uniform(-25, 25)), pivot=(0, 0.4, 0))
        s = p.rbox((0.34, 0.016, 0.06), (0, 0, 0), wood, radius=0.006, inner=(4, 1, 1), bulge=(0, 0.02, 0), edge_deg=25,
                   grain="X", tags=("debris",))
        p.lay_on_floor([s], rot=(90, 0, 0), at=(-0.5, -0.3), yaw=r.uniform(0, 90))
        p.collider((0, 0.45, 0.22), (0.5, 1.0, 0.44))
    else:
        p.collider((0, 0.02, 0.49), (0.45, 0.48, 0.98))


BUILDERS = {
    "bed_double": bed_double,
    "bed_single": bed_single,
    "mattress_dirty": mattress_dirty,
    "nightstand": nightstand,
    "dresser": dresser,
    "wardrobe": wardrobe,
    "crib": crib,
    "desk_small": desk_small,
    "chair_wood": chair_wood,
}


def build(params: dict, outputs: list[str]) -> None:
    core.build_variants(params, outputs, BUILDERS[params["prop"]])
