class_name CaveSites
extends RefCounted
## Where caves go (ADR-0056): shape seeds, region-feature caves, and mouth search on a slope.
## M0 stub: the interface only; the search lands with the full generator.


static func shape_seed(world_id: String, cave_id: String) -> int:
	return Ids.derive_seed(Ids.hash64(world_id), "cave:" + cave_id)


## The caves a region declares as features of type "cave", planned against its pristine heights.
static func from_region(world: WorldDef, rid: String, rt: RegionTerrain, cfg: Dictionary) -> CaveSet:
	var plans: Array = []
	if world == null or rt == null:
		return CaveSet.combined([], {})
	var hf: HeightField = rt.height
	var height_fn: Callable = func(x: float, z: float) -> float: return hf.sample(x, z)
	for f: Variant in world.region_data(rid).get("features", []):
		if f is Dictionary and str((f as Dictionary).get("type", "")) == "cave":
			var spec: Dictionary = (f as Dictionary).duplicate()
			spec["region_id"] = rid
			var s: int = int(spec["seed"]) if spec.has("seed") else shape_seed(world.id, str(spec.get("id", "")))
			plans.append(CavePlan.build(spec, s, height_fn, cfg))
	return CaveSet.combined(plans, {})


## {pos: Vector3, heading_deg: float} | {} (none found).
static func find_mouth(_height_fn: Callable, _area: Rect2, _seed: int, _opts: Dictionary) -> Dictionary:
	return {}


static func settle_mouth(_height_fn: Callable, _near: Vector2, _heading_hint: float, _radius: float, _opts: Dictionary) -> Dictionary:
	return {}
