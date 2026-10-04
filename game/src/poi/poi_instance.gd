class_name PoiInstance
extends Node3D
## One built POI in the world (made by PoiBuilder). Knows its layout, persistent state
## (WorldState.pois[instance_id]), sleepers, rooms (indoor queries, reverb, shelter) and route.

var layout: PoiLayout
var instance_id: StringName = &""
var tier: int = 1
var state: Dictionary = {}
var shell: StaticBody3D
var sleepers_spawned: bool = false
var _sleepers: Dictionary = {}


func setup(p_layout: PoiLayout, p_id: StringName) -> void:
	layout = p_layout
	instance_id = p_id
	tier = p_layout.def.tier
	if Game.session != null:
		state = Game.session.world.poi_state(p_id)


func piece_state(piece_id: String, default: String) -> String:
	if state.is_empty():
		return default
	if (state.get("broken", []) as Array).has(piece_id):
		return "broken"
	return str((state.get("doors", {}) as Dictionary).get(piece_id, default))


func set_piece_state(piece_id: String, s: String) -> void:
	if state.is_empty():
		return
	if s == "broken":
		var b: Array = state.get("broken", [])
		if not b.has(piece_id):
			b.append(piece_id)
		state["broken"] = b
	elif s == "triggered":
		(state["traps"] as Dictionary)[piece_id] = s
	else:
		(state["doors"] as Dictionary)[piece_id] = s


## Point in world space -> (level, cell) or level -999 when outside every level band.
func locate(world_pos: Vector3) -> Array:
	var p: Vector3 = to_local(world_pos)
	for li: int in layout.level_ids:
		var y: float = layout.level_y(li)
		if p.y >= y - 0.5 and p.y < y + PoiLayout.STOREY - 0.2:
			return [li, Vector2i(int(floor(p.x - layout.origin.x)), int(floor(p.z - layout.origin.y)))]
	return [-999, Vector2i.ZERO]


func is_indoors(world_pos: Vector3) -> bool:
	var loc: Array = locate(world_pos)
	return int(loc[0]) != -999 and layout.is_room(layout.room_at(loc[0], loc[1]))


## Room type at a world position ("" outside) — reverb/ambience and loot hints.
func room_type_at(world_pos: Vector3) -> String:
	var loc: Array = locate(world_pos)
	if int(loc[0]) == -999:
		return ""
	var ch: String = layout.room_at(loc[0], loc[1])
	return str(layout.room_def(loc[0], ch).get("type", "room")) if layout.is_room(ch) else ""


func world_bounds() -> AABB:
	var r: Rect2 = layout.extent()
	var top: float = layout.level_y(layout.level_ids.back()) + PoiLayout.STOREY + 3.0
	var bottom: float = layout.level_y(layout.level_ids.front()) - 1.0
	var local := AABB(Vector3(r.position.x, bottom, r.position.y), Vector3(r.size.x, top - bottom, r.size.y))
	return global_transform * local


# --- Sleepers ---------------------------------------------------------------------------------

func spawn_sleepers(ai: Node) -> void:
	if sleepers_spawned or ai == null:
		return
	sleepers_spawned = true
	var dead: Array = state.get("dead", [])
	for i: int in layout.sleepers.size():
		var s: Dictionary = layout.sleepers[i]
		var sid: String = str(s.get("id", "s%d" % i))
		if dead.has(sid):
			continue
		var local: Vector3 = layout.local_pos(s["level"], s["pos"])
		var e: Enemy = ai.call(&"spawn_sleeper", StringName(str(s.get("enemy", "hollow"))), to_global(local) + Vector3.UP * 0.05,
			global_rotation.y + deg_to_rad(float(s.get("rot", 0.0))), str(s.get("pose", "stand")), instance_id, StringName(sid))
		if e != null:
			_sleepers[StringName(sid)] = e
			e.died.connect(_on_sleeper_died.bind(sid))


func despawn_sleepers(ai: Node) -> void:
	for sid: StringName in _sleepers:
		var e: Enemy = _sleepers[sid]
		if is_instance_valid(e) and e.is_alive():
			ai.call(&"despawn", e)
	_sleepers.clear()
	sleepers_spawned = false


func _on_sleeper_died(_e: Enemy, sid: String) -> void:
	var dead: Array = state.get("dead", [])
	if not dead.has(sid):
		dead.append(sid)
	state["dead"] = dead
	if not bool(state.get("cleared", false)) and dead.size() >= layout.sleepers.size():
		state["cleared"] = true
		Game.session.stats["pois_cleared"] = int(Game.session.stats.get("pois_cleared", 0)) + 1
		var p: PlayerState = Game.local_player()
		if p != null:
			p.progression.add_xp(int(Content.config(&"progression").get("xp", {}).get("clear_poi_per_tier", 120)) * tier)
		Events.poi_cleared.emit(instance_id)
		Events.player_status_message.emit("%s cleared." % layout.def.display_name, &"info")


## A trap or loud event inside wakes the sleepers within earshot.
func alert_sleepers(world_pos: Vector3) -> void:
	for sid: StringName in _sleepers:
		var e: Enemy = _sleepers[sid]
		if is_instance_valid(e) and e.is_alive() and e.global_position.distance_to(world_pos) < 16.0:
			e.notice(world_pos)
