class_name WolfPack
extends RefCounted
## A wolf pack's shared mind (ADR-0055). The wolves are Enemies on the hound's body and brain; the
## pack decides what they are doing and whether the hound brain may have the player:
##
##  * ROAM: hunger rises through the day (game hours); fed, the pack drifts round its range and keeps
##    `day.avoid` m off a player, watching (WolfHunt does the moving).
##  * HUNT: hungry, it picks the nearest grazer the WildlifeManager knows within `hunt.range`,
##    stalks it (unseen by its prey) and, once a wolf is within `hunt.rush_range`, runs it down; a
##    wolf in reach bites it (Animal.take_damage, so it bolts, bleeds and dies as a shot deer does).
##  * FEED: the carcass stays; the pack eats for `feed.seconds` (hunger to 0), leaving the remains.
##  * REST: it beds down by the kill for `feed.rest_hours`, guarding it.
##
## `engaged` hands the wolves to the hound brain (pack rally, howl, flanking, hit and run, scent
## tracking, a held flame): when hungry and the player is close, at night when not fed, when one of
## them is hurt, when the player won't leave a feeding or bedded pack's kill (after a growled
## warning), or when the player bleeds and the pack smells the trail. wants_player() is the rule.
## Nothing is saved: a pack re-rolls with its plan (WildlifeSpawner).

enum Mode { ROAM, HUNT, FEED, REST }

var id: StringName = &""
## Every wolf of the pack (Enemy), dead ones too; alive() for the living.
var members: Array = []
## 0 fed .. 1 starving.
var hunger: float = 0.5
var mode: Mode = Mode.ROAM
## What it is hunting, and the kill it feeds on or guards (Animals; may be freed: check validity).
var prey: Node = null
var kill: Node = null
## Where the pack ranges round (its spawn, then its last kill).
var den := Vector3.ZERO
var rushing: bool = false
var engaged: bool = false
## Lit fires and stations the wolves keep out of at night: [{pos: Vector3, r: float}].
var fires: Array = []

var _mode_t: float = 0.0
var _feed_t: float = 0.0
var _rest_until: float = -1.0
var _retry_t: float = 0.0
var _last_hour: float = -1.0
var _warn_t: float = -1.0
var _wounded_t: float = 0.0
var _calm_t: float = 0.0
var _next_howl: float = -1.0
## Mates joining a howl: [[seconds left, Enemy]].
var _chorus: Array = []
var _health: Dictionary = {}
var _rng := RandomNumberGenerator.new()


static func cfg() -> Dictionary:
	return Content.config(&"wolves")


static func section(key: String) -> Dictionary:
	return cfg().get(key, {}) as Dictionary


func setup(p_id: StringName, p_members: Array, p_hunger: float, p_seed: int) -> void:
	id = p_id
	members = p_members
	hunger = clampf(p_hunger, 0.0, 1.0)
	_rng.seed = p_seed
	den = centre()
	for m: Variant in members:
		if m is Enemy:
			_health[(m as Enemy).entity_id] = (m as Enemy).health


func alive() -> Array:
	var out: Array = []
	for m: Variant in members:
		if m is Enemy and is_instance_valid(m) and (m as Enemy).is_alive():
			out.append(m)
	return out


func centre() -> Vector3:
	var c := Vector3.ZERO
	var live: Array = alive()
	for m: Enemy in live:
		c += m.global_position
	return c / float(live.size()) if not live.is_empty() else den


func is_hungry() -> bool:
	return hunger >= float(section("hunger").get("hungry", 0.55))


func valid_prey() -> bool:
	return prey != null and is_instance_valid(prey) and not prey.is_queued_for_deletion()


func valid_kill() -> bool:
	return kill != null and is_instance_valid(kill) and not kill.is_queued_for_deletion()


## Where a feeding or bedded pack guards: its kill, else where it beds.
func guard_point() -> Vector3:
	return (kill as Node3D).global_position if valid_kill() else den


## The rule for taking the player on (pure; data/config/wolves.json `engage`). dist: from the
## nearest wolf; wounded: one of them was hurt lately and the player is within wounded_range;
## near_kill: the player stayed by the kill past the warning; blood: the pack has their trail.
static func wants_player(c: Dictionary, hunger_now: float, night: bool, dist: float, wounded: bool, near_kill: bool,
		blood: bool) -> bool:
	var e: Dictionary = c.get("engage", {})
	if wounded and dist <= float(e.get("wounded_range", 120.0)):
		return true
	if near_kill or blood:
		return true
	if night and hunger_now >= float(e.get("night_hunger", 0.3)) and dist <= float(e.get("night_range", 60.0)):
		return true
	var hungry: float = float((c.get("hunger", {}) as Dictionary).get("hungry", 0.55))
	return hunger_now >= hungry and dist <= float(e.get("night_range" if night else "day_range", 26.0))


## One frame of the pack (WolfPacks calls it): hunger, the hunt, feeding and rest, whether it has
## the player, its howls.
func tick(dt: float, world: WolfPacks) -> void:
	_mode_t += dt
	var h: float = world.hours()
	if _last_hour >= 0.0 and h > _last_hour:
		hunger = clampf(hunger + (h - _last_hour) * float(section("hunger").get("per_hour", 0.05)), 0.0, 1.0)
	_last_hour = h
	_watch_wounds()
	_wounded_t = maxf(0.0, _wounded_t - dt)
	_step_mode(dt, world, h)
	_step_engage(dt, world)
	_step_howls(dt, world, h)


func _set_mode(m: Mode) -> void:
	mode = m
	_mode_t = 0.0
	_feed_t = 0.0
	rushing = false


func _watch_wounds() -> void:
	for m: Enemy in alive():
		var was: float = float(_health.get(m.entity_id, m.health))
		if m.health < was - 0.01:
			_wounded_t = float(section("engage").get("wounded_seconds", 90.0))
		_health[m.entity_id] = m.health
	for m: Variant in members:
		if m is Enemy and is_instance_valid(m) and not (m as Enemy).is_alive() and _health.has((m as Enemy).entity_id):
			# a mate killed: the rest are wounded in the pack's sense
			_health.erase((m as Enemy).entity_id)
			_wounded_t = float(section("engage").get("wounded_seconds", 90.0))


func _step_mode(dt: float, world: WolfPacks, h: float) -> void:
	var hunt: Dictionary = section("hunt")
	match mode:
		Mode.ROAM:
			_retry_t = maxf(0.0, _retry_t - dt)
			if is_hungry() and _retry_t <= 0.0 and not engaged:
				var a: Node = world.nearest_prey(centre(), float(hunt.get("range", 170.0)), float(hunt.get("min_prey_health", 40.0)))
				if a != null:
					prey = a
					_set_mode(Mode.HUNT)
		Mode.HUNT:
			if not valid_prey():
				prey = null
				_give_up()
			elif not bool(prey.call(&"is_alive")):
				# down: whoever killed it, the pack has a carcass
				kill = prey
				prey = null
				den = (kill as Node3D).global_position
				_set_mode(Mode.FEED)
			elif rushing and _mode_t > float(hunt.get("rush_seconds", 16.0)):
				_give_up()
			elif not rushing:
				var p: Vector3 = (prey as Node3D).global_position
				if centre().distance_to(p) > float(hunt.get("range", 170.0)) * 1.5:
					_give_up()
				else:
					for m: Enemy in alive():
						if m._flat_dist(p) <= float(hunt.get("rush_range", 28.0)):
							rushing = true
							_mode_t = 0.0
							break
		Mode.FEED:
			if not valid_kill():
				kill = null
				_set_mode(Mode.ROAM)
				return
			var at: Vector3 = (kill as Node3D).global_position
			for m: Enemy in alive():
				if m._flat_dist(at) < 2.2:
					_feed_t += dt
					break
			if _feed_t >= float(section("feed").get("seconds", 75.0)):
				hunger = 0.0
				if not bool(kill.get(&"butchered")) and kill.has_method(&"mark_butchered"):
					kill.call(&"mark_butchered")  # eaten: what is left is remains
				_rest_until = h + float(section("feed").get("rest_hours", 3.0))
				_set_mode(Mode.REST)
		Mode.REST:
			if h >= _rest_until:
				kill = null
				_set_mode(Mode.ROAM)


func _give_up() -> void:
	prey = null
	_retry_t = float(section("hunt").get("retry_seconds", 75.0))
	_set_mode(Mode.ROAM)


func _step_engage(dt: float, world: WolfPacks) -> void:
	var p: Node3D = world.player()
	var live: Array = alive()
	if p == null or live.is_empty() or not world.player_alive():
		_release()
		return
	var ppos: Vector3 = p.global_position
	var dist: float = INF
	for m: Enemy in live:
		dist = minf(dist, m.global_position.distance_to(ppos))
	# a player who comes to a feeding or bedded pack's kill is growled at, then taken on
	var near_kill: bool = false
	var guard: Dictionary = section("guard")
	if mode in [Mode.FEED, Mode.REST] and Vector2(ppos.x - guard_point().x, ppos.z - guard_point().z).length() <= float(guard.get("radius", 22.0)):
		if _warn_t < 0.0:
			_warn_t = 0.0
			_growl(live, ppos)
		_warn_t += dt
		near_kill = _warn_t >= float(guard.get("warn_seconds", 3.5))
	else:
		_warn_t = -1.0
	var bl: Dictionary = section("blood")
	var blood: bool = false
	if hunger >= float(bl.get("min_hunger", 0.35)) and world.player_bleeding() >= float(bl.get("bleeding", 0.05)):
		for m: Enemy in live:
			if world.scent_at(m.global_position) >= float(bl.get("scent", 0.6)):
				blood = true
				break
	var want: bool = wants_player(cfg(), hunger, world.is_night(), dist, _wounded_t > 0.0, near_kill, blood)
	if want:
		_calm_t = 0.0
		if not engaged:
			engaged = true
			rushing = false
			for m: Enemy in live:
				m.home = m.global_position
				if near_kill or _wounded_t > 0.0:
					m.ambush(ppos)  # they know where you are
				elif blood:
					m.notice(m.global_position + world.scent_gradient(m.global_position) * 6.0)
				else:
					m.notice(ppos)
	elif engaged:
		_calm_t += dt
		if _calm_t >= float(section("engage").get("calm_seconds", 12.0)):
			_release()


## The hound brain lets go of the player: every wolf back to the pack's business.
func _release() -> void:
	if not engaged:
		return
	engaged = false
	_calm_t = 0.0
	for m: Enemy in alive():
		if m.state in [Enemy.State.CHASE, Enemy.State.ATTACK, Enemy.State.INVESTIGATE, Enemy.State.BREAK, Enemy.State.SCREAM]:
			m._set_state(Enemy.State.IDLE)


func _growl(live: Array, at: Vector3) -> void:
	for m: Enemy in live:
		m._face(at)
	var lead: Enemy = live[0]
	Audio.play_3d(&"voice/hound_growl", lead._mouth(), {"volume_db": 2.0, "max_distance": 60.0, "pitch": 0.85})


## Dusk and night: the pack howls now and then from its range (sound only: no stimulus, no heat).
func _step_howls(dt: float, world: WolfPacks, h: float) -> void:
	for i: int in range(_chorus.size() - 1, -1, -1):
		_chorus[i][0] = float(_chorus[i][0]) - dt
		if float(_chorus[i][0]) <= 0.0:
			var m: Variant = _chorus[i][1]
			_chorus.remove_at(i)
			if m is Enemy and is_instance_valid(m) and (m as Enemy).is_alive():
				howl_once(m as Enemy, world)
	var period: String = world.period()
	if period != "dusk" and period != "night":
		_next_howl = -1.0
		return
	var c: Dictionary = section("howl")
	var every: float = float(c.get("every_hours", 2.5))
	if _next_howl < 0.0:
		_next_howl = h + every * _rng.randf_range(0.1, 0.8)
		return
	if h < _next_howl or (engaged and _mode_t < 30.0) or rushing:
		return
	_next_howl = h + every * _rng.randf_range(0.5, 1.5)
	howl(world)


## The whole pack howls: one starts and the others join in.
func howl(world: WolfPacks) -> void:
	var live: Array = alive()
	if live.is_empty():
		return
	howl_once(live[0], world)
	var ch: Array = section("howl").get("chorus", [0.6, 2.2])
	var t: float = 0.0
	for i: int in range(1, live.size()):
		t += _rng.randf_range(float(ch[0]), float(ch[1])) * 0.5
		_chorus.append([t, live[i]])


func howl_once(m: Enemy, world: WolfPacks) -> void:
	if m.state in [Enemy.State.IDLE, Enemy.State.WANDER] and m.visual != null:
		m.visual.play_once(&"scream", 1.0, [&"idle"] as Array[StringName])
	world.play_howl(m)
