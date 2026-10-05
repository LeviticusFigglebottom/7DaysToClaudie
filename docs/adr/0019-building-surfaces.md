# ADR-0019: Built and open-ground surfaces: wear, roofs, roads, meadows, riverbanks

**Status**: Accepted · 2026-10

## Context
POI interiors and exteriors were the weakest surfaces in the fidelity pass (ADR-0017):
* The kit finishes baked large peels, torn wallpaper and stains into tiles that repeat every 1 m
  (walls) or 2 m (floors). Every wall showed the same blotch each metre and read as camouflage.
* The decay overlay replaced the finish colour, so a water stain on dark paint became a cream blob.
* The overlay was offset per piece, and decay was jittered per piece, so stains broke at every 1 m
  seam.
* Rooms had no baseboards. Ceilings sampled the wall finish at twice its scale.
* No roof material existed, so every roof fell back to one flat colour, the most visible surface in
  town from any height.

## Decision
* **Finishes stay clean; wear is composed in world space.** `kit_wall.gdshader` builds stains,
  drips, grime, mould and peeling from two tileable mask textures (`kit_decay_albedo`,
  `kit_decay_orm`). They hold uniform coverage priorities (rank-equalised, so coverage is linear in
  the threshold) and detail channels, sampled continuously in world space at 2.5 m. A coarser
  sample of the same masks scales each layer per room-sized zone, so one corner is damp and the
  next is dry.
* **Thresholds come from the building's decay and the height in the room.** Decay is the building's
  `style.decay` with no per-piece jitter (the builder still makes the RNG draw, so later sequences
  don't shift). Height is the piece-local `VERTEX.y`, which is 0 on every storey's slab wherever the
  building stands. The old code used world `y` modulo 3 m, which was arbitrary per building.
  * Leaks start under the ceiling and drip down; grime collects low.
  * Mould grows along floors, ceilings and wet-room tile.
  * Paint and wallpaper peel to plaster or backing paper; ceilings peel to the lath.
  * Outside, rain draws vertical streaks and algae grows near the ground.
  * Stains are part tint, part pigment, so dark paint takes a brown cast instead of turning black.
* **Baseboards are drawn by the shader.** Interior faces of plaster, paint, wallpaper and panelling
  get an 11 cm painted or stained board with a lit top edge and a shadow above it. This needs no
  geometry, so the kit pieces and their budgets are unchanged.
* **Masks import as BC7** (new `mask` import kind): S3TC compresses RGB channels together within a
  block, which bleeds unrelated masks into each other.
* **Roof coverings are generated sets** (`roofs.json`): asphalt shingles (two), corrugated metal (two),
  cedar shakes, and tar and gravel. They are chosen by `style.roof.material`.
  * Pitched-roof UVs are metres with V up the slope, so the sets are drawn eave-down and flipped.
  * A roof is one mesh with a 2 m texture, so `std_surface` gains an opt-in world-space
    `macro_variation` that drifts its tone over metres.
* **Roads get painted lines.**
  * `RoadMarkings` lays decals along every two-lane asphalt road (≥ 6 m) recorded in
    `RegionTerrain.roads`: a dashed yellow centre line (3 m on, 9 m off) and white edge lines in
    6 m segments.
  * The decals follow the composed road profile and skip bridge decks.
  * Each fades out past 55–80 m, so a long road costs nothing beyond the player's stretch.
  * The asphalt crack network was cut to a few long cracks; a polygon net everywhere read as dried
    mud.
* **Riverbanks are planted.** The `riverbank` biome gets slough sedge and rush clumps, horsetail,
  Pacific willow shrubs and bleached driftwood (new `riparian` atlas and `driftwood` set), so the
  Tamsin's banks read as a wet Pacific-Northwest margin instead of grass on mud. Its weights
  changed, so the riverbank scatter indices did too (saved harvests there are dropped by migration).
* **Grass patches cover their cell.** The ground layer places at most one plant per 1.25 m cell.
  Grass clumps are now ~1.6 m patches of a dozen tufts, with a `_lod1` past 40 m, so a meadow reads
  as continuous grass. Only the models changed, so scatter indices and saves are untouched.

## Consequences
+ Interiors vary across a room and between buildings with no visible tiling, and the same masks
  serve every finish. Decay values in POI specs now read as intended: ~0.3 lived-in, ~0.7 derelict.
+ Roofs read as shingle, tin or shake from the ground and from the air; Route 9 reads as a road.
+ Meadows are continuous grass to the scatter distance over an olive ground that matches the clumps.
− `kit_wall.gdshader` costs three more texture fetches per pixel; it only draws walls and floors.
− The mask file names (`kit_decay_albedo/orm`) are kept for the builder and no longer describe
  their content.
− Flat roofs (a box mesh with a flat colour) don't use `roof_tar` yet: `RoofBuilder._flat` needs
  metre UVs first. Roofs still have no fascia, ridge caps or gutters (TECH_DEBT).
− Meadow grass costs more triangles per instance; the grass-density setting still thins it.
