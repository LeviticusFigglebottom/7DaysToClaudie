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

**3. The solver keeps wrists in range.** What a hold must keep is where its tool points; how
the fist is rolled round the handle, and where exactly the elbow goes, are free within reason.
`PoseSolver` searches the elbow's swing round the shoulder–wrist line (near the pose's `elbow`
hint) together with the hand's spin about its handle (near the authored roll) for the least wrist
bend past its range (`wrist` in viewmodel.json: an ellipse between flexion/extension and
radial/ulnar deviation, plus the forearm's roll). The first frame of an action searches wide,
later frames near the last answer so the arm doesn't jump, and wide again when a fast swing
outruns that; a jump to another elbow or roll must save more the slower the authored hand is
turning (mid-strike it is lost in the motion, in an idle it would read as the hand spinning). If the wrist is still past its range, the grip moves (at most 6 cm, tool direction
kept) toward where a straight wrist would put it, and what is left is turned back about the wrist
in one step. (Turned back about the grip instead, each correction moved the forearm and so the
angles again; a hand 1° past its range could wander 40° off.) The build log prints how far each
action's hands were turned and moved, `tools/fp_poses.py report` says the same in seconds without
Blender, and `tools/fp_poses.py tune` re-places a strike's key grips where an arm can deliver
them. test_viewmodel_holds measures every frame of every baked action's hands against the range.

**4. Grips as they are held.** A spear point-forward from a rear fist at the hip would need the
shaft to run along the forearm; held as a spear really is, the shaft lies diagonally across the
rear palm. A hold's `item.rot` (already how ViewModelHolds turns the item in the hand) is now
known to the solver too: a hand `on` the other grips along the item's own axis and the fist rolls
about it (`item_axis`), so the spear's shaft crosses the palm at 60° and points forward to the
centre with no wrist correction at all. The lighter has its own hold (upright in a loose fist, the
thumb over the wheel), `fist` runs past 1 (a grip round a ~3.5 cm handle) to 1.3 for a bare fist,
and a hold that uses one hand drops the other below the view (it comes up to guard or read the
tether): the owner's playtest found an open hand floating palm-down in the corner distracting.

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
* TD-174 records what is left (TD-172, the strikes, TD-173, the spear, and TD-175, per-finger curls, are fixed).
