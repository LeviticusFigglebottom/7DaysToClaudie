"""The Corvane Field Lab (agent Y): the props of the game's first tier-5 dungeon, the geology field station the
Cordon took for its forward Bloom lab (game/data/pois/buildings/corvane_field_lab.json; random worlds place it from
data/config/world_gen.json tuning.wilderness.pool).

One task per prop id, one GLB per condition: models/props/<id>.glb (clean), <id>_worn.glb, <id>_destroyed.glb.
Task names are model:props/lab/<id> so `--match props/lab` selects the whole family. Generator:
blender/generators/props_lab.py (it reuses lib/props_outskirts_parts.py and props_wild_parts.py); content defs:
game/data/props/lab.json; materials: game/data/materials/props_lab.json; the lettering atlas lab_signs:
textures/gen/lab.py.

The shells wrap kit rooms of the POI and must match them: SHELLS lists each one's room (w x d cells), floor height
and outside openings (side, index along the side, kind) in the shell's own frame, exactly as the POI JSON has them
(the four modules use one shell, the two east of the boardwalk turned 180 degrees);
game/tests/unit/test_field_lab.gd checks it.
"""
from __future__ import annotations

from ..core.registry import Task, blender_sources

C, W, D = "clean", "worn", "destroyed"
CW = [C, W]
CWD = [C, W, D]
GEN = "props_lab"

SHELLS: dict[str, dict] = {
    # The lab modules (corvane_field_lab plan cols 17..25 / 28..36, rows 23..26 and 31..34): the door onto the
    # boardwalk on the east side, two windows on each long side, one at the far end.
    "lab_module_shell": {"w": 9, "d": 4, "floor": 0.35, "openings": [
        ["E", 1, "door"], ["N", 2, "window"], ["N", 6, "window"], ["S", 2, "window"], ["S", 6, "window"], ["W", 1, "window"]]},
    # The decontamination unit (cols 26..31, rows 17..20): its outer door off the boardwalk, a window in the PPE
    # room and one in the airlock; its north side stands against the containment block (no wall).
    "lab_decon_shell": {"w": 6, "d": 4, "floor": 0.35, "skip": ["N"], "openings": [
        ["S", 0, "door"], ["W", 1, "window"], ["E", 2, "window"]]},
}

SIGNS: dict[str, tuple[str, float, float]] = {
    "lab_sign_biohazard": ("biohazard", 0.6, 0.45),
    "lab_sign_airlock": ("airlock", 0.9, 0.3),
    "lab_sign_decon": ("decon", 1.2, 0.4),
    "lab_sign_vault": ("vault", 0.8, 0.3),
    "lab_sign_emergency": ("emergency", 0.6, 0.25),
    "lab_sign_containment": ("containment", 0.7, 0.5),
    "lab_sign_core_shed": ("core_shed", 1.4, 0.35),
    "lab_sign_module_prep": ("mod_prep", 0.7, 0.25),
    "lab_sign_module_micro": ("mod_micro", 0.7, 0.25),
    "lab_sign_module_cold": ("mod_cold", 0.7, 0.25),
    "lab_sign_module_admin": ("mod_admin", 0.7, 0.25),
}

# id: (conditions, params)
PROPS: dict[str, tuple[list[str], dict]] = {
    # --- structures ------------------------------------------------------------------------------------
    "lab_module_shell": (CW, {"seed": 4101, "ao_samples": 12, "ao_dist": 1.0, **SHELLS["lab_module_shell"]}),
    "lab_decon_shell": (CW, {"seed": 4102, "ao_samples": 12, "ao_dist": 1.0, **SHELLS["lab_decon_shell"]}),
    "lab_boardwalk_roof": (CW, {"seed": 4103, "ao_dist": 0.8}),
    "lab_berm": ([C], {"seed": 4104, "ao_samples": 12, "ao_dist": 1.2}),
    "lab_fence": (CWD, {"seed": 4105}),
    "lab_fence_cut": ([C], {"seed": 4106}),
    "lab_gate": (CW, {"seed": 4107}),
    "lab_sign_station": (CW, {"seed": 4108}),
    "lab_sign_fence": (CW, {"seed": 4109}),
    "lab_fuel_tank": (CW, {"seed": 4110, "ao_dist": 0.9}),
    "lab_generator": (CW, {"seed": 4111, "ao_dist": 0.8}),
    "lab_drill_rig": (CW, {"seed": 4112, "ao_samples": 12, "ao_dist": 1.0}),
    # --- core shed ---------------------------------------------------------------------------------------
    "lab_core_rack": (CWD, {"seed": 4201, "ao_samples": 12, "ao_dist": 0.7}),
    "lab_core_boxes": (CW, {"seed": 4202, "ao_dist": 0.5}),
    "lab_core_saw": (CW, {"seed": 4203, "ao_dist": 0.5}),
    "lab_logging_bench": (CW, {"seed": 4204, "ao_dist": 0.5}),
    # --- labs ----------------------------------------------------------------------------------------------
    "lab_bench": (CWD, {"seed": 4301, "ao_dist": 0.5}),
    "lab_fume_hood": (CW, {"seed": 4302, "ao_dist": 0.6}),
    "lab_biosafety_cabinet": (CW, {"seed": 4303, "ao_dist": 0.6}),
    "lab_freezer_80": (CW, {"seed": 4304, "ao_dist": 0.5}),
    "lab_centrifuge": (CW, {"seed": 4305, "ao_dist": 0.4}),
    "lab_microscope": (CW, {"seed": 4306, "ao_dist": 0.15}),
    "lab_sample_rack": (CW, {"seed": 4307, "ao_dist": 0.4}),
    "lab_dewar": (CW, {"seed": 4308, "ao_dist": 0.4}),
    "lab_sample_vault": (CW, {"seed": 4309, "ao_samples": 12, "ao_dist": 0.5}),
    "lab_vault_frame": (CW, {"seed": 4310, "ao_dist": 0.6}),
    "lab_card_reader": ([C], {"seed": 4311, "ao_dist": 0.1}),
    "lab_decon_shower": (CW, {"seed": 4312, "ao_dist": 0.7}),
    "lab_ppe_rack": (CW, {"seed": 4313, "ao_dist": 0.5}),
    "lab_biohazard_bin": (CW, {"seed": 4314, "ao_dist": 0.3}),
    "lab_radio_desk": (CW, {"seed": 4315, "ao_dist": 0.4}),
    "lab_server_rack": (CW, {"seed": 4316, "ao_dist": 0.5}),
    "lab_ceiling_light": (CW, {"seed": 4317, "ao_dist": 0.1}),
    "lab_emergency_light": ([C], {"seed": 4318, "ao_dist": 0.1}),
}
for _k, (_pid, (_cell, _w, _h)) in enumerate(SIGNS.items()):
    PROPS[_pid] = (CW, {"seed": 4400 + _k, "cell": _cell, "w": _w, "h": _h, "ao_dist": 0.1})


def outputs_for(pid: str, conds: list[str]) -> list[str]:
    return [f"models/props/{pid}{'' if c == C else '_' + c}.glb" for c in conds]


def tasks() -> list[Task]:
    out = []
    srcs = blender_sources(GEN)
    for pid, (conds, params) in PROPS.items():
        p = {"prop": pid, "conditions": list(conds), **params}
        out.append(Task(name=f"model:props/lab/{pid}", group="models", outputs=outputs_for(pid, conds), sources=srcs,
                        params=p, blender=GEN))
    return out
