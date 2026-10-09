extends GutTest
## The death screen's words (the tether's incident log, ADR-0063).


func test_death_text_says_cause_consequence_and_where_you_wake() -> void:
	var t: Array[String] = GameUI.death_text("zombie", "Your pack lies where you fell.", false, 3, 1, false)
	assert_eq(t[0], "TETHER 4471  ·  DAY 3  ·  VITALS FLAT")
	assert_eq(t[1], "The Hollowed got you.")
	assert_string_contains(t[2], "the drop site")
	assert_false(t[2].contains("Deaths logged"), "the first death isn't counted aloud")
	var bed: Array[String] = GameUI.death_text("cold", "You keep everything you carried.", false, 9, 3, true)
	assert_string_contains(bed[2], "at your bed")
	assert_string_contains(bed[2], "Deaths logged: 3.")
	var last: Array[String] = GameUI.death_text("turned", "Your run is over.", true, 12, 1, true)
	assert_false(last[2].contains("wake"), "permadeath promises no waking")
	assert_eq(GameUI.death_text("unknown", "", false, 1, 1, false)[1], "You died.")
