# ADR-0036: Playable builds: packaged exports with the generated assets, a stand-in mode we test, a load that keeps the window alive

Status: Accepted

## Context

The first human playtest (a fresh clone opened in the Godot editor on Windows) reported three
things: Windows flagged the game "not responding" near the end of the load, every asset was a
primitive stand-in with no textures and no grass, and running up to one of them crashed the game.

* The generated assets (`game/assets/generated/`) are gitignored, and the toolchain that builds
  them (`tools/versions.env`: Linux Godot and Blender, `make assets`) is Linux-only. Any other
  clone runs entirely on `ModelLibrary.make_placeholder` and the other procedural fallbacks.
  Nothing in CI played that mode, and nothing told the player it was not the game.
* After the world loader's worker thread, `GameWorld._on_world_loaded()` built the terrain, the
  environment, twelve modules and the player in one main-thread frame. Measured headless on the
  4-core container: about 15 s, almost all of it the 22 POIs, and 95 % of each POI's build time
  was the `PoiValidator` route search the builder runs to find the route corridor.
* There was no way to hand a player a build: no export presets, no pinned export templates.

## Decision

**1. Players get packaged builds, not the repository.** `game/export_presets.cfg` has Windows
Desktop and Linux x86_64 presets: every resource plus `*.json` (content, world, region data) and
the font licences; `tests/`, `addons/gut/`, `src/tools/cli/` and the editor plugin stay out.
The export templates are pinned in `tools/versions.env` by SHA-512 (checked against the release's
official `SHA512-SUMS.txt`) and installed into `.tools/xdg` (only the six x86_64 files), so an
export never depends on the user's own Godot data dir. `make export` exports both and zips each
with a player readme and `THIRD_PARTY.md` into `build/export/`; it refuses to package without
generated assets unless `EXPORT_STANDIN=1`. The **Build** workflow (dispatch, and pushes to the
integration branch) runs setup, assets, import, export, proves with `tools/export/pck_list.py`
that each `.pck` carries `assets/generated/{models,textures,audio}` and no tests or tools, smokes
the exported Linux pack, and uploads the two zips as artifacts. It reuses ci.yml's caches.
Releases are not published from CI (the owner decides that).

**2. Stand-in mode is a supported, tested mode.** It stays the way a fresh clone runs (the game
must run before `make assets`, CLAUDE.md), but:
* the main menu says so when the vegetation models are missing (`ModelLibrary.generated_share`):
  the world is placeholder shapes, get a packaged build or run `make setup assets` (and a shorter
  note for a partial build);
* the **Stand-ins** workflow (Godot only, no Blender) runs import, check, tests, `make smoke` and
  `make tour` on every push with no generated assets, failing on any `SCRIPT ERROR`;
* `make tour` (`walk_tour.gd`) plays like a person: a survival game, real movement input,
  sprinting into one of every vegetation kind, logs, dropped items, the nearest POIs (swinging and
  using whatever the interaction ray finds), three Hollowed and wildlife.

**3. The main-thread half of the load is spread over frames.** `GameWorld` turns it into boot
steps (`[label, Callable, name]`) run within a 40 ms budget per frame, the loading screen naming
each. A step returning `false` is waiting on a worker thread and runs again next frame; a module
may queue more steps with `boot_steps()`; systems added by a step don't process until the boot
ends (they used to appear in one frame, and their `_process` may assume their neighbours exist).
Pure data moves off the main thread wherever it was a large share:
* `PoiManager` (when its world `is_booting()`) queues each building as a plan step (compile the
  layout on the main thread, since it pins per-run picks in the session, and start its
  `PoiValidator` on a worker thread) and a build step (`PoiBuilder.build(layout, id, checked)`
  with the finished validator). Tools and tests that set up a bare world still build at once.
* The world loader resolves framework lots and generates their houses (`LotPicker.resolve` /
  `def_for`) on its own thread (`WorldLoader.resolve_lots`, handed over as `GameWorld.poi_lots`).
* `TerrainManager.defer_far_tiles` meshes the far tiles in a worker group task.

`LoadMeter` logs the longest main-thread frame of the load, what the loading screen said then and
the slowest steps, and the longest of the first 30 frames in the world. Target: no frame over
about 100 ms on a desktop CPU (the OS flags a window after about 5 s without messages).

## Consequences

* A player downloads a zip, runs the program and gets the real game; the repository is for
  development. A developer on Windows or macOS still sees stand-ins in the editor, and the menu
  says why.
* A regression in the stand-in path fails CI within minutes, without the asset build.
* The load is longer in wall time by a few frames of overhead and shows its progress; the longest
  frame went from ~15 s to ~0.5 s headless on a contended container (the remaining offenders are
  the largest single POI builds, terrain setup and the player scene; see TD-102).
* The playtest crash itself was a reflection probe atlas overflow (more than 64 interior probes in
  view, on the player's Godot 4.7.1 with an RX 9070 XT); the integrator's `interior_probe_budget.gd`
  caps visible probes. `make render-check` renders `valley_overview`, whose frustum holds all 92 of
  the world's probes: with the budget disabled (both caps set to 999, not committed) Godot 4.7.2 on
  lavapipe logs **no** atlas error there. So the overflow did not reproduce on the pinned engine
  here; it may be specific to 4.7.1 or to that GPU's driver. The budget stays as a guard, and the
  render check guards the class of failure (probe atlas, FATAL, crash handler) without proving
  that fix.
* Export templates ignore `-s`, so an exported pack is smoked with the editor binary:
  `godot --headless --main-pack Hollowmere.pck -s /abs/path/slice_smoke.gd` (the wrappers load
  their runner from beside themselves for this).
