extends Node
## Keeps the buildings' interior reflection probes within the renderer's reflection atlas: only the
## probes nearest the camera stay visible.
##
## The atlas has 64 slots (rendering/reflections/reflection_atlas/reflection_count), and every
## visible probe whose box is in view takes one. Past 64 the renderer logs "reflection probe atlas
## index invalid", draws with null framebuffers, and then crashes indexing the atlas at -1. That
## was the first player's crash on reaching Pell's Crossing. PoiBuilder gives each building up to
## MAX_PROBES probes, and PoiManager builds every building of the loaded regions at load, so a town
## holds well over a hundred (TD-044).
##
## Only the fill of rooms the player can see into matters, and those are the near ones; a far
## building looks the same without its probes. The MAX_VISIBLE nearest are shown. A probe already
## shown keeps its slot while it ranks within KEEP_VISIBLE, so walking down a street does not flip
## the probes at the edge on and off (a probe shown again renders its cube map again). Probes that
## enter the tree are capped straight away, before the next ranking, so building a town never
## shows more than KEEP_VISIBLE even for a frame.

## Probes shown nearest the camera at each ranking.
const MAX_VISIBLE: int = 32
## Hard cap on visible probes, under the atlas's 64 slots with room for others.
const KEEP_VISIBLE: int = 48
## Seconds between rankings.
const INTERVAL: float = 0.25
const GROUP: StringName = &"interior_probe"

var _t: float = 0.0
## Probes visible now (kept current between rankings as probes enter and leave the tree).
var _shown: int = 0


func _ready() -> void:
	get_tree().node_added.connect(_on_node_added)
	get_tree().node_removed.connect(_on_node_removed)
	for n: Node in get_tree().get_nodes_in_group(GROUP):
		_on_node_added(n)


func _exit_tree() -> void:
	if get_tree().node_added.is_connected(_on_node_added):
		get_tree().node_added.disconnect(_on_node_added)
	if get_tree().node_removed.is_connected(_on_node_removed):
		get_tree().node_removed.disconnect(_on_node_removed)


func _process(delta: float) -> void:
	_t -= delta
	if _t > 0.0:
		return
	_t = INTERVAL
	var cam: Camera3D = get_viewport().get_camera_3d()
	if cam != null:
		update(cam.global_position)


## Shows the probes nearest `eye` (MAX_VISIBLE, plus those already shown that still rank within
## KEEP_VISIBLE) and hides the rest. Returns how many are visible.
func update(eye: Vector3) -> int:
	var ranked: Array = []
	for n: Node in get_tree().get_nodes_in_group(GROUP):
		var p := n as ReflectionProbe
		if p != null and p.is_inside_tree():
			ranked.append([box_distance(p, eye), p])
	ranked.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) < float(b[0]))
	_shown = 0
	for i: int in ranked.size():
		var p: ReflectionProbe = ranked[i][1]
		var show: bool = i < MAX_VISIBLE or (i < KEEP_VISIBLE and p.visible)
		if p.visible != show:
			p.visible = show
		if show:
			_shown += 1
	return _shown


## Visible interior probes right now.
func shown() -> int:
	return _shown


## Distance from `eye` to the probe's box (zero inside it): a long hall counts as near from either
## end, where its centre would not.
static func box_distance(p: ReflectionProbe, eye: Vector3) -> float:
	var local: Vector3 = p.global_transform.affine_inverse() * eye
	return (local.abs() - p.size * 0.5).max(Vector3.ZERO).length()


func _on_node_added(n: Node) -> void:
	if not n.is_in_group(GROUP) or not (n is ReflectionProbe):
		return
	var p := n as ReflectionProbe
	if not p.visible:
		return
	if _shown >= KEEP_VISIBLE:
		p.visible = false
	else:
		_shown += 1


func _on_node_removed(n: Node) -> void:
	if n.is_in_group(GROUP) and n is ReflectionProbe and (n as ReflectionProbe).visible:
		_shown = maxi(_shown - 1, 0)
