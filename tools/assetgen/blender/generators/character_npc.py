"""Living human NPCs (the trader at Waystation 9): the Hollowed body pipeline with the infection
left out (lib/npc_build.py) and calm counter-side clips (lib/npc_anim.py). Same skeleton, segment
and stump-cap contract as the Hollowed (docs/CHARACTERS.md), so the game loads one the same way.

params: the character_body params (height, sex, build, belly, outfit, boots, hair, hat, remap,
...) plus vest, armband, gloves, beard (npc_build). See tools/assetgen/blender_catalogs/npcs.py.
"""
from __future__ import annotations

import bpy

from lib import export, npc_anim, npc_build


def build(params: dict, outputs: list[str]) -> None:
    arm, objs, caps, skel, model, stats = npc_build.build_npc_body(params)
    lengths = npc_anim.build_all(arm, skel, params, only=params.get("_only_actions"))
    bpy.context.scene.frame_set(0)
    export.export_glb(outputs[0], [arm] + objs + caps, animations=True, skins=True)
    cap_tris = sum(sum(len(p.vertices) - 2 for p in c.data.polygons) for c in caps)
    print(f"[character_npc] {params.get('name')}: height {npc_build.height_of(objs):.3f} m, segments {stats} "
          f"(total {sum(stats.values())}) caps {cap_tris} actions {lengths}")
