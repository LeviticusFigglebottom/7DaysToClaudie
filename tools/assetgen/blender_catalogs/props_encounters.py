"""Forest encounter props (ADR-0054): the small finds between the towns (game/data/encounters).

One task per prop id, one GLB per condition: models/props/<id>.glb (clean), <id>_worn.glb. Task names are
model:props/encounters/<id> so `--match encounters` selects the family. Generator:
blender/generators/props_encounters.py (props_ext_kit / props_ext_parts / props_wild_parts); content defs:
game/data/props/encounters.json. Existing materials only (props_exterior, props_wild, animals, bloom).
"""
from __future__ import annotations

from ..core.registry import Task, blender_sources

C, W = "clean", "worn"
CW = [C, W]
GEN = "props_encounters"

# id: (conditions, params)
PROPS: dict[str, tuple[list[str], dict]] = {
    "enc_camp_cooler": (CW, {"seed": 5401}),
    "enc_ladder_stand": (CW, {"seed": 5402, "ao_dist": 0.8}),
    "enc_ground_blind": (CW, {"seed": 5403, "ao_dist": 0.9}),
    "enc_logging_truck_wreck": (CW, {"seed": 5404, "ao_samples": 16, "ao_dist": 1.2}),
    "enc_atv_wreck": (CW, {"seed": 5405, "ao_dist": 0.7}),
    "enc_tarp_cache": (CW, {"seed": 5406}),
    "enc_bloom_kill": (CW, {"seed": 5407}),
    "enc_grave_cross": (CW, {"seed": 5408}),
    "enc_cordon_marker": (CW, {"seed": 5409}),
}


def outputs_for(pid: str, conds: list[str]) -> list[str]:
    return [f"models/props/{pid}{'' if c == C else '_' + c}.glb" for c in conds]


def tasks() -> list[Task]:
    out = []
    srcs = blender_sources(GEN)
    for pid, (conds, params) in PROPS.items():
        p = {"prop": pid, "conditions": list(conds), **params}
        out.append(Task(name=f"model:props/encounters/{pid}", group="models", outputs=outputs_for(pid, conds), sources=srcs,
                        params=p, blender=GEN))
    return out
