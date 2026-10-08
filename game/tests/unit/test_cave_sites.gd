extends GutTest
## CaveSites and CaveSet (ADR-0056): the mouth search (deterministic, uphill, nothing on flat
## ground), region-feature caves (parsed, bad ones skipped, seeded per world) and the set's grid
## queries.

const REGION: String = "t_region"

var _cfg: Dictionary = {}


func before_all() -> void:
	var j := JSON.new()
	assert_eq(j.parse(FileAccess.get_file_as_string("res://data/config/caves.json")), OK)
	_cfg = j.data


## A 26.6° plane rising towards +X.
static func _plane(x: float, _z: float) -> float:
	return 0.5 * x


static func _flat(_x: float, _z: float) -> float:
	return 12.0


## A steep cone hill (33°), 45 m high at (cx, cz).
static func _cone(x: float, z: float, cx: float, cz: float) -> float:
	return maxf(0.0, 45.0 - 0.65 * Vector2(x - cx, z - cz).length())


static func _hill(x: float, z: float) -> float:
	return _cone(x, z, 0.0, 0.0)


func test_shape_seed_is_stable_and_distinct() -> void:
	assert_eq(CaveSites.shape_seed("main_map", "larch_grotto"), CaveSites.shape_seed("main_map", "larch_grotto"))
	assert_ne(CaveSites.shape_seed("main_map", "larch_grotto"), CaveSites.shape_seed("main_map", "other"))
	assert_ne(CaveSites.shape_seed("main_map", "larch_grotto"), CaveSites.shape_seed("rwg_7", "larch_grotto"))


func test_settle_heads_uphill() -> void:
	var got: Dictionary = CaveSites.settle_mouth(_plane, Vector2(10, 5), NAN, 12.0, {})
	assert_false(got.is_empty())
	var yaw: float = deg_to_rad(float(got["heading_deg"]))
	var into := Vector2(-sin(yaw), -cos(yaw))
	assert_almost_eq(into.x, 1.0, 0.01, "into the hill is up the slope (+X)")
	assert_almost_eq(float(got["heading_deg"]), -90.0, 0.5)
	assert_almost_eq(float(got["slope_deg"]), rad_to_deg(atan(0.5)), 0.5)
	var p: Vector3 = got["pos"]
	assert_lte(Vector2(p.x, p.z).distance_to(Vector2(10, 5)), 12.0)
	assert_almost_eq(p.y, _plane(p.x, p.z), 0.001)
	# A declared heading is kept when the slope faces it, refused when it faces away.
	var hinted: Dictionary = CaveSites.settle_mouth(_plane, Vector2(10, 5), deg_to_rad(-70.0), 12.0, {})
	assert_almost_eq(float(hinted["heading_deg"]), -70.0, 0.01)
	assert_true(CaveSites.settle_mouth(_plane, Vector2(10, 5), deg_to_rad(90.0), 12.0, {}).is_empty())
	# Too gentle for the asked minimum.
	assert_true(CaveSites.settle_mouth(_plane, Vector2(10, 5), NAN, 12.0, {"min_slope_deg": 30.0}).is_empty())


func test_find_mouth_is_deterministic_and_uphill() -> void:
	var area := Rect2(-80, -80, 160, 160)
	var a: Dictionary = CaveSites.find_mouth(_hill, area, 42, {})
	assert_false(a.is_empty())
	assert_eq(a, CaveSites.find_mouth(_hill, area, 42, {}))
	var p: Vector3 = a["pos"]
	assert_true(area.has_point(Vector2(p.x, p.z)))
	assert_gte(float(a["slope_deg"]), 18.0)
	var yaw: float = deg_to_rad(float(a["heading_deg"]))
	var into := Vector2(-sin(yaw), -cos(yaw))
	assert_gt(into.dot(-Vector2(p.x, p.z).normalized()), 0.95, "heads towards the summit")
	assert_gt(_hill(p.x + into.x * 5.0, p.z + into.y * 5.0), p.y + 2.0)


func test_find_mouth_rejects_flat_ground() -> void:
	assert_true(CaveSites.find_mouth(_flat, Rect2(-100, -100, 200, 200), 1, {}).is_empty())
	assert_true(CaveSites.settle_mouth(_flat, Vector2.ZERO, NAN, 12.0, {}).is_empty())
	# Slope everywhere but the area is all margin.
	assert_true(CaveSites.find_mouth(_plane, Rect2(0, 0, 40, 40), 1, {"margin": 25.0}).is_empty())


func test_feature_spec_validates() -> void:
	var good: Dictionary = {"type": "cave", "id": "a", "style": "grotto", "mouth": [1, 2], "heading": "uphill", "search": 8, "length": [14, 18]}
	var spec: Dictionary = CaveSites.feature_spec(good, _cfg)
	assert_eq(spec["id"], "a")
	assert_eq(spec["mouth"], [1.0, 2.0])
	assert_eq(float(spec["search"]), 8.0)
	assert_false(CaveSites.feature_spec(good.merged({"heading": 45}, true), _cfg).is_empty(), "a yaw heading")
	for bad: Dictionary in [
			good.merged({"type": "hill"}, true), good.merged({"id": ""}, true), good.merged({"mouth": [1]}, true),
			good.merged({"mouth": "here"}, true), good.merged({"style": "cathedral"}, true), good.merged({"style": "_doc"}, true),
			good.merged({"heading": "downhill"}, true), good.merged({"length": [1]}, true), good.merged({"seed": "x"}, true)]:
		assert_true(CaveSites.feature_spec(bad, _cfg).is_empty(), str(bad))
	assert_true(CaveSites.feature_spec("cave", _cfg).is_empty())


## A 7x7 world whose region D6 (x -512..512, z 1536..2560) has a cone hill at (0, 2048).
func _world(features: Array) -> Array:
	var w := WorldDef.new()
	w.id = "test_world"
	w.regions = {REGION: {"cell": "D6"}}
	w._region_cache[REGION] = {"id": REGION, "features": features}
	var rt := RegionTerrain.new()
	rt.region_id = REGION
	rt.rect = w.region_rect(REGION)
	rt.spacing = 2.0
	rt.height = HeightField.create(rt.rect.position, 2.0, 513, 513)
	for iz: int in 513:
		for ix: int in 513:
			rt.height.set_h(ix, iz, _cone(rt.rect.position.x + ix * 2.0, rt.rect.position.y + iz * 2.0, 0.0, 2048.0))
	return [w, rt]


func test_from_region_parses_and_skips_bad_features() -> void:
	var feats: Array = [
		{"type": "hill", "pos": [0, 2048], "radius": 50, "height": 10},
		{"type": "cave", "id": "good", "style": "grotto", "mouth": [0, 2098], "heading": "uphill", "search": 12},
		{"type": "cave", "id": "seeded", "style": "shelter", "mouth": [50, 2048], "seed": 99},
		{"type": "cave", "id": "no_mouth", "style": "grotto"},
		{"type": "cave", "id": "bad_style", "style": "cathedral", "mouth": [0, 2000]},
		{"type": "cave", "style": "grotto", "mouth": [0, 2000]},
		{"type": "cave", "id": "meadow", "style": "grotto", "mouth": [300, 1700]},
		"not a feature",
	]
	var wr: Array = _world(feats)
	var caves: CaveSet = CaveSites.from_region(wr[0], REGION, wr[1], _cfg)
	assert_false(caves.is_empty())
	var ids: Array = caves.plans.map(func(p: CavePlan) -> String: return String(p.id))
	ids.sort()
	assert_eq(ids, ["good", "seeded"], "malformed features and the flat-meadow cave are left out")
	for p: CavePlan in caves.plans:
		assert_true(p.ok, p.reason)
		assert_eq(p.region_id, REGION)
		if p.id == &"good":
			assert_eq(p.seed, CaveSites.shape_seed("test_world", "good"))
			assert_eq(p.style, &"grotto")
		else:
			assert_eq(p.seed, 99)
	# Same inputs, same caves.
	var again: CaveSet = CaveSites.from_region(wr[0], REGION, wr[1], _cfg)
	assert_eq(again.plans[0].digest(), caves.plans[0].digest())


func test_from_region_keeps_the_border_margin() -> void:
	# A slope at the region's west edge: the cave would come within 32 m of the border.
	var wr: Array = _world([{"type": "cave", "id": "edge", "style": "grotto", "mouth": [-500, 2048]}])
	var rt: RegionTerrain = wr[1]
	for iz: int in 513:
		for ix: int in 513:
			rt.height.set_h(ix, iz, maxf(0.0, 60.0 - 0.6 * (ix * 2.0)))
	assert_true(CaveSites.from_region(wr[0], REGION, rt, _cfg).is_empty())
	assert_true(CaveSites.from_region(null, REGION, rt, _cfg).is_empty())


func test_cave_set_queries() -> void:
	var a: CavePlan = CavePlan.build({"id": "a", "style": "grotto", "mouth": [0.0, 50.0]}, 7, _hill, _cfg)
	var b: CavePlan = CavePlan.build({"id": "b", "style": "grotto", "mouth": [50.0, 0.0]}, 8, _hill, _cfg)
	var dup: CavePlan = CavePlan.build({"id": "a", "style": "grotto", "mouth": [-50.0, 0.0]}, 9, _hill, _cfg)
	var failed: CavePlan = CavePlan.build({"id": "f", "style": "grotto", "mouth": [500.0, 500.0]}, 1, _hill, _cfg)
	assert_true(a.ok and b.ok and dup.ok, "%s %s %s" % [a.reason, b.reason, dup.reason])
	assert_false(failed.ok)
	var caves: CaveSet = CaveSet.combined([CaveSet.combined([a], {}), failed], {&"b": b, &"a2": dup})
	assert_eq(caves.plans.size(), 2, "first plan of an id wins; failed plans are left out")
	assert_true(CaveSet.combined([], {}).is_empty())
	assert_true(caves.touching(a.aabb).has(a))
	assert_eq(caves.touching(AABB(Vector3(400, -50, 400), Vector3(10, 100, 10))).size(), 0)
	assert_eq(caves.touching(a.aabb.merge(b.aabb)).size(), 2)
	var c: Vector3 = (a.anchors().filter(func(x: Dictionary) -> bool: return x["kind"] == &"chamber")[0] as Dictionary)["pos"]
	var inside: Vector3 = c + Vector3.UP * 1.5
	assert_true(caves.is_inside(inside, _hill(inside.x, inside.z)))
	assert_false(caves.is_inside(Vector3(300, 1, 300), 5.0))
	assert_almost_eq(caves.floor_below(inside), c.y, 0.01)
	assert_true(is_nan(caves.floor_below(Vector3(300, 1, 300))))
	var m: Vector3 = b.mouth.origin
	assert_true(caves.keep_out(m.x, m.z))
	assert_false(caves.keep_out(300.0, 300.0))
