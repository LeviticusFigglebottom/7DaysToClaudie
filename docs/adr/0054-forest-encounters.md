# ADR-0054: Forest encounters

**Status**: Accepted · 2026-10 (round 3).

## Context
The owner: the world is too town-oriented. Between the towns the forests are empty: the wilderness
pool (world_gen.json) holds 17 big set pieces, one every few square kilometres, and nothing small.
7 Days to Die and The Forest scatter small finds through their woods every few hundred metres: a
campsite, a wreck, a hunting stand, a body, a cache. We want that density in both the main map and
random worlds, without touching the composer (goldens and region caches stay as they are) and
within the streaming budgets of ADR-0038.

## Decision

### 1. Encounters are data (`data/encounters/*.json`, `EncounterDef`)
An encounter def names its **kind** and how to place and dress it:
* placement: `weight`, `biomes` {biome: weight}, `radius`, `slope_max` (degrees over the radius),
  `road` [min, max] metres from a road's edge (optionally of `road_surfaces`), `min_building`,
  `min_water`, `max_per_region`, `snap: "road"` (moved onto the nearest road's verge within the
  cell, turned along it: wrecks), `anchor: "tree"` (stood at the foot of the nearest collidable
  tree of the vegetation scatter: the ladder stand), `clear` {trees, brush} (metres of forest hidden
  around it);
* dressing (kind `scene`): `props` (prop or `one_of`, site-local `pos`, `rot`, `y`, `variant`,
  `chance`, `id`, `container`), `loose` items, a `notes` pickup, `sleepers` {chance, count, enemies,
  poses, ring}; `tier` is the loot tier of its containers and the infected-tier bonus of its sleepers;
* kind `poi`: `poi`, a tiny building (zoning `encounter`, which no lot has, so no town draws it).

Unknown fields are errors; prop, container, item, note, enemy, biome and POI references are
validated. The first set (`forest.json`): abandoned campsite, ladder stand (anchored), ground
blind, wreck on the track and logging truck (road-snapped), broken-down ATV, hermit's shack (the
`hermit_shack` POI, one a region at most), Cordon body-bag drop (a small group of lying sleepers),
survivor's cache under a tarp, Bloom-grown kill, lone grave. Notes, containers and loot tables of
their own (`notes/`, `items/`, `loot/*/encounters.json`); nine new props (`props/encounters.json`,
generator `props_encounters.py`).

### 2. The planner (`EncounterPlanner`, pure data, worker-safe)
* The world is cut into a **global grid of `cell` m squares** (128 m); a cell belongs to the region
  holding its centre. A site's id is its cell (`enc:<cx>_<cz>`): stable whatever reads it (a main
  map region, a random world of any size), and at most one site a cell.
* Each cell has its own random stream (`Ids.derive_seed(world_seed, "enc:<cell>")`), rolls once
  against `per_km2` (data/config/encounters.json, 10) × the **`encounter_density` world setting**
  (ADR-0014; 0 turns them off, up to 3) × its area, then tries up to `tries` spots, each drawing the
  same randoms whatever passes: the spot's biome weight (config `biomes`: forest 1, burn 0.8, fen
  0.7, rocky slopes and meadows ~0.3, towns and yards never) as a second roll, the region's
  vegetation mask (0 on roads, water, pads, clearings), a def by weight at that biome, then that
  def's own checks, the region's edge (24 m: a neighbour's buildings are not in our data), spawn
  points (80 m) and the spacing (90 m) from sites already planned.
* Roads and water segments are indexed on a 32 m grid; buildings are the region's placements
  (pads, frameworks, lots) as turned boxes. A region plans in ~10-35 ms (1 m Larch Hollow 34 ms).
* Measured (`list_encounters.gd`): Larch Hollow 12-13 sites on its 1.05 km² (forested, hilly); a
  3 x 3 random world (seed 7) 96 over 9.4 km², 10.2 per km²; seed 31, 8.1 per km². Slope is the
  filter that rejects most spots. Road-snapped kinds are rare in random worlds, whose roads mostly
  run between towns (TD-262).

### 3. Streaming (`Encounters`, a GameWorld module)
* On `TerrainManager.region_attached` (and for the regions attached at boot) the region is planned
  on a WorkerThreadPool task (heights through `height_at`, under the terrain lock); a region that
  detaches mid-plan drops the result. Plans are kept for the session.
* Each site is built by **one step**: the streamer's StepRunner in a streamed world (metered by
  StreamMeter as `encounter`), a runner of its own (3 ms a frame) on the main map. A scene site is
  ~5-15 nodes. On `region_detached` the region's queued steps are cancelled and its sites taken
  down (sleepers despawned, awake ones handed to the director as wanderers with our died hook).
* Before building, a site is skipped where a building now stands (`PoiManager.footprint_at`,
  which sees every building of a streamed world, built or not, and `poi_at`) or a player's piece.
* Sleepers spawn within `sleeper_spawn` (46 m) and despawn past `sleeper_despawn` (95 m), as a
  POI's do. Coming within the radius + 6 m marks the site visited (XP `discover_encounter`).

### 4. Vegetation: a runtime mask, not the composer
`VegetationManager.add_clearing(id, at, r_trees, r_brush)` / `remove_clearing(id)`: the
instances inside count as removed (`_is_removed`: hidden, no collision, not harvestable), chunks
already built are rebuilt, chunks scattered later are masked as they arrive. Instance indices and
`WorldState.trees` are untouched, the composer and its goldens never see it: **no
`TerrainComposer.VERSION` or `RwgGenerator.VERSION` bump** and no re-record. The far impostor
layer is not masked (it is discarded inside the near square anyway). An anchored site keeps its
tree (`clear.trees` 0).

### 5. State: differences only, no save bump
`WorldState.encounters` {site id: {visited, dead: [sleeper ids], taken: [pickup ids]}}, written
only when something happens there; containers in `WorldState.containers` as
`enc:<cell>:<prop key>` (LootProp, loot respawn included). The scene is redrawn from the site's
seed on every build (dead sleepers and taken pickups drawn and skipped, so nothing else moves). The
key loads empty from older saves: `SaveSystem.CURRENT_VERSION` stays. The shack is a POI: its
state is `WorldState.pois` under its site id, like any building.

### 6. Other systems' kinds (the API sessions 2 and 3 build on)
```gdscript
Encounters.register_kind(kind: StringName, on_place: Callable, on_unplace: Callable)
Encounters.unregister_kind(kind)
```
`on_place(site)` gets exactly `{id: StringName (stable), kind, def, pos: Vector3 (on the ground),
yaw, region: StringName, seed: int}` when the site's region attaches, and at once for sites
already attached when the kind registers; `on_unplace(id)` when it detaches (or the kind
unregisters). The kind's density, biomes and exclusions come from its data files like every other
kind (a def with `"kind": "nest"`); the plan never depends on who is registered, so a site keeps
its id and place whether the system is loaded or not, and an unregistered kind is simply not
built. The registry is static (a system may register before the module exists); a kind whose
callables died with their object is skipped. Its clearing is opened for it from its def.
`test_encounters.gd` registers a dummy kind.

### 7. The hermit's shack
A real POI (`hermit_shack.json`: a 5 x 4 one-room shack, a sleeper in his chair woken by his
footlocker, the house rules on the door), placed through two small public hunks:
`PoiManager.place_extra(id, def, xf, region)` (a streamed world adds it to the PoiRegistry with
`PoiRegistry.add_extra`, so the ring builds and frees it in steps like any building; the main map
builds it at once, being one room) and `free_extra(id)`. Its floor stands on the highest ground
under its footprint, its yaw the site's; the terrain is not levelled under it (TD-263).

### 8. Tools
* **F8** (debug builds): every planned site within 400 m, a ring the size of its clearing (green
  built, grey planned but not standing), its id, def, kind, distance and state.
* `godot --headless --path game -s res://src/tools/cli/list_encounters.gd -- [--world DIR |
  --world-seed N [--world-set size=4]] [--region RID | --all] [--density D] [--spacing S]`:
  the sites, the planner's time and a per-def tally per km².

## Consequences
+ Every few hundred metres of forest holds something to find, in every world, from data alone; a
  new kind is a JSON def (and, for new behaviour, a registered kind).
+ Nothing composed changes: goldens, region caches and saves are untouched; the module adds one
  worker plan per attached region and one short step per site.
+ Wildlife nests, wolf dens and cave mouths reuse the same placement, ids and streaming.
- A dig before a region's first plan in a session can move a slope check (heights are read
  through `height_at`): the plan is then not exactly the pristine one (TD-261).
- Sites keep to their own region (24 m off its edges); a neighbour's building or road near the
  border is not seen by the planner, only by the build-time footprint check (TD-260).
- Sleepers sit and lie on bare ground (no seat anchors), props stand upright on slopes, the
  ladder stand cannot be climbed yet (TD-264, TD-265).
