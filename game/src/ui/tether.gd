class_name Tether
extends Node3D
## The tether (wrist tracker, T): a rugged Remand Program wrist unit raised into view without
## stopping you. Its screen (a SubViewport rendered onto the device) shows day/time/weather,
## vitals and conditions, your level / XP / gamestage, the Hum countdown and forecast
## (HumDirector's plan for the next Hum), every supply drop (when the world setting marks them) and a
## minimap of the region you are in, captioned with the world's name and your sector (the region's
## map cell): you, where you wake (your bed, or the drop site until you have one), supply drops and
## the buildings (grey; orange once you've been inside, green once cleared).

const HIDDEN := Vector3(-0.2, -0.42, -0.34)
const RAISED := Vector3(-0.085, -0.075, -0.3)
const SCREEN := Vector2i(640, 400)
const MAP_PX: int = 256
## Characters of the 14 px caption that fit beside the map's left edge on the screen.
const CAPTION_CHARS: int = 32
const WAKE_COLOR := Color(0.95, 0.85, 0.4)

var raised: bool = false
var _t: float = 0.0
var _vp: SubViewport
var _root: Control
var _time: Label
var _vitals: Label
var _status: Label
var _record: Label
## Every supply drop on its own line (ADR-0023); the Hum forecast moves down below them.
var _drops: Label
var _directives: Label
var _hum: Label
var _map: TextureRect
var _caption: Label
var _map_region: String = ""
## The region map is shaded on a worker thread (65k height samples hitched the frame the
## tether opened in a new region); the texture is swapped in when it is done.
var _map_task: int = -1
var _map_img: Image = null
var _map_pending: String = ""
var _markers: Control
var _refresh_t: float = 0.0
## The UI shows on the unit bolted to the first-person arms' left wrist (ADR-0029), raised by the
## viewmodel; the floating device is only built when there are no arms.
var _on_arms: bool = false
var _vm: ViewModel = null


func _ready() -> void:
	position = HIDDEN
	visible = false
	_vp = SubViewport.new()
	_vp.size = SCREEN
	_vp.transparent_bg = false
	_vp.render_target_update_mode = SubViewport.UPDATE_DISABLED
	add_child(_vp)
	_build_screen()
	var vm: ViewModel = get_parent().get_node_or_null(^"ViewModel") as ViewModel
	if vm != null and vm.attach_tether_screen(_vp.get_texture()):
		_on_arms = true
		_vm = vm
		position = Vector3.ZERO
		_vp.render_target_update_mode = SubViewport.UPDATE_ONCE
		_refresh()
		return
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
	_record = _lcd_label(Vector2(16, 230), 16)
	_drops = _lcd_label(Vector2(16, 254), 13)
	_hum = _lcd_label(Vector2(16, 290), 16)
	_hum.size = Vector2(340, 100)
	_hum.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	# The full map (WorldMap) is a key away: say which.
	var hint: Label = _lcd_label(Vector2(370, 38), 13)
	hint.text = "[%s] FULL MAP" % PlayerInteraction.key_label(&"map")
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
	_caption = _lcd_label(Vector2(370, 322), 14)
	_caption.size = Vector2(SCREEN.x - 370, 20)
	_caption.clip_text = true
	_directives = _lcd_label(Vector2(370, 342), 13)
	_directives.size = Vector2(262, 56)
	_directives.clip_text = true


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
		Audio.play_2d(&"ui/tether_beep", UiStyle.level("tether_beep", -10.0))
	elif _on_arms:
		_vp.render_target_update_mode = SubViewport.UPDATE_ONCE


func _process(delta: float) -> void:
	if _on_arms:
		# A swing or the guard lowers the wrist on its own: follow it, so T raises it again.
		if raised and is_instance_valid(_vm) and not _vm.tether_raised():
			raised = false
		# Raised: live. Lowered, the screen still glows dimly on the wrist: a fresh frame every 2 s.
		_refresh_t += delta
		if raised and _refresh_t > 0.5 or _refresh_t > 2.0:
			_refresh_t = 0.0
			_refresh()
			_vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS if raised else SubViewport.UPDATE_ONCE
		return
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
	_record.text = _record_text(p)
	_drops.text = _drops_text()
	_hum.position.y = maxf(290.0, 254.0 + 17.0 * float(_drops.text.count("\n") + 1) + 6.0) if _drops.text != "" else 290.0
	_directives.text = _directives_text(p)
	_hum.text = _hum_text()
	var w: Node = Game.world
	if w != null and w.get(&"terrain") != null and w.get(&"player") != null:
		_caption.text = map_caption((w.terrain as TerrainManager).world, (w.player as Node3D).global_position)
	_ensure_map()
	_markers.queue_redraw()


func _bar(f: float) -> String:
	var n: int = int(round(clampf(f, 0.0, 1.0) * 10.0))
	# Block glyphs the UI font (IBM Plex Mono) has; ▮/▯ rendered as empty boxes.
	return "█".repeat(n) + "░".repeat(10 - n)


func _record_text(p: PlayerState) -> String:
	var pr: Progression = p.progression
	var line: String = "LV %d  XP %d/%d  GS %d" % [pr.level, pr.xp, pr.xp_to_next(), Game.session.gamestage(p)]
	if pr.skill_points > 0:
		line += "  +%d PT%s" % [pr.skill_points, "" if pr.skill_points == 1 else "S"]
	return line


## Every supply drop: distance, compass sector and whether it is still coming down, down or
## searched, one to a line; past four drops they pair up on a line in short form (eight fit).
func _drops_text() -> String:
	var w: Node = Game.world
	var drops: Node = w.get(&"supply_drops") if w != null else null
	if drops == null or w.player == null or not drops.has_method(&"entries"):
		return ""
	return drops_lines(drops.call(&"entries"), (w.player as Node3D).global_position)


static func drops_lines(list: Array, pp: Vector3) -> String:
	var items: PackedStringArray = []
	var short: bool = list.size() > 4
	for e: Dictionary in list:
		var at: Vector3 = e["pos"]
		var d: float = Vector2(at.x - pp.x, at.z - pp.z).length()
		var dist: String = ("%d m" % int(d)) if d < 1000.0 else ("%.1f km" % (d / 1000.0))
		var sector: String = HordeMemory.SECTOR_NAMES[HordeMemory.sector_of(pp, at)]
		var state: String = str(e["state"]).to_upper()
		items.append(("%s %s %s" % [dist, sector, state.substr(0, 3)]) if short else ("DROP  %-8s %-3s %s" % [dist, sector, state]))
	if not short:
		return "\n".join(items)
	var lines: PackedStringArray = []
	for i: int in range(0, items.size(), 2):
		if lines.size() == 3 and items.size() > 8:
			lines.append("DROPS +%d MORE ON THE MAP" % (items.size() - 6))
			break
		lines.append(("DROPS " if i == 0 else "      ") + "  ·  ".join(items.slice(i, i + 2)))
	return "\n".join(lines)


## The map's caption: the world's name and the sector (map cell of the region) at `pos`,
## "HOLLOWMERE VALLEY  ·  SECTOR D6". A long name is cut short so the sector always shows.
static func map_caption(wd: WorldDef, pos: Vector3) -> String:
	if wd == null:
		return ""
	var name_: String = wd.display_name.to_upper()
	var cell: String = str((wd.regions.get(wd.region_at(pos.x, pos.z), {}) as Dictionary).get("cell", ""))
	if cell == "":
		return name_.left(CAPTION_CHARS)
	var sector: String = "  ·  SECTOR %s" % cell
	if name_.length() + sector.length() > CAPTION_CHARS:
		name_ = name_.left(maxi(1, CAPTION_CHARS - sector.length() - 1)).strip_edges() + "…"
	return name_ + sector


## The open chapter's next two Program directives with their progress.
func _directives_text(p: PlayerState) -> String:
	var dr: Directives = p.directives
	if dr.all_done():
		return "DIRECTIVES  all complete"
	var lines: PackedStringArray = ["DIRECTIVES · %s" % Directives.chapter_name(dr.chapter).to_upper()]
	# With a Waystation contract open, it takes the second line (ADR-0039).
	var w: Node = Game.world
	var contracts: PackedStringArray = w.get(&"traders").call(&"lines") if w != null and w.get(&"traders") != null else PackedStringArray()
	for d: DirectiveDef in dr.open().slice(0, 1 if not contracts.is_empty() else 2):
		lines.append("> %s  %s" % [dr.label(d), d.goal_text(dr.count_of(d.id))])
	if not contracts.is_empty():
		lines.append("CONTRACT  %s" % contracts[0])
	return "\n".join(lines)


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
	if _map_task != -1:
		if not WorkerThreadPool.is_task_completed(_map_task):
			return
		WorkerThreadPool.wait_for_task_completion(_map_task)
		_map_task = -1
		if _map_img != null:
			_map.texture = ImageTexture.create_from_image(_map_img)
			_map_region = _map_pending
		_map_img = null
	var pp: Vector3 = (w.player as Node3D).global_position
	var rt: RegionTerrain = (w.terrain as TerrainManager).region_terrain_at(pp.x, pp.z)
	if rt == null or rt.region_id == _map_region:
		return
	_map_pending = rt.region_id
	# The worker shades a copy of the heights. Digging writes the live array in place on the main
	# thread, and a worker reading it meanwhile can crash (TD-104; TerrainManager's readers take its
	# lock instead). The copy is one region's heights, once per region the player enters.
	var hf := HeightField.new()
	hf.origin = rt.height.origin
	hf.spacing = rt.height.spacing
	hf.width = rt.height.width
	hf.depth = rt.height.depth
	hf.heights = rt.height.heights.duplicate()
	_map_task = WorkerThreadPool.add_task(_shade_map.bind(rt, hf), false, "tether map")


func _exit_tree() -> void:
	if _map_task != -1:
		WorkerThreadPool.wait_for_task_completion(_map_task)
		_map_task = -1


## Worker thread: reads `hf` (a copy of the region's heights) and the region's vegetation mask,
## water and roads (written only when the region is composed or loaded); touches no nodes.
func _shade_map(rt: RegionTerrain, hf: HeightField) -> void:
	var img := Image.create(MAP_PX, MAP_PX, false, Image.FORMAT_RGB8)
	var step: float = rt.rect.size.x / float(MAP_PX)
	for y: int in MAP_PX:
		for x: int in MAP_PX:
			var wx: float = rt.rect.position.x + (x + 0.5) * step
			var wz: float = rt.rect.position.y + (y + 0.5) * step
			var h: float = hf.sample(wx, wz)
			var hx: float = hf.sample(wx + step, wz) - h
			var hz: float = hf.sample(wx, wz + step) - h
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
	_map_img = img


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
	var lim := Rect2(Vector2(6, 6), Vector2(MAP_PX - 12, MAP_PX - 12))
	# Where you wake: your bed (a dot), else the drop site (a ring; spawn_point holds it from the
	# start). Off the map edge: pinned to the border in its direction, like the drops.
	if p.has_spawn_point:
		_markers.draw_circle(_to_map(rt, p.spawn_point).clamp(lim.position, lim.end), 4.0, WAKE_COLOR)
	elif p.spawn_point != Vector3.ZERO:
		_markers.draw_arc(_to_map(rt, p.spawn_point).clamp(lim.position, lim.end), 4.5, 0.0, TAU, 16, WAKE_COLOR, 1.5)
	var pois: Node = w.get(&"pois")
	if pois != null and pois.has_method(&"markers"):
		# Every building, built or not (a streamed world builds only the nearby ones, ADR-0038).
		for m: Dictionary in (pois.call(&"markers") as Array):
			var col := Color(0.6, 0.6, 0.6)
			if bool(m["cleared"]):
				col = Color(0.4, 0.9, 0.5)
			elif bool(m["visited"]):
				col = Color(0.9, 0.7, 0.4)
			var mp: Vector2 = _to_map(rt, m["pos"])
			_markers.draw_rect(Rect2(mp - Vector2(3, 3), Vector2(6, 6)), col)
	var drops: Node = w.get(&"supply_drops")
	if drops != null:
		for at: Vector3 in (drops.call(&"markers") as Array[Vector3]):
			# Off the map edge: pinned to the border in its direction.
			var mp: Vector2 = _to_map(rt, at).clamp(lim.position, lim.end)
			_markers.draw_colored_polygon(PackedVector2Array([mp + Vector2(0, -6), mp + Vector2(6, 0), mp + Vector2(0, 6), mp + Vector2(-6, 0)]), Color(1.0, 0.35, 0.2))
	# Waystations (a yellow post square) and your contracts (a ring; filled once done, to report
	# in). Off the map edge: pinned to the border in their direction (ADR-0039).
	var traders: Node = w.get(&"traders")
	if traders != null and traders.has_method(&"markers"):
		for m: Dictionary in (traders.call(&"markers") as Array[Dictionary]):
			var mp: Vector2 = _to_map(rt, m["pos"]).clamp(lim.position, lim.end)
			if str(m["kind"]) == "trader":
				_markers.draw_rect(Rect2(mp - Vector2(5, 5), Vector2(10, 10)), Color(1.0, 0.82, 0.2))
				_markers.draw_rect(Rect2(mp - Vector2(5, 5), Vector2(10, 10)), Color(0.1, 0.1, 0.1), false, 1.5)
			elif bool(m["ready"]):
				_markers.draw_circle(mp, 5.0, Color(0.5, 1.0, 0.55))
			else:
				_markers.draw_arc(mp, 5.5, 0.0, TAU, 18, Color(1.0, 0.85, 0.3), 2.0)
	# The distress call (the first days' tutorial): a pulsing ring, pinned to the edge off the map.
	var d: Dictionary = FieldManual.live_distress()
	if not d.is_empty():
		var dp: Vector2 = _to_map(rt, d.get("position", Vector3.ZERO)).clamp(lim.position, lim.end)
		var pulse: float = 0.5 + 0.5 * sin(Time.get_ticks_msec() * 0.006)
		_markers.draw_arc(dp, 5.0 + 3.0 * pulse, 0.0, TAU, 20, Color(1.0, 0.3, 0.25), 2.0)
		_markers.draw_circle(dp, 2.5, Color(1.0, 0.3, 0.25))
	var me: Vector2 = _to_map(rt, pl.global_position)
	var yaw: float = pl.global_rotation.y
	var fwd := Vector2(-sin(yaw), -cos(yaw))
	var right := Vector2(-fwd.y, fwd.x)
	_markers.draw_colored_polygon(PackedVector2Array([me + fwd * 8.0, me - fwd * 5.0 + right * 5.0, me - fwd * 5.0 - right * 5.0]), Color(1.0, 0.95, 0.9))
