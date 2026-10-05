extends GutTest
## ADR-0024: a "keep_water" pad (a boathouse slip, a dock over a lake) sits a freeboard above the
## water it overlaps and grades only the dry ground; the lake keeps its bed under the pad. Composed
## on a small synthetic flat region with a fixed-level lake and one POI placement over its shore.

const LEVEL: float = -1.0


func _world(keep_water: bool) -> WorldDef:
	var w := WorldDef.new()
	w.id = "keep_water_test"
	w.cols = 1
	w.rows = 1
	w.region_size = 256.0
	w.macro_noise_cfg = {"amplitude": 0.0, "ridged_amplitude": 0.0}
	w.regions = {"t": {"id": "t", "cell": "A1"}}
	w.cells = {"A1": "t"}
	var c: Vector2 = w.region_rect("t").get_center()
	var pad := {"type": "poi", "id": "kw_pad", "poi": "larch_pond_boathouse", "origin": [c.x - 20.0, c.y - 10.0],
		"rotation": 0, "size": [24, 20], "skirt": 6, "biome": "town"}
	if keep_water:
		pad["keep_water"] = true
		pad["freeboard"] = 0.6
	w._region_cache["t"] = {"default_biome": "meadow", "detail_noise": {"layers": [{"amplitude": 0.0}]},
		"features": [{"type": "lake", "id": "kw_lake", "ellipse": [c.x + 20.0, c.y, 30.0, 30.0, 0.0], "level": LEVEL,
			"depth": 3.0, "shore": 8.0, "irregularity": 0.0}, pad]}
	return w


func _pad_y(rt: RegionTerrain) -> float:
	for p: Dictionary in rt.placements:
		if str(p["id"]) == "kw_pad":
			return float((p["origin"] as Array)[1])
	return NAN


func test_keep_water_pad_sits_a_freeboard_over_the_lake_and_keeps_its_bed() -> void:
	var w: WorldDef = _world(true)
	var c: Vector2 = w.region_rect("t").get_center()
	var rt: RegionTerrain = TerrainComposer.compose(w, "t", 2.0)
	assert_not_null(rt)
	var pad_y: float = _pad_y(rt)
	assert_almost_eq(pad_y, LEVEL + 0.6, 1e-3, "the pad's height is the water's plus the freeboard")
	# Dry ground well inside the pad is graded to it...
	assert_almost_eq(rt.height.sample(c.x - 18.0, c.y), pad_y, 0.02, "dry ground flattened to the pad")
	# ...and the lake under the pad keeps its bed (the slip stays water).
	assert_lt(rt.height.sample(c.x + 2.0, c.y), LEVEL - 0.3, "the lake bed under the pad is not filled")


func test_an_ordinary_pad_over_the_same_shore_fills_the_water() -> void:
	var w: WorldDef = _world(false)
	var c: Vector2 = w.region_rect("t").get_center()
	var rt: RegionTerrain = TerrainComposer.compose(w, "t", 2.0)
	var pad_y: float = _pad_y(rt)
	assert_almost_eq(rt.height.sample(c.x + 2.0, c.y), pad_y, 0.02, "without keep_water the bed is graded to the pad")
