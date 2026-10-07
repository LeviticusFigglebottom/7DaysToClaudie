class_name NavTiles
extends Node
## Outdoor navigation mesh, baked in 32 m tiles around the player on worker threads and rebaked
## where the world changes (structures built or broken, terrain dug, trees felled). Source
## geometry is assembled directly — terrain faces from the heightfield, structures/trees/boulders
## as projected obstructions, POI buildings parsed from their colliders — so baking never walks
## the whole scene. Tiles bake with a border so neighbours stitch on the navigation map.

const TILE: float = 32.0
const RADIUS_TILES: int = 2
const BORDER: float = 2.0
const TERRAIN_STEP: float = 1.0
const REBAKE_DELAY: float = 1.0

var world: Node
var _tiles: Dictionary = {}
var _dirty: Dictionary = {}
var _center := Vector2i(999999, 999999)
var _t: float = 0.0
var _busy: int = 0
var enabled: bool = true


func setup(w: Node) -> void:
	world = w
	Events.structure_placed.connect(func(_id: StringName, _d: StringName, pos: Vector3) -> void: _mark(pos))
	Events.structure_destroyed.connect(func(_id: StringName, _d: StringName, pos: Vector3) -> void: _mark(pos))
	Events.tree_felled.connect(func(_id: StringName, pos: Vector3, _by: StringName) -> void: _mark(pos))
	Events.terrain_modified.connect(func(aabb: AABB) -> void: _mark(aabb.get_center()))
	# A streamed world (ADR-0038): tiles baked over a region's coarse ground are baked again once its
	# 1 m terrain attaches.
	var tm: TerrainManager = w.get(&"terrain") as TerrainManager if w != null else null
	if tm != null:
		tm.region_attached.connect(_on_region_attached)


func _on_region_attached(rid: String) -> void:
	var rt: RegionTerrain = (world.get(&"terrain") as TerrainManager).regions.get(rid)
	if rt == null:
		return
	for k: Vector2i in _tiles.keys():
		if rt.rect.intersects(Rect2(k.x * TILE, k.y * TILE, TILE, TILE)):
			_dirty[k] = REBAKE_DELAY


## Whether a tile's ground is the 1 m terrain (always outside a streamed world): baking over a
## region's coarse heights would give the Hollowed a mesh 16 m out of true.
func _ground_ready(k: Vector2i) -> bool:
	var tm: TerrainManager = world.get(&"terrain") as TerrainManager
	if tm == null or tm.streamer == null:
		return true
	return tm.region_terrain_at((k.x + 0.5) * TILE, (k.y + 0.5) * TILE) != null


func _exit_tree() -> void:
	for k: Vector2i in _tiles.keys():
		_free_tile(k)


static func tile_of(p: Vector3) -> Vector2i:
	return Vector2i(int(floor(p.x / TILE)), int(floor(p.z / TILE)))


## Something walkable changed at `pos` outside the usual events (a POI weak floor gave way,
## ADR-0022): rebake the tiles around it once REBAKE_DELAY has passed (by then the collider the
## change disabled is gone from the physics state the bake parses).
func mark_dirty(pos: Vector3) -> void:
	_mark(pos)


## Whether a tile around `pos` is waiting for a rebake (tests, debug).
func is_dirty(pos: Vector3) -> bool:
	return _dirty.has(tile_of(pos))


func _mark(pos: Vector3) -> void:
	var t: Vector2i = tile_of(pos)
	for dz: int in range(-1, 2):
		for dx: int in range(-1, 2):
			var k := Vector2i(t.x + dx, t.y + dz)
			if _tiles.has(k):
				_dirty[k] = REBAKE_DELAY


func _process(delta: float) -> void:
	if not enabled or world == null or world.player == null or not world.is_ready:
		return
	_t += delta
	for k: Vector2i in _dirty.keys():
		_dirty[k] = float(_dirty[k]) - delta
		if float(_dirty[k]) <= 0.0 and _busy < 2:
			if not _ground_ready(k):
				_dirty[k] = REBAKE_DELAY
				continue
			_dirty.erase(k)
			_bake(k)
	if _t < 0.5:
		return
	_t = 0.0
	var c: Vector2i = tile_of(world.player.global_position)
	if c == _center:
		return
	_center = c
	for k: Vector2i in _tiles.keys():
		if absi(k.x - c.x) > RADIUS_TILES + 1 or absi(k.y - c.y) > RADIUS_TILES + 1:
			_free_tile(k)
	var order: Array[Vector2i] = []
	for dz: int in range(-RADIUS_TILES, RADIUS_TILES + 1):
		for dx: int in range(-RADIUS_TILES, RADIUS_TILES + 1):
			var k := Vector2i(c.x + dx, c.y + dz)
			if not _tiles.has(k):
				order.append(k)
	order.sort_custom(func(a: Vector2i, b: Vector2i) -> bool: return (a - c).length_squared() < (b - c).length_squared())
	for k: Vector2i in order:
		_tiles[k] = {"region": RID(), "baking": false}
		_dirty[k] = 0.0


func _free_tile(k: Vector2i) -> void:
	var t: Dictionary = _tiles[k]
	if (t["region"] as RID).is_valid():
		NavigationServer3D.free_rid(t["region"])
	_tiles.erase(k)
	_dirty.erase(k)


func _bake(k: Vector2i) -> void:
	if not _tiles.has(k):
		return
	var nm := NavigationMesh.new()
	nm.agent_radius = 0.5
	nm.agent_height = 1.75
	nm.agent_max_climb = 0.5
	nm.agent_max_slope = 46.0
	nm.cell_size = 0.25
	nm.cell_height = 0.25
	nm.border_size = BORDER
	nm.region_min_size = 4.0
	# The bake is clipped to the tile itself; border_size lets Recast see the geometry around it so
	# neighbouring tiles' edges line up exactly (no overlap) and stitch on the map.
	nm.filter_baking_aabb = AABB(Vector3(k.x * TILE, -1000.0, k.y * TILE), Vector3(TILE, 3000.0, TILE))
	var src := NavigationMeshSourceGeometryData3D.new()
	_add_terrain(src, k)
	_add_bridges(src, k)
	_add_obstructions(src, k)
	_add_pois(nm, src, k)
	_busy += 1
	(_tiles[k] as Dictionary)["baking"] = true
	NavigationServer3D.bake_from_source_geometry_data_async(nm, src, _on_baked.bind(k, nm))


func _on_baked(k: Vector2i, nm: NavigationMesh) -> void:
	_busy -= 1
	if not _tiles.has(k):
		return
	var t: Dictionary = _tiles[k]
	t["baking"] = false
	if not (t["region"] as RID).is_valid():
		var r: RID = NavigationServer3D.region_create()
		NavigationServer3D.region_set_map(r, world.get_world_3d().navigation_map)
		t["region"] = r
	NavigationServer3D.region_set_navigation_mesh(t["region"], nm)


func _add_terrain(src: NavigationMeshSourceGeometryData3D, k: Vector2i) -> void:
	var x0: float = k.x * TILE - BORDER - TERRAIN_STEP
	var z0: float = k.y * TILE - BORDER - TERRAIN_STEP
	var count: int = int((TILE + BORDER * 2.0) / TERRAIN_STEP) + 2
	# POI cellars (TD-026): the terrain is cut away over them, exactly as the collision is, so
	# Recast walks the cellar floor parsed from the POI's colliders instead of the ground above.
	var terrain: TerrainManager = world.get(&"terrain") as TerrainManager
	if terrain != null and terrain.holes != null:
		var cut: Array[PackedVector2Array] = terrain.holes.pieces_in(Rect2(x0, z0, count * TERRAIN_STEP, count * TERRAIN_STEP))
		if not cut.is_empty():
			var faces_cut: PackedVector3Array = TerrainMesher.surface_faces(Vector2(x0, z0), count * TERRAIN_STEP, TERRAIN_STEP, world.height_at, Callable(), cut)
			src.add_faces(faces_cut, Transform3D(Basis.IDENTITY, Vector3(x0, 0.0, z0)))
			return
	var h := PackedFloat32Array()
	h.resize((count + 1) * (count + 1))
	for j: int in count + 1:
		for i: int in count + 1:
			h[j * (count + 1) + i] = world.height_at(x0 + i * TERRAIN_STEP, z0 + j * TERRAIN_STEP)
	var faces := PackedVector3Array()
	faces.resize(count * count * 6)
	var f: int = 0
	for j: int in count:
		for i: int in count:
			var a := Vector3(x0 + i * TERRAIN_STEP, h[j * (count + 1) + i], z0 + j * TERRAIN_STEP)
			var b := Vector3(a.x + TERRAIN_STEP, h[j * (count + 1) + i + 1], a.z)
			var c := Vector3(a.x, h[(j + 1) * (count + 1) + i], a.z + TERRAIN_STEP)
			var d := Vector3(a.x + TERRAIN_STEP, h[(j + 1) * (count + 1) + i + 1], a.z + TERRAIN_STEP)
			faces[f] = a
			faces[f + 1] = b
			faces[f + 2] = c
			faces[f + 3] = b
			faces[f + 4] = d
			faces[f + 5] = c
			f += 6
	src.add_faces(faces, Transform3D.IDENTITY)


## Bridge decks are walkable ground over the river (the terrain below is the riverbed).
func _add_bridges(src: NavigationMeshSourceGeometryData3D, k: Vector2i) -> void:
	var bridges: Node = world.get(&"bridges")
	if bridges == null or not bridges.has_method(&"nav_faces_in_rect"):
		return
	var faces: PackedVector3Array = bridges.call(&"nav_faces_in_rect", Rect2(k.x * TILE - BORDER, k.y * TILE - BORDER, TILE + BORDER * 2.0, TILE + BORDER * 2.0))
	if not faces.is_empty():
		src.add_faces(faces, Transform3D.IDENTITY)


func _add_obstructions(src: NavigationMeshSourceGeometryData3D, k: Vector2i) -> void:
	var center := Vector3((k.x + 0.5) * TILE, 0, (k.y + 0.5) * TILE)
	var reach: float = TILE * 0.75 + BORDER
	var building: Node = world.get(&"building")
	if building != null:
		for p: StructurePiece in building.call(&"pieces_in_radius", center, reach):
			if p.is_log():
				var seg: PackedVector3Array = LogSnapper.segment(p.global_transform)
				if absf(seg[0].y - seg[1].y) > 1.5:
					_box(src, p.global_position, Vector2(0.4, 0.4), 0.0, minf(seg[0].y, seg[1].y), 4.0)
				else:
					var d: Vector3 = seg[1] - seg[0]
					_box(src, (seg[0] + seg[1]) * 0.5, Vector2(d.length() + 0.2, 0.42), atan2(d.z, d.x), minf(seg[0].y, seg[1].y) - LogSnapper.RADIUS, LogSnapper.DIAM + 1.6)
			elif p.def.piece_kind != "shelter":
				_box(src, p.global_position, Vector2(p.def.size.x, p.def.size.z), -p.global_rotation.y, p.global_position.y, maxf(p.def.size.y, 0.5))
	var veg: Node = world.get(&"vegetation")
	if veg != null and veg.has_method(&"obstacles_in_rect"):
		for o: Dictionary in veg.call(&"obstacles_in_rect", Rect2(center.x - reach, center.z - reach, reach * 2.0, reach * 2.0)):
			var pos: Vector3 = o["pos"]
			_box(src, pos, Vector2.ONE * float(o["radius"]) * 2.0, 0.0, pos.y - 0.3, 3.0)


func _box(src: NavigationMeshSourceGeometryData3D, c: Vector3, size: Vector2, yaw: float, base_y: float, height: float) -> void:
	var hx: float = size.x * 0.5
	var hz: float = size.y * 0.5
	var cs: float = cos(yaw)
	var sn: float = sin(yaw)
	var pts := PackedVector3Array()
	for o: Vector2 in [Vector2(-hx, -hz), Vector2(hx, -hz), Vector2(hx, hz), Vector2(-hx, hz)]:
		pts.append(Vector3(c.x + o.x * cs - o.y * sn, base_y, c.z + o.x * sn + o.y * cs))
	src.add_projected_obstruction(pts, base_y, height, false)


func _add_pois(nm: NavigationMesh, src: NavigationMeshSourceGeometryData3D, k: Vector2i) -> void:
	var pois: Node = world.get(&"pois")
	if pois == null or not pois.has_method(&"nav_roots_in_rect"):
		return
	nm.geometry_parsed_geometry_type = NavigationMesh.PARSED_GEOMETRY_STATIC_COLLIDERS
	nm.geometry_collision_mask = (1 << 0) | (1 << 1) | (1 << 2)
	var rect := Rect2(k.x * TILE - BORDER, k.y * TILE - BORDER, TILE + BORDER * 2.0, TILE + BORDER * 2.0)
	for root: Node in pois.call(&"nav_roots_in_rect", rect):
		NavigationServer3D.parse_source_geometry_data(nm, src, root)
