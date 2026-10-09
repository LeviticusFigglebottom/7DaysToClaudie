# The intro during the load: frame times (ADR-0064)

The owner's condition (report 4, item 2): the intro may play while the world loads only if it
doesn't lag or freeze.

## How it was measured
`intro_load_probe.gd` started a new survival game on run seed 4471, headless, in a 4-core
container. A headless frame's time is its main-thread work, which is exactly what the load's steps
cost. Rendering adds GPU time on top, which the gate doesn't change.

"Moving" frames are those where an intro card is fading or being typed. A long frame there would
show as a stutter. On a still card (fully shown and holding) a long frame is invisible.

The "gated" rows apply World's gate (7566162, `GameWorld._load_may_step()` over
`GameUI.load_may_step()`). It was on World's branch, not yet on integration, so it was applied to
the working tree only for these runs. The ungated rows are this branch as committed.

## Main map (Larch Hollow)

| Run | World ready | Control | Worst load frame | Load frames > 50 ms | Moving frames | Worst moving frame | Moving frames > 50 ms |
|---|---|---|---|---|---|---|---|
| No intro | 45.7 s | 45.7 s | 2608 ms | 5 | — | — | — |
| Intro, ungated | 45.4 s | 103.8 s | 2633 ms | 4 | 9778 | 88 ms | 4 |
| **Intro, gated** | **47.6 s** | **94.2 s** | 2752 ms | 4 | 8424 | **38 ms** | **0** |

## Random world (seed 77, size 3, from its cache)

| Run | World ready | Control | Worst load frame | Load frames > 50 ms | Moving frames | Worst moving frame | Moving frames > 50 ms |
|---|---|---|---|---|---|---|---|
| No intro | 15.3 s | 15.3 s | 613 ms | 6 | — | — | — |
| Intro, ungated | 6.6 s | 92.3 s | 599 ms | 7 | 8371 | 280 ms | 4 |
| **Intro, gated** | **12.0 s** | **92.1 s** | 688 ms | 3 | 8423 | **38 ms** | **0** |

The ungated random world's 280 ms frame came as card 0 faded in, during the worker half
("Laying the ground…"). The other ungated slow frames were boot steps ("Waking up…", "Finding your
feet…") running under a moving card.

## Reading it

* **With the gate, nothing the eye could catch.** Not one frame over 50 ms lands on a moving card
  on either world, and the worst is 38 ms (a single dropped display frame at 60 Hz). Every
  multi-second load frame (up to 2.75 s on the main map) lands on a still card.
* **The load isn't slowed in a way that matters.**
  * The main map's world is ready 2 s later than without the intro (47.6 s against 45.7 s), well
    inside the intro.
  * The random world from cache is ready in 12 s against 15 s. These runs vary by a few seconds;
    the gate only ever delays a step, by at most one card's fade.
* **The mode the gate picks.** It is not a switch: the intro always plays over the load, and the
  load's heavy main-thread work always waits for its still moments.
  * On a slow machine the steps take longer, but they still land on still cards. The intro keeps
    its pace, and whatever load is left continues behind the loading screen after it.
  * If the world is ready first, it waits, paused, under the intro.
  * So "after the load" happens by itself whenever the load outlasts the intro.
* **The intro is about 90 s** at 55 characters a second. The world was ready long before it
  ended on both worlds. Holding Esc skips it.
* **Not covered by headless timing:** GPU shader compiles at the warm-up camera's first frames.
  World notes these fall under the loading screen before the first card moves, and offered to
  gate them too if a GPU run shows a hitch in the first second.

## Before this ships
Integration needs World's 7566162 (the gate). Without it the intro still plays and nothing breaks,
but the boot steps can stutter it: 280 ms at worst in these runs.

## Skipping (2026-10-09, after World's batch)

A player who holds Esc (or B) pays nothing for the intro. Skipping opens the gate the same frame
(`test_hud.gd`: `load_may_step()` turns true as `skip_intro()` returns). The rest of the load then
runs at full speed behind the loading screen. Main map, headless, the same container load for
both runs:

| Run | World ready |
|---|---|
| No intro | 55.4 s |
| Intro, skipped at 5 s (`--skip-at 5`) | 54.8 s |

Watched to the end, the intro stretches the main-thread half of the load under its cards: the
world was ready at 76 s of a ~92 s intro. That time is spent while the player watches.

## The wreck shot (2026-10-09)

`2026-10-09_intro_wreck_shot.webp`: the world card over the Lift 3 crash site, main map, 07:31 on
day 1. Rendered by `intro_load_probe.gd --shot-after-load` on lavapipe, 10 s into the card. The
camera flies 9 m up the cleared swath toward the nose (the card's `from`/`to` plan cells). This
container has no generated assets, so the fuselage and debris are procedural stand-ins. Earlier
orbiting cameras sat among the trunks round the clearing and rendered black.
