class_name CraftSheet
extends PanelContainer
## The salvage roll's crafting sheet (player report 4, item 7): every recipe you know here, the
## ones you can make first, the rest in dim but legible ink with what they lack in red. A filter
## row (All / Ready / each category), a list, and a detail card for the chosen recipe with its
## ingredients (have / need), tools, time, what it makes, and the Make button.
##
## A view only: it reads the player's inventory and asks the roll to craft (`craft_requested`),
## which goes through `Game.execute(&"inventory.craft")`.
##   click a recipe  choose it        double-click / Enter / Make  make one
##   Shift + Make    make as many as you can

signal craft_requested(recipe_id: StringName, times: int)

## Category labels in the order the filter row shows them (others follow, capitalised).
const CATEGORY_ORDER: PackedStringArray = ["tools", "weapons", "light", "medical", "cooking", "materials", "traps"]

var _title: Label
var _summary: Label
var _filters: HFlowContainer
var _list: VBoxContainer
var _scroll: ScrollContainer
var _detail: RichTextLabel
var _make: Button
var _filter: String = "all"
var _selected: StringName = &""
## Whose pack the sheet was last drawn for (its journal picks the recipe it opens on).
var _for: PlayerState = null
var _rows: Array[Dictionary] = []
var _group := ButtonGroup.new()
var _row_buttons: Dictionary = {}


func _init() -> void:
	theme = UiStyle.paper_theme()
	mouse_filter = Control.MOUSE_FILTER_STOP
	var v := VBoxContainer.new()
	v.add_theme_constant_override(&"separation", 8)
	add_child(v)
	var head := HBoxContainer.new()
	v.add_child(head)
	_title = UiStyle.label("MAKE BY HAND", &"HeadingLabel")
	_title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	head.add_child(_title)
	_summary = UiStyle.label("", &"DimLabel")
	_summary.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	head.add_child(_summary)
	_filters = HFlowContainer.new()
	_filters.add_theme_constant_override(&"h_separation", 4)
	_filters.add_theme_constant_override(&"v_separation", 4)
	v.add_child(_filters)
	_scroll = ScrollContainer.new()
	_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_scroll.size_flags_stretch_ratio = 1.1
	v.add_child(_scroll)
	_list = VBoxContainer.new()
	_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_list.add_theme_constant_override(&"separation", 1)
	_scroll.add_child(_list)
	v.add_child(HSeparator.new())
	_detail = RichTextLabel.new()
	_detail.bbcode_enabled = true
	_detail.fit_content = false
	_detail.scroll_active = true
	_detail.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_detail.add_theme_font_override(&"bold_font", UiStyle.bold_font())
	_detail.mouse_filter = Control.MOUSE_FILTER_PASS
	v.add_child(_detail)
	_make = Button.new()
	_make.text = "Make"
	_make.custom_minimum_size = Vector2(0, 44)
	_make.theme_type_variation = &"PrimaryButton"
	_make.pressed.connect(func() -> void: _request(_selected, Input.is_key_pressed(KEY_SHIFT)))
	v.add_child(_make)


# --- Model (pure; unit-tested) ------------------------------------------------------------------

## One row per known recipe for `station` ("" = by hand), ready ones first, then by how little
## they lack, then by name: {recipe, ok, max, missing: [{item, name, have, need}], tools: [kind],
## status, at}. `knows` is (RecipeDef) -> bool. With `elsewhere`, the hand list also ends with the
## known recipes made at a station, so the player learns where the rest is made: they are never
## ready here, `at` names their station and their status says where ("at a Workbench").
static func rows(inv: Inventory, station: StringName, knows: Callable, elsewhere: bool = false) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for r: RecipeDef in Content.all(&"recipe"):
		var here: bool = r.station == station or (station == &"" and r.station == &"hand")
		if not here and not (elsewhere and station == &"" and r.station != &"hand" and r.station != &""):
			continue
		if not knows.call(r):
			continue
		var e: Dictionary = row(r, inv)
		if not here:
			e["at"] = r.station
			e["ok"] = false
			e["max"] = 0
			e["status"] = "at " + station_phrase(r.station)
		out.append(e)
	out.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		var aa: bool = a.has("at")
		if aa != b.has("at"):
			return not aa
		if bool(a["ok"]) != bool(b["ok"]):
			return bool(a["ok"])
		var la: int = int(a["lack"])
		var lb: int = int(b["lack"])
		if la != lb:
			return la < lb
		return String((a["recipe"] as RecipeDef).display_name) < String((b["recipe"] as RecipeDef).display_name))
	return out


## What `inv` has and lacks for one recipe (station checks are the caller's: the list only holds
## recipes of the open station).
static func row(r: RecipeDef, inv: Inventory) -> Dictionary:
	var missing: Array[Dictionary] = []
	var have_all: Array[Dictionary] = []
	var lack: int = 0
	var most: int = 1 << 30
	for k: StringName in r.ingredients:
		var need: int = int(r.ingredients[k])
		var have: int = inv.count_of(k)
		var d: ItemDef = Content.item(k)
		var e: Dictionary = {"item": k, "name": d.display_name if d != null else String(k), "have": have, "need": need}
		have_all.append(e)
		most = mini(most, have / need)
		if have < need:
			missing.append(e)
			lack += need - have
	var tools: PackedStringArray = []
	for t: String in r.tools_required:
		if inv.find_tool(t) == null:
			tools.append(t)
	lack += tools.size()
	var ok: bool = missing.is_empty() and tools.is_empty()
	return {"recipe": r, "ok": ok, "max": most if ok else 0, "lack": lack, "ingredients": have_all,
		"missing": missing, "tools": tools, "status": status_text(missing, tools)}


## "a Workbench", "a Campfire": a station by its display name, with its article.
static func station_phrase(id: StringName) -> String:
	var sd: ContentDef = Content.get_def(&"station", id) if Content != null else null
	var n: String = sd.display_name if sd != null else String(id).capitalize()
	return ("an " if "AEIOU".contains(n.left(1).to_upper()) else "a ") + n


## What the journal's current step asks the player to make (its craft targets), else [].
static func journal_targets(p: PlayerState) -> PackedStringArray:
	if p == null or p.tutorial == null or not p.tutorial.enabled:
		return PackedStringArray()
	var step: TutorialStepDef = p.tutorial.current()
	return step.targets if step != null and step.event == "craft" else PackedStringArray()


## The recipe to open on for a journal step that asks for `targets`: a ready recipe that makes
## one, else a ready recipe for one of their ingredients (Cordage before the Stone Axe), else the
## target's own recipe to show what it needs; &"" with no targets. Pure.
static func preferred(rows_: Array, targets: PackedStringArray) -> StringName:
	if targets.is_empty():
		return &""
	var inputs: Dictionary = {}
	var target_row: StringName = &""
	for r: Dictionary in rows_:
		var rd: RecipeDef = r["recipe"]
		if targets.has(String(rd.result)):
			if bool(r["ok"]):
				return rd.id
			if target_row == &"":
				target_row = rd.id
			for k: Variant in rd.ingredients:
				inputs[String(k)] = true
	for r: Dictionary in rows_:
		var rd: RecipeDef = r["recipe"]
		if bool(r["ok"]) and inputs.has(String(rd.result)):
			return rd.id
	return target_row


## The short line a row shows on the right: "ready", or what's missing ("need 2 Stick, a knife").
static func status_text(missing: Array, tools: PackedStringArray) -> String:
	if missing.is_empty() and tools.is_empty():
		return "ready"
	var parts: PackedStringArray = []
	for e: Dictionary in missing:
		parts.append("%d %s" % [int(e["need"]) - int(e["have"]), e["name"]])
	for t: String in tools:
		parts.append("a %s" % t)
	return "need " + ", ".join(parts)


## Status lines longer than this wrap to two lines (the status column holds about this many
## characters at the sheet's narrowest, 560 px).
const STATUS_ONE_LINE: int = 24


static func status_wraps(text: String) -> bool:
	return text.length() > STATUS_ONE_LINE


## Whether a row passes a filter: "all", "ready", "uses:<item id>" or a recipe category.
static func passes(r: Dictionary, filter: String) -> bool:
	if filter.begins_with("uses:"):
		return (r["recipe"] as RecipeDef).ingredients.has(StringName(filter.substr(5)))
	match filter:
		"all":
			return true
		"ready":
			return bool(r["ok"])
		"stations":
			return r.has("at")
		_:
			return (r["recipe"] as RecipeDef).category == filter


## The filter row's entries for these rows: all, ready, then the categories present.
static func filters_for(list: Array[Dictionary]) -> PackedStringArray:
	var cats: PackedStringArray = []
	for r: Dictionary in list:
		var c: String = (r["recipe"] as RecipeDef).category
		if not cats.has(c):
			cats.append(c)
	var out: PackedStringArray = ["all", "ready"]
	for c2: String in CATEGORY_ORDER:
		if cats.has(c2):
			out.append(c2)
	for c3: String in cats:
		if not out.has(c3):
			out.append(c3)
	for r2: Dictionary in list:
		if r2.has("at"):
			out.append("stations")
			break
	return out


# --- View -----------------------------------------------------------------------------------

## Re-reads the inventory. `title` names the station (or "Make by hand").
func refresh(p: PlayerState, station: StringName, title: String) -> void:
	_for = p
	_title.text = title.to_upper()
	if p == null:
		return
	_rows = rows(p.inventory, station, p.progression.knows_recipe, station == &"")
	var ready: int = 0
	var here: int = 0
	for r: Dictionary in _rows:
		ready += 1 if bool(r["ok"]) else 0
		here += 0 if r.has("at") else 1
	_summary.text = "%d of %d ready" % [ready, here]
	_build_filters()
	_build_list()
	_show_detail()


## Shows only the recipes that use an item (an item dropped on the sheet).
func filter_uses(item_id: StringName) -> void:
	_filter = "uses:" + String(item_id)
	_build_filters()
	_build_list()
	_show_detail()


func _build_filters() -> void:
	var names: PackedStringArray = filters_for(_rows)
	if _filter.begins_with("uses:"):
		names.append(_filter)
	if not names.has(_filter):
		_filter = "all"
	for c: Node in _filters.get_children():
		c.queue_free()
	var group := ButtonGroup.new()
	for f: String in names:
		var b := Button.new()
		b.toggle_mode = true
		b.button_group = group
		b.button_pressed = f == _filter
		b.focus_mode = Control.FOCUS_NONE
		var d: ItemDef = Content.item(StringName(f.substr(5))) if f.begins_with("uses:") else null
		b.text = ("Uses %s" % (d.display_name if d != null else f.substr(5))) if f.begins_with("uses:") else ("At a station" if f == "stations" else f.capitalize())
		b.add_theme_font_size_override(&"font_size", UiStyle.BODY_SIZE - 3)
		b.pressed.connect(func() -> void:
			_filter = f
			_build_list())
		_filters.add_child(b)


func _build_list() -> void:
	for c: Node in _list.get_children():
		c.queue_free()
	_row_buttons.clear()
	_group = ButtonGroup.new()
	var any: bool = false
	var first: StringName = &""
	var still_there: bool = false
	for r: Dictionary in _rows:
		if not passes(r, _filter):
			continue
		var rd: RecipeDef = r["recipe"]
		_list.add_child(_row(r))
		any = true
		if first == &"":
			first = rd.id
		if rd.id == _selected:
			still_there = true
	if not still_there:
		var want: StringName = preferred(_rows.filter(func(r: Dictionary) -> bool: return passes(r, _filter)), journal_targets(_for))
		_selected = want if want != &"" else first
	if _row_buttons.has(_selected):
		(_row_buttons[_selected] as Button).button_pressed = true
	if not any:
		var l := UiStyle.label("Nothing you know how to make here." if _rows.is_empty() else "Nothing in this list.", &"DimLabel")
		_list.add_child(l)


func _row(r: Dictionary) -> Button:
	var rd: RecipeDef = r["recipe"]
	var ok: bool = r["ok"]
	var b := Button.new()
	b.theme_type_variation = &"ListButton"
	b.toggle_mode = true
	b.button_group = _group
	b.focus_mode = Control.FOCUS_NONE
	b.custom_minimum_size = Vector2(0, 34)
	b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	b.clip_contents = true
	var h := HBoxContainer.new()
	h.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	h.offset_left = 10
	h.offset_right = -8
	h.mouse_filter = Control.MOUSE_FILTER_IGNORE
	h.add_theme_constant_override(&"separation", 10)
	b.add_child(h)
	# A filled mark for ready, a hollow one for not: the state reads without colour too.
	# A station's recipe isn't missing anything here: it is made elsewhere (a dim dash, dim ink).
	var away: bool = r.has("at")
	var mark := UiStyle.label("✓" if ok else ("–" if away else "×"))
	mark.add_theme_color_override(&"font_color", UiStyle.INK_OK if ok else (UiStyle.INK_DIM if away else UiStyle.INK_MISSING))
	mark.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	h.add_child(mark)
	var name_l := UiStyle.label(rd.display_name + ((" ×%d" % rd.result_count) if rd.result_count > 1 else ""))
	name_l.add_theme_color_override(&"font_color", UiStyle.INK if ok else UiStyle.INK_DIM)
	name_l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	name_l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	name_l.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	name_l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	h.add_child(name_l)
	var st := UiStyle.label(str(r["status"]) if not ok else ("ready ×%d" % int(r["max"]) if int(r["max"]) > 1 else "ready"))
	st.add_theme_font_size_override(&"font_size", UiStyle.BODY_SIZE - 4)
	st.add_theme_color_override(&"font_color", UiStyle.INK_OK if ok else (UiStyle.INK_DIM if away else UiStyle.INK_MISSING))
	st.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	st.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	st.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	st.size_flags_stretch_ratio = 0.9
	# A long need ("need 1 Bottle of Stream Water") wraps to a second line in a taller row: cut
	# mid-word it read as an unreadable recipe (owner report 4, item 7).
	if status_wraps(st.text):
		st.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		st.max_lines_visible = 2
		b.custom_minimum_size.y = 54
	st.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	st.mouse_filter = Control.MOUSE_FILTER_IGNORE
	h.add_child(st)
	b.tooltip_text = ""
	b.pressed.connect(func() -> void:
		_selected = rd.id
		_show_detail())
	b.gui_input.connect(func(ev: InputEvent) -> void:
		var mb := ev as InputEventMouseButton
		if mb != null and mb.double_click and mb.button_index == MOUSE_BUTTON_LEFT:
			_request(rd.id, mb.shift_pressed))
	_row_buttons[rd.id] = b
	return b


func _find(id: StringName) -> Dictionary:
	for r: Dictionary in _rows:
		if (r["recipe"] as RecipeDef).id == id:
			return r
	return {}


func _show_detail() -> void:
	var r: Dictionary = _find(_selected)
	if r.is_empty():
		_detail.text = ""
		_make.disabled = true
		_make.text = "Make"
		return
	_detail.text = detail_bbcode(r)
	var ok: bool = r["ok"]
	_make.disabled = not ok
	var rd: RecipeDef = r["recipe"]
	_make.text = ("Make %s" % rd.display_name) if ok else ("Made at %s" % station_phrase(r["at"]) if r.has("at") else "Missing materials")
	if ok and int(r["max"]) > 1:
		_make.text += "   (Shift: all %d)" % int(r["max"])


## The detail card's text for a row: what it makes, every ingredient (have / need, coloured),
## tools, time and the result's numbers.
static func detail_bbcode(r: Dictionary) -> String:
	var rd: RecipeDef = r["recipe"]
	var d: ItemDef = Content.item(rd.result)
	var ok_c: String = UiStyle.hex(UiStyle.INK_OK)
	var miss_c: String = UiStyle.hex(UiStyle.INK_MISSING)
	var dim_c: String = UiStyle.hex(UiStyle.INK_DIM)
	var lines: PackedStringArray = []
	lines.append("[font_size=22][b]%s[/b][/font_size]%s   [color=%s]%s · %.0f s[/color]" % [rd.display_name,
		(" ×%d" % rd.result_count) if rd.result_count > 1 else "", dim_c, rd.category.capitalize(), rd.time])
	if d != null and d.description != "":
		lines.append("[color=%s]%s[/color]" % [dim_c, d.description])
	var stats: PackedStringArray = ItemCard.stat_lines(d, 0) if d != null else PackedStringArray()
	if not stats.is_empty():
		lines.append("[color=%s]%s[/color]" % [dim_c, "   ".join(stats)])
	lines.append("")
	for e: Dictionary in r["ingredients"]:
		var have: int = e["have"]
		var need: int = e["need"]
		if have >= need:
			lines.append("[color=%s]✓[/color]  %s   [color=%s]%d / %d[/color]" % [ok_c, e["name"], ok_c, need, need])
		else:
			lines.append("[color=%s]×[/color]  %s   [color=%s]%d / %d — need %d more[/color]" % [miss_c, e["name"], miss_c, have, need, need - have])
	for t: String in (r["recipe"] as RecipeDef).tools_required:
		var lacks: bool = (r["tools"] as PackedStringArray).has(t)
		lines.append("[color=%s]%s[/color]  Tool: %s%s" % [miss_c if lacks else ok_c, "×" if lacks else "✓", t,
			("   [color=%s]— not in your roll[/color]" % miss_c) if lacks else ""])
	if r.has("at"):
		lines.append("")
		lines.append("[color=%s]Made at %s: use one to open this roll beside it.[/color]" % [dim_c, station_phrase(r["at"])])
	return "\n".join(lines)


func _request(id: StringName, all: bool) -> void:
	var r: Dictionary = _find(id)
	if r.is_empty() or not bool(r["ok"]):
		return
	craft_requested.emit(id, int(r["max"]) if all else 1)


func _unhandled_key_input(event: InputEvent) -> void:
	if not is_visible_in_tree():
		return
	var k := event as InputEventKey
	if k != null and k.pressed and not k.echo and k.keycode in [KEY_ENTER, KEY_KP_ENTER]:
		_request(_selected, k.shift_pressed)
		get_viewport().set_input_as_handled()


## The recipe `step` rows from `current` among `ids` (the list as shown), held at the ends;
## the first when `current` isn't there. Pure.
static func step_selection(ids: Array, current: StringName, step: int) -> StringName:
	if ids.is_empty():
		return &""
	var i: int = ids.find(current)
	if i < 0:
		return ids[0]
	return ids[clampi(i + step, 0, ids.size() - 1)]


## Up / down (d-pad, stick or arrows) while the focus is on the sheet choose the recipe above or
## below: the rows take no focus, so a pad on the Make button could only make the first recipe.
func _input(event: InputEvent) -> void:
	if not is_visible_in_tree():
		return
	var f: Control = get_viewport().gui_get_focus_owner()
	if f == null or not is_ancestor_of(f):
		return
	var step: int = 1 if event.is_action_pressed(&"ui_down") else (-1 if event.is_action_pressed(&"ui_up") else 0)
	if step == 0:
		return
	var ids: Array = []
	for r: Dictionary in _rows:
		if passes(r, _filter):
			ids.append((r["recipe"] as RecipeDef).id)
	var to: StringName = step_selection(ids, _selected, step)
	if to != &"" and to != _selected:
		select(to)
		if _row_buttons.has(to):
			_scroll.ensure_control_visible(_row_buttons[to])
	get_viewport().set_input_as_handled()


## The id of the chosen recipe (tests, the roll's status line).
func selected() -> StringName:
	return _selected


func select(id: StringName) -> void:
	_selected = id
	if _row_buttons.has(id):
		(_row_buttons[id] as Button).button_pressed = true
	_show_detail()
