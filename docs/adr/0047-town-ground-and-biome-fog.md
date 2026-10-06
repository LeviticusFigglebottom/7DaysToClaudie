# ADR-0047: Town ground on the streets, a town mask for behaviour, and fog that follows the biome

**Status**: Accepted · 2026-10

## Context
Three loose ends from ADR-0040 and ADR-0041 (TD-136, TD-151, TD-152):
* An organic town painted the `town` biome over its whole disc. From above, every town was one brown
  disc in the meadows, and AmbienceDirector and the spawn tables relied on that paint to know they
  were in a town. A yard's grass grew within 2 m of its frame's edge, so it could reach under a
  building that filled its frame.
* Biome `fog_tint` was data that nothing read: a burn and a fen hung the forest's haze, and the fen's
  dawn mist was the valley's.
* Ash and peat drew grey before `make assets` and stepped like the forest floor; the audio catalog
  didn't hash the helper module the biome beds import.

Constraints: the composer is a function of world data alone (its cache key hashes inputs and
`TerrainComposer.VERSION`, not its code), and the main map must compose byte for byte as before
(`test_composer_golden.gd`). Which building stands on a town lot is chosen by `LotPicker` from the
*run's* seed, not the world's.

## Decision
1. **Paint `town` on the streets only** (composer VERSION 12). A town's own streets, and a world road
   inside its disc (the highway its main street is), paint `town` out to `TOWN_VERGE` (3 m, plus up
   to 2 m of noise) past their shoulders. The square stays `town`, the lots stay `yard`, and the
   ground between keeps the world's biome (the generator already leans a town's disc to meadow).
2. **Town behaviour keys on a mask, not the paint.** `WorldDef.town_at(x, z)` is the town whose disc
   holds the point, within its built bounds grown 20 m. `WorldDef.behaviour_biome(composed, x, z)`
   returns `town` there unless the ground is already `town` or `yard`. AmbienceDirector and
   AiDirector's spawn table and density use it; yards play the town bed, as their data always said.
3. **Yard grass keeps off the largest authored footprint the lot may hold**
   (`LotPicker.max_authored_footprint`: the same filter as the pick, without the per-framework
   dedupe), centred in the frame, fading in over a metre past it. Since the building is a run-seed
   choice, the clip is the union of what could stand there (TD-181). Generated buildings keep
   their own side and back yards inside the frame and need no clip. The input hash covers those
   buildings' footprint, tier and zoning.
4. **VERSION 12** for (1) and (3): random worlds with towns compose differently. The random-world
   golden digests were re-recorded; Larch Hollow's outputs held at 1, 4 and 8 m. A random-world save
   from before this re-scatters vegetation in its towns (TD-182).
5. **Fog follows the biome.** EnvironmentController samples the biome at the camera and four points
   40 m round it twice a second (weights 0.4 and 0.15 each) and eases toward the result over about
   3 s. The fog colour, the volumetric albedo and the ground fog's albedo are multiplied by the
   blend of `fog_tint` divided by the conifer forest's, with the luminance taken out and pulled
   `biome_tint` (0.6) of the way from white. The forest, and so the main map, looks as before; a
   biome changes the fog's hue, not its brightness. In a fen the hour's ground fog is up to 1.9x
   thicker and 2.5 m deeper (`fog.fen_pool`), so it pools at dawn and dusk and is gone by noon.
   Numbers in `weather.json` `fog`.
6. **Ash and peat**: `TerrainTextures.FALLBACK_COLORS` has both; footsteps on them use the `dirt`
   set until their own are generated (TD-185). `@sound(..., sources=[...])` declares helper
   modules; the four biome beds declare `ambience.py`.

## Consequences
+ From above, a town reads as streets and yards in the meadows; walking between two streets still
  sounds and spawns like town.
+ No yard grass grows through a floor, whichever building the run draws.
+ A burn's haze is dusty and warm, a fen's grey-green, and the fen's mornings are its own.
− The yard clip is conservative (TD-181), and the town mask has a hard edge (TD-183).
− Old random-world saves may shift felled trees and harvested plants in towns (TD-182).
− The fog numbers are unverified by eye (TD-184).
