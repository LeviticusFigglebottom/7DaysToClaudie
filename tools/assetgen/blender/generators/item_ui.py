"""Inventory / UI props: the salvage roll (inventory mat), the work slate (crafting board) and the
Program supply-drop canister (lid is a separate node named "lid", origin at its bottom centre).
params: kind, name, seed."""
from __future__ import annotations

import math

from mathutils import Matrix, Vector, geometry, noise

from lib import common, item_kit as K

# Keep in sync with textures/gen/items.py (ROLL_*): the top print is mapped u=(x+W/2)/W, v=(y+D/2)/D.
ROLL_W, ROLL_D = 1.4, 0.9
ROLL_HEM = 0.03
ROLL_POCKET_Y = (-0.42, -0.17)
ROLL_POCKETS = [0.10, 0.16, 0.20, 0.14, 0.24, 0.18, 0.16, 0.16]
ROLL_FLAP_Y = 0.30


def _roll_uv(x, y):
    return ((x + ROLL_W / 2) / ROLL_W, (y + ROLL_D / 2) / ROLL_D)


def salvage_roll(p):
    seed = int(p["seed"])
    noise.seed_set(seed)
    mb = K.MB()
    T = 0.006

    def base(u, v):
        x, y = (u - 0.5) * ROLL_W, (v - 0.5) * ROLL_D
        z = T / 2 + 0.0025 * noise.noise(Vector((u * 3, v * 3, 0.5)))
        edge = min(u, 1 - u) * ROLL_W
        z += 0.004 * max(0.0, 1 - edge / 0.05) ** 2          # rolled ends lift a little
        if y > ROLL_FLAP_Y:
            z += 0.0015
        return Vector((x, y, z))
    K.sheet(mb, 16, 10, base, thickness=T, mat_top="item_salvage_roll", mat_bottom="item_canvas_olive", mat_edge="item_canvas_olive",
            uv_bottom=lambda u, v: ((u - 0.5) * ROLL_W, (v - 0.5) * ROLL_D))
    # sewn pockets: puffy panels whose top print lines up with the base print
    x = -ROLL_W / 2 + ROLL_HEM
    py0, py1 = ROLL_POCKET_Y
    r = common.rng(seed)
    for i, w in enumerate(ROLL_POCKETS):
        x0, x1 = x + 0.004, x + w - 0.004
        x += w
        puff = r.uniform(0.004, 0.009)

        def pocket(u, v, x0=x0, x1=x1, puff=puff):
            px = x0 + (x1 - x0) * u
            py = py0 + 0.006 + (py1 - 0.006 - py0 - 0.006) * v
            z = T + 0.0018 + puff * math.sin(math.pi * u) * math.sin(math.pi * min(1.0, v * 1.15)) ** 0.6 + 0.003 * v ** 3
            return Vector((px, py, z + 0.0025 * noise.noise(Vector((px * 30, py * 30, 1.0)))))
        K.sheet(mb, 4, 3, pocket, thickness=0.0018, mat_top="item_salvage_roll", mat_bottom="item_canvas_olive", mat_edge="item_canvas_olive",
                uv_top=lambda u, v, pf=pocket: _roll_uv(pf(u, v).x, pf(u, v).y))
    # tie straps sewn to the right end, buckles lying on the ground beyond the edge
    for k, y in enumerate((-0.05, 0.16)):
        path = [Vector((0.6, y, T + 0.0012)), Vector((0.69, y, T + 0.0012)), Vector((0.715, y + 0.003, 0.004)),
                Vector((0.74, y + 0.008 * (k - 0.5), 0.0014)), Vector((0.84 + 0.03 * k, y + 0.02 * (k - 0.5), 0.0012))]
        K.tube(mb, path, (0.0125, 0.0011), profile=K.rect_profile(1, 1, 0.3), mat="item_webbing", up=Vector((0, 0, 1)))
        end = path[-1]
        mb.push(Matrix.Translation(end + Vector((0.012, 0, 0.0012))))
        K.extrude(mb, [(-0.012, -0.017), (0.012, -0.017), (0.012, 0.017), (-0.012, 0.017)], 0.0024,
                  holes=[[(-0.008, -0.013), (0.008, -0.013), (0.008, 0.013), (-0.008, 0.013)]], mat="item_steel_dark", uv_scale=10.0)
        mb.pop()
    return [mb.build("salvage_roll", sharp_deg=None)], {"settle": None, "keep_xy": True}


def work_slate(p):
    seed = int(p["seed"])
    r = common.rng(seed)
    mb = K.MB()
    W, D, T = 0.6, 0.4, 0.018
    f0 = len(mb.faces)
    K.box(mb, (W, D, T), (0, 0, T / 2), mat="item_plywood", bevel=0.0018)
    for fi in range(f0, len(mb.faces)):
        vs = [mb.co[i] for i in mb.faces[fi]]
        n = geometry.normal(vs)
        if abs(n.z) < 0.7:
            mb.fmat[fi] = "item_plywood_edge"
    # chipped corners: nudge corner verts in a little
    for i in range(len(mb.co)):
        c = mb.co[i]
        if abs(abs(c.x) - W / 2) < 0.004 and abs(abs(c.y) - D / 2) < 0.004 and c.z > T * 0.5:
            mb.co[i] = c - Vector((math.copysign(r.uniform(0.0, 0.004), c.x), math.copysign(r.uniform(0.0, 0.004), c.y), r.uniform(0.0, 0.002)))
    # a couple of drywall screws left in the board
    for (x, y) in ((-0.27, 0.17), (0.255, -0.165)):
        mb.push(Matrix.Translation((x, y, T)))
        K.lathe(mb, [(0.0042, 0.0), (0.0040, 0.0009), (0.0028, 0.0014)], segments=10, mat="item_steel_dark", cap_bottom=False, cap_top=True)
        mb.pop()
    return [mb.build("work_slate", sharp_deg=40)], {"settle": None}


def supply_canister(p):
    seed = int(p["seed"])
    noise.seed_set(seed)
    mb = K.MB()
    R = 0.278
    # band rings at fixed heights so the stencil regions can address them
    prof = [(0.22, 0.0), (0.268, 0.004), (0.287, 0.014), (0.29, 0.05), (0.282, 0.062), (R, 0.072),
            (R, 0.12), (R, 0.22)]                                  # lower stencil band 0.12..0.22 -> segment 6
    prof += [(R, 0.236), (R + 0.007, 0.243), (R + 0.007, 0.257), (R, 0.264)]
    prof += [(R, 0.536), (R + 0.007, 0.543), (R + 0.007, 0.557), (R, 0.564)]
    prof += [(R, 0.836), (R + 0.007, 0.843), (R + 0.007, 0.857), (R, 0.864)]
    i_up0 = len(prof)
    prof += [(R, 0.90), (R, 1.0)]                                  # upper stencil band 0.90..1.00
    prof += [(R, 1.055), (0.287, 1.062), (0.287, 1.082), (0.27, 1.088), (0.2, 1.088)]
    regions = [(6, 7, "item_stencil_band", "label", 4.0), (i_up0, i_up0 + 1, "item_stencil_band", "label", 4.0)]
    K.lathe(mb, prof, segments=28, mat="item_paint_olive", regions=regions, cap_bottom=True, cap_top=True,
            radial_fn=lambda k, i, rr, z: 1.0 - 0.012 * max(0.0, noise.noise(Vector((math.cos(k * 0.224) * 3, math.sin(k * 0.224) * 3, z * 4)))))
    # carry handles (two sides) and over-centre latches at the rim
    for a in (0.0, math.pi):
        rot = Matrix.Rotation(a, 4, "Z")
        mb.push(rot)
        hp = [Vector((R - 0.004, -0.085, 0.70)), Vector((R + 0.05, -0.075, 0.70)), Vector((R + 0.05, 0.075, 0.70)), Vector((R - 0.004, 0.085, 0.70))]
        hp = K.polyline_resample([hp[0], hp[1], hp[2], hp[3]], 12)
        K.tube(mb, hp, 0.009, sides=8, mat="item_steel_dark")
        for y in (-0.085, 0.085):
            K.box(mb, (0.02, 0.032, 0.05), (R + 0.004, y, 0.70), mat="item_steel_dark", bevel=0.003)
        mb.pop()
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        mb.push(Matrix.Rotation(a, 4, "Z"))
        K.box(mb, (0.022, 0.04, 0.07), (R + 0.006, 0.0, 1.035), mat="item_steel_tool", bevel=0.003)
        mb.push(Matrix.Translation((R + 0.02, 0.0, 1.05)) @ Matrix.Rotation(math.radians(-12), 4, "Y"))
        K.box(mb, (0.012, 0.028, 0.075), (0, 0, 0), mat="item_steel_tool", bevel=0.003)
        mb.pop()
        mb.pop()
    # riser D-rings for the parachute lines (+X side)
    for y in (-0.06, 0.06):
        ring = [Vector((R + 0.02 + math.cos(t) * 0.022, y, 0.96 + math.sin(t) * 0.022)) for t in [2 * math.pi * k / 12 for k in range(12)]]
        K.tube(mb, ring, 0.004, sides=6, mat="item_steel_tool", closed=True)
    body = mb.build("canister", sharp_deg=40)
    # lid: dome with a cream stencil ring and a lifting eye
    lm = K.MB()
    lprof = [(0.2, 0.0), (0.289, 0.0), (0.292, 0.012), (0.292, 0.03), (0.282, 0.046), (0.25, 0.062), (0.2, 0.075), (0.15, 0.083),
             (0.09, 0.088), (0.05, 0.09)]
    K.lathe(lm, lprof, segments=28, mat="item_paint_olive", regions=[(5, 6, "item_paint_stripe", "metric")], cap_bottom=True, cap_top=True)
    eye = [Vector((math.cos(t) * 0.035, 0.0, 0.09 + 0.03 + math.sin(t) * 0.03)) for t in [2 * math.pi * k / 16 for k in range(16)]]
    K.tube(lm, eye, 0.0075, sides=8, mat="item_steel_dark", closed=True)
    K.lathe(lm, [(0.03, 0.088), (0.03, 0.098), (0.018, 0.104)], segments=12, mat="item_steel_dark", cap_bottom=False, cap_top=True)
    lid = lm.build("lid", sharp_deg=40)
    lid.data.transform(Matrix.Translation((0, 0, 1.088)))
    # collapsed parachute heap beside it + suspension lines to the D-rings
    chute = K.pebble("chute_tmp", (0.78, 0.6, 0.26), seed + 3, mat="item_parachute", subdiv=4, flat_bottom=0.45, lump=0.18,
                     center=(0.74, 0.12, 0.0))
    mod = chute.modifiers.new("dec", "DECIMATE")
    mod.ratio = 0.55
    common.apply_modifiers(chute)
    me = chute.data
    for v in me.vertices:
        q = v.co
        fold = (1 - abs(noise.noise(q * 9.0))) ** 3 * 0.035 + noise.fractal(q * 4.0, 0.5, 2.0, 3) * 0.02
        if q.z > 0.02:
            v.co += Vector((0, 0, fold))
    me.update()
    lines = K.MB()
    for k in range(6):
        y = -0.06 if k < 3 else 0.06
        a = Vector((R + 0.035, y, 0.94))
        b = Vector((0.62 + 0.05 * (k % 3), 0.02 + 0.04 * k, 0.16 + 0.02 * (k % 2)))
        path = K.bezier(a, a + Vector((0.08, 0.0, -0.05)), b + Vector((-0.1, 0.0, 0.15)), b, 10)
        K.tube(lines, path, 0.0032, sides=4, mat="item_rope", u_tile=1.0, v_scale=1.0 / (2 * math.pi * 0.0032) / 3)
    lines_obj = lines.build("lines", sharp_deg=None)
    return [body, chute, lines_obj], {"settle": None, "keep_xy": True, "separate": [lid], "pivot_bottom": ("lid",)}


BUILDERS = {"salvage_roll": salvage_roll, "work_slate": work_slate, "supply_canister": supply_canister}


def build(params: dict, outputs: list[str]) -> None:
    parts, opts = BUILDERS[params["kind"]](params)
    K.publish(outputs, name=params.get("name", params["kind"]), parts=parts, seed=int(params["seed"]),
              settle_deg=opts.get("settle", None), keep_xy=opts.get("keep_xy", False), separate=opts.get("separate", ()),
              pivot_bottom=opts.get("pivot_bottom", ()))
