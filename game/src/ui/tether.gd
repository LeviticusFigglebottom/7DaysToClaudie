class_name Tether
extends Node3D
## The tether (wrist tracker, T): a rugged Remand Program wrist unit raised into view without
## stopping you. Its screen (a SubViewport rendered onto the device) shows day/time/weather,
## vitals and conditions, the Hum countdown and forecast (HumDirector's plan for the next Hum),
## and a minimap of the region with you, your bed, your base and the places you've been.

const HIDDEN := Vector3(-0.2, -0.42, -0.34)
const RAISED := Vector3(-0.085, -0.075, -0.3)
const SCREEN := Vector2i(640, 400)
const MAP_PX: int = 256

var raised: bool = false
var _t: float = 0.0
var _vp: SubViewport
var _root: Control
var _time: Label
var _vitals: Label
var _status: Label
var _hum: Label
var _map: TextureRect
var _map_region: String = ""
var _markers: Control
var _refresh_t: float = 0.0


func _ready() -> void:
	position = HIDDEN
	visible = false
	_vp = SubViewport.new()
	_vp.size = SCREEN
	_vp.transparent_bg = false
	_vp.render_target_update_mode = SubViewport.UPDATE_DISABLED
	add_child(_vp)
	_build_screen()
	var shell := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size = Vector3(0.118, 0.082, 0.02)
	var shell_mat := StandardMaterial3D.new()
	shell_mat.albedo_color = Color(0.13, 0.14, 0.13)
	shell_mat.roughness = 0.75
	box.material = shell_mat
	shell.mesh = box
	shell.position = Vector3(0, 0, -0.012)
	add_child(shell)
	# Screen sits in the bezel's cut-out (x 0.135-0.865, y 0.12-0.80 of the bezel texture).
	var screen := MeshInstance3D.new()
	var q := QuadMesh.new()
	q.size = Vector2(0.12 * 0.73, 0.08 * 0.68)
	var sm := StandardMaterial3D.new()
	sm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	sm.albedo_texture = _vp.get_texture()
	q.material = sm
	screen.mesh = q
	screen.position = Vector3(0, 0.08 * (0.5 - 0.46), -0.0005)
	add_child(screen)
	var bezel := MeshInstance3D.new()
	var bq := QuadMesh.new()
	bq.size = Vector2(0.12, 0.08)
	var bm := StandardMaterial3D.new()
	var bez: String = "res://assets/generated/textures/ui_tether_bezel.png"
	if ResourceLoader.exists(bez):
		bm.albedo_texture = load(bez)
		bm.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
		bm.alpha_scissor_threshold = 0.5
	else:
		bm.albedo_color = Color(0.16, 0.17, 0.16)
		bm.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		bm.albedo_color.a = 0.0
	bm.roughness = 0.7
	bq.material = bm
	bezel.mesh = bq
	bezel.position = Vector3(0, 0, 0.0005)
	add_child(bezel)
	rotation = Vector3(deg_to_rad(8), deg_to_rad(18), deg_to_rad(-6))


func _build_screen() -> void:
	_root = ColorRect.new()
	(_root as ColorRect).color = Color(0.04, 0.07, 0.05)
	_root.size = Vector2(SCREEN)
	_vp.add_child(_root)
	var lcd: String = "res://assets/generated/textures/ui_tether_screen.png"
	if ResourceLoader.exists(lcd):
		var bg := TextureRect.new()
		bg.texture = load(lcd)
		bg.size = Vector2(SCREEN)
		bg.stretch_mode = TextureRect.STRETCH_SCALE
		bg.modulate = Color(1, 1, 1, 0.5)
		_root.add_child(bg)
	_time = _lcd_label(Vector2(16, 10), 24)
	_vitals = _lcd_label(Vector2(16, 52), 18)
	_status = _lcd_label(Vector2(16, 200), 16)
	_hum = _lcd_label(Vector2(16, 290), 16)
	_hum.size = Vector2(340, 100)
	_hum.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_map = TextureRect.new()
	_map.position = Vector2(370, 60)
	_map.size = Vector2(256, 256)
	_map.stretch_mode = TextureRect.STRETCH_SCALE
	_root.add_child(_map)
	_markers = Control.new()
	_markers.position = _map.position
	_markers.size = _map.size
	_markers.draw.connect(_draw_markers)
	_root.add_child(_markers)
	var cap := _lcd_label(Vector2(370, 322), 14)
	cap.text = "LARCH HOLLOW  ·  CORDON SECTOR D6"


func _lcd_label(pos: Vector2, size: int) -> Label:
	var l := Label.new()
	l.position = pos
	l.add_theme_font_size_override(&"font_size", size)
	l.add_theme_color_override(&"font_color", Color(0.6, 0.95, 0.65))
	_root.add_child(l)
	return l


func toggle() -> void:
	raised = not raised
	if raised:
		visible = true
		_vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
		_refresh()
		Audio.play_2d(&"ui/tether_beep", -10.0)


func _process(delta: float) -> void:
	_t = clampf(_t + (delta if raised else -delta) * 4.0, 0.0, 1.0)
	var e: float = _t * _t * (3.0 - 2.0 * _t)
	position = HIDDEN.lerp(RAISED, e)
	if _t <= 0.0 and not raised:
		visible = false
		_vp.render_target_update_mode = SubViewport.UPDATE_DISABLED
		return
	_refresh_t += delta
	if _refresh_t > 0.5:
		_refresh_t = 0.0
		_refresh()


func _refresh() -> void:
	var s: GameSession = Game.session
	var p: PlayerState = Game.local_player()
	if s == null or p == null:
		return
	var c: WorldClock = s.clock
	var wp: Dictionary = s.weather.params()
	_time.text = "DAY %d   %02d:%02d   %s   %s" % [c.day(), c.hour(), c.minute(), c.season().to_upper(), str(wp.get("id", "clear")).to_upper().replace("_", " ")]
	var st: SurvivalStats = p.stats
	_vitals.text = "HEALTH   %s %3d\nFOOD     %s %3d\nWATER    %s %3d\nREST     %s %3d\nBODY     %.1f°C" % [
		_bar(st.health / st.max_health), int(st.health), _bar(st.fullness / 100.0), int(st.fullness),
		_bar(st.hydration / 100.0), int(st.hydration), _bar(st.rest / 100.0), int(st.rest), st.body_temp]
	var flags: PackedStringArray = []
	if st.body_temp < 35.8:
		flags.append("COLD")
	elif st.body_temp > 38.6:
		flags.append("OVERHEATING")
	if st.bleeding > 0.0:
		flags.append("BLEEDING")
	if st.infection > 5.0:
		flags.append("INFECTION %d%%" % int(st.infection))
	if st.wetness > 0.3:
		flags.append("WET")
	_status.text = "  ".join(flags) if not flags.is_empty() else "NOMINAL"
	_hum.text = _hum_text()
	_ensure_map()
	_markers.queue_redraw()


func _bar(f: float) -> String:
	var n: int = int(round(clampf(f, 0.0, 1.0) * 10.0))
	return "▮".repeat(n) + "▯".repeat(10 - n)


func _hum_text() -> String:
	var c: WorldClock = Game.session.clock
	if c.is_horde_active():
		return "!! THE HUM !!\nHold until 04:00."
	if not c.hordes_enabled():
		return "THE HUM: none (world setting)."
	var hrs: float = c.hours_until_horde()
	var ai: Node = Game.world.get(&"ai") if Game.world != null else null
	var lines: PackedStringArray = ["NEXT HUM  day %d  (%dh)" % [c.next_horde_day(), int(hrs)]]
	if hrs < 48.0 and ai != null and ai.get(&"hum") != null:
		var f: Dictionary = (ai.get(&"hum") as HumDirector).forecast()
		lines.append("~%d expected." % int(f.get("total", 0)))
		for t: Variant in (f.get("tactics", []) as Array).slice(0, 2):
			lines.append("> " + str(t))
	return "\n".join(lines)


# --- Minimap ------------------------------------------------------------------------------------

func _ensure_map() -> void:
	var w: Node = Game.world
	if w == null or w.player == null:
		return
	var pp: Vector3 = (w.player as Node3D).global_position
	var rt: RegionTerrain = (w.terrain as TerrainManager).region_terrain_at(pp.x, pp.z)
	if rt == null or rt.region_id == _map_region:
		return
	_map_region = rt.region_id
	var img := Image.create(MAP_PX, MAP_PX, false, Image.FORMAT_RGB8)
	var step: float = rt.rect.size.x / float(MAP_PX)
	for y: int in MAP_PX:
		for x: int in MAP_PX:
			var wx: float = rt.rect.position.x + (x + 0.5) * step
			var wz: float = rt.rect.position.y + (y + 0.5) * step
			var h: float = rt.height.sample(wx, wz)
			var hx: float = rt.height.sample(wx + step, wz) - h
			var hz: float = rt.height.sample(wx, wz + step) - h
			var shade: float = clampf(0.55 - (hx + hz) * 0.35 / step, 0.15, 0.95)
			var col := Color(0.12, 0.3, 0.16) * (0.6 + shade * 0.8)
			var veg: float = rt.veg_at(wx, wz)
			if veg < 0.05:
				col = Color(0.35, 0.42, 0.3) * (0.6 + shade * 0.7)
			if int(h) % 10 == 0 and absf(h - round(h)) < 0.4:
				col = col.lightened(0.18)
			img.set_pixel(x, y, col)
	for wb: Dictionary in rt.water:
		if wb.has("polygon"):
			_fill_poly(img, rt, wb["polygon"], Color(0.12, 0.3, 0.42))
	for r: Dictionary in rt.roads:
		var pts: Array = r.get("points", [])
		for i: int in pts.size():
			var a: Array = pts[i]
			var px := Vector2i(int((float(a[0]) - rt.rect.position.x) / step), int((float(a[2] if a.size() > 2 else a[1]) - rt.rect.position.y) / step))
			if px.x >= 0 and px.y >= 0 and px.x < MAP_PX and px.y < MAP_PX:
				img.set_pixel(px.x, px.y, Color(0.75, 0.72, 0.6))
	_map.texture = ImageTexture.create_from_image(img)


func _fill_poly(img: Image, rt: RegionTerrain, poly: Variant, col: Color) -> void:
	var pts := PackedVector2Array()
	var step: float = rt.rect.size.x / float(MAP_PX)
	for p: Variant in poly:
		pts.append(Vector2((float(p[0]) - rt.rect.position.x) / step, (float(p[1]) - rt.rect.position.y) / step))
	if pts.size() < 3:
		return
	var bb := Rect2(pts[0], Vector2.ZERO)
	for p2: Vector2 in pts:
		bb = bb.expand(p2)
	for y: int in range(maxi(0, int(bb.position.y)), mini(MAP_PX, int(bb.end.y) + 1)):
		for x: int in range(maxi(0, int(bb.position.x)), mini(MAP_PX, int(bb.end.x) + 1)):
			if Geometry2D.is_point_in_polygon(Vector2(x, y), pts):
				img.set_pixel(x, y, col)


func _to_map(rt: RegionTerrain, p: Vector3) -> Vector2:
	return Vector2((p.x - rt.rect.position.x) / rt.rect.size.x, (p.z - rt.rect.position.y) / rt.rect.size.y) * float(MAP_PX)


func _draw_markers() -> void:
	var w: Node = Game.world
	if w == null or w.player == null:
		return
	var pl: Node3D = w.player
	var rt: RegionTerrain = (w.terrain as TerrainManager).region_terrain_at(pl.global_position.x, pl.global_position.z)
	if rt == null:
		return
	var p: PlayerState = Game.local_player()
	if p.has_spawn_point:
		_markers.draw_circle(_to_map(rt, p.spawn_point), 4.0, Color(0.95, 0.85, 0.4))
	var pois: Node = w.get(&"pois")
	if pois != null:
		for inst: PoiInstance in (pois.get(&"instances") as Dictionary).values():
			var col := Color(0.6, 0.6, 0.6)
			if bool(inst.state.get("cleared", false)):
				col = Color(0.4, 0.9, 0.5)
			elif bool(inst.state.get("visited", false)):
				col = Color(0.9, 0.7, 0.4)
			var mp: Vector2 = _to_map(rt, inst.global_position)
			_markers.draw_rect(Rect2(mp - Vector2(3, 3), Vector2(6, 6)), col)
	var me: Vector2 = _to_map(rt, pl.global_position)
	var yaw: float = pl.global_rotation.y
	var fwd := Vector2(-sin(yaw), -cos(yaw))
	var right := Vector2(-fwd.y, fwd.x)
	_markers.draw_colored_polygon(PackedVector2Array([me + fwd * 8.0, me - fwd * 5.0 + right * 5.0, me - fwd * 5.0 - right * 5.0]), Color(1.0, 0.95, 0.9))
