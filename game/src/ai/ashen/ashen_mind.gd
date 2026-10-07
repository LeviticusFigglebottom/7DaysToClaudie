class_name AshenMind
extends RefCounted
## What makes an Enemy one of the Ashen (ADR-0048): archetype `tribe` gives every such body one of
## these. It holds the fighter's morale, its band, its job (a camp's resident, a scout, a raider)
## and the two states only the Ashen have: OBSERVE (a scout holds a vantage and watches before
## anyone comes) and FLEE (morale broke, the watching is done, or the Hum is coming). It also keeps
## them off the outsider's fire and throws their spears. A war party's firebrand carries a lit
## brand (a light) and its blows on structures are fire (`strike_type`, phase 2: TD-189); its own
## brand never frightens its band (only the player's flame and structures count as the outsider's
## fire). Enemy calls it from a handful of hooks;
## the arithmetic is AshenBrain's, the world-wide bookkeeping AshenDirector's.

enum Job { CAMP, SCOUT, RAID }

var enemy: Enemy
var fd: FactionDef
var job: Job = Job.CAMP
var role: String = "raider"
## 0-1; under morale.break it flees (never below home_floor inside its own camp's territory).
var morale: float = 1.0
## Band mates (Enemies, itself included): a raid, a scout alone, a camp's residents.
var band: Array = []
## The camp it belongs to (building id) and that camp's centre and territory; where it flees to.
var camp_id: String = ""
var camp_pos := Vector3.INF
var territory: float = 0.0
## A raid's goal (the base, or where the player was) and a scout's quarry.
var goal := Vector3.INF
## Scout: seconds watched with the quarry in sight; whether it finished (reported) or was spotted.
var watched: float = 0.0
var reported: bool = false
var spotted: bool = false
## Fleeing: where to, and for how long it has been out of the player's sight.
var flee_to := Vector3.INF
var unseen_t: float = 0.0
## Set when the director should take this body out of the world (it got away).
var gone: bool = false
var _fear: float = 0.0
var _fires: Array = []
var _fires_t: float = 0.0
var _throw: Dictionary = {}
## The damage type its blows on structures take ("" = the Hollowed's, as any Enemy's).
var strike_type: String = ""
## A firebrand's brand (an OmniLight3D on the body, registered with Stimuli); null for none.
var brand: OmniLight3D = null


func setup(e: Enemy, opts: Dictionary) -> void:
	enemy = e
	fd = AshenBrain.def()
	var t: Dictionary = e.def.beh("tribe", {})
	role = str(t.get("role", "raider"))
	_throw = t.get("throw", {})
	strike_type = str(t.get("strike_type", ""))
	if t.get("light", null) is Dictionary:
		_light_brand(t["light"])
	match str(opts.get("job", "camp")):
		"scout":
			job = Job.SCOUT
		"raid":
			job = Job.RAID
		_:
			job = Job.CAMP
	camp_id = str(opts.get("camp", ""))
	if opts.get("camp_pos", null) is Vector3:
		camp_pos = opts["camp_pos"]
		territory = float(opts.get("territory", 0.0))
	if opts.get("goal", null) is Vector3:
		goal = opts["goal"]


## Lights the brand it carries: a warm light at the hand, seen by the AI's light sampling.
func _light_brand(l: Dictionary) -> void:
	brand = OmniLight3D.new()
	brand.name = "Brand"
	var c: Array = l.get("color", [1.0, 0.62, 0.3])
	brand.light_color = Color(float(c[0]), float(c[1]), float(c[2]))
	brand.light_energy = float(l.get("energy", 1.2))
	brand.omni_range = float(l.get("range", 10.0))
	brand.position = Vector3(0.35, 1.5, 0.25)
	enemy.add_child(brand)
	if Stimuli.current != null:
		Stimuli.current.register_light(brand, brand.omni_range, brand.light_energy)


## The brand goes out (the firebrand fell): no light left to see by.
func douse() -> void:
	if brand != null and is_instance_valid(brand):
		brand.visible = false
		if Stimuli.current != null:
			Stimuli.current.unregister_light(brand)


## A blow on a structure (Enemy._strike_structure): a firebrand's is fire, so the piece's
## damage_mult for fire (wood far more than stone) applies in place of the Hollowed's.
func arm_blow(info: DamageInfo) -> void:
	if strike_type != "":
		info.type = StringName(strike_type)


## Whether it stands inside its own camp's territory (it won't break there).
func at_home() -> bool:
	return camp_pos != Vector3.INF and Vector2(enemy.global_position.x - camp_pos.x, enemy.global_position.z - camp_pos.z).length() <= territory


## Every physics frame, before the state machine: fire fear wears morale down (or it recovers),
## and a broken fighter turns to run.
func tick(delta: float, p: Player) -> void:
	if fd == null or enemy.state == Enemy.State.DEAD:
		return
	_fires_t -= delta
	if _fires_t <= 0.0:
		_fires_t = 1.0
		_fires = AshenMind.player_fires(enemy.global_position, float(fd.fire.get("radius", 9.0)) + 4.0)
	_fear = AshenBrain.fire_fear(fd, enemy.global_position, flame_of(p), facing_of(p), _fires)
	morale = AshenBrain.near_fire(fd, morale, _fear, delta, at_home())
	if enemy.state != Enemy.State.FLEE and AshenBrain.breaks(fd, morale):
		flee(p)


## A blow took `fraction` of its full health.
func on_hurt(fraction: float, p: Player) -> void:
	if fd == null:
		return
	morale = AshenBrain.hurt(fd, morale, fraction, at_home())
	if job == Job.SCOUT and enemy.state == Enemy.State.OBSERVE:
		spotted = true
	if AshenBrain.breaks(fd, morale):
		flee(p)


## A band mate fell.
func on_mate_down(p: Player) -> void:
	if fd == null or enemy.state == Enemy.State.DEAD:
		return
	morale = AshenBrain.mate_down(fd, morale, at_home())
	if AshenBrain.breaks(fd, morale):
		flee(p)


## Turns to run: home to its camp, else straight away from the player.
func flee(p: Player) -> void:
	if enemy.state == Enemy.State.DEAD or enemy.state == Enemy.State.FLEE:
		return
	var from: Vector3 = p.global_position if p != null else enemy.global_position
	if camp_pos != Vector3.INF and job == Job.CAMP:
		flee_to = camp_pos
	else:
		var away := Vector3(enemy.global_position.x - from.x, 0.0, enemy.global_position.z - from.z)
		if away.length() < 0.1:
			away = Vector3.FORWARD
		flee_to = enemy.global_position + away.normalized() * 140.0
	unseen_t = 0.0
	enemy.break_target = null
	enemy._set_state(Enemy.State.FLEE)


## Movement in the Ashen's own states.
func move(p: Player, dist: float, delta: float) -> Vector3:
	match enemy.state:
		Enemy.State.OBSERVE:
			return _observe(p, dist, delta)
		Enemy.State.FLEE:
			if p == null or dist > 60.0 or not enemy._line_of_sight(p):
				unseen_t += delta
			else:
				unseen_t = 0.0
			if flee_to == camp_pos and camp_pos != Vector3.INF and enemy._flat_dist(camp_pos) < 6.0:
				# Home: it gathers itself and stands with the others.
				morale = maxf(morale, float(fd.morale.get("home_floor", 0.6)))
				enemy.home = camp_pos
				enemy._set_state(Enemy.State.IDLE)
				return Vector3.ZERO
			if unseen_t > 8.0 and dist > 50.0:
				gone = true
			return enemy._move_dir(flee_to) * enemy._speed(true)
	return Vector3.ZERO


## A scout: makes for a vantage `vantage` m from its quarry, then holds still and watches while it
## can see them. Seen (the player looks at it from inside spotted_range), too close (flee_range) or
## hurt, it breaks off; once it has watched `observe` seconds it slips away to report.
func _observe(p: Player, dist: float, delta: float) -> Vector3:
	if p == null:
		return Vector3.ZERO
	var sc: Dictionary = fd.scouts
	if dist < float(sc.get("flee_range", 22.0)) or (dist < float(sc.get("spotted_range", 30.0)) and _looked_at(p)):
		spotted = true
	if spotted:
		# Found out: it runs (and reports nothing).
		flee(p)
		return Vector3.ZERO
	var v: Array = sc.get("vantage", [35, 55])
	var sees: bool = dist < 90.0 and enemy._line_of_sight(p)
	if sees and dist >= float(v[0]) and dist <= float(v[1]):
		watched += delta
		enemy._face(p.global_position)
		if watched >= float(sc.get("observe", 45.0)):
			reported = true
			flee(p)
		return Vector3.ZERO
	# Close in to (or back off to) the vantage ring, on its own bearing.
	var away := Vector3(enemy.global_position.x - p.global_position.x, 0.0, enemy.global_position.z - p.global_position.z)
	var spot: Vector3 = p.global_position + away.normalized() * (float(v[0]) + float(v[1])) * 0.5
	return enemy._move_dir(spot) * enemy._speed(false) * (1.0 if enemy._flat_dist(spot) > 6.0 else 0.5)


## The player looking straight at it (within ~12 degrees) with a clear line.
func _looked_at(p: Player) -> bool:
	if p.camera == null:
		return false
	var fwd: Vector3 = -p.camera.global_transform.basis.z
	var to_me: Vector3 = (enemy.global_position + Vector3.UP * 1.4) - p.camera.global_position
	return fwd.angle_to(to_me) < deg_to_rad(12.0) and enemy._line_of_sight(p)


## How it runs a chase: round the outsider's fire, and away from a held flame it won't close on.
func chase_move(p: Player, tgt: Vector3, dist: float) -> Vector3:
	var spd: float = enemy._speed(true)
	var fire: Vector3 = AshenBrain.fire_to_avoid(fd, enemy.global_position, flame_of(p), _fires)
	if fire != Vector3.INF:
		var away := Vector3(enemy.global_position.x - fire.x, 0.0, enemy.global_position.z - fire.z)
		var away_n: Vector3 = away.normalized() if away.length() > 0.05 else Vector3.FORWARD
		var side: Vector3 = away_n.cross(Vector3.UP) * (1.0 if (enemy._rng.seed & 1) == 0 else -1.0)
		return enemy._steer_open((side + away_n).normalized()) * spd * 0.6
	return enemy._move_dir(tgt) * spd


## Whether it goes in to strike: not into a flame held up at it.
func may_close(p: Player) -> bool:
	return _fear < 0.35 or p == null


## A spear throw is ready and the quarry is in its band of range (a raider throws now and then;
## kept off by fire, it throws whenever it can).
func can_throw(dist: float, cooldown_left: float) -> bool:
	if _throw.is_empty() or cooldown_left > 0.0 or enemy.crawling:
		return false
	if dist < float(_throw.get("min_range", 5.0)) or dist > float(_throw.get("range", 15.0)):
		return false
	return _fear >= 0.35 or enemy._rng.randf() < float(_throw.get("chance", 0.5))


func throw_cooldown() -> float:
	return float(_throw.get("cooldown", 6.0))


## Lets the spear go at the player, leading them a little.
func throw_at(p: Player) -> void:
	if p != null:
		throw_at_body(p)


## Lets the spear go at a body (the player, or a foe of a hostile faction: TD-186), leading it a
## little. The spear flies past the thrower and its own faction.
func throw_at_body(b: CharacterBody3D) -> void:
	if b == null or enemy.get_parent() == null:
		return
	var hand: Vector3 = enemy.global_position + Vector3.UP * 1.7 + enemy.global_transform.basis.z * 0.3
	var spd: float = float(_throw.get("speed", 20.0))
	var lead: Vector3 = b.velocity * clampf(hand.distance_to(b.global_position) / spd, 0.0, 1.0) * 0.5
	ThrownSpear.launch(enemy.get_parent(), hand, b.global_position + Vector3(lead.x, 1.1, lead.z), spd,
		float(_throw.get("damage", 15.0)) * enemy.damage_mult, float(_throw.get("bleed", 0.4)), enemy.entity_id, enemy)


## Their voices: a human call for every Hollowed sound (ADR-0048 has no groans).
static func voice(hollowed: StringName) -> StringName:
	match hollowed:
		&"voice/zombie_alert", &"voice/lurcher_screech", &"voice/zombie_wake":
			return &"voice/ashen_warcry"
		&"voice/zombie_attack":
			return &"voice/ashen_grunt"
		&"voice/zombie_pain":
			return &"voice/ashen_pain"
		&"voice/zombie_death":
			return &"voice/ashen_death"
	return &""


# --- The outsider's fire --------------------------------------------------------------------------

## Where the player's held flame burns, or Vector3.INF.
static func flame_of(p: Player) -> Vector3:
	if p == null or not p.has_node(^"Equipment") or not bool(p.get_node(^"Equipment").call(&"has_flame_on")):
		return Vector3.INF
	return p.global_position


static func facing_of(p: Player) -> Vector3:
	if p == null or p.camera == null:
		return Vector3.ZERO
	var f: Vector3 = -p.camera.global_transform.basis.z
	return Vector3(f.x, 0.0, f.z)


## The player's lit fires and stations within `r` m (StructurePiece.lit).
static func player_fires(pos: Vector3, r: float) -> Array:
	var out: Array = []
	var building: Node = Game.world.get(&"building") if Game.world != null else null
	if building == null or not building.has_method(&"pieces_in_radius"):
		return out
	for piece: StructurePiece in building.call(&"pieces_in_radius", pos, r):
		if piece.lit:
			out.append(piece.global_position)
	return out
