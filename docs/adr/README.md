# Architecture Decision Records

One file per decision: context → decision → consequences. Supersede rather than edit history
(add a new ADR and mark the old one "Superseded by ADR-XXXX").

| ADR | Title | Status |
|---|---|---|
| [0001](0001-engine-and-toolchain.md) | Godot 4.7.2 Forward+, Jolt, pinned toolchain | Accepted |
| [0002](0002-procedural-asset-pipeline.md) | Procedural, reproducible asset pipeline; generated binaries not committed | Accepted |
| [0003](0003-multiplayer-ready-state.md) | Authoritative state vs presentation, command bus, deterministic ids | Accepted |
| [0004](0004-language-gdscript.md) | Statically typed GDScript; criteria for native code | Accepted |
| [0005](0005-save-format.md) | Versioned, migratable, chunk-based saves | Accepted |
| [0006](0006-structural-integrity.md) | Stability-propagation structural model | Accepted |
| [0007](0007-terrain-hybrid.md) | Heightmap chunks + smooth SDF volumes for digging/caves | Accepted |
| [0008](0008-json-content.md) | JSON content with typed, validated definitions | Accepted |
| [0009](0009-poi-spec-dsl.md) | POI spec DSL compiled to scenes; grid-graph route validation | Accepted |
| [0010](0010-test-framework.md) | GUT 9.7.1 vendored via jsDelivr | Accepted |
| [0011](0011-horde-flow-field.md) | Hum pathing: weak-point flow field over structure costs | Accepted |
| [0012](0012-stimulus-fields.md) | Shared perception through stimulus fields | Accepted |
| [0013](0013-world-coordinates-regions.md) | World coordinates, regions and streaming | Accepted |
