# Workboard — who is doing what, across sessions

The integrator session keeps this file. Other sessions read it after merging the integration
branch `claude/amazing-davinci-60axfh` and send changes as messages; they don't edit it. That way
it never conflicts.

**Round 4 (2026-10-08).** Round 3's hub and its four workers are gone, and with them every message
they sent. A new hub took over from git alone. It merged everything round 3 had pushed past its last
integration (98a01ea): session 3's caves work in progress (ADR-0056 WS-A..D), session 2's Ezra
phases 2-3 and Bloom nests in the encounter scatter, and session 5's forest set pieces round 5 with
compound collision (generator VERSION 11). Session 5's round-5 debt was renumbered TD-314..317 (it
had collided with session 2's TD-304..307). Session 4's branch had nothing unmerged. The old
integration branches `claude/compassionate-dirac-8mtvxi` (891830b) and `ccr-24ba8b7d-fttoi8`
(98a01ea) are frozen, and so are the old worker branches: integrate into
`claude/amazing-davinci-60axfh`.

## Sessions
| Session | Branch | Role | Now | Next |
|---|---|---|---|---|
| Hub `session_01PzJeyHzavtYrZ7JLbVLmHS` | `claude/amazing-davinci-60axfh` (integration) | Reviews and merges every branch; the verification gate (import, check, validate, test, smoke, tour on every merge); goldens; this file; delegates | Round 3's leftovers merged (00cada1, 73a4f14, 475fcc6); full verification of the merged tree | Its own stream with agents: report 4 item 6 (interior routes, invisible ladders) |
| World `session_01JuE8Bvz1jodvFsrJzgkFw2` | `claude/hollowmere-r4-world` | Terrain, worldgen, towns, caves, streaming, performance, saves, builds | Report 4 items 4 and 5: roads level across their width, no long slanted cut faces, planted town edges with trees, bigger towns laid out off a single straight road | The organic caves (ADR-0056, docs/CAVES_PLAN.md WS-C..F); TD-279; TD-003 with a full Hum; TD-196/197; graphics options (ADR-0037) |
| Creatures `session_013NwRPQ1PsMRu5iFyZAajxk` | `claude/hollowmere-r4-creatures` | The Hollowed, characters, hands and combat feel | Report 4 item 1: the hands and wrists, idle and holding every item (the lighter first) | The Hollowed look and behaviour (TD-192, TD-027, TD-011); the Ashen phase 2 remainder (TD-190); Ezra follow-ups (TD-299..313) |
| Presentation `session_01B5YS2wWu8LLN1zPzXL88vP` | `claude/hollowmere-r4-presentation` | Menus, HUD and UI, the intro, cinematics | Report 4 item 7 (crafting and inventory readability), then items 3 (main menu styled like the game's other menus, a cinematic camera behind it) and 2 (the intro cutscene) | The rest of TD-014 (drag and drop, tooltips, the tether map); a UI pass over every screen for one style |

## Protocol
* **Talk to the hub.** Use the `send_message` tool of the Claude Code Remote MCP server, with
  session_id `session_01PzJeyHzavtYrZ7JLbVLmHS`. Message it when you start a stream, when a stream
  lands (with commit hashes), when you're blocked, and before you touch a file outside your
  ownership below. The hub relays what the other worker needs to know.
* **Talk to each other.** Message the other worker directly for a shared file, an interface you
  need from them, or a second opinion; copy the hub in one line. Ask for a review of anything that
  crosses into the other's area (a cave rule the Hollowed follow, a new AI cost in a perf budget).
  Answer a peer's question before you start your next task.
* **Never duplicate.** Before starting anything not listed under your name, ask the hub; it checks
  this board and the other branch. When your queue runs thin, ask the hub for the next task rather
  than picking one.
* **Commit and push often.** A container can be reclaimed at any time, and with it everything
  uncommitted. Rounds 1 and 3 lost work that way. Push a commit at least every hour of work, and
  before you end a turn. A WIP commit on your own branch is fine.
* **Branches.** Push only to your own branch; never rebase or force-push. Merge the integration
  branch into yours about hourly and before you tell the hub something landed. The hub merges your
  branch into the integration branch after running the full gate.
* **Ownership.** A file belongs to the stream listed below until that stream lands. Outside your
  own files, make only small additive hunks, and say so in your status. Never revert someone
  else's change.
* **Numbers.** Use only the ADR and TD numbers allocated to you below. Generator VERSION and save
  version: bump only right after merging the integration branch, from what's there, and tell the
  hub first.
* **Toolchain.** A fresh container has none. `make setup-godot && python3
  tools/setup/vendor_gut.py && git checkout game/addons/gut`, then `make import`, is enough for
  check, validate and test (the import takes ~10-15 min the first time, without generated assets).
  Add `make setup` and `make assets` (about 2.5 h the first time) only when you need generated
  models or renders.
* **Subagents.** Work through subagents in git worktrees for independent pieces (one Godot process
  each, one render at a time per container). You review and merge their work into your branch.
* **Status.** End each turn with a short status to the hub: what landed, what's next, blockers.

## Active streams and the files they own
| Stream | Who | Owns |
|---|---|---|
| Terrain and towns (report 4), caves (ADR-0056), perf and builds | World | `game/src/world/terrain/**` (incl. `cave/`, `volume_terrain.gd`, `terrain_holes.gd`, `terrain_manager.gd`, `terrain_composer.gd`), `game/src/worldgen/**` (roads, towns, `rwg_town_planner.gd`, `rwg_generator.gd`), `world_gen.json`, `town_planner.json`, vegetation scatter rules and threading in `game/src/world/vegetation/`, `game/src/ai/nav/nav_tiles.gd`, `game/src/ai/horde/flow_field*` (TD-279), RegionStreamer, PoiRegistry, the load sequence (`game_world.gd`, `world_loader.gd`: Presentation's intro needs a hook there, agreed by message), `game/src/core/save/`, `.github/workflows/`, `export_presets.cfg`, perf tooling, `data/config/caves.json`, `docs/CAVES_PLAN.md` |
| Hands, the Hollowed and combat feel | Creatures | `game/src/ai/` except `nav/nav_tiles.gd` and the horde flow field (window NavigationLink3Ds go in as reported hunks there), enemy and character generators (`char_body`, `character_fp_arms.py`, `npc_build`), `game/src/player/viewmodel*.gd`, equipment and combat, `game/src/companion/` (Ezra), Ashen AI and data, `data/enemies/` |
| Interiors and ladders | Hub | `game/src/poi/**` (except PoiRegistry), `game/data/pois/**`, `game/data/props/**`, prop generators, `poi_walk`/TraversalAudit, encounters (`game/src/world/encounters/`) |
| Menus, UI and the intro | Presentation | `game/src/ui/**` (main menu, New Game, options, salvage roll, field manual, HUD, theme), `game/src/app/main*` and the menu scene, the intro (new `game/src/ui/intro/`, `game/data/intro/`), UI fonts and theme resources; a load-sequence hook for the intro agreed with World by message |

## Allocations
* ADR: 0001..0058 are taken or retired (0032, 0042, 0043 were never written). 0056 (organic caves,
  World), 0059 (World: roads and towns, if needed), 0060-0061 (Creatures), 0062 (hub), 0063-0064
  (Presentation: the intro, the menu and UI style). Next free: 0065.
* TD: the register runs to TD-317. World 318-337, Creatures 338-357, the hub 358-377,
  Presentation 378-397. Next free: 398.
* Generator: `RwgGenerator.VERSION` is 11. World owns the generator this round and bumps it as it
  needs (re-record test_composer_golden with `SLOW_TESTS=1`), telling the hub each time.
* Save version: 7. Anyone who needs a bump asks the hub first.

## Queue (in order)
1. Done through round 3: everything in rounds 1 and 2; the forest encounters (ADR-0054), forest set
   pieces rounds 4 and 5 (ADR-0053), wolves and Bloom nests (ADR-0055), hunting and ranged with
   climbing (ADR-0057), Ezra Vane phases 1-3 (ADR-0058), traps and electricity (ADR-0052), farming
   (ADR-0049), the Ashen phase 1-2 (ADR-0048), interior light (ADR-0050), POI traversal (ADR-0051),
   save v7; every item of player report 3.
2. World: report 4 items 4 and 5 (terrain and towns), then caves to ADR-0056 (merge points M1..M4
   in docs/CAVES_PLAN.md), then TD-279, TD-003, TD-196/197, ADR-0037. It keeps `make tour` and
   `make smoke` clean throughout.
3. Creatures: report 4 item 1 (hands and wrists), then the Hollowed look and behaviour, then the
   Ashen and Ezra follow-ups.
4. Presentation: report 4 item 7 (crafting and inventory), item 3 (the main menu and its
   cinematic camera), item 2 (the intro cutscene); then TD-014 and a one-style pass over every
   screen.
5. Hub: merge gate; report 4 item 6 (interior routes, invisible ladders); then main-map regions D7
   and E6, perk capstones, the forge and the chemistry bench.
6. Needs the owner (a GPU and a human): the M1 playthrough, 60 FPS on target hardware, feel and
   balance (HANDOFF.md "Not verified yet").

## The owner's priorities (2026-10-07, after Builds #68/#75: "much better so far")
1. **The Hollowed: look and behaviour.** They seemed passive until you're close (c619133 now has
   them notice at 25-40 m, see in the dark and call each other; TD-192 has what the look pass
   left). Creatures.
2. **POI navigation and placement**: doorways blocked, items lying in the way, and "climb up"
   spots that use an interact instead of a ladder or a jump. Round 3 landed TraversalAudit and many
   fixes (ADR-0051); the hub finishes it.
3. **Hands: looks and animations with every tool and weapon.** Round 3 landed oblique grips, joint
   helper bones and per-finger curls (TD-173..175). Creatures.

## Player report 4 (2026-10-08, the owner, round 4's start)
Two screenshots (described here; they came in chat): a forest walk with both hands idle, and the
lighter held up.
1. **Hands still look primitive.** Idle, both hands are loose fists with the wrists bent hard down
   and in, so the backs of the hands face the camera like paddles; the fingers read as smooth
   sausages with flat nails and no knuckle definition. Holding the lighter, the hand is a flat
   pinch: four straight fingers stacked on the lighter's side, the thumb laid along its top, the
   wrist cocked down at the strap. Both read unnatural. (Creatures, first.)
2. **An intro cutscene** that gives the crash and its context before the start. It should play
   while the world loads, but only if it doesn't stutter or freeze (the load does heavy main-thread
   steps); otherwise it plays after the load, before control. (Presentation, with World for the load hook.)
3. **The intro and main menu look primitive** and unlike the rest of the game's menus. A slow
   panning cinematic camera over the world behind the main menu, as long as it doesn't stutter or
   cost performance. (Presentation.)
4. **Terrain anomalies**: roads allowed to run on a cross-slope (tilted sideways); long, slanted
   faces of rock and road (cut and fill faces stretched over long runs); the ground round towns
   obvious, with very little grass or plants and no trees at all. (World.)
5. **Towns should be bigger** and laid out less linearly: today they are often one straight
   stretch of road. (World.)
6. **Interiors**: validate that every intended route can be walked fully and intuitively;
   **ladders appear invisible** for some reason. (Hub.)
7. **The crafting menu and inventory need work**: recipes that can't be crafted show in white and
   are almost impossible to read. (Presentation.)

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
6. **Axe grip** (`docs/playtest/2026-10-06_build67_axe_dark_room.webp`): the fingers don't wrap
   the handle (knuckles show as dots on it) and the off hand floats open, palm down. (Session 4.)
7. **Interiors still too dark**: a block-walled room is near black apart from the doorway, even by
   day. Possibly probes still queued or parked, SDFGI not reaching indoors, or the indoor light
   (instance light_lit, lit props) too weak. (Session 5.)
8. **Stairs that push against a door or need a jump** are still in places. Not a save artifact:
   saves store only differences, so buildings are rebuilt from current data on every load, and
   ab89797's validator check was already in Build #67, so it misses some cases (generated
   buildings? step rise or collision?). (The hub's doors agent.)

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
