extends SceneTree
## Composes a region and writes inspection images (hillshade, biome, dominant splat, vegetation).
##   godot --headless --path game -s res://src/tools/cli/compose_region.gd -- \
##       [--world res://world/main_map] [--region d6_larch_hollow] [--spacing 1.0] [--out DIR] [--no-cache]

const LAYER_COLORS: Dictionary = {
	"forest_floor": Color(0.32, 0.22, 0.12), "moss_ground": Color(0.25, 0.36, 0.12), "grass_ground": Color(0.42, 0.52, 0.22),
	"dirt": Color(0.55, 0.42, 0.28), "mud": Color(0.3, 0.24, 0.18), "gravel": Color(0.6, 0.58, 0.54),
	"asphalt_cracked": Color(0.15, 0.15, 0.16), "sand": Color(0.82, 0.74, 0.55), "rock_cliff": Color(0.5, 0.5, 0.5),
}


func _initialize() -> void:
	await process_frame
	var a: PackedStringArray = OS.get_cmdline_user_args()
	var world_path: String = _arg(a, "--world", "res://world/main_map")
	var region_id: String = _arg(a, "--region", "d6_larch_hollow")
	var spacing: float = float(_arg(a, "--spacing", "1.0"))
	var out_dir: String = _arg(a, "--out", ProjectSettings.globalize_path("res://").path_join("../build/region_preview"))
	DirAccess.make_dir_recursive_absolute(out_dir)
	var world: WorldDef = WorldDef.load_from(world_path)
	var t0: int = Time.get_ticks_msec()
	var rt: RegionTerrain
	if a.has("--no-cache"):
		rt = TerrainComposer.compose(world, region_id, spacing, func(stage: String, t: float) -> void: print("  [%3d%%] %s (%d ms)" % [int(t * 100), stage, Time.get_ticks_msec() - t0]))
	else:
		rt = TerrainComposer.get_or_compose(world, region_id, spacing)
	print("composed %s in %d ms: %dx%d samples, hash %s" % [region_id, Time.get_ticks_msec() - t0, rt.height.width, rt.height.depth, rt.height.content_hash().substr(0, 16)])
	var hr: Vector2 = rt.height.min_max(0, 0, rt.height.width, rt.height.depth)
	print("height range %.1f .. %.1f m; water bodies %d; roads %d; bridges %d; placements %d" % [hr.x, hr.y, rt.water.size(), rt.roads.size(), rt.bridges.size(), rt.placements.size()])
	_write_images(rt, out_dir, hr)
	quit(0)


func _write_images(rt: RegionTerrain, out_dir: String, hr: Vector2) -> void:
	var n: int = rt.height.width
	var shade := Image.create(n, n, false, Image.FORMAT_RGB8)
	var biome := Image.create(n, n, false, Image.FORMAT_RGB8)
	var splat := Image.create(n, n, false, Image.FORMAT_RGB8)
	var veg := Image.create(n, n, false, Image.FORMAT_L8)
	var light := Vector3(-0.6, 0.7, -0.4).normalized()
	var biome_cols: Array[Color] = [Color(0.15, 0.3, 0.12), Color(0.3, 0.45, 0.6), Color(0.5, 0.5, 0.5), Color(0.7, 0.6, 0.4), Color(0.6, 0.7, 0.3), Color(0.45, 0.6, 0.3), Color(0.8, 0.3, 0.3), Color(0.3, 0.3, 0.8)]
	var water_level: Dictionary = {}
	for iz: int in n:
		for ix: int in n:
			var i: int = iz * n + ix
			var nrm: Vector3 = rt.height.grid_normal(ix, iz)
			var hv: float = rt.height.heights[i]
			var lit: float = clampf(nrm.dot(light) * 0.8 + 0.25, 0.0, 1.0)
			var elev: float = (hv - hr.x) / maxf(1.0, hr.y - hr.x)
			var base := Color(0.35 + elev * 0.4, 0.38 + elev * 0.35, 0.3 + elev * 0.3)
			shade.set_pixel(ix, iz, base * lit)
			biome.set_pixel(ix, iz, biome_cols[rt.biome[i] % biome_cols.size()] * (0.6 + lit * 0.5))
			var best: int = 0
			var bw: int = -1
			for c: int in 8:
				var wv: int = rt.splat0[i * 4 + c] if c < 4 else rt.splat1[i * 4 + c - 4]
				if wv > bw:
					bw = wv
					best = c
			var lname: String = rt.palette[best]
			splat.set_pixel(ix, iz, (LAYER_COLORS.get(lname, Color.MAGENTA) as Color) * (0.55 + lit * 0.6))
			veg.set_pixel(ix, iz, Color(rt.vegmask[i] / 255.0, 0, 0))
	# Water overlay (lakes + rivers) on the hillshade.
	for w: Dictionary in rt.water:
		if w["kind"] == "lake":
			var poly := PackedVector2Array()
			for p: Array in w["polygon"]:
				poly.append(Vector2(float(p[0]), float(p[1])))
			_fill_water(shade, rt, poly, float(w["level"]))
		else:
			var pts: Array = w["points"]
			for k: int in pts.size():
				var c := Vector2(float(pts[k][0]), float(pts[k][1]))
				var r: float = float(w["widths"][k]) * 0.5
				var lvl: float = float(w["levels"][k])
				for dz: int in range(-int(r) - 1, int(r) + 2):
					for dx: int in range(-int(r) - 1, int(r) + 2):
						var x: float = c.x + dx
						var z: float = c.y + dz
						var ix2: int = int((x - rt.rect.position.x) / rt.spacing)
						var iz2: int = int((z - rt.rect.position.y) / rt.spacing)
						if ix2 >= 0 and iz2 >= 0 and ix2 < n and iz2 < n and rt.height.heights[iz2 * n + ix2] < lvl:
							shade.set_pixel(ix2, iz2, Color(0.12, 0.25, 0.35))
	shade.save_png(out_dir.path_join("%s_hillshade.png" % rt.region_id))
	biome.save_png(out_dir.path_join("%s_biome.png" % rt.region_id))
	splat.save_png(out_dir.path_join("%s_splat.png" % rt.region_id))
	veg.save_png(out_dir.path_join("%s_veg.png" % rt.region_id))
	print("wrote images to %s" % out_dir)


func _fill_water(img: Image, rt: RegionTerrain, poly: PackedVector2Array, level: float) -> void:
	var n: int = rt.height.width
	var bb := Rect2(poly[0], Vector2.ZERO)
	for p: Vector2 in poly:
		bb = bb.expand(p)
	for iz: int in n:
		var z: float = rt.rect.position.y + iz * rt.spacing
		if z < bb.position.y or z > bb.end.y:
			continue
		for ix: int in n:
			var x: float = rt.rect.position.x + ix * rt.spacing
			if x < bb.position.x or x > bb.end.x:
				continue
			if rt.height.heights[iz * n + ix] < level and Geometry2D.is_point_in_polygon(Vector2(x, z), poly):
				img.set_pixel(ix, iz, Color(0.12, 0.25, 0.35))


static func _arg(a: PackedStringArray, key: String, default: String) -> String:
	var i: int = a.find(key)
	return a[i + 1] if i >= 0 and i + 1 < a.size() else default
