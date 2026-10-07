extends GutTest
## A 1 m kit window (0.7 x 1.1 m opening) can be vaulted: the crouched capsule lifted onto its sill
## is taller than the opening, so the vault dives with a lower capsule (Player.DIVE_HEIGHT). The
## traversal bot (poi_walk) found every such window blocked, Merrow House's intended way in among them.

const Bot := preload("res://src/tools/cli/poi_walk_bot.gd")

var _prev: GameSession


func before_each() -> void:
	_prev = Game.session
	Game.session = GameSession.create_new({"seed": 4711, "game_mode": "survival"})


func after_each() -> void:
	Game.session = _prev


func _def(kind: String) -> PoiDef:
	var raw: Dictionary = {"id": "window_test", "name": "Window Test", "tier": 1, "footprint": [12, 12],
		"style": {"floor_height": 0.15, "scatter": {"density": 0.0}, "roof": {"type": "flat"}},
		"levels": [{"level": 0, "plan": ["AAAA", "AAAA", "AAAA"], "rooms": {"A": {}}}],
		"openings": [{"id": "way_in", "at": [1, 2], "side": "S", "type": kind, "state": "broken"}],
		"route": [{"at": [1, 4]}, {"at": [1, 1]}],
		"loot_room": {"room": "A", "level": 0}}
	var d := PoiDef.new()
	assert_eq(d.parse(raw, &"poi", "test"), PackedStringArray())
	return d


func test_a_one_metre_window_can_be_vaulted() -> void:
	var pd: PoiDef = _def("window")
	var inst: PoiInstance = PoiBuilder.build(PoiLayout.compile(pd), &"test/window")
	add_child_autofree(inst)
	var ground := StaticBody3D.new()
	var gs := CollisionShape3D.new()
	var gb := BoxShape3D.new()
	gb.size = Vector3(60, 1, 60)
	gs.shape = gb
	gs.position = Vector3(0, -0.5, 0)
	ground.add_child(gs)
	add_child_autofree(ground)
	var p: Player = (load("res://src/player/player.tscn") as PackedScene).instantiate() as Player
	add_child_autofree(p)
	p.bind_state(Game.session.local_player())
	p.god_mode = true
	var layout: PoiLayout = inst.layout
	var op: Dictionary = layout.opening("way_in")
	# The window's wall edge: south side of cell (1, 2) -> world z = origin.y + 3, x centre = origin.x + 1.5.
	var wx: float = layout.origin.x + 1.5
	var wz: float = layout.origin.y + 3.0
	p.global_position = Vector3(wx, 0.05, wz + 0.75)
	p.rotation.y = 0.0  # facing -Z, toward the window
	for i: int in 10:
		await get_tree().physics_frame
	gut.p("opening %s, player at %s" % [op, p.global_position])
	var started: bool = p.call(&"_try_vault")
	assert_true(started, "a vault starts at a 0.7 x 1.1 m kit window")
	for i: int in 60:
		await get_tree().physics_frame
	assert_lt(p.global_position.z, wz - 0.3, "and carries the body inside (z %.2f vs the wall at %.2f)" % [p.global_position.z, wz])
