# ADR-0007: Heightmap chunks + smooth SDF volumes for digging, tunnels and caves

**Status**: Accepted · 2026-10

## Context
The brief asks for organic (non-voxel-looking) terrain that supports runtime deformation, smooth
caves/tunnels/mining, seamless transitions, collision and incremental navmesh updates, over a
6–8 km handcrafted map plus RWG. Pure voxel terrain (marching cubes everywhere) costs memory,
meshing time and draw distance; a pure heightmap can't express overhangs or tunnels.

## Decision
* **Surface = heightmap.** Regions are composed at 1 m (built) or 16 m (coarse) by
  `TerrainComposer` (deterministic, cached by input hash). `TerrainManager` streams 64 m chunks
  with distance LOD (1/2/4 m), skirts, far tiles per region, and `HeightMapShape3D` collision near
  the player. Shovel digging edits heights (clamped to `MAX_DIG_DEPTH` below the composed
  surface); edits persist as per-chunk delta blobs `t:x_z`.
* **Below/inside = SDF volume, on demand.** `VolumeTerrain` owns 16 m chunks of 0.5 m voxels.
  When a dig goes past the heightmap's limit, into a steep face, or with a pickaxe, the 16 m
  columns under the dig are *handed off*: chunks are initialised from the heightfield
  (density = height − y) so nothing visibly changes, the heightmap stops drawing those quads
  (`TerrainMesher` hole callback) and sinks its collision there, and the volume renders and
  collides instead. Edits are smooth sphere subtractions/additions; meshing is naive
  **surface nets** (smooth, table-free) on worker threads, with padded samples so neighbouring
  chunks build the identical seam. Collision = `ConcavePolygonShape3D` from the same triangles.
  Edited chunks persist as quantised, compressed blobs `v:x_y_z`.
* **Caves** (M2) are authored/generated directly as volume columns using the same chunks.
* **Navigation** bakes from heightfield faces plus volume triangles (`faces_in_rect`), rebaked
  per 32 m tile on `Events.terrain_modified`.
* **POI cellars** cut holes in the heightmap (TD-026): `TerrainHoles`, derived from the POI
  placements at load and never saved, is subtracted exactly (clipped triangles, not whole quads)
  from the near meshes at every LOD and their skirts, from the collision (a trimesh in the chunks a
  cellar touches; a heightmap can only drop whole quads), from the navigation ground faces and from
  volume columns initialised over a cellar. The POI's own cellar walls stand on the cut
  (docs/POI_AUTHORING.md "Cellars and terrain").

## Consequences
+ Cheap, good-looking terrain everywhere; volumes only where the player (or a cave) needs them.
+ One persistence model (chunk blobs) for both representations.
− The hand-off seam is interpolated differently (1 m bilinear vs 0.5 m isosurface): sub-5 cm
  steps can appear on steep ground at column borders (TECH_DEBT TD-010).
− GDScript meshing costs ~0.1–0.3 s per chunk on a worker; a GDExtension mesher is the upgrade
  path if mining becomes heavy (criteria in ADR-0004).
− `height_at()` (AI, placement) reports the heightfield in volume columns; pits/tunnels are only
  known to physics and the navmesh. Over a POI cellar it reports the surface too;
  `ground_below()` knows the cellar floor.
− A chunk with a cellar in it collides through a ~8k-triangle trimesh instead of a heightmap shape.

## Alternatives considered
* Full voxel world (Zylann's godot_voxel style): best fidelity, but a C++ dependency/build and
  heavy for an 8 km map; rejected for M1 (revisit for M3 caves if needed).
* Heightmap holes only (no volumes): no tunnels — fails the brief.
