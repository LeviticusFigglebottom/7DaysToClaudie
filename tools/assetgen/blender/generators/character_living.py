"""Living fighters (the Ashen raiders and scouts, ADR-0048): the Hollowed body pipeline without the
infection (lib/npc_build: no tier growths, wounds, Bloom or blood, the mouth closed, beards allowed)
with living-human clips under the Hollowed's action names (lib/living_anim: an upright walk and
run, an axe chop, a spear thrust / throw, an alert idle, a recoil for hits, a stumbling stagger,
collapsing deaths; the Hollowed's sleep / wake clips as they are), so the Enemy and EnemyVisual
drive them like any Hollowed: same skeleton, segments, stump caps and action names
(docs/CHARACTERS.md, TD-187).

The weapon (params "weapon": "stone_axe", the raiders') is a rigid prop in the right hand: built
here from item_kit pieces (the item materials), placed in the rest-pose fist and joined into the
`body_forearm.R` segment weighted wholly to `hand.R`, so it moves with the hand in every clip
and goes with the arm when it is severed (EnemyVisual hides the segment).

A generator of its own, not a flag on character_body, so the living bodies' extra libs (npc_build,
living_anim, item_kit) do not enter every Hollowed body's input hash.

params: the character_body params (height, sex, build, outfit, mantle, paint, accessories, hair,
remap, ...) plus npc_build's beard / gloves and "weapon". See tools/assetgen/blender_catalogs/characters.py.
"""
from __future__ import annotations

import math

import bpy
import numpy as np
from mathutils import Matrix, Vector

from lib import export, item_kit as IK, living_anim, npc_build, vcolor


def _axe(seed: int) -> bpy.types.Object:
    """A hafted stone axe, light for a body prop (~500 tris): a crooked ash haft, a knapped flint
    head through a split near the top, bound above and below with rawhide. Item frame: the grip at
    the origin, the haft along +Z, the edge towards -Y."""
    mb = IK.MB()
    hr = 0.0165
    pts = IK.branch_path(0.50, seed, bend=0.006, n=7, start=(0, 0, -0.10))
    IK.stick(mb, pts, hr * 1.05, hr * 0.92, sides=7, seed=seed, bark="item_bark_twig", lumpy=0.03)
    top = pts[-1]
    zc = 0.33
    for z0, z1, s in ((zc - 0.065, zc - 0.035, 1), (zc + 0.035, zc + 0.06, 2)):
        IK.lashing(mb, (top.x, top.y, z0), (top.x, top.y, z1), hr, cord=0.0028, turns=3, per_turn=6, sides=4,
                   mat="item_rawhide", phase=seed * 0.7 + s)
    haft = mb.build("weapon_haft", sharp_deg=60)
    head = IK.knapped("weapon_head", length=0.15, width=0.075, thickness=0.03, seed=seed + 5, scars=26, cortex=0.25,
                      mat="item_flint", subdiv=3, tris=300)
    head.data.transform(Matrix.Translation((top.x, top.y - 0.03, zc)))
    return _joined([haft, head], seed)


def _joined(parts, seed: int) -> bpy.types.Object:
    for p in parts:
        IK.bake_wear_and_masks(p, wear_deg=30.0, seed=seed)
    with bpy.context.temp_override(active_object=parts[0], selected_editable_objects=parts, object=parts[0]):
        bpy.ops.object.join()
    return parts[0]


# kind -> (builder, tilt): the haft leans from the thumb's side towards the fingers' by `tilt`
# degrees (the wrist cocked), so an axe hangs forward-down from the relaxed hand and its edge
# comes down in front in the chop. No spear: the arm IK has no wrist, so in the overhand throw
# (attack_b) the fist rolls over between the draw and the release and a rigid spear in it turns
# end over end and ends pointing backwards (and the thrown spear would leave one still in the
# hand); TD-187.
WEAPONS = {"stone_axe": (_axe, 50.0)}


def _fist(skel) -> Matrix:
    """The rest-pose right fist: item frame -> body. The haft crosses the palm with the business
    end on the thumb side (item +Z), the edge / point facing the way the knuckles do (item -Y
    along the hand), the grip in the hollow of the palm."""
    j = skel.j
    wr, tip, back = (np.array(j[k]) for k in ("wrist.R", "hand_tip.R", "palm_back.R"))
    f = tip - wr
    hl = float(np.linalg.norm(f))
    f /= hl
    b = back - wr
    b -= f * float(np.dot(b, f))
    b /= np.linalg.norm(b)
    t = np.cross(b, f)            # the right thumb's side
    x = np.cross(-f, t)           # item X = Y x Z
    grip = wr + f * hl * 0.42 - b * 0.024
    m = Matrix.Identity(4)
    for i in range(3):
        m[i][0], m[i][1], m[i][2], m[i][3] = float(x[i]), float(-f[i]), float(t[i]), float(grip[i])
    return m


def add_weapon(kind: str, skel, objs: list, seed: int) -> None:
    """Builds the weapon, puts it in the rest-pose right hand and joins it into body_forearm.R,
    weighted wholly to hand.R."""
    seg = next(o for o in objs if o.name == "body_forearm.R")
    fn, tilt = WEAPONS[kind]
    w = fn(seed)
    w.data.transform(_fist(skel) @ Matrix.Rotation(math.radians(tilt), 4, "X"))
    # the segment's layers by name (join merges same-named layers; others would add new ones)
    w.data.uv_layers[0].name = seg.data.uv_layers[0].name
    vcolor.ensure_layer(w)
    vg = w.vertex_groups.new(name="hand.R")
    vg.add(list(range(len(w.data.vertices))), 1.0, "REPLACE")
    w.parent = seg.parent
    with bpy.context.temp_override(active_object=seg, selected_editable_objects=[seg, w], object=seg):
        bpy.ops.object.join()


def build(params: dict, outputs: list[str]) -> None:
    arm, objs, caps, skel, model, stats = npc_build.build_npc_body(params)
    if params.get("weapon"):
        add_weapon(str(params["weapon"]), skel, objs, int(params.get("seed", 1)))
    lengths = living_anim.build_all(arm, skel, params, only=params.get("_only_actions"))
    bpy.context.scene.frame_set(0)
    export.export_glb(outputs[0], [arm] + objs + caps, animations=True, skins=True)
    cap_tris = sum(sum(len(p.vertices) - 2 for p in c.data.polygons) for c in caps)
    print(f"[character_living] {params.get('name')}: height {npc_build.height_of(objs):.3f} m, segments {stats} "
          f"(total {sum(stats.values())}) caps {cap_tris} actions {len(lengths)} weapon {params.get('weapon', '-')}")
