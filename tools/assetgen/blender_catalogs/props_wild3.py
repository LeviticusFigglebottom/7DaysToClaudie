"""Wilderness set pieces, round 3 (agent X): Camp Tamarack, Elk Ridge Lodge, the Cordon quarantine camp and
the Haldane Place, the four dungeons random worlds place outside towns (game/data/config/world_gen.json
tuning.wilderness.pool).

One task per prop id, one GLB per condition: models/props/<id>.glb (clean), <id>_worn.glb, <id>_destroyed.glb.
Task names are model:props/wild3/<id> so `--match wild3` selects the whole family. Generator:
blender/generators/props_wild3.py (it reuses lib/props_outskirts_parts.py and props_wild_parts.py); content
defs: game/data/props/wild3.json; materials: game/data/materials/props_wild3.json; the lettering atlas
w3_signs: textures/gen/wild3.py.

The three shells wrap kit rooms of their POIs and must match them: SHELLS below lists each one's room
(w x d cells), floor height and openings (side, index along the side, kind[, level]) exactly as the POI
JSON has them (elk_ridge_lodge.json, cordon_quarantine_camp.json); test_wilderness_round_three.gd checks it.
"""
from __future__ import annotations

from ..core.registry import Task, blender_sources

C, W, D = "clean", "worn", "destroyed"
CW = [C, W]
CWD = [C, W, D]
GEN = "props_wild3"

# The lodge: one 16 x 10 rectangle two storeys high (plan cols 4..19, rows 4..13 of elk_ridge_lodge).
LODGE_OPENINGS = [
    ["S", 3, "door2", 0], ["S", 1, "window_tall", 0], ["S", 6, "window_tall", 0],
    ["W", 1, "window_tall", 0], ["W", 8, "window_tall", 0], ["N", 2, "window_tall", 0], ["N", 6, "window_tall", 0],
    ["N", 12, "door", 0], ["N", 10, "window", 0], ["N", 14, "window", 0], ["E", 2, "window", 0], ["E", 5, "door", 0],
    ["S", 14, "door", 0], ["S", 13, "window", 0], ["S", 9, "window", 0],
    ["N", 10, "window", 1], ["N", 14, "window", 1], ["E", 2, "window", 1], ["E", 6, "window", 1], ["E", 9, "window", 1],
    ["S", 14, "window", 1], ["S", 10, "window", 1], ["S", 8, "window", 1],
]
SHELLS: dict[str, dict] = {
    "w3_lodge_shell": {"w": 16, "d": 10, "floor": 0.45, "storeys": 2, "openings": LODGE_OPENINGS},
    # The morgue reefer (cordon_quarantine_camp plan cols 34..36, rows 4..11): rear door S, side door E.
    "w3_reefer_shell": {"w": 3, "d": 8, "floor": 0.35, "openings": [["S", 1, "door"], ["E", 5, "door"]]},
    # The command trailer (plan cols 5..8, rows 8..16): door E into the radio room, windows round it.
    "w3_command_trailer_shell": {"w": 4, "d": 9, "floor": 0.35, "openings": [
        ["E", 6, "door"], ["E", 2, "window"], ["W", 2, "window"], ["W", 6, "window"], ["N", 1, "window"]]},
}

# id: (conditions, params)
PROPS: dict[str, tuple[list[str], dict]] = {
    # --- Camp Tamarack ----------------------------------------------------------------------------------
    "w3_camp_arch": (CW, {"seed": 3101, "ao_dist": 0.9}),
    "w3_canoe_rack": (CWD, {"seed": 3102, "ao_dist": 0.8}),
    "w3_camp_bunk": (CWD, {"seed": 3103, "ao_dist": 0.6}),
    "w3_sign_loon": (CW, {"seed": 3111, "cell": "sign_loon"}),
    "w3_sign_heron": (CW, {"seed": 3112, "cell": "sign_heron"}),
    "w3_sign_osprey": (CW, {"seed": 3113, "cell": "sign_osprey"}),
    "w3_sign_kestrel": (CW, {"seed": 3114, "cell": "sign_kestrel"}),
    "w3_sign_mess": (CW, {"seed": 3115, "cell": "sign_mess"}),
    "w3_sign_lodge": (CW, {"seed": 3116, "cell": "sign_lodge"}),
    "w3_sign_infirmary": (CW, {"seed": 3117, "cell": "sign_infirmary"}),
    "w3_sign_canoes": (CW, {"seed": 3118, "cell": "sign_canoes"}),
    "w3_evac_board": (CW, {"seed": 3104, "ao_dist": 0.7}),
    "w3_log_bench": (CW, {"seed": 3105}),
    "w3_chapel_cross": (CW, {"seed": 3106, "ao_dist": 0.8}),
    # --- Elk Ridge Lodge ----------------------------------------------------------------------------------
    "w3_lodge_shell": ([C], {"seed": 3201, "ao_samples": 10, "ao_dist": 1.0, **SHELLS["w3_lodge_shell"]}),
    "w3_stone_fireplace": (CW, {"seed": 3202, "ao_dist": 0.9}),
    "w3_stone_chimney": ([C], {"seed": 3203, "ao_dist": 1.0, "height": 11.2}),
    "w3_antler_chandelier": (CW, {"seed": 3204, "ao_dist": 0.5, "drop": 2.4}),
    "w3_lodge_sign": (CW, {"seed": 3212, "cell": "elk_ridge", "w": 2.0, "h": 0.5, "posts": 2, "top": 2.2, "antlers": True}),
    "w3_kennel_sign": (CW, {"seed": 3213, "cell": "kennel_names", "w": 1.2, "h": 0.3, "posts": 1, "top": 1.45}),
    "w3_trophy_elk": (CW, {"seed": 3205, "ao_dist": 0.5}),
    "w3_trophy_deer": (CW, {"seed": 3206, "ao_dist": 0.4}),
    "w3_bear_rug": (CW, {"seed": 3207}),
    "w3_gun_cabinet": (CWD, {"seed": 3208, "ao_dist": 0.5}),
    "w3_gambrel": (CW, {"seed": 3209, "ao_dist": 0.8}),
    "w3_kennel_run": (CWD, {"seed": 3210, "ao_dist": 0.8}),
    "w3_meat_rail": (CW, {"seed": 3211, "ao_dist": 0.7}),
    # --- The Cordon quarantine camp -------------------------------------------------------------------
    "w3_ward_tent": (CWD, {"seed": 3301, "ao_samples": 12, "ao_dist": 1.2}),
    "w3_ward_cot": (CWD, {"seed": 3302}),
    "w3_decon_shower": (CW, {"seed": 3303, "ao_dist": 0.8}),
    "w3_light_tower": (CW, {"seed": 3304, "ao_dist": 0.8}),
    "w3_cordon_fence": (CWD, {"seed": 3305}),
    "w3_cordon_gate": (CW, {"seed": 3306}),
    "w3_sandbags": (CW, {"seed": 3307}),
    "w3_watchtower": (CW, {"seed": 3308, "ao_dist": 1.0}),
    "w3_reefer_shell": (CW, {"seed": 3309, "ao_samples": 12, "ao_dist": 1.0, **SHELLS["w3_reefer_shell"]}),
    "w3_command_trailer_shell": (CW, {"seed": 3310, "ao_samples": 12, "ao_dist": 1.0, **SHELLS["w3_command_trailer_shell"]}),
    "w3_body_bag": (CW, {"seed": 3311}),
    "w3_morgue_rack": (CW, {"seed": 3312}),
    "w3_ward_a": (CW, {"seed": 3321, "quad": 0}),
    "w3_ward_b": (CW, {"seed": 3322, "quad": 1}),
    "w3_ward_c": (CW, {"seed": 3323, "quad": 2}),
    "w3_ward_d": (CW, {"seed": 3324, "quad": 3}),
    # --- The Haldane Place ------------------------------------------------------------------------------
    "w3_scrap_palisade": (CWD, {"seed": 3401}),
    "w3_scrap_gate": (CW, {"seed": 3402}),
    "w3_watch_platform": (CW, {"seed": 3403, "ao_dist": 0.9}),
    "w3_raised_bed": (CWD, {"seed": 3404}),
    "w3_rain_catcher": (CW, {"seed": 3405}),
    "w3_stake_row": (CW, {"seed": 3406}),
    # --- Ezra Vane's camp (ADR-0058) ------------------------------------------------------------------
    "w3_fallen_line_pole": (CW, {"seed": 3501, "ao_dist": 0.8}),
    "w3_tarp_lean": (CW, {"seed": 3502, "ao_dist": 0.8}),
}


def outputs_for(pid: str, conds: list[str]) -> list[str]:
    return [f"models/props/{pid}{'' if c == C else '_' + c}.glb" for c in conds]


def tasks() -> list[Task]:
    out = []
    srcs = blender_sources(GEN)
    for pid, (conds, params) in PROPS.items():
        p = {"prop": pid, "conditions": list(conds), **params}
        out.append(Task(name=f"model:props/wild3/{pid}", group="models", outputs=outputs_for(pid, conds), sources=srcs,
                        params=p, blender=GEN))
    return out
