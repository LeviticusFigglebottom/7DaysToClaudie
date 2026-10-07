extends GutTest
## Ashen war parties and per-camp standing (ADR-0048 phase 2; TD-189, TD-190) against real nodes:
## a firebrand's blows on a structure are fire (a wooden piece takes its fire multiplier), every
## war party carries one, its brand is a light that never frightens its own band; each camp keeps
## its own anger (its people killed, a kin camp wiped, fading at dawn), a raid comes out of the
## ring toward the angriest living camp, and a wiped camp sends nothing.

const PLAYER_SCENE: String = "res://src/player/player.tscn"
const BASE := Vector3(0, 0, 0)
const CAMP_A := Vector3(300, 0, 0)
const CAMP_B := Vector3(0, 0, -300)


class FakeWorld:
	extends Node3D
	var ai: Node = null
	var pois: Node = null
	var player: Node3D = null
	var building: Node = null
	var traders: Node = null
	var ashen: Node = null

	func height_at(_x: float, _z: float) -> float:
		return 0.0


var _prev: GameSession
var _world: FakeWorld
var _ai: AIDirector
var _bm: BuildingManager
var _dir: AshenDirector
var _p: Player


func before_each() -> void:
	_prev = Game.session
	Game.session = GameSession.create_new({"seed": 4471, "game_mode": "survival"})
	_world = FakeWorld.new()
	add_child_autofree(_world)
	_ai = AIDirector.new()
	_world.add_child(_ai)
	_world.ai = _ai
	_bm = BuildingManager.new()
	_world.add_child(_bm)
	# No world here: the manager's input/preview loop stays off.
	_bm.set_physics_process(false)
	_world.building = _bm
	var ground := StaticBody3D.new()
	var cs := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = Vector3(400, 1, 400)
	cs.shape = shape
	ground.add_child(cs)
	_world.add_child(ground)
	ground.global_position = Vector3(0, -0.5, 0)
	_p = (load(PLAYER_SCENE) as PackedScene).instantiate() as Player
	_p.input_enabled = false
	_world.add_child(_p)
	_p.bind_state(Game.session.local_player())
	_p.global_position = BASE
	_world.player = _p
	_dir = AshenDirector.new()
	_world.add_child(_dir)
	_world.ashen = _dir
	_dir.setup_world(_world)
	_dir.buildings_source = func() -> Array:
		return [{"id": "poi:camp_a", "def": "ashen_highcamp", "pos": CAMP_A}, {"id": "poi:camp_b", "def": "ashen_highcamp", "pos": CAMP_B}]


func after_each() -> void:
	Game.session = _prev


func _piece(def_id: StringName, id: String, at: Vector3) -> StructurePiece:
	var def: StructureDef = Content.structure(def_id)
	return _bm._spawn_piece(StringName(id), def, Transform3D(Basis.IDENTITY, at), def.hp)


func _spawn(id: StringName, at: Vector3, opts: Dictionary = {}) -> Enemy:
	var o: Dictionary = {"tier": "normal", "authored": true}
	o.merge(opts, true)
	return _ai.spawn(id, at, o)


func _kill(e: Enemy) -> void:
	var info := DamageInfo.make(9999.0, &"pierce", &"melee", _p.state.id)
	info.hit_pos = e.global_position + Vector3.UP
	e.take_damage(info)


## Hit points one blow of `who` takes off a fresh `def_id` piece.
func _blow(who: StringName, def_id: StringName, n: int) -> float:
	var piece: StructurePiece = _piece(def_id, "p:%s:%d" % [who, n], Vector3(20 + n * 4, 0, 20))
	var e: Enemy = _spawn(who, piece.global_position + Vector3(0, 0, 1.5), {"job": "raid", "goal": BASE})
	var before: float = piece.hp
	e.break_target = piece
	e._strike_structure()
	return before - piece.hp


func test_a_firebrands_blow_on_a_wooden_piece_is_fire() -> void:
	var raider: float = _blow(&"ashen_raider", &"log_piece", 0)
	var brand: float = _blow(&"ashen_firebrand", &"log_piece", 1)
	var dm: Dictionary = Content.structure(&"log_piece").damage_mult
	var fire: float = float(dm.get("fire", 1.0))
	var zombie: float = float(dm.get("zombie", 1.0))
	assert_gt(fire, zombie, "wood burns more than it is broken")
	assert_eq(Content.enemy(&"ashen_firebrand").atk("structure_damage", 0.0), Content.enemy(&"ashen_raider").atk("structure_damage", 0.0),
		"the same arm behind both blows")
	assert_gt(raider, 0.0)
	assert_gt(brand, raider, "the brand does more to wood")
	assert_almost_eq(brand / raider, fire / zombie, 0.001, "by the fire multiplier in place of the Hollowed's")
	# Stone doesn't burn.
	var stone: float = _blow(&"ashen_firebrand", &"campfire", 2)
	assert_eq(stone, 0.0, "a stone fire ring takes nothing from fire")


func test_every_war_party_carries_a_firebrand() -> void:
	var fd: FactionDef = _dir.fd
	var war: int = 0
	for day: int in range(5, 60):
		var r3: Dictionary = AshenBrain.raid_roll(fd, 4471, day, 3, 30, false)
		if not r3.is_empty():
			war += 1
			assert_true((r3["members"] as Array).has("ashen_firebrand"), "day %d: a war party has its firebrand" % day)
		var r2: Dictionary = AshenBrain.raid_roll(fd, 4471, day, 2, 30, false)
		if not r2.is_empty():
			assert_false((r2["members"] as Array).has("ashen_firebrand"), "day %d: a plain raid has none" % day)
	assert_gt(war, 0, "some war parties rolled")
	assert_eq(AshenBrain.raid_roll(fd, 4471, 9, 3, 30, false), AshenBrain.raid_roll(fd, 4471, 9, 3, 30, false), "deterministic")


func test_the_brand_lights_but_never_frightens_its_band() -> void:
	var fb: Enemy = _spawn(&"ashen_firebrand", Vector3(30, 0, 0), {"job": "raid", "goal": BASE})
	var mate: Enemy = _spawn(&"ashen_raider", Vector3(31, 0, 0), {"job": "raid", "goal": BASE})
	await get_tree().physics_frame
	assert_not_null(fb.tribe.brand, "it carries a lit brand")
	assert_true(fb.tribe.brand.visible)
	assert_null(mate.tribe.brand)
	mate.tribe.tick(1.0, _p)
	assert_eq(mate.tribe._fear, 0.0, "its own fire is not the outsider's")
	assert_eq(mate.tribe.morale, 1.0)
	_kill(fb)
	assert_false(fb.tribe.brand.visible, "the brand goes out when it falls")


func test_a_camp_holds_its_dead_against_the_outsider() -> void:
	var cfg: Dictionary = _dir.fd.camp_for(&"ashen_highcamp")
	var res: Array = _dir.spawn_residents("poi:camp_a", cfg, CAMP_A)
	await get_tree().physics_frame
	assert_eq(_dir.camp_anger("poi:camp_a"), 0.0)
	var hostility: float = _dir.hostility()
	_kill(res[0])
	var gain: float = float(_dir.fd.standing["anger"]["kill"])
	assert_almost_eq(_dir.camp_anger("poi:camp_a"), gain, 0.001, "its own people")
	assert_eq(_dir.camp_anger("poi:camp_b"), 0.0, "not another camp's")
	assert_gt(_dir.hostility(), hostility, "the world-wide hostility still rises too")
	# It fades a little each dawn.
	_dir._on_day_started(6)
	assert_almost_eq(_dir.camp_anger("poi:camp_a"), gain - float(_dir.fd.standing["decay_per_day"]), 0.001, "fading at dawn")
	# Wiped out: it sends nothing, and its kin take up the grudge.
	for e: Variant in res:
		if (e as Enemy).is_alive():
			_kill(e)
	assert_true(bool(_dir.camp_state("poi:camp_a").get("wiped", false)))
	assert_almost_eq(_dir.camp_anger("poi:camp_b"), float(_dir.fd.standing["anger"]["kin_wiped"]), 0.001, "the kin camp")
	assert_eq(str(_dir.source_camp().get("id", "")), "poi:camp_b")


func test_a_raid_comes_from_the_angriest_living_camp() -> void:
	_piece(&"storage_crate", "p:a", Vector3(3, 0, 0))
	_piece(&"workbench", "p:b", Vector3(-3, 0, 2))
	_dir.camp_state("poi:camp_a")["anger"] = 12.0
	_dir.camp_state("poi:camp_b")["anger"] = 30.0
	var r: Dictionary = _dir.debug_raid(4)
	assert_false(r.is_empty())
	assert_eq(str(r["camp"]), "poi:camp_b")
	var from: Vector3 = r["from"]
	var want: float = AshenDirector.camp_bearing(r["target"], CAMP_B)
	var got: float = atan2(from.z - (r["target"] as Vector3).z, from.x - (r["target"] as Vector3).x)
	assert_lt(absf(angle_difference(want, got)), deg_to_rad(float(_dir.fd.standing["spread"])) + 0.01, "out of the ring toward that camp")
	for e: Variant in r["members"]:
		assert_eq((e as Enemy).tribe.camp_id, "poi:camp_b", "its people")
	# Saved with the raid, and back after a load.
	var live: Dictionary = _dir.live_state()
	assert_eq(str(live["raid"]["camp"]), "poi:camp_b")


func test_a_wiped_camp_sends_nothing() -> void:
	_piece(&"storage_crate", "p:a", Vector3(3, 0, 0))
	_dir.camp_state("poi:camp_b")["anger"] = 80.0
	_dir.camp_state("poi:camp_b")["wiped"] = true
	assert_true(_dir.source_camp().is_empty(), "the dead send no one")
	var r: Dictionary = _dir.debug_raid(3)
	assert_eq(str(r["camp"]), "", "the raid comes from no camp")
	_dir.anger_camp("poi:camp_b", "kill")
	assert_almost_eq(_dir.camp_anger("poi:camp_b"), 80.0, 0.001, "and grows no angrier")
	# Below `lead`, a camp isn't set on the outsider yet.
	_dir.camp_state("poi:camp_a")["anger"] = float(_dir.fd.standing["lead"]) - 1.0
	assert_true(_dir.source_camp().is_empty())
	_dir.camp_state("poi:camp_a")["anger"] = float(_dir.fd.standing["lead"]) + 1.0
	assert_eq(str(_dir.source_camp().get("id", "")), "poi:camp_a")


func test_older_saves_have_no_anger_and_load_fine() -> void:
	Game.session.world.ashen["camps"] = {"poi:camp_a": {"dead": [0], "trespass_day": 3}}
	var w := WorldState.new()
	w.from_dict(JSON.parse_string(JSON.stringify(Game.session.world.to_dict())))
	Game.session.world = w
	assert_eq(_dir.camp_anger("poi:camp_a"), 0.0)
	assert_true(_dir.source_camp().is_empty())
	_dir._on_day_started(5)
	assert_false((w.ashen["camps"]["poi:camp_a"] as Dictionary).has("anger"), "dawn leaves a camp with no anger alone")
	_dir.anger_camp("poi:camp_a", "heat")
	assert_almost_eq(_dir.camp_anger("poi:camp_a"), float(_dir.fd.standing["anger"]["heat"]), 0.001)
