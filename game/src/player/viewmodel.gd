class_name ViewModel
extends Node3D
## First-person presentation (ADR-0029): the generated arms (models/characters/fp_arms.glb,
## docs/CHARACTERS.md) in the hold pose of the item in hand (data/config/viewmodel.json): tools
## low and to the right, two-handed weapons, the torch held up in the left hand, food, bottles,
## the Field Manual while laying out a blueprint, a log on the shoulder. On top of the baked poses
## ViewModelMotion adds breathing, sway, inertia, a footstep bob and the lowered sprint pose; swings
## are per class (chop, slash, bash, stab, dig, punch, torch) and freeze for a beat with a camera
## kick when they connect; the guard, staggers, eating and drinking have their own motions. The
## tether is the unit bolted over the left wrist: raising the wrist to read it narrows the view and
## its screen shows the live tether UI (Tether renders into it). Everything draws with its own
## field of view and squeezed depth (FpMaterials). Without the arms model the item floats at a
## rest pose and swings procedurally.

const ARMS_PATH: String = "res://assets/generated/models/characters/fp_arms.glb"
const VM_PATH: String = "res://assets/generated/models/viewmodels/%s.glb"
const MANUAL_MODEL: StringName = &"field_manual"
const FLIPBOOK: String = "res://assets/generated/textures/fx_fire_flipbook.png"
## Loops of the arms built before the hold classes (ADR-0029) existed.
const LEGACY_LOOPS: Array[StringName] = [&"fp_idle", &"fp_walk_bob", &"fp_idle_grip", &"fp_walk_grip", &"fp_carry_log"]
## Seconds between shelter checks (weather_exposure).
const SHELTER_CHECK: float = 0.25

var cfg: Dictionary = {}
var motion := ViewModelMotion.new()
var tether := TetherRaise.new()
## The hold class of what is in hand (ViewModelHolds).
var hold_class: StringName = ViewModelHolds.EMPTY
## QA (fp_preview): forces the base loop (fp_carry_log, fp_blueprint) without a player or building.
var qa_base: StringName = &""

var _rig: Node3D
var _item_root: Node3D
var _arms: Node3D = null
var _anim: AnimationPlayer = null
var _sock: Dictionary = {}
var _held: Node3D = null
var _held_def: ItemDef = null
var _held_hand: String = "R"
## Shown instead of the held item: the Field Manual while laying out a blueprint, the log on the
## shoulder while carrying.
var _manual: Node3D = null
var _log: Node3D = null
var _flame: Node3D = null
## The held flame's current lean (camera frame), springing towards what the turn and walk ask.
var _flame_lean := Vector3.ZERO
var _lit: bool = false
var _base: StringName = &""
var _action: StringName = &""
var _action_end: float = 0.0
var _hitstop: float = 0.0
var _guard: bool = false
var _t: float = 0.0
var _prev_basis := Basis()
var _have_basis: bool = false
var _screen_mesh: MeshInstance3D = null
var _screen_surface: int = -1
var _screen_mat: StandardMaterial3D = null
var _player: Player = null
var _loops: Dictionary = {}
## The weather_exposure the arms and what they hold draw with: 0 indoors or under a roof, so the
## rain gloss and snow on the skin and sleeves stay outside (as on PoiBuilder's indoor pieces).
var exposure: float = 1.0
var _shelter_t: float = 0.0
# Procedural fallback (no arms model).
var _swing_t: float = -1.0
var _swing_len: float = 0.8
var _recoil: float = 0.0
## Held-item nodes a use turned (viewmodel.json `uses.<use>.parts`), to put back when it ends.
var _posed_parts: Array[Node3D] = []
var _rest := Transform3D(Basis.from_euler(Vector3(deg_to_rad(8.0), deg_to_rad(-12.0), deg_to_rad(4.0))), Vector3(0.28, -0.3, -0.52))


func _ready() -> void:
	cfg = ViewModelHolds.config()
	FpMaterials.configure(cfg)
	motion.setup(cfg)
	tether.setup(cfg)
	_player = owner as Player if owner is Player else null
	_rig = Node3D.new()
	_rig.name = "Rig"
	add_child(_rig)
	_item_root = Node3D.new()
	_item_root.name = "Held"
	add_child(_item_root)
	_item_root.transform = _rest
	for cls: String in cfg.get("holds", {}):
		for n: StringName in [ViewModelHolds.idle_action(StringName(cls)), ViewModelHolds.guard_action(StringName(cls)), ViewModelHolds.tether_action(StringName(cls))]:
			_loops[n] = true
	for n: StringName in LEGACY_LOOPS:
		_loops[n] = true
	var arms_scene: PackedScene = load(ARMS_PATH) as PackedScene if ResourceLoader.exists(ARMS_PATH) else null
	if arms_scene != null:
		_arms = arms_scene.instantiate() as Node3D
		_arms.name = "Arms"
		# Authored looking down Blender -Y, which imports facing +Z: turn it to the camera's -Z.
		_arms.rotation_degrees = Vector3(0.0, 180.0, 0.0)
		_rig.add_child(_arms)
		FpMaterials.apply(_arms)
		for sd: String in ["R", "L"]:
			_sock[sd] = _find_socket(_arms, "socket_hand.%s" % sd)
		_anim = _arms.find_child("AnimationPlayer", true, false) as AnimationPlayer
		if _anim != null:
			for a: StringName in _anim.get_animation_list():
				if _loops.has(a):
					_anim.get_animation(a).loop_mode = Animation.LOOP_LINEAR
			_anim.animation_finished.connect(_on_animation_finished)
		_find_tether_screen()
	if _player != null:
		_player.landed.connect(motion.landed)
	Events.player_damaged.connect(_on_player_damaged)
	_update_base()


## Bone-attached empties import under BoneAttachment3D, with "." replaced in their names.
static func _find_socket(root: Node, socket: String) -> Node3D:
	var n: Node = root.find_child(socket, true, false)
	if n == null:
		n = root.find_child(socket.replace(".", "_"), true, false)
	return n as Node3D


func has_arms() -> bool:
	return _arms != null and _anim != null


func has_action(anim_name: StringName) -> bool:
	return _anim != null and _anim.has_animation(anim_name)


# --- Items ---------------------------------------------------------------------------------

func show_item(item_id: StringName) -> void:
	if _held != null:
		_held.queue_free()
		_held = null
	_flame = null
	_lit = false
	_held_def = Content.item(item_id) if item_id != &"" else null
	hold_class = ViewModelHolds.hold_class(_held_def, cfg)
	_guard = false
	motion.start_equip()
	if _held_def != null:
		_held = _make_item(_held_def)
		_set_layers(_held)
		if has_arms():
			_attach_held(ViewModelHolds.item_hand(hold_class, cfg))
		else:
			_item_root.add_child(_held)
			_held.rotation_degrees = _rest_pose(_held, _held_def)
		FpMaterials.apply(_held)
		_apply_exposure(_held)
	if _action != &"" and _anim != null:
		_action = &""
	_update_base(true)


func _make_item(def: ItemDef) -> Node3D:
	var vm_id: String = str(def.equip.get("viewmodel", ""))
	var vm_scene: PackedScene = load(VM_PATH % vm_id) as PackedScene if vm_id != "" and ResourceLoader.exists(VM_PATH % vm_id) else null
	if vm_scene != null:
		return vm_scene.instantiate() as Node3D
	var node: Node3D = ItemVisuals.make_model(def.id)
	# Ground models lie in their resting pose; held ones stand up, longest side along the grip.
	var it: Dictionary = ViewModelHolds.hold(hold_class, cfg).get("item", {})
	if bool(it.get("upright", false)):
		var bb: AABB = _local_aabb(node)
		var longest: int = 0 if bb.size.x >= maxf(bb.size.y, bb.size.z) else (1 if bb.size.y >= bb.size.z else 2)
		var wrap := Node3D.new()
		wrap.add_child(node)
		if longest == 0:
			node.rotation_degrees = Vector3(0, 0, 90)
		elif longest == 2:
			node.rotation_degrees = Vector3(90, 0, 0)
		return wrap
	return node


## Puts the held item in a hand socket with its hold's placement, centred on the grip when the
## hold asks for it (cans, bottles: the fist closes round their middle).
func _attach_held(hand: String) -> void:
	if _held == null:
		return
	var sock: Node3D = _sock.get(hand, null)
	if sock == null:
		sock = _sock.get("R", null)
	if sock == null:
		return
	if _held.get_parent() != null:
		_held.get_parent().remove_child(_held)
	sock.add_child(_held)
	_held_hand = hand
	var xf: Transform3D = ViewModelHolds.item_transform(_held_def, hold_class, cfg)
	var it: Dictionary = ViewModelHolds.hold(hold_class, cfg).get("item", {})
	var sc: float = float(it.get("scale", 1.0))
	var c: Array = it.get("center", [])
	if c.size() == 3:
		var bb: AABB = _local_aabb(_held)
		var at: Vector3 = bb.position + bb.size * Vector3(float(c[0]), float(c[1]), float(c[2]))
		xf.origin -= xf.basis * (at * sc)
	_held.transform = xf
	_held.scale = Vector3.ONE * sc


static func _local_aabb(root: Node3D) -> AABB:
	var out := AABB()
	var first: bool = true
	var inv: Transform3D = root.global_transform.affine_inverse() if root.is_inside_tree() else Transform3D()
	for mi: Node in root.find_children("*", "MeshInstance3D", true, false):
		var m: MeshInstance3D = mi
		if m.mesh == null:
			continue
		var xf: Transform3D = (inv * m.global_transform) if root.is_inside_tree() else _rel_xf(root, m)
		var bb: AABB = xf * m.mesh.get_aabb()
		out = bb if first else out.merge(bb)
		first = false
	return out


static func _rel_xf(root: Node3D, n: Node3D) -> Transform3D:
	var xf := Transform3D()
	var cur: Node = n
	while cur != null and cur != root:
		if cur is Node3D:
			xf = (cur as Node3D).transform * xf
		cur = cur.get_parent()
	return xf


## Floating pose for a viewmodel when there are no arms (models import facing the camera).
static func _rest_pose(node: Node3D, def: ItemDef) -> Vector3:
	var pointing: bool = false
	for s: String in ["socket_muzzle", "socket_light", "socket_flame"]:
		if node.find_child(s, true, false) != null:
			pointing = true
	if def != null and def.id == &"torch":
		return Vector3(-50.0, 180.0, 0.0)
	if pointing:
		return Vector3(0.0, 180.0, 0.0)
	if def != null and str(def.equip.get("damage_type", "")) == "pierce":
		return Vector3(-80.0, 0.0, 0.0)
	return Vector3(30.0, 180.0, 0.0)


func _set_layers(n: Node) -> void:
	if n is GeometryInstance3D:
		(n as GeometryInstance3D).cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	for c: Node in n.get_children():
		_set_layers(c)


# --- Actions -------------------------------------------------------------------------------

## Plays a one-shot arms action over `duration` seconds (its own length when 0). Also answers the
## older calls: fp_raise_wrist / fp_lower_wrist raise and lower the tether, fp_use is the held
## item's use. Returns false if the arms or the action are missing so callers can fall back.
func play_action(anim_name: StringName, duration: float = 0.0, _hold: bool = false) -> bool:
	match anim_name:
		&"fp_raise_wrist":
			set_tether_raised(true)
			return has_arms()
		&"fp_lower_wrist":
			set_tether_raised(false)
			return has_arms()
		&"fp_use":
			return play_use(ViewModelHolds.use_action(_held_def, hold_class, cfg), duration)
	return _play_once(anim_name, duration)


func _play_once(anim_name: StringName, duration: float) -> bool:
	if not has_action(anim_name):
		return false
	var length: float = _anim.get_animation(anim_name).length
	# play() keeps going if this action is still running (a swing that ran late on its hit-stop):
	# start it over instead.
	if _anim.current_animation == anim_name:
		_anim.seek(0.0, true)
	_anim.play(anim_name, 0.06)
	_anim.speed_scale = length / duration if duration > 0.05 else 1.0
	_action = anim_name
	_action_end = _t + (duration if duration > 0.05 else length)
	_hitstop = 0.0
	return true


## QA (fp_preview, screenshots): holds the arms `at` seconds into an action until released.
func freeze_action(anim_name: StringName, at: float) -> bool:
	if not has_action(anim_name):
		return false
	_anim.play(anim_name, 0.0)
	_anim.seek(at, true)
	_anim.speed_scale = 0.0
	_action = anim_name
	_action_end = INF
	_hitstop = 0.0
	return true


func release_action() -> void:
	if _action == &"":
		return
	_action = &""
	if _anim != null:
		_anim.speed_scale = 1.0
	_update_base(true)


## A swing of the held item over its attack_time (its class's style, or punching bare-handed).
func play_swing(duration: float) -> void:
	var style: StringName = ViewModelHolds.attack_style(_held_def, hold_class, cfg)
	play_attack(style if style != &"" else &"punch", duration)


func play_attack(style: StringName, duration: float) -> void:
	tether.set_raised(false)
	if _play_once(StringName("fp_%s" % style), duration):
		return
	# Older arms: their generic chop / stab.
	if _play_once(&"fp_stab" if style in [&"stab", &"dig"] else &"fp_swing", duration):
		return
	_swing_t = 0.0
	_swing_len = maxf(0.2, duration)


## Eat, drink, apply, place, throw, light...: false when the arms have no such action.
func play_use(use: StringName, duration: float = 0.0) -> bool:
	if use == &"":
		return false
	if _play_once(StringName("fp_%s" % use), duration):
		return true
	return _play_once(&"fp_use", duration) if use in [&"eat", &"drink", &"apply"] else false


## Turns the held item over to look at it (viewmodel.json `uses.inspect_<hold class>`): false when
## the hold has no inspect.
func play_inspect() -> bool:
	tether.set_raised(false)
	return play_use(StringName("inspect_%s" % hold_class))


func play_recoil() -> void:
	_recoil = 1.0
	motion.gun_recoil(1.0)


func set_lit(on: bool) -> void:
	_lit = on
	_update_flame()


## The swing connected with `surface` (ViewModelHolds.surface_kind): a beat of hit-stop, the
## camera kicks, the tool recoils off it.
func impact(surface: StringName) -> void:
	var surf: Dictionary = (cfg.get("impact", {}) as Dictionary).get("surfaces", {})
	var s: Dictionary = surf.get(String(surface), surf.get("solid", {}))
	_hitstop = maxf(_hitstop, float(s.get("hitstop", 0.05)))
	var k: Array = s.get("kick", [-1.0, 0.0, 0.0])
	motion.impact(Vector3(float(k[0]), float(k[1]), float(k[2])), float(s.get("recoil", 0.01)))


func set_guard(on: bool) -> void:
	if on == _guard:
		return
	_guard = on
	if on:
		tether.set_raised(false)
	_update_base()


func guarding() -> bool:
	return _guard


## A blow landed on the raised guard: the weapon is knocked back.
func blocked(amount: float) -> void:
	var st: Dictionary = cfg.get("stagger", {})
	motion.stagger(float(st.get("block_deg", 4.0)) * clampf(amount / 10.0, 0.4, 1.5), 0.01, 1.0)


func _on_player_damaged(player_id: StringName, amount: float, source: Dictionary) -> void:
	if _player == null or _player.state == null or player_id != _player.state.id:
		return
	var st: Dictionary = cfg.get("stagger", {})
	var deg: float = minf(amount * float(st.get("deg_per_damage", 0.35)), float(st.get("max_deg", 10.0)))
	var side: float = 1.0
	var from: Array = source.get("from", [])
	if from.size() == 3:
		var to_src: Vector3 = Vector3(float(from[0]), float(from[1]), float(from[2])) - _player.global_position
		side = -1.0 if to_src.dot(_player.global_transform.basis.x) > 0.0 else 1.0
	motion.stagger(deg, amount * float(st.get("pos_per_damage", 0.0012)), side)


# --- The tether ------------------------------------------------------------------------------

func set_tether_raised(up: bool) -> void:
	if tether.set_raised(up):
		_update_base()


func tether_raised() -> bool:
	return tether.wants_up()


## The tether's screen (fp_tether_screen) on the arms, if the model has one.
func has_tether_screen() -> bool:
	return _screen_mesh != null


## Shows `tex` (the tether UI's viewport) on the arms' tether screen. Returns false without arms.
func attach_tether_screen(tex: Texture2D) -> bool:
	if _screen_mesh == null:
		return false
	var m := StandardMaterial3D.new()
	m.albedo_color = Color(0.015, 0.02, 0.018)
	m.emission_enabled = true
	m.emission_texture = tex
	# The UI is the light: multiply, or the default add puts white under it and the screen glares.
	m.emission_operator = BaseMaterial3D.EMISSION_OP_MULTIPLY
	m.emission = Color.WHITE
	m.emission_energy_multiplier = _screen_energy(0.0)
	m.roughness = 0.16
	m.metallic_specular = 0.65
	_screen_mat = FpMaterials.fp_material(m) as StandardMaterial3D
	_screen_mesh.set_surface_override_material(_screen_surface, _screen_mat)
	return true


func _find_tether_screen() -> void:
	for n: Node in _arms.find_children("*", "MeshInstance3D", true, false):
		var mi: MeshInstance3D = n
		if mi.mesh == null:
			continue
		for i: int in mi.mesh.get_surface_count():
			var m: Material = mi.mesh.surface_get_material(i)
			if m != null and m.resource_name.contains("tether_screen"):
				_screen_mesh = mi
				_screen_surface = i
				return


func _screen_energy(raise: float) -> float:
	var e: Array = (cfg.get("tether", {}) as Dictionary).get("screen_energy", [0.35, 1.3])
	return lerpf(float(e[0]), float(e[1]), raise)


# --- Lights ----------------------------------------------------------------------------------

## Where a held light burns (the torch's flame, the flashlight's lens), for the light to follow.
func light_anchor() -> Node3D:
	if _held == null:
		return null
	for s: String in ["socket_flame", "socket_light"]:
		var n: Node3D = _held.find_child(s, true, false) as Node3D
		if n != null:
			return n
	return null


## A held flame burns on the item's socket_flame, in the socket's own space (local_coords): it
## moves with the hand exactly, never trailing behind a turn, and draws with the viewmodel's field
## of view (FpMaterials) like the hand holding it, which world-space particles never could. Each
## frame the flame is turned to stand up in the world, leaning a little against the view's turn
## and the player's walk (_flame_follow); being local, that turns the whole flame at once.
func _update_flame() -> void:
	if _flame != null and is_instance_valid(_flame):
		_flame.queue_free()
	_flame = null
	_flame_lean = Vector3.ZERO
	_set_ember(_lit)
	if not _lit or _held == null or DisplayServer.get_name() == "headless":
		return
	_flame = attach_flame(_held, _held_def.id if _held_def != null else &"")
	_flame_follow(0.0, Vector2.ZERO, Vector3.ZERO)


## The torch's burnt top glows like coals while it burns (item_torch_ember is a light_source 1
## material: it reads the instance's light_lit).
func _set_ember(on: bool) -> void:
	if _held == null:
		return
	for n: Node in _held.find_children("*", "GeometryInstance3D", true, false):
		(n as GeometryInstance3D).set_instance_shader_parameter(&"light_lit", 1.0 if on else 0.0)


## Builds the flame for `item_id` (flame_spec) under `held`'s socket_flame, converted for the
## viewmodel (FpMaterials). Null when the item has no flame socket.
static func attach_flame(held: Node3D, item_id: StringName) -> Node3D:
	var sock: Node3D = held.find_child("socket_flame", true, false) as Node3D if held != null else null
	if sock == null:
		return null
	var f: Node3D = build_flame(item_id)
	sock.add_child(f)
	FpMaterials.apply(f)
	return f


## The flame's shape per item: a lighter's is a small steady teardrop (2-3 cm, blue at the base,
## yellow-orange above); a torch's licks off the flipbook a hand-span or two high, with embers.
## `rise` lifts the flame's base above the socket (the torch's sits inside the cloth head), `size`
## is the sprite (m), `speed` / `gravity` how far the licks travel in their `lifetime`, `lean_deg`
## how far it may lean against a turn. Any other item with a socket_flame (a candle, a match)
## burns like the lighter until it has its own entry.
const FLAMES: Dictionary = {
	"lighter": {"style": "teardrop", "size": [0.012, 0.026], "rise": 0.012, "amount": 5, "lifetime": 0.3,
		"speed": [0.0, 0.006], "gravity": 0.0, "radius": 0.0006, "embers": false, "lean_deg": 8.0},
	"torch": {"style": "fire", "size": [0.085, 0.13], "rise": 0.035, "amount": 16, "lifetime": 0.5,
		"speed": [0.1, 0.2], "gravity": 0.3, "radius": 0.02, "embers": true, "lean_deg": 20.0},
}


## The flames' particle step rate (see _flame_particles).
const FLAME_FPS: int = 30


static func flame_spec(item_id: StringName) -> Dictionary:
	return FLAMES.get(String(item_id), FLAMES["lighter"])


## How high the flame reaches above its socket (m), for the culling box and the tests.
static func flame_height(spec: Dictionary) -> float:
	var t: float = float(spec["lifetime"])
	var v: float = float((spec["speed"] as Array)[1])
	var travel: float = v * t + 0.5 * float(spec["gravity"]) * t * t
	return float(spec["rise"]) + travel + float((spec["size"] as Array)[1]) * 0.5


## The flame node ("Flame") for an item: its particles, all local to it, each with a culling box
## that holds them (not the old metre-wide one).
static func build_flame(item_id: StringName) -> Node3D:
	var spec: Dictionary = flame_spec(item_id)
	var f := Node3D.new()
	f.name = "Flame"
	f.set_meta(&"lean_deg", float(spec["lean_deg"]))
	f.add_child(_flame_particles(spec))
	if bool(spec["embers"]):
		f.add_child(_ember_particles(spec))
	return f


static func _flame_particles(spec: Dictionary) -> GPUParticles3D:
	var size := Vector2(float((spec["size"] as Array)[0]), float((spec["size"] as Array)[1]))
	var teardrop: bool = str(spec["style"]) == "teardrop"
	var p := GPUParticles3D.new()
	p.name = "Fire"
	p.amount = int(spec["amount"])
	p.lifetime = float(spec["lifetime"])
	p.local_coords = true
	# Stepped at a fixed rate (interpolated between steps): a frame longer than the flame's short
	# lifetime (a hitch, a slow renderer) would otherwise skip every respawn and leave it dark.
	p.fixed_fps = FLAME_FPS
	var h: float = flame_height(spec)
	var r: float = maxf(size.x, size.y) * 0.6 + float(spec["radius"]) + h * 0.15
	p.visibility_aabb = AABB(Vector3(-r, -size.y * 0.5, -r), Vector3(2.0 * r, h + size.y, 2.0 * r))
	var m := ParticleProcessMaterial.new()
	m.direction = Vector3(0, 1, 0)
	m.spread = 4.0 if teardrop else 8.0
	m.initial_velocity_min = float((spec["speed"] as Array)[0])
	m.initial_velocity_max = float((spec["speed"] as Array)[1])
	m.gravity = Vector3(0, float(spec["gravity"]), 0)
	m.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	m.emission_sphere_radius = float(spec["radius"])
	m.emission_shape_offset = Vector3(0, float(spec["rise"]), 0)
	var sc := Curve.new()
	var g := Gradient.new()
	if teardrop:
		# Overlapping, nearly still teardrops fading in and out: steady, with a slight flicker.
		m.scale_min = 0.85
		m.scale_max = 1.0
		sc.add_point(Vector2(0.0, 0.85))
		sc.add_point(Vector2(0.5, 1.0))
		sc.add_point(Vector2(1.0, 0.9))
		g.offsets = PackedFloat32Array([0.0, 0.3, 0.7, 1.0])
		g.colors = PackedColorArray([Color(1, 1, 1, 0), Color(1, 1, 1, 0.75), Color(1, 1, 1, 0.75), Color(1, 1, 1, 0)])
	else:
		m.scale_min = 0.6
		m.scale_max = 1.0
		sc.add_point(Vector2(0.0, 0.7))
		sc.add_point(Vector2(0.3, 1.0))
		sc.add_point(Vector2(1.0, 0.2))
		g.offsets = PackedFloat32Array([0.0, 0.15, 1.0])
		g.colors = PackedColorArray([Color(1.0, 0.9, 0.6, 0.0), Color(1.0, 0.85, 0.55, 1.0), Color(0.7, 0.18, 0.05, 0.0)])
	var st := CurveTexture.new()
	st.curve = sc
	m.scale_curve = st
	var gt := GradientTexture1D.new()
	gt.gradient = g
	m.color_ramp = gt
	var q := QuadMesh.new()
	q.size = size
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	mat.vertex_color_use_as_albedo = true
	if not teardrop and ResourceLoader.exists(FLIPBOOK):
		mat.albedo_color = Color(1.0, 0.85, 0.6) * 1.5
		mat.albedo_texture = load(FLIPBOOK)
		mat.particles_anim_h_frames = 8
		mat.particles_anim_v_frames = 8
		mat.particles_anim_loop = true
		m.anim_speed_min = 1.0
		m.anim_speed_max = 1.3
		m.anim_offset_max = 1.0
	else:
		mat.albedo_color = Color(1.0, 1.0, 1.0) * 1.4
		mat.albedo_texture = teardrop_texture()
	q.material = mat
	p.process_material = m
	p.draw_pass_1 = q
	return p


static func _ember_particles(spec: Dictionary) -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.name = "Embers"
	p.amount = 6
	p.lifetime = 0.8
	p.fixed_fps = FLAME_FPS
	p.local_coords = true
	p.visibility_aabb = AABB(Vector3(-0.2, -0.05, -0.2), Vector3(0.4, 0.5, 0.4))
	var m := ParticleProcessMaterial.new()
	m.direction = Vector3(0, 1, 0)
	m.spread = 20.0
	m.initial_velocity_min = 0.15
	m.initial_velocity_max = 0.35
	m.gravity = Vector3(0, 0.25, 0)
	m.turbulence_enabled = true
	m.turbulence_noise_strength = 0.3
	m.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	m.emission_sphere_radius = float(spec["radius"])
	m.emission_shape_offset = Vector3(0, float(spec["rise"]), 0)
	m.scale_min = 0.4
	m.scale_max = 1.0
	var g := Gradient.new()
	g.set_color(0, Color(1.0, 0.75, 0.35, 1.0))
	g.set_color(1, Color(0.9, 0.25, 0.05, 0.0))
	var gt := GradientTexture1D.new()
	gt.gradient = g
	m.color_ramp = gt
	var q := QuadMesh.new()
	q.size = Vector2(0.006, 0.006)
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


static var _teardrop: ImageTexture = null


## A lighter's flame drawn in code (no asset needed): a teardrop, round at the base and drawn to a
## point, blue and dim at the root, yellow-white in the body and orange at the tip.
static func teardrop_texture() -> Texture2D:
	if _teardrop != null:
		return _teardrop
	var w: int = 32
	var h: int = 64
	var img := Image.create(w, h, false, Image.FORMAT_RGBA8)
	var blue := Color(0.22, 0.4, 1.0, 0.6)
	var body := Color(1.0, 0.86, 0.5, 1.0)
	var tip := Color(1.0, 0.5, 0.12, 0.9)
	for y: int in h:
		var t: float = 1.0 - (float(y) + 0.5) / float(h)
		var half: float
		if t < 0.3:
			var k: float = (0.3 - t) / 0.28
			half = 0.8 * sqrt(maxf(0.0, 1.0 - k * k))
		else:
			half = 0.8 * pow(maxf(0.0, 1.0 - (t - 0.3) / 0.66), 1.3)
		for x: int in w:
			var u: float = absf((float(x) + 0.5) / float(w) * 2.0 - 1.0)
			var a: float = 0.0 if half <= 0.0 else 1.0 - smoothstep(half * 0.55, half, u)
			var c: Color = blue.lerp(body, smoothstep(0.16, 0.36, t)).lerp(tip, smoothstep(0.55, 0.95, t))
			# The dim core just above the wick: the flame burns on its skin.
			var core: float = (1.0 - smoothstep(0.0, 0.45, u / maxf(half, 0.001))) * (1.0 - smoothstep(0.2, 0.45, t)) * smoothstep(0.05, 0.15, t)
			c = c.lerp(Color(0.3, 0.3, 0.6, c.a), core * 0.6)
			img.set_pixel(x, y, Color(c.r, c.g, c.b, a * c.a))
	img.generate_mipmaps()
	_teardrop = ImageTexture.create_from_image(img)
	return _teardrop


## The flame's world orientation: up (plus `lean`, in the camera's frame) and facing the camera.
static func flame_basis(cam_basis: Basis, lean: Vector3) -> Basis:
	var y: Vector3 = (Vector3.UP + cam_basis * lean).normalized()
	var z: Vector3 = cam_basis.z - y * cam_basis.z.dot(y)
	if z.length_squared() < 1e-6:
		z = cam_basis.y - y * cam_basis.y.dot(y)
	z = z.normalized()
	return Basis(y.cross(z), y, z)


## Stands the flame up and leans it against the view's turn (`look`, rad/s) and the walk (`vel`,
## camera frame), springing back when they stop; the lean is clamped to the flame's lean_deg.
func _flame_follow(delta: float, look: Vector2, vel: Vector3) -> void:
	if _flame == null or not is_instance_valid(_flame) or not _flame.is_inside_tree():
		return
	var cam: Node3D = get_parent() as Node3D
	var cam_basis: Basis = cam.global_transform.basis.orthonormalized() if cam != null else Basis()
	var deg: float = float(_flame.get_meta(&"lean_deg")) if _flame.has_meta(&"lean_deg") else 10.0
	var want := Vector3(look.x * 0.06 - vel.x * 0.05, 0.0, -vel.z * 0.05).limit_length(tan(deg_to_rad(deg)))
	_flame_lean = want if delta <= 0.0 else _flame_lean.lerp(want, 1.0 - exp(-delta * 10.0))
	_flame.global_transform = Transform3D(flame_basis(cam_basis, _flame_lean), _flame.global_position)


# --- Per frame -------------------------------------------------------------------------------

func _on_animation_finished(anim_name: StringName) -> void:
	if anim_name == _action:
		_action = &""
		_update_base(true)


func _placing_blueprint() -> bool:
	var w: Node = Game.world
	var b: Node = w.get(&"building") if w != null else null
	return b != null and b.has_method(&"is_placing") and bool(b.call(&"is_placing"))


func _carrying_logs() -> bool:
	return _player != null and _player.equipment != null and _player.equipment.carried_logs() > 0


## The loop the arms should be in (when no swing or use is playing): carrying logs, laying out a
## blueprint, reading the tether, guarding, or the hold class's idle; older arms fall back to
## their generic idles.
func base_action() -> StringName:
	var want: StringName = ViewModelHolds.idle_action(hold_class)
	if qa_base != &"" and has_action(qa_base):
		want = qa_base
	elif _carrying_logs():
		want = &"fp_carry_log"
	elif _placing_blueprint():
		want = &"fp_blueprint"
	elif tether.wants_up() and has_action(ViewModelHolds.tether_action(hold_class)):
		want = ViewModelHolds.tether_action(hold_class)
	elif _guard and has_action(ViewModelHolds.guard_action(hold_class)):
		want = ViewModelHolds.guard_action(hold_class)
	if not has_action(want):
		want = &"fp_idle_grip" if _held != null and has_action(&"fp_idle_grip") else &"fp_idle"
	if not has_action(want):
		want = ViewModelHolds.idle_action(ViewModelHolds.EMPTY)
	return want


func _update_base(force: bool = false) -> void:
	if _anim == null or _action != &"":
		return
	var want: StringName = base_action()
	if not has_action(want) or (want == _base and not force and _anim.current_animation == want):
		return
	var blend: float = 0.22
	if want == ViewModelHolds.tether_action(hold_class):
		blend = tether.raise_time
	elif _base == ViewModelHolds.tether_action(hold_class):
		blend = tether.lower_time
	elif want == ViewModelHolds.guard_action(hold_class) or _base == ViewModelHolds.guard_action(hold_class):
		blend = float((cfg.get("guard", {}) as Dictionary).get("raise_time", 0.12))
	if _anim.current_animation != want or force:
		_anim.play(want, blend)
	_anim.speed_scale = 1.0
	_base = want
	# Hands busy with the manual or a log put the item away for the moment.
	var busy: bool = want == &"fp_carry_log" or want == &"fp_blueprint"
	if _held != null:
		_held.visible = not busy
	_show_manual(want == &"fp_blueprint")
	_show_log(want == &"fp_carry_log")
	# Reading the tether with a light in the left hand: it moves to the right.
	if _held != null and has_arms():
		var hand: String = ViewModelHolds.item_hand(hold_class, cfg)
		if hand == "L" and want == ViewModelHolds.tether_action(hold_class):
			hand = "R"
		if hand != _held_hand:
			_attach_held(hand)


func _show_manual(on: bool) -> void:
	if not on:
		if _manual != null:
			_manual.visible = false
		return
	if _manual == null and _sock.get("L", null) != null:
		_manual = ItemVisuals.make_model(MANUAL_MODEL)
		(_sock["L"] as Node3D).add_child(_manual)
		var bp: Dictionary = ViewModelHolds.hold(&"blueprint", cfg).get("item", {})
		var r: Array = bp.get("rot", [90, 0, 0])
		var p: Array = bp.get("pos", [0, 0, 0])
		_manual.rotation_degrees = Vector3(float(r[0]), float(r[1]), float(r[2]))
		_manual.position = Vector3(float(p[0]), float(p[1]), float(p[2]))
		_set_layers(_manual)
		FpMaterials.apply(_manual)
		_apply_exposure(_manual)
	if _manual != null:
		_manual.visible = true


## The carried log, resting on the right shoulder (viewmodel.json holds.carry_log.log).
func _show_log(on: bool) -> void:
	if not on:
		if _log != null:
			_log.visible = false
		return
	if _log == null:
		var lc: Dictionary = ViewModelHolds.hold(&"carry_log", cfg).get("log", {})
		var c: Array = lc.get("center", [0.24, -0.1, 0.1])
		var d: Array = lc.get("dir", [0.15, 0.45, -0.88])
		var mi := MeshInstance3D.new()
		mi.name = "CarriedLog"
		mi.mesh = ModelLibrary.mesh(str(lc.get("model", "structures/log_piece")), "log")
		var x := Vector3(float(d[0]), float(d[1]), float(d[2])).normalized()
		var y: Vector3 = x.cross(Vector3.FORWARD).normalized() if absf(x.dot(Vector3.FORWARD)) < 0.99 else Vector3.UP
		mi.transform = Transform3D(Basis(x, y, x.cross(y)), Vector3(float(c[0]), float(c[1]), float(c[2])))
		_log = mi
		_rig.add_child(_log)
		_set_layers(_log)
		FpMaterials.apply(_log)
		_apply_exposure(_log)
	_log.visible = true


func _process(delta: float) -> void:
	_t += delta
	tether.update(delta)
	var cam: Camera3D = get_parent() as Camera3D
	if cam != null:
		visible = cam.current
	var look := Vector2.ZERO
	if cam != null:
		var b: Basis = cam.global_transform.basis
		if _have_basis and delta > 0.0:
			var e: Vector3 = (_prev_basis.inverse() * b).get_euler()
			look = Vector2(e.y, e.x) / delta
		_prev_basis = b
		_have_basis = true
	var vel := Vector3.ZERO
	var speed: float = 0.0
	if _player != null and cam != null:
		vel = cam.global_transform.basis.inverse() * _player.velocity
		speed = _player.horizontal_speed()
		motion.reading = tether.progress()
		motion.update(delta, look, vel, speed, _player.sprinting, _player.crouching, _player.is_on_floor(),
			_player.step_phase(), _player.step_count, float(_player.cfg.get("walk_speed", 3.4)))
	else:
		motion.reading = tether.progress()
		motion.update(delta, look, vel, 0.0, false, false, true, 0.0, 0)
	_rig.transform = motion.rig_transform()
	_flame_follow(delta, look, vel)
	_update_exposure(delta)
	if cam != null and cam.current:
		cam.rotation = motion.camera_kick()
	# Hit-stop: the swing hangs on what it struck, then catches up to finish on time.
	if _anim != null and _action != &"":
		if _hitstop > 0.0:
			_hitstop -= delta
			_anim.speed_scale = 0.0
			if _hitstop <= 0.0:
				var left_anim: float = _anim.current_animation_length - _anim.current_animation_position
				_anim.speed_scale = clampf(left_anim / maxf(0.05, _action_end - _t), 0.5, 4.0)
	else:
		_update_base()
	_animate_parts()
	# Reading the tether narrows the viewmodel's field of view so the screen fills more of it.
	var tc: Dictionary = cfg.get("tether", {})
	var fov: float = lerpf(float(cfg.get("fov", 58.0)), float(tc.get("fov", 42.0)), tether.progress())
	if absf(fov - FpMaterials.fov) > 0.01:
		FpMaterials.set_fov(fov)
	if _screen_mat != null:
		_screen_mat.emission_energy_multiplier = _screen_energy(tether.progress())
	if not has_arms():
		_fallback_motion(delta, speed)


## Moving parts of the held item, keyed by the playing use (viewmodel.json `uses.<use>.parts`:
## {node name: [[frame, [x, y, z] degrees], ...]} at the arms' 30 fps, smoothstepped between keys):
## the revolver's cylinder swings out on its crane to reload. Back to rest when no such use plays.
func _animate_parts() -> void:
	var keys_by_part: Dictionary = {}
	if _held != null and _anim != null and _action != &"" and String(_action).begins_with("fp_"):
		var use: Dictionary = (cfg.get("uses", {}) as Dictionary).get(String(_action).substr(3), {})
		keys_by_part = use.get("parts", {})
	if keys_by_part.is_empty():
		for n: Node3D in _posed_parts:
			if is_instance_valid(n):
				n.rotation = Vector3.ZERO
		_posed_parts.clear()
		return
	var f: float = _anim.current_animation_position * 30.0
	for part: String in keys_by_part:
		var n: Node3D = _held.find_child(part, true, false) as Node3D
		if n == null:
			continue
		n.rotation_degrees = part_rotation(keys_by_part[part], f)
		if not _posed_parts.has(n):
			_posed_parts.append(n)


## A part's rotation (degrees) at frame `f` of its [[frame, [x, y, z]], ...] keys.
static func part_rotation(keys: Array, f: float) -> Vector3:
	if keys.is_empty():
		return Vector3.ZERO
	var prev: Array = keys[0]
	if f <= float(prev[0]):
		return _vec3(prev[1])
	for k: Array in keys:
		if f <= float(k[0]):
			var t: float = smoothstep(float(prev[0]), float(k[0]), f)
			return _vec3(prev[1]).lerp(_vec3(k[1]), t)
		prev = k
	return _vec3(prev[1])


static func _vec3(a: Array) -> Vector3:
	return Vector3(float(a[0]), float(a[1]), float(a[2]))


## Indoors or under a roof every so often (the same tests the ambience and the survival climate
## use: a POI room, or a built roof overhead): the arms and the held item lose the weather.
func _update_exposure(delta: float) -> void:
	_shelter_t -= delta
	if _shelter_t > 0.0:
		return
	_shelter_t = SHELTER_CHECK
	var at: Vector3 = _player.global_position if _player != null else global_position
	set_exposure(0.0 if sheltered_at(Game.world, at) else 1.0)


## A POI's indoors (PoiManager.is_indoors) or under a built roof (BuildingManager.is_sheltered).
static func sheltered_at(world: Node, pos: Vector3) -> bool:
	if world == null:
		return false
	var pois: Node = world.get(&"pois") as Node
	if pois != null and pois.has_method(&"is_indoors") and bool(pois.call(&"is_indoors", pos)):
		return true
	var building: Node = world.get(&"building") as Node
	return building != null and building.has_method(&"is_sheltered") and bool(building.call(&"is_sheltered", pos))


func set_exposure(value: float) -> void:
	if is_equal_approx(value, exposure):
		return
	exposure = value
	_apply_exposure(self)


func _apply_exposure(n: Node) -> void:
	if n is GeometryInstance3D and not n is GPUParticles3D:
		(n as GeometryInstance3D).set_instance_shader_parameter(&"weather_exposure", exposure)
	for c: Node in n.get_children():
		_apply_exposure(c)


## No arms model: the item floats at its rest pose and swings procedurally.
func _fallback_motion(delta: float, speed: float) -> void:
	var tr: Transform3D = _rest
	tr.origin += Vector3(sin(_t * 6.0) * 0.006, absf(cos(_t * 6.0)) * 0.008, 0.0) * clampf(speed / 3.0, 0.0, 1.5)
	if _swing_t >= 0.0:
		_swing_t += delta
		var k: float = clampf(_swing_t / _swing_len, 0.0, 1.0)
		var a: float
		if k < 0.35:
			a = -ease(k / 0.35, 0.5) * 0.9
		elif k < 0.5:
			a = lerpf(-0.9, 0.8, (k - 0.35) / 0.15)
		else:
			a = lerpf(0.8, 0.0, ease((k - 0.5) / 0.5, 0.4))
		tr.basis = tr.basis * Basis(Vector3.RIGHT, a) * Basis(Vector3.FORWARD, -a * 0.35)
		tr.origin += Vector3(-a * 0.08, a * 0.05, -absf(a) * 0.06)
		if k >= 1.0:
			_swing_t = -1.0
	if _recoil > 0.0:
		_recoil = maxf(0.0, _recoil - delta * 6.0)
		tr.basis = tr.basis * Basis(Vector3.RIGHT, _recoil * 0.35)
		tr.origin += Vector3(0.0, 0.0, _recoil * 0.06)
	_item_root.transform = _item_root.transform.interpolate_with(tr, minf(1.0, 20.0 * delta))
