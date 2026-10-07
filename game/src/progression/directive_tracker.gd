class_name DirectiveTracker
extends Node
## Feeds gameplay events into the local player's Program directives and pays out what they
## complete: XP, items (dropped at your feet if the pack is full), a status line and a chime.
## Progress itself lives in PlayerState.directives (saved with the player). Directives aimed at
## particular buildings are fitted to the world on load (fit_world).

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
	Events.horde_night_ended.connect(_on_hum_ended)
	Events.note_found.connect(func(_n: StringName) -> void: record("read_note"))
	Events.player_leveled.connect(func(_pid: StringName, level: int) -> void: record("level", &"", level))
	Events.player_slept.connect(func(_pid: StringName, _h: float) -> void: record("sleep"))
	# Only traps taken apart while armed count: salvaging a sprung one is no feat.
	Events.trap_disarmed.connect(func(pid: StringName, _poi: StringName, trap_type: StringName, was_armed: bool) -> void:
		if was_armed and Game.session != null and pid == Game.session.local_player_id:
			record("disarm_trap", trap_type))
	# A Waystation contract turned in (ADR-0039).
	Events.contract_completed.connect(func(pid: StringName, _cid: String, def_id: StringName, _tier: int) -> void:
		if Game.session != null and pid == Game.session.local_player_id:
			record("contract", def_id))
	# An Ashen raid turned back (ADR-0048).
	Events.ashen_raid_ended.connect(func(_rid: String, repelled: bool) -> void:
		if repelled:
			record("raid"))
	# A garden plot brought in (ADR-0049).
	Events.crop_harvested.connect(func(pid: StringName, crop_id: StringName, _items: Dictionary) -> void:
		if Game.session != null and pid == Game.session.local_player_id:
			record("harvest", crop_id))
	# A Hollow put down by a player-built trap or sentry (ADR-0052).
	Events.trap_killed.connect(func(_piece: StringName, structure_id: StringName, _enemy: StringName) -> void:
		record("trap_kill", structure_id))
	if p != null:
		fit_world(p)
		# A loaded game may already meet a level goal in its open chapter.
		record.call_deferred("level", &"", p.progression.level)


## Fits the directives aimed at particular buildings to this world (Directives.for_world): a random
## world without the ranger station or the sawmill gets the nearest building like them instead,
## or the directive is spent. A chapter that opens this way is announced by the deferred record.
func fit_world(p: PlayerState) -> void:
	var pois: Node = world.get(&"pois") if world != null else null
	if pois == null or not pois.has_method(&"all_buildings") or Game.session == null:
		return
	var fit: Dictionary = Directives.for_world(pois.call(&"all_buildings"), drop_site(), Game.session.world_seed)
	# A world without a trader post (a random world whose generator places none) can't pay a
	# contract: those directives are spent (ADR-0039).
	if not _has_trader():
		for d: DirectiveDef in Content.all(&"directive"):
			if d.event == "contract":
				(fit["spent"] as Dictionary)[d.id] = true
	# A world without the Ashen (the setting is off) never raids: those directives are spent.
	if not GameRules.current().flag("ashen"):
		for d2: DirectiveDef in Content.all(&"directive"):
			if d2.event == "raid":
				(fit["spent"] as Dictionary)[d2.id] = true
	for id: Variant in fit["stand_ins"]:
		Log.info("directives", "%s: this world stands in %s" % [id, (fit["stand_ins"][id] as Dictionary)["targets"]])
	for id2: Variant in fit["spent"]:
		Log.info("directives", "%s: spent (no such building in this world)" % id2)
	p.directives.set_world(fit)


## Whether any region places a trader post (a `trader:` spawn feature, TraderManager).
func _has_trader() -> bool:
	var terrain: Node = world.get(&"terrain") if world != null else null
	if terrain == null:
		return false
	# The coarse regions too: a streamed world (ADR-0038) has only the regions near the player at
	# 1 m, and the others' coarse compositions carry the same spawns.
	var all: Array = (terrain.get(&"regions") as Dictionary).values()
	if terrain.get(&"coarse") is Dictionary:
		all.append_array((terrain.get(&"coarse") as Dictionary).values())
	for rt: Variant in all:
		for sid: Variant in ((rt as RegionTerrain).spawns as Dictionary).keys():
			if str(sid).begins_with("trader:"):
				return true
	return false


## The drop site: the "drop_site" spawn of the world's regions (where a new game starts).
func drop_site() -> Vector3:
	# GameWorld's own lookup reads the coarse regions too (a streamed world, ADR-0038).
	if world != null and world.has_method(&"drop_site"):
		return world.call(&"drop_site")
	var terrain: Node = world.get(&"terrain") if world != null else null
	var regions: Dictionary = terrain.get(&"regions") if terrain != null and terrain.get(&"regions") is Dictionary else {}
	for rid: Variant in regions:
		var rt: RegionTerrain = regions[rid] as RegionTerrain
		if rt != null and rt.spawns.has("drop_site"):
			var a: Array = (rt.spawns["drop_site"] as Dictionary).get("pos", [0, 0, 0])
			return Vector3(float(a[0]), float(a[1]), float(a[2]))
	return Vector3.ZERO


## Dawn after a Hum: it counts only for a player still alive, like the Hum's XP (HumDirector).
func _on_hum_ended(_day: int, _report: Dictionary) -> void:
	var p: PlayerState = Game.local_player()
	if p != null and p.stats.alive:
		record("survive_hum")


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
	Events.player_status_message.emit("Directive complete: %s.  +%d XP%s" % [p.directives.label(d), d.reward_xp,
		("  ·  " + ", ".join(got)) if not got.is_empty() else ""], &"level")
	if d.reward_xp > 0:
		p.progression.add_xp(d.reward_xp)
