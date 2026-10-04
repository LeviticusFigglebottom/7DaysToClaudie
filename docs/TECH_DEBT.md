# Technical debt register

Known shortcuts, with impact and the intended fix. Close an item by deleting it in the commit that
fixes it (git history keeps the record). Severity: **H** blocks a milestone / risks data, **M**
noticeable quality or perf cost, **L** polish.

| ID | Sev | Area | Debt | Fix |
|---|---|---|---|---|
| TD-001 | M | Toolchain | Godot zip SHA-512 is trust-on-first-use from the official download host (GitHub release SUMS file unreachable from the build container). | Verify against `SHA512-SUMS.txt` from the release page when reachable; update `tools/versions.env`. |
| TD-002 | M | Rendering | Visual QA runs on software Vulkan (lavapipe) under Xvfb: correct but slow (~3–4 min per screenshot) and SDFGI/volumetrics are not representative of GPU cost. | Add a GPU runner for `make screenshots` and perf captures. |
| TD-003 | H | Performance | No measurements on a real mid-range GPU yet; the 60 FPS @1080p budget is unverified. Draw-call/primitive numbers come from the F4 overlay under software rendering. | Profile on target hardware (GTX 1660 / RX 6600 class); tune presets (`data/config/graphics_presets.json`), vegetation densities and shadow distances. |
| TD-004 | M | Performance | Heavy work in GDScript: terrain composition (~13 s per 1 km region, cached), vegetation scatter (per chunk, threaded), surface-nets meshing (0.1–0.3 s per volume chunk, threaded), flow-field Dijkstra (~0.2 s, threaded). | Move hot loops to a GDExtension (ADR-0004 criteria) if profiling on target hardware demands it. |
| TD-005 | M | Vegetation | Far-tree impostors use a procedural stand-in atlas; no baking from the real tree models yet. | `make bake`: render each species from FRAMES angles (albedo + normal) into `assets/generated/impostors/`. ImpostorLibrary already loads them. |
| TD-006 | M | Vegetation | Far impostors exist only for built regions; coarse regions show no forest beyond terrain tint. | Scatter coarse regions at low density into cluster impostors (HLOD). |
| TD-007 | M | POIs | All POIs in built regions are built at world load (fine for Pell's Crossing; won't scale). Props are static (no physics props), decals limited to the generated set. | Distance-based POI streaming with threaded building; physics clutter props near the player. |
| TD-008 | L | POIs | Roofs: gable or flat over each level's bounding rectangle (no hip, no L-shaped roofs, no porch roofs). | Roof planner over rectangle decomposition. |
| TD-009 | M | Building | Trapper's Cabin front wall is lintel-only (crawl-height opening) because there are no half logs or door pieces for log walls. | Add half-log and log-door-frame structures + snap profiles. |
| TD-010 | L | Terrain | Heightmap↔volume hand-off: tiny steps (<5 cm) can show at volume column borders on steep ground; `height_at()` ignores volume edits. | Blend border vertices to the heightfield; query volume for height where columns are active. |
| TD-011 | M | AI | Enemies collide with each other physically (jams in doorways); no crowd avoidance. Ladders are not climbed by AI (by design for lofts) and navigation links for vaulting windows are missing. | NavigationAgent avoidance + separation; NavigationLink3D for windows/drops. |
| TD-012 | M | AI | Wandering Hollowed are not persisted (population is re-rolled around the player); sleepers persist via POI state. | Persist wanderer groups in chunk records if it matters for play. |
| TD-013 | L | Audio | Several synthesized sounds are weak (eating/drinking, craft twist/tie, saw rasp, formant voices); string pads in music read synthetic. Reverb zones are global by listener location (interior bus) rather than per-room. | Iterate DSP recipes; per-room reverb areas from POI rooms. |
| TD-014 | L | UI | Salvage roll recipes use 2D ink overlay buttons over the 3D cloth; no drag-and-drop, no item tooltips with stats; tether minimap is per region. | Drag items onto the crafting cloth; full map on the tether with fog of war. |
| TD-015 | L | Pipeline | Fresh-clone first import logs an error for the project font before it is imported (benign). Import option "lossless with mipmaps" missing for sky/star textures. | Import fonts before setting the theme; add the import option. |
| TD-016 | L | Characters | First-person arms and the character rig are generated but the viewmodel still shows held items without arms where the arms model is missing. | Hook `fp_arms` actions into ViewModel (see docs/CHARACTERS.md). |
| TD-017 | M | Save | Structures, blueprints and loose items are restored for the whole world at load (no chunking yet); fine for the slice, not for long games. | Store per-chunk structure/loose records and stream them with terrain chunks (ADR-0005 already allows it). |
| TD-018 | L | Weather | Rain/snow are fog/tint/wetness only: no precipitation particles or puddle normals yet. | GPU particles following the camera + wetness puddles in the terrain shader. |
