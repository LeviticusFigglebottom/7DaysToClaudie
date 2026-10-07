# Debug tools

Available in debug builds (and exports with the `debug_tools` feature). Implemented in
`game/src/debug/debug_overlay.gd`; flags live on the `DebugTools` autoload.

| Key | Tool |
|---|---|
| **F1** | Debug menu: spawn Hollow/Lurcher/Keener/Dragger or a pack, kill nearby; give kits (axe+hammer, logs, building materials, revolver, food, bandages); time (+1 h, +6 h, dawn/noon/dusk/midnight, start/end the Hum, time ×10); weather presets; teleports (drop site, Pell's Crossing, Okafor farm, pond, cliffs, bridge); toggles (god mode, invisible to Hollowed, no hunger); quicksave/screenshot; **seed viewer** (world seed, region, biome/surface/vegetation at your feet, terrain hash, placements, clock, heat) |
| **F2** | Free camera (WASD, mouse, Shift = fast, E/Q = up/down); terrain streams around the camera |
| **F3** | AI overlay: per-Hollowed label (type, state, hp, awareness), line to its current target, Hum flow-field arrows around the base, heat-map cells |
| **F4** | Performance overlay: FPS/frame time vs the 60 FPS budget, draw calls, primitives, objects, video/static memory, node count, physics/process time, Hollowed alive, graphics preset; in a streamed world the StreamMeter's minute (longest frame and the step kinds in it, late seconds, worst step kind and its max ms, steps queued) |
| **F6** | POI route visualiser: the validator's walked route (green), numbered waypoints with labels, loot-room cells, validation errors floating over the building, and the dungeon mechanics (ADR-0018): **sleepers** labelled `zz [group held] enemy` in their ambush group's colour (`G` = guardian, orange; ungrouped = pale blue; `held` while their trigger has not fired); **triggers** `T id -> group (enter K / open door / take key / search locker / trap id)` over what they watch, room triggers crossing every cell of their room, grey and `(fired)` once spent; **traps** in magenta (a bar across edge traps, crosses over cell traps) with `type id (armed / sprung / disarmed)`, greyed once sprung or disarmed |
| **F7** | Structural view: stability % and hit points over every building piece within 40 m |
| F5 / F9 | Quicksave / quickload · F12 screenshot (user://) |

Headless tools (see the Makefile): `make smoke` (end-to-end slice run), `make validate`
(content + POIs), `make check` (compile every script), `make test`, `compose_region.gd`
(terrain inspection images in build/region_preview). `exterior_qa.gd` renders the moon's phases,
the Route 9 bridge, light props lit and destroyed, and the Program drone (ADR-0023; its header
has the command line).

`make poi-preview POI="id ..." [POI_ARGS="..."]` renders layout QA images into build/poi_preview
(`--out DIR` elsewhere). The cut-away plans (`<id>_plan_L<n>.png`) show the dungeon (ADR-0022):
* **Sleepers** where they spawn, in their ambush group's colour with the group's name (ungrouped:
  pale blue; guardians ringed orange). Standing, kneeling and crouched sleepers are discs, seated
  ones a disc on their seat, lying ones a body-long capsule head to feet. Each has a tick for its
  facing and a thin line back to its authored spot when a seat or bed moved it.
* **Triggers** in their group's colour, linked to the group and labelled `T id`: a room trigger
  tints its cells, an opening trigger is a diamond on the edge, and a pickup, container or trap
  trigger is a ring.
* **Traps** in magenta: bars across edge traps, squares on cell traps.
* **Route-cue windows** as white bars with their cue kinds.
* **The route and the rest:** the validator's route path (green), waypoints (cyan), pickups
  (yellow-green), lights (orange), and props at their true size (gold = container, blue = solid,
  grey = no collision).

`--sleepers [sid,sid]` spawns the sleepers and shoots a close view of each seated or lying one
(`<id>_sleeper_<sid>.png`). `--no-exterior` / `--no-plans` / `--inside` choose the other views.

## POI walk: the player body through every building

`make poi-walk POI="merrow_house lot:pell_crossing:larch_1"` (or `POI_ARGS="--all --pool --generated 3"`)
runs `poi_walk.gd` headless (`godot --headless --fixed-fps 60 --path game -s
res://src/tools/cli/poi_walk.gd -- [--poi id[,id]] [--all] [--pool] [--generated N] [--seed N]
[--out DIR] [--plan] [--verbose]`). Ids are POI ids, `gen:<template>:<seed>` and
`lot:<framework>:<lot>` (what a run with `--seed`, default 4471, stands on that lot; `--pool` is
every lot of every framework, `--generated N` seeds 1..N of every template). Each building is
dressed for the run, built with PoiBuilder on a bare flat pad (open over its cellars), and the real
Player scene, in god mode, walks it with the move action: the route's waypoints in order, then
every room the layout reaches. Legs are planned over the validator's graph (doors, stairs, ladders,
holes, keys) but round props, under stair flights and over stairwells only when nothing else gets
there; the body steers through doorway middles and up stair lines, opens doors as a player does
(from beside the leaf's swing, closing an open leaf that is in its way), and only when it stalls
presses Jump (the player's own vault, else a jump), backs off, then crouches. It teleports only to
restart after a leg it could not finish. Per building it prints, and writes to
`build/poi_walk/<id>.json`:
* **blocked**: legs the body could not finish, by category (doorway, climb, window, drop,
  entrance, floor), with the collider in the way: a door leaf (opening, state, how far open), a
  barricade, a container or authored prop (prop id, its `id` / list key), a wall edge (and the
  opening on it), or a shell box (size, and how high it rises over the feet), with its node path
  and POI-local cell. `[no way round the props]` means the plan had to go through props.
* **needed**: legs on plain floor, a doorway or stairs that took a jump, a vault or a crouch
  (window and half-wall vaults are expected and not listed); **ladder** climbs (an interact).
  A window whose sill is past the vault's 1.3 m from the ground is climbed from a prop under it
  (a route-cue crate or any solid top within 1.5 m of the window, at most 1.0 m up): the body
  jumps onto it and vaults in from its top, and the leg is listed here as `crate` with
  `"assist": "crate"` and `"assist_prop"` in the JSON (the table's `crate` column counts them).
  The same goes for a prop standing under a window on the body's side, in the yard or in the room
  (a booth table under a diner window: climbed, then over the sill or ducked through when the sill
  is about level with its top), and for landing on a prop on the far side (`"landed_prop"`).
  With no such prop a high-sill leg stays blocked, its note giving the sill height.
* **unreached** rooms (the layout reaches them, the body never stood in them) and **sealed** rooms
  (the layout itself has no way in).
* **corridor props**: collision boxes standing in a walk-through doorway's clear width or in the
  middle of a validated route cell (static, from the layout).
The exit code is the number of buildings with blocked legs or unreached rooms. `--plan` prints
each building's compiled plan, openings, stairs and ladders first (generated buildings have no
JSON); `POI_WALK_DEBUG=1` prints the jumps, door handling and give-ups. Not modelled: terrain
(the pad is flat), sleepers (none are spawned), weak floors giving way, locked doors without
their key on the route.
