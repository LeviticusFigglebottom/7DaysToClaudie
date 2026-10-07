"""Key and note item models of the Dunmore Timber truck depot (w4_logging_truck_depot, forest set pieces round 4):
models/items/wild4_depot/<id>.glb, made by the shared item_paper generator; game/data/items/wild4_depot.json points
each item's "model" here."""
from __future__ import annotations

from ..core.registry import Task, blender_sources

ITEMS: dict[str, dict] = {
    "w4_depot_parts_key": {"kind": "key", "seed": 9921, "metal": "item_steel_tool", "tag": "tag"},
    "w4_depot_office_key": {"kind": "key", "seed": 9922, "metal": "item_brass", "tag": "tag"},
    "note_w4_depot_dispatch_log": {"kind": "logbook", "seed": 9923},
    "note_w4_depot_driver_letter": {"kind": "note", "seed": 9924, "sheet": "item_paper_note", "flat": False},
    "note_w4_depot_closure_order": {"kind": "note", "seed": 9925, "sheet": "item_paper_ledger", "flat": True},
    "note_w4_depot_weigh_tickets": {"kind": "logbook", "seed": 9926},
}


def tasks() -> list[Task]:
    out = []
    for item_id, p in ITEMS.items():
        params = {"name": item_id, **p}
        out.append(Task(name=f"model:items/wild4_depot/{item_id}", group="models",
                        outputs=[f"models/items/wild4_depot/{item_id}.glb"],
                        sources=blender_sources("item_paper"), params=params, blender="item_paper"))
    return out
