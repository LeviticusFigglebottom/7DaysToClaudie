# ADR-0016: One save per run; fires, water and repairs with a cost

**Status**: Accepted · 2026-10

## Context
A second refinement pass audited AI, UI and saves, building and world, balance, the player and the
environment (about 90 findings). Most fixes were plain bugs. A few changed how the game behaves or
how saves are laid out. Those choices are hard to undo once players have saves, so they are
recorded here.

## Decision
* **One save slot per run.** A new game takes the first free `runN` slot (`SaveSystem.new_run_slot()`).
  Every save of that run writes there: manual saves, waking from sleep, dawn after a Hum
  (`Game.autosave()`), and F5. F9 reloads it. The separate `autosave`/`quicksave` slots are gone,
  because they were shared by all runs: a new game overwrote the last one, and after a
  permadeath, quickload brought the run back. Permadeath deletes the run's slot with its `.old`
  backup.
* **No saving while dead.** `Game.save_game()` refuses while the local player is dead: the state is
  mid-penalty (pack on the ground, permadeath slot already deleted).
* **Save files must be portable.** Chunk blob keys contain `:` (`t:3_-4`); files store it as `~`,
  and both spellings load. A `session.json` that is missing or does not parse falls back to the
  `.old` copy kept during the atomic swap. `SaveSystem.last_error` says why a load failed, and
  the menu shows it. The format version did not change: old saves load as they are.
* **Fires burn fuel.** A fuel-burning station (`StationDef.needs_fuel`, the campfire) holds
  `fuel` in game minutes, saved with the piece. It burns with game time, sleep included, adds
  its `heat_per_minute` to the heat map and goes out at zero. Item `fuel` values are real
  seconds of burn, converted at the current day length
  (`fuel × WorldClock.minutes_per_real_second()`), so a log burns about ten real minutes on any
  day-length setting. A new campfire holds `start_fuel` (one hour) of kindling. Feeding happens
  with [G] at the fire, or [E] at an empty one, through `build.add_fuel`.
* **Stream water is dirty.** Lakes and rivers can be drunk from directly (thirst, plus a little
  health damage that Iron Gut reduces) or used to fill empty bottles with stream water that the
  campfire's existing recipe boils clean. Water is renewable, but not free.
* **The Bloom has a fight-off line.** Below `infection.dormant_below` (12), infection fades at
  `fight_off_per_hour`, so one or two bites clear in hours. Above it, infection grows until
  treated. Bleeding clots at 0.005 per game minute, so wounds cost real health and bandages
  matter.
* **Building costs both ways.**
  * A repair without an explicit cost costs a quarter of the piece's build cost.
  * Dismantling (crouch with a hammer, hold [E]) returns half the cost, scaled by remaining
    health; a log comes back whole.
  * Reinforcing takes a second hammer strike within 3 s.
  * A log that falls at once pays no XP and fills no blueprint slot.
* **Crafting XP follows the recipe**: `craft_<category>` in `progression.json` when listed, else
  `craft`. Digging, which is unlimited, pays nothing.
* **Weather stays outside.** `std_surface` and `kit_wall` have a `weather_exposure` instance
  uniform. PoiBuilder batches indoor floors and furniture separately with it at 0, so the global
  `hm_wetness`/`hm_snow` stop at the door.

## Consequences
+ Runs can't overwrite or resurrect each other, and saves move between Linux and Windows.
+ Fires, water, infection and repairs now cost and reward something. All the numbers live in
  data (`stations.json`, `survival.json` including `stream_water` and `stamina.sprint_recover`,
  `progression.json`).
− Old `autosave`/`quicksave` slots still list in the menu as separate entries until deleted.
  New runs no longer create them.
− Fuel and stream water add upkeep. The slice's directive "Build a campfire" teaches feeding it.
− Splitting indoor batches adds at most one MultiMesh per indoor model per POI.
