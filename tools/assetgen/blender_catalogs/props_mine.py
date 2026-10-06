"""Larkspur Exploration Adit props (the Corvane Mining Co.'s exploration mine and the limestone cave its drifts
broke into): one task per prop id producing models/props/<id>.glb (clean), <id>_worn.glb and, for the
timber set and the ore car, <id>_destroyed.glb.

Task names are model:props/mine/<id> (outputs stay models/props/<id>*.glb) so `--match props/mine` selects
the family.

Generator: blender/generators/props_mine.py (BUILDERS keyed by prop id, shared code in
blender/lib/props_int_*.py). Game data: game/data/props/mine.json, materials:
game/data/materials/props_mine.json, textures: textures/gen/mine.py (+ kit_rock.py for the rock sets).

mount: floor (origin bottom centre on the ground, front -Y in Blender = +Z in Godot), wall (origin on the
wall plane), ceiling (origin on the ceiling plane, hangs below).
"""
from __future__ import annotations

import zlib

from ..core.registry import Task, blender_sources

CWD = ["clean", "worn", "destroyed"]
CW = ["clean", "worn"]

# id: (variants, mount, triangle budget, extra params)
PROPS: dict[str, tuple[list[str], str, int, dict]] = {
    "mine_timber_set": (CWD, "floor", 3000, {}),
    "mine_rail_straight": (CW, "floor", 1500, {}),
    "mine_ore_cart": (CWD, "floor", 4000, {}),
    "mine_hoist": (CW, "floor", 7000, {}),
    "mine_headframe": (CW, "floor", 10000, {}),
    "mine_cage": (CW, "floor", 4000, {}),
    "mine_rock_face": (CW, "floor", 3000, {}),
    "mine_rock_face_b": (CW, "floor", 3000, {}),
    "mine_rock_face_c": (CW, "floor", 3000, {}),
    "mine_rock_pile": (CW, "floor", 3000, {}),
    "mine_stalagmites": (CW, "floor", 3000, {}),
    "mine_lamp_string": (CW, "ceiling", 1500, {}),
    "mine_powder_box": (CW, "floor", 1500, {}),
    "mine_tool_rack": (CW, "floor", 3000, {}),
    "mine_safety_board": (CW, "wall", 3000, {}),
}


def tasks() -> list[Task]:
    out = []
    suffix = {"clean": "", "worn": "_worn", "destroyed": "_destroyed"}
    src = blender_sources("props_mine")
    for pid, (variants, mount, budget, extra) in PROPS.items():
        seed = zlib.crc32(pid.encode()) % 100000
        outputs = [f"models/props/{pid}{suffix[v]}.glb" for v in variants]
        params = {"prop": pid, "seed": seed, "variants": variants, "mount": mount, "budget": budget, **extra}
        out.append(Task(name=f"model:props/mine/{pid}", group="models", outputs=outputs, sources=src, params=params,
                        blender="props_mine"))
    return out
