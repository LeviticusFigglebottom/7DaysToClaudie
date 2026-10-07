# Organic caves through the SDF volume terrain: working plan (ADR-0056, TD-279..288)

Session 3's plan for the Round 3 caves suite. It is written down before the ADR so parallel
worktree agents share one contract. ADR-0056 replaces it once the suite lands.

## Today's code (what the suite builds on)
* **Volume creation.** `TerrainManager.take_damage` (terrain_manager.gd) switches a dig to the volume
  (pickaxe, the heightmap dig limit, steep ground, or a hit on a volume collider).
  `VolumeTerrain.edit_sphere` then activates every 16 m column the sphere touches.
  `_create_chunk` samples a padded 35³ block of 0.5 m voxels **on the main thread**
  (`density = clamp(h - y, ±2)`, positive = solid, with cellars carved from `TerrainHoles`).
* **Meshing and collision.** `_remesh` runs `SurfaceNets.mesh` on a worker. `_apply` builds the mesh
  plus a `ConcavePolygonShape3D` body (layer 1) for every chunk, with no distance gate.
  `column_activated` then re-meshes the 64 m heightmap chunk **synchronously**: the volume columns
  become holes, and the collision sinks 40 m under them.
* **Saves.** `save_into` writes edited chunks as `v:x_y_z` (ZSTD bytes) plus
  `flags.volume_columns`. `load_from` re-activates every column at boot.
* **Not streamed.** `attach_region`/`detach_region` never touch the volume.
  `RegionStreamer.compose_fn` compiles `holes`, splat and bloom tiles on its worker; caves follow
  that pattern.
* **TD-163's gaps:**
  1. `faces_in_rect` has no caller, `NavTiles._add_terrain` bakes the pre-dig heightfield, and
     `edit_sphere` never emits `Events.terrain_modified`.
  2. Volume chunks never stream.
  3. The volume shader paints by normal only (no splat or palette), so a converted column repaints.
  4. `is_indoors` is a POI-layout test only.
* **Also:** `TerrainManager.ground_below` ignores the volume. The Hollowed fell-through rescue,
  LooseItems and `_finish_spawn` would lift things out of a cave.

## Design (ADR-0056)
* **`CavePlan`** is pure and deterministic, built from a spec, a seed and the **pristine** heights
  (never dug ones). It is made of these parts:
  * **Mouth:** settled on a slope ≥ ~18° within `search` m, heading uphill (or at a declared yaw).
    The spine starts 1.5 m outside the slope, so the tube breaks through the surface by itself.
  * **Spine:** a Catmull-Rom spline through 3–6 points, pitched −4…−12° into the hill, with a seeded
    yaw wander. It is sampled every ~1 m into `spine`, `radii` and `floor_y`.
  * **Air:** the union of noise-warped capsules along the spine, plus an optional end chamber
    (ellipsoid) and a side pocket. Each one is intersected with a floor half-space
    (`max(prim_sd, floor_y - y)`), so the floors are flat and walkable.
  * **Warp:** a seeded 3D lattice at 2 m, precomputed into a PackedFloat32Array. The hot path makes
    no FastNoiseLite calls.
  * **Terrain:** `density = min(h - y, cave_sd(p))` (cave_sd > 0 in rock), clamped. Union is a min,
    so registration order doesn't matter.
  * **Plan-time checks:** cover ≥ `min_cover` beyond the mouth (deepen the pitch, then shorten),
    clearance ≥ `min_clear` everywhere, and inside one region with a ≥ 32 m margin. A failed plan
    has `ok = false` and a `reason`.
  * **Seed:** `spec.seed`, or `CaveSites.shape_seed(world.id, id)`. It is per world, so an authored
    main-map cave is identical in every new game.
* **Styles** in `game/data/config/caves.json`:
  * `shelter`: 6–10 m long, r 2.5–3.5, no chamber.
  * `grotto`: a 12–30 m tunnel plus a 5–9 m chamber, with an optional pocket.
  * Shared: `min_cover` 2.0, `min_clear` 2.2, `min_mouth_r` 1.4, the warp, `GEN_VERSION`.
* **Declared** in either of two ways:
  * as a region feature
    `{"type":"cave","id","style","mouth":[x,z],"heading":"uphill"|deg,"search":12,"length":[a,b],"seed"?}`,
    compiled by RegionStreamer's compose worker into `rt.set_meta(&"caves")` (no composer change);
  * at runtime with `TerrainManager.place_cave(id, spec) -> CavePlan` (idempotent by id) and
    `remove_cave(id)`, for ADR-0054's forest scatter and POI set pieces. Registrations aren't saved:
    callers re-derive them from their own seeds. Only the player's digs persist (`v:` blobs).

### Contract (lands first, M0; other streams code against it)
```gdscript
class_name CavePlan extends RefCounted        # game/src/world/terrain/cave/cave_plan.gd
const GEN_VERSION: int = 1
var id: StringName; var region_id: String; var style: StringName; var seed: int
var ok: bool; var reason: String
var mouth: Transform3D                        # origin on the opening's floor, -Z into the hill
var spine: PackedVector3Array; var radii: PackedFloat32Array; var floor_y: PackedFloat32Array
var aabb: AABB
static func build(spec: Dictionary, seed: int, height_fn: Callable, cfg: Dictionary) -> CavePlan
func sdf(p: Vector3) -> float                 # > 0 rock, < 0 cave air
func carve_block(origin: Vector3, n: int, voxel: float, density: PackedFloat32Array) -> bool  # min() into a padded n³ block; false = untouched
func columns() -> Dictionary                  # Vector2i(16 m column) -> Vector2i(cy0, cy1)
func is_inside(p: Vector3, ground_y: float) -> bool   # air (sd < -0.2) and >= 1 m under ground
func floor_below(p: Vector3) -> float          # NAN when not over cave air
func keep_out(x: float, z: float) -> bool      # mouth apron, no vegetation
func anchors() -> Array[Dictionary]            # {pos, normal, kind: mouth|tunnel|chamber|pocket}
func probe_boxes() -> Array                    # [[Transform3D, size: Vector3, daylight_ratio: float]]
func digest() -> String

class_name CaveSet extends RefCounted          # immutable once published (TD-104)
static func combined(parts: Array, extra: Dictionary) -> CaveSet
func touching(aabb: AABB) -> Array[CavePlan]   # 64 m grid index
func is_inside(p: Vector3, ground_y: float) -> bool
func floor_below(p: Vector3) -> float
func keep_out(x: float, z: float) -> bool
func is_empty() -> bool

class_name CaveSites extends RefCounted
static func shape_seed(world_id: String, cave_id: String) -> int
static func from_region(world: WorldDef, rid: String, rt: RegionTerrain, cfg: Dictionary) -> CaveSet
static func find_mouth(height_fn: Callable, area: Rect2, seed: int, opts: Dictionary) -> Dictionary  # {pos: Vector3, heading_deg} | {}
static func settle_mouth(height_fn: Callable, near: Vector2, heading_hint: float, radius: float, opts: Dictionary) -> Dictionary
```
TerrainManager additions:
* `caves: CaveSet`, published like `holes`;
* `place_cave(id, spec) -> CavePlan`, `remove_cave(id)`, `cave_at(pos) -> CavePlan`;
* the signal `caves_changed(aabb: AABB)`.

VolumeTerrain additions:
* `attach_region(rid, rect)`, `detach_region(rid)`;
* `is_rect_ready(rect)`, `is_idle()`, `ground_below(pos)`;
* the signal `chunks_applied(aabb)`;
* `faces_in_rect`, indexed by column.

## Workstreams
* **WS-A, generator and API** (new files only: `world/terrain/cave/*.gd`, `data/config/caves.json`).
  Tests `test_cave_plan.gd` and `test_cave_sites.gd`: determinism, an open mouth, cover, clearance,
  `carve_block` agrees with `sdf`, flat ground gives `ok=false`. The plan is pure and thread-safe.
* **WS-B, volume streaming core** (`volume_terrain.gd`, plus hunks in `terrain_manager.gd` and a
  `region_streamer.gd` compose hunk):
  * worker density and mesh jobs, sharing TerrainManager's task cap (TD-196);
  * applies budgeted at ~3 ms (StreamMeter kind `volume`);
  * a two-phase column commit, so no hole ever shows without a mesh;
  * per-region attach/detach with blobs for detached digs; load decodes only;
  * collision bodies only within ~160 m;
  * `ground_below` reads the cave floor;
  * `take_damage` emits `terrain_modified`;
  * a boot step "Carving the caves…".

  Tests: `test_volume_streaming.gd`, plus churn in `test_terrain_threads.gd`.
* **WS-C, nav and AI** (`nav_tiles.gd`):
  * volume faces join `_add_terrain` (heightfield holes over volume columns);
  * `_mark_aabb` runs for edits, applies and `caves_changed`;
  * tests: a path from mouth to chamber, and enemy rescue rules inside caves.
* **WS-D, dark and surface**:
  * `volume_terrain.gdshader` gets the region splat and palette (shared include with
    `terrain.gdshader`), using `VolumeSurfacePaint` vertex weights from WS-B's job;
  * `CaveLighting` adds ≤ 3 interior `ReflectionProbe`s per cave in group `interior_probe`, with the
    box clamped under the ground and daylight falling with depth;
  * `PoiManager.is_indoors` also ORs in `terrain.caves.is_inside`;
  * the `ReverbCave` bus.

  `environment_controller.gd` hunks are session 5's to approve.
* **WS-E, placement**:
  * vegetation keep-out by index skip (saves stay stable), and a rebuild on `caves_changed`;
  * 1–2 authored forest caves in d6 (re-record the composer golden's input hash);
  * the RWG `_caves()` stage in `rwg_generator.gd` is the hub's file: ask first;
  * `docs/REGIONS.md`.
* **WS-F, perf and TD-003**:
  * `perf_capture` gets `dense_forest` and `cave_mouth` views, a `--gpu-profile` JSON and a
    `make perf-gpu` target;
  * `stream_walk --route forest`;
  * per-kind budgets in `streaming.json` and StreamMeter;
  * `docs/GPU_PROFILE.md`, the owner's checklist.

## Merge points
* **M0:** WS-A's contract stubs.
* **M1:** A and B (volume and streaming tests, smoke, tour).
* **M2:** C and D on M1.
* **M3:** E (world data).
* **M4:** F's measurements; write ADR-0056 and close or narrow TD-163, TD-162 and TD-010.

## Risks
* **Threads:**
  * never replace a container a worker reads;
  * capture `CaveSet` and `TerrainHoles` objects in job closures;
  * join every task in `_exit_tree`;
  * keep volume jobs under `max_tasks`.
* **Main thread and physics:**
  * `set_faces` and mesh creation cost main-thread time;
  * collision must be gated (Jolt `max_bodies`);
  * the first pickaxe hit stays synchronous.
* **Carving cost:**
  * skip chunks a cave doesn't reach;
  * skip meshing all-air or all-solid blocks;
  * use the lattice warp.
* **Seams and visuals:**
  * TD-010 steps at cave column borders;
  * volume chunks overlap the far tiles (`visibility_range_end`).
* **Nav and probes:**
  * nav needs floors ≥ 1.4 m wide;
  * keep probe boxes under the ground.
* **Determinism and saves:**
  * plan only from pristine heights;
  * store `flags.cave_gen`; the dig wins over a regenerated cave.
* **`is_indoors` cost:** five systems call it per frame, so it needs the grid index.
