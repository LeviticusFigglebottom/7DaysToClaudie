# Asset Pipeline

Every model, texture, material, sound and icon in Hollowmere is **generated from source scripts in
this repo**. No downloaded or asset-store content (fonts are the only third-party content; see
`THIRD_PARTY.md`). One command rebuilds everything:

```bash
make assets          # incremental: python tools/build_assets.py + godot import + godot bakes
make assets-force    # from scratch
make assets-list     # every task and whether it is up to date
make assets-determinism   # rebuild into a scratch dir, compare sha256 with the manifest
make preview MODELS="rocks/boulder_a props/chair_kitchen" PREVIEW_ARGS="--grid"   # in-engine QA renders
```

Outputs land in `game/assets/generated/` (gitignored). Nothing in there is ever edited by hand.

## How it works

```
tools/build_assets.py            orchestrator (incremental, parallel, deterministic)
tools/assetgen/
  core/                          paths, hashing (FNV-1a shared with the game), manifest, .import writer,
                                 Task model, Blender batch runner
  catalog.py                     collects tasks from every family below
  textures/
    texlib.py                    numpy toolkit: tileable spectral/value/Worley noise, warp, height->normal,
                                 cavity AO, colour gradients, PBR set writer
    registry.py                  @texture(...) decorator
    gen/*.py                     texture generators (one module per family)
    materials.py                 texture tasks + the material-library task
  audio/
    dsp.py                       synthesis toolkit (oscillators, noise colours, envelopes, filters, modal
                                 resonators, formants, reverb, WAV writer)
    sounds/*.py                  sound generators (one module per family)
  blender/
    runner.py                    executed inside Blender for a batch of tasks
    dev_preview.py               build one generator + Cycles preview (no GPU needed)
    lib/                         shared bpy helpers (common, primitives, materials, vcolor, uv, lod,
                                 fracture, export, preview)
    generators/*.py              Blender generators: build(params, outputs)
  blender_catalogs/*.py          task lists for the Blender generators (one per family)
  docs/                          documentation images generated from data (main-map sketch)
game/data/materials/materials.json   material library definition (-> generated .tres)
game/assets/shaders/                 hand-written shaders (code, committed)
game/src/tools/import/generated_scene_post_import.gd   M_<id> -> generated material swap
```

A **Task** owns a list of outputs. Its *input hash* = content of its source files + its params.
`manifest.json` records the hash that produced each output (+ sha256 of outputs). A task rebuilds
only when its hash changes or an output is missing. Blender tasks are batched per generator module
(one Blender process per batch). The orchestrator writes a Godot `.import` sidecar next to each
output with a **deterministic UID** (FNV-1a of the `res://` path, Godot base-34 alphabet) and the
right import settings (VRAM compression, normal maps, audio loops, glTF post-import script).

## Conventions (all generators MUST follow)

### Determinism
* All randomness from seeded RNGs (`common.rng(seed)` / `texlib.rng(seed)` / `random.Random(seed)`).
  Never time, never unseeded `random`, never iteration over unordered sets.
* Same version + same params ⇒ byte-identical output. `make assets-determinism` checks it.
* Variants are params: e.g. `boulder_a..f` = same generator, different `seed`/`size`.

### Models (Blender → glTF → Godot)
* Units: metres, real-world scale. Blender Z-up.
* **Front faces Blender −Y** (becomes Godot +Z = `Vector3.MODEL_FRONT`).
* **Origin at bottom centre** of the footprint. Wall-mounted props: origin on the wall plane,
  bottom centre, front facing away from the wall (−Y).
* Export only through `lib.export.export_glb()` (fixed settings, no embedded images).
* **Materials are named `M_<material_id>`** (use `lib.materials.assign*`). Godot swaps in
  `res://assets/generated/materials/<material_id>.tres`, defined in
  `game/data/materials/materials.json`. Add new ids there (and textures in `textures/gen`).
* **Vertex colour `Color` (COLOR_0)** — always written via `lib.vcolor`:
  | channel | meaning |
  |---|---|
  | R | baked ambient occlusion (`bake_ao`) — 1 open, 0 occluded |
  | G | wear / convex-edge mask (`bake_wear`) — chips paint, wears wood |
  | B | moss/variation mask (rocks/logs: up-facing moss; props: tint variation) |
  | A | foliage wind weight (0 rigid base → 1 free tip); 1.0 for non-foliage |
* **UVs**: tiling materials use metre-scaled UVs (`uv.box_project(scale=...)`,
  `uv.cylinder_project` for bark/logs/pipes). Foliage cards map into atlas regions of their
  foliage texture (`uv.planar_project(rect=...)`).
* **Collision proxies**: extra objects named `<name>-convcolonly` (convex hull, preferred) or
  `<name>-colonly` (trimesh, static only). Boxes for furniture, hulls for rocks, none for grass.
* **Budgets (triangles)**: small props ≤ 1.5k · furniture ≤ 3k · vehicles ≤ 8k · rocks ≤ 1.8k ·
  trees LOD0 ≤ 9k (incl. cards), LOD1 ≤ 3k, LOD2 ≤ 800 · characters ≤ 10k.
* **LODs**: Godot auto-generates mesh LODs on import. Vegetation ships explicit LODs as separate
  files: `<id>.glb`, `<id>_lod1.glb`, `<id>_lod2.glb` (impostors are baked in Godot by `make bake`).
* **Condition variants** (props/kit): `<id>` (clean), `<id>_worn`, `<id>_destroyed` — or one model
  plus shader wear (`instance_wear`) when geometry does not change.
* **Fracture**: destructible pieces export chunks as `<id>_frac.glb` (objects `chunk_00..`) using
  `lib.fracture.fracture()`; inner faces get an inner material (`wood_raw`, `brick`, ...).
* Characters: one armature named `Armature`, bone names per `docs/CHARACTERS.md`, actions named
  `idle`, `walk`, `run`, `attack_a`, ... exported with `export_glb(..., animations=True, skins=True)`.

### Textures
* Tileable, power-of-two (512–2048). Albedo sRGB; normals tangent-space **OpenGL (+Y green up)**;
  ORM packed (R = AO, G = roughness, B = metallic). Foliage/decals: albedo RGBA (alpha cut-out).
* Register with `@texture("name", size=..., seed=...)` in `textures/gen/<family>.py`; write files
  with `texlib.save_pbr_set(out, albedo, height, rough, ...)`.
* Texture arrays (wall/floor finishes for POI kits): `kind="array"`, vertical strip of slices.

### Audio
* Mono 16-bit WAV, 44.1 kHz (ambience beds may be stereo). Peak-normalized to −1 dBFS, with short
  fades (no clicks). Loops must be seamless (`loop=True` in the task; generator crossfades the seam).
* Variants are numbered `<id>_01.wav`, `<id>_02.wav`, … — the Audio autoload picks one at random.
* Ids are paths under `audio/`: `sfx/axe_chop_wood`, `amb/forest_day`, `voice/hollow_groan`, `ui/page_turn`.

## Adding an asset (checklist)
1. Write/extend a generator (`blender/generators/*.py`, `textures/gen/*.py` or `audio/sounds/*.py`).
2. Register tasks (`blender_catalogs/*.py` for models; decorators for textures/sounds).
3. New materials → `game/data/materials/materials.json`.
4. `python tools/build_assets.py --match <name>` then `make import` and `make preview MODELS=...`.
5. Reference it from content (`game/data/**`) — `make validate` reports missing models.
6. `make assets-determinism --match <name>` before committing a new generator.
