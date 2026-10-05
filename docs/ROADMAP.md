# Roadmap

Status legend: ✅ done · 🟡 in progress · ⬜ planned. Each milestone lists its acceptance criteria.
Keep this file current at the end of every session.

## M0 — Tooling, pipeline skeleton, CI ✅
- ✅ Pinned toolchain (`tools/versions.env`): Godot 4.7.2 (Forward+, Jolt), Blender 5.2.2 LTS, Python venv.
- ✅ `make setup / assets / import / validate / test / run / preview / screenshots / ci`.
- ✅ Asset orchestrator: incremental by input hash, parallel, batched Blender, deterministic UIDs,
  `.import` sidecars, determinism check.
- ✅ Data-driven ContentDB with validation; GUT tests; GitHub Actions CI.
- ✅ Core models: inventory, crafting, loot, survival, structure graph, clock/Hum schedule,
  progression, heat map, horde memory, save system (versioned, migrations, chunk blobs).

## M1 — Vertical slice 🟡
**Acceptance**: from a clean clone (`make setup assets`) the slice is playable start to finish —
wake at the drop site, gather, craft a stone axe, build a lean-to shelter, explore Pell's Crossing
and clear at least one authored building along its route, survive a night and a Hum night
(slice mode: Hum on night 3), then save and reload. All visuals use generated assets.

- 🟡 Region D6 *Larch Hollow*: terrain (heightmap chunks + LOD + digging), river, pond, cliffs,
  forest scatter ✅; Pell's Crossing framework with 5 authored buildings (Mile 9 Diner, Pell
  Pharmacy, Calder Hardware, Ranger Station, Merrow House) validated by `make validate` — in-game
  visual QA of the town pending.
- ✅ Player controller, interaction, gathering, stamina, damage, death/respawn; step-up onto
  thresholds and vault/mantle through windows and over fences (tests/integration/test_traversal).
- ✅ Survival stats in play (needs, temperature, bleeding, infection hook) + tether vitals.
- ✅ Diegetic salvage roll inventory + hand crafting; campfire/workbench station crafting.
- ✅ Tree chopping (physics fall, stumps, logs), log carrying, log building (snap + freeform),
  blueprints, structural integrity + collapse, structure damage + fracture debris.
- ✅ Terrain digging (heightmap) + smooth SDF volume chunks (tunnel prototype, unit-tested).
- 🟡 Hollow, Lurcher, Keener (+ Dragger via dismemberment): sleepers, wanderers, day/night speeds,
  perception through stimulus fields, heat summons ✅; generated bodies/animations merged, visual QA
  of the rigs in game pending.
- ✅ Day/night, weather (clear/overcast/mist/rain/storm), seasons hook.
- ✅ One Hum night with sector waves, weak-point flow field, horde memory report + forecast.
- ✅ World settings (game rules) with five difficulty presets and a New Game screen; gamestage
  scaling; special Hollowed (Blister, Husk, Rammer) and infected tiers (Seeded, Bloomed)
  (ADR-0014).
- ✅ Progression that pays off: every perk effect wired, Record tab for spending points, XP from
  looting/building/clearing/the Hum, level-up feedback, Remand supply drops, quality tiers,
  Sleeper Sense, Program Directives in four chapters (ADR-0015).
- ✅ Save/load: one slot per run, saved on sleep, at dawn after a Hum and with F5 (F9 reloads),
  `.old` recovery, portable chunk files (ADR-0016).
- ✅ Second refinement pass (ADR-0016), from six audits:
  * Hollowed use the navmesh, spawn validly, finish breaking in, and root after the Hum.
  * Doors collide; stream water; fires burn fuel; an honest hammer with dismantling; swimming.
  * Lights burn down; hitboxes follow bones; damage direction and heartbeat.
  * An options screen and Esc that closes the pause menu.
  * Weather variety with lasting snow; dry interiors; rebalanced infection, bleeding, XP and loot.
- ✅ Forest-level asset fidelity pass (ADR-0017):
  * A lush, patchy forest floor: moss mounds, twig-and-cone litter, a third fern, denser
    understory, multi-tuft meadow grass. Ground cover fades plant by plant instead of popping
    in whole chunks.
  * Deeper fir and larch bark; real moss fronds; broken stubs and stronger buttresses on trees.
  * Chipped, triplanar-mapped boulders that cast shadows.
  * 16k Hollowed with smooth faces; first-person hands that grip the tool.
  * The Route 9 bridge over the Tamsin River.
- ✅ Debug tools: free cam, spawn menu, time/weather, AI overlay, POI route visualizer, perf overlay,
  seed viewer, structural view (docs/DEBUG_TOOLS.md).
- ✅ Audio: 3D occlusion, reverb zones (listener-based, TD-013), ambient beds, creature cues.
- ✅ Generated asset families: vegetation, rocks, terrain/decal/FX/sky/UI textures, POI kit,
  interior + exterior props, items/viewmodels/structures, characters + first-person arms.
- ⬜ Human playthrough on a GPU machine against the acceptance criteria and the 60 FPS budget
  (TD-003); `make bake` impostors from the real tree models (TD-005).

Verified headless on every change: `make check`, `make test`, `make validate`, `make smoke` (the
slice loop end to end: fell → carry → build → craft → night → Hum → save/load).

## M2 — Factions, caves, companion, economy ⬜
- Okafor farmhouse (placed in D6, not authored): two storeys + cellar; needs cellar holes in the
  terrain collision (TD-026).
- The Ashen: camps, routines, scouts that observe, morale/fear of fire, raids, effigies.
- Corvane cave network (SDF volumes, darkness, key items, mine levels) + region C2/C6 entrances.
- Companion Ezra Vane: follow/gather/guard/fetch orders.
- Full perk trees (rank 4–5 capstones), forge/chemistry bench/grill, more schematics and
  journals (the joinery track has no recipes yet, TD-030); a visible Program drone for supply drops.
- Waystation 9 trader, contracts (clear/fetch/defend), reputation tiers, scrip economy.
- 10+ more POIs (church, school, motel, gas station, bar, clinic, mine office...), Mile 12 framework.
- Wildlife; Hollowed hounds (Blister, Husk and Rammer landed early, in M1).

## M3 — RWG, biomes, seasons, base tech ⬜
- Randomized world generation (macro terrain + erosion, biomes, rivers/lakes, roads, towns from
  frameworks, wilderness POIs, caves, trader placement), background thread + progress UI + cache.
- Burnt forest, snow, swamp, scrub biomes; full seasons (snow cover, frozen water, temperature).
- Structural tiers: stone, metal; repair/upgrade tools; Rammer breakers that tear through walls.
- Farming, rain collection, traps (spike pits, deadfalls), electricity (generator, wiring, lights,
  motion turrets).
- Main-map regions: Mile 12, Tamsin Gorge, Harrow (partial).

## M4+ — Novel systems in full, vehicles, co-op, the rest of the valley ⬜
- The Bloom infection mutations/madness; two-faction ecology & territory map; the Hollowing.
- Traversal: ziplines, rope descents, wing-sail glider; salvaged ATV.
- Co-op (host-authoritative, command replication — see ADR-0003).
- Remaining main-map regions, story arc to the Root, polish, accessibility, localization.
