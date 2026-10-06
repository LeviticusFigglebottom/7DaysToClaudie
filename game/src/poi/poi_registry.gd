class_name PoiRegistry
extends RefCounted
## Every building of a world, built or not (RWG v2 Phase 3, RWG_V2_PLAN §1.7): pure data, made on
## the loader thread from every region's placements (coarse ones too), so a streamed world knows
## where each building stands long before its region is composed at 1 m. Nothing is generated
## here: a town lot keeps its LotPicker resolution, and PoiManager turns it into a PoiDef (on a
## worker) only when the building comes within its build ring.
##
## The lots are chosen exactly as PoiManager._place_framework chose them when it built everything
## at load: a framework or town placement's resolved lots, without the reserved and empty ones, and
## for a town (one placement per region it touches, with that region's rect) only the lots whose
## centre lies in the rect, so each lot has exactly one owner region.
##
## Read on the main thread only once built (the loader hands it over when its thread is done).

const Lots := preload("res://src/poi/lot_picker.gd")

## Side of the lookup grid's cells (metres).
const CELL: float = 64.0

## Instance id (StringName) -> entry: {id, kind: "poi" | "lot", region, placement, def (StringName,
## "" for a generated building), res (a lot's LotPicker resolution), fxf (a poi's own transform; a
## lot's framework transform), center (Vector2, world), half (Vector2, half extents of its
## footprint box), yaw (radians, the box's turn), radius (half diagonal)}.
var entries: Dictionary = {}
## Region id -> Array of instance ids (StringName).
var by_region: Dictionary = {}
## Vector2i cell -> Array of instance ids whose box overlaps the cell.
var grid: Dictionary = {}


## The registry of a world's regions (rid -> RegionTerrain, any spacing: only the placements are
## read). `lots` caches LotPicker.resolve per framework placement id ([[res, PoiDef or null], ...]
## as WorldLoader keeps them, or [[res, null], ...]); missing ones are resolved and added. Safe on
## a worker thread (ContentDB.instance, no scene tree).
static func build(world: WorldDef, regions: Dictionary, lots: Dictionary, world_seed: int) -> PoiRegistry:
	var reg := PoiRegistry.new()
	for rid: String in regions:
		reg.add_region(world, rid, regions[rid] as RegionTerrain, lots, world_seed)
	return reg


func add_region(world: WorldDef, rid: String, rt: RegionTerrain, lots: Dictionary, world_seed: int) -> void:
	var db: Node = ContentDB.instance
	for pl: Dictionary in rt.placements:
		match str(pl.get("kind", "")):
			"poi":
				var size := Vector2(float(pl.get("size", [0, 0])[0]), float(pl.get("size", [0, 0])[1]))
				var xf: Transform3D = placement_xf(pl)
				var c: Vector3 = xf * Vector3(size.x * 0.5, 0.0, size.y * 0.5)
				_add({"id": StringName(str(pl["id"])), "kind": "poi", "region": rid, "placement": str(pl["id"]),
					"def": StringName(str(pl["def"])), "res": {}, "fxf": xf, "center": Vector2(c.x, c.z),
					"half": size * 0.5, "yaw": -deg_to_rad(float(pl.get("rotation", 0.0)))})
			"framework", "town":
				var fw: FrameworkDef = db.call(&"get_def", &"framework", StringName(str(pl["def"]))) as FrameworkDef if db != null else null
				if fw == null:
					continue
				var pid: String = str(pl["id"])
				if not lots.has(pid):
					var out: Array = []
					for res: Dictionary in Lots.resolve(fw, pid, world_seed):
						out.append([res, null])
					lots[pid] = out
				var fxf: Transform3D = placement_xf(pl)
				var only := Rect2()
				if pl.has("rect"):
					only = Rect2(float(pl["rect"][0]), float(pl["rect"][1]), float(pl["rect"][2]), float(pl["rect"][3]))
				var fyaw: float = -deg_to_rad(float(pl.get("rotation", 0.0)))
				for pair: Array in lots[pid]:
					var res2: Dictionary = pair[0]
					var l: Dictionary = res2["lot"]
					if str(res2["kind"]) in ["reserved", "empty"]:
						continue
					var lc: Vector2 = Lots.lot_center(l)
					var wc: Vector3 = fxf * Vector3(lc.x, 0.0, lc.y)
					if only.has_area() and not only.has_point(Vector2(wc.x, wc.z)):
						continue
					var half: Vector2
					var yaw: float = fyaw
					if l.has("frame"):
						half = Vector2(float(l["frame"][2]), float(l["frame"][3])) * 0.5
						yaw += deg_to_rad(float(l["frame"][4]))
					else:
						var r: Array = l.get("rect", [0, 0, 0, 0])
						half = Vector2(float(r[2]), float(r[3])) * 0.5
					_add({"id": StringName(str(res2["instance"])), "kind": "lot", "region": rid, "placement": pid,
						"def": StringName(str(res2.get("def_id", ""))) if str(res2["kind"]) == "authored" else &"",
						"res": res2, "fxf": fxf, "center": Vector2(wc.x, wc.z), "half": half, "yaw": yaw})
	if world != null and not by_region.has(rid):
		by_region[rid] = []


func _add(e: Dictionary) -> void:
	var id: StringName = e["id"]
	if entries.has(id):
		return
	var half: Vector2 = e["half"]
	e["radius"] = half.length()
	entries[id] = e
	var rid: String = e["region"]
	if not by_region.has(rid):
		by_region[rid] = []
	(by_region[rid] as Array).append(id)
	var c: Vector2 = e["center"]
	var r: float = float(e["radius"])
	for cz: int in range(int(floor((c.y - r) / CELL)), int(floor((c.y + r) / CELL)) + 1):
		for cx: int in range(int(floor((c.x - r) / CELL)), int(floor((c.x + r) / CELL)) + 1):
			var k := Vector2i(cx, cz)
			if not grid.has(k):
				grid[k] = []
			(grid[k] as Array).append(id)


## A region's 1 m composition has just attached: its own POI placements replace the coarse ones'
## transforms (a pad's height sampled at 16 m sits off the 1 m ground). Lots keep theirs: a lot's
## height comes from its frame, not from sampling.
func refresh_region(rid: String, rt: RegionTerrain) -> void:
	for pl: Dictionary in rt.placements:
		if str(pl.get("kind", "")) != "poi":
			continue
		var e: Dictionary = entries.get(StringName(str(pl["id"])), {})
		if not e.is_empty():
			e["fxf"] = placement_xf(pl)


## The building's transform once its def is known (a lot's depends on the building's footprint).
static func building_xf(e: Dictionary, pd: PoiDef) -> Transform3D:
	if str(e["kind"]) == "poi":
		return e["fxf"]
	var l: Dictionary = (e["res"] as Dictionary)["lot"]
	var local: Transform3D = Lots.lot_local_xf(l, pd.footprint) if l.has("frame") else rect_lot_xf(l, pd.footprint)
	return (e["fxf"] as Transform3D) * local


## The ids within `r` metres of p (box edge distance, nearest first): [[id, distance], ...].
func near(p: Vector2, r: float) -> Array:
	var out: Array = []
	var seen: Dictionary = {}
	for cz: int in range(int(floor((p.y - r) / CELL)), int(floor((p.y + r) / CELL)) + 1):
		for cx: int in range(int(floor((p.x - r) / CELL)), int(floor((p.x + r) / CELL)) + 1):
			for id: StringName in grid.get(Vector2i(cx, cz), []):
				if seen.has(id):
					continue
				seen[id] = true
				var d: float = distance_to(id, p)
				if d <= r:
					out.append([id, d])
	out.sort_custom(func(a: Array, b: Array) -> bool: return float(a[1]) < float(b[1]))
	return out


## Distance from p to an entry's footprint box (0 inside).
func distance_to(id: StringName, p: Vector2) -> float:
	var e: Dictionary = entries[id]
	# A turn by `yaw` about +Y is Vector2.rotated(-yaw) in the (x, z) plane; undo it.
	var local: Vector2 = (p - (e["center"] as Vector2)).rotated(float(e["yaw"]))
	var half: Vector2 = e["half"]
	var q := Vector2(maxf(absf(local.x) - half.x, 0.0), maxf(absf(local.y) - half.y, 0.0))
	return q.length()


## The building whose footprint covers p ("" when none): built or not, so nothing else (a wanderer
## spawn, a supply drop) lands where a building will stand.
func footprint_at(p: Vector2) -> StringName:
	for id: StringName in grid.get(Vector2i(int(floor(p.x / CELL)), int(floor(p.y / CELL))), []):
		if distance_to(id, p) <= 0.0:
			return id
	return &""


## A building's def id when known without generating it ("" for a generated building).
func def_id(id: StringName) -> StringName:
	return (entries.get(id, {}) as Dictionary).get("def", &"")


## A placement's transform: origin, turned by -rotation about +Y (PoiManager's convention).
static func placement_xf(pl: Dictionary) -> Transform3D:
	var o: Array = pl["origin"]
	return Transform3D(Basis(Vector3.UP, -deg_to_rad(float(pl.get("rotation", 0.0)))), Vector3(float(o[0]), float(o[1]), float(o[2])))


## A rect lot's POI frame in its framework: the footprint centred in the rect, its front (+Z)
## toward the lot's `facing`.
static func rect_lot_xf(l: Dictionary, footprint: Vector2i) -> Transform3D:
	var rect: Array = l["rect"]
	var center := Vector3(float(rect[0]) + float(rect[2]) * 0.5, 0.0, float(rect[1]) + float(rect[3]) * 0.5)
	var yaw: float = {"S": 0.0, "E": PI * 0.5, "N": PI, "W": -PI * 0.5}.get(str(l.get("facing", "S")), 0.0)
	var b := Basis(Vector3.UP, yaw)
	return Transform3D(b, center - b * Vector3(footprint.x * 0.5, 0.0, footprint.y * 0.5))
