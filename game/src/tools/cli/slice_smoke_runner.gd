extends Node
## Smoke-run logic (loaded by slice_smoke.gd once autoloads exist). End-to-end run of the M1 slice:
##   godot --headless --path game -s res://src/tools/cli/slice_smoke.gd      (make smoke)
## New game -> world ready -> fell a tree -> carry a log -> place logs (freeform) -> lay out and
## complete a campfire -> craft a stone axe -> survival ticks -> night wanderers -> a Hum night
## with waves and a memory report -> save -> load -> state restored. Exit code = failures. Ezra is
## recruited at his camp and gathers wood, fetches a log and hands it over on the way (TD-308).
## `-- --world random --world-seed N --world-set size=3` runs it on a generated world (ADR-0031).

var _fails: int = 0
var _ezra_recruited: bool = false
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
	var opts: Dictionary = {"game_mode": "slice", "skip_intro": true, "slot": "smoke"}
	# The same run on a random world (ADR-0031): -- --world random [--world-seed N] [--world-set k=v].
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if args.find("--world") >= 0 and args.find("--world") + 1 < args.size() and args[args.find("--world") + 1] == "random":
		opts["world_gen"] = (load("res://src/app/main.gd") as GDScript).call(&"world_gen_from_args", args, 1)
		opts["slot"] = "smoke_rwg"
		# Random worlds stream by default (ADR-0038); --no-stream loads every region and building.
		opts["stream"] = not args.has("--no-stream")
	game.call(&"start_new_game", opts)
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

	# --- The player can move and the arms stay on the camera (player report 3: a random world past
	# Jolt's body limit left the player's body out of the physics space, unable to move) ---------
	ok(p.camera.current, "the player camera is current")
	ok(p.get_node_or_null("Head/Camera3D/ViewModel") != null, "the viewmodel hangs off the player camera")
	var walk_from: Vector3 = p.global_position
	var walk_t: int = 0
	Input.action_press(&"move_forward")
	while walk_t < 120:
		await get_tree().physics_frame
		walk_t += 1
	Input.action_release(&"move_forward")
	var walked: float = Vector2(p.global_position.x - walk_from.x, p.global_position.z - walk_from.z).length()
	ok(walked > 2.0, "the player walks after spawning (%.1f m in 2 s of physics)" % walked)
	await seconds(0.5)

	# --- What ships: real models, not stand-ins (-- --expect-assets; the Build workflow's pack run) --
	if args.has("--expect-assets"):
		await _check_real_models(w, p)

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
	# Back in the drop site's clearing, where a player lays the first fire (journal card 4), not by
	# the tree just felled: that one stands at the forest's edge, and whether the spot beside it was clear
	# depended on where the generator put the drop (random seed 7 moved 330 m with generator 17 and
	# its neighbour stood in the way). test_drop_clearing keeps the clearing clear on every world.
	p.global_position = walk_from + Vector3.UP * 0.5
	await frames(3)
	var cpos: Vector3 = walk_from + Vector3(-3, 0, 2)
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
	ok(ps.directives.done.has(&"arrival_axe") and ps.directives.done.has(&"arrival_fire") and ps.directives.count_of(&"arrival_fell") >= 1,
		"directives track play (axe, campfire, felling)")

	# --- Ezra (TD-308): recruited at his camp, he gathers from a real region's trees and bushes,
	# fetches a log the player points him at and hands over what he carries -----------------------
	await _companion(game, w, p)

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
	# The field builds on a low-priority worker that shares the pool with terrain streaming; on a
	# freshly streamed random world the first build can take longer than 4 s (one flaky FAIL).
	await wait_until(func() -> bool: return ai.hum.flow != null and ai.hum.flow.ready, 16.0)
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

	# --- Progression and rewards ------------------------------------------------------------------
	ok(ps.progression.level >= 2, "play earns levels (level %d, %d xp)" % [ps.progression.level, ps.progression.xp])
	var drops: SupplyDrops = w.supply_drops as SupplyDrops
	ok(drops != null and drops.drops.size() == 1, "a supply drop follows the Hum")
	if drops != null:
		for d: SupplyDrops.Drop in drops.drops.values():
			d._process(60.0)
			ok(d.landed and d.global_position.distance_to(ps.position) > 50.0, "the canister lands away from the player (%.0f m)" % d.global_position.distance_to(w.player.global_position))
			# W4 (first-week audit): walked up to and looked at, the canister offers its search.
			var back: Vector3 = w.player.global_position
			var at: Vector3 = d.crate.global_position + Vector3.UP * 0.5
			var stand: Vector3 = at + Vector3(1.0, 0.0, 0.3).normalized() * 1.8
			stand.y = w.height_at(stand.x, stand.z)
			w.player.global_position = stand + Vector3.UP * 0.05
			w.player.velocity = Vector3.ZERO
			w.terrain.update_streaming(w.player.global_position, true)
			for k: int in 2:
				var eye: Vector3 = w.player.global_position + Vector3.UP * 1.65
				var to: Vector3 = at - eye
				w.player.rotation.y = atan2(-to.x, -to.z)
				w.player.head.rotation.x = atan2(to.y, Vector2(to.x, to.z).length())
				await frames(6)
			var hit: Dictionary = w.player.interaction.last_hit
			ok(str(w.player.interaction.prompt).begins_with("Search"), "the landed canister offers its search ('%s'; the ray hit %s)" % [w.player.interaction.prompt,
				str((hit["collider"] as Node).get_path()) if not hit.is_empty() and hit["collider"] is Node else "nothing"])
			w.player.global_position = back
	ps.progression.skill_points += 2
	var bulk0: float = ps.inventory.max_bulk
	var rs: Dictionary = game.call(&"execute", &"progression.raise_attribute", {"attribute": "sinew"})
	ok(bool(rs.get("ok", false)) and ps.inventory.max_bulk > bulk0, "trained Sinew (pack %.0f -> %.0f)" % [bulk0, ps.inventory.max_bulk])
	var rp: Dictionary = game.call(&"execute", &"progression.buy_perk", {"perk": "packhorse"})
	ok(bool(rp.get("ok", false)), "learned Packhorse")
	var bulk_after: float = ps.inventory.max_bulk

	# --- Save / load --------------------------------------------------------------------------------
	var pieces_before: int = b.pieces.size()
	var day_before: int = game.session.clock.day()
	var old_id: int = w.get_instance_id()
	# Where and which way the player stands: Continue must put them back there (player report 3).
	var at_save: Vector3 = w.player.global_position
	var yaw_save: float = w.player.rotation.y
	var deaths_save: int = ps.deaths
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
		var ps2: PlayerState = w2.player.state
		ok(ps2.progression.perk_rank(&"packhorse") == 1 and is_equal_approx(ps2.inventory.max_bulk, bulk_after), "progression and carry capacity restored")
		ok(w2.supply_drops != null and (w2.supply_drops as SupplyDrops).drops.size() == 1, "supply drop restored")
		await seconds(1.0)
		var at_load: Vector3 = w2.player.global_position
		ok(Vector2(at_load.x - at_save.x, at_load.z - at_save.z).length() < 0.5 and absf(at_load.y - at_save.y) < 1.0 and w2.player.is_on_floor(),
			"the player stands where they saved (%.2f m off)" % at_load.distance_to(at_save))
		ok(absf(angle_difference(w2.player.rotation.y, yaw_save)) < 0.01, "the player faces the saved way")
		ok(ps2.stats.alive and ps2.deaths == deaths_save, "the player survives arriving (deaths %d)" % ps2.deaths)
		var comp2: CompanionDirector = w2.companion as CompanionDirector
		if comp2 != null and _ezra_recruited:
			ok(comp2.recruited(), "Ezra is still with the player after the load")
	_finish()


func _finish() -> void:
	print("[smoke] %s — %d failure(s), %.1fs" % ["PASS" if _fails == 0 else "FAIL", _fails, (Time.get_ticks_msec() - _t0) / 1000.0])
	get_tree().quit(1 if _fails > 0 else 0)


## Fails the run when a build that should carry the generated assets shows stand-ins: every
## vegetation model, every building kit piece built so far and a Hollowed's body must come from
## the generated models (the owner's first playtest ran on stand-ins without anyone noticing).
func _companion(game: Node, w: GameWorld, p: Player) -> void:
	var comp: CompanionDirector = w.companion as CompanionDirector
	var back: Vector3 = p.global_position
	var camp: Dictionary = comp.camp_spot() if comp != null else {}
	if camp.is_empty() and comp != null:
		# A random world's camp stands 300-750 m from the drop (generator 20), past the ring built
		# so far: walk there (teleport) and let the streaming build it, as it would for a player.
		camp = await _reach_camp(comp, w, p)
	if not ok(not camp.is_empty(), "the lineman's camp is in the world"):
		p.global_position = back
		w.terrain.update_streaming(p.global_position, true)
		return
	var ps: PlayerState = p.state
	var at: Vector3 = camp["pos"]
	p.global_position = Vector3(at.x, w.height_at(at.x, at.z + 2.5) + 0.1, at.z + 2.5)
	p.velocity = Vector3.ZERO
	w.terrain.update_streaming(p.global_position, true)
	await wait_until(func() -> bool:
		comp.tick()
		return comp.body != null and is_instance_valid(comp.body), 30.0)
	if not ok(comp.body != null, "Ezra waits at his camp"):
		p.global_position = back
		return
	ps.inventory.add_item(&"first_aid_kit", 1)
	var rr: Dictionary = game.execute(&"companion.recruit", {})
	if not ok(bool(rr.get("ok", false)), "recruited Ezra (%s)" % rr.get("error", "")):
		p.global_position = back
		return
	_ezra_recruited = true
	var m: CompanionMind = comp.mind()
	await wait_until(func() -> bool: return m.rising_t <= 0.0, 6.0)
	# Gather wood round the camp: he picks a tree or deadfall of the region's scatter, works it and
	# carries in what it gives.
	var rg: Dictionary = game.execute(&"companion.order", {"order": "gather", "kind": "wood", "spot": [at.x, at.y, at.z]})
	if ok(bool(rg.get("ok", false)), "ordered to gather wood (%s)" % rg.get("error", "")):
		var tg: int = Time.get_ticks_msec()
		var got: bool = await wait_until(func() -> bool:
			return comp.inventory.count_of(&"log") + comp.inventory.count_of(&"stick") > 0, 150.0)
		ok(got, "he brings in wood from the region (%d logs, %d sticks, %.0f s)" % [comp.inventory.count_of(&"log"),
			comp.inventory.count_of(&"stick"), (Time.get_ticks_msec() - tg) / 1000.0])
	# Fetch a log the player looked at.
	game.execute(&"companion.order", {"order": "follow"})
	# On open ground he can walk to (the camp's tent and fence are round the player here).
	var lat: Vector3 = comp.safe_spot(p.global_position, p.global_position + Vector3(8.0, 0.0, 3.0))
	var lg: LogEntity = w.loose.spawn_log(lat + Vector3.UP * 0.3, Basis(), &"")
	await frames(10)
	var rf: Dictionary = game.execute(&"companion.order", {"order": "fetch", "target": {"entity": String(lg.entity_id)}})
	if ok(bool(rf.get("ok", false)), "ordered to fetch a log (%s)" % rf.get("error", "")):
		var lpos: Vector3 = lg.global_position
		# Held weakly: he picks it up, and a freed capture is an engine error in the lambda.
		var lref: WeakRef = weakref(lg)
		var track: PackedStringArray = []
		var next_t: Array[int] = [0]
		var fetched: bool = await wait_until(func() -> bool:
			if Time.get_ticks_msec() > next_t[0]:
				next_t[0] = Time.get_ticks_msec() + 5000
				var bp: Vector3 = comp.body.global_position
				var cols: PackedStringArray = []
				for ci: int in comp.body.get_slide_collision_count():
					var kc: KinematicCollision3D = comp.body.get_slide_collision(ci)
					cols.append("%s n(%.2f,%.2f,%.2f)" % [(kc.get_collider() as Node).name if kc.get_collider() is Node else "?", kc.get_normal().x, kc.get_normal().y, kc.get_normal().z])
				var nx: Vector3 = comp.body.agent.get_next_path_position() - bp
				track.append("(%.1f,%.1f,%.1f %s/%s v(%.1f,%.1f) next(%.1f,%.1f,%.1f) fin %s far %s)" % [bp.x - at.x, bp.y, bp.z - at.z, m.order, m.work.phase,
					comp.body.velocity.x, comp.body.velocity.z, nx.x, nx.y, nx.z, comp.body.agent.is_navigation_finished(), comp.body._far])
			var l: Object = lref.get_ref()
			return l == null or (l as Node).is_queued_for_deletion(), 130.0)
		if not fetched:
			print("[smoke] fetch track (camp-relative): log at (%.1f,%.1f) player at (%.1f,%.1f): %s" % [lpos.x - at.x, lpos.z - at.z,
				p.global_position.x - at.x, p.global_position.z - at.z, " ".join(track)])
			var from: Vector3 = comp.body.global_position + Vector3.UP * 0.6
			var dir: Vector3 = Vector3(lpos.x - from.x, 0.0, lpos.z - from.z).normalized()
			for h: float in [0.3, 0.6, 1.2]:
				var q := PhysicsRayQueryParameters3D.create(comp.body.global_position + Vector3.UP * h, comp.body.global_position + Vector3.UP * h + dir * 2.0)
				q.exclude = [comp.body.get_rid()]
				var hit: Dictionary = comp.body.get_world_3d().direct_space_state.intersect_ray(q)
				print("[smoke] blocked at %.1f m: %s" % [h, "nothing" if hit.is_empty() else "%s (layer %d) at %.2f m" % [
					(hit["collider"] as Node).get_path(), (hit["collider"] as CollisionObject3D).collision_layer, comp.body.global_position.distance_to(hit["position"])]])
			var prof: PackedStringArray = []
			var bp0: Vector3 = comp.body.global_position
			for k: int in 17:
				var q2: Vector3 = bp0.lerp(Vector3(lpos.x, bp0.y, lpos.z), float(k) / 16.0)
				var down := PhysicsRayQueryParameters3D.create(q2 + Vector3.UP * 4.0, q2 + Vector3.DOWN * 4.0)
				down.exclude = [comp.body.get_rid()]
				var hh: Dictionary = comp.body.get_world_3d().direct_space_state.intersect_ray(down)
				prof.append("%.2f%s" % [(hh["position"] as Vector3).y - bp0.y if not hh.is_empty() else -99.0,
					"" if hh.is_empty() or (hh["collider"] as Node).name.begins_with("Col_") else "*"])
			print("[smoke] ground along the way (m above him, * not terrain): %s" % " ".join(prof))
			print("[smoke] nav next: %s, finished %s, target %s" % [comp.body.agent.get_next_path_position(), comp.body.agent.is_navigation_finished(), comp.body.agent.target_position])
		ok(fetched, "he fetches the log (he is %.1f m from it, %.1f m from the player, order %s, %s)" % [comp.body.global_position.distance_to(lpos),
			comp.body.global_position.distance_to(p.global_position), m.order, m.work.to_dict()])
		var rtrack: PackedStringArray = []
		var rnext: Array[int] = [0]
		await wait_until(func() -> bool:
			if Time.get_ticks_msec() > rnext[0]:
				rnext[0] = Time.get_ticks_msec() + 3000
				var bp: Vector3 = comp.body.global_position
				var nx: Vector3 = comp.body.agent.get_next_path_position() - bp
				var cols: PackedStringArray = []
				for ci: int in comp.body.get_slide_collision_count():
					var kc: KinematicCollision3D = comp.body.get_slide_collision(ci)
					if kc.get_normal().y < 0.7:
						cols.append("%s" % ((kc.get_collider() as Node).get_path() if kc.get_collider() is Node else "?"))
				rtrack.append("(%.1f,%.1f %s v(%.1f,%.1f) next(%.1f,%.1f) straight %s detour %.1f [%s])" % [bp.x - at.x, bp.z - at.z, m.work.phase,
					comp.body.velocity.x, comp.body.velocity.z, nx.x, nx.z, comp.body._nav_straight, comp.body._detour_t, ", ".join(cols)])
			return m.order == "follow", 90.0)
		# The camp's yard joins the mesh round it only far off (TD-340): on the way back he walks the
		# long way round at a carrying pace.
		if m.order != "follow":
			print("[smoke] return track: %s" % " ".join(rtrack))
	var before: int = ps.inventory.count_of(&"stick") + ps.inventory.count_of(&"log")
	# Give is a hand-over within reach: he comes back to the player first.
	await wait_until(func() -> bool: return comp.body.global_position.distance_to(p.global_position) < 5.0, 30.0)
	var rgv: Dictionary = game.execute(&"companion.give", {})
	var bpg: Vector3 = comp.body.global_position
	ok(bool(rgv.get("ok", false)) or comp.inventory.is_empty(), "he hands over what he carries (%s; %.1f m off at (%.1f,%.1f), order %s/%s, carrying %s)" % [
		rgv.get("error", ""), bpg.distance_to(p.global_position), bpg.x - at.x, bpg.z - at.z, m.order, m.work.phase, comp.inventory.to_dict() if comp.inventory.has_method(&"to_dict") else ""])
	ok(ps.inventory.count_of(&"stick") + ps.inventory.count_of(&"log") >= before, "the player has it")
	game.execute(&"companion.order", {"order": "follow"})
	p.global_position = back
	p.velocity = Vector3.ZERO
	w.terrain.update_streaming(p.global_position, true)
	await seconds(0.5)


## Takes the player to the camp's building while it is placed but not built, until it is built
## ({} if it never is, saying what held it back).
func _reach_camp(comp: CompanionDirector, w: GameWorld, p: Player) -> Dictionary:
	var poi: String = str(comp.cdef.camp.get("poi", ""))
	var entry: Dictionary = {}
	for v: Variant in w.pois.all_buildings():
		if str((v as Dictionary).get("def", "")) == poi:
			entry = v
			break
	if entry.is_empty():
		print("[smoke] no %s in the world's buildings" % poi)
		return {}
	var at: Vector3 = entry["pos"]
	print("[smoke] camp %s placed at (%.0f, %.0f), %.0f m from the player: walking there" % [entry.get("id", ""), at.x, at.z,
		Vector2(at.x - p.global_position.x, at.z - p.global_position.z).length()])
	p.global_position = Vector3(at.x, w.height_at(at.x, at.z + 12.0) + 0.5, at.z + 12.0)
	p.velocity = Vector3.ZERO
	w.terrain.update_streaming(p.global_position, true)
	var id: StringName = StringName(str(entry.get("id", "")))
	var next_t: Array[int] = [0]
	var found: Array = [{}]
	await wait_until(func() -> bool:
		found[0] = comp.camp_spot()
		if Time.get_ticks_msec() > next_t[0]:
			next_t[0] = Time.get_ticks_msec() + 5000
			var e: Dictionary = w.pois.registry.entries.get(id, {}) if w.pois.registry != null else {}
			print("[smoke] camp: region %s attached %s, queued %s, built %s; %d built + %d on the way (max %d)" % [
				e.get("region", "?"), w.terrain.regions.has(str(e.get("region", ""))), w.pois._jobs.has(id), w.pois.instances.has(id),
				w.pois.instances.size(), w.pois._jobs.size(), w.pois._max_built])
		return not (found[0] as Dictionary).is_empty(), 180.0)
	return found[0]


func _check_real_models(w: GameWorld, p: Player) -> void:
	var share: float = ModelLibrary.generated_share(get_node("/root/Content"))
	ok(share >= 1.0, "every vegetation model is generated (%.0f%%)" % (share * 100.0))
	var kit: int = 0
	var standins: Array[String] = []
	for piece: String in PoiParts._meshes:
		kit += 1
		if not ModelLibrary._generated.has(PoiParts.KIT + piece):
			standins.append(piece)
	ok(kit > 0 and standins.is_empty(), "buildings use generated kit pieces (%d built, stand-ins: %s)" % [kit, ", ".join(standins)])
	var ai: AIDirector = w.ai as AIDirector
	if ok(ai != null, "AI module for the model check"):
		var at: Vector3 = p.global_position + Vector3(8, 0, 0)
		at.y = w.height_at(at.x, at.z)
		var e: Enemy = ai.spawn(&"hollow", at)
		if ok(e != null, "spawned a Hollowed for the model check"):
			await frames(2)
			ok(e.visual != null and not e.visual._placeholder, "the Hollowed has its generated body")
			ai.despawn(e)
			await frames(2)
