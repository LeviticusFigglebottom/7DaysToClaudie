extends GutTest
## TD-026 end to end on the real content: the Okafor farm framework placed in a small synthetic
## world. TerrainManager derives the farmhouse's cellar hole from the placement, cuts it out of
## the chunk meshes and collision it streams, and a player who drops through the clawed floor of
## Papa's room lands on the cellar floor.

const PLAYER_SCENE: String = "res://src/player/player.tscn"
const PAD_Y: float = 12.0
const FARM_ORIGIN := Vector3(-40.0, PAD_Y, -36.0)


func _farm_world() -> Array:
	var w := WorldDef.new()
	w.id = "holes_test"
	w.cols = 1
	w.rows = 1
	w.region_size = 256.0
	w.regions = {"t": {"id": "t", "cell": "A1"}}
	w.cells = {"A1": "t"}
	var rt := RegionTerrain.new()
	rt.region_id = "t"
	rt.rect = w.region_rect("t")
	rt.spacing = 1.0
	var n: int = 257
	rt.height = HeightField.create(rt.rect.position, 1.0, n, n, PAD_Y)
	rt.splat0.resize(n * n * 4)
	rt.splat1.resize(n * n * 4)
	rt.biome.resize(n * n)
	rt.vegmask.resize(n * n)
	rt.palette = TerrainComposer.DEFAULT_PALETTE
	rt.biome_ids = PackedStringArray(["meadow"])
	rt.placements = [{"kind": "framework", "def": "farm_okafor", "id": "okafor_farm", "origin": [FARM_ORIGIN.x, FARM_ORIGIN.y, FARM_ORIGIN.z],
		"rotation": 0.0, "size": [72, 62]}]
	return [w, rt]


func _house() -> Dictionary:
	for e: Dictionary in TerrainHoles.placed_pois(_farm_world()[1].placements):
		if (e["def"] as PoiDef).id == &"okafor_farmhouse":
			return e
	return {}


func test_the_farmhouse_cellar_is_cut_from_the_streamed_terrain() -> void:
	if not Content.has_def(&"framework", &"farm_okafor") or not Content.has_def(&"poi", &"okafor_farmhouse"):
		pending("farm content missing")
		return
	var wr: Array = _farm_world()
	var tm := TerrainManager.new()
	add_child_autofree(tm)
	tm.setup(wr[0], {"t": wr[1]}, {})
	assert_eq(tm.holes.holes.size(), 1, "one placed POI has a cellar")
	var h: TerrainHoles.Hole = tm.holes.holes[0]
	assert_eq(String(h.id), "okafor_farm/house")
	assert_almost_eq(h.floor_y, PAD_Y + 0.6 - 3.0, 1e-3, "cellar floor under the porch-height ground floor")
	var area: float = 0.0
	for poly: PackedVector2Array in h.pieces:
		area += TerrainHoles.signed_area(poly)
	assert_almost_eq(area, 24.0, 1e-3, "the 24 cellar cells, nothing else")
	# Stream the chunks over the cellar: no ground left inside it, collision is the exact trimesh.
	var lo: Vector2i = TerrainManager.chunk_of(h.bounds.position.x, h.bounds.position.y)
	var hi: Vector2i = TerrainManager.chunk_of(h.bounds.end.x, h.bounds.end.y)
	var t0: int = Time.get_ticks_usec()
	for cz: int in range(lo.y, hi.y + 1):
		for cx: int in range(lo.x, hi.x + 1):
			var key := Vector2i(cx, cz)
			var ch := TerrainManager.Chunk.new()
			ch.key = key
			tm._chunks[key] = ch
			tm._request_mesh(key, 0, true)
			tm._set_collision(ch, true)
			assert_true((ch.body.get_child(0) as CollisionShape3D).shape is ConcavePolygonShape3D, "chunk %s collides through a trimesh" % key)
			var arr: Array = (ch.mesh_instance.mesh as ArrayMesh).surface_get_arrays(0)
			var verts: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
			var idx: PackedInt32Array = arr[Mesh.ARRAY_INDEX]
			var inside: int = 0
			for t: int in range(0, idx.size(), 3):
				var m: Vector3 = (verts[idx[t]] + verts[idx[t + 1]] + verts[idx[t + 2]]) / 3.0 + ch.mesh_instance.position
				if tm.holes.signed_distance(m.x, m.z) < -1e-3:
					inside += 1
			assert_eq(inside, 0, "chunk %s keeps no ground over the cellar" % key)
	gut.p("cellar chunks meshed + collided in %d ms" % ((Time.get_ticks_usec() - t0) / 1000))
	# Queries.
	var c: Vector2 = h.bounds.get_center()
	var cell_center: Vector3 = (_house()["xf"] as Transform3D) * Vector3(7.0 + 6.5, 0.0, 5.0 + 1.5)
	assert_true(tm.in_cellar(cell_center.x, cell_center.z))
	assert_almost_eq(tm.ground_below(Vector3(cell_center.x, PAD_Y - 1.0, cell_center.z)), h.floor_y, 1e-3)
	assert_almost_eq(tm.ground_below(Vector3(cell_center.x, PAD_Y + 2.0, cell_center.z)), PAD_Y, 1e-3, "above ground: the surface")
	assert_false(tm.in_cellar(c.x + 40.0, c.y))


func _settle(frames: int) -> void:
	for i: int in frames:
		await get_tree().physics_frame


func test_dropping_through_papas_floor_lands_in_the_cellar() -> void:
	if not Content.has_def(&"framework", &"farm_okafor") or not Content.has_def(&"poi", &"okafor_farmhouse"):
		pending("farm content missing")
		return
	var wr: Array = _farm_world()
	var tm := TerrainManager.new()
	add_child_autofree(tm)
	tm.setup(wr[0], {"t": wr[1]}, {})
	var house: Dictionary = _house()
	var xf: Transform3D = house["xf"]
	var inst: PoiInstance = PoiBuilder.build(PoiLayout.compile(house["def"]), &"okafor_farm/house")
	add_child_autofree(inst)
	inst.global_transform = xf
	var h: TerrainHoles.Hole = tm.holes.holes[0]
	var lo: Vector2i = TerrainManager.chunk_of(h.bounds.position.x - 8.0, h.bounds.position.y - 8.0)
	var hi: Vector2i = TerrainManager.chunk_of(h.bounds.end.x + 8.0, h.bounds.end.y + 8.0)
	for cz: int in range(lo.y, hi.y + 1):
		for cx: int in range(lo.x, hi.x + 1):
			var ch := TerrainManager.Chunk.new()
			ch.key = Vector2i(cx, cz)
			tm._chunks[ch.key] = ch
			tm._set_collision(ch, true)
	var player: Player = (load(PLAYER_SCENE) as PackedScene).instantiate() as Player
	player.input_enabled = false
	add_child_autofree(player)
	player.bind_state(PlayerState.new())
	await _settle(2)
	# Papa's room is level 0 cell (7, 1); the plan sits at origin [7, 5] in the footprint.
	var hole_top: Vector3 = xf * Vector3(7.0 + 7.5, 0.6 + 0.3, 5.0 + 1.5)
	player.global_position = hole_top
	player.velocity = Vector3.ZERO
	await _settle(120)
	# The torn-up boards lie where he came down (a 12 cm plank pile).
	assert_almost_eq(player.global_position.y, h.floor_y, 0.2, "through the broken floor onto the cellar floor")
	var standing: Vector3 = xf * Vector3(7.0 + 11.4, 0.6 + 0.3, 5.0 + 1.9)
	player.global_position = standing
	player.velocity = Vector3.ZERO
	await _settle(60)
	assert_almost_eq(player.global_position.y, PAD_Y + 0.6, 0.1, "a sound floor next to it holds")


# --- Consumers of ground_below(): loose items, GameWorld (spawn drop, Hollowed, spore puddles) ----

## The world a LooseItems node reads: the player it measures distances from and the terrain.
class StubWorld:
	extends Node3D
	var player: Node3D
	var terrain: TerrainManager


func _farm_terrain() -> TerrainManager:
	var wr: Array = _farm_world()
	var tm := TerrainManager.new()
	add_child_autofree(tm)
	tm.setup(wr[0], {"t": wr[1]}, {})
	return tm


## A point on the root-cellar floor (plan cell (6, 1), level -1).
func _cellar_floor_point(tm: TerrainManager) -> Vector3:
	var c: Vector3 = (_house()["xf"] as Transform3D) * Vector3(7.0 + 6.5, 0.0, 5.0 + 1.5)
	return Vector3(c.x, tm.holes.holes[0].floor_y, c.z)


func _frozen_drop(pos: Vector3) -> RigidBody3D:
	var b := RigidBody3D.new()
	b.freeze = true
	b.add_to_group(&"item_drops")
	add_child_autofree(b)
	b.global_position = pos
	return b


func test_loose_items_in_a_cellar_stay_on_its_floor() -> void:
	if not Content.has_def(&"framework", &"farm_okafor") or not Content.has_def(&"poi", &"okafor_farmhouse"):
		pending("farm content missing")
		return
	var tm: TerrainManager = _farm_terrain()
	var w := StubWorld.new()
	w.terrain = tm
	w.player = Node3D.new()
	w.add_child(w.player)
	add_child_autofree(w)
	var li := LooseItems.new()
	add_child_autofree(li)
	li.world = w
	var at: Vector3 = _cellar_floor_point(tm)
	w.player.global_position = at
	var resting: RigidBody3D = _frozen_drop(at + Vector3.UP * 0.1)
	var sunk: RigidBody3D = _frozen_drop(at + Vector3(1.0, -2.0, 0.0))
	var buried: RigidBody3D = _frozen_drop(Vector3(at.x + 30.0, PAD_Y - 2.0, at.z))
	li._physics_process(LooseItems.CHECK_INTERVAL)
	assert_almost_eq(resting.global_position.y, at.y + 0.1, 1e-3, "a drop on the cellar floor stays down there")
	assert_almost_eq(sunk.global_position.y, at.y + 0.6, 1e-3, "one that slipped through the cellar floor comes back into the cellar")
	assert_almost_eq(buried.global_position.y, PAD_Y + 0.6, 1e-3, "away from a cellar: lifted onto the surface, as before")


func test_game_world_ground_below_is_the_cellar_floor_down_there() -> void:
	if not Content.has_def(&"framework", &"farm_okafor") or not Content.has_def(&"poi", &"okafor_farmhouse"):
		pending("farm content missing")
		return
	var tm: TerrainManager = _farm_terrain()
	var gw := GameWorld.new()
	autofree(gw)
	gw.terrain = tm
	var at: Vector3 = _cellar_floor_point(tm)
	# What a save loaded in the cellar (GameWorld._finish_spawn), a Hollowed's fall check and a
	# spore splash measure against.
	assert_almost_eq(gw.ground_below(at), at.y, 1e-3, "down in the cellar: its floor")
	assert_almost_eq(gw.ground_below(at + Vector3.UP * 2.7), at.y, 1e-3, "up under the cellar ceiling: still its floor")
	assert_almost_eq(gw.ground_below(at + Vector3.UP * 3.0), PAD_Y, 1e-3, "on the ground floor above it: the surface")
	assert_almost_eq(gw.height_at(at.x, at.z), PAD_Y, 1e-3, "height_at() stays the surface")
	assert_almost_eq(gw.ground_below(Vector3(at.x + 30.0, PAD_Y - 2.0, at.z)), PAD_Y, 1e-3, "no cellar: the surface")
