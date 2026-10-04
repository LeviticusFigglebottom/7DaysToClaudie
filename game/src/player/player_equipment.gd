class_name PlayerEquipment
extends Node
## Toolbelt, held item presentation, attacks and tool use.
## Hits are resolved with a short shape cast along the view; receivers implement take_damage().
## Trees (group "tree_body"), terrain (meta "terrain"), structures and enemies all receive
## DamageInfo with the item's tool_power so each decides what the hit does (chop, dig, break).

signal equipped_changed(item_id: StringName)
signal swung()

const HIT_MASK: int = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 4) | (1 << 9) | (1 << 12)

var player: Player
var current: StringName = &""
var _cooldown: float = 0.0
var _swing_t: float = -1.0
var _light: Light3D = null
var _light_on: bool = false
var viewmodel: ViewModel


func _ready() -> void:
	player = get_parent() as Player
	viewmodel = player.get_node_or_null("Head/Camera3D/ViewModel") as ViewModel


func carried_logs() -> int:
	return player.state.inventory.count_of(&"log") if player != null and player.state != null else 0


func _physics_process(delta: float) -> void:
	if player == null or player.state == null:
		return
	_cooldown = maxf(0.0, _cooldown - delta)
	_sync_equipped()
	if not player.input_enabled:
		return
	for i: int in player.state.toolbelt.size():
		if Input.is_action_just_pressed(StringName("toolbelt_%d" % (i + 1))):
			select_slot(i if player.state.equipped_slot != i else -1)
	if Input.is_action_just_pressed(&"toolbelt_next"):
		_cycle(1)
	elif Input.is_action_just_pressed(&"toolbelt_prev"):
		_cycle(-1)
	if Input.is_action_just_pressed(&"light"):
		toggle_light()
	if Input.is_action_pressed(&"attack") and _cooldown <= 0.0 and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		primary()
	if Input.is_action_just_pressed(&"block") and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED and not _building_busy():
		secondary()
	if _swing_t >= 0.0:
		_swing_t += delta
		var def: ItemDef = Content.item(current)
		var t_hit: float = (def.equip_num("attack_time", 0.8) if def != null else 0.6) * 0.45
		if _swing_t >= t_hit:
			_swing_t = -1.0
			_resolve_hit()


func _building_busy() -> bool:
	var building: Node = Game.world.get(&"building") if Game.world != null else null
	return building != null and (building.call(&"is_placing") or carried_logs() > 0)


func select_slot(i: int) -> void:
	player.state.equipped_slot = i
	_sync_equipped()


func _cycle(d: int) -> void:
	var n: int = player.state.toolbelt.size()
	var i: int = player.state.equipped_slot
	for k: int in n:
		i = posmod(i + d, n)
		if player.state.toolbelt[i] != &"" and player.state.inventory.has(player.state.toolbelt[i]):
			select_slot(i)
			return


func _sync_equipped() -> void:
	var item_id: StringName = player.state.equipped_item()
	if item_id == current:
		return
	current = item_id
	_set_light(false)
	if viewmodel != null:
		viewmodel.show_item(item_id)
	equipped_changed.emit(item_id)


# --- Actions ------------------------------------------------------------------------------

func primary() -> void:
	var def: ItemDef = Content.item(current)
	var building: Node = Game.world.get(&"building") if Game.world != null else null
	if building != null and building.call(&"handle_primary", player):
		_cooldown = 0.35
		if viewmodel != null:
			viewmodel.play_action(&"fp_place", 0.35)
		return
	if def == null:
		_punch()
		return
	var kind: String = str(def.equip.get("kind", ""))
	match kind:
		"melee", "light":
			if def.equip.has("damage"):
				_start_swing(def)
		"ranged":
			_fire(def)
		"throwable":
			_throw(def)
		"placeable":
			if Game.world != null and Game.world.get("building") != null:
				Game.world.building.place_item_structure(player, current)
				_cooldown = 0.5


func secondary() -> void:
	var def: ItemDef = Content.item(current)
	if def != null and def.is_consumable():
		var res: Dictionary = Game.execute(&"inventory.consume", {"player": player.state.id, "item": current})
		if bool(res.get("ok", false)) and viewmodel != null:
			viewmodel.play_action(&"fp_use")
	elif def != null and str(def.equip.get("kind", "")) == "ranged":
		_reload(def)


func _punch() -> void:
	if not player.state.stats.spend_stamina(5.0):
		return
	_cooldown = 0.6
	_swing_t = 0.0
	if viewmodel != null:
		viewmodel.play_swing(0.6)
	swung.emit()


func _start_swing(def: ItemDef) -> void:
	var cost: float = def.equip_num("stamina", 10.0)
	if not player.state.stats.spend_stamina(cost):
		return
	_cooldown = def.equip_num("attack_time", 0.8)
	_swing_t = 0.0
	if viewmodel != null:
		viewmodel.play_swing(_cooldown)
	Audio.play_3d(&"sfx/swing_whoosh", player.global_position + Vector3.UP * 1.4, {"volume_db": -8.0, "occlusion": false})
	swung.emit()


func _resolve_hit() -> void:
	var def: ItemDef = Content.item(current)
	var reach: float = def.equip_num("reach", 2.0) if def != null else 1.6
	var cam: Camera3D = player.camera
	var from: Vector3 = cam.global_position
	var dir: Vector3 = -cam.global_transform.basis.z
	var q := PhysicsShapeQueryParameters3D.new()
	var sphere := SphereShape3D.new()
	sphere.radius = 0.22
	q.shape = sphere
	q.transform = Transform3D(Basis(), from)
	q.motion = dir * reach
	q.collision_mask = HIT_MASK
	q.collide_with_areas = true
	q.exclude = [player.get_rid()]
	var space: PhysicsDirectSpaceState3D = player.get_world_3d().direct_space_state
	var frac: PackedFloat32Array = space.cast_motion(q)
	if frac.size() < 2 or frac[1] >= 1.0:
		return
	q.transform = Transform3D(Basis(), from + dir * reach * frac[1])
	var info_hit: Dictionary = space.get_rest_info(q)
	if info_hit.is_empty():
		return
	var collider: Object = instance_from_id(int(info_hit["collider_id"]))
	var pos: Vector3 = info_hit["point"]
	var dmg := _damage_for(def, pos, dir)
	dmg.collider = collider
	var receiver: Object = _damage_receiver(collider)
	if receiver != null:
		receiver.call(&"take_damage", dmg)
	_wear(def)
	var loud: float = def.equip_num("noise", 8.0) if def != null else 5.0
	if Stimuli.current != null:
		Stimuli.current.emit_sound(pos, loud, &"impact", player.state.id)


func _damage_for(def: ItemDef, pos: Vector3, dir: Vector3) -> DamageInfo:
	var p: Progression = player.state.progression
	var base: float = def.equip_num("damage", 6.0) if def != null else 6.0
	var dtype: StringName = StringName(str(def.equip.get("damage_type", "blunt"))) if def != null else &"blunt"
	var mult: float = 1.0 + p.modifier("melee_damage_mult")
	if dtype == &"blunt":
		mult += p.modifier("blunt_damage_mult")
	var stack: ItemStack = player.state.inventory.first(current) if def != null else null
	if stack != null and stack.quality > 0:
		mult *= 0.85 + 0.1 * stack.quality
	var info := DamageInfo.make(base * mult, dtype, &"melee", player.state.id)
	info.source_pos = player.global_position
	info.hit_pos = pos
	info.direction = dir
	info.dismember = float(def.equip.get("dismember", 0.0)) if def != null else 0.0
	info.stagger = float(def.equip.get("stagger", 0.3)) if def != null else 0.2
	info.tool_power = (def.equip.get("tool_power", {}) as Dictionary).duplicate() if def != null else {}
	# tool_power.wood = chopping strength (axes, machetes); tool_power.earth = digging (shovels).
	if info.tool_power.has("wood"):
		info.tool_power["chop"] = float(info.tool_power["wood"]) * (1.0 + p.modifier("chop_damage_mult"))
	if info.tool_power.has("earth") or (def != null and def.provides_tool("shovel")):
		info.tool_power["dig"] = float(info.tool_power.get("earth", 1.0))
	return info


static func _damage_receiver(o: Object) -> Object:
	var n: Node = o as Node
	var depth: int = 0
	while n != null and depth < 6:
		if n.has_method(&"take_damage"):
			return n
		if n.has_meta(&"damage_receiver"):
			var r: Variant = n.get_meta(&"damage_receiver")
			if r is Object and is_instance_valid(r):
				return r
		n = n.get_parent()
		depth += 1
	return null


func _wear(def: ItemDef) -> void:
	if def == null or def.durability <= 0.0:
		return
	var stack: ItemStack = player.state.inventory.first(current)
	if stack == null:
		return
	stack.durability -= 1.0
	if stack.durability <= 0.0:
		player.state.inventory.take_from(stack, 1)
		Audio.play_2d(&"sfx/structure_break_wood", -6.0, &"SFX")
		Events.player_status_message.emit("%s broke." % def.display_name, &"warning")
		Events.inventory_changed.emit(player.state.id)


func _fire(def: ItemDef) -> void:
	var stack: ItemStack = player.state.inventory.first(current)
	if stack == null:
		return
	var loaded: int = int(stack.data.get("loaded", 0))
	if loaded <= 0:
		Audio.play_3d(&"sfx/gun_click_empty", player.global_position, {"volume_db": -6.0, "occlusion": false})
		_cooldown = 0.4
		return
	stack.data["loaded"] = loaded - 1
	_cooldown = def.equip_num("attack_time", 0.45)
	var cam: Camera3D = player.camera
	var spread: float = deg_to_rad(def.equip_num("spread_deg", 1.5)) * (0.5 if player.crouching else 1.0)
	var dir: Vector3 = (-cam.global_transform.basis.z).rotated(cam.global_transform.basis.x, randf_range(-spread, spread)).rotated(Vector3.UP, randf_range(-spread, spread))
	var q := PhysicsRayQueryParameters3D.create(cam.global_position, cam.global_position + dir * def.equip_num("range", 60.0), HIT_MASK)
	q.collide_with_areas = true
	q.exclude = [player.get_rid()]
	var hit: Dictionary = player.get_world_3d().direct_space_state.intersect_ray(q)
	Audio.play_3d(&"sfx/gun_revolver_shot", player.global_position + Vector3.UP * 1.4, {"volume_db": 2.0, "max_distance": 400.0, "occlusion": false})
	if Stimuli.current != null:
		Stimuli.current.emit_sound(player.global_position, def.equip_num("noise", 120.0), &"gunshot", player.state.id)
	if viewmodel != null:
		viewmodel.play_recoil()
	if not hit.is_empty():
		var info := DamageInfo.make(def.equip_num("damage", 50.0) * (1.0 + player.state.progression.modifier("ranged_damage_mult")), &"ballistic", &"firearm", player.state.id)
		info.hit_pos = hit["position"]
		info.direction = dir
		info.source_pos = cam.global_position
		info.dismember = float(def.equip.get("dismember", 0.3))
		info.stagger = 0.6
		info.collider = hit["collider"]
		var r: Object = _damage_receiver(hit["collider"])
		if r != null:
			r.call(&"take_damage", info)
	_wear(def)


func _reload(def: ItemDef) -> void:
	var stack: ItemStack = player.state.inventory.first(current)
	var ammo: StringName = StringName(str(def.equip.get("ammo", "")))
	if stack == null or ammo == &"":
		return
	var cap: int = int(def.equip.get("mag_size", 6))
	var need: int = cap - int(stack.data.get("loaded", 0))
	var have: int = player.state.inventory.count_of(ammo)
	var n: int = mini(need, have)
	if n <= 0:
		return
	player.state.inventory.remove(ammo, n)
	stack.data["loaded"] = int(stack.data.get("loaded", 0)) + n
	_cooldown = def.equip_num("reload_time", 2.5)
	Audio.play_3d(&"sfx/gun_reload", player.global_position, {"volume_db": -6.0, "occlusion": false})
	Events.inventory_changed.emit(player.state.id)


func _throw(def: ItemDef) -> void:
	if not player.state.stats.spend_stamina(def.equip_num("stamina", 6.0)):
		return
	if not player.state.inventory.remove(current, 1):
		return
	if viewmodel != null:
		viewmodel.play_action(&"fp_throw", 0.5)
	_cooldown = 0.7
	var proj: Node3D = load("res://src/combat/thrown_item.gd").new()
	proj.set(&"item_id", current)
	proj.set(&"thrower", player.state.id)
	proj.set(&"damage", def.equip_num("damage", 10.0))
	player.get_tree().current_scene.add_child(proj)
	var cam: Camera3D = player.camera
	proj.global_position = cam.global_position - cam.global_transform.basis.z * 0.6
	(proj as RigidBody3D).linear_velocity = -cam.global_transform.basis.z * 17.0 + Vector3.UP * 1.5 + player.velocity * 0.5
	Events.inventory_changed.emit(player.state.id)


# --- Lights ---------------------------------------------------------------------------------

func toggle_light() -> void:
	var def: ItemDef = Content.item(current)
	if def == null or not def.equip.has("light"):
		return
	_set_light(not _light_on)
	if _light_on and viewmodel != null and "lighter" in (def.equip.get("tools", []) as Array):
		viewmodel.play_action(&"fp_light")


func _set_light(on: bool) -> void:
	if _light != null:
		if Stimuli.current != null:
			Stimuli.current.unregister_light(_light)
		_light.queue_free()
		_light = null
	_light_on = false
	if not on:
		if viewmodel != null:
			viewmodel.set_lit(false)
		return
	var def: ItemDef = Content.item(current)
	if def == null:
		return
	var l: Dictionary = def.equip["light"]
	var color := Color.html(str(l.get("color", "#ffb46b")))
	if l.has("spot_angle"):
		var spot := SpotLight3D.new()
		spot.spot_angle = float(l["spot_angle"])
		spot.spot_range = float(l.get("range", 25.0))
		spot.shadow_enabled = true
		_light = spot
		player.camera.add_child(spot)
	else:
		var omni := FlickerLight.new()
		omni.omni_range = float(l.get("range", 8.0))
		omni.shadow_enabled = true
		omni.flicker = float(l.get("flicker", 0.2))
		_light = omni
		player.camera.add_child(omni)
		omni.position = Vector3(0.25, -0.25, -0.45)
	_light.light_color = color
	_light.light_energy = float(l.get("energy", 1.0))
	_light_on = true
	if Stimuli.current != null:
		Stimuli.current.register_light(_light, float(l.get("range", 8.0)) * 1.5, float(l.get("energy", 1.0)))
	if viewmodel != null:
		viewmodel.set_lit(true)
	if current == &"lighter":
		Audio.play_3d(&"sfx/lighter_flick", player.global_position, {"volume_db": -8.0, "occlusion": false})
	elif current == &"torch":
		Audio.play_3d(&"sfx/torch_ignite", player.global_position, {"volume_db": -6.0, "occlusion": false})


func has_light_on() -> bool:
	return _light_on
