class_name WorldLoader
extends RefCounted
## Loads a world for play: parses WorldDef, composes built regions at 1 m and every other region
## at 16 m (far field), using the on-disk cache. Run `load_world()` on a worker thread and poll
## `progress` / `stage` from the main thread (loading screen).

var world: WorldDef
var detailed: Dictionary = {}
var coarse: Dictionary = {}
var progress: float = 0.0
var stage: String = ""
var done: bool = false
var error: String = ""
var _mutex := Mutex.new()


func load_world(world_dir: String, detail_spacing: float = 1.0, coarse_spacing: float = 16.0, only_regions: PackedStringArray = []) -> void:
	world = WorldDef.load_from(world_dir)
	if world == null:
		error = "cannot load world at %s" % world_dir
		done = true
		return
	var ids: Array = world.regions.keys()
	ids.sort()
	var total: int = ids.size()
	var k: int = 0
	for rid: String in ids:
		k += 1
		var built: bool = world.is_region_built(rid) and (only_regions.is_empty() or only_regions.has(rid))
		_set_stage("%s %s" % ["Shaping" if built else "Surveying", str(world.regions[rid].get("name", rid))], float(k - 1) / total)
		if built:
			var rt: RegionTerrain = TerrainComposer.get_or_compose(world, rid, detail_spacing)
			_mutex.lock()
			detailed[rid] = rt
			_mutex.unlock()
		else:
			var ct: RegionTerrain = TerrainComposer.get_or_compose(world, rid, coarse_spacing)
			_mutex.lock()
			coarse[rid] = ct
			_mutex.unlock()
	_set_stage("Ready", 1.0)
	done = true


func _set_stage(s: String, p: float) -> void:
	_mutex.lock()
	stage = s
	progress = p
	_mutex.unlock()
