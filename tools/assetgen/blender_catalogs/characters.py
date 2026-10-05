"""Characters (docs/CHARACTERS.md): the Hollowed bodies, gibs and first-person arms.

Bodies are one generator (character_body) with different params: proportions, posture, outfit,
hair, wounds and Bloom growth. Sites ("at") are body parts: hips/spine/chest/neck/head or limb
bones ua/fa/th/sh with side + t (fraction along the bone) + dir (lateral/out, along/up, front).
"""
from __future__ import annotations

from ..core.registry import Task, blender_sources

FLANNEL_A = {"type": "flannel", "sleeve": 0.97, "hem": -0.10, "collar": True, "torn": 0.25, "neck_front": 0.05,
             "tears": [{"at": "chest", "side": "L", "t": 0.45, "dir": [0.5, 0.0, 0.8], "r": 0.05}]}

BODIES = {
    # Walker: lanky man in a red flannel and jeans, bitten on the neck, a hand reaching.
    "hollow_a": {
        "seed": 101, "height": 1.78, "sex": "m", "build": 0.35, "hunch": 0.25, "head_tilt": 8.0, "limp_side": "R",
        "arm_raise": 0.35, "raise_side": "R", "claw": 0.55, "jaw_drop": 9.0, "mouth_open": 0.45, "eye_open": 0.55,
        "outfit": {"tops": [FLANNEL_A],
                   "pants": {"type": "denim", "belt": True, "torn": 0.2,
                             "tears": [{"at": "sh", "side": "R", "t": 0.04, "dir": [0, 0, 1], "r": 0.045}]}},
        "boots": {"L": True, "R": True, "height": 0.15},
        "hair": {"style": "short", "hairline": 0.05, "patchy": 0.3},
        "wounds": [{"at": "neck", "side": "L", "t": 0.30, "dir": [1.0, 0.0, 0.35], "r": 0.024, "blood": 1.0,
                    "bloom_spec": {"filaments": 6, "shelves": 2, "lumps": 6}}],
        "bloom": [{"at": "fa", "side": "R", "t": 0.35, "dir": [0.3, 0, 1], "r": 0.022, "filaments": 3, "shelves": 1}],
        "blood": 0.6, "grime": 0.45,
    },
    # Walker: young woman in a faded t-shirt, long stringy hair, bitten shoulder.
    "hollow_b": {
        "seed": 202, "height": 1.64, "sex": "f", "build": 0.30, "hunch": 0.15, "head_tilt": -7.0, "limp_side": "L",
        "claw": 0.45, "jaw_drop": 7.0, "mouth_open": 0.35, "eye_open": 0.7,
        "outfit": {"tops": [{"type": "tshirt", "sleeve": 0.40, "hem": -0.05, "torn": 0.35, "neck_front": 0.02,
                             "tears": [{"at": "spine", "side": "R", "t": 0.6, "dir": [1.0, 0.0, 0.2], "r": 0.05}]}],
                   "pants": {"type": "denim", "belt": False, "torn": 0.3, "length": 0.97}},
        "boots": {"L": True, "R": True, "height": 0.12},
        # Hair locks are rigid with the head segment: keep them chin length (<= ~0.1 m) or they
        # swing into the shoulders when the head bows (dormant poses, attacks).
        "hair": {"style": "long", "hairline": 0.055, "patchy": 0.25, "locks": 12, "length": 0.095},
        "wounds": [{"at": "ua", "side": "R", "t": 0.18, "dir": [1.0, 0.0, 0.2], "r": 0.026, "blood": 1.0,
                    "bloom_spec": {"filaments": 5, "shelves": 3}},
                   {"at": "fa", "side": "L", "t": 0.55, "dir": [0.0, 0.0, 1.0], "r": 0.018, "blood": 0.8,
                    "bloom_spec": {"filaments": 2, "shelves": 0, "lumps": 4}}],
        "blood": 0.55, "grime": 0.4,
    },
    # Walker: heavyset man in an open canvas work jacket over a t-shirt, balding, Bloom from the mouth.
    "hollow_c": {
        "seed": 303, "height": 1.85, "sex": "m", "build": 0.80, "belly": 0.9, "hunch": 0.30, "head_tilt": 4.0,
        "limp_side": "L", "claw": 0.5, "jaw_drop": 12.0, "mouth_open": 0.6, "eye_open": 0.45, "arm_raise": 0.0,
        "outfit": {"tops": [{"type": "tshirt", "sleeve": 0.40, "hem": -0.04, "torn": 0.2, "neck_front": 0.02,
                             "tears": [{"at": "chest", "side": "R", "t": 0.3, "dir": [0.2, 0.0, 1.0], "r": 0.045}]},
                            {"type": "jacket", "sleeve": 1.0, "hem": -0.07, "collar": True, "open_front": 0.07,
                             "torn": 0.12, "flare": 0.012, "neck_front": 0.03}],
                   "pants": {"type": "denim", "belt": True, "torn": 0.1}},
        "boots": {"L": True, "R": True, "height": 0.16},
        "hair": {"style": "balding", "hairline": 0.02, "bald": 0.9, "patchy": 0.2},
        "wounds": [{"at": "chest", "side": "R", "t": 0.3, "dir": [0.2, 0.0, 1.0], "r": 0.03, "blood": 1.0,
                    "bloom_spec": {"filaments": 4, "shelves": 3, "lumps": 8}}],
        "bloom": [{"at": "head", "side": "L", "dir": [0.25, -0.55, 0.8], "r": 0.022, "filaments": 6, "shelves": 0,
                   "length": 0.05, "sag": 1.0}],
        "blood": 0.65, "grime": 0.5,
    },
    # Walker: hospital patient: gown open at the back, bare legs and feet, Bloom along the spine.
    "hollow_d": {
        "seed": 404, "height": 1.70, "sex": "m", "build": 0.15, "hunch": 0.35, "head_tilt": 12.0, "limp_side": "R",
        "head_forward": 0.2, "claw": 0.65, "jaw_drop": 10.0, "mouth_open": 0.5, "eye_open": 0.8,
        "outfit": {"tops": [{"type": "hospital", "sleeve": 0.28, "hem": -0.30, "open_back": 0.075, "torn": 0.15,
                             "neck_drop": 0.012, "neck_front": 0.03, "flare": 0.018}]},
        "boots": {},
        "hair": {"style": "stubble", "hairline": 0.05, "patchy": 0.5},
        "bloom": [{"at": "chest", "side": "L", "t": 0.55, "dir": [0.0, 0.0, -1.0], "r": 0.035, "filaments": 4, "shelves": 4,
                   "shelf_size": 0.02},
                  {"at": "spine", "side": "L", "t": 0.5, "dir": [0.15, 0.0, -1.0], "r": 0.03, "filaments": 3, "shelves": 3},
                  {"at": "neck", "side": "R", "t": 0.35, "dir": [0.7, 0.0, -0.7], "r": 0.02, "filaments": 4, "shelves": 1}],
        "wounds": [{"at": "fa", "side": "L", "t": 0.3, "dir": [0.0, 0.0, 1.0], "r": 0.014, "blood": 0.7, "bloom": False}],
        "blood": 0.45, "grime": 0.35,
    },
    # Lurcher: gaunt, long-limbed, hunched; flannel shredded to rags, one boot lost.
    "lurcher_a": {
        "seed": 505, "height": 1.88, "sex": "m", "build": 0.08, "gaunt": 1.0, "hunch": 0.75, "head_forward": 0.55,
        "arm_scale": 1.09, "leg_scale": 1.04, "claw": 0.95, "jaw_drop": 16.0, "mouth_open": 0.8, "eye_open": 0.9,
        "head_tilt": -10.0, "limp_side": "L", "arm_raise": 0.5, "raise_side": "L", "wall_eye": 8.0,
        "outfit": {"tops": [{"type": "flannel", "sleeve_L": 0.62, "sleeve_R": 0.30, "hem": -0.02, "collar": True,
                             "torn": 0.85, "neck_front": 0.06,
                             "tears": [{"at": "spine", "side": "L", "t": 0.5, "dir": [1.0, 0.0, 0.0], "r": 0.07}]}],
                   "pants": {"type": "denim", "belt": False, "torn": 0.65, "length_L": 0.82, "length_R": 0.95}},
        "boots": {"L": False, "R": True, "height": 0.14},
        "hair": {"style": "long", "hairline": 0.06, "patchy": 0.7, "locks": 9, "length": 0.09},
        "wounds": [{"at": "spine", "side": "L", "t": 0.5, "dir": [1.0, 0.0, 0.0], "r": 0.04, "depth": 0.9, "blood": 1.0,
                    "bloom_spec": {"filaments": 7, "shelves": 4, "lumps": 9}},
                   {"at": "head", "side": "R", "dir": [0.55, -0.45, 0.7], "r": 0.016, "blood": 1.0,
                    "bloom_spec": {"filaments": 4, "shelves": 0, "lumps": 4, "length": 0.05, "sag": 1.0}}],
        "bloom": [{"at": "ua", "side": "R", "t": 0.1, "dir": [1.0, 0.0, -0.3], "r": 0.03, "filaments": 4, "shelves": 4,
                   "shelf_size": 0.02}],
        "blood": 0.75, "grime": 0.6, "seg_tris": {"body_torso": 2350},
    },
    # Lurcher: shirtless, barefoot, Bloom shelves across the back and shoulders.
    "lurcher_b": {
        "seed": 606, "height": 1.80, "sex": "m", "build": 0.12, "gaunt": 1.0, "hunch": 0.65, "head_forward": 0.45,
        "arm_scale": 1.07, "leg_scale": 1.03, "claw": 0.9, "jaw_drop": 14.0, "mouth_open": 0.7, "eye_open": 0.85,
        "head_tilt": 9.0, "limp_side": "R", "arm_raise": 0.2, "raise_side": "R",
        "outfit": {"pants": {"type": "canvas", "belt": True, "torn": 0.55, "length_L": 0.70, "length_R": 0.66}},
        "boots": {},
        "hair": {"style": "short", "hairline": 0.075, "patchy": 0.85},
        "bloom": [{"at": "chest", "side": "R", "t": 0.75, "dir": [0.4, 0.0, -1.0], "r": 0.045, "filaments": 5, "shelves": 6,
                   "shelf_size": 0.024, "lumps": 10},
                  {"at": "chest", "side": "L", "t": 0.35, "dir": [0.6, 0.0, -1.0], "r": 0.035, "filaments": 3, "shelves": 4,
                   "shelf_size": 0.02},
                  {"at": "ua", "side": "L", "t": 0.15, "dir": [1.0, 0.0, 0.0], "r": 0.025, "filaments": 3, "shelves": 2},
                  {"at": "head", "side": "L", "dir": [0.0, -0.6, 0.8], "r": 0.016, "filaments": 7, "shelves": 0,
                   "length": 0.06, "sag": 1.0, "lumps": 3}],
        "wounds": [{"at": "spine", "side": "R", "t": 0.2, "dir": [0.3, 0.0, 1.0], "r": 0.03, "blood": 1.0,
                    "bloom_spec": {"filaments": 3, "shelves": 1}}],
        "blood": 0.7, "grime": 0.65,
    },
    # Keener: swollen Bloom throat sac, long unhinged jaw hanging open.
    "keener_a": {
        "seed": 707, "height": 1.72, "sex": "m", "build": 0.18, "gaunt": 0.9, "hunch": 0.35, "head_forward": 0.35,
        "jaw_scale": 1.45, "jaw_drop": 30.0, "mouth_open": 1.0, "jaw_base": 6.0, "claw": 0.7, "eye_open": 1.0,
        "head_tilt": 3.0, "limp_side": "L", "wall_eye": 6.0,
        "throat_sac": {"size": 1.0, "bloom_lumps": 4}, "neck_cut": 0.86,
        "outfit": {"tops": [{"type": "tshirt", "sleeve": 0.38, "hem": -0.04, "torn": 0.5, "neck_drop": 0.03,
                             "neck_front": 0.05}],
                   "pants": {"type": "denim", "belt": True, "torn": 0.3}},
        "boots": {"L": True, "R": True, "height": 0.15},
        "hair": {"style": "medium", "hairline": 0.06, "patchy": 0.6, "locks": 6, "length": 0.065},
        "bloom": [{"at": "head", "side": "L", "dir": [0.3, -0.5, 0.8], "r": 0.016, "filaments": 6, "shelves": 0,
                   "length": 0.05, "sag": 1.0}],
        "blood": 0.5, "grime": 0.45,
    },
}


def tasks() -> list[Task]:
    out = []
    for key, p in BODIES.items():
        params = {"name": key, **p}
        rel = f"models/characters/{key}.glb"
        out.append(Task(name=f"model:characters/{key}", group="models", outputs=[rel],
                        sources=blender_sources("character_body"), params=params, blender="character_body",
                        imports={rel: {"type": "scene", "animation": True}}))
    rel = "models/characters/gibs.glb"
    out.append(Task(name="model:characters/gibs", group="models", outputs=[rel],
                    sources=blender_sources("character_gibs"), params={"name": "gibs", **BODIES["hollow_a"]},
                    blender="character_gibs", imports={rel: {"type": "scene"}}))
    rel = "models/characters/fp_arms.glb"
    out.append(Task(name="model:characters/fp_arms", group="models", outputs=[rel],
                    sources=blender_sources("character_fp_arms"), params={"name": "fp_arms", "seed": 808, "height": 1.78},
                    blender="character_fp_arms", imports={rel: {"type": "scene", "animation": True}}))
    return out
