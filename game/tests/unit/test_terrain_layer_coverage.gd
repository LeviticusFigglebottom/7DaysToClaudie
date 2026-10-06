extends GutTest
## Every terrain layer (data/materials/terrain_layers.json) has a stand-in colour, so the terrain
## draws it before `make assets` and in far views (TerrainTextures.FALLBACK_COLORS; ash and peat
## drew grey, TD-152), and a footstep sound set that exists in the sound catalog
## (Player.SURFACE_SOUNDS; unknown layers fell back to the forest floor's).

const LAYERS_JSON: String = "res://data/materials/terrain_layers.json"
const FOOTSTEP_SETS: PackedStringArray = ["forest_floor", "grass", "dirt", "gravel", "wood_floor", "concrete", "water", "leaves", "carpet", "metal"]
const PlayerScript := preload("res://src/player/player.gd")


func _layers() -> PackedStringArray:
	var j := JSON.new()
	assert_eq(j.parse(FileAccess.get_file_as_string(LAYERS_JSON)), OK, "terrain_layers.json parses")
	return PackedStringArray((j.data as Dictionary).get("layers", []))


func test_every_layer_has_a_fallback_colour() -> void:
	var layers: PackedStringArray = _layers()
	assert_true(layers.has("ash_char") and layers.has("peat"), "the burn's and the fen's layers are listed")
	for l: String in layers:
		assert_true(TerrainTextures.FALLBACK_COLORS.has(l), "%s has a stand-in colour" % l)


func test_every_layer_has_a_footstep_set() -> void:
	for l: String in _layers():
		var set: String = str(PlayerScript.SURFACE_SOUNDS.get(l, ""))
		assert_true(FOOTSTEP_SETS.has(set), "%s steps as %s, a generated footstep set" % [l, set])
	assert_eq(PlayerScript.SURFACE_SOUNDS["ash_char"], "dirt", "burnt soil steps as bare ground")
	assert_eq(PlayerScript.SURFACE_SOUNDS["peat"], "dirt", "peat as mud does")
