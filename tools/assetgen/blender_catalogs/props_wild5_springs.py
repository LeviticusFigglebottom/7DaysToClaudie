"""Wilderness set pieces, round 5: props of Ember Creek Hot Springs (w5_hot_springs_bathhouse), an old timber
hot-springs bathhouse resort up a remote valley.

One task per prop id, one GLB per condition: models/props/<id>.glb (clean) and <id>_worn.glb. Task names are
model:props/wild5_springs/<id> so `--match wild5_springs` selects the whole family. Generator:
blender/generators/props_wild5_springs.py; content defs: game/data/props/wild5_springs.json; materials:
game/data/materials/props_wild5_springs.json.
"""
from __future__ import annotations

from ..core.registry import Task, blender_sources

C, W = "clean", "worn"
CW = [C, W]
GEN = "props_wild5_springs"

# id: (conditions, params)
PROPS: dict[str, tuple[list[str], dict]] = {
    "w5_springs_plunge_pool": (CW, {"seed": 5501, "ao_dist": 0.6}),
    "w5_springs_rock_pool": (CW, {"seed": 5502, "ao_dist": 0.6}),
    "w5_springs_steam": (CW, {"seed": 5503, "ao_dist": 0.3}),
    "w5_springs_steam_bench": (CW, {"seed": 5504, "ao_dist": 0.4}),
    "w5_springs_bloom_wall": (CW, {"seed": 5505, "ao_dist": 0.3}),
    "w5_springs_bloom_mat": (CW, {"seed": 5506, "ao_dist": 0.3}),
    "w5_springs_boiler": (CW, {"seed": 5507, "ao_dist": 0.8}),
    "w5_springs_cistern": (CW, {"seed": 5508, "ao_dist": 0.7}),
    "w5_springs_boardwalk": (CW, {"seed": 5509, "ao_dist": 0.3}),
    "w5_springs_towel_shelf": (CW, {"seed": 5510, "ao_dist": 0.4}),
    "w5_springs_changing_bench": (CW, {"seed": 5511, "ao_dist": 0.4}),
    "w5_springs_key_board": (CW, {"seed": 5512, "ao_dist": 0.15}),
    "w5_springs_cedar_tub": (CW, {"seed": 5513, "ao_dist": 0.5}),
    "w5_springs_pipe_run": (CW, {"seed": 5514, "ao_dist": 0.3}),
}


def outputs_for(pid: str, conds: list[str]) -> list[str]:
    return [f"models/props/{pid}{'' if c == C else '_' + c}.glb" for c in conds]


def tasks() -> list[Task]:
    out = []
    srcs = blender_sources(GEN)
    for pid, (conds, params) in PROPS.items():
        p = {"prop": pid, "conditions": list(conds), **params}
        out.append(Task(name=f"model:props/wild5_springs/{pid}", group="models", outputs=outputs_for(pid, conds), sources=srcs,
                        params=p, blender=GEN))
    return out
