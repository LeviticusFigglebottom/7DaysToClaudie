class_name RegionRings
extends RefCounted
## The pure ring logic of region streaming (ADR-0038, RWG_V2_PLAN §1.2): from the regions' rects,
## the focus points (players), the heading, what is attached now and what is pinned, which regions
## to attach, detach and prefetch, nearest and most-ahead first. No threads, no nodes: the
## RegionStreamer acts on the plan, and tests drive it with plain rects.
##
## * A region is wanted within `load` m of any focus (rect distance), kept once attached until
##   beyond `unload` m (hysteresis: walking along a border never flickers), always when a pin
##   (the Hum's base) overlaps it.
## * Priority = distance − heading_weight × dot(heading, direction to the region's centre): the
##   regions ahead come first. Lower is sooner.
## * At most `max_attached` regions: pinned ones first, then by priority; the rest detach.
## * Prefetch (compose into the disk cache, not into memory): within `prefetch` m, reaching
##   `prefetch_ahead` m further along the heading, and not in the attached set.
## * Only built regions attach; the others stay coarse (the main map's unbuilt regions).

## Defaults of data/config/streaming.json "region".
const DEFAULTS: Dictionary = {"load": 640.0, "unload": 1100.0, "prefetch": 1400.0, "prefetch_ahead": 400.0,
	"heading_weight": 300.0, "max_attached": 9}

var load_r: float
var unload_r: float
var prefetch_r: float
var prefetch_ahead: float
var heading_weight: float
var max_attached: int


func _init(cfg: Dictionary = {}) -> void:
	load_r = float(cfg.get("load", DEFAULTS["load"]))
	unload_r = maxf(load_r, float(cfg.get("unload", DEFAULTS["unload"])))
	prefetch_r = maxf(load_r, float(cfg.get("prefetch", DEFAULTS["prefetch"])))
	prefetch_ahead = float(cfg.get("prefetch_ahead", DEFAULTS["prefetch_ahead"]))
	heading_weight = float(cfg.get("heading_weight", DEFAULTS["heading_weight"]))
	max_attached = maxi(1, int(cfg.get("max_attached", DEFAULTS["max_attached"])))


## regions: {rid: Rect2 (x/z)}; built: {rid: true} (those that may attach); focus: points (x/z
## used); heading: horizontal velocity or facing (zero = none); attached: {rid: true};
## pins: {key: Rect2}.
## Returns {"target": [rid] (what should be attached, by priority), "attach": [rid] (target not
## yet attached, by priority), "detach": [rid] (attached, no longer in target), "prefetch": [rid]
## (by priority), "priority": {rid: float}, "distance": {rid: float}}.
func plan(regions: Dictionary, built: Dictionary, focus: Array, heading: Vector3, attached: Dictionary, pins: Dictionary = {}) -> Dictionary:
	var h := Vector2(heading.x, heading.z)
	h = h.normalized() if h.length() > 0.01 else Vector2.ZERO
	var dist: Dictionary = {}
	var prio: Dictionary = {}
	var ahead: Dictionary = {}
	var pinned: Array = []
	var candidates: Array = []
	var prefetch: Array = []
	for rid: Variant in regions:
		var r: Rect2 = regions[rid]
		var d: float = INF
		var a: float = 0.0
		for f: Variant in focus:
			var p := Vector2((f as Vector3).x, (f as Vector3).z)
			var df: float = rect_distance(r, p)
			if df < d:
				d = df
				var to: Vector2 = r.get_center() - p
				a = h.dot(to.normalized()) if to.length() > 0.01 else 0.0
		dist[rid] = d
		ahead[rid] = a
		prio[rid] = d - heading_weight * a
		if not built.has(rid):
			continue
		var is_pinned: bool = false
		for k: Variant in pins:
			if (pins[k] as Rect2).intersects(r, true):
				is_pinned = true
				break
		if is_pinned:
			pinned.append(rid)
		elif d <= load_r or (attached.has(rid) and d <= unload_r):
			candidates.append(rid)
	var by_prio := func(x: Variant, y: Variant) -> bool:
		return float(prio[x]) < float(prio[y]) or (float(prio[x]) == float(prio[y]) and str(x) < str(y))
	pinned.sort_custom(by_prio)
	candidates.sort_custom(by_prio)
	var target: Array = pinned.slice(0, max_attached)
	for rid2: Variant in candidates:
		if target.size() >= max_attached:
			break
		target.append(rid2)
	var in_target: Dictionary = {}
	for t: Variant in target:
		in_target[t] = true
	var attach: Array = target.filter(func(x: Variant) -> bool: return not attached.has(x))
	var detach: Array = []
	for rid3: Variant in attached:
		if not in_target.has(rid3):
			detach.append(rid3)
	detach.sort_custom(func(x: Variant, y: Variant) -> bool: return float(prio.get(x, INF)) > float(prio.get(y, INF)))
	for rid4: Variant in regions:
		if in_target.has(rid4) or not built.has(rid4):
			continue
		var reach: float = prefetch_r + prefetch_ahead * maxf(0.0, float(ahead[rid4]))
		if float(dist[rid4]) <= reach:
			prefetch.append(rid4)
	prefetch.sort_custom(by_prio)
	return {"target": target, "attach": attach, "detach": detach, "prefetch": prefetch, "priority": prio, "distance": dist}


## Distance from a point to a rect (0 inside).
static func rect_distance(r: Rect2, p: Vector2) -> float:
	var dx: float = maxf(maxf(r.position.x - p.x, 0.0), p.x - r.end.x)
	var dz: float = maxf(maxf(r.position.y - p.y, 0.0), p.y - r.end.y)
	return Vector2(dx, dz).length()
