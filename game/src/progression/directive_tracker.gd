class_name DirectiveTracker
extends Node
## Feeds gameplay events into the local player's Program directives and pays out what they
## complete: XP, items (dropped at your feet if the pack is full), a status line and a chime.
## Progress itself lives in PlayerState.directives (saved with the player).

var world: Node
var _announced: int = 0


func setup_world(w: Node) -> void:
	world = w
	var p: PlayerState = Game.local_player()
	_announced = p.directives.chapter if p != null else 1
	Events.tree_felled.connect(func(_id: StringName, _pos: Vector3) -> void: record("fell_tree"))
	Events.item_crafted.connect(func(_o: StringName, _r: StringName, item_id: StringName, _n: int) -> void: record("craft", item_id))
	Events.structure_placed.connect(func(_id: StringName, def_id: StringName, _pos: Vector3) -> void:
		if def_id == BuildingManager.LOG_DEF:
			record("place_log"))
	Events.blueprint_completed.connect(func(_site: StringName, def_id: StringName) -> void: record("build", def_id))
	Events.container_looted.connect(_on_looted)
	Events.enemy_killed.connect(_on_killed)
	Events.poi_entered.connect(func(id: StringName) -> void: record("enter_poi", _poi_def(id)))
	Events.poi_cleared.connect(func(id: StringName) -> void: record("clear_poi", _poi_def(id)))
	Events.horde_night_ended.connect(func(_d: int, _r: Dictionary) -> void: record("survive_hum"))
	Events.note_found.connect(func(_n: StringName) -> void: record("read_note"))
	Events.player_leveled.connect(func(_pid: StringName, level: int) -> void: record("level", &"", level))
	Events.player_slept.connect(func(_pid: StringName, _h: float) -> void: record("sleep"))
	# A loaded game may already meet a level goal in its open chapter.
	if p != null:
		record.call_deferred("level", &"", p.progression.level)


func _on_looted(player_id: StringName, container_id: StringName, _tier: int) -> void:
	if Game.session == null or player_id != Game.session.local_player_id:
		return
	record("loot")
	if String(container_id).begins_with("supply:"):
		record("supply_drop")


func _on_killed(_eid: StringName, enemy_id: StringName, _pos: Vector3, killer: Dictionary) -> void:
	if Game.session == null or StringName(str(killer.get("source", ""))) != Game.session.local_player_id:
		return
	record("kill", enemy_id, 1, StringName(str(killer.get("tier", "normal"))))


func _poi_def(instance_id: StringName) -> StringName:
	var pois: Node = world.get(&"pois") if world != null else null
	if pois == null:
		return &""
	var inst: PoiInstance = (pois.get(&"instances") as Dictionary).get(instance_id)
	return inst.layout.def.id if inst != null and inst.layout != null else &""


func record(event: String, target: StringName = &"", amount: int = 1, tier: StringName = &"") -> void:
	var p: PlayerState = Game.local_player()
	if p == null:
		return
	for d: DirectiveDef in p.directives.record(event, target, amount, tier):
		_pay(p, d)
	if p.directives.chapter > _announced:
		_announced = p.directives.chapter
		Events.player_status_message.emit("New Program directives: %s. Check your tether." % Directives.chapter_name(_announced), &"level")
		# A level goal in the new chapter may already be met.
		record("level", &"", p.progression.level)


func _pay(p: PlayerState, d: DirectiveDef) -> void:
	var got: PackedStringArray = []
	for k: Variant in d.reward_items.keys():
		var item := StringName(str(k))
		var n: int = int(d.reward_items[k])
		var left: int = p.inventory.add_item(item, n)
		if left > 0 and world != null and world.get(&"player") != null:
			ItemDrop.spawn(world, ItemStack.make(item, left), (world.player as Node3D).global_position + Vector3.UP)
		var idef: ItemDef = Content.item(item)
		got.append("%d %s" % [n, idef.display_name if idef != null else String(item)])
	if not got.is_empty():
		Events.inventory_changed.emit(p.id)
	Audio.play_2d(&"ui/learned", -5.0)
	Events.player_status_message.emit("Directive complete: %s.  +%d XP%s" % [d.display_name, d.reward_xp,
		("  ·  " + ", ".join(got)) if not got.is_empty() else ""], &"level")
	if d.reward_xp > 0:
		p.progression.add_xp(d.reward_xp)
