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
game/data/materials/<family>.json    material library, one file per family (-> generated .tres)
game/assets/shaders/                 hand-written shaders (code, committed)
game/src/tools/import/generated_scene_post_import.gd   M_<id> -> generated material swap
```

A **Task** owns a list of outputs. Its *input hash* = content of its source files + its params.
`manifest.json` records the hash that produced each output (+ sha256 of outputs). A task rebuilds
only when its hash changes or an output is missing. A Blender model's sources are its runner, its
generator and only the `blender/lib/` modules it imports, directly or through other libs (a static
import scan), so editing `lib/char_fp.py` rebuilds the arms, not every family.
`build_assets.py --adopt` re-keys the manifest to the current hashes for tasks whose outputs
exist and still match their recorded sha256, without rebuilding (after a hashing change).
Blender tasks are batched per generator module
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
  bottom centre, front facing away from the wall (−Y). POIs stand a prop off its wall by this
  (PropDef `back` overrides it for a model that can't follow it); test_poi_wall_gaps.gd measures
  every generated prop against it.
* Export only through `lib.export.export_glb()` (fixed settings, no embedded images).
* **Materials are named `M_<material_id>`** (use `lib.materials.assign*`). Godot swaps in
  `res://assets/generated/materials/<material_id>.tres`, defined in
  `game/data/materials/<family>.json` (ids are global across files: prefix family-specific ids,
  e.g. `furn_*`, `item_*`, `ext_*`; a duplicate id fails the build). Each entry is
  `{shader, textures, layers?, params}`; shaders (`game/assets/shaders/`):
  | shader | use | notable params |
  |---|---|---|
  | `std_surface` | opaque PBR for almost everything | `tint`, `uv_scale`, `roughness_mult/add`, wear/moss `layers` + `wear_amount`, `grime_amount`, `emission_color` + `emission_energy` (screens, LEDs), `light_source` 1/2 + `emission_flicker` (lamp globes and embers that glow, flames that exist, only while the prop's light burns: ADR-0023), `bloom_skin` (where the infected-tier veins may show: Hollowed skin 1, growths 0.8) |
  | `std_glass` | transparent glass / clear plastic (windows, bottles, lenses) | `opacity`, `use_texture_alpha` (grime in albedo alpha), `grime_amount`, `tint` |
  | `retroreflector` | road delineators (bridge guardrail posts): a lobe returns light toward its source, so they flare in your own torch (ADR-0023) | `tint`, `retro` |
  | `foliage`, `bark` | vegetation (wind, seasons, translucency); both answer the Bloom field (ADR-0025) | `translucency`, `alpha_scissor`; `bloom_wilt` + `bloom_wilt_tint`, `bloom_droop`, `bloom_thin` (plants wilt); `bloom_affinity`, `bloom_climb`, `bloom_uv_scale` + maps `bloom_mask_tex`/`bloom_normal_tex`/`bloom_cov_tex` (threads up the bark); wire mesh (chain-link, chicken wire) sets `mip_alpha_scale` 0 and `coverage_dither` 1 so far fences keep their coverage (TD-237) |
  | `fur` (+ `fur_shell`) | wildlife coats and feathers (ADR-0027) | `base/pale/dark_color`, `grain`, `sheen`, `wing_flap`; a spec-level `"shells": {count, length, strand_cells, strand_width, fade_end}` chains `count` next_pass slices of `fur_shell.gdshader` behind the coat (deer, hare: TD-067) |
  | `kit_wall` | POI walls/floors: per-instance finish slices (`docs/POI_KIT.md`) | set up by `PoiParts.kit_material` |
  | `bloom_fungus` | the Bloom's fruiting bodies and mounds: double-sided, translucent margins and gills, faint night glow (ADR-0025) | `translucency`, `gill_tint`, `glow_energy`, `glow_gills`, `glow_felt` + `glow_from` |
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
* **Budgets (triangles)**: small props ≤ 1.5k · furniture ≤ 3k · vehicles ≤ 8k · boulders ≤ 3k
  (+ a decimated `_lod1`) · trees LOD0 ≤ 11k (incl. cards), LOD1 ≤ 3k, LOD2 ≤ 800 · Hollowed
  bodies ≤ 16k (the face takes the largest share) · first-person arms ≤ 6k per arm · ground cover
  (fern ≤ 850, litter ≤ 600, moss ≤ 400, grass patch ≤ 100).
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
* A sound module that imports helpers from another declares it, `@sound(..., sources=["ambience.py"])`
  (beside the module), so editing the helpers rebuilds its sounds (the biome beds do).

## Adding an asset (checklist)
1. Write/extend a generator (`blender/generators/*.py`, `textures/gen/*.py` or `audio/sounds/*.py`).
2. Register tasks (`blender_catalogs/*.py` for models; decorators for textures/sounds).
3. New materials → `game/data/materials/<family>.json` (unique, family-prefixed ids).
4. `python tools/build_assets.py --match <name>` then `make import` and `make preview MODELS=...`.
5. Reference it from content (`game/data/**`) — `make validate` reports missing models.
6. `make assets-determinism --match <name>` before committing a new generator.
