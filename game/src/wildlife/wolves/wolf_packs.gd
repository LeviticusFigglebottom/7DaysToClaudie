class_name WolfPacks
extends Node
## The valley's wolf packs (ADR-0055), a child of the WildlifeManager. Packs are planned with the
## herds (WildlifeSpawner, WildlifeDef kind `pack`) and spawned here, when the `wolves` world setting
## allows, as Enemies of faction wildlife through the AI director (so they are hit, searched and
## cleared like any body), each wired to its pack (Enemy.pack for the hound brain, Enemy.wolf for
## WolfHunt). The director neither counts nor despawns a wolf: a pack is dropped here once all of it
## is `spawn.despawn` m from the player. Also the packs' window on the world: the player, the clock,
## the prey the WildlifeManager knows, the scent grid, lit fires; and their howls (sound only).
## Nothing is saved: a pack re-rolls with its plan.

var manager: Node = null
var world: Node = null
## The AIDirector the wolves are spawned through (world.ai; set directly by tests).
var ai: Node = null
## Plan id -> WolfPack.
var packs: Dictionary = {}
## Plans whose pack was killed off this session (it doesn't come back).
var spent: Dictionary = {}

var _check_t: float = 0.0


func setup(p_manager: Node, p_world: Node) -> void:
	manager = p_manager
	world = p_world
	if p_world != null and ai == null:
		ai = p_world.get(&"ai") as Node


static func enabled() -> bool:
	return GameRules.current().flag("wolves")


func has_plan(plan_id: StringName) -> bool:
	return packs.has(plan_id) or spent.has(plan_id)


## A pack from a WildlifeSpawner plan: plan.count wolves of `d.enemy` round plan.pos, its hunger
## rolled from the plan's seed. Null when wolves are off, the cap is reached or nothing would spawn.
func spawn_plan(d: WildlifeDef, plan: Dictionary) -> WolfPack:
	if ai == null and world != null:
		ai = world.get(&"ai") as Node
	if not enabled() or ai == null or has_plan(plan["id"]) \
			or packs.size() >= int(WolfPack.section("spawn").get("max_packs", 2)):
		return null
	var rng := RandomNumberGenerator.new()
	rng.seed = int(plan["seed"])
	var start: Array = WolfPack.section("hunger").get("start", [0.15, 0.85])
	var hunger: float = rng.randf_range(float(start[0]), float(start[1]))
	var at: Vector2 = plan["pos"]
	var yaw: float = rng.randf() * TAU
	var members: Array = []
	for i: int in int(plan["count"]):
		var off := Vector2(rng.randf_range(-5.0, 5.0), rng.randf_range(-5.0, 5.0)) if i > 0 else Vector2.ZERO
		var pos := Vector3(at.x + off.x, 0.0, at.y + off.y)
		pos.y = _height(pos) + 0.3
		var e: Enemy = ai.call(&"spawn", d.enemy, pos, {"id": "%s#%d" % [plan["id"], i], "tier": "normal", "authored": true,
			"yaw": yaw + rng.randf_range(-0.8, 0.8)}) as Enemy
		if e != null:
			members.append(e)
	if members.is_empty():
		return null
	var pack := WolfPack.new()
	for i: int in members.size():
		var e: Enemy = members[i]
		e.pack = members
		e.pack_slot = i
	pack.setup(plan["id"], members, hunger, int(plan["seed"]))
	for m: Enemy in members:
		m.wolf = WolfHunt.new(m, pack)
	packs[plan["id"]] = pack
	Log.info("wildlife", "wolf pack %s: %d wolves at %s, hunger %.2f" % [plan["id"], members.size(), at, hunger])
	return pack


func _physics_process(delta: float) -> void:
	if packs.is_empty():
		return
	for pid: Variant in packs.keys():
		var pack: WolfPack = packs[pid]
		if pack.alive().is_empty():
			packs.erase(pid)
			spent[pid] = true
			continue
		pack.tick(delta, self)
	_check_t -= delta
	if _check_t <= 0.0:
		_check_t = 0.5
		_check()


## Fires for the night, and packs that are gone, off or out of range.
func _check() -> void:
	var off: bool = not enabled() or (manager != null and not bool(manager.call(&"enabled")))
	var p: Node3D = player()
	var range_m: float = float(WolfPack.section("spawn").get("despawn", 270.0))
	if manager != null and bool(manager.get(&"silent")):
		range_m = minf(range_m, 90.0)  # a Hum night: the woods empty, the wolves too
	for pid: Variant in packs.keys():
		var pack: WolfPack = packs[pid]
		var far: bool = p != null
		for m: Enemy in pack.alive():
			if p == null or m.global_position.distance_to(p.global_position) <= range_m:
				far = false
		if off or far:
			drop(pid)
			continue
		pack.fires = fires_near(pack.centre(), 140.0) if is_night() else []


func drop(plan_id: Variant) -> void:
	var pack: WolfPack = packs.get(plan_id)
	packs.erase(plan_id)
	if pack == null:
		return
	for m: Enemy in pack.alive():
		if ai != null and ai.has_method(&"despawn"):
			ai.call(&"despawn", m)
		else:
			m.queue_free()


func clear() -> void:
	for pid: Variant in packs.keys():
		drop(pid)


# --- The world, as a pack sees it ---------------------------------------------------------------

func player() -> Node3D:
	var w: Node = Game.world if Game.world != null else world
	return w.get(&"player") as Node3D if w != null else null


func player_alive() -> bool:
	var p: Player = player() as Player
	return p != null and p.state != null and p.state.stats.alive and not DebugTools.is_on(&"invisible")


func player_bleeding() -> float:
	var p: Player = player() as Player
	return p.state.stats.bleeding if p != null and p.state != null else 0.0


## Game hours since the world began.
func hours() -> float:
	return Game.session.clock.total_minutes / 60.0 if Game.session != null else 0.0


func is_night() -> bool:
	return Game.session != null and Game.session.clock.is_night()


func period() -> String:
	if Game.session == null:
		return "day"
	var c: WorldClock = Game.session.clock
	return WildlifeSpawner.period_of(c.hour_f(), c.sunrise_hour, c.sunset_hour)


func scent_at(pos: Vector3) -> float:
	return Stimuli.current.scent_at(pos) if Stimuli.current != null else 0.0


func scent_gradient(pos: Vector3) -> Vector3:
	return Stimuli.current.scent_gradient(pos) if Stimuli.current != null else Vector3.ZERO


## The nearest living grazer (a deer, not a hare: min_health) the WildlifeManager has within r.
func nearest_prey(pos: Vector3, r: float, min_health: float) -> Node:
	if manager == null:
		return null
	var best: Node = null
	var best_d: float = r
	for a: Variant in (manager.get(&"animals") as Dictionary).values():
		if not (a is Animal) or not is_instance_valid(a):
			continue
		var an: Animal = a
		if not an.is_alive() or an.def.wkind != "grazer" or an.def.health < min_health:
			continue
		var d: float = an.global_position.distance_to(pos)
		if d < best_d:
			best = an
			best_d = d
	return best


## Lit fires and stations within r of pos (StructurePiece.lit): [{pos, r}]; a campfire keeps the
## wolves fire.radius off, another lit station fire.station_radius.
func fires_near(pos: Vector3, r: float) -> Array:
	var out: Array = []
	var w: Node = Game.world if Game.world != null else world
	var b: Node = w.get(&"building") as Node if w != null else null
	if b == null or not b.has_method(&"pieces_in_radius"):
		return out
	var f: Dictionary = WolfPack.section("fire")
	for piece: Variant in b.call(&"pieces_in_radius", pos, r):
		if not (piece is Node3D) or not bool((piece as Node3D).get(&"lit")):
			continue
		var camp: bool = (piece as Node3D).has_method(&"station_id") and String((piece as Node3D).call(&"station_id")) == "campfire"
		out.append({"pos": (piece as Node3D).global_position, "r": float(f.get("radius" if camp else "station_radius", 9.0))})
	return out


## A howl that carries through the woods: a sound, never a stimulus (no Hollowed, no heat).
func play_howl(m: Enemy) -> void:
	if m.wolf != null:
		m.wolf.hold(m.visual.clip_length(&"scream", 2.0) if m.visual != null else 2.0)
	Audio.play_3d(&"voice/wolf_howl", m._mouth(), {"volume_db": 6.0, "max_distance": float(WolfPack.section("howl").get("audible", 320.0)),
		"occlusion": false})
	SoundCaptions.say(SoundCaptions.cell_key("wolves", m.global_position), "wolves howling", m.global_position)


func _height(p: Vector3) -> float:
	return float(manager.call(&"height_at", p.x, p.z)) if manager != null and manager.has_method(&"height_at") else p.y
