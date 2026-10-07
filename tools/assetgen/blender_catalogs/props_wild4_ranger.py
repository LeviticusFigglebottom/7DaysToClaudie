"""Wilderness set pieces, round 4 (ADR-0053): the Kettle Creek backcountry ranger station
(game/data/pois/buildings/w4_backcountry_ranger_station.json).

One task per prop id, one GLB per condition: models/props/<id>.glb (clean), <id>_worn.glb, <id>_destroyed.glb.
Task names are model:props/wild4_ranger/<id> so `--match wild4_ranger` selects the family. Generator:
blender/generators/props_wild4_ranger.py; content defs: game/data/props/wild4_ranger.json.

The cab shell wraps the POI's 2 x 2 kit cab on level 4 (plan cols 26..27, rows 6..7) with its floor at the
prop's origin: SHELLS lists its openings (side, index along the side, kind) exactly as the POI JSON has
them; test_w4_ranger.gd checks it.
"""
from __future__ import annotations

from ..core.registry import Task, blender_sources

C, W, D = "clean", "worn", "destroyed"
CW = [C, W]
CWD = [C, W, D]
GEN = "props_wild4_ranger"

SHELLS: dict[str, dict] = {
    "w4_ranger_tower_cab": {"w": 2, "d": 2, "floor": 0.0, "openings": [
        ["N", 0, "window2"], ["S", 0, "window2"], ["W", 0, "window2"], ["E", 0, "window2"]]},
}

# id: (conditions, params)
PROPS: dict[str, tuple[list[str], dict]] = {
    "w4_ranger_tower_leg_section": (CW, {"seed": 4101, "ao_dist": 0.8}),
    "w4_ranger_tower_footing": ([C], {"seed": 4102}),
    "w4_ranger_tower_cab": (CW, {"seed": 4103, "ao_samples": 12, "ao_dist": 0.8, **SHELLS["w4_ranger_tower_cab"]}),
    "w4_ranger_weather_screen": (CWD, {"seed": 4104, "ao_dist": 0.4}),
    "w4_ranger_rain_gauge": (CW, {"seed": 4105, "ao_dist": 0.3}),
    "w4_ranger_anemometer_mast": (CW, {"seed": 4106, "ao_dist": 0.5}),
    "w4_ranger_brush_truck": (CWD, {"seed": 4107, "ao_samples": 14, "ao_dist": 0.9}),
    "w4_ranger_checkpoint_barrier": (CWD, {"seed": 4108, "ao_dist": 0.5}),
    "w4_ranger_fuel_pump": (CWD, {"seed": 4109, "ao_dist": 0.6}),
    "w4_ranger_compound_gate": (CW, {"seed": 4110, "ao_dist": 0.6}),
    "w4_ranger_gun_safe": (CWD, {"seed": 4111, "ao_dist": 0.4}),
    "w4_ranger_fire_danger_sign": (CW, {"seed": 4112, "ao_dist": 0.5}),
}


def outputs_for(pid: str, conds: list[str]) -> list[str]:
    return [f"models/props/{pid}{'' if c == C else '_' + c}.glb" for c in conds]


def tasks() -> list[Task]:
    out = []
    srcs = blender_sources(GEN)
    for pid, (conds, params) in PROPS.items():
        p = {"prop": pid, "conditions": list(conds), **params}
        out.append(Task(name=f"model:props/wild4_ranger/{pid}", group="models", outputs=outputs_for(pid, conds), sources=srcs,
                        params=p, blender=GEN))
    return out
