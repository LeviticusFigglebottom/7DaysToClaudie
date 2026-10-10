extends Node
## impostor_shot.gd's work: the species' impostor quads on flat ground under a day sky, each
## variant row shown once (custom data), a summer and a winter frame.

var _out: String = "res://build"


func _ready() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var i: int = args.find("--out")
	if i >= 0 and i + 1 < args.size():
		_out = args[i + 1]
	DirAccess.make_dir_recursive_absolute(_out)
	_run.call_deferred()


func _run() -> void:
	get_window().size = Vector2i(1600, 900)
	var world := Node3D.new()
	add_child(world)
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	var sky := Sky.new()
	sky.sky_material = ProceduralSkyMaterial.new()
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	var we := WorldEnvironment.new()
	we.environment = env
	world.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-35, -40, 0)
	world.add_child(sun)
	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(800, 800)
	ground.mesh = plane
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color(0.2, 0.22, 0.14)
	ground.material_override = gm
	world.add_child(ground)
	var vm := VegetationManager.new()
	var trees: Array[SpeciesDef] = []
	for d: ContentDef in Content.all(&"species"):
		var sp := d as SpeciesDef
		if sp.veg_kind == "tree":
			trees.append(sp)
	# A row of species across the view, each species' variants one behind another along z.
	var x0: float = -float(trees.size() - 1) * 0.5 * 26.0
	for si: int in trees.size():
		var sp: SpeciesDef = trees[si]
		var dim: Vector2 = ImpostorLibrary.size_for(sp)
		var rows: int = ImpostorLibrary.variants_for(sp)
		var buf := PackedFloat32Array()
		for v: int in rows:
			var s: float = 0.9
			var b := Basis().scaled(Vector3(dim.x, dim.y, dim.x) * s)
			var p := Vector3(x0 + float(si) * 26.0 + float(v) * 4.0, 0.0, -70.0 - float(v) * 22.0)
			buf.append_array([b.x.x, b.y.x, b.z.x, p.x, b.x.y, b.y.y, b.z.y, p.y, b.x.z, b.y.z, b.z.z, p.z, float(v), 0.0, 0.0, 0.0])
		var mat: ShaderMaterial = vm._impostor_mat(sp)
		mat.set_shader_parameter("discard_rect", Vector4(0, 0, 0, 0))
		world.add_child(vm._impostor_mmi("I_%s" % sp.id, mat, [rows, buf]))
	vm.free()
	var cam := Camera3D.new()
	cam.fov = 50.0
	world.add_child(cam)
	cam.global_position = Vector3(0, 6, 40)
	cam.look_at(Vector3(0, 9, -90), Vector3.UP)
	cam.make_current()
	for season: Array in [["summer", Vector4(0, 1, 0, 0)], ["winter", Vector4(0, 0, 0, 1)]]:
		RenderingServer.global_shader_parameter_set(&"hm_season", season[1])
		RenderingServer.global_shader_parameter_set(&"hm_snow", 0.0)
		for f: int in 6:
			await get_tree().process_frame
		RenderingServer.force_draw()
		await get_tree().process_frame
		var path: String = _out.path_join("impostors_%s.png" % season[0])
		get_viewport().get_texture().get_image().save_png(path)
		print("IMPOSTOR_SHOT ", path)
	get_tree().quit(0)
