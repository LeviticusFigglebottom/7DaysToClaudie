extends GutTest


func test_fnv1a_matches_reference() -> void:
	# Reference values computed with Python (same algorithm used by the asset pipeline).
	assert_eq(Ids.hash64("A"), -5808521688781806868)
	assert_eq(Ids.hash64(""), Ids.FNV_OFFSET)


func test_derive_seed_stable_and_distinct() -> void:
	assert_eq(Ids.derive_seed(42, "loot"), Ids.derive_seed(42, "loot"))
	assert_ne(Ids.derive_seed(42, "loot"), Ids.derive_seed(42, "weather"))
	assert_ne(Ids.derive_seed(42, "loot"), Ids.derive_seed(43, "loot"))


func test_id_allocator_round_trip() -> void:
	var a := IdAllocator.new()
	assert_eq(a.next("z"), &"z:000001")
	assert_eq(a.next("z"), &"z:000002")
	assert_eq(a.next("s"), &"s:000001")
	var b := IdAllocator.new()
	b.from_dict(a.to_dict())
	assert_eq(b.next("z"), &"z:000003")


func test_rng_streams_independent_and_restorable() -> void:
	var r := RngStreams.new(99)
	var first: int = r.stream("loot").randi()
	r.stream("weather").randi()
	var r2 := RngStreams.new(99)
	assert_eq(r2.stream("loot").randi(), first, "weather draws must not affect loot stream")
	r.stream("loot").randi()
	var saved: Dictionary = r.to_dict()
	var expect: int = r.stream("loot").randi()
	var r3 := RngStreams.new(0)
	r3.from_dict(JSON.parse_string(JSON.stringify(saved)))
	assert_eq(r3.stream("loot").randi(), expect, "restored stream continues identically")


func test_chunk_key_round_trip() -> void:
	assert_eq(Ids.parse_chunk_key(Ids.chunk_key(-3, 12)), Vector2i(-3, 12))
