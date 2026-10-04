extends SceneTree
## Renders the terrain from given viewpoints (development QA).
##   xvfb-run godot --path game --rendering-driver vulkan -s res://src/tools/cli/terrain_view.gd -- \
##       --cam x,y,z --look x,y,z [--out file.png] [--size 1280x720] [--hour 15]
## y may be "g+2" meaning 2 m above the ground.

var _out: String = "res://../build/terrain_view.png"
var _size := Vector2i(1280, 720)


func _initialize() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	_out = _arg(a, "--out", ProjectSettings.globalize_path("res://").path_join("../build/terrain_view.png"))
	var sz: PackedStringArray = _arg(a, "--size", "1280x720").split("x")
	_size = Vector2i(int(sz[0]), int(sz[1]))
	root.size = _size
	var t0: int = Time.get_ticks_msec()
	var loader := WorldLoader.new()
	loader.load_world("res://world/main_map")
	print("world loaded in %d ms (%d detailed, %d coarse)" % [Time.get_ticks_msec() - t0, loader.detailed.size(), loader.coarse.size()])
	var scene := Node3D.new()
	root.add_child(scene)
	var tm := TerrainManager.new()
	scene.add_child(tm)
	tm.setup(loader.world, loader.detailed, loader.coarse)
	var cam_s: String = _arg(a, "--cam", "-60,g+30,2150")
	var look_s: String = _arg(a, "--look", "60,g+0,2000")
	var cam_pos: Vector3 = _parse_pos(cam_s, tm)
	var look_pos: Vector3 = _parse_pos(look_s, tm)
	var hour: float = float(_arg(a, "--hour", "15"))
	_env(scene, hour)
	var cam := Camera3D.new()
	cam.fov = 70.0
	cam.far = 9000.0
	scene.add_child(cam)
	cam.position = cam_pos
	cam.look_at(look_pos)
	cam.make_current()
	tm.update_streaming(cam_pos, true)
	print("terrain streamed in %d ms" % (Time.get_ticks_msec() - t0))
	for i: int in 6:
		await process_frame
	root.get_texture().get_image().save_png(_out)
	print("TERRAIN_VIEW ", _out)
	quit(0)


func _parse_pos(s: String, tm: TerrainManager) -> Vector3:
	var p: PackedStringArray = s.split(",")
	var x: float = float(p[0])
	var z: float = float(p[2])
	var ys: String = p[1]
	var y: float
	if ys.begins_with("g"):
		y = tm.height_at(x, z) + float(ys.substr(1))
	else:
		y = float(ys)
	return Vector3(x, y, z)


func _env(scene: Node3D, hour: float) -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	var sky := Sky.new()
	var sm := ProceduralSkyMaterial.new()
	sm.sky_top_color = Color(0.3, 0.42, 0.58)
	sm.sky_horizon_color = Color(0.66, 0.7, 0.74)
	sm.ground_horizon_color = Color(0.5, 0.52, 0.5)
	sky.sky_material = sm
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.fog_enabled = true
	env.fog_density = 0.0009
	env.fog_light_color = Color(0.62, 0.66, 0.7)
	env.fog_aerial_perspective = 0.4
	env.ssao_enabled = true
	var we := WorldEnvironment.new()
	we.environment = env
	scene.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 250.0
	var elev: float = clampf(sin((hour - 6.0) / 13.0 * PI) * 50.0, 3.0, 60.0)
	sun.rotation_degrees = Vector3(-elev, 30.0 + (hour - 12.0) * 15.0, 0.0)
	sun.light_energy = 1.4
	scene.add_child(sun)


static func _arg(a: PackedStringArray, key: String, default: String) -> String:
	var i: int = a.find(key)
	return a[i + 1] if i >= 0 and i + 1 < a.size() else default
