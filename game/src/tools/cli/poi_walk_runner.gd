extends Node
## POI walk logic (loaded by poi_walk.gd once autoloads exist). For each building: build it on a
## bare flat pad, walk it with the real Player body (poi_walk_bot.gd), print one line per building
## and its findings, write <out>/<id>.json, and finish with a table. Options:
##   --poi a,b        buildings by id (also bare ids after `--`): POI ids, gen:<template>:<seed>,
##                    lot:<framework>:<lot>
##   --all            every authored POI
##   --pool           every lot of every framework (authored picks and generated houses)
##   --generated N    N buildings from every template (seeds 1..N)
##   --seed N         the world seed buildings are dressed (and lots resolved) for (default 4471,
##                    a new game's)
##   --out DIR        where the JSON goes (default build/poi_walk)
##   --verbose        print every leg
##   --plan           print each building's plan (levels, openings, stairs, ladders) first
## Exit code = buildings with blocking problems (a leg the body could not finish, or a room the
## layout reaches that the body never stood in).

const Bot := preload("res://src/tools/cli/poi_walk_bot.gd")

var _ids: PackedStringArray = []
var _seed: int = 4471
var _out: String = "res://../build/poi_walk"
var _verbose: bool = false
var _plan: bool = false


func _ready() -> void:
	_run.call_deferred()


func _run() -> void:
	_parse()
	var game: Node = get_node("/root/Game")
	var session: GameSession = GameSession.create_new({"seed": _seed, "game_mode": "survival"})
	game.set(&"session", session)
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(_out))
	var bot: Node = Bot.new()
	bot.name = "Bot"
	bot.set(&"verbose", _verbose)
	add_child(bot)
	var rows: Array[Dictionary] = []
	var failing: int = 0
	var t0: int = Time.get_ticks_msec()
	for id: String in _ids:
		var r: Array = Bot.resolve(id, _seed, session)
		if r.is_empty():
			printerr("[poi_walk] unknown building '%s'" % id)
			failing += 1
			continue
		var pd: PoiDef = r[0]
		print("[poi_walk] %s (%s) ..." % [id, pd.display_name])
		if _plan:
			_print_plan(pd)
		var rep: Dictionary = await bot.call(&"walk", pd, r[1])
		rep["walk_id"] = id
		rep["seed"] = _seed
		_print_findings(rep)
		var f: FileAccess = FileAccess.open(ProjectSettings.globalize_path(_out).path_join(_file_name(id) + ".json"), FileAccess.WRITE)
		if f != null:
			f.store_string(JSON.stringify(_jsonable(rep), "  "))
			f.close()
		rows.append(rep)
		if int(rep["blocking"]) > 0:
			failing += 1
	_table(rows)
	print("[poi_walk] %d building(s), %d with blocking problems, %.1f s" % [rows.size(), failing, (Time.get_ticks_msec() - t0) / 1000.0])
	get_tree().quit(failing)


func _parse() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	var i: int = 0
	var all: bool = false
	var pool: bool = false
	var gen: int = 0
	while i < a.size():
		match a[i]:
			"--poi":
				i += 1
				_ids.append_array(a[i].split(",", false))
			"--all":
				all = true
			"--pool":
				pool = true
			"--generated":
				i += 1
				gen = int(a[i])
			"--seed":
				i += 1
				_seed = int(a[i])
			"--out":
				i += 1
				_out = a[i]
			"--verbose":
				_verbose = true
			"--plan":
				_plan = true
			_:
				_ids.append_array(a[i].split(",", false))
		i += 1
	if all:
		var ids: Array[String] = []
		for d: PoiDef in Content.all(&"poi"):
			ids.append(String(d.id))
		ids.sort()
		_ids.append_array(PackedStringArray(ids))
	if pool:
		_ids.append_array(Bot.pool_ids(_seed))
	if gen > 0:
		var ts: Array[String] = []
		for t: Resource in Content.all(&"building_template"):
			ts.append(str(t.get(&"id")))
		ts.sort()
		for t2: String in ts:
			for s: int in range(1, gen + 1):
				_ids.append("gen:%s:%d" % [t2, s])


## The compiled plan of every level with its openings, stairs, ladders and holes (generated
## buildings have no JSON to read).
func _print_plan(pd: PoiDef) -> void:
	var l: PoiLayout = PoiLayout.compile(pd)
	print("[poi_walk]   origin %s floor_height %.2f porch %s" % [l.origin, l.floor_height, l.style.get("porch", {})])
	for li: int in l.level_ids:
		print("[poi_walk]   level %d:" % li)
		var plan: PackedStringArray = l.levels[li]["plan"]
		for r: int in plan.size():
			print("[poi_walk]   %3d %s" % [r, plan[r]])
	for op: Dictionary in l.openings:
		print("[poi_walk]   opening %s %s %s L%d at %s side %s" % [op["id"], op["type"], op["state"], op["level"], op["cell"], PoiLayout.SIDE_NAMES[int(op["side"])]])
	for s: Dictionary in l.stairs:
		print("[poi_walk]   stairs L%d from %s dir %s landing %s" % [s["level"], s["cell"], PoiLayout.SIDE_NAMES[int(s["dir"])], s["landing"]])
	for ld: Dictionary in l.ladders:
		print("[poi_walk]   ladder L%d at %s side %s landing %s" % [ld["level"], ld["cell"], PoiLayout.SIDE_NAMES[int(ld["side"])], ld.get("landing")])
	for h: Dictionary in l.holes:
		print("[poi_walk]   hole L%d at %s" % [h["level"], h["cell"]])


func _file_name(id: String) -> String:
	return id.replace(":", "_").replace("/", "_")


func _print_findings(rep: Dictionary) -> void:
	var tag: String = "BLOCKED" if int(rep["blocking"]) > 0 else "ok"
	print("[poi_walk] %-7s %s: %d legs, %d blocked, %d assisted, %d ladder climbs, %d unreached, %d sealed, %d corridor props (%.0f s walked)" % [
		tag, rep["walk_id"], (rep["legs"] as Array).size(), (rep["blocked"] as Array).size(), (rep["assisted"] as Array).size(),
		(rep["climbs"] as Array).size(), (rep["unreached"] as Array).size(), (rep["sealed"] as Array).size(),
		(rep["corridor"] as Array).size(), float(rep["frames"]) / 60.0])
	for leg: Dictionary in rep["blocked"]:
		print("[poi_walk]   blocked  %s: %s %s -> %s%s: %s" % [leg.get("category", "?"), leg["kind"], leg["from"], leg["to"],
			(" (" + str(leg["opening"]) + ")") if leg.has("opening") else "", _blk(leg.get("blocker", {})) + (" [no way round the props]" if leg.get("through_props", false) else "") + ((" [" + str(leg["note"]) + "]") if leg.has("note") else "")])
	for leg2: Dictionary in rep["assisted"]:
		print("[poi_walk]   needed   %s on %s %s -> %s%s" % [",".join(PackedStringArray(leg2["needed"])), leg2["kind"], leg2["from"], leg2["to"],
			(" (" + str(leg2["opening"]) + ")") if leg2.has("opening") else ""])
	for c: Dictionary in rep["climbs"]:
		print("[poi_walk]   ladder   %s %s (an interact)%s" % [c["dir"], c["ladder"], "" if bool(c["ok"]) else " FAILED"])
	for r: Dictionary in rep["unreached"]:
		print("[poi_walk]   unreached room '%s' %s level %d" % [r["room"], r["name"], r["level"]])
	for r2: Dictionary in rep["sealed"]:
		print("[poi_walk]   sealed   room '%s' %s level %d (the layout itself has no way in)" % [r2["room"], r2["name"], r2["level"]])
	for p: Dictionary in rep["corridor"]:
		if str(p["what"]) == "doorway":
			print("[poi_walk]   prop     %s%s in doorway '%s' (L%d, cell %s, %.2f m into the clear width)" % [p["prop"],
				(" '" + str(p["id"]) + "'") if str(p["id"]) != "" else " #" + str(p["pkey"]), p["opening"], p["level"], p["cell"], p["overlap_m"]])
		else:
			print("[poi_walk]   prop     %s%s on route cell %s L%d (%.2f m)%s" % [p["prop"],
				(" '" + str(p["id"]) + "'") if str(p["id"]) != "" else " #" + str(p["pkey"]), p["cell"], p["level"], p["overlap_m"],
				" route_ok" if bool(p["route_ok"]) else ""])
	for e: String in rep["validator"]:
		print("[poi_walk]   validator %s" % e)


func _blk(b: Dictionary) -> String:
	if b.is_empty():
		return "?"
	var parts: PackedStringArray = [str(b.get("kind", "?"))]
	for k: String in ["opening", "opening_type", "state", "open", "prop", "id", "pkey", "piece", "edge", "rise_m", "box", "node", "cell", "level"]:
		if b.has(k):
			parts.append("%s=%s" % [k, b[k]])
	return " ".join(parts)


func _table(rows: Array[Dictionary]) -> void:
	print("[poi_walk] %-40s %6s %7s %8s %6s %9s %6s %8s" % ["building", "legs", "blocked", "assisted", "ladder", "unreached", "sealed", "corridor"])
	for r: Dictionary in rows:
		print("[poi_walk] %-40s %6d %7d %8d %6d %9d %6d %8d" % [str(r["walk_id"]).left(40), (r["legs"] as Array).size(), (r["blocked"] as Array).size(),
			(r["assisted"] as Array).size(), (r["climbs"] as Array).size(), (r["unreached"] as Array).size(), (r["sealed"] as Array).size(),
			(r["corridor"] as Array).size()])


## Vector2i / Vector3 / StringName to JSON-friendly values.
func _jsonable(v: Variant) -> Variant:
	if v is Dictionary:
		var d: Dictionary = {}
		for k: Variant in v:
			d[str(k)] = _jsonable(v[k])
		return d
	if v is Array:
		var a: Array = []
		for x: Variant in v:
			a.append(_jsonable(x))
		return a
	if v is Vector2i:
		return [v.x, v.y]
	if v is Vector3:
		return [v.x, v.y, v.z]
	if v is StringName:
		return String(v)
	return v
