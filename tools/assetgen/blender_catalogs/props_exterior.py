"""Exterior props family: streets, yards and ruined interiors of an abandoned 1990s logging town.

One task per prop id; outputs one GLB per condition: models/props/<id>.glb (clean),
<id>_worn.glb, <id>_destroyed.glb. Generators: blender/generators/props_ext_*.py (shared code in
blender/lib/props_ext_*.py). Content defs: game/data/props/exterior.json.
"""
from __future__ import annotations

from ..core.registry import Task, blender_sources

C, W, D = "clean", "worn", "destroyed"
CW = [C, W]
CWD = [C, W, D]

# id: (generator module suffix, conditions, params)
PROPS: dict[str, tuple[str, list[str], dict]] = {
    # --- clutter / containers -----------------------------------------------------------------
    "cardboard_box": ("clutter", CWD, {"seed": 101}),
    "cardboard_box_open": ("clutter", CWD, {"seed": 102}),
    "crate_wood": ("clutter", CWD, {"seed": 103}),
    "pallet": ("clutter", CWD, {"seed": 104}),
    "barrel_metal": ("clutter", CWD, {"seed": 105, "paint": "paint_blue"}),
    "trash_bag": ("clutter", CWD, {"seed": 106}),
    "trash_pile": ("clutter", CW, {"seed": 107}),
    "debris_pile": ("clutter", CW, {"seed": 108}),
    "plank_pile": ("clutter", CW, {"seed": 109}),
    "plaster_chunks": ("clutter", [C], {"seed": 110}),
    "glass_shards": ("clutter", [C], {"seed": 111}),
    "paper_scatter": ("clutter", CW, {"seed": 112}),
    "cans_scatter": ("clutter", CW, {"seed": 113}),
    "bottles_scatter": ("clutter", CW, {"seed": 114}),
    "books_scatter": ("clutter", CW, {"seed": 115}),
    "clothes_pile": ("clutter", CW, {"seed": 116}),
    "toolbox": ("clutter", CWD, {"seed": 117}),
    "duffel_bag": ("clutter", CW, {"seed": 118}),
    "backpack_dropped": ("clutter", CW, {"seed": 119}),
    "bucket": ("clutter", CWD, {"seed": 120}),
    "gas_can": ("clutter", CWD, {"seed": 121}),
    "propane_tank_small": ("clutter", CW, {"seed": 122}),
    "tire": ("clutter", CW, {"seed": 123}),
    "shopping_cart": ("street", CWD, {"seed": 124}),
    "bicycle_rusty": ("street", CWD, {"seed": 125}),
    "payphone": ("street", CWD, {"seed": 126}),
    # --- survivor / story ----------------------------------------------------------------------
    "sleeping_bag": ("survivor", CW, {"seed": 201}),
    "camp_stove": ("survivor", CW, {"seed": 202}),
    "candle_cluster": ("survivor", CW, {"seed": 203}),
    "lantern_camping": ("survivor", CWD, {"seed": 204}),
    "barricade_mattress": ("survivor", CWD, {"seed": 205}),
    "plywood_leaning": ("survivor", CWD, {"seed": 206}),
    "sign_plywood_painted": ("survivor", CWD, {"seed": 207}),
    "corpse_remains": ("survivor", CW, {"seed": 208}),
    "bloody_bandages": ("survivor", [C], {"seed": 209}),
    "oil_drum_fire": ("survivor", CW, {"seed": 210}),
    # --- street / exterior ---------------------------------------------------------------------
    "car_sedan_wreck": ("vehicles", CWD, {"seed": 301, "paint": {"clean": "car_paint_maroon", "worn": "car_paint_tan"},
                                          "ao_samples": 16, "ao_dist": 1.0}),
    "pickup_wreck": ("vehicles", CWD, {"seed": 302, "paint": {"clean": "car_paint_blue", "worn": "car_paint_green"},
                                       "ao_samples": 16, "ao_dist": 1.0}),
    "utility_pole": ("street", CW, {"seed": 303, "ao_dist": 1.0}),
    "street_lamp": ("street", CWD, {"seed": 304}),
    "road_sign_stop": ("street", CWD, {"seed": 305}),
    "road_sign_speed": ("street", CWD, {"seed": 306}),
    "mailbox_rural": ("street", CWD, {"seed": 307}),
    "fence_picket_2m": ("street", CWD, {"seed": 308}),
    "fence_chainlink_2m": ("street", CWD, {"seed": 309}),
    "fence_wood_2m": ("street", CWD, {"seed": 310}),
    "fence_post": ("street", CW, {"seed": 311}),
    "dumpster": ("street", CW, {"seed": 312}),
    "picnic_table": ("street", CWD, {"seed": 313}),
    "fire_hydrant": ("street", CW, {"seed": 314}),
    "bench_park": ("street", CWD, {"seed": 315}),
    "sawhorse_barricade": ("street", CWD, {"seed": 316}),
    "jersey_barrier": ("street", CWD, {"seed": 317}),
    # Highway bridge kit, instanced along road bridge spans by the game (world/bridges.gd).
    "bridge_deck": ("street", [C], {"seed": 321, "ao_dist": 1.5}),
    "bridge_pier": ("street", [C], {"seed": 322, "ao_dist": 1.5}),
    "woodpile": ("street", CW, {"seed": 318}),
    "wheelbarrow": ("street", CW, {"seed": 319}),
    "well_pump": ("street", CW, {"seed": 320}),
}


def outputs_for(pid: str, conds: list[str]) -> list[str]:
    return [f"models/props/{pid}{'' if c == C else '_' + c}.glb" for c in conds]


def tasks() -> list[Task]:
    out = []
    for pid, (mod, conds, params) in PROPS.items():
        module = f"props_ext_{mod}"
        p = {"prop": pid, "conditions": list(conds), **params}
        out.append(Task(name=f"model:props/{pid}", group="models", outputs=outputs_for(pid, conds),
                        sources=blender_sources(module), params=p, blender=module))
    return out
