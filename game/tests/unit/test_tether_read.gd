extends GutTest
## Reading the tether with each hold (player report 5): a hold whose wrist can't come up with its
## item (the rifle) or not into view (the bow) reads with empty hands, the item put away for the
## moment; the rest read with the item in hand.


func test_the_rifle_and_the_bow_read_with_the_item_put_away() -> void:
	assert_true(ViewModelHolds.reads_stowed(&"rifle"), "no_tether: both hands on the gun")
	assert_true(ViewModelHolds.reads_stowed(&"bow"), "tether_stow: the bow hand is the reading wrist")


func test_other_holds_read_with_the_item_in_hand() -> void:
	for cls: StringName in [&"one_hand", &"two_hand", &"knife", &"spear", &"lighter", &"light_left", &"pistol"]:
		assert_false(ViewModelHolds.reads_stowed(cls), "%s keeps its item" % cls)
