"""POI building kit (docs/POI_KIT.md): modular walls, floors, stairs, doors, windows, board-ups,
barricade and exterior pieces under models/kit/.

Every piece follows the kit contract (1 m grid, 2.8 m walls, 0.16 m thickness, origins per piece) and
carries a second UV map "UVSide" (glTF TEXCOORD_1 -> Godot UV2) tagging finish sides.
The last block ("compat") provides the model ids game/data/structures/poi_kit.json references today.
"""
from __future__ import annotations

from ..core.registry import Task, blender_sources

# model id -> (generator module, params)
PIECES: dict[str, tuple[str, dict]] = {
    # --- walls ---------------------------------------------------------------------------------
    "wall_1m": ("kit_wall", {"kind": "wall", "seed": 101}),
    "wall_1m_window": ("kit_wall", {"kind": "wall", "opening": "window_1m", "seed": 102}),
    "wall_2m_window": ("kit_wall", {"kind": "wall", "length": 2.0, "opening": "window_2m", "seed": 103}),
    "wall_1m_door": ("kit_wall", {"kind": "wall", "opening": "door_1m", "seed": 104}),
    "wall_2m_door": ("kit_wall", {"kind": "wall", "length": 2.0, "opening": "door_2m", "seed": 105}),
    "wall_1m_half": ("kit_wall", {"kind": "wall", "height": 1.0, "cap": True, "seed": 106}),
    "wall_1m_damaged": ("kit_wall", {"kind": "layered", "mode": "damaged", "seed": 21}),
    "wall_1m_breach": ("kit_wall", {"kind": "layered", "mode": "breach", "seed": 11}),
    "post_corner": ("kit_wall", {"kind": "post", "seed": 107}),
    "wall_1m_frac": ("kit_wall", {"kind": "frac", "pieces": 9, "seed": 108}),
    # --- floors --------------------------------------------------------------------------------
    "floor_1m": ("kit_floor", {"kind": "floor", "seed": 201}),
    "floor_1m_broken": ("kit_floor", {"kind": "broken", "seed": 41}),
    "floor_1m_frac": ("kit_floor", {"kind": "frac", "pieces": 7, "seed": 43}),
    "hatch_1m": ("kit_floor", {"kind": "hatch", "seed": 44}),
    # --- stairs / railings / ladder ------------------------------------------------------------
    "stairs_straight": ("kit_stairs", {"kind": "stairs", "seed": 51}),
    "stairs_railing": ("kit_stairs", {"kind": "stair_railing", "seed": 52}),
    "railing_1m": ("kit_stairs", {"kind": "railing", "seed": 53}),
    "ladder_3m": ("kit_stairs", {"kind": "ladder", "seed": 54}),
    # --- doors ---------------------------------------------------------------------------------
    "door_interior": ("kit_door", {"kind": "interior", "seed": 61}),
    "door_exterior": ("kit_door", {"kind": "exterior", "seed": 62}),
    "door_metal": ("kit_door", {"kind": "metal", "seed": 63}),
    "door_interior_broken": ("kit_door", {"kind": "interior", "broken": True, "seed": 64}),
    "door_exterior_broken": ("kit_door", {"kind": "exterior", "broken": True, "seed": 65}),
    "door_interior_frac": ("kit_door", {"kind": "interior", "frac": True, "pieces": 7, "seed": 66}),
    "door_exterior_frac": ("kit_door", {"kind": "exterior", "frac": True, "pieces": 7, "seed": 67}),
    # --- windows / board-ups / barricade -------------------------------------------------------
    "window_glass_1m": ("kit_window", {"size": "window_1m", "seed": 301}),
    "window_glass_2m": ("kit_window", {"size": "window_2m", "seed": 302}),
    "window_glass_1m_broken": ("kit_window", {"size": "window_1m", "broken": True, "seed": 303}),
    "window_glass_2m_broken": ("kit_window", {"size": "window_2m", "broken": True, "seed": 304}),
    "boards_window_1m": ("kit_boards", {"target": "window_1m", "seed": 401}),
    "boards_window_2m": ("kit_boards", {"target": "window_2m", "seed": 402}),
    "boards_door": ("kit_boards", {"target": "door_1m", "seed": 403}),
    "boards_window_1m_frac": ("kit_boards", {"target": "window_1m", "frac": True, "seed": 401}),
    "boards_window_2m_frac": ("kit_boards", {"target": "window_2m", "frac": True, "seed": 402}),
    "boards_door_frac": ("kit_boards", {"target": "door_1m", "frac": True, "seed": 403}),
    "barricade_furniture": ("kit_barricade", {"seed": 81}),
    # --- exterior ------------------------------------------------------------------------------
    "foundation_1m": ("kit_exterior", {"kind": "foundation", "seed": 501}),
    "porch_step_1m": ("kit_exterior", {"kind": "porch_step", "seed": 71}),
    "porch_post": ("kit_exterior", {"kind": "porch_post", "seed": 72}),
    "porch_deck_1m": ("kit_exterior", {"kind": "porch_deck", "seed": 73}),
    "chimney_brick": ("kit_exterior", {"kind": "chimney", "seed": 74}),
    # --- compat: ids referenced by game/data/structures/poi_kit.json ----------------------------
    "wall_1m_worn": ("kit_wall", {"kind": "layered", "mode": "worn", "seed": 31}),
    "wall_1m_brick": ("kit_wall", {"kind": "wall", "thickness": 0.24, "seed": 109}),
    "floor_1m_rotten": ("kit_floor", {"kind": "rotten", "seed": 42}),
    "door_wood": ("kit_door", {"kind": "interior", "seed": 61}),
    "boards": ("kit_boards", {"target": "window_1m", "seed": 401}),
    "window_glass": ("kit_window", {"size": "window_1m", "seed": 301}),
}


def tasks() -> list[Task]:
    out = []
    for mid, (module, params) in PIECES.items():
        p = {"name": mid, **params}
        out.append(Task(name=f"model:kit/{mid}", group="models", outputs=[f"models/kit/{mid}.glb"],
                        sources=blender_sources(module), params=p, blender=module))
    return out
