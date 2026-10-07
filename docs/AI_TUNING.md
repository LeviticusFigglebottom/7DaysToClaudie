# AI tuning: how soon the Hollowed notice you

Owner report (played on a real GPU): *"the zombies seem passive until you're close."* Target feel
(7 Days to Die / The Forest): by day in the open a Hollow notices an upright, moving player at
roughly 25–40 m, sooner at night if the player carries a light; crouching in cover cuts that a
lot; once it notices it commits fast, and the Hollowed near it join in. Wanderers roam.

This page records what was found, the probe used to measure it, and what changed. "Before" is
with session 3's fix of the sky's light (commit 733dd80: GameWorld feeds
`Stimuli.ambient_light` from `EnvironmentController.ambient_light_level()`) applied and no tuning.

## The probe

`game/src/tools/cli/aggro_probe.gd` (+ `aggro_probe_runner.gd`), two modes:

* **World** (session 3's): `godot --headless --path game -s res://src/tools/cli/aggro_probe.gd`
  (~6 min). A real new game on the main map; for each type, day (12:00) and night (23:00), the
  player standing or strafing at walking speed, one awake wanderer facing the player at 5..60 m:
  does it start a chase within 4 s? (Fixed here: the body used to turn straight back to its random
  spawn yaw, so "standing" rows were partly noise.)
* **Flat** (`-- --flat`, run with `--fixed-fps 60`, ~2 min): a controlled matrix. Each trial
  builds a fresh flat floor, Stimuli, AIDirector and Player (driven through the real input
  actions, stamina topped up), lets the player settle into the stance for a second, then spawns
  one enemy `d` m away facing the player (**F**) or side-on, looking 90° away (**S**). The player
  paces sideways ±3 m. Stances: `still`, `walk` (3.4 m/s), `crouch` (crouch-walk 1.7 m/s), `sprint`
  (6.2 m/s), `torch` (walking with a lit torch), `cover` (crouch-walking behind a 10 m × 1.3 m log
  on the vegetation layer 1.5 m in front), `log` (walking upright behind the same log: it sees
  your head over it and has to go round). Night is a moonless `ambient_light` 0.05 (the world
  gives 0..0.15 by the moon). Cell = **time to notice** (`s` saw the player, `i` investigates a
  sound or scent) **→ time to get within 2 m**; `-` = not noticed in 30 s / not reached in 90 s
  (simulated seconds). The *group* line puts a second Hollow 15 m behind a spotter (25 m from the
  walking player), looking away, and times when it joins in. There is no navmesh on the flat
  floor: before round 2 a body that saw you over the log walked into it and never arrived.
  Side-on cells of 13–28 s are not perception: the Hollow wandered, turned and then saw you.

Default game rules throughout (day speed `walk` = 0.6 × a type's own speeds, night `run` = 1.0).

## Findings (before)

Nothing global stops perception near or far; the causes are tuning, the newly fed darkness, and
three missing mechanisms.

1. **Daytime sight was short.** `Stimuli.detection_range()` (`game/src/ai/perception/stimuli.gd:236`
   at HEAD) is `base_sight × clamp(0.15 + light × 0.85) × crouch 0.55 × (0.75 + speed/6 × 0.5)`, plus
   the carried-light beacon `max(r, base × 1.6 + 30)` (`:242`). A Hollow's `sight_day` was **12 m**
   (`game/data/enemies/hollowed.json`): **9 m** for a player standing still, **12.4 m** walking,
   **15 m** sprinting, **5.9 m** crouch-walking (Lurcher 20 m, Keener 26, Dragger 8). And early in
   a game `AIDirector.allowed_enemy()` (`ai_director.gd:112`) swaps every type the gamestage
   doesn't allow for a basic Hollow, so the early game is all 12 m Hollows.
2. **Nights went blind once the sky's light was fed** (733dd80). `ambient_light` used to stay 1.0
   (so nights read as full daylight, with the longer night ranges); now it is 0..0.15 at night and
   the `0.15 + 0.85 × light` curve leaves a Hollow **~13–20 %** of its 32 m: ~5 m. Flat probe: by
   night a walking player was not noticed even at 10 m. The same curve also hit the hounds (their
   night range 40 m → ~6 m) and the Ashen, whose `sight_night` (18–24 m) already encodes darkness.
3. **The carried-light beacon ignored daylight** (49 m for a Hollow by day) and dwarfs everything
   at night (`base × 1.6 + 30` = 81 m for 32 m night sight).
4. **Daytime chase was a crawl.** `day_run` 1.5 m/s × the default day rule `walk` (0.6,
   `game/data/config/game_rules.json:65`) = **0.9 m/s**, wander 0.51 m/s; a Lurcher ("sprints even
   by day") 2.3 m/s.
5. **Investigating walked.** `INVESTIGATE` moved at `_speed(is_night())` (`enemy.gd:361` at HEAD):
   the walk speed by day (0.51 m/s), so a Hollow that heard you strolled over and usually gave up.
6. **No group alerting.** `Events.enemy_alerted` (`enemy.gd:626`, `:738`, `:878` at HEAD) has no
   listener; a Hollow that spotted you made a sound only the player hears.
7. **Wanderers barely moved.** `IDLE` → `WANDER` to `home ± 12 m` (`enemy.gd:353-354`), and the
   idle timer re-rolled `randf_range(4, 9)` every frame (so it ended at ~4 s anyway).
8. **Trees and logs were no cover.** `SIGHT_MASK` (`enemy.gd:30`) is world | structures |
   sight_blockers; vegetation (layer 13, `1 << 12`) didn't block sight.
9. **Field of view only.** FOV 120° (±60°): a moving player at a Hollow's shoulder was invisible.

Checked and **not** a cause:
* Perception rate: every 0.25 s within 60 m, every 0.75 s beyond (`enemy.gd:321`).
* `KINEMATIC_BEYOND = 110` (`enemy.gd:33`, `:447`): past 110 m bodies glide on the heightfield (no
  collision, no navmesh) but still perceive.
* AIDirector: no AI LOD; `_process` only spawns/despawns (190 m, `ai_director.gd:12`). GameWorld's
  `_hold_processing` (`game_world.gd:215`) only holds systems during boot. No streaming path
  freezes enemies. POI sleepers exist only within 46 m of their building (PoiManager, by design).
* `_perceive` early-outs (`enemy.gd:581`): dead player, no Stimuli, or the debug flag `invisible`.
* Hearing: footsteps are emitted (`player.gd:369`): walk 6 m, sprint 14 m, crouch 2 m
  (`data/config/player.json` `noise`), ×1.3 on wood/gravel/metal/leaves; gunshots use the
  weapon's `noise` (120 m default). Unchanged (sleepers listen to the same sounds).
* Scent: deposited every 0.5 s; idle Hollowed follow a trail above 2.0. Works.
* Memory 9 s (`MEMORY_SECONDS`) then INVESTIGATE of the last seen spot. Fine.

## Changes

Data:
* `game/data/enemies/hollowed.json` (every Hollowed type):
  * `sight_day` / `sight_night`: Hollow 12/32 → **32/40**, Lurcher 20/40 → **36/48**, Keener
    26/44 → 36/50, Dragger 8/20 → 16/26, Blister 22/36 → 30/42, Husk 14/30 → 26/38, Rammer
    18/32 → 28/40. The Hollow is what the early-game type swap spawns, so it got the big raise.
  * **`dark_sight` 0.8** (new, read by `Stimuli.detection_range`): the share of sight kept in pitch
    dark. The Hollowed see in the dark (DESIGN §6): at night a Hollow's base is 40 × ~0.8 = 32 m.
  * `light_beacon` (optional; default 1.6 × `sight_night`: 64 m for a Hollow, 77 m for a Lurcher):
    how far a carried light shows at night, instead of `base × 1.6 + 30`.
  * `sleep_sight_day` / `sleep_sight_night` = the old values: a POI sleeper's eyes (× 0.35 × wake
    factor, light-blind as before) are exactly what they were; `sleeper_alertness` unchanged.
  * Day speeds (before the rule's 0.6): Hollow walk/run 0.85/1.5 → **1.6/4.0** (wander 0.96, chase
    **2.4 m/s**: a walking player at 3.4 m/s still out-walks it; the `jog`/`run` rules give
    3.2/4.0), Lurcher 1.3/3.8 → 1.8/6.0 (3.6 m/s), Keener 1.0/2.2 → 1.4/3.6, Blister 0.8/1.4 →
    1.2/3.0, Husk 0.75/1.3 → 1.1/3.0, Rammer 0.9/1.6 → 1.3/3.4. Night speeds unchanged.
* `game/data/enemies/hounds.json`, `ashen.json`: `dark_sight` 1.0, which keeps their sight exactly
  as it was tuned before the sky's light was fed (the Ashen's night ranges already encode the dark).

So in the open a Hollow notices you at: by day **24 m standing still, 33 m walking, 40 m sprinting,
16 m crouch-walking, 13 m crouched still**; on a dark night 24/33/40/16/13 m as well (32 m base),
**64 m with a torch** (by day a torch only adds the light it casts: ~41 m walking).

Code:
* `Stimuli.detection_range()` (`stimuli.gd`, one hunk): two optional parameters, `dark_sight`
  (default 0.15) and `beacon` (default `base × 1.6 + 30`); the defaults are the original curve, so
  wildlife (`wildlife_manager.gd:157`) and every other caller are unchanged. The
  `ambient_light` comment now says it is fed.
* `game/src/ai/enemy/enemy.gd` (small commented hunks). Everything below applies to *plain*
  Hollowed (`_plain_hollowed()`: not a hound, not an Ashen) unless said:
  * `_perceive` passes `dark_sight` (1.0 for a sleeper) and, awake, `light_beacon`; a carried light
    is a beacon only at night or underground (sleepers, hounds and the Ashen keep the old rule).
  * `SIGHT_MASK` gains vegetation (`1 << 12`): trunks, thickets and logs near the player are cover
    (for everyone, and for a strike's line of sight).
  * Peripheral vision: a **moving** player up to 45° past the edge of the FOV is seen at half the
    range (`PERIPHERAL_DEG`, `PERIPHERAL_RANGE`). Not for sleepers.
  * `INVESTIGATE` by day goes at `DAY_INVESTIGATE_PACE` (0.75) of the run speed, a jog (1.8 m/s for
    a Hollow); at night it runs, as before.
  * Group alerting `_alert_nearby()`: on the first sighting (with the alert cry and
    `Events.enemy_alerted`), every awake plain Hollowed within `behavior.alert_radius` (default
    30 m) that is idle, wandering or investigating `notice()`s the player's position and comes at a
    jog. Sleepers, hounds, the Ashen and Hum members don't answer; joiners only investigate, so
    there is no runaway chain: each must see you itself before it calls out in turn.
  * Wandering: IDLE lasts 2.5–6 s (rolled once) and a roaming Hollow wanders 8 m to
    `behavior.roam_radius` (default 30 m) from home, its home drifting halfway along each leg.
    POI bodies, hounds (packs) and the Ashen keep the old 12 m box.
* AIDirector: unchanged.

## Tables

### Flat matrix, before (733dd80, no tuning)

| enemy | time | stance | 10 m F | 10 m S | 20 m F | 20 m S | 30 m F | 30 m S | 40 m F | 40 m S | 60 m F | 60 m S |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hollow | day | still | 22.9s -> 27 | 22.9s -> 27 | - | - | - | - | - | - | - | - |
| hollow | day | walk | 0.5s -> 6 | 18.6s -> 26 | - | - | - | - | - | - | - | - |
| hollow | day | crouch | - | - | - | - | - | - | - | - | - | - |
| hollow | day | sprint | 0.2s -> 6 | 0.2i -> 6 | - | - | - | - | - | - | - | - |
| hollow | day | torch | 0.2s -> 6 | 15.7s -> 24 | 0.2s -> 13 | 15.7s -> 32 | 0.2s -> 20 | 15.7s -> 38 | 0.2s -> 26 | 15.7s -> 45 | - | - |
| hollow | day | cover | - | - | - | - | - | - | - | - | - | - |
| hollow | night | still | - | - | - | - | - | - | - | - | - | - |
| hollow | night | walk | - | - | - | - | - | - | - | - | - | - |
| hollow | night | crouch | - | - | - | - | - | - | - | - | - | - |
| hollow | night | sprint | 0.2i -> 2 | 0.2i -> 2 | - | - | - | - | - | - | - | - |
| hollow | night | torch | 0.2s -> 2 | 13.3s -> 16 | 0.2s -> 5 | 13.3s -> 19 | 0.2s -> 7 | 13.3s -> 21 | 0.2s -> 9 | 13.3s -> 23 | 0.2s -> 14 | 13.7s -> 28 |
| hollow | night | cover | - | - | - | - | - | - | - | - | - | - |
| lurcher | day | still | 0.2s -> 2 | 13.3s -> 17 | - | - | - | - | - | - | - | - |
| lurcher | day | walk | 0.2s -> 2 | 13.3s -> 17 | 0.5s -> 6 | 16.5s -> 22 | - | - | - | - | - | - |
| lurcher | day | crouch | 17.0s -> 19 | 17.0s -> 19 | - | - | - | - | - | - | - | - |
| lurcher | day | sprint | 0.2s -> 2 | 0.2i -> 3 | 0.2s -> 6 | 13.3s -> 20 | - | - | - | - | - | - |
| lurcher | day | torch | 0.2s -> 2 | 13.3s -> 17 | 0.2s -> 5 | 13.3s -> 19 | 0.2s -> 8 | 13.3s -> 22 | 0.2s -> 10 | 13.3s -> 24 | 0.2s -> 16 | 15.2s -> 31 |
| lurcher | day | cover | 17.0s -> - | 17.0s -> - | - | - | - | - | - | - | - | - |
| lurcher | night | still | - | - | - | - | - | - | - | - | - | - |
| lurcher | night | walk | 16.2s -> 17 | 16.2s -> 17 | - | - | - | - | - | - | - | - |
| lurcher | night | crouch | - | - | - | - | - | - | - | - | - | - |
| lurcher | night | sprint | 0.2i -> 2 | 0.2i -> 2 | 16.0i -> 19 | 16.0i -> 19 | - | - | - | - | - | - |
| lurcher | night | torch | 0.2s -> 2 | 12.0s -> 14 | 0.2s -> 4 | 12.0s -> 16 | 0.2s -> 5 | 12.0s -> 18 | 0.2s -> 7 | 12.0s -> 20 | 0.2s -> 11 | 12.2s -> 23 |
| lurcher | night | cover | - | - | - | - | - | - | - | - | - | - |

* group (day): spotter 25 m facing the walking player; buddy 15 m behind it facing away: spotter -, buddy -
* group (night): spotter 25 m facing the walking player; buddy 15 m behind it facing away: spotter -, buddy -

### Flat matrix, after

| enemy | time | stance | 10 m F | 10 m S | 20 m F | 20 m S | 30 m F | 30 m S | 40 m F | 40 m S | 60 m F | 60 m S |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hollow | day | still | 0.2s -> 2 | 20.5s -> 26 | 0.2s -> 5 | 25.8s -> 31 | - | - | - | - | - | - |
| hollow | day | walk | 0.2s -> 2 | 0.2s -> 2 | 0.2s -> 5 | 20.0s -> 28 | 0.5s -> 8 | 26.3s -> 34 | - | - | - | - |
| hollow | day | crouch | 0.2s -> 2 | 26.1s -> 29 | - | - | - | - | - | - | - | - |
| hollow | day | sprint | 0.2s -> 2 | 0.2s -> 2 | 0.2s -> 5 | 19.7s -> 28 | 0.2s -> 8 | 22.1s -> 31 | - | - | - | - |
| hollow | day | torch | 0.2s -> 2 | 0.2s -> 2 | 0.2s -> 5 | 0.5s -> 5 | 0.2s -> 8 | 20.8s -> 31 | 0.5s -> 10 | - | - | - |
| hollow | day | cover | - | - | - | - | - | - | - | - | - | - |
| hollow | night | still | 0.2s -> 2 | - | 0.2s -> 4 | - | - | - | - | - | - | - |
| hollow | night | walk | 0.2s -> 2 | 0.2s -> 2 | 0.2s -> 5 | - | 0.5s -> 7 | - | - | - | - | - |
| hollow | night | crouch | 0.2s -> 2 | - | - | - | - | - | - | - | - | - |
| hollow | night | sprint | 0.2s -> 2 | 0.2s -> 2 | 0.2s -> 5 | 0.2s -> 5 | 0.2s -> 7 | - | 0.2s -> 9 | - | - | - |
| hollow | night | torch | 0.2s -> 2 | 0.2s -> 2 | 0.2s -> 5 | 0.2s -> 5 | 0.2s -> 7 | 0.2s -> 7 | 0.2s -> 9 | - | 0.2s -> 14 | 4.7s -> 18 |
| hollow | night | cover | - | - | - | - | - | - | - | - | - | - |
| lurcher | day | still | 0.2s -> 2 | 18.4s -> 22 | 0.2s -> 3 | 22.4s -> 26 | 27.7s -> 32 | 27.7s -> 32 | - | - | - | - |
| lurcher | day | walk | 0.2s -> 2 | 0.2s -> 2 | 0.2s -> 3 | 18.4s -> 24 | 0.5s -> 5 | 22.1s -> 28 | - | - | - | - |
| lurcher | day | crouch | 0.2s -> 2 | 22.4s -> 25 | 27.9s -> 30 | 27.9s -> 30 | - | - | - | - | - | - |
| lurcher | day | sprint | 0.2s -> 2 | 0.2s -> 2 | 0.2s -> 3 | 0.2s -> 3 | 0.2s -> 5 | 18.4s -> 25 | 0.2s -> 7 | - | 23.4s -> 31 | 23.4s -> 31 |
| lurcher | day | torch | 0.2s -> 2 | 0.2s -> 2 | 0.2s -> 3 | 0.5s -> 4 | 0.2s -> 5 | 18.4s -> 26 | 0.5s -> 7 | - | 22.6s -> 30 | 22.6s -> 30 |
| lurcher | day | cover | - | - | - | - | - | - | - | - | - | - |
| lurcher | night | still | 0.2s -> 2 | 18.4s -> 22 | 0.2s -> 3 | 21.0s -> 26 | 26.3s -> 31 | 26.3s -> 31 | - | - | - | - |
| lurcher | night | walk | 0.2s -> 2 | 0.2s -> 2 | 0.2s -> 4 | 0.8s -> 4 | 0.2s -> 5 | 20.0s -> 27 | 0.8s -> 8 | - | - | - |
| lurcher | night | crouch | 0.2s -> 2 | 21.8s -> 25 | 27.4s -> 30 | 27.4s -> 30 | - | - | - | - | - | - |
| lurcher | night | sprint | 0.2s -> 2 | 0.2s -> 2 | 0.2s -> 4 | 0.2s -> 4 | 0.2s -> 6 | 18.4s -> 26 | 0.2s -> 7 | - | 21.0s -> 30 | 21.0s -> 30 |
| lurcher | night | torch | 0.2s -> 2 | 0.2s -> 2 | 0.2s -> 4 | 0.2s -> 4 | 0.2s -> 5 | 0.2s -> 5 | 0.2s -> 7 | - | 0.2s -> 11 | 4.7s -> 15 |
| lurcher | night | cover | - | - | - | - | - | - | - | - | - | - |

* group (day): spotter 25 m facing the walking player; buddy 15 m behind it facing away: spotter 0.1s -> 6, buddy 0.1i -> 10
* group (night): spotter 25 m facing the walking player; buddy 15 m behind it facing away: spotter 0.1s -> 6, buddy 0.1i -> 9

### World probe (main map, chase within 4 s), before

```
enemy | time | player | noticed at (m) of [5.0, 10.0, 15.0, 20.0, 30.0, 45.0, 60.0]
hollow       | day   | standing | Y . . . . . .
hollow       | day   | walking  | Y Y . . . . .
hollow       | night | standing | Y . . . . . .
hollow       | night | walking  | Y . . . . . .
lurcher      | day   | standing | Y Y . . . . .
lurcher      | day   | walking  | Y Y Y . . . .
lurcher      | night | standing | Y . . . . . .
lurcher      | night | walking  | Y . . . . . .
keener       | day   | standing | Y Y Y . . . .
keener       | day   | walking  | Y Y Y Y . . .
keener       | night | standing | Y . . . . . .
keener       | night | walking  | Y . . . . . .
hollow_hound | day   | standing | Y Y Y . . . .
hollow_hound | day   | walking  | Y Y Y Y . . .
hollow_hound | night | standing | Y Y Y . . . .
hollow_hound | night | walking  | Y Y Y . . . .
```

### World probe, after

```
enemy | time | player | noticed at (m) of [5.0, 10.0, 15.0, 20.0, 30.0, 45.0, 60.0]
hollow       | day   | standing | Y Y Y Y . . .
hollow       | day   | walking  | Y Y Y Y Y . .
hollow       | night | standing | Y Y Y Y . . .
hollow       | night | walking  | Y Y Y Y Y . .
lurcher      | day   | standing | Y Y Y Y . . .
lurcher      | day   | walking  | Y Y Y Y Y . .
lurcher      | night | standing | Y Y Y Y . . .
lurcher      | night | walking  | Y Y Y Y Y . .
keener       | day   | standing | Y Y Y Y . . .
keener       | day   | walking  | Y Y Y Y Y . .
keener       | night | standing | Y Y Y Y Y . .
keener       | night | walking  | Y Y Y Y Y . .
hollow_hound | day   | standing | Y Y Y . . . .
hollow_hound | day   | walking  | Y Y Y Y . . .
hollow_hound | night | standing | Y Y Y Y . . .
hollow_hound | night | walking  | Y Y Y Y Y . .
```

Reading them: by day a Hollow facing you now notices a walking player at 30 m in 0.5 s and is on
you in ~8 s (before: 10 m at most); crouch-walking it notices only inside ~16 m; behind the log it
never sees you. On a dark night it is as sharp as by day (before: blind past ~5 m), and a torch
shows you at 60 m. The buddy behind a spotter joins in 0.1 s and arrives a few seconds after it
(before: never). On the main map the Hollow, Lurcher and Keener now chase a walking player out to 30 m by day and by
night (before: 5–15 m for the Hollow); hounds read as they did before the sky's light was fed.

## Round 2: first contact, logs, wildlife at night (TD-191)

### What was found

* **First contact was a hard edge.** `_perceive` turned a sighting straight into CHASE (alert cry,
  group call) on the first perception tick in range: one step inside 33 m and a Hollow that had
  not reacted at all was running. Wanderers spawn 70–120 m off (`ai_director.gd`, `SPAWN_MIN/MAX`),
  far past any sight range (40 m at most, 64 m for a torch at night), so first contact always
  comes at that edge as they roam in.
* **Logs.** Off the nav tiles `_move_dir` is a straight line, and on them it isn't much better for
  a log: `NavTiles` does take trunks and the `medium` vegetation layer
  (`VegetationManager.obstacles_in_rect`), but each as a square of side 2 × radius at its origin, so
  a 5–6 m fallen log is carved only as a ~0.6 m square at its middle and paths run through its
  ends. A body that met a log broadside got a sideways slide of ~0 from `move_and_slide`, and the
  only fallback, the stuck jitter (a random point ±3 m after 2.5 s), is overwritten every frame in
  CHASE while it can see you. Flat probe `log` row before: noticed in 0.2–0.8 s, never arrived.
* **Wildlife at night.** `WildlifeManager.senses_context` gave every animal the player's
  `Stimuli.detection_range(1.0, light, ...)` (the person's 0.15 dark curve), and
  `WildlifeBrain.person_threat` then cut sight by 0.45 at night again. That 0.45 was tuned while
  `ambient_light` stayed 1.0 at night; with the sky's light fed (733dd80) the dark was counted
  twice: a deer saw a walking man at ~7–10 m by moon or starlight and only bolted inside 15 m (half
  its flight distance, the brain's floor); a hare at 4 m.

### Changes

* **Noticing** (`enemy.gd`, `_noticed()` + a hunk in `_perceive` and one in the state match): an
  awake plain Hollow (not a hound, not the Ashen, not the Hum, not one already hunting or one that
  saw you within its 9 s memory) that sees you builds suspicion instead of committing. It needs
  `NOTICE_EDGE × (distance / range)²` s, at least `NOTICE_MIN` 0.25 s (one perception tick): at
  once within ~38 % of its range (~12 m for a walking player by day), ~0.6 s at 20 m, ~1.5 s at
  30 m, 1.75 s at the edge; peripheral sightings measure against the peripheral range; an
  investigating one (it heard you, or was called) needs half. The first glimpse plays a low
  groan; IDLE and WANDER stop and turn to face where it saw you; then the alert cry, the group call
  and CHASE as before. Out of sight the suspicion drains at 0.5 a second. The detection ranges are
  unchanged; the 8 tests in `test_hollowed_aggro.gd` pass with their timing as it was (they allow
  8 ticks; the slowest, a torch at 55 m by night, now needs 6).
* **Going round** (`enemy.gd`, `_detour()` / `_check_detour()` / `_wall_normal()` /
  `_way_clear()`, two lines in `_move`): after a move, a body pressed against a static face (not
  the ground, a body, a structure or a breakable, which still go to BREAK) and getting less than
  70 % of its speed toward its goal starts a detour: it slides along the face, to the side its goal
  leans to (either, square on), kept for 4 s so it doesn't dither along a long log, flipped if it
  is wedged 0.8 s. The detour holds 1.2 s after the last bump and ends as soon as a knee-height
  ray (0.45 m, 3 m long; slope hits count as clear) toward the goal is clear. No path queries;
  it works on and off the nav tiles. The probe's new `log` row: every cell arrives (5–13 s facing,
  vs never).
* **Wildlife** (`WildlifeBrain.visibility()`, `senses.dark_sight` in `data/wildlife/deer.json`):
  the context now carries the player's stance/movement/perk/light share in full light (`lit`) and
  the light on them; each species sees that through its own `dark_sight` (deer 0.4, hare 0.5; the
  default 0.15 is a person's eye), and `person_threat` lost its extra night cut. The animals also
  hear the player's footsteps (Stimuli kind `footstep`, walk 6 m, sprint 14, crouch 2 × hearing),
  which were below the 10 m floor of the loud-sound channel: a deer looks up at a tread within
  ~8 m, a sprint sends a hare off. By day nothing changes (light 1.0).

### Wildlife measurement

`game/tests/unit/test_wildlife_night.gd` (`test_probe` prints it): an animal at the origin and the
player at 20/40/80 m (F flee, A alert, - nothing), and the player walking (3.4 m/s) or
crouch-walking (1.7 m/s) straight at it from 120 m, thinking every 0.25 s as `Animal` does: where it
looks up and where it bolts (and after how long). Light on the player: day 1.0, dusk 0.35, a
moonlit night 0.15, a moonless one 0.05. Upwind reads the same as calm; downwind is unchanged
(a deer bolts at 99 m walking or crouched, a hare at 27 m, in any light).

| animal | light | stance | before: 20/40/80 m | looks up | bolts | after: 20/40/80 m | looks up | bolts |
|---|---|---|---|---|---|---|---|---|
| deer | day | walk | F A - | 60 m | 32 m (26.0 s) | F A - | 60 m | 32 m (26.0 s) |
| deer | day | crouch | A - - | 36 m | 18 m (60.2 s) | A - - | 36 m | 18 m (60.2 s) |
| deer | dusk | walk | F - - | 37 m | 32 m (26.0 s) | F A - | 50 m | 32 m (26.0 s) |
| deer | dusk | crouch | - - - | 17 m | 17 m (60.5 s) | A - - | 24 m | 18 m (60.2 s) |
| deer | moon | walk | - - - | 15 m | 15 m (30.8 s) | F A - | 40 m | 32 m (26.0 s) |
| deer | moon | crouch | - - - | 9 m | 9 m (65.5 s) | - - - | 19 m | 18 m (60.2 s) |
| deer | dark | walk | - - - | 15 m | 15 m (30.8 s) | F - - | 35 m | 32 m (26.0 s) |
| deer | dark | crouch | - - - | 9 m | 9 m (65.5 s) | - - - | 17 m | 17 m (60.8 s) |
| hare | day | walk | - - - | 20 m | 9 m (32.8 s) | - - - | 20 m | 9 m (32.8 s) |
| hare | day | crouch | - - - | 12 m | 5 m (67.8 s) | - - - | 12 m | 5 m (67.8 s) |
| hare | dusk | walk | - - - | 14 m | 9 m (32.8 s) | - - - | 20 m | 9 m (32.8 s) |
| hare | dusk | crouch | - - - | 7 m | 5 m (67.8 s) | - - - | 10 m | 5 m (67.8 s) |
| hare | moon | walk | - - - | 4 m | 4 m (34.0 s) | - - - | 17 m | 9 m (32.8 s) |
| hare | moon | crouch | - - - | 2 m | 2 m (69.2 s) | - - - | 8 m | 5 m (67.8 s) |
| hare | dark | walk | - - - | 4 m | 4 m (34.0 s) | - - - | 15 m | 9 m (32.8 s) |
| hare | dark | crouch | - - - | 2 m | 2 m (69.2 s) | - - - | 7 m | 5 m (67.8 s) |

So at night a deer again sees a walking man at 35–40 m and bolts at its 32 m flight distance
(DESIGN §6), crouching gets you to ~17 m, dusk (its hour) is nearly day, and the wind carries your
scent 90 m as it always did; the hare sits tight to 9 m walking, 5 m crouched, as by day.

### Flat matrix, round 2 (after)

Times to notice now include the build-up (before, same rows: 0.2 s at 10–20 m, 0.5 s at 30 m
facing a walking player; see "Flat matrix, after" above). `log` before: `0.2s -> -` in every
noticed cell (never arrived).

| enemy | time | stance | 10 m F | 10 m S | 20 m F | 20 m S | 30 m F | 30 m S | 40 m F | 40 m S | 60 m F | 60 m S |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hollow | day | still | 0.5s -> 2 | 22.1s -> 28 | 1.3s -> 6 | 27.4s -> 33 | - | - | - | - | - | - |
| hollow | day | walk | 0.5s -> 3 | 0.5s -> 3 | 1.0s -> 6 | 24.5s -> 32 | 1.8s -> 9 | 28.5s -> 36 | - | - | - | - |
| hollow | day | crouch | 0.8s -> 3 | 28.7s -> 31 | - | - | - | - | - | - | - | - |
| hollow | day | sprint | 0.2s -> 2 | 0.5s -> 3 | 0.5s -> 6 | 21.3s -> 29 | 1.3s -> 9 | 25.3s -> 35 | - | - | - | - |
| hollow | day | torch | 0.2s -> 2 | 0.5s -> 3 | 0.8s -> 6 | 1.0s -> 6 | 1.3s -> 8 | 24.2s -> 34 | 2.1s -> 12 | - | - | - |
| hollow | day | cover | - | - | - | - | - | - | - | - | - | - |
| hollow | day | log | 0.5s -> 5 | 0.8s -> 6 | 1.0s -> 13 | 24.5s -> 36 | 1.8s -> 13 | 28.5s -> 40 | - | - | - | - |
| hollow | night | still | 0.5s -> 2 | - | 1.3s -> 5 | - | - | - | - | - | - | - |
| hollow | night | walk | 0.5s -> 2 | 0.5s -> 2 | 0.8s -> 5 | - | 1.8s -> 8 | - | - | - | - | - |
| hollow | night | crouch | 0.8s -> 3 | - | - | - | - | - | - | - | - | - |
| hollow | night | sprint | 0.2s -> 2 | 0.5s -> 2 | 0.5s -> 5 | 0.8s -> 6 | 1.3s -> 8 | - | 3.9s -> 13 | - | - | - |
| hollow | night | torch | 0.2s -> 2 | 0.2s -> 2 | 0.2s -> 5 | 0.5s -> 5 | 0.5s -> 7 | 0.8s -> 8 | 0.8s -> 10 | - | 1.7s -> 16 | 6.3s -> 20 |
| hollow | night | cover | - | - | - | - | - | - | - | - | - | - |
| hollow | night | log | 0.5s -> 5 | 0.8s -> 5 | 1.0s -> 9 | - | 1.8s -> 11 | - | - | - | - | - |
| lurcher | day | still | 0.2s -> 2 | 20.0s -> 24 | 1.0s -> 4 | 23.9s -> 28 | 29.3s -> 33 | 29.3s -> 33 | - | - | - | - |
| lurcher | day | walk | 0.2s -> 2 | 0.5s -> 2 | 0.8s -> 4 | 20.2s -> 26 | 1.5s -> 6 | 24.2s -> 30 | - | - | - | - |
| lurcher | day | crouch | 0.8s -> 2 | 24.5s -> 27 | 29.5s -> 32 | 29.5s -> 32 | - | - | - | - | - | - |
| lurcher | day | sprint | 0.2s -> 2 | 0.5s -> 2 | 0.5s -> 4 | 0.8s -> 4 | 1.0s -> 6 | 21.0s -> 28 | 2.3s -> 9 | - | 29.5s -> 37 | 29.5s -> 37 |
| lurcher | day | torch | 0.2s -> 2 | 0.5s -> 2 | 0.5s -> 4 | 1.0s -> 4 | 1.0s -> 6 | 20.2s -> 27 | 1.8s -> 8 | - | 24.7s -> 32 | 24.7s -> 32 |
| lurcher | day | cover | - | - | - | - | - | - | - | - | - | - |
| lurcher | day | log | 0.5s -> 5 | 0.8s -> 5 | 0.8s -> 7 | 20.2s -> 28 | 1.5s -> 9 | 24.2s -> 33 | - | - | - | - |
| lurcher | night | still | 0.2s -> 2 | 19.7s -> 24 | 1.0s -> 4 | 22.6s -> 27 | 27.9s -> 33 | 27.9s -> 33 | - | - | - | - |
| lurcher | night | walk | 0.2s -> 2 | 0.5s -> 2 | 0.8s -> 4 | 1.3s -> 5 | 1.3s -> 6 | 24.5s -> 31 | 2.9s -> 10 | - | - | - |
| lurcher | night | crouch | 0.5s -> 2 | 23.7s -> 27 | 29.0s -> 32 | 29.0s -> 32 | - | - | - | - | - | - |
| lurcher | night | sprint | 0.2s -> 2 | 0.5s -> 2 | 0.5s -> 4 | 0.5s -> 4 | 0.8s -> 6 | 20.2s -> 28 | 1.8s -> 9 | - | 25.8s -> 34 | 25.8s -> 34 |
| lurcher | night | torch | 0.2s -> 2 | 0.2s -> 2 | 0.2s -> 4 | 0.5s -> 4 | 0.5s -> 6 | 0.5s -> 6 | 0.5s -> 7 | - | 1.0s -> 12 | 5.8s -> 16 |
| lurcher | night | cover | - | - | - | - | - | - | - | - | - | - |
| lurcher | night | log | 0.2s -> 4 | 0.8s -> 5 | 0.8s -> 7 | 1.3s -> 8 | 1.3s -> 9 | 24.5s -> 34 | 2.9s -> 12 | - | - | - |
* group (day): spotter 25 m facing the walking player; buddy 15 m behind it facing away: spotter 1.1s -> 7, buddy 1.1i -> 12
* group (night): spotter 25 m facing the walking player; buddy 15 m behind it facing away: spotter 1.1s -> 7, buddy 1.1i -> 10

## Left over

TD-194 (docs/TECH_DEBT.md): wanderers still spawn 70–120 m away in small groups and roam at
random (no pull toward the player short of the heat responses), and none are placed nearer in
cover. TD-193: the nav tiles carve a fallen log as a small square at its middle, so paths still
lead into long logs and the detour does the work. TD-195: the build-up, the detour and the night
wildlife are measured on the flat floor and in pure functions only, not felt in the world on a
real GPU; the detour is a local slide (a U-shaped pocket of logs can still hold a body until the
stuck jitter moves it).
