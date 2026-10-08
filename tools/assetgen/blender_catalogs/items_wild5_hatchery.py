"""Key and note item models of the Silver Run fish hatchery (w5_fish_hatchery, wilderness set pieces round 5):
models/items/wild5_hatchery/<id>.glb, made by the shared item_paper generator; game/data/items/wild5_hatchery.json points
each item's "model" here."""
from __future__ import annotations

from ..core.registry import Task, blender_sources

ITEMS: dict[str, dict] = {
    "w5_hatchery_lab_key": {"kind": "key", "seed": 9951, "metal": "item_steel_tool", "tag": "tag"},
    "w5_hatchery_house_key": {"kind": "key", "seed": 9952, "metal": "item_brass", "tag": "tag"},
    "note_w5_hatchery_feeding_chart": {"kind": "note", "seed": 9953, "sheet": "item_paper_ledger", "flat": True},
    "note_w5_hatchery_sampler_log": {"kind": "logbook", "seed": 9954},
    "note_w5_hatchery_manager_letter": {"kind": "note", "seed": 9955, "sheet": "item_paper_note", "flat": False},
    "note_w5_hatchery_spawn_log": {"kind": "logbook", "seed": 9956},
    "note_w5_hatchery_cordon_results": {"kind": "note", "seed": 9957, "sheet": "item_paper_ledger", "flat": True},
}


def tasks() -> list[Task]:
    out = []
    for item_id, p in ITEMS.items():
        params = {"name": item_id, **p}
        out.append(Task(name=f"model:items/wild5_hatchery/{item_id}", group="models",
                        outputs=[f"models/items/wild5_hatchery/{item_id}.glb"],
                        sources=blender_sources("item_paper"), params=params, blender="item_paper"))
    return out
