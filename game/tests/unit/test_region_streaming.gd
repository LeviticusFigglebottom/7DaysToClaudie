extends GutTest
## RegionStreamer (ADR-0038, RWG v2 Phase 2) on a synthetic 4x1 world of 256 m regions a b c d,
## "a" detailed at start: regions are composed on the streamer's threads (a fake compose) and
## attached as the focus moves, detached when it leaves, a job for a region nobody wants any more
## is cancelled mid-compose, a pin holds a region, is_area_ready answers for a position.

const COARSE_Y: float = 5.0
const DETAIL_Y: float = 30.0
const CFG: Dictionary = {"region": {"load": 100.0, "unload": 200.0, "prefetch": 100.0, "prefetch_ahead": 0.0,
	"max_attached": 2, "threads_runtime": 2}, "budget_ms": {"runtime": 50.0}}

var focus: Array = [Vector3.ZERO]
var composes: Array = [0]


func _world() -> WorldDef:
	var w := WorldDef.new()
	w.id = "streamer_test"
	w.cols = 4
	w.rows = 1
	w.region_size = 256.0
	for i: int in 4:
		var rid: String = "abcd"[i]
		var cell: String = "%s1" % "ABCD"[i]
		w.regions[rid] = {"id": rid, "cell": cell, "status": "built"}
		w.cells[cell] = rid
	return w


func _rt(w: WorldDef, rid: String, spacing: float, y: float) -> RegionTerrain:
	var rt := RegionTerrain.new()
	rt.region_id = rid
	rt.rect = w.region_rect(rid)
	rt.spacing = spacing
	var n: int = int(256.0 / spacing) + 1
	rt.height = HeightField.create(rt.rect.position, spacing, n, n, y)
	rt.splat0.resize(n * n * 4)
	rt.splat1.resize(n * n * 4)
	rt.biome.resize(n * n)
	rt.vegmask.resize(n * n)
	rt.palette = TerrainComposer.DEFAULT_PALETTE
	rt.biome_ids = PackedStringArray(["meadow"])
	return rt


## A terrain with "a" detailed and a streamer whose compose takes `delay_ms` (watching cancel).
func _setup(delay_ms: int = 0) -> Array:
	var w: WorldDef = _world()
	var coarse: Dictionary = {}
	for rid: String in ["b", "c", "d"]:
		coarse[rid] = _rt(w, rid, 16.0, COARSE_Y)
	var tm := TerrainManager.new()
	tm.defer_far_tiles = true
	add_child_autofree(tm)
	tm.setup(w, {"a": _rt(w, "a", 1.0, DETAIL_Y)}, coarse)
	var st := RegionStreamer.new()
	st.focus_fn = func() -> Array: return [focus[0]]
	st.compose_fn = func(rid: String, cancel: Array) -> RegionTerrain:
		var end: int = Time.get_ticks_msec() + delay_ms
		while Time.get_ticks_msec() < end:
			if cancel[0]:
				return null
			OS.delay_msec(2)
		composes[0] += 1
		return _rt(w, rid, 1.0, DETAIL_Y)
	add_child_autofree(st)
	st.setup(tm, CFG)
	return [tm, w, st]


func _mid(w: WorldDef, rid: String) -> Vector3:
	var c: Vector2 = w.region_rect(rid).get_center()
	return Vector3(c.x, 0.0, c.y)


func _wait(cond: Callable, seconds: float = 10.0) -> bool:
	var end: int = Time.get_ticks_msec() + int(seconds * 1000.0)
	while Time.get_ticks_msec() < end:
		if cond.call():
			return true
		await get_tree().process_frame
	return false


func before_each() -> void:
	composes[0] = 0


func test_regions_stream_in_and_out_as_the_focus_moves() -> void:
	var s: Array = _setup()
	var tm: TerrainManager = s[0]
	var w: WorldDef = s[1]
	var st: RegionStreamer = s[2]
	focus[0] = _mid(w, "c")
	var c: Vector3 = _mid(w, "c")
	assert_almost_eq(tm.height_at(c.x, c.z), COARSE_Y, 1e-3, "coarse before streaming")
	assert_true(await _wait(func() -> bool: return st.attached().has("c")), "c attached")
	assert_almost_eq(tm.height_at(c.x, c.z), DETAIL_Y, 1e-3, "1 m terrain under the focus")
	assert_true(await _wait(func() -> bool: return not st.attached().has("a")), "a, 640 m away, detached")
	assert_false(is_equal_approx(tm.height_at(_mid(w, "a").x, _mid(w, "a").z), DETAIL_Y), "a has no 1 m terrain now")
	focus[0] = _mid(w, "a")
	assert_true(await _wait(func() -> bool: return st.attached().has("a") and not st.attached().has("c")), "back to a, c gone")
	assert_true(st.is_area_ready(_mid(w, "a"), 50.0))
	assert_false(st.is_area_ready(_mid(w, "c"), 0.0))


func test_a_job_nobody_wants_is_cancelled_mid_compose() -> void:
	var s: Array = _setup(3000)
	var w: WorldDef = s[1]
	var st: RegionStreamer = s[2]
	focus[0] = _mid(w, "d")
	st.update()
	await _wait(func() -> bool: return int(st.status()["jobs"]) > 0, 2.0)
	focus[0] = _mid(w, "a")
	st.update()
	assert_true(await _wait(func() -> bool: return int(st.status()["cancelled"]) >= 1 and int(st.status()["jobs"]) == 0, 3.0), "cancelled")
	await get_tree().create_timer(0.5).timeout
	assert_false(st.attached().has("d"), "never attached")
	assert_eq(composes[0], 0, "the compose stopped early")


func test_a_pin_holds_a_region_and_is_area_ready_follows() -> void:
	var s: Array = _setup()
	var w: WorldDef = s[1]
	var st: RegionStreamer = s[2]
	focus[0] = _mid(w, "d")
	st.pin(&"hum", Rect2(-500, -100, 50, 50))
	assert_true(await _wait(func() -> bool: return st.attached().has("d")), "d attached")
	await get_tree().create_timer(0.6).timeout
	assert_true(st.attached().has("a"), "the pinned region stays")
	st.unpin(&"hum")
	assert_true(await _wait(func() -> bool: return not st.attached().has("a")), "unpinned, it goes")
