"""Interior props - light fixtures: flush-mount frosted dome ceiling light (ceiling: origin on the ceiling
plane, hangs down -Z), brass wall sconce with frosted tulip shade (wall), articulated desk lamp (surface).
Light parameters (colour, energy, range, flicker, offset) live in game/data/props/interior.json.

params: prop (id), seed, variants, mount, budget (see blender_catalogs/props_interior.py).
"""
from __future__ import annotations

import math

from lib import props_int_core as core
from lib import props_int_mesh as G
from lib.props_int_core import M, Prop


def _bulb(p: Prop, c, axis: str = "-Z", broken: bool = False) -> list:
    out = [p.lathe([(0.014, 0.0), (0.014, 0.02), (0.012, 0.024)], c, M.BRASS, segs=8, axis=axis, cap_top=False)]
    if broken:
        x, y, z = c
        d = {"-Z": (0, 0, -1), "Z": (0, 0, 1), "Y": (0, 1, 0), "-Y": (0, -1, 0)}[axis]
        stub = p.lathe([(0.012, 0.0), (0.02, 0.012), (0.024, 0.025)], (x + d[0] * 0.024, y + d[1] * 0.024, z + d[2] * 0.024),
                       M.GLASS_FROST, segs=8, axis=axis, cap_bottom=False, cap_top=False)
        out.append(stub)
        return out
    x, y, z = c
    d = {"-Z": (0, 0, -1), "Z": (0, 0, 1), "Y": (0, 1, 0), "-Y": (0, -1, 0)}[axis]
    out.append(p.lathe([(0.012, 0.0), (0.02, 0.012), (0.03, 0.04), (0.028, 0.06), (0.016, 0.075), (0.0, 0.078)],
                       (x + d[0] * 0.024, y + d[1] * 0.024, z + d[2] * 0.024), M.GLASS_FROST, segs=10, axis=axis))
    return out


def ceiling_light(p: Prop) -> None:
    """Flush-mount 'dome' ceiling fixture: brass canopy ring, frosted glass dome (r 0.17), finial nut.
    Origin on the ceiling plane at the fixture centre; geometry hangs down to z = -0.13."""
    p.lathe([(0.0, 0.0), (0.12, 0.0), (0.125, -0.01), (0.12, -0.02), (0.0, -0.02)], (0, 0, 0), M.BRASS, segs=20,
                     cap_bottom=False, cap_top=False)
    _bulb(p, (0.0, 0.0, -0.02), axis="-Z", broken=p.destroyed)
    dome_prof = [(0.17, 0.0), (0.168, -0.03), (0.155, -0.07), (0.12, -0.1), (0.06, -0.12), (0.0, -0.125)]
    inner_prof = [(0.0, -0.12), (0.058, -0.116), (0.116, -0.097), (0.15, -0.068), (0.163, -0.03), (0.165, 0.0)]
    if not p.destroyed:
        dome = p.lathe(dome_prof + inner_prof, (0, 0, -0.022), M.GLASS_FROST, segs=24, cap_bottom=False, cap_top=False,
                       edge_deg=50)
        p.lathe([(0.012, 0.0), (0.014, -0.01), (0.008, -0.022), (0.0, -0.024)], (0, 0, -0.145), M.BRASS, segs=8)
        if p.cond == "worn":
            # dead insects / dust pooled in the bottom of the dome
            p.cyl(0.07, 0.003, (0.0, 0.0, -0.138), M.MOLD, segs=12)
            p.rotate([dome] + p.parts[-2:], rot=(4, 0, 0), pivot=(0.17, 0, -0.022))
    else:
        # dome smashed: a jagged band of glass left in the canopy clips, shards gone
        band = p.lathe([(0.17, 0.0), (0.168, -0.03), (0.163, -0.03), (0.165, 0.0)], (0, 0, -0.022), M.GLASS_FROST, segs=24,
                       cap_bottom=False, cap_top=False, edge_deg=50)
        for v in band.obj.data.vertices:
            if v.co.z < -0.04:
                ang = math.atan2(v.co.y, v.co.x)
                v.co.z += 0.025 * (0.5 + 0.5 * math.sin(ang * 7 + 1.3)) * (1 if (int((ang + 4) * 3) % 2) else 0.3)
        for i in range(3):
            clip = p.box((0.01, 0.025, 0.035), (0, 0, 0), M.BRASS, bevel=0.002)
            a = 2 * math.pi * i / 3
            G.xform(clip.obj, rot=(0, 0, math.degrees(a)), loc=(0.17 * math.cos(a), 0.17 * math.sin(a), -0.035))
    p.collider((0, 0, -0.07), (0.36, 0.36, 0.14))


def wall_sconce(p: Prop) -> None:
    """Brass wall sconce: oval back plate on the wall, curved arm, cup with an upturned frosted tulip shade.
    Origin on the wall plane, bottom centre (front -Y)."""
    plate = p.lathe([(0.0, 0.0), (0.06, 0.0), (0.06, 0.012), (0.045, 0.02), (0.0, 0.021)], (0, 0, 0), M.BRASS, segs=14,
                    axis="-Y", cap_bottom=False)
    G.xform(plate.obj, scale=(0.75, 1.0, 1.0))
    G.xform(plate.obj, loc=(0, 0, 0.12))
    p.tube([(0, -0.015, 0.1), (0, -0.07, 0.07), (0, -0.13, 0.1), (0, -0.14, 0.15)], 0.007, M.BRASS, segs=8, fillet_r=0.04,
                 steps=3)
    p.lathe([(0.0, 0.0), (0.03, 0.0), (0.04, 0.02), (0.035, 0.03)], (0, -0.14, 0.15), M.BRASS, segs=12, cap_top=False)
    _bulb(p, (0, -0.14, 0.175), axis="Z", broken=p.destroyed)
    shade_prof = [(0.035, 0.0), (0.06, 0.04), (0.09, 0.1), (0.1, 0.14), (0.094, 0.142), (0.084, 0.1), (0.054, 0.042),
                  (0.03, 0.004)]
    if not p.destroyed:
        p.lathe(shade_prof, (0, -0.14, 0.175), M.GLASS_FROST, segs=16, cap_bottom=False, cap_top=False, edge_deg=50)
    else:
        sh = p.lathe(shade_prof[:3] + shade_prof[-3:], (0, -0.14, 0.175), M.GLASS_FROST, segs=16, cap_bottom=False,
                     cap_top=False, edge_deg=50)
        for v in sh.obj.data.vertices:
            if v.co.z > 0.2:
                ang = math.atan2(v.co.y + 0.14, v.co.x)
                v.co.z -= 0.03 * (0.5 + 0.5 * math.sin(ang * 5))
        p.rotate([q for q in p.parts if q is not plate], rot=(0, 18, 0), pivot=(0, -0.015, 0.1))
    p.collider((0, -0.08, 0.16), (0.2, 0.16, 0.32))


def desk_lamp(p: Prop) -> None:
    """Articulated task lamp (black enamel): weighted base, two parallel-rod arms with springs, cone shade."""
    base = [p.lathe([(0.09, 0.0), (0.092, 0.01), (0.085, 0.025), (0.03, 0.035), (0.0, 0.036)], (0, 0, 0), M.STEEL_BLACK,
                    segs=16)]
    base.append(p.cyl(0.012, 0.03, (0, 0, 0.05), M.STEEL_BLACK, segs=8))
    j1 = (0.0, 0.0, 0.065)
    a1 = math.radians(70)
    l1 = 0.3
    j2 = (j1[0] + math.cos(a1) * l1 * 0.3, j1[1], j1[2] + math.sin(a1) * l1)
    a2 = math.radians(-25)
    l2 = 0.28
    j3 = (j2[0] + math.cos(a2) * l2, j2[1], j2[2] + math.sin(a2) * l2)
    arms = []
    for dy in (-0.012, 0.012):
        arms.append(p.tube([(j1[0], dy, j1[2]), (j2[0], dy, j2[2])], 0.004, M.STEEL_BLACK, segs=6))
        arms.append(p.tube([(j2[0], dy, j2[2]), (j3[0], dy, j3[2])], 0.004, M.STEEL_BLACK, segs=6))
    arms.append(p.tube([(j1[0] + 0.02, 0.0, j1[2] + 0.03), (j2[0] - 0.01, 0.0, j2[2] - 0.08)], 0.006, M.CHROME, segs=6))
    for j in (j1, j2, j3):
        arms.append(p.cyl(0.012, 0.035, j, M.STEEL_BLACK, axis="Y", segs=8))
    shade_c = (j3[0] + 0.02, 0.0, j3[2] - 0.02)
    shade = p.lathe([(0.015, 0.0), (0.03, 0.03), (0.075, 0.12), (0.078, 0.125), (0.072, 0.122), (0.027, 0.034), (0.0, 0.03)],
                    shade_c, M.STEEL_BLACK, segs=16, axis="-Z", cap_bottom=True, cap_top=False, edge_deg=50)
    G.xform(shade.obj, rot=(0, -35, 0), pivot=shade_c)
    bulb = _bulb(p, (shade_c[0], 0.0, shade_c[2] - 0.035), axis="-Z", broken=p.destroyed)
    p.rotate(bulb, rot=(0, -35, 0), pivot=shade_c)
    head = [shade] + bulb
    if p.destroyed:
        for v in shade.obj.data.vertices:  # dented rim
            if v.co.x > shade_c[0] + 0.03:
                v.co.x -= 0.015
        whole = list(p.parts)
        p.rotate(whole, rot=(88, 0, 0), pivot=(0, 0, 0))
        lo, hi = p.bounds(whole)
        p.move(whole, (0, 0, -lo.z))
        p.collider((0, 0.15, 0.06), (0.45, 0.5, 0.12))
    else:
        if p.cond == "worn":
            p.rotate(head, rot=(0, 25, 0), pivot=j3)
        p.collider((0.1, 0, 0.2), (0.35, 0.2, 0.42))


BUILDERS = {
    "ceiling_light": ceiling_light,
    "wall_sconce": wall_sconce,
    "desk_lamp": desk_lamp,
}


def build(params: dict, outputs: list[str]) -> None:
    core.build_variants(params, outputs, BUILDERS[params["prop"]])
