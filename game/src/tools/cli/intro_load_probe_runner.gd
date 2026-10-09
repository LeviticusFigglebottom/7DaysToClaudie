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


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	# Last in the frame: a frame's time is everything the tree did since the previous one.
	process_priority = 100000
	var args: PackedStringArray = OS.get_cmdline_user_args()
	_with_intro = args.has("--intro")
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
	var intro: Object = ui.get(&"intro") if ui != null else null
	var moving: bool = intro != null and (intro as Node).is_inside_tree() and bool(intro.call(&"is_playing")) and not bool(intro.call(&"is_calm"))
	var loading: bool = w == null or not bool(w.get(&"is_ready"))
	if not loading and _ready_ms < 0:
		_ready_ms = Time.get_ticks_msec() - _t0
	_frames.append({"ms": ms, "moving": moving, "loading": loading, "intro": intro != null})
	var intro_over: bool = not _with_intro or (ui != null and ui.get(&"intro") == null and _frames.size() > 10)
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
	var total: int = Time.get_ticks_msec() - _t0
	print("INTRO_PROBE intro=%s world_ready_ms=%d control_ms=%d load_frames=%d load_worst_ms=%.1f load_frames_over_50ms=%d intro_moving_frames=%d intro_moving_worst_ms=%.1f intro_moving_over_50ms=%d %s" % [
		_with_intro, _ready_ms, total, load_n, load_worst, load_slow, mv_n, mv_worst, mv_slow, str(mv_hist.slice(0, 12))])
	get_tree().quit(0)
