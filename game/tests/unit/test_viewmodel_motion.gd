extends GutTest
## First person (ADR-0029): raising the tether runs lowered -> raising -> raised -> lowering on the
## data's timings and keeps the hands from swinging until it is down; the procedural motion is
## deterministic, lowers the arms while sprinting, bobs only when moving and springs its kicks
## back to rest; the viewmodel material copies gain the field-of-view and depth lines.


func test_tether_raise_state() -> void:
	var t := TetherRaise.new()
	t.setup({"tether": {"raise_time": 0.4, "lower_time": 0.2}})
	assert_eq(t.state, TetherRaise.State.LOWERED)
	assert_false(t.blocks_attack(), "a lowered wrist leaves the hands free")
	assert_true(t.toggle(), "T raises the wrist")
	assert_eq(t.state, TetherRaise.State.RAISING)
	assert_true(t.blocks_attack(), "no swinging while the wrist comes up")
	assert_false(t.set_raised(true), "asking again changes nothing")
	for i: int in 3:
		t.update(0.1)
	assert_false(t.is_reading(), "0.3 s of a 0.4 s raise: not yet readable")
	t.update(0.15)
	assert_true(t.is_reading(), "raised after raise_time")
	assert_almost_eq(t.progress(), 1.0, 1e-6)
	assert_true(t.toggle(), "T again lowers it")
	assert_eq(t.state, TetherRaise.State.LOWERING)
	t.update(0.25)
	assert_eq(t.state, TetherRaise.State.LOWERED)
	assert_false(t.blocks_attack())
	# Raising part way and lowering again reverses smoothly from where it was.
	t.set_raised(true)
	t.update(0.2)
	var mid: float = t.t
	t.set_raised(false)
	t.update(0.05)
	assert_lt(t.t, mid, "lowering from half way")
	assert_gt(t.t, 0.0)


func _run(m: ViewModelMotion, seconds: float, sprint: bool, speed: float) -> void:
	var steps: int = int(seconds / 0.016)
	for i: int in steps:
		var phase: float = fmod(float(i) * 0.016 * speed / 0.95, 1.0)
		m.update(0.016, Vector2.ZERO, Vector3(0, 0, -speed), speed, sprint, false, true, phase, i / 60)


func test_motion_is_deterministic_and_sprint_lowers_the_arms() -> void:
	var cfg: Dictionary = ViewModelHolds.config()
	var a := ViewModelMotion.new()
	a.setup(cfg)
	var b := ViewModelMotion.new()
	b.setup(cfg)
	_run(a, 1.0, true, 6.0)
	_run(b, 1.0, true, 6.0)
	assert_eq(a.rig_transform(), b.rig_transform(), "same inputs, same motion")
	var walk := ViewModelMotion.new()
	walk.setup(cfg)
	_run(walk, 1.0, false, 3.0)
	assert_lt(a.rig_rotation_deg().x, walk.rig_rotation_deg().x - 10.0, "sprinting pitches the arms down")
	assert_lt(a.rig_position().y, walk.rig_position().y, "and drops them")


func test_bob_needs_movement_and_kicks_spring_back() -> void:
	var cfg: Dictionary = ViewModelHolds.config()
	var still := ViewModelMotion.new()
	still.setup(cfg)
	var lows: Array[float] = []
	for i: int in 200:
		still.update(0.016, Vector2.ZERO, Vector3.ZERO, 0.0, false, false, true, fmod(i * 0.05, 1.0), i / 20)
		lows.append(still.rig_position().y)
	var spread: float = lows.max() - lows.min()
	assert_lt(spread, 0.01, "standing still only breathes (no footstep bob)")
	var m := ViewModelMotion.new()
	m.setup(cfg)
	m.impact(Vector3(-2.0, 0.5, 1.0), 0.02)
	m.update(0.016, Vector2.ZERO, Vector3.ZERO, 0.0, false, false, true, 0.0, 0)
	var peak: float = 0.0
	for i: int in 20:
		m.update(0.016, Vector2.ZERO, Vector3.ZERO, 0.0, false, false, true, 0.0, 0)
		peak = maxf(peak, m.camera_kick().length())
	assert_gt(peak, deg_to_rad(0.5), "a hit kicks the camera")
	for i: int in 120:
		m.update(0.016, Vector2.ZERO, Vector3.ZERO, 0.0, false, false, true, 0.0, 0)
	assert_lt(m.camera_kick().length(), deg_to_rad(0.05), "and it settles back")
	m.start_equip()
	m.update(0.016, Vector2.ZERO, Vector3.ZERO, 0.0, false, false, true, 0.0, 0)
	assert_lt(m.rig_position().y, -0.05, "a freshly equipped item starts low")


func test_viewmodel_shader_lines() -> void:
	var src: String = "shader_type spatial;\nrender_mode cull_back;\nuniform float a = 1.0;\n\nvoid vertex() {\n\tVERTEX.y += a;\n\tif (a > 0.0) {\n\t\tVERTEX.x += 1.0;\n\t}\n}\n\nvoid fragment() {\n\tALBEDO = vec3(a);\n}\n"
	var out: String = FpMaterials.inject(src)
	assert_string_contains(out, "Z_CLIP_SCALE = fp_z_clip_scale;")
	assert_string_contains(out, "uniform float fp_fov")
	assert_lt(out.find("Z_CLIP_SCALE"), out.find("void fragment()"), "added inside vertex(), before fragment()")
	assert_gt(out.find("Z_CLIP_SCALE"), out.find("VERTEX.x += 1.0;"), "after the vertex body's own code")
	assert_eq(FpMaterials.inject(out), "", "never injected twice")
	assert_eq(FpMaterials.inject("shader_type canvas_item;\nvoid fragment() {}\n"), "", "only spatial shaders")
	var no_vertex: String = FpMaterials.inject("shader_type spatial;\n\nvoid fragment() {\n\tALBEDO = vec3(1.0);\n}\n")
	assert_string_contains(no_vertex, "void vertex()", "a vertex() is added when there is none")
	var std: Shader = load("res://assets/shaders/std_surface.gdshader")
	assert_string_contains(FpMaterials.inject(std.code), "PROJECTION_MATRIX[1][1] = fp_f;", "std_surface takes the lines")
	var bm := StandardMaterial3D.new()
	var fm: Material = FpMaterials.fp_material(bm)
	assert_true(fm is BaseMaterial3D and (fm as BaseMaterial3D).use_fov_override and (fm as BaseMaterial3D).use_z_clip_scale)
	assert_eq(FpMaterials.fp_material(bm), fm, "converted once, then cached")
	assert_eq(FpMaterials.fp_material(fm), fm, "a first-person material is left as it is")
	var before: float = FpMaterials.fov
	FpMaterials.set_fov(47.0)
	assert_almost_eq((fm as BaseMaterial3D).fov_override, 47.0, 1e-4, "set_fov retunes live materials")
	FpMaterials.set_fov(before)
	# A material made at runtime (a torch flame per lighting) goes with its node: the cache
	# doesn't keep its copy alive.
	assert_null(_runtime_copy().get_ref(), "the copy is freed with its source")


## Converts a material made here; its locals (and the VM's temporaries) go when this returns.
func _runtime_copy() -> WeakRef:
	var tmp := StandardMaterial3D.new()
	var w: WeakRef = weakref(FpMaterials.fp_material(tmp))
	assert_not_null(w.get_ref(), "converted")
	return w


func test_a_fall_or_teleport_never_flings_the_arms() -> void:
	# Build #67: a player stuck in a -74 m/s free fall, looking up, had the arms fly off into the
	# sky. Whatever the velocity, the inertia offset stays what walking pace gives.
	var cfg: Dictionary = ViewModelHolds.config()
	var walk := ViewModelMotion.new()
	walk.setup(cfg)
	var fall := ViewModelMotion.new()
	fall.setup(cfg)
	for i: int in 120:
		walk.update(1.0 / 60.0, Vector2.ZERO, Vector3(0, 0, -6.0), 0.0, false, false, false, 0.0, 0)
		fall.update(1.0 / 60.0, Vector2.ZERO, Vector3(0, 0, -74.0), 0.0, false, false, false, 0.0, 0)
	assert_almost_eq(fall.rig_position().distance_to(walk.rig_position()), 0.0, 0.001, "a fall moves the arms no further than a run")
	assert_lt(fall.rig_position().length(), 0.08, "the arms stay in view")
