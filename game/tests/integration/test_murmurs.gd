extends GutTest
## Murmurs (ADR-0034): a crow flock that turns into a Murmur once up follows its quarry and marks
## them (each caw a sound on the quarry, not on the birds); it loses them under cover and scatters
## to a gunshot; whether a flush becomes one is a deterministic roll the world setting can turn off.

var _prev: GameSession
var _stimuli: Stimuli
var _manager: WildlifeManager


func before_each() -> void:
	_prev = Game.session
	Game.session = GameSession.create_new({"seed": 2727, "game_mode": "survival"})
	Game.session.clock.set_time(10, 12.0)
	_stimuli = Stimuli.new()
	add_child_autofree(_stimuli)
	_stimuli.recenter(Vector3.ZERO)
	_manager = WildlifeManager.new()
	add_child_autofree(_manager)
	_manager.setup_world(null)


func after_each() -> void:
	Game.session = _prev


func _crows(id: StringName = &"f:murmur") -> BirdFlock:
	var crow := Content.get_def(&"wildlife", &"crow") as WildlifeDef
	var perches: Array[Vector3] = []
	for i: int in 6:
		perches.append(Vector3(float(i) * 0.6, 0.0, 0.0))
	var flock := BirdFlock.new()
	flock.setup(id, crow, null, perches, 5)
	add_child_autofree(flock)
	return flock


func _step(f: BirdFlock, seconds: float) -> void:
	for i: int in int(seconds * 20.0):
		f.advance(0.05)


func test_a_murmur_follows_its_quarry_and_marks_them() -> void:
	var f: BirdFlock = _crows()
	var quarry := Vector3(10, 0, 4)
	f.flush(quarry, "person")
	f.start_murmur(quarry)
	assert_true(f.is_murmur(), "pending while the flock gets up")
	_step(f, 2.0)
	assert_eq(f.state, BirdFlock.State.MURMUR)
	# the quarry walks off; the Murmur goes with them
	quarry = Vector3(40, 0, 30)
	for i: int in 40:
		f.murmur_update(quarry, false, 0.25)
		_step(f, 0.25)
	var c: Vector3 = f.center()
	assert_lt(Vector2(c.x - quarry.x, c.z - quarry.z).length(), 18.0, "it followed")
	assert_gt(f.marks, 0, "it called")
	var mark: Stimuli.SoundEvent = null
	for s: Stimuli.SoundEvent in _stimuli.sounds:
		if s.kind == &"murmur":
			mark = s
	assert_not_null(mark, "every caw is a sound the Hollowed hear")
	if mark != null:
		assert_lt(mark.pos.distance_to(quarry), 0.5, "the mark is on the quarry, not on the birds")


func test_cover_loses_it_and_a_gunshot_scatters_it() -> void:
	var f: BirdFlock = _crows()
	f.flush(Vector3.ZERO, "person")
	f.start_murmur(Vector3.ZERO)
	_step(f, 2.0)
	var cover: float = float(f.def.murmur.get("cover_seconds", 12.0))
	var t: float = 0.0
	while t < cover + 1.0 and f.state == BirdFlock.State.MURMUR:
		f.murmur_update(Vector3.ZERO, true, 0.5)
		t += 0.5
	assert_eq(f.state, BirdFlock.State.LEAVING, "under a roof long enough, the crows lose you")
	var g: BirdFlock = _crows(&"f:murmur2")
	g.flush(Vector3.ZERO, "person")
	g.start_murmur(Vector3.ZERO)
	_step(g, 2.0)
	g.end_murmur("scattered")
	assert_false(g.is_murmur())
	assert_eq(g.state, BirdFlock.State.LEAVING)


func test_the_roll_is_deterministic_and_the_setting_turns_it_off() -> void:
	var f: BirdFlock = _crows()
	var first: bool = _manager.murmur_rolls(f, Vector3.ZERO)
	assert_eq(_manager.murmur_rolls(f, Vector3.ZERO), first, "same flock, same flush: same answer")
	var hits: int = 0
	for i: int in 200:
		f.flush_count = i
		if _manager.murmur_rolls(f, Vector3.ZERO):
			hits += 1
	# gamestage gating aside, about chance x 200 of them
	var chance: float = float(f.def.murmur.get("chance", 0.2))
	if Game.session.gamestage(Game.local_player()) >= int(f.def.murmur.get("gamestage_min", 0)):
		assert_between(hits, int(chance * 200.0 * 0.5), int(chance * 200.0 * 1.6))
	Game.session.rules.values["murmurs"] = false
	hits = 0
	for i: int in 50:
		f.flush_count = i
		if _manager.murmur_rolls(f, Vector3.ZERO):
			hits += 1
	assert_eq(hits, 0, "the world setting turns Murmurs off")
	var songs := Content.get_def(&"wildlife", &"songbird_canopy") as WildlifeDef
	assert_true(songs.murmur.is_empty(), "only crows mark you")
