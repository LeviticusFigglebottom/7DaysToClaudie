extends Node
## Smoke-run logic (loaded by slice_smoke.gd once autoloads exist). End-to-end run of the M1 slice:
##   godot --headless --path game -s res://src/tools/cli/slice_smoke.gd      (make smoke)
## New game -> world ready -> fell a tree -> carry a log -> place logs (freeform) -> lay out and
## complete a campfire -> craft a stone axe -> survival ticks -> night wanderers -> a Hum night
## with waves and a memory report -> save -> load -> state restored. Exit code = failures.

var _fails: int = 0
var _t0: int = 0


func _ready() -> void:
	_t0 = Time.get_ticks_msec()
	_run.call_deferred()


func get_nodes_in_group(g: StringName) -> Array[Node]:
	return get_tree().get_nodes_in_group(g)


func ok(cond: bool, what: String) -> bool:
	if cond:
		print("[smoke] ok    %s" % what)
	else:
		_fails += 1
		printerr("[smoke] FAIL  %s" % what)
	return cond


func frames(n: int) -> void:
	for i: int in n:
		await get_tree().process_frame


func seconds(s: float) -> void:
	var end: int = Time.get_ticks_msec() + int(s * 1000.0)
	while Time.get_ticks_msec() < end:
		await get_tree().process_frame


func wait_until(cond: Callable, timeout_s: float) -> bool:
	var end: int = Time.get_ticks_msec() + int(timeout_s * 1000.0)
	while Time.get_ticks_msec() < end:
		if cond.call():
			return true
		await get_tree().process_frame
	return false


func _game() -> Node:
	return get_node("/root/Game")


func _run() -> void:
	var game: Node = _game()
	game.call(&"start_new_game", {"game_mode": "slice", "skip_intro": true, "slot": "smoke"})
	var ready: bool = await wait_until(func() -> bool: return game.get(&"world") != null and bool(game.world.is_ready), 240.0)
	if not ok(ready, "world loads and the player spawns (%.1fs)" % ((Time.get_ticks_msec() - _t0) / 1000.0)):
		_finish()
		return
	var w: GameWorld = game.world
	var p: Player = w.player
	var ps: PlayerState = p.state
	ok(is_finite(w.height_at(p.global_position.x, p.global_position.z)), "terrain under the player")
	ok(ps.inventory.has(&"lighter"), "start kit given")
	await seconds(2.0)

	# --- Trees: fell one, logs appear ---------------------------------------------------------
	var veg: VegetationManager = w.vegetation
	ok(veg != null, "vegetation module")
	var found: Array = []
	if veg != null:
		await wait_until(func() -> bool: return not veg.nearest_instance(p.global_position, "tree", 150.0).is_empty(), 30.0)
		found = veg.nearest_instance(p.global_position, "tree", 150.0)
	if ok(not found.is_empty(), "a tree near the drop site"):
		var inst: VegetationScatter.Instance = found[1]
		p.global_position = inst.pos + Vector3(2.5, 1.0, 0.0)
		w.terrain.update_streaming(p.global_position, true)
		await wait_until(func() -> bool: return veg.body_for(found[0], inst) != null, 20.0)
		var body: Node = veg.body_for(found[0], inst)
		if ok(body != null, "tree has pooled collision near the player"):
			for i: int in 40:
				if not is_instance_valid(body) or body.is_queued_for_deletion():
					break
				var info := DamageInfo.make(20.0, &"slash", &"melee", ps.id)
				info.tool_power = {"chop": 30.0, "wood": 30.0}
				info.hit_pos = inst.pos + Vector3.UP
				info.direction = Vector3(-1, 0, 0.2).normalized()
				info.collider = body
				veg.take_damage(info)
				await frames(2)
			ok(int(game.session.stats.get("trees_felled", 0)) >= 1, "tree felled")
			await wait_until(func() -> bool: return not get_nodes_in_group(&"logs").is_empty(), 12.0)
			ok(not get_nodes_in_group(&"logs").is_empty(), "felled tree broke into logs")

	# --- Carry a log, place logs freeform -------------------------------------------------------
	var logs: Array = get_nodes_in_group(&"logs")
	if not logs.is_empty():
		(logs[0] as LogEntity).interact(p)
		ok(ps.inventory.count_of(&"log") == 1, "picked up a log onto the shoulder")
	ps.inventory.add_item(&"log", 2 - ps.inventory.count_of(&"log"))
	var b: BuildingManager = w.building
	var base: Vector3 = p.global_position + Vector3(4, 0, 4)
	base.y = w.height_at(base.x, base.z) + LogSnapper.RADIUS
	var r1: Dictionary = game.execute(&"build.place_log", {"pos": [base.x, base.y, base.z], "rot": [0, 0, 0, 1]})
	ok(bool(r1.get("ok", false)), "freeform log placed on the ground (%s)" % r1.get("error", ""))
	var snap: Dictionary = LogSnapper.best_snap(Transform3D(Basis(), base + Vector3(0.2, 0.3, 0.0)), [Transform3D(Basis(), base)] as Array[Transform3D])
	var sx: Transform3D = snap["xform"]
	var r2: Dictionary = game.execute(&"build.place_log", {"pos": [sx.origin.x, sx.origin.y, sx.origin.z], "rot": [0, 0, 0, 1]})
	ok(bool(r2.get("ok", false)), "second log snapped onto the first (%s)" % r2.get("error", ""))
	ok(b.pieces.size() == 2 and b.graph.stability(StringName(str(r2.get("piece", "")))) > 0.9, "stacked log is supported")

	# --- Blueprint: campfire --------------------------------------------------------------------
	ps.inventory.add_item(&"stone", 6)
	ps.inventory.add_item(&"stick", 4)
	var cpos: Vector3 = p.global_position + Vector3(-3, 0, 2)
	cpos.y = w.height_at(cpos.x, cpos.z)
	var r3: Dictionary = game.execute(&"build.place_blueprint", {"blueprint": "campfire", "pos": [cpos.x, cpos.y, cpos.z], "yaw": 0.0})
	if ok(bool(r3.get("ok", false)), "campfire blueprint laid out (%s)" % r3.get("error", "")):
		var r4: Dictionary = game.execute(&"build.deliver", {"site": r3["site"]})
		ok(bool(r4.get("complete", false)), "materials delivered, campfire built")
		var stations: PackedStringArray = b.stations_near(cpos, 3.0)
		ok(stations.is_empty(), "unlit campfire is not yet a station")
		for piece: StructurePiece in b.pieces_in_radius(cpos, 2.0):
			if piece.provides("light"):
				piece.set_lit(true)
		ok(b.stations_near(cpos, 3.0).has("campfire"), "lit campfire works as a station")
		ok(b.warmth_at(cpos + Vector3(1, 0, 0)) > 0.0, "fire gives warmth")

	# --- Crafting ---------------------------------------------------------------------------------
	ps.inventory.add_item(&"plant_fiber", 3)
	ps.inventory.add_item(&"stick", 1)
	ps.inventory.add_item(&"stone", 1)
	ok(bool(game.execute(&"inventory.craft", {"recipe": "cordage"}).get("ok", false)), "crafted cordage")
	ok(bool(game.execute(&"inventory.craft", {"recipe": "stone_axe"}).get("ok", false)), "crafted a stone axe")

	# --- Survival over time -------------------------------------------------------------------------
	var full0: float = ps.stats.fullness
	w.clock_driver.advance(120.0)
	await frames(2)
	ok(ps.stats.fullness < full0, "needs drain with game time")

	# --- Night: wanderers -------------------------------------------------------------------------
	game.session.clock.set_time(1, 21.5)
	w.clock_driver.advance(60.0)
	var ai: AIDirector = w.ai
	await wait_until(func() -> bool: return ai.alive_count() > 0, 20.0)
	ok(ai.alive_count() > 0, "Hollowed wander at night (%d)" % ai.alive_count())

	# --- The Hum ----------------------------------------------------------------------------------
	var hum_day: int = game.session.clock.next_horde_day(1)
	game.session.clock.set_time(hum_day, 21.8)
	w.clock_driver.advance(20.0)
	await frames(5)
	ok(ai.hum.active, "the Hum starts on day %d" % hum_day)
	w.clock_driver.advance(30.0)
	await wait_until(func() -> bool: return ai.hum.members.size() > 0, 20.0)
	ok(ai.hum.members.size() > 0, "Hum waves spawn (%d)" % ai.hum.members.size())
	await seconds(4.0)
	ok(ai.hum.flow != null and ai.hum.flow.ready, "horde flow field built")
	# Kill a few attackers to give the memory something to learn from.
	var killed: int = 0
	for id: StringName in ai.hum.members.keys():
		var e: Enemy = ai.hum.members[id]["node"]
		if is_instance_valid(e) and e.is_alive() and killed < 3:
			var info2 := DamageInfo.make(999.0, &"blunt", &"melee", ps.id)
			info2.hit_pos = e.global_position + Vector3.UP
			e.take_damage(info2)
			killed += 1
	game.session.clock.set_time(hum_day + 1, 3.9)
	w.clock_driver.advance(12.0)
	await frames(5)
	ok(not ai.hum.active and game.session.horde.horde_index == 1, "the Hum ends and files its report")
	var killed_total: int = 0
	for v: Variant in (game.session.horde.nights.back() as Dictionary).get("killed", []) if not game.session.horde.nights.is_empty() else []:
		killed_total += int(v)
	ok(killed_total >= killed, "report counts the kills (%d)" % killed_total)

	# --- Save / load --------------------------------------------------------------------------------
	var pieces_before: int = b.pieces.size()
	var day_before: int = game.session.clock.day()
	var old_id: int = w.get_instance_id()
	ok(bool(game.call(&"save_game", "smoke")), "saved")
	ok(bool(game.call(&"load_game", "smoke")), "load started")
	await frames(3)
	var ready2: bool = await wait_until(func() -> bool: return game.get(&"world") != null and is_instance_valid(game.world) and game.world.get_instance_id() != old_id and bool(game.world.is_ready), 240.0)
	if ok(ready2, "reloaded world ready"):
		var w2: GameWorld = game.world
		ok((w2.building as BuildingManager).pieces.size() == pieces_before, "structures restored (%d)" % pieces_before)
		ok(game.session.clock.day() == day_before, "clock restored")
		ok(game.session.horde.horde_index == 1, "horde memory restored")
		ok(w2.player.state.inventory.has(&"stone_axe"), "inventory restored")
	_finish()


func _finish() -> void:
	print("[smoke] %s — %d failure(s), %.1fs" % ["PASS" if _fails == 0 else "FAIL", _fails, (Time.get_ticks_msec() - _t0) / 1000.0])
	get_tree().quit(1 if _fails > 0 else 0)
