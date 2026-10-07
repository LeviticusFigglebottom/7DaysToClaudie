"""Forest set pieces, round 4 (ADR-0053): props of Shiloh Chapel (w4_overgrown_chapel), a pioneer timber chapel in a
forest clearing, its churchyard and the Teague vault dug into the bank behind it.

One task per prop id, one GLB per condition: models/props/<id>.glb (clean), <id>_worn.glb, <id>_destroyed.glb.
Task names are model:props/wild4_chapel/<id> so `--match wild4_chapel` selects the whole family. Generator:
blender/generators/props_wild4_chapel.py; content defs: game/data/props/wild4_chapel.json (shared materials only).

The vault shell wraps the vault porch's kit room and must match it: VAULT below is that room (w x d cells), the
style's floor height and its openings (side, index along the side, kind) exactly as w4_overgrown_chapel.json has
them (plan cols 11..12, rows 1..6; the chained iron door on S, the east cell).
"""
from __future__ import annotations

from ..core.registry import Task, blender_sources

C, W, D = "clean", "worn", "destroyed"
CW = [C, W]
CWD = [C, W, D]
GEN = "props_wild4_chapel"

VAULT = {"w": 2, "d": 6, "floor": 0.6, "openings": [["S", 1, "door"]]}

# id: (conditions, params). Headstone `cell`: the civic_engrave face (0, 4, 6 and 7 name no town).
PROPS: dict[str, tuple[list[str], dict]] = {
    "w4_chapel_pew": (CWD, {"seed": 4401, "ao_dist": 0.5}),
    "w4_chapel_pulpit": (CW, {"seed": 4402, "ao_dist": 0.6}),
    "w4_chapel_altar": (CW, {"seed": 4403, "ao_dist": 0.6}),
    "w4_chapel_bell_fallen": (CW, {"seed": 4404, "ao_dist": 0.7}),
    "w4_chapel_headstone": (CWD, {"seed": 4405, "cell": 4}),
    "w4_chapel_headstone_cross": (CWD, {"seed": 4406}),
    "w4_chapel_headstone_tablet": (CWD, {"seed": 4407, "cell": 6}),
    "w4_chapel_iron_railing": (CW, {"seed": 4408, "ao_dist": 0.3}),
    "w4_chapel_iron_railing_gate": (CW, {"seed": 4409, "ao_dist": 0.3}),
    "w4_chapel_mausoleum_front": (CW, {"seed": 4410, "ao_samples": 12, "ao_dist": 1.0, **VAULT}),
    "w4_chapel_coffin": (CW, {"seed": 4411, "ao_dist": 0.5}),
    "w4_chapel_crypt_niche": (CW, {"seed": 4412, "ao_dist": 0.7}),
    "w4_chapel_lych_gate": (CW, {"seed": 4413, "ao_samples": 14, "ao_dist": 1.0}),
    "w4_chapel_grave_dug": (CW, {"seed": 4414, "ao_dist": 0.6}),
    "w4_chapel_bloom_grave": (CW, {"seed": 4415, "ao_dist": 0.4}),
    "w4_chapel_ivy": (CW, {"seed": 4416, "ao_dist": 0.3, "ao_samples": 10}),
    "w4_chapel_long_grass": (CW, {"seed": 4417, "ao_dist": 0.3, "ao_samples": 8}),
    "w4_chapel_silver_chest": (CW, {"seed": 4418, "ao_dist": 0.5}),
    "w4_chapel_reliquary": (CW, {"seed": 4419, "ao_dist": 0.4}),
    "w4_chapel_stone_wall": (CW, {"seed": 4420, "ao_dist": 0.5}),
}


def outputs_for(pid: str, conds: list[str]) -> list[str]:
    return [f"models/props/{pid}{'' if c == C else '_' + c}.glb" for c in conds]


def tasks() -> list[Task]:
    out = []
    srcs = blender_sources(GEN)
    for pid, (conds, params) in PROPS.items():
        p = {"prop": pid, "conditions": list(conds), **params}
        out.append(Task(name=f"model:props/wild4_chapel/{pid}", group="models", outputs=outputs_for(pid, conds), sources=srcs,
                        params=p, blender=GEN))
    return out
