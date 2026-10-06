extends GutTest
## Biome fog (ADR-0047): EnvironmentController tints the fog by the biomes round the camera (their
## `fog_tint` against the conifer forest's, hue only) and pools deeper, thicker ground fog in fens
## when the hour's fog gathers.

var _fc: Dictionary = {}


func before_all() -> void:
	_fc = Content.config(&"weather").get("fog", {}) as Dictionary


func _of(id: String) -> Array:
	var bd: BiomeDef = Content.get_def(&"biome", StringName(id)) as BiomeDef
	var ref := Color(str(_fc.get("biome_tint_reference", "#9aa59c")))
	return [EnvironmentController.fog_tint_mul(bd.fog_tint, ref) if bd != null else Color.WHITE, 1.0 if id == "fen" else 0.0]


func _lum(c: Color) -> float:
	return c.r * 0.2126 + c.g * 0.7152 + c.b * 0.0722


func test_the_reference_biome_leaves_the_fog_as_it_was() -> void:
	var t: Array = EnvironmentController.biome_fog_target(PackedStringArray(["conifer_forest", "conifer_forest", "conifer_forest", "conifer_forest", "conifer_forest"]), _of, _fc)
	var c: Color = t[0]
	assert_almost_eq(c.r, 1.0, 1.0e-4)
	assert_almost_eq(c.g, 1.0, 1.0e-4)
	assert_almost_eq(c.b, 1.0, 1.0e-4)
	assert_eq(float(t[1]), 0.0, "no fen")
	# Unknown ground (no region yet) is neutral too.
	var u: Array = EnvironmentController.biome_fog_target(PackedStringArray(["", "", "", "", ""]), _of, _fc)
	assert_eq(u[0], Color.WHITE)


func test_a_burn_warms_the_fog_and_a_fen_greys_it_green() -> void:
	var burn: Color = EnvironmentController.biome_fog_target(PackedStringArray(["burnt_forest", "burnt_forest", "burnt_forest", "burnt_forest", "burnt_forest"]), _of, _fc)[0]
	assert_gt(burn.r, burn.b, "dusty warm: more red than blue")
	assert_almost_eq(_lum(burn), 1.0, 0.02, "hue only: the sky and the sun set the brightness")
	var fen: Array = EnvironmentController.biome_fog_target(PackedStringArray(["fen", "fen", "fen", "fen", "fen"]), _of, _fc)
	var fc: Color = fen[0]
	assert_gt(fc.g, fc.r, "the fen's fog leans green")
	assert_almost_eq(float(fen[1]), 1.0, 1.0e-6, "all fen")
	# Standing at a fen's edge: part fen.
	var edge: Array = EnvironmentController.biome_fog_target(PackedStringArray(["fen", "meadow", "fen", "meadow", "meadow"]), _of, _fc)
	assert_almost_eq(float(edge[1]), 0.55, 1.0e-6, "the camera's own ground weighs most")


func test_a_fen_pools_its_ground_fog() -> void:
	var none: Vector2 = EnvironmentController.fen_pool(0.0, _fc)
	assert_eq(none, Vector2(1.0, 0.0), "outside fens the ground fog is as before")
	var full: Vector2 = EnvironmentController.fen_pool(1.0, _fc)
	assert_gt(full.x, 1.5, "thicker in a fen")
	assert_gt(full.y, 1.0, "and deeper")
	# It scales the hour's fog: at noon (none) it adds nothing; at dawn it is at its thickest.
	var noon: float = EnvironmentController.ground_fog_at(12.0, 6.0, 20.0, _fc)
	var dawn: float = EnvironmentController.ground_fog_at(6.0, 6.0, 20.0, _fc)
	assert_almost_eq(noon * full.x, 0.0, 1.0e-6, "no fen mist at noon")
	assert_gt(dawn * full.x, dawn, "more at dawn in a fen than elsewhere")
