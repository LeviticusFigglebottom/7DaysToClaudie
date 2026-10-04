"""Interior props - bathroom: two-piece toilet, enamelled alcove bathtub, pedestal sink, mirrored medicine
cabinet (wall), towel bar with towel (wall).

params: prop (id), seed, variants, mount, budget (see blender_catalogs/props_interior.py).
"""
from __future__ import annotations

from lib import props_int_core as core
from lib import props_int_furn as F
from lib import props_int_mesh as G
from lib.props_int_core import M, Prop


def _oval_lathe(p: Prop, prof, center, sy: float, mat: str, segs: int = 16, **kw) -> core.Part:
    part = p.lathe(prof, (0, 0, 0), mat, segs=segs, **kw)
    G.xform(part.obj, scale=(1.0, sy, 1.0))
    G.xform(part.obj, loc=center)
    return part


def toilet(p: Prop) -> None:
    """Two-piece close-coupled toilet: oval bowl on a pedestal, tank with lid and chrome lever, plastic seat."""
    by = -0.1
    bowl_prof = [(0.11, 0.0), (0.1, 0.12), (0.12, 0.26), (0.175, 0.37), (0.185, 0.385), (0.17, 0.39), (0.12, 0.33),
                 (0.07, 0.24), (0.0, 0.22)]
    bowl = _oval_lathe(p, bowl_prof, (0, by, 0), 1.3, M.CERAMIC, segs=16, cap_bottom=True, cap_top=False, edge_deg=45)
    water = p.cyl(0.085, 0.002, (0, 0, 0), M.GLASS, segs=12, uv="box")
    G.xform(water.obj, scale=(1.0, 1.25, 1.0))
    G.xform(water.obj, loc=(0, by - 0.005, 0.255))
    # tank + lid + lever
    p.rbox((0.47, 0.18, 0.37), (0, 0.235, 0.4 + 0.185), M.CERAMIC, radius=0.025, inner=(3, 1, 2), edge_deg=40)
    p.box((0.2, 0.15, 0.04), (0, 0.17, 0.38), M.CERAMIC, bevel=0.01, segs=2)
    lid = p.rbox((0.49, 0.2, 0.03), (0, 0.235, 0.77 + 0.015), M.CERAMIC, radius=0.012, inner=(3, 1, 1), edge_deg=40,
                 tags=("lid",))
    lever = p.tube([(-0.17, 0.142, 0.71), (-0.17, 0.125, 0.71), (-0.1, 0.125, 0.705)], 0.006, M.CHROME, segs=6,
                   fillet_r=0.01, steps=2, tags=("knob",))
    p.tube([(-0.16, 0.36, 0.2), (-0.16, 0.3, 0.2), (-0.16, 0.26, 0.38)], 0.005, M.CHROME, segs=6, fillet_r=0.04, steps=3)
    for sx in (-1, 1):
        p.lathe([(0.016, 0.0), (0.014, 0.012), (0.0, 0.02)], (sx * 0.11, by - 0.06, 0.0), M.CERAMIC, segs=8)
    # seat ring + lid (plastic)
    ring = [(0.13, 0.0), (0.19, 0.0), (0.195, 0.012), (0.185, 0.025), (0.14, 0.025), (0.125, 0.012), (0.13, 0.0)]
    seat = _oval_lathe(p, ring, (0, by - 0.01, 0.392), 1.25, M.PL_WHITE, segs=16, cap_bottom=False, cap_top=False,
                       tags=("seat",), edge_deg=45)
    cover = _oval_lathe(p, [(0.0, 0.0), (0.19, 0.0), (0.195, 0.012), (0.18, 0.024), (0.0, 0.03)], (0, by - 0.01, 0.418), 1.25,
                        M.PL_WHITE, segs=16, cap_bottom=True, cap_top=False, tags=("seat",), edge_deg=45)
    hinge_y = by + 0.2
    if p.cond == "worn":
        p.rotate([cover], rot=(-100, 0, 0), pivot=(0, hinge_y, 0.42))
    if p.destroyed:
        r = p.vrng("wreck")
        # tank lid smashed on the floor, seat torn off, bowl rim chipped
        p.remove([lid])
        h1, h2 = F.split_panel(p, 0.49, 0.2, 0.03, (0, 0, 0), M.CERAMIC, (-0.05, -0.1), (0.07, 0.1), plane="XY",
                               inner=M.CERAMIC, teeth=5, amp=0.02, key="lid")
        p.lay_on_floor([h1], at=(0.45, -0.25), yaw=r.uniform(0, 90))
        p.lay_on_floor([h2], rot=(0, 180, 0), at=(0.55, 0.15), yaw=r.uniform(0, 90))
        p.rotate([cover], rot=(-100, 0, 0), pivot=(0, hinge_y, 0.42))
        p.lay_on_floor([seat], rot=(0, 0, 0), at=(-0.5, -0.35), yaw=r.uniform(0, 60))
        G.splinter_cut(bowl.obj, (0.12, by - 0.2, 0.36), (0.6, -0.6, 0.55), jag=0.015, seed=p.seed,
                       inner_slot=None)
        p.remove([lever])
    p.collider((0, by, 0.2), (0.4, 0.5, 0.4))
    p.collider((0, 0.235, 0.6), (0.49, 0.2, 0.4))


def bathtub(p: Prop) -> None:
    """Cast-iron alcove tub 1.52 x 0.76 x 0.5: one lofted enamel shell (apron and ends, rolled rim, sloped
    basin with a flat floor), chrome drain and overflow plate."""
    W, D, H = 1.52, 0.76, 0.5
    ring = G.rrect_ring
    rings = [ring(W, D, 0.03, 0.0), ring(W, D, 0.03, H - 0.035), ring(W - 0.012, D - 0.012, 0.04, H),
             ring(W - 0.1, D - 0.1, 0.13, H - 0.004), ring(W - 0.13, D - 0.13, 0.16, H - 0.06),
             ring(W - 0.2, D - 0.19, 0.2, 0.26, cx=0.025), ring(W - 0.34, D - 0.29, 0.16, 0.09, cx=0.05),
             ring(W - 0.4, D - 0.33, 0.12, 0.07, cx=0.05)]
    shell = p.add(G.loft(p._name("tub"), rings, cap_bottom=True, cap_top=True), M.TUB, edge_deg=40, uv_scale=1.0)
    if p.worn:
        shell.floor_wear = 0.9  # rust bleeding through chipped enamel on the basin floor and apron foot
    dx = -W / 2 + 0.26
    p.cyl(0.035, 0.004, (dx, 0.0, 0.072), M.CHROME, segs=12)
    p.cyl(0.04, 0.012, (-W / 2 + 0.092, 0.0, 0.36), M.CHROME, axis="X", segs=12)
    p.cyl(0.02, 0.012, (dx + 0.08, 0.06, 0.076), M.RUBBER, segs=8)
    p.collider((0, 0, H / 2), (W, D, H))


def sink_pedestal(p: Prop) -> None:
    """Vitreous-china pedestal sink: rounded basin at 0.84 on a flared column, two-handle chrome faucet."""
    bw, bd, top = 0.56, 0.46, 0.85
    # basin outer (lofted, front bellied) and inner bowl
    outer = [G.rrect_ring(bw * 0.5, bd * 0.45, 0.06, top - 0.2, cy=-0.01),
             G.rrect_ring(bw * 0.8, bd * 0.75, 0.12, top - 0.12, cy=-0.01),
             G.rrect_ring(bw, bd, 0.16, top - 0.03), G.rrect_ring(bw, bd, 0.16, top)]
    p.add(G.loft(p._name("basin"), outer, cap_bottom=True), M.CERAMIC, edge_deg=50)
    inner = [G.rrect_ring(0.14, 0.1, 0.045, top - 0.14, cy=-0.04), G.rrect_ring(0.3, 0.22, 0.09, top - 0.11, cy=-0.04),
             G.rrect_ring(0.42, 0.3, 0.13, top - 0.04, cy=-0.04), G.rrect_ring(0.44, 0.32, 0.14, top + 0.003, cy=-0.04)]
    p.add(G.loft(p._name("bowl"), inner, cap_bottom=True, inward=True), M.CERAMIC, edge_deg=50)
    # deck between outer rim and bowl
    rim_out = G.rrect_ring(bw, bd, 0.16, top)
    rim_in = G.rrect_ring(0.44, 0.32, 0.14, top + 0.003, cy=-0.04)
    p.add(G.loft(p._name("deck"), [rim_in, rim_out], cap_bottom=False, inward=True), M.CERAMIC, edge_deg=50)
    ped = p.lathe([(0.13, 0.0), (0.12, 0.02), (0.085, 0.1), (0.07, 0.4), (0.075, 0.55), (0.11, top - 0.19)], (0, 0.03, 0),
                  M.CERAMIC, segs=14, cap_top=False, edge_deg=45)
    G.xform(ped.obj, scale=(1.0, 0.8, 1.0), matrix=None)
    p.cyl(0.02, 0.004, (0, -0.04, top - 0.139), M.CHROME, segs=10)
    # faucet
    fy = bd / 2 - 0.07
    fau = [p.box((0.16, 0.05, 0.02), (0, fy, top + 0.01), M.CHROME, bevel=0.008, segs=2)]
    for sx in (-0.06, 0.06):
        fau.append(p.lathe([(0.012, 0), (0.013, 0.012), (0.02, 0.025), (0.0, 0.03)], (sx, fy, top + 0.02), M.CHROME,
                           segs=8, tags=("knob",)))
    spout = p.tube([(0, fy, top + 0.02), (0, fy, top + 0.07), (0, fy - 0.09, top + 0.07), (0, fy - 0.1, top + 0.055)], 0.009,
                   M.CHROME, segs=8, fillet_r=0.025, steps=3)
    fau.append(spout)
    if p.worn:
        p.rbox((0.08, 0.05, 0.022), (0.17, fy - 0.02, top + 0.011), M.PL_WHITE, radius=0.01, inner=(1, 1, 1))  # soap
    if p.destroyed:
        r = p.vrng("wreck")
        # the wall-hung basin has torn off and lies on the floor; pedestal toppled beside it
        basin = [q for q in p.parts if q is not ped]
        p.lay_on_floor(basin, rot=(r.uniform(-25, -15), r.uniform(-10, 10), 0), at=(-0.15, -0.35), yaw=r.uniform(-30, 30))
        p.lay_on_floor([ped], rot=(0, 90, 0), at=(0.45, 0.05), yaw=r.uniform(-20, 20))
        p.collider((0, -0.1, 0.15), (0.9, 0.7, 0.3))
        return
    p.collider((0, 0.0, top / 2), (bw, bd, top))


def medicine_cabinet(p: Prop) -> None:
    """Surface-mounted medicine cabinet (wall, origin on the wall plane): white steel box, mirror door with
    a chrome frame, glass shelves with bottles. 0.42 x 0.13 x 0.62."""
    W, D, H = 0.42, 0.12, 0.62
    p.hollow((W, D, H), (0, -D / 2, H / 2), M.STEEL_WHITE, wall=0.012, open_face="-Y", bevel=0.004, grain="Z")
    r = p.rng("bottles")
    for z in (0.2, 0.4):
        p.box((W - 0.03, D - 0.03, 0.006), (0, -D / 2 + 0.005, z), M.GLASS, bevel=0.0)
    for zi, z in enumerate((0.012, 0.203, 0.403)):
        x = -W / 2 + 0.05
        while x < W / 2 - 0.05:
            k = r.random()
            if k < 0.45:
                hh = r.uniform(0.06, 0.1)
                p.cyl(0.018, hh, (x, -D / 2, z + hh / 2), M.PL_RED, segs=8)
                p.cyl(0.019, 0.015, (x, -D / 2, z + hh + 0.0075), M.PL_WHITE, segs=8)
            elif k < 0.75:
                F.package_box(p, (0.05, 0.03, 0.09), (x, -D / 2, z + 0.045), r.randrange(14))
            elif k < 0.9:
                p.lathe([(0.02, 0.0), (0.022, 0.11), (0.012, 0.13), (0.012, 0.15), (0.0, 0.15)], (x, -D / 2, z), M.PL_BLUE,
                        segs=8)
            x += r.uniform(0.05, 0.08)
    yd = -D - 0.02
    door = [p.box((W + 0.01, 0.02, H + 0.01), (0, -D - 0.01, H / 2), M.CHROME, bevel=0.005, segs=2, tags=("door",))]
    if p.destroyed:
        door += F.shatter_pane(p, W - 0.03, H - 0.03, (0, yd - 0.002, H / 2), M.MIRROR, t=0.004, impact=(0.03, 0.06),
                               spokes=11, rings=3, key="mirror", missing_inner=0.9, missing_outer=0.2)
    else:
        door.append(p.box((W - 0.03, 0.004, H - 0.03), (0, yd - 0.002, H / 2), M.MIRROR, bevel=0.0, uv="planar",
                          uv_axis="Y"))
    ang = 0.0
    if p.cond == "worn":
        ang = p.vrng("door").choice([0.0, 8.0, 25.0])
    if ang:
        F.swing(p, door, W / 2 + 0.005, -D, ang)
    if p.destroyed:
        F.hang(p, door, W / 2 + 0.005, -D, H - 0.05, open_deg=110, sag_deg=8, hinge="right")
    p.collider((0, -(D + 0.02) / 2, H / 2), (W, D + 0.02, H))


def towel_rack(p: Prop) -> None:
    """Chrome towel bar (wall, origin on the wall plane at the towel's bottom) with a towel folded over it."""
    L, out, zb = 0.6, 0.07, 0.42
    for sx in (-1, 1):
        p.lathe([(0.024, 0.0), (0.02, 0.006), (0.012, 0.012), (0.012, out - 0.012), (0.016, out)], (sx * L / 2, 0.0, zb),
                M.CHROME, segs=10, axis="-Y")
    p.cyl(0.009, L + 0.01, (0, -out + 0.012, zb), M.CHROME, axis="X", segs=10)
    shift = (0.0, 0.0) if p.cond == "clean" else (p.vrng("towel").uniform(-0.08, 0.08), 0.0)
    F.drape(p, -0.22, 0.22, -out + 0.004, -out + 0.02, zb + 0.009, M.TOWEL, hang=(0.0, 0.0, 0.4, 0.36), res=0.045,
            wrinkle=0.014 if p.cond == "clean" else 0.022, seed=p.seed, thickness=0.012, shift=shift, floor=0.0)
    p.collider((0, -0.05, zb / 2 + 0.03), (L + 0.05, 0.1, zb + 0.06))


BUILDERS = {
    "toilet": toilet,
    "bathtub": bathtub,
    "sink_pedestal": sink_pedestal,
    "medicine_cabinet": medicine_cabinet,
    "towel_rack": towel_rack,
}


def build(params: dict, outputs: list[str]) -> None:
    core.build_variants(params, outputs, BUILDERS[params["prop"]])
