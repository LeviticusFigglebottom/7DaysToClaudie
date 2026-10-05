class_name PoiLayout
extends RefCounted
## Compiles a PoiDef's declarative layout (docs/POI_AUTHORING.md) into a cell model shared by the
## builder (geometry), the validator (route/loot/sleeper checks) and the route visualizer.
##
## Space: POI-local, metres. x = plan column, z = plan row (row 0 = back, last row = front);
## the building's front faces +Z. Level L floor top sits at floor_height + L * 3.0. Walls run on
## cell edges: a horizontal edge (c, r) spans x c..c+1 at z = r; a vertical edge (c, r) spans
## z r..r+1 at x = c. Plan characters: letters/digits = rooms, '.' = outside, ' ' = nothing.
##
## Dungeon mechanics (ADR-0018): sleepers may carry a "group" (an ambush, woken by its
## "triggers") and "guardian"; traps are typed (cell or edge traps); doors carry a lock kind; every
## stateful piece gets a stable key (sid / tid / pid / pkey) that the save ledger uses (TD-031).

const STOREY: float = 3.0
const WALL_H: float = 2.8
const SIDES: Dictionary = {"N": 0, "E": 1, "S": 2, "W": 3}
const SIDE_NAMES: PackedStringArray = ["N", "E", "S", "W"]
const DIRS: Array[Vector2i] = [Vector2i(0, -1), Vector2i(1, 0), Vector2i(0, 1), Vector2i(-1, 0)]
const OPENING_TYPES: PackedStringArray = ["door", "door2", "window", "window2", "breach", "open", "half"]
const OPENING_STATES: PackedStringArray = ["closed", "open", "locked", "locked_inside", "broken", "barricaded", "boarded", "missing"]
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
## not breakable), bolt (the default for locked_inside: a sliding bolt on the inside face).
const LOCK_KINDS: PackedStringArray = ["padlock", "chain", "deadbolt", "bolt"]
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
## side), b: room char (north/west side), exterior: bool, opening: Dictionary or {}}
var walls: Dictionary = {}
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


static func compile(p_def: PoiDef) -> PoiLayout:
	var l := PoiLayout.new()
	l.def = p_def
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
			var room: Dictionary = (rd[k] as Dictionary).duplicate()
			room["char"] = str(k)
			rooms[str(k)] = room
		levels[li] = {"plan": plan, "w": w, "d": plan.size(), "y": level_y(li), "rooms": rooms}
		level_ids.append(li)
		for row: String in plan:
			for ch: String in row:
				if ch != "." and ch != " " and not rooms.has(ch):
					err("level %d: plan uses room '%s' with no rooms entry" % [li, ch])
					rooms[ch] = {"char": ch, "type": "room"}
	level_ids.sort()
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


## Room char at a cell ('.' outside the plan, ' ' nothing).
func room_at(li: int, c: Vector2i) -> String:
	var lv: Dictionary = levels.get(li, {})
	if lv.is_empty() or c.y < 0 or c.y >= int(lv["d"]) or c.x < 0:
		return "."
	var row: String = (lv["plan"] as PackedStringArray)[c.y]
	if c.x >= row.length():
		return "."
	return row[c.x]


func is_room(ch: String) -> bool:
	return ch != "." and ch != " "


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
		var op: Dictionary = {
			"id": str(d.get("id", "op%d" % idx)), "level": int(d.get("level", 0)), "cell": Vector2i(int(at[0]), int(at[1])),
			"side": SIDES[side_name], "type": t, "state": st, "width": 2 if t.ends_with("2") else 1,
			"key": str(d.get("key", "")), "hp": float(d.get("hp", 0.0)), "lock": lock, "lock_authored": d.has("lock"),
		}
		# Leaf model ("door_metal") and barricade kind ("furniture") were documented but dropped
		# here, so every door was a wooden one and every barricade boards.
		if d.has("model"):
			op["model"] = str(d["model"])
		if d.has("barricade"):
			op["barricade"] = str(d["barricade"])
		var e: Array = side_edge(op["cell"], op["side"])
		op["axis"] = e[0]
		op["edge"] = e[1]
		openings.append(op)
		idx += 1


func _compile_walls() -> void:
	var open_by_edge: Dictionary = {}
	for op: Dictionary in openings:
		var e: Vector2i = op["edge"]
		for k: int in op["width"]:
			var ek: Vector2i = e + (Vector2i(k, 0) if op["axis"] == "h" else Vector2i(0, k))
			open_by_edge[edge_key(op["level"], op["axis"], ek)] = op
	for li: int in level_ids:
		var lv: Dictionary = levels[li]
		var w: int = lv["w"]
		var d: int = lv["d"]
		for r: int in range(0, d + 1):
			for c: int in range(0, w):
				_maybe_wall(li, "h", Vector2i(c, r), room_at(li, Vector2i(c, r)), room_at(li, Vector2i(c, r - 1)), open_by_edge)
		for r2: int in range(0, d):
			for c2: int in range(0, w + 1):
				_maybe_wall(li, "v", Vector2i(c2, r2), room_at(li, Vector2i(c2, r2)), room_at(li, Vector2i(c2 - 1, r2)), open_by_edge)
	for k: String in open_by_edge:
		if not walls.has(k):
			var op: Dictionary = open_by_edge[k]
			err("opening '%s' at level %d %s is not on a wall" % [op["id"], op["level"], k])


func _maybe_wall(li: int, axis: String, c: Vector2i, a: String, b: String, open_by_edge: Dictionary) -> void:
	if a == b or (not is_room(a) and not is_room(b)):
		return
	if is_room(a) and is_room(b):
		var ra: Dictionary = room_def(li, a)
		var rb: Dictionary = room_def(li, b)
		if str(ra.get("open_to", "")).contains(b) or str(rb.get("open_to", "")).contains(a):
			return
	var key: String = edge_key(li, axis, c)
	walls[key] = {"level": li, "axis": axis, "cell": c, "a": a, "b": b, "exterior": not (is_room(a) and is_room(b)),
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
	out["cell"] = Vector2i(int(floor(p.x)), int(floor(p.y)))
	return out


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


## Every room cell on a level.
func room_cells(li: int) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	var lv: Dictionary = levels.get(li, {})
	for r: int in int(lv.get("d", 0)):
		for c: int in int(lv.get("w", 0)):
			if is_room(room_at(li, Vector2i(c, r))):
				out.append(Vector2i(c, r))
	return out


## Building extent in metres (plan bounds, all levels) — for footprint checks.
func extent() -> Rect2:
	var r := Rect2(origin, Vector2.ZERO)
	for li: int in level_ids:
		r = r.merge(Rect2(origin, Vector2(levels[li]["w"], levels[li]["d"])))
	return r
