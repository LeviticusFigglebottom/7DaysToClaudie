# ADR-0058: Companion Ezra Vane: follow, guard, gather and fetch

**Status**: Proposed · 2026-10 (session 2)

## Context
DESIGN §3 and the M2 roadmap promise one companion: **Ezra Vane**, an earlier Remand convict and an
ex-lineman, who can follow, gather, guard and fetch. It is the biggest M2 gap. Nothing in the code is
a friendly character yet:
* `Enemy` bodies only ever target the player; the Ashen are an `Enemy` with an `AshenMind` plug-in
  (ADR-0048) and fight the Hollowed through `EnemyFoes` (one `foe`, `FactionDef.hostile`).
* The quartermaster is presentation only (an `EnemyVisual` behind a counter), with idle, talk and
  look clips. The living Ashen bodies have living-human locomotion, attacks, hits and deaths
  (`living_anim.py`).
* Every gathering and inventory command acts on a `PlayerState` (`_player(args)`); harvesting takes a
  `Player`; tree hits and digging award XP only to a player source.
* NavTiles bakes a 5 × 5 grid of 32 m tiles round the player (about 64–80 m each way).
* There is no order UI, no downed state, and no companion save data. Q, Z, H and the middle mouse
  button are free.

## Decision

### Ezra is an Enemy body with a CompanionMind, faction `remand`
Ezra uses the same body as everything that fights in the game, the way the Ashen do:
* **Body:** `Enemy` with archetype `companion`, faction `remand`, def `ezra_vane` in
  `data/companions/ezra.json`, and a `CompanionMind` (`game/src/companion/`) hooked like `tribe`.
  Navigation, hit zones, damage, the living animation set and EnemyFoes all apply unchanged.
* **Relations:** `remand` is hostile to `hollowed` and to the `ashen` (who kill outsiders); the
  Hollowed and the Ashen therefore pick Ezra as a foe through the existing scan, and he fights them.
  Wolves leave him alone unless he is near their kill.
* **Never the player's enemy:** the mind disables the player as a target (`_perceive` hands off to
  the mind for this archetype), the AI director never despawns, counts or culls him, he takes no
  part in the Hum, and nothing he kills credits the player (EnemyFoes' "nobody's kill") except the
  shared XP below.
* **Look:** `characters/ezra_vane` from the living-character pipeline: a weathered man in his
  fifties in faded Program fatigues under a lineman's harness, climbing spurs on his boots, a hard
  hat on his pack, a grey beard. The clip set is the living fighter's plus `talk` and `look` (from
  `npc_anim`), and new `pickup`, `chop`, `carry_walk`, `downed` and `revive` clips.

### Orders
* **E on Ezra** opens a small order card (a modal clipboard like the trade screen): Follow, Stay
  here, Guard here, Gather (wood, stone or fibre), Fetch, Give me what you carry, Store at base.
* **H (quick order)**: a whistle that toggles Follow / Stay without the card.
* **Look and order:** with the card open, "Fetch" and "Gather" target what the player last looked
  at: a loose item, a log, a tree, a rock or a bush (the interaction ray's last hit), within 60 m.
* All orders go through commands (`companion.order {order, target?}`, `companion.give`,
  `companion.store`), validated from the session state (ADR-0003).

### Behaviour
* **Follow:** he keeps 3–6 m behind and to the side, walks when the player walks and runs to catch
  up. Beyond 120 m, or after a respawn, sleep or load far away, he is placed beside the player out of
  sight.
* **Stay / Guard:** he holds the spot. Guarding, he engages hostiles within 20 m of it and returns.
  Following, he fights what attacks the player or him, and keeps within 15 m of the player.
* **Gather:** within 30 m of the ordered spot he fells small trees (with his own `chop` blows on the
  vegetation collision, near the player only: TD), picks up the logs and sticks, harvests bushes and
  stones, into **his own inventory** (12 slots; logs on his shoulder like the player's two). When
  full he returns to the player and says so, or with "Store at base" he puts it into the nearest
  storage piece of the player's base. Gathering yields count for the player's directives and XP at
  half rate (it is the player's crew).
* **Fetch:** he walks to the target, picks it up and brings it back, then drops it at the player's
  feet (or hands it over if there is room).
* **Fire and light:** he carries a lantern at night, lit while following.
* **Barks:** a few lines in the status bar (no synthesized speech yet): when he sees Hollowed, is
  hurt, is full, can't reach something, is downed.

### Downed, not dead
At zero health Ezra is **downed**: he lies (`downed`), the Hollowed lose interest after a while, and
he bleeds out over `downed.seconds` (180). The player revives him by holding E for 4 s with a
bandage or first aid kit in their inventory (consumed). If nobody revives him he is out: he loses what
he carried and turns up at the player's spawn point (bed or drop site) the next dawn, wounded. The
`death_penalty: permadeath` rule makes his death permanent too.

### Recruitment
He is found, not given. On the main map he waits in a lineman's camp by the power line west of
Larch Hollow (a small authored set piece, `ezra_camp`), barricaded in a line truck with a broken leg
splinted; random worlds place `ezra_camp` once, through the hub's wilderness pool, 300–900 m from
the drop site. Talking to him (E) and giving him a first aid kit or painkillers recruits him; a
directive "Find the lineman" points the way.

### Save
`WorldState.companion` (new key, loads empty; no version bump): `{recruited, position, yaw, health,
downed_t, order: {kind, target?, spot?}, inventory, out_until_day}`, written on `Events.game_saving`
and respawned on load with a fixed id `companion:ezra`.

### Phases
1. Ezra recruited, follow / stay / guard, combat, downed and revive, save, the order card and the
   quick order, his body and clips.
2. Gather, fetch, give and store, with their animations.
3. Barks and a few perks of his own (a lineman: climbs, fixes power, carries more), later.

## Consequences
* A companion who fights reuses everything the enemies already do; EnemyFoes needs to know a
  non-player-hostile target only by faction.
* The gathering and inventory commands gain a second kind of owner, so they take an owner id that
  may be the companion's (small, additive).
* Gaps go in TD-249..258.
