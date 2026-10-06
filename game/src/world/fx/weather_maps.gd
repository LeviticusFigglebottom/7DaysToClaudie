class_name WeatherMaps
extends RefCounted
## The weather map round the camera (ADR-0033), published as the shader globals hm_weather_map
## (RGBA half floats, bilinear, mipmapped) over hm_weather_rect = (x0, z0, 1 / size, base): heights
## are stored relative to `base` (the ground at the map's centre, whole metres), so half floats
## keep centimetres. Channels:
##   R  where rain and snow land: the roof, ground or water surface under the sky (downward rays,
##      within the inner `catch_cells`; the ground or water beyond them)
##   G  the ground (terrain heights)
##   B  the ground smoothed over `hollow_m`: puddles collect where G lies below it, and ground fog
##      reads its mips for the low ground it pools in
##   A  the water surface (lakes and rivers), or -1000 where there is none
## The heights come from a thread of the map's own (TerrainManager.height_at and
## WaterSystem.water_level_at only read data): a WorkerThreadPool task queued behind a jump's
## streaming (terrain chunks, vegetation scatter) could wait minutes. The rays run on the main
## thread, `rays_per_frame` a frame. The published map stays in place until a new one is complete,
## so every frame sees one consistent map. Eave drip points are found on it: roof cells standing
## over open ground beside them.

const NO_WATER: float = -1000.0
## A box standing on the ground that is narrower than SHELTER_MIN_M and lower than SHELTER_LOW_M
## (a barrel, a road barricade, a mailbox) keeps no rain off the ground round it: the rays look
## past it. Each one stood in a dry disc a map cell wide on a wet road. A car (1.8 m wide) still
## shelters what is under it.
const SHELTER_MIN_M: float = 1.2
const SHELTER_LOW_M: float = 1.6

var cells: int = 128
var cell_m: float = 1.5
var catch_cells: int = 48
var rays_per_frame: int = 192
var recentre_m: float = 16.0
var hollow_m: float = 9.0

## The published map: its world origin (x0, z0), the height its values are relative to, image and
## texture.
var origin := Vector2(INF, INF)
var base: float = 0.0
var image: Image
var texture: ImageTexture
## The low ground round the camera (a low percentile of the smoothed ground), for far fog.
var valley: float = 0.0
## Eave drip points: [Vector3 eave, Vector3 along-edge, float drop height] on the published map.
var eaves: Array = []

var _terrain: Object
var _water: Object
var _thread: Thread
var _next_origin := Vector2.ZERO
var _ground := PackedFloat32Array()
var _smooth := PackedFloat32Array()
var _wat := PackedFloat32Array()
var _catch := PackedFloat32Array()
var _ray_i: int = -1
var _ray_top: float = 0.0
var _next_base: float = 0.0
var _next_valley: float = 0.0
## The next map's texels (RGBA floats, row-major), filled by the worker and the rays.
var _rgba := PackedFloat32Array()
var _query: PhysicsRayQueryParameters3D


func configure(cfg: Dictionary) -> void:
	cells = maxi(16, int(cfg.get("cells", cells)))
	cell_m = maxf(0.25, float(cfg.get("cell_m", cell_m)))
	catch_cells = clampi(int(cfg.get("catch_cells", catch_cells)), 0, cells)
	rays_per_frame = maxi(1, int(cfg.get("rays_per_frame", rays_per_frame)))
	recentre_m = float(cfg.get("recentre_m", recentre_m))
	hollow_m = float(cfg.get("hollow_m", hollow_m))


func is_ready() -> bool:
	return texture != null


## True when the published map is the one round `p` (centred within recentre_m of it), so no
## rebuild is due there. After a jump (a respawn, a QA shot) the last place's map stays published
## until the new one is complete: the heights' thread and a dozen frames of rays.
func covers(p: Vector3) -> bool:
	if texture == null:
		return false
	var size: float = float(cells) * cell_m
	return Vector2(p.x, p.z).distance_to(origin + Vector2(size, size) * 0.5) <= recentre_m + cell_m


## World rect of the published map as the shaders read it: (x0, z0, 1 / size, base height); zero
## if none.
func shader_rect() -> Vector4:
	if texture == null:
		return Vector4.ZERO
	var size: float = float(cells) * cell_m
	return Vector4(origin.x, origin.y, 1.0 / size, base)


## Rain lands here: roof, ground or water (the map's R), or -INF off the map.
func catch_at(x: float, z: float) -> float:
	if image == null:
		return -INF
	var i: int = floori((x - origin.x) / cell_m)
	var j: int = floori((z - origin.y) / cell_m)
	if i < 0 or j < 0 or i >= cells or j >= cells:
		return -INF
	return image.get_pixel(i, j).r + base


## Keeps the map round `focus`: starts a rebuild when the camera has moved recentre_m from the
## centre, casts this frame's share of rays, and publishes a finished map. Main thread only.
## Returns true when a new map was published this frame.
func update(focus: Vector3, terrain: Object, water: Object, space: PhysicsDirectSpaceState3D) -> bool:
	_terrain = terrain
	_water = water
	if terrain == null:
		return false
	var size: float = float(cells) * cell_m
	var centre: Vector2 = origin + Vector2(size, size) * 0.5
	if _thread == null and _ray_i < 0 and (origin.x == INF or Vector2(focus.x, focus.z).distance_to(centre) > recentre_m):
		# Snap to the cell grid so a rebuilt map samples the ground at the same points.
		_next_origin = (Vector2(focus.x, focus.z) - Vector2(size, size) * 0.5).snapped(Vector2(cell_m, cell_m))
		_ray_top = focus.y
		_thread = Thread.new()
		_thread.start(_build_heights)
		return false
	if _thread != null:
		if _thread.is_alive():
			return false
		_thread.wait_to_finish()
		_thread = null
		_ray_i = 0 if space != null and catch_cells > 0 else catch_cells * catch_cells
	if _ray_i >= 0:
		_cast_rays(space)
		if _ray_i >= catch_cells * catch_cells:
			_ray_i = -1
			_publish()
			return true
	return false


## Builds and publishes the map round `focus` now, blocking: the heights' thread is waited on and
## every ray cast at once. For QA captures, whose software frames take seconds while the rays are
## spread over a dozen frames. Returns false if no map could be built (no terrain).
func finish(focus: Vector3, terrain: Object, water: Object, space: PhysicsDirectSpaceState3D) -> bool:
	if terrain == null:
		return false
	var per_frame: int = rays_per_frame
	rays_per_frame = cells * cells
	var end: int = Time.get_ticks_msec() + 120000
	while not (covers(focus) and _thread == null and _ray_i < 0) and Time.get_ticks_msec() < end:
		if not update(focus, terrain, water, space) and _thread != null:
			OS.delay_msec(2)
	rays_per_frame = per_frame
	return covers(focus)


## Waits for the heights' thread (call from _exit_tree).
func shutdown() -> void:
	if _thread != null:
		_thread.wait_to_finish()
		_thread = null


# Worker thread: ground and water heights over the new rect, and the smoothed ground.
func _build_heights() -> void:
	var n: int = cells
	_ground.resize(n * n)
	_wat.resize(n * n)
	for j: int in n:
		var z: float = _next_origin.y + (float(j) + 0.5) * cell_m
		for i: int in n:
			var x: float = _next_origin.x + (float(i) + 0.5) * cell_m
			_ground[j * n + i] = float(_terrain.call(&"height_at", x, z))
			var wl: float = float(_water.call(&"water_level_at", x, z)) if _water != null else -INF
			_wat[j * n + i] = wl if wl > -INF else NO_WATER
	_next_base = roundf(_ground[(n / 2) * n + n / 2])
	_smooth = box_blur(_ground, n, maxi(1, int(round(hollow_m / cell_m * 0.5))))
	# A second pass makes the box a soft tent: no square halos round a pit.
	_smooth = box_blur(_smooth, n, maxi(1, int(round(hollow_m / cell_m * 0.5))))
	# Everything but the rays: rain lands on the ground or the water until a ray finds a roof.
	_catch.resize(n * n)
	_rgba.resize(n * n * 4)
	var lows: PackedFloat32Array = []
	var b: float = _next_base
	for k: int in n * n:
		_catch[k] = maxf(_ground[k], _wat[k])
		_rgba[k * 4] = _catch[k] - b
		_rgba[k * 4 + 1] = _ground[k] - b
		_rgba[k * 4 + 2] = _smooth[k] - b
		_rgba[k * 4 + 3] = (_wat[k] - b) if _wat[k] > NO_WATER else NO_WATER
		if (k % 4) == 0 and ((k / n) % 4) == 0:
			lows.append(minf(_smooth[k], _wat[k] if _wat[k] > NO_WATER else INF))
	lows.sort()
	_next_valley = lows[int(lows.size() * 0.1)] if not lows.is_empty() else 0.0


## Separable box blur of an n x n grid with radius r cells (edges clamp).
static func box_blur(src: PackedFloat32Array, n: int, r: int) -> PackedFloat32Array:
	var tmp := PackedFloat32Array()
	tmp.resize(n * n)
	var out := PackedFloat32Array()
	out.resize(n * n)
	var inv: float = 1.0 / float(2 * r + 1)
	for j: int in n:
		var acc: float = 0.0
		for k: int in range(-r, r + 1):
			acc += src[j * n + clampi(k, 0, n - 1)]
		for i: int in n:
			tmp[j * n + i] = acc * inv
			acc += src[j * n + clampi(i + r + 1, 0, n - 1)] - src[j * n + clampi(i - r, 0, n - 1)]
	for i: int in n:
		var acc2: float = 0.0
		for k: int in range(-r, r + 1):
			acc2 += tmp[clampi(k, 0, n - 1) * n + i]
		for j: int in n:
			out[j * n + i] = acc2 * inv
			acc2 += tmp[clampi(j + r + 1, 0, n - 1) * n + i] - tmp[clampi(j - r, 0, n - 1) * n + i]
	return out


# Main thread: the next rays of the inner catch square, downward from well above the camera.
func _cast_rays(space: PhysicsDirectSpaceState3D) -> void:
	if space == null:
		_ray_i = catch_cells * catch_cells
		return
	if _query == null:
		_query = PhysicsRayQueryParameters3D.new()
		# World, structures and props: roofs, porches, car roofs and bridge decks keep rain off what
		# is under them. Vegetation (13) and water (12) do not: the water level comes from data.
		_query.collision_mask = 1 | 2 | 4
		_query.hit_from_inside = false
	var n: int = cells
	var off: int = (cells - catch_cells) / 2
	var end: int = mini(_ray_i + rays_per_frame, catch_cells * catch_cells)
	while _ray_i < end:
		var ci: int = off + _ray_i % catch_cells
		var cj: int = off + _ray_i / catch_cells
		_ray_i += 1
		var k: int = cj * n + ci
		var x: float = _next_origin.x + (float(ci) + 0.5) * cell_m
		var z: float = _next_origin.y + (float(cj) + 0.5) * cell_m
		var g: float = _ground[k]
		_query.from = Vector3(x, maxf(_ray_top, g) + 45.0, z)
		_query.to = Vector3(x, g - 0.5, z)
		var hit: Dictionary = space.intersect_ray(_query)
		var looks: int = 0
		while not hit.is_empty() and looks < 3 and _small_and_low(hit, g):
			# Rays starting inside a shape miss it (hit_from_inside is off): look on below it.
			_query.from = (hit["position"] as Vector3) - Vector3(0.0, 0.02, 0.0)
			hit = space.intersect_ray(_query)
			looks += 1
		if not hit.is_empty():
			_catch[k] = maxf(float((hit["position"] as Vector3).y), _wat[k])
			_rgba[k * 4] = _catch[k] - _next_base


## True if a ray hit a box standing on the ground (within 0.25 m) that is narrower than
## SHELTER_MIN_M and whose top is under SHELTER_LOW_M above the ground `g`: something too small to
## keep rain off the ground round it. Roofs, decks (off the ground), walls (tall) and cars (wide)
## are not.
static func _small_and_low(hit: Dictionary, g: float) -> bool:
	if float((hit["position"] as Vector3).y) - g > SHELTER_LOW_M:
		return false
	var co: CollisionObject3D = hit.get("collider") as CollisionObject3D
	if co == null:
		return false
	var cs: CollisionShape3D = co.shape_owner_get_owner(co.shape_find_owner(int(hit.get("shape", 0)))) as CollisionShape3D
	var box: BoxShape3D = cs.shape as BoxShape3D if cs != null else null
	if box == null:
		return false
	var b: Basis = cs.global_transform.basis
	var bottom: float = cs.global_position.y - box.size.y * 0.5 * b.y.length()
	return bottom - g < 0.25 and minf(box.size.x * b.x.length(), box.size.z * b.z.length()) < SHELTER_MIN_M


func _publish() -> void:
	var n: int = cells
	var img := Image.create_from_data(n, n, false, Image.FORMAT_RGBAF, _rgba.to_byte_array())
	img.convert(Image.FORMAT_RGBAH)
	img.generate_mipmaps()
	valley = _next_valley
	origin = _next_origin
	base = _next_base
	_find_eaves()
	image = img
	if texture == null or texture.get_width() != n:
		texture = ImageTexture.create_from_image(img)
	else:
		texture.update(img)
	RenderingServer.global_shader_parameter_set(&"hm_weather_map", texture)
	RenderingServer.global_shader_parameter_set(&"hm_weather_rect", shader_rect())


## Roof edges over open ground: a covered cell (rain lands min_drop above the ground) beside an
## open one. The drip point sits on the edge between them, at the roof's height.
var min_drop: float = 1.8


func _find_eaves() -> void:
	eaves.clear()
	var n: int = cells
	var off: int = (cells - catch_cells) / 2
	for cj: int in range(off, off + catch_cells):
		for ci: int in range(off, off + catch_cells):
			var k: int = cj * n + ci
			if _catch[k] - _ground[k] < min_drop:
				continue
			for d: Vector2i in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
				var ni: int = ci + d.x
				var nj: int = cj + d.y
				if ni < 0 or nj < 0 or ni >= n or nj >= n:
					continue
				var nk: int = nj * n + ni
				if _catch[nk] - _ground[nk] > 0.4:
					continue
				var at := Vector3(_next_origin.x + (float(ci) + 0.5 + 0.5 * d.x) * cell_m, _catch[k] - 0.08,
					_next_origin.y + (float(cj) + 0.5 + 0.5 * d.y) * cell_m)
				eaves.append([at, Vector3(absf(float(d.y)), 0.0, absf(float(d.x))), _catch[k] - 0.08 - _catch[nk]])
