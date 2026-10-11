class_name LadderLinks
extends RefCounted
## Navigation links up a building's ladders (TD-310) for Ezra alone: the Hollowed climb no ladders
## (a loft is a refuge, by design), so each link is on its own navigation layer (LAYER), which only
## the companion's agent adds to its own. A link joins the cell at a ladder's foot to the landing
## beside its hatch upstairs while the building is in the tree; CompanionMind climbs it when his
## path reaches it.

## Navigation layer 2: ladders. Regions and the window links stay on layer 1.
const LAYER: int = 1 << 1
## Path cost of taking a ladder (metres of walking): a stair nearby is still the way up.
const COST: float = 4.0

## Link RID -> {"ladder": PoiPieces.Ladder}.
static var _links: Dictionary = {}


## Creates the links for a building that just entered the tree; free them with `free_links`.
static func build(inst: Node3D, map: RID) -> Array[RID]:
	var out: Array[RID] = []
	if inst == null or not map.is_valid():
		return out
	for c: Node in inst.get_children():
		if c is PoiPieces.Ladder:
			var lad: PoiPieces.Ladder = c
			var e: Array = lad.ends()
			out.append(make(map, e[1], e[0], {"ladder": lad}))
	return out


## One two-way ladder link from `foot` to `top` on `map` (LAYER only).
static func make(map: RID, foot: Vector3, top: Vector3, info_d: Dictionary) -> RID:
	var rid: RID = NavigationServer3D.link_create()
	NavigationServer3D.link_set_map(rid, map)
	NavigationServer3D.link_set_start_position(rid, foot)
	NavigationServer3D.link_set_end_position(rid, top)
	NavigationServer3D.link_set_bidirectional(rid, true)
	NavigationServer3D.link_set_navigation_layers(rid, LAYER)
	NavigationServer3D.link_set_enter_cost(rid, COST)
	_links[rid] = info_d
	return rid


static func free_links(rids: Array[RID]) -> void:
	for rid: RID in rids:
		_links.erase(rid)
		NavigationServer3D.free_rid(rid)


## What a body met at a link: {} for a link that is not a ladder's.
static func info(rid: RID) -> Dictionary:
	return _links.get(rid, {})


## The climb from `from` (the end a body reached) over a ladder: the points it passes through,
## [at the rails' foot, at the rails' top, the far end]. Going down, the same reversed.
static func climb_path(lad: PoiPieces.Ladder, from: Vector3) -> Array[Vector3]:
	var e: Array = lad.ends()
	var top: Vector3 = e[0]
	var foot: Vector3 = e[1]
	# The climber's place on the rungs: off the rails toward the side it is climbed from.
	var rail: Vector3 = lad.global_position + lad.face() * 0.35
	var low: Vector3 = Vector3(rail.x, foot.y, rail.z)
	var high: Vector3 = Vector3(rail.x, top.y, rail.z)
	if from.distance_to(foot) <= from.distance_to(top):
		return [low, high, top]
	return [high, low, foot]
