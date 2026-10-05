# POI Building Kit — geometry contract

The POI builder (`game/src/poi/`) assembles buildings from modular kit pieces on a **1 m grid**.
This document is the contract between the kit generators (`tools/assetgen/blender/generators/kit_*.py`)
and the builder/shaders. Change it only together with the builder.

## Grid and storeys
* Cell = 1.0 m. Walls run along **cell edges**, centred on the edge line.
* Storey height = **3.0 m**: floor slab top at `level * 3.0`; walls from slab top `0.0` to `2.8`;
  the next slab occupies `2.8 .. 3.0`.
* Wall thickness = **0.16 m**.
* A tall room (ADR-0021) has no slab between its storeys: its walls stack one 2.8 m piece per
  storey, and `wall_band_1m` fills `2.8 .. 3.0` between them, inside and out. Two-storey openings
  are single **5.8 m** pieces (floor of one storey to the ceiling of the next).

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
| `wall_band_1m` | 1.0 | — | the storey band of a tall room's wall: z 2.8 … 3.0, finish on both sides |
| `wall_1m_window_tall` | 1.0 | 0.76 × 2.50, sill 0.80 | **5.8 m** tall: a two-storey sash window |
| `wall_2m_door_tall` | 2.0 | 1.80 × 3.50 | **5.8 m** tall: barn / bay double doors |
| `wall_1m_lancet` | 1.0 | 0.66 wide, sill 1.00, jambs to 3.45, equilateral pointed arch to ≈ 4.02 | **5.8 m** tall: church lancet; casings follow the arch |

**Side tagging (second UV map, named `UVSide`, exported as TEXCOORD_1 → Godot `UV2`)**:
`u = 0.0` on side A (faces −Y), `u = 1.0` on side B (faces +Y), `u = 0.5` on every other face
(ends, top, opening reveals). `v` unused (0). The kit wall shader picks each side's finish (paint,
wallpaper, siding, brick, …) per instance from texture arrays and projects it in world space, so
UV0 only needs to be sane (metre box projection is fine).

**Height in the room (INSTANCE_CUSTOM.a)**: in a tall room the shader must know how far above the
room's floor a stacked piece stands. The builder writes a code per side: `k + 4 × (storeys − 1)`,
where `k` (0–3) is the piece's storey within its room and `storeys` its room's height; side A in
the low nibble, side B × 16, plus a random fraction (< 0.98). Exterior faces and one-storey rooms
code 0, so ordinary walls are unchanged. `kit_wall.gdshader` turns it into the height in the room
(baseboard, grime, leaks, ceiling darkening) and the room's ceiling height.

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
| `window_glass_tall`, `window_glass_tall_broken` | `M_glass` | 6-over-6 double-hung sash for `wall_1m_window_tall` (broken: shards in the lower lites) |
| `window_glass_lancet`, `window_glass_lancet_broken` | `M_glass` | glazed lancet sash with a centre bar and four cross bars (broken: the arch knocked out) |
| `boards_window_tall`, `boards_window_lancet` | `M_wood_raw` | planks across the tall opening, nailed to the side A casing |
| `door_barn_tall`, `door_barn_tall_broken` | `farm_wood_barn_red`, `kit_trim`, `metal_steel` | 0.89 × 3.45 board-and-batten leaf (a pair fills `wall_2m_door_tall`): white battens and Z braces, strap hinges, D-handles |

### Galleries — material `M_kit_trim`, `M_kit_stairs` (balustrade), `M_wood_raw` (rail)
Where an upper room looks over a tall room's open space. The edge runs along X centred on the
origin, the origin is on the edge line at the gallery floor's top (z = 0), the void is at −Y (Godot
+Z), the gallery floor at +Y. Rails stand 6.5 cm in from the edge, handrail top at 1.0.
| model | notes |
|---|---|
| `gallery_balustrade_fascia`, `gallery_rail_fascia` | 1 m over the slab's edge: painted fascia with a nosing / a plain board |
| `gallery_balustrade_1m`, `gallery_rail_1m` | 1 m of railing: turned balusters (8 per metre) under a moulded handrail / two rough rails |
| `gallery_balustrade_1m_broken`, `gallery_rail_1m_broken` | the railing broken out (a `breach` on a gallery edge) |
| `gallery_balustrade_post`, `gallery_rail_post` | newel post at every metre of a run |

### Exterior pieces
| model | notes |
|---|---|
| `foundation_1m` | 1.0 × 0.2 × 0.6 concrete skirt under exterior walls (`M_concrete`) |
| `porch_step_1m` | 1 m wide, 3 steps up to 0.6 (`M_wood_painted`) |
| `porch_post` | 0.12 × 0.12 × 2.8 turned post |
| `porch_deck_1m` | 1 × 1 deck boards, top at 0.6 |
| `chimney_brick` | 0.8 × 0.6 × 4.5 brick chimney (`M_brick`) |
| `chimney_shaft_1m` | 1 m of plain chimney shaft; the builder stacks whole metres under `chimney_brick` until the chimney stands 0.4 m clear of every roof within 3 m (courses line up: both start at z = 0) |
| `gutter_1m` | (optional) |
Roofs are generated in Godot from the roof plan (see [Roofs](#roofs)) — not part of the kit.

## Finish texture arrays
Generated as Texture2DArrays (vertical strips, 1024² per slice):
`textures/kit_wall_finishes_{albedo,normal,orm}.png` and `textures/kit_floor_finishes_{…}.png`.
The slice order is defined in **`game/data/materials/kit_finishes.json`**
(`{"wall": ["plaster_white", ...], "floor": ["wood_oak", ...]}`) and must never be reordered
(POI specs refer to finishes by name; the builder maps names → slice indices).
The finishes are clean apart from small chips: their 1–2 m tile would repeat any big feature.
All wear is composed by `kit_wall.gdshader` in world space from two generated mask textures (the
file names predate the masks; ADR-0019):
* `textures/kit_decay_albedo.png`: RGBA coverage priorities, each uniform in [0,1], 2.5 m per tile:
  R grime, G water stains (blots plus drips running down from them), B mould, A peeling.
* `textures/kit_decay_orm.png`: RGB detail: R macro tone, G substrate grain and hairline cracks,
  B scuff strokes.
Both import as `mask` (BC7, linear). A layer shows where its priority exceeds `1 − coverage`.
Coverage comes from the instance's `decay` (INSTANCE_CUSTOM.b, the building's `style.decay` with
no per-piece jitter), from local height in the room (`VERTEX.y`: 0 on the slab, 2.8 under the
ceiling; plus 3 m per storey the piece stands above a tall room's floor, from INSTANCE_CUSTOM.a),
and from a coarse "zone" sample that makes some corners damp and others dry. Leaks start
under the ceiling, grime collects low, mould grows along floors and ceilings, paint and wallpaper
peel to their substrate (ceilings to the lath), and floors gather dust and scuffs. Exterior finishes
(slices 11–15) get rain streaks and green algae instead. Interior faces of plaster, paint, wallpaper
and panelling get a shader-drawn 11 cm baseboard.

## Roofs
`RoofPlanner` splits the building's tops into wings (rectangles roofed at their own height: main,
leg, annex, tower; ADR-0021, docs/POI_AUTHORING.md "Roofs") and `RoofBuilder.build_plan` builds
them: every slope is a plane over a convex polygon, cut wherever another wing's roof stands higher
inside that wing's walls (valleys between cross gables, roofs stopping at the walls they meet).
Types: `gable`, `hip`, `shed`, `flat`, `pyramid`, `spire` (octagonal broach spire with a cross),
`none`. Gable and shed ends are kit-wall faces flush with the wall below, from 0.2 under the wall
top (they close the storey band). Every roof's underside is `wood_weathered` sheathing boards (under
the eaves and rakes too). Under an `open_roof` room the roof also shows `wood_raw` timbers: rafters
every 0.6 m, a ridge beam, wall plates and collar ties; walls
between an open-roof room and a closed one rise to the roof's underside (partition infills).
`RoofBuilder` uses `style.roof.material` (default `roof_shingle`) from
`game/data/materials/roofs.json`: `roof_shingle`, `roof_shingle_brown`, `roof_metal`,
`roof_metal_red` and `roof_cedar`. Flat roofs use `style.roof.flat_material` (default `roof_tar`).
* Pitched-roof UVs are metres (U along the ridge, V up the slope). The sets tile every 2 m and are
  drawn eave-down.
* A tile holds nothing distinctive, because it repeats across the whole roof. Two world-space
  layers of `std_surface` carry the large scale:
  * `macro_variation` drifts tone and dampness.
  * `patch_cover`, `patch_color` and `patch_scale` lay ragged rust patches (metal roofs).
* Pitched roofs get trim:
  * fascia and rake boards (`kit_trim`) and a capped ridge;
  * half-round gutters (`metal_painted`), unless `"gutters": false`.
* Gable ends and parapets use the building's exterior finish and decay (kit wall shader).
* `"parapet"` sets a flat roof's parapet height.

## Budgets
Walls ≤ 200 tris (≤ 600 with openings + trim), floors ≤ 50, stairs ≤ 1.5k, doors ≤ 600.
