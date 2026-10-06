"""Key and note item models of the wilderness set pieces, round 3 (Camp Tamarack, Elk Ridge Lodge, the Cordon
quarantine camp, the Haldane Place): models/items/wild3/<id>.glb, made by the shared item_paper generator;
game/data/items/wild3.json points each item's "model" here."""
from __future__ import annotations

from ..core.registry import Task, blender_sources

ITEMS: dict[str, dict] = {
    "w3_tamarack_walkin_key": {"kind": "key", "seed": 9801, "metal": "item_brass", "tag": "tag"},
    "w3_elk_gun_room_key": {"kind": "key", "seed": 9802, "metal": "item_brass", "tag": "lanyard"},
    "w3_qc_reefer_key": {"kind": "key", "seed": 9803, "metal": "item_steel_tool", "tag": "tag"},
    "w3_haldane_bunker_key": {"kind": "key", "seed": 9804, "metal": "item_steel_tool", "tag": "tag"},
    "note_w3_tamarack_log": {"kind": "logbook", "seed": 9805},
    "note_w3_tamarack_notice": {"kind": "note", "seed": 9806, "sheet": "item_paper_ledger", "flat": True},
    "note_w3_tamarack_letter": {"kind": "note", "seed": 9807, "sheet": "item_paper_note", "flat": False},
    "note_w3_tamarack_nell": {"kind": "note", "seed": 9808, "sheet": "item_paper_ledger", "flat": True},
    "note_w3_tamarack_ames": {"kind": "note", "seed": 9809, "sheet": "item_paper_note", "flat": False},
    "note_w3_elk_guestbook": {"kind": "logbook", "seed": 9810},
    "note_w3_elk_marit": {"kind": "note", "seed": 9811, "sheet": "item_paper_note", "flat": False},
    "note_w3_elk_arne": {"kind": "note", "seed": 9812, "sheet": "item_paper_ledger", "flat": True},
    "note_w3_elk_kennel": {"kind": "note", "seed": 9813, "sheet": "item_paper_ledger", "flat": True},
    "note_w3_qc_orders": {"kind": "note", "seed": 9814, "sheet": "item_paper_ledger", "flat": True},
    "note_w3_qc_screening": {"kind": "note", "seed": 9815, "sheet": "item_paper_ledger", "flat": True},
    "note_w3_qc_ruiz": {"kind": "note", "seed": 9816, "sheet": "item_paper_note", "flat": False},
    "note_w3_qc_vance": {"kind": "note", "seed": 9817, "sheet": "item_paper_note", "flat": False},
    "note_w3_qc_tower": {"kind": "note", "seed": 9818, "sheet": "item_paper_note", "flat": False},
    "note_w3_haldane_della": {"kind": "logbook", "seed": 9819},
    "note_w3_haldane_rota": {"kind": "note", "seed": 9820, "sheet": "item_paper_ledger", "flat": True},
    "note_w3_haldane_tom": {"kind": "note", "seed": 9821, "sheet": "item_paper_note", "flat": False},
}


def tasks() -> list[Task]:
    out = []
    for item_id, p in ITEMS.items():
        params = {"name": item_id, **p}
        out.append(Task(name=f"model:items/wild3/{item_id}", group="models", outputs=[f"models/items/wild3/{item_id}.glb"],
                        sources=blender_sources("item_paper"), params=params, blender="item_paper"))
    return out
