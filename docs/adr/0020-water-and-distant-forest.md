# ADR-0020: Water and the distant forest

**Status**: Accepted · 2026-10

## Context
* **No lake or river had ever been drawn.** `WaterSystem` flipped the triangulated lake faces and
  wound the river strip the same way, so every water face pointed down and back-face culling
  dropped it. Swimming and water queries read the data rather than the mesh, so nothing failed.
  The screenshots showed dry, sandy basins, and these were taken for pale water.
* **The water shader lit the surface as a material.** Without screen-space reflections the engine
  mirrors only the bright sky at grazing angles. A forest lake almost never shows that: its far bank
  is a wall of dark trees.
* **Distant forest had no height.** Far terrain tiles (16 m, every unbuilt region) drew forested
  hills as flat dark ground. Past the impostor range (1.2 km) the valley's forests had no height,
  so ridgelines read bald.
* **The near terrain square left a hole.** Within 416 m of a built region's edge, the near square
  reaches into unbuilt regions. Its chunks there used the far material, which discards everything
  inside the near square, so the world had a hole.

## Decision
* **Water faces up.** The winding is fixed, with a regression test.
* **The water shader draws the light the surface sends to the eye.**
  * Body: the refracted scene (screen texture), absorbed toward a dark, tannin-tinted water colour
    with the depth-buffer thickness.
  * Reflection: the sky gradient. `EnvironmentController` publishes it every frame as the linear
    globals `hm_sky_zenith` and `hm_sky_horizon`. Low reflected rays meet the tree line instead: a
    ragged band of conifer spires, which the ripples break up.
  * The tree line is measured, not assumed. For each water vertex, `WaterSystem` finds the nearest
    forest along rays toward +X, +Z, −X and −Z (canopy from `TerrainManager.canopy_at`) and stores
    the elevation of its crown tops, bank rise included, in the vertex colour. The shader weights
    the four by the reflected ray's heading. A pond in the woods shows a tall dark band; a river
    through a meadow shows the sky down to a thin far-off line.
  * The two are blended by Schlick Fresnel and written as `EMISSION`, with black albedo and ambient
    light off, so the engine adds only the sun's glint.
* **Unbuilt regions get a canopy.** Their far tiles rise by up to 17 m.
  * The canopy is cover × crown height, both from the content: the tree density of the biome's
    species, over 3 per 100 m², times the mean crown height (¾ of tree height) over 17 m.
  * It is masked by the region's vegetation mask (roads, water and clearings stay open) and fades
    out within 200 m of a built region, whose own trees and impostors take over.
  * The raise is baked into the mesh heights, so the mesher's normals light the forest edges. The
    shader lowers it again within 96 m of the near square, where the tile is cut away and a raised
    edge would show sky under it.
* **The canopy shades by species and season.**
  * `COLOR.a` packs the canopy into the high 4 bits and the deciduous share into the low 4. The
    share comes from a new `deciduous` flag on species. The shader decodes both per vertex, before
    interpolation would mix the bits.
  * Conifers stay dark green. Deciduous crowns follow `hm_season`: bright in spring, yellow in
    autumn, bare grey-brown in winter.
  * Crowns shade as lit tops and dark gaps from world-space noise, with matching normal relief.
    The detail fades out where it would alias.
* **Near chunks in unbuilt regions** use a terrain material built from that region's coarse
  (16 m) splat, made on first use. The far material is never a near-chunk fallback.
* **Clear days read clear.** The froxel fog's floor drops from 0.0015 to 0.001 per metre, and
  clear weather from 0.004 to 0.0025. At noon, a pond's far shore at 100 m was 30 % veiled and is
  now under 20 %; mist, rain and the morning valley mist are unchanged.
* **Instance uniforms pin explicit indices.** `weather_exposure` is index 3 in both `std_surface`
  and `kit_wall`, because materials batched on one instance must agree on each name's slot.

## Consequences
+ Larch Pond, the Tamsin and Hollowmere Lake exist. Forest water reads dark, with a broken
  reflection of the tree line.
+ Forested hills keep their silhouette to the horizon. Birch groves stand lower and turn with the
  seasons.
− The reflection is a model of the bank, not the bank: the spires are generic firs whatever
  grows there, and nothing on the water (bridges, boats, the player) reflects.
− Canopy edges step with the far tile's 16 m grid, and both packed values have only 16 levels.
− Near the edge of the built region, the canopy beyond the near square recedes as the player
  approaches, because its fade follows the moving square.
