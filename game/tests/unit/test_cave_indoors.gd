extends GutTest
## Caves in the dark (CAVES_PLAN WS-D): a real CavePlan placed at runtime on a synthetic hill
## (TerrainManager.place_cave). Its interior probes (CaveLighting) stay under the ground and inside
## the cave, their daylight falls with depth, they join `interior_probe` and InteriorProbeBudget
## adopts them, and they go when the cave does. PoiManager.is_indoors is true in the chamber and
## false at the mouth's apron and on the hill above; room_type_at says "cave". The volume meshes of
## the cave paint the hill's surface as surface and the chamber as cave.
## The terrain is test_volume_streaming's synthetic world, one 256 m region with a cone hill.

const Budget := preload("res://src/poi/interior_probe_budget.gd")
const CAVE_ID: StringName = &"hill_cave"
const SPEC: Dictionary = {"style": "grotto", "mouth": [0.0, 50.0], "heading": "uphill", "length": [24.0, 28.0], "seed": 7}

var _tm: TerrainManager
var _plan: CavePlan
var _cfg: Dictionary = {}


## A 33° cone 45 m high around the origin (test_cave_plan's hill).
static func _hill(x: float, z: float) -> float:
	return maxf(0.0, 45.0 - 0.65 * Vector2(x, z).length())


func _world() -> WorldDef:
	var w := WorldDef.new()
	w.id = "cave_indoors_test"
	w.cols = 1
	w.rows = 1
	w.region_size = 256.0
	w.regions = {"a": {"id": "a", "cell": "A1"}}
	w.cells = {"A1": "a"}
	return w


func _rt(w: WorldDef) -> RegionTerrain:
	var rt := RegionTerrain.new()
	rt.region_id = "a"
	rt.rect = w.region_rect("a")
	rt.spacing = 1.0
	var n: int = 257
	rt.height = HeightField.create(rt.rect.position, 1.0, n, n, 0.0)
	for iz: int in n:
		for ix: int in n:
			rt.height.set_h(ix, iz, _hill(rt.rect.position.x + ix, rt.rect.position.y + iz))
	rt.splat0.resize(n * n * 4)
	rt.splat1.resize(n * n * 4)
	rt.biome.resize(n * n)
	rt.vegmask.resize(n * n)
	rt.palette = TerrainComposer.DEFAULT_PALETTE
	rt.biome_ids = PackedStringArray(["meadow"])
	return rt


func before_all() -> void:
	_cfg = Content.config(&"interior_light")
	var w: WorldDef = _world()
	_tm = TerrainManager.new()
	_tm.defer_far_tiles = true
	add_child(_tm)
	_tm.setup(w, {"a": _rt(w)}, {})
	_plan = _tm.place_cave(CAVE_ID, SPEC) as CavePlan
	# Build the cave's volume the way frames do.
	var until: int = Time.get_ticks_msec() + 120000
	while not _tm.volume.is_idle() and Time.get_ticks_msec() < until:
		_tm.start_queued()
		_tm.volume.pump(50.0)
		OS.delay_msec(1)


func after_all() -> void:
	_tm.free()


func _probes() -> Array[ReflectionProbe]:
	var out: Array[ReflectionProbe] = []
	var holder: Node3D = _tm.cave_lighting.holder_of(CAVE_ID)
	if holder != null:
		for n: Node in holder.get_children():
			out.append(n as ReflectionProbe)
	return out


func _chamber() -> Vector3:
	for a: Dictionary in _plan.anchors():
		if a["kind"] == &"chamber":
			return a["pos"]
	return Vector3(NAN, NAN, NAN)


func _corners(p: ReflectionProbe) -> Array[Vector3]:
	var out: Array[Vector3] = []
	var h: Vector3 = p.size * 0.5
	for sx: float in [-1.0, 1.0]:
		for sy: float in [-1.0, 1.0]:
			for sz: float in [-1.0, 1.0]:
				out.append(p.transform * Vector3(h.x * sx, h.y * sy, h.z * sz))
	return out


func test_the_cave_is_placed_and_built() -> void:
	assert_not_null(_plan)
	assert_true(_plan.ok, _plan.reason if _plan != null else "")
	assert_true(_tm.volume.is_idle(), "its volume is built")
	assert_false(_tm.volume.committed.is_empty(), "and its columns handed over")


func test_probe_boxes_stay_under_the_ground_and_in_the_cave() -> void:
	var probes: Array[ReflectionProbe] = _probes()
	assert_eq(probes.size(), _plan.probe_boxes().size())
	assert_between(probes.size(), 2, 3, "a grotto gets its tunnel's and its chamber's")
	var box: AABB = _plan.aabb.grow(0.5)
	for p: ReflectionProbe in probes:
		assert_true(p.is_in_group(&"interior_probe"))
		assert_true(p.interior)
		assert_eq(p.ambient_mode, ReflectionProbe.AMBIENT_COLOR)
		assert_eq(p.update_mode, ReflectionProbe.UPDATE_ONCE)
		assert_eq(p.blend_distance, PoiBuilder.PROBE_BLEND)
		var top_y: float = (p.transform * Vector3(0.0, p.size.y * 0.5, 0.0)).y
		for c: Vector3 in _corners(p):
			assert_true(box.has_point(c), "corner %s inside the cave's AABB %s" % [c, box])
			if c.y > top_y - 0.01:
				assert_lt(c.y, _tm.height_at(c.x, c.z) - 0.29, "the top corner %s stays under the ground" % c)
		var ct: Vector3 = p.transform.origin
		assert_lt(top_y, _tm.height_at(ct.x, ct.z) - 0.29, "and so does the top's centre")


func test_daylight_falls_with_depth() -> void:
	var probes: Array[ReflectionProbe] = _probes()
	var m: Vector3 = _plan.mouth.origin
	probes.sort_custom(func(a: ReflectionProbe, b: ReflectionProbe) -> bool:
		return Vector2(a.position.x - m.x, a.position.z - m.z).length() < Vector2(b.position.x - m.x, b.position.z - m.z).length())
	var last: float = INF
	var last_share: float = INF
	for p: ReflectionProbe in probes:
		var d: float = float(p.get_meta(&"daylight"))
		var share: float = EnvironmentController.daylight_share(_cfg, d, float(p.get_meta(&"min_share")))
		assert_lt(d, last, "deeper is darker")
		assert_lt(share, last_share)
		assert_almost_eq(float(p.get_meta(&"min_share")), float(_cfg["cave_min_share"]), 1e-6)
		assert_gte(share, float(_cfg["cave_min_share"]) - 1e-6)
		last = d
		last_share = share
	assert_lt(last_share, 0.5, "the chamber gets under half the fill")
	var ratios: Array = _plan.probe_boxes().map(func(b: Array) -> float: return float(b[2]))
	for r: Variant in ratios:
		assert_between(float(r), 0.0, 1.0)


func test_probes_join_the_budget_and_go_with_the_cave() -> void:
	var budget: Node = Budget.new()
	budget.show_per_rank = 1 << 20
	var frame: Array = [1000]
	budget.frames = func() -> int: return frame[0]
	add_child_autofree(budget)
	var probes: Array[ReflectionProbe] = _probes()
	for p: ReflectionProbe in probes:
		assert_true(budget.all_probes().has(p), "adopted")
	budget.flush_parks()
	for p2: ReflectionProbe in probes:
		assert_false(p2.is_inside_tree(), "parked as they enter")
	frame[0] += 100000
	budget.update(_chamber() + Vector3.UP)
	for p3: ReflectionProbe in probes:
		assert_true(budget.is_shown(p3), "the eye in the chamber puts them back")
	# Park one again, then take the cave away: every probe goes, parked or not.
	budget.focus(_chamber() + Vector3.UP, 1)
	_tm.remove_cave(CAVE_ID)
	assert_null(_tm.cave_lighting.holder_of(CAVE_ID))
	await get_tree().process_frame
	await get_tree().process_frame
	for p4: ReflectionProbe in probes:
		assert_false(is_instance_valid(p4), "freed with its cave")
	assert_eq(budget.all_probes().size(), 0, "and forgotten by the budget")
	# Put back for the tests that follow (the plan is the same object: same probes).
	_tm.place_cave(CAVE_ID, _plan)
	assert_eq(_probes().size(), _plan.probe_boxes().size())


func test_indoors_in_the_chamber_not_at_the_mouth_or_on_the_hill() -> void:
	var world := WorldStub.new()
	world.terrain = _tm
	var pm := PoiManager.new()
	pm.world = world
	var c: Vector3 = _chamber()
	assert_false(is_nan(c.x), "the grotto has a chamber")
	assert_true(pm.is_indoors(c + Vector3.UP * 1.5), "in the chamber")
	assert_eq(pm.room_type_at(c + Vector3.UP * 1.5), "cave")
	var m: Transform3D = _plan.mouth
	assert_false(pm.is_indoors(m.origin + Vector3.UP * 1.0), "on the mouth's floor")
	assert_false(pm.is_indoors(m.origin + m.basis.z * 2.5 + Vector3.UP * 1.0), "on the apron outside it")
	assert_eq(pm.room_type_at(m.origin + m.basis.z * 2.5 + Vector3.UP * 1.0), "")
	assert_false(pm.is_indoors(Vector3(c.x, _tm.height_at(c.x, c.z) + 1.5, c.z)), "on the hill over the chamber")
	assert_false(pm.is_indoors(Vector3(-90.0, 2.0, -90.0)), "far from any cave")
	assert_eq(AmbienceDirector.reverb_bus(true, true), &"ReverbCave")
	assert_eq(AmbienceDirector.reverb_bus(true, false), &"ReverbInterior")
	assert_eq(AmbienceDirector.reverb_bus(false, false), &"SFX")
	pm.free()
	world.free()


func test_is_indoors_is_cheap() -> void:
	var world := WorldStub.new()
	world.terrain = _tm
	var pm := PoiManager.new()
	pm.world = world
	var c: Vector3 = _chamber() + Vector3.UP * 1.5
	var t0: int = Time.get_ticks_usec()
	for i: int in 2000:
		pm.is_indoors(c if i % 2 == 0 else Vector3(-90.0, 2.0, -90.0))
	var us: float = float(Time.get_ticks_usec() - t0) / 2000.0
	gut.p("is_indoors: %.1f us a call" % us)
	assert_lt(us, 200.0, "five systems ask every frame")
	pm.free()
	world.free()


func test_the_cave_volume_paints_surface_and_interior() -> void:
	var c: Vector3 = _chamber()
	var surf: int = 0
	var deep: int = 0
	for key: Vector3i in _tm.volume.chunks:
		var ch: VolumeTerrain.VChunk = _tm.volume.chunks[key]
		if ch.mesh_node == null or ch.mesh_node.mesh == null:
			continue
		assert_eq(ch.mesh_node.material_override, _tm.volume_material_for("a"), "the region's volume material")
		var arr: Array = (ch.mesh_node.mesh as ArrayMesh).surface_get_arrays(0)
		var verts: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
		var cols: PackedColorArray = arr[Mesh.ARRAY_COLOR]
		for i: int in verts.size():
			var w: Vector3 = verts[i] + ch.mesh_node.position
			if cols[i].r > 0.99:
				surf += 1
			if cols[i].g > 0.99 and w.distance_to(c) < 6.0:
				deep += 1
	assert_gt(surf, 100, "the hill over the cave keeps the heightmap's look")
	assert_gt(deep, 50, "the chamber reads as cave")
	var mat: ShaderMaterial = _tm.volume_material_for("a")
	assert_true(bool(mat.get_shader_parameter(&"has_splat")))
	var src: ShaderMaterial = _tm._materials["a"]
	for p: StringName in TerrainManager.VOLUME_SPLAT_PARAMS:
		assert_eq(mat.get_shader_parameter(p), src.get_shader_parameter(p), "%s copied from the region's material" % p)


class WorldStub:
	extends Node
	var terrain: Node
