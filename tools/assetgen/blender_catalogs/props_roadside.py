"""Route 9 roadside props (Cordon Gas & Garage, Timberline Motel, Tamsin Valley Clinic): one task per prop
id producing models/props/<id>.glb (clean), <id>_worn.glb and, for props that break, <id>_destroyed.glb.

Generator: blender/generators/props_roadside.py (BUILDERS keyed by prop id; exterior props kit).
Game data: game/data/props/roadside.json; materials: game/data/materials/props_roadside.json; lettered
atlases + bedspread / tread-plate / oil-stain textures: textures/gen/roadside.py.

Also builds the family's readable notes and keys with the shared item_paper generator into
models/items/road/<item id>.glb (their ItemDefs in game/data/items/roadside.json point there).

Task names contain "roadside" (`build_assets.py --match roadside` builds the models; the textures are
`--match tex:road_` / `--match decal_road_`).
"""
from __future__ import annotations

from ..core.registry import Task, blender_sources

C, W, D = "clean", "worn", "destroyed"
CW = [C, W]
CWD = [C, W, D]
BIG = {"ao_samples": 16, "ao_dist": 1.2}

# id: (conditions, extra params)
PROPS: dict[str, tuple[list[str], dict]] = {
    # --- forecourt ------------------------------------------------------------------------------
    "road_fuel_pump": (CWD, {"seed": 9601}),
    "road_fuel_pump_vintage": (CWD, {"seed": 9602}),
    "road_pump_island": (CW, {"seed": 9603, **BIG}),
    "road_fuel_canopy": (CW, {"seed": 9604, "ao_samples": 16, "ao_dist": 2.0}),
    "road_canopy_column": (CW, {"seed": 9605, **BIG}),
    "road_canopy_light": (CWD, {"seed": 9606}),
    "road_air_pump": (CWD, {"seed": 9607}),
    "road_ice_freezer": (CWD, {"seed": 9608}),
    "road_vending_machine": (CWD, {"seed": 9609}),
    "road_newspaper_box": (CWD, {"seed": 9610}),
    "road_sign_gas": (CWD, {"seed": 9611, **BIG}),
    # --- garage ---------------------------------------------------------------------------------
    "road_tire_rack": (CW, {"seed": 9621}),
    "road_tire_stack": (CW, {"seed": 9622}),
    "road_lift_post": (CW, {"seed": 9623, **BIG}),
    "road_lift_post_b": (CW, {"seed": 9624, **BIG}),
    "road_tool_chest": (CWD, {"seed": 9625}),
    "road_engine_hoist": (CW, {"seed": 9626}),
    "road_oil_drum": (CWD, {"seed": 9627}),
    "road_oil_shelf": (CWD, {"seed": 9628}),
    "road_rollup_door": (CWD, {"seed": 9629, **BIG}),
    "road_rollup_door_open": (CW, {"seed": 9630}),
    "road_workbench": (CW, {"seed": 9631}),
    "road_creeper": (CW, {"seed": 9632}),
    "road_cooler": (CWD, {"seed": 9633}),
    # --- motel ----------------------------------------------------------------------------------
    "road_sign_motel": (CWD, {"seed": 9641, **BIG}),
    "road_motel_bed": (CWD, {"seed": 9642}),
    "road_motel_nightstand": (CWD, {"seed": 9643}),
    "road_tv_dresser": (CWD, {"seed": 9644}),
    "road_housekeeping_cart": (CWD, {"seed": 9645}),
    "road_washer": (CWD, {"seed": 9646}),
    "road_dryer": (CWD, {"seed": 9647}),
    "road_ice_machine": (CW, {"seed": 9648}),
    "road_walkway_post": (CW, {"seed": 9649}),
    "road_suitcase": (CW, {"seed": 9650}),
    # --- clinic ---------------------------------------------------------------------------------
    "road_exam_table": (CWD, {"seed": 9661}),
    "road_medical_cabinet": (CWD, {"seed": 9662}),
    "road_iv_stand": (CWD, {"seed": 9663}),
    "road_wheelchair": (CWD, {"seed": 9664}),
    "road_xray_unit": (CW, {"seed": 9665, **BIG}),
    "road_waiting_chairs": (CWD, {"seed": 9666}),
    "road_staff_locker": (CWD, {"seed": 9667}),
    "road_sharps_bin": (CW, {"seed": 9668}),
    "road_mop_bucket": (CW, {"seed": 9669}),
    # --- wall-mounted lettering -----------------------------------------------------------------
    "road_xray_viewer": (CW, {"seed": 9671}),
    "road_eye_chart": (CW, {"seed": 9672}),
    "road_quarantine_notice": (CW, {"seed": 9673}),
    "road_sign_clinic": (CW, {"seed": 9674}),
    "road_plaque_office": (CW, {"seed": 9675}),
    "road_plaque_laundry": (CW, {"seed": 9676}),
    "road_plaque_rates": (CW, {"seed": 9677}),
    "road_plaque_staff": (CW, {"seed": 9678}),
    "road_plaque_ring_bell": (CW, {"seed": 9679}),
    "road_plaque_exit": (CW, {"seed": 9680}),
    "road_plaque_clinic_hours": (CW, {"seed": 9681}),
}
PROPS.update({f"road_room_number_{n}": ([C], {"seed": 9690 + n}) for n in range(1, 9)})
PROPS.update({f"road_plywood_{name}": (CW, {"seed": 9700 + i}) for i, name in enumerate(
    ["sick_inside", "no_gas", "quarantine", "use_bathrooms", "stay_off_walkway", "help_room6", "dead_inside", "gone_to_cordon"])})

# Readables and keys of the family (item_paper generator): item id -> params.
ITEMS: dict[str, dict] = {
    "note_road_jess_workbench": {"kind": "note", "seed": 9801, "sheet": "item_paper_note"},
    "note_road_dale_ledger": {"kind": "note", "seed": 9802, "sheet": "item_paper_ledger", "flat": True},
    "note_road_courier": {"kind": "schematic", "seed": 9803, "sheet": "item_paper_ledger"},
    "note_road_voss_log": {"kind": "logbook", "seed": 9804},
    "note_road_cordon_memo": {"kind": "note", "seed": 9805, "sheet": "item_paper_ledger", "flat": True},
    "note_road_june_register": {"kind": "logbook", "seed": 9806},
    "note_road_room6": {"kind": "note", "seed": 9807, "sheet": "item_paper_note"},
    "road_key_cordon_stock": {"kind": "key", "seed": 9811, "metal": "item_brass", "tag": "tag"},
    "road_key_cordon_safe": {"kind": "key", "seed": 9812, "metal": "item_steel_tool", "tag": "lanyard"},
    "road_key_clinic_drugs": {"kind": "key", "seed": 9813, "metal": "item_steel_tool", "tag": "lanyard"},
    "road_key_motel_master": {"kind": "key", "seed": 9814, "metal": "item_brass", "tag": "tag"},
}


def outputs_for(pid: str, conds: list[str]) -> list[str]:
    return [f"models/props/{pid}{'' if c == C else '_' + c}.glb" for c in conds]


def tasks() -> list[Task]:
    out = []
    module = "props_roadside"
    for pid, (conds, params) in PROPS.items():
        p = {"prop": pid, "conditions": list(conds), **params}
        out.append(Task(name=f"model:roadside/{pid}", group="models", outputs=outputs_for(pid, conds),
                        sources=blender_sources(module), params=p, blender=module))
    for item_id, params in ITEMS.items():
        p = {"name": item_id, **params}
        out.append(Task(name=f"model:roadside/items/{item_id}", group="models", outputs=[f"models/items/road/{item_id}.glb"],
                        sources=blender_sources("item_paper"), params=p, blender="item_paper"))
    return out
