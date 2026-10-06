# Workboard — who is doing what, across sessions

The integrator session keeps this file. Other sessions read it after merging
`origin/claude/compassionate-dirac-8mtvxi` and send changes as messages; they don't edit it. That
way it never conflicts.

## Sessions
| Session | Branch | Role | Now | Next |
|---|---|---|---|---|
| Integrator `session_018E4KRjV3zJkPMcpffWvXJq` | `claude/compassionate-dirac-8mtvxi` (integration) | Hub: reviews and merges every branch, runs agents, delegates | Landed this round: TD-134 and the real atlas fix (8625cbe: far probes parked out of the tree), trader posts in generated worlds (faadca8, generator v3), and the merges of session 3's streamed load with the Windows load-freeze fix (71d68d3) and session 2's traders and contracts with the playtest door fixes (9c768f6). Landed: W (burnt forest and fen biomes, ADR-0041, generator v4), session 3's Phase 3 part 1 (a8ec4a2), the field lab made `unique` (generator v5). Reported: X (four wilderness dungeons; finishing its lodge fixes and renders) and Y (the Corvane Field Lab, tier 5; its renders under review). Running: Z (a fidelity round) | X's and Y's QA close; Z lands; then build every generated model this checkout lacks (the town4 props, the hunting items, session 2's camp structures, the animals); a `mine` wilderness site once session 2's adit is in |
| Session 2 `session_01FL8uPmvrm73zUGXv6bs3PZ` | `claude/hollowmere-wildlife-town` | Wildlife, town content and economy | The Corvane caves (ADR-0044, TD-162–169): the Corvane Mining Co. Larkspur Exploration Adit in D6, under the Larkspur cliffs, as underground levels of a POI; a `"buried": true` level hunk in terrain_holes.gd, agreed with session 3. Its 62f61df (Hollowed see in the dark underground) lands with the caves. Merged: traders and contracts (ADR-0039), the quartermaster, the stair-door and broken-door fixes (9c768f6) | Then the Ashen (camps, scouts, raids, fear of fire) |
| Session 3 `session_01WUr5pb2Qqt1f8oLrbvKg1F` | `claude/hollowmere-playable` | Playable builds and stability | Merged in 71d68d3: the Windows load-freeze fix (a warm-up camera compiles pipelines behind the loading screen), RegionStreamer and the streamed load behind `stream`, per-region POIs and far vegetation, `make stream-check`, TD-103 (terrain meshes on the main thread under the dummy renderer), `--expect-assets` in the pack smoke. Now: verifying the merged Windows build, and merging 8625cbe (parked probes) into its streaming | Phase 3 (PoiRegistry with frame lots), then TD-003 (the 60 FPS pass), Phase 4's save side (v7, the world bundle), graphics options (ADR-0037) |
| Session 4 `session_015vPE349hAFMwSqC3TWWqqz` | `claude/blissful-wright-gnc54e` | POI prop placement, then first-person hands | Wall-mounted props flush to their walls: 83 sit more than 10 cm off, plus two edge cases, fixed at the source (wall depth from mesh bounds or PropDef size). Its facing fix landed as 2ffe55e, with V's nudges | The first-person hands (ADR-0045, TD-172–175): the owner found them flat, mitt-like and holding tools wrong. Starts from session 2's npc_build gloves and hands, now on the integration branch |

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
| The Corvane Field Lab (Y) | integrator | `corvane_field_lab.json` with its notes, loot, keys and items, `props_lab.py` with its catalog and `data/props/lab.json`, the `lab_signs` atlas, `test_field_lab.gd`, its pool entry, ADR-0046 |
| Fidelity round (Z) | integrator | the generators, textures and materials of the assets it upgrades, the impostor bake, the town biome paint in `terrain_composer.gd` (TD-136); small reported hunks in shaders, vegetation (session 3's threading rules), `ambience_director.gd`, biomes and species data |
| Wilderness set pieces, round 3 (X) | integrator | its four building JSONs (Camp Tamarack, Elk Ridge Lodge, the Cordon Quarantine Camp, the Haldane Place) with their notes, loot and keys, its new props family, `test_wilderness_round_three.gd`, and its four entries in the wilderness pool of `world_gen.json` |
| The Corvane caves (ADR-0044) | session 2 | the cave POI, its data, keys, lights and the sight rule; the `buried` level hunk in `game/src/world/terrain/terrain_holes.gd` (agreed with session 3, which owns the file); D6's region data for the adit; no edits in `game/src/worldgen/**` |
| Wall-mounted prop offsets | session 4 | the wall-mount math in `PoiBuilder._prop_xf` and `poi_layout.gd`, wall-depth data on prop defs, and a validator check for wall gaps. Session 3 owns the rest of PoiBuilder; keep hunks small and report them |
| First-person hands (ADR-0045), after the offsets | session 4 | `game/src/player/viewmodel.gd`'s arms and hold poses, the first-person arms generator (`character_fp_arms.py`) and its catalog entries; session 2's npc_build library is shared (additive hunks, reported) |
| Builds, stability and streaming | session 3 | `.github/workflows/` (new export jobs), `game/export_presets.cfg`, the load sequence (`game/src/app/game_world.gd`, `world_loader.gd`, `PoiManager`'s placement path, `PoiBuilder.build`'s validator argument), RegionStreamer and Phase 3's PoiRegistry, `terrain_holes.gd`, thread-safety fixes in `game/src/world/terrain/` and `game/src/world/vegetation/`, and fixes it reports to the hub |

## Allocations
* ADR: 0026 (vault, S2), 0027 (wildlife, S2), 0031 (random worlds), 0032 (pool, if needed),
  0033 (weather), 0034 (hounds and Murmurs, S2), 0035 (base building, S2), 0036–0037 (session 3),
  0038 (streamed worlds: the hub creates it, session 3 adds its phases), 0039 (traders and
  contracts, S2), 0040 (organic towns, the hub), 0041 (new biomes, the hub), 0042 (wilderness
  set pieces, the hub, if needed), 0043 (session 4, if needed), 0044 (the Corvane caves, S2),
  0045 (first-person hands, session 4, if needed), 0046 (the field lab, the hub), 0047 (agent Z, if
  needed). Next free: 0048.
* TD: S2 094–101, 111–114, 141–148, 162–169 (caves) and 170–171 (the quartermaster's face, NPC
  notes); session 3 102–109 and 126–130; session 4 159–161 and 172–175 (hands); the hub 110,
  115–125, 131–140, 149–158 (agents W and X), 176–180 (agent Y) and 181–185 (agent Z), then 186 up.
* Save version: 6 since random worlds. Traders add `world.traders` and `players[*].contracts`
  without a bump (both load empty from older saves). 7 is reserved for session 3's world bundle
  (RWG v2 Phase 4), which carries those keys through. Anyone else who needs a bump asks the hub
  first.

## Queue (in order)
1. Done: random worlds v1 and v2 (organic towns), weather, the pool buildings (two rounds), the third
   block, hounds and Murmurs, base building, the playable builds and downloads, the "how to play"
   guide, trader posts in generated worlds, traders and contracts, the streamed load (behind
   `stream`), and every crash and freeze the owner has hit: the probe atlas for good (parked
   probes, 8625cbe), the digging crash, the Windows load freeze (71d68d3).
2. Running now:
   * the hub's agent X: finishing round 3's visual QA (the lodge's logs and fieldstone, the camp and
     homestead renders);
   * the hub's agent Y's field lab renders, reviewed by the hub;
   * the hub's agent Z: a fidelity round on what the player sees most (impostors, wildlife fur, town
     ground in random worlds, the fen close up, buildings);
   * session 2: the Corvane caves (ADR-0044), the Larkspur adit in D6;
   * session 3: verifying the merged Windows build, then Phase 3 (PoiRegistry with frame lots);
   * session 4: wall-mounted props flush to their walls, then the first-person hands (ADR-0045).
3. The hub: W landed (TD-149..153); every generated model the checkout lacked is built (113). Next
   after X, Y and Z: the M3 base tech (farming, rain catchers, traps, electricity) or more pool
   dungeons, and a `mine` wilderness site once session 2's adit lands.
4. Session 3, in this order:
   * Phase 3 (PoiRegistry with frame lots; TD-137: today every building of every town is built at
     load);
   * TD-003, the 60 FPS pass, profiled in a build (a Pell's Crossing walk and a Hum night);
   * Phase 4's save side (v7, the world bundle); then the New Game cap lifts past 7;
   * graphics options (ADR-0037).
   It keeps `make tour` clean throughout, and adds the trader post to the tour.
5. Session 2: the caves land, then the Ashen (camps, scouts, raids, fear of fire).
6. Session 4: the hands land; then ask the hub.
7. Later, unassigned: companion Ezra Vane; main-map regions D7 (Waystation 9's surroundings) and E6
   (Mile 12); perk capstones, the forge and the chemistry bench.

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
