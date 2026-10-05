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
* Verified headless:
  * `make check`: all scripts compile.
  * `make validate`: 0 errors.
  * `make test`: 149 unit and integration tests, including POI routes, player traversal, special
    Hollowed, supply drops, progression and directives.
  * `make smoke`: the slice loop runs fell → carry → build → craft → night → Hum → XP, level,
    supply drop, spending points → save/load of all of it.
* `make bake` renders far-tree impostors from the real tree models (seasonal tint at runtime).
* Visual QA: `make screenshots` (software Vulkan, about 1–4 min per shot) → `build/screenshots/`.
  * Places: the drop site, forest, Pell's Crossing road and street, the diner interior.
  * Views: the first-person stone axe and an awake Hollow close-up.
  * Scenes: the special Hollowed lineup, a landed supply drop at dusk, the Record tab, a base,
    and a Hum night.
  * Pick shots with `SHOTS_ARGS="--only a,b"`.

## Not verified yet (needs a GPU machine and a human)
1. A full playthrough against the M1 acceptance criteria (docs/ROADMAP.md), including clearing a
   Pell's Crossing building along its route (vaulting the diner's booth window, the hardware
   store's ladder to the loft).
2. Frame rate on target hardware (TD-003) and tuning of `data/config/graphics_presets.json`.
3. Feel:
   * vault timing, FP arm poses (TD-025), Hollowed animation blending, audio mix (TD-013);
   * pacing of XP and levels at each preset;
   * whether a Rammer at gamestage 40 is fair against log walls.

## Next steps (in order)
1. Playtest the slice on a GPU (`make run-slice`; `--preset hollowed` or `--rule key=value` to try
   settings) and file issues against the ROADMAP checklist.
2. Balance pass on `progression.json` XP and the `infected_tiers.json` brackets, using the
   playtest numbers. Both are pure data.
3. Hollowed vaulting/window navigation links and crowd avoidance (TD-011), so the town's window
   routes are dangerous both ways.
4. Special Hollowed silhouettes and dedicated spit/charge animations (TD-027); a visible drone
   for supply drops (TD-029).
5. Author `okafor_farmhouse` (already placed in region D6) once POI cellars get terrain holes
   (TD-026).
6. M2 planning: factions, caves through the volume terrain, companion, economy, perk capstones
   and the joinery track (TD-030).
