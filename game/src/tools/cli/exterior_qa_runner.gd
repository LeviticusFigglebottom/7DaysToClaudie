extends Node
## Exterior QA renders (loaded by exterior_qa.gd, ADR-0023): starts a slice game, then for each
## shot sets the day (the moon's phase), time and weather, stages what the shot is about and saves
## a PNG: the night sky under a full and a new moon and a clearing under each, a bridge from the
## bank and from its deck at night (reflectors in a hand light), light props lit and destroyed side
## by side, and the Program drone hovering with a lift.

const SHOTS: Array[Dictionary] = [
	# Larch Pond's north shore, looking across the water toward the moon (day 3 is full, day 8 new).
	{"name": "moon_full", "pos": Vector3(-268, 1.8, 1846), "look_moon": true, "day": 3, "hour": 23.5, "weather": "clear"},
	{"name": "moon_new", "pos": Vector3(-268, 1.8, 1846), "look_dir": Vector3(0.45, 0.2, 0.87), "day": 8, "hour": 23.5, "weather": "clear"},
	# The drop-site clearing under a high full moon and under none: how readable the night is.
	{"name": "moonlit_clearing", "pos": Vector3(-300, 2.0, 2302), "look": Vector3(-240, 0, 2296), "day": 3, "hour": 23.5, "weather": "clear"},
	{"name": "moonless_clearing", "pos": Vector3(-300, 2.0, 2302), "look": Vector3(-240, 0, 2296), "day": 8, "hour": 23.5, "weather": "clear"},
	# Route 9 over the Tamsin: from the west bank downstream, and along the deck at night.
	{"name": "bridge_bank", "pos": Vector3(150, 1.7, 1918), "look": Vector3(181, 5.5, 1957), "hour": 16.5, "weather": "clear"},
	{"name": "bridge_wide", "pos": Vector3(108, 4.0, 1890), "look": Vector3(176, 4.0, 1955), "hour": 10.5, "weather": "clear"},
	{"name": "bridge_deck_night", "pos": Vector3(128, 1.65, 1961.2), "look": Vector3(200, 1.0, 1955.2), "level_look": true, "day": 8,
		"hour": 22.5, "weather": "clear", "light": true},
	# Light props on the drop-site clearing at night: each lit as a POI lights it (PropLights).
	{"name": "lamps_night", "pos": Vector3(-292, 1.25, 2301.2), "look": Vector3(-292, 0.25, 2296.5), "day": 8, "hour": 22.5, "weather": "clear",
		"props": [["lantern_camping", "clean"], ["lantern_camping", "destroyed"], ["wild_oil_lantern", "clean"], ["wild_oil_lantern", "destroyed"],
			["candle_cluster", "clean"], ["candle_cluster", "worn"], ["oil_drum_fire", "clean"], ["oil_drum_fire", "worn"]], "fov": 55.0},
	# The Program's drone braking into a hover over a drop, a lift on its sling.
	{"name": "drone_hover", "pos": Vector3(-301, 1.6, 2306), "drone": Vector3(-292, 8.5, 2298), "hour": 16.2, "weather": "clear", "fov": 45.0},
	{"name": "drone_dusk", "pos": Vector3(-301, 1.6, 2306), "drone": Vector3(-292, 8.5, 2298), "hour": 20.6, "weather": "clear", "fov": 45.0},
]

var _out: String = "res://../build/exterior_qa"
var _temp: Array[Node] = []
var _settle: float = 4.0
## Longest wait for the vegetation round the camera to stream in. Software Vulkan saturates the
## CPU and the scatter can take minutes, so a quick pass can cut it short (night shots barely
## show it).
var _stream_wait: float = 240.0
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
			"--stream-wait":
				_stream_wait = float(args[i + 1])
	DirAccess.make_dir_recursive_absolute(_out)
	_run.call_deferred()


func _wait(s: float) -> void:
	var end: int = Time.get_ticks_msec() + int(s * 1000.0)
	while Time.get_ticks_msec() < end:
		await get_tree().process_frame


## Waits (up to --stream-wait, 4 min by default) until the vegetation within two chunks of the
## camera has streamed in.
func _wait_streamed(w: Node) -> void:
	var veg: Node = w.get(&"vegetation")
	var t0: int = Time.get_ticks_msec()
	while veg != null and not bool(veg.call(&"is_settled", 2)):
		if Time.get_ticks_msec() - t0 > int(_stream_wait * 1000.0):
			print("QA warning: vegetation still streaming after %.0f s" % _stream_wait)
			return
		await get_tree().process_frame


func _run() -> void:
	var game: Node = get_node("/root/Game")
	# No Hum in these shots: its aurora and green fill would hide what the moon alone does.
	game.call(&"start_new_game", {"game_mode": "slice", "skip_intro": true, "slot": "exterior_qa", "rules": {"hum_first_day": 28}})
	var t0: int = Time.get_ticks_msec()
	while (game.get(&"world") == null or not bool(game.world.is_ready)) and Time.get_ticks_msec() - t0 < 300000:
		await get_tree().process_frame
	var w: Node = game.world
	if w == null:
		printerr("QA world did not load")
		get_tree().quit(1)
		return
	(w.get(&"ui") as CanvasLayer).visible = false
	var debug: Node = w.get_node_or_null(^"Debug")
	if debug != null:
		(debug as CanvasLayer).visible = false
	var cam := Camera3D.new()
	cam.far = 4000.0
	w.add_child(cam)
	cam.make_current()
	var p: Player = w.player
	p.input_enabled = false
	var vm: Node3D = p.get_node_or_null(^"Head/Camera3D/ViewModel") as Node3D
	if vm != null:
		vm.visible = false
	(w.get(&"clock_driver") as WorldClockDriver).paused = true
	for shot: Dictionary in SHOTS:
		if not _only.is_empty() and not _only.has(str(shot["name"])):
			continue
		await _shoot(w, cam, p, shot)
	print("QA done in %.1fs" % ((Time.get_ticks_msec() - t0) / 1000.0))
	get_tree().quit(0)


func _shoot(w: Node, cam: Camera3D, p: Player, shot: Dictionary) -> void:
	var clock: WorldClock = Game.session.clock
	clock.set_time(int(shot.get("day", clock.day())), float(shot["hour"]))
	Game.session.weather.force(StringName(str(shot["weather"])))
	Game.session.weather.blend = 1.0
	Game.session.weather.current = StringName(str(shot["weather"]))
	var pos: Vector3 = shot["pos"]
	var ground: float = w.call(&"height_at", pos.x, pos.z)
	pos.y += ground
	p.global_position = Vector3(pos.x, ground + 0.2, pos.z)
	(w.get(&"terrain") as TerrainManager).update_streaming(p.global_position, true)
	var env: EnvironmentController = w.get(&"env") as EnvironmentController
	env.update_now()
	var look: Vector3
	if bool(shot.get("look_moon", false)):
		# The moon a little below the top of the frame, the far shore across the bottom.
		var md: Vector3 = env.moon_model.direction(clock)
		var flat := Vector3(md.x, 0.0, md.z).normalized()
		var alt: float = asin(md.y)
		look = pos + (flat * cos(alt - deg_to_rad(16.0)) + Vector3.UP * sin(alt - deg_to_rad(16.0))) * 50.0
	elif shot.has("look_dir"):
		look = pos + (shot["look_dir"] as Vector3).normalized() * 50.0
	elif shot.has("drone"):
		look = shot["drone"]
		look.y += w.call(&"height_at", look.x, look.z) - 2.0
	else:
		look = shot["look"]
		look.y += ground if bool(shot.get("level_look", false)) else float(w.call(&"height_at", look.x, look.z))
	if shot.has("props"):
		_place_props(w, look, pos, shot["props"])
	if shot.has("drone"):
		_hover_drone(w, shot["drone"])
	if bool(shot.get("light", false)):
		var l := OmniLight3D.new()
		l.light_color = Color(1.0, 0.86, 0.7)
		l.light_energy = 2.2
		l.omni_range = 40.0
		l.shadow_enabled = true
		cam.add_child(l)
		l.position = Vector3(0.25, -0.25, -0.3)
	cam.global_position = pos
	cam.look_at(look, Vector3.UP)
	cam.fov = float(shot.get("fov", 70.0))
	await _wait_streamed(w)
	await _wait(float(shot.get("settle", _settle)))
	print("QA %s: moon %s phase %.2f alt %.1f deg, moonlight %.3f, ambient %.3f" % [shot["name"], env.moon_state.get("name", "?"),
		float(env.moon_state.get("phase", 0.0)), float(env.moon_state.get("altitude", 0.0)), env.moon.light_energy, env.env.ambient_light_energy])
	var img: Image = get_viewport().get_texture().get_image()
	var path: String = _out.path_join("%s.png" % shot["name"])
	img.save_png(path)
	print("QA %s" % path)
	for n: Node in _temp:
		if is_instance_valid(n):
			n.queue_free()
	_temp.clear()
	for c: Node in cam.get_children():
		c.queue_free()


## Light props in a row across `at`, facing the camera, each lit as PoiBuilder lights a POI's lit
## prop: [prop id, condition]. A destroyed lantern or a mains fixture stays dark.
func _place_props(w: Node, at: Vector3, cam_pos: Vector3, list: Array) -> void:
	var to_cam := Vector3(cam_pos.x - at.x, 0.0, cam_pos.z - at.z).normalized()
	# Left to right as listed.
	var side: Vector3 = Vector3.UP.cross(to_cam)
	var n: int = list.size()
	var spacing: float = 1.0
	for i: int in n:
		var e: Array = list[i]
		var pd: PropDef = Content.get_def(&"prop", StringName(str(e[0]))) as PropDef
		if pd == null:
			continue
		var cond: String = str(e[1])
		var q: Vector3 = at + side * ((float(i) - float(n - 1) * 0.5) * spacing)
		q.y = w.call(&"height_at", q.x, q.z)
		var xf := Transform3D(Basis.looking_at(-to_cam, Vector3.UP), q)
		var light: Dictionary = pd.light_for(cond)
		var holder := Node3D.new()
		w.add_child(holder)
		_temp.append(holder)
		if light.is_empty():
			var mi := MeshInstance3D.new()
			mi.mesh = ModelLibrary.mesh(pd.model_for(cond), "box")
			mi.transform = xf
			holder.add_child(mi)
		else:
			holder.add_child(PropLights.lit_mesh(pd.model_for(cond), xf, false))
			holder.add_child(PropLights.light_node(light, xf))
		print("QA prop %s (%s): %s" % [pd.id, cond, "lit" if not light.is_empty() else "dark"])


## A Program drone braking into its hover at `hover` (y above the ground there), a lift on its
## sling, held still for the shot.
func _hover_drone(w: Node, hover: Vector3) -> void:
	var g := Vector3(hover.x, w.call(&"height_at", hover.x, hover.z), hover.z)
	var cfg: Dictionary = Content.config(&"program_drone")
	var f: ProgramDrone.Flight = ProgramDrone.plan_flight(g, "qa", Game.session.world_seed, cfg, hover.y)
	var d := ProgramDrone.new()
	d.flight = f
	d.cfg = cfg
	d.ground = g
	w.add_child(d)
	_temp.append(d)
	var t: float = f.t_arrive - 1.5
	d.fly(t)
	var can := MeshInstance3D.new()
	can.mesh = ModelLibrary.mesh("items/supply_canister", "box")
	w.add_child(can)
	can.global_position = f.position(t) + ProgramDrone.HANG
	_temp.append(can)
