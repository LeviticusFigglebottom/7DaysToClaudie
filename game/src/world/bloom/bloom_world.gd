class_name BloomWorld
extends Node
## Puts the Bloom field on screen (ADR-0025). TerrainManager owns one: it publishes the field as the
## shader globals `hm_bloom_map` / `hm_bloom_rect`, drives the night glow (`hm_bloom_night`) from
## the sun, hands the terrain its mycelium-web textures and keeps the map in step with the dynamic
## spots (rooting mounds, BloomMounds). The globals are cleared on exit, so menus and tools that
## run after a game never show a stale field.
##
## The field is tiled (BloomTiles, ADR-0038 §7) and `hm_bloom_map` is a window of it, `window` m
## square (data/config/bloom.json "field"), around the player: rebuilt on a worker once the player
## is two tiles from its middle, a tile redrawn in it when that tile changes. In a streamed world
## it also composes the missing tiles in the window on a worker, nearest first, and frees the tiles
## more than FREE_MARGIN tiles past the window (keeping those of attached regions).

const WEB_MASK: String = "res://assets/generated/textures/bloom_web_mask.png"
const WEB_NORMAL: String = "res://assets/generated/textures/bloom_web_normal.png"
const WEB_COV: String = "res://assets/generated/textures/bloom_web_cov.png"
## Sun elevations (degrees) between which the threads' glow fades in at dusk: full in deep twilight,
## gone just above the horizon, so it never shows by day and is full once the forest is dark.
const GLOW_FADE: Vector2 = Vector2(-9.0, 3.0)
## Window side when the config sets none (m).
const DEFAULT_WINDOW: float = 3072.0
## How often the window and the tiles are planned (s).
const PLAN_EVERY: float = 0.25
## Tiles composed by one worker task.
const COMPOSE_BATCH: int = 6
## Tiles kept past the window's edge before they are freed (streamed worlds).
const FREE_MARGIN: int = 3

static var _web: Dictionary = {}

var tiles: BloomTiles
## Where the tiles' ground comes from and which regions are attached (null in tests driving it).
var terrain: TerrainManager
## The window's texels in the tiles' grid (what hm_bloom_map holds).
var window := Rect2i()
## Window side in tiles.
var window_tiles: int = 12
var _image: Image
var _texture: ImageTexture
var _night: float = -1.0
var _plan_accum: float = 0.0
var _published: bool = false
## The window being built on a worker: {task, rect, out: [Image], dirty: {key: true}}.
var _win_job: Dictionary = {}
## Tiles being composed on a worker: {task, out: [Tile...], cancel: [bool]}.
var _tile_job: Dictionary = {}
var _uploads: int = 0


## Takes the field and publishes a window of it around `centre` (default: the field's middle). An
## empty field switches the Bloom off in every shader.
## `whole`: the window is the whole grid and never moves (a field composed whole, as the main map's:
## the same texture and rect the whole-map field gave).
func setup(p_tiles: BloomTiles, p_terrain: TerrainManager = null, centre: Vector2 = Vector2(NAN, NAN), cfg: Dictionary = {},
		whole: bool = false) -> void:
	tiles = p_tiles
	terrain = p_terrain
	var side: float = float((cfg.get("field", {}) as Dictionary).get("window", DEFAULT_WINDOW))
	window_tiles = maxi(2, int(ceil(side / (BloomTiles.TILE * tiles.texel))))
	if whole:
		window_tiles = maxi(window_tiles, maxi(tiles.cols, tiles.rows))
	if is_nan(centre.x):
		centre = tiles.rect.get_center()
	window = window_for(centre)
	tiles.take_dirty()
	_image = tiles.window_image(window)
	_publish()


## The window (grid texels) for a player at `p`: `window_tiles` square on whole tiles around p's
## tile, kept inside the grid (all of it when the grid is smaller).
func window_for(p: Vector2) -> Rect2i:
	var c: Vector2i = tiles.tile_of(p.x, p.y)
	var nx: int = mini(window_tiles, tiles.cols)
	var nz: int = mini(window_tiles, tiles.rows)
	var ox: int = clampi(c.x - nx / 2, 0, maxi(tiles.cols - nx, 0))
	var oz: int = clampi(c.y - nz / 2, 0, maxi(tiles.rows - nz, 0))
	var r := Rect2i(ox * BloomTiles.TILE, oz * BloomTiles.TILE, nx * BloomTiles.TILE, nz * BloomTiles.TILE)
	return r.intersection(Rect2i(0, 0, tiles.width, tiles.depth))


## A window (grid texels) as tiles.
func window_tile_rect(w: Rect2i = window) -> Rect2i:
	var a := Vector2i(w.position.x / BloomTiles.TILE, w.position.y / BloomTiles.TILE)
	var b := Vector2i((w.end.x + BloomTiles.TILE - 1) / BloomTiles.TILE, (w.end.y + BloomTiles.TILE - 1) / BloomTiles.TILE)
	return Rect2i(a, b - a)


## Shader global hm_bloom_rect for the window: (x0, z0, 1/width, 1/depth) in metres; zero when
## there is no field.
func shader_rect() -> Vector4:
	if tiles == null or tiles.is_empty() or window.size.x <= 0 or window.size.y <= 0:
		return Vector4.ZERO
	return Vector4(tiles.rect.position.x + window.position.x * tiles.texel, tiles.rect.position.y + window.position.y * tiles.texel,
		1.0 / (window.size.x * tiles.texel), 1.0 / (window.size.y * tiles.texel))


## The window image as it was last uploaded (tests, tools).
func window_image() -> Image:
	return _image


## What the field holds now (tools: stream_walk): tiles, their MB, the window's size in texels.
func status() -> Dictionary:
	if tiles == null:
		return {}
	return {"tiles": tiles.tile_count(), "tile_mb": snappedf(tiles.memory_bytes() / 1048576.0, 0.01),
		"window": window.size, "uploads": _uploads}


## Window uploads so far (tests, tools).
func uploads() -> int:
	return _uploads


func _publish() -> void:
	if tiles == null or tiles.is_empty() or _image == null:
		RenderingServer.global_shader_parameter_set(&"hm_bloom_rect", Vector4.ZERO)
		_published = false
		return
	if _texture == null or Vector2i(_texture.get_width(), _texture.get_height()) != _image.get_size():
		_texture = ImageTexture.create_from_image(_image)
		RenderingServer.global_shader_parameter_set(&"hm_bloom_map", _texture)
	else:
		_texture.update(_image)
	_uploads += 1
	RenderingServer.global_shader_parameter_set(&"hm_bloom_rect", shader_rect())
	_published = true


## Replaces the rooting mounds' spots (BloomMounds): set_spot_source(&"mounds", spots).
func set_spots(spots: Array) -> void:
	set_spot_source(&"mounds", spots)


## Dynamic spots by source ([{pos: Vector2, radius, strength}] each), merged into the field's one
## spot list: the zones are fixed at build (workers read them unlocked), so anything placed or
## removed at runtime (rooting mounds, Bloom nests) is a spot. Only the tiles the old and new
## spots touch are recomposed; they are redrawn next frame (at() reads them at once). An empty
## list removes the source. Fading is calling it again with a lower strength.
func set_spot_source(source: StringName, spots: Array) -> void:
	if spots.is_empty():
		_spot_sources.erase(source)
	else:
		_spot_sources[source] = spots.duplicate(true)
	if tiles == null:
		return
	var keys: Array = _spot_sources.keys()
	keys.sort()
	var all: Array = []
	for k: Variant in keys:
		all.append_array(_spot_sources[k])
	tiles.set_spots(all)


## Source -> its spots (set_spot_source), merged in source order.
var _spot_sources: Dictionary = {}


## Publishes tiles composed elsewhere (TerrainManager.attach_region); redrawn next frame, so an
## attach step doesn't pay for the window's upload.
func install(made: Array) -> void:
	if tiles != null:
		tiles.install(made)


## Redraws the tiles published since the last call that lie in the window and uploads the window
## once (main thread; `force`: upload anyway). A window being built on a worker is told about them.
func redraw(force: bool = false) -> void:
	var dirty: Array = tiles.take_dirty()
	var wt: Rect2i = window_tile_rect()
	var any: bool = false
	for k: Variant in dirty:
		var key: Vector2i = k
		if not _win_job.is_empty():
			(_win_job["dirty"] as Dictionary)[key] = true
		if wt.has_point(key):
			tiles.blit_tile(_image, window.position, key)
			any = true
	# Published when the field gains its first spot, switched off when the last one goes.
	if force or any or _published != (not tiles.is_empty()):
		_publish()


## Dynamic spots by source ([{pos: Vector2, radius, strength}] each), merged into the field's one
## spot list, so the rooting mounds (&"mounds") and the Bloom nests (&"nests", ADR-0055) never
## clobber each other. An empty list removes the source; fading is calling again with a lower
## strength. (Same API as session 3's f5dbc8a; it merges every source into set_spots.)
func set_spot_source(source: StringName, spots: Array) -> void:
	if spots.is_empty():
		_spot_sources.erase(source)
	else:
		_spot_sources[source] = spots.duplicate(true)
	var keys: Array = _spot_sources.keys()
	keys.sort()
	var all: Array = []
	for k: Variant in keys:
		all.append_array(_spot_sources[k])
	set_spots(all)


## Source -> its spots (set_spot_source), merged in source order.
var _spot_sources: Dictionary = {}


func _process(delta: float) -> void:
	var night: float = 0.0
	if Game.session != null and Game.session.clock != null:
		night = night_level(Game.session.clock.sun_elevation_deg())
	if absf(night - _night) > 0.002:
		_night = night
		RenderingServer.global_shader_parameter_set(&"hm_bloom_night", night)
	if tiles == null:
		return
	var t0: int = Time.get_ticks_usec()
	collect()
	_plan_accum += delta
	if _plan_accum >= PLAN_EVERY:
		_plan_accum = 0.0
		var focus: Node3D = terrain.focus if terrain != null and is_instance_valid(terrain.focus) else null
		if focus != null:
			plan(Vector2(focus.global_position.x, focus.global_position.z))
	StreamMeter.note("bloom", t0)


## Takes finished worker jobs and redraws what changed (main thread, every frame). Returns
## whether a job is still running.
func collect() -> bool:
	var swapped: bool = false
	if not _tile_job.is_empty() and WorkerThreadPool.is_task_completed(int(_tile_job["task"])):
		WorkerThreadPool.wait_for_task_completion(int(_tile_job["task"]))
		var out: Array = _tile_job["out"]
		_tile_job = {}
		tiles.install(out)
	if not _win_job.is_empty() and WorkerThreadPool.is_task_completed(int(_win_job["task"])):
		WorkerThreadPool.wait_for_task_completion(int(_win_job["task"]))
		var job: Dictionary = _win_job
		_win_job = {}
		window = job["rect"]
		_image = (job["out"] as Array)[0]
		# Tiles published while it was being built were drawn into the old window only.
		var wt: Rect2i = window_tile_rect()
		for k: Variant in (job["dirty"] as Dictionary):
			if wt.has_point(k):
				tiles.blit_tile(_image, window.position, k)
		swapped = true
	redraw(swapped)
	return not _tile_job.is_empty() or not _win_job.is_empty()


## Moves the window with the player at `p` and, in a streamed world, composes and frees tiles
## around it (main thread; the work runs on workers).
func plan(p: Vector2) -> void:
	var c: Vector2i = tiles.tile_of(p.x, p.y)
	var want: Rect2i = window_for(p)
	var wt: Rect2i = window_tile_rect()
	var mid: Vector2 = Vector2(wt.position) + Vector2(wt.size) * 0.5 - Vector2(0.5, 0.5)
	var off: bool = absf(c.x - mid.x) >= 2.0 or absf(c.y - mid.y) >= 2.0
	if _win_job.is_empty() and want != window and off:
		_start_window(want)
	if not tiles.lazy:
		return
	var target: Rect2i = window_tile_rect(_win_job["rect"] if not _win_job.is_empty() else window)
	if _tile_job.is_empty():
		var keys: Array = tiles.missing(target.grow(1), c)
		if not keys.is_empty():
			_start_compose(keys.slice(0, COMPOSE_BATCH))
	tiles.free_far(c, window_tiles / 2 + 1 + FREE_MARGIN, _keep_tile)


## Tiles of attached regions stay (their 1 m masks came with the attach).
func _keep_tile(key: Vector2i) -> bool:
	if terrain == null:
		return false
	var c: Vector2 = tiles.tile_rect(key).get_center()
	return terrain.region_terrain_at(c.x, c.y) != null


func _start_window(rect: Rect2i) -> void:
	var out: Array = [null]
	var t: BloomTiles = tiles
	var task: int = WorkerThreadPool.add_task(func() -> void: out[0] = t.window_image(rect), false, "bloom window")
	_win_job = {"task": task, "rect": rect, "out": out, "dirty": {}}


## Composes tiles on a worker, each masked by the ground it lies on now (the region's 1 m mask
## when attached, else its 16 m one).
func _start_compose(keys: Array) -> void:
	var jobs: Array = []
	for k: Variant in keys:
		var key: Vector2i = k
		var tr: Rect2 = tiles.tile_rect(key)
		var ground: Dictionary = {}
		if terrain != null:
			# Every region the tile lies on (one where regions are whole tiles, as 1024 m ones are).
			var h: float = tiles.texel * 0.5
			for q: Vector2 in [tr.position + Vector2(h, h), Vector2(tr.end.x - h, tr.position.y + h),
					Vector2(tr.position.x + h, tr.end.y - h), tr.end - Vector2(h, h)]:
				var rt: RegionTerrain = terrain.ground_terrain_at(q.x, q.y)
				if rt != null:
					ground[rt.region_id] = rt
		jobs.append([key, ground])
	var out: Array = []
	var cancel: Array = [false]
	var t: BloomTiles = tiles
	var work := func() -> void:
		for j: Array in jobs:
			if bool(cancel[0]):
				return
			out.append(t.compose_tile(j[0], j[1]))
	var task: int = WorkerThreadPool.add_task(work, false, "bloom tiles")
	_tile_job = {"task": task, "out": out, "cancel": cancel}


## Joins the workers (a task still running at shutdown aborts the engine) and switches the Bloom off.
func _exit_tree() -> void:
	if not _tile_job.is_empty():
		(_tile_job["cancel"] as Array)[0] = true
		WorkerThreadPool.wait_for_task_completion(int(_tile_job["task"]))
		_tile_job = {}
	if not _win_job.is_empty():
		WorkerThreadPool.wait_for_task_completion(int(_win_job["task"]))
		_win_job = {}
	RenderingServer.global_shader_parameter_set(&"hm_bloom_rect", Vector4.ZERO)
	RenderingServer.global_shader_parameter_set(&"hm_bloom_night", 0.0)


## How much the threads glow (0..1) at a sun elevation (degrees).
static func night_level(sun_elevation_deg: float) -> float:
	return 1.0 - smoothstep(GLOW_FADE.x, GLOW_FADE.y, sun_elevation_deg)


## Binds the mycelium-web textures to a terrain material (near chunks; generated textures, or a
## procedural stand-in before `make assets`).
static func apply_web(mat: ShaderMaterial) -> void:
	if _web.is_empty():
		var mask: Texture2D = load(WEB_MASK) if ResourceLoader.exists(WEB_MASK) else null
		var nrm: Texture2D = load(WEB_NORMAL) if ResourceLoader.exists(WEB_NORMAL) else null
		var cov: Texture2D = load(WEB_COV) if ResourceLoader.exists(WEB_COV) else null
		if mask == null or nrm == null or cov == null:
			var fb: Array[Texture2D] = _fallback_web()
			mask = fb[0]
			nrm = fb[1]
			cov = fb[2]
		_web = {"mask": mask, "normal": nrm, "cov": cov}
	mat.set_shader_parameter("bloom_web_mask", _web["mask"])
	mat.set_shader_parameter("bloom_web_normal", _web["normal"])
	mat.set_shader_parameter("bloom_web_cov", _web["cov"])


## A crude web from cellular noise (cell borders as threads), so the terrain still shows the Bloom
## before the generated textures exist. Channels as the generated mask: R priority, G age, B mat,
## A thread body; and its coverage map (the threads the shader's thresholds reveal at a third, two
## thirds and all of full growth, for bloom_web_cover 0.33).
static func _fallback_web() -> Array[Texture2D]:
	var size: int = 256
	var cells := FastNoiseLite.new()
	cells.noise_type = FastNoiseLite.TYPE_CELLULAR
	cells.cellular_return_type = FastNoiseLite.RETURN_DISTANCE2_SUB
	cells.frequency = 0.045
	cells.seed = 2501
	var soft := FastNoiseLite.new()
	soft.frequency = 0.02
	soft.seed = 2502
	var img := Image.create(size, size, false, Image.FORMAT_RGBA8)
	var cov := Image.create(size, size, false, Image.FORMAT_RGBA8)
	for y: int in size:
		for x: int in size:
			var edge: float = 1.0 - clampf(absf(cells.get_noise_2d(x, y)) * 6.0, 0.0, 1.0)
			var s: float = soft.get_noise_2d(x, y) * 0.5 + 0.5
			img.set_pixel(x, y, Color(edge * 0.9, s, clampf(s * 1.4 - 0.5, 0.0, 1.0), edge))
			var e: float = edge * 0.9
			cov.set_pixel(x, y, Color(float(e > 0.89), float(e > 0.78), float(e > 0.67), float(e > 0.67)))
	img.generate_mipmaps()
	cov.generate_mipmaps()
	var flat := Image.create(4, 4, false, Image.FORMAT_RGB8)
	flat.fill(Color(0.5, 0.5, 1.0))
	flat.generate_mipmaps()
	var out: Array[Texture2D] = [ImageTexture.create_from_image(img), ImageTexture.create_from_image(flat), ImageTexture.create_from_image(cov)]
	return out
