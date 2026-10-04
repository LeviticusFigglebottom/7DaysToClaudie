# Debug tools

Available in debug builds (and exports with the `debug_tools` feature). Implemented in
`game/src/debug/debug_overlay.gd`; flags live on the `DebugTools` autoload.

| Key | Tool |
|---|---|
| **F1** | Debug menu: spawn Hollow/Lurcher/Keener/Dragger or a pack, kill nearby; give kits (axe+hammer, logs, building materials, revolver, food, bandages); time (+1 h, +6 h, dawn/noon/dusk/midnight, start/end the Hum, time ×10); weather presets; teleports (drop site, Pell's Crossing, Okafor farm, pond, cliffs, bridge); toggles (god mode, invisible to Hollowed, no hunger); quicksave/screenshot; **seed viewer** (world seed, region, biome/surface/vegetation at your feet, terrain hash, placements, clock, heat) |
| **F2** | Free camera (WASD, mouse, Shift = fast, E/Q = up/down); terrain streams around the camera |
| **F3** | AI overlay: per-Hollowed label (type, state, hp, awareness), line to its current target, Hum flow-field arrows around the base, heat-map cells |
| **F4** | Performance overlay: FPS/frame time vs the 60 FPS budget, draw calls, primitives, objects, video/static memory, node count, physics/process time, Hollowed alive, graphics preset |
| **F6** | POI route visualiser: the validator's walked route (green), numbered waypoints with labels, sleepers, loot-room cells, validation errors floating over the building |
| **F7** | Structural view: stability % and hit points over every building piece within 40 m |
| F5 / F9 | Quicksave / quickload · F12 screenshot (user://) |

Headless tools (see the Makefile): `make smoke` (end-to-end slice run), `make validate`
(content + POIs), `make check` (compile every script), `make test`, `compose_region.gd`
(terrain inspection images in build/region_preview).
