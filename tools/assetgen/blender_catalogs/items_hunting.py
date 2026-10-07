"""The hunting bow and its arrows (ADR-0057), models/hunting/: the ground pickup (<id>.glb, which the
items name as their "model") and the first-person / projectile model in the canonical frame
(<id>_fp.glb: the bow as BowRig holds it, an arrow as game/src/combat/arrow.gd flies, nocks and
sticks it), from one item_hunting build each."""
from __future__ import annotations

from ..core.registry import Task, blender_sources

MODELS: dict[str, dict] = {
    "hunting_bow": {"kind": "hunting_bow", "seed": 281},
    "arrow_stone": {"kind": "arrow", "head": "stone", "seed": 283},
    "arrow_bone": {"kind": "arrow", "head": "bone", "seed": 284},
}


def tasks() -> list[Task]:
    out = []
    for item_id, p in MODELS.items():
        params = {"name": item_id, **p}
        out.append(Task(name=f"model:hunting/{item_id}", group="models",
                        outputs=[f"models/hunting/{item_id}.glb", f"models/hunting/{item_id}_fp.glb"],
                        sources=blender_sources("item_hunting"), params=params, blender="item_hunting"))
    return out
