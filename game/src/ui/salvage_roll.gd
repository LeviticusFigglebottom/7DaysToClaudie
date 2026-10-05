class_name SalvageRoll
extends Control
## The salvage roll (diegetic inventory, DESIGN.md): a canvas tool roll unrolled in front of you
## with everything you carry laid out as real 3D objects. The right flap is either the crafting
## sheet (recipes you can make here — by hand or at the station you opened it from) or another
## container's contents (crate, cabinet, remains) to trade items with.
##
## Rendered in its own SubViewport (own world, own light) so it never clips into walls and reads
## the same at night; text is a 2D ink overlay projected onto the cloth.
##   LMB item  use / equip / read (in a container view: move to the other side)
##   RMB item  drop one (Shift: the stack) · 1-6 assign to the toolbelt · wheel scrolls recipes

const COLS: int = 6
const ROWS: int = 5
const SLOT: float = 0.074
const ORIGIN := Vector3(-0.43, 0.0, -0.17)
const FLAP_ORIGIN := Vector3(0.07, 0.0, -0.17)
const INK := Color(0.16, 0.13, 0.1)
const INK_DIM := Color(0.42, 0.36, 0.3)

var mode: StringName = &"inventory"
var station: StringName = &""
var station_node: Node = null
var container: Object = null
var _open: bool = false
var _vp: SubViewport
var _cam: Camera3D
var _items_root: Node3D
var _flap_root: Node3D
var _overlay: Control
var _info: Label
var _title: Label
var _flap_title: Label
var _recipe_box: VBoxContainer
var _bulk: Label
var _slots: Array = []
var _flap_slots: Array = []
var _hover: Dictionary = {}
var _scroll: int = 0
## Recipes in the current list (the scroll stops at the last page of them).
var _recipe_count: int = 0
## Pages of stacks: the cloth shows COLS x ROWS at a time; the mouse wheel over a grid turns it.
var _page: int = 0
var _flap_page: int = 0
const RECIPE_ROWS: int = 11
var _dirty: bool = true
var _labels: Array[Label] = []


func _ready() -> void:
	# In the tree already: plain set_anchors_preset() would keep the 0x0 rect (offsets follow).
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	visible = false
	process_mode = Node.PROCESS_MODE_ALWAYS
	var dim := ColorRect.new()
	dim.color = Color(0.0, 0.0, 0.0, 0.55)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	dim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(dim)
	var svc := SubViewportContainer.new()
	svc.stretch = true
	svc.set_anchors_preset(Control.PRESET_FULL_RECT)
	svc.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(svc)
	_vp = SubViewport.new()
	_vp.transparent_bg = true
	_vp.own_world_3d = true
	_vp.msaa_3d = Viewport.MSAA_2X
	_vp.render_target_update_mode = SubViewport.UPDATE_DISABLED
	svc.add_child(_vp)
	_build_scene()
	_overlay = Control.new()
	_overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
	_overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_overlay)
	_title = _ink_label(22, INK)
	_flap_title = _ink_label(20, INK)
	_bulk = _ink_label(15, INK_DIM)
	_info = Label.new()
	_info.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_info.add_theme_color_override(&"font_color", Color(0.92, 0.9, 0.84))
	_info.add_theme_color_override(&"font_outline_color", Color(0, 0, 0, 0.9))
	_info.add_theme_constant_override(&"outline_size", 5)
	_info.add_theme_font_size_override(&"font_size", 17)
	_overlay.add_child(_info)
	_recipe_box = VBoxContainer.new()
	_recipe_box.add_theme_constant_override(&"separation", 2)
	_recipe_box.mouse_filter = Control.MOUSE_FILTER_PASS
	add_child(_recipe_box)
	Events.inventory_changed.connect(func(_o: StringName) -> void: _dirty = true)
	Events.ui_modal_closed.connect(func(id: StringName) -> void:
		if id == &"salvage_roll" and _open:
			_close_silently())


func _ink_label(size: int, color: Color) -> Label:
	var l := Label.new()
	l.add_theme_font_size_override(&"font_size", size)
	l.add_theme_color_override(&"font_color", color)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_overlay.add_child(l)
	return l


func _build_scene() -> void:
	var env := WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_CLEAR_COLOR
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(0.55, 0.5, 0.45)
	e.ambient_light_energy = 0.6
	e.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.environment = e
	_vp.add_child(env)
	_cam = Camera3D.new()
	_cam.fov = 38.0
	_cam.position = Vector3(0.0, 0.78, 0.5)
	_vp.add_child(_cam)
	_cam.look_at_from_position(_cam.position, Vector3(0, 0, -0.02), Vector3.UP)
	var key := DirectionalLight3D.new()
	key.light_color = Color(1.0, 0.9, 0.78)
	key.light_energy = 1.4
	key.shadow_enabled = true
	key.rotation = Vector3(deg_to_rad(-62), deg_to_rad(-28), 0)
	_vp.add_child(key)
	var fill := OmniLight3D.new()
	fill.light_color = Color(0.65, 0.75, 1.0)
	fill.light_energy = 0.4
	fill.omni_range = 2.0
	fill.position = Vector3(0.6, 0.6, 0.6)
	_vp.add_child(fill)
	# The cloth roll and the flap.
	_vp.add_child(_cloth(Vector2(0.98, 0.56), Vector3(0, 0, 0), "res://assets/generated/textures/ui_canvas.png", Color(0.47, 0.4, 0.3)))
	_vp.add_child(_cloth(Vector2(0.4, 0.44), Vector3(0.27, 0.004, 0.01), "res://assets/generated/textures/ui_paper_page.png", Color(0.86, 0.82, 0.72)))
	_items_root = Node3D.new()
	_vp.add_child(_items_root)
	_flap_root = Node3D.new()
	_vp.add_child(_flap_root)


func _cloth(size: Vector2, pos: Vector3, tex_path: String, fallback: Color) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = size
	var m := StandardMaterial3D.new()
	m.roughness = 0.95
	if ResourceLoader.exists(tex_path):
		m.albedo_texture = load(tex_path)
	else:
		m.albedo_color = fallback
	pm.material = m
	mi.mesh = pm
	mi.position = pos
	return mi


# --- Open / close --------------------------------------------------------------------------

func open(p_mode: StringName = &"inventory", p_station: StringName = &"", p_container: Object = null) -> void:
	mode = p_mode
	station = p_station
	container = p_container
	station_node = p_container if p_mode == &"station" else null
	_scroll = 0
	_page = 0
	_flap_page = 0
	_open = true
	visible = true
	_vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	_dirty = true
	var ui: Node = get_parent()
	if ui != null and ui.has_method(&"push_modal"):
		ui.call(&"push_modal", &"salvage_roll")
	Audio.play_2d(&"ui/roll_open", -6.0)


func close() -> void:
	if not _open:
		return
	_close_silently()
	var ui: Node = get_parent()
	if ui != null and ui.has_method(&"pop_modal"):
		ui.call(&"pop_modal", &"salvage_roll")
	Audio.play_2d(&"ui/roll_close", -8.0)


func _close_silently() -> void:
	_open = false
	visible = false
	container = null
	station_node = null
	_vp.render_target_update_mode = SubViewport.UPDATE_DISABLED


func is_open() -> bool:
	return _open


func _player() -> PlayerState:
	return Game.local_player()


# --- Layout ---------------------------------------------------------------------------------

func _rebuild() -> void:
	_dirty = false
	for c: Node in _items_root.get_children():
		c.queue_free()
	for c2: Node in _flap_root.get_children():
		c2.queue_free()
	for l: Label in _labels:
		l.queue_free()
	_labels.clear()
	_slots.clear()
	_flap_slots.clear()
	var p: PlayerState = _player()
	if p == null:
		return
	_page = clampi(_page, 0, _pages(p.inventory.stacks.size(), COLS) - 1)
	_place_stacks(p.inventory.stacks, ORIGIN, _items_root, _slots, COLS, _page)
	if mode == &"container" and container != null and is_instance_valid(container):
		var inv: Inventory = container.get(&"inventory")
		if inv != null:
			_flap_page = clampi(_flap_page, 0, _pages(inv.stacks.size(), 4) - 1)
			_place_stacks(inv.stacks, FLAP_ORIGIN + Vector3(0.02, 0.006, 0.0), _flap_root, _flap_slots, 4, _flap_page)
	_rebuild_recipes()


static func _pages(n: int, cols: int) -> int:
	return maxi(1, ceili(float(n) / float(cols * ROWS)))


func _place_stacks(stacks: Array[ItemStack], origin: Vector3, parent: Node3D, out: Array, cols: int, page: int = 0) -> void:
	var per_page: int = cols * ROWS
	for k: int in range(page * per_page, mini(stacks.size(), (page + 1) * per_page)):
		var i: int = k - page * per_page
		var s: ItemStack = stacks[k]
		var center: Vector3 = origin + Vector3((i % cols + 0.5) * SLOT, 0.006, (i / cols + 0.5) * SLOT)
		var holder := Node3D.new()
		holder.position = center
		parent.add_child(holder)
		var model: Node3D = ItemVisuals.make_model(s.item_id)
		holder.add_child(model)
		_fit(model, SLOT * 0.8)
		holder.rotation.y = deg_to_rad(float((i * 37) % 30) - 15.0)
		out.append({"stack": s, "center": center, "holder": holder})
		if s.count > 1 or s.def() != null and s.def().durability > 0.0:
			var l := Label.new()
			l.text = ("x%d" % s.count) if s.count > 1 else "%d%%" % int(100.0 * s.durability / maxf(1.0, s.def().durability * ItemStack.quality_durability_mult(s.quality)))
			if s.quality > 0 and s.count <= 1:
				l.text = "Q%d %s" % [s.quality, l.text]
			l.add_theme_font_size_override(&"font_size", 13)
			# Quality items wear their tier colour (Scrap grey ... Pristine violet).
			l.add_theme_color_override(&"font_color", ItemStack.quality_color(s.quality) if s.quality > 0 else Color(0.95, 0.93, 0.86))
			l.add_theme_color_override(&"font_outline_color", Color(0, 0, 0, 0.85))
			l.add_theme_constant_override(&"outline_size", 4)
			l.mouse_filter = Control.MOUSE_FILTER_IGNORE
			l.set_meta(&"anchor", center + Vector3(SLOT * 0.3, 0.0, SLOT * 0.38))
			_overlay.add_child(l)
			_labels.append(l)


## Scales and lifts a model so it fits a slot and rests on the cloth.
func _fit(model: Node3D, size: float) -> void:
	var aabb := AABB()
	var first: bool = true
	for c: Node in model.find_children("*", "VisualInstance3D", true, false):
		var vi: VisualInstance3D = c
		var b: AABB = vi.transform * vi.get_aabb()
		aabb = b if first else aabb.merge(b)
		first = false
	var longest: float = maxf(aabb.size.x, maxf(aabb.size.y, aabb.size.z))
	if longest <= 0.0001:
		return
	var s: float = size / longest
	model.scale = Vector3.ONE * s
	# Lay long things flat (axes, bottles): the longest axis goes along the cloth.
	if aabb.size.y >= maxf(aabb.size.x, aabb.size.z):
		model.rotation.x = -PI * 0.5
		model.position = Vector3(0, -aabb.position.z * s, 0)
	else:
		model.position = Vector3(0, -aabb.position.y * s, 0)


func _rebuild_recipes() -> void:
	for c: Node in _recipe_box.get_children():
		c.queue_free()
	if mode == &"container":
		return
	var p: PlayerState = _player()
	var list: Array = []
	for r: RecipeDef in Content.all(&"recipe"):
		if r.station != station and not (station == &"" and r.station == &"hand"):
			continue
		if not p.progression.knows_recipe(r):
			continue
		var chk: Crafting.Result = Crafting.check(r, p.inventory, station)
		list.append([r, chk.ok])
	list.sort_custom(func(a: Array, b: Array) -> bool:
		if a[1] != b[1]:
			return a[1]
		return String((a[0] as RecipeDef).display_name) < String((b[0] as RecipeDef).display_name))
	_recipe_count = list.size()
	_scroll = clampi(_scroll, 0, maxi(0, list.size() - RECIPE_ROWS))
	var shown: int = 0
	for i: int in range(_scroll, list.size()):
		if shown >= RECIPE_ROWS:
			break
		var r2: RecipeDef = list[i][0]
		var ok: bool = list[i][1]
		var b := Button.new()
		b.flat = true
		b.alignment = HORIZONTAL_ALIGNMENT_LEFT
		b.text = "%s%s  —  %s" % [r2.display_name, (" x%d" % r2.result_count) if r2.result_count > 1 else "", _cost_text(r2, p.inventory)]
		b.add_theme_color_override(&"font_color", INK if ok else INK_DIM)
		b.add_theme_color_override(&"font_hover_color", Color(0.45, 0.12, 0.08) if ok else INK_DIM)
		b.add_theme_font_size_override(&"font_size", 14)
		b.disabled = not ok
		b.pressed.connect(_craft.bind(r2.id))
		b.mouse_entered.connect(func() -> void: _show_recipe(r2))
		_recipe_box.add_child(b)
		shown += 1
	if list.is_empty():
		var l := Label.new()
		l.text = "Nothing you know how to make here."
		l.add_theme_color_override(&"font_color", INK_DIM)
		_recipe_box.add_child(l)


func _cost_text(r: RecipeDef, inv: Inventory) -> String:
	var parts: PackedStringArray = []
	for k: Variant in r.ingredients.keys():
		var d: ItemDef = Content.item(StringName(str(k)))
		var have: int = inv.count_of(StringName(str(k)))
		parts.append("%d/%d %s" % [mini(have, int(r.ingredients[k])), int(r.ingredients[k]), d.display_name if d != null else str(k)])
	for t: Variant in r.tools_required:
		parts.append("[%s]" % str(t))
	return ", ".join(parts)


func _show_recipe(r: RecipeDef) -> void:
	var d: ItemDef = Content.item(r.result)
	_info.text = "%s — %s" % [r.display_name, d.description if d != null else ""]


func _craft(recipe_id: StringName) -> void:
	var res: Dictionary = Game.execute(&"inventory.craft", {"recipe": String(recipe_id), "station": String(station)})
	if not bool(res.get("ok", false)):
		_info.text = "Can't make that: %s" % str(res.get("error", ""))
	_dirty = true


# --- Frame ------------------------------------------------------------------------------------

func _process(_delta: float) -> void:
	if not _open:
		return
	if _dirty:
		_rebuild()
	if container != null and not is_instance_valid(container):
		close()
		return
	_layout_overlay()
	_update_hover()


func _screen(p: Vector3) -> Vector2:
	var vs: Vector2 = Vector2(_vp.size)
	var s: Vector2 = _cam.unproject_position(p)
	return s * (size / vs) if vs.x > 0 else s


func _layout_overlay() -> void:
	var p: PlayerState = _player()
	_title.text = "SALVAGE ROLL"
	_title.position = _screen(ORIGIN + Vector3(0.0, 0.0, -0.035))
	_bulk.text = "Pack %.1f / %.0f   ·   Shoulder: %d log%s" % [p.inventory.total_bulk(), p.inventory.max_bulk, p.inventory.count_of(&"log"), "" if p.inventory.count_of(&"log") == 1 else "s"]
	var pages: int = _pages(p.inventory.stacks.size(), COLS)
	if pages > 1:
		_bulk.text += "   ·   page %d/%d (wheel over the cloth)" % [_page + 1, pages]
	_bulk.position = _screen(ORIGIN + Vector3(0.0, 0.0, ROWS * SLOT + 0.02))
	match mode:
		&"container":
			var cname: String = "Container"
			if container != null and container.get(&"cdef") != null:
				cname = (container.get(&"cdef") as ContainerDef).display_name
			elif container is Enemy:
				cname = "Remains"
			elif container is StructurePiece:
				cname = (container as StructurePiece).def.display_name
			_flap_title.text = cname.to_upper()
		&"station":
			var sd: StationDef = Content.get_def(&"station", station) as StationDef
			_flap_title.text = (sd.display_name if sd != null else String(station)).to_upper()
		_:
			_flap_title.text = "MAKE BY HAND"
	_flap_title.position = _screen(FLAP_ORIGIN + Vector3(0.02, 0.0, -0.01))
	var tl: Vector2 = _screen(FLAP_ORIGIN + Vector3(0.02, 0.0, 0.03))
	_recipe_box.position = tl
	_recipe_box.size = Vector2(_screen(FLAP_ORIGIN + Vector3(0.38, 0.0, 0.0)).x - tl.x, 0)
	_recipe_box.visible = mode != &"container"
	for l: Label in _labels:
		if is_instance_valid(l):
			l.position = _screen(l.get_meta(&"anchor"))
	_info.position = Vector2(size.x * 0.12, size.y * 0.86)
	_info.size = Vector2(size.x * 0.76, 60)


func _mat_point(mouse: Vector2) -> Vector3:
	var vs: Vector2 = Vector2(_vp.size)
	var m: Vector2 = mouse * (vs / size) if size.x > 0 else mouse
	var from: Vector3 = _cam.project_ray_origin(m)
	var dir: Vector3 = _cam.project_ray_normal(m)
	if absf(dir.y) < 0.0001:
		return Vector3.INF
	var t: float = -from.y / dir.y
	return from + dir * t


static func _in_grid(mp: Vector3, origin: Vector3, cols: int) -> bool:
	return mp != Vector3.INF and mp.x >= origin.x and mp.x <= origin.x + cols * SLOT \
		and mp.z >= origin.z and mp.z <= origin.z + ROWS * SLOT


func _update_hover() -> void:
	var mp: Vector3 = _mat_point(get_local_mouse_position())
	var found: Dictionary = {}
	for list: Array in [_slots, _flap_slots]:
		for e: Dictionary in list:
			var c: Vector3 = e["center"]
			if absf(mp.x - c.x) < SLOT * 0.5 and absf(mp.z - c.z) < SLOT * 0.5:
				found = e
				found["flap"] = list == _flap_slots
	if found.get("holder") != _hover.get("holder"):
		if _hover.has("holder") and is_instance_valid(_hover["holder"]):
			(_hover["holder"] as Node3D).scale = Vector3.ONE
			(_hover["holder"] as Node3D).position.y = 0.006
		_hover = found
		if _hover.has("holder"):
			(_hover["holder"] as Node3D).scale = Vector3.ONE * 1.18
			(_hover["holder"] as Node3D).position.y = 0.02
			_describe(_hover["stack"], bool(_hover["flap"]))
		elif _info.text.begins_with("["):
			_info.text = ""


func _describe(s: ItemStack, in_flap: bool) -> void:
	var d: ItemDef = s.def()
	if d == null:
		return
	var actions: PackedStringArray = []
	if mode == &"container":
		actions.append("[LMB] " + ("take" if in_flap else "put in"))
	else:
		if d.is_consumable():
			actions.append("[LMB] use")
		elif d.category in ["note", "schematic", "magazine"]:
			actions.append("[LMB] read")
		elif not d.equip.is_empty():
			actions.append("[LMB] equip")
		actions.append("[1-6] toolbelt")
	if not in_flap:
		actions.append("[RMB] drop")
	var q: String = (" · %s (Q%d)" % [ItemStack.quality_name(s.quality), s.quality]) if s.quality > 0 else ""
	_info.text = "[%s]%s  %s\n%s" % [d.display_name, q, "   ".join(actions), d.description]


func _gui_input(event: InputEvent) -> void:
	if not _open:
		return
	var p: PlayerState = _player()
	if event is InputEventMouseButton and event.pressed:
		var mb: InputEventMouseButton = event
		if mb.button_index in [MOUSE_BUTTON_WHEEL_DOWN, MOUSE_BUTTON_WHEEL_UP]:
			var step: int = 1 if mb.button_index == MOUSE_BUTTON_WHEEL_DOWN else -1
			var mp: Vector3 = _mat_point(get_local_mouse_position())
			if _in_grid(mp, ORIGIN, COLS):
				_page += step
				_dirty = true
			elif mode == &"container" and _in_grid(mp, FLAP_ORIGIN + Vector3(0.02, 0.0, 0.0), 4):
				_flap_page += step
				_dirty = true
			else:
				_scroll = clampi(_scroll + step, 0, maxi(0, _recipe_count - RECIPE_ROWS))
				_rebuild_recipes()
		elif _hover.has("stack"):
			var s: ItemStack = _hover["stack"]
			var flap: bool = bool(_hover["flap"])
			if mb.button_index == MOUSE_BUTTON_LEFT:
				_primary(p, s, flap)
			elif mb.button_index == MOUSE_BUTTON_RIGHT and not flap:
				Game.execute(&"inventory.drop", {"item": String(s.item_id), "count": s.count if mb.shift_pressed else 1,
					"index": p.inventory.stacks.find(s)})
			_dirty = true
		accept_event()


func _unhandled_key_input(event: InputEvent) -> void:
	if not _open:
		return
	if event.is_action_pressed(&"inventory") or event.is_action_pressed(&"cancel"):
		close()
		get_viewport().set_input_as_handled()
		return
	if _hover.has("stack") and not bool(_hover.get("flap", false)):
		for i: int in 6:
			if event.is_action_pressed(StringName("toolbelt_%d" % (i + 1))):
				Game.execute(&"inventory.equip", {"item": String((_hover["stack"] as ItemStack).item_id), "slot": i})
				_info.text = "Toolbelt %d: %s" % [i + 1, (_hover["stack"] as ItemStack).def().display_name]
				get_viewport().set_input_as_handled()


func _primary(p: PlayerState, s: ItemStack, flap: bool) -> void:
	if mode == &"container":
		if flap:
			var inv: Inventory = container.get(&"inventory")
			var idx: int = inv.stacks.find(s)
			Game.execute(&"container.take", {"container": container, "index": idx})
		else:
			Game.execute(&"container.put", {"container": container, "item": String(s.item_id), "count": s.count,
				"index": p.inventory.stacks.find(s)})
		return
	var d: ItemDef = s.def()
	if d == null:
		return
	if d.is_consumable():
		Game.execute(&"inventory.consume", {"item": String(s.item_id)})
	elif d.category in ["note", "schematic", "magazine"]:
		var res: Dictionary = Game.execute(&"inventory.read", {"item": String(s.item_id)})
		if res.has("note"):
			var ui: Node = get_parent()
			if ui != null and ui.has_method(&"show_note"):
				ui.call(&"show_note", StringName(str(res["note"])))
		elif res.has("learned"):
			_info.text = "Learned something new."
	elif not d.equip.is_empty():
		Game.execute(&"inventory.equip", {"item": String(s.item_id)})
		_info.text = "Equipped %s." % d.display_name
