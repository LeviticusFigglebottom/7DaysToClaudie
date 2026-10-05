"""The Bloom's growths (ADR-0025): fruiting-body clusters (species bloom_caps, the scatter's bloom
layer) and the fungal mounds Hum survivors leave where they rooted (BloomMounds).

Model ids match game/data/vegetation/bloom.json and BloomMounds.MODELS. Every model ships a cheaper
_lod1 (ground cover past ~40 m blocks, mounds past 25 m).
"""
from __future__ import annotations

import math

from ..core.registry import Task, blender_sources


def _arc(n: int, radius: float, a0: float, a1: float, seed: int) -> list[list[float]]:
    """Small young caps along an arc (a buried root under the litter): deterministic jitter."""
    out = []
    for i in range(n):
        t = i / max(1, n - 1)
        a = a0 + (a1 - a0) * t
        j = ((seed * 7919 + i * 104729) % 1000) / 1000.0
        k = ((seed * 6271 + i * 7907) % 1000) / 1000.0
        out.append([round(math.cos(a) * radius - radius + (j - 0.5) * 0.03, 4), round(math.sin(a) * radius + (k - 0.5) * 0.03, 4),
                    round(0.008 + 0.009 * k, 4), round(0.3 * j, 3), round(0.12 + 0.3 * k, 3), round(a + math.pi * 0.5 * (j - 0.5), 3)])
    return out


# [x, y, cap radius, form (0 bell .. 1 old upturned), lean (rad), lean heading (rad)]; `size` scales
# a whole cluster (honey-fungus scale: caps 3-13 cm across, so a cluster reads from 10-15 m).
CAPS: dict[str, dict] = {
    # A tight cluster fused at the base, every age at once.
    "bloom_caps_a": {"seed": 25101, "size": 1.6, "mushrooms": [
        [0.0, 0.0, 0.032, 0.55, 0.08, 0.0], [0.03, 0.015, 0.026, 0.35, 0.25, 0.5], [-0.025, 0.02, 0.028, 0.72, 0.3, 2.6],
        [0.01, -0.03, 0.02, 0.15, 0.35, 4.8], [-0.03, -0.02, 0.016, 0.05, 0.45, 3.9], [0.04, -0.015, 0.012, 0.0, 0.5, 5.8],
        [-0.008, 0.035, 0.009, 0.0, 0.4, 1.6]],
        "broken": [{"kind": "cap", "at": [0.11, 0.05], "r": 0.027, "form": 0.6}]},
    # An older troop gone flat and upturned: one toppled, one torn half away.
    "bloom_caps_b": {"seed": 25202, "size": 1.6, "mushrooms": [
        [0.0, 0.0, 0.04, 0.85, 0.06, 0.0], [0.12, 0.06, 0.034, 0.95, 0.12, 0.7], [-0.09, 0.08, 0.03, 0.75, 0.2, 2.4],
        [0.05, -0.1, 0.022, 0.5, 0.18, 5.0]],
        "broken": [{"kind": "toppled", "at": [-0.08, -0.07], "r": 0.033, "form": 0.8, "ang": 3.6},
                   {"kind": "torn", "at": [0.15, -0.05], "r": 0.035, "form": 0.9, "arc": 200.0, "lean": 0.2, "ang": 5.6}]},
    # Young bells along a buried root.
    "bloom_caps_c": {"seed": 25303, "size": 1.4, "mushrooms": _arc(9, 0.28, -0.7, 0.9, 25303),
                     "broken": [{"kind": "cap", "at": [-0.12, 0.2], "r": 0.016, "form": 0.3}]},
    # Fruiting from a cushion of felted mycelium.
    "bloom_caps_d": {"seed": 25404, "size": 1.6, "felt": 0.17, "felt_h": 0.032, "mushrooms": [
        [0.02, 0.01, 0.024, 0.4, 0.15, 0.3], [-0.05, 0.04, 0.02, 0.2, 0.3, 2.3], [0.06, -0.04, 0.017, 0.1, 0.35, 5.4],
        [-0.02, -0.06, 0.012, 0.0, 0.3, 4.2], [0.0, 0.08, 0.009, 0.0, 0.45, 1.4]],
        "broken": [{"kind": "cap", "at": [0.21, 0.08], "r": 0.022, "form": 0.55}]},
}

MOUNDS: dict[str, dict] = {
    "bloom_mound_a": {"seed": 25501, "length": 1.75, "width": 0.72, "height": 0.4, "caps": 7},
    "bloom_mound_b": {"seed": 25602, "length": 1.6, "width": 0.8, "height": 0.34, "caps": 8},
}


def tasks() -> list[Task]:
    out = []
    for cid, p in CAPS.items():
        out.append(Task(name=f"model:plants/{cid}", group="models",
                        outputs=[f"models/plants/{cid}.glb", f"models/plants/{cid}_lod1.glb"],
                        sources=blender_sources("veg_fungus"),
                        params={"name": cid, "kind": "caps", "mat": "bloom_caps", "felt_mat": "bloom_felt",
                                "ao_dist": 0.12 * p.get("size", 1.0), **p},
                        blender="veg_fungus"))
    for mid, p in MOUNDS.items():
        out.append(Task(name=f"model:plants/{mid}", group="models",
                        outputs=[f"models/plants/{mid}.glb", f"models/plants/{mid}_lod1.glb"],
                        sources=blender_sources("veg_fungus"),
                        params={"name": mid, "kind": "mound", "mat": "bloom_caps", "felt_mat": "bloom_felt", "ao_dist": 0.35, **p},
                        blender="veg_fungus"))
    return out
