"""Garden and rain-collection models (ADR-0049), all from blender/generators/farm_garden.py except the garden
stew, which is item_food's open can:
  * models/structures/garden_bed.glb, rain_catcher.glb (game/data/structures/farming.json; the catcher's
    `water` node is scaled to its level);
  * models/crops/<crop>_s<n>.glb for every crop and stage in game/data/crops/*.json (read here, so a crop
    added in data gets its stages; a crop without a builder in farm_garden.CROPS is reported), and
    models/crops/dead_plant.glb;
  * models/items/garden/<id>.glb for the items in game/data/items/garden.json."""
from __future__ import annotations

import json
import sys

from ..core.paths import DATA
from ..core.registry import Task, blender_sources

GEN = "farm_garden"
# crop id -> seed (its stages vary the seed by stage)
CROP_SEEDS: dict[str, int] = {"potato": 7101, "carrot": 7111, "pole_beans": 7121, "huckleberry": 7131, "yarrow": 7141}

ITEMS: dict[str, tuple[str, dict]] = {
    "seed_potato": (GEN, {"kind": "item", "item": "seed_potatoes", "seed": 7201}),
    "carrot_seeds": (GEN, {"kind": "item", "item": "packet", "seed": 7202, "band": "garden_packet_orange"}),
    "bean_seeds": (GEN, {"kind": "item", "item": "packet", "seed": 7203, "band": "garden_packet_green"}),
    "huckleberry_seeds": (GEN, {"kind": "item", "item": "twist", "seed": 7204}),
    "yarrow_seeds": (GEN, {"kind": "item", "item": "twist", "seed": 7205}),
    "potato": (GEN, {"kind": "item", "item": "potato", "seed": 7206}),
    "carrot": (GEN, {"kind": "item", "item": "carrot", "seed": 7207}),
    "green_beans": (GEN, {"kind": "item", "item": "beans", "seed": 7208}),
    "baked_potato": (GEN, {"kind": "item", "item": "potato", "seed": 7209, "mat": "garden_potato_baked"}),
    "garden_stew": ("item_food", {"kind": "can_open", "seed": 7210, "label": "item_can_label_b_sooty", "size": [0.087, 0.118],
                                  "contents": "item_stew"}),
    "bucket": (GEN, {"kind": "item", "item": "bucket", "seed": 7211}),
    "bucket_water": (GEN, {"kind": "item", "item": "bucket", "seed": 7211, "water": True}),
}


def _sources(mod: str) -> list:
    """farm_garden builds on the log toolkit in structure_logs: list it (and the libs it imports) too."""
    out = blender_sources(mod)
    if mod == GEN:
        for f in blender_sources("structure_logs"):
            if f not in out:
                out.append(f)
    return out


def _crops() -> list[tuple[str, int]]:
    out = []
    for f in sorted((DATA / "crops").glob("*.json")):
        for d in json.loads(f.read_text()).get("defs", []):
            out.append((d["id"], int(d.get("stages", 4))))
    return out


def _task(out_path: str, mod: str, params: dict) -> Task:
    return Task(name=f"model:{out_path}", group="models", outputs=[f"models/{out_path}.glb"], sources=_sources(mod), params=params,
                blender=mod)


def tasks() -> list[Task]:
    out = [
        _task("structures/garden_bed", GEN, {"name": "garden_bed", "kind": "garden_bed", "seed": 7001}),
        _task("structures/rain_catcher", GEN, {"name": "rain_catcher", "kind": "rain_catcher", "seed": 7002}),
        _task("crops/dead_plant", GEN, {"name": "dead_plant", "kind": "dead_plant", "seed": 7003}),
    ]
    for crop_id, stages in _crops():
        if crop_id not in CROP_SEEDS:
            print(f"[farming] WARNING: no model spec for crop '{crop_id}'", file=sys.stderr)
            continue
        for n in range(1, stages + 1):
            out.append(_task(f"crops/{crop_id}_s{n}", GEN, {"name": f"{crop_id}_s{n}", "kind": "crop", "crop": crop_id, "stage": n,
                                                          "seed": CROP_SEEDS[crop_id]}))
    for item_id, (mod, p) in ITEMS.items():
        out.append(_task(f"items/garden/{item_id}", mod, {"name": item_id, **p}))
    return out
