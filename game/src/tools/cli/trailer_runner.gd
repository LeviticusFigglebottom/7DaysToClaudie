extends Node
## Plays one trailer shot (data/trailer, TrailerShotDef) for Movie Maker: --shot <id>.
##
## Movie Maker records from launch and can't start later, so everything before the shot (the world
## load and the streaming wait, drawn with the root's 3D off so those frames cost nothing, the
## shader warm-up) is recorded too, and tools/trailer_shot.sh cuts it away: the last frame before
## the shot is a solid MARKER colour, and the shot is the frame_count() frames after it (the audio
## is cut at the same frame). Under --fixed-fps every frame is 1/30 s of game time however long it
## takes to draw, so the camera, the clock and the AI play at film speed.
##   --preview --out <dir>   without Movie Maker (still under --fixed-fps): saves the first,
##                           middle and last frames of the shot as <id>_0..2.png (framing checks)

## The frame before the shot, found by tools/trailer_shot.sh (pure magenta never occurs in the game).
const MARKER: Color = Color(1.0, 0.0, 1.0)
const FPS: int = 30
## Frames drawn at the first camera pose before the shot: shadows, the ubershader cache, the sky.
const WARM: int = 20
## Seconds the world waits at most for the forest round the camera to stream in.
const STREAM_WAIT: float = 300.0

var _def: TrailerShotDef
var _w: Node
var _cam: Camera3D
var _ground: float = 0.0
var _preview_out: String = ""


func _ready() -> void:
	_run.call_deferred()


func _run() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var id: String = _arg(args, "--shot", "")
	if args.has("--list"):
		for d: TrailerShotDef in Content.all(&"trailer_shot"):
			print("TRAILER shot %s %.1f s" % [d.id, d.dur])
		get_tree().quit(0)
		return
	_def = Content.get_def(&"trailer_shot", StringName(id)) as TrailerShotDef
	if _def == null:
		printerr("TRAILER unknown shot '%s' (make trailer-shots lists them)" % id)
		get_tree().quit(2)
		return
	if args.has("--preview"):
		_preview_out = _arg(args, "--out", "")
		DirAccess.make_dir_recursive_absolute(_preview_out)
	var t0: int = Time.get_ticks_msec()
	var ok: bool = await _shot()
	print("TRAILER %s %s in %.1fs" % [id, "done" if ok else "FAILED", (Time.get_ticks_msec() - t0) / 1000.0])
	get_tree().quit(0 if ok else 1)


func _shot() -> bool:
	get_viewport().disable_3d = true
	var marker := _marker_layer()
	Game.start_new_game({"game_mode": "survival", "seed": 4471, "skip_intro": true, "slot": "qa_trailer", "poi_ring": false})
	var t0: int = Time.get_ticks_msec()
	while (Game.world == null or not bool(Game.world.is_ready)) and Time.get_ticks_msec() - t0 < 900000:
		await get_tree().process_frame
	_w = Game.world
	if _w == null or not bool(_w.is_ready):
		printerr("TRAILER the world did not load")
		return false
	print("TRAILER world loaded in %.1fs" % ((Time.get_ticks_msec() - t0) / 1000.0))
	(_w.get(&"ui") as CanvasLayer).visible = _def.hud
	var debug: Node = _w.get_node_or_null(^"Debug")
	if debug != null:
		(debug as CanvasLayer).visible = false
	var driver: WorldClockDriver = _w.get(&"clock_driver")
	driver.paused = true
	DebugTools.set_flag(&"invisible", true)
	DebugTools.set_flag(&"god_mode", true)
	Game.session.clock.set_time(_def.day, _def.hour)
	_weather(_def.weather)
	Settings.brightness = _def.exposure
	_ground = float(_w.call(&"height_at", _def.anchor.x, _def.anchor.y))
	# For authoring: how the keys sit on the ground (a key below the ground under it films the
	# terrain's underside).
	for i: int in _def.keys.size():
		var at: Vector3 = _abs(_def.keys[i]["pos"], _def.terrain_follow)
		print("TRAILER key %d at %s, %.1f m above the ground (anchor ground %.1f)" % [i, at.round(),
			at.y - float(_w.call(&"height_at", at.x, at.z)), _ground])
	var p: Player = _w.player
	p.input_enabled = false
	p.visible = false
	# Only its position matters (the streaming focus, what the Hum heads for); left running, the
	# body falls through ground whose collision hasn't streamed in under a moving camera.
	p.process_mode = Node.PROCESS_MODE_DISABLED
	_cam = Camera3D.new()
	_cam.far = 2500.0
	add_child(_cam)
	_cam.current = true
	_pose(-_def.lead)
	(_w.get(&"terrain") as TerrainManager).update_streaming(p.global_position, true)
	await _wait_streamed()
	get_viewport().disable_3d = false
	for k: int in (3 if _preview_out != "" else WARM):
		await get_tree().process_frame
	if _preview_out != "":
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(_preview_out.path_join("%s_warm.png" % _def.id))
		for cl: Node in get_tree().root.find_children("*", "CanvasLayer", true, false):
			if (cl as CanvasLayer).visible:
				print("TRAILER canvas layer %s (layer %d)" % [cl.get_path(), (cl as CanvasLayer).layer])
	# The timeline: -lead .. 0 plays unrecorded (trimmed), the marker frame, then the shot.
	var t: float = -_def.lead
	var dt: float = 1.0 / float(FPS)
	var next_action: int = 0
	var n: int = _def.frame_count(FPS)
	var lead_frames: int = roundi(_def.lead * FPS)
	var shot_t0: int = 0
	var preview_at: PackedInt32Array = [0, n / 2, n - 1]
	for f: int in range(-lead_frames - 1, n):
		t = float(f) * dt
		while next_action < _def.actions.size() and float(_def.actions[next_action]["t"]) <= t + 0.0001:
			_act(_def.actions[next_action])
			next_action += 1
		marker.visible = f == -1
		_pose(t)
		if f != -1:
			_clock(driver, dt)
		if f == 0:
			shot_t0 = Time.get_ticks_msec()
			print("TRAILER recording %d frames" % n)
		if _preview_out != "":
			# A preview draws 3D only for its three pictures (and the two frames before each, for
			# the shadows): everything still plays every frame, at a fraction of the cost.
			var draw: bool = false
			for at: int in preview_at:
				draw = draw or (f >= at - 2 and f <= at)
			get_viewport().disable_3d = not draw
		await RenderingServer.frame_post_draw
		if _preview_out != "" and preview_at.has(f):
			var img: Image = get_viewport().get_texture().get_image()
			img.convert(Image.FORMAT_RGB8)
			img.save_png(_preview_out.path_join("%s_%d.png" % [_def.id, preview_at.find(f)]))
			var env: Environment = _cam.get_world_3d().environment if _cam.get_world_3d() != null else null
			print("TRAILER preview %d: camera %s, hour %.2f, exposure %s, ambient %s, 3d off %s" % [f, _cam.global_position.round(),
				Game.session.clock.hour_f(), env.tonemap_exposure if env != null else -1.0,
				env.ambient_light_energy if env != null else -1.0, get_viewport().disable_3d])
	if _preview_out == "":
		var spf: float = (Time.get_ticks_msec() - shot_t0) / 1000.0 / float(n)
		print("TRAILER %s %d frames %.2f s/frame" % [_def.id, n, spf])
	return true


## Camera at shot time t (anchor-relative keys made absolute); the hidden player follows the
## camera's ground point unless the shot pins it (`player`), so the forest streams round the lens.
func _pose(t: float) -> void:
	var c: Dictionary = _def.camera_at(maxf(t, 0.0))
	var pos: Vector3 = _abs(c["pos"], _def.terrain_follow)
	var look: Vector3 = _abs(c["look"], false)
	_cam.fov = float(c["fov"])
	if not pos.is_equal_approx(look):
		_cam.global_transform = Transform3D(Basis.looking_at(look - pos, Vector3.UP), pos)
	var p: Player = _w.player
	var at: Vector3 = _abs(_def.player, false) if _def.player_fixed else pos
	p.global_position = Vector3(at.x, float(_w.call(&"height_at", at.x, at.z)) + 0.1, at.z)


func _abs(off: Vector3, follow: bool) -> Vector3:
	var x: float = _def.anchor.x + off.x
	var z: float = _def.anchor.y + off.z
	var base: float = float(_w.call(&"height_at", x, z)) if follow else _ground
	return Vector3(x, base + off.y, z)


## The clock: a time-lapse spreads hour .. hour_end over the recorded frames; otherwise it runs
## at the game's own rate (its events fire: the Hum's waves, dawn).
func _clock(driver: WorldClockDriver, dt: float) -> void:
	var minutes: float
	if _def.hour_end >= 0.0:
		minutes = (_def.hour_end - _def.hour) * 60.0 * dt / (_def.dur + _def.tail)
	else:
		minutes = dt * Game.session.clock.minutes_per_real_second() * Game.session.clock.time_scale
	driver.advance(minutes)


func _act(a: Dictionary) -> void:
	match str(a["do"]):
		"spawn":
			_spawn(a)
		"hum":
			# As the debug menu's Start the Hum: the clock jumps to the next Hum night, just before
			# it starts, and runs into it.
			var c: WorldClock = Game.session.clock
			var d: int = c.next_horde_day(c.day())
			if d != c.day() or c.hour_f() < 21.9:
				c.set_time(d, 21.9)
			var driver: WorldClockDriver = _w.get(&"clock_driver")
			driver.advance(10.0)
			if float(a["until"]) >= 0.0:
				driver.advance(fposmod(float(a["until"]) - c.hour_f(), 24.0) * 60.0)
			print("TRAILER the Hum: active=%s" % c.is_horde_active())
		"command":
			var args: Dictionary = {}
			for k: Variant in (a["args"] as Dictionary).keys():
				var v: Variant = a["args"][k]
				if v is Array and (v as Array).size() == 3:
					var vec := Vector3(float(v[0]), float(v[1]), float(v[2]))
					v = _abs(vec, true) if str(k).ends_with("pos") else vec
				args[k] = v
			var r: Dictionary = Game.execute(StringName(str(a["command"])), args)
			print("TRAILER %s -> %s" % [a["command"], r])
		"weather":
			_weather(a["weather"])
		"flag":
			DebugTools.set_flag(StringName(str(a["flag"])), bool(a["on"]))


func _spawn(a: Dictionary) -> void:
	var ai: Node = _w.get(&"ai")
	var rng := RandomNumberGenerator.new()
	rng.seed = Ids.hash64("trailer:%s:%s" % [_def.id, a["t"]])
	var at: Vector3 = a["at"]
	for i: int in int(a["count"]):
		var off := Vector3(rng.randf_range(-1.0, 1.0), 0.0, rng.randf_range(-1.0, 1.0)) * float(a["spread"])
		var pos: Vector3 = _abs(at + off, true)
		var opts: Dictionary = {"authored": true}
		if bool(a["horde"]):
			opts["horde_sector"] = 0
		elif a["target"] != null:
			opts["target"] = _abs(a["target"], true)
		ai.call(&"spawn", a["enemy"], pos + Vector3.UP * 0.3, opts)


func _weather(id: StringName) -> void:
	Game.session.weather.force(id)
	Game.session.weather.blend = 1.0
	Events.weather_changed.emit(id)


## A full-screen MARKER rectangle above everything, shown for one frame.
func _marker_layer() -> CanvasItem:
	var layer := CanvasLayer.new()
	layer.layer = 128
	add_child(layer)
	var rect := ColorRect.new()
	rect.color = MARKER
	rect.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	rect.visible = false
	layer.add_child(rect)
	return rect


func _wait_streamed() -> void:
	var veg: Node = _w.get(&"vegetation")
	var t0: int = Time.get_ticks_msec()
	while veg != null and not bool(veg.call(&"is_settled", 2)):
		if Time.get_ticks_msec() - t0 > int(STREAM_WAIT * 1000.0):
			print("TRAILER warning: vegetation still streaming after %.0f s" % STREAM_WAIT)
			return
		await get_tree().process_frame
	while veg != null and veg.has_method(&"coarse_pending") and int(veg.call(&"coarse_pending")) > 0:
		if Time.get_ticks_msec() - t0 > int(STREAM_WAIT * 1000.0):
			return
		await get_tree().process_frame
	print("TRAILER streamed in %.1fs" % ((Time.get_ticks_msec() - t0) / 1000.0))


static func _arg(args: PackedStringArray, key: String, default: String) -> String:
	var i: int = args.find(key)
	return args[i + 1] if i >= 0 and i + 1 < args.size() else default
