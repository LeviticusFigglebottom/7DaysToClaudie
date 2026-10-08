extends SceneTree
func _initialize() -> void:
	await process_frame
	var world: WorldDef = WorldDef.load_from("res://world/main_map")
	var src: Array = []
	for rid: String in world.regions:
		src.append(TerrainComposer.get_or_compose(world, rid, 16.0))
	var t := Time.get_ticks_msec()
	var img: Image = WorldMap.shade(world.world_rect(), src, world.rivers, world.lakes, world.roads)
	print("shade ms ", Time.get_ticks_msec() - t, " ", img.get_size())
	img.save_png("/tmp/claude-0/sp/map.png")
	quit()
