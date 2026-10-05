# ADR-0030: Varied interiors: per-run dressing, room alternatives, generated ordinary buildings, lots that pick

**Status**: Accepted · 2026-10

## Context
The product owner asked whether towns have randomized buildings, or at least randomized interiors,
"so every place feels distinct", as in 7 Days to Die. They did not:
* Each of the 22 buildings was one hand-authored layout (ADR-0009), placed once at a fixed spot.
* `PoiBuilder` seeded its set dressing (clutter scatter, wall damage, decal turns) from
  `Ids.hash64("poi:" + instance_id)`, so a building looked the same in every run. Only loot rolls
  and sleepers followed the world seed.
* Framework lots carried zoning for random picks, but `PoiManager._place_framework` skipped every
  lot without an authored `pick`. A random-world generator (ADR-0031, next) needs many distinct
  ordinary buildings per town, and the authored set pieces are too few and too special to repeat.

Constraints: stable piece ids (ADR-0018) and the saved container, trap, door and trigger states
must stay valid within a run; old saves must keep the buildings they were played in; the validator
must still prove every route; cellars cut the terrain from the placements alone (TD-026), so
nothing that varies may change a plan.

## Decision

### 1. Per-run dressing (`PoiDressing`, `PoiManager.dress_for`)
* A placed building is **dressed** before it is compiled: `PoiDressing.resolve(def, picks, dress)`
  returns a plain `PoiDef` whose layout has its alternatives resolved and, for a per-run world, its
  wear applied. Everything downstream (layout, validator, seat plan, route cues, builder, F6) sees
  that one def, so they agree.
* The **dressing seed** is `hash("dress:<world seed>:<placement id>")`: the same seed builds the
  same building, a new run a different-looking one, and two placements of one def differ.
* **Wear** (per run only):
  * Furniture without an authored variant may be broken (≈ decay × 0.3) or missing (≈ decay ×
    0.12, household furniture only).
  * Never touched: containers, anything with an id (trigger props, stable ids), seats and beds
    (sleepers land on them; the seat plan must not change), lit props' bodies, wall-mounted and
    stacked props and what they stand on, `route_ok` debris, the yard.
  * Lights and lit props still burn with `style.lights_on` (0.7); a lit prop and the authored
    light hung on it share one draw; `"keep": true` pins a light on.
  * The builder draws its scatter, wall damage and floor-decal turns from the dressing seed, and
    adds 1–10 **run decals** (`PoiDressing.run_decals`): grime, water stains, mould and cracks on
    solid wall faces (more with decay), survivors' marks and blood on walls and floors.
* **Saves (v5).** `WorldState.poi_dressing` is `2` (per run) for new worlds. The v4 → v5 migration
  sets `1` (legacy) on older saves: their buildings resolve to the authored defaults with no wear
  and the builder keeps the instance-id seed, so a run saved before this change keeps exactly the
  buildings it was played in. A POI state pins its picks (`"picks": {group: option}`) the first
  time the building is built, so a run keeps its rooms even if content later gains options.

### 2. Room alternatives in the DSL (`"alternatives"`)
* A def may carry `"alternatives": [{id, label?, options: [{id, label?, weight?, default?, rooms?,
  openings?, style?}]}]`. One option per group is picked per run, weighted, each group from its own
  stream (adding a group does not reshuffle the others).
* An option may re-dress rooms (`name, type, wall, floor, ceiling, open_to`: purpose and finish),
  change openings by id (`state, key, lock, barricade, barricade_on, cue, model, hp`: locked,
  barricaded, broken open) and restyle the building (`exterior, interior, floor, ceiling, decay,
  damaged_walls, prop_condition, scatter, lights_on`). It may not touch a plan, a room's height or
  a roof: walls, cellars and the terrain cut must not move between runs.
* Any entry of `props, sleepers, traps, triggers, pickups, notes, lights, decals, openings` may be
  tagged `"alt": "group:option"` (or a list): it exists only when one of those is picked. That
  gives furniture sets, sleeper spots and groups (one sleeper id may stand in different places in
  different options: its dead state follows it), alternative trap spots and knocked-through walls.
* The first option (or the one marked `"default"`) is the authored building, and a content def
  compiles as its defaults (`PoiLayout.compile`). Retrofitting keeps the default resolution
  identical to the old layout, list order included (alt-tag entries in place, append new ones), so
  legacy saves, stable ids and the builder's draw order are untouched.
* **Validation.** `PoiValidator.validate` checks the block's structure (unknown keys, bad tags,
  options that change plans), then validates **every option changed alone from the base** and
  **every full combination**, or a deterministic sample of 16 when there are more. Each must keep
  the route, the loot room, sleepers and triggers valid, and every shortcut and every locked door
  the base can use must stay usable. Errors and new warnings are reported once, tagged with the
  picks that showed them (`[alt bedroom=nursery, doors=kicked_in]`).
* Four buildings are retrofitted, each with five groups: the Merrow House (the parents' room and
  the kids' room finishes, where the neighbour lies in wait or that he brought his wife, the living
  room, how Dad left the doors); the Mile 9 Diner (where the regulars sit, a third in the walk-in,
  where the trapper's jaws are, the dining room and office); the Okafor farmhouse (the room at the
  top of the stairs is a sewing room, Papa's study or the junk room; the spare room; where Chidi's
  floor has rotted; how the cellar ambush lies; the kitchen); Lou's trailer (the bedroom, who is
  in the bathroom, a second listener when the key is taken, the living room, the kitchen).

### 3. Generated ordinary buildings (`BuildingGenerator`, `BuildingTemplateDef`)
* Templates live in `data/pois/templates/` (a new content kind with typed `_fields`): archetype
  (`house`, `duplex`, `store`, `workshop`), zoning, tier, weight, width/depth ranges, storeys, `upper`
  (`full` or `cape`), porch and chimney chances, floor height, setback, decay and sleeper ranges,
  exteriors, weighted roofs (type, pitch range), roof materials, finishes per room purpose, name
  and story patterns (`{family}` from `data/config/building_generator.json`). Seven ship: bungalow,
  ranch house, two-storey, cape cod, duplex, corner store, workshop.
* `generate(template, seed, lot)` is a pure function of its inputs (one seeded stream; finishes per
  room from their own streams). It builds, in order: the plan (a hall from the front door to the
  back between a day side and a night side, both drawn, or for a single storey a hall across the
  middle as in the Merrow House; a night side too wide for a bathroom gets an en-suite off the back
  bedroom or a linen room beside the bath; two storeys widen the hall to two columns,
  a flight rising in one from the back; a cape cod sets the upper floor back so the front rooms get
  a lean-to; a duplex's two units and their knocked-through party wall; a store's sales floor,
  stock room, office and restroom; a workshop's bay, office and tool crib), doors, the way in (the
  back door, a smashed side window or a clawed hole) and windows, the route (the bolted front, round
  to the way in, the loot room, out through the bolted door: the shortcut), then furniture off the
  route corridor (the validator's own paths) and a ceiling fixture in most rooms, a container in
  the loot room, 2–4 sleepers with one
  small ambush (a body on the bed, one crouched, woken by the loot room door), one gentle trap,
  story decals, the porch, chimney, fences, mailbox, yard junk and a drive wreck, and the style.
* It validates what it made and retries from a derived seed until the validator reports nothing
  (errors or warnings), up to 8 times. Unit tests generate 50 buildings per template.
* These are tier-1, dungeon-lite buildings: modest loot, a few sleepers, no keys. No cellars, so
  the terrain cut never needs them.

### 4. Lots that pick (`LotPicker`)
* A lot without a `pick` holds what `LotPicker.resolve(framework, placement, world seed)` chooses:
  an authored building zoned for it (not already standing in the framework, its footprint fitting)
  or a template zoned for it, weighted, deterministically from the world seed. `pool`
  (`any|authored|generated`), `templates` (naming them implies `generated`) and `tier` narrow it;
  `"reserved"` holds a lot empty for a building still to be authored. Lot keys are checked
  (`FrameworkDef`). On a shallow lot the generator shortens the front yard before the house.
* PoiManager and TerrainHoles resolve lots the same way, so an authored building picked from the
  pool gets its cellar cut. A generated building fills its lot (footprint = lot, building set
  back from the street edge) and is named after the lot.
* **Pell's Crossing** grows south (framework size 76 × 336): Larch Street runs from the Grange Road
  corner to a dead end short of Route 9, with six residential lots that each run fills with its own
  houses, hydrants, lamps, poles, a collection box, a board fence behind the gardens, two wrecks and
  the barred dead end. On its corner, three lots are **reserved** for the school, the fire station
  and the bank (the third block, authored by another workstream).
* `make validate` validates the alternatives of every POI, six buildings per template and every
  generated lot of every framework for three world seeds; the poi-preview takes `--seed N` and
  `gen:<template>:<n>` ids; the screenshot suite has a `larch_street` shot.

## Consequences
+ A run's buildings differ from the last run's: rooms change purpose and finish, the ambushes lie
  differently, doors are shut or kicked in, furniture is broken or gone, lights burn or not, the
  grime, stains and marks move; ordinary streets are new every run.
+ Old saves, stable ids and saved piece states are untouched; the validator still proves every
  variant and every generated building.
+ RWG (ADR-0031) can fill any framework from zoning alone.
− Validation costs grow with alternatives (base + singles + up to 16 combinations per building).
− Generated buildings are rectangles of rectangles with one archetype each: no L-plans, cellars,
  keys, tall rooms or alarms yet, and their furniture sets are small (TD-077).
− An option cannot move a wall or change a plan (by design); alternative plans need separate defs.
− Picks are pinned per run but generated buildings are not: a template edit changes the generated
  houses of a running save, orphaning their saved piece states (harmless, but visible) (TD-078).
− Pell's Crossing's pad grew with the framework: the town's pad is the mean height over the larger
  area, 0.48 m lower than before (86.66 m against 87.14 m), and the land falls away to the
  south-west, so the extension's far corner stands on up to ~9 m of fill behind the last gardens
  (composed and probed; TD-079). Its bank (up to 51°) stood across the drop trail, which now
  skirts south of the pad to meet Route 9 below the dead end (walked: 24° at its steepest).
− New class names are referenced through `preload` constants in the files that use them, so the
  code compiles before an editor import registers them.
