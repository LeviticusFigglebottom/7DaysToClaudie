class_name WaterSystem
extends Node3D
## Builds lake and river surfaces from region metadata and answers water-level queries.

const RIVER_EXTRA: float = 3.0
const LAKE_OFFSET: float = 3.5

var world: Node
var _lakes: Array[Dictionary] = []
var _rivers: Array[Dictionary] = []
var _lake_mat: ShaderMaterial
var _river_mat: ShaderMaterial


func setup_world(w: Node) -> void:
	world = w
	_lake_mat = _make_material(0.0)
	_river_mat = _make_material(0.35)
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
				_add_lake(wb)
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
		_add_river_piece(merged)


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


static func _noise_normal(seed: int) -> Texture2D:
	var nz := FastNoiseLite.new()
	nz.seed = seed
	nz.frequency = 0.03
	nz.fractal_octaves = 4
	var tex := NoiseTexture2D.new()
	tex.noise = nz
	tex.seamless = true
	tex.as_normal_map = true
	tex.bump_strength = 6.0
	tex.width = 512
	tex.height = 512
	tex.generate_mipmaps = true
	return tex


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
	for v: Vector2 in outline:
		verts.append(Vector3(v.x, level, v.y))
		uvs.append(v * 0.1)
	# triangulate_polygon winding -> flip to Godot's clockwise front faces.
	var fixed := PackedInt32Array()
	for i: int in range(0, idx.size(), 3):
		fixed.append(idx[i])
		fixed.append(idx[i + 2])
		fixed.append(idx[i + 1])
	_add_mesh("Lake_" + str(wb["id"]), verts, uvs, fixed, _lake_mat, true)
	_lakes.append({"poly": poly, "level": level, "bounds": _bounds(poly)})


func _add_river_piece(wb: Dictionary) -> void:
	var pts: Array = wb["points"]
	var widths: Array = wb["widths"]
	var levels: Array = wb["levels"]
	if pts.size() < 2:
		return
	var verts := PackedVector3Array()
	var uvs := PackedVector2Array()
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
		if i > 0:
			var a: int = (i - 1) * 2
			idx.append_array([a, a + 2, a + 1, a + 1, a + 2, a + 3])
	_add_mesh("River_" + str(wb["id"]), verts, uvs, idx, _river_mat, false)
	var line := PackedVector2Array()
	for p: Array in pts:
		line.append(Vector2(float(p[0]), float(p[1])))
	_rivers.append({"line": line, "widths": widths, "levels": levels, "bounds": _bounds(line).grow(40.0)})


func _add_mesh(name_: String, verts: PackedVector3Array, uvs: PackedVector2Array, idx: PackedInt32Array, mat: Material, flip_check: bool) -> void:
	var arrays: Array = []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts
	arrays[Mesh.ARRAY_TEX_UV] = uvs
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


static func _bounds(p: PackedVector2Array) -> Rect2:
	var r := Rect2(p[0], Vector2.ZERO)
	for v: Vector2 in p:
		r = r.expand(v)
	return r


## Water surface height at (x, z), or -INF if there is no water there.
func water_level_at(x: float, z: float) -> float:
	var p := Vector2(x, z)
	for l: Dictionary in _lakes:
		if (l["bounds"] as Rect2).has_point(p) and Geometry2D.is_point_in_polygon(p, l["poly"]):
			return float(l["level"])
	for r: Dictionary in _rivers:
		if not (r["bounds"] as Rect2).has_point(p):
			continue
		var line: PackedVector2Array = r["line"]
		var best: float = INF
		var best_i: int = -1
		for i: int in line.size() - 1:
			var q: Vector2 = Geometry2D.get_closest_point_to_segment(p, line[i], line[i + 1])
			var d: float = p.distance_to(q)
			if d < best:
				best = d
				best_i = i
		if best_i >= 0 and best < float(r["widths"][best_i]) * 0.5:
			return float(r["levels"][best_i])
	return -INF


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
