# ADR-0025: The Bloom on the land: an authored infestation field, threads, web, fruit and mounds

**Status**: Accepted · 2026-10

## Context
The Bloom is the game's antagonist, and DESIGN §1 sets the tone as "a beautiful autumn wilderness
with wrongness underneath: pale threads on the larches near infested ground". Nothing in the world
showed it. The forest read as a healthy autumn wood, and only the Hollowed told the player the
ground was infested. DESIGN §6 also promised that Hum survivors collapse into the soil as fungal
mounds at dawn. They despawned instead.

## Decision
* **One field, authored and deterministic.** `BloomField` holds colonisation 0..1 on a 2 m grid
  over the built regions.
  * Zones are region features: `{"type": "bloom", "at": [x, z] | "points": [[x, z], ...] |
    "poi": <placement id> + "offset": [x, z], "radius", "strength", "edge"}`. These are a patch, a
    seep along a polyline, or a patch anchored in a POI's own frame.
  * `data/config/bloom.json` holds the per-POI defaults, keyed by POI def. Buildings whose story
    kept the sick there (the clinic, the logging camp) carry a zone wherever they are placed,
    unless the region anchors its own zone to that placement.
  * Shape: each zone's radius swells along its boundary (lobes) and shoots out sparse tongues. A
    tongue tapers because a spike in the radius narrows the further out it reaches. The point is
    domain-warped, so the tongues bend. The edge frays at 16 m, and the inside is mottled. All of
    this uses noise seeded by the world seed and the zone id.
  * Nothing grows on water, roads, paths, pads or clearings: the field is scaled by the
    composer's vegetation mask.
  * Overlapping zones merge as a soft union, 1 − Π(1 − v).
  * The whole field (Larch Hollow: 512 × 512 texels) builds in about 0.4 s at world setup
    (TerrainManager), so it needs no cache.
* **Published as shader globals, read the same on the CPU.**
  * `hm_bloom_map` is an R8 texture, sampled bilinearly. `hm_bloom_rect` maps the world onto it;
    it is zero when there is no field, so menus and previews show nothing. `hm_bloom_night` is the
    glow level, set from the sun's elevation by `BloomWorld`.
  * The shared include `bloom.gdshaderinc` reads them: the field, metre-scale raggedness, the
    pulse and the glow.
  * `TerrainManager.bloom_at(x, z)` reads the same texels bilinearly, from any thread. It is there
    for infection exposure, Hollowed density and audio later.
  * `bloom_base_at` is the authored field only. The vegetation scatter reads it, because dynamic
    spots must never change scatter results.
* **Threads and webs are revealed by rank-equalised priority masks.** These are generated
  textures (`textures/gen/bloom.py`), drawn as anti-aliased strokes on a periodic canvas.
  * The R channel ranks every pixel. Thread pixels rank by importance: cords, then branches and
    fans, then the fine net. Gap pixels rank below all of them, by distance to a thread.
  * A threshold `t = 1 − field × F`, where F is the thread share of the tile, shows exactly that
    share, in importance order. So threads extend as the field rises; they don't fade in.
  * A threshold only holds while a texel covers a pixel or more: on mipmapped priorities it turns
    the web into blotches (the first renders read as snow). So each mask has a coverage map: the
    binary masks those thresholds reveal at a third, two thirds and all of full growth. The GPU's
    mipmaps of a binary mask are the exact share of threads in a footprint, so from about one mip
    level the shaders read the share at the current growth from it, and fade it with distance
    (the threads are hair-thin). Far LODs use the same path and keep a faint pale cast.
* **Ground (terrain.gdshader).** The ground has three layers:
  * Rot drains some of the litter's colour, a quarter of the way to grey.
  * A cream-white web binds it. The tile is 1.6 m, made of cords from colony points on a jittered
    grid, anastomoses and feathery fans.
  * In the strongest ground, a cottony mat fills the litter's hollows, where the blended layer
    height is low.
  * Web and mat are hidden on cliff faces and under snow.
  * Beyond a few metres every pixel holds a share of threads, and a share of near-white threads
    over dark litter brightens it a lot. With a white-grey web, litter greyed halfway and the
    veil fading only to 45 %, the deep wood's floor came out 2–2.3× as bright as clean litter
    with half its saturation, and under the cold sky light it read as old snow. The web is now
    cream, the litter keeps more of its colour, and the veil thins to 55 % opacity and fades to
    30 %, so the floor is 1.2–1.7× as bright as clean litter. In full sun it still reads as a
    cream veil past 2–3 m rather than as threads (TD-062).
* **Bark (bark.gdshader).** Cords climb from the roots in the bark's UVs. They are periodic in V,
  so they run on across tiles, and fans open up the trunk.
  * How far they reach depends on the field at the tree's foot, the material's `bloom_affinity`
    (larch 1.0, dead wood 0.9, fir 0.75, birch 0.55) and `bloom_climb` (larch 4.2 m).
  * World-space 3D noise clumps them into tongues that climb higher on one side of a trunk and
    differ from tree to tree.
  * Bracket-like crusts show low on the most colonised trunks, gated by world noise so the tile
    doesn't repeat them.
  * Impostors are unchanged; past the impostor distance the cast would be invisible.
* **Plants (foliage.gdshader).** Plants wilt by material opt-in (`bloom_wilt`).
  * They drain to a dead tint (`bloom_wilt_tint`: ferns tan-brown, grass grey), lose their
    translucency and thin out (`bloom_thin`).
  * Fronds droop and curl in by the wind weight squared (`bloom_droop`). No new models are needed.
* **Fruiting bodies are a new scatter layer.** `VegetationScatter` gains a fourth layer, `bloom`,
  for the kind `fungus`. It is the last layer, so no tree, plant or stone index that saves address
  can move.
  * Its chance is the biome density at full strength × field^1.6. Nothing fruits below 0.12.
    The mycelium feeds on roots: the chance rises up to 3.5× within 2.6 m of a trunk, and nothing
    fruits inside a trunk's flare. In the deep wood that is up to about 250 clusters in a 64 m
    chunk, and the layer adds about 6 ms to that chunk's scatter; chunks the field doesn't reach
    skip it after a 4 m probe.
  * The species is `bloom_caps`: four generated clusters (`veg_fungus.py`) with real stems, caps
    of revolution, gills and partial gills: a tight cluster of every age, an old troop gone flat
    and upturned, young bells along a buried root, and caps fruiting from a felt cushion. Each has
    a broken piece: a snapped cap lying gills-up, or in the old troop a toppled mushroom and a cap
    torn half away. All carry baked vertex AO. LOD0 is 758–962 triangles, LOD1 170–282; caps under
    4 cm across keep a plain underside.
  * Clusters are honey-fungus sized (caps 3–13 cm across), so they read from 10–15 m. They are
    drawn as ground cover that shrinks away by 36 m. The `bloom_fungus` shader is
    double-sided: translucency through the thin margins and gills (vertex B), greyer gills (G)
    that glow faintly at night.
* **The night glow is cold, dim and slow.**
  * It is a pale green-cyan (the aurora's family, colder) in the thread mask × `hm_bloom_night`.
  * It brightens 2.4× at the Hum's peak (`hm_bloom`, from EnvironmentController).
  * It breathes over about 10 s, out of phase across the land, and only ever dims to 70 %. Each
    material's `bloom_glow_energy` (0.035–0.06) keeps it a faint presence, not a light source.
* **Dawn rooting leaves a mound (save v4).**
  * Enemy emits `Events.hollowed_rooted` (one line) where a Hum survivor roots.
  * `BloomMounds` stores the mound in `WorldState.mounds`: position, yaw, model, day and whether
    it was harvested. It grows a generated mound there: a body-length lump of felted mycelium
    over a curled form, with caps fruiting from its back.
  * A mound swells over 6 h, then shrinks and sinks until 6 days have passed, and is then dropped.
  * While it stands, it adds a dynamic spot to the field. Only those texels are re-uploaded, so
    the web, threads and wilting reach out around it.
  * `bloom.harvest_mound` tears it open once, within reach: 2–4 Bloom mycelium and a 12 % chance
    of a core sample.
  * Migration 3 → 4 adds the empty ledger.

## Consequences
+ The land now shows the Bloom before the Hollowed do: a deep wood north-east of the Tamsin, the
  mill and Larch Pond's shore, a seep down the river, the clinic's back lot and the logging camp.
  The drop site stays clean, and a test checks it.
+ Other systems get a cheap query to build on: infection exposure, spawn density, ambience.
+ Mounds give the dawn after a Hum a visible aftermath and a reason to go out: Bloom mycelium.
− Three more shader globals, one of them a texture, and one more texture fetch per vertex in the
  bark and foliage shaders (the field at the plant's foot). The terrain and the bark fetch their
  mask, its coverage map and its normal map only where the field is set (TD-064).
− The field covers the built regions only. Far terrain tiles and impostors show no Bloom.
− POI defaults apply to standalone placements, not to buildings on framework lots (TD-061).
− Thread masks follow the bark UVs, so they stretch a little on tapering trunks and thin branches
  (TD-062).
− Mounds keep no per-chunk streaming and no navmesh obstruction: their collider is a low box
  (TD-063).
