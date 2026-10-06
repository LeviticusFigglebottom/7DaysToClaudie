# ADR-0033: Weather you can see: rain, wet ground, storms, ground fog and snow

**Status**: Accepted · 2026-10

## Context
DESIGN §12 asks for "dramatic day/night and weather". The weather model has had six states since
the slice, but every one of them showed up only as fog density, cloud cover and a global wetness
tint (TD-018):
* **Rain** had no streaks, splashes or ripples. A rainy street read as an overcast one. Wetness
  darkened everything by the same factor, so a soaked brick wall looked like a dry one, while
  `bark` dropped to roughness 0.15 and turned trunks into lacquered plastic under a torch.
* **No puddles.** Wet ground never held standing water, not even on asphalt or in ruts.
* **Storms** had no lightning and no thunder. Wind gusts swung over game minutes (about 80 real
  seconds a beat), far too slowly to read as gusts.
* **Mist** was one uniform depth fog plus froxel fog at every height. From the valley rim at dawn
  the whole view was a brown soup: no valley floor, no ridges, no pooling.
* **Snow** settled as a flat white sheet with no relief. Nothing fell from the sky.
* **The shots couldn't show any of it.** The screenshot clock stands still, so a "rain" shot
  always rendered dry ground.

## Decision
### State: what the weather leaves behind (WeatherState, data/config/weather.json)
* **Wetness** soaks in `wet_minutes` of full rain. It dries in `dry_minutes` of grey, still air,
  faster in sun (`daylight`, set by the environment) and wind.
* **Puddles** are a separate level (`hm_rain.y`). They only start once surfaces are soaked past
  `puddle_after`, then fill over `puddle_fill_minutes`. They outlast the rain by hours
  (`puddle_dry_minutes`). They are saved as `puddles`; old saves load dry, with no version bump.
* **Snow cover** keeps its rates (build, melt, winter melt, rain wash), now in data.
* **Each state gets four new fields:**
  * `lightning`: strikes per game hour;
  * `gust`: the swing depth;
  * `ground_fog`: how readily fog pools;
  * `haze`: grey depth fog in rain or snow.
* **Gusts.** `WeatherState.gust_at(t, depth)` gives gusts in real seconds as a pure function of
  the clock. They swell over a few seconds and lull for longer. `hm_wind.z` carries the gusting
  wind, so foliage bends and rain slants with it.

### Lightning and thunder (LightningModel, EnvironmentController)
* **Pure function of the world seed and the game clock.** Game time is cut into slots
  (`slot_minutes`). A slot holds a strike with chance rate × slot / 60, decided by a hash of the
  seed and the slot. The same world gives the same storm however the frames fall. Contiguous
  windows never count a strike twice or miss one, and a test steps uneven frames to check it.
* **A strike has:**
  * a moment inside its slot;
  * a bearing;
  * a distance, log-uniform over `distance_m` (most fall kilometres away);
  * 1–4 return strokes;
  * a seed for the bolt's shape.
* **The flash:**
  * Each stroke flashes in milliseconds and dies away over `flash_s`.
  * A hard-shadowed `DirectionalLight3D` lights the world from the cloud base over the strike.
    It has one orthogonal split, angular size 0, and is visible only during the flash. Near
    strikes light from high; far ones from the horizon.
  * The sky shader lights the cloud deck from inside, most of all over the strike, and draws the
    bolt within `bolt_within_m`: a jagged channel from the cloud base to the horizon on its
    bearing, with a glow and a fork.
  * Ambient light, the depth fog and the published sky colours (`hm_sky_*`, which water and wet
    ground mirror) flash with it.
  * A sleep or a load (a clock step over 2 minutes) flashes nothing.
* **Thunder** arrives `distance / speed_of_sound` real seconds later: `amb/thunder_near` within
  `thunder_near_m`, otherwise `amb/thunder_far`. It gets quieter with distance and 8 dB quieter
  indoors.
* **The thunder is built from the channel** (`audio/sounds/weather.py`):
  * A tortuous channel is a random walk of 12 m segments from about 2 km up down to the ground.
  * Each segment fires an N-wave. Its sound arrives when its own distance allows, so a channel
    kilometres long arrives as a roll lasting seconds: the nearest kink first, as the crack of a
    close strike.
  * Segments broadside to the line of sight clap loudest.
  * Air absorption by distance leaves far thunder a low rumble, which the valley echoes.

### Rain, snow and drips round the camera (WeatherFx, precipitation*.gdshader)
* **GPU particles with their own process shader.**
  * Drops and flakes spawn in a column box round the camera (`box`) and fall with the wind and
    its gusts.
  * The box wraps round the camera, so wind never empties one side.
  * The emitters stay at the world origin and the column follows the camera through a `focus`
    uniform, with the culling box moved to match. So the particles are in world space whichever
    space the engine draws them in, and they don't slide when the camera moves.
  * Counts depend on the graphics preset: 4,000 to 16,000 drops and 4,000 to 15,000 flakes, in a
    column 26 m across. A narrow, dense column reads as rain where a wide, sparse one did not; the
    rain haze carries it beyond. `amount_ratio` follows the rainfall without restarting the
    system.
* **Rain stops where it lands.** The **weather map** (below) holds the height where rain lands
  under each cell: the roof, the ground or the water surface. So no rain falls indoors, under a
  porch roof or under a bridge.
* **A landed drop turns into a splash on the spot** for a fifth of a second (the `fx_splash`
  flipbook): on roofs, roads and lakes. Snow settles and fades.
* **How a drop is drawn** (`precipitation_draw`):
  * A streak along its motion, facing the camera.
  * Never thinner than about a pixel: a wider streak is fainter by the same factor, so far rain
    keeps its weight without shimmering.
  * Streaks are lit, with backlight, so they glow round lamps and torches and flare in
    lightning. By day they mirror the sky's brightness: lighter than a wall or the road behind
    them, fading into the sky itself.
  * NaN-proof. The profile is clamped (a UV a hair outside 0..1 on a one-pixel streak's edge made
    `pow()` return NaN) and an inactive particle's zeroed transform collapses instead of making NaN
    vertices. The glow had blown each stray NaN pixel up into a white disc with a black centre.
* **How a flake is drawn:** a soft disc facing the camera, tumbling as it falls. Only up close (10
  to 22 pixels across) does the generated crystal atlas (`fx_snowflakes`) take over: a crystal's
  thin arms average away in the mips of a flake a few pixels across, which had left falling snow
  invisible.
* **Eave drips:**
  * The map finds roof edges standing `min_drop_m` over open ground. Up to 256 points within
    22 m go to a third particle system.
  * Drips swell on the eave, fall under gravity and splash below.
  * The drip rate follows wetness and lags the rain, so roofs keep dripping as they drain.
* **Dust motes** hang in the air indoors by day (`PoiManager.is_indoors`). They are lit and
  backlit, so they show only where a shaft of light crosses them.

### The weather map (WeatherMaps; globals hm_weather_map, hm_weather_rect)
* An RGBA half-float texture of 128 × 128 cells of 1.5 m round the camera. Its heights are
  relative to a base (`hm_weather_rect.w`), so half floats keep centimetres. It is rebuilt when
  the camera moves 16 m from its centre.
* **Channels:**
  * **R**: where rain lands. Downward rays over the inner 48 × 48 cells hit the world, structures
    and props (not vegetation), 192 rays a frame. Beyond those cells it is the ground or water.
  * **G**: the ground.
  * **B**: the ground smoothed over 9 m.
  * **A**: the water surface.
* Heights and blurring run on a worker thread (`height_at` and `water_level_at` only read data).
  Rays run on the main thread. A map is published only once complete.
* **Readers:**
  * the particles (where rain lands);
  * the terrain (puddles where G lies below B; no rain under roofs);
  * std_surface and kit_wall (dry under roofs);
  * the ground fog (low ground and water).

### Wet world (weather.gdshaderinc; shared hunks)
* **The porosity model** (after Lagarde):
  * A porous surface first drinks the water and darkens, with little change in gloss.
  * Only once it is soaked does a glossy film sit on it.
  * A sealed surface barely darkens and glosses at once.
  * Wet albedo is a little more saturated.
* **Terrain:**
  * Porosity and puddle-holding come per layer from config `surfaces`. They are published as two
    mat4 globals indexed by layer slice: asphalt and mud hold water; litter and sand drink it.
  * Water stands where a fill rank beats the water level. The rank combines the hollow from the
    map, the layer's own relief (texture height) and noise that breaks the sheet into pools.
  * A damp, darker margin rings each pool.
  * A pool is dark (the ground seen through water), a flat mirror (roughness 0.015) and ringed by
    ripples while it rains. SSR is not needed: the sky radiance and every light's specular show
    in it.
  * Nothing gets wet under a roof.
* **Ripples** (`wx_ripples`): rings spreading from random points in two layers of cells, about
  once a second per cell in heavy rain. They need one hash per cell and layer. They are used on
  puddles and on lakes and rivers (`water.gdshader`, driven by rainfall now, not by wetness).
* **std_surface:**
  * Porosity is derived from the dry roughness and metalness (wood, concrete and cloth soak;
    paint and metal gloss).
  * What faces up under a roof stays dry; walls still take driven rain.
  * Snow breaks up at its edge with drifts and with the surface's creases (AO).
* **kit_wall:** exterior finishes take driven rain and darken by their porosity. Floors open to
  the sky soak like the ground. Before this, only floors lost a little roughness.
* **bark:**
  * Soaks dark, more on the side facing into the wind and in the furrows.
  * Keeps a satin sheen: its roughness floor is 0.3.
* **foliage:**
  * Wet leaves darken a little under their film.
  * Snow rides the fronds' upper faces in clumps and dims their translucency.

### Fog and atmosphere (EnvironmentController, ground_fog.gdshader)
* **Ground fog** has a strength from the clock (`ground_fog_at`):
  * it gathers at dusk to `dusk_strength`;
  * it deepens through the night and peaks at sunrise;
  * it burns off by `dawn[1]` hours after.

  This is multiplied by the weather's `ground_fog` (mist 1.8; rain and storm stir it away) and by
  the calm (it fades above `calm_wind`).
* **Near the camera, a FogVolume** (High and up) fills in below the local fog level:
  * the level is the low ground at about 25 m scale (the map's B, read at mip 4) plus `depth_m`,
    raised over water to the surface plus `water_depth_m`;
  * it is torn into banks by drifting 3-D noise;
  * sun shafts through it are boosted at a low sun (`god_rays`), the canopy's god rays in mist.
* **Further off**, the depth fog's height falloff works under the same level: it fills the valley
  seen from above.
  * Standing in the fog, the falloff stays below your feet and the volume carries the fog round
    you.
  * Mist's uniform densities drop (depth 0.006 → 0.0012, froxel 0.035 → 0.004), so mist now lies
    in the valley instead of filling the sky. A misty state (`ground_fog` over 1) keeps a thinner
    bank in the low ground all day.
* **Rain haze:** each state's `haze` adds grey depth fog, and the fog colour turns from blue
  distance to grey water in the air.

### Shots
The screenshot runner gets six weather shots (`wx_*`):
* rain on Pell's Crossing's street;
* a storm in the forest at night lit by a strike;
* misty dawn over the valley;
* the town under snow;
* a puddled road after rain;
* into the low sun through the wood on a misty morning (ground fog and the canopy's god rays).

Shot keys `wet`, `puddles` and `snow_cover` set what the weather has left (the clock stands still
between shots). `strike` holds a strike's flash for the capture, because software frames take
longer than a flash (`EnvironmentController.flash_hold`). Weather shots also freeze the rain and
snow for the capture (`WeatherFx.hold_still`). A software frame takes so long that a moving drop
never covers the same pixels twice, and temporal AA averaged every streak away. They also wait (up
to three minutes) until the weather map is the one round the camera (`WeatherMaps.covers`): after
the jump to a shot it is rebuilt by a worker queued behind the streaming and some frames of rays,
and the first renders captured the previous shot's map, with rain landing and puddles collecting
by another place's heights. `--stream-wait` caps the runner's wait for vegetation (240 s by
default) when the render lock is busy.

## Consequences
+ Rain reads in daylight and at night, and stays out of buildings.
+ Ground holds water where it would, and wet materials differ.
+ Storms flash and roll.
+ Mist lies in the valley.
+ Snow falls and drifts.
+ Every number is in `data/config/weather.json` or the state defs. The tests cover wetness and
  drying, puddles, snow, gusts, lightning determinism, frame-rate independence, the flash and
  thunder delay, ground fog by hour, the map's hollows and eaves, and a map that is published
  round the camera and kept in place until the next one is complete.
− Five more shader globals: `hm_rain`, `hm_weather_map`, `hm_weather_rect` and two mat4 tables.
  The surface shaders gain about one texture fetch per fragment where it rains or snows. The
  terrain gains two more (the map, twice) where puddles stand. The fog volume costs a 3-D noise
  per froxel at dawn and dusk.
− The weather map is 1.5 m cells, so rain stops a cell short of a roof edge. Eaves step on that
  grid, and a thin roof (a lean-to's poles) can miss a ray.
− The splash particles move as a fixed 30 fps simulation capped at 0.1 s a frame, so on very slow
  frames rain falls in slow motion.
− Temporal AA softens fast, thin streaks. They read at game frame rates because a drop moves along
  its own streak, but a streak's ends fade, and the QA captures must freeze the rain.
− Thunder plays in 2D: it has no direction (TD-091).
− Left for later: decals ignore the weather (TD-090), lightning strikes nothing (TD-091), the
  map's resolution and puddles off the terrain (TD-092), snow depth and flakes beyond the column
  (TD-093).
