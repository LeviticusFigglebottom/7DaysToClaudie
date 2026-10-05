extends GutTest
## First person in the player scene (ADR-0029): equipping an item sets its hold class on the
## viewmodel and the arms' loop; a swing connects at its style's contact frame; a raised guard
## takes its share of a blow from the front (not from behind), costing stamina; reading the tether
## and guarding switch the arms' loop; the tether UI draws on the wrist unit and follows the wrist
## down when a swing lowers it.

const PLAYER_SCENE: String = "res://src/player/player.tscn"

var _player: Player


func before_each() -> void:
	_player = (load(PLAYER_SCENE) as PackedScene).instantiate() as Player
	_player.input_enabled = false
	add_child_autofree(_player)
	_player.bind_state(PlayerState.new())
	_player.state.stats.stamina = 100.0


func _equip(id: StringName) -> void:
	var ps: PlayerState = _player.state
	ps.inventory.add_item(id, 1)
	ps.toolbelt[0] = id
	ps.equipped_slot = 0
	_player.equipment.select_slot(0)


func _blow(amount: float, from_front: bool) -> DamageInfo:
	var info := DamageInfo.make(amount, &"zombie", &"zombie", &"qa_hollow")
	var fwd: Vector3 = -_player.global_transform.basis.z
	info.source_pos = _player.global_position + (fwd if from_front else -fwd) * 1.2
	info.tool_power = {"bleed": 0.0, "infection": 0.0}
	return info


func test_equip_sets_the_hold() -> void:
	_equip(&"stone_club")
	var vm: ViewModel = _player.equipment.viewmodel
	assert_not_null(vm)
	assert_eq(vm.hold_class, &"club")
	if vm.has_action(&"fp_club"):
		assert_eq(vm.base_action(), &"fp_club", "the arms hold the club")
		vm.set_guard(true)
		assert_eq(vm.base_action(), &"fp_club_guard", "guarding raises the club across")
		vm.set_guard(false)
		vm.set_tether_raised(true)
		assert_eq(vm.base_action(), &"fp_club_tether", "reading the wrist with the club in the other hand")
		vm.set_tether_raised(false)


func test_swing_connects_at_its_contact_frame() -> void:
	_equip(&"stone_club")
	_player.equipment.primary()
	var def: ItemDef = Content.item(&"stone_club")
	assert_almost_eq(_player.equipment.get(&"_swing_len"), def.equip_num("attack_time"), 1e-6, "attack_time stays authoritative")
	assert_almost_eq(_player.equipment.get(&"_hit_frac"), ViewModelHolds.impact_fraction(&"bash"), 1e-6)
	assert_lt(_player.state.stats.stamina, 100.0, "the swing cost its stamina")


func test_guard_takes_its_share_from_the_front() -> void:
	_equip(&"stone_club")
	var share: float = ViewModelHolds.block_share(Content.item(&"stone_club"), &"club")
	var eq: PlayerEquipment = _player.equipment
	eq.call(&"_update_guard", true)
	assert_true(eq.guarding, "Block raises the club's guard")
	var hp: float = _player.state.stats.health
	_player.take_damage(_blow(20.0, true))
	assert_almost_eq(hp - _player.state.stats.health, 20.0 * (1.0 - share), 0.01, "the guard took its share")
	assert_lt(_player.state.stats.stamina, 100.0, "blocking costs stamina")
	hp = _player.state.stats.health
	_player.take_damage(_blow(20.0, false))
	assert_almost_eq(hp - _player.state.stats.health, 20.0, 0.01, "a blow from behind gets through")
	eq.call(&"_update_guard", false)
	hp = _player.state.stats.health
	_player.take_damage(_blow(10.0, true))
	assert_almost_eq(hp - _player.state.stats.health, 10.0, 0.01, "guard down: all of it")


func test_food_has_no_guard() -> void:
	_equip(&"canned_beans")
	_player.equipment.call(&"_update_guard", true)
	assert_false(_player.equipment.guarding, "Block is for eating when food is in hand")
	assert_eq(_player.equipment.viewmodel.hold_class, &"food")


func test_tether_ui_rides_the_wrist() -> void:
	var vm: ViewModel = _player.equipment.viewmodel
	if not vm.has_tether_screen():
		pending("arms not built (make assets)")
		return
	_equip(&"stone_club")
	# GameUI puts the tether beside the viewmodel under the camera.
	var t := Tether.new()
	_player.camera.add_child(t)
	assert_true(bool(t.get(&"_on_arms")), "the tether UI draws on the arms' wrist unit")
	var screen: StandardMaterial3D = vm.get(&"_screen_mat") as StandardMaterial3D
	assert_not_null(screen)
	if screen != null:
		assert_eq(screen.emission_operator, BaseMaterial3D.EMISSION_OP_MULTIPLY, "the screen glows with the UI's own colours, not white")
	t.toggle()
	vm.set_tether_raised(true)
	assert_true(vm.tether_raised())
	_player.equipment.primary()
	assert_false(vm.tether_raised(), "a swing lowers the wrist")
	t._process(0.016)
	assert_false(t.raised, "and the tether UI follows, so T raises it again")
