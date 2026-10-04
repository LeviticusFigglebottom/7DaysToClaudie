# POI Building Kit — geometry contract

The POI builder (`game/src/poi/`) assembles buildings from modular kit pieces on a **1 m grid**.
This document is the contract between the kit generators (`tools/assetgen/blender/generators/kit_*.py`)
and the builder/shaders. Change it only together with the builder.

## Grid and storeys
* Cell = 1.0 m. Walls run along **cell edges**, centred on the edge line.
* Storey height = **3.0 m**: floor slab top at `level * 3.0`; walls from slab top `0.0` to `2.8`;
  the next slab occupies `2.8 .. 3.0`.
* Wall thickness = **0.16 m**.

## Pieces (Blender space, Z up, front = −Y, units m)

### Walls — material `M_kit_wall`
Length along X, thickness along Y (−0.08 … +0.08), height along Z (0 … 2.8). Origin = bottom centre.

| model id (`models/kit/…`) | length | opening (w × h, sill) | notes |
|---|---|---|---|
| `wall_1m` | 1.0 | — | solid |
| `wall_1m_window` | 1.0 | 0.70 × 1.10, sill 0.90 | |
| `wall_2m_window` | 2.0 | 1.60 × 1.20, sill 0.85 | |
| `wall_1m_door` | 1.0 | 0.86 × 2.10 | |
| `wall_2m_door` | 2.0 | 1.70 × 2.10 | double door / archway |
| `wall_1m_half` | 1.0 | — | 1.0 m tall pony wall |
| `wall_1m_damaged` | 1.0 | — | cracks, small holes (not passable), exposed lath at holes |
| `wall_1m_breach` | 1.0 | jagged hole ≈ 0.8 × 1.7 from the floor (**passable**) | splintered studs/plaster |
| `post_corner` | 0.16 × 0.16 | — | fills wall junctions; centred on the grid vertex |
| `wall_1m_frac` | — | — | Voronoi chunks of `wall_1m` (8–10), inner material `M_kit_wall_inner` |

**Side tagging (second UV map, named `UVSide`, exported as TEXCOORD_1 → Godot `UV2`)**:
`u = 0.0` on side A (faces −Y), `u = 1.0` on side B (faces +Y), `u = 0.5` on every other face
(ends, top, opening reveals). `v` unused (0). The kit wall shader picks each side's finish (paint,
wallpaper, siding, brick, …) per instance from texture arrays and projects it in world space, so
UV0 only needs to be sane (metre box projection is fine).

Openings get **casing trim** (≈ 7 cm wide, 2 cm proud) on both sides and a sill on windows, as
separate mesh parts with material `M_kit_trim`. Windows do **not** include glass (separate piece).

### Floors — material `M_kit_floor`
| model | size | notes |
|---|---|---|
| `floor_1m` | 1 × 1, 0.2 thick | origin = **top** centre; slab extends down to −0.2 |
| `floor_1m_broken` | 1 × 1 | jagged partial slab with a hole (passable drop), splintered joists |
| `floor_1m_frac` | — | chunks of `floor_1m` |
Side tagging: top face `u = 0.0` (floor finish), bottom face `u = 1.0` (ceiling finish), sides 0.5.

### Stairs, ladders, railings — material `M_kit_stairs` (wood), `M_kit_trim`
* `stairs_straight`: 1.0 wide, rises **3.0 m over 4.0 m** (12 risers × 0.25, treads 0.333). Origin at
  the bottom-front edge centre; the flight ascends toward **+Y** (occupies x ∈ [−0.5, 0.5],
  y ∈ [0, 4]). Closed stringers.
* `stairs_railing`: banister matching `stairs_straight` (placed on one side).
* `railing_1m`: landing railing, 1.0 long, 0.95 tall.
* `ladder_3m`: wall ladder 0.5 wide × 3.0 tall (roof hatches, lofts), origin bottom centre.
* `hatch_1m`: floor/ceiling hatch frame with hinged lid (1 × 1).

### Doors, windows, barricades
Door leaves are hinged on their **left** edge (seen from −Y): origin = bottom of the hinge edge.
| model | material | notes |
|---|---|---|
| `door_interior` | `M_door_wood` | 0.82 × 2.05 × 0.04 panel door + knob (`M_metal_steel`) |
| `door_exterior` | `M_door_wood` | with small glass window |
| `door_metal` | `M_metal_painted` | steel security door + push bar |
| `door_interior_broken`, `door_exterior_broken` | | split/cracked leaf |
| `door_*_frac` | | chunks, inner `M_wood_raw` |
| `window_glass_1m`, `window_glass_2m` | `M_glass` | pane for the matching opening, origin bottom centre of the pane |
| `window_glass_1m_broken`, `window_glass_2m_broken` | `M_glass` | jagged shards left in frame |
| `boards_window_1m`, `boards_window_2m` | `M_wood_raw` | 3–4 planks nailed across (slight random angles via seed) |
| `boards_door` | `M_wood_raw` | 4–5 planks across a door opening |
| `boards_*_frac` | | plank pieces |
| `barricade_furniture` | mixed | pile of a dresser + chairs + planks blocking a doorway (1.6 × 1.4 × 0.8) |

### Exterior pieces
| model | notes |
|---|---|
| `foundation_1m` | 1.0 × 0.2 × 0.6 concrete skirt under exterior walls (`M_concrete`) |
| `porch_step_1m` | 1 m wide, 3 steps up to 0.6 (`M_wood_painted`) |
| `porch_post` | 0.12 × 0.12 × 2.8 turned post |
| `porch_deck_1m` | 1 × 1 deck boards, top at 0.6 |
| `chimney_brick` | 0.8 × 0.6 × 4.5 brick chimney (`M_brick`) |
| `gutter_1m` | (optional) |
Roofs are generated in Godot from the footprint (gable/hip/flat) — not part of the kit.

## Finish texture arrays
Generated as Texture2DArrays (vertical strips, 1024² per slice):
`textures/kit_wall_finishes_{albedo,normal,orm}.png` and `textures/kit_floor_finishes_{…}.png`.
The slice order is defined in **`game/data/materials/kit_finishes.json`**
(`{"wall": ["plaster_white", ...], "floor": ["wood_oak", ...]}`) and must never be reordered
(POI specs refer to finishes by name; the builder maps names → slice indices).
Also generated: `textures/kit_decay_{albedo,orm}.png` (tileable water stains / mould / grime used by
the kit shaders as an overlay driven by per-instance `decay`).

## Budgets
Walls ≤ 200 tris (≤ 600 with openings + trim), floors ≤ 50, stairs ≤ 1.5k, doors ≤ 600.
