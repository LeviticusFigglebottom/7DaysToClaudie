class_name PoiPieces
extends RefCounted
## Interactive POI pieces: doors (open/close, keys, locked-from-inside shortcuts, breakable, lock
## cues with breakable padlocks), window glass (shatters), barricades/boards (breakable), lootable
## props, ladders, pickups and the traps (ADR-0018): can-chime trip lines, bear traps, shotgun
## trip-wires, creaky floors, weak floors and alarms. Each reports state changes to its
## PoiInstance so they persist (WorldState.pois) and so the building's ambush triggers can fire.
## ADR-0022: the Hollowed set traps off by weight class (data/config/traps.json "hollowed" and each
## trap's "hollowed" block); what they set off makes its noise through the stimulus fields, and
## only the player's misstep alerts sleepers directly. The shotgun fires a spread of pellet rays.

## Layers: interactable bodies sit on "interact" (the interaction ray, not movement); breakable
## lock bodies on "hitboxes" (melee sweeps and bullets hit them, nobody bumps into them); trap
## sensors on "triggers" watching the player and the Hollowed.
const INTERACT_LAYER: int = 1 << 7
const LOCK_LAYER: int = 1 << 9
const TRIGGER_LAYER: int = 1 << 10
const PLAYER_LAYER: int = 1 << 3
const ENEMY_LAYER: int = 1 << 4


## Tuning for one trap type (data/config/traps.json).
static func cfg(section: String) -> Dictionary:
	return Content.config(&"traps").get(section, {})


## Weight class index of a Hollowed (traps.json hollowed.classes: light < normal < heavy).
static func weight_of(e: Enemy) -> int:
	var h: Dictionary = cfg("hollowed")
	var classes: Array = h.get("classes", ["light", "normal", "heavy"])
	var w: String = str((h.get("weights", {}) as Dictionary).get(String(e.def.id), h.get("default_weight", "normal")))
	return maxi(0, classes.find(w))


## A trap type's rules for the Hollowed ({} = they never set it off).
static func hollowed_rule(trap_type: String) -> Dictionary:
	return cfg(trap_type).get("hollowed", {})


## Whether a living Hollowed is heavy enough to set this trap type off.
static func hollowed_sets_off(trap_type: String, e: Enemy) -> bool:
	var rule: Dictionary = hollowed_rule(trap_type)
	if not rule.has("min_weight") or e == null or not e.is_alive():
		return false
	var classes: Array = cfg("hollowed").get("classes", ["light", "normal", "heavy"])
	return weight_of(e) >= maxi(0, classes.find(str(rule["min_weight"])))


## Whether a trap a Hollowed set off fires the trap's ambush triggers.
static func hollowed_fires(trap_type: String) -> bool:
	return bool(hollowed_rule(trap_type).get("fires_trigger", true))


## Whether damage came from a player (their blows and bullets break a door "by the player"; the
## Hum's do not).
static func by_player(info: DamageInfo) -> bool:
	return Game.session != null and Game.session.players.has(info.source_id)


## A generated model, or (before `make assets`) a box of `size` standing on its origin.
static func model_mesh(model_id: String, size: Vector3, color: Color) -> Mesh:
	if ModelLibrary.has_model(model_id):
		return ModelLibrary.mesh(model_id)
	var b := BoxMesh.new()
	b.size = size.max(Vector3(0.01, 0.01, 0.01))
	var arr: Array = b.get_mesh_arrays()
	var v: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
	for i: int in v.size():
		v[i] += Vector3(0, size.y * 0.5, 0)
	arr[Mesh.ARRAY_VERTEX] = v
	var am := ArrayMesh.new()
	am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = 0.7
	am.surface_set_material(0, m)
	return am


## Size of a trap/lock model from its PropDef (data/props/traps.json), for fallbacks and shapes.
static func model_size(prop_id: String, default: Vector3) -> Vector3:
	var pd: PropDef = Content.get_def(&"prop", StringName(prop_id)) as PropDef
	return pd.size if pd != null else default


static func _box_shape(body: CollisionObject3D, size: Vector3, xf: Transform3D) -> CollisionShape3D:
	var cs := CollisionShape3D.new()
	var b := BoxShape3D.new()
	b.size = size
	cs.shape = b
	cs.transform = xf
	body.add_child(cs)
	return cs


## The opening id a door leaf, pane, boards or barricade piece belongs to.
static func opening_of(piece_id: String) -> String:
	for suffix: String in ["_glass", "_boards", "_bar", "_l", "_r"]:
		if piece_id.ends_with(suffix):
			return piece_id.trim_suffix(suffix)
	return piece_id


class Door:
	extends StaticBody3D
	var poi: Node
	var op_id: String = ""
	## The authored opening this leaf belongs to (op_id without _l/_r) — triggers and alarms.
	var opening_id: String = ""
	var state: String = "closed"
	var key: String = ""
	var hp: float = 250.0
	var inside_sign: float = 1.0
	var model_broken: String = ""
	var pivot: Node3D
	## The other leaf of a double door (unlocking or breaking the lock frees both).
	var partner: Door = null
	## Lock cue (PoiLayout.LOCK_KINDS) and its visual on the leaf; lock_open is what replaces a
	## padlock once it is off (the hasp hanging open).
	var lock_kind: String = ""
	var lock_mesh: MeshInstance3D = null
	var lock_open_model: String = ""
	var lock_body: Node = null
	## Hinge yaw when closed: PI for the right leaf of a double door (it hangs toward the centre).
	var flip: float = 0.0
	## The leaf's collision shape. It stays a direct child of this body (a shape under the plain
	## pivot Node3D never registers with physics) and _apply() moves it with the hinge.
	var leaf_shape: CollisionShape3D
	var leaf_local := Transform3D.IDENTITY
	var _open_amount: float = 0.0
	var _target: float = 0.0
	## Whether the last blow came from a player (an alarm on the door rouses the whole building).
	var _by_player: bool = true
	## A vault door has already roused its building (ADR-0026).
	var _vault_roused: bool = false

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
		if pivot == null:
			return
		# Both leaves of a double door swing to the same side of the wall.
		pivot.rotation.y = flip + _open_amount * PI * 0.55 * (1.0 if flip != 0.0 else -1.0)
		if leaf_shape != null:
			leaf_shape.transform = pivot.transform * leaf_local

	func is_broken() -> bool:
		return state == "broken"

	func is_locked() -> bool:
		return state == "locked" or state == "locked_inside"

	func interact_text(player: Player) -> String:
		if state == "broken":
			return ""
		if state == "locked":
			if key != "" and player.state.inventory.has(StringName(key)):
				var kd: ItemDef = Content.item(StringName(key))
				return "Unlock (%s)" % (kd.display_name if kd != null else key)
			match lock_kind:
				"vault":
					return "Vault door: needs the combination (or cut it open)"
				"padlock":
					return "Padlocked"
				"chain":
					return "Chained shut"
			return "Locked"
		if state == "locked_inside":
			return "Slide the bolt back" if _player_inside(player) else "Bolted from the other side"
		return "Close door" if _target > 0.5 else "Open door"

	func _player_inside(player: Player) -> bool:
		var n: Vector3 = global_transform.basis.z
		return signf((player.global_position - global_position).dot(n)) == inside_sign

	func interact(player: Player) -> void:
		match state:
			"locked":
				if key != "" and player.state.inventory.has(StringName(key)):
					unlock(false)
					Audio.play_3d(&"sfx/door_unlock", global_position + Vector3.UP, {"volume_db": -4.0})
					if lock_kind == "vault":
						Audio.play_3d(&"sfx/metal_clang", global_position + Vector3.UP, {"volume_db": -2.0})
				else:
					Audio.play_3d(&"sfx/door_locked", global_position + Vector3.UP, {"volume_db": -6.0})
				return
			"locked_inside":
				if _player_inside(player):
					unlock(false)
					Audio.play_3d(&"sfx/door_unlock", global_position + Vector3.UP, {"volume_db": -4.0})
				else:
					Audio.play_3d(&"sfx/door_locked", global_position + Vector3.UP, {"volume_db": -6.0})
				return
			"broken":
				return
		_target = 0.0 if _target > 0.5 else 1.0
		state = "open" if _target > 0.5 else "closed"
		Audio.play_3d(&"sfx/door_open" if _target > 0.5 else &"sfx/door_close", global_position + Vector3.UP, {"volume_db": -4.0})
		if Stimuli.current != null:
			Stimuli.current.emit_sound(global_position, 9.0, &"door", player.state.id)
		_save()
		if state == "open" and poi != null:
			poi.call(&"on_opening_event", opening_id, global_position + Vector3.UP)

	## Key, bolt or a broken padlock: the door (and its other leaf) is now just closed. `broke`:
	## the lock was smashed off rather than opened.
	func unlock(broke: bool) -> void:
		if not is_locked():
			return
		state = "closed"
		_lock_off(broke)
		_save()
		if partner != null and partner.is_locked():
			partner.unlock(broke)

	func _lock_off(broke: bool) -> void:
		if lock_body != null and is_instance_valid(lock_body):
			lock_body.queue_free()
		lock_body = null
		if lock_mesh == null:
			return
		if lock_kind == "padlock" and lock_open_model != "":
			lock_mesh.mesh = PoiPieces.model_mesh(lock_open_model, PoiPieces.model_size("lock_hasp_open", Vector3(0.18, 0.12, 0.03)), Color(0.35, 0.33, 0.3))
		elif lock_kind in ["padlock", "chain"]:
			lock_mesh.visible = false
		if broke:
			FxLibrary.burst(get_parent(), "sparks", lock_mesh.global_position, global_transform.basis.z, 0.6)

	func take_damage(info: DamageInfo) -> void:
		if state == "broken":
			return
		_by_player = PoiPieces.by_player(info)
		var amount: float = float(info.tool_power.get("structure", info.amount))
		hp -= amount
		if poi != null and hp > 0.0:
			poi.call(&"set_piece_hp", op_id, hp)
		if lock_kind == "vault" and is_locked():
			_cut(info)
		else:
			Audio.play_3d(&"sfx/hit_wood_structure", info.hit_pos, {"volume_db": -3.0})
			FxLibrary.burst(get_parent(), "splinters", info.hit_pos, -info.direction, 0.4)
			if Stimuli.current != null:
				Stimuli.current.emit_sound(info.hit_pos, 16.0, &"pound", info.source_id)
		if hp <= 0.0:
			smash()

	## Cutting at a vault door (ADR-0026): sparks and a screech of steel that carries like an alarm
	## (held ambushers within their wake radius rise to it), and the first blow a player lands
	## rouses the whole building, as a set-off alarm does. It takes the opening's hit points.
	func _cut(info: DamageInfo) -> void:
		Audio.play_3d(&"sfx/hit_metal", info.hit_pos, {"volume_db": 0.0})
		FxLibrary.burst(get_parent(), "sparks", info.hit_pos, -info.direction, 0.8)
		if Stimuli.current != null:
			Stimuli.current.emit_sound(info.hit_pos, float(PoiPieces.cfg("vault").get("noise", 48.0)), &"alarm", info.source_id)
		if _by_player and not _vault_roused and poi != null:
			_vault_roused = true
			poi.call(&"alarm", info.hit_pos, true)

	func smash() -> void:
		state = "broken"
		Audio.play_3d(&"sfx/structure_break_wood", global_position + Vector3.UP, {"volume_db": 0.0})
		FxLibrary.burst(get_parent(), "splinters", global_position + Vector3.UP, Vector3.UP, 1.5)
		for c: Node in get_children():
			if c is CollisionShape3D:
				(c as CollisionShape3D).set_deferred(&"disabled", true)
		if lock_body != null and is_instance_valid(lock_body):
			lock_body.queue_free()
		lock_body = null
		if pivot != null:
			for c2: Node in pivot.get_children():
				if c2 == lock_mesh:
					(c2 as MeshInstance3D).visible = false
				elif c2 is MeshInstance3D and model_broken != "" and ModelLibrary.has_model(model_broken):
					(c2 as MeshInstance3D).mesh = ModelLibrary.mesh(model_broken)
				elif c2 is MeshInstance3D:
					(c2 as MeshInstance3D).visible = false
		_save()
		if poi != null:
			poi.call(&"on_opening_event", opening_id, global_position + Vector3.UP, _by_player)

	func _save() -> void:
		if poi != null:
			poi.call(&"set_piece_state", op_id, state)


class LockBody:
	extends StaticBody3D
	## A padlock or chain on a locked door: melee hits and bullets wear it down (loud clanks,
	## data/config/traps.json padlock); at 0 it breaks off and the door is merely closed — the
	## noisy alternative to finding the key.
	var door: Door
	var piece_id: String = ""
	var hp: float = 60.0

	func _ready() -> void:
		collision_layer = PoiPieces.LOCK_LAYER
		collision_mask = 0

	func is_broken() -> bool:
		return hp <= 0.0

	func take_damage(info: DamageInfo) -> void:
		if hp <= 0.0 or door == null:
			return
		var amount: float = maxf(float(info.amount), float(info.tool_power.get("structure", 0.0)))
		hp -= amount
		var loud: float = float(PoiPieces.cfg("padlock").get("noise", 22.0))
		if Stimuli.current != null:
			Stimuli.current.emit_sound(global_position, loud, &"pound", info.source_id)
		FxLibrary.burst(get_parent(), "sparks", info.hit_pos if info.hit_pos != Vector3.ZERO else global_position, -info.direction, 0.5)
		if hp > 0.0:
			Audio.play_3d(&"sfx/lock_padlock_hit", global_position, {"volume_db": -1.0, "max_distance": 60.0})
			if door.poi != null:
				door.poi.call(&"set_piece_hp", piece_id, hp)
			return
		Audio.play_3d(&"sfx/lock_padlock_break", global_position, {"volume_db": 0.0, "max_distance": 60.0})
		door.unlock(true)


class Breakable:
	extends StaticBody3D
	## Window glass ("glass") or boards / furniture barricades ("boards").
	var poi: Node
	var piece_id: String = ""
	## The authored opening this piece sits in (triggers, alarms).
	var opening_id: String = ""
	var kind: String = "boards"
	var hp: float = 120.0
	var model_broken: String = ""
	var mesh_node: MeshInstance3D
	## Whether the last blow came from a player (see Door._by_player).
	var _by_player: bool = true

	func _ready() -> void:
		collision_layer = 1 << 1
		collision_mask = 0
		set_meta(&"breakable", true)

	func is_broken() -> bool:
		return hp <= 0.0

	func take_damage(info: DamageInfo) -> void:
		# Already smashed: its shape is being disabled, but a second hit in the same frame (or a
		# Hollow still pounding the frame) must not replay the break or count it again.
		if hp <= 0.0:
			return
		_by_player = PoiPieces.by_player(info)
		var amount: float = float(info.tool_power.get("structure", info.amount))
		if kind == "glass":
			amount = 999.0
		hp -= amount
		if hp > 0.0:
			if poi != null:
				poi.call(&"set_piece_hp", piece_id, hp)
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
			poi.call(&"on_opening_event", opening_id, global_position + Vector3.UP, _by_player)


class LootProp:
	extends StaticBody3D
	## A prop with a container: search (hold) to roll its loot once, then open/take.
	var poi: Node
	var prop: PropDef
	var cdef: ContainerDef
	var container_id: StringName = &""
	## The authored prop key (its "id", else its list index) — container triggers.
	var prop_key: String = ""
	var tier: int = 1
	var bonus: bool = false
	var key: String = ""
	var inventory: Inventory = null
	var opened: bool = false
	## Restocks under the loot_respawn_days world setting (supply drops do not).
	var respawns: bool = true

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
		if opened and _respawn_generation() >= 0:
			# Restocked under loot_respawn_days: say so (it used to keep reading "empty").
			return "Search %s (restocked)" % cdef.display_name
		if opened:
			return "%s (empty)" % cdef.display_name if inventory == null or inventory.stacks.is_empty() else "Open %s" % cdef.display_name
		return "Search %s" % cdef.display_name

	func interact_hold_time(player: Player) -> float:
		if cdef == null or (cdef.locked and not opened and not (key != "" and player.state.inventory.has(StringName(key)))):
			return 0.0
		if opened and _respawn_generation() < 0:
			return 0.0
		return cdef.search_time

	func interact(player: Player) -> void:
		if cdef == null:
			return
		if cdef.locked and not opened and not (key != "" and player.state.inventory.has(StringName(key))):
			Audio.play_3d(&"sfx/door_locked", global_position, {"volume_db": -6.0})
			return
		var gen: int = _respawn_generation()
		if not opened or gen >= 0:
			var first: bool = not opened
			opened = true
			inventory = _new_inv()
			gen = maxi(gen, 0)
			var rng := RandomNumberGenerator.new()
			rng.seed = Ids.hash64("loot:%d:%s:%d" % [Game.session.world_seed, container_id, gen]) if gen > 0 \
				else Ids.hash64("loot:%d:%s" % [Game.session.world_seed, container_id])
			var ctx := LootRoller.Context.new(tier + (1 if bonus else 0), Game.session.gamestage(player.state), rng)
			ctx.quality_bonus = player.state.progression.modifier("loot_quality_bonus")
			for s: ItemStack in LootRoller.roll(cdef.loot_table, ctx):
				inventory.add(s)
			if bonus:
				for s2: ItemStack in LootRoller.roll(cdef.loot_table, ctx):
					inventory.add(s2)
			Game.session.world.set_container_items(container_id, inventory, true, Game.session.clock.day(), gen)
			player.state.progression.award("loot_container", tier)
			Events.container_looted.emit(player.state.id, container_id, tier)
			if Stimuli.current != null and cdef.noise > 0.0:
				Stimuli.current.emit_sound(global_position, cdef.noise, &"search", player.state.id)
			Audio.play_3d(&"sfx/search_container", global_position, {"volume_db": -6.0})
			if first and poi != null:
				poi.call(&"on_container_searched", prop_key, global_position)
		var ui: Node = Game.world.get(&"ui") if Game.world != null else null
		if ui != null and ui.has_method(&"open_container"):
			ui.call(&"open_container", self)
		else:
			Game.execute(&"container.take_all", {"player": player.state.id, "container": self})

	func on_contents_changed() -> void:
		Game.session.world.set_container_items(container_id, inventory, true)

	## Loot respawn (world setting loot_respawn_days): an emptied container restocks once that
	## many days have passed since it was last rolled. Returns the next roll generation, or -1.
	func _respawn_generation() -> int:
		var days: int = GameRules.current().integer("loot_respawn_days")
		if not respawns or not opened or days <= 0 or (inventory != null and not inventory.stacks.is_empty()):
			return -1
		var st: Dictionary = Game.session.world.container_state(container_id)
		if Game.session.clock.day() - int(st.get("rolled_day", 0)) < days:
			return -1
		return int(st.get("gen", 0)) + 1


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
	## A can-chime string across a doorway: rattles (loud) when anyone walks through it, the player
	## or a Hollowed (traps.json can_chime). The player's misstep alerts the sleepers near at once;
	## a Hollowed's rattle wakes them by hearing it (ADR-0022).
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
		var player: bool = body is Player
		if not player and not (body is Enemy and PoiPieces.hollowed_sets_off("can_chime", body as Enemy)):
			return
		armed = false
		var t: Dictionary = PoiPieces.cfg("can_chime")
		var loud: float = float(t.get("noise", 40.0))
		Audio.play_3d(&"sfx/can_chime", global_position + Vector3.UP * 0.5, {"volume_db": float(t.get("volume_db", 2.0)), "max_distance": 70.0})
		if Stimuli.current != null:
			Stimuli.current.emit_sound(global_position, loud, &"trap", StringName(trap_id))
		if poi != null:
			poi.call(&"set_piece_state", trap_id, "triggered")
			if player:
				poi.call(&"alert_sleepers", global_position, float(t.get("alert_radius", 16.0)))
			else:
				poi.call(&"on_trap_noise", global_position, loud, &"trap")
			if player or PoiPieces.hollowed_fires("can_chime"):
				poi.call(&"on_trap_fired", trap_id, global_position)


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
				poi.call(&"on_pickup_taken", pickup_id, global_position)
			queue_free()


# --- Traps (ADR-0018) ---------------------------------------------------------------------------

class Trap:
	extends Node3D
	## Base of the authored traps: an id, a type, its persistent state through the PoiInstance
	## ("armed" / "sprung" / "disarmed"), and the crouched disarm interaction (an interact-layer
	## body child routes the look ray here) that runs the poi.disarm_trap command.
	var poi: Node
	var trap_id: String = ""
	var type: String = ""
	## Display name in prompts ("bear trap").
	var label: String = "trap"
	var interact_body: StaticBody3D = null

	func trap_state() -> String:
		return str(poi.call(&"trap_state", trap_id)) if poi != null else "armed"

	func is_armed() -> bool:
		return trap_state() == "armed"

	func tuning() -> Dictionary:
		return PoiPieces.cfg(type)

	## A box the interaction ray can find (on the interact layer: nothing collides with it).
	func add_interact_box(size: Vector3, xf: Transform3D) -> void:
		interact_body = StaticBody3D.new()
		interact_body.name = "Interact"
		interact_body.collision_layer = PoiPieces.INTERACT_LAYER
		interact_body.collision_mask = 0
		PoiPieces._box_shape(interact_body, size, xf)
		add_child(interact_body)

	## Trap sensor watching `mask` bodies, and the Hollowed too when this trap type's rules let them
	## set it off (traps.json "hollowed": the builder asks for the player; `type` is set by then).
	func add_sensor(size: Vector3, xf: Transform3D, mask: int) -> Area3D:
		var a := Area3D.new()
		a.name = "Sensor"
		a.collision_layer = PoiPieces.TRIGGER_LAYER
		if PoiPieces.hollowed_rule(type).has("min_weight"):
			mask |= PoiPieces.ENEMY_LAYER
		a.collision_mask = mask
		a.monitorable = false
		PoiPieces._box_shape(a, size, xf)
		add_child(a)
		return a

	func interact_text(player: Player) -> String:
		var st: String = trap_state()
		if st == "armed":
			return ("Disarm %s" % label) if player.crouching else ("%s (crouch to disarm)" % label.capitalize())
		if st == "sprung" and not (tuning().get("salvage_yield", {}) as Dictionary).is_empty():
			return "Salvage %s" % label
		return ""

	func interact(player: Player) -> void:
		var st: String = trap_state()
		if st == "armed" and not player.crouching:
			Events.player_status_message.emit("Crouch to work the %s safely." % label, &"info")
			return
		if st == "disarmed" or poi == null:
			return
		Game.execute(&"poi.disarm_trap", {"player": String(player.state.id), "poi": String(poi.get(&"instance_id")), "trap": trap_id})

	## Called by PoiInstance.disarm_trap: the mechanism is taken apart.
	func on_disarmed() -> void:
		Audio.play_3d(&"sfx/trap_disarm", global_position + Vector3.UP * 0.3, {"volume_db": -4.0})
		if interact_body != null:
			interact_body.queue_free()
			interact_body = null

	func fired(at: Vector3) -> void:
		if poi != null:
			poi.call(&"on_trap_fired", trap_id, at)

	## After it went off: the player's misstep alerts the sleepers near (radius); a Hollowed's
	## wakes them through the stimulus fields, or rouses them while nobody is spawned; its ambush
	## triggers fire unless the rules say a Hollowed does not count (ADR-0022).
	func went_off(at: Vector3, player: bool, radius: float, loudness: float, kind: StringName) -> void:
		if poi == null:
			return
		if player:
			poi.call(&"alert_sleepers", at, radius)
		else:
			poi.call(&"on_trap_noise", at, loudness, kind)
		if player or PoiPieces.hollowed_fires(type):
			fired(at)


class BearTrap:
	extends Trap
	## Steel jaws half-hidden in debris. Stepping in snaps them shut: damage, bleeding, the leg held
	## for root_seconds (Jump or Use to struggle free sooner) and a loud snap. A Hollow walking
	## into it takes the bite instead. Crouch-interact disarms it (scrap metal).
	var mesh: MeshInstance3D
	var _held: Player = null
	var _hold_t: float = 0.0
	var _hold_at := Vector3.ZERO

	func _ready() -> void:
		# After the player's own movement each physics frame, so the pin holds.
		process_physics_priority = 10
		label = "bear trap"

	func on_body(body: Node) -> void:
		if not is_armed():
			return
		if body is Player and (body as Player).state != null and (body as Player).state.stats.alive:
			_spring(body as Player, null)
		elif body is Enemy and PoiPieces.hollowed_sets_off(type if type != "" else "bear_trap", body as Enemy):
			_spring(null, body as Enemy)

	func _spring(player: Player, enemy: Enemy) -> void:
		var t: Dictionary = tuning()
		if poi != null:
			poi.call(&"set_trap_state", trap_id, "sprung")
		show_sprung()
		var pos: Vector3 = global_position + Vector3.UP * 0.2
		Audio.play_3d(&"sfx/trap_bear_snap", pos, {"volume_db": 3.0, "max_distance": 70.0})
		if Stimuli.current != null:
			Stimuli.current.emit_sound(pos, float(t.get("noise", 32.0)), &"trap", StringName(trap_id))
		if player != null:
			var info := DamageInfo.make(float(t.get("damage", 25.0)), &"pierce", &"trap", StringName(trap_id))
			info.hit_pos = player.global_position + Vector3.UP * 0.3
			info.source_pos = pos
			info.direction = Vector3.UP
			player.take_damage(info)
			player.state.stats.add_wound(float(t.get("bleed", 0.35)))
			_held = player
			_hold_t = float(t.get("root_seconds", 2.5))
			_hold_at = player.global_position
			Events.player_status_message.emit("A bear trap has your leg. Struggle free (Jump).", &"warning")
		elif enemy != null:
			var info2 := DamageInfo.make(float(t.get("enemy_damage", 60.0)), &"pierce", &"trap", StringName(trap_id))
			info2.hit_pos = enemy.global_position + Vector3.UP * 0.3
			info2.source_pos = pos
			info2.direction = Vector3.UP
			enemy.take_damage(info2)
		went_off(pos, player != null, float(t.get("alert_radius", 14.0)), float(t.get("noise", 32.0)), &"trap")

	func show_sprung() -> void:
		if mesh != null:
			mesh.mesh = PoiPieces.model_mesh("props/trap_bear_sprung", PoiPieces.model_size("trap_bear_sprung", Vector3(0.42, 0.12, 0.3)), Color(0.25, 0.22, 0.2))

	func is_holding() -> bool:
		return _held != null

	func _physics_process(delta: float) -> void:
		if _held == null:
			return
		if not is_instance_valid(_held) or _held.state == null or not _held.state.stats.alive:
			_held = null
			return
		# The jaws hold the leg: no walking away (a hop on the spot is all a jump gets).
		_held.global_position.x = _hold_at.x
		_held.global_position.z = _hold_at.z
		_held.velocity.x = 0.0
		_held.velocity.z = 0.0
		if _held.input_enabled and (Input.is_action_just_pressed(&"jump") or Input.is_action_just_pressed(&"interact")):
			_hold_t -= float(tuning().get("struggle_seconds", 0.45))
			Audio.play_3d(&"sfx/trap_bear_rattle", global_position + Vector3.UP * 0.2, {"volume_db": -6.0})
		_hold_t -= delta
		if _hold_t <= 0.0:
			_held = null
			Audio.play_3d(&"sfx/trap_bear_rattle", global_position + Vector3.UP * 0.2, {"volume_db": -2.0})

	func on_disarmed() -> void:
		super.on_disarmed()
		_held = null
		if mesh != null:
			mesh.visible = false


class ShotgunTrap:
	extends Trap
	## A tripwire across a doorway and a shotgun lashed to a chair beside it, its barrels across the
	## doorway. Crossing it (the player, or any Hollowed: traps.json shotgun.hollowed) fires it: a
	## spread of pellet rays from the muzzle (ADR-0022). Walls, furniture and the first body in the
	## way stop a pellet; each carries its share of the damage, falling off with the distance it
	## flew; a body takes all its pellets as one hit (bleeding for the player, a chance to sever a
	## limb for the Hollowed). A gunshot the whole street hears (it wakes held ambushers close by
	## too). Crouch-interact on the wire disarms it (cordage, scrap).
	## What stops a pellet: the building shell and solid props (layer 1), containers (layer 3),
	## the player and the Hollowed. Doors and glass (layer 2) do not: a leaf swung open beside the
	## gun must not shield the doorway.
	const PELLET_MASK: int = 1 | (1 << 2) | (1 << 3) | (1 << 4)
	var wire: Node3D
	## Muzzle position and aim direction in this node's frame (set by the builder).
	var muzzle := Vector3.ZERO
	var aim := Vector3.FORWARD
	## The wire pulls the trigger a moment after it is caught: whoever caught it is in the doorway,
	## in front of the barrels, when the charge goes off (-1 = not pulled).
	var _pull_t: float = -1.0
	var _by_player: bool = true

	func _ready() -> void:
		label = "shotgun trap"

	func on_body(body: Node) -> void:
		if not is_armed() or _pull_t >= 0.0:
			return
		var player: bool = body is Player and (body as Player).state != null and (body as Player).state.stats.alive
		if player or (body is Enemy and PoiPieces.hollowed_sets_off("shotgun", body as Enemy)):
			_by_player = player
			_pull_t = float(tuning().get("pull_seconds", 0.12))
			Audio.play_3d(&"sfx/trap_disarm", global_position + Vector3.UP * 0.4, {"volume_db": -10.0})

	func _physics_process(delta: float) -> void:
		if _pull_t < 0.0:
			return
		_pull_t -= delta
		if _pull_t <= 0.0:
			_pull_t = -1.0
			fire()

	## The pellets' directions (world), a fixed pattern for this trap: uniform over the disc of
	## half angle spread_deg around `dir`, seeded by the building and the trap.
	func pellet_dirs(dir: Vector3) -> Array[Vector3]:
		var t: Dictionary = tuning()
		var n: int = maxi(1, int(t.get("pellets", 9)))
		var spread: float = tan(deg_to_rad(float(t.get("spread_deg", 7.0))))
		var rng := RandomNumberGenerator.new()
		rng.seed = Ids.hash64("pellets:%s:%s" % [String(poi.get(&"instance_id")) if poi != null else "", trap_id])
		var side: Vector3 = dir.cross(Vector3.UP).normalized() if absf(dir.y) < 0.98 else Vector3.RIGHT
		var up: Vector3 = side.cross(dir).normalized()
		var out: Array[Vector3] = []
		for i: int in n:
			var r: float = sqrt(rng.randf()) * spread
			var a: float = rng.randf() * TAU
			out.append((dir + side * (cos(a) * r) + up * (sin(a) * r)).normalized())
		return out

	## Casts every pellet from muzzle `m`: [{collider, pos, normal, dist}] for the pellets that hit
	## something within `far` (in pellet order).
	func cast_pellets(m: Vector3, dirs: Array[Vector3], far: float) -> Array[Dictionary]:
		var space: PhysicsDirectSpaceState3D = get_world_3d().direct_space_state
		var exclude: Array[RID] = []
		var rig: CollisionObject3D = get_node_or_null(^"RigBody") as CollisionObject3D
		if rig != null:
			exclude.append(rig.get_rid())
		var out: Array[Dictionary] = []
		for d: Vector3 in dirs:
			var q := PhysicsRayQueryParameters3D.create(m, m + d * far, PELLET_MASK)
			q.exclude = exclude
			var hit: Dictionary = space.intersect_ray(q)
			if hit.is_empty():
				continue
			out.append({"collider": hit["collider"], "pos": hit["position"], "normal": hit["normal"],
				"dist": m.distance_to(hit["position"])})
		return out

	## Sums the pellets per body: collider -> {"share": sum of falloff (0..pellets), "pos": first hit,
	## "n": pellets}. Walls and props take theirs and stop them.
	func pellet_hits(m: Vector3, dir: Vector3) -> Dictionary:
		var t: Dictionary = tuning()
		var near: float = float(t.get("near", 1.5))
		var far: float = float(t.get("far", 9.0))
		var out: Dictionary = {}
		var puffs: int = 0
		for h: Dictionary in cast_pellets(m, pellet_dirs(dir), far):
			var c: Object = h["collider"]
			# Bodies take pellets (and a test target marked "pellet_target"); everything else stops them.
			if c is Player or c is Enemy or (c != null and c.has_meta(&"pellet_target")):
				var falloff: float = 1.0 - clampf((float(h["dist"]) - near) / maxf(far - near, 0.1), 0.0, 1.0)
				if not out.has(c):
					out[c] = {"share": 0.0, "pos": h["pos"], "n": 0}
				out[c]["share"] = float(out[c]["share"]) + falloff
				out[c]["n"] = int(out[c]["n"]) + 1
			elif puffs < 4 and get_parent() != null:
				puffs += 1
				FxLibrary.burst(get_parent(), "dust", h["pos"], h["normal"], 0.25)
		return out

	func fire() -> void:
		if not is_armed():
			return
		var t: Dictionary = tuning()
		if poi != null:
			poi.call(&"set_trap_state", trap_id, "sprung")
		if wire != null:
			wire.visible = false
		var m: Vector3 = to_global(muzzle)
		var dir: Vector3 = (global_transform.basis * aim).normalized()
		Audio.play_3d(&"sfx/trap_shotgun_blast", m, {"volume_db": 6.0, "max_distance": 220.0, "occlusion": false})
		FxLibrary.burst(get_parent(), "sparks", m, dir, 1.2)
		FxLibrary.burst(get_parent(), "dust", m + dir * 0.4, dir, 0.6)
		_flash(m)
		var loud: float = float(t.get("noise", 120.0))
		if Stimuli.current != null:
			Stimuli.current.emit_sound(m, loud, &"gunshot", StringName(trap_id))
		if Game.session != null:
			Game.session.heat.add(m, float(t.get("heat", 14.0)))
		var n: float = float(maxi(1, int(t.get("pellets", 9))))
		var hits: Dictionary = pellet_hits(m, dir)
		for c: Object in hits:
			var h: Dictionary = hits[c]
			var share: float = float(h["share"]) / n
			var hp: Vector3 = h["pos"]
			if c is Player and (c as Player).state != null:
				var info := DamageInfo.make(float(t.get("damage", 60.0)) * share, &"ballistic", &"trap", StringName(trap_id))
				info.hit_pos = hp
				info.source_pos = m
				info.direction = (hp - m).normalized()
				(c as Player).take_damage(info)
				(c as Player).state.stats.add_wound(float(t.get("bleed", 0.45)) * share)
			elif is_instance_valid(c) and c.has_method(&"take_damage"):
				if c is Enemy and not (c as Enemy).is_alive():
					continue
				var info2 := DamageInfo.make(float(t.get("enemy_damage", 150.0)) * share, &"ballistic", &"trap", StringName(trap_id))
				info2.hit_pos = hp
				info2.source_pos = m
				info2.direction = (hp - m).normalized()
				info2.dismember = 0.3 * share
				c.call(&"take_damage", info2)
		went_off(m, _by_player, float(t.get("alert_radius", 30.0)), loud, &"gunshot")

	func _flash(at: Vector3) -> void:
		var l := OmniLight3D.new()
		l.light_color = Color(1.0, 0.78, 0.45)
		l.light_energy = 6.0
		l.omni_range = 7.0
		get_parent().add_child(l)
		l.global_position = at
		var tw: Tween = l.create_tween()
		tw.tween_property(l, "light_energy", 0.0, 0.12)
		tw.tween_callback(l.queue_free)

	func on_disarmed() -> void:
		super.on_disarmed()
		if wire != null:
			wire.visible = false


class CreakyFloor:
	extends Trap
	## Loose, warped boards: every stride across them groans — loud underfoot, barely a whisper
	## crouched. The player's first loud groan counts as the trap firing (once) for ambush triggers.
	## The Hollowed make them groan too (ADR-0022): a sound cue for the player only (no noise for
	## the Hollowed to hear, no ambush: traps.json creaky_floor.hollowed).
	## Bodies on the boards: body -> [last position, metres walked since the last groan].
	var _on: Dictionary = {}

	func _ready() -> void:
		label = "loose boards"

	func on_enter(body: Node) -> void:
		if body is Player or (body is Enemy and PoiPieces.hollowed_sets_off("creaky_floor", body as Enemy)):
			_on[body] = [(body as Node3D).global_position, 0.0]

	func on_exit(body: Node) -> void:
		_on.erase(body)

	func interact_text(_player: Player) -> String:
		return ""

	func _physics_process(_delta: float) -> void:
		if _on.is_empty():
			return
		var t: Dictionary = tuning()
		for body: Variant in _on.keys():
			var b: Node3D = body as Node3D
			if not is_instance_valid(b) or (b is Enemy and not (b as Enemy).is_alive()):
				_on.erase(body)
				continue
			var rec: Array = _on[body]
			var p: Vector3 = b.global_position
			var last: Vector3 = rec[0]
			var walked: float = float(rec[1]) + Vector2(p.x - last.x, p.z - last.z).length()
			var player: Player = b as Player
			var stride: float = float(t.get("stride", 0.75)) if player != null else float((t.get("hollowed", {}) as Dictionary).get("stride", 0.9))
			if walked >= stride:
				walked = 0.0
				if player != null:
					creak(player.crouching, p, player.state.id if player.state != null else &"")
				else:
					creak_under_hollowed(p)
			_on[body] = [p, walked]

	func creak(quiet: bool, at: Vector3, source: StringName = &"") -> void:
		var t: Dictionary = tuning()
		Audio.play_3d(&"sfx/trap_floor_creak", at, {"volume_db": -16.0 if quiet else -1.0, "max_distance": 25.0 if quiet else 55.0})
		if Stimuli.current != null:
			Stimuli.current.emit_sound(at, float(t.get("crouch_noise" if quiet else "noise", 3.0 if quiet else 18.0)), &"creak", source)
		if not quiet and is_armed():
			if poi != null:
				poi.call(&"set_trap_state", trap_id, "sprung")
			fired(at)

	## A Hollowed's weight on the boards: the groan is the player's warning that something is
	## walking about upstairs. Nothing hears it but the player; the trap stays armed.
	func creak_under_hollowed(at: Vector3) -> void:
		var h: Dictionary = tuning().get("hollowed", {})
		Audio.play_3d(&"sfx/trap_floor_creak", at, {"volume_db": float(h.get("volume_db", -5.0)), "max_distance": 45.0, "pitch": 0.9})
		if bool(h.get("fires_trigger", false)) and is_armed():
			if poi != null:
				poi.call(&"set_trap_state", trap_id, "sprung")
			fired(at)


class WeakFloor:
	extends Trap
	## Rotten, sagging boards over a room: half a second after the player, or a heavy Hollowed (a
	## Rammer, a Husk: traps.json weak_floor.hollowed), steps on them they give way into a one-way
	## drop hole (persisted: the hole is there on every later visit). A Hollowed that goes through
	## takes fall damage; the nav tiles there are rebaked so the rest stop pathing over the hole.
	var shape: CollisionShape3D
	## Kit floor batches of this cell: the rotten slab now, the broken one once it falls.
	var intact_mm: Node3D
	var broken_mm: Node3D
	var _t: float = -1.0
	var _by_player: bool = true

	func _ready() -> void:
		label = "rotten floor"

	func on_body(body: Node) -> void:
		if not is_armed() or _t >= 0.0:
			return
		var player: bool = body is Player
		if not player and not (body is Enemy and PoiPieces.hollowed_sets_off("weak_floor", body as Enemy)):
			return
		_by_player = player
		_t = float(tuning().get("delay", 0.5))
		Audio.play_3d(&"sfx/trap_floor_crack", global_position + Vector3.UP * 0.1, {"volume_db": -2.0, "max_distance": 40.0})
		FxLibrary.burst(get_parent(), "dust", global_position + Vector3.UP * 0.1, Vector3.UP, 0.5)

	func interact_text(_player: Player) -> String:
		return ""

	func _physics_process(delta: float) -> void:
		if _t < 0.0:
			return
		_t -= delta
		if _t <= 0.0:
			_t = -1.0
			collapse()

	func collapse() -> void:
		if not is_armed():
			return
		if poi != null:
			poi.call(&"set_trap_state", trap_id, "sprung")
		# The heavy ones standing on it go down with it.
		var fallers: Array[Enemy] = []
		for c: Node in get_children():
			if c is Area3D:
				for b: Node3D in (c as Area3D).get_overlapping_bodies():
					if b is Enemy and PoiPieces.hollowed_sets_off("weak_floor", b as Enemy):
						fallers.append(b as Enemy)
		show_collapsed()
		var pos: Vector3 = global_position
		var t: Dictionary = tuning()
		Audio.play_3d(&"sfx/trap_floor_collapse", pos, {"volume_db": 2.0, "max_distance": 70.0})
		FxLibrary.burst(get_parent(), "splinters", pos, Vector3.DOWN, 1.4)
		FxLibrary.burst(get_parent(), "dust", pos - Vector3.UP * 0.5, Vector3.UP, 1.2)
		var loud: float = float(t.get("noise", 30.0))
		if Stimuli.current != null:
			Stimuli.current.emit_sound(pos, loud, &"structure_break", StringName(trap_id))
		var dmg: float = float((t.get("hollowed", {}) as Dictionary).get("fall_damage", 40.0))
		for e: Enemy in fallers:
			var info := DamageInfo.make(dmg, &"blunt", &"fall", StringName(trap_id))
			info.hit_pos = e.global_position + Vector3.UP * 0.4
			info.source_pos = pos + Vector3.UP
			info.direction = Vector3.DOWN
			e.take_damage(info)
		if poi != null:
			poi.call(&"on_floor_collapsed", pos)
		went_off(pos, _by_player, float(t.get("alert_radius", 12.0)), loud, &"structure_break")

	func show_collapsed() -> void:
		if shape != null:
			shape.set_deferred(&"disabled", true)
		if intact_mm != null:
			intact_mm.visible = false
		if broken_mm != null:
			broken_mm.visible = true
		for c: Node in get_children():
			if c is Area3D:
				c.queue_free()

	func is_collapsed() -> bool:
		return trap_state() == "sprung"


class AlarmTrap:
	extends Trap
	## A battery door/window alarm (or a bell on a cord across an open passage). Opening or
	## breaking its opening, or walking through, sets it off: it rings for `seconds`, wakes every
	## sleeper in the building (when the player set it off; a Hollowed blundering through only makes
	## it ring, ADR-0022) and keeps putting out noise the horde and heat systems hear. Use it while
	## ringing to smash it quiet; crouch-interact while armed to disarm it.
	var style: String = "battery"
	var _ring_t: float = 0.0
	var _noise_t: float = 0.0
	var _player3d: Sound3D = null

	func _ready() -> void:
		label = "door alarm" if style == "battery" else "bell"

	func on_body(body: Node) -> void:
		if body is Player:
			trip(body, true)
		elif body is Enemy and PoiPieces.hollowed_sets_off("alarm", body as Enemy):
			trip(body, false)

	## Sets the alarm off (body: whoever did it, or null for an opening event). `by_player`: the
	## player's doing rouses the whole building (ADR-0018); a Hollowed's only rings (ADR-0022), and
	## the ringing wakes what hears it.
	func trip(_body: Variant, by_player: bool = true) -> void:
		if not is_armed():
			return
		if poi != null:
			poi.call(&"set_trap_state", trap_id, "sprung")
		var t: Dictionary = tuning()
		_ring_t = float(t.get("seconds", 20.0))
		_noise_t = 0.0
		var s: AudioStream = Audio.stream(&"sfx/trap_alarm_siren" if style == "battery" else &"sfx/trap_alarm_bell")
		if s != null:
			_player3d = Sound3D.new()
			_player3d.stream = s
			_player3d.bus = &"SFX"
			_player3d.volume_db = 4.0
			_player3d.unit_size = 8.0
			_player3d.max_distance = 120.0
			add_child(_player3d)
			_player3d.position = Vector3.UP * 1.9
			_player3d.play()
		if poi != null:
			poi.call(&"alarm", global_position, by_player)
		if by_player or PoiPieces.hollowed_fires("alarm"):
			fired(global_position + Vector3.UP)

	func is_ringing() -> bool:
		return _ring_t > 0.0

	func _process(delta: float) -> void:
		if _ring_t <= 0.0:
			return
		_ring_t -= delta
		_noise_t -= delta
		if _noise_t <= 0.0:
			var t: Dictionary = tuning()
			var every: float = float(t.get("noise_interval", 1.0))
			_noise_t = every
			if Stimuli.current != null:
				Stimuli.current.emit_sound(global_position + Vector3.UP, float(t.get("noise", 55.0)), &"alarm", StringName(trap_id))
			if Game.session != null:
				Game.session.heat.add(global_position, float(t.get("heat_per_second", 2.0)) * every)
		if _ring_t <= 0.0:
			_silence()

	func _silence() -> void:
		_ring_t = 0.0
		if _player3d != null and is_instance_valid(_player3d):
			_player3d.queue_free()
		_player3d = null

	func interact_text(player: Player) -> String:
		if is_ringing():
			return "Smash the %s quiet" % label
		return super.interact_text(player)

	func interact(player: Player) -> void:
		if is_ringing():
			_silence()
			Audio.play_3d(&"sfx/lock_padlock_hit", global_position + Vector3.UP * 1.9, {"volume_db": -2.0})
			return
		super.interact(player)
