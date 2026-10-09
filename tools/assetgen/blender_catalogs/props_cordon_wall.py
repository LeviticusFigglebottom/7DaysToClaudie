"""The Cordon wall (region D7's south edge, DESIGN section 1): one task per prop id producing
models/props/<id>.glb (clean) and <id>_worn.glb.

Task names are model:props/cordon_wall/<id> (outputs stay models/props/<id>*.glb) so `--match cordon_wall`
selects the whole family (`--match cordon_` also catches textures cordon_print / cordon_concrete).

Generator: blender/generators/props_cordon_wall.py (BUILDERS keyed by prop id), which builds on the
Waystation kit's helpers in generators/props_waystation.py (listed as an extra source). Game data:
game/data/props/cordon.json, materials: game/data/materials/props_cordon.json, textures:
textures/gen/cordon.py.

mount: floor (origin on the wall line at the foot, front -Y in Blender = +Z in Godot = the valley side);
the notice board is wall-mounted (origin on the wall plane).
"""
from __future__ import annotations

import pathlib
import zlib

from ..core.registry import Task, blender_sources

CW = ["clean", "worn"]

# id: (variants, mount, triangle budget)
PROPS: dict[str, tuple[list[str], str, int]] = {
    "cordon_wall_panel": (CW, "floor", 3000),
    "cordon_wall_gate": (CW, "floor", 9000),
    "cordon_river_gate": (CW, "floor", 5000),
    "cordon_river_abutment": (CW, "floor", 2500),
    "cordon_notice_board": (CW, "wall", 2000),
}


def tasks() -> list[Task]:
    out = []
    suffix = {"clean": "", "worn": "_worn"}
    gen = pathlib.Path(__file__).resolve().parent.parent / "blender" / "generators"
    src = blender_sources("props_cordon_wall") + [gen / "props_waystation.py"]
    for pid, (variants, mount, budget) in PROPS.items():
        seed = zlib.crc32(pid.encode()) % 100000
        outputs = [f"models/props/{pid}{suffix[v]}.glb" for v in variants]
        params = {"prop": pid, "seed": seed, "variants": variants, "mount": mount, "budget": budget}
        out.append(Task(name=f"model:props/cordon_wall/{pid}", group="models", outputs=outputs, sources=src, params=params,
                        blender="props_cordon_wall"))
    return out
