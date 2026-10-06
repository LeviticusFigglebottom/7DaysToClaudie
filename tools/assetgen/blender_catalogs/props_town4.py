"""Town props IV, pool round 2 - the cannery, the water works pump house, the quarry office, the Pawn & Gun
and the VFW post: one task per prop id producing models/props/<id>.glb (clean), <id>_worn.glb and, for
breakables, <id>_destroyed.glb.

Task names are model:props/town4/<id> (outputs stay models/props/<id>*.glb) so `--match town4` selects the
whole family, textures included.

Generator: blender/generators/props_town4.py (BUILDERS keyed by prop id, shared code in
blender/lib/props_int_*.py and props_ext_kit.py). Game data: game/data/props/town4.json, materials:
game/data/materials/props_town4.json, textures: textures/gen/town4.py.

mount: floor (origin bottom centre on the floor), wall (origin on the wall plane, bottom centre, front -Y).
"""
from __future__ import annotations

import zlib

from ..core.registry import Task, blender_sources

CWD = ["clean", "worn", "destroyed"]
CW = ["clean", "worn"]

# id: (variants, mount, triangle budget, extra params)
PROPS: dict[str, tuple[list[str], str, int, dict]] = {
    # --- the cannery ----------------------------------------------------------------------------
    "cannery_retort": (CW, "floor", 8000, {}),
    "cannery_conveyor": (CWD, "floor", 3000, {}),
    "cannery_filler": (CW, "floor", 7000, {}),
    "cannery_can_pallet": (CWD, "floor", 3000, {}),
    "cannery_sorting_table": (CWD, "floor", 3000, {}),
    "cannery_tote_stack": (CW, "floor", 2000, {}),
    # --- the water works pump house ------------------------------------------------------------
    "pump_station_pump": (CW, "floor", 8000, {}),
    "pump_pipe_manifold": (CW, "floor", 6000, {}),
    "pump_pipe_manifold_wall": (CW, "wall", 5000, {}),
    "pump_chlorinator": (CW, "floor", 4000, {}),
    "pump_control_panel": (CW, "wall", 3000, {}),
    # --- the quarry office ---------------------------------------------------------------------
    "quarry_magazine": (CWD, "floor", 3000, {}),
    "quarry_core_rack": (CW, "floor", 3500, {}),
    "quarry_drill_steel_rack": (CW, "floor", 3000, {}),
    "quarry_scale_terminal": (CW, "floor", 3500, {}),
    # --- the Pawn & Gun ------------------------------------------------------------------------
    "pawn_gun_case": (CWD, "floor", 3500, {}),
    "pawn_long_gun_rack": (CW, "wall", 3000, {}),
    "pawn_shelf_mixed": (CWD, "floor", 3500, {}),
    "pawn_security_grille": (CW, "wall", 2500, {}),
    "pawn_ammo_shelf": (CWD, "floor", 3500, {}),
    # --- the VFW post --------------------------------------------------------------------------
    "vfw_honor_wall": (CW, "wall", 3500, {}),
    "vfw_flag_stand": (CW, "floor", 2000, {}),
    "vfw_memorial_case": (CWD, "floor", 3000, {}),
    "vfw_bar_taps": (CW, "wall", 4000, {}),
}


def tasks() -> list[Task]:
    out = []
    suffix = {"clean": "", "worn": "_worn", "destroyed": "_destroyed"}
    src = blender_sources("props_town4")
    for pid, (variants, mount, budget, extra) in PROPS.items():
        seed = zlib.crc32(pid.encode()) % 100000
        outputs = [f"models/props/{pid}{suffix[v]}.glb" for v in variants]
        params = {"prop": pid, "seed": seed, "variants": variants, "mount": mount, "budget": budget, **extra}
        out.append(Task(name=f"model:props/town4/{pid}", group="models", outputs=outputs, sources=src, params=params,
                        blender="props_town4"))
    return out
