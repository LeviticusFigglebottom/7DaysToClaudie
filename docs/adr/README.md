# Architecture Decision Records

One file per decision: context → decision → consequences. Supersede rather than edit history
(add a new ADR and mark the old one "Superseded by ADR-XXXX").

| ADR | Title | Status |
|---|---|---|
| [0001](0001-engine-and-toolchain.md) | Godot 4.7.2 Forward+, Jolt, pinned toolchain | Accepted |
| [0002](0002-procedural-asset-pipeline.md) | Procedural, reproducible asset pipeline; generated binaries not committed | Accepted |
| [0003](0003-multiplayer-ready-state.md) | Authoritative state vs presentation, command bus, deterministic ids | Accepted |
| [0004](0004-language-gdscript.md) | Statically typed GDScript; criteria for native code | Accepted |
| [0005](0005-save-format.md) | Versioned, migratable, chunk-based saves | Accepted |
| [0006](0006-structural-integrity.md) | Stability-propagation structural model | Accepted |
| [0007](0007-terrain-hybrid.md) | Heightmap chunks + smooth SDF volumes for digging/caves | Accepted |
| [0008](0008-json-content.md) | JSON content with typed, validated definitions | Accepted |
| [0009](0009-poi-spec-dsl.md) | POI spec DSL compiled to scenes; grid-graph route validation | Accepted |
| [0010](0010-test-framework.md) | GUT 9.7.1 vendored via jsDelivr | Accepted |
| [0011](0011-horde-flow-field.md) | Hum pathing: weak-point flow field over structure costs | Accepted |
| [0012](0012-stimulus-fields.md) | Shared perception through stimulus fields | Accepted |
| [0013](0013-world-coordinates-regions.md) | World coordinates, regions and streaming | Accepted |
| [0014](0014-game-rules-and-gamestage.md) | World settings (game rules), gamestage and difficulty scaling | Accepted |
| [0015](0015-progression-rewards.md) | Progression that pays off: derived stats, XP sources, supply drops | Accepted |
| [0016](0016-runs-fires-water-refinement.md) | One save per run; fires, water and repairs with a cost | Accepted |
| [0017](0017-forest-fidelity.md) | Forest-level fidelity: per-plant ground fade, patchy scatter, bigger budgets, triplanar rock | Accepted |
| [0018](0018-poi-dungeon-mechanics.md) | POI dungeon mechanics: ambush triggers, traps, lock cues, guardians, stable piece ids | Accepted |
| [0019](0019-building-surfaces.md) | Built and open-ground surfaces: wear, roofs, roads, meadows, riverbanks | Accepted |
| [0020](0020-water-and-distant-forest.md) | Water and the distant forest: visible water, tree-line reflections, far canopy | Accepted |
| [0021](0021-tall-rooms-roof-planner.md) | Tall rooms, galleries, a roof planner and per-room probes | Accepted |
| [0022](0022-dungeon-life.md) | Dungeon life: sleepers on seats and beds, the Hollowed on traps, route cues, readable plans (amends 0018) | Accepted |
| [0023](0023-light-moon-bridges-drone.md) | Lights that make sense, a real moon, bridges that follow the road, the Program's drone | Accepted |
| [0024](0024-pads-that-keep-their-water.md) | Pads that keep their water: placements over a lake or river grade only dry ground, a freeboard over the water | Accepted |
| [0025](0025-the-bloom-on-the-land.md) | The Bloom on the land: an authored infestation field, threads, web, fruit and mounds | Accepted |
| [0026](0026-the-vault.md) | The vault: a lock opened with a combination or cut through loudly, rousing the building | Accepted |
| [0027](0027-the-living-forest.md) | The living forest: generated quadrupeds and instanced birds, deterministic wildlife, flushes the Hollowed hear, hunting | Accepted |
| [0028](0028-the-hollowed-up-close.md) | The Hollowed up close: skin and cloth shaders on rest-pose vertex data, garments, tier growths, special features, populations | Accepted |
| [0029](0029-first-person.md) | First person: hold classes, a viewmodel field of view, arms that carry the tether, swings that land | Accepted |
| [0030](0030-varied-interiors.md) | Varied interiors: per-run dressing, room alternatives, generated ordinary buildings, lots that pick | Accepted |
| [0031](0031-random-worlds.md) | Random worlds: a seeded generator that writes the handcrafted map's own format | Accepted |
| [0033](0033-weather-and-atmosphere.md) | Weather you can see: rain that stops at roofs, wet ground and puddles, lightning and thunder, ground fog that pools, falling snow | Accepted |
| [0034](0034-hounds-and-murmurs.md) | Hollowed hounds and Murmurs: pack hunters on the Enemy brain, crows that mark you | Accepted |
| [0035](0035-base-building-fidelity.md) | Base-building fidelity: a woodsman's camp, racks that fill, doors, stairs, furnished floors | Accepted |
| [0036](0036-playable-builds.md) | Playable builds: packaged exports with the generated assets, a stand-in mode we test, a load that keeps the window alive | Accepted |
| [0037](0037-graphics-options-and-perf.md) | Graphics and controls options for real GPUs, and what the first perf pass found | Accepted |
| [0038](0038-streamed-worlds.md) | Streamed worlds: Phase 1, a composer 2-2.5x faster with byte-identical output, row bands, cancellation, a crash-safe region cache with an LRU, generator spatial indexes | Accepted (Phase 1) |
| [0039](0039-waystation-trading.md) | Waystation trading: trader posts (safe zones, a quartermaster), a scrip shop with reputation tiers, clear/fetch/defend contracts dealt by the day | Accepted |
| [0040](0040-organic-towns.md) | Organic towns: streets grown over the land, lots by frontage, zoning by rings | Accepted |
| [0041](0041-burnt-forest-and-fen.md) | Burnt forest and fen: fire scars and drowned lowland in random worlds, fire char on the bark, waders, per-biome ambience | Accepted |
| [0044](0044-corvane-caves.md) | The Corvane caves: buried POI levels (a mine and a limestone cave under the Larkspur cliffs), underground is night for the Hollowed, rock finishes and a mine kit | Accepted |
| [0046](0046-tier-five-field-lab.md) | Tier 5: the Corvane Field Lab, keycards as keys, and a compound the validator can walk | Accepted |
| [0047](0047-town-ground-and-biome-fog.md) | Town ground on the streets, a town mask for ambience and spawns, yard grass off the buildings, fog that follows the biome | Accepted |
| [0049](0049-farming-and-rain-collection.md) | Farming and rain collection: garden beds that need water, crops as data, rain catchers | Accepted |
| [0052](0052-base-traps-and-electricity.md) | Base traps and electricity: spike pits, deadfalls, a tripwire bell, generators on gas, wires, lights, a motion floodlight and a nail sentry | Accepted |
