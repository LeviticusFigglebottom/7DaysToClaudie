class_name VolumeTerrain
extends Node3D
## SDF volume terrain for tunnels, mining and caves (hybrid with the heightmap; ADR-0007, ADR-0056).
##
## The world is a heightmap until you dig past what a heightmap can express (deeper than its dig
## limit, or into a steep face) or a cave runs through it. Then the 16 m columns there become
## volume: chunks of 0.5 m voxels initialised from the heightfield (density = height - y, positive =
## solid), with POI cellars and caves carved in, so the surface is unchanged at hand-off. Edits are
## sphere subtractions/additions meshed with SurfaceNets (collision from the same triangles).
##
## Streaming (CAVES_PLAN WS-B):
##  * jobs: a chunk's density (build_density, a pure static function of the heights, the cellars,
##    the caves and an optional saved blob) and its mesh are made in one worker job, queued under
##    TerrainManager's task cap (TD-196) and applied in _process within APPLY_BUDGET_MS.
##  * two-phase commit: a column is owned (`columns`, is_volume_column) as soon as its chunks
##    exist, but only becomes a heightmap hole (`committed`, is_hole_column, column_activated)
##    once every chunk of it has been applied, so the ground never shows a hole without its mesh.
##  * regions: attach_region activates the dug columns, the saved blobs and the cave columns over
##    a region; detach_region encodes its edited chunks into blobs and frees them. Edited chunks
##    persist as chunk blobs "v:x_y_z"; dug columns as flags.volume_columns. Cave columns are
##    derived from the terrain's `caves` set (duck-typed: touching/columns/carve_block) and never
##    saved.
##  * collision bodies only within COLLISION_RANGE of the terrain's focus.

const N: int = 32
const VOXEL: float = 0.5
const SIZE: float = N * VOXEL
const CLAMP: float = 2.0
## Main-thread time a frame spends installing finished chunks (StreamMeter kind "volume").
const APPLY_BUDGET_MS: float = 3.0
## Collision bodies exist within this distance of the focus (Jolt's max_bodies, physics cost)...
const COLLISION_RANGE: float = 160.0
## ...and are dropped beyond this one (hysteresis, so walking along the edge doesn't churn).
const COLLISION_DROP: float = 184.0
## Volume meshes fade where the far tiles take over.
const VISIBILITY_END: float = 400.0
const GATE_INTERVAL: float = 0.25

## Every chunk of a column has been applied: the heightmap treats it as a hole from now on.
signal column_activated(column: Vector2i)
## A committed column left the volume (its region detached, its cave was removed).
signal column_deactivated(column: Vector2i)
## Chunks were installed this frame (meshes and collision), over this box.
signal chunks_applied(aabb: AABB)

var terrain: Node
var chunks: Dictionary = {}
## Owned columns: Vector2i -> {"y0", "y1"} (chunk rows). Chunks exist (or are being built).
var columns: Dictionary = {}
## Committed columns (Vector2i -> true): applied, so the heightmap is a hole there.
var committed: Dictionary = {}
## Guards `columns` and `committed`: terrain chunk meshing reads them on worker threads (the
## mesher's hole test) while the main thread inserts. Copy-and-swap is not enough: assigning a
## container to a member releases the old one before the new one is stored, so a reader in
## between dereferences null (TD-104).
var _columns_lock := Mutex.new()
var _material: ShaderMaterial
## Vector3i -> job {key, vol, build, out: [result], fn, task (once started)}.
var _pending: Dictionary = {}
## Tasks of superseded jobs, joined when they finish (and in _exit_tree).
var _orphans: Array[int] = []
var _edited: Dictionary = {}
## Edited chunks not in memory (their region detached, or not attached since the load):
## Vector3i -> ZSTD bytes, as saved.
var _blobs: Dictionary = {}
## Columns the player dug (saved): Vector2i -> Vector2i(cy0, cy1).
var _dug: Dictionary = {}
## Columns a cave runs through (derived, never saved): Vector2i -> Vector2i(cy0, cy1).
var _cave_cols: Dictionary = {}
## Attached regions: rid -> Rect2. Until the first attach everything counts as attached (a bare
## volume in tests, tools).
var _regions: Dictionary = {}
var _streamed: bool = false
## Vector2i column -> Array of the Vector3i chunk keys in it.
var _by_column: Dictionary = {}
var _gate_accum: float = 0.0
## Chunks waiting for their collision body (Vector3i -> true), made a few a frame in pump().
var _body_queue: Dictionary = {}
## What a body costs Jolt per triangle (ms), learnt as they are made: ~1.4 µs (2,800 triangles of
## a surface chunk, 2.5-4 ms).
var _body_ms_per_tri: float = 0.0014
var _applied_box := AABB()
var _applied_any: bool = false
## {frames, chunks, total_ms, max_ms}: main-thread apply cost of the frames that applied chunks.
var apply_stats: Dictionary = {"frames": 0, "chunks": 0, "total_ms": 0.0, "max_ms": 0.0}


class VChunk:
	var key: Vector3i
	## Empty until built (a job is on its way).
	var density: PackedFloat32Array
	var mesh_node: MeshInstance3D
	var body: StaticBody3D
	## World-space triangles (collision and navigation source).
	var tris: PackedVector3Array
	## A mesh result has been installed at least once.
	var applied: bool = false


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


## Whether the volume owns the column at (x, z) (its chunks exist or are being built).
## Thread-safe.
func is_volume_column(x: float, z: float) -> bool:
	_columns_lock.lock()
	var on: bool = columns.has(column_of(x, z))
	_columns_lock.unlock()
	return on


## Whether the heightmap must leave a hole at (x, z): the column's volume meshes are installed.
## Thread-safe (the terrain mesher's hole test).
func is_hole_column(x: float, z: float) -> bool:
	_columns_lock.lock()
	var on: bool = committed.has(column_of(x, z))
	_columns_lock.unlock()
	return on


# --- Density (pure, worker-safe) ------------------------------------------------------------------

## A chunk's padded density block: the heightfield (height_fn(x, z), pristine-or-dug heights)
## minus the POI cellars in `holes` and the caves of `caves` (an object with touching(AABB) whose
## plans have carve_block; null = none), or the saved `blob` when there is one (a dig wins over a
## regenerated cave). Pure: everything it reads is captured by the caller.
static func build_density(key: Vector3i, height_fn: Callable, holes: TerrainHoles, caves: Object, blob: PackedByteArray = PackedByteArray()) -> PackedFloat32Array:
	var density := PackedFloat32Array()
	density.resize(SurfaceNets.size_for(N))
	if not blob.is_empty():
		decode_blob(blob, density)
		return density
	var origin := Vector3(key.x * SIZE, key.y * SIZE, key.z * SIZE)
	var s: int = N + 3
	# POI cellars (TD-026) stay open when a column over them turns into volume: the ground is
	# the heightfield minus each cellar's box (footprint x from just under its floor upward),
	# carved with the horizontal distance to the cellar outline so the surface lands on the
	# cellar walls' centre line, as the cut heightmap does.
	var carve: bool = holes != null and holes.intersects(Rect2(origin.x - VOXEL * 2.0, origin.z - VOXEL * 2.0, SIZE + VOXEL * 4.0, SIZE + VOXEL * 4.0))
	for k: int in s:
		var z: float = origin.z + (k - 1) * VOXEL
		for i: int in s:
			var x: float = origin.x + (i - 1) * VOXEL
			var h: float = height_fn.call(x, z)
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
				density[(k * s + j) * s + i] = clampf(dens, -CLAMP, CLAMP)
	carve_caves(key, caves, density)
	return density


## min()s every cave of `caves` that reaches the chunk into its padded block (CavePlan.carve_block:
## sample (i, j, k) at origin + (ijk - 1) * VOXEL). False when no cave touched it.
static func carve_caves(key: Vector3i, caves: Object, density: PackedFloat32Array) -> bool:
	if caves == null or not caves.has_method(&"touching"):
		return false
	if caves.has_method(&"is_empty") and bool(caves.call(&"is_empty")):
		return false
	var origin := Vector3(key.x * SIZE, key.y * SIZE, key.z * SIZE)
	var box := AABB(origin - Vector3.ONE * VOXEL, Vector3.ONE * (SIZE + VOXEL * 2.0))
	var any: bool = false
	for plan: Variant in caves.call(&"touching", box):
		if plan != null and bool((plan as Object).call(&"carve_block", origin, N, VOXEL, density)):
			any = true
	return any


static func _nearest_hole(holes: TerrainHoles, x: float, z: float) -> TerrainHoles.Hole:
	for h: TerrainHoles.Hole in holes.holes:
		if h.bounds.grow(CLAMP).has_point(Vector2(x, z)):
			return h
	return null


static func encode_blob(density: PackedFloat32Array) -> PackedByteArray:
	var bytes := PackedByteArray()
	bytes.resize(density.size())
	for i: int in density.size():
		bytes[i] = clampi(int(round(density[i] / CLAMP * 127.0)) + 128, 0, 255)
	return bytes.compress(FileAccess.COMPRESSION_ZSTD)


static func decode_blob(blob: PackedByteArray, density: PackedFloat32Array) -> void:
	var raw: PackedByteArray = blob.decompress(SurfaceNets.size_for(N), FileAccess.COMPRESSION_ZSTD)
	for i: int in mini(raw.size(), density.size()):
		density[i] = float(int(raw[i]) - 128) / 127.0 * CLAMP


## The worker half of a chunk job: the density when `data` is empty, then its mesh. Blocks that
## are all solid or all air skip SurfaceNets (most of a deep cave column).
static func run_job(key: Vector3i, height_fn: Callable, holes: TerrainHoles, caves: Object, blob: PackedByteArray, data: PackedFloat32Array) -> Dictionary:
	var built: bool = data.is_empty()
	var d: PackedFloat32Array = build_density(key, height_fn, holes, caves, blob) if built else data
	var res: Dictionary = mesh_density(key, d)
	if built:
		res["density"] = d
	return res


## SurfaceNets over a chunk's block plus its world-space triangles.
static func mesh_density(key: Vector3i, d: PackedFloat32Array) -> Dictionary:
	var solid: int = 0
	for v: float in d:
		if v > 0.0:
			solid += 1
	if solid == 0 or solid == d.size():
		return {"vertices": PackedVector3Array(), "normals": PackedVector3Array(), "indices": PackedInt32Array(), "tris": PackedVector3Array()}
	var res: Dictionary = SurfaceNets.mesh(d, N, VOXEL)
	var verts: PackedVector3Array = res["vertices"]
	var idx: PackedInt32Array = res["indices"]
	var o := Vector3(key.x * SIZE, key.y * SIZE, key.z * SIZE)
	var tris := PackedVector3Array()
	tris.resize(idx.size())
	for i: int in idx.size():
		tris[i] = verts[idx[i]] + o
	res["tris"] = tris
	return res


# --- Columns ----------------------------------------------------------------------------------

## The chunk rows of a column from below `min_y` to above its highest surface point.
func _surface_span(col: Vector2i, min_y: float) -> Vector2i:
	var lo_h: float = INF
	var hi_h: float = -INF
	for j: int in 5:
		for i: int in 5:
			var h: float = terrain.call(&"base_height_at", col.x * SIZE + i * SIZE * 0.25, col.y * SIZE + j * SIZE * 0.25)
			lo_h = minf(lo_h, h)
			hi_h = maxf(hi_h, h)
	return Vector2i(int(floor(minf(min_y, lo_h - 4.0) / SIZE)), int(floor((hi_h + 3.0) / SIZE)))


static func _union(a: Variant, b: Vector2i) -> Vector2i:
	if a == null:
		return b
	var av: Vector2i = a
	return Vector2i(mini(av.x, b.x), maxi(av.y, b.y))


## Converts the 16 m column at (x, z) to volume chunks spanning from below `min_y` to above the
## highest surface point, now: the density is built on this thread (a dig needs it to edit at
## once); the meshes come from workers, and the column commits when they are installed.
func activate_column(col: Vector2i, min_y: float) -> void:
	_dug[col] = _union(_dug.get(col), _surface_span(col, min_y))
	_activate(col, _dug[col], true)


## Owns a column over `span` (grown with what it had); new chunks are built now (`sync`) or by
## a worker job.
func _activate(col: Vector2i, span: Vector2i, sync: bool) -> void:
	var had: Dictionary = columns.get(col, {})
	if not had.is_empty():
		span = Vector2i(mini(span.x, int(had["y0"])), maxi(span.y, int(had["y1"])))
	_columns_lock.lock()
	columns[col] = {"y0": span.x, "y1": span.y}
	_columns_lock.unlock()
	for cy: int in range(span.x, span.y + 1):
		var key := Vector3i(col.x, cy, col.y)
		if not chunks.has(key):
			_new_chunk(key, sync)


func _new_chunk(key: Vector3i, sync: bool) -> VChunk:
	var c := VChunk.new()
	c.key = key
	chunks[key] = c
	var col := Vector2i(key.x, key.z)
	if not _by_column.has(col):
		_by_column[col] = []
	(_by_column[col] as Array).append(key)
	if sync:
		_build_now(c)
		_queue(key, false)
	else:
		_queue(key, true)
	return c


## The chunk's density on this thread (from its saved blob when it has one).
func _build_now(c: VChunk) -> void:
	var blob: PackedByteArray = _blobs.get(c.key, PackedByteArray())
	c.density = build_density(c.key, Callable(terrain, &"base_height_at"), _holes(), _caves(), blob)
	if not blob.is_empty():
		_blobs.erase(c.key)
		_edited[c.key] = true


func _holes() -> TerrainHoles:
	return terrain.get(&"holes") as TerrainHoles if terrain != null else null


func _caves() -> Object:
	var c: Variant = terrain.get(&"caves") if terrain != null else null
	return c as Object if c is Object else null


## Commits a column once every chunk of it has been installed (phase two).
func _try_commit(col: Vector2i) -> void:
	if committed.has(col) or not columns.has(col):
		return
	for key: Vector3i in _by_column.get(col, []):
		var c: VChunk = chunks.get(key)
		if c == null or not c.applied:
			return
	_columns_lock.lock()
	committed[col] = true
	_columns_lock.unlock()
	column_activated.emit(col)


## Drops a column: edited chunks go back to blobs (`keep_edits`), the rest is freed.
func _deactivate(col: Vector2i, keep_edits: bool) -> void:
	for key: Vector3i in (_by_column.get(col, []) as Array).duplicate():
		var c: VChunk = chunks.get(key)
		if c != null and _edited.has(key) and keep_edits and not c.density.is_empty():
			_blobs[key] = encode_blob(c.density)
		_edited.erase(key)
		_retire(key)
		_free_chunk(key)
	_by_column.erase(col)
	_cave_cols.erase(col)
	var was: bool = committed.has(col)
	_columns_lock.lock()
	columns.erase(col)
	committed.erase(col)
	_columns_lock.unlock()
	if was:
		column_deactivated.emit(col)


func _free_chunk(key: Vector3i) -> void:
	var c: VChunk = chunks.get(key)
	if c == null:
		return
	if c.mesh_node != null:
		c.mesh_node.queue_free()
	if c.body != null:
		c.body.queue_free()
	_body_queue.erase(key)
	chunks.erase(key)


# --- Regions (ADR-0038) -------------------------------------------------------------------------

func _col_in(col: Vector2i, rect: Rect2) -> bool:
	return rect.has_point(Vector2((col.x + 0.5) * SIZE, (col.y + 0.5) * SIZE))


func _is_live_col(col: Vector2i) -> bool:
	if not _streamed:
		return true
	for rid: String in _regions:
		if _col_in(col, _regions[rid]):
			return true
	return false


## Brings a region's volume into play: its dug columns (their saved digs decoded on the workers)
## and the columns its caves run through, built by worker jobs and committed as they land.
func attach_region(rid: String, rect: Rect2) -> void:
	_streamed = true
	_regions[rid] = rect
	var want: Dictionary = {}
	for col: Vector2i in _dug:
		if _col_in(col, rect):
			want[col] = _dug[col]
	for key: Vector3i in _blobs:
		var bcol := Vector2i(key.x, key.z)
		if _col_in(bcol, rect):
			want[bcol] = _union(want.get(bcol), Vector2i(key.y, key.y))
	var spans: Dictionary = _cave_spans(rect)
	for col2: Vector2i in spans:
		_cave_cols[col2] = spans[col2]
		want[col2] = _union(want.get(col2), spans[col2])
	for col3: Vector2i in want:
		_activate(col3, want[col3], false)


## Takes a region's volume out of play: its edited chunks become blobs, everything is freed.
func detach_region(rid: String) -> void:
	if not _regions.has(rid):
		return
	var rect: Rect2 = _regions[rid]
	_regions.erase(rid)
	for col: Vector2i in columns.keys():
		if _col_in(col, rect) and not _is_live_col(col):
			_deactivate(col, true)


## Columns the caves run through within `rect`: the cave's rows grown up through the surface.
func _cave_spans(rect: Rect2) -> Dictionary:
	var out: Dictionary = {}
	var caves: Object = _caves()
	if caves == null or not caves.has_method(&"touching"):
		return out
	if caves.has_method(&"is_empty") and bool(caves.call(&"is_empty")):
		return out
	var box := AABB(Vector3(rect.position.x, -100000.0, rect.position.y), Vector3(rect.size.x, 200000.0, rect.size.y))
	for plan: Variant in caves.call(&"touching", box):
		var cols: Dictionary = (plan as Object).call(&"columns")
		for col: Vector2i in cols:
			if not _col_in(col, rect):
				continue
			var cs: Vector2i = cols[col]
			var span: Vector2i = _union(cs, _surface_span(col, cs.x * SIZE))
			out[col] = _union(out.get(col), span)
	return out


## The caves changed over `box` (TerrainManager.place_cave/remove_cave): new cave columns are
## built, unedited chunks there rebuilt (a dig wins), columns no cave or dig needs any more freed.
func refresh_caves(box: AABB) -> void:
	var rects: Array[Rect2] = []
	if _streamed:
		for rid: String in _regions:
			rects.append(_regions[rid])
	else:
		rects.append(Rect2(box.position.x, box.position.z, box.size.x, box.size.z).grow(SIZE))
	var next: Dictionary = {}
	for r: Rect2 in rects:
		next.merge(_cave_spans(r), true)
	var area := Rect2(box.position.x, box.position.z, box.size.x, box.size.z).grow(VOXEL * 2.0)
	for col: Vector2i in _cave_cols.keys():
		if next.has(col) or _dug.has(col) or not area.intersects(Rect2(col.x * SIZE, col.y * SIZE, SIZE, SIZE)):
			continue
		var edited: bool = false
		for key: Vector3i in _by_column.get(col, []):
			edited = edited or _edited.has(key) or _blobs.has(key)
		if edited:
			_cave_cols.erase(col)
		else:
			_deactivate(col, true)
	# Chunks already there are rebuilt with the new caves (their jobs captured the old set);
	# before the new columns, whose chunks are built with the new set anyway.
	var grown: AABB = box.grow(VOXEL * 2.0)
	for key2: Vector3i in chunks:
		if _edited.has(key2) or _blobs.has(key2):
			continue
		if AABB(Vector3(key2.x, key2.y, key2.z) * SIZE, Vector3.ONE * SIZE).intersects(grown):
			_queue(key2, true)
	for col2: Vector2i in next:
		_cave_cols[col2] = next[col2]
		_activate(col2, next[col2], false)


# --- Jobs -------------------------------------------------------------------------------------

## Queues a chunk's job: `build` makes its density first (from the heights, cellars and caves
## as they are now, or its blob), else it meshes a copy of its current density. Replaces any job
## the chunk had.
func _queue(key: Vector3i, build: bool) -> void:
	_retire(key)
	var c: VChunk = chunks[key]
	var data: PackedFloat32Array = PackedFloat32Array() if build else c.density.duplicate()
	var blob: PackedByteArray = _blobs.get(key, PackedByteArray()) if build else PackedByteArray()
	var height_fn := Callable(terrain, &"base_height_at")
	var holes: TerrainHoles = _holes()
	var caves: Object = _caves()
	# The worker fills its own slot: `job` gains "task" on the main thread after the task has
	# started, and a dictionary written from two threads at once can corrupt itself.
	var out: Array = [null]
	var fn := func() -> void:
		out[0] = VolumeTerrain.run_job(key, height_fn, holes, caves, blob, data)
	var job: Dictionary = {"key": key, "vol": true, "build": build, "blob": not blob.is_empty(), "out": out, "fn": fn,
		"dist_key": Vector2i(int(floor(key.x * SIZE / 64.0)), int(floor(key.z * SIZE / 64.0)))}
	_pending[key] = job
	if terrain != null and terrain.has_method(&"queue_volume_job"):
		terrain.call(&"queue_volume_job", job, fn)
	else:
		job["task"] = WorkerThreadPool.add_task(fn, true, "volume chunk")


## Forgets a chunk's job: one already running is joined later.
func _retire(key: Vector3i) -> void:
	var job: Dictionary = _pending.get(key, {})
	if job.is_empty():
		return
	if job.has("task"):
		_orphans.append(int(job["task"]))
	_pending.erase(key)


## For TerrainManager's queue: whether a queued job still stands for its chunk.
func is_job_live(job: Dictionary) -> bool:
	return is_same(_pending.get(job["key"]), job)


## Adds the tasks running now to `running` (task id -> true), for the shared task cap.
func count_running(running: Dictionary) -> void:
	for job: Dictionary in _pending.values():
		if job.has("task") and not WorkerThreadPool.is_task_completed(int(job["task"])):
			running[job["task"]] = true
	for t: int in _orphans:
		if not WorkerThreadPool.is_task_completed(t):
			running[t] = true


## Makes sure a chunk's density is here (a dig on a chunk whose build job hasn't come back):
## a running job is joined and its density taken, a queued one is dropped and built here.
func _settle(key: Vector3i) -> void:
	var c: VChunk = chunks.get(key)
	var job: Dictionary = _pending.get(key, {})
	if c == null or job.is_empty() or not bool(job["build"]):
		return
	if job.has("task"):
		WorkerThreadPool.wait_for_task_completion(int(job["task"]))
		_pending.erase(key)
		_take_density(c, job)
	else:
		_pending.erase(key)
		_build_now(c)
	_queue(key, false)


func _take_density(c: VChunk, job: Dictionary) -> void:
	var res: Dictionary = (job["out"] as Array)[0]
	c.density = res["density"]
	if bool(job["blob"]):
		_blobs.erase(c.key)
		_edited[c.key] = true


func _join_orphans(all: bool) -> void:
	for i: int in range(_orphans.size() - 1, -1, -1):
		if all or WorkerThreadPool.is_task_completed(_orphans[i]):
			WorkerThreadPool.wait_for_task_completion(_orphans[i])
			_orphans.remove_at(i)


func _process(delta: float) -> void:
	var t0: int = Time.get_ticks_usec()
	_gate_accum += delta
	if _gate_accum >= GATE_INTERVAL:
		_gate_accum = 0.0
		_gate_collision()
	pump(APPLY_BUDGET_MS)
	StreamMeter.note("volume", t0)


## Installs finished jobs, then queued collision bodies, within `budget_ms` (also driven by the
## boot's cave step and tests). A body (Jolt building the trimesh: ~2.5-4 ms for a surface chunk)
## waits for a frame with time left, or one with no mesh to install. Returns the chunks installed.
func pump(budget_ms: float) -> int:
	var t0: int = Time.get_ticks_usec()
	_join_orphans(false)
	if terrain != null and terrain.has_method(&"start_queued"):
		terrain.call(&"start_queued")
	var n: int = 0
	for key: Vector3i in _pending.keys():
		var job: Dictionary = _pending[key]
		if not job.has("task") or not WorkerThreadPool.is_task_completed(int(job["task"])):
			continue
		WorkerThreadPool.wait_for_task_completion(int(job["task"]))
		_pending.erase(key)
		_take(key, job)
		n += 1
		if float(Time.get_ticks_usec() - t0) / 1000.0 >= budget_ms:
			break
	var bodies: int = 0
	for key2: Vector3i in _body_queue.keys():
		var c: VChunk = chunks.get(key2)
		if c == null or c.body != null or c.tris.is_empty():
			_body_queue.erase(key2)
			continue
		# A body that would overrun the budget waits, unless nothing else ran this frame (progress).
		var est: float = _body_ms_per_tri * float(c.tris.size() / 3)
		if (n > 0 or bodies > 0) and float(Time.get_ticks_usec() - t0) / 1000.0 + est > budget_ms:
			break
		_body_queue.erase(key2)
		var tb: int = Time.get_ticks_usec()
		_set_body(c)
		_body_ms_per_tri = lerpf(_body_ms_per_tri, float(Time.get_ticks_usec() - tb) / 1000.0 / maxf(1.0, float(c.tris.size() / 3)), 0.25)
		bodies += 1
	if n > 0 or bodies > 0:
		var ms: float = float(Time.get_ticks_usec() - t0) / 1000.0
		apply_stats["frames"] = int(apply_stats["frames"]) + 1
		apply_stats["chunks"] = int(apply_stats["chunks"]) + n
		apply_stats["bodies"] = int(apply_stats.get("bodies", 0)) + bodies
		apply_stats["total_ms"] = float(apply_stats["total_ms"]) + ms
		apply_stats["max_ms"] = maxf(float(apply_stats["max_ms"]), ms)
	_emit_applied()
	return n


func _take(key: Vector3i, job: Dictionary) -> void:
	var c: VChunk = chunks.get(key)
	if c == null:
		return
	if bool(job["build"]):
		_take_density(c, job)
	_apply(key, (job["out"] as Array)[0])


func _emit_applied() -> void:
	if _applied_any:
		_applied_any = false
		chunks_applied.emit(_applied_box)


## Joins in-flight jobs: leaving one running past the engine's shutdown aborts it.
func _exit_tree() -> void:
	for key: Vector3i in _pending.keys():
		var job: Dictionary = _pending[key]
		if job.has("task"):
			WorkerThreadPool.wait_for_task_completion(int(job["task"]))
	_pending.clear()
	_join_orphans(true)


## Finishes every job now, on this thread when it hasn't started (tests, tools).
func flush() -> void:
	while not _pending.is_empty():
		for key: Vector3i in _pending.keys():
			var job: Dictionary = _pending.get(key, {})
			if job.is_empty():
				continue
			if job.has("task"):
				WorkerThreadPool.wait_for_task_completion(int(job["task"]))
			else:
				# Still in TerrainManager's queue: it drops the job once it is no longer pending.
				(job["fn"] as Callable).call()
			_pending.erase(key)
			_take(key, job)
	for key2: Vector3i in _body_queue.keys():
		var c: VChunk = chunks.get(key2)
		if c != null and c.body == null and not c.tris.is_empty():
			_set_body(c)
	_body_queue.clear()
	_join_orphans(true)
	_emit_applied()


## Is everything over `rect` built and installed (owned columns committed, no job pending)?
func is_rect_ready(rect: Rect2) -> bool:
	for col: Vector2i in columns:
		if not rect.intersects(Rect2(col.x * SIZE, col.y * SIZE, SIZE, SIZE)):
			continue
		if not committed.has(col):
			return false
		for key: Vector3i in _by_column.get(col, []):
			if _pending.has(key) or _body_queue.has(key):
				return false
	return true


## No job pending or still running (a retired one too: it may be inside the terrain's height
## query, and the terrain can't be freed until it returns) and no body waiting.
func is_idle() -> bool:
	return _pending.is_empty() and _body_queue.is_empty() and _orphans.is_empty()


# --- Install ------------------------------------------------------------------------------------

func _focus_xz() -> Vector2:
	var f: Variant = terrain.get(&"focus") if terrain != null else null
	if is_instance_valid(f) and f is Node3D and (f as Node3D).is_inside_tree():
		var p: Vector3 = (f as Node3D).global_position
		return Vector2(p.x, p.z)
	return Vector2(NAN, NAN)


static func _chunk_distance(key: Vector3i, f: Vector2) -> float:
	if is_nan(f.x):
		return 0.0
	return Vector2((key.x + 0.5) * SIZE, (key.z + 0.5) * SIZE).distance_to(f)


func _apply(key: Vector3i, res: Dictionary) -> void:
	var c: VChunk = chunks.get(key)
	if c == null:
		return
	var verts: PackedVector3Array = res.get("vertices", PackedVector3Array())
	var idx: PackedInt32Array = res.get("indices", PackedInt32Array())
	c.applied = true
	var box := AABB(Vector3(key.x, key.y, key.z) * SIZE, Vector3.ONE * SIZE)
	_applied_box = box if not _applied_any else _applied_box.merge(box)
	_applied_any = true
	if idx.is_empty():
		if c.mesh_node != null:
			c.mesh_node.mesh = null
		if c.body != null:
			c.body.queue_free()
			c.body = null
		c.tris = PackedVector3Array()
		_body_queue.erase(key)
		_try_commit(Vector2i(key.x, key.z))
		return
	if c.mesh_node == null:
		c.mesh_node = MeshInstance3D.new()
		c.mesh_node.name = "V_%d_%d_%d" % [key.x, key.y, key.z]
		c.mesh_node.position = Vector3(key.x * SIZE, key.y * SIZE, key.z * SIZE)
		c.mesh_node.material_override = _material
		c.mesh_node.visibility_range_end = VISIBILITY_END
		add_child(c.mesh_node)
	var arr: Array = []
	arr.resize(Mesh.ARRAY_MAX)
	arr[Mesh.ARRAY_VERTEX] = verts
	arr[Mesh.ARRAY_NORMAL] = res["normals"]
	arr[Mesh.ARRAY_INDEX] = idx
	var am := ArrayMesh.new()
	am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
	c.mesh_node.mesh = am
	c.tris = res["tris"]
	if c.body != null:
		# Re-meshed (a dig): the ground someone stands in must change with the mesh.
		_set_body(c)
	elif _chunk_distance(key, _focus_xz()) <= COLLISION_RANGE:
		_body_queue[key] = true
	_try_commit(Vector2i(key.x, key.z))


## The chunk's collision from its triangles (made on first use).
func _set_body(c: VChunk) -> void:
	if c.body == null:
		c.body = StaticBody3D.new()
		c.body.name = "VC_%d_%d_%d" % [c.key.x, c.key.y, c.key.z]
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
	shape.set_faces(c.tris)


## Queues bodies for meshed chunks that came within COLLISION_RANGE; drops those past
## COLLISION_DROP.
func _gate_collision() -> void:
	var f: Vector2 = _focus_xz()
	if is_nan(f.x):
		return
	for key: Vector3i in chunks:
		var c: VChunk = chunks[key]
		var d: float = _chunk_distance(key, f)
		if d > COLLISION_DROP:
			_body_queue.erase(key)
			if c.body != null:
				c.body.queue_free()
				c.body = null
		elif c.body == null and not c.tris.is_empty() and d <= COLLISION_RANGE:
			_body_queue[key] = true


# --- Edits ------------------------------------------------------------------------------------

## Smooth sphere edit: amount > 0 removes material (dig), < 0 adds. Returns volume removed (m^3).
func edit_sphere(center: Vector3, radius: float, amount: float) -> float:
	# Make sure every chunk whose padded samples the sphere touches exists.
	for cz: int in range(int(floor((center.z - radius - VOXEL) / SIZE)), int(floor((center.z + radius + VOXEL) / SIZE)) + 1):
		for cx: int in range(int(floor((center.x - radius - VOXEL) / SIZE)), int(floor((center.x + radius + VOXEL) / SIZE)) + 1):
			activate_column(Vector2i(cx, cz), center.y - radius - 2.0)
	var removed: float = 0.0
	var touched: Dictionary = {}
	var r_cells: int = int(ceil(radius / VOXEL)) + 1
	var cell_vol: float = VOXEL * VOXEL * VOXEL
	for key: Vector3i in _chunks_near(center, radius + VOXEL * 2.0):
		# A chunk whose density is still on a worker (a cave column streaming in) gets it now.
		_settle(key)
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
		_queue(key2, false)
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
		if not (chunks[key] as VChunk).density.is_empty():
			_queue(key, false)


# --- Queries ------------------------------------------------------------------------------------

## Triangles of volume chunks overlapping an XZ rect (navigation source geometry), by column.
func faces_in_rect(r: Rect2) -> PackedVector3Array:
	var out := PackedVector3Array()
	var lo: Vector2i = column_of(r.position.x, r.position.y)
	var hi: Vector2i = column_of(r.end.x, r.end.y)
	var cols: Array = []
	if (hi.x - lo.x + 1) * (hi.y - lo.y + 1) > _by_column.size():
		for col: Vector2i in _by_column:
			if col.x >= lo.x and col.x <= hi.x and col.y >= lo.y and col.y <= hi.y:
				cols.append(col)
	else:
		for cz: int in range(lo.y, hi.y + 1):
			for cx: int in range(lo.x, hi.x + 1):
				if _by_column.has(Vector2i(cx, cz)):
					cols.append(Vector2i(cx, cz))
	for col2: Vector2i in cols:
		if not r.intersects(Rect2(col2.x * SIZE, col2.y * SIZE, SIZE, SIZE)):
			continue
		for key: Vector3i in _by_column[col2]:
			var c: VChunk = chunks.get(key)
			if c != null:
				out.append_array(c.tris)
	return out


## Trilinear density at p (NAN where no built chunk holds it). Main thread.
func density_at(p: Vector3) -> float:
	var key: Vector3i = chunk_of(p)
	var c: VChunk = chunks.get(key)
	if c == null or c.density.is_empty():
		return NAN
	var l: Vector3 = (p - Vector3(key.x, key.y, key.z) * SIZE) / VOXEL
	var i0 := Vector3i(clampi(int(floor(l.x)), 0, N), clampi(int(floor(l.y)), 0, N), clampi(int(floor(l.z)), 0, N))
	var f: Vector3 = (l - Vector3(i0)).clamp(Vector3.ZERO, Vector3.ONE)
	var d: PackedFloat32Array = c.density
	var c00: float = lerpf(d[SurfaceNets.at(N, i0.x, i0.y, i0.z)], d[SurfaceNets.at(N, i0.x + 1, i0.y, i0.z)], f.x)
	var c10: float = lerpf(d[SurfaceNets.at(N, i0.x, i0.y + 1, i0.z)], d[SurfaceNets.at(N, i0.x + 1, i0.y + 1, i0.z)], f.x)
	var c01: float = lerpf(d[SurfaceNets.at(N, i0.x, i0.y, i0.z + 1)], d[SurfaceNets.at(N, i0.x + 1, i0.y, i0.z + 1)], f.x)
	var c11: float = lerpf(d[SurfaceNets.at(N, i0.x, i0.y + 1, i0.z + 1)], d[SurfaceNets.at(N, i0.x + 1, i0.y + 1, i0.z + 1)], f.x)
	return lerpf(lerpf(c00, c10, f.y), lerpf(c01, c11, f.y), f.z)


## The volume ground under pos: scanning the density down from pos (clamped into the column) to
## the first air-to-solid crossing; from inside solid, up to where it opens. NAN outside a
## committed volume column or when no crossing is found. Main thread.
func ground_below(pos: Vector3) -> float:
	var col: Vector2i = column_of(pos.x, pos.z)
	if not committed.has(col) or not columns.has(col):
		return NAN
	var span: Dictionary = columns[col]
	var lo: float = float(int(span["y0"])) * SIZE + VOXEL * 0.5
	var hi: float = float(int(span["y1"]) + 1) * SIZE - VOXEL * 0.5
	var y: float = clampf(pos.y, lo, hi)
	var d0: float = density_at(Vector3(pos.x, y, pos.z))
	if is_nan(d0):
		return NAN
	if d0 <= 0.0:
		while y - VOXEL >= lo:
			var y1: float = y - VOXEL
			var d1: float = density_at(Vector3(pos.x, y1, pos.z))
			if is_nan(d1):
				return NAN
			if d1 > 0.0:
				return y1 + VOXEL * d1 / (d1 - d0)
			y = y1
			d0 = d1
		return NAN
	while y + VOXEL <= hi:
		var y2: float = y + VOXEL
		var d2: float = density_at(Vector3(pos.x, y2, pos.z))
		if is_nan(d2):
			return NAN
		if d2 <= 0.0:
			return y + VOXEL * d0 / (d0 - d2)
		y = y2
		d0 = d2
	return NAN


# --- Persistence --------------------------------------------------------------------------------

## Edited chunks in memory plus the blobs of those that are not, and the dug columns (cave
## columns are derived from the caves on attach, never saved).
func save_into(ws: WorldState) -> void:
	for key: Vector3i in _edited:
		var c: VChunk = chunks.get(key)
		if c == null or c.density.is_empty():
			continue
		ws.chunk_blobs["v:%d_%d_%d" % [key.x, key.y, key.z]] = encode_blob(c.density)
	for key2: Vector3i in _blobs:
		ws.chunk_blobs["v:%d_%d_%d" % [key2.x, key2.y, key2.z]] = _blobs[key2]
	ws.flags["volume_columns"] = _columns_to_array()


func _columns_to_array() -> Array:
	var out: Array = []
	for col: Vector2i in _dug:
		var s: Vector2i = _dug[col]
		out.append([col.x, col.y, s.x, s.y])
	return out


## Decodes the saved columns and blobs. Columns over regions attached now (the boot) are
## activated: their blobs decoded here (a dig must be editable at once), the rest built by jobs;
## the others wait for attach_region.
func load_from(ws: WorldState) -> void:
	for e: Variant in ws.flags.get("volume_columns", []):
		var a: Array = e
		var col := Vector2i(int(a[0]), int(a[1]))
		_dug[col] = _union(_dug.get(col), Vector2i(int(a[2]), int(a[3])))
	var live: Dictionary = {}
	for k: Variant in ws.chunk_blobs.keys():
		var ks: String = str(k)
		if not ks.begins_with("v:"):
			continue
		var p: PackedStringArray = ks.substr(2).split("_")
		var key := Vector3i(int(p[0]), int(p[1]), int(p[2]))
		_blobs[key] = ws.chunk_blobs[k]
		var bcol := Vector2i(key.x, key.z)
		if _is_live_col(bcol):
			live[key] = true
	for key2: Vector3i in live:
		var col2 := Vector2i(key2.x, key2.z)
		var c: VChunk = chunks.get(key2)
		if c == null:
			_columns_lock.lock()
			var had: Dictionary = columns.get(col2, {})
			columns[col2] = {"y0": mini(key2.y, int(had.get("y0", key2.y))), "y1": maxi(key2.y, int(had.get("y1", key2.y)))}
			_columns_lock.unlock()
			_new_chunk(key2, true)
		else:
			_retire(key2)
			_build_now(c)
			_queue(key2, false)
	for col3: Vector2i in _dug:
		if _is_live_col(col3):
			_activate(col3, _dug[col3], false)
