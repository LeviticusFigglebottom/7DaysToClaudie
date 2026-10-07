# Workboard — who is doing what, across sessions

The integrator session keeps this file. Other sessions read it after merging the integration
branch `ccr-24ba8b7d-fttoi8` and send changes as messages; they don't edit it. That way it never
conflicts.

**Round 2 (2026-10-06).** The first round's four sessions are gone, and with them every message
they sent. A new hub took over from git alone. It merged session 3's last two commits and session
2's caves. It found agent Z's fidelity round and session 4's wall-gap work lost: nothing was
committed. It then started three new worker sessions on the old branches with the same roles. The
old integration branch `claude/compassionate-dirac-8mtvxi` is frozen at 891830b; integrate into
`ccr-24ba8b7d-fttoi8` instead.

## Sessions
| Session | Branch | Role | Now | Next |
|---|---|---|---|---|
| Integrator `session_01F4L1SyEdjgRRBm7g93Yk8J` | `ccr-24ba8b7d-fttoi8` (integration) | Hub: reviews and merges every branch, runs agents, delegates | Landed this round: session 2's caves (ADR-0044), tier-5 contract (TD-179) and the Ashen phase 1 (ADR-0048, generator VERSION 6); session 3's streamed random worlds, Phase 3 part 2, save v7, TD-182 and the stream budgets; agent Z's town ground and biome fog (ADR-0047); the hub's mine site (TD-169, VERSION 7) and farming and rain collection (ADR-0049). Every generated model is built. Now: renders and landing commits for X and Y | The garden and Ashen camp renders (TD-215); Z's asset side (fur, impostors); traps and electricity (M3 part 2) or more pool dungeons |
| Session 2 `session_018Mc59z7WZz2YkXsyMHsJ75` | `claude/hollowmere-wildlife-town` | Wildlife, town content and economy | A tier-5 contract on `bloom_core_canister` (TD-179), then the Ashen (ADR-0048) | Ashen camps, scouts, raids, fear of fire |
| Session 3 `session_01Nvn2rfJdMq7iK7ZuQhac7y` | `claude/hollowmere-playable` | Playable builds and stability | Streaming on for random worlds (TD-137, TD-118), then Phase 3 part 2 (TD-107) | Phase 4's save side (v7, the world bundle), then TD-003's headless profile |
| Session 4 `session_01DYqPNtu8CtWNbHWPmbsFcW` | `claude/blissful-wright-gnc54e` | POI prop placement, then first-person hands | Merge the integration branch (take its side of the facing fix), port the two lost nudges, then wall-mounted props flush to their walls (TD-159–161) | The first-person hands (ADR-0045, TD-172–175) |

## Protocol
* **Talk to the hub.** Use the `send_message` tool of the Claude Code Remote MCP server, with
  session_id `session_01F4L1SyEdjgRRBm7g93Yk8J`. Message it when you start a stream, when a stream
  lands (with commit hashes), when you're blocked, and before you touch a file outside your
  ownership below. You can message another session directly when it saves a round trip; copy the
  hub in.
* **Commit and push often.** A container can be reclaimed at any time, and with it everything
  uncommitted. Round 1 lost agent Z's work and session 4's wall-gap fix that way. Push a commit
  at least every hour of work, and before you end a turn. A WIP commit on your own branch is fine.
* **Branches.** Push only to your own branch; never rebase or force-push. Merge the integration
  branch into yours about hourly and before you push. The hub merges your branch into the
  integration branch.
* **Ownership.** A file belongs to the stream listed below until that stream lands. Outside your
  own files, make only small additive hunks, and say so in your status. Never revert someone
  else's change.
* **Numbers.** Use only the ADR and TD numbers allocated to you below. Save version: bump only
  right after merging the integration branch, from what's there, and tell the hub.
* **Toolchain.** A fresh container has none. `make setup-godot && python3
  tools/setup/vendor_gut.py && git checkout game/addons/gut` (then `make import`) is enough for
  check, validate and test. Add `make setup` and `make assets` (about 2.5 h the first time) only
  when you need generated models or renders.
* **Never idle.** Keep your container busy: run independent work in parallel with subagents in
  worktrees (one Godot process each, one render at a time). When your queue runs thin, message the
  hub for new work instead of ending your turn with nothing running.
* **Status.** End each turn with a short status to the hub: what landed, what's next, blockers.

## Active streams and the files they own
| Stream | Where | Owns |
|---|---|---|
| The Corvane Field Lab (Y), landing | integrator | `corvane_field_lab.json` with its notes, loot, keys and items, `props_lab.py` with its catalog and `data/props/lab.json`, the `lab_signs` atlas, `test_field_lab.gd`, its pool entry, ADR-0046 |
| Wilderness set pieces, round 3 (X), landing | integrator | its four building JSONs (Camp Tamarack, Elk Ridge Lodge, the Cordon Quarantine Camp, the Haldane Place) with their notes, loot and keys, its props family, `test_wilderness_round_three.gd`, and its four entries in the wilderness pool of `world_gen.json` |
| Fidelity round (Z), code side | integrator | landed (ADR-0047); the asset side (fur, impostors: TD-005/006/067) waits for renders |
| Tier-5 contract, then the Ashen (ADR-0048) | session 2 | contract and trader data and code (`game/data/traders/`, `contracts`), new Ashen data (`game/data/factions/` or `enemies/ashen*`), Ashen AI under `game/src/ai/ashen/`, Ashen camp POIs, their props and generators; `enemy.gd` hunks reported |
| Streaming default, Phase 3 part 2, Phase 4 (v7) | session 3 | `.github/workflows/`, `game/export_presets.cfg`, the load sequence (`game_world.gd`, `world_loader.gd`, `PoiManager`'s placement path, `PoiBuilder.build`'s validator argument), RegionStreamer, PoiRegistry, `terrain_holes.gd`, `terrain_manager.gd`, thread-safety fixes in `game/src/world/terrain/` and `vegetation/`, `game/src/core/save/` (v7) |
| Wall-mounted prop offsets | session 4 | the wall-mount math in `PoiBuilder._prop_xf` and `poi_layout.gd`, wall-depth data on prop defs, and a validator check for wall gaps. Session 3 owns the rest of PoiBuilder; keep hunks small and report them |
| First-person hands (ADR-0045), after the offsets | session 4 | `game/src/player/viewmodel.gd` and `viewmodel_holds.gd` arms and hold poses, the first-person arms generator (`character_fp_arms.py`) and its catalog entries; session 2's npc_build library is shared (additive hunks, reported) |

## Allocations
* ADR: 0026 (vault, S2), 0027 (wildlife, S2), 0031 (random worlds), 0032 (pool, if needed),
  0033 (weather), 0034 (hounds and Murmurs, S2), 0035 (base building, S2), 0036–0037 (session 3),
  0038 (streamed worlds: session 3 adds its phases), 0039 (traders and contracts, S2), 0040
  (organic towns, the hub), 0041 (new biomes, the hub), 0042 (wilderness set pieces, the hub, if
  needed), 0043 (session 4, if needed), 0044 (the Corvane caves, S2), 0045 (first-person hands,
  session 4), 0046 (the field lab, the hub), 0047 (agent Z, if needed), 0048 (the Ashen, S2), 0049 (farming and rain collection, the hub).
  Next free: 0050.
* TD: S2 094–101, 111–114, 141–148, 162–171 and 186–195 (contract, the Ashen); session 3 102–109,
  126–130 and 196–205; session 4 159–161 and 172–175 (hands); the hub 110, 115–125, 131–140,
  149–158 (agents W and X), 176–180 (agent Y), 181–185 (agent Z), 206–210 (the mine site), 211–220 (farming and rain), then 221 up.
* Save version: 6 since random worlds. Traders add `world.traders` and `players[*].contracts`
  without a bump (both load empty from older saves). 7 is reserved for session 3's world bundle
  (RWG v2 Phase 4), which carries those keys through. Anyone else who needs a bump asks the hub
  first.

## Queue (in order)
1. Done: everything in round 1's list (random worlds v1 and v2, weather, the pool buildings, the
   third block, hounds and Murmurs, base building, the playable builds, the "how to play" guide,
   traders and contracts, the streamed load behind `stream`, Phase 3 part 1, the burnt forest and
   fen, every crash and freeze the owner has hit), and in round 2 the Corvane caves (ADR-0044).
2. The hub: land X and Y (the lab's `plastic_green` material, X's unused meat-locker container
   and free-standing pelt board; `make assets`; renders; reviewed landing commits; ADR-0046's pool
   wording); restart Z; then a `mine` wilderness site (TD-169).
3. Session 2: the tier-5 contract (TD-179), then the Ashen (ADR-0048).
4. Session 3: streaming on for random worlds; Phase 3 part 2 (TD-107: fixture batching, `poi_at`
   on a grid, holes per built POI, StreamMeter, ModelLibrary warm-up, `test_poi_streaming.gd`);
   Phase 4 (v7, the world bundle; then the New Game cap lifts past 7); TD-003 profiled headless
   (a GPU run is the owner's). It keeps `make tour` clean throughout.
5. Session 4: the lost nudges (St. Ansel's pantry freezer, the tavern's bedroom safe), wall gaps
   (TD-159–161), then the hands (ADR-0045, TD-172–175).
6. Later, unassigned: companion Ezra Vane; main-map regions D7 (Waystation 9's surroundings) and E6
   (Mile 12); perk capstones, the forge and the chemistry bench.
7. Needs the owner (a GPU and a human): the M1 playthrough, 60 FPS on target hardware, feel and
   balance (HANDOFF.md "Not verified yet").

## Player report 3 (Windows Build #67, 891830b; round 2)
Screenshot: `docs/playtest/2026-10-06_build67_lighter_door.webp` (Pell's Crossing, a lit lighter, a
cottage's front door). The owner said it "looks incredible", but:
1. **New random world: the player can't move after spawning.** It loads fine, then no movement.
   (Session 3.)
2. **In that same new world, looking up detaches the arms**: hands and arms float off into the sky
   where you look. Not seen on Continue. Probably the same root cause as 1; one suspect is that the
   warm-up camera or a stand-in camera stays current while the player's camera and viewmodel don't
   follow. (Session 3, with session 4 for the viewmodel side.)
3. **Continue keeps progress but not the last location.** (Session 3, saves.)
4. **Hands still look unnatural holding things**, the lighter worst of all. Its flame looks off and
   trails behind as you turn (flame particles in world space, not following the hand).
   (Session 4, ADR-0045.)
5. **A cottage front door (the intended entrance) has no steps up to its raised sill**, and the
   door has no "open": it just has no collision. It is likely a door authored `broken` (leaf drawn,
   passable). (The hub: POI doors and generated buildings.)

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

## Player report 2 (Windows Build #46)
Same setup, now on the downloadable build:
* **Black interior walls.** The hide-based probe budget left rooms waiting behind every queued
  probe, and a hidden probe still held its atlas slot, so the crash could still come after about
  64 rooms. Fixed by parking far probes out of the tree, nearest first (8625cbe, Build 56).
* **A 16.5 s "Waking up…" freeze.** Every shader pipeline compiled in the player camera's first
  frame. A warm-up camera now draws the world behind the loading screen (session 3, 71d68d3).
* **A "brown cover" door the player walked through.** A door authored broken, with no broken
  model, drew a stand-in slab over an open doorway. The leaf is now hidden (acb7ddb), and there is
  a door_metal_broken model.
* **Stairs backed against a door.** The fire station's stair door opened halfway up its flight.
  It now opens at the foot, and PoiValidator flags any doorway that meets a flight above its first
  step (ab89797).
* **First-person hands.** Big flat mitts, and a holding pose that reads wrong. Session 4 takes
  this next (ADR-0045, TD-172–175).

## Lessons (read before your first render)
* Every checkout and worktree of this project shares one `user://` folder (Godot keys it by the
  project name). Two test runs at once can clobber each other's random-world cache and fail
  `test_rwg` with "cannot parse world.json": run one full suite per machine at a time.
* Adding a wilderness pool entry moves every place drawn after it: bump `RwgGenerator.VERSION`
  (pool data isn't in the settings key) and re-record test_composer_golden with SLOW_TESTS=1.
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
* Reflection probes share a 64-slot atlas, and going past it crashes the engine. In Godot 4.7.2 a
  probe takes a slot the first time it renders and keeps it until it leaves the scene tree or is
  freed:
  * Hiding a probe keeps its slot. A lab that showed one probe at a time crashed with the player's
    error after its 64th room.
  * Detaching its RenderingServer base frees the slot, but the probe never renders again.
  * UPDATE_ONCE probes render one at a time, about 9 frames each, in the renderer's order.
  * Setting any probe to UPDATE_ALWAYS clears the whole atlas.
  Put new probes in the `interior_probe` group; PoiManager's budget parks far ones out of the tree.
* A generated model can exist on disk and still not load (built, not imported yet). Check the
  loaded resource for null before `instantiate()`; ModelLibrary does.
* The instance shader-variable buffer is 262144. std_surface uses instance slots 0–4 (light_lit
  is 4); kit_wall uses 0 and 3. Don't renumber them.
