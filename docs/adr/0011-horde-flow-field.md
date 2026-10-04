# ADR-0011: Hum pathing — one weak-point flow field over structure costs

**Status**: Accepted · 2026-10

## Context
Horde nights put dozens of Hollowed against a player base. Per-agent pathfinding on a navmesh
that fully encloses the base fails ("no path") and doesn't express 7DTD's signature behaviour:
attackers target the weakest part of the defences. We also want the horde to *learn* between
nights (HordeMemory, novel system #2).

## Decision
`FlowField` integrates travel cost (Dijkstra, 8-neighbour, 1.5 m cells, ~75 m radius) from the
player's position over a grid around the base: slope penalty, deep water impassable, and
**structure cells passable at a cost ∝ remaining hit points** (`structure_cost_per_hp`). Every
attacker follows the field downhill; bumping into a structure switches it to BREAK. The field is
rebuilt on a worker every ~3 s, so damaged walls become cheaper and the horde converges on the
breach. `HumDirector` spawns waves from `HordeMemory.plan()` (sectors, roles, mix), tallies kills,
breaches and causes per sector and files the report, so the next Hum flanks killing fields and
sieges the wall that held. The same plan (seeded by the day) is the tether's forecast.

## Consequences
+ O(cells) once per rebuild for any number of attackers; weak-point targeting emerges.
+ Deterministic and unit-tested (`test_flow_field.gd`).
− Grid resolution (1.5 m) is coarse for tight interiors; inside POIs agents use the navmesh.
− Multi-level bases (platforms, roofs) are flattened to the ground plane (M3: layered fields).
