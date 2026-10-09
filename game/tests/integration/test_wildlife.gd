extends GutTest
## Wildlife against real nodes (ADR-0027): a flock's flush is a sound a Hollowed hears and walks
## to; a shot deer bolts its band and becomes a carcass that bleeds scent; butchering it through
## the command bus pays out its cuts once, and only to someone with a blade.

const PLAYER_SCENE: String = "res://src/player/player.tscn"

var _prev: GameSession
var _stimuli: Stimuli
var _manager: WildlifeManager


func before_each() -> void:
	_prev = Game.session
	Game.session = GameSession.create_new({"seed": 2727, "game_mode": "survival"})
	_stimuli = Stimuli.new()
	add_child_autofree(_stimuli)
	_stimuli.recenter(Vector3.ZERO)
	_manager = WildlifeManager.new()
	add_child_autofree(_manager)
	_manager.setup_world(null)


func after_each() -> void:
	Game.session = _prev


func _player_at(pos: Vector3) -> Player:
	var p: Player = (load(PLAYER_SCENE) as PackedScene).instantiate() as Player
	add_child_autofree(p)
	p.bind_state(Game.session.local_player())
	p.global_position = pos
	p.state.position = pos
	return p


func _deer_band(n: int, at: Vector3) -> Array:
	var d := Content.get_def(&"wildlife", &"white_tailed_deer") as WildlifeDef
	return _manager.spawn_band(d, {"id": &"w:test:0", "def": d.id, "pos": Vector2(at.x, at.z), "count": n, "seed": 11})


func test_a_flush_brings_the_hollowed() -> void:
	var crow := Content.get_def(&"wildlife", &"crow") as WildlifeDef
	var perches: Array[Vector3] = []
	for i: int in 5:
		perches.append(Vector3(i * 0.5, 0.0, 0.0))
	var flock := BirdFlock.new()
	flock.setup(&"f:test", crow, null, perches, 5)
	add_child_autofree(flock)
	var e := Enemy.new()
	e.setup(&"test:hollow", Content.enemy(&"hollow"), null, {"tier": "normal"})
	add_child_autofree(e)
	e.global_position = Vector3(35, 0, 0)
	e.rotation.y = 0.0
	# the player is far off and out of sight: the Hollowed can only learn of them from the birds
	var p: Player = _player_at(Vector3(-400, 0, 0))
	await get_tree().physics_frame
	e.state = Enemy.State.IDLE
	e._heard_seq = _stimuli.last_seq()
	flock.flush(Vector3(-5, 0, 0), "person")
	var heard: Stimuli.SoundEvent = null
	for s: Stimuli.SoundEvent in _stimuli.sounds:
		if s.kind == &"bird_flush":
			heard = s
	assert_not_null(heard, "the flush is in the stimulus field")
	assert_eq(heard.loudness, crow.flush_loudness * _stimuli.weather_noise_mask)
	e._perceive(p, e.global_position.distance_to(p.global_position))
	assert_eq(e.state, Enemy.State.INVESTIGATE, "the Hollowed goes to see what put the birds up")
	assert_lt(Vector2(e.target_pos.x - 1.0, e.target_pos.z).length(), 4.0, "towards the flock")


func test_a_flock_takes_off_and_lands_again() -> void:
	var song := Content.get_def(&"wildlife", &"songbird_ground") as WildlifeDef
	var perches: Array[Vector3] = [Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 0, 1)]
	var flock := BirdFlock.new()
	flock.setup(&"f:song", song, null, perches, 9)
	add_child_autofree(flock)
	await get_tree().process_frame
	flock.flush(Vector3(-3, 0, 0), "person")
	assert_eq(flock.state, BirdFlock.State.FLUSHING)
	await get_tree().create_timer(1.5).timeout
	var up: float = 0.0
	for b: Dictionary in flock.birds:
		up = maxf(up, (b["pos"] as Vector3).y)
	assert_gt(up, 1.0, "they climb away")
	assert_gt(flock.center().x, 2.5, "away from what flushed them")


func test_shot_deer_bolts_the_band_and_bleeds_scent() -> void:
	var herd: Array = _deer_band(3, Vector3.ZERO)
	assert_eq(herd.size(), 3)
	await get_tree().physics_frame
	var a: Animal = herd[1]
	var info := DamageInfo.make(500.0, &"pierce", &"gunshot", Game.session.local_player_id)
	info.hit_pos = a.global_position + Vector3.UP
	info.source_pos = a.global_position + Vector3(0, 0, -20)
	info.direction = Vector3(0, 0, 1)
	a.take_damage(info)
	assert_false(a.is_alive(), "dead")
	for o: Animal in herd:
		if o != a:
			assert_eq(o.state, Animal.State.FLEE, "the rest of the band bolts")
	var start: float = (herd[0] as Animal).global_position.distance_to(a.global_position)
	for i: int in 60:
		await get_tree().physics_frame
	assert_gt((herd[0] as Animal).global_position.distance_to(a.global_position), start + 2.0, "and runs")
	assert_gt(_stimuli.scent_at(a.global_position), 1.0, "a kill bleeds scent the Hollowed follow")
	assert_eq(int(_manager.taken.get(&"w:test:0", 0)), 1, "the band is one short when it comes back")


func test_butchering_needs_a_blade_and_pays_once() -> void:
	var herd: Array = _deer_band(1, Vector3(3, 0, 0))
	await get_tree().physics_frame
	var a: Animal = herd[0]
	var p: Player = _player_at(a.global_position + Vector3(1.5, 0, 0))
	var st: PlayerState = p.state
	var r0: Dictionary = Game.execute(&"wildlife.butcher", {"player": st.id, "animal": a.entity_id})
	assert_false(bool(r0["ok"]), "not while it's alive")
	var info := DamageInfo.make(500.0, &"slash", &"melee", st.id)
	a.take_damage(info)
	var r1: Dictionary = Game.execute(&"wildlife.butcher", {"player": st.id, "animal": a.entity_id})
	assert_false(bool(r1["ok"]), "no knife, no axe")
	st.inventory.add_item(&"kitchen_knife", 1)
	var r2: Dictionary = Game.execute(&"wildlife.butcher", {"player": st.id, "animal": a.entity_id})
	assert_true(bool(r2["ok"]), str(r2))
	var want: Dictionary = WildlifeManager.butcher_yields(a.def, a.entity_id, Game.session.world_seed, &"kitchen_knife")
	assert_eq(r2["items"], want)
	for k: String in want:
		assert_eq(st.inventory.count_of(StringName(k)), int(want[k]), "%s in the pack" % k)
	var r3: Dictionary = Game.execute(&"wildlife.butcher", {"player": st.id, "animal": a.entity_id})
	assert_false(bool(r3["ok"]), "only once")


func test_butcher_reach_matches_the_prompt_and_follows_the_player() -> void:
	# First-week audit W3: the prompt showed at 1.6 m but the command said "Too far away". The
	# command measured from PlayerState.position, written only on save, and the two reaches
	# differed. The state follows the body every frame, and the reach is the interaction ray's
	# plus half the carcass.
	var herd: Array = _deer_band(1, Vector3(3, 0, 0))
	await get_tree().physics_frame
	var a: Animal = herd[0]
	var p: Player = _player_at(a.global_position + Vector3(30, 0, 0))
	var st: PlayerState = p.state
	st.inventory.add_item(&"kitchen_knife", 1)
	a.take_damage(DamageInfo.make(500.0, &"slash", &"melee", st.id))
	var ray: float = float(Content.config(&"player").get("interact_range", 2.6))
	assert_gt(WildlifeManager.butcher_reach(a.def), ray, "at least as far as the prompt shows")
	# Walk up to it (the body moves; nothing writes the state but the player's own frame).
	p.global_position = a.global_position + Vector3(1.6, 0, 0)
	await get_tree().physics_frame
	await get_tree().physics_frame
	var r: Dictionary = Game.execute(&"wildlife.butcher", {"player": st.id, "animal": a.entity_id})
	assert_true(bool(r["ok"]), "butchered from 1.6 m: %s" % str(r))
