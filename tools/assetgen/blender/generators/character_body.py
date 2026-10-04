"""Hollowed bodies (hollow_a..d, lurcher_a..b, keener_a): segmented skinned meshes on the shared
skeleton, stump caps and the full action set (docs/CHARACTERS.md).

params (all optional except name/seed): height, sex, build, gaunt, hunch, head_forward, arm_scale,
leg_scale, shoulder_drop, jaw_drop, jaw_scale, mouth_open, eye_open, claw, outfit, boots, hair,
wounds, bloom, throat_sac, blood, grime, limp_side, arm_raise, raise_side, head_tilt.
See tools/assetgen/blender_catalogs/characters.py for the variants.
"""
from __future__ import annotations

import bpy

from lib import char_anim, char_build, export


def build(params: dict, outputs: list[str]) -> None:
    arm, objs, caps, skel, model, stats = char_build.build_body(params)
    lengths = char_anim.build_all(arm, skel, params, only=params.get("_only_actions"))
    bpy.context.scene.frame_set(0)
    export.export_glb(outputs[0], [arm] + objs + caps, animations=True, skins=True)
    total = sum(stats.values()) + sum(len(c.data.polygons) for c in caps)
    print(f"[character_body] {params.get('name')}: segments {stats} caps "
          f"{sum(sum(len(p.vertices) - 2 for p in c.data.polygons) for c in caps)} actions {len(lengths)}")
    del total
