# ADR-0053: Forest set pieces (round 4): seven dungeons in the woods, placed late from their own streams

**Status**: Accepted · 2026-10

## Context
After the Build #67 playtest the owner asked for more to find in the woods between towns, every
building walkable by the player who plays it (ADR-0051: real ladders, clear doorways, no "climb"
interactions). Round 3 (Camp Tamarack, the lodge, the quarantine camp, the Haldane Place) set the
pattern: an authored dungeon in the wilderness pool, kit rooms with shell props round them where the
kit can't build the walls, its own props, notes, keys and loot.

Two constraints came with the round:
* **Worlds already played must not move.** A random world's id hashes the generator version
  (TD-082). A new pool entry in the forest pass draws from the shared `places` stream, which shifts
  every place drawn after it.
* **Traversal is proven, not assumed.** Every building is checked with `TraversalAudit` (ADR-0051)
  as well as `PoiValidator`, and each climb is a ladder, a stair, a vault or a drop.

## Decision

### Seven buildings, one file set each
Seven parallel authors, each in its own worktree with the namespace `w4_<short>_` (props, notes,
items, keys, loot, materials), its own `data/props/wild4_<short>.json`, its own
`props_wild4_<short>.py` generator and catalog, and its own test `test_w4_<short>.gd`. The test
checks for 0 errors and 0 warnings in every dressing, a route of more than six beats walked end to
end, and a full dungeon (`locked_inside` shortcut, a guardian, two or more sleeper groups, traps,
lock cues, at least three notes). It also checks that keys are found before they are needed, that
nothing a player reads names a town, and that `TraversalAudit` reports 0 errors.

| POI | Tier | Footprint | What is climbed |
|---|---|---|---|
| The Kell Shelter (`w4_hillside_bunker`) | 3 | 30 x 30 | Three hatch ladders: under the rug into the bunker, and up the escape shaft into a hatch house in the woods |
| The Cordon Transport Wreck (`w4_cordon_plane_wreck`) | 3 | 36 x 40 | A vault over the ramp lip (1.08 m), a hatch ladder to the flight deck |
| Kettle Creek Ranger Station (`w4_backcountry_ranger_station`) | 2 | 34 x 34 | Four hatch ladders up the fire tower to its cab (12 m) |
| Tunnel 2 Trestle (`w4_trestle_tunnel`) | 2 | 40 x 44 | A ladder on a trestle bent up to the deck, a 1.15 m vault into the boxcar, the embankment stair down |
| Dunmore Timber Truck Depot (`w4_logging_truck_depot`) | 2 | 40 x 36 | The inspection pit's ladder, the stair to the mezzanine |
| Ridge Relay Hut (`w4_ridge_relay_hut`) | 1 | 24 x 24 | Four hatch ladders up the relay tower |
| Shiloh Chapel (`w4_overgrown_chapel`) | 2 | 30 x 34 | A window over a crate (1.5 m sill), the loft ladder, two drops, the vestry hatch ladder, the vault stairs |

Towers (fire tower, relay tower) are stacked 2 x 2 kit rooms railed with the mast rail and dressed
by a no-collision lattice prop: the player climbs real ladders between real floors, and a Hollowed
can't follow (a cleared tower is a refuge, as intended).

### Late pool entries
`tuning.wilderness.pool` entries may say `"late": true`. The main site loop skips them. After the
farmsteads and before the mines, each one is placed from its own stream,
`rng("places:late:<poi id>")`. Every place an older world held is drawn exactly as before. Late
places still take room from the mines, which come last from their own streams, as they must so
their cover is checked on the final ground. All seven set pieces are late `forest` entries.
`RwgGenerator.VERSION` goes to 9 (8 is the Ezra camp), so worlds cached by older generators
regenerate as they were.

### The validator's yard
Several set pieces stand in an open yard (the trestle's ravine, the relay compound, the
churchyard). PoiValidator's yard ring now walks a POI's unbuilt level-0 cells:
* a solid yard prop taller than a vault (a fence, a wall, a truck) cuts the yard steps it stands
  across;
* `out` joins only the ring at the footprint's edge, so a fenced compound is entered by its gate.

## Consequences
* Random worlds gain seven kinds of forest dungeon at danger 1-3; 8 x 8 worlds hold most of them
  (`test_wilderness_round_four`).
* Goldens recorded at v7 or v8 are re-recorded at v9. Places at earlier draws are identical; the
  composed ground differs only round the new pads.
* Leftovers are TD-269 to TD-278. The common ones:
  * no sleepers in yards (TD-269);
  * shell and structure props collide only as their single size box (TD-270);
  * colours were reviewed only in the lead's renders, not by the authors (TD-271).
