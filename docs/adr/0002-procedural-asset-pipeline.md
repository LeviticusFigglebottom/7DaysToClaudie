# ADR-0002: Procedural, reproducible asset pipeline

**Status**: Accepted (2026-10-04)

## Context
No external content is allowed: every model, texture, sound, animation and icon must be generated
by scripts in the repo, reproducibly, with seeds/params for cheap variants. Generated binaries
should live in a clearly separated directory.

## Decision
* `tools/build_assets.py` orchestrates **tasks** (Blender, numpy textures, DSP audio, material
  library, docs images) contributed by per-family catalogs. A task's input hash (source file
  contents + params) is recorded in `game/assets/generated/manifest.json`; only changed tasks
  rebuild. Blender tasks are batched per generator module; python tasks run in a process pool.
* Outputs go to **`game/assets/generated/` (gitignored)** — the repo stays small and the pipeline is
  continuously exercised. CI caches the directory and rebuilds incrementally.
* Each output gets a Godot `.import` sidecar with a **deterministic UID** (FNV-1a of the res path in
  Godot's base-34 alphabet) and explicit import settings, so scene references never churn.
* Materials are data (`game/data/materials/*.json`) compiled to ShaderMaterial `.tres`; models only
  name materials (`M_<id>`) and a post-import script swaps them in. Textures are tileable sets,
  geometry carries vertex-colour masks (AO/wear/moss/wind).
* Renderer-dependent bakes (item icons, tree impostors) run in Godot (`make bake`) after import so
  they match in-game shading.
* `--check-determinism` rebuilds into a scratch dir and compares hashes.

## Consequences
* A fresh clone must run `make assets` (minutes) before playing; documented in CLAUDE.md/README.
* Generators must be deterministic (seeded RNG, no time) — enforced by the determinism check.
* Git LFS is unnecessary for now; revisit if hand-authored binaries ever appear.
