# ADR-0003: Multiplayer-ready state — authority, commands, deterministic ids

**Status**: Accepted (2026-10-04)

## Context
Ship single-player first, but co-op must be addable without a rewrite.

## Decision
* **Authoritative state** lives in plain serializable models under `GameSession`
  (`PlayerState`, `WorldState` ledger, `WorldClock`, `HordeMemory`, `HeatMap`, `IdAllocator`,
  `RngStreams`). Nodes are presentation: they read state and send intents.
* **Command bus**: every state-mutating player intent goes through
  `Game.execute(&"domain.verb", args) -> Dictionary`. Handlers depend only on session state + args.
  Single-player executes locally; a co-op client would forward the same command to the host via RPC
  and apply replicated results. `Game.is_authority()` gates authority-only simulation (AI, spawns,
  loot rolls, structural collapse).
* **Deterministic ids**: authored/world things use content-addressed ids
  (`tree:<chunk>:<index>`, `poi:<instance>`, `ctr:<poi>:<local>`); runtime spawns use the session
  `IdAllocator` (`z:000123`). Never instance ids or node paths.
* **RNG streams** per subsystem derived from the world seed; worldgen uses position-keyed seeds.
* **Events** (`Events` bus) carry plain data (ids, vectors, dictionaries), never node references —
  the same payloads can be replicated.

## Consequences
* A little ceremony for UI actions (commands instead of direct calls) — worth it.
* Physics-driven entities (zombies, debris) are simulated on the authority; co-op will replicate
  transforms (MultiplayerSynchronizer) and use client-side prediction only for the local player.
