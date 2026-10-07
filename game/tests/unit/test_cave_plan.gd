extends GutTest
## CavePlan (ADR-0056): deterministic shape, an open mouth, cover and clearance, carve_block
## agreeing with sdf sample by sample, failing plans on flat ground, and carve timing.

const N: int = 32
const VOXEL: float = 0.5
const SIZE: float = 16.0

var _cfg: Dictionary = {}


func before_all() -> void:
	var j := JSON.new()
	assert_eq(j.parse(FileAccess.get_file_as_string("res://data/config/caves.json")), OK)
	_cfg = j.data


## A steep cone hill (33°) around the origin, 45 m high.
static func _hill(x: float, z: float) -> float:
	return maxf(0.0, 45.0 - 0.65 * Vector2(x, z).length())


## A 39° face rising towards +X (shelters want 30° or more).
static func _tilted(x: float, _z: float) -> float:
	return 0.8 * x


static func _flat(_x: float, _z: float) -> float:
	return 3.0


func _grotto(seed: int = 7) -> CavePlan:
	var spec: Dictionary = {"id": "g", "style": "grotto", "mouth": [0.0, 50.0], "heading": "uphill", "length": [24.0, 28.0]}
	return CavePlan.build(spec, seed, _hill, _cfg)


func _shelter(seed: int = 3) -> CavePlan:
	return CavePlan.build({"id": "s", "style": "shelter", "mouth": [20.0, 0.0]}, seed, _tilted, _cfg)


func _density(p: Vector3, h: float, sd: float) -> float:
	return minf(clampf(h - p.y, -2.0, 2.0), clampf(sd, -2.0, 2.0))


func test_builds_and_is_deterministic() -> void:
	var a: CavePlan = _grotto()
	assert_true(a.ok, a.reason)
	assert_eq(a.digest(), _grotto().digest())
	assert_ne(a.digest(), _grotto(8).digest(), "another seed shapes another cave")
	assert_eq(a.spine.size(), a.radii.size())
	assert_eq(a.spine.size(), a.floor_y.size())
	var s: CavePlan = _shelter()
	assert_true(s.ok, s.reason)
	assert_eq(s.digest(), _shelter().digest())
	assert_ne(a.digest(), s.digest())


func test_mouth_heads_into_the_hill_and_spine_starts_outside() -> void:
	var p: CavePlan = _grotto()
	assert_true(p.ok, p.reason)
	var into: Vector3 = -p.mouth.basis.z
	var m: Vector3 = p.mouth.origin
	# Uphill on the cone is towards the apex.
	assert_gt(into.dot(-Vector3(m.x, 0.0, m.z).normalized()), 0.9)
	assert_gt(_hill(m.x + into.x * 4.0, m.z + into.z * 4.0), _hill(m.x, m.z) + 2.0)
	var s0: Vector3 = p.spine[0]
	assert_almost_eq((m - s0).dot(into), 1.5, 0.2, "the spine starts 1.5 m down the slope")
	assert_almost_eq(m.y, _hill(m.x, m.z), 0.6, "the mouth floor sits at the ground")


func test_air_in_chamber_and_rock_off_the_tube() -> void:
	var p: CavePlan = _grotto()
	var chamber: Array = p.anchors().filter(func(a: Dictionary) -> bool: return a["kind"] == &"chamber")
	assert_eq(chamber.size(), 1)
	var c: Vector3 = chamber[0]["pos"]
	assert_lt(p.sdf(c + Vector3.UP * 1.5), -0.5, "air in the chamber")
	assert_gt(p.sdf(c + Vector3.DOWN * 1.0), 0.5, "rock under the chamber floor")
	for i: int in range(p.spine.size() / 3, p.spine.size() * 2 / 3):
		var q: Vector3 = p.spine[i]
		assert_gt(p.sdf(q + Vector3.UP * (p.radii[i] + 3.5)), 0.0, "rock 3 m over the tube")
		assert_gt(p.sdf(Vector3(q.x, p.floor_y[i] - 3.0, q.z)), 0.0, "rock 3 m under the floor")
	var s: CavePlan = _shelter()
	for i: int in range(s._mouth_i, s.spine.size()):
		var q2: Vector3 = s.spine[i]
		var lat: Vector3 = s.mouth.basis.x
		for side: float in [-1.0, 1.0]:
			assert_gt(s.sdf(q2 + lat * side * (s.radii[i] + 0.45 + 3.0)), 0.0, "rock 3 m beside the shelter")


func test_mouth_opens() -> void:
	for p: CavePlan in [_grotto(), _shelter()]:
		var m: Vector3 = p.mouth.origin
		var into: Vector3 = -p.mouth.basis.z
		var under_ground: int = 0
		for k: int in 9:
			var q: Vector3 = m + into * (k * 0.5) + Vector3.UP * 1.0
			var h: float = _hill(q.x, q.z) if p.style == &"grotto" else _tilted(q.x, q.z)
			assert_lt(_density(q, h, p.sdf(q)), 0.0, "air 1 m over the mouth floor, %.1f m in" % (k * 0.5))
			if h > q.y + 0.5:
				under_ground += 1
		assert_gt(under_ground, 0, "the opening pierces the slope")


func test_cover_beyond_the_portal() -> void:
	for p: CavePlan in [_grotto(), _grotto(11), _shelter()]:
		assert_true(p.ok, p.reason)
		# Past the portal (the thin hood on the slope) and at the back wall.
		var st: Dictionary = _cfg["styles"][String(p.style)]
		assert_almost_eq(p._portal, maxf(float(st["portal"]) * p._length, float(st.get("portal_min", 0.0))), 6.0)
		var from: float = p._mouth_arc + p._portal
		var hf: Callable = _hill if p.style == &"grotto" else _tilted
		for i: int in p.spine.size():
			if p._arc[i] < from and i != p.spine.size() - 1:
				continue
			var top: float = p.floor_y[i]
			while p.sdf(Vector3(p.spine[i].x, top + 0.1, p.spine[i].z)) < 0.0:
				top += 0.1
			var cover: float = float(hf.call(p.spine[i].x, p.spine[i].z)) - top
			assert_gte(cover, 2.0, "%s cover at sample %d" % [p.id, i])


func test_clearance_along_the_spine() -> void:
	for p: CavePlan in [_grotto(), _grotto(11), _grotto(12), _shelter(), _shelter(4)]:
		assert_true(p.ok, p.reason)
		for i: int in range(p._mouth_i, p.spine.size()):
			var f := Vector3(p.spine[i].x, p.floor_y[i] + 0.05, p.spine[i].z)
			for h: float in [0.0, 0.5, 1.0, 1.5, 2.0, 2.2]:
				assert_lt(p.sdf(f + Vector3.UP * h), 0.0, "%s: air %.1f m over the floor at sample %d" % [p.id, h, i])


func test_carve_block_matches_sdf() -> void:
	var p: CavePlan = _grotto()
	var keys: Array[Vector3i] = []
	var m: Vector3 = p.mouth.origin
	keys.append(VolumeTerrain.chunk_of(m))
	keys.append(VolumeTerrain.chunk_of(p.spine[p.spine.size() / 2]))
	var chamber: Dictionary = p.anchors().filter(func(a: Dictionary) -> bool: return a["kind"] == &"chamber")[0]
	keys.append(VolumeTerrain.chunk_of(chamber["pos"] + Vector3.UP))
	var s: int = N + 3
	for key: Vector3i in keys:
		var origin := Vector3(key) * SIZE
		var dens := PackedFloat32Array()
		dens.resize(s * s * s)
		for k: int in s:
			for j: int in s:
				for i: int in s:
					var q: Vector3 = origin + Vector3(i - 1, j - 1, k - 1) * VOXEL
					dens[(k * s + j) * s + i] = clampf(_hill(q.x, q.z) - q.y, -2.0, 2.0)
		var before: PackedFloat32Array = dens.duplicate()
		assert_true(p.carve_block(origin, N, VOXEL, dens), "chunk %s is carved" % key)
		var bad: int = 0
		for k: int in s:
			for j: int in s:
				for i: int in s:
					var idx: int = (k * s + j) * s + i
					var q2: Vector3 = origin + Vector3(i - 1, j - 1, k - 1) * VOXEL
					var want: float = minf(before[idx], clampf(p.sdf(q2), -2.0, 2.0))
					if absf(dens[idx] - want) > 1e-4:
						if bad < 5:
							gut.p("mismatch at %s: carved %f, sdf %f" % [q2, dens[idx], want])
						bad += 1
		assert_eq(bad, 0, "carve_block equals sdf in chunk %s" % key)
	# A chunk far away is untouched.
	var far := PackedFloat32Array()
	far.resize(s * s * s)
	far.fill(2.0)
	assert_false(p.carve_block(Vector3(400, 0, 400), N, VOXEL, far))
	assert_eq(far.count(2.0), far.size())


func test_columns_cover_the_carved_chunks() -> void:
	var p: CavePlan = _grotto()
	var cols: Dictionary = p.columns()
	assert_false(cols.is_empty())
	for i: int in p.spine.size():
		var key: Vector3i = VolumeTerrain.chunk_of(p.spine[i])
		var col := Vector2i(key.x, key.z)
		assert_true(cols.has(col), "column %s" % col)
		var span: Vector2i = cols[col]
		assert_between(key.y, span.x, span.y)


func test_queries() -> void:
	var p: CavePlan = _grotto()
	var c: Vector3 = (p.anchors().filter(func(a: Dictionary) -> bool: return a["kind"] == &"chamber")[0] as Dictionary)["pos"]
	var inside: Vector3 = c + Vector3.UP * 1.5
	assert_true(p.is_inside(inside, _hill(inside.x, inside.z)))
	assert_false(p.is_inside(Vector3(c.x, _hill(c.x, c.z) + 1.0, c.z), _hill(c.x, c.z)), "on the hill above")
	assert_almost_eq(p.floor_below(inside), c.y, 0.01)
	assert_true(is_nan(p.floor_below(Vector3(c.x, _hill(c.x, c.z) + 0.5, c.z))), "the hilltop is not over cave air")
	assert_true(is_nan(p.floor_below(Vector3(300, 0, 300))))
	var m: Vector3 = p.mouth.origin
	assert_true(p.keep_out(m.x, m.z))
	var out: Vector3 = m + p.mouth.basis.z * 3.0
	assert_true(p.keep_out(out.x, out.z), "the apron below the mouth")
	assert_false(p.keep_out(m.x + 40.0, m.z))
	var kinds: Dictionary = {}
	for a: Dictionary in p.anchors():
		kinds[a["kind"]] = true
	assert_true(kinds.has(&"mouth") and kinds.has(&"tunnel") and kinds.has(&"chamber"))


func test_probe_boxes_stay_under_ground() -> void:
	for p: CavePlan in [_grotto(), _grotto(11), _shelter()]:
		var boxes: Array = p.probe_boxes()
		assert_between(boxes.size(), 1, 3, "%s has probes" % p.id)
		var hf: Callable = _hill if p.style == &"grotto" else _tilted
		var last: float = 2.0
		for b: Array in boxes:
			var xf: Transform3D = b[0]
			var size: Vector3 = b[1]
			var ratio: float = b[2]
			assert_between(ratio, 0.0, 1.0)
			assert_lte(ratio, last, "daylight falls with depth")
			last = ratio
			for cx: float in [-0.5, 0.5]:
				for cz: float in [-0.5, 0.5]:
					var corner: Vector3 = xf * Vector3(size.x * cx, size.y * 0.5, size.z * cz)
					assert_lte(corner.y, float(hf.call(corner.x, corner.z)) - 0.3 + 1e-3, "%s probe top under the ground" % p.id)


func test_flat_ground_fails() -> void:
	var p: CavePlan = CavePlan.build({"id": "f", "style": "grotto", "mouth": [0.0, 0.0]}, 1, _flat, _cfg)
	assert_false(p.ok)
	assert_ne(p.reason, "")
	var dens := PackedFloat32Array()
	dens.resize((N + 3) * (N + 3) * (N + 3))
	dens.fill(2.0)
	assert_false(p.carve_block(Vector3(-8, -8, -8), N, VOXEL, dens), "a failed plan carves nothing")
	assert_true(p.columns().is_empty())
	var bad: CavePlan = CavePlan.build({"id": "b", "style": "cathedral", "mouth": [20.0, 0.0]}, 1, _tilted, _cfg)
	assert_false(bad.ok)
	assert_string_contains(bad.reason, "style")


func test_region_margin() -> void:
	var spec: Dictionary = {"id": "r", "style": "shelter", "mouth": [20.0, 0.0], "region_rect": Rect2(0, -500, 1000, 1000)}
	var p: CavePlan = CavePlan.build(spec, 3, _tilted, _cfg)
	assert_false(p.ok, "within 32 m of the region's west edge")
	assert_string_contains(p.reason, "region")
	spec["region_rect"] = Rect2(-500, -500, 1000, 1000)
	assert_true(CavePlan.build(spec, 3, _tilted, _cfg).ok)


func test_carve_timing() -> void:
	var p: CavePlan = _grotto()
	var s: int = N + 3
	var best_ms: float = INF
	var key: Vector3i = VolumeTerrain.chunk_of(p.spine[p.spine.size() * 2 / 3])
	var origin := Vector3(key) * SIZE
	for run: int in 3:
		var dens := PackedFloat32Array()
		dens.resize(s * s * s)
		dens.fill(2.0)
		var t0: int = Time.get_ticks_usec()
		p.carve_block(origin, N, VOXEL, dens)
		best_ms = minf(best_ms, (Time.get_ticks_usec() - t0) / 1000.0)
	var t1: int = Time.get_ticks_usec()
	var g: CavePlan = _grotto(21)
	var build_ms: float = (Time.get_ticks_usec() - t1) / 1000.0
	gut.p("[cave] carve one chunk inside a grotto: %.1f ms (aim < 150); build a plan: %.1f ms (%s)" % [best_ms, build_ms, g.ok])
	assert_true(true)
