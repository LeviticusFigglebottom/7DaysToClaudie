# ADR-0009: POI spec DSL compiled to geometry; grid-graph route validation

**Status**: Accepted · 2026-10

## Context
POIs are central (7DTD-style): many distinct authored buildings, tiers, an intended route with
sleepers/traps/loot room/shortcut, dense dilapidated dressing, all validated. Authoring every
building as a hand-placed Godot scene does not scale for an LLM-driven team or for RWG reuse,
and can't be validated structurally.

## Decision
* Buildings are **data** (`data/pois/buildings/*.json`): plans of room letters per level,
  openings on cell edges with states (closed/locked/locked_inside/barricaded/boarded/broken...),
  stairs/ladders/drop holes, props, sleepers, pickups/notes, traps, lights, decals, an ordered
  **route**, the **loot room** and **shortcuts** (docs/POI_AUTHORING.md).
* `PoiLayout` compiles a def into a cell/edge model; `PoiValidator` walks it as a graph
  (rooms + a yard ring; doors, breaches, broken windows, stairs, ladders, one-way drops; keys
  collected when reachable; bolts that open only from inside) and checks route completability,
  loot room reachability/container, sleeper placement, props vs route corridor, footprint and
  budgets. It runs in `make validate`, GUT and the F6 visualiser.
* `PoiBuilder` assembles the generated modular kit (docs/POI_KIT.md) into per-piece MultiMeshes
  with per-instance finishes (texture-array slices + decay), one merged collision shell,
  interactive pieces (doors, glass, barricades, loot props, ladders, trip lines), roofs, porch,
  props and room-aware clutter scatter. A hand-authored scene (`"scene"`) can override.
* Frameworks (`data/pois/frameworks`) describe lots/streets/fixtures; the composer grades and
  paints framework streets into the terrain; `PoiManager` places and streams POIs and sleepers.

## Consequences
+ Buildings are diffable, reviewable, validated in CI, reusable by RWG, cheap to render.
+ Route/loot/sleeper mistakes are caught before play.
− 1 m grid + kit vocabulary limits architectural variety (diagonals, curved walls) — add kit
  pieces/plan glyphs when needed.
− Physics props are static in M1 (TECH_DEBT).
