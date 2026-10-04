# ADR-0005: Versioned, migratable, chunk-based saves

**Status**: Accepted (2026-10-04)

## Decision
* Slot directory `user://saves/<slot>/`: `meta.json` (summary for menus), `session.json`
  (`{save_version, session}` = `GameSession.to_dict()`), `chunks/<key>.bin` (terrain height deltas /
  SDF densities per modified chunk, compressed by their producers).
* The world is regenerated from seed + region data; saves store only **differences** keyed by
  deterministic ids (structures, felled trees, containers, POI states, loose items, chunk blobs).
* Writes are atomic: write `<slot>.tmp`, rename the old slot to `.old`, swap, delete `.old`.
* `SaveSystem.CURRENT_VERSION` + ordered migrations (`from_version -> Callable`). Newer or gapped
  saves are refused with a clear error. Unknown item ids are dropped with a warning, not fatal.
* Numbers that must stay exact beyond 2^53 (seeds, RNG states) are stored as strings.

## Consequences
* Saves stay small and human-inspectable; editing content never invalidates old saves silently.
