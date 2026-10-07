"""Key and note item models of the Cordon transport wreck (w4_cordon_plane_wreck, forest set pieces round 4):
models/items/wild4_plane/<id>.glb, made by the shared item_paper generator; game/data/items/wild4_plane.json points
each item's "model" here."""
from __future__ import annotations

from ..core.registry import Task, blender_sources

ITEMS: dict[str, dict] = {
    "w4_plane_sample_key": {"kind": "key", "seed": 9901, "metal": "item_steel_tool", "tag": "tag"},
    "note_w4_plane_manifest": {"kind": "note", "seed": 9902, "sheet": "item_paper_ledger", "flat": True},
    "note_w4_plane_medic": {"kind": "note", "seed": 9903, "sheet": "item_paper_note", "flat": False},
    "note_w4_plane_pilot_log": {"kind": "logbook", "seed": 9904},
    "note_w4_plane_radio": {"kind": "note", "seed": 9905, "sheet": "item_paper_ledger", "flat": True},
}


def tasks() -> list[Task]:
    out = []
    for item_id, p in ITEMS.items():
        params = {"name": item_id, **p}
        out.append(Task(name=f"model:items/wild4_plane/{item_id}", group="models",
                        outputs=[f"models/items/wild4_plane/{item_id}.glb"], sources=blender_sources("item_paper"),
                        params=params, blender="item_paper"))
    return out
