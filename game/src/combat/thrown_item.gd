class_name ThrownItem
extends RigidBody3D
## A thrown stone/spear: damages what it hits once, then becomes a pickup.

var item_id: StringName = &"stone"
var thrower: StringName = &""
var damage: float = 10.0
## Where it was thrown from: what a struck Hollow turns toward (and wakes facing).
var origin := Vector3.ZERO
var _armed: bool = true
var _life: float = 0.0


func _ready() -> void:
	collision_layer = 1 << 13
	collision_mask = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 4) | (1 << 9) | (1 << 12)
	contact_monitor = true
	max_contacts_reported = 2
	mass = 0.8
	var cs := CollisionShape3D.new()
	var sh := SphereShape3D.new()
	sh.radius = 0.08
	cs.shape = sh
	add_child(cs)
	add_child(ItemVisuals.make_model(item_id))
	body_entered.connect(_on_hit)


func _process(delta: float) -> void:
	_life += delta
	if _life > 3.0 and linear_velocity.length() < 0.3:
		ItemDrop.spawn(get_tree().current_scene, ItemStack.make(item_id, 1), global_position)
		queue_free()


func _on_hit(body: Node) -> void:
	if not _armed:
		return
	_armed = false
	var info := DamageInfo.make(damage * clampf(linear_velocity.length() / 15.0, 0.3, 1.2), &"blunt", &"thrown", thrower)
	info.hit_pos = global_position
	info.source_pos = origin
	info.direction = linear_velocity.normalized()
	info.collider = body
	info.stagger = 0.4
	var r: Object = PlayerEquipment._damage_receiver(body)
	if r != null:
		r.call(&"take_damage", info)
	Audio.play_3d(&"sfx/hit_stone", global_position, {"volume_db": -6.0})
	if Stimuli.current != null:
		Stimuli.current.emit_sound(global_position, 9.0, &"impact", thrower)
