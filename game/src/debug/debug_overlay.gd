class_name DebugOverlay
extends CanvasLayer
## In-game debug tools (added by GameWorld when DebugTools.enabled()). See docs/DEBUG_TOOLS.md.
##   F1  menu: spawn Hollowed, give kits, time & Hum control, weather, teleports, toggles, seed viewer
##   F2  free camera (WASD + mouse, Shift fast, E/Q up/down)
##   F3  AI overlay: state/awareness labels, targets, detection radius, Hum flow arrows, heat cells
##   F4  performance overlay: FPS, frame time, draw calls, primitives, memory, world stats
##   F6  POI route visualiser: validator routes, waypoints, sleepers, loot rooms of nearby POIs
##   F7  structural view: per-piece stability and hit points

const TELEPORTS: Array[Array] = [
	["Drop site", Vector3(-292, 0, 2296)], ["Pell's Crossing", Vector3(-60, 0, 2070)], ["Okafor farm", Vector3(-190, 0, 1975)],
	["Larch Pond", Vector3(-262, 0, 1860)], ["Larkspur cliffs", Vector3(-380, 0, 2200)], ["Route 9 bridge", Vector3(180, 0, 1975)],
]

var world: Node
var _menu: PanelContainer
var _perf: Label
var _seed_label: Label
var _draw_root: Node3D
var _mesh: ImmediateMesh
var _mesh_node: MeshInstance3D
var _labels: Node3D
var _cam: Camera3D = null
var _cam_pitch: float = 0.0
var _t: float = 0.0


func setup(w: Node) -> void:
	world = w
	layer = 50
	process_mode = Node.PROCESS_MODE_ALWAYS
	_build_menu()
	_perf = Label.new()
	_perf.position = Vector2(14, 120)
	_perf.add_theme_color_override(&"font_color", Color(0.8, 1.0, 0.8))
	_perf.add_theme_color_override(&"font_outline_color", Color(0, 0, 0))
	_perf.add_theme_constant_override(&"outline_size", 4)
	_perf.add_theme_font_size_override(&"font_size", 14)
	_perf.visible = false
	add_child(_perf)
	_draw_root = Node3D.new()
	_draw_root.name = "DebugDraw"
	world.add_child(_draw_root)
	_mesh = ImmediateMesh.new()
	_mesh_node = MeshInstance3D.new()
	_mesh_node.mesh = _mesh
	_mesh_node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.vertex_color_use_as_albedo = true
	m.no_depth_test = true
	_mesh_node.material_override = m
	_draw_root.add_child(_mesh_node)
	_labels = Node3D.new()
	_draw_root.add_child(_labels)


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed(&"debug_menu"):
		_menu.visible = not _menu.visible
		var ui: Node = world.get(&"ui")
		if _menu.visible:
			ui.call(&"push_modal", &"debug_menu")
			_refresh_seed()
		else:
			ui.call(&"pop_modal", &"debug_menu")
	elif event.is_action_pressed(&"debug_freecam"):
		_toggle_free_cam()
	elif event.is_action_pressed(&"debug_ai"):
		DebugTools.toggle(&"ai_overlay")
	elif event.is_action_pressed(&"debug_perf"):
		_perf.visible = DebugTools.toggle(&"perf_overlay")
	elif event.is_action_pressed(&"debug_routes"):
		DebugTools.toggle(&"poi_routes")
	elif event.is_action_pressed(&"debug_structure"):
		DebugTools.toggle(&"structure_view")
	elif _cam != null and event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		var mm: InputEventMouseMotion = event
		_cam.rotation.y -= mm.relative.x * 0.003
		_cam_pitch = clampf(_cam_pitch - mm.relative.y * 0.003, -1.5, 1.5)
		_cam.rotation.x = _cam_pitch


# --- Menu ------------------------------------------------------------------------------------

func _build_menu() -> void:
	_menu = PanelContainer.new()
	_menu.position = Vector2(20, 20)
	_menu.visible = false
	add_child(_menu)
	var scroll := ScrollContainer.new()
	scroll.custom_minimum_size = Vector2(460, 640)
	_menu.add_child(scroll)
	var v := VBoxContainer.new()
	v.add_theme_constant_override(&"separation", 4)
	scroll.add_child(v)
	_section(v, "Spawn (8 m ahead)")
	_row(v, [["Hollow", _spawn.bind(&"hollow")], ["Lurcher", _spawn.bind(&"lurcher")], ["Keener", _spawn.bind(&"keener")], ["Dragger", _spawn.bind(&"dragger")]])
	_row(v, [["Pack of 6", _spawn_pack], ["Kill nearby", _kill_nearby]])
	_section(v, "Give")
	_row(v, [["Axe + hammer", _give.bind({"stone_axe": 1, "claw_hammer": 1})], ["4 logs", _give.bind({"log": 2})],
		["Building kit", _give.bind({"stick": 20, "stone": 12, "leaf_bundle": 12, "cordage": 6, "nails": 30, "plant_fiber": 10})]])
	_row(v, [["Revolver", _give.bind({"revolver": 1, "ammo_38": 24})], ["Food + water", _give.bind({"ration_bar": 4, "water_bottle_clean": 3})], ["Medkit", _give.bind({"cloth_bandage": 4})]])
	_section(v, "Time")
	_row(v, [["+1 h", _advance.bind(60.0)], ["+6 h", _advance.bind(360.0)], ["Dawn", _set_hour.bind(6.0)], ["Noon", _set_hour.bind(12.0)], ["Dusk", _set_hour.bind(19.5)], ["Midnight", _set_hour.bind(0.0)]])
	_row(v, [["Start the Hum", _start_hum], ["End the Hum", _end_hum], ["Time x10", _time_scale.bind(10.0)], ["Time x1", _time_scale.bind(1.0)]])
	_section(v, "Weather")
	var wr: Array = []
	for wd: WeatherDef in Content.all(&"weather"):
		wr.append([wd.display_name, _weather.bind(wd.id)])
	_row(v, wr)
	_section(v, "Teleport")
	var tr: Array = []
	for t: Array in TELEPORTS:
		tr.append([t[0], _teleport.bind(t[1])])
	_row(v, tr.slice(0, 3))
	_row(v, tr.slice(3))
	_section(v, "Toggles")
	_row(v, [["God mode", _flag.bind(&"god_mode")], ["Invisible", _flag.bind(&"invisible")], ["No hunger", _flag.bind(&"no_hunger")]])
	_row(v, [["AI overlay (F3)", _flag.bind(&"ai_overlay")], ["Perf (F4)", func() -> void: _perf.visible = DebugTools.toggle(&"perf_overlay")],
		["Routes (F6)", _flag.bind(&"poi_routes")], ["Structure (F7)", _flag.bind(&"structure_view")]])
	_row(v, [["Quicksave", func() -> void: Game.save_game("quicksave")], ["Screenshot", _screenshot]])
	_section(v, "World")
	_seed_label = Label.new()
	_seed_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_seed_label.custom_minimum_size = Vector2(440, 0)
	v.add_child(_seed_label)


func _section(v: VBoxContainer, text: String) -> void:
	var l := Label.new()
	l.text = text
	l.add_theme_color_override(&"font_color", Color(1.0, 0.85, 0.5))
	v.add_child(l)


func _row(v: VBoxContainer, buttons: Array) -> void:
	var h := HFlowContainer.new()
	for b: Array in buttons:
		var btn := Button.new()
		btn.text = b[0]
		btn.pressed.connect(b[1])
		h.add_child(btn)
	v.add_child(h)


func _player() -> Player:
	return world.get(&"player")


func _ahead(d: float) -> Vector3:
	var p: Player = _player()
	var fwd: Vector3 = -p.global_transform.basis.z
	var pos: Vector3 = p.global_position + Vector3(fwd.x, 0, fwd.z).normalized() * d
	pos.y = world.call(&"height_at", pos.x, pos.z) + 0.3
	return pos


func _spawn(id: StringName) -> void:
	var ai: Node = world.get(&"ai")
	if ai != null:
		ai.call(&"spawn", id, _ahead(8.0), {"target": _player().global_position})


func _spawn_pack() -> void:
	for i: int in 6:
		_spawn(&"hollow" if i % 3 != 0 else &"lurcher")


func _kill_nearby() -> void:
	var ai: Node = world.get(&"ai")
	if ai == null:
		return
	for e: Enemy in ai.call(&"enemies_in_radius", _player().global_position, 60.0):
		if e.is_alive():
			var info := DamageInfo.make(9999.0, &"blunt", &"debug", &"")
			info.hit_pos = e.global_position + Vector3.UP
			e.take_damage(info)


func _give(items: Dictionary) -> void:
	var p: PlayerState = Game.local_player()
	for k: Variant in items.keys():
		p.inventory.add_item(StringName(str(k)), int(items[k]))
	Events.inventory_changed.emit(p.id)


func _advance(minutes: float) -> void:
	(world.get(&"clock_driver") as WorldClockDriver).advance(minutes)


func _set_hour(h: float) -> void:
	var c: WorldClock = Game.session.clock
	var target: float = h if h > c.hour_f() else h + 24.0
	_advance((target - c.hour_f()) * 60.0)


func _start_hum() -> void:
	var c: WorldClock = Game.session.clock
	var d: int = c.next_horde_day(c.day())
	if d != c.day():
		c.set_time(d, 21.9)
	elif c.hour_f() < 21.9:
		c.set_time(d, 21.9)
	_advance(10.0)


func _end_hum() -> void:
	var c: WorldClock = Game.session.clock
	if c.is_horde_active():
		var d: int = c.day() + (1 if c.hour_f() >= 12.0 else 0)
		c.set_time(d, 3.95)
		_advance(5.0)


func _time_scale(s: float) -> void:
	Game.session.clock.time_scale = s


func _weather(id: StringName) -> void:
	Game.session.weather.force(id)
	Events.weather_changed.emit(id)


func _teleport(p: Vector3) -> void:
	var pl: Player = _player()
	var y: float = world.call(&"height_at", p.x, p.z)
	pl.global_position = Vector3(p.x, y + 1.0, p.z)
	pl.velocity = Vector3.ZERO
	(world.get(&"terrain") as TerrainManager).update_streaming(pl.global_position, true)


func _flag(f: StringName) -> void:
	var on: bool = DebugTools.toggle(f)
	if f == &"god_mode" and _player() != null:
		_player().god_mode = on
	Events.player_status_message.emit("%s: %s" % [f, "on" if on else "off"], &"info")


func _screenshot() -> void:
	var path: String = "user://screenshot_%d.png" % Time.get_unix_time_from_system()
	get_viewport().get_texture().get_image().save_png(path)
	Events.player_status_message.emit("Saved %s" % ProjectSettings.globalize_path(path), &"info")


func _refresh_seed() -> void:
	var p: Vector3 = _player().global_position
	var t: TerrainManager = world.get(&"terrain")
	var rt: RegionTerrain = t.region_terrain_at(p.x, p.z)
	var lines: PackedStringArray = ["world '%s' seed %d  mode %s" % [Game.session.world_id, Game.session.world_seed, Game.session.game_mode]]
	lines.append("pos (%.1f, %.1f, %.1f)" % [p.x, p.y, p.z])
	if rt != null:
		lines.append("region %s  biome %s  surface %s  veg %.2f" % [rt.region_id, rt.biome_at(p.x, p.z), rt.surface_at(p.x, p.z), rt.veg_at(p.x, p.z)])
		lines.append("height hash %s  placements %d  water bodies %d  roads %d" % [rt.height.content_hash().substr(0, 12), rt.placements.size(), rt.water.size(), rt.roads.size()])
	var c: WorldClock = Game.session.clock
	lines.append("day %d %02d:%02d %s  next Hum day %d  heat here %.1f" % [c.day(), c.hour(), c.minute(), c.season(), c.next_horde_day(), Game.session.heat.heat_at(p)])
	_seed_label.text = "\n".join(lines)


# --- Free camera ---------------------------------------------------------------------------------

func _toggle_free_cam() -> void:
	var p: Player = _player()
	if _cam == null:
		_cam = Camera3D.new()
		_cam.far = 3000.0
		world.add_child(_cam)
		_cam.global_transform = p.camera.global_transform
		_cam_pitch = _cam.rotation.x
		_cam.make_current()
		p.input_enabled = false
		p.look_enabled = false
		DebugTools.set_flag(&"free_cam", true)
	else:
		_cam.queue_free()
		_cam = null
		p.camera.make_current()
		p.input_enabled = true
		p.look_enabled = true
		DebugTools.set_flag(&"free_cam", false)


func _process(delta: float) -> void:
	if world == null or _player() == null:
		return
	if _cam != null:
		var dir := Vector3.ZERO
		var b: Basis = _cam.global_transform.basis
		if Input.is_action_pressed(&"move_forward"):
			dir -= b.z
		if Input.is_action_pressed(&"move_back"):
			dir += b.z
		if Input.is_action_pressed(&"move_left"):
			dir -= b.x
		if Input.is_action_pressed(&"move_right"):
			dir += b.x
		if Input.is_key_pressed(KEY_E):
			dir += Vector3.UP
		if Input.is_key_pressed(KEY_Q):
			dir -= Vector3.UP
		_cam.global_position += dir.normalized() * delta * (40.0 if Input.is_action_pressed(&"sprint") else 10.0)
		(world.get(&"terrain") as TerrainManager).update_streaming(_cam.global_position, false)
	_t += delta
	if _perf.visible:
		_update_perf()
	if _t < 0.2:
		return
	_t = 0.0
	_mesh.clear_surfaces()
	for c: Node in _labels.get_children():
		c.queue_free()
	var any: bool = false
	if DebugTools.is_on(&"ai_overlay"):
		any = _draw_ai() or any
	if DebugTools.is_on(&"poi_routes"):
		any = _draw_routes() or any
	if DebugTools.is_on(&"structure_view"):
		_draw_structures()


func _update_perf() -> void:
	var fps: float = Engine.get_frames_per_second()
	var dc: int = RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME)
	var prim: int = RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME)
	var objs: int = RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_OBJECTS_IN_FRAME)
	var vmem: float = RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_VIDEO_MEM_USED) / 1048576.0
	var ai: Node = world.get(&"ai")
	_perf.text = "%.0f FPS  %.2f ms  (target 60 / 16.7 ms)\ndraw calls %d  primitives %.1fk  objects %d\nvideo mem %.0f MB  static mem %.0f MB  nodes %d\nphysics %.2f ms  process %.2f ms\nHollowed alive %d  graphics preset %s" % [
		fps, 1000.0 / maxf(fps, 1.0), dc, prim / 1000.0, objs, vmem, OS.get_static_memory_usage() / 1048576.0,
		get_tree().get_node_count(), Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS) * 1000.0,
		Performance.get_monitor(Performance.TIME_PROCESS) * 1000.0, int(ai.call(&"alive_count")) if ai != null else 0, Settings.graphics_preset]


func _line(a: Vector3, b: Vector3, c: Color) -> void:
	_mesh.surface_set_color(c)
	_mesh.surface_add_vertex(a)
	_mesh.surface_set_color(c)
	_mesh.surface_add_vertex(b)


func _label(pos: Vector3, text: String, c: Color = Color.WHITE, size: int = 48) -> void:
	var l := Label3D.new()
	l.text = text
	l.modulate = c
	l.font_size = size
	l.pixel_size = 0.004
	l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	l.no_depth_test = true
	l.position = pos
	_labels.add_child(l)


func _circle(c: Vector3, r: float, col: Color) -> void:
	var prev: Vector3 = c + Vector3(r, 0.2, 0)
	for i: int in range(1, 25):
		var a: float = TAU * float(i) / 24.0
		var p: Vector3 = c + Vector3(cos(a) * r, 0.2, sin(a) * r)
		_line(prev, p, col)
		prev = p


func _draw_ai() -> bool:
	var ai: Node = world.get(&"ai")
	if ai == null:
		return false
	var p: Vector3 = _player().global_position
	_mesh.surface_begin(Mesh.PRIMITIVE_LINES)
	var n: int = 0
	for e: Enemy in ai.call(&"enemies_in_radius", p, 80.0):
		var st: String = Enemy.State.keys()[e.state]
		var col: Color = {"CHASE": Color.RED, "ATTACK": Color.RED, "BREAK": Color.ORANGE, "INVESTIGATE": Color.YELLOW, "SLEEP": Color(0.5, 0.5, 1.0), "HORDE": Color.MAGENTA}.get(st, Color(0.7, 0.9, 0.7))
		_label(e.global_position + Vector3.UP * 2.2, "%s %s\nhp %d aw %.2f" % [e.def.id, st, int(e.health), e.awareness], col, 40)
		if e.state != Enemy.State.SLEEP and e.state != Enemy.State.DEAD:
			_line(e.global_position + Vector3.UP, e.target_pos + Vector3.UP * 0.5, col)
		n += 1
	var hum: HumDirector = ai.get(&"hum")
	if hum != null and hum.flow != null and hum.flow.ready:
		for dz: int in range(-10, 11):
			for dx: int in range(-10, 11):
				var q: Vector3 = hum.base + Vector3(dx * 4.0, 0, dz * 4.0)
				q.y = world.call(&"height_at", q.x, q.z) + 0.4
				var d: Vector3 = hum.flow.direction_at(q)
				if d != Vector3.ZERO:
					_line(q, q + d * 1.5, Color(1, 0.3, 1, 0.8))
	var heat: HeatMap = Game.session.heat
	for c: Vector2i in heat.cells:
		var cc: Vector3 = heat.cell_center(c)
		if cc.distance_to(Vector3(p.x, 0, p.z)) < 300.0:
			cc.y = world.call(&"height_at", cc.x, cc.z)
			_circle(cc, 6.0 + float(heat.cells[c]) * 0.2, Color(1, 0.5, 0.1))
	_mesh.surface_end()
	return n > 0


func _draw_routes() -> bool:
	var pois: Node = world.get(&"pois")
	if pois == null:
		return false
	var p: Vector3 = _player().global_position
	_mesh.surface_begin(Mesh.PRIMITIVE_LINES)
	for inst: PoiInstance in (pois.get(&"instances") as Dictionary).values():
		if inst.global_position.distance_to(p) > 120.0:
			continue
		var v: PoiValidator = PoiValidator.validate(inst.layout.def)
		var l: PoiLayout = inst.layout
		for path: Array in v.paths:
			var prev: Variant = null
			for node: Variant in path:
				if not node is Array:
					continue
				var wp: Vector3 = inst.to_global(l.cell_center(node[0], node[1]) + Vector3.UP * 0.3)
				if prev != null:
					_line(prev, wp, Color(0.3, 1.0, 0.4))
				prev = wp
		for i: int in l.route.size():
			var wpt: Dictionary = l.route[i]
			_label(inst.to_global(l.local_pos(wpt["level"], wpt["pos"]) + Vector3.UP * 1.6), "%d %s" % [i, wpt.get("label", "")], Color(0.4, 1.0, 0.5), 36)
		for s: Dictionary in l.sleepers:
			_label(inst.to_global(l.local_pos(s["level"], s["pos"]) + Vector3.UP * 1.2), "zz %s" % s.get("enemy", "hollow"), Color(0.6, 0.6, 1.0), 32)
		if not l.loot_room.is_empty():
			for c: Vector2i in l.room_cells(int(l.loot_room.get("level", 0))):
				if l.room_at(int(l.loot_room.get("level", 0)), c) == str(l.loot_room.get("room", "")):
					var cc: Vector3 = inst.to_global(l.cell_center(int(l.loot_room.get("level", 0)), c) + Vector3.UP * 0.1)
					_line(cc - Vector3(0.3, 0, 0), cc + Vector3(0.3, 0, 0), Color(1, 0.85, 0.2))
		for e: String in v.errors:
			_label(inst.global_position + Vector3.UP * 6.0, e, Color.RED, 32)
	_mesh.surface_end()
	return true


func _draw_structures() -> void:
	var b: Node = world.get(&"building")
	if b == null:
		return
	for piece: StructurePiece in b.call(&"pieces_in_radius", _player().global_position, 40.0):
		var s: float = float(b.call(&"stability_of", piece.piece_id))
		var col: Color = Color(1.0 - s, s, 0.2)
		_label(piece.global_position + Vector3.UP * 0.5, "%.0f%%  %d/%d" % [s * 100.0, int(piece.hp), int(piece.max_hp())], col, 36)
