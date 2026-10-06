class_name AIDirector
extends Node3D
## Owns every Hollowed in the world: spawning (wandering population by biome, time and
## gamestage; heat-triggered scouts/Keeners/packs; Keener summons; hound packs (ADR-0034); POI
## sleepers via PoiManager;
## Hum waves via HumDirector), despawning out of range, corpse cleanup, and spatial queries for
## other systems (sleep checks, debug overlay). Wanderers are not persisted — the population is
## re-rolled around you; sleepers persist through their POI's state (dead ids).

const SPAWN_MIN: float = 70.0
const SPAWN_MAX: float = 120.0
const DESPAWN_RANGE: float = 190.0
const POP_INTERVAL: float = 5.0
const MAX_CORPSES: int = 24
const CORPSE_SECONDS: float = 300.0
## Summoned/scripted spawns never appear closer than this to the player.
const MIN_SPAWN_DIST: float = 35.0
## Hard cap on awake non-sleeper Hollowed outside the Hum (Keener screams, heat responses).
const MAX_ROAMING: int = 28

var world: Node
var hum: HumDirector
var nav: NavTiles
var enemies: Dictionary = {}
var _pop_t: float = 0.0
var _rng := RandomNumberGenerator.new()
var _ids: int = 0


func setup_world(w: Node) -> void:
	world = w
	_rng.seed = Ids.derive_seed(Game.session.world_seed, "ai:%d" % Game.session.clock.day())
	hum = HumDirector.new()
	hum.name = "Hum"
	hum.ai = self
	add_child(hum)
	nav = NavTiles.new()
	nav.name = "NavTiles"
	add_child(nav)
	nav.setup(world)
	if world.clock_driver != null:
		world.clock_driver.game_minutes_passed.connect(_on_minutes)
	Game.session.heat.configure(Content.config(&"heat"))


# --- Spawning --------------------------------------------------------------------------------

## opts: id, yaw, target, tier, tier_bonus, pose/poi/sleeper (POI sleepers), authored (keep the
## requested type even below its gamestage: sleepers, the debug spawn menu, QA shots).
func spawn(enemy_id: StringName, pos: Vector3, opts: Dictionary = {}) -> Enemy:
	var gs: int = _gamestage()
	enemy_id = allowed_enemy(enemy_id, gs, opts.has("sleeper") or bool(opts.get("authored", false)))
	var def: EnemyDef = Content.enemy(enemy_id)
	if def == null:
		Log.warn("ai", "unknown enemy %s" % enemy_id)
		return null
	_ids += 1
	var id: StringName = StringName(str(opts.get("id", ""))) if opts.has("id") else StringName("e:%d" % _ids)
	if not opts.has("tier"):
		# Deterministic per entity (a sleeper is the same Bloomed brute every time you return).
		var trng := RandomNumberGenerator.new()
		trng.seed = Ids.hash64("tier:%d:%s" % [Game.session.world_seed if Game.session != null else 0, id])
		opts = opts.duplicate()
		opts["tier"] = InfectedTiers.pick(gs + int(opts.get("tier_bonus", 0)), trng)
	if bool(opts.get("guardian", false)):
		opts = opts.duplicate()
		opts["tier"] = guardian_tier(StringName(str(opts["tier"])))
	var e := Enemy.new()
	e.setup(id, def, self, opts)
	e.name = String(id).replace(":", "_")
	# Placed before entering the tree: _ready() takes its home, wander anchor and facing from the
	# transform it has then (placing afterwards left every body facing south, homed at the origin).
	e.position = to_local(pos) if is_inside_tree() else pos
	e.rotation.y = float(opts.get("yaw", _rng.randf() * TAU))
	add_child(e)
	if opts.has("target"):
		e.notice(opts["target"])
	enemies[id] = e
	e.died.connect(_on_died)
	Events.enemy_spawned.emit(id, enemy_id, pos)
	return e


## Dormant sleeper placed by a POI (pose: lie/sit/stand/kneel/crouch). Harder buildings roll
## their sleepers' infected tier at a higher gamestage. extra (ADR-0018): "group" (ambush group),
## "held" (dormant until the group's trigger fires), "guardian" (one infected tier up); ADR-0022:
## "perch" (the seat or bed it sits or lies on, Enemy.perch), "awake_at" (spawn it up and about,
## heading there: its building was roused while nobody was near).
func spawn_sleeper(enemy_id: StringName, pos: Vector3, yaw: float, pose: String, poi_id: StringName, sleeper_id: StringName,
		poi_tier: int = 1, extra: Dictionary = {}) -> Enemy:
	var bonus: int = int((InfectedTiers.cfg().get("sleeper_tier_bonus", {}) as Dictionary).get("per_poi_tier", 8)) * maxi(0, poi_tier - 1)
	var opts: Dictionary = {"yaw": yaw, "pose": pose, "poi": poi_id, "sleeper": sleeper_id, "id": "sl:%s:%s" % [poi_id, sleeper_id],
		"tier_bonus": bonus}
	for k: String in ["group", "held", "guardian", "perch", "awake_at"]:
		if extra.has(k):
			opts[k] = extra[k]
	return spawn(enemy_id, pos, opts)


## A guardian's infected tier: the rolled one, stepped up (normal -> Seeded -> Bloomed) by
## data/config/traps.json guardian.tier_steps. The world setting that turns tiers off wins.
static func guardian_tier(rolled: StringName) -> StringName:
	if not GameRules.current().flag("infected_tiers"):
		return rolled
	var order: Array[StringName] = [&"normal", &"seeded", &"bloomed"]
	var steps: int = int((Content.config(&"traps").get("guardian", {}) as Dictionary).get("tier_steps", 1))
	return order[clampi(maxi(0, order.find(rolled)) + steps, 0, order.size() - 1)]


## What actually spawns for a request: authored sleepers keep their type; everything else must
## meet the type's gamestage_min. Special Hollowed obey the world setting either way.
static func allowed_enemy(enemy_id: StringName, gamestage: int, authored: bool) -> StringName:
	var def: EnemyDef = Content.enemy(enemy_id)
	if def == null:
		return enemy_id
	if bool(def.beh("special", false)) and not GameRules.current().flag("special_hollowed"):
		return &"hollow"
	if def.archetype == "hound" and not GameRules.current().flag("hollowed_hounds"):
		return &"hollow"
	if not authored and def.gamestage_min > gamestage:
		return &"hollow"
	return enemy_id


func despawn(e: Enemy) -> void:
	enemies.erase(e.entity_id)
	e.queue_free()


func _on_died(e: Enemy) -> void:
	pass


func _on_minutes(minutes: float) -> void:
	for t: Dictionary in Game.session.heat.tick(minutes):
		_heat_response(t)


func _heat_response(t: Dictionary) -> void:
	var p: Player = world.player
	if p == null:
		return
	var target: Vector3 = t["pos"]
	target.y = world.height_at(target.x, target.z)
	var group: Array[StringName] = []
	if str(t["kind"]) == "pack" and hounds_allowed(_gamestage()) and _rng.randf() < float(Content.config(&"hounds").get("heat_pack", 0.5)):
		# the noise has drawn a hound pack: it comes in on the scent
		var from: Vector3 = _offscreen_point(target, 60.0, 90.0)
		if from != Vector3.INF and _roaming_count() < MAX_ROAMING:
			spawn_pack(&"hollow_hound", from, {"target": target})
			Log.info("ai", "heat response 'hounds' at %s (heat %.0f)" % [target, t["heat"]])
		return
	match str(t["kind"]):
		"scout":
			group = [&"hollow"]
		"keener":
			group = [&"keener", &"hollow", &"hollow"]
		"pack":
			group = [&"lurcher", &"hollow", &"hollow", &"hollow", &"hollow"]
	var origin: Vector3 = _offscreen_point(target, 60.0, 90.0)
	if origin == Vector3.INF or _roaming_count() >= MAX_ROAMING:
		return
	for id: StringName in group:
		var def: EnemyDef = Content.enemy(id)
		if def != null and def.gamestage_min > _gamestage():
			id = &"hollow"
		spawn(id, _ground(origin + Vector3(_rng.randf_range(-3, 3), 0.0, _rng.randf_range(-3, 3))), {"target": target + Vector3(_rng.randf_range(-6, 6), 0, _rng.randf_range(-6, 6))})
	Log.info("ai", "heat response '%s' at %s (heat %.0f)" % [t["kind"], target, t["heat"]])


## A hound pack (ADR-0034): `def.behavior.pack.size` hounds of `enemy_id` round `pos`, each knowing
## the others (Enemy.pack) and its place in their spread. opts are passed to every spawn (a
## "target" sends the pack to look there). Returns the hounds.
func spawn_pack(enemy_id: StringName, pos: Vector3, opts: Dictionary = {}) -> Array[Enemy]:
	var out: Array[Enemy] = []
	var def: EnemyDef = Content.enemy(enemy_id)
	if def == null:
		return out
	var size: Array = (def.beh("pack", {}) as Dictionary).get("size", [3, 5])
	var n: int = _rng.randi_range(int(size[0]), int(size[1]))
	for i: int in n:
		var at: Vector3 = pos + Vector3(_rng.randf_range(-4.0, 4.0), 0.0, _rng.randf_range(-4.0, 4.0))
		var o: Dictionary = opts.duplicate()
		if opts.has("id"):
			o["id"] = "%s:%d" % [opts["id"], i]
		if opts.has("target"):
			o["target"] = (opts["target"] as Vector3) + Vector3(_rng.randf_range(-5, 5), 0, _rng.randf_range(-5, 5))
		var e: Enemy = spawn(enemy_id, _ground(at) if world != null else at, o)
		if e != null:
			out.append(e)
	for i: int in out.size():
		out[i].pack = out
		out[i].pack_slot = i
	return out


## Whether hound packs may appear at this gamestage (the world setting, and the hound's own
## gamestage_min).
func hounds_allowed(gamestage: int) -> bool:
	var def: EnemyDef = Content.enemy(&"hollow_hound")
	return def != null and GameRules.current().flag("hollowed_hounds") and gamestage >= def.gamestage_min


## A Keener's scream calls Hollowed from out of sight toward it.
func on_scream(keener: Enemy, count: int) -> void:
	for e: Enemy in enemies_in_radius(keener.global_position, float(keener.def.beh("scream_radius", 120.0))):
		if e != keener and e.is_alive():
			e.notice(keener.global_position)
	# Each Keener can only call so many in total, and never past the roaming cap.
	var budget: int = int(keener.get_meta(&"summon_budget", int(keener.def.beh("summon_budget", 6))))
	count = mini(count, mini(budget, MAX_ROAMING - _roaming_count()))
	if count <= 0:
		return
	keener.set_meta(&"summon_budget", budget - count)
	for i: int in count:
		var pos: Vector3 = _offscreen_point(keener.global_position, 40.0, 70.0)
		if pos == Vector3.INF:
			continue
		spawn(&"hollow" if _rng.randf() < 0.75 or _gamestage() < 3 else &"lurcher", _ground(pos), {"target": keener.global_position})


## Awake Hollowed that are neither POI sleepers nor Hum members.
func _roaming_count() -> int:
	var n: int = 0
	for e: Enemy in enemies.values():
		if is_instance_valid(e) and e.is_alive() and e.poi_id == &"" and not e.horde:
			n += 1
	return n


## A point lifted onto the ground under it (each group member stands on its own patch of slope).
func _ground(p: Vector3) -> Vector3:
	return Vector3(p.x, world.height_at(p.x, p.z) + 0.4, p.z)


func _gamestage() -> int:
	var p: PlayerState = Game.local_player()
	return Game.session.gamestage(p)


# --- Population --------------------------------------------------------------------------------

func _process(delta: float) -> void:
	_pop_t += delta
	if _pop_t < POP_INTERVAL or world == null or world.player == null or not world.is_ready:
		return
	_pop_t = 0.0
	var ppos: Vector3 = world.player.global_position
	var wanderers: int = 0
	var corpses: Array[Enemy] = []
	for id: StringName in enemies.keys():
		var e: Enemy = enemies[id]
		if not is_instance_valid(e):
			enemies.erase(id)
			continue
		var d: float = e.global_position.distance_to(ppos)
		if not e.is_alive():
			corpses.append(e)
			if e._corpse_t > CORPSE_SECONDS and d > 40.0:
				despawn(e)
			continue
		if e.poi_id != &"" or e.horde:
			continue
		if d > DESPAWN_RANGE:
			despawn(e)
			continue
		wanderers += 1
	if corpses.size() > MAX_CORPSES:
		corpses.sort_custom(func(a: Enemy, b: Enemy) -> bool: return a._corpse_t > b._corpse_t)
		for i: int in corpses.size() - MAX_CORPSES:
			despawn(corpses[i])
	if hum.active:
		return
	var want: int = _wanted_wanderers(ppos)
	if wanderers < want:
		_spawn_group(ppos)


func _wanted_wanderers(ppos: Vector3) -> int:
	var rt: RegionTerrain = world.terrain.region_terrain_at(ppos.x, ppos.z)
	var density: float = 0.6
	if rt != null:
		var b: BiomeDef = Content.get_def(&"biome", StringName(_spawn_biome(rt, ppos.x, ppos.z))) as BiomeDef
		if b != null:
			density = b.spawn_density
	var night: bool = Game.session.clock.is_night()
	var base: float = 4.0 * density * (1.8 if night else 1.0)
	if Game.session.clock.day() <= 1:
		base *= 0.5
	base *= GameRules.current().num("wanderer_density")
	return int(round(base))


func _spawn_group(ppos: Vector3) -> void:
	var pos: Vector3 = _offscreen_point(ppos, SPAWN_MIN, SPAWN_MAX)
	if pos == Vector3.INF:
		return
	var rt: RegionTerrain = world.terrain.region_terrain_at(pos.x, pos.z)
	var table: Dictionary = {"hollow": 10}
	if rt != null:
		var b: BiomeDef = Content.get_def(&"biome", StringName(_spawn_biome(rt, pos.x, pos.z))) as BiomeDef
		if b != null and not b.spawns.is_empty():
			table = b.spawns
	var gs: int = _gamestage()
	var hc: Dictionary = Content.config(&"hounds").get("spawn", {})
	var chance: float = float(hc.get("chance", 0.12)) * (float(hc.get("night_mult", 2.0)) if Game.session.clock.is_night() else 1.0)
	if hounds_allowed(gs) and _rng.randf() < chance:
		spawn_pack(&"hollow_hound", pos)
		return
	var n: int = _rng.randi_range(1, 3)
	for i: int in n:
		var id := StringName(str(Weighted.pick_key(table, _rng)))
		var def: EnemyDef = Content.enemy(id)
		if def == null or def.gamestage_min > gs:
			id = &"hollow"
		spawn(id, _ground(pos + Vector3(_rng.randf_range(-4, 4), 0.0, _rng.randf_range(-4, 4))))


## The biome whose spawns apply at (x, z): an organic town's whole ground spawns as town, not only
## its streets, which are all the composer paints `town` (TD-136).
func _spawn_biome(rt: RegionTerrain, x: float, z: float) -> String:
	var composed: String = rt.biome_at(x, z)
	var wdef: WorldDef = world.get(&"world_def") as WorldDef
	return wdef.behaviour_biome(composed, x, z) if wdef != null else composed


## A point on dry land at `min_d..max_d` from `center`, out of the player's view (or INF).
func _offscreen_point(center: Vector3, min_d: float, max_d: float) -> Vector3:
	var p: Player = world.player
	var fwd: Vector3 = -p.camera.global_transform.basis.z if p != null else Vector3.FORWARD
	var flat_fwd := Vector3(fwd.x, 0, fwd.z).normalized()
	for attempt: int in 16:
		var ang: float = _rng.randf() * TAU
		var dir := Vector3(sin(ang), 0, cos(ang))
		var pos: Vector3 = center + dir * _rng.randf_range(min_d, max_d)
		pos.y = world.height_at(pos.x, pos.z)
		if p != null and (pos - p.global_position).normalized().dot(flat_fwd) > -0.1 and attempt < 12:
			continue
		if spawn_point_ok(pos):
			return pos
	return Vector3.INF


## Whether a Hollowed can appear at `pos`: inside the map, dry, not on a cliff, not inside a
## building or someone's base or a trader's safe zone, and not on top of the player.
func spawn_point_ok(pos: Vector3) -> bool:
	if world.terrain.region_terrain_at(pos.x, pos.z) == null:
		return false
	var p: Player = world.player
	if p != null and Vector2(pos.x - p.global_position.x, pos.z - p.global_position.z).length() < MIN_SPAWN_DIST:
		return false
	var wsys: Node = world.get(&"water")
	if wsys != null and wsys.has_method(&"depth_at") and float(wsys.call(&"depth_at", pos)) > 0.2:
		return false
	var e: float = 1.0
	var slope: float = Vector2(world.height_at(pos.x + e, pos.z) - world.height_at(pos.x - e, pos.z),
		world.height_at(pos.x, pos.z + e) - world.height_at(pos.x, pos.z - e)).length() / (2.0 * e)
	if slope > 0.84:  # ~40 degrees
		return false
	var pois: Node = world.get(&"pois")
	if pois != null and pois.has_method(&"poi_at") and pois.call(&"poi_at", pos + Vector3.UP) != null:
		return false
	# Streamed worlds: nor where a building not built yet will stand (RWG v2 Phase 3).
	if pois != null and pois.has_method(&"footprint_at") and pois.call(&"footprint_at", pos) != &"":
		return false
	var b: Node = world.get(&"building")
	if b != null and b.has_method(&"pieces_in_radius") and not (b.call(&"pieces_in_radius", pos, 6.0) as Array).is_empty():
		return false
	# A trader post's safe zone (ADR-0039): its guards keep it clear.
	var tr: Node = world.get(&"traders")
	if tr != null and tr.has_method(&"is_safe") and bool(tr.call(&"is_safe", pos)):
		return false
	return true


# --- Queries ------------------------------------------------------------------------------------

func enemies_in_radius(pos: Vector3, r: float) -> Array[Enemy]:
	var out: Array[Enemy] = []
	for e: Enemy in enemies.values():
		if is_instance_valid(e) and e.global_position.distance_to(pos) <= r:
			out.append(e)
	return out


func hostiles_near(pos: Vector3, r: float) -> int:
	var n: int = 0
	for e: Enemy in enemies_in_radius(pos, r):
		if e.is_alive() and e.state != Enemy.State.SLEEP:
			n += 1
	return n


func horde_direction(pos: Vector3) -> Vector3:
	return hum.direction(pos)


func alive_count() -> int:
	var n: int = 0
	for e: Enemy in enemies.values():
		if is_instance_valid(e) and e.is_alive():
			n += 1
	return n
