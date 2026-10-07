extends GutTest
## The bolt-action hunting rifle in the player's hands (ADR-0057): its content checks out (item,
## ammo, hold, uses, rare loot and trader stock); R loads it a round at a time up to its magazine
## (firing stops that; the revolver still loads all at once) and right mouse no longer reloads;
## each shot is followed by the bolt cycle before the next; a shot down the sights through the
## same hitscan as the revolver hurts a Hollowed and a deer, and is heard far and wide.

const PLAYER_SCENE: String = "res://src/player/player.tscn"

var _prev: GameSession
var _stimuli: Stimuli
var _player: Player


func before_each() -> void:
	_prev = Game.session
	Game.session = GameSession.create_new({"seed": 5701, "game_mode": "survival"})
	_stimuli = Stimuli.new()
	add_child_autofree(_stimuli)
	_stimuli.recenter(Vector3.ZERO)
	_player = (load(PLAYER_SCENE) as PackedScene).instantiate() as Player
	_player.input_enabled = false
	add_child_autofree(_player)
	_player.bind_state(Game.session.local_player())
	_player.global_position = Vector3.ZERO
	_player.rotation = Vector3.ZERO
	_player.freeze(true)


func after_each() -> void:
	Game.session = _prev


func _equip(id: StringName, ammo: int = 0) -> PlayerEquipment:
	var ps: PlayerState = _player.state
	ps.inventory.add_item(id, 1)
	var def: ItemDef = Content.item(id)
	if ammo > 0:
		ps.inventory.add_item(StringName(str(def.equip["ammo"])), ammo)
	ps.toolbelt[0] = id
	ps.equipped_slot = 0
	_player.equipment.select_slot(0)
	return _player.equipment


func _loaded(id: StringName) -> int:
	return int(_player.state.inventory.first(id).data.get("loaded", 0))


func test_the_rifle_content_checks_out() -> void:
	var rifle: ItemDef = Content.item(&"hunting_rifle")
	assert_not_null(rifle)
	assert_not_null(Content.item(&"ammo_308"))
	assert_eq(str(rifle.equip["kind"]), "ranged")
	assert_eq(StringName(str(rifle.equip["ammo"])), &"ammo_308")
	assert_eq(ViewModelHolds.hold_class(rifle), &"rifle", "the long-gun hold")
	assert_eq(ViewModelHolds.item_hand(&"rifle"), "L", "the support hand holds it: the right works the bolt")
	assert_eq(ViewModelHolds.problems().size(), 0, "\n".join(ViewModelHolds.problems()))
	var uses: Dictionary = ViewModelHolds.config()["uses"]
	for u: String in ["fire_rifle", "reload_rifle_open", "reload_rifle", "reload_rifle_close", "inspect_rifle"]:
		assert_true(uses.has(u), "use %s" % u)
	assert_true((uses["fire_rifle"] as Dictionary).has("parts"), "the bolt moves in the bolt cycle")
	assert_gt(rifle.equip_num("noise"), Content.item(&"revolver").equip_num("noise"), "louder than the revolver")
	assert_gt(rifle.equip_num("range"), Content.item(&"revolver").equip_num("range"), "and reaches further")


func test_the_rifle_is_rare_loot() -> void:
	var seen := {}
	for table: StringName in [&"civic_gun_safe", &"wild_lookout_stores"]:
		var rng := RandomNumberGenerator.new()
		rng.seed = 99
		var n: int = 0
		var rifles: int = 0
		for i: int in 300:
			for s: ItemStack in LootRoller.roll(table, LootRoller.Context.new(4, 10, rng)):
				seen[s.item_id] = true
				if s.item_id == &"hunting_rifle":
					rifles += 1
			n += 1
		assert_gt(rifles, 0, "%s can hold a rifle" % table)
		assert_lt(rifles, n / 4, "%s: but sparingly" % table)
	assert_true(seen.has(&"ammo_308"), "and its rounds")
	var stocked: bool = false
	for t: TraderDef in Content.all(&"trader"):
		for e: Dictionary in t.stock:
			if StringName(str(e.get("item", ""))) == &"hunting_rifle":
				stocked = true
				assert_eq(int(e.get("rep_tier", 0)), 3, "only for the Program's trusted")
	assert_true(stocked, "a trader can sell one")


func test_r_loads_round_by_round_up_to_the_magazine() -> void:
	var eq: PlayerEquipment = _equip(&"hunting_rifle", 7)
	var def: ItemDef = Content.item(&"hunting_rifle")
	var rounds: RoundReload = eq.get(&"_rounds")
	eq.secondary()
	assert_false(eq.is_reloading(), "right mouse aims now; it doesn't reload")
	eq.reload()
	assert_true(eq.is_reloading())
	assert_eq(rounds.phase, RoundReload.Phase.OPEN, "the bolt opens first")
	rounds.step(def.equip_num("reload_open_time") + 0.01, eq)
	assert_eq(rounds.phase, RoundReload.Phase.ROUND)
	assert_eq(_loaded(&"hunting_rifle"), 0, "nothing in yet")
	var mag: int = int(def.equip["mag_size"])
	for i: int in mag:
		rounds.step(def.equip_num("reload_time") * 0.5, eq)
		assert_eq(_loaded(&"hunting_rifle"), i, "a round goes in when its motion ends")
		rounds.step(def.equip_num("reload_time") * 0.5 + 0.01, eq)
		assert_eq(_loaded(&"hunting_rifle"), i + 1, "one at a time")
	assert_eq(_loaded(&"hunting_rifle"), mag, "up to the magazine")
	assert_eq(_player.state.inventory.count_of(&"ammo_308"), 7 - mag, "the rest stay in the pack")
	assert_eq(rounds.phase, RoundReload.Phase.CLOSE, "full: the bolt closes")
	rounds.step(def.equip_num("reload_close_time") + 0.01, eq)
	assert_false(eq.is_reloading())
	eq.reload()
	assert_false(eq.is_reloading(), "a full magazine takes no more")


func test_firing_stops_a_reload_and_keeps_the_rounds_in() -> void:
	var eq: PlayerEquipment = _equip(&"hunting_rifle", 4)
	var def: ItemDef = Content.item(&"hunting_rifle")
	var rounds: RoundReload = eq.get(&"_rounds")
	eq.reload()
	rounds.step(def.equip_num("reload_open_time") + 0.01, eq)
	rounds.step(def.equip_num("reload_time") + 0.01, eq)
	rounds.step(def.equip_num("reload_time") + 0.01, eq)
	assert_eq(_loaded(&"hunting_rifle"), 2)
	eq.primary()
	assert_eq(rounds.phase, RoundReload.Phase.CLOSE, "fire: the bolt closes on what's in")
	assert_eq(_loaded(&"hunting_rifle"), 2, "and that press didn't fire")
	rounds.step(def.equip_num("reload_close_time") + 0.01, eq)
	assert_false(eq.is_reloading())
	assert_eq(_player.state.inventory.count_of(&"ammo_308"), 2)


func test_the_revolver_reloads_on_r_all_at_once() -> void:
	var eq: PlayerEquipment = _equip(&"revolver", 10)
	eq.secondary()
	assert_false(eq.is_reloading(), "right mouse aims the revolver too")
	eq.reload()
	assert_true(eq.is_reloading())
	assert_false((eq.get(&"_rounds") as RoundReload).active(), "not round by round")
	eq.call(&"_finish_reload")
	assert_eq(_loaded(&"revolver"), 6, "the whole cylinder")


func test_the_bolt_cycle_gates_the_rate_of_fire() -> void:
	var eq: PlayerEquipment = _equip(&"hunting_rifle", 0)
	var def: ItemDef = Content.item(&"hunting_rifle")
	_player.state.inventory.first(&"hunting_rifle").data["loaded"] = 3
	eq.primary()
	assert_eq(_loaded(&"hunting_rifle"), 2, "a shot")
	var cycle: float = def.equip_num("attack_time") + def.equip_num("bolt_time")
	assert_almost_eq(float(eq.get(&"_cooldown")), cycle, 1e-4, "the next waits for the bolt")
	assert_gt(cycle, 1.0, "about a second between aimed shots")
	_equip(&"revolver", 0)
	_player.state.inventory.first(&"revolver").data["loaded"] = 1
	eq.set(&"_cooldown", 0.0)
	eq.primary()
	assert_lt(float(eq.get(&"_cooldown")), cycle * 0.5, "a revolver fires again far sooner")


## Points the player's view at a world point.
func _look_at(p: Vector3) -> void:
	var eye: Vector3 = _player.camera.global_position
	var d: Vector3 = p - eye
	_player.rotation.y = atan2(-d.x, -d.z)
	_player.head.rotation.x = atan2(d.y, Vector2(d.x, d.z).length())


func _fire_aimed_at(p: Vector3) -> void:
	var eq: PlayerEquipment = _equip(&"hunting_rifle", 0)
	_player.state.inventory.first(&"hunting_rifle").data["loaded"] = 5
	_player.aim.update(5.0, true, &"hunting_rifle")
	assert_true(_player.aim.fully_aimed())
	await get_tree().physics_frame
	await get_tree().physics_frame
	_look_at(p)
	eq.primary()


func test_a_rifle_shot_hurts_a_hollowed_and_is_heard() -> void:
	var e := Enemy.new()
	e.setup(&"test:rifle_target", Content.enemy(&"hollow"), null, {"tier": "normal"})
	add_child_autofree(e)
	e.global_position = Vector3(0, 0, -12)
	var hp: float = e.health
	await _fire_aimed_at(e.global_position + Vector3.UP * 1.1)
	assert_lt(e.health, hp, "the round went in")
	var heard: Stimuli.SoundEvent = null
	for s: Stimuli.SoundEvent in _stimuli.sounds:
		if s.kind == &"gunshot":
			heard = s
	assert_not_null(heard, "the shot is in the stimulus field")
	if heard != null:
		assert_almost_eq(heard.loudness, Content.item(&"hunting_rifle").equip_num("noise") * _stimuli.weather_noise_mask, 0.01)


func test_a_rifle_shot_drops_a_deer() -> void:
	var manager := WildlifeManager.new()
	add_child_autofree(manager)
	manager.setup_world(null)
	var d := Content.get_def(&"wildlife", &"white_tailed_deer") as WildlifeDef
	var herd: Array = manager.spawn_band(d, {"id": &"w:rifle:0", "def": d.id, "pos": Vector2(0, -15), "count": 1, "seed": 3})
	assert_eq(herd.size(), 1)
	var a: Animal = herd[0]
	a.global_position = Vector3(0, 0, -15)
	var hp: float = a.health
	await _fire_aimed_at(a.global_position + Vector3.UP * 0.9)
	assert_true(a.health < hp or not a.is_alive(), "hit through the same hitscan as the revolver")
