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
  * `make validate`: 0 errors.
  * `make test`: 176 unit and integration tests, including POI routes, player traversal and
    swimming, special Hollowed and hit zones, supply drops, progression, directives, saves (per-run
    slots, recovery, Windows-safe chunk files), fire fuel, repairs and the horde's routing round
    buildings.
  * `make smoke`: the slice loop runs fell → carry → build → craft → night → Hum → XP, level,
    supply drop, spending points → save/load of all of it.
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
3. Look and cost of the fidelity pass on a real GPU: ground-cover density against frame time
   (thin with `grass_density`), the 16k Hollowed in a full Hum, triplanar rock, tree LOD pops
   at chunk borders (TD-035).
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
4. Stable ids for POI props, sleepers and traps before any POI is re-authored (TD-031): saved loot
   states are keyed by list position today.
5. Special Hollowed silhouettes and dedicated spit/charge animations (TD-027); a visible drone
   for supply drops (TD-029).
6. Author `okafor_farmhouse` (already placed in region D6) once POI cellars get terrain holes
   (TD-026).
7. M2 planning: factions, caves through the volume terrain, companion, economy, perk capstones
   and the joinery track (TD-030).
