"""Player-built log pieces and blueprint ghosts.

log_piece: 4.0 m along X, d = 0.34 m, origin at the CENTRE (physics object). Bark, sawn end grain,
a cove scribed along the underside and saddle notches near both ends (cylindrical cuts sized for the
guidebook layouts: logs 0.29 m apart vertically, crossing logs at x = +-1.83). Cut surfaces use
item_wood_raw. Variants: reinforced (rope lashings + iron straps with bolts), frac (Voronoi chunks via
lib.fracture, inner item_wood_inner). Ghosts: simple merged logs at the blueprint piece transforms
(Godot coordinates converted to Blender: (x, y, z) -> (x, -z, y)), origin = blueprint origin.
"""
from __future__ import annotations

import math

import bpy
from mathutils import Matrix, Vector, noise

from lib import common, fracture, item_kit as K

LEN, RAD = 4.0, 0.17
NOTCH_X = 1.83          # crossing-log centre lines (cabin walls at +-1.83 m)
STEP = 0.29             # vertical spacing of stacked / crossing logs
CUT_R = 0.176           # cutter radius (log radius + clearance)


def _ring_positions():
    xs = set()
    xs.update([-LEN / 2, -LEN / 2 + 0.012, LEN / 2 - 0.012, LEN / 2])
    for sgn in (1, -1):
        c = sgn * NOTCH_X
        for k in range(-7, 8):
            xs.add(round(c + k * 0.022, 4))
    x = -LEN / 2 + 0.12
    while x < LEN / 2 - 0.1:
        if all(abs(x - sgn * NOTCH_X) > 0.17 for sgn in (1, -1)):
            xs.add(round(x, 4))
        x += 0.24
    return sorted(v for v in xs if -LEN / 2 <= v <= LEN / 2)


def log_mesh(name: str, seed: int, *, sides: int = 16, notches: bool = True, cove: bool = True) -> bpy.types.Object:
    r = common.rng(seed)
    noise.seed_set(seed)
    mb = K.MB()
    xs = _ring_positions()
    pts, radii = [], []
    a1, a2 = r.uniform(0, 6.28), r.uniform(0, 6.28)
    for x in xs:
        t = (x + LEN / 2) / LEN
        wob = Vector((0, 0.005 * math.sin(t * 2.3 + a1), 0.004 * math.sin(t * 1.7 + a2)))
        pts.append(Vector((x, 0, 0)) + wob)
        rr = RAD * (1.0 + 0.018 * math.sin(t * 9.0 + a1) + 0.012 * noise.noise(Vector((t * 6.0, 0.4, 0.2))))
        if abs(abs(x) - LEN / 2) < 0.013:
            rr *= 0.965 if abs(x) < LEN / 2 else 0.93       # broken bark edge at the cut
        radii.append(rr)
    rings = K.tube(mb, pts, radii, sides=sides, mat="item_bark", cap_mat="item_wood_end", cap_uv="disc",
                   rot=r.uniform(0, 6.28), up=Vector((0, 0, 1)))
    # slight saw-cut angle on each end
    for end, sgn in ((0, -1), (-1, 1)):
        tilt = Vector((r.uniform(-0.02, 0.02), r.uniform(-0.02, 0.02)))
        for vi in rings[end]:
            c = mb.co[vi]
            mb.co[vi] = Vector((c.x + c.y * tilt.x + c.z * tilt.y, c.y, c.z))
    cut = set()
    for i, c in enumerate(mb.co):
        z_new = None
        if cove and c.y * c.y + (c.z + STEP) ** 2 < CUT_R ** 2:
            z_new = -STEP + math.sqrt(max(0.0, CUT_R ** 2 - c.y * c.y))
        if notches:
            for sgn in (1, -1):
                dx = c.x - sgn * NOTCH_X
                if dx * dx + (c.z + STEP) ** 2 < CUT_R ** 2:
                    zn = -STEP + math.sqrt(max(0.0, CUT_R ** 2 - dx * dx))
                    z_new = zn if z_new is None else max(z_new, zn)
        if z_new is not None and z_new > c.z:
            mb.co[i] = Vector((c.x, c.y, z_new))
            cut.add(i)
    for fi, f in enumerate(mb.faces):
        if mb.fmat[fi] == "item_bark" and sum(1 for v in f if v in cut) >= 3:
            mb.fmat[fi] = "item_wood_raw"
            mb.fuv[fi] = [(mb.co[v].x * 1.0, mb.co[v].y * 1.0) for v in f]
    return mb.build(name, sharp_deg=50)


def log_piece(p, outputs):
    obj = log_mesh("log_piece", int(p["seed"]))
    K.publish(outputs, name="log_piece", parts=[obj], seed=int(p["seed"]), keep_origin=True, wear_deg=35.0, ao_dist=0.25)


def log_piece_reinforced(p, outputs):
    seed = int(p["seed"])
    obj = log_mesh("log_piece_reinforced", seed)
    mb = K.MB()
    # rope lashings outboard of the notches
    for k, x in enumerate((-1.48, 1.48)):
        K.lashing(mb, (x - 0.05, 0, 0), (x + 0.05, 0, 0), RAD * 1.01, cord=0.0065, turns=6, per_turn=10, sides=4, mat="item_rope",
                  phase=k * 1.3, up=Vector((0, 0, 1)), wobble=0.002, seed=seed + k)
    # forged iron straps with bolts
    for k, x in enumerate((-0.72, 0.72)):
        loop = []
        for i in range(28):
            a = 2 * math.pi * i / 28
            rr = RAD * 1.012
            y, z = math.cos(a) * rr, math.sin(a) * rr
            if y * y + (z + STEP) ** 2 < CUT_R ** 2:
                z = -STEP + math.sqrt(max(0.0, CUT_R ** 2 - y * y)) + 0.004
            loop.append(Vector((x, y, z)))
        K.tube(mb, loop, (0.022, 0.0035), profile=K.rect_profile(1, 1, 0.25), mat="item_iron_strap", closed=True, up=Vector((1, 0, 0)))
        for a in (math.radians(25), math.radians(155), math.radians(90)):
            y, z = math.cos(a) * (RAD + 0.0045), math.sin(a) * (RAD + 0.0045)
            n = Vector((0, math.cos(a), math.sin(a)))
            m = Matrix.Translation((x, y, z)) @ n.to_track_quat("Z", "X").to_matrix().to_4x4()
            mb.push(m)
            K.lathe(mb, [(0.012, 0.0), (0.012, 0.004), (0.008, 0.008)], segments=6, mat="item_iron_strap", cap_bottom=False, cap_top=True)
            mb.pop()
    hw = mb.build("hardware", sharp_deg=45)
    K.publish(outputs, name="log_piece_reinforced", parts=[obj, hw], seed=seed, keep_origin=True, wear_deg=35.0, ao_dist=0.25)


def log_piece_frac(p, outputs):
    seed = int(p["seed"])
    src = log_mesh("log_src", seed)          # identical to log_piece so the chunks swap in seamlessly
    chunks = fracture.fracture(src, int(p.get("pieces", 9)), int(p.get("frac_seed", seed)), "item_wood_inner", margin=0.003,
                               bias=(1.0, 0.55, 0.55))
    bpy.data.objects.remove(src, do_unlink=True)
    bpy.context.view_layer.update()
    for ch in chunks:
        me = ch.data
        inner = [i for i, m in enumerate(me.materials) if m is not None and m.name == "M_item_wood_inner"]
        uvl = me.uv_layers.active or me.uv_layers.new(name="UVMap")
        for poly in me.polygons:
            if poly.material_index in inner:
                n = poly.normal
                ax = max(range(3), key=lambda i: abs(n[i]))
                for li in poly.loop_indices:
                    co = me.vertices[me.loops[li].vertex_index].co + ch.location
                    u, v = ((co.y, co.z) if ax == 0 else (co.x, co.z) if ax == 1 else (co.x, co.y))
                    uvl.data[li].uv = (u, v)
        K.mark_sharp(ch, 40.0)
        K.bake_wear_and_masks(ch, wear_deg=30.0, seed=seed)
    K.bake_ao(chunks, ground=False, dist=0.2, samples=16)
    K.export_objects(outputs[0], chunks)
    print(f"[item_kit] log_piece_frac: {K.tri_count(chunks)} tris in {len(chunks)} chunks -> {outputs[0]}")


def _godot_to_blender(pos, rot_deg) -> Matrix:
    gx, gy, gz = pos
    rx, ry, rz = (math.radians(a) for a in rot_deg)
    # Godot Euler YXZ: R = Ry * Rx * Rz ; axes map Godot X->X, Y->Z, Z->-Y
    R = Matrix.Rotation(ry, 4, "Z") @ Matrix.Rotation(rx, 4, "X") @ Matrix.Rotation(-rz, 4, "Y")
    return Matrix.Translation((gx, -gz, gy)) @ R


def ghost(p, outputs):
    seed = int(p["seed"])
    mb = K.MB()
    for k, piece in enumerate(p["pieces"]):
        m = _godot_to_blender(piece["pos"], piece.get("rot", [0, 0, 0]))
        mb.push(m)
        pts = [Vector((-LEN / 2 + LEN * i / 5, 0, 0)) for i in range(6)]
        K.tube(mb, pts, RAD * 0.98, sides=12, mat="item_ghost", cap_mat="item_ghost", rot=0.13 * k)
        mb.pop()
    obj = mb.build(p["name"], sharp_deg=50)
    K.publish(outputs, name=p["name"], parts=[obj], seed=seed, keep_origin=True, inset=False, ao_dist=0.3, ao_samples=12)


BUILDERS = {"log_piece": log_piece, "log_piece_reinforced": log_piece_reinforced, "log_piece_frac": log_piece_frac, "ghost": ghost}


def build(params: dict, outputs: list[str]) -> None:
    BUILDERS[params["kind"]](params, outputs)
