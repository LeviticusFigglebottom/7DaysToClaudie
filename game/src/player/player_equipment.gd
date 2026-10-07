class_name PlayerEquipment
extends Node
## Toolbelt, held item presentation, attacks and tool use.
## Hits are resolved with a short shape cast along the view; receivers implement take_damage().
## Trees (group "tree_body"), terrain (meta "terrain"), structures and enemies all receive
## DamageInfo with the item's tool_power so each decides what the hit does (chop, dig, break).
## First person (ADR-0029): a swing connects at its style's keyed contact frame (attack_time x
## viewmodel.json attacks.<style>.impact) and the viewmodel answers with hit-stop, a camera kick
## and particles by what was struck; holding Block with a melee weapon raises its guard.

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
## A reload in progress: seconds left and the weapon it is for. The rounds go in when it
## finishes; putting the gun away first cancels it (it used to load instantly).
var _reload_left: float = -1.0
var _reload_item: StringName = &""
## The swing in progress: its length and the fraction of it at which it connects.
var _swing_len: float = 0.6
var _hit_frac: float = 0.45
## Block held with a weapon that has a guard (ViewModelHolds.block_share > 0).
var guarding: bool = false


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
	var captured: bool = Input.mouse_mode == Input.MOUSE_MODE_CAPTURED
	if Input.is_action_just_pressed(&"inspect") and captured and _cooldown <= 0.0 and not guarding and viewmodel != null:
		viewmodel.play_inspect()
	_update_guard(captured and Input.is_action_pressed(&"block") and not _building_busy())
	if Input.is_action_pressed(&"attack") and _cooldown <= 0.0 and captured and not guarding:
		# A raised wrist goes down first; the next press swings.
		if viewmodel != null and viewmodel.tether_raised():
			if Input.is_action_just_pressed(&"attack"):
				viewmodel.set_tether_raised(false)
				_cooldown = 0.2
		else:
			primary()
	if Input.is_action_just_pressed(&"block") and captured and not _building_busy():
		secondary()
	if _light_on:
		_burn_light(delta)
		_follow_light()
	if _reload_left >= 0.0:
		_reload_left -= delta
		if _reload_left < 0.0:
			_finish_reload()
	if _swing_t >= 0.0:
		_swing_t += delta
		if _swing_t >= _swing_len * _hit_frac:
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
	# Changing what is in hand cancels a swing (its hit would land with the new item) and a
	# reload, and takes a moment to raise the new item.
	_swing_t = -1.0
	_reload_left = -1.0
	_reload_item = &""
	_cooldown = 0.3
	guarding = false
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
			viewmodel.play_use(&"place", 0.35)
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
				if viewmodel != null:
					viewmodel.play_use(&"place", 0.5)


func secondary() -> void:
	var def: ItemDef = Content.item(current)
	if def != null and def.is_consumable():
		var res: Dictionary = Game.execute(&"inventory.consume", {"player": player.state.id, "item": current})
		if bool(res.get("ok", false)) and viewmodel != null:
			viewmodel.play_use(ViewModelHolds.use_action(def, viewmodel.hold_class))
	elif def != null and str(def.equip.get("kind", "")) == "ranged":
		_reload(def)
	elif def != null and bool(def.equip.get("throwable", false)) and _cooldown <= 0.0:
		# Melee weapons marked throwable (the spear) are thrown with the secondary button.
		_throw(def)


func _punch() -> void:
	if not player.state.stats.spend_stamina(5.0):
		return
	_cooldown = 0.6
	_begin_swing(&"punch", 0.6)
	swung.emit()


func _start_swing(def: ItemDef) -> void:
	var cost: float = def.equip_num("stamina", 10.0)
	if not player.state.stats.spend_stamina(cost):
		return
	_cooldown = def.equip_num("attack_time", 0.8)
	var style: StringName = ViewModelHolds.attack_style(def, ViewModelHolds.hold_class(def))
	_begin_swing(style if style != &"" else &"punch", _cooldown)
	Audio.play_3d(&"sfx/swing_whoosh", player.global_position + Vector3.UP * 1.4, {"volume_db": -8.0, "occlusion": false})
	swung.emit()


## Starts the swing's clock (it connects at its style's contact frame) and its arms action.
func _begin_swing(style: StringName, length: float) -> void:
	_swing_t = 0.0
	_swing_len = length
	_hit_frac = ViewModelHolds.impact_fraction(style)
	if viewmodel != null:
		viewmodel.play_attack(style, length)


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
	_impact_feedback(collider, receiver, pos, dir)
	_wear(def)
	var loud: float = def.equip_num("noise", 8.0) if def != null else 5.0
	if Stimuli.current != null:
		Stimuli.current.emit_sound(pos, loud, &"impact", player.state.id)


## What a connecting swing feels like (data/config/viewmodel.json impact.surfaces): the viewmodel's
## hit-stop and kick, plus particles where the struck thing makes none of its own (bark off a
## loose log, sparks off metal, chips off stone).
func _impact_feedback(collider: Object, receiver: Object, pos: Vector3, dir: Vector3) -> void:
	var surface: StringName = ViewModelHolds.surface_kind(collider, receiver)
	if viewmodel != null:
		viewmodel.impact(surface)
	var surf: Dictionary = (ViewModelHolds.config().get("impact", {}) as Dictionary).get("surfaces", {})
	var s: Dictionary = surf.get(String(surface), {})
	var fx: String = str(s.get("fx", ""))
	if fx != "" and Game.world != null:
		FxLibrary.burst(Game.world, fx, pos - dir * 0.03, -dir, float(s.get("fx_scale", 1.0)))
		if surface == &"bark":
			FxLibrary.burst(Game.world, "wood", pos - dir * 0.03, -dir, 0.5)


# --- Guard -----------------------------------------------------------------------------------

## Block held: raise the hold's guard if the item has one (and its Block isn't already a use:
## eating, reloading, throwing). You can't swing while guarding.
func _update_guard(want: bool) -> void:
	var def: ItemDef = Content.item(current)
	var can: bool = want and not (def != null and (def.is_consumable() or str(def.equip.get("kind", "")) == "ranged"
		or bool(def.equip.get("throwable", false)))) and ViewModelHolds.block_share(def, ViewModelHolds.hold_class(def)) > 0.0
	if can == guarding:
		return
	guarding = can
	if viewmodel != null:
		viewmodel.set_guard(can)


## How much of a blow gets through (1 = all): a raised guard facing the attacker takes its share
## (equip.block or the hold's), spending stamina per blocked hit and per point absorbed and wearing
## the weapon; without the stamina the guard is beaten down and takes nothing.
func guard_factor(info: DamageInfo) -> float:
	if not guarding or player == null or player.state == null or info.cause in [&"fall", &"fire", &"trap"]:
		return 1.0
	var g: Dictionary = ViewModelHolds.config().get("guard", {})
	var to_src: Vector3 = info.source_pos - player.global_position
	to_src.y = 0.0
	var fwd: Vector3 = -player.global_transform.basis.z
	fwd.y = 0.0
	if info.source_pos == Vector3.ZERO or to_src.length() < 0.01 or fwd.length() < 0.01:
		return 1.0
	if rad_to_deg(fwd.normalized().angle_to(to_src.normalized())) > float(g.get("arc_deg", 110.0)) * 0.5:
		return 1.0
	var def: ItemDef = Content.item(current)
	var share: float = ViewModelHolds.block_share(def, ViewModelHolds.hold_class(def))
	var cost: float = float(g.get("stamina_per_hit", 6.0)) + info.amount * share * float(g.get("stamina_per_damage", 0.4))
	if not player.state.stats.spend_stamina(cost):
		_update_guard(false)
		return 1.0
	if def != null:
		_wear(def)
	if viewmodel != null:
		viewmodel.blocked(info.amount)
	Audio.play_3d(&"sfx/hit_wood_structure", player.global_position + Vector3.UP * 1.4, {"volume_db": -4.0, "occlusion": false})
	return 1.0 - share


func _damage_for(def: ItemDef, pos: Vector3, dir: Vector3) -> DamageInfo:
	var p: Progression = player.state.progression
	var base: float = def.equip_num("damage", 6.0) if def != null else 6.0
	var dtype: StringName = StringName(str(def.equip.get("damage_type", "blunt"))) if def != null else &"blunt"
	var mult: float = 1.0 + p.modifier("melee_damage_mult")
	if dtype == &"blunt":
		mult += p.modifier("blunt_damage_mult")
	var stack: ItemStack = player.state.inventory.first(current) if def != null else null
	if stack != null and stack.quality > 0:
		mult *= ItemStack.quality_damage_mult(stack.quality)
	var info := DamageInfo.make(base * mult, dtype, &"melee", player.state.id)
	info.source_pos = player.global_position
	info.hit_pos = pos
	info.direction = dir
	info.dismember = float(def.equip.get("dismember", 0.0)) if def != null else 0.0
	info.stagger = float(def.equip.get("stagger", 0.3)) if def != null else 0.2
	if dtype == &"blunt":
		info.stagger += p.modifier("stagger_bonus")
	info.tool_power = (def.equip.get("tool_power", {}) as Dictionary).duplicate() if def != null else {}
	# tool_power.wood = chopping strength (axes, machetes); tool_power.earth = digging (shovels).
	# World setting player_harvest scales chopping and digging speed.
	var harvest: float = GameRules.current().num("player_harvest")
	if info.tool_power.has("wood"):
		info.tool_power["chop"] = float(info.tool_power["wood"]) * (1.0 + p.modifier("chop_damage_mult")) * harvest
	if info.tool_power.has("earth") or (def != null and def.provides_tool("shovel")):
		info.tool_power["dig"] = float(info.tool_power.get("earth", 1.0)) * harvest
	return info


static func _damage_receiver(o: Object) -> Object:
	var n: Node = o as Node
	var depth: int = 0
	while n != null and depth < 6:
		if n.has_method(&"take_damage"):
			return n
		if n.has_meta(&"damage_receiver"):
			var r: Variant = n.get_meta(&"damage_receiver")
			if is_instance_valid(r):
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
	var spread: float = shot_spread(def, player.crouching, player.state.progression)
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
		viewmodel.play_use(StringName("fire_%s" % viewmodel.hold_class))
	if not hit.is_empty():
		var gun: ItemStack = player.state.inventory.first(current)
		var dmg: float = def.equip_num("damage", 50.0) * (1.0 + player.state.progression.modifier("ranged_damage_mult"))
		if gun != null and gun.quality > 0:
			dmg *= ItemStack.quality_damage_mult(gun.quality)
		var info := DamageInfo.make(dmg, &"ballistic", &"firearm", player.state.id)
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


## How far (radians, each axis) a shot may wander off the crosshair: the gun's spread_deg, halved
## crouched, less with the Steady Aim perk (ranged_spread_mult, ADR-0015).
static func shot_spread(def: ItemDef, crouching: bool, prog: Progression) -> float:
	var steady: float = maxf(0.1, 1.0 + prog.modifier("ranged_spread_mult")) if prog != null else 1.0
	return deg_to_rad(def.equip_num("spread_deg", 1.5)) * (0.5 if crouching else 1.0) * steady


func _reload(def: ItemDef) -> void:
	if _reload_left >= 0.0 or _rounds_to_load(def) <= 0:
		return
	_reload_left = def.equip_num("reload_time", 2.5)
	_reload_item = current
	_cooldown = _reload_left
	if viewmodel != null:
		viewmodel.play_use(StringName("reload_%s" % viewmodel.hold_class), _reload_left)
	Audio.play_3d(&"sfx/gun_reload", player.global_position, {"volume_db": -6.0, "occlusion": false})


func _rounds_to_load(def: ItemDef) -> int:
	var stack: ItemStack = player.state.inventory.first(current)
	var ammo: StringName = StringName(str(def.equip.get("ammo", "")))
	if stack == null or ammo == &"":
		return 0
	var need: int = int(def.equip.get("mag_size", 6)) - int(stack.data.get("loaded", 0))
	return mini(need, player.state.inventory.count_of(ammo))


func _finish_reload() -> void:
	var def: ItemDef = Content.item(current)
	if current != _reload_item or def == null:
		return
	_reload_item = &""
	var n: int = _rounds_to_load(def)
	if n <= 0:
		return
	var stack: ItemStack = player.state.inventory.first(current)
	player.state.inventory.remove(StringName(str(def.equip.get("ammo", ""))), n)
	stack.data["loaded"] = int(stack.data.get("loaded", 0)) + n
	Events.inventory_changed.emit(player.state.id)


func _throw(def: ItemDef) -> void:
	if not player.state.stats.spend_stamina(def.equip_num("stamina", 6.0)):
		return
	# The very item thrown (its quality and wear) is what lands and can be picked up again.
	var thrown: Array[ItemStack] = player.state.inventory.take(current, 1)
	if thrown.is_empty():
		return
	if viewmodel != null:
		viewmodel.play_use(&"throw", 0.5)
	_cooldown = 0.7
	var proj: Node3D = load("res://src/combat/thrown_item.gd").new()
	proj.set(&"item_id", current)
	proj.set(&"stack", thrown[0])
	proj.set(&"thrower", player.state.id)
	proj.set(&"damage", def.equip_num("damage", 10.0))
	proj.set(&"origin", player.global_position)
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
	var held: ItemStack = _lit_stack()
	if not _light_on and held != null and def.durability > 0.0 and held.durability <= 0.0:
		Events.player_status_message.emit("The %s is dead." % def.display_name.to_lower(), &"warning")
		return
	_set_light(not _light_on)
	if _light_on and viewmodel != null and "lighter" in (def.equip.get("tools", []) as Array):
		viewmodel.play_use(&"light")


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


## A held flame (torch, lantern, lighter: an omni light, not a flashlight's beam) is burning: the
## Hollowed hounds keep clear of it (ADR-0034).
func has_flame_on() -> bool:
	return _light_on and _light is OmniLight3D


## A held flame lights from where it burns: the torch up in the left hand, swinging with it.
func _follow_light() -> void:
	if _light == null or not (_light is OmniLight3D) or viewmodel == null:
		return
	var anchor: Node3D = viewmodel.light_anchor()
	if anchor != null and anchor.is_inside_tree():
		_light.global_position = anchor.global_position + Vector3.UP * 0.08


## The held light's own stack: the most used one of its kind (the one already burning).
func _lit_stack() -> ItemStack:
	var best: ItemStack = null
	for s: ItemStack in player.state.inventory.stacks:
		if s.item_id == current and (best == null or s.durability < best.durability):
			best = s
	return best


## Lights burn their durability as seconds of light. Only the torch in hand burns: it is split
## from a stack of fresh ones (they used to share one durability). A torch burns out and is gone,
## a lighter runs dry and is thrown away, a flashlight's batteries die (a repair kit revives it).
func _burn_light(delta: float) -> void:
	var def: ItemDef = Content.item(current)
	if def == null or def.durability <= 0.0:
		return
	var inv: Inventory = player.state.inventory
	var stack: ItemStack = _lit_stack()
	if stack == null:
		_set_light(false)
		return
	if stack.count > 1:
		stack = stack.split(1)
		inv.stacks.append(stack)
	stack.durability -= delta
	if stack.durability > 0.0:
		return
	_set_light(false)
	if current == &"flashlight":
		stack.durability = 0.0
		Events.player_status_message.emit("The flashlight's batteries are dead.", &"warning")
	else:
		inv.take_from(stack, 1)
		Events.player_status_message.emit("The torch burns out." if current == &"torch" else "The %s is spent." % def.display_name.to_lower(), &"warning")
	Events.inventory_changed.emit(player.state.id)
