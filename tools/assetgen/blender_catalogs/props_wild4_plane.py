"""Forest set pieces, round 4: the Cordon transport wreck (w4_cordon_plane_wreck).

One task per prop id, one GLB per condition: models/props/<id>.glb (clean), <id>_worn.glb. Task names are
model:props/wild4_plane/<id> so `--match wild4_plane` selects the whole family. Generator:
blender/generators/props_wild4_plane.py; content defs: game/data/props/wild4_plane.json; materials:
game/data/materials/props_wild4_plane.json.

The two fuselage shells wrap kit rooms of the POI and must match them: SHELLS below lists each one's rooms
(w x d cells, the shell's local frame), floor height and outside openings (side, index along the side, kind,
level) exactly as w4_cordon_plane_wreck.json has them; game/tests/unit/test_w4_plane.gd checks it (in plan terms).
The tail lies crosswise: it is built along local y and turned +90 degrees, so its local S end is the plan's
east (the torn end), local N the plan's west (the sample bay) and local W the plan's south side.
"""
from __future__ import annotations

from ..core.registry import Task, blender_sources

C, W = "clean", "worn"
CW = [C, W]
GEN = "props_wild4_plane"

SHELLS: dict[str, dict] = {
    # Plan cols 15..18, rows 4..17: crew bay (rows 4..7) with the flight deck over it (level 1), cargo hold
    # (rows 8..17) open over the ramp lip at its south end, the emergency exit on its west side at row 14.
    "w4_plane_fuselage_fwd": {"w": 4, "d": 14, "floor": 0.08, "deck_rows": 4, "openings": [
        ["S", 0, "half", 0], ["S", 1, "half", 0], ["S", 2, "half", 0], ["S", 3, "half", 0], ["W", 10, "door", 0],
        ["N", 1, "window", 1], ["N", 2, "window", 1]]},
    # Plan cols 6..12, rows 30..32 (local 3 x 7): the side door on the plan's south side at col 10.
    "w4_plane_fuselage_tail": {"w": 3, "d": 7, "floor": 0.08, "turn": 90.0, "openings": [["W", 4, "door", 0]]},
}

PROPS: dict[str, tuple[list[str], dict]] = {
    "w4_plane_fuselage_fwd": ([C], {"seed": 4101, "ao_samples": 10, "ao_dist": 1.0, **SHELLS["w4_plane_fuselage_fwd"]}),
    "w4_plane_fuselage_tail": ([C], {"seed": 4102, "ao_samples": 10, "ao_dist": 1.0, **SHELLS["w4_plane_fuselage_tail"]}),
    "w4_plane_nose": ([C], {"seed": 4103, "ao_samples": 12, "ao_dist": 1.0, "floor": 0.08}),
    "w4_plane_tail_cone": ([C], {"seed": 4104, "ao_samples": 12, "ao_dist": 1.0, "floor": 0.08}),
    "w4_plane_wing_section": (CW, {"seed": 4105, "ao_dist": 0.8}),
    "w4_plane_engine": (CW, {"seed": 4106, "ao_dist": 0.7}),
    "w4_plane_parachute": (CW, {"seed": 4107, "ao_dist": 0.8}),
    "w4_plane_cargo_pallet": (CW, {"seed": 4108, "ao_dist": 0.6}),
    "w4_plane_seat_row": (CW, {"seed": 4109}),
    "w4_plane_cockpit_console": (CW, {"seed": 4110}),
    "w4_plane_pilot_seat": (CW, {"seed": 4111}),
    "w4_plane_sample_case": (CW, {"seed": 4112}),
    "w4_plane_snapped_trunk": (CW, {"seed": 4113, "ao_dist": 0.6}),
}


def outputs_for(pid: str, conds: list[str]) -> list[str]:
    return [f"models/props/{pid}{'' if c == C else '_' + c}.glb" for c in conds]


def tasks() -> list[Task]:
    out = []
    srcs = blender_sources(GEN)
    for pid, (conds, params) in PROPS.items():
        p = {"prop": pid, "conditions": list(conds), **params}
        out.append(Task(name=f"model:props/wild4_plane/{pid}", group="models", outputs=outputs_for(pid, conds), sources=srcs,
                        params=p, blender=GEN))
    return out
