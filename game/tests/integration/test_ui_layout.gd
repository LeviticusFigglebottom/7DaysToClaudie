extends GutTest
## Full-screen UIs must actually fill the screen. The field manual and salvage roll once anchored
## themselves with set_anchors_preset() from _ready(), which keeps the 0x0 rect for a control
## already in the tree, so both collapsed to their contents' minimum size.


func test_full_screen_uis_fill_the_viewport() -> void:
	var ui := GameUI.new()
	add_child_autofree(ui)
	await get_tree().process_frame
	var vp: Vector2 = get_viewport().get_visible_rect().size
	assert_eq(ui.manual.size, vp, "field manual fills the screen")
	assert_eq(ui.roll.size, vp, "salvage roll fills the screen")
