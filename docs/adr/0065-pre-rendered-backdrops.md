# ADR-0065: The menu's and the intro's backdrops are pictures rendered offline, never 3D drawn live

**Status**: Accepted · 2026-10 (round 4, hub)

## Context
The owner's first packaged round-4 build (Build #94) reached the main menu and then froze, or
crashed, as soon as an entry was hovered or clicked. They asked for this to be fixed and, if the
intro or the menu's panning camera was the cause, for both to work "like a pre-recorded yet
high-quality video": nothing should stutter, get in the way, or render at startup.

The menu's backdrop (ADR-0063) was the real D6 region built and drawn live in a SubViewport behind
the menu: the terrain composed at 4 m, its water, and some thousands of trees in LOD tiles, with sky
and fog. Before the menu's first frame was even quiet, it was:
* composing the region on a worker;
* building the scene on the main thread, a step a frame;
* drawing it every frame with MSAA and a two-split shadow.

Its cost guard (freeze below 40 fps) could only act after the scene had faded in and four seconds
had been measured. Running the exported Linux build on a software renderer reproduced a frozen
menu: the window stopped redrawing for minutes, and a hover never highlighted. On the owner's
machine the same work, and its first-use shader and pipeline costs, came just as they started to
use the menu.

The intro's world card (ADR-0064) also drew 3D live. It took over the loaded world's camera for the
wreck shot while the load's last steps ran.

## Decision
**Neither the menu nor the intro draws 3D at runtime.** Both show pictures rendered offline by the
asset pipeline.

* **`make stills`** (also run by `make bake`, so by `make assets` and CI) runs
  `src/tools/cli/stills.gd` under Xvfb. Each picture is drawn supersampled (4608×2592, MSAA 4×,
  four shadow splits) and saved at 3840×2160, sharp on a 4K screen (3200×1800 at first: soft at
  4K, Presentation's check). `tools/stills.sh` writes lossy, mipmapped import sidecars. Each shot is redrawn
  only when its stamp changes: a hash of the code, data, world, shaders and generated-asset hashes
  it is drawn from.
  * **The menu:** five stills of `MenuFlight` (the old live flight, moved to `src/tools/stills/`)
    along the Tamsin, the weather turning over between them (`STILL_MOODS`: dusk, a misty dawn, a
    rainstorm with frozen rain streaks). Each still grows the game's own undergrowth and ground
    cover in front of the lens (`VegetationScatter`'s medium and ground layers, further out than
    the game draws them: the render is offline).
  * **The intro:** `intro_wreck.png`. The world card's framing (`IntroPlayer.shot_pose`) is taken
    from the loaded main map at first light (`SHOT_HOUR`).
* **The menu (`MenuBackdrop`)** loads the stills on worker threads (`load_threaded_request`). It
  then drifts across them, one dissolving into the next: a slow zoom and a sideways drift whose
  direction alternates, always inside the zoom's margin. Options: moving, still (the first
  picture) or off. It costs two textured quads a frame.
* **The intro's world card** shows `intro_wreck.png`, loaded on a worker when the intro starts. It
  zooms in slowly by `SHOT_ZOOM`, as the live shot pushed in. While it moves, `is_calm()` is false,
  so no load step can stall it. Without the picture, the card is a caption on black.

### Why pictures and not a video
A video was the first choice and works: Godot's Movie Maker writes Ogg Theora, and the encoding
worked here. Filming does not. The pipeline renders on software Vulkan (lavapipe; CI has no GPU),
where one 2560×1440 frame of the valley took 32 s. A one-minute loop at 30 fps would take about
16 hours of CI per change, so a real camera move can't be filmed. A slow pan and dissolve over
well-rendered stills gives the same calm, cinematic backdrop, with no decoding cost and no
compression artefacts. The pictures can be replaced by a filmed video later if the pipeline gets a
GPU.

## Consequences
* The menu's first frame and every frame after it cost the same on every machine. Nothing is
  composed, built or compiled behind it.
* There is no motion parallax: the pan is 2D. The dissolve into and out of the dawn still is the same crossfade as between the dusks.
* The pictures need the generated assets. A source tree without `make assets` shows a plain menu
  and a caption on black for the world card.
* The five menu stills take about 2.5 minutes each on lavapipe (building D6, its buildings and each still's undergrowth, then about two minutes a picture). The wreck needs a full main-map load, so
  the first CI build after a world change spends 10-20 minutes more in `make bake`. A failed stills
  run doesn't fail the bake: the menu and the intro simply show no pictures.
