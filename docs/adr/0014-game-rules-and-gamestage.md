# ADR-0014: World settings (game rules), gamestage and difficulty scaling

**Status**: Accepted · 2026-10

## Context
Players should tune almost everything about a run, as in 7 Days to Die's game options (day length,
horde frequency and size, zombie speed by day and night, loot abundance and respawn, XP rate,
death penalty...), and the world should push back harder the longer and better they play
(gamestage). Before this, tuning lived in scattered configs and three hard-coded game modes, and
nothing scaled enemies with progress.

## Decision
* **Schema in data**: `data/config/game_rules.json` lists every option (type, range or values,
  default, category, label) plus difficulty **presets** (Drifter, Survivor, Remanded, Hollowed,
  Rooted) and lookup tables (speed factors, sleeper wake factors).
* **Resolution once per run**: option defaults ← game mode `rules` (`game_modes.json`) ← preset ←
  the player's overrides, coerced and clamped to the schema. The result (`GameRules`) is stored in
  `GameSession.rules` and saved; on load, saved values win and options added later take the
  preset's value, so old saves keep working.
* **Read live, never cached across a run**: systems call `GameRules.current()` (falls back to
  defaults when no session exists, so unit tests and menus work). Enemies capture their
  multipliers at spawn.
* **UI generated from the schema**: the main menu's New Game screen (`NewGamePanel`) lists modes,
  presets and every option by category; the command line takes `--preset` and `--rule key=value`.
* **Gamestage** (`GameSession.gamestage()`) = (player level + days survived × `gamestage_days_weight`)
  × `gamestage_bonus`. It is the single difficulty scaler for spawn composition, infected tiers,
  Hum budgets and loot quality (the 7 Days "gamestage" / "loot stage").
* Speeds are rules relative to each period's designed default (`speed_scale`), so enemy types keep
  their relative pace (a Lurcher stays faster than a Hollow at every setting).

## Consequences
+ A new tunable is one schema entry plus one `GameRules.current()` read; the New Game screen,
  saves, CLI and tests pick it up automatically.
+ Difficulty presets are data, not code paths.
− Every system that reads a rule must do so at the moment it applies it (no stale copies); tests
  cover the resolution order and the clock/loot/session integrations (`tests/unit/test_game_rules.gd`).
− Changing an option mid-run is not supported yet (the settings screen exists only at new game).
