"""Base traps and electricity models (ADR-0052), from blender/generators/base_tech.py except the schematics,
which are item_paper's:
  * models/structures/<id>.glb for the pieces in game/data/structures/base_tech.json (the deadfall's `log`
    node drops, the floodlight's and nail sentry's `head` node turns);
  * models/items/base_tech/<id>.glb for the items in game/data/items/base_tech.json.
Materials all reuse existing families (structure logs, item metals and plastics, garden soil, the
roadside lamp glow, the lab's genset yellow): no new textures."""
from __future__ import annotations

from ..core.registry import Task, blender_sources

GEN = "base_tech"

STRUCTURES: dict[str, int] = {"spike_pit": 7401, "deadfall": 7402, "tripwire_bell": 7403, "generator": 7404, "work_light": 7405,
                              "floodlight": 7406, "nail_sentry": 7407}

ITEMS: dict[str, tuple[str, dict]] = {
    "gas_can": (GEN, {"kind": "item", "item": "gas_can", "seed": 7451}),
    "copper_wire": (GEN, {"kind": "item", "item": "copper_wire", "seed": 7452}),
    "electrical_parts": (GEN, {"kind": "item", "item": "electrical_parts", "seed": 7453}),
    "light_bulb": (GEN, {"kind": "item", "item": "light_bulb", "seed": 7454}),
    "small_engine": (GEN, {"kind": "item", "item": "small_engine", "seed": 7455}),
    "schematic_generator": ("item_paper", {"kind": "schematic", "seed": 7461, "sheet": "item_schematic_a"}),
    "schematic_floodlight": ("item_paper", {"kind": "schematic", "seed": 7462, "sheet": "item_schematic_b"}),
    "schematic_nail_sentry": ("item_paper", {"kind": "schematic", "seed": 7463, "sheet": "item_schematic_c"}),
}


def _sources(mod: str) -> list:
    """base_tech builds on the log toolkit in structure_logs: list it (and the libs it imports) too."""
    out = blender_sources(mod)
    if mod == GEN:
        for f in blender_sources("structure_logs"):
            if f not in out:
                out.append(f)
    return out


def _task(out_path: str, mod: str, params: dict) -> Task:
    return Task(name=f"model:{out_path}", group="models", outputs=[f"models/{out_path}.glb"], sources=_sources(mod), params=params,
                blender=mod)


def tasks() -> list[Task]:
    out = [_task(f"structures/{sid}", GEN, {"name": sid, "kind": sid, "seed": seed}) for sid, seed in STRUCTURES.items()]
    for item_id, (mod, p) in ITEMS.items():
        out.append(_task(f"items/base_tech/{item_id}", mod, {"name": item_id, **p}))
    return out
