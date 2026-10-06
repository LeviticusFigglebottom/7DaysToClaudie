# Handoff — where the M1 slice stands and how to resume

Snapshot for the next session. Update it when the state changes; delete it once M1 is signed off.

## State of this branch
* All parallel work is merged: POI building kit, interior and exterior props, items/viewmodels/
  player structures, characters + first-person arms, and the five Pell's Crossing buildings with
  their framework. `make assets` builds every task (0 failures), `make import` is clean.
* The 7 Days layer is in:
  * **World settings** (ADR-0014): five difficulty presets plus about 30 per-option settings on
    the New Game screen, including day length, Hum schedule and size, enemy speeds, loot,
    XP, needs and death penalty.
  * **Gamestage scaling** of spawns, loot and the Hum.
  * **Special Hollowed**: the Blister spits and bursts, the Husk is armoured, the Rammer charges
    through walls.
  * **Infected tiers**: Seeded and Bloomed.
  * **Progression that pays off** (ADR-0015): every perk effect is wired; points are spent in
    the Field Manual's Record tab.
  * **XP from everything you survive**, Remand supply drops, quality tiers, Sleeper Sense, and
    Program Directives (four chapters of challenges with rewards).
* A second refinement pass (ADR-0016) fixed about 80 of some 90 findings from six audits (AI, UI/saves,
  building/world, balance, player, environment). The rest are in TECH_DEBT TD-031..034. Most
  visible in play:
  * Hollowed path around buildings and through doorways (the navmesh was never queried).
  * Doors have collision.
  * You can drink from and fill bottles at streams; campfires need feeding.
  * Swimming floats instead of sinking.
  * Each run has its own save slot.
  * There is an options screen.
* A forest-level fidelity pass (ADR-0017) reworked the generated assets towards The Forest /
  Sons of the Forest:
  * **Forest floor**: moss mounds, twig-and-cone litter, a third sword fern, three times the
    ferns, patchy medium/ground scatter, and multi-tuft meadow grass. Ground cover now fades
    plant by plant in 32 m blocks instead of popping per 64 m chunk.
  * **Trees**: deeper fir and larch bark; real moss fronds on bark, rocks and logs; broken
    stubs instead of spikes; stronger buttresses.
  * **Rocks**: chipped, tilted boulders with triplanar mapping (no UV seams), LOD1 and shadows.
  * **Characters**: 16k Hollowed with smooth faces and unsmeared hands; first-person hands
    close around a held tool.
  * **Bridge**: the Route 9 bridge over the Tamsin River.
  Save version 2 drops harvested-plant records (the medium/ground layout changed); stumps are
  kept.
* Verified headless:
  * `make check`: all scripts compile.
  * `make validate`: 0 errors, 0 warnings over 22 POIs and 2 frameworks.
  * `make test`: 225 unit and integration tests. They cover:
    * POI routes and dungeon mechanics (triggers, traps, locks, stable ids, stairwells,
      placement);
    * cellar holes;
    * water surfaces;
    * player traversal and swimming;
    * special Hollowed and hit zones;
    * supply drops, progression and directives;
    * saves (v3 migration, per-run slots, recovery, Windows-safe chunk files);
    * fire fuel, repairs and the horde's routing round buildings.
  * `make smoke`: the slice loop runs fell → carry → build → craft → night → Hum → XP, level,
    supply drop, spending points → save/load of all of it.
* **POI dungeons** (ADR-0018, TD-026). Larch Hollow has 25 authored buildings (DESIGN §11):
  * Pell's Crossing grew a church block: St. Ansel, the Northwoods Tavern, the post office, the
    grange hall and a trailer.
  * And a third block on Larch Street's corner (generated props in `data/props/town2.json`):
    * **the school** (tier 3), the Cordon's failed evacuation point: a double-height gym of cots
      with a lights catwalk to drop from, classrooms, a nurse's triage and an isolation cellar;
    * **the fire station** (tier 2): the engine wreck in a double-height bay, a hose tower to climb
      and a brass pole from the dorm down into the bay ambush;
    * **the Savings & Loan** (tier 3): a teller line that turns, and a vault that opens with the
      combination from the manager's desk, or is cut through with a screech that wakes the whole
      building (ADR-0026).
  * Route 9 has a gas garage, a clinic and the Timberline Motel.
  * The Okafor farm has a farmhouse and a barn.
  * The wilderness has a fire lookout, a trapper's cabin, a logging camp and the tier-4 sawmill.
  * The outskirts have Larch Pond Bait & Boat (its slip is open pond water: a keep_water pad,
    ADR-0024), the mostly outdoor Ashen watch camp and Tamsin River Campground.
  * Every building is a dungeon: held sleeper groups that ambush on a trigger, guardians on the
    loot, typed traps that a crouched player disarms, and lock cues that can be beaten off.
  * Cellars are cut out of the terrain mesh, collision and navmesh.
  * Piece states are keyed by stable ids (save version 3).
  * Three new directives use these mechanics: disarm two traps, clear a tier-3 building, clear the
    sawmill.
* **Varied interiors** (ADR-0030): no two runs dress a building alike.
  * Per-run dressing from the world seed: furniture worn, broken or gone, lights out or burning,
    grime, stains and survivors' marks, the clutter scatter. Saves from before v5 keep the
    buildings they were played in (`WorldState.poi_dressing` = legacy).
  * Room alternatives in the DSL, validated option by option and combination by combination: the
    Merrow House, the Mile 9 Diner, the Okafor farmhouse and Lou's trailer have five groups each.
  * Seven templates generate tier-1 houses, duplexes, corner stores and workshops; framework lots
    without a pick choose from the pool or generate one. Pell's Crossing's Larch Street is six of
    them, south of the third block.
  * `make poi-preview POI="merrow_house gen:cape_cod:3" POI_ARGS="--seed 7"` shows a run's dressing.
  * **Pool buildings** (DESIGN §11): five authored set pieces only random towns place, picked for
    commercial, civic and industrial lots by zoning, tier and footprint: Suds & Spin Laundromat (a
    sleeper curled in a big dryer, a neighbour through the wall), Hollowmere Grocery (aisles of
    collapsed shelving, a mezzanine gallery, an alarmed walk-in, a reefer at the dock), Bracken
    Lumber & Feed (a timber shed open to its rafters, a weak catwalk, a grain leg to climb, an
    office wired to a shotgun), Pell County Library (stacks of creaking boards, a reading room under
    a two-storey ceiling, a flat reached by its fire-escape ladder, an archive cage in the cellar)
    and KHLW Valley Radio (a booth under a lit ON AIR sign, a lattice mast climbed platform by
    platform). Five to seven alternative groups each; `tests/unit/test_pool_buildings.gd`.
* **Random worlds** (ADR-0031): the main menu's Random World opens the New Game screen's World tab.
  * Settings and presets in `data/config/world_gen.json`, a map seed and a map preview; a world is
    generated in about a second and cached in `user://worlds/random/<id>/` in the main map's own
    format (world.json + region.json files + the towns' frameworks).
  * Land with valleys carved by its drainage, lakes, rivers to a lake or the edge, a biome map,
    towns of zoned lots filled per run, roads with bridges, the authored places by site, a drop
    site by a road. Saves record the world (save version 6).
  * `rwg_preview.gd -- --seed N --size S --out map.png` draws a map; `--world random` starts or
    smokes one. Every region is built and composed on first load (minutes for 5 x 5, TD-081).
* **The living forest** (ADR-0027): generated deer (doe and an antlered buck), snowshoe hares,
  songbirds and crows, spawned deterministically by biome and time of day round the player.
  * Herds graze, look up, bolt together (sight by light and stance, scent downwind, noise, the
    Hollowed) and bed down at night; the valley falls silent before a Hum.
  * Flocks flush for you, a Hollowed or a gunshot, and the flush is a sound the Hollowed hear;
    crows circle and call over what put them up.
  * Hunting: a carcass bleeds scent; `wildlife.butcher` with a knife or an axe gives venison or
    hare, a hide or pelt, bone and sinew. World settings `wildlife` and `wildlife_density`.
  * QA shots `deer_meadow_dawn`, `hare_brush`, `birds_lift_off`.
* **Surfaces, water and sky** (ADR-0019, ADR-0020):
  * Interiors wear in world space.
  * Roofs have trim and tiles that don't repeat.
  * Roads have lane lines; meadows are continuous; riverbanks are planted.
  * Lakes and rivers are drawn at last. They had faced down since the first water commit.
    They reflect the tree line that actually stands around them.
  * Distant hills carry a forest canopy, and clouds are shaded.
* `make bake` renders far-tree impostors from the real tree models (seasonal tint at runtime).
* Visual QA: `make screenshots` (software Vulkan, about 1–4 min per shot) → `build/screenshots/`.
  * Places: the drop site, forest, Pell's Crossing road and street, the diner interior.
  * Views: the first-person stone axe, a lit torch at night, and an awake Hollow close-up.
  * Scenes: the special Hollowed lineup, a landed supply drop at dusk, the Record tab, the
    options screen, a base, and a Hum night.
  * Pick shots with `SHOTS_ARGS="--only a,b"`.

## Not verified yet (needs a GPU machine and a human)
1. A full playthrough against the M1 acceptance criteria (docs/ROADMAP.md), including clearing a
   Pell's Crossing building along its route (vaulting the diner's booth window, the hardware
   store's ladder to the loft).
2. Frame rate on target hardware (TD-003) and tuning of `data/config/graphics_presets.json`.
3. Look and cost of the fidelity passes on a real GPU:
   * ground-cover density against frame time (thin with `grass_density`);
   * the 16k Hollowed in a full Hum;
   * triplanar rock;
   * tree LOD pops at chunk borders (TD-035);
   * the screen-reading water;
   * the raised far canopy at the edge of the built region.
4. Feel:
   * vault timing, FP arm poses (TD-025; the ready stance, diagonal chop and tool grip are new),
     Hollowed animation blending, audio mix (TD-013) and the stronger occlusion;
   * the second pass's balance: fire fuel per log, stream water's health cost, the infection
     fight-off line (12), bleeding, craft XP by category, perk values;
   * pacing of XP and levels at each preset;
   * whether a Rammer at gamestage 40 is fair against log walls.

## Next steps (in order)
1. Playtest the slice on a GPU (`make run-slice`; `--preset hollowed` or `--rule key=value` to try
   settings) and file issues against the ROADMAP checklist.
2. Balance pass on `progression.json` XP and the `infected_tiers.json` brackets, using the
   playtest numbers. Both are pure data.
3. Hollowed vaulting/window navigation links and crowd avoidance (TD-011), so the town's window
   routes are dangerous both ways.
4. Play the new buildings' routes and tune them: ambush triggers and stagger, trap damage and
   disarm reach (`data/config/traps.json`), the sawmill's difficulty against its tier 4. Then do
   the dungeon gaps: Hollowed that respect creaky and weak floors, nav rebakes after a collapse
   (TD-037), seats and beds for posed sleepers (TD-039).
5. Special Hollowed silhouettes and dedicated spit/charge animations (TD-027). (Supply drops now
   arrive by drone: ADR-0023.)
6. Taller rooms and multi-wing roofs (TD-008, TD-038, TD-040), so churches, barns and mills
   stop reading as stacked boxes.
7. M2 planning: factions, caves through the volume terrain, companion, economy, perk capstones
   and the joinery track (TD-030).
