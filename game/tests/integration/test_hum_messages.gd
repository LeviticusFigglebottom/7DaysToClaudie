extends GutTest
## A Hum warning is announced once on the HUD: HumDirector's line with the forecast (GameUI used to
## post a second, vaguer one of its own for every warning and for the start).

var _prev: GameSession


func before_each() -> void:
	_prev = Game.session
	Game.session = GameSession.create_new({"seed": 9, "game_mode": "slice"})


func after_each() -> void:
	Game.session = _prev


func test_each_hum_warning_posts_one_line() -> void:
	var ui := GameUI.new()
	add_child_autofree(ui)
	var hum := HumDirector.new()
	add_child_autofree(hum)
	await get_tree().process_frame
	for hours: float in [24.0, 6.0, 1.0]:
		var before: int = ui._messages.get_child_count()
		Events.horde_night_warning.emit(3, hours)
		assert_eq(ui._messages.get_child_count(), before + 1, "one line %d hours ahead" % int(hours))
	var last: Label = ui._messages.get_child(ui._messages.get_child_count() - 1) as Label
	assert_string_contains(last.text, "Within the hour, they come", "the director's warning is the one kept")
