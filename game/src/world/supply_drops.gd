class_name SupplyDrops
extends Node3D
## Remand Program supply drops (our take on the 7 Days airdrop). On the schedule the world
## setting `supply_drops` picks (at dawn after each Hum, weekly, every third day, or never) a
## Program drone releases a canister under a drogue chute a few hundred metres from the player.
## It lands with a hissing flare and a smoke column (which the Hollowed nearby hear too) and holds
## a `supply_drop` container whose loot tier rises with the gamestage. With the world setting
## `supply_drop_markers` the tether marks it. The spot and the loot are deterministic (world seed
## + drop id). Drops persist in WorldState.drops until they have been emptied and left behind.

const RELEASE_HEIGHT: float = 110.0
const FALL_SPEED: float = 5.5
const MIN_DIST: float = 110.0
const MAX_DIST: float = 300.0
## Hour of day the scheduled (non-Hum) drops arrive.
const DROP_HOUR: int = 12
## How far the landing is heard (Stimuli loudness, metres).
const LANDING_NOISE: float = 45.0
const FLARE_COLOR := Color(1.0, 0.3, 0.16)

var world: Node
## drop id -> Drop node
var drops: Dictionary = {}
var _check_t: float = 0.0


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
	_spawn(id, at, tier, false)
	Events.supply_drop_incoming.emit(id, at)
	return id


## A dry, fairly flat spot MIN..MAX_DIST from `center`, inside the detailed map and clear of
## buildings, chosen deterministically from the world seed and `key` (later attempts move closer).
func pick_spot(center: Vector3, key: String) -> Vector3:
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
	return true


func _spawn(id: StringName, ground: Vector3, tier: int, landed: bool) -> Drop:
	var d := Drop.new()
	d.name = String(id)
	d.drop_id = id
	d.ground = ground
	d.tier = tier
	d.landed = landed
	add_child(d)
	drops[id] = d
	return d


## Drop positions for the tether (empty when the world setting hides them).
func markers() -> Array[Vector3]:
	var out: Array[Vector3] = []
	if not GameRules.current().flag("supply_drop_markers"):
		return out
	for d: Drop in drops.values():
		if is_instance_valid(d) and not d.emptied():
			out.append(d.ground)
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


## One canister: falls under its chute, lands, burns a flare beside it until it is searched.
class Drop:
	extends Node3D
	var drop_id: StringName = &""
	var ground := Vector3.ZERO
	var tier: int = 2
	var landed: bool = false
	var crate: PoiPieces.LootProp
	var _chute: Node3D
	var _flare: FlickerLight
	var _smoke: CPUParticles3D
	var _hiss: AudioStreamPlayer3D
	var _sway: float = 0.0
	var _fade: float = 1.0

	func _ready() -> void:
		crate = PoiPieces.LootProp.new()
		crate.cdef = Content.get_def(&"container", &"supply_drop") as ContainerDef
		crate.container_id = StringName("supply:%s" % drop_id)
		crate.tier = tier
		crate.respawns = false
		var mi := MeshInstance3D.new()
		mi.mesh = ModelLibrary.mesh("items/supply_canister", "box")
		crate.add_child(mi)
		var aabb: AABB = mi.mesh.get_aabb()
		var cs := CollisionShape3D.new()
		var box := BoxShape3D.new()
		box.size = aabb.size.max(Vector3(0.3, 0.3, 0.3))
		cs.shape = box
		cs.position = aabb.get_center()
		crate.add_child(cs)
		add_child(crate)
		if landed:
			global_position = ground
			_land(true)
		else:
			global_position = ground + Vector3.UP * SupplyDrops.RELEASE_HEIGHT
			_chute = _make_chute(aabb.size.y)
			add_child(_chute)

	func emptied() -> bool:
		return crate != null and crate.opened and (crate.inventory == null or crate.inventory.stacks.is_empty())

	func _process(delta: float) -> void:
		if not landed:
			_sway += delta
			var y: float = global_position.y - SupplyDrops.FALL_SPEED * delta
			global_position = Vector3(ground.x + sin(_sway * 0.7) * 0.6, maxf(ground.y, y), ground.z + cos(_sway * 0.5) * 0.6)
			crate.rotation.z = sin(_sway * 1.3) * 0.08
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
		grow.add_point(Vector2(0.0, 0.4))
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
