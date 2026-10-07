extends GutTest
## The Hollowed's committed reactions (char_anim root-motion clips): a heavy blunt blow floors a
## walker (knockdown, a hold on the ground, wake_lie gets it up, then back to the hunt), a light or
## cutting one only staggers, bodies without the new clips never go down or trip, and a chasing
## walker stumbles now and then, slowed to the stumble pace while the clip plays. The clips are
## injected (a stand-in AnimationPlayer), so this runs with or without generated assets.


func _floor() -> void:
	var b := StaticBody3D.new()
	var cs := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = Vector3(60, 1, 60)
	cs.shape = shape
	b.add_child(cs)
	add_child_autofree(b)
	b.global_position = Vector3(0, -0.5, 0)


func _enemy(id: StringName) -> Enemy:
	var e := Enemy.new()
	e.setup(StringName("test:react:%s" % id), Content.enemy(id), null, {"tier": "normal"})
	add_child_autofree(e)
	return e


## Gives the body an AnimationPlayer holding just `clips` (name -> seconds).
func _clips(e: Enemy, clips: Dictionary) -> void:
	var ap := AnimationPlayer.new()
	var lib := AnimationLibrary.new()
	for n: String in ["idle", "walk", "walk_b", "run", "hit_front", "hit_back", "stagger"]:
		if not clips.has(n):
			clips[n] = 0.6
	for n: String in clips:
		var a := Animation.new()
		a.length = float(clips[n])
		lib.add_animation(StringName(n), a)
	ap.add_animation_library(&"", lib)
	e.visual.add_child(ap)
	e.visual.anim = ap


func _blow(e: Enemy, amount: float, type: StringName, stagger: float) -> void:
	var info := DamageInfo.make(amount, type, &"melee", &"")
	info.hit_pos = Vector3.ZERO  # torso
	info.direction = -e.global_transform.basis.z  # from the front
	info.stagger = stagger
	e.take_damage(info)


func test_heavy_blunt_blow_knocks_down_then_it_gets_up() -> void:
	_floor()
	var e: Enemy = _enemy(&"hollow")
	await get_tree().physics_frame
	_clips(e, {"knockdown": 1.2, "wake_lie": 1.33, "stumble": 1.0})
	e.state = Enemy.State.CHASE
	_blow(e, 60.0, &"blunt", 0.6)
	assert_eq(e.state, Enemy.State.STAGGER)
	assert_true(e._down, "floored")
	assert_eq(e.visual.current_anim, &"knockdown")
	assert_almost_eq(e._rise_at, 1.2 + Enemy.KNOCKDOWN_HOLD, 0.01, "lies there before getting up")
	assert_almost_eq(e._stagger_t, 1.2 + Enemy.KNOCKDOWN_HOLD + 1.33, 0.01, "down for the fall, the hold and the get-up")
	assert_true((e._shape.shape as CapsuleShape3D).height > 0.0 and absf(e._shape.rotation.x) > 1.0, "lying capsule")
	var pos0: Vector3 = e.global_position
	var rose: bool = false
	for i: int in 300:
		await get_tree().physics_frame
		if not rose and e.visual.current_anim == &"wake_lie":
			rose = true
			assert_false(e._down, "up off the ground once wake_lie starts")
			assert_gte(e._state_t, 1.2 + Enemy.KNOCKDOWN_HOLD - 0.05, "after the fall and the hold")
		if e.state != Enemy.State.STAGGER:
			break
	assert_true(rose, "got up with wake_lie")
	assert_ne(e.state, Enemy.State.STAGGER, "back on its feet and moving on")
	var moved: Vector3 = e.global_position - pos0
	assert_almost_eq(Vector2(moved.x, moved.z).length(), float(Enemy.RECOIL[&"knockdown"][0]), 0.12, "driven back by the blow")


func test_light_or_cutting_blows_only_stagger() -> void:
	_floor()
	var e: Enemy = _enemy(&"hollow")
	await get_tree().physics_frame
	_clips(e, {"knockdown": 1.2, "wake_lie": 1.33, "stumble": 1.0})
	var info := DamageInfo.make(60.0, &"slash", &"melee", &"")
	info.stagger = 0.6
	assert_false(e.knocks_down(info, 60.0), "a blade does not floor it")
	info.type = &"blunt"
	assert_false(e.knocks_down(info, 25.0), "a light blunt blow does not")
	info.stagger = 0.3
	assert_false(e.knocks_down(info, 60.0), "nor a heavy one with no weight behind it")
	info.type = &"explosive"
	assert_true(e.knocks_down(info, 20.0), "a blast does")
	_blow(e, 35.0, &"slash", 0.6)
	assert_eq(e.state, Enemy.State.STAGGER)
	assert_false(e._down)
	assert_eq(e.visual.current_anim, &"stagger", "a heavy cut from the front reels it back")


func test_bodies_without_the_new_clips_never_go_down_or_trip() -> void:
	_floor()
	var e: Enemy = _enemy(&"hollow")
	await get_tree().physics_frame
	_clips(e, {"wake_lie": 1.33})
	var info := DamageInfo.make(80.0, &"explosive", &"trap", &"")
	assert_false(e.knocks_down(info, 80.0), "no knockdown clip: no knockdown")
	assert_false(e.stumbles(3.0), "no stumble clip: no stumbles")
	_blow(e, 80.0, &"explosive", 1.0)
	assert_eq(e.state, Enemy.State.STAGGER, "it still reels")
	assert_false(e._down)


func test_chasing_walker_stumbles_and_slows() -> void:
	_floor()
	var e: Enemy = _enemy(&"hollow")
	# no player here: the brain would treat it as far off (it glides, never on the floor); stand it
	# on the ground by hand
	e.set_physics_process(false)
	for i: int in 10:
		await get_tree().physics_frame
		e.velocity = Vector3(0.0, -1.0, 0.0)
		e.move_and_slide()
	e._far = false
	_clips(e, {"knockdown": 1.2, "wake_lie": 1.33, "stumble": 1.0})
	assert_true(e.stumbles(3.0), "on its feet, on the ground, with the clip")
	assert_false(e.stumbles(0.3), "not when barely moving")
	var want := Vector3(3.0, 0.0, 0.0)
	var got := want
	var tries: int = 0
	while e._stumble_t <= 0.0 and tries < 200:
		e._stumble_cd = 0.0
		got = e._stumble_step(want, 0.016)
		tries += 1
	assert_gt(e._stumble_t, 0.0, "it trips sooner or later")
	assert_eq(e.visual.current_anim, &"stumble")
	assert_almost_eq(got.length(), Enemy.STUMBLE_SPEED, 0.01, "slowed to the stumble's pace")
	assert_almost_eq(e._stumble_step(want, 0.016).length(), Enemy.STUMBLE_SPEED, 0.01, "and kept there while it plays")
	e._stumble_t = 0.0
	e._stumble_cd = 5.0
	assert_eq(e._stumble_step(want, 0.016), want, "between stumbles it runs as it was")
