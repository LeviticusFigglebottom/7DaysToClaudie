class_name AIDirector
extends Node3D
## Owns every Hollowed in the world: spawning (wandering population by biome, time and
## gamestage; heat-triggered scouts/Keeners/packs; Keener summons; POI sleepers via PoiManager;
## Hum waves via HumDirector), despawning out of range, corpse cleanup, and spatial queries for
## other systems (sleep checks, debug overlay). Wanderers are not persisted — the population is
## re-rolled around you; sleepers persist through their POI's state (dead ids).

const SPAWN_MIN: float = 70.0
const SPAWN_MAX: float = 120.0
const DESPAWN_RANGE: float = 190.0
const POP_INTERVAL: float = 5.0
const MAX_CORPSES: int = 24
const CORPSE_SECONDS: float = 300.0

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

func spawn(enemy_id: StringName, pos: Vector3, opts: Dictionary = {}) -> Enemy:
	var def: EnemyDef = Content.enemy(enemy_id)
	if def == null:
		Log.warn("ai", "unknown enemy %s" % enemy_id)
		return null
	_ids += 1
	var id: StringName = StringName(str(opts.get("id", ""))) if opts.has("id") else StringName("e:%d" % _ids)
	var e := Enemy.new()
	e.setup(id, def, self, opts)
	e.name = String(id).replace(":", "_")
	add_child(e)
	e.global_position = pos
	e.rotation.y = float(opts.get("yaw", _rng.randf() * TAU))
	if opts.has("target"):
		e.notice(opts["target"])
	enemies[id] = e
	e.died.connect(_on_died)
	Events.enemy_spawned.emit(id, enemy_id, pos)
	return e


## Dormant sleeper placed by a POI (pose: lie/sit/stand/kneel/crouch).
func spawn_sleeper(enemy_id: StringName, pos: Vector3, yaw: float, pose: String, poi_id: StringName, sleeper_id: StringName) -> Enemy:
	return spawn(enemy_id, pos, {"yaw": yaw, "pose": pose, "poi": poi_id, "sleeper": sleeper_id, "id": "sl:%s:%s" % [poi_id, sleeper_id]})


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
	match str(t["kind"]):
		"scout":
			group = [&"hollow"]
		"keener":
			group = [&"keener", &"hollow", &"hollow"]
		"pack":
			group = [&"lurcher", &"hollow", &"hollow", &"hollow", &"hollow"]
	var origin: Vector3 = _offscreen_point(target, 60.0, 90.0)
	for id: StringName in group:
		var def: EnemyDef = Content.enemy(id)
		if def != null and def.gamestage_min > _gamestage():
			id = &"hollow"
		spawn(id, origin + Vector3(_rng.randf_range(-3, 3), 0.4, _rng.randf_range(-3, 3)), {"target": target + Vector3(_rng.randf_range(-6, 6), 0, _rng.randf_range(-6, 6))})
	Log.info("ai", "heat response '%s' at %s (heat %.0f)" % [t["kind"], target, t["heat"]])


## A Keener's scream calls Hollowed from out of sight toward it.
func on_scream(keener: Enemy, count: int) -> void:
	for e: Enemy in enemies_in_radius(keener.global_position, float(keener.def.beh("scream_radius", 120.0))):
		if e != keener and e.is_alive():
			e.notice(keener.global_position)
	for i: int in count:
		var pos: Vector3 = _offscreen_point(keener.global_position, 40.0, 70.0)
		spawn(&"hollow" if _rng.randf() < 0.75 or _gamestage() < 3 else &"lurcher", pos + Vector3.UP * 0.4, {"target": keener.global_position})


func _gamestage() -> int:
	var p: PlayerState = Game.local_player()
	return p.progression.gamestage(Game.session.clock.day()) if p != null else 1


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
		var b: BiomeDef = Content.get_def(&"biome", StringName(rt.biome_at(ppos.x, ppos.z))) as BiomeDef
		if b != null:
			density = b.spawn_density
	var night: bool = Game.session.clock.is_night()
	var base: float = 4.0 * density * (1.8 if night else 1.0)
	if Game.session.clock.day() <= 1:
		base *= 0.5
	var mode: Dictionary = Game.session.mode_config()
	base *= float(mode.get("wander_mult", 1.0))
	return int(round(base))


func _spawn_group(ppos: Vector3) -> void:
	var pos: Vector3 = _offscreen_point(ppos, SPAWN_MIN, SPAWN_MAX)
	if pos == Vector3.INF:
		return
	var rt: RegionTerrain = world.terrain.region_terrain_at(pos.x, pos.z)
	var table: Dictionary = {"hollow": 10}
	if rt != null:
		var b: BiomeDef = Content.get_def(&"biome", StringName(rt.biome_at(pos.x, pos.z))) as BiomeDef
		if b != null and not b.spawns.is_empty():
			table = b.spawns
	var gs: int = _gamestage()
	var n: int = _rng.randi_range(1, 3)
	for i: int in n:
		var id := StringName(str(Weighted.pick_key(table, _rng)))
		var def: EnemyDef = Content.enemy(id)
		if def == null or def.gamestage_min > gs:
			id = &"hollow"
		spawn(id, pos + Vector3(_rng.randf_range(-4, 4), 0.4, _rng.randf_range(-4, 4)))


## A point on dry land at `min_d..max_d` from `center`, preferably behind the camera.
func _offscreen_point(center: Vector3, min_d: float, max_d: float) -> Vector3:
	var p: Player = world.player
	var fwd: Vector3 = -p.camera.global_transform.basis.z if p != null else Vector3.FORWARD
	var wsys: Node = world.get(&"water")
	for attempt: int in 12:
		var ang: float = _rng.randf() * TAU
		var dir := Vector3(sin(ang), 0, cos(ang))
		if p != null and attempt < 8 and dir.dot(Vector3(fwd.x, 0, fwd.z).normalized()) > -0.2:
			continue
		var pos: Vector3 = center + dir * _rng.randf_range(min_d, max_d)
		pos.y = world.height_at(pos.x, pos.z)
		if world.terrain.region_terrain_at(pos.x, pos.z) == null:
			continue
		if wsys != null and wsys.has_method(&"depth_at") and float(wsys.call(&"depth_at", pos)) > 0.2:
			continue
		return pos
	return Vector3.INF


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
