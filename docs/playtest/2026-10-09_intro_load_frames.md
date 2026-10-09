# The intro during the load: frame times (ADR-0064)

The owner's condition (report 4, item 2): the intro may play while the world loads only if it
doesn't lag or freeze.

Measured with `intro_load_probe.gd`, a new survival game on run seed 4471, headless, in a 4-core
container. A headless frame's time is its main-thread work, which is exactly what the load's steps
cost. Rendering adds GPU time on top, which the gate doesn't change.

"Moving" frames are those where an intro card is fading or being typed. A long frame there would
show as a stutter. On a still card (one holding, fully shown) a long frame is invisible.

## Main map (Larch Hollow)

| Run | World ready | Control | Load frames | Worst load frame | Load frames > 50 ms | Moving frames | Worst moving frame | Moving frames > 50 ms |
|---|---|---|---|---|---|---|---|---|
| No intro | 45.7 s | 45.7 s | 6153 | 2608 ms | 5 | — | — | — |
| Intro, run 1 | 46.1 s | 103.7 s | 6236 | 2545 ms | 4 | 9780 | 87 ms | 3 |
| Intro, run 2 | 45.4 s | 103.8 s | 6123 | 2633 ms | 4 | 9778 | 88 ms | 4 |

Run 2's moving frames over 50 ms:

| Frame | When | During |
|---|---|---|
| 87.5 ms | 4.9 s | card 0 typing, the worker half ("Laying the ground…") |
| 52.9 ms | 4.9 s | card 0 typing, the worker half ("Raising the far hills…") |
| 88.1 ms | 43.0 s | card 3 fading out, "Waking up… (Loose)": systems' first frames after the boot releases them |
| 51.4 ms | 54.8 s | card 4 fading out, the world already ready and paused |

RANDOM_WORLD_TABLE

## Reading it

* **No freeze shows.** Every multi-second frame of the load (2.5–2.6 s, the world-loaded hand-off
  and the biggest boot steps) lands on a still card. The gate (World's 7566162) holds main-thread
  steps while a card moves.
* **The world is ready just as soon** (45.4–46.1 s against 45.7 s). The worker half dominates the
  load, and the boot steps fit in the cards' holds.
* **What's left is four or fewer frames of 50–90 ms in about 100 s of moving cards.** That is a
  typewriter or a fade pausing for one to five display frames:
  * Two fall in the worker half, when the main thread is mostly idle (thread contention while the
    composer fills every core).
  * One falls on the systems' first frames after the boot releases them, which are not boot steps
    and so aren't gated.
  * None lasts long enough to read as a freeze.
* **The mode the gate picks.** It is not a switch: the intro always plays over the load, and the
  load's heavy steps always wait for its still moments.
  * On a slow machine the steps take longer, but they still land on still cards. The intro
    finishes on time, and whatever load is left continues behind the normal loading screen.
  * If the world is ready first, it waits, paused, under the intro.
  * So the "after the load" case happens by itself whenever the load outlasts the intro.
* **Rendered runs.** The ~2 s steps that load new models (TD-102) are boot steps, so they are
  gated too. A GPU run should confirm that the warm-up camera's first-frame shader compiles fall
  under the loading screen before the first card moves (World offered to gate it as well).

Next steps if a GPU run shows hitches in the moving frames:
* gate the systems' release frames (`_release_processing`) the same way (World's file);
* make the worker half yield a core to the main thread.
