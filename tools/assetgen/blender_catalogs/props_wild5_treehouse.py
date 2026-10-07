"""Wilderness set pieces, round 5: props of the Treehouse Holdout (w5_treehouse_holdout), a family's plank huts and
decks in three big firs, joined by rope bridges, with the burned-out cabin and the garden below.

One task per prop id, one GLB per condition: models/props/<id>.glb (clean), <id>_worn.glb. Task names are
model:props/wild5_treehouse/<id> so `--match wild5_treehouse` selects the whole family. Generator:
blender/generators/props_wild5_treehouse.py; content defs: game/data/props/wild5_treehouse.json (shared materials
only).
"""
from __future__ import annotations

from ..core.registry import Task, blender_sources

C, W = "clean", "worn"
CW = [C, W]
GEN = "props_wild5_treehouse"

# id: (conditions, params)
PROPS: dict[str, tuple[list[str], dict]] = {
    "w5_treehouse_trunk": (CW, {"seed": 5501, "ao_dist": 1.0, "ao_samples": 12}),
    "w5_treehouse_stilt": (CW, {"seed": 5502, "ao_dist": 0.5}),
    "w5_treehouse_rail": (CW, {"seed": 5503, "ao_dist": 0.3}),
    "w5_treehouse_rope_rail": (CW, {"seed": 5504, "ao_dist": 0.3}),
    "w5_treehouse_bridge_planks": (CW, {"seed": 5505, "ao_dist": 0.3}),
    "w5_treehouse_ladder_pulled": (CW, {"seed": 5506, "ao_dist": 0.3}),
    "w5_treehouse_pulley_lift": (CW, {"seed": 5507, "ao_dist": 0.5}),
    "w5_treehouse_rain_barrel": (CW, {"seed": 5508, "ao_dist": 0.5}),
    "w5_treehouse_garden_bed": (CW, {"seed": 5509, "ao_dist": 0.5}),
    "w5_treehouse_garden_fence": (CW, {"seed": 5510, "ao_dist": 0.4}),
    "w5_treehouse_fallen_rafters": (CW, {"seed": 5511, "ao_dist": 0.5}),
    "w5_treehouse_stores_chest": (CW, {"seed": 5512, "ao_dist": 0.4}),
}


def outputs_for(pid: str, conds: list[str]) -> list[str]:
    return [f"models/props/{pid}{'' if c == C else '_' + c}.glb" for c in conds]


def tasks() -> list[Task]:
    out = []
    srcs = blender_sources(GEN)
    for pid, (conds, params) in PROPS.items():
        p = {"prop": pid, "conditions": list(conds), **params}
        out.append(Task(name=f"model:props/wild5_treehouse/{pid}", group="models", outputs=outputs_for(pid, conds), sources=srcs,
                        params=p, blender=GEN))
    return out
