class_name PoiPieces
extends RefCounted
## Interactive POI pieces: doors (open/close, keys, locked-from-inside shortcuts, breakable),
## window glass (shatters), barricades/boards (breakable), lootable props, ladders and can-chime
## trip lines. Each reports state changes to its PoiInstance so they persist (WorldState.pois).


class Door:
	extends StaticBody3D
	var poi: Node
	var op_id: String = ""
	var state: String = "closed"
	var key: String = ""
	var hp: float = 250.0
	var inside_sign: float = 1.0
	var model_broken: String = ""
	var pivot: Node3D
	var _open_amount: float = 0.0
	var _target: float = 0.0

	func _ready() -> void:
		collision_layer = 1 << 1
		collision_mask = 0
		set_meta(&"breakable", true)
		set_meta(&"surface", "wood_floor")
		_target = 1.0 if state == "open" else 0.0
		_open_amount = _target
		_apply()

	func _process(delta: float) -> void:
		if not is_equal_approx(_open_amount, _target):
			_open_amount = move_toward(_open_amount, _target, delta * 2.2)
			_apply()

	func _apply() -> void:
		if pivot != null:
			pivot.rotation.y = -_open_amount * PI * 0.55

	func is_locked() -> bool:
		return state == "locked" or state == "locked_inside"

	func interact_text(player: Player) -> String:
		if state == "broken":
			return ""
		if state == "locked":
			if key != "" and player.state.inventory.has(StringName(key)):
				var kd: ItemDef = Content.item(StringName(key))
				return "Unlock (%s)" % (kd.display_name if kd != null else key)
			return "Locked"
		if state == "locked_inside":
			return "Unbolt door" if _player_inside(player) else "Locked from the other side"
		return "Close door" if _target > 0.5 else "Open door"

	func _player_inside(player: Player) -> bool:
		var n: Vector3 = global_transform.basis.z
		return signf((player.global_position - global_position).dot(n)) == inside_sign

	func interact(player: Player) -> void:
		match state:
			"locked":
				if key != "" and player.state.inventory.has(StringName(key)):
					state = "closed"
					Audio.play_3d(&"sfx/door_unlock", global_position + Vector3.UP, {"volume_db": -4.0})
					_save()
				else:
					Audio.play_3d(&"sfx/door_locked", global_position + Vector3.UP, {"volume_db": -6.0})
				return
			"locked_inside":
				if _player_inside(player):
					state = "closed"
					Audio.play_3d(&"sfx/door_unlock", global_position + Vector3.UP, {"volume_db": -4.0})
					_save()
				return
			"broken":
				return
		_target = 0.0 if _target > 0.5 else 1.0
		state = "open" if _target > 0.5 else "closed"
		Audio.play_3d(&"sfx/door_open" if _target > 0.5 else &"sfx/door_close", global_position + Vector3.UP, {"volume_db": -4.0})
		if Stimuli.current != null:
			Stimuli.current.emit_sound(global_position, 9.0, &"door", player.state.id)
		_save()

	func take_damage(info: DamageInfo) -> void:
		if state == "broken":
			return
		var amount: float = float(info.tool_power.get("structure", info.amount))
		hp -= amount
		Audio.play_3d(&"sfx/hit_wood_structure", info.hit_pos, {"volume_db": -3.0})
		FxLibrary.burst(get_parent(), "splinters", info.hit_pos, -info.direction, 0.4)
		if Stimuli.current != null:
			Stimuli.current.emit_sound(info.hit_pos, 16.0, &"pound", info.source_id)
		if hp <= 0.0:
			smash()

	func smash() -> void:
		state = "broken"
		Audio.play_3d(&"sfx/structure_break_wood", global_position + Vector3.UP, {"volume_db": 0.0})
		FxLibrary.burst(get_parent(), "splinters", global_position + Vector3.UP, Vector3.UP, 1.5)
		for c: Node in get_children():
			if c is CollisionShape3D:
				(c as CollisionShape3D).disabled = true
		if pivot != null:
			for c2: Node in pivot.get_children():
				if c2 is CollisionShape3D:
					(c2 as CollisionShape3D).set_deferred(&"disabled", true)
				elif c2 is MeshInstance3D and model_broken != "" and ModelLibrary.has_model(model_broken):
					(c2 as MeshInstance3D).mesh = ModelLibrary.mesh(model_broken)
				elif c2 is MeshInstance3D:
					(c2 as MeshInstance3D).visible = false
		_save()

	func _save() -> void:
		if poi != null:
			poi.call(&"set_piece_state", op_id, state)


class Breakable:
	extends StaticBody3D
	## Window glass ("glass") or boards / furniture barricades ("boards").
	var poi: Node
	var piece_id: String = ""
	var kind: String = "boards"
	var hp: float = 120.0
	var model_broken: String = ""
	var mesh_node: MeshInstance3D

	func _ready() -> void:
		collision_layer = 1 << 1
		collision_mask = 0
		set_meta(&"breakable", true)

	func take_damage(info: DamageInfo) -> void:
		var amount: float = float(info.tool_power.get("structure", info.amount))
		if kind == "glass":
			amount = 999.0
		hp -= amount
		if hp > 0.0:
			Audio.play_3d(&"sfx/hit_wood_structure", info.hit_pos, {"volume_db": -4.0})
			FxLibrary.burst(get_parent(), "splinters", info.hit_pos, -info.direction, 0.3)
			return
		smash()

	func smash() -> void:
		if kind == "glass":
			Audio.play_3d(&"sfx/glass_break", global_position + Vector3.UP, {"volume_db": 0.0})
			if Stimuli.current != null:
				Stimuli.current.emit_sound(global_position, 26.0, &"glass", &"")
		else:
			Audio.play_3d(&"sfx/structure_break_wood", global_position + Vector3.UP, {"volume_db": -2.0})
			FxLibrary.burst(get_parent(), "splinters", global_position + Vector3.UP, Vector3.UP, 1.0)
		if model_broken != "" and ModelLibrary.has_model(model_broken) and mesh_node != null:
			mesh_node.mesh = ModelLibrary.mesh(model_broken)
		elif mesh_node != null:
			mesh_node.visible = false
		for c: Node in get_children():
			if c is CollisionShape3D:
				(c as CollisionShape3D).set_deferred(&"disabled", true)
		if poi != null:
			poi.call(&"set_piece_state", piece_id, "broken")


class LootProp:
	extends StaticBody3D
	## A prop with a container: search (hold) to roll its loot once, then open/take.
	var poi: Node
	var prop: PropDef
	var cdef: ContainerDef
	var container_id: StringName = &""
	var tier: int = 1
	var bonus: bool = false
	var key: String = ""
	var inventory: Inventory = null
	var opened: bool = false

	func _ready() -> void:
		collision_layer = 1 << 2
		collision_mask = 0
		var st: Dictionary = Game.session.world.container_state(container_id) if Game.session != null else {}
		if not st.is_empty() and st.get("items") != null:
			opened = bool(st.get("opened", true))
			inventory = _new_inv()
			for d: Variant in st.get("items", []):
				var s: ItemStack = ItemStack.from_dict(d)
				if s != null:
					inventory.add(s)

	func _new_inv() -> Inventory:
		var inv := Inventory.new()
		inv.owner_id = container_id
		inv.max_slots = cdef.slots if cdef != null else 6
		return inv

	func interact_text(player: Player) -> String:
		if cdef == null:
			return ""
		if cdef.locked and not opened:
			if key != "" and player.state.inventory.has(StringName(key)):
				return "Unlock %s" % cdef.display_name
			return "%s (locked)" % cdef.display_name
		if opened:
			return "%s (empty)" % cdef.display_name if inventory == null or inventory.stacks.is_empty() else "Open %s" % cdef.display_name
		return "Search %s" % cdef.display_name

	func interact_hold_time(player: Player) -> float:
		if cdef == null or opened or (cdef.locked and not (key != "" and player.state.inventory.has(StringName(key)))):
			return 0.0
		return cdef.search_time

	func interact(player: Player) -> void:
		if cdef == null:
			return
		if cdef.locked and not opened and not (key != "" and player.state.inventory.has(StringName(key))):
			Audio.play_3d(&"sfx/door_locked", global_position, {"volume_db": -6.0})
			return
		if not opened:
			opened = true
			inventory = _new_inv()
			var rng := RandomNumberGenerator.new()
			rng.seed = Ids.hash64("loot:%d:%s" % [Game.session.world_seed, container_id])
			var ctx := LootRoller.Context.new(tier + (1 if bonus else 0), player.state.progression.gamestage(Game.session.clock.day()), rng)
			for s: ItemStack in LootRoller.roll(cdef.loot_table, ctx):
				inventory.add(s)
			if bonus:
				for s2: ItemStack in LootRoller.roll(cdef.loot_table, ctx):
					inventory.add(s2)
			Game.session.world.set_container_items(container_id, inventory, true)
			if Stimuli.current != null and cdef.noise > 0.0:
				Stimuli.current.emit_sound(global_position, cdef.noise, &"search", player.state.id)
			Audio.play_3d(&"sfx/search_container", global_position, {"volume_db": -6.0})
		var ui: Node = Game.world.get(&"ui") if Game.world != null else null
		if ui != null and ui.has_method(&"open_container"):
			ui.call(&"open_container", self)
		else:
			Game.execute(&"container.take_all", {"player": player.state.id, "container": self})

	func on_contents_changed() -> void:
		Game.session.world.set_container_items(container_id, inventory, true)


class Ladder:
	extends StaticBody3D
	## Climb by interacting: moves the player to the top/bottom landing (POI-local points).
	var top_local: Vector3
	var bottom_local: Vector3

	func _ready() -> void:
		collision_layer = 1 << 7
		collision_mask = 0

	func _ends() -> Array:
		var p: Node3D = get_parent() as Node3D
		return [p.to_global(top_local), p.to_global(bottom_local)]

	func interact_text(player: Player) -> String:
		var e: Array = _ends()
		return "Climb down" if player.global_position.y > ((e[0] as Vector3).y + (e[1] as Vector3).y) * 0.5 else "Climb up"

	func interact(player: Player) -> void:
		var e: Array = _ends()
		var up: bool = player.global_position.y <= ((e[0] as Vector3).y + (e[1] as Vector3).y) * 0.5
		player.global_position = (e[0] if up else e[1]) + Vector3.UP * 0.1
		player.velocity = Vector3.ZERO
		Audio.play_3d(&"sfx/ladder_climb", player.global_position, {"volume_db": -4.0})


class TripLine:
	extends Area3D
	## A can-chime string across a doorway: rattles (loud) when anything walks through it.
	var poi: Node
	var trap_id: String = ""
	var armed: bool = true

	func _ready() -> void:
		collision_layer = 1 << 10
		collision_mask = (1 << 3) | (1 << 4)
		body_entered.connect(_on_body)

	func _on_body(body: Node) -> void:
		if not armed:
			return
		armed = false
		Audio.play_3d(&"sfx/can_chime", global_position + Vector3.UP * 0.5, {"volume_db": 2.0, "max_distance": 70.0})
		if Stimuli.current != null:
			Stimuli.current.emit_sound(global_position, 40.0, &"trap", StringName(trap_id))
		if poi != null:
			poi.call(&"set_piece_state", trap_id, "triggered")
			poi.call(&"alert_sleepers", global_position)


class Pickup:
	extends StaticBody3D
	## A placed POI item (key, note, schematic) — taken once, remembered in the POI state.
	var poi: Node
	var pickup_id: String = ""
	var item: StringName = &""
	var count: int = 1

	func _ready() -> void:
		collision_layer = 1 << 6
		collision_mask = 0
		var model: Node3D = ItemVisuals.make_model(item)
		add_child(model)
		var cs := CollisionShape3D.new()
		var box := BoxShape3D.new()
		box.size = Vector3(0.3, 0.12, 0.3)
		cs.shape = box
		cs.position = Vector3(0, 0.06, 0)
		add_child(cs)

	func interact_text(_player: Player) -> String:
		var d: ItemDef = Content.item(item)
		return "Take %s" % (d.display_name if d != null else String(item))

	func interact(player: Player) -> void:
		var res: Dictionary = Game.execute(&"world.pickup_item", {"player": player.state.id, "item": String(item), "count": count})
		if bool(res.get("ok", false)):
			if poi != null:
				poi.call(&"set_piece_state", pickup_id, "broken")
			queue_free()
