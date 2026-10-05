"""Wilderness / industrial props family: the Tamsin logging camp, the Larch Hollow sawmill, the
Cedar Ridge fire lookout and the trapper's cabin (region D6, Larch Hollow).

One task per prop id; one GLB per condition: models/props/<id>.glb (clean), <id>_worn.glb,
<id>_destroyed.glb. Generators: blender/generators/props_wild.py (camp, cabin, lookout) and
props_wild_mill.py (sawmill and yard), shared parts in blender/lib/props_wild_parts.py.
Content defs: game/data/props/wild.json; materials: game/data/materials/props_wild.json;
textures: textures/gen/wild.py.
"""
from __future__ import annotations

from ..core.registry import Task, blender_sources

C, W, D = "clean", "worn", "destroyed"
CW = [C, W]
CWD = [C, W, D]
CAMP = "props_wild"
MILL = "props_wild_mill"

# id: (generator module, conditions, params)
PROPS: dict[str, tuple[str, list[str], dict]] = {
    # --- camp: bunkhouse, cookhouse, office, tool shed ------------------------------------------
    "wild_bunk_steel": (CAMP, CWD, {"seed": 701}),
    "wild_wood_stove": (CAMP, CWD, {"seed": 702}),
    "wild_cook_range": (CAMP, CWD, {"seed": 703}),
    "wild_mess_table": (CAMP, CWD, {"seed": 704}),
    "wild_mess_bench": (CAMP, CWD, {"seed": 705}),
    "wild_locker_steel": (CAMP, CWD, {"seed": 706}),
    "wild_footlocker": (CAMP, CWD, {"seed": 707}),
    "wild_tool_chest": (CAMP, CWD, {"seed": 708}),
    "wild_ammo_box": (CAMP, CWD, {"seed": 709}),
    "wild_safe_floor": (CAMP, CWD, {"seed": 710}),
    "wild_cot_canvas": (CAMP, CWD, {"seed": 711}),
    "wild_oil_lantern": (CAMP, CWD, {"seed": 712}),
    "wild_oil_lantern_hanging": (CAMP, CW, {"seed": 713}),
    "wild_washstand": (CAMP, CW, {"seed": 714}),
    "wild_enamel_dishes": (CAMP, CW, {"seed": 715}),
    "wild_firewood_stack": (CAMP, CW, {"seed": 716}),
    "wild_caulk_boots": (CAMP, CW, {"seed": 717}),
    # --- lookout ------------------------------------------------------------------------------
    "wild_fire_finder": (CAMP, CW, {"seed": 721}),
    "wild_radio_set": (CAMP, CWD, {"seed": 722}),
    "wild_lookout_tower": (CAMP, [C], {"seed": 723, "ao_samples": 12, "ao_dist": 2.0}),
    # --- trapper's cabin ------------------------------------------------------------------------
    "wild_gun_rack": (CAMP, CWD, {"seed": 731}),
    "wild_leg_trap": (CAMP, CW, {"seed": 732}),
    "wild_pelt_board": (CAMP, CW, {"seed": 733}),
    "wild_crosscut_saw": (CAMP, CW, {"seed": 734}),
    "wild_smoking_rack": (CAMP, CW, {"seed": 735}),
    "wild_chopping_block": (CAMP, CW, {"seed": 736}),
    "wild_canoe": (CAMP, CWD, {"seed": 737, "ao_dist": 0.8}),
    "wild_outhouse": (CAMP, CW, {"seed": 738, "ao_dist": 0.9}),
    "wild_smokehouse": (CAMP, CW, {"seed": 739, "ao_dist": 1.0}),
    "wild_lean_to": (CAMP, CW, {"seed": 740, "ao_dist": 1.0}),
    "wild_meat_cache": (CAMP, CW, {"seed": 741, "ao_dist": 1.0}),
    # --- sawmill and yard -----------------------------------------------------------------------
    "wild_headrig_saw": (MILL, CW, {"seed": 751, "ao_samples": 16, "ao_dist": 1.0}),
    "wild_log_carriage": (MILL, CW, {"seed": 752, "ao_samples": 16, "ao_dist": 0.8}),
    "wild_roller_conveyor": (MILL, CW, {"seed": 753}),
    "wild_waste_conveyor": (MILL, CW, {"seed": 754}),
    "wild_belt_drive": (MILL, CW, {"seed": 755, "ao_dist": 0.8}),
    "wild_edger": (MILL, CW, {"seed": 756, "ao_dist": 0.8}),
    "wild_sawdust_pile": (MILL, CW, {"seed": 757}),
    "wild_lumber_stack": (MILL, CW, {"seed": 758}),
    "wild_log_deck": (MILL, CW, {"seed": 759, "ao_samples": 16, "ao_dist": 1.2}),
    "wild_chain_hoist": (MILL, CW, {"seed": 760}),
    "wild_filing_bench": (MILL, CW, {"seed": 761}),
    "wild_band_blade_coil": (MILL, CW, {"seed": 762}),
    "wild_saw_blade_circular": (MILL, CW, {"seed": 763}),
    "wild_peavey": (MILL, CW, {"seed": 764}),
    "wild_choker_cable": (MILL, [C], {"seed": 765}),
    "wild_skidder_wreck": (MILL, CW, {"seed": 766, "ao_samples": 16, "ao_dist": 1.2}),
}


def outputs_for(pid: str, conds: list[str]) -> list[str]:
    return [f"models/props/{pid}{'' if c == C else '_' + c}.glb" for c in conds]


def tasks() -> list[Task]:
    out = []
    for pid, (mod, conds, params) in PROPS.items():
        p = {"prop": pid, "conditions": list(conds), **params}
        out.append(Task(name=f"model:props/{pid}", group="models", outputs=outputs_for(pid, conds),
                        sources=blender_sources(mod), params=p, blender=mod))
    return out
