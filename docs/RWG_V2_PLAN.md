<!-- Planning document for ADR-0038 (streamed worlds) and ADR-0040 (organic towns). Written by a
planning agent from the code at c8c76d3; the implementers update it as phases land. -->

> **Who does what** (the hub, docs/WORKBOARD.md):
> * **The hub's agents:** Phase 1 (measure, then speed up the composer and the generator; worldgen
>   and tools only), the generator side of Phase 4 (sizes to 16, town density, place caps, map
>   glyphs, presets), and Phase 5 (organic towns). The pure town planner can start alongside
>   Phase 2.
> * **Session 3:** Phases 2 and 3 (terrain and POIs stream: the load path, TerrainManager,
>   RegionStreamer, StepRunner, PoiManager, PoiBuilder phases, the loading screen), and the save
>   side of Phase 4 (v7, the world bundle, the migration). Phase 2 starts once Phase 1's golden
>   test and composer cancellation have landed.
>
> **Numbers:**
> * ADR-0038 (streamed worlds): the hub's Phase 1 agent creates it, with the budgets; session 3
>   adds Phases 2–4.
> * ADR-0040 (organic towns): the hub. ADR-0039 belongs to session 2.
> * TD: the hub 110 and 115–125; session 3 105–109 and 126–130.
> * Save version 7: session 3, in Phase 4.

# Random worlds v2: plan for streamed regions, 10–16 km maps and organic towns

This is a read-only planning pass; I ran no code. Every timing below comes from ADR-0031, ADR-0036 or the TD entries, or is an estimate. Estimates are marked "(est.)". Assumptions are tagged [A#] and listed in §8.

## 0. Where v1 leaves us, and what to settle first

**What v1 does today** (checked in the tree at c8c76d3, plus O2's in-flight ADR-0031 edits):

**Load.**
* `WorldLoader.load_world` → `_compose_parallel` composes every region of a generated world at 1 m, on up to three `Thread`s.
* `_resolve_lots` then resolves and generates every lot of every framework.
* `GameWorld._on_world_loaded` queues the boot steps, and `PoiManager._place_all` queues a plan step and a build step for every building of every detailed region.

**`TerrainManager.setup` fixes the world's shape at load:**
* `_build_grid` runs once.
* Each detailed region gets one material with two 1025² splat textures.
* `TerrainHoles.from_regions` runs once.
* `BloomField.build` covers the union of all detailed regions at 2 m per texel, and one global texture holds it.
* A far tile is built for every region.

**These systems assume every region exists at setup:**
* `WaterSystem.setup_world` and `BridgeBuilder.setup_world` read detailed and coarse metadata. Bridges take their ground from `height_at`, so where no 1 m region exists their piers stand on 16 m heights.
* `RoadMarkings.setup_world`, `VegetationManager._build_far_layer` and `PoiManager._place_all` loop over the detailed regions.
* `GameWorld._find_spawn` reads `_loader.detailed`.
* `TerrainManager.load_from` silently drops deltas for chunks outside the loaded regions, and never applies them later.
* `VolumeTerrain.load_from` initialises every saved column from whatever `height_at` returns at load.
* `PoiManager.poi_at` tests world AABBs, which is wrong for rotated, closely packed buildings.

**Generator limits:**
* Sizes run 2–7; `towns` is at most 10.
* Each town must fit inside one region with a 72 m margin (`inside_one_region`), because local features fade within 48 m of a border.
* The drop site may be as close as 60 m to a border.
* `RwgMap.GLYPHS` only covers A–G and 1–7.
* `_biome_map`'s per-region dominant-biome loop costs O(regions × biome cells): 256 × 65k at 16×16.
* `_places` caps each pool entry with a per-world `max`, so big worlds would be nearly empty.
* There are only 30 town names.

**Coordination with the hub:**
* **Session 3 owns files v2 rewrites:** `game_world.gd`, `world_loader.gd`, PoiManager's placement path, `PoiBuilder.build`'s validator argument, and the terrain/vegetation thread fixes. The hub must hand them to the v2 stream when session 3's current round merges. Until then, only Phase 1 can start; it touches worldgen and tools, which the RWG stream owns.
* **Session 2 owns additive hunks in `game/src/ai/`.** v2 needs small additive hunks in `ai_director.gd` and `nav_tiles.gd`; announce them through the hub.
* **Numbers:** ADR-0038 (streamed worlds), ADR-0040 (organic towns) [A1], TD-110 and up, save version 7.

---

## 1. Streaming architecture

### 1.1 What becomes on-demand

| System | Today | v2 |
|---|---|---|
| 1 m region composition (heights, splats, biome, vegmask, metadata) | Every built region, at load | `RegionStreamer`: the first area at load, the rest in the background. Cached on disk; unloaded beyond 1100 m. |
| 16 m coarse composition | Only unbuilt regions (main map) | Every region of every world at load, cached (`_1600.bin`) and kept all session. Used for far tiles, water and bridge metadata, and as the `height_at` fallback. |
| Near terrain chunks and collision | ±6 / ±2 chunks around the player | Unchanged. Chunks in and around a region are re-meshed when it attaches or detaches. |
| Far tiles | One 16 m tile per region, built once | 16 m tile plus a 64 m LOD per region. A region and its 8 neighbours re-mesh when the attached set changes. |
| POI buildings | All at load | Per building, by distance (see §1.2). Plan on workers, build in main-thread phases, free beyond the ring. |
| Framework fixtures | All at load, one body and mesh each | Per 64 m cell with the POI ring, batched into MultiMeshes. Container fixtures stay `LootProp`s. |
| Cellar holes | `TerrainHoles.from_regions` once | Added and removed per built POI (copy-on-write), so no pit shows where no building stands. |
| Vegetation, near | Streamed | Unchanged. It already skips chunks with no detailed region. |
| Vegetation, far impostors | Every chunk of every detailed region | Per attached region: a group task on attach, freed on detach. MultiMesh buffers are built on workers. |
| Water surfaces | World-wide, on the main thread | Still world-wide (cheap, world-level data). Vertex arrays, including `_tree_line`, are computed on workers and meshes added in boot steps. |
| Bridges | All, at setup | Per attached region; the owner is the region of the span's midpoint. `plan()` runs on a worker. |
| Road markings | Every road of every detailed region, one `Decal` per stripe | Per 64 m chunk within ±2 chunks (the decals fade at 80 m anyway). |
| Bloom field | One grid over all detailed regions, one global texture | One 512² tile (2 m) per attached region, composed in its job. A window texture covering 3×3 regions is re-centred when the player changes region. |
| Nav tiles | ±2 tiles (32 m) | Same radius. Never baked over a non-attached region; rebaked when a region attaches or a POI in range is built or freed. |
| Terrain height deltas | Applied at load to the regions present | Decoded at boot into `_deltas`; applied per region on attach, on the worker. |
| Volume (tunnels) | Every saved column activated at load | Activated when its region attaches. Densities stay in memory on detach; only nodes are freed. |

### 1.2 Rings, radii and budgets

All numbers go in a new `game/data/config/streaming.json`, which ContentDB loads like every config. A `StreamingConfig.errors()` check runs in `make validate`.

```json
{"region": {"load": 640, "unload": 1100, "prefetch": 1400, "prefetch_ahead": 400, "first_area": 300,
            "max_attached": 9, "threads_runtime": 2, "threads_loading": 4, "bands_first_area": 4},
 "poi": {"plan": 600, "build": 450, "free": 560, "max_built": 90, "fixture_cell": 64},
 "markings": {"chunks": 2},
 "budget_ms": {"runtime": 4.0, "overlay": 40.0, "step_target": 8.0},
 "cache": {"detail_max_mb": 2048}}
```

| Ring | Radius (hysteresis) | Contents | RAM | VRAM | Time budget |
|---|---|---|---|---|---|
| A active | ≤128 m (existing radii) | Collision ±2 chunks, nav ±2 tiles, sleepers 46/95 m, loose physics 96 m, ground cover ±1 chunk | ~5 MB | small | Unchanged |
| B near | Terrain ±6 chunks (≈480 m), vegetation ±3, markings ±2. POIs: plan ≤600 m; build the nearest ≤90 within 450 m; free beyond 560 m | Near meshes, near scatter, built POIs, fixtures, decals | POIs are the main unknown: est. 1–2 MB each, so ≤180 MB | Near terrain ~4 MB; POI batches to be measured | Every main-thread step ≤8 ms; streaming work ≤4 ms per frame |
| C detail | Regions whose rect lies within 640 m; unload beyond 1100 m; at most 9 attached | 1 m RegionTerrain (14.7 MB: heights 4.2, splats 8.4, biome 1, vegmask 1), a pristine copy only if dug (4.2 MB), far impostors, bridges, Bloom tile | ≤170 MB | Splat textures only for regions under the near square (≤4, so ≤34 MB); impostors ~2 MB per region | Compose ≤10 s on the container or ≤5 s on a desktop, per region on one low-priority thread. Cache load ≤150 ms. Attach on the main thread ≤30 ms in total. |
| D prefetch | ≤1400 m, plus 400 m ahead of the heading | Composed into the disk cache, not kept in RAM | 0 | 0 | Lowest priority |
| E world | Every region | Coarse 16 m RegionTerrain (~60 KB each, est.), far tiles, water, PoiRegistry | ~15 MB coarse plus ~2 MB registry at 16×16 | Far tiles ~45 MB at 16 m plus ~3 MB at 64 m LOD (16×16) | Coarse compose ≤60 ms per region after Phase 1; ≤10 ms from cache |

Why 640 m: the near square reaches 416 m plus one 64 m chunk. A 640 m load radius leaves about 160 m, which is 26 s at sprint (6.2 m/s, `player.json`). Prefetch at 1400 m starts composing about 2 minutes ahead at sprint. Rect distance means 4–9 regions are attached, never more, which caps RAM.

### 1.3 Worker threads and the handoff to the main thread

**RegionStreamer** (new: `game/src/world/region_streamer.gd`, a child of TerrainManager).
* It owns `threads_runtime` dedicated `Thread`s started at `Thread.PRIORITY_LOW`, and `threads_loading` during the loading screen. They are not WorkerThreadPool tasks: composes run for seconds, must be cancellable, and must never starve chunk meshing or scatter.
* Jobs sit in a Mutex+Semaphore priority queue. Priority = rect distance − 300 × dot(heading, direction to the region). Jobs no longer wanted are dropped before they start.
* Job kinds:
  * `LOAD`: `RegionTerrain.load_cached`.
  * `COMPOSE`: `TerrainComposer.compose(..., cancel)`, then an atomic cache write.
  * `PREFETCH`: compose and write; the result is dropped unless the region is wanted by then.
* After LOAD or COMPOSE the worker also:
  1. copies the pristine heights if the region has deltas (snapshot passed in at enqueue);
  2. applies the deltas;
  3. composes the Bloom tile.
* Results go into an `out: [null]` slot created before the job starts (the TD-104 pattern).
* `_exit_tree` sets every `cancel[0] = true`, posts the semaphore and joins. The composer checks `cancel` at each `_report` and every 64 rows, so quitting waits about 0.2 s.

**First area.** `TerrainComposer.compose(world, rid, spacing, progress, cancel, bands)` gains a row-band mode for the per-sample passes `_macro_and_noise`, `_apply_water`, `_apply_roads` and `_surface_pass`.
* Each band runs on a dedicated `Thread` and writes its own packed arrays (`h`, `dnoise`, `splat0/1`, `biome`, `vegmask`), merged after the join. Writing one shared PackedArray from several threads is unsafe: copy-on-write can silently fork it.
* Field rasterisation, pads and cliffs stay sequential.
* Expect about 3× on 4 threads (est.). Output must be byte-identical (§6, the golden test).
* FastNoiseLite is already read concurrently by v1's parallel composer [A7].

**WorkerThreadPool** (existing pattern: result slots, polling on the main thread):
* POI planning: `LotPicker.def_for`, `Dressing` roll and resolve, `PoiLayout.compile`, `PoiValidator._run`.
* Far impostor scatter (low priority).
* Far-tile vertex arrays, bridge `plan()`, marking stripe layout, water vertex arrays.
* Nav bakes (async, existing).

New worker paths return Packed arrays only; the main thread creates the RIDs (`add_surface_from_arrays`, `MultiMesh.buffer = …`). This keeps out of TD-103's headless RID race.

**Main thread: `StepRunner`** (new: `game/src/app/step_runner.gd`, factored out of `GameWorld._run_boot_steps`).
* Steps keep the `[label, Callable, name]` format, and the "return false = waiting on a worker" convention.
* Budget: 40 ms per frame during the boot or a blocking overlay; `budget_ms.runtime` (4 ms) in play.
* At runtime it is a priority queue keyed by distance.
* Every step aims at ≤8 ms. Anything larger gets split: PoiBuilder phases, one MultiMesh per step, decals per chunk, a few far tiles per step.

**Attach steps for region R:**
1. `TerrainManager.attach_region(rt, pristine)`: copy-on-write `_grid` swap, `_base_cache[rid] = pristine` if dug, emit `region_attached`.
2. Re-mesh live near chunks in R plus a one-chunk border (async). Rebuild collision for chunks within ±2 (one step per chunk). Lift the player or frozen bodies that now sit below the ground (`ground_below`).
3. Re-mesh the far tiles of R and its neighbours on workers; swap a few per step.
4. Start the vegetation far scatter; one step per species MultiMesh.
5. Build bridges: plan on a worker, one step per bridge.
6. Re-blit the Bloom window, if R is inside it.
7. Activate R's saved volume columns.
8. Mark R's nav tiles dirty.
9. Place the drop-site spawn props, if R holds the `drop_site` spawn.

Detach reverses this, and also erases `_materials[rid]` and `_base_cache[rid]`.

**Thread safety:**
* `_grid` is replaced whole and the old one kept for `RETIRE_MSEC`, like `_publish_heights`.
* `region_terrain_at` uses the grid entry plus a new `RegionTerrain.detailed: bool`, not the `regions` Dictionary.
* `_far_tile_mesh` jobs get snapshots of the attached rects; they never read `regions`.
* `TerrainHoles` stays immutable; every change publishes a new object.
* Bloom tiles are published copy-on-write.

### 1.4 How far terrain covers regions that aren't composed

* Every region has its coarse 16 m RegionTerrain. Its far tile (heights, splat-derived colours) is raised by canopy × 17 m where the biome is forest (`_far_canopy_grid`), exactly as unbuilt regions look on the main map today.
* An attached region's far tile is re-meshed from its 1 m data at 16 m and drops the canopy, because its impostors take over. Neighbours fade their canopy within 48–192 m of it.
* Each region gets a second, 64 m far mesh. `visibility_range` is 0–3000 m for the 16 m mesh and 3000–9000 m for the 64 m one (the camera's far plane is 9000 m), which keeps a 16 km view under the 4 M triangle budget.
* Near chunks that reach a non-attached region (only when the player outruns streaming) use the coarse splat material (the existing branch of `_material_for`). They re-mesh on attach. Coarse materials are kept in a small LRU of 9.
* Water surfaces are world-wide from load. Bridges beyond the detail ring are not drawn (TD), so a far river shows a gap at a crossing. Towns beyond the POI ring show their pads and streets only, until POI proxies land (§6, Phase 5).

### 1.5 What persists when a region unloads

What WorldState covers and what v2 must add:

| State | Stored in | Gap in v2, and the fix |
|---|---|---|
| Terrain digs | `chunk_blobs["t:cx_cz"]` (65² deltas) | `load_from` applied deltas only to regions present at load. **Fix:** decode every blob into `_deltas` at boot; apply per region on attach (on the worker); keep the pristine copy for the dig limit (`_base_heights` must never copy already-edited heights); `save_into` is unchanged. |
| Tunnels | `chunk_blobs["v:x_y_z"]` plus `flags.volume_columns` | Activation reads `base_height_at`, which would be coarse for a far region. **Fix:** activate columns on attach. Keep `VChunk.density` on detach (only nodes are freed), so `save_into` still writes edited chunks. |
| Felled and harvested plants | `trees[chunk][index]` | Covered. The far layer reads `_removed` when it scatters each region. Indices stay valid only while composer output for the same inputs stays byte-identical (§5). |
| POI state | `pois[instance_id]` (doors, broken, hp, traps, dead, triggers, roused, picks, visited, cleared) | Covered; written in place. Legacy `keys: 1` states re-key when the building is next built (already lazy). |
| Picks pinning | `poi_state(id)["picks"]` | `dress_for` creates a state entry (a mutation), so it can't run on a worker. **Fix:** snapshot pinned picks on the main thread when scheduling the plan; pin them when the build starts. |
| Containers | `containers[id]` | Covered: write-through on roll and on change (`LootProp`). |
| Sleepers | `dead` and `roused` | Covered: `despawn_sleepers` runs before freeing. |
| Structures and blueprints | `structures`, `blueprints` | Covered: restored world-wide at load; static bodies; the saved `grounded` flag needs no terrain. Never emit `terrain_modified` on attach, or logs would re-ground. |
| Loose items and logs | `loose` | Already frozen beyond 96 m. **Fix:** the rescue (`p.y < ground - 1.5`) only runs inside an attached region, otherwise it would lift items to coarse ground. |
| Supply drops, Bloom mounds | `drops`, `mounds` | Covered: static, at saved positions. Mound spots outside the Bloom window wait until it moves. |
| Drop-site canister | Not saved (spawn props) | `_place_spawn_props` reads `height_at` at spawn time. **Fix:** place it on attach of the drop-site region. |

### 1.6 The disk cache for composed regions

* Path and format are unchanged: `user://cache/worlds/<world id>/<rid>_<spacing×100>.bin`, HMRT.
* **`input_hash` keeps the same formula,** so v1 caches stay valid. But `WorldDef` holds the bytes of `world.json` and `frameworks.json` once, and memoises each region's hash (today every call re-reads about 3 MB and re-parses `region.json`). The hash runs on the job thread.
* **Atomic writes:** `RegionTerrain.save` writes `path.tmp`, then renames. `load_cached` rejects short reads (truncated means a miss).
* **LRU:** `user://cache/worlds/index.json` holds `{world_id: {file: [bytes, last_used]}}`. After each 1 m write, it trims to `cache.detail_max_mb`, oldest `_100.bin` first, across worlds. It never evicts `_1600.bin` files of worlds named by a save.
* `RwgWorlds.prune` keeps deleting the caches of pruned worlds.

### 1.7 Data shapes

```gdscript
# RegionStreamer (Node)
signal region_attached(rid: String)        # re-emitted by TerrainManager for modules
signal region_detached(rid: String)
enum State { COARSE, QUEUED, WORKING, READY, ATTACHED }
class Slot:  # per region
    var rid: String; var rect: Rect2; var built: bool; var state: int
    var hash: String; var cached: bool       # filled by a hash job at load
    var job: Dictionary                      # {kind, priority, cancel: [false], out: [null], deltas: {...}}
var focus_points: Array[Vector3]             # players (co-op ready); GameWorld.stream_focus for tools
func update(velocity: Vector3) -> void       # every 0.25 s from TerrainManager._process
func request_now(pos: Vector3, radius: float) -> void   # first area, teleport, respawn
func pin(key: StringName, rect: Rect2) -> void          # the Hum base during a Hum
func is_area_ready(pos: Vector3, radius: float) -> bool
func status() -> Dictionary                  # {attached, queued, working, late_s, last_attach_ms}
```

```gdscript
# PoiRegistry (RefCounted, built on the loader thread; pure data, no generation)
entries: {instance_id: {id, kind: "poi"|"lot", region: rid, placement: id, framework: fw_id,
          lot: {...}, frame: [cx, cz, w, d, yaw_deg], y: float|NAN,
          pick: {kind, def_id|template, seed, size}}}
by_region: {rid: [ids]}
grid: {Vector2i(64 m cell): [ids]}
func footprint_at(p: Vector2) -> StringName
func def_id(id) -> StringName
func near(p: Vector2, r: float) -> Array
```

---

## 2. What changes in each system, file by file

**Worldgen**
* **`worldgen/terrain_composer.gd`**
  * `compose`/`get_or_compose` gain `cancel` and `bands` parameters; cache writes become atomic.
  * Memoised `input_hash` (formula unchanged).
  * `_build_profile` takes world-graded road profiles from a per-world cache in `WorldDef`. With `road_grade == "world"` they depend only on world data, and every region today recomputes the whole road (est. 25 ms per road per region).
  * `_metadata` samples only the arc range of a road or river that overlaps the region margin.
  * `_surface_pass` and `_pad_at` bucket pads, paints and paths in a 32 m index. Order is preserved (lowest pad index wins; paints in index order).
  * Phase 5 adds world towns (§3.10).
  * `VERSION` stays 11: every change is output-identical for existing inputs.
* **`worldgen/world_def.gd`**
  * Keeps raw `world.json`/`frameworks.json` bytes and a memo of region hashes.
  * Adds a `road_profile(i)` cache behind a mutex.
  * Sets `corner_heights = []` after flattening into `_corners` (the nested Array is about 20 MB at 513²).
  * `macro_height` skips the noise calls when the amplitudes are 0 (identical output).
  * Adds `towns: Array[Dictionary]` (Phase 5) and an optional binary macro grid (`macro.grid: "macro.bin"`, Phase 4).
* **`worldgen/region_terrain.gd`**: atomic `save`, robust `load_cached`, a `detailed: bool` flag, `memory_bytes()`.
* **`worldgen/rwg/rwg_generator.gd`**
  * `VERSION` 2 in Phase 4, 3 in Phase 5.
  * Drop site at least 300 m from a region border, falling back to 200, then 120, then 60 m.
  * Town count from a density setting; place caps per 16 km²; sub-progress inside long stages.
  * `_biome_map`: compute region dominants over each region's own cells.
  * Spatial indexes (a shared `SpatialGrid` helper, 256 m cells) for `nearest_road`, `road_clearance` and `_hits_built`.
  * Phase 5: town centres, a network routed through them, the `towns` list in `world_json()`, `region_json` without town features, and `_finalize_town_heights()`.
* **`worldgen/rwg/rwg_terrain.gd`**: profile `_flood` and `_carve` at 513². No flatten under towns in v2; at most a gentle core smoothing (Phase 5).
* **`worldgen/rwg/rwg_roads.gd`**: `route` gains a valley term (cost by height relative to the local 300 m mean) and a `route_fine()` on an 8 m local grid for in-town refinement (Phase 5).
* **`worldgen/rwg/rwg_towns.gd`** is replaced by the organic planner `rwg_town_planner.gd`, plus `rwg_streets.gd` and `rwg_lots.gd` (§3).
* **`worldgen/rwg/rwg_worlds.gd`**: `trim_cache()` (the LRU), `bundle(dir) -> PackedByteArray` and `unbundle()` for saves (ZIPPacker/ZIPReader), and writing the `towns` data.
* **`worldgen/rwg/world_gen_settings.gd`**: `size` max 16; `town_density` replaces `towns`; new `TOWN_KEYS`/`KIND_KEYS` for the organic tuning; `generator_version` in `to_dict()` (not in `key()`).
* **`worldgen/rwg/rwg_map.gd`**
  * Glyphs for H–P and 0, 8, 9; two-digit row labels.
  * World towns drawn from lot frames, parcels and streets.
  * `render_progress(img, marks)` overlay for the loading screen.
  * 1024 px stays the file size (2048 px would cost ~6 s, est.).

**World**
* **`world/world_loader.gd`** (new flow):
  1. Generate, or read the world and register its frameworks.
  2. Build the `PoiRegistry`.
  3. Hash and coarse-compose every region on `threads_loading`.
  4. Find the spawn: the drop site from `region_data` spawn features for a new game, else the saved player position.
  5. Compose the first area at 1 m with `bands`.
  6. Plan the POIs within the first POI ring.
  7. Report progress.
  * `_compose_parallel` and all-region `_resolve_lots` go away.
  * New outputs: `first_area`, `coarse`, `registry`, `planned`, `spawn`, `map_path`, `marks`.
* **`world/terrain/terrain_manager.gd`**
  * Adds `attach_region`/`detach_region`, a copy-on-write `_grid`, and lazy per-region materials (created on first near-chunk use, freed on detach).
  * `region_attached`/`region_detached` signals; the streamer is created in `setup`.
  * `load_from` decodes all deltas into `_deltas`; the per-region apply runs in jobs.
  * Far tiles: `_far_tile_mesh(rid, attached_rects_snapshot)`, 64 m LOD, neighbour re-mesh.
  * `holes` add/remove per built POI; `is_area_ready()`; Bloom tiles.
  * **Assumption broken:** `_grid`, `regions` and `_materials` are fixed after `setup`.
* **`world/terrain/terrain_holes.gd`**: `with_poi(id, def, xf)` and `without(id)` return new instances. `placed_pois` is replaced by `LotPicker.lot_local_xf`, so the lot transform math lives in one place (today PoiManager duplicates it).
* **`world/terrain/volume_terrain.gd`**: `activate_region(rect)` on attach; `free_nodes_in(rect)` on detach, keeping densities. **Assumption broken:** every column is activated at load.
* **`world/vegetation/vegetation_manager.gd`**: `_build_far_layer` becomes `_far_attach(rid)`/`_far_detach(rid)`. `_scatter_far_chunk` results are packed into PackedFloat32Array MultiMesh buffers on the worker. **Assumption broken:** the far layer covers `terrain.regions` at setup.
* **`world/water/water_system.gd`**: `setup_world` computes vertex arrays (the costly `_tree_line`) on workers and adds meshes in boot steps. Merged rivers are cut into pieces of about 512 m for culling. A 32 m grid index for lakes in `water_level_at`.
* **`world/bridges.gd`**: per-region `attach`/`detach`. A span is built once both its end regions are attached; `_river_fn` reads the attached regions. **Assumption broken:** every bridge exists at setup, on whatever ground `height_at` gave (coarse).
* **`world/road_markings.gd`**: stripe layout per road on attach (worker), bucketed by 64 m chunk; decals created and freed for chunks within ±2.
* **`world/loose_items.gd`**: rescue only where `region_terrain_at(p)` is detailed.
* **`world/supply_drops.gd`**: `spot_ok` also rejects `registry.footprint_at` (unbuilt buildings).
* **`world/bloom/bloom_field.gd`** and **`bloom_world.gd`**
  * `BloomField.build_region(world, rid, rt, cfg)` builds the zones of R plus border-crossing zones of its 8 neighbours (from their `region_data`), and `mask_ground` against R only.
  * `BloomWorld` assembles a 1536² window over 3×3 regions (`blit_rect`) and sets `hm_bloom_rect` to the window.
  * `at`/`base_at` look up the tile by region.
* **`world/bloom/bloom_mounds.gd`**: no change; spots land in the window.
* **New `world/region_streamer.gd`.**

**POIs**
* **`poi/poi_manager.gd`**
  * One slot per instance: `UNPLANNED → PLANNING (worker) → PLANNED → BUILDING (phases) → BUILT → FREEING`.
  * Builds the nearest `max_built` within `poi.build`; frees beyond `poi.free` or rank > max+15.
  * `dress_for` is split into `dress_inputs()` (main thread) and static `dress_with()` (worker-safe).
  * Fixture cells; `poi_at` tests the point in each instance's local frame, through a 64 m grid; `footprint_at` delegates to the registry.
  * Signals `poi_built(id, aabb)`/`poi_freed(id, aabb)`, used by nav and holes.
  * **Assumption broken:** `_place_all` at setup.
* **`poi/poi_builder.gd`**: `static start(layout, id, checked) -> PoiBuilder` plus `step() -> bool`, which runs one phase of `_build`'s sequence per call. The sequence: shell, `_walls`, `_posts`, `_floors`, `_galleries`, `_stairs_and_ladders`, `_openings`, `_exterior`, `_roof`, `_props`, `_scatter`, `_lights`, `_interior_probes`, `_pickups`, `_decals`, `_traps`, `_emit_batches` (k batches per step, using `MultiMesh.buffer`), `_wire_weak_floors`. `build()` stays a loop over `step()` for tools and tests (closes TD-102's item).
* **`poi/lot_picker.gd`**: `lot_size` reads `frame` when present; adds `lot_local_xf(l, footprint)` and `assign_authored(towns, seed, cap)` (Phase 5, v2 worlds only).
* **`core/content/defs/framework_def.gd`**
  * `LOT_KEYS` gains `frame`, `poly`, `street`, `ring`, `y`, `pad`.
  * A lot needs either `rect` or `frame`.
  * `_fields` gains `layout`, `center`, `radius`, `kind` and `plaza`.
* **New `poi/poi_registry.gd`.**
* **`poi/interior_probe_budget.gd`**: no change; it already tracks probes added and removed in the tree.

**AI**
* **`ai/nav/nav_tiles.gd`**: `_bake` skips tiles whose rect isn't attached; `_mark` on `region_attached`, `poi_built` and `poi_freed`.
* **`ai/ai_director.gd`**: `spawn_point_ok` also rejects `registry.footprint_at`. Today a wanderer could spawn where a building is about to stand.
* **`ai/horde/hum_director.gd`**: on `_on_start`, `pin(&"hum", rect around base)`; unpin in `_on_end`. Otherwise unchanged: the base is within rings A and B, and the flow field's houses are among the nearest built.

**App, UI, progression**
* **`app/game_world.gd`**
  * New load flow, a runtime StepRunner, and `stream_focus`.
  * `_find_spawn` reads the registry or `region_data` for x/z and the attached region for y.
  * `respawn()` and debug teleports become `await_area(pos)`: request the area, show the "Finding your feet…" overlay, then place the player.
  * `is_settled_around(pos, r)` for QA tools; `_place_spawn_props` on attach.
* **`app/load_meter.gd`**: adds `StreamMeter` (the longest frame inside StreamQueue steps and its label, per-step costs, late seconds), logged every 60 s and shown in F4.
* **`ui/game_ui.gd`**: loading screen with the map, per-region marks and a cancel button (§4); a small HUD hint "The land ahead is still forming…".
* **`ui/tether.gd`**: `_draw_markers` takes POI markers from the registry plus `WorldState.pois` (unbuilt places show).
* **`ui/new_game_panel.gd`**: size up to 16, with a note that first starts take about a minute.
* **`progression/directive_tracker.gd`**: `_poi_def` falls back to `registry.def_id`.
* **`debug/debug_overlay.gd`**: teleports wait for the area; streaming stats.

**Core**
* **`core/save/save_system.gd`**: `CURRENT_VERSION` 7, `_v6_to_v7`, the world bundle (§5).
* **`core/session/game_session.gd`**: `world_files`; `world_gen.generator_version`.

**Tools**
* `compose_region_runner.gd`: `--bands N`, `--spacing 16`, per-stage timings (already printed with `--no-cache`), memory.
* `rwg_preview_runner.gd`: `--compose` coarse-only by default plus `--detail x,z,r`; prints generator sub-stage timings.
* New `stream_walk.gd`/`stream_walk_runner.gd` (a thin SceneTree, per the CLAUDE.md gotcha) and a `make stream-check` target.
* `walk_tour_runner.gd`: `--world random`.
* `screenshots_runner.gd`: `--world random …` (TD-084) and waits for `is_settled_around`.
* `tools/qa/render_check.sh`: random-world shots.

**Data**
* `data/config/streaming.json` (new).
* `world_gen.json`: size max 16; `town_density`; organic town tuning; place caps per 16 km²; ≥60 town names; big-world presets ("Large county 10 × 10", "Wide country 16 × 16").
* `biomes.json`: a `yard` biome (meadow grass and flowers only, no trees or bushes; spawn_density ≈ town).

**Docs**: ADR-0038 and ADR-0040; REGIONS.md (streaming, the `towns` key, lot frames); DESIGN §10.2 status; POI_AUTHORING.md (lot frames); TECH_DEBT (close TD-007/081, update TD-082/083/084, add TD-110+).

---

## 3. Organic towns

### 3.1 Decisions

* **Towns become world-level features.** world.json gets `towns`, and the composer applies a town in every region it touches, without the 48 m border fade. Today's rule that a town must fit inside one region with a 72 m margin caps a town at 880 m and pins its centre to the middle of a region. Organic towns of 700–900 m must be able to straddle borders.
  * Seamless joins come from the mechanism world roads already use. Streets are world-graded (`_reference_ground`: macro plus the shared world noise). Lot pads take a target height `y` precomputed from the same reference ground. Both sides of a border therefore compute identical samples.
* **Lots stay rectangles for the POI system, rotated freely and set in irregular parcels.**
  * Each lot carries a `frame` (an oriented rectangle: centre, size, yaw; its +Z faces its street) and an optional parcel polygon `poly`.
  * Why rectangles:
    * buildings are rectangular kit grids (ADR-0009) validated in their own frame;
    * generated buildings fill a rectangular lot;
    * cellars cut the terrain from plan cells;
    * an arbitrary yaw is already supported by placement transforms, `TerrainHoles` (world-XZ quads), `FlowField.add_buildings`, nav parsing and probes.
  * Irregularity comes from four sources: streets that follow contours, per-lot yaw along curved streets, varied frontage and depth, and gaps where slope or water reject a lot.
  * Parcels serve the map, optional fences and yard ground. Polygon lots with non-rectangular buildings would need a polygon-aware generator and validator; that is a TD entry.
* **No town-wide flat pad.** Every lot has its own pad. A town on a slope reads as terraces along streets graded by profile.

### 3.2 Generator order (v3)

1. Land; lakes and rivers.
2. **Town sites and size classes:** centres and radii; no flattening; optional core smoothing (blend the macro grid 50% toward its local mean within 0.8 × the core radius).
3. **Road network through the centres:** MST plus loops plus exits as in v1. A* targets are town centres; towns are not blocked; the valley term applies. Extra "stub arterials" bring every town to 1–3 arterials (county roads out along the valley axis to radius + 150 m).
4. **Per town** (independent, so it can run in parallel; RNG `rng("town:<id>")` with sub-streams `streets`, `lots`, `fixtures`):
   1. refine each arterial inside the town disc with `route_fine` (8 m grid) and splice it back into the world road;
   2. grow side streets (§3.5);
   3. place lots (§3.6), assign zoning (§3.7), lay fixtures (§3.9);
   4. block lot frames in the router.
5. Drop site, danger, biome map. The town ring comes from the town discs, with cells inside the disc made meadow or yard.
6. Places with access; `_hits_built` against lot frames (grown 12 m) and street corridors (grown half-width + 8 m) through the spatial grid.
7. Bridges (in-town streets stop at water, so only arterials cross), the Bloom, names.
8. `_finalize_town_heights()`: each lot's `y` = the mean reference ground over the frame on the final grid (25 samples). Then `world_json`, `frameworks_json`, `region_json`.

### 3.3 Sites

* **Candidates:** dry (water distance > 60 m at the centre).
* **Score:** mean slope over the core disc; relative elevation against a 1 km neighbourhood (valleys preferred); water 80–300 m away is a bonus and closer than 60 m a penalty; central bias; distance to the map edge.
* **Hard limits:** core relief ≤ 15 m, disc relief ≤ 45 m, and spacing ≥ r_a + r_b + 300 m.

### 3.4 Arterials

The world road through the centre is the main street. A* already prefers gentle grades, so it follows valleys and contours; the valley term pulls it onto valley floors. Inside the town: asphalt, the world road's width, markings kept.

### 3.5 Street growth (Parish & Müller-style agents, constrained)

* **Seeds** along each arterial, every 55–120 m (denser in the core), alternating sides, branching at 75–105° (`grid_bias` pulls core branches to 90° and straighter).
* **Agent step:** 12 m. Candidate headings: current ±0/12/24/36°.
* **Cost** = 40·|grade| + 0.6·|Δheading/12°| + crowding.
* **Snap:** if another street lies within 16 m at ≥35°, snap and make a T-junction (a loop forms).
* **Reject** steps that run parallel within 60 m of another street at <25° (two back-to-back lot depths need about 66 m).
* **Stop** at:
  * water (water distance < 15 m);
  * two steps steeper than 0.14;
  * the town radius;
  * the street's own length budget (80–320 m);
  * the class budget of total street length.
* **Dead ends** ≥60 m long get a cul-de-sac bulb: a road piece `{points: [end, end + dir*0.1], width: 18, markings: false}` (a disc in the composer's distance field).
* **Second-generation branches** on village (30%) and town (60%) side streets, 60–140 m long; core back lanes in towns.
* **Classes:** street 6 m asphalt, `markings: false`; lane 5 m, gravel in hamlets and outskirts.
* **Blocks** are the faces of the street graph (a planar face walk over the junctions). They are used for map drawing and back-lane infill; lots never depend on them.

### 3.6 Lots: frontage subdivision

* **Walk** each street side from `junction_gap` (crossing half-width + 8 m) to the end − gap.
* **Frame:** at arc s, frontage w and depth d from the zone's ranges; centre = p(s + w/2) + n·(street half-width + verge 3 m + d/2); yaw makes local +Z = −n. [A10: check the sign against `lot_xf`, where facing S is yaw 0 and the front points +Z.]
* **Accept if:**
  * it overlaps no other frame (polygon test through a 32 m hash, 1 m gap);
  * it is clear of every street corridor;
  * water distance > 12 m;
  * reference-ground relief over the frame is ≤3.5 m (residential, rural) or ≤2.5 m (commercial, civic, industrial).
* **Otherwise** shrink frontage and depth down to the zone minimum, then skip 6 m. After a lot, s advances by w + 1–4 m.
* **Sizes fit the content:**

| Zone | Frontage × depth (m) | Fits |
|---|---|---|
| Inner residential | 18–23 × 26–32 | bungalow min 15 × 15 |
| Outer residential | 22–30 × 30–40 | Merrow House 22 × 24 |
| Commercial | 22–32 × 28–36 | |
| Civic | 32–36 × 33–38 | library 32 × 32, fire station 28 × 33 |
| Industrial | 30–44 × 32–44 | logging camp 36 × 28 |
| Rural | 34–60 × 40–60 | |

* **Parcel:** the frame grown sideways to the midline with its neighbours and up to 8 m back, clipped by street corridors (`Geometry2D.clip_polygons`).

### 3.7 Zoning by distance from the centre

* **Rings:**
  * core: d < r_core;
  * inner: d < 0.6 r;
  * outer: d < r;
  * edge: arterials only, up to r + 400 m.
* **Quotas in order:**
  1. commercial along arterials and the plaza, nearest the centre first;
  2. civic around the plaza or arterial crossing;
  3. industrial on edge arterials;
  4. rural on edge arterials and stubs;
  5. residential everywhere else.
* Tier comes from region danger, as in v1.

### 3.8 Size classes (`tuning.towns.kinds`)

| Class | Radius | Arterials | Side streets | Street budget | Lots | Core |
|---|---|---|---|---|---|---|
| Hamlet | 100–140 m | 1 | 0–2 lanes | ≤400 m | 6–14 | 50 m; 1 commercial (roadside); 1–3 rural lots |
| Village | 190–260 m | 1–2 | 3–7; 0–1 loop; 1–2 cul-de-sacs | ≤1.6 km | 22–45 | 80 m; 3–5 commercial, 1–2 civic; 1–2 industrial, 3–6 rural |
| Town | 330–440 m | 2–3, crossing near the centre | 10–18; 2–4 loops; 3–6 cul-de-sacs; core back lanes | ≤5 km | 70–120 | 130 m; plaza 36–48 m (paved pad); 8–14 commercial, 3–5 civic; 2–4 industrial, 4–8 rural |

`town_density` sets towns per 16 km² (default 2.0 [A11]); the `mix` keeps the hamlet/village/town weights.

### 3.9 Fixtures and outskirts

* Lamps every 30–38 m in the core and inner rings.
* Poles along arterials, out to the edge.
* Hydrants every 60–90 m in the inner ring.
* Stop signs on the minor leg of each T-junction.
* Benches, a payphone, dumpsters and a collection box at commercial and civic lots.
* Mailboxes at residential frames.
* Wrecks, litter, and a Cordon barricade with a fire drum at one arterial entry.
* Optional: gravel drives (3 m roads, `class: drive`) from the kerb to each frame.
* Fixture ids are `fx_N`, stable per world, so container ids `c:<town>:<fx>` stay stable.
* Rural lots along arterials and stubs beyond the radius, every 150–300 m (zoning `rural`: ranch house, workshop, Okafor farmhouse and barn), are the outskirts.

### 3.10 Composer extension (additive; main-map output unchanged)

* `WorldDef._parse`: `towns: [{id, framework, origin: [x, z], rotation: 0, bounds: [x, z, w, h], center, kind}]`.
* `_collect_features`, for each world town whose bounds (grown 40 m) intersect the region:
  * adds its `fw.roads` as `world: true` roads (graded by `_reference_ground`, no `_border_weight`);
  * adds one pad per lot: `{kind: "lot", origin: frame corner, rot: yaw, size, skirt: 5, world: true, target: l.y, biome: "yard", veg: 0.6}`;
  * adds the plaza: `{biome: "town", surface: "asphalt", veg: 0}`.
* `_apply_pads`:
  * world pads skip `_border_weight` and use `target`;
  * lot pads multiply their weight by `(1 - road_weight)`, so they never bump a street. `road_weight` is the street's own flatten weight, recomputed from `r_d`/`r_idx`.
* `_surface_pass`: a hit pad's biome comes from the pad; `veg = pad.veg`, so yards grow grass. Grass under buildings is hidden by the floor slabs (check in a render).
* `_metadata` placements:
  * one `{kind: "lot", framework, town, lot, id: "<town>/<lot>", origin: [cx, y, cz], rotation: yaw, size: [w, d]}` per lot whose frame centre lies in this region (one owner per lot);
  * one `{kind: "town", framework, id: town, origin, rotation: 0, rect: region rect}` per touched region, for fixtures filtered by rect.

### 3.11 How lots and LotPicker consume the result

* `LotPicker.resolve(fw, town_id, seed)` is unchanged except that `lot_size` reads the frame. The per-run picks keep their seeds `lot:<seed>:<town>/<lot>`.
* For v2 worlds only, `assign_authored` precomputes, in town-id order, which towns receive each authored building, capped by `tuning.towns.authored_max` (default 3 [A12]). Otherwise 32 towns would each get a Merrow House.
* The PoiRegistry stores each lot's resolution (kind, def or template, seed, size) without generating anything.
* PoiManager plans `def_for` on demand and places each building at `T(origin) · R(−yaw) · T(−footprint/2)` (`lot_local_xf`), with y = `l.y`.
* TerrainHoles uses the same transform.
* `RwgMap` draws streets, frames by zoning colour, and parcels.

### 3.12 frameworks.json, v2 town def

```json
{"id": "rwg_x_harlow", "name": "Harlow", "layout": "organic", "kind": "village", "size": [w, d],
 "center": [x, z], "radius": 230, "tier_range": [1, 2],
 "lots": [{"id": "lot_12", "frame": [cx, cz, 21.5, 30.0, 37.5], "poly": [[x, z], ...], "zoning": ["residential"],
           "street": "st_3", "ring": "inner", "y": 84.37}],
 "roads": [{"id": "st_3", "class": "street", "points": [[x, z], ...], "width": 6, "surface": "asphalt",
            "shoulder": 0.8, "markings": false}],
 "fixtures": [{"id": "fx_0", "prop": "street_lamp", "pos": [x, z], "rot": 112}],
 "plaza": {"frame": [cx, cz, 40, 40, 12]}}
```

---

## 4. The loading screen and progress

**Fresh world.** Weighted stages; the bar never stalls.

| Bar | Stage | Notes |
|---|---|---|
| 0–30% | Generator stages: Raising the land, Laying out towns, Building roads, Planting forests, Placing camps and cabins, Mapping | Sub-progress inside `_flood`, `_carve`, routing (k of N links), town plans (k of N), places |
| 30–33% | Drawing the map | Then `map.png` appears on the loading screen |
| 33–60% | Surveying the far hills (k of N regions) | Coarse composes; each region's cell tints on the map |
| 60–85% | Shaping the land around the drop site | The composer's own `_report` stages: macro, features, water, roads, pads, surface; the region's cell pulses |
| 85–88% | Planning the nearest buildings | Registry, plus generation for the first POI ring |
| 88–100% | Boot steps as today | Far hills, sky, modules, raising buildings, growing the forest, waking up |

* GameUI's `show_loading(text, progress, map: Texture2D = null, marks: Dictionary = {})` shows the map with a drop-site marker and region marks (done, working, pending).
* The marks come from `WorldLoader.status()` under its mutex.
* Optional ETA from measured per-region compose times.
* A "Back to menu" button sets the cancel flags; the loader joins.
* Long stages report sub-progress, so on Windows the bar moves continuously and the window stays responsive (ADR-0036).

**Later loads.**
1. Reading the map: `map.png` shown at once.
2. Surveying the far hills: cached coarse regions, k of N.
3. Shaping the land around you: the first area from the cache, or a compose if it was evicted.
4. Boot steps. Target: 15 s or less (est.).

**In play.**
* No loading screen.
* If the player's own chunk lies in a non-attached region (outrunning, teleport, respawn), a blocking "Finding your feet…" overlay holds until `is_area_ready(pos, 1 chunk)`, running steps at the 40 ms budget.
* If only the near square is late, the HUD shows the hint.

---

## 5. Save compatibility (version 7)

**`SaveSystem.CURRENT_VERSION = 7`; `_v6_to_v7(d)`:**
* If `session.world_mode == "random"` and `world_gen` has no `generator_version`, set it to 1. Every v6 random run was made by generator v1.
* `session.world_files = "shared"`: the files live in `user://worlds/random/<id>/`.
* Main-map saves: no other change.
* The bump also stops a v6 build from loading a streamed run and trying to compose a 16×16 world entirely.

**The world bundle** (Phase 4; fixes TD-082 for v7+):
* On save, a random world's slot gets `world.zip`: `world.json`, `regions/`, `frameworks.json`, `meta.json`, `macro.bin`, without `map.png`; about 1–3 MB (est.).
* It is written once per world id, then carried to later saves by renaming it from the previous slot into `<slot>.tmp` before the swap.
* On load, if `user://worlds/random/<world_id>/world.json` is missing and the slot has a bundle, `RwgWorlds.unbundle` restores the folder before loading. `session.world_files = "slot"`.

**v1 random-world saves under v2:**
* **The world folder still exists** (the normal case): it loads as is through the streaming loader. v1 towns are region `framework` features with one pad; there is no `towns` key and every region is built. Sizes 2–7 work.
  * Instance ids (`<town>/lot_N`), POI states, terrain deltas and felled-tree indices stay valid only if composer output for the same inputs is byte-identical. That is why every Phase 1–4 composer change must pass the golden test, and why `input_hash` keeps its formula, which keeps v1 caches valid.
* **The folder is gone:** the run regenerates with the current generator, as TD-082 already describes, and gets a different world. The load menu warns ("This run's world was made by an older generator and is no longer on this computer; loading it makes a new world from the same settings"). Saved state then points at things that no longer exist, which is harmless.
* At its first v7 save, a v1 run gets its bundle too, so it is safe from then on.
* LotPicker's world-level authored caps apply only to `layout: "organic"` frameworks (v2 worlds), so v1 lots keep their buildings.

**Tests:**
* migrating a v6 random save adds `generator_version: 1` and `world_files: "shared"`;
* a v6 main-map save is unchanged apart from the version;
* a v7 bundle restores a deleted world folder byte for byte;
* a v8 file is refused.

---

## 6. Phases

Each phase is shippable (`make check test validate smoke tour` green). The pure planner of Phase 5 (`rwg_town_planner.gd` and its unit tests) can run in parallel from Phase 2 on.

### Phase 1: measure, then speed up with no behaviour change (worldgen and tools only; can start now)

**Work**
* Golden output test first.
* Composer speed-ups: road-profile cache, arc-range metadata, pad/paint/path buckets, memoised hashes, bands, cancellation.
* Atomic cache writes and LRU.
* `macro_height` noise skip; release `corner_heights`.
* Generator hot spots: `_biome_map` per-region loop, spatial grids.
* `compose_region --bands/--spacing 16` timings.
* `stream_walk.gd` skeleton that only measures.
* Record every number in §7.4 into ADR-0038's budget section.

**Tests**
* `test_composer_golden.gd`: Larch Hollow and a fixed RWG region (seed 2026, size 3), composed at 4 m and 8 m. Digests of `height.content_hash()`, md5 of splat0, splat1, biome and vegmask, and the JSON of water, roads, bridges and placements must be equal before and after. `bands=1` and `bands=4` must also be equal. A 1 m variant runs behind `SLOW_TESTS=1`.
* `test_region_cache.gd`: a truncated file is a miss, a leftover `.tmp` is ignored, the LRU respects the budget and keeps coarse files and saved worlds.

**Verify**
* `compose_region.gd -- --world <rwg dir> --region <rid> --no-cache`, before and after.
* `rwg_preview.gd -- --seed 2026 --size 7 --fresh --compose`: total time against v1.
* The v1 7×7 first load (smoke `-- --world random --world-set size=7`) should take about half its time (est.).

### Phase 2: terrain streams

**Work**
* `RegionStreamer`, `StepRunner`, attach and detach, the copy-on-write grid, lazy materials.
* Coarse composes for every region plus the first area at load (new `WorldLoader` flow); drop-site margin of 300 m (generator only, so `VERSION` bumps to 2; or delay this to Phase 4 [A13]).
* Deltas applied per region; volume per region; loose-item rescue gating; nav gating.
* Far-tile neighbour re-mesh and the 64 m LOD.
* Vegetation far layer per region with buffers; bridges per region; markings per chunk; Bloom tiles and window; water vertex arrays on workers.
* Loading screen v2 (stages, map, marks, cancel); the "Finding your feet" overlay; `await_area` for respawn and teleport; spawn props on attach.
* **Interim POIs:** PoiManager queues every POI of a region when it attaches and frees them on detach, through the existing plan and build steps.

**Tests**
* `test_region_streamer.gd`, pure ring logic: wanted and keep sets with hysteresis, priority by heading, `max_attached` eviction, pins.
* `test_terrain_streaming.gd`, on a synthetic world with an injected compose function (the `test_terrain_threads.gd` pattern):
  * after attach, `height_at` reads the detailed data;
  * dig, detach, re-attach: the delta is reapplied and the dig limit still holds;
  * a volume column comes back;
  * a worker reads heights in a loop through 2 s of attach/detach churn (surviving is the pass).
* `test_bloom_tiles.gd`: the window samples equal the old global field over the same rect.
* Water and bridge counts match v1 on a 3×3 world.

**Verify**
* `make smoke` (main map, unchanged result) and smoke `-- --world random --world-set size=7`: time to spawn under 60 s on the container, est.
* `make tour`; `make render-check` (`valley_overview`, `pell_crossing_street`).
* `make stream-check STREAM_ARGS="--world-seed 7 --world-set size=7 --km 3"`: no late seconds at 6.2 m/s; peak static memory within budget; memory after walking out and back twice within 5% of the first return (leak check).

### Phase 3: POIs stream by distance

**Work**
* `PoiRegistry`, built on the loader thread.
* PoiManager slots: nearest-N build ring, worker planning with snapshotted picks, resumable `PoiBuilder`.
* Fixture cells with batching; `poi_at` in local frames; holes per built POI.
* Registry checks in `spawn_point_ok` and `spot_ok`; tether markers; directive fallback.
* ModelLibrary warm-up of kit and prop models on the loader thread (it already has a mutex); `PoiParts.kit_mesh` in boot steps.
* StreamMeter.
* Lot frames in LotPicker, PoiManager, TerrainHoles and FrameworkDef, so Phase 5 can plug in.

**Tests**
* `test_poi_builder_phases.gd`: for Merrow House, the sawmill, the campground, a cellar POI and a generated house, phased build equals one-shot build (node count, batch names and instance counts, collision shapes, probes).
* `test_poi_streaming.gd`: open a door, kill a sleeper, loot a container, free the building by moving the focus, rebuild it: state restored, picks pinned once.
* `test_poi_registry.gd`: footprints match the built transforms for rect and frame lots.
* `poi_at` on rotated neighbours.

**Verify**
* render-check, with the runner waiting on `is_settled_around`.
* Tour on a random world (`TOUR_ARGS="--world random --world-seed 7 --world-set size=5"`).
* StreamMeter: the longest streaming frame under 50 ms headless on the container, and every step under 8 ms except those listed in §7.
* Walking into Pell's Crossing from outside 600 m builds it with no frame over the threshold.

### Phase 4: big worlds, loading screen polish, saves

**Work**
* `size` max 16 and `town_density`; place and farmstead caps per 16 km²; Bloom scaling.
* Optional binary macro grid. Generator scaling, so 16×16 generates in about 20 s on the container (est.; set the budget from the Phase 1 numbers).
* RwgMap glyphs and labels; New Game notes; big-world presets.
* Generation sub-progress and ETA.
* Save v7 with the bundle; the migration; the load-menu warning; RwgWorlds LRU wired to Settings.
* RWG `VERSION` 2.

**Tests**
* `test_rwg.gd` updated: determinism at size 10; `test_generation_time_10x10` (budget from measurement); 16×16 behind `SLOW_TESTS`; every region gets a coarse tile; places not empty at 16×16.
* `test_save_system.gd`: the v6→v7 cases in §5.

**Verify**
* Fresh 16×16: time to spawn at most 120 s on the container (about 60 s on a desktop, est.) via smoke `-- --world random --world-set size=16`.
* `stream-check --km 5` on 16×16: memory bounded, no late seconds.
* Loading-screen QA shot: a runner capturing the screen at about 50% under Xvfb.
* Save/load across a v6 fixture world.

### Phase 5: organic towns (+ optional POI far proxies)

**Work**
* World-level towns in the composer (§3.10); `rwg_town_planner.gd`, `rwg_streets.gd`, `rwg_lots.gd`; `route_fine` and the valley term; the yard biome; fixtures; `assign_authored`; RwgMap towns; `rwg_preview_shots` framing the arterial.
* RWG `VERSION` 3; the RWG golden digest re-recorded (the main-map golden must not change).
* Optional proxies: per-lot boxes with a roof prism, coloured by zoning, merged per region into one ArrayMesh from the registry, shown 450 m to view distance.

**Tests:** `test_town_planner.gd`, 3 classes × 12 seeds × rolling and hilly:
* lot overlaps under 0.5 m²;
* lots clear of corridors;
* the street graph connected to an arterial;
* street grade at most 0.12;
* frame relief within limits;
* counts within the class ranges;
* mean distance of commercial lots < civic ≤ residential;
* cul-de-sacs present in towns;
* every lot holds a building (LotPicker);
* md5 determinism;
* "follows the land": mean |grade| of side streets ≤ 0.6 × the disc's mean slope on hilly seeds, and the arterial's mean relative elevation < 0;
* "irregular": standard deviation of lot yaw > 10°;
* planning a town in under 1 s.

`test_world_towns_seams.gd`: a 2×2 world with a test hook placing a town across a border. Compose both regions at 4 m:
* the shared border column is equal (|Δ| < 1e-4);
* each lot is owned once;
* each lot's placement y equals `l.y`.

**Verify**
* `rwg_preview.gd --crop x,z,900` of several towns.
* `rwg_preview_shots.gd` (town street, from above) under Xvfb.
* render-check with an `rwg_town_street` shot.
* Smoke and tour on organic worlds; StreamMeter in a town core.
* Draw calls in the town view from the F4 counters in the rendered run.

---

## 7. Risks, budgets, and what to measure first

### 7.1 Risks

1. **GDScript composer speed limits streaming speed.** At 8–10 s per region (container), prefetch keeps up at sprint, not with future vehicles (ATV in M4). Mitigations: bands, prefetch, cache. The real fix is TD-004 (native hot loops). → TD-110.
2. **Main-thread hitches.**
   * PoiBuilder phases: today's single builds take up to 0.3–0.6 s (TD-102).
   * First-time model and shader loads: warm-up only covers the models.
   * Decals and MultiMeshes.
   * Measure each phase; split the offenders further (props by room, batches by k).
3. **POI density in organic towns.** 70–120 buildings, so memory and draw calls (DESIGN §13: under 3000). Mitigations: `max_built`, fixture batching, proxies; measure in the rendered run.
4. **Composer identity.** An accidental output change silently invalidates v1 trees, deltas and caches. The golden test is mandatory in Phases 1–4.
5. **Thread safety.** The new copy-on-write structures (grid, holes, Bloom tiles), worker result slots, and packed arrays written from several threads (the band merge). Plus the noise from TD-103 in headless runs.
6. **Seams.** World-level pads and streets must use world-only inputs (reference ground, precomputed `y`); the seam test is required.
7. **Disk use:** about 4 MB per visited region, so a fully explored 16×16 world is about 1 GB. Hence the LRU.
8. **Memory churn** from repeated 15 MB allocations: the stream-check leak check.
9. **Pop-in.** Towns pop at the build radius until proxies land. A smooth near-coarse region can show briefly beyond 300 m at the first spawn. Bridges are absent beyond the detail ring.
10. **Coordination:** heavy overlap with session 3's files (§0).

### 7.2 Time budgets (targets; confirm with measurements)

* First load of a fresh 16×16 world: ≤120 s on the container, about 60 s on a desktop.
  * generation ≤20 s;
  * writing the files and map ≤3 s;
  * coarse composes ≤10 s on 3–4 threads;
  * the first area ≤10 s;
  * boot ≤8 s.
* Later loads: ≤15 s.
* Runtime: streaming ≤4 ms per frame; every step ≤8 ms; streaming's longest frame ≤50 ms headless on the container.

### 7.3 Memory budget

Process RSS ≤1.2–1.5 GB on 16×16 (est.); set it from the main-map baseline.

### 7.4 Measure first, in Phase 1 (with commands)

1. Composer per stage at 1 m, single-threaded and with bands: `compose_region.gd -- --world <dir> --region <rid> --no-cache [--bands 4]`, for Larch Hollow, an RWG wilderness region and an RWG town region.
2. Composer at 16 m per region, and the total for 256 regions (`--spacing 16`).
3. `RegionTerrain.load_cached` time (I/O + zstd), and `input_hash` cost per region before and after memoisation.
4. Generator per stage at sizes 7, 10, 13, 16 (`rwg_preview --memory`; needs the size cap lifted on the CLI for measurement); the size and parse time of `world.json`; `RwgMap` at 1024 and 2048 px.
5. Far-tile meshing per tile at 16 and 64 m; triangle count in a 16 km view (rendered run).
6. Far impostor scatter per region, and MultiMesh build time with `set_instance_transform` against `buffer`.
7. PoiBuilder time per phase for a generated house, Merrow House, the sawmill, the campground and the logging camp.
8. Memory per built POI (`Performance.MEMORY_STATIC`, `OBJECT_NODE_COUNT` before and after building Pell's Crossing's 31 buildings); `RENDER_VIDEO_MEM_USED` in a rendered run.
9. RegionTerrain RAM (expected 14.7 MB), and VRAM per region material (expected 8.4 MB).
10. Main-thread attach costs: `ImageTexture` creation, grid swap, holes rebuild, far-tile adds.
11. RSS baselines: main map, v1 7×7, then v2 after a 5 km walk.
12. Draw calls and visible triangles in a town view: a rendered run with F4 counters (counts don't depend on the GPU).

---

## 8. Assumptions

* **[A1]** ADR-0038 and ADR-0040, the TD ranges in the header, and save v7 (per the WORKBOARD).
* **[A2]** v1 lands as ADR-0031 describes it: sizes 2–7, every region built, composer `VERSION` 11, save v6, `RwgGenerator.VERSION` 1, towns as region frameworks inside one region.
* **[A3]** A desktop core is about 2× the container's (4 shared cores). Desktop times are container ÷ 2.
* **[A4]** Top speed is 6.2 m/s (`player.json` sprint); no vehicles in scope.
* **[A5]** Camera far plane is 9000 m (`player.tscn`); view distance 700–2000 m by preset.
* **[A6]** Building POI nodes off-tree on the main thread in phases is safe. Building them on worker threads is not assumed safe.
* **[A7]** `FastNoiseLite.get_noise_2d` is safe for concurrent reads. v1's parallel composer already relies on it.
* **[A8]** POI build costs are about 35 ms on average and up to 0.6 s per building (container; ADR-0036/TD-102), and memory per POI is est. 1–2 MB. Both are unmeasured.
* **[A9]** RegionTerrain is ~15 MB RAM and ~8 MB VRAM (TD-081). A coarse region is ~60 KB and a 1 m cache file ~4 MB (from array sizes).
* **[A10]** The lot-frame yaw sign convention matches `PoiManager.lot_xf` (facing S is yaw 0, the front points +Z). Verify it with a placement test.
* **[A11]** `town_density` defaults to 2.0 per 16 km² (32 towns at 16×16). It is a tuning choice.
* **[A12]** A world-level cap of about 3 copies per authored building is acceptable design-wise.
* **[A13]** The drop-site margin change is a generator change. Grouping it with the Phase 4 `VERSION` bump avoids changing worlds twice.
* **[A14]** Godot 4.7.2 provides `Thread` priorities, `MultiMesh.buffer`, `ZIPPacker`/`ZIPReader` and `visibility_range` as in 4.x.
* **[A15]** Grass growing under building floors on yard pads stays hidden by the floor slabs. Check in a render.

### Critical Files for Implementation
- /home/user/7DaysToClaudie/game/src/world/terrain/terrain_manager.gd
- /home/user/7DaysToClaudie/game/src/world/world_loader.gd
- /home/user/7DaysToClaudie/game/src/poi/poi_manager.gd
- /home/user/7DaysToClaudie/game/src/worldgen/terrain_composer.gd
- /home/user/7DaysToClaudie/game/src/worldgen/rwg/rwg_generator.gd