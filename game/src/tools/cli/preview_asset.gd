extends SceneTree
## Renders generated assets in-engine (real materials, sun + sky + fog) to PNG for visual QA.
##
##   make preview MODELS="rocks/boulder_a rocks/boulder_b" [PREVIEW_ARGS="--time 17.5 --size 960x540"]
##   (= xvfb-run godot --path game --rendering-driver vulkan -s res://src/tools/cli/preview_asset.gd -- \
##        --out build/previews rocks/boulder_a ...)
## Options: --out DIR, --size WxH, --time HOUR (sun position), --dist MULT, --angle DEG, --grid (all
## models side by side in one image named grid.png), --ground none|grass|dirt, --focus X,Y,Z,R (look
## at that model-space point and frame a radius R instead of the whole model: a trunk base, a face).
## Characters (ADR-0028): --anim NAME[:SECONDS] holds that pose of the model's animation,
## --instance NAME=VALUE (repeatable) sets an instance shader parameter on every mesh (bloom_glow=1
## for a Bloomed Hollowed, hollow_burst=1 for burst pustules), --tag TAG names the image
## <model>_<TAG>.png so views of one model don't overwrite each other, --focus-bone NAME,R frames a
## radius R round a bone of the posed skeleton (a face close-up whatever the body's height), --elev
## E the camera's rise per unit of distance (default 0.42; 0 looks a hanging face in the eye).
## --global NAME=VALUE (repeatable) sets a float global shader uniform (hm_bloom_night=1 shows the
## Bloom's night glow on fungus and nest props).

var _out_dir: String = "res://../build/previews"
var _size := Vector2i(960, 540)
var _hour: float = 15.0
var _dist_mult: float = 1.0
var _angle: float = 35.0
var _grid: bool = false
var _ground: String = "dirt"
var _focus := Vector4.ZERO
var _models: PackedStringArray = []
var _anim: String = ""
var _instance_params: Dictionary = {}
var _tag: String = ""
var _focus_bone: String = ""
var _focus_bone_r: float = 0.25
var _elev: float = 0.42


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
			"--ground":
				i += 1
				_ground = a[i]
			"--focus":
				i += 1
				var f: PackedStringArray = a[i].split(",")
				_focus = Vector4(float(f[0]), float(f[1]), float(f[2]), float(f[3]))
			"--anim":
				i += 1
				_anim = a[i]
			"--instance":
				i += 1
				var kv: PackedStringArray = a[i].split("=")
				_instance_params[StringName(kv[0])] = float(kv[1])
			"--global":
				i += 1
				var gv: PackedStringArray = a[i].split("=")
				RenderingServer.global_shader_parameter_set(StringName(gv[0]), float(gv[1]))
			"--tag":
				i += 1
				_tag = a[i]
			"--elev":
				i += 1
				_elev = float(a[i])
			"--focus-bone":
				i += 1
				var fb: PackedStringArray = a[i].split(",")
				_focus_bone = fb[0]
				_focus_bone_r = float(fb[1]) if fb.size() > 1 else 0.25
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
	if _ground == "none":
		return
	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(200, 200)
	ground.mesh = plane
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color(0.17, 0.21, 0.11) if _ground == "grass" else Color(0.22, 0.21, 0.18)
	gm.roughness = 0.95
	ground.material_override = gm
	world.add_child(ground)


func _load_model(model_id: String) -> Node3D:
	var path: String = "res://assets/generated/models/%s.glb" % model_id
	if not ResourceLoader.exists(path):
		push_error("preview: missing %s" % path)
		return null
	var ps: PackedScene = load(path)
	var inst: Node3D = ps.instantiate() as Node3D
	for g: Node in inst.find_children("*", "GeometryInstance3D", true, false):
		for k: StringName in _instance_params:
			(g as GeometryInstance3D).set_instance_shader_parameter(k, _instance_params[k])
	return inst


## --focus-bone: the bone's posed position becomes the --focus point.
func _focus_on_bone(inst: Node3D) -> void:
	if _focus_bone == "":
		return
	var sk := inst.find_child("Skeleton3D", true, false) as Skeleton3D
	var bi: int = sk.find_bone(_focus_bone) if sk != null else -1
	if bi < 0:
		push_error("preview: no bone %s" % _focus_bone)
		return
	# a little along the bone (glTF bones run along +Y): the middle of a head, not the top of the neck
	var at: Vector3 = sk.global_transform * (sk.get_bone_global_pose(bi) * Vector3(0.0, 0.09, 0.0))
	_focus = Vector4(at.x, at.y, at.z, _focus_bone_r)


## Holds the --anim pose (needs the model in the tree).
func _pose(inst: Node3D) -> void:
	if _anim == "":
		return
	var ap := inst.find_child("AnimationPlayer", true, false) as AnimationPlayer
	var parts: PackedStringArray = _anim.split(":")
	if ap == null or not ap.has_animation(StringName(parts[0])):
		push_error("preview: no animation %s" % parts[0])
		return
	ap.play(StringName(parts[0]))
	ap.seek(float(parts[1]) if parts.size() > 1 else 0.5, true)
	ap.pause()


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
	if _focus.w > 0.0:
		center = Vector3(_focus.x, _focus.y, _focus.z)
		radius = _focus.w
	var dist: float = radius / tan(deg_to_rad(cam.fov * 0.5)) * 1.1 * _dist_mult
	var a: float = deg_to_rad(_angle)
	var dir := Vector3(sin(a), _elev, cos(a)).normalized()
	cam.position = center + dir * dist
	cam.look_at(center)
	cam.make_current()
	return cam


func _render_one(world: Node3D, model_id: String) -> void:
	var inst: Node3D = _load_model(model_id)
	if inst == null:
		return
	world.add_child(inst)
	_pose(inst)
	await process_frame
	_focus_on_bone(inst)
	var cam: Camera3D = _camera_for(world, _aabb(inst))
	await _settle()
	var img: Image = root.get_texture().get_image()
	var out: String = _out_dir.path_join(model_id.replace("/", "__") + ("_" + _tag if _tag != "" else "") + ".png")
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
		_pose(inst)
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
