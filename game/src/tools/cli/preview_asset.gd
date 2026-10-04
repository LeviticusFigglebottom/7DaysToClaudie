extends SceneTree
## Renders generated assets in-engine (real materials, sun + sky + fog) to PNG for visual QA.
##
##   make preview MODELS="rocks/boulder_a rocks/boulder_b" [PREVIEW_ARGS="--time 17.5 --size 960x540"]
##   (= xvfb-run godot --path game --rendering-driver vulkan -s res://src/tools/cli/preview_asset.gd -- \
##        --out build/previews rocks/boulder_a ...)
## Options: --out DIR, --size WxH, --time HOUR (sun position), --dist MULT, --angle DEG, --grid (all
## models side by side in one image named grid.png), --ground none|grass|dirt.

var _out_dir: String = "res://../build/previews"
var _size := Vector2i(960, 540)
var _hour: float = 15.0
var _dist_mult: float = 1.0
var _angle: float = 35.0
var _grid: bool = false
var _models: PackedStringArray = []


func _initialize() -> void:
	_parse_args()
	root.size = _size
	var world := Node3D.new()
	root.add_child(world)
	_setup_environment(world)
	if _grid:
		await _render_grid(world)
	else:
		for m: String in _models:
			await _render_one(world, m)
	quit(0)


func _parse_args() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	var i: int = 0
	while i < a.size():
		match a[i]:
			"--out":
				i += 1
				_out_dir = a[i]
			"--size":
				i += 1
				var p: PackedStringArray = a[i].split("x")
				_size = Vector2i(int(p[0]), int(p[1]))
			"--time":
				i += 1
				_hour = float(a[i])
			"--dist":
				i += 1
				_dist_mult = float(a[i])
			"--angle":
				i += 1
				_angle = float(a[i])
			"--grid":
				_grid = true
			_:
				_models.append(a[i])
		i += 1
	DirAccess.make_dir_recursive_absolute(_out_dir)


func _setup_environment(world: Node3D) -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	var sky := Sky.new()
	var sky_mat := ProceduralSkyMaterial.new()
	sky_mat.sky_top_color = Color(0.32, 0.42, 0.55)
	sky_mat.sky_horizon_color = Color(0.68, 0.70, 0.72)
	sky_mat.ground_horizon_color = Color(0.4, 0.4, 0.38)
	sky_mat.ground_bottom_color = Color(0.15, 0.14, 0.12)
	sky.sky_material = sky_mat
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.ssao_enabled = true
	env.glow_enabled = true
	env.fog_enabled = true
	env.fog_density = 0.002
	env.fog_light_color = Color(0.6, 0.64, 0.68)
	var we := WorldEnvironment.new()
	we.environment = env
	world.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.shadow_enabled = true
	sun.light_energy = 1.6
	sun.light_color = Color(1.0, 0.95, 0.86)
	var elev: float = clampf(sin((_hour - 6.0) / 13.0 * PI) * 55.0, 4.0, 70.0)
	sun.rotation_degrees = Vector3(-elev, 35.0 + (_hour - 12.0) * 12.0, 0.0)
	world.add_child(sun)
	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(200, 200)
	ground.mesh = plane
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color(0.22, 0.21, 0.18)
	gm.roughness = 0.95
	ground.material_override = gm
	world.add_child(ground)


func _load_model(model_id: String) -> Node3D:
	var path: String = "res://assets/generated/models/%s.glb" % model_id
	if not ResourceLoader.exists(path):
		push_error("preview: missing %s" % path)
		return null
	var ps: PackedScene = load(path)
	return ps.instantiate() as Node3D


func _aabb(n: Node) -> AABB:
	var box := AABB()
	var first: bool = true
	for c: Node in n.find_children("*", "VisualInstance3D", true, false):
		var vi := c as VisualInstance3D
		var b: AABB = vi.global_transform * vi.get_aabb()
		box = b if first else box.merge(b)
		first = false
	return box


func _camera_for(world: Node3D, box: AABB) -> Camera3D:
	var cam := Camera3D.new()
	cam.fov = 40.0
	world.add_child(cam)
	var center: Vector3 = box.get_center()
	var radius: float = maxf(box.size.length() * 0.5, 0.15)
	var dist: float = radius / tan(deg_to_rad(cam.fov * 0.5)) * 1.1 * _dist_mult
	var a: float = deg_to_rad(_angle)
	var dir := Vector3(sin(a), 0.42, cos(a)).normalized()
	cam.position = center + dir * dist
	cam.look_at(center)
	cam.make_current()
	return cam


func _render_one(world: Node3D, model_id: String) -> void:
	var inst: Node3D = _load_model(model_id)
	if inst == null:
		return
	world.add_child(inst)
	await process_frame
	var cam: Camera3D = _camera_for(world, _aabb(inst))
	await _settle()
	var img: Image = root.get_texture().get_image()
	var out: String = _out_dir.path_join(model_id.replace("/", "__") + ".png")
	img.save_png(out)
	print("PREVIEW ", out)
	inst.queue_free()
	cam.queue_free()
	await process_frame


func _render_grid(world: Node3D) -> void:
	var x: float = 0.0
	var holder := Node3D.new()
	world.add_child(holder)
	for m: String in _models:
		var inst: Node3D = _load_model(m)
		if inst == null:
			continue
		holder.add_child(inst)
		await process_frame
		var b: AABB = _aabb(inst)
		inst.position.x = x - b.position.x
		x += b.size.x + 0.4
	await process_frame
	_camera_for(world, _aabb(holder))
	await _settle()
	var out: String = _out_dir.path_join("grid.png")
	root.get_texture().get_image().save_png(out)
	print("PREVIEW ", out)


func _settle() -> void:
	for i: int in 8:
		await process_frame
	RenderingServer.force_draw()
	await process_frame
