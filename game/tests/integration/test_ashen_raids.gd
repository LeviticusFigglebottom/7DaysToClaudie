extends GutTest
## Ashen raids, phase 2 (ADR-0048; TD-188, TD-189, TD-211) against real nodes: a raid on a base
## makes for its weakest piece along a flow field, out of the side its fires don't light; a raider
## at a garden bed takes the ripe crops and tramples the rest; a base left alone is still raided,
## broken into and left; a raid and a scout under way survive a save and resume as themselves.

const PLAYER_SCENE: String = "res://src/player/player.tscn"
const BASE := Vector3(0, 0, 0)


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


## Stands in for BuildingManager: the pieces by id, a radius query, and damage that takes hp off.
class FakeBuilding:
	extends Node3D
	var pieces: Dictionary = {}

	func pieces_in_radius(pos: Vector3, r: float) -> Array[StructurePiece]:
		var out: Array[StructurePiece] = []
		var ids: Array = pieces.keys()
		ids.sort()
		for id: Variant in ids:
			var p: StructurePiece = pieces[id]
			if is_instance_valid(p) and p.global_position.distance_to(pos) <= r + 2.5:
				out.append(p)
		return out

	func damage_piece(piece: StructurePiece, info: DamageInfo) -> void:
		piece.hp = maxf(0.0, piece.hp - info.amount)
		if piece.hp <= 0.0:
			pieces.erase(piece.piece_id)
			piece.queue_free()


var _prev: GameSession
var _world: FakeWorld
var _ai: AIDirector
var _b: FakeBuilding
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
	_b = FakeBuilding.new()
	_world.add_child(_b)
	_world.building = _b
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
	_dir = _new_director()


func after_each() -> void:
	Game.session = _prev


func _new_director() -> AshenDirector:
	var d := AshenDirector.new()
	_world.add_child(d)
	_world.ashen = d
	d.setup_world(_world)
	d.buildings_source = func() -> Array: return []
	return d


func _piece(id: String, def_id: StringName, at: Vector3, hp: float = -1.0) -> StructurePiece:
	var p := StructurePiece.new()
	p.setup(StringName(id), Content.structure(def_id), _b, hp)
	_b.add_child(p)
	p.global_position = at
	_b.pieces[StringName(id)] = p
	return p


## A garden bed with a ripe potato in plot 0 and a growing carrot in plot 1.
func _bed(id: String, at: Vector3) -> StructurePiece:
	var bed: StructurePiece = _piece(id, &"garden_bed", at)
	var st: Dictionary = FarmManager.state_of(bed)
	Farming.plant(st["plots"][0], Farming.crop(&"potato"))
	st["plots"][0]["grown"] = Farming.crop(&"potato").grow_days
	Farming.plant(st["plots"][1], Farming.crop(&"carrot"))
	return bed


func test_a_raid_makes_for_the_weakest_piece_along_the_flow() -> void:
	_piece("p:strong_a", &"storage_crate", Vector3(4, 0, 0), 900.0)
	var weak: StructurePiece = _piece("p:weak", &"storage_crate", Vector3(-4, 0, 3), 40.0)
	_piece("p:strong_b", &"workbench", Vector3(0, 0, -4), 900.0)
	assert_eq(_dir.weakest_piece(BASE, 60.0), weak, "the fewest hit points")
	var r: Dictionary = _dir.debug_raid(4)
	assert_false(r.is_empty())
	assert_true(bool(r["base"]), "it is a raid on the base")
	assert_eq(str(r["goal_piece"]), "p:weak")
	assert_not_null(_dir.flow)
	assert_true(_dir.flow.ready)
	# Walking the field from where they came out ends at the weak piece.
	var at: Vector3 = r["from"]
	for i: int in 400:
		var d: Vector3 = _dir.flow.direction_at(at)
		if d == Vector3.ZERO:
			break
		at += d * _dir.flow.cell
	assert_lt(Vector2(at.x - weak.global_position.x, at.z - weak.global_position.z).length(), 2.5, "the flow ends at the weak piece")
	var e: Enemy = r["members"][0]
	var wp: Vector3 = _dir.waypoint(e.global_position)
	assert_lt(wp.distance_to(weak.global_position), e.global_position.distance_to(weak.global_position), "each waypoint brings them closer")


func test_a_raider_in_reach_breaks_the_goal_then_the_next() -> void:
	var weak: StructurePiece = _piece("p:weak", &"storage_crate", Vector3(-4, 0, 3), 40.0)
	_piece("p:next", &"storage_crate", Vector3(4, 0, 0), 300.0)
	_dir._remember_base(_p)
	_p.global_position = Vector3(150, 0, 0)  # nobody home
	var r: Dictionary = _dir.debug_raid(2)
	assert_true(bool(r["base"]), "an empty base is still raided")
	var e: Enemy = r["members"][0]
	await get_tree().physics_frame
	e.global_position = weak.global_position + Vector3(1.2, 0, 0)
	e._set_state(Enemy.State.IDLE)
	_dir._steer(e)
	assert_eq(e.state, Enemy.State.BREAK)
	assert_eq(e.break_target, weak)
	weak.hp = 0.0
	assert_eq(str(_dir.raid["goal_piece"]), "p:weak")
	_dir._goal_piece()
	assert_eq(int(_dir.raid["broken"]), 1, "broken through")
	assert_eq(str(_dir.raid["goal_piece"]), "p:next", "on to the next weakest")


func test_a_raid_comes_from_the_dark_side() -> void:
	_piece("p:wall", &"storage_crate", Vector3(0, 0, 2), 200.0)
	var fire: StructurePiece = _piece("p:fire", &"campfire", Vector3(10, 0, 0))
	fire.lit = true
	var b: float = AshenDirector.dark_bearing(BASE, [fire.global_position])
	assert_almost_eq(absf(angle_difference(b, PI)), 0.0, 0.01, "the dark side is the far side from the fire")
	assert_true(is_nan(AshenDirector.dark_bearing(BASE, [])), "no fires, no side")
	assert_eq(_dir.weakest_piece(BASE, 60.0).piece_id, &"p:wall", "never a lit fire")
	for i: int in 3:
		var r: Dictionary = _dir.debug_raid(2)
		var from: Vector3 = r["from"]
		var c: Vector3 = r["target"]
		assert_lt((from - c).normalized().dot((fire.global_position - c).normalized()), -0.2, "they come in away from the fire")
		_dir._end_raid(false)


func test_a_raider_at_a_ripe_bed_takes_the_crops_and_tramples_the_rest() -> void:
	_piece("p:wall", &"storage_crate", Vector3(6, 0, 6), 200.0)
	var bed: StructurePiece = _bed("p:bed", Vector3(-3, 0, -3))
	var r: Dictionary = _dir.debug_raid(3)
	var jobs: Dictionary = r["jobs"]
	var looter: Enemy = r["members"][2]
	assert_eq(str(jobs[String(looter.entity_id)]), "garden", "the last of the band goes for the crops")
	await get_tree().physics_frame
	looter._set_state(Enemy.State.IDLE)
	_dir._steer(looter)
	assert_lt(looter.target_pos.distance_to(bed.global_position), 0.1, "making for the ripe bed")
	looter.global_position = bed.global_position + Vector3(0.6, 0, 0)
	_dir._raid_gardens(looter)
	var st: Dictionary = FarmManager.peek(bed)
	assert_true(Farming.is_empty_plot(st["plots"][0]), "the ripe potatoes are gone")
	assert_almost_eq(float(st["plots"][1]["health"]), 0.5, 0.001, "the carrots trampled")
	assert_eq(int(_dir.raid["looted"]), 1)
	_dir._raid_gardens(looter)
	assert_almost_eq(float(FarmManager.peek(bed)["plots"][1]["health"]), 0.5, 0.001, "trampled once a raid, not every tick")
	assert_null(_dir._ripe_bed(BASE), "nothing ripe left")


func test_a_base_left_alone_is_sacked_and_they_leave() -> void:
	_piece("p:weak", &"storage_crate", Vector3(-4, 0, 3), 40.0)
	_bed("p:bed", Vector3(3, 0, 3))
	_p.global_position = Vector3(10, 0, 0)
	_dir._remember_base(_p)
	_p.global_position = Vector3(170, 0, 0)
	var ended: Array = []
	Events.ashen_raid_ended.connect(func(_rid: String, repelled: bool) -> void: ended.append(repelled), CONNECT_ONE_SHOT)
	var r: Dictionary = _dir.debug_raid(2)
	assert_true(bool(r["base"]), "the remembered base, not the player")
	assert_lt(Vector2(Vector3(r["target"]).x, Vector3(r["target"]).z).length(), 5.0)
	await get_tree().physics_frame
	var members: Array = (r["members"] as Array).duplicate()
	_dir._follow_raid(_p, 0.5)
	assert_false(_dir.raid.is_empty(), "not before they get there")
	_dir.raid["arrived"] = true
	_dir.raid["broken"] = 2
	_dir._follow_raid(_p, 0.5)
	assert_false(_dir.raid.is_empty(), "not while there are ripe crops to take")
	var looter: Enemy = members[1]
	looter.global_position = Vector3(3.5, 0, 3)
	_dir._follow_raid(_p, 0.5)
	assert_true(_dir.raid.is_empty(), "sacked: broke in and took the crops")
	assert_eq(ended, [false], "not repelled")
	for e: Variant in members:
		assert_eq((e as Enemy).state, Enemy.State.FLEE, "they leave")
	assert_eq(_dir._leaving.size(), members.size(), "and are taken out of the world once away")
	(members[0] as Enemy).tribe.gone = true
	_dir._follow_leaving()
	assert_eq(_dir._leaving.size(), members.size() - 1)


func test_a_raid_and_a_scout_survive_a_save_and_resume() -> void:
	_piece("p:weak", &"storage_crate", Vector3(-4, 0, 3), 40.0)
	_piece("p:strong", &"storage_crate", Vector3(4, 0, 0), 500.0)
	var r: Dictionary = _dir.debug_raid(3)
	var scout: Enemy = _dir.send_scout(_p)
	assert_not_null(scout)
	await get_tree().physics_frame
	r["t"] = 77.0
	(r["members"][0] as Enemy).tribe.morale = 0.55
	(r["members"][1] as Enemy).global_position = Vector3(30, 0, 40)
	scout.tribe.watched = 12.0
	var ids: Array = []
	for e: Variant in r["members"]:
		ids.append(String((e as Enemy).entity_id))
	var scout_id: StringName = scout.entity_id
	Events.game_saving.emit("test")
	var w := WorldState.new()
	w.from_dict(JSON.parse_string(JSON.stringify(Game.session.world.to_dict())))
	assert_true(w.ashen.has("live"), "the bands out are saved with the faction")
	# The reload: the old bodies and director go, the session world is the saved one.
	for e2: Variant in r["members"]:
		_ai.despawn(e2)
	_ai.despawn(scout)
	_dir.free()
	await get_tree().physics_frame
	Game.session.world = w
	var d2: AshenDirector = _new_director()
	d2._process(1.0)
	assert_false(d2.raid.is_empty(), "the raid resumes")
	assert_eq(str(d2.raid["id"]), str(r["id"]))
	assert_almost_eq(float(d2.raid["t"]), 77.0 + 1.0, 0.6, "its clock runs on")
	assert_eq(str(d2.raid["goal_piece"]), "p:weak", "still making for the weak point")
	var ids2: Array = []
	for e3: Variant in d2.raid["members"]:
		ids2.append(String((e3 as Enemy).entity_id))
	assert_eq(ids2, ids, "the same raiders")
	assert_almost_eq((d2.raid["members"][0] as Enemy).tribe.morale, 0.55, 0.001)
	assert_lt((d2.raid["members"][1] as Enemy).global_position.distance_to(Vector3(30, 0.2, 40)), 1.0, "where they stood")
	assert_eq((d2.raid["members"][0] as Enemy).tribe.job, AshenMind.Job.RAID)
	assert_not_null(d2.flow, "the way in is laid again")
	assert_eq(d2._scouts.size(), 1, "the scout is back")
	assert_eq(d2._scouts[0].entity_id, scout_id)
	assert_almost_eq(d2._scouts[0].tribe.watched, 12.0, 0.001)
	assert_eq(d2._scouts[0].state, Enemy.State.OBSERVE)
	assert_false(w.ashen.has("live"), "brought back once")
	# Saved again with nothing out: the key goes.
	for e4: Variant in d2.raid["members"]:
		_ai.despawn(e4)
	d2.raid = {}
	_ai.despawn(d2._scouts[0])
	d2._scouts.clear()
	Events.game_saving.emit("test")
	assert_false(Game.session.world.ashen.has("live"))
