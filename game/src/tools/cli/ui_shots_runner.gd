extends Node
## Runner for ui_shots.gd: builds each screen on its own with a demo player and saves the frame.

const ALL: PackedStringArray = ["roll", "roll_campfire", "roll_hover", "menu", "options", "new_game", "manual",
	"loading", "pause", "trader", "death", "hud", "vignette", "intro_0", "intro_1", "intro_2", "intro_3", "intro_4", "intro_5", "intro_6", "intro_7", "intro_8", "intro_9"]

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


## A stand-in trader manager: one post with the Waystation 9 def, its stock, no board offers.
class FakeTraders:
	extends Node
	var posts: Dictionary = {}

	func stock_of(_tid: StringName, _post: String) -> Dictionary:
		# Three of each of a few early items, as a restocked counter shows them.
		var out: Dictionary = {}
		for k: String in ["canned_beans", "cloth_bandage", "water_bottle", "torch", "stone_axe", "cordage"]:
			if Content.item(StringName(k)) != null:
				out[StringName(k)] = {"count": 3, "rep_tier": 2 if k == "stone_axe" else 0}
		return out

	func board_offers(_p: PlayerState, _td: TraderDef) -> Array:
		return []


func _shot_trader() -> Node:
	var layer: CanvasLayer = _ui_layer()
	var fake := FakeTraders.new()
	fake.posts = {"wp9": {"def": Content.get_def(&"trader", &"waystation_9")}}
	layer.add_child(fake)
	var t := TraderScreen.new()
	t.manager = fake
	layer.add_child(t)
	await _settle(1)
	t.open("wp9", "shop")
	return layer


func _shot_death() -> Node:
	var ui := GameUI.new()
	add_child(ui)
	await _settle(1)
	ui.hide_loading()
	ui.show_death("zombie", "Your pack lies where you fell.")
	await get_tree().create_timer(2.3).timeout
	return ui


## The HUD with a toolbelt and a few messages over a mid-grey field (no world).
func _shot_hud() -> Node:
	var bg := ColorRect.new()
	bg.color = Color(0.32, 0.36, 0.3)
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var layer: CanvasLayer = _ui_layer()
	layer.layer = 0
	layer.add_child(bg)
	var ui := GameUI.new()
	add_child(ui)
	await _settle(1)
	ui.hide_loading()
	var p: PlayerState = Game.local_player()
	p.toolbelt[0] = &"stone_axe"
	p.toolbelt[1] = &"torch"
	p.equipped_slot = 0
	ui.message("Journal: Make a stone axe ✓   Next: Fell a tree ([B])", &"level")
	ui.message("Picked up 3 Stick.", &"info")
	if ui.has_method(&"show_belt"):
		ui.call(&"show_belt")
	await _settle(4)
	bg.set_meta(&"ui", ui)
	return layer


## The HUD's hurt and cold edges at once (the vignette shader), over a mid-grey field.
func _shot_vignette() -> Node:
	var layer: Node = await _shot_hud()
	var ui: GameUI = (layer.get_child(0) as Node).get_meta(&"ui")
	var vm: ShaderMaterial = (ui.get(&"_vignette") as CanvasItem).material
	vm.set_shader_parameter("damage", 0.6)
	vm.set_shader_parameter("cold", 0.7)
	(ui.get(&"_hum_label") as Label).text = "THE HUM IN 05:42"
	await _settle(3)
	return layer
