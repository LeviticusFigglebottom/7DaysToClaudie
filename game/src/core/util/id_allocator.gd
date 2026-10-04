class_name IdAllocator
extends RefCounted
## Monotonic id source for runtime-spawned entities. Owned by the authority (host) and saved
## with the session, so ids never repeat across save/load and are identical for all peers.

var _counters: Dictionary = {}


func next(prefix: String) -> StringName:
	var n: int = int(_counters.get(prefix, 0)) + 1
	_counters[prefix] = n
	return StringName("%s:%06d" % [prefix, n])


func peek(prefix: String) -> int:
	return int(_counters.get(prefix, 0))


func to_dict() -> Dictionary:
	return _counters.duplicate()


func from_dict(d: Dictionary) -> void:
	_counters.clear()
	for k: Variant in d.keys():
		_counters[str(k)] = int(d[k])
