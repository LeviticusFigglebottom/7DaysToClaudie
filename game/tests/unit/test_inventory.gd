extends GutTest


func test_add_stacks_and_counts() -> void:
	var inv := Inventory.new()
	assert_eq(inv.add_item(&"stick", 25), 0)
	assert_eq(inv.count_of(&"stick"), 25)
	assert_eq(inv.stacks.size(), 2, "stack_max 20 splits into 20 + 5")


func test_carry_cap_enforced() -> void:
	var inv := Inventory.new(&"p", 0, 0.0, true)
	var leftover: int = inv.add_item(&"log", 5)
	assert_eq(inv.count_of(&"log"), 2, "logs capped at 2 on the shoulder")
	assert_eq(leftover, 3)


func test_bulk_cap_enforced() -> void:
	var inv := Inventory.new(&"p", 0, 4.0, false)
	var leftover: int = inv.add_item(&"stone", 10)  # 0.8 bulk each
	assert_eq(inv.count_of(&"stone"), 5)
	assert_eq(leftover, 5)
	assert_almost_eq(inv.total_bulk(), 4.0, 0.001)


func test_slot_cap_enforced() -> void:
	var inv := Inventory.new(&"c", 2)
	inv.add_item(&"stick", 20)
	inv.add_item(&"stone", 10)
	assert_eq(inv.add_item(&"cloth", 1), 1, "no free slot")
	assert_eq(inv.add_item(&"stick", 5), 5, "existing stick stack is full")


func test_remove_is_all_or_nothing() -> void:
	var inv := Inventory.new()
	inv.add_item(&"cloth", 3)
	assert_false(inv.remove(&"cloth", 4))
	assert_eq(inv.count_of(&"cloth"), 3)
	assert_true(inv.remove(&"cloth", 3))
	assert_true(inv.is_empty())


func test_remove_all_atomic() -> void:
	var inv := Inventory.new()
	inv.add_item(&"stick", 2)
	inv.add_item(&"stone", 1)
	assert_false(inv.remove_all({&"stick": 1, &"stone": 2}))
	assert_eq(inv.count_of(&"stick"), 2, "nothing removed on failure")
	assert_true(inv.remove_all({&"stick": 1, &"stone": 1}))
	assert_eq(inv.count_of(&"stick"), 1)


func test_quality_items_do_not_merge() -> void:
	var inv := Inventory.new()
	inv.add_item(&"machete", 1, 2)
	inv.add_item(&"machete", 1, 5)
	assert_eq(inv.stacks.size(), 2)
	assert_true(inv.remove(&"machete", 1))
	assert_eq(inv.first(&"machete").quality, 5, "lowest quality consumed first")


func test_serialization_round_trip() -> void:
	var inv := Inventory.new(&"p:1", 0, 40.0, true)
	inv.add_item(&"stone_axe", 1, 3)
	inv.add_item(&"nails", 37)
	var copy: Inventory = Inventory.from_dict(JSON.parse_string(JSON.stringify(inv.to_dict())))
	assert_eq(copy.to_dict(), inv.to_dict())


func test_transfer_all() -> void:
	var a := Inventory.new()
	var b := Inventory.new(&"c", 1)
	a.add_item(&"stick", 30)
	var moved: int = a.transfer_all_to(b)
	assert_eq(moved, 20, "one slot of 20")
	assert_eq(a.count_of(&"stick"), 10)


func test_find_tool() -> void:
	var inv := Inventory.new()
	assert_null(inv.find_tool("axe"))
	inv.add_item(&"stone_axe")
	assert_not_null(inv.find_tool("axe"))
