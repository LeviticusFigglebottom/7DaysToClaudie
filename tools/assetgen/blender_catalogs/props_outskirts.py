"""Larch Hollow outskirts (agent H2): Larch Pond Bait & Boat, the Ashen watch camp and Tamsin River
Campground (region D6).

One task per prop id, one GLB per condition: models/props/<id>.glb (clean), <id>_worn.glb,
<id>_destroyed.glb. Generators: blender/generators/props_outskirts.py (boathouse, campground) and
props_outskirts_ashen.py (the watch camp, plus the plank door leaf models/kit/door_plank[_broken]
its doorways hang); shared parts in blender/lib/props_outskirts_parts.py. The Hollowed Ashen's
bodies (models/characters/ashen_a, ashen_b) come from blender/generators/character_ashen.py, which
wraps character_body. Content defs: game/data/props/outskirts.json, game/data/enemies/outskirts.json;
materials: game/data/materials/props_outskirts.json; textures: textures/gen/outskirts.py.
"""
from __future__ import annotations

from ..core.registry import Task, blender_sources

C, W, D = "clean", "worn", "destroyed"
CW = [C, W]
CWD = [C, W, D]
OUT = "props_outskirts"
ASH = "props_outskirts_ashen"

# id: (generator module, conditions, params). Conditions match the variants in props/outskirts.json.
PROPS: dict[str, tuple[str, list[str], dict]] = {
    # --- Larch Pond Bait & Boat --------------------------------------------------------------------
    "out_dock_section": (OUT, CW, {"seed": 1101, "ao_dist": 0.8}),
    "out_dock_piles": (OUT, CW, {"seed": 1102}),
    "out_rowboat": (OUT, CWD, {"seed": 1103, "ao_dist": 0.7}),
    "out_rowboat_hauled": (OUT, CW, {"seed": 1104, "ao_dist": 0.8}),
    "out_fishing_rod": (OUT, CW, {"seed": 1105}),
    "out_boat_doors": (OUT, CW, {"seed": 1106, "ao_dist": 0.8}),
    "out_bait_tank": (OUT, CWD, {"seed": 1107}),
    "out_tackle_wall": (OUT, CW, {"seed": 1108}),
    "out_rod_rack": (OUT, CWD, {"seed": 1109}),
    "out_life_jackets": (OUT, CW, {"seed": 1110}),
    "out_outboard_motor": (OUT, CWD, {"seed": 1111}),
    "out_net_pile": (OUT, CW, {"seed": 1112}),
    "out_bait_sign": (OUT, CW, {"seed": 1113}),
    "out_trophy_fish": (OUT, CW, {"seed": 1114}),
    # --- Ashen watch camp ----------------------------------------------------------------------------
    "out_palisade": (ASH, CWD, {"seed": 1201}),
    "out_palisade_half": (ASH, CWD, {"seed": 1202}),
    "out_palisade_gate": (ASH, CW, {"seed": 1203, "ao_dist": 0.9}),
    "out_palisade_breach": (ASH, CW, {"seed": 1204}),
    "out_effigy": (ASH, CW, {"seed": 1205}),
    "out_bone_totem": (ASH, CW, {"seed": 1206}),
    "out_bone_chime": (ASH, CW, {"seed": 1207}),
    "out_burial_platform": (ASH, CW, {"seed": 1208, "ao_dist": 0.9}),
    "out_pit_hut": (ASH, CWD, {"seed": 1209, "ao_dist": 0.9}),
    "out_pyre": (ASH, CW, {"seed": 1210}),
    "out_hide_frame": (ASH, CW, {"seed": 1211}),
    "out_antler_pile": (ASH, [C], {"seed": 1212}),
    "out_stone_fire_pit": (ASH, CW, {"seed": 1213}),
    "out_hide_bed": (ASH, CW, {"seed": 1214}),
    "out_ashen_cache": (ASH, CW, {"seed": 1215}),
    "out_ashen_bundle": (ASH, CW, {"seed": 1216}),
    "out_longhouse_shell": (ASH, [C], {"seed": 1217, "ao_samples": 12, "ao_dist": 1.2}),
    "out_smoke_hut_shell": (ASH, [C], {"seed": 1218, "ao_samples": 12, "ao_dist": 1.0}),
    "out_lean_to_shell": (ASH, [C], {"seed": 1219, "ao_samples": 12, "ao_dist": 1.0}),
    # --- Tamsin River Campground -----------------------------------------------------------------------
    "out_rv": (OUT, CWD, {"seed": 1301, "ao_samples": 16, "ao_dist": 1.0}),
    "out_tent_dome": (OUT, CWD, {"seed": 1302, "ao_dist": 0.8}),
    "out_tent_cabin": (OUT, CWD, {"seed": 1303, "ao_dist": 1.0}),
    "out_fire_ring": (OUT, CW, {"seed": 1304}),
    "out_tent_pad": (OUT, CW, {"seed": 1305}),
    "out_bear_box": (OUT, CWD, {"seed": 1306}),
    "out_host_trailer_shell": (OUT, CW, {"seed": 1307, "ao_samples": 12, "ao_dist": 1.2}),
    "out_block_roof": (OUT, [C], {"seed": 1308, "ao_samples": 12, "ao_dist": 1.0}),
    "out_kiosk_shell": (OUT, CW, {"seed": 1309, "ao_samples": 12, "ao_dist": 1.0}),
    "out_camp_sign": (OUT, CW, {"seed": 1310}),
    "out_gate_arm": (OUT, CW, {"seed": 1311}),
    "out_water_spigot": (OUT, CW, {"seed": 1312}),
    "out_camp_chair": (OUT, CWD, {"seed": 1313}),
    "out_lockbox": (OUT, [C], {"seed": 1314}),
}

# Kit door leaves for the camp's doorways (the POI kit door contract; `"model": "door_plank"` on an
# opening, its broken state loads door_plank_broken).
KIT: dict[str, dict] = {
    "door_plank": {"seed": 1291},
    "door_plank_broken": {"seed": 1291, "broken": True},
}

FUR = {"type": "jacket", "sleeve": 0.95, "hem": -0.16, "collar": True, "open_front": 0.09, "torn": 0.35, "flare": 0.02,
       "neck_front": 0.04}
BODIES: dict[str, dict] = {
    # A watchman: gaunt, long matted hair, a hide coat open over a wool shirt, hide leggings and
    # moccasins, the Bloom out of an old wound in the forearm.
    "ashen_a": {
        "seed": 1401, "height": 1.8, "sex": "m", "build": 0.3, "gaunt": 0.6, "hunch": 0.3, "head_tilt": 6.0,
        "limp_side": "L", "claw": 0.6, "jaw_drop": 10.0, "mouth_open": 0.5, "eye_open": 0.5, "arm_raise": 0.2,
        "raise_side": "R",
        "outfit": {"tops": [{"type": "flannel", "sleeve": 0.92, "hem": -0.08, "collar": False, "torn": 0.3, "neck_front": 0.05},
                            FUR],
                   "pants": {"type": "denim", "belt": True, "torn": 0.35, "length": 0.92}},
        "boots": {"L": True, "R": True, "height": 0.07},
        "hair": {"style": "long", "hairline": 0.04, "patchy": 0.15, "locks": 14, "length": 0.095},
        "wounds": [{"at": "fa", "side": "L", "t": 0.5, "dir": [0.3, 0.0, 1.0], "r": 0.022, "blood": 0.6,
                    "bloom_spec": {"filaments": 5, "shelves": 2, "lumps": 5}}],
        "blood": 0.25, "grime": 0.75,
    },
    # A woman of the camp in a wool tunic under a short hide cape, hair matted with ash, the fever's
    # Bloom from the neck.
    "ashen_b": {
        "seed": 1402, "height": 1.66, "sex": "f", "build": 0.28, "gaunt": 0.5, "hunch": 0.2, "head_tilt": -9.0,
        "limp_side": "R", "claw": 0.5, "jaw_drop": 8.0, "mouth_open": 0.4, "eye_open": 0.6,
        "outfit": {"tops": [{"type": "tshirt", "sleeve": 0.9, "hem": -0.14, "torn": 0.3, "neck_front": 0.03},
                            {"type": "jacket", "sleeve": 0.45, "hem": 0.05, "collar": True, "open_front": 0.07,
                             "torn": 0.45, "flare": 0.015, "neck_front": 0.03}],
                   "pants": {"type": "denim", "belt": False, "torn": 0.3, "length": 0.95}},
        "boots": {"L": True, "R": True, "height": 0.07},
        "hair": {"style": "long", "hairline": 0.05, "patchy": 0.2, "locks": 12, "length": 0.095},
        "wounds": [{"at": "neck", "side": "R", "t": 0.4, "dir": [1.0, 0.0, 0.3], "r": 0.022, "blood": 0.5,
                    "bloom_spec": {"filaments": 6, "shelves": 1, "lumps": 6}}],
        "blood": 0.2, "grime": 0.7,
    },
}


def outputs_for(pid: str, conds: list[str]) -> list[str]:
    return [f"models/props/{pid}{'' if c == C else '_' + c}.glb" for c in conds]


def tasks() -> list[Task]:
    out = []
    for pid, (mod, conds, params) in PROPS.items():
        p = {"prop": pid, "conditions": list(conds), **params}
        out.append(Task(name=f"model:props/{pid}", group="models", outputs=outputs_for(pid, conds),
                        sources=blender_sources(mod), params=p, blender=mod))
    for kid, params in KIT.items():
        p = {"prop": "door_plank", "conditions": [C], **params}
        out.append(Task(name=f"model:kit/{kid}", group="models", outputs=[f"models/kit/{kid}.glb"],
                        sources=blender_sources(ASH), params=p, blender=ASH))
    body_sources = sorted(set(blender_sources("character_ashen")) | set(blender_sources("character_body")))
    for key, p in BODIES.items():
        rel = f"models/characters/{key}.glb"
        out.append(Task(name=f"model:characters/{key}", group="models", outputs=[rel], sources=body_sources,
                        params={"name": key, **p}, blender="character_ashen",
                        imports={rel: {"type": "scene", "animation": True}}))
    return out
