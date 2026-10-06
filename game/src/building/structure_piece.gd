class_name StructurePiece
extends StaticBody3D
## A placed building piece (log, station, shelter, storage, trap). Collision + presentation +
## the behaviour its StructureDef `provides` (station, light/warmth, storage, sleep, noise trap,
## contact damage). Hit points, support and collapse are BuildingManager's business.
## ADR-0035: a resource rack (`rack:<item>:<capacity>`) holds one kind of thing and shows how full
## it is (its model's fill_NN parts); a door (kind `door`) swings its `leaf` open and shut; stairs
## (kind `stairs`) are a ramp to walk up.

const LAYER: int = 1 << 1

var piece_id: StringName = &""
var def: StructureDef
var hp: float = 0.0
## The builder's toughness bonus when it was placed (Wits, Builder perk): max hp = def.hp x this.
## Saved per piece, so it survives respec-free progression changes and loads unchanged.
var hp_mult: float = 1.0
var manager: Node
var inventory: Inventory = null
var lit: bool = false
## Game minutes of burn left (fuel-burning stations: the campfire). BuildingManager burns it down
## while lit and the fire goes out at zero.
var fuel: float = 0.0

var _mesh: MeshInstance3D
var _light: FlickerLight = null
var _fire: GPUParticles3D = null
var _loop: AudioStreamPlayer3D = null
var _trap_area: Area3D = null
var _trap_cooldown: float = 0.0
var _spike_area: Area3D = null
var _spike_t: float = 0.0
## Seconds between spike hits on a Hollow that stays on (or keeps pushing into) the spikes.
const SPIKE_INTERVAL: float = 1.2
## A rack's fill parts in order (the first N shown), a door's leaf (pivoting on its hinge) and the
## leaf's collision, and whether the door stands open (ADR-0035).
var _fills: Array[Node3D] = []
var _leaf: Node3D = null
var _leaf_shape: CollisionShape3D = null
var door_open: bool = false
## Stairs: rise and run of the flight (8 courses of logs over 3.6 m).
const STAIR_RISE: float = 2.32
const STAIR_RUN: float = 3.6


func setup(p_id: StringName, p_def: StructureDef, p_manager: Node, p_hp: float = -1.0, p_hp_mult: float = 1.0) -> void:
	piece_id = p_id
	def = p_def
	manager = p_manager
	hp_mult = maxf(0.1, p_hp_mult)
	hp = max_hp() if p_hp < 0.0 else p_hp


func _ready() -> void:
	collision_layer = LAYER
	collision_mask = 0
	add_to_group(&"structures")
	set_meta(&"surface", "wood_floor" if def.material in ["log", "wood", "stick", "reinforced"] else "stone")
	_build_visual()
	_build_collision()
	_apply_provides()
	# Only traps tick; a wall of logs has nothing to do per frame.
	set_process(_trap_area != null or _spike_area != null)


func is_log() -> bool:
	return def.piece_kind == "log"


func max_hp() -> float:
	return def.hp * hp_mult


func _build_visual() -> void:
	_mesh = MeshInstance3D.new()
	if rack_capacity() > 0 or def.piece_kind == "door":
		_build_parted_visual()
		return
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


## A rack or a door: the model's still part merged, its moving or showing parts as their own
## nodes; stand-ins when the model is not generated.
func _build_parted_visual() -> void:
	var door: bool = def.piece_kind == "door"
	var split: Dictionary = ModelLibrary.parts(def.model, PackedStringArray(["leaf"] if door else ["fill_"]))
	if not split.is_empty() and split.get("base") != null:
		_mesh.mesh = split["base"]
		add_child(_mesh)
		var names: Array = (split["parts"] as Dictionary).keys()
		names.sort()
		for nm: String in names:
			var part: Dictionary = split["parts"][nm]
			var mi := MeshInstance3D.new()
			mi.name = nm
			mi.mesh = part["mesh"]
			if door:
				# The leaf turns about its own origin, the hinge.
				_leaf = Node3D.new()
				_leaf.name = "Leaf"
				_leaf.transform = part["xf"]
				_leaf.add_child(mi)
				add_child(_leaf)
			else:
				mi.transform = part["xf"]
				add_child(mi)
				_fills.append(mi)
		return
	# Stand-ins: a frame of posts and a slab leaf, or a cradle with stacked fill blocks.
	var m := StandardMaterial3D.new()
	m.albedo_color = Color(0.42, 0.33, 0.24)
	var box := func(size: Vector3, at: Vector3, parent: Node3D) -> MeshInstance3D:
		var mi := MeshInstance3D.new()
		var b := BoxMesh.new()
		b.size = size
		b.material = m
		mi.mesh = b
		mi.position = at
		parent.add_child(mi)
		return mi
	add_child(_mesh)
	if door:
		box.call(Vector3(0.12, 2.2, 0.12), Vector3(-0.55, 1.1, 0), self)
		box.call(Vector3(0.12, 2.2, 0.12), Vector3(0.55, 1.1, 0), self)
		box.call(Vector3(1.22, 0.12, 0.12), Vector3(0, 2.16, 0), self)
		_leaf = Node3D.new()
		_leaf.name = "Leaf"
		_leaf.position = Vector3(-0.5, 0, 0)
		add_child(_leaf)
		box.call(Vector3(1.0, 2.0, 0.07), Vector3(0.5, 1.0, 0), _leaf)
		return
	box.call(Vector3(def.size.x, 0.08, def.size.z), Vector3(0, 0.04, 0), self)
	var cap: int = rack_capacity()
	var slots: int = mini(cap, 12)
	for i: int in slots:
		var row: int = i % 4
		var tier: int = i / 4
		var f: MeshInstance3D = box.call(Vector3(def.size.x * 0.9, 0.12, def.size.z * 0.2),
			Vector3(0, 0.14 + tier * 0.13, (float(row) - 1.5) * def.size.z * 0.22), self)
		_fills.append(f)


func _build_collision() -> void:
	if def.piece_kind == "stairs":
		# One ramp along the flight (walkable at 33 degrees), lying under the treads' noses.
		var ramp := CollisionShape3D.new()
		var rb := BoxShape3D.new()
		var length: float = Vector2(STAIR_RUN, STAIR_RISE).length()
		rb.size = Vector3(maxf(def.size.x, 1.0), 0.1, length)
		ramp.shape = rb
		ramp.transform = Transform3D(Basis(Vector3.RIGHT, -atan2(STAIR_RISE, STAIR_RUN)), Vector3(0, STAIR_RISE * 0.5, STAIR_RUN * 0.5))
		add_child(ramp)
		return
	if def.piece_kind == "door":
		for x: float in [-0.55, 0.55]:
			var post := CollisionShape3D.new()
			var pb := BoxShape3D.new()
			pb.size = Vector3(0.14, 2.2, 0.14)
			post.shape = pb
			post.position = Vector3(x, 1.1, 0)
			add_child(post)
		_leaf_shape = CollisionShape3D.new()
		var lb := BoxShape3D.new()
		lb.size = Vector3(1.0, 2.0, 0.08)
		_leaf_shape.shape = lb
		add_child(_leaf_shape)
		_place_leaf(false)
		return
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


func station_def() -> StationDef:
	var sid: StringName = station_id()
	return Content.get_def(&"station", sid) as StationDef if sid != &"" else null


## A fire that needs feeding (campfire): fuel is tracked, it goes out when it runs dry.
func burns_fuel() -> bool:
	var sd: StationDef = station_def()
	return sd != null and sd.needs_fuel and provides("light")


func max_fuel() -> float:
	var sd: StationDef = station_def()
	return sd.max_fuel if sd != null else 0.0


static func fuel_text(minutes: float) -> String:
	if minutes >= 60.0:
		return "%dh %02dm" % [int(minutes / 60.0), int(fmod(minutes, 60.0))]
	return "%dm" % maxi(1, int(minutes))


func storage_slots() -> int:
	for p: String in def.provides:
		if p.begins_with("storage:"):
			return int(p.substr(8))
	return 0


## A resource rack's item and how many it holds (`rack:<item>:<capacity>`, ADR-0035).
func rack_item() -> StringName:
	for p: String in def.provides:
		if p.begins_with("rack:"):
			return StringName(p.get_slice(":", 1))
	return &""


func rack_capacity() -> int:
	for p: String in def.provides:
		if p.begins_with("rack:"):
			return int(p.get_slice(":", 2))
	return 0


func rack_count() -> int:
	return inventory.count_of(rack_item()) if inventory != null else 0


## Shows as many fill parts as the rack's share of its capacity.
func update_fill() -> void:
	if _fills.is_empty():
		return
	var cap: int = rack_capacity()
	var n: int = rack_count()
	var shown: int = 0 if n <= 0 else clampi(int(ceil(float(n) * float(_fills.size()) / float(maxi(cap, 1)))), 1, _fills.size())
	for i: int in _fills.size():
		_fills[i].visible = i < shown


## Swings the leaf open (90 degrees, away from the side it opens to) or shut; `animate` eases it.
func set_door_open(on: bool, animate: bool = true) -> void:
	door_open = on
	_place_leaf(animate)


func _place_leaf(animate: bool) -> void:
	var yaw: float = -PI * 0.5 if door_open else 0.0
	if _leaf != null:
		var base: Basis = _leaf.transform.basis.orthonormalized()
		var target := Basis(Vector3.UP, yaw)
		if animate and is_inside_tree():
			var tw := create_tween()
			tw.tween_method(func(t: float) -> void:
				if is_instance_valid(_leaf):
					_leaf.basis = base.slerp(target, t), 0.0, 1.0, 0.45)
		else:
			_leaf.basis = target
	if _leaf_shape != null:
		# The collider jumps to where the leaf ends up (open, it stands along the hinge post).
		var hinge := Vector3(-0.5, 0.0, 0.0)
		var leaf_xf := Transform3D(Basis(Vector3.UP, yaw), hinge)
		_leaf_shape.transform = leaf_xf * Transform3D(Basis(), Vector3(0.5, 1.0, 0.0))


func _apply_provides() -> void:
	if rack_capacity() > 0:
		inventory = Inventory.new()
		inventory.owner_id = piece_id
		inventory.max_slots = rack_capacity()
		var rst: Dictionary = Game.session.world.container_state(piece_id) if Game.session != null else {}
		for d: Variant in rst.get("items", []):
			var s2: ItemStack = ItemStack.from_dict(d)
			if s2 != null:
				inventory.add(s2)
		update_fill()
	if def.piece_kind == "door" and Game.session != null:
		set_door_open(bool(Game.session.world.flags.get("open:%s" % piece_id, false)), false)
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
		_spike_area = _make_trigger(def.size + Vector3(0.6, 0.0, 0.6))
		_spike_area.body_entered.connect(_on_spike_body)
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
	if _spike_area != null:
		_spike_t += delta
		if _spike_t >= SPIKE_INTERVAL:
			_spike_t = 0.0
			# Entering hits at once; staying on the spikes keeps hurting.
			for b: Node3D in _spike_area.get_overlapping_bodies():
				if is_instance_valid(self) and hp > 0.0:
					_on_spike_body(b)


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
	# The coals of a lit fire glow (ember_glow materials, ADR-0023).
	if _mesh != null:
		PropLights.set_lit(_mesh, on)
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
	var flame: String = "res://assets/generated/textures/fx_fire_flipbook.png"
	if ResourceLoader.exists(flame):
		mat.albedo_texture = load(flame)
		mat.particles_anim_h_frames = 8
		mat.particles_anim_v_frames = 8
		mat.particles_anim_loop = true
		m.anim_speed_min = 1.0
		m.anim_speed_max = 1.0
		m.anim_offset_max = 1.0
	q.material = mat
	p.draw_pass_1 = q
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(p)
	return p


## Warmth in °C this piece adds at a position (lit fires only), fading out to the station's
## warmth radius.
func warmth_at(pos: Vector3) -> float:
	if not lit or not provides("warmth"):
		return 0.0
	var sd: StationDef = station_def()
	var r: float = sd.warmth_radius if sd != null and sd.warmth_radius > 0.0 else 5.0
	var d: float = global_position.distance_to(pos)
	return 0.0 if d > r else 14.0 * (1.0 - d / r)


# --- Damage & interaction -------------------------------------------------------------------

func take_damage(info: DamageInfo) -> void:
	if manager != null:
		manager.call(&"damage_piece", self, info)


## Crouching with a hammer in hand turns every piece into "dismantle" (hold), so the normal
## prompt (use, open, sleep) stays what a plain press does.
static func _dismantling(player: Player) -> bool:
	if not player.crouching:
		return false
	var held: ItemDef = Content.item(player.state.equipped_item())
	return held != null and held.provides_tool("hammer")


func interact_text(player: Player) -> String:
	if _dismantling(player):
		return "Dismantle %s (hold)" % def.display_name.to_lower()
	if def.piece_kind == "log":
		return ""
	if def.piece_kind == "door":
		return "Close door" if door_open else "Open door"
	if rack_capacity() > 0:
		var item: ItemDef = Content.item(rack_item())
		var nm: String = item.display_name.to_lower() if item != null else String(rack_item())
		var carried: int = player.state.inventory.count_of(rack_item())
		var room: int = rack_capacity() - rack_count()
		if carried > 0 and room > 0:
			return "Store %s x%d (%d/%d)" % [nm, mini(carried, room), rack_count(), rack_capacity()]
		if rack_count() > 0:
			return "Take %s (%d/%d)" % [nm, rack_count(), rack_capacity()]
		return "%s (empty, holds %d %s)" % [def.display_name, rack_capacity(), nm]
	var parts: PackedStringArray = []
	if station_id() != &"":
		parts.append("Use %s" % def.display_name)
	if inventory != null:
		parts.append("Open %s" % def.display_name)
	if provides("sleep"):
		parts.append("Sleep")
	if parts.is_empty():
		return ""
	if burns_fuel():
		if not lit and fuel <= 0.0:
			var item: StringName = BuildingManager.fuel_choice(player.state, self)
			return "Add fuel (%s)" % Content.item(item).display_name if item != &"" else "Needs fuel: sticks, leaves or a log"
		if not lit:
			return ("Light fire" if _has_igniter(player) else "Light fire (needs a lighter)") + " · fuel %s" % fuel_text(fuel)
		return "%s · burns %s · [%s] add fuel" % [parts[0], fuel_text(fuel), PlayerInteraction.key_label(&"drop")]
	if provides("light") and not lit:
		return "Light fire" if _has_igniter(player) else "Light fire (needs a lighter)"
	return parts[0]


func interact_hold_time(player: Player) -> float:
	return 1.6 if _dismantling(player) else 0.0


func _has_igniter(player: Player) -> bool:
	return has_igniter(player.state)


static func has_igniter(p: PlayerState) -> bool:
	return p.inventory.find_tool("lighter") != null or p.inventory.has(&"torch")


func interact(player: Player) -> void:
	if _dismantling(player):
		Game.execute(&"build.dismantle", {"player": player.state.id, "piece": String(piece_id)})
		return
	if def.piece_kind == "door":
		Game.execute(&"build.toggle_door", {"player": player.state.id, "piece": String(piece_id)})
		return
	if rack_capacity() > 0:
		var store: bool = player.state.inventory.count_of(rack_item()) > 0 and rack_count() < rack_capacity()
		Game.execute(&"build.rack_store" if store else &"build.rack_take", {"player": player.state.id, "piece": String(piece_id)})
		return
	if burns_fuel() and not lit and fuel <= 0.0:
		Game.execute(&"build.add_fuel", {"player": player.state.id, "piece": String(piece_id)})
		return
	if provides("light") and not lit:
		Game.execute(&"build.light", {"player": player.state.id, "piece": String(piece_id)})
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
	update_fill()


var container_id: StringName:
	get:
		return piece_id
