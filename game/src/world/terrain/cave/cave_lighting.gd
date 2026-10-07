class_name CaveLighting
extends Node3D
## Interior light for the caves (ADR-0050, ADR-0056, CAVES_PLAN WS-D). Under SDFGI a cave is as
## black as a closed room was before ADR-0050, and without SDFGI it is lit by the open sky's
## ambient, as bright as the hill outside. So each cave gets the buildings' answer: up to three
## interior ReflectionProbes from CavePlan.probe_boxes() (yaw-aligned, the top clamped under the
## ground), in group `interior_probe`. EnvironmentController gives them the interior fill and the
## indoor exposure as it does a room's, and InteriorProbeBudget keeps them within the atlas.
##
## Each probe's share of the fill falls with its depth from the mouth:
##  * meta `daylight`: exp(-depth / cave_falloff_m) of daylight_full_ratio (interior_light.json), so
##    a box at the mouth gets the whole fill and the far chamber next to none. The plan's own
##    daylight_ratio (caves.json daylight_falloff) is turned back into a depth for it, so the light's
##    falloff is tuned here without reshaping a single cave.
##  * meta `min_share`: cave_min_share, the floor of that share (darker than a cellar's
##    daylight_min_share: no lamp burns in a cave).
##
## The probes of a cave live under a holder node of their own, rebuilt when the terrain's cave set
## changes (caves_changed, a region attached or detached). The budget parks probes out of the tree
## and sends them home when their holder leaves: removing the holder frees them, parked or not.

const GROUP: StringName = &"interior_probe"

var terrain: Node
## Cave id -> [CavePlan, holder Node3D].
var _caves: Dictionary = {}


func setup(p_terrain: Node) -> void:
	terrain = p_terrain
	for sig: StringName in [&"caves_changed", &"region_attached", &"region_detached"]:
		if terrain.has_signal(sig):
			terrain.connect(sig, _on_changed)
	rebuild()


func _on_changed(_arg: Variant = null) -> void:
	rebuild()


## The plans of the terrain's cave set now (an object with `plans`; fakes without probe boxes
## are left out).
func _current_plans() -> Dictionary:
	var out: Dictionary = {}
	var set_obj: Variant = terrain.get(&"caves") if terrain != null else null
	if not (set_obj is Object):
		return out
	var plans: Variant = (set_obj as Object).get(&"plans")
	if not (plans is Array):
		return out
	for p: Variant in plans:
		if p is Object and (p as Object).has_method(&"probe_boxes") and bool((p as Object).get(&"ok")):
			out[StringName(str((p as Object).get(&"id")))] = p
	return out


## Brings the probes in line with the terrain's caves: new caves get theirs, gone or replanned
## ones lose theirs.
func rebuild() -> void:
	var want: Dictionary = _current_plans()
	for id: StringName in _caves.keys():
		if not want.has(id) or not is_same(want[id], _caves[id][0]):
			_drop(id)
	var cfg: Dictionary = _light_cfg()
	var plan_falloff: float = float(_caves_cfg().get("daylight_falloff", 6.0))
	for id2: StringName in want:
		if not _caves.has(id2):
			_caves[id2] = [want[id2], _build(want[id2], cfg, plan_falloff)]


func _drop(id: StringName) -> void:
	var holder: Node3D = _caves[id][1]
	_caves.erase(id)
	if is_instance_valid(holder):
		remove_child(holder)
		holder.queue_free()


## Every probe of every cave (parked ones too: they are the holders' children or the budget's).
func probe_count() -> int:
	var n: int = 0
	for id: StringName in _caves:
		n += (_caves[id][0] as Object).call(&"probe_boxes").size()
	return n


## The holder of a cave's probes (tests, debug), or null.
func holder_of(id: StringName) -> Node3D:
	return _caves[id][1] if _caves.has(id) else null


func _build(plan: Object, cfg: Dictionary, plan_falloff: float) -> Node3D:
	var holder := Node3D.new()
	holder.name = "Cave_%s" % str(plan.get(&"id")).validate_node_name()
	add_child(holder)
	for box: Array in plan.call(&"probe_boxes"):
		holder.add_child(make_probe(box[0], box[1], float(box[2]), cfg, plan_falloff))
	return holder


## An interior probe for one of CavePlan.probe_boxes()' boxes [Transform3D, size, daylight_ratio].
static func make_probe(xf: Transform3D, size: Vector3, ratio: float, cfg: Dictionary, plan_falloff: float) -> ReflectionProbe:
	var probe := ReflectionProbe.new()
	probe.name = "CaveProbe"
	probe.interior = true
	probe.ambient_mode = ReflectionProbe.AMBIENT_COLOR
	probe.ambient_color = Color(0.8, 0.8, 0.78)
	# A dim fill until EnvironmentController takes over (previews, tests, the first frame).
	probe.ambient_color_energy = 0.2
	probe.transform = xf
	probe.size = size
	probe.blend_distance = PoiBuilder.PROBE_BLEND
	probe.max_distance = maxf(size.x, size.z)
	probe.update_mode = ReflectionProbe.UPDATE_ONCE
	probe.set_meta(&"daylight", daylight_of(ratio, plan_falloff, cfg))
	probe.set_meta(&"min_share", float(cfg.get("cave_min_share", 0.06)))
	probe.add_to_group(GROUP)
	return probe


## A probe's `daylight` meta (EnvironmentController.daylight_share's ratio) from the plan's
## daylight_ratio = exp(-depth / plan_falloff): exp(-depth / cave_falloff_m) of daylight_full_ratio.
static func daylight_of(ratio: float, plan_falloff: float, cfg: Dictionary) -> float:
	var depth: float = -log(clampf(ratio, 1e-4, 1.0)) * maxf(0.1, plan_falloff)
	var share: float = exp(-depth / maxf(0.1, float(cfg.get("cave_falloff_m", 6.0))))
	return share * float(cfg.get("daylight_full_ratio", 0.1))


static func _light_cfg() -> Dictionary:
	return ContentDB.instance.config(&"interior_light") if ContentDB.instance != null else {}


static func _caves_cfg() -> Dictionary:
	return ContentDB.instance.config(&"caves") if ContentDB.instance != null else {}
