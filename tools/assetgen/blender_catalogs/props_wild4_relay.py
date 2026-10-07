"""Forest set pieces, round 4 (ADR-0053): props of the Ridge Relay Hut (w4_ridge_relay_hut), an unmanned microwave
relay hut on a forested ridge with a guyed tower, a fenced compound and a helipad.

One task per prop id, one GLB per condition: models/props/<id>.glb (clean), <id>_worn.glb, <id>_destroyed.glb.
Task names are model:props/wild4_relay/<id> so `--match wild4_relay` selects the whole family. Generator:
blender/generators/props_wild4_relay.py; content defs: game/data/props/wild4_relay.json (shared materials only).
"""
from __future__ import annotations

from ..core.registry import Task, blender_sources

C, W, D = "clean", "worn", "destroyed"
CW = [C, W]
CWD = [C, W, D]
GEN = "props_wild4_relay"

# id: (conditions, params)
PROPS: dict[str, tuple[list[str], dict]] = {
    "w4_relay_tower": (CW, {"seed": 4301, "ao_dist": 1.2, "ao_samples": 12}),
    "w4_relay_tower_section": (CW, {"seed": 4302, "ao_dist": 0.6}),
    "w4_relay_dish": (CW, {"seed": 4303, "ao_dist": 0.5}),
    "w4_relay_tower_platform_rail": (CW, {"seed": 4304, "ao_dist": 0.3}),
    "w4_relay_equipment_rack": (CWD, {"seed": 4305, "ao_dist": 0.5}),
    "w4_relay_battery_bank": (CW, {"seed": 4306, "ao_dist": 0.5}),
    "w4_relay_generator": (CW, {"seed": 4307, "ao_dist": 0.6}),
    "w4_relay_propane_tank": (CW, {"seed": 4308, "ao_dist": 0.7}),
    "w4_relay_fuel_shed": (CW, {"seed": 4309, "ao_dist": 0.8}),
    "w4_relay_gate": (CW, {"seed": 4310, "ao_dist": 0.4}),
    "w4_relay_helipad": (CW, {"seed": 4311, "ao_dist": 0.5}),
    "w4_relay_field_radio": (CW, {"seed": 4312, "ao_dist": 0.3}),
    "w4_relay_cable_reel": (CW, {"seed": 4313, "ao_dist": 0.5}),
    "w4_relay_windsock": (CW, {"seed": 4314, "ao_dist": 0.4}),
}


def outputs_for(pid: str, conds: list[str]) -> list[str]:
    return [f"models/props/{pid}{'' if c == C else '_' + c}.glb" for c in conds]


def tasks() -> list[Task]:
    out = []
    srcs = blender_sources(GEN)
    for pid, (conds, params) in PROPS.items():
        p = {"prop": pid, "conditions": list(conds), **params}
        out.append(Task(name=f"model:props/wild4_relay/{pid}", group="models", outputs=outputs_for(pid, conds), sources=srcs,
                        params=p, blender=GEN))
    return out
