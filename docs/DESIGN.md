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
| Traders & quests | Waystation 9 quartermaster, contracts (clear/fetch/defend), reputation tiers (ADR-0039) | M2 ✅ |
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
   turns. Antifungals push it back. A bite or two below the dormant line (12) is fought off in
   hours; past it the Bloom grows until treated (`survival.json` `infection`). Hook:
   `SurvivalStats.infection`, `hm_bloom` shader global.
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

**Hollowed hounds** (ADR-0034): dogs the Bloom took, in packs of three to five, more at night and
when your noise draws them. The first to see you howls and the pack comes. They spread round
you, bite and break off, and work your scent trail when they lose you. A torch held up keeps the
ones in front of you off; the one behind still goes for your legs. Climb, shut a door, or hold
the flame and turn.
**Sleepers**: dormant Hollowed in POIs (lying, sitting, standing head-down) wake on noise, light
or line of sight. **Dawn rooting**: Hum survivors collapse into the soil as fungal mounds.

**The Ashen** (faction `ashen`, M2) — lichen-ash painted tribes with camps, patrol routes,
scouts that observe before attacking, morale and fear of fire, effigies marking territory,
escalating responses to the player (watchers → raids → war parties).

**Wildlife** (ADR-0027, landed early in M1) — the forest moves:
* **White-tailed deer** in bands of two to five (a buck among the does) at the forest's edge and
  in the meadows at dawn and dusk; they graze, look up and stamp, bolt together, and bed down at
  night. They see a standing man at 80 m and won't let one inside 32; downwind they smell you at
  90; a gunshot or a Hollowed sends them off.
* **Snowshoe hares** in the brush, sitting tight until you're almost on them.
* **Songbirds** in the canopy and on the ground, **crows** in the clearings and over Pell's
  Crossing. They **flush** when you or a Hollowed come close, or at a loud noise: wingbeats, an
  alarm call, and a sound the Hollowed hear and come to look at. Birds give your position away.
  Crows circle what put them up, cawing, every caw another mark over your head.
* **Murmurs** (ADR-0034): a crow flock you flush may not settle. It follows you low overhead,
  and every caw is a mark *on you* that the Hollowed come to; more often where the Bloom lies
  thick. Get under a roof or the canopy until they lose you, shoot into them (and pay for the
  noise), or wait for nightfall.
* **The Hum night is silent**: from the evening before the Hum the herds leave and the birds go.
* **Hunting**: a deer or hare killed with any weapon leaves a carcass that bleeds scent the
  Hollowed follow; butcher it with a knife or an axe for venison or hare, a hide or pelt, bone and
  sinew; roast the meat at a campfire, twist sinew into cordage, cut rawhide strips.
* Later: wolves (TD-066).

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
* **Program Directives** (the challenges): chaptered goals on the tether and in the Record tab.
  1. *Arrival*: fell, axe, fire, lean-to, sleep.
  2. *The Cordon*: search, enter, kill, read, clear.
  3. *Holding Ground*: logs, the Hum, a supply drop, level 7.
  4. *Into the Bloom*: Seeded or Bloomed kills, specials, more Hums, level 12.

  Each pays XP and supplies; finishing a chapter opens the next.
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

**Landed (v1, ADR-0031):** world settings with presets on the New Game screen's World tab (size 2-7
regions, terrain, roughness, biome mix, rivers, lakes, towns and their size, wilderness and road
density) and a map preview; ranges and valleys carved by drainage, lakes in basins, rivers falling
to a lake or the map edge, a biome map, towns as generated frameworks of zoned lots on level ground
(buildings picked or generated per run, ADR-0030), a road network with bridges, the authored places
by site, a drop site by a road, and Bloom patches far from it. Saves record the settings (save
v6). Still to come: coasts, burnt/snow/swamp biomes, caves, traders, the Ashen's territory, and
streaming regions for large worlds (TD-081..084).

## 11. POIs and buildings

POIs are authored with the **POI spec DSL** (ASCII floor plans + route/sleeper/loot/trap lists,
`docs/POI_AUTHORING.md`) and compiled to scenes with metadata. Frameworks place them on lots.

Every building is a small dungeon (ADR-0018): a validated route with a locked front and a
shortcut out, held sleeper groups that ambush on a trigger (a room, a door, a pickup, a search or a
trap), traps a careful player spots and disarms, lock cues that read at a glance, and a guardian on
the loot. Below-ground rooms are real cellars cut out of the terrain (TD-026, ADR-0007).

**M1 roster: 25 buildings in Larch Hollow (D6).**

*Pell's Crossing (town framework `pell_crossing`)*

| POI | Tier | Concept | Route sketch |
|---|---|---|---|
| The Merrow House | 1 | Small family home; the family barricaded the front door against their own father | Barricaded front → round back through the kitchen → hallway sleepers (creaky boards) → kids' room ambush → back door shortcut |
| Mile 9 Diner | 1 | Roadside diner, last-stand barricade around the counter | In over a booth → kitchen → pantry ambush when its door opens → walk-in loot (bear trap in the barricade gap) → back exit |
| Pell Post Office | 1 | Post office opposite the church | Deadbolted front → 24-hour box lobby → pried box wall (bear trap) → postmaster's office (cage key) → basement → dock stair → registry cage ambush → unbolt the dock |
| Lou's Trailer | 1 | Single-wide on blocks; a radio man who stayed on the air | Front bolted, back blocked → clawed bedroom wall → soft hallway → radio room (taking the key wakes Lou) → gun cabinet → unbolt the front |
| Pell Pharmacy | 2 | Looted pharmacy with a locked dispensary | Shutter chained → loading bay → stockroom ambush → dispensary key in the office → dispensary (alarm on the door, guardian) → side door |
| Calder Hardware & Feed | 2 | Hardware store; the owner hid tools in the loft | Shelving maze (can chime) → back-room ambush → ladder by a bear trap → loft guardian, weak floor → drop outside |
| St. Ansel Church | 2 | The congregation still sits in the pews | Chained doors → churchyard to the vestry (bear trap) → nave (creaky aisle) → belfry for the pantry key → drop through the choir loft → fellowship-hall ambush → pantry guardian behind a shotgun |
| Northwoods Tavern | 2 | Roadhouse on Route 9 | Front nailed → beer-hatch ladder to the keg cellar → trapdoor behind the bar (keys or the bottle chime wake the bar) → back stairs → Marnie's room (shotgun, guardian, safe) |
| Pell Ranger Station | 3 | Ranger substation; last log of Deputy Hale | Fenced lot → office (creaky boards, keys) → evidence locker search wakes the cell block → deadbolted security door → shotgun on the evidence room → guardian |
| Pell Grange Hall | 3 | The town's last shelter, a ward of cots | Barricaded front → stage door → hall of cots (chime ambush) → kitchen triage (bear trap) → sick-bay ambush → records room behind an alarm (guardian) → drop through the rotten balcony |
| Volunteer Fire Station (Pell's Crossing; also a random-town pool building) | 2 | Double-height apparatus bay with the engine still in it; the crew went to the dorm | Bolted watch office, bays padlocked → broken hose-tower door (bear trap) → ladder up the tower to the lookout (station keys) → day room → dorm door (creaky aisle, the dorm wakes) → down the brass pole into the bay ambush → chief's office guardian → unbolt the watch office |
| Consolidated School (Pell's Crossing; also a random-town pool building) | 3 | The Cordon's failed evacuation point: cots in the gym, triage in the nurse's office | Front doors boarded → Mrs Dale's window (bear trap) → classrooms and lockers → teachers' workroom ambush → lights catwalk over the gym (creaky, boiler key) → drop through the rail gap: the families in the cots wake → nurse's triage → boiler-room cellar → isolation behind a shotgun (guardian) → unbolt the back door |
| Tamsin Valley Savings & Loan (Pell's Crossing; also a random-town pool building) | 3 | A bank that closed at three o'clock with a line still waiting | Front bolted → staff-room window → creaky back hall → manager's office (the combination) → the line in the banking hall turns → behind the teller counter → dial the vault (or cut it: ADR-0026, the whole building wakes) → vault guardian → unbolt the front |

*Route 9*

| POI | Tier | Concept | Route sketch |
|---|---|---|---|
| Cordon Gas & Garage | 2 | Gas station across from the diner; SICK INSIDE | Open bay → mechanic under the lift → inspection pit → knocked-out wall (chime, bear trap) into Dale's furnace cellar → hatch up to the office → shop |
| Tamsin Valley Clinic | 2 | Small clinic turned Cordon Medical's isolation ward | Screening barriers → waiting room window → creaky landing to the ward (taking the drug-closet key wakes it; a rotten floor drops into x-ray) → Patient 1's films |
| Timberline Motel | 3 | Roadside motel whose guests broke through their walls | Upper walkway (creaky) → master key on the cart → through the bathroom walls 8 → 7 → 6 → 5 → drop into room 1 → laundry ambush |

*The Okafor farm (framework `farm_okafor`)*

| POI | Tier | Concept | Route sketch |
|---|---|---|---|
| The Okafor Farmhouse | 3 | Two storeys and a root cellar; the family nailed Papa into his room | Boarded porch → parlour window (the rubble stirs) → creaky landing → spare-room floor into Papa's room → his clawed hole into the cellar ambush (Papa, guardian) → padlocked cold room behind a shotgun → hatch shortcut to the pantry |
| The Okafor Barn | 2 | Dairy barn; something lived in the loft | Chained doors → torn workshop boards → aisle bear trap wakes the stalls → feed-room key behind a chime → tack-room ladder to the nest (guardian) → hayloft ambush, weak floor → hay drop |

*Wilderness*

| POI | Tier | Concept | Route sketch |
|---|---|---|---|
| Cedar Ridge Lookout | 1 | Fire lookout tower on the summit | Trail → stair house window → held group at the locked gate → woodshed for the spare key (bear trap) → ladder into the cab (Marnie rises) → bolted back door |
| The Trapper's Cabin | 1 | One-room cabin, boarded from outside with a warning | Bear trap at the corner → clawed hole under the lean-to → held trio (journal, bolt or cache wakes them) → smokehouse key (second trap) → cache |
| Tamsin Logging Camp | 2 | Camp house and office at the end of the logging road | Kitchen door → office keys wake the cookhouse → padlocked drying room (chime) → creaky bunkroom aisle → foreman's room (guardian) → bolted side door |
| Larch Hollow Sawmill | 4 | A three-level mill on the pond: the valley's hardest building | Barred doors → log-haul stairs → deck boards wake the saw floor → offices for the keys → lunchroom ambush → one-way dust chute → basement ambush → payroll office behind a shotgun (husk guardian); a weak floor punishes greed |

*Outskirts*

| POI | Tier | Concept | Route sketch |
|---|---|---|---|
| Larch Pond Bait & Boat | 1 | Bait shop and boathouse on piles over the pond; the Ruuds fished through the loft floor | Shop padlocked from outside → round to the dock (bear trap under the net) → slip walk (loose boards wake the mill hands across the water) → bay ladder to the net loft for Ned's keys (the bay wakes) → bait-room padlock → shop → Ned's office (guardian, safe) → bolted side door |
| Ashen Watch Camp | 2 | Mostly outdoor: a palisade camp of the Ashen at the treeline, taken by the fever | Barred gate → round the palisade to the burnt breach (bone chimes) → burial platform for the cache key (jaws in the grass; the key wakes the lean-to) → clawed longhouse wall → the sick round the hearth (ambush) → hatch to the cache pit (keeper, guardian) → the longhouse's bolted back door |
| Tamsin River Campground | 2 | County campground on a gravel loop; the host kept a ward in the shower house | Fee station (cans on the door) → the loop past tents, an RV and fire rings (bear trap at site 5) → padlocked host trailer → shower house: the women's-side ward wakes when its door opens, Bev's keys in the utility room wake the chained men's side → the trailer: an alarm on the bedroom door, Gus on the lockbox (guardian) → bolted back door |

**No two runs alike** (ADR-0030). As in 7 Days, a place should feel different every run:
* every building is dressed per run from the world seed: which furniture is worn, broken or gone,
  which lights still burn, where the grime, water stains, mould and survivors' marks are, the
  clutter;
* authored buildings give rooms **alternatives** picked per run: the back bedroom that is a nursery,
  a study or a junk room, the wallpaper, which doors are shut or kicked in, where an ambush lies,
  where the trapper set his jaws (the Merrow House, the Mile 9 Diner, the Okafor farmhouse and
  Lou's trailer first); the validator proves every option and combination;
* ordinary houses, duplexes, corner stores and workshops are **generated** from templates as
  tier-1, dungeon-lite filler (a bolted front, a way in round the back, a small ambush on the loot
  room), so a street of twelve reads as twelve houses; framework lots without an authored pick
  choose from the pool or generate. Pell's Crossing's **Larch Street** is six such lots, with the
  school, the fire station and the bank reserved on its corner.

*Pool buildings (random towns)*

Authored set pieces with no fixed place: random towns (ADR-0031) fill their commercial, civic and
industrial lots from them through `LotPicker` by zoning, tier and footprint (sized for the
generator's 28 x 32 commercial, 32 x 32 civic and 26 x 26 industrial lots), so two towns of one
world show different landmarks. Each is a full dungeon with room alternatives (ADR-0030), and its
notes name people, not a town. None stands in the handcrafted map, and Larch Street's residential
lots never draw one. Props: `data/props/town3.json` (`props_town3.py`) and, for the second round,
`data/props/town4.json` (`props_town4.py`).

| POI | Tier | Zoning, footprint | Concept | Route sketch |
|---|---|---|---|---|
| Suds & Spin Laundromat | 1 | commercial, 22 x 26 | Coin laundry with three flats over it; one family barricaded in, the neighbour came through the wall | Chained glass doors → round to where a pickup went through the side wall → laundry floor (big dryers stand open; one isn't empty: the change machine or the staff door wakes them) → Dee's change office for the stair key → loose boards upstairs wake Hal's flat (cans across his kicked-in door) → through his clawed hole into the Bauers' front room (guardian, their stores) → bolted back door to the alley |
| Hollowmere Grocery | 2 | commercial, 28 x 32 | Two-storey grocery hall with a mezzanine office; the stock boy locked in the walk-in | Chained front, carts piled behind it → past Northline's reefer trailer (jaws under its doors) → pried roll-up door → stock room → butcher's counter (Sal stands there, held) → a maze of collapsed shelving: only aisle 2 is clear, cans strung across it → the meat room door wakes the butcher → up to Ruth's office on the mezzanine for the key → drop through the broken railing → walk-in behind a battery alarm (Danny, guardian) → bolted meat-room door |
| Bracken Lumber & Feed | 3 | industrial, 26 x 26 | Lumber yard and feed store; a timber shed open to its rafters and a grain leg climbing beside the feed bin | Padlocked store, chained shed → through the yard (forklift, stacks, jaws) → the shed's back doors (their cans wake the shed) → ladder to the catwalk (rotten boards past the tool crate) → feed loft (its door wakes the sacks) → mix loft → ladder up the grain leg to the head house: Walt and the office key → back down → Walt's office, wired to his shotgun (Eli, guardian) → bolted yard door |
| Pell County Library | 2 | civic, 32 x 32 | Carnegie-style library: a reading room two storeys high, the stacks a maze of creaking boards, the librarian's flat over them, the county archive in the basement | Bolted front doors → up the fire-escape ladder to Ida's back porch → her flat (the cage key, her diary) → back stair → the stacks (every board wakes them) → the reading room, where they sit at the tables (ambush as you walk in) → circulation hall → children's corner → cellar → the archive cage, chained and alarmed (the Cordon's clerk, guardian) → out through the bolted front doors |
| KHLW Valley Radio | 2 | civic or commercial, 26 x 30 | Small AM station where the Cordon read its bulletins; the generator still runs at dusk: the ON AIR sign, the racks and the mast beacon burn | Chained front → the generator shed → the hole Bud cut for the generator cable (jaws in the gap) → equipment room → Bud's office → the hall's boards or the studio door wake the booth (Mel at the console, the transcripts) → out of the office's bolted side door → up the lattice mast's ladders past two rest platforms → the relay cabinet (Bud, guardian) |
| Hollis Pawn & Gun | 3 | commercial, 28 x 28 | Pawn shop and gun counter; Ray Hollis held out in his vault room until the counter stock ran out | Grille down, front bolted → the alley: back door jemmied → back hall (loose boards) → Ray's office (the book) → the staff door wakes the looters on the showroom floor → basement range: Ray's body and the vault key (the range wakes; cans in the doorway) → vault door on Ray's shotgun (an alarm in one dressing) → the vault (Danny, guardian) → unbolt the front |
| Northfork Packing Co. | 3 | industrial, 26 x 26 | Cannery the Cordon took over to can rations; the night shift never went home | Office bolted → a truck through the dock wall (jaws among the totes) → retort room (the night shift in the baskets wakes) → the two-storey packing floor → gallery (loose boards) → foreman's office: the cold-store key (the line below wakes) → the cold store (alarm in one dressing; the quartermaster, guardian) → unbolt the street door |
| Water Works | 2 | industrial, 26 x 26 | The town's pumping station; Gus kept the emergency water and tablets for "the town" | Street door bolted → smashed workshop window (jaws) → hall → the lab: the stores key (the pump hall wakes) → two storeys of pumps (cans across the door) → down to the valve gallery (two of the crew) → emergency stores (alarm in one dressing; Gus, guardian) → unbolt the street door |
| Ridgeline Aggregate | 2 | industrial, 26 x 26 | Quarry scale house and office; the blaster locked himself in the powder magazine rather than sign it over | Office bolted → a haul truck through the shed wall (jaws by the drill rack) → the scale house (the weighmaster at his terminal) → manager's office: the magazine key (the crew wakes, in the core shed or round the radio) → magazine door (cans in one dressing) → the magazine (Pete, guardian) → unbolt the front |
| Veterans' Post | 2 | civic, 24 x 22 | Bingo-night hall turned shelter; the quartermaster kept the cellar stores and the raffle revolver by the count | Doors chained → the kitchen door kicked in → the hall (the families who sheltered there) → canteen: the cage key in the till (the hall wakes) → back hall, down the cellar stair → the cage (a shotgun on its door or cans on the stair; the quartermaster, guardian) → out through the vestibule, unchaining the doors |

**Planned (M2+)**: school, mine office, rail depot, dam control house, lighthouse, fishing co-op,
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
