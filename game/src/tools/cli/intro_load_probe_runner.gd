extends Node
## Runner for intro_load_probe.gd: starts a new game, then times every frame until the player has
## control (and the intro, when it plays, has ended).

const SLOW_MS: float = 50.0

var _with_intro: bool = false
var _last: int = 0
var _frames: Array[Dictionary] = []
var _t0: int = 0
var _ready_ms: int = -1
var _done: bool = false
## --shot <png>: saves a frame of the intro's world card (a rendered run) once it has shown 10 s (auto exposure settles).
var _shot_path: String = ""
var _world_shot_s: float = 0.0
var _saw_world_shot: bool = false
## --shot-after-load: no intro during the load; once the world is up, show the intro's world
## card on its own (a still of the shot on a renderer too slow to reach it in time).
var _after_load: bool = false
## --skip-at <s>: skips the intro that many seconds in (a player holding Esc).
var _skip_at: float = -1.0
var _shot_intro: Node = null


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	# Last in the frame: a frame's time is everything the tree did since the previous one.
	process_priority = 100000
	var args: PackedStringArray = OS.get_cmdline_user_args()
	_with_intro = args.has("--intro")
	_after_load = args.has("--shot-after-load")
	if _after_load:
		_with_intro = false
	var ki: int = args.find("--skip-at")
	if ki >= 0 and ki + 1 < args.size():
		_skip_at = float(args[ki + 1])
	var si: int = args.find("--shot")
	if si >= 0 and si + 1 < args.size():
		_shot_path = args[si + 1]
	var opts: Dictionary = {"game_mode": "survival", "seed": 4471, "slot": "intro_probe",
		"skip_intro": not _with_intro, "force_intro": _with_intro}
	var wi: int = args.find("--world")
	if wi >= 0 and wi + 1 < args.size() and args[wi + 1] == "random":
		var main_script: GDScript = load("res://src/app/main.gd")
		opts["world_gen"] = main_script.call(&"world_gen_from_args", args, 77)
	_t0 = Time.get_ticks_msec()
	_last = Time.get_ticks_usec()
	(get_node("/root/Game")).call(&"start_new_game", opts)


func _process(_delta: float) -> void:
	if _done:
		return
	var now: int = Time.get_ticks_usec()
	var ms: float = (now - _last) / 1000.0
	_last = now
	var w: Node = get_node("/root/Game").get(&"world")
	var ui: Node = w.get(&"ui") if w != null else null
	var intro: Object = _shot_intro if _shot_intro != null else (ui.get(&"intro") if ui != null else null)
	var moving: bool = intro != null and (intro as Node).is_inside_tree() and bool(intro.call(&"is_playing")) and not bool(intro.call(&"is_calm"))
	var loading: bool = w == null or not bool(w.get(&"is_ready"))
	if _skip_at >= 0.0 and (Time.get_ticks_msec() - _t0) / 1000.0 >= _skip_at and intro != null and is_instance_valid(intro) and bool(intro.call(&"is_playing")):
		intro.call(&"skip_intro")
		print("INTRO_PROBE skipped at %d ms" % (Time.get_ticks_msec() - _t0))
		_skip_at = -1.0
	if intro != null and is_instance_valid(intro) and bool(intro.call(&"is_showing_world")):
		_saw_world_shot = true
		_world_shot_s += ms / 1000.0
		if _shot_path != "" and _world_shot_s > 10.0:
			get_viewport().get_texture().get_image().save_png(_shot_path)
			print("INTRO_PROBE world shot saved to %s" % _shot_path)
			_shot_path = ""
	if not loading and _ready_ms < 0:
		_ready_ms = Time.get_ticks_msec() - _t0
	var what: String = ""
	if moving:
		what = "card %d %s" % [int(intro.get(&"_index")), str(intro.get(&"_phase"))]
	if ui != null and loading:
		what += " | " + str(ui.call(&"loading_text"))
	_frames.append({"ms": ms, "moving": moving, "loading": loading, "intro": intro != null,
		"t": Time.get_ticks_msec() - _t0, "what": what})
	var intro_over: bool = not _with_intro or (ui != null and ui.get(&"intro") == null and _frames.size() > 10)
	if _after_load and not loading and _shot_intro == null:
		_shot_intro = IntroPlayer.new()
		ui.add_child(_shot_intro)
		_shot_intro.call(&"play", {}, IntroPlayer.vars_for(Game.session))
		var cards: Array = IntroPlayer.load_script()["cards"]
		for i: int in cards.size():
			if str((cards[i] as Dictionary).get("kind", "")) == "world":
				_shot_intro.call(&"show_card", i)
		intro = _shot_intro
		intro_over = false
	if _after_load and _shot_intro != null:
		intro_over = _shot_path == ""
	if not loading and intro_over:
		_done = true
		_report()


func _report() -> void:
	var load_worst: float = 0.0
	var load_slow: int = 0
	var load_n: int = 0
	var mv_worst: float = 0.0
	var mv_slow: int = 0
	var mv_n: int = 0
	var mv_hist: Array[float] = []
	for f: Dictionary in _frames:
		var ms: float = f["ms"]
		if bool(f["loading"]):
			load_n += 1
			load_worst = maxf(load_worst, ms)
			load_slow += 1 if ms > SLOW_MS else 0
		if bool(f["moving"]):
			mv_n += 1
			mv_worst = maxf(mv_worst, ms)
			if ms > SLOW_MS:
				mv_slow += 1
				mv_hist.append(ms)
				print("INTRO_PROBE slow moving frame %.1f ms at %d ms: %s" % [ms, int(f["t"]), str(f["what"])])
	var total: int = Time.get_ticks_msec() - _t0
	print("INTRO_PROBE world_shot=%s" % _saw_world_shot)
	print("INTRO_PROBE intro=%s world_ready_ms=%d control_ms=%d load_frames=%d load_worst_ms=%.1f load_frames_over_50ms=%d intro_moving_frames=%d intro_moving_worst_ms=%.1f intro_moving_over_50ms=%d %s" % [
		_with_intro, _ready_ms, total, load_n, load_worst, load_slow, mv_n, mv_worst, mv_slow, str(mv_hist.slice(0, 12))])
	get_tree().quit(0)
