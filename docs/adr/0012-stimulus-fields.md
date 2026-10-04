# ADR-0012: Shared perception through stimulus fields

**Status**: Accepted · 2026-10

## Context
Stealth, light, noise, fire and scent must matter (brief), and AI must be cheap with many agents.
"AI reads the player's position" makes stealth fake and perception expensive per agent.

## Decision
A single `Stimuli` node holds the world's perceivable signals:
* **Sound events** (position, loudness in metres, kind, source) with weather masking and
  wall/terrain occlusion; loud events also feed the **heat map** (attention → scouts/Keener/pack).
* **Scent grid** (64×64 × 4 m around the player): deposited by movement/bleeding, decays,
  diffuses and **advects with the wind**, so Hollowed can follow where you went.
* **Light**: ambient light from the sky plus registered light sources (torches, campfires, the
  player's own light) → `detection_range()` combining light, stance, motion and perks.
Enemies sample these on staggered perception ticks; they never read the player's position unless
sight (range × FOV × line of sight) succeeds. Debug: F3 overlay; invisible flag for testing.

## Consequences
+ Stealth emerges from systems (crouch in the dark, downwind, quiet tools) instead of rules.
+ New stimulus sources (traps, fires, gunshots, screams) need no AI changes.
− Scent window follows the player only (single-player); co-op needs one window per player.
