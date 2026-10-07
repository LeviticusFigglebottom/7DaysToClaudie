extends Node
## Runner of continue_check.gd (loaded once the autoloads exist): a save far from the drop site
## must come back at the same spot and facing after quit-to-menu and Continue (player report 3).

const YAW: float = 2.1
const PITCH: float = -0.4

var _fails: int = 0
var _t0: int = 0
var _slow_ms: int = 0


func _ready() -> void:
	_t0 = Time.get_ticks_msec()
	_run.call_deferred()


func _process(_delta: float) -> void:
	if _slow_ms > 0:
		OS.delay_msec(_slow_ms)


func ok(cond: bool, what: String) -> bool:
	print("[continue] %s %s" % ["ok   " if cond else "FAIL ", what])
	if not cond:
		_fails += 1
	return cond


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


func _run() -> void:
	var game: Node = get_node("/root/Game")
	var opts: Dictionary = {"game_mode": "slice", "skip_intro": true, "slot": "continue_check"}
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var i: int = args.find("--world")
	if i >= 0 and i + 1 < args.size() and args[i + 1] == "random":
		opts["world_gen"] = (load("res://src/app/main.gd") as GDScript).call(&"world_gen_from_args", args, 1)
		opts["slot"] = "continue_check_rwg"
		opts["stream"] = not args.has("--no-stream")
	var dist: float = float(args[args.find("--distance") + 1]) if args.has("--distance") else 160.0
	game.call(&"start_new_game", opts)
	if not ok(await wait_until(func() -> bool: return game.get(&"world") != null and bool(game.world.is_ready), 300.0), "new game ready"):
		_finish()
		return
	var w: GameWorld = game.world
	var start: Vector3 = w.player.global_position
	# Move off: far enough that a streamed world attaches other regions there.
	var target := Vector3(start.x + dist * 0.8, 0.0, start.z + dist * 0.6)
	var arrived: Array = [false]
	w.await_area(target, func() -> void:
		w.player.global_position = Vector3(target.x, w.height_at(target.x, target.z) + 0.5, target.z)
		w.player.velocity = Vector3.ZERO
		w.player.input_enabled = true
		arrived[0] = true)
	ok(await wait_until(func() -> bool: return bool(arrived[0]), 240.0), "moved %.0f m from the drop site" % dist)
	await seconds(2.0)
	var p: Player = w.player
	if args.has("--indoor"):
		# Inside the nearest building, on its highest floor under 4.5 m (Pell's Crossing's cottages).
		var best: Dictionary = {}
		for b: Dictionary in (w.pois as PoiManager).all_buildings():
			if b.get("pos") is Vector3 and (best.is_empty() or (b["pos"] as Vector3).distance_to(p.global_position) < (best["pos"] as Vector3).distance_to(p.global_position)):
				if (w.pois as PoiManager).instances.has(b["id"]):
					best = b
		if ok(not best.is_empty(), "a building to stand in"):
			var c: Vector3 = best["pos"]
			var g: float = w.height_at(c.x, c.z)
			var q := PhysicsRayQueryParameters3D.create(Vector3(c.x, g + 4.5, c.z), Vector3(c.x, g - 3.0, c.z), (1 << 0) | (1 << 1) | (1 << 2))
			var hit: Dictionary = p.get_world_3d().direct_space_state.intersect_ray(q)
			var floor_y: float = (hit["position"] as Vector3).y if not hit.is_empty() else g
			p.global_position = Vector3(c.x, floor_y + 0.1, c.z)
			p.velocity = Vector3.ZERO
			print("[continue] indoors in %s (%s) at floor %.2f, terrain %.2f" % [best["id"], best.get("def", ""), floor_y, g])
			await seconds(2.0)
	var saved_floor: bool = p.is_on_floor()
	ok(saved_floor, "standing before the save")
	p.rotation.y = YAW
	p.set(&"_pitch", PITCH)
	p.head.rotation.x = PITCH
	await seconds(1.0)
	var saved_pos: Vector3 = p.global_position
	var saved_hp: float = p.state.stats.health
	print("[continue] saving at %s (ground %.2f, on floor %s), yaw %.3f pitch %.3f" % [saved_pos, w.ground_below(saved_pos), p.is_on_floor(), p.rotation.y, float(p.get(&"_pitch"))])
	ok(bool(game.call(&"save_game", "")), "saved")
	var slot: String = str(game.get(&"current_slot"))
	game.call(&"quit_to_menu")
	await seconds(1.0)
	var slots: Array[Dictionary] = SaveSystem.list_slots()
	ok(not slots.is_empty() and str(slots[0]["slot"]) == slot, "Continue offers the slot just saved (%s)" % slot)
	ok(bool(game.call(&"load_game", slot)), "Continue started")
	# A slow machine (the owner's Windows build): frames of --slow-ms while the world loads, so
	# physics runs its full steps per frame while the player waits for the ground.
	_slow_ms = int(args[args.find("--slow-ms") + 1]) if args.has("--slow-ms") else 0
	# The ground under the player arriving late (--late-ground S): on a real renderer the terrain
	# meshes and its collision come from worker threads, seconds after the player can fall; headless
	# they are made on the main thread before the player ticks. Emulated by giving the player
	# nothing to stand on, and holding "Finding your feet", for S seconds once it ticks.
	var late: float = float(args[args.find("--late-ground") + 1]) if args.has("--late-ground") else 0.0
	var late_end: Array = [-1]
	var loaded: bool = await wait_until(func() -> bool:
		var gw: Variant = game.get(&"world")
		if gw != null and is_instance_valid(gw) and (gw as GameWorld).player != null:
			var pl: Player = (gw as GameWorld).player
			if late > 0.0 and pl.can_process() and not bool((gw as GameWorld).is_ready):
				if int(late_end[0]) < 0:
					late_end[0] = Time.get_ticks_msec() + int(late * 1000.0)
					pl.set_meta(&"mask", pl.collision_mask)
					pl.collision_mask = 0
				if Time.get_ticks_msec() < int(late_end[0]):
					(gw as GameWorld).set(&"_spawn_settle", 0)
				elif pl.has_meta(&"mask"):
					pl.collision_mask = int(pl.get_meta(&"mask"))
					pl.remove_meta(&"mask")
			if Engine.get_process_frames() % 10 == 0:
				print("[continue] loading: %s y %.2f vy %.2f fall %.2f hp %.0f floor %s" % [(gw as GameWorld).ui.loading_text(), pl.global_position.y, pl.velocity.y, float(pl.get(&"_fall_speed")), pl.state.stats.health, pl.is_on_floor()])
		return gw != null and is_instance_valid(gw) and bool((gw as GameWorld).is_ready), 300.0)
	_slow_ms = 0
	if not ok(loaded, "continued world ready"):
		_finish()
		return
	var deaths: int = Game.local_player().deaths
	var p2: Player = (game.world as GameWorld).player
	_check(p2, saved_pos, "at ready")
	await seconds(3.0)
	_check(p2, saved_pos, "3 s later")
	ok(p2.state.stats.alive and p2.state.deaths == deaths and p2.state.stats.health >= saved_hp - 1.0, "unhurt by the load (health %.0f of %.0f, deaths %d)" % [p2.state.stats.health, saved_hp, p2.state.deaths])
	SaveSystem.delete_slot(slot)
	_finish()


func _check(p2: Player, saved_pos: Vector3, when: String) -> void:
	var pos: Vector3 = p2.global_position
	var flat: float = Vector2(pos.x - saved_pos.x, pos.z - saved_pos.z).length()
	ok(flat < 0.5 and absf(pos.y - saved_pos.y) < 1.0, "%s: back where saved (%s vs %s, %.2f m)" % [when, pos, saved_pos, flat])
	ok(absf(angle_difference(p2.rotation.y, YAW)) < 0.01, "%s: facing restored (yaw %.3f)" % [when, p2.rotation.y])
	ok(absf(float(p2.get(&"_pitch")) - PITCH) < 0.01 and absf(p2.head.rotation.x - PITCH) < 0.01, "%s: view pitch restored (%.3f)" % [when, p2.head.rotation.x])
	var cam: Camera3D = p2.get_viewport().get_camera_3d()
	ok(cam == p2.camera, "%s: the player's camera is current (%s)" % [when, cam.get_path() if cam != null else "none"])


func _finish() -> void:
	# Out of the world first: quitting with a streamed world mid-load sometimes crashed in the
	# engine's teardown (heap corruption after the PASS line) and turned a pass into exit 134.
	if get_node("/root/Game").get(&"world") != null:
		get_node("/root/Game").call(&"quit_to_menu")
		await seconds(1.0)
	print("[continue] %s - %d failure(s), %.1fs" % ["PASS" if _fails == 0 else "FAIL", _fails, (Time.get_ticks_msec() - _t0) / 1000.0])
	get_tree().quit(1 if _fails > 0 else 0)
