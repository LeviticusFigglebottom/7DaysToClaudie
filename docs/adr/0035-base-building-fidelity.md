# ADR-0035: Base-building fidelity: a woodsman's camp, racks that fill, doors, stairs, furnished floors

**Status**: Accepted · 2026-10

## Context
Building is The Forest's core loop. Hollowmere had its skeleton from ADR-0006:
* freeform 4 m logs that snap into notched walls, platforms and pitched roofs;
* blueprints for a campfire, a lean-to, a bough bed, a workbench, stake barricades and a crate;
* structural support and collapse.

Rendered in-engine, it did not look or play like a survivor's camp:
* **The log.** It read as a smooth, mottled tube with no bark relief, and every wall, floor and
  roof is made of it.
* **Camp pieces.** The workbench and the crate were sawn lumber. The lean-to was a sparse frame.
  The campfire was clean sticks in a ring.
* **Missing pieces.** There was no way to keep logs, sticks and stones where you build (The
  Forest's holders), no door for a gap in a wall, and no stairs onto a platform.
* **Floors.** Nothing could stand on a log floor: assemblies always went to the terrain under
  the aim.

## Decision

### Models (tools/assetgen/blender/generators/structure_*.py)
* **The log** gets real bark: thick fissured plates, knots, trimmed branch stubs, and axe-cut ends
  with rings and checks, plus moss in the vertex colour. Its contract does not move: 4.0 m long,
  the 0.34 m envelope, origin at the centre, the saddle notches, the cove. LogSnapper's numbers
  stay true.
* **Camp pieces:**
  * The campfire gets an ash and charcoal bed, half-burnt split wood and a lashed cooking tripod
    with a spit.
  * The lean-to gets dense layered boughs, lashings and a bough floor.
  * The bough bed gets a lashed log frame and a pillow.
  * The workbench becomes split-log, with a stump vice.
* **New pieces** (structure_base.py):
  * a log holder, a stick holder and a rock pile, each with `fill_NN` parts;
  * log stairs: eight 0.29 m risers over 3.6 m, matching the log courses;
  * a stick door on a pole frame, its `leaf` a separate node hinged at its own origin.

### Runtime
* **Racks** (`provides: rack:<item>:<capacity>`):
  * A rack takes only its own resource.
  * One press stores everything of that kind the player carries, or takes one when they carry
    none (`build.rack_store` / `build.rack_take`, reach-checked).
  * Its inventory saves as a container's does.
  * It shows `ceil(count x parts / capacity)` of its fill parts.
  * Logs are carried two at a time, so a holder by the build site is the point.
* **Named parts:** `ModelLibrary.parts(model, prefixes)` splits a model's named nodes from the
  merged mesh (rack fills, a door's leaf) and caches them. Stand-ins, built from posts, a slab leaf
  and stacked fill blocks, work before `make assets`.
* **Doors** (kind `door`):
  * `build.toggle_door` swings the leaf 90 degrees with a short tween. The leaf's collider jumps
    to where the leaf ends up.
  * The state saves in `WorldState.flags["open:<id>"]`.
  * A door is a StructurePiece, so a Hollowed in a chase that runs into it tears at it, as it
    would at a wall.
* **Stairs** (kind `stairs`) are one walkable 33-degree ramp under the treads.
* **Furnished floors.** A blueprint with `on_structures` (beds, benches, crates, racks, stairs,
  doors) aims at logs too:
  * It stands on the horizontal log under the aim, at the log's top.
  * The floor logs it stands on don't block it.
  * Once built, it is not a ground root: it is linked ON that log in the structure graph, so it
    comes down with the floor.
  * The campfire stays on the ground.
* **Saves.** Nothing new beyond flags and container records. The grounded flag and links already
  save per piece.

## Consequences
* A camp can now be stocked and lived in: logs racked by the wall, a door to shut, stairs up to a
  platform, and a bed and bench on the cabin floor.
* All of it is data plus three small runtime pieces (racks, door, ramp), and every piece degrades
  to a stand-in.
* Gaps are TD-098..101.
