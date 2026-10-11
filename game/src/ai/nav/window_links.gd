class_name WindowLinks
extends RefCounted
## Navigation links through a building's windows (TD-011): a window's sill (0.8-1.0 m) is above
## the nav bake's climb (0.5 m), so the mesh outside and the floor inside never join there and a
## Hollow hunting someone in a house with its doors shut could only paw at the walls. Each window
## whose floor lies near the ground outside (a ground floor; upper ones are drops, not climbs) gets
## a two-way link from 0.6 m outside its wall to 0.6 m inside, on the world's navigation map, while
## the building is in the tree. What's in the way costs: an open or smashed window little, glass a
## little more, boards most (so a door left open is still the way in), and a link is cheaper again
## once what was in it is broken. A body that reaches a link tears out what is in the window and
## climbs through (Enemy's VAULT state).

## Metres from the wall face to each end of a link (past a body's radius, on open floor).
const REACH: float = 0.6
## Highest ground outside, under or over the floor, that still makes a window a climb.
const CLIMB_BAND: float = 1.0
## Path cost of entering a link (in metres of walking), by what is in the window.
const COST_OPEN: float = 3.0
const COST_GLASS: float = 6.0
const COST_BOARDS: float = 16.0

## Link RID -> {"poi": PoiInstance, "opening": id, "sill": world y of the sill, "pieces": [Breakable]}.
static var _links: Dictionary = {}


## Creates the links for a building that just entered the tree; returns their RIDs (free them with
## `free_links` when it leaves).
static func build(inst: PoiInstance, map: RID, ground: Callable = Callable()) -> Array[RID]:
	var out: Array[RID] = []
	if inst == null or inst.layout == null or not map.is_valid():
		return out
	var lay: PoiLayout = inst.layout
	var pieces: Dictionary = {}
	for c: Node in inst.get_children():
		if c is PoiPieces.Breakable and (c as PoiPieces.Breakable).opening_id != "":
			var b: PoiPieces.Breakable = c
			if not pieces.has(b.opening_id):
				pieces[b.opening_id] = []
			(pieces[b.opening_id] as Array).append(b)
	var xf: Transform3D = inst.global_transform
	for op: Dictionary in lay.openings:
		if not PoiLayout.is_window(str(op["type"])):
			continue
		var ends: Array = ends_of(lay, op, xf)
		if ends.is_empty():
			continue
		var a: Vector3 = ends[0]
		var b2: Vector3 = ends[1]
		if ground.is_valid():
			# Outside ground too far under the floor (an upper storey, a raised porch) is a drop.
			var g: float = float(ground.call(a))
			if absf(g - a.y) > CLIMB_BAND:
				continue
			a.y = g
		out.append(make(map, a, b2, {"poi": inst, "opening": str(op["id"]), "sill": float(ends[2]),
			"pieces": pieces.get(str(op["id"]), [])}))
	return out


## One two-way window link between `a` and `b` on `map`; `info` as WindowLinks keeps it ("sill":
## world y the feet must clear, "pieces": what is in the window).
static func make(map: RID, a: Vector3, b: Vector3, info_d: Dictionary) -> RID:
	var rid: RID = NavigationServer3D.link_create()
	NavigationServer3D.link_set_map(rid, map)
	NavigationServer3D.link_set_start_position(rid, a)
	NavigationServer3D.link_set_end_position(rid, b)
	NavigationServer3D.link_set_bidirectional(rid, true)
	_links[rid] = info_d
	NavigationServer3D.link_set_enter_cost(rid, cost(info_d))
	return rid


static func free_links(rids: Array[RID]) -> void:
	for rid: RID in rids:
		_links.erase(rid)
		NavigationServer3D.free_rid(rid)


## A window's link changed (something in it broke): cheaper to path through now.
static func refresh(rid: RID) -> void:
	var info: Dictionary = _links.get(rid, {})
	if not info.is_empty():
		NavigationServer3D.link_set_enter_cost(rid, cost(info))


static func cost(info: Dictionary) -> float:
	var c: float = COST_OPEN
	for b: Variant in info["pieces"]:
		if b == null or not is_instance_valid(b) or (b as PoiPieces.Breakable).is_broken():
			continue
		c = maxf(c, COST_GLASS if (b as PoiPieces.Breakable).kind == "glass" else COST_BOARDS)
	return c


## What a body met at a link: {} for a link that is not a window's.
static func info(rid: RID) -> Dictionary:
	return _links.get(rid, {})


## The end of a link farther from `near` (the one a body reached).
static func far_end(rid: RID, near: Vector3) -> Vector3:
	var a: Vector3 = NavigationServer3D.link_get_start_position(rid)
	var b: Vector3 = NavigationServer3D.link_get_end_position(rid)
	return a if a.distance_to(near) > b.distance_to(near) else b


## The piece still whole in a window (boards first: they are outside the glass), or null.
static func blocker(info_d: Dictionary) -> Node3D:
	var glass: Node3D = null
	for b: Variant in info_d.get("pieces", []):
		if b == null or not is_instance_valid(b) or (b as PoiPieces.Breakable).is_broken():
			continue
		if (b as PoiPieces.Breakable).kind != "glass":
			return b
		glass = b
	return glass


## A window opening's link ends in world space: [outside, inside, sill y], each end REACH m off the
## wall at the floor of the opening's level ([] when its wall has no outside or inside to tell).
static func ends_of(lay: PoiLayout, op: Dictionary, xf: Transform3D) -> Array:
	var w: Dictionary = lay.walls.get(PoiLayout.edge_key(op["level"], op["axis"], op["edge"]), {})
	if w.is_empty():
		return []
	var e: Vector2i = op["edge"]
	var width: float = float(op["width"])
	var y: float = lay.level_y(int(op["level"]))
	var c: Vector3
	var n: Vector3
	if str(op["axis"]) == "h":
		c = Vector3(lay.origin.x + e.x + width * 0.5, y, lay.origin.y + e.y)
		n = Vector3(0, 0, 1)
	else:
		c = Vector3(lay.origin.x + e.x, y, lay.origin.y + e.y + width * 0.5)
		n = Vector3(1, 0, 0)
	# The empty side of the wall (PoiBuilder._openings' outside_sign): +n when `ra` holds nothing.
	var out_sign: float = 1.0 if (w.get("ra", []) as Array).is_empty() else -1.0
	var spec: Dictionary = PoiParts.OPENINGS.get(str(op["type"]), {})
	var sill: float = y + float(spec.get("sill", 0.9))
	var outside: Vector3 = xf * (c + n * out_sign * REACH)
	var inside: Vector3 = xf * (c - n * out_sign * REACH)
	return [outside, inside, (xf * Vector3(c.x, sill, c.z)).y]
