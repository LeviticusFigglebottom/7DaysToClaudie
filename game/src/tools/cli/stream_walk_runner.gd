extends Node
## Stream-walk logic (loaded by stream_walk.gd once autoloads exist). See stream_walk.gd.

var _fails: int = 0


func _ready() -> void:
	_run.call_deferred()


func _arg(args: PackedStringArray, key: String, default: String) -> String:
	var i: int = args.find(key)
	return args[i + 1] if i >= 0 and i + 1 < args.size() else default


func _run() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var km: float = float(_arg(args, "--km", "2"))
	var speed: float = float(_arg(args, "--speed", "6.2"))
	var laps: int = int(_arg(args, "--laps", "2"))
	var gen_args: PackedStringArray = ["--world-seed", _arg(args, "--world-seed", "7")]
	for i: int in args.size() - 1:
		if args[i] == "--world-set":
			gen_args.append_array(["--world-set", args[i + 1]])
	if not "--world-set" in gen_args:
		gen_args.append_array(["--world-set", "size=5"])
	var game: Node = get_node("/root/Game")
	var gen: Dictionary = (load("res://src/app/main.gd") as GDScript).call(&"world_gen_from_args", gen_args, 7)
	var t0: int = Time.get_ticks_msec()
	game.call(&"start_new_game", {"game_mode": "survival", "skip_intro": true, "slot": "stream_walk", "world_gen": gen, "stream": true})
	while game.get(&"world") == null or not bool(game.world.is_ready):
		await get_tree().process_frame
		if Time.get_ticks_msec() - t0 > 600000:
			printerr("[stream] FAIL the world never loaded")
			get_tree().quit(1)
			return
	var w: GameWorld = game.world
	var p: Player = w.player
	var st: RegionStreamer = w.terrain.streamer
	if st == null:
		printerr("[stream] FAIL no streamer: the world did not stream")
		get_tree().quit(1)
		return
	p.god_mode = true
	p.input_enabled = false
	print("[stream] world ready in %.1f s: %s" % [(Time.get_ticks_msec() - t0) / 1000.0, st.status()])
	var start: Vector3 = p.global_position
	# Across the world's longest open line from the spawn: towards its centre and beyond.
	var dir := Vector3(-start.x, 0.0, -start.z)
	dir = dir.normalized() if dir.length() > 10.0 else Vector3(1, 0, 0)
	var mem: Array[float] = []
	var late_total: float = 0.0
	var longest: float = 0.0
	for lap: int in laps:
		for leg: int in 2:
			var from: Vector3 = start if leg == 0 else start + dir * km * 1000.0
			var to: Vector3 = start + dir * km * 1000.0 if leg == 0 else start
			var res: Dictionary = await _walk(w, p, st, from, to, speed)
			late_total += float(res["late_s"])
			longest = maxf(longest, float(res["longest_ms"]))
			print("[stream] lap %d leg %d: %.0f m in %.1f s, late %.1f s, longest frame %.0f ms, %s" % [
				lap + 1, leg + 1, from.distance_to(to), res["seconds"], res["late_s"], res["longest_ms"], st.status()])
		# Settle at the start, then read memory.
		for i: int in 120:
			await get_tree().process_frame
		mem.append(Performance.get_monitor(Performance.MEMORY_STATIC) / 1048576.0)
		print("[stream] after lap %d: static memory %.0f MiB, %d nodes" % [lap + 1, mem.back(), get_tree().get_node_count()])
	if late_total > 2.0:
		_fails += 1
		printerr("[stream] FAIL the player outran streaming for %.1f s" % late_total)
	if mem.size() >= 2 and mem[mem.size() - 1] > mem[0] * 1.05:
		_fails += 1
		printerr("[stream] FAIL memory grew %.0f -> %.0f MiB between returns" % [mem[0], mem[mem.size() - 1]])
	print("[stream] %s: late %.1f s, longest frame %.0f ms, memory %s MiB" % ["PASS" if _fails == 0 else "FAIL", late_total, longest, str(mem)])
	get_tree().quit(1 if _fails > 0 else 0)


## Carries the player from `from` to `to` at `speed` m/s on the ground (no physics: streaming is
## what is measured). Late = frames whose region under the player was not attached.
func _walk(w: GameWorld, p: Player, st: RegionStreamer, from: Vector3, to: Vector3, speed: float) -> Dictionary:
	var dist: float = from.distance_to(to)
	var t: float = 0.0
	var late: float = 0.0
	var longest: float = 0.0
	var last: int = Time.get_ticks_usec()
	var d: Vector3 = (to - from).normalized()
	p.rotation.y = atan2(-d.x, -d.z)
	while t * speed < dist:
		await get_tree().process_frame
		var now: int = Time.get_ticks_usec()
		var dt: float = float(now - last) / 1e6
		last = now
		longest = maxf(longest, dt * 1000.0)
		# Game time, not wall time: a slow frame on this container must not teleport the player.
		var step: float = minf(dt, 1.0 / 30.0)
		t += step
		var pos: Vector3 = from + d * minf(t * speed, dist)
		pos.y = w.height_at(pos.x, pos.z) + 0.1
		p.global_position = pos
		p.velocity = d * speed
		if not st.is_area_ready(pos, 0.0):
			late += step
	return {"seconds": t, "late_s": late, "longest_ms": longest}
