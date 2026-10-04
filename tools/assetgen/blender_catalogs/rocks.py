"""Rock assets: granite boulders (6 variants) and loose-stone pebble clusters (2)."""
from __future__ import annotations

from ..core.registry import Task, blender_sources

BOULDERS = {
    "a": {"size": [1.8, 1.4, 1.2], "chips": 4, "seed": 101},
    "b": {"size": [2.6, 2.0, 1.5], "chips": 5, "seed": 202},
    "c": {"size": [1.2, 1.1, 0.9], "chips": 3, "seed": 303},
    "d": {"size": [3.6, 2.4, 2.2], "chips": 6, "seed": 404, "tris": 1800},
    "e": {"size": [1.6, 0.9, 0.7], "chips": 3, "seed": 505},
    "f": {"size": [2.2, 2.0, 2.6], "chips": 5, "seed": 606, "tris": 1800},
}


def tasks() -> list[Task]:
    out = []
    for key, p in BOULDERS.items():
        params = {"kind": "boulder", "name": f"boulder_{key}", "detail": 5, "flatten": 0.16, "moss": 0.7, **p}
        out.append(Task(name=f"model:rocks/boulder_{key}", group="models", outputs=[f"models/rocks/boulder_{key}.glb"],
                        sources=blender_sources("rock"), params=params, blender="rock"))
    for key, seed in (("a", 11), ("b", 22)):
        params = {"kind": "pebbles", "name": f"pebble_cluster_{key}", "seed": seed, "count": 5 + seed % 3, "moss": 0.2}
        out.append(Task(name=f"model:rocks/pebble_cluster_{key}", group="models", outputs=[f"models/rocks/pebble_cluster_{key}.glb"],
                        sources=blender_sources("rock"), params=params, blender="rock"))
    return out
