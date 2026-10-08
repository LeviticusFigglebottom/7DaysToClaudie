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
##   RMB item  drop one (Shift: the stack) · 1-6 assign to the toolbelt · wheel over the cloth pages
## The crafting flap is a CraftSheet (a paper panel over the flap) and the hovered item gets an
## ItemCard; the cloth's sort and filter are a view of the inventory only (its order is state).

const COLS: int = 6
const ROWS: int = 5
const SLOT: float = 0.074
const ORIGIN := Vector3(-0.43, 0.0, -0.17)
const FLAP_ORIGIN := Vector3(0.07, 0.0, -0.17)
## Ink on the canvas cloth: light type with a dark outline (the cloth is mid-brown).
const CLOTH_TEXT := Color(0.94, 0.91, 0.82)
## How the cloth orders and filters stacks (a view: the inventory's order is untouched).
const SORTS: PackedStringArray = ["packed", "kind", "name"]
const FILTERS: Dictionary = {
	"all": [],
	"gear": ["tool", "weapon", "ammo", "clothing", "light", "throwable", "trap", "placeable"],
	"food & meds": ["food", "drink", "medical"],
	"materials": ["resource", "junk"],
	"papers": ["note", "schematic", "magazine", "quest", "key"],
}

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
var _sheet: CraftSheet
var _card: ItemCard
var _toolbar: HBoxContainer
var _bulk: Label
var _sort: String = "packed"
var _filter: String = "all"
var _slots: Array = []
var _flap_slots: Array = []
var _hover: Dictionary = {}
## Pages of stacks: the cloth shows COLS x ROWS at a time; the mouse wheel over a grid turns it.
var _page: int = 0
var _flap_page: int = 0
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
	_title = _cloth_label(30, UiStyle.heading_font())
	_flap_title = _cloth_label(24, UiStyle.heading_font())
	_bulk = _cloth_label(UiStyle.BODY_SIZE, null)
	_info = _cloth_label(UiStyle.BODY_SIZE, null)
	_info.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_info.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_build_toolbar()
	_sheet = CraftSheet.new()
	_sheet.craft_requested.connect(_craft)
	add_child(_sheet)
	_card = ItemCard.new()
	_card.visible = false
	add_child(_card)
	Events.inventory_changed.connect(func(_o: StringName) -> void: _dirty = true)
	Events.ui_modal_closed.connect(func(id: StringName) -> void:
		if id == &"salvage_roll" and _open:
			_close_silently())


## Type laid on the canvas: light with a dark outline, readable on the brown cloth at night too.
func _cloth_label(size: int, f: Font) -> Label:
	var l := Label.new()
	l.add_theme_font_size_override(&"font_size", size)
	l.add_theme_color_override(&"font_color", CLOTH_TEXT)
	l.add_theme_color_override(&"font_outline_color", Color(0.05, 0.04, 0.03, 0.95))
	l.add_theme_constant_override(&"outline_size", 6)
	if f != null:
		l.add_theme_font_override(&"font", f)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_overlay.add_child(l)
	return l


## Sort and filter for the cloth: small kit-style toggles above it.
func _build_toolbar() -> void:
	_toolbar = HBoxContainer.new()
	_toolbar.theme = UiStyle.kit_theme()
	_toolbar.add_theme_constant_override(&"separation", 4)
	add_child(_toolbar)
	_toolbar_group(SORTS, "Sort", func(v: String) -> void: _sort = v)
	var gap := Control.new()
	gap.custom_minimum_size = Vector2(18, 0)
	_toolbar.add_child(gap)
	_toolbar_group(PackedStringArray(FILTERS.keys()), "Show", func(v: String) -> void: _filter = v)


func _toolbar_group(values: PackedStringArray, caption: String, set_value: Callable) -> void:
	var l := UiStyle.label(caption, &"DimLabel")
	l.add_theme_color_override(&"font_color", CLOTH_TEXT)
	l.add_theme_color_override(&"font_outline_color", Color(0.05, 0.04, 0.03, 0.95))
	l.add_theme_constant_override(&"outline_size", 5)
	_toolbar.add_child(l)
	var group := ButtonGroup.new()
	for v: String in values:
		var b := Button.new()
		b.text = v.capitalize()
		b.toggle_mode = true
		b.button_group = group
		b.button_pressed = v == values[0]
		b.focus_mode = Control.FOCUS_NONE
		b.add_theme_font_size_override(&"font_size", UiStyle.BODY_SIZE - 3)
		b.pressed.connect(func() -> void:
			set_value.call(v)
			_page = 0
			_dirty = true)
		_toolbar.add_child(b)


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
	_card.visible = false
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
	var view: Array[ItemStack] = view_stacks(p.inventory.stacks, _sort, _filter)
	_page = clampi(_page, 0, _pages(view.size(), COLS) - 1)
	_place_stacks(view, ORIGIN, _items_root, _slots, COLS, _page)
	if mode == &"container" and container != null and is_instance_valid(container):
		var inv: Inventory = container.get(&"inventory")
		if inv != null:
			_flap_page = clampi(_flap_page, 0, _pages(inv.stacks.size(), 4) - 1)
			_place_stacks(inv.stacks, FLAP_ORIGIN + Vector3(0.02, 0.006, 0.0), _flap_root, _flap_slots, 4, _flap_page)
	_rebuild_recipes()


## The stacks the cloth shows, in its order: as packed (the inventory's own order), by kind
## (category, then name) or by name; `filter` is a FILTERS key.
static func view_stacks(stacks: Array[ItemStack], sort: String, filter: String) -> Array[ItemStack]:
	var cats: Array = FILTERS.get(filter, [])
	var out: Array[ItemStack] = []
	for s: ItemStack in stacks:
		var d: ItemDef = s.def()
		if cats.is_empty() or (d != null and cats.has(d.category)):
			out.append(s)
	if sort == "packed":
		return out
	var key := func(s: ItemStack) -> String:
		var d: ItemDef = s.def()
		var n: String = d.display_name if d != null else String(s.item_id)
		var c: String = d.category if d != null else "~"
		return (c + "|" + n) if sort == "kind" else n
	# Stable for equal keys: the packed index breaks ties.
	var idx: Dictionary = {}
	for i: int in out.size():
		idx[out[i]] = i
	out.sort_custom(func(a: ItemStack, b: ItemStack) -> bool:
		var ka: String = key.call(a)
		var kb: String = key.call(b)
		return ka < kb if ka != kb else int(idx[a]) < int(idx[b]))
	return out


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
			l.add_theme_font_size_override(&"font_size", 16)
			# Quality items wear their tier colour (Scrap grey ... Pristine violet).
			l.add_theme_color_override(&"font_color", ItemStack.quality_color(s.quality) if s.quality > 0 else Color(0.95, 0.93, 0.86))
			l.add_theme_color_override(&"font_outline_color", Color(0, 0, 0, 0.85))
			l.add_theme_constant_override(&"outline_size", 6)
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
	_sheet.visible = mode != &"container"
	if mode == &"container":
		return
	_sheet.refresh(_player(), station, _flap_name())


func _flap_name() -> String:
	match mode:
		&"container":
			var cname: String = "Container"
			if container != null and container.get(&"cdef") != null:
				cname = (container.get(&"cdef") as ContainerDef).display_name
			elif container is Enemy:
				cname = "Remains"
			elif container is StructurePiece:
				cname = (container as StructurePiece).def.display_name
			return cname
		&"station":
			var sd: StationDef = Content.get_def(&"station", station) as StationDef
			return sd.display_name if sd != null else String(station)
	return "Make by hand"


## Makes a recipe `times` times through the command bus (one craft per command), stopping at the
## first failure and saying why.
func _craft(recipe_id: StringName, times: int = 1) -> void:
	var made: int = 0
	var last: Dictionary = {}
	for i: int in maxi(1, times):
		last = Game.execute(&"inventory.craft", {"recipe": String(recipe_id), "station": String(station)})
		if not bool(last.get("ok", false)):
			break
		made += int(last.get("count", 1))
	var r: RecipeDef = Content.recipe(recipe_id)
	var nm: String = r.display_name if r != null else String(recipe_id)
	if made > 0:
		_info.text = "Made %s%s." % [nm, (" ×%d" % made) if made > 1 else ""]
	else:
		_info.text = "Can't make %s: %s." % [nm, str(last.get("error", "missing materials"))]
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
	var top: Vector2 = _screen(ORIGIN + Vector3(0.0, 0.0, -0.01))
	_title.position = top - Vector2(0, _title.size.y + 8 + _toolbar.size.y + 6)
	_toolbar.position = top - Vector2(0, _toolbar.size.y + 6)
	var bulk: float = p.inventory.total_bulk()
	_bulk.text = "Pack %.1f / %.0f   ·   Shoulder: %d log%s" % [bulk, p.inventory.max_bulk, p.inventory.count_of(&"log"), "" if p.inventory.count_of(&"log") == 1 else "s"]
	_bulk.add_theme_color_override(&"font_color", UiStyle.RUST_BRIGHT if bulk > p.inventory.max_bulk * 0.9 else CLOTH_TEXT)
	var shown: int = view_stacks(p.inventory.stacks, _sort, _filter).size()
	var pages: int = _pages(shown, COLS)
	if pages > 1:
		_bulk.text += "   ·   page %d/%d (wheel)" % [_page + 1, pages]
	if _filter != "all":
		_bulk.text += "   ·   showing %d of %d" % [shown, p.inventory.stacks.size()]
	_bulk.position = _screen(ORIGIN + Vector3(0.0, 0.0, ROWS * SLOT + 0.02))
	_flap_title.text = _flap_name().to_upper()
	_flap_title.visible = mode == &"container"
	_flap_title.position = _screen(FLAP_ORIGIN + Vector3(0.02, 0.0, -0.01)) - Vector2(0, _flap_title.size.y)
	# The sheet covers the paper flap, and never gets narrower than its contents need.
	var a: Vector2 = _screen(FLAP_ORIGIN + Vector3(0.0, 0.0, -0.04))
	var b: Vector2 = _screen(FLAP_ORIGIN + Vector3(0.41, 0.0, 0.44))
	var w: float = maxf(b.x - a.x, 560.0)
	var x: float = minf(a.x, size.x - w - 16.0)
	var y: float = maxf(16.0, top.y - _toolbar.size.y - _title.size.y - 14.0)
	_sheet.position = Vector2(x, y)
	_sheet.size = Vector2(w, maxf(b.y - y, 520.0))
	for l: Label in _labels:
		if is_instance_valid(l):
			l.position = _screen(l.get_meta(&"anchor"))
	_info.position = Vector2(size.x * 0.12, minf(size.y - 70.0, _bulk.position.y + _bulk.size.y + 14.0))
	_info.size = Vector2(size.x * 0.76, 60)
	if _card.visible:
		_place_card()


## The item card sits beside the cursor, flipped to stay on screen.
func _place_card() -> void:
	var m: Vector2 = get_local_mouse_position()
	var cs: Vector2 = _card.get_combined_minimum_size()
	var pos: Vector2 = m + Vector2(28, 12)
	if pos.x + cs.x > size.x - 12.0:
		pos.x = m.x - cs.x - 28.0
	pos.y = clampf(pos.y, 12.0, maxf(12.0, size.y - cs.y - 12.0))
	_card.position = pos


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
		else:
			_card.visible = false


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
		elif d.has_tag("repair"):
			actions.append("[LMB] repair the held or most worn tool")
		elif d.category in ["note", "schematic", "magazine"]:
			actions.append("[LMB] read")
		elif not d.equip.is_empty():
			actions.append("[LMB] equip")
		actions.append("[1-6] toolbelt")
	if not in_flap:
		actions.append("[RMB] drop")
	_card.show_stack(s, "   ".join(actions))
	_card.visible = true
	_place_card()


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
	elif d.has_tag("repair"):
		Game.execute(&"inventory.repair", {"item": String(s.item_id)})
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
