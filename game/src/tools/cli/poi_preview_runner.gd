extends Node
## POI preview logic (loaded by poi_preview.gd once autoloads exist). For each requested POI:
##   <id>_plan_L<n>.png   top-down orthographic plan of level n: roofs, ceilings and everything
##                        above 1.5 m over that floor hidden; markers: sleepers posed where they
##                        spawn (ADR-0022: standing = disc, kneeling / crouched = smaller discs,
##                        seated = disc on its seat, lying = a body-long capsule head to feet, a tick
##                        for the way each faces, a thin line back to where it was authored if a seat
##                        or bed moved it), coloured by ambush group (ungrouped pale blue) with the
##                        group's name, guardians in an orange ring; triggers in their group's colour
##                        linked to the group: room = its cells tinted, opening = a diamond on the
##                        edge, pickup / container / trap = a ring round it, each labelled "T id";
##                        pickups/notes yellow-green, lights orange, traps magenta (bars across edge
##                        traps, squares on cell traps), validator route path green, waypoints cyan
##                        with their index, route-cue windows white, authored props at their true
##                        size (gold = container, blue = solid, grey = no collision)
##   <id>_front.png, <id>_back.png, <id>_aerial.png   exterior perspective views
##   <id>_inside_L<n>_a.png / _b.png   (--inside) eye-level views across the largest room of level n
##   <id>_sleeper_<sid>.png   (--sleepers [sid,sid...]) the building's sleepers spawned and posed (on
##                        their seats and beds), a close view of each seated or lying one
## and prints the validator stats line ("POI_PREVIEW <id> stats {...}") plus any errors/warnings.
## Options: --out DIR, --size WxH, --all (every POI), --no-exterior, --no-plans, --inside,
## --sleepers [ids], --seed N (ADR-0030: dress each building as a run with world seed N builds it -
## its alternatives, wear, scatter and decals; files get a _s<N> suffix), --views front,back,aerial
## (the exterior views to shoot), --game-env HOUR (light the scene as the game does at that hour:
## EnvironmentController with SDFGI by the graphics preset - pick one with HOLLOWMERE_GFX - and the
## probes' interior fill; inside views settle longer for SDFGI and the probes). An id "gen:<template>:<n>" previews the building that template
## generates from seed n; "lot:<framework>:<lot id>" the building a run with --seed puts on that lot
## (LotPicker), dressed as that placement.
## Kit pieces / props that have not been generated render as stand-in boxes.

const CUT: float = 1.5
## Ambush group colours, in the order groups first appear among the sleepers (deterministic).
const GROUP_COLORS: Array[Color] = [Color(0.95, 0.2, 0.15), Color(1.0, 0.75, 0.1), Color(0.25, 0.85, 0.35),
	Color(0.7, 0.35, 1.0), Color(0.1, 0.8, 0.9), Color(1.0, 0.45, 0.75), Color(0.6, 0.85, 0.2), Color(1.0, 0.55, 0.25)]
const UNGROUPED: Color = Color(0.6, 0.75, 1.0)
const GUARDIAN: Color = Color(1.0, 0.55, 0.15)

var _out_dir: String = "res://../build/poi_preview"
var _size := Vector2i(1280, 720)
var _ids: PackedStringArray = []
var _exterior: bool = true
var _plans: bool = true
var _inside: bool = false
## --sleepers: spawn the sleepers and shoot the seated / lying ones (empty = every one, else ids).
var _sleepers: bool = false
var _sleeper_ids: PackedStringArray = []
## --seed: the world seed a run would dress the buildings with (-1 = the authored defaults).
var _seed: int = -1
var _views: PackedStringArray = ["front", "back", "aerial"]
## The placement id a "lot:" preview is dressed as (the game's "<framework>/<lot>").
var _instance: String = ""
## --game-env: the game hour to light the scene at with the game's EnvironmentController (-1 = the
## preview's own flat sky light).
var _game_hour: float = -1.0
## --room: the room letters to look across with --inside (each level's first that it has), in
## place of its largest room.
var _rooms: PackedStringArray = []
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
			"--inside":
				_inside = true
			"--seed":
				i += 1
				_seed = int(a[i])
			"--game-env":
				i += 1
				_game_hour = float(a[i])
			"--room":
				i += 1
				_rooms = a[i].split(",", false)
			"--views":
				i += 1
				_views = a[i].split(",", false)
			"--sleepers":
				_sleepers = true
				if i + 1 < a.size() and not a[i + 1].begins_with("--") and Content.get_def(&"poi", StringName(a[i + 1])) == null:
					i += 1
					_sleeper_ids = a[i].split(",", false)
			_:
				for part: String in a[i].split(" ", false):
					_ids.append(part)
		i += 1
	DirAccess.make_dir_recursive_absolute(_out_dir)


func _setup_environment() -> void:
	if _game_hour >= 0.0:
		var clock := WorldClock.new()
		clock.configure(Content.config(&"world_clock"), Content.config(&"horde"))
		clock.set_time(2, _game_hour)
		var ec := EnvironmentController.new()
		ec.name = "Environment"
		ec.clock = clock
		_world.add_child(ec)
		_sun = ec.sun
		print("POI_PREVIEW game light at %.2f h, preset %s" % [_game_hour, Settings.graphics_preset])
	else:
		_setup_preview_light()
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


func _setup_preview_light() -> void:
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


func _preview(id_arg: String) -> void:
	var pd: PoiDef = _resolve_def(id_arg)
	if pd == null:
		printerr("POI_PREVIEW unknown poi '%s'" % id_arg)
		return
	var id: String = id_arg.replace(":", "_") + ("_s%d" % _seed if _seed >= 0 else "")
	if _seed >= 0:
		var session: GameSession = GameSession.create_new({"seed": _seed, "game_mode": "survival"})
		pd = PoiManager.dress_for(pd, StringName(_instance if _instance != "" else "preview/%s" % id_arg), session)
		print("POI_PREVIEW %s dressed for seed %d: %s" % [id, _seed, pd.dressing.get("picks", {})])
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
			if not _views.has(view):
				continue
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
	if _inside:
		await _interiors(id, layout)
	if _sleepers:
		await _sleeper_shots(id, inst)
	inst.queue_free()
	await _frames(2)


## A content POI, or "gen:<template>:<n>": the building that template generates from seed n (ADR-0030).
func _resolve_def(id: String) -> PoiDef:
	_instance = ""
	if id.begins_with("lot:"):
		var lp: PackedStringArray = id.split(":")
		var fw: FrameworkDef = Content.get_def(&"framework", StringName(lp[1])) as FrameworkDef if lp.size() > 2 else null
		if fw == null:
			return null
		var lots: GDScript = load("res://src/poi/lot_picker.gd")
		for res: Dictionary in lots.call(&"resolve", fw, lp[1], maxi(_seed, 0)):
			if str((res["lot"] as Dictionary).get("id", "")) == lp[2]:
				_instance = str(res["instance"])
				var lot_def: PoiDef = lots.call(&"def_for", res) as PoiDef
				print("POI_PREVIEW %s holds %s %s: '%s'" % [id, res["kind"], res.get("template", res.get("def_id", "")),
					lot_def.display_name if lot_def != null else "nothing"])
				return lot_def
		return null
	if id.begins_with("gen:"):
		var parts: PackedStringArray = id.split(":")
		var t: Resource = Content.get_def(&"building_template", StringName(parts[1])) if parts.size() > 1 else null
		if t == null:
			return null
		var gen: GDScript = load("res://src/poi/building_generator.gd")
		var made: PoiDef = gen.call(&"generate", t, int(parts[2]) if parts.size() > 2 else 1) as PoiDef
		if made != null:
			print("POI_PREVIEW %s is '%s': %s" % [id, made.display_name, made.story])
		return made
	return Content.get_def(&"poi", StringName(id)) as PoiDef


## Eye-level views across the largest room of each level, corner to opposite corner and back: wall
## finishes, wear, baseboards, props and light as the player sees them.
func _interiors(id: String, layout: PoiLayout) -> void:
	_ground.visible = true
	_sun.rotation_degrees = Vector3(-38.0, -35.0, 0.0)
	# Each interior probe's daylight (PoiBuilder.daylight_ratio) and the share of the day fill it gets.
	var cfg: Dictionary = Content.config(&"interior_light")
	for probe: Node in get_tree().get_nodes_in_group(&"interior_probe"):
		var rp := probe as ReflectionProbe
		var ratio: float = float(rp.get_meta(&"daylight")) if rp.has_meta(&"daylight") else -1.0
		print("POI_PREVIEW %s probe at %s size %s: daylight %.3f, share %.2f" % [id, rp.position, rp.size, ratio,
			EnvironmentController.daylight_share(cfg, ratio)])
	for li: int in layout.level_ids:
		var by_room: Dictionary = {}
		for c: Vector2i in layout.room_cells(li):
			var ch: String = layout.room_at(li, c)
			if not by_room.has(ch):
				by_room[ch] = []
			(by_room[ch] as Array).append(c)
		var best: String = ""
		for want: String in _rooms:
			if best == "" and by_room.has(want):
				best = want
		if _rooms.is_empty():
			for ch: String in by_room:
				if best == "" or (by_room[ch] as Array).size() > (by_room[best] as Array).size():
					best = ch
		if best == "":
			continue
		var cells: Array = by_room[best]
		var lo := Vector2(1e9, 1e9)
		var hi := Vector2(-1e9, -1e9)
		for c: Vector2i in cells:
			lo = lo.min(Vector2(c))
			hi = hi.max(Vector2(c))
		# The free room cells nearest the bounding-box corners (rooms need not be rectangles, and a
		# camera inside a wardrobe shows nothing).
		var taken: Dictionary = {}
		for pr: Dictionary in layout.props:
			if int(pr.get("level", 0)) == li and pr.has("cell"):
				taken[pr["cell"]] = true
		var free: Array = cells.filter(func(c: Vector2i) -> bool: return not taken.has(c))
		if free.is_empty():
			free = cells
		var near_lo: Vector2i = free[0]
		var near_hi: Vector2i = free[0]
		for c: Vector2i in free:
			if Vector2(c).distance_squared_to(lo) < Vector2(near_lo).distance_squared_to(lo):
				near_lo = c
			if Vector2(c).distance_squared_to(hi) < Vector2(near_hi).distance_squared_to(hi):
				near_hi = c
		var y: float = layout.level_y(li)
		var pa: Vector3 = layout.cell_center(li, near_lo)
		var pb: Vector3 = layout.cell_center(li, near_hi)
		pa.y = y
		pb.y = y
		var into: Vector3 = (pb - pa).normalized()
		for view: String in ["a", "b"]:
			var from: Vector3 = pa if view == "a" else pb
			var to: Vector3 = pb if view == "a" else pa
			var cam := Camera3D.new()
			cam.fov = 70.0
			cam.near = 0.05
			_world.add_child(cam)
			cam.position = from - (into if view == "a" else -into) * 0.3 + Vector3.UP * 1.6
			cam.look_at(to + Vector3.UP * 1.0)
			cam.make_current()
			# The game's light needs SDFGI to converge and the probes to render (one at a time).
			await _shoot("%s_inside_L%d_%s" % [id, li, view], 8 if _game_hour < 0.0 else 48)
			cam.queue_free()


## Hides roofs and every piece/prop/node whose origin is above `cut` (rebuilding MultiMeshes);
## returns what to restore.
func _cut_above(inst: PoiInstance, cut: float) -> Array:
	var restore: Array = []
	for c: Node in inst.get_children():
		if c is MultiMeshInstance3D:
			var mmi := c as MultiMeshInstance3D
			if String(mmi.name).contains("Gables") or String(mmi.name).contains("Parapet"):
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
		if not pd.boxes.is_empty():
			# A compound collision (TD-270): each of its boxes.
			for b: Array in pd.collision_boxes():
				var bxf: Transform3D = xf * (b[1] as Transform3D)
				var part: MeshInstance3D = _marker(by_level[int(p["level"])], BoxMesh.new(), b[0], bxf.origin, pcol)
				part.basis = bxf.basis
			continue
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
	_sleeper_markers(layout, inst, by_level)
	_trigger_markers(layout, by_level)
	_cue_markers(layout, by_level)
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
		if not by_level.has(li5):
			continue
		if str(t.get("kind", "edge")) == "cell":
			# Cell traps: a flat square on every cell they cover; a bear trap sits at its own spot.
			if str(t["type"]) == "bear_trap":
				_marker(by_level[li5], BoxMesh.new(), Vector3(0.5, 0.06, 0.5), layout.local_pos(li5, t["pos"]) + Vector3.UP * 0.05, Color(1.0, 0.1, 0.9))
			else:
				for c: Vector2i in t["cells"]:
					_marker(by_level[li5], BoxMesh.new(), Vector3(0.8, 0.04, 0.8), layout.cell_center(li5, c) + Vector3.UP * 0.04, Color(1.0, 0.1, 0.9, 0.7))
			continue
		# Edge traps (wires, chimes, alarms): a bar along the edge they guard.
		var side: int = int(t.get("side_i", 2))
		var toward := Vector3(PoiLayout.DIRS[side].x, 0, PoiLayout.DIRS[side].y)
		var size := Vector3(1.0, 0.15, 0.12) if side in [0, 2] else Vector3(0.12, 0.15, 1.0)
		_marker(by_level[li5], BoxMesh.new(), size, layout.cell_center(li5, t["cell"]) + toward * 0.45 + Vector3.UP * 0.3, Color(1.0, 0.1, 0.9))
	return by_level


## Group name -> colour (GROUP_COLORS in first-appearance order; guardians orange).
func _group_colors(layout: PoiLayout) -> Dictionary:
	var out: Dictionary = {}
	for s: Dictionary in layout.sleepers:
		var g: String = str(s["group"])
		if g != "" and not out.has(g):
			out[g] = GUARDIAN if g == PoiLayout.GUARDIAN_GROUP else GROUP_COLORS[out.size() % GROUP_COLORS.size()]
	return out


## Group name -> centre of its sleepers' markers (POI-local), for the trigger links.
var _group_centroids: Dictionary = {}


## Sleepers as they spawn (ADR-0022): posed on their seat or bed, or where authored, in their
## ambush group's colour, a tick for their facing, guardians ringed.
func _sleeper_markers(layout: PoiLayout, inst: PoiInstance, by_level: Dictionary) -> void:
	var colors: Dictionary = _group_colors(layout)
	var seats: Dictionary = inst.seat_plan()
	var sums: Dictionary = {}
	_group_centroids = {}
	for s: Dictionary in layout.sleepers:
		var li: int = int(s["level"])
		if not by_level.has(li):
			continue
		var parent: Node3D = by_level[li]
		var g: String = str(s["group"])
		var col: Color = colors.get(g, UNGROUPED)
		var pose: String = str(s.get("pose", "stand"))
		var authored: Vector3 = PoiInstance.sleeper_local(layout, s)
		var pelvis: Vector3 = authored
		var yaw: float = deg_to_rad(float(s.get("rot", 0.0)))
		var top: float = authored.y + 0.6
		var seat: Dictionary = seats.get(str(s["sid"]), {})
		if not seat.is_empty():
			yaw = float(seat["yaw"])
			pelvis = seat["point"]
			top = pelvis.y + 0.35
			if Vector2(authored.x - pelvis.x, authored.z - pelvis.z).length() > 0.25:
				_link(parent, Vector3(authored.x, top, authored.z), Vector3(pelvis.x, top, pelvis.z), col.darkened(0.35), 0.05)
		var fwd := Vector3(sin(yaw), 0.0, cos(yaw))
		var at := Vector3(pelvis.x, top, pelvis.z)
		if pose == "lie":
			# Head to feet along its facing: the head 0.75 m behind the pelvis, the feet 0.9 ahead.
			var cap: MeshInstance3D = _marker(parent, CapsuleMesh.new(), Vector3(0.46, 1.65, 0.46), at + fwd * 0.07, col)
			cap.basis = Basis(Vector3.UP, yaw) * Basis(Vector3.RIGHT, PI * 0.5)
			_marker(parent, SphereMesh.new(), Vector3.ONE * 0.3, at - fwd * 0.62 + Vector3.UP * 0.12, col.lightened(0.45))
		else:
			var r: float = {"stand": 0.62, "kneel": 0.5, "crouch": 0.44, "sit": 0.52}.get(pose, 0.55)
			_marker(parent, SphereMesh.new(), Vector3.ONE * r, at, col)
			var tick: MeshInstance3D = _marker(parent, BoxMesh.new(), Vector3(0.09, 0.07, 0.42), at + fwd * 0.38 + Vector3.UP * 0.2, col.lightened(0.45))
			tick.basis = Basis(Vector3.UP, yaw)
		if bool(s["guardian"]):
			var ring := TorusMesh.new()
			ring.inner_radius = 0.46
			ring.outer_radius = 0.58
			_marker(parent, ring, Vector3.ONE, at + Vector3.UP * 0.3, GUARDIAN)
		if g != "":
			if not sums.has(g):
				sums[g] = [Vector3.ZERO, 0, li]
			sums[g][0] = (sums[g][0] as Vector3) + at
			sums[g][1] = int(sums[g][1]) + 1
	for g2: String in sums:
		var c: Array = sums[g2]
		var centre: Vector3 = (c[0] as Vector3) / float(c[1])
		_group_centroids[g2] = centre
		_label(by_level[int(c[2])], "guardian" if g2 == PoiLayout.GUARDIAN_GROUP else g2, centre + Vector3(0.0, 1.1, -0.8),
			colors.get(g2, UNGROUPED), 48)


## Triggers in their group's colour, each linked to its group: room = the room's cells tinted,
## opening = a diamond on the edge, pickup / container / trap = a ring round it; "T id" labels.
func _trigger_markers(layout: PoiLayout, by_level: Dictionary) -> void:
	var colors: Dictionary = _group_colors(layout)
	for t: Dictionary in layout.triggers:
		var col: Color = colors.get(str(t["group"]), UNGROUPED)
		var tint := Color(col.r, col.g, col.b, 0.28)
		var li: int = int(t["level"])
		var at := Vector3.INF
		match str(t["on"]):
			"room":
				if not by_level.has(li):
					continue
				var sum := Vector3.ZERO
				var n: int = 0
				for c: Vector2i in layout.room_cells(li):
					if layout.room_at(li, c) == str(t["room"]):
						_marker(by_level[li], BoxMesh.new(), Vector3(0.96, 0.03, 0.96), layout.cell_center(li, c) + Vector3.UP * 0.02, tint)
						sum += layout.cell_center(li, c)
						n += 1
				if n > 0:
					at = sum / float(n) + Vector3.UP * 0.3
			"opening":
				var op: Dictionary = layout.opening(str(t["opening"]))
				if op.is_empty():
					continue
				li = int(op["level"])
				at = _edge_centre(layout, op) + Vector3.UP * 0.6
				if by_level.has(li):
					var dia: MeshInstance3D = _marker(by_level[li], BoxMesh.new(), Vector3(0.42, 0.42, 0.42), at, col)
					dia.basis = Basis(Vector3.UP, PI * 0.25) * Basis(Vector3.RIGHT, PI * 0.25)
			"pickup":
				for pk: Dictionary in layout.pickups:
					if str(pk["pid"]) == str(t["pickup"]):
						li = int(pk["level"])
						at = layout.local_pos(li, pk["pos"]) + Vector3.UP * 0.4
			"container":
				for p: Dictionary in layout.props:
					if str(p.get("id", "")) == str(t["prop"]):
						li = int(p["level"])
						at = layout.local_pos(li, p["pos"]) + Vector3.UP * 0.4
			"trap":
				var tr: Dictionary = layout.trap(str(t["trap"]))
				if not tr.is_empty():
					li = int(tr["level"])
					at = layout.local_pos(li, tr["pos"]) + Vector3.UP * 0.4
		if at == Vector3.INF or not by_level.has(li):
			continue
		if str(t["on"]) in ["pickup", "container", "trap"]:
			var ring := TorusMesh.new()
			ring.inner_radius = 0.55
			ring.outer_radius = 0.68
			_marker(by_level[li], ring, Vector3.ONE, at, col)
		var text: String = "T guardian: enter loot room" if bool(t["implicit"]) else "T " + str(t["id"])
		_label(by_level[li], text, at + Vector3(0.0, 0.6, 0.45), col, 40)
		if _group_centroids.has(str(t["group"])):
			var to: Vector3 = _group_centroids[str(t["group"])]
			_link(by_level[li], at, Vector3(to.x, at.y, to.z), col, 0.05)


## Windows that get route cues (RouteCues): a white bar outside the window and the cue kinds.
func _cue_markers(layout: PoiLayout, by_level: Dictionary) -> void:
	var plan: Dictionary = RouteCues.plan(layout)
	for op_id: String in plan:
		var op: Dictionary = layout.opening(op_id)
		var f: Dictionary = RouteCues.frame(layout, op)
		if f.is_empty() or not by_level.has(int(op["level"])):
			continue
		var out: Vector3 = f["out"]
		var c: Vector3 = (f["centre"] as Vector3) + out * 0.35 + Vector3.UP * 0.2
		var bar: MeshInstance3D = _marker(by_level[int(op["level"])], BoxMesh.new(), Vector3(float(f["width"]) * 0.8, 0.1, 0.22), c, Color(1, 1, 1))
		bar.basis = Basis(Vector3.UP, atan2(out.x, out.z))
		_label(by_level[int(op["level"])], "cue " + ", ".join(plan[op_id]), c + out * 0.6 + Vector3.UP * 0.3, Color(1, 1, 1), 32)


func _edge_centre(layout: PoiLayout, op: Dictionary) -> Vector3:
	var e: Vector2i = op["edge"]
	var w: float = float(op["width"])
	var y: float = layout.level_y(int(op["level"]))
	if str(op["axis"]) == "h":
		return Vector3(layout.origin.x + e.x + w * 0.5, y, layout.origin.y + e.y)
	return Vector3(layout.origin.x + e.x, y, layout.origin.y + e.y + w * 0.5)


## A thin bar from a to b (links: trigger -> group, authored -> posed).
func _link(parent: Node3D, a: Vector3, b: Vector3, col: Color, width: float) -> void:
	var d: Vector3 = b - a
	if d.length() < 0.05:
		return
	var bar: MeshInstance3D = _marker(parent, BoxMesh.new(), Vector3(width, width, d.length()), (a + b) * 0.5, col)
	bar.basis = Basis.looking_at(d.normalized(), Vector3.UP if absf(d.normalized().y) < 0.98 else Vector3.FORWARD)


func _label(parent: Node3D, text: String, pos: Vector3, col: Color, size: int) -> void:
	var lab := Label3D.new()
	lab.text = text
	lab.font_size = size
	lab.pixel_size = 0.01
	lab.outline_size = 12
	lab.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	lab.no_depth_test = true
	lab.modulate = col
	lab.position = pos
	parent.add_child(lab)


## --sleepers: spawns the building's sleepers (a throwaway session and director: previews have no
## world) and shoots each seated or lying one from in front of its seat or beside its bed.
func _sleeper_shots(id: String, inst: PoiInstance) -> void:
	if Game.session == null:
		Game.session = GameSession.create_new({"seed": 4711, "game_mode": "survival"})
	var ai := AIDirector.new()
	ai.name = "PreviewAI"
	_world.add_child(ai)
	inst.spawn_sleepers(ai)
	_ground.visible = true
	_sun.rotation_degrees = Vector3(-38.0, -35.0, 0.0)
	await _frames(6)
	var seats: Dictionary = inst.seat_plan()
	for s: Dictionary in inst.layout.sleepers:
		var sid: String = str(s["sid"])
		if not _sleeper_ids.is_empty() and not _sleeper_ids.has(sid):
			continue
		var seat: Dictionary = seats.get(sid, {})
		var e: Enemy = inst.sleeper(sid)
		if e == null or (seat.is_empty() and _sleeper_ids.is_empty()):
			continue
		var target: Vector3 = e.global_position + Vector3.UP * 0.6
		var from_dir := Vector3(sin(e.global_rotation.y), 0.0, cos(e.global_rotation.y))
		if not seat.is_empty():
			var pt: Vector3 = inst.to_global(seat["point"] as Vector3)
			var ex: Vector3 = inst.to_global(seat["exit"] as Vector3)
			target = pt + Vector3.UP * (0.3 if str(seat["kind"]) == "seat" else 0.1)
			from_dir = Vector3(ex.x - pt.x, 0.0, ex.z - pt.z).normalized()
			if str(seat["kind"]) == "bed":
				# Beside the bed, toward its foot, looking along the body.
				var yaw: float = inst.global_rotation.y + float(seat["yaw"])
				from_dir = (from_dir + Vector3(sin(yaw), 0.0, cos(yaw)) * 0.7).normalized()
		var cam := Camera3D.new()
		cam.fov = 64.0
		cam.near = 0.05
		_world.add_child(cam)
		cam.global_position = target + _clear_view(target, from_dir, 1.6) + Vector3.UP * 0.7
		cam.look_at(target, Vector3.UP)
		cam.make_current()
		var fill := OmniLight3D.new()
		fill.light_energy = 1.3
		fill.omni_range = 7.0
		fill.light_color = Color(1.0, 0.93, 0.82)
		fill.shadow_enabled = true
		cam.add_child(fill)
		fill.position = Vector3(0.5, 0.4, 0.3)
		await _shoot("%s_sleeper_%s" % [id, sid], 4)
		cam.queue_free()
	inst.despawn_sleepers(ai)
	ai.queue_free()
	await _frames(2)


## The camera offset from `target` (horizontal) for a close view: along `dir` if the room is open
## that way for `want` metres, else the direction within +-70 degrees with the longest clear line
## (walls, doors, furniture and containers cut it short), kept a hand's breadth off what is in the
## way.
func _clear_view(target: Vector3, dir: Vector3, want: float) -> Vector3:
	var space: PhysicsDirectSpaceState3D = _world.get_world_3d().direct_space_state
	var eye_up := Vector3.UP * 0.7
	var best := Vector3.ZERO
	var best_len: float = -1.0
	for deg: float in [0.0, 35.0, -35.0, 70.0, -70.0]:
		var d: Vector3 = dir.rotated(Vector3.UP, deg_to_rad(deg))
		var q := PhysicsRayQueryParameters3D.create(target, target + d * want + eye_up, 1 | (1 << 1) | (1 << 2))
		var hit: Dictionary = space.intersect_ray(q)
		# Clear length along the ground (the ray climbs 0.7 m over `want`).
		var clear: float = want if hit.is_empty() else \
			maxf(0.3, (target.distance_to(hit["position"]) - 0.15) * want / Vector2(want, 0.7).length())
		if clear > best_len + 0.25:
			best_len = clear
			best = d * clear
		if clear >= want:
			break
	return best


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


## Renders and saves one image after `settle` frames (software Vulkan is slow: close views of
## a still scene need fewer).
func _shoot(file_stem: String, settle: int = 8) -> void:
	await _frames(settle)
	RenderingServer.force_draw()
	await _frames(1)
	var img: Image = get_viewport().get_texture().get_image()
	var out: String = _out_dir.path_join(file_stem + ".png")
	img.save_png(out)
	print("POI_PREVIEW wrote %s (mean luma %.3f)" % [out, ImageStats.mean_luma(img)])


func _frames(n: int) -> void:
	for i: int in n:
		await get_tree().process_frame
