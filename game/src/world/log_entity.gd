class_name LogEntity
extends RigidBody3D
## A loose 4 m log in the world (from a felled tree, or dropped off the shoulder). Pick it up to
## carry it (two; three with Timberwright), then place it freeform or into a blueprint ghost.
## Rolls on slopes.
## Persistent through LooseItems (WorldState.loose, kind "log").

const LENGTH: float = 4.0
const RADIUS: float = 0.17

var entity_id: StringName = &""
var species_id: StringName = &""


func _ready() -> void:
	collision_layer = 1 << 6
	collision_mask = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 6)
	mass = 60.0
	linear_damp = 0.3
	angular_damp = 1.2
	add_to_group(&"logs")
	var pm := PhysicsMaterial.new()
	pm.friction = 0.95
	pm.rough = true
	pm.bounce = 0.05
	physics_material_override = pm
	var mi := MeshInstance3D.new()
	mi.mesh = ModelLibrary.mesh(_model_id(), "log")
	add_child(mi)
	var cs := CollisionShape3D.new()
	var cyl := CylinderShape3D.new()
	cyl.radius = RADIUS
	cyl.height = LENGTH
	cs.shape = cyl
	cs.rotation = Vector3(0, 0, -PI * 0.5)
	add_child(cs)


func _model_id() -> String:
	var sp: SpeciesDef = Content.get_def(&"species", species_id) as SpeciesDef if species_id != &"" else null
	if sp != null and sp.log_model != "" and ModelLibrary.has_model(sp.log_model):
		return sp.log_model
	return "structures/log_piece"


func interact_text(player: Player) -> String:
	if player.state.inventory.count_of(&"log") >= _carry_max(player):
		return "Shoulder full (%d logs)" % _carry_max(player)
	return "Pick up log"


## Shoulder capacity: the log item's carry_max plus perk bonuses (Timberwright).
func _carry_max(player: Player) -> int:
	var cap: int = player.state.inventory.carry_limit(&"log")
	return cap if cap > 0 else 2


func interact(player: Player) -> void:
	if player.state.inventory.count_of(&"log") >= _carry_max(player):
		return
	var res: Dictionary = Game.execute(&"world.pickup_item", {"player": player.state.id, "item": "log", "count": 1})
	if bool(res.get("ok", false)):
		Audio.play_3d(&"sfx/log_pickup", global_position, {"volume_db": -4.0})
		queue_free()


func to_dict() -> Dictionary:
	var q: Quaternion = global_transform.basis.get_rotation_quaternion()
	return {"kind": "log", "species": String(species_id), "pos": [global_position.x, global_position.y, global_position.z], "rot": [q.x, q.y, q.z, q.w]}
