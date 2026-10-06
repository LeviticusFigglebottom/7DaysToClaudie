"""Vegetation assets: trees (explicit LODs), stumps/logs/fallen logs, understory plants.

Atlas layouts come from textures/gen/vegetation.py (LAYOUTS) and are passed to the Blender
generators as params, so a layout change rebuilds both the atlas and the models that use it.
Model ids match game/data/vegetation/species.json.
"""
from __future__ import annotations

from ..core.registry import Task, blender_sources
from ..textures.gen.burn_fen import FEN
from ..textures.gen.riparian import RIPARIAN
from ..textures.gen.vegetation import LAYOUTS

# id: params (species-specific knobs; see generators/veg_tree.py)
TREES: dict[str, dict] = {
    "grey_fir_a": {"species": "fir", "seed": 1101, "height": 26.0, "dbh_r": 0.33, "crown_base": 0.36, "crown_r": 0.15, "lean": 1.0},
    "grey_fir_b": {"species": "fir", "seed": 1202, "height": 21.0, "dbh_r": 0.28, "crown_base": 0.3, "crown_r": 0.17, "lean": 2.0},
    "grey_fir_c": {"species": "fir", "seed": 1303, "height": 29.5, "dbh_r": 0.38, "crown_base": 0.44, "crown_r": 0.135, "lean": 0.5},
    "grey_fir_d": {"species": "fir", "seed": 1404, "height": 18.5, "dbh_r": 0.25, "crown_base": 0.26, "crown_r": 0.19, "lean": 2.5},
    "hollow_larch_a": {"species": "larch", "seed": 2101, "height": 24.0, "dbh_r": 0.3, "crown_base": 0.45, "crown_r": 0.125, "lean": 1.0},
    "hollow_larch_b": {"species": "larch", "seed": 2202, "height": 19.0, "dbh_r": 0.25, "crown_base": 0.4, "crown_r": 0.13, "lean": 2.0},
    "hollow_larch_c": {"species": "larch", "seed": 2303, "height": 26.0, "dbh_r": 0.33, "crown_base": 0.5, "crown_r": 0.115, "lean": 0.8},
    "paper_birch_a": {"species": "birch", "seed": 3101, "height": 15.0, "dbh_r": 0.13, "stems": 3, "crown_r": 0.2},
    "paper_birch_b": {"species": "birch", "seed": 3202, "height": 13.0, "dbh_r": 0.14, "stems": 2, "crown_r": 0.21},
    "paper_birch_c": {"species": "birch", "seed": 3303, "height": 15.8, "dbh_r": 0.16, "stems": 1, "crown_r": 0.18},
    "dead_snag_a": {"species": "snag", "seed": 4101, "height": 12.5, "dbh_r": 0.3, "full_height": 1.8, "lean": 2.5},
    "dead_snag_b": {"species": "snag", "seed": 4202, "height": 8.5, "dbh_r": 0.26, "full_height": 2.3, "lean": 4.0},
    # The fen's stunted trees (ADR-0041): tamarack (larch) and black spruce (a narrow fir spire),
    # starved on the peat: short, thin-crowned, low-limbed.
    "tamarack_a": {"species": "larch", "seed": 2411, "height": 9.0, "dbh_r": 0.13, "crown_base": 0.22, "crown_r": 0.11, "lean": 3.0, "density": 0.8},
    "tamarack_b": {"species": "larch", "seed": 2512, "height": 6.5, "dbh_r": 0.1, "crown_base": 0.18, "crown_r": 0.12, "lean": 4.5, "density": 0.7},
    "black_spruce_a": {"species": "fir", "seed": 1511, "height": 8.5, "dbh_r": 0.11, "crown_base": 0.08, "crown_r": 0.075, "lean": 2.0, "density": 1.0},
    "black_spruce_b": {"species": "fir", "seed": 1612, "height": 6.0, "dbh_r": 0.09, "crown_base": 0.06, "crown_r": 0.085, "lean": 3.5, "density": 0.9},
}

# Fire-killed snags of the burnt forest (generators/veg_burn.py): fir spikes and snapped firs, larch
# snapped and whole; one bark-shader material whose char layer covers the lower trunk.
BURNT_SNAGS: dict[str, dict] = {
    "burnt_snag_a": {"form": "fir", "seed": 9101, "height": 24.0, "dbh_r": 0.32, "top": "spike", "lean": 1.0},
    "burnt_snag_b": {"form": "fir", "seed": 9202, "height": 15.5, "dbh_r": 0.34, "full_height": 1.6, "top": "snapped", "lean": 2.0},
    "burnt_snag_c": {"form": "fir", "seed": 9303, "height": 19.0, "dbh_r": 0.26, "top": "spike", "lean": 2.5, "limbs": 0.7},
    "burnt_snag_d": {"form": "larch", "seed": 9404, "height": 13.0, "dbh_r": 0.28, "full_height": 1.7, "top": "snapped", "lean": 3.0},
    "burnt_snag_e": {"form": "larch", "seed": 9505, "height": 21.0, "dbh_r": 0.27, "top": "spike", "lean": 1.5},
}
# Fire-hollowed stumps (veg_burn kind stump): the heartwood burnt out of the broken trunk.
BURNT_STUMPS: dict[str, dict] = {
    "burnt_stump_a": {"kind": "stump", "seed": 9611, "height": 1.3, "radius": 0.36, "shell": 0.07, "mat": "burn_wood_char"},
    "burnt_stump_b": {"kind": "stump", "seed": 9712, "height": 0.8, "radius": 0.3, "shell": 0.06, "mat": "burn_wood_char"},
}


# Stumps, cut logs (physics objects, origin at the geometric centre) and fallen logs.
WOOD: dict[str, dict] = {
    "conifer_stump": {"kind": "stump", "seed": 5101, "radius": 0.36, "height": 0.62, "bark": "bark_grey_fir_static", "end": "wood_log_end"},
    "birch_stump": {"kind": "stump", "seed": 5202, "radius": 0.17, "height": 0.52, "bark": "bark_birch_static", "end": "wood_log_end_birch", "sides": 18, "splinter": 0.6, "roots": False},
    "log_conifer": {"kind": "log", "seed": 5301, "radius": 0.162, "length": 4.0, "bark": "bark_grey_fir_static", "end": "wood_log_end"},
    "log_larch": {"kind": "log", "seed": 5402, "radius": 0.162, "length": 4.0, "bark": "bark_larch_static", "end": "wood_log_end"},
    "log_birch": {"kind": "log", "seed": 5503, "radius": 0.162, "length": 4.0, "bark": "bark_birch_static", "end": "wood_log_end_birch"},
    "log_dead": {"kind": "log", "seed": 5604, "radius": 0.162, "length": 4.0, "bark": "bark_dead_static", "end": "wood_log_end_dead", "knots": 4},
    "fallen_log_a": {"kind": "fallen", "seed": 5701, "radius": 0.42, "length": 6.6, "sink": 0.3, "bark": "bark_fallen", "end": "wood_log_end_rotten"},
    "fallen_log_b": {"kind": "fallen", "seed": 5802, "radius": 0.36, "length": 5.3, "sink": 0.26, "bark": "bark_fallen", "end": "wood_log_end_rotten"},
    # Stripped, bleached logs the river left on its gravel bars (moss mask unused by the material).
    "driftwood_a": {"kind": "fallen", "seed": 5903, "radius": 0.27, "length": 4.8, "sink": 0.1, "bark": "driftwood", "end": "wood_log_end_dead"},
    "driftwood_b": {"kind": "fallen", "seed": 6004, "radius": 0.2, "length": 3.3, "sink": 0.08, "bark": "driftwood", "end": "wood_log_end_dead"},
    # Burnt forest (ADR-0041): charred windfall, hollowed and torn at the ends; the stump and log a
    # felled burnt snag leaves.
    "fallen_burnt_a": {"kind": "fallen", "seed": 9801, "radius": 0.38, "length": 7.4, "sink": 0.18, "bark": "burn_wood_char", "end": "wood_log_end_charred"},
    "fallen_burnt_b": {"kind": "fallen", "seed": 9902, "radius": 0.3, "length": 4.6, "sink": 0.14, "bark": "burn_wood_char", "end": "wood_log_end_charred"},
    "burnt_cut_stump": {"kind": "stump", "seed": 9951, "radius": 0.34, "height": 0.6, "bark": "burn_wood_char", "end": "wood_log_end_dead"},
    "log_burnt": {"kind": "log", "seed": 9961, "radius": 0.162, "length": 4.0, "bark": "burn_wood_char", "end": "wood_log_end_dead", "knots": 3},
}


def _wood_tasks() -> list[Task]:
    out = []
    for wid, p in WOOD.items():
        out.append(Task(name=f"model:trees/{wid}", group="models", outputs=[f"models/trees/{wid}.glb"],
                        sources=blender_sources("veg_wood"), params={"name": wid, **p}, blender="veg_wood"))
    return out


_FIR = LAYOUTS["foliage_fir"]
_PL = LAYOUTS["plants"]
# Fern-built plants of the fen atlas: the builder's frond and young regions mapped onto it.
_BRACKEN = {"frond_a": FEN["bracken_a"], "frond_b": FEN["bracken_b"], "frond_c": FEN["bracken_a"], "young": FEN["bracken_young"]}
# Skunk cabbage in late season: three leaf shapes and no spathe (FEN["skunk_young"] is spring's).
_SKUNK = {"frond_a": FEN["skunk_a"], "frond_b": FEN["skunk_b"], "frond_c": FEN["skunk_c"], "young": FEN["skunk_c"]}
# Understory plants (models/plants/). lods=2 ships an explicit cheaper <id>_lod1.glb.
PLANTS: dict[str, dict] = {
    "fir_sapling_a": {"kind": "sapling", "seed": 6101, "height": 2.5, "atlas": _FIR, "mat": "foliage_sapling", "bark": "bark_sapling", "lods": 2},
    "fir_sapling_b": {"kind": "sapling", "seed": 6202, "height": 1.5, "atlas": _FIR, "mat": "foliage_sapling", "bark": "bark_sapling", "lods": 2},
    "huckleberry_a": {"kind": "huckleberry", "seed": 6301, "height": 1.15, "stems": 8, "clusters": 48, "atlas": _PL, "mat": "huckleberry", "stem_mat": "huckleberry_stem", "lods": 2},
    "huckleberry_b": {"kind": "huckleberry", "seed": 6402, "height": 0.8, "stems": 6, "clusters": 32, "atlas": _PL, "mat": "huckleberry", "stem_mat": "huckleberry_stem", "lods": 2},
    "fireweed_a": {"kind": "fireweed", "seed": 6501, "height": 1.05, "stalks": 9, "atlas": _PL, "mat": "plants"},
    "yarrow_a": {"kind": "yarrow", "seed": 6601, "height": 0.5, "stems": 5, "atlas": _PL, "mat": "plants"},
    "sword_fern_a": {"kind": "fern", "seed": 6701, "size": 0.95, "fronds": 26, "atlas": LAYOUTS["fern"], "mat": "fern", "lods": 2},
    "sword_fern_b": {"kind": "fern", "seed": 6802, "size": 0.68, "fronds": 18, "atlas": LAYOUTS["fern"], "mat": "fern", "lods": 2},
    "sword_fern_c": {"kind": "fern", "seed": 6703, "size": 1.3, "fronds": 34, "atlas": LAYOUTS["fern"], "mat": "fern", "lods": 2},
    # Grass patches: about a dozen tufts over a ~1.6 m disc. The ground layer places at most one
    # plant per 1.25 m cell, so neighbouring patches overlap and a meadow reads as continuous grass.
    "grass_clump_a": {"kind": "grass", "seed": 6901, "height": 0.55, "cards": [["dense", 1.0], ["dense", 0.85], ["tall", 0.9], ["dense", 0.7]],
                      "tufts": 12, "spread": 0.8, "atlas": LAYOUTS["grass"], "mat": "grass", "lods": 2},
    "grass_clump_b": {"kind": "grass", "seed": 7002, "height": 0.7, "cards": [["tall", 1.0], ["tall", 0.85], ["dense", 0.7], ["tall", 0.75], ["dense", 0.6]],
                      "tufts": 10, "spread": 0.75, "atlas": LAYOUTS["grass"], "mat": "grass", "lods": 2},
    "grass_clump_c": {"kind": "grass", "seed": 7103, "height": 0.45, "cards": [["dry", 1.0], ["dry", 0.9], ["dense", 0.75], ["dry", 0.7]],
                      "tufts": 12, "spread": 0.8, "atlas": LAYOUTS["grass"], "mat": "grass", "lods": 2},
    "shelf_mushroom_a": {"kind": "mushroom", "seed": 7201, "length": 0.55, "radius": 0.11, "brackets": 4, "bracket_scale": 1.5, "mat": "mushroom",
                         "wood": "deadwood_static", "end": "wood_log_end_rotten"},
    "deadfall_a": {"kind": "deadfall", "seed": 7301, "sticks": 16, "spread": 0.8, "pile_h": 0.32, "wood": "deadwood_static",
                   "end": "wood_log_end_dead", "dead_sprays": 3, "atlas": _FIR, "spray_mat": "foliage_fir"},
    "deadfall_b": {"kind": "deadfall", "seed": 7402, "sticks": 22, "spread": 1.0, "pile_h": 0.45, "wood": "deadwood_static",
                   "end": "wood_log_end_dead", "dead_sprays": 4, "atlas": _FIR, "spray_mat": "foliage_fir"},
    # Forest-floor litter: a flat scatter of thin twigs, fallen cones and dead sprays (ground layer).
    "litter_a": {"kind": "deadfall", "seed": 7501, "sticks": 7, "spread": 0.7, "pile_h": 0.03, "stick_len": [0.15, 0.55],
                 "stick_r": [0.004, 0.011], "sides": 4, "caps": False, "wood": "deadwood_static", "cones": 5,
                 "cone_mat": "conifer_cone", "dead_sprays": 3, "spray_size": 0.6, "atlas": _FIR, "spray_mat": "foliage_fir"},
    "litter_b": {"kind": "deadfall", "seed": 7602, "sticks": 10, "spread": 0.9, "pile_h": 0.04, "stick_len": [0.2, 0.7],
                 "stick_r": [0.005, 0.013], "sides": 4, "caps": False, "wood": "deadwood_static", "cones": 3,
                 "cone_mat": "conifer_cone", "dead_sprays": 4, "spray_size": 0.7, "atlas": _FIR, "spray_mat": "foliage_fir"},
    # Moss mounds over buried stones and rotted stumps (ground layer; the rim sinks into the floor).
    # Tall enough to shade their own flanks: at 10-15 cm they read as flat green mats from standing height.
    "moss_mound_a": {"kind": "moss", "seed": 7701, "radius": 0.6, "height": 0.17, "humps": 3, "mat": "moss_mound"},
    "moss_mound_b": {"kind": "moss", "seed": 7802, "radius": 0.95, "height": 0.24, "humps": 4, "mat": "moss_mound"},
    # Redwood sorrel carpets between the ferns (ground layer).
    "sorrel_patch_a": {"kind": "carpet", "seed": 7901, "size": 0.9, "height": 0.11, "tops": 3, "sides": 3, "atlas": _PL, "mat": "plants"},
    "sorrel_patch_b": {"kind": "carpet", "seed": 8002, "size": 1.2, "height": 0.13, "tops": 4, "sides": 3, "atlas": _PL, "mat": "plants"},
    # Riverbank (textures/gen/riparian.py): sedge fountains with rushes, horsetail stands, willow shrubs.
    "sedge_clump_a": {"kind": "grass", "seed": 8101, "height": 0.85, "cards": [["sedge", 1.0], ["sedge", 0.85], ["sedge", 0.7]],
                      "tufts": 6, "spread": 0.45, "atlas": RIPARIAN, "mat": "riparian", "lods": 2},
    "sedge_clump_b": {"kind": "grass", "seed": 8202, "height": 0.95, "cards": [["sedge", 1.0], ["rush", 0.95], ["sedge", 0.8], ["rush", 0.8]],
                      "tufts": 5, "spread": 0.4, "atlas": RIPARIAN, "mat": "riparian", "lods": 2},
    "horsetail_a": {"kind": "grass", "seed": 8303, "height": 0.6, "cards": [["horsetail", 1.0], ["horsetail", 0.8]],
                    "tufts": 7, "spread": 0.55, "atlas": RIPARIAN, "mat": "riparian", "lods": 2},
    # Willows (build_willow): ascending stems forking near the top, twig cards massed toward the tips.
    "willow_shrub_a": {"kind": "willow", "seed": 8401, "height": 2.6, "stems": 10, "shoots": 9, "clusters": 175,
                       "regs": ["willow_a", "willow_b"], "lean": [0.06, 0.26], "card_len": [0.17, 0.26], "stem_scale": 1.8, "atlas": RIPARIAN, "mat": "willow",
                       "stem_mat": "willow_stem", "lods": 2},
    "willow_shrub_b": {"kind": "willow", "seed": 8502, "height": 1.9, "stems": 8, "shoots": 7, "clusters": 155,
                       "regs": ["willow_b", "willow_a"], "lean": [0.1, 0.32], "card_len": [0.19, 0.28], "stem_scale": 1.5, "atlas": RIPARIAN, "mat": "willow",
                       "stem_mat": "willow_stem", "lods": 2},
    # Burnt forest regrowth (ADR-0041): bracken drifts (textures/gen/burn_fen.py) and lodgepole
    # seedlings coming up through the ash.
    "bracken_a": {"kind": "fern", "seed": 10101, "size": 0.95, "fronds": 9, "atlas": _BRACKEN, "mat": "bracken", "lods": 2},
    "bracken_b": {"kind": "fern", "seed": 10202, "size": 1.25, "fronds": 12, "atlas": _BRACKEN, "mat": "bracken", "lods": 2},
    "lodgepole_sapling_a": {"kind": "sapling", "seed": 10301, "height": 1.6, "atlas": _FIR, "mat": "foliage_lodgepole", "bark": "bark_sapling", "lods": 2},
    "lodgepole_sapling_b": {"kind": "sapling", "seed": 10402, "height": 0.9, "atlas": _FIR, "mat": "foliage_lodgepole", "bark": "bark_sapling", "lods": 2},
    # Fen (ADR-0041): sphagnum hummocks, cattail and bulrush stands, skunk cabbage.
    "sphagnum_mound_a": {"kind": "moss", "seed": 10501, "radius": 0.75, "height": 0.26, "humps": 4, "mat": "sphagnum_red"},
    "sphagnum_mound_b": {"kind": "moss", "seed": 10602, "radius": 1.05, "height": 0.32, "humps": 5, "mat": "sphagnum_green"},
    "cattail_a": {"kind": "grass", "seed": 10701, "height": 1.9, "cards": [["cattail", 1.0], ["cattail", 0.9], ["cattail", 0.8]],
                  "tufts": 5, "spread": 0.55, "atlas": FEN, "mat": "fen_plants", "lods": 2},
    "cattail_b": {"kind": "grass", "seed": 10802, "height": 1.6, "cards": [["cattail", 1.0], ["cattail", 0.85], ["bulrush", 0.9]],
                  "tufts": 4, "spread": 0.45, "atlas": FEN, "mat": "fen_plants", "lods": 2},
    "bulrush_a": {"kind": "grass", "seed": 10903, "height": 1.7, "cards": [["bulrush", 1.0], ["bulrush", 0.85], ["bulrush", 0.7]],
                  "tufts": 4, "spread": 0.4, "atlas": FEN, "mat": "fen_plants", "lods": 2},
    "skunk_cabbage_a": {"kind": "fern", "seed": 11001, "size": 0.75, "fronds": 8, "atlas": _SKUNK, "mat": "fen_leaves", "lods": 2},
    "skunk_cabbage_b": {"kind": "fern", "seed": 11102, "size": 0.55, "fronds": 6, "atlas": _SKUNK, "mat": "fen_leaves", "lods": 2},
}


def _plant_tasks() -> list[Task]:
    out = []
    for pid, p in PLANTS.items():
        outs = [f"models/plants/{pid}.glb"] + ([f"models/plants/{pid}_lod1.glb"] if p.get("lods", 1) > 1 else [])
        out.append(Task(name=f"model:plants/{pid}", group="models", outputs=outs, sources=blender_sources("veg_plant"),
                        params={"name": pid, **p}, blender="veg_plant"))
    return out


def _tree_tasks() -> list[Task]:
    out = []
    for tid, p in TREES.items():
        atlas_name = {"fir": "foliage_fir", "larch": "foliage_larch", "birch": "foliage_birch"}.get(p["species"])
        params = {"name": tid, **p}
        if atlas_name:
            params["atlas"] = LAYOUTS[atlas_name]
        outs = [f"models/trees/{tid}.glb", f"models/trees/{tid}_lod1.glb", f"models/trees/{tid}_lod2.glb"]
        out.append(Task(name=f"model:trees/{tid}", group="models", outputs=outs, sources=blender_sources("veg_tree"),
                        params=params, blender="veg_tree"))
    return out


def _burn_tasks() -> list[Task]:
    # veg_burn builds on generators/veg_tree.py (trunks, roots, broken tops): its edits rebuild these.
    src = blender_sources("veg_burn") + [f for f in blender_sources("veg_tree") if f.name == "veg_tree.py"]
    out = []
    for tid, p in BURNT_SNAGS.items():
        outs = [f"models/trees/{tid}.glb", f"models/trees/{tid}_lod1.glb", f"models/trees/{tid}_lod2.glb"]
        out.append(Task(name=f"model:trees/{tid}", group="models", outputs=outs, sources=src,
                        params={"name": tid, "kind": "snag", **p}, blender="veg_burn"))
    for sid, p in BURNT_STUMPS.items():
        out.append(Task(name=f"model:trees/{sid}", group="models", outputs=[f"models/trees/{sid}.glb"], sources=src,
                        params={"name": sid, **p}, blender="veg_burn"))
    return out


def tasks() -> list[Task]:
    return _tree_tasks() + _wood_tasks() + _plant_tasks() + _burn_tasks()
