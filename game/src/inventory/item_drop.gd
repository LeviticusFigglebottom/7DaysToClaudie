class_name ItemDrop
extends RigidBody3D
## An item lying in the world (dropped, thrown, spilled from a container). Interact to pick up.
## Persistent: registered in WorldState.loose by LooseItems on save; recreated on load.

var entity_id: StringName = &""
var stack: ItemStack


static func spawn(parent: Node, p_stack: ItemStack, pos: Vector3, id: StringName = &"") -> ItemDrop:
	var d := ItemDrop.new()
	d.stack = p_stack
	d.entity_id = id if id != &"" else (Game.session.ids.next("i") if Game.session != null else StringName("i:%d" % Time.get_ticks_usec()))
	parent.add_child(d)
	d.global_position = pos
	d.rotation.y = randf() * TAU
	return d


func _ready() -> void:
	collision_layer = 1 << 6
	collision_mask = (1 << 0) | (1 << 1) | (1 << 2)
	mass = 1.0
	add_to_group(&"item_drops")
	var model: Node3D = ItemVisuals.make_model(stack.item_id)
	add_child(model)
	var cs := CollisionShape3D.new()
	var box := BoxShape3D.new()
	var aabb := _aabb(model)
	box.size = (aabb.size if aabb.size.length() > 0.01 else Vector3(0.2, 0.08, 0.12)).max(Vector3(0.06, 0.04, 0.06))
	cs.shape = box
	cs.position = aabb.get_center() if aabb.size.length() > 0.01 else Vector3(0, 0.04, 0)
	add_child(cs)


static func _aabb(n: Node) -> AABB:
	var out := AABB()
	var first: bool = true
	for c: Node in n.find_children("*", "VisualInstance3D", true, false):
		var vi := c as VisualInstance3D
		var b: AABB = vi.transform * vi.get_aabb()
		out = b if first else out.merge(b)
		first = false
	return out


func interact_text(_player: Player) -> String:
	var def: ItemDef = stack.def()
	if def == null:
		return ""
	return "Pick up %s%s" % [def.display_name, (" x%d" % stack.count) if stack.count > 1 else ""]


func interact(player: Player) -> void:
	var res: Dictionary = Game.execute(&"world.pickup_stack", {"player": player.state.id, "stack": stack})
	var left: int = int(res.get("left", stack.count))
	if left <= 0:
		queue_free()
	else:
		stack.count = left


func to_dict() -> Dictionary:
	var q: Quaternion = global_transform.basis.get_rotation_quaternion()
	return {"kind": "item", "stack": stack.to_dict(), "pos": [global_position.x, global_position.y, global_position.z], "rot": [q.x, q.y, q.z, q.w]}
