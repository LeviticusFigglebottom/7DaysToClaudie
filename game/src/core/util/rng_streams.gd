class_name RngStreams
extends RefCounted
## Named, independent, deterministic random streams derived from one seed.
##
## Each subsystem draws from its own stream ("loot", "weather", "horde", ...) so adding a roll
## in one system never shifts the sequence of another (keeps saves and tests stable).
## Worldgen does NOT use these (it derives position-keyed seeds so generation order never
## matters) — see WorldgenRandom.

var seed: int
var _streams: Dictionary = {}


func _init(world_seed: int = 0) -> void:
	seed = world_seed


func stream(name: String) -> RandomNumberGenerator:
	var rng: RandomNumberGenerator = _streams.get(name)
	if rng == null:
		rng = RandomNumberGenerator.new()
		rng.seed = Ids.derive_seed(seed, name)
		_streams[name] = rng
	return rng


## One-off RNG for a keyed purpose (does not advance any stream).
func keyed(key: String) -> RandomNumberGenerator:
	var rng := RandomNumberGenerator.new()
	rng.seed = Ids.derive_seed(seed, key)
	return rng


func to_dict() -> Dictionary:
	var states: Dictionary = {}
	for k: String in _streams:
		states[k] = str((_streams[k] as RandomNumberGenerator).state)
	return {"seed": str(seed), "states": states}


func from_dict(d: Dictionary) -> void:
	seed = int(str(d.get("seed", "0")))
	_streams.clear()
	var states: Dictionary = d.get("states", {})
	for k: Variant in states.keys():
		var rng: RandomNumberGenerator = stream(str(k))
		rng.state = int(str(states[k]))
