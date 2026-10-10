class_name AshenDirector
extends Node
## The Ashen in the world (ADR-0048), a GameWorld module: the one owner of the faction's state.
## It peoples their living camps when the player comes near (the dead stay dead), keeps one
## world-wide hostility score and the escalation level it gives (unaware, watchers, raids, war
## parties), sends a scout on the days the seed picks once they are watching, and a raid at dusk
## on the days it picks once they raid: never on a Hum day, never while the Hum is out (they run
## from it), never in the first days. Every Ashen fighter is an Enemy spawned through the AI
## director with an AshenMind; this node tells them their job and band and takes them out of the
## world when they get away.
##
## Phase 2 (TD-188, TD-189, TD-211): a raid comes out of the dark side of the base (away from its
## lit fires) and makes for its weakest piece along a FlowField that prices the player's structures
## by their hit points (the Hum's weak-point rule) and keeps off their fires. It hits the base even
## when the player is away: it breaks in, tramples the garden beds it crosses, takes ripe crops and
## leaves. Saved state is WorldState.ashen (no version bump); a raid or scout under way is saved in
## it (`live`) and comes back on load.
##
## Per-camp standing (TD-190): beside the world-wide hostility (still the escalation driver) each
## camp keeps its own `anger` (trespass in it, its people killed, heat in its territory, a kin camp
## wiped out; fading each dawn). A scout or raid comes from the angriest living camp, out of the
## ring on the bearing toward it; a wiped camp sends nothing.

const TICK: float = 0.5
## Seconds between looks at where the player's base is (remembered for raids while they're away).
const BASE_EVERY: float = 10.0
## Flow-field cells a raider's next waypoint lies ahead of it.
const WAYPOINT_STEPS: int = 6

var world: Node
var fd: FactionDef
## building id -> [Enemy] living residents spawned now
var _residents: Dictionary = {}
## Scouts out now.
var _scouts: Array[Enemy] = []
## The raid under way; {} when none: {id, members: [Enemy], jobs: {entity id: "goal"|"garden"},
## t (s), target (the base's centre, or the player), base (bool: target is a base), goal (the weak
## point they make for), goal_piece (its piece id, "" for none), from (where they came out), size,
## broken (goal pieces broken), trampled: {bed id: true}, looted (plots taken), arrived (bool)}.
var raid: Dictionary = {}
## The raid's way in (built at its start and whenever its goal changes); null when none.
var flow: FlowField = null
## Ashen whose raid is over, on their way back into the trees: despawned once they get away (the
## AI director leaves every tribe body to us).
var _leaving: Array[Enemy] = []
## The bands a save had out (WorldState.ashen.live), brought back on the first tick: setup_world
## runs before the player is spawned.
var _restore: Dictionary = {}
## Today's rolls (re-rolled deterministically at load and each dawn): {day, scout: {}, raid: {}}.
var _today: Dictionary = {}
var _tick: float = 0.0
var _base_t: float = 0.0
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
	Events.game_saving.connect(_on_game_saving)
	var live: Variant = st.get("live", {})
	_restore = live if live is Dictionary else {}


func _exit_tree() -> void:
	# Bodies belong to the AI director; nothing of ours outlives the world.
	_residents.clear()
	_scouts.clear()
	_leaving.clear()
	raid = {}
	flow = null


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
	for cs: Variant in (state().get("camps", {}) as Dictionary).values():
		if cs is Dictionary and (cs as Dictionary).has("anger"):
			cs["anger"] = AshenBrain.anger_at_dawn(fd, float(cs["anger"]))
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
	if not _restore.is_empty():
		restore_live(_restore)
		_restore = {}
		state().erase("live")
	_update_level()
	_base_t -= dt
	if _base_t <= 0.0:
		_base_t = BASE_EVERY
		_remember_base(p)
	_follow_camps(p)
	_follow_scouts(p)
	_follow_raid(p, dt)
	_follow_leaving()
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
			anger_camp(cid, "trespass")
		if d <= float(cfg.get("wake_range", 150.0)) and not _residents.has(cid):
			_residents[cid] = spawn_residents(cid, cfg, pos)
		elif d > float(cfg.get("sleep_range", 180.0)) and _residents.has(cid):
			for e: Variant in _residents[cid]:
				if e is Enemy and is_instance_valid(e) and (e as Enemy).is_alive():
					_ai().call(&"despawn", e)
			_residents.erase(cid)


## A camp's saved state: {dead: [resident indices], trespass_day, wiped, anger} (older saves have
## no anger: 0).
func camp_state(cid: String) -> Dictionary:
	var all: Dictionary = state().get("camps", {})
	state()["camps"] = all
	if not all.has(cid):
		all[cid] = {"dead": []}
	return all[cid]


## A camp's own anger at the outsider (TD-190).
func camp_anger(cid: String) -> float:
	return float(((state().get("camps", {}) as Dictionary).get(cid, {}) as Dictionary).get("anger", 0.0))


## Raises a living camp's anger for an event tied to it (FactionDef.STANDING_EVENTS); a wiped camp
## has nobody left to be angry.
func anger_camp(cid: String, event: String, times: float = 1.0) -> void:
	if fd == null or cid == "":
		return
	var cs: Dictionary = camp_state(cid)
	if bool(cs.get("wiped", false)):
		return
	cs["anger"] = AshenBrain.anger(fd, float(cs.get("anger", 0.0)), event, times, aggression())


## The camp a scout or raid comes from: the angriest living placed camp ({id, pos, ...} as
## camps() gives it), {} for none (then they come from anywhere, or the dark side).
func source_camp() -> Dictionary:
	var list: Array = camps()
	var ids: Array = []
	var dists: Dictionary = _camp_dists(list)
	for c: Dictionary in list:
		ids.append(c["id"])
	var best: String = AshenBrain.angriest(fd, state().get("camps", {}), ids, dists)
	for c2: Dictionary in list:
		if c2["id"] == best:
			return c2
	return {}


## The leading camp's effective anger (its anger x reach from the player), 0 for none: it feeds
## the day's scout and raid rolls (TD-190).
func lead_anger() -> float:
	var c: Dictionary = source_camp()
	if c.is_empty():
		return 0.0
	return camp_anger(str(c["id"])) * AshenBrain.reach(fd, float(_camp_dists([c]).get(str(c["id"]), -1.0)))


## id -> flat distance (m) from the player to each camp in `list` (empty without a player).
func _camp_dists(list: Array) -> Dictionary:
	var out: Dictionary = {}
	var p: Node3D = world.get(&"player") as Node3D if world != null else null
	if p == null:
		return out
	for c: Dictionary in list:
		if c.has("pos"):
			out[str(c["id"])] = _flat(p.global_position, c["pos"] as Vector3)
	return out


## The bearing (radians, as _ring_point measures it) from `center` toward a camp.
static func camp_bearing(center: Vector3, camp_pos: Vector3) -> float:
	return atan2(camp_pos.z - center.z, camp_pos.x - center.x)


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

## Today's rolls, made once a day (and again after a load: pure functions of the seed and the leading
## camp's anger).
func today() -> Dictionary:
	var day: int = Game.session.clock.day()
	if int(_today.get("day", -1)) != day:
		var clock: WorldClock = Game.session.clock
		var hum_day: bool = clock.hordes_enabled() and clock.is_horde_day(day)
		# The leading camp's anger as it stands at the first roll of the day (a load re-rolls with
		# the anger saved, so a camp provoked since then can change that day's roll).
		var anger: float = lead_anger()
		_today = {"day": day,
			"scout": AshenBrain.scout_roll(fd, Game.session.world_seed, day, level(), aggression(), anger),
			"raid": AshenBrain.raid_roll(fd, Game.session.world_seed, day, level(), _gamestage(), hum_day, aggression(), anger)}
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
	var day: int = Game.session.clock.day()
	# From the angriest living camp when one is set on the outsider (TD-190).
	var src: Dictionary = source_camp()
	var bearing: float = camp_bearing(target, src["pos"]) if not src.is_empty() else NAN
	var at: Vector3 = _ring_point(target, float(ring[0]), float(ring[1]), "scout:%d" % day, bearing, _camp_spread())
	if at == Vector3.INF:
		return null
	# A fixed id (not the AI director's running count) so a saved scout comes back as itself.
	var seq: int = int(state().get("scout_seq", 0)) + 1
	state()["scout_seq"] = seq
	var e: Enemy = _ai().call(&"spawn", StringName(str(fd.scouts.get("enemy", "ashen_scout"))), at,
		{"id": "ash:scout:%d:%d" % [day, seq], "tier": "normal", "authored": true, "job": "scout", "goal": target,
			"camp": str(src.get("id", ""))})
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


## Where a raid goes: {pos, base}. The base round the player when they are home, else the base
## they were last seen at (remembered every BASE_EVERY s) while it still stands, else the player.
func raid_target(p: Player) -> Dictionary:
	var here: Vector3 = _base_near(p.global_position)
	if here != Vector3.INF:
		return {"pos": here, "base": true}
	var saved: Vector3 = _vec(state().get("base"))
	if saved != Vector3.INF:
		var there: Vector3 = _base_near(saved)
		if there != Vector3.INF:
			return {"pos": there, "base": true}
	return {"pos": p.global_position, "base": false}


func _remember_base(p: Player) -> void:
	var b: Vector3 = _base_near(p.global_position)
	if b != Vector3.INF:
		state()["base"] = _arr(b)


## A raid band: `members` (enemy ids) come in from 90-120 m out, from the angriest living camp's
## side when one is set on the outsider (TD-190), else on the side of the base its fires light
## least, and make for its weakest piece (or for the player when there is no base).
func start_raid(p: Player, members: Array) -> Dictionary:
	var tg: Dictionary = raid_target(p)
	var target: Vector3 = tg["pos"]
	var is_base: bool = bool(tg["base"])
	var ring: Array = fd.raids.get("ring", [90, 120])
	var day: int = Game.session.clock.day()
	var src: Dictionary = source_camp()
	var bearing: float = dark_bearing(target, _lit_fires(target)) if is_base else NAN
	var spread: float = deg_to_rad(float(fd.raids.get("dark_side", 70.0)))
	if not src.is_empty():
		bearing = camp_bearing(target, src["pos"])
		spread = _camp_spread()
	var at: Vector3 = _ring_point(target, float(ring[0]), float(ring[1]), "raid:%d" % day, bearing, spread)
	if at == Vector3.INF:
		return {}
	var seq: int = int(state().get("raid_seq", 0)) + 1
	state()["raid_seq"] = seq
	var rid: String = "raid:%d:%d" % [day, seq]
	var band: Array = []
	var rng := RandomNumberGenerator.new()
	rng.seed = Ids.hash64("ashen:%d:%s" % [Game.session.world_seed, rid])
	for i: int in members.size():
		var off := Vector3(rng.randf_range(-5.0, 5.0), 0.0, rng.randf_range(-5.0, 5.0))
		var pos: Vector3 = at + off
		pos.y = _height(pos) + 0.4
		var e: Enemy = _ai().call(&"spawn", StringName(str(members[i])), pos, {"id": "ash:%s:%d" % [rid, i], "tier": "normal",
			"authored": true, "job": "raid", "goal": target, "target": target, "camp": str(src.get("id", ""))})
		if e != null:
			e.home = target
			band.append(e)
	if band.is_empty():
		return {}
	for e2: Variant in band:
		(e2 as Enemy).tribe.band = band
	raid = {"id": rid, "members": band, "jobs": {}, "t": 0.0, "target": target, "base": is_base, "goal": target,
		"goal_piece": "", "from": at, "size": band.size(), "broken": 0, "trampled": {}, "looted": 0, "arrived": false,
		"camp": str(src.get("id", ""))}
	_assign_jobs()
	_pick_goal()
	Events.ashen_raid_started.emit(rid, target, band.size())
	var away: bool = is_base and _flat(p.global_position, target) > float(fd.raids.get("base_range", 60.0))
	Events.player_status_message.emit("Far off, drums. The Ashen are going for your base." if away
		else "Drums in the trees. The Ashen are coming.", &"warning")
	if Audio != null:
		Audio.play_3d(&"sfx/ashen_drum", at + Vector3.UP, {"volume_db": 4.0, "max_distance": 260.0, "occlusion": false})
	Log.info("ashen", "a raid of %d from (%.0f, %.0f) on (%.0f, %.0f)%s" % [band.size(), at.x, at.z, target.x, target.z,
		" (nobody home)" if away else ""])
	return raid


## The last `gardens.looters` of the band go for the ripe crops; the rest for the weak point.
func _assign_jobs() -> void:
	var g: Dictionary = fd.raids.get("gardens", {})
	var looters: int = int(g.get("looters", 1)) if bool(g.get("loot_crops", false)) and bool(raid["base"]) else 0
	var band: Array = raid["members"]
	var jobs: Dictionary = raid["jobs"]
	for i: int in band.size():
		jobs[String((band[i] as Enemy).entity_id)] = "garden" if i >= band.size() - looters else "goal"


## The raid ends when nobody of the band is left in the fight (repelled: dead or run off), when it
## has sacked a base nobody is home at (broke in and took the crops), or after give_up seconds;
## then they melt back into the trees.
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
			_raid_gardens(en)
			_steer(en)
	if fighting == 0:
		_end_raid(true)
	elif float(raid["t"]) > float(fd.raids.get("give_up", 420.0)):
		_leave(p)
		_end_raid(false)
	elif _sacked(p):
		_leave(p)
		Events.player_status_message.emit("The Ashen have been at your base while you were away.", &"warning")
		_end_raid(false, "sacked the base")


## Tells a raider at a loose end (not fighting, breaking or running) where to go next: a ripe bed
## for a looter, else the goal piece (struck once in reach), along the flow field.
func _steer(e: Enemy) -> void:
	var target: Vector3 = raid["target"]
	if e._flat_dist(target) < 12.0:
		raid["arrived"] = true
	if e.state not in [Enemy.State.IDLE, Enemy.State.WANDER, Enemy.State.INVESTIGATE]:
		return
	var id: String = String(e.entity_id)
	var jobs: Dictionary = raid["jobs"]
	if str(jobs.get(id, "goal")) == "garden":
		var bed: StructurePiece = _ripe_bed(e.global_position)
		if bed != null:
			e.notice(bed.global_position)
			return
		jobs[id] = "goal"
	var piece: StructurePiece = _goal_piece()
	if piece != null and e._flat_dist(piece.global_position) <= _reach(piece):
		e.break_target = piece
		e._resume_state = Enemy.State.INVESTIGATE
		e._set_state(Enemy.State.BREAK)
		return
	e.notice(waypoint(e.global_position))


## Where a raider at `from` walks next: WAYPOINT_STEPS cells down the flow field toward the goal
## (straight at it with no field, or once there).
func waypoint(from: Vector3) -> Vector3:
	var goal: Vector3 = raid.get("goal", from)
	if flow == null or not flow.ready:
		return goal
	var at: Vector3 = from
	for i: int in WAYPOINT_STEPS:
		var d: Vector3 = flow.direction_at(at)
		if d == Vector3.ZERO:
			return goal if i == 0 else at
		at += d * flow.cell
	at.y = _height(at)
	return at


## The piece the raid is breaking in at, while it stands; once it's gone (broken, or taken down)
## that counts and the next weakest is picked.
func _goal_piece() -> StructurePiece:
	var gid: String = str(raid.get("goal_piece", ""))
	if gid == "":
		return null
	var piece: StructurePiece = _piece(gid)
	if piece != null and piece.hp > 0.0:
		return piece
	raid["broken"] = int(raid.get("broken", 0)) + 1
	_pick_goal()
	return _piece(str(raid["goal_piece"]))


## Sets the raid's goal to the weakest piece of its base (the target itself with none) and lays
## the way in to it.
func _pick_goal() -> void:
	var piece: StructurePiece = weakest_piece(raid["target"], float(fd.raids.get("base_range", 60.0))) if bool(raid["base"]) else null
	raid["goal_piece"] = String(piece.piece_id) if piece != null else ""
	raid["goal"] = piece.global_position if piece != null else raid["target"]
	_build_flow()


## The base's weakest piece within `r` m of `center`: the fewest hit points (ties by id, so every
## run picks the same), never a lit fire (they won't go near) or a garden bed (looted, not broken).
func weakest_piece(center: Vector3, r: float) -> StructurePiece:
	var best: StructurePiece = null
	var b: Node = _building()
	if b == null:
		return null
	for piece: StructurePiece in b.call(&"pieces_in_radius", center, r):
		if piece.lit or Farming.is_farm(piece.def) or piece.hp <= 0.0 or piece.is_queued_for_deletion():
			continue
		if best == null or piece.hp < best.hp - 0.001 or (absf(piece.hp - best.hp) <= 0.001 and String(piece.piece_id) < String(best.piece_id)):
			best = piece
	return best


## The raid's FlowField round its base, integrated to its goal: the player's structures cost their
## hit points to cross (so the way in runs through the weak spots, as the Hum's does), lit fires
## cost fire_cost out to fire.keep_off, garden beds and the goal piece cost nothing. Built at once
## (raids.flow radius 50 m at 1.5 m is ~4.6k cells), so the raid's path is a function of the world.
func _build_flow() -> void:
	flow = null
	var b: Node = _building()
	if not bool(raid.get("base", false)) or b == null:
		return
	var cfg: Dictionary = fd.raids.get("flow", {})
	var target: Vector3 = raid["target"]
	var f := FlowField.new()
	f.setup(target, float(cfg.get("radius", 50.0)), float(cfg.get("cell", 1.5)))
	var ground: float = target.y
	var height_fn: Callable = Callable(world, &"height_at") if world != null and world.has_method(&"height_at") \
		else func(_x: float, _z: float) -> float: return ground
	var wsys: Node = world.get(&"water") if world != null else null
	var water_fn: Callable = Callable(wsys, &"water_level_at") if wsys != null and wsys.has_method(&"water_level_at") else Callable()
	f.build_terrain(height_fn, water_fn, float(cfg.get("slope_max_deg", 42.0)))
	var gid: String = str(raid.get("goal_piece", ""))
	var walls: Array = []
	var fires: Array = []
	for piece: StructurePiece in b.call(&"pieces_in_radius", target, f.cell * f.n * 0.5):
		if String(piece.piece_id) == gid or Farming.plots_of(piece.def) > 0:
			continue
		if piece.lit:
			fires.append({"a": piece.global_position, "b": piece.global_position, "hp": float(cfg.get("fire_cost", 60.0))})
		elif piece.is_log():
			var seg: PackedVector3Array = LogSnapper.segment(piece.global_transform)
			walls.append({"a": seg[0], "b": seg[1], "hp": piece.hp})
		else:
			walls.append({"a": piece.global_position, "b": piece.global_position, "hp": piece.hp})
	f.add_structures(walls, float(cfg.get("structure_cost_per_hp", 0.02)))
	f.add_structures(fires, 1.0, float(fd.fire.get("keep_off", 4.0)))
	var goals: Array[Vector3] = [raid["goal"]]
	f.integrate(goals)
	flow = f


## A raider at a garden bed (raids.gardens): tramples it once a raid (trample_damage off every
## growing plant) and takes whatever is ripe (FarmManager.raid_bed).
func _raid_gardens(e: Enemy) -> void:
	var g: Dictionary = fd.raids.get("gardens", {})
	var loot: bool = bool(g.get("loot_crops", false))
	var trample: bool = bool(g.get("trample", false))
	var b: Node = _building()
	if (not loot and not trample) or b == null:
		return
	var reach: float = float(g.get("reach", 1.2))
	var trampled: Dictionary = raid["trampled"]
	for piece: StructurePiece in b.call(&"pieces_in_radius", e.global_position, reach):
		if Farming.plots_of(piece.def) <= 0 or e._flat_dist(piece.global_position) > maxf(piece.def.size.x, piece.def.size.z) * 0.5 + reach:
			continue
		var pid: String = String(piece.piece_id)
		var dmg: float = float(g.get("trample_damage", 0.5)) if trample and not trampled.has(pid) else 0.0
		var r: Dictionary = FarmManager.raid_bed(piece, loot, dmg)
		if dmg > 0.0:
			trampled[pid] = true
		var n: int = 0
		for k: Variant in (r["looted"] as Dictionary).keys():
			n += int(r["looted"][k])
		if n > 0:
			if int(raid["looted"]) == 0:
				Events.player_status_message.emit("The Ashen are stripping your garden.", &"warning")
			raid["looted"] = int(raid["looted"]) + n
			Log.info("ashen", "%s took %d ripe plot(s) from %s" % [e.entity_id, n, pid])


## The nearest garden bed to `near` within base_range of the raid's base with something ripe in it.
func _ripe_bed(near: Vector3) -> StructurePiece:
	var b: Node = _building()
	if b == null or not bool(raid.get("base", false)):
		return null
	var best: StructurePiece = null
	var best_d: float = INF
	for piece: StructurePiece in b.call(&"pieces_in_radius", raid["target"], float(fd.raids.get("base_range", 60.0))):
		if Farming.plots_of(piece.def) <= 0:
			continue
		var ripe: bool = false
		for plot: Dictionary in FarmManager.peek(piece).get("plots", []):
			ripe = ripe or Farming.is_ripe(plot)
		var d: float = _flat(near, piece.global_position)
		if ripe and (d < best_d - 0.001 or (absf(d - best_d) <= 0.001 and String(piece.piece_id) < String(best.piece_id))):
			best = piece
			best_d = d
	return best


## A base nobody is home at (the player beyond base_range) that the band reached is sacked once
## it broke sack_pieces pieces (or had nothing to break) and took every ripe crop.
func _sacked(p: Player) -> bool:
	if not bool(raid["base"]) or not bool(raid["arrived"]):
		return false
	if _flat(p.global_position, raid["target"]) <= float(fd.raids.get("base_range", 60.0)):
		return false
	if bool((fd.raids.get("gardens", {}) as Dictionary).get("loot_crops", false)) and _ripe_bed(raid["target"]) != null:
		return false
	return int(raid["broken"]) >= int(fd.raids.get("sack_pieces", 2)) or str(raid["goal_piece"]) == ""


## Every raider still in the fight turns for the trees.
func _leave(p: Player) -> void:
	for e: Variant in raid["members"]:
		if e is Enemy and is_instance_valid(e) and (e as Enemy).is_alive():
			(e as Enemy).tribe.flee(p)


func _end_raid(repelled: bool, how: String = "gave up") -> void:
	var rid: String = str(raid.get("id", ""))
	for e: Variant in raid.get("members", []):
		if e is Enemy and is_instance_valid(e) and (e as Enemy).is_alive() and not _leaving.has(e):
			_leaving.append(e)
	raid = {}
	flow = null
	if repelled:
		provoke("raid_repelled")
		var pl: PlayerState = Game.session.local_player()
		if pl != null:
			pl.progression.award("repel_raid")
		Events.player_status_message.emit("The Ashen are gone back into the trees.", &"info")
	Events.ashen_raid_ended.emit(rid, repelled)
	Log.info("ashen", "raid %s over (%s)" % [rid, "repelled" if repelled else how])


## Raiders of a finished raid on their way out: despawned once they get away.
func _follow_leaving() -> void:
	for e: Enemy in _leaving.duplicate():
		if not is_instance_valid(e) or not e.is_alive():
			_leaving.erase(e)
		elif e.tribe.gone:
			_leaving.erase(e)
			_ai().call(&"despawn", e)
		elif e.state != Enemy.State.FLEE:
			e.tribe.flee(_player())


## The player's base: the centre of what they built within base_range of them, else where they stand.
func base_of(p: Player) -> Vector3:
	var b: Vector3 = _base_near(p.global_position)
	return b if b != Vector3.INF else p.global_position


## The centre of the player's pieces within base_range of `pos`; Vector3.INF with none.
func _base_near(pos: Vector3) -> Vector3:
	var b: Node = _building()
	if b == null:
		return Vector3.INF
	var near: Array = b.call(&"pieces_in_radius", pos, float(fd.raids.get("base_range", 60.0)))
	if near.is_empty():
		return Vector3.INF
	var c := Vector3.ZERO
	for piece: Variant in near:
		c += (piece as Node3D).global_position
	return c / float(near.size())


## Where the base's lit fires and stations burn (StructurePiece.lit), within base_range.
func _lit_fires(center: Vector3) -> Array:
	var out: Array = []
	var b: Node = _building()
	if b == null:
		return out
	for piece: StructurePiece in b.call(&"pieces_in_radius", center, float(fd.raids.get("base_range", 60.0))):
		if piece.lit:
			out.append(piece.global_position)
	return out


## The bearing (radians, as _ring_point measures it) of the side of `center` its fires light
## least: opposite their summed directions. NAN when no fire leans any way (none, or one in the
## middle lighting every side).
static func dark_bearing(center: Vector3, fires: Array) -> float:
	var light := Vector2.ZERO
	for f: Variant in fires:
		var d := Vector2((f as Vector3).x - center.x, (f as Vector3).z - center.z)
		if d.length() > 1.0:
			light += d.normalized()
	if light.length() < 0.05:
		return NAN
	return atan2(-light.y, -light.x)


func _building() -> Node:
	var b: Node = world.get(&"building") if world != null else null
	return b if b != null and b.has_method(&"pieces_in_radius") else null


func _piece(id: String) -> StructurePiece:
	var b: Node = _building()
	var all: Variant = b.get(&"pieces") if b != null else null
	var piece: Variant = (all as Dictionary).get(StringName(id)) if all is Dictionary else null
	return piece if piece is StructurePiece and is_instance_valid(piece) and not (piece as Node).is_queued_for_deletion() else null


## Radians either side of the bearing to the camp a band comes from (standing.spread).
func _camp_spread() -> float:
	return deg_to_rad(float(fd.standing.get("spread", 30.0)))


## How close a raider must stand to strike a piece.
static func _reach(piece: StructurePiece) -> float:
	return maxf(piece.def.size.x, piece.def.size.z) * 0.5 + 1.6


static func _flat(a: Vector3, b: Vector3) -> float:
	return Vector2(a.x - b.x, a.z - b.z).length()


## A spawn point `lo`-`hi` m from `center` the AI director accepts (out of sight, dry, outside
## buildings and trader safe zones), on a bearing the key picks (within `spread` of `bearing` when
## one is given, widening as tries fail); Vector3.INF if none.
func _ring_point(center: Vector3, lo: float, hi: float, key: String, bearing: float = NAN, spread: float = PI) -> Vector3:
	var rng := RandomNumberGenerator.new()
	rng.seed = Ids.hash64("ashen:ring:%d:%s" % [Game.session.world_seed, key])
	var ai: Node = _ai()
	for attempt: int in 16:
		var ang: float = rng.randf() * TAU
		if not is_nan(bearing):
			ang = bearing + (ang / TAU * 2.0 - 1.0) * minf(PI, spread * (1.0 + float(attempt) / 8.0))
		var r: float = rng.randf_range(lo, hi)
		var at := Vector3(center.x + cos(ang) * r, 0.0, center.z + sin(ang) * r)
		at.y = _height(at) + 0.4
		# (an AI director with no world, as in tests, has nothing to check against)
		if ai == null or ai.get(&"world") == null or bool(ai.call(&"spawn_point_ok", at)):
			return at
	return Vector3.INF


# --- Save (TD-189) ---------------------------------------------------------------------------------

## The bands out now, as saved in WorldState.ashen.live: the raid (its members' enemy ids,
## positions, morale and jobs, its goal and elapsed time) and the scouts. Those already running
## off are left out: they were leaving anyway.
func live_state() -> Dictionary:
	var out: Dictionary = {}
	if not raid.is_empty():
		var ms: Array = []
		for e: Variant in raid["members"]:
			if _holds(e):
				var en: Enemy = e
				ms.append({"id": String(en.entity_id), "enemy": String(en.def.id), "pos": _arr(en.global_position),
					"morale": en.tribe.morale, "job": str((raid["jobs"] as Dictionary).get(String(en.entity_id), "goal"))})
		if not ms.is_empty():
			out["raid"] = {"id": raid["id"], "t": raid["t"], "target": _arr(raid["target"]), "base": raid["base"],
				"goal": _arr(raid["goal"]), "goal_piece": raid["goal_piece"], "from": _arr(raid["from"]), "size": raid["size"],
				"broken": raid["broken"], "trampled": (raid["trampled"] as Dictionary).keys(), "looted": raid["looted"],
				"arrived": raid["arrived"], "camp": raid.get("camp", ""), "members": ms}
	var sc: Array = []
	for e2: Enemy in _scouts:
		if _holds(e2):
			sc.append({"id": String(e2.entity_id), "enemy": String(e2.def.id), "pos": _arr(e2.global_position),
				"goal": _arr(e2.tribe.goal) if e2.tribe.goal != Vector3.INF else [], "watched": e2.tribe.watched, "morale": e2.tribe.morale,
				"camp": e2.tribe.camp_id})
	if not sc.is_empty():
		out["scouts"] = sc
	return out


func _holds(e: Variant) -> bool:
	return e is Enemy and is_instance_valid(e) and (e as Enemy).is_alive() and not (e as Enemy).tribe.gone \
		and (e as Enemy).state != Enemy.State.FLEE


func _on_game_saving(_slot: String) -> void:
	if fd == null or Game.session == null:
		return
	# Not brought back yet (saved in the moment before the first tick): keep what was loaded.
	var live: Dictionary = _restore if not _restore.is_empty() else live_state()
	if live.is_empty():
		state().erase("live")
	else:
		state()["live"] = live


## Brings back the bands a save had out (live_state()), as themselves: the same ids, where they
## stood, their morale, the raid's goal, jobs and clock.
func restore_live(live: Dictionary) -> void:
	if fd == null or _ai() == null:
		return
	var rd: Dictionary = live.get("raid", {})
	if not rd.is_empty() and raid.is_empty():
		var target: Vector3 = _vec(rd.get("target"))
		var band: Array = []
		var jobs: Dictionary = {}
		for m: Variant in rd.get("members", []):
			var e: Enemy = _respawn(m as Dictionary, {"job": "raid", "goal": target, "camp": str(rd.get("camp", ""))})
			if e != null:
				e.home = target
				jobs[String(e.entity_id)] = str((m as Dictionary).get("job", "goal"))
				band.append(e)
		if not band.is_empty() and target != Vector3.INF:
			for e2: Variant in band:
				(e2 as Enemy).tribe.band = band
			var trampled: Dictionary = {}
			for k: Variant in rd.get("trampled", []):
				trampled[str(k)] = true
			var goal: Vector3 = _vec(rd.get("goal"))
			raid = {"id": str(rd.get("id", "")), "members": band, "jobs": jobs, "t": float(rd.get("t", 0.0)), "target": target,
				"base": bool(rd.get("base", false)), "goal": goal if goal != Vector3.INF else target,
				"goal_piece": str(rd.get("goal_piece", "")), "from": _vec(rd.get("from")), "size": int(rd.get("size", band.size())),
				"broken": int(rd.get("broken", 0)), "trampled": trampled, "looted": int(rd.get("looted", 0)),
				"arrived": bool(rd.get("arrived", false)), "camp": str(rd.get("camp", ""))}
			# (its goal piece may have gone meanwhile: the next steer counts that and picks again)
			_build_flow()
			Log.info("ashen", "raid %s resumes with %d" % [raid["id"], band.size()])
	for s: Variant in live.get("scouts", []):
		var sd: Dictionary = s
		var opts: Dictionary = {"job": "scout", "camp": str(sd.get("camp", ""))}
		if _vec(sd.get("goal")) != Vector3.INF:
			opts["goal"] = _vec(sd.get("goal"))
		var sc: Enemy = _respawn(sd, opts)
		if sc == null:
			continue
		sc.tribe.band = [sc]
		sc.tribe.watched = float(sd.get("watched", 0.0))
		sc._set_state(Enemy.State.OBSERVE)
		_scouts.append(sc)


func _respawn(m: Dictionary, opts: Dictionary) -> Enemy:
	var pos: Vector3 = _vec(m.get("pos"))
	if pos == Vector3.INF:
		return null
	var o: Dictionary = {"tier": "normal", "authored": true}
	o.merge(opts, true)
	if str(m.get("id", "")) != "":
		o["id"] = str(m["id"])
	var e: Enemy = _ai().call(&"spawn", StringName(str(m.get("enemy", "ashen_raider"))), pos + Vector3.UP * 0.2, o)
	if e != null:
		e.tribe.morale = float(m.get("morale", 1.0))
	return e


static func _arr(v: Vector3) -> Array:
	return [v.x, v.y, v.z]


static func _vec(v: Variant) -> Vector3:
	if v is Array and (v as Array).size() >= 3:
		return Vector3(float(v[0]), float(v[1]), float(v[2]))
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
	dead.tribe.douse()
	# Its own camp (a resident's, or the camp a raid or scout came from) holds the death against them.
	if by_player:
		anger_camp(dead.tribe.camp_id, "kill")
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
				# A wiped camp sends nothing; its kin camps take up the grudge.
				for other: Dictionary in camps():
					if other["id"] != c["id"]:
						anger_camp(other["id"], "kin_wiped")
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
			anger_camp(c["id"], "heat")
			return


## The Hum is coming: every Ashen out of their camps runs for home.
func _on_hum(_day: int) -> void:
	var p: Player = _player()
	for e: Enemy in _scouts:
		if is_instance_valid(e) and e.is_alive():
			e.tribe.flee(p)
	if not raid.is_empty():
		_leave(p)
		_end_raid(false, "ran from the Hum")


## Debug and QA: a raid now with the level's band (or `n` raiders).
func debug_raid(n: int = 0) -> Dictionary:
	var p: Player = _player()
	if p == null or fd == null:
		return {}
	var members: Array = []
	for i: int in maxi(1, n if n > 0 else 4):
		members.append("ashen_scout" if i % 4 == 3 else "ashen_raider")
	return start_raid(p, members)
