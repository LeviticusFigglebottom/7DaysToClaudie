class_name PoiParts
extends RefCounted
## Shared kit knowledge for the POI builder: kit model ids, opening dimensions (POI_KIT.md), the
## finish-name -> texture-array-slice tables, the kit wall/floor ShaderMaterials, and procedural
## stand-ins for kit pieces that have not been generated yet.

const KIT: String = "kit/"
## Opening geometry (metres): width, height, sill; "len" cells along the wall, "storeys" of wall the
## piece stands (two-storey pieces are 5.8 m tall: a tall room's wall), and the kit ids of the pane
## ("glass"), board-up ("boards") and door leaf ("leaf") that fill it. A lancet's "h" is to the
## apex of its pointed arch ("spring": where the arch starts). "mirror_pair": the leaf is dressed on
## one face only, so the right leaf of the pair is the left one mirrored (not turned half round).
const OPENINGS: Dictionary = {
	"door": {"model": "wall_1m_door", "w": 0.86, "h": 2.1, "sill": 0.0, "len": 1},
	"door2": {"model": "wall_2m_door", "w": 1.7, "h": 2.1, "sill": 0.0, "len": 2},
	"window": {"model": "wall_1m_window", "w": 0.7, "h": 1.1, "sill": 0.9, "len": 1, "glass": "window_glass_1m", "boards": "boards_window_1m"},
	"window2": {"model": "wall_2m_window", "w": 1.6, "h": 1.2, "sill": 0.85, "len": 2, "glass": "window_glass_2m", "boards": "boards_window_2m"},
	"breach": {"model": "wall_1m_breach", "w": 0.8, "h": 1.7, "sill": 0.0, "len": 1},
	"half": {"model": "wall_1m_half", "w": 1.0, "h": 0.0, "sill": 1.0, "len": 1},
	"open": {"model": "", "w": 1.0, "h": 2.8, "sill": 0.0, "len": 1},
	"lancet": {"model": "wall_1m_lancet", "w": 0.66, "h": 3.0, "sill": 1.0, "spring": 2.45, "len": 1, "storeys": 2,
		"glass": "window_glass_lancet", "boards": "boards_window_lancet"},
	"window_tall": {"model": "wall_1m_window_tall", "w": 0.76, "h": 2.5, "sill": 0.8, "len": 1, "storeys": 2,
		"glass": "window_glass_tall", "boards": "boards_window_tall"},
	"door2_tall": {"model": "wall_2m_door_tall", "w": 1.8, "h": 3.5, "sill": 0.0, "len": 2, "storeys": 2, "leaf": "door_barn_tall",
		"leaf_size": [0.89, 3.45], "mirror_pair": true},
}
## Wall height of an opening piece: 2.8 m, or 5.8 m for a two-storey piece.
static func piece_height(spec: Dictionary) -> float:
	return PoiLayout.WALL_H + PoiLayout.STOREY * float(int(spec.get("storeys", 1)) - 1)

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
	# Wall finishes are authored to tile every 1 m, floor finishes every 2 m.
	m.set_shader_parameter("texture_scale", 0.5 if kind == "floor" else 1.0)
	if kind == "floor":
		m.set_shader_parameter("is_floor", true)
		var wall_alb: Texture = _tex("res://assets/generated/textures/kit_wall_finishes_albedo.png")
		if wall_alb != null:
			m.set_shader_parameter("side_b_albedo", wall_alb)
			m.set_shader_parameter("side_b_from_other_array", true)
			# Its relief too, so a rock ceiling (a mine level's, a cave's) isn't a flat lid.
			var wall_n: Texture = _tex("res://assets/generated/textures/kit_wall_finishes_normal.png")
			var wall_orm: Texture = _tex("res://assets/generated/textures/kit_wall_finishes_orm.png")
			if wall_n != null and wall_orm != null:
				m.set_shader_parameter("side_b_normal", wall_n)
				m.set_shader_parameter("side_b_orm", wall_orm)
				m.set_shader_parameter("side_b_has_maps", true)
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
	var src: Mesh = ModelLibrary.generated_mesh(id)
	if src != null:
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
	if piece.ends_with("_tall") or piece == "wall_1m_lancet":
		# Two-storey wall pieces (a tall room's wall): the stand-in is solid, the opening is cut
		# by the generated piece only.
		size.y = 5.8
		offset.y = 2.9
	if piece == "wall_1m_half":
		size.y = 1.0
		offset.y = 0.5
	elif piece == "wall_band_1m":
		# The 20 cm storey band between stacked wall pieces (2.8 .. 3.0 above the storey's floor).
		size.y = 0.2
		offset.y = 2.9
	elif piece.begins_with("gallery_"):
		# A gallery railing: the rail stands on the gallery side (local -Z), the fascia covers the
		# floor slab's edge over the void (local +Z).
		size = Vector3(1.0, 1.0, 0.07)
		offset = Vector3(0, 0.5, -0.06)
		kind = "boards"
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
	elif piece == "chimney_brick" or piece == "chimney_shaft_1m":
		# The chimney (4.5 m) and the metres of shaft stacked under it to clear the roof.
		size = Vector3(0.8, 4.5 if piece == "chimney_brick" else 1.0, 0.6)
		offset = Vector3(0, size.y * 0.5, 0)
		kind = "brick"
	elif piece.begins_with("stairs"):
		size = Vector3(1.0, 0.2, 5.0)
		kind = "stairs"
	elif piece.begins_with("door_barn_tall"):
		size = Vector3(0.89, 3.45, 0.06)
		offset = Vector3(0.445, 1.725, 0)
		kind = "door"
	elif piece.begins_with("door"):
		size = Vector3(0.82, 2.05, 0.04)
		offset = Vector3(0.41, 1.025, 0)
		kind = "door"
	elif piece.begins_with("window_glass"):
		size = Vector3(1.6 if piece.contains("2m") else 0.7, 1.1, 0.01)
		if piece.contains("lancet") or piece.contains("tall"):
			size.y = 2.5
		offset = Vector3(0, size.y * 0.5, 0)
		kind = "glass"
	elif piece.begins_with("boards"):
		size = Vector3(1.8 if piece.contains("2m") else 0.9, 2.0 if piece == "boards_door" else 1.2, 0.04)
		if piece.contains("lancet") or piece.contains("tall"):
			size.y = 2.4
		offset = Vector3(0, size.y * 0.5, 0)
		kind = "boards"
	elif piece == "ladder_3m":
		# Where the generated ladder's rails are (0.09-0.16 m out along +Z), so a builder that
		# turns it the wrong way buries the stand-in in the wall too and the tests see it.
		size = Vector3(0.5, 3.0, 0.07)
		offset = Vector3(0, 1.5, 0.125)
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
	elif piece.begins_with("stoop_"):
		# stoop_<kind>_<steps>_<w>m (PoiBuilder.stoop_piece): its block, running out along +Z.
		var parts: PackedStringArray = piece.split("_")
		var n: int = int(parts[2]) if parts.size() > 3 else 1
		var d: float = (PoiBuilder.STOOP_LANDING + PoiBuilder.STOOP_TREAD * float(n - 1)) if parts[1] == "concrete" else PoiBuilder.STOOP_TREAD * float(n)
		size = Vector3(float(parts[3].trim_suffix("m")) if parts.size() > 3 else 1.0, PoiBuilder.STOOP_RISE * float(n), d)
		offset = Vector3(0, size.y * 0.5, d * 0.5)
		kind = "concrete" if parts[1] == "concrete" else "boards"
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
			sm.albedo_color = {"concrete": Color(0.5, 0.5, 0.48), "brick": Color(0.5, 0.27, 0.2), "stairs": Color(0.42, 0.3, 0.2), "door": Color(0.45, 0.33, 0.22),
				"glass": Color(0.6, 0.7, 0.75, 0.35), "boards": Color(0.5, 0.4, 0.28)}.get(kind, Color(0.5, 0.5, 0.5))
			if kind == "glass":
				sm.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
				sm.roughness = 0.1
			mat = sm
	am.surface_set_material(0, mat)
	return am
