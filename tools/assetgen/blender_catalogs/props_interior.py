"""Interior props (abandoned 1990s homes, shops, diner, civic offices): one task per prop id producing
models/props/<id>.glb (clean), <id>_worn.glb and, for breakables, <id>_destroyed.glb.

Generators: blender/generators/props_interior_<family>.py (BUILDERS dict keyed by prop id), shared code in
blender/lib/props_int_*.py. Game data: game/data/props/interior.json, materials:
game/data/materials/props_interior.json.

mount: floor (origin bottom centre on the floor), surface (small props standing on counters/desks),
       wall (origin on the wall plane, bottom centre, front -Y), ceiling (origin on the ceiling plane, top
       centre, hangs down -Z).
"""
from __future__ import annotations

import zlib

from ..core.registry import Task, blender_sources

CWD = ["clean", "worn", "destroyed"]
CW = ["clean", "worn"]

# id: (family module suffix, variants, mount, triangle budget)
PROPS: dict[str, tuple[str, list[str], str, int]] = {
    # kitchen
    "kitchen_counter": ("kitchen", CWD, "floor", 3000),
    "kitchen_counter_sink": ("kitchen", CWD, "floor", 3000),
    "kitchen_wall_cabinet": ("kitchen", CWD, "wall", 3000),
    "fridge_old": ("kitchen", CWD, "floor", 3000),
    "stove_old": ("kitchen", CWD, "floor", 3000),
    "microwave": ("kitchen", CWD, "surface", 1500),
    "kitchen_table": ("kitchen", CWD, "floor", 3000),
    "kitchen_chair": ("kitchen", CWD, "floor", 1500),
    "trash_can_kitchen": ("kitchen", CWD, "floor", 1500),
    "dish_clutter": ("kitchen", CW, "surface", 1500),
    # living room
    "couch": ("living", CWD, "floor", 3000),
    "armchair": ("living", CWD, "floor", 3000),
    "recliner": ("living", CWD, "floor", 3000),
    "coffee_table": ("living", CWD, "floor", 3000),
    "side_table": ("living", CWD, "floor", 1500),
    "tv_crt": ("living", CWD, "floor", 3000),
    "bookshelf": ("living", CWD, "floor", 3000),
    "floor_lamp": ("living", CWD, "floor", 1500),
    "rug_oval": ("living", CW, "floor", 1500),
    "rug_rect": ("living", CW, "floor", 1500),
    # bedroom
    "bed_double": ("bedroom", CWD, "floor", 3000),
    "bed_single": ("bedroom", CWD, "floor", 3000),
    "mattress_dirty": ("bedroom", CW, "floor", 1500),
    "nightstand": ("bedroom", CWD, "floor", 1500),
    "dresser": ("bedroom", CWD, "floor", 3000),
    "wardrobe": ("bedroom", CWD, "floor", 3000),
    "crib": ("bedroom", CWD, "floor", 3000),
    "desk_small": ("bedroom", CWD, "floor", 3000),
    "chair_wood": ("bedroom", CWD, "floor", 1500),
    # bathroom
    "toilet": ("bath", CWD, "floor", 3000),
    "bathtub": ("bath", CW, "floor", 3000),
    "sink_pedestal": ("bath", CWD, "floor", 3000),
    "medicine_cabinet": ("bath", CWD, "wall", 1500),
    "towel_rack": ("bath", CW, "wall", 1500),
    # office / civic
    "office_desk": ("office", CWD, "floor", 3000),
    "office_chair": ("office", CWD, "floor", 3000),
    "filing_cabinet": ("office", CWD, "floor", 3000),
    "metal_shelf": ("office", CWD, "floor", 3000),
    "weapons_locker": ("office", CWD, "floor", 3000),
    "safe_small": ("office", CWD, "floor", 1500),
    "cork_board": ("office", CW, "wall", 1500),
    "water_cooler": ("office", CWD, "floor", 1500),
    "counter_reception": ("office", CWD, "floor", 3000),
    # store
    "store_shelf_gondola": ("store", CWD, "floor", 3000),
    "checkout_counter": ("store", CWD, "floor", 3000),
    "cash_register": ("store", CWD, "surface", 1500),
    "store_freezer": ("store", CWD, "floor", 3000),
    "pharmacy_counter": ("store", CWD, "floor", 3000),
    "pegboard_wall": ("store", CW, "wall", 3000),
    "paint_can_stack": ("store", CW, "floor", 1500),
    "lumber_stack": ("store", CW, "floor", 1500),
    "feed_sacks": ("store", CW, "floor", 1500),
    # diner
    "diner_booth": ("diner", CWD, "floor", 3000),
    "diner_table": ("diner", CWD, "floor", 1500),
    "diner_counter": ("diner", CWD, "floor", 3000),
    "diner_stool": ("diner", CWD, "floor", 1500),
    "coffee_machine": ("diner", CWD, "surface", 1500),
    "griddle": ("diner", CW, "surface", 1500),
    "menu_board": ("diner", CWD, "wall", 1500),
    # lights
    "ceiling_light": ("lights", CWD, "ceiling", 1500),
    "wall_sconce": ("lights", CWD, "wall", 1500),
    "desk_lamp": ("lights", CWD, "surface", 1500),
}


def tasks() -> list[Task]:
    out = []
    for pid, (fam, variants, mount, budget) in PROPS.items():
        module = f"props_interior_{fam}"
        seed = zlib.crc32(pid.encode()) % 100000
        suffix = {"clean": "", "worn": "_worn", "destroyed": "_destroyed"}
        outputs = [f"models/props/{pid}{suffix[v]}.glb" for v in variants]
        params = {"prop": pid, "seed": seed, "variants": variants, "mount": mount, "budget": budget}
        out.append(Task(name=f"model:props/{pid}", group="models", outputs=outputs, sources=blender_sources(module),
                        params=params, blender=module))
    return out
