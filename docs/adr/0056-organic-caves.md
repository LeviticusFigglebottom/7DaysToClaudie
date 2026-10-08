# ADR-0056: Organic caves through the SDF volume terrain

**Status**: Accepted · 2026-10 (rounds 3-4). docs/CAVES_PLAN.md was the working plan the parallel
streams coded against; this record keeps what landed and why. WS-F (GPU profiling, per-kind stream
budgets) is still open: see the end.

## Context
The world's caves were a POI's buried levels on the 1 m kit grid (TD-162): drifts and chambers that
read as a mine, boxy rather than organic. The terrain has had an SDF volume since ADR-0007 for digs,
but it could not hold a tunnel (TD-163): its faces never reached the nav tiles, its chunks never
streamed, a converted column repainted its surface, and `is_indoors` was false inside it.

## Decision

### 1. A cave is a pure, deterministic plan (`src/world/terrain/cave/`)
`CavePlan.build(spec, seed, height_fn, cfg)` builds from a spec, a seed and the **pristine** heights
(never dug ones):
* a mouth settled on a slope (≥ 18°, a shelter ≥ 30°) within `search` m, the spine starting 1.5 m
  outside the slope so the tube breaks through by itself;
* a Catmull-Rom spine of 3-6 points pitched 4-12° into the hill with a seeded yaw wander, sampled
  every metre into radii and floor heights;
* air as the union of warped capsules along the spine (a seeded 2 m lattice, precomputed: no noise
  calls in the hot path), an optional end chamber and side pocket, each cut by a floor half-space, so
  floors are flat and walkable;
* plan-time checks: cover ≥ `min_cover` past the portal, clearance ≥ `min_clear`, inside one region
  32 m from its border. A plan that fails is `ok = false` with a `reason` and is simply left out.
`density = min(h - y, cave_sd(p))`: a union, so the order caves are registered in doesn't matter.
`CaveSet` (immutable once published, indexed on a 64 m grid) answers `is_inside`, `floor_below`
and `keep_out`; `CaveSites` finds and settles mouths and reads a region's `cave` features. Styles
(`shelter`, `grotto`) and every number are in `data/config/caves.json`; `CavePlan.GEN_VERSION`
moves with a shape number.

### 2. Volume terrain streams (WS-B)
Density and mesh jobs run on workers under TerrainManager's task cap; applies are budgeted (~3 ms,
StreamMeter kind `volume`); a column commit is two-phase, so no heightfield hole shows before its
volume mesh; volume chunks attach and detach with their regions (digs of a detached region kept as
blobs); collision bodies only within ~160 m; `ground_below` reads the cave floor; a dig emits
`terrain_modified`; the boot carves the caves as a step of its own.

### 3. Nav, collision and AI (WS-C, round 4)
* NavTiles bakes the volume's faces with the heightfield holed over committed columns, and re-marks
  tiles on edits, volume applies and `caves_changed`.
* **The bake box takes the border** (round 4): Godot's `border_size` is taken from inside
  `filter_baking_aabb`, and the box was the bare 32 m tile, so every tile's polygons stopped 2 m short
  of its edges (since 1c6b830): no path crossed a tile edge anywhere in the world. The box is now the
  tile grown by the border.
* **The border strip**: surface nets put the volume's vertices at voxel centres, so its surface stops
  half a voxel short of a column's +X/+Z edge. `VolumeTerrain.is_ground_hole(x, z, h)` keeps the old
  heightfield in the last 1 m strip before such an edge (unless a dig took the ground under it), and
  both the nav source and the heightmap collision use it (a ball dropped there fell 9 m before).
* Rescue rules (an enemy below the ground, loose items, respawns) wait for and respect the volume.

### 4. Dark and surface (WS-D)
The volume shader paints with the region's splat and palette through the shared
`terrain_splat.gdshaderinc` (vertex weights from `VolumeSurfacePaint` on the worker); `CaveLighting`
adds 2-3 probes per cave in group `interior_probe`, boxes kept under the ground and daylight falling
with depth; `PoiManager.is_indoors` also asks `in_cave()` (and `room_type_at` says "cave");
ambience switches to the `ReverbCave` bus; `environment_controller.gd` gained only `min_share`.

### 5. Placement (WS-E, round 4)
* Region features `{"type": "cave", id, style, mouth, heading, search?, length?, seed?}` (docs/
  REGIONS.md), compiled on RegionStreamer's worker; runtime `TerrainManager.place_cave(id, spec)` /
  `remove_cave(id)` for encounters and set pieces. Registrations are not saved; only digs are.
* Larch Hollow has two authored grottos (`larch_hollow_grotto`, `logging_hill_grotto`), seeds
  written in so the checked shapes hold.
* Random worlds: `RwgGenerator._caves()` after every other stage from its own stream (so no other
  place moves): per region by `tuning.caves`, each checked with the real planner on the reference
  ground with the shape seed the game will use.
* Vegetation keeps off a mouth's apron by index, near and far (the far layer's worker holds the cave
  set it started with; the set is replaced, never changed), re-masking on `caves_changed`.

## Consequences
+ Caves you can walk into, dig on from inside, and that the Hollowed path through; random worlds have
  forest caves; the nav fix mends pursuit across every tile edge, caves or not.
− TD-279: the Hum's flow field is 2D on `height_at` and ignores caves: a base in a chamber is
  targeted on the hillside above it.
− TD-010 narrowed: the render mesh keeps the per-column hole test (its skirts hide the half-voxel
  slit); only collision and nav use the strip rule.
− `faces_in_rect` returns every triangle of a whole column (about 194k vertices of source for one
  cave tile, assembled on the main thread; 9 tiles bake in ~125 ms): clipping to the tile is a WS-F
  measurement to make.
− A random world's cave is planned on the generator's reference ground; in game it is re-planned on
  the composed region, whose detail noise can fail it, and then it is left out silently.
− Open (WS-F): `perf_capture` dense-forest and cave-mouth views and a GPU profile, `stream_walk
  --route forest`, per-kind budgets in `streaming.json`, docs/GPU_PROFILE.md.
