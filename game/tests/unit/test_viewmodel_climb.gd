extends GutTest
## Climbing arms (ViewModelClimb, ADR-0057): the hand-over-hand phase follows the climb, the grab-on
## and let-go bracket it, the item in hand is stowed and comes back; climbable structures lay out a
## ladder Player can climb.


## A stand-in for Player's climbing getters (ADR-0051).
class FakeClimber:
	extends RefCounted
	var climbing: bool = false
	var speed: float = 0.0
	var ladder: Node3D = null

	func is_climbing() -> bool:
		return climbing

	func climbing_ladder() -> Node3D:
		return ladder

	func climb_speed() -> float:
		return speed


func _climb(fake: FakeClimber) -> ViewModelClimb:
	var c := ViewModelClimb.new()
	c.setup(ViewModelHolds.config())
	c.source = fake
	return c


func test_phase_follows_climb_speed() -> void:
	var fake := FakeClimber.new()
	var c: ViewModelClimb = _climb(fake)
	c.update(0.1)
	assert_eq(c.state, ViewModelClimb.State.OFF, "not climbing: nothing")
	fake.climbing = true
	fake.speed = 1.9
	assert_true(c.update(0.05), "the grab-on starts")
	assert_eq(c.state, ViewModelClimb.State.GRAB)
	for i: int in 20:
		c.update(0.05)
	assert_eq(c.state, ViewModelClimb.State.CLIMB, "on the ladder after the grab-on")
	var m: float = float(c.cycle_m[ViewModelClimb.LADDER])
	var p0: float = c.phase
	c.update(0.1)
	assert_almost_eq(fposmod(c.phase - p0, 1.0), 1.9 * 0.1 / m, 0.0001, "the cycle advances by the metres climbed")
	fake.speed = 0.0
	var p1: float = c.phase
	for i: int in 10:
		c.update(0.05)
	assert_almost_eq(c.phase, p1, 0.0001, "holding still, the hands hold still")
	fake.speed = -1.9
	c.update(0.1)
	assert_almost_eq(fposmod(p1 - c.phase, 1.0), 1.9 * 0.1 / m, 0.0001, "climbing down runs it backwards")
	assert_almost_eq(c.cycle_time(2.0), c.phase * 2.0, 0.0001)
	fake.climbing = false
	assert_true(c.update(0.05), "let go")
	assert_eq(c.state, ViewModelClimb.State.RELEASE)
	for i: int in 20:
		c.update(0.05)
	assert_eq(c.state, ViewModelClimb.State.OFF, "the let-go ends")


func test_rope_takes_the_rope_hold() -> void:
	var fake := FakeClimber.new()
	var root := Node3D.new()
	add_child_autofree(root)
	var lad := PoiPieces.Ladder.new()
	lad.bottom_local = Vector3(0, 0, 0.6)
	lad.set_meta(&"climb_style", "rope")
	root.add_child(lad)
	fake.ladder = lad
	fake.climbing = true
	var c: ViewModelClimb = _climb(fake)
	c.update(0.05)
	assert_eq(c.hold, ViewModelClimb.ROPE)
	assert_eq(c.cycle_action(), &"fp_climb_rope_cycle")
	assert_eq(c.grab_action(), &"fp_climb_rope_grab")


func test_climb_holds_and_actions_exist() -> void:
	var cfg: Dictionary = ViewModelHolds.config()
	for h: String in ["climb", "climb_rope"]:
		assert_true((cfg["holds"] as Dictionary).has(h), "hold %s" % h)
		for u: String in ["_cycle", "_grab", "_release"]:
			assert_true((cfg["uses"] as Dictionary).has(h + u), "use %s%s" % [h, u])
	assert_eq(ViewModelHolds.problems(cfg), PackedStringArray())


func test_arms_level_with_the_ladder() -> void:
	var c := ViewModelClimb.new()
	c.anchor = 1.0
	c.face = Vector3.BACK  # the ladder's rails toward -Z, the climber at +Z
	var looking_down := Basis(Vector3.RIGHT, deg_to_rad(-40.0))
	var b: Basis = c.rig_basis(looking_down)
	# The arms' up stays the world's up, whatever the view does.
	assert_almost_eq(((looking_down * b) * Vector3.UP).distance_to(Vector3.UP), 0.0, 0.001)
	assert_almost_eq(c.rig_basis(Basis()).get_euler().length(), 0.0, 0.001, "looking at the ladder: no turn")


func test_arms_stow_and_restore_the_item() -> void:
	var fake := FakeClimber.new()
	var vm: ViewModel = (load("res://src/player/viewmodel.gd") as GDScript).new() as ViewModel
	add_child_autofree(vm)
	vm.climb.source = fake
	vm.show_item(&"stone_axe")
	var held: Node3D = vm.get(&"_held")
	assert_not_null(held, "an axe in hand")
	vm._process(0.05)
	assert_true(held.visible)
	assert_false(vm.item_stowed())
	fake.climbing = true
	fake.speed = 1.9
	for i: int in 12:
		vm._process(0.05)
	assert_true(vm.item_stowed(), "stowed while climbing")
	assert_false(held.visible, "the axe is put away")
	fake.climbing = false
	for i: int in 3:
		vm._process(0.05)
	assert_false(held.visible, "still away while the hands let go")
	for i: int in 12:
		vm._process(0.05)
	assert_false(vm.item_stowed())
	assert_true(held.visible, "back in hand")


# --- Climbable structures -------------------------------------------------------------------------

func test_climbing_data_validates() -> void:
	assert_eq(ClimbMount.problems(Content), PackedStringArray())
	assert_not_null(Content.structure(&"hunting_stand"))
	assert_not_null(Content.structure(&"climbing_rope"))
	assert_not_null(Content.get_def(&"blueprint", &"hunting_stand"))
	assert_not_null(Content.get_def(&"recipe", &"climbing_rope"))
	assert_eq(str(Content.item(&"climbing_rope").equip.get("structure", "")), "climbing_rope")


func _ladder_in(n: Node) -> PoiPieces.Ladder:
	for c: Node in n.find_children("*", "", true, false):
		if c is PoiPieces.Ladder:
			return c
	return null


func test_hunting_stand_spawns_a_climbable_ladder() -> void:
	var piece := StructurePiece.new()
	piece.setup(&"s_test", Content.structure(&"hunting_stand"), null)
	add_child_autofree(piece)
	piece.global_transform = Transform3D(Basis(Vector3.UP, 0.7), Vector3(5, 2, -3))
	var lad: PoiPieces.Ladder = _ladder_in(piece)
	assert_not_null(lad, "a ladder")
	if lad == null:
		return
	assert_true(lad.is_in_group(&"ladder"))
	var e: Array = lad.ends()
	var top: Vector3 = e[0]
	var foot_cell: Vector3 = e[1]
	assert_almost_eq(lad.height, 3.0, 0.001)
	assert_almost_eq(top.y - lad.global_position.y, 3.0, 0.01, "the landing is the deck")
	assert_almost_eq(foot_cell.y, lad.global_position.y, 0.01, "the foot cell is on the ground")
	# The landing and the foot cell are both on the climber's side, like a POI ladder's hatch.
	assert_gt((top - lad.global_position).dot(lad.face()), 0.8)
	assert_gt((foot_cell - lad.global_position).dot(lad.face()), 0.3)
	assert_almost_eq(lad.face().dot(piece.global_basis * Vector3.FORWARD), 1.0, 0.01, "faces into the frame")


func test_rope_finds_the_ledge_and_hangs_a_ladder() -> void:
	var s: Dictionary = ClimbMount.spec_for(&"climbing_rope")
	# A ledge 0.55 m ahead of the anchor, 4 m above the ground.
	var probe := func(from: Vector3, _to: Vector3) -> Variant:
		return Vector3(from.x, 10.0 if from.z > -0.55 else 6.0, from.z)
	var drop: Dictionary = ClimbMount.find_drop(Vector3(0, 10, 0), Vector3.FORWARD, s, probe)
	assert_false(drop.is_empty(), "the edge is found")
	assert_almost_eq(float(drop["ground"]), 6.0, 0.001)
	assert_between(float(drop["d"]), 0.55, 0.8)
	var flat := func(from: Vector3, _to: Vector3) -> Variant:
		return Vector3(from.x, 10.0, from.z)
	assert_true(ClimbMount.find_drop(Vector3(0, 10, 0), Vector3.FORWARD, s, flat).is_empty(), "no ledge, no rope")
	var root := Node3D.new()
	add_child_autofree(root)
	root.global_position = Vector3(0, 10, 0)
	var lad: PoiPieces.Ladder = ClimbMount.hang_rope(root, s, drop)
	assert_true(lad.is_in_group(&"ladder"))
	assert_eq(ViewModelClimb.hold_for(lad), ViewModelClimb.ROPE)
	assert_almost_eq(lad.height, 4.0, 0.001)
	assert_almost_eq(lad.global_position.y, 6.0, 0.001, "the foot on the ground")
	assert_almost_eq(lad.face().dot(Vector3.FORWARD), 1.0, 0.001, "the climber hangs out over the drop")
	var top: Vector3 = lad.ends()[0]
	assert_almost_eq(top.y, 10.0, 0.001, "the landing on top")
	assert_lt(top.z, 0.0 + 0.5, "behind the edge")
	assert_gt(top.z, -0.1)


func test_hands_stay_on_the_rails_at_any_fov() -> void:
	# TD-296: the poses were baked at the default world FOV; elsewhere the rig scales across the screen.
	assert_almost_eq(ViewModelClimb.fov_scale(75.0, 75.0), 1.0, 0.0001)
	assert_lt(ViewModelClimb.fov_scale(100.0, 75.0), 1.0, "wider: the rails crowd to the middle")
	assert_gt(ViewModelClimb.fov_scale(60.0, 75.0), 1.0, "narrower: they spread out")
	# A rail at screen x = X/tan(fov/2) stays under the hand: scaled hand / bake projection = rail.
	var rail_x: float = 0.2
	for fov: float in [60.0, 90.0, 110.0]:
		var rail_screen: float = rail_x / tan(deg_to_rad(fov) * 0.5)
		var hand_screen: float = rail_x * ViewModelClimb.fov_scale(fov, 75.0) / tan(deg_to_rad(75.0) * 0.5)
		assert_almost_eq(hand_screen, rail_screen, 0.0001)
	var c := ViewModelClimb.new()
	c.setup({"climb": {"bake_fov": 75.0}})
	c.anchor = 0.0
	assert_eq(c.rig_scale(100.0), 1.0, "off the rails: no scale")
	c.anchor = 1.0
	assert_almost_eq(c.rig_scale(100.0), ViewModelClimb.fov_scale(100.0, 75.0), 0.0001)
