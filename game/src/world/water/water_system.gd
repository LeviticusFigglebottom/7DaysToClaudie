class_name WaterSystem
extends Node3D
## Builds lake and river surfaces from region metadata and answers water-level queries.

const RIVER_EXTRA: float = 3.0
const LAKE_OFFSET: float = 3.5
## Cell size of the river segment index behind water_level_at().
const GRID: float = 32.0
## Distances (m) probed for the nearest forest when measuring a vertex's tree line, and the
## canopy that counts as forest.
const TREE_PROBES: PackedFloat32Array = [12.0, 24.0, 40.0, 60.0, 85.0, 120.0, 170.0]
const FOREST_CANOPY: float = 0.35
## Tree-line elevation (sine) with no forest in reach: distant hills and forest.
const FAR_TREE_LINE: float = 0.035
const NO_LAKES: Array = []

var world: Node
var _lakes: Array[Dictionary] = []
var _rivers: Array[Dictionary] = []
## Grid cell -> Array of Vector2i(river index, segment index) whose wetted width reaches into the
## cell. water_level_at() runs every physics frame for the player, for every Hollow's swim check
## and along interaction rays; scanning every segment of every river each time was the cost.
var _river_grid: Dictionary = {}
var _lake_mat: ShaderMaterial
var _river_mat: ShaderMaterial
## Fen pools (lakes whose id starts "fen_", ADR-0041): tea-dark tannin water.
var _tannin_mat: ShaderMaterial
## Grid cell -> indices into _lakes whose bounds reach the cell, ascending, so water_level_at() tests
## only the lakes near a point (the first that holds it wins, as it did over the whole list). A fen
## puts dozens of small pools in a world, and the vegetation scatter asks about every plant.
var _lake_grid: Dictionary = {}
## Set by setup_world; null in tests, where water reflects a uniform tree line.
var _terrain: TerrainManager


func setup_world(w: Node) -> void:
	world = w
	_terrain = w.terrain
	_lake_mat = _make_material(0.0)
	_river_mat = _make_material(0.35)
	_tannin_mat = _make_material(0.0)
	_tannin_mat.set_shader_parameter("shallow_color", Color(0.16, 0.105, 0.05))
	_tannin_mat.set_shader_parameter("deep_color", Color(0.028, 0.017, 0.008))
	_tannin_mat.set_shader_parameter("absorption", 1.6)
	_tannin_mat.set_shader_parameter("treeline", 0.95)
	# Still water in the peat: no surf at the edge, the margin just goes dark and wet. (The foam band
	# is measured in view depth: 8 cm still showed a white smear at a pool's near edge, eye level.)
	_tannin_mat.set_shader_parameter("foam_width", 0.015)
	_tannin_mat.set_shader_parameter("normal_strength", 0.35)
	var seen: Dictionary = {}
	var river_parts: Dictionary = {}
	var terrain: TerrainManager = w.terrain
	var all: Array = []
	for rid: String in terrain.regions:
		all.append(terrain.regions[rid])
	for rid: String in terrain.coarse:
		all.append(terrain.coarse[rid])
	for rt: RegionTerrain in all:
		for wb: Dictionary in rt.water:
			var key: String = str(wb["kind"]) + ":" + str(wb["id"])
			if wb["kind"] == "lake":
				if seen.has(key):
					continue
				seen[key] = true
				_todo.append(_add_lake.bind(wb))
			else:
				# Same world river sampled at identical arc lengths in every region: merge by arc.
				var parts: Dictionary = river_parts.get(str(wb["id"]), {})
				for i: int in (wb["points"] as Array).size():
					var arc: int = int(round(float(wb.get("arcs", [])[i]) if wb.has("arcs") else float(i)))
					parts[arc] = [wb["points"][i], wb["widths"][i], wb["levels"][i]]
				river_parts[str(wb["id"])] = parts
	for rid: String in river_parts:
		var parts: Dictionary = river_parts[rid]
		var keys: Array = parts.keys()
		keys.sort()
		var merged: Dictionary = {"id": rid, "points": [], "widths": [], "levels": []}
		for k: int in keys:
			merged["points"].append(parts[k][0])
			merged["widths"].append(parts[k][1])
			merged["levels"].append(parts[k][2])
		_todo.append(_add_river_piece.bind(merged))
	# A tool or test without a booting world gets every body of water now.
	if not (w.has_method(&"is_booting") and bool(w.call(&"is_booting"))):
		for c: Callable in _todo:
			c.call()
		_todo.clear()


## Lakes and river pieces still to build: a 10 km world has dozens, about 2.6 s in one frame.
var _todo: Array[Callable] = []
## Main-thread time the boot step spends on them per frame.
const BOOT_SLICE_MS: float = 30.0


## The water bodies as one boot step, a few a frame (GameWorld runs it right after this module's).
func boot_steps() -> Array:
	if _todo.is_empty():
		return []
	return [["Filling the rivers…", func() -> bool:
		var t0: int = Time.get_ticks_usec()
		while not _todo.is_empty():
			var c: Callable = _todo.pop_front()
			c.call()
			if float(Time.get_ticks_usec() - t0) / 1000.0 >= BOOT_SLICE_MS:
				break
		return _todo.is_empty(), "water bodies"]]


func _make_material(flow: float) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = load("res://assets/shaders/water.gdshader")
	var base: String = "res://assets/generated/textures/"
	var na: Texture2D = load(base + "water_normal_a.png") if ResourceLoader.exists(base + "water_normal_a.png") else _noise_normal(11)
	var nb: Texture2D = load(base + "water_normal_b.png") if ResourceLoader.exists(base + "water_normal_b.png") else _noise_normal(23)
	m.set_shader_parameter("normal_a", na)
	m.set_shader_parameter("normal_b", nb)
	if ResourceLoader.exists(base + "water_foam.png"):
		m.set_shader_parameter("foam_tex", load(base + "water_foam.png"))
	m.set_shader_parameter("flow_speed", flow)
	return m


## Fallback normal maps (no generated assets), by seed: shared by every water material and kept
## for the process, so a reload doesn't make them again.
static var _noise_normals: Dictionary = {}
## Worker tasks generating them, not yet joined.
static var _noise_tasks: PackedInt64Array = []


## A flat normal map now, the generated one when a worker has made it (TD-197). A NoiseTexture2D
## makes its first image synchronously in the next deferred-call flush: 512² seamless with
## mipmaps is ~70 ms, and six of them made one ~410 ms load frame after the water module (and
## again on every reload).
static func _noise_normal(seed: int) -> Texture2D:
	if _noise_normals.has(seed):
		return _noise_normals[seed]
	var flat := Image.create_empty(1, 1, false, Image.FORMAT_RGBA8)
	flat.fill(Color(0.5, 0.5, 1.0))
	var tex := ImageTexture.create_from_image(flat)
	_noise_normals[seed] = tex
	# Joined by _exit_tree; set_image runs on the main thread (call_deferred from the worker).
	_noise_tasks.append(WorkerThreadPool.add_task(func() -> void:
		tex.set_image.call_deferred(_noise_normal_image(seed)), false, "water normals"))
	return tex


## What NoiseTexture2D made with these settings (seamless, normal map, bump 6, mipmaps).
static func _noise_normal_image(seed: int) -> Image:
	var nz := FastNoiseLite.new()
	nz.seed = seed
	nz.frequency = 0.03
	nz.fractal_octaves = 4
	var img: Image = nz.get_seamless_image(512, 512, false, false, 0.1, true)
	img.bump_map_to_normal_map(6.0)
	img.generate_mipmaps()
	return img


func _exit_tree() -> void:
	for t: int in _noise_tasks:
		WorkerThreadPool.wait_for_task_completion(t)
	_noise_tasks.clear()


func _add_lake(wb: Dictionary) -> void:
	var poly := PackedVector2Array()
	for p: Array in wb["polygon"]:
		poly.append(Vector2(float(p[0]), float(p[1])))
	var grown: Array[PackedVector2Array] = Geometry2D.offset_polygon(poly, LAKE_OFFSET, Geometry2D.JOIN_ROUND)
	var outline: PackedVector2Array = grown[0] if not grown.is_empty() else poly
	var idx: PackedInt32Array = Geometry2D.triangulate_polygon(outline)
	if idx.is_empty():
		return
	var level: float = float(wb["level"])
	var verts := PackedVector3Array()
	var uvs := PackedVector2Array()
	var cols := PackedColorArray()
	for v: Vector2 in outline:
		verts.append(Vector3(v.x, level, v.y))
		uvs.append(v * 0.1)
		cols.append(_tree_line(v.x, v.y, level))
	# triangulate_polygon emits every triangle with a positive (x, z) cross product whatever the
	# outline's winding, and that is clockwise seen from above: a front face, as is. (This used to
	# be flipped, which turned every lake face down, and back-face culling hid it.)
	_add_mesh("Lake_" + str(wb["id"]), verts, uvs, cols, idx, _tannin_mat if str(wb["id"]).begins_with("fen_") else _lake_mat)
	var b: Rect2 = _bounds(poly)
	_lakes.append({"poly": poly, "level": level, "bounds": b})
	for gz: int in range(floori(b.position.y / GRID), floori(b.end.y / GRID) + 1):
		for gx: int in range(floori(b.position.x / GRID), floori(b.end.x / GRID) + 1):
			var key := Vector2i(gx, gz)
			if not _lake_grid.has(key):
				_lake_grid[key] = []
			(_lake_grid[key] as Array).append(_lakes.size() - 1)


func _add_river_piece(wb: Dictionary) -> void:
	var pts: Array = wb["points"]
	var widths: Array = wb["widths"]
	var levels: Array = wb["levels"]
	if pts.size() < 2:
		return
	var verts := PackedVector3Array()
	var uvs := PackedVector2Array()
	var cols := PackedColorArray()
	var idx := PackedInt32Array()
	var along: float = 0.0
	for i: int in pts.size():
		var c := Vector2(float(pts[i][0]), float(pts[i][1]))
		var prev := Vector2(float(pts[maxi(i - 1, 0)][0]), float(pts[maxi(i - 1, 0)][1]))
		var nxt := Vector2(float(pts[mini(i + 1, pts.size() - 1)][0]), float(pts[mini(i + 1, pts.size() - 1)][1]))
		var t: Vector2 = (nxt - prev).normalized()
		var nrm := Vector2(-t.y, t.x)
		var half: float = float(widths[i]) * 0.5 + RIVER_EXTRA
		var lvl: float = float(levels[i])
		if i > 0:
			along += c.distance_to(prev)
		var l: Vector2 = c + nrm * half
		var r: Vector2 = c - nrm * half
		verts.append(Vector3(l.x, lvl, l.y))
		verts.append(Vector3(r.x, lvl, r.y))
		var w: float = half * 2.0
		uvs.append(Vector2(0.0, along / w))
		uvs.append(Vector2(1.0, along / w))
		var tl: Color = _tree_line(c.x, c.y, lvl)
		cols.append(tl)
		cols.append(tl)
		if i > 0:
			# Left bank is +nrm, i.e. counter-clockwise of the flow in (x, z): left, right, next
			# left is clockwise seen from above, so the strip faces up.
			var a: int = (i - 1) * 2
			idx.append_array([a, a + 1, a + 2, a + 1, a + 3, a + 2])
	_add_mesh("River_" + str(wb["id"]), verts, uvs, cols, idx, _river_mat)
	var line := PackedVector2Array()
	for p: Array in pts:
		line.append(Vector2(float(p[0]), float(p[1])))
	_rivers.append({"line": line, "widths": widths, "levels": levels, "bounds": _bounds(line).grow(40.0)})
	var ri: int = _rivers.size() - 1
	for i: int in line.size() - 1:
		var half: float = maxf(float(widths[i]), float(widths[i + 1])) * 0.5
		var r := Rect2(line[i], Vector2.ZERO).expand(line[i + 1]).grow(half)
		for cz: int in range(floori(r.position.y / GRID), floori(r.end.y / GRID) + 1):
			for cx: int in range(floori(r.position.x / GRID), floori(r.end.x / GRID) + 1):
				var cell := Vector2i(cx, cz)
				if not _river_grid.has(cell):
					_river_grid[cell] = []
				(_river_grid[cell] as Array).append(Vector2i(ri, i))


func _add_mesh(name_: String, verts: PackedVector3Array, uvs: PackedVector2Array, cols: PackedColorArray, idx: PackedInt32Array, mat: Material) -> void:
	var arrays: Array = []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts
	arrays[Mesh.ARRAY_TEX_UV] = uvs
	arrays[Mesh.ARRAY_COLOR] = cols
	var normals := PackedVector3Array()
	normals.resize(verts.size())
	normals.fill(Vector3.UP)
	arrays[Mesh.ARRAY_NORMAL] = normals
	var tangents := PackedFloat32Array()
	for i: int in verts.size():
		tangents.append_array([1.0, 0.0, 0.0, 1.0])
	arrays[Mesh.ARRAY_TANGENT] = tangents
	arrays[Mesh.ARRAY_INDEX] = idx
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	var mi := MeshInstance3D.new()
	mi.name = name_
	mi.mesh = mesh
	mi.material_override = mat
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mi)


## How high the far bank's trees stand over the water at (x, z), seen toward +X, +Z, -X and -Z
## (the colour's r, g, b, a): the sine of the elevation of the nearest forest's crown tops, averaged
## over three rays per direction. The water shader reflects them by the reflected ray's heading, so
## a lake in the woods shows a tall dark band and a river through a meadow shows the sky.
func _tree_line(x: float, z: float, level: float) -> Color:
	if _terrain == null:
		return Color(0.24, 0.24, 0.24, 0.24)
	var out := Color()
	for q: int in 4:
		var acc: float = 0.0
		for k: int in 3:
			var ang: float = q * PI * 0.5 + (k - 1) * 0.4
			var dir := Vector2(cos(ang), sin(ang))
			var el: float = FAR_TREE_LINE
			for d: float in TREE_PROBES:
				var px: float = x + dir.x * d
				var pz: float = z + dir.y * d
				var c: float = _terrain.canopy_at(px, pz)
				if c >= FOREST_CANOPY:
					# Crown tops (canopy x canopy height is the crown mass) over the bank.
					var top: float = c * TerrainManager.CANOPY_HEIGHT / TerrainManager.CROWN_MASS_HEIGHT
					var rise: float = maxf(_terrain.height_at(px, pz) - level, 0.0)
					el = maxf(el, sin(atan2(top + rise, d)))
					break
			acc += el
		out[q] = acc / 3.0
	return out


static func _bounds(p: PackedVector2Array) -> Rect2:
	var r := Rect2(p[0], Vector2.ZERO)
	for v: Vector2 in p:
		r = r.expand(v)
	return r


## Water surface height at (x, z), or -INF if there is no water there.
func water_level_at(x: float, z: float) -> float:
	var p := Vector2(x, z)
	for li: int in _lake_grid.get(Vector2i(floori(x / GRID), floori(z / GRID)), NO_LAKES):
		var l: Dictionary = _lakes[li]
		if (l["bounds"] as Rect2).has_point(p) and Geometry2D.is_point_in_polygon(p, l["poly"]):
			return float(l["level"])
	# The nearest river segment whose wetted half-width covers the point.
	var best: float = INF
	var level: float = -INF
	for e: Vector2i in _river_grid.get(Vector2i(floori(x / GRID), floori(z / GRID)), []):
		var r: Dictionary = _rivers[e.x]
		var line: PackedVector2Array = r["line"]
		var d: float = p.distance_to(Geometry2D.get_closest_point_to_segment(p, line[e.y], line[e.y + 1]))
		if d < best and d < float(r["widths"][e.y]) * 0.5:
			best = d
			level = float(r["levels"][e.y])
	return level


## "lake", "river" or "" — what kind of water is at (x, z) (ambience, fishing later).
func kind_at(pos: Vector3) -> String:
	var p := Vector2(pos.x, pos.z)
	for li: int in _lake_grid.get(Vector2i(floori(pos.x / GRID), floori(pos.z / GRID)), NO_LAKES):
		var l: Dictionary = _lakes[li]
		if (l["bounds"] as Rect2).has_point(p) and Geometry2D.is_point_in_polygon(p, l["poly"]):
			return "lake"
	return "river" if water_level_at(pos.x, pos.z) > -INF else ""


## Depth of water above the ground at a position (0 if dry).
func depth_at(pos: Vector3) -> float:
	var lvl: float = water_level_at(pos.x, pos.z)
	return maxf(0.0, lvl - pos.y) if lvl > -INF else 0.0


func _physics_process(_delta: float) -> void:
	var w: Node = world
	if w == null or w.player == null:
		return
	var p: Player = w.player
	p.in_water_depth = depth_at(p.global_position)
	if p.in_water_depth > 0.6:
		p.state.stats.wetness = minf(1.0, p.state.stats.wetness + 0.02)
