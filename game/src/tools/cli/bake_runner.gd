extends Node
## Bakes far-tree impostors from the generated tree models (TD-005): for every tree species, the
## first model variant is rendered from ImpostorLibrary.FRAMES directions around the trunk axis
## with an orthographic camera, unshaded (albedo + coverage) and as the normal buffer (frame-space
## normals), supersampled and packed side by side into
##   assets/generated/impostors/<species>.png, <species>_n.png and <species>.json (quad size)
## with .import sidecars (mipmapped). Run through `make bake`, which re-imports afterwards.

const SUPER: int = 4

var _vp: SubViewport
var _cam: Camera3D
var _holder: Node3D


func _ready() -> void:
	_run.call_deferred()


func _run() -> void:
	var t0: int = Time.get_ticks_msec()
	var out_dir: String = ProjectSettings.globalize_path(ImpostorLibrary.DIR)
	DirAccess.make_dir_recursive_absolute(out_dir)
	_setup()
	# Neutral weather and summer foliage: the impostor shader re-tints by season at runtime.
	RenderingServer.global_shader_parameter_set(&"hm_season", Vector4(0.0, 1.0, 0.0, 0.0))
	RenderingServer.global_shader_parameter_set(&"hm_snow", 0.0)
	RenderingServer.global_shader_parameter_set(&"hm_wetness", 0.0)
	var baked: int = 0
	for d: ContentDef in Content.all(&"species"):
		var sp: SpeciesDef = d as SpeciesDef
		if sp.veg_kind != "tree" or sp.models.is_empty():
			continue
		if not ModelLibrary.has_model(sp.models[0]):
			print("BAKE skip %s (model %s not generated)" % [sp.id, sp.models[0]])
			continue
		await _bake_species(sp, out_dir)
		baked += 1
	print("BAKE done: %d species in %.1fs" % [baked, (Time.get_ticks_msec() - t0) / 1000.0])
	get_tree().quit(0)


func _setup() -> void:
	_vp = SubViewport.new()
	_vp.size = Vector2i(ImpostorLibrary.FRAME_W * SUPER, ImpostorLibrary.FRAME_H * SUPER)
	_vp.transparent_bg = true
	_vp.own_world_3d = true
	_vp.msaa_3d = Viewport.MSAA_4X
	_vp.render_target_update_mode = SubViewport.UPDATE_DISABLED
	add_child(_vp)
	var env := Environment.new()
	env.background_mode = Environment.BG_CLEAR_COLOR
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(1, 1, 1)
	env.ambient_light_energy = 1.0
	var we := WorldEnvironment.new()
	we.environment = env
	_vp.add_child(we)
	_cam = Camera3D.new()
	_cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	_cam.keep_aspect = Camera3D.KEEP_HEIGHT
	_cam.near = 0.05
	_cam.far = 200.0
	_vp.add_child(_cam)
	_holder = Node3D.new()
	_vp.add_child(_holder)


func _bake_species(sp: SpeciesDef, out_dir: String) -> void:
	for c: Node in _holder.get_children():
		c.free()
	var scene: Node3D = (load(ModelLibrary.model_path(sp.models[0])) as PackedScene).instantiate() as Node3D
	_holder.add_child(scene)
	# Quad size: the frame is 1:2, so fit the tree's height and its widest radius around the trunk.
	var aabb: AABB = ModelLibrary.mesh(sp.models[0]).get_aabb()
	var radius: float = 0.0
	for i: int in 8:
		var corner: Vector3 = aabb.get_endpoint(i)
		radius = maxf(radius, Vector2(corner.x, corner.z).length())
	var height: float = maxf(aabb.end.y, radius * 4.0) * 1.02
	var width: float = height * 0.5
	_cam.size = height
	var albedo := Image.create(ImpostorLibrary.FRAME_W * ImpostorLibrary.FRAMES, ImpostorLibrary.FRAME_H, false, Image.FORMAT_RGBA8)
	var normals := Image.create(ImpostorLibrary.FRAME_W * ImpostorLibrary.FRAMES, ImpostorLibrary.FRAME_H, false, Image.FORMAT_RGBA8)
	for f: int in ImpostorLibrary.FRAMES:
		var a: float = float(f) * TAU / float(ImpostorLibrary.FRAMES)
		var dir := Vector3(sin(a), 0.0, cos(a))
		var target := Vector3(0.0, height * 0.5, 0.0)
		_cam.global_transform = Transform3D(Basis(), target + dir * 60.0).looking_at(target, Vector3.UP)
		var col: Image = await _render(Viewport.DEBUG_DRAW_UNSHADED)
		var nrm: Image = await _render(Viewport.DEBUG_DRAW_NORMAL_BUFFER)
		var at := Vector2i(f * ImpostorLibrary.FRAME_W, 0)
		albedo.blit_rect(_shrink(col), Rect2i(Vector2i.ZERO, Vector2i(ImpostorLibrary.FRAME_W, ImpostorLibrary.FRAME_H)), at)
		var small_n: Image = _shrink(nrm)
		var small_c: Image = _shrink(col)
		# Coverage from the albedo pass; flat facing normal where nothing was drawn.
		for y: int in ImpostorLibrary.FRAME_H:
			for x: int in ImpostorLibrary.FRAME_W:
				var n: Color = small_n.get_pixel(x, y)
				if small_c.get_pixel(x, y).a < 0.05:
					n = Color(0.5, 0.5, 1.0)
				n.a = 1.0
				small_n.set_pixel(x, y, n)
		normals.blit_rect(small_n, Rect2i(Vector2i.ZERO, Vector2i(ImpostorLibrary.FRAME_W, ImpostorLibrary.FRAME_H)), at)
	var base: String = out_dir.path_join(String(sp.id))
	_dilate(albedo)
	albedo.save_png(base + ".png")
	normals.save_png(base + "_n.png")
	_write_import(base + ".png")
	_write_import(base + "_n.png")
	var meta := FileAccess.open(base + ".json", FileAccess.WRITE)
	meta.store_string(JSON.stringify({"width": snappedf(width, 0.01), "height": snappedf(height, 0.01), "model": sp.models[0], "frames": ImpostorLibrary.FRAMES}))
	meta.close()
	print("BAKE %s %.1fx%.1f m" % [sp.id, width, height])


func _render(mode: Viewport.DebugDraw) -> Image:
	_vp.debug_draw = mode
	_vp.render_target_update_mode = SubViewport.UPDATE_ONCE
	for i: int in 3:
		await RenderingServer.frame_post_draw
	return _vp.get_texture().get_image()


func _shrink(img: Image) -> Image:
	var copy: Image = img.duplicate() as Image
	copy.convert(Image.FORMAT_RGBA8)
	copy.resize(ImpostorLibrary.FRAME_W, ImpostorLibrary.FRAME_H, Image.INTERPOLATE_LANCZOS)
	return copy


## Bleeds edge colours into transparent texels so mipmaps don't fringe the silhouette dark.
static func _dilate(img: Image) -> void:
	var w: int = img.get_width()
	var h: int = img.get_height()
	for _pass: int in 4:
		var src: Image = img.duplicate() as Image
		for y: int in h:
			for x: int in w:
				if src.get_pixel(x, y).a > 0.05:
					continue
				var acc := Color(0, 0, 0, 0)
				var n: int = 0
				for o: Vector2i in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
					var q: Vector2i = Vector2i(x, y) + o
					if q.x < 0 or q.y < 0 or q.x >= w or q.y >= h:
						continue
					var c: Color = src.get_pixel(q.x, q.y)
					if c.a > 0.05:
						acc += c
						n += 1
				if n > 0:
					var avg: Color = acc / float(n)
					img.set_pixel(x, y, Color(avg.r, avg.g, avg.b, 0.0))


## Mipmapped VRAM-compressed import (the atlases are sampled in 3D at a distance). The normal
## atlas holds frame-space normals, not tangent-space ones, so normal-map compression stays off.
static func _write_import(png_path: String) -> void:
	var f := FileAccess.open(png_path + ".import", FileAccess.WRITE)
	f.store_string("[remap]\n\nimporter=\"texture\"\ntype=\"CompressedTexture2D\"\n\n[params]\n\ncompress/mode=2\ncompress/high_quality=false\ncompress/normal_map=2\nmipmaps/generate=true\nprocess/size_limit=0\ndetect_3d/compress_to=0\n")
	f.close()
