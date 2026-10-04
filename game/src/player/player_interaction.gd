class_name PlayerInteraction
extends Node
## Finds what the player is looking at and runs interactions.
##
## Interactable protocol (duck-typed; the collider or its nearest ancestor implementing it):
##   interact_text(player: Player) -> String          prompt ("" = not interactable now)
##   interact(player: Player) -> void
##   interact_hold_time(player: Player) -> float      optional; > 0 = hold to complete (searching)

signal focus_changed(target: Object, text: String)
signal hold_progress(t: float)

const MASK: int = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 4) | (1 << 6) | (1 << 7) | (1 << 12)

var player: Player
var target: Object = null
var prompt: String = ""
var hold_t: float = 0.0
var hold_needed: float = 0.0
var last_hit: Dictionary = {}


func _ready() -> void:
	player = get_parent() as Player


func _physics_process(delta: float) -> void:
	if player == null or player.state == null:
		return
	_scan()
	if not player.input_enabled:
		_cancel_hold()
		return
	if target != null and Input.is_action_just_pressed(&"interact"):
		var ht: float = float(target.call(&"interact_hold_time", player)) if target.has_method(&"interact_hold_time") else 0.0
		ht *= maxf(0.3, 1.0 - player.state.progression.modifier("search_speed_mult"))
		if ht <= 0.0:
			target.call(&"interact", player)
		else:
			hold_needed = ht
			hold_t = 0.0
	if hold_needed > 0.0:
		if target == null or not Input.is_action_pressed(&"interact"):
			_cancel_hold()
		else:
			hold_t += delta
			hold_progress.emit(hold_t / hold_needed)
			if hold_t >= hold_needed:
				var t: Object = target
				_cancel_hold()
				t.call(&"interact", player)


func _cancel_hold() -> void:
	if hold_needed > 0.0:
		hold_progress.emit(0.0)
	hold_needed = 0.0
	hold_t = 0.0


func _scan() -> void:
	var cam: Camera3D = player.camera
	var from: Vector3 = cam.global_position
	var to: Vector3 = from - cam.global_transform.basis.z * float(player.cfg.get("interact_range", 2.6))
	var q := PhysicsRayQueryParameters3D.create(from, to, MASK)
	q.collide_with_areas = true
	q.exclude = [player.get_rid()]
	var hit: Dictionary = player.get_world_3d().direct_space_state.intersect_ray(q)
	last_hit = hit
	var found: Object = null
	if not hit.is_empty():
		found = find_interactable(hit["collider"])
	if found == null:
		# Scattered plants, stones and deadfall have no bodies: ask vegetation along the ray.
		var veg: Node = Game.world.get(&"vegetation") if Game.world != null else null
		if veg != null:
			var reach: float = from.distance_to(hit["position"]) if not hit.is_empty() else from.distance_to(to)
			found = veg.call(&"pick_harvestable", from, (to - from).normalized(), reach + 0.3)
	var text: String = ""
	if found != null:
		text = str(found.call(&"interact_text", player))
		if text == "":
			found = null
	if found != target or text != prompt:
		target = found
		prompt = text
		focus_changed.emit(target, prompt)


static func find_interactable(o: Object) -> Object:
	var n: Node = o as Node
	var depth: int = 0
	while n != null and depth < 6:
		if n.has_method(&"interact") and n.has_method(&"interact_text"):
			return n
		if n.has_meta(&"interactable"):
			var ref: Variant = n.get_meta(&"interactable")
			if ref is Object and is_instance_valid(ref):
				return ref
		n = n.get_parent()
		depth += 1
	return null
