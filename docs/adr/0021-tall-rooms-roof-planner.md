# ADR-0021: Tall rooms, galleries, a roof planner and per-room probes

**Status**: Accepted · 2026-10

## Context
POIs compile from one plan per 3 m storey (ADR-0009). Until now every room was one storey tall
and every roof was a gable or a flat slab over one level's bounding rectangle (TD-008, TD-038).
The buildings that should be tall read as stacked boxes: the church nave and belfry, the barn's
threshing bay, the sawmill's saw floor, the grange hall. An L-shaped plan got a roof over its
bounding rectangle. One reflection probe over the whole plan lit the yard inside the L as if it
were a room (TD-040). Stair flights and door leaves stood 8 cm into the walls beside them (TD-023).

## Decision

### Tall rooms are drawn in the plans
* A room def takes `"storeys": 2` or `3` on its lowest level. The plans above mark the space it
  rises through with `^` (the void). The compiler resolves each `^` to the room it rises from
  (`PoiLayout.void_base`, `volume_of`), so an upper plan can put a gallery, a loft or a bell
  chamber beside the void, or close it at any storey.
  * Why not a rectangle or a flag on the room: authors read each storey as a plan. The void must
    show where they place stairs, galleries and holes, and it can take any shape a room can.
* A void cell has no floor and no ceiling under it. The tall room's ceiling closes its top storey,
  unless the room says `"open_roof": true`: then it sees the underside of the roof (boards,
  rafters, collar ties, a ridge beam, wall plates).
* **Walls stay one kit piece per storey and metre.** This keeps the kit, wall damage, finishes and
  piece budgets as they are. Where a floor slab used to sit, `wall_band_1m` fills the 20 cm band
  between storeys.
  * The `kit_wall` shader hides the stack. Each wall instance carries a per-side height code in
    `INSTANCE_CUSTOM.a`: the storey's offset in the room plus 4 × (storeys − 1); side A is the low
    nibble and side B is ×16. Exterior faces carry code 0.
  * With the code, the baseboard, grime, leaks and ceiling darkening measure height in the room
    instead of in the storey.
  * `std_surface` only acts on negative values there, and instance uniform indices are unchanged.
* **Two-storey openings** (`lancet`, `window_tall`, `door2_tall`) are single 5.8 m kit pieces.
  They are authored on the lower storey and fill the edge above, which must be a wall.
* **Galleries.** An upper room beside a void gets a gallery edge instead of a wall: a fascia over
  the slab edge and a waist-high railing with a collision box. The railing is `balustrade` (turned
  balusters) or `rail` (rough timber). The room can opt out with `"gallery": false`, which builds
  a wall.
  * Only `open` (a gap: an authored drop) or `breach` (a broken railing) can go on a gallery edge.
* **One room, whatever the height.** `PoiInstance.locate` resolves a point in a void to the tall
  room's floor cell. Room triggers, shelter, indoor checks and reverb therefore answer for the
  floor the room rises from. Ceiling fixtures (`ceiling_mounted` props) and authored lights hang
  from the real ceiling.
* **The validator knows the void.**
  * Nothing stands in it: sleepers, pickups, cell traps, route waypoints, and props unless they
    are wall-mounted, `stairwell` or raised 0.5 m.
  * No stairs land in it, and no holes are cut in it.
  * A gallery gap, or a passable opening in a wall onto the void, is a one-way drop edge in the
    route graph, so an authored drop is a valid shortcut. A drop that strands the player is an
    error.
  * The navmesh needs nothing extra: the void has no floor collision and the railings are
    obstacles. Drops have no navigation links (TD-042).

### A roof planner follows the massing
* `RoofPlanner` takes each level's tops: the built cells with nothing built above, voids
  included. It decomposes them into rectangles greedily, largest first.
  * A tower that rises through a roof is added to the roof below, so that roof runs on whole under
    it instead of breaking into strips. Such a tower is a small rectangular column on the storey
    above, bordered by this level's tops on two or more sides.
* Each rectangle becomes a **wing** with a role:
  * **main**: the style's roof.
  * **leg**: the same height as a larger wing beside it. It gets a gable that runs to the main
    ridge (cross gables meeting in valleys), or stops at a gable end it abuts.
  * **annex**: against a taller wall. It gets a lean-to when it is no deeper than 4.5 m, an
    abutting gable when deeper, and a flat roof behind a parapet on commercial and industrial
    buildings. Its pitch is lowered until it stays under the windows of the wall it leans on.
  * **tower**: a small top a storey above the rest. It gets a hip roof, or a pyramid or spire by
    override.
* Authors override a wing in `style.roof.roofs`. An entry names its wing by
  `{"level": L, "at": [col, row]}` (any cell of the wing) and can set type, axis, pitch, slope,
  material, parapet and so on. The validator reports an override that names no wing, an unknown
  key and an unknown type.
* `RoofBuilder` makes each wing's slopes as planes over convex polygons. It cuts each face wherever
  another wing's roof stands higher inside that wing's walls (convex subtraction). One rule gives
  valleys between cross gables, roofs that stop at the walls they meet, and roofs that run on under
  towers.
  * The trims (fascia, rake boards, ridge and hip caps, gutters) follow whatever edges are left on
    the eave, rake, ridge and hip lines.
  * ADR-0019 stands: materials and colours come from `roofs.json`, UVs run in metres along the
    eave and up the slope, gable ends are wound to face out (`Plane(...).normal.dot(outward)`),
    and `"type": "none"` builds no roof.
* Chimneys clear the roofs near them. The 4.5 m `chimney_brick` stood under the eaves of anything
  taller than a cabin. It now sits on whole metres of `chimney_shaft_1m`, so its brick courses
  run on, until it stands 0.4 m clear of every roof within 3 m: past the ridge beside a gable end,
  a little above the eave beside a long wall.
* Alternatives considered:
  * A straight skeleton over the outline handles any polygon. But it is fragile on grid
    outlines, gives one roof for all heights, and leaves authors nothing to override.
  * Authored roof volumes would be 19 buildings' worth of work, and would drift whenever a plan
    changed.

### Probes per room rectangle (TD-040)
* `PoiBuilder.probe_boxes()` groups each level's room cells by the storey their room rises to
  (and whether it is open to the roof). It splits the groups into rectangles and stacks a
  rectangle that repeats storey over storey into one box. It then merges the pair that wastes the
  least volume until 8 or fewer remain.
* Each box stops 5 cm inside the walls, so a yard inside an L or a courtyard keeps the outdoor
  light, and so do the facades.
* The probes stay in the `interior_probe` group (daylight-scaled by `EnvironmentController`) with
  `UPDATE_ONCE`.

### Stairs and doors stand off the walls (TD-023)
* A flight against a wall moves off it by half the wall's thickness, and is narrowed when it runs
  between two walls. Its banister goes on the open side.
* A door leaf that would swing into a wall running off its hinge side is hung on the other jamb.
* A door's casing in the last metre of a wall still reaches into the wall at the corner: openings
  are centred in their 1 m piece (TD-023 keeps that part).

## Consequences
* Five showcase buildings are retrofitted, and their piece ids are kept:
  * St. Ansel's: a double-height nave with a choir-loft gallery, a belfry tower with a steeple,
    and lancets.
  * The Okafor barn: the threshing bay is open to the roof under a hayloft gallery, with a tall
    hay door and a hay-chute drop.
  * The sawmill: a two-storey saw floor.
  * The grange hall: open to the roof, with its balcony as a gallery.
  * The Okafor farmhouse: a summer-kitchen ell, so its roof and probes are an L.
* The other 14 buildings keep their JSON. The planner's defaults replace their bounding-box roofs:
  lean-tos on single-storey annexes, flat fronts behind parapets on commercial blocks.
* There are 21 new kit pieces: 20 in `kit_tall.py` and `kit_gallery.py` (the storey band, tall
  openings with their glass, boards and barn door, both railing styles) and the chimney shaft.
* School gyms, fire-station apparatus bays and warehouses use the same schema (`storeys`, `^`,
  `door2_tall`, `open_roof`). A bay door wider than 2 m is not in the kit yet (TD-041).
* Saves are unaffected: there is no new state, and piece ids are stable.
