extends GutTest
## The crafting sheet's model, the item card's numbers, the roll's sort/filter view and the UI
## style (player report 4, item 7; ADR-0063).

var _knows_default: Callable = func(r: RecipeDef) -> bool: return r.unlock == "default"


func _row_of(rows: Array[Dictionary], id: StringName) -> Dictionary:
	for r: Dictionary in rows:
		if (r["recipe"] as RecipeDef).id == id:
			return r
	return {}


func test_rows_put_ready_recipes_first_and_name_what_is_missing() -> void:
	var inv := Inventory.new()
	inv.add_item(&"plant_fiber", 7)
	inv.add_item(&"stick", 1)
	var rows: Array[Dictionary] = CraftSheet.rows(inv, &"", _knows_default)
	assert_gt(rows.size(), 3)
	var cordage: Dictionary = _row_of(rows, &"cordage")
	assert_true(bool(cordage["ok"]))
	assert_eq(int(cordage["max"]), 2, "7 fibre makes two cordage")
	assert_true(bool(rows[0]["ok"]), "a ready recipe leads the list")
	var seen_not_ready: bool = false
	for r: Dictionary in rows:
		if not bool(r["ok"]):
			seen_not_ready = true
		else:
			assert_false(seen_not_ready, "no ready recipe after a missing one")
	var axe: Dictionary = _row_of(rows, &"stone_axe")
	assert_false(bool(axe["ok"]))
	var missing: PackedStringArray = []
	for e: Dictionary in axe["missing"]:
		missing.append(String(e["item"]))
	assert_true(missing.has("stone") and missing.has("cordage"))
	assert_false(missing.has("stick"), "the stick is there")
	assert_string_starts_with(str(axe["status"]), "need ")


func test_unknown_recipes_are_left_out() -> void:
	var rows: Array[Dictionary] = CraftSheet.rows(Inventory.new(), &"", _knows_default)
	assert_true(_row_of(rows, &"can_chime").is_empty(), "a schematic recipe you haven't learned")


func test_station_rows_only_hold_that_station() -> void:
	var rows: Array[Dictionary] = CraftSheet.rows(Inventory.new(), &"campfire", func(_r: RecipeDef) -> bool: return true)
	assert_gt(rows.size(), 0)
	for r: Dictionary in rows:
		assert_eq((r["recipe"] as RecipeDef).station, &"campfire")


func test_status_text_lists_shortfalls_and_tools() -> void:
	var t: String = CraftSheet.status_text([{"name": "Stick", "have": 1, "need": 3}], PackedStringArray(["knife"]))
	assert_eq(t, "need 2 Stick, a knife")
	assert_eq(CraftSheet.status_text([], PackedStringArray()), "ready")


func test_filters_and_passes() -> void:
	var inv := Inventory.new()
	inv.add_item(&"plant_fiber", 3)
	var rows: Array[Dictionary] = CraftSheet.rows(inv, &"", _knows_default)
	var f: PackedStringArray = CraftSheet.filters_for(rows)
	assert_eq(f[0], "all")
	assert_eq(f[1], "ready")
	assert_true(f.has("tools"))
	for r: Dictionary in rows:
		assert_eq(CraftSheet.passes(r, "ready"), bool(r["ok"]))
		assert_true(CraftSheet.passes(r, "all"))


func test_detail_names_every_ingredient_with_counts() -> void:
	var inv := Inventory.new()
	inv.add_item(&"stick", 1)
	var axe: Dictionary = CraftSheet.row(Content.recipe(&"stone_axe"), inv)
	var text: String = CraftSheet.detail_bbcode(axe)
	assert_string_contains(text, "1 / 1")
	assert_string_contains(text, "0 / 1 — need 1 more")


func test_sheet_builds_and_keeps_a_selection() -> void:
	var sheet := CraftSheet.new()
	add_child_autofree(sheet)
	var p := PlayerState.new()
	p.inventory.add_item(&"plant_fiber", 3)
	sheet.refresh(p, &"", "Make by hand")
	assert_eq(sheet.selected(), &"cordage", "the first ready recipe is chosen")
	var asked: Array = []
	sheet.craft_requested.connect(func(id: StringName, n: int) -> void: asked.append([id, n]))
	sheet.select(&"stone_axe")
	sheet.call(&"_request", &"stone_axe", false)
	assert_eq(asked.size(), 0, "a recipe you can't make is never requested")
	sheet.call(&"_request", &"cordage", false)
	assert_eq(asked, [[&"cordage", 1]])


func test_item_card_stats() -> void:
	var axe: PackedStringArray = ItemCard.stat_lines(Content.item(&"stone_axe"), 0)
	assert_true(axe.size() >= 2)
	assert_string_starts_with(axe[0], "Damage ")
	var joined: String = " ".join(axe)
	assert_string_contains(joined, "Works as: axe")
	var s := ItemStack.make(&"stone_axe", 1, 2)
	var body: String = ItemCard.body_bbcode(s)
	assert_string_contains(body, "Condition")
	assert_string_contains(body, "Bulk")


func test_view_stacks_sort_and_filter_without_touching_the_inventory() -> void:
	var inv := Inventory.new()
	inv.add_item(&"stone", 2)
	inv.add_item(&"stone_axe", 1)
	inv.add_item(&"cloth", 1)
	var before: Array = inv.stacks.map(func(s: ItemStack) -> StringName: return s.item_id)
	var gear: Array[ItemStack] = SalvageRoll.view_stacks(inv.stacks, "packed", "gear")
	assert_eq(gear.size(), 1)
	assert_eq(gear[0].item_id, &"stone_axe")
	var by_name: Array[ItemStack] = SalvageRoll.view_stacks(inv.stacks, "name", "all")
	assert_eq(by_name.size(), 3)
	for i: int in by_name.size() - 1:
		assert_true(by_name[i].def().display_name <= by_name[i + 1].def().display_name)
	assert_eq(inv.stacks.map(func(s: ItemStack) -> StringName: return s.item_id), before, "a view, not a reorder")


func test_ui_scale() -> void:
	assert_eq(UiStyle.auto_scale(720), 1.0)
	assert_eq(UiStyle.auto_scale(1080), 1.0)
	assert_eq(UiStyle.auto_scale(1440), 1.25)
	assert_eq(UiStyle.auto_scale(2160), 2.0)
	assert_eq(UiStyle.resolve_scale(1.5, 720), 1.5)
	assert_eq(UiStyle.resolve_scale(0.0, 2160), 2.0)


func test_themes_never_draw_disabled_text_white() -> void:
	for t: Theme in [UiStyle.paper_theme(), UiStyle.kit_theme()]:
		var c: Color = t.get_color(&"font_disabled_color", &"Button")
		assert_lt(c.get_luminance(), 0.75, "disabled buttons keep a readable ink")
	var paper_dim: Color = UiStyle.paper_theme().get_color(&"font_disabled_color", &"Button")
	assert_gt(_contrast(UiStyle.PAPER, paper_dim), 4.5, "dim ink on paper is still body-text legible")
	assert_gt(_contrast(UiStyle.PAPER, UiStyle.INK_MISSING), 4.5)


static func _contrast(a: Color, b: Color) -> float:
	var la: float = a.srgb_to_linear().get_luminance()
	var lb: float = b.srgb_to_linear().get_luminance()
	return (maxf(la, lb) + 0.05) / (minf(la, lb) + 0.05)


func test_drop_targets() -> void:
	assert_eq(SalvageRoll.drop_target(false, 2, false, false, true), "belt")
	assert_eq(SalvageRoll.drop_target(false, -1, true, false, false), "sheet")
	assert_eq(SalvageRoll.drop_target(false, -1, false, true, false), "put")
	assert_eq(SalvageRoll.drop_target(false, -1, false, false, true), "", "back on the cloth: nothing")
	assert_eq(SalvageRoll.drop_target(false, -1, false, false, false), "drop", "off the cloth: dropped")
	assert_eq(SalvageRoll.drop_target(true, -1, false, false, true), "take")
	assert_eq(SalvageRoll.drop_target(true, -1, false, true, false), "", "within the container")


func test_uses_filter() -> void:
	var rows: Array[Dictionary] = CraftSheet.rows(Inventory.new(), &"", _knows_default)
	var n: int = 0
	for r: Dictionary in rows:
		if CraftSheet.passes(r, "uses:cordage"):
			n += 1
			assert_true((r["recipe"] as RecipeDef).ingredients.has(&"cordage"))
	assert_gt(n, 1, "the axe, the spear, the club... use cordage")


func test_ready_and_missing_never_rely_on_colour_alone() -> void:
	# Colour-blind safe: every row says it in words and a mark, besides red and green.
	var inv := Inventory.new()
	inv.add_item(&"plant_fiber", 3)
	for r: Dictionary in CraftSheet.rows(inv, &"", _knows_default):
		var text: String = CraftSheet.detail_bbcode(r)
		if bool(r["ok"]):
			assert_eq(str(r["status"]), "ready")
			assert_false(text.contains("×"), "a ready recipe has no missing mark")
		else:
			assert_string_starts_with(str(r["status"]), "need ")
			assert_true(text.contains("×") and text.contains("more"), "missing ingredients say so")
	assert_gt(_contrast(UiStyle.PAPER, UiStyle.INK_OK), 4.5, "the 'have' ink is legible too")


func test_pad_cursor_walks_the_cloth_and_the_flap() -> void:
	# 8 items on a 6-wide cloth (rows 0-1), 3 in a container's 4-wide flap.
	assert_eq(SalvageRoll.pad_step(-1, Vector2i(1, 0), 8, 3, 6, 4), 0, "the first press lands on the first item")
	assert_eq(SalvageRoll.pad_step(0, Vector2i(1, 0), 8, 3, 6, 4), 1)
	assert_eq(SalvageRoll.pad_step(1, Vector2i(0, 1), 8, 3, 6, 4), 7, "down a row")
	assert_eq(SalvageRoll.pad_step(7, Vector2i(0, 1), 8, 3, 6, 4), 7, "no row below: stays")
	assert_eq(SalvageRoll.pad_step(5, Vector2i(1, 0), 8, 3, 6, 4), 8, "off the cloth's right edge into the flap")
	assert_eq(SalvageRoll.pad_step(8, Vector2i(-1, 0), 8, 3, 6, 4), 5, "and back")
	assert_eq(SalvageRoll.pad_step(5, Vector2i(1, 0), 8, 0, 6, 4), 5, "no flap: the edge holds")
	assert_eq(SalvageRoll.pad_step(0, Vector2i(1, 0), 0, 0, 6, 4), -1)
