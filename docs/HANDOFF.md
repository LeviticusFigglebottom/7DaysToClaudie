# Handoff — where the M1 slice stands and how to resume

Snapshot for the next session. Update it when the state changes; delete it once M1 is signed off.

## State of this branch
* All parallel work is merged: POI building kit, interior and exterior props, items/viewmodels/
  player structures, characters + first-person arms, and the five Pell's Crossing buildings with
  their framework. `make assets` builds every task (0 failures), `make import` is clean.
* Verified headless: `make check` (all scripts compile), `make validate` (0 errors), `make test`
  (all unit + integration tests, incl. POI routes and player traversal), `make smoke` (the slice
  loop: fell → carry → build → craft → night → Hum → save/load).
* `make bake` renders far-tree impostors from the real tree models (seasonal tint at runtime).
* Visual QA: `make screenshots` (software Vulkan, ~1–4 min per shot) → `build/screenshots/`.
  The suite covers the drop site, forest, Pell's Crossing road/street, the diner interior, the
  first-person view with a stone axe, a dormant Hollow close-up, a base and a Hum night.

## Not verified yet (needs a GPU machine and a human)
1. A full playthrough against the M1 acceptance criteria (docs/ROADMAP.md), including clearing a
   Pell's Crossing building along its route (vaulting the diner's booth window, the hardware
   store's ladder to the loft).
2. Frame rate on target hardware (TD-003) and tuning of `data/config/graphics_presets.json`.
3. Feel: vault timing, FP arm poses (TD-025), Hollowed animation blending, audio mix (TD-013).

## Next steps (in order)
1. Playtest the slice on a GPU (`make run-slice`); file issues against the ROADMAP checklist.
2. Hollowed vaulting/window navigation links and crowd avoidance (TD-011), so the town's window
   routes are dangerous both ways.
3. Author `okafor_farmhouse` (already placed in region D6) once POI cellars get terrain holes
   (TD-026).
4. Trim over-budget models (TD-019) and add a budget check to `build_assets.py`.
5. M2 planning: factions, caves through the volume terrain, companion, economy.
