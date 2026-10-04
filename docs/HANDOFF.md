# Handoff — where the M1 slice stands and how to resume

Snapshot of in-flight work so the next session can pick up exactly where this one stopped.
Delete this file once everything below is merged and M1 is signed off.

## Verified state of this branch
* `make import` ok · `make check` 137 scripts, 0 failed · `make smoke` PASS (world load, fell tree →
  logs, carry, freeform + snapped logs, campfire blueprint, stations/warmth, cordage + stone axe
  crafting, needs drain, night wanderers, Hum waves + flow field + report, save/load restores
  structures/clock/horde memory/inventory).
* `make test`: all unit/integration tests pass, including the new SDF volume tests (surface-nets
  winding fixed in the same commit). Two POI tests are pending/risky only because no POI JSON is
  merged yet (`game/data/pois/` is empty on this branch).
* Visual QA (`make screenshots`, software Vulkan): foliage now renders with its generated
  materials (import self-repair), haze/fog tuned, far impostor forest visible. The screenshot tool
  now waits for vegetation streaming (`VegetationManager.is_settled()`), and near vegetation
  streams nearest-chunk-first, so re-shoot `drop_site_morning` to confirm the near forest appears.

## Unmerged parallel work (asset + POI agents)
Six agents were generating assets in git worktrees under `.claude/worktrees/agent-*`. Their
unfinished work is preserved on this branch as patches in `wip/agents/` (one per agent, made
with `git diff` against this branch's base including untracked files; generated outputs
excluded). Each patch's header has the agent's own status note when it sent one.

| Patch | Contents | Integrate by |
|---|---|---|
| `poi_kit` | Blender kit: walls/floors/doors/windows/stairs/roofs + finish texture arrays (`docs/POI_KIT.md`) | apply, `make assets`, wire `kit_wall`/`kit_floor` surfaces into `PoiParts.kit_material` |
| `props_interior` | `data/props/interior.json` + generators | apply, `make assets`, `make validate` |
| `props_exterior` | `data/props/exterior.json` + generators (vehicles, fences, street fixtures) | same |
| `characters` | rig, Hollow/Lurcher/Keener bodies, animations, first-person arms | apply; hook `fp_arms` into ViewModel (TD-016), bodies into `EnemyVisual` |
| `items_structures` | item models, viewmodels, `items/supply_canister`, log/camp/station structures | apply; ModelLibrary picks them up by id (spawn canister uses `items/supply_canister`) |
| `pois` | 5 Pell's Crossing buildings + `pell_crossing` framework + Merrow House | apply, `make validate`, `make test` (un-pends the POI tests), F6 route check |

Apply one at a time on a clean tree: `git apply --3way wip/agents/<name>.patch`, then
`make assets && make import && make check && make validate && make test && make smoke`, commit,
and delete the patch. Order: items_structures → poi_kit → props_interior → props_exterior →
pois → characters (POIs need the kit and props ids to validate).

## Remaining M1 work after the merges
1. Re-run `make screenshots` (all shots) and review: forest floor brightness under canopy, Pell's
   Crossing streets with buildings, interiors (`pell_crossing_street`), Hum night shot.
2. `make bake` for impostors/icons from the real tree models (TD-005).
3. Full slice playthrough on a GPU machine (TD-003): wake → gather → stone axe → lean-to → clear
   a Pell's Crossing building along its route → survive a night and the Hum (night 3) → save/load.
4. Update `docs/ROADMAP.md` M1 statuses and close fixed TECH_DEBT rows.
