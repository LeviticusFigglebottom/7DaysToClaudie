# ADR-0045: First-person hands: real hands, a joint per finger bone, wrists that stay in range

Status: Accepted

## Context

ADR-0029 gave the player forearms, sleeves, the tether and hold poses. On the first human playtest
(WORKBOARD, Player report 2) the owner found the hands "big flat mitts, and a holding pose that
reads wrong". Measured, there were three causes:

* **The mesh.** The palm was one rounded box, wider than the fingers' span and reaching over their
  roots; the fingers were 1.9 cm thick on 1.7 cm centres, smooth-joined into the palm and each
  other; and the 1.8 mm meshing cell closed any gap under 2–4 mm. The result was a paddle with
  webbed fingers and nails as caps.
* **The rig.** The middle, ring and little fingers shared the middle finger's two bones
  (`fingers_1/2`), so the ring and little fingers bent up to 3.5 cm off their own knuckles, could
  not close separately, and a fist left a hollow under them. One bone per finger past the knuckle
  bent the middle and end joints together, so curled fingertips poked straight into the palm.
* **The poses.** A hold names the grip point, the handle's direction and where the knuckles point,
  and the arm's two-bone IK laid the forearm out from an elbow hint alone. Nothing related the two:
  on the baked actions the wrists were bent about 90° in nearly every idle and 100–140° mid-swing.
  A wrist manages roughly 65° of flexion, 55° of extension, 18° radial and 32° ulnar deviation.
  That bend, more than anything, is what read wrong.

## Decision

**1. Hands built as hands** (`lib/char_fp.py` `FPModel._hand`): a domed metacarpal block from a
palm outline, arched across the back (~2.7 cm thick at the knuckles), with thenar, hypothenar and
distal palm pads, raised knuckles and faint extensor tendons; four separate fingers, each its own
SDF field so the clefts survive the union, tapering, middle longest and little finger shortest,
with joint bulges, a pad under each phalanx, rounded tips and inset nails; the thumb on a thenar
mass, webbed to the index. The arms are meshed in a narrow band round the surface
(`sparse_surface_nets`, identical output to the dense grid) at a 1.1 mm cell and decimated to 14k
triangles an arm, 11.5k of them past the wrist. Vertex B (unused on the arms) carries a flush mask
over knuckles, finger joints and fingertips that the skin shader's new `flush` reddens (default 0,
so the Hollowed are unchanged).

**2. A bone per joint.** Each digit has three bones: `thumb_1/2/3` (CMC, MCP, IP) and
`index_, middle_, ring_, pinky_1/2/3` (MCP, PIP, DIP). `fist` curls every finger at its three
joints (`FINGER_CURL`, the ring and little fingers a little further, as round a handle); `thumb`
swings the thumb across the palm, turns it about its own length so the pad meets the index, and
wraps its two joints. No game code names a finger bone, so this is the generator's alone.

**3. The solver keeps wrists in range.** `PoseSolver` swings the elbow round the shoulder–wrist
line to where the forearm best lines up with the hand (near the pose's `elbow` hint), then turns
what bend is left past the wrist's range (`wrist` in viewmodel.json: an ellipse between
flexion/extension and radial/ulnar deviation, plus the forearm's roll) out of the hand's turn about
its grip, so the grip stays where the pose put it. The build log says how far each action's hands
were turned back: a pose that needs much of that is asking for a wrist nobody has, and its data
should be rewritten toward what the solver found. test_viewmodel_holds measures every frame of
every baked action's hands against the range.

Rejected: clamping the wrist alone without moving the elbow (it turns tools away from where the
pose aims them far more often), and per-pose hand-tuned elbow positions (every new hold would have
to rediscover the same anatomy).

## Consequences

* The holds look like hands holding things; `viewmodel.json` stays the one place a hold is written,
  and a hold that asks for an impossible wrist is corrected and reported rather than baked.
* A hand turned back by the limits no longer points its tool exactly where the data says: retune
  the pose (the build log names it) rather than widen the range.
* 39 bones instead of 21 and 28k triangles for the arms instead of 18k: still small beside a
  Hollowed, and the arms are one draw.
* TD-172–175 record what is left.
