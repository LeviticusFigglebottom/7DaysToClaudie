"""Route-cue props (ADR-0022): the torn curtain RouteCues hangs in a POI's entry windows so the way
in reads from the street. Generator: blender/generators/props_cues.py; content defs (sizes for the
procedural fallback): game/data/props/traps.json; material: game/data/materials/props_cues.json.

One task per model id, two conditions (a newer and a sun-rotted curtain), outputs
models/props/<id>[_worn].glb.
"""
from __future__ import annotations

from ..core.registry import Task, blender_sources

MODULE = "props_cues"

PROPS: dict[str, dict] = {
    "cue_curtain": {"seed": 7301, "levels": {"clean": 0.4, "worn": 0.75}},
    "cue_curtain_wide": {"seed": 7302, "levels": {"clean": 0.4, "worn": 0.75}},
}


def tasks() -> list[Task]:
    out = []
    for pid, params in PROPS.items():
        conds = ["clean", "worn"]
        p = {"prop": pid, "conditions": conds, **params}
        outs = [f"models/props/{pid}.glb" if c == "clean" else f"models/props/{pid}_{c}.glb" for c in conds]
        out.append(Task(name=f"model:props/{pid}", group="models", outputs=outs,
                        sources=blender_sources(MODULE), params=p, blender=MODULE))
    return out
