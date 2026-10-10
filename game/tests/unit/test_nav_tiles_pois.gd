extends GutTest
## NavTiles' source for a tile with a building on it (TD-340): the building's colliders join the
## terrain in world space. Parsed straight into the tile's source, the parse cleared the terrain and
## kept the building relative to its own root, so every tile with a POI on it baked empty and the
## Hollowed and Ezra had no mesh across a yard.


## A flat world at y = 0 with one "POI": a 4 x 2 x 4 m box collider in a shell placed in tile (1, 1).
class FlatWorld:
	extends Node3D
	var pois: Node

	func height_at(_x: float, _z: float) -> float:
		return 0.0


class Pois:
	extends Node
	var roots: Array = []

	func nav_roots_in_rect(_r: Rect2) -> Array:
		return roots


var _world: FlatWorld
var _nav: NavTiles


func before_each() -> void:
	_world = FlatWorld.new()
	add_child(_world)
	var pois := Pois.new()
	_world.add_child(pois)
	_world.pois = pois
	var shell := Node3D.new()
	_world.add_child(shell)
	shell.global_position = Vector3(44.0, 0.0, 44.0)
	var body := StaticBody3D.new()
	body.collision_layer = 1
	shell.add_child(body)
	var cs := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(4.0, 2.0, 4.0)
	cs.shape = box
	cs.position = Vector3(0.0, 1.0, 0.0)
	body.add_child(cs)
	pois.roots = [shell]
	_nav = NavTiles.new()
	_nav.enabled = false
	_world.add_child(_nav)
	_nav.world = _world


func after_each() -> void:
	_world.free()


func test_building_joins_the_terrain_in_world_space() -> void:
	var inputs: Array = _nav.bake_inputs(Vector2i(1, 1))
	var src: NavigationMeshSourceGeometryData3D = inputs[1]
	var b: AABB = src.get_bounds()
	# The terrain's faces are still there (the whole tile and its border)...
	assert_lt(b.position.x, 32.0 - NavTiles.BORDER + 0.01, "terrain kept: %s" % b)
	assert_gt(b.end.x, 64.0 + NavTiles.BORDER - 0.01, "terrain kept: %s" % b)
	# ...and the box stands where the shell is, not at the origin.
	assert_almost_eq(b.end.y, 2.0, 0.01, "the box's top is the source's highest point: %s" % b)
	var top_at_box: bool = false
	var v: PackedFloat32Array = src.get_vertices()
	for i: int in range(0, v.size(), 3):
		if is_equal_approx(v[i + 1], 2.0):
			top_at_box = top_at_box or Vector2(v[i], v[i + 2]).distance_to(Vector2(44.0, 44.0)) < 3.0
			assert_true(Vector2(v[i], v[i + 2]).distance_to(Vector2(44.0, 44.0)) < 3.0, "box vertex at (%.1f, %.1f)" % [v[i], v[i + 2]])
	assert_true(top_at_box, "the box's top is around its shell")


func test_tile_with_a_building_bakes_its_ground() -> void:
	var inputs: Array = _nav.bake_inputs(Vector2i(1, 1))
	var nm: NavigationMesh = inputs[0]
	NavigationServer3D.bake_from_source_geometry_data(nm, inputs[1])
	assert_gt(nm.get_polygon_count(), 0, "the tile has a navmesh")
	# Ground across the tile, and the box's top where the shell stands (Recast walks onto it).
	var lo := Vector3(INF, INF, INF)
	var hi := Vector3(-INF, -INF, -INF)
	var on_box: bool = false
	for p: Vector3 in nm.get_vertices():
		if p.y < 1.0:
			lo = lo.min(p)
			hi = hi.max(p)
		elif p.y > 1.9 and absf(p.x - 44.0) < 2.0 and absf(p.z - 44.0) < 2.0:
			on_box = true
	assert_lt(lo.x, 33.0, "ground reaches the tile's west edge")
	assert_gt(hi.x, 63.0, "ground reaches the tile's east edge")
	assert_true(on_box, "the box's top is on the mesh where the shell stands")
