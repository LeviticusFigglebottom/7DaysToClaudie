extends Node
## Keeps the buildings' interior reflection probes within the renderer's reflection atlas, and has
## the room the player is in render first: only the probes nearest the camera are in the scene.
##
## The atlas has 64 slots (rendering/reflections/reflection_atlas/reflection_count). Past 64 the
## renderer logs "reflection probe atlas index invalid", draws with null framebuffers, and then
## crashes indexing the atlas at -1. That was the first player's crash on reaching Pell's Crossing.
## PoiBuilder gives each building up to MAX_PROBES probes, and PoiManager builds every building of
## the loaded regions at load, so a town holds well over a hundred (TD-044).
##
## Only the fill of rooms the player can see into matters, and those are the near ones; a far
## building looks the same without its probes. The MAX_VISIBLE nearest are live. A probe already
## live stays so while it ranks within KEEP_VISIBLE, so walking down a street does not flip the
## probes at the edge on and off. Probes enter parked and go live only when a ranking reaches
## them, nearest first, so building a town neither overfills the atlas nor queues renders for
## rooms far from the player.
##
## How Godot 4.7.2 handles these probes (servers/rendering/renderer_scene_cull.cpp and
## renderer_rd/storage_rd/light_storage.cpp) decides how a far probe is switched off:
## * A probe takes an atlas slot the first time it renders and keeps it until its instance leaves
##   its scenario or is freed. Hiding it (`visible = false`) keeps the slot. When the atlas is full
##   the least recently used slot should be reused, but that code never picks one. The probe lab
##   (70 rooms, one probe visible at a time) crashed exactly as the player did after the 64th room.
## * Detaching the instance's base (`RenderingServer.instance_set_base`) frees the slot, but the
##   probe never renders again once the base is back.
## * So a far probe is parked: taken out of the scene tree, which takes its instance out of the
##   scenario and frees its slot. Put back, it renders anew; the lab's 70 rooms all lit, with no
##   atlas errors. While parked the budget holds it; if its building leaves the tree meanwhile,
##   the probe goes back to the building (out of the tree, or freed with it).
## * UPDATE_ONCE probes render one at a time, in the renderer's own order: all six faces in one
##   frame, then one roughness layer a frame (RENDER_FRAMES in all). Until a probe's layers are done
##   its room has no interior fill and reads near-black under SDFGI (TD-134). A ranking puts back at
##   most `show_per_rank` probes, nearest first, and a jump ranks at once, so the room you're in
##   renders first; `focus()` parks all but the nearest few for a capture that can't wait.
## * Leaving the scenario frees a probe's slot but leaves it in the renderer's queue. When the
##   queue reaches it, the renderer logs `Parameter "scenario" is null` and drops it, a frame lost
##   per stale entry (agent W's biome renders logged 22 after two jumps). So a ranking puts back
##   more probes only once the last ones have nearly had their turn, and doesn't park a probe
##   before its turn has come.
## * Never switch these probes to UPDATE_ALWAYS. The first ALWAYS probe clears the whole atlas
##   (`_reflection_atlas_clear`), which wipes every probe's cube map, and leaves the atlas at
##   real-time quality.

## Probes live nearest the camera at each ranking.
const MAX_VISIBLE: int = 32
## Hard cap on live probes, under the atlas's 64 slots with room for others.
const KEEP_VISIBLE: int = 48
## Seconds between rankings.
const INTERVAL: float = 0.25
const GROUP: StringName = &"interior_probe"
## Probes put back per ranking. Eight a second roughly matches how fast a GPU renders them at 60 fps
## (RENDER_FRAMES each).
const SHOW_PER_RANK: int = 2
## Frames one UPDATE_ONCE probe takes to render: its faces, then the sky's roughness layers
## (rendering/reflections/sky_reflections/roughness_layers is 8 by default).
const RENDER_FRAMES: int = 9
## Metres the eye may move between rankings before it ranks at once (a teleport, a respawn).
const JUMP: float = 24.0

## Probes put back per ranking (SHOW_PER_RANK; tests raise it to check the ranking alone).
var show_per_rank: int = SHOW_PER_RANK
## The drawn-frame clock the render queue runs on (tests step a fake one).
var frames: Callable = Callable(Engine, &"get_frames_drawn")
var _t: float = 0.0
var _last_eye := Vector3(INF, INF, INF)
## Every probe the budget manages, live or parked.
var _probes: Dictionary = {}
## Parked probes -> the instance id of the node they were taken from (their building).
var _homes: Dictionary = {}
## Building instance id -> its parked probes.
var _parked: Dictionary = {}
## New probes waiting to be parked at the end of the frame (they can't leave the tree while it adds
## them).
var _to_park: Array[ReflectionProbe] = []
## The drawn frame by which every probe put back so far has had its turn to render.
var _rendered_by: int = 0
## Probes put back -> the drawn frame by which each has had its turn; until then it may still be
## in the renderer's queue, so it isn't parked.
var _due: Dictionary = {}


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
	# Parked probes belong to no tree: send each home, or free it with its building gone.
	for hid: Variant in _parked.keys():
		_send_home(int(hid))


func _process(delta: float) -> void:
	var cam: Camera3D = get_viewport().get_camera_3d()
	if cam != null and due(cam.global_position, delta):
		update(cam.global_position)


## Whether to rank now: every INTERVAL, or at once when the eye jumped JUMP metres.
func due(eye: Vector3, delta: float) -> bool:
	_t -= delta
	if _t > 0.0 and eye.distance_to(_last_eye) < JUMP:
		return false
	_t = INTERVAL
	return true


## Makes the probes nearest `eye` live (MAX_VISIBLE, plus those already live that still rank within
## KEEP_VISIBLE; at most `show_per_rank` put back, nearest first, and none while the last ones still
## wait to render) and parks the rest, except those still waiting for their turn. Probes hidden on
## purpose (`visible` false) are left alone. Returns how many are live.
func update(eye: Vector3) -> int:
	flush_parks()
	_last_eye = eye
	var now: int = int(frames.call())
	var ranked: Array = _ranked(eye)
	var room: bool = frames_to_render() < show_per_rank * RENDER_FRAMES
	var start: int = maxi(_rendered_by, now)
	var fresh: int = 0
	for i: int in ranked.size():
		var p: ReflectionProbe = ranked[i][1]
		var live: bool = not _homes.has(p)
		var show: bool = i < MAX_VISIBLE or (i < KEEP_VISIBLE and live)
		if show and not live:
			if room and fresh < show_per_rank and _unpark(p):
				fresh += 1
				_due[p] = start + fresh * RENDER_FRAMES
		elif not show and live and int(_due.get(p, 0)) <= now:
			_park(p)
	if fresh > 0:
		_rendered_by = start + fresh * RENDER_FRAMES
	return shown()


## Parks every probe but the `k` nearest `eye` and makes those live at once, so they are all the
## render queue holds (the screenshot runner, before an interior shot). Counts all `k` in
## frames_to_render(), since a live probe may not have rendered yet. Rankings go on as before.
func focus(eye: Vector3, k: int) -> void:
	flush_parks()
	var ranked: Array = _ranked(eye)
	for i: int in ranked.size():
		var p: ReflectionProbe = ranked[i][1]
		if i < k:
			_unpark(p)
		else:
			_park(p)
	_last_eye = eye
	_t = INTERVAL
	_rendered_by = int(frames.call()) + mini(k, ranked.size()) * RENDER_FRAMES


## Parks the probes that entered the tree since the last call (normally at the end of the frame).
func flush_parks() -> void:
	var batch: Array[ReflectionProbe] = _to_park.duplicate()
	_to_park.clear()
	for p: ReflectionProbe in batch:
		if is_instance_valid(p) and _probes.has(p) and p.is_inside_tree():
			_park(p)


## Whether a probe is live: in the scene, authored visible and not parked.
func is_shown(p: ReflectionProbe) -> bool:
	return is_instance_valid(p) and p.is_inside_tree() and p.visible and not _homes.has(p)


## Every probe the budget manages, live or parked (parked ones are out of the tree and its groups).
func all_probes() -> Array:
	var out: Array = []
	for p: Variant in _probes:
		if is_instance_valid(p):
			out.append(p)
	return out


## Frames until every probe put back so far has had its turn to render (they render one at a time).
## The screenshot runner waits on it for interiors.
func frames_to_render() -> int:
	return maxi(_rendered_by - int(frames.call()), 0)


## Live interior probes right now.
func shown() -> int:
	var n: int = 0
	for p: Variant in _probes:
		if is_instance_valid(p) and is_shown(p as ReflectionProbe):
			n += 1
	return n


## Distance from `eye` to the probe's box (zero inside it): a long hall counts as near from either
## end, where its centre would not. A parked probe out of the tree uses its last placement.
static func box_distance(p: ReflectionProbe, eye: Vector3) -> float:
	var xf: Transform3D = p.global_transform if p.is_inside_tree() else p.get_meta(&"probe_xf", p.transform)
	var local: Vector3 = xf.affine_inverse() * eye
	return (local.abs() - p.size * 0.5).max(Vector3.ZERO).length()


## The managed probes by box distance from `eye`, nearest first: [distance, probe] each.
func _ranked(eye: Vector3) -> Array:
	var ranked: Array = []
	for v: Variant in _probes.keys():
		if not is_instance_valid(v):
			_probes.erase(v)
			_due.erase(v)
			continue
		var p := v as ReflectionProbe
		if p.visible:
			ranked.append([box_distance(p, eye), p])
	ranked.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) < float(b[0]))
	return ranked


func _park(p: ReflectionProbe) -> void:
	if _homes.has(p) or not p.is_inside_tree():
		return
	var home: Node = p.get_parent()
	var hid: int = home.get_instance_id()
	# Its place in the world, for ranking while it is out of the tree.
	p.set_meta(&"probe_xf", p.global_transform)
	_homes[p] = hid
	_due.erase(p)
	if not _parked.has(hid):
		_parked[hid] = []
		# One watch per building (a signal takes one connection per method, binds aside).
		home.tree_exited.connect(_on_home_left.bind(hid), CONNECT_ONE_SHOT)
	(_parked[hid] as Array).append(p)
	home.remove_child(p)


## Puts a parked probe back in its building; false when the building has left the tree.
func _unpark(p: ReflectionProbe) -> bool:
	if not _homes.has(p):
		return true
	var hid: int = _homes[p]
	var home := instance_from_id(hid) as Node
	if home == null or not home.is_inside_tree():
		return false
	_homes.erase(p)
	var waiting: Array = _parked.get(hid, [])
	waiting.erase(p)
	if waiting.is_empty():
		_parked.erase(hid)
		_unwatch(home, hid)
	home.add_child(p)
	return true


func _unwatch(home: Node, hid: int) -> void:
	var watch: Callable = _on_home_left.bind(hid)
	if home.tree_exited.is_connected(watch):
		home.tree_exited.disconnect(watch)


## A building with parked probes left the tree (streamed out, freed): they go back to it.
func _on_home_left(hid: int) -> void:
	_send_home.call_deferred(hid)


## Returns a building's parked probes to it, out of the tree, so they are freed with it or come
## back with it (and are managed again then); frees them if the building is gone.
func _send_home(hid: int) -> void:
	var probes: Array = _parked.get(hid, [])
	_parked.erase(hid)
	var home := instance_from_id(hid) as Node
	if home != null:
		_unwatch(home, hid)
	for v: Variant in probes:
		if not is_instance_valid(v):
			continue
		var p := v as ReflectionProbe
		_homes.erase(p)
		_probes.erase(p)
		_due.erase(p)
		if p.get_parent() != null:
			continue
		if home != null and not home.is_queued_for_deletion():
			home.add_child(p)
		else:
			p.free()


func _on_node_added(n: Node) -> void:
	if not n.is_in_group(GROUP) or not (n is ReflectionProbe):
		return
	var p := n as ReflectionProbe
	if _probes.has(p):
		# Put back by the budget.
		return
	_probes[p] = true
	if p.visible:
		_to_park.append(p)
		if _to_park.size() == 1:
			flush_parks.call_deferred()


func _on_node_removed(n: Node) -> void:
	if not n.is_in_group(GROUP) or not (n is ReflectionProbe):
		return
	var p := n as ReflectionProbe
	if _homes.has(p):
		# Parked by the budget.
		return
	# Removed with its building, or by someone else: forget it (re-added later, it starts over).
	_probes.erase(p)
	_to_park.erase(p)
	_due.erase(p)
