# ADR-0004: Statically typed GDScript; criteria for native code

**Status**: Accepted (2026-10-04)

## Context
GDScript is the default; C#/C++ GDExtension are allowed for hot paths if justified and the build
stays reproducible. GitHub (godot-cpp releases) was unreachable from the build container and a
native toolchain would complicate CI and every contributor's setup.

## Decision
* All game code is **statically typed GDScript** (typed vars, typed arrays, typed signatures;
  `untyped_declaration` warning enabled). Hot loops use Packed*Arrays and run on WorkerThreadPool
  threads (terrain meshing, SDF meshing, worldgen, flow fields).
* A system moves to a C++ GDExtension only with **profiling evidence** that it misses its budget
  on target hardware after algorithmic fixes. First candidates: hydraulic erosion for RWG (M3), SDF
  marching cubes for large cave edits, flow fields for 100+ unit Hums.

## Consequences
* Zero native build steps today; everything runs from a clean clone with the pinned Godot binary.
* Some systems are slower than native; tracked in TECH_DEBT (TD-004).
