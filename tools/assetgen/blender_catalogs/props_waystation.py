"""Waystation 9 props - the Remand Program's trader relay post built into the Cordon wall where the river
leaves the valley: one task per prop id producing models/props/<id>.glb (clean), <id>_worn.glb and, for
the hesco barrier, <id>_destroyed.glb.

Task names are model:props/waystation/<id> (outputs stay models/props/<id>*.glb) so `--match waystation`
selects the whole family, textures included.

Generator: blender/generators/props_waystation.py (BUILDERS keyed by prop id, shared code in
blender/lib/props_int_*.py). Game data: game/data/props/waystation.json, materials:
game/data/materials/props_waystation.json, textures: textures/gen/waystation.py.

mount: floor (origin bottom centre on the ground, front -Y in Blender = +Z in Godot).
"""
from __future__ import annotations

import zlib

from ..core.registry import Task, blender_sources

CWD = ["clean", "worn", "destroyed"]
CW = ["clean", "worn"]

# id: (variants, mount, triangle budget, extra params)
PROPS: dict[str, tuple[list[str], str, int, dict]] = {
    "waystation_counter": (CW, "floor", 9000, {}),
    "waystation_board": (CW, "floor", 3000, {}),
    "waystation_tower": (CW, "floor", 9000, {}),
    "waystation_barrier": (CWD, "floor", 5000, {}),
    "waystation_gate": (CW, "floor", 3000, {}),
    "waystation_sign": (CW, "floor", 1500, {}),
    "waystation_floodlight": (CW, "floor", 4000, {}),
    "waystation_supply_stack": (CW, "floor", 3500, {}),
}


def tasks() -> list[Task]:
    out = []
    suffix = {"clean": "", "worn": "_worn", "destroyed": "_destroyed"}
    src = blender_sources("props_waystation")
    for pid, (variants, mount, budget, extra) in PROPS.items():
        seed = zlib.crc32(pid.encode()) % 100000
        outputs = [f"models/props/{pid}{suffix[v]}.glb" for v in variants]
        params = {"prop": pid, "seed": seed, "variants": variants, "mount": mount, "budget": budget, **extra}
        out.append(Task(name=f"model:props/waystation/{pid}", group="models", outputs=outputs, sources=src, params=params,
                        blender="props_waystation"))
    return out
