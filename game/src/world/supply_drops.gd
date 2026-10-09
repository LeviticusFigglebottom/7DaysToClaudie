class_name SupplyDrops
extends Node3D
## Remand Program supply drops (our take on the 7 Days airdrop). On the schedule the world
## setting `supply_drops` picks (at dawn after each Hum, weekly, every third day, or never) the
## Program's heavy-lift drone (ProgramDrone, ADR-0023) flies in, hovers over a spot a few hundred
## metres from the player and lets a canister go under a drogue chute; its racket and the landing
## carry to the Hollowed nearby. The canister lands with a hissing flare and a smoke column and
## holds a `supply_drop` container whose loot tier rises with the gamestage. With the world setting
## `supply_drop_markers` the tether marks and lists every drop. The spot, the drone's bearing and the
## loot are deterministic (world seed + drop id); the spot is dry, fairly flat, off the buildings and
## clear of trees and player structures. Drops persist in WorldState.drops until they have been
## emptied and left behind.

const RELEASE_HEIGHT: float = 110.0
const FALL_SPEED: float = 5.5
const MIN_DIST: float = 110.0
const MAX_DIST: float = 300.0
## Hour of day the scheduled (non-Hum) drops arrive.
const DROP_HOUR: int = 12
## How far the landing is heard (Stimuli loudness, metres).
const LANDING_NOISE: float = 45.0
const FLARE_COLOR := Color(1.0, 0.3, 0.16)
## The canister's size (diameter, height): its stand-in and the least its search box covers.
const CANISTER := Vector2(0.58, 1.1)
## Within this many metres of the camera the smoke's puffs fade out (5 m more to full).
const SMOKE_CLEAR_M: float = 2.5

var world: Node
## drop id -> Drop node
var drops: Dictionary = {}
## (p: Vector3, r: float) -> [{"pos", "radius"}]: replaces the scatter as the landing check's tree
## source (tests).
var tree_source: Callable = Callable()
var _check_t: float = 0.0
## Chunk -> its collidable trees, for one pick_spot() (the scatter is deterministic; felled trees
## can change between drops).
var _tree_cache: Dictionary = {}


func setup_world(w: Node) -> void:
	world = w
	Events.hour_changed.connect(_on_hour)
	Events.horde_night_ended.connect(_on_hum_ended)
	var saved: Dictionary = Game.session.world.drops
	for id: Variant in saved.keys():
		var e: Dictionary = saved[id]
		var p: Array = e.get("pos", [0, 0, 0])
		_spawn(StringName(str(id)), Vector3(float(p[0]), float(p[1]), float(p[2])), int(e.get("tier", 2)), true)


## Days between scheduled drops for a `supply_drops` setting (0 = not on a day schedule).
static func interval_days(mode: String) -> int:
	match mode:
		"weekly":
			return 7
		"every_3_days":
			return 3
	return 0


## Loot tier of a drop at this gamestage: 2 at the start, 5 from gamestage 75.
static func tier_for(gamestage: int) -> int:
	return clampi(2 + gamestage / 25, 2, 5)


func _on_hour(day: int, hour: int) -> void:
	var n: int = interval_days(GameRules.current().choice("supply_drops"))
	if n > 0 and hour == DROP_HOUR and day % n == 0:
		dispatch(day)


func _on_hum_ended(day: int, _report: Dictionary) -> void:
	if GameRules.current().choice("supply_drops") == "after_hum":
		dispatch(day)


## Sends the drop for `day` (at most one per day). Returns its id, or &"" when none was sent.
func dispatch(day: int) -> StringName:
	var flags: Dictionary = Game.session.world.flags
	if world == null or world.player == null or int(flags.get("last_drop_day", -1)) == day:
		return &""
	flags["last_drop_day"] = day
	var id := StringName("drop_%d" % day)
	var at: Vector3 = pick_spot((world.player as Node3D).global_position, String(id))
	var tier: int = tier_for(Game.session.gamestage())
	Game.session.world.drops[String(id)] = {"pos": [at.x, at.y, at.z], "day": day, "tier": tier}
	var d: Drop = _spawn(id, at, tier, false, ProgramDrone.plan_flight(at, String(id), Game.session.world_seed, _cfg(), RELEASE_HEIGHT))
	var drone := ProgramDrone.new()
	drone.name = "Drone"
	drone.flight = d.flight
	drone.cfg = _cfg()
	drone.ground = at
	d.drone = drone
	d.add_child(drone)
	Events.supply_drop_incoming.emit(id, at)
	return id


func _cfg() -> Dictionary:
	return Content.config(&"program_drone")


## A dry, fairly flat spot MIN..MAX_DIST from `center`, inside the detailed map and clear of
## buildings, chosen deterministically from the world seed and `key` (later attempts move closer).
func pick_spot(center: Vector3, key: String) -> Vector3:
	_tree_cache.clear()
	var rng := RandomNumberGenerator.new()
	rng.seed = Ids.hash64("drop:%d:%s" % [Game.session.world_seed, key])
	for attempt: int in 40:
		var ang: float = rng.randf() * TAU
		var dist: float = rng.randf_range(MIN_DIST, MAX_DIST) * (1.0 - 0.6 * float(attempt) / 40.0)
		var p := Vector3(center.x + cos(ang) * dist, 0.0, center.z + sin(ang) * dist)
		if spot_ok(p):
			p.y = world.height_at(p.x, p.z)
			return p
	return Vector3(center.x, world.height_at(center.x, center.z), center.z)


func spot_ok(p: Vector3) -> bool:
	var terrain: Node = world.get(&"terrain")
	if terrain == null or terrain.call(&"region_terrain_at", p.x, p.z) == null:
		return false
	var h: float = world.height_at(p.x, p.z)
	for o: Vector2 in [Vector2(2.5, 0.0), Vector2(-2.5, 0.0), Vector2(0.0, 2.5), Vector2(0.0, -2.5)]:
		if absf(world.height_at(p.x + o.x, p.z + o.y) - h) > 1.2:
			return false
	var water: Node = world.get(&"water")
	if water != null and water.has_method(&"depth_at") and float(water.call(&"depth_at", Vector3(p.x, h, p.z))) > 0.05:
		return false
	var pois: Node = world.get(&"pois")
	if pois != null:
		for inst: PoiInstance in (pois.get(&"instances") as Dictionary).values():
			var b: AABB = inst.world_bounds().grow(12.0)
			if b.has_point(Vector3(p.x, b.get_center().y, p.z)):
				return false
		# Streamed worlds: nor by a building not built yet (RWG v2 Phase 3).
		if pois.has_method(&"footprint_at") and pois.call(&"footprint_at", p, 12.0) != &"":
			return false
	return _clear_of_obstacles(Vector3(p.x, h, p.z))


## Trees and anything solid around a landing spot (TD-029). Trees come from the deterministic
## scatter (felled ones excluded), so a spot far beyond the trees' pooled colliders is checked
## too; player structures from the building manager; and whatever else collides (rocks, props,
## structures near the player) from a physics query over the canister's footprint.
func _clear_of_obstacles(p: Vector3) -> bool:
	var tree_clear: float = float(_cfg().get("landing_tree_clearance", 4.5))
	for t: Dictionary in trees_near(p, tree_clear + 1.0):
		if Vector2(t["pos"].x - p.x, t["pos"].z - p.z).length() < tree_clear + float(t["radius"]):
			return false
	var clear: float = float(_cfg().get("landing_clearance", 3.5))
	var building: Node = world.get(&"building")
	if building != null and building.has_method(&"pieces_in_radius"):
		for piece: Variant in building.call(&"pieces_in_radius", p, clear):
			if piece is Node3D and Vector2((piece as Node3D).global_position.x - p.x, (piece as Node3D).global_position.z - p.z).length() < clear:
				return false
	if is_inside_tree() and get_world_3d() != null:
		var q := PhysicsShapeQueryParameters3D.new()
		var cyl := CylinderShape3D.new()
		cyl.radius = clear
		cyl.height = 4.0
		q.shape = cyl
		# Clear of the ground itself (layer 1 is the terrain): structures, props and vegetation.
		q.collision_mask = (1 << 1) | (1 << 2) | (1 << 12)
		q.transform = Transform3D(Basis.IDENTITY, p + Vector3.UP * 2.4)
		if not get_world_3d().direct_space_state.intersect_shape(q, 1).is_empty():
			return false
	return true


## Collidable trees within `r` of `p`: [{"pos": Vector3, "radius": trunk m}]: the vegetation
## scatter's tree layer, or `tree_source` when set (tests).
func trees_near(p: Vector3, r: float) -> Array:
	if tree_source.is_valid():
		return tree_source.call(p, r)
	var out: Array = []
	var terrain: Node = world.get(&"terrain") if world != null else null
	if terrain == null or Game.session == null:
		return out
	var c0 := Vector2i(int(floor((p.x - r) / VegetationScatter.CHUNK)), int(floor((p.z - r) / VegetationScatter.CHUNK)))
	var c1 := Vector2i(int(floor((p.x + r) / VegetationScatter.CHUNK)), int(floor((p.z + r) / VegetationScatter.CHUNK)))
	for cz: int in range(c0.y, c1.y + 1):
		for cx: int in range(c0.x, c1.x + 1):
			for t: Dictionary in _chunk_trees(terrain, Vector2i(cx, cz)):
				if Vector2(t["pos"].x - p.x, t["pos"].z - p.z).length() <= r + float(t["radius"]):
					out.append(t)
	return out


func _chunk_trees(terrain: Node, key: Vector2i) -> Array:
	if _tree_cache.has(key):
		return _tree_cache[key]
	var out: Array = []
	var rt: Variant = terrain.call(&"region_terrain_at", (key.x + 0.5) * VegetationScatter.CHUNK, (key.y + 0.5) * VegetationScatter.CHUNK)
	if rt is RegionTerrain:
		var felled: Dictionary = Game.session.world.trees.get(Ids.chunk_key(key.x, key.y), {})
		var layers: Dictionary = VegetationScatter.scatter_chunk(key, rt, Game.session.world_seed, Callable(world, &"height_at"), Callable(), 1)
		for inst: VegetationScatter.Instance in layers.get("tree", []):
			var sp: SpeciesDef = Content.get_def(&"species", inst.species) as SpeciesDef
			if sp == null or not sp.collides or felled.has(str(inst.index)):
				continue
			out.append({"pos": inst.pos, "radius": maxf(0.15, sp.trunk_radius * inst.scale)})
	_tree_cache[key] = out
	return out


func _spawn(id: StringName, ground: Vector3, tier: int, landed: bool, flight: ProgramDrone.Flight = null) -> Drop:
	var d := Drop.new()
	d.name = String(id)
	d.drop_id = id
	d.ground = ground
	d.tier = tier
	d.landed = landed
	d.flight = flight
	add_child(d)
	drops[id] = d
	return d


## Drop positions for the tether (empty when the world setting hides them).
func markers() -> Array[Vector3]:
	var out: Array[Vector3] = []
	for e: Dictionary in entries():
		out.append(e["pos"])
	return out


## Every drop not yet emptied, for the tether's list (empty when the world setting hides them):
## [{"id", "pos", "day", "state": "inbound" | "falling" | "landed" | "opened"}], in the order they came.
func entries() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	if not GameRules.current().flag("supply_drop_markers"):
		return out
	var ids: Array = drops.keys()
	ids.sort_custom(func(a: StringName, b: StringName) -> bool: return (drops[a] as Drop).day() < (drops[b] as Drop).day() or ((drops[a] as Drop).day() == (drops[b] as Drop).day() and String(a) < String(b)))
	for id: StringName in ids:
		var d: Drop = drops[id]
		if not is_instance_valid(d) or d.emptied():
			continue
		out.append({"id": id, "pos": d.ground, "day": d.day(), "state": d.state()})
	return out


func _process(delta: float) -> void:
	_check_t += delta
	if _check_t < 2.0 or world == null or world.player == null:
		return
	_check_t = 0.0
	# Emptied drops are cleared away once you have walked off.
	var pp: Vector3 = (world.player as Node3D).global_position
	for id: StringName in drops.keys():
		var d: Drop = drops[id]
		if is_instance_valid(d) and d.emptied() and d.ground.distance_to(pp) > 60.0:
			Game.session.world.drops.erase(String(id))
			Game.session.world.containers.erase(String(d.crate.container_id))
			drops.erase(id)
			d.queue_free()


## One canister: carried in under the drone, let go over the spot, falls under its chute, lands
## and burns a flare beside it until it is searched. Its clock (`_t`, seconds since dispatch)
## drives the drone too, so both follow the same flight.
class Drop:
	extends Node3D
	var drop_id: StringName = &""
	var ground := Vector3.ZERO
	var tier: int = 2
	var landed: bool = false
	## The drone's flight (null for a drop restored from a save, already down, or one dropped
	## without a drone: it then falls from RELEASE_HEIGHT straight away).
	var flight: ProgramDrone.Flight = null
	var drone: ProgramDrone = null
	var crate: PoiPieces.LootProp
	var _chute: Node3D
	var _flare: FlickerLight
	var _smoke: CPUParticles3D
	var _hiss: AudioStreamPlayer3D
	var _fade: float = 1.0
	var _t: float = 0.0
	var _height: float = 1.0

	func _ready() -> void:
		crate = PoiPieces.LootProp.new()
		crate.cdef = Content.get_def(&"container", &"supply_drop") as ContainerDef
		crate.container_id = StringName("supply:%s" % drop_id)
		crate.tier = tier
		crate.respawns = false
		var mi := MeshInstance3D.new()
		mi.mesh = ModelLibrary.generated_mesh("items/supply_canister")
		if mi.mesh == null:
			# Before `make assets`: a canister-sized olive drum standing on its base (a box
			# centred on the origin was half in the ground and under the eye's aim: W4).
			var cyl := CylinderMesh.new()
			cyl.top_radius = SupplyDrops.CANISTER.x * 0.5
			cyl.bottom_radius = SupplyDrops.CANISTER.x * 0.5
			cyl.height = SupplyDrops.CANISTER.y
			var cmat := StandardMaterial3D.new()
			cmat.albedo_color = Color(0.3, 0.33, 0.2)
			cyl.material = cmat
			mi.mesh = cyl
			mi.position.y = SupplyDrops.CANISTER.y * 0.5
		crate.add_child(mi)
		var aabb: AABB = mi.mesh.get_aabb()
		aabb.position += mi.position
		# The search box stands on the ground, at least the canister's size whatever the model,
		# so a look at it from where you stand always finds it (W4).
		var cs := CollisionShape3D.new()
		var box := BoxShape3D.new()
		box.size = aabb.size.max(Vector3(SupplyDrops.CANISTER.x, SupplyDrops.CANISTER.y, SupplyDrops.CANISTER.x))
		cs.shape = box
		cs.position = Vector3(aabb.get_center().x, maxf(aabb.position.y, 0.0) + box.size.y * 0.5, aabb.get_center().z)
		crate.add_child(cs)
		add_child(crate)
		_height = aabb.size.y
		if landed:
			global_position = ground
			_land(true)
		elif flight != null:
			global_position = flight.position(0.0) + ProgramDrone.HANG
		else:
			global_position = ground + Vector3.UP * SupplyDrops.RELEASE_HEIGHT
			_open_chute()

	func emptied() -> bool:
		return crate != null and crate.opened and (crate.inventory == null or crate.inventory.stacks.is_empty())

	## Inbound under the drone, falling under the chute, down, or down and searched.
	func state() -> String:
		if not landed:
			return "inbound" if flight != null and _t < flight.release_time() else "falling"
		return "opened" if crate != null and crate.opened else "landed"

	## Game day the drop was sent (from its id, drop_<day>).
	func day() -> int:
		return int(String(drop_id).get_slice("_", 1)) if String(drop_id).begins_with("drop_") else 0

	func _open_chute() -> void:
		if _chute == null:
			_chute = _make_chute(_height)
			add_child(_chute)

	func _process(delta: float) -> void:
		_t += delta
		if drone != null and is_instance_valid(drone):
			drone.fly(_t)
		elif drone != null:
			drone = null
		if not landed:
			var released: float = flight.release_time() if flight != null else 0.0
			if _t < released:
				# Carried: the sling sways a little under the airframe.
				global_position = flight.position(_t) + ProgramDrone.HANG
				crate.rotation.z = sin(_t * 1.9) * 0.03
				return
			_open_chute()
			var from: Vector3 = (flight.position(released) + ProgramDrone.HANG) if flight != null else ground + Vector3.UP * SupplyDrops.RELEASE_HEIGHT
			var since: float = _t - released
			# The chute takes a few seconds to drift onto the spot from where the drone let go.
			var drift: float = smoothstep(0.0, 6.0, since)
			var y: float = from.y - SupplyDrops.FALL_SPEED * since
			var x: float = lerpf(from.x, ground.x, drift) + sin(_t * 0.7) * 0.6 * drift
			var z: float = lerpf(from.z, ground.z, drift) + cos(_t * 0.5) * 0.6 * drift
			global_position = Vector3(x, maxf(ground.y, y), z)
			crate.rotation.z = sin(_t * 1.3) * 0.08
			if y <= ground.y:
				global_position = ground
				crate.rotation = Vector3.ZERO
				_land(false)
			return
		# Once searched, the flare burns down and the smoke thins out.
		if crate.opened and _fade > 0.0:
			_fade = maxf(0.0, _fade - delta / 30.0)
			if _flare != null:
				_flare.light_energy = 3.0 * _fade
			if _hiss != null:
				_hiss.volume_db = linear_to_db(maxf(_fade, 0.001)) - 6.0
			if _smoke != null:
				_smoke.emitting = _fade > 0.5
			if _fade <= 0.0:
				for n: Node in [_flare, _hiss]:
					if n != null:
						n.queue_free()
				_flare = null
				_hiss = null

	func _land(quiet: bool) -> void:
		landed = true
		if _chute != null:
			_chute.queue_free()
			_chute = null
		if crate.opened:
			_fade = 0.0
			return
		var stick := MeshInstance3D.new()
		var cm := CylinderMesh.new()
		cm.top_radius = 0.025
		cm.bottom_radius = 0.025
		cm.height = 0.3
		var sm := StandardMaterial3D.new()
		sm.albedo_color = SupplyDrops.FLARE_COLOR
		sm.emission_enabled = true
		sm.emission = SupplyDrops.FLARE_COLOR
		sm.emission_energy_multiplier = 4.0
		cm.material = sm
		stick.mesh = cm
		stick.position = Vector3(0.7, 0.1, 0.3)
		stick.rotation = Vector3(0.0, 0.0, 1.2)
		add_child(stick)
		_flare = FlickerLight.new()
		_flare.light_color = SupplyDrops.FLARE_COLOR
		_flare.light_energy = 3.0
		_flare.omni_range = 16.0
		_flare.flicker = 0.35
		_flare.speed = 16.0
		_flare.shadow_enabled = false
		_flare.position = Vector3(0.7, 0.45, 0.3)
		add_child(_flare)
		_hiss = AudioStreamPlayer3D.new()
		_hiss.stream = Audio.stream(&"sfx/flare_loop")
		_hiss.bus = &"SFX"
		_hiss.unit_size = 5.0
		_hiss.max_distance = 60.0
		_hiss.volume_db = -6.0
		_hiss.position = _flare.position
		add_child(_hiss)
		if _hiss.stream != null:
			_hiss.play()
		_smoke = _make_smoke()
		if _smoke != null:
			_smoke.position = _flare.position
			add_child(_smoke)
		if quiet:
			return
		Audio.play_3d(&"sfx/metal_clang", global_position, {"volume_db": -2.0, "pitch": 0.65})
		FxLibrary.burst(get_parent(), "dust", global_position + Vector3.UP * 0.3, Vector3.UP, 1.5)
		if Stimuli.current != null:
			Stimuli.current.emit_sound(global_position, SupplyDrops.LANDING_NOISE, &"drop", &"")
		Events.supply_drop_landed.emit(drop_id, global_position)

	## A drogue chute: an orange dome on four risers above the canister.
	func _make_chute(top: float) -> Node3D:
		var root := Node3D.new()
		var mat := StandardMaterial3D.new()
		mat.albedo_color = Color(0.85, 0.36, 0.12)
		mat.roughness = 0.9
		mat.cull_mode = BaseMaterial3D.CULL_DISABLED
		var dome := MeshInstance3D.new()
		var sm := SphereMesh.new()
		sm.radius = 1.7
		sm.height = 1.4
		sm.is_hemisphere = true
		sm.material = mat
		dome.mesh = sm
		dome.position = Vector3(0.0, top + 3.6, 0.0)
		root.add_child(dome)
		var line := StandardMaterial3D.new()
		line.albedo_color = Color(0.2, 0.2, 0.18)
		for i: int in 4:
			var a: float = TAU * (float(i) + 0.5) / 4.0
			var rim := Vector3(cos(a) * 1.6, top + 3.6, sin(a) * 1.6)
			var foot := Vector3(0.0, top, 0.0)
			var riser := MeshInstance3D.new()
			var cm := CylinderMesh.new()
			cm.top_radius = 0.008
			cm.bottom_radius = 0.008
			cm.height = rim.distance_to(foot)
			cm.material = line
			riser.mesh = cm
			var mid: Vector3 = (rim + foot) * 0.5
			riser.transform = Transform3D(Basis(Quaternion(Vector3.UP, (rim - foot).normalized())), mid)
			root.add_child(riser)
		return root

	## A tall red smoke column you can see over the trees. CPU particles: cheap at this count and
	## the same on every renderer. None when headless.
	func _make_smoke() -> CPUParticles3D:
		if DisplayServer.get_name() == "headless":
			return null
		var p := CPUParticles3D.new()
		p.amount = 48
		p.lifetime = 9.0
		# A drop found already burning (or restored from a save) has its full column.
		p.preprocess = 9.0
		p.local_coords = false
		p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		p.direction = Vector3.UP
		p.spread = 10.0
		p.initial_velocity_min = 1.8
		p.initial_velocity_max = 2.8
		p.gravity = Vector3(0.35, 0.25, 0.1)
		p.damping_min = 0.1
		p.damping_max = 0.3
		p.scale_amount_min = 1.0
		p.scale_amount_max = 1.6
		var grow := Curve.new()
		grow.max_value = 3.0
		grow.add_point(Vector2(0.0, 0.25))
		grow.add_point(Vector2(1.0, 2.6))
		p.scale_amount_curve = grow
		p.anim_speed_min = 0.6
		p.anim_speed_max = 0.9
		var fade := Gradient.new()
		fade.set_color(0, Color(1, 1, 1, 0.0))
		fade.set_color(1, Color(1, 1, 1, 0.0))
		fade.add_point(0.08, Color(1, 1, 1, 0.75))
		fade.add_point(0.6, Color(1, 1, 1, 0.4))
		p.color_ramp = fade
		var mat := StandardMaterial3D.new()
		mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		mat.shading_mode = BaseMaterial3D.SHADING_MODE_PER_PIXEL
		mat.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
		# Without this the billboard drops the per-particle scale and the puffs stay quad-sized.
		mat.billboard_keep_scale = true
		mat.vertex_color_use_as_albedo = true
		mat.albedo_color = Color(0.92, 0.42, 0.3, 0.8)
		# Clear close up (W4): within a few metres the puffs fade out, so a player at the
		# canister sees it and the crate rather than a screen of red; the column still reads from afar.
		mat.distance_fade_mode = BaseMaterial3D.DISTANCE_FADE_PIXEL_ALPHA
		mat.distance_fade_min_distance = SupplyDrops.SMOKE_CLEAR_M
		mat.distance_fade_max_distance = SupplyDrops.SMOKE_CLEAR_M + 5.0
		var tex: String = "res://assets/generated/textures/fx_smoke_flipbook.png"
		if ResourceLoader.exists(tex):
			mat.albedo_texture = load(tex)
			mat.particles_anim_h_frames = 8
			mat.particles_anim_v_frames = 8
			mat.particles_anim_loop = true
		var q := QuadMesh.new()
		q.size = Vector2(2.5, 2.5)
		q.material = mat
		p.mesh = q
		p.emitting = true
		return p
