extends GutTest
## Aiming a gun (ADR-0057): only ranged weapons aim; holding Aim raises the gun over its aim time
## and letting go lowers it; when up, the view narrows by the gun's zoom (the rifle's 4x scope far
## more than the revolver's iron sights), shots spread less, the arms sway less and the walk slows;
## the scope picture only once a scoped gun is all the way up; changing what is in hand drops the
## aim; the sight offset puts the sight on the line of sight.

var _aim: PlayerAim


func before_each() -> void:
	_aim = PlayerAim.new()
	add_child_autofree(_aim)
	# No player: the state machine is driven directly.
	_aim.set_physics_process(false)


func test_only_guns_aim() -> void:
	assert_true(PlayerAim.can_aim(Content.item(&"hunting_rifle")))
	assert_true(PlayerAim.can_aim(Content.item(&"revolver")))
	assert_false(PlayerAim.can_aim(Content.item(&"stone_axe")), "an axe has no sights")
	assert_false(PlayerAim.can_aim(null))
	_aim.update(1.0, true, &"stone_axe")
	assert_false(_aim.is_aiming(), "holding Aim with an axe does nothing")
	assert_eq(_aim.zoom(), 1.0)


func test_raise_and_lower_over_the_aim_time() -> void:
	var t: float = float(PlayerAim.settings(Content.item(&"hunting_rifle"))["time"])
	_aim.update(0.0, false, &"hunting_rifle")
	assert_false(_aim.is_aiming())
	_aim.update(t * 0.5, true, &"hunting_rifle")
	assert_true(_aim.is_aiming(), "on its way up")
	assert_false(_aim.fully_aimed())
	assert_almost_eq(_aim.progress, 0.5, 0.01)
	_aim.update(t * 0.6, true, &"hunting_rifle")
	assert_true(_aim.fully_aimed(), "up after the aim time")
	_aim.update(t * 0.5, false, &"hunting_rifle")
	assert_false(_aim.fully_aimed(), "let go: coming down")
	_aim.update(t, false, &"hunting_rifle")
	assert_false(_aim.is_aiming(), "down again")
	assert_almost_eq(_aim.zoom(), 1.0, 1e-6)


func test_zoom_spread_sway_and_walk_when_up() -> void:
	var s: Dictionary = PlayerAim.settings(Content.item(&"hunting_rifle"))
	assert_almost_eq(_aim.fov(75.0), 75.0, 1e-4, "at the hip the view is as it was")
	assert_almost_eq(_aim.spread_mult(), 1.0, 1e-6)
	_aim.update(5.0, true, &"hunting_rifle")
	var want: float = rad_to_deg(2.0 * atan(tan(deg_to_rad(37.5)) / float(s["zoom"])))
	assert_almost_eq(_aim.fov(75.0), want, 1e-3, "the scope narrows the view by its zoom")
	assert_lt(_aim.fov(75.0), 25.0, "4x: a narrow view")
	assert_almost_eq(_aim.spread_mult(), float(s["spread"]), 1e-6, "tighter shots")
	assert_almost_eq(_aim.sway_mult(), float(s["sway"]), 1e-6, "steadier arms")
	assert_almost_eq(_aim.move_mult(), float(s["move"]), 1e-6, "a slower walk")
	assert_almost_eq(_aim.look_mult(), 1.0 / float(s["zoom"]), 1e-6, "turning scaled to the zoom")
	assert_true(_aim.scoped(), "the scope picture is up")


func test_iron_sights_zoom_less_than_the_scope() -> void:
	_aim.update(5.0, true, &"revolver")
	var iron: float = _aim.fov(75.0)
	assert_false(_aim.scoped(), "the revolver has no scope")
	assert_lt(iron, 75.0, "iron sights narrow the view a little")
	_aim.update(0.0, true, &"hunting_rifle")
	assert_eq(_aim.progress, 0.0, "a new gun in hand starts at the hip")
	_aim.update(5.0, true, &"hunting_rifle")
	assert_lt(_aim.fov(75.0), iron, "the scope far more")


func test_scope_picture_only_near_the_top() -> void:
	var t: float = float(PlayerAim.settings(Content.item(&"hunting_rifle"))["time"])
	_aim.update(t * 0.5, true, &"hunting_rifle")
	assert_false(_aim.scoped(), "half way up: still looking past the scope")
	_aim.update(t, true, &"hunting_rifle")
	assert_true(_aim.scoped())


func test_sight_offset_puts_the_sight_on_the_line_of_sight() -> void:
	var sight := Transform3D(Basis.from_euler(Vector3(0.1, -0.2, 0.05)), Vector3(0.12, -0.1, -0.2))
	var off: Transform3D = PlayerAim.sight_offset(sight, 0.02, 0.3)
	var aimed: Transform3D = off * sight
	var point: Vector3 = aimed * Vector3(0.0, 0.02, 0.0)
	assert_almost_eq(point.x, 0.0, 1e-5)
	assert_almost_eq(point.y, 0.0, 1e-5)
	assert_almost_eq(point.z, -0.3, 1e-5, "the sight comes up 0.3 m before the eye")
	var fwd: Vector3 = -aimed.basis.z.normalized()
	assert_almost_eq(fwd.dot(Vector3.FORWARD), 1.0, 1e-5, "looking straight down it")
