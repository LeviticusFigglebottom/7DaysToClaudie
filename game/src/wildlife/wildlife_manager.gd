class_name WildlifeManager
extends Node3D
## The living forest (ADR-0027): deer, hares and bird flocks spawned deterministically round the
## player from data/wildlife (WildlifeSpawner plans per 128 m cell, day and time of day), dropped
## again when the player is far, and silenced on a Hum night: the evening before the Hum the
## animals bolt and the birds leave, and nothing comes back until morning.
##
## It is also their senses (one context per frame: the player's visibility, the wind, awake
## Hollowed, the loudest recent sound) and the authority for butchering (`wildlife.butcher`).
## Nothing is saved: the plans re-roll the same, minus what this session has killed; a carcass
## left behind is gone after a reload (TD-065).

const GRAZER_RING := Vector2(70.0, 230.0)
const FLOCK_RING := Vector2(30.0, 160.0)
const GRAZER_DESPAWN: float = 270.0
const FLOCK_DESPAWN: float = 200.0
const TICK: float = 1.0
## The valley falls silent this many hours before the Hum.
const SILENCE_HOURS: float = 2.0
const BUTCHER_REACH: float = 3.5

var world: Node = null
var animals: Dictionary = {}
var flocks: Dictionary = {}
## Plan id -> how many of that band were killed this session (they don't come back).
var taken: Dictionary = {}
var silent: bool = false

var _tick_t: float = 0.0
var _ctx_frame: int = -1
var _ctx: Dictionary = {}
var _seen_seq: int = 0
var _loud: Array[Dictionary] = []
var _flock_check_t: float = 0.0


func setup_world(w: Node) -> void:
	world = w
	Game.register_command(&"wildlife.butcher", _butcher)
	# A region's 1 m terrain answers sample() differently from its coarse one: plan again.
	var tm: Node = (w.get(&"terrain") as Node) if w != null else null
	if tm != null and tm.has_signal(&"region_attached"):
		tm.connect(&"region_attached", _on_regions_changed)
		tm.connect(&"region_detached", _on_regions_changed)


func _on_regions_changed(_rid: String) -> void:
	_plan_cache.clear()


# --- Plans, cached per cell -------------------------------------------------------------------

## "cx:cz:day:period:density" -> the cell's plans (WildlifeSpawner.plan_cell is pure for a given
## world). Planning every cell round the player every tick sampled the terrain ~200 times a
## second and spiked to 0.4 s in a streamed world; now a cell is planned once, a few a tick.
var _plan_cache: Dictionary = {}
## New cells planned per tick at most (the ring is ~25 cells; it fills over a few seconds).
const PLAN_CELLS_PER_TICK: int = 4


func _plans_near(center: Vector2, radius: float, day: int, period: String, defs: Array, density: float) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var c0: Vector2i = WildlifeSpawner.cell_of(center - Vector2(radius, radius))
	var c1: Vector2i = WildlifeSpawner.cell_of(center + Vector2(radius, radius))
	var budget: int = PLAN_CELLS_PER_TICK
	var keep: Dictionary = {}
	for cz: int in range(c0.y, c1.y + 1):
		for cx: int in range(c0.x, c1.x + 1):
			var key: String = "%d:%d:%d:%s:%s" % [cx, cz, day, period, density]
			if not _plan_cache.has(key):
				if budget <= 0:
					continue
				budget -= 1
				_plan_cache[key] = WildlifeSpawner.plan_cell(Game.session.world_seed, Vector2i(cx, cz), day, period, defs, sample, density)
			keep[key] = _plan_cache[key]
			for p: Dictionary in _plan_cache[key]:
				if (p["pos"] as Vector2).distance_to(center) <= radius:
					out.append(p)
	_plan_cache = keep
	return out


func _exit_tree() -> void:
	Game.unregister_command(&"wildlife.butcher")


func enabled() -> bool:
	return GameRules.current().flag("wildlife")


# --- World queries (animals and flocks call these) ------------------------------------------

func height_at(x: float, z: float) -> float:
	return float(world.call(&"height_at", x, z)) if world != null else 0.0


## Dry, gentle ground outside buildings, inside the map.
func walkable(p: Vector3) -> bool:
	if world == null:
		return true
	var terrain: Node = world.get(&"terrain")
	if terrain == null or terrain.call(&"region_terrain_at", p.x, p.z) == null:
		return false
	var wsys: Node = world.get(&"water")
	if wsys != null and wsys.has_method(&"depth_at"):
		p.y = height_at(p.x, p.z)
		if float(wsys.call(&"depth_at", p)) > 0.25:
			return false
	var e: float = 1.0
	var slope: float = Vector2(height_at(p.x + e, p.z) - height_at(p.x - e, p.z), height_at(p.x, p.z + e) - height_at(p.x, p.z - e)).length() / (2.0 * e)
	if slope > 0.9:
		return false
	var pois: Node = world.get(&"pois")
	if pois != null and pois.has_method(&"poi_at") and pois.call(&"poi_at", Vector3(p.x, height_at(p.x, p.z) + 1.0, p.z)) != null:
		return false
	return true


## The world as WildlifeSpawner samples it.
func sample(pos: Vector2) -> Dictionary:
	var terrain: Node = world.get(&"terrain") if world != null else null
	if terrain == null:
		return {"ok": false}
	var rt: RegionTerrain = terrain.call(&"region_terrain_at", pos.x, pos.y) as RegionTerrain
	if rt == null:
		return {"ok": false}
	var biome: String = rt.biome_at(pos.x, pos.y)
	var edge: bool = false
	for o: Vector2 in [Vector2(40, 0), Vector2(-40, 0), Vector2(0, 40), Vector2(0, -40)]:
		var rt2: RegionTerrain = terrain.call(&"region_terrain_at", pos.x + o.x, pos.y + o.y) as RegionTerrain
		if rt2 != null and rt2.biome_at(pos.x + o.x, pos.y + o.y) != biome:
			edge = true
			break
	return {"biome": biome, "edge": edge, "ok": walkable(Vector3(pos.x, 0.0, pos.y))}


## What the animals perceive this frame (shared by all of them).
func senses_context(_who: Node = null) -> Dictionary:
	var f: int = Engine.get_physics_frames()
	if f == _ctx_frame:
		return _ctx
	_ctx_frame = f
	_ctx = {"silence": silent}
	var st: Stimuli = Stimuli.current
	if st != null:
		_ctx["wind"] = st.wind
		_ctx["wind_strength"] = st.wind_strength
		_collect_loud(st)
		if not _loud.is_empty():
			_ctx["loud"] = _loud.back()
	if Game.session != null:
		_ctx["night"] = Game.session.clock.is_night()
	var p: Player = world.get(&"player") as Player if world != null else null
	if p != null and p.state != null and p.state.stats.alive and not DebugTools.is_on(&"invisible"):
		var light: float = st.light_at(p.global_position + Vector3.UP) if st != null else 1.0
		var own: bool = p.get_node(^"Equipment").call(&"has_light_on") if p.has_node(^"Equipment") else false
		var vis: float = st.detection_range(1.0, light, p.crouching, p.horizontal_speed(), own, p.state.progression.modifier("visibility_mult")) if st != null else 1.0
		_ctx["person"] = {"pos": p.global_position, "visibility": clampf(vis, 0.05, 1.25), "crouched": p.crouching,
			"speed": p.horizontal_speed()}
	var hol: Array[Vector3] = []
	var ai: Node = world.get(&"ai") if world != null else null
	if ai != null and ai.has_method(&"enemies_in_radius") and p != null:
		for e: Enemy in ai.call(&"enemies_in_radius", p.global_position, GRAZER_DESPAWN):
			if e.is_alive() and e.state != Enemy.State.SLEEP:
				hol.append(e.global_position)
	_ctx["hollowed"] = hol
	return _ctx


## Loud sounds of the last couple of seconds that weren't made by the wildlife itself.
func _collect_loud(st: Stimuli) -> void:
	for e: Stimuli.SoundEvent in st.sounds:
		if e.seq <= _seen_seq:
			continue
		if e.kind in [&"bird_flush", &"wildlife_alarm", &"murmur"] or e.loudness < 10.0:
			continue
		_loud.append({"pos": e.pos, "loudness": e.loudness, "time": st.now(), "kind": e.kind})
	_seen_seq = st.last_seq()
	while not _loud.is_empty() and st.now() - float(_loud[0]["time"]) > 1.5:
		_loud.pop_front()


## Perch points for a flock of `n` near `spot`: tree crowns for canopy birds, open ground otherwise.
func perches_for(d: WildlifeDef, spot: Vector3, n: int, p_seed: int) -> Array[Vector3]:
	var rng := RandomNumberGenerator.new()
	rng.seed = p_seed
	var out: Array[Vector3] = []
	if d.perch == "canopy":
		var veg: Node = world.get(&"vegetation") if world != null else null
		var trees: Array = []
		if veg != null and veg.has_method(&"instances_near"):
			for pair: Array in veg.call(&"instances_near", spot, 22.0):
				var inst: VegetationScatter.Instance = pair[1]
				var sp := Content.get_def(&"species", inst.species) as SpeciesDef
				if sp != null and sp.veg_kind == "tree":
					trees.append(inst)
				if trees.size() >= 4:
					break
		if trees.is_empty():
			return out
		for i: int in n:
			var inst: VegetationScatter.Instance = trees[i % trees.size()]
			var sp := Content.get_def(&"species", inst.species) as SpeciesDef
			var h: float = clampf(inst.scale * lerpf(sp.height_range.x, sp.height_range.y, 0.5), 6.0, 26.0)
			var a: float = rng.randf() * TAU
			out.append(inst.pos + Vector3(cos(a) * rng.randf_range(0.6, 2.2), h * rng.randf_range(0.45, 0.75), sin(a) * rng.randf_range(0.6, 2.2)))
		return out
	for i: int in n:
		for k: int in 6:
			var p := spot + Vector3(rng.randf_range(-3.5, 3.5), 0.0, rng.randf_range(-3.5, 3.5))
			if walkable(p):
				p.y = height_at(p.x, p.z)
				out.append(p)
				break
	return out


# --- Population ---------------------------------------------------------------------------------

func _process(delta: float) -> void:
	var t0: int = Time.get_ticks_usec()
	_process_body(delta)
	StreamMeter.note("wildlife", t0)


func _process_body(delta: float) -> void:
	if world == null or not bool(world.get(&"is_ready")):
		return
	_flock_check_t -= delta
	if _flock_check_t <= 0.0:
		_flock_check_t = 0.25
		_check_flocks()
	_tick_t -= delta
	if _tick_t > 0.0:
		return
	_tick_t = TICK
	var p: Player = world.get(&"player") as Player
	if p == null:
		return
	if not enabled():
		_clear()
		return
	var clock: WorldClock = Game.session.clock
	var was: bool = silent
	silent = silence_due(clock)
	if silent and not was:
		for fv: Variant in flocks.values():
			if is_instance_valid(fv):
				(fv as BirdFlock).leave(p.global_position)
	_despawn(p.global_position)
	if silent:
		return
	var period: String = WildlifeSpawner.period_of(clock.hour_f(), clock.sunrise_hour, clock.sunset_hour)
	var defs: Array = Content.all(&"wildlife")
	var center := Vector2(p.global_position.x, p.global_position.z)
	var plans: Array[Dictionary] = _plans_near(center, GRAZER_RING.y, clock.day(), period, defs, GameRules.current().num("wildlife_density"))
	for plan: Dictionary in plans:
		var id: StringName = plan["id"]
		if animals_of(id) > 0 or flocks.has(id):
			continue
		var d := Content.get_def(&"wildlife", plan["def"]) as WildlifeDef
		var dist: float = (plan["pos"] as Vector2).distance_to(center)
		var ring: Vector2 = GRAZER_RING if d.wkind == "grazer" else FLOCK_RING
		if dist < ring.x or dist > ring.y:
			continue
		if d.wkind == "grazer":
			spawn_band(d, plan, clock.is_night())
		else:
			spawn_flock(d, plan)


## The valley falls silent on a Hum night: from SILENCE_HOURS before it until it ends.
static func silence_due(clock: WorldClock) -> bool:
	return clock.is_horde_active() or clock.hours_until_horde() <= SILENCE_HOURS


func animals_of(plan_id: StringName) -> int:
	var n: int = 0
	var prefix: String = String(plan_id) + "#"
	for id: StringName in animals.keys():
		if String(id).begins_with(prefix) and is_instance_valid(animals[id]):
			n += 1
	return n


## A band from a plan: members round its spot, the first the leader.
func spawn_band(d: WildlifeDef, plan: Dictionary, bedded: bool = false) -> Array:
	var rng := RandomNumberGenerator.new()
	rng.seed = int(plan["seed"])
	var herd: Array = []
	var gone: int = int(taken.get(plan["id"], 0))
	var at: Vector2 = plan["pos"]
	var yaw: float = rng.randf() * TAU
	for i: int in int(plan["count"]):
		var seed_i: int = int(rng.randi())
		var off := Vector2(rng.randf_range(-4.0, 4.0), rng.randf_range(-4.0, 4.0)) if i > 0 else Vector2.ZERO
		if i < gone:
			continue
		var pos := Vector3(at.x + off.x, 0.0, at.y + off.y)
		if not walkable(pos):
			continue
		pos.y = height_at(pos.x, pos.z)
		var a := Animal.new()
		a.setup(StringName("%s#%d" % [plan["id"], i]), d, self, {"seed": seed_i, "bedded": bedded and d.beds_at_night})
		a.name = String(a.entity_id).replace(":", "_").replace("#", "_")
		a.position = pos
		a.rotation.y = yaw + rng.randf_range(-0.6, 0.6)
		add_child(a)
		a.died.connect(_on_animal_died)
		animals[a.entity_id] = a
		herd.append(a)
	for a: Animal in herd:
		a.herd = herd
	return herd


func spawn_flock(d: WildlifeDef, plan: Dictionary) -> BirdFlock:
	var at: Vector2 = plan["pos"]
	var spot := Vector3(at.x, height_at(at.x, at.y), at.y)
	var perches: Array[Vector3] = perches_for(d, spot, int(plan["count"]), int(plan["seed"]))
	if perches.size() < int(plan["count"]):
		return null
	var f := BirdFlock.new()
	f.setup(plan["id"], d, self, perches, int(plan["seed"]))
	f.name = String(plan["id"]).replace(":", "_")
	# the node sits on its perches: the MultiMeshes' bounds are drawn round it
	f.position = to_local(spot) if is_inside_tree() else spot
	add_child(f)
	flocks[f.flock_id] = f
	return f


func _on_animal_died(a: Animal) -> void:
	var plan: String = String(a.entity_id).get_slice("#", 0)
	taken[StringName(plan)] = int(taken.get(StringName(plan), 0)) + 1


func _despawn(ppos: Vector3) -> void:
	for id: StringName in animals.keys():
		if not is_instance_valid(animals[id]):
			animals.erase(id)
			continue
		var a: Animal = animals[id]
		var d: float = Vector2(a.global_position.x - ppos.x, a.global_position.z - ppos.z).length()
		var rotted: bool = not a.is_alive() and a.carcass_age() > float(a.def.carcass.get("lifetime", 600.0))
		if d > GRAZER_DESPAWN or rotted or (silent and a.is_alive() and d > 90.0):
			animals.erase(id)
			a.queue_free()
	for id: StringName in flocks.keys():
		if not is_instance_valid(flocks[id]):
			flocks.erase(id)
			continue
		var f: BirdFlock = flocks[id]
		var c: Vector3 = f.center()
		if f.state == BirdFlock.State.GONE or Vector2(c.x - ppos.x, c.z - ppos.z).length() > FLOCK_DESPAWN:
			flocks.erase(id)
			f.queue_free()


func _check_flocks() -> void:
	if flocks.is_empty():
		return
	var ctx: Dictionary = senses_context()
	var people: Array = []
	if ctx.has("person"):
		people.append(ctx["person"])
	_check_murmurs(ctx)
	for fv: Variant in flocks.values():
		if not is_instance_valid(fv) or not (fv as BirdFlock).is_perched():
			continue
		var f: BirdFlock = fv
		var c: Vector3 = f.center()
		var cause: String = WildlifeBrain.flush_cause(f.def, c, people, ctx.get("hollowed", [] as Array[Vector3]), ctx.get("loud", {}))
		if cause != "":
			var from: Vector3 = c
			match cause:
				"person":
					from = (people[0] as Dictionary)["pos"]
				"noise":
					from = (ctx["loud"] as Dictionary)["pos"]
				"hollowed":
					from = _nearest(c, ctx.get("hollowed", [] as Array[Vector3]))
			f.flush(from, cause)
			if cause == "person" and murmur_rolls(f, from):
				f.start_murmur(from)


# --- Murmurs (ADR-0034) -------------------------------------------------------------------------

## Whether a crow flock just flushed by the player turns into a Murmur: the world setting, the
## flock's own `murmur` tuning, the gamestage, and more often where the Bloom lies thick. Rolled on
## the flock's flush count, so the same flush of the same flock in the same world decides the same.
func murmur_rolls(f: BirdFlock, at: Vector3) -> bool:
	var m: Dictionary = f.def.murmur
	if m.is_empty() or not GameRules.current().flag("murmurs") or Game.session == null:
		return false
	if Game.session.clock.is_night() or silent:
		return false
	if Game.session.gamestage(Game.local_player()) < int(m.get("gamestage_min", 0)):
		return false
	var chance: float = float(m.get("chance", 0.2))
	var terrain: Node = world.get(&"terrain") if world != null else null
	if terrain != null and terrain.has_method(&"bloom_at"):
		chance = lerpf(chance, float(m.get("bloom_chance", chance)), clampf(float(terrain.call(&"bloom_at", at.x, at.z)), 0.0, 1.0))
	var rng := RandomNumberGenerator.new()
	rng.seed = Ids.hash64("murmur:%d:%s:%d" % [Game.session.world_seed, f.flock_id, f.flush_count])
	return rng.randf() < chance


## Murmurs follow the player: where they are now, and whether they are under cover. One breaks up at
## a gunshot or explosion close by, at nightfall, on a Hum night, or once the player is lost to it.
func _check_murmurs(ctx: Dictionary) -> void:
	var person: Dictionary = ctx.get("person", {})
	var loud: Dictionary = ctx.get("loud", {})
	for fv: Variant in flocks.values():
		if not is_instance_valid(fv) or not (fv as BirdFlock).is_murmur():
			continue
		var f: BirdFlock = fv
		var m: Dictionary = f.def.murmur
		if silent:
			f.end_murmur("hum")
		elif bool(ctx.get("night", false)):
			f.end_murmur("night")
		elif person.is_empty():
			f.end_murmur("lost")
		elif not loud.is_empty() and (m.get("scatter_kinds", ["gunshot", "explosion"]) as Array).has(String(loud.get("kind", ""))) \
				and (loud["pos"] as Vector3).distance_to(f.center()) <= float(m.get("scatter_radius", 35.0)):
			f.end_murmur("scattered")
		else:
			var p: Vector3 = person["pos"]
			f.murmur_update(p, under_cover(p), 0.25)


## Whether the crows can lose sight of someone here: a roof, a floor above, or the canopy overhead.
func under_cover(p: Vector3) -> bool:
	if not is_inside_tree():
		return false
	var space: PhysicsDirectSpaceState3D = get_world_3d().direct_space_state
	var from: Vector3 = p + Vector3.UP * 1.8
	var q := PhysicsRayQueryParameters3D.create(from, from + Vector3.UP * 25.0, (1 << 0) | (1 << 1) | (1 << 2) | (1 << 12))
	var pl: Node = world.get(&"player") as Node if world != null else null
	if pl is CollisionObject3D:
		q.exclude = [(pl as CollisionObject3D).get_rid()]
	return not space.intersect_ray(q).is_empty()


static func _nearest(c: Vector3, pts: Array[Vector3]) -> Vector3:
	var best := c
	var bd: float = INF
	for p: Vector3 in pts:
		if p.distance_squared_to(c) < bd:
			bd = p.distance_squared_to(c)
			best = p
	return best


func _clear() -> void:
	for a: Variant in animals.values():
		if is_instance_valid(a):
			(a as Node).queue_free()
	for f: Variant in flocks.values():
		if is_instance_valid(f):
			(f as Node).queue_free()
	animals.clear()
	flocks.clear()


# --- Butchering ---------------------------------------------------------------------------------

## The tool a player would butcher with: the one in hand if it cuts, else the first knife or axe
## carried (&"" = none). The carcass def lists the tool kinds that work.
static func butcher_tool(p: PlayerState, d: WildlifeDef) -> StringName:
	var kinds: Array = d.carcass.get("tools", ["knife", "axe"])
	var held: ItemDef = Content.item(p.equipped_item())
	if held != null:
		for k: Variant in kinds:
			if held.provides_tool(str(k)):
				return held.id
	for s: ItemStack in p.inventory.stacks:
		var def: ItemDef = Content.item(s.item_id)
		if def == null:
			continue
		for k: Variant in kinds:
			if def.provides_tool(str(k)):
				return def.id
	return &""


## What a carcass gives: deterministic per animal and world seed. An axe hacks the carcass apart:
## a strand of sinew less than a knife's clean work.
static func butcher_yields(d: WildlifeDef, animal_id: StringName, world_seed: int, tool_id: StringName) -> Dictionary:
	var rng := RandomNumberGenerator.new()
	rng.seed = Ids.hash64("butcher:%d:%s" % [world_seed, animal_id])
	var out: Dictionary = {}
	var ys: Dictionary = d.carcass.get("yields", {})
	var keys: Array = ys.keys()
	keys.sort()
	var axe: bool = Content.item(tool_id) != null and Content.item(tool_id).provides_tool("axe") \
		and not Content.item(tool_id).provides_tool("knife")
	for k: Variant in keys:
		var r: Array = ys[k]
		var n: int = rng.randi_range(int(r[0]), int(r[1]))
		if axe and str(k) == "sinew":
			n = maxi(0, n - 1)
		if n > 0:
			out[str(k)] = n
	return out


func _butcher(args: Dictionary) -> Dictionary:
	var p: PlayerState = Game.session.players.get(StringName(str(args.get("player", Game.session.local_player_id)))) if Game.session != null else null
	if p == null:
		return {"ok": false, "error": "no player"}
	var a: Animal = animals.get(StringName(str(args.get("animal", ""))))
	if a == null or not is_instance_valid(a):
		return {"ok": false, "error": "Nothing to butcher"}
	if a.is_alive():
		return {"ok": false, "error": "It's still alive"}
	if a.butchered:
		return {"ok": false, "error": "Already butchered"}
	if p.position.distance_to(a.global_position) > BUTCHER_REACH:
		return {"ok": false, "error": "Too far away"}
	var tool: StringName = butcher_tool(p, a.def)
	if tool == &"":
		return {"ok": false, "error": "You need a knife or an axe"}
	var items: Dictionary = butcher_yields(a.def, a.entity_id, Game.session.world_seed, tool)
	for k: String in items:
		var left: int = p.inventory.add_item(StringName(k), int(items[k]))
		if left > 0 and world != null and world.get(&"loose") != null:
			world.get(&"loose").call(&"spawn_item", ItemStack.make(StringName(k), left), a.global_position + Vector3.UP * 0.4)
	a.mark_butchered()
	p.progression.award("butcher")
	Audio.play_3d(&"sfx/butcher_cut", a.global_position + Vector3.UP * 0.3, {"volume_db": -2.0})
	# wet work is not silent, and the opened carcass reeks
	if Stimuli.current != null:
		Stimuli.current.emit_sound(a.global_position, 10.0, &"butcher", p.id)
		Stimuli.current.deposit_scent(a.global_position, float(a.def.carcass.get("scent", 2.0)) * 6.0)
	Events.inventory_changed.emit(p.id)
	Events.wildlife_butchered.emit(p.id, a.def.id, items)
	return {"ok": true, "items": items, "tool": String(tool)}
