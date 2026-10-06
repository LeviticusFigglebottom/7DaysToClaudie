"""Key and note item models of Pell's Crossing's third block (the school, the fire station, the
Savings & Loan): models/items/town2/<id>.glb, made by the shared item_paper generator;
game/data/items/town2.json points each item's "model" here."""
from __future__ import annotations

from ..core.registry import Task, blender_sources

ITEMS: dict[str, dict] = {
    "town2_vault_combination": {"kind": "note", "seed": 9601, "sheet": "item_paper_ledger", "flat": True},
    "town2_isolation_key": {"kind": "key", "seed": 9602, "metal": "item_brass", "tag": "tag"},
    "town2_tower_keys": {"kind": "key", "seed": 9603, "metal": "item_steel_tool", "tag": "lanyard"},
    "note_town2_evac_notice": {"kind": "note", "seed": 9611, "sheet": "item_paper_ledger", "flat": True},
    "note_town2_school_register": {"kind": "logbook", "seed": 9612},
    "note_town2_school_chalkboard": {"kind": "note", "seed": 9613, "sheet": "item_paper_note"},
    "note_town2_isolation_orders": {"kind": "note", "seed": 9614, "sheet": "item_paper_ledger", "flat": True},
    "note_town2_fire_log": {"kind": "logbook", "seed": 9615},
    "note_town2_fire_duty_board": {"kind": "note", "seed": 9616, "sheet": "item_paper_ledger", "flat": True},
    "note_town2_bank_notice": {"kind": "note", "seed": 9617, "sheet": "item_paper_ledger", "flat": True},
    "note_town2_bank_ledger": {"kind": "logbook", "seed": 9618},
    "note_town2_vault_scratch": {"kind": "note", "seed": 9619, "sheet": "item_paper_note"},
}


def tasks() -> list[Task]:
    out = []
    for item_id, p in ITEMS.items():
        params = {"name": item_id, **p}
        out.append(Task(name=f"model:items/town2/{item_id}", group="models", outputs=[f"models/items/town2/{item_id}.glb"],
                        sources=blender_sources("item_paper"), params=params, blender="item_paper"))
    return out
