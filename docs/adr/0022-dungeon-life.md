# ADR-0022: Dungeon life: sleepers on seats and beds, the Hollowed on traps, route cues, readable plans

**Status**: Accepted · 2026-10 · amends two rules of ADR-0018 (triggers while nobody is near; who
sets traps off)

## Context
ADR-0018 made POIs into dungeons, but some of it was only staged for the player.
* **Posed sleepers ignored the furniture (TD-039).** A `sit` sleeper sat on the floor beside the
  pew, or inside the chair. A `lie` sleeper lay through the bed. Woken, both stood up inside the
  furniture. Sleepers had no height: the pose was played at the authored floor spot.
* **Traps were the player's alone (TD-037).** Hollowed sprang bear traps and shotgun wires. They
  walked over creaky and rotten boards and through alarm cords without a sound. A weak floor that
  gave way left the nav mesh over the hole. The shotgun was a damage cone that went through walls.
* **Triggers waited for the player.** An ambush trigger fired only while the building's sleepers
  were spawned. A door the Hum broke far from the player left its ambush armed forever, even
  though the door now hung broken.
* **Entry windows didn't read from the street (TD-034).** A route that climbs in through a
  window gave no sign of it from outside.
* **Preview plans hid the dungeon.** `make poi-preview` drew every sleeper as the same dot. It
  showed no ambush groups or triggers, every trap was an edge bar, and seated sleepers stood where
  they were authored (F6 in game showed more).

## Decision
### Seats and beds
* **Anchors on props.** `PropDef.anchors` lists seats and beds:
  `{kind: seat|bed, pos: [x, z], height, facing, lean}`.
  * `pos` is prop-local, under the pelvis. `height` is the seat or mattress top above the prop's
    base.
  * `facing` is in degrees from the prop's front (+Z). It is the way a sitter looks, or head to
    feet on a bed.
  * `lean` (seats only):
    * `back` (default): against a backrest. Plays `idle_sleep_seat`.
    * `forward`: hunched on a backless stool, bench, crate or cot rail. Plays `idle_sleep_hunch`.
    * `low`: sat legs out in a bathtub or on a mattress. Plays `idle_sleep_sit`, raised onto
      the surface.

  Chairs, pews, booths, stools, couches, benches, waiting chairs, crates, beds, cots, bunks,
  mattresses, sleeping bags and the bathtub carry anchors. A destroyed variant carries none.
* **Landing.** A `sit` sleeper takes a seat and a `lie` sleeper takes a bed, the nearest free one
  within `reach` (1.6 m) on its level (`SleeperAnchors.assign`). The choice is a pure function of
  the layout: no RNG and no spawn order.
  * Every (sleeper, anchor) pair in reach is sorted by: pinned first, then distance plus a facing
    penalty against the authored `rot`, then sleeper order, then anchor order. Pairs are taken
    greedily.
  * An anchor holds one body. Anchors of one prop closer than `exclusive` exclude each other (a
    bench seats both ways at the same spots).
  * A prop holds sitters or lying bodies, never both.
  * `"anchor": "<prop id>"` pins a sleeper to a prop (within twice the reach).
  * `"anchor": "floor"` keeps a sleeper on the floor: Draggers, bodies under rubble or slumped in
    an aisle.
* **Unusable anchors are skipped.** These carry no seat or bed:
  * a prop stacked on something (it has a `y`), or with something standing on it;
  * a seat whose feet would go through a wall, out of the building or over a stair well.
* **Posing.** `SleeperAnchors.body_origin` places the animation's origin from char_anim's pose
  constants, mirrored in `traps.json` `sleepers`. It scales with the body.
  * **Seats:** the pelvis sits `seat_back` behind the feet on a seat `seat_height` high. A
    taller seat lifts the body (feet on a stool's ring). A lower one sinks it, at most
    `max_sink`.
  * **Beds:** the pelvis lies over the anchor, pressed `mattress_sink` into the bedding.

  A test keeps the two sets of constants in step: with generated bodies, the animated hips bone
  of each pose must end within 8 cm of its anchor, 4 to 20 cm above the seat or mattress. In the
  shipped buildings it lands within 2.5 cm, 9 to 13 cm above.

  New in-place animations: `idle_sleep_seat`, `idle_sleep_hunch`, `idle_sleep_crouch` and
  `idle_sleep_kneel` (breathing loops), plus `wake_seat` and `wake_hunch`. The old floor `sit`
  pose keeps its hands above the floor and its arms out of long-armed bodies.
* **Perched bodies.** A perched sleeper (`Enemy.perch`) is kinematic: it does not fall or slide
  off the seat. Its capsule (what weapons hit) and its eye follow the pose. Killed asleep, it keeps
  the pose and the corpse box matches it.
* **Getting up.** Woken, the body rises over `rise_seconds`. The origin moves along a scripted path
  to its **exit** while the wake animation plays:
  * from a seat: up where its feet were;
  * from a bed: it sits up, swings round and steps off the side.

  The exit is a free floor spot in front of the seat, else behind it or to a side (out of a
  booth). For a bed it is beside it, else past the foot. It must be in a room cell, not across a
  wall, and clear of the other props. Then the body is an ordinary one under physics.
* **Validation.** `PoiValidator._check_dungeon_life` reports what `SleeperAnchors.check` and
  `RouteCues.check` find (a sleeper that lands on a big seat no longer counts as sharing its cell
  with a prop):
  * a warning for each sit or lie sleeper left on the floor without `"anchor": "floor"`;
  * an error for a pin that names no such prop;
  * errors and warnings for malformed or misplaced cues.
* **Content.** Every seated or lying sleeper in the buildings is landed or marked. The changes
  were moves into an existing bed or bunk, added furniture where the story has it, or
  `"anchor": "floor"`:
  * the travellers' bedroll and a folding chair in the Cordon garage;
  * beer crates and a quarantine mattress at the Northwoods;
  * Benning's office cot;
  * a chair for the sample miner and one by the clinic's drug closet;
  * a cot for the sick in the logging camp;
  * a walkway chair outside room 7 and June's armchair at the Timberline;
  * the trailer's tub sleeper now sits in the tub.

### The Hollowed and traps
* **Weight classes.** `traps.json` `hollowed` sorts Hollowed into light, normal and heavy:
  Draggers are light, Husks and Rammers heavy, the rest normal. Each trap's `hollowed` block gives
  a `min_weight` (no block: they never set it off) and `fires_trigger`.
  * Sensors watch the enemy layer when the rule allows.
  * A trap a Hollowed sets off makes its noise through the stimulus fields: sleepers wake by
    hearing it. Only the player's misstep alerts them directly. Only the player's alarm spends
    every ambush and rouses the whole building.
* **Per trap:**
  * **Can chime, bear trap, shotgun wire:** set off by any Hollowed.
  * **Alarm:** a Hollowed rings it. The ringing wakes by stimulus (held ambushes only within the
    ambush `wake_radius`) instead of rousing the building.
  * **Creaky floor:** groans under any Hollowed. The groan is a sound cue for the player only: no
    noise for the Hollowed, and the trap is not spent, so its ambush stays armed for the player.
    Something walking about upstairs should warn, not spring the trap meant for the player.
  * **Weak floor:** gives way only under a heavy Hollowed. Bodies standing on it fall and take
    `fall_damage`. The collapse emits `PoiInstance.geometry_changed`. `PoiManager` then marks the
    nav tiles there dirty (`NavTiles.mark_dirty`). They rebake after `REBAKE_DELAY`, once the
    slab's collider is disabled, so the rest stop pathing over the hole.
* **Shotgun pellets.** The shotgun fires `pellets` rays, spread uniformly within `spread_deg` of
  the aim. The pattern is deterministic per building and trap.
  * The building shell, solid props and the first body in the way stop a pellet. Door leaves and
    glass (layer 2) do not: a leaf swung open beside the gun must not shield the doorway.
  * Each pellet carries `damage / pellets`, falling linearly from full at `near` to nothing at
    `far`.
  * A body takes all its pellets as one hit.

### Triggers and noise while nobody is near
A trigger that fires while the building's sleepers are not spawned is **spent** like any other.
This amends ADR-0018. The trigger's group is **roused**: recorded in
`WorldState.pois[id].roused` (sid -> POI-local point) and saved with the world. Roused sleepers
spawn awake next time:
* not held, already investigating toward where it happened;
* standing by their post, at their seat's or bed's exit.

The entry is consumed when they spawn.

Unspawned sleepers are roused by the same rules as spawned ones:
* **A trap a Hollowed sets off:** ordinary sleepers within `loudness x unspawned.hearing`. Held
  ones only for ambush wake kinds (gunshot, explosion, alarm) within `wake_radius`.
* **An alarm the player sets off:** everyone.

The key is optional, so the save format does not change (no version bump).

### Route cues on windows
Every window that the validated route climbs in through from outside gets `route_cues.default`
(`curtain`, `crate`, `scuffs`). An opening's own `"cue"` overrides it: a kind, a list, or
`"none"`. The kinds are:
* **`curtain`:** a torn floral curtain dragged out over the sill (`props/cue_curtain`, `_wide` on
  2 m windows). Only in open, broken or missing windows.
* **`crate`:** a solid crate under the window outside, two stacked when the sill is high.
* **`scuffs`:** muddy boot scuffs up the wall and a bloody handprint on the sill.
* **`light`:** a camping lantern left burning on the inside sill, lit through PropLights
  (ADR-0023). At most `max_lights` per building.

`RouteCues.build` adds them when a `PoiInstance` enters the tree. They are deterministic per
building and window, and a cue whose model has not been generated yet is left out.

The entry windows come from the route, not from a second validation. For each route leg that starts
outside, `RouteCues.entry_windows` runs the validator's breadth-first search over its own graph
(`PoiValidator._neighbors`, no keys), stops at the leg's first room and reads the window the path
climbs through. The plan is cached per POI def. This runs as each building is built at world load:
the validator's full search took 14 s for the 22 buildings (3.5 s for the sawmill alone), the
early-exit search 0.7 s, with the same windows.

### Readable plans
`make poi-preview` plans draw:
* sleepers posed where they spawn: a disc per pose, a lying capsule head to feet, a facing tick,
  and a line back to the authored spot when a seat moved them;
* sleepers coloured by ambush group, with group labels and orange guardian rings;
* triggers in their group's colour, linked to the group. Room triggers tint their cells, opening
  triggers are a diamond on the edge, and pickup, container and trap triggers are a ring;
* cell traps as squares, edge traps as bars;
* route-cue windows.

`--sleepers [ids]` spawns the sleepers and shoots a close view of each seated or lying one.

## Consequences
+ Seated and lying sleepers sit and lie on the furniture the stories put them on, the same way on
  every machine and visit. They get up off it believably before they hunt.
+ Traps belong to the building, not just the player: the Hum can spring them, the player can
  hear something on the boards upstairs, and a broken floor stays broken for pathing too.
+ A building the Hum went through while the player was away is different when they come back: the
  ambush is spent and its sleepers are up.
- Getting up is scripted. It is not collision-checked: a body can pass through a bed's side rail
  or the tub's rim. A sleeper on a top bunk drops to its exit (TD-047).
- Sitting on a bed's edge, a hay bale or other seats far from 0.46 m would float or dangle. Those
  props have no seat anchors until there are high- and low-seat poses (TD-046).
- Authors place a seated sleeper roughly where it should sit. It moves up to `reach` onto the
  seat, and the preview plan draws the move.
- The Hollowed only set traps off. They don't see or avoid them, a bear trap bites a Hollowed but
  doesn't hold it, and a fall through a weak floor has no animation (TD-045).
- Route cues are scenery for ground-floor entries. Upper-storey entries get no ladder cue, and the
  curtain fits 1 m and 2 m windows only (TD-048).
