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

No two runs look alike (ADR-0030): every building is **dressed per run** from the world seed
(furniture broken or missing, lights out, grime and marks, scatter), authors give rooms
[alternatives](#alternatives-different-every-run) picked per run, and ordinary houses and shops on
lots without a pick are [generated](#generated-buildings) from templates.

## Coordinates
* Plan cell = **1 m**. Column = x (→), row = z (↓). Row 0 is the **back**, the last row the
  **front**; the building's front faces **+Z** (toward the street when placed).
* `origin: [x, z]` offsets the plan inside the lot `footprint: [w, d]` (yard space around it).
* Level `L` floor top is at `floor_height + L × 3.0` (default `floor_height` 0.6 with a porch,
  use 0.15 for slab-on-grade shops). Level −1 is a cellar.
* A level below ground may say `"buried": true` (ADR-0044): it runs on under the ground beyond the
  building (a mine level, a cave). Only its cells under a ground-floor room cut the terrain; the rest
  lie under the hillside. Give the region feature a `size` to level only the surface buildings, and
  keep at least a storey of ground over buried cells (TD-164). Example: `corvane_larkspur_adit`.
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
`"alternatives": [...]` (optional) varies the building per run: see
[Alternatives](#alternatives-different-every-run).

`"population": "clinic"` (optional) dresses the building's Hollowed as the people who were there
(`game/data/populations/`, ADR-0028): the clinic's patients, St. Ansel's congregation, a Cordon
crew. A sleeper entry may name its own `population` (a nurse among the patients); a region names
one for its open ground with `"population"` in `region.json`.

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
| `roof` | defaults for every roof of the building, `{"type": "gable", "axis": "x"|"z", "pitch": 32, "overhang": 0.45, "material": "...", "parapet": 0.6, "roofs": [...]}`: the planner roofs each part where it sits, `roofs` overrides a part (see [Roofs](#roofs)) |
| `porch` | `{"side": "S", "from": 1, "to": 8, "depth": 2, "steps": [4]}` (deck along a side, steps at columns) |
| `chimney` | `[col, row]` |

Wall finishes (texture-array order is fixed in `data/materials/kit_finishes.json`):
`plaster_white, plaster_grey, paint_mustard, paint_sage, paint_slate_blue, wallpaper_floral_rose,
wallpaper_stripe_green, wallpaper_damask_brown, wood_paneling_dark, tile_bathroom_white,
tile_kitchen_check, siding_white, siding_pale_blue, siding_barn_red, brick_red, concrete_block,
rock_drift, rock_limestone, log_chinked` (the two rock walls also serve as ceilings; they never peel;
`log_chinked` is bark-on logs with lime chinking for a log building's exterior and gables, weathered as an
exterior finish).
Floor finishes: `wood_oak, wood_pine, carpet_brown, carpet_blue_worn, linoleum_check,
linoleum_beige, tile_white_small, concrete, rock_floor, cave_mud`.

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
* A room may rise two or three storeys: `"storeys": 2` on its lowest level and `^` in the plans
  above wherever it rises; `"open_roof": true` leaves out its ceiling and `"gallery"` sets the
  railing of the rooms that look over it (see [Tall rooms](#tall-rooms-galleries-and-open-roofs)).
  Room keys: `name, type, wall, floor, ceiling, open_to, storeys, open_roof, gallery`.
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
  along the wall (east for N/S walls, south for E/W walls). Two storeys high, on a tall room's wall
  ([Tall rooms](#tall-rooms-galleries-and-open-roofs)): `lancet` (pointed church window),
  `window_tall` (1 m) and `door2_tall` (2 m barn or bay doors).
* `state`: `closed`, `open`, `locked` (needs `key` item — place it as a pickup), `locked_inside`
  (bolted: only opens from the cell it was authored on — the classic **shortcut**), `broken`,
  `barricaded` (door + boards, or `"barricade": "furniture"` for an inside furniture pile),
  `boarded` (window boards), `missing`. A `broken` door's leaf hangs open off its top hinge (its
  smashed model, or the whole leaf where the kit has none), at an angle fixed per door, with no
  collision; a door smashed in play swings there. The leaf of any door swings to the wall's "a"
  (south / east) face, or to the other one when only that face is a stair flight.
* Exterior doorways (`door*`, `open`) on the ground floor whose sill is more than 0.2 m above the
  yard (the pad, or the porch deck where it covers the threshold) get steps up to them, out from the
  foundation with a ramp under it (PoiBuilder.stoops): a concrete stoop with a landing on a brick,
  block or rock building, wooden steps on any other, 1-3 steps by the rise, 2 m wide at a double
  door (PoiBuilder.stoop_piece). Keep the metre outside such a doorway clear of yard props (1.5 m
  for a concrete stoop of two or three steps).
* Where a barricade stands: boards go on the face the door is approached from (outside on an
  exterior wall; on an interior wall the side reachable without passing through it, as for lock
  cues — whoever nailed them sealed the room behind), a furniture pile inside on an exterior wall
  and on the wall's "a" (south/east) side on an interior one. `"barricade_on": "H"` puts it in that
  room instead (`"."` = outside), e.g. boards nailed on the hall side of a cellar door the player
  first reaches from the cellar.
* Doors take an optional `"model": "door_metal"`, `"hp"` and `"lock"` (see [Locks](#locks)).
* Windows the route climbs in by get route cues; `"cue"` overrides them on any opening (see
  [Route cues on windows](#route-cues-on-windows)).

### stairs, ladders, holes
* `{"level": 0, "at": [6, 5], "dir": "N"}` — a straight flight occupying 4 cells from `at` toward
  `dir`, arriving on level+1 at the 5th cell. The builder opens the upper floor over the flight
  (and over a ladder's hatch): keep sleepers, props, pickups and traps off those cells upstairs
  (validator error).
* The flight's collision is a ramp rising 0.75 m a cell from its foot edge, and the player steps up
  only 0.38 m, so (player report 3; validator):
  * a flight is entered at its foot: from the cell behind it, or from a side of the first step
    along its low half. Doorways belong on the foot's back edge or off the flight: one beside a
    step past the first is an error, one beside the first step a warning;
  * upstairs, a doorway onto the well is an error except at the head (between the last step's well
    and the landing); a gallery railing is left out across the head;
  * no wall across a flight, between its head and its landing, or upstairs over its second step or
    higher (headroom); a door there is the way off the top;
  * the route never stands on the steps past the foot or over the well (put waypoints beside them).
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
* `against` pushes the prop's back flush to that wall of its cell (1 cm off its face) and faces it
  into the room (`N` 0, `E` −90, `S` 180, `W` 90); a `rot` of its own overrides that facing. Name
  the cell **next to** the wall: `against` on a cell whose side has no wall leaves the prop standing
  in the room (the validator says so). How far the back is from the model's origin is the
  PropDef's `back` (default: 0 for a `wall_mounted` prop, whose origin is on the wall plane; half
  its depth for the rest), so a wall cabinet hangs on the wall, not half its depth out.
* A wall-mounted prop placed by hand with `pos` hangs on the wall behind it: put its origin on the
  wall's face (half a wall, 0.08 m, off the wall's line, plus 1 cm). One hung on something that is
  not a building wall (a counter's front, a canopy, a sign leant on a sawhorse) takes
  `"wall_ok": true`.
* Containers come from the PropDef (`container`) or an override; loot is rolled on first search
  from the container's table at the POI tier (+1 and a second roll in the **loot room**).
* `key` on a locked container (safe, weapons locker) names the key item.
* Light props shine only when `"lit": true` (power is out; survivors left candles and lanterns).
* `y` lifts a prop above its floor: the level's floor indoors and on the porch deck, the pad
  (ground) for level-0 props on yard cells off the porch. Yard pickups, bear traps and floor decals
  stand on the pad too; wall-mounted props hang at `height` above the building's floor wherever
  they are. A negative `y` sinks a prop under the pad: Larch Pond Bait & Boat's docks and piles
  stand in the pond that its `keep_water` placement leaves under it (ADR-0024).
* **Shell props** stand in for walls and roofs the kit can't build (bark, pole and sod huts, a
  park-model trailer, a fee station): one prop modelled as the walls and roof, with openings where
  the plan's doors are, wrapped round a small kit room under `"roof": {"type": "none"}` (the Ashen
  watch camp, Tamsin River Campground; TD-051).
* **Collision** is the PropDef's: one box of its `size` (`collision` box, convex or mesh alike;
  none for `"none"`), standing on the origin (forward off the wall plane for a wall-mounted prop).
  A shell or a structure whose size box would close a doorway, fill a gate or stand in the air
  lists **`boxes`** instead (TD-270): `[{"size": [x, y, z], "at": [x, y, z], "yaw": 0}]`, each a
  box in the prop's own frame (Godot axes: +X right, +Y up, +Z the prop's front; origin the
  model's origin), `at` the centre of its **base** (`[0, 0, 0]` is a box standing on the origin)
  and the optional `yaw` (degrees) turning it about its vertical axis as a placement's `rot` turns
  a prop. They replace the size box (the size still drives the validator's footprints: corridor,
  stairwell and wall checks). `boxes` implies `"collision": "box"` (leave it out or say "box";
  "none", "convex" or "mesh" with boxes is an error), sizes must be positive and unknown keys are
  errors. Every box is tagged with the prop's id, so TraversalAudit names it; the validator's
  yard cuts and sleeper placement use the boxes too. Read the prop's generator for the geometry
  (a fuselage's skin beside its kit walls, with the kit doors' gaps; a tower's legs; a gate's
  posts; a boxcar's walls round its door) and run the traversal audit on the POIs that use it.

### people and things
* `sleepers`: `{"id": "s1", "at": [5, 2], "enemy": "hollow", "pose": "lie|sit|stand|kneel|crouch", "rot": 90, "group": "pantry", "guardian": false}`
  — dormant until noise, light or a careless approach wakes them (spawned within ~45 m). `id` is
  **required** (their dead/alive state is keyed by it). `group` puts the sleeper in an ambush
  ([Ambushes](#ambushes-sleeper-groups-and-triggers)); `guardian` makes it the loot room's
  keeper ([Guardians](#guardians)). `sit` and `lie` sleepers land on the nearest free seat or bed;
  `"anchor"` pins or opts out ([Seats and beds](#seats-and-beds)).
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
* Each trigger fires **once per POI instance**; it is saved. One fired while nobody is near (the
  Hum broke the door) is spent all the same, and its group comes back awake
  ([The Hollowed on traps](#the-hollowed-on-traps)). After a reload a spent ambush stays spent:
  survivors are ordinary sleepers. Several triggers may wake one group (two doors into the same room); a later
  one only wakes members still asleep.
* An alarm the player sets off wakes every sleeper in the building and spends every ambush.
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
| `shotgun` | edge `{"at", "side"}`: `at` is the room the gun is in | a tripwire across the doorway at shin height and a sawn-off lashed to a chair beside it, aimed back along the wire: a spread of pellets that walls and the first body stop, falling off with distance, bleeding, a gunshot (heat; wakes ambushers within 14 m). Disarm on the wire: cordage + scrap |
| `creaky_floor` | cell `{"at", "size": [w, d]?}` | loose boards: every stride groans loudly (crouch-walk: barely a creak); the first loud groan counts as the trap firing. They groan under the Hollowed too: a warning only |
| `weak_floor` | cell `{"at", "level"}` with a **room directly below** | rotten sagging boards: 0.5 s after the player (or a Rammer or Husk) steps on them they give way → a one-way drop hole, for good |
| `alarm` | edge `{"at", "side", "style"?}` | battery door/window alarm on the frame (or `"style": "bell"`: a bell on a cord across an open passage, the default for openings that are open). Opening/breaking the opening or walking through sets it off: rings 20 s; set off by the player it wakes **every** sleeper in the building (by a Hollowed it only rings), keeps making noise and heat the horde hears. Use it while ringing to smash it quiet; disarm it crouched before |

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

## Dungeon life: seats, beds, the Hollowed on traps, window cues
ADR-0022. The building's furniture, its traps and its windows tell the story too.

### Seats and beds
A `sit` sleeper sits on the nearest free **seat** and a `lie` sleeper lies on the nearest free
**bed**, within 1.6 m of where it is authored on its level. It is posed at the furniture's height,
facing the way the seat faces (head to feet along a bed), and when it wakes it gets up off it
before it hunts. Put the sleeper roughly where it sits; the plan in `make poi-preview` draws a line
from the authored spot to the seat it took. With nothing free in reach it stays on the floor, and
the validator warns.

| props with anchors | seats | beds |
|---|---|---|
| chairs (`kitchen_chair`, `chair_wood`, `office_chair`, `civic_folding_chair`, `armchair`, `recliner`, `road_wheelchair`, `out_camp_chair`) | 1 | |
| `civic_pew` 4, `couch` 3 (or one lying), `diner_booth` 2, `road_waiting_chairs` 3, `bench_park` 2, `picnic_table` 4, `wild_mess_bench` 3 each way | yes | |
| stools (`diner_stool`, `civic_bar_stool`), `crate_wood`, `civic_beer_crates` (hunched, any way round), `toilet` | 1 | |
| `bed_double`, `road_motel_bed`, `farm_quilt_bed`, `mattress_dirty` | (mattress: 2 sat legs out) | 2 |
| `bed_single`, `out_hide_bed`, `civic_army_cot` and `wild_cot_canvas` (plus one sat on the rail), `sleeping_bag` (or sat up in it), `wild_bunk_steel` (lower and upper) | | 1–2 |
| `bathtub` | 1, sat legs out | |

* `"anchor": "floor"` keeps a `sit`/`lie` sleeper on the floor (a Dragger, a body in the rubble,
  someone slumped in an aisle) and silences the warning. Decide for every one: the validator warns
  about each `sit`/`lie` sleeper that lands on nothing without it.
* `"anchor": "<prop id>"` pins it to that prop (within 3.2 m). An error if no such prop has that
  kind of anchor.
* `rot` picks among close choices (a bench or crate seats either way: give the sitter the facing
  you want).
* Each anchor holds one body, close anchors of one prop exclude each other, and a couch holds
  sitters or one lying body.
* Not used: destroyed props, props stacked on something (`"y"`), anchors with something standing on
  them (the crate under a crate, a lamp on the mattress), and seats whose sitter's feet would be in
  a wall, outside or over a stair well.
* The getting-up spot is in front of a seat (else behind it or out to a side), beside a bed (else
  past its foot): leave a body's width free there.
* A sitter may be authored in its seat's cell: the validator warns about a sitter sharing a cell
  with a prop only when it lands on no seat.
* A new seat or bed prop gets `"anchors"` in its def:
  `{"kind": "seat", "pos": [x, z], "height": 0.46, "facing": 0, "lean": "back|forward|low"}`
  (prop-local, under the pelvis; `facing` in degrees from the prop's front; `lean` `forward` for
  backless seats, `low` for sitting legs out).

### The Hollowed on traps
The Hollowed set traps off too, by weight (`data/config/traps.json` `hollowed`): Draggers are
light, Husks and Rammers heavy, the rest in between.

| trap | set off by a Hollowed | then |
|---|---|---|
| `can_chime`, `bear_trap`, `shotgun` | any | as for the player (the jaws and the pellets hurt them) |
| `alarm` | any | it rings; the ringing wakes who hears it (a held ambush only within 14 m); it does not rouse the whole building |
| `creaky_floor` | any | it groans for the player to hear (something walking about upstairs); nothing else: the trap and its ambush stay armed |
| `weak_floor` | heavy only | it gives way; they fall to the room below hurt, and stop pathing over the hole |

A trap a Hollowed sets off fires its `trap` triggers (except the creaky floor) and makes its noise
for the sleepers to hear; only the player's own misstep alerts the sleepers near at once.

With nobody near, a trigger that fires (the Hum breaking a door) is spent and its group is
**roused**, and a trap a Hollowed trips rouses the sleepers that would have heard it. Roused
sleepers are saved, and the next time the player comes they are up and about, off their seats and
beds, heading for where it happened. Plan for it: an ambush on a door the Hum likes to break may be
spent before the player ever gets there.

### Route cues on windows
A window the validated route climbs in through from outside reads from the street: a torn curtain
dragged out over the sill (open, broken or missing windows only), a crate under it to climb on (two
if the sill is high), muddy boot scuffs up the wall and a handprint on the sill. Any opening can ask
for its own with `"cue"`: one of `curtain`, `crate`, `scuffs`, `light` (a lantern left burning on
the inside sill: the window glows at night, one per building), a list of them, or `"none"`.

```json
{"id": "kitchen_window", "at": [6, 0], "side": "N", "type": "window", "state": "broken", "cue": ["curtain", "light"]},
{"id": "bath_window", "at": [2, 4], "side": "W", "type": "window", "state": "broken", "cue": "none"}
```
The validator errors on unknown kinds and warns about a cue on an interior wall or a curtain in a
shut window. Defaults: `data/config/traps.json` `route_cues`.

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
0. (ADR-0030) Alternatives are well formed, and every option and combination passes 1–7 below and
   keeps the base's shortcuts and keyed doors usable; generated buildings pass all of it with no
   warnings.
1. The route is completable start to finish, also once every weak floor has given way; the loot room
   is reachable and has a container; no fall strands the player.
2. Sleepers stand in rooms, not on stairs or inside furniture, and are reachable. Nothing (sleeper,
   prop, pickup, cell trap, or the `at` cell of a chime or shotgun) stands on the open well a stair
   flight or ladder hatch leaves in the level above: there is no floor there. Wall-mounted props,
   props raised 0.5 m or more with `y` (a ceiling lamp), and props tagged `stairwell` (a railing, a
   ladder) are the exception.
3. Props stay inside rooms and off the route corridor (`"route_ok": true` to allow). Every wall
   prop (wall-mounted, or `against` a wall) has its back within 5 cm of a wall's face (a gallery
   railing counts), as the builder places it (`"wall_ok": true` to skip; test_poi_wall_gaps.gd).
4. The plan fits the footprint; lights ≤ 10, sleepers ≤ 14, kit pieces ≤ 2600 (override in `budget`).
5. Every prop/enemy/item/note id exists.
6. Sleepers, traps and triggers have unique ids (containers and pickups should); trap types, keys
   and placement are valid; triggers name real rooms/openings/pickups/containers/traps and wake a
   group that has sleepers; locks sit on doors.
7. Every `^` has a tall room under it with enough `storeys`; nothing stands, lands or is cut in a
   void; tall openings have a wall above them; gallery edges carry only gaps and breaches, and no
   drop strands the player; `style.roof` keys and its `roofs` overrides are valid.

## Story first
Write the `story` before the plan. Every room should say something about it: the barricade that
faces the wrong way, the note in the fridge, the child's room the parents never opened. Then
design the **route** as a sequence of beats (approach → blocked → detour → ambush → payoff →
shortcut out) and only then lay out rooms around it.

## Alternatives: different every run
ADR-0030. A building keeps its plan, its route and its story, but each run picks how it is dressed.
Give the def an `"alternatives"` list of groups; each group has weighted options and one is picked
per run from the world seed (each group from its own stream):

```json
"alternatives": [
  {"id": "back_bedroom", "label": "What the back bedroom is now",
   "options": [
     {"id": "bedroom", "weight": 2},
     {"id": "nursery", "rooms": [{"room": "C", "name": "Nursery", "wall": "wallpaper_floral_rose", "floor": "carpet_blue_worn"}]},
     {"id": "study", "rooms": [{"room": "C", "name": "Study", "type": "office", "wall": "wood_paneling_dark"}]}]},
  {"id": "doors", "options": [
     {"id": "as_left", "weight": 2},
     {"id": "kicked_in", "openings": [{"id": "bedroom_door", "state": "broken"}]}]}
],
"props": [
  {"id": "back_bed", "prop": "bed_double", "at": [11, 6], "against": "E", "alt": "back_bedroom:bedroom"},
  {"prop": "crib", "at": [7, 3], "against": "W", "alt": "back_bedroom:nursery"},
  {"id": "study_desk", "prop": "desk_small", "at": [7, 0], "against": "N", "alt": ["back_bedroom:study", "back_bedroom:nursery"]}
]
```
* **Groups**: `id, label?, options` (two or more). **Options**: `id, label?, weight` (default 1, 0 =
  never), `default` (the authored option; else the first), and what it changes:
  * `rooms`: `[{"level", "room", ...}]` with `name, type, wall, floor, ceiling, open_to` (the
    room's purpose and finish);
  * `openings`: `[{"id", ...}]` with `state, key, lock, barricade, barricade_on, cue, model, hp`
    (locked, barricaded, broken open, boarded);
  * `style`: `exterior, interior, floor, ceiling, decay, damaged_walls, prop_condition, scatter,
    lights_on`.
* **`"alt": "group:option"`** (or a list) on any entry of `props, sleepers, traps, triggers,
  pickups, notes, lights, decals, openings`: it exists only when that option is picked. Use it for
  furniture sets, alternative sleeper spots and groups (one sleeper `id` may stand in different
  places in different options; its dead state follows it), alternative trap spots, an extra
  sleeper in an ambush, a knocked-through doorway.
* Never: plans, `storeys`, `open_roof`, `gallery`, roofs. Walls, cellars and the terrain cut must
  not move between runs (make a second def for a different plan).
* **The default is the authored building.** A content def compiles as its defaults. When you
  retrofit a shipped building, tag its existing entries with the default option where they are
  and append the new ones at the end of each list: the default resolution must stay identical to
  the old layout (legacy saves, the builder's draw order and unnamed props' keys depend on it).
* **Validated in full.** `make validate` validates every option changed alone from the defaults,
  then every full combination (a deterministic sample of 16 beyond the singles when there are
  more). Each must keep the route, the loot room, sleepers and triggers valid, and every shortcut
  and locked door the base can use must stay usable. Messages carry the picks:
  `merrow_house: [alt doors=kicked_in, neighbour=both] ...`.
* Keep the story true in every combination: vary what the story leaves open (which window, who sat
  where, the wallpaper), not what it says.
* `make poi-preview POI="merrow_house" POI_ARGS="--seed 7"` shows the building as the run with
  world seed 7 dresses it (picks printed, files suffixed `_s7`).

### Per-run wear
Without anything authored, a run also wears every building (`PoiDressing._wear`): furniture without
an authored `variant` may be broken or gone (decay-scaled; never containers, props with an `id`,
seats and beds, lit props, wall-mounted or stacked props and what they stand on, `route_ok` debris
or the yard), lights and `"lit"` props burn with `style.lights_on` (default 0.7; `"keep": true`
pins one on), and the builder adds grime, stains, mould, cracks, marks and blood decals and draws
its scatter from the run. Give a prop an `id` or a `variant` to keep it as authored.

## Generated buildings
ADR-0030. Ordinary houses, shops and workshops are generated from **templates**
(`game/data/pois/templates/*.json`, `BuildingTemplateDef`) by `BuildingGenerator`: a template and a
seed always give the same validated building, plan to roof.

```json
{"id": "bungalow", "name": "Bungalow", "archetype": "house", "zoning": ["residential"], "tier": 1, "weight": 3,
 "width": [9, 13], "depth": [7, 10], "storeys": 1, "porch": 0.6, "floor_height": 0.6, "setback": [4, 7],
 "decay": [0.22, 0.55], "sleepers": [2, 3], "chimney": 0.45,
 "exteriors": ["siding_white", "siding_pale_blue", "brick_red"],
 "roofs": [{"type": "gable", "pitch": [22, 34], "weight": 3}, {"type": "hip", "pitch": [20, 28]}],
 "roof_materials": ["roof_shingle", "roof_cedar"],
 "finishes": {"living": {"wall": ["wallpaper_damask_brown", "wood_paneling_dark"], "floor": ["wood_oak"]}},
 "names": ["The {family} House"], "stories": ["The {family}s bolted the front door and went out the back."]}
```
| key | meaning |
|---|---|
| `archetype` | `house` (a hall front to back between a day side and a night side), `duplex` (two units, the party wall knocked through), `store` (sales floor, stock room, office, restroom), `workshop` (bay, office, tool crib) |
| `zoning`, `tier`, `weight` | which lots may draw it, and how often among the candidates |
| `width`, `depth` | plan size ranges (cells; x along the street) |
| `storeys`, `upper` | 1 or 2; `"cape"` sets the upper floor back from the front (a storey and a half; the front rooms get a lean-to) |
| `porch`, `chimney` | chances |
| `floor_height`, `setback` | 0.6 porch house / 0.15 slab; front yard depth range (m) |
| `decay`, `sleepers` | ranges |
| `exteriors`, `roofs`, `roof_materials`, `finishes` | drawn per building (`finishes` per room purpose: `living, kitchen, bedroom, kids, nursery, bath, dining, study, office, storage, utility, store, garage, hallway`) |
| `names`, `stories` | patterns; `{family}` draws from `data/config/building_generator.json` |

Every generated building is a tier-1 dungeon-lite: a bolted front door (the shortcut out), a way in
round the side or back (the back door, a smashed window, a clawed hole), the loot room with a small
ambush on its door, a gentle trap (loose boards, jaws under the way in, a can chime), modest loot,
fences, a mailbox and yard junk. The generator validates what it makes and retries until the
validator reports nothing; `make validate` and `tests/unit/test_building_generator.gd` (50 seeds a
template) prove it. Preview one with `make poi-preview POI="gen:bungalow:12"`.

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

Lot keys: `id, rect, zoning, facing, pick, tags`, and (ADR-0030) `tier` (`[lo, hi]` or a number,
else the framework's `tier_range`), `pool` (`any`, `authored`, `generated`), `templates` (template
ids it may generate; naming them makes the pool `generated` unless `pool` says otherwise) and `reserved` (a note: the lot stays empty for a building still to come). A
lot **without a `pick`** holds what `LotPicker` chooses from the world seed: an authored building
zoned and tiered for it that fits and is not already standing in this framework, or a generated
building from a template zoned for it (filling the lot). Larch Street in Pell's Crossing is six
such lots; the school, fire station and bank lots on its corner are `reserved`.

**Pool buildings.** An authored building with no fixed placement is still in every lot's pool when
its zoning, tier and footprint fit (DESIGN §11 "Pool buildings": the laundromat, grocery, lumber
yard, library and radio station only random towns place). Size a pool building for the random
generator's lots (`data/config/world_gen.json` `tuning.towns.lot`: commercial 28 x 32, civic
32 x 32, industrial 26 x 26 on the back street), keep its notes free of a town's name, and give it
alternatives so two runs don't meet the same set piece. Leave a zoning off when a framework's
generated lots must not draw it (Larch Street is residential, so none of the five is).

**Organic towns (random worlds v2, ADR-0040).** A generated town's lots are **frame lots**:
`"frame": [cx, cz, w, d, yaw]` in world XZ, a rectangle stood along its street (its front is the
frame's local +Z, toward the street; `w` is the frontage, `d` the depth), with the graded pad's
height in `y`. `LotPicker.lot_size` reads the frame and `lot_local_xf` stands the building in it,
footprint centred, front to the street, so author the front of a pool building on its `+Z` side as
usual. Its authored buildings are **capped world-wide**: the generator gives each authored building
to at most `tuning.towns.authored_max` towns of one world (3) and writes each town's share into
its framework's `authored` list; an organic town's lots choose authored buildings from that list
only, and fill the rest from templates. So a big world shows each set piece a few times, not on
every street. Rect lots (`rect`, the handcrafted frameworks and v1 towns) are unchanged.

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

## Tall rooms, galleries and open roofs
ADR-0021. A room can rise two or three storeys: a church nave, a barn's threshing bay, a saw floor,
a hall open to its rafters, a school gym, a fire station's apparatus bay.

```json
"levels": [
  {"level": 0,
   "plan": [
     "BBBBBBBBOOOO",
     "BBBBBBBBOOOO",
     "BBBBBBBBKKKK",
     "BBBBBBBBKKKK"],
   "rooms": {
     "B": {"name": "Apparatus bay", "type": "garage", "storeys": 2, "wall": "concrete_block", "floor": "concrete"},
     "O": {"name": "Watch office", "type": "office"},
     "K": {"name": "Kitchen", "type": "kitchen"}}},
  {"level": 1,
   "plan": [
     "^^^^^^^^DDDD",
     "^^^^^^^^DDDD",
     "^^^^^^^^MMMM",
     "^^^^^^^^MMMM"],
   "rooms": {
     "D": {"name": "Bunk room", "type": "bedroom", "gallery": false},
     "M": {"name": "Hose loft", "type": "storage", "gallery": "rail"}}}],
"openings": [
  {"id": "bay_door_a", "at": [1, 3], "side": "S", "type": "door2_tall", "state": "closed"},
  {"id": "bay_door_b", "at": [5, 3], "side": "S", "type": "door2_tall", "state": "broken"},
  {"id": "loft_gap", "at": [8, 3], "side": "W", "type": "open", "level": 1}]
```
* `"storeys": 2` (or 3) goes on the room at its lowest level; the plans above hold `^` wherever it
  rises (any shape: leave cells for a gallery, a loft or a bell chamber). A `^` with no tall room
  under it, or above the room's `storeys`, is an error; a tall room with no `^` over it stays one
  storey (warning).
* The tall room has no floor or ceiling between its storeys: its walls rise through the void (a
  20 cm `wall_band_1m` closes the gap where a floor slab would sit, inside and out, so the finish,
  siding and trims run on unbroken), and its ceiling is at its top storey. Authored lights without
  a `height` and `ceiling_mounted` fixtures without a `y` hang from that ceiling.
* `"open_roof": true` on any room whose top is under the roof (tall or not: a hayloft) leaves out
  its ceiling: it sees the roof's boards, rafters, ridge beam, wall plates and collar ties, and the
  walls between it and closed rooms beside it rise to the roof.
* An upper room beside the void looks over it from a **gallery**: a fascia over its floor's edge
  and a waist-high railing the player and the Hollowed can't walk through. `"gallery": "balustrade"`
  (the default: turned balusters and a moulded rail), `"rail"` (two rough timber rails, for barns
  and mills) or `false` (a wall instead: the bunk room above).
* On a gallery edge only `open` (a gap in the railing) and `breach` (a broken one) are allowed.
  Both are **one-way drops** onto the tall room's floor for the route, so a gap in a hayloft rail is
  a valid shortcut down; the validator errors when a drop strands the player. A passable opening
  in a wall onto the void (a door out of a `"gallery": false` room) drops the same way.
* A stairwell (the hole a flight comes up through) beside the void gets no railing or fascia on
  that edge, and the flight's banister is then the only guard: keep stairwells off the gallery
  edge (TD-042).
* Tall openings stand on the lower storey of a tall room's wall and fill the storey above it,
  which must be a wall with nothing else on it: `lancet`, `window_tall` (a 1 m sash 2.5 m high:
  gyms, mills, halls), `door2_tall` (2 m wide, 3.5 m high, a pair of board-and-batten barn doors).
  There is no roll-up or sectional bay door and nothing wider yet (TD-041): use two `door2_tall`s.
* Nothing stands in the void: sleepers, pickups, cell traps, route waypoints, stair landings,
  holes, props (except wall-mounted ones, `stairwell` props and props raised 0.5 m with `y`). Put
  them on the tall room's floor, at its level.
* In game the volume is one room: room triggers, shelter, indoor checks and reverb answer for its
  floor wherever the player is in it. The Hollowed walk its floor and do not follow a drop: they go
  round by the stairs (TD-042).
* Interior light needs nothing authored: every building gets a reflection probe per rectangle of
  rooms of one height (8 at most), so a tall room and each wing of an L are lit as rooms and a yard
  inside an L stays outdoors.
* A school gym: a `hall` two storeys tall with `open_roof`, `window_tall` along both long walls, a
  balustrade gallery on the side the bleachers or the stage are on. A fire station: the bay above,
  `door2_tall` doors on the apron side and a flat roof behind a parapet (`"type": "flat"` in
  `style.roof`, or a `roofs` override on the bay's wing: `commercial` zoning flattens only the
  annexes).

## Roofs
`RoofPlanner` roofs the building's massing; `style.roof` holds the building's defaults and
`roofs` overrides single parts of it:

```json
"roof": {"type": "gable", "axis": "x", "pitch": 38, "overhang": 0.5, "material": "roof_shingle_brown",
         "roofs": [{"level": 3, "at": [6, 20], "type": "flat", "parapet": 0.45},
                   {"level": 0, "at": [2, 9], "type": "shed", "slope": "S", "pitch": 18}]}
```
The tops of the building (every built cell with nothing built above it, a tall room's void
included) are split level by level into rectangles, largest first. Each is a **wing**, roofed at
its own height:

| wing | what | roof by default |
|---|---|---|
| main | the largest part of a level | the style's `type`, ridge along `axis` (else the long side) |
| leg | a part of the same height beside a larger one (an L, T or U) | a gable whose ridge runs into the main roof (cross gables meeting in valleys), or that stops against the gable end it abuts |
| annex | a lower part against a taller wall | a lean-to sloping away when up to 4.5 m deep, an abutting gable when deeper, a flat roof behind a parapet on `commercial` and `industrial` buildings |
| tower | a top of 8 × 8 cells or less with nothing of its height beside it, standing over lower parts of the building (a small two-storey house on its own is a main) | hip; a tower rising through a bigger roof (a belfry) leaves that roof whole around it |

* Types: `gable`, `hip`, `shed` (a lean-to; `"slope"` names its low side), `flat` (a membrane
  behind a parapet on the outside walls, `"parapet"` m), `pyramid`, `spire` (an octagonal broach
  spire with a cross, `"height"` m) and `none`.
* A `roofs` entry names its wing by `"level"` (the roof's level: the highest storey built at that
  cell) and `"at"`, any cell of the wing. It may set `type, axis, pitch, overhang, slope, material,
  color, flat_material, flat_color, parapet, gutters, gable_finish, height`. An entry that names no
  wing, an unknown key and an unknown type are errors.
* An annex roof is pitched down until its top stays 25 cm under the lowest sill of the wall it
  leans on (or 35 cm under that wall's top), and turns into a lean-to, then a flat roof, when that
  gets too flat. Keep windows off a wall a lower roof leans on: the Okafor farmhouse moved the two
  east windows its kitchen ell covers to the back wall.
* Pitched roofs keep the ADR-0019 trims: fascia under the eaves, rake boards, capped ridges and
  hips, gutters (`"gutters": false` for cabins and sheds). Gable ends wear the exterior finish
  (`"gable_finish"` overrides it).
* Check roofs from every side with `make poi-preview POI=<id>`.
