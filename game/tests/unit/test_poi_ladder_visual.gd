extends GutTest
## A POI ladder is seen (the owner's playtest: every ladder in a building was invisible with the
## generated assets). The kit ladder's rails stand 0.09-0.16 m out along its local +Z (POI_KIT.md);
## PoiBuilder had turned that +Z into the wall, so the rails stood inside the wall slab. These build
## a real POI with a ladder against a wall and check its mesh is drawn, non-empty, opaque, and in
## the room in front of the wall's face: once with whatever kit_mesh gives (the stand-in here, which
## now has its rails where the generated ladder has them) and once with a mesh shaped like the
## generated one (rails out on +Z, brackets back to the wall plane at z = 0).

const WALL_FACE: float = 0.5 - PoiBuilder.WALL_T * 0.5

var _saved: Variant = null


func after_each() -> void:
	if _saved != null:
		PoiParts._meshes["ladder_3m"] = _saved
		_saved = null


func _build() -> PoiInstance:
	var raw: Dictionary = {"id": "t_ladder_vis", "name": "T", "tier": 1, "footprint": [12, 12],
		"style": {"floor_height": 0.0},
		"levels": [{"level": 0, "plan": ["AAA", "AAA", "AAA"], "rooms": {"A": {}}},
			{"level": 1, "plan": ["BBB", "BBB", "BBB"], "rooms": {"B": {}}}],
		"openings": [{"id": "front", "at": [1, 2], "side": "S", "type": "door", "state": "open"}],
		"ladders": [{"level": 0, "at": [1, 0], "side": "N", "hatch": true}],
		"route": [{"at": [1, 4]}, {"at": [1, 1]}, {"at": [1, 1], "level": 1}]}
	var d := PoiDef.new()
	assert_eq(d.parse(raw, &"poi", "test"), PackedStringArray(), "def parses")
	var inst: PoiInstance = PoiBuilder.build(PoiLayout.compile(d), &"t_ladder_vis")
	add_child_autofree(inst)
	return inst


func _ladder(inst: PoiInstance) -> PoiPieces.Ladder:
	for n: Node in inst.find_children("*", "StaticBody3D", true, false):
		if n is PoiPieces.Ladder:
			return n as PoiPieces.Ladder
	return null


## Checks the ladder's drawn meshes: at least one visible, non-empty, opaque, and every corner of
## each in front of the wall's face (toward the climber).
func _assert_seen(inst: PoiInstance) -> void:
	var lad: PoiPieces.Ladder = _ladder(inst)
	assert_not_null(lad, "the ladder is built")
	if lad == null:
		return
	var face: Vector3 = lad.face()
	var foot: Vector3 = lad.ends()[1]
	assert_gt(lad.global_basis.z.dot(face), 0.99, "the ladder's +Z (its rails' side) faces the climber")
	var drawn: int = 0
	for n: Node in lad.find_children("*", "MeshInstance3D", true, false):
		var mi: MeshInstance3D = n
		if not mi.is_visible_in_tree() or mi.mesh == null:
			continue
		var box: AABB = mi.mesh.get_aabb()
		assert_gt(box.size.x, 0.1, "wide")
		assert_gt(box.size.y, 2.5, "tall")
		assert_gt(box.size.z, 0.01, "deep")
		for s: int in mi.mesh.get_surface_count():
			var m: Material = mi.get_active_material(s)
			if m is BaseMaterial3D:
				assert_eq((m as BaseMaterial3D).transparency, BaseMaterial3D.TRANSPARENCY_DISABLED, "opaque")
		var xf: Transform3D = mi.global_transform
		var behind: float = -INF
		for i: int in 8:
			var p: Vector3 = xf * box.get_endpoint(i)
			# Metres from the cell's middle toward the wall (the wall's face is at WALL_FACE).
			behind = maxf(behind, (p - foot).dot(-face))
		assert_lt(behind, WALL_FACE + 0.005, "the ladder stands in the room, not in the wall (reaches %.3f m toward it)" % behind)
		drawn += 1
	assert_gt(drawn, 0, "a visible ladder mesh")


func test_ladder_is_drawn_in_front_of_its_wall() -> void:
	_assert_seen(_build())


func test_generated_shape_ladder_is_drawn_in_front_of_its_wall() -> void:
	# A mesh shaped like kit/ladder_3m from kit_stairs.build_ladder: rails 0.09-0.16 m out on +Z
	# (Blender -Y), the standoff brackets reaching back to the wall plane at z = 0.
	var am := ArrayMesh.new()
	var b := BoxMesh.new()
	b.size = Vector3(0.5, 3.0, 0.16)
	var src: Array = b.get_mesh_arrays()
	var v: PackedVector3Array = src[Mesh.ARRAY_VERTEX]
	for i: int in v.size():
		v[i] += Vector3(0, 1.5, 0.08)
	src[Mesh.ARRAY_VERTEX] = v
	am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, src)
	var mat := StandardMaterial3D.new()
	am.surface_set_material(0, mat)
	PoiParts.kit_mesh("ladder_3m")  # fill the cache, then stand the generated shape in for it
	_saved = PoiParts._meshes["ladder_3m"]
	PoiParts._meshes["ladder_3m"] = am
	_assert_seen(_build())
