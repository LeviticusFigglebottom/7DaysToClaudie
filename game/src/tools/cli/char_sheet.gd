extends SceneTree
## Animation contact sheets for a character GLB.
## godot --path game --rendering-driver vulkan -s res://src/tools/cli/char_sheet.gd -- --glb <path|res://...> --out <png prefix>
##     [--anims a,b,c] [--frames 6] [--cell 300x400] [--az 35] [--el 12] [--dist 4.2] [--res]
## Loads at runtime with GLTFDocument unless the path starts with res:// (imported scene, real
## materials). Prints skeleton bones + animation names/lengths.

var _glb: String = ""
var _out: String = "res://../build/char_sheets/sheet"
var _anims: PackedStringArray = []
var _frames: int = 6
var _cell := Vector2i(300, 420)
var _az: float = 35.0
var _el: float = 12.0
var _dist: float = 4.0
var _look_y: float = 0.85
## In-game body proportions (EnemyDef behavior.body_scale), e.g. --scale 1.45,1,1.35
var _scale := Vector3.ONE


func _initialize() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	var i: int = 0
	while i < a.size():
		match a[i]:
			"--glb":
				i += 1
				_glb = a[i]
			"--out":
				i += 1
				_out = a[i]
			"--anims":
				i += 1
				_anims = a[i].split(",")
			"--frames":
				i += 1
				_frames = int(a[i])
			"--cell":
				i += 1
				var p: PackedStringArray = a[i].split("x")
				_cell = Vector2i(int(p[0]), int(p[1]))
			"--az":
				i += 1
				_az = float(a[i])
			"--el":
				i += 1
				_el = float(a[i])
			"--dist":
				i += 1
				_dist = float(a[i])
			"--scale":
				i += 1
				var sc: PackedStringArray = a[i].split(",")
				_scale = Vector3(float(sc[0]), float(sc[1]), float(sc[2]))
			"--look":
				i += 1
				_look_y = float(a[i])
		i += 1
	await _run()
	quit(0)


func _load() -> Node3D:
	if _glb.begins_with("res://"):
		var ps: PackedScene = load(_glb)
		return ps.instantiate() as Node3D
	var doc := GLTFDocument.new()
	var st := GLTFState.new()
	if doc.append_from_file(_glb, st) != OK:
		push_error("load failed")
		return null
	return doc.generate_scene(st) as Node3D


func _run() -> void:
	root.size = _cell
	var world := Node3D.new()
	root.add_child(world)
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.42, 0.44, 0.47)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.55, 0.57, 0.6)
	env.ambient_light_energy = 0.7
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	var we := WorldEnvironment.new()
	we.environment = env
	world.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-45, 30, 0)
	sun.light_energy = 1.4
	sun.shadow_enabled = true
	world.add_child(sun)
	var ground := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(20, 20)
	ground.mesh = pm
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color(0.3, 0.29, 0.27)
	ground.material_override = gm
	world.add_child(ground)
	# 0.5 m grid lines on the ground to judge foot sliding
	for k: int in range(-6, 7):
		for axis: int in 2:
			var line := MeshInstance3D.new()
			var bm := BoxMesh.new()
			bm.size = Vector3(6.0, 0.002, 0.008) if axis == 0 else Vector3(0.008, 0.002, 6.0)
			line.mesh = bm
			var lm := StandardMaterial3D.new()
			lm.albedo_color = Color(0.2, 0.2, 0.2)
			line.material_override = lm
			line.position = Vector3(0, 0.001, k * 0.5) if axis == 0 else Vector3(k * 0.5, 0.001, 0)
			world.add_child(line)
	var inst: Node3D = _load()
	world.add_child(inst)
	inst.scale = _scale
	var cam := Camera3D.new()
	cam.fov = 35.0
	world.add_child(cam)
	await process_frame
	var az: float = deg_to_rad(_az)
	var el: float = deg_to_rad(_el)
	var target := Vector3(0, _look_y, 0)
	cam.look_at_from_position(target + Vector3(sin(az) * cos(el), sin(el), cos(az) * cos(el)) * _dist, target)
	cam.make_current()
	var ap: AnimationPlayer = inst.find_children("*", "AnimationPlayer", true, false)[0] as AnimationPlayer
	for sk: Node in inst.find_children("*", "Skeleton3D", true, false):
		var s := sk as Skeleton3D
		var names: PackedStringArray = []
		for b: int in s.get_bone_count():
			names.append(s.get_bone_name(b))
		print("BONES ", s.get_bone_count(), " ", ",".join(names))
	var list: PackedStringArray = ap.get_animation_list()
	for n: String in list:
		print("ANIM ", n, " ", snappedf(ap.get_animation(n).length, 0.0001))
	var todo: PackedStringArray = _anims if _anims.size() > 0 else list
	var sheet := Image.create(_cell.x * _frames, _cell.y * todo.size(), false, Image.FORMAT_RGBA8)
	var row: int = 0
	for n: String in todo:
		if not ap.has_animation(n):
			print("MISSING ", n)
			row += 1
			continue
		var anim: Animation = ap.get_animation(n)
		ap.play(n)
		for f: int in _frames:
			var t: float = anim.length * float(f) / float(max(1, _frames - 1))
			ap.seek(t, true)
			ap.pause()
			for w: int in 3:
				await process_frame
			RenderingServer.force_draw()
			await process_frame
			var img: Image = root.get_texture().get_image()
			img.convert(Image.FORMAT_RGBA8)
			var iw: int = img.get_width()
			var ih: int = img.get_height()
			var want: float = float(_cell.x) / float(_cell.y)
			var cw: int = mini(iw, int(ih * want))
			var ch: int = mini(ih, int(cw / want))
			var crop: Image = img.get_region(Rect2i((iw - cw) / 2, (ih - ch) / 2, cw, ch))
			crop.resize(_cell.x, _cell.y, Image.INTERPOLATE_BILINEAR)
			sheet.blit_rect(crop, Rect2i(Vector2i.ZERO, _cell), Vector2i(f * _cell.x, row * _cell.y))
		row += 1
	sheet.save_png(_out + ".png")
	print("SHEET ", _out + ".png")
