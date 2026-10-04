"""POI kit door leaves (docs/POI_KIT.md): hinged on the LEFT edge seen from -Y, origin = bottom of the
hinge edge; the leaf spans x in [0, 0.82], y in [-0.02, 0.02], z in [0, 2.05].

params: kind ("interior" | "exterior" | "metal"), name, seed, broken (bool), frac (bool), pieces
  interior: six-panel door, raised panels, knobs both sides (M_door_wood, M_metal_steel)
  exterior: two lower panels + 9-lite glazed upper section (M_glass), knob + deadbolt
  metal:    steel security door (M_metal_painted) with push bar (+Y side), lever (-Y side), kick plate
  broken:   kicked-in panel(s) with splintered remains, latch area torn out, split along the stile
  frac:     Voronoi chunks of the leaf (inner M_wood_raw) + the knob as its own chunk
UVSide: -Y faces 0, +Y faces 1, edges 0.5 (two-sided paint possible).
"""
from __future__ import annotations

import math

import bpy
from mathutils import Matrix, Vector

from lib import common, fracture
from lib import kit_poly as P
from lib.kit_dims import DOOR_H, DOOR_T, DOOR_W
from lib.kit_geo import SIDE_N, KitMesh, bake_colors, export_glb, fix_chunks
from lib.kit_parts import glass_pane, glass_shards, sliver

W, H, T = DOOR_W, DOOR_H, DOOR_T
STILE = 0.11
KNOB = (W - 0.065, 0.95)

SIX_PANELS = [(STILE, 0.355, 0.23, 0.82), (0.465, W - STILE, 0.23, 0.82),
              (STILE, 0.355, 1.02, 1.58), (0.465, W - STILE, 1.02, 1.58),
              (STILE, 0.355, 1.69, 1.94), (0.465, W - STILE, 1.69, 1.94)]
EXT_PANELS = SIX_PANELS[:2]
EXT_GLASS = (0.14, W - 0.14, 1.12, 1.88)


def _rect(x0, x1, z0, z1):
    return [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]


def _raised_panel(km: KitMesh, x0, x1, z0, z1, *, mat: str = "door_wood", inset: float = 0.035,
                  t_edge: float = 0.005, t_field: float = 0.011, tuck: float = 0.01) -> None:
    """Raised panel sitting in the frame groove (edges tucked `tuck` into the stiles/rails)."""
    ox0, ox1, oz0, oz1 = x0 - tuck, x1 + tuck, z0 - tuck, z1 + tuck
    ix0, ix1, iz0, iz1 = x0 + inset, x1 - inset, z0 + inset, z1 - inset
    for sy in (-1, 1):
        o = [(ox0, sy * t_edge, oz0), (ox1, sy * t_edge, oz0), (ox1, sy * t_edge, oz1), (ox0, sy * t_edge, oz1)]
        i = [(ix0, sy * t_field, iz0), (ix1, sy * t_field, iz0), (ix1, sy * t_field, iz1), (ix0, sy * t_field, iz1)]
        pts = o + i
        quads = [[0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7], [4, 5, 6, 7]]
        if sy > 0:
            quads = [list(reversed(q)) for q in quads]
        km.emit(pts, [(q, mat, "y", False) for q in quads], grain="z")


def _knob(km: KitMesh, x: float, z: float, sy: int, *, deadbolt: bool = False) -> None:
    prof = [(0.028, 0.0), (0.028, 0.007), (0.009, 0.012), (0.009, 0.03), (0.026, 0.042), (0.024, 0.058), (0.0, 0.064)]
    fr = Matrix.Translation((x, sy * T / 2, z)) @ Matrix.Rotation(-sy * math.pi / 2, 4, "X")
    km.lathe(prof, mat="metal_steel", segments=6, frame=fr, cap_bottom=False)
    if deadbolt:
        fr2 = Matrix.Translation((x, sy * T / 2, z + 0.16)) @ Matrix.Rotation(-sy * math.pi / 2, 4, "X")
        km.lathe([(0.027, 0.0), (0.027, 0.01), (0.02, 0.016), (0.0, 0.017)], mat="metal_steel", segments=6, frame=fr2,
                 cap_bottom=False)
        if sy > 0:
            km.box((x - 0.006, sy * T / 2 + 0.012, z + 0.16 - 0.02), (x + 0.006, sy * T / 2 + 0.03, z + 0.16 + 0.02),
                   "metal_steel")


def _hinges(km: KitMesh, zs=(0.24, 1.0, 1.8), r: float = 0.0075, h: float = 0.09) -> None:
    for z in zs:
        km.lathe([(r, 0.0), (r, h)], mat="metal_steel", segments=6, frame=Matrix.Translation((-0.001, -T / 2, z - h / 2)))


def _leaf(km: KitMesh, kind: str, rng, *, broken: bool, for_frac: bool = False) -> dict:
    """Builds the leaf body. Returns info (knob position, removed parts)."""
    panels = SIX_PANELS if kind == "interior" else EXT_PANELS
    holes = [_rect(*pnl) for pnl in panels]
    glass = None
    if kind == "exterior":
        glass = EXT_GLASS
        holes.append(_rect(*glass))
    outline = _rect(0.0, W, 0.0, H)
    broken_pts: set = set()
    smashed: list[int] = []
    info = {"knob": True}
    if broken:
        # Latch area torn out: jagged notch in the latch edge around the knob.
        zc = KNOB[1] + rng.uniform(-0.04, 0.06)
        h0, h1 = zc - rng.uniform(0.13, 0.2), zc + rng.uniform(0.14, 0.24)
        depth = rng.uniform(0.07, 0.095)
        notch = [(W, h0)]
        n = 7
        for k in range(1, n):
            t = k / n
            z = h0 + (h1 - h0) * t
            d = depth * math.sin(math.pi * t) ** 0.6 * rng.uniform(0.6, 1.0)
            if k % 2:
                d *= rng.uniform(0.55, 0.85)
            notch.append((W - d, z + rng.uniform(-0.012, 0.012)))
        notch.append((W, h1))
        outline = [(0.0, 0.0), (W, 0.0)] + notch + [(W, H), (0.0, H)]
        broken_pts |= {(round(x, 6), round(z, 6)) for x, z in notch}
        info["knob"] = False
        info["notch"] = notch
        # Split running up the lock stile from the notch (along the grain).
        line = [(W - STILE / 2 + rng.uniform(-0.01, 0.01), h1 + 0.03)]
        zz = line[0][1]
        while zz < min(H - 0.15, h1 + rng.uniform(0.35, 0.6)):
            zz += rng.uniform(0.05, 0.09)
            line.append((W - STILE / 2 + rng.uniform(-0.012, 0.012), zz))
        crack = P.crack_lens(line, rng.uniform(0.004, 0.007))
        holes.append(crack)
        broken_pts |= {(round(x, 6), round(z, 6)) for x, z in crack}
        smashed = [1] if kind == "interior" else [1]
        if kind == "interior" and rng.random() < 0.5:
            smashed.append(0)
    km.part(rng.uniform(0.3, 0.7))

    def rim_mat(pa, pb):
        if (round(pa[0], 6), round(pa[1], 6)) in broken_pts and (round(pb[0], 6), round(pb[1], 6)) in broken_pts:
            return ("wood_raw", SIDE_N)
        return None

    km.prism([outline] + holes, -T / 2, T / 2, axis="y", mat="door_wood", side=("y", "y", SIDE_N), grain="z",
             rim_mat_fn=rim_mat, uv_off=(rng.uniform(0, 3), rng.uniform(0, 3)))
    # Panels.
    for i, (x0, x1, z0, z1) in enumerate(panels):
        km.part(rng.uniform(0.3, 0.7))
        if for_frac:
            km.box((x0 - 0.01, -0.008, z0 - 0.01), (x1 + 0.01, 0.008, z1 + 0.01), "door_wood", side="y", grain="z")
        elif i in smashed:
            _smashed_panel(km, x0, x1, z0, z1, rng)
        else:
            _raised_panel(km, x0, x1, z0, z1)
    if glass is not None:
        _glazing(km, glass, rng, broken=broken, for_frac=for_frac)
    return info


def _smashed_panel(km: KitMesh, x0, x1, z0, z1, rng) -> None:
    """A kicked-in panel: splintered remains along the groove, split into a few cracked pieces."""
    cx, cz = (x0 + x1) / 2 + rng.uniform(-0.03, 0.03), (z0 + z1) / 2 + rng.uniform(-0.05, 0.05)
    rx, rz = (x1 - x0) / 2, (z1 - z0) / 2
    hole = P.star(cx, cz, rx * rng.uniform(0.62, 0.78), rz * rng.uniform(0.62, 0.8), 13, rng, rough=0.22, teeth=0.4)
    outer = _rect(x0 - 0.01, x1 + 0.01, z0 - 0.01, z1 + 0.01)
    angles = sorted(rng.uniform(0, math.tau) for _ in range(rng.randint(3, 5)))
    pieces = P.sector_split(outer, hole, (cx, cz), angles, gap=0.012)
    for k, pc in enumerate(pieces):
        if rng.random() < 0.18:
            continue
        tilt = Matrix.Translation((0, 0, 0))
        if rng.random() < 0.5:
            # pushed inward a little (toward +Y), hinged on the groove
            ang = rng.uniform(0.04, 0.12)
            cxp, czp = P.centroid(pc)
            tilt = Matrix.Translation((cxp, 0, czp)) @ Matrix.Rotation(ang, 4, Vector((math.cos(k), 0, math.sin(k)))) @ \
                Matrix.Translation((-cxp, 0, -czp))
        outer_set = {(round(x, 6), round(z, 6)) for x, z in outer}

        def rim(pa, pb, outer_set=outer_set):
            if (round(pa[0], 6), round(pa[1], 6)) in outer_set and (round(pb[0], 6), round(pb[1], 6)) in outer_set:
                return None
            return ("wood_raw", SIDE_N)
        km.prism([pc], -0.006, 0.006, axis="y", mat="door_wood", side=("y", "y", SIDE_N), grain="z", frame=tilt,
                 rim_mat_fn=rim)


def _glazing(km: KitMesh, g, rng, *, broken: bool, for_frac: bool) -> None:
    x0, x1, z0, z1 = g
    mw = 0.022
    # glazing beads on both faces
    km.part(rng.uniform(0.3, 0.7))
    b = 0.016
    for sy in (-1, 1):
        ya, yb = sorted((sy * 0.004, sy * (T / 2 - 0.002)))
        km.box((x0, ya, z0), (x1, yb, z0 + b), "door_wood", side="y", grain="x")
        km.box((x0, ya, z1 - b), (x1, yb, z1), "door_wood", side="y", grain="x")
        km.box((x0, ya, z0 + b), (x0 + b, yb, z1 - b), "door_wood", side="y", grain="z")
        km.box((x1 - b, ya, z0 + b), (x1, yb, z1 - b), "door_wood", side="y", grain="z")
    # muntins (3 x 3 lites)
    km.part(rng.uniform(0.3, 0.7))
    for k in (1, 2):
        xm = x0 + b + (x1 - x0 - 2 * b) * k / 3
        km.box((xm - mw / 2, -0.012, z0 + b), (xm + mw / 2, 0.012, z1 - b), "door_wood", side="y", grain="z")
        zm = z0 + b + (z1 - z0 - 2 * b) * k / 3
        km.box((x0 + b, -0.0115, zm - mw / 2), (x1 - b, 0.0115, zm + mw / 2), "door_wood", side="y", grain="x")
    km.part(0.5)
    gx0, gx1, gz0, gz1 = x0 + 0.006, x1 - 0.006, z0 + 0.006, z1 - 0.006
    if for_frac:
        return
    if not broken:
        glass_pane(km, gx0, gx1, gz0, gz1)
        return
    # broken: shards left in each lite
    lw = (gx1 - gx0 - 2 * mw) / 3
    lh = (gz1 - gz0 - 2 * mw) / 3
    for i in range(3):
        for j in range(3):
            lx0 = gx0 + i * (lw + mw)
            lz0 = gz0 + j * (lh + mw)
            if rng.random() < 0.4:
                continue
            glass_shards(km, lx0, lx0 + lw, lz0, lz0 + lh, rng, uv_rect=(gx0, gx1, gz0, gz1), n_hole=6, cracks=(2, 3))


def _metal_leaf(km: KitMesh, rng) -> None:
    t = 0.045
    c = 0.004
    prof = [(0.0, -t / 2 + c), (c, -t / 2), (W - c, -t / 2), (W, -t / 2 + c), (W, t / 2 - c), (W - c, t / 2),
            (c, t / 2), (0.0, t / 2 - c)]
    km.part(rng.uniform(0.3, 0.7))
    km.prism([prof], 0.0, H, axis="z", mat="metal_painted", side=(SIDE_N, SIDE_N, "y"), grain="z")
    # stiffener seam lines on both faces (a raised border 3 cm in from the edge)
    for sy in (-1, 1):
        ya, yb = sorted((sy * t / 2, sy * (t / 2 + 0.0025)))
        for lo, hi, g in (((0.045, ya, 0.06), (0.06, yb, H - 0.06), "z"), ((W - 0.06, ya, 0.06), (W - 0.045, yb, H - 0.06), "z"),
                          ((0.06, ya, 0.06), (W - 0.06, yb, 0.075), "x"), ((0.06, ya, H - 0.075), (W - 0.06, yb, H - 0.06), "x")):
            km.box(lo, hi, "metal_painted", side="y", grain=g, skip=("+y",) if sy < 0 else ("-y",))
    km.part(0.5)
    # kick plate (+Y) and push bar
    km.box((0.05, t / 2, 0.03), (W - 0.05, t / 2 + 0.0015, 0.28), "metal_steel", side="y", skip=("-y",))
    for hx in (0.09, W - 0.11):
        km.box((hx - 0.03, t / 2, 0.92), (hx + 0.03, t / 2 + 0.07, 1.04), "metal_steel", side="y", skip=("-y",))
    km.box((0.12, t / 2 + 0.035, 0.955), (W - 0.14, t / 2 + 0.065, 1.005), "metal_steel", side="y", grain="x")
    # lever + escutcheon (-Y)
    ex = W - 0.07
    km.box((ex - 0.025, -t / 2 - 0.008, 0.9), (ex + 0.025, -t / 2, 1.12), "metal_steel", side="y", skip=("+y",))
    km.lathe([(0.011, 0.0), (0.011, 0.05)], mat="metal_steel", segments=8,
             frame=Matrix.Translation((ex, -t / 2 - 0.008, 1.0)) @ Matrix.Rotation(math.pi / 2, 4, "X"), cap_bottom=False)
    km.box((ex - 0.13, -t / 2 - 0.07, 0.988), (ex + 0.008, -t / 2 - 0.05, 1.012), "metal_steel", side="y", grain="x")
    km.lathe([(0.018, 0.0), (0.018, 0.008)], mat="metal_steel", segments=8,
             frame=Matrix.Translation((ex, -t / 2 - 0.008, 1.06)) @ Matrix.Rotation(math.pi / 2, 4, "X"), cap_bottom=False)
    _hinges(km, zs=(0.22, 1.0, 1.82), r=0.009, h=0.11)


def build(params: dict, outputs: list[str]) -> None:
    name = params.get("name", "door")
    kind = params.get("kind", "interior")
    seed = int(params.get("seed", 1))
    rng = common.rng(seed)
    broken = bool(params.get("broken", False))
    frac = bool(params.get("frac", False))
    km = KitMesh(name)
    if kind == "metal":
        _metal_leaf(km, rng)
        obj = km.build()
        bake_colors(obj, ground_z=None, samples=12, distance=0.15, strength=0.7, seed=seed)
        export_glb(outputs[0], [obj])
        return
    info = _leaf(km, kind, rng, broken=broken, for_frac=frac)
    if frac:
        src = km.build(name + "_src")
        chunks = fracture.fracture(src, int(params.get("pieces", 7)), seed, "wood_raw", margin=0.002, bias=(1.0, 0.0, 1.0))
        bpy.data.objects.remove(src, do_unlink=True)
        fix_chunks(chunks, "wood_raw", seed=seed, grain="z")
        kk = KitMesh("knob")
        for sy in (-1, 1):
            _knob(kk, KNOB[0], KNOB[1], sy)
        knob = kk.build(f"chunk_{len(chunks):02d}")
        c = Vector((KNOB[0], 0.0, KNOB[1]))
        knob.data.transform(Matrix.Translation(-c))
        knob.location = c
        bake_colors(knob, ground_z=None, samples=8, distance=0.05, seed=seed)
        export_glb(outputs[0], chunks + [knob])
        return
    km.part(0.5)
    if info["knob"]:
        for sy in (-1, 1):
            _knob(km, KNOB[0], KNOB[1], sy, deadbolt=(kind == "exterior"))
    else:
        # torn-out latch: splinters around the notch, the knob is gone
        notch = info["notch"]
        for k in range(4):
            x, z = notch[1 + (k * 2) % (len(notch) - 2)]
            sliver(km, (x + 0.004, rng.uniform(-0.012, 0.012), z), (rng.uniform(-0.6, 0.2), rng.uniform(-0.8, 0.8), rng.uniform(-0.5, 0.5)),
                   rng.uniform(0.03, 0.07), 0.008, rng, mat="wood_raw")
    _hinges(km)
    obj = km.build()
    bake_colors(obj, ground_z=None, samples=12, distance=0.15, strength=0.7, seed=seed)
    export_glb(outputs[0], [obj])
