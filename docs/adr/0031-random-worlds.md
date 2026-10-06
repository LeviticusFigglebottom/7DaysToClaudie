# ADR-0031: Random worlds: a seeded generator that writes the handcrafted map's own format

**Status**: Accepted · 2026-10

## Context
The product owner asked for "the other half" of 7 Days to Die: randomized, customizable worlds
whose towns differ every time. DESIGN §10.2 planned RWG as a generator feeding the interface the
handcrafted map already uses: `WorldDef` (world.json: macro elevation, rivers, lakes, roads, the
region roster) plus one feature list per region (region.json: frameworks, POIs, paths, clearings,
spawns, Bloom zones...), which `TerrainComposer` turns into heights, splats, biomes and a
vegetation mask, and which water, roads, bridges, vegetation, POIs, the Bloom and streaming read
unchanged. Varied interiors (ADR-0030) made towns fillable from zoning alone: a framework lot
without a `pick` gets an authored building or a generated house from the world seed.

Constraints: deterministic per seed, settings and generator version; generation on a background
thread with progress; cached to disk; saves record the world; the slice smoke must still pass on the
main map; and nothing that varies may break the composer's region-border stitching (local features
fade out within 48 m of a border).

## Decision

### 1. Settings in data (`data/config/world_gen.json`, `WorldGenSettings`)
* Thirteen options in four categories (map, land, water, towns and places): size (2-7 regions a
  side), terrain (flat, rolling, hilly, mountainous), roughness, the biome mix (conifer, birch,
  meadow, rocky weights), rivers and lakes (none, few, some, many), town count and size (hamlets,
  villages, mixed, towns), wilderness density and road density. Six presets (standard, small valley,
  highlands, lakeland, settled county, wild country). Resolved like game rules (ADR-0014): option
  defaults <- preset <- the player's overrides, coerced and clamped.
* A random world has its own **map seed** (land, water, towns, places). The run seed
  (`GameSession.world_seed`) still drives loot, scatter, the Hum and which buildings stand on the
  lots, so one map can be played many times with different towns' buildings.
* `tuning` holds the generator's numbers (terrain profiles, river catchments, lake rates, town kinds
  and lot sizes, road classes, the wilderness pool with each place's site and access kind, the drop
  site's rules, Bloom rates) and `names` its place names. `WorldGenSettings.schema_errors()` types
  the file (unknown keys, option specs, presets, pool entries naming unknown POIs, biomes or
  frameworks); `make validate` runs it.

### 2. The generator (`src/worldgen/rwg/`)
A pure function of `(map seed, resolved settings, RwgGenerator.VERSION)`; every stage draws from its
own derived stream. Stages:
1. **Land** (`RwgTerrain`, a 32 m macro grid): domain-warped rolling noise, ridged ranges under a
   slow mountain mask, a tilt that gives water somewhere to go. Lakes are irregular basins dug at
   low, level spots, their level under the lowest point of their rim. A priority-flood from the map
   edge and the lakes fills every other hollow (no river ever runs uphill or needs a levee),
   steepest-descent drainage counts each cell's catchment, the ground is carved by it (a simple
   stream-power erosion, blurred so valleys have floors), and flooded again. Rivers are traced up
   from the biggest mouths (map edge or lake) and then their largest tributaries, until the
   setting's count; a river's level is the filled ground under it (monotone to its mouth), sampled
   every 20 m along its smoothed line and never above the ground under that line; its width grows
   with its catchment.
2. **Towns** (`RwgTowns`): sites on the flattest dry ground (relief under 9 m, 45 m clear of water,
   650 m apart, inside one region with a 72 m margin, low and central preferred); the grid is then
   levelled under the pad. A town is a **generated framework** in one of two layouts. *Rows*: one
   or two row streets with lots on both sides (a verge between kerb and lot for lamps, poles and
   hydrants), cross streets joining the rows, commercial lots at the middle of the main street,
   civic lots at its centre, a workshop lot at the end of a back street. *Crossroads* (half the
   villages, two in five towns): a main street and a cross street through its middle, lots along
   all four arms, shops and a civic building on the corner lots of the crossing, four entries.
   Residential lots elsewhere; every lot is sized to fit every building template and the authored
   buildings zoned for it (the new pool buildings fit too). Fixtures: lamps, poles, hydrants, stop signs,
   wrecks in the lanes, a Cordon barricade at one entry with a fire drum, dumpsters, benches, a
   payphone, a collection box, litter. Its lots pick or generate their buildings through LotPicker
   exactly like Pell's Crossing's.
3. **Roads** (`RwgRoads`): A* over the macro grid costed by length and grade (gentle grades
   preferred, steep ones heavily penalised), rivers (a bridge to enter, more to follow), lakes,
   towns and places (impassable). A spanning tree joins the towns (asphalt highways between villages
   and towns, gravel county roads to hamlets), plus loops and exits off the map by road density. A
   route that meets a road already built joins it at a T-junction instead of running beside it;
   routes are simplified, their sharp corners cut where the straight line is passable, and they
   arrive at a town along its main street's axis. Every crossing gets a bridge span.
4. **Drop site**: away from towns (380 m) and places, 40-220 m from a road, on gentle dry ground,
   about a day's walk from a town; a clearing, the drop-site spawn with the Remand canister, and a
   footpath to the road. Region danger (1-5) is the distance from it.
5. **Biome map** (64 m cells): conifer, birch, meadow and rocky scores from the mix, elevation,
   slope, wetness and noise, meadow round towns, one majority pass. The composer jitters its edges.
6. **Places**: the authored wilderness pool by site (the boathouse on a lake shore over the water,
   the lookout on a summit, cabins and logging camps in forest, the campground and the sawmill by
   water, the Ashen watch camp far from the start, gas stations, motels and diners on straight
   highway stretches, the Okafor farm in meadows) with per-world caps and minimum danger, never
   overlapping towns, places, roads, water or the drop site, on ground they can level. Each gets
   its access: a short asphalt drive off the road it fronts, a dirt track, or a footpath (listed
   in every region it crosses), from the nearest road clear of town streets.
7. **The Bloom**: patches in the forest of danger 3-5 regions (ADR-0025); POI defaults add theirs.

Output: `world_json()` (the same schema as the main map plus `macro.step`, `road_grade`,
`biome_map` and a `generator` record of settings, towns, places, the drop site, timings and
warnings), one `region_json()` per cell (frameworks, POIs, paths, the clearing and spawn, Bloom
zones, shared detail noise), and `frameworks_json()`.

### 3. The composer reads it unchanged, with four additive extensions
* `WorldDef.macro_step`: the macro grid's spacing (region corners on the handcrafted map, 32 m for a
  generated world, whose ranges and valleys live in the grid; macro noise is off there).
* `Polyline2.value_at` takes three or more values spaced evenly along the arc (river levels and
  widths); a [start, end] pair is unchanged.
* `WorldDef.road_grade == "world"`: world roads are graded from the macro height plus the shared
  world detail noise, so a road has one profile on both sides of a region border.
* `WorldDef.biome_map`: the base biome of a sample (before water, pads and slope rules).
Plus two pure speed-ups in the surface pass (bounding-box early outs for paints and pads: Larch
Hollow composes to the identical hash, 13.3 s -> 10.1 s) and the generated `frameworks.json` in the
input hash. `TerrainComposer.VERSION` is unchanged: the main map composes byte for byte as before.

### 4. On disk, loading and saves
* `RwgWorlds.ensure(settings)` writes `user://worlds/random/<world id>/` (world.json,
  regions/*/region.json, frameworks.json, map.png, meta.json) through a `.tmp` folder; the id
  hashes the map seed, the settings and VERSION, so the folder is a cache and a world is generated
  once. The newest six worlds are kept (composed terrain included). Composed regions cache under
  `user://cache/worlds/<world id>/` like any world's.
* Generated towns are registered with ContentDB (`add_runtime_def`, the one hook in core) before
  the world loads, so the composer, PoiManager, TerrainHoles and LotPicker find them by id.
* `WorldLoader.load_random_world()` (on GameWorld's worker) generates or reads the world, registers
  its towns and loads it; all its regions are built, so they compose on three threads of their own.
* `GameSession.world_gen` holds the settings (`world_mode` "random", `world_id` the hash). **Save
  version 6** records it (the 5 -> 6 migration puts every older run on the main map). A loaded run
  reads its saved world folder if it is still there (identical even if the generator changed since)
  and otherwise regenerates it from the settings.

### 5. Screens and tools
* The main menu's **Random World…** opens the New Game screen on its new **World** tab: the map
  (Hollowmere Valley or a random world), the world preset, the map seed (and New seed), every world
  option, and **Generate preview**, which generates on a worker thread and shows the map with a
  summary. The run seed moves to the Game tab beside the difficulty and the rules.
* `RwgMap` draws a world's map from its files: shaded relief tinted by biome (sampled exactly as
  the game interpolates the land), lakes and rivers, roads by class with bridges, towns with their
  lots by zoning and their streets, places, trails, Bloom patches, the drop site and the region
  grid with cell labels.
* `rwg_preview.gd -- --seed N --size S [--preset id] [--set k=v] --out map.png [--fresh] [--compose]`
  prints the world's towns, places, water and roads and writes its map; `--compose` shapes every
  region into the cache. `rwg_preview_shots.gd` renders in-world shots of a generated world from
  its own data (a town street and the town from above, a river valley, a wilderness place, the
  drop site, the land from the air), and `rwg_preview_menu.gd` captures the World tab with a
  generated preview. `--world random [--world-seed N] [--world-preset id]
  [--world-set k=v]` starts one from the command line, and the slice smoke takes it too.

### Budgets (measured headless on this container, 4 shared cores)
* Generation: 4 x 4 world 0.5 s, 5 x 5 world ~0.9 s (`test_generation_time_5x5` asserts < 10 s).
  Writing the files and drawing the 1024 px map: ~1.5 s more.
* First load: composing a region at 1 m takes ~8-10 s (more under load) on each of three threads:
  a 3 x 3 world was ready in 97 s the first time (composition ~65 s), 31.5 s once cached (the main
  map: 36.5 s). Composed cache: ~4 MB a region.

## Consequences
+ A new world from any seed in about a second: rolling or mountainous land with valleys carved by
  its drainage, rivers that fall to lakes or off the map, lakes in basins, towns on level ground
  with their streets, a road network with bridges, the authored places where they belong, and a
  drop site by a road. Every town's buildings are picked and generated per run (ADR-0030).
+ Nothing downstream changed: composer, water, roads, bridges, vegetation, the Bloom, POIs, the Hum,
  supply drops and saves run on generated worlds as they are (the slice smoke passes on one).
+ The main map is untouched: same composer output, same save behaviour (v5 runs migrate to the main
  map).
− Every region of a random world is built at 1 m and held in memory, and every building is built at
  load: a 5 x 5 world's first load composes for a few minutes, and large worlds cost memory and
  load time (TD-081).
− A run whose world folder was pruned and whose generator has changed since gets a different world
  (TD-082).
− v1 leaves out caves, traders, the Ashen's territory, coasts, burnt/snow/swamp biomes, outflowing
  lakes and droplet erosion; towns are rectangular grids at right angles and authored places repeat
  across a world (TD-083).
− The preview is a fixed image without labels or zoom; QA renders need the world pre-composed
  (TD-084).
