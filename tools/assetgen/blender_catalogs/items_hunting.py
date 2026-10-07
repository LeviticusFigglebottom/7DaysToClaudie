"""Arrows (ADR-0057): the ground pickup (models/items/hunting/<id>.glb, which the arrow items name as
their "model") and the projectile in flight, nocked or stuck (models/projectiles/<id>.glb, the
canonical frame of game/src/combat/arrow.gd: tip at the origin, shaft along +Z), from one
item_hunting build. The hunting bow itself is in items.py (an item with a viewmodel)."""
from __future__ import annotations

from ..core.registry import Task, blender_sources

ARROWS: dict[str, dict] = {
    "arrow_stone": {"kind": "arrow", "head": "stone", "seed": 283},
    "arrow_bone": {"kind": "arrow", "head": "bone", "seed": 284},
}


def tasks() -> list[Task]:
    out = []
    for item_id, p in ARROWS.items():
        params = {"name": item_id, **p}
        out.append(Task(name=f"model:items/hunting/{item_id}", group="models",
                        outputs=[f"models/items/hunting/{item_id}.glb", f"models/projectiles/{item_id}.glb"],
                        sources=blender_sources("item_hunting"), params=params, blender="item_hunting"))
    return out
