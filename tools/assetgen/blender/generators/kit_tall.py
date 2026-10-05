"""POI kit pieces for tall rooms (ADR-0021, docs/POI_KIT.md): the storey band between stacked wall
pieces, two-storey (5.8 m) wall pieces with a tall window, a pointed lancet or tall double doors, and
the panes, board-ups and tall barn door leaves that fill them.

Same contract as kit_wall / kit_window / kit_boards / kit_door: Blender space (Z up, front = -Y),
walls along X centred on y = 0 (0.16 thick) standing on z = 0, side A = -Y, side B = +Y in UVSide.

params: kind, name, seed, plus
  band:      the 1 m storey band, z 2.8 .. 3.0 (finish faces both sides, like a wall).
  wall_tall: length (1 | 2), opening ("window_tall" | "door_2m_tall"): kit_wall's wall body and
             casings on a 5.8 m piece.
  lancet:    1 m x 5.8 m wall with a pointed-arch window: clear 0.66 wide from a sill at 1.0, straight
             jambs to 3.45, an equilateral arch to 4.02; linings, casings that follow the arch, a stool.
  glass:     target ("window_tall" | "lancet"), broken. Origin = bottom centre of the clear opening.
             window_tall: 6-over-6 double-hung. lancet: a glazed sash with a centre bar and four
             cross bars; broken = shards in the lower lites, the arch knocked out.
  boards:    target ("window_tall" | "lancet"): planks nailed across on the side A casing face.
  barn_door: broken. Board-and-batten leaf 0.89 x 3.45 (hinged on its left edge seen from -Y, origin
             at the bottom of the hinge edge): red boards, white battens and Z braces and black strap
             hinges on the -Y face, a D-handle each side. Broken: boards kicked out, a brace snapped.
"""
from __future__ import annotations

import math

from mathutils import Vector

from generators.kit_wall import _casing, _chamfer_board_x, _opening_trim, _wall_body
from lib import common
from lib import kit_dims
from lib.kit_dims import CASING_T, CASING_W, HALF_T, JAMB_T, SILL_PROUD, SILL_T, STOREY_H, WALL_H, WALL_T
from lib.kit_geo import SIDE_A, SIDE_B, SIDE_N, KitMesh, bake_colors, collision_box, export_glb
from lib.kit_parts import board, glass_pane, glass_shards, nail

TALL_H = 2 * STOREY_H - (STOREY_H - WALL_H)  # 5.8: one storey's floor to the next storey's ceiling
# Clear openings (width, height, sill) of the two-storey pieces; the lancet's height is to its apex.
TALL_OPENINGS = {
    "window_tall": (0.76, 2.50, 0.80),
    "door_2m_tall": (1.80, 3.50, 0.0),
}
LANCET = (0.66, 1.00, 2.45)   # clear width, sill, straight jambs above the sill (then the arch)
BARN_DOOR = (0.89, 3.45, 0.05)
PLANK_T = 0.02
# kit_wall's casing and lining code reads kit_dims.OPENINGS by name: make the tall rectangles known.
kit_dims.OPENINGS.update(TALL_OPENINGS)


# -------------------------------------------------------------------------------------------------
# Pointed arch
# -------------------------------------------------------------------------------------------------

def lancet_outline(d: float, z_bottom: float, steps: int = 6) -> list[tuple[float, float]]:
    """The lancet's outline offset outward by d (d = 0: the clear opening, d < 0 inside it): up the
    left jamb from z_bottom, over an equilateral pointed arch (each side an arc of radius w + d about
    the opposite springing point), down the right jamb."""
    w, sill, spring = LANCET
    zs = sill + spring
    r = w + d
    pts = [(-(w / 2 + d), z_bottom), (-(w / 2 + d), zs)]
    apex = math.acos(-(w / 2) / r)
    for k in range(1, steps):
        a = math.pi - (math.pi - apex) * k / steps
        pts.append((w / 2 + r * math.cos(a), zs + r * math.sin(a)))
    pts.append((0.0, zs + math.sqrt(r * r - (w / 2) ** 2)))
    for k in range(steps - 1, 0, -1):
        a = math.pi - (math.pi - apex) * k / steps
        pts.append((-(w / 2 + r * math.cos(a)), zs + r * math.sin(a)))
    pts += [(w / 2 + d, zs), (w / 2 + d, z_bottom)]
    return pts


def lancet_apex(d: float = 0.0) -> float:
    w, sill, spring = LANCET
    return sill + spring + math.sqrt((w + d) ** 2 - (w / 2) ** 2)


def _band_between(inner: list, outer: list) -> list:
    """A U-shaped region between two lancet outlines that share their bottom height: up the outer,
    back down the inner (one simple polygon)."""
    return outer + list(reversed(inner))


# -------------------------------------------------------------------------------------------------
# Walls
# -------------------------------------------------------------------------------------------------

def build_band(p: dict, name: str, outputs: list[str]) -> None:
    km = KitMesh(name)
    km.part(0.0)
    z0, z1 = WALL_H, STOREY_H
    km.box((-0.5, -HALF_T, z0), (0.5, HALF_T, z1), "kit_wall",
           sides={"-y": SIDE_A, "+y": SIDE_B, "-x": SIDE_N, "+x": SIDE_N, "-z": SIDE_N, "+z": SIDE_N})
    obj = km.build()
    bake_colors(obj, ground_z=None, samples=8, seed=int(p.get("seed", 1)))
    export_glb(outputs[0], [obj, collision_box(f"{name}_col0", (-0.5, -HALF_T, z0), (0.5, HALF_T, z1))])


def build_wall_tall(p: dict, name: str, outputs: list[str]) -> None:
    rng = common.rng(p.get("seed", 1))
    L = float(p.get("length", 1.0))
    opening = p["opening"]
    km = KitMesh(name)
    rough = _wall_body(km, L, TALL_H, WALL_T, opening)
    _opening_trim(km, opening, L, rng)
    obj = km.build()
    bake_colors(obj, ground_z=0.0, ceiling_z=TALL_H, samples=16, distance=0.25, strength=0.7, seed=int(p.get("seed", 1)))
    x0, x1, z0, z1 = rough
    h2 = WALL_T / 2
    boxes = [((-L / 2, -h2, 0.0), (x0, h2, TALL_H)), ((x1, -h2, 0.0), (L / 2, h2, TALL_H)), ((x0, -h2, z1), (x1, h2, TALL_H))]
    if z0 > 0.0:
        boxes.append(((x0, -h2, 0.0), (x1, h2, z0)))
    cols = [collision_box(f"{name}_col{i}", lo, hi) for i, (lo, hi) in enumerate(boxes) if hi[0] - lo[0] > 1e-4]
    export_glb(outputs[0], [obj] + cols)


def build_lancet(p: dict, name: str, outputs: list[str]) -> None:
    seed = int(p.get("seed", 1))
    rng = common.rng(seed)
    w, sill, spring = LANCET
    L, H = 1.0, TALL_H
    km = KitMesh(name)
    # Wall body with the rough opening (2 cm lining all round, the stool's thickness below the sill).
    rough = lancet_outline(JAMB_T, sill - SILL_T)
    km.part(0.0)
    km.prism([[(-L / 2, 0.0), (L / 2, 0.0), (L / 2, H), (-L / 2, H)], rough], -HALF_T, HALF_T, axis="y", mat="kit_wall",
             side=(SIDE_A, SIDE_B, SIDE_N))
    # Linings through the wall (the reveal), from the stool up and over the arch.
    km.part(rng.uniform(0.3, 0.7))
    km.prism([_band_between(lancet_outline(0.0, sill), lancet_outline(JAMB_T, sill))], -HALF_T, HALF_T, axis="y",
             mat="kit_trim", side=(SIDE_N, SIDE_N, SIDE_N), grain="z")
    # Casings on both faces follow the jambs and the arch; a keystone at the apex.
    for sy, side in ((-1, SIDE_A), (1, SIDE_B)):
        km.part(rng.uniform(0.3, 0.7))
        band = _band_between(lancet_outline(JAMB_T, sill), lancet_outline(JAMB_T + CASING_W, sill))
        y0, y1 = sorted((sy * HALF_T, sy * (HALF_T + CASING_T)))
        km.prism([band], y0, y1, axis="y", mat="kit_trim", side=(side, side, SIDE_N), grain="z")
        top = lancet_apex(JAMB_T)
        ky0, ky1 = sorted((sy * HALF_T, sy * (HALF_T + CASING_T + 0.012)))
        km.box((-0.045, ky0, top - 0.05), (0.045, ky1, top + CASING_W + 0.03), "kit_trim", side=SIDE_N, grain="z")
        # apron under the stool
        ax = w / 2 + CASING_W - 0.006
        _casing(km, -ax, ax, sill - SILL_T - 0.075, sill - SILL_T, sy, CASING_T - 0.002, side, "x")
    # Stool: one board through the opening, projecting on both faces, with horns.
    km.part(rng.uniform(0.3, 0.7))
    sx = w / 2 + CASING_W + 0.028
    sy_ = HALF_T + CASING_T + SILL_PROUD
    _chamfer_board_x(km, -sx, sx, -sy_, sy_, sill - SILL_T, sill, "kit_trim", SIDE_N, ch=0.008, top_only=False)
    obj = km.build()
    bake_colors(obj, ground_z=0.0, ceiling_z=H, samples=16, distance=0.25, strength=0.7, seed=seed)
    rx = w / 2 + JAMB_T
    zs = sill + spring
    cols = [collision_box(f"{name}_col0", (-L / 2, -HALF_T, 0.0), (-rx, HALF_T, H)),
            collision_box(f"{name}_col1", (rx, -HALF_T, 0.0), (L / 2, HALF_T, H)),
            collision_box(f"{name}_col2", (-rx, -HALF_T, 0.0), (rx, HALF_T, sill - SILL_T)),
            collision_box(f"{name}_col3", (-rx, -HALF_T, zs), (rx, HALF_T, H))]
    export_glb(outputs[0], [obj] + cols)


# -------------------------------------------------------------------------------------------------
# Glass
# -------------------------------------------------------------------------------------------------

def _tall_sashes() -> dict:
    """6-over-6 double-hung layout for window_tall (as lib.kit_dims.sash_layout)."""
    w, h, _ = TALL_OPENINGS["window_tall"]
    frames, lites, locks = [], [], []
    x0, x1 = -w / 2, w / 2
    meet = h * 0.5
    stile, mw = 0.055, 0.022
    for z0, z1, y0, y1, rb, rt in ((meet - 0.02, h, -0.034, 0.0, 0.04, 0.055), (0.0, meet + 0.02, 0.002, 0.036, 0.085, 0.04)):
        frames.append((x0, x0 + stile, z0, z1, y0, y1))
        frames.append((x1 - stile, x1, z0, z1, y0, y1))
        frames.append((x0 + stile, x1 - stile, z0, z0 + rb, y0, y1))
        frames.append((x0 + stile, x1 - stile, z1 - rt, z1, y0, y1))
        frames.append((-mw / 2, mw / 2, z0 + rb, z1 - rt, y0 + 0.004, y1 - 0.004))
        lz0, lz1 = z0 + rb, z1 - rt
        lh = (lz1 - lz0 - 2 * mw) / 3
        yc = (y0 + y1) / 2
        for k in range(3):
            za = lz0 + k * (lh + mw)
            if k > 0:
                frames.append((x0 + stile, x1 - stile, za - mw, za, y0 + 0.004, y1 - 0.004))
            lites.append((x0 + stile, -mw / 2, za, za + lh, yc))
            lites.append((mw / 2, x1 - stile, za, za + lh, yc))
    locks.append((0.0, meet + 0.02, 0.036))
    return {"frames": frames, "lites": lites, "locks": locks}


def build_glass(p: dict, name: str, outputs: list[str]) -> None:
    seed = int(p.get("seed", 1))
    rng = common.rng(seed)
    broken = bool(p.get("broken", False))
    target = p.get("target", "lancet")
    km = KitMesh(name)
    if target == "window_tall":
        lay = _tall_sashes()
        for x0, x1, z0, z1, y0, y1 in lay["frames"]:
            km.part(rng.uniform(0.35, 0.65))
            km.box((x0, y0, z0), (x1, y1, z1), "kit_trim", side="y", grain="z" if (z1 - z0) > (x1 - x0) else "x")
        km.part(0.5)
        for x, z, y in lay["locks"]:
            km.box((x - 0.03, y, z - 0.012), (x + 0.03, y + 0.008, z + 0.006), "metal_steel", side="y")
        for x0, x1, z0, z1, yc in lay["lites"]:
            km.part(rng.uniform(0.3, 0.7))
            if broken:
                if rng.random() < 0.25:
                    continue
                glass_shards(km, x0, x1, z0, z1, rng, yc=yc, uv_rect=(x0, x1, z0, z1), tuck=0.01)
            else:
                glass_pane(km, x0 - 0.01, x1 + 0.01, z0 - 0.01, z1 + 0.01, yc, uv_rect=(x0, x1, z0, z1))
        w, h, _ = TALL_OPENINGS["window_tall"]
    else:
        w, sill, spring = LANCET
        h = lancet_apex() - sill
        # Outlines relative to the sill (the piece's origin).
        outer = [(x, z - sill) for x, z in lancet_outline(0.0, sill)]
        inner = [(x, z - sill) for x, z in lancet_outline(-0.05, sill + 0.06)]
        km.part(rng.uniform(0.35, 0.65))
        km.prism([_band_between(inner, outer)], -0.02, 0.02, axis="y", mat="kit_trim", side=(SIDE_N, SIDE_N, SIDE_N), grain="z")
        km.box((-w / 2 + 0.05, -0.02, 0.0), (w / 2 - 0.05, 0.02, 0.06), "kit_trim", side="y", grain="x")
        # Glazing bars: one up the middle, four across the straight part.
        mw = 0.02
        top_in = lancet_apex(-0.05) - sill
        km.part(rng.uniform(0.35, 0.65))
        km.box((-mw / 2, -0.011, 0.06), (mw / 2, 0.011, top_in - 0.01), "kit_trim", side="y", grain="z")
        bars = [0.06 + (spring - 0.06) * k / 5 for k in range(1, 5)] + [spring]
        for z in bars:
            km.box((-w / 2 + 0.045, -0.0105, z - mw / 2), (w / 2 - 0.045, 0.0105, z + mw / 2), "kit_trim", side="y", grain="x")
        km.part(0.5)
        lw = w - 0.1
        if not broken:
            pts = [(x, 0.0, z) for x, z in inner]
            n = len(pts)
            uv = lambda q, nn: ((q.x + lw / 2) / lw, (q.z - 0.06) / (top_in - 0.06))  # noqa: E731
            for yc in (-0.0015, 0.0015):
                verts = [(x, yc, z) for x, _, z in pts]
                face = list(range(n)) if yc > 0 else list(reversed(range(n)))
                km.emit(verts, [(face, "glass", "y", False)], uv_fn=uv)
        else:
            rows = [0.06] + bars
            for k in range(len(rows) - 1):
                if rng.random() < 0.3:
                    continue
                for xa, xb in ((-lw / 2, -mw / 2), (mw / 2, lw / 2)):
                    if rng.random() < 0.35:
                        continue
                    glass_shards(km, xa, xb, rows[k] + mw / 2, rows[k + 1] - mw / 2, rng, uv_rect=(-lw / 2, lw / 2, 0.06, top_in),
                                 n_hole=6, cracks=(2, 3))
    obj = km.build()
    bake_colors(obj, ground_z=None, samples=12, distance=0.12, strength=0.6, seed=seed)
    out = [obj]
    if not broken:
        out.append(collision_box(f"{name}_col0", (-w / 2, -0.02, 0.0), (w / 2, 0.02, h)))
    export_glb(outputs[0], out)


# -------------------------------------------------------------------------------------------------
# Board-ups
# -------------------------------------------------------------------------------------------------

def build_boards(p: dict, name: str, outputs: list[str]) -> None:
    seed = int(p.get("seed", 1))
    rng = common.rng(seed)
    target = p.get("target", "lancet")
    km = KitMesh(name)
    if target == "lancet":
        w = LANCET[0]
        zs = [0.12, 0.5, 0.88, 1.28, 1.66, 2.06, 2.42]
        top = lancet_apex() - LANCET[1]
    else:
        w, top, _ = TALL_OPENINGS["window_tall"]
        zs = [0.12, 0.52, 0.94, 1.36, 1.78, 2.2, 2.38]
    span = w + 2 * CASING_W
    ymin = 0.0
    for k, z in enumerate(zs):
        wd = rng.choice((0.14, 0.16, 0.18))
        length = min(span + rng.uniform(0.02, 0.1), 0.99)
        if target == "lancet" and z > LANCET[2] - 0.1:
            length = w * 0.85
        layer = k % 2
        ang = rng.uniform(-0.12, 0.12)
        y = -(HALF_T + CASING_T) - PLANK_T / 2 - layer * (PLANK_T + 0.001)
        ymin = min(ymin, y - PLANK_T / 2)
        dx = rng.uniform(-0.03, 0.03)
        c, s = math.cos(ang), math.sin(ang)
        a = Vector((dx - c * length / 2, y, z + rng.uniform(-0.03, 0.03) - s * length / 2))
        b = Vector((dx + c * length / 2, y, a.z + s * length))
        wdir = Vector((-s, 0.0, c))
        km.part(rng.uniform(0.15, 0.85))
        board(km, a, b, wdir, wd, PLANK_T, mat="wood_raw", rng=rng, end1=rng.uniform(0.02, 0.05) if rng.random() < 0.25 else None, teeth=1)
        km.part(0.5)
        along = (b - a).normalized()
        for t_ in (0.035, length - 0.035):
            for sgn in (-1, 1):
                nail(km, a + along * t_ + wdir * (sgn * wd * 0.28) + Vector((0, -PLANK_T / 2, 0)), Vector((0, -1, 0)), rng)
    obj = km.build()
    bake_colors(obj, ground_z=None, samples=12, distance=0.12, strength=0.7, seed=seed)
    col = collision_box(f"{name}_col0", (-w / 2 - CASING_W, ymin, 0.0), (w / 2 + CASING_W, -HALF_T, top))
    export_glb(outputs[0], [obj, col])


# -------------------------------------------------------------------------------------------------
# Tall barn door leaf
# -------------------------------------------------------------------------------------------------

def build_barn_door(p: dict, name: str, outputs: list[str]) -> None:
    seed = int(p.get("seed", 1))
    rng = common.rng(seed)
    broken = bool(p.get("broken", False))
    W, H, T = BARN_DOOR
    km = KitMesh(name)
    n = 8
    gap = 0.004
    bw = (W - gap * (n - 1)) / n
    t_board = 0.026
    missing = set(rng.sample(range(1, n - 1), 2)) if broken else set()
    short = rng.randrange(1, n - 1) if broken else -1
    for k in range(n):
        if k in missing:
            continue
        x0 = k * (bw + gap)
        z_top = H if k != short else H * rng.uniform(0.45, 0.65)
        km.part(rng.uniform(0.2, 0.8))
        board(km, (x0 + bw / 2, 0.0, 0.0), (x0 + bw / 2, 0.0, z_top), (1, 0, 0), bw, t_board, mat="farm_wood_barn_red", rng=rng,
              end1=rng.uniform(0.04, 0.12) if k == short else None, teeth=2 if k == short else 0)
    # Battens and Z braces on the -Y face (white), strap hinges and the handle (black iron).
    yb = -t_board / 2 - 0.012
    rails = [0.22, H * 0.5, H - 0.24]
    for z in rails:
        km.part(rng.uniform(0.3, 0.7))
        board(km, (0.02, yb, z), (W - 0.02, yb, z), (0, 0, 1), 0.15, 0.024, mat="kit_trim", rng=rng)
    for k in range(2):
        za, zb = rails[k] + 0.075, rails[k + 1] - 0.075
        if broken and k == 1:
            # snapped: the lower half stays, the upper hangs away
            mid = Vector((W / 2, yb, (za + zb) / 2))
            board(km, (0.08, yb, za), mid, (0.6, 0, -0.8), 0.13, 0.024, mat="kit_trim", rng=rng, end1=0.06, teeth=2)
            continue
        km.part(rng.uniform(0.3, 0.7))
        board(km, (0.08, yb, za), (W - 0.08, yb, zb), (0.6, 0, -0.8), 0.13, 0.024, mat="kit_trim", rng=rng)
    km.part(0.5)
    ys = -t_board / 2 - 0.027
    for z in rails:
        km.box((0.0, ys - 0.005, z - 0.035), (0.48, ys, z + 0.035), "metal_steel", side="y", grain="x")
        for x in (0.06, 0.2, 0.36):
            nail(km, (x, ys - 0.005, z), (0, -1, 0), rng)
    for sy in (-1, 1):
        y0 = sy * (t_board / 2 + (0.024 if sy < 0 else 0.0))
        hx = W - 0.08
        km.box((hx - 0.012, min(y0, y0 + sy * 0.05), 0.95), (hx + 0.012, max(y0, y0 + sy * 0.05), 0.98), "metal_steel", side="y")
        km.box((hx - 0.012, min(y0, y0 + sy * 0.05), 1.22), (hx + 0.012, max(y0, y0 + sy * 0.05), 1.25), "metal_steel", side="y")
        km.box((hx - 0.012, min(y0 + sy * 0.04, y0 + sy * 0.05), 0.95), (hx + 0.012, max(y0 + sy * 0.04, y0 + sy * 0.05), 1.25),
               "metal_steel", side="y", grain="z")
    obj = km.build()
    bake_colors(obj, ground_z=None, samples=12, distance=0.15, strength=0.7, seed=seed)
    export_glb(outputs[0], [obj])


def build(params: dict, outputs: list[str]) -> None:
    name = params.get("name", "kit_tall")
    {"band": build_band, "wall_tall": build_wall_tall, "lancet": build_lancet, "glass": build_glass,
     "boards": build_boards, "barn_door": build_barn_door}[params.get("kind", "band")](params, name, outputs)
