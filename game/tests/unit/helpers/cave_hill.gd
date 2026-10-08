extends RefCounted
## A one-region synthetic world on a 21° hillside rising towards +X, with a REAL grotto
## (CavePlan.build through TerrainManager.place_cave) carved into it by the real volume jobs, plus
## a stand-in GameWorld that answers height_at / ground_below the way GameWorld does. Shared by
## the cave nav test and the cave AI rules test (CAVES_PLAN WS-C).

const REGION: float = 256.0
## tan(21°): grottos plan on hills of about 19° and up.
const SLOPE: float = 0.3839
const BASE_Y: float = 20.0
## Where the grotto is asked for (it settles within `search` m) and its seed.
const MOUTH := Vector2(-12.0, 16.0)
const SEED: int = 7


static func hill(x: float, _z: float) -> float:
	return BASE_Y + SLOPE * x


## Stands in for GameWorld: the terrain, height_at and ground_below (GameWorld's own bodies).
class HillWorld:
	extends Node3D
	var terrain: TerrainManager
	var player: Node3D = null
	var is_ready: bool = false

	func height_at(x: float, z: float) -> float:
		return terrain.height_at(x, z) if terrain != null else 0.0

	func ground_below(pos: Vector3) -> float:
		return terrain.ground_below(pos) if terrain != null else 0.0


static func world_def() -> WorldDef:
	var w := WorldDef.new()
	w.id = "cave_hill_test"
	w.cols = 1
	w.rows = 1
	w.region_size = REGION
	w.regions = {"a": {"id": "a", "cell": "A1"}}
	w.cells = {"A1": "a"}
	return w


static func region(w: WorldDef) -> RegionTerrain:
	var rt := RegionTerrain.new()
	rt.region_id = "a"
	rt.rect = w.region_rect("a")
	rt.spacing = 1.0
	var n: int = int(REGION) + 1
	rt.height = HeightField.create(rt.rect.position, 1.0, n, n, 0.0)
	for j: int in n:
		for i: int in n:
			rt.height.set_h(i, j, hill(rt.rect.position.x + i, rt.rect.position.y + j))
	rt.splat0.resize(n * n * 4)
	rt.splat1.resize(n * n * 4)
	rt.biome.resize(n * n)
	rt.vegmask.resize(n * n)
	rt.palette = TerrainComposer.DEFAULT_PALETTE
	rt.biome_ids = PackedStringArray(["meadow"])
	return rt


## The hill world (not set up yet: add `world` to the tree first, then call setup()).
static func make() -> HillWorld:
	var hw := HillWorld.new()
	hw.name = "HillWorld"
	var tm := TerrainManager.new()
	tm.name = "Terrain"
	tm.defer_far_tiles = true
	hw.terrain = tm
	return hw


## Sets the terrain up (the world must be in the tree).
static func setup(hw: HillWorld) -> void:
	hw.add_child(hw.terrain)
	var w: WorldDef = world_def()
	hw.terrain.setup(w, {"a": region(w)}, {})


## The real grotto, placed through TerrainManager.place_cave.
static func place_grotto(tm: TerrainManager, id: StringName = &"hill_grotto") -> CavePlan:
	var spec: Dictionary = {"style": "grotto", "mouth": [MOUTH.x, MOUTH.y], "heading": "uphill", "search": 12.0,
		"length": [20.0, 24.0], "seed": SEED, "region_id": "a", "region_rect": tm.world.region_rect("a")}
	return tm.place_cave(id, spec) as CavePlan


## Runs the volume's jobs to the end the way frames do (start under the cap, apply in budget).
static func drain(tm: TerrainManager, timeout_ms: int = 120000) -> bool:
	var until: int = Time.get_ticks_msec() + timeout_ms
	while not tm.volume.is_idle() and Time.get_ticks_msec() < until:
		tm.start_queued()
		tm.volume.pump(8.0)
		OS.delay_msec(1)
	return tm.volume.is_idle()


## The chamber's floor anchor (else the deepest tunnel anchor).
static func chamber_floor(plan: CavePlan) -> Vector3:
	var best: Vector3 = plan.mouth.origin
	for a: Dictionary in plan.anchors():
		if a["kind"] == &"chamber":
			return a["pos"]
		if a["kind"] == &"tunnel":
			best = a["pos"]
	return best


## Into the hill from the mouth (its -Z), flat.
static func into(plan: CavePlan) -> Vector3:
	var d: Vector3 = -plan.mouth.basis.z
	return Vector3(d.x, 0.0, d.z).normalized()
