"""Key and note item models of pool round 2 (random-town set pieces: the pawn and gun shop, the
cannery, the water works, the quarry office, the VFW post): models/items/town4/<id>.glb, made by the
shared item_paper generator; game/data/items/town4.json points each item's "model" here."""
from __future__ import annotations

from ..core.registry import Task, blender_sources

ITEMS: dict[str, dict] = {
    "town4_pawn_vault_key": {"kind": "key", "seed": 9701, "metal": "item_steel_tool", "tag": "lanyard"},
    "town4_cannery_cold_key": {"kind": "key", "seed": 9702, "metal": "item_brass", "tag": "tag"},
    "town4_waterworks_store_key": {"kind": "key", "seed": 9703, "metal": "item_brass", "tag": "tag"},
    "town4_quarry_magazine_key": {"kind": "key", "seed": 9704, "metal": "item_steel_tool", "tag": "tag"},
    "town4_vfw_cage_key": {"kind": "key", "seed": 9705, "metal": "item_brass", "tag": "tag"},
    "note_town4_pawn_book": {"kind": "logbook", "seed": 9711},
    "note_town4_pawn_order": {"kind": "note", "seed": 9712, "sheet": "item_paper_ledger", "flat": True},
    "note_town4_pawn_ray": {"kind": "note", "seed": 9713, "sheet": "item_paper_note", "flat": False},
    "note_town4_cannery_tally": {"kind": "logbook", "seed": 9714},
    "note_town4_cannery_requisition": {"kind": "note", "seed": 9715, "sheet": "item_paper_ledger", "flat": True},
    "note_town4_cannery_quartermaster": {"kind": "note", "seed": 9716, "sheet": "item_paper_note", "flat": False},
    "note_town4_waterworks_log": {"kind": "logbook", "seed": 9717},
    "note_town4_waterworks_boil": {"kind": "note", "seed": 9718, "sheet": "item_paper_ledger", "flat": True},
    "note_town4_waterworks_gus": {"kind": "note", "seed": 9719, "sheet": "item_paper_note", "flat": False},
    "note_town4_quarry_ticket": {"kind": "note", "seed": 9720, "sheet": "item_paper_ledger", "flat": True},
    "note_town4_quarry_seizure": {"kind": "note", "seed": 9721, "sheet": "item_paper_ledger", "flat": True},
    "note_town4_quarry_pete": {"kind": "note", "seed": 9722, "sheet": "item_paper_note", "flat": False},
    "note_town4_vfw_bulletin": {"kind": "note", "seed": 9723, "sheet": "item_paper_ledger", "flat": True},
    "note_town4_vfw_minutes": {"kind": "note", "seed": 9724, "sheet": "item_paper_ledger", "flat": True},
    "note_town4_vfw_qm": {"kind": "note", "seed": 9725, "sheet": "item_paper_note", "flat": False},
}


def tasks() -> list[Task]:
    out = []
    for item_id, p in ITEMS.items():
        params = {"name": item_id, **p}
        out.append(Task(name=f"model:items/town4/{item_id}", group="models", outputs=[f"models/items/town4/{item_id}.glb"],
                        sources=blender_sources("item_paper"), params=params, blender="item_paper"))
    return out
