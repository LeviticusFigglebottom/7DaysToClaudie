class_name StructurePiece
extends StaticBody3D
## A placed building piece (log, station, shelter, storage, trap). Collision + presentation +
## the behaviour its StructureDef `provides` (station, light/warmth, storage, sleep, noise trap,
## contact damage). Hit points, support and collapse are BuildingManager's business.

const LAYER: int = 1 << 1

var piece_id: StringName = &""
var def: StructureDef
var hp: float = 0.0
var manager: Node
var inventory: Inventory = null
var lit: bool = false

var _mesh: MeshInstance3D
var _light: FlickerLight = null
var _fire: GPUParticles3D = null
var _loop: AudioStreamPlayer3D = null
var _trap_area: Area3D = null
var _trap_cooldown: float = 0.0


func setup(p_id: StringName, p_def: StructureDef, p_manager: Node, p_hp: float = -1.0) -> void:
	piece_id = p_id
	def = p_def
	manager = p_manager
	hp = p_def.hp if p_hp < 0.0 else p_hp


func _ready() -> void:
	collision_layer = LAYER
	collision_mask = 0
	add_to_group(&"structures")
	set_meta(&"surface", "wood_floor" if def.material in ["log", "wood", "stick", "reinforced"] else "stone")
	_build_visual()
	_build_collision()
	_apply_provides()


func is_log() -> bool:
	return def.piece_kind == "log"


func max_hp() -> float:
	return def.hp


func _build_visual() -> void:
	_mesh = MeshInstance3D.new()
	if ModelLibrary.has_model(def.model):
		_mesh.mesh = ModelLibrary.mesh(def.model)
	elif is_log():
		_mesh.mesh = ModelLibrary.make_placeholder("log")
	else:
		var b := BoxMesh.new()
		b.size = def.size
		var m := StandardMaterial3D.new()
		m.albedo_color = Color(0.45, 0.35, 0.25) if def.material != "stone" else Color(0.45, 0.45, 0.43)
		b.material = m
		_mesh.mesh = b
		_mesh.position = Vector3(0, def.size.y * 0.5, 0)
	add_child(_mesh)


func _build_collision() -> void:
	if is_log():
		var cs := CollisionShape3D.new()
		var cyl := CylinderShape3D.new()
		cyl.radius = LogSnapper.RADIUS
		cyl.height = LogSnapper.LENGTH
		cs.shape = cyl
		cs.rotation = Vector3(0, 0, -PI * 0.5)
		add_child(cs)
		return
	var shapes: Array = ModelLibrary.shapes(def.model) if ModelLibrary.has_model(def.model) else []
	if not shapes.is_empty():
		for s: Dictionary in shapes:
			var c := CollisionShape3D.new()
			c.shape = s["shape"]
			c.transform = s["transform"]
			add_child(c)
		return
	var cs2 := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = def.size
	if def.piece_kind == "shelter":
		# Lean-to placeholder: only the sloped roof blocks, so you can crawl under it.
		box.size = Vector3(def.size.x, 0.12, def.size.z)
		cs2.transform = Transform3D(Basis(Vector3.RIGHT, deg_to_rad(-38.0)), Vector3(0, def.size.y * 0.55, 0))
	else:
		cs2.position = Vector3(0, def.size.y * 0.5, 0)
	cs2.shape = box
	add_child(cs2)


# --- Behaviour from `provides` --------------------------------------------------------------

func provides(tag: String) -> bool:
	return def.provides.has(tag)


func station_id() -> StringName:
	for p: String in def.provides:
		if p.begins_with("station:"):
			return StringName(p.substr(8))
	return &""


func storage_slots() -> int:
	for p: String in def.provides:
		if p.begins_with("storage:"):
			return int(p.substr(8))
	return 0


func _apply_provides() -> void:
	if storage_slots() > 0:
		inventory = Inventory.new()
		inventory.owner_id = piece_id
		inventory.max_slots = storage_slots()
		var st: Dictionary = Game.session.world.container_state(piece_id) if Game.session != null else {}
		for d: Variant in st.get("items", []):
			var s: ItemStack = ItemStack.from_dict(d)
			if s != null:
				inventory.add(s)
	if provides("noise_trap"):
		_trap_area = _make_trigger(Vector3(def.size.x, 1.2, 1.0))
		_trap_area.body_entered.connect(_on_trap_body)
	if def.contact_damage > 0.0:
		var a: Area3D = _make_trigger(def.size + Vector3(0.6, 0.0, 0.6))
		a.body_entered.connect(_on_spike_body)
	if provides("light"):
		var lit_state: bool = bool(Game.session.world.flags.get("lit:%s" % piece_id, false)) if Game.session != null else false
		set_lit(lit_state)


func _make_trigger(size: Vector3) -> Area3D:
	var a := Area3D.new()
	a.collision_layer = 1 << 10
	a.collision_mask = (1 << 3) | (1 << 4)
	var cs := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = size
	cs.shape = box
	cs.position = Vector3(0, size.y * 0.5, 0)
	a.add_child(cs)
	add_child(a)
	return a


func _process(delta: float) -> void:
	_trap_cooldown = maxf(0.0, _trap_cooldown - delta)


func _on_trap_body(body: Node) -> void:
	if _trap_cooldown > 0.0:
		return
	_trap_cooldown = 2.0
	Audio.play_3d(&"sfx/can_chime", global_position + Vector3.UP * 0.4, {"volume_db": 0.0, "max_distance": 60.0})
	if Stimuli.current != null:
		Stimuli.current.emit_sound(global_position, 30.0, &"trap", piece_id)
	if body.is_in_group(&"enemies") and manager != null:
		Events.player_status_message.emit("Something rattled the can chime.", &"warning")


func _on_spike_body(body: Node) -> void:
	if not body.is_in_group(&"enemies") or not body.has_method(&"take_damage"):
		return
	var info := DamageInfo.make(def.contact_damage, &"pierce", &"trap", piece_id)
	info.hit_pos = (body as Node3D).global_position + Vector3.UP
	info.source_pos = global_position
	info.direction = ((body as Node3D).global_position - global_position).normalized()
	body.call(&"take_damage", info)
	# Spikes wear as they work.
	var wear := DamageInfo.make(def.contact_damage * 0.25, &"blunt", &"wear", &"")
	wear.hit_pos = global_position
	take_damage(wear)


## Campfire / light sources.
func set_lit(on: bool) -> void:
	lit = on
	if Game.session != null:
		if on:
			Game.session.world.flags["lit:%s" % piece_id] = true
		else:
			Game.session.world.flags.erase("lit:%s" % piece_id)
	if on and _light == null:
		_light = FlickerLight.new()
		_light.light_color = Color(1.0, 0.62, 0.32)
		_light.light_energy = 2.2
		_light.omni_range = 11.0
		_light.shadow_enabled = true
		_light.flicker = 0.35
		_light.position = Vector3(0, 0.7, 0)
		add_child(_light)
		_fire = _make_flames()
		_loop = AudioStreamPlayer3D.new()
		_loop.stream = Audio.stream(&"sfx/campfire_loop")
		_loop.bus = &"SFX"
		_loop.unit_size = 4.0
		_loop.max_distance = 30.0
		_loop.volume_db = -4.0
		add_child(_loop)
		if _loop.stream != null:
			_loop.play()
		if Stimuli.current != null:
			Stimuli.current.register_light(_light, 22.0, 1.4)
	elif not on and _light != null:
		if Stimuli.current != null:
			Stimuli.current.unregister_light(_light)
		_light.queue_free()
		_light = null
		if _fire != null:
			_fire.queue_free()
			_fire = null
		if _loop != null:
			_loop.queue_free()
			_loop = null


func _make_flames() -> GPUParticles3D:
	if DisplayServer.get_name() == "headless":
		return null
	var p := GPUParticles3D.new()
	p.amount = 24
	p.lifetime = 0.9
	p.position = Vector3(0, 0.15, 0)
	var m := ParticleProcessMaterial.new()
	m.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	m.emission_sphere_radius = 0.22
	m.direction = Vector3.UP
	m.spread = 12.0
	m.initial_velocity_min = 0.6
	m.initial_velocity_max = 1.3
	m.gravity = Vector3(0, 0.6, 0)
	m.scale_min = 0.6
	m.scale_max = 1.2
	var g := Gradient.new()
	g.set_color(0, Color(1.0, 0.85, 0.45, 1.0))
	g.set_color(1, Color(0.6, 0.15, 0.05, 0.0))
	var gt := GradientTexture1D.new()
	gt.gradient = g
	m.color_ramp = gt
	p.process_material = m
	var q := QuadMesh.new()
	q.size = Vector2(0.35, 0.5)
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	mat.vertex_color_use_as_albedo = true
	var flame: String = "res://assets/generated/textures/fx/flame.png"
	if ResourceLoader.exists(flame):
		mat.albedo_texture = load(flame)
	q.material = mat
	p.draw_pass_1 = q
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(p)
	return p


## Warmth in °C this piece adds at a position (lit fires only).
func warmth_at(pos: Vector3) -> float:
	if not lit or not provides("warmth"):
		return 0.0
	var d: float = global_position.distance_to(pos)
	return 0.0 if d > 5.0 else 14.0 * (1.0 - d / 5.0)


# --- Damage & interaction -------------------------------------------------------------------

func take_damage(info: DamageInfo) -> void:
	if manager != null:
		manager.call(&"damage_piece", self, info)


func interact_text(player: Player) -> String:
	if def.piece_kind == "log":
		return ""
	var parts: PackedStringArray = []
	if station_id() != &"":
		parts.append("Use %s" % def.display_name)
	if inventory != null:
		parts.append("Open %s" % def.display_name)
	if provides("sleep"):
		parts.append("Sleep")
	if parts.is_empty():
		return ""
	if provides("light") and not lit:
		return "Light fire" if _has_igniter(player) else "Light fire (needs a lighter)"
	return parts[0]


func interact_hold_time(_player: Player) -> float:
	return 0.0


func _has_igniter(player: Player) -> bool:
	return player.state.inventory.find_tool("lighter") != null or player.state.inventory.has(&"torch")


func interact(player: Player) -> void:
	if provides("light") and not lit:
		if _has_igniter(player):
			set_lit(true)
			Audio.play_3d(&"sfx/fire_ignite", global_position, {"volume_db": -2.0})
		else:
			Events.player_status_message.emit("You need something to light it with.", &"warning")
		return
	if station_id() != &"":
		var ui: Node = Game.world.get(&"ui") if Game.world != null else null
		if ui != null and ui.has_method(&"open_crafting"):
			ui.call(&"open_crafting", station_id(), self)
		return
	if inventory != null:
		var ui2: Node = Game.world.get(&"ui") if Game.world != null else null
		if ui2 != null and ui2.has_method(&"open_container"):
			ui2.call(&"open_container", self)
		return
	if provides("sleep") and Game.world != null and Game.world.has_method(&"try_sleep"):
		Game.world.call(&"try_sleep", player, self)


## Containers: persist contents whenever they change.
func on_contents_changed() -> void:
	if inventory != null and Game.session != null:
		Game.session.world.set_container_items(piece_id, inventory)


var container_id: StringName:
	get:
		return piece_id
