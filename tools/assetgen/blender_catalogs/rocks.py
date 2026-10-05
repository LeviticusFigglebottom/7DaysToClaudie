"""Rock assets: weathered granite boulders (6), loose-stone pebble clusters (2) and slabby cliff-band
masses (3). Generator: blender/generators/rock.py (smoothed convex polytopes, see its docstring)."""
from __future__ import annotations

from ..core.registry import Task, blender_sources

# size = full extents [x, y, z] in metres before embedding; round = edge radius fraction;
# cuts = extra fracture planes; embed = fraction of the height below ground.
BOULDERS = {
    "a": {"size": [1.9, 1.5, 1.3], "cuts": 9, "round": 0.16, "embed": 0.2, "seed": 101},
    "b": {"size": [2.8, 2.1, 1.7], "cuts": 10, "round": 0.12, "embed": 0.22, "seed": 202},
    "c": {"size": [1.3, 1.1, 1.0], "cuts": 8, "round": 0.2, "embed": 0.18, "seed": 303},
    "d": {"size": [3.8, 2.7, 2.4], "cuts": 11, "round": 0.1, "embed": 0.2, "seed": 404, "tris": 3000, "grooves": 2},
    "e": {"size": [1.8, 1.1, 0.8], "cuts": 8, "round": 0.18, "embed": 0.25, "seed": 505},
    "f": {"size": [2.3, 2.0, 2.9], "cuts": 10, "round": 0.11, "embed": 0.15, "seed": 606, "tris": 3000, "grooves": 2},
}

CLIFFS = {
    "a": {"size": [10.0, 4.5, 8.0], "joints": 2, "talus": 2, "seed": 701},
    "b": {"size": [7.0, 4.0, 6.0], "joints": 1, "talus": 1, "seed": 802},
    "c": {"size": [12.0, 5.0, 10.5], "joints": 3, "talus": 3, "seed": 903},
}


def tasks() -> list[Task]:
    out = []
    for key, p in BOULDERS.items():
        params = {"kind": "boulder", "name": f"boulder_{key}", "moss": 0.75, "tris": 2400, **p}
        out.append(Task(name=f"model:rocks/boulder_{key}", group="models",
                        outputs=[f"models/rocks/boulder_{key}.glb", f"models/rocks/boulder_{key}_lod1.glb"],
                        sources=blender_sources("rock"), params=params, blender="rock"))
    for key, seed in (("a", 11), ("b", 22)):
        params = {"kind": "pebbles", "name": f"pebble_cluster_{key}", "seed": seed, "count": 5 + seed % 3, "moss": 0.25,
                  "tris": 420}
        out.append(Task(name=f"model:rocks/pebble_cluster_{key}", group="models",
                        outputs=[f"models/rocks/pebble_cluster_{key}.glb"], sources=blender_sources("rock"),
                        params=params, blender="rock"))
    for key, p in CLIFFS.items():
        params = {"kind": "cliff", "name": f"cliff_rock_{key}", "moss": 0.85, "tris": 2450, "embed": 0.06, **p}
        out.append(Task(name=f"model:rocks/cliff_rock_{key}", group="models", outputs=[f"models/rocks/cliff_rock_{key}.glb"],
                        sources=blender_sources("rock"), params=params, blender="rock"))
    return out
