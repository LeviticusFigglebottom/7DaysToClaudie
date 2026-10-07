# ADR-0052: Base traps and electricity: pits, deadfalls, a tripwire bell, generators, wires, lights and sentries

**Status**: Accepted · 2026-10

## Context
M3's base tech (DESIGN §4: "Rain catchers, gardens, deadfalls, generator + wiring + lights + motion
turrets") had its first half in ADR-0049. A base could feed and water itself, but its defences were a
stake barricade and a can chime, and nothing lit it but a campfire. The Hum (DESIGN §6) asks the
player to hold ground at night against waves that "target your weakest wall": the base needs things
that work while the player is busy elsewhere, and a way to see.

What there was to build on:
* base building (ADR-0006, ADR-0035), StructurePiece behaviour from `provides`, and farming's
  template for a base-tech system (ADR-0049: data, a GameWorld module, commands, a WorldState key);
* the stimulus fields and the heat map (ADR-0012): sounds the Hollowed hear, lights that make the
  player visible, attention that summons scouts and packs;
* PropLights and the shadowed-light budget (ADR-0023, the `shadow_light_budget` group);
* the POI traps' weight classes (`traps.json` `hollowed`, ADR-0022);
* the command bus and diff-only saves (ADR-0003, ADR-0005), world settings (ADR-0014), XP sources
  and directives (ADR-0015).

Constraints: the save version is reserved (v7, session 3's world bundle); session 2 is retuning
Hollowed perception in `enemy.gd` at the same time, so this must not need hooks there; and the game
must run before `make assets`.

## Decision

### Content
* **Pieces** (`structures/base_tech.json`; blueprints in "defense" and a new "power" category):
  * `spike_pit` (provides `spike_pit`), `deadfall` (`deadfall`), `tripwire_bell` (`tripwire`);
  * `generator` (`power_source:400`);
  * consumers `work_light` (`power_use:60`), `floodlight` (`power_use:150`) and `nail_sentry`
    (`power_use:200` + `turret`).
* **Items** (`items/base_tech.json`): gas can (fuel), wire spool, electrical parts, work lamp, small
  engine, and three schematics. The generator, floodlight and sentry blueprints need their schematic
  (`unlock: schematic`); the pit, deadfall, bell and work light are known from the start.
* **Recipes** at the workbench: a wire spool from two electrical parts; a small engine from scrap,
  parts, tape and nails.
* **Loot**: an `electrical_salvage` table (parts, wire, lamps, a gas can, a tier-2 engine) rolled
  from toolboxes, hardware shelves and auto shop shelves; gas cans in car trunks and auto shelves;
  the schematics in the `reading` table (tier 2+, the sentry tier 3+).
* **Tuning** is `config/base_tech.json`: every damage, duration, noise, wattage-independent number
  and range. Wattages are in the pieces' `provides`, so a new consumer is a JSON entry.

### Rules (`BaseTech`, pure functions)
* **Roles** come from `provides` (`trap_kind`, `power_kind`, `source_watts`, `draw_watts`).
* **The grid** (`solve`): wires join pieces into networks (union-find over the wire list). A
  network's running generators (on, with fuel) sum their watts; its switched-on consumers are served
  in piece-id order while the watts last. One that does not fit is skipped and a smaller one after
  it may still fit. The order is deterministic, so a save always lights the same lamps.
* **Fuel** is generator hours at full load. A gas can is `can_hours` (4), the tank `tank_hours` (8).
  It burns at `idle_burn` (0.35) of the full rate idling, rising linearly to 1 at full load, times
  the `power_fuel_use` world setting.
* **Attention**: a running generator adds `heat_per_minute` (same load factor) to the heat map, so a
  generator left running summons scouts, then a Keener, then a pack. Every `noise_interval` seconds
  it is heard as a sound of loudness `noise` (18 m): Hollowed nearby investigate.
* **Wires** cost one spool per started 10 m (`metres_per_item`), at most 14 m a run; cutting a
  piece's wires gives the spools back, and a destroyed piece's wires are lost.
* **Traps** do damage x the `trap_damage` world setting. A spike pit below `dull_below` of its hit
  points does half.

### Runtime
* **`BaseTechManager`** is a GameWorld module (one line in `MODULES`). It:
  * registers `power.fuel`, `power.toggle`, `power.wire`, `power.unwire`, `power.load` and
    `trap.rearm`, each validating the player, the reach and the state;
  * re-solves the grid on every change (`refresh_grid`), keeping who has power as derived,
    unsaved state;
  * burns fuel and heats the map every `tick_minutes` of game time, and emits the generator noise;
  * draws the wires as one sagging-tube mesh;
  * turns a Hollow killed by `base_trap` or `sentry` damage into `Events.trap_killed` and the
    `trap_kill` XP.
* **`BaseTechNode`** is a child of every base-tech piece (StructurePiece attaches it, as it does
  FarmVisual). It owns what the piece shows and does:
  * **Spike pit**: a trigger box over the pit.
    * A Hollow entering is staked at once (`damage`), held where it fell in for `stuck_seconds`,
      then moved at `slow` x its speed, and staked again every `tick_seconds`.
    * The hold and the slow are applied from the node's physics step at priority 10, after the
      Hollowed's own movement. It rewinds part of the step they just took, so `enemy.gd` needs no
      hook and stays session 2's.
    * Each stake wears the pit (`wear` hit points through BuildingManager.damage_piece). A hammer
      repairs it like any piece.
    * A player who steps in takes `player_damage`.
  * **Deadfall**: armed (`WorldState.base_tech.traps[id].armed`), the first body under it is
    enough to drop the log.
    * A Hollow must be at least `min_weight` (the POI traps' weight classes); a player always is.
    * Everything under it takes `damage` (blunt, a full stagger), a player `player_damage`.
    * The drop is heard (`noise`) and wears the piece.
    * It stays sprung until a player lifts the log (`trap.rearm`).
  * **Tripwire bell**: a Hollow walking through rings it, at most every `cooldown`. It is heard
    (`noise` 34, which draws more of them), and a player within `warn_radius` gets "The tripwire
    bell is ringing: north-west, 40 m."
  * **Traps are walked through**: their collider moves to the interact layer, which the interaction
    ray hits and bodies don't. The Hollowed path into them, and don't stop to claw at them as they
    would at a wall.
  * **Generator**: an engine loop while it runs, and a run lamp.
  * **Work light**: an OmniLight while it is powered and switched on.
    * It joins the `shadow_light_budget` group, so PoiManager casts shadows only from the nearest.
    * It registers with Stimuli: a lit base shows the player to the Hollowed.
    * The lamp's glow materials light through PropLights.
  * **Motion floodlight**: powered, it scans every 0.25 s.
    * A Hollow within `detect_range` turns its head toward it and lights a SpotLight for
      `hold_seconds`.
    * A player within `warn_radius` is told where (at most every `warn_cooldown`).
  * **Nail sentry**: powered and loaded, every `interval` it shoots the nearest Hollow it can see
    within `range`.
    * Each shot is one nail (`ammo_item`, up to `magazine`), `damage` pierce with a light stagger,
      and is heard (`noise`).
    * Its head turns to the target. It tells the player when it runs empty.
* **Interaction** goes through StructurePiece's prompts:
  * interact does the obvious next thing: fuel, start or stop the generator; switch a consumer;
    load a sentry; lift a deadfall; otherwise the piece's status;
  * hold [X] with a wire spool runs a wire from the piece, then connects it on the next one (the
    pending start is presentation state; `power.wire` validates both ends);
  * without a spool, hold [X] tops up a running generator or cuts a piece's wires.
* **Progression**:
  * XP sources `trap_kill` (10) and `wire_power` (3);
  * a `trap_kill` directive event (targets: structure ids), with "Let your traps do the work"
    (three kills) as chapter 3's eighth directive;
  * the world settings `trap_damage` (The Hollowed) and `power_fuel_use` (Survival);
  * Field Manual: a "Traps and power" survival page and the "Power" blueprint category.

### Saves
* **`WorldState.base_tech`** = `{traps: {piece id: {armed}}, power: {piece id: {on, fuel, ammo}},
  wires: [[piece id, piece id, spools]]}`.
* It is written as it changes and loads empty from saves without it, so there is **no version
  bump**.
* A state missing its def's keys starts over. States and wires whose structure is gone are pruned at
  load. Who has power is never saved: it is solved again from the state.

### Models (`tools/assetgen`)
* `base_tech.py` with the catalog `base_tech.py` makes the seven pieces and five items; the
  schematics are `item_paper`'s.
* Moving parts are separate nodes with their pivots on the axis the game moves them about: the
  deadfall's `log` at its centre, the floodlight's and sentry's `head` at the pan axis.
* Materials reuse existing families: logs, item metals and plastics, garden soil, the roadside lamp
  glow and the lab's genset yellow.
* Sounds are aliases of existing recordings (`audio.json`).
* The models were not built in this stream (TD-244). Every piece has a stand-in from primitives.

## Consequences
* A base can defend itself in its approaches and light itself, at a price the design wants:
  * fuel to scavenge;
  * wire to run;
  * a generator whose noise and heat bring the Hollowed to the lights;
  * traps that wear and need resetting.
* New consumers and traps of an existing kind are JSON entries. A new behaviour is a branch in
  BaseTechNode.
* Tests:
  * `tests/unit/test_base_tech.gd`: roles, states, wire spools, the grid's serving order and
    networks, fuel and heat by load and setting, trap damage, bearings, content wiring and the save
    round trip;
  * `tests/integration/test_base_tech_commands.gd`: every command on real pieces, a lit base going
    dark when the fuel runs out, a sentry's shots and kill credit, the pit's hold and slow, a
    deadfall set off by the physics overlap and lifted again, the bell, and destruction.
* Gaps are TD-239..248:
  * no real pit dug in the terrain;
  * the Hollowed don't see or avoid traps;
  * the Hum's breach planner ignores traps and power;
  * a simplified grid (no batteries, switches or relays);
  * unbuilt models and sounds;
  * the sentry's line of sight and stand-in look;
  * the one-key wiring UI;
  * nothing ticks while unloaded;
  * no ammo or fuel crafting beyond the engine;
  * the floodlight doesn't dazzle.
