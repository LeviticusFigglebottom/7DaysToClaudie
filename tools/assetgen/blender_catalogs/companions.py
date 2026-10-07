"""The companion's body (ADR-0058, Ezra Vane): a living human (generator character_companion: the
Hollowed body pipeline without the infection, lib/npc_build) with the living fighter's clips
(lib/living_anim), the trader's talk and look (lib/npc_anim) and his own downed, revive and
sit_injured (lib/companion_anim). Task names are model:characters/<id>, so `--match ezra` builds
him with his materials and textures.

Materials: game/data/materials/npcs.json (the Program's staff remap, with his own faded fatigues
and grey hair: ezra_fatigues, ezra_hair); his gear (hatchet, pack, hard hat, spurs) is item_kit
geometry with item materials.
"""
from __future__ import annotations

from ..core.registry import Task, blender_sources

# The Program's fatigues on a man who has lived in them for two drops: faded, his own grey hair.
EZRA_REMAP = {
    "skin_hollow": "npc_skin", "eyes_hollow": "npc_eye", "hair": "ezra_hair",
    "cloth_shirt": "ezra_fatigues", "cloth_canvas": "ezra_fatigues",
    "hide": "npc_gloves",
    # segment-joint skirts and the mouth: dark and neutral (as the Program's staff)
    "gore": "npc_inner",
}

COMPANIONS = {
    # Ezra Vane: fifties, lean and weathered, a full grey beard and a receding grey crop; faded
    # Program fatigues (shirt worn out over the trousers, sleeves rolled), a lineman's leather
    # harness over them (shoulder straps and a wide belt), tan work gloves, laced work boots with
    # climbing spurs strapped up the inside of the shins, a canvas pack with a white hard hat
    # clipped to its flap, a hatchet in his right hand.
    "ezra_vane": {
        "seed": 1301, "height": 1.81, "sex": "m", "build": 0.55, "belly": 0.4, "gaunt": 0.35,
        "hunch": 0.04, "head_forward": 0.04, "head_tilt": 0.0, "brow": 0.75,
        "claw": 0.08, "jaw_drop": 1.0, "mouth_open": 0.0, "eye_open": 0.3, "lid_droop": 0.8, "wall_eye": 1.0,
        "teeth_missing": 0.0, "gum_recede": 0.2, "bruise": 0.0, "blood": 0.0, "grime": 0.3,
        "arm_hang": -31.0,
        "outfit": {"tops": [{"type": "shirt", "sleeve": 0.72, "hem": -0.08, "collar": True, "neck_front": 0.04,
                             "rolled": {"L": True, "R": True}, "flare": 0.012, "placket": True, "torn": 0.05}],
                   "pants": {"type": "canvas", "belt": True, "length": 0.97, "thickness": 0.011}},
        "straps": [{"type": "leather", "x": 0.075, "width": 0.042, "waist": 0.05}],
        "gloves": {"cuff": 0.035},
        "beard": {"thickness": 0.0042, "line": -0.024, "moustache": True},
        "boots": {"L": True, "R": True, "height": 0.24},
        "hair": {"style": "short", "hairline": 0.03, "patchy": 0.05},
        "remap": EZRA_REMAP,
        "weapon": "hatchet",
        "gear": {"pack": True, "hard_hat": True, "spurs": True},
    },
}


def tasks() -> list[Task]:
    out = []
    for key, p in COMPANIONS.items():
        params = {"name": key, **p}
        rel = f"models/characters/{key}.glb"
        # The hatchet comes from item_tools and the joining from character_living: their edits rebuild him.
        sources = blender_sources("character_companion") + blender_sources("character_living") + blender_sources("item_tools")
        out.append(Task(name=f"model:characters/{key}", group="models", outputs=[rel],
                        sources=sorted(set(sources)), params=params, blender="character_companion",
                        imports={rel: {"type": "scene", "animation": True}}))
    return out
