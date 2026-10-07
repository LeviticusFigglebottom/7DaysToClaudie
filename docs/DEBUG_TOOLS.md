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
| **F8** | Forest encounters (ADR-0054): every planned site within 400 m, a ring the size of its clearing (green when built, grey when planned but not standing), its id, def, kind, distance and state (visited, dead sleepers, taken pickups) |
| F5 / F9 | Quicksave / quickload · F12 screenshot (user://) |

Headless tools (see the Makefile): `make smoke` (end-to-end slice run), `make validate`
(content + POIs), `make check` (compile every script), `make test`, `compose_region.gd`
(terrain inspection images in build/region_preview). `list_encounters.gd -- [--world DIR | --world-seed N [--world-set size=4]] [--region RID | --all]
[--density D] [--spacing S]` lists a region's (or a world's) forest encounters with the planner's time
and a tally per def. `exterior_qa.gd` renders the moon's phases,
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
