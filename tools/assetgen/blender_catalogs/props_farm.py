"""Farm props family: the Okafor farm in Larch Hollow — farmyard machinery and fixtures, barn
stores and tack, farmhouse furnishings and the root cellar.

One task per prop id; outputs one GLB per condition: models/props/<id>.glb (clean),
<id>_worn.glb, <id>_destroyed.glb. Generator: blender/generators/props_farm.py (built on the
exterior props kit, blender/lib/props_ext_kit.py). Content defs: game/data/props/farm.json.
"""
from __future__ import annotations

from ..core.registry import Task, blender_sources

C, W, D = "clean", "worn", "destroyed"
CW = [C, W]
CWD = [C, W, D]

# id: (conditions, params)
PROPS: dict[str, tuple[list[str], dict]] = {
    # --- yard ----------------------------------------------------------------------------------
    "farm_hay_bale_round": (CWD, {"seed": 1201}),
    "farm_fence_rail": (CWD, {"seed": 1202}),
    "farm_fence_wire": (CWD, {"seed": 1203}),
    "farm_gate": (CWD, {"seed": 1204}),
    "farm_tractor_wreck": (CWD, {"seed": 1205, "ao_samples": 16, "ao_dist": 1.0}),
    "farm_plough": (CW, {"seed": 1206, "ao_dist": 0.8}),
    "farm_water_trough": (CWD, {"seed": 1207, "ao_dist": 0.8}),
    "farm_chicken_coop": (CWD, {"seed": 1208, "ao_dist": 0.8}),
    "farm_windmill_pump": (CWD, {"seed": 1209, "ao_samples": 12, "ao_dist": 1.5}),
    "farm_grain_bin": (CW, {"seed": 1210, "ao_samples": 12, "ao_dist": 1.5}),
    "farm_wagon_wheel": (CWD, {"seed": 1211}),
    # --- barn ----------------------------------------------------------------------------------
    "farm_hay_bale_square": (CWD, {"seed": 1221}),
    "farm_feed_sacks": (CWD, {"seed": 1222}),
    "farm_feed_bin": (CWD, {"seed": 1223}),
    "farm_milk_can": (CWD, {"seed": 1224}),
    "farm_pitchfork": (CW, {"seed": 1225}),
    "farm_tool_rack": (CWD, {"seed": 1226}),
    "farm_saddle_stand": (CWD, {"seed": 1227}),
    "farm_stall_partition": (CWD, {"seed": 1228, "ao_dist": 0.8}),
    "farm_tool_chest": (CWD, {"seed": 1229}),
    "farm_lantern": (CWD, {"seed": 1230, "ao_dist": 0.2}),
    # --- farmhouse -----------------------------------------------------------------------------
    "farm_stove_castiron": (CWD, {"seed": 1241}),
    "farm_butter_churn": (CWD, {"seed": 1242}),
    "farm_washtub": (CWD, {"seed": 1243}),
    "farm_quilt_bed": (CWD, {"seed": 1244, "ao_dist": 0.8}),
    "farm_hope_chest": (CWD, {"seed": 1245}),
    "farm_oil_lamp": (CWD, {"seed": 1246, "ao_dist": 0.2}),
    # --- root cellar ---------------------------------------------------------------------------
    "farm_cellar_shelf": (CWD, {"seed": 1251}),
    "farm_preserve_jars": (CWD, {"seed": 1252, "ao_dist": 0.3}),
    "farm_crate_potatoes": (CWD, {"seed": 1253, "produce": "potato"}),
    "farm_crate_apples": (CWD, {"seed": 1254, "produce": "apple"}),
    "farm_shell_box": (CW, {"seed": 1255, "ao_dist": 0.1}),
}

# Item models for the farm's own items (game/data/items/farm.json names them explicitly, so the
# items catalog leaves them to this family): (blender module, params). Notes and keys reuse the
# shared paper/key generator; the jar and the potatoes come from the props_farm builders.
ITEMS: dict[str, tuple[str, dict]] = {
    "farm_jar_preserves": ("props_farm", {"prop": "farm_jar_preserves", "conditions": [C], "seed": 1261, "ao_dist": 0.1}),
    "farm_cellar_potatoes": ("props_farm", {"prop": "farm_cellar_potatoes", "conditions": [C], "seed": 1262, "ao_dist": 0.1}),
    "farm_note_journal": ("item_paper", {"kind": "logbook", "seed": 1263}),
    "farm_note_page": ("item_paper", {"kind": "note", "seed": 1264, "sheet": "item_paper_note"}),
    "farm_note_ledger": ("item_paper", {"kind": "note", "seed": 1265, "sheet": "item_paper_ledger", "flat": True}),
    "farm_key_storeroom": ("item_paper", {"kind": "key", "seed": 1266, "metal": "item_steel_tool", "tag": "tag"}),
    "farm_key_tackroom": ("item_paper", {"kind": "key", "seed": 1267, "metal": "item_brass", "tag": "lanyard"}),
}


def outputs_for(pid: str, conds: list[str]) -> list[str]:
    return [f"models/props/{pid}{'' if c == C else '_' + c}.glb" for c in conds]


def tasks() -> list[Task]:
    out = []
    module = "props_farm"
    for pid, (conds, params) in PROPS.items():
        p = {"prop": pid, "conditions": list(conds), **params}
        out.append(Task(name=f"model:props/{pid}", group="models", outputs=outputs_for(pid, conds),
                        sources=blender_sources(module), params=p, blender=module))
    for iid, (mod, params) in ITEMS.items():
        p = {"name": iid, **params}
        out.append(Task(name=f"model:items/{iid}", group="models", outputs=[f"models/items/{iid}.glb"],
                        sources=blender_sources(mod), params=p, blender=mod))
    return out
