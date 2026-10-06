"""Player-built structure models (models/structures/<id>.glb): the ids referenced by
game/data/structures/player_built.json ("model" / "fracture") and the blueprint ghost previews of
game/data/blueprints/guidebook.json. Ghost layouts are read from the blueprint data so they always
match the piece transforms the game uses."""
from __future__ import annotations

import json
import sys

from ..core.paths import DATA
from ..core.registry import Task, blender_sources

SPEC: dict[str, tuple[str, dict]] = {
    "log_piece": ("structure_logs", {"kind": "log_piece", "seed": 401}),
    "log_piece_reinforced": ("structure_logs", {"kind": "log_piece_reinforced", "seed": 401}),
    "log_piece_frac": ("structure_logs", {"kind": "log_piece_frac", "seed": 401, "pieces": 9, "frac_seed": 537}),
    "campfire": ("structure_camp", {"kind": "campfire", "seed": 411}),
    "lean_to": ("structure_camp", {"kind": "lean_to", "seed": 412}),
    "bough_bed": ("structure_camp", {"kind": "bough_bed", "seed": 413}),
    "spike_barrier": ("structure_camp", {"kind": "spike_barrier", "seed": 414}),
    "can_chime": ("structure_camp", {"kind": "can_chime", "seed": 415}),
    "grill": ("structure_camp", {"kind": "grill", "seed": 416}),
    "workbench": ("structure_stations", {"kind": "workbench", "seed": 421}),
    "storage_crate": ("structure_stations", {"kind": "storage_crate", "seed": 422}),
    "forge": ("structure_stations", {"kind": "forge", "seed": 423}),
    "chemistry_bench": ("structure_stations", {"kind": "chemistry_bench", "seed": 424}),
    # ADR-0035 holders, stairs and door (structure_base)
    "log_rack": ("structure_base", {"kind": "log_rack", "seed": 441}),
    "stick_rack": ("structure_base", {"kind": "stick_rack", "seed": 442}),
    "stone_pile": ("structure_base", {"kind": "stone_pile", "seed": 443}),
    "log_stairs": ("structure_base", {"kind": "log_stairs", "seed": 444}),
    "stick_door": ("structure_base", {"kind": "stick_door", "seed": 445}),
}
# Built even before a structure def references them (the runtime + defs land separately).
ALWAYS = ("log_rack", "stick_rack", "stone_pile", "log_stairs", "stick_door")


def _sources(mod: str) -> list:
    """Every structure generator builds on the log toolkit in structure_logs.py: list it (and the libs
    it imports) as a source so a change to the bark or the log rebuilds what uses it."""
    out = blender_sources(mod)
    for f in blender_sources("structure_logs"):
        if f not in out:
            out.append(f)
    return out


def _referenced() -> list[str]:
    ids: list[str] = []
    for f in sorted((DATA / "structures").glob("player_built.json")):
        for d in json.loads(f.read_text()).get("defs", []):
            for key in ("model", "fracture"):
                m = d.get(key, "")
                if m.startswith("structures/") and m[len("structures/"):] not in ids:
                    ids.append(m[len("structures/"):])
    return ids


def _ghosts() -> list[tuple[str, list]]:
    out = []
    f = DATA / "blueprints" / "guidebook.json"
    for d in json.loads(f.read_text()).get("defs", []):
        prev = d.get("preview", "")
        if d.get("mode") == "pieces" and prev.startswith("structures/") and prev.endswith("_ghost"):
            pieces = [{"pos": pc["pos"], "rot": pc.get("rot", [0, 0, 0]), "structure": pc.get("structure", "")} for pc in d.get("pieces", [])]
            out.append((prev[len("structures/"):], pieces))
    return out


def tasks() -> list[Task]:
    out: list[Task] = []
    ids = _referenced()
    ids += [sid for sid in ALWAYS if sid not in ids]
    for sid in ids:
        if sid not in SPEC:
            print(f"[structures] WARNING: no model spec for structure model '{sid}'", file=sys.stderr)
            continue
        mod, p = SPEC[sid]
        out.append(Task(name=f"model:structures/{sid}", group="models", outputs=[f"models/structures/{sid}.glb"],
                        sources=_sources(mod), params={"name": sid, **p}, blender=mod))
    for gid, pieces in _ghosts():
        params = {"name": gid, "kind": "ghost", "seed": 431, "pieces": pieces}
        out.append(Task(name=f"model:structures/{gid}", group="models", outputs=[f"models/structures/{gid}.glb"],
                        sources=blender_sources("structure_logs"), params=params, blender="structure_logs"))
    return out
