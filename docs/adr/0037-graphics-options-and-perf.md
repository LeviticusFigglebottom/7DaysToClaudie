# ADR-0037: Graphics and controls options for real GPUs, and what the first perf pass found

Status: Accepted

## Context

The owner plays on an RX 9070 XT; most players have less. The options screen offered one graphics
preset, mouse, FOV, head bob, volumes, brightness, fullscreen and vsync, and no way to rebind keys.
Nothing had been measured on a GPU (TD-003), and our only renderer is software Vulkan (lavapipe),
whose frame times say nothing about a GPU (TD-002). Some preset keys (`tree_lod_scale`,
`terrain_lod_bias`, `max_shadowed_lights`) were read by no code at all.

## What the pass measured

`perf_capture.gd` (ADR-0036 tooling) measures what does not depend on the GPU:
* **Main-thread CPU**, headless with all assets: process ~1.3–1.8 ms and physics ~3 ms a step at
  five views; sprinting 20 s through streaming forest, no frame over 33 ms (worst 29 ms). Script
  CPU is not the bottleneck.
* **A triangle census** (`--census`): what each source submits within its visibility range, before
  frustum culling and shadow passes. At the drop site on high: 18.9 M triangles, of which 11.4 M
  vegetation (the chunk around the player at full detail: ~340 firs of ~10k triangles; TD-035) and
  6.4 M POIs, whose ~2,400 props and pieces plus their prop batches had **no draw distance**:
  every building in the valley drawn, shadows included, from the forest. Lavapipe's own counter
  agreed: ~17 M primitives and ~950 draw calls a frame at the drop site.
* **The rendered load** (LoadMeter's slow-frame log): no pipeline is compiled at draw time (the
  ubershaders work); the first frames in the world cost what any frame costs.

## Decision

**1. Fix what the census found.** POI props, pieces and prop batches stop at a new graphics
setting `object_distance` (70 / 100 / 140 / 220 m from low to ultra), door-sized ones at 2.5x,
anything over 8 m never; the kit batches keep each building's shape at any range; no dithered
fade (it would draw every prop as transparency). `tree_lod_scale` is now applied (full-detail and
middle tree LOD ends; the last LOD keeps its end where the impostors start), and below 0.5 there
are no full-detail trees: the low preset (0.45) draws LOD1 from 0 m. Drop site: high 18.9 → 14.3 M,
low → 7.0 M triangles submitted.

**2. Options on top of presets.** `Settings.set_graphics_override(key, value)` changes one feature
of the active preset (saved in `settings.cfg` `graphics_overrides`); picking a preset drops them.
The Graphics tab offers render scale, the upscaler (bilinear, FSR 1, FSR 2), TAA, SDFGI,
volumetric fog, SSAO, SSIL, SSR, shadow resolution, softness (`shadow_filter`, new, 1–4 by preset)
and distance, view distance, tree detail, object distance and grass density and distance. Sliders
apply on release (a graphics change rebuilds viewport and environment state). Grass and tree
changes show as the forest around the player rebuilds.

**3. A first run starts on what the GPU can carry**: high for a discrete GPU, low for integrated or
software rendering, medium otherwise (`Settings.preset_for_adapter`), remembered once chosen.

**4. Controls.** The Controls tab lists every player action (debug keys stay out); clicking one
and pressing a key or mouse button makes it the action's main binding, keeping its second key
(Ctrl as well as C) and gamepad bindings; Escape cancels; one button resets all. The pause menu
has a Controls button that opens the panel there.

## Consequences

* Low and medium presets are now genuinely cheaper; before, they differed from ultra only in the
  environment effects and grass.
* Props pop in at `object_distance`; the hysteresis margin keeps them from flickering at the edge.
* Still unmeasured on a GPU (TD-003 stays open). Remaining costs found here: TD-105.
