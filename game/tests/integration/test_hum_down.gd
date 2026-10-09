extends GutTest
## The Hum and a player who goes down during it (first-week audit W7/W15): a player who died during
## the night is not paid for surviving it; the night's report is queued first among the dawn's
## lines; the first Hum on the default rules is a real threat (W14).

var _prev: GameSession


func before_each() -> void:
	_prev = Game.session
	Game.session = GameSession.create_new({"seed": 9, "game_mode": "slice"})


func after_each() -> void:
	Game.session = _prev


func _end_night(hum: HumDirector) -> void:
	hum.active = true
	hum.report = {"day": 7, "spawned": HumDirector._zeros(), "killed": HumDirector._zeros(), "breaches": HumDirector._zeros(), "causes": {}, "total": 0}
	hum._on_end(7, {})


func test_a_death_during_the_night_forfeits_the_survival_award() -> void:
	var hum := HumDirector.new()
	add_child_autofree(hum)
	var p: PlayerState = Game.session.local_player()
	hum._deaths_at_start = {p.id: p.deaths}
	var xp0: Array = [p.progression.level, p.progression.xp]
	p.deaths += 1
	_end_night(hum)
	assert_eq([p.progression.level, p.progression.xp], xp0, "died during the Hum: no award")
	hum._deaths_at_start = {p.id: p.deaths}
	_end_night(hum)
	assert_ne([p.progression.level, p.progression.xp], xp0, "stood through the night: paid")


func test_the_nights_report_is_queued_first_among_the_dawns_lines() -> void:
	var hum := HumDirector.new()
	add_child_autofree(hum)
	var got: Array = []
	var on_q := func(text: String, _kind: StringName, priority: int) -> void: got.append([text, priority])
	Events.status_message_queued.connect(on_q)
	_end_night(hum)
	Events.status_message_queued.disconnect(on_q)
	assert_eq(got.size(), 1)
	assert_string_contains(str(got[0][0]), "The Hum fades.")
	assert_eq(int(got[0][1]), StatusFeed.PRIORITY_REPORT)


## W14: on the default rules (hum_size 1) the first Hum, day 7 at the audit's gamestage 14, plans
## 17 Hollowed over its night (12 base + 0 per earlier Hum + 0.4 x 14), well under the 64-alive
## cap; the audit's four were its first wave alone (the driver skipped the clock to 03:54).
func test_the_first_hum_on_the_default_rules_is_a_real_threat() -> void:
	var mem := HordeMemory.new()
	var rng := RandomNumberGenerator.new()
	rng.seed = 7
	var plan: Dictionary = mem.plan(14, rng)
	assert_eq(int(plan["total"]), 17)
	assert_between(int(plan["total"]), 12, 20)
	var n: int = 0
	for w: Dictionary in plan["waves"]:
		for k: Variant in (w["units"] as Dictionary).keys():
			n += int(w["units"][k])
	assert_eq(n, 17, "every one is in a wave")
	assert_eq((plan["waves"] as Array).size(), 4)
