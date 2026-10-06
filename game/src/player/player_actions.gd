class_name PlayerActions
extends Node
## Authoritative handlers for player inventory/world commands (ADR-0003). Registered on the
## Game command bus while the world is alive. Every handler validates against session state and
## returns {"ok": bool, ...}; UI only ever calls Game.execute().

var world: Node


func _ready() -> void:
	var cmds: Dictionary = {
		&"inventory.consume": _consume, &"inventory.drop": _drop, &"inventory.equip": _equip,
		&"inventory.craft": _craft, &"inventory.read": _read, &"world.pickup_stack": _pickup_stack,
		&"world.pickup_item": _pickup_item, &"container.take": _container_take,
		&"container.take_all": _container_take_all, &"container.put": _container_put,
		&"progression.raise_attribute": _raise_attribute, &"progression.buy_perk": _buy_perk,
		&"world.drink_water": _drink_water, &"world.fill_water": _fill_water, &"inventory.repair": _repair,
	}
	for c: StringName in cmds:
		Game.register_command(c, cmds[c])


func _exit_tree() -> void:
	for c: StringName in [&"inventory.consume", &"inventory.drop", &"inventory.equip", &"inventory.craft", &"inventory.read",
			&"world.pickup_stack", &"world.pickup_item", &"container.take", &"container.take_all", &"container.put",
			&"progression.raise_attribute", &"progression.buy_perk", &"world.drink_water", &"world.fill_water", &"inventory.repair"]:
		Game.unregister_command(c)


func _player(args: Dictionary) -> PlayerState:
	return Game.session.players.get(StringName(str(args.get("player", Game.session.local_player_id)))) if Game.session != null else null


static func _fail(why: String) -> Dictionary:
	return {"ok": false, "error": why}


func _consume(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player(args)
	var item_id := StringName(str(args.get("item", "")))
	var def: ItemDef = Content.item(item_id)
	if p == null or def == null or not def.is_consumable():
		return _fail("not consumable")
	if not p.inventory.has(item_id):
		return _fail("not carried")
	var fx: Dictionary = def.consume.duplicate()
	if def.category == "medical":
		var m: float = 1.0 + p.progression.modifier("heal_mult")
		if fx.has("health") and float(fx["health"]) > 0.0:
			fx["health"] = float(fx["health"]) * m
	if float(fx.get("health", 0.0)) < 0.0:
		fx["health"] = float(fx["health"]) * (1.0 - clampf(p.progression.modifier("food_poison_resist"), 0.0, 0.9))
	var tmp := ItemDef.new()
	tmp.consume = fx
	p.inventory.remove(item_id, 1)
	p.stats.consume(tmp)
	var ret: String = str(def.consume.get("returns", ""))
	if ret != "":
		var left: int = p.inventory.add_item(StringName(ret), 1)
		if left > 0:
			_drop_near(p, ItemStack.make(StringName(ret), left))
	var snd: StringName = &"sfx/drink_gulp" if def.category == "drink" else (&"sfx/bandage_wrap" if def.category == "medical" else (&"sfx/eat_can" if ret == "empty_can" else &"sfx/eat_crunch"))
	Audio.play_2d(snd, -4.0, &"SFX")
	Events.inventory_changed.emit(p.id)
	return {"ok": true, "effects": fx}


## The exact stack a UI action points at: args.index into the player's stacks (checked against
## args.item when both are given), or null when no index was passed.
static func _indexed_stack(p: PlayerState, args: Dictionary) -> ItemStack:
	if not args.has("index"):
		return null
	var idx: int = int(args["index"])
	if idx < 0 or idx >= p.inventory.stacks.size():
		return null
	var s: ItemStack = p.inventory.stacks[idx]
	if args.has("item") and s.item_id != StringName(str(args["item"])):
		return null
	return s


## Drops items: {player?, item, count, index?}. With an index the dropped items come from that
## very stack (its quality and wear), otherwise the lowest-quality ones go first.
## Spends a repair kit ({player?, item: kit id}) on the held tool or weapon when it is worn,
## else on the most worn one carried. Restores it to its quality's full durability.
func _repair(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player(args)
	if p == null:
		return _fail("no player")
	var kit := StringName(str(args.get("item", "repair_kit")))
	var kd: ItemDef = Content.item(kit)
	if kd == null or not kd.has_tag("repair") or not p.inventory.has(kit):
		return _fail("no repair kit")
	var target: ItemStack = p.inventory.first(p.equipped_item()) if p.equipped_item() != &"" else null
	if target == null or not target.is_damaged():
		target = null
		var worst: float = 1.0
		for s: ItemStack in p.inventory.stacks:
			if not s.is_damaged():
				continue
			var share: float = s.durability / maxf(1.0, s.def().durability * ItemStack.quality_durability_mult(s.quality))
			if share < worst:
				worst = share
				target = s
	if target == null:
		Events.player_status_message.emit("Nothing you carry needs repairing.", &"info")
		return _fail("nothing worn")
	target.durability = target.def().durability * ItemStack.quality_durability_mult(target.quality)
	p.inventory.remove(kit, 1)
	Audio.play_2d(&"sfx/hammer_nail", -6.0, &"SFX")
	Events.player_status_message.emit("%s repaired." % target.def().display_name, &"info")
	Events.inventory_changed.emit(p.id)
	return {"ok": true, "item": String(target.item_id)}


## {player?, pos: [x, y, z]} -> the water surface the player reaches there, or Vector3.INF.
func _reachable_water(p: PlayerState, args: Dictionary) -> Vector3:
	var water: Node = world.get(&"water") if world != null else null
	var a: Array = args.get("pos", [])
	if water == null or a.size() != 3:
		return Vector3.INF
	var at := Vector3(float(a[0]), float(a[1]), float(a[2]))
	var level: float = water.call(&"water_level_at", at.x, at.z)
	if level == -INF:
		return Vector3.INF
	var node: Node3D = world.player_node(p.id) if world.has_method(&"player_node") else null
	var from: Vector3 = node.global_position if node != null else p.position
	at.y = level
	return at if from.distance_to(at) <= 4.0 else Vector3.INF


func _drink_water(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player(args)
	if p == null or not p.stats.alive:
		return _fail("no player")
	if _reachable_water(p, args) == Vector3.INF:
		return _fail("no water in reach")
	if p.stats.hydration >= 99.0:
		Events.player_status_message.emit("You're not thirsty.", &"info")
		return _fail("not thirsty")
	# Thirst per mouthful, and a little sickness unless the gut is used to it (survival.json).
	var sw: Dictionary = Content.config(&"survival").get("stream_water", {"hydration": 18.0, "health": -3.0})
	var tmp := ItemDef.new()
	tmp.consume = sw.duplicate()
	tmp.consume["health"] = float(sw.get("health", 0.0)) * (1.0 - clampf(p.progression.modifier("food_poison_resist"), 0.0, 0.9))
	p.stats.consume(tmp)
	Audio.play_2d(&"sfx/drink_gulp", -4.0, &"SFX")
	return {"ok": true, "effects": tmp.consume}


## Fills every carried empty bottle that still fits in the pack (full ones weigh more).
func _fill_water(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player(args)
	if p == null or not p.stats.alive:
		return _fail("no player")
	var at: Vector3 = _reachable_water(p, args)
	if at == Vector3.INF:
		return _fail("no water in reach")
	var filled: int = 0
	# Bottles, and a bucket for the garden (ADR-0049).
	for pair: Array in [[&"water_bottle_empty", &"water_bottle_dirty"], [&"bucket", &"bucket_water"]]:
		while p.inventory.has(pair[0]):
			p.inventory.remove(pair[0], 1)
			if p.inventory.add_item(pair[1], 1) > 0:
				p.inventory.add_item(pair[0], 1)
				break
			filled += 1
	if filled == 0:
		Events.player_status_message.emit("No room to carry full bottles.", &"warning")
		return _fail("no room")
	Audio.play_3d(&"sfx/footstep_water", at, {"volume_db": -2.0})
	Events.player_status_message.emit("Filled %d bottle%s. Boil it before you drink it." % [filled, "" if filled == 1 else "s"], &"info")
	Events.inventory_changed.emit(p.id)
	return {"ok": true, "filled": filled}


func _drop(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player(args)
	if p == null:
		return _fail("no player")
	var item_id := StringName(str(args.get("item", "")))
	var n: int = int(args.get("count", 1))
	var src: ItemStack = _indexed_stack(p, args)
	if args.has("index"):
		if src == null or src.count < n:
			return _fail("not carried")
		item_id = src.item_id
	if n <= 0 or not p.inventory.has(item_id, n):
		return _fail("not carried")
	var def: ItemDef = Content.item(item_id)
	if def != null and def.has_tag("no_drop"):
		return _fail("cannot drop")
	var out: Array[ItemStack] = []
	if src != null:
		out.append(p.inventory.take_from(src, n))
	else:
		out = p.inventory.take(item_id, n)
	if item_id == &"log" and world != null and world.get("building") != null:
		# Every carried log becomes its own loose log, stacked so they don't spawn inside each other.
		for i: int in n:
			world.building.drop_log(p, i)
	else:
		for st: ItemStack in out:
			_drop_near(p, st)
	Events.inventory_changed.emit(p.id)
	return {"ok": true}


func _drop_near(p: PlayerState, stack: ItemStack) -> void:
	var node: Node3D = world.player if world != null else null
	var pos: Vector3 = p.position + Vector3.UP
	if node != null:
		pos = node.global_position + Vector3.UP * 1.2 - node.global_transform.basis.z * 0.8
	ItemDrop.spawn(world, stack, pos)


func _equip(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player(args)
	var item_id := StringName(str(args.get("item", "")))
	var slot: int = int(args.get("slot", -1))
	if p == null:
		return _fail("no player")
	if slot < 0:
		slot = p.toolbelt.find(&"")
		if slot < 0:
			slot = maxi(p.equipped_slot, 0)
	for i: int in p.toolbelt.size():
		if p.toolbelt[i] == item_id:
			p.toolbelt[i] = &""
	p.toolbelt[slot] = item_id
	p.equipped_slot = slot
	Events.inventory_changed.emit(p.id)
	return {"ok": true, "slot": slot}


func _craft(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player(args)
	var r: RecipeDef = Content.recipe(StringName(str(args.get("recipe", ""))))
	var station := StringName(str(args.get("station", "")))
	if p == null or r == null:
		return _fail("unknown recipe")
	if not p.progression.knows_recipe(r):
		return _fail("recipe not known")
	var skill: int = int(p.progression.modifier("craft_quality"))
	var res: Crafting.Result = Crafting.craft(r, p.inventory, station, Crafting.quality_for(r, skill))
	if not res.ok:
		return _fail(res.reason)
	# What it teaches depends on what it was: craft_<category> when the XP table lists it.
	var src: String = "craft_%s" % r.category
	p.progression.award(src if p.progression.has_xp_source(src) else "craft")
	Audio.play_2d(&"ui/craft_success", -4.0)
	Events.item_crafted.emit(p.id, r.id, r.result, r.result_count)
	Events.inventory_changed.emit(p.id)
	return {"ok": true, "item": String(r.result), "count": r.result_count, "quality": res.stack.quality if res.stack != null else 0}


func _read(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player(args)
	var item_id := StringName(str(args.get("item", "")))
	var def: ItemDef = Content.item(item_id)
	if p == null or def == null or not p.inventory.has(item_id):
		return _fail("not carried")
	if def.category == "note":
		if not p.read_notes.has(def.note):
			p.read_notes[def.note] = true
			p.progression.award("read_note")
			Events.note_found.emit(def.note)
		return {"ok": true, "note": String(def.note)}
	var learned: Dictionary = p.progression.learn_from_item(def)
	if learned.is_empty():
		return _fail("nothing new to learn")
	p.inventory.remove(item_id, 1)
	Audio.play_2d(&"ui/learned", -3.0)
	Events.schematic_learned.emit(StringName(str(learned.get("id", ""))))
	Events.inventory_changed.emit(p.id)
	return {"ok": true, "learned": learned}


## Spends points on an attribute level: {player?, attribute} -> {ok, level, points}.
func _raise_attribute(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player(args)
	if p == null:
		return _fail("no player")
	var id := StringName(str(args.get("attribute", "")))
	var why: String = p.progression.attribute_block_reason(id)
	if why != "":
		return _fail(why)
	p.progression.raise_attribute(id)
	_progressed(p)
	return {"ok": true, "level": p.progression.attr_level(id), "points": p.progression.skill_points}


## Learns a perk's next rank: {player?, perk} -> {ok, rank, points}.
func _buy_perk(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player(args)
	if p == null:
		return _fail("no player")
	var id := StringName(str(args.get("perk", "")))
	var why: String = p.progression.perk_block_reason(id)
	if why != "":
		return _fail(why)
	p.progression.buy_perk(id)
	_progressed(p)
	return {"ok": true, "rank": p.progression.perk_rank(id), "points": p.progression.skill_points}


func _progressed(p: PlayerState) -> void:
	Audio.play_2d(&"ui/learned", -6.0)
	Events.player_progressed.emit(p.id)
	# Carry capacity may have grown.
	Events.inventory_changed.emit(p.id)


func _pickup_stack(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player(args)
	var stack: ItemStack = args.get("stack")
	if p == null or stack == null:
		return _fail("nothing")
	var left: int = p.inventory.add(stack)
	var took: int = stack.count - left
	if took > 0:
		Audio.play_2d(&"sfx/pickup_generic", -8.0, &"SFX")
		Events.item_picked_up.emit(p.id, stack.item_id, took)
		Events.inventory_changed.emit(p.id)
	elif left > 0:
		Events.player_status_message.emit("Can't carry more %s." % stack.def().display_name, &"warning")
	return {"ok": took > 0, "left": left, "took": took}


func _pickup_item(args: Dictionary) -> Dictionary:
	return _pickup_stack({"player": args.get("player"), "stack": ItemStack.make(StringName(str(args.get("item", ""))), int(args.get("count", 1)))})


## Containers expose `inventory` (Inventory) and `container_id`.
func _container_take(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player(args)
	var c: Object = args.get("container")
	var idx: int = int(args.get("index", -1))
	if p == null or c == null or not is_instance_valid(c):
		return _fail("no container")
	var inv: Inventory = c.get(&"inventory")
	if idx < 0 or idx >= inv.stacks.size():
		return _fail("bad slot")
	var s: ItemStack = inv.stacks[idx]
	var left: int = p.inventory.add(s)
	var took: int = s.count - left
	if took > 0:
		inv.take_from(s, took)
		Events.item_picked_up.emit(p.id, s.item_id, took)
		Events.inventory_changed.emit(p.id)
		if c.has_method(&"on_contents_changed"):
			c.call(&"on_contents_changed")
	return {"ok": took > 0, "took": took}


func _container_take_all(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player(args)
	var c: Object = args.get("container")
	if p == null or c == null or not is_instance_valid(c):
		return _fail("no container")
	var inv: Inventory = c.get(&"inventory")
	var moved: int = inv.transfer_all_to(p.inventory)
	if moved > 0:
		Events.inventory_changed.emit(p.id)
		if c.has_method(&"on_contents_changed"):
			c.call(&"on_contents_changed")
	return {"ok": moved > 0, "moved": moved}


## Stashes items: {player?, container, item, count, index?}; the index picks the exact stack.
func _container_put(args: Dictionary) -> Dictionary:
	var p: PlayerState = _player(args)
	var c: Object = args.get("container")
	if p == null or c == null or not is_instance_valid(c):
		return _fail("no container")
	var item_id := StringName(str(args.get("item", "")))
	var n: int = int(args.get("count", 1))
	var src: ItemStack = _indexed_stack(p, args)
	if args.has("index"):
		if src == null or src.count < n:
			return _fail("not carried")
		item_id = src.item_id
	if n <= 0 or not p.inventory.has(item_id, n):
		return _fail("not carried")
	var inv: Inventory = c.get(&"inventory")
	var left: int = 0
	if src != null:
		var piece: ItemStack = src.duplicate_stack()
		piece.count = n
		left = inv.add(piece)
		p.inventory.take_from(src, n - left)
	else:
		# Whatever does not fit goes back to the player, quality and wear intact.
		for st: ItemStack in p.inventory.take(item_id, n):
			var rest: int = inv.add(st)
			if rest > 0:
				st.count = rest
				p.inventory.add(st)
				left += rest
	Events.inventory_changed.emit(p.id)
	if c.has_method(&"on_contents_changed"):
		c.call(&"on_contents_changed")
	return {"ok": left < n, "left": left}
