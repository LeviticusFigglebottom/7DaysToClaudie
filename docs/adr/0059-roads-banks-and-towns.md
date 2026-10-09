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
− Pell's Crossing itself is not bigger yet: its land is crowded (the drop site, Okafor's farm, the
  logging road, Larkspur's cliffs, the river). `src/tools/cli/plan_main_town.gd` plans an organic
  extension on the main map's own ground with all of that as keep-outs; a west end of 58 houses on
  the bluff was tried and is parked until Larkspur's cliff stops fading at the D6/C6 border (TD-319).
