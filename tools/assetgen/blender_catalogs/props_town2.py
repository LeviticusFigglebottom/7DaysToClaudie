"""Town props II - Pell's Crossing School, Pell Volunteer Fire Station, Tamsin Valley Savings & Loan: one task
per prop id producing models/props/<id>.glb (clean), <id>_worn.glb and, for breakables and vehicle wrecks,
<id>_destroyed.glb; plus the bank vault door leaves for the POI kit (models/kit/door_vault.glb,
models/kit/door_vault_broken.glb; hinged at the origin like the other kit door leaves, no collision proxy).

Generator: blender/generators/props_town2.py (BUILDERS keyed by prop id, shared code in
blender/lib/props_int_*.py). Game data: game/data/props/town2.json, materials:
game/data/materials/props_town2.json, textures: textures/gen/town2.py.

mount: floor (origin bottom centre on the floor), surface (small props on counters / desks),
       wall (origin on the wall plane, bottom centre, front -Y), ceiling (hangs below the origin),
       door (kit door leaf: AO without a ground plane).
"""
from __future__ import annotations

import zlib

from ..core.registry import Task, blender_sources

CWD = ["clean", "worn", "destroyed"]
CW = ["clean", "worn"]

# id: (variants, mount, triangle budget, extra params)
PROPS: dict[str, tuple[list[str], str, int, dict]] = {
    # --- Pell's Crossing School ----------------------------------------------------------------
    "school_desk": (CWD, "floor", 2500, {}),
    "school_teacher_desk": (CWD, "floor", 3500, {}),
    "school_chalkboard": (CW, "wall", 1500, {}),
    "school_locker_bank": (CWD, "floor", 3000, {}),
    "school_bleachers": (CW, "floor", 4000, {}),
    "school_basketball_hoop": (CW, "wall", 2500, {}),
    "school_wall_bars": (CW, "wall", 1500, {}),
    "school_gym_mats": (CW, "floor", 2500, {}),
    "school_stage_lights": (CW, "ceiling", 3500, {}),
    "school_boiler": (CW, "floor", 5500, {}),
    "school_card_catalog": (CW, "floor", 3500, {}),
    "school_flagpole": (CW, "floor", 1500, {}),
    "school_bus_wreck": (CWD, "floor", 8000, {}),
    # --- Pell Volunteer Fire Station --------------------------------------------------------------
    "fire_engine_wreck": (CWD, "floor", 8000, {}),
    "fire_hose_rack": (CW, "wall", 2500, {}),
    "fire_turnout_locker": (CW, "floor", 6500, {}),
    "fire_pole": (CW, "floor", 800, {}),
    "fire_hose_hanging": (CW, "wall", 2500, {}),
    "fire_siren": (CW, "floor", 2000, {}),
    "fire_extinguisher": (CW, "wall", 800, {}),
    # --- Tamsin Valley Savings & Loan -------------------------------------------------------------
    "bank_vault_door": (CW, "floor", 2500, {}),
    "bank_teller_counter": (CWD, "floor", 4000, {}),
    "bank_deposit_boxes": (CWD, "floor", 3500, {}),
    "bank_stanchions": (CW, "floor", 1500, {}),
    "bank_money_bags": (CW, "floor", 1800, {}),
}

# Kit door leaves (models/kit/<id>.glb): id -> (condition used for wear, budget).
KIT: dict[str, tuple[str, int]] = {
    "door_vault": ("clean", 4500),
    "door_vault_broken": ("worn", 4500),
}


def tasks() -> list[Task]:
    out = []
    suffix = {"clean": "", "worn": "_worn", "destroyed": "_destroyed"}
    src = blender_sources("props_town2")
    for pid, (variants, mount, budget, extra) in PROPS.items():
        seed = zlib.crc32(pid.encode()) % 100000
        outputs = [f"models/props/{pid}{suffix[v]}.glb" for v in variants]
        params = {"prop": pid, "seed": seed, "variants": variants, "mount": mount, "budget": budget, **extra}
        out.append(Task(name=f"model:props/{pid}", group="models", outputs=outputs, sources=src, params=params,
                        blender="props_town2"))
    for kid, (cond, budget) in KIT.items():
        seed = zlib.crc32(kid.encode()) % 100000
        params = {"prop": kid, "seed": seed, "variants": [cond], "mount": "door", "budget": budget, "no_collision": True}
        out.append(Task(name=f"model:kit/{kid}", group="models", outputs=[f"models/kit/{kid}.glb"], sources=src, params=params,
                        blender="props_town2"))
    return out
