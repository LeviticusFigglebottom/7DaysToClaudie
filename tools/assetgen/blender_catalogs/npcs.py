"""Living human NPCs (docs/CHARACTERS.md): the Hollowed body pipeline without the infection
(generator character_npc), on the shared skeleton, with counter-side clips idle, idle_b, talk, look.

Sites and garment params as in blender_catalogs/characters.py; the NPC-only params (vest, armband,
gloves, beard) are documented in blender/lib/npc_build.py. Materials: game/data/materials/npcs.json
(selected with "remap", so no label or shader is forked for the living).
"""
from __future__ import annotations

from ..core.registry import Task, blender_sources

# The Remand Program's uniform, as its living staff wear it: olive fatigues (shirt worn out over
# the trousers, sleeves rolled), a quilted vest with pouches, the yellow Program armband, a knit
# cap, tan work gloves and boots.
PROGRAM_REMAP = {
    "skin_hollow": "npc_skin", "eyes_hollow": "npc_eye", "hair": "npc_hair",
    "cloth_shirt": "npc_fatigues", "cloth_canvas": "npc_fatigues",
    "cloth_hivis": "npc_vest", "cloth_hunter": "npc_vest",
    "cloth_cap": "npc_armband", "cloth_knit": "npc_knit", "hide": "npc_gloves",
    # segment-joint skirts and the mouth: dark and neutral, not red (no one cuts the living up)
    "gore": "npc_inner",
}

NPCS = {
    # The quartermaster of Waystation 9: a heavy-set, middle-aged Program man behind the trade
    # counter, tired but healthy; short grizzled beard, knit cap, armband on the left arm.
    "waystation_quartermaster": {
        "seed": 1209, "height": 1.79, "sex": "m", "build": 0.95, "belly": 1.9, "gaunt": 0.0,
        "hunch": 0.06, "head_forward": 0.06, "head_tilt": 0.0, "brow": 0.45,
        "claw": 0.12, "jaw_drop": 1.0, "mouth_open": 0.0, "eye_open": 0.5, "lid_droop": 0.55, "wall_eye": 1.0,
        "teeth_missing": 0.0, "gum_recede": 0.1, "bruise": 0.0, "blood": 0.0, "grime": 0.12,
        "arm_hang": -31.0,
        "outfit": {"tops": [{"type": "shirt", "sleeve": 0.70, "hem": -0.07, "collar": True, "neck_front": 0.035,
                             "rolled": {"L": True, "R": True}, "flare": 0.012, "placket": True}],
                   "pants": {"type": "canvas", "belt": True, "length": 0.97, "thickness": 0.011}},
        "vest": {"hem": -0.035, "neck_front": 0.075, "armhole": 0.022, "thickness": 0.013, "flare": 0.006,
                 "quilt": 0.075, "puff": 0.0035,
                 "pouches": [{"x": 0.085, "h": 0.115, "w": 0.085, "hgt": 0.095, "depth": 0.034},
                             {"x": -0.085, "h": 0.115, "w": 0.085, "hgt": 0.095, "depth": 0.034},
                             {"x": 0.075, "h": 0.330, "w": 0.060, "hgt": 0.085, "depth": 0.026}]},
        "armband": {"side": "L", "t": 0.40, "width": 0.080},
        "gloves": {"cuff": 0.035},
        "beard": {"thickness": 0.0020, "line": -0.030, "moustache": True},
        "boots": {"L": True, "R": True, "height": 0.17},
        "hair": {"style": "short", "hairline": 0.05, "patchy": 0.05},
        "hat": {"type": "beanie", "tilt": -4.0},
        "remap": PROGRAM_REMAP,
    },
}


def tasks() -> list[Task]:
    out = []
    for key, p in NPCS.items():
        params = {"name": key, **p}
        rel = f"models/characters/{key}.glb"
        out.append(Task(name=f"model:characters/{key}", group="models", outputs=[rel],
                        sources=blender_sources("character_npc"), params=params, blender="character_npc",
                        imports={rel: {"type": "scene", "animation": True}}))
    return out
