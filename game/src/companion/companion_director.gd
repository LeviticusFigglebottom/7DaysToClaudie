class_name CompanionDirector
extends Node
## The companion's bookkeeping (ADR-0058, Ezra Vane): a GameWorld module. Before he is recruited
## it seats him at his camp (the CompanionDef's `camp` POI) while the player is near; recruited, it
## keeps his body in the world beside the player (spawned after a load, placed beside the player
## out of sight past teleport_beyond, after a respawn, a sleep or a load far away), takes him out
## when he bleeds out and brings him back at the player's spawn point the next dawn (or never, under
## the permadeath death penalty), and saves him (WorldState.companion) on Events.game_saving. His
## orders and the rest go through commands (ADR-0003): companion.recruit, companion.order
## {order: follow|stay|guard, spot?}, companion.revive. E on him opens the order card
## (CompanionScreen); the quick-order key (`companion_order`, H) toggles follow / stay.
##
## His body is an Enemy spawned by the AI director with the fixed id BODY_ID (so the Hollowed and
## the Ashen find him through its spatial queries and EnemyFoes), which never despawns, counts or
## culls him.

const BODY_ID: StringName = &"companion:ezra"
const COMMANDS: Array[StringName] = [&"companion.recruit", &"companion.order", &"companion.revive"]
const TICK: float = 0.5
## Following, he is brought to the player after a respawn, sleep or load when further than this.
const REJOIN: float = 20.0

var world: Node
var cdef: CompanionDef
var body: Enemy = null
var screen: Control = null
var _tick: float = 0.0
## Set by a respawn, a sleep or a load: bring him to the player on the next tick if far.
var _rejoin: bool = true
## Tests stand in their own camp listing: () -> Array of {id, def, pos, xf?}.
var buildings_source: Callable = Callable()


func setup_world(w: Node) -> void:
	world = w
	cdef = Content.get_def(&"companion", &"ezra") as CompanionDef
	if cdef == null:
		return
	for c: StringName in COMMANDS:
		Game.register_command(c, Callable(self, "_cmd_" + String(c).replace(".", "_")))
	Events.game_saving.connect(_on_game_saving)
	Events.player_spawned.connect(func(_pid: StringName) -> void: _rejoin = true)
	Events.player_slept.connect(func(_pid: StringName, _h: float) -> void: _rejoin = true)


func _exit_tree() -> void:
	for c: StringName in COMMANDS:
		Game.unregister_command(c)
	body = null


## The saved state (WorldState.companion): {recruited, dead, position: [3], yaw, health (fraction),
## downed_t (s left, -1 up), order, spot: [3] | [], out_until_day (-1 not out)}.
static func state() -> Dictionary:
	return Game.session.world.companion


func recruited() -> bool:
	return bool(state().get("recruited", false))


## Out of the world until a dawn (bled out), or gone for good.
func is_out() -> bool:
	return int(state().get("out_until_day", -1)) >= 0 or bool(state().get("dead", false))


func mind() -> CompanionMind:
	return body.ally if _has_body() else null


func _has_body() -> bool:
	return body != null and is_instance_valid(body) and not body.is_queued_for_deletion()


func _ai() -> Node:
	return world.get(&"ai") if world != null else null


func _player() -> Player:
	return world.get(&"player") as Player if world != null else null


# --- The loop --------------------------------------------------------------------------------------

func _process(delta: float) -> void:
	if cdef == null or Game.session == null:
		return
	_tick += delta
	if _tick < TICK:
		return
	_tick = 0.0
	tick()


## One bookkeeping step (tests call it directly).
func tick() -> void:
	var p: Player = _player()
	if p == null or _ai() == null or (world.get(&"is_ready") != null and not bool(world.get(&"is_ready"))):
		return
	if bool(state().get("dead", false)):
		return
	if not recruited():
		_follow_camp(p)
		return
	if _has_body() and body.ally.gone:
		_bled_out()
		return
	if int(state().get("out_until_day", -1)) >= 0:
		if Game.session.clock.day() >= int(state()["out_until_day"]) and not Game.session.clock.is_night():
			_come_back(p)
		return
	if not _has_body():
		_restore(p)
		return
	var m: CompanionMind = body.ally
	if m.downed or m.rising_t > 0.0 or m.order != "follow":
		_rejoin = false
		return
	var d: float = body.global_position.distance_to(p.global_position)
	if d > CompanionDef.fnum(cdef.follow, "teleport_beyond", 120.0) or (_rejoin and d > REJOIN):
		place_beside(p)
	_rejoin = false


## Seats him at his camp while the player is within its wake range; out past its sleep range.
func _follow_camp(p: Player) -> void:
	var camp: Dictionary = camp_spot()
	if camp.is_empty():
		return
	var at: Vector3 = camp["pos"]
	var d: float = Vector2(p.global_position.x - at.x, p.global_position.z - at.z).length()
	if not _has_body() and d <= CompanionDef.fnum(cdef.camp, "wake_range", 140.0):
		body = _spawn(at, float(camp["yaw"]))
		if body != null:
			body._fit_pose_shape("sit")
	elif _has_body() and d > CompanionDef.fnum(cdef.camp, "sleep_range", 170.0):
		_remove_body()


## Where he sits at his camp: {pos, yaw} from the first placed building of the camp's POI def, its
## offset building-local ({} when the world has no camp, or it isn't built yet).
func camp_spot() -> Dictionary:
	var poi: String = str(cdef.camp.get("poi", ""))
	var off: Array = cdef.camp.get("offset", [0.0, 0.0])
	var list: Array = buildings_source.call() if buildings_source.is_valid() else _buildings()
	for v: Variant in list:
		var b: Dictionary = v
		if str(b.get("def", "")) != poi:
			continue
		var xf: Variant = b.get("xf", null)
		var pois: Node = world.get(&"pois")
		if xf == null and pois != null and (pois.get(&"instances") as Dictionary).has(b.get("id", &"")):
			var inst: PoiInstance = (pois.get(&"instances") as Dictionary)[b["id"]]
			var lp := Vector3(inst.layout.origin.x + float(off[0]), 0.0, inst.layout.origin.y + float(off[1]))
			xf = inst.global_transform.translated_local(lp)
		if xf == null:
			return {}  # placed but not built yet: his spot is building-local
		var t: Transform3D = xf
		var pos: Vector3 = t.origin
		pos.y = _ground(pos)
		return {"pos": pos, "yaw": t.basis.get_euler().y + deg_to_rad(float(cdef.camp.get("yaw", 0.0))), "building": str(b.get("id", ""))}
	return {}


func _buildings() -> Array:
	var pois: Node = world.get(&"pois") if world != null else null
	return pois.call(&"all_buildings") if pois != null and pois.has_method(&"all_buildings") else []


func _ground(at: Vector3) -> float:
	return float(world.call(&"height_at", at.x, at.z)) if world != null and world.has_method(&"height_at") else at.y


func _spawn(pos: Vector3, yaw: float) -> Enemy:
	var e: Enemy = _ai().call(&"spawn", cdef.enemy, pos + Vector3.UP * 0.1, {"id": String(BODY_ID), "authored": true,
		"tier": "normal", "yaw": yaw}) as Enemy
	if e == null or e.ally == null:
		return e
	# He is no Hollowed: the world settings for enemy health and damage don't apply to him.
	e.max_health = e.def.health
	e.health = e.max_health
	e.damage_mult = 1.0
	e.ally.recruited = recruited()
	return e


func _remove_body() -> void:
	if _has_body():
		var ai: Node = _ai()
		if ai != null:
			ai.call(&"despawn", body)
		else:
			body.queue_free()
	body = null


## A recruited companion with no body (a load, or back from being out): placed where he was saved,
## or beside the player.
func _restore(p: Player) -> void:
	var st: Dictionary = state()
	var pos: Vector3 = _vec(st.get("position"))
	if pos == Vector3.INF:
		pos = beside(p)
	body = _spawn(pos, float(st.get("yaw", 0.0)))
	if body == null:
		return
	var m: CompanionMind = body.ally
	m.recruited = true
	body.health = maxf(1.0, body.max_health * clampf(float(st.get("health", 1.0)), 0.0, 1.0))
	var spot: Vector3 = _vec(st.get("spot"))
	m.set_order(str(st.get("order", "follow")), spot)
	var dt: float = float(st.get("downed_t", -1.0))
	if dt >= 0.0:
		m.go_down(null, dt)
	_rejoin = true


## Puts him beside the player, out of sight (behind them), on the ground.
func place_beside(p: Player) -> void:
	if not _has_body():
		return
	body.global_position = beside(p)
	body.velocity = Vector3.ZERO
	body.foe = null
	body._set_state(Enemy.State.IDLE)


func beside(p: Player) -> Vector3:
	var fwd: Vector3 = -p.camera.global_transform.basis.z if p.camera != null else Vector3.FORWARD
	fwd.y = 0.0
	fwd = fwd.normalized() if fwd.length() > 0.01 else Vector3.FORWARD
	var at: Vector3 = p.global_position - fwd * 6.0 + Vector3(fwd.z, 0.0, -fwd.x) * 2.0
	var g: float = _ground(at)
	at.y = maxf(g, p.global_position.y - 1.0) + 0.3 if g > -INF else p.global_position.y
	return at


## Nobody revived him: he is out until the next dawn (losing what he carried), or for good under
## the permadeath death penalty.
func _bled_out() -> void:
	var m: CompanionMind = body.ally
	m.bark("out")
	_remove_body()
	var st: Dictionary = state()
	st.erase("position")
	st["downed_t"] = -1.0
	if GameRules.current().choice("death_penalty") == "permadeath":
		st["dead"] = true
		Events.player_status_message.emit("Ezra Vane is dead.", &"warning")
		return
	st["out_until_day"] = Game.session.clock.day() + 1


## The dawn after he bled out: at the player's spawn point (bed or drop site), wounded, staying.
func _come_back(p: Player) -> void:
	var st: Dictionary = state()
	st["out_until_day"] = -1
	var ps: PlayerState = p.state
	var at: Vector3 = ps.spawn_point if ps.has_spawn_point else (world.call(&"drop_site") as Vector3 if world.has_method(&"drop_site") else p.global_position)
	at.y = maxf(_ground(at), at.y)
	st["position"] = [at.x + 1.5, at.y, at.z + 1.0]
	st["health"] = cdef.return_health
	st["order"] = "stay"
	st["spot"] = []
	st["downed_t"] = -1.0
	_restore(p)
	if _has_body():
		body.ally.bark("back")


# --- Commands (ADR-0003) ---------------------------------------------------------------------------

func _ps(args: Dictionary) -> PlayerState:
	return Game.session.players.get(StringName(str(args.get("player", Game.session.local_player_id)))) if Game.session != null else null


func _near(ps: PlayerState, r: float) -> bool:
	var p: Player = _player()
	return _has_body() and p != null and p.state == ps and p.global_position.distance_to(body.global_position) <= r


## {player, item?}: gives him one of the recruit items (the one named, else the first carried) at
## his camp. He gets up and follows.
func _cmd_companion_recruit(args: Dictionary) -> Dictionary:
	var ps: PlayerState = _ps(args)
	if ps == null or recruited() or is_out() or not _has_body():
		return {"ok": false, "error": "nobody to recruit"}
	if not _near(ps, 4.0):
		return {"ok": false, "error": "too far"}
	var item: StringName = StringName(str(args.get("item", "")))
	if item == &"":
		for it: String in cdef.recruit_items:
			if ps.inventory.count_of(StringName(it)) > 0:
				item = StringName(it)
				break
	if item == &"" or not cdef.recruit_items.has(String(item)) or not ps.inventory.remove(item, 1):
		return {"ok": false, "error": "needs one of %s" % ", ".join(cdef.recruit_items)}
	Events.inventory_changed.emit(ps.id)
	state()["recruited"] = true
	var m: CompanionMind = body.ally
	m.recruited = true
	m.set_order("follow")
	m.get_up(cdef.recruit_health)
	m.bark("recruited")
	Events.companion_recruited.emit(cdef.id)
	return {"ok": true, "item": item}


## {player, order: follow|stay|guard, spot?: [x, y, z] (default: where he stands)}.
func _cmd_companion_order(args: Dictionary) -> Dictionary:
	var ps: PlayerState = _ps(args)
	var kind: String = str(args.get("order", ""))
	if ps == null or not recruited() or not _has_body():
		return {"ok": false, "error": "no companion"}
	if not CompanionMind.ORDERS.has(kind):
		return {"ok": false, "error": "unknown order '%s'" % kind}
	var m: CompanionMind = body.ally
	if m.downed or m.rising_t > 0.0:
		return {"ok": false, "error": "he is down"}
	var spot: Vector3 = _vec(args.get("spot"))
	m.set_order(kind, spot)
	m.bark(kind)
	return {"ok": true, "order": kind}


## {player}: a bandage or first aid kit (consumed) gets him up off the ground.
func _cmd_companion_revive(args: Dictionary) -> Dictionary:
	var ps: PlayerState = _ps(args)
	if ps == null or not _has_body() or not body.ally.downed:
		return {"ok": false, "error": "not down"}
	if not _near(ps, 3.5):
		return {"ok": false, "error": "too far"}
	var item: StringName = body.ally.revive_item(ps)
	if item == &"" or not ps.inventory.remove(item, 1):
		return {"ok": false, "error": "needs a bandage or a first aid kit"}
	Events.inventory_changed.emit(ps.id)
	body.ally.get_up(cdef.revive_health)
	body.ally.bark("revived")
	return {"ok": true, "item": item}


## The quick order: follow when he holds a spot, stay when he follows.
func quick_order() -> Dictionary:
	if not _has_body() or not recruited():
		return {"ok": false, "error": "no companion"}
	return Game.execute(&"companion.order", {"order": "stay" if body.ally.order == "follow" else "follow"})


func _unhandled_input(event: InputEvent) -> void:
	if cdef == null or not event.is_action_pressed(&"companion_order") or not recruited():
		return
	var p: Player = _player()
	if p == null or not p.input_enabled:
		return
	var r: Dictionary = quick_order()
	if bool(r.get("ok", false)):
		Audio.play_2d(&"ui/page_turn", -14.0)
		get_viewport().set_input_as_handled()


# --- The order card ----------------------------------------------------------------------------------

func open_card() -> void:
	var ui: Node = world.get(&"ui") if world != null else null
	if ui == null:
		return
	if screen == null or not is_instance_valid(screen):
		screen = CompanionScreen.new()
		screen.name = "CompanionScreen"
		screen.set(&"director", self)
		ui.add_child(screen)
	screen.call(&"open")


# --- Save --------------------------------------------------------------------------------------------

func _on_game_saving(_slot: String) -> void:
	if cdef == null or Game.session == null or not recruited() or is_out() or not _has_body():
		return
	var st: Dictionary = state()
	var m: CompanionMind = body.ally
	st["position"] = _arr(body.global_position)
	st["yaw"] = body.rotation.y
	st["health"] = body.health / maxf(1.0, body.max_health)
	st["downed_t"] = m.downed_t if m.downed else -1.0
	st["order"] = m.order
	st["spot"] = _arr(m.spot) if m.spot != Vector3.INF else []
	if not st.has("out_until_day"):
		st["out_until_day"] = -1


static func _arr(v: Vector3) -> Array:
	return [v.x, v.y, v.z]


static func _vec(v: Variant) -> Vector3:
	if v is Vector3:
		return v
	if v is Array and (v as Array).size() >= 3:
		return Vector3(float(v[0]), float(v[1]), float(v[2]))
	return Vector3.INF
