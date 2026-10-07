# ADR-0050: Interior light: probe fill that reaches the walls, a night share, indoor exposure

**Status**: Accepted · 2026-10

## Context
Player report 3 (Windows, RX 9070 XT, Build #67): a block-walled room was near black even by day,
apart from the bright doorway. In the screenshot (`docs/playtest/2026-10-06_build67_axe_dark_room.webp`)
77% of the pixels are below luma 16 and the median is 3. The table and the player's hands, in the
middle of the room, were lit; the walls, the corners and the wall-floor joins were black.

Interior light came from three places:
* **SDFGI** (high and ultra) occludes the sky indoors. A closed room gets almost no bounce from a
  door or two windows, so under SDFGI its ambient is near black.
* **Interior reflection probes** (PoiBuilder, one per rectangle of rooms; ADR-0021, TD-044). Each
  has `AMBIENT_COLOR`, which *replaces* the ambient inside its box. EnvironmentController set the
  fill to 0.55 by day and 0 at night.
* **Burning props** (ADR-0023): candles and lanterns of 0.35–0.55 energy, a few metres' reach.

The probes were meant to light the room, and they did, but not at the walls. Godot 4.7.2
(`scene_forward_lights_inc.glsl`, `reflection_process`) fades a probe in from each face of its box
over `blend_distance`, as `((1 - d / blend) per axis)^2`. Probes overlapping the same point don't
add up: each one only fills what is left (`max(0, blend - accumulated)`). The boxes stopped 5 cm past
the walls' centre lines, and walls are 0.16 m thick. So a wall's inner face was 3 cm inside its
box. With a 0.3 m blend that face got `(1 - 0.27 / 0.3)^2 ≈ 1%` of the room's fill and 99% SDFGI,
which is black. A floor (0.2 m deep in its box) got 44%. A corner, the product of two faces, got
nothing. Where two boxes of one room met, with no wall between them, the floor showed a dark band.
The probe budget, exposure and preset settings weren't the cause. They only decided how black the
SDFGI part looked.

## Decision
* **Boxes reach the wall faces.** `PROBE_BLEND` is 0.12 m. On a side that looks outside, a box
  reaches `PROBE_REACH_OUT` = 0.07 m past the wall's centre line: 1 cm short of the outer face,
  which keeps facades in the outdoor light. That puts the inner face 0.15 m deep, past the blend
  band. On a side where every cell beyond is built, on every level the box spans, the box reaches
  `PROBE_REACH_IN` = 0.14 m. Two boxes of one room, or two rooms across a partition, overlap far
  enough that each fills the seam fully. Floors and ceilings were already 0.2 m deep. The probe
  count is unchanged, so the 64-slot atlas and the budget (TD-044) are untouched.
  `test_interior_light` checks every room face of every POI for full fill.
* **The fill is data** (`data/config/interior_light.json`), applied by EnvironmentController to
  every live probe:
  * By day, `day_fill` of `day_color`, dimmed by `overcast_dim` under full cloud.
  * At night, `night_share` of the outdoor night's ambient energy, in its colour (the moon's blue,
    the Hum's green), never below `night_floor`. The old code set it to 0, a pure black. With the
    blend fixed, the probe would otherwise hold every wall at exactly 0, darker than the SDFGI it
    replaced.
  * A lightning flash adds `flash_share` of its fill: a storm lights the room through its windows.
* **Indoor exposure.** While the camera is inside a live probe's box, the tonemap exposure opens
  by `exposure_day` (1.3) by day and `exposure_night` (1.1) at night, eased over `adapt_seconds`.
  The room reads and the doorway blooms a little, as an eye adapts. There is no auto-exposure:
  this is one predictable multiplier, the same on every preset.
* `poi_preview --game-env HOUR` lights a preview with the game's EnvironmentController (SDFGI by
  `HOLLOWMERE_GFX`), so interior shots measure what the game shows.

## Consequences
* Rooms get the same flat fill on every preset: SDFGI's indoor result is replaced inside the probe
  boxes, as it already was at room centres. Light from windows and doors still adds directly
  (sun, sky through openings, volumetric shafts on medium and up). Bounce from a sunlit patch of
  floor doesn't add (TD-226).
* A room whose probe is parked (beyond the nearest 32–48) or hasn't rendered yet still falls back
  to SDFGI's black. The budget renders the room you're in first (TD-044).
* Probe boxes now poke 7 cm into outside walls and 14 cm into neighbouring rooms. Any box test
  that assumed the old inset changes with them (none did).
* The night share makes a dark room just readable as shapes. Seeing in it still takes a light:
  a lighter, a torch, or a lantern a building's story keeps burning.
