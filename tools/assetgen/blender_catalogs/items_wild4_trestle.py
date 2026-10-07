"""Key and note item models of the trestle tunnel (w4_trestle_tunnel, forest set pieces round 4, ADR-0053):
models/items/wild4_trestle/<id>.glb, made by the shared item_paper generator; game/data/items/wild4_trestle.json points
each item's "model" here."""
from __future__ import annotations

from ..core.registry import Task, blender_sources

ITEMS: dict[str, dict] = {
    "w4_trestle_bulkhead_key": {"kind": "key", "seed": 9901, "metal": "item_steel_tool", "tag": "tag"},
    "w4_trestle_niche_key": {"kind": "key", "seed": 9902, "metal": "item_brass", "tag": "tag"},
    "note_w4_trestle_watch_log": {"kind": "logbook", "seed": 9903},
    "note_w4_trestle_work_order": {"kind": "note", "seed": 9904, "sheet": "item_paper_ledger", "flat": True},
    "note_w4_trestle_demolition_order": {"kind": "note", "seed": 9905, "sheet": "item_paper_ledger", "flat": True},
    "note_w4_trestle_crew_letter": {"kind": "note", "seed": 9906, "sheet": "item_paper_note", "flat": False},
}


def tasks() -> list[Task]:
    out = []
    for item_id, p in ITEMS.items():
        params = {"name": item_id, **p}
        out.append(Task(name=f"model:items/wild4_trestle/{item_id}", group="models",
                        outputs=[f"models/items/wild4_trestle/{item_id}.glb"],
                        sources=blender_sources("item_paper"), params=params, blender="item_paper"))
    return out
