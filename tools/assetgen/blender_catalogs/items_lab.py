"""Item models of the Corvane Field Lab (agent Y): models/items/lab/<id>.glb. Keys and papers come from the shared
item_paper generator, the earlier salvager's tether from item_gear, the keycard, the vault code card, the sealed
core canister, the research drive and the auto-injector from item_lab; game/data/items/lab.json points each
item's "model" here."""
from __future__ import annotations

from ..core.registry import Task, blender_sources

ITEMS: dict[str, tuple[str, dict]] = {
    "lab_station_keys": ("item_paper", {"kind": "key", "seed": 9901, "metal": "item_brass", "tag": "tag"}),
    "lab_containment_key": ("item_paper", {"kind": "key", "seed": 9902, "metal": "item_steel_tool", "tag": "lanyard"}),
    "lab_keycard": ("item_lab", {"kind": "card", "seed": 9903, "cell": "containment"}),
    "lab_vault_code": ("item_lab", {"kind": "card", "seed": 9904, "cell": "vault"}),
    "bloom_core_canister": ("item_lab", {"kind": "canister", "seed": 9905}),
    "lab_research_drive": ("item_lab", {"kind": "drive", "seed": 9906}),
    "lab_antifungal_ampoule": ("item_lab", {"kind": "injector", "seed": 9907}),
    "note_lab_core_log": ("item_paper", {"kind": "note", "seed": 9911, "sheet": "item_paper_ledger", "flat": True}),
    "note_lab_station_log": ("item_paper", {"kind": "logbook", "seed": 9912}),
    "note_lab_orders": ("item_paper", {"kind": "note", "seed": 9913, "sheet": "item_paper_ledger", "flat": True}),
    "note_lab_sample_log": ("item_paper", {"kind": "note", "seed": 9914, "sheet": "item_paper_note", "flat": False}),
    "note_lab_torvald": ("item_paper", {"kind": "note", "seed": 9915, "sheet": "item_paper_ledger", "flat": True}),
    "note_lab_tether_3907": ("item_gear", {"kind": "tether", "seed": 3907}),
}


def tasks() -> list[Task]:
    out = []
    for item_id, (gen, p) in ITEMS.items():
        params = {"name": item_id, **p}
        out.append(Task(name=f"model:items/lab/{item_id}", group="models", outputs=[f"models/items/lab/{item_id}.glb"],
                        sources=blender_sources(gen), params=params, blender=gen))
    return out
