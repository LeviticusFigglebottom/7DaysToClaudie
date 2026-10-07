class_name PoiLayout
extends RefCounted
## Compiles a PoiDef's declarative layout (docs/POI_AUTHORING.md) into a cell model shared by the
## builder (geometry), the validator (route/loot/sleeper checks) and the route visualizer.
##
## Space: POI-local, metres. x = plan column, z = plan row (row 0 = back, last row = front);
## the building's front faces +Z. Level L floor top sits at floor_height + L * 3.0. Walls run on
## cell edges: a horizontal edge (c, r) spans x c..c+1 at z = r; a vertical edge (c, r) spans
## z r..r+1 at x = c. Plan characters: letters/digits = rooms, '.' = outside, ' ' = nothing,
## '^' = the room below rises through this storey (a tall room, ADR-0021).
##
## Dungeon mechanics (ADR-0018): sleepers may carry a "group" (an ambush, woken by its
## "triggers") and "guardian"; traps are typed (cell or edge traps); doors carry a lock kind; every
## stateful piece gets a stable key (sid / tid / pid / pkey) that the save ledger uses (TD-031).
##
## Tall rooms (ADR-0021): a room def with "storeys": 2 or 3 may continue up through the levels
## above wherever their plans hold '^' over it (the void). A void cell has no floor and no ceiling
## under it; it belongs to the room it rises from (volume_of), so walls between it and the outside
## rise through the storey, and an upper-level room beside it gets a gallery edge (a railing) instead
## of a wall unless that room says "gallery": false. Tall openings (lancet, window_tall, door2_tall)
## span two storeys of one wall.

## New ADR-0030 scripts by path, so this compiles before the editor registers their class names.
const Dressing := preload("res://src/poi/poi_dressing.gd")

const STOREY: float = 3.0
const WALL_H: float = 2.8
const SIDES: Dictionary = {"N": 0, "E": 1, "S": 2, "W": 3}
const SIDE_NAMES: PackedStringArray = ["N", "E", "S", "W"]
const DIRS: Array[Vector2i] = [Vector2i(0, -1), Vector2i(1, 0), Vector2i(0, 1), Vector2i(-1, 0)]
## The plan character of a storey a tall room rises through.
const VOID: String = "^"
const MAX_STOREYS: int = 3
const OPENING_TYPES: PackedStringArray = ["door", "door2", "window", "window2", "breach", "open", "half", "lancet",
	"window_tall", "door2_tall"]
## Opening type -> cells along the wall ("w") and storeys of wall it spans ("storeys", default 1).
## Two-storey openings stand on the level they are authored on and need a wall on the same edge one
## level up (the tall room's void, or the outside over a lower room).
const OPENING_SPECS: Dictionary = {
	"door": {"w": 1}, "door2": {"w": 2}, "window": {"w": 1}, "window2": {"w": 2}, "breach": {"w": 1}, "open": {"w": 1},
	"half": {"w": 1}, "lancet": {"w": 1, "storeys": 2}, "window_tall": {"w": 1, "storeys": 2}, "door2_tall": {"w": 2, "storeys": 2},
}
const OPENING_STATES: PackedStringArray = ["closed", "open", "locked", "locked_inside", "broken", "barricaded", "boarded", "missing"]
## Keys a room def may carry ("_"-prefixed keys are comments).
const ROOM_KEYS: PackedStringArray = ["name", "type", "wall", "floor", "ceiling", "open_to", "storeys", "open_roof", "gallery"]
## Gallery edge kit styles: turned balusters and a moulded rail, or a rough two-rail timber railing.
const GALLERY_STYLES: PackedStringArray = ["balustrade", "rail"]
## Trap type -> placement: "cell" traps sit in a cell ("at", optional "size" for creaky floors),
## "edge" traps span a cell side ("at" + "side") like a doorway.
const TRAP_TYPES: Dictionary = {"can_chime": "edge", "bear_trap": "cell", "shotgun": "edge", "creaky_floor": "cell",
	"weak_floor": "cell", "alarm": "edge"}
const TRAP_KEYS: PackedStringArray = ["id", "type", "at", "pos", "offset", "side", "level", "size", "rot", "style"]
## What fires a trigger: entering a room, opening/breaking an opening, taking a pickup, the first
## search of a container prop, or a trap going off.
const TRIGGER_ON: PackedStringArray = ["room", "opening", "pickup", "container", "trap"]
const TRIGGER_KEYS: PackedStringArray = ["id", "group", "on", "room", "level", "opening", "pickup", "prop", "trap", "delay"]
## Door lock cues: padlock / chain (breakable, on the side the key opens from), deadbolt (keyed,
## not breakable), bolt (the default for locked_inside: a sliding bolt on the inside face), vault
## (ADR-0026: keyed by a combination; cutting through it instead is slow and rouses the building).
const LOCK_KINDS: PackedStringArray = ["padlock", "chain", "deadbolt", "bolt", "vault"]
## Guardians without a group of their own wake when the loot room is entered (implicit trigger).
const GUARDIAN_GROUP: String = "_guardian"
const GUARDIAN_TRIGGER: String = "_guardian"

var def: PoiDef
var poi_id: StringName
var errors: PackedStringArray = []
## level index -> {plan: PackedStringArray, w, d, y, rooms: {char: Dictionary}}
var levels: Dictionary = {}
var level_ids: Array[int] = []
var floor_height: float = 0.6
## Building grid offset inside the lot footprint (metres).
var origin := Vector2.ZERO
var style: Dictionary = {}
## Edge key "L:h:c:r" / "L:v:c:r" -> {level, axis ("h"/"v"), cell: Vector2i, a: room char (south/east
## side), b: room char (north/west side), ra / rb: the rooms those cells belong to ([level, char],
## [] outside; a void cell resolves to its tall room), exterior: bool, opening: Dictionary or {},
## covered: the two-storey opening below that fills this edge (absent otherwise)}
var walls: Dictionary = {}
## Edge key -> {level, axis, cell, a, b, room: [level, char] of the upper room on it, void_a: the void
## is on the "a" side, style ("balustrade" / "rail"), opening: an "open"/"breach" gap in it, or {}}.
## Edges between a tall room's void and a room on the same storey: a railing, not a wall.
var galleries: Dictionary = {}
## Node key "L:c:r" of every void cell -> [base level, room char] of the tall room it belongs to.
var void_base: Dictionary = {}
var openings: Array[Dictionary] = []
var stairs: Array[Dictionary] = []
var ladders: Array[Dictionary] = []
var holes: Array[Dictionary] = []
var props: Array[Dictionary] = []
var sleepers: Array[Dictionary] = []
var pickups: Array[Dictionary] = []
var traps: Array[Dictionary] = []
## {id, group, on, room, level, opening, pickup, prop, trap, delay, implicit}
var triggers: Array[Dictionary] = []
var route: Array[Dictionary] = []
var loot_room: Dictionary = {}
var shortcuts: Array = []
var lights: Array = []
var decals: Array = []


## A def with alternatives (ADR-0030) compiles as its authored defaults unless it was resolved
## first (PoiDressing.resolve: a placed building's per-run picks).
static func compile(p_def: PoiDef) -> PoiLayout:
	var l := PoiLayout.new()
	l.def = Dressing.resolve(p_def) if p_def.layout.has("alternatives") else p_def
	l.poi_id = p_def.id
	l._compile()
	return l


func err(msg: String) -> void:
	errors.append("%s: %s" % [poi_id, msg])


func _compile() -> void:
	var lay: Dictionary = def.layout
	style = lay.get("style", {})
	floor_height = float(style.get("floor_height", 0.6))
	var o: Array = lay.get("origin", [0, 0])
	origin = Vector2(float(o[0]), float(o[1]))
	for lv: Variant in lay.get("levels", []):
		if not lv is Dictionary:
			err("levels entries must be objects")
			continue
		var li: int = int(lv.get("level", level_ids.size()))
		var plan := PackedStringArray()
		for row: Variant in lv.get("plan", []):
			plan.append(str(row))
		var w: int = 0
		for row: String in plan:
			w = maxi(w, row.length())
		var rooms: Dictionary = {}
		var rd: Dictionary = lv.get("rooms", {})
		for k: Variant in rd.keys():
			if str(k) == VOID:
				err("level %d: '%s' is reserved for the storeys a tall room rises through; it cannot name a room" % [li, VOID])
				continue
			var room: Dictionary = (rd[k] as Dictionary).duplicate()
			room["char"] = str(k)
			rooms[str(k)] = room
			_check_room(li, room)
		# A buried underground level (ADR-0044) runs on under the ground beyond the building: only
		# its cells under a ground-floor room cut the surface (TerrainHoles).
		levels[li] = {"plan": plan, "w": w, "d": plan.size(), "y": level_y(li), "rooms": rooms,
			"buried": li < 0 and bool(lv.get("buried", false))}
		level_ids.append(li)
		for row: String in plan:
			for ch: String in row:
				if ch != "." and ch != " " and ch != VOID and not rooms.has(ch):
					err("level %d: plan uses room '%s' with no rooms entry" % [li, ch])
					rooms[ch] = {"char": ch, "type": "room"}
	level_ids.sort()
	_compile_voids()
	_compile_openings(lay.get("openings", []))
	_compile_walls()
	_compile_vertical(lay)
	# Stable keys (TD-031): authored ids, falling back to the old list-index keys so content
	# without ids keeps the state it was saved with.
	var props_raw: Array = lay.get("props", [])
	for i: int in props_raw.size():
		if props_raw[i] is Dictionary:
			var pr: Dictionary = _placed(props_raw[i])
			pr["index"] = i
			pr["pkey"] = str(pr["id"]) if pr.has("id") else str(i)
			props.append(pr)
	var sl_raw: Array = lay.get("sleepers", [])
	for i: int in sl_raw.size():
		if sl_raw[i] is Dictionary:
			var sl: Dictionary = _placed(sl_raw[i])
			sl["sid"] = str(sl.get("id", "s%d" % i))
			sl["guardian"] = bool(sl.get("guardian", false))
			sl["group"] = str(sl.get("group", ""))
			if sl["guardian"] and str(sl["group"]) == "":
				sl["group"] = GUARDIAN_GROUP
			sleepers.append(sl)
	var pk_raw: Array = lay.get("pickups", [])
	for i: int in pk_raw.size():
		if pk_raw[i] is Dictionary:
			var pk0: Dictionary = _placed(pk_raw[i])
			pk0["pid"] = str(pk0.get("id", "pk%d" % i))
			pk0["legacy_key"] = "pk%d" % i
			pickups.append(pk0)
	var notes_raw: Array = lay.get("notes", [])
	for j: int in notes_raw.size():
		if notes_raw[j] is Dictionary:
			var n: Dictionary = notes_raw[j]
			var pk: Dictionary = _placed(n)
			pk["item"] = "note_" + str(n.get("note", ""))
			# Notes are keyed by their note id (a note appears once per building); before ids they
			# were "pk<index>" counted after the pickups.
			pk["pid"] = str(n.get("id", "note_" + str(n.get("note", ""))))
			pk["legacy_key"] = "pk%d" % (pk_raw.size() + j)
			pk["is_note"] = true
			pickups.append(pk)
	var tr_raw: Array = lay.get("traps", [])
	for i: int in tr_raw.size():
		if tr_raw[i] is Dictionary:
			traps.append(_compile_trap(tr_raw[i], i))
	for tg: Variant in lay.get("triggers", []):
		if not tg is Dictionary:
			err("triggers entries must be objects")
			continue
		var t: Dictionary = tg
		triggers.append({"id": str(t.get("id", "")), "group": str(t.get("group", "")), "on": str(t.get("on", "room")),
			"room": str(t.get("room", "")), "level": int(t.get("level", 0)), "opening": str(t.get("opening", "")),
			"pickup": str(t.get("pickup", "")), "prop": str(t.get("prop", "")), "trap": str(t.get("trap", "")),
			"delay": float(t.get("delay", 0.0)), "implicit": false, "raw": t})
	for wp: Variant in lay.get("route", []):
		if wp is Dictionary:
			route.append(_placed(wp))
	loot_room = lay.get("loot_room", {})
	shortcuts = lay.get("shortcuts", [])
	lights = lay.get("lights", [])
	decals = lay.get("decals", [])
	# A guardian without a group of its own stirs when someone walks into its loot room.
	for s: Dictionary in sleepers:
		if str(s["group"]) == GUARDIAN_GROUP:
			triggers.append({"id": GUARDIAN_TRIGGER, "group": GUARDIAN_GROUP, "on": "room", "room": str(loot_room.get("room", "")),
				"level": int(loot_room.get("level", 0)), "opening": "", "pickup": "", "prop": "", "trap": "", "delay": 0.0,
				"implicit": true, "raw": {}})
			break


## Room def keys and the tall-room values (storeys, open_roof, gallery).
func _check_room(li: int, room: Dictionary) -> void:
	var ch: String = str(room["char"])
	for k: Variant in room.keys():
		var ks: String = str(k)
		if ks != "char" and not ks.begins_with("_") and not ROOM_KEYS.has(ks):
			err("level %d room '%s' has unknown key '%s' (%s)" % [li, ch, ks, ", ".join(ROOM_KEYS)])
	if room.has("storeys"):
		var n: int = int(room["storeys"])
		if n < 1 or n > MAX_STOREYS or float(room["storeys"]) != float(n):
			err("level %d room '%s': storeys must be 1..%d" % [li, ch, MAX_STOREYS])
	if room.has("open_roof") and not room["open_roof"] is bool:
		err("level %d room '%s': open_roof must be true or false" % [li, ch])
	if room.has("gallery"):
		var g: Variant = room["gallery"]
		if not (g is bool or (g is String and GALLERY_STYLES.has(g))):
			err("level %d room '%s': gallery must be true, false or one of %s" % [li, ch, ", ".join(GALLERY_STYLES)])


## Resolves every '^' cell to the tall room it rises from (the room below, or the void below's room)
## and checks that room is tall enough to reach this storey.
func _compile_voids() -> void:
	for li: int in level_ids:
		var lv: Dictionary = levels[li]
		for r: int in int(lv["d"]):
			var row: String = (lv["plan"] as PackedStringArray)[r]
			for c: int in row.length():
				if row[c] != VOID:
					continue
				var cell := Vector2i(c, r)
				var below: String = room_at(li - 1, cell)
				var base: Array = []
				if below == VOID:
					base = void_base.get(node_key(li - 1, cell), [])
				elif is_room(below):
					base = [li - 1, below]
				if base.is_empty():
					err("level %d cell %s is '%s' but no room rises from below it (level %d holds '%s')" % [li, cell, VOID, li - 1, below])
					continue
				var n: int = room_storeys(int(base[0]), str(base[1]))
				if li - int(base[0]) + 1 > n:
					err("level %d cell %s: room '%s' (level %d) rises through it but has storeys %d; give it \"storeys\": %d" % [
						li, cell, base[1], base[0], n, li - int(base[0]) + 1])
				void_base[node_key(li, cell)] = base


## Normalises one trap: placement, its stable id ("trap<i>" before ids were required), its
## kind ("cell"/"edge"), the side index and edge of edge traps, and the cells a cell trap covers.
func _compile_trap(raw: Dictionary, i: int) -> Dictionary:
	var t: Dictionary = _placed(raw)
	t["tid"] = str(raw.get("id", "trap%d" % i))
	t["rot_set"] = raw.has("rot")
	t["type"] = str(raw.get("type", "can_chime"))
	t["kind"] = str(TRAP_TYPES.get(t["type"], ""))
	var side_i: int = int(SIDES.get(str(raw.get("side", "S")), 2))
	t["side_i"] = side_i
	if t["kind"] == "edge":
		var e: Array = side_edge(t["cell"], side_i)
		t["axis"] = e[0]
		t["edge"] = e[1]
	var cells: Array[Vector2i] = []
	var size: Array = raw.get("size", [1, 1]) if t["type"] == "creaky_floor" else [1, 1]
	var c0: Vector2i = t["cell"]
	for dz: int in maxi(1, int(size[1]) if size.size() > 1 else 1):
		for dx: int in maxi(1, int(size[0]) if size.size() > 0 else 1):
			cells.append(c0 + Vector2i(dx, dz))
	t["cells"] = cells
	return t


## The compiled trigger with this id ({} if none).
func trigger(tid: String) -> Dictionary:
	for t: Dictionary in triggers:
		if str(t["id"]) == tid:
			return t
	return {}


## The compiled trap with this id ({} if none).
func trap(tid: String) -> Dictionary:
	for t: Dictionary in traps:
		if str(t["tid"]) == tid:
			return t
	return {}


## The compiled opening with this id ({} if none).
func opening(op_id: String) -> Dictionary:
	for op: Dictionary in openings:
		if str(op["id"]) == op_id:
			return op
	return {}


## Weak-floor cells: node key "L:c:r" -> trap id.
func weak_floor_cells() -> Dictionary:
	var out: Dictionary = {}
	for t: Dictionary in traps:
		if str(t["type"]) == "weak_floor":
			out["%d:%d:%d" % [int(t["level"]), (t["cell"] as Vector2i).x, (t["cell"] as Vector2i).y]] = str(t["tid"])
	return out


func level_y(li: int) -> float:
	return floor_height + float(li) * STOREY


static func node_key(li: int, c: Vector2i) -> String:
	return "%d:%d:%d" % [li, c.x, c.y]


## Room char at a cell ('.' outside the plan, ' ' nothing, '^' a tall room's void).
func room_at(li: int, c: Vector2i) -> String:
	var lv: Dictionary = levels.get(li, {})
	if lv.is_empty() or c.y < 0 or c.y >= int(lv["d"]) or c.x < 0:
		return "."
	var row: String = (lv["plan"] as PackedStringArray)[c.y]
	if c.x >= row.length():
		return "."
	return row[c.x]


## A room cell with a floor of its own (not outside, not a tall room's void).
func is_room(ch: String) -> bool:
	return ch != "." and ch != " " and ch != VOID


func is_void(li: int, c: Vector2i) -> bool:
	return room_at(li, c) == VOID


## Something is built in this cell on this level: a room, or a tall room rising through it.
func is_built(li: int, c: Vector2i) -> bool:
	var ch: String = room_at(li, c)
	return is_room(ch) or ch == VOID


## The room a cell belongs to: [level, char] of the room itself, of the tall room a void cell rises
## from, or [] outside.
func volume_of(li: int, c: Vector2i) -> Array:
	var ch: String = room_at(li, c)
	if is_room(ch):
		return [li, ch]
	if ch == VOID:
		return void_base.get(node_key(li, c), [])
	return []


## [level, cell] of the floor under a point of a cell: a void cell's tall room floor, else itself.
## (PoiInstance.locate: indoor queries, shelter, reverb and room triggers treat the whole volume
## as one room.)
func floor_cell(li: int, c: Vector2i) -> Array:
	var v: Array = volume_of(li, c) if is_void(li, c) else []
	return [int(v[0]), c] if not v.is_empty() else [li, c]


## Storeys of a room (1 unless its def says "storeys").
func room_storeys(li: int, ch: String) -> int:
	return clampi(int(room_def(li, ch).get("storeys", 1)), 1, MAX_STOREYS)


## The highest level the room column at (li, c) reaches: li unless voids of the same room rise
## above it.
func column_top(li: int, c: Vector2i) -> int:
	var base: Array = volume_of(li, c)
	if base.is_empty():
		return li
	var top: int = li
	while is_void(top + 1, c) and volume_of(top + 1, c) == base:
		top += 1
	return top


## Height of a cell's ceiling (underside) above the floor of level `li`: 2.8 m, plus 3 m for every
## storey a tall room rises above it.
func ceiling_height(li: int, c: Vector2i) -> float:
	return float(column_top(li, c) - li) * STOREY + WALL_H


## Whether the room at (li, c) has no ceiling at its top: it sees the roof (rafters and boards).
func open_roof_at(li: int, c: Vector2i) -> bool:
	var v: Array = volume_of(li, c)
	return not v.is_empty() and bool(room_def(int(v[0]), str(v[1])).get("open_roof", false))


func room_def(li: int, ch: String) -> Dictionary:
	return ((levels.get(li, {}) as Dictionary).get("rooms", {}) as Dictionary).get(ch, {})


static func edge_key(li: int, axis: String, c: Vector2i) -> String:
	return "%d:%s:%d:%d" % [li, axis, c.x, c.y]


## Edge of a cell side: N -> h(c, r), S -> h(c, r+1), W -> v(c, r), E -> v(c+1, r).
static func side_edge(cell: Vector2i, side: int) -> Array:
	match side:
		0:
			return ["h", cell]
		2:
			return ["h", Vector2i(cell.x, cell.y + 1)]
		3:
			return ["v", cell]
		_:
			return ["v", Vector2i(cell.x + 1, cell.y)]


## The two cells an edge separates: [a (south / east of it), b (north / west)].
static func edge_cells(axis: String, c: Vector2i) -> Array[Vector2i]:
	if axis == "h":
		return [c, Vector2i(c.x, c.y - 1)]
	return [c, Vector2i(c.x - 1, c.y)]


## Every edge a compiled opening spans (2 m ones span two): [[a cell, b cell], ...] (edge_cells order).
static func opening_edges(op: Dictionary) -> Array:
	var out: Array = []
	var e: Vector2i = op["edge"]
	for k: int in int(op.get("width", 1)):
		var ek: Vector2i = e + (Vector2i(k, 0) if str(op["axis"]) == "h" else Vector2i(0, k))
		out.append(edge_cells(str(op["axis"]), ek))
	return out


## Cells of the stair flights on a level (their steps rise through them): cell -> the flight's step
## index there (0 = the foot).
func flight_cells(li: int) -> Dictionary:
	var out: Dictionary = {}
	for s: Dictionary in stairs:
		if int(s["level"]) == li:
			var cells: Array = s["cells"]
			for k: int in cells.size():
				out[cells[k]] = k
	return out


## Whether the edge between two cells on a level is where a flight from the level below arrives:
## between its head (the last step's well) and its landing. A gallery railing is left out there
## (the cannery's gallery stood across the top of its stair, player report 3).
func is_stair_head_edge(li: int, a: Vector2i, b: Vector2i) -> bool:
	for s: Dictionary in stairs:
		if int(s["level"]) + 1 != li:
			continue
		var head: Vector2i = (s["cells"] as Array).back()
		var land: Vector2i = s["landing"]
		if (a == head and b == land) or (a == land and b == head):
			return true
	return false


## Which face of its wall a door leaf swings to: +1 toward the edge's "a" cell (south / east, the
## builder's default), -1 toward "b". An authored "swing" (the compass side it opens to) wins.
## Otherwise the leaf opens to the side with room for it (traversal bot poi_walk): open, it stands
## out square from its hinge jamb up to a metre deep, so
##  * never into a stair flight or the well over one (it stood in the steps: the owner's "stairs
##    that push against a door", player report 3), nor onto the cell a flight is climbed from;
##  * never across a hall one cell deep (merrow's kids' door, the bungalows' bedroom doors on
##    Larch Street): a leaf a metre deep there walls the hall off; it opens into the room instead,
##    where a metre is left beside it;
##  * into the building rather than out over the yard (where the walk round the walls and the
##    stoop are), unless the inside is a hall;
##  * away from the face a barricade stands on (the leaf would open through the pile or boards).
## Ties keep the default ("a").
func door_swing(op: Dictionary) -> float:
	if op.has("swing"):
		return float(op["swing"])
	var sa: float = _swing_room(op, 1.0)
	var sb: float = _swing_room(op, -1.0)
	if str(op.get("state", "")) == "barricaded":
		var bar: float = barricade_face_hint(op)
		if bar > 0.0:
			sa -= 5.0
		elif bar < 0.0:
			sb -= 5.0
	return -1.0 if sb > sa else 1.0


## How good a side of a door's wall is for its leaf to open into (higher is better; see
## door_swing): the worst of the cells the opening's edges have on that side. -10 a stair flight
## or a well (no floor), 0.5 the cell a flight is climbed from, 1 a hall one cell deep (the cell
## beyond, away from the wall, is walled off), 1.5 outside, 2 a room with a metre to spare.
func _swing_room(op: Dictionary, side: float) -> float:
	var li: int = int(op["level"])
	var flights: Dictionary = flight_cells(li)
	flights.merge(stairwell_cells(li))
	var feet: Dictionary = stair_approach_cells(li)
	var h: bool = str(op["axis"]) == "h"
	var away: Vector2i = (Vector2i(0, 1) if h else Vector2i(1, 0)) * (1 if side > 0.0 else -1)
	var worst: float = 2.0
	for pair: Array in opening_edges(op):
		var c: Vector2i = pair[0] if side > 0.0 else pair[1]
		var score: float = 2.0
		if flights.has(c) or is_void(li, c):
			score = -10.0
		elif not is_room(room_at(li, c)):
			score = 1.5
		elif feet.has(c):
			score = 0.5
		else:
			var n: Vector2i = c + away
			var e: Array = side_edge(c, DIRS.find(away))
			var ek: String = edge_key(li, e[0], e[1])
			if not is_room(room_at(li, n)) or flights.has(n) or walls.has(ek) or galleries.has(ek):
				score = 1.0
		worst = minf(worst, score)
	return worst


## Which face of its wall a barricaded door's barricade stands on, as far as the layout alone
## says (+1 the "a" side, -1 "b", 0 unknown): an authored "barricade_on" (a room char, "." for
## outside); a furniture pile inside on an exterior wall and on the "a" side of an interior one;
## boards outside on an exterior wall. Boards on an interior wall go on the side the door is
## approached from (PoiValidator._approach_side): 0 here. PoiBuilder._barricade_faces agrees.
func barricade_face_hint(op: Dictionary) -> float:
	var w: Dictionary = walls.get(edge_key(int(op["level"]), str(op["axis"]), op["edge"]), {})
	if w.is_empty():
		return 0.0
	var on: String = str(op.get("barricade_on", ""))
	if on != "" and on == str(w["a"]):
		return 1.0
	if on != "" and on == str(w["b"]):
		return -1.0
	var furniture: bool = str(op.get("barricade", "boards")) != "boards"
	if bool(w["exterior"]):
		var outside_sign: float = 1.0 if not is_room(str(w["a"])) else -1.0
		return -outside_sign if furniture else outside_sign
	return 1.0 if furniture else 0.0


## Cells a stair flight on a level is climbed from: the one behind each flight's foot.
func stair_approach_cells(li: int) -> Dictionary:
	var out: Dictionary = {}
	for s: Dictionary in stairs:
		if int(s["level"]) == li:
			var foot: Vector2i = (s["cells"] as Array)[0]
			out[foot - DIRS[int(s["dir"])]] = true
	return out


## Full width of the furniture pile (barricade_furniture: a dresser, chairs and planks, 1.6 x 1.4 x
## 0.8 m) where it may spill past its doorway, and how much it overhangs a 1 m door's clear width
## where it may not.
const PILE_W: float = 1.6
## Hit points of a door barricade (boards or a furniture pile): it can be broken while above 0.
const BARRICADE_HP: float = 260.0
const PILE_NARROW_MARGIN: float = 0.1


## Where a barricaded door's furniture pile stands: {"cells": the cells it fills on its face's side
## of the wall (one per metre of the opening; it stands 0.13 to 0.93 m off the wall, so it fills
## them until broken), "wide": whether it may stand its full PILE_W wide, spilling 0.3 m into the
## cells either side of a 1 m doorway}. Wide only where both those cells are open floor of the
## same room or yard (no wall, flight, stairwell, ladder, stair approach or doorway there): the
## lookout's pile stood over the foot of its stairs (poi_walk). Otherwise PoiBuilder narrows it to
## the doorway's own column.
func barricade_pile(op: Dictionary, face: float) -> Dictionary:
	var li: int = int(op["level"])
	var cells: Array[Vector2i] = []
	for pair: Array in opening_edges(op):
		cells.append(pair[0] if face > 0.0 else pair[1])
	var wide: bool = true
	if int(op["width"]) == 1:
		var h: bool = str(op["axis"]) == "h"
		# The side of the pile's cell its wall is on.
		var wall_side: int = (0 if face > 0.0 else 2) if h else (3 if face > 0.0 else 1)
		for ld: int in ([3, 1] if h else [0, 2]):
			if not _pile_spill_ok(li, cells[0], ld, wall_side):
				wide = false
	return {"cells": cells, "wide": wide}


func _pile_spill_ok(li: int, pc: Vector2i, ld: int, wall_side: int) -> bool:
	var n: Vector2i = pc + DIRS[ld]
	var ch: String = room_at(li, n)
	if is_room(ch) != is_room(room_at(li, pc)) or ch == VOID or ch == " " or (not is_room(ch) and li != 0):
		return false
	var e: Array = side_edge(pc, ld)
	var ek: String = edge_key(li, e[0], e[1])
	if walls.has(ek) or galleries.has(ek):
		return false
	if flight_cells(li).has(n) or stairwell_cells(li).has(n) or stair_approach_cells(li).has(n):
		return false
	for l: Dictionary in ladders:
		if int(l["level"]) == li and l["cell"] == n:
			return false
	# A doorway beside it on the same wall.
	var we: Array = side_edge(n, wall_side)
	var w: Dictionary = walls.get(edge_key(li, we[0], we[1]), {})
	if not w.is_empty():
		var wop: Dictionary = w["opening"]
		if not wop.is_empty() and not is_window(str(wop["type"])):
			return false
	return true


## Glazed opening types (glass, boards, a sill to vault): windows and lancets.
static func is_window(t: String) -> bool:
	return t.begins_with("window") or t == "lancet"


## Storeys of wall an opening type spans (1, or 2 for lancets, tall windows and tall doors).
static func opening_storeys(t: String) -> int:
	return int((OPENING_SPECS.get(t, {}) as Dictionary).get("storeys", 1))


func _compile_openings(list: Array) -> void:
	var idx: int = 0
	for o: Variant in list:
		if not o is Dictionary:
			continue
		var d: Dictionary = o
		var at: Array = d.get("at", [0, 0])
		var side_name: String = str(d.get("side", "S"))
		if not SIDES.has(side_name):
			err("opening side '%s' must be N/E/S/W" % side_name)
			continue
		var t: String = str(d.get("type", "door"))
		if not OPENING_TYPES.has(t):
			err("opening type '%s' unknown" % t)
			continue
		var st: String = str(d.get("state", "closed" if t.begins_with("door") else ("open" if t in ["open", "breach"] else "closed")))
		if not OPENING_STATES.has(st):
			err("opening state '%s' unknown" % st)
		# Lock cue: padlocks by default on locked doors, a sliding bolt on locked_inside ones.
		var lock: String = str(d.get("lock", ""))
		if lock == "" and t.begins_with("door"):
			lock = "padlock" if st == "locked" else ("bolt" if st == "locked_inside" else "")
		if lock != "" and not LOCK_KINDS.has(lock):
			err("opening '%s' lock '%s' must be one of %s" % [d.get("id", "op%d" % idx), lock, ", ".join(LOCK_KINDS)])
			lock = ""
		if lock == "vault" and (st != "locked" or str(d.get("key", "")) == "" or t != "door"):
			err("opening '%s': a vault lock goes on a locked door with a key (its combination)" % d.get("id", "op%d" % idx))
		var op: Dictionary = {
			"id": str(d.get("id", "op%d" % idx)), "level": int(d.get("level", 0)), "cell": Vector2i(int(at[0]), int(at[1])),
			"side": SIDES[side_name], "type": t, "state": st, "width": int((OPENING_SPECS[t] as Dictionary)["w"]),
			"storeys": opening_storeys(t), "key": str(d.get("key", "")), "hp": float(d.get("hp", 0.0)), "lock": lock,
			"lock_authored": d.has("lock"),
		}
		# Leaf model ("door_metal") and barricade kind ("furniture") were documented but dropped
		# here, so every door was a wooden one and every barricade boards.
		if d.has("model"):
			op["model"] = str(d["model"])
		if d.has("barricade"):
			op["barricade"] = str(d["barricade"])
		if d.has("barricade_on"):
			op["barricade_on"] = str(d["barricade_on"])
		var e: Array = side_edge(op["cell"], op["side"])
		op["axis"] = e[0]
		op["edge"] = e[1]
		# An authored leaf swing: the compass side of its wall the leaf opens to (door_swing).
		if d.has("swing"):
			var sw: String = str(d["swing"])
			var along: PackedStringArray = ["N", "S"] if e[0] == "h" else ["W", "E"]
			if not along.has(sw):
				err("opening '%s' swing '%s' must be %s or %s (a side of its wall)" % [op["id"], sw, along[0], along[1]])
			elif not t.begins_with("door"):
				err("opening '%s': only doors take a swing" % op["id"])
			else:
				op["swing"] = 1.0 if sw == along[1] else -1.0
		openings.append(op)
		idx += 1


func _compile_walls() -> void:
	var open_by_edge: Dictionary = {}
	## Edges one storey above a two-storey opening: its piece fills them.
	var covered: Dictionary = {}
	for op: Dictionary in openings:
		var e: Vector2i = op["edge"]
		for k: int in op["width"]:
			var ek: Vector2i = e + (Vector2i(k, 0) if op["axis"] == "h" else Vector2i(0, k))
			open_by_edge[edge_key(op["level"], op["axis"], ek)] = op
			for s: int in range(1, int(op["storeys"])):
				covered[edge_key(int(op["level"]) + s, op["axis"], ek)] = op
	for li: int in level_ids:
		var lv: Dictionary = levels[li]
		var w: int = lv["w"]
		var d: int = lv["d"]
		for r: int in range(0, d + 1):
			for c: int in range(0, w):
				_maybe_wall(li, "h", Vector2i(c, r), open_by_edge)
		for r2: int in range(0, d):
			for c2: int in range(0, w + 1):
				_maybe_wall(li, "v", Vector2i(c2, r2), open_by_edge)
	for k: String in open_by_edge:
		var op: Dictionary = open_by_edge[k]
		if walls.has(k):
			continue
		if galleries.has(k):
			if str(op["type"]) in ["open", "breach"]:
				galleries[k]["opening"] = op
			else:
				err("opening '%s' at level %d %s is on a gallery edge: only 'open' (a gap in the railing) or 'breach' (a broken one) go there; give the room \"gallery\": false for a wall" % [
					op["id"], op["level"], k])
			continue
		err("opening '%s' at level %d %s is not on a wall" % [op["id"], op["level"], k])
	for k2: String in covered:
		var op2: Dictionary = covered[k2]
		if not walls.has(k2):
			err("tall opening '%s' (%s) needs a wall on the same edge one storey up (%s): put it on a tall room's wall" % [op2["id"], op2["type"], k2])
		elif not (walls[k2]["opening"] as Dictionary).is_empty():
			err("opening '%s' sits on the upper half of tall opening '%s'" % [walls[k2]["opening"]["id"], op2["id"]])
		else:
			walls[k2]["covered"] = op2


func _maybe_wall(li: int, axis: String, c: Vector2i, open_by_edge: Dictionary) -> void:
	var cells: Array[Vector2i] = edge_cells(axis, c)
	var a: String = room_at(li, cells[0])
	var b: String = room_at(li, cells[1])
	var ra: Array = volume_of(li, cells[0])
	var rb: Array = volume_of(li, cells[1])
	if ra.is_empty() and rb.is_empty():
		return
	var key: String = edge_key(li, axis, c)
	if not ra.is_empty() and not rb.is_empty():
		if ra == rb:
			return
		if int(ra[0]) == int(rb[0]):
			var da: Dictionary = room_def(int(ra[0]), str(ra[1]))
			var db: Dictionary = room_def(int(rb[0]), str(rb[1]))
			if str(da.get("open_to", "")).contains(str(rb[1])) or str(db.get("open_to", "")).contains(str(ra[1])):
				return
		# A tall room's void beside a room on this storey: the room looks over it from a gallery,
		# unless it asks for a wall.
		if (a == VOID) != (b == VOID):
			var up: Array = rb if a == VOID else ra
			var g: Variant = room_def(int(up[0]), str(up[1])).get("gallery", true)
			if not (g is bool and not g):
				galleries[key] = {"level": li, "axis": axis, "cell": c, "a": a, "b": b, "room": up, "void_a": a == VOID,
					"style": str(g) if g is String else "balustrade", "opening": {}}
				return
	walls[key] = {"level": li, "axis": axis, "cell": c, "a": a, "b": b, "ra": ra, "rb": rb, "exterior": ra.is_empty() or rb.is_empty(),
		"opening": open_by_edge.get(key, {})}


func _compile_vertical(lay: Dictionary) -> void:
	for s: Variant in lay.get("stairs", []):
		if not s is Dictionary:
			continue
		var at: Array = s.get("at", [0, 0])
		var dir: int = SIDES.get(str(s.get("dir", "N")), 0)
		var li: int = int(s.get("level", 0))
		var cells: Array[Vector2i] = []
		var c0 := Vector2i(int(at[0]), int(at[1]))
		for k: int in 4:
			cells.append(c0 + DIRS[dir] * k)
		var landing: Vector2i = c0 + DIRS[dir] * 4
		stairs.append({"level": li, "cell": c0, "dir": dir, "cells": cells, "landing": landing})
		if not levels.has(li + 1):
			err("stairs at level %d lead to a missing level %d" % [li, li + 1])
	for l: Variant in lay.get("ladders", []):
		if not l is Dictionary:
			continue
		var at2: Array = l.get("at", [0, 0])
		ladders.append({"level": int(l.get("level", 0)), "cell": Vector2i(int(at2[0]), int(at2[1])), "side": SIDES.get(str(l.get("side", "N")), 0),
			"hatch": bool(l.get("hatch", true))})
	for h: Variant in lay.get("holes", []):
		if not h is Dictionary:
			continue
		var at3: Array = h.get("at", [0, 0])
		holes.append({"level": int(h.get("level", 1)), "cell": Vector2i(int(at3[0]), int(at3[1]))})
	for l: Dictionary in ladders:
		l["landing"] = _ladder_landing(l)


## Where a ladder's climber steps off upstairs: the hatch cell itself has no floor, so the
## neighbouring room cell away from the wall the ladder leans on (or either side of it).
func _ladder_landing(l: Dictionary) -> Vector2i:
	var up: int = int(l["level"]) + 1
	var c: Vector2i = l["cell"]
	var away: Vector2i = -DIRS[int(l["side"])]
	var open: Dictionary = stairwell_cells(up)
	for d: Vector2i in [away, Vector2i(away.y, away.x), Vector2i(-away.y, -away.x)]:
		if is_room(room_at(up, c + d)) and not open.has(c + d):
			return c + d
	if levels.has(up):
		err("ladder at %s (level %d) has no floor beside its hatch on level %d" % [c, int(l["level"]), up])
	return c


## Normalises a placed entry. "at": [c, r] = centre of that cell (plus optional "offset":
## [dx, dz] in metres); "pos": [x, z] = exact plan position in metres. Adds pos, level, rot, cell.
func _placed(d: Dictionary) -> Dictionary:
	var out: Dictionary = d.duplicate()
	var p := Vector2.ZERO
	if d.has("pos"):
		var a: Array = d["pos"]
		p = Vector2(float(a[0]), float(a[1]))
	else:
		var at: Array = d.get("at", [0, 0])
		p = Vector2(floor(float(at[0])) + 0.5, floor(float(at[1])) + 0.5)
		var off: Array = d.get("offset", [0, 0])
		p += Vector2(float(off[0]), float(off[1]))
	out["pos"] = p
	out["level"] = int(d.get("level", 0))
	out["rot"] = float(d.get("rot", 0.0))
	# Whether the author gave a rotation. "rot" is always filled in above, so without this flag a
	# prop placed `against` a wall could never take that wall's default facing.
	out["rot_set"] = d.has("rot")
	out["cell"] = Vector2i(int(floor(p.x)), int(floor(p.y)))
	return out


## Where a compiled prop (or a scatter entry) stands in plan: Vector3(x, z, facing in degrees),
## layout-local. A prop `against` a wall stands with its back (PropDef.back_depth) 1 cm off the
## wall's face and faces into the room unless its author turned it. Compiled props carry
## "rot_set" (_placed always fills "rot"); scatter entries set "rot" themselves. PoiBuilder places
## by this and PoiValidator measures wall gaps by it.
static func prop_plan(p: Dictionary, pd: PropDef) -> Vector3:
	var pos: Vector2 = p["pos"]
	var rot: float = float(p.get("rot", 0.0))
	var turned: bool = bool(p.get("rot_set", p.has("rot")))
	var against: String = str(p.get("against", ""))
	if against != "" and SIDES.has(against):
		var cell: Vector2i = p["cell"]
		var facing: float = AGAINST_ROT[int(SIDES[against])]
		rot = rot if turned else facing
		# Origin to wall face: half the wall, 1 cm of air, then how far the footprint reaches toward
		# the wall (its back depth when it faces the room square). Round 1 used half the prop's
		# depth for every prop, which stood wall-mounted ones (origin on the wall plane) half their
		# depth out in the room (round 1 measured 83 more than 10 cm off their walls).
		var off: float = PoiBuilder.WALL_T * 0.5 + wall_reach(pd, rot - facing) + 0.01
		match against:
			"N":
				pos.y = cell.y + off
			"S":
				pos.y = cell.y + 1.0 - off
			"W":
				pos.x = cell.x + off
			"E":
				pos.x = cell.x + 1.0 - off
	return Vector3(pos.x, pos.y, rot)


## The facing of a prop with its back to the wall on each side (N, E, S, W): into the room.
const AGAINST_ROT: Array[float] = [0.0, -90.0, 180.0, 90.0]


## How far (m) a prop's footprint reaches behind its origin toward a wall when it is turned
## `turn` degrees from facing square away from it: its back depth square on, half its width side
## on (a scatter box turned 25° off its wall puts a back corner nearer the wall than its back).
static func wall_reach(pd: PropDef, turn: float) -> float:
	var back: float = pd.back_depth()
	var toward: Vector3 = Basis(Vector3.UP, deg_to_rad(-turn)) * Vector3(0, 0, -1)
	var reach: float = -INF
	for sx: float in [-0.5, 0.5]:
		for z: float in [-back, pd.size.z - back]:
			reach = maxf(reach, Vector3(sx * pd.size.x, 0.0, z).dot(toward))
	return reach


## Cells blocked for the stairwell on the level above (no floor slab there).
func stairwell_cells(li: int) -> Dictionary:
	var out: Dictionary = {}
	for s: Dictionary in stairs:
		if int(s["level"]) + 1 == li:
			for c: Vector2i in s["cells"]:
				out[c] = true
	for l: Dictionary in ladders:
		if int(l["level"]) + 1 == li and bool(l["hatch"]):
			out[l["cell"]] = true
	return out


## World-ish local position of a cell centre on a level.
func cell_center(li: int, c: Vector2i) -> Vector3:
	return Vector3(origin.x + c.x + 0.5, level_y(li), origin.y + c.y + 0.5)


func local_pos(li: int, p: Vector2) -> Vector3:
	return Vector3(origin.x + p.x, level_y(li), origin.y + p.y)


## Every room cell on a level (not a tall room's void: it has no floor of its own).
func room_cells(li: int) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	var lv: Dictionary = levels.get(li, {})
	for r: int in int(lv.get("d", 0)):
		for c: int in int(lv.get("w", 0)):
			if is_room(room_at(li, Vector2i(c, r))):
				out.append(Vector2i(c, r))
	return out


## Every void cell on a level.
func void_cells(li: int) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	var lv: Dictionary = levels.get(li, {})
	for r: int in int(lv.get("d", 0)):
		for c: int in int(lv.get("w", 0)):
			if is_void(li, Vector2i(c, r)):
				out.append(Vector2i(c, r))
	return out


## Building extent in metres (plan bounds, all levels) — for footprint checks.
func extent() -> Rect2:
	var r := Rect2(origin, Vector2.ZERO)
	for li: int in level_ids:
		r = r.merge(Rect2(origin, Vector2(levels[li]["w"], levels[li]["d"])))
	return r
