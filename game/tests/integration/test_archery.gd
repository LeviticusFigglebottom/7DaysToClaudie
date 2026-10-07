extends GutTest
## Arrows against real nodes (ADR-0057): an arrow's arc lands where its ballistics say and sticks
## in the ground facing its flight; it wounds a Hollow and a deer (piercing, the shooter's) and
## rides the body; one in the ground, or in a body once it's dead, is pulled out into the pack;
## a broken one is gone; and a loose from the player's bow spends an arrow and flies at the
## draw's speed.

const PLAYER_SCENE: String = "res://src/player/player.tscn"

var _prev: GameSession
var _stimuli: Stimuli
var _holder: Node3D


func before_each() -> void:
	_prev = Game.session
	Game.session = GameSession.create_new({"seed": 5757, "game_mode": "survival"})
	_stimuli = Stimuli.new()
	add_child_autofree(_stimuli)
	_stimuli.recenter(Vector3.ZERO)
	_holder = Node3D.new()
	add_child_autofree(_holder)
	var actions := PlayerActions.new()
	add_child_autofree(actions)


func after_each() -> void:
	Game.session = _prev


func _floor() -> StaticBody3D:
	var b := StaticBody3D.new()
	var cs := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = Vector3(120, 1, 120)
	cs.shape = shape
	b.add_child(cs)
	b.set_meta(&"terrain", true)
	add_child_autofree(b)
	b.global_position = Vector3(0, -0.5, 0)
	return b


func _player_at(pos: Vector3) -> Player:
	var p: Player = (load(PLAYER_SCENE) as PackedScene).instantiate() as Player
	add_child_autofree(p)
	p.bind_state(Game.session.local_player())
	p.global_position = pos
	p.state.position = pos
	return p


func _fly(a: Arrow, frames: int = 240) -> void:
	for i: int in frames:
		if not is_instance_valid(a) or a.stuck:
			return
		await get_tree().physics_frame


## Launch speed to hit `to` from `from` on a flat shot (a little lift for the drop).
func _aim(from: Vector3, to: Vector3, speed: float, g: float) -> Vector3:
	var d: Vector3 = to - from
	var t: float = d.length() / speed
	return d / t + Vector3.UP * (0.5 * g * t)


func test_an_arrow_lands_where_its_arc_says_and_sticks_facing_its_flight() -> void:
	_floor()
	await get_tree().physics_frame
	var from := Vector3(0, 1.6, 0)
	var vel := Vector3(0, 6.0, -22.0)
	var g: float = 9.8
	var a: Arrow = Arrow.launch(_holder, &"arrow_stone", from, vel, {"gravity": g, "seed": 1})
	# Where the analytic arc meets the ground (y = 0).
	var t_land: float = (vel.y + sqrt(vel.y * vel.y + 2.0 * g * from.y)) / g
	var want: Vector3 = Arrow.position_at(from, vel, g, t_land)
	await _fly(a)
	assert_true(is_instance_valid(a) and a.stuck, "it struck the ground")
	if not is_instance_valid(a):
		return
	assert_almost_eq(a.global_position.z, want.z, absf(want.z) * 0.03 + 0.3, "lands where the arc says (%.2f vs %.2f)" % [a.global_position.z, want.z])
	assert_almost_eq(a.global_position.x, 0.0, 0.05)
	assert_lt(a.global_position.y, 0.05, "the tip is in the ground")
	var fwd: Vector3 = -a.global_transform.basis.z
	assert_lt(fwd.y, -0.3, "nose down, along its flight")
	assert_lt(fwd.z, 0.0)
	assert_eq(a.host != null, true, "in the ground (its terrain body)")
	assert_true(a.is_in_group(&"item_drops"), "saved with the loose items")
	assert_eq(str(a.to_dict()["kind"]), "item")
	assert_true(a.recoverable())
	var heard: bool = false
	for s: Stimuli.SoundEvent in _stimuli.sounds:
		heard = heard or (s.kind == &"impact" and s.pos.distance_to(a.global_position) < 0.5)
	assert_true(heard, "a quiet thunk in the stimulus field")


func test_an_arrow_wounds_a_hollow_and_comes_out_once_its_dead() -> void:
	_floor()
	var e := Enemy.new()
	e.setup(&"test:hollow", Content.enemy(&"hollow"), null, {"tier": "normal"})
	add_child_autofree(e)
	e.global_position = Vector3(0, 0, -10)
	await get_tree().physics_frame
	await get_tree().physics_frame
	var hp: float = e.health
	var from := Vector3(0, 1.2, 0)
	var a: Arrow = Arrow.launch(_holder, &"arrow_bone", from, _aim(from, e.global_position + Vector3.UP * 1.2, 45.0, 9.8),
		{"damage": 30.0, "shooter": String(Game.session.local_player_id), "seed": 2})
	var hit: Array = []
	a.struck.connect(func(_a: Arrow, t: Object) -> void: hit.append(t))
	await _fly(a, 60)
	assert_eq(hit.size(), 1, "struck once")
	assert_true(hit.size() == 1 and hit[0] == e, "the Hollow")
	assert_lt(e.health, hp, "wounded")
	assert_true(is_instance_valid(a) and a.stuck and a.host == e, "in the body")
	if not is_instance_valid(a):
		return
	assert_false(a.recoverable(), "not out of a living Hollow")
	var p: Player = _player_at(Vector3(0, 0, -8))
	assert_eq(a.interact_text(p), "")
	var kill := DamageInfo.make(999.0, &"slash", &"melee", p.state.id)
	kill.hit_pos = e.global_position + Vector3.UP * 1.2
	e.take_damage(kill)
	assert_false(e.is_alive())
	assert_true(a.recoverable(), "a dead body gives it up")
	assert_ne(a.interact_text(p), "")
	a.interact(p)
	assert_eq(p.state.inventory.count_of(&"arrow_bone"), 1, "back in the pack")
	assert_true(a.is_queued_for_deletion())


func test_an_arrow_wounds_a_deer() -> void:
	_floor()
	var manager := WildlifeManager.new()
	add_child_autofree(manager)
	manager.setup_world(null)
	var d := Content.get_def(&"wildlife", &"white_tailed_deer") as WildlifeDef
	var herd: Array = manager.spawn_band(d, {"id": &"w:arch:0", "def": d.id, "pos": Vector2(0, -12), "count": 1, "seed": 7})
	await get_tree().physics_frame
	var deer: Animal = herd[0]
	var hp: float = deer.health
	var from := Vector3(0, 0.9, 0)
	var target: Vector3 = deer.global_position + Vector3.UP * 0.85 * (deer._scale if "_scale" in deer else 1.0)
	var a: Arrow = Arrow.launch(_holder, &"arrow_stone", from, _aim(from, target, 50.0, 9.8),
		{"damage": 20.0, "shooter": String(Game.session.local_player_id), "seed": 3})
	await _fly(a, 60)
	assert_lt(deer.health, hp, "the deer is hit")
	assert_true(deer.state in [Animal.State.FLEE, Animal.State.DEAD], "and bolts (or drops)")
	assert_true(is_instance_valid(a) and a.host == deer, "the arrow rides it")


func test_a_broken_arrow_is_gone_and_a_lost_host_drops_it() -> void:
	var floor_body: StaticBody3D = _floor()
	await get_tree().physics_frame
	var a: Arrow = Arrow.launch(_holder, &"arrow_stone", Vector3(0, 1, 0), Vector3(0, -20, -1), {"break": 1.0, "seed": 4})
	await _fly(a, 30)
	assert_false(is_instance_valid(a) and not a.is_queued_for_deletion(), "snapped on impact")
	var b: Arrow = Arrow.launch(_holder, &"arrow_stone", Vector3(0, 1, 0), Vector3(0, -20, -1), {"break": 0.0, "seed": 5})
	await _fly(b, 30)
	assert_true(is_instance_valid(b) and b.stuck)
	var p: Player = _player_at(Vector3(2, 0, 0))
	assert_eq(b.interact_text(p), "Pick up Stone Arrow")
	# The ground it was in streams out: it falls as a loose item.
	floor_body.get_parent().remove_child(floor_body)
	await get_tree().physics_frame
	await get_tree().physics_frame
	var drops: int = 0
	for n: Node in _holder.get_children():
		if n is ItemDrop and (n as ItemDrop).stack.item_id == &"arrow_stone":
			drops += 1
	assert_eq(drops, 1, "dropped where it was")
	floor_body.free()


func test_a_loose_from_the_bow_spends_an_arrow_at_the_draws_speed() -> void:
	_floor()
	var p: Player = _player_at(Vector3.ZERO)
	var st: PlayerState = p.state
	st.inventory.add_item(&"hunting_bow", 1)
	st.inventory.add_item(&"arrow_stone", 3)
	st.toolbelt[0] = &"hunting_bow"
	p.equipment.select_slot(0)
	await get_tree().physics_frame
	var bow: BowHandler = p.equipment.bow
	assert_not_null(bow)
	var def: ItemDef = Content.item(&"hunting_bow")
	bow.drawing = true
	bow.frac = 0.5
	bow.loose(def)
	assert_eq(st.inventory.count_of(&"arrow_stone"), 2, "one arrow spent")
	var arrow: Arrow = null
	for n: Node in get_tree().root.find_children("*", "Node3D", true, false):
		if n is Arrow:
			arrow = n as Arrow
	assert_not_null(arrow, "an arrow in flight")
	if arrow != null:
		assert_almost_eq(arrow.velocity.length(), BowHandler.shot_speed(def, 0.5), 1.0, "at the half draw's speed")
		var q: int = st.inventory.first(&"hunting_bow").quality
		assert_almost_eq(arrow.damage, BowHandler.shot_damage(def, &"arrow_stone", 0.5, q, st.progression), 0.01)
		arrow.queue_free()
	assert_false(bow.drawing)
	assert_true(bow.need_press, "a fresh press draws the next")
