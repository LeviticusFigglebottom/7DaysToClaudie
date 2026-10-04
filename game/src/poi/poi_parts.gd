class_name PoiParts
extends RefCounted
## Shared kit knowledge for the POI builder: kit model ids, opening dimensions (POI_KIT.md), the
## finish-name -> texture-array-slice tables, the kit wall/floor ShaderMaterials, and procedural
## stand-ins for kit pieces that have not been generated yet.

const KIT: String = "kit/"
## Opening geometry (metres): width, height, sill.
const OPENINGS: Dictionary = {
	"door": {"model": "wall_1m_door", "w": 0.86, "h": 2.1, "sill": 0.0, "len": 1},
	"door2": {"model": "wall_2m_door", "w": 1.7, "h": 2.1, "sill": 0.0, "len": 2},
	"window": {"model": "wall_1m_window", "w": 0.7, "h": 1.1, "sill": 0.9, "len": 1},
	"window2": {"model": "wall_2m_window", "w": 1.6, "h": 1.2, "sill": 0.85, "len": 2},
	"breach": {"model": "wall_1m_breach", "w": 0.8, "h": 1.7, "sill": 0.0, "len": 1},
	"half": {"model": "wall_1m_half", "w": 1.0, "h": 0.0, "sill": 1.0, "len": 1},
	"open": {"model": "", "w": 1.0, "h": 2.8, "sill": 0.0, "len": 1},
}

static var _finishes: Dictionary = {}
static var _mats: Dictionary = {}
static var _meshes: Dictionary = {}


static func finish_index(kind: String, finish_name: String) -> int:
	if _finishes.is_empty():
		var path: String = "res://data/materials/kit_finishes.json"
		var d: Variant = JSON.parse_string(FileAccess.get_file_as_string(path)) if FileAccess.file_exists(path) else null
		_finishes = {"wall": {}, "floor": {}}
		if d is Dictionary:
			for k: String in ["wall", "floor"]:
				var arr: Array = (d as Dictionary).get(k, [])
				for i: int in arr.size():
					_finishes[k][str(arr[i])] = i
	var table: Dictionary = _finishes.get(kind, {})
	if table.has(finish_name):
		return int(table[finish_name])
	return 0 if kind == "wall" else 0


static func _tex(path: String) -> Texture:
	return load(path) as Texture if ResourceLoader.exists(path) else null


## ShaderMaterial for kit walls ("wall") or floors ("floor").
static func kit_material(kind: String) -> ShaderMaterial:
	if _mats.has(kind):
		return _mats[kind]
	var m := ShaderMaterial.new()
	m.shader = load("res://assets/shaders/kit_wall.gdshader")
	var base: String = "res://assets/generated/textures/kit_%s_finishes_" % kind
	var alb: Texture = _tex(base + "albedo.png")
	m.set_shader_parameter("has_finishes", alb != null)
	if alb != null:
		m.set_shader_parameter("finish_albedo", alb)
		m.set_shader_parameter("finish_normal", _tex(base + "normal.png"))
		m.set_shader_parameter("finish_orm", _tex(base + "orm.png"))
	if kind == "floor":
		m.set_shader_parameter("is_floor", true)
		var wall_alb: Texture = _tex("res://assets/generated/textures/kit_wall_finishes_albedo.png")
		if wall_alb != null:
			m.set_shader_parameter("side_b_albedo", wall_alb)
			m.set_shader_parameter("side_b_from_other_array", true)
	var dec: Texture = _tex("res://assets/generated/textures/kit_decay_albedo.png")
	m.set_shader_parameter("has_decay", dec != null)
	if dec != null:
		m.set_shader_parameter("decay_albedo", dec)
		m.set_shader_parameter("decay_orm", _tex("res://assets/generated/textures/kit_decay_orm.png"))
	_mats[kind] = m
	return m


static func _is_kit_surface(mat: Material, kind: String) -> bool:
	if mat == null:
		return false
	var n: String = mat.resource_name if mat.resource_name != "" else mat.resource_path.get_file().get_basename()
	return n == "kit_" + kind or n == "M_kit_" + kind or mat.resource_path.ends_with("/kit_%s.tres" % kind)


## Kit mesh with its kit_wall / kit_floor surfaces switched to the per-instance finish shader.
static func kit_mesh(piece: String) -> Mesh:
	if _meshes.has(piece):
		return _meshes[piece]
	var id: String = KIT + piece
	var mesh: Mesh
	if ModelLibrary.has_model(id):
		var src: Mesh = ModelLibrary.mesh(id)
		var am := ArrayMesh.new()
		for s: int in src.get_surface_count():
			am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, src.surface_get_arrays(s))
			var mat: Material = src.surface_get_material(s)
			if _is_kit_surface(mat, "wall"):
				mat = kit_material("wall")
			elif _is_kit_surface(mat, "floor"):
				mat = kit_material("floor")
			am.surface_set_material(s, mat)
		mesh = am
	else:
		mesh = _standin(piece)
	_meshes[piece] = mesh
	return mesh


## Procedural stand-ins sized per POI_KIT.md (so buildings work before `make assets`).
static func _standin(piece: String) -> Mesh:
	var size := Vector3(1.0, 2.8, 0.16)
	var offset := Vector3(0, 1.4, 0)
	var kind: String = "wall"
	if piece.begins_with("wall_2m"):
		size.x = 2.0
	if piece == "wall_1m_half":
		size.y = 1.0
		offset.y = 0.5
	elif piece.begins_with("floor"):
		size = Vector3(1.0, 0.2, 1.0)
		offset = Vector3(0, -0.1, 0)
		kind = "floor"
	elif piece == "post_corner":
		size = Vector3(0.16, 2.8, 0.16)
	elif piece == "foundation_1m":
		size = Vector3(1.0, 0.6, 0.2)
		offset = Vector3(0, 0.3, 0)
		kind = "concrete"
	elif piece.begins_with("stairs"):
		size = Vector3(1.0, 0.2, 5.0)
		kind = "stairs"
	elif piece.begins_with("door"):
		size = Vector3(0.82, 2.05, 0.04)
		offset = Vector3(0.41, 1.025, 0)
		kind = "door"
	elif piece.begins_with("window_glass"):
		size = Vector3(0.7 if piece.contains("1m") else 1.6, 1.1, 0.01)
		offset = Vector3(0, 0.55, 0)
		kind = "glass"
	elif piece.begins_with("boards"):
		size = Vector3(0.9 if piece.contains("1m") or piece == "boards_door" else 1.8, 1.2 if piece != "boards_door" else 2.0, 0.04)
		offset = Vector3(0, size.y * 0.5, 0)
		kind = "boards"
	elif piece == "ladder_3m":
		size = Vector3(0.5, 3.0, 0.06)
		offset = Vector3(0, 1.5, 0)
		kind = "boards"
	elif piece.begins_with("porch_deck"):
		size = Vector3(1.0, 0.1, 1.0)
		offset = Vector3(0, 0.55, 0)
		kind = "boards"
	elif piece == "porch_post":
		size = Vector3(0.12, 2.8, 0.12)
		kind = "boards"
	elif piece == "porch_step_1m":
		size = Vector3(1.0, 0.3, 0.9)
		offset = Vector3(0, 0.15, 0.45)
		kind = "boards"
	elif piece == "barricade_furniture":
		size = Vector3(1.6, 1.4, 0.8)
		offset = Vector3(0, 0.7, 0)
		kind = "boards"
	var b := BoxMesh.new()
	b.size = size
	var arr: Array = b.get_mesh_arrays()
	var v: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
	for i: int in v.size():
		v[i] += offset
	arr[Mesh.ARRAY_VERTEX] = v
	var am := ArrayMesh.new()
	am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
	var mat: Material
	match kind:
		"wall", "floor":
			mat = kit_material(kind)
		_:
			var sm := StandardMaterial3D.new()
			sm.albedo_color = {"concrete": Color(0.5, 0.5, 0.48), "stairs": Color(0.42, 0.3, 0.2), "door": Color(0.45, 0.33, 0.22),
				"glass": Color(0.6, 0.7, 0.75, 0.35), "boards": Color(0.5, 0.4, 0.28)}.get(kind, Color(0.5, 0.5, 0.5))
			if kind == "glass":
				sm.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
				sm.roughness = 0.1
			mat = sm
	am.surface_set_material(0, mat)
	return am
