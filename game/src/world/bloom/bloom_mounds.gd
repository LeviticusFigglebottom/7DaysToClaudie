class_name BloomMounds
extends Node3D
## Dawn rooting leaves a mark (DESIGN §6, ADR-0025). Where a Hum survivor roots into the soil at
## dawn (Events.hollowed_rooted), a fungal mound grows over it: a body-length lump of felted
## mycelium with caps fruiting from its back (generated models, MODELS). Mounds live in
## WorldState.mounds, so they are saved; each swells for a few hours, then shrinks and sinks over
## days until it is gone (data/config/bloom.json "mounds"). The ground around one takes the Bloom:
## a dynamic spot in the field (web, threads up nearby trunks, wilting plants).
## Command bloom.harvest_mound tears one open for Bloom mycelium (and sometimes a core sample).

const MODELS: PackedStringArray = ["plants/bloom_mound_a", "plants/bloom_mound_b"]
## LOD0 / LOD1 switch and draw distance (m).
const LOD_SPLIT: float = 28.0
const DRAW_END: float = 160.0
## How often ages, sizes and the field spots are refreshed (s).
const TICK: float = 2.0

var world: Node
var terrain: TerrainManager
## mound id -> its body (Mound)
var _nodes: Dictionary = {}
var _cfg: Dictionary = {}
var _tick: float = 0.0
var _spots_sig: String = ""


## A mound in the world: its meshes and a low collider the interaction ray can pick.
class Mound:
	extends StaticBody3D
	var mound_id: String = ""
	var owner_sys: BloomMounds
	var meshes: Array[MeshInstance3D] = []

	func interact_text(_player: Node) -> String:
		var st: Dictionary = owner_sys.state(mound_id)
		return "" if st.is_empty() or bool(st.get("harvested", false)) else "Tear open the mound"

	func interact(player: Node) -> void:
		Game.execute(&"bloom.harvest_mound", {"player": String((player as Player).state.id), "mound": mound_id})


func setup_world(w: Node) -> void:
	world = w
	terrain = w.get(&"terrain") as TerrainManager
	_cfg = Content.config(&"bloom").get("mounds", {})
	Events.hollowed_rooted.connect(_on_rooted)
	Game.register_command(&"bloom.harvest_mound", _cmd_harvest)
	_sync(true)


func _exit_tree() -> void:
	if Events.hollowed_rooted.is_connected(_on_rooted):
		Events.hollowed_rooted.disconnect(_on_rooted)
	Game.unregister_command(&"bloom.harvest_mound")


func _mounds() -> Dictionary:
	return Game.session.world.mounds if Game.session != null else {}


func state(id: String) -> Dictionary:
	return _mounds().get(id, {})


## Game days (fractional) since the session began.
static func now_days(clock: WorldClock) -> float:
	return clock.total_minutes / WorldClock.MIN_PER_DAY


## Size of a mound `age` days after it rooted (0..1): it swells over `grow_hours`, then shrinks and
## sinks toward 0.35 by the end of its life; 0 once gone (or before it rooted).
static func growth(age_days: float, grow_hours: float, lifetime_days: float) -> float:
	if age_days < 0.0 or age_days >= lifetime_days:
		return 0.0
	var grow: float = clampf(age_days * 24.0 / maxf(grow_hours, 0.01), 0.0, 1.0)
	var decay: float = clampf(age_days / maxf(lifetime_days, 0.01), 0.0, 1.0)
	return smoothstep(0.0, 1.0, grow) * lerpf(1.0, 0.35, decay * decay)


func _on_rooted(entity_id: StringName, _enemy_id: StringName, position: Vector3) -> void:
	if Game.session == null or terrain == null:
		return
	var mounds: Dictionary = _mounds()
	var id: String = "mound:%s" % entity_id
	if mounds.has(id):
		return
	# Oldest first out when there are too many.
	var cap: int = int(_cfg.get("max", 48))
	while mounds.size() >= cap and cap > 0:
		var oldest: String = ""
		var oldest_day: float = INF
		for k: Variant in mounds.keys():
			var d: float = float((mounds[k] as Dictionary).get("day", 0.0))
			if d < oldest_day:
				oldest_day = d
				oldest = str(k)
		mounds.erase(oldest)
	var h: int = Ids.hash31(id)
	var y: float = terrain.height_at(position.x, position.z)
	mounds[id] = {"pos": [position.x, y, position.z], "yaw": float(h % 6283) / 1000.0, "model": MODELS[h % MODELS.size()],
		"day": now_days(Game.session.clock), "harvested": false}
	_sync(true)


func _process(delta: float) -> void:
	_tick += delta
	if _tick < TICK:
		return
	_tick = 0.0
	_sync(false)


## Matches the bodies, their sizes and the field spots to WorldState.mounds; drops the dead ones.
func _sync(force: bool) -> void:
	if Game.session == null:
		return
	var mounds: Dictionary = _mounds()
	var now: float = now_days(Game.session.clock)
	var life: float = float(_cfg.get("lifetime_days", 6.0))
	var grow_h: float = float(_cfg.get("grow_hours", 6.0))
	var spots: Array = []
	for id: Variant in mounds.keys():
		var st: Dictionary = mounds[id]
		var g: float = growth(now - float(st.get("day", now)), grow_h, life)
		if bool(st.get("harvested", false)):
			g *= 0.55
		if g <= 0.0 and now - float(st.get("day", now)) >= life:
			mounds.erase(id)
			continue
		var p: Array = st.get("pos", [0, 0, 0])
		spots.append({"pos": Vector2(float(p[0]), float(p[2])), "radius": float(_cfg.get("radius", 2.4)) * maxf(g, 0.3),
			"strength": float(_cfg.get("strength", 0.85)) * maxf(g, 0.25)})
		var node: Mound = _nodes.get(id)
		if node == null:
			node = _make(str(id), st)
		_size(node, g)
	for id: Variant in _nodes.keys():
		if not mounds.has(id):
			(_nodes[id] as Node).queue_free()
			_nodes.erase(id)
	# Re-upload the field only when the spots changed (sizes are quantised by the signature).
	var sig: String = ",".join(spots.map(func(s: Dictionary) -> String: return "%.1f:%.1f:%.2f" % [s["pos"].x, s["pos"].y, s["strength"]]))
	if (force or sig != _spots_sig) and terrain != null and terrain.bloom != null and terrain.bloom.field != null:
		_spots_sig = sig
		terrain.bloom.set_spot_source(&"mounds", spots)


func _make(id: String, st: Dictionary) -> Mound:
	var m := Mound.new()
	m.name = id.replace(":", "_")
	m.mound_id = id
	m.owner_sys = self
	m.collision_layer = 1 << 12
	m.collision_mask = 0
	var model: String = str(st.get("model", MODELS[0]))
	for lod: int in 2:
		var mi := MeshInstance3D.new()
		mi.mesh = ModelLibrary.mesh(model if lod == 0 else model + "_lod1", "rock")
		mi.visibility_range_begin = 0.0 if lod == 0 else LOD_SPLIT
		mi.visibility_range_end = LOD_SPLIT if lod == 0 else DRAW_END
		mi.visibility_range_begin_margin = 0.0 if lod == 0 else 4.0
		mi.visibility_range_end_margin = 4.0
		mi.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
		m.add_child(mi)
		m.meshes.append(mi)
	var cs := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(0.8, 0.3, 1.6)
	cs.shape = box
	cs.position = Vector3(0.0, 0.12, 0.0)
	m.add_child(cs)
	var p: Array = st.get("pos", [0, 0, 0])
	add_child(m)
	# Lying on the slope, a little into it, so the downhill side never floats.
	var up := Vector3.UP
	if terrain != null:
		up = terrain.normal_at(float(p[0]), float(p[2]))
	var b := Basis(Quaternion(Vector3.UP, up)) * Basis(Vector3.UP, float(st.get("yaw", 0.0)))
	m.global_transform = Transform3D(b, Vector3(float(p[0]), float(p[1]) - 0.04, float(p[2])))
	_nodes[id] = m
	return m


## Grows, shrinks and sinks a mound with its age (the skirt keeps it rooted as it sinks).
static func _size(m: Mound, g: float) -> void:
	var s: float = maxf(g, 0.02)
	for mi: MeshInstance3D in m.meshes:
		mi.scale = Vector3(lerpf(0.75, 1.0, s), s, lerpf(0.8, 1.0, s))
		mi.position.y = -0.06 * (1.0 - s)


## Tears a mound open: Bloom mycelium (and a chance of a core sample) for a player within reach.
## args: {player, mound}. Returns {ok, items} or {ok: false, error}.
func _cmd_harvest(args: Dictionary) -> Dictionary:
	var id: String = str(args.get("mound", ""))
	var st: Dictionary = state(id)
	if st.is_empty():
		return {"ok": false, "error": "no such mound"}
	if bool(st.get("harvested", false)):
		return {"ok": false, "error": "already torn open"}
	var ps: PlayerState = Game.session.players.get(StringName(str(args.get("player", "")))) if Game.session != null else null
	if ps == null:
		return {"ok": false, "error": "no such player"}
	var p: Array = st["pos"]
	if ps.position.distance_to(Vector3(float(p[0]), float(p[1]), float(p[2]))) > float(_cfg.get("reach", 2.6)) + 1.0:
		return {"ok": false, "error": "too far"}
	var rng: RandomNumberGenerator = Game.session.rng.stream("bloom_mounds")
	var got: Dictionary = {}
	var yields: Dictionary = _cfg.get("yield", {"bloom_mycelium": [2, 4]})
	for item: Variant in yields.keys():
		var r: Array = yields[item]
		got[str(item)] = rng.randi_range(int(r[0]), int(r[1]))
	if rng.randf() < float(_cfg.get("sample_chance", 0.0)):
		got["bloom_sample"] = 1
	for item: String in got:
		if int(got[item]) > 0:
			Game.execute(&"world.pickup_item", {"player": String(ps.id), "item": item, "count": int(got[item])})
	st["harvested"] = true
	Audio.play_3d(&"sfx/foliage_rustle", Vector3(float(p[0]), float(p[1]), float(p[2])), {"volume_db": -3.0})
	_sync(true)
	return {"ok": true, "items": got}
