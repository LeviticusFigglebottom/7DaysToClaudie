extends GutTest
## Light inside buildings (ADR-0050): every wall, floor and ceiling face of every room gets its
## interior probe's full fill (player report 3: block-walled rooms read near black by day because
## the probes' blend band started inside the walls), facades keep the outdoor light, and the fill
## and the indoor exposure follow data/config/interior_light.json.


func _def(layout: Dictionary, footprint: Array = [16, 16]) -> PoiDef:
	var raw: Dictionary = {"id": "t", "name": "T", "tier": 2, "footprint": footprint}
	raw.merge(layout, true)
	var d := PoiDef.new()
	var errs: PackedStringArray = d.parse(raw, &"poi", "test")
	assert_eq(errs, PackedStringArray(), "def parses")
	return d


## Godot 4.7.2's box blend (scene_forward_lights_inc.glsl, reflection_process): 0 outside the box,
## fading over `blend` metres inside each face as ((1 - d) per axis)^2.
static func blend_at(box: AABB, blend: float, p: Vector3) -> float:
	var ext: Vector3 = box.size * 0.5
	var local: Vector3 = (p - box.get_center()).abs()
	if local.x > ext.x or local.y > ext.y or local.z > ext.z:
		return 0.0
	var f: float = 1.0
	for i: int in 3:
		var bd: float = minf(blend, ext[i])
		f *= clampf(1.0 - (local[i] - ext[i] + bd) / bd, 0.0, 1.0)
	return f * f


## The most fill any of `boxes` gives at `p` (overlapping boxes fill up to the strongest).
static func fill_at(boxes: Array[AABB], p: Vector3) -> float:
	var best: float = 0.0
	for box: AABB in boxes:
		best = maxf(best, blend_at(box, PoiBuilder.PROBE_BLEND, p))
	return best


## Points on the inner faces of a room cell's four sides, at floor, mid and ceiling height, and its
## floor and ceiling at the centre.
static func face_points(l: PoiLayout, li: int, c: Vector2i) -> Array[Vector3]:
	var centre: Vector3 = l.cell_center(li, c)
	var ceil_h: float = l.ceiling_height(li, c)
	var inset: float = 0.5 - PoiBuilder.WALL_T * 0.5 - 0.005
	var out: Array[Vector3] = [centre + Vector3(0, 0.01, 0), centre + Vector3(0, ceil_h - 0.01, 0)]
	for d: Vector3 in [Vector3.LEFT, Vector3.RIGHT, Vector3.FORWARD, Vector3.BACK]:
		for h: float in [0.02, 1.4, ceil_h - 0.02]:
			out.append(centre + d * inset + Vector3(0, h, 0))
	return out


func test_wall_faces_get_the_full_fill_and_facades_none() -> void:
	# One block room: its walls are outside walls on every side.
	var b := PoiBuilder.new()
	b.layout = PoiLayout.compile(_def({"levels": [{"level": 0, "plan": ["AAA", "AAA", "AAA"], "rooms": {"A": {}}}]}))
	var boxes: Array[AABB] = b.probe_boxes()
	assert_eq(boxes.size(), 1)
	for c: Vector2i in b.layout.room_cells(0):
		for p: Vector3 in face_points(b.layout, 0, c):
			assert_gt(fill_at(boxes, p), 0.99, "full fill at %s" % p)
	# The outer face of the west wall, mid-height: outdoors.
	var west: Vector3 = b.layout.cell_center(0, Vector2i(0, 1)) + Vector3(-0.5 - PoiBuilder.WALL_T * 0.5 - 0.002, 1.4, 0)
	assert_eq(fill_at(boxes, west), 0.0, "the facade keeps the outdoor light")
	# The old boxes (5 cm past the centre lines, a 0.3 m band) left the wall faces about 1%.
	var old := AABB(b.layout.local_pos(0, Vector2(0.05, 0.05)) + Vector3(0, -0.2, 0), Vector3(2.9, 3.2, 2.9))
	var face: Vector3 = b.layout.cell_center(0, Vector2i(0, 1)) + Vector3(-0.5 + PoiBuilder.WALL_T * 0.5, 1.4, 0)
	assert_lt(blend_at(old, 0.3, face), 0.02, "what player report 3 saw")


func test_seams_between_boxes_of_one_room_are_filled() -> void:
	# An L-shaped room splits into two rectangles; where they meet there is no wall, and the
	# floor along the seam must not show a dark line.
	var b := PoiBuilder.new()
	b.layout = PoiLayout.compile(_def({"levels": [{"level": 0, "plan": ["AA..", "AA..", "AAAA", "AAAA"], "rooms": {"A": {}}}]}))
	var boxes: Array[AABB] = b.probe_boxes()
	assert_eq(boxes.size(), 2)
	for c: Vector2i in b.layout.room_cells(0):
		var centre: Vector3 = b.layout.cell_center(0, c)
		for d: Vector3 in [Vector3.LEFT, Vector3.RIGHT, Vector3.FORWARD, Vector3.BACK]:
			# The cell's edge itself (a seam or a wall's centre line inside the room's own cells).
			var edge: Vector3 = centre + d * 0.5 + Vector3(0, 0.01, 0)
			var n: Vector2i = c + Vector2i(int(d.x), int(d.z))
			if b.layout.is_built(0, n):
				assert_gt(fill_at(boxes, edge), 0.99, "no seam between %s and %s" % [c, n])


func test_every_poi_room_face_is_filled() -> void:
	var bad: PackedStringArray = []
	for v: Variant in Content.all(&"poi"):
		var pd := v as PoiDef
		var l: PoiLayout = PoiLayout.compile(pd)
		if not l.errors.is_empty():
			continue
		var b := PoiBuilder.new()
		b.layout = l
		var boxes: Array[AABB] = b.probe_boxes()
		var misses: int = 0
		var first: String = ""
		for li: int in l.level_ids:
			for c: Vector2i in l.room_cells(li):
				for p: Vector3 in face_points(l, li, c):
					if fill_at(boxes, p) < 0.99:
						misses += 1
						if first.is_empty():
							first = "level %d cell %s at %s" % [li, c, p]
		if misses > 0:
			bad.append("%s: %d dim face points (first %s)" % [pd.id, misses, first])
	assert_eq(bad, PackedStringArray(), "every room's faces get the probe's full fill")


func test_fill_follows_the_day() -> void:
	var cfg: Dictionary = Content.config(&"interior_light")
	assert_false(cfg.is_empty(), "interior_light.json loads")
	var night_col := Color.html("#5c6f99")
	var noon: Color = EnvironmentController.interior_fill(cfg, 1.0, 0.0, 0.1, night_col)
	var grey: Color = EnvironmentController.interior_fill(cfg, 1.0, 1.0, 0.1, night_col)
	var moonlit: Color = EnvironmentController.interior_fill(cfg, 0.0, 0.0, 0.11, night_col)
	var moonless: Color = EnvironmentController.interior_fill(cfg, 0.0, 0.0, 0.0, night_col)
	assert_almost_eq(noon.a, float(cfg["day_fill"]), 1e-4)
	assert_lt(grey.a, noon.a, "overcast dims it")
	assert_lt(moonlit.a, grey.a * 0.5, "nights stay dark")
	assert_almost_eq(moonlit.a, 0.11 * float(cfg["night_share"]), 1e-4, "a share of the night's ambient")
	assert_almost_eq(moonless.a, float(cfg["night_floor"]), 1e-4, "never quite black")
	assert_almost_eq(moonlit.b, night_col.b, 1e-4, "in the night's colour")


func test_exposure_opens_indoors() -> void:
	var cfg: Dictionary = Content.config(&"interior_light")
	assert_eq(EnvironmentController.indoor_exposure(cfg, 1.0, 0.0), 1.0, "outdoors as before")
	assert_almost_eq(EnvironmentController.indoor_exposure(cfg, 1.0, 1.0), float(cfg["exposure_day"]), 1e-4)
	assert_almost_eq(EnvironmentController.indoor_exposure(cfg, 0.0, 1.0), float(cfg["exposure_night"]), 1e-4)
	assert_gt(float(cfg["exposure_day"]), 1.0)


func test_daylight_follows_the_openings() -> void:
	# Three 3x3 rooms in a row: the west one has a window, the middle one only inside doors, the
	# east one a boarded window. A cellar under them has none.
	var lay: Dictionary = {
		"levels": [{"level": -1, "plan": ["CCC", "CCC", "CCC"], "rooms": {"C": {}}},
			{"level": 0, "plan": ["AAA BBB DDD", "AAA BBB DDD", "AAA BBB DDD"], "rooms": {"A": {}, "B": {}, "D": {}}}],
		"openings": [{"at": [0, 1], "side": "W", "type": "window"},
			{"at": [10, 1], "side": "E", "type": "window", "state": "boarded"}]}
	var b := PoiBuilder.new()
	b.layout = PoiLayout.compile(_def(lay, [20, 12]))
	assert_eq(b.layout.errors, PackedStringArray())
	var by_room: Dictionary = {}
	for box: AABB in b.probe_boxes():
		for ch: String in ["A", "B", "D"]:
			var c: Vector2i = {"A": Vector2i(1, 1), "B": Vector2i(5, 1), "D": Vector2i(9, 1)}[ch]
			if box.has_point(b.layout.cell_center(0, c) + Vector3.UP):
				by_room[ch] = b.daylight_ratio(box)
		if box.has_point(b.layout.cell_center(-1, Vector2i(1, 1)) + Vector3.UP):
			by_room["C"] = b.daylight_ratio(box)
	assert_almost_eq(float(by_room.get("A", -1.0)), 1.2 / (3.14 * 3.14), 0.02, "one window over a 3x3 floor")
	assert_eq(float(by_room.get("B", -1.0)), 0.0, "no outside opening")
	assert_lt(float(by_room.get("D", -1.0)), float(by_room["A"]) * 0.5, "boards let little through")
	assert_gt(float(by_room.get("D", -1.0)), 0.0)
	assert_eq(float(by_room.get("C", -1.0)), 0.0, "the cellar")
	var cfg: Dictionary = Content.config(&"interior_light")
	assert_almost_eq(EnvironmentController.daylight_share(cfg, 0.0), float(cfg["daylight_min_share"]), 1e-4)
	assert_eq(EnvironmentController.daylight_share(cfg, 1.0), 1.0)
	assert_eq(EnvironmentController.daylight_share(cfg, -1.0), 1.0, "a probe with no ratio")


func test_poi_daylight_survey() -> void:
	# Not a pass/fail on taste: every POI's rooms have a ratio, and the spread is printed for tuning.
	var ratios: Array[float] = []
	for v: Variant in Content.all(&"poi"):
		var l: PoiLayout = PoiLayout.compile(v as PoiDef)
		if not l.errors.is_empty():
			continue
		var b := PoiBuilder.new()
		b.layout = l
		for box: AABB in b.probe_boxes():
			var r: float = b.daylight_ratio(box)
			assert_true(r >= 0.0 and is_finite(r))
			ratios.append(r)
	ratios.sort()
	var n: int = ratios.size()
	gut.p("daylight ratios over %d boxes: p10 %.3f p25 %.3f p50 %.3f p75 %.3f p90 %.3f, zero %d" % [n,
		ratios[n / 10], ratios[n / 4], ratios[n / 2], ratios[n * 3 / 4], ratios[n * 9 / 10], ratios.count(0.0)])
