extends Node
## Spawn check logic (see spawn_check.gd).

var _fails: int = 0


func ok(cond: bool, what: String) -> bool:
	print("[spawn] %s %s" % ["ok   " if cond else "FAIL ", what])
	if not cond:
		_fails += 1
	return cond


func _ready() -> void:
	_run.call_deferred()


func _run() -> void:
	var game: Node = get_node("/root/Game")
	var args: PackedStringArray = OS.get_cmdline_user_args()
	# The New Game screen's options (new_game_panel.gd _start): no skip_intro, a preset, rules.
	var opts: Dictionary = {"game_mode": "survival", "preset": "survivor", "rules": {}, "seed": 1234}
	var wi: int = args.find("--world")
	if wi >= 0 and wi + 1 < args.size() and args[wi + 1] == "random":
		opts["world_gen"] = (load("res://src/app/main.gd") as GDScript).call(&"world_gen_from_args", args, 7)
		if args.has("--no-stream"):
			opts["stream"] = false
	var t0: int = Time.get_ticks_msec()
	game.call(&"start_new_game", opts)
	while game.get(&"world") == null or not bool(game.world.is_ready):
		await get_tree().process_frame
		if Time.get_ticks_msec() - t0 > 600000:
			ok(false, "world ready within 600 s")
			get_tree().quit(1)
			return
	print("[spawn] world ready in %.1f s" % ((Time.get_ticks_msec() - t0) / 1000.0))
	await _check(game.world)
	print("[spawn] %s — %d failure(s)" % ["PASS" if _fails == 0 else "FAIL", _fails])
	get_tree().quit(_fails)


func _check(w: Node) -> void:
	var p: Player = w.player
	var vp: Viewport = get_viewport()
	ok(p.can_process(), "player processes (mode %d)" % p.process_mode)
	ok(p.input_enabled, "player input enabled")
	ok(p.look_enabled, "player look enabled")
	var cam: Camera3D = vp.get_camera_3d()
	ok(cam == p.camera, "the player camera is current (%s)" % (cam.get_path() if cam != null else "none"))
	var vm: Node = p.get_node_or_null("Head/Camera3D/ViewModel")
	ok(vm != null and vm.get_parent() == p.camera, "the viewmodel hangs off the player camera")
	for c: Node in w.get_children():
		if c is Camera3D:
			print("[spawn] note: a camera under the world: %s current=%s" % [c.name, (c as Camera3D).current])
	print("[spawn] held: %s" % [w.get(&"_held")])
	var bodies: int = get_tree().root.find_children("*", "CollisionObject3D", true, false).size()
	print("[spawn] collision objects in the tree: %d" % bodies)
	ok(PhysicsServer3D.body_get_space(p.get_rid()).is_valid(), "the player body is in a physics space")
	# The current camera over the first seconds (a warm-up or stand-in camera taking over again).
	var seen: Dictionary = {}
	for i: int in 120:
		await get_tree().process_frame
		var c2: Camera3D = vp.get_camera_3d()
		seen[str(c2.get_path()) if c2 != null else "none"] = true
	ok(seen.size() == 1, "one current camera over 120 frames: %s" % [seen.keys()])
	_shot("spawn")
	# Walk: press forward for 3 s.
	await get_tree().physics_frame
	var start: Vector3 = p.global_position
	print("[spawn] at %s, on floor %s, ground %.2f" % [start, p.is_on_floor(), float(w.call(&"ground_below", start))])
	# 3 s of physics ticks, not wall time (a software-rendered frame takes seconds).
	Input.action_press(&"move_forward")
	for i: int in 180:
		await get_tree().physics_frame
	Input.action_release(&"move_forward")
	var moved: float = Vector2(p.global_position.x - start.x, p.global_position.z - start.z).length()
	ok(moved > 3.0, "the player walks (%.2f m in 3 s of physics; velocity %s)" % [moved, p.velocity])
	# Look up: the head pitches, the viewmodel stays under the camera.
	var ev := InputEventMouseMotion.new()
	ev.relative = Vector2(0, -400)
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	if Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		p._unhandled_input(ev)
	else:
		# Headless can't capture the mouse: pitch the way the handler does.
		p.set(&"_pitch", 1.0)
		p.head.rotation.x = 1.0
	for i: int in 30:
		await get_tree().process_frame
	_shot("look_up")
	ok(p.head.rotation.x > 0.3, "looking up pitches the head (%.2f rad)" % p.head.rotation.x)
	if vm != null:
		var local: Vector3 = p.camera.global_transform.affine_inverse() * (vm as Node3D).global_position
		ok(local.length() < 1.0, "the viewmodel stays at the camera (%.2f m off)" % local.length())


func _shot(name: String) -> void:
	if DisplayServer.get_name() == "headless":
		return
	await RenderingServer.frame_post_draw
	var img: Image = get_viewport().get_texture().get_image()
	var out: String = OS.get_environment("SPAWN_SHOTS")
	if out != "" and img != null:
		img.save_png(out.path_join("%s.png" % name))
		print("[spawn] shot %s" % out.path_join("%s.png" % name))
