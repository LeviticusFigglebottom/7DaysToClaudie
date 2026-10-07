# ADR-0039: Waystation trading: trader posts, a scrip economy and contracts

**Status**: Accepted · 2026-10

## Context
The dungeons had no reason to exist beyond their loot. 7 Days to Die's core loop is the
trader: take a job, clear or fetch or defend, come back, get paid, and climb a reward ladder.
DESIGN §2 and §6 put that at **Waystation 9**, the Remand Program's relay post at the Cordon wall.
The pieces were there but unused:
* `scrip` dropped in towns and the Savings & Loan, and was worth nothing.
* `ItemDef.value` was documented as "trade value" and nothing read it.
* `QuestDef` (`data/quests/`) was data only.
* Region D7, where DESIGN puts the post, is not built; D6 is.

## Decision

### The post
* A trader is a `TraderDef` (`data/traders/<id>.json`, new content kind `trader`). It holds:
  * the set dressing, the trade counter and the contracts board (post-local offsets);
  * the quartermaster;
  * the safe radius;
  * the stock list;
  * prices, restocks, reputation tiers and the board's size.
* It is placed by a region `spawn` feature with the id `trader:<def>` (or `trader:<def>:<n>`).
  `TraderManager`, a GameWorld module, raises a `TraderPost` at every such spawn. The post's
  front (local +Z) faces the spawn's yaw.
* **Waystation 9 stands in D6** by Route 9, at (-30, 2522), short of where the river leaves the
  valley. It sits there until D7 is built: then its spawn moves to the culvert in the Cordon
  wall and nothing else changes. A clearing and a drive from Route 9 come with it.
* **Random worlds** use the generic `program_relay` def, a smaller camp. The generator emits
  `trader:program_relay:<n>` spawns, with a clearing and a road stub to the gate, along its roads.
  That generator side is the hub's: no worldgen code here.
* **The quartermaster** is the first living human character (`characters/waystation_quartermaster`).
  He stands behind the hatch, turns to the player and leans on the counter to talk. He is drawn
  by EnemyVisual, so the stand-in body applies before `make assets`.
* Every prop falls back to a box of its size.

### The safe zone
* `AIDirector.spawn_point_ok` refuses points inside any post's `safe_radius`. That covers
  wanderers, heat responses, Keener summons and the Hum.
* The guards fire on any Hollowed that walks in (`guard_dps`, ballistic, from the towers), so
  a chase into the post ends at the wire.

### The shop
* Prices follow `ItemDef.value`:
  * Buying costs `ceil(value × buy_markup × (1 − rep_discount × tier))`.
  * Selling pays `floor(value × sell_ratio)`.
  * The post never buys keys, quest items, notes or scrip.
* **Stock** is rolled per restock period (`restock_days`) from the world seed (`Contracts.roll_stock`).
  * Each entry has a reputation tier; the counter shows only the tiers the player's standing has reached.
  * What players buy leaves the shelf; what they sell goes on it.
  * The live stock is saved in `WorldState.traders`, keyed by the def id. A def with
    `stock_per_post` (the relay camps) keys it by the post's spawn id instead, so each camp keeps its
    own shelves (TD-146). A save from before that has the camps' stock under the def id: a post
    with no entry of its own starts from it, with no version bump.
* Trades go through `trade.buy` and `trade.sell`, checked against the player's range from the post.

### Contracts
* `QuestDef` is the contract def.
* `clear`, `fetch` and `defend` defs are **templates**: a tier band and a distance band from
  the post, the reputation tier needed, a weight and rewards. `defend` also has its waves.
* **The board** (`Contracts.offers`) deals `offers_per_day` offers per trader and day, all
  deterministic from the world seed, the trader, the day and the slot.
* Each offer picks a building:
  * in its bands, not visited or cleared, and not already a target of the player's;
  * for clear and fetch, one with sleepers;
  * the one its seed key ranks first.
* Buildings come from one lookup, `TraderManager.buildings()`, which is `PoiManager.all_buildings()`.
  That holds every placed building, never just the ones near the player. TD-118's PoiRegistry
  switch applies here too.
* **Clear** is done when PoiInstance marks the building cleared (every sleeper down) and a
  container in its loot room was searched. The container id (`c:<building>:<prop key>`) names its
  prop, and the building's layout says whether that prop stands in the loot room, so reaching in
  through a doorway counts (TD-145).
* **Fetch**: a Program cache (`program_cache`) is set down on a loot-room cell once the building
  stands and the player is near. It is a loose item from then on. The contract is done when the
  player picks it up there, and turning it in hands the cache over.
* **Defend**: the offer's spot is a dry, gentle point 16–26 m from the building.
  * Holding E on the relay cache there starts the uplink.
  * `waves` waves spawn on a 50–65 m ring through `AIDirector.spawn`, aimed at the cache.
  * The contract is done once `duration` seconds pass with the player within 30 m.
  * Leaving for 8 s or dying drops the uplink, and it can be started again. A run is never saved
    half-held.
* **A tier-5 site** (TD-179): `fetch_t5` sends a Trusted player to the Corvane Field Lab (ADR-0046) for
  a sealed Bloom core. Three fields make a fetch fit a unique site whose payoff is already there:
  * `place: false`: nothing is set down; the vault's guaranteed core is the item. The contract is
    ready while the player carries one, wherever it came from, and open again if they drop or sell it.
  * `target.fresh: false`: offered even after the player has been inside.
  * `once`: never dealt again once turned in (`ContractLog.done`).
  It pays 450 scrip, well over the core's 240-scrip sale, plus XP, standing and two antifungals.
* **Turning in** at the post pays scrip and items (overflow drops at the player's feet), XP
  (`progression.add_xp`) and reputation.
* **Reputation** is per player and per contract giver. Its tiers (Unknown, Known, Trusted, Program
  asset) unlock stock, harder contracts and a discount. A relay camp reads and pays Waystation 9's
  standing.
* **Failing** (TD-146): an accepted contract has `expires_days` (QuestDef, default 3, 0 never;
  `due` on the contract). One still open at the dawn of its due day fails: it leaves the books, its
  building is free for the board again and the giver docks `fail_rep` (default 10). One done and
  waiting to be reported never fails, nor a defence being held. `contract.abandon` costs
  `abandon_rep` (default 5). Standing can now go down; rival givers (factions) are still out of scope.
* `contract.accept`, `contract.turn_in`, `contract.abandon` and `contract.start_defend` are
  commands.
* The player's contracts, standing and taken offers are a `ContractLog` saved with the
  PlayerState.

### Around it
* **Saves**: `world.traders` and `players[*].contracts` are new keys that load empty from older
  saves, so there is no version bump (v7 is session 3's world bundle).
* **Events**: `contract_accepted`, `contract_completed` and `trade_made`.
* **Directives**:
  * the `contract` event, and directive `hold_contract` (chapter 3);
  * a world with no trader spawn marks it spent.
* **Tether**: posts are yellow squares and contracts are rings (filled when ready to report). The
  first open contract takes the directives' second line.
* **Field manual**: a "Waystation 9" page.
* **UI**: `TraderScreen` is a clipboard with Buy, Sell, the board and your contracts.
* **QA shots**: `waystation_9` and `waystation_counter`.

## Consequences
* Every building now has a job attached and a reward ladder over it. Scrip, item value and
  reputation finally mean something.
* The board, stock and targets are reproducible: two players of one world see the same day,
  and a reload changes nothing.
* Gaps are TD-141..148.
