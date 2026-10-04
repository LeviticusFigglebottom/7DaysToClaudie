"""Item models (models/items/<id>.glb), first-person viewmodels (models/viewmodels/<viewmodel>.glb) and
inventory/UI props. One task per item id; items whose equip block names a viewmodel also own the
viewmodel output (same mesh, exported in the viewmodel frame). Item ids / viewmodel names are read
from game/data/items/*.json so the catalog follows the content; every id must have a SPEC entry."""
from __future__ import annotations

import json
import sys

from ..core.paths import DATA
from ..core.registry import Task, blender_sources

# item id -> (generator module, params)
SPEC: dict[str, tuple[str, dict]] = {
    # tools / weapons (viewmodel frame: grip at origin, handle +Z, edge -Y)
    "stone_axe": ("item_tools", {"kind": "stone_axe", "seed": 11}),
    "hatchet": ("item_tools", {"kind": "hatchet", "seed": 12}),
    "crude_spear": ("item_tools", {"kind": "crude_spear", "seed": 13}),
    "stone_club": ("item_tools", {"kind": "stone_club", "seed": 14}),
    "steel_pipe": ("item_tools", {"kind": "steel_pipe", "seed": 15}),
    "machete": ("item_tools", {"kind": "machete", "seed": 16}),
    "shovel": ("item_tools", {"kind": "shovel", "seed": 17}),
    "claw_hammer": ("item_tools", {"kind": "claw_hammer", "seed": 18}),
    "kitchen_knife": ("item_tools", {"kind": "kitchen_knife", "seed": 19}),
    "torch": ("item_tools", {"kind": "torch", "seed": 20}),
    # gear (pointing frame for lighter / flashlight / revolver: grip at origin, axis -Y)
    "revolver": ("item_gear", {"kind": "revolver", "seed": 21}),
    "lighter": ("item_gear", {"kind": "lighter", "seed": 22}),
    "flashlight": ("item_gear", {"kind": "flashlight", "seed": 23}),
    "ammo_38": ("item_gear", {"kind": "ammo_38", "seed": 24}),
    "tether": ("item_gear", {"kind": "tether", "seed": 25}),
    "repair_kit": ("item_gear", {"kind": "repair_kit", "seed": 26}),
    "can_chime": ("item_gear", {"kind": "can_chime", "seed": 27}),
    # consumables
    "ration_bar": ("item_food", {"kind": "ration_bar", "seed": 31}),
    "canned_beans": ("item_food", {"kind": "can", "seed": 32, "label": "item_can_label_a", "size": [0.0765, 0.112], "dent": 0.6}),
    "canned_stew": ("item_food", {"kind": "can", "seed": 33, "label": "item_can_label_b", "size": [0.087, 0.118], "dent": 0.2}),
    "hot_stew": ("item_food", {"kind": "can_open", "seed": 34, "label": "item_can_label_b_sooty", "size": [0.087, 0.118], "contents": "item_stew"}),
    "dog_food": ("item_food", {"kind": "can", "seed": 35, "label": "item_can_label_c", "size": [0.086, 0.098], "dent": 0.4}),
    "soda_can": ("item_food", {"kind": "soda", "seed": 36}),
    "empty_can": ("item_food", {"kind": "can_open", "seed": 37, "label": None, "size": [0.0765, 0.112]}),
    "huckleberries": ("item_food", {"kind": "berries", "seed": 38}),
    "wild_mushroom": ("item_food", {"kind": "mushroom", "seed": 39}),
    "cooked_mushroom": ("item_food", {"kind": "mushroom_skewer", "seed": 40}),
    "water_bottle_empty": ("item_food", {"kind": "bottle", "seed": 41, "fill": 0.0}),
    "water_bottle_dirty": ("item_food", {"kind": "bottle", "seed": 42, "fill": 0.8, "water": "item_bottle_dirty"}),
    "water_bottle_clean": ("item_food", {"kind": "bottle", "seed": 43, "fill": 0.9, "water": "item_bottle_water"}),
    "glass_bottle": ("item_food", {"kind": "glass_bottle", "seed": 44}),
    "cloth_bandage": ("item_food", {"kind": "bandage", "seed": 45}),
    "first_aid_kit": ("item_food", {"kind": "first_aid", "seed": 46}),
    "painkillers": ("item_food", {"kind": "blister", "seed": 47}),
    "antifungal": ("item_food", {"kind": "pill_bottle", "seed": 48}),
    "yarrow": ("item_food", {"kind": "yarrow", "seed": 49}),
    "yarrow_poultice": ("item_food", {"kind": "poultice", "seed": 50}),
    "bloom_sample": ("item_food", {"kind": "vial", "seed": 51}),
    "bloom_mycelium": ("item_food", {"kind": "mycelium", "seed": 52}),
    # resources
    "stick": ("item_resources", {"kind": "stick", "seed": 61}),
    "stone": ("item_resources", {"kind": "stone", "seed": 62}),
    "plant_fiber": ("item_resources", {"kind": "plant_fiber", "seed": 63}),
    "cordage": ("item_resources", {"kind": "cordage", "seed": 64}),
    "leaf_bundle": ("item_resources", {"kind": "leaf_bundle", "seed": 65}),
    "log": ("item_resources", {"kind": "log", "seed": 66}),
    "wood_plank": ("item_resources", {"kind": "plank", "seed": 67}),
    "cloth": ("item_resources", {"kind": "cloth", "seed": 68}),
    "bone": ("item_resources", {"kind": "bone", "seed": 69}),
    "nails": ("item_resources", {"kind": "nails", "seed": 70}),
    "scrap_metal": ("item_resources", {"kind": "scrap", "seed": 71}),
    "duct_tape": ("item_resources", {"kind": "duct_tape", "seed": 72}),
    "scrip": ("item_resources", {"kind": "scrip", "seed": 73}),
    # readables
    "schematic_spike_barrier": ("item_paper", {"kind": "schematic", "seed": 81, "sheet": "item_schematic_a"}),
    "schematic_log_cabin": ("item_paper", {"kind": "schematic", "seed": 82, "sheet": "item_schematic_b"}),
    "schematic_can_chime": ("item_paper", {"kind": "schematic", "seed": 83, "sheet": "item_schematic_c"}),
    "journal_timber_trade": ("item_paper", {"kind": "magazine", "seed": 84, "cover": "item_magazine_a"}),
    "journal_field_medicine": ("item_paper", {"kind": "magazine", "seed": 85, "cover": "item_magazine_b"}),
    "note_merrow_fridge": ("item_paper", {"kind": "note", "seed": 86, "sheet": "item_paper_note"}),
    "note_pharmacy_ledger": ("item_paper", {"kind": "note", "seed": 87, "sheet": "item_paper_ledger", "flat": True}),
    "note_ranger_log": ("item_paper", {"kind": "logbook", "seed": 88}),
    "note_diner_specials": ("item_paper", {"kind": "note", "seed": 92, "sheet": "item_paper_note"}),
    "note_hardware_inventory": ("item_paper", {"kind": "note", "seed": 93, "sheet": "item_paper_ledger", "flat": True}),
    "note_okafor_letter": ("item_paper", {"kind": "note", "seed": 94, "sheet": "item_paper_note"}),
    "pharmacy_key": ("item_paper", {"kind": "key", "seed": 89, "metal": "item_brass", "tag": "lanyard"}),
    "evidence_locker_key": ("item_paper", {"kind": "key", "seed": 90, "metal": "item_steel_tool", "tag": "tag"}),
    "field_manual": ("item_paper", {"kind": "manual", "seed": 91}),
}

# Inventory / UI props (not item ids) -> models/items/<id>.glb
UI_PROPS: dict[str, tuple[str, dict]] = {
    "salvage_roll": ("item_ui", {"kind": "salvage_roll", "seed": 101}),
    "work_slate": ("item_ui", {"kind": "work_slate", "seed": 102}),
    "supply_canister": ("item_ui", {"kind": "supply_canister", "seed": 103}),
    "tether_device": ("item_gear", {"kind": "tether", "seed": 25}),
}


def _items() -> list[tuple[str, str | None]]:
    out = []
    for f in sorted((DATA / "items").glob("*.json")):
        for d in json.loads(f.read_text()).get("defs", []):
            vm = (d.get("equip") or {}).get("viewmodel")
            model = d.get("model", f"items/{d['id']}")
            if model == f"items/{d['id']}":
                out.append((d["id"], vm))
    return out


def tasks() -> list[Task]:
    out: list[Task] = []
    for item_id, vm in _items():
        if item_id not in SPEC:
            print(f"[items] WARNING: no model spec for item '{item_id}'", file=sys.stderr)
            continue
        mod, p = SPEC[item_id]
        outputs = [f"models/items/{item_id}.glb"]
        if vm:
            outputs.append(f"models/viewmodels/{vm}.glb")
        params = {"name": item_id, **p}
        out.append(Task(name=f"model:items/{item_id}", group="models", outputs=outputs, sources=blender_sources(mod),
                        params=params, blender=mod))
    for prop_id, (mod, p) in UI_PROPS.items():
        params = {"name": prop_id, **p}
        out.append(Task(name=f"model:items/{prop_id}", group="models", outputs=[f"models/items/{prop_id}.glb"],
                        sources=blender_sources(mod), params=params, blender=mod))
    return out
