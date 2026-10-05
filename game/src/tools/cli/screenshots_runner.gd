extends Node
## Screenshot suite (loaded by screenshots.gd): starts a slice game, then for each shot sets the
## time, weather and a camera, waits for streaming to settle and saves a PNG. Used for visual QA
## of terrain, vegetation, lighting, POIs, building and the Hum.
##   make screenshots [SHOTS_ARGS="--only pell_crossing,pond_dusk --settle 6"]

const SHOTS: Array[Dictionary] = [
	{"name": "drop_site_morning", "pos": Vector3(-300, 2.0, 2302), "look": Vector3(-240, 0, 2296), "hour": 7.6, "weather": "clear"},
	{"name": "forest_noon", "pos": Vector3(-201, 1.8, 2227), "look": Vector3(-160, 3, 2200), "hour": 12.5, "weather": "clear"},
	{"name": "pell_crossing_road", "pos": Vector3(-30, 6.0, 2170), "look": Vector3(-60, 0, 2070), "hour": 15.0, "weather": "overcast"},
	{"name": "pell_crossing_street", "pos": Vector3(-45, 1.7, 2068), "look": Vector3(-95, 2, 2064), "hour": 10.0, "weather": "clear"},
	{"name": "pond_dusk", "pos": Vector3(-200, 4.0, 1880), "look": Vector3(-262, 0, 1915), "hour": 19.6, "weather": "mist"},
	{"name": "cliffs_overview", "pos": Vector3(-300, 40.0, 2130), "look": Vector3(-420, 10, 2220), "hour": 16.5, "weather": "clear"},
	{"name": "river_bridge", "pos": Vector3(160, 8.0, 1935), "look": Vector3(185, 0, 1960), "hour": 9.0, "weather": "rain"},
	{"name": "valley_aerial", "pos": Vector3(-150, 140.0, 2420), "look": Vector3(-60, 0, 2050), "hour": 17.5, "weather": "clear"},
	{"name": "night_forest", "pos": Vector3(-240, 1.7, 2290), "look": Vector3(-200, 1.5, 2280), "hour": 23.0, "weather": "clear", "light": true},
	{"name": "base_building", "pos": Vector3(-296, 2.2, 2302), "look": Vector3(-286, 0.5, 2294), "hour": 11.0, "weather": "clear", "build": true},
	{"name": "diner_interior", "pos": Vector3(-49, 1.75, 2021), "look": Vector3(-60, 1.0, 2018), "hour": 14.0, "weather": "overcast"},
	{"name": "first_person_axe", "pos": Vector3(-286, 0.0, 2300), "look": Vector3(-276, 0.2, 2297), "hour": 11.0, "weather": "clear", "fp": "stone_axe"},
	{"name": "hollow_closeup", "pos": Vector3(-287, 1.55, 2300), "look": Vector3(-285, 1.1, 2299.5), "hour": 11.0, "weather": "overcast", "enemy": "hollow", "fov": 45.0},
	{"name": "hum_night", "pos": Vector3(-296, 2.2, 2302), "look": Vector3(-286, 0.5, 2294), "hour": 22.5, "weather": "clear", "hum": true, "light": true},
	{"name": "special_hollowed", "pos": Vector3(-300, 1.6, 2297), "look": Vector3(-300, 1.1, 2290), "hour": 12.0, "weather": "overcast",
		"lineup": [["blister", -2.3, "normal"], ["husk", 0.0, "seeded"], ["rammer", 2.5, "bloomed"]], "fov": 48.0, "cam_height": 1.55, "look_height": 1.15},
	{"name": "supply_drop", "pos": Vector3(-306, 1.7, 2312), "look": Vector3(-296, 4.0, 2302), "hour": 17.8, "weather": "clear", "drop": true, "settle": 10.0},
	{"name": "record_tab", "pos": Vector3(-296, 2.2, 2302), "look": Vector3(-286, 0.5, 2294), "hour": 11.0, "weather": "clear", "ui": "record"},
]

var _out: String = "res://../build/screenshots"
## Nodes a shot spawned for itself (QA enemies, the QA drop), removed after the shot.
var _temp: Array[Node] = []
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


## Waits (up to 4 min) until the vegetation within two chunks of the camera has streamed in
## (software rendering leaves the scatter workers little CPU; the far impostors cover the rest).
func _wait_streamed(w: Node) -> void:
	var veg: Node = w.get(&"vegetation")
	var t0: int = Time.get_ticks_msec()
	while veg != null and not bool(veg.call(&"is_settled", 2)):
		if Time.get_ticks_msec() - t0 > 240000:
			print("SHOT warning: vegetation still streaming after 240 s (%s)" % veg.call(&"settle_report", 2))
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
			var he: Node = ai.call(&"spawn", [&"hollow", &"hollow", &"lurcher", &"hollow"][i % 4], q, {"target": look})
			if he != null:
				_temp.append(he)
	if bool(shot.get("light", false)):
		var l := OmniLight3D.new()
		l.light_color = Color(1.0, 0.72, 0.42)
		l.light_energy = 1.6
		l.omni_range = 9.0
		l.shadow_enabled = true
		cam.add_child(l)
		l.position = Vector3(0.3, -0.3, -0.5)
	if shot.has("lineup"):
		# Special Hollowed side by side across the frame, awake and facing the camera, each at the
		# infected tier given (normal / seeded / bloomed).
		var c := Vector3(look.x, w.call(&"height_at", look.x, look.z), look.z)
		var side: Vector3 = (look - pos).cross(Vector3.UP).normalized()
		for entry: Array in shot["lineup"]:
			var at: Vector3 = c + side * float(entry[1])
			at.y = w.call(&"height_at", at.x, at.z)
			var yaw: float = atan2(pos.x - at.x, pos.z - at.z)
			var e: Node = w.get(&"ai").call(&"spawn", StringName(str(entry[0])), at, {"yaw": yaw, "authored": true,
				"tier": str(entry[2]), "id": "qa:%s:%s" % [shot["name"], entry[0]]})
			if e != null:
				e.set_physics_process(false)
				(e.get(&"visual") as EnemyVisual).play(&"idle")
				_temp.append(e)
		pos.y = c.y + float(shot.get("cam_height", 1.5))
		look.y = c.y + float(shot.get("look_height", 1.1))
	if bool(shot.get("drop", false)):
		var drops: SupplyDrops = w.get(&"supply_drops") as SupplyDrops
		if drops != null:
			var g := Vector3(look.x, w.call(&"height_at", look.x, look.z), look.z)
			_temp.append(drops.call(&"_spawn", &"qa_drop", g, 3, true))
			drops.drops.erase(&"qa_drop")
	if shot.has("ui"):
		_show_record(w)
	if shot.has("enemy"):
		# An awake body at the look point facing the camera, its brain paused so it holds its
		# idle loop in place; framed from its own feet so slopes don't tilt the shot.
		var at := Vector3(look.x, w.call(&"height_at", look.x, look.z), look.z)
		var yaw: float = atan2(pos.x - at.x, pos.z - at.z)
		var e: Node = w.get(&"ai").call(&"spawn", StringName(str(shot["enemy"])), at, {"yaw": yaw, "id": "qa:%s" % shot["name"]})
		if e != null:
			e.set_physics_process(false)
			(e.get(&"visual") as EnemyVisual).play(&"idle")
			_temp.append(e)
		pos.y = at.y + float(shot.get("cam_height", 1.45))
		look.y = at.y + float(shot.get("look_height", 1.15))
	cam.global_position = pos
	cam.look_at(look, Vector3.UP)
	cam.fov = float(shot.get("fov", 70.0))
	# The player's first-person arms sit where the QA camera is; show them only in FP shots.
	var vm: Node3D = p.get_node_or_null(^"Head/Camera3D/ViewModel") as Node3D
	if vm != null:
		vm.visible = shot.has("fp")
	if shot.has("fp"):
		_hold_item(p, StringName(str(shot["fp"])), look)
		p.camera.make_current()
	await _wait_streamed(w)
	await _wait(float(shot.get("settle", _settle)))
	var img: Image = get_viewport().get_texture().get_image()
	var path: String = _out.path_join("%s.png" % shot["name"])
	img.save_png(path)
	print("SHOT %s" % path)
	if shot.has("ui"):
		var ui: GameUI = w.get(&"ui") as GameUI
		ui.manual.close()
		ui.visible = false
	for n: Node in _temp:
		if is_instance_valid(n):
			if n is Enemy:
				w.get(&"ai").call(&"despawn", n)
			else:
				n.queue_free()
	_temp.clear()
	for c: Node in cam.get_children():
		c.queue_free()
	cam.make_current()
	Game.local_player().equipped_slot = -1


## The Field Manual open on the Record tab for a character a few levels in (perks bought, points
## left), over the game view.
func _show_record(w: Node) -> void:
	var ps: PlayerState = Game.local_player()
	var pr: Progression = ps.progression
	pr.add_xp(2600)
	pr.skill_points += 3
	for a: StringName in [&"sinew", &"sinew", &"keen"]:
		pr.raise_attribute(a)
	for pk: StringName in [&"timberwright", &"packhorse", &"scavenger"]:
		pr.buy_perk(pk)
	Game.session.stats["zombies_killed"] = 23
	Game.session.stats["hums_survived"] = 1
	var ui: GameUI = w.get(&"ui") as GameUI
	ui.visible = true
	ui.manual.open("record")
	ui.manual.call(&"_select", Content.get_def(&"perk", &"timberwright"))


## Equips an item in toolbelt slot 0 and turns the player (camera) toward `look`.
func _hold_item(p: Player, item: StringName, look: Vector3) -> void:
	var ps: PlayerState = Game.local_player()
	# Earlier shots may have left logs on the shoulder (carry pose); empty hands for this one.
	ps.inventory.remove(&"log", ps.inventory.count_of(&"log"))
	ps.inventory.add_item(item, 1)
	ps.toolbelt[0] = item
	ps.equipped_slot = 0
	var dir: Vector3 = look - p.camera.global_position
	p.rotation.y = atan2(-dir.x, -dir.z)
	p.head.rotation.x = atan2(dir.y, Vector2(dir.x, dir.z).length())


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
	# Building has a reach limit: stand beside the spot while the scene goes up.
	var p: Player = w.get(&"player")
	var stand: Vector3 = p.global_position
	p.global_position = Vector3(at.x - 1.0, w.call(&"height_at", at.x - 1.0, at.z - 1.0) + 0.2, at.z - 1.0)
	var base: Vector3 = at + Vector3(0, 0, -3.0)
	base.y = w.call(&"height_at", base.x, base.z) + LogSnapper.RADIUS
	var xf := Transform3D(Basis(), base)
	for i: int in 5:
		ps.inventory.add_item(&"log", 1)
		var q: Quaternion = xf.basis.get_rotation_quaternion()
		var rl: Dictionary = game.call(&"execute", &"build.place_log", {"pos": [xf.origin.x, xf.origin.y, xf.origin.z], "rot": [q.x, q.y, q.z, q.w]})
		if not bool(rl.get("ok", false)):
			print("SHOT build: log %d failed: %s" % [i, rl.get("error", "?")])
		xf = Transform3D(xf.basis, xf.origin + Vector3.UP * LogSnapper.STACK)
	var c: Vector3 = at + Vector3(2.0, 0, 1.0)
	c.y = w.call(&"height_at", c.x, c.z)
	var r: Dictionary = game.call(&"execute", &"build.place_blueprint", {"blueprint": "campfire", "pos": [c.x, c.y, c.z], "yaw": 0.0})
	if r.get("ok", false):
		var rd: Dictionary = game.call(&"execute", &"build.deliver", {"site": r["site"]})
		print("SHOT build: campfire %s" % ("built" if bool(rd.get("complete", false)) else "incomplete: %s" % rd))
	else:
		print("SHOT build: campfire not placed: %s" % r.get("error", "?"))
	var l: Vector3 = at + Vector3(-2.5, 0, 0.5)
	l.y = w.call(&"height_at", l.x, l.z)
	var r2: Dictionary = game.call(&"execute", &"build.place_blueprint", {"blueprint": "lean_to", "pos": [l.x, l.y, l.z], "yaw": 0.6})
	if r2.get("ok", false):
		var rd2: Dictionary = game.call(&"execute", &"build.deliver", {"site": r2["site"]})
		print("SHOT build: lean-to %s" % ("built" if bool(rd2.get("complete", false)) else "incomplete: %s" % rd2))
	else:
		print("SHOT build: lean-to not placed: %s" % r2.get("error", "?"))
	var b: Node = w.get(&"building")
	for piece: StructurePiece in b.call(&"pieces_in_radius", c, 2.0):
		if piece.provides("light"):
			piece.set_lit(true)
	p.global_position = stand
