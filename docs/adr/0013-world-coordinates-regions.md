# ADR-0013: World coordinates, regions and streaming

**Status**: Accepted · 2026-10

## Context
The handcrafted map is 6–8 km and must grow by expansion; RWG must reuse the same machinery.
Float precision, streaming granularity, ownership of data and deterministic ids all hinge on one
coordinate convention.

## Decision
* **Main map**: 7 × 7 regions of 1024 m (7.2 km), world origin at the centre of region D4.
  Regions are addressed by cell (A–G × 1–7) and own a data folder
  (`world/main_map/regions/<cell>_<name>/region.json`): features (lakes, cliffs, hills, roads,
  paths, frameworks, POIs, biome paints, clearings, spawns, frontiers). World-level data
  (`world.json`): macro height corner grid, world roads/rivers that cross regions, region status.
* **Built vs coarse**: built regions compose at 1 m and stream full detail; others compose at
  16 m for far tiles only. Region borders blend features over 48 m so neighbours meet.
* **Streaming**: 64 m terrain chunks (LOD by distance), 64 m vegetation chunks (scattered
  deterministically per chunk), 32 m navigation tiles, 16 m volume chunks, POIs by distance.
* **Ids**: `veg:cx_cz:index`, `t:cx_cz`, `v:x_y_z`, `<placement>/<lot>` for POIs, allocator ids
  for player entities — stable across sessions, so saves store only differences (ADR-0005).
* Single-precision floats are sufficient within ±4 km; double-precision builds are not needed.

## Consequences
+ Expansion = add region folders / extend the grid; RWG emits the same region data.
+ Everything addressable by deterministic keys (multiplayer- and save-friendly).
− Region-crossing features must live at world level (world roads/rivers) to stay continuous.
