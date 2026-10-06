# ADR-0041: Burnt forest and fen: fire scars and drowned lowland in random worlds

**Status**: Accepted · 2026-10

## Context
Random worlds (ADR-0031, ADR-0040) had four biomes since v1: conifer forest, birch grove, meadow
and rocky slope. DESIGN §10 names a burnt forest (Burnwood) and a fen (Sallow Fen) on the main
map, and §10.2 promised burnt and swamp biomes to the generator. A generated valley read as one
forest broken by meadows; nothing in it told of a past. The owner's bar is The Forest's fidelity:
the new ground has to hold up at eye level, in rain and at dawn, not only on the map.

Constraints: deterministic per seed and settings; the main map (Larch Hollow) must compose byte for
byte as before (`test_composer_golden.gd`); saves address scatter instances by index, so nothing
may change where the existing species grow; every asset generated; the terrain shader takes eight
splat layers per region.

## Decision

### 1. Two biomes and their content (data)
* `burnt_forest`: an old burn, years after. Fire-killed snags (1.1 per 100 m², against 3.5 trees in
  conifer forest: open sky through dead crowns), a few survivors, charred windfall and fire-hollowed
  stumps, sooted boulders, and regrowth that makes it beautiful as well as grim: fireweed drifts,
  bracken, lodgepole seedlings, grass in the gaps. Ground: ash and char, grass in drifts, bare burnt
  soil. A warmer, dustier `fog_tint` (`#b4a996`; nothing reads biome fog tints yet, TD-151). Spawns for open ground with long sightlines:
  more lurchers (they sprint) and keeners (they see you from far and call the rest).
* `fen`: the drowned lowland. Stunted black spruce and tamarack, grey drowned snags, cattail and
  bulrush stands, willow, sedge tussocks, sphagnum hummocks, skunk cabbage, horsetail. Ground: peat,
  sphagnum carpets on the rises, sedge meadow, muddy pool margins. The Bloom pools here: Bloom
  patches may take fens (`_bloom`), bloom caps grow at 9 per 100 m² (conifer forest 6), and the
  spawn table runs to draggers (in the reeds), blisters and husks at 1.3x density.
* New species (`species.json`): `burnt_snag`, `burnt_log`, `burnt_stump`, `sooted_boulder`,
  `bracken`, `lodgepole_sapling`, `sphagnum_hummock`, `cattail`, `bulrush`, `skunk_cabbage`,
  `tamarack`, `black_spruce`, `drowned_snag` (the dead snag models, wading).
* **Waders.** `SpeciesDef.wade_depth` (m, default 0): the scatter's water test becomes
  `water > ground - 0.15 + wade_depth`, so cattail (0.6), bulrush (0.7) and drowned snags (1.2)
  stand in the fen's pools and nothing else does. Every existing species keeps 0, so no existing
  scatter index moves.

### 2. Assets (generated)
* **Terrain layers** (slices 11 and 12, appended): `ash_char` (crusted burnt soil, charred needles,
  charcoal pieces with cracked faces, blackened twigs, sooted pebbles, the rust needles the dead
  crowns shed, then a powder of fine ash over it all, thicker in the hollows, with grains of white
  wood ash, a little fire moss; no drifts or white patches at tile scale, which a 3 m tile repeated
  across the burn like polka dots) and `peat` (black-brown muck in low hummocks with old prints,
  reddish fibres, flattened sedge, red and green sphagnum cushions, a film of tannin water in the
  deepest prints; roughness ~0.3; standing water is the weather's puddles and the pools, since a
  mirror-water quarter in the tile showed as repeated pale plates).
  Weather tables: ash puddle 0.55 / porosity 1.0 (wet ash darkens most), peat 1.0 / 0.3.
* **Fire char** (`bark.gdshader`, opt-in by `char_amount`): `bark_char` is alligatored charcoal,
  blocks of uneven height in wavy columns up the trunk (a quarter of the cross-cracks never opened:
  even rows read as basketwork at eye level), each with crazing, a dull silvery sheen on the tops,
  ash in the fissures. The `bark_burnt` material lays it over the silver weathered wood of
  `bark_dead` from the roots up to a ragged char line: `char_height` m (2.9; mostly 1-5 m, so a
  trunk at eye level shows char and silver wood both), higher on one (lee) side of the trunk,
  different on every tree (`char_ragged`, world noise at the foot), fraying into scorched tongues,
  with a soot-grey fade above it. One material, no new mesh split, so LODs and impostors come free.
* **Snags** (`generators/veg_burn.py`, on `veg_tree.py`'s trunks, roots and broken tops): five, fir
  and larch, spike tops and snapped crowns, crowns burnt to bare branch skeletons (fir: many,
  drooping, broken back; larch: fewer, level, mostly broken), the lower trunk's stubs; LOD0/1/2 like
  the live trees. **Fire-hollowed stumps**: a broken shell round a charred cavity, a jagged rim low
  where the fire ate through, roots, a hull collider. Charred windfall, the felled snag's stump and
  log, and sooted boulders (`rock_sooted`: granite under grime and world-space soot patches) are
  catalog entries of the existing generators.
* **Plants**: `fen_plants`, a painter atlas (cattail, hardstem bulrush, skunk cabbage leaves and
  spathe, bracken fronds and fiddleheads) built by the existing grass and fern builders; lodgepole
  seedlings are the sapling builder with a young-pine material; sphagnum hummocks are moss mounds in
  two generated sphagnum sets (red-dominant, green-dominant) on the terrain compositor.
* **Ambience** (`audio/sounds/biome_beds.py`): `amb/burn_day|night` (a hollow wind whistling past bare
  trunks, snags creaking and ticking, black-backed woodpeckers, dry fireweed rustling) and
  `amb/fen_day|night` (breeze in the reeds, flies, marsh gas bubbling; from dusk chorus frogs,
  peepers, a green frog's plucked note and crickets). `AmbienceDirector` plays a biome's own beds,
  `amb/<ambience>_day|night`, where they exist, and the forest's elsewhere, as before.
* **Water**: lakes whose id begins `fen_` get a tannin material (tea-dark shallows, near-opaque
  depths). `WaterSystem` indexes lakes on its 32 m grid: `water_level_at` ran over every lake, and
  the vegetation scatter asks it for every plant; fens put dozens of pools in a world.

### 3. The generator places them (`RwgGenerator.VERSION` 4)
* Settings: `burn` (default 0.4) and `fen` (0.35) on the World tab's Land category (the panel builds
  its controls from `world_gen.json`); presets lean them (highlands burn, lakeland fens, wild country
  both). `tuning.burn` and `tuning.fen` hold the numbers; `WorldGenSettings.schema_errors` types them.
* **Fens** take the lowest, flattest, wettest ground after the four base biomes are scored: slope
  under 0.075 (macro grid), within 420 m of a river or lake, low on the map or 8 m under the ground
  400 m round (valley floors), broken into patches by their own noise, never within 80 m of a town's
  disc or 220 m of the drop site.
* **Fire scars**, after the majority pass (their ragged edges and skipped islands are the point):
  `floor(burn x area / 16 km² x 3 + a draw)` fires lit in forest, each spreading cheapest-first over
  the 64 m biome cells to its size (45-650 cells, small ones likelier: a few hundred metres to a
  couple of kilometres across; no scar past 9 % of the map's cells and all of them past 18 %, so a
  3 x 3 map is not one burn). Downwind and uphill run fastest, meadow (x2.6) and rock (x1.8) slow
  it, noise makes the fingers; it crosses ridges. Rivers and lakes (48 m), roads (48 m), fens, towns
  (+120 m) and the drop site (260 m) stop it. It burns forest and rock to `burnt_forest`, leaves
  meadows as meadow and noise-picked islands green.
* **Fen pools** are region `lake` features (`fen_pools`): per fen cell, a chance of 1-3 irregular
  ellipses 5-15 m across, inside the fen all round, 72 m inside the region (local features fade at
  borders), on level ground, clear of rivers and lakes, roads, paths, lots and streets, places,
  trader posts, the drop site and each other. The composer reads two new optional lake keys: `drop`
  (the water stands that far under the ground round it: 0.28 m, brim-full; default 1.8 m as before)
  and `probe` (the step of the level's sample spiral, default 4 m). The bed is 0.35 + 0.65 m deep at
  most, so **the player wades** (slowed past 0.5 m) and never swims (1.25 m).
* **Palettes**: a region with burnt forest or fen cells (its rect grown two cells, the composer's
  edge wander) gets `palette` in its region.json: `ash_char` / `peat` replace `sand` (lake coves fall
  back to mud and gravel), then `asphalt_cracked` where no paved road, town or trader post comes
  near, else `moss_ground`. Kept layers keep their channels. Other regions keep the default.
* `BIOMES` appends `burnt_forest` (4) and `fen` (5); region counts, the majority pass and dominant
  biomes run over all six. The map draws burns ash-brown, fens olive, their pools as dark water.

### 4. The composer paints them (additive; `TerrainComposer.VERSION` stays 11)
* Kinds `K_BURN` and `K_FEN` with their splat recipes. Ash or peat fall back to dirt or mud in a
  palette without them.
* In a fen the riverbank override and the lake-shore recipe (sand coves, gravel) give way to the
  fen's own margins, a pool's bed is peat and muck, and the vegetation mask stays at 0.55 in the
  pools (waders only, by the scatter).
* Every change is gated on the new biomes or the new lake keys: the main map and v1-v3 worlds
  compose byte for byte as before (the golden test's Larch Hollow digests hold; its generated-region
  digests were re-recorded for VERSION 4).

### 5. QA
`rwg_preview_shots` plans seven biome shots from a world's own data: the burn's heart at midday
and at dusk, its edge against live forest (looking obliquely across the cells' boundary), a
charred snag at eye level (the nearest instance, from its sunlit side), the fen at dawn in mist and
in rain by its densest pools, and a pool's edge up close; plus a conifer-forest reference. Each
shot logs its frame time, draw calls, primitives and objects (`SHOT perf`).

## Consequences
+ A generated valley has a history: a fire scar a kilometre or two across that stopped at the river
  and the highway, its grey snags over fireweed and bracken; black pools and cattails in the bottoms
  where the Bloom gathers.
+ Waders and per-biome ambience beds are general: any species can stand in water, any biome can have
  its own beds, by data.
− The burn's edge follows the 64 m biome map: the composer's edge wander (up to ~1.5 cells) can carry
  ash a little past a road or river it stopped at (TD-149).
− Regions holding both new biomes lose a default layer (sand, then asphalt or moss) (TD-150).
− Fog does not pool more in fens than elsewhere; the fen's dawn mist is the valley's (TD-151).
− Far views: unbuilt fens and burns tint by the terrain's fallback colours (grey for both new
  layers until `TerrainTextures.FALLBACK_COLORS` learns them) and the far canopy counts snags and
  stunted trees by the 20 m tree-height convention (TD-152).
− Biome shot QA needs a world that holds both biomes (seed and weights chosen per run) (TD-153).
