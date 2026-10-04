class_name BuildPreview
extends Node3D
## The placement ghost that follows the player's aim: a whole blueprint while choosing where to
## lay it out, or a single log while holding one. Tinted pale when placeable, red when not.

const VALID := Color(0.78, 0.86, 0.95, 0.32)
const INVALID := Color(0.95, 0.3, 0.25, 0.4)
const SNAPPED := Color(0.75, 0.95, 0.8, 0.38)

var mode: StringName = &""
var valid: bool = false
var _mat: ShaderMaterial
var _key: String = ""


func _ready() -> void:
	_mat = ShaderMaterial.new()
	_mat.shader = load(BlueprintSite.GHOST_SHADER)
	visible = false


func show_blueprint(bp: BlueprintDef) -> void:
	if _key == "bp:" + String(bp.id):
		visible = true
		return
	_clear()
	_key = "bp:" + String(bp.id)
	mode = &"blueprint"
	if bp.mode == "pieces":
		for p: Dictionary in bp.pieces:
			var s: StructureDef = Content.structure(StringName(p["structure"]))
			var r: Vector3 = p["rot"]
			var mi := _ghost_mesh(s)
			mi.transform = Transform3D(Basis.from_euler(Vector3(deg_to_rad(r.x), deg_to_rad(r.y), deg_to_rad(r.z))), p["pos"]) * mi.transform
			add_child(mi)
	else:
		add_child(_ghost_mesh(Content.structure(bp.result), bp.preview))
	visible = true


func show_log() -> void:
	if _key == "log":
		visible = true
		return
	_clear()
	_key = "log"
	mode = &"log"
	add_child(_ghost_mesh(Content.structure(&"log_piece")))
	visible = true


func hide_preview() -> void:
	visible = false


func set_state(is_valid: bool, snapped: bool = false) -> void:
	valid = is_valid
	_mat.set_shader_parameter("tint", (SNAPPED if snapped else VALID) if is_valid else INVALID)


func _ghost_mesh(s: StructureDef, preview_model: String = "") -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.material_override = _mat
	if preview_model != "" and ModelLibrary.has_model(preview_model):
		mi.mesh = ModelLibrary.mesh(preview_model)
	elif s != null and ModelLibrary.has_model(s.model):
		mi.mesh = ModelLibrary.mesh(s.model)
	elif s != null and s.piece_kind == "log":
		mi.mesh = ModelLibrary.make_placeholder("log")
	else:
		var b := BoxMesh.new()
		b.size = s.size if s != null else Vector3.ONE
		mi.mesh = b
		mi.position = Vector3(0, b.size.y * 0.5, 0)
	return mi


func _clear() -> void:
	for c: Node in get_children():
		c.queue_free()
	_key = ""
