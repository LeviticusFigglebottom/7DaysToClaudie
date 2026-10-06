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
(99 regions) before and after the changes: identical.

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
  method also goes through ObjectDB's global spin lock. Four bands calling `_bl()` and `_add()`
  per sample on the shared `_Build` were no faster than one and took 60% more CPU. So a band's
  loop calls no script function and no object method it can avoid (the helpers are inlined with
  their exact arithmetic), copies no shared container per sample (indexes and per-road data are
  flat packed arrays with offsets), and uses typed `roundi`/`floori` and `if` chains: the generic
  `round()`/`floor()` and `match` also serialise threads (measured: `match` on an int was 2.7x
  slower than an `if` chain on one thread and did not scale at all). The noise calls
  (`FastNoiseLite.get_noise_2d`) are object calls that can't be avoided, so in a debug build the
  macro pass hardly scales (TD-121).
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

**1. The composer at 1 m, per stage** (the composer's own step times, the original and the new
script back to back in one harness; load average 6.5-7.4, so the 4 cores were oversubscribed):

| Region | Before | After, 1 band | After, 4 bands (busy CPU) |
|---|---|---|---|
| Larch Hollow (main map) | 10.68 s | 4.34 s | 3.90 s |
| Ashby (generated, seed 2026: town, river, 9 roads) | 12.19 s | 4.76 s | 4.44 s |
| Raven Barrens (seed 2026: wilderness) | 7.79 s | 3.55 s | 3.76 s |
| Juniper Flats (seed 1, 7 x 7: town) | 9.88 s | 4.35 s | 5.89 s |

Larch Hollow by step, before -> after (one band): surface 8.02 -> 2.17 s; macro and detail noise
1.20 -> 1.00 s; water carve 0.71 -> 0.47 s; road flatten 0.25 -> 0.20 s; hills and cliffs 0.30 s,
water fields 0.12-0.14 s, pads 0.05 s and road fields 0.02 s unchanged (sequential); metadata
3 -> 2 ms. The surface pass was 75-80% of a region: its per-sample method calls (`_bl`, `_add`,
`_pad_at`), the string `match` and the scans over every pad, paint and path.

**Bands with free cores** (load 1.7; Larch Hollow at 2 m, two runs each): one band 1.33-1.39 s,
two 0.86-0.92 s, four 0.67-0.76 s. By pass, one band -> four: surface 0.61-0.64 -> 0.17-0.22 s,
water 0.12 -> 0.04-0.06 s, roads 0.05 -> 0.02-0.03 s, macro and noise 0.29-0.31 -> 0.19-0.24 s
(noise-bound, TD-121). On a saturated CPU (load over 6) four bands gain 10% at best and can lose
(Juniper Flats above): bands are for the loading screen's first area, not for background work.

**2. The composer at 16 m** (one band; the last of three runs; load 7.4-8):

| Region | Before | After |
|---|---|---|
| Larch Hollow | 243 ms | 116 ms |
| Ashby | 164 ms | 78 ms |
| Raven Barrens | 116 ms | 47 ms |
| Juniper Flats | 125 ms | 96 ms |
| Sorrow Bottoms (seed 1, 7 x 7) | 152 ms | 43 ms |

The 8 m macro grid fell from 59-99 ms to 19-40 ms (a 16 m compose evaluates half its rows and
columns) and the surface from 29-49 ms to 9-23 ms. **All 256 regions of a 16 x 16 world** (seed 1,
size forced; one thread, load 7.1): 32.6 s (127.5 ms a region, slowest 249 ms) -> 16.8 s (65.8 ms
a region, slowest 162 ms). The plan's ≤60 ms a region needs an idle machine or 3-4 threads (the
load composes coarse regions in parallel anyway); Larch Hollow's world lake keeps its water
fields at ~65 ms.

**3. The cache and the input hash.** Larch Hollow at 1 m is a 4.26 MB file: written in 45 ms
(temp file and rename), read by `load_cached` (I/O, zstd and the checks) in 20 ms (the plan's
budget is 150 ms). `input_hash` per region: main map 0.19 ms per call before; after, 0.18 ms the
first time and 0.002 ms after. 16 x 16 world (world.json 1.72 MB): 6.6 ms per call before (each
re-read and re-hashed world.json and re-parsed region.json); after, 7.6 ms the first time per
region and spacing (the unchanged formula hashes world.json's bytes) and 0.002 ms after.

**4. The generator by stage** (seed 1, standard preset, size forced past the cap in a scratch
harness; load 3.9-4.3; output identical in every pair):

| Size | Before | After | After: land (shape, lakes, flood, carve, flood, rivers) | After: roads | Drop site + biome map, before -> after |
|---|---|---|---|---|---|
| 7 x 7 | 2.28 s | 2.05 s | 0.79 s | 0.93 s | 0.22 -> 0.15 s |
| 10 x 10 | 3.42 s | 3.49 s | 1.63 s | 1.28 s | 0.37 -> 0.27 s |
| 13 x 13 | 5.84 s | 5.34 s | 3.08 s | 1.45 s | 0.86 -> 0.46 s |
| 16 x 16 | 8.48 s | 7.25 s | 4.82 s (flood 1.9, carve 0.7, flood 1.7) | 1.62 s | 1.46 -> 0.54 s |

Dense (seed 77: 10 towns, wilderness 2, dense roads): 16 x 16 11.12 -> 9.24 s; 7 x 7 2.12 -> 2.45 s
(every stage slower in that one pair, the unchanged ones too: noise). The drop site's 600 candidate
checks of the nearest road take 46 ms at 16 x 16 (139 ms with a first version of the index that
re-walked empty cells; queries are now clipped to the occupied cells). Peak static memory 112 MB at
16 x 16. The plan's ≤20 s for a 16 x 16 generation holds; the floods and the road routing are the
next hot spots (TD-123), and v1's place caps keep big worlds sparse until Phase 4 scales them.
**world.json**: 0.32 MB at 7 x 7 (stringify 22 ms, parse 5 ms, `WorldDef` 5 ms); 1.64 MB at 16 x 16
(88 ms, 14 ms, 17 ms; the nested corner Arrays are now dropped once flattened). **RwgMap**: 1.7 s
at 7 x 7 and 2.0 s at 16 x 16 for 1024 px; 6.8 s for 2048 px.

**9. A region in memory.** `RegionTerrain.memory_bytes()` at 1 m: 14.0 MiB (14.7 MB: heights
4.2, splats 8.4, biome 1.05, vegetation mask 1.05); at 16 m about 0.07 MB (25 KB on disk). VRAM
per detailed region's material: two 1025² RGBA8 splat textures without mipmaps, 8.4 MB.

**First loads** (`WorldLoader` alone, as the game's worker runs it, in two scratch copies of the
project, the original worldgen scripts and the new ones, each with its own cold cache; two rounds
back to back):

| Load | Before | After |
|---|---|---|
| Random world 4 x 4 (seed 4242), cold: generate, compose 16 regions at 1 m on three threads, plan the lots | 225.7 s / 168.0 s (load 10.3 / 7.0) | 48.4 s / 42.5 s (load 9.6 / 6.8) |
| of which composing the 16 regions | 215.7 s / 158.1 s | 39.0 s / 32.9 s |
| Main map, cold: Larch Hollow at 1 m, 48 regions at 16 m, one thread | 16.1 s / 15.4 s | 7.3 s / 7.3 s |
| Main map, cached | 0.88 s | 0.76-0.81 s |
| Random world 4 x 4, cached | 7.2 s | 7.3 s (planning the lots: ~6 s) |

v1's three composer threads gain more than one thread does (4-5x, against 2.5x): the old surface
pass's per-sample object and script calls also contended between those threads.

**The slice smoke** after the change: the main map passes in 60.4 s, ready to play in 23.0 s from
cached terrain (load 5.3); `-- --world random` (seed 1, 4 x 4) passes in 152.8 s, ready in 86.4 s
from a cold cache (its 16 regions recomposed: POI files it places had changed since they were
cached), boot and every building included (load 5.7). ADR-0031 measured a 3 x 3 world's first load
at 97 s with v1's composer.

## Consequences
+ A 1 m region composes in 3.5-4.8 s on one thread of this busy container instead of 7.8-12.2 s
  (2.2-2.6x), a 16 m region in 43-116 ms instead of 116-243 ms, byte for byte the same; a whole
  16 x 16 world's coarse pass in half the time. That is inside the plan's ≤10 s per region for a
  background compose on the container, with room for its prefetch.
+ On free cores the first area composes about 2x faster with four bands (surface, water and roads
  scale 3x), and any compose can be cancelled within about 0.1 s of work.
+ The cache survives crashes, concurrent readers and other processes, and the 1 m files of a big
  explored world are bounded by an LRU; v1 caches stay valid.
+ The generator makes 16 x 16 worlds in about 7 s here with identical output, reports progress
  inside its long stages, and has the spatial indexes Phase 4's denser worlds need.
+ A region can be composed at two spacings at once (the lake-level race is gone).
- The band passes are long: the per-sample helpers are inlined with their exact arithmetic, so a
  change to that arithmetic must be made where the band uses it, and the golden test proves it.
- The golden digests pin today's inputs: any intended change to Larch Hollow's region, the
  frameworks and POIs it places, world_gen.json or the generator needs a re-record (TD-125).
- Nothing loads differently yet: `WorldLoader` still composes every region at load with one band
  per region on three threads (session 3's Phase 2 brings the streamer, bands for the first area
  and the cancel flags), so v1's first load gains only the single-thread speed-up.
- In a debug build the noise pass doesn't scale with bands (TD-121); the LRU index is shared by
  processes on a last-writer-wins basis (TD-122).

Left for later: TD-121 (bands and the noise pass, the sequential steps), TD-122 (the cache index
across processes, flushing at exit), TD-123 (the generator's floods and routing), TD-124 (the
measurements of §7.4 items 5-8 and 10-12 and the `stream_walk` skeleton, for session 3),
TD-125 (the golden test's upkeep).
