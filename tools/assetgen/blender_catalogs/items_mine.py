"""Key and note item models of the Corvane Larkspur Adit (ADR-0044): models/items/mine/<id>.glb,
made by the shared item_paper generator; game/data/items/mine.json points each item's "model" here."""
from __future__ import annotations

from ..core.registry import Task, blender_sources

ITEMS: dict[str, dict] = {
    "corvane_magazine_key": {"kind": "key", "seed": 9801, "metal": "item_brass", "tag": "tag"},
    "corvane_winze_key": {"kind": "key", "seed": 9802, "metal": "item_steel_tool", "tag": "lanyard"},
    "note_corvane_shift_log": {"kind": "logbook", "seed": 9811},
    "note_corvane_breakthrough": {"kind": "note", "seed": 9812, "sheet": "item_paper_ledger", "flat": True},
    "note_corvane_refuge": {"kind": "note", "seed": 9813, "sheet": "item_paper_note", "flat": False},
    "note_corvane_program_seal": {"kind": "note", "seed": 9814, "sheet": "item_paper_ledger", "flat": True},
}


def tasks() -> list[Task]:
    out = []
    for item_id, p in ITEMS.items():
        params = {"name": item_id, **p}
        out.append(Task(name=f"model:items/mine/{item_id}", group="models", outputs=[f"models/items/mine/{item_id}.glb"],
                        sources=blender_sources("item_paper"), params=params, blender="item_paper"))
    return out
