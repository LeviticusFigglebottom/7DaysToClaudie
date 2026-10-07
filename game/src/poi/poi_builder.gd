class_name PoiBuilder
extends RefCounted
## Builds a PoiInstance from a compiled PoiLayout: kit walls/floors/posts batched into MultiMeshes
## with per-instance finishes (kit_wall shader), one merged collision shell, doors / windows /
## barricades / ladders / pickups as interactive pieces, stairs, porch, foundation, generated roof,
## authored + scattered props (set dressing), lights and decals, and the dungeon mechanics
## (ADR-0018): lock cues on locked doors (breakable padlocks), and the traps — can chimes, bear
## traps, shotgun trip-wires, creaky floors, weak floors (their own kit floor batches so the slab
## can fall away) and alarms.
## Tall rooms (ADR-0021): their walls stack one kit piece per storey with a storey band between,
## each carrying a height code so the kit_wall shader measures wear in the whole room; no floor or
## ceiling inside them; gallery railings where an upper room looks over one; two-storey lancets,
## tall windows and tall doors; lights and ceiling fixtures under the real ceiling; one interior
## reflection probe per rectangle of rooms of one height; and the roof plan of RoofPlanner.

## New ADR-0030 scripts by path, so this compiles before the editor registers their class names.
const Dressing := preload("res://src/poi/poi_dressing.gd")

const WALL_T: float = 0.16

var layout: PoiLayout
var root: PoiInstance
var shell: StaticBody3D
var _batches: Dictionary = {}
var _rng := RandomNumberGenerator.new()
var _decay: float = 0.4
var _route_cells: Dictionary = {}
var _checked: PoiValidator = null
var _occupied: Dictionary = {}
## Locked door opening id -> +1/-1: the wall side its lock cue faces (PoiValidator.lock_sides).
var _lock_sides: Dictionary = {}
## Barricaded door opening id -> +1/-1: the wall side its boards or furniture pile stand on
## (_barricade_faces).
var _barricade_sides: Dictionary = {}
## Level-0 cells under the porch deck: yard items there stand on the deck, elsewhere on the pad.
var _porch_cells: Dictionary = {}
## Batch tag -> its MultiMeshInstance3D (pieces that change at runtime: weak floors).
var _tagged: Dictionary = {}
## Weak floor trap id -> {"piece": WeakFloor, "shape": CollisionShape3D}.
var _weak: Dictionary = {}
## Draws for pieces added with tall rooms (storey bands, galleries, tall openings): a stream of its
## own, so the sequences of everything else (and the scatter of every older building) stay put.
var _rng2 := RandomNumberGenerator.new()
## The roof plan (RoofPlanner wings), kept for the probes and open-roof checks.
var _wings: Array[RoofPlanner.Wing] = []
## Most interior reflection probes one building gets (each costs a cubemap render at load and a
## slot in the reflection atlas).
const MAX_PROBES: int = 8


## `checked`: the layout's PoiValidator, already run (PoiManager runs it on a worker thread while
## the world loads, ADR-0036: it is nearly all of a building's build time); null runs it here.
## Builds the whole building at once (tools, tests, previews); the game builds in phases (start).
static func build(p_layout: PoiLayout, instance_id: StringName, checked: PoiValidator = null) -> PoiInstance:
	var b: PoiBuilder = start(p_layout, instance_id, checked)
	while not b.step():
		pass
	return b.root


## The build's phases in order (ADR-0038: a building is raised over several frames within the
## streaming budget, so no single frame pays for a whole sawmill). A step() runs one phase, or as
## much of a resumable one as its budget allows (TD-107): those walk their items (walls, rows of
## cells, props, roof stages...) from `_cursor` in the one-shot order and return false until done,
## so a build cut into any number of steps draws the same random numbers in the same order and
## adds the same nodes in the same order as one built at once.
const PHASES: PackedStringArray = ["_begin", "_route", "_walls", "_posts", "_floors", "_galleries",
	"_stairs_and_ladders", "_openings", "_roof_plan", "_exterior", "_roof", "_props", "_scatter", "_lights",
	"_interior_probes", "_pickups", "_decals", "_traps", "_emit_batches", "_wire_weak_floors"]

var _instance_id: StringName = &""
var _phase: int = 0
## The current resumable phase's next item (-1: the phase has not started).
var _cursor: int = -1
## Time.get_ticks_usec() at which the current step's budget runs out (0: no budget).
var _deadline: int = 0
## The current resumable phase's items (wall keys, [level, row] pairs...).
var _work: Array = []
## Phase state carried between steps: walls already placed (openings span several edges), the
## floors' hole and weak-floor cells, stairwells per level, the scatter's clutter by room tag,
## the probe rectangles so far, the roof in progress.
var _walls_done: Dictionary = {}
var _hole_cells: Dictionary = {}
var _weak_cells: Dictionary = {}
var _wells: Dictionary = {}
var _by_room: Dictionary = {}
var _rects: Array = []
var _roof_job: RoofBuilder.Job = null


## A builder for one building; call step() until it returns true, then take `root`.
static func start(p_layout: PoiLayout, instance_id: StringName, checked: PoiValidator = null) -> PoiBuilder:
	var b := PoiBuilder.new()
	b.layout = p_layout
	b._checked = checked
	b._instance_id = instance_id
	return b


## Runs the next phase; true once the building is complete (root holds it). `budget_ms` > 0 lets a
## resumable phase stop once that much time is spent (after at least one item) and go on at the
## next step; 0 runs the whole phase.
func step(budget_ms: float = 0.0) -> bool:
	if _phase < PHASES.size():
		_deadline = Time.get_ticks_usec() + maxi(1, int(budget_ms * 1000.0)) if budget_ms > 0.0 else 0
		var done: Variant = call(PHASES[_phase])
		# Resumable phases return false until their last item is in; the others return nothing.
		if not done is bool or done:
			_phase += 1
			_cursor = -1
			_work = []
	return _phase >= PHASES.size()


## Frees a build given up half way (PoiManager's ring dropped the building): its root, and the
## roof nodes not in it yet.
func discard() -> void:
	if _roof_job != null:
		_roof_job.free_nodes()
		_roof_job = null
	if is_instance_valid(root) and not root.is_inside_tree():
		root.free()


## Whether the current step's budget is spent (a resumable phase then returns false).
func _spent() -> bool:
	return _deadline > 0 and Time.get_ticks_usec() >= _deadline


## Per level, its stairwell cells (asked for every row and cell of it).
func _well(li: int) -> Dictionary:
	if not _wells.has(li):
		_wells[li] = layout.stairwell_cells(li)
	return _wells[li]


## Name of the phase the next step() runs ("" when done): for meters.
func next_phase() -> String:
	return PHASES[_phase].trim_prefix("_") if _phase < PHASES.size() else ""


## The whole build on a builder already set up with `layout` (tests that pre-set builder state).
func _build(instance_id: StringName) -> PoiInstance:
	_instance_id = instance_id
	_phase = 0
	_cursor = -1
	while not step():
		pass
	return root


func _begin() -> void:
	var instance_id: StringName = _instance_id
	root = PoiInstance.new()
	root.name = String(instance_id).replace("/", "_").replace(":", "_")
	root.setup(layout, instance_id)
	# Per-run dressing (ADR-0030): scatter, wall damage and decal turns follow the world seed too.
	# Legacy saves (and bare content defs) keep the instance-id streams, so they look as they did.
	var dress: Dictionary = layout.def.dressing
	if int(dress.get("mode", 0)) == Dressing.MODE_PER_RUN:
		_rng.seed = Ids.derive_seed(int(dress.get("seed", 0)), "build")
		_rng2.seed = Ids.derive_seed(int(dress.get("seed", 0)), "build_tall")
	else:
		_rng.seed = Ids.hash64("poi:" + String(instance_id))
		_rng2.seed = Ids.hash64("poi_tall:" + String(instance_id))
	var style: Dictionary = layout.style
	_decay = float(style.get("decay", 0.25 + 0.1 * layout.def.tier))
	shell = StaticBody3D.new()
	shell.name = "Shell"
	shell.collision_layer = 1
	shell.collision_mask = 0
	shell.set_meta(&"surface", "wood_floor")
	root.add_child(shell)
	root.shell = shell
	_porch_cells = _porch_cell_set()


func _route() -> void:
	_route_cells = _route_corridor()


# --- helpers ---------------------------------------------------------------------------------

## Whether the top of level `li` is roofed (a flat or pitched roof sits over every top level the
## RoofBuilder sees; an open top floor is the exception authors mark with roof "none").
func _roofed(_li: int) -> bool:
	return str((layout.style.get("roof", {}) as Dictionary).get("type", "gable")) != "none"

## Batches a kit piece or model ("@model") instance. Indoor instances go in their own batch,
## drawn with weather_exposure 0 so rain gloss and snow stay outside. A `tag` gives the piece a
## batch of its own (found in _tagged) so it can be hidden or swapped at runtime.
func _add(piece: String, xf: Transform3D, custom: Color = Color(0, 0, 0, 0), indoor: bool = false, tag: String = "") -> void:
	var key: String = piece + ("|in" if indoor else "") + ("#" + tag if tag != "" else "")
	if not _batches.has(key):
		_batches[key] = {"xf": [], "c": []}
	(_batches[key]["xf"] as Array).append(xf)
	(_batches[key]["c"] as Array).append(custom)


## Resumable (see PHASES): one batch an item (a prop's first batch loads its model).
func _emit_batches() -> bool:
	if _cursor < 0:
		_work = _batches.keys()
		_cursor = 0
	while _cursor < _work.size():
		_emit_batch(_work[_cursor])
		_cursor += 1
		if _spent():
			break
	return _cursor >= _work.size()


func _emit_batch(key: String) -> void:
	var tag: String = key.get_slice("#", 1) if key.contains("#") else ""
	var base: String = key.get_slice("#", 0)
	var piece: String = base.trim_suffix("|in")
	var xfs: Array = _batches[key]["xf"]
	var cs: Array = _batches[key]["c"]
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_custom_data = true
	mm.mesh = PoiParts.kit_mesh(piece) if not piece.begins_with("@") else ModelLibrary.mesh(piece.substr(1), "box")
	mm.instance_count = xfs.size()
	for i: int in xfs.size():
		mm.set_instance_transform(i, xfs[i])
		mm.set_instance_custom_data(i, cs[i])
	var mmi := MultiMeshInstance3D.new()
	mmi.name = "MM_" + key.replace("/", "_").replace("@", "").replace("|", "_").replace("#", "_").replace(":", "_")
	mmi.multimesh = mm
	if base.ends_with("|in"):
		mmi.set_instance_shader_parameter(&"weather_exposure", 0.0)
	root.add_child(mmi)
	if tag != "":
		_tagged[tag] = mmi


func _box(size: Vector3, xf: Transform3D, body: CollisionObject3D = null) -> CollisionShape3D:
	var cs := CollisionShape3D.new()
	var b := BoxShape3D.new()
	b.size = size
	cs.shape = b
	cs.transform = xf
	(body if body != null else shell).add_child(cs)
	return cs


func _finish(li: int, ch: String, kind: String) -> int:
	if not layout.is_room(ch):
		return PoiParts.finish_index("wall", str(layout.style.get("exterior", "siding_white")))
	var room: Dictionary = layout.room_def(li, ch)
	match kind:
		"floor":
			return PoiParts.finish_index("floor", str(room.get("floor", layout.style.get("floor", "wood_pine"))))
		"ceiling":
			return PoiParts.finish_index("wall", str(room.get("ceiling", layout.style.get("ceiling", "plaster_white"))))
	return PoiParts.finish_index("wall", str(room.get("wall", layout.style.get("interior", "plaster_white"))))


## Finish of the room a wall side belongs to ([level, char] from PoiLayout.volume_of; [] = outside).
func _finish_r(r: Array, kind: String) -> int:
	if r.is_empty():
		return PoiParts.finish_index("wall", str(layout.style.get("exterior", "siding_white")))
	return _finish(int(r[0]), str(r[1]), kind)


func _seed() -> float:
	return _rng.randf()


## Height code of one side of a kit wall piece (kit_wall.gdshader reads it from INSTANCE_CUSTOM.a,
## ADR-0021): how many storeys above its room's floor the piece stands (0..3) and how many storeys
## that room is tall (1..3), so baseboards, grime near the floor and leaks under the ceiling are
## measured in the whole tall room, not per stacked piece. 0 for ordinary rooms and the outside.
func _side_code(li: int, r: Array, cell: Vector2i) -> int:
	if r.is_empty():
		return 0
	var base: int = int(r[0])
	var top: int = layout.column_top(base, cell)
	return clampi(li - base, 0, 3) + 4 * (clampi(top - base + 1, 1, 3) - 1)


## Both sides' codes of a wall (side A + 16 x side B).
func _wall_code(li: int, w: Dictionary) -> int:
	var cells: Array[Vector2i] = PoiLayout.edge_cells(str(w["axis"]), w["cell"])
	return _side_code(li, w["ra"], cells[0]) + 16 * _side_code(li, w["rb"], cells[1])


## Instance custom data of a wall piece: finishes, decay, a random value (0..1) plus its code.
func _wall_custom(li: int, w: Dictionary, rnd: float) -> Color:
	return Color(_finish_r(w["ra"], "wall"), _finish_r(w["rb"], "wall"), clampf(_decay, 0.0, 1.0), float(_wall_code(li, w)) + clampf(rnd, 0.0, 0.98))


## The building's decay for one kit piece. Stains, peel, grime and mould come from continuous
## world-space masks in kit_wall.gdshader with decay-driven thresholds, so every piece of a
## building gets the same value: per-piece jitter cut those features off at every 1 m seam.
func _decay_v() -> float:
	_rng.randf_range(-0.15, 0.2)  # keep the draw: later _rng sequences (seeds, scatter) must not shift
	return clampf(_decay, 0.0, 1.0)


## Local transform of an edge's wall piece (length `span` edges, starting at edge cell `c`).
func _edge_xf(li: int, axis: String, c: Vector2i, span: int = 1) -> Transform3D:
	var y: float = layout.level_y(li)
	var o: Vector2 = layout.origin
	if axis == "h":
		return Transform3D(Basis.IDENTITY, Vector3(o.x + c.x + span * 0.5, y, o.y + c.y))
	return Transform3D(Basis(Vector3.UP, PI * 0.5), Vector3(o.x + c.x, y, o.y + c.y + span * 0.5))


func _route_corridor() -> Dictionary:
	var out: Dictionary = {}
	var v: PoiValidator = _checked
	if v == null or v.layout != layout:
		v = PoiValidator.new()
		v.layout = layout
		v._run()
	_lock_sides = v.lock_sides
	# Each barricade's face costs a reachability flood (~7 ms apiece): PoiManager's check worker
	# finds them (prepare_check); tools and tests that pass no prepared check find them here.
	_barricade_sides = v.barricade_sides if v == _prepared() else _barricade_faces(v)
	for path: Array in v.paths:
		for node: Variant in path:
			if node is Array:
				out[PoiValidator.node_key(node[0], node[1])] = true
	return out


## Does the builder's pure-data prework on a run validator, off the main thread (PoiManager's check
## worker): the faces of its barricades (a reachability flood each), the roof plan and the interior
## probe boxes, the clutter table and the per-run decals, each up to ~25 ms of a big building.
## Reads only the layout, the validator and ContentDB.instance.
static func prepare_check(v: PoiValidator) -> void:
	var b := PoiBuilder.new()
	b.layout = v.layout
	v.barricade_sides = b._barricade_faces(v)
	b._wings = RoofPlanner.plan(v.layout)
	v.roof_wings = b._wings
	v.probe_boxes = b.probe_boxes()
	v.clutter = clutter_by_room()
	v.run_decals = Dressing.run_decals(v.layout)
	v.prepared = true


## The validator passed in when it carries prepare_check's prework for this layout, else null.
func _prepared() -> PoiValidator:
	return _checked if _checked != null and _checked.prepared and _checked.layout == layout else null


## Which face of its wall each barricaded door's barricade stands on (+1 = the wall's "a" side,
## local +Z; the PoiValidator.lock_sides convention). An authored "barricade_on" (the room char
## it stands in, "." for outside) wins. Otherwise boards go on the face the door is approached
## from (the side reachable without passing through it, as for lock cues): whoever nailed them
## shut the room behind away, so they are seen from the way in, never from inside the sealed
## room. A furniture pile stays where whoever held the room piled it: inside on exterior walls,
## the "a" side on interior ones.
func _barricade_faces(v: PoiValidator) -> Dictionary:
	var out: Dictionary = {}
	var raw: Dictionary = {}
	for o: Variant in layout.def.layout.get("openings", []):
		if o is Dictionary and (o as Dictionary).has("id"):
			raw[str(o["id"])] = o
	for op: Dictionary in layout.openings:
		if str(op["state"]) != "barricaded" or not str(op["type"]).begins_with("door"):
			continue
		var w: Dictionary = layout.walls.get(PoiLayout.edge_key(op["level"], op["axis"], op["edge"]), {})
		if w.is_empty():
			continue
		var boards: bool = str(op.get("barricade", "boards")) == "boards"
		var on: String = str((raw.get(str(op["id"]), {}) as Dictionary).get("barricade_on", ""))
		var face: float = 1.0
		if on != "" and on == str(w["a"]):
			face = 1.0
		elif on != "" and on == str(w["b"]):
			face = -1.0
		elif bool(w["exterior"]):
			var outside_sign: float = 1.0 if not layout.is_room(str(w["a"])) else -1.0
			face = outside_sign if boards else -outside_sign
		elif boards:
			face = v._approach_side(op, v._keys_found)
		out[str(op["id"])] = face
	return out


## Level-0 cells under the porch deck (mirrors _porch).
func _porch_cell_set() -> Dictionary:
	var out: Dictionary = {}
	var porch: Dictionary = layout.style.get("porch", {})
	if porch.is_empty() or layout.level_ids.is_empty():
		return out
	var li0: int = 0 if layout.levels.has(0) else layout.level_ids.front()
	var lv: Dictionary = layout.levels[li0]
	var side: int = PoiLayout.SIDES.get(str(porch.get("side", "S")), 2)
	for i: int in range(int(porch.get("from", 0)), int(porch.get("to", 3)) + 1):
		for k: int in int(porch.get("depth", 2)):
			match side:
				2:
					out[Vector2i(i, int(lv["d"]) + k)] = true
				0:
					out[Vector2i(i, -1 - k)] = true
				1:
					out[Vector2i(int(lv["w"]) + k, i)] = true
				_:
					out[Vector2i(-1 - k, i)] = true
	return out


## Height an item placed on level `li` in `cell` stands at: level-0 items on yard cells off the
## porch deck stand on the pad (y = 0); everything else on its level's floor (floor_height above
## the pad on level 0, so yard props, pickups, bear traps and floor decals used to float).
func _base_y(li: int, cell: Vector2i) -> float:
	if li == 0 and not layout.is_room(layout.room_at(0, cell)) and not _porch_cells.has(cell):
		return 0.0
	return layout.level_y(li)


# --- walls -----------------------------------------------------------------------------------

## Resumable (see PHASES): one wall edge an item.
func _walls() -> bool:
	if _cursor < 0:
		_work = layout.walls.keys()
		_walls_done = {}
		_cursor = 0
	var damaged_p: float = float(layout.style.get("damaged_walls", 0.04 * layout.def.tier))
	while _cursor < _work.size():
		_wall(_work[_cursor], damaged_p)
		_cursor += 1
		if _spent():
			break
	return _cursor >= _work.size()


func _wall(key: String, damaged_p: float) -> void:
	var done: Dictionary = _walls_done
	if done.has(key):
		return
	var w: Dictionary = layout.walls[key]
	var li: int = w["level"]
	var axis: String = w["axis"]
	var c: Vector2i = w["cell"]
	var op: Dictionary = w["opening"]
	if w.has("covered"):
		# The two-storey opening one level down stands here too; a third storey above still
		# needs its band.
		done[key] = true
		_band(li, axis, c, w, _wall_custom(li, w, _rng2.randf()))
		return
	_decay_v()
	var custom: Color = _wall_custom(li, w, _seed())
	# Up through a tall room (or a storey over it), a damaged piece's floor debris would hang in
	# the air: those walls stay whole.
	var tall: bool = str(w["a"]) == PoiLayout.VOID or str(w["b"]) == PoiLayout.VOID
	if op.is_empty():
		var piece: String = "wall_1m"
		if not w["exterior"] and _rng.randf() < damaged_p and not tall:
			piece = "wall_1m_damaged"
		_add(piece, _edge_xf(li, axis, c), custom)
		_wall_collision(li, axis, c, 1, {})
		_band(li, axis, c, w, custom)
		done[key] = true
		return
	# Openings: handled once at their first edge.
	if op["edge"] != c:
		return
	var spec: Dictionary = PoiParts.OPENINGS[op["type"]]
	var span: int = int(spec["len"])
	for k: int in span:
		var ek: Vector2i = c + (Vector2i(k, 0) if axis == "h" else Vector2i(0, k))
		done[PoiLayout.edge_key(li, axis, ek)] = true
		if int(spec.get("storeys", 1)) == 1:
			_band(li, axis, ek, layout.walls.get(PoiLayout.edge_key(li, axis, ek), w), custom)
	if str(spec["model"]) != "":
		_add(str(spec["model"]), _edge_xf(li, axis, c, span), custom)
	_wall_collision(li, axis, c, span, spec)


## The storey band (2.8 .. 3.0 m) between a wall piece and the one stacked on it on the same edge,
## where a side has no floor slab up there to close it: a tall room's void, or the outside. Without
## it the slab's edge showed as a recessed strip across facades and through tall rooms.
func _band(li: int, axis: String, c: Vector2i, w: Dictionary, custom: Color) -> void:
	var up: String = PoiLayout.edge_key(li + 1, axis, c)
	if not layout.walls.has(up):
		return
	var cells: Array[Vector2i] = PoiLayout.edge_cells(axis, c)
	var slab_a: bool = layout.is_room(layout.room_at(li + 1, cells[0])) and not _well(li + 1).has(cells[0])
	var slab_b: bool = layout.is_room(layout.room_at(li + 1, cells[1])) and not _well(li + 1).has(cells[1])
	if slab_a and slab_b:
		return
	_rng2.randf()
	_add("wall_band_1m", _edge_xf(li, axis, c), custom)
	var xf: Transform3D = _edge_xf(li, axis, c)
	_box(Vector3(1.02, 0.2, WALL_T), xf * Transform3D(Basis.IDENTITY, Vector3(0, PoiLayout.WALL_H + 0.1, 0)))


## Collision boxes for one wall piece: solid, or split around its opening (two-storey pieces stand
## 5.8 m).
func _wall_collision(li: int, axis: String, c: Vector2i, span: int, spec: Dictionary) -> void:
	var xf: Transform3D = _edge_xf(li, axis, c, span)
	var length: float = float(span)
	var h: float = PoiParts.piece_height(spec) if not spec.is_empty() else PoiLayout.WALL_H
	if spec.is_empty():
		_box(Vector3(length + 0.02, h, WALL_T), xf * Transform3D(Basis.IDENTITY, Vector3(0, h * 0.5, 0)))
		return
	var ow: float = float(spec["w"])
	var oh: float = float(spec["h"])
	var sill: float = float(spec["sill"])
	if spec["model"] == "":
		return
	if oh <= 0.0:
		# Pony wall.
		_box(Vector3(length, sill, WALL_T), xf * Transform3D(Basis.IDENTITY, Vector3(0, sill * 0.5, 0)))
		return
	var jamb: float = (length - ow) * 0.5
	if jamb > 0.01:
		_box(Vector3(jamb, h, WALL_T), xf * Transform3D(Basis.IDENTITY, Vector3(-length * 0.5 + jamb * 0.5, h * 0.5, 0)))
		_box(Vector3(jamb, h, WALL_T), xf * Transform3D(Basis.IDENTITY, Vector3(length * 0.5 - jamb * 0.5, h * 0.5, 0)))
	var top: float = sill + oh
	if top < h - 0.01:
		_box(Vector3(ow, h - top, WALL_T), xf * Transform3D(Basis.IDENTITY, Vector3(0, top + (h - top) * 0.5, 0)))
	if sill > 0.01:
		_box(Vector3(ow, sill, WALL_T), xf * Transform3D(Basis.IDENTITY, Vector3(0, sill * 0.5, 0)))


## Resumable (see PHASES): one row of wall vertices of one level an item.
func _posts() -> bool:
	if _cursor < 0:
		_work = []
		for li: int in layout.level_ids:
			for r: int in int(layout.levels[li]["d"]) + 1:
				_work.append(Vector2i(li, r))
		_cursor = 0
	while _cursor < _work.size():
		_post_row(_work[_cursor].x, _work[_cursor].y)
		_cursor += 1
		if _spent():
			break
	return _cursor >= _work.size()


func _post_row(li: int, r: int) -> void:
	var lv: Dictionary = layout.levels[li]
	for c: int in int(lv["w"]) + 1:
		var h_l: bool = layout.walls.has(PoiLayout.edge_key(li, "h", Vector2i(c - 1, r)))
		var h_r: bool = layout.walls.has(PoiLayout.edge_key(li, "h", Vector2i(c, r)))
		var v_u: bool = layout.walls.has(PoiLayout.edge_key(li, "v", Vector2i(c, r - 1)))
		var v_d: bool = layout.walls.has(PoiLayout.edge_key(li, "v", Vector2i(c, r)))
		var n: int = int(h_l) + int(h_r) + int(v_u) + int(v_d)
		if n == 0 or (n == 2 and ((h_l and h_r) or (v_u and v_d))):
			continue
		var p := Vector3(layout.origin.x + c, layout.level_y(li), layout.origin.y + r)
		var ext: String = str(layout.style.get("exterior", "siding_white"))
		# A corner that goes on up (a tall room, a storey over this one) is closed through
		# the storey band: the post is stretched to the next storey's floor.
		var up: bool = layout.walls.has(PoiLayout.edge_key(li + 1, "h", Vector2i(c - 1, r))) or layout.walls.has(PoiLayout.edge_key(li + 1, "h", Vector2i(c, r))) \
			or layout.walls.has(PoiLayout.edge_key(li + 1, "v", Vector2i(c, r - 1))) or layout.walls.has(PoiLayout.edge_key(li + 1, "v", Vector2i(c, r)))
		var b := Basis.IDENTITY.scaled(Vector3(1.0, PoiLayout.STOREY / PoiLayout.WALL_H, 1.0)) if up else Basis.IDENTITY
		_add("post_corner", Transform3D(b, p), Color(PoiParts.finish_index("wall", ext), PoiParts.finish_index("wall", ext), _decay_v(), _seed()))


# --- floors, ceilings ----------------------------------------------------------------------

## Resumable (see PHASES): one row of cells of one level an item.
func _floors() -> bool:
	if _cursor < 0:
		_hole_cells = {}
		for h: Dictionary in layout.holes:
			_hole_cells[PoiValidator.node_key(h["level"], h["cell"])] = true
		# Weak floors: a fallen one is just a hole; a standing one gets its own rotten slab batch,
		# its broken twin (hidden) and a collision box it can switch off when it gives way.
		_weak_cells = layout.weak_floor_cells()
		for wk: String in _weak_cells:
			if root.trap_state(_weak_cells[wk]) == "sprung":
				_hole_cells[wk] = true
		_work = []
		for li: int in layout.level_ids:
			for r: int in int(layout.levels[li]["d"]):
				_work.append(Vector2i(li, r))
		_cursor = 0
	while _cursor < _work.size():
		_floor_row(_work[_cursor].x, _work[_cursor].y)
		_cursor += 1
		if _spent():
			break
	return _cursor >= _work.size()


func _floor_row(li: int, r: int) -> void:
	var hole_cells: Dictionary = _hole_cells
	var weak: Dictionary = _weak_cells
	var well: Dictionary = _well(li)
	var y: float = layout.level_y(li)
	var lv: Dictionary = layout.levels[li]
	var run_start: int = -1
	for c: int in int(lv["w"]) + 1:
		var cell := Vector2i(c, r)
		var nk: String = PoiValidator.node_key(li, cell)
		var weak_tid: String = str(weak.get(nk, "")) if not hole_cells.has(nk) else ""
		var ch: String = layout.room_at(li, cell) if c < int(lv["w"]) else "."
		var solid: bool = layout.is_room(ch) and not well.has(cell) and not hole_cells.has(nk) and weak_tid == ""
		if ch == PoiLayout.VOID:
			# A tall room rises through: no floor here; its ceiling closes the top storey
			# (unless it is open to the roof).
			var vol: Array = layout.volume_of(li, cell)
			if not vol.is_empty() and not layout.is_built(li + 1, cell) and not layout.open_roof_at(li, cell):
				var pc := Vector3(layout.origin.x + c + 0.5, y + PoiLayout.STOREY, layout.origin.y + r + 0.5)
				_add("floor_1m", Transform3D(Basis.IDENTITY, pc), Color(0, _finish_r(vol, "ceiling"), clampf(_decay, 0.0, 1.0), _rng2.randf()))
		if layout.is_room(ch) and not well.has(cell):
			var below_v: Array = layout.volume_of(li - 1, cell)
			var custom := Color(_finish(li, ch, "floor"), _finish_r(below_v, "ceiling") if not below_v.is_empty() else _finish(li, ch, "ceiling"), _decay_v(), _seed())
			var p := Vector3(layout.origin.x + c + 0.5, y, layout.origin.y + r + 0.5)
			var indoor: bool = layout.is_built(li + 1, cell) if layout.levels.has(li + 1) else _roofed(li)
			if weak_tid != "":
				_add("floor_1m_rotten", Transform3D(Basis.IDENTITY, p), custom, indoor, "weak:" + weak_tid)
				_add("floor_1m_broken", Transform3D(Basis.IDENTITY, p), custom, indoor, "weakx:" + weak_tid)
				_weak[weak_tid] = {"shape": _box(Vector3(1.0, 0.2, 1.0), Transform3D(Basis.IDENTITY, p - Vector3.UP * 0.1))}
			else:
				_add("floor_1m_broken" if hole_cells.has(nk) else "floor_1m", Transform3D(Basis.IDENTITY, p), custom, indoor)
			# Ceiling where nothing is built above (a tall room's void continues the room; a room
			# open to the roof sees the rafters instead).
			if not layout.is_built(li + 1, cell):
				if not layout.open_roof_at(li, cell):
					_add("floor_1m", Transform3D(Basis.IDENTITY, p + Vector3.UP * PoiLayout.STOREY), Color(0, _finish(li, ch, "ceiling"), _decay_v(), _seed()))
				else:
					_decay_v()
					_seed()
		if solid and run_start < 0:
			run_start = c
		elif not solid and run_start >= 0:
			var n: int = c - run_start
			_box(Vector3(n, 0.2, 1.0), Transform3D(Basis.IDENTITY, Vector3(layout.origin.x + run_start + n * 0.5, y - 0.1, layout.origin.y + r + 0.5)))
			run_start = -1


## Gallery edges (an upper room looking over a tall room): a fascia over the floor slab's edge on
## every one, a railing ("balustrade": turned balusters and a moulded rail; "rail": rough two-rail
## timber) unless a gap is authored ("open") or it is broken out ("breach": a splintered stub), and a
## newel post at every metre of each run. Local +Z of each piece faces the void.
func _galleries() -> void:
	var posts: Dictionary = {}
	for key: String in layout.galleries:
		var g: Dictionary = layout.galleries[key]
		var li: int = int(g["level"])
		var axis: String = str(g["axis"])
		var c: Vector2i = g["cell"]
		var cells: Array[Vector2i] = PoiLayout.edge_cells(axis, c)
		var floor_cell: Vector2i = cells[1] if bool(g["void_a"]) else cells[0]
		if layout.stairwell_cells(li).has(floor_cell):
			continue
		var xf: Transform3D = _edge_xf(li, axis, c)
		if not bool(g["void_a"]):
			xf.basis = xf.basis * Basis(Vector3.UP, PI)
		var style: String = str(g["style"])
		var op: Dictionary = g["opening"]
		var custom := Color(0, 0, clampf(_decay, 0.0, 1.0), _rng2.randf())
		_add("gallery_%s_fascia" % style, xf, custom, true)
		if op.is_empty():
			_add("gallery_%s_1m" % style, xf, custom, true)
			# Waist-high: nobody walks off it (the navmesh ends at it too).
			_box(Vector3(1.0, 1.05, 0.1), xf * Transform3D(Basis.IDENTITY, Vector3(0, 0.525, -0.07)))
		elif str(op["type"]) == "breach":
			_add("gallery_%s_1m_broken" % style, xf, custom, true)
		else:
			continue
		for k: int in 2:
			var v: Vector3 = xf * Vector3(-0.5 + float(k), 0.0, 0.0)
			var vk: String = "%d:%.2f:%.2f" % [li, v.x, v.z]
			if not posts.has(vk):
				posts[vk] = true
				_add("gallery_%s_post" % style, Transform3D(xf.basis, v), custom, true)


func _stairs_and_ladders() -> void:
	var yaws: Array[float] = [0.0, -PI * 0.5, PI, PI * 0.5]
	for s: Dictionary in layout.stairs:
		var li: int = s["level"]
		var dir: int = s["dir"]
		var c0: Vector2i = s["cell"]
		var center: Vector3 = layout.cell_center(li, c0)
		var d3 := Vector3(PoiLayout.DIRS[dir].x, 0, PoiLayout.DIRS[dir].y)
		var edge: Vector3 = center - d3 * 0.5
		var basis := Basis(Vector3.UP, yaws[dir])
		# TD-023: a flight against a wall (or two) stood 8 cm into it. Move it off a wall at its
		# foot and on one side, narrow it between two, and hang the banister on the open side
		# (the banister is centred on its stringer, 0.48 m off the flight's centre line).
		var side_x: Vector3 = basis * Vector3.RIGHT
		var walled: Array[bool] = [_flight_walled(s, Vector2i(roundi(side_x.x), roundi(side_x.z))), _flight_walled(s, -Vector2i(roundi(side_x.x), roundi(side_x.z)))]
		var e_foot: Array = PoiLayout.side_edge(c0, (dir + 2) % 4)
		if layout.walls.has(PoiLayout.edge_key(li, e_foot[0], e_foot[1])):
			edge += d3 * (WALL_T * 0.5)
		var width: float = 1.0
		if walled[0] and walled[1]:
			width = 1.0 - WALL_T
		elif walled[0]:
			edge -= side_x * (WALL_T * 0.5)
		elif walled[1]:
			edge += side_x * (WALL_T * 0.5)
		var stair_basis: Basis = basis.scaled_local(Vector3(width, 1.0, 1.0)) if width < 1.0 else basis
		_add("stairs_straight", Transform3D(stair_basis, edge), Color(0, 0, _decay_v(), _seed()))
		var rail_c := Color(0, 0, _decay_v(), _seed())
		for k: int in 2:
			if not walled[k]:
				_add("stairs_railing", Transform3D(basis, edge + side_x * (0.48 if k == 0 else -0.48)), rail_c)
		_ramp(edge, edge + d3 * 4.0 + Vector3.UP * PoiLayout.STOREY, width)
	for l: Dictionary in layout.ladders:
		var li2: int = l["level"]
		var cell: Vector2i = l["cell"]
		var cc: Vector3 = layout.cell_center(li2, cell)
		var side: int = l["side"]
		var toward := Vector3(PoiLayout.DIRS[side].x, 0, PoiLayout.DIRS[side].y)
		var basis2 := Basis(Vector3.UP, yaws[(side + 2) % 4])
		var lad := PoiPieces.Ladder.new()
		lad.position = cc + toward * 0.38
		lad.basis = basis2
		lad.bottom_local = cc
		lad.top_local = layout.cell_center(li2 + 1, l.get("landing", cell))
		var mi := MeshInstance3D.new()
		mi.mesh = PoiParts.kit_mesh("ladder_3m")
		lad.add_child(mi)
		_box(Vector3(0.6, 3.0, 0.3), Transform3D(Basis.IDENTITY, Vector3(0, 1.5, 0)), lad)
		root.add_child(lad)
		# Up into a tall room's open space there is no floor to cut a hatch in.
		if bool(l["hatch"]) and layout.is_room(layout.room_at(li2 + 1, cell)):
			_add("hatch_1m", Transform3D(Basis.IDENTITY, cc + Vector3.UP * PoiLayout.STOREY), Color(0, 0, _decay_v(), _seed()))


# --- openings: doors, windows, barricades ------------------------------------------------------

func _openings() -> void:
	for op: Dictionary in layout.openings:
		var key: String = PoiLayout.edge_key(op["level"], op["axis"], op["edge"])
		var w: Dictionary = layout.walls.get(key, {})
		if w.is_empty():
			continue
		var spec: Dictionary = PoiParts.OPENINGS[op["type"]]
		var span: int = int(spec["len"])
		var xf: Transform3D = _edge_xf(op["level"], op["axis"], op["edge"], span)
		var st: String = root.piece_state(op["id"], op["state"])
		var exterior: bool = w["exterior"]
		var outside_sign: float = 1.0 if (w["ra"] as Array).is_empty() else -1.0
		var inside_sign: float = 1.0 if op["side"] in [0, 3] else -1.0
		var t: String = op["type"]
		if t.begins_with("door") and st != "missing":
			var leaf: String = str(op.get("model", spec.get("leaf", "door_exterior" if exterior else "door_interior")))
			var ls: Array = spec.get("leaf_size", [0.82, 2.05])
			var leaf_size := Vector2(float(ls[0]), float(ls[1]))
			var hp: float = float(op["hp"]) if float(op["hp"]) > 0.0 else (900.0 if leaf == "door_metal" else (380.0 if exterior else 220.0))
			var oid: String = str(op["id"])
			if span == 1:
				# TD-023: a leaf hinged beside a wall that runs off on its swing side would open into
				# that wall: hang it on the other jamb when that one is clear.
				var hinge_x: float = -0.43
				var flip: float = 0.0
				var swing: Vector3 = xf.basis * Vector3.BACK
				var sw := Vector2i(roundi(swing.x), roundi(swing.z))
				var v0: Vector3 = xf * Vector3(-0.5, 0, 0)
				var v1: Vector3 = xf * Vector3(0.5, 0, 0)
				var lv0 := Vector2i(roundi(v0.x - layout.origin.x), roundi(v0.z - layout.origin.y))
				var lv1 := Vector2i(roundi(v1.x - layout.origin.x), roundi(v1.z - layout.origin.y))
				if _wall_from_vertex(int(op["level"]), lv0, sw) and not _wall_from_vertex(int(op["level"]), lv1, sw):
					hinge_x = 0.43
					flip = PI
				var d1: PoiPieces.Door = _door(oid, xf, Vector3(hinge_x, 0, 0), flip, leaf, st, str(op["key"]), hp, inside_sign, leaf_size)
				d1.opening_id = oid
				_lock_cue(d1, op, inside_sign)
			else:
				var hx: float = float(spec["w"]) * 0.5
				var dl: PoiPieces.Door = _door(oid + "_l", xf, Vector3(-hx, 0, 0), 0.0, leaf, st, str(op["key"]), hp, inside_sign, leaf_size)
				var dr: PoiPieces.Door = _door(oid + "_r", xf, Vector3(hx, 0, 0), PI, leaf, st, str(op["key"]), hp, inside_sign, leaf_size)
				if bool(spec.get("mirror_pair", false)) and not op.has("model"):
					# A leaf dressed on one face (the barn door's battens, braces and strap hinges),
					# turned half round on its pivot, showed its plain back outside: the right leaf's
					# mesh is the left one mirrored instead (through its own plane; the collider is
					# symmetric, and a broken leaf keeps the transform).
					for c: Node in dr.pivot.get_children():
						if c is MeshInstance3D:
							(c as MeshInstance3D).transform = Transform3D(Basis.from_scale(Vector3(1, 1, -1)), Vector3.ZERO)
				dl.opening_id = oid
				dr.opening_id = oid
				dl.partner = dr
				dr.partner = dl
				# One lock on the left leaf, at the meeting stiles.
				_lock_cue(dl, op, inside_sign)
				dr.lock_kind = dl.lock_kind
			if st == "barricaded":
				var boards: bool = str(op.get("barricade", "boards")) == "boards"
				var bar_face: float = float(_barricade_sides.get(oid, outside_sign if boards else -outside_sign))
				var bar: PoiPieces.Breakable = _barricade(oid + "_bar", xf, bar_face, "boards_door" if boards else "barricade_furniture", 260.0)
				if bar != null:
					bar.opening_id = oid
		elif PoiLayout.is_window(t):
			var pane: String = str(spec.get("glass", "window_glass_1m"))
			var glass_state: String = root.piece_state(op["id"] + "_glass", "broken" if st in ["broken", "missing", "open"] else "closed")
			if st != "missing" and st != "open":
				var g: PoiPieces.Breakable = _glass(op["id"] + "_glass", xf, pane, glass_state, float(spec["w"]), float(spec["h"]), float(spec["sill"]))
				g.opening_id = str(op["id"])
			if st == "boarded":
				var bsize := Vector3(float(spec["w"]) + 0.3, minf(float(spec["h"]), 2.4), 0.08)
				var boards: PoiPieces.Breakable = _barricade(op["id"] + "_boards", xf, outside_sign, str(spec.get("boards", "boards_window_1m")), 150.0, float(spec["sill"]), bsize)
				if boards != null:
					boards.opening_id = str(op["id"])


## Whether a wall (or a gallery railing) stands along either side of a stair flight, on the side
## `toward` (a plan direction) of its four cells.
func _flight_walled(s: Dictionary, toward: Vector2i) -> bool:
	var side: int = PoiLayout.DIRS.find(toward)
	if side < 0:
		return false
	for c: Vector2i in s["cells"]:
		var e: Array = PoiLayout.side_edge(c, side)
		var k: String = PoiLayout.edge_key(int(s["level"]), e[0], e[1])
		if layout.walls.has(k) or layout.galleries.has(k):
			return true
	return false


## Whether a wall leaves a plan vertex in a plan direction on a level (TD-023: a door leaf swung open
## against it would stand in it).
func _wall_from_vertex(li: int, v: Vector2i, toward: Vector2i) -> bool:
	var k: String = ""
	if toward == Vector2i(1, 0):
		k = PoiLayout.edge_key(li, "h", v)
	elif toward == Vector2i(-1, 0):
		k = PoiLayout.edge_key(li, "h", v - Vector2i(1, 0))
	elif toward == Vector2i(0, 1):
		k = PoiLayout.edge_key(li, "v", v)
	else:
		k = PoiLayout.edge_key(li, "v", v - Vector2i(0, 1))
	return layout.walls.has(k) or layout.galleries.has(k)


## Lock cue heights on the leaf (m): the hasp and chain above the knob (0.95), a sliding bolt
## higher still, all at the latch edge (leaf x = 0.82, origin of the lock models).
const LOCK_X: float = 0.82
const LOCK_Y: Dictionary = {"padlock": 1.22, "chain": 1.02, "deadbolt": 1.25, "bolt": 1.48}


## Lock cues (TD-034): a padlock and hasp, a chain or a deadbolt on the face a locked door is
## approached from (where its key is used: PoiValidator.lock_sides), a sliding bolt on the inside
## face of a locked_inside one. Padlocks and chains can be broken off (PoiPieces.LockBody). They
## hang on the leaf at its latch edge, so they swing with it once open.
func _lock_cue(d: PoiPieces.Door, op: Dictionary, inside_sign: float) -> void:
	var kind: String = str(op.get("lock", ""))
	var authored: String = str(op["state"])
	if kind == "" or d.pivot == null or not authored in ["locked", "locked_inside"]:
		return
	var face: float = inside_sign if authored == "locked_inside" else float(_lock_sides.get(str(op["id"]), inside_sign))
	# A leaf hung on the other jamb (TD-023) turns its pivot half round: its local faces swap.
	if d.flip != 0.0 and d.op_id == str(op["id"]):
		face = -face
	var lock_x: float = d.leaf_local.origin.x * 2.0
	var locked: bool = d.is_locked()
	var model: String = ""
	match kind:
		"padlock":
			model = "props/lock_padlock" if locked else "props/lock_hasp_open"
		"chain":
			model = "props/lock_chain" if locked else ""
		"deadbolt":
			model = "props/lock_deadbolt"
		"bolt":
			model = "props/lock_bolt"
	d.lock_kind = kind
	d.lock_open_model = "props/lock_hasp_open" if kind == "padlock" else ""
	if model == "" or d.state == "broken":
		return
	var mi := MeshInstance3D.new()
	mi.name = "Lock"
	mi.mesh = PoiPieces.model_mesh(model, PoiPieces.model_size(model.trim_prefix("props/"), Vector3(0.18, 0.2, 0.05)), Color(0.33, 0.31, 0.28))
	# The far face is a mirror image (z flipped): hasp plate on the leaf, staple toward the frame.
	var y: float = float(LOCK_Y.get(kind, 1.2))
	mi.transform = Transform3D(Basis.IDENTITY if face > 0.0 else Basis.from_scale(Vector3(1, 1, -1)), Vector3(lock_x, y, 0.02 * face))
	d.pivot.add_child(mi)
	d.lock_mesh = mi
	if locked and kind in ["padlock", "chain"]:
		var cfg: Dictionary = PoiPieces.cfg("padlock")
		var lb := PoiPieces.LockBody.new()
		lb.name = "LockBody_" + d.op_id
		lb.door = d
		lb.piece_id = d.op_id + "_lock"
		lb.hp = root.piece_hp(lb.piece_id, float(cfg.get("chain_hp" if kind == "chain" else "hp", 60.0)))
		# A generous box over the lock, standing proud of the leaf, so a swing at it lands on it.
		var at: Vector3 = d.pivot.transform * Vector3(lock_x, y - 0.06, 0.07 * face)
		PoiPieces._box_shape(lb, Vector3(0.22, 0.26, 0.12), Transform3D(Basis.IDENTITY, at))
		d.add_child(lb)
		d.lock_body = lb


func _door(id: String, wall_xf: Transform3D, hinge: Vector3, flip: float, leaf: String, st: String, key: String, hp: float, inside_sign: float, leaf_size := Vector2(0.82, 2.05)) -> PoiPieces.Door:
	var d := PoiPieces.Door.new()
	d.poi = root
	d.op_id = id
	d.opening_id = PoiPieces.opening_of(id)
	d.state = root.piece_state(id, st if st != "barricaded" else "closed")
	d.key = key
	d.hp = hp
	d.inside_sign = inside_sign
	d.model_broken = PoiParts.KIT + leaf + "_broken"
	d.transform = wall_xf
	d.hp = root.piece_hp(id, hp)
	d.flip = flip
	d.pivot = Node3D.new()
	d.pivot.position = hinge
	d.pivot.rotation.y = flip
	d.add_child(d.pivot)
	var mi := MeshInstance3D.new()
	mi.mesh = PoiParts.kit_mesh(leaf) if d.state != "broken" else PoiParts.kit_mesh(leaf + "_broken")
	# A broken door with no broken model (metal, wood) has lost its leaf: drawing the stand-in
	# would hang a slab in a doorway the player walks through (the first playtest). Door.break_open
	# hides it the same way.
	if d.state == "broken" and not ModelLibrary.has_model(d.model_broken):
		mi.visible = false
	d.pivot.add_child(mi)
	d.leaf_local = Transform3D(Basis.IDENTITY, Vector3(leaf_size.x * 0.5, leaf_size.y * 0.5, 0))
	d.leaf_shape = _box(Vector3(leaf_size.x, leaf_size.y, 0.05), d.pivot.transform * d.leaf_local, d)
	d.leaf_shape.disabled = d.state == "broken"
	root.add_child(d)
	return d


func _glass(id: String, wall_xf: Transform3D, pane: String, st: String, w: float, h: float, sill: float) -> PoiPieces.Breakable:
	var g := PoiPieces.Breakable.new()
	g.poi = root
	g.piece_id = id
	g.kind = "glass"
	g.hp = 1.0
	g.model_broken = PoiParts.KIT + pane + "_broken"
	g.transform = wall_xf * Transform3D(Basis.IDENTITY, Vector3(0, sill, 0))
	var mi := MeshInstance3D.new()
	mi.mesh = PoiParts.kit_mesh(pane if st != "broken" else pane + "_broken")
	g.mesh_node = mi
	g.add_child(mi)
	if st != "broken":
		_box(Vector3(w, h, 0.03), Transform3D(Basis.IDENTITY, Vector3(0, h * 0.5, 0)), g)
	root.add_child(g)
	return g


func _barricade(id: String, wall_xf: Transform3D, side_sign: float, piece: String, hp: float, sill: float = 0.0, box_size := Vector3.ZERO) -> PoiPieces.Breakable:
	if root.piece_state(id, "intact") == "broken":
		return null
	var b := PoiPieces.Breakable.new()
	b.poi = root
	b.piece_id = id
	b.kind = "boards"
	b.hp = root.piece_hp(id, hp)
	var off := Vector3(0, sill, side_sign * (WALL_T * 0.5 + (0.45 if piece == "barricade_furniture" else 0.04)))
	b.transform = wall_xf * Transform3D(Basis.IDENTITY if side_sign > 0.0 else Basis(Vector3.UP, PI), off)
	var mi := MeshInstance3D.new()
	mi.mesh = PoiParts.kit_mesh(piece)
	b.mesh_node = mi
	b.add_child(mi)
	var size := Vector3(1.0, 1.2, 0.08) if piece.begins_with("boards_window") else (Vector3(1.0, 2.1, 0.08) if piece == "boards_door" else Vector3(1.6, 1.4, 0.8))
	if piece == "boards_window_2m":
		size.x = 1.8
	if box_size != Vector3.ZERO:
		size = box_size
	_box(size, Transform3D(Basis.IDENTITY, Vector3(0, size.y * 0.5, 0)), b)
	root.add_child(b)
	return b


# --- exterior: foundation, porch, chimney ----------------------------------------------------

## The roof plan (RoofPlanner, a pure function of the layout; prepare_check's when there is one), a
## step of its own: the chimney (_exterior), the roof and the probes need it.
func _roof_plan() -> void:
	var v: PoiValidator = _prepared()
	if v != null:
		_wings = v.roof_wings
	if _wings.is_empty():
		_wings = RoofPlanner.plan(layout)


## Resumable (see PHASES): one foundation wall an item, then the porch and chimney.
func _exterior() -> bool:
	var li0: int = 0 if layout.levels.has(0) else layout.level_ids.front()
	var fh: float = layout.floor_height
	if _cursor < 0:
		_work = layout.walls.keys() if fh > 0.12 else []
		_cursor = 0
	while _cursor < _work.size():
		var w: Dictionary = layout.walls[_work[_cursor]]
		_cursor += 1
		if int(w["level"]) != li0 or not w["exterior"]:
			continue
		var xf: Transform3D = _edge_xf(li0, w["axis"], w["cell"])
		xf.origin.y = -0.4
		var s: float = (fh + 0.4) / 0.6
		xf.basis = xf.basis.scaled(Vector3(1.0, s, 1.0))
		_add("foundation_1m", xf, Color(0, 0, _decay_v(), _seed()))
		if _spent():
			return false
	var porch: Dictionary = layout.style.get("porch", {})
	if not porch.is_empty():
		_porch(porch, li0)
	var chim: Variant = layout.style.get("chimney", null)
	if chim is Array:
		var p := Vector3(layout.origin.x + float(chim[0]) + 0.5, 0.0, layout.origin.y + float(chim[1]) + 0.5)
		# The 4.5 m chimney stood under the eaves of anything taller than a cabin: lift it on whole
		# metres of plain shaft (the brick courses run on) until it clears the roofs near it.
		var shafts: int = _chimney_shafts(Vector2(p.x, p.z))
		for k: int in shafts:
			_add("chimney_shaft_1m", Transform3D(Basis.IDENTITY, p + Vector3.UP * float(k)), Color(0, 0, clampf(_decay, 0.0, 1.0), _rng2.randf()))
		_add("chimney_brick", Transform3D(Basis.IDENTITY, p + Vector3.UP * float(shafts)), Color(0, 0, _decay_v(), _seed()))
		var ch_h: float = 4.5 + float(shafts)
		_box(Vector3(0.8, ch_h, 0.6), Transform3D(Basis.IDENTITY, p + Vector3.UP * (ch_h * 0.5)))
	return true


## Metres of shaft a chimney needs under its 4.5 m top piece to stand 0.4 m clear of every roof
## within 3 m of it (the flue rule of thumb): past the ridge beside a gable end, a little above the
## eave beside a long wall.
func _chimney_shafts(at: Vector2) -> int:
	if _wings.is_empty():
		_wings = RoofPlanner.plan(layout)
	var peak: float = 0.0
	for w: RoofPlanner.Wing in _wings:
		if w.type == "none":
			continue
		var r: Rect2 = w.rect_m(layout.origin, w.span).grow(w.overhang)
		var near: Rect2 = r.intersection(Rect2(at - Vector2(3.0, 3.0), Vector2(6.0, 6.0)))
		if near.size.x <= 0.0 or near.size.y <= 0.0:
			continue
		for i: int in 7:
			for j: int in 7:
				var q: Vector2 = near.position + near.size * Vector2(float(i) / 6.0, float(j) / 6.0)
				peak = maxf(peak, _wing_h(w, q))
	return maxi(0, ceili(peak + 0.4 - 4.5 - 0.12))


## Height of a wing's roof over a plan point (POI-local metres): its slopes extended over the eaves,
## clamped to the wing's eave and top.
func _wing_h(w: RoofPlanner.Wing, q: Vector2) -> float:
	var r: Rect2 = w.rect_m(layout.origin, w.span)
	var t: float = tan(deg_to_rad(w.pitch))
	var h: float = w.y + w.rise()
	match w.type:
		"gable":
			h = w.y + (r.size.y * 0.5 - absf(q.y - r.get_center().y)) * t if w.axis == "x" else w.y + (r.size.x * 0.5 - absf(q.x - r.get_center().x)) * t
		"shed":
			var rise_from: Array[float] = [q.y - r.position.y, r.end.x - q.x, r.end.y - q.y, q.x - r.position.x]
			h = w.y + rise_from[w.slope] * t
		"hip", "pyramid":
			h = w.y + minf(minf(q.x - r.position.x, r.end.x - q.x), minf(q.y - r.position.y, r.end.y - q.y)) * t
		"flat":
			h = w.y + 0.25
	return clampf(h, w.y - w.overhang * t, w.y + w.rise())


func _porch(porch: Dictionary, li0: int) -> void:
	var side: int = PoiLayout.SIDES.get(str(porch.get("side", "S")), 2)
	var from: int = int(porch.get("from", 0))
	var to: int = int(porch.get("to", 3))
	var depth: int = int(porch.get("depth", 2))
	var lv: Dictionary = layout.levels[li0]
	var top: float = layout.floor_height
	# JSON numbers are floats: as ints, or `steps.has(i)` never matched and no authored porch got
	# its steps (player report 3 item 5, found by poi_walk).
	var steps: Array[int] = []
	for v: Variant in porch.get("steps", []):
		steps.append(int(v))
	for i: int in range(from, to + 1):
		for k: int in depth:
			var cell: Vector2i
			match side:
				2:
					cell = Vector2i(i, int(lv["d"]) + k)
				0:
					cell = Vector2i(i, -1 - k)
				1:
					cell = Vector2i(int(lv["w"]) + k, i)
				_:
					cell = Vector2i(-1 - k, i)
			var p := Vector3(layout.origin.x + cell.x + 0.5, top - 0.6, layout.origin.y + cell.y + 0.5)
			_add("porch_deck_1m", Transform3D(Basis.IDENTITY, p), Color(0, 0, _decay_v(), _seed()))
			_box(Vector3(1.0, 0.2, 1.0), Transform3D(Basis.IDENTITY, p + Vector3.UP * (0.5)))
			var outer: bool = k == depth - 1
			if outer and (i == from or i == to or (i - from) % 3 == 0):
				var d3 := Vector3(PoiLayout.DIRS[side].x, 0, PoiLayout.DIRS[side].y)
				_add("porch_post", Transform3D(Basis.IDENTITY, p + d3 * 0.42 + Vector3.UP * 0.6), Color(0, 0, _decay_v(), _seed()))
			if outer and steps.has(i):
				var d4 := Vector3(PoiLayout.DIRS[side].x, 0, PoiLayout.DIRS[side].y)
				var yaw: float = [PI, PI * 0.5, 0.0, -PI * 0.5][side]
				var edge_top := Vector3(p.x, top, p.z) + d4 * 0.5
				_add("porch_step_1m", Transform3D(Basis(Vector3.UP, yaw), Vector3(edge_top.x, 0.0, edge_top.z)), Color(0, 0, _decay_v(), _seed()))
				_ramp(edge_top, edge_top + d4 * 0.95 - Vector3.UP * top, 1.0)


## Walkable ramp collision between two edge-centre points (its top surface on the line).
func _ramp(a: Vector3, b: Vector3, width: float) -> void:
	var along: Vector3 = b - a
	var z: Vector3 = along.normalized()
	var x: Vector3 = Vector3.UP.cross(z).normalized()
	if x.length() < 0.01:
		x = Vector3.RIGHT
	var y: Vector3 = z.cross(x).normalized()
	var basis := Basis(x, y, z)
	_box(Vector3(width, 0.1, along.length() + 0.1), Transform3D(basis, (a + b) * 0.5 - y * 0.05))


# --- roof ------------------------------------------------------------------------------------------

## The roof plan (RoofPlanner, ADR-0021): wings over the building's tops at their own heights,
## each roofed for where it sits, joined along valleys and cut at taller walls. Gable ends and
## parapets wear the building's exterior finish and decay (ADR-0019).
## Resumable (see PHASES): RoofBuilder.Job's stages, a wing or a face at a time.
func _roof() -> bool:
	if _cursor < 0:
		# _roof_plan planned it (the plan is a pure function of the layout).
		if _wings.is_empty():
			_wings = RoofPlanner.plan(layout)
		var ctx: Dictionary = {"exterior": str(layout.style.get("exterior", "siding_white")), "decay": _decay, "layout": layout,
			"open_finish": {}, "partitions": []}
		# The job reads ctx from its first step on: the open wings fill it first.
		_roof_job = RoofBuilder.Job.new(_wings, layout.origin, ctx)
		_cursor = 0
	# Open wings, one an item: the finish under them and the partitions rising to them.
	while _cursor < _wings.size():
		var w: RoofPlanner.Wing = _wings[_cursor]
		_cursor += 1
		if w.open:
			(_roof_job.ctx["open_finish"] as Dictionary)[w.index] = _open_finish(w)
			(_roof_job.ctx["partitions"] as Array).append_array(_open_partitions(w))
			if _spent():
				return false
	if not _roof_job.step(_deadline):
		return false
	var built: Array = _roof_job.out
	_roof_job = null
	for item: Variant in built:
		if item is MeshInstance3D or item is MultiMeshInstance3D:
			root.add_child(item)
		elif item is Shape3D:
			var cs := CollisionShape3D.new()
			cs.shape = item
			shell.add_child(cs)
	return true


## Wall finish of the open room under a wing (the inside face of its gable ends).
func _open_finish(w: RoofPlanner.Wing) -> int:
	for z: int in range(w.cells.position.y, w.cells.end.y):
		for x: int in range(w.cells.position.x, w.cells.end.x):
			var c := Vector2i(x, z)
			if layout.open_roof_at(w.level, c):
				return _finish_r(layout.volume_of(w.level, c), "wall")
	return _finish_r([], "wall")


## Walls under an open roof between the open room and a closed one (or a gallery with a ceiling):
## they rise from the storey band to the roof, so the closed room's attic stays shut.
## [a, b, y0, open finish, other finish, toward the open side] for RoofBuilder.
func _open_partitions(w: RoofPlanner.Wing) -> Array:
	var out: Array = []
	var li: int = w.level
	var o: Vector2 = layout.origin
	for z: int in range(w.cells.position.y, w.cells.end.y + 1):
		for x: int in range(w.cells.position.x, w.cells.end.x + 1):
			for axis: String in ["h", "v"]:
				var c := Vector2i(x, z)
				var cells: Array[Vector2i] = PoiLayout.edge_cells(axis, c)
				if not (w.cells.has_point(cells[0]) or w.cells.has_point(cells[1])):
					continue
				if not (layout.is_built(li, cells[0]) and layout.is_built(li, cells[1])):
					continue
				if layout.is_built(li + 1, cells[0]) or layout.is_built(li + 1, cells[1]):
					continue
				var open_a: bool = layout.open_roof_at(li, cells[0])
				var open_b: bool = layout.open_roof_at(li, cells[1])
				if open_a == open_b:
					continue
				var a := Vector2(o.x + x, o.y + z)
				var b: Vector2 = a + (Vector2(1, 0) if axis == "h" else Vector2(0, 1))
				var toward: Vector2 = (Vector2(0, 1) if axis == "h" else Vector2(1, 0)) * (1.0 if open_a else -1.0)
				var open_cell: Vector2i = cells[0] if open_a else cells[1]
				var other_cell: Vector2i = cells[1] if open_a else cells[0]
				out.append([a, b, w.y - 0.2, _finish_r(layout.volume_of(li, open_cell), "wall"), _finish_r(layout.volume_of(li, other_cell), "wall"), toward])
	return out


# --- props & set dressing ------------------------------------------------------------------------

func _prop_xf(p: Dictionary, pd: PropDef) -> Transform3D:
	var plan: Vector3 = PoiLayout.prop_plan(p, pd)
	var pos := Vector2(plan.x, plan.y)
	var rot: float = plan.z
	# Free-standing props in the yard stand on the pad; wall-mounted ones hang at a height measured
	# from the building's floor, whichever side of the wall they are on.
	var li: int = int(p["level"])
	var y: float = (layout.level_y(li) if pd.wall_mounted else _base_y(li, p["cell"])) + float(p.get("y", 0.0))
	if pd.wall_mounted:
		y += float(p.get("height", 1.4))
	elif pd.has_tag("ceiling_mounted") and not p.has("y") and layout.is_built(li, p["cell"]):
		# A ceiling fixture hangs from the real ceiling: storeys up in a tall room.
		y += layout.ceiling_height(li, p["cell"])
	return Transform3D(Basis(Vector3.UP, deg_to_rad(rot)), Vector3(layout.origin.x + pos.x, y, layout.origin.y + pos.y))


## Resumable (see PHASES): one authored prop an item.
func _props() -> bool:
	if _cursor < 0:
		_cursor = 0
	while _cursor < layout.props.size():
		_prop(layout.props[_cursor])
		_cursor += 1
		if _spent():
			break
	return _cursor >= layout.props.size()


func _prop(p: Dictionary) -> void:
	var lr_char: String = str(layout.loot_room.get("room", ""))
	var lr_level: int = int(layout.loot_room.get("level", 0))
	var pd: PropDef = Content.get_def(&"prop", StringName(str(p.get("prop", "")))) as PropDef
	if pd == null:
		return
	var cond: String = str(p.get("variant", layout.style.get("prop_condition", "worn")))
	var model: String = pd.model_for(cond)
	var xf: Transform3D = _prop_xf(p, pd)
	_occupied[PoiValidator.node_key(p["level"], p["cell"])] = true
	var cont: StringName = StringName(str(p.get("container", pd.container)))
	# A lit light source burns only in a variant that can (a destroyed lantern stays dark) and
	# glows on its own instance (PropLights, ADR-0023).
	var light: Dictionary = pd.light_for(cond) if bool(p.get("lit", false)) else {}
	if cont != &"" and Content.get_def(&"container", cont) != null:
		var lp := PoiPieces.LootProp.new()
		lp.poi = root
		lp.prop = pd
		lp.cdef = Content.get_def(&"container", cont) as ContainerDef
		# Keyed by the prop's authored id when it has one (TD-031), else its list index.
		lp.container_id = StringName("c:%s:%s" % [root.instance_id, p["pkey"]])
		lp.prop_key = str(p["pkey"])
		lp.tier = layout.def.tier
		lp.bonus = int(p["level"]) == lr_level and layout.room_at(p["level"], p["cell"]) == lr_char
		lp.key = str(p.get("key", ""))
		lp.transform = xf
		var mi := MeshInstance3D.new()
		mi.mesh = ModelLibrary.mesh(model, "box")
		if not light.is_empty():
			PropLights.set_lit(mi, true)
		lp.add_child(mi)
		_box(pd.size.max(Vector3(0.2, 0.2, 0.2)), Transform3D(Basis.IDENTITY, pd.box_centre()), lp)
		root.add_child(lp)
	else:
		if light.is_empty():
			_add("@" + model, xf, Color(0, 0, 0, 0), layout.is_room(layout.room_at(p["level"], p["cell"])))
		else:
			root.add_child(PropLights.lit_mesh(model, xf, layout.is_room(layout.room_at(p["level"], p["cell"]))))
		if pd.collision != "none":
			_box(pd.size.max(Vector3(0.05, 0.05, 0.05)), xf * Transform3D(Basis.IDENTITY, pd.box_centre()))
	if not light.is_empty():
		root.add_child(PropLights.light_node(light, xf))


## Dense, room-appropriate clutter along walls (deterministic per instance), kept off the route.
## POI room types -> the prop room tags whose clutter suits them (room types are finer or coarser
## than the tags props carry; unknown types use their own name).
const ROOM_TAGS: Dictionary = {
	"bath": ["bathroom"],
	"storage": ["basement", "garage", "store"],
	"loft": ["basement", "garage"],
	"pharmacy": ["store", "office"],
	"cells": ["office", "basement"],
	"diner": ["diner", "kitchen"],
	# Room types of the wider POI roster: each also matches props tagged with its own name.
	"church": ["church", "living"],
	"bar": ["bar", "diner", "kitchen"],
	"motel_room": ["motel_room", "bedroom", "bathroom"],
	"classroom": ["classroom", "office"],
	"clinic": ["clinic", "pharmacy", "office", "bathroom"],
	"post_office": ["post_office", "office", "store"],
	"hall": ["hall", "living", "office"],
	"workshop": ["workshop", "garage", "basement"],
	"mill": ["mill", "garage", "basement"],
	"bunkhouse": ["bunkhouse", "bedroom", "basement"],
	"barn": ["barn", "garage", "basement"],
	"cellar": ["cellar", "basement"],
	"lookout": ["lookout", "office"],
}


## Resumable (see PHASES): one room cell an item.
func _scatter() -> bool:
	var sc: Dictionary = layout.style.get("scatter", {})
	var density: float = float(sc.get("density", 0.35))
	if density <= 0.0:
		return true
	if _cursor < 0:
		var v: PoiValidator = _prepared()
		_by_room = v.clutter if v != null else clutter_by_room()
		# Rows, not layout.room_cells(): listing a big building's cells up front was ~8 ms.
		_work = []
		for li: int in layout.level_ids:
			for r: int in int(layout.levels[li]["d"]):
				_work.append(Vector2i(li, r))
		_cursor = 0
		if _spent():
			return false
	while _cursor < _work.size():
		var li: int = _work[_cursor].x
		var r: int = _work[_cursor].y
		# The cells of layout.room_cells(li), in its order.
		for c: int in int(layout.levels[li]["w"]):
			if layout.is_room(layout.room_at(li, Vector2i(c, r))):
				_scatter_cell(li, Vector2i(c, r), density)
		_cursor += 1
		if _spent():
			break
	return _cursor >= _work.size()


## Room tag -> the small clutter props that suit it ("any": untagged ones). Reads ContentDB.instance,
## so prepare_check can make it on its worker (~4 ms over every prop def).
static func clutter_by_room() -> Dictionary:
	var by_room: Dictionary = {}
	for pd: PropDef in ContentDB.instance.all(&"prop"):
		if not pd.has_tag("clutter") or pd.size.x * pd.size.z > 0.6:
			continue
		for room_type: String in (pd.rooms if not pd.rooms.is_empty() else PackedStringArray(["any"])):
			if not by_room.has(room_type):
				by_room[room_type] = []
			(by_room[room_type] as Array).append(pd)
	return by_room


func _scatter_cell(li: int, c: Vector2i, density: float) -> void:
	var by_room: Dictionary = _by_room
	var k: String = PoiValidator.node_key(li, c)
	if _route_cells.has(k) or _occupied.has(k) or _well(li).has(c):
		return
	var room: Dictionary = layout.room_def(li, layout.room_at(li, c))
	var room_type: String = str(room.get("type", "any"))
	var pool: Array = by_room.get("any", []).duplicate()
	for tag: String in ROOM_TAGS.get(room_type, [room_type]):
		pool.append_array(by_room.get(tag, []))
	if pool.is_empty():
		return
	for side: int in 4:
		var e: Array = PoiLayout.side_edge(c, side)
		var wall: Dictionary = layout.walls.get(PoiLayout.edge_key(li, e[0], e[1]), {})
		if wall.is_empty() or not (wall["opening"] as Dictionary).is_empty():
			continue
		if _rng.randf() > density * 0.5:
			continue
		var pd2: PropDef = pool[_rng.randi() % pool.size()]
		var entry: Dictionary = {"level": li, "cell": c, "pos": Vector2(c.x + 0.5 + _rng.randf_range(-0.25, 0.25), c.y + 0.5 + _rng.randf_range(-0.25, 0.25)),
			"against": PoiLayout.SIDE_NAMES[side], "rot": [0.0, -90.0, 180.0, 90.0][side] + _rng.randf_range(-25, 25)}
		var xf: Transform3D = _prop_xf(entry, pd2)
		var cond: String = "destroyed" if _rng.randf() < _decay * 0.3 else "worn"
		_add("@" + pd2.model_for(cond), xf, Color(0, 0, 0, 0), true)
		_occupied[k] = true
		break


## SDFGI occludes the sky indoors, which leaves rooms near-black even at noon. Interior reflection
## probes give the rooms their own ambient fill (scaled with daylight by EnvironmentController
## through the "interior_probe" group, so nights stay dark) and keep sky reflections off indoor
## floors. One probe per rectangle of rooms of one height (TD-040): each level's room cells are
## grouped by how high their room rises, split into rectangles, stacked where a rectangle repeats
## storey over storey, and merged pairwise (least waste first) down to MAX_PROBES. A yard inside an
## L or a courtyard is in no box, so it keeps the outdoor light. Boxes stop just inside the walls so
## facades keep it too.
## Resumable (see PHASES): prepare_check's boxes, else one level's rectangles an item, then the
## merge and the probes.
func _interior_probes() -> bool:
	var v: PoiValidator = _prepared()
	if _cursor < 0:
		_rects = []
		_cursor = 0 if v == null else layout.level_ids.size()
	while _cursor < layout.level_ids.size():
		_rects.append_array(_probe_rects(layout.level_ids[_cursor]))
		_cursor += 1
		if _spent():
			return false
	for box: AABB in (v.probe_boxes if v != null else _merge_probe_rects(_rects)):
		var probe := ReflectionProbe.new()
		probe.name = "InteriorProbe"
		probe.interior = true
		probe.ambient_mode = ReflectionProbe.AMBIENT_COLOR
		probe.ambient_color = Color(0.86, 0.83, 0.78)
		# A daytime fill until EnvironmentController takes over (previews, tests, the first frame).
		probe.ambient_color_energy = 0.5
		probe.size = box.size
		probe.position = box.get_center()
		probe.blend_distance = 0.3
		probe.max_distance = maxf(probe.size.x, probe.size.z)
		probe.update_mode = ReflectionProbe.UPDATE_ONCE
		probe.add_to_group(&"interior_probe")
		root.add_child(probe)
	return true


## The interior probe boxes (POI-local), at most MAX_PROBES.
func probe_boxes() -> Array[AABB]:
	var rects: Array = []
	for li: int in layout.level_ids:
		rects.append_array(_probe_rects(li))
	return _merge_probe_rects(rects)


## [level, top level, Rect2i, open] per rectangle of level `li`'s room cells whose room rises to
## the same storey.
func _probe_rects(li: int) -> Array:
	var rects: Array = []
	var groups: Dictionary = {}
	for c: Vector2i in layout.room_cells(li):
		var top: int = layout.column_top(li, c)
		var key: int = top * 2 + (1 if layout.open_roof_at(li, c) and not layout.is_built(top + 1, c) else 0)
		if not groups.has(key):
			groups[key] = {}
		(groups[key] as Dictionary)[c] = true
	for key2: int in groups:
		for r: Rect2i in RoofPlanner.decompose(groups[key2]):
			rects.append([li, key2 >> 1, r, key2 & 1])
	return rects


## The probe boxes of every level's rectangles, stacked and merged down to MAX_PROBES.
func _merge_probe_rects(rects: Array) -> Array[AABB]:
	# A rectangle repeated storey over storey (stacked floors of one block): one box.
	var merged: bool = true
	while merged:
		merged = false
		for i: int in rects.size():
			for j: int in rects.size():
				var a: Array = rects[i]
				var b: Array = rects[j]
				if i != j and a[2] == b[2] and int(a[1]) + 1 == int(b[0]) and int(a[3]) == 0:
					rects[i] = [a[0], b[1], a[2], b[3]]
					rects.remove_at(j)
					merged = true
					break
			if merged:
				break
	var boxes: Array[AABB] = []
	for e: Array in rects:
		boxes.append(_probe_box(int(e[0]), int(e[1]), e[2], int(e[3]) == 1))
	# Over the cap: merge the pair whose union wastes the least volume.
	while boxes.size() > MAX_PROBES:
		var best: Vector2i = Vector2i(0, 1)
		var best_waste: float = INF
		for i2: int in boxes.size():
			for j2: int in range(i2 + 1, boxes.size()):
				var u: AABB = boxes[i2].merge(boxes[j2])
				var waste: float = u.get_volume() - boxes[i2].get_volume() - boxes[j2].get_volume()
				if waste < best_waste:
					best_waste = waste
					best = Vector2i(i2, j2)
		boxes[best.x] = boxes[best.x].merge(boxes[best.y])
		boxes.remove_at(best.y)
	return boxes


## The box of one rectangle of room cells: inset 5 cm from the walls' centre lines, from under its
## floor slab to its ceiling (to the ridge where it is open to the roof).
func _probe_box(li: int, top: int, r: Rect2i, open: bool) -> AABB:
	var lo: float = layout.level_y(li) - 0.2
	var hi: float = layout.level_y(top) + PoiLayout.STOREY
	if open:
		for w: RoofPlanner.Wing in _wings:
			if w.level == top and w.cells.intersects(r):
				hi = maxf(hi, w.y + w.rise())
	var p := Vector3(layout.origin.x + r.position.x + 0.05, lo, layout.origin.y + r.position.y + 0.05)
	return AABB(p, Vector3(maxf(0.5, r.size.x - 0.1), hi - lo, maxf(0.5, r.size.y - 0.1)))


func _light_at(pos: Vector3, l: Dictionary) -> void:
	var light: OmniLight3D = FlickerLight.new() if float(l.get("flicker", 0.0)) > 0.0 else OmniLight3D.new()
	if light is FlickerLight:
		(light as FlickerLight).flicker = float(l.get("flicker", 0.2))
	light.light_color = Color.html(str(l.get("color", "#ffcf96")))
	light.light_energy = float(l.get("energy", 1.0))
	light.omni_range = float(l.get("range", 6.0))
	light.shadow_enabled = bool(l.get("shadow", false))
	if light.shadow_enabled:
		# PoiManager keeps shadows on the nearest of these only (max_shadowed_lights).
		light.add_to_group(&"shadow_light_budget")
	light.position = pos
	root.add_child(light)


func _lights() -> void:
	for l: Variant in layout.lights:
		if not l is Dictionary:
			continue
		var d: Dictionary = l
		var placed: Dictionary = layout._placed(d)
		# Lights hang half a metre under the real ceiling unless their height is given (a tall
		# room's ceiling is storeys up).
		var ceiling: float = layout.ceiling_height(int(placed["level"]), placed["cell"])
		var pos: Vector3 = layout.local_pos(placed["level"], placed["pos"]) + Vector3.UP * float(d.get("height", ceiling - 0.5))
		_light_at(pos, d)


func _pickups() -> void:
	for i: int in layout.pickups.size():
		var p: Dictionary = layout.pickups[i]
		var pid: String = str(p["pid"])
		if root.piece_state(pid, "") == "broken":
			continue
		var pk := PoiPieces.Pickup.new()
		pk.poi = root
		pk.pickup_id = pid
		pk.item = StringName(str(p.get("item", "")))
		pk.count = int(p.get("count", 1))
		var pk_pos: Vector3 = layout.local_pos(p["level"], p["pos"])
		pk_pos.y = _base_y(int(p["level"]), p["cell"])
		pk.position = pk_pos + Vector3.UP * float(p.get("y", 0.0))
		pk.rotation.y = deg_to_rad(float(p.get("rot", 0.0)))
		root.add_child(pk)


## Authored decals, then the per-run ones of a dressed building (Dressing.run_decals, ADR-0030).
## Resumable (see PHASES): one decal an item (each loads its textures). The per-run list is
## prepare_check's when there is one (listing a big building's wall faces took ~25 ms).
func _decals() -> bool:
	if _cursor < 0:
		var v: PoiValidator = _prepared()
		_work = layout.decals.duplicate()
		_work.append_array(v.run_decals if v != null else Dressing.run_decals(layout))
		_cursor = 0
		if _spent():
			return false
	while _cursor < _work.size():
		_decal(_work[_cursor])
		_cursor += 1
		if _spent():
			break
	return _cursor >= _work.size()


func _decal(d: Variant) -> void:
	if not d is Dictionary:
		return
	var path: String = "res://assets/generated/textures/decal_%s_albedo.png" % str(d.get("decal", ""))
	if not ResourceLoader.exists(path):
		return
	var placed: Dictionary = layout._placed(d)
	var dec := Decal.new()
	dec.texture_albedo = load(path)
	var npath: String = path.replace("_albedo.png", "_normal.png")
	if ResourceLoader.exists(npath):
		dec.texture_normal = load(npath)
	var size: Array = d.get("size", [1.0, 1.0])
	var pos: Vector3 = layout.local_pos(placed["level"], placed["pos"])
	var side: String = str(d.get("side", "floor"))
	if side == "floor":
		pos.y = _base_y(int(placed["level"]), placed["cell"])
		dec.size = Vector3(float(size[0]), 0.5, float(size[1]))
		dec.position = pos + Vector3.UP * 0.1
		dec.rotation.y = deg_to_rad(float(d.get("rot", _rng.randf() * 360.0)))
	else:
		var s: int = PoiLayout.SIDES.get(side, 0)
		var toward := Vector3(PoiLayout.DIRS[s].x, 0, PoiLayout.DIRS[s].y)
		var cell: Vector2i = placed["cell"]
		var wall_p: Vector3 = layout.cell_center(placed["level"], cell) + toward * 0.5
		# A decal projects along its local Y and maps the texture on X/Z: width, a shallow
		# depth, then height (height and depth were swapped, squashing the art to 0.4 m). The
		# shallow box sits on the room-side face so it does not show through on the outside.
		dec.size = Vector3(float(size[0]), 0.12, float(size[1]))
		dec.position = wall_p + Vector3.UP * float(d.get("height", 1.3)) - toward * (WALL_T * 0.5)
		dec.basis = Basis.looking_at(toward, Vector3.UP) * Basis(Vector3.RIGHT, PI * 0.5)
	dec.cull_mask = 1
	root.add_child(dec)


func _traps() -> void:
	for i: int in layout.traps.size():
		var t: Dictionary = layout.traps[i]
		var tid: String = str(t["tid"])
		match str(t["type"]):
			"can_chime":
				_can_chime(t, tid)
			"bear_trap":
				_bear_trap(t, tid)
			"shotgun":
				_shotgun_trap(t, tid)
			"creaky_floor":
				_creaky_floor(t, tid)
			"weak_floor":
				_weak_floor(t, tid)
			"alarm":
				_alarm(t, tid)


## Deterministic per instance and trap (a separate stream: the builder's own _rng must not shift).
func _trap_rng(tid: String) -> RandomNumberGenerator:
	var r := RandomNumberGenerator.new()
	r.seed = Ids.hash64("trap:%s:%s" % [root.instance_id, tid])
	return r


func _register(piece: PoiPieces.Trap, t: Dictionary, tid: String) -> void:
	piece.name = "Trap_" + tid
	piece.poi = root
	piece.trap_id = tid
	piece.type = str(t["type"])
	root.traps[tid] = piece


## Geometry of an edge trap: the edge centre (POI-local, floor level), the direction across it
## (from the "at" cell outwards) and along it.
func _edge_frame(t: Dictionary) -> Dictionary:
	var side: int = int(t["side_i"])
	var cc: Vector3 = layout.cell_center(t["level"], t["cell"])
	var across := Vector3(PoiLayout.DIRS[side].x, 0, PoiLayout.DIRS[side].y)
	var along := Vector3(absf(across.z), 0, absf(across.x))
	return {"center": cc + across * 0.5, "across": across, "along": along, "cell_center": cc}


func _can_chime(t: Dictionary, tid: String) -> void:
	var triggered: bool = (root.state.get("traps", {}) as Dictionary).has(tid)
	var side: int = PoiLayout.SIDES.get(str(t.get("side", "S")), 2)
	var cc: Vector3 = layout.cell_center(t["level"], t["cell"])
	var toward := Vector3(PoiLayout.DIRS[side].x, 0, PoiLayout.DIRS[side].y)
	var p: Vector3 = cc + toward * 0.35
	var model: String = "structures/can_chime"
	var mi := MeshInstance3D.new()
	mi.mesh = ModelLibrary.mesh(model, "box")
	mi.position = p + Vector3.UP * 0.3
	mi.rotation.y = 0.0 if side in [0, 2] else PI * 0.5
	root.add_child(mi)
	if triggered:
		return
	var tl := PoiPieces.TripLine.new()
	tl.poi = root
	tl.trap_id = tid
	tl.position = p
	var cs := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(1.0, 0.6, 0.2) if side in [0, 2] else Vector3(0.2, 0.6, 1.0)
	cs.shape = box
	cs.position = Vector3(0, 0.3, 0)
	tl.add_child(cs)
	root.add_child(tl)


## Steel jaws in the debris of a cell (or the yard): sensor on the pan, a crouch-interact box.
func _bear_trap(t: Dictionary, tid: String) -> void:
	var st: String = root.trap_state(tid)
	if st == "disarmed":
		return
	var bt := PoiPieces.BearTrap.new()
	_register(bt, t, tid)
	var rng: RandomNumberGenerator = _trap_rng(tid)
	# An authored "rot" wins; otherwise a deterministic random turn so no two sit square.
	var yaw: float = deg_to_rad(float(t["rot"])) if bool(t.get("rot_set", false)) else rng.randf() * TAU
	var bt_pos: Vector3 = layout.local_pos(t["level"], t["pos"])
	bt_pos.y = _base_y(int(t["level"]), t["cell"])
	bt.transform = Transform3D(Basis(Vector3.UP, yaw), bt_pos)
	bt.mesh = MeshInstance3D.new()
	bt.mesh.name = "Model"
	bt.add_child(bt.mesh)
	if st == "sprung":
		bt.show_sprung()
	else:
		bt.mesh.mesh = PoiPieces.model_mesh("props/trap_bear", PoiPieces.model_size("trap_bear", Vector3(0.42, 0.1, 0.42)), Color(0.24, 0.21, 0.19))
		var sensor: Area3D = bt.add_sensor(Vector3(0.44, 0.35, 0.36), Transform3D(Basis.IDENTITY, Vector3(0, 0.18, 0)),
			PoiPieces.PLAYER_LAYER | PoiPieces.ENEMY_LAYER)
		sensor.body_entered.connect(bt.on_body)
	bt.add_interact_box(Vector3(0.5, 0.16, 0.5), Transform3D(Basis.IDENTITY, Vector3(0, 0.08, 0)))
	root.add_child(bt)


## A tripwire across the edge and a shotgun lashed to a chair inside the "at" cell's room, beside
## the opening along the wall, its barrels across the doorway.
func _shotgun_trap(t: Dictionary, tid: String) -> void:
	var st: String = root.trap_state(tid)
	var f: Dictionary = _edge_frame(t)
	var li: int = int(t["level"])
	var c: Vector2i = t["cell"]
	var along: Vector3 = f["along"]
	var across: Vector3 = f["across"]
	var step := Vector2i(int(along.x), int(along.z))
	# The gun goes into the neighbouring cell along the wall on the side with floor to stand on
	# (a room cell, not the open well over a stair or hatch).
	var sgn: float = 0.0
	var well: Dictionary = layout.stairwell_cells(li)
	for k: float in [1.0, -1.0]:
		var nc: Vector2i = c + step * int(k)
		var wall_between: Dictionary = layout.walls.get(PoiLayout.edge_key(li, "v" if step.x != 0 else "h", c + (step if k > 0.0 else Vector2i.ZERO)), {})
		if layout.is_room(layout.room_at(li, nc)) and wall_between.is_empty() and not well.has(nc):
			sgn = k
			break
	var centre: Vector3 = f["center"]
	var s2: float = sgn if sgn != 0.0 else 1.0
	var gun: Vector3 = centre - across * 0.42 + along * (0.78 * sgn) if sgn != 0.0 else centre - across * 0.8
	var far_jamb: Vector3 = centre - along * (0.4 * s2)
	var near_jamb: Vector3 = centre + along * (0.4 * s2)
	var sg := PoiPieces.ShotgunTrap.new()
	_register(sg, t, tid)
	# Aimed across the doorway at its middle: whoever catches the wire is standing there when the
	# cord pulls the trigger.
	var aim: Vector3 = (centre - gun)
	aim.y = 0.0
	aim = aim.normalized()
	sg.transform = Transform3D(Basis(Vector3.UP, atan2(aim.x, aim.z)), gun)
	# Matches props/trap_shotgun_rig: barrels level over the seat front, muzzle 0.51 m up and 0.47 m
	# ahead of the chair's centre; the trigger cord runs down to a nail in the front stretcher.
	sg.muzzle = Vector3(0, 0.51, 0.47)
	sg.aim = Vector3.BACK
	var rig := MeshInstance3D.new()
	rig.name = "Rig"
	rig.mesh = PoiPieces.model_mesh("props/trap_shotgun_rig", PoiPieces.model_size("trap_shotgun_rig", Vector3(0.46, 0.9, 0.5)), Color(0.36, 0.27, 0.19))
	sg.add_child(rig)
	var body := StaticBody3D.new()
	body.name = "RigBody"
	body.collision_layer = 1 << 2
	body.collision_mask = 0
	PoiPieces._box_shape(body, Vector3(0.44, 0.9, 0.44), Transform3D(Basis.IDENTITY, Vector3(0, 0.45, 0)))
	sg.add_child(body)
	if st == "disarmed":
		root.add_child(sg)
		return
	# The wire: jamb to jamb across the doorway at shin height, then up to the trigger guard.
	var inv: Transform3D = sg.transform.affine_inverse()
	var a: Vector3 = inv * (far_jamb + Vector3.UP * 0.16)
	var b: Vector3 = inv * (near_jamb + Vector3.UP * 0.16)
	var trig := Vector3(0.0, 0.2, 0.17)
	var wire := Node3D.new()
	wire.name = "Wires"
	wire.add_child(_wire_mesh(a, b))
	wire.add_child(_wire_mesh(b, trig))
	sg.add_child(wire)
	sg.wire = wire
	if st == "armed":
		var wlen: float = a.distance_to(b)
		var wxf := Transform3D(Basis.looking_at((b - a).normalized(), Vector3.UP), (a + b) * 0.5)
		var sensor: Area3D = sg.add_sensor(Vector3(0.3, 0.5, wlen), wxf, PoiPieces.PLAYER_LAYER | PoiPieces.ENEMY_LAYER)
		sensor.body_entered.connect(sg.on_body)
		sg.add_interact_box(Vector3(0.3, 0.3, wlen), wxf)
	else:
		wire.visible = false
	root.add_child(sg)


## A taut cord between two points (local to its parent): a thin box, dark and slightly glossy.
func _wire_mesh(a: Vector3, b: Vector3) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.name = "Wire"
	var bm := BoxMesh.new()
	bm.size = Vector3(0.004, 0.004, a.distance_to(b))
	var m := StandardMaterial3D.new()
	m.albedo_color = Color(0.16, 0.15, 0.13)
	m.roughness = 0.55
	bm.material = m
	mi.mesh = bm
	var dir: Vector3 = (b - a).normalized()
	mi.transform = Transform3D(Basis.looking_at(dir, Vector3.UP if absf(dir.y) < 0.98 else Vector3.FORWARD), (a + b) * 0.5)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return mi


## Loose warped boards over each covered cell and a sensor over them all.
func _creaky_floor(t: Dictionary, tid: String) -> void:
	var cf := PoiPieces.CreakyFloor.new()
	_register(cf, t, tid)
	var cells: Array = t["cells"]
	var c0: Vector2i = cells[0]
	var origin: Vector3 = layout.cell_center(t["level"], c0) - Vector3(0.5, 0, 0.5)
	cf.position = origin
	var rng: RandomNumberGenerator = _trap_rng(tid)
	var lo := Vector2i(1 << 20, 1 << 20)
	var hi := Vector2i(-(1 << 20), -(1 << 20))
	for c: Vector2i in cells:
		lo = Vector2i(mini(lo.x, c.x), mini(lo.y, c.y))
		hi = Vector2i(maxi(hi.x, c.x), maxi(hi.y, c.y))
		var mi := MeshInstance3D.new()
		mi.mesh = PoiPieces.model_mesh("props/trap_creaky_boards", PoiPieces.model_size("trap_creaky_boards", Vector3(0.9, 0.03, 0.9)), Color(0.38, 0.3, 0.22))
		mi.transform = Transform3D(Basis(Vector3.UP, PI * 0.5 * float(rng.randi_range(0, 3))), Vector3(c.x - c0.x + 0.5, 0.0, c.y - c0.y + 0.5))
		cf.add_child(mi)
	var size := Vector3(hi.x - lo.x + 1, 0.6, hi.y - lo.y + 1)
	var sensor: Area3D = cf.add_sensor(size, Transform3D(Basis.IDENTITY, Vector3(size.x * 0.5, 0.3, size.z * 0.5)), PoiPieces.PLAYER_LAYER)
	sensor.body_entered.connect(cf.on_enter)
	sensor.body_exited.connect(cf.on_exit)
	root.add_child(cf)


## The rotten slab itself is a kit batch of its own (_floors); here its sensor and controller.
func _weak_floor(t: Dictionary, tid: String) -> void:
	var wf := PoiPieces.WeakFloor.new()
	_register(wf, t, tid)
	wf.position = layout.cell_center(t["level"], t["cell"])
	if root.trap_state(tid) == "armed":
		var sensor: Area3D = wf.add_sensor(Vector3(0.8, 0.5, 0.8), Transform3D(Basis.IDENTITY, Vector3(0, 0.25, 0)), PoiPieces.PLAYER_LAYER)
		sensor.body_entered.connect(wf.on_body)
	if _weak.has(tid):
		_weak[tid]["piece"] = wf
		wf.shape = _weak[tid]["shape"]
	root.add_child(wf)


func _wire_weak_floors() -> void:
	for tid: String in _weak:
		var wf: PoiPieces.WeakFloor = (_weak[tid] as Dictionary).get("piece")
		if wf == null:
			continue
		wf.intact_mm = _tagged.get("weak:" + tid)
		wf.broken_mm = _tagged.get("weakx:" + tid)
		if wf.broken_mm != null:
			wf.broken_mm.visible = false


## Centre of an opening's edge span (POI-local, at its level's floor): 2 m openings span this
## cell and the next one along the wall.
func _opening_center(op: Dictionary) -> Vector3:
	var e: Vector2i = op["edge"]
	var w: float = float(op["width"])
	var y: float = layout.level_y(int(op["level"]))
	if str(op["axis"]) == "h":
		return Vector3(layout.origin.x + e.x + w * 0.5, y, layout.origin.y + e.y)
	return Vector3(layout.origin.x + e.x, y, layout.origin.y + e.y + w * 0.5)


## A battery alarm on the header of the opening's frame, inside face (or a bell on a cord across
## an open passage) and a sensor across the edge; opening or breaking the opening sets it off too
## (PoiInstance._alarms_on).
func _alarm(t: Dictionary, tid: String) -> void:
	var st: String = root.trap_state(tid)
	if st == "disarmed":
		return
	var f: Dictionary = _edge_frame(t)
	var li: int = int(t["level"])
	var wall: Dictionary = layout.walls.get(PoiLayout.edge_key(li, t["axis"], t["edge"]), {})
	var op: Dictionary = wall.get("opening", {}) if not wall.is_empty() else {}
	var op_type: String = str(op.get("type", "open"))
	var style: String = str(t.get("style", "bell" if op.is_empty() or op_type in ["open", "breach", "half"] else "battery"))
	var al := PoiPieces.AlarmTrap.new()
	al.style = style
	_register(al, t, tid)
	var across: Vector3 = f["across"]
	var along: Vector3 = f["along"]
	var centre: Vector3 = _opening_center(op) if not op.is_empty() else (f["center"] as Vector3)
	var spec: Dictionary = PoiParts.OPENINGS.get(op_type, PoiParts.OPENINGS["open"])
	var width: float = float(op.get("width", 1))
	# Facing back into the "at" room, on the inside face of the wall.
	var face: Vector3 = -across
	var mount: Vector3 = centre - across * (PoiBuilder.WALL_T * 0.5 + 0.005)
	var top: float = float(spec["sill"]) + float(spec["h"]) if float(spec["h"]) > 0.0 and op_type != "open" else 2.1
	var y: float = minf(top + 0.03, 2.55)
	if style == "battery":
		# Latch-side top corner of the frame, on the header.
		mount += along * (float(spec["w"]) * 0.5 - 0.12)
	else:
		mount -= across * 0.12
		y = 1.95
	al.transform = Transform3D(Basis(Vector3.UP, atan2(face.x, face.z)), mount)
	var mi := MeshInstance3D.new()
	mi.name = "Model"
	var model: String = "props/trap_alarm_box" if style == "battery" else "props/trap_alarm_bell"
	mi.mesh = PoiPieces.model_mesh(model, PoiPieces.model_size(model.trim_prefix("props/"), Vector3(0.1, 0.16, 0.05)), Color(0.8, 0.78, 0.72))
	mi.position = Vector3(0, y, 0)
	al.add_child(mi)
	var inv: Transform3D = al.transform.affine_inverse()
	if style == "bell" and st == "armed":
		# The cord: across the passage at shin height, then up the jamb to the bell.
		var a: Vector3 = inv * (centre - along * (width * 0.5 - 0.05) - across * 0.1 + Vector3.UP * 0.2)
		var b: Vector3 = inv * (centre + along * (width * 0.5 - 0.05) - across * 0.1 + Vector3.UP * 0.2)
		al.add_child(_wire_mesh(a, b))
		al.add_child(_wire_mesh(b, Vector3(0, y + 0.02, 0)))
	if st == "armed":
		var c_local: Vector3 = inv * (centre + Vector3.UP * 0.9)
		# Local X runs along the wall (the alarm faces across it).
		var sensor: Area3D = al.add_sensor(Vector3(width, 1.6, 0.3), Transform3D(Basis.IDENTITY, c_local), PoiPieces.PLAYER_LAYER)
		sensor.body_entered.connect(al.on_body)
		al.add_interact_box(Vector3(0.3, 0.35, 0.3), Transform3D(Basis.IDENTITY, mi.position + Vector3(0, 0.08, 0.08)))
	root.add_child(al)
