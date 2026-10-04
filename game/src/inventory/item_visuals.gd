class_name ItemVisuals
extends RefCounted
## Builds the 3D representation of an item: the generated model when available, otherwise a
## category-coloured placeholder so gameplay never depends on assets being built.

const CATEGORY_COLORS: Dictionary = {
	"resource": Color(0.45, 0.36, 0.25), "tool": Color(0.5, 0.5, 0.52), "weapon": Color(0.4, 0.4, 0.42),
	"food": Color(0.7, 0.45, 0.2), "drink": Color(0.4, 0.6, 0.8), "medical": Color(0.9, 0.9, 0.9),
	"light": Color(1.0, 0.7, 0.3), "schematic": Color(0.85, 0.82, 0.7), "magazine": Color(0.75, 0.3, 0.25),
	"note": Color(0.9, 0.88, 0.8), "ammo": Color(0.75, 0.6, 0.3), "quest": Color(0.4, 0.7, 0.5),
}

static var _cache: Dictionary = {}


static func model_path(item_id: StringName) -> String:
	var def: ItemDef = Content.item(item_id)
	if def == null or def.model == "":
		return ""
	return "res://assets/generated/models/%s.glb" % def.model


static func make_model(item_id: StringName) -> Node3D:
	var path: String = model_path(item_id)
	if path != "" and ResourceLoader.exists(path):
		var ps: PackedScene = _cache.get(path)
		if ps == null:
			ps = load(path)
			_cache[path] = ps
		return ps.instantiate() as Node3D
	var def: ItemDef = Content.item(item_id)
	var mi := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size = Vector3(0.18, 0.08, 0.12)
	if item_id == &"log":
		var cyl := CylinderMesh.new()
		cyl.top_radius = 0.17
		cyl.bottom_radius = 0.17
		cyl.height = 4.0
		mi.mesh = cyl
		mi.rotation_degrees = Vector3(0, 0, 90)
	elif item_id == &"stick":
		box.size = Vector3(0.9, 0.035, 0.035)
		mi.mesh = box
	else:
		mi.mesh = box
	var mat := StandardMaterial3D.new()
	mat.albedo_color = CATEGORY_COLORS.get(def.category if def != null else "resource", Color(0.5, 0.5, 0.5))
	mat.roughness = 0.8
	mi.material_override = mat
	var root := Node3D.new()
	root.add_child(mi)
	mi.position.y = 0.04
	return root
