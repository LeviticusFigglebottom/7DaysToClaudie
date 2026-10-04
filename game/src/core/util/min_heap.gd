class_name MinHeap
extends RefCounted
## Binary min-heap of (priority: float, value: Variant). Used by Dijkstra-style searches
## (structural stability, horde flow fields, POI route validation).

var _prio: PackedFloat64Array = []
var _vals: Array = []


func size() -> int:
	return _prio.size()


func is_empty() -> bool:
	return _prio.is_empty()


func push(priority: float, value: Variant) -> void:
	_prio.append(priority)
	_vals.append(value)
	var i: int = _prio.size() - 1
	while i > 0:
		var p: int = (i - 1) >> 1
		if _prio[p] <= _prio[i]:
			break
		_swap(i, p)
		i = p


func peek_priority() -> float:
	return _prio[0]


## Removes and returns the value with the smallest priority.
func pop() -> Variant:
	var top: Variant = _vals[0]
	var last: int = _prio.size() - 1
	_swap(0, last)
	_prio.resize(last)
	_vals.resize(last)
	var i: int = 0
	var n: int = last
	while true:
		var l: int = i * 2 + 1
		var r: int = l + 1
		var m: int = i
		if l < n and _prio[l] < _prio[m]:
			m = l
		if r < n and _prio[r] < _prio[m]:
			m = r
		if m == i:
			break
		_swap(i, m)
		i = m
	return top


func _swap(a: int, b: int) -> void:
	var tp: float = _prio[a]
	_prio[a] = _prio[b]
	_prio[b] = tp
	var tv: Variant = _vals[a]
	_vals[a] = _vals[b]
	_vals[b] = tv
