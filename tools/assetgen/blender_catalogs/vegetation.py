"""Vegetation assets: trees (explicit LODs), stumps/logs/fallen logs, understory plants.

Atlas layouts come from textures/gen/vegetation.py (LAYOUTS) and are passed to the Blender
generators as params, so a layout change rebuilds both the atlas and the models that use it.
Model ids match game/data/vegetation/species.json.
"""
from __future__ import annotations

from ..core.registry import Task, blender_sources
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
}


def _wood_tasks() -> list[Task]:
    out = []
    for wid, p in WOOD.items():
        out.append(Task(name=f"model:trees/{wid}", group="models", outputs=[f"models/trees/{wid}.glb"],
                        sources=blender_sources("veg_wood"), params={"name": wid, **p}, blender="veg_wood"))
    return out


_FIR = LAYOUTS["foliage_fir"]
_PL = LAYOUTS["plants"]
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
    "grass_clump_a": {"kind": "grass", "seed": 6901, "height": 0.5, "cards": [["dense", 1.0], ["dense", 0.85], ["tall", 0.9], ["dense", 0.7]], "atlas": LAYOUTS["grass"], "mat": "grass"},
    "grass_clump_b": {"kind": "grass", "seed": 7002, "height": 0.65, "cards": [["tall", 1.0], ["tall", 0.85], ["dense", 0.7], ["tall", 0.75], ["dense", 0.6]], "atlas": LAYOUTS["grass"], "mat": "grass"},
    "grass_clump_c": {"kind": "grass", "seed": 7103, "height": 0.42, "cards": [["dry", 1.0], ["dry", 0.9], ["dense", 0.75], ["dry", 0.7]], "atlas": LAYOUTS["grass"], "mat": "grass"},
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
    "moss_mound_a": {"kind": "moss", "seed": 7701, "radius": 0.6, "height": 0.1, "humps": 3, "mat": "moss_mound"},
    "moss_mound_b": {"kind": "moss", "seed": 7802, "radius": 0.95, "height": 0.15, "humps": 4, "mat": "moss_mound"},
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


def tasks() -> list[Task]:
    return _tree_tasks() + _wood_tasks() + _plant_tasks()
