extends Node
## The menu freeze guard's runner (menu_guard.gd): loads main.tscn as the running scene, so the
## real menu (backdrop, music, What's New) runs, then for `--seconds` hovers every entry and opens
## and closes New Game, Random World, Options, What's New and Load (when there are saves) by fake
## mouse events through Input, as a player's mouse would. It times every frame and fails when one
## is longer than `--limit` seconds, or when the menu stops answering (a hover or a click that
## nothing answers within INPUT_TIMEOUT). Classes are named by their scripts' global names, so a
## pack older than this script still runs it.

## Entries that open a panel over the menu (the menu list hides while one is open).
const OPENERS: PackedStringArray = ["New Game", "Random World", "Options", "What's New", "Load"]
## Entries only hovered: they would leave the menu (a run, the intro, quitting).
const HOVER_ONLY: PackedStringArray = ["Continue", "The Intro", "Quit", "Vertical Slice"]
## Seconds a hover or a click may go unanswered before the menu counts as stuck.
const INPUT_TIMEOUT: float = 3.0
## How long the pictures may take to load before the backdrop counts as having none.
const PICTURE_WAIT: float = 10.0
## Seconds with no frame at all before the watchdog calls the menu frozen and ends the run (Build
## #98's live backdrop stopped the main thread for minutes: no frame ever came back to report).
const STALL: float = 20.0

var seconds: float = 20.0
var limit: float = 1.5
var expect_pictures: bool = false
## A player's menu (no developer entries, even from the editor's binary): every entry must fit.
var player: bool = false
## A saved run in place first, so the menu has Continue and Load… (a player's longest menu).
var with_continue: bool = false
const PROBE_SLOT: String = "menu_guard_probe"
## A PNG of the menu as it first settles (--shot <path>), for the record.
var shot: String = ""

var _main: Control
var _list: Control
var _phase: String = "boot"
var _last_us: int = 0
var _frames: PackedFloat32Array = []
var _worst: float = 0.0
var _worst_phase: String = ""
var _slow: Array[String] = []
var _failures: Array[String] = []
## Kept apart until the end, so a build without pictures still has its input and frames tested.
var _backdrop_fail: Array[String] = []
var _mouse: Vector2 = Vector2.ZERO
var _watchdog: Thread
var _watching: bool = true


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	process_priority = -1000
	var args: PackedStringArray = OS.get_cmdline_user_args()
	for i: int in args.size():
		match args[i]:
			"--seconds": seconds = float(args[i + 1])
			"--limit": limit = float(args[i + 1])
			"--expect-pictures": expect_pictures = true
			"--player": player = true
			"--with-continue": with_continue = true
			"--shot": shot = args[i + 1]
	_watchdog = Thread.new()
	_watchdog.start(_watch)
	_run.call_deferred()


func _exit_tree() -> void:
	_watching = false
	if _watchdog != null and _watchdog.is_started():
		_watchdog.wait_to_finish()


## On its own thread: a main thread that draws no frame for STALL seconds is reported and the run
## ended, so a frozen menu fails with a reason instead of hanging until a CI timeout.
func _watch() -> void:
	while _watching:
		OS.delay_msec(500)
		var last: int = _last_us
		if last > 0 and float(Time.get_ticks_usec() - last) / 1e6 > STALL:
			print("MENU_GUARD FAIL: the menu froze: no frame for %.0f s (during %s)" % [STALL, _phase])
			print("MENU_GUARD done: FAIL (frozen)")
			OS.kill(OS.get_process_id())
			return


func _process(_delta: float) -> void:
	var now: int = Time.get_ticks_usec()
	if _last_us > 0:
		var dt: float = float(now - _last_us) / 1e6
		_frames.append(dt)
		if dt > _worst:
			_worst = dt
			_worst_phase = _phase
		if dt > limit:
			_slow.append("%.2f s (%s)" % [dt, _phase])
	_last_us = now


func _run() -> void:
	print("MENU_GUARD start: %s, renderer %s, %.0f s, limit %.2f s" % [DisplayServer.get_name(),
		RenderingServer.get_current_rendering_driver_name(), seconds, limit])
	if with_continue:
		_write_probe_save()
	var scene := load("res://src/app/main.tscn") as PackedScene
	_main = scene.instantiate() as Control
	get_tree().root.add_child(_main)
	get_tree().current_scene = _main
	_list = _main.get_node("%Buttons") as Control
	await _frames_pass(10)
	# A new build's notes open by themselves once: close them like a player would.
	_phase = "what's new (opened by itself)"
	var auto: Control = _panel()
	if auto != null:
		print("MENU_GUARD what's new opened by itself")
		await _close(auto, "What's New (auto)")
	_phase = "backdrop"
	await _report_backdrop()
	_check_fit()
	if shot != "":
		await _seconds(2.5)
		get_viewport().get_texture().get_image().save_png(shot)
		print("MENU_GUARD shot %s" % shot)
	var start: int = Time.get_ticks_msec()
	var rounds: int = 0
	while Time.get_ticks_msec() - start < int(seconds * 1000.0) and _failures.is_empty():
		rounds += 1
		# By index, fetched afresh each time: closing Load… rebuilds the list (a run deleted there).
		var i: int = 0
		while i < _entries().size() and _failures.is_empty():
			var b: Button = _entries()[i]
			i += 1
			var name: String = b.text
			# The editor's dev entry pushes the list down: the last can sit below a 720p window
			# (a player's menu that does so fails in _check_fit).
			if not get_viewport().get_visible_rect().has_point(b.get_global_rect().get_center()):
				continue
			_phase = "hover %s" % name
			if not await _hover(b):
				_failures.append("hovering %s at %s: the menu never answered (%.0f s)" % [name, str(b.get_global_rect()) if is_instance_valid(b) else "(freed)", INPUT_TIMEOUT])
				break
			if not _opens(name):
				continue
			_phase = "open %s" % name
			if not await _click(b, func() -> bool: return not _list.visible):
				_failures.append("clicking %s: nothing opened (%.0f s)" % [name, INPUT_TIMEOUT])
				break
			var panel: Control = _panel()
			_phase = "in %s" % name
			if rounds == 1:
				await _frames_pass(2)
				_check_panel_buttons(panel, name)
			# Look around it for a moment (the backdrop keeps moving behind it).
			if panel != null:
				var r: Rect2 = panel.get_global_rect()
				for k: int in 6:
					_move(r.position + r.size * Vector2(randf(), randf()))
					await _frames_pass(4)
			await _seconds(0.5)
			_phase = "close %s" % name
			await _close(panel, name)
			# A list rebuilt on closing (Load…) lays its new entries out over the next frames.
			await _frames_pass(3)
	var report := _report(rounds)
	_failures.append_array(_backdrop_fail)
	print(report)
	_finish()


## Every entry inside the window and above the version line. A player's menu (--player) that
## doesn't fit fails; the editor's (one more entry) is only noted.
func _check_fit() -> void:
	var view: Rect2 = get_viewport().get_visible_rect()
	var status: Control = _main.get_node_or_null("%Status") as Control
	var floor_y: float = status.get_global_rect().position.y if status != null and status.text != "" else view.end.y
	var names: PackedStringArray = []
	var bad: PackedStringArray = []
	for b: Button in _entries():
		names.append(b.text)
		var r: Rect2 = b.get_global_rect()
		if not view.encloses(r) or r.end.y > floor_y + 0.5:
			bad.append("%s (%d-%d px)" % [b.text, int(r.position.y), int(r.end.y)])
	print("MENU_GUARD menu: %d entries at %s%s: %s" % [names.size(), str(view.size), "" if player else " (developer menu)", ", ".join(names)])
	if bad.is_empty():
		return
	var msg: String = "entries off the window or over the version line (from %d px): %s" % [int(floor_y), ", ".join(bad)]
	if player:
		_failures.append(msg)
	else:
		print("MENU_GUARD note: %s" % msg)


func _write_probe_save() -> void:
	var dir: String = "user://saves".path_join(PROBE_SLOT)
	DirAccess.make_dir_recursive_absolute(dir)
	var f := FileAccess.open(dir.path_join("meta.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify({"slot": PROBE_SLOT, "day": 3, "hour": 9.0, "saved_unix": int(Time.get_unix_time_from_system()),
		"play_seconds": 600, "preset": "normal", "world_mode": "main"}))
	f.close()


func _remove_probe_save() -> void:
	var dir: String = "user://saves".path_join(PROBE_SLOT)
	if DirAccess.dir_exists_absolute(dir):
		for n: String in DirAccess.get_files_at(dir):
			DirAccess.remove_absolute(dir.path_join(n))
		DirAccess.remove_absolute(dir)


func _finish() -> void:
	if with_continue:
		_remove_probe_save()
	for f: String in _failures:
		print("MENU_GUARD FAIL: %s" % f)
	print("MENU_GUARD done: %s" % ("PASS" if _failures.is_empty() else "FAIL (%d)" % _failures.size()))
	# A clean exit (CI reads the log): the menu's music let go and the menu freed first, else the
	# engine reports its stream "still in use at exit".
	var code: int = _failures.size()
	_watching = false
	if is_instance_valid(_main):
		var music: AudioStreamPlayer = _main.get_node_or_null("Music") as AudioStreamPlayer
		if music != null:
			music.stop()
			music.stream = null
		_main.queue_free()
	for i: int in 4:
		await get_tree().process_frame
	get_tree().quit(code)


## The menu's entries, top to bottom (only ones on screen).
func _entries() -> Array[Button]:
	var out: Array[Button] = []
	for c: Node in _list.get_children():
		var b := c as Button
		if b != null and b.visible and not b.is_queued_for_deletion():
			out.append(b)
	return out


func _opens(text: String) -> bool:
	for k: String in HOVER_ONLY:
		if text.begins_with(k):
			return false
	for k: String in OPENERS:
		if text.begins_with(k):
			return true
	return false


## The panel open over the menu: the newest child of the menu that is a panel (New Game, Options,
## What's New, Load), or null.
func _panel() -> Control:
	var kids: Array[Node] = _main.get_children()
	for i: int in range(kids.size() - 1, -1, -1):
		var c := kids[i] as Control
		if c == null or c.is_queued_for_deletion() or not c.visible:
			continue
		var s: Script = c.get_script() as Script
		var cls: String = s.get_global_name() if s != null else ""
		if cls in ["NewGamePanel", "OptionsPanel", "WhatsNewPanel", "LoadPanel"]:
			return c
	return null


## A panel's way out and its way on (Back, Close, Start) must lie inside the window: World's
## longer map label once widened New Game past 1280 px and pushed Back off screen, and its
## 760 px height put Back and Start under a 720p window's edge.
func _check_panel_buttons(panel: Control, what: String) -> void:
	if panel == null:
		return
	var view: Rect2 = get_viewport().get_visible_rect()
	var out: PackedStringArray = []
	for c: Node in panel.find_children("*", "Button", true, false):
		var b := c as Button
		if b != null and b.is_visible_in_tree() and b.text in ["Back", "Close", "Start"]:
			var r: Rect2 = b.get_global_rect()
			if not view.encloses(r):
				out.append("%s at %s" % [b.text, str(r)])
	print("MENU_GUARD panel %s: %s, %s" % [what, str(panel.get_global_rect()), "buttons inside the window" if out.is_empty() else "OUT: " + ", ".join(out)])
	if not out.is_empty():
		_failures.append("%s: %s outside the %s window" % [what, ", ".join(out), str(view.size)])


## Closes a panel by its own Back / Close button, clicked; Esc if it has none on screen.
func _close(panel: Control, what: String) -> void:
	if panel == null:
		return
	var back: Button = _find_button(panel, ["Back", "Close"])
	# By id: a lambda holding the panel itself errors once the panel is freed.
	var pid: int = panel.get_instance_id()
	var closed := func() -> bool:
		var p: Control = instance_from_id(pid) as Control
		return _list.visible and (p == null or p.is_queued_for_deletion() or not p.is_inside_tree())
	var ok: bool
	if back != null and get_viewport().get_visible_rect().has_point(back.get_global_rect().get_center()):
		ok = await _click(back, closed)
	else:
		_key(KEY_ESCAPE)
		ok = await _wait(closed)
	if not ok:
		_failures.append("closing %s: it never closed (%.0f s)" % [what, INPUT_TIMEOUT])


func _find_button(n: Node, texts: Array) -> Button:
	for c: Node in n.find_children("*", "Button", true, false):
		var b := c as Button
		if b != null and b.is_visible_in_tree() and b.text in texts:
			return b
	return null


# --- Input, as a player's mouse makes it ---------------------------------------------------------

func _move(to: Vector2) -> void:
	var m := InputEventMouseMotion.new()
	m.position = to
	m.global_position = to
	m.relative = to - _mouse
	_mouse = to
	Input.parse_input_event(m)


func _button(pressed: bool) -> void:
	var e := InputEventMouseButton.new()
	e.position = _mouse
	e.global_position = _mouse
	e.button_index = MOUSE_BUTTON_LEFT
	e.button_mask = MOUSE_BUTTON_MASK_LEFT if pressed else 0
	e.pressed = pressed
	Input.parse_input_event(e)


func _key(code: Key) -> void:
	for down: bool in [true, false]:
		var k := InputEventKey.new()
		k.keycode = code
		k.physical_keycode = code
		k.pressed = down
		Input.parse_input_event(k)


func _hover(b: Button) -> bool:
	_move(b.get_global_rect().get_center())
	var bid: int = b.get_instance_id()
	return await _wait(func() -> bool:
		var bb: Button = instance_from_id(bid) as Button
		return bb != null and bb.is_hovered())


func _click(b: Button, answered: Callable) -> bool:
	_move(b.get_global_rect().get_center())
	await _frames_pass(2)
	_button(true)
	await _frames_pass(2)
	_button(false)
	return await _wait(answered)


func _wait(cond: Callable) -> bool:
	var end: int = Time.get_ticks_msec() + int(INPUT_TIMEOUT * 1000.0)
	while Time.get_ticks_msec() < end:
		if cond.call():
			return true
		await get_tree().process_frame
	return bool(cond.call())


func _frames_pass(n: int) -> void:
	for i: int in n:
		await get_tree().process_frame


func _seconds(s: float) -> void:
	var end: int = Time.get_ticks_msec() + int(s * 1000.0)
	while Time.get_ticks_msec() < end:
		await get_tree().process_frame


# --- Reports ------------------------------------------------------------------------------------

## What the backdrop shows: its pictures loaded, none (no generated stills), or off/headless.
func _report_backdrop() -> void:
	var bd: Control = _main.get_node_or_null("Backdrop") as Control
	if bd == null:
		print("MENU_GUARD backdrop: none (Options sets it off)")
		if expect_pictures:
			_backdrop_fail.append("backdrop: none, and pictures were expected")
		return
	# A pack from before ADR-0065 has the live 3D backdrop: no pictures to report.
	if bd.get(&"_paths") == null:
		print("MENU_GUARD backdrop: a live 3D scene (a build from before the pictures, ADR-0065)")
		if expect_pictures:
			_backdrop_fail.append("backdrop: a live 3D scene, and pictures were expected")
		return
	var paths: PackedStringArray = bd.get(&"_paths")
	var end: int = Time.get_ticks_msec() + int(PICTURE_WAIT * 1000.0)
	while Time.get_ticks_msec() < end and not paths.is_empty() and (bd.get(&"_textures") as Array).size() < paths.size():
		await get_tree().process_frame
	var loaded: int = (bd.get(&"_textures") as Array).size()
	var state: String
	if DisplayServer.get_name() == "headless":
		state = "headless (draws nothing)"
	elif paths.is_empty():
		state = "no pictures (no generated stills: the menu stays plain)"
	else:
		state = "%d of %d pictures loaded, mode %s" % [loaded, paths.size(), str(bd.get(&"mode"))]
	print("MENU_GUARD backdrop: %s" % state)
	if expect_pictures and (paths.is_empty() or loaded < paths.size()):
		_backdrop_fail.append("backdrop: %s, and pictures were expected" % state)


func _report(rounds: int) -> String:
	if _frames.is_empty():
		_failures.append("no frames were drawn")
		return "MENU_GUARD frames: none"
	var sorted: PackedFloat32Array = _frames.duplicate()
	sorted.sort()
	var total: float = 0.0
	for f: float in _frames:
		total += f
	var p99: float = sorted[mini(sorted.size() - 1, int(sorted.size() * 0.99))]
	if not _slow.is_empty():
		_failures.append("%d frame(s) over %.2f s: %s" % [_slow.size(), limit, ", ".join(_slow.slice(0, 8))])
	return "MENU_GUARD frames: %d in %.1f s over %d round(s), mean %.1f ms (%.0f fps), p99 %.1f ms, worst %.0f ms (%s)" % [
		_frames.size(), total, rounds, total / _frames.size() * 1000.0, _frames.size() / maxf(total, 0.001),
		p99 * 1000.0, _worst * 1000.0, _worst_phase]
