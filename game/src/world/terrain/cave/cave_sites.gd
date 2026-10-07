class_name CaveSites
extends RefCounted
## Where caves go (ADR-0056): shape seeds, the caves a region declares as features, and the mouth
## search on a slope. Pure and thread-safe: heights come in as a Callable(x, z) -> float, config as
## a dictionary (data/config/caves.json); nothing here touches Content, Game or the scene tree.
##
## Headings are yaws in degrees in Godot's convention (Basis(Vector3.UP, yaw)): into the hill is
## (-sin yaw, 0, -cos yaw), so a slope rising towards +X has heading -90.

const DEFAULT_MIN_SLOPE: float = 18.0
## How far ahead of a mouth the ground must keep rising (m), and the share of the min-slope rise
## it must reach there: a bump in a meadow is no hillside to tunnel into.
const LOOK: float = 10.0
const RISE_SHARE: float = 0.6
## Hinted headings accept slopes whose uphill is within this of the hint (degrees).
const HINT_TOLERANCE: float = 60.0


## The seed of an authored cave's shape: per world, so a main-map cave is identical in every game.
static func shape_seed(world_id: String, cave_id: String) -> int:
	return Ids.derive_seed(Ids.hash64("caves|" + world_id), cave_id)


## A region feature {"type": "cave", "id", "style", "mouth": [x, z], "heading"?: "uphill" | deg,
## "search"?, "length"?: [a, b] | m, "seed"?} as a CavePlan spec; {} when it is malformed (no id,
## bad mouth, unknown style, bad heading), so callers can skip it and validators report it.
static func feature_spec(f: Variant, cfg: Dictionary) -> Dictionary:
	if not f is Dictionary:
		return {}
	var d: Dictionary = f
	if str(d.get("type", "")) != "cave" or str(d.get("id", "")) == "":
		return {}
	var m: Variant = d.get("mouth")
	if not (m is Array and (m as Array).size() == 2 and _is_num(m[0]) and _is_num(m[1])):
		return {}
	var styles: Dictionary = cfg.get("styles", CavePlan.DEFAULTS["styles"])
	var style: String = str(d.get("style", "grotto"))
	if not styles.has(style) or style.begins_with("_"):
		return {}
	var heading: Variant = d.get("heading", "uphill")
	if not (_is_num(heading) or str(heading) == "uphill"):
		return {}
	var spec: Dictionary = {"id": str(d["id"]), "style": style, "mouth": [float(m[0]), float(m[1])], "heading": heading}
	if d.has("search"):
		if not _is_num(d["search"]):
			return {}
		spec["search"] = float(d["search"])
	if d.has("length"):
		var l: Variant = d["length"]
		if not (_is_num(l) or (l is Array and (l as Array).size() == 2 and _is_num(l[0]) and _is_num(l[1]))):
			return {}
		spec["length"] = l
	if d.has("seed"):
		if not _is_num(d["seed"]):
			return {}
		spec["seed"] = int(d["seed"])
	return spec


static func _is_num(v: Variant) -> bool:
	return v is float or v is int


## The caves region `rid` declares, planned against its composed (pristine) heights and kept
## `region_margin` m inside it. Malformed features and plans that fail their checks are left out.
static func from_region(world: WorldDef, rid: String, rt: RegionTerrain, cfg: Dictionary) -> CaveSet:
	var plans: Array = []
	if world == null or rt == null or rt.height == null:
		return CaveSet.combined([], {})
	var hf: HeightField = rt.height
	var height_fn: Callable = hf.sample
	var rect: Rect2 = world.region_rect(rid)
	if rect.size == Vector2.ZERO:
		rect = rt.rect
	for f: Variant in world.region_data(rid).get("features", []):
		var spec: Dictionary = feature_spec(f, cfg)
		if spec.is_empty():
			continue
		spec["region_id"] = rid
		spec["region_rect"] = rect
		var s: int = int(spec["seed"]) if spec.has("seed") else shape_seed(world.id, str(spec["id"]))
		plans.append(CavePlan.build(spec, s, height_fn, cfg))
	return CaveSet.combined(plans, {})


## A mouth somewhere in `area`: seeded tries, each settled within opts.search (12) m. opts:
## min_slope_deg (18), search, tries (32), margin (0, kept off the area's edges), heading (yaw deg
## or "uphill"). Returns {pos: Vector3, heading_deg: float, slope_deg: float} or {}.
static func find_mouth(height_fn: Callable, area: Rect2, seed: int, opts: Dictionary) -> Dictionary:
	var inner: Rect2 = area.grow(-float(opts.get("margin", 0.0)))
	if inner.size.x <= 0.0 or inner.size.y <= 0.0:
		return {}
	var rng := RandomNumberGenerator.new()
	rng.seed = seed
	var hint: float = NAN
	var hv: Variant = opts.get("heading", "uphill")
	if _is_num(hv):
		hint = deg_to_rad(float(hv))
	var radius: float = float(opts.get("search", 12.0))
	for t: int in int(opts.get("tries", 32)):
		var near := Vector2(rng.randf_range(inner.position.x, inner.end.x), rng.randf_range(inner.position.y, inner.end.y))
		var got: Dictionary = settle_mouth(height_fn, near, hint, radius, opts)
		if not got.is_empty():
			var p: Vector3 = got["pos"]
			if inner.has_point(Vector2(p.x, p.z)):
				return got
	return {}


## The best mouth within `radius` m of `near`: a slope of at least opts.min_slope_deg whose ground
## keeps rising ahead, preferring the most hill ahead and then the nearest. heading_hint (radians,
## NAN = uphill) fixes the heading and accepts only slopes facing it. Candidates sit on a 2 m grid
## in a fixed order, so the result is deterministic. {pos, heading_deg, slope_deg} or {}.
static func settle_mouth(height_fn: Callable, near: Vector2, heading_hint: float, radius: float, opts: Dictionary) -> Dictionary:
	var min_slope: float = float(opts.get("min_slope_deg", DEFAULT_MIN_SLOPE))
	var min_grad: float = tan(deg_to_rad(min_slope))
	var hinted: bool = not is_nan(heading_hint)
	var hint_dir := Vector2(-sin(heading_hint), -cos(heading_hint)) if hinted else Vector2.ZERO
	var cos_tol: float = cos(deg_to_rad(HINT_TOLERANCE))
	var steps: int = int(floor(maxf(0.0, radius) / 2.0))
	var best: Dictionary = {}
	var best_score: float = -INF
	for gz: int in range(-steps, steps + 1):
		for gx: int in range(-steps, steps + 1):
			var off := Vector2(gx, gz) * 2.0
			if off.length() > radius + 0.001:
				continue
			var q: Vector2 = near + off
			var h: float = float(height_fn.call(q.x, q.y))
			# Gradient over a 2 m baseline (smooths the composer's 1 m sample steps).
			var g := Vector2(float(height_fn.call(q.x + 1.0, q.y)) - float(height_fn.call(q.x - 1.0, q.y)),
				float(height_fn.call(q.x, q.y + 1.0)) - float(height_fn.call(q.x, q.y - 1.0))) * 0.5
			var gl: float = g.length()
			if gl < min_grad:
				continue
			var up: Vector2 = g / gl
			var dir: Vector2 = up
			if hinted:
				if up.dot(hint_dir) < cos_tol:
					continue
				dir = hint_dir
			var ahead: Vector2 = q + dir * LOOK
			var rise: float = float(height_fn.call(ahead.x, ahead.y)) - h
			if rise < LOOK * min_grad * RISE_SHARE:
				continue
			var score: float = rise - 0.1 * off.length()
			if score > best_score:
				best_score = score
				var yaw: float = heading_hint if hinted else atan2(-dir.x, -dir.y)
				best = {"pos": Vector3(q.x, h, q.y), "heading_deg": rad_to_deg(yaw), "slope_deg": rad_to_deg(atan(gl))}
	return best
