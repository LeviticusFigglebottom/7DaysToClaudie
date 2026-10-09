class_name TraderScreen
extends Control
## The Waystation trade screen (ADR-0039): the quartermaster's counter (buy, sell) and the
## contracts board (today's offers, your contracts, turning them in). A plain clipboard over the
## view; everything it does goes through the trade.* / contract.* commands. Shop rows carry the
## item's icon, a tooltip (description, price each, stock / owned) and a count picker whose number
## is the `count` of trade.buy / trade.sell; the picked counts are screen state only (ADR-0003).

const TradeIcons := preload("res://src/trade/trade_icons.gd")

const PAPER := Color(0.83, 0.8, 0.7)
const INK := Color(0.14, 0.12, 0.1)
const INK_DIM := UiStyle.INK_DIM
const OK_INK := Color(0.16, 0.4, 0.18)
const ICON_SIZE := 40

var manager: Node
var _post_id: String = ""
var _tab: String = "buy"
var _open: bool = false
var _title: Label
var _status: Label
var _list: VBoxContainer
var _tabs: HBoxContainer
var _msg: Label
var _icons: Node
## Picked count per shop row ("buy:<item>" / "sell:<item>"), kept across refreshes. UI state only.
var _counts: Dictionary = {}


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	# The paper theme (ADR-0063): disabled entries stay in dim ink, never Godot's white.
	theme = UiStyle.paper_theme()
	mouse_filter = Control.MOUSE_FILTER_STOP
	visible = false
	_icons = TradeIcons.new()
	_icons.name = "Icons"
	add_child(_icons)
	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.45)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(dim)
	var panel := PanelContainer.new()
	panel.anchor_left = 0.2
	panel.anchor_right = 0.8
	panel.anchor_top = 0.1
	panel.anchor_bottom = 0.9
	# The paper theme's panel (ADR-0063), with the clipboard's wider margins.
	var sb: StyleBoxFlat = UiStyle.panel_box(true)
	sb.content_margin_left = 30
	sb.content_margin_right = 30
	sb.content_margin_top = 22
	sb.content_margin_bottom = 22
	panel.add_theme_stylebox_override(&"panel", sb)
	add_child(panel)
	var v := VBoxContainer.new()
	v.add_theme_constant_override(&"separation", 10)
	panel.add_child(v)
	_title = UiStyle.label("", &"HeadingLabel")
	v.add_child(_title)
	_status = _label("", 16, INK_DIM)
	v.add_child(_status)
	_tabs = HBoxContainer.new()
	_tabs.add_theme_constant_override(&"separation", 4)
	v.add_child(_tabs)
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	v.add_child(scroll)
	_list = VBoxContainer.new()
	_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_list.add_theme_constant_override(&"separation", 6)
	scroll.add_child(_list)
	_msg = _label("", 15, INK_DIM)
	v.add_child(_msg)
	var close := Button.new()
	close.text = "Done"
	close.theme_type_variation = &"PrimaryButton"
	close.custom_minimum_size = Vector2(0, 44)
	close.pressed.connect(close_screen)
	v.add_child(close)
	Events.ui_modal_closed.connect(func(id: StringName) -> void:
		if id == &"trader" and _open:
			_open = false
			visible = false)


func open(post_id: String, where: String) -> void:
	if post_id != _post_id:
		_counts.clear()
	_post_id = post_id
	_tab = "buy" if where == "shop" else "offers"
	_open = true
	visible = true
	_msg.text = ""
	_refresh()
	var ui: Node = get_parent()
	if ui != null and ui.has_method(&"push_modal"):
		ui.call(&"push_modal", &"trader")
	Audio.play_2d(&"ui/page_turn", -8.0)


func close_screen() -> void:
	if not _open:
		return
	_open = false
	visible = false
	var ui: Node = get_parent()
	if ui != null and ui.has_method(&"pop_modal"):
		ui.call(&"pop_modal", &"trader")


func is_open() -> bool:
	return _open


func _unhandled_key_input(event: InputEvent) -> void:
	if _open and event.is_action_pressed(&"cancel"):
		close_screen()
		get_viewport().set_input_as_handled()


func _trader() -> TraderDef:
	var post: Dictionary = (manager.get(&"posts") as Dictionary).get(_post_id, {})
	return post.get("def") as TraderDef


func _refresh() -> void:
	# Detached at once so the rebuilt rows keep their names (tests and tools find them by name).
	for box: Node in [_list, _tabs]:
		for c: Node in box.get_children():
			box.remove_child(c)
			c.queue_free()
	var td: TraderDef = _trader()
	var p: PlayerState = Game.session.local_player()
	if td == null or p == null:
		return
	var key: StringName = TraderManager.rep_key(td)
	var tier: int = td.rep_tier(p.contracts.reputation(key))
	_title.text = td.display_name.to_upper()
	_status.text = "Scrip: %d    Standing: %s (%d)    Contracts: %d/%d" % [p.inventory.count_of(&"scrip"),
		td.rep_tier_name(tier), p.contracts.reputation(key), p.contracts.count_for(key), td.max_active]
	for t: Array in [["buy", "Buy"], ["sell", "Sell"], ["offers", "Contracts board"], ["mine", "Your contracts"]]:
		var b := Button.new()
		b.text = str(t[1])
		b.theme_type_variation = &"ListButton"
		b.toggle_mode = true
		b.button_pressed = _tab == t[0]
		b.focus_mode = Control.FOCUS_NONE
		b.add_theme_font_size_override(&"font_size", 19)
		b.pressed.connect(func() -> void:
			_tab = str(t[0])
			_msg.text = ""
			_refresh())
		_tabs.add_child(b)
	match _tab:
		"buy":
			_buy_rows(td, p, tier)
		"sell":
			_sell_rows(td, p)
		"offers":
			_offer_rows(td, p)
		"mine":
			_mine_rows(td, p)


func _buy_rows(td: TraderDef, p: PlayerState, tier: int) -> void:
	var stock: Dictionary = manager.call(&"stock_of", td.id, _post_id)
	var ids: Array = stock.keys()
	ids.sort()
	var shown: int = 0
	for id: Variant in ids:
		var e: Dictionary = stock[id]
		var idef: ItemDef = Content.item(StringName(str(id)))
		if idef == null or int(e["count"]) <= 0:
			continue
		var need: int = int(e.get("rep_tier", 0))
		if need > tier:
			var locked: HBoxContainer = _icon_row(idef, "%s\n\nNeeds %s standing." % [idef.description, td.rep_tier_name(need)])
			# Dim ink says "locked" (ADR-0063); fading the whole row made it hard to read.
			if locked.get_child_count() > 0:
				(locked.get_child(0) as CanvasItem).modulate = Color(1, 1, 1, 0.5)
			locked.add_child(_label("%s — needs %s standing" % [idef.display_name, td.rep_tier_name(need)], 16, INK_DIM))
			_list.add_child(locked)
			continue
		var price: int = td.buy_price(idef, tier)
		var have: int = p.inventory.count_of(idef.id)
		var afford: int = mini(int(e["count"]), floori(float(p.inventory.count_of(&"scrip")) / float(price)))
		_trade_row("buy", idef, "%s  x%d   —   %d scrip" % [idef.display_name, int(e["count"]), price],
			"%s\n\n%d scrip each   ·   %d on the shelf   ·   you have %d" % [idef.description, price, int(e["count"]), have],
			afford, price)
		shown += 1
	if shown == 0:
		_list.add_child(_label("Nothing on the shelves. Restocks every %d days." % td.restock_days, 16, INK_DIM))


func _sell_rows(td: TraderDef, p: PlayerState) -> void:
	var seen: Dictionary = {}
	for s: ItemStack in p.inventory.stacks:
		if seen.has(s.item_id):
			continue
		seen[s.item_id] = true
		var idef: ItemDef = Content.item(s.item_id)
		var each: int = td.sell_price(idef) if idef != null else 0
		if each <= 0:
			continue
		var n: int = p.inventory.count_of(s.item_id)
		_trade_row("sell", idef, "%s  x%d   —   pays %d each" % [idef.display_name, n, each],
			"%s\n\nPays %d scrip each   ·   you have %d" % [idef.description, each, n], n, each)
	if seen.is_empty():
		_list.add_child(_label("You have nothing the Program buys.", 16, INK_DIM))


func _offer_rows(td: TraderDef, p: PlayerState) -> void:
	var post: Dictionary = (manager.get(&"posts") as Dictionary)[_post_id]
	var offers: Array = manager.call(&"board_offers", p, td)
	if offers.is_empty():
		_list.add_child(_label("Nothing posted today. Come back tomorrow.", 16, INK_DIM))
	for o: Variant in offers:
		var od: Dictionary = o
		var qd: QuestDef = Content.get_def(&"quest", StringName(str(od["def"]))) as QuestDef
		var rw: String = _rewards_text(qd)
		_list.add_child(_label("%s — %s  (tier %d)" % [qd.display_name, od["name"], int(od["tier"])], 18, INK))
		_list.add_child(_label(Contracts.briefing(qd, od, post["pos"]), 15, INK_DIM, true))
		_row("Pays %s" % rw, "Take it", p.contracts.count_for(TraderManager.rep_key(td)) < td.max_active,
			_do.bind(&"contract.accept", {"offer": str(od["id"])}))


func _mine_rows(td: TraderDef, p: PlayerState) -> void:
	var any: bool = false
	for c: Variant in p.contracts.active:
		var cd: Dictionary = c
		if not td.contracts_from.has(str(cd.get("giver", ""))):
			continue
		any = true
		var qd: QuestDef = Content.get_def(&"quest", StringName(str(cd["def"]))) as QuestDef
		var ready: bool = str(cd["state"]) == ContractLog.READY
		var due: int = TraderManager.due_day(cd)
		_list.add_child(_label("%s — %s%s" % [qd.display_name, cd.get("name", ""), "   (done)" if ready else (
			"   (due by dawn, day %d)" % due if due > 0 else "")], 18, OK_INK if ready else INK))
		var h: HBoxContainer = _row("Pays %s" % _rewards_text(qd), "Turn in", ready,
			_do.bind(&"contract.turn_in", {"contract": str(cd["id"])}))
		var ab := Button.new()
		ab.text = "Abandon"
		ab.tooltip_text = "Costs %d standing." % qd.abandon_rep
		ab.pressed.connect(_do.bind(&"contract.abandon", {"contract": str(cd["id"])}))
		h.add_child(ab)
	if not any:
		_list.add_child(_label("You hold no contracts from %s." % td.display_name, 16, INK_DIM))


static func _rewards_text(qd: QuestDef) -> String:
	var parts: PackedStringArray = []
	for k: Variant in qd.rewards.keys():
		match str(k):
			"scrip":
				parts.append("%d scrip" % int(qd.rewards[k]))
			"xp":
				parts.append("%d XP" % int(qd.rewards[k]))
			"reputation":
				parts.append("+%d standing" % int(qd.rewards[k]))
			_:
				var idef: ItemDef = Content.item(StringName(str(k)))
				parts.append("%s x%d" % [idef.display_name if idef != null else str(k), int(qd.rewards[k])])
	return ", ".join(parts)


func _do(cmd: StringName, args: Dictionary) -> void:
	var a: Dictionary = args.duplicate()
	a["trader"] = String(_trader().id)
	var r: Dictionary = Game.execute(cmd, a)
	_msg.text = "" if bool(r.get("ok", false)) else str(r.get("error", "")).capitalize() + "."
	if bool(r.get("ok", false)):
		Audio.play_2d(&"ui/page_turn", -12.0)
	_refresh()


## A shop row: icon, text, count picker (SpinBox plus a Max / All shortcut) and the action button,
## which sends the picked count. `limit` is the most this row can trade now (stock and scrip for a
## buy, what you carry for a sale); below 1 the row is shown but can't be used. Named
## "<tab>_<item>" with children "Count", "Most" and "Action".
func _trade_row(tab: String, idef: ItemDef, text: String, tip: String, limit: int, each: int) -> HBoxContainer:
	var key: String = "%s:%s" % [tab, idef.id]
	var h: HBoxContainer = _icon_row(idef, tip)
	h.name = "%s_%s" % [tab, idef.id]
	var l: Label = _label(text, 16, INK)
	l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	h.add_child(l)
	var n: int = clampi(int(_counts.get(key, 1)), 1, maxi(1, limit))
	_counts[key] = n
	var spin := SpinBox.new()
	spin.name = "Count"
	spin.min_value = 1
	spin.max_value = maxi(1, limit)
	spin.step = 1
	spin.rounded = true
	spin.value = n
	spin.editable = limit > 1
	spin.custom_minimum_size.x = 76
	spin.tooltip_text = tip
	h.add_child(spin)
	var most := Button.new()
	most.name = "Most"
	most.text = "Max" if tab == "buy" else "All"
	most.tooltip_text = "As many as you can afford (%d)" % limit if tab == "buy" else "Everything you carry (%d)" % limit
	most.disabled = limit <= 1
	most.pressed.connect(func() -> void:
		spin.value = spin.max_value)
	h.add_child(most)
	var act := Button.new()
	act.name = "Action"
	act.disabled = limit < 1
	act.custom_minimum_size.x = 130
	h.add_child(act)
	var label_action := func(v: float) -> void:
		var c: int = int(v)
		act.text = ("Buy %d  (%d)" % [c, c * each]) if tab == "buy" else ("Sell %d  (+%d)" % [c, c * each])
	label_action.call(spin.value)
	spin.value_changed.connect(func(v: float) -> void:
		_counts[key] = int(v)
		label_action.call(v))
	act.pressed.connect(_trade.bind(tab, String(idef.id)))
	_list.add_child(h)
	return h


## Sends the row's picked count through trade.buy / trade.sell.
func _trade(tab: String, item: String) -> void:
	var n: int = maxi(1, int(_counts.get("%s:%s" % [tab, item], 1)))
	_do(&"trade.buy" if tab == "buy" else &"trade.sell", {"item": item, "count": n})


## An HBox carrying the item's icon, with the tooltip over the whole row.
func _icon_row(idef: ItemDef, tip: String) -> HBoxContainer:
	var h := HBoxContainer.new()
	h.add_theme_constant_override(&"separation", 10)
	h.tooltip_text = tip
	var icon := TextureRect.new()
	icon.name = "Icon"
	icon.texture = _icons.call(&"texture", idef.id)
	icon.custom_minimum_size = Vector2(ICON_SIZE, ICON_SIZE)
	icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	h.add_child(icon)
	return h


func _row(text: String, action: String, enabled: bool, cb: Callable) -> HBoxContainer:
	var h := HBoxContainer.new()
	h.add_theme_constant_override(&"separation", 10)
	var l: Label = _label(text, 16, INK)
	l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	h.add_child(l)
	var b := Button.new()
	b.text = action
	b.disabled = not enabled
	b.pressed.connect(cb)
	h.add_child(b)
	_list.add_child(h)
	return h


static func _label(text: String, size: int, color: Color, wrap: bool = false) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override(&"font_size", size)
	l.add_theme_color_override(&"font_color", color)
	if wrap:
		l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	return l
