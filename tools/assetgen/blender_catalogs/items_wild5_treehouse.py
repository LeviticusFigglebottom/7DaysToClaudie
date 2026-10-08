"""Key and note item models of the Treehouse Holdout (w5_treehouse_holdout, wilderness set pieces round 5):
models/items/wild5_treehouse/<id>.glb, made by the shared item_paper generator; game/data/items/wild5_treehouse.json
points each item's "model" here."""
from __future__ import annotations

from ..core.registry import Task, blender_sources

ITEMS: dict[str, dict] = {
    "w5_treehouse_nest_key": {"kind": "key", "seed": 9951, "metal": "item_brass"},
    "note_w5_treehouse_diary": {"kind": "note", "seed": 9952, "sheet": "item_paper_note", "flat": False},
    "note_w5_treehouse_rules": {"kind": "note", "seed": 9953, "sheet": "item_paper_ledger", "flat": True},
    "note_w5_treehouse_curtis": {"kind": "note", "seed": 9954, "sheet": "item_paper_note", "flat": False},
    "note_w5_treehouse_dale": {"kind": "logbook", "seed": 9955},
}


def tasks() -> list[Task]:
    out = []
    for item_id, p in ITEMS.items():
        params = {"name": item_id, **p}
        out.append(Task(name=f"model:items/wild5_treehouse/{item_id}", group="models",
                        outputs=[f"models/items/wild5_treehouse/{item_id}.glb"],
                        sources=blender_sources("item_paper"), params=params, blender="item_paper"))
    return out
