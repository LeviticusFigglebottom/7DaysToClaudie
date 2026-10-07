"""Key and note item models of Ember Creek Hot Springs (w5_hot_springs_bathhouse, wilderness set pieces round 5):
models/items/wild5_springs/<id>.glb, made by the shared item_paper generator; game/data/items/wild5_springs.json points
each item's "model" here."""
from __future__ import annotations

from ..core.registry import Task, blender_sources

ITEMS: dict[str, dict] = {
    "w5_springs_staff_key": {"kind": "key", "seed": 5521, "metal": "item_steel_tool", "tag": "tag"},
    "w5_springs_suite_key": {"kind": "key", "seed": 5522, "metal": "item_brass", "tag": "tag"},
    "note_w5_springs_holding_order": {"kind": "note", "seed": 5523, "sheet": "item_paper_ledger", "flat": True},
    "note_w5_springs_guest_letter": {"kind": "note", "seed": 5524, "sheet": "item_paper_note", "flat": False},
    "note_w5_springs_caretaker": {"kind": "note", "seed": 5525, "sheet": "item_paper_note", "flat": True},
    "note_w5_springs_water_log": {"kind": "logbook", "seed": 5526},
    "note_w5_springs_owner_diary": {"kind": "logbook", "seed": 5527},
}


def tasks() -> list[Task]:
    out = []
    for item_id, p in ITEMS.items():
        params = {"name": item_id, **p}
        out.append(Task(name=f"model:items/wild5_springs/{item_id}", group="models",
                        outputs=[f"models/items/wild5_springs/{item_id}.glb"],
                        sources=blender_sources("item_paper"), params=params, blender="item_paper"))
    return out
