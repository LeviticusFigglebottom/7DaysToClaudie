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
from lib import companion_anim, export, item_kit as IK, living_anim, npc_anim, npc_build, vcolor
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


def build(params: dict, outputs: list[str]) -> None:
    arm, objs, caps, skel, model, stats = npc_build.build_npc_body(params)
    seed = int(params.get("seed", 1))
    gear = params.get("gear", {})
    if params.get("weapon"):
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
    export.export_glb(outputs[0], [arm] + objs + caps, animations=True, skins=True)
    cap_tris = sum(sum(len(p.vertices) - 2 for p in c.data.polygons) for c in caps)
    print(f"[character_companion] {params.get('name')}: height {npc_build.height_of(objs):.3f} m, segments {stats} "
          f"(total {sum(stats.values())}) caps {cap_tris} actions {len(lengths)} {sorted(lengths)}")
