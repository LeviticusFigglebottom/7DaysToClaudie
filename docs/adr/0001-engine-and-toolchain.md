# ADR-0001: Godot 4.7.2 Forward+, Jolt physics, pinned toolchain

**Status**: Accepted (2026-10-04)

## Context
The brief requires the latest stable Godot 4.x, Forward+ and Jolt if available, plus a headless
build for CI. On 2026-10-04 godotengine.org listed **4.7.2-stable** as current (4.8 is in dev
snapshots). Jolt has been built into Godot since 4.4 (`physics/3d/physics_engine="Jolt Physics"`).
Godot 4 has no separate server binary: the standard Linux editor binary runs with `--headless`.
GitHub release pages were not reachable from the build container; the official
`downloads.godotengine.org` redirect was. Blender 5.2.2 LTS is the newest Blender release.

## Decision
* Pin Godot 4.7.2-stable (linux x86_64) and Blender 5.2.2 in `tools/versions.env` with checksums;
  `make setup` installs them into `.tools/` (gitignored) and verifies them.
* Renderer: Forward+ (`rendering/renderer/rendering_method="forward_plus"`), Vulkan.
* Physics: Jolt (`physics/3d/physics_engine="Jolt Physics"`), 60 Hz.
* Headless automation uses the same binary with `--headless`; rendering checks (screenshots,
  previews, icon/impostor bakes) run under Xvfb with Mesa's software Vulkan (lavapipe).

## Consequences
* Reproducible builds across machines and CI; upgrades are one-line changes + checksum.
* The Godot SHA-512 is trust-on-first-use from the official download host (TD-001) until the
  official SUMS file can be fetched from GitHub releases.
* Software Vulkan renders correctly but slowly; real-GPU performance must be profiled on hardware
  (TD-003).
