"""The companion's body (ADR-0058, Ezra Vane): a living human (lib/npc_build: the Hollowed body
pipeline without the infection) dressed as a lineman in Program fatigues, with the living
fighter's clips under the Hollowed's action names (lib/living_anim, so the Enemy plays him like the
Ashen), the trader's talk and look (lib/npc_anim) and his own downed, revive and sit_injured
(lib/companion_anim). Same skeleton, segments and stump caps as every body (docs/CHARACTERS.md).

Rigid gear joined into the segments that carry it, each weighted wholly to one bone (as
character_living joins the Ashen's axe):
  * a lineman's hatchet in the right fist (item_tools.hatchet, character_living.add_weapon);
  * a canvas pack on his back (body_torso, `chest`), a white hard hat clipped to its flap;
  * climbing spurs (gaffs) on the inside of both boots: a steel shank up the inside of the shin
    with the gaff at the instep, two leather straps round the calf (body_shin.*, `shin.*`).
Props the game shows or hides by what he is doing (TD-302), separate skinned meshes named prop_*
(EnemyVisual.set_part), each weighted wholly to one bone:
  * prop_hatchet_hand: the hatchet in his right fist (fighting, chopping);
  * prop_hatchet_belt: the same hatchet hung head-up from his belt on the right hip (the rest of
    the time);
  * prop_lantern: a hurricane lantern in his left fist (at night, following);
  * prop_splint: two slats bound to his left shin with strips of cloth (at his camp, unrecruited).
The harness is dressing params (leather straps over the shoulders, the belt on the trousers).

params: the character_npc params (height, sex, build, outfit, boots, hair, beard, remap, ...)
plus "weapon" (character_living.WEAPONS or "hatchet") and "gear" {"pack": bool, "hard_hat": bool,
"spurs": bool}. See tools/assetgen/blender_catalogs/companions.py.
"""
from __future__ import annotations

import math

import bpy
import numpy as np
from mathutils import Matrix, Vector

from generators import character_living as CL
from generators import item_tools
from lib import char_build as CB, companion_anim, export, item_kit as IK, living_anim, npc_anim, npc_build, vcolor
from lib.char_dress import surface_hit


def _hatchet(seed: int) -> bpy.types.Object:
    """The tool hatchet (items/hatchet's model), grip at the origin, haft +Z, bit -Y."""
    objs, sockets = item_tools.hatchet({"seed": seed})
    for s in sockets:
        bpy.data.objects.remove(s, do_unlink=True)
    obj = objs[0]
    IK.bake_wear_and_masks(obj, wear_deg=30.0, seed=seed)
    return obj


CL.WEAPONS.setdefault("hatchet", (_hatchet, 46.0))


def _attach(obj: bpy.types.Object, seg_name: str, bone: str, objs: list) -> None:
    """Joins a rigid prop into a body segment, weighted wholly to `bone` (like add_weapon)."""
    seg = next(o for o in objs if o.name == seg_name)
    obj.data.uv_layers[0].name = seg.data.uv_layers[0].name
    vcolor.ensure_layer(obj)
    vg = obj.vertex_groups.new(name=bone)
    vg.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
    obj.parent = seg.parent
    with bpy.context.temp_override(active_object=seg, selected_editable_objects=[seg, obj], object=seg):
        bpy.ops.object.join()


def _built(mb: IK.MB, name: str, seed: int) -> bpy.types.Object:
    obj = mb.build(name, sharp_deg=40)
    IK.bake_wear_and_masks(obj, wear_deg=30.0, seed=seed)
    return obj


def _pack(model, skel, seed: int, hard_hat: bool) -> bpy.types.Object:
    """A canvas rucksack high on his back (the body's back is +Y), its flap buckled down, a rolled
    groundsheet strapped under it, and a white hard hat clipped to the flap by its brim."""
    s = model.s
    j = skel.j
    mid = (np.array(j["chest0"]) * 0.45 + np.array(j["neck0"]) * 0.55)
    back, _n = surface_hit(model, mid, np.array([0.0, 1.0, 0.0]), max_dist=0.35)
    back = Vector(back.tolist())
    w, d, h = 0.34 * s, 0.17 * s, 0.44 * s
    lean = math.radians(8.0)      # the top sits closer to the shoulders than the bottom
    cz = back.z - h * 0.22
    c = Vector((0.0, back.y + d * 0.5 + 0.012 * s, cz))
    mb = IK.MB()
    IK.box(mb, (w, d, h), (0, 0, 0), mat="item_canvas_olive", bevel=0.03 * s)
    # the flap over the top and its two buckled straps down the front (the face away from him)
    IK.box(mb, (w * 0.96, d * 1.04, 0.07 * s), (0, 0.004 * s, h * 0.5 - 0.02 * s), mat="item_canvas_olive", bevel=0.015 * s)
    for sx in (-1, 1):
        IK.box(mb, (0.028 * s, 0.006 * s, h * 0.42), (sx * w * 0.24, d * 0.5 + 0.003 * s, h * 0.24), mat="item_webbing")
        IK.box(mb, (0.034 * s, 0.009 * s, 0.03 * s), (sx * w * 0.24, d * 0.5 + 0.006 * s, h * 0.08), mat="item_steel_dark")
    # side pockets
    for sx in (-1, 1):
        IK.box(mb, (0.05 * s, d * 0.7, h * 0.36), (sx * (w * 0.5 + 0.022 * s), 0.0, -h * 0.18), mat="item_canvas_olive", bevel=0.012 * s)
    # the rolled groundsheet under it
    roll = [Vector((-w * 0.55, 0.0, -h * 0.5 - 0.05 * s)), Vector((w * 0.55, 0.0, -h * 0.5 - 0.05 * s))]
    IK.tube(mb, roll, 0.055 * s, sides=10, mat="item_canvas_tan")
    parts = [_built(mb, "pack", seed)]
    if hard_hat:
        hb = IK.MB()
        prof = [(0.140, 0.0), (0.142, 0.008), (0.112, 0.012), (0.106, 0.05), (0.094, 0.09), (0.07, 0.118),
                (0.038, 0.132), (0.01, 0.136)]
        IK.lathe(hb, [(r * s, z * s) for r, z in prof], segments=20, mat="item_plastic_white")
        # the ridge along the crown
        IK.box(hb, (0.016 * s, 0.17 * s, 0.014 * s), (0, 0, 0.128 * s), mat="item_plastic_white", bevel=0.005 * s)
        hat = _built(hb, "hard_hat", seed + 3)
        # crown outward, brim clipped over the flap: tipped back against the pack's face, lower half
        hat.data.transform(Matrix.Translation((0.0, d * 0.5 + 0.004 * s, -h * 0.12)) @ Matrix.Rotation(math.radians(-80.0), 4, "X"))
        parts.append(hat)
    obj = IK.join(parts, "pack") if len(parts) > 1 else parts[0]
    obj.data.transform(Matrix.Translation(c) @ Matrix.Rotation(-lean, 4, "X"))
    return obj


def _spur(model, skel, side: str, seed: int) -> bpy.types.Object:
    """A lineman's climbing spur on the inside of one leg: a flat steel shank from the instep up
    the inside of the shin to below the knee, the gaff (a short spike) pointing down at the instep,
    a stirrup under the boot's arch, two leather straps round the calf."""
    s = model.s
    j = skel.j
    sx = 1.0 if side == "L" else -1.0
    ankle = np.array(j[f"ankle.{side}"])
    knee = np.array(j[f"knee.{side}"])
    axis = knee - ankle
    length = float(np.linalg.norm(axis))
    up = axis / length
    inward = np.array([-sx, 0.0, 0.0])
    inward -= up * float(np.dot(inward, up))
    inward /= np.linalg.norm(inward)
    fwd = np.cross(up, inward) * (1.0 if side == "L" else -1.0)
    mb = IK.MB()
    shank_lo, shank_hi = 0.02 * s, length * 0.72
    IK.box(mb, (0.006 * s, 0.024 * s, shank_hi - shank_lo), (0, 0, (shank_lo + shank_hi) * 0.5), mat="item_steel_dark")
    # the gaff: a tapered spike down and a little forward off the shank's foot
    IK.tube(mb, [Vector((0, -0.008 * s, shank_lo + 0.01 * s)), Vector((0, -0.03 * s, shank_lo - 0.05 * s))], 0.006 * s,
            sides=6, mat="item_steel_bright")
    # the stirrup under the arch and the straps round the calf
    for z, r in ((shank_hi * 0.32, 0.058), (shank_hi * 0.92, 0.066)):
        ring = [Vector((math.cos(a) * r * s - r * s * 0.85, math.sin(a) * r * s * 0.92, z))
                for a in np.linspace(0.0, 2.0 * math.pi, 14, endpoint=False)]
        IK.tube(mb, ring, 0.006 * s, sides=4, mat="item_leather", closed=True)
    obj = _built(mb, f"spur_{side}", seed + (7 if side == "L" else 11))
    # local frame: X inward, Y forward, Z up the shin; origin at the ankle on the inner surface
    edge, _nrm = surface_hit(model, ankle + up * 0.06 * s, inward, max_dist=0.2)
    origin = np.array(edge) - up * 0.06 * s + inward * 0.004 * s
    m = Matrix.Identity(4)
    for i in range(3):
        m[i][0], m[i][1], m[i][2], m[i][3] = float(inward[i]), float(-fwd[i]), float(up[i]), float(origin[i])
    obj.data.transform(m)
    return obj


def _frame(origin, x, y, z) -> Matrix:
    m = Matrix.Identity(4)
    for i in range(3):
        m[i][0], m[i][1], m[i][2], m[i][3] = float(x[i]), float(y[i]), float(z[i]), float(origin[i])
    return m


def _fist_l(skel) -> Matrix:
    """The rest-pose left fist, as character_living._fist is the right: item frame -> body (item +Z
    out of the thumb side, -Y along the hand, the grip in the palm)."""
    j = skel.j
    wr, tip, back = (np.array(j[k]) for k in ("wrist.L", "hand_tip.L", "palm_back.L"))
    f = tip - wr
    hl = float(np.linalg.norm(f))
    f /= hl
    b = back - wr
    b -= f * float(np.dot(b, f))
    b /= np.linalg.norm(b)
    t = np.cross(f, b)            # the left thumb's side (mirrored)
    x = np.cross(-f, t)
    grip = wr + f * hl * 0.42 - b * 0.024
    return _frame(grip, x, -f, t)


def _hatchet_belt(model, skel, seed: int) -> bpy.types.Object:
    """The hatchet hung from his belt on the right hip: through a leather loop, head up at the belt,
    haft down the outside of the thigh, the bit to the back."""
    s = model.s
    j = skel.j
    h = _hatchet(seed)
    hip = np.array(j["hip.R"])
    belt_z = float(np.array(j["pelvis"])[2]) + 0.04 * s
    at = np.array([hip[0], hip[1], belt_z])
    side, _n = surface_hit(model, at + np.array([0.0, 0.0, 0.0]), np.array([-1.0, 0.0, 0.0]), max_dist=0.4)
    side = np.array(side) + np.array([-0.022 * s, 0.01 * s, 0.0])
    # the item's grip is its origin and the haft runs +Z to the head: hang it head up with the head
    # at the belt, so the grip sits a haft's length below it
    head = max(v.co.z for v in h.data.vertices)
    m = Matrix.Translation(Vector(side.tolist()) + Vector((0.0, 0.0, -head + 0.03 * s))) @ Matrix.Rotation(math.radians(180.0), 4, "Z")
    h.data.transform(m)
    loop = IK.MB()
    IK.box(loop, (0.012 * s, 0.05 * s, 0.07 * s), (float(side[0]) + 0.006 * s, float(side[1]), belt_z - 0.02 * s), mat="item_leather")
    lo = _built(loop, "belt_loop", seed + 5)
    return IK.join([h, lo], "prop_hatchet_belt")


def _lantern(seed: int) -> bpy.types.Object:
    """A hurricane lantern hanging from its bail: a tin fount, a clear glass globe in a wire guard,
    a vented chimney cap; item frame as a held tool (the bail's grip at the origin, up +Z), so the
    lantern hangs below the fist."""
    mb = IK.MB()
    # the body hangs 0.07 m under the grip
    top = -0.07
    IK.lathe(mb, [(0.068, top - 0.24), (0.072, top - 0.225), (0.07, top - 0.19), (0.05, top - 0.18), (0.0, top - 0.18)],
             segments=16, mat="item_paint_red")
    IK.lathe(mb, [(0.048, top - 0.18), (0.062, top - 0.14), (0.064, top - 0.1), (0.05, top - 0.065), (0.03, top - 0.055)],
             segments=16, mat="item_glass_clear")
    for k in range(4):
        a = k * math.pi / 2 + math.pi / 4
        IK.tube(mb, [Vector((math.cos(a) * 0.07, math.sin(a) * 0.07, top - 0.19)),
                     Vector((math.cos(a) * 0.07, math.sin(a) * 0.07, top - 0.05))], 0.0025, sides=4, mat="item_steel_dark")
    IK.lathe(mb, [(0.0, top), (0.035, top - 0.01), (0.055, top - 0.04), (0.04, top - 0.055), (0.0, top - 0.055)],
             segments=16, mat="item_paint_red")
    # the wire bail up to the grip
    bail = [Vector((math.sin(a) * 0.075, 0.0, top - 0.06 + math.cos(a) * 0.06 + 0.0)) for a in np.linspace(-math.pi / 2, math.pi / 2, 9)]
    IK.tube(mb, bail, 0.003, sides=4, mat="item_steel_dark")
    return _built(mb, "prop_lantern", seed)


def _splint(model, skel, seed: int) -> bpy.types.Object:
    """Two straight branches bound either side of his left shin with three strips of cloth: the leg
    he hurt, splinted where he sits at his camp."""
    s = model.s
    j = skel.j
    ankle = np.array(j["ankle.L"])
    knee = np.array(j["knee.L"])
    up = (knee - ankle) / float(np.linalg.norm(knee - ankle))
    length = float(np.linalg.norm(knee - ankle))
    mb = IK.MB()
    for sx in (-1.0, 1.0):
        IK.box(mb, (0.022 * s, 0.03 * s, length * 0.95), (sx * 0.062 * s, 0.0, length * 0.5), mat="item_wood_raw", bevel=0.004 * s)
    for z in (0.18, 0.5, 0.82):
        ring = [Vector((math.cos(a) * 0.068 * s, math.sin(a) * 0.058 * s, length * z))
                for a in np.linspace(0.0, 2.0 * math.pi, 14, endpoint=False)]
        IK.tube(mb, ring, 0.012 * s, sides=4, mat="item_cloth_bandage", closed=True)
    obj = _built(mb, "prop_splint", seed + 31)
    x = np.array([1.0, 0.0, 0.0])
    x -= up * float(np.dot(x, up))
    x /= np.linalg.norm(x)
    y = np.cross(up, x)
    obj.data.transform(_frame(ankle + up * 0.03 * s, x, y, up))
    return obj


def _prop(obj: bpy.types.Object, name: str, bone: str, arm) -> bpy.types.Object:
    """A separate skinned mesh weighted wholly to `bone` (the game shows or hides it by name)."""
    obj.name = name
    obj.data.name = name
    vcolor.ensure_layer(obj)
    vg = obj.vertex_groups.new(name=bone)
    vg.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
    CB._bind(obj, arm)
    return obj


def _props(model, skel, arm, seed: int, weapon: str) -> list:
    out = []
    if weapon:
        fn, tilt = CL.WEAPONS[weapon]
        hand = fn(seed)
        hand.data.transform(CL._fist(skel) @ Matrix.Rotation(math.radians(tilt), 4, "X"))
        out.append(_prop(hand, "prop_hatchet_hand", "hand.R", arm))
        out.append(_prop(_hatchet_belt(model, skel, seed + 41), "prop_hatchet_belt", "hips", arm))
    lan = _lantern(seed + 43)
    # the lantern's up (+Z) along the item's +Y, toward the wrist: it hangs from the fist
    lan.data.transform(_fist_l(skel) @ Matrix.Rotation(math.radians(-90.0), 4, "X"))
    out.append(_prop(lan, "prop_lantern", "hand.L", arm))
    out.append(_prop(_splint(model, skel, seed), "prop_splint", "shin.L", arm))
    return out


def build(params: dict, outputs: list[str]) -> None:
    arm, objs, caps, skel, model, stats = npc_build.build_npc_body(params)
    seed = int(params.get("seed", 1))
    gear = params.get("gear", {})
    # TD-302: his hatchet, belt hatchet, lantern and splint are separate meshes the game toggles
    props = _props(model, skel, arm, seed, str(params.get("weapon", ""))) if params.get("props", True) else []
    if params.get("weapon") and not props:
        CL.add_weapon(str(params["weapon"]), skel, objs, seed)
    if gear.get("pack", True):
        _attach(_pack(model, skel, seed + 21, bool(gear.get("hard_hat", True))), "body_torso", "chest", objs)
    if gear.get("spurs", True):
        for side in ("L", "R"):
            _attach(_spur(model, skel, side, seed), f"body_shin.{side}", f"shin.{side}", objs)
    only = params.get("_only_actions")
    lengths = living_anim.build_all(arm, skel, params, only=only)
    talk = [a for a in ("talk", "look") if not only or a in only]
    if talk:  # (never npc_anim's idle: the living fighter's idle is his)
        lengths.update(npc_anim.build_all(arm, skel, params, only=talk))
    lengths.update(companion_anim.build_all(arm, skel, params, only=only))
    bpy.context.scene.frame_set(0)
    export.export_glb(outputs[0], [arm] + objs + caps + props, animations=True, skins=True)
    cap_tris = sum(sum(len(p.vertices) - 2 for p in c.data.polygons) for c in caps)
    print(f"[character_companion] props {[o.name for o in props]}")
    print(f"[character_companion] {params.get('name')}: height {npc_build.height_of(objs):.3f} m, segments {stats} "
          f"(total {sum(stats.values())}) caps {cap_tris} actions {len(lengths)} {sorted(lengths)}")
