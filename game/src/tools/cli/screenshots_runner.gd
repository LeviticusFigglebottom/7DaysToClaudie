extends Node
## Screenshot suite (loaded by screenshots.gd): starts a slice game, then for each shot sets the
## time, weather and a camera, waits for streaming to settle and saves a PNG. Used for visual QA
## of terrain, vegetation, lighting, POIs, building and the Hum.
##   make screenshots [SHOTS_ARGS="--only pell_crossing,pond_dusk --settle 6"]

const SHOTS: Array[Dictionary] = [
	{"name": "drop_site_morning", "pos": Vector3(-300, 2.0, 2302), "look": Vector3(-240, 0, 2296), "hour": 7.6, "weather": "clear"},
	{"name": "forest_noon", "pos": Vector3(-201, 1.8, 2227), "look": Vector3(-160, 3, 2200), "hour": 12.5, "weather": "clear"},
	{"name": "forest_floor", "pos": Vector3(-212, 1.7, 2236), "look": Vector3(-196, 0.0, 2224), "hour": 15.0, "weather": "overcast"},
	{"name": "pell_crossing_road", "pos": Vector3(-30, 6.0, 2170), "look": Vector3(-60, 0, 2070), "hour": 15.0, "weather": "overcast"},
	{"name": "pell_crossing_street", "pos": Vector3(-45, 1.7, 2068), "look": Vector3(-95, 2, 2064), "hour": 10.0, "weather": "clear"},
	{"name": "pond_dusk", "pos": Vector3(-200, 4.0, 1880), "look": Vector3(-262, 0, 1915), "hour": 19.6, "weather": "mist"},
	{"name": "pond_noon", "pos": Vector3(-204, 2.5, 1884), "look": Vector3(-262, 0, 1915), "hour": 12.5, "weather": "clear"},
	{"name": "cliffs_overview", "pos": Vector3(-300, 40.0, 2130), "look": Vector3(-420, 10, 2220), "hour": 16.5, "weather": "clear"},
	{"name": "river_bridge", "pos": Vector3(160, 8.0, 1935), "look": Vector3(185, 0, 1960), "hour": 9.0, "weather": "rain"},
	{"name": "river_noon", "pos": Vector3(150, 1.7, 2075), "look": Vector3(118, 0.0, 2100), "hour": 13.0, "weather": "clear"},
	{"name": "valley_aerial", "pos": Vector3(-150, 140.0, 2420), "look": Vector3(-60, 0, 2050), "hour": 17.5, "weather": "clear"},
	{"name": "night_forest", "pos": Vector3(-240, 1.7, 2290), "look": Vector3(-200, 1.5, 2280), "hour": 23.0, "weather": "clear", "light": true},
	{"name": "base_building", "pos": Vector3(-296, 2.2, 2302), "look": Vector3(-286, 0.5, 2294), "hour": 11.0, "weather": "clear", "build": true},
	{"name": "diner_interior", "pos": Vector3(-49, 1.75, 2021), "look": Vector3(-60, 1.0, 2018), "hour": 14.0, "weather": "overcast"},
	{"name": "first_person_axe", "pos": Vector3(-286, 0.0, 2300), "look": Vector3(-276, 0.2, 2297), "hour": 11.0, "weather": "clear", "fp": "stone_axe"},
	{"name": "hollow_closeup", "pos": Vector3(-287, 1.55, 2300), "look": Vector3(-285, 1.1, 2299.5), "hour": 11.0, "weather": "overcast", "enemy": "hollow", "fov": 45.0,
		"tier": "normal"},
	{"name": "hum_night", "pos": Vector3(-296, 2.2, 2302), "look": Vector3(-286, 0.5, 2294), "hour": 22.5, "weather": "clear", "hum": true, "light": true},
	{"name": "special_hollowed", "pos": Vector3(-300, 1.6, 2297), "look": Vector3(-300, 1.1, 2290), "hour": 12.0, "weather": "overcast",
		"lineup": [["blister", -2.3, "normal"], ["husk", 0.0, "seeded"], ["rammer", 2.5, "bloomed"]], "fov": 48.0, "cam_height": 1.55, "look_height": 1.15},
	# The specials must read at a distance (ADR-0028): the three and a plain Hollow, 40 m down the path.
	{"name": "special_hollowed_40m", "pos": Vector3(-288, 1.7, 2300), "look": Vector3(-248, 1.1, 2298), "hour": 12.0, "weather": "overcast",
		"lineup": [["blister", -3.0, "normal"], ["husk", -1.0, "normal"], ["rammer", 1.2, "normal"], ["hollow", 3.2, "normal"]],
		"fov": 50.0, "cam_height": 1.7, "look_height": 1.0},
	# Who they were (ADR-0028): Hollows dressed by the population of the building named in each
	# entry (the clinic's patients and nurse, St. Ansel's congregation, a Cordon crew, a hunter), and
	# the clinic's waiting room with its own sleepers in place.
	{"name": "population_lineup", "pos": Vector3(-300, 1.6, 2297), "look": Vector3(-300, 1.1, 2290.5), "hour": 12.0, "weather": "overcast",
		"lineup": [["hollow", -3.0, "normal", "tamsin_clinic"], ["hollow", -1.8, "normal", "tamsin_clinic"], ["hollow", -0.6, "normal", "pell_crossing/church"],
			["hollow", 0.6, "normal", "pell_crossing/church"], ["hollow", 1.8, "normal", "cordon_gas"], ["hollow", 3.0, "normal", "trappers_cabin"]],
		"fov": 40.0, "cam_height": 1.5, "look_height": 1.0},
	# At night by torchlight: the Cordon's retroreflective tape throws the light back, and the Bloomed
	# one's veins glow cold.
	{"name": "cordon_torch_night", "pos": Vector3(-300, 1.6, 2297), "look": Vector3(-300, 1.1, 2292.5), "hour": 22.5, "weather": "clear",
		"light": true, "lineup": [["hollow", -0.6, "normal", "cordon_gas"], ["hollow", 0.6, "bloomed", "cordon_gas"]],
		"fov": 50.0, "cam_height": 1.5, "look_height": 1.1},
	{"name": "clinic_waiting", "pos": Vector3(8, 1.6, 2106), "look": Vector3(4, 1.0, 2100), "hour": 11.0, "weather": "overcast", "fov": 80.0,
		"poi_view": {"poi": "tamsin_clinic", "level": 0, "cam": [4.4, 1.5, 9.3], "look": [4.2, 0.75, 13.0], "sleepers": ["waiting_1", "waiting_2", "waiting_3"]}},
	{"name": "supply_drop", "pos": Vector3(-306, 1.7, 2312), "look": Vector3(-296, 4.0, 2302), "hour": 17.8, "weather": "clear", "drop": true, "settle": 10.0},
	{"name": "record_tab", "pos": Vector3(-296, 2.2, 2302), "look": Vector3(-286, 0.5, 2294), "hour": 11.0, "weather": "clear", "ui": "record"},
	{"name": "options_menu", "pos": Vector3(-296, 2.2, 2302), "look": Vector3(-286, 0.5, 2294), "hour": 11.0, "weather": "clear", "ui": "options"},
	{"name": "first_person_torch", "pos": Vector3(-286, 0.0, 2300), "look": Vector3(-276, 0.4, 2297), "hour": 21.8, "weather": "clear", "fp": "torch", "fp_light": true},
	# First person (ADR-0029), where first_person_axe stands: the chop at its contact frame, the
	# tether raised at dusk with its live screen, the spear, a can of beans.
	{"name": "first_person_axe_swing", "pos": Vector3(-286, 0.0, 2300), "look": Vector3(-276, 0.2, 2297), "hour": 11.0, "weather": "clear", "fp": "stone_axe", "fp_action": "fp_chop", "fp_frame": 12},
	{"name": "first_person_tether", "pos": Vector3(-286, 0.0, 2300), "look": Vector3(-276, 0.2, 2297), "hour": 18.6, "weather": "clear", "fp": "stone_axe", "fp_tether": true},
	{"name": "first_person_spear", "pos": Vector3(-286, 0.0, 2300), "look": Vector3(-276, 0.2, 2297), "hour": 11.0, "weather": "clear", "fp": "crude_spear"},
	{"name": "first_person_food", "pos": Vector3(-286, 0.0, 2300), "look": Vector3(-276, 0.2, 2297), "hour": 11.0, "weather": "clear", "fp": "canned_beans"},
	# The Bloom on the land (ADR-0025): the deep wood north-east of the Tamsin, inside and at its
	# edge, by day, at night and on a Hum night; a colonised larch and a cluster of caps up close.
	# Each finds its own clear view near `pos` (_seek_view / _frame_tree), nearby shots back to back.
	{"name": "bloom_zone_day", "pos": Vector3(318, 1.7, 1748), "look": Vector3(342, 0.8, 1722), "hour": 13.0, "weather": "clear",
		"seek": {"r": 20.0, "here": [0.55, 1.0], "ahead": [0.55, 1.0], "clear": 14.0}},
	{"name": "bloom_ground", "pos": Vector3(331, 1.25, 1737), "look": Vector3(332, 0.0, 1733.5), "hour": 12.5, "weather": "clear", "fov": 55.0,
		"frame_tree": "bloom_caps", "frame": [1.3, 0.85, 0.05]},
	{"name": "bloom_bark", "pos": Vector3(330, 1.7, 1730), "look": Vector3(331, 1.0, 1726), "hour": 12.5, "weather": "clear",
		"frame_tree": "hollow_larch", "frame": [2.2, 1.2, 0.85], "fov": 55.0},
	{"name": "bloom_zone_night", "pos": Vector3(318, 1.7, 1748), "look": Vector3(342, 0.8, 1722), "hour": 23.5, "weather": "clear",
		"seek": {"r": 20.0, "here": [0.55, 1.0], "ahead": [0.55, 1.0], "clear": 14.0}},
	{"name": "bloom_hum_night", "pos": Vector3(318, 1.7, 1748), "look": Vector3(342, 0.8, 1722), "hour": 23.5, "weather": "clear", "hum_glow": true,
		"seek": {"r": 20.0, "here": [0.55, 1.0], "ahead": [0.55, 1.0], "clear": 14.0}},
	{"name": "bloom_edge_day", "pos": Vector3(258, 1.7, 1846), "look": Vector3(296, 0.8, 1786), "hour": 15.5, "weather": "clear",
		"seek": {"r": 40.0, "here": [0.0, 0.08], "ahead": [0.3, 1.0], "clear": 14.0}},
	{"name": "bloom_edge_night", "pos": Vector3(258, 1.7, 1846), "look": Vector3(296, 0.8, 1786), "hour": 23.5, "weather": "clear",
		"seek": {"r": 40.0, "here": [0.0, 0.08], "ahead": [0.3, 1.0], "clear": 14.0}},
	# The outskirts (DESIGN §11): Larch Pond Bait & Boat from the shore by its dock (the slip's water
	# under the building, ADR-0024), over the Ashen watch camp's palisade, the campground's entrance.
	{"name": "outskirts_boathouse", "pos": Vector3(-337, 1.8, 1893), "look": Vector3(-324, 1.0, 1905), "hour": 17.4, "weather": "clear"},
	{"name": "outskirts_ashen_camp", "pos": Vector3(409, 6.0, 1764), "look": Vector3(417, 0.5, 1740), "hour": 16.5, "weather": "overcast"},
	{"name": "outskirts_campground", "pos": Vector3(338, 3.0, 1945), "look": Vector3(343, 0.8, 1966), "hour": 10.5, "weather": "clear"},
	# ADR-0030: Larch Street, Pell's Crossing's residential side street of generated houses (different
	# every run), looking north up it from the dead end towards the Grange Road corner.
	# Wildlife (ADR-0027): a band of deer at the forest's edge at dawn, a hare in the brush, crows going up.
	{"name": "deer_meadow_dawn", "pos": Vector3(-163, 1.4, 2156), "look": Vector3(-178, 0.7, 2163), "hour": 7.0, "weather": "clear",
	 "wildlife": "white_tailed_deer", "count": 4, "anims": ["graze", "alert", "graze", "idle"], "fov": 42.0},
	{"name": "hare_brush", "pos": Vector3(-210.5, 0.6, 2235), "look": Vector3(-207, 0.15, 2232), "hour": 17.8, "weather": "clear",
	 "wildlife": "snowshoe_hare", "count": 1, "anims": ["alert"], "fov": 40.0},
	{"name": "birds_lift_off", "pos": Vector3(-143, 1.2, 2117), "look": Vector3(-150, 2.2, 2108), "hour": 9.5, "weather": "overcast",
	 "flock": "crow", "flush_after": 0.9, "fov": 60.0},
	{"name": "larch_street", "pos": Vector3(-69.0, 2.6, 2330.0), "look": Vector3(-84.0, 1.5, 2262.0), "hour": 10.5, "weather": "clear"},
]

var _out: String = "res://../build/screenshots"
## Nodes a shot spawned for itself (QA enemies, the QA drop), removed after the shot.
var _temp: Array[Node] = []
var _settle: float = 4.0
## [enemy, position] pairs a shot keeps in place until it is taken.
var _hold: Array = []
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
	# Time stands still between shots: streaming waits run up to 240 s, which at the default day
	# length moved a "19.6 h" dusk shot an hour and a half into the night (and by a different
	# amount every run).
	(w.get(&"clock_driver") as WorldClockDriver).paused = true
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
	# A Hum night's glow (the Bloom aurora, brighter threads): on the next Hum's day, with the
	# environment at full Hum strength at once (it otherwise builds over ~20 s). Restored after.
	var day_before: int = clock.day()
	if bool(shot.get("hum_glow", false)):
		clock.set_time(clock.next_horde_day(), float(shot["hour"]))
		(w.get(&"env") as EnvironmentController).hum_intensity = 1.0
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
		for i: int in (shot["lineup"] as Array).size():
			var entry: Array = shot["lineup"][i]
			var at: Vector3 = c + side * float(entry[1])
			at.y = w.call(&"height_at", at.x, at.z)
			var yaw: float = atan2(pos.x - at.x, pos.z - at.z)
			var opts: Dictionary = {"yaw": yaw, "authored": true, "tier": str(entry[2]), "id": "qa:%s:%s" % [shot["name"], entry[0]]}
			if entry.size() > 3:
				# Dressed as one of that building's people (EnemyVisual.population_body).
				opts["poi"] = str(entry[3])
				opts["id"] = "qa:%s:%d" % [shot["name"], i]
			var e: Node = w.get(&"ai").call(&"spawn", StringName(str(entry[0])), at, opts)
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
		if str(shot["ui"]) == "options":
			_show_options(w)
		else:
			_show_record(w)
	if shot.has("enemy"):
		# An awake body at the look point facing the camera, its brain paused so it holds its
		# idle loop in place; framed from its own feet so slopes don't tilt the shot.
		var at := Vector3(look.x, w.call(&"height_at", look.x, look.z), look.z)
		var yaw: float = atan2(pos.x - at.x, pos.z - at.z)
		var e: Node = w.get(&"ai").call(&"spawn", StringName(str(shot["enemy"])), at, {"yaw": yaw, "id": "qa:%s" % shot["name"],
			"authored": true, "tier": str(shot.get("tier", "normal"))})
		if e != null:
			e.set_physics_process(false)
			(e.get(&"visual") as EnemyVisual).play(&"idle")
			_temp.append(e)
			_hold.append([e, at])
		pos.y = at.y + float(shot.get("cam_height", 1.45))
		look.y = at.y + float(shot.get("look_height", 1.15))
	if shot.has("wildlife"):
		_place_band(w, shot, pos, look)
	var flock: BirdFlock = null
	if shot.has("flock"):
		# unseen until the shot flushes them: the manager's own check would put them up early
		DebugTools.set_flag(&"invisible", true)
		flock = _place_flock(w, shot, look)
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
		if bool(shot.get("fp_light", false)):
			p.equipment.call(&"_sync_equipped")
			p.equipment.toggle_light()
		_fp_pose(w, p, shot, true)
	if shot.has("poi_view"):
		await _poi_view(w, cam, p, shot["poi_view"])
	await _wait_streamed(w)
	for h: Array in _hold:
		var he: Node3D = h[0] as Node3D
		if is_instance_valid(he):
			he.global_position = h[1]
			var hv: EnemyVisual = he.get(&"visual") as EnemyVisual
			print("SHOT %s: %s at %s, body %s, visible %s" % [shot["name"], he.name, he.global_position, hv.model_id, hv.is_visible_in_tree()])
		else:
			print("SHOT warning: %s lost its Hollowed" % shot["name"])
	_hold.clear()
	if shot.has("frame_tree"):
		_frame_tree(w, cam, shot)
	if shot.has("seek"):
		_seek_view(w, cam, shot)
	if flock != null:
		await _wait(float(shot.get("settle", _settle)))
		DebugTools.set_flag(&"invisible", false)
		# stepped at a fixed rate: a software-rendered frame can last seconds
		flock.set_process(false)
		flock.flush(cam.global_position, "person")
		for i: int in int(float(shot["flush_after"]) * 30.0):
			flock.advance(1.0 / 30.0)
		await get_tree().process_frame
		await get_tree().process_frame
	else:
		await _wait(float(shot.get("settle", _settle)))
	var img: Image = get_viewport().get_texture().get_image()
	var path: String = _out.path_join("%s.png" % shot["name"])
	img.save_png(path)
	print("SHOT %s" % path)
	if shot.has("ui"):
		var ui: GameUI = w.get(&"ui") as GameUI
		ui.manual.close()
		for c: Node in ui.get_children():
			if c is OptionsPanel:
				c.queue_free()
		ui.visible = false
	if bool(shot.get("fp_light", false)) and p.equipment.has_light_on():
		p.equipment.toggle_light()
	if shot.has("fp"):
		_fp_pose(w, p, shot, false)
	if shot.has("poi_view"):
		DebugTools.set_flag(&"invisible", false)
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
	if bool(shot.get("hum_glow", false)):
		clock.set_time(day_before, clock.hour_f())
		(w.get(&"env") as EnvironmentController).hum_intensity = 0.0


## Frames a plant of a species near the shot's `pos` (once vegetation has streamed): the camera
## stands `frame` = [distance, camera height, look height] metres from it, on the side facing the
## shot's `look` or turned around it in eighths of a turn, whichever first gives a clear view
## (_view_open, low plants counting); the nearest of up to eight plants with one wins.
func _frame_tree(w: Node, cam: Camera3D, shot: Dictionary) -> void:
	var veg: Node = w.get(&"vegetation")
	var pos: Vector3 = shot["pos"]
	var at0 := Vector3(pos.x, w.call(&"height_at", pos.x, pos.z), pos.z)
	var found: Array = veg.call(&"instances_near", at0, 60.0, StringName(str(shot["frame_tree"]))) if veg != null else []
	if found.is_empty():
		print("SHOT warning: no %s near %s" % [shot["frame_tree"], pos])
		return
	var fr: Array = shot.get("frame", [2.0, 1.2, 0.8])
	var look: Vector3 = shot["look"]
	var h0: float = atan2(look.x - pos.x, look.z - pos.z)
	var blockers: Array = _blockers(w, at0, 70.0, true)
	for e: Array in found.slice(0, 8):
		var inst: VegetationScatter.Instance = e[1]
		var target := Vector2(inst.pos.x, inst.pos.z)
		for k: int in 8:
			var h: float = h0 + _turn(k) * TAU / 8.0
			var d := Vector2(sin(h), cos(h))
			var c: Vector2 = target - d * float(fr[0])
			if not _view_open(blockers, c, d, float(fr[0]) - 0.3, target):
				continue
			var at := Vector3(c.x, w.call(&"height_at", c.x, c.y) + float(fr[1]), c.y)
			cam.global_position = at
			cam.look_at(inst.pos + Vector3.UP * float(fr[2]), Vector3.UP)
			print("SHOT framing %s at %s from %s" % [inst.species, inst.pos, at])
			return
	print("SHOT warning: no clear view of a %s near %s" % [shot["frame_tree"], pos])


## Finds a clear view for a shot (`seek`: {r, here: [lo, hi], ahead: [lo, hi], clear}): camera spots
## on a 4 m grid within r of `pos`, nearest first, sixteen headings each from the authored one
## outward. A view passes when the Bloom field at the camera, and its mean 8-26 m ahead, lie in the
## given ranges and _view_open() holds for `clear` metres (half that on a second pass if none
## does). The camera keeps the authored height above the ground, the look its distance and height.
## The same world gives the same view.
func _seek_view(w: Node, cam: Camera3D, shot: Dictionary) -> void:
	var terrain: TerrainManager = w.get(&"terrain") as TerrainManager
	var sk: Dictionary = shot["seek"]
	var pos: Vector3 = shot["pos"]
	var look: Vector3 = shot["look"]
	var r: float = float(sk.get("r", 20.0))
	var clear: float = float(sk.get("clear", 14.0))
	var here: Array = sk.get("here", [0.0, 1.0])
	var ahead: Array = sk.get("ahead", [0.0, 1.0])
	var c0 := Vector2(pos.x, pos.z)
	var blockers: Array = _blockers(w, Vector3(pos.x, 0.0, pos.z), r + clear + 6.0, false)
	var h0: float = atan2(look.x - pos.x, look.z - pos.z)
	var look_d: float = Vector2(look.x - pos.x, look.z - pos.z).length()
	var spots: Array[Vector2] = []
	var n: int = int(r / 4.0)
	for iz: int in range(-n, n + 1):
		for ix: int in range(-n, n + 1):
			if Vector2(ix, iz).length() * 4.0 <= r:
				spots.append(c0 + Vector2(ix, iz) * 4.0)
	spots.sort_custom(func(a: Vector2, b: Vector2) -> bool: return a.distance_squared_to(c0) < b.distance_squared_to(c0))
	for need: float in [clear, clear * 0.5]:
		for c: Vector2 in spots:
			var f: float = terrain.bloom_at(c.x, c.y)
			if f < float(here[0]) or f > float(here[1]):
				continue
			for k: int in 16:
				var h: float = h0 + _turn(k) * TAU / 16.0
				var d := Vector2(sin(h), cos(h))
				var fa: float = 0.0
				for t: float in [8.0, 14.0, 20.0, 26.0]:
					fa += terrain.bloom_at(c.x + d.x * t, c.y + d.y * t) * 0.25
				if fa < float(ahead[0]) or fa > float(ahead[1]) or not _view_open(blockers, c, d, need):
					continue
				var lk: Vector2 = c + d * look_d
				cam.global_position = Vector3(c.x, terrain.height_at(c.x, c.y) + pos.y, c.y)
				cam.look_at(Vector3(lk.x, terrain.height_at(lk.x, lk.y) + look.y, lk.y), Vector3.UP)
				print("SHOT %s: view from (%.1f, %.1f) heading %.0f deg, %.0f m clear, Bloom %.2f here, %.2f ahead" % [shot["name"], c.x, c.y, rad_to_deg(h), need, f, fa])
				return
	print("SHOT warning: no clear view for %s within %.0f m of %s" % [shot["name"], r, c0])


## 0, +1, -1, +2, -2 ...: steps away from an authored heading, nearest first.
static func _turn(k: int) -> int:
	return ((k + 1) >> 1) * (1 if k % 2 == 1 else -1)


## What can stand in a QA camera's way near `at`: trunks (their radius) and bushes, boulders, logs
## and saplings (half their model's footprint); with `low`, ferns too (a camera framing something on
## the ground). As [centre (x, z), radius].
func _blockers(w: Node, at: Vector3, span: float, low: bool) -> Array:
	var out: Array = []
	var veg: Node = w.get(&"vegetation")
	if veg == null:
		return out
	for e: Array in veg.call(&"instances_near", at, span):
		var inst: VegetationScatter.Instance = e[1]
		var sp: SpeciesDef = Content.get_def(&"species", inst.species) as SpeciesDef
		if sp == null or not (sp.veg_kind in ["tree", "bush", "rock", "deadfall"] or (low and sp.veg_kind == "fern")):
			continue
		var rad: float = sp.trunk_radius * inst.scale + 0.15
		if sp.veg_kind != "tree" and not sp.models.is_empty():
			var bb: AABB = ModelLibrary.mesh(sp.models[inst.variant % sp.models.size()]).get_aabb()
			rad = maxf(bb.size.x, bb.size.z) * 0.5 * inst.scale
		out.append([Vector2(inst.pos.x, inst.pos.z), rad])
	return out


## True if a view from `c` along `d` (unit, x/z) is clear: nothing within half a metre of the lens,
## nothing in its first 5 m within 25 degrees, nothing across the line of sight up to `clear` metres.
## `skip` is the subject itself.
static func _view_open(blockers: Array, c: Vector2, d: Vector2, clear: float, skip: Vector2 = Vector2.INF) -> bool:
	for b: Array in blockers:
		var p: Vector2 = b[0]
		if p.distance_squared_to(skip) < 0.0001:
			continue
		var rad: float = b[1]
		var rel: Vector2 = p - c
		if rel.length() < rad + 0.5:
			return false
		var along: float = rel.dot(d)
		if along < 0.0 or along > clear + rad:
			continue
		var side: float = absf(rel.x * d.y - rel.y * d.x)
		if side < rad + 0.35 or (along < 5.0 and side < rad + along * 0.47):
			return false
	return true


## A view inside a building: the camera at a POI-local point looking at another (POI cells,
## metres; `level` the storey), with the building's own sleepers spawned and left asleep (the player,
## standing at the camera, is invisible to them for the shot).
func _poi_view(w: Node, cam: Camera3D, p: Player, v: Dictionary) -> void:
	var pois: Node = w.get(&"pois")
	var inst: PoiInstance = (pois.get(&"instances") as Dictionary).get(StringName(str(v["poi"]))) as PoiInstance if pois != null else null
	if inst == null:
		print("SHOT warning: no POI %s" % v["poi"])
		return
	var li: int = int(v.get("level", 0))
	var c: Array = v["cam"]
	var l: Array = v["look"]
	var cam_at: Vector3 = inst.to_global(inst.layout.local_pos(li, Vector2(float(c[0]), float(c[2]))) + Vector3.UP * float(c[1]))
	var look_pt: Vector3 = inst.to_global(inst.layout.local_pos(li, Vector2(float(l[0]), float(l[2]))) + Vector3.UP * float(l[1]))
	DebugTools.set_flag(&"invisible", true)
	p.global_position = cam_at - Vector3.UP * (float(c[1]) - 0.1)
	var t0: int = Time.get_ticks_msec()
	var want: Array = v.get("sleepers", [])
	while Time.get_ticks_msec() - t0 < 60000:
		var have: Dictionary = inst.get(&"_sleepers")
		var missing: int = 0
		for sid: Variant in want:
			if not is_instance_valid(have.get(StringName(str(sid)))):
				missing += 1
		if bool(inst.get(&"sleepers_spawned")) and missing == 0:
			break
		await get_tree().process_frame
	for sid: Variant in want:
		var se: Enemy = (inst.get(&"_sleepers") as Dictionary).get(StringName(str(sid))) as Enemy
		if se != null and is_instance_valid(se):
			print("SHOT %s: sleeper %s (%s) wears %s" % [v["poi"], sid, se.def.id, se.visual.model_id])
		else:
			print("SHOT warning: sleeper %s of %s not spawned" % [sid, v["poi"]])
	cam.global_position = cam_at
	cam.look_at(look_pt, Vector3.UP)


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


## The options screen over the game view.
func _show_options(w: Node) -> void:
	var ui: GameUI = w.get(&"ui") as GameUI
	ui.visible = true
	var panel := OptionsPanel.new()
	ui.add_child(panel)
	panel.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	panel.position = (ui.get_viewport().get_visible_rect().size - Vector2(620, 560)) * 0.5


## First-person QA poses (ADR-0029): an arms action frozen at a frame, or the left wrist raised
## with the tether UI live on its screen; undone after the shot.
func _fp_pose(w: Node, p: Player, shot: Dictionary, on: bool) -> void:
	p.equipment.call(&"_sync_equipped")
	var vm: ViewModel = p.equipment.viewmodel
	if vm == null:
		return
	var ui: GameUI = w.get(&"ui") as GameUI
	if not on:
		vm.release_action()
		if bool(shot.get("fp_tether", false)) and ui != null and ui.tether != null and ui.tether.raised:
			ui.tether.toggle()
		vm.set_tether_raised(false)
		return
	vm.motion.equip = 1.0
	if shot.has("fp_action"):
		vm.freeze_action(StringName(str(shot["fp_action"])), float(shot.get("fp_frame", 0)) / 30.0)
	if bool(shot.get("fp_tether", false)) and ui != null:
		ui.call(&"_ensure_tether")
		if ui.tether != null and not ui.tether.raised:
			ui.tether.toggle()
		vm.set_tether_raised(true)


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


## A band of wild animals at the look point, side-on to the camera, their brains paused in the
## actions the shot names (ADR-0027).
func _place_band(w: Node, shot: Dictionary, pos: Vector3, look: Vector3) -> void:
	var wm: WildlifeManager = w.get(&"wildlife") as WildlifeManager
	var d := Content.get_def(&"wildlife", StringName(str(shot["wildlife"]))) as WildlifeDef
	if wm == null or d == null:
		print("SHOT warning: no wildlife for %s" % shot["name"])
		return
	var plan: Dictionary = {"id": StringName("qa:%s" % shot["name"]), "def": d.id, "pos": Vector2(look.x, look.z),
		"count": int(shot.get("count", 1)), "seed": 77}
	var herd: Array = wm.spawn_band(d, plan)
	var side: float = atan2(look.x - pos.x, look.z - pos.z) + PI * 0.5
	var anims: Array = shot.get("anims", ["idle"])
	for i: int in herd.size():
		var a: Animal = herd[i]
		a.set_physics_process(false)
		a.rotation.y = side + (PI if i % 2 == 1 else 0.0) + (float(i) - 1.5) * 0.25
		var g := a.global_position
		g.y = w.call(&"height_at", g.x, g.z)
		a.global_position = g
		var an: StringName = StringName(str(anims[i % anims.size()]))
		if a.anim != null and a.anim.has_animation(an):
			a.anim.play(an)
			a.anim.seek(float(i) * 0.7, true)
		_temp.append(a)
		print("SHOT %s: %s %s at %s" % [shot["name"], a.model_id, an, a.global_position])


## A flock perched round the look point; the shot flushes it towards the camera's far side.
func _place_flock(w: Node, shot: Dictionary, look: Vector3) -> BirdFlock:
	var wm: WildlifeManager = w.get(&"wildlife") as WildlifeManager
	var d := Content.get_def(&"wildlife", StringName(str(shot["flock"]))) as WildlifeDef
	if wm == null or d == null:
		return null
	var g := Vector3(look.x, w.call(&"height_at", look.x, look.z), look.z)
	var f: BirdFlock = wm.spawn_flock(d, {"id": StringName("qa:%s" % shot["name"]), "def": d.id, "pos": Vector2(g.x, g.z),
		"count": 8, "seed": 41})
	if f != null:
		_temp.append(f)
	return f

