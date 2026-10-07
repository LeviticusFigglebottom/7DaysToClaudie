"""Key and note item models of Shiloh Chapel (w4_overgrown_chapel, forest set pieces round 4):
models/items/wild4_chapel/<id>.glb, made by the shared item_paper generator; game/data/items/wild4_chapel.json
points each item's "model" here."""
from __future__ import annotations

from ..core.registry import Task, blender_sources

ITEMS: dict[str, dict] = {
    "w4_chapel_vault_key": {"kind": "key", "seed": 9941, "metal": "item_iron_strap", "tag": "tag"},
    "note_w4_chapel_diary": {"kind": "logbook", "seed": 9942},
    "note_w4_chapel_register": {"kind": "logbook", "seed": 9943},
    "note_w4_chapel_grave_letter": {"kind": "note", "seed": 9944, "sheet": "item_paper_note", "flat": False},
    "note_w4_chapel_cordon_notice": {"kind": "note", "seed": 9945, "sheet": "item_paper_ledger", "flat": True},
    "note_w4_chapel_sexton": {"kind": "note", "seed": 9946, "sheet": "item_paper_note", "flat": False},
}


def tasks() -> list[Task]:
    out = []
    for item_id, p in ITEMS.items():
        params = {"name": item_id, **p}
        out.append(Task(name=f"model:items/wild4_chapel/{item_id}", group="models",
                        outputs=[f"models/items/wild4_chapel/{item_id}.glb"],
                        sources=blender_sources("item_paper"), params=params, blender="item_paper"))
    return out
