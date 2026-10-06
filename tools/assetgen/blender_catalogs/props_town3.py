"""Props of the town pool buildings (Suds & Spin Laundromat, Hollowmere Grocery, Bracken Lumber & Feed, Pell
County Library, KHLW Valley Radio): one task per prop id producing models/props/<id>.glb (clean),
<id>_worn.glb and, for breakables, <id>_destroyed.glb; plus the models of their keys and notes
(models/items/town3/<id>.glb, made by the shared item_paper generator; game/data/items/town3.json points
each item's "model" there).

Generator: blender/generators/props_town3.py (BUILDERS keyed by builder name). Game data:
game/data/props/town3.json, materials: game/data/materials/props_town3.json, textures:
textures/gen/town3.py (the town3_print atlas).

mount: floor (origin bottom centre on the floor), wall (origin on the wall plane, bottom centre, front -Y).
"""
from __future__ import annotations

import zlib

from ..core.registry import Task, blender_sources

CWD = ["clean", "worn", "destroyed"]
CW = ["clean", "worn"]

# id: (variants, mount, triangle budget, extra params - "builder" names a shared builder function)
PROPS: dict[str, tuple[list[str], str, int, dict]] = {
    # --- Suds & Spin Laundromat --------------------------------------------------------------------
    "town3_washer": (CWD, "floor", 3000, {}),
    "town3_dryer": (CWD, "floor", 3500, {}),
    "town3_folding_table": (CWD, "floor", 2500, {}),
    "town3_laundry_cart": (CW, "floor", 3000, {}),
    "town3_change_machine": (CWD, "floor", 2000, {}),
    "town3_sign_suds": (CW, "wall", 1500, {"builder": "facade_sign", "cell": "sign_suds", "w": 3.2, "h": 0.8}),
    # --- Hollowmere Grocery -----------------------------------------------------------------------------
    "town3_grocery_shelf": (CWD, "floor", 4500, {"aisle": 0}),
    "town3_grocery_shelf_2": (CWD, "floor", 4500, {"builder": "town3_grocery_shelf", "aisle": 1}),
    "town3_grocery_shelf_3": (CWD, "floor", 4500, {"builder": "town3_grocery_shelf", "aisle": 2}),
    "town3_grocery_shelf_4": (CWD, "floor", 4500, {"builder": "town3_grocery_shelf", "aisle": 3}),
    "town3_grocery_shelf_fallen": (CW, "floor", 3500, {}),
    "town3_cooler_case": (CWD, "floor", 5000, {}),
    "town3_butcher_counter": (CWD, "floor", 4000, {}),
    "town3_reefer_trailer": (CW, "floor", 8000, {}),
    "town3_sign_grocery": (CW, "wall", 1500, {"builder": "facade_sign", "cell": "sign_grocery", "w": 5.0, "h": 1.25, "lamps": True}),
    # --- Bracken Lumber & Feed ---------------------------------------------------------------------------
    "town3_forklift": (CW, "floor", 6000, {}),
    "town3_lumber_rack": (CWD, "floor", 4000, {}),
    "town3_grain_bin": (CW, "floor", 6000, {}),
    "town3_sign_lumber": (CW, "wall", 1500, {"builder": "facade_sign", "cell": "sign_lumber", "w": 4.4, "h": 1.1, "lamps": True}),
    # --- Pell County Library -----------------------------------------------------------------------------
    "town3_library_stack": (CWD, "floor", 4000, {"label": 3}),
    "town3_library_stack_b": (CWD, "floor", 4000, {"builder": "town3_library_stack", "label": 14}),
    "town3_card_catalog": (CWD, "floor", 4500, {}),
    "town3_reading_table": (CWD, "floor", 3000, {}),
    "town3_circulation_desk": (CWD, "floor", 3500, {}),
    "town3_book_cart": (CW, "floor", 2500, {}),
    "town3_kids_table": (CWD, "floor", 2500, {}),
    "town3_sign_library": (CW, "wall", 1500, {"builder": "facade_sign", "cell": "sign_library", "w": 3.0, "h": 0.75}),
    # --- KHLW Valley Radio -------------------------------------------------------------------------------
    "town3_studio_desk": (CWD, "floor", 3500, {}),
    "town3_equipment_rack": (CWD, "floor", 2500, {}),
    "town3_transmitter": (CWD, "floor", 2500, {}),
    "town3_on_air_sign": (CWD, "wall", 2500, {}),
    "town3_generator": (CWD, "floor", 4000, {}),
    "town3_lattice_mast": (CW, "floor", 6000, {"floor_height": 0.15}),
    "town3_mast_rail": (CW, "floor", 600, {}),
    "town3_relay_cabinet": (CWD, "floor", 1500, {}),
    "town3_sign_khlw": (CW, "wall", 1500, {"builder": "facade_sign", "cell": "sign_khlw", "w": 3.0, "h": 0.75, "lamps": True}),
}

# Key / note item models (item_paper generator): item id -> params.
ITEMS: dict[str, dict] = {
    "t3_suds_stair_key": {"kind": "key", "seed": 9611, "metal": "item_brass", "tag": "tag"},
    "t3_grocery_cold_key": {"kind": "key", "seed": 9612, "metal": "item_steel_tool", "tag": "lanyard"},
    "t3_bracken_office_key": {"kind": "key", "seed": 9613, "metal": "item_steel_tool", "tag": "tag"},
    "t3_library_cage_key": {"kind": "key", "seed": 9614, "metal": "item_brass", "tag": "tag"},
    "t3_khlw_relay_key": {"kind": "key", "seed": 9615, "metal": "item_steel_tool", "tag": "lanyard"},
    "note_t3_suds_notice": {"kind": "note", "seed": 9621, "sheet": "item_paper_ledger", "flat": True},
    "note_t3_suds_ledger": {"kind": "logbook", "seed": 9622},
    "note_t3_suds_bauer": {"kind": "note", "seed": 9623, "sheet": "item_paper_note"},
    "note_t3_grocery_ration": {"kind": "note", "seed": 9624, "sheet": "item_paper_ledger", "flat": True},
    "note_t3_grocery_log": {"kind": "logbook", "seed": 9625},
    "note_t3_grocery_lading": {"kind": "note", "seed": 9626, "sheet": "item_paper_ledger", "flat": True},
    "note_t3_bracken_order": {"kind": "note", "seed": 9627, "sheet": "item_paper_ledger", "flat": True},
    "note_t3_bracken_tally": {"kind": "logbook", "seed": 9628},
    "note_t3_bracken_walt": {"kind": "note", "seed": 9629, "sheet": "item_paper_note"},
    "note_t3_library_returns": {"kind": "logbook", "seed": 9630},
    "note_t3_library_ida": {"kind": "note", "seed": 9631, "sheet": "item_paper_note"},
    "note_t3_library_archive": {"kind": "note", "seed": 9632, "sheet": "item_paper_ledger", "flat": True},
    "note_t3_khlw_day3": {"kind": "note", "seed": 9633, "sheet": "item_paper_ledger", "flat": True},
    "note_t3_khlw_day9": {"kind": "note", "seed": 9634, "sheet": "item_paper_ledger", "flat": True},
    "note_t3_khlw_bud": {"kind": "logbook", "seed": 9635},
}


def tasks() -> list[Task]:
    out = []
    suffix = {"clean": "", "worn": "_worn", "destroyed": "_destroyed"}
    for pid, (variants, mount, budget, extra) in PROPS.items():
        seed = zlib.crc32(pid.encode()) % 100000
        outputs = [f"models/props/{pid}{suffix[v]}.glb" for v in variants]
        params = {"prop": pid, "seed": seed, "variants": variants, "mount": mount, "budget": budget, **extra}
        out.append(Task(name=f"model:props/{pid}", group="models", outputs=outputs, sources=blender_sources("props_town3"),
                        params=params, blender="props_town3"))
    for item_id, p in ITEMS.items():
        params = {"name": item_id, **p}
        out.append(Task(name=f"model:items/town3/{item_id}", group="models", outputs=[f"models/items/town3/{item_id}.glb"],
                        sources=blender_sources("item_paper"), params=params, blender="item_paper"))
    return out
