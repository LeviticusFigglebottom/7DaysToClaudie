extends GutTest
## Throwables and fire (ADR-0057): a thrown stone lands as a distraction where it falls (the
## Hollowed go there, not to the thrower; loud landings bolt deer), a throw charges between its
## tap and full speed, the molotov is craftable from a bottle, a fuel and a rag, and its ground
## fire burns the Hollowed, wildlife and players standing in it, nobody outside it, and goes out.

const PLAYER_SCENE: String = "res://src/player/player.tscn"

var _prev: GameSession
var _stimuli: Stimuli
var _manager: WildlifeManager
var _knows_all: Callable = func(_r: RecipeDef) -> bool: return true


func before_each() -> void:
	_prev = Game.session
	Game.session = GameSession.create_new({"seed": 5757, "game_mode": "survival"})
	_stimuli = Stimuli.new()
	add_child_autofree(_stimuli)
	_stimuli.recenter(Vector3.ZERO)
	_manager = WildlifeManager.new()
	add_child_autofree(_manager)
	_manager.setup_world(null)


func after_each() -> void:
	Game.session = _prev


func _player_at(pos: Vector3) -> Player:
	var p: Player = (load(PLAYER_SCENE) as PackedScene).instantiate() as Player
	add_child_autofree(p)
	p.bind_state(Game.session.local_player())
	p.global_position = pos
	p.state.position = pos
	return p


func _hollow_at(id: String, pos: Vector3) -> Enemy:
	var e := Enemy.new()
	e.setup(StringName(id), Content.enemy(&"hollow"), null, {"tier": "normal"})
	add_child_autofree(e)
	e.global_position = pos
	return e


func _deer_at(pos: Vector3, band: String) -> Animal:
	var d := Content.get_def(&"wildlife", &"white_tailed_deer") as WildlifeDef
	var herd: Array = _manager.spawn_band(d, {"id": StringName(band), "def": d.id, "pos": Vector2(pos.x, pos.z), "count": 1, "seed": 3})
	var a: Animal = herd[0]
	a.global_position = pos
	return a


func _land_stone(at: Vector3, thrower: StringName, from: Vector3) -> ThrownItem:
	var t := ThrownItem.new()
	t.item_id = &"stone"
	t.thrower = thrower
	t.origin = from
	add_child_autofree(t)
	t.global_position = at
	t.impact(null)
	return t


func _sounds_of(kind: StringName) -> Array[Stimuli.SoundEvent]:
	var out: Array[Stimuli.SoundEvent] = []
	for s: Stimuli.SoundEvent in _stimuli.sounds:
		if s.kind == kind:
			out.append(s)
	return out


# --- Stones -------------------------------------------------------------------------------------

func test_a_stone_lands_as_a_distraction_at_the_landing_point() -> void:
	var at := Vector3(6.0, 0.0, -9.0)
	_land_stone(at, &"p:thrower", Vector3(-30.0, 0.0, 0.0))
	var heard: Array[Stimuli.SoundEvent] = _sounds_of(ThrownItem.NOISE_KIND)
	assert_eq(heard.size(), 1, "one distraction where it landed")
	var stone: ItemDef = Content.item(&"stone")
	assert_almost_eq(heard[0].pos.distance_to(at), 0.0, 0.01, "at the landing point, not the thrower")
	assert_almost_eq(heard[0].loudness, stone.equip_num("noise", -1.0) * _stimuli.weather_noise_mask, 0.001, "as loud as the item says")
	assert_eq(heard[0].source_id, &"p:thrower")


func test_a_landed_stone_only_makes_its_noise_once() -> void:
	var t: ThrownItem = _land_stone(Vector3(2.0, 0.0, 2.0), &"p:thrower", Vector3.ZERO)
	t.impact(null)
	assert_eq(_sounds_of(ThrownItem.NOISE_KIND).size(), 1, "bounces after the first contact are quiet")


func test_hollowed_investigate_where_the_stone_landed_not_the_thrower() -> void:
	var e: Enemy = _hollow_at("test:hollow", Vector3(0, 0, 0))
	# The thrower is far off and out of sight: the stone is all it can know of.
	var p: Player = _player_at(Vector3(-400, 0, 0))
	await get_tree().physics_frame
	e.state = Enemy.State.IDLE
	e._heard_seq = _stimuli.last_seq()
	var at := Vector3(7.0, 0.0, 4.0)
	_land_stone(at, p.state.id, p.global_position)
	e._perceive(p, e.global_position.distance_to(p.global_position))
	assert_eq(e.state, Enemy.State.INVESTIGATE, "the Hollow goes to see what fell")
	assert_lt(Vector2(e.target_pos.x - at.x, e.target_pos.z - at.z).length(), 3.0, "to where it fell")
	assert_gt(e.target_pos.distance_to(p.global_position), 300.0, "not toward the thrower")


func test_a_stone_out_of_earshot_is_not_heard() -> void:
	var e: Enemy = _hollow_at("test:hollow_far", Vector3(0, 0, 0))
	var p: Player = _player_at(Vector3(-400, 0, 0))
	await get_tree().physics_frame
	e.state = Enemy.State.IDLE
	e._heard_seq = _stimuli.last_seq()
	_land_stone(Vector3(60.0, 0.0, 0.0), p.state.id, p.global_position)
	e._perceive(p, e.global_position.distance_to(p.global_position))
	assert_eq(e.state, Enemy.State.IDLE, "60 m off a stone is not heard")


func test_loud_landings_bolt_deer_quiet_ones_only_alert_them() -> void:
	var deer := Content.get_def(&"wildlife", &"white_tailed_deer") as WildlifeDef
	var stone: float = ThrownItem.landing_noise(&"stone")
	var molotov: float = ThrownItem.landing_noise(&"molotov")
	assert_lt(stone, deer.sense("bolt_loudness", 25.0), "a stone is below a deer's bolt loudness")
	assert_gte(molotov, deer.sense("bolt_loudness", 25.0), "a shattering molotov is above it")
	assert_eq(WildlifeBrain.sound_threat(deer, molotov, 12.0), WildlifeBrain.Threat.FLEE, "a bottle bursting 12 m off bolts it")
	assert_eq(WildlifeBrain.sound_threat(deer, stone, 8.0), WildlifeBrain.Threat.ALERT, "a stone 8 m off makes it look up")
	# The wildlife manager listens to landings like any loud sound (it drops those under 10 m).
	assert_gte(stone, 10.0, "loud enough for wildlife to notice at all")


# --- The throw ----------------------------------------------------------------------------------

func test_a_throw_charges_from_tap_to_full_speed() -> void:
	var stone: ItemDef = Content.item(&"stone")
	var speeds: Array = stone.equip["throw_speed"]
	assert_almost_eq(ThrowHand.throw_speed(stone, ThrowHand.charge_power(stone, 0.0)), float(speeds[0]), 0.001, "a tap")
	assert_almost_eq(ThrowHand.throw_speed(stone, ThrowHand.charge_power(stone, 10.0)), float(speeds[1]), 0.001, "held: full")
	var half: float = ThrowHand.throw_speed(stone, ThrowHand.charge_power(stone, stone.equip_num("charge_time") * 0.5))
	assert_almost_eq(half, (float(speeds[0]) + float(speeds[1])) * 0.5, 0.001, "halfway")
	var cfg: Dictionary = ViewModelHolds.config()
	assert_eq(ThrowHand.use_for(&"stone", cfg), &"throw_stone", "a stone has its own throw")
	assert_eq(ThrowHand.use_for(&"held", cfg), &"throw", "anything else the plain one")
	var f: float = ThrowHand.windup_fraction(&"throw_molotov", cfg)
	assert_true(f > 0.2 and f < 0.6, "the arm is drawn back partway through the throw")


# --- The molotov --------------------------------------------------------------------------------

func test_the_molotov_recipe_validates_and_crafts() -> void:
	assert_eq(Content.errors().size(), 0, "content loads clean: %s" % ", ".join(Content.errors()))
	for rid: StringName in [&"molotov", &"molotov_rotgut"]:
		var r: RecipeDef = Content.recipe(rid)
		assert_not_null(r, "recipe %s" % rid)
		assert_eq(r.result, &"molotov")
		for ing: Variant in r.ingredients:
			assert_not_null(Content.item(StringName(str(ing))), "ingredient %s is an item" % ing)
	var m: ItemDef = Content.item(&"molotov")
	assert_true(ThrowHand.needs_light(m), "lit before it is thrown")
	assert_false(GroundFire.spec_for(ThrownItem.ground_fire_of(&"molotov")).is_empty(), "its ground fire is in fire.json")
	var r2: RecipeDef = Crafting.match_recipe({&"glass_bottle": 1, &"kerosene": 1, &"cloth": 1}, &"", _knows_all)
	assert_not_null(r2, "bottle + kerosene + rag on the slate")
	var inv := Inventory.new()
	inv.add_item(&"glass_bottle", 1)
	inv.add_item(&"kerosene", 1)
	inv.add_item(&"cloth", 2)
	var res: Crafting.Result = Crafting.craft(r2, inv, &"")
	assert_true(res.ok, res.reason)
	assert_eq(inv.count_of(&"molotov"), 1)
	assert_eq(inv.count_of(&"cloth"), 1)
	assert_eq(inv.count_of(&"glass_bottle"), 0)


func test_an_unlit_molotov_just_breaks() -> void:
	var t := ThrownItem.new()
	t.item_id = &"molotov"
	add_child_autofree(t)
	t.global_position = Vector3(3, 0, 3)
	t.impact(null)
	assert_eq(get_tree().get_nodes_in_group(&"ground_fires").size(), 0, "no fire without a lit rag")
	assert_true(t.is_queued_for_deletion(), "the bottle is gone")
	assert_eq(_sounds_of(ThrownItem.NOISE_KIND).size(), 1, "but it is heard breaking")


func test_a_lit_molotov_shatters_into_a_ground_fire() -> void:
	var t := ThrownItem.new()
	t.item_id = &"molotov"
	t.lit = true
	t.thrower = &"p:thrower"
	add_child_autofree(t)
	t.global_position = Vector3(3, 0, 3)
	t.impact(null)
	var fires: Array[Node] = get_tree().get_nodes_in_group(&"ground_fires")
	assert_eq(fires.size(), 1, "it bursts into flames")
	var f: GroundFire = fires[0]
	assert_almost_eq(Vector2(f.global_position.x - 3.0, f.global_position.z - 3.0).length(), 0.0, 0.01, "where it broke")
	assert_eq(f.source_id, &"p:thrower")
	assert_eq(_sounds_of(&"fire").size(), 1, "the whoomp is a sound the Hollowed hear")
	assert_true(_stimuli.lights.size() >= 1, "and a light they see by")
	f.queue_free()


func test_a_ground_fire_burns_what_stands_in_it_and_goes_out() -> void:
	var inside_e: Enemy = _hollow_at("test:burning", Vector3(1.0, 0.0, 0.0))
	var outside_e: Enemy = _hollow_at("test:watching", Vector3(7.0, 0.0, 0.0))
	var inside_a: Animal = _deer_at(Vector3(-1.2, 0.0, 0.6), "w:test:in")
	var outside_a: Animal = _deer_at(Vector3(-8.0, 0.0, -3.0), "w:test:out")
	var p: Player = _player_at(Vector3(0.4, 0.0, -1.0))
	var far_p_hp: float = 0.0
	var fire: GroundFire = GroundFire.spawn(self, Vector3.ZERO, &"molotov", &"p:thrower", Vector3(-12, 0, 0))
	assert_not_null(fire)
	fire.set_physics_process(false)  # stepped by hand below
	await get_tree().physics_frame
	await get_tree().physics_frame
	var hp := {"ie": inside_e.health, "oe": outside_e.health, "ia": inside_a.health, "oa": outside_a.health,
		"p": p.state.stats.health}
	far_p_hp = p.state.stats.health
	# Two seconds in the flames.
	for i: int in 4:
		fire.advance(0.5)
	var dps: float = float(fire.spec["dps"])
	assert_lt(inside_e.health, float(hp["ie"]) - dps * 0.5, "the Hollow standing in it burns")
	assert_lt(inside_a.health, float(hp["ia"]) - dps, "so does the deer")
	assert_lt(p.state.stats.health, far_p_hp, "and the player")
	assert_eq(outside_e.health, float(hp["oe"]), "a Hollow 7 m off does not")
	assert_eq(outside_a.health, float(hp["oa"]), "nor a deer 8 m off")
	assert_true(fire.is_burning())
	# It burns its duration, dies down, and is out.
	fire.advance(fire.duration + fire.fade)
	assert_false(fire.is_burning(), "out after its duration")
	var after := {"ie": inside_e.health, "ia": inside_a.health}
	for i: int in 6:
		fire.advance(0.5)
	assert_eq(inside_e.health, float(after["ie"]), "an out fire burns nobody")
	assert_eq(inside_a.health, float(after["ia"]))
	assert_eq(_stimuli.lights.size(), 0, "its light is gone")
	fire.advance(100.0)
	assert_true(fire.is_queued_for_deletion(), "and once the smoke clears it is gone")
