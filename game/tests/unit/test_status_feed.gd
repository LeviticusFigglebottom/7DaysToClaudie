extends GutTest
## StatusFeed (first-week audit W15): lines queued together come out paced, highest priority
## first, and wait their gap after a line shown straight away.

var _feed: StatusFeed
var _lines: Array[String] = []


func before_each() -> void:
	_lines.clear()
	_feed = StatusFeed.new()
	add_child_autofree(_feed)
	# Driven by tick() alone (the test's clock), not the frame.
	_feed.set_process(false)
	Events.player_status_message.connect(_on_line)


func after_each() -> void:
	Events.player_status_message.disconnect(_on_line)


func _on_line(text: String, _kind: StringName) -> void:
	_lines.append(text)


func test_dawn_lines_come_out_paced_with_the_report_first() -> void:
	assert_almost_eq(_feed.min_gap, 1.5, 0.001, "data: config/status_messages.json")
	# The dawn after a Hum, in the order the handlers ran.
	Events.status_message_queued.emit("A Program drone is overhead.", &"level", StatusFeed.PRIORITY_NORMAL)
	Events.status_message_queued.emit("Dawn. Progress saved.", &"info", 5)
	Events.status_message_queued.emit("The Hum fades.", &"info", StatusFeed.PRIORITY_REPORT)
	Events.status_message_queued.emit("Level 3.", &"level", 3)
	assert_eq(_feed.pending(), 4)
	_feed.tick(0.016)
	assert_eq(_lines, ["The Hum fades."] as Array[String], "the report first, at once")
	_feed.tick(1.0)
	assert_eq(_lines.size(), 1, "nothing inside the gap")
	_feed.tick(0.6)
	assert_eq(_lines.back(), "Dawn. Progress saved.")
	_feed.tick(1.6)
	assert_eq(_lines.back(), "Level 3.")
	_feed.tick(1.6)
	assert_eq(_lines.back(), "A Program drone is overhead.")
	assert_eq(_feed.pending(), 0)


func test_a_direct_line_resets_the_gap_and_duplicates_merge() -> void:
	_feed.tick(5.0)
	Events.player_status_message.emit("Too far away.", &"info")
	Events.status_message_queued.emit("You're cold.", &"warning", StatusFeed.PRIORITY_WARNING)
	Events.status_message_queued.emit("You're cold.", &"warning", StatusFeed.PRIORITY_WARNING)
	assert_eq(_feed.pending(), 1, "the same line waits once")
	_feed.tick(1.0)
	assert_eq(_lines, ["Too far away."] as Array[String], "the queued line waits the gap after a direct one")
	_feed.tick(0.6)
	assert_eq(_lines.back(), "You're cold.")


func test_the_queue_is_bounded() -> void:
	for i: int in _feed.max_queued + 5:
		_feed.push("line %d" % i, &"info", 0)
	_feed.push("urgent", &"danger", 9)
	assert_eq(_feed.pending(), _feed.max_queued)
	_feed.tick(0.1)
	assert_eq(_lines.back(), "urgent", "a higher priority is never the one dropped")


## W19: waking in a blizzard, the cold ladder's steps leave the feed in order, each its gap apart.
func test_a_warning_ladder_comes_out_in_order() -> void:
	_feed.tick(5.0)
	var s := SurvivalStats.new()
	s.body_temp = 35.2
	for warn: Dictionary in SurvivalWarnings.new().update(s, 5.0):
		Events.status_message_queued.emit(str(warn["text"]), warn["kind"], StatusFeed.PRIORITY_WARNING)
	assert_eq(_feed.pending(), 2)
	_feed.tick(0.016)
	assert_eq(_lines, ["You're cold. Find shelter or a fire."] as Array[String])
	_feed.tick(1.0)
	assert_eq(_lines.size(), 1, "spaced")
	_feed.tick(0.6)
	assert_eq(_lines.back(), "You're freezing. Find a fire, now.")
