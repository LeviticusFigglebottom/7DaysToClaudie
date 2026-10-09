extends Node
## Walk-tour logic (loaded by walk_tour.gd once autoloads exist). The player sprints into each kind
## of thing (tree, bush, rock, deadfall, plants, POIs and their props, loose items, logs, a
## Hollowed, wildlife), stands inside it, swings at it and uses whatever the interaction ray finds.
## A crash shows as the process dying before "[tour] PASS"; script errors are counted from the log
## by CI. `-- --mode survival|slice` picks the game mode (survival, as the menu's New Game).

## Wall-clock limit for the whole tour (a random 10 km world takes 10–20 min on a busy machine).
const WATCHDOG_S: float = 1800.0

var _fails: int = 0
var _t0: int = 0
var _visits: int = 0
var w: GameWorld
var p: Player


func _ready() -> void:
	_t0 = Time.get_ticks_msec()
	# A script error inside _run's coroutine stops it without quitting: without this the process
	# would idle until an outside timeout instead of failing.
	get_tree().create_timer(WATCHDOG_S, true, false, true).timeout.connect(_on_watchdog)
	_run.call_deferred()


func _on_watchdog() -> void:
	ok(false, "tour finished within %d s (a script error stops the tour's coroutine)" % int(WATCHDOG_S))
	_finish()


func ok(cond: bool, what: String) -> bool:
	if cond:
		print("[tour] ok    %s" % what)
	else:
		_fails += 1
		printerr("[tour] FAIL  %s" % what)
	return cond


func frames(n: int) -> void:
	for i: int in n:
		await get_tree().physics_frame


func wait_until(cond: Callable, timeout_s: float) -> bool:
	var end: int = Time.get_ticks_msec() + int(timeout_s * 1000.0)
	while Time.get_ticks_msec() < end:
		if cond.call():
			return true
		await get_tree().process_frame
	return false


func _run() -> void:
	var game: Node = get_node("/root/Game")
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var mode: String = args[args.find("--mode") + 1] if args.find("--mode") >= 0 and args.find("--mode") + 1 < args.size() else "survival"
	var opts: Dictionary = {"game_mode": mode, "skip_intro": true, "slot": "tour"}
	# `--world random [--world-seed N] [--world-preset id] [--world-set key=value ...]` tours a random
	# world (ADR-0031), read as the game's own command line reads it (map seed 7 by default).
	var wi: int = args.find("--world")
	if wi >= 0 and wi + 1 < args.size() and args[wi + 1] == "random":
		opts["world_gen"] = (load("res://src/app/main.gd") as GDScript).call(&"world_gen_from_args", args, 7)
		# Random worlds stream by default (ADR-0038); --no-stream loads every region and building.
		opts["stream"] = not args.has("--no-stream")
	game.call(&"start_new_game", opts)
	# A random world composes its regions on its first load (minutes on a busy machine).
	var ready: bool = await wait_until(func() -> bool: return game.get(&"world") != null and bool(game.world.is_ready), 600.0 if opts.has("world_gen") else 240.0)
	if not ok(ready, "world loads and the player spawns (%.1fs)" % ((Time.get_ticks_msec() - _t0) / 1000.0)):
		_finish()
		return
	w = game.world
	p = w.player
	p.god_mode = true
	p.state.inventory.add_item(&"stone_axe", 1)
	var slot: int = p.state.toolbelt.find(&"stone_axe")
	if slot < 0:
		p.state.toolbelt[0] = &"stone_axe"
		slot = 0
	p.equipment.select_slot(slot)
	var spawn: Vector3 = p.global_position
	await frames(30)

	# --- Vegetation: one of every kind near the spawn --------------------------------------------
	var veg: VegetationManager = w.vegetation
	# "World ready" doesn't wait for the scatter (or, streamed, the buildings past the boot radius):
	# a quick load reached here with nothing scattered and the tour skipped every kind.
	if not await wait_until(func() -> bool: return veg.is_settled(1), 60.0):
		print("[tour] note  vegetation not settled: %s" % veg.settle_report(1))
	for kind: String in ["tree", "rock", "deadfall", "bush", "fern", "herb", "mushroom", "flower"]:
		var found: Array = veg.nearest_instance(spawn, kind, 200.0)
		if found.is_empty():
			print("[tour] skip  no %s near the spawn" % kind)
			continue
		var inst: VegetationScatter.Instance = found[1]
		await visit("%s %s" % [kind, inst.species], inst.pos, 1.2 if kind in ["tree", "rock", "deadfall"] else 0.4)
		await swing(12 if kind == "tree" else 4)
		await use()

	# --- Logs and loose items ----------------------------------------------------------------------
	for g: StringName in [&"logs", &"item_drops"]:
		var nodes: Array = get_tree().get_nodes_in_group(g)
		# Untyped: an earlier visit can free a later node (picked up, or streamed out).
		for n: Variant in nodes.slice(0, 3):
			if is_instance_valid(n) and n is Node3D:
				await visit("%s %s" % [g, (n as Node).name], (n as Node3D).global_position, 0.5)
				await use()

	# --- POIs: walk up to each, into it, swing at whatever is in front, use what the ray finds ------
	# A streamed world builds and frees buildings by the player's distance (ADR-0038) while the tour
	# walks, so each pick is the nearest building still standing, never a list taken up front.
	var seen_pois: Dictionary = {}
	if w.pois != null and not await wait_until(func() -> bool: return (w.pois.get(&"_jobs") as Dictionary).is_empty(), 120.0):
		print("[tour] note  buildings still on their way after 120 s")
	var live: Dictionary = w.pois.get(&"instances") as Dictionary if w.pois != null else {}
	for i: int in 6:
		var poi: Node3D = null
		var poi_id: StringName = &""
		var best: float = INF
		for id: StringName in live:
			var cand: Variant = live[id]
			if seen_pois.has(id) or not is_instance_valid(cand):
				continue
			var d: float = (cand as Node3D).global_position.distance_to(spawn)
			if d < best:
				best = d
				poi = cand
				poi_id = id
		if poi == null:
			break
		seen_pois[poi_id] = true
		await visit("poi %s" % poi.name, poi.global_position, 1.0)
		for k: int in 8:
			p.rotation.y = k * TAU / 8.0
			await frames(2)
			await use()
			await swing(1)

	# --- A Hollowed, close enough to touch ------------------------------------------------------------
	if w.ai != null:
		for enemy_id: StringName in [&"hollow", &"lurcher", &"keener"]:
			var at: Vector3 = p.global_position + Vector3(6, 0, 0)
			at.y = w.height_at(at.x, at.z)
			var e: Enemy = (w.ai as AIDirector).spawn(enemy_id, at)
			if ok(e != null, "spawned a %s" % enemy_id):
				await visit("enemy %s" % enemy_id, e.global_position, 0.6, e)
				await swing(6)

	# --- Wildlife ---------------------------------------------------------------------------------
	if w.wildlife != null:
		var animals: Array = (w.wildlife.get(&"animals") as Dictionary).values()
		for a: Variant in animals.slice(0, 2):
			# Validity first: an animal the last swing killed is freed, and `is` on a freed one errors.
			if is_instance_valid(a) and a is Node3D:
				await visit("animal %s" % (a as Node).name, (a as Node3D).global_position, 0.6, a)
				await swing(3)

	ok(_visits > 0, "visited %d things" % _visits)
	ok(p.state.stats.alive and is_finite(p.global_position.y), "player still standing at the end")
	_finish()


## Sprints at a point (re-aimed every frame, at `follow` when it moves) until within `stop` metres
## or 12 s pass, then stands on it for a moment: the overlap and contact paths a player hits.
func visit(what: String, target: Vector3, stop: float, follow: Variant = null) -> void:
	_visits += 1
	var start: Vector3 = target + Vector3(14, 0, 3)
	start.y = w.height_at(start.x, start.z) + 1.0
	if not is_finite(start.y):
		start.y = target.y + 1.0
	p.global_position = start
	p.velocity = Vector3.ZERO
	w.terrain.update_streaming(p.global_position, true)
	await frames(3)
	Input.action_press(&"move_forward")
	Input.action_press(&"sprint")
	var end: int = Time.get_ticks_msec() + 12000
	var reached: bool = false
	while Time.get_ticks_msec() < end:
		if follow != null and is_instance_valid(follow):
			target = (follow as Node3D).global_position
		var to := Vector3(target.x - p.global_position.x, 0.0, target.z - p.global_position.z)
		if to.length() < stop:
			reached = true
			break
		p.rotation.y = atan2(-to.x, -to.z)
		await get_tree().physics_frame
	Input.action_release(&"move_forward")
	Input.action_release(&"sprint")
	# Stand right on it (inside a trunk or a crate): what running into it at speed can end in.
	var inside := Vector3(target.x, maxf(target.y, w.height_at(target.x, target.z)) + 0.2, target.z)
	p.global_position = inside
	await frames(20)
	print("[tour] seen  %s (%s, %.1f m left)" % [what, "reached" if reached else "blocked", Vector2(target.x - p.global_position.x, target.z - p.global_position.z).length()])


func swing(times: int) -> void:
	for i: int in times:
		p.equipment.primary()
		await frames(int(0.9 * Engine.physics_ticks_per_second))


func use() -> void:
	await frames(2)
	var t: Object = p.interaction.target
	if t != null and is_instance_valid(t) and t.has_method(&"interact"):
		t.call(&"interact", p)
		await frames(5)


func _finish() -> void:
	print("[tour] %s — %d failure(s), %d visits, %.1fs" % ["PASS" if _fails == 0 else "FAIL", _fails, _visits, (Time.get_ticks_msec() - _t0) / 1000.0])
	get_tree().quit(1 if _fails > 0 else 0)
