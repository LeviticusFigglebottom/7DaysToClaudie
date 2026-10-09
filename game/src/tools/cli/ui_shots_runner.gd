extends Node
## Runner for ui_shots.gd: builds each screen on its own with a demo player and saves the frame.

const ALL: PackedStringArray = ["roll", "roll_campfire", "roll_hover", "menu", "options", "new_game", "manual",
	"loading", "pause", "intro_0", "intro_1", "intro_2", "intro_3", "intro_4", "intro_5", "intro_6", "intro_7", "intro_8", "intro_9"]

var _out: String = "res://../build/ui_shots"
var _only: PackedStringArray = []


func _ready() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	for i: int in args.size() - 1:
		if args[i] == "--out":
			_out = args[i + 1]
		elif args[i] == "--only":
			_only = args[i + 1].split(",", false)
	_run.call_deferred()


func _run() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(_out))
	Game.new_session({"game_mode": "survival", "seed": 4471})
	_fill_player(Game.local_player())
	for shot: String in ALL:
		if not _only.is_empty() and not _only.has(shot):
			continue
		var node: Node = null
		if shot.begins_with("intro_"):
			node = await _shot_intro(int(shot.get_slice("_", 1)))
		else:
			node = await call(&"_shot_" + shot)
		await _settle(12)
		var img: Image = get_viewport().get_texture().get_image()
		var path: String = ProjectSettings.globalize_path(_out).path_join(shot + ".png")
		img.save_png(path)
		print("UI_SHOT %s %s" % [shot, path])
		if node != null:
			node.queue_free()
		await _settle(2)
	print("UI_SHOT done")
	get_tree().quit(0)


func _settle(frames: int) -> void:
	for i: int in frames:
		await get_tree().process_frame


func _fill_player(p: PlayerState) -> void:
	for kv: Array in [["plant_fiber", 5], ["stick", 3], ["stone", 1], ["cloth", 1], ["stone_axe", 1], ["canned_beans", 2],
			["bandage", 1], ["empty_can", 2], ["yarrow", 1], ["torch", 1], ["water_bottle", 1], ["raw_meat", 2]]:
		if Content.item(StringName(kv[0])) != null:
			p.inventory.add_item(StringName(kv[0]), int(kv[1]))


func _ui_layer() -> CanvasLayer:
	var layer := CanvasLayer.new()
	add_child(layer)
	return layer


func _roll(mode: StringName, station: StringName) -> Node:
	var layer: CanvasLayer = _ui_layer()
	var roll := SalvageRoll.new()
	layer.add_child(roll)
	await _settle(1)
	roll.open(mode, station)
	return layer


func _shot_roll() -> Node:
	return await _roll(&"inventory", &"")


func _shot_roll_campfire() -> Node:
	return await _roll(&"station", &"campfire")


func _shot_roll_hover() -> Node:
	var layer: Node = await _roll(&"inventory", &"")
	await _settle(4)
	var roll: SalvageRoll = layer.get_child(0)
	# Hover the first slot: the item card shows beside it.
	var slots: Array = roll.get(&"_slots")
	if not slots.is_empty():
		var c: Vector3 = (slots[4] if slots.size() > 4 else slots[0])["center"]
		var at: Vector2 = roll.call(&"_screen", c)
		get_viewport().warp_mouse(at)
		Input.parse_input_event(_motion(at))
	return layer


func _motion(at: Vector2) -> InputEventMouseMotion:
	var m := InputEventMouseMotion.new()
	m.position = at
	m.global_position = at
	return m


func _shot_menu() -> Node:
	var menu: Node = (load("res://src/app/main.tscn") as PackedScene).instantiate()
	add_child(menu)
	await _settle(30)
	# The backdrop composes and builds on its own; wait for it to be faded in (or give up).
	var bd: Node = menu.get_node_or_null("Backdrop")
	var t0: int = Time.get_ticks_msec()
	while bd != null and (bd as CanvasItem).modulate.a < 1.0 and Time.get_ticks_msec() - t0 < 120000:
		await _settle(1)
	if bd != null:
		print("UI_SHOT menu backdrop after %d ms (alpha %.2f)" % [Time.get_ticks_msec() - t0, (bd as CanvasItem).modulate.a])
		await get_tree().create_timer(6.0).timeout
	return menu


func _shot_options() -> Node:
	var layer: CanvasLayer = _ui_layer()
	var p := OptionsPanel.new()
	layer.add_child(p)
	p.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	await _settle(2)
	p.position = (get_viewport().get_visible_rect().size - p.size) * 0.5
	return layer


func _shot_new_game() -> Node:
	var layer: CanvasLayer = _ui_layer()
	var p := NewGamePanel.new()
	layer.add_child(p)
	await _settle(2)
	p.position = (get_viewport().get_visible_rect().size - p.size) * 0.5
	return layer


func _shot_manual() -> Node:
	var layer: CanvasLayer = _ui_layer()
	var m := FieldManual.new()
	layer.add_child(m)
	await _settle(1)
	m.open("build")
	return layer


func _shot_intro(i: int) -> Node:
	var layer: CanvasLayer = _ui_layer()
	var intro := IntroPlayer.new()
	layer.add_child(intro)
	intro.play({}, IntroPlayer.vars_for(Game.session))
	intro.set_status("Shaping the valley…  42%")
	intro.show_card(i)
	await _settle(2)
	return layer


func _shot_loading() -> Node:
	var ui := GameUI.new()
	add_child(ui)
	await _settle(1)
	ui.show_loading("Shaping the valley…", 0.42)
	return ui


func _shot_pause() -> Node:
	var ui := GameUI.new()
	add_child(ui)
	await _settle(1)
	ui.hide_loading()
	(ui.get(&"_pause") as Control).visible = true
	return ui
