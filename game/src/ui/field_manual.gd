class_name FieldManual
extends Control
## The Remand Program Field Manual (guidebook, B): a dog-eared printed booklet issued with the
## tether. Blueprints to lay out (shelter, crafting, defence, walls), notes you have read, and
## the program's survival pages. Choosing "Lay it out" hands the blueprint to the building
## placement ghost and closes the book.

const PAPER := Color(0.86, 0.82, 0.71)
const INK := Color(0.15, 0.12, 0.09)
const INK_DIM := Color(0.45, 0.4, 0.34)
const TIPS: Array[Array] = [
	["The Remand Program", "You signed the waiver. You are inside the Cordon to find out what the Bloom did to Hollowmere and whether anyone is left. The canister drop is your only resupply. Your tether keeps time, vitals and the Hum forecast."],
	["Hollowed", "By day they are slow and half blind. After dark they see without light and they run. Anything you carry that glows tells them where you are. Crouch, keep your lights off, and let the wind carry your scent away from them."],
	["The Hum", "Every few nights the ground hums and the Hollowed answer from every side. They remember what killed them last time and where your walls held. Build where you can see them coming. Spikes slow them; logs make them work; nothing stops them forever."],
	["Shelter", "A lean-to and a bough bed mark your place in the world: sleep there to rest, save, and wake there if the worst happens. Fire keeps you warm and dries you — and every Hollowed for half a kilometre can see it."],
	["Building with logs", "Fell trees with an axe; carry two logs at most. Lay a blueprint from this manual and fill its ghost, or set logs freely: they notch onto each other (R turns the log, V stands it up or pitches it for a roof). A log needs something under it or beside it — what nothing holds up, falls."],
	["Hammer", "A claw hammer repairs what the Hollowed break (sticks and nails), and reinforces logs once they are whole (cordage and nails)."],
]

var _open: bool = false
var _tabs: HBoxContainer
var _list: VBoxContainer
var _detail: RichTextLabel
var _action: Button
var _tab: String = "build"
var _selected: Variant = null


func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	visible = false
	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.5)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(dim)
	var book := PanelContainer.new()
	book.anchor_left = 0.14
	book.anchor_right = 0.86
	book.anchor_top = 0.08
	book.anchor_bottom = 0.92
	var sb := StyleBoxTexture.new()
	var tex_path: String = "res://assets/generated/textures/ui_paper_page.png"
	if ResourceLoader.exists(tex_path):
		sb.texture = load(tex_path)
		sb.content_margin_left = 40
		sb.content_margin_right = 40
		sb.content_margin_top = 30
		sb.content_margin_bottom = 30
		book.add_theme_stylebox_override(&"panel", sb)
	else:
		var flat := StyleBoxFlat.new()
		flat.bg_color = PAPER
		flat.content_margin_left = 40
		flat.content_margin_right = 40
		flat.content_margin_top = 30
		flat.content_margin_bottom = 30
		flat.shadow_size = 12
		flat.shadow_color = Color(0, 0, 0, 0.5)
		book.add_theme_stylebox_override(&"panel", flat)
	add_child(book)
	var v := VBoxContainer.new()
	v.add_theme_constant_override(&"separation", 12)
	book.add_child(v)
	var title := Label.new()
	title.text = "REMAND PROGRAM — FIELD MANUAL  (rev. 3)"
	title.add_theme_font_size_override(&"font_size", 24)
	title.add_theme_color_override(&"font_color", INK)
	v.add_child(title)
	_tabs = HBoxContainer.new()
	_tabs.add_theme_constant_override(&"separation", 18)
	v.add_child(_tabs)
	for t: Array in [["build", "Blueprints"], ["notes", "Notes found"], ["tips", "Survival"]]:
		var b := Button.new()
		b.text = t[1]
		b.flat = true
		b.add_theme_color_override(&"font_color", INK)
		b.add_theme_font_size_override(&"font_size", 18)
		b.pressed.connect(_set_tab.bind(str(t[0])))
		_tabs.add_child(b)
	var h := HBoxContainer.new()
	h.size_flags_vertical = Control.SIZE_EXPAND_FILL
	h.add_theme_constant_override(&"separation", 24)
	v.add_child(h)
	var scroll := ScrollContainer.new()
	scroll.custom_minimum_size = Vector2(320, 0)
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	h.add_child(scroll)
	_list = VBoxContainer.new()
	_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(_list)
	var right := VBoxContainer.new()
	right.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	h.add_child(right)
	_detail = RichTextLabel.new()
	_detail.bbcode_enabled = true
	_detail.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_detail.add_theme_color_override(&"default_color", INK)
	_detail.add_theme_font_size_override(&"normal_font_size", 17)
	right.add_child(_detail)
	_action = Button.new()
	_action.text = "Lay it out"
	_action.custom_minimum_size = Vector2(200, 40)
	_action.pressed.connect(_on_action)
	right.add_child(_action)
	Events.ui_modal_closed.connect(func(id: StringName) -> void:
		if id == &"field_manual" and _open:
			_open = false
			visible = false)


func _set_tab(t: String) -> void:
	_tab = t
	_selected = null
	_refresh()


func open(tab: String = "build") -> void:
	_tab = tab
	_open = true
	visible = true
	_selected = null
	_refresh()
	var ui: Node = get_parent()
	if ui != null and ui.has_method(&"push_modal"):
		ui.call(&"push_modal", &"field_manual")
	Audio.play_2d(&"ui/page_turn", -6.0)


func close() -> void:
	if not _open:
		return
	_open = false
	visible = false
	var ui: Node = get_parent()
	if ui != null and ui.has_method(&"pop_modal"):
		ui.call(&"pop_modal", &"field_manual")


func is_open() -> bool:
	return _open


func show_note(note_id: StringName) -> void:
	open("notes")
	_select(Content.get_def(&"note", note_id))


func _unhandled_key_input(event: InputEvent) -> void:
	if _open and (event.is_action_pressed(&"guidebook") or event.is_action_pressed(&"cancel")):
		close()
		get_viewport().set_input_as_handled()


func _refresh() -> void:
	for c: Node in _list.get_children():
		c.queue_free()
	_detail.text = ""
	_action.visible = false
	var p: PlayerState = Game.local_player()
	match _tab:
		"build":
			var by_cat: Dictionary = {}
			for bp: BlueprintDef in Content.all(&"blueprint"):
				if not by_cat.has(bp.category):
					by_cat[bp.category] = []
				(by_cat[bp.category] as Array).append(bp)
			for cat: String in ["survival", "shelter", "crafting", "storage", "defense", "walls", "floors"]:
				if not by_cat.has(cat):
					continue
				_header(cat.capitalize())
				for bp: BlueprintDef in by_cat[cat]:
					var known: bool = p != null and p.progression.knows_blueprint(bp)
					_entry(bp.display_name if known else "%s  (schematic needed)" % bp.display_name, bp, known)
		"notes":
			if p == null or p.read_notes.is_empty():
				_header("Nothing yet. People leave notes. Read them.")
			for nid: Variant in (p.read_notes.keys() if p != null else []):
				var n: NoteDef = Content.get_def(&"note", StringName(str(nid))) as NoteDef
				if n != null:
					_entry(n.title, n, true)
		"tips":
			for t: Array in TIPS:
				_entry(t[0], t, true)
	if _selected != null:
		_select(_selected)


func _header(text: String) -> void:
	var l := Label.new()
	l.text = text.to_upper()
	l.add_theme_color_override(&"font_color", INK_DIM)
	l.add_theme_font_size_override(&"font_size", 14)
	_list.add_child(l)


func _entry(text: String, payload: Variant, enabled: bool) -> void:
	var b := Button.new()
	b.text = "  " + text
	b.flat = true
	b.alignment = HORIZONTAL_ALIGNMENT_LEFT
	b.add_theme_color_override(&"font_color", INK if enabled else INK_DIM)
	b.add_theme_color_override(&"font_hover_color", Color(0.5, 0.15, 0.08))
	b.add_theme_font_size_override(&"font_size", 17)
	b.pressed.connect(_select.bind(payload))
	_list.add_child(b)


func _select(payload: Variant) -> void:
	_selected = payload
	_action.visible = false
	if payload is BlueprintDef:
		var bp: BlueprintDef = payload
		var p: PlayerState = Game.local_player()
		var cost: Dictionary = bp.total_cost(Content)
		var lines: PackedStringArray = []
		for k: Variant in cost.keys():
			var d: ItemDef = Content.item(StringName(str(k)))
			var have: int = p.inventory.count_of(StringName(str(k))) if p != null else 0
			lines.append("  %s %d  [color=#%s](carrying %d)[/color]" % [d.display_name if d != null else str(k), int(cost[k]), "3a5a2a" if have >= int(cost[k]) else "7a3a22", have])
		var known: bool = p != null and p.progression.knows_blueprint(bp)
		_detail.text = "[b][font_size=22]%s[/font_size][/b]\n\n%s\n\n[b]Materials[/b]\n%s\n\n%s" % [bp.display_name, bp.description,
			"\n".join(lines), "Place the ghost, then bring the materials to it." if bp.mode == "assembly" else "Place the ghost, then carry logs into each slot."]
		if not known:
			_detail.text += "\n\n[i]You need the schematic for this.[/i]"
		_action.text = "Lay it out"
		_action.visible = known
	elif payload is NoteDef:
		var n: NoteDef = payload
		_detail.text = "[b][font_size=22]%s[/font_size][/b]\n[i]%s[/i]\n\n%s" % [n.title, n.author, n.body]
	elif payload is Array:
		_detail.text = "[b][font_size=22]%s[/font_size][/b]\n\n%s" % [payload[0], payload[1]]


func _on_action() -> void:
	if _selected is BlueprintDef:
		var building: Node = Game.world.get(&"building") if Game.world != null else null
		if building != null and bool(building.call(&"begin_placement", (_selected as BlueprintDef).id)):
			close()
			Events.player_status_message.emit("Place the %s — [LMB] place · [R] rotate · [X] cancel" % (_selected as BlueprintDef).display_name, &"info")
