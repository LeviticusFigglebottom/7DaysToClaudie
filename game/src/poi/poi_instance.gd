class_name PoiInstance
extends Node3D
## One built POI in the world (made by PoiBuilder). Knows its layout, persistent state
## (WorldState.pois[instance_id]), sleepers, rooms (indoor queries, reverb, shelter) and route,
## and runs the building's dungeon mechanics (ADR-0018):
##  * ambush triggers: entering a room, opening or breaking an opening, taking a pickup, the first
##    search of a container or a trap going off wakes that trigger's sleeper group, one after
##    another, already alerted to the player. Each trigger fires once per instance (persisted);
##  * traps (pieces in `traps`, state "armed" / "sprung" / "disarmed" in the ledger) and alarms,
##    which rouse every sleeper in the building.
## Without a session (previews, tests, the editor) it keeps a detached ledger.

var layout: PoiLayout
var instance_id: StringName = &""
var tier: int = 1
var state: Dictionary = {}
var shell: StaticBody3D
var sleepers_spawned: bool = false
## Trap pieces by trap id (registered by PoiBuilder).
var traps: Dictionary = {}
var _sleepers: Dictionary = {}
## Sleepers that woke and left with the player (sleeper id -> Enemy), now roaming.
var _roaming: Dictionary = {}
## Ambush wakes waiting out their stagger: {"at": seconds on _clock, "sid": StringName, "target": Vector3}.
var _pending: Array = []
var _clock: float = 0.0
var _scan_t: float = 0.0
## "level:room char" -> [trigger ids] (room triggers, polled against the player's cell).
var _room_triggers: Dictionary = {}
## "opening:<id>" / "pickup:<id>" / "container:<prop id>" / "trap:<id>" -> [trigger ids].
var _event_triggers: Dictionary = {}
## Opening id -> [alarm trap ids] strung on it: opening or breaking it sets them off.
var _alarms_on: Dictionary = {}


func setup(p_layout: PoiLayout, p_id: StringName) -> void:
	layout = p_layout
	instance_id = p_id
	tier = p_layout.def.tier
	if Game.session != null:
		state = Game.session.world.poi_state(p_id)
		if int(state.get("keys", WorldState.POI_KEYS)) < WorldState.POI_KEYS:
			_rekey_legacy(Game.session.world)
	else:
		state = WorldState.new().poi_state(p_id)
	_index_triggers()


## Pre-v3 saves keyed containers by prop index, unnamed sleepers/traps/pickups by list position
## and notes after the pickups (TD-031). Moves those records onto the stable ids; assumes the
## authored lists only gained ids and appended entries since that save (the retrofit rule).
func _rekey_legacy(world: WorldState) -> void:
	for p: Dictionary in layout.props:
		if p.has("id"):
			world.rekey_container("c:%s:%d" % [instance_id, int(p["index"])], "c:%s:%s" % [instance_id, p["pkey"]])
	var dead: Array = state.get("dead", [])
	for i: int in layout.sleepers.size():
		_rename(dead, "s%d" % i, str(layout.sleepers[i]["sid"]))
	var tr: Dictionary = state.get("traps", {})
	for i2: int in layout.traps.size():
		var old: String = "trap%d" % i2
		var tid: String = str(layout.traps[i2]["tid"])
		if old != tid and tr.has(old) and not tr.has(tid):
			tr[tid] = tr[old]
			tr.erase(old)
	var broken: Array = state.get("broken", [])
	for pk: Dictionary in layout.pickups:
		_rename(broken, str(pk.get("legacy_key", "")), str(pk["pid"]))
	state["keys"] = WorldState.POI_KEYS
	Log.info("poi", "%s: re-keyed saved state to stable ids" % instance_id)


static func _rename(list: Array, old: String, new_id: String) -> void:
	if old == "" or old == new_id or not list.has(old) or list.has(new_id):
		return
	list[list.find(old)] = new_id


func _index_triggers() -> void:
	for t: Dictionary in layout.triggers:
		var tid: String = str(t["id"])
		var key: String = ""
		match str(t["on"]):
			"room":
				_add_to(_room_triggers, "%d:%s" % [int(t["level"]), str(t["room"])], tid)
				continue
			"opening":
				key = "opening:" + str(t["opening"])
			"pickup":
				key = "pickup:" + str(t["pickup"])
			"container":
				key = "container:" + str(t["prop"])
			"trap":
				key = "trap:" + str(t["trap"])
		if key != "":
			_add_to(_event_triggers, key, tid)
	for tp: Dictionary in layout.traps:
		if str(tp["type"]) != "alarm":
			continue
		var wall: Dictionary = layout.walls.get(PoiLayout.edge_key(int(tp["level"]), tp["axis"], tp["edge"]), {})
		if not wall.is_empty() and not (wall["opening"] as Dictionary).is_empty():
			_add_to(_alarms_on, str(wall["opening"]["id"]), str(tp["tid"]))


static func _add_to(d: Dictionary, key: String, v: String) -> void:
	if not d.has(key):
		d[key] = []
	(d[key] as Array).append(v)


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


## Remaining hit points of a damaged door or barricade (default when untouched), so a door
## half beaten in stays half beaten after a reload.
func piece_hp(piece_id: String, default: float) -> float:
	return float((state.get("hp", {}) as Dictionary).get(piece_id, default))


func set_piece_hp(piece_id: String, hp: float) -> void:
	if state.is_empty():
		return
	var d: Dictionary = state.get("hp", {})
	d[piece_id] = snappedf(hp, 0.1)
	state["hp"] = d


# --- Traps ------------------------------------------------------------------------------------

## "armed" (untouched), "sprung" (went off; a can chime's legacy "triggered" reads as sprung) or
## "disarmed".
func trap_state(trap_id: String) -> String:
	var s: String = str((state.get("traps", {}) as Dictionary).get(trap_id, "armed"))
	return "sprung" if s == "triggered" else s


func set_trap_state(trap_id: String, s: String) -> void:
	if not state.has("traps"):
		state["traps"] = {}
	(state["traps"] as Dictionary)[trap_id] = s


## A trap went off: persist it, fire the triggers watching it.
func on_trap_fired(trap_id: String, at: Vector3) -> void:
	if trap_state(trap_id) == "armed":
		set_trap_state(trap_id, "sprung")
	_fire_event("trap:" + trap_id, at)


## Takes an armed trap apart (or salvages a sprung one) for poi.disarm_trap. Returns
## {"ok", "items": {item id: count}, "error"?}; the caller hands the items over.
func disarm_trap(trap_id: String) -> Dictionary:
	var t: Dictionary = layout.trap(trap_id)
	if t.is_empty():
		return {"ok": false, "error": "no such trap"}
	var st: String = trap_state(trap_id)
	if st == "disarmed":
		return {"ok": false, "error": "already disarmed"}
	var cfg: Dictionary = Content.config(&"traps").get(str(t["type"]), {})
	var items: Dictionary = cfg.get("disarm_yield" if st == "armed" else "salvage_yield", {})
	set_trap_state(trap_id, "disarmed")
	var piece: Node = traps.get(trap_id)
	if piece != null and is_instance_valid(piece) and piece.has_method(&"on_disarmed"):
		piece.call(&"on_disarmed")
	return {"ok": true, "items": items, "was": st}


# --- Indoor queries ----------------------------------------------------------------------------

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
		var sid: String = str(s["sid"])
		if dead.has(sid):
			continue
		# Still out hunting from the last visit: it is not back at its post yet.
		var out: Enemy = _roaming.get(StringName(sid), null)
		if is_instance_valid(out) and out.is_alive():
			continue
		_roaming.erase(StringName(sid))
		var local: Vector3 = layout.local_pos(s["level"], s["pos"])
		var group: String = str(s["group"])
		# An ambush whose trigger already fired is spent: survivors are ordinary sleepers now.
		var extra: Dictionary = {"group": group, "held": group != "" and not group_released(group), "guardian": bool(s["guardian"])}
		var e: Enemy = ai.call(&"spawn_sleeper", StringName(str(s.get("enemy", "hollow"))), to_global(local) + Vector3.UP * 0.05,
			global_rotation.y + deg_to_rad(float(s.get("rot", 0.0))), str(s.get("pose", "stand")), instance_id, StringName(sid), layout.def.tier,
			extra)
		if e != null:
			_sleepers[StringName(sid)] = e
			e.died.connect(_on_sleeper_died.bind(sid))


## Leaving the area puts dormant sleepers away. Awake ones that followed the player out are
## handed to the director as ordinary wanderers instead of vanishing mid-chase; a kill still
## counts for this building (the died hook stays), and the sleeper is not duplicated at its post
## until the director has despawned it.
func despawn_sleepers(ai: Node) -> void:
	for sid: StringName in _sleepers:
		var e: Enemy = _sleepers[sid]
		if not is_instance_valid(e) or not e.is_alive():
			continue
		if e.state == Enemy.State.SLEEP:
			ai.call(&"despawn", e)
		else:
			e.poi_id = &""
			_roaming[sid] = e
	_sleepers.clear()
	_pending.clear()
	sleepers_spawned = false


## The live sleeper body for an authored sleeper id (null when not spawned, dead or roaming).
func sleeper(sid: String) -> Enemy:
	var e: Enemy = _sleepers.get(StringName(sid), null)
	return e if is_instance_valid(e) else null


func _on_sleeper_died(_e: Enemy, sid: String) -> void:
	var dead: Array = state.get("dead", [])
	if not dead.has(sid):
		dead.append(sid)
	state["dead"] = dead
	if not bool(state.get("cleared", false)) and dead.size() >= layout.sleepers.size() and Game.session != null:
		state["cleared"] = true
		Game.session.stats["pois_cleared"] = int(Game.session.stats.get("pois_cleared", 0)) + 1
		var p: PlayerState = Game.local_player()
		if p != null:
			p.progression.award("clear_poi_per_tier", tier)
		Events.poi_cleared.emit(instance_id)
		Events.player_status_message.emit("%s cleared." % layout.def.display_name, &"info")


## A trap or loud event inside wakes the sleepers within earshot (held ambushes keep still).
func alert_sleepers(world_pos: Vector3, radius: float = 16.0) -> void:
	for sid: StringName in _sleepers:
		var e: Enemy = _sleepers[sid]
		if is_instance_valid(e) and e.is_alive() and e.global_position.distance_to(world_pos) < radius:
			e.notice(world_pos)


## An alarm rings: every sleeper in the building wakes and heads for it, ambushes included, and
## every ambush is spent (its triggers count as fired).
func alarm(world_pos: Vector3) -> void:
	for t: Dictionary in layout.triggers:
		(state["triggers"] as Dictionary)[str(t["id"])] = true
	for sid: StringName in _sleepers:
		var e: Enemy = _sleepers[sid]
		if is_instance_valid(e) and e.is_alive():
			e.release_hold()
			e.notice(world_pos)


# --- Ambush triggers --------------------------------------------------------------------------

func is_trigger_fired(tid: String) -> bool:
	return (state.get("triggers", {}) as Dictionary).has(tid)


## Whether a group's ambush is spent (any of its triggers has fired).
func group_released(group: String) -> bool:
	for t: Dictionary in layout.triggers:
		if str(t["group"]) == group and is_trigger_fired(str(t["id"])):
			return true
	return false


## Fires a trigger once: its group's dormant sleepers wake one after another (closest first,
## ambush.stagger seconds apart after the trigger's delay), alerted to the player, with an audible
## stir. Returns false if it already fired, does not exist, or the building's sleepers are not out
## (nobody to ambush yet: it stays armed). `at`: where it was set off (fallback target).
func fire_trigger(tid: String, at: Vector3 = Vector3.INF) -> bool:
	var t: Dictionary = layout.trigger(tid)
	if t.is_empty() or is_trigger_fired(tid) or not sleepers_spawned:
		return false
	(state["triggers"] as Dictionary)[tid] = true
	var group: StringName = StringName(str(t["group"]))
	var target: Vector3 = _ambush_target(at)
	var members: Array[Enemy] = []
	for sid: StringName in _sleepers:
		var e: Enemy = _sleepers[sid]
		if is_instance_valid(e) and e.is_alive() and e.group == group and e.state == Enemy.State.SLEEP:
			members.append(e)
	members.sort_custom(func(a: Enemy, b: Enemy) -> bool: return a.global_position.distance_squared_to(target) < b.global_position.distance_squared_to(target))
	var cfg: Dictionary = Content.config(&"traps").get("ambush", {})
	var stagger: Array = cfg.get("stagger", [0.15, 0.6])
	var rng := RandomNumberGenerator.new()
	rng.seed = Ids.hash64("ambush:%s:%s" % [instance_id, tid])
	var when: float = _clock + maxf(0.0, float(t["delay"]))
	var centre := Vector3.ZERO
	for e2: Enemy in members:
		when += rng.randf_range(float(stagger[0]), float(stagger[1]))
		_pending.append({"at": when, "sid": e2.sleeper_id, "target": target})
		centre += e2.global_position
	if not members.is_empty():
		centre /= float(members.size())
		# The stir: something shifts in the dark before they are on their feet.
		Audio.play_3d(&"sfx/ambush_stir", centre + Vector3.UP, {"volume_db": float(cfg.get("cue_volume_db", 2.0)), "max_distance": 45.0})
	Log.info("poi", "%s: trigger '%s' wakes group '%s' (%d)" % [instance_id, tid, group, members.size()])
	return true


func _ambush_target(at: Vector3) -> Vector3:
	var p: Node3D = _player_node()
	if p != null:
		return p.global_position
	return at if at != Vector3.INF else global_position


func _player_node() -> Node3D:
	if Game.world == null:
		return null
	return Game.world.get(&"player") as Node3D


## Fires the room triggers of the cell a player stands in.
func check_player_at(world_pos: Vector3) -> void:
	var loc: Array = locate(world_pos)
	if int(loc[0]) == -999:
		return
	var ch: String = layout.room_at(loc[0], loc[1])
	if not layout.is_room(ch):
		return
	for tid: String in _room_triggers.get("%d:%s" % [int(loc[0]), ch], []):
		fire_trigger(tid, world_pos)


## A door was opened or an opening (door, glass, boards, barricade) broken: its triggers fire and
## alarms strung on it go off.
func on_opening_event(op_id: String, at: Vector3) -> void:
	_fire_event("opening:" + op_id, at)
	for tid: String in _alarms_on.get(op_id, []):
		var piece: Node = traps.get(tid)
		if piece != null and is_instance_valid(piece) and piece.has_method(&"trip"):
			piece.call(&"trip", null)


func on_pickup_taken(pickup_id: String, at: Vector3) -> void:
	_fire_event("pickup:" + pickup_id, at)


## First search of a container prop (its authored id).
func on_container_searched(prop_key: String, at: Vector3) -> void:
	_fire_event("container:" + prop_key, at)


func _fire_event(key: String, at: Vector3) -> void:
	for tid: String in _event_triggers.get(key, []):
		fire_trigger(tid, at)


func _physics_process(delta: float) -> void:
	if not sleepers_spawned and _pending.is_empty():
		return
	_clock += delta
	if not _pending.is_empty():
		_run_pending()
	_scan_t -= delta
	if _scan_t <= 0.0 and sleepers_spawned and not _room_triggers.is_empty():
		_scan_t = 0.15
		var p: Node3D = _player_node()
		if p != null:
			check_player_at(p.global_position)


## Wakes the ambushers whose stagger has run out (closest first).
func _run_pending() -> void:
	var p: Node3D = _player_node()
	var i: int = 0
	while i < _pending.size():
		var w: Dictionary = _pending[i]
		if float(w["at"]) > _clock:
			i += 1
			continue
		_pending.remove_at(i)
		var e: Enemy = _sleepers.get(w["sid"], null)
		if is_instance_valid(e) and e.is_alive():
			e.ambush(p.global_position if p != null else (w["target"] as Vector3))


## Wakes every pending ambusher now (tests, debug).
func flush_ambush() -> void:
	_clock += 1000.0
	_run_pending()
