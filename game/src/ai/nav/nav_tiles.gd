class_name NavTiles
extends Node
## Outdoor navigation mesh, baked in 32 m tiles around the player on worker threads and rebaked
## where the world changes (structures built or broken, terrain dug, trees felled, volume chunks
## installed, caves placed). Source geometry is assembled directly — terrain faces from the
## heightfield plus the SDF volume's triangles where it owns the ground (tunnels, caves; ADR-0056),
## structures/trees/boulders as projected obstructions, POI buildings parsed from their colliders —
## so baking never walks the whole scene. Tiles bake with a border so neighbours stitch on the
## navigation map.

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
	Events.terrain_modified.connect(_mark_aabb)
	# A streamed world (ADR-0038): tiles baked over a region's coarse ground are baked again once its
	# 1 m terrain attaches.
	var tm: TerrainManager = w.get(&"terrain") as TerrainManager if w != null else null
	if tm != null:
		tm.region_attached.connect(_on_region_attached)
		# Volume chunks landing (a dig re-meshed, a cave column streaming in) and caves placed or
		# removed change the walkable ground over their box (ADR-0056).
		tm.caves_changed.connect(_mark_aabb)
		if tm.volume != null:
			tm.volume.chunks_applied.connect(_mark_aabb)


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
	if tm == null:
		return true
	# Volume columns under the tile still building: baking now would bake the heightfield over a
	# cave mouth that is about to open (or a hole with no floor yet).
	if tm.volume != null and not tm.volume.is_rect_ready(tile_rect(k)):
		return false
	if tm.streamer == null:
		return true
	return tm.region_terrain_at((k.x + 0.5) * TILE, (k.y + 0.5) * TILE) != null


func _exit_tree() -> void:
	for k: Vector2i in _tiles.keys():
		_free_tile(k)


static func tile_of(p: Vector3) -> Vector2i:
	return Vector2i(int(floor(p.x / TILE)), int(floor(p.z / TILE)))


## The XZ area a tile's bake reads geometry from: the tile plus its border.
static func tile_rect(k: Vector2i) -> Rect2:
	return Rect2(k.x * TILE - BORDER, k.y * TILE - BORDER, TILE + BORDER * 2.0, TILE + BORDER * 2.0)


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


## Queues a rebake of every live tile whose bake reads geometry inside `aabb` (its XZ footprint
## against the tile plus border): an edit, a batch of volume chunks installed, a cave placed.
## Walks the live tiles, not the box's tile range: a frame's applied box can be large.
func _mark_aabb(aabb: AABB) -> void:
	var r := Rect2(aabb.position.x, aabb.position.z, aabb.size.x, aabb.size.z)
	for k: Vector2i in _tiles:
		if tile_rect(k).intersects(r, true):
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
	var inputs: Array = bake_inputs(k)
	var nm: NavigationMesh = inputs[0]
	_busy += 1
	(_tiles[k] as Dictionary)["baking"] = true
	NavigationServer3D.bake_from_source_geometry_data_async(nm, inputs[1], _on_baked.bind(k, nm))


## [NavigationMesh, NavigationMeshSourceGeometryData3D]: a tile's bake settings and its source
## geometry, assembled on this thread (tests bake them synchronously).
func bake_inputs(k: Vector2i) -> Array:
	var nm := NavigationMesh.new()
	nm.agent_radius = 0.5
	nm.agent_height = 1.75
	nm.agent_max_climb = 0.5
	nm.agent_max_slope = 46.0
	nm.cell_size = 0.25
	nm.cell_height = 0.25
	nm.border_size = BORDER
	nm.region_min_size = 4.0
	# border_size is cut from *inside* the baking box (Godot's Recast setup), so the box is the tile
	# grown by the border: the polygons then end exactly on the tile's edges, neighbours' edges
	# line up (no overlap) and stitch on the map. A box of the bare tile left a 2 * BORDER gap
	# between every pair of tiles, and no path ever crossed a seam (found by the cave nav test).
	var r: Rect2 = tile_rect(k)
	nm.filter_baking_aabb = AABB(Vector3(r.position.x, -1000.0, r.position.y), Vector3(r.size.x, 3000.0, r.size.y))
	var src := NavigationMeshSourceGeometryData3D.new()
	_add_terrain(src, k)
	_add_bridges(src, k)
	_add_obstructions(src, k)
	_add_pois(nm, src, k)
	return [nm, src]


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
	var area := Rect2(x0, z0, count * TERRAIN_STEP, count * TERRAIN_STEP)
	var terrain: TerrainManager = world.get(&"terrain") as TerrainManager
	# The SDF volume (dug tunnels, caves; ADR-0056): where a column is committed the heightmap is a
	# hole and the volume's triangles are the ground, so Recast walks into the tunnel floor instead
	# of over the hillside's old surface. Owned columns not committed yet keep the heightfield (it
	# is still what you stand on there).
	var hole_fn := Callable()
	if terrain != null and terrain.volume != null and not terrain.volume.committed.is_empty():
		var vol: VolumeTerrain = terrain.volume
		var lo: Vector2i = VolumeTerrain.column_of(area.position.x, area.position.y)
		var hi: Vector2i = VolumeTerrain.column_of(area.end.x, area.end.y)
		for cz: int in range(lo.y, hi.y + 1):
			for cx: int in range(lo.x, hi.x + 1):
				if not vol.committed.has(Vector2i(cx, cz)):
					continue
				hole_fn = _nav_hole.bind(vol)
				# Shrunk a hair so faces_in_rect takes this column alone.
				var faces_v: PackedVector3Array = vol.faces_in_rect(Rect2(cx * VolumeTerrain.SIZE + 0.01, cz * VolumeTerrain.SIZE + 0.01, VolumeTerrain.SIZE - 0.02, VolumeTerrain.SIZE - 0.02))
				if not faces_v.is_empty():
					src.add_faces(faces_v, Transform3D.IDENTITY)
	# POI cellars (TD-026): the terrain is cut away over them, exactly as the collision is, so
	# Recast walks the cellar floor parsed from the POI's colliders instead of the ground above.
	var cut: Array[PackedVector2Array] = []
	if terrain != null and terrain.holes != null:
		cut = terrain.holes.pieces_in(area)
	if not cut.is_empty() or hole_fn.is_valid():
		var faces_cut: PackedVector3Array = TerrainMesher.surface_faces(Vector2(x0, z0), count * TERRAIN_STEP, TERRAIN_STEP, world.height_at, hole_fn, cut)
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


## The heightfield cells the volume replaces in a tile's source (TerrainMesher's hole test, called
## with each 1 m cell's centre): the cells over committed columns, except the last strip before a
## column edge whose neighbour the heightfield still owns. Surface nets put the volume's vertices at
## voxel centres, so its surface stops VOXEL / 2 short of a column's +X / +Z edge; dropping that
## cell too left a 0.25 m slit that Recast's agent radius widened into a 1.25 m gap all along the
## border. There the old surface stays unless a dig took the ground from under it (the volume's
## density just below it is air), so no lid is left over a hole. Main thread (density_at).
func _nav_hole(x: float, z: float, vol: VolumeTerrain) -> bool:
	var col: Vector2i = VolumeTerrain.column_of(x, z)
	if not vol.committed.has(col):
		return false
	var hx: bool = x - col.x * VolumeTerrain.SIZE > VolumeTerrain.SIZE - TERRAIN_STEP
	var hz: bool = z - col.y * VolumeTerrain.SIZE > VolumeTerrain.SIZE - TERRAIN_STEP
	var edge: bool = (hx and not vol.committed.has(col + Vector2i(1, 0))) or (hz and not vol.committed.has(col + Vector2i(0, 1))) \
		or (hx and hz and not vol.committed.has(col + Vector2i(1, 1)))
	if not edge:
		return true
	var d: float = vol.density_at(Vector3(x, world.height_at(x, z) - 0.3, z))
	return not is_nan(d) and d <= 0.0


## Bridge decks are walkable ground over the river (the terrain below is the riverbed).
func _add_bridges(src: NavigationMeshSourceGeometryData3D, k: Vector2i) -> void:
	var bridges: Node = world.get(&"bridges")
	if bridges == null or not bridges.has_method(&"nav_faces_in_rect"):
		return
	var faces: PackedVector3Array = bridges.call(&"nav_faces_in_rect", tile_rect(k))
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
	var rect: Rect2 = tile_rect(k)
	for root: Node in pois.call(&"nav_roots_in_rect", rect):
		NavigationServer3D.parse_source_geometry_data(nm, src, root)
