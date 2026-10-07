"""Forest set pieces, round 4 (ADR-0053): props of the Dunmore Timber truck depot (w4_logging_truck_depot), a logging
company's truck shop deep in the timber.

One task per prop id, one GLB per condition: models/props/<id>.glb (clean), <id>_worn.glb, <id>_destroyed.glb.
Task names are model:props/wild4_depot/<id> so `--match wild4_depot` selects the whole family. Generator:
blender/generators/props_wild4_depot.py; content defs: game/data/props/wild4_depot.json (shared materials only).
"""
from __future__ import annotations

from ..core.registry import Task, blender_sources

C, W, D = "clean", "worn", "destroyed"
CW = [C, W]
CWD = [C, W, D]
GEN = "props_wild4_depot"

# id: (conditions, params)
PROPS: dict[str, tuple[list[str], dict]] = {
    "w4_depot_log_truck": (CW, {"seed": 4301, "ao_dist": 1.2}),
    "w4_depot_log_tractor": (CW, {"seed": 4302, "ao_dist": 1.0}),
    "w4_depot_truck_lift": (CW, {"seed": 4303, "ao_dist": 0.9}),
    "w4_depot_weighbridge": (CW, {"seed": 4304, "ao_dist": 0.6}),
    "w4_depot_fuel_pump": (CWD, {"seed": 4305, "ao_dist": 0.5}),
    "w4_depot_fuel_tank": (CW, {"seed": 4306, "ao_dist": 1.0}),
    "w4_depot_fuel_island": (CW, {"seed": 4307, "ao_dist": 0.4}),
    "w4_depot_log_stack": (CW, {"seed": 4308, "ao_dist": 0.9}),
    "w4_depot_log_pile_low": (CW, {"seed": 4309, "ao_dist": 0.7}),
    "w4_depot_loader": (CW, {"seed": 4310, "ao_dist": 1.0}),
    "w4_depot_welding_cart": (CW, {"seed": 4311, "ao_dist": 0.4}),
    "w4_depot_parts_shelf": (CWD, {"seed": 4312, "ao_dist": 0.5}),
    "w4_depot_dispatch_radio": (CW, {"seed": 4313, "ao_dist": 0.5}),
    "w4_depot_pit_planks": (CW, {"seed": 4314, "ao_dist": 0.3}),
    "w4_depot_dispatch_board": (CW, {"seed": 4315, "ao_dist": 0.2}),
    "w4_depot_tire_stack": (CW, {"seed": 4316, "ao_dist": 0.5}),
}


def outputs_for(pid: str, conds: list[str]) -> list[str]:
    return [f"models/props/{pid}{'' if c == C else '_' + c}.glb" for c in conds]


def tasks() -> list[Task]:
    out = []
    srcs = blender_sources(GEN)
    for pid, (conds, params) in PROPS.items():
        p = {"prop": pid, "conditions": list(conds), **params}
        out.append(Task(name=f"model:props/wild4_depot/{pid}", group="models", outputs=outputs_for(pid, conds), sources=srcs,
                        params=p, blender=GEN))
    return out
