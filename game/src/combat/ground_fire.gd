class_name GroundFire
extends Node3D
## A patch of burning ground (ADR-0057): what a shattered molotov leaves. Its numbers come from
## data/config/fire.json `ground_fires.<id>`: a disc of `radius` burns for `duration` seconds,
## then dies down over `fade`; every `tick` it hurts the Hollowed and wildlife standing in it
## (`dps`) and a player (`player_dps`) with DamageInfo type/cause fire, and every `structure_tick`
## it scorches flammable structures within radius + structure_reach through the structure damage
## API (their damage_mult.fire applies). It lights with a whoomp and crackles (Stimuli kind
## `fire`: the Hollowed come to look), and its light shows whoever stands near it to their eyes.
## Flames, embers, smoke, a flickering light and a scorch mark are procedural; the smoke and the
## scorch linger a while after it is out.
##
## Transient by design: a fire is out within seconds, so it is never saved (a save mid-burn just
## loses the flames, nothing it already burned).

const MASK: int = (1 << 1) | (1 << 3) | (1 << 4) | (1 << 9)
## A body this far outside the disc (its capsule's radius, roughly) still stands in the flames.
const BODY_PAD: float = 0.35
const FLIPBOOK: String = "res://assets/generated/textures/fx_fire_flipbook.png"

var fire_id: StringName = &"molotov"
var spec: Dictionary = {}
## Who started it (a player id): what the burned blame (horde memory, kills, XP).
var source_id: StringName = &""
## Where it was thrown from (what a burned Hollow turns toward; a burned deer runs from).
var origin := Vector3.ZERO
var radius: float = 2.4
var duration: float = 9.0
var fade: float = 2.5
var age: float = 0.0
var _tick_t: float = 0.0
var _structure_t: float = 0.0
var _crackle_t: float = 0.0
var _light: FlickerLight = null
var _fx: Array[GPUParticles3D] = []
var _smoke: GPUParticles3D = null
var _scorch: Decal = null
var _loop: AudioStreamPlayer3D = null
var _out: bool = false


## The tuning of a ground fire kind (empty if there is none).
static func spec_for(id: StringName) -> Dictionary:
	return (Content.config(&"fire").get("ground_fires", {}) as Dictionary).get(String(id), {})


## Lights a fire of kind `id` on the ground at (or under) `pos`, in `parent`. Null if the kind is
## unknown.
static func spawn(parent: Node, pos: Vector3, id: StringName, p_source: StringName = &"", p_origin := Vector3.ZERO) -> GroundFire:
	var s: Dictionary = spec_for(id)
	if parent == null or s.is_empty():
		return null
	var f := GroundFire.new()
	f.fire_id = id
	f.spec = s
	f.source_id = p_source
	f.origin = p_origin
	parent.add_child(f)
	f.global_position = ground_below(f, pos)
	return f


## Where a fire at `pos` burns: on the ground under it (a bottle that broke on a wall or a body
## spills to the ground), or at `pos` when there is no ground near.
static func ground_below(n: Node3D, pos: Vector3) -> Vector3:
	if not n.is_inside_tree():
		return pos
	var space: PhysicsDirectSpaceState3D = n.get_world_3d().direct_space_state
	var q := PhysicsRayQueryParameters3D.create(pos + Vector3.UP * 0.3, pos + Vector3.DOWN * 4.0, (1 << 0) | (1 << 1) | (1 << 2))
	var hit: Dictionary = space.intersect_ray(q)
	return hit["position"] if not hit.is_empty() else pos


func _ready() -> void:
	if spec.is_empty():
		spec = spec_for(fire_id)
	radius = float(spec.get("radius", 2.4))
	duration = float(spec.get("duration", 9.0))
	fade = float(spec.get("fade", 2.5))
	add_to_group(&"ground_fires")
	var l: Dictionary = spec.get("light", {})
	_light = FlickerLight.new()
	_light.light_color = Color.html(str(l.get("color", "#ff8a3c")))
	_light.light_energy = float(l.get("energy", 3.0))
	_light.omni_range = float(l.get("range", 12.0))
	_light.flicker = float(l.get("flicker", 0.4))
	_light.shadow_enabled = true
	_light.position = Vector3(0, 0.6, 0)
	add_child(_light)
	if Stimuli.current != null:
		Stimuli.current.register_light(_light, float(spec.get("sight_range", 18.0)), float(spec.get("sight_energy", 1.6)))
		Stimuli.current.emit_sound(global_position, float(spec.get("ignite_noise", 18.0)), &"fire", source_id)
	_crackle_t = float(spec.get("crackle_every", 2.5))
	if is_inside_tree() and get_tree().current_scene != null:
		Audio.play_3d(&"sfx/torch_ignite", global_position + Vector3.UP * 0.3, {"volume_db": 2.0, "pitch": 0.7})
	_loop = AudioStreamPlayer3D.new()
	_loop.stream = Audio.stream(&"sfx/campfire_loop")
	_loop.bus = &"SFX"
	_loop.unit_size = 5.0
	_loop.max_distance = 40.0
	_loop.volume_db = 0.0
	add_child(_loop)
	if _loop.stream != null:
		_loop.play()
	_build_fx()


func _exit_tree() -> void:
	if Stimuli.current != null and _light != null:
		Stimuli.current.unregister_light(_light)


func _physics_process(delta: float) -> void:
	advance(delta)


## Burning: 1 at full strength, down to 0 over the fade, 0 once out.
func strength() -> float:
	if age < duration:
		return 1.0
	return clampf(1.0 - (age - duration) / maxf(fade, 0.01), 0.0, 1.0)


func is_burning() -> bool:
	return not _out


## Steps the fire `delta` seconds: damage on its ticks, the crackle, dying down, going out, and
## (headless tests step it by hand) freeing itself once the smoke has cleared.
func advance(delta: float) -> void:
	age += delta
	if not _out:
		var tick: float = float(spec.get("tick", 0.5))
		_tick_t += delta
		while _tick_t >= tick:
			_tick_t -= tick
			burn_creatures(tick)
		var st: float = float(spec.get("structure_tick", 1.5))
		_structure_t += delta
		while _structure_t >= st:
			_structure_t -= st
			burn_structures(st)
		_crackle_t -= delta
		if _crackle_t <= 0.0:
			_crackle_t = float(spec.get("crackle_every", 2.5))
			if Stimuli.current != null:
				Stimuli.current.emit_sound(global_position, float(spec.get("crackle_noise", 9.0)) * strength(), &"fire", source_id)
		_present()
		if age >= duration + fade:
			_go_out()
	elif age >= duration + fade + float(spec.get("linger", 14.0)):
		queue_free()


## Everything in the flames that can burn: receivers (take_damage) of the bodies whose physics
## shapes overlap the fire's cylinder (radius + reach), each once.
func receivers_in(reach: float) -> Array[Node3D]:
	var out: Array[Node3D] = []
	if not is_inside_tree():
		return out
	var h: float = float(spec.get("height", 1.8))
	var shape := CylinderShape3D.new()
	shape.radius = radius + reach
	shape.height = h + 1.0
	var q := PhysicsShapeQueryParameters3D.new()
	q.shape = shape
	q.transform = Transform3D(Basis(), global_position + Vector3.UP * (h * 0.5))
	q.collision_mask = MASK
	q.collide_with_areas = true
	var seen: Dictionary = {}
	for hit: Dictionary in get_world_3d().direct_space_state.intersect_shape(q, 64):
		var r: Object = PlayerEquipment._damage_receiver(hit.get("collider"))
		if r == null or not (r is Node3D) or seen.has(r.get_instance_id()):
			continue
		seen[r.get_instance_id()] = true
		out.append(r as Node3D)
	return out


## One damage step of `dt` seconds on the Hollowed, wildlife and players standing in the flames.
func burn_creatures(dt: float) -> void:
	var k: float = strength()
	if k <= 0.0:
		return
	for r: Node3D in receivers_in(BODY_PAD):
		# Bodies only: doors, barricades and built pieces burn on their own (slower) step.
		if not (r is Enemy or r is Animal or r is Player):
			continue
		var d := Vector2(r.global_position.x - global_position.x, r.global_position.z - global_position.z)
		if d.length() > radius + BODY_PAD:
			continue
		var dps: float = float(spec.get("player_dps" if r is Player else "dps", 10.0))
		r.call(&"take_damage", _fire_info(dps * dt * k, r.global_position + Vector3.UP * 0.9))


## One step of `dt` seconds on the flammable structures the flames reach.
func burn_structures(dt: float) -> void:
	var k: float = strength()
	var dps: float = float(spec.get("structure_dps", 0.0))
	if k <= 0.0 or dps <= 0.0:
		return
	for r: Node3D in receivers_in(float(spec.get("structure_reach", 0.6))):
		var piece := r as StructurePiece
		if piece == null or piece.def == null or not piece.def.flammable:
			continue
		var info := _fire_info(dps * dt * k, piece.global_position + Vector3.UP * 0.3)
		info.tool_power = {"structure": dps * dt * k}
		piece.take_damage(info)


func _fire_info(amount: float, at: Vector3) -> DamageInfo:
	var info := DamageInfo.make(amount, &"fire", &"fire", source_id)
	info.hit_pos = at
	info.source_pos = origin if origin != Vector3.ZERO else global_position
	info.direction = (at - global_position).normalized() if at.distance_to(global_position) > 0.01 else Vector3.UP
	return info


func _go_out() -> void:
	_out = true
	if Stimuli.current != null and _light != null:
		Stimuli.current.unregister_light(_light)
	if _light != null:
		_light.queue_free()
		_light = null
	for p: GPUParticles3D in _fx:
		if is_instance_valid(p):
			p.emitting = false
	if _loop != null:
		_loop.queue_free()
		_loop = null


## The flames shrink and the light dims as it dies down; the scorch darkens in as it burns.
func _present() -> void:
	var k: float = strength()
	if _light != null:
		_light.light_energy = float((spec.get("light", {}) as Dictionary).get("energy", 3.0)) * k
	for p: GPUParticles3D in _fx:
		if is_instance_valid(p):
			p.amount_ratio = clampf(k, 0.05, 1.0)
	if _loop != null:
		_loop.volume_db = linear_to_db(maxf(k, 0.01))
	if _scorch != null:
		_scorch.modulate.a = clampf(age / 1.5, 0.0, 1.0)


# --- FX (procedural; none headless, where nothing draws) ----------------------------------------

func _build_fx() -> void:
	if DisplayServer.get_name() == "headless":
		return
	var rng := RandomNumberGenerator.new()
	rng.seed = hash(global_position)
	var n: int = int(spec.get("flames", 7))
	var size: float = float(spec.get("flame_size", 0.75))
	# One tall clump in the middle where the bottle burst, lower clumps where the fuel ran, and a
	# carpet of short flames over the whole patch so it reads as burning ground, not candles.
	for i: int in n:
		var p: GPUParticles3D = _flames(size * (1.3 if i == 0 else rng.randf_range(0.65, 1.0)), radius * (0.22 if i == 0 else 0.14), 22)
		var a: float = TAU * float(i) / float(maxi(1, n - 1)) + rng.randf_range(-0.3, 0.3)
		var rr: float = 0.0 if i == 0 else radius * rng.randf_range(0.3, 0.72)
		p.position = Vector3(cos(a) * rr, 0.05, sin(a) * rr)
		add_child(p)
		_fx.append(p)
	var carpet: GPUParticles3D = _flames(size * 0.45, radius * 0.75, 90)
	add_child(carpet)
	_fx.append(carpet)
	var embers: GPUParticles3D = _embers()
	add_child(embers)
	_fx.append(embers)
	_smoke = _smoke_particles()
	add_child(_smoke)
	_scorch = Decal.new()
	_scorch.size = Vector3(radius * 2.3, 1.2, radius * 2.3)
	_scorch.texture_albedo = _scorch_texture()
	_scorch.modulate = Color(1, 1, 1, 0)
	_scorch.cull_mask = 1
	add_child(_scorch)
	# The smoke outlasts the flames a little, then stops; the node frees after `linger`.
	get_tree().create_timer(duration + fade + 4.0).timeout.connect(func() -> void:
		if is_instance_valid(_smoke):
			_smoke.emitting = false)


## Licking flames over a patch `spread` m across: flipbook fire, additive, rising and shrinking.
func _flames(size: float, spread: float, amount: int) -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.amount = amount
	p.lifetime = 0.7
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	p.visibility_aabb = AABB(Vector3(-spread - size, -0.2, -spread - size), Vector3(2.0 * (spread + size), size * 3.0, 2.0 * (spread + size)))
	var m := ParticleProcessMaterial.new()
	m.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
	m.emission_box_extents = Vector3(spread, 0.05, spread)
	m.direction = Vector3.UP
	m.spread = 12.0
	m.initial_velocity_min = 0.4
	m.initial_velocity_max = 1.0
	m.gravity = Vector3(0.0, 0.9, 0.0)
	m.scale_min = 0.6
	m.scale_max = 1.15
	var sc := Curve.new()
	sc.add_point(Vector2(0.0, 0.55))
	sc.add_point(Vector2(0.25, 1.0))
	sc.add_point(Vector2(1.0, 0.25))
	var st := CurveTexture.new()
	st.curve = sc
	m.scale_curve = st
	var g := Gradient.new()
	g.offsets = PackedFloat32Array([0.0, 0.12, 0.6, 1.0])
	g.colors = PackedColorArray([Color(1.0, 0.9, 0.6, 0.0), Color(1.0, 0.82, 0.48, 1.0), Color(0.95, 0.4, 0.1, 0.7), Color(0.4, 0.08, 0.02, 0.0)])
	var gt := GradientTexture1D.new()
	gt.gradient = g
	m.color_ramp = gt
	var q := QuadMesh.new()
	q.size = Vector2(size * 0.75, size)
	q.center_offset = Vector3(0.0, size * 0.4, 0.0)
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	mat.vertex_color_use_as_albedo = true
	if ResourceLoader.exists(FLIPBOOK):
		mat.albedo_texture = load(FLIPBOOK)
		mat.albedo_color = Color(1.0, 0.9, 0.7) * 1.4
		mat.particles_anim_h_frames = 8
		mat.particles_anim_v_frames = 8
		mat.particles_anim_loop = true
		m.anim_speed_min = 1.0
		m.anim_speed_max = 1.4
		m.anim_offset_max = 1.0
	else:
		mat.albedo_texture = ViewModel.teardrop_texture()
	q.material = mat
	p.process_material = m
	p.draw_pass_1 = q
	return p


func _embers() -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.amount = 24
	p.lifetime = 1.6
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	p.visibility_aabb = AABB(Vector3(-radius - 1.0, -0.2, -radius - 1.0), Vector3(2.0 * radius + 2.0, 5.0, 2.0 * radius + 2.0))
	var m := ParticleProcessMaterial.new()
	m.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
	m.emission_box_extents = Vector3(radius * 0.6, 0.1, radius * 0.6)
	m.direction = Vector3.UP
	m.spread = 25.0
	m.initial_velocity_min = 0.8
	m.initial_velocity_max = 2.0
	m.gravity = Vector3(0.0, 0.4, 0.0)
	m.turbulence_enabled = true
	m.turbulence_noise_strength = 0.6
	var g := Gradient.new()
	g.set_color(0, Color(1.0, 0.75, 0.35, 1.0))
	g.set_color(1, Color(0.9, 0.25, 0.05, 0.0))
	var gt := GradientTexture1D.new()
	gt.gradient = g
	m.color_ramp = gt
	var q := QuadMesh.new()
	q.size = Vector2(0.025, 0.025)
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	mat.vertex_color_use_as_albedo = true
	mat.albedo_color = Color(1.0, 0.8, 0.5) * 2.0
	q.material = mat
	p.process_material = m
	p.draw_pass_1 = q
	return p


## Dark, soft smoke rolling up off the flames and drifting.
func _smoke_particles() -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.amount = 20
	p.lifetime = 4.5
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	p.visibility_aabb = AABB(Vector3(-6, -0.5, -6), Vector3(12, 12, 12))
	var m := ParticleProcessMaterial.new()
	m.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
	m.emission_box_extents = Vector3(radius * 0.5, 0.2, radius * 0.5)
	m.emission_shape_offset = Vector3(0.0, 0.9, 0.0)
	m.direction = Vector3.UP
	m.spread = 15.0
	m.initial_velocity_min = 0.6
	m.initial_velocity_max = 1.2
	m.gravity = Vector3(0.25, 0.15, 0.0)
	m.damping_min = 0.1
	m.damping_max = 0.3
	m.angle_min = -180.0
	m.angle_max = 180.0
	m.scale_min = 0.8
	m.scale_max = 1.3
	var sc := Curve.new()
	sc.add_point(Vector2(0.0, 0.4))
	sc.add_point(Vector2(1.0, 1.6))
	var st := CurveTexture.new()
	st.curve = sc
	m.scale_curve = st
	var g := Gradient.new()
	g.offsets = PackedFloat32Array([0.0, 0.15, 1.0])
	g.colors = PackedColorArray([Color(0.12, 0.1, 0.09, 0.0), Color(0.14, 0.12, 0.11, 0.55), Color(0.3, 0.29, 0.28, 0.0)])
	var gt := GradientTexture1D.new()
	gt.gradient = g
	m.color_ramp = gt
	var q := QuadMesh.new()
	q.size = Vector2(1.4, 1.4)
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	mat.vertex_color_use_as_albedo = true
	mat.albedo_texture = _soft_texture()
	q.material = mat
	p.process_material = m
	p.draw_pass_1 = q
	return p


static var _soft: ImageTexture = null
static var _scorch_tex: ImageTexture = null


## A soft round puff (smoke) drawn in code.
static func _soft_texture() -> Texture2D:
	if _soft != null:
		return _soft
	var n: int = 64
	var img := Image.create(n, n, false, Image.FORMAT_RGBA8)
	var noise := FastNoiseLite.new()
	noise.seed = 57
	noise.frequency = 0.08
	for y: int in n:
		for x: int in n:
			var d: float = Vector2(x - n * 0.5 + 0.5, y - n * 0.5 + 0.5).length() / (n * 0.5)
			var a: float = clampf(1.0 - d, 0.0, 1.0)
			a = a * a * (0.75 + 0.25 * noise.get_noise_2d(x, y))
			img.set_pixel(x, y, Color(1, 1, 1, clampf(a, 0.0, 1.0)))
	img.generate_mipmaps()
	_soft = ImageTexture.create_from_image(img)
	return _soft


## The scorch the fire leaves: soot black at the middle, broken and blotchy toward the edge.
static func _scorch_texture() -> Texture2D:
	if _scorch_tex != null:
		return _scorch_tex
	var n: int = 128
	var img := Image.create(n, n, false, Image.FORMAT_RGBA8)
	var noise := FastNoiseLite.new()
	noise.seed = 91
	noise.frequency = 0.045
	noise.fractal_octaves = 4
	for y: int in n:
		for x: int in n:
			var d: float = Vector2(x - n * 0.5 + 0.5, y - n * 0.5 + 0.5).length() / (n * 0.5)
			var v: float = noise.get_noise_2d(x, y)
			var a: float = clampf((1.0 - d) * 1.6 + v * 0.7 - 0.25, 0.0, 1.0)
			var c: float = 0.03 + 0.05 * clampf(v + 0.5, 0.0, 1.0)
			img.set_pixel(x, y, Color(c, c * 0.9, c * 0.8, a * 0.92))
	img.generate_mipmaps()
	_scorch_tex = ImageTexture.create_from_image(img)
	return _scorch_tex
