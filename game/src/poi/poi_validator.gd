class_name PoiValidator
extends RefCounted
## Static checks for an authored POI (run by `make validate`, the editor tool and GUT):
##  * the intended route is completable waypoint to waypoint (doors, breaches, stairs, ladders,
##    drop holes, keys picked up along the way; barricades and intact glass do not count), and
##    stays completable once every weak floor has given way (a fall must never strand the player),
##  * the loot room is reachable and holds a container; declared shortcuts exist and lead out,
##  * sleepers stand on walkable cells (not stairs, not inside props), props stay inside rooms and
##    off the route corridor, pickups are reachable,
##  * dungeon mechanics (ADR-0018): stable ids on sleepers, traps and triggers (TD-031), trap types
##    and placement, triggers that name real rooms/openings/pickups/containers/traps and wake a
##    group that exists, guardians in the loot room, lock kinds on doors,
##  * tall rooms (ADR-0021): nobody stands in a tall room's open space (sleepers, props, pickups,
##    traps, stair landings, holes), a gallery railing only lets anyone through where a gap is
##    authored, and that drop lands on the room's floor without stranding the player; roof
##    overrides name real wings,
##  * the building fits its footprint, and the performance budget (lights, sleepers, pieces) holds;
##  * alternatives (ADR-0030, PoiDressing): their structure, and EVERY option against the base (the
##    authored defaults) plus every full combination (a deterministic sample when there are too
##    many): each must keep the route, the loot room, the sleepers and the triggers valid, and every
##    shortcut and every locked door the base can open must stay usable;
##  * validate_all also generates and validates buildings from every template (BuildingGenerator)
##    and resolves every framework lot without a pick (LotPicker).
## Node graph: (level, cell) room/outside cells; "out" = the yard. A tall room's void cells are
## never nodes: stepping into one lands on the floor it rises from.

## New ADR-0030 scripts by path, so this compiles before the editor registers their class names.
const Dressing := preload("res://src/poi/poi_dressing.gd")
const Generator := preload("res://src/poi/building_generator.gd")
const Lots := preload("res://src/poi/lot_picker.gd")
const TemplateDef := preload("res://src/core/content/defs/building_template_def.gd")

const PASSABLE_DOOR_STATES: PackedStringArray = ["closed", "open", "broken", "missing", "locked", "locked_inside"]
const DEFAULT_BUDGET: Dictionary = {"lights": 10, "enemies": 14, "pieces": 2600, "props": 220}

var layout: PoiLayout
var errors: PackedStringArray = []
var warnings: PackedStringArray = []
## For the route visualizer: one Array[Vector3] (local positions) per route segment.
var paths: Array = []
var stats: Dictionary = {}
## Locked doors: opening id -> +1 / -1, the side of the wall (local +Z = the "a" room side) the
## door is approached from, i.e. where its padlock hangs and its key is used (PoiBuilder lock cues).
var lock_sides: Dictionary = {}
## The builder's prework, done on PoiManager's check worker by PoiBuilder.prepare_check (`prepared`):
## barricaded door id -> +1 / -1 (the face its barricade stands on), the roof plan, the interior
## probe boxes, the scatter's clutter props by room tag and the per-run decals.
var prepared: bool = false
var barricade_sides: Dictionary = {}
var roof_wings: Array[RoofPlanner.Wing] = []
var probe_boxes: Array[AABB] = []
var clutter: Dictionary = {}
var run_decals: Array[Dictionary] = []
var _keys_found: Dictionary = {}
## Weak floors treated as already collapsed: stepping onto one drops you to the level below.
var _collapsed: bool = false
## node key -> trap id for every weak floor.
var _weak: Dictionary = {}
## An opening treated as impassable (lock side search).
var _blocked_op: String = ""
## level -> {cell: true}: cells left open over a stair flight or a ladder hatch from the level
## below (PoiLayout.stairwell_cells). They have no floor, so nothing may stand on them.
var _wells: Dictionary = {}


static func validate(def: PoiDef) -> PoiValidator:
	var v := PoiValidator.new()
	v.layout = PoiLayout.compile(def)
	v.errors.append_array(v.layout.errors)
	v._run()
	if def.layout.has("alternatives"):
		v._check_alternatives(def)
	return v


## Full combinations of alternatives tried beyond the single changes (Dressing.combinations).
const COMBO_LIMIT: int = 16


## ADR-0030: the alternatives block is well formed, and every option (each one changed alone from the
## defaults, then full combinations) validates like the base. Errors and new warnings are reported
## once each, tagged with the picks that showed them ("[alt bedroom=nursery, front=boarded]").
func _check_alternatives(def: PoiDef) -> void:
	var structure: PackedStringArray = Dressing.check(def)
	for e: String in structure:
		_e(e)
	if not structure.is_empty():
		return
	var base_warn: Dictionary = {}
	for wn: String in warnings:
		base_warn[wn] = true
	var base_use: Dictionary = _usable_exits()
	var seen_e: Dictionary = {}
	var seen_w: Dictionary = {}
	var combos: Array[Dictionary] = Dressing.combinations(def, COMBO_LIMIT)
	for i: int in range(1, combos.size()):
		var picks: Dictionary = combos[i]
		var vv := PoiValidator.new()
		vv.layout = PoiLayout.compile(Dressing.resolve(def, picks))
		vv.errors.append_array(vv.layout.errors)
		vv._run()
		vv._check_exits_kept(base_use)
		var tag: String = "[alt %s] " % Dressing.describe(picks)
		var head: String = "%s: " % layout.poi_id
		for e2: String in vv.errors:
			if not seen_e.has(e2):
				seen_e[e2] = true
				errors.append(head + tag + e2.trim_prefix(head))
		for w2: String in vv.warnings:
			if not base_warn.has(w2) and not seen_w.has(w2):
				seen_w[w2] = true
				warnings.append(head + tag + w2.trim_prefix(head))
	stats["variants"] = combos.size()


## Which exits work in this layout: shortcut opening id -> usable from its inside cell, and locked
## door id -> its key can be found.
func _usable_exits() -> Dictionary:
	var out: Dictionary = {"shortcuts": {}, "locks": {}}
	var keys: Dictionary = {}
	var seen: Dictionary = _reach_all(keys)
	for sc: Variant in layout.shortcuts:
		var op_id: String = str((sc as Dictionary).get("opening", "")) if sc is Dictionary else str(sc)
		var op: Dictionary = layout.opening(op_id)
		if op.is_empty():
			continue
		out["shortcuts"][op_id] = seen.has(node_key(int(op["level"]), op["cell"])) and _opening_passable(op, op["cell"], keys)
	for op2: Dictionary in layout.openings:
		if str(op2["state"]) == "locked" and str(op2["key"]) != "":
			out["locks"][str(op2["id"])] = keys.has(str(op2["key"]))
	return out


## A shortcut or a locked door the base can use must stay usable in every alternative (an option
## that barricades the bolted way out, or drops the key, breaks the dungeon even when the route
## itself still completes).
func _check_exits_kept(base: Dictionary) -> void:
	var now: Dictionary = _usable_exits()
	for op_id: String in base["shortcuts"]:
		if bool(base["shortcuts"][op_id]) and not bool((now["shortcuts"] as Dictionary).get(op_id, false)):
			_e("shortcut '%s' can no longer be used from inside" % op_id)
	for lock_id: String in base["locks"]:
		if bool(base["locks"][lock_id]) and (now["locks"] as Dictionary).has(lock_id) and not bool(now["locks"][lock_id]):
			_e("locked door '%s': its key can no longer be found" % lock_id)


func ok() -> bool:
	return errors.is_empty()


func _e(msg: String) -> void:
	errors.append("%s: %s" % [layout.poi_id, msg])


func _w(msg: String) -> void:
	warnings.append("%s: %s" % [layout.poi_id, msg])


static func node_key(li: int, c: Vector2i) -> String:
	return "%d:%d:%d" % [li, c.x, c.y]


## True when (li, c) is the open well over a stair flight or a ladder hatch (no floor slab).
func _over_well(li: int, c: Vector2i) -> bool:
	if not _wells.has(li):
		_wells[li] = layout.stairwell_cells(li)
	return (_wells[li] as Dictionary).has(c)


## Rooms, plus a yard ring (YARD cells) around level 0 so routes can walk round the outside.
const YARD: int = 3


func _walkable(li: int, c: Vector2i) -> bool:
	if layout.is_room(layout.room_at(li, c)):
		return true
	if li != 0 or layout.room_at(li, c) != ".":
		return false
	var lv: Dictionary = layout.levels.get(0, {})
	return c.x >= -YARD and c.y >= -YARD and c.x < int(lv.get("w", 0)) + YARD and c.y < int(lv.get("d", 0)) + YARD


## Where a step onto (li, c) ends: on the cell itself, (weak floors collapsed) on the cell below, or
## (a tall room's void) on the floor of the room it rises from.
func _land(li: int, c: Vector2i) -> Array:
	if _collapsed and _weak.has(node_key(li, c)):
		return [li - 1, c]
	if layout.is_void(li, c):
		return layout.floor_cell(li, c)
	return [li, c]


## What stands between two cells across an edge: a wall (passable only through an opening) or a
## gallery railing (only where an "open"/"breach" gap is authored in it).
func _edge_passable(li: int, e: Array, from_cell: Vector2i, keys: Dictionary) -> bool:
	var ek: String = PoiLayout.edge_key(li, e[0], e[1])
	var wall: Dictionary = layout.walls.get(ek, {})
	if not wall.is_empty():
		var op: Dictionary = wall["opening"]
		return not op.is_empty() and _opening_passable(op, from_cell, keys)
	var gal: Dictionary = layout.galleries.get(ek, {})
	if not gal.is_empty():
		var gop: Dictionary = gal["opening"]
		return not gop.is_empty() and _opening_passable(gop, from_cell, keys)
	return true


## Neighbours of a node given the keys held.
func _neighbors(li: int, c: Vector2i, keys: Dictionary) -> Array:
	var out: Array = []
	if _collapsed and _weak.has(node_key(li, c)):
		return [[li - 1, c]]
	var here: String = layout.room_at(li, c)
	var outside_here: bool = not layout.is_room(here)
	if outside_here and li == 0:
		out.append("out")
	for side: int in 4:
		var n: Vector2i = c + PoiLayout.DIRS[side]
		if not _edge_passable(li, PoiLayout.side_edge(c, side), c, keys):
			continue
		# Over a gallery's gap (or through a door onto a tall room's void) is a one-way drop.
		if _walkable(li, n) or layout.is_void(li, n):
			out.append(_land(li, n))
	for s: Dictionary in layout.stairs:
		if int(s["level"]) == li and s["cell"] == c:
			out.append(_land(li + 1, s["landing"]))
		elif int(s["level"]) + 1 == li and s["landing"] == c:
			out.append([li - 1, s["cell"]])
	for l: Dictionary in layout.ladders:
		var lc: Vector2i = l["cell"]
		var land: Vector2i = l.get("landing", lc)
		if int(l["level"]) == li and lc == c:
			out.append(_land(li + 1, land))
		elif int(l["level"]) + 1 == li and land == c:
			out.append([li - 1, lc])
	for h: Dictionary in layout.holes:
		if int(h["level"]) == li and h["cell"] == c:
			out.append(_land(li - 1, c))
	return out


func _opening_passable(op: Dictionary, from_cell: Vector2i, keys: Dictionary) -> bool:
	if _blocked_op != "" and str(op["id"]) == _blocked_op:
		return false
	var t: String = op["type"]
	var st: String = op["state"]
	if t in ["open", "breach", "half"]:
		return true
	if PoiLayout.is_window(t):
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


## Everything reachable from outside, picking up keys as they come into reach.
func _reach_all(keys: Dictionary) -> Dictionary:
	var seen: Dictionary = _bfs(["out"], keys)
	while _keys_reachable(seen, keys):
		seen = _bfs(["out"], keys)
	return seen


func _run() -> void:
	var def: PoiDef = layout.def
	if layout.level_ids.is_empty():
		_e("no levels")
		return
	_weak.clear()
	_wells.clear()
	for t: Dictionary in layout.traps:
		if str(t["type"]) == "weak_floor":
			_weak[node_key(int(t["level"]), t["cell"])] = str(t["tid"])
	# Footprint.
	var ext: Rect2 = layout.extent()
	if ext.position.x < 0 or ext.position.y < 0 or ext.end.x > def.footprint.x + 0.01 or ext.end.y > def.footprint.y + 0.01:
		_e("building %s does not fit footprint %s" % [ext, def.footprint])
	# Reachability with keys picked up as they become reachable.
	var keys: Dictionary = {}
	var seen: Dictionary = _reach_all(keys)
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
	var route_ok: bool = true
	var prev: Variant = "out"
	for i: int in layout.route.size():
		var wp: Dictionary = layout.route[i]
		var li: int = wp["level"]
		var c: Vector2i = wp["cell"]
		if not _walkable(li, c):
			if layout.is_void(li, c):
				_e("route waypoint %d '%s' at %s (level %d) is in a tall room's open space; put it on its floor (level %d)" % [
					i, wp.get("label", ""), c, li, int(layout.floor_cell(li, c)[0])])
			else:
				_e("route waypoint %d '%s' is not on a walkable cell %s (level %d)" % [i, wp.get("label", ""), c, li])
			route_ok = false
			continue
		var s2: Dictionary = _bfs([prev], keys)
		var k: String = node_key(li, c)
		if not s2.has(k):
			_e("route waypoint %d '%s' unreachable from the previous one" % [i, wp.get("label", "")])
			route_ok = false
		else:
			paths.append(_reconstruct(s2, k))
		prev = [li, c]
	if route_ok and not _weak.is_empty():
		_check_collapsed_route(seen)
	_check_tall_rooms(seen, keys)
	# Shortcuts lead outside.
	for sc: Variant in layout.shortcuts:
		var op_id: String = str((sc as Dictionary).get("opening", "")) if sc is Dictionary else str(sc)
		if layout.opening(op_id).is_empty():
			_e("shortcut opening '%s' not found" % op_id)
	# Sleepers.
	var stair_cells: Dictionary = {}
	for s: Dictionary in layout.stairs:
		for c: Vector2i in s["cells"]:
			stair_cells[node_key(s["level"], c)] = true
	var blocked: Dictionary = _prop_cells()
	# A sitter that lands on the chair it was authored at shares that chair's cell by design
	# (SleeperAnchors, ADR-0022).
	var landed: Dictionary = {} if layout.sleepers.is_empty() else SleeperAnchors.assign(layout)["by_sleeper"]
	for i: int in layout.sleepers.size():
		var sl: Dictionary = layout.sleepers[i]
		var k2: String = node_key(sl["level"], sl["cell"])
		if layout.is_void(sl["level"], sl["cell"]):
			_e("sleeper '%s' at %s (level %d) floats in a tall room's open space (no floor there)" % [sl.get("sid", i), sl["cell"], sl["level"]])
		elif not layout.is_room(layout.room_at(sl["level"], sl["cell"])):
			_e("sleeper %d is not inside a room (%s level %d)" % [i, sl["cell"], sl["level"]])
		elif stair_cells.has(k2):
			_e("sleeper %d stands on stairs" % i)
		elif _over_well(int(sl["level"]), sl["cell"]):
			_e("sleeper '%s' at %s (level %d) floats over a stairwell or hatch opening" % [sl.get("sid", i), sl["cell"], sl["level"]])
		elif blocked.has(k2) and str(sl.get("pose", "stand")) != "lie" and not landed.has(str(sl.get("sid", ""))):
			_w("sleeper %d shares a cell with a prop" % i)
		elif not seen.has(k2):
			_e("sleeper %d is in an unreachable cell" % i)
		if _weak.has(k2):
			_w("sleeper '%s' stands on weak floor '%s'" % [sl["sid"], _weak[k2]])
		for bt: Dictionary in layout.traps:
			# A sleeper spawned on the jaws springs them on itself.
			if str(bt["type"]) == "bear_trap" and int(bt["level"]) == int(sl["level"]) and (bt["pos"] as Vector2).distance_to(sl["pos"]) < 0.55:
				_w("sleeper '%s' stands on bear trap '%s'" % [sl["sid"], bt["tid"]])
		if not ContentDB.instance.has_def(&"enemy", StringName(str(sl.get("enemy", "hollow")))):
			_e("sleeper %d enemy '%s' unknown" % [i, sl.get("enemy")])
	# Props.
	var route_cells: Dictionary = {}
	for path: Array in paths:
		for node: Variant in path:
			if node is Array:
				route_cells[node_key(node[0], node[1])] = true
	for p: Dictionary in layout.props:
		var pd: PropDef = ContentDB.instance.get_def(&"prop", StringName(str(p.get("prop", "")))) as PropDef
		if pd == null:
			_e("prop '%s' unknown" % p.get("prop"))
			continue
		var in_void: bool = layout.is_void(p["level"], p["cell"])
		var outside: bool = not layout.is_room(layout.room_at(p["level"], p["cell"])) and not in_void
		var hangs: bool = pd.wall_mounted or pd.has_tag("stairwell") or float(p.get("y", 0.0)) >= 0.5
		if outside and int(p["level"]) != 0:
			_e("prop '%s' at %s level %d is outside the building" % [pd.id, p["cell"], p["level"]])
		# A tall room's open space has no floor: only what hangs on its walls or high in it.
		elif in_void and not hangs:
			_e("prop '%s' at %s level %d floats in a tall room's open space (no floor there; place it on level %d)" % [
				str(p.get("id", pd.id)), p["cell"], p["level"], int(layout.floor_cell(p["level"], p["cell"])[0])])
		# Only what stands on the floor needs one: wall-mounted props hang on the well's walls,
		# raised ones (y >= 0.5 m: under a ceiling or on a counter, which is checked itself) hang
		# or sit above it, and a prop tagged "stairwell" (a railing, a ladder) belongs in it.
		elif _over_well(int(p["level"]), p["cell"]) and not pd.wall_mounted and not pd.has_tag("stairwell") \
				and float(p.get("y", 0.0)) < 0.5:
			_e("prop '%s' at %s level %d floats over a stairwell or hatch opening (no floor there)" % [
				str(p.get("id", pd.id)), p["cell"], p["level"]])
		if pd.collision != "none" and route_cells.has(node_key(p["level"], p["cell"])) and pd.size.x * pd.size.z > 0.5 and not bool(p.get("route_ok", false)):
			_w("prop '%s' at %s sits on the route corridor" % [pd.id, p["cell"]])
	_check_wall_gaps()
	for p2: Dictionary in layout.pickups:
		if layout.is_void(int(p2["level"]), p2["cell"]):
			_e("pickup '%s' at %s level %d floats in a tall room's open space" % [p2["pid"], p2["cell"], p2["level"]])
		elif _over_well(int(p2["level"]), p2["cell"]):
			_e("pickup '%s' at %s level %d floats over a stairwell or hatch opening" % [p2["pid"], p2["cell"], p2["level"]])
		if not seen.has(node_key(p2["level"], p2["cell"])):
			_e("pickup '%s' unreachable" % p2.get("item"))
		elif not ContentDB.instance.has_def(&"item", StringName(str(p2.get("item", "")))):
			_e("pickup item '%s' unknown" % p2.get("item"))
	_check_ids()
	_check_traps(seen, stair_cells)
	_check_stair_doors()
	_check_triggers(seen)
	_check_locks(keys)
	_check_roof()
	_check_dungeon_life()
	# Budget.
	var budget: Dictionary = DEFAULT_BUDGET.duplicate()
	budget.merge(def.budget, true)
	var piece_count: int = layout.walls.size() + layout.galleries.size()
	for li: int in layout.level_ids:
		piece_count += layout.room_cells(li).size() * 2
	var groups: Dictionary = {}
	for sl2: Dictionary in layout.sleepers:
		if str(sl2["group"]) != "":
			groups[str(sl2["group"])] = true
	stats = {"walls": layout.walls.size(), "pieces": piece_count, "props": layout.props.size(), "lights": layout.lights.size(),
		"sleepers": layout.sleepers.size(), "openings": layout.openings.size(), "levels": layout.level_ids.size(), "keys": keys.keys(),
		"traps": layout.traps.size(), "triggers": layout.triggers.size(), "groups": groups.keys()}
	if layout.lights.size() > int(budget["lights"]):
		_e("too many lights %d > %d" % [layout.lights.size(), budget["lights"]])
	if layout.sleepers.size() > int(budget["enemies"]):
		_e("too many sleepers %d > %d" % [layout.sleepers.size(), budget["enemies"]])
	if piece_count > int(budget["pieces"]):
		_e("too many kit pieces %d > %d" % [piece_count, budget["pieces"]])
	if layout.props.size() > int(budget["props"]):
		_w("many authored props %d > %d" % [layout.props.size(), budget["props"]])


## Wall props this far (m) off their wall's face, or into it, are reported: about what a
## player sees from across a room as a prop hanging in the air or swallowed by its wall.
const WALL_GAP_MAX: float = 0.05
## How far behind a wall prop the wall it hangs on may be before it hangs on nothing (m).
const WALL_REACH: float = 0.6


## Every wall prop (wall-mounted, or placed `against` a wall) has its back on a wall's face: within
## WALL_GAP_MAX of it, measured from the footprint's nearest point (PropDef.back_depth square on)
## as PoiBuilder places it. A prop `against` a wall stands 1 cm off by construction, so this catches
## the hand-placed ones (`pos`), authors' rotations and walls that are not there. Messages start
## with "wall gap" (test_poi_wall_gaps.gd collects them across every building).
func _check_wall_gaps() -> void:
	for p: Dictionary in layout.props:
		var pd: PropDef = ContentDB.instance.get_def(&"prop", StringName(str(p.get("prop", "")))) as PropDef
		# "wall_ok": hung on or leant against something that is not a building wall (a counter's
		# front, a canopy, a sawhorse); it is placed by hand and not checked.
		if pd == null or not (pd.wall_mounted or p.has("against")) or bool(p.get("wall_ok", false)):
			continue
		var plan: Vector3 = PoiLayout.prop_plan(p, pd)
		var r: float = deg_to_rad(plan.z)
		var fwd := Vector2(sin(r), cos(r))
		# From the footprint's nearest point toward the wall: straight back from a hand-placed
		# prop, toward the named wall from one `against` it (however it is turned).
		var dir: Vector2 = -fwd
		var reach: float = pd.back_depth()
		var side: String = str(p.get("against", ""))
		if PoiLayout.SIDES.has(side):
			var s: int = int(PoiLayout.SIDES[side])
			dir = Vector2(PoiLayout.DIRS[s])
			reach = PoiLayout.wall_reach(pd, plan.z - PoiLayout.AGAINST_ROT[s])
		var back_pt: Vector2 = Vector2(plan.x, plan.y) + dir * reach
		var li: int = int(p["level"])
		if pd.wall_mounted:
			# A prop hung above its storey's walls hangs on the storey above's.
			li += int(floor((float(p.get("height", 1.4)) + float(p.get("y", 0.0))) / PoiLayout.STOREY))
		var gap: float = wall_gap(layout, li, back_pt, dir)
		var what: String = "'%s' (%s) at %s level %d" % [str(p.get("id", pd.id)), pd.id, p["pos"], int(p["level"])]
		if is_inf(gap):
			_w("wall gap: %s has no wall within %.1f m behind it" % [what, WALL_REACH])
		elif gap > WALL_GAP_MAX:
			_w("wall gap: %s stands %.2f m off its wall" % [what, gap])
		elif gap < -WALL_GAP_MAX:
			_w("wall gap: %s sinks %.2f m into its wall" % [what, -gap])


## Distance (m) from `from` (layout-local plan point) along `dir` to the nearest face of a wall on
## level `li` whose span it meets (a gallery's railing counts: an organ backs onto one); negative
## when `from` is already inside the wall, INF when no wall lies within WALL_REACH. Only walls
## roughly square to `dir` count (a prop hung on a wall faces away from it).
static func wall_gap(lay: PoiLayout, li: int, from: Vector2, dir: Vector2) -> float:
	var best: float = INF
	var half: float = PoiBuilder.WALL_T * 0.5
	var c0 := Vector2i(int(floor(from.x)), int(floor(from.y)))
	var seen: Dictionary = {}
	for dz: int in range(-1, 2):
		for dx: int in range(-1, 2):
			for side: int in 4:
				var e: Array = PoiLayout.side_edge(c0 + Vector2i(dx, dz), side)
				var key: String = PoiLayout.edge_key(li, e[0], e[1])
				if seen.has(key) or not (lay.walls.has(key) or lay.galleries.has(key)):
					continue
				seen[key] = true
				var c: Vector2i = e[1]
				# The wall's centre line on its axis, the prop's coordinate across it and along it.
				var horiz: bool = e[0] == "h"
				var line: float = float(c.y if horiz else c.x)
				var across: float = from.y if horiz else from.x
				var d_across: float = dir.y if horiz else dir.x
				if absf(d_across) < 0.7:
					continue
				# Distance to the face on the prop's side of the centre line (negative: inside it).
				var to_line: float = (line - across) / d_across
				var t: float = to_line - half / absf(d_across)
				if t > WALL_REACH or to_line < -half:
					continue
				var hit: Vector2 = from + dir * maxf(t, 0.0)
				var along: float = hit.x if horiz else hit.y
				var lo: float = float(c.x if horiz else c.y)
				if along < lo - 0.01 or along > lo + 1.01:
					continue
				if absf(t) < absf(best):
					best = t
	return best


## The route again with every weak floor already given way: a waypoint on a weak floor counts as
## reached by falling through it. And from under each weak floor the way out must stay open.
## `intact`: what is reachable before anything gave way (a floor nobody can reach never falls).
func _check_collapsed_route(intact: Dictionary) -> void:
	_collapsed = true
	var keys: Dictionary = {}
	_reach_all(keys)
	var prev: Variant = "out"
	for i: int in layout.route.size():
		var wp: Dictionary = layout.route[i]
		var target: Array = _land(int(wp["level"]), wp["cell"])
		var s: Dictionary = _bfs([prev], keys)
		if not s.has(node_key(target[0], target[1])):
			_e("route waypoint %d '%s' unreachable once the weak floors give way" % [i, wp.get("label", "")])
			break
		prev = target
	for wk: String in _weak:
		var parts: PackedStringArray = wk.split(":")
		var below := [int(parts[0]) - 1, Vector2i(int(parts[1]), int(parts[2]))]
		if not intact.has(wk):
			continue  # never reached: nothing to fall from
		if not _bfs([below], keys).has("out"):
			_e("falling through weak floor '%s' traps the player: no way out from %s level %d" % [_weak[wk], below[1], below[0]])
	_collapsed = false


## Tall rooms (ADR-0021): every "storeys" room rises somewhere and every "open_roof" room reaches the
## roof; stair landings and drop holes have a floor; and each authored drop off a gallery (a gap in
## its railing, or a door or broken window onto a tall room's open space) lands where the player can
## still get out (a fall must never strand them).
func _check_tall_rooms(seen: Dictionary, keys: Dictionary) -> void:
	var rises: Dictionary = {}
	for vk: String in layout.void_base:
		var b: Array = layout.void_base[vk]
		rises["%d:%s" % [int(b[0]), b[1]]] = true
	var under_roof: Dictionary = {}
	for li: int in layout.level_ids:
		for c: Vector2i in layout.room_cells(li):
			if not layout.is_built(layout.column_top(li, c) + 1, c):
				under_roof["%d:%s" % [li, layout.room_at(li, c)]] = true
	for li2: int in layout.level_ids:
		for ch: String in (layout.levels[li2]["rooms"] as Dictionary):
			var rd: Dictionary = layout.room_def(li2, ch)
			var rk: String = "%d:%s" % [li2, ch]
			if layout.room_storeys(li2, ch) > 1 and not rises.has(rk):
				_w("room '%s' (level %d) has storeys %d but no '%s' above it, so it is one storey tall" % [ch, li2, layout.room_storeys(li2, ch), PoiLayout.VOID])
			if bool(rd.get("open_roof", false)) and not under_roof.has(rk):
				_w("room '%s' (level %d) is open_roof but no part of it is under the roof" % [ch, li2])
	for s: Dictionary in layout.stairs:
		if layout.is_void(int(s["level"]) + 1, s["landing"]):
			_e("stairs at %s (level %d) land in a tall room's open space on level %d" % [s["cell"], s["level"], int(s["level"]) + 1])
	for h: Dictionary in layout.holes:
		if layout.is_void(int(h["level"]), h["cell"]):
			_e("hole at %s (level %d) is in a tall room's open space: there is no floor to break" % [h["cell"], h["level"]])
	# Drops off a gallery: through a gap in its railing, or a passable opening in a wall onto the void.
	var drops: Array = []
	for gk: String in layout.galleries:
		var g: Dictionary = layout.galleries[gk]
		if not (g["opening"] as Dictionary).is_empty():
			drops.append([g, g["opening"]])
	for wk: String in layout.walls:
		var w: Dictionary = layout.walls[wk]
		if not (w["opening"] as Dictionary).is_empty() and (str(w["a"]) == PoiLayout.VOID) != (str(w["b"]) == PoiLayout.VOID):
			drops.append([w, w["opening"]])
	for d: Array in drops:
		var e: Dictionary = d[0]
		var op: Dictionary = d[1]
		var li3: int = int(e["level"])
		var cells: Array[Vector2i] = PoiLayout.edge_cells(str(e["axis"]), e["cell"])
		var from: Vector2i = cells[1] if layout.is_void(li3, cells[0]) else cells[0]
		var into: Vector2i = cells[0] if layout.is_void(li3, cells[0]) else cells[1]
		if not seen.has(node_key(li3, from)) or not _opening_passable(op, from, keys):
			continue
		var land: Array = layout.floor_cell(li3, into)
		if not _bfs([land], keys).has("out"):
			_e("the drop through '%s' from %s (level %d) strands the player: no way out from %s level %d" % [op["id"], from, li3, land[1], land[0]])


## style.roof keys and type, and its per-wing overrides (RoofPlanner): each must name a cell of a
## roof on its level, with a known type.
func _check_roof() -> void:
	var roof: Variant = layout.style.get("roof", {})
	if not roof is Dictionary:
		_e("style.roof must be an object")
		return
	for k: Variant in (roof as Dictionary).keys():
		if not str(k).begins_with("_") and not RoofPlanner.ROOF_KEYS.has(str(k)):
			_e("style.roof has unknown key '%s' (%s)" % [k, ", ".join(RoofPlanner.ROOF_KEYS)])
	var t: String = str((roof as Dictionary).get("type", "gable"))
	if not RoofPlanner.TYPES.has(t):
		_e("style.roof type '%s' unknown (%s)" % [t, ", ".join(RoofPlanner.TYPES)])
	var roof_errors: Array = []
	RoofPlanner.plan(layout, roof_errors)
	for e: String in roof_errors:
		_e(e)


static func _valid_id(s: String) -> bool:
	if s == "" or s.begins_with("_"):
		return false
	for ch: String in s:
		if not ((ch >= "a" and ch <= "z") or (ch >= "0" and ch <= "9") or ch == "_"):
			return false
	return true


## Stable ids (TD-031): sleepers, traps and triggers must have unique ids; containers and pickups
## should (their saved state is otherwise keyed by list position).
func _check_ids() -> void:
	var seen_ids: Dictionary = {}
	for i: int in layout.sleepers.size():
		var sl: Dictionary = layout.sleepers[i]
		if not sl.has("id"):
			_e("sleeper %d has no id" % i)
		elif not _valid_id(str(sl["id"])):
			_e("sleeper id '%s' must be lower_snake_case" % sl["id"])
		elif seen_ids.has("s:" + str(sl["id"])):
			_e("duplicate sleeper id '%s'" % sl["id"])
		seen_ids["s:" + str(sl.get("id", ""))] = true
	for i2: int in layout.traps.size():
		var t: Dictionary = layout.traps[i2]
		if not t.has("id"):
			_e("trap %d (%s) has no id" % [i2, t["type"]])
		elif not _valid_id(str(t["id"])):
			_e("trap id '%s' must be lower_snake_case" % t["id"])
		elif seen_ids.has("t:" + str(t["id"])):
			_e("duplicate trap id '%s'" % t["id"])
		seen_ids["t:" + str(t.get("id", ""))] = true
	for tg: Dictionary in layout.triggers:
		if bool(tg["implicit"]):
			continue
		if str(tg["id"]) == "":
			_e("a trigger has no id")
		elif not _valid_id(str(tg["id"])):
			_e("trigger id '%s' must be lower_snake_case" % tg["id"])
		elif seen_ids.has("g:" + str(tg["id"])):
			_e("duplicate trigger id '%s'" % tg["id"])
		seen_ids["g:" + str(tg["id"])] = true
	var unnamed: PackedStringArray = []
	for p: Dictionary in layout.props:
		if p.has("id"):
			var pid: String = str(p["id"])
			if not _valid_id(pid) or pid.is_valid_int():
				_e("prop id '%s' must be lower_snake_case and not a number" % pid)
			elif seen_ids.has("p:" + pid):
				_e("duplicate prop id '%s'" % pid)
			seen_ids["p:" + pid] = true
		elif _is_container(p):
			unnamed.append("%s@%s" % [p.get("prop", "?"), p["cell"]])
	if not unnamed.is_empty():
		_w("%d container props have no id (loot state keyed by list position): %s%s" % [unnamed.size(),
			", ".join(unnamed.slice(0, 4)), " ..." if unnamed.size() > 4 else ""])
	for pk: Dictionary in layout.pickups:
		if not bool(pk.get("is_note", false)) and not pk.has("id"):
			_w("pickup '%s' has no id (taken state keyed by list position)" % pk.get("item", "?"))
		var key: String = "k:" + str(pk["pid"])
		if seen_ids.has(key):
			_e("duplicate pickup id '%s'" % pk["pid"])
		seen_ids[key] = true


## Trap types, keys and placement: cell traps inside rooms (bear traps may sit in the yard), weak
## floors over a room, creaky floors wholly indoors, edge traps across a passable edge.
## A doorway onto a stair flight above its first step meets the steps a metre or more up: the player
## has to jump onto them (the fire station's bay door, the first playtest). Doors and openings
## belong at a flight's foot or along the floor beside it.
func _check_stair_doors() -> void:
	for s: Dictionary in layout.stairs:
		var mid: Dictionary = {}
		var cells: Array = s["cells"]
		for k: int in range(1, cells.size()):
			mid[cells[k]] = true
		for op: Dictionary in layout.openings:
			if int(op["level"]) != int(s["level"]) or PoiLayout.is_window(str(op["type"])) or str(op["type"]) == "half":
				continue
			var c: Vector2i = op["cell"]
			var n: Vector2i = c + PoiLayout.DIRS[int(op["side"])]
			if mid.has(c) or mid.has(n):
				_e("opening '%s' at %s (level %d) opens onto the stair flight from %s above its foot: move it to the foot (%s) or off the flight" % [
					op["id"], c, int(op["level"]), s["cell"], s["cell"]])


func _check_traps(seen: Dictionary, stair_cells: Dictionary) -> void:
	for t: Dictionary in layout.traps:
		var tid: String = str(t["tid"])
		var type: String = str(t["type"])
		var li: int = int(t["level"])
		if not PoiLayout.TRAP_TYPES.has(type):
			_e("trap '%s' type '%s' unknown (%s)" % [tid, type, ", ".join(PoiLayout.TRAP_TYPES.keys())])
			continue
		if not layout.levels.has(li):
			_e("trap '%s' is on missing level %d" % [tid, li])
			continue
		for rk: Variant in _raw_keys(t):
			if not str(rk).begins_with("_") and not PoiLayout.TRAP_KEYS.has(str(rk)):
				_e("trap '%s' has unknown key '%s'" % [tid, rk])
		if str(t["kind"]) == "cell":
			for c: Vector2i in t["cells"]:
				var nk: String = node_key(li, c)
				if not layout.is_room(layout.room_at(li, c)) and not (type == "bear_trap" and li == 0 and _walkable(0, c)):
					_e("trap '%s' cell %s (level %d) is not inside a room" % [tid, c, li])
				elif stair_cells.has(nk):
					_e("trap '%s' sits on stairs at %s" % [tid, c])
				elif _over_well(li, c):
					_e("trap '%s' cell %s (level %d) floats over a stairwell or hatch opening" % [tid, c, li])
				elif not seen.has(nk) and type != "weak_floor":
					_w("trap '%s' at %s can never be reached" % [tid, c])
			if type == "weak_floor":
				var c0: Vector2i = t["cell"]
				if not layout.levels.has(li - 1) or not layout.is_room(layout.room_at(li - 1, c0)):
					_e("weak floor '%s' at %s level %d needs a room cell directly below" % [tid, c0, li])
				for h: Dictionary in layout.holes:
					if int(h["level"]) == li and h["cell"] == c0:
						_e("weak floor '%s' at %s is already a hole" % [tid, c0])
		else:
			var c1: Vector2i = t["cell"]
			var n: Vector2i = c1 + PoiLayout.DIRS[int(t["side_i"])]
			if not _walkable(li, c1) and not _walkable(li, n):
				_e("trap '%s' edge at %s %s is outside the building" % [tid, c1, PoiLayout.SIDE_NAMES[int(t["side_i"])]])
				continue
			var wall: Dictionary = layout.walls.get(PoiLayout.edge_key(li, t["axis"], t["edge"]), {})
			if not wall.is_empty() and (wall["opening"] as Dictionary).is_empty():
				_e("trap '%s' crosses a solid wall at %s %s" % [tid, c1, PoiLayout.SIDE_NAMES[int(t["side_i"])]])
			var gal: Dictionary = layout.galleries.get(PoiLayout.edge_key(li, t["axis"], t["edge"]), {})
			if not gal.is_empty() and (gal["opening"] as Dictionary).is_empty():
				_e("trap '%s' crosses a gallery railing at %s %s" % [tid, c1, PoiLayout.SIDE_NAMES[int(t["side_i"])]])
			if type == "shotgun" and not layout.is_room(layout.room_at(li, c1)):
				_e("shotgun trap '%s': its 'at' cell %s holds the gun and must be inside a room" % [tid, c1])
			# The chair-and-gun and the chime's cans stand on the 'at' cell's floor (an alarm hangs
			# on the frame).
			if type in ["shotgun", "can_chime"] and _over_well(li, c1):
				_e("trap '%s': its 'at' cell %s (level %d) is a stairwell or hatch opening; put 'at' on the floor side" % [tid, c1, li])


static func _raw_keys(t: Dictionary) -> Array:
	var out: Array = []
	for k: Variant in t.keys():
		# Keys PoiLayout adds while compiling.
		if str(k) in ["tid", "kind", "side_i", "axis", "edge", "cells", "cell", "rot_set"]:
			continue
		out.append(k)
	return out


## Triggers name real things and wake a group that has sleepers; every group can be woken;
## guardians wait in the loot room.
func _check_triggers(seen: Dictionary) -> void:
	var group_sleepers: Dictionary = {}
	for sl: Dictionary in layout.sleepers:
		var g: String = str(sl["group"])
		if g != "":
			group_sleepers[g] = int(group_sleepers.get(g, 0)) + 1
	var group_triggers: Dictionary = {}
	for tg: Dictionary in layout.triggers:
		var tid: String = str(tg["id"])
		var g2: String = str(tg["group"])
		if bool(tg["implicit"]):
			group_triggers[g2] = true
			if layout.loot_room.is_empty():
				_w("a guardian waits for its loot room, but the POI declares none")
			continue
		for rk: Variant in (tg["raw"] as Dictionary).keys():
			if not str(rk).begins_with("_") and not PoiLayout.TRIGGER_KEYS.has(str(rk)):
				_e("trigger '%s' has unknown key '%s'" % [tid, rk])
		var on: String = str(tg["on"])
		if not PoiLayout.TRIGGER_ON.has(on):
			_e("trigger '%s' on '%s' unknown (%s)" % [tid, on, ", ".join(PoiLayout.TRIGGER_ON)])
			continue
		if g2 == "":
			_e("trigger '%s' has no group" % tid)
		elif not group_sleepers.has(g2):
			_e("trigger '%s' wakes group '%s', but no sleeper is in it" % [tid, g2])
		group_triggers[g2] = true
		if float(tg["delay"]) < 0.0:
			_e("trigger '%s' delay must be >= 0" % tid)
		match on:
			"room":
				var li: int = int(tg["level"])
				var ch: String = str(tg["room"])
				if ch.length() != 1 or (layout.levels.get(li, {}) as Dictionary).is_empty() or not (layout.levels[li]["rooms"] as Dictionary).has(ch):
					_e("trigger '%s' room '%s' does not exist on level %d" % [tid, ch, li])
				else:
					var reach: bool = false
					for c: Vector2i in layout.room_cells(li):
						if layout.room_at(li, c) == ch and seen.has(node_key(li, c)):
							reach = true
							break
					if not reach:
						_e("trigger '%s' room '%s' (level %d) can never be entered" % [tid, ch, li])
			"opening":
				var op: Dictionary = layout.opening(str(tg["opening"]))
				if op.is_empty():
					_e("trigger '%s' opening '%s' not found" % [tid, tg["opening"]])
				elif str(op["type"]) in ["open", "breach", "half"] or str(op["state"]) in ["open", "broken", "missing"]:
					_w("trigger '%s' opening '%s' is already open, so it never fires" % [tid, op["id"]])
			"pickup":
				var found: bool = false
				for pk: Dictionary in layout.pickups:
					if str(pk["pid"]) == str(tg["pickup"]):
						found = true
				if not found:
					_e("trigger '%s' pickup '%s' not found" % [tid, tg["pickup"]])
			"container":
				var prop: Dictionary = {}
				for p: Dictionary in layout.props:
					if str(p.get("id", "")) == str(tg["prop"]):
						prop = p
				if prop.is_empty():
					_e("trigger '%s' prop '%s' not found (give the container prop an \"id\")" % [tid, tg["prop"]])
				elif not _is_container(prop):
					_e("trigger '%s' prop '%s' is not a container" % [tid, tg["prop"]])
			"trap":
				if layout.trap(str(tg["trap"])).is_empty():
					_e("trigger '%s' trap '%s' not found" % [tid, tg["trap"]])
	for g3: String in group_sleepers:
		if not group_triggers.has(g3):
			_w("sleeper group '%s' has no trigger: only gunfire, alarms or a blow will ever wake it" % g3)
	var lr_level: int = int(layout.loot_room.get("level", 0))
	var lr_char: String = str(layout.loot_room.get("room", ""))
	for sl2: Dictionary in layout.sleepers:
		if bool(sl2["guardian"]) and (layout.loot_room.is_empty() or int(sl2["level"]) != lr_level or layout.room_at(lr_level, sl2["cell"]) != lr_char):
			_w("guardian '%s' is not in the loot room" % sl2["sid"])


## ADR-0022: seated and lying sleepers land on a seat or bed in reach (SleeperAnchors: a warning
## for each one left on the floor without "anchor": "floor", an error for a pinned anchor that
## names no such prop), and authored window cues are valid (RouteCues).
func _check_dungeon_life() -> void:
	for res: Dictionary in [SleeperAnchors.check(layout), RouteCues.check(layout)]:
		for e: String in res["errors"]:
			_e(e)
		for w: String in res["warnings"]:
			_w(w)


## Lock kinds sit on doors that are locked; and where each padlock hangs (the side the door is
## approached from: reachable from outside without passing through it).
func _check_locks(keys: Dictionary) -> void:
	for op: Dictionary in layout.openings:
		var lock: String = str(op.get("lock", ""))
		if lock == "":
			continue
		var st: String = str(op["state"])
		if not str(op["type"]).begins_with("door"):
			_e("opening '%s' has a lock but is not a door" % op["id"])
			continue
		if bool(op.get("lock_authored", false)):
			if not st in ["locked", "locked_inside"]:
				_w("opening '%s' lock '%s' on a door that is not locked (no cue is shown)" % [op["id"], lock])
			elif lock == "bolt" and st == "locked":
				_w("opening '%s': a bolt only opens from inside; use locked_inside or a padlock" % op["id"])
		if st == "locked":
			lock_sides[str(op["id"])] = _approach_side(op, keys)


func _approach_side(op: Dictionary, keys: Dictionary) -> float:
	var wall: Dictionary = layout.walls.get(PoiLayout.edge_key(op["level"], op["axis"], op["edge"]), {})
	if wall.is_empty():
		return 1.0
	var e: Vector2i = op["edge"]
	var a_cell: Vector2i = e
	var b_cell: Vector2i = e - (Vector2i(0, 1) if op["axis"] == "h" else Vector2i(1, 0))
	_blocked_op = str(op["id"])
	var k: Dictionary = keys.duplicate()
	var seen: Dictionary = _reach_all(k)
	_blocked_op = ""
	var li: int = int(op["level"])
	var a_in: bool = seen.has(node_key(li, a_cell)) or (not layout.is_room(str(wall["a"])) and li == 0)
	var b_in: bool = seen.has(node_key(li, b_cell)) or (not layout.is_room(str(wall["b"])) and li == 0)
	if a_in and not b_in:
		return 1.0
	if b_in and not a_in:
		return -1.0
	if a_in and b_in:
		var da: int = _reconstruct(seen, node_key(li, a_cell)).size() if seen.has(node_key(li, a_cell)) else 0
		var db: int = _reconstruct(seen, node_key(li, b_cell)).size() if seen.has(node_key(li, b_cell)) else 0
		return 1.0 if da <= db else -1.0
	# Neither side reachable without it: the outside face, else the side it was authored from.
	if not layout.is_room(str(wall["a"])):
		return 1.0
	if not layout.is_room(str(wall["b"])):
		return -1.0
	return 1.0 if int(op["side"]) in [0, 3] else -1.0


func _is_container(p: Dictionary) -> bool:
	if p.has("container"):
		return true
	var pd: PropDef = ContentDB.instance.get_def(&"prop", StringName(str(p.get("prop", "")))) as PropDef
	return pd != null and pd.container != ""


func _prop_cells() -> Dictionary:
	var out: Dictionary = {}
	for p: Dictionary in layout.props:
		var pd: PropDef = ContentDB.instance.get_def(&"prop", StringName(str(p.get("prop", "")))) as PropDef
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
	var gen: Dictionary = validate_generated()
	errors.append_array(gen["errors"])
	warnings.append_array(gen["warnings"])
	return {"errors": errors, "warnings": warnings, "summary": "%d POIs, %d frameworks, %d generated buildings checked" % [
		n, Content.all(&"framework").size(), int(gen["count"])]}


## World seeds the framework lots are resolved and generated with in `make validate`.
const LOT_SEEDS: Array[int] = [4471, 1, 90210]
## Buildings generated per template in `make validate` (the unit tests run 50).
const GEN_SEEDS: int = 6


## ADR-0030: buildings from every template (GEN_SEEDS seeds each) and from every framework lot
## without a pick (LOT_SEEDS world seeds) generate and validate with no errors and no warnings;
## every such lot resolves to something unless it is reserved.
static func validate_generated() -> Dictionary:
	var errors: PackedStringArray = []
	var warnings: PackedStringArray = []
	var count: int = 0
	for t: TemplateDef in Content.all(&"building_template"):
		for i: int in GEN_SEEDS:
			var seed: int = Ids.hash64("validate:%s:%d" % [t.id, i])
			var pd: PoiDef = Generator.generate(t, seed)
			count += 1
			_collect(pd, "template %s seed %d" % [t.id, i], errors, warnings)
	for fw: FrameworkDef in Content.all(&"framework"):
		for ws: int in LOT_SEEDS:
			for res: Dictionary in Lots.resolve(fw, String(fw.id), ws):
				var l: Dictionary = res["lot"]
				match str(res["kind"]):
					"empty":
						if ws == LOT_SEEDS[0]:
							warnings.append("%s: lot '%s' has no pick and nothing in the pool fits it (zoning %s, %s)" % [
								fw.id, l.get("id"), l.get("zoning", []), res["size"]])
					"generated":
						count += 1
						var gd: PoiDef = Lots.def_for(res)
						_collect(gd, "%s lot %s world seed %d" % [fw.id, l.get("id"), ws], errors, warnings)
						if gd != null and (gd.footprint.x > (res["size"] as Vector2i).x or gd.footprint.y > (res["size"] as Vector2i).y):
							errors.append("%s: lot '%s' generated %s with footprint %s, larger than the lot %s" % [fw.id, l.get("id"), gd.id, gd.footprint, res["size"]])
	return {"errors": errors, "warnings": warnings, "count": count}


static func _collect(pd: PoiDef, what: String, errors: PackedStringArray, warnings: PackedStringArray) -> void:
	if pd == null:
		errors.append("generated %s: the generator made nothing" % what)
		return
	var v: PoiValidator = validate(pd)
	for e: String in v.errors:
		errors.append("generated %s: %s" % [what, e])
	for w: String in v.warnings:
		warnings.append("generated %s: %s" % [what, w])
