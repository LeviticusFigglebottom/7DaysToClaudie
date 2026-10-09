# ADR-0051: POI traversal: a capsule audit, clear doorways, ladders that are climbed

**Status**: Accepted · 2026-10

## Context
The owner's second priority after a playtest of Build #67 was getting around inside buildings:
* doorways blocked by props;
* things lying on the floor in the way;
* "climb up" spots that are an interaction instead of a ladder or a jump.

Nothing checked traversal in physical space:
* PoiValidator walks a 1 m cell graph. A prop never blocks one of its edges; it only warns when a
  big one sits on a route cell. Stairs and ladders are single abstract edges.
* The builder's scattered clutter has no collision. Authored props get a box of their def's size
  (`collision` box, convex or mesh alike). A def's `boxes` gives several (ADR-0053, TD-270).
* Nothing keeps a door's swing, or the space in front of it, clear.
* A ladder (`PoiPieces.Ladder`) was an interaction that teleported the player to the other floor.
* The tour bot sprints at a POI's origin and never walks a route.

## Decision

### The audit
`TraversalAudit` (`src/poi/traversal_audit.gd`) walks a built POI with the player's own capsule:
radius 0.33 m, 1.75 m tall, tested a step (0.42 m) off the floor so thresholds don't count.
* **Free-space grid.** Each level is sampled every 0.25 m, so cell centres and doorway centre lines
  fall on the grid. A short ray down from a step above the floor finds where to stand: porch
  decks and stoops count, tables and beds don't. The free samples are joined into connected areas.
* **Route runs.** The validator's route is split into same-level runs. A run breaks at an opening,
  a stair, ladder or hole cell, or a level change. A run is blocked when no area reaches both of
  its ends (each end with its four neighbours, since a waypoint is often the bench itself).
* **Doorways.** Each non-window, non-boarded opening between two walkable cells is checked three
  ways:
  * the capsule must fit on its centre line in an area that reaches both sides;
  * a breach is swept with the crouched capsule;
  * no step across it may exceed 0.38 m (Player.STEP_HEIGHT), up or down.
* **Windows on the route.** Each window or pony wall the route climbs through is measured. The
  sill must be within a vault of the highest thing in front of it: the ground, a porch, or the route
  cue's crates. That thing must be within a vault of the ground. A crate is climbed by the same
  vault. Session 3's `poi_walk` bot doesn't climb a crate first, so its window blocks over-count.
* **Naming the blocker.** A straight sweep names what is in the way:
  * `prop:<id>` (PoiBuilder tags the prop's collision shape) or `container:<id>`;
  * `trap:<id>` (a shotgun's chair rig) or `structure`;
  * `step <m>` for a sill.
* **Severity.**
  * An **error** is anything on the route: a blocked run, or a doorway the route crosses.
  * A **warn** is everything else, plus three cases: an obstacle the player vaults (0.3–1.3 m, as
    `Player._try_vault`), a prop authored `route_ok`, and a closure (a prop tagged `door`, a pulled
    down roll-up bay door, is skipped).
* CLI: `godot --headless --path game -s res://src/tools/cli/traversal_audit.gd -- [ids] [--gen N]
  [--seed S]`. Building a POI takes most of the time. The runner validates the base route only:
  `validate()` re-checks every alternative, which takes seconds per building.
* `test_traversal_audit` fails on any error in a shipped POI except raised sills. Sills belong to
  the entrance-steps work (TD-229) and are counted.

### Data and rules
* The first pass found 69 errors on the route.
  * 39 of them were sills: exterior doors on floors 0.3–0.6 m up with no step outside, including
    the back door of every generated house. These are left to the entrance-steps work.
  * The rest were props, moved in the data:
    * The Okafor cold room was sealed: a shotgun rig beside its door, plus a shelf.
    * At the cannery, Haldane Place and the VFW, a board, gun rack or back bar was mounted on the
      door's own wall edge.
    * At the cannery and the quarry, a pickup wreck stood in a breach.
    * Grange Hall had plywood across the stage door.
    * At the Savings & Loan, the library, the diner, the logging camp and the VFW, furniture
      stood in or against a doorway.
* **Small floor clutter has no collision**: the bucket, gas can, extinguisher and three lanterns
  (all ≤ 0.55 m tall, ≤ 0.12 m² footprint). The player walked into them and stopped dead. Scattered
  clutter never had collision. Heavier things (milk cans, crates, propane tanks) stay solid.
* **Scatter keeps clear of door swings.** The scatter makes the same draws but places nothing in a
  cell a door opens from, so every other building's scatter is unchanged.

* **The fire station's pole slides.** `fire_pole` has no collision: the brass pole stood in the middle
  of its 1 m hole and stopped the drop.
* **Ladder hatches are drops.** In PoiValidator's route graph, stepping onto an open ladder hatch
  lands at the ladder's foot, as the player does. A doorway onto a hatch is an error (TD-224).
* **Session 3's `poi_walk`** walks the real player through every room. It complements the audit,
  and its prop findings in doorways are fixed: the tavern's bathtub, the school nurse's cabinet,
  the laundromat chair, the Grange sick bay, the lodge's boot room, the barn's workshop door.

### Ladders are climbed
A ladder no longer has an interaction. `Player` climbs it:
* **Getting on.** Walk into it at its foot, facing its rails, and it takes hold. From the landing
  upstairs, walk into its hatch. A ladder whose landing is behind its rails (a hunting stand, a rope) is
  taken from the top by walking off the landing toward it (TD-295).
* **Moving.** Forward climbs at 1.9 m/s. Back climbs down, and so does forward while looking down
  more than about 35°. Grabbed from above, forward means down until forward is let go.
* **Getting off.** Over the top, the vault's scripted path steps you off onto the landing. At the
  foot you let go on the floor. Jump lets go anywhere.
* **Sound.** Rungs sound and make a little noise.
* `PoiPieces.Ladder` keeps its layer (not solid). It joins the `ladder` group with its foot,
  height and face. Vaults stay vaults: windows, pony walls, crates under entry windows.

## Consequences
* Every authored POI and generated building can be audited in about a minute headless. Layouts
  are checked against the same body that walks them.
* The audit covers authored props and building pieces at their authored placement. Per-run
  dressing (alternatives) is audited only with `--seed`, and the test doesn't run it (TD-231).
* Sleepers, loot and the player's own structures aren't in the audit's scene.
* Off-route doorways still blocked are listed as warnings for their authors (TD-230). The quarantine
  camp's cots stand in its tent entrances (`route_ok`, vaultable). The sawmill's log carriage spans
  the deck doors (`route_ok`, 1.45 m).
* Hollowed can't climb ladders (unchanged), and the climb has no hand animation (TD-232).
* A bucket or lantern without collision is walked through: a clip, not a snag (TD-233).

## Addendum (2026-10, round 4): "intuitively navigated"
The owner's next report: interiors still need validating so the intended path can be walked
fully and intuitively. Since round 3 many POIs were added (the forest set pieces of rounds 4 and
5, the field lab, the Ashen camps, Ezra's camp, the mine). The audit as it stood passed all 54
POIs and 3 generated buildings of every template, with no dressing and with seeds 1, 77, 4471 and
9001: no errors at all. `poi_walk` (the real body) still stopped in 27 of the 54. The audit had
five blind spots.

### What the audit now checks
* **A vault on the route is an error.** A table, cot or trough the route only gets past with
  Jump is not an intuitive way (and the bot doesn't vault furniture either). The finding is still
  named "(vault <m>)". An author's `route_ok` keeps it a warning (the quarantine camp's cots, the
  radio station's rubble under its cable hole).
* **Floor breaks.** Free samples join into areas only across a step the player takes (0.38 m).
  The floor under a deck gap or a loft edge was free space too, and a 0.41 m blanket pile counted
  as floor. A run broken that way is "floor step <m>", an error.
* **Door leaves** (`_door_swings`). Every leaf is posed fully open
  (`PoiPieces.Door.open_leaf_transform`) and tested for anything it stands in, past its first
  0.25 m (the jamb):
  * props, containers, trap rigs and walls from 0.3 m up: an error on a doorway the route
    crosses, a warning elsewhere;
  * floor clutter under 0.3 m: a warning ("(low)");
  * a leaf standing out over a stair flight, its well or a ladder hatch ("stairs"): an error
    wherever the door is. It closes the steps for whoever comes up them.
* **Loot in reach** (`_loot_reach`). A loot-room container must be searchable from somewhere the
  route's areas reach. That is a free spot whose eyes (1.55 m up) see the box within the 2.6 m
  interaction reach, with nothing in between. If no container passes it's an error; if only some
  fail it's a warning.
* **Pitch dark** (`dark_route`, pure layout). A route room (with the rooms open to it) can be lit
  in three ways: an outside opening; one doorway on from such a room (an arch, a hole, a door
  standing open or the one the route opens); or a light within 1.5x its range. A dark route room
  is a warning. A dark loot room is an error, and so is a loot room whose only light lacks
  `"keep": true`, since `style.lights_on` puts it out in some runs.

### Door leaves in the builder
* **Hinge on the wall side.** A leaf hangs on the jamb a wall runs off, where it stops at 90°
  (`PoiBuilder.DOORSTOP`). Its pivot moves 1.5 cm into the jamb (`_stop_hinge`), so the leaf lies
  flat on the wall without entering the clear width. This replaces TD-023's rule, which hung it
  on the other jamb. That put the open leaf across the room beside the doorway, closing the way
  to it from that side.
* **Exceptions.** The wall side is skipped when that wall has a doorway in its first metre (the
  fire station's shop door lay across its stair-bay door). With no wall at either jamb, the leaf
  avoids the jamb a stair flight or well runs along.
* Other leaves still open 99° (`Door.OPEN_ANGLE`). A leaf stopped at 90° snagged the bot in
  narrow corners. With the stop limited to walls and the pivot shift, `poi_walk` is no worse
  anywhere.
* **Shotgun rigs.** A shotgun's chair goes on the latch side of a door that opens into its room
  (six leaves opened into their own rigs).
* **Generated houses.** A generated wall prop keeps 7 cm off the edge of a cell beside a
  doorway's cell, on the same wall: the open leaf leans 13 cm back past its hinge jamb.

### Results
* Audit errors on shipped POIs and generated buildings: 0. Base dressing and seeds 77 and 4471
  checked, 3 per template.
* Warnings: 21 dark route rooms (TD-366), 66 off-route or `route_ok` doorways, 5 leaves (4 over floor
  clutter, 1 into a generated armchair: TD-367), 2 `route_ok` runs.
* `poi_walk`: 22 of 54 buildings still have a blocked leg, against 27 before; the blocked legs
  fell from 63 to 36. What is left is mostly ladders the bot can't grab, the thin ramp edge at
  the side of a flight's foot, and cascades from those (TD-363, TD-364, TD-368).

### Consequences
* `test_traversal_audit` covers each new check:
  * a leaf opening into milk cans (error) and over a rag pile (warning);
  * a crate fenced off behind a stall partition;
  * a loot room two doorways from daylight: unlit, lit but not kept, and kept;
  * a barrel in a doorway: an error, or a warning when `route_ok`.
* Vaults on the route are errors now, so a new POI that wants a climb on its route says so with
  `route_ok`.
* Doors next to walls look different in every building: open, they lie flat against the wall
  instead of standing across the room.
* Still blind (TD-365): a route path through furniture between a run's ends, and a window
  vaulted from a prop whose top leaves the sill too low for the vault's ray.

## Addendum (2026-10, round 5): every intended route walked by the real body
The owner, again: "interiors need more validation to ensure the intended path can be fully and
intuitively navigated; ladders appear invisible" (the invisible ladders: 96c4320, kit ladders
turned to face the room). Goal: `poi_walk` walks every authored POI's route and explores every
room with 0 blocked legs and 0 unreached rooms, fixing the building wherever it is at fault and
the bot only where it misjudges something a player manages.

### The player
* **A ladder climbed down with forward held could not be climbed back up.** Walking into a hatch
  sets the climb-down hold (forward climbs down until let go); only back or no input on the rungs
  cleared it, so it outlived the climb, and the next grab at the foot climbed down and let go at
  once. Every ladder the route takes down and back up failed this way (the depot pit, Cedar
  Ridge, the bunker shafts, the bathhouse, the treehouse: most of TD-363). It clears on a grab
  from the foot and on letting go there.
* **Onto a flight from its side.** The ramp's floor under the body's middle rises under a step
  over the first step's low half, but the capsule's round bottom rests 8 cm higher on a 37°
  slope, and the step-up landed on the slab's edge or not at all (TD-364). After the plain steps,
  one more try lifts `STEP_HEIGHT + SLOPE_LIFT` (0.5 m) and carries the body a radius on, onto the
  slope's face, when the floor a radius past where it presses stands within a step of the feet:
  a 0.49 m ledge is still a vault.

### The audit
* **Ladders** (`TraversalAudit._ladders`): the standing capsule fits in front of the rails, the
  landing holds it, and a hatch ladder's landing lies across the hatch from the rails (the player
  takes a ladder down only walking at its rails, so from a landing beside the hatch the way down
  is the hole). Errors where the route climbs (down, for the landing's side), warnings elsewhere.

### The buildings
* Cedar Ridge: the stair gate hung in the side wall of the second flight's first step, where the
  floor rises 0.3-0.45 m under a 2.1 m header. The tower is three cells wide, so its flights are
  entered from the side; the gate now closes the flight's head on the second landing.
* Relay tower: the field radio stood on the top platform's landing. Fish hatchery: the catwalk
  ladder's landing was beside its hatch (it leans east now). Library: the same for the fire
  escape.
* Motel: room 3's nightstand under its broken window (the way in) left the sill 0.22 m over its
  top; June's armchair left 0.56 m to her bathroom door. Bunker: the firewood leaned on the
  couch's front, closing the bedroom door's corner. Grange: the office door opens into the office.
  Tunnel 2 Trestle: rails on the deck's last metre, where the gate's leaf shoved a body off.

### The bot (`poi_walk`)
Off the route a player walks round what the plan walked into: weak floors and holes (the explore
walk fell through the motel's room 7 and the chapel nave), a ladder's rails on an open edge (the
treehouse deck), a barricade across a door (a room only a barricade closes is listed apart as
"barricaded"), a window whose sill is past the vault with nothing under it (St. Ansel's lancets).
It opens a door at a flight's head on the stairs leg, ducks through a breach (1.7 m), takes a
drop onto whatever stands under the hole (the sawmill's conveyor, Calder's feed sacks), keeps a
bolt it drew drawn, never steps aside onto a hatch or out through another doorway to work a door
(Cedar Ridge's cab door sent it down the hatch; the Grange's and the ranger station's out of the
building), and drops off any ladder or vault when it restarts a failed leg (TD-368).
