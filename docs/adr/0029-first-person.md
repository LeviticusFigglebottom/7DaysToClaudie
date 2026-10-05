# ADR-0029: First person: hold classes, a viewmodel field of view, arms that carry the tether, swings that land

Status: Accepted

## Context

The player looks at their own hands and tools all game. The first-person presentation read as a
placeholder: the stone axe stood straight up in the middle of the screen like a torch, bare hands
floated at the lower edge with no forearms or sleeves, the wrists were thin (TD-025), the axe head
was a dark blob, the torch had no flame, a swing had no weight and connected with nothing but a
sound, the wrist tether on the arms was a prop separate from the tether UI (TD-016), and the
world's field of view (75° by default, more when sprinting) stretched everything near the lens and
let tools sink into walls. In The Forest and Sons of the Forest the hands sell the world: the axe
low and to the right with real weight, sleeves and forearms framing the screen, every swing
landing with a jolt.

## Decision

**1. A viewmodel field of view with Godot's own technique.** Godot 4.5 added per-material
viewmodel support: `Z_CLIP_SCALE` in `vertex()` squeezes the depth towards the near plane, and
`PROJECTION_MATRIX` is writable there, so a material can draw with its own field of view
(BaseMaterial3D `use_fov_override` / `use_z_clip_scale`). `FpMaterials` gives everything under the
viewmodel such a material: BaseMaterial3Ds get the flags; ShaderMaterials (std_surface, std_glass,
the character `skin` and `cloth` shaders) get a copy of their shader with the same lines added at
the end of `vertex()` (cached per shader; each material's copy is kept on it), as surface overrides
so shared meshes stay untouched. `viewmodel.json` sets `fov` (58°) and `z_clip_scale` (0.04); reading the tether
narrows the FOV to 42° and `set_fov()` retunes every live material. Rejected: a second camera in a
SubViewport composited over the view (a second shadow pass, its own environment, tonemap and fog to
keep in step, transparency and TAA seams), and leaving the world FOV (stretching, clipping).

**2. Hold classes, in data.** `data/config/viewmodel.json` defines the hold classes: `empty`,
`one_hand` (axes, hatchet, machete, knife, hammer), `club` (club, pipe: two hands, cocked over the
shoulder), `spear` (two hands, low, point to the centre), `two_hand` (shovel), `light_left` (torch,
lighter up in the left hand), `flashlight` (overhand in the left fist, the beam out of the
little-finger side where you look), `pistol`, `held` (anything on the palm: resources,
medicine, placeables), `food`, `bottle`, `blueprint` (the Field Manual open on the left palm while
laying out a ghost) and `carry_log`. An item's class is `equip.hold`, else by `equip.kind`, then
(melee) by `damage_type`, then by category (`ViewModelHolds`); `equip.swing` picks its attack style.
Both keys are validated. A hand pose is written the way an animator thinks about a grip, in camera
space: the grip point, the handle's direction (thumb side), where the back of the hand faces, the
curl of the fingers and thumb, an elbow hint; or "on the other hand's handle, this far along, turned
so much" for two-handed grips. The arms generator (`lib/char_fp.py`) reads the same file and bakes
one looping action per class (`fp_<class>`), its guard (`fp_<class>_guard`) and its tether reading
(`fp_<class>_tether`), and one action per attack (`fp_chop`, `fp_slash`, `fp_bash`, `fp_stab`,
`fp_dig`, `fp_punch`, `fp_torch`, `fp_jab`) and use (`fp_eat`, `fp_drink`, `fp_apply`, `fp_place`,
`fp_throw`, `fp_light`). Keys are absolute hand specs or moves and turns relative to the hold;
positions ease, hand frames slerp, two-handed grips stay on the handle every frame. The data file is
a source of the arms task, so a pose edit rebuilds them. At runtime the class also gives the item's
placement in the hand (its hold's rotation and offset, composed with the item's own `grip_rot`, which
now only turns a model into the tool frame), centring for cans and bottles, which hand holds it,
the guard's share and the use action. Items without a viewmodel model are held as their ground
model, stood upright along their longest side for food and bottles.

**3. Arms worth looking at.** The rest pose is a working grip (thumb up, elbows bent), so the poses
used most deform least. Forearm twist bones (`forearm_twist.L/R`) take 70% of the hand's roll about
the forearm, so pronation spreads along it instead of wringing the wrist. The jumpsuit sleeves are
rolled to just below the elbow (a thick, lumpy roll of three folds), so bare forearms come in from
the lower corners. Wrists and forearms are a labourer's (TD-025's thin wrists): radial and ulnar
heads, tendons, a few veins, knuckles and tendons on the backs of the hands, nails of their own
material. Remand orange is kept (the Program's colour, ADR-0023's drone and canisters) but washed
and sun-bleached to a dull rust that sits in the autumn palette. The arms use the character `skin`
and `cloth` shaders (ADR-0028: subsurface light, fabric sheen) through FP-only materials
(`data/materials/fp.json`, `fp_*`; textures in `textures/gen/fp.py`), and a vertex dirt mask
(creases, knuckles, fingertips) shows the `fp_grime` layer.

**4. The tether is the unit on the wrist.** A rugged Program unit (76×52 mm, bevelled, bolted,
rubber straps with a lock block, side buttons, a status LED, an antenna stub) sits over the back of
the left wrist on the twist bone, so it turns with the wrist like a watch. Its landscape screen
(1.56:1, the tether UI's 640×400) shows the live tether UI: `Tether` renders its SubViewport into the
arms' screen when the arms exist (the floating device remains only for arms-less builds), refreshes
it every 2 s while lowered so the screen glows dimly at the lower left, and live while raised. T
raises the left wrist (`TetherRaise`: lowered, raising, raised, lowering on data timings) into each
class's reading pose: the forearm across the view, the screen facing you, the viewmodel narrowed
and the screen brightened. A light in the left hand passes to the right while you read. While the
wrist is up you can't swing: the first press lowers it.

**5. Motion.** `ViewModelMotion` (springs, node-free, deterministic) layers breathing, a sway that
lags the view and rolls into turns, inertia against movement, a footstep bob tied to the player's
steps (`Player.step_phase()` / `step_count`: lowest as each foot lands, swaying every other step),
the lowered sprint pose, a landing dip, the drop-and-raise of a newly equipped item, recoil, a
stagger when you are hit (`Events.player_damaged`, from the attacker's side) and the camera kick.

**6. Swings that land.** Each style is keyed with anticipation (a hang at the top), a fast strike,
the contact frame and a follow-through, and plays over the item's `attack_time`, which stays
authoritative with reach and stamina. The hit resolves at `attack_time × attacks.<style>.impact`,
the keyed contact frame (it was a fixed 45%). When it connects, the viewmodel freezes for the
surface's hit-stop (then catches up to finish on time, so the gameplay rhythm is unchanged), the
camera kicks and the tool recoils, by what was struck: wood, bark, flesh, metal, stone, dirt, solid
(`impact.surfaces`; the struck surface comes from the collider: Hollowed, loose logs, trees, the
`surface` meta, terrain). Particles are added only where the target makes none of its own: bark and
chips off a loose log, sparks off metal, chips off stone, a little dust off anything else (trees,
the Hollowed's dark spray, structures and terrain already burst their own).

**7. Guard.** Holding Block with a melee item whose Block isn't already a use (eating, reloading,
throwing) raises its hold's guard. A blow from within `guard.arc_deg` of where you face loses the
item's `equip.block` or the hold's `block` share of its damage and of the wound it would open,
costs stamina per blocked hit and per point absorbed, wears the weapon and jolts the guard; out of
stamina, the guard is beaten down. You can't swing while guarding. This gives `fp_block` (TD-016)
its gameplay; side swings are the machete's and knife's `slash`.

**8. Tools at 40 cm.** The stone axe's head is knapped flint (`item_flint`, glassy, clouded, with
chalky inclusions, flake-scar ripples, and translucent lighter edges revealed by the wear mask) and
its bindings are flat rawhide strips wound over each other and crossed over the stone, instead of
round plant cord. The torch's burnt cap glows like coals while lit (`item_torch_ember`, a
`light_source` material lit through the instance's `light_lit`) under a flame of fire-flipbook
particles with embers, in world space so it trails; its light follows the flame in the left hand.

### Visual QA
`src/tools/cli/fp_preview.gd` renders the viewmodel in a lit clearing with no world load (seconds
a shot): each hold class at rest, attacks frozen at their wind-up and contact frames, the guards,
the uses (eat, drink, apply, throw), the torch by day and at night, the raised tether (the tether
UI on the wrist screen, its layout only without a session), carrying a log and laying out a
blueprint (`--only` picks shots; `--out`, `--size`). The screenshot suite adds
`first_person_axe`, `first_person_axe_swing`, `first_person_torch`, `first_person_tether` (the
live tether UI on the wrist), `first_person_spear` and `first_person_food` in the world.

## Consequences

* Poses, swings and uses are tuned in one data file and checked with `fp_preview.gd` (a lit
  clearing, seconds a shot, no world load) and the screenshot suite's first-person shots; the arms
  rebuild (about 3 minutes) when the file changes.
* Every viewmodel material is a converted copy; a new shader used by an item needs nothing (the
  lines are injected), but a shader that writes `POSITION` or returns early from `vertex()` would
  bypass them. A copy is kept on its source material (metadata `fp_material`) and tracked weakly
  for `set_fov()`, so materials made at runtime (a torch flame each time it is lit, the tether
  screen) are freed with their nodes instead of filling a static cache.
* The arms' SDF labels its skin 0, which the Hollowed's label map turns into `skin_hollow`: the
  first arms built drew the player's hands in dead skin. `FPModel.eval_points` relabels it
  `fp_skin`; a new FP part must take an `fp_*` label of its own.
* `viewmodel.json` is a declared source of `model:characters/fp_arms`, so a pose edit rebuilds
  the arms (`make assets`), and the arms on disk can't lag the data (the test
  `test_arms_carry_every_action` checks every hold, attack and use has its action).
* Squeezed depth means screen-space effects (SSAO, SSR, the skin's screen-space subsurface blur)
  see the arms as nearer than they are; they are tuned to look right on the software renderer and
  need a check on GPUs (TD-074).
* `fp_*` materials are FP-only, so the Hollowed's character materials can change freely.
* Hold poses are baked: items of different sizes in one class share a grip, and nothing adapts at
  runtime (TD-073).

Supersedes the first-person parts of TD-016; resolves TD-025's FP wrists and FP skin shader.
