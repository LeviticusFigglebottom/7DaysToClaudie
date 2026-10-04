class_name PoiValidator
extends RefCounted
## Static checks for an authored POI (run by `make validate`, the editor tool and GUT):
##  * the intended route is completable waypoint to waypoint (doors, breaches, stairs, ladders,
##    drop holes, keys picked up along the way; barricades and intact glass do not count),
##  * the loot room is reachable and holds a container; declared shortcuts exist and lead out,
##  * sleepers stand on walkable cells (not stairs, not inside props), props stay inside rooms and
##    off the route corridor, pickups are reachable,
##  * the building fits its footprint, and the performance budget (lights, sleepers, pieces) holds.
## Node graph: (level, cell) room/outside cells; "out" = the yard.

const PASSABLE_DOOR_STATES: PackedStringArray = ["closed", "open", "broken", "missing", "locked", "locked_inside"]
const DEFAULT_BUDGET: Dictionary = {"lights": 10, "enemies": 14, "pieces": 2600, "props": 220}

var layout: PoiLayout
var errors: PackedStringArray = []
var warnings: PackedStringArray = []
## For the route visualizer: one Array[Vector3] (local positions) per route segment.
var paths: Array = []
var stats: Dictionary = {}
var _keys_found: Dictionary = {}


static func validate(def: PoiDef) -> PoiValidator:
	var v := PoiValidator.new()
	v.layout = PoiLayout.compile(def)
	v.errors.append_array(v.layout.errors)
	v._run()
	return v


func ok() -> bool:
	return errors.is_empty()


func _e(msg: String) -> void:
	errors.append("%s: %s" % [layout.poi_id, msg])


func _w(msg: String) -> void:
	warnings.append("%s: %s" % [layout.poi_id, msg])


static func node_key(li: int, c: Vector2i) -> String:
	return "%d:%d:%d" % [li, c.x, c.y]


## Rooms, plus a yard ring (YARD cells) around level 0 so routes can walk round the outside.
const YARD: int = 3


func _walkable(li: int, c: Vector2i) -> bool:
	if layout.is_room(layout.room_at(li, c)):
		return true
	if li != 0 or layout.room_at(li, c) != ".":
		return false
	var lv: Dictionary = layout.levels.get(0, {})
	return c.x >= -YARD and c.y >= -YARD and c.x < int(lv.get("w", 0)) + YARD and c.y < int(lv.get("d", 0)) + YARD


## Neighbours of a node given the keys held.
func _neighbors(li: int, c: Vector2i, keys: Dictionary) -> Array:
	var out: Array = []
	var here: String = layout.room_at(li, c)
	var outside_here: bool = not layout.is_room(here)
	if outside_here and li == 0:
		out.append("out")
	for side: int in 4:
		var n: Vector2i = c + PoiLayout.DIRS[side]
		var e: Array = PoiLayout.side_edge(c, side)
		var wall: Dictionary = layout.walls.get(PoiLayout.edge_key(li, e[0], e[1]), {})
		if not wall.is_empty():
			var op: Dictionary = wall["opening"]
			if op.is_empty() or not _opening_passable(op, c, keys):
				continue
		if _walkable(li, n):
			out.append([li, n])
	for s: Dictionary in layout.stairs:
		if int(s["level"]) == li and s["cell"] == c:
			out.append([li + 1, s["landing"]])
		elif int(s["level"]) + 1 == li and s["landing"] == c:
			out.append([li - 1, s["cell"]])
	for l: Dictionary in layout.ladders:
		var lc: Vector2i = l["cell"]
		var land: Vector2i = l.get("landing", lc)
		if int(l["level"]) == li and lc == c:
			out.append([li + 1, land])
		elif int(l["level"]) + 1 == li and land == c:
			out.append([li - 1, lc])
	for h: Dictionary in layout.holes:
		if int(h["level"]) == li and h["cell"] == c:
			out.append([li - 1, c])
	return out


func _opening_passable(op: Dictionary, from_cell: Vector2i, keys: Dictionary) -> bool:
	var t: String = op["type"]
	var st: String = op["state"]
	if t in ["open", "breach", "half"]:
		return true
	if t.begins_with("window"):
		return st == "broken" or st == "missing" or st == "open"
	if not PASSABLE_DOOR_STATES.has(st):
		return false
	if st == "locked":
		return str(op["key"]) != "" and keys.has(str(op["key"]))
	if st == "locked_inside":
		# Opens only from the cell it was authored on (the inside).
		return from_cell == op["cell"]
	return true


## BFS from `start` nodes; returns {key: [prev_key, li, cell]} for reconstruction.
func _bfs(starts: Array, keys: Dictionary) -> Dictionary:
	var seen: Dictionary = {}
	var queue: Array = []
	for s: Variant in starts:
		var k: String = "out" if s is String else node_key(s[0], s[1])
		seen[k] = ["", s]
		queue.append(s)
	while not queue.is_empty():
		var cur: Variant = queue.pop_front()
		var nbrs: Array = []
		var cur_key: String
		if cur is String:
			cur_key = "out"
			for li: int in [0]:
				var lv: Dictionary = layout.levels.get(li, {})
				for r: int in range(-1, int(lv.get("d", 0)) + 1):
					for c: int in range(-1, int(lv.get("w", 0)) + 1):
						var cc := Vector2i(c, r)
						if layout.room_at(li, cc) == ".":
							nbrs.append([li, cc])
		else:
			cur_key = node_key(cur[0], cur[1])
			nbrs = _neighbors(cur[0], cur[1], keys)
		for n: Variant in nbrs:
			var nk: String = "out" if n is String else node_key(n[0], n[1])
			if not seen.has(nk):
				seen[nk] = [cur_key, n]
				queue.append(n)
	return seen


func _keys_reachable(seen: Dictionary, keys: Dictionary) -> bool:
	var added: bool = false
	for p: Dictionary in layout.pickups:
		var item: String = str(p.get("item", ""))
		if item == "" or keys.has(item):
			continue
		if seen.has(node_key(p["level"], p["cell"])):
			keys[item] = true
			added = true
	return added


func _run() -> void:
	var def: PoiDef = layout.def
	if layout.level_ids.is_empty():
		_e("no levels")
		return
	# Footprint.
	var ext: Rect2 = layout.extent()
	if ext.position.x < 0 or ext.position.y < 0 or ext.end.x > def.footprint.x + 0.01 or ext.end.y > def.footprint.y + 0.01:
		_e("building %s does not fit footprint %s" % [ext, def.footprint])
	# Reachability with keys picked up as they become reachable.
	var keys: Dictionary = {}
	var seen: Dictionary = _bfs(["out"], keys)
	while _keys_reachable(seen, keys):
		seen = _bfs(["out"], keys)
	_keys_found = keys
	var entrances: int = 0
	for li: int in [0]:
		for c: Vector2i in layout.room_cells(li):
			if seen.has(node_key(li, c)):
				entrances += 1
				break
	if entrances == 0:
		_e("no way in from outside")
	# Loot room.
	if layout.loot_room.is_empty():
		_w("no loot_room declared")
	else:
		var lr_level: int = int(layout.loot_room.get("level", 0))
		var lr_char: String = str(layout.loot_room.get("room", ""))
		var reached: bool = false
		for c: Vector2i in layout.room_cells(lr_level):
			if layout.room_at(lr_level, c) == lr_char and seen.has(node_key(lr_level, c)):
				reached = true
				break
		if not reached:
			_e("loot room '%s' (level %d) is not reachable" % [lr_char, lr_level])
		var has_container: bool = false
		for p: Dictionary in layout.props:
			if int(p["level"]) == lr_level and layout.room_at(lr_level, p["cell"]) == lr_char and _is_container(p):
				has_container = true
		if not has_container:
			_e("loot room '%s' has no container" % lr_char)
	# Route.
	if layout.route.size() < 2:
		_e("route needs at least two waypoints")
	var prev: Variant = "out"
	for i: int in layout.route.size():
		var wp: Dictionary = layout.route[i]
		var li: int = wp["level"]
		var c: Vector2i = wp["cell"]
		if not _walkable(li, c):
			_e("route waypoint %d '%s' is not on a walkable cell %s (level %d)" % [i, wp.get("label", ""), c, li])
			continue
		var s2: Dictionary = _bfs([prev], keys)
		var k: String = node_key(li, c)
		if not s2.has(k):
			_e("route waypoint %d '%s' unreachable from the previous one" % [i, wp.get("label", "")])
		else:
			paths.append(_reconstruct(s2, k))
		prev = [li, c]
	# Shortcuts lead outside.
	for sc: Variant in layout.shortcuts:
		var op_id: String = str((sc as Dictionary).get("opening", "")) if sc is Dictionary else str(sc)
		var found: Dictionary = {}
		for op: Dictionary in layout.openings:
			if op["id"] == op_id:
				found = op
		if found.is_empty():
			_e("shortcut opening '%s' not found" % op_id)
	# Sleepers.
	var stair_cells: Dictionary = {}
	for s: Dictionary in layout.stairs:
		for c: Vector2i in s["cells"]:
			stair_cells[node_key(s["level"], c)] = true
	var blocked: Dictionary = _prop_cells()
	for i: int in layout.sleepers.size():
		var sl: Dictionary = layout.sleepers[i]
		var k2: String = node_key(sl["level"], sl["cell"])
		if not layout.is_room(layout.room_at(sl["level"], sl["cell"])):
			_e("sleeper %d is not inside a room (%s level %d)" % [i, sl["cell"], sl["level"]])
		elif stair_cells.has(k2):
			_e("sleeper %d stands on stairs" % i)
		elif blocked.has(k2) and str(sl.get("pose", "stand")) != "lie":
			_w("sleeper %d shares a cell with a prop" % i)
		elif not seen.has(k2):
			_e("sleeper %d is in an unreachable cell" % i)
		if not Content.has_def(&"enemy", StringName(str(sl.get("enemy", "hollow")))):
			_e("sleeper %d enemy '%s' unknown" % [i, sl.get("enemy")])
	# Props.
	var route_cells: Dictionary = {}
	for path: Array in paths:
		for node: Variant in path:
			if node is Array:
				route_cells[node_key(node[0], node[1])] = true
	for p: Dictionary in layout.props:
		var pd: PropDef = Content.get_def(&"prop", StringName(str(p.get("prop", "")))) as PropDef
		if pd == null:
			_e("prop '%s' unknown" % p.get("prop"))
			continue
		var outside: bool = not layout.is_room(layout.room_at(p["level"], p["cell"]))
		if outside and int(p["level"]) != 0:
			_e("prop '%s' at %s level %d is outside the building" % [pd.id, p["cell"], p["level"]])
		if pd.collision != "none" and route_cells.has(node_key(p["level"], p["cell"])) and pd.size.x * pd.size.z > 0.5 and not bool(p.get("route_ok", false)):
			_w("prop '%s' at %s sits on the route corridor" % [pd.id, p["cell"]])
	for p2: Dictionary in layout.pickups:
		if not seen.has(node_key(p2["level"], p2["cell"])):
			_e("pickup '%s' unreachable" % p2.get("item"))
		elif not Content.has_def(&"item", StringName(str(p2.get("item", "")))):
			_e("pickup item '%s' unknown" % p2.get("item"))
	# Budget.
	var budget: Dictionary = DEFAULT_BUDGET.duplicate()
	budget.merge(def.budget, true)
	var piece_count: int = layout.walls.size()
	for li: int in layout.level_ids:
		piece_count += layout.room_cells(li).size() * 2
	stats = {"walls": layout.walls.size(), "pieces": piece_count, "props": layout.props.size(), "lights": layout.lights.size(),
		"sleepers": layout.sleepers.size(), "openings": layout.openings.size(), "levels": layout.level_ids.size(), "keys": keys.keys()}
	if layout.lights.size() > int(budget["lights"]):
		_e("too many lights %d > %d" % [layout.lights.size(), budget["lights"]])
	if layout.sleepers.size() > int(budget["enemies"]):
		_e("too many sleepers %d > %d" % [layout.sleepers.size(), budget["enemies"]])
	if piece_count > int(budget["pieces"]):
		_e("too many kit pieces %d > %d" % [piece_count, budget["pieces"]])
	if layout.props.size() > int(budget["props"]):
		_w("many authored props %d > %d" % [layout.props.size(), budget["props"]])


func _is_container(p: Dictionary) -> bool:
	if p.has("container"):
		return true
	var pd: PropDef = Content.get_def(&"prop", StringName(str(p.get("prop", "")))) as PropDef
	return pd != null and pd.container != ""


func _prop_cells() -> Dictionary:
	var out: Dictionary = {}
	for p: Dictionary in layout.props:
		var pd: PropDef = Content.get_def(&"prop", StringName(str(p.get("prop", "")))) as PropDef
		if pd != null and pd.collision != "none" and pd.size.x * pd.size.z > 0.35:
			out[node_key(p["level"], p["cell"])] = true
	return out


func _reconstruct(seen: Dictionary, k: String) -> Array:
	var out: Array = []
	var cur: String = k
	var guard: int = 0
	while cur != "" and guard < 4000:
		var e: Array = seen[cur]
		out.push_front(e[1])
		cur = e[0]
		guard += 1
	return out


func report() -> String:
	var lines: PackedStringArray = []
	for e: String in errors:
		lines.append("ERROR " + e)
	for w: String in warnings:
		lines.append("warn  " + w)
	return "\n".join(lines)


## Validates every POI and framework (CLI `make validate`, editor tool, tests).
static func validate_all() -> Dictionary:
	var errors: PackedStringArray = []
	var warnings: PackedStringArray = []
	var n: int = 0
	for d: PoiDef in Content.all(&"poi"):
		var v: PoiValidator = validate(d)
		errors.append_array(v.errors)
		warnings.append_array(v.warnings)
		n += 1
	for fw: FrameworkDef in Content.all(&"framework"):
		for lot: Variant in fw.lots:
			var l: Dictionary = lot
			var r: Array = l["rect"]
			var rect := Rect2(float(r[0]), float(r[1]), float(r[2]), float(r[3]))
			if rect.position.x < 0 or rect.position.y < 0 or rect.end.x > fw.size.x or rect.end.y > fw.size.y:
				errors.append("%s: lot '%s' %s outside framework size %s" % [fw.id, l["id"], rect, fw.size])
			var pick: String = str(l.get("pick", ""))
			if pick == "":
				continue
			var pd: PoiDef = Content.get_def(&"poi", StringName(pick)) as PoiDef
			if pd == null:
				errors.append("%s: lot '%s' picks unknown poi '%s'" % [fw.id, l["id"], pick])
				continue
			var facing: String = str(l.get("facing", "S"))
			var need := Vector2(pd.footprint) if facing in ["S", "N"] else Vector2(pd.footprint.y, pd.footprint.x)
			if need.x > rect.size.x + 0.01 or need.y > rect.size.y + 0.01:
				errors.append("%s: poi '%s' footprint %s (facing %s) does not fit lot '%s' %s" % [fw.id, pick, pd.footprint, facing, l["id"], rect.size])
	return {"errors": errors, "warnings": warnings, "summary": "%d POIs, %d frameworks checked" % [n, Content.all(&"framework").size()]}
