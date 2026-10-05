class_name PoiDressing
extends RefCounted
## Per-run dressing of a building (ADR-0030): what makes one house look and play differently from
## run to run while its plan, its route and its stable piece ids stay put.
##
## Two layers, both resolved into a plain PoiDef before PoiLayout compiles it, so the validator, the
## seat plan, the route cues and the builder all see the same building:
##  * **Alternatives** (authored, docs/POI_AUTHORING.md "Alternatives"): the def's "alternatives"
##    list holds groups, each with weighted options. An option may re-dress rooms (name, purpose,
##    finishes), change door and window states (locked, barricaded, broken open) and restyle the
##    building; list entries (props, sleepers, traps, triggers, pickups, notes, lights, decals,
##    openings) tagged "alt": "group:option" (or a list of them) exist only when that option is
##    picked. The first option, or the one marked "default", is the authored building: a content
##    def compiles as its defaults, which is exactly the building as it was before it had any.
##  * **Wear** (procedural, per run only): furniture without an authored variant may be broken or
##    missing (never containers, seats and beds, lit lights, anything with an id or something
##    standing on it), lights and lit props burn or have gone out, and the builder adds decals
##    (run_decals) and reseeds its scatter and wall damage from the dressing seed.
##
## The dressing seed follows the world seed and the placement id (MODE_PER_RUN), so the same seed
## builds the same building and a new run a different-looking one. Saves from before ADR-0030
## carry MODE_LEGACY (WorldState.poi_dressing): their buildings keep the authored defaults and the
## old instance-id scatter. Picks are pinned in the POI's saved state the first time it is built
## (PoiManager), so a run keeps its rooms even if content gains options later.
## Pure functions of their inputs; prop defs come from ContentDB.instance (safe off the main thread
## and before autoloads exist).

const MODE_LEGACY: int = 1
const MODE_PER_RUN: int = 2
## Layout lists whose entries may carry "alt".
const LISTS: PackedStringArray = ["props", "sleepers", "traps", "triggers", "pickups", "notes", "lights", "decals", "openings"]
const GROUP_KEYS: PackedStringArray = ["id", "label", "options"]
const OPTION_KEYS: PackedStringArray = ["id", "label", "weight", "default", "rooms", "openings", "style"]
## What an option may change in a room (never its plan, height or roof: those shape walls, cellars
## and the terrain cut, which must not move between runs).
const ROOM_PATCH_KEYS: PackedStringArray = ["level", "room", "name", "type", "wall", "floor", "ceiling", "open_to"]
## What an option may change on an opening named by id (never its type, place or width).
const OPENING_PATCH_KEYS: PackedStringArray = ["id", "state", "key", "lock", "barricade", "barricade_on", "cue", "model", "hp"]
const STYLE_PATCH_KEYS: PackedStringArray = ["exterior", "interior", "floor", "ceiling", "decay", "damaged_walls", "prop_condition",
	"scatter", "lights_on"]
## Chance a light (or lit prop) still burns in a per-run dressing, unless the style says otherwise
## or the light is marked "keep": true.
const LIGHTS_ON: float = 0.7
## Decals the per-run pass draws from: wall stains rise with decay, marks and blood are the story.
const WALL_DECALS: Dictionary = {"grime_streaks": 3.0, "water_stain": 3.0, "mold_patch": 2.0, "crack_wall": 2.0, "blood_drip": 0.6,
	"survivor_marks_a": 0.8, "survivor_marks_b": 0.8, "survivor_marks_c": 0.8, "blood_splatter_a": 0.7, "blood_handprint": 0.7,
	"bullet_holes": 0.6}
const FLOOR_DECALS: Dictionary = {"footprints_mud": 2.0, "blood_pool": 1.0, "blood_trail": 1.0, "blood_splatter_b": 0.8,
	"blood_splatter_c": 0.8, "scorch": 0.4, "water_stain": 1.0}


## The dressing seed of one placed building: the world seed and its placement id (per run), or the
## instance id alone (legacy saves: the builder's old scatter seed).
static func dressing_seed(world_seed: int, instance_id: StringName, mode: int) -> int:
	if mode == MODE_PER_RUN:
		return Ids.hash64("dress:%d:%s" % [world_seed, instance_id])
	return Ids.hash64("poi:" + String(instance_id))


static func has_alternatives(def: PoiDef) -> bool:
	return not groups(def).is_empty()


## The def's alternative groups (raw dictionaries, in authored order).
static func groups(def: PoiDef) -> Array:
	var out: Array = []
	var raw: Variant = def.layout.get("alternatives", [])
	if raw is Array:
		for g: Variant in raw:
			if g is Dictionary:
				out.append(g)
	return out


static func options(g: Dictionary) -> Array:
	var out: Array = []
	var raw: Variant = g.get("options", [])
	if raw is Array:
		for o: Variant in raw:
			if o is Dictionary:
				out.append(o)
	return out


static func option_ids(g: Dictionary) -> PackedStringArray:
	var out: PackedStringArray = []
	for o: Dictionary in options(g):
		out.append(str(o.get("id", "")))
	return out


## The authored option of a group: the one marked "default", else the first.
static func default_option(g: Dictionary) -> String:
	var opts: Array = options(g)
	for o: Dictionary in opts:
		if bool(o.get("default", false)):
			return str(o.get("id", ""))
	return str((opts[0] as Dictionary).get("id", "")) if not opts.is_empty() else ""


static func default_picks(def: PoiDef) -> Dictionary:
	var out: Dictionary = {}
	for g: Dictionary in groups(def):
		out[str(g.get("id", ""))] = default_option(g)
	return out


## Weighted picks for a dressing seed. Each group draws from its own stream, so adding a group (or an
## option to another group) leaves the other groups' picks alone.
static func roll(def: PoiDef, seed: int) -> Dictionary:
	var picks: Dictionary = {}
	for g: Dictionary in groups(def):
		var gid: String = str(g.get("id", ""))
		var opts: Array = options(g)
		if opts.is_empty():
			continue
		var total: float = 0.0
		for o: Dictionary in opts:
			total += maxf(0.0, float(o.get("weight", 1.0)))
		if total <= 0.0:
			picks[gid] = default_option(g)
			continue
		var rng := RandomNumberGenerator.new()
		rng.seed = Ids.derive_seed(seed, "alt:" + gid)
		var x: float = rng.randf() * total
		var pick: String = str((opts.back() as Dictionary).get("id", ""))
		for o2: Dictionary in opts:
			x -= maxf(0.0, float(o2.get("weight", 1.0)))
			if x < 0.0:
				pick = str(o2.get("id", ""))
				break
		picks[gid] = pick
	return picks


## Every combination of picks (group -> option), or `limit` of them: the defaults first, then each
## single change from the defaults, then full combinations (all of them when they fit, else a
## deterministic sample). What the validator walks (ADR-0030).
static func combinations(def: PoiDef, limit: int = 24) -> Array[Dictionary]:
	var gs: Array = groups(def)
	var base: Dictionary = default_picks(def)
	var out: Array[Dictionary] = [base]
	var seen: Dictionary = {_combo_key(base): true}
	for g: Dictionary in gs:
		var gid: String = str(g.get("id", ""))
		for oid: String in option_ids(g):
			if oid == str(base.get(gid, "")):
				continue
			var p: Dictionary = base.duplicate()
			p[gid] = oid
			seen[_combo_key(p)] = true
			out.append(p)
	var total: int = 1
	for g2: Dictionary in gs:
		total *= maxi(1, options(g2).size())
	if total <= limit:
		for i: int in total:
			var p2: Dictionary = {}
			var k: int = i
			for g3: Dictionary in gs:
				var ids: PackedStringArray = option_ids(g3)
				p2[str(g3.get("id", ""))] = ids[k % ids.size()]
				k /= ids.size()
			if not seen.has(_combo_key(p2)):
				seen[_combo_key(p2)] = true
				out.append(p2)
	else:
		var rng := RandomNumberGenerator.new()
		rng.seed = Ids.hash64("alt_sample:" + String(def.id))
		var tries: int = 0
		var extra: int = 0
		while extra < limit and tries < limit * 8:
			tries += 1
			var p3: Dictionary = {}
			for g4: Dictionary in gs:
				var ids2: PackedStringArray = option_ids(g4)
				p3[str(g4.get("id", ""))] = ids2[rng.randi() % ids2.size()]
			if seen.has(_combo_key(p3)):
				continue
			seen[_combo_key(p3)] = true
			out.append(p3)
			extra += 1
	return out


static func _combo_key(p: Dictionary) -> String:
	var keys: Array = p.keys()
	keys.sort()
	var parts: PackedStringArray = []
	for k: Variant in keys:
		parts.append("%s=%s" % [k, p[k]])
	return ",".join(parts)


## Human-readable picks ("bedroom=nursery, front=boarded") for messages and plans.
static func describe(picks: Dictionary) -> String:
	return _combo_key(picks).replace(",", ", ")


## Structural problems of the alternatives block (the validator reports them as errors).
static func check(def: PoiDef) -> PackedStringArray:
	var errs: PackedStringArray = []
	var raw: Variant = def.layout.get("alternatives", [])
	if not raw is Array:
		return PackedStringArray(["alternatives must be a list of groups"])
	var lay: Dictionary = def.layout
	var known: Dictionary = {}
	var gids: Dictionary = {}
	for g: Variant in raw:
		if not g is Dictionary:
			errs.append("alternatives entries must be objects")
			continue
		var gd: Dictionary = g
		var gid: String = str(gd.get("id", ""))
		if not _valid_id(gid):
			errs.append("alternative group id '%s' must be lower_snake_case" % gid)
		elif gids.has(gid):
			errs.append("duplicate alternative group '%s'" % gid)
		gids[gid] = true
		for k: Variant in gd.keys():
			if not str(k).begins_with("_") and not GROUP_KEYS.has(str(k)):
				errs.append("alternative group '%s' has unknown key '%s' (%s)" % [gid, k, ", ".join(GROUP_KEYS)])
		var opts: Array = options(gd)
		if opts.size() < 2:
			errs.append("alternative group '%s' needs at least two options" % gid)
		var oids: Dictionary = {}
		var defaults: int = 0
		var weight: float = 0.0
		for o: Dictionary in opts:
			var oid: String = str(o.get("id", ""))
			if not _valid_id(oid):
				errs.append("alternative '%s' option id '%s' must be lower_snake_case" % [gid, oid])
			elif oids.has(oid):
				errs.append("alternative '%s' has two options '%s'" % [gid, oid])
			oids[oid] = true
			known["%s:%s" % [gid, oid]] = true
			defaults += 1 if bool(o.get("default", false)) else 0
			weight += maxf(0.0, float(o.get("weight", 1.0)))
			if float(o.get("weight", 1.0)) < 0.0:
				errs.append("alternative '%s:%s' weight must be >= 0" % [gid, oid])
			for k2: Variant in o.keys():
				if not str(k2).begins_with("_") and not OPTION_KEYS.has(str(k2)):
					errs.append("alternative '%s:%s' has unknown key '%s' (%s)" % [gid, oid, k2, ", ".join(OPTION_KEYS)])
			errs.append_array(_check_option(lay, gid, oid, o))
		if defaults > 1:
			errs.append("alternative group '%s' marks %d options default" % [gid, defaults])
		if not opts.is_empty() and weight <= 0.0:
			errs.append("alternative group '%s': every option has weight 0" % gid)
	for key: String in LISTS:
		var list: Variant = lay.get(key, [])
		if not list is Array:
			continue
		for e: Variant in list:
			if e is Dictionary and (e as Dictionary).has("alt"):
				var tags: Array = e["alt"] if e["alt"] is Array else [e["alt"]]
				for t: Variant in tags:
					if not known.has(str(t)):
						errs.append("%s entry %s: alt '%s' names no group:option" % [key, _entry_name(e), t])
	return errs


static func _valid_id(s: String) -> bool:
	if s == "" or s.begins_with("_"):
		return false
	for ch: String in s:
		if not ((ch >= "a" and ch <= "z") or (ch >= "0" and ch <= "9") or ch == "_"):
			return false
	return true


static func _entry_name(e: Dictionary) -> String:
	return "'%s'" % str(e.get("id", e.get("prop", e.get("decal", e.get("note", e.get("item", "?"))))))


static func _check_option(lay: Dictionary, gid: String, oid: String, o: Dictionary) -> PackedStringArray:
	var errs: PackedStringArray = []
	var where: String = "alternative '%s:%s'" % [gid, oid]
	for rp: Variant in o.get("rooms", []):
		if not rp is Dictionary:
			errs.append("%s rooms entries must be objects" % where)
			continue
		var li: int = int((rp as Dictionary).get("level", 0))
		var ch: String = str((rp as Dictionary).get("room", ""))
		var rooms: Dictionary = _level_rooms(lay, li)
		if not rooms.has(ch):
			errs.append("%s: room '%s' does not exist on level %d" % [where, ch, li])
		for k: Variant in (rp as Dictionary).keys():
			if not str(k).begins_with("_") and not ROOM_PATCH_KEYS.has(str(k)):
				errs.append("%s: a room may change only %s, not '%s'" % [where, ", ".join(ROOM_PATCH_KEYS.slice(2)), k])
	var op_ids: Dictionary = {}
	for op: Variant in lay.get("openings", []):
		if op is Dictionary:
			op_ids[str((op as Dictionary).get("id", ""))] = true
	for opp: Variant in o.get("openings", []):
		if not opp is Dictionary:
			errs.append("%s openings entries must be objects" % where)
			continue
		var opid: String = str((opp as Dictionary).get("id", ""))
		if not op_ids.has(opid):
			errs.append("%s: opening '%s' not found" % [where, opid])
		for k2: Variant in (opp as Dictionary).keys():
			if not str(k2).begins_with("_") and not OPENING_PATCH_KEYS.has(str(k2)):
				errs.append("%s: an opening may change only %s, not '%s'" % [where, ", ".join(OPENING_PATCH_KEYS.slice(1)), k2])
	var st: Variant = o.get("style", {})
	if not st is Dictionary:
		errs.append("%s style must be an object" % where)
	else:
		for k3: Variant in (st as Dictionary).keys():
			if not str(k3).begins_with("_") and not STYLE_PATCH_KEYS.has(str(k3)):
				errs.append("%s: style may change only %s, not '%s'" % [where, ", ".join(STYLE_PATCH_KEYS), k3])
	return errs


static func _level_rooms(lay: Dictionary, li: int) -> Dictionary:
	for lv: Variant in lay.get("levels", []):
		if lv is Dictionary and int((lv as Dictionary).get("level", 0)) == li:
			return (lv as Dictionary).get("rooms", {})
	return {}


## The def as built for these picks (missing groups take their default) and dressing
## ({"mode": MODE_*, "seed": int}; MODE_PER_RUN adds the wear). A new PoiDef with no
## "alternatives" and no "alt" tags left; `dressing` records what was chosen.
static func resolve(def: PoiDef, picks: Dictionary = {}, dress: Dictionary = {}) -> PoiDef:
	var lay: Dictionary = def.layout.duplicate(true)
	var alts: Array = groups(def)
	lay.erase("alternatives")
	var chosen: Dictionary = {}
	var final_picks: Dictionary = {}
	var opts: Array = []
	for g: Dictionary in alts:
		var gid: String = str(g.get("id", ""))
		var pick: String = str(picks.get(gid, default_option(g)))
		if not option_ids(g).has(pick):
			pick = default_option(g)
		final_picks[gid] = pick
		chosen["%s:%s" % [gid, pick]] = true
		for o: Dictionary in options(g):
			if str(o.get("id", "")) == pick:
				opts.append(o)
	for key: String in LISTS:
		if not lay.get(key, null) is Array:
			continue
		var kept: Array = []
		for e: Variant in lay[key]:
			if e is Dictionary and (e as Dictionary).has("alt"):
				if not _tagged(e["alt"], chosen):
					continue
				var copy: Dictionary = (e as Dictionary).duplicate(true)
				copy.erase("alt")
				kept.append(copy)
			else:
				kept.append(e)
		lay[key] = kept
	for o2: Dictionary in opts:
		_apply_option(lay, o2)
	var mode: int = int(dress.get("mode", 0))
	var seed: int = int(dress.get("seed", 0))
	if mode == MODE_PER_RUN:
		_wear(lay, seed, def.tier)
	var out: PoiDef = copy_def(def, lay)
	out.dressing = {"mode": mode, "seed": seed, "picks": final_picks}
	return out


static func _tagged(v: Variant, chosen: Dictionary) -> bool:
	var tags: Array = v if v is Array else [v]
	for t: Variant in tags:
		if chosen.has(str(t)):
			return true
	return false


static func _apply_option(lay: Dictionary, o: Dictionary) -> void:
	for rp: Variant in o.get("rooms", []):
		if not rp is Dictionary:
			continue
		var rooms: Dictionary = _level_rooms(lay, int((rp as Dictionary).get("level", 0)))
		var ch: String = str((rp as Dictionary).get("room", ""))
		if not rooms.has(ch) or not rooms[ch] is Dictionary:
			continue
		for k: Variant in (rp as Dictionary).keys():
			if str(k) in ["level", "room"] or str(k).begins_with("_"):
				continue
			(rooms[ch] as Dictionary)[k] = rp[k]
	for opp: Variant in o.get("openings", []):
		if not opp is Dictionary:
			continue
		for op: Variant in lay.get("openings", []):
			if op is Dictionary and str((op as Dictionary).get("id", "")) == str((opp as Dictionary).get("id", "")):
				for k2: Variant in (opp as Dictionary).keys():
					if str(k2) != "id" and not str(k2).begins_with("_"):
						(op as Dictionary)[k2] = opp[k2]
	var st: Variant = o.get("style", {})
	if st is Dictionary and not (st as Dictionary).is_empty():
		var style: Dictionary = lay.get("style", {})
		for k3: Variant in (st as Dictionary).keys():
			if not str(k3).begins_with("_"):
				style[k3] = st[k3]
		lay["style"] = style


## A copy of `def` with another layout (every parsed field carried over).
static func copy_def(def: PoiDef, lay: Dictionary) -> PoiDef:
	var d := PoiDef.new()
	d.id = def.id
	d.kind = def.kind
	d.display_name = def.display_name
	d.description = def.description
	d.tags = def.tags
	d.source = def.source
	d.tier = def.tier
	d.zoning = def.zoning
	d.footprint = def.footprint
	d.story = def.story
	d.author = def.author
	d.scene = def.scene
	d.layout = lay
	d.budget = def.budget
	d.population = def.population
	d.template = def.template
	d.gen_seed = def.gen_seed
	return d


# --- Wear ------------------------------------------------------------------------------------------

## Per-run wear of the furniture and the lights (MODE_PER_RUN). Furniture without an authored
## variant may be broken (decay x 0.3) or missing (decay x 0.12, household furniture only); lights
## and lit props keep burning with style.lights_on (LIGHTS_ON), a lit prop and an authored light
## within 0.6 m of it sharing one draw. Never touched: containers, anything with an id, seats and
## beds (sleepers land on them), lit props' bodies, wall-mounted and stacked props and what they
## stand on, route_ok debris and anything outside the rooms.
static func _wear(lay: Dictionary, seed: int, tier: int) -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = Ids.derive_seed(seed, "wear")
	var style: Dictionary = lay.get("style", {})
	var decay: float = clampf(float(style.get("decay", 0.25 + 0.1 * tier)), 0.0, 1.0)
	var broken_p: float = clampf(0.05 + decay * 0.3, 0.05, 0.3)
	var missing_p: float = clampf(decay * 0.12, 0.02, 0.1)
	var props: Array = lay.get("props", [])
	var stacked: Array = []
	for p: Variant in props:
		if p is Dictionary and float((p as Dictionary).get("y", 0.0)) > 0.02:
			stacked.append([int((p as Dictionary).get("level", 0)), _pos(p)])
	var db: Node = ContentDB.instance
	var kept: Array = []
	for p2: Variant in props:
		if not p2 is Dictionary:
			kept.append(p2)
			continue
		var pd: PropDef = db.call(&"get_def", &"prop", StringName(str((p2 as Dictionary).get("prop", "")))) as PropDef if db != null else null
		if pd == null or not _wearable(p2, pd, lay, stacked):
			kept.append(p2)
			continue
		var r: float = rng.randf()
		if r < missing_p and _household(pd):
			continue
		if r < missing_p + broken_p and pd.variants.has("destroyed"):
			var worn: Dictionary = (p2 as Dictionary).duplicate()
			worn["variant"] = "destroyed"
			kept.append(worn)
		else:
			kept.append(p2)
	lay["props"] = kept
	# Lights: a lit prop and the light hung on it go out together.
	var on_p: float = clampf(float(style.get("lights_on", LIGHTS_ON)), 0.0, 1.0)
	var lit_at: Array = []
	for p3: Variant in lay["props"]:
		if p3 is Dictionary and bool((p3 as Dictionary).get("lit", false)) and not bool((p3 as Dictionary).get("keep", false)):
			var on: bool = rng.randf() < on_p
			lit_at.append([int((p3 as Dictionary).get("level", 0)), _pos(p3), on])
			if not on:
				(p3 as Dictionary)["lit"] = false
	var lights: Array = []
	for l: Variant in lay.get("lights", []):
		if not l is Dictionary or bool((l as Dictionary).get("keep", false)):
			lights.append(l)
			continue
		var lp: Vector2 = _pos(l)
		var li: int = int((l as Dictionary).get("level", 0))
		var shared: int = -1
		for i: int in lit_at.size():
			if int(lit_at[i][0]) == li and (lit_at[i][1] as Vector2).distance_to(lp) < 0.6:
				shared = i
				break
		var burns: bool = bool(lit_at[shared][2]) if shared >= 0 else rng.randf() < on_p
		if burns:
			lights.append(l)
	if lay.has("lights"):
		lay["lights"] = lights


static func _pos(e: Dictionary) -> Vector2:
	if e.has("pos"):
		var a: Array = e["pos"]
		return Vector2(float(a[0]), float(a[1]))
	var at: Array = e.get("at", [0, 0])
	var off: Array = e.get("offset", [0, 0])
	return Vector2(floor(float(at[0])) + 0.5 + float(off[0]), floor(float(at[1])) + 0.5 + float(off[1]))


static func _household(pd: PropDef) -> bool:
	for t: String in pd.tags:
		if t.begins_with("family_"):
			return true
	return false


static func _wearable(p: Dictionary, pd: PropDef, lay: Dictionary, stacked: Array) -> bool:
	for k: String in ["variant", "id", "container", "y", "anchor", "key", "route_ok"]:
		if p.has(k):
			return false
	if bool(p.get("lit", false)) or not pd.has_tag("breakable") or pd.container != &"" or not pd.anchors.is_empty() \
			or pd.wall_mounted or pd.has_tag("shell") or pd.has_tag("stairwell") or pd.has_tag("story"):
		return false
	var li: int = int(p.get("level", 0))
	var pos: Vector2 = _pos(p)
	if not _in_room(lay, li, Vector2i(int(floor(pos.x)), int(floor(pos.y)))):
		return false
	var reach: float = maxf(pd.size.x, pd.size.z) * 0.5 + 0.1
	for s: Array in stacked:
		if int(s[0]) == li and (s[1] as Vector2).distance_to(pos) < reach:
			return false
	return true


static func _in_room(lay: Dictionary, li: int, c: Vector2i) -> bool:
	for lv: Variant in lay.get("levels", []):
		if lv is Dictionary and int((lv as Dictionary).get("level", 0)) == li:
			var plan: Array = (lv as Dictionary).get("plan", [])
			if c.y < 0 or c.y >= plan.size():
				return false
			var row: String = str(plan[c.y])
			if c.x < 0 or c.x >= row.length():
				return false
			var ch: String = row[c.x]
			return ch != "." and ch != " " and ch != PoiLayout.VOID
	return false


# --- Decals ----------------------------------------------------------------------------------------

## The per-run decals of a dressed building (MODE_PER_RUN only, else none): grime, water stains,
## mould and cracks on solid wall faces (more with decay), survivors' marks and blood on walls and
## floors. Entries in the authored "decals" format, placed by PoiBuilder like authored ones.
static func run_decals(layout: PoiLayout) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var d: Dictionary = layout.def.dressing
	if int(d.get("mode", 0)) != MODE_PER_RUN:
		return out
	var rng := RandomNumberGenerator.new()
	rng.seed = Ids.derive_seed(int(d.get("seed", 0)), "decals")
	var decay: float = clampf(float(layout.style.get("decay", 0.25 + 0.1 * layout.def.tier)), 0.0, 1.0)
	var walls: Array = []
	var floors: Array = []
	for li: int in layout.level_ids:
		var well: Dictionary = layout.stairwell_cells(li)
		for c: Vector2i in layout.room_cells(li):
			if well.has(c):
				continue
			floors.append([li, c])
			for side: int in 4:
				var e: Array = PoiLayout.side_edge(c, side)
				var w: Dictionary = layout.walls.get(PoiLayout.edge_key(li, e[0], e[1]), {})
				if not w.is_empty() and (w["opening"] as Dictionary).is_empty() and not w.has("covered"):
					walls.append([li, c, side])
	if floors.is_empty():
		return out
	var cells: int = floors.size()
	var n: int = clampi(int(round(float(cells) / 40.0 * (0.6 + decay * 1.6))) + rng.randi_range(0, 2), 1, 10)
	var used: Dictionary = {}
	for i: int in n:
		var on_wall: bool = not walls.is_empty() and rng.randf() < 0.62
		if on_wall:
			var slot: Array = walls[rng.randi() % walls.size()]
			var k: String = "%d:%s:%d" % [slot[0], slot[1], slot[2]]
			if used.has(k):
				continue
			used[k] = true
			var name: String = _weighted(WALL_DECALS, rng, decay)
			var high: bool = name in ["water_stain", "mold_patch", "blood_drip"]
			var sz: float = rng.randf_range(0.7, 1.3)
			out.append({"decal": name, "at": [(slot[1] as Vector2i).x, (slot[1] as Vector2i).y], "level": int(slot[0]),
				"side": PoiLayout.SIDE_NAMES[int(slot[2])], "height": rng.randf_range(1.6, 2.2) if high else rng.randf_range(0.7, 1.5),
				"size": [snappedf(sz, 0.01), snappedf(sz * rng.randf_range(0.7, 1.1), 0.01)], "run": true})
		else:
			var fslot: Array = floors[rng.randi() % floors.size()]
			var fk: String = "%d:%s" % [fslot[0], fslot[1]]
			if used.has(fk):
				continue
			used[fk] = true
			var fname: String = _weighted(FLOOR_DECALS, rng, decay)
			var fs: float = rng.randf_range(0.8, 1.5)
			out.append({"decal": fname, "at": [(fslot[1] as Vector2i).x, (fslot[1] as Vector2i).y], "level": int(fslot[0]),
				"side": "floor", "size": [snappedf(fs, 0.01), snappedf(fs * rng.randf_range(0.6, 1.2), 0.01)],
				"rot": snappedf(rng.randf() * 360.0, 1.0), "run": true})
	return out


## A weighted draw; stains, mould and cracks weigh more the more decayed the building is.
static func _weighted(table: Dictionary, rng: RandomNumberGenerator, decay: float) -> String:
	var total: float = 0.0
	var ws: Array[float] = []
	for k: String in table:
		var w: float = float(table[k])
		if k in ["water_stain", "mold_patch", "crack_wall", "grime_streaks"]:
			w *= 0.4 + decay * 1.6
		ws.append(w)
		total += w
	var x: float = rng.randf() * total
	var i: int = 0
	for k2: String in table:
		x -= ws[i]
		if x < 0.0:
			return k2
		i += 1
	return str(table.keys().back())
