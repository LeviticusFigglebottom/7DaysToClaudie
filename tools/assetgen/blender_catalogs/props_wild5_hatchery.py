"""Wilderness set pieces, round 5: props of the Silver Run fish hatchery (w5_fish_hatchery), a state trout hatchery on a
forest creek the Cordon used as a water-testing post.

One task per prop id, one GLB per condition: models/props/<id>.glb (clean), <id>_worn.glb, <id>_destroyed.glb.
Task names are model:props/wild5_hatchery/<id> so `--match wild5_hatchery` selects the whole family. Generator:
blender/generators/props_wild5_hatchery.py; content defs: game/data/props/wild5_hatchery.json; materials: shared sets
plus game/data/materials/props_wild5_hatchery.json (the trout).
"""
from __future__ import annotations

from ..core.registry import Task, blender_sources

C, W, D = "clean", "worn", "destroyed"
CW = [C, W]
CWD = [C, W, D]
GEN = "props_wild5_hatchery"

# id: (conditions, params)
PROPS: dict[str, tuple[list[str], dict]] = {
    "w5_hatchery_raceway": (CW, {"seed": 5101, "ao_dist": 0.5}),
    "w5_hatchery_headbox": (CW, {"seed": 5102, "ao_dist": 0.5}),
    "w5_hatchery_shed_post": (CW, {"seed": 5103, "ao_dist": 0.3}),
    "w5_hatchery_intake_pipe": (CW, {"seed": 5104, "ao_dist": 0.5}),
    "w5_hatchery_fish_tote": (CW, {"seed": 5105, "ao_dist": 0.3}),
    "w5_hatchery_feed_cart": (CW, {"seed": 5106, "ao_dist": 0.4}),
    "w5_hatchery_incubator_stack": (CWD, {"seed": 5107, "ao_dist": 0.4}),
    "w5_hatchery_hatch_trough": (CW, {"seed": 5108, "ao_dist": 0.4}),
    "w5_hatchery_results_board": (CW, {"seed": 5109, "ao_dist": 0.15}),
    "w5_hatchery_chiller": (CW, {"seed": 5110, "ao_dist": 0.5}),
    "w5_hatchery_sample_cooler": (CW, {"seed": 5111, "ao_dist": 0.3}),
    "w5_hatchery_feed_pallet": (CW, {"seed": 5112, "ao_dist": 0.4}),
    "w5_hatchery_dam": (CW, {"seed": 5113, "ao_dist": 1.0}),
    "w5_hatchery_weir_pool": (CW, {"seed": 5114, "ao_dist": 0.8}),
    "w5_hatchery_creek": (CW, {"seed": 5115, "ao_dist": 0.6}),
    "w5_hatchery_headgate": (CW, {"seed": 5116, "ao_dist": 0.3}),
    "w5_hatchery_sampler": (CW, {"seed": 5117, "ao_dist": 0.3}),
    "w5_hatchery_catwalk_rail": (CW, {"seed": 5118, "ao_dist": 0.2}),
    "w5_hatchery_sign": (CW, {"seed": 5119, "ao_dist": 0.5}),
    "w5_hatchery_stocking_truck": (CW, {"seed": 5120, "ao_dist": 1.0}),
    "w5_hatchery_feed_silo": (CW, {"seed": 5121, "ao_dist": 0.9}),
}


def outputs_for(pid: str, conds: list[str]) -> list[str]:
    return [f"models/props/{pid}{'' if c == C else '_' + c}.glb" for c in conds]


def tasks() -> list[Task]:
    out = []
    srcs = blender_sources(GEN)
    for pid, (conds, params) in PROPS.items():
        p = {"prop": pid, "conditions": list(conds), **params}
        out.append(Task(name=f"model:props/wild5_hatchery/{pid}", group="models", outputs=outputs_for(pid, conds), sources=srcs,
                        params=p, blender=GEN))
    return out
