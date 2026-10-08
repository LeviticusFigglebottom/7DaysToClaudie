# ADR-0060: Relaxed wrists: a comfort range for hands at rest, holds written against the forearm

Status: Accepted

## Context

Player report 4 (WORKBOARD) found the first-person hands still unnatural: idle, both hands were
loose fists "with the wrists bent hard down and in, so the backs of the hands face the camera like
paddles"; holding the lighter, "a flat pinch ... the wrist cocked down at the strap".

ADR-0045's PoseSolver keeps every baked wrist inside the anatomical range (65° flexion, 55°
extension, 18° radial, 32° ulnar, 95° roll), and charges nothing inside it. Measured on the round 3
data, every idle had settled near the edge: +50..+60° of flexion with +15..+20° of ulnar deviation
and the forearm rolled 60..95° (empty, one_hand, lighter, knife, food, bottle, torch ...), and the
climbing hands at -54° extension. A wrist can do that; it never rests there. The bend reads at once,
far more than any detail of the mesh.

## Decision

**1. A comfort range** (`viewmodel.json` `wrist.comfort`, defaults in `char_fp.WRIST_COMFORT`):
the same ellipse, smaller and leaning to extension (18° flexion, 30° extension, 10° radial, 20°
ulnar) and 70° of roll. PoseSolver's limits are lerped from the full range toward it by a per-frame
`_relax` weight:

* 1 for a hold at rest (its idle, guard and tether loops);
* in a keyed action, `1 - d / 30°` where d is how far the hands have left the hold (degrees of
  turn plus 3° a centimetre of grip): a strike starts and ends on the very arm its idle bakes and
  uses the whole range once under way;
* at least 0.5 throughout a *use* (eating, lighting, reloading, inspecting: slow and watched),
  overridable per action with `relax`.

A hand at rest may also move its grip further (10 cm instead of 6) toward where a straight wrist
puts it before it is turned back. Inside the range, a small cost on the bend off the comfort
ellipse's middle (`COMFORT_COST`) picks, among in-range elbows and fist rolls, the straightest
wrist.

**2. Holds written against the forearm.** A hold hand may give `"wrist": [flexion, ulnar, roll]`
instead of `dir`/`back`: the hand is placed so the arm, reaching the grip with its elbow at the
hint, has exactly that wrist (`char_fp._wrist_frame`; resolved once into an absolute frame, so keyed
channels such as `R.rot` work on it unchanged). A hand with no tool to point should say what its
wrist does, not which way its knuckles face; the empty hands are now `[-12, 6, ±40]` with
progressive finger curls (index least).

**3. Grips as hands hold small things.** A fist's handle axis is square to the forearm, so with the
elbow down (where it rests) an upright lighter needs a broken wrist, and with the elbow raised the
forearm's neutral roll turns the thumb to the chest. The lighter now sits obliquely in the fingers
(item `rot` 40° toward the knuckles), forearm rising, wrist straight, fingers closed round its thin
body (curls 1.0..1.2), the thumb across its top with the end joint bent onto the wheel.

**4. Tools.** `fp_dev_render.py` poses and renders the arms from the player's camera in Blender
alone (cached mesh: ~15 s a shot) for iterating on holds; the solver's rest-pose FK is computed once
(a full FK per candidate was most of the bake time, now ~10x faster). test_viewmodel_holds checks
every hold's resting wrists against `wrist.comfort`; ViewModelHolds validates it.

Rejected: a narrower full range (strikes need it), and per-hold hand-tuned absolute frames (each
new hold would rediscover the same anatomy, and the round 3 data shows they drift to the edge).

## Consequences

* Idle hands read relaxed; a hold whose data asks for a bent wrist at rest is turned back into
  comfort and the build log says how far: rewrite it (prefer `wrist`) rather than widen `comfort`.
* A tool held at rest may point a little off what its data says until its hold is retuned.
