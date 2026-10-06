class_name RwgTerrain
extends RefCounted
## The land of a random world (ADR-0031) on a coarse macro grid (tuning `macro_step`, 32 m): the
## shape, its lakes and its rivers. The grid becomes world.json's `macro.corner_heights`, so the
## composer interpolates exactly this land and adds the shared detail noise on top.
##
## Steps (each a pure function of the seed and settings):
##  1. shape: domain-warped rolling noise, ridged ranges under a slow mountain mask, and a tilt
##     across the map that gives the water somewhere to go;
##  2. lakes: irregular basins dug at low, flat spots, their level just under the lowest point of
##     their rim;
##  3. hydrology: priority-flood from the map edge and the lakes fills every other hollow (so no
##     river runs uphill and none needs a levee), gives each cell the cell it drains to and counts
##     the cells draining through it;
##  4. valleys: ground is carved by how much drains through it (a little stream-power erosion),
##     blurred so valleys have a floor, then flooded again;
##  5. rivers: the drainage cells past a catchment threshold, longest first; a river ends at the
##     map edge, in a lake, or where it meets a river already traced (a tributary). Its level is the
##     filled ground under it, so it falls monotonically to its mouth.

## New ADR-0031 scripts by path, so this compiles before the editor registers their class names.
const GenSettings := preload("res://src/worldgen/rwg/world_gen_settings.gd")

const EPS: float = 0.02
const NB8: Array[Vector2i] = [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1),
	Vector2i(1, 1), Vector2i(-1, 1), Vector2i(1, -1), Vector2i(-1, -1)]

var n: int = 0
var step: float = 32.0
var x0: float = 0.0
var z0: float = 0.0
var width_m: float = 0.0
var h := PackedFloat32Array()
## Lake index per cell (-1: dry).
var lake_of := PackedInt32Array()
## River index per cell a river runs through (-1: none).
var river_of := PackedInt32Array()
## The cell each cell drains to (-1: an outlet, the map edge or a lake).
var down := PackedInt32Array()
## Cells draining through each cell, itself included.
var accum := PackedFloat32Array()
## {id, name, center: Vector2, polygon: PackedVector2Array, level, depth, shore}
var lakes: Array[Dictionary] = []
## {id, name, control: PackedVector2Array, levels: PackedFloat32Array, widths: PackedFloat32Array,
##  depth, bank, valley_width, valley_slope, mouth: "edge" | "lake" | "river", cells: PackedInt32Array}
var rivers: Array[Dictionary] = []
var relief: float = 50.0

var _seed: int = 0


## Milliseconds each step of build() took (ADR-0038's measurements; not part of the world).
var timings: Dictionary = {}
## Called with the fraction (0..1) of build() done, inside its long steps too, so a loading bar
## keeps moving (ADR-0038). Optional; held only while build() runs.
var _progress: Callable = Callable()
var _t_step: int = 0


func build(settings: GenSettings, tun: Dictionary, names: Dictionary, progress: Callable = Callable()) -> void:
	_progress = progress
	_t_step = Time.get_ticks_msec()
	_seed = settings.seed
	step = float(tun.get("macro_step", 32.0))
	width_m = settings.integer("size") * 1024.0
	n = int(round(width_m / step)) + 1
	x0 = -width_m * 0.5
	z0 = -width_m * 0.5
	var prof: Dictionary = (tun.get("terrain", {}) as Dictionary).get(settings.choice("terrain"), {})
	relief = float(prof.get("relief", 50.0))
	h.resize(n * n)
	lake_of.resize(n * n)
	lake_of.fill(-1)
	river_of.resize(n * n)
	river_of.fill(-1)
	_shape(prof, settings.num("roughness"))
	_done("shape", 0.2)
	_place_lakes(settings, tun.get("lakes", {}), names)
	_done("lakes", 0.25)
	_flood(0.25, 0.5)
	_done("flood", 0.5)
	_carve(float(prof.get("carve", 4.0)) * (0.6 + 0.8 * settings.num("roughness")))
	_done("carve", 0.6)
	_flood(0.6, 0.85)
	_done("flood2", 0.85)
	_rivers(settings, tun.get("rivers", {}), names)
	_done("rivers", 1.0)
	# The caller's callable may hold its owner (the generator, which holds this): let it go.
	_progress = Callable()


func _done(step_name: String, f: float) -> void:
	var now: int = Time.get_ticks_msec()
	timings[step_name] = now - _t_step
	_t_step = now
	_report(f)


func _report(f: float) -> void:
	if _progress.is_valid():
		_progress.call(f)


func rng_for(key: String) -> RandomNumberGenerator:
	var r := RandomNumberGenerator.new()
	r.seed = Ids.derive_seed(_seed, "rwg:" + key)
	return r


# --- Grid helpers --------------------------------------------------------------------------------

func pos(c: int) -> Vector2:
	return Vector2(x0 + (c % n) * step, z0 + (c / n) * step)


func cell(x: float, z: float) -> int:
	var i: int = clampi(int(round((x - x0) / step)), 0, n - 1)
	var j: int = clampi(int(round((z - z0) / step)), 0, n - 1)
	return j * n + i


## Bilinear height at world (x, z) (the generator's own queries; the game uses Catmull-Rom on the
## same grid, which agrees to well under a metre on this smooth land).
func height(x: float, z: float) -> float:
	var gx: float = clampf((x - x0) / step, 0.0, n - 1.001)
	var gz: float = clampf((z - z0) / step, 0.0, n - 1.001)
	var i: int = int(gx)
	var j: int = int(gz)
	var fx: float = gx - i
	var fz: float = gz - j
	var k: int = j * n + i
	var top: float = lerpf(h[k], h[k + 1], fx)
	var bot: float = lerpf(h[k + n], h[k + n + 1], fx)
	return lerpf(top, bot, fz)


## Steepest gradient (rise over run) at (x, z) over one cell.
func slope(x: float, z: float) -> float:
	var dx: float = height(x + step, z) - height(x - step, z)
	var dz: float = height(x, z + step) - height(x, z - step)
	return sqrt(dx * dx + dz * dz) / (2.0 * step)


## {min, max, mean} of the ground over a polygon (samples every half cell inside its bounds).
func stats_in(poly: PackedVector2Array) -> Dictionary:
	var bb := Rect2(poly[0], Vector2.ZERO)
	for p: Vector2 in poly:
		bb = bb.expand(p)
	var lo: float = INF
	var hi: float = -INF
	var acc: float = 0.0
	var cnt: int = 0
	var s: float = step * 0.5
	var z: float = bb.position.y
	while z <= bb.end.y + 0.01:
		var x: float = bb.position.x
		while x <= bb.end.x + 0.01:
			if Geometry2D.is_point_in_polygon(Vector2(x, z), poly):
				var v: float = height(x, z)
				lo = minf(lo, v)
				hi = maxf(hi, v)
				acc += v
				cnt += 1
			x += s
		z += s
	for p2: Vector2 in poly:
		var v2: float = height(p2.x, p2.y)
		lo = minf(lo, v2)
		hi = maxf(hi, v2)
		acc += v2
		cnt += 1
	return {"min": lo, "max": hi, "mean": acc / maxf(1.0, cnt)}


## Levels the grid under a polygon to `target`, easing back to the land over `falloff` metres
## outside it (towns and places sit on ground already shaped for them; the composer's pad then
## only trims the detail noise).
func flatten(poly: PackedVector2Array, target: float, falloff: float) -> void:
	var bb := Rect2(poly[0], Vector2.ZERO)
	for p: Vector2 in poly:
		bb = bb.expand(p)
	bb = bb.grow(falloff + step)
	var i0: int = clampi(int(floor((bb.position.x - x0) / step)), 0, n - 1)
	var i1: int = clampi(int(ceil((bb.end.x - x0) / step)), 0, n - 1)
	var j0: int = clampi(int(floor((bb.position.y - z0) / step)), 0, n - 1)
	var j1: int = clampi(int(ceil((bb.end.y - z0) / step)), 0, n - 1)
	for j: int in range(j0, j1 + 1):
		for i: int in range(i0, i1 + 1):
			var c: int = j * n + i
			if lake_of[c] >= 0:
				continue
			var p := Vector2(x0 + i * step, z0 + j * step)
			var d: float = 0.0 if Geometry2D.is_point_in_polygon(p, poly) else _poly_distance(poly, p)
			if d >= falloff:
				continue
			var w: float = 1.0 - smoothstep(0.0, falloff, d)
			h[c] = lerpf(h[c], target, w)


static func _poly_distance(poly: PackedVector2Array, p: Vector2) -> float:
	var best: float = INF
	for k: int in poly.size():
		best = minf(best, p.distance_to(Geometry2D.get_closest_point_to_segment(p, poly[k], poly[(k + 1) % poly.size()])))
	return best


# --- 1. Shape --------------------------------------------------------------------------------------

func _shape(prof: Dictionary, rough: float) -> void:
	var fbm := FastNoiseLite.new()
	fbm.seed = Ids.derive_seed(_seed, "rwg:fbm") & 0x7fffffff
	fbm.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	fbm.fractal_type = FastNoiseLite.FRACTAL_FBM
	fbm.fractal_octaves = 4 + int(round(rough * 2.0))
	fbm.fractal_gain = 0.42 + 0.18 * rough
	fbm.frequency = 1.0 / 1400.0
	fbm.domain_warp_enabled = true
	fbm.domain_warp_type = FastNoiseLite.DOMAIN_WARP_SIMPLEX
	fbm.domain_warp_amplitude = 260.0
	fbm.domain_warp_frequency = 1.0 / 2200.0
	var ridge := FastNoiseLite.new()
	ridge.seed = Ids.derive_seed(_seed, "rwg:ridge") & 0x7fffffff
	ridge.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	ridge.fractal_type = FastNoiseLite.FRACTAL_RIDGED
	ridge.fractal_octaves = 3 + int(round(rough))
	ridge.fractal_gain = 0.42
	ridge.frequency = 1.0 / 1500.0
	ridge.domain_warp_enabled = true
	ridge.domain_warp_amplitude = 180.0
	ridge.domain_warp_frequency = 1.0 / 1600.0
	var mask := FastNoiseLite.new()
	mask.seed = Ids.derive_seed(_seed, "rwg:mask") & 0x7fffffff
	mask.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	mask.fractal_type = FastNoiseLite.FRACTAL_FBM
	mask.fractal_octaves = 2
	mask.frequency = 1.0 / 3200.0
	var r := rng_for("tilt")
	var tilt := Vector2.from_angle(r.randf() * TAU)
	var base: float = float(prof.get("base", 60.0))
	var ridges: float = float(prof.get("ridges", 0.0))
	var tilt_m: float = float(prof.get("tilt", 20.0))
	for j: int in n:
		if j % 64 == 63:
			_report(0.2 * j / n)
		var z: float = z0 + j * step
		for i: int in n:
			var x: float = x0 + i * step
			var b: float = clampf(fbm.get_noise_2d(x, z) * 0.8 + 0.5, 0.0, 1.0)
			var hills: float = b * b * (3.0 - 2.0 * b)
			var m: float = smoothstep(0.38, 0.7, mask.get_noise_2d(x, z) * 0.5 + 0.5)
			var rr: float = clampf(ridge.get_noise_2d(x, z) * 0.5 + 0.5, 0.0, 1.0)
			var t: float = (x * tilt.x + z * tilt.y) / (width_m * 0.5)
			h[j * n + i] = base + relief * hills + ridges * relief * 1.3 * rr * rr * m + tilt_m * t


# --- 2. Lakes --------------------------------------------------------------------------------------

func _place_lakes(settings: GenSettings, cfg: Dictionary, names: Dictionary) -> void:
	var per: float = float((cfg.get("per_region", {}) as Dictionary).get(settings.choice("lakes"), 0.0))
	var regions: int = settings.integer("size") * settings.integer("size")
	var r := rng_for("lakes")
	var want: int = int(floor(per * regions + r.randf()))
	if want <= 0:
		return
	var rad: Array = cfg.get("radius", [70, 190])
	var dep: Array = cfg.get("depth", [5, 12])
	var edge: float = 320.0
	# Low, level spots first: sample candidates, score them, take the best that keep their distance.
	var cands: Array = []
	for k: int in 500:
		var p := Vector2(r.randf_range(x0 + edge, -x0 - edge), r.randf_range(z0 + edge, -z0 - edge))
		var score: float = height(p.x, p.y) + slope(p.x, p.y) * 400.0 + r.randf() * relief * 0.35
		cands.append([score, p])
	cands.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) < float(b[0]))
	var nz := FastNoiseLite.new()
	nz.frequency = 1.6
	var words: Array = names.get("region_words", ["Still"])
	var kinds: Array = names.get("lakes", ["Lake"])
	for cand: Array in cands:
		if lakes.size() >= want:
			break
		var c: Vector2 = cand[1]
		var ok: bool = true
		for l: Dictionary in lakes:
			if (l["center"] as Vector2).distance_to(c) < 720.0:
				ok = false
				break
		if not ok:
			continue
		var radius: float = r.randf_range(float(rad[0]), float(rad[1]))
		var e: float = r.randf_range(0.75, 1.3)
		var rot: float = r.randf() * TAU
		nz.seed = r.randi()
		var poly := PackedVector2Array()
		for k2: int in 40:
			var a: float = TAU * k2 / 40.0
			var m: float = 1.0 + 0.24 * nz.get_noise_2d(cos(a), sin(a))
			poly.append(c + Vector2(cos(a) * radius * e * m, sin(a) * radius / e * m).rotated(rot))
		# The level sits just under the lowest point of the rim (a ring a fifth further out).
		var rim: float = INF
		for p2: Vector2 in poly:
			var q: Vector2 = c + (p2 - c) * 1.22
			rim = minf(rim, height(q.x, q.y))
		var level: float = rim - 0.6
		var depth: float = r.randf_range(float(dep[0]), float(dep[1]))
		var li: int = lakes.size()
		var name: String = "%s %s" % [words[r.randi() % words.size()], kinds[r.randi() % kinds.size()]]
		lakes.append({"id": "lake_%d" % li, "name": name, "center": c, "polygon": poly, "level": snappedf(level, 0.01),
			"depth": snappedf(depth, 0.1), "shore": float(cfg.get("shore", 18.0)), "radius": radius * maxf(e, 1.0 / e)})
		_dig_basin(li, poly, c, level, depth, radius * maxf(e, 1.0 / e))


## Digs a lake's basin into the grid (below its level inside, a rim at least at the level just
## outside) and marks its cells, so the flood drains the land around into it.
func _dig_basin(li: int, poly: PackedVector2Array, c: Vector2, level: float, depth: float, reach: float) -> void:
	var bb := Rect2(c - Vector2(reach, reach) * 1.6, Vector2(reach, reach) * 3.2)
	var i0: int = clampi(int(floor((bb.position.x - x0) / step)), 0, n - 1)
	var i1: int = clampi(int(ceil((bb.end.x - x0) / step)), 0, n - 1)
	var j0: int = clampi(int(floor((bb.position.y - z0) / step)), 0, n - 1)
	var j1: int = clampi(int(ceil((bb.end.y - z0) / step)), 0, n - 1)
	for j: int in range(j0, j1 + 1):
		for i: int in range(i0, i1 + 1):
			var k: int = j * n + i
			var p := Vector2(x0 + i * step, z0 + j * step)
			if Geometry2D.is_point_in_polygon(p, poly):
				var d: float = _poly_distance(poly, p)
				var f: float = clampf(d / maxf(20.0, reach * 0.6), 0.0, 1.0)
				h[k] = minf(h[k], level - 1.0 - depth * f * (2.0 - f))
				lake_of[k] = li
			else:
				var d2: float = _poly_distance(poly, p)
				if d2 < 70.0:
					h[k] = maxf(h[k], level + 0.5 + d2 * 0.015)


# --- 3. Hydrology --------------------------------------------------------------------------------

## Priority-flood: fills every hollow that is not a lake to its spill height (plus a whisker of
## fall), sets each cell's drain and counts the cells draining through it.
func _flood(f0: float = 0.0, f1: float = 0.0) -> void:
	var count: int = n * n
	down.resize(count)
	down.fill(-1)
	accum.resize(count)
	accum.fill(1.0)
	var done := PackedByteArray()
	done.resize(count)
	var fill := h.duplicate()
	var heap := _Heap.new()
	for k: int in count:
		var i: int = k % n
		var j: int = k / n
		if lake_of[k] >= 0:
			fill[k] = float(lakes[lake_of[k]]["level"])
			heap.push(fill[k], k)
			done[k] = 1
		elif i == 0 or j == 0 or i == n - 1 or j == n - 1:
			heap.push(fill[k], k)
			done[k] = 1
	var order := PackedInt32Array()
	order.resize(count)
	var oi: int = 0
	while not heap.is_empty():
		var c: int = heap.pop()
		order[oi] = c
		oi += 1
		if oi % 32768 == 0:
			_report(lerpf(f0, f1, 0.8 * oi / count))
		var ci: int = c % n
		var cj: int = c / n
		var fc: float = fill[c]
		for d: Vector2i in NB8:
			var ni: int = ci + d.x
			var nj: int = cj + d.y
			if ni < 0 or nj < 0 or ni >= n or nj >= n:
				continue
			var nb: int = nj * n + ni
			if done[nb] != 0:
				continue
			done[nb] = 1
			var hv: float = maxf(h[nb], fc + EPS * (1.4142 if d.x != 0 and d.y != 0 else 1.0))
			fill[nb] = hv
			down[nb] = c
			heap.push(hv, nb)
	for k2: int in count:
		if lake_of[k2] < 0:
			h[k2] = fill[k2]
	# Drain each cell down its steepest fall on the filled surface (the flood's own links follow
	# the order cells were reached, which can run a stream along a valley side above the floor).
	# Every filled cell has a lower neighbour, so the links reach an outlet without cycles.
	for k3: int in count:
		if down[k3] < 0:
			continue
		var ci2: int = k3 % n
		var cj2: int = k3 / n
		var best: int = down[k3]
		var best_fall: float = (fill[k3] - fill[best]) / (step * (1.4142 if (best % n) != ci2 and (best / n) != cj2 else 1.0))
		for d2: Vector2i in NB8:
			var ni2: int = ci2 + d2.x
			var nj2: int = cj2 + d2.y
			if ni2 < 0 or nj2 < 0 or ni2 >= n or nj2 >= n:
				continue
			var nb2: int = nj2 * n + ni2
			var fall: float = (fill[k3] - fill[nb2]) / (step * (1.4142 if d2.x != 0 and d2.y != 0 else 1.0))
			if fall > best_fall:
				best_fall = fall
				best = nb2
		down[k3] = best
	# Upstream before downstream: the flood reached cells in rising order of filled height.
	for o: int in range(oi - 1, -1, -1):
		var c2: int = order[o]
		if down[c2] >= 0:
			accum[down[c2]] += accum[c2]


# --- 4. Valleys ----------------------------------------------------------------------------------

func _carve(k: float) -> void:
	if k <= 0.0:
		return
	var count: int = n * n
	var cell_km2: float = step * step / 1.0e6
	var cut := PackedFloat32Array()
	cut.resize(count)
	for c: int in count:
		if lake_of[c] >= 0:
			continue
		var a: float = accum[c] * cell_km2
		cut[c] = k * log(1.0 + a * 20.0) / log(2.0)
	# Two box blurs: valleys get a floor and shoulders instead of one-cell slots.
	for pass_i: int in 2:
		var src: PackedFloat32Array = cut.duplicate()
		for j: int in n:
			for i: int in n:
				var acc: float = 0.0
				var wsum: float = 0.0
				for dj: int in range(-1, 2):
					for di: int in range(-1, 2):
						var ii: int = i + di
						var jj: int = j + dj
						if ii < 0 or jj < 0 or ii >= n or jj >= n:
							continue
						acc += src[jj * n + ii]
						wsum += 1.0
				cut[j * n + i] = acc / wsum
	for c2: int in count:
		if lake_of[c2] < 0:
			h[c2] -= cut[c2]


# --- 5. Rivers -----------------------------------------------------------------------------------

func _rivers(settings: GenSettings, cfg: Dictionary, names: Dictionary) -> void:
	var setting: String = settings.choice("rivers")
	var thr_km2: float = float((cfg.get("catchment", {}) as Dictionary).get(setting, 0.0))
	if thr_km2 <= 0.0:
		return
	var area_km2: float = width_m * width_m / 1.0e6
	var max_count: int = maxi(1, int(round(float((cfg.get("count", {}) as Dictionary).get(setting, 0.1)) * area_km2)))
	var cell_km2: float = step * step / 1.0e6
	var head_cells: float = float(cfg.get("head", 0.06)) / cell_km2
	var count: int = n * n
	# Each cell's biggest upstream neighbour: the main stem when tracing up from a mouth.
	var up_best := PackedInt32Array()
	up_best.resize(count)
	up_best.fill(-1)
	for c: int in count:
		var d: int = down[c]
		if d >= 0 and (up_best[d] < 0 or accum[c] > accum[up_best[d]] or (accum[c] == accum[up_best[d]] and c < up_best[d])):
			up_best[d] = c
	# Mouths: cells draining off the map or into a lake, biggest catchment first.
	var mouths: Array = []
	for c2: int in count:
		if lake_of[c2] >= 0 or accum[c2] * cell_km2 < thr_km2:
			continue
		if down[c2] < 0 or lake_of[down[c2]] >= 0:
			mouths.append([accum[c2], c2])
	mouths.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) > float(b[0]) or (float(a[0]) == float(b[0]) and int(a[1]) < int(b[1])))
	var r := rng_for("rivers")
	var words: Array = names.get("region_words", ["Still"])
	var kinds: Array = names.get("rivers", ["River"])
	var wr: Array = cfg.get("width", [6, 24])
	var dr: Array = cfg.get("depth", [1.6, 2.6])
	var min_len: float = float(cfg.get("min_length", 450.0))
	for m: Array in mouths:
		if rivers.size() >= max_count:
			break
		var mc: int = int(m[1])
		var path: PackedInt32Array = _upstream(mc, up_best, head_cells)
		var mouth: String = "edge"
		if down[mc] >= 0 and lake_of[down[mc]] >= 0:
			path.append(down[mc])
			mouth = "lake"
		if path.size() * step < min_len:
			continue
		_trace(path, mouth, r, words, kinds, wr, dr, cfg)
	# Tributaries: the biggest side streams joining a traced river, while the count allows.
	var trib_cells: float = thr_km2 * 0.6 / cell_km2
	var cands: Array = []
	for ri: int in rivers.size():
		var cells: PackedInt32Array = rivers[ri]["cells"]
		for c3: int in cells:
			if lake_of[c3] >= 0:
				continue
			var ci: int = c3 % n
			var cj: int = c3 / n
			for dd: Vector2i in NB8:
				var ni: int = ci + dd.x
				var nj: int = cj + dd.y
				if ni < 0 or nj < 0 or ni >= n or nj >= n:
					continue
				var nb: int = nj * n + ni
				if down[nb] == c3 and river_of[nb] < 0 and accum[nb] >= trib_cells:
					cands.append([accum[nb], nb, c3])
	cands.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) > float(b[0]) or (float(a[0]) == float(b[0]) and int(a[1]) < int(b[1])))
	for tc: Array in cands:
		if rivers.size() >= max_count:
			break
		if river_of[int(tc[1])] >= 0:
			continue
		var tpath: PackedInt32Array = _upstream(int(tc[1]), up_best, head_cells)
		tpath.append(int(tc[2]))
		if tpath.size() * step < min_len * 0.8:
			continue
		_trace(tpath, "river", r, words, kinds, wr, dr, cfg)


## The main stem above `mouth` up to where its catchment falls under `head_cells`, head first.
func _upstream(mouth: int, up_best: PackedInt32Array, head_cells: float) -> PackedInt32Array:
	var rev := PackedInt32Array([mouth])
	var c: int = mouth
	while true:
		var u: int = up_best[c]
		if u < 0 or accum[u] < head_cells or river_of[u] >= 0 or lake_of[u] >= 0:
			break
		rev.append(u)
		c = u
	rev.reverse()
	return rev


## Turns a drainage path into a river: control points along it, levels from the filled ground
## (monotone to the mouth), widths from the catchment, and a carved bed in the grid.
func _trace(path: PackedInt32Array, mouth: String, r: RandomNumberGenerator, words: Array, kinds: Array, wr: Array, dr: Array, cfg: Dictionary) -> void:
	var ri: int = rivers.size()
	var cell_km2: float = step * step / 1.0e6
	var mouth_level: float = -INF
	var last: int = path[path.size() - 1]
	if mouth == "lake":
		mouth_level = float(lakes[lake_of[last]]["level"])
	elif mouth == "river":
		mouth_level = _river_level_at_cell(river_of[last], last)
	# Cell-path levels and widths, with the distance along the path.
	var dist := PackedFloat32Array()
	var lv := PackedFloat32Array()
	var wd := PackedFloat32Array()
	var acc_d: float = 0.0
	var run_min: float = INF
	for k: int in path.size():
		var c: int = path[k]
		if k > 0:
			acc_d += pos(c).distance_to(pos(path[k - 1]))
		dist.append(acc_d)
		var level: float = h[c] - 0.9
		if mouth == "lake" and k == path.size() - 1:
			level = mouth_level
		run_min = minf(run_min, maxf(level, mouth_level))
		lv.append(run_min)
		var a: float = accum[c] * cell_km2
		wd.append(clampf(float(wr[0]) + (float(wr[1]) - float(wr[0])) * sqrt(a / 25.0), float(wr[0]), float(wr[1])))
	# Carve the bed into the grid and mark the cells (roads pay to cross them). The banks beside it
	# come down toward the water, but never another river's bed (on a steep stretch a lower cell's
	# bank would otherwise cut under the water upstream).
	for k3: int in path.size():
		var c6: int = path[k3]
		if lake_of[c6] >= 0:
			continue
		if river_of[c6] < 0:
			river_of[c6] = ri
		h[c6] = minf(h[c6], lv[k3] + 0.4)
	for k4: int in path.size():
		var c8: int = path[k4]
		if lake_of[c8] >= 0:
			continue
		var ci: int = c8 % n
		var cj: int = c8 / n
		for d: Vector2i in NB8:
			var ni: int = ci + d.x
			var nj: int = cj + d.y
			if ni < 0 or nj < 0 or ni >= n or nj >= n:
				continue
			var nb: int = nj * n + ni
			if lake_of[nb] < 0 and river_of[nb] < 0:
				h[nb] = minf(h[nb], lv[k4] + 0.4 + step * 0.12)
	# Control points every third cell, nudged off the grid's diagonals a little.
	var ctrl := PackedVector2Array()
	var nz := FastNoiseLite.new()
	nz.seed = r.randi()
	nz.frequency = 0.004
	for k2: int in path.size():
		if k2 % 3 != 0 and k2 != path.size() - 1:
			continue
		var p: Vector2 = pos(path[k2])
		if k2 > 0 and k2 < path.size() - 1:
			var tdir: Vector2 = (pos(path[mini(k2 + 1, path.size() - 1)]) - pos(path[maxi(k2 - 1, 0)])).normalized()
			p += Vector2(-tdir.y, tdir.x) * nz.get_noise_2d(p.x, p.y) * 9.0
		ctrl.append(p)
	# Off the map edge a little, so the water does not stop at the last region's border.
	if mouth == "edge" and ctrl.size() >= 2:
		var out: Vector2 = (ctrl[ctrl.size() - 1] - ctrl[ctrl.size() - 2]).normalized()
		ctrl.append(ctrl[ctrl.size() - 1] + out * 60.0)
	elif mouth == "lake":
		# Into the lake a way, so the river mouth and the lake meet in open water.
		var lake_c: Vector2 = lakes[lake_of[last]]["center"]
		var p_end: Vector2 = ctrl[ctrl.size() - 1]
		ctrl.append(p_end + (lake_c - p_end).normalized() * 24.0)
	if ctrl.size() < 2:
		return
	var line: Polyline2 = Polyline2.from_array(_arr(ctrl))
	var total: float = maxf(1.0, line.total_length)
	var samples: int = clampi(int(ceil(total / 20.0)) + 1, 2, 400)
	var levels := PackedFloat32Array()
	var widths := PackedFloat32Array()
	# Each sample of the smoothed line takes the level of the cell path where it actually is (its
	# closest point on the path), not of the same fraction of the path's length: the two lengths
	# differ, and on a steep stretch that put the water metres above the land.
	var cell_pts: Array = []
	for c7: int in path:
		var cp: Vector2 = pos(c7)
		cell_pts.append([cp.x, cp.y])
	var cell_line: Polyline2 = Polyline2.from_array(cell_pts, 0.0)
	var prev: float = INF
	for s: int in samples:
		var at: Vector2 = line.point_at(total * float(s) / (samples - 1))
		var dd: float = cell_line.closest(at).y if cell_line.points.size() > 1 else 0.0
		# Never above the ground under the line itself (it can cut a bend across lower ground).
		var v: float = minf(_interp(dist, lv, dd), maxf(height(at.x, at.y) - 0.9, mouth_level))
		prev = minf(prev, v)
		levels.append(snappedf(prev, 0.01))
		widths.append(snappedf(_interp(dist, wd, dd), 0.1))
	if mouth != "edge":
		levels[levels.size() - 1] = snappedf(mouth_level, 0.01)
	var wmax: float = 0.0
	for w: float in widths:
		wmax = maxf(wmax, w)
	var depth: float = lerpf(float(dr[0]), float(dr[1]), clampf((wmax - float(wr[0])) / maxf(1.0, float(wr[1]) - float(wr[0])), 0.0, 1.0))
	var name: String = "%s %s" % [words[r.randi() % words.size()], kinds[r.randi() % kinds.size()]]
	rivers.append({"id": "river_%d" % ri, "name": name, "control": ctrl, "line": line, "levels": levels, "widths": widths,
		"depth": snappedf(depth, 0.1), "bank": float(cfg.get("bank", 6.0)), "valley_width": snappedf(90.0 + wmax * 3.0, 1.0),
		"valley_slope": 0.16, "mouth": mouth, "cells": path, "cell_levels": lv})


func _river_level_at_cell(ri: int, c: int) -> float:
	var rv: Dictionary = rivers[ri]
	var cells: PackedInt32Array = rv["cells"]
	var lv: PackedFloat32Array = rv["cell_levels"]
	var k: int = cells.find(c)
	return lv[k] if k >= 0 else h[c] - 0.9


static func _interp(xs: PackedFloat32Array, ys: PackedFloat32Array, x: float) -> float:
	if xs.size() == 1 or x <= xs[0]:
		return ys[0]
	for k: int in range(1, xs.size()):
		if xs[k] >= x:
			var t: float = (x - xs[k - 1]) / maxf(0.001, xs[k] - xs[k - 1])
			return lerpf(ys[k - 1], ys[k], t)
	return ys[ys.size() - 1]


static func _arr(pts: PackedVector2Array) -> Array:
	var out: Array = []
	for p: Vector2 in pts:
		out.append([snappedf(p.x, 0.1), snappedf(p.y, 0.1)])
	return out


## Distance from (x, z) to the nearest river centre line minus its half width, and to the nearest
## lake edge (negative inside): how far a place is from the water.
func water_distance(p: Vector2) -> float:
	var best: float = INF
	for rv: Dictionary in rivers:
		var line: Polyline2 = rv["line"]
		if not line.bounds.grow(400.0).has_point(p):
			continue
		var q: Vector3 = line.closest(p)
		best = minf(best, q.x - line.value_at(Array(rv["widths"]), q.y) * 0.5)
	for l: Dictionary in lakes:
		var poly: PackedVector2Array = l["polygon"]
		if (l["center"] as Vector2).distance_to(p) > float(l["radius"]) * 1.6 + 400.0:
			continue
		var d: float = _poly_distance(poly, p)
		best = minf(best, -d if Geometry2D.is_point_in_polygon(p, poly) else d)
	return best


## Binary min-heap of (float priority, int cell): the flood's queue.
class _Heap:
	var prio := PackedFloat32Array()
	var vals := PackedInt32Array()
	var size: int = 0

	func is_empty() -> bool:
		return size == 0

	func push(p: float, v: int) -> void:
		if size >= prio.size():
			prio.resize(maxi(64, size * 2))
			vals.resize(maxi(64, size * 2))
		var i: int = size
		size += 1
		while i > 0:
			var par: int = (i - 1) >> 1
			if prio[par] < p or (prio[par] == p and vals[par] <= v):
				break
			prio[i] = prio[par]
			vals[i] = vals[par]
			i = par
		prio[i] = p
		vals[i] = v

	func pop() -> int:
		var top: int = vals[0]
		size -= 1
		if size == 0:
			return top
		var p: float = prio[size]
		var v: int = vals[size]
		var i: int = 0
		while true:
			var l: int = i * 2 + 1
			if l >= size:
				break
			var m: int = l
			if l + 1 < size and (prio[l + 1] < prio[l] or (prio[l + 1] == prio[l] and vals[l + 1] < vals[l])):
				m = l + 1
			if prio[m] > p or (prio[m] == p and vals[m] >= v):
				break
			prio[i] = prio[m]
			vals[i] = vals[m]
			i = m
		prio[i] = p
		vals[i] = v
		return top
