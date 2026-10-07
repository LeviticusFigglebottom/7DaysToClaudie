"""Bloom nests (ADR-0055): the root mass, pods, shelf cluster and remains a nest is made of.

One task per prop id, one GLB per condition: models/props/<id>.glb (the living nest) and
<id>_destroyed.glb (burned). Generator: blender/generators/props_bloom_nest.py. Content defs:
game/data/props/bloom_nest.json; nests: game/data/nests/*.json; materials:
game/data/materials/props_bloom_nest.json (bloom_fungus shader, the Bloom mound and cap textures).
"""
from __future__ import annotations

from ..core.registry import Task, blender_sources

C, D = "clean", "destroyed"
GEN = "props_bloom_nest"

PROPS: dict[str, tuple[list[str], dict]] = {
    "nest_root_mass": ([C, D], {"seed": 5501, "ao_samples": 16, "ao_dist": 1.2}),
    "nest_pod": ([C, D], {"seed": 5502, "ao_dist": 0.6}),
    "nest_shelf_cluster": ([C, D], {"seed": 5503, "ao_dist": 0.6}),
    "nest_remains": ([C], {"seed": 5504, "ao_dist": 0.4}),
}


def tasks() -> list[Task]:
    out = []
    for pid, (conds, params) in PROPS.items():
        outputs = [f"models/props/{pid}{'' if c == C else '_' + c}.glb" for c in conds]
        out.append(Task(name=f"model:props/{pid}", group="models", outputs=outputs, sources=blender_sources(GEN),
                        params={"prop": pid, "conditions": list(conds), **params}, blender=GEN))
    return out
