"""Contract item models (ADR-0039): models/items/contracts/<id>.glb from blender/generators/item_contracts.py.
game/data/items/contracts.json points each item's "model" here. The cache's Program mark and asset plate come
from the waystation_print atlas (material ws_print)."""
from __future__ import annotations

from ..core.registry import Task, blender_sources

ITEMS: dict[str, tuple[str, dict]] = {
    "program_cache": ("item_contracts", {"kind": "program_cache", "seed": 9951}),
}


def tasks() -> list[Task]:
    out = []
    for item_id, (gen, p) in ITEMS.items():
        params = {"name": item_id, **p}
        out.append(Task(name=f"model:items/contracts/{item_id}", group="models", outputs=[f"models/items/contracts/{item_id}.glb"],
                        sources=blender_sources(gen), params=params, blender=gen))
    return out
