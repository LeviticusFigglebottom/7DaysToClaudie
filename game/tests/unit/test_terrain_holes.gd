extends GutTest
## POI cellar holes in the heightmap terrain (TD-026): the hole model (cells -> world pieces,
## containment, distance), exact cutting of render chunks (every LOD step, skirts) and of the
## collision/navigation faces, the SDF volume carve, and real physics: a body dropped in the
## cellar of a built POI stands on the cellar floor, not on the terrain above it.

const PLAYER_SCENE: String = "res://src/player/player.tscn"
## Placement used throughout: a turned building on a pad at y = 5.
const PAD_Y: float = 5.0
const YAW_DEG: float = 30.0


## 6 x 5 ground floor over an L-shaped cellar (10 cells) whose stair rises to the hall.
func _cellar_def() -> PoiDef:
	var raw: Dictionary = {
		"id": "t_cellar", "name": "Test Cellar", "tier": 1, "footprint": [10, 10], "origin": [2, 2],
		"style": {"floor_height": 0.6, "roof": {"type": "flat"}},
		"levels": [
			{"level": 0, "plan": ["HHKKKK", "HHKKKK", "HHKKKK", "HHKKKK", "HHKKKK"],
				"rooms": {"H": {"type": "hallway"}, "K": {"type": "kitchen"}}},
			{"level": -1, "plan": ["CCC", "CCC", "CC.", "C..", "C.."], "rooms": {"C": {"type": "cellar"}}}],
		"stairs": [{"level": -1, "at": [0, 4], "dir": "N"}],
		"openings": [{"id": "front", "at": [3, 4], "side": "S", "type": "door", "state": "open"}],
		"route": [{"at": [3, 6]}, {"at": [3, 3]}],
	}
	var d := PoiDef.new()
	assert_eq(d.parse(raw, &"poi", "test"), PackedStringArray())
	return d


func _xf() -> Transform3D:
	return Transform3D(Basis(Vector3.UP, -deg_to_rad(YAW_DEG)), Vector3(10.3, PAD_Y, -3.7))


func _holes() -> TerrainHoles:
	var th := TerrainHoles.new()
	th.add_poi(_cellar_def(), &"test/cellar", _xf())
	return th


## World XZ of a POI-local plan point (origin offset [2, 2]).
func _w(lx: float, lz: float) -> Vector2:
	var p: Vector3 = _xf() * Vector3(2.0 + lx, 0.0, 2.0 + lz)
	return Vector2(p.x, p.z)


func _plane(x: float, z: float) -> float:
	return PAD_Y + 0.08 * x - 0.05 * z


# --- Hole model -----------------------------------------------------------------------------------

func test_merge_cells_covers_each_cell_once() -> void:
	var cells: Array[Vector2i] = [Vector2i(0, 0), Vector2i(1, 0), Vector2i(2, 0), Vector2i(0, 1), Vector2i(1, 1), Vector2i(2, 1),
		Vector2i(0, 2), Vector2i(1, 2), Vector2i(0, 3), Vector2i(4, 3)]
	var count: Dictionary = {}
	for r: Rect2i in TerrainHoles.merge_cells(cells):
		for y: int in range(r.position.y, r.end.y):
			for x: int in range(r.position.x, r.end.x):
				count[Vector2i(x, y)] = int(count.get(Vector2i(x, y), 0)) + 1
	assert_eq(count.size(), cells.size(), "every cell covered, nothing else")
	for c: Vector2i in cells:
		assert_eq(int(count.get(c, 0)), 1, "cell %s covered once" % c)


func test_hole_follows_the_cellar_cells() -> void:
	var th: TerrainHoles = _holes()
	assert_eq(th.holes.size(), 1)
	var h: TerrainHoles.Hole = th.holes[0]
	assert_almost_eq(h.top_y, PAD_Y, 1e-4)
	assert_almost_eq(h.floor_y, PAD_Y + 0.6 - 3.0, 1e-4, "cellar floor = pad + level_y(-1)")
	assert_almost_eq(h.ceiling_y, PAD_Y + 0.6 - TerrainHoles.SLAB, 1e-4, "its ceiling: the underside of the ground floor")
	for c: Vector2i in [Vector2i(0, 0), Vector2i(2, 1), Vector2i(1, 2), Vector2i(0, 4)]:
		var p: Vector2 = _w(c.x + 0.5, c.y + 0.5)
		assert_true(th.contains(p.x, p.y), "cellar cell %s is cut" % c)
	for c2: Vector2i in [Vector2i(3, 0), Vector2i(2, 2), Vector2i(1, 4), Vector2i(5, 4)]:
		var q: Vector2 = _w(c2.x + 0.5, c2.y + 0.5)
		assert_false(th.contains(q.x, q.y), "ground-floor-only cell %s keeps its terrain" % c2)
	# Distances: a corner cell's centre is 0.5 m inside; 1 m east of the cellar is 1 m outside.
	var inside: Vector2 = _w(0.5, 0.5)
	assert_almost_eq(th.signed_distance(inside.x, inside.y), -0.5, 1e-3)
	var outside: Vector2 = _w(4.0, 0.5)
	assert_almost_eq(th.signed_distance(outside.x, outside.y), 1.0, 1e-3)
	assert_true(th.intersects(Rect2(inside - Vector2.ONE, Vector2(2, 2))))
	assert_false(th.intersects(Rect2(200, 200, 10, 10)))


func test_placed_pois_match_the_poi_manager_transform() -> void:
	var defs: Array = Content.all(&"poi")
	if defs.is_empty():
		pending("no POIs")
		return
	var pd: PoiDef = defs[0]
	var pl: Dictionary = {"kind": "poi", "def": String(pd.id), "id": "x", "origin": [12.5, 3.0, -7.0], "rotation": 73.0, "size": [pd.footprint.x, pd.footprint.y]}
	var e: Array[Dictionary] = TerrainHoles.placed_pois([pl])
	assert_eq(e.size(), 1)
	var a: Transform3D = e[0]["xf"]
	var b: Transform3D = PoiManager._placement_xf(pl)
	assert_true(a.is_equal_approx(b), "same transform as the building node")


func test_subtract_convex_conserves_area() -> void:
	var tri := PackedVector2Array([Vector2(0, 0), Vector2(4, 0), Vector2(0, 4)])
	var sq := PackedVector2Array([Vector2(1, 1), Vector2(2, 1), Vector2(2, 2), Vector2(1, 2)])
	var area: float = 0.0
	for p: PackedVector2Array in TerrainHoles.cut(tri, [sq]):
		assert_gt(TerrainHoles.signed_area(p), 0.0, "pieces keep the winding")
		area += TerrainHoles.signed_area(p)
	assert_almost_eq(area, 8.0 - 1.0, 1e-4, "triangle minus the square inside it")
	assert_eq(TerrainHoles.cut(tri, [PackedVector2Array([Vector2(-1, -1), Vector2(5, -1), Vector2(5, 5), Vector2(-1, 5)])]).size(), 0, "fully covered")


# --- Mesh cutting ---------------------------------------------------------------------------------

## XZ-projected area of front faces, and whether any face centroid lies inside the hole.
func _faces_stats(verts: PackedVector3Array, idx: PackedInt32Array, origin: Vector2, th: TerrainHoles) -> Dictionary:
	var area: float = 0.0
	var inside: int = 0
	var back: int = 0
	var off_plane: int = 0
	for t: int in range(0, idx.size(), 3):
		var a: Vector3 = verts[idx[t]]
		var b: Vector3 = verts[idx[t + 1]]
		var c: Vector3 = verts[idx[t + 2]]
		var s: float = TerrainHoles.signed_area(PackedVector2Array([Vector2(a.x, a.z), Vector2(b.x, b.z), Vector2(c.x, c.z)]))
		if absf(s) < 1e-7:
			continue  # skirt (vertical)
		if s < 0.0:
			back += 1
		area += s
		var m: Vector3 = (a + b + c) / 3.0
		if th.contains(origin.x + m.x, origin.y + m.z) and th.signed_distance(origin.x + m.x, origin.y + m.z) < -1e-3:
			inside += 1
		for v: Vector3 in [a, b, c]:
			if absf(v.y - _plane(origin.x + v.x, origin.y + v.z)) > 2e-3:
				off_plane += 1
	return {"area": area, "inside": inside, "back": back, "off_plane": off_plane}


func test_chunk_mesh_is_cut_exactly_at_every_lod() -> void:
	var th: TerrainHoles = _holes()
	var origin := Vector2(0.0, -16.0)
	var size: float = 32.0
	var cut: Array[PackedVector2Array] = th.pieces_in(Rect2(origin, Vector2(size, size)))
	assert_gt(cut.size(), 0, "the chunk overlaps the cellar")
	for step: float in [1.0, 2.0, 4.0]:
		var mesh: ArrayMesh = TerrainMesher.build_chunk(origin, size, step, _plane, 0.0, Callable(), Callable(), cut)
		var arr: Array = mesh.surface_get_arrays(0)
		var st: Dictionary = _faces_stats(arr[Mesh.ARRAY_VERTEX], arr[Mesh.ARRAY_INDEX], origin, th)
		assert_almost_eq(float(st["area"]), size * size - 10.0, 0.01, "step %.0f: chunk minus the 10 m2 cellar" % step)
		assert_eq(int(st["inside"]), 0, "step %.0f: no ground left inside the cellar" % step)
		assert_eq(int(st["back"]), 0, "step %.0f: every face still faces up" % step)
		assert_eq(int(st["off_plane"]), 0, "step %.0f: cut vertices stay on the original surface" % step)
	# Without cutters the same chunk is whole.
	var whole: ArrayMesh = TerrainMesher.build_chunk(origin, size, 1.0, _plane, 0.0)
	var arr2: Array = whole.surface_get_arrays(0)
	assert_almost_eq(float(_faces_stats(arr2[Mesh.ARRAY_VERTEX], arr2[Mesh.ARRAY_INDEX], origin, th)["area"]), size * size, 0.01)


func test_skirt_does_not_hang_into_the_cellar() -> void:
	var th: TerrainHoles = _holes()
	# A chunk border through the middle of the cellar.
	var mid: Vector2 = _w(1.5, 1.5)
	var origin := Vector2(floor(mid.x) - 16.0, floor(mid.y) - 7.0)
	var cut: Array[PackedVector2Array] = th.pieces_in(Rect2(origin, Vector2(16, 16)))
	assert_gt(cut.size(), 0)
	var mesh: ArrayMesh = TerrainMesher.build_chunk(origin, 16.0, 1.0, _plane, 1.0, Callable(), Callable(), cut)
	var arr: Array = mesh.surface_get_arrays(0)
	var verts: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
	var idx: PackedInt32Array = arr[Mesh.ARRAY_INDEX]
	var skirts: int = 0
	var bad: int = 0
	for t: int in range(0, idx.size(), 3):
		var a: Vector3 = verts[idx[t]]
		var b: Vector3 = verts[idx[t + 1]]
		var c: Vector3 = verts[idx[t + 2]]
		var s: float = TerrainHoles.signed_area(PackedVector2Array([Vector2(a.x, a.z), Vector2(b.x, b.z), Vector2(c.x, c.z)]))
		if absf(s) > 1e-7:
			continue
		skirts += 1
		var m: Vector3 = (a + b + c) / 3.0
		if th.signed_distance(origin.x + m.x, origin.y + m.z) < -1e-3:
			bad += 1
	assert_gt(skirts, 0, "the chunk still has its skirt")
	assert_eq(bad, 0, "no skirt strip inside the cellar")


func test_surface_faces_cut_like_the_render_mesh() -> void:
	var th: TerrainHoles = _holes()
	var origin := Vector2(0.0, -16.0)
	var faces: PackedVector3Array = TerrainMesher.surface_faces(origin, 32.0, 1.0, _plane, Callable(), th.pieces_in(Rect2(origin, Vector2(32, 32))))
	var idx := PackedInt32Array()
	for i: int in faces.size():
		idx.append(i)
	var st: Dictionary = _faces_stats(faces, idx, origin, th)
	assert_almost_eq(float(st["area"]), 32.0 * 32.0 - 10.0, 0.01)
	assert_eq(int(st["inside"]), 0)
	assert_eq(int(st["back"]), 0)


# --- SDF volume -----------------------------------------------------------------------------------

class HoleTerrain:
	extends Node
	var textures: Variant = null
	var holes: TerrainHoles

	func base_height_at(_x: float, _z: float) -> float:
		return PAD_Y


func test_volume_handoff_keeps_the_cellar_open() -> void:
	var t := HoleTerrain.new()
	t.holes = _holes()
	add_child_autofree(t)
	var vol := VolumeTerrain.new()
	t.add_child(vol)
	vol.setup(t)
	var inside: Vector2 = _w(1.5, 0.5)
	vol.activate_column(VolumeTerrain.column_of(inside.x, inside.y), PAD_Y - 8.0)
	var floor_y: float = t.holes.holes[0].floor_y
	var probe := func(x: float, y: float, z: float) -> float:
		var key: Vector3i = VolumeTerrain.chunk_of(Vector3(x, y, z))
		var c: VolumeTerrain.VChunk = vol.chunks.get(key)
		var o := Vector3(key.x, key.y, key.z) * VolumeTerrain.SIZE
		var l: Vector3i = Vector3i(((Vector3(x, y, z) - o) / VolumeTerrain.VOXEL).floor())
		return c.density[SurfaceNets.at(VolumeTerrain.N, l.x, l.y, l.z)]
	assert_lt(float(probe.call(inside.x, floor_y + 1.0, inside.y)), 0.0, "air inside the cellar")
	assert_gt(float(probe.call(inside.x, floor_y - 1.0, inside.y)), 0.0, "solid under the cellar floor")
	var away: Vector2 = _w(6.0, 0.5)
	assert_gt(float(probe.call(away.x, floor_y + 1.0, away.y)), 0.0, "solid ground beside it")
	vol.flush()


# --- Real physics ---------------------------------------------------------------------------------

func _settle(frames: int) -> void:
	for i: int in frames:
		await get_tree().physics_frame


func test_a_body_stands_on_the_cellar_floor() -> void:
	var def: PoiDef = _cellar_def()
	var th: TerrainHoles = _holes()
	var inst: PoiInstance = PoiBuilder.build(PoiLayout.compile(def), &"test/cellar")
	add_child_autofree(inst)
	inst.global_transform = _xf()
	# Flat terrain at the pad height, cut over the cellar, as TerrainManager builds it.
	var origin := Vector2(-8.0, -24.0)
	var body := StaticBody3D.new()
	body.collision_layer = 1
	var cs := CollisionShape3D.new()
	var shape := ConcavePolygonShape3D.new()
	shape.backface_collision = true
	shape.set_faces(TerrainMesher.surface_faces(origin, 48.0, 1.0, func(_x: float, _z: float) -> float: return PAD_Y, Callable(), th.pieces_in(Rect2(origin, Vector2(48, 48)))))
	cs.shape = shape
	body.add_child(cs)
	add_child_autofree(body)
	body.global_position = Vector3(origin.x, 0.0, origin.y)
	var player: Player = (load(PLAYER_SCENE) as PackedScene).instantiate() as Player
	player.input_enabled = false
	add_child_autofree(player)
	player.bind_state(PlayerState.new())
	await _settle(2)
	var floor_y: float = th.holes[0].floor_y
	# Into the open stairwell from the hall: it only goes down if the terrain under the house
	# is cut (uncut, the ground at the pad height would catch the player 0.6 m below the hall).
	var well: Vector2 = _w(0.5, 2.5)
	player.global_position = Vector3(well.x, PAD_Y + 0.9, well.y)
	player.velocity = Vector3.ZERO
	await _settle(90)
	var ramp_y: float = floor_y + 3.0 * (5.0 - 2.5) / 4.0
	assert_almost_eq(player.global_position.y, ramp_y, 0.3, "lands on the cellar stairs, below the pad")
	assert_lt(player.global_position.y, PAD_Y - 0.2, "under the old ground level")
	# On the cellar floor.
	var cell: Vector2 = _w(1.5, 0.5)
	player.global_position = Vector3(cell.x, floor_y + 0.3, cell.y)
	player.velocity = Vector3.ZERO
	await _settle(60)
	assert_almost_eq(player.global_position.y, floor_y, 0.08, "stands on the cellar floor, 2.4 m under the pad")
	# Out in the yard the cut terrain still holds the player up at the pad height.
	var yard: Vector2 = _w(-2.0, 2.5)
	player.global_position = Vector3(yard.x, PAD_Y + 0.6, yard.y)
	player.velocity = Vector3.ZERO
	await _settle(90)
	assert_almost_eq(player.global_position.y, PAD_Y, 0.08, "stands on the terrain beside the house")
