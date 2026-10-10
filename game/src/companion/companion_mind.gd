class_name CompanionMind
extends RefCounted
## What makes an Enemy body the companion (ADR-0058, Ezra Vane): archetype `companion` gives the
## body one of these, the way `tribe` gives the Ashen an AshenMind. Enemy hands it the whole frame
## (`step`), so none of the hunting state machine runs for him: he never perceives or targets the
## player, never breaks the player's walls, and makes no Hollowed noises.
##
## Before he is recruited he sits injured at his camp (out of play: no foe for anyone, no damage).
## Recruited he follows (keeping follow.min..max behind the player, walking, running to catch up,
## placed beside the player out of sight past teleport_beyond), stays, or guards a spot; following
## he takes on Hollowed hunting near the player and whatever hits him, guarding whatever comes
## within guard.radius of the spot. The fight itself is EnemyFoes' (the chase and the blows at a
## `foe`), so his kills are nobody's. At 0 hp he is downed (out of play, lying, bleeding out over
## downed.seconds) until revived or gone; CompanionDirector owns the bookkeeping (orders, save,
## the camp, his return at dawn) and this the body's moment to moment. Gather, fetch and store are
## errands run by `work` (CompanionWork, ADR-0058 phase 2) while nothing needs fighting.

const ORDERS: PackedStringArray = ["follow", "stay", "guard", "gather", "fetch", "store"]
## Orders that are errands (CompanionWork, ADR-0058 phase 2).
const ERRANDS: PackedStringArray = ["gather", "fetch", "store"]
## Enemy states the fight runs in (EnemyFoes._fight drives CHASE / ATTACK).
const FIGHT_STATES: Array = [Enemy.State.CHASE, Enemy.State.ATTACK, Enemy.State.SPIT]
const SCAN_INTERVAL: float = 0.4
## How long a spotted bark keeps quiet after the last fight (s).
const SPOTTED_QUIET: float = 45.0
## Barks he says on his own (not answering an order): an event repeated within voice.repeat s is
## dropped, line and voice (ADR-0058 phase 3, TD-303).
const AUTO_BARKS: PackedStringArray = ["spotted", "hurt", "full", "done", "cant_reach", "store_full"]
## Barks voiced even right after another one.
const URGENT_BARKS: PackedStringArray = ["downed", "recruited", "revived"]

var enemy: Enemy
var cdef: CompanionDef
var recruited: bool = false
var order: String = "follow"
## Where he stays or guards (INF: where he stands when the order is given).
var spot := Vector3.INF
var downed: bool = false
## Seconds of bleeding left while downed.
var downed_t: float = 0.0
## Bled out (the director takes the body out of the world).
var gone: bool = false
## Getting up (revive / recruit clip), seconds left.
var rising_t: float = 0.0
var lantern: OmniLight3D = null
var _scan_t: float = 0.0
var _fight_end_t: float = -1000.0
var _bark_n: int = 0
var _step_t: float = 0.0
var _anim_fixed: bool = false
var _hurt_bark_t: float = -1000.0
## When each bark event was last said (s, enemy._now()).
var _said: Dictionary = {}
## When he last spoke a voiced bark.
var _voice_t: float = -1000.0
## The voice sound (and 1-based variant, 0 random) the last voiced bark asked for (tests; set
## even when the sound isn't generated and he stays silent).
var last_voice: String = ""
var last_voice_variant: int = 0
## His voice: one positional player at his mouth, so a bark follows him (a new one cuts the last).
var _voice: Sound3D = null
## Downed, the Hollowed that were on him keep at him until this time (downed.linger, TD-300).
var _linger_until: float = -1000.0
## The bodies (instance ids) that had him as their foe when he went down: only they keep at him
## while he lies there (TD-312: a Hollow arriving in the linger window used to take him up).
var _maulers: Dictionary = {}
## His errands (gather, fetch, store).
var work: CompanionWork = null
## His own pack (CompanionDirector.inventory; set when the body is spawned).
var inventory: Inventory = null:
	set(v):
		inventory = v
		if work != null:
			work.inventory = v
## The logs on his shoulder (one mesh per log carried).
var _shoulder: Node3D = null
var _shoulder_n: int = 0


func setup(e: Enemy) -> void:
	enemy = e
	for c: ContentDef in Content.all(&"companion"):
		if (c as CompanionDef).enemy == e.def.id:
			cdef = c
			break
	work = CompanionWork.new(self)
	work.inventory = inventory


## The body's frame (Enemy._physics_process hands it over). True: nothing else runs this frame.
func step(delta: float, p: Player, dist: float) -> bool:
	_fix_anims()
	if enemy.state != Enemy.State.STAGGER or downed:
		enemy._state_t += delta  # (Enemy's own frame, which counts it, doesn't run for him)
	if downed:
		downed_t -= delta
		enemy.velocity = Vector3.ZERO
		_light(false)
		if downed_t <= 0.0:
			gone = true
		return true
	if rising_t > 0.0:
		rising_t -= delta
		enemy.velocity = Vector3.ZERO
		if rising_t <= 0.0:
			enemy._fit_shape()
			enemy._set_state(Enemy.State.IDLE)
		return true
	if not recruited:
		_sit(p, dist)
		return true
	if enemy.state == Enemy.State.STAGGER:
		return false  # Enemy plays the recoil out (and resumes the fight)
	if enemy.state == Enemy.State.BREAK:
		enemy.break_target = null  # never at the player's walls
		enemy._set_state(Enemy.State.CHASE)
	_light((order == "follow" or ERRANDS.has(order)) and enemy.is_night())
	_shoulder_logs()
	_scan_t -= delta
	if _scan_t <= 0.0:
		_scan_t = SCAN_INTERVAL
		_pick_foe(p)
	var want := Vector3.ZERO
	if enemy.foe != null:
		if enemy.state not in FIGHT_STATES:
			enemy._set_state(Enemy.State.CHASE)
		work.interrupt()
		want = EnemyFoes._fight(enemy)
	else:
		if enemy.state in FIGHT_STATES:
			enemy._set_state(Enemy.State.IDLE)
			_fight_end_t = enemy._now()
		want = work.step(delta, p) if work.active() else _order_move(p)
		enemy._set_state(Enemy.State.WANDER if want.length() > 0.05 else Enemy.State.IDLE)
	enemy._move(want, delta, dist)
	_animate(want)
	_footsteps(delta)
	return true


## The clip for the frame: an errand's pickup or chop plays itself out; carrying logs he walks
## with them on his shoulder (`carry_walk`, never running); else the body's own gait and idle.
func _animate(want: Vector3) -> void:
	if enemy.foe == null and work.acting:
		return
	var sp: float = Vector2(enemy.velocity.x, enemy.velocity.z).length()
	if enemy.foe == null and work.carrying_logs() and sp > 0.15 and enemy.visual.has_anim(&"carry_walk"):
		enemy.visual.play(&"carry_walk", clampf(sp / 0.9, 0.5, 2.0), 0.3, [&"walk"] as Array[StringName])
		return
	enemy._update_anim(want)


# --- Orders ----------------------------------------------------------------------------------------

## Sets an order (validated by the director's command). Stay and guard hold `at` (INF: here).
func set_order(kind: String, at: Vector3 = Vector3.INF) -> void:
	order = kind
	if work != null:
		work.clear()  # an errand is started by its command after this
	spot = at if at != Vector3.INF else enemy.global_position
	if kind == "follow":
		spot = Vector3.INF
	enemy.foe = null


## Where he heads for the order: a place 3-6 m behind and to the side of the player (follow), or
## back to his spot (stay, guard). Walks, runs to catch up.
func _order_move(p: Player) -> Vector3:
	if order == "follow":
		if p == null:
			return Vector3.ZERO
		var mn: float = CompanionDef.fnum(cdef.follow, "min", 3.0)
		var mx: float = CompanionDef.fnum(cdef.follow, "max", 6.0)
		var d: float = enemy._flat_dist(p.global_position)
		if d <= mx and d >= mn * 0.6:
			enemy._face(p.global_position)
			return Vector3.ZERO
		var slot: Vector3 = follow_slot(p)
		var run: bool = d > CompanionDef.fnum(cdef.follow, "run_beyond", 9.0) or p.horizontal_speed() > 4.0
		if d < mn * 0.6:
			# too close (the player walked back into him): a step out of the way
			return (enemy.global_position - p.global_position).normalized() * Vector3(1, 0, 1) * enemy._speed(false)
		return enemy._move_dir(slot) * enemy._speed(run)
	if spot == Vector3.INF:
		spot = enemy.global_position
	var away: float = enemy._flat_dist(spot)
	if away > 1.5:
		return enemy._move_dir(spot) * enemy._speed(away > 10.0)
	return Vector3.ZERO


## The follow spot: behind the player and a little to his own side of them.
func follow_slot(p: Player) -> Vector3:
	var fwd: Vector3 = -p.camera.global_transform.basis.z if p.camera != null else Vector3.FORWARD
	fwd.y = 0.0
	fwd = fwd.normalized() if fwd.length() > 0.01 else Vector3.FORWARD
	var side := Vector3(fwd.z, 0.0, -fwd.x)
	var s: float = 1.0 if side.dot(enemy.global_position - p.global_position) >= 0.0 else -1.0
	var back: float = (CompanionDef.fnum(cdef.follow, "min", 3.0) + CompanionDef.fnum(cdef.follow, "max", 6.0)) * 0.5
	return p.global_position - fwd * back + side * s * 1.5


# --- Fighting --------------------------------------------------------------------------------------

## Keeps a foe he may fight under his order, or picks the nearest: following, a hostile body
## hunting within follow.engage of the player or close to him; guarding, any awake hostile within
## guard.radius of the spot; staying, only what comes at him. Never the player (only Enemy bodies
## of a hostile faction are candidates), never one asleep.
func _pick_foe(p: Player) -> void:
	var f: Enemy = enemy.foe
	if f != null and (not is_instance_valid(f) or not f.is_alive() or not _may_fight(f, p)):
		enemy.foe = null
		f = null
	if f != null:
		enemy._foe_seen = enemy._now()
		return
	if enemy.director == null or not enemy.director.has_method(&"enemies_in_radius"):
		return
	var centre: Vector3 = enemy.global_position
	var r: float = 8.0
	if order == "follow" and p != null:
		centre = p.global_position
		r = CompanionDef.fnum(cdef.follow, "engage", 15.0)
	elif order == "guard":
		centre = spot if spot != Vector3.INF else enemy.global_position
		r = CompanionDef.fnum(cdef.guard, "radius", 20.0)
	var best: Enemy = null
	var best_d: float = INF
	for o: Enemy in enemy.director.call(&"enemies_in_radius", centre, r + 8.0):
		if o == enemy or not candidate(o) or not _may_fight(o, p):
			continue
		var d: float = enemy.global_position.distance_to(o.global_position)
		if d < best_d and (d < 3.0 or EnemyFoes.sees(enemy, o)):
			best = o
			best_d = d
	if best != null:
		take(best)


## A body of a hostile faction, alive and awake: what he may ever fight.
func candidate(o: Enemy) -> bool:
	return o != null and is_instance_valid(o) and o.is_alive() and o.ally == null and o.state != Enemy.State.SLEEP \
		and FactionDef.hostile(enemy.def.faction, o.def.faction)


## Whether his order lets him fight `o` (where it is, what it is doing).
func _may_fight(o: Enemy, p: Player) -> bool:
	var at_him: bool = o.foe == enemy or enemy.global_position.distance_to(o.global_position) < 4.0
	match order:
		"follow":
			if p == null:
				return at_him
			var dp: float = o.global_position.distance_to(p.global_position)
			if dp > CompanionDef.fnum(cdef.follow, "leash", 22.0):
				return false
			var hunting: bool = o.state in [Enemy.State.CHASE, Enemy.State.ATTACK, Enemy.State.BREAK, Enemy.State.SPIT,
				Enemy.State.CHARGE, Enemy.State.HORDE, Enemy.State.INVESTIGATE]
			return at_him or (hunting and dp <= CompanionDef.fnum(cdef.follow, "engage", 15.0) + 4.0) \
				or enemy.global_position.distance_to(o.global_position) < 8.0
		"guard":
			var c: Vector3 = spot if spot != Vector3.INF else enemy.global_position
			return at_him or o.global_position.distance_to(c) <= CompanionDef.fnum(cdef.guard, "leash", 26.0)
	return at_him


## Turns on `o` now (a bark the first time in a while).
func take(o: Enemy) -> void:
	if enemy._now() - _fight_end_t > SPOTTED_QUIET and enemy.foe == null:
		bark("spotted")
	enemy.foe = o
	enemy._foe_seen = enemy._now()
	enemy.target_pos = o.global_position
	if enemy.state not in FIGHT_STATES:
		enemy._set_state(Enemy.State.CHASE)
	_fight_end_t = enemy._now()


# --- Damage, downed, revive ------------------------------------------------------------------------

## Blows he ignores: none count before he is recruited or while he is down; the player's own (no
## friendly fire), traps and the Waystation guns never hurt him.
func shrugs(info: DamageInfo) -> bool:
	if downed and in_play() and not (Game.session != null and Game.session.players.has(info.source_id)):
		# Mauled where he lies: no health to lose, but he bleeds out the faster (TD-300).
		downed_t = maxf(0.5, downed_t - CompanionDef.fnum(cdef.downed, "mauled", 6.0))
		Audio.play_3d(&"sfx/hit_flesh", enemy.global_position + Vector3.UP * 0.3, {"volume_db": -4.0})
		# Seen as well as heard (TD-312): blood where he lies, toward whoever is at him.
		if enemy.get_parent() != null:
			var at: Vector3 = info.hit_pos if info.hit_pos != Vector3.ZERO else enemy.global_position + Vector3.UP * 0.3
			FxLibrary.burst(enemy.get_parent(), "blood", at, -info.direction if info.direction != Vector3.ZERO else Vector3.UP, 0.6)
		return true
	if not recruited or downed or rising_t > 0.0:
		return true
	if Game.session != null and Game.session.players.has(info.source_id):
		return true
	if info.cause == &"trap" or String(info.source_id).begins_with("guard:"):
		return true
	if enemy.health - info.amount > 0.0 and enemy._now() - _hurt_bark_t > 30.0 and enemy.health < enemy.max_health * 0.5:
		_hurt_bark_t = enemy._now()
		bark("hurt")
	return false


## At 0 hp: down on the ground, bleeding out. The Hollowed that were on him keep at him for
## downed.linger s (in_play), then lose interest (is_alive() is false); a downed body restored from
## a save is out of play at once.
func go_down(_info: DamageInfo = null, seconds: float = -1.0) -> void:
	downed = true
	_linger_until = enemy._now() + CompanionDef.fnum(cdef.downed, "linger", 8.0) if seconds < 0.0 else -1000.0
	_maulers = _bodies_on_him()
	downed_t = seconds if seconds >= 0.0 else CompanionDef.fnum(cdef.downed, "seconds", 180.0)
	enemy.health = 0.0
	enemy.foe = null
	enemy.velocity = Vector3.ZERO
	enemy._set_state(Enemy.State.STAGGER)
	enemy.visual.play(&"downed", 1.0, 0.3, [&"idle_sleep_lie", &"idle"] as Array[StringName])
	enemy.visual.animate_placeholder(0.0, 0.0, true)
	enemy._fit_pose_shape("lie")
	_light(false)
	if seconds < 0.0:
		bark("downed")


## Back on his feet with `fraction` of his health (revived, recruited, returned).
func get_up(fraction: float) -> void:
	downed = false
	gone = false
	enemy.health = maxf(1.0, enemy.max_health * fraction)
	enemy.velocity = Vector3.ZERO
	enemy.foe = null
	enemy._set_state(Enemy.State.STAGGER)
	rising_t = enemy.visual.play_once(&"revive", 1.0, [&"wake_lie", &"wake_sit", &"idle"] as Array[StringName])
	enemy.visual.animate_placeholder(0.0, 0.0, false)


## Whether `who` may take him up as a new foe: anyone while he stands; downed, only the bodies
## that were already on him (they linger; nobody new joins in).
func open_to(who: Enemy) -> bool:
	return not downed or _maulers.has(who.get_instance_id())


## Instance ids of the live bodies whose foe he is now.
func _bodies_on_him() -> Dictionary:
	var out: Dictionary = {}
	var all: Variant = enemy.director.get(&"enemies") if enemy.director != null else null
	if all is Dictionary:
		for o: Variant in (all as Dictionary).values():
			if o is Enemy and is_instance_valid(o) and (o as Enemy).foe == enemy:
				out[(o as Enemy).get_instance_id()] = true
	return out


## Out of play (not recruited yet, or down past downed.linger): nobody's foe.
func in_play() -> bool:
	return recruited and (not downed or enemy._now() < _linger_until)


# --- Before he is recruited: hurt, at his camp --------------------------------------------------

func _sit(_p: Player, _dist: float) -> void:
	enemy.velocity = Vector3.ZERO
	if enemy.state != Enemy.State.IDLE:
		enemy._set_state(Enemy.State.IDLE)
	enemy.visual.play(&"sit_injured", 1.0, 0.4, [&"idle_sleep_sit", &"idle"] as Array[StringName])
	enemy.visual.animate_placeholder(0.0, 0.0, false)


# --- Interaction (Enemy's interactable hooks) ------------------------------------------------------

func _director() -> Node:
	return Game.world.get(&"companion") if Game.world != null else null


func interact_text(p: Player) -> String:
	if not recruited:
		return "Talk to the lineman"
	if downed:
		return "Patch Ezra up (hold)" if revive_item(p.state) != &"" else "Ezra is down: you need a bandage or a first aid kit"
	if rising_t > 0.0:
		return ""
	return "Talk to Ezra"


func interact_hold_time(p: Player) -> float:
	return cdef.revive_hold if downed and revive_item(p.state) != &"" else 0.0


func interact(p: Player) -> void:
	var dir: Node = _director()
	if downed:
		if revive_item(p.state) != &"":
			Game.execute(&"companion.revive", {"player": p.state.id})
		return
	if dir != null and dir.has_method(&"open_card"):
		dir.call(&"open_card")


## The first revive item the player carries (&"" for none).
func revive_item(ps: PlayerState) -> StringName:
	for it: String in cdef.revive_items:
		if ps != null and ps.inventory.count_of(StringName(it)) > 0:
			return StringName(it)
	return &""


# --- Presentation ----------------------------------------------------------------------------------

## A status-bar line for an event (cycling through the def's lines), spoken in his voice from his
## body (ADR-0058 phase 3). What he says on his own is not repeated within voice.repeat s.
func bark(event: String) -> void:
	if cdef == null:
		return
	var now: float = enemy._now()
	if event in AUTO_BARKS and now - float(_said.get(event, -1000.0)) < CompanionDef.fnum(cdef.voice, "repeat", 6.0):
		return
	_said[event] = now
	var n: int = _bark_n
	_bark_n += 1
	var line: String = cdef.bark(event, n)
	if line != "":
		Events.player_status_message.emit(line, &"warning" if event in ["downed", "out"] else &"info")
	speak(event, n)


## Plays the voice for a bark (voice.lines: "id", "id:N" or "id:line" = the variant of the line
## `n` shown), at most every voice.gap s (urgent barks cut in). Silent where the sound isn't
## generated: the status-bar line carries it.
func speak(event: String, n: int = 0) -> void:
	var spec: String = str((cdef.voice.get("lines", {}) as Dictionary).get(event, ""))
	var now: float = enemy._now()
	if spec == "" or (now - _voice_t < CompanionDef.fnum(cdef.voice, "gap", 2.0) and not event in URGENT_BARKS):
		return
	_voice_t = now
	var id: String = spec
	var variant: int = 0
	var colon: int = spec.rfind(":")
	if colon > 0:
		id = spec.substr(0, colon)
		var v: String = spec.substr(colon + 1)
		var lines: Array = cdef.barks.get(event, [])
		variant = posmod(n, lines.size()) + 1 if v == "line" and not lines.is_empty() else maxi(0, v.to_int())
	last_voice = id
	last_voice_variant = variant
	var vs: Array = Audio.variants(StringName(id))
	if vs.is_empty() or not enemy.is_inside_tree():
		return
	if _voice == null:
		_voice = Sound3D.new()
		_voice.name = "Voice"
		_voice.bus = Audio.sfx_bus
		_voice.unit_size = 7.0
		_voice.max_distance = 60.0
		_voice.position = Vector3(0.0, 1.6, 0.1)
		enemy.add_child(_voice)
	_voice.stream = vs[clampi(variant - 1, 0, vs.size() - 1)] if variant > 0 else vs[randi() % vs.size()]
	_voice.play()
	# Far off, he's heard and not seen: say so (G4); near, the status line carries his words.
	if _far_from_player(25.0):
		SoundCaptions.say("ezra", "ezra calling out", enemy.global_position, 10.0)


## The lantern he carries at night while following: his own light (not a stimulus-field light, so
## it never shows the Hollowed the player).
func _light(on: bool) -> void:
	if lantern == null:
		if not on or enemy.visual == null:
			return
		lantern = OmniLight3D.new()
		lantern.name = "Lantern"
		var c: Array = cdef.lantern.get("color", [1.0, 0.78, 0.48])
		lantern.light_color = Color(float(c[0]), float(c[1]), float(c[2]))
		lantern.light_energy = float(cdef.lantern.get("energy", 1.1))
		lantern.omni_range = float(cdef.lantern.get("range", 9.0))
		lantern.shadow_enabled = false
		lantern.position = Vector3(-0.3, 1.0, 0.15)
		enemy.add_child(lantern)
	lantern.visible = on


## A perk effect of his now (CompanionDirector.perk), `none` without a director.
func perk(key: String, none: float) -> float:
	var d: Node = _director()
	return float(d.call(&"perk", key, none)) if d != null and d.has_method(&"perk") else none


## His body's id (`companion:<def>`): the owner the gathering commands fill his pack for.
func body_id() -> StringName:
	return enemy.entity_id


## The logs on his right shoulder, one per log in his pack (like the player's two). A plain node
## at shoulder height, not on a bone: it doesn't follow the clips (TD-305).
func _shoulder_logs() -> void:
	var n: int = inventory.count_of(&"log") if inventory != null else 0
	if n == _shoulder_n:
		return
	_shoulder_n = n
	if _shoulder == null:
		_shoulder = Node3D.new()
		_shoulder.name = "ShoulderLogs"
		_shoulder.position = Vector3(-0.2, 1.55, -0.05)
		enemy.add_child(_shoulder)
	for c: Node in _shoulder.get_children():
		c.queue_free()
	for i: int in n:
		var mi := MeshInstance3D.new()
		mi.mesh = ModelLibrary.mesh("structures/log_piece", "log")
		# along his facing (the mesh lies along +X), the far end dipping a little, stacked outward
		mi.transform = Transform3D(Basis(Vector3.UP, PI * 0.5) * Basis(Vector3.BACK, -0.12), Vector3(-0.17 * i, 0.12 * i, 0.0))
		_shoulder.add_child(mi)


func lantern_on() -> bool:
	return lantern != null and lantern.visible


## His clips that hold or loop (EnemyVisual loops only idles and gaits).
func _fix_anims() -> void:
	if _anim_fixed or enemy.visual == null:
		return
	_anim_fixed = true
	var ap: AnimationPlayer = enemy.visual.anim
	if ap == null:
		return
	for n: StringName in [&"downed", &"sit_injured", &"talk", &"look", &"carry_walk"]:
		if ap.has_animation(n):
			ap.get_animation(n).loop_mode = Animation.LOOP_LINEAR


func _footsteps(delta: float) -> void:
	var sp: float = Vector2(enemy.velocity.x, enemy.velocity.z).length()
	if sp < 0.3 or enemy._far:
		return
	_step_t -= delta * sp
	if _step_t <= 0.0:
		_step_t = 0.85
		Audio.play_3d(&"sfx/footstep_grass", enemy.global_position, {"volume_db": -12.0, "max_distance": 25.0})


## His voice for the Hollowed's voice ids (Enemy._vid): a living man's grunts and pain, no cries.
## His own (TD-303) when generated, else the Ashen's.
static func voice(hollowed: StringName) -> StringName:
	match hollowed:
		&"voice/zombie_attack":
			return &"voice/ezra_grunt" if not Audio.variants(&"voice/ezra_grunt").is_empty() else &"voice/ashen_grunt"
		&"voice/zombie_pain":
			return &"voice/ezra_pain" if not Audio.variants(&"voice/ezra_pain").is_empty() else &"voice/ashen_pain"
		&"voice/zombie_death":
			return &"voice/ashen_death"
	return &""


func _far_from_player(m: float) -> bool:
	var p: Node3D = Game.world.get(&"player") as Node3D if Game.world != null else null
	return p != null and p.global_position.distance_to(enemy.global_position) > m
