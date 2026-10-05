# ADR-0023: Lights that make sense, a real moon, bridges that follow the road, the Program's drone

**Status**: Accepted · 2026-10

## Context
A second exterior fidelity pass found four things that broke the valley's logic or its look:
* **Lights (TD-024).** Prop lights applied to every condition variant, so a smashed lantern still
  glowed. Flames and lamp globes "glowed" through the foliage shader's back-light translucency,
  which only shows when a light sits behind them and reads as nothing at night. The burn barrel's
  burning model was its clean variant, but every POI lit the worn, cold one. Nothing said what still
  burns in a valley whose power has been out for eighteen months.
* **The moon (TD-033)** was the sun's direction mirrored with an offset: no phases, rising and
  setting with the sun, every night the same.
* **Bridges (TD-036)** were straight chords at one deck height. A curving road bent at the
  abutments; there were no abutments; piers stood wherever the ground left room.
* **Supply drops (TD-029)** fell out of an empty sky: no drone, no sound, a landing check that
  ignored trees and the player's base, and a tether that named only the nearest drop.

## Decision
### What still burns
* **Mains power is dead.** Street lamps, canopy lights, ceiling lights, sconces, floor and desk
  lamps, signs and screens stay dark: their lights declare `"power": "mains"` and
  `PropDef.light_for()` returns nothing for them. A lit flag on one does nothing.
* **What burns is what somebody keeps fed**: candles, kerosene and propane lanterns, wood stoves and
  burn barrels (`"power": "flame"`), lit where a POI's story says so (`"lit": true`, as before).
  `battery` and `generator` are accepted for kit that brings its own power (none placed yet).
* **The Program's own kit runs on batteries**: the drone's nav lights and strobe and the tether are
  always on.

### Per-variant lights and glow that follows them
* `PropDef.light` keeps its keys and adds `power`, `variants` (per condition: overrides, or
  `false` for dark) and `fx` (`"fire"`: flames and a crackle, sized by `fx_size`). A destroyed
  variant is dark unless it lists a light of its own. `light_for(condition)` resolves the variant the
  way `model_for` does (a missing destroyed model falls back to worn, and so does its light). Unknown
  light keys, powers or variants fail validation.
* **Glow is emission, and it follows the light.** `std_surface` gets one minimal hunk, and every
  material that leaves `light_source` at 0 renders exactly as before:
  * `light_source` (material `int`, 0..2): 1 glows only while lit (lamp globes, lenses, embers,
    stove mica), showing its albedo when cold; 2 exists only while lit (flames: the vertex stage
    collapses a cold one to a point, so it draws nothing).
  * `emission_flicker` (material `float`): fire breathes. A sum of sines in the vertex stage,
    phased by world position so neighbouring candles and coals don't pulse together, scales a new
    varying (`v_emit`).
  * `light_lit` (instance uniform, **index 4**, after the four shared slots, which are unchanged:
    `instance_wear` 0, `instance_variation` 1, `bloom_glow` 2, `weather_exposure` 3): 1 on an
    instance whose light burns.
  * The emission line: a light source's emission is `emission_color × emission_energy × v_emit`
    instead of `× albedo`, so it glows in its emission colour whatever its albedo, and a cold ember
    is charcoal.
* `PropLights` builds what a burning prop shows. PoiBuilder draws each lit prop on its own instance
  with `light_lit` set (batched props share one instance-uniform value), adds its light at the full
  offset (it used the height only) and, for fires, flipbook flames and a crackle. A campfire's coals
  glow while it burns (`StructurePiece.set_lit`).
* **Models.** The burn barrel's worn variant is now a fire burning low, with coals in the ash. The
  coals are cold charcoal unless the barrel burns. The propane lantern has a clear globe around a
  mantle that glows white. The kerosene lanterns' globes are clear glass, so their flame shows. Stove
  mica glows. Church candles, the votive stand and the piano's sconces have flames.

### The moon
* `MoonModel` is a pure model driven by the world clock.
  * **Phase** = `(phase_at_start + days / synodic_days) mod 1`. The synodic month is 10 game days,
    not 29.5: the real month is too slow for runs of a few weeks, and 10 days walks the Hum (every
    7th night) through every phase.
  * **Position.** The moon sits `phase` of a turn east of the sun. Its hour angle is the sun's less
    the elongation, so it transits `phase × 24 h` after noon and rises ~24/(P − 1) h later each day.
    A full moon rises at dusk; a new moon keeps the sun's hours.
  * **Declination** follows a softened ecliptic (amplitude 14° at latitude 46°, plus a 5° node
    wobble). A summer full moon still stays up most of the night.
* **Light by phase.** Moonlight is `energy_full × lit^1.5`, dimmer and warmer near the horizon, and
  killed by cloud. Its colour runs from a blue crescent to a whiter full moon.
* **The night's darkness range is data** (`world_clock.json` "moon"). Ambient fill, night sky
  colours and star visibility run from the new-moon values to a high full moon's. At night the
  ambient comes from a set colour, not from the near-black sky, so the data is what the player gets.
  * A new moon is very dark but not black. The torch (13 m), the flashlight (28 m) and campfires
    still carry the night.
  * During the Hum the Bloom aurora adds a green fill (`hum_ambient`), so the exam night stays
    fightable under a new moon.
* **The sky shader draws the moon from uniforms**, as it now draws the sun: a hidden sun drops out
  of LIGHT0 at night and the moon would take its slot.
  * The disc is a sphere lit by `moon_sun_dir`, the sunlight direction at the moon. It is built so
    the lit limb points at the sun the player sees and the lit fraction is exactly the phase's.
  * It is shaded with the Lommel–Seeliger law: a full moon is flat, not limb-dark.
  * Its night side carries earthshine, strongest at new moon.
  * It hides the stars behind it and sits in an aureole that widens in thin cloud.
  * Moonlight silvers the clouds, brightens the night sky and drowns the faint stars, most of all
    near the moon.
* **The stars turn.** The star sphere wheels about the celestial pole (due north, at the latitude's
  altitude) once a sidereal day: one turn a year more than the sun makes
  (`EnvironmentController.star_basis()`). The star map is a 2:1 equirect whose stars are
  pre-stretched in longitude (`sky.py`), so the shader wraps it once round the sky: it used to tile
  it twice, which squeezed every star into a dash along its meridian.

### Bridges
* `BridgeBuilder.plan()` is a pure function of the deck centreline (the road's own points between
  the span ends) and the ground. It lays:
  * **Sections**: ~8 m chords of the curve, each angled to the next and lengthened by half the
    width × tan(half the bend) at each joint, so the outer edges meet.
  * **Abutments**: a seat where the bank has fallen 0.7 m clear of the girders' underside. Between
    the seat and the span end run **approach sections**: the same road between U-wing retaining
    walls that sink 4.6 m into the bank, holding the fill.
  * **Piers**: evenly spaced between the seats at ~22 m spans. The river profile (centreline, width
    and level) says which stand in the water, or in its flood channel (within 5 m of the edge on
    ground less than 1 m above the level): those are wall piers with round cutwaters, turned to
    the current unless the crossing is skewed past 35°. The rest are two-column bents.
* **The deck carries its own paint**: a double yellow no-passing line and white edge lines, worn
  through to the asphalt. RoadMarkings asks `BridgeBuilder.on_deck()` and keeps its decals off the
  curved decks, approaches included. The chord test is the fallback.
* **Guardrail posts carry delineators** (amber left, white right) in a new `retroreflector`
  shader: a narrow lobe returns light toward its source, so they flare in your own torch and stay
  dull plates otherwise. There is **no deck lighting**: the valley has no power.

### The Program's drone
* A generated heavy-lift coaxial X8, about 3.3 m across the rotor tips:
  * a white fibreglass hull with an orange nose and battery bays;
  * **Program livery** from a new atlas in the roadside stroke font: REMAND SALVAGE PROGRAM, unit
    RP-HL 09, the Cordon Authority roundel, a big belly number for spotters on the ground, a
    rotor caution strip, chevrons and a data plate;
  * carbon arms, coaxial motors, nav lights and a strobe, skids, a gimbal camera, and a cargo hook
    and sling down to the canister's lifting lugs;
  * rotors as a separate model the game spins over a faint blur disc.
* **The flight is a pure function of time** (`ProgramDrone.Flight`, numbers in
  `program_drone.json`):
  * in from 650 m out at cruise height, on a bearing fixed by the world seed and the drop;
  * braking to a hover over the spot, letting the lift go 1.2 s in;
  * then on and climbing away.
* The Drop owns the clock and moves both, so a frame skip or a test's single 60 s step still lands
  the canister where the drone let it go. The drone's racket over the spot is a stimulus, so
  Hollowed nearby come to look.
* **The rotor loop** is built periodic: eight rotors' blade-pass tones beating near 80 Hz, blade
  chop and motor whine. The game shifts its pitch for the doppler from the drone's velocity
  relative to the listener. The release has its own clunk and chute crack.
* **The landing check also keeps clear of trees and player structures.**
  * Trees come from the deterministic scatter's tree layer, felled ones excluded, so a spot 300 m
    out, beyond the pooled tree colliders, is still checked. The clearance is 4.5 m from the trunk:
    a crown would snag the chute.
  * Player structures come from the building manager (3.5 m).
  * Anything else solid comes from a physics query over the canister's footprint.
* **The tether lists every drop** with its distance, sector and state (inbound, falling, landed,
  opened), one to a line, paired up in short form past four. The Hum forecast moves down below
  them.

### Visual QA
`src/tools/cli/exterior_qa.gd` renders the moon full and new over Larch Pond and the drop-site
clearing, the Route 9 bridge from the bank and along its deck at night in a hand light, the light
props lit and destroyed side by side, and the drone hovering with a lift by day and at dusk.
`--only` picks shots and `--stream-wait` caps the wait for vegetation (software Vulkan streams it
slowly).

## Consequences
+ The valley's lighting tells its story: a lit window means somebody's candle; a smashed lantern,
  a dead street lamp or a cold barrel is dark.
+ No two nights look alike. The full moon reads, the new moon is near black, and the Hum drifts
  through the phases.
+ The Route 9 bridge stands on real supports and follows its road; reflectors trace the deck in your
  light.
+ Supply drops arrive. You hear them coming, watch them hover and drop, and find every one on the
  tether.
− `std_surface` has a fifth instance-uniform slot (`light_lit`, index 4). A material batched on the
  same instance must not claim index 4 for anything else.
− Lit props are drawn as their own MeshInstance3D instead of joining a MultiMesh batch: a few more
  draw calls per lit building (4 at most today).
− The moon's sky is self-consistent, but the game's sun is not a celestial model. The lit limb
  follows the visible sun instead of being derived from one shared sky.
− Abutment and pier models have fixed heights (7.3 m and 15 m below the road). A bridge over a
  deeper gorge would show their feet (TD-054).
− The drone is presentational. It is not saved mid-flight (a reloaded drop is already down), and
  nothing can shoot it (TD-055).
