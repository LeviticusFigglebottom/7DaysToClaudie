class_name BridgeBuilder
extends Node3D
## Builds the road bridges the terrain composer leaves room for (RegionTerrain.bridges: the deck
## height and the two ends of each span, where the road ramps meet it). Generated kit pieces are
## instanced along the chord from end to end: 8 m deck sections (asphalt, concrete slab, steel
## girders, guardrails) and two-column piers where the ground below leaves room. Boxes stand in
## before `make assets`. One static body carries the deck, curbs and guardrails, plus the piers.

const DECK_MODEL: String = "props/bridge_deck"
const PIER_MODEL: String = "props/bridge_pier"
## Section length and width the kit models are authored at (props_ext_street.py BRIDGE_*).
const SECTION: float = 8.0
const MODEL_WIDTH: float = 9.0
const PIER_SPACING: float = 22.0
## Underside of the girders below the road surface; a pier needs this much clearance plus a metre.
const DEPTH: float = 1.28

var world: Node
## Built spans: [{"from": Vector3, "to": Vector3, "width": float}] (deck-surface ends).
var spans: Array[Dictionary] = []


func setup_world(w: Node) -> void:
	world = w
	var seen: Dictionary = {}
	var terrain: TerrainManager = w.terrain
	var all: Array = []
	for rid: String in terrain.regions:
		all.append(terrain.regions[rid])
	for rid: String in terrain.coarse:
		all.append(terrain.coarse[rid])
	for rt: RegionTerrain in all:
		for b: Dictionary in rt.bridges:
			var f: Array = b["from"]
			var t: Array = b["to"]
			# The same span is recorded by every region the road passes through.
			var key: String = "%s:%d_%d" % [str(b.get("road", "")), roundi(float(f[0])), roundi(float(f[2]))]
			if seen.has(key):
				continue
			seen[key] = true
			_build(Vector3(float(f[0]), float(f[1]), float(f[2])), Vector3(float(t[0]), float(t[1]), float(t[2])), float(b.get("width", MODEL_WIDTH)))


func _build(a: Vector3, b: Vector3, width: float) -> void:
	var flat := Vector3(b.x - a.x, 0.0, b.z - a.z)
	var length: float = flat.length()
	if length < 1.0:
		return
	var dir: Vector3 = flat / length
	b.y = a.y
	spans.append({"from": a, "to": b, "width": width})
	var basis := Basis(dir, Vector3.UP, dir.cross(Vector3.UP))
	var root := Node3D.new()
	root.name = "Bridge_%d_%d" % [roundi(a.x), roundi(a.z)]
	add_child(root)
	# Deck sections stretched a little so a whole number of them spans the gap exactly.
	var n: int = maxi(1, ceili(length / SECTION))
	var stretch: float = length / (n * SECTION)
	var xfs: Array[Transform3D] = []
	for k: int in n:
		var c: Vector3 = a + dir * (length * (k + 0.5) / n)
		xfs.append(Transform3D(basis.scaled_local(Vector3(stretch, 1.0, width / MODEL_WIDTH)), c))
	root.add_child(_instances(ModelLibrary.mesh(DECK_MODEL, "box") if ModelLibrary.has_model(DECK_MODEL) else _fallback_deck(), xfs))
	# Piers where the ground under the deck leaves room for the girders plus a metre.
	var pier_xfs: Array[Transform3D] = []
	var m: int = int(length / PIER_SPACING)
	for k: int in range(1, m + 1):
		var p: Vector3 = a + dir * (length * k / (m + 1))
		if world.height_at(p.x, p.z) < a.y - DEPTH - 1.0:
			pier_xfs.append(Transform3D(basis.scaled_local(Vector3(1.0, 1.0, width / MODEL_WIDTH)), p))
	if not pier_xfs.is_empty():
		root.add_child(_instances(ModelLibrary.mesh(PIER_MODEL, "box") if ModelLibrary.has_model(PIER_MODEL) else _fallback_pier(), pier_xfs))
	root.add_child(_body(a, b, dir, width, pier_xfs))


func _instances(mesh: Mesh, xfs: Array[Transform3D]) -> MultiMeshInstance3D:
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.mesh = mesh
	mm.instance_count = xfs.size()
	for i: int in xfs.size():
		mm.set_instance_transform(i, xfs[i])
	var mmi := MultiMeshInstance3D.new()
	mmi.multimesh = mm
	mmi.visibility_range_end = 900.0
	return mmi


## Deck slab (top at the road surface), curbs and guardrails; one box per pier column pair.
func _body(a: Vector3, b: Vector3, dir: Vector3, width: float, piers: Array[Transform3D]) -> StaticBody3D:
	var body := StaticBody3D.new()
	body.name = "Collision"
	body.collision_layer = 1
	body.collision_mask = 0
	body.set_meta(&"surface", "concrete")
	var length: float = a.distance_to(b)
	var mid: Vector3 = (a + b) * 0.5
	var basis := Basis(dir, Vector3.UP, dir.cross(Vector3.UP))
	var side: Vector3 = dir.cross(Vector3.UP)
	_add_box(body, Transform3D(basis, mid - Vector3.UP * 0.2), Vector3(length, 0.4, width))
	for s: float in [-1.0, 1.0]:
		# curb + guardrail as one wall along each edge (1.05 m above the road)
		_add_box(body, Transform3D(basis, mid + side * s * (width * 0.5 - 0.25) + Vector3.UP * 0.45), Vector3(length, 1.1, 0.5))
	for xf: Transform3D in piers:
		var h: float = 14.0
		_add_box(body, Transform3D(basis, xf.origin - Vector3.UP * (DEPTH + 1.0 + h * 0.5)), Vector3(1.0, h, width * 0.62))
	return body


func _add_box(body: StaticBody3D, xf: Transform3D, size: Vector3) -> void:
	var cs := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = size
	cs.shape = box
	cs.transform = xf
	body.add_child(cs)


## Deck surfaces the navigation tiles add as walkable ground (tile rects in world XZ).
func nav_faces_in_rect(r: Rect2) -> PackedVector3Array:
	var out := PackedVector3Array()
	for sp: Dictionary in spans:
		var a: Vector3 = sp["from"]
		var b: Vector3 = sp["to"]
		var half: float = float(sp["width"]) * 0.5 - 0.5
		var side: Vector3 = (b - a).normalized().cross(Vector3.UP) * half
		var box := Rect2(Vector2(minf(a.x, b.x), minf(a.z, b.z)), Vector2.ZERO).expand(Vector2(maxf(a.x, b.x), maxf(a.z, b.z))).grow(half)
		if not box.intersects(r):
			continue
		var p0: Vector3 = a - side
		var p1: Vector3 = b - side
		var p2: Vector3 = b + side
		var p3: Vector3 = a + side
		out.append_array(PackedVector3Array([p0, p1, p2, p0, p2, p3]))
	return out


# --- Stand-ins before `make assets` ---------------------------------------------------------------

func _fallback_deck() -> Mesh:
	var m := BoxMesh.new()
	m.size = Vector3(SECTION, 0.4, MODEL_WIDTH)
	return _shifted(m, Vector3(0.0, -0.2, 0.0), Color(0.42, 0.42, 0.4))


func _fallback_pier() -> Mesh:
	var m := BoxMesh.new()
	m.size = Vector3(1.0, 14.0, MODEL_WIDTH * 0.62)
	return _shifted(m, Vector3(0.0, -DEPTH - 8.0, 0.0), Color(0.5, 0.5, 0.48))


static func _shifted(m: PrimitiveMesh, offset: Vector3, col: Color) -> Mesh:
	var st := SurfaceTool.new()
	st.create_from(m, 0)
	var arr: Array = st.commit_to_arrays()
	var v: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
	for i: int in v.size():
		v[i] += offset
	arr[Mesh.ARRAY_VERTEX] = v
	var out := ArrayMesh.new()
	out.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
	var mat := StandardMaterial3D.new()
	mat.albedo_color = col
	out.surface_set_material(0, mat)
	return out
