# Workboard — who is doing what, across sessions

The integrator session keeps this file. Other sessions read it after merging
`origin/claude/compassionate-dirac-8mtvxi` and send changes as messages; they don't edit it. That
way it never conflicts.

## Sessions
| Session | Branch | Role | Now | Next |
|---|---|---|---|---|
| Integrator `session_018E4KRjV3zJkPMcpffWvXJq` | `claude/compassionate-dirac-8mtvxi` (integration) | Hub: reviews and merges every branch, runs agents, delegates | Agents O (random worlds), P (pool buildings), Q (weather) | Random worlds v2 (big streaming maps, organic towns); full screenshot QA |
| Session 2 `session_01FL8uPmvrm73zUGXv6bs3PZ` | `claude/hollowmere-wildlife-town` | Wildlife and town content | School, fire station, bank (ADR-0026) | Hollowed hounds and Murmurs (ADR-0034), then base-building fidelity (ADR-0035) |
| Session 3 (see the integrator's messages) | `claude/hollowmere-playable` | Playable builds and stability | Downloadable builds with assets; the player-reported freeze and crash | A performance pass for real GPUs (TD-003) |

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
| Random worlds (O, ADR-0031) | integrator | `game/src/worldgen/**`, `game/src/ui/new_game_panel.gd`, `game/data/config/world_gen.json`, `game/src/tools/cli/rwg_*` |
| Pool buildings (P) | integrator | `game/data/props/town3.json`, `props_town3.py`, the laundromat, grocery, lumber & feed, library and radio station JSONs |
| Weather (Q, ADR-0033) | integrator | `game/src/world/environment/**`, `game/src/world/fx/` (rain, snow), the weather hunks in every shader, rain and thunder audio |
| Town buildings (ADR-0026) | session 2 | the school, fire station and bank JSONs, `game/data/props/town2.json` and its generators, the vault lock kind |
| Builds and stability | session 3 | `.github/workflows/` (new export jobs), `game/export_presets.cfg`, the load sequence (`game/src/app/game_world.gd`, `world_loader.gd`) and fixes it reports to the hub |

## Allocations
* ADR: 0026 (vault, S2), 0027 (wildlife, S2), 0031 (random worlds), 0032 (pool, if needed),
  0033 (weather), 0034 (hounds and Murmurs, S2), 0035 (base building, S2), 0036–0037 (session 3).
  Next free for the integrator: 0038.
* TD: S2 094–101; session 3 102–109; integrator 110 and up.
* Save version: 6 since random worlds. Next bump: merge first, then take 7.

## Queue (in order)
1. Land O, P and Q, and merge session 2's town buildings.
2. Session 3: downloadable builds that include the generated assets, plus the reported freeze
   and crash (below).
3. Random worlds v2: compose regions on demand, so maps of 10–16 km stream within bounded
   memory; organic towns (streets that follow the land, irregular lots).
4. Session 2: hounds and Murmurs, then base-building fidelity.
5. A full screenshot QA pass and a stabilization round, then a "how to play" guide.

## Player report (the first human playtest)
On a fresh setup:
* the game showed "not responding" near the end of the load, then spawned the player;
* every asset was a primitive stand-in, with no textures and no grass;
* running up to one of them crashed the game.

Diagnosis so far:
* The generated assets aren't committed, and the toolchain that builds them is Linux-only
  (`tools/versions.env` pins Linux Godot and Blender). A Windows or macOS clone therefore runs on
  the procedural stand-ins, a mode nobody had played.
* "Not responding": the end of the load does a lot of work on the main thread in one frame.
* The crash is not diagnosed yet. The player's log is at `user://logs/godot.log`; the user dir
  is named `hollowmere`.

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
* The instance shader-variable buffer is 262144. std_surface uses instance slots 0–4 (light_lit
  is 4); kit_wall uses 0 and 3. Don't renumber them.
