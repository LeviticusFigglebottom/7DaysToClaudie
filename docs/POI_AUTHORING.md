# POI authoring guide

Buildings are **data**: one JSON file per POI in `game/data/pois/buildings/`, compiled by
`PoiLayout` (`game/src/poi/poi_layout.gd`), checked by `PoiValidator`, and assembled from the
generated kit (`docs/POI_KIT.md`) by `PoiBuilder`. Towns are **frameworks** in
`game/data/pois/frameworks/`: lots, streets and fixtures that pick buildings. The handcrafted map
places frameworks/POIs as region features; RWG (M3) will use the same frameworks with random picks.

```
make validate          # content + every POI (route, loot room, sleepers, footprint, budget)
make test              # includes tests/unit/test_poi_*.gd
F6 in game             # route visualiser: route, sleepers, loot room for nearby POIs
```

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
  "props": [...], "sleepers": [...], "pickups": [...], "notes": [...], "traps": [...],
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
  storage, garage, basement, diner, pharmacy, cells, loft`.

### openings (on walls)
`{"id": "front_door", "at": [3, 7], "side": "S", "type": "door", "state": "closed", "key": "", "level": 0}`
* `type`: `door`, `door2` (2 m double), `window`, `window2` (2 m), `breach` (passable hole),
  `open` (no wall), `half` (1 m pony wall, vaultable). 2 m openings span this cell and the next one
  along the wall (east for N/S walls, south for E/W walls).
* `state`: `closed`, `open`, `locked` (needs `key` item — place it as a pickup), `locked_inside`
  (bolted: only opens from the cell it was authored on — the classic **shortcut**), `broken`,
  `barricaded` (door + boards, or `"barricade": "furniture"` for an inside furniture pile),
  `boarded` (window boards), `missing`.
* Doors take an optional `"model": "door_metal"` and `"hp"`.

### stairs, ladders, holes
* `{"level": 0, "at": [6, 5], "dir": "N"}` — a straight flight occupying 4 cells from `at` toward
  `dir`, arriving on level+1 at the 5th cell. The builder opens the upper floor over the flight.
* `{"level": 0, "at": [2, 2], "side": "W", "hatch": true}` — ladder against a wall up through a
  hatch in the ceiling (climb by interacting). Hollowed do not climb ladders: lofts are refuges.
* `{"level": 1, "at": [4, 3]}` — broken floor: a one-way drop to the level below.

### props
`{"prop": "fridge_old", "at": [1, 0], "against": "N", "variant": "worn", "container": "fridge", "lit": false, "y": 0.0}`
* `against` pushes the prop's back flush to that wall of its cell and faces it into the room.
* Containers come from the PropDef (`container`) or an override; loot is rolled on first search
  from the container's table at the POI tier (+1 and a second roll in the **loot room**).
* `key` on a locked container (safe, weapons locker) names the key item.
* Light props shine only when `"lit": true` (power is out; survivors left candles and lanterns).

### people and things
* `sleepers`: `{"id": "s1", "at": [5, 2], "enemy": "hollow", "pose": "lie|sit|stand|kneel|crouch", "rot": 90}`
  — dormant until noise, light or a careless approach wakes them (spawned within ~45 m).
* `pickups`: `{"id": "k1", "item": "pharmacy_key", "at": [2, 1], "y": 0.9}` (keys, schematics, journals).
* `notes`: `{"note": "merrow_fridge", "at": [1, 0], "y": 1.2}` → the readable item `note_<id>`.
* `traps`: `{"id": "chime1", "type": "can_chime", "at": [4, 6], "side": "S"}` — trip line across that
  edge; rattles loudly and wakes nearby sleepers.
* `lights`: `{"at": [3, 3], "height": 0.9, "color": "#ffbb77", "energy": 0.8, "range": 5, "flicker": 0.3, "shadow": false}`.
* `decals`: `{"decal": "blood_splatter_a", "at": [2, 3], "side": "N", "height": 1.2, "size": [1.2, 1.0]}`
  (`"side": "floor"` for floor decals). Ids (textures `decal_<id>_albedo.png`): `blood_splatter_a..d`,
  `blood_pool`, `blood_drip`, `blood_trail`, `blood_handprint`, `mold_patch`, `scorch`, `crack_wall`,
  `bullet_holes`, `footprints_mud`, `grime_streaks`, `water_stain`, `survivor_marks_a..c`.

### route, loot room, shortcuts
* `route`: ordered waypoints `{"at": [c, r], "level": 0, "label": "Front door barricaded"}`. The
  first waypoint should be outside (a `.` cell) at the intended entrance. The validator walks the
  graph waypoint to waypoint: doors (not barricaded), breaches, open/broken windows, stairs, ladders
  and drop holes count; keys count once their pickup is reachable. Intact glass and barricades do
  **not** count — the intended route must not require breaking things unless you add a breach.
* `loot_room`: `{"room": "C", "level": -1}` — must be reachable and contain a container.
* `shortcuts`: `[{"opening": "back_door"}]` — a `locked_inside` door from the loot side back out.

## Checklist (enforced by the validator)
1. The route is completable start to finish; the loot room is reachable and has a container.
2. Sleepers stand in rooms, not on stairs or inside furniture, and are reachable.
3. Props stay inside rooms and off the route corridor (`"route_ok": true` to allow).
4. The plan fits the footprint; lights ≤ 10, sleepers ≤ 14, kit pieces ≤ 2600 (override in `budget`).
5. Every prop/enemy/item/note id exists.

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
