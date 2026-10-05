# HOLLOWMERE — Game Design Document

> *The valley breathes on the seventh night.*

Working title **Hollowmere**. First-person, co-op-ready survival horror. Original IP: all names,
lore, creatures, places and art are our own. Inspirations are acknowledged only at the level of
genre pillars (forest-survival horror + systemic base-defence survival); no names, assets, layouts
or story beats are borrowed.

---

## 1. Premise

Hollowmere is a remote logging-and-mining valley in the fictional **Sawback Range**: timber company
towns, a deep hard-rock mine, a hydro dam, fire lookouts, a narrow-gauge railway and a long cold
lake. Eighteen months ago a bore at the **Corvane Deep Mine** broke into a limestone cave system
older than the mountains. What came up was **the Bloom** — a pale, filamentous fungus that colonises
nervous tissue. Its hosts, **the Hollowed**, lose themselves but keep walking. The Bloom is
photosensitive: by day the Hollowed are sluggish and half-blind; at night they hunt.

And every seventh night the colony beneath the valley **exhales** — a low seismic hum felt through
the ground. On those nights, **the Hum**, every Hollowed within miles converges on the strongest
heat, light and noise it can sense.

The government sealed the valley behind **the Cordon**: fencing, drones, a burned firebreak. Inside,
a few hundred survivors fled to the high timber and became **the Ashen** — tribes who smear
themselves with lichen-ash (it masks their scent from the Hollowed), burn their dead, raise
effigies of bone and antler, and kill outsiders who might carry the Bloom.

You are **Remand Salvager #4471**, a convict enrolled in the **Remand Salvage Program**: inmates
"volunteer" to be dropped inside the Cordon to recover Bloom core samples and research data from
the mine and the old field lab. Every delivery shortens your sentence. Your **tether** — a locked
wrist unit with GPS, vitals and a cordon radio — counts down to the next Hum. Supply **lifts**
parachute in at drop sites; the Program's quartermaster trades and issues contracts from
**Waystation 9**, a relay post built into the Cordon wall where the river leaves the valley.

**Tone**: grounded, melancholy dread. A beautiful autumn wilderness with wrongness underneath —
pale threads on the larches near infested ground, ash effigies at the treeline, a hum in the soil.

## 2. Pillars

1. **The wilderness is beautiful and it is watching.** Dense, believable forest; light, sound and
   scent matter; night is genuinely dark.
2. **Everything is physical.** Logs are carried on the shoulder, structures stand because they are
   supported, inventory is a canvas roll on the ground, the map is on your wrist.
3. **Every building is a dungeon.** Hand-authored POIs with intended routes, sleepers, traps,
   shortcuts and a payoff room; environmental storytelling in every room.
4. **The seventh night is the exam.** A weekly escalating horde that targets your weakest wall and
   *remembers* what killed it last time.
5. **Systems talk to each other.** Noise brings attention, scent drifts with the wind, fire is both
   tool and beacon, factions fight each other.
6. **Built to grow.** Data-driven content, region-based world, co-op-ready state.

## 3. Core loops

**Minute to minute** — move through the forest with limited sightlines; read the soundscape;
gather sticks, stones, fibre and logs; manage stamina in fights; sneak through POIs (crouch, light
discipline), loot containers, fight with crude melee and scarce, loud firearms.

**Day to day** — Morning: scavenge a POI or a region; take a Waystation contract (M2). Afternoon:
gather logs, expand and upgrade the base, craft. Dusk: get home, light fires (warmth vs. beacon),
cook, boil water, repair. Night: the Hollowed run; hunker down or risk night looting for better
rewards. Sleep in a shelter to save, restore rest and pass time (not during the Hum).

**Hum to Hum (7 days)** — the tether counts down; days 1–6 are preparation (walls, stakes,
traps, firing positions, supplies). The Hum: waves from multiple sectors, smart breach targeting.
Dawn: survivors root into the soil — harvest Bloom mycelium and core samples from the mounds,
repair, learn what the horde learned (the tether's *Hum forecast*), plan the next week.

## 4. Feature map (pillar → original form → milestone)

| Inspiration pillar | Hollowmere form | Milestone |
|---|---|---|
| Dense believable wilderness | Larch/fir/birch forests, rivers, lakes, cliffs, coast, snowy summit; wind-animated foliage, volumetric fog, god rays, SDFGI | M1 (one region), M3+ |
| Freeform physical building | Fell trees → logs carried on the shoulder → log pieces placed freely or snapped; guidebook blueprints (ghosts) | M1 |
| Structural physics & destruction | Stability graph per structure, HP/material, Voronoi-fractured debris, cascade collapse | M1 |
| Gathering from environment | Trees fall physically and leave stumps; sticks, stones, fibre, boughs, berries, mushrooms, bones | M1 |
| Diegetic UI | Salvage roll inventory on the ground, crafting on the work slate, Remand Field Manual (guidebook), wrist tether (GPS/vitals/countdown), minimal HUD | M1 |
| Intelligent humanoid enemies | The Ashen: tribes with camps, routines, scouting, fear of fire, morale, escalation | M2 |
| Cave networks | The Corvane caves (lightless, key items, the mine and the Root) | M2 |
| AI companion | Ezra Vane, an earlier Remand convict (ex-lineman) — follow, gather, guard, fetch | M2 |
| Survival stats & seasons | Health, stamina, fullness, hydration, rest, body temperature, wetness, bleeding, Bloom infection; four seasons, snow, freezing water | M1 stats / M3 seasons |
| Stealth, light, noise, fire | Shared stimulus fields (sight/sound/scent) drive all AI; fire warms and attracts | M1 |
| Traversal & vehicles | Ziplines, rope descents, a glider-like "wing-sail", a salvaged ATV | M4 |
| Gore & dismemberment | Limb HP, severable segments, stumps, gibs; Draggers emerge from leg loss | M1 |
| Hand-designed POIs | POI spec DSL → scenes with route, sleepers, traps, loot room, shortcut; validator | M1 (6 buildings) |
| Tiered loot | Container types, quality Q1–Q6, POI tier + gamestage scaling | M1 |
| Crafting stations | Hands, campfire, workbench (M1); forge, chemistry bench, grill (M2) | M1/M2 |
| Character progression | Attributes (Sinew, Grit, Keen, Quiet, Wits), perks, schematics, field journals | M1 core / M2 full |
| Base upgrading | Log → reinforced log → stone → metal tiers, repair, collapse | M1 log tiers / M3 |
| Escalating horde nights | The Hum every 7th night (configurable), sector waves, breach targeting, adaptive memory | M1 |
| Zombie variety | Hollow (walker), Lurcher (feral), Keener (screamer), Dragger (crawler) in M1; Blister (spitter), Husk (armoured), Rammer (breaker), hounds, Murmur crows later | M1/M2/M3 |
| Heat / attention | Heat grid: noisy activity summons scouts, Keeners, packs | M1 |
| Traders & quests | Waystation 9 quartermaster, contracts (clear/fetch/defend), reputation tiers | M2 |
| Mining & digging | Heightmap digging + smooth SDF volumes for tunnels/caves/mines | M1 (dig), M2 (tunnels) |
| Farming, water, traps, electricity | Rain catchers, gardens, deadfalls, generator + wiring + lights + motion turrets | M3 |
| Randomized worlds | Seeded RWG using the same terrain composer, biomes, frameworks and POIs | M3 |

## 5. Novel systems

We propose five; **two ship in the M1 core loop**, the rest have hooks now.

1. **Stimulus Fields** *(M1 core)* — all AI perceives the world through one shared layer:
   **sound** events propagate with distance falloff, wall/terrain occlusion and rain masking;
   **scent** is a coarse grid advected by the wind (blood boosts it, water and ash mask it, it
   decays); **light** exposure decides how visible you are (a lit torch is seen from 80 m, a
   crouched figure in shadow at 6 m). The heat/attention system is the long-term integral of the
   same fields. Hooks: wind direction in weather, `noise_mask` per weather, `Stimuli` API.
2. **Horde Memory** *(M1 core)* — after every Hum the director files a report per compass sector
   (sent, killed, breaches, causes). The next Hum flanks killing fields, masses a siege group at
   the wall that held, escalates Keeners/Lurchers if you cleared fast, and the tether's **Hum
   forecast** tells you what they learned in-fiction ("They step around the stakes now").
   Implemented in `HordeMemory` (tested), consumed by the Hum director.
3. **The Bloom (infection as progression)** *(hook M1, full M4)* — bites raise infection; above
   thresholds the player gains night vision, scent-tracking and strength mutations, but suffers
   madness effects (phantom Hollowed, unreliable tether readouts, whispering audio) and, at 100,
   turns. Antifungals push it back. Hook: `SurvivalStats.infection`, `hm_bloom` shader global.
4. **Two-faction ecology** *(M2/M4)* — Ashen and Hollowed are hostile to each other. Lure a
   Keener into an Ashen camp; Ashen raid Hollowed nests and burn them; a territory influence map
   shifts over weeks. Hook: `EnemyDef.faction`, faction relation matrix (M2).
5. **The Hollowing** *(M4)* — a pale spore-fog front that crawls across regions for a day or two:
   visibility collapses, the Hollowed are bold even by day, the Ashen retreat, the tether glitches.
   It rewrites what is dangerous where. Hook: weather states + region danger modifiers.

## 6. Factions & creatures

**The Hollowed** (faction `hollowed`) — *Hollow* (walker; slow by day, fast at night), *Lurcher*
(feral sprinter), *Keener* (keening wail summons everything within ~120 m and heats the area),
*Dragger* (legless crawler — also produced by severing a Hollow's legs), later *Blister*
(spits spore blisters), *Husk* (fused with debris/riot gear, armoured), *Rammer* (huge, tears
through walls), *Hollowed hounds*, *Murmurs* (crow flocks that mark you).
**Sleepers**: dormant Hollowed in POIs (lying, sitting, standing head-down) wake on noise, light
or line of sight. **Dawn rooting**: Hum survivors collapse into the soil as fungal mounds.

**The Ashen** (faction `ashen`, M2) — lichen-ash painted tribes with camps, patrol routes,
scouts that observe before attacking, morale and fear of fire, effigies marking territory,
escalating responses to the player (watchers → raids → war parties).

**Wildlife** (M2) — deer, hare, wolves; birds that flush and give away positions.

## 7. Progression

* **Attributes**: Sinew (strength, carrying, chopping), Grit (health, stamina, resistances),
  Keen (perception, loot quality, aim), Quiet (stealth, speed), Wits (crafting, building, medicine).
* **Perks**: ranked, gated by attribute level (`data/progression/perks`), effects are named
  modifiers consumed by systems (`Progression.modifier("chop_damage_mult")`). Every effect key
  in the data is read somewhere: pack space, the third shoulder log, max health, stamina
  recovery, loot quality, structure toughness, blunt stagger, Sleeper Sense (dormant Hollowed
  outlined through walls), noise, speed, resistances, healing (ADR-0015).
* **Spending**: the Field Manual's **Record** tab: level, XP, gamestage and run stats; train
  attributes and learn perk ranks (each locked choice says why: "needs Sinew 3").
* **XP** comes from everything you live through (`progression.json` `xp`): kills (Seeded ×1.8,
  Bloomed ×3), searching containers (× tier), first entry into a building (× tier), clearing it
  (× tier), logs set, upgrades, finished blueprints, crafting, felling, digging, reading notes,
  and above all surviving the Hum (more for every Hum survived). Level-ups chime and say how many
  points wait.
* **Learn by reading**: schematics teach a recipe/blueprint; trade journals advance skill tracks
  that unlock recipes at thresholds (`unlock: "skill:field_medicine:2"`).
* **Gamestage** = (level + days survived × weight) × bonus (world settings), which scales loot
  quality, infected tiers, special Hollowed, Hum size and supply-drop tier.
* **Remand supply drops** (the airdrop): after each Hum (default), weekly, every 3 days or
  never; a canister under a chute lands 110–300 m away with a red flare and smoke column, holds
  tiered supplies (ammo, tools, antifungal, schematics as the gamestage rises) and is marked on
  the tether. The landing is loud: the Hollowed come to look too.
* **Quality tiers** Q1–Q6: Scrap, Worn, Serviceable, Good, Fine, Pristine (colours in the salvage
  roll). Quality scales weapon damage and durability. Keen and Scavenger raise what you find.

## 8. Items, crafting, building

* Items are data (`data/items`): stack/carry caps, bulk (encumbrance), quality, durability,
  equip/consume blocks, teaches. Logs are carried on the shoulder (max 2, Timberwright → 3).
* **Hand crafting** on the salvage roll's work slate (exact ingredient match), **station** crafting
  at campfire/workbench (M1) and forge/chemistry bench/grill (M2).
* **Building**: log pieces snap (stack, side-by-side, corner, pillar) or go freeform; blueprints
  from the Field Manual place ghosts you fill log by log (`pieces`) or with materials
  (`assembly`). Stability propagates from grounded pieces; spans fail; damage fractures pieces.
  Upgrade tiers: log → reinforced → stone → metal (M3 adds stone/metal).
* **Base defence** (M1): stake barricades (contact damage), log walls, can chimes (noise alarm);
  M3: spike pits, deadfalls, electrified wire, motion lights and turrets.

## 9. Diegetic UI

* **Salvage roll** (inventory): kneel, the canvas tool roll unfurls on the ground; items lie in
  stitched pockets by category; selected items go to the work slate; a matching recipe shows a
  chalk outline of the result — combine.
* **Remand Field Manual** (guidebook): survival tips, blueprints (place ghosts), recipes, notes you
  found, someone else's handwriting in the margins (lore).
* **Tether** (wrist): raise your wrist for the GPS map (built from the real terrain), compass,
  time, vitals (heart rate, body temp), level/XP/gamestage, supply-drop bearing and marker,
  objectives and the **Hum countdown/forecast**.
* **HUD**: minimal — interaction prompt, subtle stamina breath, damage vignette, cold frost,
  status pips only when critical, transient toolbelt strip when switching.

## 10. World

### 10.1 Main map ("the canonical world")
7 × 7 regions of 1024 m = **7.2 km per side**, origin at the centre of region D4. Each region has
its own data folder and builds independently (`docs/REGIONS.md`). World-scale macro terrain
(mountain ranges, the lake, the river, the coast) comes from `game/world/main_map/world.json`;
regions add local detail. Danger rises north and east; the Whitecap summit relay is visible from
almost everywhere for navigation.

![Main map sketch](images/main_map_sketch.png)

| | A | B | C | D | E | F | G |
|---|---|---|---|---|---|---|---|
| **1** | Greywater Headland (coast cliffs) | Kestrel Peaks (snow) | Corvane Ridge (snow, vent shafts) | **Whitecap Summit** (relay, landmark) | Glacier Basin (snow, tarns) | Hightimber (snow forest) | Northern Pass *(frontier: sealed rail tunnel)* |
| **2** | Saltreach (fishing village) | Old Growth (giant forest) | **Corvane Deep Mine** (industrial, cave entrance) | Harrow Heights (residential) | Selk Dam (hydro) | **Ashen Highcamp** (tribe village) | Burnwood East *(frontier: blocked highway)* |
| **3** | Greywater Shore | Fernmere (wet forest) | Mere West Shore (cabins) | **Harrow** (main town) | Harrow Mill & Railyard (industrial) | Burnwood (burnt forest) | Ember Ridge (Ashen watch) |
| **4** | Sound Narrows (wrecked ferry) | Westwood | Hollowmere West (lake) | **Hollowmere Lake / Lantern Island lab** | Hollowmere East | Ashen Lowcamp | Burnwood South *(frontier: collapsed bridge)* |
| **5** | Greywater Point (lighthouse) | Cedar Hollow | Kettle Hills | Tamsin Gorge | Bramble Flats (meadows) | Sallow Fen North (swamp) | Sallow Fen East *(frontier: flooded lowlands)* |
| **6** | Driftwood Beach | Lowland Timber (cut-blocks) | Larkspur Ridge (sealed cave) | **Larch Hollow** — M1 start, Pell's Crossing | Mile 12 (gas station, motel) | Sallow Fen | Fen Edge *(frontier)* |
| **7** | Cordon West *(frontier)* | Cordon Firebreak | Cordon Gate West | **Waystation 9** (trader) | Cordon Firebreak East | Cordon Marsh | Cordon East *(frontier)* |

**Progression arc**: Larch Hollow (D6, safe-ish start) → Waystation 9 (D7, trader/contracts) →
Mile 12 (E6) → Harrow (D3, big town) → Corvane Deep Mine & caves (C2) → Lantern Island field lab
(D4) → the Ashen (F2: alliance or war) → Whitecap Summit relay (D1) → **the Root**, the Bloom's
heart under the mountain. Every region lists an elevation class, biomes, POI frameworks and its
frontiers in `world.json`.

**Expansion frontiers** — places where future prompts add whole regions without touching existing
ones: the map edges (the sound to the west, the Cordon wall south), the sealed rail tunnel (G1),
the blocked eastern highway (G2), the collapsed bridge (G4), the flooded lowlands (G5/G6), sealed
cave passages (C6, C1) and the mine's lower levels (C2, underground layer).

### 10.2 Randomized worlds (M3)
Seeded generator producing the same structure: macro terrain (ridges, basins, coast) + hydraulic
erosion, biome map (forest, burnt forest, snow, scrub, swamp), rivers and lakes, road network,
towns from the same **frameworks** and **POIs**, wilderness POIs, cave systems, trader placement.
Deterministic per seed + version, generated on a background thread with progress, cached to disk.
The M1 terrain composer already takes features + seed, which is the same interface RWG feeds.

## 11. POIs and buildings

POIs are authored with the **POI spec DSL** (ASCII floor plans + route/sleeper/loot/trap lists,
`docs/POI_AUTHORING.md`) and compiled to scenes with metadata. Frameworks place them on lots.

**M1 roster — Pell's Crossing (town framework `pell_crossing`)**:

| POI | Tier | Concept | Route sketch |
|---|---|---|---|
| The Merrow House | 1 | Small family home; the family barricaded the front door against their own father | Front door barricaded → around back through the kitchen → hallway sleepers → kids' room loot → back door shortcut |
| Mile 9 Diner | 1 | Roadside diner, last-stand barricade around the counter | Broken front window → booths (sleepers sit) → kitchen through swinging doors → walk-in pantry loot → back exit |
| Pell Pharmacy | 2 | Looted pharmacy with a locked dispensary | Front shutter down → loading bay → stockroom ambush → find dispensary key in the office → dispensary payoff → side door |
| Calder Hardware & Feed | 2 | Hardware store; owner hid tools in the loft | Store floor (shelving maze, can-chime trap) → back room → ladder up through a hatch to the loft (nails, hatchet) → drop back down outside |
| The Okafor Farmhouse | 3 | Two-storey farmhouse with root cellar | Porch → parlour (collapsed ceiling) → upstairs via stairs → bedroom hole drop into the cellar (sealed hatch) → cellar stash → hatch shortcut up to the kitchen |
| Pell Ranger Station | 3 | Sheriff/ranger substation; last log of Deputy Hale | Fenced lot → side office (keys) → holding cells (sleepers) → evidence locker (revolver, cold box with a Bloom sample) → back door |

**Planned (M2+)**: church, school, motel, gas station, bar, clinic, post office, fire lookout,
logging camp, mine office, sawmill, rail depot, dam control house, lighthouse, fishing co-op,
lab outpost, survivor compounds, Ashen camps, crashed Program supply drone, quarantine camp.

## 12. Audio & visual direction

* **Visual**: grounded PBR, dense layered vegetation (canopy, understory, ferns, grass, debris),
  wind animation, volumetric fog, god rays, SDFGI (High/Ultra) with SSAO/SSIL fallbacks, AgX
  tonemapping, dramatic day/night and weather. Night is dark — the moon helps only in clearings.
* **Audio**: 3D positional sound with raycast occlusion (muffled through walls), reverb zones
  (interiors, caves), ambient beds per biome/time/weather, readable creature cues, a generative
  dread score, and the Hum's sub-bass drone.

## 13. Technical targets

60 FPS at 1080p on a mid-range GPU (High preset). Budgets (tracked by the perf overlay):
draw calls < 3000, visible triangles < 4M, terrain chunk 64 m (LOD0 65×65), trees LOD0 ≤ 9k tris,
active full-tick AI ≤ 48 (≤ 64 during the Hum, distant AI ticks at 5 Hz), physics debris ≤ 120
bodies (auto-cleanup 20 s), shadowed lights ≤ 12 visible. Presets Low/Medium/High/Ultra.
