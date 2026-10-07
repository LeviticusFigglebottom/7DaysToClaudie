# ADR-0055: The living forest: wolf packs and Bloom nests

**Status**: Wolves: Accepted with notes · Bloom nests: Proposed · 2026-10 (session 2)

## Context
The owner wants the forests alive and full of places (WORKBOARD "Round 3 suites"). Two things are
missing between the deer (ADR-0027) and the Hollowed:
* a natural predator that hunts what the player hunts, and hunts the player;
* landmarks in the deep woods that say where the Bloom is strongest and give the player a reason to
  go there.

What exists to build on:
* Hollowed hounds (ADR-0034) are Enemies on a four-legged body with packs, a rallying howl, flanking,
  hit and run, scent tracking and fear of a held flame. The quadruped rig and its action set are
  generated (`animals/hollow_hound_*`).
* Wildlife (ADR-0027) is a separate, lighter system: `Animal` bodies, `WildlifeBrain`, a spawner,
  herds, carcasses the player butchers. Animals read the awake Enemies near them and bolt.
* The Bloom field (ADR-0025) is authored and deterministic, published as shader globals; Bloom mounds
  sit on it.
* EnemyFoes (ADR-0048 phase 2) lets an Enemy fight a hostile Enemy. Nothing lets an Enemy hunt an
  Animal.
* The hub's forest-encounter scatter (ADR-0054) places small set pieces in the woods.

## Decision

### Wolves are Enemies on the hound body, faction `wildlife`
A wolf is an `Enemy` (archetype `hound`, faction `wildlife`, def `grey_wolf` in
`data/enemies/wolves.json`) on a living wolf body (`animals/wolf_a`, `_b`: the hound generator's rig
and clips with a healthy coat, ears up, no Bloom). Everything the hound pack does applies: packs of
3–6 (`spawn_pack`), the rallying howl, flanking, hit and run, scent tracking, keeping off a held
flame. What is different, all data in `data/config/wolves.json`:
* **Not the Bloom.** No infection on a bite (bleed only), no Hum membership, no dawn rooting, no
  heat responses. They are wildlife: hostility to the Hollowed is `FactionDef`-style neutral (they
  avoid them), and the Ashen ignore them.
* **Hunger and prey.** A pack has hunger that rises through the day. A hungry pack hunts deer: a
  `WolfPack` (in `game/src/wildlife/wolves/`) picks the nearest herd the WildlifeManager knows within
  `hunt.range`, sends the pack to flank it, and a wolf that reaches a deer kills it (the Animal's
  `_die`), leaving the carcass. The pack eats (hunger to zero) and beds down by the carcass for a
  while; a player who comes near a feeding pack is warned (growls) and then attacked.
* **The player.** By day a fed pack avoids a player (keeps 40 m, watches). A hungry pack at night, a
  wounded wolf, or a player near a kill is attacked. Wolves follow the player's blood trail
  (scent grid) when the player is bleeding.
* **Fire.** As hounds: a held flame keeps them off in front; a lit campfire or station is a no-go
  zone of `fire.radius` at night (packs circle outside it).
* **Howls.** Packs howl at dusk and at night from their range (sound with no heat), so the forest
  carries them; the first howl of a hunt rallies the pack.
* **Spawning.** Wolves come from the WildlifeSpawner's per-biome tables (`conifer_forest`,
  `burnt_forest`, snow), not the AI director's wanderers: a pack is placed with the deer and saved
  like them (nothing; they re-roll). A `wolves` world setting turns them off.
* **Carcasses.** A dead wolf is a carcass the player butchers (pelt, meat, bone), through the Enemy
  corpse loot table `wolf_remains`.

#### Wolves as built (notes)
* **Data.** `grey_wolf` (`data/enemies/wolves.json`, archetype hound, faction wildlife, pack 3-6,
  bite bleed 0.4 and infection 0, loot `wolf_remains`: a `wolf_pelt` and `raw_wolf_meat` always,
  bone and sinew; new items `wolf_pelt`, `raw_wolf_meat`, `cooked_wolf_meat`, recipes
  `roast_wolf`, `wolf_rawhide_strips`); tuning in `data/config/wolves.json`; world setting
  `wolves` (category world).
* **Spawning.** A new WildlifeDef kind `pack` (`data/wildlife/wolves.json`: `enemy` grey_wolf;
  conifer forest 1.0, burnt forest 0.8, rocky slope 0.4, fen 0.2 — there is no snow biome yet) is
  planned by WildlifeSpawner with the herds; `WolfPacks` (a child of the WildlifeManager) spawns
  the plan through `AIDirector.spawn` (tier normal), wires `Enemy.pack` and `Enemy.wolf`, keeps at
  most `spawn.max_packs`, drops a pack 270 m off (90 m on a Hum night) and remembers packs killed
  off. The director skips wolves as wanderers and in its roaming count, and `allowed_enemy` no
  longer turns a wildlife hound into a Hollow when the hounds setting is off.
* **Behaviour.** `WolfPack` (pack mind: hunger, ROAM / HUNT / FEED / REST, engagement, howls) and
  `WolfHunt` (one wolf: the moving, the bite on an Animal, the fire ring) in `src/wildlife/wolves/`.
  Enemy hooks (5 one-line hunks): the `wolf` var, `wolf.step()` beside the foe step,
  `wolf.ignores_player()` at the head of `_perceive`, no stimulus from a wildlife howl, no
  `zombies_killed` for a wolf. The rule for taking the player on is `WolfPack.wants_player`:
  hungry and close (26 m day / 60 m night), at night unless just fed, wounded (or a mate killed),
  a player staying by the kill after a growl, or a bleeding player whose trail it smells; then
  the hound brain hunts them (rally, howl, flank, hit and run, held flame). A stalking wolf is
  left out of the deer's senses until the rush. Ambient howls (`voice/wolf_howl`) are sound only.
* **Bodies.** `animals/wolf_a` (grey), `wolf_b` (timber, bigger): the hound generator with
  `breed: wolf` (wolf skeleton table, no bones showing or Bloom growths, coat volume: ruff,
  cheeks, breeches, brush; wolf coat masks; amber `eye_wolf`; a level-headed stance); same rig and
  clips. Previews checked in engine.
* Gaps: TD-250..253.

### Bloom nests are world landmarks with a small module
A Bloom nest is a grown mass of Bloom: a knot of roots and shelves round a hollow, pods hanging from
it, the remains of what it took (bones, a pack, a body). A `NestDef` (`data/nests/<id>.json`, new
content kind `nest`) holds its props (generated: `nest_root_mass`, `nest_pod`, `nest_shelf_cluster`,
`nest_remains`), its Bloom zone, the Hollowed it seeds, its loot and its burn.
* **Placement.** Nests are placed by the hub's forest-encounter scatter (ADR-0054) as encounters of
  kind `nest` (the hook: the scatter hands `BloomNests` a placement `{id, def, pos, yaw}`), and
  can be authored in a region as a feature `{"type": "nest", "def": ..., "at": [x, z]}`.
* **Bloom ground.** Each nest adds a Bloom zone round itself (ADR-0025's field, `radius`,
  `strength`): the threads, web and fruit appear there because the field says so.
* **Seeding.** While the player is within `seed.range`, a living nest keeps `seed.count` Hollowed
  (its pods' kind: hollow, a Seeded tier, a Blister later) round it, sleeping in its roots or
  wandering; they are its guards. Killed ones come back from the pods after `seed.respawn` hours
  until the nest is burned.
* **Burning.** A nest takes fire damage only (a torch blow, a thrown molotov later, a lit fire set
  against it). At zero it burns for `burn.seconds` (flames, smoke, a Bloom scream that is a loud
  sound the Hollowed hear), its seeded Hollowed rise and come, and then it is dead: its Bloom zone
  fades over a day, its pods drop the loot (`nest_loot`: Bloom samples and mycelium, what its
  victims carried), XP source `burn_nest`, a directive event `burn_nest`.
* **Save.** `WorldState.nests` (new key, loads empty, no version bump): `{placement id: {burned,
  hp, seeded_dead: [..]}}`.

### Not in this ADR
Wolves fighting the Hollowed or hounds; packs claiming territory; Ezra Vane (his own ADR next); nest
spreading over weeks; the Ashen burning nests.

## Consequences
* The forest has a food chain and a danger that isn't the Bloom, and the night has another sound.
* The deep woods have places to find and a fire-based objective that rewards preparation.
* Wolves reuse the hound brain, so the shared AI files take only data and a prey hook; nests are
  a self-contained module behind the hub's scatter.
* Gaps go in TD-249..258.
