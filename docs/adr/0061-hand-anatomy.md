# ADR-0061: Hands inside anatomy: joint limits, a lagging end joint, proportions and a baked check

Status: Accepted

## Context

Player report 5 (WORKBOARD): "hands (mostly fingers) still look off in almost every form, such as
the crooked fingers here in idle, or this massive thumb when holding the lighter".

ADR-0045 gave every finger its own three bones and ADR-0060 kept the wrists comfortable, but
nothing bounded the fingers themselves. `FPRig.evaluate` turned each joint linearly with its curl:
`FINGER_CURL` (68°, 92°, 58° at the MCP, PIP and DIP at curl 1) times the curl, times
`FINGER_SCALE` (the little finger 1.12), on top of the rest pose's own bend (14°, 20°, 12°).
Holds ask for curls up to `FIST_MAX` 1.3, so a little finger's PIP was asked for 144° (a real one
stops near 100-110°). Measured on every 4th frame of every baked action (tools/fp_hands_check.py,
below), the round-4 data had 4695 PIP, 1128 MCP and 673 DIP frame-joints past a hand's range in
73 of 91 actions (74 failing some check): grips folded the middle phalanx flat onto the first and sank fingertips into
the palm.

The two reported looks had their own causes:

* **The crooked idle.** The empty hold's loose fists (curls 0.45-0.85, `together` 1) had the end
  joints bent 85% as far as the knuckles in proportion: hooked tips on a hand meant to be at
  rest, seen from above as claws. `FINGER_TOGETHER` swung the index and little fingers 9° and
  14° toward the middle one, but the rest pose's fingers already lie side by side (17-19 mm
  apart at the knuckles, as wide as they are), so the relaxed hand's fingers crossed (index into
  middle by 6 mm).
* **The massive thumb.** Not the lens: the lighter's thumb is 30 cm from the eye against the
  fingers' 35-40 (the near plane is far closer). The mesh's fingers were ~9% slimmer than an
  adult's while the thumb was full size, and its end segment (29 mm) long, so the thumb was drawn
  1.6 times as wide as the index finger (1.67 turned over in the inspect; after: 1.40 and 1.44) (an adult's is ~1.3 side by side). Its pose, nearly
  straight across the top of the lighter with the nail toward the eye, showed all of it.

## Decision

**1. Joint limits in the rig** (`char_fp.FINGER_MAX` 88° / 102° / 75° at the MCP, PIP and DIP,
`THUMB_MAX` 58° / 78° at the thumb's MCP and IP, counted from straight with the rest bend
included). A joint follows its curl linearly up to `JOINT_KNEE` (15°) short of its limit, then
eases into it (`joint_bend`): no hold or key can bend a joint past a hand's range, and below the
knee nothing changes. Fists keep closing to the limits instead of through the palm.

**2. The end joint lags** (`CURL_LAG`: the DIP follows `curl ** 1.6` below curl 1). A relaxed
hand's end joints are nearly straight and only catch up as it closes; full grips (curl 1 and
past) are unchanged.

**3. Proportions**: finger radii up ~9% (`FINGER_SHAPE`), the thumb's end segment 26 mm
(`THUMB_DISTAL`) with its IP and tip a little slimmer; `FINGER_TOGETHER` cut to -3 / 0 / 2.5 / 5°
so fingers held together lie side by side instead of crossing.

**4. Two holds.** The empty idle is relaxed, lightly and evenly curled (index 0.28 .. little
finger 0.46, `together` 0.8) instead of loose fists. The lighter sits 12 mm higher in the fist
(`item.pos`) with the thumb tucked a little (0.2): its pad rests on the wheel instead of the
thumb reaching straight over the top toward the eye (drawn 1.40x the index finger's width, from
1.61x).

**5. A check on every baked frame** (`lib/fp_anatomy.py`, pure numpy). For each frame of each
fp_* action, solved as the bake solves it, it measures from the posed bones:

* each finger's MCP / PIP / DIP and the thumb's MCP / IP flexion against `LIMITS`, and the
  knuckle's sideways swing (25° max);
* neighbouring fingers' middle and end phalanges as capsules of the mesh's radii: no more than
  2 mm into each other;
* every fingertip in view (the hold FOV on a 16:9 screen) at least 20 cm from the eye: nearer, a
  digit looms at the lens. Climbing hands (reaching past the view) and a bow's string hand (drawn
  to the jaw past the eye, as a real draw is) are exempt. Two uses came 1-2 cm nearer (the
  drink's bottle hand, the flashlight inspect's last turn) and were moved back;
* the thumb in view drawn at most 1.5 times the index finger's width (its end joint's radius
  over its distance from the eye against the index finger's): the "massive thumb" rule, mesh
  and pose together.

`character_fp_arms` runs it on what it bakes and fails the build on any violation, listing them
per action and joint; `tools/fp_hands_check.py` runs it without Blender (`--only` actions,
`--table` for each action's ranges) to try a pose before baking.

## Consequences

* Every hold, attack and use now bakes inside a hand's range (0 violations in 91 actions; before,
  6841 joint-frames past a limit on every 4th frame; docs/playtest/2026-10-10_report5_hands/ has the before / after
  sheet and the per-hold checklist).
* Grips that leaned on the overshoot close a little less: a fist at curl 1.2 has its PIP at
  ~100° instead of 110-134°, so fingertips that sank into a handle now sit on it.
* A pose that bends a finger past what a hand can do, crosses fingers, or pushes a digit into
  the lens fails the fp_arms bake with the frame and joint named. Pose authors (the rifle, the
  tether) run `tools/fp_hands_check.py --only fp_<action>` first; the full sweep takes ~15
  minutes, the bake does the same work anyway.
* The check measures bones and capsules, not the item: a finger through a handle that is too
  thick for its curl still needs the renders (fp_preview). A per-item handle radius would close
  that gap.
