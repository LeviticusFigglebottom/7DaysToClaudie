extends Node
## entry_light's work (see entry_light.gd).

## Walks: the building (PoiManager instance id), waypoints in its level-0 plan cells (outside first),
## and the point the camera turns to at the end. Each crosses a wall or two (the camera is not the
## player's body): it is the light the room gets on arrival that's measured.
const ENTRIES: Array[Dictionary] = [
	{"name": "garage_office", "poi": "cordon_gas", "path": [Vector2(11.0, 13.0), Vector2(11.0, 7.0), Vector2(11.0, 3.5), Vector2(11.0, 1.6)], "look": Vector3(9.4, 0.9, 0.4)},
	{"name": "pharmacy_stock", "poi": "pell_crossing/pharmacy", "path": [Vector2(19.5, 5.5), Vector2(12.5, 5.5), Vector2(12.5, 3.6), Vector2(12.5, 1.8)], "look": Vector3(6.5, 0.9, 1.5)},
]
const EYE: float = 1.6
const WALK_SPEED: float = 2.5
const SAMPLE_FRAMES: int = 15
const SECONDS: float = 5.0

var _out: String = "res://../build/entry_light"
var _before: bool = false
var _only: PackedStringArray = []
## --cold: wait COLD_AWAY m off first, then jump to the doorway and walk in at once, so the room's
## probe is still parked or queued as the camera enters (a fast arrival; the case report 3 saw).
var _cold: bool = false
const COLD_AWAY: float = 220.0


func _ready() -> void:
	_run.call_deferred()


func _run() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	for i: int in args.size():
		match args[i]:
			"--out":
				_out = args[i + 1]
			"--only":
				_only = args[i + 1].split(",")
			"--before":
				_before = true
			"--cold":
				_cold = true
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(_out) if _out.begins_with("res://") else _out)
	var cfg: Dictionary = Content.config(&"interior_light")
	if _before:
		cfg["pending_fill"] = 0.0
		cfg["daylight_min_share"] = 0.2
	var game: Node = get_node("/root/Game")
	game.call(&"start_new_game", {"game_mode": "slice", "skip_intro": true, "slot": "entry"})
	var t0: int = Time.get_ticks_msec()
	while (game.get(&"world") == null or not bool(game.world.is_ready)) and Time.get_ticks_msec() - t0 < 1200000:
		await get_tree().process_frame
	var w: Node = game.world
	if w == null or not bool(w.is_ready):
		printerr("ENTRY world did not load")
		get_tree().quit(1)
		return
	(w.get(&"ui") as CanvasLayer).visible = false
	var debug: Node = w.get_node_or_null(^"Debug")
	if debug != null:
		(debug as CanvasLayer).visible = false
	DebugTools.set_flag(&"invisible", true)
	var p: Player = w.player
	p.input_enabled = false
	(w.get(&"clock_driver") as WorldClockDriver).paused = true
	var clock: WorldClock = Game.session.clock
	clock.set_time(clock.day(), 13.0)
	Game.session.weather.force(&"clear")
	Game.session.weather.blend = 1.0
	Game.session.weather.current = &"clear"
	var pois: Node = w.get(&"pois")
	var budget: Node = pois.get(&"probes")
	if _before:
		budget.set(&"enter", -1.0)
	var env: EnvironmentController = w.get(&"env") as EnvironmentController
	var cam := Camera3D.new()
	cam.fov = 75.0
	w.add_child(cam)
	cam.make_current()
	for e: Dictionary in ENTRIES:
		if not _only.is_empty() and not _only.has(str(e["name"])):
			continue
		await _entry(w, p, cam, pois, budget, env, e)
	print("ENTRY done")
	get_tree().quit(0)


func _entry(w: Node, p: Player, cam: Camera3D, pois: Node, budget: Node, env: EnvironmentController, e: Dictionary) -> void:
	var path: Array = e["path"]
	# Arrive in the street first: the player stands at the start until the building is built and the
	# probes round it have had time to queue, as they would on a walk into town.
	var inst: PoiInstance = null
	var start_pt: Vector3 = Vector3.ZERO
	var t0: int = Time.get_ticks_msec()
	while Time.get_ticks_msec() - t0 < 600000:
		inst = (pois.get(&"instances") as Dictionary).get(StringName(str(e["poi"]))) as PoiInstance
		if inst != null:
			break
		var entry: Dictionary = (pois.get(&"registry") as PoiRegistry).entries.get(StringName(str(e["poi"])), {}) if pois.get(&"registry") != null else {}
		if not entry.is_empty():
			var c: Vector2 = entry["center"]
			p.global_position = Vector3(c.x, float(w.call(&"height_at", c.x, c.y)) + 1.0, c.y)
		await get_tree().process_frame
	if inst == null:
		print("ENTRY %s: no building %s" % [e["name"], e["poi"]])
		return
	var pts: Array[Vector3] = []
	for q: Vector2 in path:
		pts.append(inst.to_global(inst.layout.local_pos(0, q)) + Vector3.UP * EYE)
	var lv: Vector3 = e["look"]
	var look_end: Vector3 = inst.to_global(inst.layout.local_pos(0, Vector2(lv.x, lv.z)) + Vector3.UP * lv.y)
	start_pt = pts[0]
	if _cold:
		# Away long enough for the budget to park the building's probes, then straight to the door.
		var away: Vector3 = start_pt + (start_pt - pts[1]).normalized() * COLD_AWAY
		away.y = float(w.call(&"height_at", away.x, away.z)) + EYE
		p.global_position = away - Vector3.UP * (EYE - 0.1)
		cam.global_position = away
		for i: int in 240:
			await get_tree().process_frame
		var room0: ReflectionProbe = budget.call(&"room_probe", pts[pts.size() - 1]) as ReflectionProbe
		print("ENTRY %s: away %d m, the room's probe %s" % [e["name"], int(COLD_AWAY), "none" if room0 == null else ("parked" if not bool(budget.call(&"is_shown", room0)) else "live")])
	p.global_position = start_pt - Vector3.UP * (EYE - 0.1)
	cam.global_position = start_pt
	cam.look_at(pts[1], Vector3.UP)
	for i: int in (2 if _cold else 240):
		await get_tree().process_frame
	# Walk in, sampling.
	var total: float = 0.0
	for i: int in range(1, pts.size()):
		total += pts[i - 1].distance_to(pts[i])
	var frames: int = int(SECONDS * 60.0)
	var curve: PackedFloat32Array = []
	var low: float = INF
	for f: int in frames + 1:
		var t: float = f / 60.0
		var at: Vector3 = _along(pts, minf(t * WALK_SPEED, total))
		var walking: bool = t * WALK_SPEED < total
		cam.global_position = at
		p.global_position = at - Vector3.UP * (EYE - 0.1)
		var ahead: Vector3 = _along(pts, minf(t * WALK_SPEED + 1.5, total)) if walking else look_end
		if ahead.distance_to(at) > 0.05:
			var target: Vector3 = Vector3(ahead.x, at.y - 0.2, ahead.z) if walking else look_end
			cam.look_at(target, Vector3.UP)
		await get_tree().process_frame
		if f % SAMPLE_FRAMES == 0:
			var img: Image = get_viewport().get_texture().get_image()
			var luma: float = ImageStats.mean_luma(img)
			curve.append(luma)
			var room: ReflectionProbe = budget.call(&"room_probe", at) as ReflectionProbe
			var state: String = "outside"
			if room != null:
				low = minf(low, luma)
				state = "parked" if not bool(budget.call(&"is_shown", room)) else ("ready %.2f" % float(budget.call(&"readiness", room)))
			print("ENTRY %s t=%.2f luma %.3f room %s fill %.2f%s" % [e["name"], t, luma, state, env.pending, " (walking)" if walking else ""])
			if f % 60 == 0:
				img.save_png(_out.path_join("%s_%s%s_t%d.png" % [e["name"], "before" if _before else "after", "_cold" if _cold else "", f / 60]))
	print("ENTRY %s %s%s: lowest luma once inside a room %.3f; curve %s" % [e["name"], "before" if _before else "after", " cold" if _cold else "", low, ", ".join(Array(curve).map(func(v: float) -> String: return "%.2f" % v))])


## The point `d` metres along the polyline.
static func _along(pts: Array[Vector3], d: float) -> Vector3:
	for i: int in range(1, pts.size()):
		var seg: float = pts[i - 1].distance_to(pts[i])
		if d <= seg:
			return pts[i - 1].lerp(pts[i], d / maxf(seg, 0.001))
		d -= seg
	return pts[pts.size() - 1]
