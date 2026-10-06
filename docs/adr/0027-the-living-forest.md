# ADR-0027: The living forest: generated quadrupeds and birds, deterministic wildlife, flushes the Hollowed hear, hunting

**Status**: Accepted · 2026-10

## Context
DESIGN §6 promises wildlife in M2: "deer, hare, wolves; birds that flush and give away
positions", and Murmurs, "crow flocks that mark you". The valley had none. A forest of fir and
larch with nothing moving in it reads as a set, and the stealth game (ADR-0012) had no way for
the world to give the player away except the Hollowed's own senses.

The character pipeline (ADR-0028) builds bipeds only: one skeleton layout, segmented bodies for
dismemberment. Animals need four legs, a different gait vocabulary, fur rather than skin and
cloth, and — for birds — numbers that a skeleton per bird can't afford.

## Decision
* **Quadrupeds on the character toolkit.** `lib/animal_skel.py` defines one bone layout for every
  four-legged animal (pelvis `hips`, spine, chest, two neck bones, head, jaw, ears, tail;
  scapula/upper arm/forearm/cannon/hoof in front; thigh/shin/cannon/hoof behind), with joint
  tables for a white-tailed doe and a snowshoe hare. It reuses `char_skel.Skeleton` (FK, two-bone
  IK, aim), `create_armature` and `char_anim.write_action`, so the export and import path is the
  Hollowed's.
  * Anatomy is signed-distance shapes (`lib/animal_body.py`): ribcage, belly, loin, rump, withers
    and brisket; shoulder blades and haunches; muscled upper limbs over slim cannons; cloven hooves
    with dewclaws; a head built in its own frame (cranium, muzzle, jowls, cheeks, brows, wet nose,
    nostrils, lips, eye sockets). Ears (cupped) and antlers (beams, brow tines, points, burrs,
    pearling) are meshed finer as their own parts. One skinned mesh per part, decimated to a budget
    (doe 12.4k triangles, buck 15k with its rack, hare 6.3k).
  * Skinning is by distance to each bone's segment, top four, smoothed over the mesh; the trunk
    behind the elbow and before the stifle and the rump over the hip stay with the trunk, so a
    leg swinging under the body doesn't drag the flank into a seam.
  * Actions (`lib/animal_anim.py`, 30 fps, in place): legs are IK by default (toe target, cannon
    and hoof angles) and FK when folded. Gaits come from phase tables: a lateral-sequence walk, a
    diagonal trot, a rotary gallop with a suspension phase and spinal flexion, and the hare's hop
    and half-bound. Plus idle, graze (muzzle to the ground, chewing, plucking), alert (head high,
    ears forward, a stamped fore hoof), bed down, bed (sternal, legs folded under), get up (rear
    end first), death (buckling onto its side) and hit.
* **Birds are instances, not rigs.** `generators/animal_bird.py` writes a songbird and a crow as
  two meshes each: `fly` (wings spread, the crow's primaries fingered) and `perch` (wings folded,
  standing). A flock is two MultiMeshes. The wings flap in the vertex stage: `UV2.x` is the span
  fraction, and each instance's custom data holds its phase, rate and amplitude (a fast climb, a
  songbird's bounding flight, a crow's glide when circling). No skeleton per bird.
* **One fur shader** (`fur.gdshader`, the only new shader) for coats and feathers. The coat is
  painted by the generator in vertex colour (R baked AO, G the pale coat, B the dark coat) and
  tinted per material; a neutral strand or feather texture whose UVs follow the lie of the hair
  (head to tail, down the legs, chordwise on wings) gives the grain. A soft rim on the hair tips,
  backlit ears, a wet nose, an oil-slick sheen on crows, rain darkening the coat.
* **Wildlife is data** (`data/wildlife/*.json`, `WildlifeDef`): `grazer` or `flock`; models by
  weight; biome weights, density (groups per km²), a forest-edge multiplier and activity by
  period (dawn, day, dusk, night); group size; speeds and the speed each gait shows; senses
  (sight, smell, hearing, alert and flight distances, the Hollowed, a bolting loudness); health;
  carcass yields, tools, scent and lifetime; sounds; flush radius and loudness, circling and
  return times.
* **Deterministic plans, nothing saved.** `WildlifeSpawner` plans each 128 m cell from the world
  seed, the cell, the day and the period: the same herd grazes the same meadow at the same dawn on
  every machine. `WildlifeManager` (a GameWorld module) spawns the plans in a ring round the
  player (grazers 70–230 m, flocks 30–160 m) and drops them beyond it; a band you took animals
  from comes back short for the rest of the session. Like wandering Hollowed (TD-012), wildlife is
  re-rolled rather than persisted; there is no save format change.
* **The same senses as the Hollowed** (ADR-0012), in a pure `WildlifeBrain`: a person's
  visibility from `Stimuli.detection_range` (light, stance, movement, carried light), scent
  carried downwind by the weather's wind, awake Hollowed, and loud sounds. A deer looks up at
  60 m and bolts inside 32 (a crouched stalker gets nearer), smells you downwind at 90, bolts at a
  gunshot; the whole band goes when one does; animals bed down at night. Flocks flush for a
  person inside their radius (a crouched, slow one can slip by at half of it), a Hollowed, or a
  loud noise.
* **Birds give you away.** A flush emits a `bird_flush` sound into the stimulus field at the
  flock (songbirds 34–38 m, crows 60 m), and the Hollowed hear it like any other sound and come to
  look. Crows circle what flushed them for ~24 s, cawing, and every caw is another stimulus over
  that spot: the Murmurs, in small. A deer's alarm snort is a quieter stimulus of its own.
* **The Hum night is silent.** From two hours before the Hum until it ends, nothing spawns, the
  herds bolt and leave and the flocks fly off for good.
* **Hunting through the command bus.** Animals take damage on the enemy layer (head hits count
  more), bleed, and die into a carcass that keeps depositing scent (the Hollowed follow scent
  gradients) until it rots away; the kill is XP (`hunt_kill`). `wildlife.butcher` validates the
  carcass, reach and a knife or axe (in hand or carried) and pays deterministic yields per animal
  and world seed (an axe spoils a strand of sinew), XP (`butcher`), a little noise and a reek.
  New items: raw and roast venison and hare, deer hide, hare pelt, sinew, rawhide strips; recipes
  to roast them, twist sinew into cordage, cut rawhide strips and make bandages from a pelt.
* **World settings**: `wildlife` (on/off) and `wildlife_density`.

## Consequences
+ The forest moves: deer at the edges at dawn and dusk, hares in the brush, songbirds in the
  canopy, crows over the town, and a reason to crouch and watch the wind.
+ Birds turn noise discipline into a world system: walking through a flock is a shout.
+ Hunting closes a food loop the slice lacked, with a cost: blood draws the Hollowed.
+ Every animal reuses the character pipeline; a new species is a joint table, shapes and a JSON
  def.
− Wildlife isn't saved: a carcass left behind is gone after a reload, and a band re-rolls on a new
  day (TD-065).
− Animals glide on the heightfield and steer by sampling walkable ground; they don't use the
  navmesh and pass through trunks and fences. They see without line-of-sight checks (TD-068).
− Coats are textured and masked, not shelled: silhouettes are smooth at close range (TD-067).
− Wolves, hounds and true Murmurs (crows that follow and mark you over time) are still to come
  (TD-066).
