# POI authoring guide

Buildings are **data**: one JSON file per POI in `game/data/pois/buildings/`, compiled by
`PoiLayout` (`game/src/poi/poi_layout.gd`), checked by `PoiValidator`, and assembled from the
generated kit (`docs/POI_KIT.md`) by `PoiBuilder`. Towns are **frameworks** in
`game/data/pois/frameworks/`: lots, streets and fixtures that pick buildings. The handcrafted map
places frameworks/POIs as region features; RWG (M3) will use the same frameworks with random picks.

```
make validate          # content + every POI (route, loot room, sleepers, footprint, budget)
make test              # includes tests/unit/test_poi_*.gd
F6 in game             # route visualiser: route, sleepers + groups, loot room, triggers, traps
```

Buildings are 7 Days to Die-style **dungeons** (ADR-0018): sleepers in ambush groups woken by
triggers, traps a careless player springs, lock cues on doors, a guardian on the loot. See
[Ambushes](#ambushes-sleeper-groups-and-triggers), [Traps](#traps), [Locks](#locks) and
[Designing a dungeon](#designing-a-dungeon).

## Coordinates
* Plan cell = **1 m**. Column = x (→), row = z (↓). Row 0 is the **back**, the last row the
  **front**; the building's front faces **+Z** (toward the street when placed).
* `origin: [x, z]` offsets the plan inside the lot `footprint: [w, d]` (yard space around it).
* Level `L` floor top is at `floor_height + L × 3.0` (default `floor_height` 0.6 with a porch,
  use 0.15 for slab-on-grade shops). Level −1 is a cellar.
* Sides: `N` (−z, back), `E` (+x), `S` (+z, front), `W` (−x).
* Placed things use `"at": [col, row]` = centre of that cell (+ optional `"offset": [dx, dz]` m),
  or `"pos": [x, z]` = exact plan position in metres. `"level"` defaults to 0; `"rot"` is degrees
  (0 = facing +Z / the front).

## File skeleton
```json
{
  "id": "merrow_house", "name": "The Merrow House", "tier": 1, "zoning": ["residential"],
  "footprint": [16, 18], "origin": [3, 4], "author": "...", "story": "One paragraph: what happened here.",
  "style": {...}, "levels": [...], "openings": [...], "stairs": [...], "ladders": [...], "holes": [...],
  "props": [...], "sleepers": [...], "pickups": [...], "notes": [...], "traps": [...], "triggers": [...],
  "lights": [...], "decals": [...], "route": [...], "loot_room": {...}, "shortcuts": [...], "budget": {...}
}
```

### style
| key | meaning |
|---|---|
| `exterior` | wall finish on the outside faces (`siding_white`, `siding_pale_blue`, `siding_barn_red`, `brick_red`, `concrete_block`) |
| `interior` / `floor` / `ceiling` | defaults for rooms without their own |
| `floor_height` | ground-floor height above the pad (0.15 slab, 0.6 porch house) |
| `decay` | 0..1 stains/mould/grime (default 0.25 + 0.1 × tier) |
| `damaged_walls` | chance an interior wall uses `wall_1m_damaged` |
| `prop_condition` | default prop variant: `clean` / `worn` / `destroyed` |
| `scatter` | `{"density": 0.35}` — room-appropriate clutter along walls, never on the route |
| `roof` | `{"type": "gable"|"flat", "axis": "x"|"z", "pitch": 32, "overhang": 0.45, "material": "...", "parapet": 0.6}` |
| `porch` | `{"side": "S", "from": 1, "to": 8, "depth": 2, "steps": [4]}` (deck along a side, steps at columns) |
| `chimney` | `[col, row]` |

Wall finishes (texture-array order is fixed in `data/materials/kit_finishes.json`):
`plaster_white, plaster_grey, paint_mustard, paint_sage, paint_slate_blue, wallpaper_floral_rose,
wallpaper_stripe_green, wallpaper_damask_brown, wood_paneling_dark, tile_bathroom_white,
tile_kitchen_check, siding_white, siding_pale_blue, siding_barn_red, brick_red, concrete_block`.
Floor finishes: `wood_oak, wood_pine, carpet_brown, carpet_blue_worn, linoleum_check,
linoleum_beige, tile_white_small, concrete`.

### levels
```json
{"level": 0,
 "plan": [
   "KKKKBBBB",
   "KKKKBBBB",
   "LLLLHHHH",
   "LLLLHHHH"],
 "rooms": {
   "K": {"name": "Kitchen", "type": "kitchen", "wall": "tile_kitchen_check", "floor": "linoleum_check"},
   "L": {"name": "Living room", "type": "living", "wall": "wallpaper_stripe_green", "floor": "wood_oak", "open_to": "H"},
   "H": {"name": "Hall", "type": "hallway"}, "B": {"name": "Bedroom", "type": "bedroom"}}}
```
* Each character is one cell: a room letter, `.` = yard (outside), space = nothing.
* Walls are generated automatically on every edge between different rooms and between a room
  and the outside. `"open_to": "HD"` removes walls to those rooms (open plan).
* Room `type` drives clutter and ambience: `kitchen, living, bedroom, bath, hallway, office, store,
  storage, garage, basement, diner, pharmacy, cells, loft, church, bar, post_office, hall, cellar`.
  Scatter clutter comes from props whose `rooms` tags match; `PoiBuilder.ROOM_TAGS` maps types
  without their own tag (bath → bathroom, storage → basement/garage/store, pharmacy →
  store/office, cells → office/basement, loft → basement/garage) and widens others (church →
  church/living, bar → bar/diner/kitchen, post_office → post_office/office/store, hall →
  hall/living/office, cellar → cellar/basement).

### openings (on walls)
`{"id": "front_door", "at": [3, 7], "side": "S", "type": "door", "state": "closed", "key": "", "level": 0}`
* `type`: `door`, `door2` (2 m double), `window`, `window2` (2 m), `breach` (passable hole),
  `open` (no wall), `half` (1 m pony wall, vaultable). 2 m openings span this cell and the next one
  along the wall (east for N/S walls, south for E/W walls).
* `state`: `closed`, `open`, `locked` (needs `key` item — place it as a pickup), `locked_inside`
  (bolted: only opens from the cell it was authored on — the classic **shortcut**), `broken`,
  `barricaded` (door + boards, or `"barricade": "furniture"` for an inside furniture pile),
  `boarded` (window boards), `missing`.
* Where a barricade stands: boards go on the face the door is approached from (outside on an
  exterior wall; on an interior wall the side reachable without passing through it, as for lock
  cues — whoever nailed them sealed the room behind), a furniture pile inside on an exterior wall
  and on the wall's "a" (south/east) side on an interior one. `"barricade_on": "H"` puts it in that
  room instead (`"."` = outside), e.g. boards nailed on the hall side of a cellar door the player
  first reaches from the cellar.
* Doors take an optional `"model": "door_metal"`, `"hp"` and `"lock"` (see [Locks](#locks)).

### stairs, ladders, holes
* `{"level": 0, "at": [6, 5], "dir": "N"}` — a straight flight occupying 4 cells from `at` toward
  `dir`, arriving on level+1 at the 5th cell. The builder opens the upper floor over the flight
  (and over a ladder's hatch): keep sleepers, props, pickups and traps off those cells upstairs
  (validator error).
* `{"level": 0, "at": [2, 2], "side": "W", "hatch": true}` — ladder against a wall up through a
  hatch in the ceiling (climb by interacting). Climbers step off upstairs onto the room cell beside
  the hatch, away from the wall (or to either side); the validator errors if there is none.
  Hollowed do not climb ladders: lofts are refuges.
* `{"level": 1, "at": [4, 3]}` — broken floor: a one-way drop to the level below.

### props
`{"id": "kitchen_fridge", "prop": "fridge_old", "at": [1, 0], "against": "N", "variant": "worn", "container": "fridge", "lit": false, "y": 0.0}`
* `id` (lower_snake_case, not a number, unique in the POI): **give every container one** — its
  saved loot state is keyed by it (`c:<instance>:<id>`; without it, by list position, which a later
  edit can scramble — the validator warns). Container triggers name props by it.
* `against` pushes the prop's back flush to that wall of its cell and faces it into the room.
* Containers come from the PropDef (`container`) or an override; loot is rolled on first search
  from the container's table at the POI tier (+1 and a second roll in the **loot room**).
* `key` on a locked container (safe, weapons locker) names the key item.
* Light props shine only when `"lit": true` (power is out; survivors left candles and lanterns).
* `y` lifts a prop above its floor: the level's floor indoors and on the porch deck, the pad
  (ground) for level-0 props on yard cells off the porch. Yard pickups, bear traps and floor decals
  stand on the pad too; wall-mounted props hang at `height` above the building's floor wherever
  they are.

### people and things
* `sleepers`: `{"id": "s1", "at": [5, 2], "enemy": "hollow", "pose": "lie|sit|stand|kneel|crouch", "rot": 90, "group": "pantry", "guardian": false}`
  — dormant until noise, light or a careless approach wakes them (spawned within ~45 m). `id` is
  **required** (their dead/alive state is keyed by it). `group` puts the sleeper in an ambush
  ([Ambushes](#ambushes-sleeper-groups-and-triggers)); `guardian` makes it the loot room's
  keeper ([Guardians](#guardians)).
* `pickups`: `{"id": "k1", "item": "pharmacy_key", "at": [2, 1], "y": 0.9}` (keys, schematics, journals).
  Give pickups an `id` (taken-state key; pickup triggers name it).
* `notes`: `{"note": "merrow_fridge", "at": [1, 0], "y": 1.2}` → the readable item `note_<id>`
  (keyed `note_<note id>`).
* `traps`: see [Traps](#traps). `id` is **required**.
* `triggers`: see [Ambushes](#ambushes-sleeper-groups-and-triggers).
* `lights`: `{"at": [3, 3], "height": 0.9, "color": "#ffbb77", "energy": 0.8, "range": 5, "flicker": 0.3, "shadow": false}`.
* `decals`: `{"decal": "blood_splatter_a", "at": [2, 3], "side": "N", "height": 1.2, "size": [1.2, 1.0]}`
  (`"side": "floor"` for floor decals). Ids (textures `decal_<id>_albedo.png`): `blood_splatter_a..d`,
  `blood_pool`, `blood_drip`, `blood_trail`, `blood_handprint`, `mold_patch`, `scorch`, `crack_wall`,
  `bullet_holes`, `footprints_mud`, `grime_streaks`, `water_stain`, `survivor_marks_a..c`.

### route, loot room, shortcuts
* `route`: ordered waypoints `{"at": [c, r], "level": 0, "label": "Front door barricaded"}`. The
  first waypoint should be outside (a `.` cell) at the intended entrance. The validator walks the
  graph waypoint to waypoint: doors (not barricaded), breaches, open/broken windows (the player
  vaults sills up to 1.3 m with Jump; Hollowed don't vault yet), stairs, ladders
  and drop holes count; keys count once their pickup is reachable. Intact glass and barricades do
  **not** count — the intended route must not require breaking things unless you add a breach.
* `loot_room`: `{"room": "C", "level": -1}` — must be reachable and contain a container.
* `shortcuts`: `[{"opening": "back_door"}]` — a `locked_inside` door from the loot side back out.

## Ambushes: sleeper groups and triggers
A sleeper with a `"group"` is **held**: it ignores ordinary noise, light and a player walking past
(and other sleepers waking); only gunfire, an explosion or an alarm within 14 m, or a blow, wakes
it early. A **trigger** of its group wakes the whole group as an ambush: the dormant members get
up one after another, closest first, 0.15–0.6 s apart (after the trigger's `delay`), already
knowing where the player is, under an audible stir. Every group needs at least one trigger.

```json
"sleepers": [
  {"id": "pantry_trucker", "group": "pantry", "pos": [2.4, 1.35], "enemy": "hollow", "pose": "crouch", "rot": 90},
  {"id": "pantry_waitress", "group": "pantry", "pos": [1.4, 3.5], "enemy": "hollow", "pose": "lie"}],
"triggers": [
  {"id": "pantry_door_opened", "group": "pantry", "on": "opening", "opening": "pantry_door", "delay": 0.15}]
```

| `on` | fires when | names |
|---|---|---|
| `room` | the player enters any cell of the room | `"room": "K", "level": 0` |
| `opening` | that door/window/barricade is opened or broken (by anyone) | `"opening": "<opening id>"` |
| `pickup` | that pickup is taken | `"pickup": "<pickup id>"` |
| `container` | the first search of that container prop | `"prop": "<prop id>"` |
| `trap` | that trap goes off | `"trap": "<trap id>"` |

* `delay` (s, default 0) before the first ambusher stirs.
* Each trigger fires **once per POI instance** and only while the building's sleepers are out
  (the player is near); it is saved. After a reload a spent ambush stays spent: survivors are
  ordinary sleepers. Several triggers may wake one group (two doors into the same room); a later
  one only wakes members still asleep.
* An alarm wakes every sleeper in the building and spends every ambush.
* Keys allowed: `id, group, on, room, level, opening, pickup, prop, trap, delay` (others are errors;
  `_`-prefixed keys are comments).

### Guardians
`"guardian": true` on a sleeper in the loot room: it spawns one infected tier up (normal →
Seeded → Bloomed, unless the world setting turns tiers off) and is held until the player enters the
loot room (an implicit trigger) — unless it has its own `group`. The validator warns when a guardian
stands outside the loot room. Sleeper Sense outlines guardians in a warm rim. Put one in tier 2+
loot rooms.

## Traps
All traps need an `id`; their state (armed / sprung / disarmed) is saved. A trap a player spots can
be **disarmed crouched** (interact) for its parts; tuning lives in `data/config/traps.json`.

| `type` | placement | does |
|---|---|---|
| `can_chime` | edge `{"at", "side"}` | trip line across that cell side; rattles loudly (wakes ordinary sleepers near) |
| `bear_trap` | cell `{"at" or "pos", "rot"?}` (rooms, or the yard on level 0) | steel jaws half-hidden in debris: 25 damage, bleeding, holds the player ~2.5 s (Jump to struggle free sooner), a snap that wakes sleepers near; bites Hollowed too. Disarm: 2 scrap metal |
| `shotgun` | edge `{"at", "side"}`: `at` is the room the gun is in | a tripwire across the doorway at shin height and a sawn-off lashed to a chair beside it, aimed back along the wire: heavy damage falling off with distance (cone), bleeding, a gunshot (heat; wakes ambushers within 14 m). Disarm on the wire: cordage + scrap |
| `creaky_floor` | cell `{"at", "size": [w, d]?}` | loose boards: every stride groans loudly (crouch-walk: barely a creak); the first loud groan counts as the trap firing |
| `weak_floor` | cell `{"at", "level"}` with a **room directly below** | rotten sagging boards: 0.5 s after the player steps on them they give way → a one-way drop hole, for good |
| `alarm` | edge `{"at", "side", "style"?}` | battery door/window alarm on the frame (or `"style": "bell"`: a bell on a cord across an open passage, the default for openings that are open). Opening/breaking the opening or walking through sets it off: rings 20 s, wakes **every** sleeper in the building, keeps making noise and heat the horde hears. Use it while ringing to smash it quiet; disarm it crouched before |

```json
"traps": [
  {"id": "barricade_gap_trap", "type": "bear_trap", "pos": [3.6, 7.35], "rot": 0},
  {"id": "evidence_shotgun", "type": "shotgun", "at": [1, 3], "side": "S"},
  {"id": "hall_boards", "type": "creaky_floor", "at": [3, 4], "size": [3, 1]},
  {"id": "loft_rotten_boards", "type": "weak_floor", "at": [10, 2], "level": 1},
  {"id": "dispensary_alarm", "type": "alarm", "at": [9, 5], "side": "S"}]
```
* Edge traps must cross a passable edge (an opening, or two cells of one room) — never a solid wall.
  The alarm box and the shotgun hang on the `at` side: put that on the side the player comes from
  if a careful player should see it in time (alarms), or inside the room (shotguns).
* The shotgun's chair goes into the neighbouring cell along the wall (whichever side has floor), so
  leave that cell free; it is a solid body the player walks round.
* Weak floors: the validator walks the route again with **every weak floor collapsed** (stepping on
  one drops you below) and errors if a waypoint becomes unreachable, and it errors if the room under
  a weak floor has no way back out. Never put one on the only path; use them to punish a shortcut
  or a greedy step toward loot.
* Keys allowed: `id, type, at, pos, offset, side, level, size, rot, style`.

## Locks
Locked doors show what holds them. `locked` doors get a **padlock and hasp** by default, on the
face the door is approached from (the side reachable from outside without passing through it —
where the key is used); `locked_inside` doors get a **sliding bolt** on their inside face (from
outside: "Bolted from the other side"). Override with `"lock"`:

| `lock` | on | cue |
|---|---|---|
| `padlock` | `locked` (default) | hasp + padlock; **60 hp**: melee or bullets break it off (each hit a loud clank) and the door is then just closed |
| `chain` | `locked` | chain between eye bolts in the leaf and the casing, padlocked; **90 hp** |
| `deadbolt` | `locked` | brass keyed deadbolt; cannot be broken off — bash the door (its own hp) |
| `bolt` | `locked_inside` (default) | sliding barrel bolt on the inside |

Breaking a lock is the noisy alternative to the key; the validator's route still requires the key.
Use `deadbolt` on keyless sealed doors that must hold the route, `chain` on shutters and roll-up
doors.

## Designing a dungeon
Write the route as beats, then hang a mechanic on each:
1. **Approach** — the sealed front (barricade, chained shutter) pushes the player round the side.
2. **Tension** — a creaky floor near a sleeper, a bear trap in the gap the player will squeeze
   through, a chime or alarm on the obvious door. Make every trap readable: debris round a bear trap,
   a red LED over a door, a wire glinting at shin height — a careful player should spot it.
3. **Ambush** — a group waiting where the route forces the player in: behind a door they must open
   (`opening`), in the room they must cross (`room`), or around the thing they came for
   (`container`, `pickup`). Two to four sleepers, crouched or lying where they rise between the
   player and the way they came. Leave room to fight (not a 1 m corridor) and a fallback.
4. **Payoff** — the loot room with its guardian; the key that opens it found further in.
5. **Exit** — the bolted shortcut out (`locked_inside` + `shortcuts`).

Tier 1: one ambush, one gentle trap (creaky floor, a visible bear trap). Tier 2: an ambush on the
route, one or two traps, a guardian. Tier 3: layered — a trap that sets off an ambush (`on: trap`),
a shotgun or alarm guarding the loot, a guardian. Never make the route impossible: every trap can be
survived at full health, and the validator checks the weak-floor cases.

## Stable ids
Every stateful piece is saved under its id: sleepers (`dead`), traps, triggers, pickups and
container props (`c:<instance>:<prop id>`). Ids are lower_snake_case and unique in the POI. Once a
POI ships, never reorder its `props`, `sleepers`, `pickups` or `notes` without ids — append instead
(old saves are re-keyed by position the first time they load, ADR-0018).

## Checklist (enforced by the validator)
1. The route is completable start to finish, also once every weak floor has given way; the loot room
   is reachable and has a container; no fall strands the player.
2. Sleepers stand in rooms, not on stairs or inside furniture, and are reachable. Nothing (sleeper,
   prop, pickup, cell trap, or the `at` cell of a chime or shotgun) stands on the open well a stair
   flight or ladder hatch leaves in the level above: there is no floor there. Wall-mounted props,
   props raised 0.5 m or more with `y` (a ceiling lamp), and props tagged `stairwell` (a railing, a
   ladder) are the exception.
3. Props stay inside rooms and off the route corridor (`"route_ok": true` to allow).
4. The plan fits the footprint; lights ≤ 10, sleepers ≤ 14, kit pieces ≤ 2600 (override in `budget`).
5. Every prop/enemy/item/note id exists.
6. Sleepers, traps and triggers have unique ids (containers and pickups should); trap types, keys
   and placement are valid; triggers name real rooms/openings/pickups/containers/traps and wake a
   group that has sleepers; locks sit on doors.

## Story first
Write the `story` before the plan. Every room should say something about it: the barricade that
faces the wrong way, the note in the fridge, the child's room the parents never opened. Then
design the **route** as a sequence of beats (approach → blocked → detour → ambush → payoff →
shortcut out) and only then lay out rooms around it.

## Frameworks
`game/data/pois/frameworks/<id>.json`:
```json
{"id": "pell_crossing", "size": [72, 124], "tier_range": [1, 3],
 "lots": [{"id": "diner", "rect": [44, 6, 26, 22], "zoning": ["commercial"], "facing": "E", "pick": "mile9_diner"}],
 "roads": [{"points": [[0, 60], [72, 60]], "width": 7, "surface": "asphalt"}],
 "fixtures": [{"prop": "street_lamp", "pos": [40, 58], "rot": 0}]}
```
Lot `rect` is `[x, z, w, d]` in framework space; the POI footprint is centred in the lot with its
front toward `facing`. Streets are painted and graded into the terrain by the composer.

## Cellars and terrain
Rooms on level −1 (and below) are cellars. At load the terrain is cut away under them (TD-026):
`TerrainHoles` (`game/src/world/terrain/terrain_holes.gd`) takes every placed POI's below-ground room
cells, merges them into rectangles in world space, and the near terrain meshes (every LOD, skirts
included), the terrain collision (a trimesh in the chunks a cellar touches), the navigation tiles'
ground faces and any SDF volume column handed off over a cellar subtract them exactly. Nothing is
saved: the same placements cut the same holes.
* The cut follows the **outer edges of the level −1 room cells**, which is where the builder stands
  the cellar walls (centred on the edge, 16 cm thick, from the cellar floor to the underside of the
  ground floor), so the edge is always inside a wall and never shows from the yard. Keep every
  cellar cell **under a level-0 room**: a cellar cell under the open yard only gets a ceiling slab
  without collision, and the hole would open to the sky.
* The cellar floor sits `3.0 − floor_height` below the pad (2.4 m for a 0.6 m porch house).
* Ways in: interior stairs (a `"level": -1` flight that lands in a level-0 room), a ladder through a
  hatch (`"level": -1`, the hatch opens in the room above) or a drop hole in a level-0 floor. Stairs
  that surface in the yard are not supported (the landing would hang 0.6 m above the ground).
* `height_at()` still reports the ground surface over a cellar (ADR-0007);
  `TerrainManager.ground_below(pos)` returns the cellar floor for a point inside one and
  `in_cellar(x, z)` says whether the terrain is cut there (`GameWorld.ground_below()` passes it
  through). Everything that "rescues" things it finds under the ground asks `ground_below()`:
  loose items (1.5 m under), Hollowed (3 m under), the spawn drop after a load and spore puddles,
  so a log dropped in a cellar stays there. New code of that kind must do the same.
* Vegetation never grows there (the POI pad's vegetation mask is zero over the whole footprint), and
  far tiles (16 m, past the near square) are not cut: the ground floor hides the terrain anyway.
* Check a cellar with `make poi-preview POI=<id>` (cut-away plan per level) and F6 in game;
  `tests/unit/test_terrain_holes.gd` drops a player through a stairwell into a cellar against real
  physics, and `test_terrain_holes_world.gd` does it end to end on the Okafor farm framework. The
  Okafor farmhouse (`okafor_farmhouse`) is the reference: drop in through a clawed hole, climb out
  through the pantry hatch.
