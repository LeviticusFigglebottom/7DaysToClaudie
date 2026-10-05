"""Civic props of Pell's Crossing (church, tavern, post office, grange hall, trailer, street fixtures): one
task per prop id producing models/props/<id>.glb (clean), <id>_worn.glb and, for breakables,
<id>_destroyed.glb; plus the models of the civic key and note items (models/items/civic/<id>.glb, made by
the shared item_paper generator; game/data/items/civic.json points each item's "model" there).

Generator: blender/generators/props_civic.py (BUILDERS keyed by builder name, shared code in
blender/lib/props_int_*.py). Game data: game/data/props/civic.json, materials:
game/data/materials/props_civic.json, textures: textures/gen/civic.py.

mount: floor (origin bottom centre on the floor), surface (small props standing on counters/desks),
       wall (origin on the wall plane, bottom centre, front -Y).
"""
from __future__ import annotations

import zlib

from ..core.registry import Task, blender_sources

CWD = ["clean", "worn", "destroyed"]
CW = ["clean", "worn"]

# id: (variants, mount, triangle budget, extra params - "builder" names a shared builder function)
PROPS: dict[str, tuple[list[str], str, int, dict]] = {
    # --- St. Ansel's Church ---------------------------------------------------------------------
    "civic_pew": (CWD, "floor", 3000, {}),
    "civic_altar": (CWD, "floor", 3500, {}),
    "civic_pulpit": (CWD, "floor", 3000, {}),
    "civic_hymn_board": (CW, "wall", 1500, {}),
    "civic_candle_stand": (CWD, "floor", 3000, {}),
    "civic_collection_box": (CWD, "floor", 1500, {}),
    "civic_reed_organ": (CWD, "floor", 3500, {}),
    "civic_baptismal_font": (CWD, "floor", 1500, {}),
    "civic_church_bell": (CWD, "floor", 3000, {}),
    "civic_steeple": (CW, "floor", 8000, {}),
    "civic_church_sign": (CWD, "floor", 2000, {}),
    "civic_iron_fence": (CWD, "floor", 2500, {}),
    "civic_headstone_round": (CWD, "floor", 1500, {"builder": "headstone", "shape": "round", "cell": 0}),
    "civic_headstone_round_b": (CWD, "floor", 1500, {"builder": "headstone", "shape": "round", "cell": 5}),
    "civic_headstone_gothic": (CWD, "floor", 1500, {"builder": "headstone", "shape": "gothic", "cell": 1}),
    "civic_headstone_gothic_b": (CWD, "floor", 1500, {"builder": "headstone", "shape": "gothic", "cell": 4}),
    "civic_headstone_tablet": (CWD, "floor", 1500, {"builder": "headstone", "shape": "tablet", "cell": 6, "stone": "marble"}),
    "civic_headstone_cross": (CWD, "floor", 1500, {"builder": "headstone", "shape": "cross", "cell": 2}),
    "civic_headstone_small": (CWD, "floor", 1500, {"builder": "headstone", "shape": "small", "cell": 3, "stone": "marble"}),
    "civic_headstone_plain": (CWD, "floor", 1500, {"builder": "headstone", "shape": "square", "cell": 7}),
    "civic_grave_mound": (CW, "floor", 2500, {}),
    "civic_hymnals": (CW, "surface", 1500, {}),
    # --- Northwoods Tavern ------------------------------------------------------------------------
    "civic_bar_counter": (CWD, "floor", 3500, {}),
    "civic_back_bar": (CWD, "floor", 6000, {}),
    "civic_beer_taps": (CW, "surface", 2500, {}),
    "civic_bar_stool": (CWD, "floor", 1500, {}),
    "civic_pool_table": (CWD, "floor", 4000, {}),
    "civic_jukebox": (CWD, "floor", 3000, {}),
    "civic_dartboard": (CW, "wall", 1500, {}),
    "civic_keg": (CWD, "floor", 1500, {}),
    "civic_beer_crates": (CW, "floor", 2000, {}),
    # --- Pell's Crossing post office ---------------------------------------------------------------
    "civic_po_counter": (CWD, "floor", 4000, {}),
    "civic_po_boxes": (CWD, "floor", 2500, {}),
    "civic_sorting_rack": (CWD, "floor", 3500, {}),
    "civic_parcel_cage": (CWD, "floor", 3000, {}),
    "civic_mail_cart": (CWD, "floor", 2500, {}),
    "civic_mail_sacks": (CW, "floor", 1500, {}),
    "civic_parcel_scale": (CW, "surface", 1500, {}),
    "civic_collection_mailbox": (CWD, "floor", 2000, {}),
    "civic_po_sign": (CW, "wall", 600, {}),
    # --- Pell's Crossing grange hall --------------------------------------------------------------
    "civic_folding_table": (CWD, "floor", 2500, {}),
    "civic_folding_chair": (CWD, "floor", 1500, {}),
    "civic_army_cot": (CWD, "floor", 3000, {}),
    "civic_relief_crate": (CWD, "floor", 3000, {}),
    "civic_stage_lectern": (CWD, "floor", 2000, {}),
    "civic_coat_rack": (CWD, "floor", 3000, {}),
    "civic_upright_piano": (CWD, "floor", 4000, {}),
    "civic_trophy_case": (CWD, "floor", 4000, {}),
    "civic_grange_banner": (CW, "wall", 1500, {}),
    "civic_shelter_board": (CW, "wall", 600, {}),
    "civic_blanket_pile": (CW, "floor", 2000, {}),
    # --- the trailer --------------------------------------------------------------------------------
    "civic_ham_radio": (CW, "surface", 2000, {}),
    "civic_antenna_mast": (CW, "floor", 4000, {}),
}

# Civic key / note item models (item_paper generator): item id -> params.
ITEMS: dict[str, dict] = {
    "civic_pantry_key": {"kind": "key", "seed": 9301, "metal": "item_brass", "tag": "tag"},
    "civic_tavern_keys": {"kind": "key", "seed": 9302, "metal": "item_steel_tool", "tag": "lanyard"},
    "civic_parcel_cage_key": {"kind": "key", "seed": 9303, "metal": "item_brass", "tag": "tag"},
    "civic_records_key": {"kind": "key", "seed": 9304, "metal": "item_steel_tool", "tag": "tag"},
    "note_civic_haskett_daybook": {"kind": "logbook", "seed": 9311},
    "note_civic_haskett_last": {"kind": "note", "seed": 9312, "sheet": "item_paper_note"},
    "note_civic_pantry_list": {"kind": "note", "seed": 9313, "sheet": "item_paper_ledger", "flat": True},
    "note_civic_tavern_tab": {"kind": "note", "seed": 9314, "sheet": "item_paper_ledger", "flat": True},
    "note_civic_lund_letter": {"kind": "note", "seed": 9315, "sheet": "item_paper_note"},
    "note_civic_convoy_manifest": {"kind": "note", "seed": 9316, "sheet": "item_paper_ledger", "flat": True},
    "note_civic_postmaster_log": {"kind": "logbook", "seed": 9317},
    "note_civic_dead_letter": {"kind": "note", "seed": 9318, "sheet": "item_paper_note"},
    "note_civic_grange_log": {"kind": "logbook", "seed": 9319},
    "note_civic_ward_chart": {"kind": "note", "seed": 9320, "sheet": "item_paper_ledger", "flat": True},
    "note_civic_evac_notice": {"kind": "note", "seed": 9321, "sheet": "item_paper_ledger", "flat": True},
    "note_civic_radio_log": {"kind": "logbook", "seed": 9322},
}


def tasks() -> list[Task]:
    out = []
    suffix = {"clean": "", "worn": "_worn", "destroyed": "_destroyed"}
    for pid, (variants, mount, budget, extra) in PROPS.items():
        seed = zlib.crc32(pid.encode()) % 100000
        outputs = [f"models/props/{pid}{suffix[v]}.glb" for v in variants]
        params = {"prop": pid, "seed": seed, "variants": variants, "mount": mount, "budget": budget, **extra}
        out.append(Task(name=f"model:props/{pid}", group="models", outputs=outputs, sources=blender_sources("props_civic"),
                        params=params, blender="props_civic"))
    for item_id, p in ITEMS.items():
        params = {"name": item_id, **p}
        out.append(Task(name=f"model:items/civic/{item_id}", group="models", outputs=[f"models/items/civic/{item_id}.glb"],
                        sources=blender_sources("item_paper"), params=params, blender="item_paper"))
    return out
