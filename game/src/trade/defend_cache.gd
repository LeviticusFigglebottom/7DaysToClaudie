class_name DefendCache
extends StaticBody3D
## The relay cache a defend contract holds (ADR-0039): a stack of Program crates with a beacon.
## Hold E on it to start the uplink; while it runs its beacon flashes and the waves come for it.

var manager: Node
var contract_id: String = ""
var _beacon: OmniLight3D
var _t: float = 0.0


func _ready() -> void:
	var pd: PropDef = Content.get_def(&"prop", &"waystation_supply_stack") as PropDef
	var mi := MeshInstance3D.new()
	mi.mesh = ModelLibrary.mesh(pd.model_for("worn") if pd != null else "props/waystation_supply_stack", "box")
	add_child(mi)
	var aabb: AABB = mi.mesh.get_aabb() if mi.mesh != null else AABB(Vector3(-0.8, 0, -0.6), Vector3(1.6, 1.5, 1.2))
	if aabb.size.length() < 0.01:
		aabb = AABB(Vector3(-0.8, 0, -0.6), Vector3(1.6, 1.5, 1.2))
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = aabb.size
	shape.shape = box
	shape.position = aabb.get_center()
	add_child(shape)
	_beacon = OmniLight3D.new()
	_beacon.light_color = Color(1.0, 0.55, 0.1)
	_beacon.omni_range = 7.0
	_beacon.light_energy = 0.0
	_beacon.position = Vector3(0, aabb.end.y + 0.3, 0)
	add_child(_beacon)


func _process(delta: float) -> void:
	_t += delta
	var running: bool = manager != null and bool(manager.call(&"is_running", contract_id))
	_beacon.light_energy = (2.5 if fmod(_t, 0.8) < 0.25 else 0.2) if running else 0.6


func interact_text(_player: Node) -> String:
	if manager != null and bool(manager.call(&"is_running", contract_id)):
		return "Uplink %d%%" % int(float(manager.call(&"run_progress", contract_id)) * 100.0)
	return "Start the uplink (hold)"


func interact_hold_time(_player: Node) -> float:
	return 1.2


func interact(_player: Node) -> void:
	var r: Dictionary = Game.execute(&"contract.start_defend", {"contract": contract_id})
	if not bool(r.get("ok", false)):
		Events.player_status_message.emit(str(r.get("error", "")).capitalize() + ".", &"warning")
