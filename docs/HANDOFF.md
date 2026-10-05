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
* **POI dungeons** (ADR-0018, TD-026). Larch Hollow has 22 authored buildings (DESIGN §11):
  * Pell's Crossing grew a church block: St. Ansel, the Northwoods Tavern, the post office, the
    grange hall and a trailer.
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
