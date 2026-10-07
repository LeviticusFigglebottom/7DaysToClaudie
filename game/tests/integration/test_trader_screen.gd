extends GutTest
## The Waystation trade screen (ADR-0039, TD-148) built headless on a post: shop rows carry an icon
## and a tooltip, and the count picked on a row goes through trade.buy / trade.sell as `count`.

class FakeWorld:
	extends Node3D
	var ai: Node = null
	var pois: Node = null
	var terrain: Node = null
	var player: Node3D = null
	var ui: Node = null

	func height_at(_x: float, _z: float) -> float:
		return 0.0


const POST := Vector3(100, 0, 100)
const POST_ID := "trader:waystation_9"

var _prev: GameSession
var _tm: TraderManager
var _p: PlayerState
var _td: TraderDef
var _screen: TraderScreen
var _item: String


func before_each() -> void:
	_prev = Game.session
	Game.session = GameSession.create_new({"seed": 4471, "game_mode": "slice"})
	_p = Game.session.local_player()
	_p.position = POST + Vector3(0, 0, 6)
	_td = Content.get_def(&"trader", &"waystation_9") as TraderDef
	var world := FakeWorld.new()
	add_child_autofree(world)
	_tm = TraderManager.new()
	world.add_child(_tm)
	_tm.setup_world(world)
	_tm.add_post(POST_ID, _td, POST, -90.0, false)
	var stock: Dictionary = _tm.stock_of(&"waystation_9")
	_item = "water_bottle_clean" if stock.has("water_bottle_clean") else "canned_beans"
	_screen = TraderScreen.new()
	_screen.manager = _tm
	add_child_autofree(_screen)


func after_each() -> void:
	_screen.close_screen()
	Game.session = _prev


func _row(tab: String, item: String) -> HBoxContainer:
	return _screen.find_child("%s_%s" % [tab, item], true, false) as HBoxContainer


func _stock(item: String) -> int:
	return int((_tm.stock_of(&"waystation_9").get(item, {"count": 0}) as Dictionary)["count"])


func test_rows_have_icons_and_tooltips() -> void:
	_p.inventory.add_item(&"scrip", 100)
	_screen.open(POST_ID, "shop")
	var row: HBoxContainer = _row("buy", _item)
	assert_not_null(row, "a buy row for %s" % _item)
	if row == null:
		return
	var icon: TextureRect = row.get_node("Icon") as TextureRect
	assert_not_null(icon.texture, "the row has an icon even before assets are generated")
	var idef: ItemDef = Content.item(StringName(_item))
	assert_string_contains(row.tooltip_text, idef.description)
	assert_string_contains(row.tooltip_text, "%d scrip each" % _td.buy_price(idef, 0))
	assert_string_contains(row.tooltip_text, "%d on the shelf" % _stock(_item))


func test_buying_the_picked_count_goes_through_the_command() -> void:
	_p.inventory.add_item(&"scrip", 100)
	var price: int = _td.buy_price(Content.item(StringName(_item)), 0)
	var before: int = _stock(_item)
	var n: int = mini(3, before)
	assert_gt(n, 1, "enough on the shelf to buy several")
	_screen.open(POST_ID, "shop")
	watch_signals(Events)
	var row: HBoxContainer = _row("buy", _item)
	(row.get_node("Count") as SpinBox).value = n
	assert_eq((row.get_node("Action") as Button).text, "Buy %d  (%d)" % [n, n * price])
	(row.get_node("Action") as Button).pressed.emit()
	assert_eq(_p.inventory.count_of(StringName(_item)), n, "bought %d in one trade" % n)
	assert_eq(_p.inventory.count_of(&"scrip"), 100 - n * price)
	assert_eq(_stock(_item), before - n)
	assert_signal_emit_count(Events, "trade_made", 1)
	assert_signal_emitted_with_parameters(Events, "trade_made", [_p.id, &"waystation_9", StringName(_item), n, -n * price])


func test_max_is_what_you_can_afford() -> void:
	var price: int = _td.buy_price(Content.item(StringName(_item)), 0)
	_p.inventory.add_item(&"scrip", price * 2)
	_screen.open(POST_ID, "shop")
	var row: HBoxContainer = _row("buy", _item)
	assert_gt(_stock(_item), 2, "the shelf holds more than you can afford")
	(row.get_node("Most") as Button).pressed.emit()
	assert_eq(int((row.get_node("Count") as SpinBox).value), 2)
	(row.get_node("Action") as Button).pressed.emit()
	assert_eq(_p.inventory.count_of(&"scrip"), 0)
	assert_eq(_p.inventory.count_of(StringName(_item)), 2)
	# Broke now: the row stays but can't be used.
	row = _row("buy", _item)
	assert_true((row.get_node("Action") as Button).disabled, "no scrip, no buy button")


func test_selling_all_sends_the_whole_count() -> void:
	_p.inventory.add_item(StringName(_item), 5)
	var each: int = _td.sell_price(Content.item(StringName(_item)))
	_screen.open(POST_ID, "shop")
	_screen.set(&"_tab", "sell")
	_screen.call(&"_refresh")
	var row: HBoxContainer = _row("sell", _item)
	assert_not_null(row, "a sell row for what you carry")
	if row == null:
		return
	assert_string_contains(row.tooltip_text, "you have 5")
	(row.get_node("Most") as Button).pressed.emit()
	(row.get_node("Action") as Button).pressed.emit()
	assert_eq(_p.inventory.count_of(StringName(_item)), 0, "sold all five at once")
	assert_eq(_p.inventory.count_of(&"scrip"), 5 * each)
