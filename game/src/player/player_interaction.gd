class_name PlayerInteraction
extends Node
## Finds what the player is looking at and runs interactions.
##
## Interactable protocol (duck-typed; the collider or its nearest ancestor implementing it):
##   interact_text(player: Player) -> String          prompt ("" = not interactable now)
##   interact(player: Player) -> void
##   interact_hold_time(player: Player) -> float      optional; > 0 = hold to complete (searching)
##   alt_interact_text(player: Player) -> String      optional second action, done by holding the
##   alt_interact(player: Player) -> void             `cancel` key (X) ALT_HOLD s ("" = none now):
##                                                    taking down a blueprint ghost

signal focus_changed(target: Object, text: String)
signal hold_progress(t: float)

const MASK: int = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 4) | (1 << 6) | (1 << 7) | (1 << 12)
## Seconds the cancel key is held for a second action: long enough that a tap meant to cancel a
## placement or close a page never takes anything down.
const ALT_HOLD: float = 1.0

var player: Player
var target: Object = null
var prompt: String = ""
var hold_t: float = 0.0
var hold_needed: float = 0.0
var last_hit: Dictionary = {}
## Context for the held tool on what is aimed at (a hammer on a building piece: its health and
## what a strike does), shown under the prompt.
var tool_hint: String = ""
## The target's second action for the line under the prompt ("hold [X] to take down the …
## blueprint"), "" when it has none.
var alt_prompt: String = ""
## What a running hold started on: looking at something else cancels it rather than finishing
## the search on the new target.
var _hold_target: Object = null
## The running hold is the second action (on the cancel key), not an interact hold.
var _hold_alt: bool = false
## A blueprint was being placed last frame: its cancel press (handled by BuildingManager, which
## runs first) must not also start taking a ghost down.
var _was_placing: bool = false
## One reused instance, so the focus doesn't change every frame while you look at a stream.
var _water := WaterSource.new()


func _ready() -> void:
	player = get_parent() as Player


func _physics_process(delta: float) -> void:
	if player == null or player.state == null:
		return
	_scan()
	var placing: bool = _placing()
	var was_placing: bool = _was_placing
	_was_placing = placing
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
			_hold_target = target
			_hold_alt = false
	elif alt_prompt != "" and not placing and not was_placing and Input.is_action_just_pressed(&"cancel"):
		hold_needed = ALT_HOLD
		hold_t = 0.0
		_hold_target = target
		_hold_alt = true
	if hold_needed > 0.0:
		if target == null or target != _hold_target or not Input.is_action_pressed(&"cancel" if _hold_alt else &"interact"):
			_cancel_hold()
		else:
			hold_t += delta
			hold_progress.emit(hold_t / hold_needed)
			if hold_t >= hold_needed:
				var t: Object = target
				var alt: bool = _hold_alt
				_cancel_hold()
				t.call(&"alt_interact" if alt else &"interact", player)


func _cancel_hold() -> void:
	if hold_needed > 0.0:
		hold_progress.emit(0.0)
	hold_needed = 0.0
	hold_t = 0.0
	_hold_target = null
	_hold_alt = false


func _placing() -> bool:
	var building: Node = Game.world.get(&"building") if Game.world != null else null
	return building != null and building.has_method(&"is_placing") and bool(building.call(&"is_placing"))


## The key or mouse button an input action is bound to now (rebinds included), named as the
## Controls screen names it ("X", "Middle mouse"; "?" when it has neither), for prompts.
static func key_label(action: StringName) -> String:
	# The pad's button while a pad is in use (Settings.input_label, Presentation round 4).
	return Settings.input_label(String(action))


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
	if found == null:
		found = _water_on_ray(from, to, hit)
	tool_hint = _tool_hint(hit)
	var text: String = ""
	if found != null:
		text = str(found.call(&"interact_text", player))
		if text == "":
			found = null
	alt_prompt = alt_text(found, player)
	if found != target or text != prompt:
		target = found
		prompt = text
		focus_changed.emit(target, prompt)


## "hold [X] to take down the Campfire blueprint (3 Stone back)" for a target with a second
## action, "" otherwise.
static func alt_text(found: Object, p: Player) -> String:
	if found == null or not found.has_method(&"alt_interact_text"):
		return ""
	var what: String = str(found.call(&"alt_interact_text", p))
	return "hold [%s] to %s" % [key_label(&"cancel"), what] if what != "" else ""


func _tool_hint(hit: Dictionary) -> String:
	if hit.is_empty() or Game.world == null:
		return ""
	var held: ItemDef = Content.item(player.state.equipped_item())
	if held == null or not held.provides_tool("hammer"):
		return ""
	var piece: StructurePiece = hit["collider"] as StructurePiece
	var building: Node = Game.world.get(&"building")
	if piece == null or building == null or not is_instance_valid(piece):
		return ""
	return str(building.call(&"hammer_hint", piece, player.state))


## A lake or river surface along the look ray (before anything solid it hit), or null. Water has
## no collider, so the ray is stepped against the water system's surface heights.
func _water_on_ray(from: Vector3, to: Vector3, hit: Dictionary) -> WaterSource:
	var water: Node = Game.world.get(&"water") if Game.world != null else null
	if water == null:
		return null
	var end: Vector3 = hit["position"] if not hit.is_empty() else to
	# Reach a little further down than up: you kneel to drink from a bank.
	end += (end - from).normalized() * 0.6
	var steps: int = maxi(2, int(from.distance_to(end) / 0.25))
	for i: int in range(1, steps + 1):
		var q: Vector3 = from.lerp(end, float(i) / float(steps))
		var level: float = water.call(&"water_level_at", q.x, q.z)
		if level != -INF and q.y <= level + 0.05:
			_water.point = Vector3(q.x, level, q.z)
			return _water
	return null


static func find_interactable(o: Object) -> Object:
	var n: Node = o as Node
	var depth: int = 0
	while n != null and depth < 6:
		if n.has_method(&"interact") and n.has_method(&"interact_text"):
			return n
		if n.has_meta(&"interactable"):
			var ref: Variant = n.get_meta(&"interactable")
			if is_instance_valid(ref):
				return ref
		n = n.get_parent()
		depth += 1
	return null
