# ADR-0024: Pads that keep their water

**Status**: Accepted · 2026-10

## Context
* **Every placement pad flattened everything under it.** `TerrainComposer` grades a framework's or
  POI's footprint to one height after water and roads are carved: the mean of 25 samples over the
  pad plus 5 cm, with a smoothstep skirt round it. A pad that reaches over a lake or river fills the
  water's bed up to that height, so the water surface sits under solid ground.
* **The boathouse needs water inside it.** Larch Pond Bait & Boat (DESIGN §11) has a boat slip
  open to the pond between two walkways under its net loft, a dock along it and pilings under the
  bays. Placing the whole POI on dry land loses the slip; placing it out over the pond buried the
  pond under the pad.
* **An "auto" lake level moves.** Larch Pond's level is derived from its shoreline. A pad height
  taken from the dry ground's mean floated anywhere from 0.1 m to 0.6 m over the water as the
  placement or the terrain around it changed. The dock decks, piles and the rowboat in the slip are
  props authored against the water: they would end up afloat or drowned.

## Decision
* **A placement may keep its water.** `"keep_water": true` on a `framework` or `poi` feature in
  region.json:
  * The pad's height is the water's, plus a `"freeboard"` (default 0.6 m), not the ground's mean:
    the water level is averaged over the pad samples that fall in the water (the coarse water
    field). With no sample in the water the pad behaves like any other.
  * The pad grades only dry ground. Its weight is multiplied by a smoothstep over the first 2 m of
    signed distance from the water's edge, so nothing in the water changes and the bank eases down
    to the shore instead of standing over the water as a step. Under the pad the lake keeps its
    bed and the water system draws its surface as before.
* **The POI is authored against its freeboard.** Larch Pond Bait & Boat puts the water 0.6 m under
  its pad: the slip cells are yard between the walkways, the dock sections (decks at the top of the
  model) are placed `y = -height`, the piles stand in the water and the rowboat floats at
  `y = -0.6 - 0.12`. Its placement on the pond's west shore sets `"freeboard": 0.6`.
* The change is the pad step only (`_pad_for`, `_apply_pads`, `_water_field`). No cache version
  bump: a region's cache key hashes region.json, which changes with the flag.

## Consequences
+ Buildings can stand over water: boathouses, docks, mills on their races, bridge houses.
+ The water props' heights hold whatever the auto level does; only the freeboard ties them.
- The water under a pad is whatever the lake carving made: the pad cannot shape a slip's bed
  (deepen it, square it off). Docks and piles are props, not terrain.
- The building's floor over water is the kit floor slab with nothing under it but piles (props).
  The validator still treats yard cells over water as walkable ground (TD-049).
- A keep_water pad that only grazes the water takes its height from those few wet samples: authors
  pick a placement where the water reaches well under the pad (`probe` the compose, REGIONS.md).
