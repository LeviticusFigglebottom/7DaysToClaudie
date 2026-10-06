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
  forest scatter ✅. 25 authored buildings validated by `make validate` (DESIGN §11):
  * Pell's Crossing (13 buildings, with the church block on Church Lane and the third block on
    Larch Street's corner: the school, the fire station and the Savings & Loan, whose vault opens
    with a combination or a loud cut that wakes the building, ADR-0026).
  * Three on Route 9: gas garage, clinic, motel.
  * The Okafor farm: farmhouse and barn.
  * Four in the wilderness: lookout, trapper's cabin, logging camp, sawmill.
  * Three on the outskirts: Larch Pond Bait & Boat (a boathouse over the pond, ADR-0024), the
    Ashen watch camp, Tamsin River Campground.
  * Varied interiors (ADR-0030): every building is dressed per run from the world seed (wear,
    lights, decals, scatter); the Merrow House, the Mile 9 Diner, the Okafor farmhouse and Lou's
    trailer have room alternatives (five groups each); seven templates generate ordinary houses,
    shops and workshops; lots without a pick choose from the pool or generate; Pell's Crossing's
    Larch Street holds six generated houses south of the third block.

  Still pending: in-game visual QA of the town.
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
- ✅ Weather you can see (ADR-0033): rain streaks and splashes that stop at roofs, eave drips,
  ripples on puddles and lakes, soaked materials by porosity, puddles in hollows and on asphalt that
  outlast the rain, lightning with bolts and hard shadows, thunder delayed by distance, gusts,
  ground fog pooling in the valley at dawn and dusk, rain haze, dust motes indoors, falling snow.
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
- ✅ POI dungeons (ADR-0018):
  * Held sleeper groups that ambush on a trigger, and guardians on the loot.
  * Typed traps a crouched player can disarm: bear trap, shotgun wire, creaky and weak floors,
    alarm, can chime.
  * Lock cues to beat or shoot off.
  * Stable piece ids (save v3).
  * Cellars cut out of the terrain, its collision and the navmesh (TD-026).
- ✅ Surfaces, water and sky (ADR-0019, ADR-0020):
  * Worn interiors composed in world space; trimmed roofs whose tiles don't repeat; painted
    road lines; continuous meadows and planted riverbanks.
  * Lakes and rivers drawn for the first time, mirroring the tree line actually around them.
  * A forest canopy on distant hills.
  * Shaded clouds with a cirrus veil.
- ✅ Buildings with massing (ADR-0021):
  * Tall rooms: St. Ansel's nave and belfry, the Okafor barn's threshing bay under its hayloft
    gallery, the sawmill's saw floor and the grange hall rise two or three storeys, open to their
    rafters, with lancets, tall windows and tall barn doors.
  * A roof planner that follows the plan: cross gables, lean-tos on annexes, flat roofs behind
    parapets, towers, per-part overrides; chimneys that clear them. The Okafor farmhouse gets its
    kitchen ell.
  * Interior light probes per room rectangle; stairs and doors stand off the walls.
- ✅ The Bloom on the land (ADR-0025): an authored, deterministic infestation field (`bloom_at`);
  pale threads climbing the trunks (larches most), a mycelial web over the litter, fruiting
  caps where it is strong, plants wilting, a cold slow glow at night (brighter on Hum nights),
  and fungal mounds where Hum survivors root at dawn (save v4).
- ✅ Light, moon, bridges and the Program's drone (ADR-0023):
  * What still burns follows the buildings' stories: no mains power, candles, lanterns, stoves
    and burn barrels lit per condition variant, flames and globes glowing through emission and
    flickering, coals glowing in barrels and campfires.
  * A moon with phases on a 10-day month, rising later each night: a readable full moon, a
    near-black new moon, stars that fade in moonlight and wheel around the pole.
  * Bridges that follow their road's curve, with abutments, U-wing approaches, evenly spaced
    river piers turned to the current and reflectors on the guardrail posts.
  * Supply drops flown in by a heavy-lift drone in Program livery (doppler rotor loop). They land
    clear of trees and the player's base, and the tether lists every one.
- ✅ The Hollowed up close (ADR-0028):
  * Dead skin with light under it, wet eyes and mouths, and Bloom veins that stay put on a moving
    body; clothes with thickness, seams, hems, tears and retroreflective tape.
  * Fruiting caps and filament mats that erupt as the tier rises.
  * A plated Husk, a Blister of translucent pustules that burst, and a Rammer built big rather than
    scaled.
  * Buildings dress their Hollowed (clinic patients, St. Ansel's congregation, Cordon crews,
    loggers, hunters, the Ashen).
  * Idle and limp variants, so a crowd doesn't move in step.
- ✅ First person (ADR-0029):
  * Hands and tools drawn with their own field of view and squeezed depth: nothing stretches at a
    wide FOV, and a tool never sinks into the wall you stand against.
  * A hold per item class, from data: one-handed tools low and angled, clubs and spears in both
    hands, the torch up in the left hand, food, bottles, placeables, empty fists. Breathing, sway,
    lag, a footstep bob and a lowered sprint on top.
  * Remand sleeves rolled to the elbow over a labourer's forearms in skin, and the tether bolted to
    the left wrist, raised with T to show the live tether UI.
  * Swings with anticipation and follow-through that connect at their contact frame: hit-stop, a
    camera kick, sparks or chips. A guard on Block, staggers, eating and drinking.
  * A stone axe with a knapped flint head and rawhide bindings; a torch whose cap glows like coals.
- ✅ The living forest (ADR-0027), landed early from M2:
  * Generated deer (doe, antlered buck) and snowshoe hare on a quadruped rig built on the character
    pipeline, with IK gaits (walk, trot, gallop, the hare's hop and bound), graze, alert, bedding
    and death; songbirds and crows drawn as instances whose wings flap in the shader.
  * Deterministic wildlife by biome and time of day (data/wildlife), with the Hollowed's senses:
    sight by light and stance, scent downwind, noise. Herds graze, look up, bolt together and bed
    down; the valley falls silent on a Hum night.
  * Flocks flush for you, a Hollowed or a gunshot, and the flush is a sound the Hollowed hear;
    crows circle and call over what put them up.
  * Hunting: carcasses that bleed scent, butchering with a knife or an axe (`wildlife.butcher`),
    venison, hare, hides, sinew; roasting and sinew cordage.
  * Generated calls: snorts, bleats, hooves, the hare's thump and squeal, songbird chatter and
    alarms, crow caws, wingbeats.
- ⬜ Human playthrough on a GPU machine against the acceptance criteria and the 60 FPS budget
  (TD-003); `make bake` impostors from the real tree models (TD-005).

Verified headless on every change: `make check`, `make test`, `make validate`, `make smoke` (the
slice loop end to end: fell → carry → build → craft → night → Hum → save/load).

## M2 — Factions, caves, companion, economy ⬜
- The Ashen: camps, routines, scouts that observe, morale/fear of fire, raids, effigies.
- Corvane cave network (SDF volumes, darkness, key items, mine levels) + region C2/C6 entrances.
- Companion Ezra Vane: follow/gather/guard/fetch orders.
- Full perk trees (rank 4–5 capstones), forge/chemistry bench/grill, more schematics and
  journals (the joinery track has no recipes yet, TD-030). (The Program's supply drone landed
  early, in M1: ADR-0023.)
- ✅ Waystation 9 trader (ADR-0039): a safe-zone post in D6 by Route 9 (D7 later), a quartermaster,
  a scrip shop with restocks and reputation tiers, a contracts board dealing clear/fetch/defend
  contracts by the day, turn-ins for scrip, XP and standing; `program_relay` camps for random
  worlds once the generator places them. Gaps: TD-141..148.
- More POIs (mine office, rail depot, dam control house...) and the Mile 12 framework.
  Church, motel, gas station, bar, clinic, post office, lookout, logging camp, sawmill and the
  Okafor farm landed early, in M1.
- Wolves. Deer, hares, songbirds and crows landed early, in M1 (ADR-0027), as did the Blister,
  Husk and Rammer, and the Hollowed hounds and Murmurs (ADR-0034).

## M3 — RWG, biomes, seasons, base tech ⬜
- Randomized world generation (macro terrain + erosion, biomes, rivers/lakes, roads, towns from
  frameworks, wilderness POIs, caves, trader placement), background thread + progress UI + cache.
  Frameworks already fill lots without a pick from zoning (LotPicker, generated buildings,
  ADR-0030); RWG is ADR-0031.
  - [x] v1 (ADR-0031): world settings + presets + map seed on the New Game World tab with a map
    preview; land with drainage-carved valleys, lakes, rivers, biome map; towns as generated
    frameworks; roads with bridges; authored places by site; drop site; Bloom patches; cached in
    user://worlds/random; save v6; `rwg_preview.gd` map CLI and in-world shots; the slice smoke
    passes on a 3 x 3 random world.
  - [x] v2, organic towns (ADR-0040, `RwgGenerator.VERSION` 2): towns sited by size class from a
    `town_density` setting, arterials routed through their centres, streets grown over the land with
    lots by frontage and zoning by rings, lot pads graded to each frame, buildings stood on their
    frames, an authored building in at most 3 towns per world; v1 worlds still load. Gaps:
    TD-136..140.
  - [ ] Caves, traders, the Ashen's territory, coasts and new biomes; streaming regions for 6-7 km
    worlds (TD-081..084; RWG v2 Phases 2–4, ADR-0038).
  - [x] Pool buildings for random towns (DESIGN §11): Suds & Spin Laundromat, Hollowmere Grocery,
    Bracken Lumber & Feed, Pell County Library and KHLW Valley Radio, five authored dungeons with
    room alternatives that town lots pick by zoning, tier and footprint; 36 new props
    (`props_town3.py`) and the `town3_print` sign atlas. Gaps: TD-086..089.
  - [x] Pool round 2 (DESIGN §11): Hollis Pawn & Gun, Northfork Packing Co., Water Works,
    Ridgeline Aggregate and the Veterans' Post, five more pool dungeons (three of them industrial)
    with their own keys, notes and loot (`town4` content) and 24 new props (`props_town4.py`);
    `tests/unit/test_pool_round_two.gd`. Gaps: TD-112..114.
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
