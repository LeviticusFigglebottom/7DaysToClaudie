extends Node
## Renders the stills the menu and the intro show instead of drawing 3D live (ADR-0065), into
## --out <dir> (tools/stills.sh moves them to assets/generated/stills/ with their import sidecars):
##   --shot menu   menu_0.png ... : MenuFlight's stills along the Tamsin at dusk (MenuBackdrop pans
##                 across them)
##   --shot wreck  intro_wreck.png: the intro's world card, the Lift 3 wreck at first light, from the
##                 start of the card's framing (IntroPlayer zooms in on it, as the shot pushed in)
## Each is drawn supersampled (SUPER) into a SubViewport and scaled down to SIZE: larger than a
## 1080p screen, so the slow pan and zoom never magnify it.

const SIZE: Vector2i = Vector2i(3200, 1800)
const SUPER: float = 1.2
## Frames drawn before the capture: the first after a cut fills shadows and the ubershader cache.
const SETTLE: int = 2
## Seconds the wreck waits at most for the forest round it to stream in.
const STREAM_WAIT: float = 300.0

var _out: String = ""
var _vp: SubViewport


func _ready() -> void:
	_run.call_deferred()


func _run() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var shot: String = _arg(args, "--shot", "menu")
	_out = _arg(args, "--out", "")
	if _out == "":
		printerr("STILLS needs --out <dir>")
		get_tree().quit(2)
		return
	DirAccess.make_dir_recursive_absolute(_out)
	var t0: int = Time.get_ticks_msec()
	var ok: bool = false
	match shot:
		"menu":
			ok = await _menu()
		"wreck":
			ok = await _wreck()
		_:
			printerr("STILLS unknown shot %s" % shot)
	print("STILLS %s %s in %.1fs" % [shot, "done" if ok else "FAILED", (Time.get_ticks_msec() - t0) / 1000.0])
	get_tree().quit(0 if ok else 1)


func _viewport(own_world: bool) -> void:
	_vp = SubViewport.new()
	_vp.size = Vector2i(roundi(SIZE.x * SUPER), roundi(SIZE.y * SUPER))
	_vp.own_world_3d = own_world
	_vp.msaa_3d = Viewport.MSAA_4X
	# Drawn only for a capture: a frame at this size costs about a minute in software.
	_vp.render_target_update_mode = SubViewport.UPDATE_DISABLED
	add_child(_vp)


## Draws SETTLE frames and saves the last at SIZE as `name`.png.
func _capture(name: String) -> void:
	_vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	for k: int in SETTLE:
		await RenderingServer.frame_post_draw
	_vp.render_target_update_mode = SubViewport.UPDATE_DISABLED
	var img: Image = _vp.get_texture().get_image()
	img.convert(Image.FORMAT_RGB8)
	img.resize(SIZE.x, SIZE.y, Image.INTERPOLATE_LANCZOS)
	img.save_png(_out.path_join(name + ".png"))
	print("STILLS saved %s" % name)


func _menu() -> bool:
	# Nothing else draws: the root's 3D is off and the stills' viewport has its own world.
	get_viewport().disable_3d = true
	_viewport(true)
	var flight := MenuFlight.new()
	_vp.add_child(flight)
	if not flight.build():
		printerr("STILLS menu: no D6 terrain or no Tamsin path")
		return false
	for i: int in MenuFlight.STILLS.size():
		flight.place_still(i)
		await _capture("menu_%d" % i)
	return true


func _wreck() -> bool:
	var card: Dictionary = {}
	for c: Variant in (IntroPlayer.load_script().get("cards", []) as Array):
		if str((c as Dictionary).get("kind", "")) == "world":
			card = c
	if card.is_empty():
		printerr("STILLS wreck: intro.json has no world card")
		return false
	# The world draws only into the still's viewport, once, at the end: under software rendering
	# every frame of the load and the streaming wait would otherwise cost seconds.
	get_viewport().disable_3d = true
	Game.start_new_game({"game_mode": "survival", "seed": 4471, "skip_intro": true, "slot": "qa_stills"})
	var t0: int = Time.get_ticks_msec()
	while (Game.world == null or not bool(Game.world.is_ready)) and Time.get_ticks_msec() - t0 < 900000:
		await get_tree().process_frame
	var w: Node = Game.world
	if w == null or not bool(w.is_ready):
		printerr("STILLS wreck: the world did not load")
		return false
	(w.get(&"ui") as CanvasLayer).visible = false
	var debug: Node = w.get_node_or_null(^"Debug")
	if debug != null:
		(debug as CanvasLayer).visible = false
	(w.get(&"clock_driver") as WorldClockDriver).paused = true
	DebugTools.set_flag(&"invisible", true)
	var clock: WorldClock = Game.session.clock
	clock.set_time(clock.day(), IntroPlayer.SHOT_HOUR)
	Game.session.weather.force(&"clear")
	Game.session.weather.blend = 1.0
	var target: Variant = IntroPlayer.shot_target(card)
	if target == null:
		printerr("STILLS wreck: no lift3_crash_site and no `at` in the world")
		return false
	var pose: Transform3D = IntroPlayer.shot_pose(IntroPlayer.shot_frame(card), target, 0.0, 1.0, w)
	var p: Player = w.player
	p.input_enabled = false
	p.visible = false
	p.global_position = Vector3(pose.origin.x, float(w.call(&"height_at", pose.origin.x, pose.origin.z)) + 0.2, pose.origin.z)
	(w.get(&"terrain") as TerrainManager).update_streaming(p.global_position, true)
	await _wait_streamed(w)
	_viewport(false)
	var cam := Camera3D.new()
	cam.fov = IntroPlayer.SHOT_FOV
	cam.far = 1500.0
	_vp.add_child(cam)
	cam.current = true
	cam.global_transform = pose
	# A few seconds of the fire and smoke's motion before the picture.
	for k: int in 30:
		await get_tree().process_frame
	await _capture("intro_wreck")
	return true


func _wait_streamed(w: Node) -> void:
	var veg: Node = w.get(&"vegetation")
	var t0: int = Time.get_ticks_msec()
	while veg != null and not bool(veg.call(&"is_settled", 2)):
		if Time.get_ticks_msec() - t0 > int(STREAM_WAIT * 1000.0):
			print("STILLS warning: vegetation still streaming after %.0f s" % STREAM_WAIT)
			return
		await get_tree().process_frame
	while veg != null and veg.has_method(&"coarse_pending") and int(veg.call(&"coarse_pending")) > 0:
		if Time.get_ticks_msec() - t0 > int(STREAM_WAIT * 1000.0):
			return
		await get_tree().process_frame


static func _arg(args: PackedStringArray, key: String, default: String) -> String:
	var i: int = args.find(key)
	return args[i + 1] if i >= 0 and i + 1 < args.size() else default
