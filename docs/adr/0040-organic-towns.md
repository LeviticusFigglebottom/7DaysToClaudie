# ADR-0040: Organic towns: streets grown over the land, lots by frontage, zoning by rings

**Status**: Accepted · 2026-10. The pure planner (sections 1-5) and its wiring into random worlds
(section 6: `RwgGenerator.VERSION` 2, RWG v2 Phase 5 and the generator side of Phase 4).

## Context
The owner wants random worlds whose towns "ultimately feel organic". v1 towns (ADR-0031,
`RwgTowns`) are row or crossroads grids at right angles to the world axes, levelled onto one pad
inside one region: they read as stamped templates, and TD-083 lists what they lack (bends, squares,
outlying farms, back lanes). docs/RWG_V2_PLAN.md §3 plans organic towns as world-level features
with their own streets and lots; this ADR records the planner that implements its §3.5-§3.9 and
§3.12, which Phase 5 then wires in (§3.2, §3.10, §3.11).

Constraints: deterministic from its inputs and a seed; pure and safe on a worker thread (towns are
planned in parallel at generation); lots stay rectangles for the POI system (ADR-0009 buildings
are kit grids validated in their own frame, generated houses fill rectangular lots, cellars cut
plan cells); every lot must hold a real building through LotPicker (ADR-0030); and the output must
drop into a framework def (`FrameworkDef` v2) and the composer's existing road and pad vocabulary.

## Decision

### 1. A pure planner (`src/worldgen/rwg/`)
`RwgTownPlanner.plan(site, world, arterials, tuning, seed) -> Dictionary`:
* `site`: `{id, kind: hamlet | village | town, center, radius, name?}`.
* `world`: callables `height(x, z)` (the reference ground the composer grades world roads and
  world pads from), `water(x, z)` (distance to water, negative in it) and optionally `slope(x, z)`.
  The planner samples them lazily on a 4 m (heights) and 8 m (water) grid around the town, so
  the plan is a pure function of position and never depends on query order.
* `arterials`: the world roads through the town (`{id, points, width, shoulder, surface}`), as
  the generator routes them to the town centre.
* `tuning`: `data/config/town_planner.json` (`default_tuning()` reads it through
  `ContentDB.instance` or the file; `config_errors()` types it).
* `seed`: the town's seed; streams `town:<id>:streets`, `:lots`, `:fixtures` via
  `Ids.derive_seed`.

It returns plain data in world XZ (a v2 town's framework origin is [0, 0], rotation 0): `lots`
(`{id, frame: [cx, cz, w, d, yaw], poly, zoning, street, ring, y}`), `roads` (the town's own
streets, lanes, back lanes and cul-de-sac bulbs: `{id, class, points, width, surface, shoulder,
markings: false}`), `fixtures` (`{id: fx_N, prop, pos, rot}`), `plaza` (`{frame, y}` or `{}`),
`junctions`, `blocks`, `size`, `bounds`, `center`, `radius`, `tier_range` and `stats`.
`to_framework(plan, fw_id, name)` keeps exactly the §3.12 keys. No scene tree, no autoloads; a
town plans in about 0.1 s (a big hilly town in under 0.4 s) headless on the shared container.

Frames follow `PoiManager.lot_xf` (plan assumption A10, now tested): `yaw` in degrees with
`Basis(Vector3.UP, yaw)` as the building's basis, so the front (local +Z) points along
`(sin yaw, cos yaw)`: facing south is 0, east 90. Fixture `rot` uses the same convention. The
composer's 2D `rot` and a placement's `rotation` turn the other way (`Vector2.rotated(a)` is
`Basis(UP, -a)`), so a lot's pad and its placement take `-yaw`.

### 2. Streets (`RwgStreets`, §3.5)
* Seeds along each arterial out from the centre, every 55-130 m by ring, alternating sides; core
  seeds come first and leave square (`grid_bias`, 90 ± 4 degrees), some carrying on across the
  main street (`cross_chance`); the rest are mixed across the rings so the side-street count
  reaches the edge instead of being spent round the centre. Outside the core a seed leaves at
  whichever angle of 65-115 degrees climbs least.
* An agent steps 12 m, trying its heading ±0/6/12/24/36 degrees. Cost: 55 x grade + 0.35 per 12
  degrees turned + a drift towards a slowly wandering aim (so streets on level ground still bend;
  it fades out on slopes over 0.06, where the land decides) + crowding near other streets. Steps
  steeper than 0.11 are refused (the composer's smoothed profile then stays under 0.12).
* It joins a street it crosses or ends within 16 m of at 35 degrees or more (a T-junction: a
  loop), merging into a junction within 14 m; it refuses steps nearer a street at a shallower
  angle, or running beside one within 60 m at under 25 degrees (room for two lot depths). It stops
  at water (15 m), the radius, its length budget, the class's street budget, or when every heading
  is refused. Once the class's loop count is reached, streets keep 30 m off each other instead.
* Second-generation branches off long side streets (village 30%, town 60%); dead ends reach for a
  neighbour while there are too few loops; dead ends of 60 m or more get a bulb
  (`{points: [end, end + dir * 0.1], width: 18}`), interior ones first, up to the class's count;
  towns get back lanes behind the main street's core frontage (44 m off it, between two side
  streets leaving the same side).
* Blocks are the bounded faces of the planar street graph (a rightmost-turn face walk, dead-end
  spurs dropped), for the map; lots never depend on them.
* `route_fine(ground, a, b, opts)`: A* on an 8 m local grid (length, grade, a valley term against
  the local 150 m mean, water refused or bridged) with corner relaxation, for in-town arterial
  refinement in Phase 5; the tests route their synthetic arterials with it.

### 3. Lots (`RwgLots`, §3.6)
* Each street side is walked from junction gap to junction gap (crossing half width + 8 m, on the
  side the crossing street leaves); a lot's front edge runs along the chord of its stretch, out
  past the verge (3 m, at least the shoulder + 1 m) from wherever the street bulges nearest, its
  front facing the street. A stretch that bends more than 30 degrees holds no lot.
* Accepted only when 1 m clear of every frame (separating axes, through a 32 m hash), clear of
  every street corridor (half width + shoulder + 0.4 m, measured against the composer's own
  Catmull-Rom centre lines), 12 m from water, and on reference-ground relief of at most 3.5 m
  (residential, rural) or 2.5 m (commercial, civic, industrial, the plaza). Otherwise it shrinks to
  its zone's minimum depth, then frontage, then the walk skips 6 m; after a lot it leaves 1-4 m.
* Sizes (frontage x depth, m): inner residential 18-23 x 26-32, outer residential 22-30 x 30-40,
  commercial 22-32 x 28-36, civic 32-36 x 33-38 (a small civic lot 26-30 x 30-33 as a fallback),
  industrial 30-44 x 32-44, rural 34-60 x 40-60. Every size fits at least one building of its
  zoning (templates for residential, commercial, industrial and rural; authored civic buildings),
  which the tests check through LotPicker itself.
* Cul-de-sacs get up to three head lots facing the bulb. Parcels: the frame grown towards its
  neighbours (halfway, at most 4 m) and back (at most 8 m), clipped by the corridors.

### 4. Zoning (§3.7, §3.8)
Rings by distance from the centre (core: the class's core radius; inner < 0.6 r; outer < r;
edge beyond). Quotas, each drawn from the class's range, in order: commercial on arterial
frontage nearest the centre (zoned `commercial, roadside`); civic round the plaza (behind it and
beside it, facing it) and then in a band just past the shops, on arterials or side streets (the
first two `civic`, more `civic, commercial` because the authored civic pool is small); industrial
on arterials round 0.92 r; rural out along the arterials past the radius, every 150-300 m (the
outskirts, §3.9); then houses on every street side. Quotas short of the class minimum retry on
ground a metre steeper, then anywhere in town. The houses are then thinned to the class's lot count
by a weighted draw without replacement, the weight falling with distance from the centre, so the
core stays full and the edge goes ragged. Lots: hamlet 6-14, village 22-45, town 70-120.

### 5. Fixtures (§3.9)
Lamps every 30-38 m and hydrants every 60-90 m in the core and inner rings; utility poles along
the arterials out past the farthest farm; stop signs on the minor leg of every junction; speed
signs at the entries; the Cordon's barricade and fire drum across one entry; dumpsters, litter, a
payphone, newspaper boxes, benches and a collection box at shops and civic lots; mailboxes at
houses and farms; the square's benches and lamps; wrecks in the lanes. All on verges or streets,
never in a lot; prop ids exist in `data/props`.

### 6. Towns in the world (RWG v2: generator VERSION 2)
Generator VERSION 2 (one bump for everything here; a v1 world still loads from its folder, and a
run whose folder is gone regenerates with v2, TD-082):

* **Sites by size class** (plan §3.3, §3.8). The `towns` option is gone; `town_density` (towns per
  16 km², default 2.0, 0-6) sets the count (`floor(density x area / 16 + a draw)`, at least one when
  above zero), the town-size mix the classes, big first. A site is the best of 240 candidates:
  dry (60 m from water), core relief at most 15 m and disc relief 45 m, the disc's mean macro slope
  at most `max_slope` by class (hamlet 0.11, village 0.09, town 0.075; else the least steep disc
  seen plus 0.01, so a rough map still gets its town), its disc 300 m clear of every other town's
  and inside the map; scored by core and disc slope, height below the kilometre round it (valleys),
  water 80-300 m away, the middle of the map. The macro grid then eases half way to its mean
  within 0.8 of the core radius (water and its banks stay). Measured on generated land, the disc's
  slope decides how far a town grows: the planner's streets climb at most 0.11, and towns on 0.1
  slopes stopped at 4 side streets and 23-40 lots; the slope limit brought them to 10-15 side
  streets and 75-105 lots.
* **Main streets through the centres** (§3.4). The road network (spanning tree, loops and exits by
  density, both now per 16 km² / per 4 km of map side) is routed between town centres, towns not
  blocked, with a valley term in the 32 m router (`valley` 0.03: each metre of road costs that much
  more per metre the ground stands above its 300 m mean). Then every town gets a main street
  through its centre: the two roads ending there that meet straightest become one road; a lone
  road carries on past the centre as a stub (`stub`: radius + 150 m, along the heading that keeps
  lowest and least steep, routed by `route_fine` on 8 m cells, the least winding of the four best
  headings: a route forced up a slope zigzagged); a town no road reached gets a county road
  through it; a town (the biggest class) with one road through its core gets a county road across.
  The plan's in-disc `route_fine` refinement of the 32 m arterials is not done (TD-139).
* **Planned in parallel, on the ground the composer grades.** Each town is planned (up to four
  threads, results by index, byte-identical to one thread) with the world roads within radius +
  outskirts + 60 m as its arterials, nearest first. Its ground is the composer's own macro ground
  (`RefGround`: world.json's grid written and read back through JSON exactly as the composer reads
  it, bicubic): the shared detail noise (2.5 m, 10-80 m across) is texture the composer smooths
  out of a street's profile and grades out of a pad, and on it every 12 m street step and every
  lot's relief read as steep at random. Water: the exact distance near water (a river-segment
  index), a lower bound from the chamfer field far from it. Then the towns are settled against
  each other (a lot must lie inside the map, clear of every other town's street corridors and of
  the lots of the towns before it) and against roads added after them (a track or a drive to a
  place that comes into a frame takes the lot away; the router closes its 32 m cells within 18 m
  of every frame first). A lot's `y` is set last, on the final grid: the mean of the reference
  ground (macro plus the world detail noise, `TerrainComposer._reference_ground`, bit-identical:
  a test compares them) over its frame, 5 x 5 samples.
* **World-level towns.** world.json has `towns: [{id, name, kind, framework, origin: [0, 0],
  rotation: 0, center, radius, bounds}]` (bounds: lots, parcels, streets with their width, the
  square and the fixtures, grown 4 m); frameworks.json the town as a FrameworkDef v2 (`layout:
  "organic"`, frame lots, `kind`, `center`, `radius`, `plaza`, `authored`, tier range by the
  danger of its centre's region). No region lists a town as a feature any more.
* **Authored buildings capped per world** (§3.11). `LotPicker.assign_authored(towns, seed, cap)`
  gives each authored building to at most `authored_max` (3) towns that have a lot it fits (zoning,
  tier, size), drawn from a stream of the map seed and the building; an organic town's lots choose
  authored buildings only from its list (per run, as before). Civic lots hold only authored civic
  buildings, so a town keeps as many pure civic lots as it was given civic buildings that fit
  them all; the rest also take shops (`civic, commercial`). v1 towns are not capped.
* **The composer** (§3.10; additive: worlds without `towns` compose byte for byte as before, so
  `TerrainComposer.VERSION` stays 11 and the golden test's Larch Hollow digests hold). Every town
  whose bounds, grown 40 m, reach a region adds there: its streets as world roads (graded from the
  reference ground, no border fade; profiles memoised in `WorldDef.road_profile` under
  "town:<town>:<street>"); a pad per lot over its frame (rotation -yaw, corner at the frame's
  local (-w/2, -d/2), target `y`, biome `yard`: grass only, vegetation 0.6, a 5 m skirt that gives
  way to every road's paved corridor and eases in over the next 2 m, so a yard never bumps a
  street) and its square (`town`, paved asphalt, no vegetation); a `town` biome paint over its
  disc (streets and the ground between them, as a v1 town's pad had: town spawns and ambience).
  Skirts first, then every frame graded to exactly its `y` to its edges (lots stand 1 m apart, so
  a later skirt reached into an earlier lot). Placements: one `{kind: "lot", def, town, lot, id:
  "<town>/<lot>", origin: [cx, y, cz], rotation: -yaw, size}` per lot, by the region holding its
  frame's centre (each lot once), and one `{kind: "town", def, id: <town>, origin: 0, rotation: 0,
  rect}` per region the town reaches. Both sides of a border compute the same samples from world
  data alone: a test composes a 2 x 2 world with a village forced onto the corner where all four
  regions meet, at 4 m, and the border rows and columns agree to 1e-4 m.
* **Buildings on frames.** `LotPicker.lot_size` reads a frame (frontage, depth), `lot_local_xf(l,
  footprint)` = T(cx, y, cz) · Basis(UP, yaw) · T(-footprint / 2) (the footprint centred, front
  towards the street; the same transform lot_xf gives a rect lot facing the same way, tested).
  PoiManager places a `town` placement through `_place_framework`: the lots whose frames centre
  in its rect, with `lot_local_xf`, and the fixtures standing in it; TerrainHoles cuts the cellars
  of the same lots with the same transform; WorldLoader resolves a town's lots once on its thread.
  The `lot` placements are for the PoiRegistry of Phase 3 (session 3).
* **The map** draws an organic town from world.json and frameworks.json: yards, frames by zoning
  with a tick to the street each faces, the square, the streets by class (turning circles as
  discs) under the world roads; glyphs for cells A-P and rows 0-9 (maps to 16 x 16).
* **Sizes.** The New Game cap stays 7 (big worlds wait for streaming); generation scales: 10 x 10
  in 6.3 s (towns 1.1 s on threads, roads 1.6 s, land 1.9 s), tested with the size forced in
  memory (rwg_preview `--force-size`); place caps are per 16 km²; 70 town names.
* **TD-135**: the generator's polygon tests use `RwgStreets.point_in` (Geometry2D's counted a ray
  through a vertex twice); the composer's lake tests keep Geometry2D (main-map output).

## Consequences
+ Towns follow their land: side streets bend along the contours (their mean grade stays under 0.6
  of the land's mean slope on hilly sites), lots turn with them (their yaw spread about a common
  grid is over 10 degrees), and terraces form where lots step down a slope. Main street, shops at
  the crossing, a square ringed by civic buildings in towns, cul-de-sacs, loops, alleys behind the
  shops, farms out on the roads: a small American town, different every seed.
+ Pure and fast (0.1 s a town; 72 seeded plans in the tests in about 33 s with their checks), so the
  generator can plan dozens of towns on worker threads.
+ Data-driven: every number in `town_planner.json`; the tests check the tuning fits real buildings.
+ In the game: every random world (generator v2) has organic towns that may straddle region
  borders, graded seamlessly, every lot placed once at its own height with a building that fits.
− Towns are bigger (a town 70-120 lots): until Phases 2-3 stream them, every building of every
  town is built at load (TD-137).
− Lots step down a slope as terraces with short banks between them (1 m apart, 5 m skirts), and
  yards grow grass right up to (and, under a low floor, possibly into) the building (TD-136).
− Lots are rectangles in irregular parcels; a building never takes a parcel's shape (TD-116).
− Fixtures are per town in lists of a few hundred; they need Phase 3's per-cell batching.
− The planner trusts its arterials: a kinked or doubled main street near the centre costs core
  frontage; the 32 m arterials are not refined in the disc yet (TD-139).
− A town on ground steeper than its class's slope limit (rough small maps) still comes out half
  grown (TD-138).
