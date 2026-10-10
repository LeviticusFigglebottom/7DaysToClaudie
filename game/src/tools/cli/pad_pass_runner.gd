extends Node
## Runner for pad_pass.gd: every step sends gamepad buttons and sticks through Input, as a pad
## would, and checks what opened, what closed and what holds the focus.

var _fails: Array[String] = []
var _main: Node


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_run.call_deferred()


func _run() -> void:
	get_viewport().disable_3d = true
	var scene := load("res://src/app/main.tscn") as PackedScene
	_main = scene.instantiate()
	get_tree().root.add_child(_main)
	get_tree().current_scene = _main
	await _frames(20)
	# What's New may open by itself: B closes it.
	if _main.get_node_or_null("WhatsNewPanel") != null or _panel_named("WhatsNewPanel") != null:
		await _press(JOY_BUTTON_B)
	# --- Menu: the d-pad walks the entries, A opens New Game.
	await _press(JOY_BUTTON_DPAD_DOWN)
	var ng: bool = await _focus_to(func(c: Control) -> bool: return c is Button and (c as Button).text.begins_with("New Game"), JOY_BUTTON_DPAD_DOWN, 12)
	_step("menu: d-pad reaches New Game", ng)
	await _press(JOY_BUTTON_A)
	await _frames(6)
	var panel: Control = _panel_named("NewGamePanel")
	_step("menu: A opens New Game", panel != null)
	if panel == null:
		return _finish()
	# --- New Game: walk the focus to Start.
	var start: bool = await _focus_to(func(c: Control) -> bool: return c is Button and (c as Button).text == "Start", JOY_BUTTON_DPAD_DOWN, 120)
	if not start:
		start = await _focus_to(func(c: Control) -> bool: return c is Button and (c as Button).text == "Start", JOY_BUTTON_DPAD_RIGHT, 20)
	_step("New Game: d-pad reaches Start", start)
	if not start:
		return _finish()
	await _press(JOY_BUTTON_A)
	# --- The intro: hold B to skip.
	var game: Node = get_node("/root/Game")
	var ui: Node = null
	var end: int = Time.get_ticks_msec() + 60000
	while Time.get_ticks_msec() < end:
		var w: Node = game.get(&"world")
		ui = w.get(&"ui") if w != null else null
		if ui != null and ui.get(&"intro") != null:
			break
		await get_tree().process_frame
	var had_intro: bool = ui != null and ui.get(&"intro") != null
	_step("new game: the intro plays", had_intro)
	if had_intro:
		await _hold(JOY_BUTTON_B, 1.6)
		await _frames(30)
		_step("intro: holding B skips it", not bool(ui.call(&"is_intro_playing")))
	end = Time.get_ticks_msec() + 900000
	while Time.get_ticks_msec() < end and not bool(game.world.is_ready):
		await get_tree().process_frame
	_step("the world loads", bool(game.world.is_ready))
	if not bool(game.world.is_ready):
		return _finish()
	await _seconds(3.0)
	var w2: Node = game.world
	ui = w2.ui
	var p: Node3D = w2.player
	# --- Look: the right stick turns the player.
	var yaw0: float = p.rotation.y
	await _stick(JOY_AXIS_RIGHT_X, 1.0, 0.6)
	_step("right stick looks (yaw %.2f -> %.2f)" % [yaw0, p.rotation.y], absf(p.rotation.y - yaw0) > 0.3)
	# --- Field manual (d-pad up), its Journal tab, B out.
	var manual: Node = ui.get(&"manual")
	await _press(JOY_BUTTON_DPAD_UP)
	await _frames(6)
	_step("d-pad up opens the field manual", bool(manual.call(&"is_open")))
	var belt0: int = int(p.get(&"state").equipped_slot)
	await _press(JOY_BUTTON_RIGHT_SHOULDER)
	await _frames(4)
	_step("field manual: RB turns to the Journal tab (%s)" % str(manual.get(&"_tab")), str(manual.get(&"_tab")) == "journal")
	_step("field manual: RB didn't step the toolbelt behind it", int(p.get(&"state").equipped_slot) == belt0)
	var card: bool = await _focus_to(func(c: Control) -> bool: return c is Button, JOY_BUTTON_DPAD_DOWN, 3)
	_step("field manual: the d-pad reaches the journal's cards", card)
	await _press(JOY_BUTTON_B)
	await _frames(6)
	_step("B closes the field manual", not bool(manual.call(&"is_open")))
	# --- The roll (Y), its recipe sheet (RB), a craft (A), B out.
	var roll: Node = ui.get(&"roll")
	await _press(JOY_BUTTON_Y)
	await _frames(8)
	_step("Y opens the salvage roll", bool(roll.call(&"is_open")))
	await _stick(JOY_AXIS_LEFT_X, 1.0, 0.3)
	_step("left stick walks the cloth (pad cursor %s)" % str(roll.get(&"_pad_index")), int(roll.get(&"_pad_index")) >= 0)
	await _press(JOY_BUTTON_RIGHT_SHOULDER)
	await _frames(4)
	var f: Control = get_viewport().gui_get_focus_owner()
	_step("RB moves to the recipe sheet (focus: %s)" % _name(f), f != null and _inside(f, roll.get(&"_sheet")))
	var sheet: Node = roll.get(&"_sheet")
	var sel0: StringName = sheet.call(&"selected")
	await _press(JOY_BUTTON_DPAD_DOWN)
	await _press(JOY_BUTTON_DPAD_DOWN)
	await _frames(3)
	var sel1: StringName = sheet.call(&"selected")
	_step("d-pad picks another recipe on the sheet (%s -> %s)" % [sel0, sel1], sel1 != sel0)
	await _press(JOY_BUTTON_B)
	await _frames(6)
	_step("B closes the roll", not bool(roll.call(&"is_open")))
	# --- The map (Back), B out.
	var map: Node = ui.get(&"world_map")
	await _press(JOY_BUTTON_BACK)
	await _frames(8)
	_step("Back opens the map", map != null and bool(map.call(&"is_open")))
	await _press(JOY_BUTTON_B)
	await _frames(6)
	_step("B closes the map", map == null or not bool(map.call(&"is_open")))
	# --- Pause (Start), the d-pad to Resume, A.
	var pause: Control = ui.get(&"_pause")
	await _press(JOY_BUTTON_START)
	await _frames(6)
	_step("Start pauses", pause.visible)
	var rs: bool = await _focus_to(func(c: Control) -> bool: return c is Button and (c as Button).text == "Resume", JOY_BUTTON_DPAD_DOWN, 10)
	_step("pause: the d-pad reaches Resume", rs)
	await _press(JOY_BUTTON_A)
	await _frames(6)
	_step("A on Resume unpauses", not pause.visible and not get_tree().paused)
	# --- Attack (RT) and the toolbelt (RB).
	var slot0: int = int(p.get(&"state").equipped_slot)
	await _press(JOY_BUTTON_RIGHT_SHOULDER)
	await _frames(4)
	_step("RB steps the toolbelt (%d -> %d)" % [slot0, int(p.get(&"state").equipped_slot)], int(p.get(&"state").equipped_slot) != slot0)
	_axis(JOY_AXIS_TRIGGER_RIGHT, 1.0)
	await _frames(3)
	_step("RT is attack", Input.is_action_pressed(&"attack"))
	_axis(JOY_AXIS_TRIGGER_RIGHT, 0.0)
	await _frames(4)
	# --- Reload: X held with a gun in hand and nothing in reach (looking at the sky).
	var ps: Object = p.get(&"state")
	ps.inventory.add_item(&"hunting_rifle", 1)
	ps.inventory.add_item(&"ammo_308", 5)
	ps.toolbelt[5] = &"hunting_rifle"
	p.get(&"equipment").call(&"select_slot", 5)
	await _stick(JOY_AXIS_RIGHT_Y, -1.0, 1.2)
	await _frames(4)
	var aimed_at: Variant = p.get(&"interaction").get(&"target")
	_step("looking up, nothing in reach (%s)" % str(aimed_at), aimed_at == null)
	await _press(JOY_BUTTON_X)
	_step("a tap of X with a gun doesn't reload", not bool(p.get(&"equipment").call(&"is_reloading")))
	await _hold(JOY_BUTTON_X, 0.7)
	_step("X held with a gun reloads", bool(p.get(&"equipment").call(&"is_reloading")))
	await _seconds(0.3)
	# --- Placing a blueprint: LB/RB turn the piece, the toolbelt stays put, B cancels.
	var b: Node = w2.get(&"building")
	b.call(&"begin_placement", &"campfire")
	var belt1: int = int(ps.equipped_slot)
	var yaw1: float = float(b.get(&"_place_yaw"))
	await _press(JOY_BUTTON_RIGHT_SHOULDER)
	await _frames(3)
	var yaw2: float = float(b.get(&"_place_yaw"))
	_step("placing: RB turns the piece (%.2f -> %.2f)" % [yaw1, yaw2], yaw2 > yaw1)
	await _press(JOY_BUTTON_LEFT_SHOULDER)
	await _frames(3)
	_step("placing: LB turns it back", is_equal_approx(float(b.get(&"_place_yaw")), yaw1))
	_step("placing: LB/RB left the toolbelt alone", int(ps.equipped_slot) == belt1)
	await _press(JOY_BUTTON_B)
	await _frames(3)
	_step("placing: B cancels", not bool(b.call(&"is_placing")))
	_finish()


func _finish() -> void:
	for f: String in _fails:
		print("PAD FAIL: %s" % f)
	print("PAD done: %s" % ("PASS" if _fails.is_empty() else "FAIL (%d)" % _fails.size()))
	get_tree().quit(_fails.size())


func _step(what: String, ok: bool) -> void:
	print("PAD %s  %s  (focus: %s)" % ["OK  " if ok else "FAIL", what, _name(get_viewport().gui_get_focus_owner())])
	if not ok:
		_fails.append(what)


# --- Pad input -------------------------------------------------------------------------------

func _press(button: JoyButton) -> void:
	await _hold(button, 0.08)


func _hold(button: JoyButton, secs: float) -> void:
	_button(button, true)
	await _seconds(secs)
	_button(button, false)
	await _frames(2)


func _button(button: JoyButton, down: bool) -> void:
	var e := InputEventJoypadButton.new()
	e.device = 0
	e.button_index = button
	e.pressed = down
	e.pressure = 1.0 if down else 0.0
	Input.parse_input_event(e)


func _axis(axis: JoyAxis, value: float) -> void:
	var m := InputEventJoypadMotion.new()
	m.device = 0
	m.axis = axis
	m.axis_value = value
	Input.parse_input_event(m)


func _stick(axis: JoyAxis, value: float, secs: float) -> void:
	_axis(axis, value)
	await _seconds(secs)
	_axis(axis, 0.0)
	await _frames(2)


## Presses `button` until the focus is on a control `want` accepts (at most `tries` presses).
func _focus_to(want: Callable, button: JoyButton, tries: int) -> bool:
	for i: int in tries:
		var f: Control = get_viewport().gui_get_focus_owner()
		if f != null and want.call(f):
			return true
		await _press(button)
		await _frames(1)
	var f2: Control = get_viewport().gui_get_focus_owner()
	return f2 != null and want.call(f2)


func _panel_named(cls: String) -> Control:
	for c: Node in _main.get_children():
		var s: Script = c.get_script() as Script
		if s != null and s.get_global_name() == cls and not c.is_queued_for_deletion():
			return c as Control
	return null


func _inside(n: Node, root_node: Variant) -> bool:
	return root_node is Node and (root_node == n or (root_node as Node).is_ancestor_of(n))


func _name(c: Control) -> String:
	if c == null:
		return "nothing"
	return ("%s '%s'" % [c.get_class(), (c as Button).text]) if c is Button else c.get_class()


func _frames(n: int) -> void:
	for i: int in n:
		await get_tree().process_frame


func _seconds(s: float) -> void:
	var end: int = Time.get_ticks_msec() + int(s * 1000.0)
	while Time.get_ticks_msec() < end:
		await get_tree().process_frame
