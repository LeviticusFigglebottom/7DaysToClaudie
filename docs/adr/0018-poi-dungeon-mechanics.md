# ADR-0018: POI dungeon mechanics: ambush triggers, traps, lock cues, guardians, stable piece ids

**Status**: Accepted · 2026-10

## Context
7 Days to Die's buildings are dungeons. Sleepers wait in volumes that wake when you step into
them. Traps punish a careless approach. Locked doors push you onto a route or make you choose
something noisy. The loot room has a guardian. Our POIs (ADR-0009) had a validated route,
sleepers that woke only to noise, light and proximity, and one trap (the can chime). Locked
doors looked like closed ones (TD-034). POI piece states were keyed by list position (TD-031),
so the authored lists could not be edited after release.

Several other authors are writing new buildings against this schema at the same time, so it has
to be declarative, validated and stable.

## Decision
* **Sleeper groups and triggers.** A sleeper may carry `"group"`. A POI's top-level `"triggers"`
  (`{id, group, on: room|opening|pickup|container|trap, room+level | opening | pickup | prop | trap,
  delay}`) wake a group:
  * `room`: the player enters any cell of that room.
  * `opening`: that door, window or barricade is opened or broken.
  * `pickup`: that pickup is taken.
  * `container`: the first search of the prop with that `id`.
  * `trap`: that trap goes off.

  A grouped sleeper spawns **held**. Ordinary noise, light and proximity are ignored, and so are
  other sleepers waking. It wakes early only to gunfire, explosions or an alarm within
  `ambush.wake_radius`, or to a blow. When its trigger fires, the group's dormant members wake
  closest-first. Each one comes `ambush.stagger` seconds after the last (deterministic per instance
  and trigger), already alerted to the player (straight into the chase once on its feet), under an
  audible stir (`sfx/ambush_stir`).

  A trigger fires once per POI instance and only while the building's sleepers are spawned
  (nobody is there to ambush otherwise). Fired triggers are persisted in
  `WorldState.pois[id].triggers`. After a reload a spent ambush is not re-armed: surviving members
  come back as ordinary sleepers.
* **Guardians.** `"guardian": true` spawns one infected tier up (normal -> Seeded -> Bloomed; the
  world setting that turns tiers off wins). A guardian without a group of its own is held until
  the loot room is entered: the compiler adds an implicit `_guardian` room trigger. Sleeper Sense
  outlines guardians in a warm rim.
* **Traps** are typed: `can_chime` (unchanged), `bear_trap`, `shotgun`, `creaky_floor`,
  `weak_floor` and `alarm`. They are cell traps or edge traps (`PoiLayout.TRAP_TYPES`). Each has
  a generated model (`props/trap_*`) and a state of `armed`, `sprung` or `disarmed`, persisted in
  `WorldState.pois[id].traps`. Tuning lives in `data/config/traps.json`.
  * A crouched interaction disarms a trap through the `poi.disarm_trap` command (ADR-0003) and
    pays out parts.
  * A weak floor gives way 0.5 s after the player steps on it and becomes a one-way drop hole.
    It is built from kit batches of its own (rotten slab, then broken slab) so the hole persists.
  * An alarm wakes every sleeper in the building, which spends every ambush. It keeps putting
    `alarm` noise and heat into the stimulus fields while it rings.
* **Lock cues.** Doors get a lock kind (`padlock` by default on `locked`, `bolt` on
  `locked_inside`, or `"lock": "padlock|chain|deadbolt"`). The cue hangs on the leaf at its latch
  edge, on the face the door is approached from (`PoiValidator.lock_sides`: the side reachable
  from outside without passing through it) or the inside face for bolts. A padlock (60 hp) or
  chain (90 hp) can be beaten or shot off. That is loud: each hit is noise. The door is then
  merely closed. The validator's route still requires the key.
* **Validation.** `PoiValidator` errors on:
  * missing or duplicate ids on sleepers, traps and triggers;
  * unknown trap types or keys, traps outside rooms, edge traps across solid walls;
  * weak floors without a room below, routes that break once every weak floor has given way, and
    falls that strand the player;
  * triggers naming missing rooms, openings, pickups, containers or traps, or a group with no
    sleepers;
  * locks on non-doors.

  It warns about groups with no trigger, triggers on openings that start open, guardians outside
  the loot room, and container props or pickups without an id.
* **Stable piece ids (TD-031).** Containers are keyed `c:<instance>:<prop id>` (prop index when the
  prop has no `id`). Sleepers and traps use their ids, and notes `note_<note id>`. The save
  format version goes to 3. The v2 -> v3 step can't know each building's layout, so it tags every
  POI state `keys: 1` (the same step drops harvested-plant records, as v1 -> v2 did, because the
  riverbank biome's scatter changed in the same release). `PoiInstance` re-keys a legacy state from its layout the first time the
  building is built (all POIs are built at world load). That assumes the authored lists only gained
  ids and appended entries since the save. The five retrofitted POIs follow that rule.

## Consequences
+ Buildings can be authored as 7DTD-style dungeons in data alone: ambushes on the route, traps a
  careful player can spot and disarm, a guardian on the loot, locks that read at a glance.
+ Everything is validated in `make validate`, shown by F6 and covered by `test_poi_mechanics` and
  `test_poi_dungeon`.
+ Container, sleeper, trap and pickup states survive edits to a POI's lists once ids are given.
− The legacy re-keying trusts that the 5 original POIs were only appended to. A future reorder of
  a POI without ids still misassigns states. The validator warns on missing container ids.
− Held sleepers ignore everything ordinary by design, so a badly placed trigger can leave a group
  asleep forever. The validator warns about groups with no trigger.
− Nav tiles are baked with the weak floor intact. After a collapse the Hollowed path as if it were
  still there (TD-037).
− Traps are player-only where it matters: Hollowed spring bear traps and shotgun wires, but not
  creaky floors, weak floors or alarms (TD-037).
