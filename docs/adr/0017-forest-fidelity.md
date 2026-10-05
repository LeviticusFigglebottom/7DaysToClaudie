# ADR-0017: Forest-level asset fidelity: dense patchy ground cover, bigger budgets, triplanar rock

**Status**: Accepted · 2026-10

## Context
A fidelity pass aimed the generated assets at the look of The Forest / Sons of the Forest. The
gap was largest on the forest floor: bare dirt with an even sprinkle of small ferns, culled per
64 m chunk. Smaller gaps were spiky dead branches, flat fir bark, Voronoi larch bark, blurred moss,
rounded-box boulders with UV seams, faceted Hollowed faces and loose first-person grips. Several
fixes change budgets, shaders or the scatter layout that saves address, so they are recorded here.

## Decision
* **Ground cover fades per plant.** The ground layer is batched in 32 m blocks, not 64 m chunks. Each
  instance carries its fade distance as a negative `INSTANCE_CUSTOM.a`. The `foliage` and
  `std_surface` vertex shaders shrink such an instance between 80 % and 100 % of that distance.
  Other MultiMeshes keep `.a >= 0`, so POI kit batches, which also use custom data, are unaffected.
  A block is drawn while any of its plants can be inside the distance (fade + half a block
  diagonal). Ferns switch to their `_lod1` in blocks farther than 40 m, with a dithered
  cross-fade. Litter fades out at 30 m.
* **Patchy medium and ground layers.**
  * A low-frequency field scales placement: ground ×0.5..×1.5, medium ×0.4..×1.6.
  * Each species reads the field at its own offset, so ferns, moss and litter dominate different
    patches.
  * No random draws were added, so the sequences stay stable. The tree layer is left uniform
    because its indices address felled trees.
  * The medium and ground indices changed. Save version 2 therefore drops harvested-plant records
    and keeps stumps.
* **New ground kinds** `moss` and `litter`. Moss mounds and twig-and-cone litter follow the
  terrain slope (`VegetationScatter.ground_tilt`). Moss mounds use the terrain's moss texture
  set, so they match the floor around them.
* **Budgets rise where they show.**
  * Hollowed bodies go from 10k to 16k triangles; the head goes from 1.7k to 4.2k. At 1.7k the
    face decimated into jagged eye sockets.
  * First-person arms go from 3.9k to 6k per arm.
  * Fir LOD0 goes from 9k to 10.8k, so the crown keeps every card next to the new broken stubs.
  * Boulders go from 1.5k to 2.4–3k, plus a decimated `_lod1` past 90 m.
  * Import LODs (characters) and explicit LODs (vegetation, boulders) bring distant copies back
    down.
* **Triplanar `std_surface`.** The `triplanar` parameter (UV units per metre, 0 = off) maps
  albedo, ORM, normal and the moss layer in object space. The normal is built with a whiteout
  blend, with tangent signs fixed for Godot's right-handed frame. Rocks use it, because their
  box-projected UVs showed jagged seams across faces.
* **Boulders cast shadows.** Every colliding rock now casts a shadow; loose pebbles still don't.
* **Held tools are gripped.** `fp_idle_grip` and `fp_walk_grip` close the right hand around a held
  item. The viewmodel plays them whenever something is in the hand.

## Consequences
+ The forest floor reads as lush and varied up to the grass distance, with no chunk-sized pops.
  Moss, litter and ferns cluster naturally.
+ Faces, hands and rocks hold up at arm's length.
− More triangles on screen: dense ground cover (up to ~1M triangles in view), larger bodies and
  firs. The grass-density setting thins grass, litter and flowers; ferns and moss stay.
− Tree LOD selection is still per 64 m chunk (block-level visibility applies only to ground cover),
  so a neighbouring chunk's trees can switch to LOD1 at ~35 m (TECH_DEBT).
− A triplanar material samples each map three times. Only rocks use it.
