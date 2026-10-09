extends GutTest
## A random world's drop site stands in its own clearing (RwgGenerator: a 16 m `clearing` at the
## drop_site spawn): a player lays the first fire there (journal card 4), so no tree, rock or
## deadfall may stand within a campfire's reach of the drop on any world. The smoke's campfire
## stood by a felled tree at the forest's edge instead, and failed when generator 17 moved seed 7's
## drop 330 m (integration 02a8a60).

const GenSettings := preload("res://src/worldgen/rwg/world_gen_settings.gd")
const Worlds := preload("res://src/worldgen/rwg/rwg_worlds.gd")

## [seed, size]: the smoke's random world (seed 7, size 5) and two more.
const WORLDS: Array = [[7, 5], [21, 4], [1234, 4]]
## A campfire's footprint and then some, round the drop.
const CLEAR_M: float = 8.0


func test_nothing_stands_in_the_drop_clearing() -> void:
	VegetationScatter.warm()
	var checked: int = 0
	for spec: Array in WORLDS:
		var settings: RefCounted = GenSettings.resolve(&"standard", {"size": int(spec[1])}, int(spec[0]))
		var res: Dictionary = Worlds.ensure(settings, Callable(), false)
		assert_true(bool(res.get("ok", false)), "seed %d generates" % spec[0])
		if not bool(res.get("ok", false)):
			continue
		var world: WorldDef = WorldDef.load_from(str(res["dir"]))
		var d: Array = world.generator.get("drop_site", [])
		assert_eq(d.size(), 2, "seed %d has a drop site" % spec[0])
		if d.size() != 2:
			continue
		var drop := Vector2(float(d[0]), float(d[1]))
		var rid: String = world.region_at(drop.x, drop.y)
		var rt: RegionTerrain = TerrainComposer.compose(world, rid, 2.0)
		var hfn: Callable = func(x: float, z: float) -> float: return rt.height.sample(x, z)
		var near: Array = []
		for cz: int in range(floori((drop.y - CLEAR_M) / VegetationScatter.CHUNK), floori((drop.y + CLEAR_M) / VegetationScatter.CHUNK) + 1):
			for cx: int in range(floori((drop.x - CLEAR_M) / VegetationScatter.CHUNK), floori((drop.x + CLEAR_M) / VegetationScatter.CHUNK) + 1):
				# Trees, then bushes, rocks and deadfall (the layers with collision).
				var out: Dictionary = VegetationScatter.scatter_chunk(Vector2i(cx, cz), rt, world.seed, hfn, Callable(), 2)
				for layer: String in out:
					for inst: VegetationScatter.Instance in out[layer]:
						if Vector2(inst.pos.x, inst.pos.z).distance_to(drop) < CLEAR_M:
							near.append("%s at (%.1f, %.1f)" % [inst.species, inst.pos.x, inst.pos.z])
		assert_eq(near, [], "seed %d size %d: the drop at %s is clear" % [spec[0], spec[1], drop])
		checked += 1
	assert_eq(checked, WORLDS.size(), "every world checked")
