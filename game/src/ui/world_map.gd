class_name WorldMap
extends Control
## The full map (TD-014): the whole world on a sheet of survey paper, shaded from the terrain the
## world already holds (every region's coarse 16 m terrain, the built ones' finer heights), with
## forest, water, roads, contour lines every 20 m and the map grid lettered like the regions. Over
## it: you, where you wake, the buildings (grey, orange once entered, green once cleared),
## waystations and supply drops. Wheel zooms on the cursor, drag pans, M or Esc closes.
##
## The sheet is shaded on a worker thread from references taken on the main thread, once per
## world (the terrain it reads isn't edited: digging edits only the 1 m regions' heights, and the
## map samples those through a copy).

const PX_PER_M: float = 1.0 / 8.0
const CONTOUR: float = 20.0
const PAPER := Color(0.88, 0.84, 0.74)
const FOREST := Color(0.5, 0.58, 0.42)
const WATER := Color(0.42, 0.55, 0.62)
const ROAD := Color(0.55, 0.27, 0.14)
const CONTOUR_INK := Color(0.52, 0.38, 0.26)

## How far round the player the map uncovers as you walk, and round the bed or drop site the first
## time (a new game, or a save from before the fog of war).
const SIGHT: float = 90.0
const FIRST_REVEAL: float = 300.0
const FOG := Color(0.8, 0.76, 0.66, 0.93)

static var _cache_key: String = ""
static var _cache_img: Image = null

var _open: bool = false
var _tex: TextureRect
var _sheet: Control
var _markers: Control
var _status: Label
var _task: int = -1
var _img: Image = null
var _rect: Rect2
var _zoom: float = 1.0
var _pan: Vector2 = Vector2.ZERO
var _dragging: bool = false
var _fog: TextureRect
var _explore_t: float = 0.0
## Revealed cells counted at the last fog redraw (redrawn only when it changes).
var _fog_count: int = -1


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	process_mode = Node.PROCESS_MODE_ALWAYS
	visible = false
	theme = UiStyle.paper_theme()
	var dim := ColorRect.new()
	dim.color = Color(0.02, 0.02, 0.02, 0.88)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	dim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(dim)
	_sheet = Control.new()
	_sheet.clip_contents = true
	_sheet.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_sheet)
	_tex = TextureRect.new()
	_tex.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_tex.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
	_tex.stretch_mode = TextureRect.STRETCH_SCALE
	_sheet.add_child(_tex)
	_fog = TextureRect.new()
	_fog.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_fog.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
	_fog.stretch_mode = TextureRect.STRETCH_SCALE
	_sheet.add_child(_fog)
	_markers = Control.new()
	_markers.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_markers.draw.connect(_draw_markers)
	_sheet.add_child(_markers)
	var head := UiStyle.label("", &"HeadingLabel")
	head.name = "Head"
	head.add_theme_color_override(&"font_color", UiStyle.KIT_TEXT)
	head.position = Vector2(48, 24)
	add_child(head)
	_status = UiStyle.label("", &"DimLabel")
	_status.add_theme_color_override(&"font_color", UiStyle.KIT_TEXT_DIM)
	_status.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	_status.offset_left = 48
	_status.offset_top = -48
	add_child(_status)


func _enter_tree() -> void:
	if not Game.has_command(&"map.explore"):
		Game.register_command(&"map.explore", _cmd_explore)


## map.explore {pos: Vector3, radius: float}: uncovers the map round a point for the local player.
func _cmd_explore(args: Dictionary) -> Dictionary:
	var p: PlayerState = Game.local_player()
	if p == null or not (args.get("pos") is Vector3):
		return {"ok": false, "error": "no player or position"}
	var n: int = p.explored.reveal(args["pos"], clampf(float(args.get("radius", SIGHT)), 1.0, 2000.0))
	return {"ok": true, "revealed": n}


func _exit_tree() -> void:
	if Game.has_command(&"map.explore"):
		Game.unregister_command(&"map.explore")
	if _task >= 0:
		WorkerThreadPool.wait_for_task_completion(_task)
		_task = -1


func is_open() -> bool:
	return _open


func toggle() -> void:
	if _open:
		close()
	else:
		open()


func open() -> void:
	var w: Node = Game.world
	if w == null or w.get(&"terrain") == null:
		return
	_open = true
	visible = true
	var tm: TerrainManager = w.terrain
	var world: WorldDef = tm.world
	_rect = world.world_rect()
	(get_node("Head") as Label).text = "%s  ·  SURVEY SHEET" % (world.display_name if world.display_name != "" else "HOLLOWMERE").to_upper()
	_status.text = "Wheel: zoom   ·   drag: pan   ·   M / Esc: close"
	var key: String = "%s|%d" % [world.id, world.regions.size()]
	if _cache_key == key and _cache_img != null:
		_show(_cache_img)
	elif _task < 0:
		_status.text = "Drawing the sheet…"
		var sources: Array = sources_for(tm)
		var roads: Array = world.roads.duplicate()
		var lakes: Array = world.lakes.duplicate()
		var rivers: Array = world.rivers.duplicate()
		var r: Rect2 = _rect
		_task = WorkerThreadPool.add_task(func() -> void:
			_img = shade(r, sources, rivers, lakes, roads), false, "world map")
		_pending_key = key
	_zoom = 1.0
	_pan = Vector2.ZERO
	_fog_count = -1
	var lp: PlayerState = Game.local_player()
	if lp != null:
		_refresh_fog(lp)
	_centre_on_player()
	var ui: Node = get_parent()
	if ui != null and ui.has_method(&"push_modal"):
		ui.call(&"push_modal", &"world_map")


var _pending_key: String = ""


func close() -> void:
	if not _open:
		return
	_open = false
	visible = false
	var ui: Node = get_parent()
	if ui != null and ui.has_method(&"pop_modal"):
		ui.call(&"pop_modal", &"world_map")


## The terrain the sheet is shaded from, taken on the main thread: [RegionTerrain] for every region
## (built regions with a copy of their heights, which digging edits in place).
static func sources_for(tm: TerrainManager) -> Array:
	var out: Array = []
	for rid: String in tm.coarse:
		out.append(tm.coarse[rid])
	for rid2: String in tm.regions:
		var rt: RegionTerrain = tm.regions[rid2]
		# A stand-in holding copies of what shade() reads: the live 1 m heights are dug in place.
		var c := RegionTerrain.new()
		c.region_id = rt.region_id
		c.rect = rt.rect
		c.spacing = rt.spacing
		var hf := HeightField.new()
		hf.origin = rt.height.origin
		hf.spacing = rt.height.spacing
		hf.width = rt.height.width
		hf.depth = rt.height.depth
		hf.heights = rt.height.heights.duplicate()
		c.height = hf
		c.vegmask = rt.vegmask.duplicate()
		out.append(c)
	return out


## Worker thread: the sheet's image for a world rect, from region terrains, river and lake shapes
## and road lines (world-level data). Pure: reads its arguments only.
static func shade(r: Rect2, sources: Array, rivers: Array, lakes: Array, roads: Array) -> Image:
	var w: int = int(r.size.x * PX_PER_M)
	var h: int = int(r.size.y * PX_PER_M)
	var img := Image.create(w, h, false, Image.FORMAT_RGB8)
	img.fill(PAPER)
	var step: float = 1.0 / PX_PER_M
	var heights := PackedFloat32Array()
	heights.resize(w * h)
	var veg := PackedFloat32Array()
	veg.resize(w * h)
	for src: Variant in sources:
		var rt: RegionTerrain = src
		var x0: int = int((rt.rect.position.x - r.position.x) * PX_PER_M)
		var y0: int = int((rt.rect.position.y - r.position.y) * PX_PER_M)
		var n: int = int(rt.rect.size.x * PX_PER_M)
		for y: int in n:
			for x: int in n:
				var px: int = x0 + x
				var py: int = y0 + y
				if px < 0 or py < 0 or px >= w or py >= h:
					continue
				var wx: float = r.position.x + (px + 0.5) * step
				var wz: float = r.position.y + (py + 0.5) * step
				heights[py * w + px] = rt.height.sample(wx, wz)
				veg[py * w + px] = rt.veg_at(wx, wz)
	for y2: int in h:
		for x2: int in w:
			var i: int = y2 * w + x2
			var e: float = heights[i]
			var ex: float = heights[i + 1] if x2 + 1 < w else e
			var ez: float = heights[i + w] if y2 + 1 < h else e
			# Light from the north-west, as survey sheets are drawn.
			var shade_k: float = clampf(1.0 - ((ex - e) + (ez - e)) * 0.06, 0.62, 1.18)
			var col: Color = PAPER.lerp(FOREST, clampf(veg[i] * 0.75, 0.0, 0.6))
			col = Color(col.r * shade_k, col.g * shade_k, col.b * shade_k)
			# A contour where a 20 m line passes between this pixel and its neighbours.
			if floorf(e / CONTOUR) != floorf(ex / CONTOUR) or floorf(e / CONTOUR) != floorf(ez / CONTOUR):
				col = col.lerp(CONTOUR_INK, 0.55 if int(floorf(maxf(e, maxf(ex, ez)) / CONTOUR)) % 5 == 0 else 0.3)
			img.set_pixel(x2, y2, col)
	for lake: Variant in lakes:
		_fill(img, r, (lake as Dictionary).get("polygon", PackedVector2Array()), WATER)
	for river: Variant in rivers:
		var d: Dictionary = river
		# A river's width is a number or a range along it ([from, to]): draw the mean.
		var wv: Variant = d.get("width", 12.0)
		var wm: float = float(wv) if (wv is float or wv is int) else 12.0
		if wv is Array and not (wv as Array).is_empty():
			wm = 0.0
			for x: Variant in wv:
				wm += float(x)
			wm /= (wv as Array).size()
		_line(img, r, d.get("line"), WATER, maxf(1.0, wm * PX_PER_M))
	for road: Variant in roads:
		_line(img, r, (road as Dictionary).get("line"), ROAD, 1.6)
	# The Cordon: a red dashed line just inside the sheet's edge.
	var red := Color(0.62, 0.14, 0.1)
	for k: int in range(4, maxi(w, h) - 4):
		if (k / 8) % 2 == 0:
			for t: int in 2:
				if k < w:
					img.set_pixel(k, 3 + t, red)
					img.set_pixel(k, h - 4 - t, red)
				if k < h:
					img.set_pixel(3 + t, k, red)
					img.set_pixel(w - 4 - t, k, red)
	return img


static func _to_px(r: Rect2, p: Vector2) -> Vector2:
	return (p - r.position) * PX_PER_M


static func _fill(img: Image, r: Rect2, poly: Variant, col: Color) -> void:
	var pts := PackedVector2Array()
	for p: Variant in poly:
		pts.append(_to_px(r, p if p is Vector2 else Vector2(float(p[0]), float(p[1]))))
	if pts.size() < 3:
		return
	var bb := Rect2(pts[0], Vector2.ZERO)
	for p2: Vector2 in pts:
		bb = bb.expand(p2)
	for y: int in range(maxi(0, int(bb.position.y)), mini(img.get_height(), int(bb.end.y) + 1)):
		for x: int in range(maxi(0, int(bb.position.x)), mini(img.get_width(), int(bb.end.x) + 1)):
			if Geometry2D.is_point_in_polygon(Vector2(x, y), pts):
				img.set_pixel(x, y, col)


## Draws a polyline (a Polyline2 or an array of points) `width` pixels wide.
static func _line(img: Image, r: Rect2, line: Variant, col: Color, width: float) -> void:
	var pts: PackedVector2Array = []
	if line is Object and (line as Object).get(&"points") != null:
		pts = (line as Object).get(&"points")
	elif line is PackedVector2Array:
		pts = line
	elif line is Array:
		for p: Variant in line:
			pts.append(Vector2(float(p[0]), float(p[p.size() - 1])))
	var rad: int = maxi(0, int(ceil(width * 0.5)) - 1)
	for i: int in range(1, pts.size()):
		var a: Vector2 = _to_px(r, pts[i - 1])
		var b: Vector2 = _to_px(r, pts[i])
		var n: int = maxi(1, int(a.distance_to(b)))
		for k: int in n + 1:
			var p: Vector2 = a.lerp(b, float(k) / n)
			for dy: int in range(-rad, rad + 1):
				for dx: int in range(-rad, rad + 1):
					var x: int = int(p.x) + dx
					var y: int = int(p.y) + dy
					if x >= 0 and y >= 0 and x < img.get_width() and y < img.get_height():
						img.set_pixel(x, y, col)


func _show(img: Image) -> void:
	_tex.texture = ImageTexture.create_from_image(img)
	_layout()


func _process(delta: float) -> void:
	_explore_t -= delta
	if _explore_t <= 0.0:
		_explore_t = 1.0
		_explore()
	if _task >= 0 and WorkerThreadPool.is_task_completed(_task):
		WorkerThreadPool.wait_for_task_completion(_task)
		_task = -1
		if _img != null:
			_cache_key = _pending_key
			_cache_img = _img
			_img = null
			if _open:
				_show(_cache_img)
				_status.text = "Wheel: zoom   ·   drag: pan   ·   M / Esc: close"
	if _open:
		_layout()
		_markers.queue_redraw()


## Once a second: uncover the map round the player (and round where they wake, the first time).
func _explore() -> void:
	var w: Node = Game.world
	var p: PlayerState = Game.local_player()
	if w == null or p == null or w.get(&"player") == null or not bool(w.get(&"is_ready")):
		return
	if p.explored.is_empty():
		var at: Vector3 = p.spawn_point if p.spawn_point != Vector3.ZERO else (w.player as Node3D).global_position
		Game.execute(&"map.explore", {"pos": at, "radius": FIRST_REVEAL})
	Game.execute(&"map.explore", {"pos": (w.player as Node3D).global_position, "radius": SIGHT})
	if _open:
		_refresh_fog(p)


## The fog over the sheet: one pixel a 32 m cell, paper where you haven't been.
func _refresh_fog(p: PlayerState) -> void:
	var count: int = 0
	for k: String in p.explored.blocks:
		for byte: int in (p.explored.blocks[k] as PackedByteArray):
			while byte:
				count += byte & 1
				byte >>= 1
	if count == _fog_count and _fog.texture != null:
		return
	_fog_count = count
	_fog.texture = ImageTexture.create_from_image(fog_image(p.explored, _rect))


## The fog image for a world rect: FOG on unexplored cells, clear on explored ones.
static func fog_image(ex: ExploredMap, r: Rect2) -> Image:
	var cw: int = int(ceil(r.size.x / ExploredMap.CELL))
	var ch: int = int(ceil(r.size.y / ExploredMap.CELL))
	var img := Image.create(cw, ch, false, Image.FORMAT_RGBA8)
	img.fill(FOG)
	var c0 := Vector2i(int(floor(r.position.x / ExploredMap.CELL)), int(floor(r.position.y / ExploredMap.CELL)))
	for y: int in ch:
		for x: int in cw:
			if ex.cell_explored(c0.x + x, c0.y + y):
				img.set_pixel(x, y, Color(0, 0, 0, 0))
	return img


## The sheet's rect on screen: fit to the screen at zoom 1, then zoomed and panned.
func _layout() -> void:
	var avail := Rect2(Vector2(48, 84), size - Vector2(96, 150))
	_sheet.position = avail.position
	_sheet.size = avail.size
	var fit: float = minf(avail.size.x / _rect.size.x, avail.size.y / _rect.size.y)
	var px: Vector2 = _rect.size * fit * _zoom
	_tex.size = px
	_tex.position = (avail.size - px) * 0.5 + _pan
	_markers.position = _tex.position
	_markers.size = px
	_fog.position = _tex.position
	_fog.size = px


func _world_to_sheet(p: Vector3) -> Vector2:
	return (Vector2(p.x, p.z) - _rect.position) / _rect.size * _tex.size


func _centre_on_player() -> void:
	var w: Node = Game.world
	if w == null or w.get(&"player") == null:
		return
	_layout()
	# At zoom 1 the whole sheet fits; centring matters once zoomed, so keep the pan at the middle.


func _gui_input(event: InputEvent) -> void:
	if not _open:
		return
	var mb := event as InputEventMouseButton
	if mb != null:
		if mb.pressed and mb.button_index in [MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN]:
			var old: float = _zoom
			_zoom = clampf(_zoom * (1.25 if mb.button_index == MOUSE_BUTTON_WHEEL_UP else 0.8), 1.0, 8.0)
			# Zoom on the cursor: the point under it stays put.
			var c: Vector2 = mb.position - _sheet.position - _sheet.size * 0.5
			_pan = c - (c - _pan) * (_zoom / old)
			if _zoom == 1.0:
				_pan = Vector2.ZERO
		elif mb.button_index == MOUSE_BUTTON_LEFT:
			_dragging = mb.pressed
		accept_event()
	elif event is InputEventMouseMotion and _dragging:
		_pan += (event as InputEventMouseMotion).relative
		accept_event()


func _unhandled_key_input(event: InputEvent) -> void:
	if _open and (event.is_action_pressed(&"map") or event.is_action_pressed(&"cancel") or event.is_action_pressed(&"pause")):
		close()
		get_viewport().set_input_as_handled()


func _draw_markers() -> void:
	var w: Node = Game.world
	if w == null or w.get(&"player") == null or _tex.texture == null:
		return
	var p: PlayerState = Game.local_player()
	var s: float = clampf(_zoom, 1.0, 2.5)
	var pois: Node = w.get(&"pois")
	if pois != null and pois.has_method(&"markers"):
		for m: Dictionary in (pois.call(&"markers") as Array):
			var col := Color(0.35, 0.33, 0.3)
			if bool(m["cleared"]):
				col = Color(0.18, 0.45, 0.2)
			elif bool(m["visited"]):
				col = Color(0.75, 0.4, 0.1)
			# The fog hides what you haven't seen for yourself.
			if p != null and not p.explored.is_explored((m["pos"] as Vector3).x, (m["pos"] as Vector3).z):
				continue
			var mp: Vector2 = _world_to_sheet(m["pos"])
			_markers.draw_rect(Rect2(mp - Vector2(3, 3) * s, Vector2(6, 6) * s), col)
	var traders: Node = w.get(&"traders")
	if traders != null and traders.has_method(&"markers"):
		for m2: Dictionary in (traders.call(&"markers") as Array[Dictionary]):
			if str(m2["kind"]) == "trader":
				var tp: Vector2 = _world_to_sheet(m2["pos"])
				_markers.draw_rect(Rect2(tp - Vector2(6, 6) * s, Vector2(12, 12) * s), Color(0.85, 0.62, 0.1))
				_markers.draw_rect(Rect2(tp - Vector2(6, 6) * s, Vector2(12, 12) * s), UiStyle.INK, false, 1.5)
	var drops: Node = w.get(&"supply_drops")
	if drops != null:
		for at: Vector3 in (drops.call(&"markers") as Array[Vector3]):
			var dp: Vector2 = _world_to_sheet(at)
			_markers.draw_colored_polygon(PackedVector2Array([dp + Vector2(0, -7) * s, dp + Vector2(7, 0) * s, dp + Vector2(0, 7) * s, dp + Vector2(-7, 0) * s]), Color(0.8, 0.2, 0.1))
	if p != null and p.spawn_point != Vector3.ZERO:
		var sp: Vector2 = _world_to_sheet(p.spawn_point)
		if p.has_spawn_point:
			_markers.draw_circle(sp, 5.0 * s, Color(0.85, 0.65, 0.1))
		else:
			_markers.draw_arc(sp, 6.0 * s, 0.0, TAU, 20, Color(0.85, 0.65, 0.1), 2.0)
	var pl: Node3D = w.player
	var me: Vector2 = _world_to_sheet(pl.global_position)
	var yaw: float = pl.global_rotation.y
	var fwd := Vector2(-sin(yaw), -cos(yaw))
	var right := Vector2(-fwd.y, fwd.x)
	var k: float = 9.0 * s
	_markers.draw_colored_polygon(PackedVector2Array([me + fwd * k, me - fwd * k * 0.6 + right * k * 0.6, me - fwd * k * 0.6 - right * k * 0.6]), UiStyle.INK_MISSING)
	_markers.draw_arc(me, k * 1.6, 0.0, TAU, 24, Color(UiStyle.INK_MISSING, 0.6), 1.5)
