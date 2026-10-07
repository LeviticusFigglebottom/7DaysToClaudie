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
