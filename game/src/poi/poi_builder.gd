class_name PoiBuilder
extends RefCounted
## Builds a PoiInstance from a compiled PoiLayout: kit walls/floors/posts batched into MultiMeshes
## with per-instance finishes (kit_wall shader), one merged collision shell, doors / windows /
## barricades / ladders / pickups / trip lines as interactive pieces, stairs, porch, foundation,
## generated roof, authored + scattered props (set dressing), lights and decals.

const WALL_T: float = 0.16

var layout: PoiLayout
var root: PoiInstance
var shell: StaticBody3D
var _batches: Dictionary = {}
var _rng := RandomNumberGenerator.new()
var _decay: float = 0.4
var _route_cells: Dictionary = {}
var _occupied: Dictionary = {}


static func build(p_layout: PoiLayout, instance_id: StringName) -> PoiInstance:
	var b := PoiBuilder.new()
	b.layout = p_layout
	return b._build(instance_id)


func _build(instance_id: StringName) -> PoiInstance:
	root = PoiInstance.new()
	root.name = String(instance_id).replace("/", "_").replace(":", "_")
	root.setup(layout, instance_id)
	_rng.seed = Ids.hash64("poi:" + String(instance_id))
	var style: Dictionary = layout.style
	_decay = float(style.get("decay", 0.25 + 0.1 * layout.def.tier))
	shell = StaticBody3D.new()
	shell.name = "Shell"
	shell.collision_layer = 1
	shell.collision_mask = 0
	shell.set_meta(&"surface", "wood_floor")
	root.add_child(shell)
	root.shell = shell
	_route_cells = _route_corridor()
	_walls()
	_posts()
	_floors()
	_stairs_and_ladders()
	_openings()
	_exterior()
	_roof()
	_props()
	_scatter()
	_lights()
	_interior_probe()
	_pickups()
	_decals()
	_traps()
	_emit_batches()
	return root


# --- helpers ---------------------------------------------------------------------------------

## Whether the top of level `li` is roofed (a flat or pitched roof sits over every top level the
## RoofBuilder sees; an open top floor is the exception authors mark with roof "none").
func _roofed(_li: int) -> bool:
	return str((layout.style.get("roof", {}) as Dictionary).get("type", "gable")) != "none"

## Batches a kit piece or model ("@model") instance. Indoor instances go in their own batch,
## drawn with weather_exposure 0 so rain gloss and snow stay outside.
func _add(piece: String, xf: Transform3D, custom: Color = Color(0, 0, 0, 0), indoor: bool = false) -> void:
	var key: String = piece + ("|in" if indoor else "")
	if not _batches.has(key):
		_batches[key] = {"xf": [], "c": []}
	(_batches[key]["xf"] as Array).append(xf)
	(_batches[key]["c"] as Array).append(custom)


func _emit_batches() -> void:
	for key: String in _batches:
		var piece: String = key.trim_suffix("|in")
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
		mmi.name = "MM_" + key.replace("/", "_").replace("@", "").replace("|", "_")
		mmi.multimesh = mm
		if key.ends_with("|in"):
			mmi.set_instance_shader_parameter(&"weather_exposure", 0.0)
		root.add_child(mmi)


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


func _seed() -> float:
	return _rng.randf()


func _decay_v() -> float:
	return clampf(_decay + _rng.randf_range(-0.15, 0.2), 0.0, 1.0)


## Local transform of an edge's wall piece (length `span` edges, starting at edge cell `c`).
func _edge_xf(li: int, axis: String, c: Vector2i, span: int = 1) -> Transform3D:
	var y: float = layout.level_y(li)
	var o: Vector2 = layout.origin
	if axis == "h":
		return Transform3D(Basis.IDENTITY, Vector3(o.x + c.x + span * 0.5, y, o.y + c.y))
	return Transform3D(Basis(Vector3.UP, PI * 0.5), Vector3(o.x + c.x, y, o.y + c.y + span * 0.5))


func _route_corridor() -> Dictionary:
	var out: Dictionary = {}
	var v := PoiValidator.new()
	v.layout = layout
	v._run()
	for path: Array in v.paths:
		for node: Variant in path:
			if node is Array:
				out[PoiValidator.node_key(node[0], node[1])] = true
	return out


# --- walls -----------------------------------------------------------------------------------

func _walls() -> void:
	var done: Dictionary = {}
	var damaged_p: float = float(layout.style.get("damaged_walls", 0.04 * layout.def.tier))
	for key: String in layout.walls:
		if done.has(key):
			continue
		var w: Dictionary = layout.walls[key]
		var li: int = w["level"]
		var axis: String = w["axis"]
		var c: Vector2i = w["cell"]
		var op: Dictionary = w["opening"]
		var custom := Color(_finish(li, w["a"], "wall"), _finish(li, w["b"], "wall"), _decay_v(), _seed())
		if op.is_empty():
			var piece: String = "wall_1m"
			if not w["exterior"] and _rng.randf() < damaged_p:
				piece = "wall_1m_damaged"
			_add(piece, _edge_xf(li, axis, c), custom)
			_wall_collision(li, axis, c, 1, {})
			done[key] = true
			continue
		# Openings: handled once at their first edge.
		if op["edge"] != c:
			continue
		var spec: Dictionary = PoiParts.OPENINGS[op["type"]]
		var span: int = int(spec["len"])
		for k: int in span:
			var ek: Vector2i = c + (Vector2i(k, 0) if axis == "h" else Vector2i(0, k))
			done[PoiLayout.edge_key(li, axis, ek)] = true
		if str(spec["model"]) != "":
			_add(str(spec["model"]), _edge_xf(li, axis, c, span), custom)
		_wall_collision(li, axis, c, span, spec)


## Collision boxes for one wall piece: solid, or split around its opening.
func _wall_collision(li: int, axis: String, c: Vector2i, span: int, spec: Dictionary) -> void:
	var xf: Transform3D = _edge_xf(li, axis, c, span)
	var length: float = float(span)
	var h: float = PoiLayout.WALL_H
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


func _posts() -> void:
	for li: int in layout.level_ids:
		var lv: Dictionary = layout.levels[li]
		for r: int in int(lv["d"]) + 1:
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
				_add("post_corner", Transform3D(Basis.IDENTITY, p), Color(PoiParts.finish_index("wall", ext), PoiParts.finish_index("wall", ext), _decay_v(), _seed()))


# --- floors, ceilings ----------------------------------------------------------------------

func _floors() -> void:
	var hole_cells: Dictionary = {}
	for h: Dictionary in layout.holes:
		hole_cells[PoiValidator.node_key(h["level"], h["cell"])] = true
	for li: int in layout.level_ids:
		var well: Dictionary = layout.stairwell_cells(li)
		var y: float = layout.level_y(li)
		var lv: Dictionary = layout.levels[li]
		for r: int in int(lv["d"]):
			var run_start: int = -1
			for c: int in int(lv["w"]) + 1:
				var cell := Vector2i(c, r)
				var ch: String = layout.room_at(li, cell) if c < int(lv["w"]) else "."
				var solid: bool = layout.is_room(ch) and not well.has(cell) and not hole_cells.has(PoiValidator.node_key(li, cell))
				if layout.is_room(ch) and not well.has(cell):
					var below: String = layout.room_at(li - 1, cell) if layout.levels.has(li - 1) else "."
					var custom := Color(_finish(li, ch, "floor"), _finish(li - 1, below, "ceiling") if layout.is_room(below) else _finish(li, ch, "ceiling"), _decay_v(), _seed())
					var p := Vector3(layout.origin.x + c + 0.5, y, layout.origin.y + r + 0.5)
					_add("floor_1m_broken" if hole_cells.has(PoiValidator.node_key(li, cell)) else "floor_1m", Transform3D(Basis.IDENTITY, p), custom,
						layout.is_room(layout.room_at(li + 1, cell)) if layout.levels.has(li + 1) else _roofed(li))
					# Ceiling where nothing is built above.
					var above: String = layout.room_at(li + 1, cell) if layout.levels.has(li + 1) else "."
					if not layout.is_room(above):
						_add("floor_1m", Transform3D(Basis.IDENTITY, p + Vector3.UP * PoiLayout.STOREY), Color(0, _finish(li, ch, "ceiling"), _decay_v(), _seed()))
				if solid and run_start < 0:
					run_start = c
				elif not solid and run_start >= 0:
					var n: int = c - run_start
					_box(Vector3(n, 0.2, 1.0), Transform3D(Basis.IDENTITY, Vector3(layout.origin.x + run_start + n * 0.5, y - 0.1, layout.origin.y + r + 0.5)))
					run_start = -1


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
		_add("stairs_straight", Transform3D(basis, edge), Color(0, 0, _decay_v(), _seed()))
		_add("stairs_railing", Transform3D(basis, edge), Color(0, 0, _decay_v(), _seed()))
		_ramp(edge, edge + d3 * 4.0 + Vector3.UP * PoiLayout.STOREY, 1.0)
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
		if bool(l["hatch"]):
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
		var outside_sign: float = 1.0 if not layout.is_room(w["a"]) else -1.0
		var inside_sign: float = 1.0 if op["side"] in [0, 3] else -1.0
		var t: String = op["type"]
		if t.begins_with("door") and st != "missing":
			var leaf: String = str(op.get("model", "door_exterior" if exterior else "door_interior"))
			var hp: float = float(op["hp"]) if float(op["hp"]) > 0.0 else (900.0 if leaf == "door_metal" else (380.0 if exterior else 220.0))
			if span == 1:
				_door(op["id"], xf, Vector3(-0.43, 0, 0), 0.0, leaf, st, str(op["key"]), hp, inside_sign)
			else:
				_door(op["id"] + "_l", xf, Vector3(-0.85, 0, 0), 0.0, leaf, st, str(op["key"]), hp, inside_sign)
				_door(op["id"] + "_r", xf, Vector3(0.85, 0, 0), PI, leaf, st, str(op["key"]), hp, inside_sign)
			if st == "barricaded":
				_barricade(op["id"] + "_bar", xf, outside_sign if str(op.get("barricade", "boards")) == "boards" else -outside_sign,
					"boards_door" if str(op.get("barricade", "boards")) == "boards" else "barricade_furniture", 260.0)
		elif t.begins_with("window"):
			var pane: String = "window_glass_1m" if span == 1 else "window_glass_2m"
			var glass_state: String = root.piece_state(op["id"] + "_glass", "broken" if st in ["broken", "missing", "open"] else "closed")
			if st != "missing" and st != "open":
				_glass(op["id"] + "_glass", xf, pane, glass_state, float(spec["w"]), float(spec["h"]), float(spec["sill"]))
			if st == "boarded":
				_barricade(op["id"] + "_boards", xf, outside_sign, "boards_window_1m" if span == 1 else "boards_window_2m", 150.0, float(spec["sill"]))


func _door(id: String, wall_xf: Transform3D, hinge: Vector3, flip: float, leaf: String, st: String, key: String, hp: float, inside_sign: float) -> void:
	var d := PoiPieces.Door.new()
	d.poi = root
	d.op_id = id
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
	d.pivot.add_child(mi)
	d.leaf_local = Transform3D(Basis.IDENTITY, Vector3(0.41, 1.025, 0))
	d.leaf_shape = _box(Vector3(0.82, 2.05, 0.05), d.pivot.transform * d.leaf_local, d)
	d.leaf_shape.disabled = d.state == "broken"
	root.add_child(d)


func _glass(id: String, wall_xf: Transform3D, pane: String, st: String, w: float, h: float, sill: float) -> void:
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


func _barricade(id: String, wall_xf: Transform3D, side_sign: float, piece: String, hp: float, sill: float = 0.0) -> void:
	if root.piece_state(id, "intact") == "broken":
		return
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
	_box(size, Transform3D(Basis.IDENTITY, Vector3(0, size.y * 0.5, 0)), b)
	root.add_child(b)


# --- exterior: foundation, porch, chimney ----------------------------------------------------

func _exterior() -> void:
	var li0: int = 0 if layout.levels.has(0) else layout.level_ids.front()
	var fh: float = layout.floor_height
	if fh > 0.12:
		for key: String in layout.walls:
			var w: Dictionary = layout.walls[key]
			if int(w["level"]) != li0 or not w["exterior"]:
				continue
			var xf: Transform3D = _edge_xf(li0, w["axis"], w["cell"])
			xf.origin.y = -0.4
			var s: float = (fh + 0.4) / 0.6
			xf.basis = xf.basis.scaled(Vector3(1.0, s, 1.0))
			_add("foundation_1m", xf, Color(0, 0, _decay_v(), _seed()))
	var porch: Dictionary = layout.style.get("porch", {})
	if not porch.is_empty():
		_porch(porch, li0)
	var chim: Variant = layout.style.get("chimney", null)
	if chim is Array:
		var p := Vector3(layout.origin.x + float(chim[0]) + 0.5, 0.0, layout.origin.y + float(chim[1]) + 0.5)
		_add("chimney_brick", Transform3D(Basis.IDENTITY, p), Color(0, 0, _decay_v(), _seed()))
		_box(Vector3(0.8, 4.5 + layout.level_y(layout.level_ids.back()), 0.6), Transform3D(Basis.IDENTITY, p + Vector3.UP * (2.25 + layout.level_y(layout.level_ids.back()) * 0.5)))


func _porch(porch: Dictionary, li0: int) -> void:
	var side: int = PoiLayout.SIDES.get(str(porch.get("side", "S")), 2)
	var from: int = int(porch.get("from", 0))
	var to: int = int(porch.get("to", 3))
	var depth: int = int(porch.get("depth", 2))
	var lv: Dictionary = layout.levels[li0]
	var top: float = layout.floor_height
	var steps: Array = porch.get("steps", [])
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

func _roof() -> void:
	var roof: Dictionary = layout.style.get("roof", {"type": "gable"})
	var top_li: int = layout.level_ids.back()
	for li: int in layout.level_ids:
		if li < 0:
			continue
		var cells: Array[Vector2i] = []
		for c: Vector2i in layout.room_cells(li):
			if not layout.levels.has(li + 1) or not layout.is_room(layout.room_at(li + 1, c)):
				cells.append(c)
		if cells.is_empty():
			continue
		var r := Rect2i(cells[0], Vector2i.ONE)
		for c: Vector2i in cells:
			r = r.merge(Rect2i(c, Vector2i.ONE))
		var y: float = layout.level_y(li) + PoiLayout.STOREY
		var t: String = str(roof.get("type", "gable")) if li == top_li else "flat"
		if float(cells.size()) < float(r.size.x * r.size.y) * 0.6:
			t = "flat"
		var rect := Rect2(Vector2(layout.origin.x + r.position.x, layout.origin.y + r.position.y), Vector2(r.size))
		var built: Array = RoofBuilder.build(t, rect, y, roof)
		for item: Variant in built:
			if item is MeshInstance3D or item is MultiMeshInstance3D:
				root.add_child(item)
			elif item is Shape3D:
				var cs := CollisionShape3D.new()
				cs.shape = item
				shell.add_child(cs)


# --- props & set dressing ------------------------------------------------------------------------

func _prop_xf(p: Dictionary, pd: PropDef) -> Transform3D:
	var pos: Vector2 = p["pos"]
	var rot: float = float(p.get("rot", 0.0))
	var against: String = str(p.get("against", ""))
	if against != "" and PoiLayout.SIDES.has(against):
		var cell: Vector2i = p["cell"]
		var depth: float = pd.size.z
		match against:
			"N":
				pos.y = cell.y + WALL_T * 0.5 + depth * 0.5 + 0.01
				rot = 0.0 if not p.has("rot") else rot
			"S":
				pos.y = cell.y + 1.0 - WALL_T * 0.5 - depth * 0.5 - 0.01
				rot = 180.0 if not p.has("rot") else rot
			"W":
				pos.x = cell.x + WALL_T * 0.5 + depth * 0.5 + 0.01
				rot = 90.0 if not p.has("rot") else rot
			"E":
				pos.x = cell.x + 1.0 - WALL_T * 0.5 - depth * 0.5 - 0.01
				rot = -90.0 if not p.has("rot") else rot
	var y: float = layout.level_y(int(p["level"])) + float(p.get("y", 0.0))
	if pd.wall_mounted:
		y += float(p.get("height", 1.4))
	return Transform3D(Basis(Vector3.UP, deg_to_rad(rot)), Vector3(layout.origin.x + pos.x, y, layout.origin.y + pos.y))


func _props() -> void:
	var lr_char: String = str(layout.loot_room.get("room", ""))
	var lr_level: int = int(layout.loot_room.get("level", 0))
	for i: int in layout.props.size():
		var p: Dictionary = layout.props[i]
		var pd: PropDef = Content.get_def(&"prop", StringName(str(p.get("prop", "")))) as PropDef
		if pd == null:
			continue
		var cond: String = str(p.get("variant", layout.style.get("prop_condition", "worn")))
		var model: String = pd.model_for(cond)
		var xf: Transform3D = _prop_xf(p, pd)
		_occupied[PoiValidator.node_key(p["level"], p["cell"])] = true
		var cont: StringName = StringName(str(p.get("container", pd.container)))
		if cont != &"" and Content.get_def(&"container", cont) != null:
			var lp := PoiPieces.LootProp.new()
			lp.poi = root
			lp.prop = pd
			lp.cdef = Content.get_def(&"container", cont) as ContainerDef
			lp.container_id = StringName("c:%s:%d" % [root.instance_id, i])
			lp.tier = layout.def.tier
			lp.bonus = int(p["level"]) == lr_level and layout.room_at(p["level"], p["cell"]) == lr_char
			lp.key = str(p.get("key", ""))
			lp.transform = xf
			var mi := MeshInstance3D.new()
			mi.mesh = ModelLibrary.mesh(model, "box")
			lp.add_child(mi)
			_box(pd.size.max(Vector3(0.2, 0.2, 0.2)), Transform3D(Basis.IDENTITY, Vector3(0, pd.size.y * 0.5, 0)), lp)
			root.add_child(lp)
		else:
			_add("@" + model, xf, Color(0, 0, 0, 0), layout.is_room(layout.room_at(p["level"], p["cell"])))
			if pd.collision != "none":
				_box(pd.size.max(Vector3(0.05, 0.05, 0.05)), xf * Transform3D(Basis.IDENTITY, Vector3(0, pd.size.y * 0.5, 0)))
		if not pd.light.is_empty() and bool(p.get("lit", false)):
			_light_at(xf * Vector3(0, float((pd.light.get("offset", [0, pd.size.y, 0]) as Array)[1]), 0), pd.light)


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
}


func _scatter() -> void:
	var sc: Dictionary = layout.style.get("scatter", {})
	var density: float = float(sc.get("density", 0.35))
	if density <= 0.0:
		return
	var by_room: Dictionary = {}
	for pd: PropDef in Content.all(&"prop"):
		if not pd.has_tag("clutter") or pd.size.x * pd.size.z > 0.6:
			continue
		for room_type: String in (pd.rooms if not pd.rooms.is_empty() else PackedStringArray(["any"])):
			if not by_room.has(room_type):
				by_room[room_type] = []
			(by_room[room_type] as Array).append(pd)
	for li: int in layout.level_ids:
		var well: Dictionary = layout.stairwell_cells(li)
		for c: Vector2i in layout.room_cells(li):
			var k: String = PoiValidator.node_key(li, c)
			if _route_cells.has(k) or _occupied.has(k) or well.has(c):
				continue
			var room: Dictionary = layout.room_def(li, layout.room_at(li, c))
			var room_type: String = str(room.get("type", "any"))
			var pool: Array = by_room.get("any", []).duplicate()
			for tag: String in ROOM_TAGS.get(room_type, [room_type]):
				pool.append_array(by_room.get(tag, []))
			if pool.is_empty():
				continue
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


## SDFGI occludes the sky indoors, which leaves rooms near-black even at noon. An interior
## reflection probe over the plan gives the building its own ambient fill (scaled with daylight by
## EnvironmentController through the "interior_probe" group, so nights stay dark) and keeps sky
## reflections off indoor floors. The box stops just inside the outer walls so facades keep the
## outdoor lighting.
func _interior_probe() -> void:
	if layout.level_ids.is_empty():
		return
	var ext: Rect2 = layout.extent()
	var lo: float = layout.level_y(layout.level_ids[0]) - 0.2
	var hi: float = layout.level_y(layout.level_ids[-1]) + PoiLayout.STOREY
	var probe := ReflectionProbe.new()
	probe.name = "InteriorProbe"
	probe.interior = true
	probe.ambient_mode = ReflectionProbe.AMBIENT_COLOR
	probe.ambient_color = Color(0.86, 0.83, 0.78)
	probe.ambient_color_energy = 0.0
	probe.size = Vector3(maxf(0.5, ext.size.x - 0.1), hi - lo, maxf(0.5, ext.size.y - 0.1))
	probe.position = Vector3(ext.position.x + ext.size.x * 0.5, (lo + hi) * 0.5, ext.position.y + ext.size.y * 0.5)
	probe.blend_distance = 0.3
	probe.max_distance = maxf(probe.size.x, probe.size.z)
	probe.update_mode = ReflectionProbe.UPDATE_ONCE
	probe.add_to_group(&"interior_probe")
	root.add_child(probe)


func _light_at(pos: Vector3, l: Dictionary) -> void:
	var light: OmniLight3D = FlickerLight.new() if float(l.get("flicker", 0.0)) > 0.0 else OmniLight3D.new()
	if light is FlickerLight:
		(light as FlickerLight).flicker = float(l.get("flicker", 0.2))
	light.light_color = Color.html(str(l.get("color", "#ffcf96")))
	light.light_energy = float(l.get("energy", 1.0))
	light.omni_range = float(l.get("range", 6.0))
	light.shadow_enabled = bool(l.get("shadow", false))
	light.position = pos
	root.add_child(light)


func _lights() -> void:
	for l: Variant in layout.lights:
		if not l is Dictionary:
			continue
		var d: Dictionary = l
		var placed: Dictionary = layout._placed(d)
		var pos: Vector3 = layout.local_pos(placed["level"], placed["pos"]) + Vector3.UP * float(d.get("height", 2.3))
		_light_at(pos, d)


func _pickups() -> void:
	for i: int in layout.pickups.size():
		var p: Dictionary = layout.pickups[i]
		var pid: String = str(p.get("id", "pk%d" % i))
		if root.piece_state(pid, "") == "broken":
			continue
		var pk := PoiPieces.Pickup.new()
		pk.poi = root
		pk.pickup_id = pid
		pk.item = StringName(str(p.get("item", "")))
		pk.count = int(p.get("count", 1))
		pk.position = layout.local_pos(p["level"], p["pos"]) + Vector3.UP * float(p.get("y", 0.0))
		pk.rotation.y = deg_to_rad(float(p.get("rot", 0.0)))
		root.add_child(pk)


func _decals() -> void:
	for d: Variant in layout.decals:
		if not d is Dictionary:
			continue
		var path: String = "res://assets/generated/textures/decal_%s_albedo.png" % str(d.get("decal", ""))
		if not ResourceLoader.exists(path):
			continue
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
		var tid: String = str(t.get("id", "trap%d" % i))
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
			continue
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
