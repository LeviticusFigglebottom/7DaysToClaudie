extends GutTest
## VolumeSurfacePaint (CAVES_PLAN WS-D): a converted column must look like the heightmap at the
## surface. On a flat column with a tunnel under it, the vertices on the old ground get R = 1 (the
## region's splat takes over in volume_terrain.gdshader) and the tunnel's walls, roof and floor
## R = 0; G marks the cave interior, more than 1.5 m under the ground. The worker job carries the
## colours, deterministically, and the installed mesh has them.

const Fakes := preload("res://tests/unit/helpers/fake_caves.gd")
const GROUND: float = 10.0
## A tunnel along X under the flat ground: air from y 4.5 to 7.5 (2.5 m of rock over it), z 6.5..9.5.
const TUNNEL_CENTER := Vector3(8.0, 6.0, 8.0)
const TUNNEL_HALF := Vector3(12.0, 1.5, 1.5)


class FlatTerrain:
	extends Node
	var textures: Variant = null
	var holes: TerrainHoles = null
	var caves: Object = null

	func base_height_at(_x: float, _z: float) -> float:
		return 10.0


static func _flat(_x: float, _z: float) -> float:
	return GROUND


func _job() -> Dictionary:
	var caves := Fakes.FakeCaveSet.new([Fakes.FakeCave.new(&"tunnel", TUNNEL_CENTER, TUNNEL_HALF)])
	return VolumeTerrain.run_job(Vector3i(0, 0, 0), _flat, null, caves, PackedByteArray(), PackedFloat32Array())


func test_weights_by_height_and_facing() -> void:
	assert_eq(VolumeSurfacePaint.surface(0.0, 1.0), 1.0, "on the ground, facing up")
	assert_eq(VolumeSurfacePaint.surface(0.5, 1.0), 0.0, "half a metre off it")
	assert_eq(VolumeSurfacePaint.surface(-0.5, 1.0), 0.0)
	assert_eq(VolumeSurfacePaint.surface(0.0, 0.3), 0.0, "a wall at the ground line")
	var mid: float = VolumeSurfacePaint.surface(0.3, 1.0)
	assert_true(mid > 0.0 and mid < 1.0, "a smooth falloff in height (%.3f)" % mid)
	var tilt: float = VolumeSurfacePaint.surface(0.0, 0.65)
	assert_true(tilt > 0.0 and tilt < 1.0, "and in facing (%.3f)" % tilt)
	assert_eq(VolumeSurfacePaint.interior(1.0), 0.0, "a metre down is not the cave yet")
	assert_eq(VolumeSurfacePaint.interior(3.0), 1.0)
	var c: PackedColorArray = VolumeSurfacePaint.weights(PackedVector3Array([Vector3(1, 0, 1), Vector3(1, -5, 1)]),
		PackedVector3Array([Vector3.UP, Vector3.UP]), Vector3(0, GROUND, 0), _flat)
	assert_eq(c[0], Color(1, 0, 0, 1))
	assert_eq(c[1], Color(0, 1, 0, 1), "a floor 5 m down is cave, not surface")


func test_flat_column_paints_the_top_and_not_the_tunnel() -> void:
	var res: Dictionary = _job()
	var verts: PackedVector3Array = res["vertices"]
	var normals: PackedVector3Array = res["normals"]
	var colors: PackedColorArray = res["colors"]
	assert_gt(verts.size(), 100)
	assert_eq(colors.size(), verts.size(), "a colour per vertex")
	var top: int = 0
	var bad_top: int = 0
	var walls: int = 0
	var bad_walls: int = 0
	var floors: int = 0
	var bad_floors: int = 0
	for i: int in verts.size():
		var y: float = verts[i].y
		var c: Color = colors[i]
		if absf(y - GROUND) < 0.05 and normals[i].y > 0.95:
			top += 1
			if not is_equal_approx(c.r, 1.0) or c.g != 0.0:
				bad_top += 1
		elif y < GROUND - 2.0:
			if absf(normals[i].y) < 0.3:
				walls += 1
				if c.r != 0.0 or c.g < 0.9:
					bad_walls += 1
			elif normals[i].y > 0.9:
				floors += 1
				if c.r != 0.0 or c.g != 1.0:
					bad_floors += 1
	assert_gt(top, 500, "the old ground is meshed")
	assert_eq(bad_top, 0, "and painted R=1 G=0 throughout")
	assert_gt(walls, 50, "the tunnel's walls are meshed")
	assert_eq(bad_walls, 0, "R=0 on the tunnel walls, G deep")
	assert_gt(floors, 20, "and its floor")
	assert_eq(bad_floors, 0, "an up-facing floor 5 m down is no surface")


func test_paint_is_deterministic() -> void:
	var a: PackedColorArray = _job()["colors"]
	var b: PackedColorArray = _job()["colors"]
	assert_eq(a.size(), b.size())
	assert_eq(a.to_byte_array(), b.to_byte_array(), "byte for byte")


func test_the_installed_mesh_carries_the_colours() -> void:
	var t := FlatTerrain.new()
	t.caves = Fakes.FakeCaveSet.new([Fakes.FakeCave.new(&"tunnel", TUNNEL_CENTER, TUNNEL_HALF)])
	add_child_autofree(t)
	var vol := VolumeTerrain.new()
	t.add_child(vol)
	vol.setup(t)
	vol.activate_column(Vector2i(0, 0), 0.0)
	vol.flush()
	var c: VolumeTerrain.VChunk = vol.chunks[Vector3i(0, 0, 0)]
	assert_not_null(c.mesh_node)
	var am: ArrayMesh = c.mesh_node.mesh
	var arr: Array = am.surface_get_arrays(0)
	var colors: PackedColorArray = arr[Mesh.ARRAY_COLOR]
	assert_eq(colors.size(), (arr[Mesh.ARRAY_VERTEX] as PackedVector3Array).size())
	var want: PackedColorArray = _job()["colors"]
	var worst: float = 0.0
	for i: int in mini(colors.size(), want.size()):
		worst = maxf(worst, maxf(absf(colors[i].r - want[i].r), absf(colors[i].g - want[i].g)))
	assert_lt(worst, 0.01, "the job's colours (stored as 8 bits)")
	assert_same(c.mesh_node.material_override, vol._material, "no region here: the shared material")
