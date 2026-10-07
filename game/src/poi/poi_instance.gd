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
## ADR-0022: sit/lie sleepers spawn on their seat or bed (SleeperAnchors, Enemy.perch). A trigger
## that fires, or a loud trap that goes off, while the sleepers are not spawned is spent all the
## same and rouses who would have woken (`roused` in the ledger): they spawn awake by their posts
## next time, heading for where it happened. A weak floor giving way asks for a nav rebake
## (geometry_changed).
## Without a session (previews, tests, the editor) it keeps a detached ledger.

## Walkable geometry changed at a world position (a weak floor gave way): PoiManager has the nav
## tiles there rebaked so the Hollowed stop pathing over the hole.
signal geometry_changed(world_pos: Vector3)

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
## sid -> the seat or bed it lands on (SleeperAnchors.assign, POI-local), computed on first use.
var _seats: Dictionary = {}
var _seats_done: bool = false


## Route cues on the entry windows (RouteCues, ADR-0022) go in once the building is in the tree.
var _cues_built: bool = false


func _ready() -> void:
	if not _cues_built and layout != null:
		_cues_built = true
		RouteCues.build(self)


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
			# A tall room's open space is that room (ADR-0021): indoor queries, shelter, reverb and
			# room triggers answer for the floor it rises from.
			return layout.floor_cell(li, Vector2i(int(floor(p.x - layout.origin.x)), int(floor(p.z - layout.origin.y))))
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
	return global_transform * local_bounds()


## The building's box in its own frame (every level, buried ones too, a roof's height above).
func local_bounds() -> AABB:
	var r: Rect2 = layout.extent()
	var top: float = layout.level_y(layout.level_ids.back()) + PoiLayout.STOREY + 3.0
	var bottom: float = layout.level_y(layout.level_ids.front()) - 1.0
	return AABB(Vector3(r.position.x, bottom, r.position.y), Vector3(r.size.x, top - bottom, r.size.y))


# --- Sleepers ---------------------------------------------------------------------------------

func spawn_sleepers(ai: Node) -> void:
	if sleepers_spawned or ai == null:
		return
	sleepers_spawned = true
	var dead: Array = state.get("dead", [])
	var roused: Dictionary = state.get("roused", {})
	var seats: Dictionary = seat_plan()
	for i: int in layout.sleepers.size():
		var s: Dictionary = layout.sleepers[i]
		var sid: String = str(s["sid"])
		if dead.has(sid):
			continue
		# Still out hunting from the last visit: it is not back at its post yet.
		# Untyped first: the roamer may have been freed meanwhile (despawned far away), and a freed
		# instance can't be assigned to a typed variable.
		var out: Variant = _roaming.get(StringName(sid), null)
		if is_instance_valid(out) and (out as Enemy).is_alive():
			continue
		_roaming.erase(StringName(sid))
		var local: Vector3 = sleeper_local(layout, s)
		var yaw: float = global_rotation.y + deg_to_rad(float(s.get("rot", 0.0)))
		var group: String = str(s["group"])
		# An ambush whose trigger already fired is spent: survivors are ordinary sleepers now.
		var extra: Dictionary = {"group": group, "held": group != "" and not group_released(group), "guardian": bool(s["guardian"])}
		var seat: Dictionary = seats.get(sid, {})
		if roused.has(sid):
			# Woken while nobody was near: up and about by its post (off its seat or bed), heading
			# for where it happened. It has been seen to now; from here on it is an ordinary body.
			var at: Array = roused[sid]
			extra["awake_at"] = to_global(Vector3(float(at[0]), float(at[1]), float(at[2])))
			extra["held"] = false
			if not seat.is_empty():
				local = seat["exit"]
				yaw = global_rotation.y + float(seat["exit_yaw"])
			roused.erase(sid)
		elif not seat.is_empty():
			extra["perch"] = _world_seat(seat)
		var e: Enemy = ai.call(&"spawn_sleeper", StringName(str(s.get("enemy", "hollow"))), _sleeper_spawn_at(s, local),
			yaw, str(s.get("pose", "stand")), instance_id, StringName(sid), layout.def.tier, extra)
		if e != null:
			_sleepers[StringName(sid)] = e
			e.died.connect(_on_sleeper_died.bind(sid))


## Which sit/lie sleepers land on which seat or bed (SleeperAnchors.assign; POI-local). A pure
## function of the layout, so every visit and every machine poses them the same.
func seat_plan() -> Dictionary:
	if not _seats_done:
		_seats_done = true
		_seats = SleeperAnchors.assign(layout)["by_sleeper"]
	return _seats


## The seat or bed a sleeper lands on ({} on the floor), POI-local.
func seat_of(sid: String) -> Dictionary:
	return seat_plan().get(sid, {})


## A landed seat in world space for Enemy.perch.
func _world_seat(seat: Dictionary) -> Dictionary:
	var pt: Vector3 = seat["point"]
	return {"kind": seat["kind"], "lean": seat["lean"], "point": to_global(pt),
		"floor": to_global(Vector3(pt.x, float(seat["floor"]), pt.z)).y, "yaw": global_rotation.y + float(seat["yaw"]),
		"exit": to_global(seat["exit"] as Vector3), "exit_yaw": global_rotation.y + float(seat["exit_yaw"])}


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
	check_cleared()


## Counts the building cleared once every sleeper is dead (also after a rebuild: a sleeper that
## roamed off can die while its building is freed, PoiManager._on_roamer_died).
func check_cleared() -> void:
	var dead: Array = state.get("dead", [])
	if not bool(state.get("cleared", false)) and dead.size() >= layout.sleepers.size() and Game.session != null:
		state["cleared"] = true
		Game.session.stats["pois_cleared"] = int(Game.session.stats.get("pois_cleared", 0)) + 1
		var p: PlayerState = Game.local_player()
		if p != null:
			p.progression.award("clear_poi_per_tier", tier)
		Events.poi_cleared.emit(instance_id)
		Events.player_status_message.emit("%s cleared." % layout.def.display_name, &"info")


## A trap or loud event inside wakes the sleepers within earshot (held ambushes keep still). While
## they are not spawned, the ones within earshot are roused instead (ADR-0022).
func alert_sleepers(world_pos: Vector3, radius: float = 16.0) -> void:
	if not sleepers_spawned:
		var at: Vector3 = to_local(world_pos)
		for s: Dictionary in layout.sleepers:
			if not _is_held(s) and _sleeper_local(s).distance_to(at) < radius:
				rouse(str(s["sid"]), at)
		return
	for sid: StringName in _sleepers:
		var e: Enemy = _sleepers[sid]
		if is_instance_valid(e) and e.is_alive() and e.global_position.distance_to(world_pos) < radius:
			e.notice(world_pos)


## An alarm rings. Set off by the player (ADR-0018): every sleeper in the building wakes and heads
## for it, ambushes included, and every ambush is spent (its triggers count as fired); with nobody
## spawned, every sleeper is roused. Set off by a Hollowed (ADR-0022): its ringing wakes sleepers
## through the stimulus fields like any noise (AlarmTrap emits it), and while nobody is near, those
## that would have heard it are roused.
func alarm(world_pos: Vector3, by_player: bool = true) -> void:
	if not by_player:
		if not sleepers_spawned:
			on_trap_noise(world_pos, float(PoiPieces.cfg("alarm").get("noise", 55.0)), &"alarm")
		return
	for t: Dictionary in layout.triggers:
		(state["triggers"] as Dictionary)[str(t["id"])] = true
	if not sleepers_spawned:
		for s: Dictionary in layout.sleepers:
			rouse(str(s["sid"]), to_local(world_pos))
		return
	for sid: StringName in _sleepers:
		var e: Enemy = _sleepers[sid]
		if is_instance_valid(e) and e.is_alive():
			e.release_hold()
			e.notice(world_pos)


## A trap went off with nobody spawned to hear it (a Hollowed tripped it far from the player): the
## sleepers that would have woken to it by stimulus are roused (ADR-0022): ordinary ones within
## loudness x unspawned.hearing, held ones only for ambush wake_kinds within the wake radius. While
## the sleepers are out, the stimulus fields do this themselves.
func on_trap_noise(world_pos: Vector3, loudness: float, kind: StringName) -> void:
	if sleepers_spawned:
		return
	var amb: Dictionary = PoiPieces.cfg("ambush")
	var hearing: float = float(PoiPieces.cfg("unspawned").get("hearing", 0.7))
	var at: Vector3 = to_local(world_pos)
	for s: Dictionary in layout.sleepers:
		var d: float = _sleeper_local(s).distance_to(at)
		if _is_held(s):
			if (amb.get("wake_kinds", []) as Array).has(String(kind)) and d <= float(amb.get("wake_radius", 14.0)):
				rouse(str(s["sid"]), at)
		elif d <= loudness * hearing:
			rouse(str(s["sid"]), at)


## The ledger of sleepers roused while the building was empty: sid -> POI-local [x, y, z] of where
## it happened. Saved; consumed when they next spawn (awake).
func roused() -> Dictionary:
	return state.get("roused", {})


func is_roused(sid: String) -> bool:
	return roused().has(sid)


## Marks one sleeper roused (no-op for the dead and the already roused).
func rouse(sid: String, local_at: Vector3) -> void:
	if (state.get("dead", []) as Array).has(sid):
		return
	if not state.has("roused"):
		state["roused"] = {}
	var r: Dictionary = state["roused"]
	if not r.has(sid):
		r[sid] = [snappedf(local_at.x, 0.01), snappedf(local_at.y, 0.01), snappedf(local_at.z, 0.01)]


## Whether an authored sleeper is held right now (a grouped one whose ambush is not spent).
func _is_held(s: Dictionary) -> bool:
	var g: String = str(s["group"])
	return g != "" and not group_released(g)


func _sleeper_local(s: Dictionary) -> Vector3:
	return sleeper_local(layout, s)


## Where an authored sleeper stands, POI-local: on its level's floor in a room (or on the porch
## deck), on the pad (y = 0: the ground PoiManager levels under a building and its yard) in the yard
## (TD-269), as PoiBuilder._base_y stands yard props, pickups and bear traps.
static func sleeper_local(lay: PoiLayout, s: Dictionary) -> Vector3:
	var p: Vector3 = lay.local_pos(int(s["level"]), s["pos"])
	if lay.is_yard(int(s["level"]), s["cell"]) and not PoiBuilder.porch_cells(lay).has(s["cell"]):
		p.y = 0.0
	return p


## A sleeper's spawn point in world space: its floor spot (sleeper_local); in the yard the terrain
## under it, which is the pad give or take the heightfield's grid and its skirt, so the body is not
## dropped from (or into) the ground. Lifted a little so it settles onto what is under it.
func _sleeper_spawn_at(s: Dictionary, local: Vector3) -> Vector3:
	var at: Vector3 = to_global(local)
	if layout.is_yard(int(s["level"]), s["cell"]) and not PoiBuilder.porch_cells(layout).has(s["cell"]) \
			and Game.world != null and Game.world.has_method(&"height_at"):
		var ground: float = float(Game.world.call(&"height_at", at.x, at.z))
		# A ground far off the pad is a world the pad does not describe (stand-in terrain, a test
		# rig): keep the pad.
		if absf(ground - at.y) < 2.0:
			at.y = ground
	return at + Vector3.UP * 0.05


## A weak floor gave way: the nav tiles there are rebaked (PoiManager), so the Hollowed stop
## pathing over the hole.
func on_floor_collapsed(world_pos: Vector3) -> void:
	geometry_changed.emit(world_pos)


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
## stir. Returns false if it already fired or does not exist. `at`: where it was set off (fallback
## target). With the building's sleepers not spawned (the Hum broke the door far from the player,
## ADR-0022) it is spent all the same: the group is roused and is up and about next time.
func fire_trigger(tid: String, at: Vector3 = Vector3.INF) -> bool:
	var t: Dictionary = layout.trigger(tid)
	if t.is_empty() or is_trigger_fired(tid):
		return false
	(state["triggers"] as Dictionary)[tid] = true
	var group: StringName = StringName(str(t["group"]))
	if not sleepers_spawned:
		var local_at: Vector3 = to_local(at) if at != Vector3.INF else layout.cell_center(0, Vector2i(layout.extent().get_center() - layout.origin))
		for s: Dictionary in layout.sleepers:
			if str(s["group"]) == String(group):
				rouse(str(s["sid"]), local_at)
		Log.info("poi", "%s: trigger '%s' fired with nobody near: group '%s' roused" % [instance_id, tid, group])
		return true
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
## alarms strung on it go off. `by_player`: false when a Hollowed (the Hum) broke it.
func on_opening_event(op_id: String, at: Vector3, by_player: bool = true) -> void:
	_fire_event("opening:" + op_id, at)
	for tid: String in _alarms_on.get(op_id, []):
		var piece: Node = traps.get(tid)
		if piece != null and is_instance_valid(piece) and piece.has_method(&"trip"):
			piece.call(&"trip", null, by_player)


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
