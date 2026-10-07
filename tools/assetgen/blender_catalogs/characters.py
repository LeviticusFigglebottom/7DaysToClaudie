"""Characters (docs/CHARACTERS.md): the Hollowed bodies, gibs and first-person arms.

Bodies are one generator (character_body) with different params: proportions, posture, outfit,
hair, wounds and Bloom growth. Sites ("at") are body parts: hips/spine/chest/neck/head or limb
bones ua/fa/th/sh with side + t (fraction along the bone) + dir (lateral/out, along/up, front).
"""
from __future__ import annotations

from ..core.paths import GAME
from ..core.registry import Task, blender_sources

FLANNEL_A = {"type": "flannel", "sleeve": 0.97, "hem": -0.10, "collar": True, "torn": 0.25, "neck_front": 0.05,
             "buttons": 7, "pockets": [{"side": "L", "x": 0.068, "y": 0.13, "w": 0.11, "h": 0.12},
                                       {"side": "R", "x": 0.068, "y": 0.13, "w": 0.11, "h": 0.12}],
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
    # --- Populations (ADR-0028, game/data/populations) -------------------------------------------
    # Cordon road crew: navy coveralls zipped to the neck under a hi-vis vest (retroreflective
    # bands and braces), a white supervisor's hard hat, steel-toe boots. Bitten through the collar.
    "hollow_cordon_a": {
        "seed": 911, "height": 1.81, "sex": "m", "build": 0.45, "hunch": 0.3, "head_forward": 0.35, "head_tilt": -5.0,
        "limp_side": "R", "claw": 0.5, "jaw_drop": 11.0, "mouth_open": 0.5, "eye_open": 0.5, "lid_droop": 0.4,
        "outfit": {"tops": [{"type": "coverall", "sleeve": 0.93, "hem": -0.06, "collar": True, "neck_front": 0.03, "torn": 0.2,
                             "pockets": [{"side": "L", "x": 0.07, "y": 0.12, "w": 0.12, "h": 0.14}],
                             "tears": [{"at": "fa", "side": "L", "t": 0.45, "dir": [0, 0, 1], "r": 0.03}]},
                            {"type": "hivis", "sleeve": 0.0, "armhole": 0.02, "hem": -0.05, "neck_front": 0.08, "torn": 0.15,
                             "thickness": 0.016, "flare": 0.008,
                             "trim": {"bands": [0.08, 0.27], "braces": 0.072, "width": 0.05}}],
                   "pants": {"type": "coverall", "waist": 0.12, "torn": 0.2, "length": 0.97,
                             "trim": {"leg_bands": [0.80], "width": 0.05}}},
        "boots": {"L": True, "R": True, "height": 0.17},
        "hair": {"style": "short", "hairline": 0.05, "patchy": 0.4},
        "hat": {"type": "hardhat", "tilt": 6.0},
        "remap": {"hardhat": "hardhat_white"},
        "wounds": [{"at": "neck", "side": "R", "t": 0.35, "dir": [-1.0, 0.0, 0.3], "r": 0.022, "blood": 1.0,
                    "bloom_spec": {"filaments": 4, "shelves": 1, "lumps": 5}}],
        "bloom": [{"at": "ua", "side": "L", "t": 0.25, "dir": [1.0, 0.2, -0.3], "r": 0.022, "filaments": 3, "shelves": 1}],
        "blood": 0.55, "grime": 0.6,
    },
    # Cordon crew, second shift: a woman in safety-orange coveralls, the vest torn half off, a yellow
    # hard hat pushed back, a radio lanyard; the Bloom out of her shoulder.
    "hollow_cordon_b": {
        "seed": 922, "height": 1.67, "sex": "f", "build": 0.3, "hunch": 0.25, "head_forward": 0.3, "head_tilt": 7.0,
        "limp_side": "L", "claw": 0.55, "jaw_drop": 9.0, "mouth_open": 0.4, "eye_open": 0.7, "lid_droop": 0.2,
        "outfit": {"tops": [{"type": "coverall", "sleeve": 0.75, "hem": -0.06, "collar": True, "neck_front": 0.05, "torn": 0.3,
                             "rolled": {"L": True, "R": True},
                             "pockets": [{"side": "R", "x": 0.065, "y": 0.11, "w": 0.11, "h": 0.12}]},
                            {"type": "hivis", "sleeve": 0.0, "armhole": 0.025, "hem": -0.03, "neck_front": 0.09, "torn": 0.55,
                             "thickness": 0.016, "flare": 0.008, "open_front": 0.05,
                             "trim": {"bands": [0.08, 0.26], "braces": 0.07, "width": 0.05},
                             "tears": [{"at": "chest", "side": "L", "t": 0.5, "dir": [0.9, 0.0, 0.5], "r": 0.09}]}],
                   "pants": {"type": "coverall", "waist": 0.12, "torn": 0.3, "length": 0.96, "trim": {"leg_bands": [0.80], "width": 0.05}}},
        "boots": {"L": True, "R": True, "height": 0.15},
        "hair": {"style": "medium", "hairline": 0.055, "patchy": 0.3, "locks": 6, "length": 0.075},
        "hat": {"type": "hardhat", "tilt": -12.0},
        "remap": {"cloth_coverall": "cloth_coverall_orange"},
        "accessories": [{"kind": "lanyard"}],
        "bloom": [{"at": "chest", "side": "L", "t": 0.9, "dir": [0.8, 0.5, 0.2], "r": 0.03, "filaments": 4, "shelves": 2, "lumps": 6}],
        "wounds": [{"at": "fa", "side": "R", "t": 0.6, "dir": [0.0, 0.0, 1.0], "r": 0.018, "blood": 0.9, "bloom": False}],
        "blood": 0.5, "grime": 0.55,
    },
    # Clinic patient: a hospital gown open at the back, a wristband and an IV still taped into the
    # hand, a gauze head bandage soaked through, barefoot with bruised feet. Isolation-ward pallor.
    "hollow_patient_a": {
        "seed": 931, "height": 1.74, "sex": "m", "build": 0.2, "gaunt": 0.8, "hunch": 0.35, "head_forward": 0.35,
        "head_tilt": 9.0, "limp_side": "L", "claw": 0.6, "jaw_drop": 13.0, "mouth_open": 0.55, "eye_open": 0.85,
        "lid_droop": 0.1, "nose_rot": 0.0, "bruise": 1.3,
        "outfit": {"tops": [{"type": "hospital", "sleeve": 0.26, "hem": -0.30, "open_back": 0.08, "torn": 0.2,
                             "neck_drop": 0.012, "neck_front": 0.03, "flare": 0.02}]},
        "boots": {},
        "hair": {"style": "short", "hairline": 0.06, "patchy": 0.6},
        "hat": {"type": "bandage", "height": 0.05},
        "accessories": [{"kind": "wristband", "side": "L"}, {"kind": "iv", "side": "R"}],
        "bloom": [{"at": "neck", "side": "R", "t": 0.4, "dir": [0.8, 0.0, -0.5], "r": 0.022, "filaments": 4, "shelves": 1}],
        "blood": 0.4, "grime": 0.3,
    },
    # Clinic patient: a woman in a gown and a restraint cuff she tore loose from the cot, long hair
    # matted, the Bloom spreading from her collarbone.
    "hollow_patient_b": {
        "seed": 942, "height": 1.62, "sex": "f", "build": 0.25, "gaunt": 0.7, "hunch": 0.2, "head_forward": 0.25,
        "head_tilt": -11.0, "limp_side": "R", "claw": 0.5, "jaw_drop": 8.0, "mouth_open": 0.35, "eye_open": 0.6,
        "lid_droop": 0.5, "bruise": 1.2,
        "outfit": {"tops": [{"type": "hospital", "sleeve": 0.24, "hem": -0.32, "open_back": 0.07, "torn": 0.35,
                             "neck_drop": 0.01, "neck_front": 0.025, "flare": 0.022, "seed_off": 3.0}]},
        "boots": {},
        "hair": {"style": "long", "hairline": 0.055, "patchy": 0.35, "locks": 12, "length": 0.095},
        "accessories": [{"kind": "wristband", "side": "R"}],
        "remap": {},
        "wounds": [{"at": "chest", "side": "L", "t": 0.85, "dir": [0.4, 0.3, 1.0], "r": 0.02, "blood": 0.8,
                    "bloom_spec": {"filaments": 5, "shelves": 2, "lumps": 6}}],
        "blood": 0.45, "grime": 0.3,
    },
    # Clinic nurse: teal scrubs, a lanyard with her ID, soft shoes; bitten on the forearm on the
    # night the ward woke.
    "hollow_nurse_a": {
        "seed": 951, "height": 1.66, "sex": "f", "build": 0.35, "hunch": 0.2, "head_forward": 0.3, "head_tilt": 5.0,
        "limp_side": "L", "claw": 0.45, "jaw_drop": 10.0, "mouth_open": 0.45, "eye_open": 0.65, "lid_droop": 0.3,
        "outfit": {"tops": [{"type": "scrubs", "sleeve": 0.32, "hem": -0.08, "neck_front": 0.085, "torn": 0.15,
                             "pockets": [{"side": "L", "x": 0.07, "y": 0.10, "w": 0.10, "h": 0.10, "flap": False}]}],
                   "pants": {"type": "scrubs", "belt": False, "torn": 0.1, "length": 0.98}},
        "boots": {"L": True, "R": True, "height": 0.07},
        "remap": {"leather_boot": "leather_shoe"},
        "hair": {"style": "medium", "hairline": 0.055, "patchy": 0.2, "locks": 5, "length": 0.06},
        "accessories": [{"kind": "lanyard"}],
        "wounds": [{"at": "fa", "side": "L", "t": 0.45, "dir": [0.3, 0.0, 1.0], "r": 0.024, "blood": 1.0,
                    "bloom_spec": {"filaments": 3, "shelves": 1, "lumps": 5}}],
        "blood": 0.6, "grime": 0.3,
    },
    # St. Ansel's: an old man in his Sunday best - white shirt buttoned to the collar under a wool
    # vest, a burgundy tie, pressed charcoal slacks, polished shoes. Balding, grey.
    "hollow_church_a": {
        "seed": 961, "height": 1.72, "sex": "m", "build": 0.4, "gaunt": 0.6, "hunch": 0.45, "head_forward": 0.4,
        "head_tilt": -4.0, "limp_side": "R", "claw": 0.5, "jaw_drop": 9.0, "mouth_open": 0.4, "eye_open": 0.45,
        "lid_droop": 0.6, "brow": 0.7,
        "outfit": {"tops": [{"type": "shirt", "sleeve": 1.0, "hem": 0.05, "tucked": True, "collar": True, "collar_open": 18,
                             "neck_front": 0.015, "buttons": 7, "torn": 0.1},
                            {"type": "wool", "sleeve": 0.0, "armhole": 0.02, "hem": 0.0, "neck_front": 0.10, "thickness": 0.010,
                             "flare": 0.002, "buttons": 4, "torn": 0.1, "tucked": True}],
                   "pants": {"type": "wool", "belt": True, "torn": 0.1, "length": 1.0}},
        "tie": {"bottom": 0.07, "loose": 0.4},
        "boots": {"L": True, "R": True, "height": 0.065},
        "remap": {"leather_boot": "leather_shoe"},
        "hair": {"style": "balding", "hairline": 0.02, "bald": 0.85, "patchy": 0.2},
        "wounds": [{"at": "neck", "side": "L", "t": 0.3, "dir": [1.0, 0.0, 0.2], "r": 0.02, "blood": 1.0,
                    "bloom_spec": {"filaments": 4, "shelves": 1, "lumps": 5}}],
        "blood": 0.55, "grime": 0.2,
    },
    # St. Ansel's: a woman in a floral Sunday dress under a mustard cardigan, a string of pearls,
    # low shoes, her hair pinned up and coming loose.
    "hollow_church_b": {
        "seed": 972, "height": 1.63, "sex": "f", "build": 0.4, "hunch": 0.3, "head_forward": 0.3, "head_tilt": 8.0,
        "limp_side": "L", "claw": 0.45, "jaw_drop": 7.0, "mouth_open": 0.3, "eye_open": 0.55, "lid_droop": 0.4,
        "outfit": {"tops": [{"type": "dress", "sleeve": 0.45, "hem": -0.40, "neck_front": 0.035, "flare": 0.035, "torn": 0.15},
                            {"type": "knit", "sleeve": 0.85, "hem": -0.12, "open_front": 0.06, "thickness": 0.013, "flare": 0.012,
                             "neck_front": 0.09, "torn": 0.2, "placket": False}]},
        "boots": {"L": True, "R": True, "height": 0.06},
        "remap": {"leather_boot": "leather_shoe"},
        "hair": {"style": "medium", "hairline": 0.05, "patchy": 0.2, "locks": 7, "length": 0.07},
        "accessories": [{"kind": "necklace", "beads": "pearl"}],
        "wounds": [{"at": "ua", "side": "R", "t": 0.3, "dir": [1.0, 0.0, 0.3], "r": 0.022, "blood": 0.9,
                    "bloom_spec": {"filaments": 4, "shelves": 1, "lumps": 5}}],
        "blood": 0.5, "grime": 0.25,
    },
    # Timber crew: a faller in a green flannel and suspenders over his jeans, a yellow hard hat,
    # caulk boots to the shin; a deep gash across the back where the Bloom came out.
    "hollow_logger_b": {
        "seed": 981, "height": 1.84, "sex": "m", "build": 0.55, "hunch": 0.3, "head_forward": 0.3, "head_tilt": 6.0,
        "limp_side": "R", "claw": 0.6, "jaw_drop": 12.0, "mouth_open": 0.5, "eye_open": 0.5, "lid_droop": 0.5, "brow": 0.8,
        "outfit": {"tops": [{"type": "flannel", "sleeve": 0.80, "hem": 0.02, "tucked": True, "collar": True, "neck_front": 0.06,
                             "buttons": 6, "torn": 0.3, "rolled": {"L": True, "R": True},
                             "pockets": [{"side": "L", "x": 0.068, "y": 0.13, "w": 0.11, "h": 0.12},
                                         {"side": "R", "x": 0.068, "y": 0.13, "w": 0.11, "h": 0.12}],
                             "tears": [{"at": "chest", "side": "R", "t": 0.5, "dir": [0.2, 0.0, -1.0], "r": 0.07}]}],
                   "pants": {"type": "denim", "belt": False, "torn": 0.3, "waist": 0.09}},
        "straps": [{"type": "leather", "x": 0.068, "width": 0.032, "waist": 0.07}],
        "boots": {"L": True, "R": True, "height": 0.22},
        "hair": {"style": "short", "hairline": 0.05, "patchy": 0.3},
        "hat": {"type": "hardhat", "tilt": 3.0},
        "remap": {"cloth_flannel": "cloth_flannel_green"},
        "wounds": [{"at": "chest", "side": "R", "t": 0.5, "dir": [0.2, 0.0, -1.0], "r": 0.04, "blood": 1.0, "depth": 0.9,
                    "bloom_spec": {"filaments": 6, "shelves": 3, "lumps": 8}}],
        "blood": 0.6, "grime": 0.65,
    },
    # Hunter: a red and black buffalo-check wool coat with big pockets, a blaze-orange cap, canvas
    # trousers and boots. Hunting season never ended.
    "hollow_hunter_a": {
        "seed": 991, "height": 1.80, "sex": "m", "build": 0.5, "hunch": 0.3, "head_forward": 0.35, "head_tilt": -6.0,
        "limp_side": "L", "claw": 0.55, "jaw_drop": 11.0, "mouth_open": 0.5, "eye_open": 0.55, "lid_droop": 0.4,
        "nose_rot": 0.3,
        "outfit": {"tops": [{"type": "tshirt", "sleeve": 0.4, "hem": -0.05, "torn": 0.2, "neck_front": 0.02, "seed_off": 2.0},
                            # With a 5 cm neckline, a 10 mm coat and a 5 mm flare, decimation kept ~2k
                            # of the torso's triangles round the big collar and left the T-shirt in the
                            # open front as facets up to 40 cm across. hollow_c's jacket proportions
                            # (3 cm, the default thickness, 12 mm) mesh evenly (edges under 12 cm).
                            {"type": "hunter", "sleeve": 0.98, "hem": -0.17, "collar": True, "open_front": 0.04, "torn": 0.2,
                             "flare": 0.012, "neck_front": 0.03,
                             "pockets": [{"side": "L", "x": 0.075, "y": 0.11, "w": 0.12, "h": 0.12},
                                         {"side": "R", "x": 0.075, "y": 0.11, "w": 0.12, "h": 0.12}]}],
                   "pants": {"type": "canvas", "belt": True, "torn": 0.25}},
        "boots": {"L": True, "R": True, "height": 0.20},
        "hair": {"style": "short", "hairline": 0.05, "patchy": 0.4},
        "hat": {"type": "cap", "tilt": 4.0},
        "wounds": [{"at": "th", "side": "R", "t": 0.4, "dir": [0.5, 0.0, 1.0], "r": 0.03, "blood": 1.0,
                    "bloom_spec": {"filaments": 3, "shelves": 1, "lumps": 5}}],
        "blood": 0.55, "grime": 0.6,
    },
    # The Ashen, taken in the high timber despite the ash: a hide wrap laced down the side under a
    # shaggy fur mantle, hide leggings, bare feet; lichen-ash over all of him, a painted band across
    # the eyes, a handprint over the heart, rings round the forearms; a cord of bone charms.
    "hollow_ashen_a": {
        "seed": 1001, "height": 1.78, "sex": "m", "build": 0.35, "gaunt": 0.7, "hunch": 0.35, "head_forward": 0.4,
        "head_tilt": 5.0, "limp_side": "R", "claw": 0.7, "jaw_drop": 12.0, "mouth_open": 0.55, "eye_open": 0.7,
        "lid_droop": 0.3, "brow": 0.9,
        "outfit": {"tops": [{"type": "hide", "sleeve_L": 0.35, "sleeve_R": 0.0, "hem": -0.16, "torn": 0.45, "neck_front": 0.07,
                             "flare": 0.016, "placket": False}],
                   "pants": {"type": "hide", "belt": False, "torn": 0.4, "length": 0.86}},
        "mantle": {"low": 0.20, "reach": 0.22},
        "boots": {},
        "hair": {"style": "long", "hairline": 0.06, "patchy": 0.5, "locks": 10, "length": 0.09},
        "remap": {"skin_hollow": "skin_ashen"},
        "paint": [{"kind": "eye_band", "y": 0.012, "width": 0.011},
                  {"kind": "hand", "at": "chest", "pos": [0.05, 0.14, 0.11], "angle": -12.0},
                  {"kind": "arm_rings", "side": "L", "seg": "fa", "ts": [0.25, 0.4, 0.55], "width": 0.012},
                  {"kind": "arm_rings", "side": "R", "seg": "ua", "ts": [0.5, 0.65], "width": 0.014}],
        "accessories": [{"kind": "necklace", "beads": "bone"}],
        "wounds": [{"at": "spine", "side": "L", "t": 0.4, "dir": [0.8, 0.0, 0.5], "r": 0.03, "blood": 0.8,
                    "bloom_spec": {"filaments": 5, "shelves": 2, "lumps": 7}}],
        "blood": 0.4, "grime": 0.7,
    },
    # Ashen Lurcher: starved down to cords and bone, nearly naked - a hide breechcloth, a strip of fur
    # over one shoulder, chin stripes and ash; long-limbed and fast.
    "lurcher_ashen_a": {
        "seed": 1011, "height": 1.86, "sex": "m", "build": 0.05, "gaunt": 1.0, "hunch": 0.7, "head_forward": 0.55,
        "arm_scale": 1.08, "leg_scale": 1.04, "claw": 0.95, "jaw_drop": 17.0, "mouth_open": 0.85, "eye_open": 0.95,
        "lid_droop": 0.0, "head_tilt": -12.0, "limp_side": "L", "wall_eye": 7.0, "brow": 1.0, "nose_rot": 0.5,
        "outfit": {"pants": {"type": "hide", "belt": False, "torn": 0.6, "length_L": 0.42, "length_R": 0.36, "waist": 0.05}},
        "mantle": {"low": 0.12, "reach": 0.16},
        "boots": {},
        "hair": {"style": "long", "hairline": 0.07, "patchy": 0.75, "locks": 8, "length": 0.09},
        "remap": {"skin_hollow": "skin_ashen"},
        "paint": [{"kind": "chin_stripes", "xs": [-0.018, 0.0, 0.018], "width": 0.008},
                  {"kind": "eye_band", "y": 0.014, "width": 0.009},
                  {"kind": "arm_rings", "side": "R", "seg": "fa", "ts": [0.3, 0.45], "width": 0.012}],
        "accessories": [{"kind": "necklace", "beads": "bone"}],
        "bloom": [{"at": "chest", "side": "R", "t": 0.75, "dir": [0.4, 0.0, -1.0], "r": 0.04, "filaments": 5, "shelves": 3, "lumps": 8}],
        "blood": 0.6, "grime": 0.75, "seg_tris": {"body_torso": 2600},
    },
    # --- Special Hollowed (docs/DESIGN.md §6) ---------------------------------------------------
    # Blister: bloated and tight with translucent spore pustules in clusters over the chest, back,
    # shoulders, neck and face (they burst when it dies), a swollen throat sac it spits from;
    # a torn hospital gown. Silhouette at 40 m: a swollen, lumpy pear with a bulging throat.
    "blister_a": {
        "seed": 811, "height": 1.70, "sex": "f", "build": 1.0, "belly": 2.8, "hunch": 0.30, "head_forward": 0.25,
        "jaw_drop": 16.0, "mouth_open": 0.75, "eye_open": 0.35, "lid_droop": 0.8, "claw": 0.3, "head_tilt": -6.0,
        "limp_side": "R", "throat_sac": {"size": 2.2, "bloom_lumps": 5}, "neck_cut": 0.86,
        "outfit": {"tops": [{"type": "hospital", "sleeve": 0.25, "hem": -0.20, "torn": 0.7, "neck_front": 0.08, "flare": 0.03,
                             "tears": [{"at": "chest", "side": "L", "t": 0.6, "dir": [0.6, 0.2, 0.8], "r": 0.10},
                                       {"at": "spine", "side": "R", "t": 0.7, "dir": [0.4, 0.0, -1.0], "r": 0.12}]}]},
        "boots": {"L": False, "R": False},
        "hair": {"style": "balding", "hairline": 0.03, "bald": 0.7, "patchy": 0.6},
        "pustules": {"sites": [
            {"at": "chest", "side": "L", "t": 0.6, "dir": [0.6, 0.2, 0.8], "count": 9, "size": 0.026, "spread": 0.7},
            {"at": "spine", "side": "R", "t": 0.7, "dir": [0.4, 0.0, -1.0], "count": 10, "size": 0.030, "spread": 0.8},
            {"at": "spine", "side": "L", "t": 0.3, "dir": [0.9, 0.0, 0.4], "count": 6, "size": 0.024},
            {"at": "ua", "side": "R", "t": 0.6, "dir": [1.0, 0.2, 0.0], "count": 6, "size": 0.022},
            {"at": "ua", "side": "L", "t": 0.5, "dir": [1.0, 0.0, 0.3], "count": 5, "size": 0.020},
            {"at": "head", "side": "R", "dir": [0.8, -0.2, 0.5], "count": 4, "size": 0.016, "spread": 0.4},
            {"at": "neck", "side": "L", "t": 0.5, "dir": [0.7, 0.0, 0.6], "count": 4, "size": 0.020},
            {"at": "th", "side": "L", "t": 0.55, "dir": [0.5, 0.0, 1.0], "count": 5, "size": 0.024},
            {"at": "sh", "side": "R", "t": 0.3, "dir": [0.6, 0.0, 0.8], "count": 4, "size": 0.020}]},
        "bloom": [{"at": "spine", "side": "L", "t": 0.6, "dir": [0.0, 0.0, -1.0], "r": 0.05, "lumps": 5, "filaments": 3, "shelves": 0}],
        "blood": 0.4, "grime": 0.7, "bruise": 1.2,
    },
    # Husk: grown into its riot gear and whatever debris it lay under: a chest plate, pauldrons and
    # guards, torn sheet steel over the back, belly and thighs, hard fungal shell at the hips and
    # the small of the back, all overlapping like lamellar armour and fused at the edges with
    # growth; the head bare and soft. Silhouette at 40 m: broad, plated, a small bare head.
    "husk_a": {
        "seed": 822, "height": 1.82, "sex": "m", "build": 0.6, "hunch": 0.2, "head_forward": 0.25, "brow": 0.8,
        "jaw_drop": 6.0, "mouth_open": 0.3, "eye_open": 0.5, "lid_droop": 0.5, "claw": 0.45, "head_tilt": 4.0,
        "outfit": {"tops": [{"type": "jacket", "sleeve": 0.85, "hem": -0.08, "torn": 0.45, "collar": True, "neck_front": 0.04}],
                   "pants": {"type": "denim", "belt": True, "torn": 0.35}},
        "boots": {"L": True, "R": True, "height": 0.18},
        "hair": {"style": "short", "hairline": 0.06, "patchy": 0.5},
        "armour": [
            # rows from the top down, each tucking under the one above
            {"at": "chest", "side": "L", "t": 0.62, "dir": [0.0, 0.1, 1.0], "w": 0.33, "h": 0.19, "kind": "riot", "tilt": 0.014},
            {"at": "chest", "side": "L", "t": 0.96, "dir": [0.8, 0.6, 0.05], "w": 0.19, "h": 0.15, "kind": "riot", "tilt": 0.010},
            {"at": "chest", "side": "R", "t": 0.96, "dir": [0.8, 0.6, 0.05], "w": 0.19, "h": 0.15, "kind": "riot", "tilt": 0.010},
            {"at": "ua", "side": "L", "t": 0.22, "dir": [1.0, 0.0, 0.15], "w": 0.14, "h": 0.11, "kind": "riot", "tilt": 0.008},
            {"at": "ua", "side": "R", "t": 0.22, "dir": [1.0, 0.0, 0.15], "w": 0.14, "h": 0.11, "kind": "riot", "tilt": 0.008},
            {"at": "spine", "side": "L", "t": 1.0, "dir": [0.45, 0.0, 1.0], "w": 0.17, "h": 0.17, "kind": "metal", "tilt": 0.012},
            {"at": "spine", "side": "R", "t": 0.95, "dir": [0.45, -0.05, 1.0], "w": 0.16, "h": 0.17, "kind": "metal", "tilt": 0.012},
            {"at": "spine", "side": "L", "t": 0.30, "dir": [0.0, 0.0, 1.0], "w": 0.26, "h": 0.12, "kind": "shell", "tilt": 0.008},
            {"at": "chest", "side": "L", "t": 0.55, "dir": [0.05, 0.0, -1.0], "w": 0.34, "h": 0.22, "kind": "metal", "tilt": 0.014},
            {"at": "spine", "side": "L", "t": 0.65, "dir": [0.0, 0.0, -1.0], "w": 0.28, "h": 0.14, "kind": "shell", "tilt": 0.010},
            {"at": "hips", "side": "L", "t": 0.30, "dir": [1.0, 0.0, 0.25], "w": 0.13, "h": 0.12, "kind": "shell"},
            {"at": "hips", "side": "R", "t": 0.30, "dir": [1.0, 0.0, 0.25], "w": 0.13, "h": 0.12, "kind": "shell"},
            {"at": "fa", "side": "L", "t": 0.45, "dir": [0.8, 0.0, 0.6], "w": 0.11, "h": 0.18, "kind": "riot"},
            {"at": "fa", "side": "R", "t": 0.45, "dir": [0.8, 0.0, 0.6], "w": 0.11, "h": 0.18, "kind": "riot"},
            {"at": "th", "side": "L", "t": 0.45, "dir": [0.3, 0.0, 1.0], "w": 0.12, "h": 0.13, "kind": "metal", "standoff": 0.006, "tilt": 0.006},
            {"at": "th", "side": "R", "t": 0.50, "dir": [0.3, 0.0, 1.0], "w": 0.11, "h": 0.12, "kind": "metal", "standoff": 0.006, "tilt": 0.006},
            {"at": "sh", "side": "L", "t": 0.40, "dir": [0.0, 0.0, 1.0], "w": 0.11, "h": 0.25, "kind": "riot"},
            {"at": "sh", "side": "R", "t": 0.40, "dir": [0.0, 0.0, 1.0], "w": 0.11, "h": 0.25, "kind": "riot"}],
        "bloom": [{"at": "chest", "side": "R", "t": 0.3, "dir": [0.9, 0.0, 0.3], "r": 0.04, "lumps": 6, "filaments": 2, "shelves": 2, "shelf_size": 0.03},
                  {"at": "neck", "side": "L", "t": 0.3, "dir": [0.6, 0.0, -0.8], "r": 0.03, "lumps": 5, "filaments": 3, "shelves": 1}],
        "blood": 0.3, "grime": 0.8,
    },
    # Rammer: a 2.3 m Bloom-thickened hulk, its bulk built into the frame (mass): a yoke of shoulders
    # and a knotted hump the head hangs from, slab forearms, a gut; torn work clothes split by the
    # growth. Silhouette at 40 m: a low head under a wide hump, arms to the knees.
    "rammer_a": {
        "seed": 833, "height": 2.30, "sex": "m", "build": 1.0, "mass": 1.0, "belly": 0.7, "hunch": 0.62,
        "head_forward": 0.6, "brow": 1.0, "arm_scale": 1.22, "shoulder_drop": 0.2, "jaw_drop": 12.0, "mouth_open": 0.6,
        "eye_open": 0.3, "lid_droop": 0.7, "claw": 0.8, "head_tilt": 6.0, "limp_side": "L", "gaunt": 0.0,
        "outfit": {"tops": [{"type": "tshirt", "sleeve": 0.2, "hem": 0.05, "torn": 0.95, "neck_front": 0.08}],
                   "pants": {"type": "coverall", "belt": False, "torn": 0.75, "length": 0.78}},
        "boots": {"L": False, "R": False},
        "hair": {"style": "stubble", "hairline": 0.04, "patchy": 0.7},
        "bloom": [{"at": "chest", "side": "L", "t": 0.8, "dir": [0.3, 0.5, -1.0], "r": 0.11, "lumps": 16, "filaments": 4, "shelves": 5, "shelf_size": 0.06},
                  {"at": "ua", "side": "R", "t": 0.2, "dir": [1.0, 0.3, 0.0], "r": 0.10, "lumps": 14, "filaments": 2, "shelves": 3, "shelf_size": 0.05},
                  {"at": "ua", "side": "L", "t": 0.3, "dir": [1.0, 0.1, -0.2], "r": 0.09, "lumps": 12, "filaments": 2, "shelves": 2, "shelf_size": 0.05},
                  {"at": "fa", "side": "R", "t": 0.6, "dir": [0.0, 0.0, 1.0], "r": 0.07, "lumps": 10, "filaments": 1, "shelves": 0},
                  {"at": "neck", "side": "R", "t": 0.5, "dir": [0.5, 0.3, -0.8], "r": 0.08, "lumps": 10, "filaments": 2, "shelves": 0}],
        "blood": 0.5, "grime": 0.75,
        "seg_tris": {"body_torso": 4400, "body_upper_arm.L": 640, "body_upper_arm.R": 640, "body_forearm.L": 1350,
                     "body_forearm.R": 1350, "body_thigh.L": 640, "body_thigh.R": 640, "body_shin.L": 760, "body_shin.R": 760},
    },
}


# --- The living Ashen (ADR-0048) -------------------------------------------------------------
# Raiders and scouts of the high-timber tribes: living people, built by generators/character_living.py
# (the Hollowed pipeline with the infection left out: no growths, wounds, Bloom or blood, the mouth
# closed) with the Hollowed's action set so the Enemy plays them. Upright and alert: no hunch, no
# claw, eyes open, the head carried level. Skin is living skin under lichen-ash (skin_ashen_living:
# the skin shader's ash dust and paint with the infection switched off), clear eyes; hide, fur and
# bone over it. Their joint skirts and stump caps (and the parting of the lips) are ashen_inner, a
# darker blood than the Hollowed's gore. The Hollowed head is wide-eyed: a low eye_open and a heavy lid
# give the living a hard squint instead (TD-170).
# Ash-grey from scalp to heel (skin_ashen_living: a grey base under heavy lichen-ash dust, charcoal paint),
# so they read at 30 m as grey figures; darker worn hide (ashen_hide_dark) and wrapped shins: the
# "boots" are raised to the knee and drawn as hide strip wraps (ashen_wrap), as is the belt.
# The raiders carry a hafted stone axe in the right fist ("weapon": a rigid prop that
# character_living joins into body_forearm.R on hand.R); the scout goes empty-handed (TD-187).
ASHEN_LIVING_REMAP = {"skin_hollow": "skin_ashen_living", "eyes_hollow": "npc_eye", "hide": "ashen_hide_dark",
                     "leather_boot": "ashen_wrap",
                     # the closed lips' parting line and the stump caps: dark blood, not the Hollowed's wet red
                     "gore": "ashen_inner"}
_LIVING_FACE = {"hunch": 0.0, "head_forward": 0.0, "head_tilt": 0.0, "gaze_down": 2.0, "claw": 0.08, "jaw_drop": 0.0,
                "mouth_open": 0.0, "eye_open": 0.45, "teeth_missing": 0.0, "gum_recede": 0.0, "bruise": 0.0,
                "blood": 0.0, "arm_raise": 0.0, "wall_eye": 0.0}
LIVING = {
    # Raider: a big, broad man in his prime; a sleeveless hide jerkin under a heavy wolf-grey fur
    # mantle, hide leggings and wrapped hide boots; a black lichen band across the eyes ear to ear,
    # a handprint over the heart, rings up both arms; a cord of bone charms and a short beard.
    "ashen_raider_a": {
        "seed": 1101, "height": 1.86, "sex": "m", "build": 0.9, "gaunt": 0.15, **_LIVING_FACE, "brow": 0.85,
        "lid_droop": 0.45, "nose_rot": 0.2, "limp_side": "R",
        "outfit": {"tops": [{"type": "hide", "sleeve": 0.0, "hem": -0.13, "torn": 0.1, "neck_front": 0.06,
                             "flare": 0.014, "placket": False, "armhole": 0.01}],
                   "pants": {"type": "hide", "belt": True, "torn": 0.15, "length": 0.97, "thickness": 0.0045}},
        "mantle": {"low": 0.25, "reach": 0.26},
        "boots": {"L": True, "R": True, "height": 0.36},
        "hair": {"style": "long", "hairline": 0.05, "patchy": 0.0, "locks": 12, "length": 0.11},
        "beard": {"thickness": 0.0035, "line": -0.028, "moustache": True},
        "remap": ASHEN_LIVING_REMAP,
        "paint": [{"kind": "eye_band", "y": 0.012, "width": 0.013},
                  {"kind": "hand", "at": "chest", "pos": [0.055, 0.15, 0.12], "angle": -10.0},
                  {"kind": "arm_rings", "side": "L", "seg": "ua", "ts": [0.45, 0.6, 0.75], "width": 0.022},
                  {"kind": "arm_rings", "side": "R", "seg": "ua", "ts": [0.45, 0.6, 0.75], "width": 0.022},
                  {"kind": "arm_rings", "side": "L", "seg": "fa", "ts": [0.3, 0.45], "width": 0.02},
                  {"kind": "arm_rings", "side": "R", "seg": "fa", "ts": [0.3, 0.45], "width": 0.02}],
        "accessories": [{"kind": "necklace", "beads": "bone"}],
        "weapon": "stone_axe",
        "grime": 0.35,
    },
    # Raider: a woman, wiry and hard; a long-sleeved hide tunic belted at the hip, a narrow fur
    # mantle, hide leggings and wrap boots; her hair long and thick, three chin stripes and a band
    # across the eyes, rings on the forearms; bone charms at her throat and a cord harness crossing
    # her back (where she slings her spears).
    "ashen_raider_b": {
        "seed": 1102, "height": 1.71, "sex": "f", "build": 0.45, "gaunt": 0.0, **_LIVING_FACE, "brow": 0.7,
        "lid_droop": 0.4, "limp_side": "L",
        "outfit": {"tops": [{"type": "hide", "sleeve": 0.82, "hem": -0.22, "torn": 0.12, "neck_front": 0.05,
                             "flare": 0.02, "placket": False}],
                   "pants": {"type": "hide", "belt": True, "torn": 0.15, "length": 0.97, "thickness": 0.0045}},
        "mantle": {"low": 0.16, "reach": 0.19},
        "straps": [{"type": "cord", "x": 0.06, "width": 0.018, "waist": 0.16}],
        "boots": {"L": True, "R": True, "height": 0.34},
        "hair": {"style": "long", "hairline": 0.06, "patchy": 0.0, "locks": 14, "length": 0.12},
        "remap": ASHEN_LIVING_REMAP,
        "paint": [{"kind": "eye_band", "y": 0.014, "width": 0.013},
                  {"kind": "chin_stripes", "xs": [-0.017, 0.0, 0.017], "width": 0.011},
                  {"kind": "arm_rings", "side": "L", "seg": "fa", "ts": [0.7, 0.8], "width": 0.010},
                  {"kind": "arm_rings", "side": "R", "seg": "fa", "ts": [0.7, 0.8], "width": 0.010}],
        "accessories": [{"kind": "necklace", "beads": "bone"}],
        "weapon": "stone_axe",
        "grime": 0.3,
    },
    # Scout: young, lean and long-legged, built to run; bare-chested under a short fur mantle, hide
    # leggings and wrap boots, almost all of him painted: the eye band, chin stripes, a handprint on
    # the chest and one on the back, rings from shoulder to wrist; his hair tied short.
    "ashen_scout_a": {
        "seed": 1103, "height": 1.77, "sex": "m", "build": 0.12, "gaunt": 0.4, **_LIVING_FACE, "brow": 0.8,
        "lid_droop": 0.4, "leg_scale": 1.03, "limp_side": "R",
        "outfit": {"pants": {"type": "hide", "belt": True, "torn": 0.15, "length": 0.97, "waist": 0.06, "thickness": 0.0045}},
        "mantle": {"low": 0.15, "reach": 0.19},
        "boots": {"L": True, "R": True, "height": 0.34},
        "hair": {"style": "short", "hairline": 0.06, "patchy": 0.0},
        "remap": ASHEN_LIVING_REMAP,
        "paint": [{"kind": "eye_band", "y": 0.010, "width": 0.016},
                  {"kind": "chin_stripes", "xs": [-0.021, -0.007, 0.007, 0.021], "width": 0.009},
                  {"kind": "hand", "at": "chest", "pos": [-0.05, 0.02, 0.12], "angle": 14.0},
                  {"kind": "hand", "at": "spine", "pos": [0.03, 0.10, -0.11], "angle": 8.0},
                  {"kind": "arm_rings", "side": "L", "seg": "ua", "ts": [0.3, 0.45, 0.6, 0.75], "width": 0.02},
                  {"kind": "arm_rings", "side": "R", "seg": "ua", "ts": [0.3, 0.45, 0.6, 0.75], "width": 0.02},
                  {"kind": "arm_rings", "side": "L", "seg": "fa", "ts": [0.25, 0.4, 0.55, 0.7], "width": 0.018},
                  {"kind": "arm_rings", "side": "R", "seg": "fa", "ts": [0.25, 0.4, 0.55, 0.7], "width": 0.018}],
        "accessories": [{"kind": "necklace", "beads": "bone"}],
        "grime": 0.4,
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
    for key, p in LIVING.items():
        params = {"name": key, **p}
        rel = f"models/characters/{key}.glb"
        out.append(Task(name=f"model:characters/{key}", group="models", outputs=[rel],
                        sources=blender_sources("character_living"), params=params, blender="character_living",
                        imports={rel: {"type": "scene", "animation": True}}))
    rel = "models/characters/gibs.glb"
    out.append(Task(name="model:characters/gibs", group="models", outputs=[rel],
                    sources=blender_sources("character_gibs"), params={"name": "gibs", **BODIES["hollow_a"]},
                    blender="character_gibs", imports={rel: {"type": "scene"}}))
    rel = "models/characters/fp_arms.glb"
    out.append(Task(name="model:characters/fp_arms", group="models", outputs=[rel],
                    # The hold poses are baked into the arms' actions: a pose edit rebuilds them.
                    sources=blender_sources("character_fp_arms") + [GAME / "data" / "config" / "viewmodel.json"],
                    params={"name": "fp_arms", "seed": 808, "height": 1.78},
                    blender="character_fp_arms", imports={rel: {"type": "scene", "animation": True}}))
    return out
