# Spit and charge clips (TD-027)

Contact sheets (`char_sheet.gd`, the GLB loaded at runtime, so flat colours, not the game's materials), side view, six frames each:

* `blister_spit_vs_scream.webp`: top row is the new `spit` (rear back, thrust the head out with the jaw wide on the release beat at 0.55 s, fold over retching, settle); bottom row is the `scream` it used before.
* `rammer_charge_vs_run.webp`: top row is the new `charge` (bent low behind the yoke, head down, shoulders forward, elbows out, short pumping arms; the run's gait underneath); bottom row is the `run` it used before.

## Crowd separation in a real Hum (TD-011)

`hum_watch.gd` (a Hum of 78 in Pell's Crossing, 40 alive at most, the player in god mode in the street; Vulkan fell back to OpenGL under xvfb), headings and close pairs measured over 16 frames, 8 s of play, for the Hum's bodies within 30 m:

| run | separation | jitter (degrees a tick) | pairs within 0.5 m |
|---|---|---|---|
| watch from 6 near | on, stepped push | 2.80 | 0.11 % |
| watch from 6 near | on, eased push | 2.47 | 0.02 % |
| watch from 6 near | off | 1.96 | 0 % |
| watch from 20 near | on, eased push | 2.69 | 0.07 % |
| watch from 20 near | off | 1.77 | 0.03 % |

It costs ~4% of the bodies' step and doesn't help here, so `Crowd.enabled` is off by default. `hum_watch_crowd_vs_none.webp`: frames 0, 7 and 15 with it on (top row) and off (bottom row). The overhead view is tight, so most of the 39 bodies within 30 m are out of frame.

Under the OpenGL renderer the world floods the log with "Too many instances using shader instance variables" (4096 at most): `rendering/limits/global_shader_variables/buffer_size` would need raising for Compatibility.
