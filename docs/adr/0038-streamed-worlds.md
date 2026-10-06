# ADR-0038: Streamed worlds

**Status**: Accepted for Phase 1 (measure, then speed up the composer and the generator) · 2026-10.
Session 3 adds Phases 2-4 (terrain and POIs stream, big worlds and saves) to this record.

## Context
Random worlds v1 (ADR-0031) compose every region of a world at 1 m when it loads and build every
building, which caps worlds at 7 x 7 and makes first loads long (TD-081). Random worlds v2
(docs/RWG_V2_PLAN.md) streams regions instead: the region around the player composes at 1 m in
row bands on the loading screen, the rest in the background on low-priority threads, cancellable,
cached on disk with an LRU; every region of every world composes at 16 m for the far view.

Phase 1 is the foundation the streaming builds on, and it may change nothing a player can see:
saves keep terrain digs, felled trees (by index into the scatter) and POI state against composed
regions, and the composed-region cache is keyed by an input hash of the data and
`TerrainComposer.VERSION`, not of the composer's code. A composer change that moved one byte of
output for the same inputs would silently invalidate v1 runs. So: measure first, then make the
composer and the generator faster with output identical byte for byte, prove it with a golden
test, and give session 3 the API it needs (bands, cancellation, a robust cache).

## Decision

### 1. A golden test first (`tests/unit/test_composer_golden.gd`)
Recorded from the composer at `VERSION` 11 before anything changed: Larch Hollow, and the town
region (B2, Ashby) and the drop-site region (A2) of a fixed random world (seed 2026, size 3), at
4 m and 8 m (and at 1 m with `SLOW_TESTS=1`). Each digest is the height hash
(`HeightField.content_hash()`), md5 of `splat0`, `splat1`, `biome` and `vegmask`, and md5 of the
JSON (full precision) of `water`, `roads`, `bridges`, `placements` and the rest (spawns,
frontiers, biome ids, palette, rect). The input hash is recorded too, so a failure says whether
the inputs changed (re-record with `GOLDEN_PRINT=1`) or the composer did. One band, three bands and
four bands must give the same digests; `VERSION` stays 11. A scratch differential run also
compared all 49 main-map regions at 16 m and every region of two generated worlds at 16 m and 8 m
(99 regions) before and after every change: identical.

### 2. Composer speed-ups, each output-identical
* **World roads graded from world data** (`road_grade == "world"`, generated worlds) have one
  profile wherever they are composed: `WorldDef.road_profile(i, build)` builds it once per world
  behind a mutex. Each region used to build every road that crossed it end to end.
* **Metadata** (`_metadata`) samples a river (every 6 m of arc) or a road (every 4 m) only over the
  arc range whose segments come near the region's 64 m margin; the samples kept are the same.
* **The surface pass** looks pads, paints, paths and clearings up in a 32 m index (per cell, the
  items whose boxes reach it, ascending), so a sample tests the same items in the same order as
  before, minus those that can't reach it (lowest pad index still wins; paints still in order).
  A path's distance is taken over the segments indexed near the sample, with
  `Polyline2.closest()`'s arithmetic and its single-precision result (it returns the distance in a
  `Vector3`; a double here changed nothing in the golden regions but could flip a byte elsewhere).
* **`input_hash`** keeps v1's formula (so v1 caches stay valid), but `WorldDef` keeps the bytes
  of `world.json`, `frameworks.json`, each `region.json` and the frameworks and POIs a region places,
  read once, and memoises each region's hash per spacing (mutex). Every call used to re-read
  `world.json` (up to ~2 MB on a 16 x 16 world) and re-parse `region.json`.
* **`macro_height`** skips the noise calls when the amplitudes are 0 (a generated world's land is
  all in its grid): the term is then a signed zero, and `base + 0.0 + 0.0` is `base` (or +0.0)
  whichever zero it was.
* **The macro grid** of a coarse compose evaluates only the grid rows and columns its samples read
  with a non-zero weight (a 16 m compose reads every other one of the 8 m grid; the rest enter the
  blend times an exact 0).
* A detail-noise layer configured exactly like the shared world noise (a generated world's first
  layer) reads the world noise's value instead of computing it again.
* `WorldDef.corner_heights` (nested Arrays, ~20 MB at 513²) is released once flattened.
* Per-column positions and blend weights are computed once per pass with the loop's own
  expressions; per-road values (half width, shoulder, profile, spans, surface) are flat arrays.

### 3. Row bands and cancellation
`TerrainComposer.compose(world, rid, spacing = 1.0, progress = Callable(), cancel: Array = [false],
bands: int = 1)` (and `get_or_compose` with the same parameters; existing callers are unchanged).
* The per-sample passes (macro and detail noise, the water carve, the road flatten, the coarse
  patch noise and the surface pass) run in `bands` row bands: the first on the calling thread, each
  other on a `Thread` of its own. Each band writes its own packed arrays, concatenated in row
  order after the join; one PackedArray is never written from two threads. Field rasterisation,
  hills and cliffs, pads and metadata stay sequential.
* `cancel[0] = true` (from any thread) stops a compose: it is read at each progress report and
  every 64 rows (`CANCEL_ROWS`, ~0.1 s of work at 1 m); a cancelled compose returns null and
  `get_or_compose` writes nothing.
* **What made bands scale**: in GDScript every call of a script function (instance or static)
  takes the reference count of the object it runs on, and in a debug build every call of an object
  method also goes through ObjectDB's global spin lock. Four bands calling `_bl()` and `_add()` per
  sample on the shared `_Build` ran slower than one. So a band's loop calls no script function and
  no object method it can avoid (the helpers are inlined with their exact arithmetic), copies no
  shared container per sample (indexes and per-road data are flat packed arrays with offsets),
  and uses typed `roundi`/`floori` and `if` chains: the generic `round()`/`floor()` and `match`
  also serialise threads (measured: `match` on an int was 2.7x slower than an `if` chain on one
  thread and did not scale at all). The noise calls (`FastNoiseLite.get_noise_2d`) are object
  calls that can't be avoided, so in a debug build the macro pass hardly scales (TD-121).
* A region's "auto" lake levels used to be written into the shared `region_data()` dictionary; a
  region composed at two spacings at once (as a streamed world will: coarse and detail) raced on
  it. They are kept per compose now.
* `RegionTerrain.compose_ms` records each step's time (not saved; `compose_region` prints it) and
  `RegionTerrain.memory_bytes()` the arrays' size.

### 4. The disk cache
* `RegionTerrain.save` writes `<path>.<pid>_<thread>.tmp` and renames it over the file (removing
  the old one first where a platform won't rename over it). A reader on another thread or process,
  or a crash mid-write, sees the old file or the new one; two writers of one region never share a
  temporary file.
* `RegionTerrain.load_cached` treats anything short or malformed as a miss, never an engine
  error: lengths checked before every read, the meta parsed with a `JSON` instance, every
  decompressed part's size and the arrays against the height grid. A leftover temporary file is
  ignored.
* **The LRU** (`src/worldgen/region_cache.gd`, `RegionCache.shared()`): `index.json` in
  `user://cache/worlds/` holds `{world_id: {file: [bytes, last_used]}}`. A cache hit touches its
  file; after every detail write (any spacing finer than 16 m) the detail files are trimmed to the
  budget, least recently used first across worlds, never the file just written nor a path in
  `keep`. The budget is `data/config/streaming.json` `cache.detail_max_mb` once session 3 adds that
  file, 2048 MB until then. Coarse (16 m) files are never evicted by the LRU: they are ~25 KB a
  region, every region of every world needs one, and `RwgWorlds.prune` already removes them with
  their world while keeping every world a save names. The index only orders evictions: a missing
  or unreadable index, a file another process wrote or removed, is read back from the folders
  (size, and modified time as the last use) at the next trim, which also removes temporary files
  older than an hour. Processes share the folder; the last to write the index wins, which costs at
  most some ordering (TD-122).

### 5. The generator
`RwgGenerator.VERSION` stays 1 and the size cap stays 7 (both Phase 4). The output was compared as
JSON md5 for nine seeds and settings (sizes 3-7) and, with the cap lifted in a scratch harness, at
sizes 7, 10, 13 and 16 and in a dense setting (10 towns, wilderness 2, dense roads) at 7 and 16:
identical.
* `_biome_map`'s per-region dominant biome counts only the biome cells near each region (it
  walked the whole map per region: 256 x 65k cells at 16 x 16).
* A shared `SpatialGrid` (`src/worldgen/spatial_grid.gd`, 256 m cells; ids ascending, so
  candidates are walked in the order an exhaustive loop would) indexes road segments, road
  vertices and places. `nearest_road` searches squares of 256, 1024 and 4097 m around the point and
  stops when the nearest found lies inside the square; it returns what the scan over every road
  did whenever a road lies within 4000 m (the scan's own cut-off), and runs the scan beyond that.
  `road_clearance` and `_hits_built` test only what the indexes return (towns' 40 m outlines are
  made once); their exact tests are unchanged.
* Sub-progress inside the long stages (the land's shape and floods, the towns, the road links,
  the biome map, the places) at most every 50 ms, labelled with the stage under way, so the bar
  moves through a 16 x 16 generation. `sub_timings` records the steps (not written to the world).

### 6. Tools
* `compose_region.gd -- [--world DIR] [--region RID | --all] [--spacing S] [--bands N]
  [--repeat K] [--no-cache] [--no-images] [--cache-io]`: per-step times with `--no-cache`, region
  RAM and static memory, every region of a world with `--all`, and cache write/read and input-hash
  times with `--cache-io`. A generated world's towns are registered first: without them its regions
  composed without their streets (and, cached, under the real input hash).
* `rwg_preview.gd -- --memory [--force-size N] [--px P] [--write-dir DIR] [--progress]`: the
  generator's stage and step times, the size and parse time of `world.json`, the map's time;
  `--force-size` lifts the size cap for that measurement only (never in the settings).

## Budgets and measurements
Headless on this container (4 shared cores; other agents' processes were running throughout, so
the load average is given with each run). "Before" is the code at the start of this phase, run
back to back with "after" (scratch copies of the original scripts).

MEASUREMENTS

## Consequences
CONSEQUENCES
