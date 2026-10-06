"""Living fighters (the Ashen raiders and scouts, ADR-0048): the Hollowed body pipeline without the
infection (lib/npc_build: no tier growths, wounds, Bloom or blood, the mouth closed, beards allowed)
with the Hollowed's full action set (lib/char_anim), so the Enemy and EnemyVisual drive them like
any Hollowed: same skeleton, segments, stump caps and clips (docs/CHARACTERS.md).

A generator of its own, not a flag on character_body, so the living bodies' extra lib (npc_build)
does not enter every Hollowed body's input hash.

params: the character_body params (height, sex, build, outfit, mantle, paint, accessories, hair,
remap, ...) plus npc_build's beard / gloves. See tools/assetgen/blender_catalogs/characters.py.
"""
from __future__ import annotations

import bpy

from lib import char_anim, export, npc_build


def build(params: dict, outputs: list[str]) -> None:
    arm, objs, caps, skel, model, stats = npc_build.build_npc_body(params)
    lengths = char_anim.build_all(arm, skel, params, only=params.get("_only_actions"))
    bpy.context.scene.frame_set(0)
    export.export_glb(outputs[0], [arm] + objs + caps, animations=True, skins=True)
    cap_tris = sum(sum(len(p.vertices) - 2 for p in c.data.polygons) for c in caps)
    print(f"[character_living] {params.get('name')}: height {npc_build.height_of(objs):.3f} m, segments {stats} "
          f"(total {sum(stats.values())}) caps {cap_tris} actions {len(lengths)}")
