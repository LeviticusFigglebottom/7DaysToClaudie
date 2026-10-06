# ADR-0026: The vault: a lock you open with a combination or cut through, loudly

**Status**: Accepted · 2026-10

## Context
The Pell's Crossing Savings & Loan (tier 3) is the town's richest loot room. A dungeon's loot room
already sits behind a guardian, a trap and a locked door (ADR-0018). A bank vault should make one
more choice concrete: find the combination somewhere in the building, or force the door and pay
for it. The existing lock kinds (`latch`, `padlock`, `chain`, `deadbolt`...) all take a few blows
to beat off. A vault door must not, and forcing it should cost more than time.

## Decision
* **A `vault` lock kind** in the POI DSL (`PoiLayout.LOCK_KINDS`). It is valid only on a 1-cell
  `door` that is `locked` with a `key`, and the key is the combination item, placed somewhere in
  the building (a pickup or a container roll). The validator rejects a vault lock on any other
  opening, so the honest route is always provable: the route reaches the key before the vault.
* **The door is a kit leaf** (`models/kit/door_vault.glb`, `door_vault_broken.glb`, the
  `door_metal` conventions: hinge at the origin, +X 0.82, 2.05 tall) chosen with the opening's
  `model`. A decorative frame prop (`bank_vault_door`: wheel, bolts, collar, no collision) stands
  in the wall face round it.
* **The combination opens it quietly**: interacting with the key in the inventory unlocks it, with
  the extra clank of the bolts withdrawing.
* **Cutting through it is the loud way.** The opening's `hp` is large (1400 at the bank, several
  minutes of an axe). Every blow on a locked vault door:
  * plays a metal hit and sparks instead of splinters;
  * emits an `alarm`-kind sound of loudness `traps.json` `vault.noise` (48), so held ambushers
    within their wake radius rise to it and roaming Hollowed outside hear it;
  * and the **first blow a player lands rouses the whole building**
    (`PoiInstance.alarm(pos, true)`): every trigger fires and every held group rises, as with a set-off
    alarm trap. A Hollowed hitting the door (the Hum) does not rouse it.
  When the hit points run out, the door smashes to its broken leaf as any door does.
* No new save state: the lock state and hit points use the existing door piece records (ADR-0018),
  so this needs no save version bump.

## Consequences
* The bank offers two clean routes: the combination (found by the teller line; see the POI's
  triggers) and a long, noisy fight at the vault. Tuning lives in `traps.json` and the opening's
  `hp`.
* The mechanic is two small hunks in the POI engine (`poi_layout.gd`'s lock check and
  `poi_pieces.gd`'s `Door`). Any other building can use it with data only.
* A cut that rouses the building in one blow is harsh if the player only tests the door. It is
  deliberate, and the interaction text says the door "needs the combination (or cut it open)".
  Revisit after a playtest (TD-059).
