"""Key and note item models of the Kell Shelter (w4_hillside_bunker, forest set pieces round 4):
models/items/wild4_bunker/<id>.glb, made by the shared item_paper generator; game/data/items/wild4_bunker.json
points each item's "model" here."""
from __future__ import annotations

from ..core.registry import Task, blender_sources

ITEMS: dict[str, dict] = {
    "w4_bunker_blast_key": {"kind": "key", "seed": 9901, "metal": "item_brass", "tag": "tag"},
    "note_w4_bunker_journal": {"kind": "logbook", "seed": 9902},
    "note_w4_bunker_letter": {"kind": "note", "seed": 9903, "sheet": "item_paper_note", "flat": False},
    "note_w4_bunker_ledger": {"kind": "note", "seed": 9904, "sheet": "item_paper_ledger", "flat": True},
    "note_w4_bunker_radio_log": {"kind": "logbook", "seed": 9905},
}


def tasks() -> list[Task]:
    out = []
    for item_id, p in ITEMS.items():
        params = {"name": item_id, **p}
        out.append(Task(name=f"model:items/wild4_bunker/{item_id}", group="models",
                        outputs=[f"models/items/wild4_bunker/{item_id}.glb"],
                        sources=blender_sources("item_paper"), params=params, blender="item_paper"))
    return out
