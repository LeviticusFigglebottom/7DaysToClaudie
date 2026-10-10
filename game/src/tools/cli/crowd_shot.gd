extends SceneTree
## A mixed group of Hollowed seen from the player's distances (TD-192 review: does the crowd read as
## different people at 10, 20 and 30 m?). Bodies stand in a loose group on open ground at dusk, each
## with its own skin tone (instance_variation from its index, as EnemyVisual sets it from the entity
## id) and a different moment of its idle loop, turned roughly toward the camera.
##
##   xvfb-run godot --path game --rendering-driver vulkan -s res://src/tools/cli/crowd_shot.gd -- \
##       --out DIR [--size 1280x720] [--time 19.4] [--dists 10,20,30] [--fov 60] characters/hollow_a ...
## Writes DIR/crowd_<dist>m.png. A staged scene (sky, sun, fog, flat ground), not the streamed
## world: lighting is close to the game's dusk, not the same.

var _out_dir: String = "res://build"
var _size := Vector2i(1280, 720)
var _hour: float = 19.4
var _dists: PackedFloat32Array = [10.0, 20.0, 30.0]
var _fov: float = 60.0
var _models: PackedStringArray = []


func _initialize() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var i: int = 0
	while i < args.size():
		match args[i]:
			"--out":
				i += 1
				_out_dir = args[i]
			"--size":
				i += 1
				var p: PackedStringArray = args[i].split("x")
				_size = Vector2i(int(p[0]), int(p[1]))
			"--time":
				i += 1
				_hour = float(args[i])
			"--dists":
				i += 1
				_dists = PackedFloat32Array()
				for d: String in args[i].split(","):
					_dists.append(float(d))
			"--fov":
				i += 1
				_fov = float(args[i])
			_:
				_models.append(args[i])
		i += 1
	DirAccess.make_dir_recursive_absolute(_out_dir)
	root.size = _size
	var world := Node3D.new()
	root.add_child(world)
	_environment(world)
	await _place(world)
	var cam := Camera3D.new()
	cam.fov = _fov
	world.add_child(cam)
	cam.make_current()
	for d: float in _dists:
		# Standing eye height, looking at the group's chests.
		cam.global_position = Vector3(0.0, 1.65, d)
		cam.look_at(Vector3(0.0, 1.2, 0.0), Vector3.UP)
		for f: int in 8:
			await process_frame
		RenderingServer.force_draw()
		await process_frame
		var out: String = _out_dir.path_join("crowd_%dm.png" % int(d))
		root.get_texture().get_image().save_png(out)
		print("CROWD ", out)
	quit(0)


func _environment(world: Node3D) -> void:
	var t: float = clampf((_hour - 17.5) / 3.0, 0.0, 1.0)  # 0 late afternoon .. 1 dark
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	var sky := Sky.new()
	var sm := ProceduralSkyMaterial.new()
	sm.sky_top_color = Color(0.30, 0.38, 0.52).lerp(Color(0.10, 0.12, 0.22), t)
	sm.sky_horizon_color = Color(0.75, 0.62, 0.50).lerp(Color(0.45, 0.30, 0.25), t)
	sm.ground_horizon_color = Color(0.35, 0.32, 0.28).lerp(Color(0.15, 0.13, 0.12), t)
	sm.ground_bottom_color = Color(0.12, 0.11, 0.10)
	sky.sky_material = sm
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_energy = lerpf(1.0, 0.45, t)
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.ssao_enabled = true
	env.fog_enabled = true
	env.fog_density = 0.008
	env.fog_light_color = Color(0.55, 0.48, 0.45).lerp(Color(0.25, 0.22, 0.25), t)
	var we := WorldEnvironment.new()
	we.environment = env
	world.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.shadow_enabled = true
	sun.light_energy = lerpf(1.4, 0.35, t)
	sun.light_color = Color(1.0, 0.72, 0.5)
	# Low in the west, raking across the group from the camera's left.
	sun.rotation_degrees = Vector3(-lerpf(14.0, 3.0, t), -70.0, 0.0)
	world.add_child(sun)
	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(300, 300)
	ground.mesh = plane
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color(0.16, 0.18, 0.11)
	gm.roughness = 0.95
	ground.material_override = gm
	world.add_child(ground)


## A loose group, 2-3 deep, about 6 m across.
func _place(world: Node3D) -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 4242
	var n: int = _models.size()
	for k: int in n:
		var path: String = "res://assets/generated/models/%s.glb" % _models[k]
		if not ResourceLoader.exists(path):
			push_error("crowd_shot: missing %s" % path)
			continue
		var inst: Node3D = (load(path) as PackedScene).instantiate() as Node3D
		world.add_child(inst)
		var row: int = k % 3
		inst.position = Vector3((float(k) - float(n - 1) * 0.5) * 0.85 + rng.randf_range(-0.3, 0.3), 0.0,
			-float(row) * 1.6 + rng.randf_range(-0.4, 0.4))
		inst.rotation.y = rng.randf_range(-0.7, 0.7)  # bodies face +Z: toward the camera
		var v: float = fmod(float(k) * 0.618034 + 0.13, 1.0)
		for g: Node in inst.find_children("*", "GeometryInstance3D", true, false):
			(g as GeometryInstance3D).set_instance_shader_parameter(&"instance_variation", v)
		var ap := inst.find_child("AnimationPlayer", true, false) as AnimationPlayer
		if ap != null:
			var idle: StringName = &"idle" if ap.has_animation(&"idle") else (ap.get_animation_list()[0] if not ap.get_animation_list().is_empty() else &"")
			if idle != &"":
				ap.play(idle)
				ap.seek(rng.randf_range(0.0, ap.current_animation_length), true)
				ap.pause()
		# Stumps stay hidden (EnemyVisual hides them on spawn).
		for m: Node in inst.find_children("stump_*", "MeshInstance3D", true, false):
			(m as MeshInstance3D).visible = false
	await process_frame
