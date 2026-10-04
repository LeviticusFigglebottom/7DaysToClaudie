# ADR-0008: JSON content with typed, validated definitions

**Status**: Accepted (2026-10-04)

## Decision
Content lives in `game/data/<kind>/*.json` and loads into typed `ContentDef` resources
(`ItemDef`, `RecipeDef`, ...) through `DefReader`, which converts JSON types and reports
file-located errors (including unknown-field typos). After loading, every def cross-validates its
references. Packs (`Content.add_pack`) let regions/expansions ship their own data folders.
`make validate` and a unit test fail on any content error.

## Why not .tres
JSON is diff-friendly, trivially authored by tools and future AI sessions, readable by the Python
asset pipeline, and validated with precise messages. Defs are still Resources, so `.tres` content
could be added as another loader later.
