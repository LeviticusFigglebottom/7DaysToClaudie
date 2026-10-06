extends GutTest
## The interior probe budget keeps the visible reflection probes under the renderer's 64 atlas
## slots however many buildings are built. Past 64 the engine crashed on reaching Pell's Crossing.
## Probes entering the tree are capped at once, a ranking shows the ones nearest the eye, and a
## probe already shown keeps its slot while it ranks within KEEP_VISIBLE.

const Budget := preload("res://src/poi/interior_probe_budget.gd")

var _budget: Node
var _town: Node3D


func before_each() -> void:
	_budget = Budget.new()
	add_child_autofree(_budget)
	_town = Node3D.new()
	add_child_autofree(_town)


## A street of `n` interior probes 10 m apart along +X, each a 6 x 3 x 6 m room box.
func _street(n: int, from: int = 0) -> Array[ReflectionProbe]:
	var out: Array[ReflectionProbe] = []
	for i: int in range(from, from + n):
		var p := ReflectionProbe.new()
		p.size = Vector3(6.0, 3.0, 6.0)
		p.position = Vector3(i * 10.0, 1.5, 0.0)
		p.add_to_group(&"interior_probe")
		_town.add_child(p)
		out.append(p)
	return out


func _ids(from: int, to: int) -> Array[int]:
	var out: Array[int] = []
	for i: int in range(from, to):
		out.append(i)
	return out


func _shown_ids(probes: Array[ReflectionProbe]) -> Array[int]:
	var out: Array[int] = []
	for i: int in probes.size():
		if probes[i].visible:
			out.append(i)
	return out


func test_the_cap_is_under_the_atlas() -> void:
	assert_lt(Budget.KEEP_VISIBLE, 64, "the reflection atlas has 64 slots")
	assert_lt(Budget.MAX_VISIBLE, Budget.KEEP_VISIBLE)


func test_a_town_built_at_once_shows_no_more_than_the_cap() -> void:
	var probes: Array[ReflectionProbe] = _street(150)
	assert_eq(_shown_ids(probes).size(), Budget.KEEP_VISIBLE, "capped as they enter the tree, before any ranking")
	assert_eq(_budget.shown(), Budget.KEEP_VISIBLE)


func test_the_nearest_probes_are_shown_and_a_shown_one_keeps_its_slot() -> void:
	var probes: Array[ReflectionProbe] = _street(150)
	# Just past probe 100: the 32 nearest are 85..116 (the eye sits a metre toward 101).
	assert_eq(_budget.update(Vector3(1001.0, 1.5, 0.0)), Budget.MAX_VISIBLE)
	assert_eq(_shown_ids(probes), _ids(85, 117), "the nearest 32 around the eye")
	# 30 m on, the nearest are 88..119; 85..87 were shown and still rank within KEEP_VISIBLE, so
	# they keep their slots instead of flickering off at the edge.
	assert_eq(_budget.update(Vector3(1031.0, 1.5, 0.0)), 35)
	assert_eq(_shown_ids(probes), _ids(85, 120))
	# Across town: only the new nearest are shown.
	assert_eq(_budget.update(Vector3(-5.0, 1.5, 0.0)), Budget.MAX_VISIBLE)
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


func test_buildings_added_later_respect_the_cap() -> void:
	var probes: Array[ReflectionProbe] = _street(40)
	assert_eq(_budget.shown(), 40, "under the cap every probe shows")
	var later: Array[ReflectionProbe] = _street(30, 40)
	assert_eq(_budget.shown(), Budget.KEEP_VISIBLE, "new probes fill the cap and no more")
	assert_eq(_shown_ids(probes).size() + _shown_ids(later).size(), Budget.KEEP_VISIBLE)


func test_freed_probes_give_their_slots_back() -> void:
	var probes: Array[ReflectionProbe] = _street(10)
	assert_eq(_budget.shown(), 10)
	for i: int in 4:
		_town.remove_child(probes[i])
		probes[i].free()
	assert_eq(_budget.shown(), 6)
