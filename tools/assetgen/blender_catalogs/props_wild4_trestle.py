"""Forest set pieces, round 4 (ADR-0053): props of the trestle tunnel (w4_trestle_tunnel).

One task per prop id, one GLB per condition: models/props/<id>.glb (clean), <id>_worn.glb, <id>_destroyed.glb.
Task names are model:props/wild4_trestle/<id> so `--match wild4_trestle` selects the family. Generator:
blender/generators/props_wild4_trestle.py; content defs: game/data/props/wild4_trestle.json (shared materials only).
"""
from __future__ import annotations

from ..core.registry import Task, blender_sources

C, W, D = "clean", "worn", "destroyed"
CW = [C, W]
CWD = [C, W, D]
GEN = "props_wild4_trestle"

# id: (conditions, params)
PROPS: dict[str, tuple[list[str], dict]] = {
    "w4_trestle_bent": (CW, {"seed": 4101, "ao_dist": 0.9}),
    "w4_trestle_deck_section": (CW, {"seed": 4102, "ao_dist": 0.6}),
    "w4_trestle_rail_section": (CW, {"seed": 4103, "ao_dist": 0.4}),
    "w4_trestle_crib": (CW, {"seed": 4104, "ao_dist": 0.8}),
    "w4_trestle_hill": ([C], {"seed": 4105, "ao_samples": 8, "ao_dist": 2.0}),
    "w4_trestle_tunnel_portal": (CW, {"seed": 4106, "ao_samples": 12, "ao_dist": 1.2}),
    "w4_trestle_rubble_wall": (CW, {"seed": 4107, "ao_samples": 10, "ao_dist": 1.0}),
    "w4_trestle_boxcar": (CW, {"seed": 4108, "ao_samples": 12, "ao_dist": 1.0}),
    "w4_trestle_lumber_stack": (CW, {"seed": 4109, "ao_dist": 0.6}),
    "w4_trestle_flatcar_derailed": (CW, {"seed": 4110, "ao_samples": 12, "ao_dist": 0.9}),
    "w4_trestle_handcar": (CWD, {"seed": 4111, "ao_dist": 0.5}),
    "w4_trestle_key_board": (CW, {"seed": 4112, "ao_dist": 0.2}),
    "w4_trestle_spike_keg": (CW, {"seed": 4113, "ao_dist": 0.3}),
    "w4_trestle_tie_pile": (CW, {"seed": 4114, "ao_dist": 0.5}),
}


def outputs_for(pid: str, conds: list[str]) -> list[str]:
    return [f"models/props/{pid}{'' if c == C else '_' + c}.glb" for c in conds]


def tasks() -> list[Task]:
    out = []
    srcs = blender_sources(GEN)
    for pid, (conds, params) in PROPS.items():
        p = {"prop": pid, "conditions": list(conds), **params}
        out.append(Task(name=f"model:props/wild4_trestle/{pid}", group="models", outputs=outputs_for(pid, conds),
                        sources=srcs, params=p, blender=GEN))
    return out
