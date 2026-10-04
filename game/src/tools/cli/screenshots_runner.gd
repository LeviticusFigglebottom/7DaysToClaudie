extends Node
## Screenshot suite (loaded by screenshots.gd): starts a slice game, then for each shot sets the
## time, weather and a camera, waits for streaming to settle and saves a PNG. Used for visual QA
## of terrain, vegetation, lighting, POIs, building and the Hum.
##   make screenshots [SHOTS_ARGS="--only pell_crossing,pond_dusk --settle 6"]

const SHOTS: Array[Dictionary] = [
	{"name": "drop_site_morning", "pos": Vector3(-300, 2.0, 2302), "look": Vector3(-240, 0, 2296), "hour": 7.6, "weather": "clear"},
	{"name": "forest_noon", "pos": Vector3(-205, 1.8, 2230), "look": Vector3(-160, 3, 2200), "hour": 12.5, "weather": "clear"},
	{"name": "pell_crossing_road", "pos": Vector3(-30, 6.0, 2170), "look": Vector3(-60, 0, 2070), "hour": 15.0, "weather": "overcast"},
	{"name": "pell_crossing_street", "pos": Vector3(-45, 1.7, 2068), "look": Vector3(-95, 2, 2064), "hour": 10.0, "weather": "clear"},
	{"name": "pond_dusk", "pos": Vector3(-200, 4.0, 1880), "look": Vector3(-262, 0, 1915), "hour": 19.6, "weather": "mist"},
	{"name": "cliffs_overview", "pos": Vector3(-300, 40.0, 2130), "look": Vector3(-420, 10, 2220), "hour": 16.5, "weather": "clear"},
	{"name": "river_bridge", "pos": Vector3(160, 8.0, 1935), "look": Vector3(185, 0, 1960), "hour": 9.0, "weather": "rain"},
	{"name": "valley_aerial", "pos": Vector3(-150, 140.0, 2420), "look": Vector3(-60, 0, 2050), "hour": 17.5, "weather": "clear"},
	{"name": "night_forest", "pos": Vector3(-240, 1.7, 2290), "look": Vector3(-200, 1.5, 2280), "hour": 23.0, "weather": "clear", "light": true},
	{"name": "base_building", "pos": Vector3(-272, 2.2, 2304), "look": Vector3(-262, 0.5, 2296), "hour": 11.0, "weather": "clear", "build": true},
	{"name": "diner_interior", "pos": Vector3(-49, 1.75, 2021), "look": Vector3(-60, 1.0, 2018), "hour": 14.0, "weather": "overcast"},
	{"name": "first_person_axe", "pos": Vector3(-286, 0.0, 2300), "look": Vector3(-270, 1.2, 2296), "hour": 11.0, "weather": "clear", "fp": "stone_axe"},
	{"name": "hollow_closeup", "pos": Vector3(-286, 1.6, 2300), "look": Vector3(-283, 1.2, 2299), "hour": 10.0, "weather": "overcast", "enemy": "hollow"},
	{"name": "hum_night", "pos": Vector3(-272, 2.2, 2304), "look": Vector3(-262, 0.5, 2296), "hour": 22.5, "weather": "clear", "hum": true, "light": true},
]

var _out: String = "res://../build/screenshots"
var _settle: float = 4.0
var _only: PackedStringArray = []


func _ready() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	for i: int in args.size():
		match args[i]:
			"--out":
				_out = args[i + 1]
			"--settle":
				_settle = float(args[i + 1])
			"--only":
				_only = args[i + 1].split(",")
	DirAccess.make_dir_recursive_absolute(_out)
	_run.call_deferred()


func _wait(s: float) -> void:
	var end: int = Time.get_ticks_msec() + int(s * 1000.0)
	while Time.get_ticks_msec() < end:
		await get_tree().process_frame


## Waits (up to 4 min) until the vegetation around the player has streamed in.
func _wait_streamed(w: Node) -> void:
	var veg: Node = w.get(&"vegetation")
	var t0: int = Time.get_ticks_msec()
	while veg != null and not bool(veg.call(&"is_settled")):
		if Time.get_ticks_msec() - t0 > 240000:
			print("SHOT warning: vegetation still streaming after 240 s")
			return
		await get_tree().process_frame


func _run() -> void:
	var game: Node = get_node("/root/Game")
	game.call(&"start_new_game", {"game_mode": "slice", "skip_intro": true, "slot": "screens"})
	var t0: int = Time.get_ticks_msec()
	while (game.get(&"world") == null or not bool(game.world.is_ready)) and Time.get_ticks_msec() - t0 < 300000:
		await get_tree().process_frame
	var w: Node = game.world
	if w == null:
		printerr("SHOT world did not load")
		get_tree().quit(1)
		return
	(w.get(&"ui") as CanvasLayer).visible = false
	var debug: Node = w.get_node_or_null(^"Debug")
	if debug != null:
		(debug as CanvasLayer).visible = false
	var cam := Camera3D.new()
	cam.far = 4000.0
	cam.fov = 70.0
	w.add_child(cam)
	cam.make_current()
	var p: Player = w.player
	p.input_enabled = false
	for shot: Dictionary in SHOTS:
		if not _only.is_empty() and not _only.has(str(shot["name"])):
			continue
		await _shoot(w, cam, p, shot)
	print("SHOT done in %.1fs" % ((Time.get_ticks_msec() - t0) / 1000.0))
	get_tree().quit(0)


func _shoot(w: Node, cam: Camera3D, p: Player, shot: Dictionary) -> void:
	var pos: Vector3 = shot["pos"]
	var look: Vector3 = shot["look"]
	var ground: float = w.call(&"height_at", pos.x, pos.z)
	pos.y += ground
	look.y += w.call(&"height_at", look.x, look.z)
	# The player stands at the camera (streaming, AI and vegetation follow the player).
	p.global_position = Vector3(pos.x, ground + 0.2, pos.z)
	var clock: WorldClock = Game.session.clock
	clock.set_time(clock.day(), float(shot["hour"]))
	Game.session.weather.force(StringName(str(shot["weather"])))
	Game.session.weather.blend = 1.0
	Game.session.weather.current = StringName(str(shot["weather"]))
	(w.get(&"terrain") as TerrainManager).update_streaming(p.global_position, true)
	if bool(shot.get("build", false)) or bool(shot.get("hum", false)):
		_build_scene(w, look)
	if bool(shot.get("hum", false)):
		var ai: Node = w.get(&"ai")
		for i: int in 8:
			var a: float = TAU * float(i) / 8.0
			var q: Vector3 = look + Vector3(cos(a), 0, sin(a)) * (9.0 + float(i % 3) * 3.0)
			q.y = w.call(&"height_at", q.x, q.z) + 0.2
			ai.call(&"spawn", [&"hollow", &"hollow", &"lurcher", &"hollow"][i % 4], q, {"target": look})
	if bool(shot.get("light", false)):
		var l := OmniLight3D.new()
		l.light_color = Color(1.0, 0.72, 0.42)
		l.light_energy = 1.6
		l.omni_range = 9.0
		l.shadow_enabled = true
		cam.add_child(l)
		l.position = Vector3(0.3, -0.3, -0.5)
	if shot.has("enemy"):
		# A dormant body standing at the look point, facing the camera (character model QA).
		var at := Vector3(look.x, w.call(&"height_at", look.x, look.z), look.z)
		var yaw: float = atan2(pos.x - at.x, pos.z - at.z)
		w.get(&"ai").call(&"spawn", StringName(str(shot["enemy"])), at, {"yaw": yaw, "pose": "stand", "sleeper": "qa", "id": "qa:%s" % shot["name"]})
	cam.global_position = pos
	cam.look_at(look, Vector3.UP)
	if shot.has("fp"):
		_hold_item(p, StringName(str(shot["fp"])), look)
		p.camera.make_current()
	await _wait_streamed(w)
	await _wait(_settle)
	var img: Image = get_viewport().get_texture().get_image()
	var path: String = _out.path_join("%s.png" % shot["name"])
	img.save_png(path)
	print("SHOT %s" % path)
	for c: Node in cam.get_children():
		c.queue_free()
	cam.make_current()
	Game.local_player().equipped_slot = -1


## Equips an item in toolbelt slot 0 and turns the player (camera) toward `look`.
func _hold_item(p: Player, item: StringName, look: Vector3) -> void:
	var ps: PlayerState = Game.local_player()
	ps.inventory.add_item(item, 1)
	ps.toolbelt[0] = item
	ps.equipped_slot = 0
	var dir: Vector3 = look - p.camera.global_position
	p.rotation.y = atan2(-dir.x, -dir.z)


var _built: bool = false


## A small log wall, a lean-to and a lit campfire in front of the camera.
func _build_scene(w: Node, at: Vector3) -> void:
	if _built:
		return
	_built = true
	var game: Node = get_node("/root/Game")
	var ps: PlayerState = Game.local_player()
	ps.inventory.add_item(&"log", 2)
	for k: Variant in {"stone": 12, "stick": 30, "leaf_bundle": 12, "cordage": 4}.keys():
		ps.inventory.add_item(StringName(str(k)), {"stone": 12, "stick": 30, "leaf_bundle": 12, "cordage": 4}[k])
	var base: Vector3 = at + Vector3(0, 0, -3.0)
	base.y = w.call(&"height_at", base.x, base.z) + LogSnapper.RADIUS
	var xf := Transform3D(Basis(), base)
	for i: int in 5:
		ps.inventory.add_item(&"log", 1)
		var q: Quaternion = xf.basis.get_rotation_quaternion()
		game.call(&"execute", &"build.place_log", {"pos": [xf.origin.x, xf.origin.y, xf.origin.z], "rot": [q.x, q.y, q.z, q.w]})
		xf = Transform3D(xf.basis, xf.origin + Vector3.UP * LogSnapper.STACK)
	var c: Vector3 = at + Vector3(2.0, 0, 1.0)
	c.y = w.call(&"height_at", c.x, c.z)
	var r: Dictionary = game.call(&"execute", &"build.place_blueprint", {"blueprint": "campfire", "pos": [c.x, c.y, c.z], "yaw": 0.0})
	if r.get("ok", false):
		game.call(&"execute", &"build.deliver", {"site": r["site"]})
	var l: Vector3 = at + Vector3(-2.5, 0, 0.5)
	l.y = w.call(&"height_at", l.x, l.z)
	var r2: Dictionary = game.call(&"execute", &"build.place_blueprint", {"blueprint": "lean_to", "pos": [l.x, l.y, l.z], "yaw": 0.6})
	if r2.get("ok", false):
		game.call(&"execute", &"build.deliver", {"site": r2["site"]})
	var b: Node = w.get(&"building")
	for piece: StructurePiece in b.call(&"pieces_in_radius", c, 2.0):
		if piece.provides("light"):
			piece.set_lit(true)
