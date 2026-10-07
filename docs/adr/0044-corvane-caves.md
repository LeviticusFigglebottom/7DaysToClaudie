# ADR-0044: The Corvane caves: buried POI levels under the Larkspur cliffs

**Status**: Accepted · 2026-10

## Context
DESIGN puts the Bloom's origin underground: a Corvane bore broke into a limestone cave older than
the mountains. The Corvane cave network (M2) is "lightless, key items, the mine and the Root", entered
through the Corvane Deep Mine (region C2) and sealed passages (C6, C1). None of those regions is
built; D6 is, and its Larkspur cliffs carry a frontier feature, `larkspur_sealed_cave`, waiting for it.

ADR-0007 planned caves as SDF volume columns. That path is not ready:
* Volume chunks have no navmesh: `VolumeTerrain.faces_in_rect` is never baked into the nav tiles.
* Volume chunks never stream out.
* Converting a column repaints the ground above with volume dirt.
* The Hollowed's fell-through-the-world rescue (`ground_below`) would lift anything in a tunnel back
  to the surface.
* `is_indoors` is false in a tunnel, so rain, outdoor ambience and sky ambient (on Low) reach in.

## Decision
**Caves are underground levels of a POI.** Everything the dungeons already have applies as is: the
navmesh from colliders, `is_indoors` and reverb, interior probes, keys and locks, sleepers, triggers,
guardians, alternatives and the route validator.

### Buried levels (TerrainHoles)
* A POI level may say `"buried": true`.
* Its cells under a ground-floor room cut the terrain surface, as every cellar does.
* The rest lie under the ground, one floor-only Hole per level in `TerrainHoles.buried`, kept apart
  from `holes`. So the mesher, collision, nav and volume carving never see them, and the ground stays
  whole over a drift or a cave.
* `TerrainManager.ground_below` finds a buried level's floor for a point down in it, so the enemy
  rescue, loose items, spores and the load drop leave things where they are.
* A region feature's `size` keeps the POI's pad (the levelled ground) to its surface buildings, while
  its footprint runs on under the hillside.

### Darkness
* Below the surface it is always night for the Hollowed (`Enemy.is_night`, more than 2.5 m under the
  ground, re-checked once a second): they see without light and run.
* The player's light is what gives them away.
* This applies to every cellar too.

### Rock
* `kit_finishes.json` gains walls `rock_drift` (blasted granite with drill half-barrels) and
  `rock_limestone` (pale wet limestone with flowstone), and floors `rock_floor` and `cave_mud`
  (textures in `kit_rock.py`).
* `kit_wall.gdshader` treats them as interior finishes that never peel or take a baseboard.
* A mine kit (`props_mine.py`):
  * timber sets, rails, ore cars, the hoist, a headframe and a cage;
  * rock faces (granite, an overhang, flowstone) to break the 1 m grid, rock piles, stalagmites;
  * lamp strings, powder boxes, a tool rack and a safety board.

### The Corvane Larkspur Adit (`corvane_larkspur_adit`, tier 3)
Corvane's exploration adit at the foot of the Larkspur cliffs, by the sealed cave. The Deep Mine
itself stays C2's.
* **The surface:**
  * a mine office, bolted from inside: the way out;
  * a changehouse and a hoist house, whose door hangs off: the way in;
  * a shaft house with the manway down, and the headframe in the yard.
* **No. 1 Level** (buried, running west under the cliff):
  * the shaft station, then a 40 m timbered drift with jaws between the rails;
  * the powder magazine (the key is in the office);
  * the refuge station, where the trapped crew wakes when the winze key is taken;
  * a chained winze gate with cans on it.
* **No. 2 Level** (buried):
  * the stope, whose crew wakes on its loose boards;
  * a blasted breach into the limestone cave;
  * the grotto: the loot room, held by the foreman, with a survey cache that always holds a Bloom core
    sample.
* Four notes tell the story: the shift boss's log, the breakthrough report, the refuge door and the
  Program's order to collapse the passage west.
* Four alternative groups vary each run.

Random worlds can take the adit as a wilderness site: the hub's generator adds a `mine` site.

**Note (generator v7, TD-169):** the `mine` site does. It reuses this adit as is, once per world
(`unique`, danger 3+). The generator picks a steep macro slope within 800 m of a road and turns the
plan so local +X (where the levels run) goes uphill. The region feature's `size` (the entry's `pad`,
24 x 14) is all that is levelled. Every buried cell beyond the pad must lie under the reference
ground by 1.5 m at the pad's edge, growing to 4 m 16 m in: TD-164's check, made at placement. The
track comes along the contour to the hoist-house door. Mines are placed last, from their own stream,
so no other place moves. Leftovers: TD-206..210.

## Consequences
* A dungeon can now go down into the ground without opening it to the sky, and the Hollowed stay
  down there.
* The caves read as a mine rather than as natural limestone: the POI grid is boxy, and only the rock
  faces, stalagmites and finishes break it.
* The organic caves beyond the sealed passage (C6) and the Deep Mine (C2) wait for their regions.
* Gaps: TD-162..169; random-world mines TD-206..210.
