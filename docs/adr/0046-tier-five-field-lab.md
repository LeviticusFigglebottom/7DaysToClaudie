# ADR-0046: Tier 5: the Corvane Field Lab, keycards as keys, and a compound the validator can walk

**Status**: Accepted · 2026-10

## Context
The premise sends Remand Salvager #4471 into the Cordon "to recover Bloom core samples and research data
from the mine and the old field lab" (DESIGN §1), but nothing in the game was the field lab, and nothing was
tier 5: the Larch Hollow Sawmill (tier 4) was the hardest building. The engine already allowed it: `PoiDef`
clamps tiers to 1..5 and `LootRoller` scales empties, rolls and quality up to tier 5. What was missing was a
place that earns the number, rules for what tier 5 means, and a way to build a 50-60 m compound (most of it
outdoors) that the validator can still prove in every dressing.

## Decision
* **Tier 5 means the deepest dungeons**, and the Corvane Field Lab is the first. A tier-5 building has:
  a locked front and a way in round it; four or more held groups that ambush on different kinds of trigger
  (the lab: a room, a door, a pickup, a search and a trap, eight groups in all); traps of four kinds or more; a
  route of twenty beats or more down into a buried level; a chain of keys to its deep rooms (the lab: the
  station keys, the containment key, a keycard and the vault's code); a vault lock on the loot room
  (ADR-0026) behind a wire, a special Hollowed as its guardian (a Husk: the biosafety officer in her suit);
  and loot gated to tiers 4-5, with the Program's quest items as the payoff. `tests/unit/test_field_lab.gd`
  holds the lab to this.
* **The payoff is data**: sealed Bloom core canisters (`bloom_core_canister`, value 600, the most valuable
  item in the game) and Program research drives (`lab_research_drive`, 220) are `quest` items tagged
  `trade`, so the quartermaster buys them at `sell_ratio` of their value (ADR-0039); the vault always holds a
  core (`guaranteed`). A staff antifungal (`lab_antifungal_ampoule`) is the best non-quest pickup. A fetch
  contract can target either item without any code.
* **A keycard is a key.** An item of category `key` with a card model (`items/lab/lab_keycard`), opening a
  `locked` door with a `deadbolt` lock (it can't be broken off: bash the door), and a card reader prop
  (`lab_card_reader`, its red lamp on the battery) beside the door as the lock cue. No engine change; the
  validator proves it like any key.
* **Placement**: one wilderness pool entry, site `remote` (far from the drop site, high, level ground),
  `min_danger` 4, `max` 1 per 16 km², reached by a dirt track. `per_region` 0.07 places one in every world of
  4 x 4 and up (16 x 0.07 > 1) and in about two of three 3 x 3 worlds; `rwg_preview`-style checks placed it in
  15 of 15 worlds of size 4-6, always in a danger 4-5 region 2.5-6 km from the drop site.
* **The compound**: a 56 x 56 footprint. The wire is props with collision (the station fence, its gate); the
  guard hut stands in the south fence line and the containment block in the north one, so the block's escape
  hatch (the bolted shortcut) opens on the hillside beyond the wire. Prefab lab modules are kit rooms under
  shell props (`lab_module_shell`, one model for all four, turned 180 degrees east of the boardwalk), the
  covered boardwalk an open-sided kit room under roof props (`lab_boardwalk_roof`), as round 3's tents
  (ADR-0031 wilderness set pieces). The buried level is an ADR-0007 cellar entirely under the block, so the
  terrain cut never opens to the sky; earth banks (`lab_berm`) bury the block's back and shoulders.
* **A yard the validator can walk.** The validator floods every '.' cell of a plan for every route leg,
  every key wave and every dressing; a 54 x 54 yard made one validation of the lab take 4.4 s and the whole
  test time out. The lab's open ground is ' ' (nothing) except a ring round each building and the cells the
  route stands on outside: the builder treats ' ' and '.' alike (both are not rooms), and every '.' cell
  still joins every other through "outside". With its alternatives grouped into four pairs (sixteen
  dressings, all validated) the lab validates in about 40 s.

## Consequences
+ The game has its hardest place where the story says it is, and random worlds put it far from the start.
+ Keycards, tier-5 loot, the vault and the escape shaft are all data on existing mechanics; another tier-5
  building can reuse the props and the pattern.
- Validation and `make test` each take ~40 s more. A compound bigger than this one should keep its open
  ground ' ' as well, or the validator should get a cheaper yard (TD-176).
- The buried level is one storey (what the engine supports); deeper levels wait for the caves' buried levels.
- In game the fence is the only thing that keeps the player to the route through the wire; the validator
  can't see props (TD-177).
