# Player report 5: first-person hands audit (2026-10-10)

Report: "hands (mostly fingers) still look off in almost every form, such as the crooked fingers
here in idle, or this massive thumb when holding the lighter". Fixes and the check: ADR-0061.

* `closeups_before_after.webp`: the two reported holds (idle, lighter) and the lighter turned over.
* `sheet_key_before_after.webp`: 24 holds and states, before | after.
* `sheet_all_before_after.webp`: all 130 fp_preview shots, before | after (the rifle shots differ
  in pose too: Presentation's rifle rework landed between the two renders).

## The two reported looks

* **Crooked idle fingers.** Pose and rig, not mesh. The fingers were curled 0.45-0.85 with the end
  joints bent in the same proportion as the knuckles (tips hooked: little finger PIP 108°, DIP
  67°), and `together` swung the index 11° into the middle finger (6 mm through it). After: the
  DIP lags a light curl, the idle is lightly and evenly curled (index MCP/PIP/DIP 33/46/20°,
  little finger 49/67/31°), fingers side by side.
* **Massive lighter thumb.** Mesh proportions first, then the pose; not the lens. The thumb is
  30 cm from the eye against the fingertips' 35-40 cm (only ~1.2x larger for being nearer), but
  the fingers were ~9% slimmer than an adult's and the thumb's end segment 29 mm, so the thumb was
  drawn 1.61x the index finger's width (1.67x in the inspect); an adult's is ~1.3x. It lay nearly
  straight across the lighter's top toward the eye. After: fingers ~9% thicker, the thumb's end
  segment 26 mm, the lighter 12 mm higher in the fist with the thumb's pad on the wheel: 1.40x
  (1.44x in the inspect).

## Checklist

Criteria, per baked action (every frame, `tools/fp_hands_check.py`; ADR-0061 limits):
**joints** (finger MCP/PIP/DIP and thumb MCP/IP inside a hand's range: no crooked or
hyperextended joint, no finger folded into the palm), **crossed** (neighbouring fingers no more
than 2 mm into each other), **lens** (no fingertip in view nearer than 20 cm), **thumb** (drawn at
most 1.5x the index finger's width). Wrist angle is held by ADR-0060's solver in every action
(unchanged). Knuckle definition: the mesh's knuckle knobs and creases show in every close render;
pass throughout. Walk and sprint move the whole rig (bob, the lowered sprint pose) with the
hold's own fingers; pick-up and interact have no first-person animation: graded by their holds.

Before counts are frames failing on a sweep of every 4th frame of the round-4 data (the lens
count then used any tip within 24 cm, in view or not). After: the fp_arms bake checks every frame
and fails on any violation; it passes, so every row is a pass.

| Action | Worst PIP before | Before (frames failing, every 4th frame) | After | Notes (renders) |
|---|---|---|---|---|
| fp_apply | 72 deg | pass | pass |  |
| fp_bash | 139 deg | FAIL: joints x126 | pass |  |
| fp_blueprint | 108 deg | FAIL: joints x16 | pass |  |
| fp_bottle | 92 deg | pass | pass |  |
| fp_bottle_tether | 92 deg | pass | pass |  |
| fp_bow | 123 deg | FAIL: joints x80 | pass |  |
| fp_bow_drawn | 123 deg | FAIL: joints x80, lens x80 | pass |  |
| fp_bow_tether | 118 deg | FAIL: joints x64 | pass |  |
| fp_carry_log | 72 deg | pass | pass |  |
| fp_chop | 139 deg | FAIL: joints x80 | pass |  |
| fp_climb | 123 deg | FAIL: joints x128 | pass |  |
| fp_climb_cycle | 123 deg | FAIL: joints x98 | pass | ladder hands: pass (no joint over range) |
| fp_climb_grab | 123 deg | FAIL: joints x8 | pass |  |
| fp_climb_release | 123 deg | FAIL: joints x8 | pass |  |
| fp_climb_rope | 123 deg | FAIL: joints x128 | pass |  |
| fp_climb_rope_cycle | 123 deg | FAIL: joints x98 | pass | rope hands open and hooked mid-reach: pass on joints, the open hand reads stiff (pose, not limits) |
| fp_climb_rope_grab | 123 deg | FAIL: joints x8 | pass |  |
| fp_climb_rope_release | 123 deg | FAIL: joints x8 | pass |  |
| fp_club | 139 deg | FAIL: joints x224 | pass |  |
| fp_club_guard | 139 deg | FAIL: joints x224 | pass |  |
| fp_club_tether | 139 deg | FAIL: joints x160 | pass |  |
| fp_dig | 123 deg | FAIL: joints x64 | pass |  |
| fp_draw_bow | 123 deg | FAIL: joints x35, lens x16 | pass | string hand passes the cheek to the jaw anchor: exempt (a real draw) |
| fp_drink | 92 deg | FAIL: lens x16 | pass | bottle hand thumb 19.3 cm from the eye -> moved back 1-2 cm |
| fp_eat | 97 deg | pass | pass |  |
| fp_empty | 108 deg | FAIL: joints x32, crossed x32 | pass | claw: tips hooked, index into middle -> relaxed even curl, fingers together |
| fp_empty_guard | 154 deg | FAIL: joints x384 | pass | fists folded through the palm -> closed fists on the palm |
| fp_empty_tether | 108 deg | FAIL: joints x16, crossed x16 | pass |  |
| fp_fire_pistol | 118 deg | FAIL: joints x9 | pass |  |
| fp_fire_rifle | 118 deg | FAIL: joints x13 | pass |  |
| fp_flashlight | 123 deg | FAIL: joints x64, lens x48 | pass |  |
| fp_flashlight_guard | 123 deg | FAIL: joints x128 | pass |  |
| fp_flashlight_tether | 123 deg | FAIL: joints x64, lens x32 | pass |  |
| fp_food | 97 deg | pass | pass |  |
| fp_food_tether | 97 deg | pass | pass |  |
| fp_held | 61 deg | pass | pass |  |
| fp_held_tether | 77 deg | pass | pass |  |
| fp_inspect_bottle | 92 deg | pass | pass |  |
| fp_inspect_club | 139 deg | FAIL: joints x266 | pass |  |
| fp_inspect_flashlight | 123 deg | FAIL: joints x76, lens x43 | pass | index 19.2 cm from the eye -> moved back |
| fp_inspect_food | 97 deg | pass | pass |  |
| fp_inspect_held | 71 deg | pass | pass |  |
| fp_inspect_knife | 139 deg | FAIL: joints x180 | pass |  |
| fp_inspect_light_left | 123 deg | FAIL: joints x72 | pass |  |
| fp_inspect_lighter | 144 deg | FAIL: joints x152, lens x4 | pass | thumb 1.67x turned over -> 1.4x |
| fp_inspect_one_hand | 139 deg | FAIL: joints x180 | pass |  |
| fp_inspect_pistol | 118 deg | FAIL: joints x60 | pass |  |
| fp_inspect_rifle | 118 deg | FAIL: joints x63, lens x17 | pass |  |
| fp_inspect_spear | 123 deg | FAIL: joints x144 | pass |  |
| fp_inspect_two_hand | 123 deg | FAIL: joints x144 | pass |  |
| fp_jab | 123 deg | FAIL: joints x24, lens x10 | pass |  |
| fp_knife | 139 deg | FAIL: joints x160 | pass |  |
| fp_knife_guard | 139 deg | FAIL: joints x176 | pass |  |
| fp_knife_tether | 139 deg | FAIL: joints x160 | pass |  |
| fp_light | 144 deg | FAIL: joints x56, thumb x1 | pass | as the lighter hold; the flick bent the thumb IP to 77 deg (limit 78) |
| fp_light_left | 123 deg | FAIL: joints x64 | pass |  |
| fp_light_left_guard | 123 deg | FAIL: joints x128 | pass |  |
| fp_light_left_tether | 118 deg | FAIL: joints x64 | pass |  |
| fp_light_molotov | 123 deg | FAIL: joints x36, thumb x1 | pass |  |
| fp_lighter | 144 deg | FAIL: joints x128 | pass | thumb 1.6x the index finger, overhanging the lighter; fingers through the body -> 1.4x, pad on the wheel, fingers round it |
| fp_lighter_tether | 118 deg | FAIL: joints x64 | pass |  |
| fp_molotov | 123 deg | FAIL: joints x64 | pass |  |
| fp_molotov_tether | 123 deg | FAIL: joints x64 | pass |  |
| fp_one_hand | 139 deg | FAIL: joints x160 | pass | handle grips: fingers through the handle -> on it |
| fp_one_hand_guard | 139 deg | FAIL: joints x176 | pass |  |
| fp_one_hand_tether | 139 deg | FAIL: joints x160 | pass |  |
| fp_pistol | 118 deg | FAIL: joints x48 | pass |  |
| fp_pistol_tether | 118 deg | FAIL: joints x48 | pass |  |
| fp_place | 61 deg | pass | pass |  |
| fp_punch | 154 deg | FAIL: joints x33, crossed x10 | pass | off hand clawed (the idle) -> relaxed |
| fp_release_bow | 123 deg | FAIL: joints x32, lens x19 | pass |  |
| fp_reload_pistol | 118 deg | FAIL: joints x64 | pass | eject: the open left hand splayed and stiff (pose; joints in range) |
| fp_reload_rifle | 102 deg | pass | pass |  |
| fp_reload_rifle_close | 118 deg | FAIL: joints x3 | pass |  |
| fp_reload_rifle_open | 118 deg | FAIL: joints x3 | pass |  |
| fp_rifle | 118 deg | FAIL: joints x48 | pass |  |
| fp_slash | 139 deg | FAIL: joints x60 | pass |  |
| fp_slice | 139 deg | FAIL: joints x50 | pass |  |
| fp_spear | 123 deg | FAIL: joints x128 | pass |  |
| fp_spear_guard | 123 deg | FAIL: joints x128 | pass |  |
| fp_spear_tether | 123 deg | FAIL: joints x64 | pass |  |
| fp_stab | 123 deg | FAIL: joints x56 | pass |  |
| fp_stone | 97 deg | pass | pass |  |
| fp_stone_tether | 97 deg | pass | pass |  |
| fp_throw | 97 deg | pass | pass |  |
| fp_throw_molotov | 123 deg | FAIL: joints x13 | pass |  |
| fp_throw_stone | 108 deg | FAIL: joints x2 | pass | windup sweeps the stone hand past the lens edge (in view at 2 frames, >20 cm): pass |
| fp_torch | 123 deg | FAIL: joints x28 | pass |  |
| fp_two_hand | 123 deg | FAIL: joints x128 | pass |  |
| fp_two_hand_guard | 123 deg | FAIL: joints x128 | pass |  |
| fp_two_hand_tether | 123 deg | FAIL: joints x64 | pass |  |

## Still to do (TD-341)

Inside the limits but not yet right, from the renders: the rope climb's reaching hands
(half-curled and splayed), the revolver eject's open left hand and the lighter inspect's spread
fingers read stiff (an `open` hand preset would help); and the check does not see the item, so a
finger through a handle too thick for its curl still shows only in the renders.
