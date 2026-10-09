# ADR-0059: Roads graded to the land, natural banks, towns that grow, and street networks

**Status**: Accepted · 2026-10 (round 4; generator VERSION 12, TerrainComposer VERSION 13)

## Context
Player report 4 (the owner, 2026-10-08), items 4 and 5:
* roads tilted sideways on cross-slopes;
* long slanted faces of rock and road: the cut and fill beside roads and town pads stretched into
  long uniform planes;
* the ground round towns obvious: little grass or plants and no trees at all, so a town read as a
  cleared patch in the forest;
* towns too small and too linear: often one straight stretch of road.

Measured first (`src/tools/cli/terrain_audit.gd`: per region and in all, the cross-slope over each
road's paved width, the grade along it in 8 m steps, the banks beside it out to 12 m, how far a steep
bank runs unbroken, and the steepest 2 m step round each town lot; `--shade DIR` writes low-sun
hillshades, `--line` prints a height profile, `--probe` the ground across a road):
* **The worst of it was not the road pass.** A generated world's road profiles (and its streets and
  lot heights) come from the reference ground, the macro grid plus the world noise. The composer
  then caps the ground round every lake (160 m, rising 0.2 per metre) and river (its valley width,
  0.16) with a cone; the reference ground had no cap. On a hilly seed a road along a lake shore stood
  on a 60 m dyke over the capped ground (bank heights p95 38.7 m, a grade of 3.4 where it fell off
  the dyke's end), and lots near water sat on plinths.
* Every road's terrain blend was a fixed 8 m smoothstep from the shoulder: whatever the height
  difference, one uniform plane as long as the road (face runs up to 600 m on hilly seeds).
* Profiles were the ground smoothed over 36 m with no cap on the grade: 10-18% of road stations on
  hilly seeds steeper than 12%.
* The cross-slope over the paved width was already level (p95 under 2%): the corridor is flattened to
  one height per arc length. What reads as a tilted road is the 8 m planar bank beside it and, past
  150 m, the 2 m and 4 m terrain LODs folding a narrow bench into its bank.
* Towns: the biome map turned a town's whole disc and 90 m round it to meadow; a yard kept plants
  only in a 2 m rim of its frame (the composer cannot know which house a run stands there); the yard
  biome was grass only. Pell's Crossing on the main map is one flat framework pad with no
  vegetation at all and 10 m planar ramps round it.

## Decision

### 1. Valley caps in the macro grid (generator VERSION 12)
`RwgTerrain._valley_caps` cuts the composer's cap (`_band_water`'s formula, noise-free, from exact
distances: the nearest water body's level + 0.5 m + its valley slope per metre, eased off between
0.55 and 1 of its valley width) into the 32 m macro grid after the rivers are traced. Roads, town
streets, lot heights and the town planner's ground all read that grid, so they grade from the land
the composer makes; the composer's own cap finds the ground already under it.

### 2. Roads (TerrainComposer VERSION 13, generated worlds: `road_grade == "world"`)
* **Grade cap**: after smoothing, a world road's profile keeps under `ROAD_MAX_GRADE` by surface
  (asphalt 12%, gravel 14%, dirt 16%): the mean of the lowest profile over the ground and the highest
  under it whose grades keep under the cap (each is Lipschitz, so their mean is), so cut and fill
  balance, and where the land is gentler the profile is the land. Bridges are lifted after.
* **Banks**: the corridor (half width + shoulder) stays level at the profile; past a flat verge of
  0.8-2.8 m the ground is pulled only as far as it stands steeper than the bank's slope: cut 0.6-1.6,
  fill 0.45-0.8 (rise over run), varied along the road by a value noise 23 m across. A bank under a
  metre eases towards 0.3, full slope from 6 m (`BANK_LOW`), so a road a metre off the land blends
  in instead of standing on a curb. The crest and toe round off (a smooth minimum, 1.5 m), the face
  gets ±0.35 m of relief (6.5 m across) only where the bank moved the land, and the bank fades out
  between 19.5 and 26 m past the shoulder. Steep cuts take the rocky_slope biome by the existing
  slope rule (over ~34°), so a tall cut reads as rock. The road fields reach 28 m past the shoulder
  for these roads (10 m before).
* The value noise is an integer hash with bilinear smoothing, inlined in `_band_roads` (no calls in a
  band's loop, ADR-0038).
* **The main map too** (the owner plays it most): every road keeps the grade cap and meets the land
  in the same banks; a region's own roads still fade out at its border. Larch Hollow (1 m): road
  stations tilted over 4% 3.8% -> 3.1% (the rest are roads entering pads), grade p95 17.6% -> 14.1%.

### 3. Pads (VERSION 13, every world)
A lot's frame (`LOT_BANK` 0.4-0.75, out to 14 m, giving way to the streets as before) and a
framework's or POI's pad (out to `PAD_BANK_REACH` 18 m, or its skirt when longer; border-faded as
before) meet the land in the same kind of bank instead of a 5 m or 10 m smoothstep ramp. Pads that
keep their water (a boathouse's slip) keep the old skirt.

### 4. Town edges
* **Biome map** (generator VERSION 12): only a town's core (half to 1.1 of its core radius) turns
  meadow; between the core and the radius second-growth birch gains (`town_edge`), and past the lots
  the world's own forest comes up to the yards.
* **Yards** (VERSION 13): a lot's yard keeps its vegetation over its whole frame (`YARD_VEG` 0.85),
  and the `yard` biome grows long grass, yarrow, fireweed, huckleberry, fir saplings, a few paper
  birch and the odd grey fir. A v1 framework's pad (Pell's Crossing) keeps `FRAMEWORK_VEG` 0.75 of the
  `town` biome's overgrown lots.
* **The house clears its own ground at runtime.** VegetationManager builds `_footprints` once from the
  PoiRegistry: every town lot's building box (an authored building's footprint; a generated one's
  `BuildingGenerator.plan_box`, the first draws of its seed, shared with `_make` through `_lay_out`),
  as world-to-local transforms by 64 m chunk. A scattered instance on the box (trees 1.6 m round it,
  brush 0.8 m, ground cover 0.25 m) or in the strip in front of it out to the street (trees and
  brush, 12 m: the walk stays clear) is hidden by index like a runtime clearing (ADR-0054), so the
  scatter keeps its indices and saves their meaning; the far tree layer skips them too. A house the
  validator sent to a retry (rare: the test asks for 90% agreement) may stand a little off its
  predicted box.

### 5. Bigger towns and street networks (generator VERSION 12)
* **Bigger classes** (`town_planner.json`): hamlets 14-26 lots, villages 50-110, towns 110-260, wider
  radii; a mixed world leans to villages and towns. A class with no room on the land retries one
  class smaller once the others are placed; town discs keep 180 m apart (300) with a disc relief of
  60 m (45); a trader post that finds no room where the roads leave town looks along highways,
  county roads and tracks out to 900 m.
* **A network, not a comb** (ADR-0040 §2 and §4 have the detail): the reasons streets ended were
  counted (`stats.why`): seeds dropped near junctions, side streets running out their length without
  meeting another, and the loop cap forcing every later street 30 m off the others. Now every side
  street, branch and cross street is walked one block depth at a time (78-88 m behind core shops,
  66-76 m inner, 76-90 m outer), and at each stop a cross street reaches for the next street over
  (55-220 m, met at 35 degrees or more) and joins it at a T, past the loop cap; growth runs in rounds
  (first-generation side streets, cross streets, branches, cross streets again, forced branches);
  a seed near a junction slides up to 15 m instead of being dropped; side streets are seeded only to
  ~0.65 of the radius along the main road, so towns grow across it rather than along it.
  Synthetic land, seeds 1-3: blocks per village 3.5 -> 9.3, per town 8.5 -> 30.5; a hamlet is a
  crossroads or a small loop. A big town plans in 0.47-0.66 s headless (0.24-0.42 before).
* **Caves** (ADR-0056 WS-E) are a stage of their own after everything else (forest grottos and
  shelters per region from `tuning.caves`), so no other place moves.

### 5a. Where two roads meet (VERSION 13)
Where a 4 m cell's corners belong to different roads, the road pass and a lot's give-way used to take
the nearest corner's distance and arc, constant over the cell. With banks reaching 26 m that drew
stair steps along a town's streets. The distance to the nearest road is continuous across the line
where two roads' cells meet, so it stays bilinear; the arc is interpolated over the chosen road's own
corners. Hilly seed 21: road stations tilted over 4% went 1.3% -> 0.2%.

### 6. Saves
`SaveSystem.fix_composer_changes` (TD-182): a run crossing composer 13 drops its felled-tree and
harvested-plant records in the 64 m chunks whose scatter moved: within 40 m of a generated world's
road, within 30 m past any pad that does not keep its water, and over every organic town. The trees
there simply stand again. A random run keeps its own world folder (generator 11 land), so only the
composer's side applies to it.

### Yards meet their streets, streets meet each other (TD-318, composer 14, generator 14)
A lot stood at the mean of the reference ground over its frame and its street at the street's own
smoothed, grade-capped profile; on hills the yard met the street in a lip of a metre or more. Now
`TerrainComposer.town_street_profiles` profiles a world town's streets together, after the world
roads through or by it (`town_world_roads`, within 60 m of its disc), which are profiled first and
never moved: a street that meets an earlier one (a tee or a crossing, within 3 m) is pinned to its
height there, eased over 32 m. The generator reads the same profiles and keeps each lot within
`LOT_STREET_STEP` (0.3 m) of its street where the lot meets it; the difference with the ground goes
to the back of the lot. The composer and the generator call the same static code on the same
reference ground, so the lot, its pad and its building agree. Random-world saves drop the
vegetation records of their town chunks on the way to composer 14. The main map is unchanged
(its streets are graded per region).

Measured (terrain_audit, hilly seeds 21 and 7, size 4): the steepest 1 m step between a yard and
its street, p95 1.01 → 0.44 m and 0.81 → 0.30 m (max 1.53 → 0.80 and 0.95 → 0.56). On the
carriageways within 10 m of where one road ends on another, p95 1.44 → 1.41 m and 0.92 → 0.84 m:
the town junctions that led that list before (1.25-1.29 m) are gone from its top; what is left
there is where two world roads meet (not pinned) and the edge of cul-de-sac bulbs, whose paved
circle drops off before its radius (TD-318 follow-ups).

### Roads meet roads and pads at one height (composer 15, generator 15)
The carriageway steps left (measured on the carriageways only, within 10 m of where one road ends
on another) were where two world roads met, at cul-de-sac bulbs, and above all where a road met a
pad: since VERSION 13 a pad's bank gives way to the roads, and a road graded on its own met a pad at
another height in a wall. Route 9 ran 3.7 m under Pell's Crossing's pad, 4 m off its edge, under the
storefronts facing it, and 1.9 m under the Timberline Motel's.
* **World roads** are profiled together in road order (`world_road_profiles`) and pinned to the
  earlier roads they meet; the generator reads the same profiles for the lots by them.
* **The nearest road is the nearest edge**: the road fields hold the distance to a road's edge, so a
  bulb keeps its whole circle where its narrow street ends in it, and the distance stays continuous
  where two roads of different widths meet. Readers add the road's half width back.
* **On a region-graded world** (the main map) the POI and framework pads are levelled before the
  roads are cut (`_pad_targets`; heights moved by at most 15 cm, Pell's 2 cm), a road whose centre
  line comes within 8 m of a pad is pinned to its level and eases back at 8% over 12-60 m
  (`_pin_to_pads`), and a road pins to the roads before it where they meet, over 32 m or half its
  length (`_pin_to_roads`), so a lane between the highway and a pad meets both.
* **On a world-graded world** (random worlds) a road that runs onto a pad ramps to it after the pads
  are levelled (`PAD_RAMP_*`); its spur still meets the pad in a step where the pad stands far from
  the road's grade (TD-320).

* **Where one road meets another** the reach is the other road's half width + 1.5 m (at least 3 m):
  an authored road starts at the edge of the road it leaves, not its centre line (the Waystation
  drive started 3.6 m off Route 9's and was never pinned).
* **Random worlds' places** are listed in world.json `pads`, levelled from the reference ground
  (`world_pad_height`) and the world roads pinned to them (TD-320).

Measured (carriageways within 10 m of where one road ends on another): main map p95 1.29 → 0.21 m,
max 1.98 → 0.23 m, cross slope p95 0.023 → 0.011; hilly seed 7 p95 0.92 → 0.24 m, max 1.72 →
0.55 m; seed 21 p95 1.44 → 0.49 m, max 2.75 → 2.15 m (a roadside diner levelled 2 m off its highway
10 m away, TD-320). Saves crossing composer 15 drop their vegetation records by the roads, as at 13.

### Roadside places at their road's level (composer 16, generator 16)

A random world's roadside place (a diner by the highway, a trader post) records the road point it
fronts (`level_at` in world.json `pads`); `world_pad_heights` sets its pad to that road's profile
height there + 0.1 m, held within `ROADSIDE_LEVEL` (3 m) of the pad's mean ground, before the roads
are pinned to the pads. Seed 21's worst carriageway step 2.15 → 1.16 m (p95 0.49 → 0.47 m); seed 7
unchanged (its 0.55 m is a trader drive beside a lot). Random-world saves crossing composer 16 drop
their bank-chunk records.

### The main map within its caps (composer 17)

Owner report 4's "roads on slants" and "long slanted faces", checked with terrain_audit over all 49
main-map regions (roads run through D6, D7 and E6; Pell's Crossing's west end is in C6). Cross-slope
was already level (max 3.9%) and no long planar faces stood anywhere. The grades did not hold:
* **Bridge ramps** (region-graded worlds): up to the deck at `BRIDGE_RAMP` (0.8) of the road's cap,
  as long as the lift needs; the fixed 40 m smoothstep climbed Route 9 east of the Tamsin bridge at
  20% (its cap is 12%).
* **Pad ramps** (region-graded worlds): within `PAD_PIN_REACH` of the pad at its level, then a cone at
  `PAD_RAMP_GRADE` per metre out, for the road's profile and the pad's ramp under it alike; the
  smoothstep, capped at 60 m, took Route 9 off Pell's Crossing's pad at 15%.
* **Pads that keep their water** are levelled before the roads (their water is known), so a road
  running onto one is pinned to it: the larch pond road met the boathouse at 17% (gravel cap 14%).
* **Bulbs**: a region-graded street is level over its last metres into its cul-de-sac's bulb.
* **Pell's Crossing's west end**: its lots (plan_main_town.gd's output, heights from the ground as it
  was) are refitted to within `LOT_STREET_STEP` of their own streets' composed heights
  (`terrain_audit --fit-lots`).

Random worlds keep composer 16's ramps: their places, levelled from world data, can stand 10 m off
their road, and on seed 21 the longer cones made long tall fills (bank height p95 6.4 -> 8.4 m, face
runs 250 -> 552 m) and ran past a junction (a 3.07 m step); with them kept, seed 21's audit is
identical to composer 16's.

Measured on the main map: grade max 20.1% -> 14.4% (Route 9 within 12% everywhere; the gravel
logging and pond roads at their 14% cap), stations over 12% 11.4% -> 7.4% (all on gravel); C6 yard
to street lips p95 0.75 -> 0.24 m (lot banks p95 2.6 -> 3.3 m, the yards held to their streets);
one face run, 56 m, the fill under Route 9's longer east bridge ramp. Saves crossing composer 17 drop
their vegetation records round bridges, pads and towns. Left: TD-323.

## Consequences
+ Measured on hilly seeds (size 4): bank heights p95 38.7 m → 6-7 m, the steepest 2 m step beside
  roads p95 1.57 → 0.85-0.9, grades capped (max 0.13-0.17 by surface, bridge ramps aside), face runs
  shorter and no longer uniform; lot banks steepest step p95 0.71 → 0.51.
+ Towns sit in the forest: birch and the world's trees come up to the yards, yards grow, houses keep
  their ground and their walks clear, from data the run already has.
− Bank shapes still come from one road at a time (the nearest), so where two roads with different
  profiles meet the junction is the nearest road's; the audit skips 14 m round junctions.
− A tall cut on a steep hillside that has not met the land by 26 m fades back over the last 6.5 m,
  steeper there.
− Grades over the cap on a long climb become cuts and fills of several metres; the 32 m router's
  `grade_max` (0.16) is unchanged, so a road may still climb a slope the cap then cuts into.
− Main-map road profiles are grade-capped too, so a road climbing steeper than its cap now runs in a
  cutting of a few metres (a Larch Hollow spur sits 2.4 m below its old line); saves drop the
  vegetation records beside it (§6).
+ Pell's Crossing grew a west end (TD-319): Mill Street West continues Mill Street from the pad's west
  edge round the north end of the Larkspur cliffs (left as they are) into C6, and 40 houses grew round
  it (`src/tools/cli/plan_main_town.gd`: the organic planner on the main map's own composed ground,
  every pad, road, path, cliff, cave and water a keep-out, 150 m off the drop marker; houses only, so
  the old core stays the centre). A world-level town on the main map (`world.json` towns,
  `pell_outskirts`). Boot, main map headless: 41.0-43.5 s before, 46.8-53.6 s with the houses made
  one after another on the loader thread, 42.6-43.4 s once WorldLoader made every lot's building on
  the worker pool at once.
