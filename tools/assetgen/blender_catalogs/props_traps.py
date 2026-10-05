"""Traps and lock cues family (POI dungeon mechanics, ADR-0018): bear traps, the shotgun trip-wire
rig, loose floorboards, alarms and door locks that PoiBuilder places by model id.

One task per model id; outputs models/props/<id>.glb (a single condition each: the game swaps
models for state changes, e.g. trap_bear -> trap_bear_sprung). Generator:
blender/generators/props_traps.py. Content defs (sizes for the procedural fallbacks):
game/data/props/traps.json; materials: game/data/materials/props_traps.json.
"""
from __future__ import annotations

from ..core.registry import Task, blender_sources

MODULE = "props_traps"

# id: params. "levels" sets the wear of the one variant (props_ext_kit.Ctx: clean 0.3, worn 0.65);
# door and wall pieces skip the floor-plane AO (ground_ao false) and bake short-range AO.
WORN = {"clean": 0.45}
PROPS: dict[str, dict] = {
    "trap_bear": {"seed": 7201, "levels": WORN, "ao_dist": 0.15, "ao_samples": 24},
    "trap_bear_sprung": {"seed": 7201, "levels": WORN, "ao_dist": 0.15, "ao_samples": 24},
    "trap_shotgun_rig": {"seed": 7202, "levels": WORN, "ao_dist": 0.35},
    "trap_creaky_boards": {"seed": 7203, "levels": {"clean": 0.7}, "ao_dist": 0.12},
    "trap_alarm_box": {"seed": 7204, "levels": {"clean": 0.45}, "ao_dist": 0.05, "ground_ao": False},
    "trap_alarm_bell": {"seed": 7205, "levels": {"clean": 0.5}, "ao_dist": 0.06, "ground_ao": False},
    "lock_padlock": {"seed": 7211, "levels": WORN, "ao_dist": 0.05, "ground_ao": False},
    "lock_hasp_open": {"seed": 7211, "levels": WORN, "ao_dist": 0.05, "ground_ao": False},
    "lock_chain": {"seed": 7212, "levels": WORN, "ao_dist": 0.05, "ground_ao": False},
    "lock_deadbolt": {"seed": 7213, "levels": {"clean": 0.4}, "ao_dist": 0.04, "ground_ao": False},
    "lock_bolt": {"seed": 7214, "levels": WORN, "ao_dist": 0.04, "ground_ao": False},
}


def tasks() -> list[Task]:
    out = []
    for pid, params in PROPS.items():
        p = {"prop": pid, "conditions": ["clean"], **params}
        out.append(Task(name=f"model:props/{pid}", group="models", outputs=[f"models/props/{pid}.glb"],
                        sources=blender_sources(MODULE), params=p, blender=MODULE))
    return out
