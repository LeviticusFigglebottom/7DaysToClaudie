extends GutTest
## The interior probe budget keeps the live reflection probes under the renderer's 64 atlas slots
## however many buildings are built, and has the room the player is in render first. Past 64 the
## engine crashed on reaching Pell's Crossing. Far probes are parked: taken out of the scene tree,
## the one way Godot 4.7.2 frees a probe's atlas slot and still renders it when it comes back
## (hiding it keeps the slot, so a walk round town crashed after the 64th room; detaching its base
## frees the slot but it never renders again). Probes enter parked, a ranking puts back the ones
## nearest the eye a few at a time, and a live probe stays live while it ranks within KEEP_VISIBLE.
## The budget reads a drawn-frame clock; here a fake one, stepped by hand, stands in for rendering.

const Budget := preload("res://src/poi/interior_probe_budget.gd")

var _budget: Node
var _town: Node3D
## The fake drawn-frame clock.
var _frame: int = 1000


func before_each() -> void:
	_budget = Budget.new()
	# Most tests check the ranking alone; the throttle has its own tests below.
	_budget.show_per_rank = 1 << 20
	_budget.frames = func() -> int: return _frame
	add_child_autofree(_budget)
	_town = Node3D.new()
	add_child_autofree(_town)


## A street of `n` interior probes 10 m apart along +X, each a 6 x 3 x 6 m room box, parked as they
## would be at the end of the frame that built them.
func _street(n: int, from: int = 0, parent: Node3D = null) -> Array[ReflectionProbe]:
	var out: Array[ReflectionProbe] = []
	for i: int in range(from, from + n):
		var p := ReflectionProbe.new()
		p.size = Vector3(6.0, 3.0, 6.0)
		p.position = Vector3(i * 10.0, 1.5, 0.0)
		p.add_to_group(&"interior_probe")
		(parent if parent != null else _town).add_child(p)
		out.append(p)
	_budget.flush_parks()
	return out


## A ranking long after every probe put back so far has rendered.
func _update(eye: Vector3) -> int:
	_frame += 100000
	return _budget.update(eye)


func _ids(from: int, to: int) -> Array[int]:
	var out: Array[int] = []
	for i: int in range(from, to):
		out.append(i)
	return out


func _shown_ids(probes: Array[ReflectionProbe]) -> Array[int]:
	var out: Array[int] = []
	for i: int in probes.size():
		if _budget.is_shown(probes[i]):
			out.append(i)
	return out


func test_the_cap_is_under_the_atlas() -> void:
	assert_lt(Budget.KEEP_VISIBLE, 64, "the reflection atlas has 64 slots")
	assert_lt(Budget.MAX_VISIBLE, Budget.KEEP_VISIBLE)


func test_a_town_built_at_once_goes_live_only_when_ranked() -> void:
	var probes: Array[ReflectionProbe] = _street(150)
	assert_eq(_shown_ids(probes).size(), 0, "parked as they enter: none queues a render far from the player")
	assert_false(probes[0].is_inside_tree(), "parked means out of the tree")
	assert_eq(_update(Vector3(1001.0, 1.5, 0.0)), Budget.MAX_VISIBLE)
	assert_eq(_shown_ids(probes), _ids(85, 117), "the first ranking puts the nearest back")
	assert_eq(probes[100].get_parent(), _town, "back in its own building")


func test_the_nearest_probes_are_shown_and_a_shown_one_keeps_its_slot() -> void:
	var probes: Array[ReflectionProbe] = _street(150)
	# Just past probe 100: the 32 nearest are 85..116 (the eye sits a metre toward 101).
	assert_eq(_update(Vector3(1001.0, 1.5, 0.0)), Budget.MAX_VISIBLE)
	assert_eq(_shown_ids(probes), _ids(85, 117), "the nearest 32 around the eye")
	# 30 m on, the nearest are 88..119; 85..87 are live and still rank within KEEP_VISIBLE, so they
	# stay live instead of flickering off at the edge.
	assert_eq(_update(Vector3(1031.0, 1.5, 0.0)), 35)
	assert_eq(_shown_ids(probes), _ids(85, 120))
	# Across town: only the new nearest are live.
	assert_eq(_update(Vector3(-5.0, 1.5, 0.0)), Budget.MAX_VISIBLE)
	assert_eq(_shown_ids(probes), _ids(0, 32))


func test_distance_is_to_the_room_box_not_its_centre() -> void:
	var hall := ReflectionProbe.new()
	hall.size = Vector3(40.0, 3.0, 4.0)
	hall.position = Vector3(500.0, 1.5, 0.0)
	_town.add_child(hall)
	assert_almost_eq(Budget.box_distance(hall, Vector3(518.0, 1.5, 0.0)), 0.0, 0.001, "at the end of a long hall, inside its box")
	assert_almost_eq(Budget.box_distance(hall, Vector3(530.0, 1.5, 0.0)), 10.0, 0.001)
	hall.rotation_degrees.y = 90.0
	assert_almost_eq(Budget.box_distance(hall, Vector3(500.0, 1.5, 18.0)), 0.0, 0.001, "the box turns with its building")


func test_a_parked_probe_is_ranked_where_it_stood() -> void:
	var probes: Array[ReflectionProbe] = _street(3)
	assert_false(probes[2].is_inside_tree())
	assert_almost_eq(Budget.box_distance(probes[2], Vector3(20.0, 1.5, 0.0)), 0.0, 0.001, "out of the tree, it keeps its place")


func test_buildings_added_later_respect_the_cap() -> void:
	var probes: Array[ReflectionProbe] = _street(40)
	assert_eq(_update(Vector3(200.0, 1.5, 0.0)), Budget.MAX_VISIBLE, "the nearest 32 of 40")
	var later: Array[ReflectionProbe] = _street(30, 40)
	assert_eq(_shown_ids(later).size(), 0, "a building added later comes in parked")
	assert_lte(_update(Vector3(400.0, 1.5, 0.0)), Budget.KEEP_VISIBLE, "and a ranking never passes the cap")
	assert_lte(_shown_ids(probes).size() + _shown_ids(later).size(), Budget.KEEP_VISIBLE)


func test_freed_probes_give_their_slots_back() -> void:
	var probes: Array[ReflectionProbe] = _street(10)
	assert_eq(_update(Vector3.ZERO), 10)
	for i: int in 4:
		_town.remove_child(probes[i])
		probes[i].free()
	assert_eq(_budget.shown(), 6)


func test_after_a_jump_the_nearest_probes_show_first_a_few_at_a_time() -> void:
	# Godot renders UPDATE_ONCE probes one at a time, about RENDER_FRAMES each. Putting 32 back at
	# once left the room the camera stood in waiting behind up to 31 others, near-black meanwhile
	# (the Mile 9 Diner at noon, TD-134).
	_budget.show_per_rank = Budget.SHOW_PER_RANK
	var probes: Array[ReflectionProbe] = _street(150)
	# The eye is inside probe 100's room; 101 is 6 m away and 99 is 8 m.
	assert_eq(_budget.update(Vector3(1001.0, 1.5, 0.0)), 2)
	assert_eq(_shown_ids(probes), [100, 101], "the room the eye is in, then its nearest neighbour")
	_frame += Budget.RENDER_FRAMES
	assert_eq(_budget.update(Vector3(1001.0, 1.5, 0.0)), 4)
	assert_eq(_shown_ids(probes), [99, 100, 101, 102])
	for i: int in 14:
		_frame += 2 * Budget.RENDER_FRAMES
		_budget.update(Vector3(1001.0, 1.5, 0.0))
	assert_eq(_shown_ids(probes), _ids(85, 117), "the same nearest 32 in the end")


func test_shown_probes_queue_their_renders() -> void:
	_budget.show_per_rank = Budget.SHOW_PER_RANK
	_street(150)
	assert_eq(_budget.frames_to_render(), 0, "parked probes queue nothing")
	_budget.update(Vector3(1001.0, 1.5, 0.0))
	assert_eq(_budget.frames_to_render(), 2 * Budget.RENDER_FRAMES)
	# Rankings come every INTERVAL; renders come every RENDER_FRAMES drawn frames, which a slow GPU
	# (or lavapipe) draws far slower. A ranking puts back no more while the last two wait.
	assert_eq(_budget.update(Vector3(1001.0, 1.5, 0.0)), 2, "nothing more while the last two wait")
	assert_eq(_budget.frames_to_render(), 2 * Budget.RENDER_FRAMES)
	_frame += Budget.RENDER_FRAMES
	assert_eq(_budget.update(Vector3(1001.0, 1.5, 0.0)), 4, "one has had its turn: two more")
	assert_eq(_budget.frames_to_render(), 3 * Budget.RENDER_FRAMES, "and they render one after another")


func test_a_probe_waiting_to_render_is_not_parked_yet() -> void:
	# Leaving the scenario frees a probe's slot but leaves it in the renderer's queue, where it
	# logs `Parameter "scenario" is null` when its turn comes. A probe put back is parked only after
	# its turn.
	_budget.show_per_rank = Budget.SHOW_PER_RANK
	var probes: Array[ReflectionProbe] = _street(150)
	_budget.update(Vector3(1001.0, 1.5, 0.0))
	assert_eq(_shown_ids(probes), [100, 101])
	# A jump across town, before either has rendered.
	assert_eq(_budget.update(Vector3(-5.0, 1.5, 0.0)), 2, "both still wait their turn: neither is parked")
	assert_eq(_shown_ids(probes), [100, 101])
	_frame += Budget.RENDER_FRAMES
	_budget.update(Vector3(-5.0, 1.5, 0.0))
	assert_eq(_shown_ids(probes), [0, 1, 101], "100 had its turn and is parked; 101 waits; the new nearest come")
	_frame += Budget.RENDER_FRAMES
	_budget.update(Vector3(-5.0, 1.5, 0.0))
	assert_eq(_shown_ids(probes), [0, 1], "then 101 goes too")
	for i: int in 15:
		_frame += 2 * Budget.RENDER_FRAMES
		_budget.update(Vector3(-5.0, 1.5, 0.0))
	assert_eq(_shown_ids(probes), _ids(0, 32))


func test_a_jump_ranks_at_once() -> void:
	_street(10)
	assert_true(_budget.due(Vector3.ZERO, 0.0), "the first ranking is due at once")
	_update(Vector3.ZERO)
	assert_false(_budget.due(Vector3(5.0, 0.0, 0.0), 0.01), "a step waits for the interval")
	assert_true(_budget.due(Vector3(Budget.JUMP + 1.0, 0.0, 0.0), 0.01), "a teleport does not")
	_update(Vector3(Budget.JUMP + 1.0, 0.0, 0.0))
	assert_true(_budget.due(Vector3(Budget.JUMP + 1.0, 0.0, 0.0), Budget.INTERVAL), "and the interval still ranks")


func test_far_probes_are_parked_out_of_the_tree_not_hidden() -> void:
	# Hiding a probe keeps its atlas slot (Godot 4.7.2 frees it only when the instance leaves its
	# scenario or is freed): the probe lab, one probe visible at a time, crashed after its 64th
	# room. Taken out of the tree, a probe frees its slot and renders again when put back.
	var probes: Array[ReflectionProbe] = _street(150)
	_update(Vector3(1001.0, 1.5, 0.0))
	for i: int in [0, 50, 149]:
		assert_true(probes[i].visible, "probe %d keeps `visible`, which stays the builder's to set" % i)
		assert_false(probes[i].is_inside_tree(), "but is out of the tree")
	assert_true(probes[100].is_inside_tree())
	assert_eq(_budget.all_probes().size(), 150, "the budget still knows every one")


func test_a_probe_hidden_on_purpose_is_left_alone() -> void:
	var probes: Array[ReflectionProbe] = _street(10)
	_update(Vector3(30.0, 1.5, 0.0))
	_town.remove_child(probes[3])
	probes[3].visible = false
	_town.add_child(probes[3])
	_budget.flush_parks()
	_update(Vector3(30.0, 1.5, 0.0))
	assert_false(_budget.is_shown(probes[3]), "a probe the builder hid stays off")
	assert_true(probes[3].is_inside_tree(), "and in its building")
	assert_eq(_budget.shown(), 9, "and doesn't count")


func test_a_parked_probe_goes_home_when_its_building_leaves() -> void:
	# Streaming takes buildings out with their regions; a parked probe must leave with its building,
	# not stay behind in the budget.
	var building := Node3D.new()
	_town.add_child(building)
	var probes: Array[ReflectionProbe] = _street(2, 500, building)
	assert_eq(probes[0].get_parent(), null, "parked")
	_town.remove_child(building)
	await get_tree().process_frame
	assert_eq(probes[0].get_parent(), building, "back in its building, out of the tree with it")
	assert_eq(probes[1].get_parent(), building)
	assert_eq(_budget.all_probes().size(), 0, "and forgotten until the building comes back")
	_town.add_child(building)
	_budget.flush_parks()
	assert_eq(_budget.all_probes().size(), 2, "managed again when it does")
	assert_false(probes[0].is_inside_tree(), "and parked again")
	_town.remove_child(building)
	await get_tree().process_frame
	building.free()


func test_a_parked_probe_is_freed_with_its_building() -> void:
	var building := Node3D.new()
	_town.add_child(building)
	var probes: Array[ReflectionProbe] = _street(2, 500, building)
	building.free()
	await get_tree().process_frame
	assert_false(is_instance_valid(probes[0]), "no orphan probe left behind")
	assert_false(is_instance_valid(probes[1]))


func test_focus_leaves_only_the_nearest_few_live() -> void:
	# The render queue runs in the renderer's order, so a capture of a room parks everything else.
	var probes: Array[ReflectionProbe] = _street(150)
	_update(Vector3(1001.0, 1.5, 0.0))
	_budget.focus(Vector3(501.0, 1.5, 0.0), 4)
	assert_eq(_shown_ids(probes), [49, 50, 51, 52], "the room the eye is in and its three nearest")
	assert_eq(_budget.shown(), 4)
	assert_eq(_budget.frames_to_render(), 4 * Budget.RENDER_FRAMES, "all four counted, rendered before or not")
