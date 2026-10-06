# Hollowmere

An original open-world survival-horror game set inside the **Cordon**, a quarantined Pacific
Northwest valley where the Bloom hollowed out the townsfolk. Wake at a Remand Program drop site
with a tether on your wrist; fell trees, build from logs, scavenge Pell's Crossing building by
building, and hold out against **the Hum** — the nights when every Hollowed in the valley answers
the ground's call, and remembers how you beat them last time.

Built in **Godot 4.7.2** (Forward+, Jolt) with statically typed GDScript. **Every model, texture,
material, animation and sound is generated procedurally by this repository** (Blender headless,
NumPy/SciPy synthesis, Godot shaders) — nothing is downloaded from asset stores.

## Play
Download a packaged build (Windows or Linux): GitHub Actions → **Build** → the latest run →
`hollowmere-windows` / `hollowmere-linux`. Unzip and run; the zip includes every generated asset.
See `docs/BUILDS.md`.

New to the game? Read the player's guide: [docs/HOW_TO_PLAY.md](docs/HOW_TO_PLAY.md).

A clone opened straight in the Godot editor has **no generated assets** (they are built by
`make assets`, which needs Linux) and draws the world with placeholder shapes; the main menu says
so. Open the project with **Godot 4.7.2** exactly: other versions import and render differently.

## Build from a clean clone (Linux x86_64)
```bash
make setup      # downloads + verifies pinned Godot 4.7.2, Blender 5.2.2, Python deps, fonts, GUT
make assets     # generates every asset into game/assets/generated (first run: about 2½ hours with 3 jobs; incremental after)
make import     # Godot headless import
make test       # unit + integration tests
make run-slice  # play the vertical slice (or: make run)
```
Requirements: `bash`, `make`, `python3` (3.11+), `curl`, `xz-utils`, `unzip`, `flock`; a Vulkan
GPU to play. Headless targets (`assets`, `import`, `check`, `test`, `validate`, `smoke`) need no
GPU. `make help` lists everything.

## Controls
WASD move · Shift sprint · C/Ctrl crouch · Space jump · E interact (hold to search) · LMB use/attack/place ·
RMB block/consume · R rotate piece · V log pose · X cancel (hold on a placed blueprint to take it down) · G drop ·
F light · 1–6 or mouse wheel toolbelt · Tab/I salvage roll (inventory/crafting) · B field manual · T tether ·
F5/F9 quicksave/load · F12 screenshot · Esc pause · F1–F7 debug tools (docs/DEBUG_TOOLS.md).

## Documentation
* `CLAUDE.md` — how to work in this repo (conventions, how to add things, gotchas)
* `docs/DESIGN.md` — game design: pillars, loops, novel systems, regions, POI roster
* `docs/ROADMAP.md` — milestones and status
* `docs/adr/` — architecture decisions
* `docs/ASSET_PIPELINE.md`, `docs/POI_KIT.md`, `docs/POI_AUTHORING.md`, `docs/CHARACTERS.md`,
  `docs/REGIONS.md`, `docs/DEBUG_TOOLS.md`, `docs/TECH_DEBT.md`
* `THIRD_PARTY.md` — tools, engine, test addon and fonts with licenses

## License
Project code and generated content: all rights reserved by the project owner unless stated
otherwise. Third-party components keep their own licenses (THIRD_PARTY.md).
