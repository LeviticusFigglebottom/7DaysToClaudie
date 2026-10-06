extends GutTest
## TerrainComposer VERSION 11 (ADR-0031): the ground crosses a lake's or river's water line on a
## slope. It used to step from the bank (0.22 m over the water) to the bed (0.35 m under) between two
## 1 m samples, so the water's edge followed the sample grid: a 1 m staircase seen from near the
## water. Composed on a small flat synthetic region with one round lake.

const LEVEL: float = -1.0
const RADIUS: float = 24.0


func _world() -> WorldDef:
	var w := WorldDef.new()
	w.id = "water_edge_test"
	w.cols = 1
	w.rows = 1
	w.region_size = 256.0
	w.macro_noise_cfg = {"amplitude": 0.0, "ridged_amplitude": 0.0}
	w.regions = {"t": {"id": "t", "cell": "A1"}}
	w.cells = {"A1": "t"}
	var c: Vector2 = w.region_rect("t").get_center()
	w._region_cache["t"] = {"default_biome": "meadow", "detail_noise": {"layers": [{"amplitude": 0.0}]},
		"features": [{"type": "lake", "id": "edge_lake", "ellipse": [c.x, c.y, RADIUS, RADIUS, 0.0], "level": LEVEL,
			"depth": 3.0, "shore": 8.0, "irregularity": 0.0}]}
	return w


## Walks from dry ground into the lake along a line (off the sample grid) and returns
## [crossing x, slope (m/m) where the ground passes under the water line], or [] if it never does.
func _crossing(rt: RegionTerrain, x0: float, x1: float, z: float) -> Array:
	var step: float = 0.05
	var prev: float = rt.height.sample(x0, z)
	var x: float = x0
	while x < x1:
		x += step
		var hgt: float = rt.height.sample(x, z)
		if prev >= LEVEL and hgt < LEVEL:
			return [x, (prev - hgt) / step]
		prev = hgt
	return []


func test_the_ground_crosses_the_water_line_on_a_slope_not_a_step() -> void:
	var w: WorldDef = _world()
	var c: Vector2 = w.region_rect("t").get_center()
	var rt: RegionTerrain = TerrainComposer.compose(w, "t", 1.0)
	assert_not_null(rt)
	# Three lines across the west shore, at different offsets from the 1 m sample rows.
	for dz: float in [0.13, 0.5, 7.71]:
		var hit: Array = _crossing(rt, c.x - RADIUS - 8.0, c.x - RADIUS + 6.0, c.y + dz)
		assert_false(hit.is_empty(), "the ground goes under the water line (dz %.2f)" % dz)
		if hit.is_empty():
			continue
		var edge_x: float = c.x - sqrt(RADIUS * RADIUS - dz * dz)
		assert_almost_eq(float(hit[0]), edge_x, 1.0, "the water's edge is where the lake's outline is (dz %.2f)" % dz)
		# A step between two samples crossed at ~0.7 m/m (0.57 m plus the bed); the slope is ~0.25.
		assert_lt(float(hit[1]), 0.45, "the ground meets the water on a slope (dz %.2f)" % dz)
