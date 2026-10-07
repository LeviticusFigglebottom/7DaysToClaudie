"""Key and note item models of the Kettle Creek backcountry ranger station (wilderness round 4,
game/data/pois/buildings/w4_backcountry_ranger_station.json): models/items/wild4_ranger/<id>.glb, made by the
shared item_paper generator; game/data/items/wild4_ranger.json points each item's "model" here."""
from __future__ import annotations

from ..core.registry import Task, blender_sources

ITEMS: dict[str, dict] = {
    "w4_ranger_tower_key": {"kind": "key", "seed": 9901, "metal": "item_brass", "tag": "tag"},
    "w4_ranger_district_key": {"kind": "key", "seed": 9902, "metal": "item_steel_tool", "tag": "lanyard"},
    "note_w4_ranger_district_log": {"kind": "logbook", "seed": 9903},
    "note_w4_ranger_roster": {"kind": "note", "seed": 9904, "sheet": "item_paper_ledger", "flat": True},
    "note_w4_ranger_letter": {"kind": "note", "seed": 9905, "sheet": "item_paper_note", "flat": False},
    "note_w4_ranger_weather_log": {"kind": "note", "seed": 9906, "sheet": "item_paper_ledger", "flat": True},
}


def tasks() -> list[Task]:
    out = []
    for item_id, p in ITEMS.items():
        params = {"name": item_id, **p}
        out.append(Task(name=f"model:items/wild4_ranger/{item_id}", group="models", outputs=[f"models/items/wild4_ranger/{item_id}.glb"],
                        sources=blender_sources("item_paper"), params=params, blender="item_paper"))
    return out
