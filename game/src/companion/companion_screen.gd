class_name CompanionScreen
extends Control
## Ezra's order card (ADR-0058): a small clipboard over the view, modal like the trade screen.
## Before he is recruited it is the talk at his camp (what he says, and giving him a first aid kit
## or painkillers: companion.recruit); after, his orders: Follow, Stay here, Guard here
## (companion.order), Gather wood / stone / fibre round what the player last looked at, Fetch what
## they last looked at (companion.order), Give me what you carry (companion.give) and Store at base
## (companion.store), with what he carries and his knacks (perks, ADR-0058 phase 3). Everything
## goes through the commands (ADR-0003); the card only shows state.

const PAPER := Color(0.83, 0.8, 0.7)
const INK := Color(0.14, 0.12, 0.1)
const INK_DIM := Color(0.42, 0.38, 0.32)
const ORDER_NAMES: Dictionary = {"follow": "Following you", "stay": "Holding his spot", "guard": "Guarding his spot",
	"gather": "Gathering", "fetch": "Fetching", "store": "Taking his load to base"}

var director: Node
var _open: bool = false
var _title: Label
var _status: Label
var _body: Label
var _list: VBoxContainer
var _msg: Label


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	visible = false
	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.35)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(dim)
	var panel := PanelContainer.new()
	panel.anchor_left = 0.33
	panel.anchor_right = 0.67
	panel.anchor_top = 0.2
	panel.anchor_bottom = 0.8
	var sb := StyleBoxFlat.new()
	sb.bg_color = PAPER
	sb.border_color = Color(0.3, 0.28, 0.22)
	sb.set_border_width_all(3)
	sb.content_margin_left = 26
	sb.content_margin_right = 26
	sb.content_margin_top = 20
	sb.content_margin_bottom = 20
	sb.shadow_size = 12
	sb.shadow_color = Color(0, 0, 0, 0.5)
	panel.add_theme_stylebox_override(&"panel", sb)
	add_child(panel)
	var v := VBoxContainer.new()
	v.add_theme_constant_override(&"separation", 8)
	panel.add_child(v)
	_title = TraderScreen._label("EZRA VANE", 24, INK)
	v.add_child(_title)
	_status = TraderScreen._label("", 16, INK_DIM)
	v.add_child(_status)
	_body = TraderScreen._label("", 16, INK, true)
	v.add_child(_body)
	_list = VBoxContainer.new()
	_list.add_theme_constant_override(&"separation", 4)
	_list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	v.add_child(_list)
	_msg = TraderScreen._label("", 15, INK_DIM, true)
	v.add_child(_msg)
	var close := Button.new()
	close.name = "Done"
	close.text = "Done"
	close.pressed.connect(close_screen)
	v.add_child(close)
	# Recruited with the card open (the give button): the plea gives way to his orders at once.
	Events.companion_recruited.connect(_on_recruited)
	Events.ui_modal_closed.connect(func(id: StringName) -> void:
		if id == &"companion" and _open:
			_open = false
			visible = false)


func open() -> void:
	_open = true
	visible = true
	_msg.text = ""
	_refresh()
	var ui: Node = get_parent()
	if ui != null and ui.has_method(&"push_modal"):
		ui.call(&"push_modal", &"companion")
	Audio.play_2d(&"ui/page_turn", -8.0)


func _on_recruited(_id: StringName) -> void:
	if _open:
		_refresh()


func close_screen() -> void:
	if not _open:
		return
	_open = false
	visible = false
	var ui: Node = get_parent()
	if ui != null and ui.has_method(&"pop_modal"):
		ui.call(&"pop_modal", &"companion")


func is_open() -> bool:
	return _open


func _unhandled_key_input(event: InputEvent) -> void:
	if _open and event.is_action_pressed(&"cancel"):
		close_screen()
		get_viewport().set_input_as_handled()


## The rows, rebuilt from the state: the talk before he is recruited, the orders after.
func _refresh() -> void:
	for c: Node in _list.get_children():
		_list.remove_child(c)
		c.queue_free()
	var cd: CompanionDef = director.get(&"cdef") as CompanionDef
	var m: CompanionMind = director.call(&"mind") as CompanionMind
	var ps: PlayerState = Game.session.local_player() if Game.session != null else null
	if cd == null or m == null or ps == null:
		return
	if not bool(director.call(&"recruited")):
		_title.text = "THE LINEMAN"
		_status.text = "Hurt, barricaded in, short of everything."
		_body.text = "\"Leg's broke. Splinted it myself, it won't take weight for a while. I was Remand too, two drops before yours. I know the lines in this valley, and I know what's out in the dark. Get me something for this and I'll walk with you.\""
		for it: String in cd.recruit_items:
			var idef: ItemDef = Content.item(StringName(it))
			var have: int = ps.inventory.count_of(StringName(it))
			_button("give_%s" % it, "Give %s (you have %d)" % [idef.display_name if idef != null else it, have], have > 0,
				func() -> void: _do(&"companion.recruit", {"item": it}))
		return
	_title.text = "EZRA VANE"
	var hp: int = int(round(100.0 * m.enemy.health / maxf(1.0, m.enemy.max_health)))
	_status.text = "%s   ·   Health %d%%%s" % [ORDER_NAMES.get(m.order, m.order), hp, "   ·   lantern lit" if m.lantern_on() else ""]
	if m.order == "gather" and m.work.kind != "":
		_status.text = _status.text.replace("Gathering", "Gathering %s" % m.work.kind)
	_body.text = _carrying(m.inventory)
	var knacks: PackedStringArray = []
	var why: PackedStringArray = []
	for pk: Variant in director.call(&"active_perks"):
		knacks.append(str((pk as Dictionary).get("name", "")))
		why.append("%s: %s" % [(pk as Dictionary).get("name", ""), (pk as Dictionary).get("text", "")])
	if not knacks.is_empty():
		_body.text += "\nKnacks: %s." % ", ".join(knacks)
	_body.tooltip_text = "\n".join(why)
	_body.mouse_filter = Control.MOUSE_FILTER_PASS
	_button("follow", "Follow me", m.order != "follow", func() -> void: _do(&"companion.order", {"order": "follow"}))
	_button("stay", "Stay here", true, func() -> void: _do(&"companion.order", {"order": "stay"}))
	_button("guard", "Guard here", true, func() -> void: _do(&"companion.order", {"order": "guard"}))
	for k: Variant in (cd.gather.get("kinds", {}) as Dictionary).keys():
		var gk: String = str(k)
		_button("gather_%s" % gk, "Gather %s" % gk, true, func() -> void: _do(&"companion.order", {"order": "gather", "kind": gk}))
	var looked: Dictionary = director.get(&"looked")
	var ft: Dictionary = director.call(&"fetch_target")
	var what: String = str(director.call(&"describe", looked))
	var fb: Button = _button("fetch", "Fetch %s" % what if what != "" else "Fetch (look at something first)", bool(ft.get("ok", false)),
		func() -> void: _do(&"companion.order", {"order": "fetch", "target": looked}))
	fb.tooltip_text = str(ft.get("error", ""))
	var carrying: bool = m.inventory != null and not m.inventory.is_empty()
	_button("give", "Give me what you carry", carrying, func() -> void: _do(&"companion.give", {}))
	var crate: Node = director.call(&"nearest_storage", m.enemy.global_position)
	var sb: Button = _button("store", "Store at base", carrying and crate != null, func() -> void: _do(&"companion.store", {}))
	sb.tooltip_text = "" if crate != null else "No storage at your base near enough."
	_msg.text = "[%s] whistles him to follow or to stay without the card." % PlayerInteraction.key_label(&"companion_order")


## "Carrying: 2 Log, 12 Stick." from his pack.
static func _carrying(inv: Inventory) -> String:
	if inv == null or inv.is_empty():
		return "Carrying nothing."
	var counts: Dictionary = {}
	for s: ItemStack in inv.stacks:
		counts[s.item_id] = int(counts.get(s.item_id, 0)) + s.count
	var parts: PackedStringArray = []
	for id: Variant in counts:
		var d: ItemDef = Content.item(id)
		parts.append("%d %s" % [counts[id], d.display_name if d != null else String(id)])
	return "Carrying: %s." % ", ".join(parts)


func _button(id: String, text: String, enabled: bool, on_press: Callable) -> Button:
	var b := Button.new()
	b.name = id
	b.text = text
	b.disabled = not enabled
	b.alignment = HORIZONTAL_ALIGNMENT_LEFT
	b.add_theme_font_size_override(&"font_size", 18)
	if on_press.is_valid():
		b.pressed.connect(on_press)
	_list.add_child(b)
	return b


func _do(command: StringName, args: Dictionary) -> void:
	var r: Dictionary = Game.execute(command, args)
	if bool(r.get("ok", false)):
		close_screen()
	else:
		_refresh()
		_msg.text = str(r.get("error", "He doesn't move."))
