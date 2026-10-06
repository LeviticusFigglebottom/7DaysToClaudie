# Workboard — who is doing what, across sessions

The integrator session keeps this file. Other sessions read it after merging
`origin/claude/compassionate-dirac-8mtvxi` and send changes as messages; they don't edit it. That
way it never conflicts.

## Sessions
| Session | Branch | Role | Now | Next |
|---|---|---|---|---|
| Integrator `session_018E4KRjV3zJkPMcpffWvXJq` | `claude/compassionate-dirac-8mtvxi` (integration) | Hub: reviews and merges every branch, runs agents, delegates | Landed: random worlds v1 (O2), weather (Q2, ADR-0033), the pool buildings (P2), the guide's bug batch (S1), the wall-prop facing fix. Running: V (the QA and stabilization round), R2 (RWG v2 Phases 4 and 5: organic towns into generated worlds, generator VERSION 2); R1 (RWG v2 Phase 1: golden composer test, speed-ups, bands, cancel, cache LRU, ADR-0038); T (the organic town planner, ADR-0040); S1 (bugs found while writing `docs/HOW_TO_PLAY.md`) | Random worlds v2 (`docs/RWG_V2_PLAN.md`): Phase 1 (measure and speed up the composer and generator) once O2 lands, then Phase 4's generator side and Phase 5 (organic towns, ADR-0040); the full screenshot QA and stabilization round once O2, P2 and Q2 land |
| Session 2 `session_01FL8uPmvrm73zUGXv6bs3PZ` | `claude/hollowmere-wildlife-town` | Wildlife, town content and economy | Traders and contracts (M2, ADR-0039): Waystation 9, the shop, clear/fetch/defend contracts, reputation. Merged: hounds and Murmurs, base building (02cb425), pool round 2, the third block | Then the Corvane caves (likely) |
| Session 3 `session_01WUr5pb2Qqt1f8oLrbvKg1F` | `claude/hollowmere-playable` | Playable builds and stability | Merged: boot-step load, stand-in CI, menu notices, Build workflow (301e85c), terrain thread races (cb83882), the load fixes, the digging-crash fix (TD-104) and the Phase 2 groundwork (StepRunner, RegionRings, region attach/detach, the loading map) in 5fc5f3e. Now: Phase 2 proper and Phase 3 | Random worlds v2 Phases 2 and 3 (regions and buildings stream; the load path), then Phase 4's save side (v7, the world bundle), then graphics options (ADR-0037) |

## Protocol
* **Talk to the hub.** Use the `send_message` tool of the Claude Code Remote MCP server, with
  session_id `session_018E4KRjV3zJkPMcpffWvXJq` (or "@parent"). Message it when you start a
  stream, when a stream lands (with commit hashes), when you're blocked, and before you touch a
  file outside your ownership below. You can message another session directly when it saves a
  round trip; copy the hub in.
* **Branches.** Push only to your own branch; never rebase or force-push. Merge the integration
  branch into yours about hourly and before you push. The hub merges your branch into the
  integration branch.
* **Ownership.** A file belongs to the stream listed below until that stream lands. Outside your
  own files, make only small additive hunks, and say so in your status. Never revert someone
  else's change.
* **Numbers.** Use only the ADR and TD numbers allocated to you below. Save version: bump only
  right after merging the integration branch, from what's there, and tell the hub.
* **Status.** End each turn with a short status to the hub: what landed, what's next, blockers.

## Active streams and the files they own
| Stream | Where | Owns |
|---|---|---|
| Random worlds v2, generator side (R2: Phases 4 and 5, organic towns wired in; Phase 1 and the planner landed) | integrator | `game/src/worldgen/**`, `game/src/ui/new_game_panel.gd`, `game/data/config/world_gen.json`, `game/data/config/town_planner.json`, `game/src/tools/cli/rwg_*`, `compose_region*` |
| QA round (V) | integrator | fixes in building JSONs, `game/src/ui/new_game_panel.gd` and `game/src/app/main.gd` (seed handling, World tab label), the storm-night shot in `screenshots_runner.gd` |
| Traders and contracts (ADR-0039) | session 2 | the trader post, shop and contract data and scripts it creates; additive hunks elsewhere reported to the hub; no edits in `game/src/worldgen/**` |
| Builds and stability | session 3 | `.github/workflows/` (new export jobs), `game/export_presets.cfg`, the load sequence (`game/src/app/game_world.gd`, `world_loader.gd`, `PoiManager`'s placement path, `PoiBuilder.build`'s validator argument), thread-safety fixes in `game/src/world/terrain/` and `game/src/world/vegetation/`, and fixes it reports to the hub |

## Allocations
* ADR: 0026 (vault, S2), 0027 (wildlife, S2), 0031 (random worlds), 0032 (pool, if needed),
  0033 (weather), 0034 (hounds and Murmurs, S2), 0035 (base building, S2), 0036–0037 (session 3),
  0038 (streamed worlds: the hub creates it, session 3 adds its phases), 0039 (traders and
  contracts, S2), 0040 (organic towns, the hub). Next free: 0041.
* TD: S2 094–101, 111–114 and 141–148; session 3 102–109 and 126–130; the hub 110, 115–125 and
  131–140, then 149 up.
* Save version: 6 since random worlds. 7 is reserved for session 3's world bundle (RWG v2 Phase 4); anyone else who needs a bump asks the hub first.

## Queue (in order)
1. Done: random worlds v1, weather, the pool buildings, the third block, hounds and Murmurs, the playable builds. The QA round (agent V) is running.
2. Session 3: the first downloadable build from the Build workflow (artifacts on the Actions page),
   then the races and the performance pass. The freeze and the crash are fixed (below).
3. Random worlds v2 (`docs/RWG_V2_PLAN.md`): compose regions on demand, so maps of 10–16 km
   stream within bounded memory; organic towns (streets that follow the land, irregular lots).
   The hub takes the composer and generator; session 3 takes streaming and saves.
4. Session 2: hounds and Murmurs, then base-building fidelity.
5. A full screenshot QA pass and a stabilization round, then a "how to play" guide.

## Player report (the first human playtest)
On a fresh setup:
* the game showed "not responding" near the end of the load, then spawned the player;
* every asset was a primitive stand-in, with no textures and no grass;
* running up to one of them crashed the game.

Their setup: Windows 10, an AMD RX 9070 XT, the project opened in the Godot **4.7.1** editor (the
project pins 4.7.2).

Diagnosis:
* **The crash** was the interior reflection probes. The log shows "Reflection probe atlas index
  invalid ... (64) may have been exceeded", then `FATAL: Index p_index = -1 is out of bounds
  (size = 64)`. Every building is built at load with up to 8 interior probes: 92 for the main
  world's 31 buildings, 61 of them within 150 m of one point in Pell's Crossing. More than 64 in
  view overflow the atlas. Fixed in the hub: PoiManager's probe budget
  (`game/src/poi/interior_probe_budget.gd`) shows only the nearest 32 to 48 (TD-044).
* **Primitive stand-ins:** the generated assets aren't committed, and the toolchain that builds
  them is Linux-only (`tools/versions.env` pins Linux Godot and Blender). A Windows clone runs on
  the procedural stand-ins. Session 3's downloadable builds fix this.
* **"Not responding":** the end of the load did all its main-thread work in one frame of about
  15 s, mostly `PoiManager.setup_world` building every building. Session 3 split it into boot
  steps (301e85c): the longest frame is now about 0.5 s headless.
* A model that exists on disk but doesn't load (built, not imported yet) stopped buildings
  halfway with script errors. Every generated-model load now falls back to its stand-in.

## Lessons (read before your first render)
* Software Vulkan takes minutes per image. Imports and renders take
  `flock build/.godot.lock`, one at a time. `make screenshots` has a 30 s exit watchdog
  (`tools/qa_watchdog.sh`); start any other render with `setsid` and kill only your own process
  group.
* The Makefile's headless targets also take the lock. Running Godot directly for check, test,
  validate and smoke is safe.
* A new `class_name` needs an import before `-s` scripts can see it.
* `compose_region.gd` now loads content (d4d34eb); never cache a region composed without content.
* The asset manifest merges only the tasks each build touched (c410c49).
* Never replace an Array, Dictionary or Packed*Array member that worker threads read. In GDScript
  the assignment isn't atomic: the old value is released and the pointer is null before the new
  one is stored, so a reader in that window crashes (session 3 found this in its own TD-104
  copy-and-swap). Writing in place is no safer. A Packed*Array that a worker also holds is
  copy-on-write, so the write moves the buffer out from under the reader. Readers and writers must
  take the same Mutex; TerrainManager's terrain lock is the model (444375b).
* A WorkerThreadPool task still running at engine shutdown aborts the process with rc 134 and
  prints nothing. Wait for your tasks in `_exit_tree`, as VolumeTerrain does.
* Reflection probes share a 64-slot atlas, and going past it crashes the engine. Put any new
  probe in the `interior_probe` group so PoiManager's budget caps it.
* A generated model can exist on disk and still not load (built, not imported yet). Check the
  loaded resource for null before `instantiate()`; ModelLibrary does.
* The instance shader-variable buffer is 262144. std_surface uses instance slots 0–4 (light_lit
  is 4); kit_wall uses 0 and 3. Don't renumber them.
