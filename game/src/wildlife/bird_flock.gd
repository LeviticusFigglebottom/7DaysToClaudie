class_name BirdFlock
extends Node3D
## A flock of songbirds or crows (ADR-0027), drawn as two MultiMeshes (perched and flying
## meshes of one model) and flapped by the fur shader from per-instance data, so a flock of ten
## is two draw calls and no skeletons.
##
## Perched, the birds peck and hop (ground) or sit in a tree's crown (canopy) and chatter. They
## flush when a person or a Hollowed comes close or at a loud noise: wingbeats, an alarm call,
## and a sound in the stimulus field (ADR-0012) that the Hollowed hear and come to look at —
## birds give your position away. Songbirds scatter to new perches; crows circle over what
## flushed them, cawing, every caw another stimulus over your head, then settle elsewhere.

enum State { PERCHED, FLUSHING, CIRCLING, LEAVING, LANDING, GONE }

var flock_id: StringName = &""
var def: WildlifeDef
var manager: Node = null
var state: State = State.PERCHED
var birds: Array[Dictionary] = []
var circle_center := Vector3.ZERO
var flush_count: int = 0
var last_cause: String = ""

var _rng := RandomNumberGenerator.new()
var _perch_mm: MultiMeshInstance3D
var _fly_mm: MultiMeshInstance3D
var _t: float = 0.0
var _state_t: float = 0.0
var _call_t: float = 3.0
var _check_t: float = 0.0
var _leave_to := Vector3.ZERO
var _flap_rate: float = 12.0
var _crow: bool = false


## perches: world-space perch points (one per bird; trees' crowns or the ground).
func setup(id: StringName, p_def: WildlifeDef, p_manager: Node, perches: Array[Vector3], p_seed: int) -> void:
	flock_id = id
	def = p_def
	manager = p_manager
	_rng.seed = p_seed
	_crow = def.model.ends_with("crow")
	_flap_rate = 4.2 if _crow else 13.0
	for i: int in perches.size():
		birds.append({"pos": perches[i], "perch": perches[i], "vel": Vector3.ZERO, "yaw": _rng.randf() * TAU,
			"scale": lerpf(def.size.x, def.size.y, _rng.randf()), "phase": _rng.randf(), "delay": 0.0, "air": false,
			"hop": 0.0, "hop_from": perches[i], "hop_to": perches[i], "peck": _rng.randf() * 3.0})


func _ready() -> void:
	var meshes: Dictionary = _load_meshes()
	_perch_mm = _make_mm(meshes.get("perch"), false)
	_fly_mm = _make_mm(meshes.get("fly"), true)
	_sync()


func _load_meshes() -> Dictionary:
	var out: Dictionary = {}
	var path: String = "res://assets/generated/models/%s.glb" % def.model
	if ResourceLoader.exists(path):
		var root: Node = (load(path) as PackedScene).instantiate()
		for mi: Node in root.find_children("*", "MeshInstance3D", true, false):
			out[String(mi.name)] = (mi as MeshInstance3D).mesh
		root.free()
	if not out.has("perch") or not out.has("fly"):
		# Stand-in until `make assets`: dark little lozenges.
		var m := StandardMaterial3D.new()
		m.albedo_color = Color(0.08, 0.08, 0.09) if _crow else Color(0.4, 0.3, 0.2)
		var b := CapsuleMesh.new()
		b.radius = 0.05 if _crow else 0.025
		b.height = 0.4 if _crow else 0.16
		b.material = m
		out["perch"] = b
		out["fly"] = b
	return out


func _make_mm(mesh: Mesh, custom: bool) -> MultiMeshInstance3D:
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_custom_data = custom
	mm.mesh = mesh
	mm.instance_count = birds.size()
	var mmi := MultiMeshInstance3D.new()
	mmi.multimesh = mm
	mmi.custom_aabb = AABB(Vector3(-150, -40, -150), Vector3(300, 120, 300))
	mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	add_child(mmi)
	return mmi


func center() -> Vector3:
	var c := Vector3.ZERO
	for b: Dictionary in birds:
		c += b["pos"]
	return c / maxf(1.0, float(birds.size()))


func is_perched() -> bool:
	return state == State.PERCHED


func _process(delta: float) -> void:
	_t += delta
	_state_t += delta
	match state:
		State.PERCHED:
			_perched(delta)
		State.FLUSHING, State.CIRCLING, State.LEAVING, State.LANDING:
			_flying(delta)
	_sync()


func _perched(delta: float) -> void:
	_call_t -= delta
	if _call_t <= 0.0:
		_call_t = _rng.randf_range(5.0, 14.0) if not _crow else _rng.randf_range(8.0, 22.0)
		var snd: String = str(def.sounds.get("call", ""))
		if snd != "" and is_inside_tree():
			Audio.play_3d(StringName(snd), center() + Vector3.UP, {"volume_db": -6.0 if not _crow else -2.0, "max_distance": 80.0})
	for b: Dictionary in birds:
		b["peck"] = float(b["peck"]) - delta
		if float(b["hop"]) > 0.0:
			b["hop"] = float(b["hop"]) - delta * 3.0
			var t: float = 1.0 - clampf(float(b["hop"]), 0.0, 1.0)
			var p: Vector3 = (b["hop_from"] as Vector3).lerp(b["hop_to"], t)
			p.y += sin(t * PI) * 0.12 * float(b["scale"])
			b["pos"] = p
		elif float(b["peck"]) <= 0.0:
			b["peck"] = _rng.randf_range(1.0, 4.0)
			if def.perch == "ground" and _rng.randf() < 0.5:
				var to: Vector3 = (b["perch"] as Vector3) + Vector3(_rng.randf_range(-0.6, 0.6), 0.0, _rng.randf_range(-0.6, 0.6))
				if manager != null:
					to.y = float(manager.call(&"height_at", to.x, to.z))
				b["hop_from"] = b["pos"]
				b["hop_to"] = to
				b["hop"] = 1.0
				b["yaw"] = atan2(to.x - (b["pos"] as Vector3).x, to.z - (b["pos"] as Vector3).z)
			else:
				b["yaw"] = float(b["yaw"]) + _rng.randf_range(-1.2, 1.2)


## Up they go. cause: person / hollowed / noise / hum.
func flush(threat: Vector3, cause: String) -> void:
	if state != State.PERCHED:
		return
	flush_count += 1
	last_cause = cause
	state = State.FLUSHING
	_state_t = 0.0
	circle_center = threat
	var c: Vector3 = center()
	var away := Vector3(c.x - threat.x, 0.0, c.z - threat.z)
	away = away.normalized() if away.length() > 0.1 else Vector3.FORWARD
	_leave_to = c + away * _rng.randf_range(45.0, 80.0)
	for b: Dictionary in birds:
		b["delay"] = _rng.randf_range(0.0, 0.35)
		var spread: Vector3 = away.rotated(Vector3.UP, _rng.randf_range(-0.9, 0.9))
		b["vel"] = spread * def.fly_speed * 0.5 + Vector3.UP * _rng.randf_range(3.0, 5.0)
		b["air"] = false
	for k: String in ["flush", "alarm"]:
		var snd: String = str(def.sounds.get(k, ""))
		if snd != "" and is_inside_tree():
			Audio.play_3d(StringName(snd), c + Vector3.UP, {"volume_db": 0.0 if k == "flush" else -2.0, "max_distance": 140.0})
	# A flush is a sound like any other to the Hollowed (ADR-0012): they come to see what put the birds up.
	if Stimuli.current != null:
		Stimuli.current.emit_sound(c, def.flush_loudness, &"bird_flush", flock_id)
	Events.birds_flushed.emit(flock_id, def.id, c, cause)


## Leave for good (a Hum night: the valley falls silent).
func leave(from: Vector3) -> void:
	if state == State.GONE:
		return
	if state == State.PERCHED:
		flush(from, "hum")
	state = State.LEAVING
	circle_center = from
	var c: Vector3 = center()
	_leave_to = c + Vector3(c.x - from.x, 0.0, c.z - from.z).normalized() * 400.0


func _flying(delta: float) -> void:
	var c: Vector3 = center()
	if state == State.FLUSHING and _state_t > 1.6:
		_state_t = 0.0
		state = State.CIRCLING if def.circle_seconds > 0.0 and last_cause != "hum" else State.LEAVING
		_call_t = 0.5
	if state == State.CIRCLING:
		_call_t -= delta
		if _call_t <= 0.0:
			_call_t = _rng.randf_range(1.8, 3.6)
			var snd: String = str(def.sounds.get("call", ""))
			if snd != "" and is_inside_tree():
				Audio.play_3d(StringName(snd), c, {"volume_db": 0.0, "max_distance": 160.0})
			# every caw over you is another mark on the map for anything listening
			if Stimuli.current != null:
				Stimuli.current.emit_sound(Vector3(circle_center.x, c.y, circle_center.z), def.flush_loudness * 0.6, &"bird_flush", flock_id)
		if _state_t > def.circle_seconds:
			state = State.LEAVING
			_state_t = 0.0
	if state == State.LEAVING and Vector2(c.x - _leave_to.x, c.z - _leave_to.z).length() < 8.0:
		if last_cause == "hum":
			state = State.GONE
			return
		_land_at(_leave_to)
	var landed: int = 0
	for i: int in birds.size():
		var b: Dictionary = birds[i]
		if float(b["delay"]) > 0.0:
			b["delay"] = float(b["delay"]) - delta
			continue
		b["air"] = true
		var p: Vector3 = b["pos"]
		var v: Vector3 = b["vel"]
		var goal: Vector3
		var ground: float = float(manager.call(&"height_at", p.x, p.z)) if manager != null else 0.0
		match state:
			State.FLUSHING:
				goal = p + v.normalized() * 5.0 + Vector3.UP * 2.0
			State.CIRCLING:
				var ang: float = _t * 0.45 + float(i) * TAU / float(birds.size())
				var r: float = 15.0 + 4.0 * sin(float(i) * 1.7)
				goal = Vector3(circle_center.x + cos(ang) * r, ground + 14.0 + 3.0 * sin(ang * 2.0 + float(i)), circle_center.z + sin(ang) * r)
			State.LEAVING:
				goal = _leave_to + Vector3(sin(float(i) * 2.3) * 4.0, 16.0, cos(float(i) * 1.9) * 4.0)
				goal.y = maxf(goal.y, ground + 10.0)
			State.LANDING:
				goal = b["perch"]
		var want: Vector3 = (goal - p)
		var dist: float = want.length()
		var speed: float = def.fly_speed * (0.6 if state == State.LANDING and dist < 6.0 else 1.0)
		if dist > 0.01:
			v = v.lerp(want.normalized() * minf(speed, dist * 2.0 + 0.6), clampf(delta * 2.2, 0.0, 1.0))
		p += v * delta
		p.y = maxf(p.y, ground + 0.05)
		b["vel"] = v
		b["pos"] = p
		if Vector2(v.x, v.z).length() > 0.2:
			b["yaw"] = atan2(v.x, v.z)
		if state == State.LANDING and dist < 0.15:
			b["pos"] = b["perch"]
			b["vel"] = Vector3.ZERO
			b["air"] = false
			landed += 1
	if state == State.LANDING and landed == birds.size():
		state = State.PERCHED
		_state_t = 0.0
		_call_t = _rng.randf_range(4.0, 9.0)


func _land_at(spot: Vector3) -> void:
	var perches: Array[Vector3] = []
	if manager != null:
		perches = manager.call(&"perches_for", def, spot, birds.size(), _rng.randi())
	if perches.size() < birds.size():
		state = State.GONE
		return
	for i: int in birds.size():
		birds[i]["perch"] = perches[i]
	state = State.LANDING
	_state_t = 0.0


func _sync() -> void:
	if _perch_mm == null:
		return
	var pm: MultiMesh = _perch_mm.multimesh
	var fm: MultiMesh = _fly_mm.multimesh
	var gx: Transform3D = global_transform.affine_inverse()
	var hidden := Transform3D(Basis().scaled(Vector3.ZERO), Vector3.ZERO)
	for i: int in birds.size():
		var b: Dictionary = birds[i]
		var s: float = float(b["scale"])
		var basis := Basis(Vector3.UP, float(b["yaw"])).scaled(Vector3.ONE * s)
		var air: bool = bool(b["air"])
		if air:
			var v: Vector3 = b["vel"]
			var pitch: float = clampf(-atan2(v.y, maxf(Vector2(v.x, v.z).length(), 0.1)), -0.7, 0.7)
			basis = Basis(Vector3.UP, float(b["yaw"])) * Basis(Vector3.RIGHT, pitch)
			basis = basis.scaled(Vector3.ONE * s)
		var xf := gx * Transform3D(basis, b["pos"])
		if air:
			pm.set_instance_transform(i, hidden)
			fm.set_instance_transform(i, xf)
			# flapping hard on the climb, steadier in cruise, wings spread to glide when circling
			var amp: float = 1.0
			var rate: float = _flap_rate
			if state == State.CIRCLING:
				amp = 0.35 + 0.35 * (0.5 + 0.5 * sin(_t * 0.8 + float(i)))
				rate *= 0.8
			elif state == State.LEAVING and not _crow:
				# a songbird's bounding flight: bursts of beats, wings shut between
				amp = 1.0 if fmod(_t * 1.6 + float(b["phase"]), 1.0) < 0.6 else 0.0
			elif state == State.LANDING:
				amp = 0.7
				rate *= 1.2
			fm.set_instance_custom_data(i, Color(float(b["phase"]), rate, amp, 0.0))
		else:
			fm.set_instance_transform(i, hidden)
			pm.set_instance_transform(i, xf)
