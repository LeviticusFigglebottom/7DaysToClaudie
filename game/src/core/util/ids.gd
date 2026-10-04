class_name Ids
extends RefCounted
## Deterministic identifiers and hashing.
##
## Rules (ADR-0003):
##  - Authored/world-placed things get *content-addressed* ids built from stable parts
##    ("tree:r_d6:12_7:143", "poi:pell_crossing:lot_3", "ctr:<poi_instance>:<local>").
##  - Runtime-spawned things get ids from the session IdAllocator ("z:000123").
##  - Never use get_instance_id() or node paths as persistent ids.

const FNV_OFFSET: int = -3750763034362895579  # 14695981039346656037 as signed int64
const FNV_PRIME: int = 1099511628211


## 64-bit FNV-1a over UTF-8 bytes (int64 arithmetic wraps, which is what FNV wants).
static func hash64(s: String) -> int:
	var h: int = FNV_OFFSET
	for b: int in s.to_utf8_buffer():
		h = (h ^ b) * FNV_PRIME
	return h


## Combines a seed and a key into a new seed (for derived RNG streams).
static func derive_seed(seed: int, key: String) -> int:
	return hash64("%d|%s" % [seed, key])


## Non-negative 31-bit hash, handy for indices and shader seeds.
static func hash31(s: String) -> int:
	return hash64(s) & 0x7FFFFFFF


static func make(prefix: String, parts: Array) -> StringName:
	var strs: PackedStringArray = []
	for p: Variant in parts:
		strs.append(str(p))
	return StringName("%s:%s" % [prefix, ":".join(strs)])


static func chunk_key(cx: int, cz: int) -> String:
	return "%d_%d" % [cx, cz]


static func parse_chunk_key(key: String) -> Vector2i:
	var p: PackedStringArray = key.split("_")
	if p.size() != 2:
		return Vector2i.ZERO
	return Vector2i(int(p[0]), int(p[1]))
