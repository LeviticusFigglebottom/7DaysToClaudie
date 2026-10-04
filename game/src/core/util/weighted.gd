class_name Weighted
extends RefCounted
## Weighted random selection helpers.


## Picks an index from weights (floats >= 0). Returns -1 if all weights are zero.
static func pick_index(weights: PackedFloat32Array, rng: RandomNumberGenerator) -> int:
	var total: float = 0.0
	for w: float in weights:
		total += maxf(w, 0.0)
	if total <= 0.0:
		return -1
	var r: float = rng.randf() * total
	for i: int in weights.size():
		r -= maxf(weights[i], 0.0)
		if r < 0.0:
			return i
	return weights.size() - 1


## Picks a key from {key: weight}. Keys are iterated in sorted order for determinism.
static func pick_key(table: Dictionary, rng: RandomNumberGenerator) -> Variant:
	var keys: Array = table.keys()
	keys.sort()
	var weights := PackedFloat32Array()
	for k: Variant in keys:
		weights.append(float(table[k]))
	var i: int = pick_index(weights, rng)
	return null if i < 0 else keys[i]


static func randi_range_v(range_v: Vector2i, rng: RandomNumberGenerator) -> int:
	return rng.randi_range(mini(range_v.x, range_v.y), maxi(range_v.x, range_v.y))
