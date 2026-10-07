"""Forest set pieces, round 4 (ADR-0053): props of the Kell Shelter (w4_hillside_bunker), a prepper's hillside
cabin over a two-level concrete bunker.

One task per prop id, one GLB per condition: models/props/<id>.glb (clean), <id>_worn.glb, <id>_destroyed.glb.
Task names are model:props/wild4_bunker/<id> so `--match wild4_bunker` selects the whole family. Generator:
blender/generators/props_wild4_bunker.py; content defs: game/data/props/wild4_bunker.json (shared materials only).
"""
from __future__ import annotations

from ..core.registry import Task, blender_sources

C, W, D = "clean", "worn", "destroyed"
CW = [C, W]
CWD = [C, W, D]
GEN = "props_wild4_bunker"

# id: (conditions, params)
PROPS: dict[str, tuple[list[str], dict]] = {
    "w4_bunker_air_filter": (CW, {"seed": 4101, "ao_dist": 0.6}),
    "w4_bunker_generator": (CW, {"seed": 4102, "ao_dist": 0.6}),
    "w4_bunker_water_drum": (CW, {"seed": 4103}),
    "w4_bunker_decon_shower": (CW, {"seed": 4104, "ao_dist": 0.6}),
    "w4_bunker_radio_desk": (CW, {"seed": 4105, "ao_dist": 0.5}),
    "w4_bunker_solar_pole": (CW, {"seed": 4106, "ao_dist": 0.8}),
    "w4_bunker_chicken_coop": (CW, {"seed": 4107, "ao_dist": 0.7}),
    "w4_bunker_shelf_cans": (CWD, {"seed": 4108, "ao_dist": 0.5}),
    "w4_bunker_rain_barrel": (CW, {"seed": 4109}),
    "w4_bunker_woodshed": (CW, {"seed": 4110, "ao_dist": 0.9}),
    "w4_bunker_map_wall": (CW, {"seed": 4111, "ao_dist": 0.2}),
}


def outputs_for(pid: str, conds: list[str]) -> list[str]:
    return [f"models/props/{pid}{'' if c == C else '_' + c}.glb" for c in conds]


def tasks() -> list[Task]:
    out = []
    srcs = blender_sources(GEN)
    for pid, (conds, params) in PROPS.items():
        p = {"prop": pid, "conditions": list(conds), **params}
        out.append(Task(name=f"model:props/wild4_bunker/{pid}", group="models", outputs=outputs_for(pid, conds), sources=srcs,
                        params=p, blender=GEN))
    return out
