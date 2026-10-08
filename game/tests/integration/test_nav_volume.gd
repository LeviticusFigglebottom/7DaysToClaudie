extends GutTest
## Navigation through the SDF volume (CAVES_PLAN WS-C, ADR-0056), end to end with the real cave
## generator inside the real volume: a grotto placed with TerrainManager.place_cave on a 21° hill,
## its chunks built by the volume's jobs, then NavTiles' real source assembly (_add_terrain via
## bake_inputs) baked synchronously tile by tile onto a navigation map of its own. A path runs from
## outside the mouth down to the chamber floor below the heightfield; the hillside above still has
## its path; no polygon is left on the heightfield over the opening the volume replaced; and the
## volume's events (chunks applied, caves changed) queue the tiles they touch for a rebake.

const Hill := preload("res://tests/unit/helpers/cave_hill.gd")

var _hw: Node3D
var _tm: TerrainManager
var _plan: CavePlan
var _nav: NavTiles
var _map := RID()
var _regions: Array[RID] = []
var _meshes: Dictionary = {}


func before_all() -> void:
	_hw = Hill.make()
	add_child(_hw)
	Hill.setup(_hw)
	_tm = _hw.get(&"terrain")
	_plan = Hill.place_grotto(_tm)
	_nav = NavTiles.new()
	_nav.enabled = false
	_hw.add_child(_nav)
	_nav.world = _hw


func after_all() -> void:
	for r: RID in _regions:
		NavigationServer3D.free_rid(r)
	if _map.is_valid():
		NavigationServer3D.free_rid(_map)
	_hw.free()


## The tiles the cave and some hillside around it lie in.
func _tile_keys() -> Array[Vector2i]:
	var fp := Rect2(_plan.aabb.position.x, _plan.aabb.position.z, _plan.aabb.size.x, _plan.aabb.size.z).grow(16.0)
	var lo: Vector2i = NavTiles.tile_of(Vector3(fp.position.x, 0.0, fp.position.y))
	var hi: Vector2i = NavTiles.tile_of(Vector3(fp.end.x, 0.0, fp.end.y))
	var out: Array[Vector2i] = []
	for z: int in range(lo.y, hi.y + 1):
		for x: int in range(lo.x, hi.x + 1):
			out.append(Vector2i(x, z))
	return out


## Bakes every tile synchronously and puts them on a fresh map (once).
func _bake_map() -> void:
	if _map.is_valid():
		return
	_map = NavigationServer3D.map_create()
	NavigationServer3D.map_set_cell_size(_map, 0.25)
	NavigationServer3D.map_set_cell_height(_map, 0.25)
	NavigationServer3D.map_set_up(_map, Vector3.UP)
	NavigationServer3D.map_set_active(_map, true)
	var t0: int = Time.get_ticks_msec()
	for k: Vector2i in _tile_keys():
		var inputs: Array = _nav.bake_inputs(k)
		var nm: NavigationMesh = inputs[0]
		NavigationServer3D.bake_from_source_geometry_data(nm, inputs[1])
		_meshes[k] = nm
		var r: RID = NavigationServer3D.region_create()
		NavigationServer3D.region_set_map(r, _map)
		NavigationServer3D.region_set_navigation_mesh(r, nm)
		_regions.append(r)
	# The map syncs on the server's own step, and the regions join at the first sync after they were
	# added: wait for the iteration to move past the one before them, then a few steps more.
	var start: int = NavigationServer3D.map_get_iteration_id(_map)
	var until: int = Time.get_ticks_msec() + 5000
	while NavigationServer3D.map_get_iteration_id(_map) <= start and Time.get_ticks_msec() < until:
		await get_tree().physics_frame
	for i: int in 3:
		await get_tree().physics_frame
	var polys: int = 0
	for k: Vector2i in _meshes:
		polys += (_meshes[k] as NavigationMesh).get_polygon_count()
	gut.p("[nav] baked %d tiles (%s) in %d ms: %d polygons, map iteration %d; cave %s mouth %s" % [_meshes.size(), _meshes.keys(), Time.get_ticks_msec() - t0,
		polys, NavigationServer3D.map_get_iteration_id(_map), _plan.aabb, _plan.mouth.origin])


func _path(from: Vector3, to: Vector3) -> PackedVector3Array:
	var path: PackedVector3Array = NavigationServer3D.map_get_path(_map, from, to, true)
	if path.size() < 2:
		gut.p("[nav] no path %s -> %s: closest %s / %s, %d regions, iteration %d" % [from, to,
			NavigationServer3D.map_get_closest_point(_map, from), NavigationServer3D.map_get_closest_point(_map, to),
			NavigationServer3D.map_get_regions(_map).size(), NavigationServer3D.map_get_iteration_id(_map)])
	return path


func test_a_the_real_grotto_carves_into_the_real_volume() -> void:
	assert_not_null(_plan, "place_cave returned a plan")
	assert_true(_plan.ok, "the grotto planned on a 21° hill: %s" % _plan.reason)
	if _plan == null or not _plan.ok:
		return
	assert_true(Hill.drain(_tm), "every volume job came back")
	var fp := Rect2(_plan.aabb.position.x, _plan.aabb.position.z, _plan.aabb.size.x, _plan.aabb.size.z)
	assert_true(_tm.volume.is_rect_ready(fp), "the cave's columns are committed")
	for col: Vector2i in _plan.columns():
		assert_true(_tm.volume.committed.has(col), "column %s is a heightmap hole" % col)
	# The chamber is air in the built density, its floor rock, and ground_below finds that floor.
	var floor_p: Vector3 = Hill.chamber_floor(_plan)
	assert_lt(_tm.volume.density_at(floor_p + Vector3.UP * 1.0), 0.0, "air over the chamber floor")
	assert_gt(_tm.volume.density_at(floor_p - Vector3.UP * 0.6), 0.0, "rock under it")
	assert_almost_eq(_tm.ground_below(floor_p + Vector3.UP * 1.0), floor_p.y, 0.4, "ground_below reads the chamber floor")
	assert_lt(floor_p.y, _tm.height_at(floor_p.x, floor_p.z) - 3.0, "the chamber lies well under the hillside")
	# The opening: the heightfield's surface lies in cave air at the mouth.
	assert_gt(_opening_points().size(), 0, "the mouth breaks through the hillside")
	assert_gt(_tm.volume.faces_in_rect(fp).size(), 0, "the volume has triangles there")


## Points on the heightfield over the mouth where the old surface floats in cave air (>= 1 m from
## every wall and the floor), on a 0.5 m grid.
func _opening_points() -> Array[Vector3]:
	var out: Array[Vector3] = []
	var m: Vector3 = _plan.mouth.origin
	for j: int in range(-24, 25):
		for i: int in range(-24, 25):
			var x: float = m.x + i * 0.5
			var z: float = m.z + j * 0.5
			var p := Vector3(x, _tm.height_at(x, z), z)
			if _plan.sdf(p) < -1.0 and not is_nan(_tm.volume.density_at(p)) and _tm.volume.density_at(p) < -0.5:
				out.append(p)
	return out


func test_b_path_from_the_mouth_to_the_chamber_runs_under_the_hill() -> void:
	if _plan == null or not _plan.ok:
		fail_test("no plan")
		return
	await _bake_map()
	var into: Vector3 = Hill.into(_plan)
	var outside: Vector3 = _plan.mouth.origin - into * 6.0
	outside.y = _tm.height_at(outside.x, outside.z)
	var chamber: Vector3 = Hill.chamber_floor(_plan)
	var path: PackedVector3Array = _path(outside, chamber)
	assert_gt(path.size(), 1, "a path exists")
	if path.size() < 2:
		return
	gut.p("[nav] mouth->chamber %d points, ends %s (want %s)" % [path.size(), path[path.size() - 1], chamber])
	assert_lt(path[0].distance_to(outside), 1.5, "it starts outside the mouth")
	assert_lt(path[path.size() - 1].distance_to(chamber), 1.0, "it reaches the chamber floor")
	var under: int = 0
	var deepest: float = 0.0
	for p: Vector3 in path:
		var below: float = _tm.height_at(p.x, p.z) - p.y
		deepest = maxf(deepest, below)
		if below > 1.5:
			under += 1
	assert_gt(under, 0, "the path runs below the heightfield (deepest %.1f m)" % deepest)
	assert_gt(deepest, 3.0, "well below it")


func test_c_the_hillside_above_still_has_a_path() -> void:
	if _plan == null or not _plan.ok:
		fail_test("no plan")
		return
	await _bake_map()
	# Across the hill over the chamber, perpendicular to the tunnel.
	var chamber: Vector3 = Hill.chamber_floor(_plan)
	var into: Vector3 = Hill.into(_plan)
	var side := Vector3(-into.z, 0.0, into.x)
	var a: Vector3 = chamber - side * 12.0
	var b: Vector3 = chamber + side * 12.0
	a.y = _tm.height_at(a.x, a.z)
	b.y = _tm.height_at(b.x, b.z)
	var path: PackedVector3Array = _path(a, b)
	assert_gt(path.size(), 1, "a path over the hill")
	if path.size() < 2:
		return
	assert_lt(path[0].distance_to(a), 1.0, "from the hillside")
	assert_lt(path[path.size() - 1].distance_to(b), 1.0, "to the hillside across")
	var off: float = 0.0
	for p: Vector3 in path:
		off = maxf(off, absf(p.y - _tm.height_at(p.x, p.z)))
	assert_lt(off, 1.0, "and it stays on the surface (worst %.2f m off)" % off)


func test_d_no_polygon_on_the_heightfield_over_the_opening() -> void:
	if _plan == null or not _plan.ok:
		fail_test("no plan")
		return
	await _bake_map()
	var opening: Array[Vector3] = _opening_points()
	assert_gt(opening.size(), 0)
	var bad: int = 0
	var checked: int = 0
	for k: Vector2i in _meshes:
		var nm: NavigationMesh = _meshes[k]
		var verts: PackedVector3Array = nm.get_vertices()
		for pi: int in nm.get_polygon_count():
			var poly: PackedInt32Array = nm.get_polygon(pi)
			for vi: int in poly:
				var v: Vector3 = verts[vi]
				var h: float = _tm.height_at(v.x, v.z)
				# A vertex near the old surface where that surface floats in the cave's air.
				if _plan.sdf(Vector3(v.x, h, v.z)) < -1.0:
					checked += 1
					if absf(v.y - h) < 0.4:
						bad += 1
	gut.p("[nav] %d polygon vertices under the opening, %d on the old surface" % [checked, bad])
	assert_eq(bad, 0, "the heightfield over the opening is gone from the navmesh")
	# Vertices alone can miss a big polygon spanning the opening: no point of the map lies on the old
	# surface there either (the nearest is the tunnel floor, >= 1 m below).
	var lid: int = 0
	for p: Vector3 in opening:
		if NavigationServer3D.map_get_closest_point(_map, p).distance_to(p) < 0.4:
			lid += 1
	assert_eq(lid, 0, "no navmesh over the opening (%d of %d points)" % [lid, opening.size()])


## A walk along the hillside beside the cave, through the tile seam at x = 0 and the volume's
## borders (x = -32 where it starts, x = 32 and z = 32 where the heightfield takes the ground back):
## surface nets stop the volume's surface VOXEL / 2 short of a column's +X / +Z edge, and before the
## nav source closed that slit (and before the bake box took the tile's border) Recast left a gap
## there that no path crossed.
func test_e_paths_cross_the_tile_seams_and_the_volume_borders() -> void:
	if _plan == null or not _plan.ok:
		fail_test("no plan")
		return
	await _bake_map()
	var legs: Array = [[Vector2(-30.0, 5.0), Vector2(40.0, 5.0)], [Vector2(8.0, 26.0), Vector2(8.0, 40.0)]]
	for leg: Array in legs:
		var a := Vector3(leg[0].x, 0.0, leg[0].y)
		var b := Vector3(leg[1].x, 0.0, leg[1].y)
		a.y = _tm.height_at(a.x, a.z)
		b.y = _tm.height_at(b.x, b.z)
		var path: PackedVector3Array = _path(a, b)
		assert_gt(path.size(), 1, "a path %s -> %s" % [a, b])
		if path.size() < 2:
			continue
		assert_lt(path[path.size() - 1].distance_to(b), 1.0, "it gets across to %s (ends %s)" % [b, path[path.size() - 1]])
		var off: float = 0.0
		for p: Vector3 in path:
			off = maxf(off, absf(p.y - _tm.height_at(p.x, p.z)))
		assert_lt(off, 1.0, "on the surface all the way (worst %.2f m off)" % off)


func test_f_volume_events_queue_their_tiles() -> void:
	var nav := NavTiles.new()
	nav.enabled = false
	_hw.add_child(nav)
	nav.setup(_hw)
	var inside: Vector2i = NavTiles.tile_of(_plan.mouth.origin) if _plan != null else Vector2i.ZERO
	var far := Vector2i(inside.x + 3, inside.y)
	for k: Vector2i in [inside, far]:
		nav._tiles[k] = {"region": RID(), "baking": false}
	_tm.volume.chunks_applied.emit(AABB(_plan.mouth.origin - Vector3.ONE, Vector3.ONE * 2.0))
	assert_true(nav._dirty.has(inside), "chunks applied there queue its tile")
	assert_false(nav._dirty.has(far), "and not a tile 96 m off")
	nav._dirty.clear()
	_tm.caves_changed.emit(AABB(Vector3(far.x * NavTiles.TILE + 4.0, 0.0, far.y * NavTiles.TILE + 4.0), Vector3(2.0, 2.0, 2.0)))
	assert_true(nav._dirty.has(far), "a cave placed there queues it")
	assert_false(nav._dirty.has(inside))
	nav._dirty.clear()
	# A box just past a tile's edge still reaches its bake border.
	Events.terrain_modified.emit(AABB(Vector3((inside.x + 1) * NavTiles.TILE + 1.0, 0.0, inside.y * NavTiles.TILE + 10.0), Vector3(0.5, 0.5, 0.5)))
	assert_true(nav._dirty.has(inside), "an edit in the border queues the tile")
	nav._dirty.clear()
	# A tile whose volume is still building waits.
	assert_true(nav._ground_ready(inside), "built: ready")
	_tm.volume.edit_sphere(_plan.mouth.origin + Vector3.UP * 0.5, 1.0, 1.0)
	assert_false(nav._ground_ready(inside), "a re-mesh pending: wait")
	_tm.volume.flush()
	assert_true(nav._ground_ready(inside))
	nav.free()
