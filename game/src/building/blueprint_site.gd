class_name BlueprintSite
extends Node3D
## A blueprint laid out from the field manual: a ghost the player completes.
##  * assembly: carry the materials to it and interact; once the cost is delivered it becomes the
##    structure (campfire, lean-to, workbench...).
##  * pieces:   every piece is a ghost slot; put a carried log into a slot (interact or attack).
## State lives in WorldState.blueprints[site_id] = {def, pos, rot, delivered, placed}.

const INTERACT_LAYER: int = 1 << 7
const GHOST_SHADER: String = "res://assets/shaders/ghost.gdshader"

var site_id: StringName = &""
var bp: BlueprintDef
var manager: Node
var delivered: Dictionary = {}
var placed: Array = []
var _mat: ShaderMaterial
var _slots: Dictionary = {}
var _body: StaticBody3D


class GhostSlot:
	extends StaticBody3D
	var site: BlueprintSite
	var index: int = 0

	func interact_text(player: Player) -> String:
		var s: StructureDef = site.slot_def(index)
		if s == null:
			return ""
		if s.piece_kind == "log" and player.state.inventory.count_of(&"log") <= 0:
			return "Needs a log"
		return "Place %s" % s.display_name

	func interact(player: Player) -> void:
		site.fill_slot(index, player)


func setup(p_id: StringName, p_bp: BlueprintDef, p_manager: Node, p_delivered: Dictionary = {}, p_placed: Array = []) -> void:
	site_id = p_id
	bp = p_bp
	manager = p_manager
	delivered = p_delivered.duplicate()
	placed = p_placed.duplicate()


func _ready() -> void:
	add_to_group(&"blueprint_sites")
	_mat = ShaderMaterial.new()
	_mat.shader = load(GHOST_SHADER)
	if bp.mode == "assembly":
		_build_assembly_ghost()
	else:
		for i: int in bp.pieces.size():
			if not placed.has(i):
				_add_slot(i)


func _build_assembly_ghost() -> void:
	var sdef: StructureDef = Content.structure(bp.result)
	var mi := MeshInstance3D.new()
	var model: String = bp.preview if ModelLibrary.has_model(bp.preview) else (sdef.model if sdef != null else "")
	var size: Vector3 = sdef.size if sdef != null else Vector3.ONE
	if ModelLibrary.has_model(model):
		mi.mesh = ModelLibrary.mesh(model)
	else:
		var b := BoxMesh.new()
		b.size = size
		mi.mesh = b
		mi.position = Vector3(0, size.y * 0.5, 0)
	mi.material_override = _mat
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mi)
	_mat.set_shader_parameter("height", size.y)
	_mat.set_shader_parameter("base_y", 0.0 if ModelLibrary.has_model(model) else -size.y * 0.5)
	_body = StaticBody3D.new()
	_body.collision_layer = INTERACT_LAYER
	_body.collision_mask = 0
	_body.set_meta(&"interactable", self)
	var cs := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = size.max(Vector3(0.6, 0.4, 0.6))
	cs.shape = box
	cs.position = Vector3(0, box.size.y * 0.5, 0)
	_body.add_child(cs)
	add_child(_body)
	_update_fill()


func _add_slot(i: int) -> void:
	var s: StructureDef = slot_def(i)
	if s == null:
		return
	var slot := GhostSlot.new()
	slot.site = self
	slot.index = i
	slot.collision_layer = INTERACT_LAYER
	slot.collision_mask = 0
	slot.transform = slot_local(i)
	var mi := MeshInstance3D.new()
	mi.mesh = ModelLibrary.mesh(s.model, "log") if s.piece_kind == "log" else ModelLibrary.mesh(s.model, "box")
	mi.material_override = _mat
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	slot.add_child(mi)
	var cs := CollisionShape3D.new()
	if s.piece_kind == "log":
		var cyl := CylinderShape3D.new()
		cyl.radius = 0.22
		cyl.height = LogSnapper.LENGTH
		cs.shape = cyl
		cs.rotation = Vector3(0, 0, -PI * 0.5)
	else:
		var box := BoxShape3D.new()
		box.size = s.size
		cs.shape = box
		cs.position = Vector3(0, s.size.y * 0.5, 0)
	slot.add_child(cs)
	add_child(slot)
	_slots[i] = slot


func slot_def(i: int) -> StructureDef:
	if i < 0 or i >= bp.pieces.size():
		return null
	return Content.structure(StringName(bp.pieces[i]["structure"]))


func slot_local(i: int) -> Transform3D:
	var p: Dictionary = bp.pieces[i]
	var r: Vector3 = p["rot"]
	return Transform3D(Basis.from_euler(Vector3(deg_to_rad(r.x), deg_to_rad(r.y), deg_to_rad(r.z))), p["pos"])


func slot_global(i: int) -> Transform3D:
	return global_transform * slot_local(i)


## Open slot whose ghost is nearest a world point (for placing with the attack button).
func nearest_open_slot(pos: Vector3, max_dist: float) -> int:
	var best: int = -1
	var best_d: float = max_dist
	for i: int in _slots:
		var d: float = slot_global(i).origin.distance_to(pos)
		if d < best_d:
			best_d = d
			best = i
	return best


func fill_slot(i: int, player: Player) -> void:
	Game.execute(&"build.place_log", {"player": player.state.id, "site": String(site_id), "slot": i})


## Called by BuildingManager once a slot's piece exists.
func mark_placed(i: int) -> void:
	if not placed.has(i):
		placed.append(i)
	if _slots.has(i):
		(_slots[i] as Node).queue_free()
		_slots.erase(i)


func is_complete() -> bool:
	if bp.mode == "pieces":
		return placed.size() >= bp.pieces.size()
	return remaining().is_empty()


## Materials still missing (assembly mode).
func remaining() -> Dictionary:
	var out: Dictionary = {}
	for k: Variant in bp.cost.keys():
		var need: int = int(bp.cost[k]) - int(delivered.get(k, 0))
		if need > 0:
			out[k] = need
	return out


func progress() -> float:
	if bp.mode == "pieces":
		return float(placed.size()) / maxf(1.0, float(bp.pieces.size()))
	var total: int = 0
	var got: int = 0
	for k: Variant in bp.cost.keys():
		total += int(bp.cost[k])
		got += mini(int(bp.cost[k]), int(delivered.get(k, 0)))
	return float(got) / maxf(1.0, float(total))


func _update_fill() -> void:
	if _mat != null:
		_mat.set_shader_parameter("fill", progress())


func on_delivered() -> void:
	_update_fill()


# --- Interactable (assembly ghost) -------------------------------------------------------------

func interact_text(player: Player) -> String:
	if bp.mode != "assembly":
		return ""
	var rem: Dictionary = remaining()
	var parts: PackedStringArray = []
	var can_give: bool = false
	for k: Variant in rem.keys():
		var have: int = player.state.inventory.count_of(StringName(str(k)))
		if have > 0:
			can_give = true
		var idef: ItemDef = Content.item(StringName(str(k)))
		parts.append("%s %d/%d" % [idef.display_name if idef != null else str(k), int(delivered.get(k, 0)), int(bp.cost[k])])
	var verb: String = "Add materials" if can_give else "Needs"
	return "%s — %s: %s" % [bp.display_name, verb, ", ".join(parts)]


func interact(player: Player) -> void:
	Game.execute(&"build.deliver", {"player": player.state.id, "site": String(site_id)})


func to_dict() -> Dictionary:
	var q: Quaternion = global_transform.basis.get_rotation_quaternion()
	return {"def": String(bp.id), "pos": [global_position.x, global_position.y, global_position.z], "rot": [q.x, q.y, q.z, q.w],
		"delivered": delivered, "placed": placed}
