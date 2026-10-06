class_name VolumeTerrain
extends Node3D
## SDF volume terrain for tunnels and mining (hybrid with the heightmap; ADR-0007).
##
## The world is a heightmap until you dig past what a heightmap can express (deeper than its dig
## limit, or into a steep face). Then the 16 m columns under the dig become volume: chunks of
## 0.5 m voxels initialised from the heightfield (density = height - y, positive = solid) so the
## surface is unchanged at hand-off, the heightmap stops drawing and sinks its collision there,
## and from then on edits are sphere subtractions/additions meshed with SurfaceNets on worker
## threads (collision from the same triangles). Edited chunks persist as chunk blobs "v:x_y_z".

const N: int = 32
const VOXEL: float = 0.5
const SIZE: float = N * VOXEL
const CLAMP: float = 2.0

signal column_activated(column: Vector2i)

var terrain: Node
var chunks: Dictionary = {}
var columns: Dictionary = {}
## Column dictionaries replaced by activate_column: [ticks_msec, Dictionary], oldest first.
var _retired: Array = []
var _material: ShaderMaterial
var _pending: Dictionary = {}
var _edited: Dictionary = {}


class VChunk:
	var key: Vector3i
	var density: PackedFloat32Array
	var mesh_node: MeshInstance3D
	var body: StaticBody3D
	var tris: PackedVector3Array


func setup(p_terrain: Node) -> void:
	terrain = p_terrain
	_material = ShaderMaterial.new()
	_material.shader = load("res://assets/shaders/volume_terrain.gdshader")
	var tex: Variant = terrain.get(&"textures")
	if tex != null and tex.has_method(&"apply_to"):
		tex.call(&"apply_to", _material)


static func column_of(x: float, z: float) -> Vector2i:
	return Vector2i(int(floor(x / SIZE)), int(floor(z / SIZE)))


static func chunk_of(p: Vector3) -> Vector3i:
	return Vector3i(int(floor(p.x / SIZE)), int(floor(p.y / SIZE)), int(floor(p.z / SIZE)))


func is_volume_column(x: float, z: float) -> bool:
	return columns.has(column_of(x, z))


## Converts the 16 m column at (x, z) to volume chunks spanning from below `min_y` to above the
## highest surface point (initialised from the heightfield so nothing visibly changes).
func activate_column(col: Vector2i, min_y: float) -> void:
	var lo_h: float = INF
	var hi_h: float = -INF
	for j: int in 5:
		for i: int in 5:
			var h: float = terrain.call(&"base_height_at", col.x * SIZE + i * SIZE * 0.25, col.y * SIZE + j * SIZE * 0.25)
			lo_h = minf(lo_h, h)
			hi_h = maxf(hi_h, h)
	var cy0: int = int(floor(minf(min_y, lo_h - 4.0) / SIZE))
	var cy1: int = int(floor((hi_h + 3.0) / SIZE))
	var had: Dictionary = columns.get(col, {})
	var span := Vector2i(cy0, cy1)
	if not had.is_empty():
		span = Vector2i(mini(cy0, int(had["y0"])), maxi(cy1, int(had["y1"])))
	# Copy, then swap: terrain chunk meshing reads `columns` on worker threads (is_volume_column as
	# the mesher's hole test), and inserting into a dictionary another thread is reading can
	# corrupt it. The replaced dictionary stays referenced a while for a reader still holding it.
	var next: Dictionary = columns.duplicate()
	next[col] = {"y0": span.x, "y1": span.y}
	_retired.append([Time.get_ticks_msec(), columns])
	columns = next
	while _retired.size() > 4 and Time.get_ticks_msec() - int(_retired[0][0]) > 20000:
		_retired.pop_front()
	for cy: int in range(span.x, span.y + 1):
		var key := Vector3i(col.x, cy, col.y)
		if not chunks.has(key):
			_create_chunk(key)
			_remesh(key)
	if had.is_empty():
		column_activated.emit(col)


func _create_chunk(key: Vector3i) -> VChunk:
	var c := VChunk.new()
	c.key = key
	c.density = PackedFloat32Array()
	c.density.resize(SurfaceNets.size_for(N))
	var origin := Vector3(key.x * SIZE, key.y * SIZE, key.z * SIZE)
	var s: int = N + 3
	# POI cellars (TD-026) stay open when a column over them turns into volume: the ground is
	# the heightfield minus each cellar's box (footprint x from just under its floor upward),
	# carved with the horizontal distance to the cellar outline so the surface lands on the
	# cellar walls' centre line, as the cut heightmap does.
	var holes: TerrainHoles = terrain.get(&"holes") as TerrainHoles
	var carve: bool = holes != null and holes.intersects(Rect2(origin.x - VOXEL * 2.0, origin.z - VOXEL * 2.0, SIZE + VOXEL * 4.0, SIZE + VOXEL * 4.0))
	for k: int in s:
		var z: float = origin.z + (k - 1) * VOXEL
		for i: int in s:
			var x: float = origin.x + (i - 1) * VOXEL
			var h: float = terrain.call(&"base_height_at", x, z)
			var sd: float = INF
			var floor_y: float = INF
			if carve:
				sd = holes.signed_distance(x, z)
				var hole: TerrainHoles.Hole = holes.hole_at(x, z)
				if hole == null and sd < CLAMP:
					hole = _nearest_hole(holes, x, z)
				if hole != null:
					floor_y = hole.floor_y - 0.25
			for j: int in s:
				var y: float = origin.y + (j - 1) * VOXEL
				var dens: float = h - y
				if floor_y != INF:
					dens = minf(dens, maxf(sd, floor_y - y))
				c.density[(k * s + j) * s + i] = clampf(dens, -CLAMP, CLAMP)
	chunks[key] = c
	return c


static func _nearest_hole(holes: TerrainHoles, x: float, z: float) -> TerrainHoles.Hole:
	for h: TerrainHoles.Hole in holes.holes:
		if h.bounds.grow(CLAMP).has_point(Vector2(x, z)):
			return h
	return null


## Smooth sphere edit: amount > 0 removes material (dig), < 0 adds. Returns volume removed (m^3).
func edit_sphere(center: Vector3, radius: float, amount: float) -> float:
	var col: Vector2i = column_of(center.x, center.z)
	# Make sure every chunk whose padded samples the sphere touches exists.
	for cz: int in range(int(floor((center.z - radius - VOXEL) / SIZE)), int(floor((center.z + radius + VOXEL) / SIZE)) + 1):
		for cx: int in range(int(floor((center.x - radius - VOXEL) / SIZE)), int(floor((center.x + radius + VOXEL) / SIZE)) + 1):
			activate_column(Vector2i(cx, cz), center.y - radius - 2.0)
	var removed: float = 0.0
	var touched: Dictionary = {}
	var r_cells: int = int(ceil(radius / VOXEL)) + 1
	var cell_vol: float = VOXEL * VOXEL * VOXEL
	for key: Vector3i in _chunks_near(center, radius + VOXEL * 2.0):
		var c: VChunk = chunks[key]
		var origin := Vector3(key.x * SIZE, key.y * SIZE, key.z * SIZE)
		var local: Vector3 = (center - origin) / VOXEL
		var s: int = N + 3
		var changed: bool = false
		for k: int in range(maxi(-1, int(local.z) - r_cells), mini(N + 1, int(local.z) + r_cells) + 1):
			for j: int in range(maxi(-1, int(local.y) - r_cells), mini(N + 1, int(local.y) + r_cells) + 1):
				for i: int in range(maxi(-1, int(local.x) - r_cells), mini(N + 1, int(local.x) + r_cells) + 1):
					var p: Vector3 = origin + Vector3(i, j, k) * VOXEL
					var d: float = p.distance_to(center) / radius
					if d >= 1.0:
						continue
					var w: float = (1.0 - d * d) * amount
					var idx: int = ((k + 1) * s + (j + 1)) * s + (i + 1)
					var before: float = c.density[idx]
					var after: float = clampf(before - w, -CLAMP, CLAMP)
					if not is_equal_approx(before, after):
						c.density[idx] = after
						changed = true
						# Only count each world sample once (in its owning chunk).
						if i >= 0 and j >= 0 and k >= 0 and i < N and j < N and k < N:
							removed += clampf(before, 0.0, 1.0) * cell_vol - clampf(after, 0.0, 1.0) * cell_vol
		if changed:
			touched[key] = true
			_edited[key] = true
	for key2: Vector3i in touched:
		_remesh(key2)
	return removed


func _chunks_near(p: Vector3, r: float) -> Array[Vector3i]:
	var out: Array[Vector3i] = []
	var lo: Vector3i = chunk_of(p - Vector3.ONE * r)
	var hi: Vector3i = chunk_of(p + Vector3.ONE * r)
	for z: int in range(lo.z, hi.z + 1):
		for y: int in range(lo.y, hi.y + 1):
			for x: int in range(lo.x, hi.x + 1):
				var k := Vector3i(x, y, z)
				if chunks.has(k):
					out.append(k)
	return out


func remesh_all() -> void:
	for key: Vector3i in chunks:
		_remesh(key)


func _remesh(key: Vector3i) -> void:
	var c: VChunk = chunks[key]
	var data: PackedFloat32Array = c.density.duplicate()
	# The worker fills its own slot: `job` gains "task" on this thread after the task has started,
	# and a dictionary written from two threads at once can corrupt itself.
	var out: Array = [{}]
	var job: Dictionary = {"key": key, "out": out}
	job["task"] = WorkerThreadPool.add_task(func() -> void: out[0] = SurfaceNets.mesh(data, N, VOXEL), true, "volume mesh")
	if _pending.has(key):
		WorkerThreadPool.wait_for_task_completion(_pending[key]["task"])
	_pending[key] = job


func _process(_delta: float) -> void:
	for key: Vector3i in _pending.keys():
		var job: Dictionary = _pending[key]
		if WorkerThreadPool.is_task_completed(job["task"]):
			WorkerThreadPool.wait_for_task_completion(job["task"])
			_pending.erase(key)
			_apply(key, job["out"][0])


## Builds the mesh and collision of a chunk synchronously (tests, load).
func flush() -> void:
	for key: Vector3i in _pending.keys():
		WorkerThreadPool.wait_for_task_completion(_pending[key]["task"])
		_apply(key, _pending[key]["out"][0])
	_pending.clear()


func _apply(key: Vector3i, res: Dictionary) -> void:
	var c: VChunk = chunks.get(key)
	if c == null:
		return
	var verts: PackedVector3Array = res.get("vertices", PackedVector3Array())
	var idx: PackedInt32Array = res.get("indices", PackedInt32Array())
	if c.mesh_node == null:
		c.mesh_node = MeshInstance3D.new()
		c.mesh_node.name = "V_%d_%d_%d" % [key.x, key.y, key.z]
		c.mesh_node.position = Vector3(key.x * SIZE, key.y * SIZE, key.z * SIZE)
		c.mesh_node.material_override = _material
		add_child(c.mesh_node)
	if idx.is_empty():
		c.mesh_node.mesh = null
		if c.body != null:
			c.body.queue_free()
			c.body = null
		c.tris = PackedVector3Array()
		return
	var arr: Array = []
	arr.resize(Mesh.ARRAY_MAX)
	arr[Mesh.ARRAY_VERTEX] = verts
	arr[Mesh.ARRAY_NORMAL] = res["normals"]
	arr[Mesh.ARRAY_INDEX] = idx
	var am := ArrayMesh.new()
	am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
	c.mesh_node.mesh = am
	var tris := PackedVector3Array()
	tris.resize(idx.size())
	var o: Vector3 = c.mesh_node.position
	for i: int in idx.size():
		tris[i] = verts[idx[i]] + o
	c.tris = tris
	if c.body == null:
		c.body = StaticBody3D.new()
		c.body.collision_layer = 1
		c.body.collision_mask = 0
		c.body.set_meta(&"terrain", true)
		c.body.set_meta(&"volume", true)
		c.body.set_meta(&"damage_receiver", terrain)
		c.body.set_meta(&"surface", "dirt")
		var cs := CollisionShape3D.new()
		cs.shape = ConcavePolygonShape3D.new()
		c.body.add_child(cs)
		add_child(c.body)
	var shape: ConcavePolygonShape3D = (c.body.get_child(0) as CollisionShape3D).shape
	shape.backface_collision = true
	shape.set_faces(tris)


## Triangles of volume chunks overlapping an XZ rect (navigation source geometry).
func faces_in_rect(r: Rect2) -> PackedVector3Array:
	var out := PackedVector3Array()
	for key: Vector3i in chunks:
		var cr := Rect2(key.x * SIZE, key.z * SIZE, SIZE, SIZE)
		if cr.intersects(r):
			out.append_array((chunks[key] as VChunk).tris)
	return out


# --- Persistence --------------------------------------------------------------------------------

func save_into(ws: WorldState) -> void:
	for key: Vector3i in _edited:
		var c: VChunk = chunks.get(key)
		var bytes := PackedByteArray()
		bytes.resize(c.density.size())
		for i: int in c.density.size():
			bytes[i] = clampi(int(round(c.density[i] / CLAMP * 127.0)) + 128, 0, 255)
		ws.chunk_blobs["v:%d_%d_%d" % [key.x, key.y, key.z]] = bytes.compress(FileAccess.COMPRESSION_ZSTD)
	ws.flags["volume_columns"] = _columns_to_array()


func _columns_to_array() -> Array:
	var out: Array = []
	for col: Vector2i in columns:
		out.append([col.x, col.y, int(columns[col]["y0"]), int(columns[col]["y1"])])
	return out


func load_from(ws: WorldState) -> void:
	for e: Variant in ws.flags.get("volume_columns", []):
		var a: Array = e
		var col := Vector2i(int(a[0]), int(a[1]))
		activate_column(col, float(int(a[2]) * SIZE))
	for k: Variant in ws.chunk_blobs.keys():
		var ks: String = str(k)
		if not ks.begins_with("v:"):
			continue
		var p: PackedStringArray = ks.substr(2).split("_")
		var key := Vector3i(int(p[0]), int(p[1]), int(p[2]))
		var c: VChunk = chunks.get(key)
		if c == null:
			c = _create_chunk(key)
		var raw: PackedByteArray = (ws.chunk_blobs[k] as PackedByteArray).decompress(SurfaceNets.size_for(N), FileAccess.COMPRESSION_ZSTD)
		for i: int in mini(raw.size(), c.density.size()):
			c.density[i] = float(int(raw[i]) - 128) / 127.0 * CLAMP
		_edited[key] = true
	remesh_all()
