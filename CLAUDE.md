# CLAUDE.md — working on Hollowmere

Hollowmere is an original open-world zombie-survival horror game (The Forest / Sons of the Forest
meets 7 Days to Die) in **Godot 4.7.2** with **statically typed GDScript**. Every asset is generated
by this repo's code — never download or import third-party art/audio (see THIRD_PARTY.md).
Read `docs/DESIGN.md` (what we are building), `docs/ROADMAP.md` (where we are) and the ADRs in
`docs/adr/` (why things are the way they are) before large changes.

## Quick start
```
make setup        # pinned Godot + Blender + Python venv + fonts + GUT into .tools (once)
make assets       # regenerate every model/texture/material/sound (incremental, cached by input hash)
make import       # Godot headless import (+ self-repair of models imported before their materials)
make check        # compile every script (fast)
make test         # GUT unit/integration tests (JUnit in build/test-results)
make validate     # content cross-references + every POI (route, loot, sleepers, footprint, budget)
make smoke        # headless end-to-end slice run (~30–80 s): fell, carry, build, craft, night, Hum, save/load
make run-slice    # play the vertical slice (Hum on night 3)
make screenshots  # visual QA suite under Xvfb + software Vulkan (slow) -> build/screenshots
```
CI (`.github/workflows/ci.yml`) runs setup → assets → validate → test.

## Repository map
| Path | What |
|---|---|
| `game/` | Godot project (`project.godot`, main scene `src/app/main.tscn`) |
| `game/src/core/` | Autoloads: `Log`, `Events` (signal bus), `Content` (ContentDB), `Settings`, `Game` (session + **command bus**); session/state models; save system; ids/rng utils |
| `game/src/app/` | `GameWorld` (in-game root: threaded world load, module wiring, survival ticking, sleep/death/respawn) |
| `game/src/worldgen/`, `game/src/world/` | Region composition, terrain (heightmap chunks + SDF volumes), vegetation, water, environment/weather/clock, loose items, FX |
| `game/src/player/` | Controller, interaction ray, equipment/combat, viewmodel, player command handlers |
| `game/src/building/` | Blueprints, freeform log snapping, structural graph, damage/collapse, stations |
| `game/src/ai/` | Stimulus fields, Hollowed (enemy body/brain), nav tiles, Hum director + flow field + horde memory, heat |
| `game/src/poi/` | POI DSL compiler, validator, kit builder, manager, roof builder, interactive pieces |
| `game/src/ui/` | HUD, salvage roll (inventory/crafting/containers), field manual, tether |
| `game/src/debug/` | F1–F7 debug tools (docs/DEBUG_TOOLS.md) |
| `game/src/tools/` | Editor import script, CLI tools (`cli/*.gd`) |
| `game/data/` | **All content as JSON** (items, recipes, structures, blueprints, enemies, loot, species, biomes, weather, props, POIs, frameworks, configs, materials) |
| `game/world/main_map/` | World + per-region data (`regions/<cell>_<name>/region.json`) |
| `game/tests/` | GUT tests (`unit/`, `integration/`) |
| `tools/assetgen/` | Procedural asset pipeline (Blender generators, texture/audio synthesis, catalogs) |
| `docs/` | Design, roadmap, ADRs, pipeline/kit/POI/character contracts, debug tools, tech debt |

## Conventions
* **Typed GDScript everywhere** (`var x: int`, typed arrays, return types). Tabs. `class_name` for
  reusable types. Comments explain *why*; doc comments (`##`) on every class.
* **Data-driven**: gameplay numbers live in `game/data/**.json` (typed defs in
  `src/core/content/defs/`, unknown fields are errors, cross-refs validated). Add content by adding
  JSON — no code change. `_doc` / `_`-prefixed keys are comments.
* **State vs presentation (ADR-0003)**: authoritative state lives in `GameSession` / `WorldState` /
  `PlayerState`. Anything that changes state for a player goes through
  `Game.execute(&"domain.verb", args)` (handlers in PlayerActions, BuildingManager...), returning
  `{"ok": bool, ...}`. UI never mutates state directly.
* **Deterministic ids and RNG**: `Ids.hash64/derive_seed`, `session.rng.stream(name)` /
  `keyed(key)`. Same seed ⇒ same world, scatter, loot rolls, Hum plans.
* **Saves (ADR-0005)**: versioned JSON + chunk blobs; store only differences from the
  deterministic world. Bump `SaveSystem.CURRENT_VERSION` and add a migration when formats change.
* **Events**: cross-system notifications go through `Events` with plain data arguments.
* **Threads**: worker tasks (`WorkerThreadPool`) must not touch the scene tree; join them in
  `_exit_tree`. Use `ContentDB.instance` (not `/root/Content`) from threads.
* **Assets**: model ids are `models/<family>/<id>.glb` under `game/assets/generated/` (gitignored);
  glTF materials named `M_<id>` are swapped for `assets/generated/materials/<id>.tres` at import.
  Always keep a procedural fallback so the game runs before `make assets`.
* **Commits**: small and meaningful; message body explains the why; end with the session's
  attribution lines. Never commit `game/assets/generated/` or `.tools/`.

## How to add …
* **Item / recipe / structure / blueprint / enemy / loot table / species / biome**: add a JSON def in
  the matching `game/data/<kind>/` folder (see existing files and the def's `_fields()`); run
  `make validate test`. Models referenced by id must exist in an asset catalog.
* **A model / texture / sound**: add a generator + catalog entry in `tools/assetgen/` (see
  docs/ASSET_PIPELINE.md); run `make assets import`; preview with `make preview MODELS="..."`.
  Declare extra input files with `sources=[...]` so edits trigger rebuilds.
* **A POI**: `game/data/pois/buildings/<id>.json` following docs/POI_AUTHORING.md; pick it from a
  framework lot or place it as a region feature; `make validate`; check with F6 in game.
* **A region feature** (lake, cliff, road, POI, biome paint...): edit
  `game/world/main_map/regions/<region>/region.json`; inspect with
  `godot --headless --path game -s res://src/tools/cli/compose_region.gd -- <region>`.
* **A world setting (game rule)**: add an option to `game/data/config/game_rules.json` (type,
  range/values, default, category, label; presets may override it), then read it where it applies
  with `GameRules.current().num/integer/flag/choice("id")` — never cache it beyond a spawn. The New
  Game screen, saves and `--rule id=value` pick it up automatically (ADR-0014).
* **A perk effect / XP source**: put the effect key in a perk rank or attribute `per_level`, read
  it with `progression.modifier(key)` where it applies (character-wide stats go in
  `PlayerState.refresh_derived()`), and give it a label in `FieldManual.EFFECT_TEXT`. XP: add the
  source to `data/config/progression.json` `xp` and call `progression.award(source, times)`
  (ADR-0015).
* **A directive (challenge)**: add a def to `game/data/progression/directives/` (chapter, order,
  event from `DirectiveDef.EVENTS`, optional targets/min_tier, count, reward); a new event kind
  also needs a hook in `DirectiveTracker.setup_world()`.
* **A command**: register in the owning system's setup (`Game.register_command`), unregister in
  `_exit_tree`, validate everything from session state + args.

## Gotchas learned the hard way
* CLI scripts run with `-s` are compiled before autoloads exist: they can't reference classes that
  use `Content`/`Game`/`Events` at compile time. Use a thin SceneTree that `load()`s a runner Node
  after one frame (see `src/tools/cli/slice_smoke.gd`).
* Every headless Godot invocation goes through `flock build/.godot.lock` (Makefile does this);
  don't run two imports at once.
* Godot UIDs use base-34 (a–y, 0–8); generated `.import` sidecars pin deterministic UIDs.
* Uniform arrays can't have default values in shaders — use `const` arrays.
* Godot already has a `MeshLibrary` class: our merged-mesh cache is `ModelLibrary`.
* A model imported before its material `.tres` existed keeps the placeholder material; `make
  import` runs `verify_imports.gd` to re-import such models.
* `ResourceLoader.load(..., CACHE_MODE_IGNORE)` on scripts used by autoloads crashes the VM.
* Software Vulkan (lavapipe) renders correctly but slowly (minutes per screenshot).
* A Control already in the tree (e.g. anchoring itself in `_ready`) must use
  `set_anchors_and_offsets_preset()`: plain `set_anchors_preset()` keeps the current (0x0) rect.
* A lambda connected to a RefCounted's own signal must not capture that object (state ->
  connection -> lambda -> state is a cycle that leaks); bind ids instead.

## Status
See `docs/ROADMAP.md` (milestone checklists) and `docs/TECH_DEBT.md`. Visual QA images:
`make screenshots` → `build/screenshots/`.
