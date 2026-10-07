"""Key and note item models of the Ridge Relay Hut (w4_ridge_relay_hut, forest set pieces round 4):
models/items/wild4_relay/<id>.glb, made by the shared item_paper generator; game/data/items/wild4_relay.json
points each item's "model" here."""
from __future__ import annotations

from ..core.registry import Task, blender_sources

ITEMS: dict[str, dict] = {
    "w4_relay_battery_key": {"kind": "key", "seed": 9931, "metal": "item_steel_tool", "tag": "tag"},
    "note_w4_relay_log": {"kind": "logbook", "seed": 9932},
    "note_w4_relay_schedule": {"kind": "note", "seed": 9933, "sheet": "item_paper_ledger", "flat": True},
    "note_w4_relay_letter": {"kind": "note", "seed": 9934, "sheet": "item_paper_note", "flat": False},
    "note_w4_relay_tag": {"kind": "note", "seed": 9935, "sheet": "item_paper_ledger", "flat": True},
}


def tasks() -> list[Task]:
    out = []
    for item_id, p in ITEMS.items():
        params = {"name": item_id, **p}
        out.append(Task(name=f"model:items/wild4_relay/{item_id}", group="models",
                        outputs=[f"models/items/wild4_relay/{item_id}.glb"],
                        sources=blender_sources("item_paper"), params=params, blender="item_paper"))
    return out
