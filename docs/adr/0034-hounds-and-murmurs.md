# ADR-0034: Hollowed hounds and Murmurs: pack hunters on the Enemy brain, crows that mark you

**Status**: Accepted · 2026-10

## Context
DESIGN §6 promised two Hollowed that hunt differently from a body walking at you:
* *Hollowed hounds*: dogs the Bloom took, hunting in packs.
* *Murmurs*: crow flocks that mark you.

TD-028 left both waiting on "quadruped and flying rigs". ADR-0027 then built both rigs for
wildlife:
* the quadruped skeleton, body, coat and action pipeline (deer, hare);
* instanced bird flocks that flush, circle and call. Their calls are already sounds the
  Hollowed hear.

So the question was no longer how to animate them. It was how they hunt, and how much of the
Hollowed machinery they share.

## Decision

### Hounds are Enemies with a low body, not a second brain
A hound is an `Enemy` with archetype `hound` and the def `hollow_hound` (data/enemies/hounds.json).
It shares everything the other Hollowed have:
* senses (sight, hearing, the scent grid);
* damage, hit zones (the quadruped skeleton has `head`, `neck`, `chest`, `spine` and `hips`, so
  `limb_at` works unchanged), XP, kills, heat;
* navmesh pathing, breaking through what blocks it;
* infected tiers, world settings and the debug spawn menu.

What `behavior.quadruped` changes:
* **The body.** The capsule lies along the hound on the ground (radius 0.3 m, length 1.2 m,
  scaled), and the eye is at 0.62 m.
* **Dismemberment.** None (`no_dismember`): humanoid gibs off a dog would be wrong.
* **Corpse.** A dog-sized box.
* **Stand-in.** `EnemyVisual` builds a four-legged one when `animals/hollow_hound_*` is not
  generated, so stand-in mode (no generated assets) still shows a dog.
* **Animations.** The generated model provides the Enemy's own action names: `idle`, `walk`, `run`,
  `attack_a`, `attack_b`, `attack_structure`, `scream` (the howl), `hit_front`, `hit_back`,
  `stagger`, `death_front`, `death_back`, `idle_sleep_lie`, `wake_lie`, `eat`. It adds `track`,
  nose to the ground.
* **Voices.** `_vid()` swaps each Hollowed voice for the hound's: growl, snarl, bark, howl, yelp,
  death and pant (tools/assetgen/audio/sounds/hounds.py).
* **Footsteps.** None: no shuffling footsteps.

### How a pack hunts (data/config/hounds.json)
* **Packs.** `AIDirector.spawn_pack` spawns 3–5 hounds that each know the pack (`Enemy.pack`) and
  their slot in its spread (`pack_slot`). Packs come from two places:
  * Wandering groups: `spawn.chance`, doubled at night.
  * Heat: the heat system's `pack` response is hounds `heat_pack` of the time.

  Both need the hound's `gamestage_min` (6) and the `hollowed_hounds` world setting.
* **Rally and howl.** What one hound sees, the pack knows: every mate within `howl.pack_radius`
  that isn't already on the quarry takes up the chase (`ambush`). The first sight is answered with
  a howl:
  * The hound stops in the SCREAM state.
  * One howl is spent for the whole pack.
  * The howl is a stimulus of `howl.loudness` that the Hollowed hear like any other sound.
* **Flank, then close.** In a chase with mates alive, each hound first makes for its own bearing
  round the player. Bearings are `flank.spread` degrees apart, at `flank.radius`, from the side the
  pack came. It goes straight in once it gets there, or after 6 s.
* **Hit and run.** After a bite, a hound breaks off wide for `retreat` seconds, then comes again.
* **Scent.** A hound is a `tracker`: when it loses sight it works the trail. While investigating it
  keeps re-aiming at the scent gradient, and plays `track`. Its smell is 3x a Hollow's, so it picks
  up weaker trails.
* **Fire.** A hound in front of a player holding a flame keeps `torch.keep_off` m away and circles.
  A flame is an omni light: a torch, lantern or lighter, not a flashlight; see
  `PlayerEquipment.has_flame_on()`. A hound more than `torch.behind_angle` degrees off the
  player's facing still bites. A torch is a real defence against a pack, but not a complete one.

### Murmurs are a crow flock state, not an enemy
A Murmur is `BirdFlock.State.MURMUR`, appended to the enum so existing values don't move.
`WildlifeManager` runs it:
* **Start.** When the player flushes a crow flock, `murmur_rolls()` decides whether it becomes a
  Murmur. The chance rises from `chance` to `bloom_chance` with `bloom_at` (the Bloom field,
  ADR-0025). It needs the crow def's `gamestage_min`, the `murmurs` world setting and daylight.
  The roll is seeded by world seed, flock id and flush count, so it is deterministic.
* **Follow.** The flock rises, then rings the player at `height` m and `radius` m. The ring drifts
  after them (`follow`), lower and tighter than the circling after an ordinary flush.
* **Mark.** Every caw (`caw` seconds apart) emits a stimulus of `mark_loudness` (kind `murmur`) at
  the player's position, not at the birds. The Hollowed within hearing come to *you*. Wildlife
  ignores these marks, so a Murmur doesn't flush every other flock.
* **End.** One of:
  * the player stays under a roof, a floor above or the canopy (a ray up hits the world, building
    or vegetation layers) for `cover_seconds`, with cover time decaying while exposed;
  * a gunshot or explosion within `scatter_radius` of the flock;
  * nightfall (the crows roost) or a Hum night;
  * `max_seconds`.

  Status messages tell the player when it starts and ends.

Neither feature needs new save state:
* Wandering packs are re-rolled around the player like any wanderer.
* Flocks are re-rolled from the world seed (TD-065).

## Consequences
* Hounds reuse 95% of the Enemy code and every system that knows about Enemies. The price is a
  handful of `quad` branches in `enemy.gd`. A second four-legged Hollowed costs only a def.
* A pack is the first Hollowed that coordinates. It is cheap: shared knowledge through `ambush`,
  and bearings from the pack centre, with no blackboard or tactics planner.
* Murmurs make crows a threat you manage: get under cover, shoot (and pay for the noise), or keep
  moving away from the Hollowed they call.
* Known gaps: TD-094 to TD-097.
