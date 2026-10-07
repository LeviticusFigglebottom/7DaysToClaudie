# ADR-0057: Hunting and ranged: a bow, throwables and fire, a bolt-action rifle with aim, climbing

Status: Accepted

## Context

The survival loop had one ranged weapon (the .38 revolver, hitscan, reloaded on right mouse), a
thrown spear, and stones that were thrown and forgotten. Hunting deer meant walking up to them.
The Forest / Sons of the Forest and 7 Days to Die set the expectation: a crafted bow whose arrows
you take back, a stone to pull the dead away from you, a molotov for a crowd, a long gun for the
deer at the treeline, and somewhere high to shoot from. Session 5 made POI ladders climbable
(ADR-0051, `Player` climb getters); nothing first-person showed it. Nothing in the game burned.

## Decision

All tuning lives in item JSON (`equip`) or a config (`data/config/fire.json`, `climbing.json`,
`viewmodel.json` `aim` / `climb`). Each family's logic sits in its own file and is driven from
`PlayerEquipment` by small hunks, so the families never shared code paths they could break.

**1. The bow** (`BowHandler`, `BowRig`, `Arrow`; `hunting_bow`, `arrow_stone`, `arrow_bone`).
Hold attack to draw over `equip.draw_time`; let go past `min_draw` to loose, below it (or block,
or a freed mouse, or grabbing a ladder) to let down. Draw fraction lerps the arrow's speed
(`speed` [14, 50] m/s), damage (`damage_scale`) and spread (`draw_spread_deg`); holding full draw
past `full_hold_free` drains stamina. The arrow is a node, not a body: semi-implicit gravity and one
ray per physics step (as `ThrownSpear`), facing its velocity; a living Enemy or Animal takes pierce
`DamageInfo` (cause `arrow`, the shooter's id so kills and XP are the player's). It sticks: on a
body it rides the nearest bone and is pulled out once the body is dead; in ground, walls and trees
it joins `item_drops` and saves as a lying pickup; `break` rolls a splinter. The string and nocked
arrow are drawn every frame from the limb tips to the right-hand socket rather than baked, so the
draw is `fp_draw_bow` frozen at the fraction and a let-down plays it backwards.

**2. Throwables and fire** (`ThrowHand`, `ThrownItem`, `GroundFire`; `molotov`, `kerosene`,
`rotgut`). A throw charges while attack is held (`throw_speed` lerped over `charge_time`) and leaves
the hand at the use's `windup` frame. A thrown item's first contact emits a Stimuli sound of kind
`distraction` at the landing point with `equip.noise` loudness: the Hollowed already go to a sound's
position (`Enemy._perceive`), so a stone pulls them off the thrower with no AI change; deer look up
at a stone and bolt from a shattering bottle. A molotov `needs_light`: a lighter or torch in the pack
lights its rag through the existing light path (Stimuli light, `socket_flame` flame), the rag burns
`fuse` seconds, and a lit bottle shatters into a `GroundFire`: radius, `dps` to enemies and animals,
`player_dps`, `structure_dps` through each piece's `damage_mult.fire`, fade and linger, an ignite
sound and crackle the Hollowed hear, and a light that shows who stands by it. Fires are deliberately
not saved: one burns about 11 s.

**3. The rifle and aim** (`PlayerAim`, `RoundReload`, `ScopeOverlay`; `hunting_rifle`,
`ammo_308`). Right mouse aims any gun (a new `aim` action; `block` stays on the same button for the
things that guard); R reloads (a new `reload` action, sharing R with `rotate_piece`, which only acts
while building). Aim is a node-free state machine: camera FOV `2·atan(tan(base/2)/zoom)`, look
scaled by `1/zoom`, spread, sway and walk speed multiplied, all from `viewmodel.json` `aim` with
per-gun `equip.aim` overrides (rifle zoom 4 and a scope picture; revolver iron sights). The aim pose
is measured, not authored: each hold names a sight socket, and the viewmodel applies the rigid
offset that puts it on the line of sight, frozen while an action plays so recoil and the bolt still
move the gun. The rifle is held in the left hand so the right works the bolt; `fire_rifle` is the
shot and the bolt cycle and its length gates the next shot; reload is round by round (open, a round
per `reload_time`, close; firing stops it with the rounds kept).

**4. Climbing** (`ViewModelClimb`, `ClimbMount`; `hunting_stand`, `climbing_rope`). Movement is
session 5's (`Player.is_climbing/climbing_ladder/climb_speed`, polled each frame). The arms are a
cycle *seeked* by distance climbed (`climb_speed × dt / cycle_m`), backwards going down and still
when the player is, each hand gripping 70% of the cycle and riding down with the rails; the held
item is hidden, not unequipped, and the rig is squared to the ladder's `face()`. Stands and ropes
add no movement code: `ClimbMount` places a `PoiPieces.Ladder` in any structure that provides
`climb` (the stand's hatch ladder) or hangs one over the ledge a rope is set down at (searching
forward for a 1.5–14 m drop, saved in world flags so reloads don't wait on terrain).

## Consequences

* Four families shipped in parallel with only additive hunks in `player_equipment.gd`,
  `viewmodel.gd` and `viewmodel.json`; the merges conflicted only where two hunks sat side by side.
* Fire is a first system, not a fire model: no burning status, spread or avoidance yet
  (TD-292, TD-293). Arrows in bodies vanish with the body until wildlife and corpses persist (TD-289).
* R and right mouse each carry two actions, kept apart by context; both stay separately rebindable.
* Climbing hands meet the rails only at the default FOV (TD-296); you can't climb down a rope from
  its top until the player's grab accepts a landing behind the rails (TD-295, session 5's code).
* Remaining debts: TD-289..TD-298.
