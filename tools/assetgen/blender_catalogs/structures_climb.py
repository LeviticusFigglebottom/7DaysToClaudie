"""Climbable structures (ADR-0057): models/structures/<id>.glb for the hunting stand, the climbing rope's
anchor, its 1 m knotted span (repeated down the drop by ClimbMount) and the coiled rope item.
Generator: blender/generators/structure_climb.py; layout shared with data/config/climbing.json."""
from __future__ import annotations

from ..core.registry import Task, blender_sources

MODULE = "structure_climb"

SPEC: dict[str, dict] = {
    "hunting_stand": {"kind": "hunting_stand", "seed": 4701},
    "climbing_rope": {"kind": "climbing_rope", "seed": 4702},
    "climbing_rope_span": {"kind": "climbing_rope_span", "seed": 4703},
    "climbing_rope_coil": {"kind": "climbing_rope_coil", "seed": 4704},
}


def _sources() -> list:
    out = blender_sources(MODULE)
    for f in blender_sources("structure_logs"):
        if f not in out:
            out.append(f)
    return out


def tasks() -> list[Task]:
    return [Task(name=f"model:structures/{sid}", group="models", outputs=[f"models/structures/{sid}.glb"],
                 sources=_sources(), params={"name": sid, **p}, blender=MODULE) for sid, p in SPEC.items()]
