# ADR-0006: Stability-propagation structural integrity

**Status**: Accepted (2026-10-04)

## Context
Player structures (and destructible POI pieces) need believable support: unsupported pieces
collapse, spans have limits, damage cascades — at interactive speed in GDScript.

## Decision
`StructureGraph`: pieces are nodes, links are `ON` (rests on, vertical) or `SIDE` (joined).
Grounded pieces have stability 1.0. Stability propagates outward by max-propagation
(Dijkstra on `1 - s`): resting on a piece costs the piece's `vertical_loss`, sideways/hanging costs
`1 / max_span`. Pieces at ≤ 0 collapse. Removal recomputes only the affected connected
components. Parameters come from `StructureDef` (material tiers differ in span and loss).

## Consequences
* Easy to explain in a debug "structural view" (colour by stability) and to unit test.
* Not a stress solver: no torque/load accumulation. Good enough for M1–M3; revisit if building
  depth demands it.
