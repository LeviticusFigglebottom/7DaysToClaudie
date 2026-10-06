class_name AshenDirector
extends Node
## The Ashen in the world (ADR-0048), a GameWorld module: the one owner of the faction's state.
## It peoples their living camps when the player comes near (the dead stay dead), keeps one
## world-wide hostility score and the escalation level it gives (unaware, watchers, raids, war
## parties), sends a scout on the days the seed picks once they are watching, and a raid at dusk
## on the days it picks once they raid: never on a Hum day, never while the Hum is out (they run
## from it), never in the first days. Every Ashen fighter is an Enemy spawned through the AI
## director with an AshenMind; this node tells them their job and band and takes them out of the
## world when they get away. Saved state is WorldState.ashen (no version bump); a scout or raid
## under way when the game is saved is simply over after a reload.

const TICK: float = 0.5

var world: Node
var fd: FactionDef
## building id -> [Enemy] living residents spawned now
var _residents: Dictionary = {}
## Scouts out now.
var _scouts: Array[Enemy] = []
## The raid under way: {id, members: [Enemy], t, target: Vector3, size}; {} when none.
var raid: Dictionary = {}
## Today's rolls (re-rolled deterministically at load and each dawn): {day, scout: {}, raid: {}}.
var _today: Dictionary = {}
var _tick: float = 0.0
## () -> Array: the placed buildings (PoiManager.all_buildings()); tests stand in their own.
var buildings_source: Callable = Callable()


func setup_world(w: Node) -> void:
	world = w
	fd = AshenBrain.def()
	if fd == null:
		return
	var st: Dictionary = state()
	if not st.has("hostility"):
		st["hostility"] = float(fd.hostility.get("start", 0.0))
		st["level"] = 0
		st["camps"] = {}
	Events.enemy_killed.connect(_on_enemy_killed)
	Events.day_started.connect(_on_day_started)
	Events.horde_night_started.connect(_on_hum)


func _exit_tree() -> void:
	# Bodies belong to the AI director; nothing of ours outlives the world.
	_residents.clear()
	_scouts.clear()
	raid = {}


## The saved state (WorldState.ashen).
static func state() -> Dictionary:
	return Game.session.world.ashen


func enabled() -> bool:
	return fd != null and GameRules.current().flag("ashen")


func aggression() -> String:
	return GameRules.current().choice("ashen_aggression")


func hostility() -> float:
	return float(state().get("hostility", 0.0))


func level() -> int:
	return int(state().get("level", 0))


## Raises (or lowers) hostility for an event and updates the level.
func provoke(event: String, times: float = 1.0) -> void:
	if fd == null:
		return
	state()["hostility"] = AshenBrain.gain(fd, hostility(), event, times, aggression())
	_update_level()


func _update_level() -> void:
	var lv: int = AshenBrain.level_for(fd, hostility(), _gamestage())
	if lv != level():
		state()["level"] = lv
		Log.info("ashen", "level %d (%s), hostility %.0f" % [lv, (fd.levels[lv] as Dictionary).get("name", ""), hostility()])
		Events.ashen_level_changed.emit(lv)


func _gamestage() -> int:
	return Game.session.gamestage(Game.session.local_player())


func _on_day_started(_day: int) -> void:
	if fd == null:
		return
	state()["hostility"] = AshenBrain.dawn(fd, hostility())
	_update_level()
	_today = {}


## Every placed building that is one of the faction's camps: [{id, def, pos, camp (its entry)}].
func camps() -> Array:
	var out: Array = []
	var list: Array = buildings_source.call() if buildings_source.is_valid() else _all_buildings()
	for v: Variant in list:
		var b: Dictionary = v
		var c: Dictionary = fd.camp_for(StringName(str(b.get("def", ""))))
		if not c.is_empty():
			out.append({"id": str(b.get("id", "")), "def": str(b.get("def", "")), "pos": b.get("pos", Vector3.ZERO), "camp": c})
	return out


func _all_buildings() -> Array:
	var pois: Node = world.get(&"pois") if world != null else null
	return pois.call(&"all_buildings") if pois != null and pois.has_method(&"all_buildings") else []


func _ai() -> Node:
	return world.get(&"ai") if world != null else null


func _player() -> Player:
	return world.get(&"player") as Player if world != null else null


# --- The loop --------------------------------------------------------------------------------------

func _process(delta: float) -> void:
	if Game.session == null or not enabled():
		return
	_tick += delta
	if _tick < TICK:
		return
	var dt: float = _tick
	_tick = 0.0
	var p: Player = _player()
	if p == null or _ai() == null:
		return
	_update_level()
	_follow_camps(p)
	_follow_scouts(p)
	_follow_raid(p, dt)
	_schedule(p)


## Peoples a camp when the player comes within its wake range, empties it past its sleep range,
## and counts a visit to its territory as trespass (once a day per camp).
func _follow_camps(p: Player) -> void:
	var day: int = Game.session.clock.day()
	for c: Dictionary in camps():
		var cid: String = c["id"]
		var cfg: Dictionary = c["camp"]
		var pos: Vector3 = c["pos"]
		var d: float = Vector2(p.global_position.x - pos.x, p.global_position.z - pos.z).length()
		var cs: Dictionary = camp_state(cid)
		if d <= float(cfg.get("territory", 160.0)) and int(cs.get("trespass_day", -1)) != day:
			cs["trespass_day"] = day
			provoke("trespass")
		if d <= float(cfg.get("wake_range", 150.0)) and not _residents.has(cid):
			_residents[cid] = spawn_residents(cid, cfg, pos)
		elif d > float(cfg.get("sleep_range", 180.0)) and _residents.has(cid):
			for e: Variant in _residents[cid]:
				if e is Enemy and is_instance_valid(e) and (e as Enemy).is_alive():
					_ai().call(&"despawn", e)
			_residents.erase(cid)


## A camp's saved state: {dead: [resident indices], trespass_day, wiped}.
func camp_state(cid: String) -> Dictionary:
	var all: Dictionary = state().get("camps", {})
	state()["camps"] = all
	if not all.has(cid):
		all[cid] = {"dead": []}
	return all[cid]


## Who lives at a camp: [enemy ids], fixed by the world seed and the building (index i is always
## the same person).
func residents_of(cid: String, cfg: Dictionary) -> Array[String]:
	var rng := RandomNumberGenerator.new()
	rng.seed = Ids.hash64("ashen:camp:%d:%s" % [Game.session.world_seed, cid])
	var out: Array[String] = []
	var keys: Array = (cfg.get("residents", {}) as Dictionary).keys()
	keys.sort()
	for k: Variant in keys:
		var r: Array = cfg["residents"][k]
		for i: int in rng.randi_range(int(r[0]), int(r[r.size() - 1])):
			out.append(str(k))
	return out


func spawn_residents(cid: String, cfg: Dictionary, pos: Vector3) -> Array:
	var out: Array = []
	var dead: Array = camp_state(cid).get("dead", [])
	var who: Array[String] = residents_of(cid, cfg)
	var rng := RandomNumberGenerator.new()
	rng.seed = Ids.hash64("ashen:camp_pos:%d:%s" % [Game.session.world_seed, cid])
	for i: int in who.size():
		var ang: float = rng.randf() * TAU
		var r: float = rng.randf_range(4.0, 13.0)
		if dead.has(i):
			continue
		var at := Vector3(pos.x + cos(ang) * r, 0.0, pos.z + sin(ang) * r)
		at.y = _height(at) + 0.4
		var e: Enemy = _ai().call(&"spawn", StringName(who[i]), at, {"id": "ash:%s:%d" % [cid, i], "tier": "normal",
			"authored": true, "job": "camp", "camp": cid, "camp_pos": pos, "territory": float(cfg.get("territory", 160.0))})
		if e != null:
			e.set_meta(&"ashen_resident", i)
			out.append(e)
	for e2: Variant in out:
		(e2 as Enemy).tribe.band = out
	return out


func _height(at: Vector3) -> float:
	return float(world.call(&"height_at", at.x, at.z)) if world != null and world.has_method(&"height_at") else at.y


# --- Scouts and raids --------------------------------------------------------------------------------

## Today's rolls, made once a day (and again after a load: they are pure functions of the seed).
func today() -> Dictionary:
	var day: int = Game.session.clock.day()
	if int(_today.get("day", -1)) != day:
		var clock: WorldClock = Game.session.clock
		var hum_day: bool = clock.hordes_enabled() and clock.is_horde_day(day)
		_today = {"day": day,
			"scout": AshenBrain.scout_roll(fd, Game.session.world_seed, day, level(), aggression()),
			"raid": AshenBrain.raid_roll(fd, Game.session.world_seed, day, level(), _gamestage(), hum_day, aggression())}
	return _today


func _schedule(p: Player) -> void:
	var clock: WorldClock = Game.session.clock
	if clock.is_horde_active() or not p.state.stats.alive or _in_safe_zone(p.global_position):
		return
	var day: int = clock.day()
	var t: Dictionary = today()
	var sc: Dictionary = t["scout"]
	if not sc.is_empty() and level() >= 1 and int(state().get("scout_day", -1)) != day and clock.hour_f() >= float(sc["hour"]):
		state()["scout_day"] = day
		send_scout(p)
	var rd: Dictionary = t["raid"]
	if not rd.is_empty() and level() >= 2 and raid.is_empty() and int(state().get("raid_day", -1)) != day \
			and clock.hour_f() >= float(rd["hour"]) and not _defence_running():
		state()["raid_day"] = day
		start_raid(p, rd["members"])


## A scout comes out 70-95 m from the player (from their base when they have one) and watches.
func send_scout(p: Player) -> Enemy:
	var target: Vector3 = base_of(p)
	var ring: Array = fd.scouts.get("ring", [70, 95])
	var at: Vector3 = _ring_point(target, float(ring[0]), float(ring[1]), "scout:%d" % Game.session.clock.day())
	if at == Vector3.INF:
		return null
	var e: Enemy = _ai().call(&"spawn", StringName(str(fd.scouts.get("enemy", "ashen_scout"))), at,
		{"tier": "normal", "authored": true, "job": "scout", "goal": target})
	if e == null:
		return null
	e.tribe.band = [e]
	e._set_state(Enemy.State.OBSERVE)
	_scouts.append(e)
	Log.info("ashen", "a scout at (%.0f, %.0f) is watching" % [at.x, at.z])
	return e


func _follow_scouts(p: Player) -> void:
	for e: Enemy in _scouts.duplicate():
		if not is_instance_valid(e) or not e.is_alive():
			_scouts.erase(e)
			continue
		if e.tribe.gone:
			_scouts.erase(e)
			if e.tribe.reported:
				provoke("scout_report")
				state()["base_marked"] = true
			Events.ashen_scout_done.emit(e.entity_id, e.tribe.reported)
			Log.info("ashen", "a scout got away (%s)" % ("reported" if e.tribe.reported else "seen off"))
			_ai().call(&"despawn", e)


## A raid band: `members` (enemy ids) come in from 90-120 m out and make for the base (or the
## player when there is none).
func start_raid(p: Player, members: Array) -> Dictionary:
	var target: Vector3 = base_of(p)
	var ring: Array = fd.raids.get("ring", [90, 120])
	var at: Vector3 = _ring_point(target, float(ring[0]), float(ring[1]), "raid:%d" % Game.session.clock.day())
	if at == Vector3.INF:
		return {}
	var rid: String = "raid:%d" % Game.session.clock.day()
	var band: Array = []
	var rng := RandomNumberGenerator.new()
	rng.seed = Ids.hash64("ashen:%d:%s" % [Game.session.world_seed, rid])
	for i: int in members.size():
		var off := Vector3(rng.randf_range(-5.0, 5.0), 0.0, rng.randf_range(-5.0, 5.0))
		var pos: Vector3 = at + off
		pos.y = _height(pos) + 0.4
		var e: Enemy = _ai().call(&"spawn", StringName(str(members[i])), pos, {"tier": "normal", "authored": true,
			"job": "raid", "goal": target, "target": target})
		if e != null:
			e.home = target
			band.append(e)
	if band.is_empty():
		return {}
	for e2: Variant in band:
		(e2 as Enemy).tribe.band = band
	raid = {"id": rid, "members": band, "t": 0.0, "target": target, "size": band.size()}
	Events.ashen_raid_started.emit(rid, target, band.size())
	Events.player_status_message.emit("Drums in the trees. The Ashen are coming.", &"warning")
	if Audio != null:
		Audio.play_3d(&"sfx/ashen_drum", at + Vector3.UP, {"volume_db": 4.0, "max_distance": 260.0, "occlusion": false})
	Log.info("ashen", "a raid of %d from (%.0f, %.0f) on (%.0f, %.0f)" % [band.size(), at.x, at.z, target.x, target.z])
	return raid


## The raid ends when nobody of the band is left in the fight (repelled: dead or run off), or it
## gives up after give_up seconds and they melt back into the trees.
func _follow_raid(p: Player, dt: float) -> void:
	if raid.is_empty():
		return
	raid["t"] = float(raid["t"]) + dt
	var fighting: int = 0
	for e: Variant in raid["members"]:
		if not (e is Enemy) or not is_instance_valid(e):
			continue
		var en: Enemy = e
		if en.is_alive() and en.tribe.gone:
			_ai().call(&"despawn", en)
			continue
		if en.is_alive() and en.state != Enemy.State.FLEE:
			fighting += 1
	if fighting == 0:
		_end_raid(true)
	elif float(raid["t"]) > float(fd.raids.get("give_up", 420.0)):
		for e3: Variant in raid["members"]:
			if e3 is Enemy and is_instance_valid(e3) and (e3 as Enemy).is_alive():
				(e3 as Enemy).tribe.flee(p)
		_end_raid(false)


func _end_raid(repelled: bool) -> void:
	var rid: String = str(raid.get("id", ""))
	raid = {}
	if repelled:
		provoke("raid_repelled")
		var pl: PlayerState = Game.session.local_player()
		if pl != null:
			pl.progression.award("repel_raid")
		Events.player_status_message.emit("The Ashen are gone back into the trees.", &"info")
	Events.ashen_raid_ended.emit(rid, repelled)
	Log.info("ashen", "raid %s over (%s)" % [rid, "repelled" if repelled else "gave up"])


## The player's base: the centre of what they built within base_range of them, else where they stand.
func base_of(p: Player) -> Vector3:
	var pos: Vector3 = p.global_position
	var building: Node = world.get(&"building") if world != null else null
	if building == null or not building.has_method(&"pieces_in_radius"):
		return pos
	var near: Array = building.call(&"pieces_in_radius", pos, float(fd.raids.get("base_range", 60.0)))
	if near.is_empty():
		return pos
	var c := Vector3.ZERO
	for piece: Variant in near:
		c += (piece as Node3D).global_position
	return c / float(near.size())


## A spawn point `lo`-`hi` m from `center` the AI director accepts (out of sight, dry, outside
## buildings and trader safe zones), on a bearing the key picks; Vector3.INF if none.
func _ring_point(center: Vector3, lo: float, hi: float, key: String) -> Vector3:
	var rng := RandomNumberGenerator.new()
	rng.seed = Ids.hash64("ashen:ring:%d:%s" % [Game.session.world_seed, key])
	var ai: Node = _ai()
	for attempt: int in 16:
		var ang: float = rng.randf() * TAU
		var r: float = rng.randf_range(lo, hi)
		var at := Vector3(center.x + cos(ang) * r, 0.0, center.z + sin(ang) * r)
		at.y = _height(at) + 0.4
		# (an AI director with no world, as in tests, has nothing to check against)
		if ai == null or ai.get(&"world") == null or bool(ai.call(&"spawn_point_ok", at)):
			return at
	return Vector3.INF


func _in_safe_zone(pos: Vector3) -> bool:
	var traders: Node = world.get(&"traders") if world != null else null
	return traders != null and traders.has_method(&"is_safe") and bool(traders.call(&"is_safe", pos))


## A Waystation defence under way (ADR-0039): a raid waits for it (TD-142's overlap rule).
func _defence_running() -> bool:
	var traders: Node = world.get(&"traders") if world != null else null
	return traders != null and not (traders.get(&"_runs") as Dictionary).is_empty()


# --- Events ----------------------------------------------------------------------------------------

func _on_enemy_killed(entity_id: StringName, enemy_id: StringName, _pos: Vector3, killer: Dictionary) -> void:
	var ed: EnemyDef = Content.enemy(enemy_id)
	if ed == null or ed.faction != "ashen" or fd == null:
		return
	var by_player: bool = Game.session.players.has(StringName(str(killer.get("source", ""))))
	var dead: Enemy = _ai().get(&"enemies").get(entity_id) as Enemy if _ai() != null else null
	if by_player:
		provoke("kill")
		if dead != null and dead.tribe != null and dead.tribe.job == AshenMind.Job.SCOUT:
			provoke("scout_killed")
	if dead == null or dead.tribe == null:
		return
	for m: Variant in dead.tribe.band:
		if m is Enemy and is_instance_valid(m) and m != dead:
			(m as Enemy).tribe.on_mate_down(_player())
	if dead.tribe.camp_id != "" and dead.has_meta(&"ashen_resident"):
		var cs: Dictionary = camp_state(dead.tribe.camp_id)
		var list: Array = cs.get("dead", [])
		list.append(int(dead.get_meta(&"ashen_resident")))
		cs["dead"] = list
		for c: Dictionary in camps():
			if c["id"] == dead.tribe.camp_id and list.size() >= residents_of(c["id"], c["camp"]).size() and not bool(cs.get("wiped", false)):
				cs["wiped"] = true
				provoke("camp_wiped")
				Events.player_status_message.emit("The camp is silent. The Ashen will remember this.", &"warning")


## A heat trigger (AIDirector) inside a camp's territory: they heard the outsider.
func on_heat(t: Dictionary) -> void:
	if fd == null or not enabled():
		return
	var pos: Vector3 = t.get("pos", Vector3.INF)
	for c: Dictionary in camps():
		var cp: Vector3 = c["pos"]
		if Vector2(pos.x - cp.x, pos.z - cp.z).length() <= float((c["camp"] as Dictionary).get("territory", 160.0)):
			provoke("heat")
			return


## The Hum is coming: every Ashen out of their camps runs for home.
func _on_hum(_day: int) -> void:
	var p: Player = _player()
	for e: Enemy in _scouts:
		if is_instance_valid(e) and e.is_alive():
			e.tribe.flee(p)
	if not raid.is_empty():
		for e2: Variant in raid["members"]:
			if e2 is Enemy and is_instance_valid(e2) and (e2 as Enemy).is_alive():
				(e2 as Enemy).tribe.flee(p)
		_end_raid(false)


## Debug and QA: a raid now with the level's band (or `n` raiders).
func debug_raid(n: int = 0) -> Dictionary:
	var p: Player = _player()
	if p == null or fd == null:
		return {}
	var members: Array = []
	for i: int in maxi(1, n if n > 0 else 4):
		members.append("ashen_scout" if i % 4 == 3 else "ashen_raider")
	return start_raid(p, members)
