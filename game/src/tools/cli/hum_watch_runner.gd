extends Node
## hum_watch.gd's work: see there.

const STREET := Vector3(-45, 1.7, 2068)
const LOOK := Vector3(-95, 2, 2064)
const NEAR: float = 30.0

var _out: String = "user://hum_watch"
var _frames: int = 16
var _every: float = 0.5
var _start: int = 6
var _height: float = 18.0
var w: Node
var p: Node3D
var _ai: Node


func _ready() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var i: int = 0
	while i < args.size():
		match args[i]:
			"--out":
				i += 1
				_out = args[i]
			"--frames":
				i += 1
				_frames = int(args[i])
			"--every":
				i += 1
				_every = float(args[i])
			"--start":
				i += 1
				_start = int(args[i])
			"--height":
				i += 1
				_height = float(args[i])
			"--no-crowd":
				Crowd.enabled = false
		i += 1
	DirAccess.make_dir_recursive_absolute(_out)
	_run.call_deferred()


func _run() -> void:
	var game: Node = get_node("/root/Game")
	game.call(&"start_new_game", {"game_mode": "survival", "skip_intro": true, "slot": "humwatch",
		"rules": {"hum_max_alive": 40, "hum_size": 1.5}})
	while game.get(&"world") == null or not bool(game.world.is_ready):
		await get_tree().process_frame
	w = game.world
	p = w.player
	p.set(&"god_mode", true)
	p.set(&"input_enabled", false)
	p.global_position = Vector3(STREET.x, w.height_at(STREET.x, STREET.z) + 0.1, STREET.z)
	var d: Vector3 = LOOK - STREET
	p.rotation.y = atan2(-d.x, -d.z)
	w.terrain.update_streaming(p.global_position, true)
	for k: int in 120:
		await get_tree().process_frame
	var ai: Node = w.get(&"ai")
	var day: int = game.session.clock.next_horde_day(1)
	game.session.clock.set_time(day, 21.98)
	# Game time runs slow on a software renderer: wait on the night itself, not a short clock.
	var t0: int = Time.get_ticks_msec() + 900000
	while not bool(ai.hum.active) and Time.get_ticks_msec() < t0:
		await get_tree().process_frame
	var rng := RandomNumberGenerator.new()
	rng.seed = 7
	game.session.horde.horde_index = 3
	var plan: Dictionary = game.session.horde.plan(40, rng)
	ai.hum.set(&"_wave_i", 0)
	for wv: Dictionary in plan.get("waves", []):
		wv["start_min"] = 0.0
	ai.hum.plan = plan
	print("[hum_watch] hum active %s, plan %d, crowd %s" % [ai.hum.active, int(plan.get("total", 0)), Crowd.enabled])
	_ai = ai
	# Wait for them to come in round the player.
	var t1: int = Time.get_ticks_msec() + 900000
	var next_log: int = 0
	while Time.get_ticks_msec() < t1 and _near().size() < _start:
		await get_tree().process_frame
		if Time.get_ticks_msec() > next_log:
			next_log = Time.get_ticks_msec() + 15000
			print("[hum_watch] near %d" % _near().size())
	print("[hum_watch] near %d: watching" % _near().size())
	# Light it (a Hum night is too dark to see the bodies on a software renderer).
	var lamp := OmniLight3D.new()
	lamp.omni_range = 45.0
	lamp.light_energy = 3.0
	lamp.omni_attenuation = 0.6
	w.add_child(lamp)
	var cam := Camera3D.new()
	cam.fov = 70.0
	w.add_child(cam)
	var turn: float = 0.0
	var samples: int = 0
	var close: int = 0
	var pairs: int = 0
	var last: Dictionary = {}
	var shot_t: float = 0.0
	var shot: int = 0
	while shot < _frames:
		await get_tree().physics_frame
		var dt: float = get_physics_process_delta_time()
		var near: Array[Enemy] = _near()
		for e: Enemy in near:
			var v := Vector2(e.velocity.x, e.velocity.z)
			if v.length() > 0.5:
				var a: float = v.angle()
				if last.has(e):
					turn += absf(rad_to_deg(angle_difference(float(last[e]), a)))
					samples += 1
				last[e] = a
			else:
				last.erase(e)
		for i: int in near.size():
			for j: int in range(i + 1, near.size()):
				pairs += 1
				var dd: Vector3 = near[i].global_position - near[j].global_position
				if Vector2(dd.x, dd.z).length() < 0.5:
					close += 1
		shot_t -= dt
		if shot_t <= 0.0:
			shot_t = _every
			var fwd: Vector3 = -p.global_transform.basis.z
			lamp.global_position = p.global_position + Vector3.UP * 12.0
			# From above, a little behind: the ring of bodies round the player in view.
			cam.global_position = p.global_position - fwd * _height * 0.22 + Vector3.UP * _height
			cam.look_at(p.global_position + fwd * 1.0, Vector3.UP)
			cam.make_current()
			await get_tree().process_frame
			await get_tree().process_frame
			var img: Image = get_viewport().get_texture().get_image()
			img.save_png(_out.path_join("hum_%02d.png" % shot))
			shot += 1
	var report: Dictionary = {"crowd": Crowd.enabled, "near_bodies": _near().size(),
		"jitter_deg_per_tick": snappedf(turn / maxf(1.0, float(samples)), 0.01),
		"close_pairs_share": snappedf(float(close) / maxf(1.0, float(pairs)), 0.0001), "frames": _frames}
	print("[hum_watch] ", JSON.stringify(report))
	var f := FileAccess.open(_out.path_join("report.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(report, "  "))
	f.close()
	get_tree().quit(0)


## The Hum's own bodies within NEAR m of the player (sleepers in the houses don't count).
func _near() -> Array[Enemy]:
	var out: Array[Enemy] = []
	if _ai == null:
		return out
	for m: Dictionary in (_ai.hum.members as Dictionary).values():
		var e: Enemy = m.get("node") as Enemy if is_instance_valid(m.get("node")) else null
		if e != null and e.is_alive() and e.global_position.distance_to(p.global_position) < NEAR:
			out.append(e)
	return out
