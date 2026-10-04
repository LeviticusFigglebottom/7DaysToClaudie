extends Node
## POI preview logic (loaded by poi_preview.gd once autoloads exist). For each requested POI:
##   <id>_plan_L<n>.png   top-down orthographic plan of level n: roofs, ceilings and everything
##                        above 1.5 m over that floor hidden; markers: sleepers (hollow red, lurcher
##                        orange, keener magenta, dragger brown; lying = flat), pickups/notes
##                        yellow-green, lights orange, traps magenta, validator route path green,
##                        waypoints cyan with their index, authored props at their true size
##                        (gold = container, blue = solid, grey = no collision)
##   <id>_front.png, <id>_back.png, <id>_aerial.png   exterior perspective views
## and prints the validator stats line ("POI_PREVIEW <id> stats {...}") plus any errors/warnings.
## Options: --out DIR, --size WxH, --all (every POI), --no-exterior, --no-plans.
## Kit pieces / props that have not been generated render as stand-in boxes.

const CUT: float = 1.5
const ENEMY_COLORS: Dictionary = {"hollow": Color(0.85, 0.12, 0.1), "lurcher": Color(1.0, 0.5, 0.05),
	"keener": Color(0.9, 0.1, 0.85), "dragger": Color(0.45, 0.2, 0.1)}

var _out_dir: String = "res://../build/poi_preview"
var _size := Vector2i(1280, 720)
var _ids: PackedStringArray = []
var _exterior: bool = true
var _plans: bool = true
var _world: Node3D
var _sun: DirectionalLight3D
var _ground: MeshInstance3D
var _mats: Dictionary = {}


func _ready() -> void:
	_run.call_deferred()


func _run() -> void:
	_parse_args()
	get_tree().root.size = _size
	_world = Node3D.new()
	_world.name = "PreviewWorld"
	add_child(_world)
	_setup_environment()
	if _ids.is_empty():
		for d: PoiDef in Content.all(&"poi"):
			_ids.append(String(d.id))
	for id: String in _ids:
		await _preview(id)
	get_tree().quit(0)


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
			"--all":
				_ids.clear()
			"--no-exterior":
				_exterior = false
			"--no-plans":
				_plans = false
			_:
				for part: String in a[i].split(" ", false):
					_ids.append(part)
		i += 1
	DirAccess.make_dir_recursive_absolute(_out_dir)


func _setup_environment() -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	var sky := Sky.new()
	var sky_mat := ProceduralSkyMaterial.new()
	sky_mat.sky_top_color = Color(0.32, 0.42, 0.55)
	sky_mat.sky_horizon_color = Color(0.68, 0.7, 0.72)
	sky_mat.ground_horizon_color = Color(0.4, 0.4, 0.38)
	sky_mat.ground_bottom_color = Color(0.15, 0.14, 0.12)
	sky.sky_material = sky_mat
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_energy = 1.2
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.ssao_enabled = true
	var we := WorldEnvironment.new()
	we.environment = env
	_world.add_child(we)
	_sun = DirectionalLight3D.new()
	_sun.shadow_enabled = true
	_sun.light_energy = 1.5
	_sun.light_color = Color(1.0, 0.95, 0.86)
	_world.add_child(_sun)
	_ground = MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(240, 240)
	_ground.mesh = plane
	_ground.position.y = -0.02
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color(0.27, 0.29, 0.21)
	gm.roughness = 0.95
	_ground.material_override = gm
	_world.add_child(_ground)


func _preview(id: String) -> void:
	var pd: PoiDef = Content.get_def(&"poi", StringName(id)) as PoiDef
	if pd == null:
		printerr("POI_PREVIEW unknown poi '%s'" % id)
		return
	var v: PoiValidator = PoiValidator.validate(pd)
	print("POI_PREVIEW %s stats %s" % [id, v.stats])
	for e: String in v.errors:
		print("POI_PREVIEW %s ERROR %s" % [id, e])
	for w: String in v.warnings:
		print("POI_PREVIEW %s warn %s" % [id, w])
	var layout: PoiLayout = PoiLayout.compile(pd)
	var inst: PoiInstance = PoiBuilder.build(layout, StringName("preview/%s" % id))
	_world.add_child(inst)
	await _frames(2)
	var ext: Rect2 = layout.extent()
	var top: float = layout.level_y(layout.level_ids.back()) + PoiLayout.STOREY
	var center := Vector3(ext.get_center().x, top * 0.4, ext.get_center().y)
	if _exterior:
		_ground.visible = true
		_sun.rotation_degrees = Vector3(-38.0, -35.0, 0.0)
		var radius: float = 0.5 * Vector3(ext.size.x, top + 2.0, ext.size.y).length()
		var views: Dictionary = {"front": Vector3(-0.55, 0.5, 1.0), "back": Vector3(0.6, 0.55, -1.0), "aerial": Vector3(0.7, 1.5, 0.9)}
		for view: String in views:
			var cam := Camera3D.new()
			cam.fov = 45.0
			_world.add_child(cam)
			var dist: float = radius / tan(deg_to_rad(cam.fov * 0.5)) * 1.12
			cam.position = center + (views[view] as Vector3).normalized() * dist
			cam.look_at(center)
			cam.make_current()
			await _shoot("%s_%s" % [id, view])
			cam.queue_free()
	if _plans:
		var markers: Dictionary = _build_markers(v, layout, inst)
		_sun.rotation_degrees = Vector3(-72.0, -30.0, 0.0)
		for li: int in layout.level_ids:
			var cut: float = layout.level_y(li) + CUT
			var restore: Array = _cut_above(inst, cut)
			_ground.visible = li >= 0
			for k: int in markers:
				(markers[k] as Node3D).visible = k == li
			var cam2 := Camera3D.new()
			cam2.projection = Camera3D.PROJECTION_ORTHOGONAL
			var aspect: float = float(_size.x) / float(_size.y)
			cam2.size = maxf(ext.size.y + 7.0, (ext.size.x + 7.0) / aspect)
			cam2.near = 0.1
			cam2.far = 80.0
			_world.add_child(cam2)
			cam2.position = Vector3(ext.get_center().x, cut + 30.0, ext.get_center().y)
			cam2.look_at(Vector3(ext.get_center().x, cut, ext.get_center().y), Vector3(0, 0, -1))
			cam2.make_current()
			await _shoot("%s_plan_L%d" % [id, li])
			cam2.queue_free()
			_restore(restore)
		for k2: int in markers:
			(markers[k2] as Node3D).queue_free()
	inst.queue_free()
	await _frames(2)


## Hides roofs and every piece/prop/node whose origin is above `cut` (rebuilding MultiMeshes);
## returns what to restore.
func _cut_above(inst: PoiInstance, cut: float) -> Array:
	var restore: Array = []
	for c: Node in inst.get_children():
		if c is MultiMeshInstance3D:
			var mmi := c as MultiMeshInstance3D
			if String(mmi.name).contains("Gables"):
				restore.append([mmi, mmi.visible])
				mmi.visible = false
				continue
			var mm: MultiMesh = mmi.multimesh
			var keep: Array[int] = []
			for i: int in mm.instance_count:
				if mm.get_instance_transform(i).origin.y <= cut:
					keep.append(i)
			var cut_mm := MultiMesh.new()
			cut_mm.transform_format = MultiMesh.TRANSFORM_3D
			cut_mm.use_custom_data = mm.use_custom_data
			cut_mm.mesh = mm.mesh
			cut_mm.instance_count = keep.size()
			for j: int in keep.size():
				cut_mm.set_instance_transform(j, mm.get_instance_transform(keep[j]))
				if mm.use_custom_data:
					cut_mm.set_instance_custom_data(j, mm.get_instance_custom_data(keep[j]))
			restore.append([mmi, mm])
			mmi.multimesh = cut_mm
		elif c is Node3D and not c is Light3D:
			var n := c as Node3D
			var nm: String = String(n.name)
			var hide: bool = nm.contains("Roof") or nm.contains("Parapet") or (n.position.y > cut and not nm.begins_with("Marker"))
			if hide and n.visible:
				restore.append([n, true])
				n.visible = false
	return restore


func _restore(restore: Array) -> void:
	for r: Array in restore:
		if r[1] is MultiMesh:
			(r[0] as MultiMeshInstance3D).multimesh = r[1]
		else:
			(r[0] as Node3D).visible = bool(r[1])


func _build_markers(v: PoiValidator, layout: PoiLayout, inst: PoiInstance) -> Dictionary:
	var by_level: Dictionary = {}
	for li: int in layout.level_ids:
		var n := Node3D.new()
		n.name = "Marker_L%d" % li
		n.visible = false
		inst.add_child(n)
		by_level[li] = n
	# Authored props at their true size and transform (generated models may be missing, in which
	# case the builder shows uniform placeholder boxes): gold = container, blue = solid, grey = none.
	var pb := PoiBuilder.new()
	pb.layout = layout
	for p: Dictionary in layout.props:
		var pd: PropDef = Content.get_def(&"prop", StringName(str(p.get("prop", "")))) as PropDef
		if pd == null or not by_level.has(int(p["level"])):
			continue
		var xf: Transform3D = pb._prop_xf(p, pd)
		var pcol := Color(0.3, 0.55, 0.95, 0.55)
		if p.has("container") or pd.container != &"":
			pcol = Color(0.95, 0.7, 0.15, 0.6)
		elif pd.collision == "none":
			pcol = Color(0.75, 0.75, 0.75, 0.35)
		var box: MeshInstance3D = _marker(by_level[int(p["level"])], BoxMesh.new(), pd.size.max(Vector3(0.05, 0.05, 0.05)),
			xf * Vector3(0.0, pd.size.y * 0.5, 0.0), pcol)
		box.basis = xf.basis
	for path: Array in v.paths:
		for node: Variant in path:
			if node is Array and by_level.has(int(node[0])):
				var p: Vector3 = layout.cell_center(int(node[0]), node[1]) + Vector3.UP * 0.06
				_marker(by_level[int(node[0])], BoxMesh.new(), Vector3(0.22, 0.04, 0.22), p, Color(0.2, 0.95, 0.3))
	for i: int in layout.route.size():
		var wp: Dictionary = layout.route[i]
		var li2: int = int(wp["level"])
		if not by_level.has(li2):
			continue
		var p2: Vector3 = layout.local_pos(li2, wp["pos"]) + Vector3.UP * 0.1
		_marker(by_level[li2], SphereMesh.new(), Vector3.ONE * 0.45, p2, Color(0.1, 0.85, 1.0))
		var lab := Label3D.new()
		lab.text = str(i)
		lab.font_size = 72
		lab.pixel_size = 0.01
		lab.outline_size = 18
		lab.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		lab.no_depth_test = true
		lab.modulate = Color(0.1, 0.9, 1.0)
		lab.position = p2 + Vector3(0.45, 0.6, -0.45)
		(by_level[li2] as Node3D).add_child(lab)
	for s: Dictionary in layout.sleepers:
		var li3: int = int(s["level"])
		if not by_level.has(li3):
			continue
		var col: Color = ENEMY_COLORS.get(str(s.get("enemy", "hollow")), Color.RED)
		var p3: Vector3 = layout.local_pos(li3, s["pos"])
		var lying: bool = str(s.get("pose", "stand")) == "lie"
		var cap := _marker(by_level[li3], CapsuleMesh.new(), Vector3(0.6, 1.6, 0.6) if not lying else Vector3(0.6, 1.6, 0.6),
			p3 + Vector3.UP * (0.8 if not lying else 0.3), col)
		if lying:
			cap.rotation = Vector3(PI * 0.5, deg_to_rad(float(s.get("rot", 0.0))), 0.0)
	for pk: Dictionary in layout.pickups:
		var li4: int = int(pk["level"])
		if by_level.has(li4):
			_marker(by_level[li4], BoxMesh.new(), Vector3(0.35, 0.35, 0.35), layout.local_pos(li4, pk["pos"]) + Vector3.UP * (float(pk.get("y", 0.0)) + 0.2), Color(0.7, 1.0, 0.1))
	for l: Variant in layout.lights:
		if l is Dictionary:
			var pl: Dictionary = layout._placed(l)
			if by_level.has(int(pl["level"])):
				_marker(by_level[int(pl["level"])], SphereMesh.new(), Vector3.ONE * 0.3, layout.local_pos(pl["level"], pl["pos"]) + Vector3.UP * minf(float(l.get("height", 2.3)), 1.4), Color(1.0, 0.6, 0.15))
	for t: Dictionary in layout.traps:
		var li5: int = int(t["level"])
		if by_level.has(li5):
			var side: int = PoiLayout.SIDES.get(str(t.get("side", "S")), 2)
			var toward := Vector3(PoiLayout.DIRS[side].x, 0, PoiLayout.DIRS[side].y)
			var size := Vector3(1.0, 0.15, 0.12) if side in [0, 2] else Vector3(0.12, 0.15, 1.0)
			_marker(by_level[li5], BoxMesh.new(), size, layout.cell_center(li5, t["cell"]) + toward * 0.35 + Vector3.UP * 0.3, Color(1.0, 0.1, 0.9))
	return by_level


func _marker(parent: Node3D, mesh: PrimitiveMesh, size: Vector3, pos: Vector3, col: Color) -> MeshInstance3D:
	if mesh is BoxMesh:
		(mesh as BoxMesh).size = size
	elif mesh is SphereMesh:
		(mesh as SphereMesh).radius = size.x * 0.5
		(mesh as SphereMesh).height = size.x
	elif mesh is CapsuleMesh:
		(mesh as CapsuleMesh).radius = size.x * 0.5
		(mesh as CapsuleMesh).height = size.y
	var key: String = col.to_html()
	if not _mats.has(key):
		var m := StandardMaterial3D.new()
		m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		m.albedo_color = col
		if col.a < 0.99:
			m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		_mats[key] = m
	mesh.material = _mats[key]
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	mi.position = pos
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	parent.add_child(mi)
	return mi


func _shoot(file_stem: String) -> void:
	await _frames(8)
	RenderingServer.force_draw()
	await _frames(1)
	var img: Image = get_viewport().get_texture().get_image()
	var out: String = _out_dir.path_join(file_stem + ".png")
	img.save_png(out)
	print("POI_PREVIEW wrote ", out)


func _frames(n: int) -> void:
	for i: int in n:
		await get_tree().process_frame
