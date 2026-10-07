extends GutTest
## The Ashen's arithmetic (ADR-0048): the faction and its fighters load clean; hostility gives a
## level only with the gamestage behind it; aggression scales what provokes them; curiosity alone
## never brings a raid; the day's scout and raid are the same for the same world and day, never a
## raid on a Hum day or in the grace days; morale breaks, except at home; and only the outsider's
## fire in front of them frightens them.

var _fd: FactionDef


func before_each() -> void:
	_fd = AshenBrain.def()


func test_the_faction_and_its_fighters_load() -> void:
	assert_not_null(_fd)
	assert_gt(_fd.levels.size(), 3, "unaware, watchers, raids, war parties")
	for id: StringName in [&"ashen_raider", &"ashen_scout"]:
		var ed: EnemyDef = Content.enemy(id)
		assert_not_null(ed, String(id))
		assert_eq(ed.faction, "ashen")
		assert_eq(ed.archetype, "tribe")
		assert_eq(float(ed.atk("infection", 1.0)), 0.0, "the Ashen are not the Bloom")
	for e: String in Content.errors():
		assert_false(e.contains("factions/") or e.contains("enemies/ashen"), e)


func test_a_level_needs_its_gamestage() -> void:
	assert_eq(AshenBrain.level_for(_fd, 0.0, 99), 0)
	assert_eq(AshenBrain.level_for(_fd, 50.0, 0), 0, "a new player is not raided however angry they are")
	assert_eq(AshenBrain.level_for(_fd, 50.0, 5), 1, "watched first")
	assert_eq(AshenBrain.level_for(_fd, 50.0, 12), 2)
	assert_eq(AshenBrain.level_for(_fd, 500.0, 99), 3)


func test_aggression_scales_and_hostility_is_capped() -> void:
	var calm: float = AshenBrain.gain(_fd, 0.0, "kill", 1.0, "calm")
	var fierce: float = AshenBrain.gain(_fd, 0.0, "kill", 1.0, "fierce")
	assert_gt(fierce, calm)
	assert_eq(AshenBrain.gain(_fd, 0.0, "nothing_known"), 0.0)
	assert_eq(AshenBrain.gain(_fd, 0.0, "camp_wiped", 100.0), float(_fd.hostility.get("max", 150.0)))


func test_curiosity_alone_never_brings_a_raid() -> void:
	var raid_at: float = float((_fd.levels[2] as Dictionary)["at"])
	var h: float = 0.0
	for day: int in 200:
		h = AshenBrain.dawn(_fd, h)
	assert_lt(h, raid_at, "watched, never raided, without provocation")
	assert_gt(h, float((_fd.levels[1] as Dictionary)["at"]), "but they do come to watch")
	assert_lt(AshenBrain.dawn(_fd, raid_at + 20.0), raid_at + 20.0, "anger fades without fresh provocation")


func test_the_days_rolls_are_deterministic_and_keep_off_hum_days() -> void:
	var raids: int = 0
	for day: int in range(1, 80):
		var a: Dictionary = AshenBrain.raid_roll(_fd, 4471, day, 2, 15, false)
		assert_eq(a, AshenBrain.raid_roll(_fd, 4471, day, 2, 15, false), "same world, same day")
		assert_true(AshenBrain.raid_roll(_fd, 4471, day, 2, 15, true).is_empty(), "never on a Hum day")
		assert_true(AshenBrain.raid_roll(_fd, 4471, day, 1, 15, false).is_empty(), "watchers don't raid")
		if not a.is_empty():
			raids += 1
			assert_gt(day, int(_fd.raids["grace_days"]), "not in the grace days")
			assert_eq((a["members"] as Array).size(), int(a["size"]))
			assert_between(float(a["hour"]), 18.0, 20.0, "at dusk")
			for m: Variant in a["members"]:
				assert_eq(Content.enemy(StringName(str(m))).faction, "ashen")
		assert_eq(AshenBrain.scout_roll(_fd, 4471, day, 1), AshenBrain.scout_roll(_fd, 4471, day, 1))
		assert_true(AshenBrain.scout_roll(_fd, 4471, day, 0).is_empty(), "nobody watches yet")
	assert_between(raids, 8, 40, "some days, not every day: %d" % raids)


func test_war_parties_are_bigger_and_grow_with_gamestage() -> void:
	var rng := RandomNumberGenerator.new()
	var raid_n: int = 0
	var war_n: int = 0
	for i: int in 50:
		rng.seed = i
		raid_n += AshenBrain.raid_size(_fd, 2, 10, rng)
		rng.seed = i
		war_n += AshenBrain.raid_size(_fd, 3, 10, rng)
	assert_gt(war_n, raid_n)
	rng.seed = 3
	var small: int = AshenBrain.raid_size(_fd, 3, 0, rng)
	rng.seed = 3
	assert_gt(AshenBrain.raid_size(_fd, 3, 60, rng), small)
	rng.seed = 3
	assert_lte(AshenBrain.raid_size(_fd, 3, 9999, rng), int(_fd.raids["max_size"]))


func test_morale_breaks_except_at_home() -> void:
	var m: float = 1.0
	for i: int in 4:
		m = AshenBrain.mate_down(_fd, m, false)
	assert_true(AshenBrain.breaks(_fd, m), "four mates down and it runs")
	var home: float = 1.0
	for i2: int in 10:
		home = AshenBrain.mate_down(_fd, home, true)
		home = AshenBrain.hurt(_fd, home, 0.5, true)
	assert_false(AshenBrain.breaks(_fd, home), "they defend home to the end")
	assert_lt(AshenBrain.hurt(_fd, 1.0, 0.5, false), 1.0)
	assert_almost_eq(AshenBrain.near_fire(_fd, 0.5, 0.0, 10.0, false), 0.5 + float(_fd.morale["recover_per_s"]) * 10.0, 0.0001, "it recovers away from fire")


func test_only_the_outsiders_fire_in_front_frightens_them() -> void:
	var flame := Vector3.ZERO
	var facing := Vector3(0, 0, 1)
	var ahead: float = AshenBrain.fire_fear(_fd, Vector3(0, 0, 4), flame, facing, [])
	var behind: float = AshenBrain.fire_fear(_fd, Vector3(0, 0, -4), flame, facing, [])
	assert_gt(ahead, 0.4, "a torch held up at them")
	assert_eq(behind, 0.0, "one behind the player still comes on")
	assert_eq(AshenBrain.fire_fear(_fd, Vector3(0, 0, 40), flame, facing, []), 0.0, "too far to matter")
	assert_eq(AshenBrain.fire_fear(_fd, Vector3(0, 0, 4), Vector3.INF, facing, []), 0.0, "no flame, no fear")
	assert_gt(AshenBrain.fire_fear(_fd, Vector3(2, 0, 0), Vector3.INF, facing, [Vector3.ZERO]), 0.3, "a lit fire at the base")
	assert_eq(AshenBrain.fire_to_avoid(_fd, Vector3(1, 0, 0), Vector3.INF, [Vector3.ZERO]), Vector3.ZERO)
	assert_eq(AshenBrain.fire_to_avoid(_fd, Vector3(20, 0, 0), Vector3.INF, [Vector3.ZERO]), Vector3.INF)
	assert_gt(AshenBrain.near_fire(_fd, 1.0, 0.0, 1.0, false), AshenBrain.near_fire(_fd, 1.0, 1.0, 1.0, false))
