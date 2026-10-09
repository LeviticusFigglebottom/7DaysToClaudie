class_name BaseTech
extends RefCounted
## Base traps and electricity (ADR-0052): the rules as pure functions over the saved state, so
## they are tested without a scene. BaseTechManager runs the commands and ticks; BaseTechNode is
## what a piece shows and does in the world.
##
## A piece's role comes from its StructureDef `provides`:
##   spike_pit / deadfall / tripwire      a trap (state: {armed} for the deadfall)
##   power_source:<watts>                 a generator (state: {on, fuel: hours at full load})
##   power_use:<watts> + work_light | floodlight | turret
##                                        a consumer (state: {on}; a sentry also {ammo})
## Wires join two power pieces; a network's running generators serve its switched-on consumers
## in piece-id order until their watts run out (solve()).
## Tuning: data/config/base_tech.json.

const TRAP_KINDS: PackedStringArray = ["spike_pit", "deadfall", "tripwire"]
const CONSUMER_KINDS: PackedStringArray = ["work_light", "floodlight", "turret"]


static func cfg() -> Dictionary:
	return ContentDB.instance.config(&"base_tech") if ContentDB.instance != null else {}


static func trap_cfg(kind: String) -> Dictionary:
	return (cfg().get("traps", {}) as Dictionary).get(kind, {})


static func power_cfg(section: String) -> Dictionary:
	return (cfg().get("power", {}) as Dictionary).get(section, {})


# --- Roles ---------------------------------------------------------------------------------------

## The trap a piece is ("" for none).
static func trap_kind(def: StructureDef) -> String:
	if def == null:
		return ""
	for k: String in TRAP_KINDS:
		if def.provides.has(k):
			return k
	return ""


## What a powered piece does: "generator", "work_light", "floodlight", "turret" or "".
static func power_kind(def: StructureDef) -> String:
	if def == null:
		return ""
	if source_watts(def) > 0.0:
		return "generator"
	if draw_watts(def) <= 0.0:
		return ""
	for k: String in CONSUMER_KINDS:
		if def.provides.has(k):
			return k
	return "consumer"


static func handles(def: StructureDef) -> bool:
	return trap_kind(def) != "" or power_kind(def) != ""


static func is_power(def: StructureDef) -> bool:
	return power_kind(def) != ""


## Traps are walked through: their colliders only catch the interaction ray.
static func walk_through(def: StructureDef) -> bool:
	return trap_kind(def) != ""


static func _tag_num(def: StructureDef, prefix: String) -> float:
	if def == null:
		return 0.0
	for p: String in def.provides:
		if p.begins_with(prefix):
			return float(p.substr(prefix.length()))
	return 0.0


static func source_watts(def: StructureDef) -> float:
	return _tag_num(def, "power_source:")


static func draw_watts(def: StructureDef) -> float:
	return _tag_num(def, "power_use:")


# --- State ---------------------------------------------------------------------------------------

## WorldState.base_tech, shaped ({traps, power, wires}); {} without a session.
static func world_state() -> Dictionary:
	if Game.session == null:
		return {}
	var st: Dictionary = Game.session.world.base_tech
	for k: String in ["traps", "power"]:
		if not (st.get(k) is Dictionary):
			st[k] = {}
	if not (st.get("wires") is Array):
		st["wires"] = []
	return st


## A new piece's state: a deadfall comes armed, a generator off and empty, a consumer switched on.
static func new_state(def: StructureDef) -> Dictionary:
	match trap_kind(def):
		"deadfall":
			return {"armed": true}
		"spike_pit", "tripwire":
			return {}
	match power_kind(def):
		"generator":
			return {"on": false, "fuel": 0.0}
		"turret":
			return {"on": true, "ammo": 0}
		"":
			return {}
	return {"on": true}


# --- Wires and the grid ----------------------------------------------------------------------------

## Spools a run of `length` metres takes (0 past max_length).
static func wire_spools(length: float) -> int:
	var w: Dictionary = power_cfg("wire")
	if length > float(w.get("max_length", 14.0)) + 0.001:
		return 0
	return maxi(1, ceili(length / maxf(0.1, float(w.get("metres_per_item", 10.0)))))


static func has_wire(wires: Array, a: String, b: String) -> bool:
	for w: Array in wires:
		if (str(w[0]) == a and str(w[1]) == b) or (str(w[0]) == b and str(w[1]) == a):
			return true
	return false


static func wires_of(wires: Array, id: String) -> Array:
	var out: Array = []
	for w: Array in wires:
		if str(w[0]) == id or str(w[1]) == id:
			out.append(w)
	return out


## Who gets power. `nodes`: piece id -> {def: StructureDef, st: its state}; `wires`: [[a, b, ...]].
## Returns {powered: {id: true}, load: {generator id: 0..1}, networks: [[ids]]}. A generator runs
## while it is on and has fuel; consumers of a network are served in id order while the running
## generators' watts cover them (one that does not fit is skipped, a smaller one later may fit).
static func solve(nodes: Dictionary, wires: Array) -> Dictionary:
	var parent: Dictionary = {}
	for id: Variant in nodes:
		parent[str(id)] = str(id)
	var find := func(x: String) -> String:
		var r: String = x
		while str(parent[r]) != r:
			r = str(parent[r])
		return r
	for w: Array in wires:
		var a: String = str(w[0])
		var b: String = str(w[1])
		if parent.has(a) and parent.has(b):
			var ra: String = find.call(a)
			var rb: String = find.call(b)
			if ra != rb:
				parent[ra] = rb
	var groups: Dictionary = {}
	var ids: Array = parent.keys()
	ids.sort()
	for id: String in ids:
		var r: String = find.call(id)
		if not groups.has(r):
			groups[r] = []
		(groups[r] as Array).append(id)
	var powered: Dictionary = {}
	var load: Dictionary = {}
	var networks: Array = []
	for r: String in groups:
		var members: Array = groups[r]
		networks.append(members)
		var supply: float = 0.0
		var gens: Array = []
		for id: String in members:
			var n: Dictionary = nodes[id]
			if running(n["def"], n["st"]):
				supply += source_watts(n["def"])
				gens.append(id)
		var used: float = 0.0
		for id: String in members:
			var n2: Dictionary = nodes[id]
			var draw: float = draw_watts(n2["def"])
			if draw <= 0.0 or not bool((n2["st"] as Dictionary).get("on", true)):
				continue
			if used + draw <= supply + 0.001:
				used += draw
				powered[id] = true
		for g: String in gens:
			load[g] = clampf(used / supply, 0.0, 1.0) if supply > 0.0 else 0.0
	return {"powered": powered, "load": load, "networks": networks}


static func running(def: StructureDef, st: Dictionary) -> bool:
	return source_watts(def) > 0.0 and bool(st.get("on", false)) and float(st.get("fuel", 0.0)) > 0.0


## Fuel burnt over `minutes` at `load` (0..1), in hours at full load; `rate` is the world setting.
static func fuel_burn(minutes: float, load: float, rate: float = 1.0) -> float:
	var idle: float = float(power_cfg("generator").get("idle_burn", 0.35))
	return minutes / 60.0 * lerpf(idle, 1.0, clampf(load, 0.0, 1.0)) * maxf(0.0, rate)


## Burns a running generator's fuel; returns true when it just ran dry.
static func burn(st: Dictionary, minutes: float, load: float, rate: float = 1.0) -> bool:
	var before: float = float(st.get("fuel", 0.0))
	if not bool(st.get("on", false)) or before <= 0.0:
		return false
	st["fuel"] = maxf(0.0, before - fuel_burn(minutes, load, rate))
	return float(st["fuel"]) <= 0.0


## Heat the generator adds to the heat map over `minutes` (attention, ADR-0012).
static func heat(minutes: float, load: float) -> float:
	var idle: float = float(power_cfg("generator").get("idle_burn", 0.35))
	return float(power_cfg("generator").get("heat_per_minute", 0.3)) * minutes * lerpf(idle, 1.0, clampf(load, 0.0, 1.0))


static func tank_hours() -> float:
	return float(power_cfg("generator").get("tank_hours", 8.0))


static func can_hours() -> float:
	return float(power_cfg("generator").get("can_hours", 4.0))


## "3h 20m" / "40m".
static func hours_text(h: float) -> String:
	var m: int = int(round(h * 60.0))
	if m >= 60:
		return "%dh %02dm" % [m / 60, m % 60]
	return "%dm" % m


# --- Traps -----------------------------------------------------------------------------------------

## Whether a body is something the base's traps and sensors act on: a living body in the
## "enemies" group that is not the companion. Ezra (ADR-0058) shares that group as an ally
## (Enemy.ally); TD-300 says no friendly fire at all, so no stake, log, bell, floodlight or nail
## is ever for him (mid-game audit M1: the floodlight warned of him and the sentry shot him in a
## Hum). Wolves (ADR-0055) do count: they come for the player and his base like the Hollowed.
static func is_target(e: Enemy) -> bool:
	return e != null and is_instance_valid(e) and e.is_alive() and e.ally == null


## A trap's damage to the Hollowed after the world setting; a spike pit below dull_below of its
## hit points does half.
static func trap_damage(base: float, hp_frac: float = 1.0, dull_below: float = 0.0) -> float:
	var mult: float = 1.0
	var rules: GameRules = Game.session.rules if Game.session != null else null
	if rules != null and rules.values.has("trap_damage"):
		mult = rules.num("trap_damage")
	return base * mult * (0.5 if hp_frac < dull_below else 1.0)


## Where `to` lies from `from`, for warnings: "north-east, 40 m".
static func bearing_text(from: Vector3, to: Vector3) -> String:
	var d: Vector3 = to - from
	var dist: int = int(round(Vector2(d.x, d.z).length()))
	if dist < 4:
		return "right by you"
	# -Z is north (the tether's compass).
	var ang: float = fposmod(rad_to_deg(atan2(d.x, -d.z)), 360.0)
	var names: PackedStringArray = ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"]
	return "%s, %d m" % [names[int(round(ang / 45.0)) % 8], dist]
