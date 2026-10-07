class_name BaseTechNode
extends Node3D
## What a base trap or powered piece shows and does in the world (ADR-0052). A child of its
## StructurePiece, made by StructurePiece for every def BaseTech.handles():
##  * spike pit: the Hollowed that walk in are hurt, held for a moment and slowed while inside;
##    the stakes wear with use. A player who steps in is hurt too.
##  * deadfall: the first body under it drops the log (damage, a stagger, a crash heard far off);
##    it lies sprung until someone lifts it (trap.rearm).
##  * tripwire bell: a Hollow walking through rings it; the player is told from where.
##  * generator: an engine noise loop while it runs (BaseTechManager ticks its fuel and heat).
##  * work light: a steady light while powered and switched on.
##  * floodlight: lights up when a Hollow moves within range, and warns the player.
##  * nail sentry: shoots the nearest Hollow it can see while powered and loaded.
## Generated models when they exist (a deadfall's `log` part drops; a floodlight's or sentry's
## `head` part turns), stand-ins from primitives otherwise. The Hollowed are slowed and held from
## here, after their own movement each physics frame, so enemy.gd needs no hook.

const TRIGGER_LAYER: int = 1 << 10
const PLAYER_LAYER: int = 1 << 3
const ENEMY_LAYER: int = 1 << 4
## Layer the walk-through traps' colliders move to: the interaction ray hits it, bodies don't.
const INTERACT_LAYER: int = 1 << 7
## What a sentry's shots are stopped by: the ground, structures, props, enemies, sight blockers.
const SHOT_MASK: int = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 4) | (1 << 14)
const SCAN_SECONDS: float = 0.25

var piece: StructurePiece
var trap: String = ""
var power: String = ""

var _area: Area3D = null
## Spike pit: enemy -> {stuck: seconds left held, t: seconds to the next tick, at: where it entered,
## prev: last position after the pit had its say}.
var _inside: Dictionary = {}
var _player_cd: float = 0.0
var _cooldown: float = 0.0
var _log: Node3D = null
var _log_up := Transform3D.IDENTITY
var _head: Node3D = null
var _glow: GeometryInstance3D = null
var _light: Light3D = null
var _light_registered: bool = false
var _loop: AudioStreamPlayer3D = null
var _scan_t: float = 0.0
var _hold_t: float = 0.0
var _warn_t: float = -100.0
var _fire_t: float = 0.0
var _empty_warned: bool = false

static var _mats: Dictionary = {}


static func handles(def: StructureDef) -> bool:
	return BaseTech.handles(def)


## Builds the piece's base visual into `base` (added to the piece) and attaches the tech node.
static func attach(p: StructurePiece, base: MeshInstance3D) -> BaseTechNode:
	var v := BaseTechNode.new()
	v.name = "Tech"
	v.piece = p
	v.trap = BaseTech.trap_kind(p.def)
	v.power = BaseTech.power_kind(p.def)
	p.add_child(base)
	p.add_child(v)
	v._build(base)
	return v


func _ready() -> void:
	# After the Hollowed's own movement each physics frame, so a pit's hold and slow stick.
	process_physics_priority = 10
	if trap != "":
		# Walked through: the piece's collider only catches the interaction ray.
		piece.collision_layer = INTERACT_LAYER
		var size: Vector3 = piece.def.size
		match trap:
			"spike_pit":
				_area = _trigger(Vector3(size.x * 0.9, 1.2, size.z * 0.9), Vector3.ZERO)
			"deadfall":
				_area = _trigger(Vector3(size.x * 0.8, 1.6, size.z * 0.7), Vector3.ZERO)
			"tripwire":
				_area = _trigger(Vector3(size.x, 0.9, 0.5), Vector3.ZERO)
		_area.body_entered.connect(_on_body_entered)
		_area.body_exited.connect(_on_body_exited)
	refresh()
	set_physics_process(trap == "spike_pit" or power in ["floodlight", "turret"])
	set_process(trap != "")


func _exit_tree() -> void:
	_set_light(false)


func _trigger(size: Vector3, at: Vector3) -> Area3D:
	var a := Area3D.new()
	a.name = "Trigger"
	a.collision_layer = TRIGGER_LAYER
	a.collision_mask = PLAYER_LAYER | ENEMY_LAYER
	a.monitorable = false
	var cs := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = size
	cs.shape = box
	cs.position = at + Vector3(0, size.y * 0.5, 0)
	a.add_child(cs)
	add_child(a)
	return a


# --- Visuals ---------------------------------------------------------------------------------------

func _build(base: MeshInstance3D) -> void:
	var def: StructureDef = piece.def
	var part: String = "log" if trap == "deadfall" else ("head" if power in ["floodlight", "turret"] else "")
	if ModelLibrary.has_model(def.model):
		if part != "":
			var split: Dictionary = ModelLibrary.parts(def.model, PackedStringArray([part]))
			if not split.is_empty() and split.get("base") != null:
				base.mesh = split["base"]
				for nm: String in (split["parts"] as Dictionary):
					var pd: Dictionary = split["parts"][nm]
					var holder := Node3D.new()
					holder.name = nm.capitalize()
					holder.transform = pd["xf"]
					var mi := MeshInstance3D.new()
					mi.mesh = pd["mesh"]
					holder.add_child(mi)
					add_child(holder)
					if part == "log":
						_log = holder
					else:
						_head = holder
						_glow = mi
				_glow = _glow if _glow != null else base
				if _log != null:
					_log_up = _log.transform
				return
		base.mesh = ModelLibrary.mesh(def.model)
		_glow = base
		return
	_glow = base
	match trap:
		"spike_pit":
			_standin_pit(base)
		"deadfall":
			_standin_deadfall(base)
		"tripwire":
			_standin_tripwire(base)
	match power:
		"generator":
			_standin_generator(base)
		"work_light":
			_standin_light(base)
		"floodlight":
			_standin_floodlight(base)
		"turret":
			_standin_turret(base)
	if _log != null:
		_log_up = _log.transform


static func _mat(key: String, c: Color, emissive: bool = false) -> StandardMaterial3D:
	if _mats.has(key):
		return _mats[key]
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	m.roughness = 0.85
	if emissive:
		m.emission_enabled = true
		m.emission = c
		m.emission_energy_multiplier = 0.0
	_mats[key] = m
	return m


func _box(parent: Node3D, size: Vector3, at: Vector3, m: Material, rot := Vector3.ZERO) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var b := BoxMesh.new()
	b.size = size
	b.material = m
	mi.mesh = b
	mi.position = at
	mi.rotation = rot
	parent.add_child(mi)
	return mi


func _cyl(parent: Node3D, r_top: float, r_bottom: float, h: float, at: Vector3, m: Material, rot := Vector3.ZERO) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var c := CylinderMesh.new()
	c.top_radius = r_top
	c.bottom_radius = r_bottom
	c.height = h
	c.radial_segments = 8
	c.rings = 1
	c.material = m
	mi.mesh = c
	mi.position = at
	mi.rotation = rot
	parent.add_child(mi)
	return mi


func _standin_pit(base: MeshInstance3D) -> void:
	var s: Vector3 = piece.def.size
	base.mesh = null
	var dark := _mat("pit_dark", Color(0.07, 0.05, 0.04))
	var dirt := _mat("pit_dirt", Color(0.33, 0.25, 0.17))
	var stake := _mat("pit_stake", Color(0.55, 0.43, 0.3))
	_box(self, Vector3(s.x * 0.92, 0.02, s.z * 0.92), Vector3(0, 0.012, 0), dark)
	for k: int in 4:
		var along_x: bool = k < 2
		var sign: float = -1.0 if k % 2 == 0 else 1.0
		var size := Vector3(s.x, 0.1, 0.16) if along_x else Vector3(0.16, 0.1, s.z)
		var at := Vector3(0, 0.05, sign * s.z * 0.5) if along_x else Vector3(sign * s.x * 0.5, 0.05, 0)
		_box(self, size, at, dirt)
	var rng := RandomNumberGenerator.new()
	rng.seed = Ids.hash64(String(piece.piece_id)) if piece.piece_id != &"" else 1
	for i: int in 3:
		for j: int in 3:
			var at2 := Vector3((float(i) - 1.0) * s.x * 0.28, 0.0, (float(j) - 1.0) * s.z * 0.28)
			var h: float = rng.randf_range(0.3, 0.42)
			_cyl(self, 0.0, 0.035, h, at2 + Vector3(0, h * 0.5 - 0.05, 0), stake, Vector3(rng.randf_range(-0.2, 0.2), 0, rng.randf_range(-0.2, 0.2)))


func _standin_deadfall(base: MeshInstance3D) -> void:
	var s: Vector3 = piece.def.size
	base.mesh = null
	var wood := _mat("df_wood", Color(0.42, 0.32, 0.22))
	var bark := _mat("df_bark", Color(0.3, 0.22, 0.15))
	for x: float in [-s.x * 0.5 + 0.06, s.x * 0.5 - 0.06]:
		_cyl(self, 0.05, 0.06, s.y, Vector3(x, s.y * 0.5, -s.z * 0.35), wood)
	_cyl(self, 0.04, 0.04, s.x, Vector3(0, s.y - 0.05, -s.z * 0.35), wood, Vector3(0, 0, PI * 0.5))
	_cyl(self, 0.02, 0.02, 0.6, Vector3(0.1, 0.3, 0.0), wood, Vector3(0.4, 0, 0.3))
	_log = Node3D.new()
	_log.name = "Log"
	_log.position = Vector3(0, s.y - 0.38, 0)
	add_child(_log)
	_cyl(_log, 0.17, 0.18, s.x * 0.95, Vector3.ZERO, bark, Vector3(0, 0, PI * 0.5))


func _standin_tripwire(base: MeshInstance3D) -> void:
	var s: Vector3 = piece.def.size
	base.mesh = null
	var wood := _mat("tw_wood", Color(0.45, 0.35, 0.24))
	var cord := _mat("tw_cord", Color(0.6, 0.55, 0.42))
	var brass := _mat("tw_brass", Color(0.7, 0.55, 0.2))
	for x: float in [-s.x * 0.5, s.x * 0.5]:
		_cyl(self, 0.02, 0.03, s.y, Vector3(x, s.y * 0.5 - 0.1, 0), wood)
	_box(self, Vector3(s.x, 0.008, 0.008), Vector3(0, 0.22, 0), cord)
	_cyl(self, 0.02, 0.07, 0.11, Vector3(s.x * 0.5, s.y - 0.18, 0.06), brass)


func _standin_generator(base: MeshInstance3D) -> void:
	var s: Vector3 = piece.def.size
	base.mesh = null
	var frame := _mat("gen_frame", Color(0.85, 0.66, 0.12))
	var engine := _mat("gen_engine", Color(0.2, 0.2, 0.21))
	var tank := _mat("gen_tank", Color(0.62, 0.12, 0.08))
	_box(self, Vector3(s.x, 0.06, s.z), Vector3(0, 0.03, 0), frame)
	for x: float in [-s.x * 0.47, s.x * 0.47]:
		for z: float in [-s.z * 0.45, s.z * 0.45]:
			_box(self, Vector3(0.04, s.y, 0.04), Vector3(x, s.y * 0.5, z), frame)
	_box(self, Vector3(s.x * 0.5, s.y * 0.5, s.z * 0.7), Vector3(-s.x * 0.15, s.y * 0.3, 0), engine)
	_cyl(self, 0.16, 0.16, s.x * 0.35, Vector3(s.x * 0.25, s.y * 0.32, 0), engine, Vector3(0, 0, PI * 0.5))
	_box(self, Vector3(s.x * 0.7, 0.16, s.z * 0.6), Vector3(0, s.y - 0.1, 0), tank)
	_glow = _box(self, Vector3(0.06, 0.04, 0.02), Vector3(s.x * 0.3, s.y * 0.6, s.z * 0.36), _mat("gen_lamp", Color(0.3, 1.0, 0.3), true))


func _standin_light(base: MeshInstance3D) -> void:
	var s: Vector3 = piece.def.size
	base.mesh = null
	var wood := _mat("wl_wood", Color(0.45, 0.35, 0.24))
	_cyl(self, 0.035, 0.045, s.y, Vector3(0, s.y * 0.5, 0), wood)
	_box(self, Vector3(0.18, 0.2, 0.16), Vector3(0, s.y - 0.05, 0.1), _mat("wl_cage", Color(0.2, 0.2, 0.2)))
	_glow = _cyl(self, 0.06, 0.06, 0.12, Vector3(0, s.y - 0.08, 0.12), _mat("wl_bulb", Color(1.0, 0.86, 0.6), true))


func _standin_floodlight(base: MeshInstance3D) -> void:
	var s: Vector3 = piece.def.size
	base.mesh = null
	var steel := _mat("fl_steel", Color(0.35, 0.36, 0.37))
	_cyl(self, 0.04, 0.05, s.y, Vector3(0, s.y * 0.5, 0), steel)
	_head = Node3D.new()
	_head.name = "Head"
	_head.position = Vector3(0, s.y - 0.1, 0.05)
	add_child(_head)
	_box(_head, Vector3(0.42, 0.3, 0.16), Vector3.ZERO, steel, Vector3(-0.5, 0, 0))
	_glow = _box(_head, Vector3(0.36, 0.24, 0.02), Vector3(0, -0.05, 0.08), _mat("fl_lens", Color(0.95, 0.96, 1.0), true), Vector3(-0.5, 0, 0))
	_box(self, Vector3(0.1, 0.08, 0.08), Vector3(0, s.y - 0.45, 0.06), _mat("fl_sensor", Color(0.9, 0.9, 0.88)))


func _standin_turret(base: MeshInstance3D) -> void:
	var s: Vector3 = piece.def.size
	base.mesh = null
	var steel := _mat("st_steel", Color(0.3, 0.31, 0.3))
	var paint := _mat("st_paint", Color(0.75, 0.2, 0.12))
	for k: int in 3:
		var a: float = TAU * float(k) / 3.0
		_cyl(self, 0.025, 0.03, s.y * 0.85, Vector3(sin(a) * 0.2, s.y * 0.4, cos(a) * 0.2), steel, Vector3(cos(a) * 0.3, 0, -sin(a) * 0.3))
	_head = Node3D.new()
	_head.name = "Head"
	_head.position = Vector3(0, s.y * 0.85, 0)
	add_child(_head)
	_box(_head, Vector3(0.26, 0.24, 0.42), Vector3.ZERO, paint)
	_cyl(_head, 0.03, 0.03, 0.3, Vector3(0, 0.02, 0.34), steel, Vector3(PI * 0.5, 0, 0))
	_glow = _box(_head, Vector3(0.06, 0.04, 0.02), Vector3(0.09, 0.08, 0.22), _mat("st_lamp", Color(1.0, 0.25, 0.15), true))


## Shows the piece's state: a sprung or set deadfall, a light on or off, a generator running.
func refresh() -> void:
	if piece == null or not is_instance_valid(piece):
		return
	var st: Dictionary = BaseTechManager.peek(piece)
	if trap == "deadfall" and _log != null:
		var armed: bool = bool(st.get("armed", true))
		_log.transform = _log_up if armed else _log_down()
	if power == "":
		return
	var live: bool = BaseTechManager.is_powered(piece)
	_set_glow(live)
	match power:
		"generator":
			_set_engine(live)
		"work_light":
			_set_light(live and bool(st.get("on", true)))
		"floodlight":
			if not live:
				_hold_t = 0.0
				_set_light(false)


## Where a dropped log lies: on the ground under where it hung.
func _log_down() -> Transform3D:
	var t: Transform3D = _log_up
	t.origin.y = 0.18
	return t


func _set_glow(on: bool) -> void:
	if _glow == null:
		return
	PropLights.set_lit(_glow, on)
	var mi := _glow as MeshInstance3D
	if mi != null and mi.mesh is PrimitiveMesh:
		var m := (mi.mesh as PrimitiveMesh).material as StandardMaterial3D
		if m != null and m.emission_enabled:
			# Stand-in glow materials are shared per colour: each lit piece gets its own copy.
			var own: StandardMaterial3D = m if m.resource_local_to_scene else m.duplicate()
			own.resource_local_to_scene = true
			own.emission_energy_multiplier = 2.5 if on else 0.0
			(mi.mesh as PrimitiveMesh).material = own


func _set_engine(on: bool) -> void:
	if on and _loop == null:
		_loop = AudioStreamPlayer3D.new()
		_loop.stream = Audio.stream(&"sfx/generator_loop")
		_loop.bus = &"SFX"
		_loop.unit_size = 5.0
		_loop.max_distance = 45.0
		_loop.volume_db = -2.0
		add_child(_loop)
		if _loop.stream != null:
			_loop.play()
	elif not on and _loop != null:
		_loop.queue_free()
		_loop = null


func _set_light(on: bool) -> void:
	if on and _light == null:
		var flood: bool = power == "floodlight"
		var c: Dictionary = BaseTech.power_cfg("floodlight" if flood else "light")
		if flood:
			var spot := SpotLight3D.new()
			spot.spot_range = float(c.get("range", 28.0))
			spot.spot_angle = float(c.get("angle", 38.0))
			spot.rotation = Vector3(deg_to_rad(-30.0), 0, 0)
			_light = spot
		else:
			var omni := OmniLight3D.new()
			omni.omni_range = float(c.get("range", 13.0))
			_light = omni
		_light.name = "Light"
		_light.light_color = Color.html(str(c.get("color", "#ffe4b8")))
		_light.light_energy = float(c.get("energy", 1.8))
		_light.position = Vector3(0, float(c.get("height", 2.0)), 0.15)
		# Shadowed lights share the graphics preset's budget (PoiManager casts only the nearest).
		_light.shadow_enabled = bool(c.get("shadow", true))
		if _light.shadow_enabled:
			_light.add_to_group(&"shadow_light_budget")
		(_head if _head != null and flood else self as Node3D).add_child(_light)
		if flood and _head != null:
			_light.position = Vector3(0, 0, 0.1)
		if Stimuli.current != null:
			Stimuli.current.register_light(_light, float(c.get("stimulus_range", 24.0)), float(c.get("stimulus_energy", 1.2)))
			_light_registered = true
	elif not on and _light != null:
		if _light_registered and Stimuli.current != null:
			Stimuli.current.unregister_light(_light)
		_light_registered = false
		_light.queue_free()
		_light = null


func is_lit() -> bool:
	return _light != null


# --- Traps -----------------------------------------------------------------------------------------

func _on_body_entered(body: Node) -> void:
	if piece == null or not is_instance_valid(piece) or piece.hp <= 0.0:
		return
	var enemy := body as Enemy
	if enemy != null and not enemy.is_alive():
		return
	match trap:
		"spike_pit":
			if enemy != null:
				var c: Dictionary = BaseTech.trap_cfg("spike_pit")
				_inside[enemy] = {"stuck": float(c.get("stuck_seconds", 1.8)), "t": float(c.get("tick_seconds", 1.0)),
					"at": enemy.global_position, "prev": enemy.global_position}
				_stake(enemy, float(c.get("damage", 24.0)))
				if Stimuli.current != null:
					Stimuli.current.emit_sound(piece.global_position, float(c.get("noise", 10.0)), &"trap", piece.piece_id)
			elif body is Player and _player_cd <= 0.0:
				var pc: Dictionary = BaseTech.trap_cfg("spike_pit")
				_player_cd = float(pc.get("player_cooldown", 2.0))
				_hurt_player(body as Player, float(pc.get("player_damage", 12.0)), &"pierce")
				Events.player_status_message.emit("You stumble into your own spike pit.", &"warning")
		"deadfall":
			var armed: bool = bool(BaseTechManager.peek(piece).get("armed", true))
			if not armed:
				return
			var cfg: Dictionary = BaseTech.trap_cfg("deadfall")
			if enemy != null and not _heavy_enough(enemy, str(cfg.get("min_weight", "light"))):
				return
			if enemy != null or body is Player:
				drop()
		"tripwire":
			if enemy != null and _cooldown <= 0.0:
				ring()


func _on_body_exited(body: Node) -> void:
	_inside.erase(body)


static func _heavy_enough(e: Enemy, min_weight: String) -> bool:
	var classes: Array = PoiPieces.cfg("hollowed").get("classes", ["light", "normal", "heavy"])
	return PoiPieces.weight_of(e) >= maxi(0, classes.find(min_weight))


## A stake into a Hollow (and the stakes wear).
func _stake(enemy: Enemy, base: float) -> void:
	var c: Dictionary = BaseTech.trap_cfg("spike_pit")
	var frac: float = piece.hp / maxf(1.0, piece.max_hp())
	var info := DamageInfo.make(BaseTech.trap_damage(base, frac, float(c.get("dull_below", 0.35))), &"pierce", &"base_trap", piece.piece_id)
	info.hit_pos = enemy.global_position + Vector3.UP * 0.5
	info.source_pos = piece.global_position
	info.direction = Vector3.UP
	Audio.play_3d(&"sfx/spike_pit_hit", info.hit_pos, {"volume_db": -4.0})
	enemy.take_damage(info)
	_wear(float(c.get("wear", 5.0)))


func _wear(amount: float) -> void:
	if amount <= 0.0 or piece == null or not is_instance_valid(piece) or piece.manager == null:
		return
	var wear := DamageInfo.make(amount, &"wear", &"wear", &"")
	wear.hit_pos = piece.global_position + Vector3.UP * 0.2
	wear.direction = Vector3.UP
	piece.take_damage(wear)


func _hurt_player(pl: Player, amount: float, type: StringName) -> void:
	if pl.state == null or not pl.state.stats.alive:
		return
	var info := DamageInfo.make(amount, type, &"trap", piece.piece_id)
	info.hit_pos = pl.global_position + Vector3.UP * 0.3
	info.source_pos = piece.global_position
	info.direction = Vector3.UP
	pl.take_damage(info)


func _process(delta: float) -> void:
	_player_cd = maxf(0.0, _player_cd - delta)
	_cooldown = maxf(0.0, _cooldown - delta)


func _physics_process(delta: float) -> void:
	if trap == "spike_pit":
		_pit_step(delta)
	elif power == "floodlight":
		_flood_step(delta)
	elif power == "turret":
		_turret_step(delta)


## Hollowed in the pit: held where they fell in, then slowed, and staked again every tick.
func _pit_step(delta: float) -> void:
	if _inside.is_empty():
		return
	var c: Dictionary = BaseTech.trap_cfg("spike_pit")
	var slow: float = clampf(float(c.get("slow", 0.3)), 0.0, 1.0)
	for e: Variant in _inside.keys():
		var enemy := e as Enemy
		if enemy == null or not is_instance_valid(enemy) or not enemy.is_alive() or piece.hp <= 0.0:
			_inside.erase(e)
			continue
		var s: Dictionary = _inside[e]
		var cur: Vector3 = enemy.global_position
		var prev: Vector3 = s["prev"]
		var to: Vector3
		if float(s["stuck"]) > 0.0:
			s["stuck"] = float(s["stuck"]) - delta
			to = s["at"]
		else:
			to = prev + (cur - prev) * slow
		enemy.global_position = Vector3(to.x, cur.y, to.z)
		s["prev"] = enemy.global_position
		s["t"] = float(s["t"]) - delta
		if float(s["t"]) <= 0.0:
			s["t"] = float(c.get("tick_seconds", 1.0))
			_stake(enemy, float(c.get("tick_damage", 8.0)))
			if not is_instance_valid(piece) or piece.hp <= 0.0:
				return


## Drops the deadfall's log: everything under it is hit; the trap is sprung until lifted.
func drop() -> void:
	var st: Dictionary = BaseTechManager.state_of(piece)
	if st.is_empty() or not bool(st.get("armed", true)):
		return
	st["armed"] = false
	var c: Dictionary = BaseTech.trap_cfg("deadfall")
	var at: Vector3 = piece.global_position + Vector3.UP * 0.4
	Audio.play_3d(&"sfx/deadfall_drop", at, {"volume_db": 2.0, "max_distance": 70.0})
	if Stimuli.current != null:
		Stimuli.current.emit_sound(at, float(c.get("noise", 30.0)), &"trap", piece.piece_id)
	if _log != null:
		var down: Transform3D = _log_down()
		if is_inside_tree():
			var tw := create_tween()
			tw.tween_property(_log, "transform", down, 0.22).set_ease(Tween.EASE_IN).set_trans(Tween.TRANS_QUAD)
		else:
			_log.transform = down
	for b: Node3D in _area.get_overlapping_bodies() if _area != null and _area.is_inside_tree() else []:
		var enemy := b as Enemy
		if enemy != null and enemy.is_alive():
			var info := DamageInfo.make(BaseTech.trap_damage(float(c.get("damage", 110.0))), &"blunt", &"base_trap", piece.piece_id)
			info.hit_pos = enemy.global_position + Vector3.UP * 1.4
			info.source_pos = at + Vector3.UP
			info.direction = Vector3.DOWN
			info.stagger = float(c.get("stagger", 1.0))
			enemy.take_damage(info)
		elif b is Player:
			_hurt_player(b as Player, float(c.get("player_damage", 45.0)), &"blunt")
	_wear(float(c.get("wear", 20.0)))


## The tripwire bell rings: heard by everything around, and the player is told from where.
func ring() -> void:
	var c: Dictionary = BaseTech.trap_cfg("tripwire")
	_cooldown = float(c.get("cooldown", 8.0))
	var at: Vector3 = piece.global_position + Vector3.UP * 0.5
	Audio.play_3d(&"sfx/tripwire_bell", at, {"volume_db": 2.0, "max_distance": 90.0})
	if Stimuli.current != null:
		Stimuli.current.emit_sound(at, float(c.get("noise", 34.0)), &"trap", piece.piece_id)
	_warn("The tripwire bell is ringing", at, float(c.get("warn_radius", 160.0)))
	_wear(float(c.get("wear", 0.0)))


func _warn(what: String, at: Vector3, radius: float) -> void:
	var pl: Node3D = Game.world.get(&"player") if Game.world != null else null
	if pl == null or pl.global_position.distance_to(at) > radius:
		return
	Events.player_status_message.emit("%s: %s." % [what, BaseTech.bearing_text(pl.global_position, at)], &"warning")


# --- Sensors ---------------------------------------------------------------------------------------

## The nearest living Hollow within `r` of `from` (in sight when `sight`).
func _nearest_enemy(from: Vector3, r: float, sight: bool) -> Enemy:
	var best: Enemy = null
	var best_d: float = r
	for n: Node in get_tree().get_nodes_in_group(&"enemies"):
		var e := n as Enemy
		if e == null or not e.is_alive():
			continue
		var d: float = e.global_position.distance_to(from)
		if d >= best_d:
			continue
		if sight and not _sees(from, e):
			continue
		best = e
		best_d = d
	return best


func _sees(from: Vector3, e: Enemy) -> bool:
	var space: PhysicsDirectSpaceState3D = get_world_3d().direct_space_state if is_inside_tree() else null
	if space == null:
		return true
	var q := PhysicsRayQueryParameters3D.create(from, e.global_position + Vector3.UP * 1.1, SHOT_MASK, [piece.get_rid()])
	var hit: Dictionary = space.intersect_ray(q)
	return hit.is_empty() or hit.get("collider") == e or (hit.get("collider") is Node and (hit["collider"] as Node).is_ancestor_of(e)) \
		or (hit.get("collider") is Node and e.is_ancestor_of(hit["collider"] as Node))


func _flood_step(delta: float) -> void:
	_hold_t = maxf(0.0, _hold_t - delta)
	_scan_t -= delta
	if _scan_t > 0.0:
		return
	_scan_t = SCAN_SECONDS
	if not BaseTechManager.is_powered(piece):
		_set_light(false)
		return
	var c: Dictionary = BaseTech.power_cfg("floodlight")
	var e: Enemy = _nearest_enemy(piece.global_position + Vector3.UP, float(c.get("detect_range", 20.0)), false)
	if e != null:
		if _hold_t <= 0.0 and _now() - _warn_t >= float(c.get("warn_cooldown", 25.0)):
			_warn_t = _now()
			_warn("The floodlight caught movement", e.global_position, float(c.get("warn_radius", 160.0)))
		_hold_t = float(c.get("hold_seconds", 8.0))
		if _head != null:
			_aim(e.global_position, 0.5)
	_set_light(_hold_t > 0.0)


func _turret_step(delta: float) -> void:
	_fire_t -= delta
	if _fire_t > 0.0:
		return
	var t: Dictionary = BaseTech.power_cfg("turret")
	_fire_t = SCAN_SECONDS
	if not BaseTechManager.is_powered(piece):
		return
	var st: Dictionary = BaseTechManager.peek(piece)
	if int(st.get("ammo", 0)) <= 0:
		return
	var eye: Vector3 = piece.global_position + Vector3.UP * float(t.get("height", 1.0))
	var e: Enemy = _nearest_enemy(eye, float(t.get("range", 14.0)), true)
	if e == null:
		return
	fire_at(e)
	_fire_t = float(t.get("interval", 0.7))


## One nail into `e`: damage, a nail spent, the shot heard.
func fire_at(e: Enemy) -> void:
	var t: Dictionary = BaseTech.power_cfg("turret")
	var st: Dictionary = BaseTechManager.state_of(piece)
	if int(st.get("ammo", 0)) <= 0:
		return
	st["ammo"] = int(st["ammo"]) - 1
	var eye: Vector3 = piece.global_position + Vector3.UP * float(t.get("height", 1.0))
	if _head != null:
		_aim(e.global_position, 1.0)
	var info := DamageInfo.make(BaseTech.trap_damage(float(t.get("damage", 16.0))), &"pierce", &"sentry", piece.piece_id)
	info.hit_pos = e.global_position + Vector3.UP * 1.2
	info.source_pos = eye
	info.direction = (info.hit_pos - eye).normalized()
	info.stagger = 0.2
	Audio.play_3d(&"sfx/sentry_shot", eye, {"volume_db": 0.0, "pitch": 1.5, "max_distance": 60.0})
	if Stimuli.current != null:
		Stimuli.current.emit_sound(eye, float(t.get("noise", 22.0)), &"trap", piece.piece_id)
	e.take_damage(info)
	if int(st["ammo"]) <= 0 and not _empty_warned:
		_empty_warned = true
		_warn("The nail sentry is empty", eye, 80.0)
	elif int(st["ammo"]) > 0:
		_empty_warned = false


## Turns the head toward `at` (yaw only; `weight` 1 snaps).
func _aim(at: Vector3, weight: float) -> void:
	var d: Vector3 = at - _head.global_position
	if Vector2(d.x, d.z).length() < 0.05:
		return
	var yaw: float = atan2(d.x, d.z) - piece.global_rotation.y
	_head.rotation.y = lerp_angle(_head.rotation.y, yaw, weight)


static func _now() -> float:
	return Stimuli.current.now() if Stimuli.current != null else Time.get_ticks_msec() / 1000.0
