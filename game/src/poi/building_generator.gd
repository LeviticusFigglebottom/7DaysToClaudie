class_name BuildingGenerator
extends RefCounted
## Generated ordinary buildings (ADR-0030): a BuildingTemplateDef plus a seed becomes a complete,
## validated PoiDef - plan, rooms and finishes, doors and windows, stairs, furniture and loot, a few
## sleepers with one small ambush, a gentle trap, a dungeon-lite route with a bolted front and a way
## in, the porch, the yard and the roof - built from the existing kit by PoiBuilder like any
## authored building. These are the tier-1 "filler" houses, shops and workshops of a street; the
## authored set pieces stay the dungeons.
##
## Archetypes (BuildingTemplateDef.archetype):
##  * house: a hall from the front door to the back, a day side (living room and kitchen) and a
##    night side (bedrooms and bath) on either side of it, both drawn per building. Two storeys
##    widen the hall to two columns: a flight rises in one from the back, the other stays a
##    passage. "cape" sets the upper floor back from the front so the front rooms get a lean-to.
##  * duplex: two units side by side behind their own front doors; the neighbours knocked through
##    the party wall.
##  * store: a sales floor behind display windows, a stock room, an office and a restroom behind it.
##  * workshop: a bay behind chained double doors, an office and a tool crib.
## Every draw comes from one seeded stream, so a template and a seed always give the same building.
## generate() validates what it made (PoiValidator: route, loot, locks, sleepers, props off the
## route) and tries again from a derived seed if anything is reported, up to MAX_TRIES.

## New ADR-0030 scripts by path, so this compiles before the editor registers their class names.
const TemplateDef := preload("res://src/core/content/defs/building_template_def.gd")

const MAX_TRIES: int = 8
## Yard kept round the building inside its lot (m): sides, back.
const SIDE_YARD: int = 3
const BACK_YARD: int = 4

## Furniture per room purpose: [prop id, placement, chance]. Placements: "wall" (back to a solid
## wall), "high" (wall-mounted over a wall slot), "table" (a table with a chair each side),
## "rug", "aisle" (free-standing shelving), "car" (a wreck in a bay).
const FURNITURE: Dictionary = {
	"living": [["couch", "wall", 1.0], ["armchair", "wall", 0.7], ["tv_crt", "wall", 0.6], ["bookshelf", "wall", 0.8],
		["side_table", "wall", 0.5], ["floor_lamp", "wall", 0.5], ["coffee_table", "rug", 0.4], ["rug_rect", "rug", 0.5]],
	"kitchen": [["fridge_old", "wall", 1.0], ["stove_old", "wall", 1.0], ["kitchen_counter_sink", "wall", 1.0], ["kitchen_counter", "wall", 0.9],
		["kitchen_wall_cabinet", "high", 0.8], ["kitchen_counter", "wall", 0.5], ["trash_can_kitchen", "wall", 0.6], ["kitchen_table", "table", 0.8]],
	"bedroom": [["bed_double", "wall", 1.0], ["dresser", "wall", 0.9], ["nightstand", "wall", 0.8], ["wardrobe", "wall", 0.6],
		["armchair", "wall", 0.25], ["rug_oval", "rug", 0.4]],
	"kids": [["bed_single", "wall", 1.0], ["dresser", "wall", 0.8], ["bed_single", "wall", 0.4], ["nightstand", "wall", 0.5],
		["crib", "wall", 0.3], ["rug_oval", "rug", 0.6]],
	"nursery": [["crib", "wall", 1.0], ["dresser", "wall", 0.9], ["armchair", "wall", 0.6], ["rug_oval", "rug", 0.6]],
	"bath": [["toilet", "wall", 1.0], ["sink_pedestal", "wall", 1.0], ["bathtub", "wall", 0.7], ["medicine_cabinet", "high", 0.9]],
	"dining": [["kitchen_table", "table", 1.0], ["dresser", "wall", 0.7], ["bookshelf", "wall", 0.5]],
	"study": [["desk_small", "wall", 1.0], ["bookshelf", "wall", 1.0], ["bookshelf", "wall", 0.6], ["armchair", "wall", 0.5],
		["filing_cabinet", "wall", 0.4], ["rug_rect", "rug", 0.5]],
	"office": [["office_desk", "wall", 1.0], ["filing_cabinet", "wall", 0.9], ["bookshelf", "wall", 0.6], ["safe_small", "wall", 0.5],
		["metal_shelf", "wall", 0.4], ["water_cooler", "wall", 0.3]],
	"storage": [["metal_shelf", "wall", 1.0], ["metal_shelf", "wall", 0.9], ["metal_shelf", "wall", 0.6], ["cardboard_box", "wall", 0.7],
		["crate_wood", "wall", 0.5], ["paint_can_stack", "wall", 0.4], ["feed_sacks", "wall", 0.3]],
	"utility": [["metal_shelf", "wall", 0.8], ["cardboard_box", "wall", 0.7], ["bucket", "wall", 0.5], ["trash_bag", "wall", 0.4]],
	"store": [["checkout_counter", "wall", 1.0], ["store_freezer", "wall", 0.8], ["road_cooler", "wall", 0.6], ["metal_shelf", "wall", 0.7],
		["road_vending_machine", "wall", 0.4], ["store_shelf_gondola", "aisle", 1.0]],
	"garage": [["road_workbench", "wall", 1.0], ["road_tool_chest", "wall", 0.9], ["metal_shelf", "wall", 0.8], ["road_oil_shelf", "wall", 0.6],
		["farm_tool_rack", "wall", 0.5], ["road_tire_stack", "wall", 0.5], ["road_oil_drum", "wall", 0.5], ["car_sedan_wreck", "car", 0.5]],
	"hallway": [],
}
## Room purpose -> [plan room type, display name].
const PURPOSE: Dictionary = {
	"living": ["living", "Living room"], "kitchen": ["kitchen", "Kitchen"], "bedroom": ["bedroom", "Bedroom"],
	"kids": ["bedroom", "Kids' room"], "nursery": ["bedroom", "Nursery"], "bath": ["bath", "Bathroom"], "dining": ["living", "Dining room"],
	"study": ["office", "Study"], "office": ["office", "Office"], "storage": ["storage", "Stock room"], "utility": ["storage", "Utility room"],
	"store": ["store", "Sales floor"], "garage": ["garage", "Workshop bay"], "hallway": ["hallway", "Hall"],
}
## Finishes when a template names none for a purpose's room type.
const DEFAULT_FINISH: Dictionary = {
	"living": {"wall": ["wallpaper_damask_brown", "wallpaper_stripe_green", "paint_sage", "wood_paneling_dark"], "floor": ["wood_oak", "carpet_brown"]},
	"kitchen": {"wall": ["tile_kitchen_check", "paint_mustard", "plaster_white"], "floor": ["linoleum_check", "linoleum_beige"]},
	"bedroom": {"wall": ["paint_sage", "paint_slate_blue", "wallpaper_floral_rose", "plaster_white"], "floor": ["carpet_brown", "carpet_blue_worn", "wood_pine"]},
	"bath": {"wall": ["tile_bathroom_white"], "floor": ["tile_white_small", "linoleum_beige"]},
	"office": {"wall": ["wood_paneling_dark", "plaster_grey", "paint_slate_blue"], "floor": ["carpet_brown", "wood_oak"]},
	"storage": {"wall": ["plaster_grey", "concrete_block"], "floor": ["concrete", "wood_pine"]},
	"store": {"wall": ["plaster_white", "paint_mustard", "plaster_grey"], "floor": ["linoleum_beige", "linoleum_check"]},
	"garage": {"wall": ["concrete_block", "plaster_grey"], "floor": ["concrete"]},
	"hallway": {"wall": ["wallpaper_stripe_green", "plaster_white", "paint_mustard", "wallpaper_floral_rose"], "floor": ["wood_oak", "wood_pine"]},
}

## A rectangle of cells on one level that is one room.
class Room:
	var level: int = 0
	var ch: String = ""
	var rect := Rect2i()
	var purpose: String = ""
	var key: String = ""

	func has(c: Vector2i) -> bool:
		return rect.has_point(c)


var t: TemplateDef
var rng := RandomNumberGenerator.new()
var w: int = 10
var d: int = 9
var seed_v: int = 0
var family: String = ""
## level -> Array of Array[String] (plan rows).
var grid: Dictionary = {}
var rooms: Array[Room] = []
var openings: Array[Dictionary] = []
## Edge key "L:h:c:r" / "L:v:c:r" -> opening id (every edge an opening spans).
var edge_op: Dictionary = {}
var stairs: Array[Dictionary] = []
var props: Array[Dictionary] = []
var sleepers: Array[Dictionary] = []
var traps: Array[Dictionary] = []
var triggers: Array[Dictionary] = []
var decals: Array[Dictionary] = []
var route: Array[Dictionary] = []
var style: Dictionary = {}
var lot := Vector2i.ZERO
var origin := Vector2i.ZERO
## "L:c:r" -> true: cells furniture must stay off (door swings, stairs and wells, the route).
var blocked: Dictionary = {}
## "L:c:r" -> true: cells furniture stands on.
var occupied: Dictionary = {}
var ids: Dictionary = {}
## The door the route starts in front of (shut fast from the street) and the one it leaves by
## (bolted on the inside: the shortcut).
var street_door: Dictionary = {}
var exit_door: Dictionary = {}
var entry: Dictionary = {}
var loot: Room = null
var shortcut: String = ""
## Plan cells outside the building that must stay clear (chimney, the entry approach).
var yard_keep: Dictionary = {}


## A complete building for a template and seed. `lot`: the lot it fills (footprint, x along the
## street, y depth; ZERO = a tight yard of its own). `def_id`: the PoiDef id ("" = template + seed).
static func generate(tdef: TemplateDef, seed: int, lot_size: Vector2i = Vector2i.ZERO, def_id: String = "") -> PoiDef:
	var last: PoiDef = null
	for attempt: int in MAX_TRIES:
		var g: RefCounted = (load("res://src/poi/building_generator.gd") as GDScript).new()
		var s: int = seed if attempt == 0 else Ids.derive_seed(seed, "retry%d" % attempt)
		var made: PoiDef = g.call(&"_make", tdef, s, lot_size, def_id if def_id != "" else default_id(tdef, seed)) as PoiDef
		if made == null:
			continue
		made.gen_seed = seed
		last = made
		var v: PoiValidator = PoiValidator.validate(made)
		if v.errors.is_empty() and v.warnings.is_empty():
			return made
	return last


static func default_id(tdef: TemplateDef, seed: int) -> String:
	return "%s_%06x" % [tdef.id, seed & 0xffffff]


## Whether a template's smallest building, with its yards, fits a lot (x along the street, y depth).
static func fits(tdef: TemplateDef, lot_size: Vector2i) -> bool:
	return tdef.width.x + 2 * SIDE_YARD <= lot_size.x and tdef.depth.x + tdef.setback.x + BACK_YARD <= lot_size.y


# --- Assembly --------------------------------------------------------------------------------------

func _make(tdef: TemplateDef, seed: int, lot_size: Vector2i, def_id: String) -> PoiDef:
	t = tdef
	seed_v = seed
	rng.seed = seed
	lot = lot_size
	var fams: Array = _cfg().get("families", ["Hale"])
	family = str(fams[rng.randi() % maxi(1, fams.size())])
	w = rng.randi_range(t.width.x, t.width.y)
	d = rng.randi_range(t.depth.x, t.depth.y)
	var setback: int = rng.randi_range(t.setback.x, t.setback.y)
	if lot != Vector2i.ZERO:
		w = mini(w, lot.x - 2 * SIDE_YARD)
		# A shallow lot takes a shorter front yard before a shallower house.
		setback = clampi(lot.y - BACK_YARD - t.depth.x, t.setback.x, setback)
		d = mini(d, lot.y - setback - BACK_YARD)
		if w < t.width.x or d < t.depth.x:
			return null
	else:
		lot = Vector2i(w + 2 * SIDE_YARD + rng.randi_range(0, 4), d + setback + BACK_YARD + rng.randi_range(0, 3))
	var slack: int = lot.x - w - 2 * SIDE_YARD
	origin = Vector2i(SIDE_YARD + rng.randi_range(0, slack), lot.y - setback - d)
	origin.y = maxi(origin.y, BACK_YARD)
	match t.archetype:
		"duplex":
			if not _duplex():
				return null
		"store":
			if not _store():
				return null
		"workshop":
			if not _workshop():
				return null
		_:
			if not _house():
				return null
	_windows()
	_route()
	_mark_route()
	_furnish()
	_ensure_loot()
	_people()
	_trap()
	_story_decals()
	_yard()
	_style()
	return _assemble(def_id)


func _cfg() -> Dictionary:
	var db: Node = ContentDB.instance
	return db.call(&"config", &"building_generator") if db != null else {}


func _prop_def(id: String) -> PropDef:
	var db: Node = ContentDB.instance
	return db.call(&"get_def", &"prop", StringName(id)) as PropDef if db != null else null


func _assemble(def_id: String) -> PoiDef:
	var levels: Array = []
	var lis: Array = grid.keys()
	lis.sort()
	for li: int in lis:
		var plan: Array = []
		for row: Array in grid[li]:
			plan.append("".join(PackedStringArray(row)))
		var rd: Dictionary = {}
		for r: Room in rooms:
			if r.level == li:
				rd[r.ch] = _room_def(r)
		levels.append({"level": li, "plan": plan, "rooms": rd})
	var names: PackedStringArray = t.names if not t.names.is_empty() else PackedStringArray(["The {family} Place"])
	var stories: PackedStringArray = t.stories if not t.stories.is_empty() else PackedStringArray(["The {family}s left in a hurry."])
	var raw: Dictionary = {
		"id": def_id, "name": names[rng.randi() % names.size()].format({"family": family}), "tier": t.tier, "zoning": Array(t.zoning),
		"footprint": [lot.x, lot.y], "origin": [origin.x, origin.y], "author": "BuildingGenerator (%s)" % t.id,
		"story": stories[rng.randi() % stories.size()].format({"family": family}),
		"style": style, "levels": levels, "openings": openings, "stairs": stairs, "props": props, "sleepers": sleepers,
		"traps": traps, "triggers": triggers, "decals": decals, "route": route,
		"loot_room": {"room": loot.ch, "level": loot.level}, "shortcuts": [{"opening": shortcut}] if shortcut != "" else [],
	}
	var pd := PoiDef.new()
	var errs: PackedStringArray = pd.parse(raw, &"poi", "generated/%s" % t.id)
	if not errs.is_empty():
		push_warning("BuildingGenerator %s: %s" % [t.id, "; ".join(errs)])
		return null
	pd.template = t.id
	return pd


func _room_def(r: Room) -> Dictionary:
	var p: Array = PURPOSE.get(r.purpose, ["room", "Room"])
	var rt: String = str(p[0])
	var fin: Dictionary = t.finishes.get(r.purpose, t.finishes.get(rt, DEFAULT_FINISH.get(rt, DEFAULT_FINISH["living"])))
	var walls: Array = fin.get("wall", DEFAULT_FINISH.get(rt, DEFAULT_FINISH["living"])["wall"])
	var floors: Array = fin.get("floor", DEFAULT_FINISH.get(rt, DEFAULT_FINISH["living"])["floor"])
	# Finishes drawn from a stream of their own per room, so furniture draws don't shift them.
	var frng := RandomNumberGenerator.new()
	frng.seed = Ids.derive_seed(seed_v, "finish:%d:%s" % [r.level, r.ch])
	return {"name": str(p[1]), "type": rt, "wall": str(walls[frng.randi() % walls.size()]), "floor": str(floors[frng.randi() % floors.size()])}


# --- Plan helpers ----------------------------------------------------------------------------------

func _level(li: int, rows: int = -1) -> void:
	var g: Array = []
	for r: int in (d if rows < 0 else rows):
		var row: Array = []
		for c: int in w:
			row.append(".")
		g.append(row)
	grid[li] = g


func _room(li: int, rect: Rect2i, ch: String, purpose: String) -> Room:
	var r := Room.new()
	r.level = li
	r.ch = ch
	r.rect = rect
	r.purpose = purpose
	r.key = "%s_%d" % [purpose, rooms.size()]
	for y: int in range(rect.position.y, rect.end.y):
		var row: Array = grid[li][y]
		for x: int in range(rect.position.x, rect.end.x):
			row[x] = ch
	rooms.append(r)
	return r


func _at(li: int, c: Vector2i) -> String:
	if not grid.has(li) or c.y < 0 or c.y >= (grid[li] as Array).size() or c.x < 0 or c.x >= w:
		return "."
	return str((grid[li][c.y] as Array)[c.x])


func _room_at(li: int, c: Vector2i) -> Room:
	for r: Room in rooms:
		if r.level == li and r.has(c):
			return r
	return null


static func _nk(li: int, c: Vector2i) -> String:
	return "%d:%d:%d" % [li, c.x, c.y]


func _edge_key(li: int, c: Vector2i, side: int) -> String:
	var e: Array = PoiLayout.side_edge(c, side)
	return PoiLayout.edge_key(li, e[0], e[1])


func _id(base: String) -> String:
	var b: String = base.to_lower().replace(" ", "_").replace("'", "")
	var n: int = int(ids.get(b, 0)) + 1
	ids[b] = n
	return b if n == 1 else "%s_%d" % [b, n]


## An opening on the edge `side` of cell `c` (2 m wide ones span the next cell east / south).
func _open(li: int, c: Vector2i, side: int, type: String, state: String, extra: Dictionary = {}) -> Dictionary:
	var op: Dictionary = {"id": _id(str(extra.get("id", type))), "at": [c.x, c.y], "side": PoiLayout.SIDE_NAMES[side], "type": type, "state": state}
	if li != 0:
		op["level"] = li
	for k: String in extra:
		if k != "id":
			op[k] = extra[k]
	var width: int = int((PoiLayout.OPENING_SPECS[type] as Dictionary)["w"])
	for k2: int in width:
		var cc: Vector2i = c + (Vector2i(k2, 0) if side in [0, 2] else Vector2i(0, k2))
		edge_op[_edge_key(li, cc, side)] = op["id"]
		# The cells each side of a doorway stay clear of furniture (swing, passage).
		blocked[_nk(li, cc)] = true
		blocked[_nk(li, cc + PoiLayout.DIRS[side])] = true
	openings.append(op)
	return op


## Whether the edge on `side` of `c` is free for an opening (no opening on it yet).
func _edge_free(li: int, c: Vector2i, side: int) -> bool:
	return not edge_op.has(_edge_key(li, c, side))


## Shared edges between two rooms on one level: [[cell in a, side toward b], ...].
func _shared(a: Room, b: Room) -> Array:
	var out: Array = []
	for y: int in range(a.rect.position.y, a.rect.end.y):
		for x: int in range(a.rect.position.x, a.rect.end.x):
			for side: int in 4:
				var n: Vector2i = Vector2i(x, y) + PoiLayout.DIRS[side]
				if b.level == a.level and b.has(n):
					out.append([Vector2i(x, y), side])
	return out


## A door (or other opening) between two rooms, on a shared edge away from `avoid` cells (stair
## cells, wells), preferring the middle of the shared wall. Returns {} when there is no room for it.
func _connect(a: Room, b: Room, type: String, state: String, avoid: Dictionary = {}, extra: Dictionary = {}) -> Dictionary:
	var cands: Array = []
	for e: Array in _shared(a, b):
		var c: Vector2i = e[0]
		var side: int = e[1]
		var n: Vector2i = c + PoiLayout.DIRS[side]
		if avoid.has(_nk(a.level, c)) or avoid.has(_nk(a.level, n)) or not _edge_free(a.level, c, side):
			continue
		cands.append(e)
	if cands.is_empty():
		return {}
	# Middle third of the shared wall first.
	var mid: Array = cands.slice(cands.size() / 3, maxi(cands.size() / 3 + 1, cands.size() * 2 / 3))
	var pick: Array = mid[rng.randi() % mid.size()] if not mid.is_empty() else cands[rng.randi() % cands.size()]
	return _open(a.level, pick[0], pick[1], type, state, extra)


## Exterior edges of a room: [[cell, side], ...] facing a cell with nothing built on this level.
func _exterior(r: Room) -> Array:
	var out: Array = []
	for y: int in range(r.rect.position.y, r.rect.end.y):
		for x: int in range(r.rect.position.x, r.rect.end.x):
			for side: int in 4:
				var n: Vector2i = Vector2i(x, y) + PoiLayout.DIRS[side]
				if _at(r.level, n) == ".":
					out.append([Vector2i(x, y), side])
	return out


# --- Archetypes ------------------------------------------------------------------------------------

## A hall from front to back between a day side and a night side (see the class doc); a single
## storey may instead have its hall across the middle (_house_across).
func _house() -> bool:
	var two: bool = t.storeys > 1
	if not two and w >= 9 and d >= 7 and rng.randf() < 0.45:
		return _house_across()
	var hw: int = 2 if two else 1
	if w < hw + 8 or d < (8 if two else 6):
		return false
	_level(0)
	var lw: int = rng.randi_range(4, w - hw - 4)
	var hx: int = lw
	var left := Rect2i(0, 0, lw, d)
	var right := Rect2i(hx + hw, 0, w - hx - hw, d)
	var day_left: bool = rng.randf() < 0.5
	var day: Rect2i = left if day_left else right
	var night: Rect2i = right if day_left else left
	var hall: Room = _room(0, Rect2i(hx, 0, hw, d), "H", "hallway")
	# The flight (two storeys): in the hall column beside the day or the night side, rising from the
	# back toward the front; the other column stays a passage.
	var sc: int = hx + (rng.randi() % 2) if two else hx
	var pc: int = (hx + 1 if sc == hx else hx) if two else hx
	var avoid: Dictionary = {}
	if two:
		stairs.append({"level": 0, "at": [sc, 1], "dir": "S"})
		for k: int in 4:
			avoid[_nk(0, Vector2i(sc, 1 + k))] = true
			avoid[_nk(1, Vector2i(sc, 1 + k))] = true
			blocked[_nk(0, Vector2i(sc, 1 + k))] = true
			blocked[_nk(1, Vector2i(sc, 1 + k))] = true
		blocked[_nk(0, Vector2i(sc, 0))] = true
		blocked[_nk(1, Vector2i(sc, 5))] = true
	# Day side: living room at the front, kitchen behind (a dining room between when it is deep).
	var split: int = rng.randi_range(maxi(3, d - 6), d - 4)
	var living: Room = _room(0, Rect2i(day.position.x, split, day.size.x, d - split), "L", "living")
	var kitchen: Room = _room(0, Rect2i(day.position.x, 0, day.size.x, split), "K", "kitchen")
	# Night side.
	var night_rooms: Array[Room] = []
	if not two:
		var fs: int = rng.randi_range(maxi(3, d - 5), d - 3)
		var front: Room = _room(0, Rect2i(night.position.x, fs, night.size.x, d - fs), "B", "bedroom")
		night_rooms.append(front)
		if fs >= 5:
			var bath_back: bool = rng.randf() < 0.5
			var by: int = 0 if bath_back else fs - 2
			night_rooms.append(_room(0, Rect2i(night.position.x, by, night.size.x, 2), "T", "bath"))
			var cy: int = 2 if bath_back else 0
			night_rooms.append(_room(0, Rect2i(night.position.x, cy, night.size.x, fs - 2), "C", ["kids", "bedroom", "study", "nursery"][rng.randi() % 4]))
		else:
			night_rooms.append(_room(0, Rect2i(night.position.x, 0, night.size.x, fs), "T", "bath"))
	else:
		var fs2: int = rng.randi_range(maxi(3, d - 5), d - 3)
		night_rooms.append(_room(0, Rect2i(night.position.x, fs2, night.size.x, d - fs2), "D", ["dining", "study"][rng.randi() % 2]))
		if fs2 >= 5:
			night_rooms.append(_room(0, Rect2i(night.position.x, 0, night.size.x, 2), "T", "bath"))
			night_rooms.append(_room(0, Rect2i(night.position.x, 2, night.size.x, fs2 - 2), "U", "utility"))
		else:
			night_rooms.append(_room(0, Rect2i(night.position.x, 0, night.size.x, fs2), "U", "utility"))
	# Ground-floor doors: every room opens off the hall (a living room may be open to it).
	if rng.randf() < 0.45:
		if _connect(living, hall, "open", "open", avoid).is_empty():
			return false
		_connect(living, hall, "open", "open", avoid)
	elif _connect(living, hall, "door", ["open", "closed"][rng.randi() % 2], avoid).is_empty():
		return false
	if _connect(kitchen, hall, "door" if rng.randf() < 0.6 else "open", "open" if rng.randf() < 0.5 else "closed", avoid).is_empty():
		return false
	if rng.randf() < 0.5:
		_connect(living, kitchen, "open", "open", avoid)
	for nr: Room in night_rooms:
		if _connect(nr, hall, "door", "closed" if rng.randf() < 0.6 else "open", avoid).is_empty():
			return false
	# Front door bolted from the inside (the shortcut out); the back door at the hall's far end.
	street_door = _open(0, Vector2i(pc, d - 1), 2, "door", "locked_inside", {"id": "front_door"})
	exit_door = street_door
	shortcut = str(exit_door["id"])
	var back: Dictionary = _open(0, Vector2i(pc, 0), 0, "door", "closed", {"id": "back_door"})
	if not two:
		loot = night_rooms[0] if rng.randf() < 0.6 or night_rooms.size() < 3 else night_rooms[2]
	else:
		if not _upper(hx, hw, sc, pc):
			return false
	_pick_entry(back, [living, kitchen] + night_rooms)
	return true


## A hall across the middle of the house (the Merrow House's shape): kitchen, bathroom and a bedroom
## behind it, the living room and a front bedroom before it; the front door opens into the living
## room, the back door into the kitchen.
func _house_across() -> bool:
	_level(0)
	var hb: int = rng.randi_range(3, d - 4)
	var hall: Room = _room(0, Rect2i(0, hb, w, 1), "H", "hallway")
	var kw: int = rng.randi_range(3, mini(5, w - 5))
	var bw: int = w - kw - 2
	var kitchen_left: bool = rng.randf() < 0.5
	var kx: int = 0 if kitchen_left else w - kw
	var tx: int = kw if kitchen_left else (w - kw - 2 if rng.randf() < 0.5 else 0)
	var bx: int = (kw + 2 if kitchen_left else (0 if tx != 0 else 2))
	var kitchen: Room = _room(0, Rect2i(kx, 0, kw, hb), "K", "kitchen")
	var bath: Room = _room(0, Rect2i(tx, 0, 2, hb), "T", "bath")
	var back_bed: Room = _room(0, Rect2i(bx, 0, bw, hb), "C", ["bedroom", "kids", "nursery", "study"][rng.randi() % 4])
	var lw: int = rng.randi_range(4, w - 3)
	var living_left: bool = rng.randf() < 0.5
	var fy: int = hb + 1
	var living: Room = _room(0, Rect2i(0 if living_left else w - lw, fy, lw, d - fy), "L", "living")
	var front_bed: Room = _room(0, Rect2i(lw if living_left else 0, fy, w - lw, d - fy), "B", "bedroom")
	if rng.randf() < 0.4:
		if _connect(living, hall, "open", "open").is_empty():
			return false
		_connect(living, hall, "open", "open")
	elif _connect(living, hall, "door", "open" if rng.randf() < 0.5 else "closed").is_empty():
		return false
	for r: Room in [kitchen, bath, back_bed, front_bed]:
		if _connect(r, hall, "door" if r != kitchen or rng.randf() < 0.6 else "open", "closed" if rng.randf() < 0.6 else "open").is_empty():
			return false
	var fx: int = living.rect.position.x + rng.randi_range(1, living.rect.size.x - 2)
	street_door = _open(0, Vector2i(fx, d - 1), 2, "door", "locked_inside", {"id": "front_door"})
	exit_door = street_door
	shortcut = str(exit_door["id"])
	var back: Dictionary = _open(0, Vector2i(kitchen.rect.position.x + rng.randi_range(1, kw - 2), 0), 0, "door", "closed", {"id": "back_door"})
	loot = front_bed if rng.randf() < 0.5 or back_bed.purpose == "study" else back_bed
	_pick_entry(back, [living, kitchen, back_bed, front_bed])
	return true


## The upper floor of a two-storey house: the hall columns again (the flight's well in one), a
## bedroom or two each side and a bathroom; "cape" sets it back from the front.
func _upper(hx: int, hw: int, sc: int, pc: int) -> bool:
	var du: int = d
	if t.upper == "cape":
		du = d - rng.randi_range(2, 3)
	if du < 6:
		return false
	_level(1)
	# Rows past the upper floor stay outside ("." over the lower roof).
	var hall: Room = _room(1, Rect2i(hx, 0, hw, du), "H", "hallway")
	var avoid: Dictionary = {}
	for k: int in 4:
		avoid[_nk(1, Vector2i(sc, 1 + k))] = true
	var left := Rect2i(0, 0, hx, du)
	var right := Rect2i(hx + hw, 0, w - hx - hw, du)
	var ups: Array[Room] = []
	var chars: Array[String] = ["M", "N", "P", "Q"]
	var ci: int = 0
	var bath_done: bool = false
	for block: Rect2i in [left, right]:
		if du >= 7 and rng.randf() < 0.75:
			var s: int = rng.randi_range(3, du - 3)
			var back_purpose: String = "bath" if not bath_done and rng.randf() < 0.5 else ["bedroom", "kids", "nursery", "study"][rng.randi() % 4]
			if back_purpose == "bath":
				bath_done = true
				s = mini(s, 3)
			ups.append(_room(1, Rect2i(block.position.x, 0, block.size.x, s), chars[ci], back_purpose))
			ci += 1
			ups.append(_room(1, Rect2i(block.position.x, s, block.size.x, du - s), chars[ci], "bedroom"))
			ci += 1
		else:
			ups.append(_room(1, Rect2i(block.position.x, 0, block.size.x, du), chars[ci], "bedroom"))
			ci += 1
	if not bath_done:
		# The smallest back room is the bathroom.
		var best: Room = null
		for r: Room in ups:
			if r.rect.position.y == 0 and (best == null or r.rect.get_area() < best.rect.get_area()):
				best = r
		best.purpose = "bath"
	for r2: Room in ups:
		if _connect(r2, hall, "door", "closed" if rng.randf() < 0.55 else "open", avoid).is_empty():
			return false
	# The loot: the biggest bedroom upstairs.
	for r3: Room in ups:
		if r3.purpose in ["bedroom", "kids", "nursery"] and (loot == null or r3.rect.get_area() > loot.rect.get_area()):
			loot = r3
	return loot != null


## Two units side by side; each has its own bolted front door; the neighbours broke through the
## party wall. The way in is one unit's back door or a window, the loot in the other unit.
func _duplex() -> bool:
	if w < 12 or d < 7:
		return false
	_level(0)
	var uw: int = w / 2
	var units: Array = []
	for u: int in 2:
		var x0: int = 0 if u == 0 else uw
		var ux: int = uw if u == 0 else w - uw
		var split: int = rng.randi_range(3, d - 4)
		var lw: int = rng.randi_range(4, ux - 2) if ux >= 6 else ux
		var front_l: Rect2i = Rect2i(x0, split, lw, d - split) if u == 0 else Rect2i(x0 + ux - lw, split, lw, d - split)
		var front_b: Rect2i = Rect2i(x0 + lw, split, ux - lw, d - split) if u == 0 else Rect2i(x0, split, ux - lw, d - split)
		var tag: Array = ["L", "B", "K", "T"] if u == 0 else ["M", "N", "J", "V"]
		var living: Room = _room(0, front_l, str(tag[0]), "living")
		var bed: Room = _room(0, front_b, str(tag[1]), "bedroom") if front_b.size.x >= 3 else null
		if bed == null and front_b.size.x > 0:
			# Too narrow for a bedroom: the living room takes it.
			living.rect = living.rect.merge(front_b)
			for y: int in range(front_b.position.y, front_b.end.y):
				var row: Array = grid[0][y]
				for x: int in range(front_b.position.x, front_b.end.x):
					row[x] = tag[0]
		var kw: int = rng.randi_range(3, ux - 2) if ux >= 5 else ux
		var kit_r: Rect2i = Rect2i(x0, 0, kw, split) if u == 0 else Rect2i(x0 + ux - kw, 0, kw, split)
		var bath_r: Rect2i = Rect2i(x0 + kw, 0, ux - kw, split) if u == 0 else Rect2i(x0, 0, ux - kw, split)
		var kitchen: Room = _room(0, kit_r, str(tag[2]), "kitchen")
		var bath: Room = _room(0, bath_r, str(tag[3]), "bath" if bath_r.size.x <= 3 else "kids") if bath_r.size.x > 0 else null
		_connect(living, kitchen, "door" if rng.randf() < 0.5 else "open", "open", {})
		if bed != null:
			_connect(bed, living, "door", "closed", {})
		if bath != null:
			var via: Room = bed if bed != null and not _shared(bath, bed).is_empty() and rng.randf() < 0.5 else kitchen
			if _connect(bath, via, "door", "closed", {}).is_empty():
				_connect(bath, kitchen, "door", "closed", {})
		var fd_cell := Vector2i(living.rect.position.x + living.rect.size.x / 2, d - 1)
		var fd: Dictionary = _open(0, fd_cell, 2, "door", "locked_inside", {"id": "front_door_%s" % ("a" if u == 0 else "b")})
		units.append({"living": living, "bed": bed, "kitchen": kitchen, "bath": bath, "door": fd})
	# The party wall: knocked through between the two units' rooms that meet.
	var a: Dictionary = units[0]
	var b: Dictionary = units[1]
	var breach: Dictionary = {}
	for pair: Array in [[a["kitchen"], b["kitchen"]], [a["bath"], b["bath"]], [a["living"], b["living"]], [a["bed"], b["bed"]],
			[a["kitchen"], b["bath"]], [a["bath"], b["kitchen"]]]:
		if pair[0] == null or pair[1] == null or _shared(pair[0], pair[1]).is_empty():
			continue
		breach = _connect(pair[0], pair[1], "breach", "open", {}, {"id": "party_wall_breach"})
		if not breach.is_empty():
			break
	if breach.is_empty():
		return false
	street_door = a["door"]
	exit_door = b["door"]
	shortcut = str(exit_door["id"])
	loot = b["bed"] if b["bed"] != null else b["living"]
	var back: Dictionary = _open(0, Vector2i((a["kitchen"] as Room).rect.position.x + 1, 0), 0, "door", "closed", {"id": "back_door"})
	_pick_entry(back, [a["kitchen"], a["living"]] + ([a["bed"]] if a["bed"] != null else []))
	return true


## A sales floor behind the front with a stock room, an office and a restroom along the back.
func _store() -> bool:
	if w < 9 or d < 9:
		return false
	_level(0)
	var b: int = rng.randi_range(3, 4)
	var floor_r: Room = _room(0, Rect2i(0, b, w, d - b), "F", "store")
	var ow: int = rng.randi_range(3, 4)
	var tw: int = 2
	var sw: int = w - ow - tw
	var order: int = rng.randi() % 3
	var stock: Room
	var office: Room
	var rest: Room
	if order == 0:
		stock = _room(0, Rect2i(0, 0, sw, b), "S", "storage")
		office = _room(0, Rect2i(sw, 0, ow, b), "O", "office")
		rest = _room(0, Rect2i(sw + ow, 0, tw, b), "T", "bath")
	elif order == 1:
		rest = _room(0, Rect2i(0, 0, tw, b), "T", "bath")
		office = _room(0, Rect2i(tw, 0, ow, b), "O", "office")
		stock = _room(0, Rect2i(tw + ow, 0, sw, b), "S", "storage")
	else:
		office = _room(0, Rect2i(0, 0, ow, b), "O", "office")
		stock = _room(0, Rect2i(ow, 0, sw, b), "S", "storage")
		rest = _room(0, Rect2i(ow + sw, 0, tw, b), "T", "bath")
	_connect(stock, floor_r, "door", "closed", {}, {"id": "stock_door"})
	_connect(office, floor_r, "door", "closed", {}, {"id": "office_door"})
	if _connect(rest, floor_r, "door", "closed", {}).is_empty():
		_connect(rest, stock, "door", "closed", {})
	# The front: double doors chained or barricaded, display windows either side.
	var fx: int = w / 2 - 1
	var chained: bool = rng.randf() < 0.6
	street_door = _open(0, Vector2i(fx, d - 1), 2, "door2", "locked" if chained else "barricaded",
		{"id": "front_doors", "lock": "chain"} if chained else {"id": "front_doors", "barricade": "furniture"})
	# Back door out of the stock room: bolted (the shortcut) or the way in.
	exit_door = _open(0, Vector2i(stock.rect.position.x + stock.rect.size.x / 2, 0), 0, "door", "locked_inside", {"id": "back_door"})
	shortcut = str(exit_door["id"])
	loot = office if rng.randf() < 0.55 else stock
	# Display windows; one is smashed in (the way in) unless a side window is.
	var win: Array = []
	for x: int in range(1, w - 2):
		if absi(x - fx) >= 3 and absi(x + 1 - fx) >= 3 and _edge_free(0, Vector2i(x, d - 1), 2) and _edge_free(0, Vector2i(x + 1, d - 1), 2):
			var o: Dictionary = _open(0, Vector2i(x, d - 1), 2, "window2", ["closed", "boarded", "closed"][rng.randi() % 3], {"id": "display_window"})
			win.append(o)
	if win.is_empty():
		return false
	var way: Dictionary = win[rng.randi() % win.size()]
	way["state"] = "broken"
	entry = {"op": way, "outside": Vector2i(int(way["at"][0]), d + 1), "inside": Vector2i(int(way["at"][0]), d - 1), "label": "A display window is smashed in"}
	return true


## A bay behind chained double doors, an office at the front corner, a tool crib behind it.
func _workshop() -> bool:
	if w < 9 or d < 9:
		return false
	_level(0)
	var sw: int = rng.randi_range(3, 4)
	var gw: int = w - sw
	var bay_left: bool = rng.randf() < 0.5
	var bx: int = 0 if bay_left else sw
	var sx: int = gw if bay_left else 0
	var bay: Room = _room(0, Rect2i(bx, 0, gw, d), "G", "garage")
	var oh: int = rng.randi_range(3, 4)
	var office: Room = _room(0, Rect2i(sx, d - oh, sw, oh), "O", "office")
	var crib: Room = _room(0, Rect2i(sx, 0, sw, d - oh), "S", "storage")
	_connect(office, bay, "door", "closed", {}, {"id": "office_door"})
	_connect(crib, bay, "door", "closed", {}, {"id": "crib_door"})
	if rng.randf() < 0.5:
		_connect(crib, office, "door", "closed", {})
	var dx: int = bx + gw / 2 - 1
	street_door = _open(0, Vector2i(dx, d - 1), 2, "door2", "locked", {"id": "bay_doors", "lock": "chain"})
	exit_door = _open(0, Vector2i(sx + sw / 2, d - 1), 2, "door", "locked_inside", {"id": "office_front_door"})
	shortcut = str(exit_door["id"])
	var back: Dictionary = _open(0, Vector2i(bx + rng.randi_range(1, gw - 2), 0), 0, "door", "closed", {"id": "back_door"})
	loot = crib if rng.randf() < 0.6 else office
	_pick_entry(back, [bay, crib])
	return true


## The way in: the back door left shut but unlocked, a smashed side window, or a hole clawed through
## a side wall; the back door is barricaded when it is not the way in.
func _pick_entry(back: Dictionary, ground: Array) -> void:
	var roll: float = rng.randf()
	if roll < 0.4:
		back["state"] = "closed" if rng.randf() < 0.6 else "broken"
		var bc: Vector2i = Vector2i(int(back["at"][0]), int(back["at"][1]))
		entry = {"op": back, "outside": bc + Vector2i(0, -2), "inside": bc, "label": "Round the back: the back door gives"}
		return
	# A side window or breach on a ground-floor room's east or west wall, away from the corners.
	var cands: Array = []
	for r: Variant in ground:
		if r == null:
			continue
		for e: Array in _exterior(r as Room):
			var c: Vector2i = e[0]
			var side: int = e[1]
			if side in [1, 3] and c.y > 0 and c.y < d - 1 and _edge_free(0, c, side) and _edge_free(0, c + Vector2i(0, 1), side) \
					and _edge_free(0, c - Vector2i(0, 1), side):
				cands.append(e)
	if cands.is_empty():
		back["state"] = "closed"
		var bc2: Vector2i = Vector2i(int(back["at"][0]), int(back["at"][1]))
		entry = {"op": back, "outside": bc2 + Vector2i(0, -2), "inside": bc2, "label": "Round the back: the back door gives"}
		return
	var pick: Array = cands[rng.randi() % cands.size()]
	var pc: Vector2i = pick[0]
	var ps: int = pick[1]
	var breach: bool = roll > 0.85
	var op: Dictionary = _open(0, pc, ps, "breach" if breach else "window", "open" if breach else "broken", {"id": "clawed_hole" if breach else "side_window"})
	entry = {"op": op, "outside": pc + PoiLayout.DIRS[ps] * 2, "inside": pc,
		"label": "Round the side: something clawed through the wall" if breach else "Round the side: a window is smashed in"}
	back["state"] = "barricaded"
	back["barricade"] = "furniture" if rng.randf() < 0.5 else "boards"


# --- Windows ---------------------------------------------------------------------------------------

## Windows on every room's outside walls: one in each run of wall up to 3 m, more along longer ones,
## off the corners; living rooms and sales floors get 2 m ones on the front where there is room.
## Most stay shut, some are boarded.
func _windows() -> void:
	for r: Room in rooms:
		if r.purpose == "hallway" and rng.randf() < 0.5:
			continue
		var by_side: Dictionary = {}
		for e: Array in _exterior(r):
			var side: int = e[1]
			if not by_side.has(side):
				by_side[side] = []
			(by_side[side] as Array).append(e[0])
		for side: int in by_side:
			var cells: Array = by_side[side]
			cells.sort_custom(func(a: Vector2i, b: Vector2i) -> bool: return a.x < b.x if side in [0, 2] else a.y < b.y)
			var n: int = cells.size()
			if n < 2 and r.purpose != "bath":
				continue
			var step: int = 3 if r.purpose != "bath" else 99
			var i: int = 1 if n >= 3 else 0
			while i < n:
				var c: Vector2i = cells[i]
				var along := Vector2i(1, 0) if side in [0, 2] else Vector2i(0, 1)
				var wide: bool = r.purpose in ["living", "store"] and side == 2 and i + 1 < n - 1 and cells.has(c + along) and rng.randf() < 0.6
				if _edge_free(r.level, c, side) and _edge_free(r.level, c - along, side) and _edge_free(r.level, c + along, side) \
						and (not wide or (_edge_free(r.level, c + along, side) and _edge_free(r.level, c + along * 2, side))):
					var st: String = "boarded" if rng.randf() < 0.22 else "closed"
					_open(r.level, c, side, "window2" if wide else "window", st, {"id": "%s_window" % r.purpose})
					i += step + (1 if wide else 0)
				else:
					i += 1


# --- Route -----------------------------------------------------------------------------------------

## The dungeon-lite route: the bolted front, round to the way in, the loot room, out through the
## front (or the shortcut) after drawing its bolt.
func _route() -> void:
	var fd: Vector2i = Vector2i(int(exit_door["at"][0]), int(exit_door["at"][1]))
	var sx: int = int(street_door["at"][0])
	route.append({"at": [sx, d + 1], "label": "The front is shut fast"})
	route.append({"at": [(entry["outside"] as Vector2i).x, (entry["outside"] as Vector2i).y], "label": str(entry["label"])})
	route.append({"at": [(entry["inside"] as Vector2i).x, (entry["inside"] as Vector2i).y], "label": "Inside"})
	if loot.level > 0:
		for s: Dictionary in stairs:
			route.append({"at": [int(s["at"][0]), 5], "level": 1, "label": "Upstairs"})
	var lc: Vector2i = loot.rect.get_center()
	route.append({"at": [lc.x, lc.y], "level": loot.level, "label": "%s (loot)" % PURPOSE.get(loot.purpose, ["", "Back room"])[1]})
	route.append({"at": [fd.x, fd.y], "label": "Draw the bolt"})
	route.append({"at": [fd.x, fd.y + 2] if str(exit_door["side"]) == "S" else [fd.x, fd.y - 2], "label": "Out"})
	for wp: Dictionary in route:
		if int(wp.get("level", 0)) == 0:
			wp.erase("level")


## Runs the validator over the bare plan to learn the route corridor; furniture stays off it.
func _mark_route() -> void:
	var raw: Dictionary = _bare_raw()
	var pd := PoiDef.new()
	if not pd.parse(raw, &"poi", "generated/%s" % t.id).is_empty():
		return
	var v: PoiValidator = PoiValidator.validate(pd)
	for path: Array in v.paths:
		for node: Variant in path:
			if node is Array:
				blocked[_nk(int(node[0]), node[1])] = true
	for wp: Dictionary in route:
		blocked[_nk(int(wp.get("level", 0)), Vector2i(int(wp["at"][0]), int(wp["at"][1])))] = true


func _bare_raw() -> Dictionary:
	var levels: Array = []
	var lis: Array = grid.keys()
	lis.sort()
	for li: int in lis:
		var plan: Array = []
		for row: Array in grid[li]:
			plan.append("".join(PackedStringArray(row)))
		var rd: Dictionary = {}
		for r: Room in rooms:
			if r.level == li:
				rd[r.ch] = {"type": str((PURPOSE.get(r.purpose, ["room"]) as Array)[0])}
		levels.append({"level": li, "plan": plan, "rooms": rd})
	return {"id": "bare", "tier": 1, "footprint": [lot.x, lot.y], "origin": [origin.x, origin.y], "levels": levels,
		"openings": openings, "stairs": stairs, "route": route, "style": {"floor_height": t.floor_height}}


# --- Furniture -------------------------------------------------------------------------------------

func _furnish() -> void:
	for r: Room in rooms:
		var list: Array = FURNITURE.get(r.purpose, [])
		var placed_counters: Array = []
		for item: Array in list:
			if rng.randf() > float(item[2]):
				continue
			var pid: String = str(item[0])
			match str(item[1]):
				"wall":
					var p: Dictionary = _place_wall(r, pid)
					if not p.is_empty() and pid.begins_with("kitchen_counter"):
						placed_counters.append(p)
				"high":
					_place_high(r, pid, placed_counters)
				"table":
					_place_table(r, pid)
				"rug":
					_place_free(r, pid, false)
				"aisle":
					for k: int in rng.randi_range(2, 5):
						_place_free(r, pid, true)
				"car":
					_place_free(r, pid, true)


## Cells a prop of this size covers against the wall `side` of cell `c` (along the wall from c,
## east or south, and into the room).
func _cover(c: Vector2i, side: int, along: int, deep: int) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	var a := Vector2i(1, 0) if side in [0, 2] else Vector2i(0, 1)
	var inward: Vector2i = -PoiLayout.DIRS[side]
	for i: int in along:
		for j: int in deep:
			out.append(c + a * i + inward * j)
	return out


func _free_cell(r: Room, c: Vector2i) -> bool:
	return r.has(c) and not blocked.has(_nk(r.level, c)) and not occupied.has(_nk(r.level, c))


func _solid(li: int, c: Vector2i, side: int) -> bool:
	if not _edge_free(li, c, side):
		return false
	var n: Vector2i = c + PoiLayout.DIRS[side]
	var here: String = _at(li, c)
	var there: String = _at(li, n)
	return here != there


## A prop with its back to a solid wall, on cells off the route, the stairs and the doorways.
func _place_wall(r: Room, pid: String) -> Dictionary:
	var pd: PropDef = _prop_def(pid)
	if pd == null:
		return {}
	var along: int = maxi(1, ceili(pd.size.x - 0.2))
	var deep: int = maxi(1, ceili(pd.size.z - 0.2))
	var cands: Array = []
	for y: int in range(r.rect.position.y, r.rect.end.y):
		for x: int in range(r.rect.position.x, r.rect.end.x):
			for side: int in 4:
				var c := Vector2i(x, y)
				var cells: Array[Vector2i] = _cover(c, side, along, deep)
				var ok: bool = true
				for cc: Vector2i in cells:
					if not _free_cell(r, cc):
						ok = false
						break
				if not ok:
					continue
				var a := Vector2i(1, 0) if side in [0, 2] else Vector2i(0, 1)
				for i: int in along:
					if not _solid(r.level, c + a * i, side):
						ok = false
						break
				if ok:
					cands.append([c, side, cells])
	if cands.is_empty():
		return {}
	var pick: Array = cands[rng.randi() % cands.size()]
	var c0: Vector2i = pick[0]
	var s0: int = pick[1]
	var a0 := Vector2i(1, 0) if s0 in [0, 2] else Vector2i(0, 1)
	var centre: Vector2 = Vector2(c0) + Vector2(0.5, 0.5) + Vector2(a0) * (float(along) - 1.0) * 0.5
	for cc2: Vector2i in pick[2] as Array[Vector2i]:
		occupied[_nk(r.level, cc2)] = true
	var p: Dictionary = {"prop": pid, "pos": [snappedf(centre.x, 0.01), snappedf(centre.y, 0.01)], "against": PoiLayout.SIDE_NAMES[s0]}
	return _add_prop(r, p, pd)


func _add_prop(r: Room, p: Dictionary, pd: PropDef) -> Dictionary:
	if r.level != 0:
		p["level"] = r.level
	if pd.container != &"" or pd.has_tag("container"):
		p["id"] = _id("%s_%s" % [r.purpose, pd.id])
	props.append(p)
	return p


## A wall-mounted prop (medicine cabinet, kitchen wall cabinet over a counter).
func _place_high(r: Room, pid: String, over: Array) -> void:
	var pd: PropDef = _prop_def(pid)
	if pd == null:
		return
	var cands: Array = []
	if pid == "kitchen_wall_cabinet":
		for p: Dictionary in over:
			cands.append([Vector2i(floori(float(p["pos"][0])), floori(float(p["pos"][1]))), PoiLayout.SIDES[str(p["against"])]])
	else:
		for y: int in range(r.rect.position.y, r.rect.end.y):
			for x: int in range(r.rect.position.x, r.rect.end.x):
				for side: int in 4:
					if _solid(r.level, Vector2i(x, y), side) and not blocked.has(_nk(r.level, Vector2i(x, y))):
						cands.append([Vector2i(x, y), side])
	if cands.is_empty():
		return
	var pick: Array = cands[rng.randi() % cands.size()]
	var c: Vector2i = pick[0]
	_add_prop(r, {"prop": pid, "at": [c.x, c.y], "against": PoiLayout.SIDE_NAMES[int(pick[1])], "height": 1.45 if pid == "kitchen_wall_cabinet" else 1.3}, pd)


## A table on a free cell with a free cell each side for a chair (facing it).
func _place_table(r: Room, pid: String) -> void:
	var pd: PropDef = _prop_def(pid)
	if pd == null:
		return
	var cands: Array[Vector2i] = []
	for y: int in range(r.rect.position.y, r.rect.end.y):
		for x: int in range(r.rect.position.x + 1, r.rect.end.x - 1):
			var c := Vector2i(x, y)
			if _free_cell(r, c) and _free_cell(r, c + Vector2i(1, 0)) and _free_cell(r, c - Vector2i(1, 0)):
				cands.append(c)
	if cands.is_empty():
		return
	var c0: Vector2i = cands[rng.randi() % cands.size()]
	for dx: int in [-1, 0, 1]:
		occupied[_nk(r.level, c0 + Vector2i(dx, 0))] = true
	_add_prop(r, {"prop": pid, "pos": [c0.x + 0.5, c0.y + 0.5]}, pd)
	var chair: String = "kitchen_chair" if r.purpose == "kitchen" else "chair_wood"
	var cd: PropDef = _prop_def(chair)
	if cd == null:
		return
	_add_prop(r, {"prop": chair, "pos": [c0.x - 0.3, c0.y + 0.5], "rot": 90}, cd)
	_add_prop(r, {"prop": chair, "pos": [c0.x + 1.3, c0.y + 0.5], "rot": -90}, cd)


## A free-standing prop (rug, shelving, a wreck) on free cells in the room, turned by its fit.
func _place_free(r: Room, pid: String, solid_body: bool) -> void:
	var pd: PropDef = _prop_def(pid)
	if pd == null:
		return
	var sx: int = maxi(1, ceili(pd.size.x - 0.15))
	var sz: int = maxi(1, ceili(pd.size.z - 0.15))
	var cands: Array = []
	for turn: int in 2:
		var ax: int = sx if turn == 0 else sz
		var az: int = sz if turn == 0 else sx
		for y: int in range(r.rect.position.y, r.rect.end.y - az + 1):
			for x: int in range(r.rect.position.x, r.rect.end.x - ax + 1):
				var ok: bool = true
				for j: int in az:
					for i: int in ax:
						if not _free_cell(r, Vector2i(x + i, y + j)):
							ok = false
				# Shelving and wrecks keep a cell free round them where the room allows.
				if ok:
					cands.append([Vector2i(x, y), ax, az, turn])
	if cands.is_empty():
		return
	var pick: Array = cands[rng.randi() % cands.size()]
	var c: Vector2i = pick[0]
	for j2: int in int(pick[2]):
		for i2: int in int(pick[1]):
			occupied[_nk(r.level, c + Vector2i(i2, j2))] = true
	var centre: Vector2 = Vector2(c) + Vector2(float(pick[1]), float(pick[2])) * 0.5
	var rot: float = 0.0 if int(pick[3]) == 0 else 90.0
	if solid_body:
		rot += 180.0 if rng.randf() < 0.5 else 0.0
	_add_prop(r, {"prop": pid, "pos": [snappedf(centre.x, 0.01), snappedf(centre.y, 0.01)], "rot": rot}, pd)


## The loot room always holds a container: a dropped duffel bag when the furniture left none.
func _ensure_loot() -> void:
	for p: Dictionary in props:
		var lvl: int = int(p.get("level", 0))
		var pos: Array = p.get("pos", p.get("at", [0, 0]))
		if lvl == loot.level and loot.has(Vector2i(floori(float(pos[0])), floori(float(pos[1])))) and p.has("id"):
			return
	for pid: String in ["duffel_bag", "backpack_dropped", "cardboard_box"]:
		var before: int = props.size()
		_place_free(loot, pid, false)
		if props.size() > before:
			return
	# Nothing fits off the route: a backpack on any loot-room cell (the route keeps a body's width).
	var c: Vector2i = loot.rect.position
	_add_prop(loot, {"prop": "backpack_dropped", "pos": [c.x + 0.25, c.y + 0.25], "rot": 30.0, "route_ok": true}, _prop_def("backpack_dropped"))


# --- Sleepers, ambush, trap ------------------------------------------------------------------------

func _free_for_body(r: Room) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	for y: int in range(r.rect.position.y, r.rect.end.y):
		for x: int in range(r.rect.position.x, r.rect.end.x):
			var c := Vector2i(x, y)
			var k: String = _nk(r.level, c)
			if not occupied.has(k) and not _stair_cell(r.level, c):
				out.append(c)
	return out


func _stair_cell(li: int, c: Vector2i) -> bool:
	for s: Dictionary in stairs:
		var sc := Vector2i(int(s["at"][0]), int(s["at"][1]))
		if c.x == sc.x and c.y >= sc.y and c.y < sc.y + 4 and (li == 0 or li == 1):
			return true
	return false


func _prop_in(r: Room, prefix: String) -> Dictionary:
	for p: Dictionary in props:
		if str(p["prop"]).begins_with(prefix) and int(p.get("level", 0)) == r.level:
			var pos: Array = p["pos"] if p.has("pos") else p["at"]
			if r.has(Vector2i(floori(float(pos[0])), floori(float(pos[1])))):
				return p
	return {}


## The ambush in the loot room (a body on the bed, one crouched in a corner) woken when its door is
## opened, and a few ordinary sleepers about the house.
func _people() -> void:
	var count: int = rng.randi_range(t.sleepers.x, t.sleepers.y)
	var loot_door: Dictionary = {}
	for op: Dictionary in openings:
		if str(op["type"]) == "door" and int(op.get("level", 0)) == loot.level and str(op["state"]) in ["closed", "open"]:
			var c := Vector2i(int(op["at"][0]), int(op["at"][1]))
			var n: Vector2i = c + PoiLayout.DIRS[PoiLayout.SIDES[str(op["side"])]]
			if (loot.has(c) and not loot.has(n)) or (loot.has(n) and not loot.has(c)):
				loot_door = op
				break
	var placed: int = 0
	var bed: Dictionary = _prop_in(loot, "bed_")
	if not bed.is_empty() and bed.has("id") == false:
		bed["id"] = _id("loot_bed")
	if not bed.is_empty():
		_sleeper(loot, Vector2(float(bed["pos"][0]), float(bed["pos"][1])), "lie", "loot", {"anchor": str(bed["id"])})
		placed += 1
	for k: int in (1 if placed > 0 else 2):
		var free: Array[Vector2i] = _free_for_body(loot)
		if free.is_empty():
			break
		var c2: Vector2i = free[rng.randi() % free.size()]
		_sleeper(loot, Vector2(c2) + Vector2(0.5, 0.5), "crouch" if rng.randf() < 0.6 else "stand", "loot", {})
		placed += 1
	if placed > 0:
		if not loot_door.is_empty():
			loot_door["state"] = "closed"
			triggers.append({"id": "loot_door_opened", "group": "loot", "on": "opening", "opening": loot_door["id"], "delay": 0.35})
		else:
			triggers.append({"id": "loot_room_entered", "group": "loot", "on": "room", "room": loot.ch, "level": loot.level, "delay": 0.2})
	# The rest about the house: one in the hall or the biggest room, one on the couch.
	var others: Array[Room] = []
	for r: Room in rooms:
		if r != loot:
			others.append(r)
	var guard: int = 0
	while placed < count and guard < 12 and not others.is_empty():
		guard += 1
		var r2: Room = others[rng.randi() % others.size()]
		var couch: Dictionary = _prop_in(r2, "couch")
		if not couch.is_empty() and not couch.has("used"):
			couch["used"] = true
			if not couch.has("id"):
				couch["id"] = _id("couch")
			_sleeper(r2, Vector2(float(couch["pos"][0]), float(couch["pos"][1])), "sit", "", {"anchor": str(couch["id"])})
			placed += 1
			continue
		var cells: Array[Vector2i] = _free_for_body(r2)
		if cells.is_empty():
			continue
		var c3: Vector2i = cells[rng.randi() % cells.size()]
		if rng.randf() < 0.25 and r2.purpose != "hallway":
			_sleeper(r2, Vector2(c3) + Vector2(0.5, 0.5), "lie", "", {"anchor": "floor", "enemy": "dragger"})
		else:
			_sleeper(r2, Vector2(c3) + Vector2(0.5, 0.5), "stand" if rng.randf() < 0.6 else "crouch", "", {})
		placed += 1
	for p: Dictionary in props:
		p.erase("used")


func _sleeper(r: Room, pos: Vector2, pose: String, group: String, extra: Dictionary) -> void:
	var s: Dictionary = {"id": _id("%s_%s" % [r.purpose, pose]), "pos": [snappedf(pos.x, 0.01), snappedf(pos.y, 0.01)],
		"enemy": str(extra.get("enemy", "hollow")), "pose": pose, "rot": float(rng.randi_range(0, 7) * 45)}
	if r.level != 0:
		s["level"] = r.level
	if group != "":
		s["group"] = group
	if extra.has("anchor"):
		s["anchor"] = extra["anchor"]
	occupied[_nk(r.level, Vector2i(floori(pos.x), floori(pos.y)))] = true
	sleepers.append(s)


## One gentle trap: loose boards in the hall, a bear trap under the way in, or a can chime across
## the loot room's doorway.
func _trap() -> void:
	var roll: float = rng.randf()
	var hall: Room = null
	for r: Room in rooms:
		if r.purpose == "hallway" and r.level == 0:
			hall = r
	if roll < 0.45 and hall != null and hall.rect.size.x > hall.rect.size.y:
		# A hall across the house: two boards side by side along it.
		var x0: int = rng.randi_range(1, maxi(1, hall.rect.size.x - 3))
		traps.append({"id": "loose_boards", "type": "creaky_floor", "at": [x0, hall.rect.position.y], "size": [2, 1]})
		return
	if roll < 0.45 and hall != null:
		var col: int = hall.rect.position.x
		for c: Vector2i in [Vector2i(hall.rect.position.x, 0), Vector2i(hall.rect.end.x - 1, 0)]:
			if not _stair_cell(0, Vector2i(c.x, 2)):
				col = c.x
		var y0: int = rng.randi_range(maxi(1, d / 2 - 2), d - 3)
		if not _stair_cell(0, Vector2i(col, y0)) and not _stair_cell(0, Vector2i(col, y0 + 1)):
			traps.append({"id": "loose_boards", "type": "creaky_floor", "at": [col, y0], "size": [1, 2]})
			return
	var eo: Dictionary = entry.get("op", {})
	if roll < 0.75 and not eo.is_empty() and str(eo["side"]) in ["E", "W"]:
		var oc := Vector2i(int(eo["at"][0]), int(eo["at"][1]))
		var out_c: Vector2i = oc + PoiLayout.DIRS[PoiLayout.SIDES[str(eo["side"])]]
		var spot: Vector2i = out_c + Vector2i(0, 1 if rng.randf() < 0.5 else -1)
		traps.append({"id": "yard_bear_trap", "type": "bear_trap", "pos": [spot.x + 0.5, spot.y + 0.5]})
		yard_keep[spot] = true
		return
	for op: Dictionary in openings:
		if str(op["type"]) == "door" and int(op.get("level", 0)) == loot.level:
			var c2 := Vector2i(int(op["at"][0]), int(op["at"][1]))
			var side: int = PoiLayout.SIDES[str(op["side"])]
			var n: Vector2i = c2 + PoiLayout.DIRS[side]
			if loot.has(n) and not loot.has(c2) and not _stair_cell(loot.level, c2):
				traps.append({"id": "loot_door_chime", "type": "can_chime", "at": [c2.x, c2.y], "side": op["side"], "level": loot.level})
				return
			if loot.has(c2) and not loot.has(n) and not _stair_cell(loot.level, n) and _room_at(loot.level, n) != null:
				traps.append({"id": "loot_door_chime", "type": "can_chime", "at": [n.x, n.y], "side": PoiLayout.SIDE_NAMES[(side + 2) % 4], "level": loot.level})
				return


## The marks that tell the story: blood where the way in is, survivors' marks by the front door.
func _story_decals() -> void:
	var ins: Vector2i = entry.get("inside", Vector2i.ZERO)
	decals.append({"decal": ["blood_trail", "footprints_mud"][rng.randi() % 2], "at": [ins.x, ins.y], "side": "floor", "size": [0.9, 1.5],
		"rot": float(rng.randi_range(0, 359))})
	var fd := Vector2i(int(exit_door["at"][0]), int(exit_door["at"][1]))
	var fl: int = int(exit_door.get("level", 0))
	for side: int in [3, 1, 0]:
		if _solid(fl, fd, side):
			decals.append({"decal": ["survivor_marks_a", "survivor_marks_b", "survivor_marks_c"][rng.randi() % 3], "at": [fd.x, fd.y],
				"side": PoiLayout.SIDE_NAMES[side], "height": 1.4, "size": [0.8, 0.7]})
			break
	var lc: Vector2i = loot.rect.get_center()
	for side2: int in 4:
		if _solid(loot.level, lc, side2):
			var dd: Dictionary = {"decal": "blood_handprint", "at": [lc.x, lc.y], "side": PoiLayout.SIDE_NAMES[side2], "height": 1.2, "size": [0.45, 0.45]}
			if loot.level != 0:
				dd["level"] = loot.level
			decals.append(dd)
			break


# --- Yard, style -----------------------------------------------------------------------------------

## A porch, a chimney, fences along the lot, a mailbox at the walk, the odd wreck and woodpile.
func _yard() -> void:
	var front_x: int = int(street_door["at"][0])
	# Plan-space bounds of the lot.
	var lx0: float = -float(origin.x)
	var lx1: float = float(lot.x - origin.x)
	var lz0: float = -float(origin.y)
	var lz1: float = float(lot.y - origin.y)
	var walk: Vector2 = Vector2(front_x + 0.5, lz1)
	# Keep the walk, the route's yard cells and the way in clear.
	for wp: Dictionary in route:
		if int(wp.get("level", 0)) == 0:
			for dz: int in [-1, 0, 1]:
				for dx: int in [-1, 0, 1]:
					yard_keep[Vector2i(int(wp["at"][0]) + dx, int(wp["at"][1]) + dz)] = true
	if t.porch > 0.0 and rng.randf() < t.porch:
		var from: int = 0 if rng.randf() < 0.5 else maxi(0, front_x - rng.randi_range(2, 4))
		var to: int = w - 1 if from == 0 else mini(w - 1, front_x + rng.randi_range(2, 4))
		style["porch"] = {"side": "S", "from": from, "to": to, "depth": 2, "steps": [front_x]}
	if t.chimney > 0.0 and rng.randf() < t.chimney:
		var side_x: int = -1 if rng.randf() < 0.5 else w
		var cz: int = rng.randi_range(1, maxi(1, d - 3))
		var cell := Vector2i(side_x, cz)
		var eo: Dictionary = entry.get("op", {})
		var clear: bool = not yard_keep.has(cell) and not yard_keep.has(cell + Vector2i(0, 1)) and not yard_keep.has(cell - Vector2i(0, 1))
		if clear and not eo.is_empty():
			var ec := Vector2i(int(eo["at"][0]), int(eo["at"][1]))
			clear = absi(ec.y - cz) > 2 or (side_x < 0) != (str(eo["side"]) == "W")
		if clear:
			style["chimney"] = [cell.x, cell.y]
			yard_keep[cell] = true
	# A picket fence along the street edge with a gap at the walk.
	if rng.randf() < 0.55:
		var z: float = lz1 - 0.4
		var x: float = lx0 + 1.0
		while x + 2.0 <= lx1 - 0.5:
			if absf(x + 1.0 - walk.x) > 1.8:
				props.append({"prop": "fence_picket_2m", "pos": [snappedf(x + 1.0, 0.01), snappedf(z, 0.01)], "rot": 0.0, "variant": ["clean", "worn", "worn", "destroyed"][rng.randi() % 4]})
			x += 2.0
	# Board fence along the back of the lot.
	if rng.randf() < 0.45:
		var zb: float = lz0 + 0.4
		var xb: float = lx0 + 1.0
		while xb + 2.0 <= lx1 - 0.5:
			if rng.randf() < 0.85:
				props.append({"prop": "fence_wood_2m", "pos": [snappedf(xb + 1.0, 0.01), snappedf(zb, 0.01)], "rot": 0.0, "variant": ["worn", "worn", "destroyed"][rng.randi() % 3]})
			xb += 2.0
	# The mailbox by the walk.
	if t.archetype != "store" or rng.randf() < 0.3:
		props.append({"id": _id("mailbox"), "prop": "mailbox_rural", "pos": [snappedf(walk.x + 1.3, 0.01), snappedf(lz1 - 1.0, 0.01)], "rot": float(rng.randi_range(-8, 8))})
	# Odds and ends in the side and back yards, off the route's cells.
	var junk: Array = [["woodpile", 0.4], ["wheelbarrow", 0.3], ["trash_bag", 0.6], ["tire", 0.3], ["barrel_metal", 0.3], ["bicycle_rusty", 0.2]]
	if t.archetype == "workshop":
		junk.append_array([["road_tire_stack", 0.6], ["road_oil_drum", 0.6], ["pallet", 0.5]])
	for j: Array in junk:
		if rng.randf() > float(j[1]):
			continue
		for attempt: int in 6:
			var px: float = rng.randf_range(lx0 + 1.0, lx1 - 1.0)
			var pz: float = rng.randf_range(lz0 + 1.0, float(d) + 1.0)
			var cell2 := Vector2i(floori(px), floori(pz))
			if cell2.x >= -1 and cell2.x <= w and cell2.y >= -1 and cell2.y <= d + 2:
				continue
			if yard_keep.has(cell2):
				continue
			yard_keep[cell2] = true
			var e: Dictionary = {"prop": str(j[0]), "pos": [snappedf(px, 0.01), snappedf(pz, 0.01)], "rot": float(rng.randi_range(0, 359))}
			if str(j[0]) == "trash_bag":
				e["id"] = _id("yard_trash")
			props.append(e)
			break
	# A wreck in the drive beside the house when the lot is wide enough.
	var east: float = lx1 - float(w)
	if east >= 4.2 and rng.randf() < 0.45:
		var cx: float = float(w) + east * 0.5
		var cz2: float = float(d) - 1.0 + rng.randf_range(-1.0, 1.0)
		var ok: bool = true
		for dz2: int in range(-3, 4):
			for dx2: int in [-1, 0, 1]:
				if yard_keep.has(Vector2i(floori(cx) + dx2, floori(cz2) + dz2)):
					ok = false
		if ok:
			props.append({"id": _id("drive_wreck"), "prop": ["car_sedan_wreck", "pickup_wreck"][rng.randi() % 2], "pos": [snappedf(cx, 0.01), snappedf(cz2, 0.01)],
				"rot": float(rng.randi_range(-10, 10))})


func _style() -> void:
	var dec: float = snappedf(rng.randf_range(t.decay.x, t.decay.y), 0.01)
	style["exterior"] = t.exteriors[rng.randi() % t.exteriors.size()]
	style["interior"] = "plaster_white"
	style["floor"] = "wood_pine"
	style["ceiling"] = "plaster_white"
	style["floor_height"] = t.floor_height
	style["decay"] = dec
	style["damaged_walls"] = snappedf(0.02 + dec * 0.08, 0.01)
	style["prop_condition"] = "worn"
	style["scatter"] = {"density": snappedf(rng.randf_range(0.3, 0.5), 0.01)}
	var roofs: Array = t.roofs if not t.roofs.is_empty() else [{"type": "gable", "pitch": [24, 34]}]
	var total: float = 0.0
	for rf: Dictionary in roofs:
		total += float(rf.get("weight", 1.0))
	var x: float = rng.randf() * total
	var pick: Dictionary = roofs.back()
	for rf2: Dictionary in roofs:
		x -= float(rf2.get("weight", 1.0))
		if x < 0.0:
			pick = rf2
			break
	var roof: Dictionary = {"type": str(pick["type"])}
	var pr: Array = pick.get("pitch", [24, 34])
	if str(pick["type"]) != "flat":
		roof["pitch"] = rng.randi_range(int(pr[0]), int(pr[1]))
		roof["overhang"] = snappedf(rng.randf_range(0.3, 0.5), 0.05)
		roof["material"] = t.roof_materials[rng.randi() % t.roof_materials.size()]
	else:
		roof["parapet"] = snappedf(rng.randf_range(0.45, 0.85), 0.05)
	if str(pick["type"]) in ["gable", "shed"]:
		roof["axis"] = str(pick.get("axis", "x" if w >= d else "z"))
	if str(pick["type"]) == "shed":
		roof.erase("axis")
	if pick.has("gutters"):
		roof["gutters"] = bool(pick["gutters"])
	style["roof"] = roof
