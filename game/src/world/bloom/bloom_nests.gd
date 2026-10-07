class_name BloomNests
extends Node3D
## Bloom nests (ADR-0055): grown masses of Bloom in the deep woods, a fire-based objective.
##
## A nest is placed (place(), the encounter scatter's on_place, or a region feature
## {"type": "nest", "def": id, "at": [x, z], "yaw": deg} when its region attaches) and built from
## its NestDef: generated props (their burned variant once it is dead; a box of each prop's size
## before `make assets`), and a core in its hollow that takes FIRE damage only (a torch blow:
## DamageInfo type "fire"). While the player is within its seed range it keeps its guards round it
## (Hollowed asleep in its roots and a wanderer or two; a killed one comes back from the pods after
## the def's respawn hours until it is burned). At zero hp it burns: flames on its heart and pods
## (PropLights), a smoke column (Smoke), its own roaring burn loop, a wet fungal shriek that is a
## loud sound (Stimuli), its guards wake and come; then it is dead: it collapses (a thud, dust, the
## pods split), its pods are searchable remains (Pod: the def's loot table, rolled on the first
## search and saved), XP (burn_nest), Events.nest_burned (the directive event), its smoke lingers a
## while and its Bloom ground fades.
##
## The Bloom ground is a spot per nest in the Bloom field (BloomWorld.set_spot_source(&"nests")):
## the field's authored zones are fixed once built (workers read them unlocked), so runtime nests
## add and fade spots; all live nests are re-sent whenever one changes. Its felted mat is a clearing
## in the vegetation (VegetationManager.set_clearings(&"nests")): nothing grows through it.
## State: WorldState.nests, by placement id ({burned, hp, seeded_dead, burned_at, pods: {prop index:
## [item dicts]}}); un-placing a nest (its region streamed out) frees its nodes and guards and keeps
## its state.

const FEATURE: String = "nest"
const FEATURE_KEYS: PackedStringArray = ["type", "id", "def", "at", "yaw", "_doc"]
const SPOT_SOURCE: StringName = &"nests"
## Seconds between seeding / fading passes.
const TICK: float = 1.0
## Physics layer of the props and the core (static world).
const LAYER: int = 1
const DRAW_END: float = 320.0
## Seconds between "only fire" reminders.
const HINT_EVERY: float = 6.0
## Its own sounds (tools/assetgen/audio/sounds/bloom_nest.py).
const SND_SCREAM: StringName = &"voice/nest_scream"
const SND_BURN: StringName = &"sfx/nest_burn_loop"
const SND_COLLAPSE: StringName = &"sfx/nest_collapse"
## Seconds the smoke goes on rising, thinning, once the nest is dead.
const SMOKE_LINGER: float = 150.0
## Metres past its props' reach that its mat keeps clear of vegetation.
const MAT_MARGIN: float = 1.0
const POD_CONTAINER: StringName = &"nest_pod"
var world: Node
## placement id -> {id, def: StringName, pos: Vector3, yaw: float (rad), region: String}
var placements: Dictionary = {}
## placement id -> Nest
var _nodes: Dictionary = {}
## placement id -> {slot index: Enemy}
var _guards: Dictionary = {}
## guard entity id -> [placement id, slot]
var _slot_of: Dictionary = {}
## placement id -> seconds of burning left
var _burning: Dictionary = {}
## placement id -> who lit it (player id)
var _burner: Dictionary = {}
var _tick: float = 0.0
var _spots_sig: String = "-"
var _hint_t: float = 0.0
var _encounters_hooked: bool = false
var _hook_tries: int = 0
## placement id -> Smoke (outlives the nest's own nodes, which are rebuilt when it dies)
var _smoke: Dictionary = {}
var _clear_sig: String = "-"
## The last sounds it played (newest last, a few kept): tests read them, nothing else does.
var played: Array[StringName] = []


## A placed nest: its props and, while it lives, its core.
class Nest:
	extends Node3D
	var nest_id: String = ""
	var core: Core = null
	var fires: Array[Node3D] = []


## The burnable heart: forwards hits to BloomNests.damage().
class Core:
	extends StaticBody3D
	var nest_id: String = ""
	var owner_sys: BloomNests

	func take_damage(info: DamageInfo) -> void:
		owner_sys.damage(nest_id, info)


## A dead nest's split pod: searchable remains, opened like a corpse or a crate (the salvage roll's
## container flap). Its loot is rolled from the nest's loot table on the first search and kept in
## the nest's state (`pods`), so a looted pod stays looted. `index` is the pod's prop index (-1: the
## heart of a nest with no pod).
class Pod:
	extends StaticBody3D
	var nest_id: String = ""
	var index: int = -1
	var owner_sys: BloomNests
	## data/loot/containers/nests.json `nest_pod`: its name, slots and search time.
	var cdef: ContainerDef = null
	var inventory: Inventory = null
	var container_id: StringName:
		get:
			return StringName("nest:%s:pod%d" % [nest_id, index])

	func searched() -> bool:
		return owner_sys != null and owner_sys.pod_searched(nest_id, index)

	func interact_text(_player: Player) -> String:
		var nm: String = cdef.display_name if cdef != null else "Split Pod"
		if not searched():
			return "Search %s" % nm
		return "%s (empty)" % nm if inventory == null or inventory.stacks.is_empty() else "Open %s" % nm

	func interact_hold_time(_player: Player) -> float:
		return 0.0 if searched() else (cdef.search_time if cdef != null else 1.5)

	func interact(player: Player) -> void:
		var first: bool = not searched()
		inventory = owner_sys.pod_inventory(nest_id, index, player.state)
		if inventory == null:
			return
		if first:
			Audio.play_3d(&"sfx/search_container", global_position, {"volume_db": -6.0, "pitch": 0.8})
			if Stimuli.current != null and cdef != null and cdef.noise > 0.0:
				Stimuli.current.emit_sound(global_position, cdef.noise, &"search", player.state.id)
		var ui: Node = Game.world.get(&"ui") if Game.world != null else null
		if ui != null and ui.has_method(&"open_container"):
			ui.call(&"open_container", self)
		else:
			Game.execute(&"container.take_all", {"player": player.state.id, "container": self})

	func on_contents_changed() -> void:
		owner_sys.save_pod(nest_id, index, inventory)


## The smoke over a burning nest: a dark column of CPU particles (cheap at this count, the same on
## every renderer; none headless, where the node stays as the marker). Once the nest is dead it
## smoulders: the column thins out over `linger` seconds, stops, and is freed when the last puff
## has risen.
class Smoke:
	extends Node3D
	const LIFE: float = 10.0
	var particles: CPUParticles3D = null
	## Smouldering (the nest is dead): `linger` seconds of thinning smoke left.
	var smouldering: bool = false
	var linger: float = 0.0
	var _total: float = 1.0

	func start(size: float) -> void:
		if DisplayServer.get_name() == "headless":
			return
		var p := CPUParticles3D.new()
		p.name = "Column"
		p.amount = 56
		p.lifetime = LIFE
		p.local_coords = false
		p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		p.emission_shape = CPUParticles3D.EMISSION_SHAPE_SPHERE
		p.emission_sphere_radius = 0.6 * size
		p.direction = Vector3.UP
		p.spread = 12.0
		p.initial_velocity_min = 1.4
		p.initial_velocity_max = 2.4
		# A little drift downwind as it rises, slowing (it spreads into a haze over the canopy).
		p.gravity = Vector3(0.3, 0.2, 0.12)
		p.damping_min = 0.08
		p.damping_max = 0.2
		p.scale_amount_min = 1.0 * size
		p.scale_amount_max = 1.7 * size
		var grow := Curve.new()
		grow.max_value = 4.0
		grow.add_point(Vector2(0.0, 0.5))
		grow.add_point(Vector2(1.0, 3.4))
		p.scale_amount_curve = grow
		p.anim_speed_min = 0.5
		p.anim_speed_max = 0.8
		var fade := Gradient.new()
		fade.set_color(0, Color(1, 1, 1, 0.0))
		fade.set_color(1, Color(1, 1, 1, 0.0))
		fade.add_point(0.06, Color(1, 1, 1, 0.85))
		fade.add_point(0.55, Color(1, 1, 1, 0.45))
		p.color_ramp = fade
		var mat := StandardMaterial3D.new()
		mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		mat.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
		mat.billboard_keep_scale = true
		mat.vertex_color_use_as_albedo = true
		# Burning wet flesh: a thick smoke, dark and a little yellow-brown.
		mat.albedo_color = Color(0.24, 0.22, 0.18, 0.9)
		var tex: String = "res://assets/generated/textures/fx_smoke_flipbook.png"
		if ResourceLoader.exists(tex):
			mat.albedo_texture = load(tex)
			mat.particles_anim_h_frames = 8
			mat.particles_anim_v_frames = 8
			mat.particles_anim_loop = true
		var q := QuadMesh.new()
		q.size = Vector2(2.4, 2.4)
		q.material = mat
		p.mesh = q
		p.emitting = true
		add_child(p)
		particles = p

	func smoulder(seconds: float) -> void:
		smouldering = true
		linger = seconds
		_total = maxf(seconds, 0.01)
		if particles != null:
			# Paler once the flames are out: steam and ash more than soot.
			((particles.mesh as PrimitiveMesh).material as StandardMaterial3D).albedo_color = Color(0.42, 0.4, 0.37, 0.8)

	## Advances the smoulder; true once it is gone (the caller frees it).
	func step(delta: float) -> bool:
		if not smouldering:
			return false
		linger -= delta
		if particles != null:
			particles.color = Color(1, 1, 1, clampf(linger / _total, 0.0, 1.0) * 0.8 + 0.2)
			if linger <= 0.0 and particles.emitting:
				particles.emitting = false
		return linger <= -LIFE


func setup_world(w: Node) -> void:
	world = w
	Events.enemy_killed.connect(_on_enemy_killed)
	var t: Node = _terrain()
	if t != null:
		if t.has_signal(&"region_attached"):
			t.connect(&"region_attached", _on_region_attached)
			t.connect(&"region_detached", _on_region_detached)
		var regions: Variant = t.get(&"regions")
		if regions is Dictionary:
			var ids: Array = (regions as Dictionary).keys()
			ids.sort()
			for rid: Variant in ids:
				_on_region_attached(str(rid))
	_hook_encounters()


func _exit_tree() -> void:
	if Events.enemy_killed.is_connected(_on_enemy_killed):
		Events.enemy_killed.disconnect(_on_enemy_killed)
	var b: Node = _bloom()
	if b != null and b.has_method(&"set_spot_source"):
		b.call(&"set_spot_source", SPOT_SOURCE, [])


# --- Placement -------------------------------------------------------------------------------------

## Places a nest (idempotent by id): builds it, puts its Bloom on the ground, and (when it is
## alive and the player near) its guards come with the next pass. `pos` is on the ground, `yaw`
## in radians. Returns false for an unknown def.
func place(id: String, def_id: StringName, pos: Vector3, yaw: float) -> bool:
	var def: NestDef = Content.get_def(&"nest", def_id) as NestDef
	if def == null:
		push_warning("BloomNests: unknown nest def '%s' for %s" % [def_id, id])
		return false
	if placements.has(id):
		return true
	placements[id] = {"id": id, "def": def_id, "pos": pos, "yaw": yaw, "region": ""}
	var st: Dictionary = state(id)
	_build(id)
	# Saved mid-burn: it caught, so it finishes burning.
	if not bool(st.get("burned", false)) and float(st.get("hp", def.hp)) <= 0.0:
		_ignite(id, &"")
	_sync_spots()
	_sync_clearings()
	return true


## The encounter scatter's hook (ADR-0054): {id, kind, def, pos (on the ground), yaw, region, seed}.
func on_place(placement: Dictionary) -> void:
	var id: String = str(placement.get("id", ""))
	var p: Variant = placement.get("pos", Vector3.ZERO)
	if id == "" or not p is Vector3:
		push_warning("BloomNests: bad placement %s" % placement)
		return
	if place(id, StringName(str(placement.get("def", ""))), p, float(placement.get("yaw", 0.0))):
		placements[id]["region"] = str(placement.get("region", ""))


## Takes a nest out of play (its region streamed out): frees its nodes and guards, keeps its state.
func on_unplace(id: Variant) -> void:
	var key: String = str(id)
	if not placements.has(key):
		return
	_despawn_guards(key)
	_burning.erase(key)
	var sm: Smoke = _smoke.get(key)
	if sm != null and is_instance_valid(sm):
		sm.queue_free()
	_smoke.erase(key)
	var n: Nest = _nodes.get(key)
	if n != null and is_instance_valid(n):
		n.queue_free()
	_nodes.erase(key)
	placements.erase(key)
	_sync_spots()
	_sync_clearings()


## Every nest feature of a region ({"type": "nest", "def", "at": [x, z], "yaw": degrees}), as
## placements {id, def, at: Vector2, yaw (rad)}; malformed ones are reported and skipped.
static func region_features(region: Dictionary) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var rid: String = str(region.get("id", ""))
	var k: int = 0
	for fv: Variant in region.get("features", []):
		if not fv is Dictionary or str((fv as Dictionary).get("type", "")) != FEATURE:
			continue
		var f: Dictionary = fv
		var where: String = "%s nest #%d" % [rid, k]
		var id: String = "%s:%s" % [rid, str(f.get("id", "nest_%d" % k))]
		k += 1
		for key: Variant in f.keys():
			if not FEATURE_KEYS.has(str(key)) and not str(key).begins_with("_"):
				push_error("BloomNests: %s has unknown field '%s'" % [where, key])
		var at: Variant = f.get("at", null)
		if not at is Array or (at as Array).size() < 2 or str(f.get("def", "")) == "":
			push_error("BloomNests: %s needs 'def' and 'at': [x, z]" % where)
			continue
		out.append({"id": id, "def": StringName(str(f["def"])), "at": Vector2(float(at[0]), float(at[1])),
			"yaw": deg_to_rad(float(f.get("yaw", 0.0)))})
	return out


func _on_region_attached(rid: String) -> void:
	var wdef: WorldDef = world.get(&"world_def") as WorldDef if world != null else null
	if wdef == null:
		return
	for f: Dictionary in region_features(wdef.region_data(rid)):
		var at: Vector2 = f["at"]
		if place(f["id"], f["def"], Vector3(at.x, _height(at.x, at.y), at.y), float(f["yaw"])):
			placements[f["id"]]["region"] = rid


func _on_region_detached(rid: String) -> void:
	for id: Variant in placements.keys():
		if str((placements[id] as Dictionary).get("region", "")) == rid:
			on_unplace(id)


## Registers kind `nest` with the hub's encounter scatter (ADR-0054) when it exists: a world module
## `encounters`, or a global class Encounters with a static register_kind. Tried at setup and on
## the first passes (the module may come after this one).
func _hook_encounters() -> void:
	if _encounters_hooked:
		return
	var enc: Object = world.get(&"encounters") as Object if world != null else null
	if enc == null:
		for c: Dictionary in ProjectSettings.get_global_class_list():
			if str(c.get("class", "")) == "Encounters":
				enc = load(str(c["path"]))
				break
	if enc != null and enc.has_method(&"register_kind"):
		enc.call(&"register_kind", StringName(FEATURE), on_place, on_unplace)
		_encounters_hooked = true


# --- State -----------------------------------------------------------------------------------------

## A nest's saved state (made on first use): {burned, hp, seeded_dead: [{i, at}], burned_at}.
func state(id: String) -> Dictionary:
	if Game.session == null:
		return {}
	var all: Dictionary = Game.session.world.nests
	if not all.has(id):
		var def: NestDef = _def(id)
		all[id] = {"burned": false, "hp": def.hp if def != null else 100.0, "seeded_dead": []}
	return all[id]


func _def(id: String) -> NestDef:
	var p: Dictionary = placements.get(id, {})
	return Content.get_def(&"nest", StringName(str(p.get("def", "")))) as NestDef if not p.is_empty() else null


func is_burned(id: String) -> bool:
	return bool(state(id).get("burned", false))


func is_burning(id: String) -> bool:
	return _burning.has(id)


func guards(id: String) -> Array[Enemy]:
	var out: Array[Enemy] = []
	for e: Variant in (_guards.get(id, {}) as Dictionary).values():
		if e is Enemy and is_instance_valid(e):
			out.append(e)
	return out


func core_of(id: String) -> Core:
	var n: Nest = _nodes.get(id)
	return n.core if n != null and is_instance_valid(n) else null


static func _now() -> float:
	return Game.session.clock.total_minutes if Game.session != null and Game.session.clock != null else 0.0


# --- Building --------------------------------------------------------------------------------------

func _build(id: String) -> void:
	var old: Nest = _nodes.get(id)
	if old != null and is_instance_valid(old):
		old.queue_free()
	var p: Dictionary = placements[id]
	var def: NestDef = _def(id)
	var burned: bool = is_burned(id)
	var n := Nest.new()
	n.nest_id = id
	n.name = "Nest_" + id.replace(":", "_").replace("/", "_")
	add_child(n)
	var pos: Vector3 = p["pos"]
	var yaw: float = float(p["yaw"])
	n.global_transform = Transform3D(Basis(Vector3.UP, yaw), pos)
	for k: int in def.props.size():
		_add_prop(n, def.props[k], burned, pos, yaw, k)
	if burned and def.pods().is_empty():
		# No pod to split: what it held lies in the ash of its heart.
		var heart: Pod = _new_pod(id, -1)
		heart.name = "Heart"
		var hs := CollisionShape3D.new()
		var hb := BoxShape3D.new()
		hb.size = def.core_size
		hs.shape = hb
		heart.add_child(hs)
		n.add_child(heart)
		heart.position = def.core_offset
	if not burned:
		var c := Core.new()
		c.name = "Core"
		c.nest_id = id
		c.owner_sys = self
		c.collision_layer = LAYER
		c.collision_mask = 0
		var cs := CollisionShape3D.new()
		var box := BoxShape3D.new()
		box.size = def.core_size
		cs.shape = box
		c.add_child(cs)
		n.add_child(c)
		c.position = def.core_offset
		n.core = c
	_nodes[id] = n


func _add_prop(n: Nest, entry: Dictionary, burned: bool, pos: Vector3, yaw: float, k: int) -> void:
	var pd: PropDef = Content.get_def(&"prop", entry["prop"]) as PropDef
	if pd == null:
		return
	var model: String = str(pd.variants.get("destroyed" if burned else "clean", pd.variants.get("clean", "")))
	var off: Vector3 = entry["offset"]
	var sc: float = float(entry.get("scale", 1.0))
	var wp: Vector3 = pos + off.rotated(Vector3.UP, yaw)
	# Each prop sits on the ground where it stands (a nest straddles uneven ground).
	wp.y = _height(wp.x, wp.z) + off.y - 0.05
	# A dead nest's pods are split open: searchable remains.
	var pod: bool = burned and bool(entry.get("pod", false))
	var body: StaticBody3D = _new_pod(n.nest_id, k) if pod else StaticBody3D.new()
	body.name = "Prop%d_%s" % [k, pd.id]
	body.collision_layer = LAYER
	body.collision_mask = 0
	n.add_child(body)
	body.global_transform = Transform3D(Basis(Vector3.UP, yaw + deg_to_rad(float(entry.get("rot", 0.0)))).scaled(Vector3.ONE * sc), wp)
	var mi := MeshInstance3D.new()
	var mesh: Mesh = ModelLibrary.generated_mesh(model) if model != "" else null
	if mesh == null:
		# Stand-in before `make assets`: a box of the prop's size, standing on the ground.
		var bm := BoxMesh.new()
		bm.size = pd.size
		mesh = bm
		mi.position = Vector3(0.0, pd.size.y * 0.5, 0.0)
	mi.mesh = mesh
	mi.visibility_range_end = DRAW_END
	mi.visibility_range_end_margin = 10.0
	mi.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
	body.add_child(mi)
	var shapes: Array = ModelLibrary.shapes(model) if ModelLibrary.generated_mesh(model) != null else []
	for s: Variant in shapes:
		var cs := CollisionShape3D.new()
		cs.shape = (s as Dictionary)["shape"]
		cs.transform = (s as Dictionary)["transform"]
		body.add_child(cs)
	# (A pod needs a body the interaction ray can hit even before its model exists.)
	if shapes.is_empty() and (pd.collision == "box" or pod):
		var cs2 := CollisionShape3D.new()
		var box := BoxShape3D.new()
		box.size = pd.size
		cs2.shape = box
		cs2.position = Vector3(0.0, pd.size.y * 0.5, 0.0)
		body.add_child(cs2)


func _height(x: float, z: float) -> float:
	if world != null and world.has_method(&"height_at"):
		return float(world.call(&"height_at", x, z))
	return 0.0


func _terrain() -> Node:
	return world.get(&"terrain") as Node if world != null else null


func _bloom() -> Node:
	var t: Node = _terrain()
	return t.get(&"bloom") as Node if t != null else null


func _ai() -> Node:
	return world.get(&"ai") as Node if world != null else null


func _player() -> Node3D:
	return world.get(&"player") as Node3D if world != null else null


# --- Damage and burning ----------------------------------------------------------------------------

## A hit on a nest's core: fire hurts it, nothing else does.
func damage(id: String, info: DamageInfo) -> void:
	if not placements.has(id) or is_burned(id) or _burning.has(id):
		return
	var at: Vector3 = info.hit_pos if info.hit_pos != Vector3.ZERO else (placements[id]["pos"] as Vector3) + Vector3.UP
	if info.type != &"fire":
		Audio.play_3d(&"sfx/hit_flesh", at, {"volume_db": -4.0, "pitch": 0.7})
		if _hint_t <= 0.0 and Game.session != null and info.source_id == Game.session.local_player_id:
			_hint_t = HINT_EVERY
			Events.player_status_message.emit("The flesh closes over the wound. Only fire will kill it.", &"warning")
		return
	var st: Dictionary = state(id)
	st["hp"] = maxf(0.0, float(st.get("hp", 0.0)) - info.amount)
	FxLibrary.burst(self, "sparks", at, -info.direction, 1.2)
	Audio.play_3d(&"sfx/fire_ignite", at, {"volume_db": -2.0})
	# It feels it: its guards stir.
	if Stimuli.current != null:
		Stimuli.current.emit_sound(at, 18.0, &"nest_pain", StringName("nest:" + id))
	if float(st["hp"]) <= 0.0:
		_ignite(id, info.source_id)


## It caught: flames over its heart and pods, the smoke column, its burn roaring, the shriek; its
## guards rise and come.
func _ignite(id: String, by: StringName) -> void:
	var def: NestDef = _def(id)
	if def == null or _burning.has(id):
		return
	_burning[id] = def.burn_seconds
	_burner[id] = by
	var p: Dictionary = placements[id]
	var pos: Vector3 = p["pos"]
	var yaw: float = float(p["yaw"])
	var n: Nest = _nodes.get(id)
	# The heart's flames are big enough to show over the root mass's collar; the pods' smaller.
	var heart_fire: float = maxf(1.6, def.core_size.x * 1.6)
	if n != null and is_instance_valid(n):
		var fires: Array = [[def.core_offset + Vector3(0.0, def.core_size.y * 0.3, 0.0), heart_fire, 5.0]]
		for pi: int in def.pods():
			fires.append([def.props[pi]["offset"] + Vector3(0.0, 0.5 * float(def.props[pi].get("scale", 1.0)), 0.0), 1.2, 3.0])
		for f: Array in fires:
			var o: Vector3 = f[0]
			var l: Node3D = PropLights.light_node({"color": "#ff8a3a", "energy": f[2], "range": 12.0, "flicker": 0.5, "fx": "fire",
				"fx_size": f[1], "offset": [o.x, o.y, o.z]}, Transform3D.IDENTITY)
			n.add_child(l)
			n.fires.append(l)
		# Its own burn: a big wet fire roaring (the PropLights crackles under it are campfire-sized).
		var loop := AudioStreamPlayer3D.new()
		loop.name = "BurnLoop"
		loop.stream = Audio.stream(SND_BURN)
		loop.bus = &"SFX"
		loop.unit_size = 10.0
		loop.max_distance = 110.0
		loop.volume_db = 2.0
		loop.position = def.core_offset
		loop.autoplay = loop.stream != null
		loop.set_meta(&"sound_id", SND_BURN)
		n.add_child(loop)
		_note(SND_BURN)
	var smoke: Smoke = _smoke.get(id)
	if smoke == null or not is_instance_valid(smoke):
		smoke = Smoke.new()
		smoke.name = "Smoke_" + id.replace(":", "_").replace("/", "_")
		add_child(smoke)
		smoke.global_position = pos + def.core_offset.rotated(Vector3.UP, yaw) + Vector3.UP * def.core_size.y
		smoke.start(clampf(def.core_size.x / 1.4, 0.6, 1.6))
		_smoke[id] = smoke
	var mouth: Vector3 = pos + Vector3.UP * 1.2
	_play(SND_SCREAM, mouth, {"volume_db": 10.0, "max_distance": 260.0, "unit_size": 18.0, "occlusion": false})
	_play(&"sfx/fire_ignite", mouth, {"volume_db": 4.0})
	if Stimuli.current != null:
		Stimuli.current.emit_sound(mouth, def.burn_scream, &"scream", StringName("nest:" + id))
	var target: Vector3 = _player().global_position if _player() != null else pos
	for e: Enemy in guards(id):
		if e.is_alive():
			e.ambush(target)
	Events.player_status_message.emit("The nest shrieks as it burns.", &"danger")


## Burned out: it collapses (the thud, dust, its pods split open as searchable remains), pays the
## burner, and its smoke smoulders on a while.
func _die(id: String) -> void:
	_burning.erase(id)
	var def: NestDef = _def(id)
	var st: Dictionary = state(id)
	st["burned"] = true
	st["hp"] = 0.0
	st["burned_at"] = _now()
	var pos: Vector3 = placements[id]["pos"]
	var yaw: float = float(placements[id]["yaw"])
	var heart: Vector3 = pos + def.core_offset.rotated(Vector3.UP, yaw)
	_play(SND_COLLAPSE, heart, {"volume_db": 6.0, "max_distance": 140.0, "unit_size": 12.0})
	FxLibrary.burst(self, "dust", heart, Vector3.UP, 3.0)
	for pi: int in def.pods():
		var at: Vector3 = pos + (def.props[pi]["offset"] as Vector3).rotated(Vector3.UP, yaw) + Vector3.UP * 0.6
		FxLibrary.burst(self, "gore", at, Vector3.UP, 1.2)
		FxLibrary.burst(self, "dust", at, Vector3.UP, 1.4)
	var smoke: Smoke = _smoke.get(id)
	if smoke != null and is_instance_valid(smoke):
		smoke.smoulder(SMOKE_LINGER)
	var by: StringName = _burner.get(id, &"")
	_burner.erase(id)
	var ps: PlayerState = Game.session.players.get(by) if Game.session != null and by != &"" else null
	if ps == null:
		ps = Game.local_player()
	if ps != null:
		ps.progression.award("burn_nest", def.xp)
	Events.nest_burned.emit(id, def.id, pos)
	Events.player_status_message.emit("The nest falls in on itself. Its pods have split open.", &"info")
	# Burned: charred props, split pods to search, no core, the fires out.
	_build(id)
	_sync_spots()


func _play(sound_id: StringName, at: Vector3, opts: Dictionary) -> void:
	_note(sound_id)
	Audio.play_3d(sound_id, at, opts)


func _note(sound_id: StringName) -> void:
	played.append(sound_id)
	if played.size() > 8:
		played.remove_at(0)


# --- Pods ------------------------------------------------------------------------------------------

func _new_pod(id: String, k: int) -> Pod:
	var pod := Pod.new()
	pod.nest_id = id
	pod.index = k
	pod.owner_sys = self
	pod.cdef = Content.get_def(&"container", POD_CONTAINER) as ContainerDef
	pod.collision_layer = LAYER
	pod.collision_mask = 0
	pod.inventory = _saved_pod(id, k)
	return pod


## True once a dead nest's pod `k` was searched (its loot rolled).
func pod_searched(id: String, k: int) -> bool:
	return (state(id).get("pods", {}) as Dictionary).has(str(k))


## The pods of a placed nest's built nodes (searchable once it is dead).
func pods_of(id: String) -> Array[Pod]:
	var out: Array[Pod] = []
	var n: Nest = _nodes.get(id)
	if n == null or not is_instance_valid(n):
		return out
	for c: Node in n.get_children():
		if c is Pod:
			out.append(c)
	return out


## What a searched pod still holds (null before its first search).
func _saved_pod(id: String, k: int) -> Inventory:
	var pods: Dictionary = state(id).get("pods", {})
	if not pods.has(str(k)):
		return null
	var inv: Inventory = _pod_inv(id, k)
	for d: Variant in pods[str(k)]:
		var s: ItemStack = ItemStack.from_dict(d)
		if s != null:
			inv.add(s)
	return inv


func _pod_inv(id: String, k: int) -> Inventory:
	var inv := Inventory.new()
	inv.owner_id = StringName("nest:%s:pod%d" % [id, k])
	var cd: ContainerDef = Content.get_def(&"container", POD_CONTAINER) as ContainerDef
	inv.max_slots = cd.slots if cd != null else 8
	return inv


## A dead nest's pod contents for `searcher`: rolled from the nest's loot table on the first search
## (seeded by world seed, nest and pod, so it is the same in any order), saved, then what is left.
func pod_inventory(id: String, k: int, searcher: PlayerState) -> Inventory:
	var def: NestDef = _def(id)
	if def == null or not is_burned(id):
		return null
	if pod_searched(id, k):
		for pod: Pod in pods_of(id):
			if pod.index == k and pod.inventory != null:
				return pod.inventory
		return _saved_pod(id, k)
	var inv: Inventory = _pod_inv(id, k)
	if def.loot != &"":
		var rng := RandomNumberGenerator.new()
		rng.seed = Ids.hash64("nest_pod:%d:%s:%d" % [Game.session.world_seed, id, k])
		var ctx := LootRoller.Context.new(2, Game.session.gamestage(searcher) if searcher != null else 1, rng)
		if searcher != null:
			ctx.quality_bonus = searcher.progression.modifier("loot_quality_bonus")
		for r: int in def.loot_rolls:
			for s: ItemStack in LootRoller.roll(def.loot, ctx):
				inv.add(s)
	save_pod(id, k, inv)
	return inv


## Keeps what a pod holds in the nest's state (a looted pod stays looted through saves).
func save_pod(id: String, k: int, inv: Inventory) -> void:
	var st: Dictionary = state(id)
	var pods: Dictionary = st.get("pods", {})
	var items: Array = []
	if inv != null:
		for s: ItemStack in inv.stacks:
			items.append(s.to_dict())
	pods[str(k)] = items
	st["pods"] = pods



# --- The loop --------------------------------------------------------------------------------------

func _process(delta: float) -> void:
	_hint_t = maxf(0.0, _hint_t - delta)
	for id: Variant in _burning.keys():
		_burning[id] = float(_burning[id]) - delta
		if float(_burning[id]) <= 0.0:
			_die(str(id))
	for sid: Variant in _smoke.keys():
		var sm: Smoke = _smoke[sid]
		if not is_instance_valid(sm):
			_smoke.erase(sid)
		elif sm.step(delta):
			sm.queue_free()
			_smoke.erase(sid)
	_tick += delta
	if _tick < TICK:
		return
	_tick = 0.0
	tick()


## One pass: hooks the encounter scatter if it arrived, seeds or clears each nest's guards by the
## player's distance, and fades burned nests' Bloom.
func tick() -> void:
	if Game.session == null:
		return
	if not _encounters_hooked and _hook_tries < 30:
		_hook_tries += 1
		_hook_encounters()
	var p: Node3D = _player()
	if p != null:
		for id: Variant in placements.keys():
			_seed(str(id), p.global_position)
	_sync_spots()
	_sync_clearings()


## Keeps a nest's guards while the player is within range: spawns the living slots (and those whose
## respawn time has come, from the pods, while it lives); past leave_range takes them away.
func _seed(id: String, ppos: Vector3) -> void:
	var def: NestDef = _def(id)
	var ai: Node = _ai()
	if def == null or ai == null or def.seed_count <= 0:
		return
	var pos: Vector3 = placements[id]["pos"]
	var d: float = Vector2(ppos.x - pos.x, ppos.z - pos.z).length()
	if d > def.seed_leave_range:
		_despawn_guards(id)
		return
	var st: Dictionary = state(id)
	var burned: bool = bool(st.get("burned", false))
	var have: Dictionary = _guards.get(id, {})
	_guards[id] = have
	if d > def.seed_range and have.is_empty():
		return
	# Burned: the guards out now stay out, nobody new comes.
	if burned or _burning.has(id):
		return
	var now: float = _now()
	var dead: Array = st.get("seeded_dead", [])
	var dead_slots: Dictionary = {}
	var keep: Array = []
	for dv: Variant in dead:
		var dd: Dictionary = dv
		if now - float(dd.get("at", now)) >= def.seed_respawn_hours * 60.0:
			continue
		keep.append(dd)
		dead_slots[int(dd.get("i", -1))] = true
	st["seeded_dead"] = keep
	var first: bool = have.is_empty()
	for i: int in def.seed_count:
		if dead_slots.has(i):
			continue
		var cur: Variant = have.get(i)
		if cur is Enemy and is_instance_valid(cur):
			continue
		# Back from the dead: out of a pod, awake (a respawn); else in its place, asleep or about.
		_spawn_guard(id, def, i, not first and _was_dead(i, dead))


static func _was_dead(i: int, dead: Array) -> bool:
	for dv: Variant in dead:
		if int((dv as Dictionary).get("i", -1)) == i:
			return true
	return false


func _spawn_guard(id: String, def: NestDef, i: int, from_pod: bool) -> Enemy:
	var ai: Node = _ai()
	var pos: Vector3 = placements[id]["pos"]
	var yaw: float = float(placements[id]["yaw"])
	var rng := RandomNumberGenerator.new()
	rng.seed = Ids.hash64("nest_guard:%d:%s:%d" % [Game.session.world_seed, id, i])
	var kind := StringName(str(Weighted.pick_key(def.seed_enemies, rng)))
	var sleeper: bool = i < def.seed_sleepers
	var ang: float = rng.randf() * TAU
	var r: float = rng.randf_range(def.seed_ring.x, lerpf(def.seed_ring.x, def.seed_ring.y, 0.45) if sleeper else def.seed_ring.y)
	var at := Vector3(pos.x + cos(ang) * r, 0.0, pos.z + sin(ang) * r)
	var pods: Array[int] = def.pods()
	if from_pod and not pods.is_empty():
		at = pos + (def.props[pods[i % pods.size()]]["offset"] as Vector3).rotated(Vector3.UP, yaw) + Vector3(rng.randf_range(-1, 1), 0, rng.randf_range(-1, 1))
		sleeper = false
	at.y = _height(at.x, at.z) + 0.3
	var opts: Dictionary = {"id": "nest:%s:g%d" % [id, i], "poi": "nest:" + id, "authored": true, "yaw": rng.randf() * TAU}
	if def.seed_tier != "":
		opts["tier"] = def.seed_tier
	if sleeper:
		opts["sleeper"] = "g%d" % i
		opts["pose"] = "lie" if rng.randf() < 0.7 else "crouch"
	var e: Enemy = ai.call(&"spawn", kind, at, opts)
	if e == null:
		return null
	(_guards[id] as Dictionary)[i] = e
	_slot_of[e.entity_id] = [id, i]
	return e


func _despawn_guards(id: String) -> void:
	var ai: Node = _ai()
	for e: Variant in (_guards.get(id, {}) as Dictionary).values():
		if e is Enemy and is_instance_valid(e):
			_slot_of.erase((e as Enemy).entity_id)
			if (e as Enemy).is_alive() and ai != null:
				ai.call(&"despawn", e)
	_guards.erase(id)


func _on_enemy_killed(entity_id: StringName, _enemy_id: StringName, _pos: Vector3, _killer: Dictionary) -> void:
	var slot: Variant = _slot_of.get(entity_id)
	if slot == null:
		return
	_slot_of.erase(entity_id)
	var id: String = slot[0]
	var i: int = slot[1]
	if Game.session == null or not Game.session.world.nests.has(id):
		return
	var st: Dictionary = state(id)
	var dead: Array = st.get("seeded_dead", [])
	dead.append({"i": i, "at": _now()})
	st["seeded_dead"] = dead
	(_guards.get(id, {}) as Dictionary).erase(i)


# --- Bloom ground ----------------------------------------------------------------------------------

## The Bloom strength a nest puts on the ground now: full while it lives, fading to nothing over its
## def's fade hours once burned.
func spot_strength(id: String) -> float:
	var def: NestDef = _def(id)
	if def == null:
		return 0.0
	var st: Dictionary = state(id)
	if not bool(st.get("burned", false)):
		return def.bloom_strength
	var t: float = (_now() - float(st.get("burned_at", _now()))) / (def.burn_fade_hours * 60.0)
	return def.bloom_strength * (1.0 - clampf(t, 0.0, 1.0))


## Every placed nest's spot ([{pos: Vector2, radius, strength}]), strengths quantised to 2 decimals.
func spots() -> Array:
	var out: Array = []
	var ids: Array = placements.keys()
	ids.sort()
	for id: Variant in ids:
		var s: float = snappedf(spot_strength(str(id)), 0.01)
		if s <= 0.0:
			continue
		var p: Vector3 = placements[id]["pos"]
		out.append({"pos": Vector2(p.x, p.z), "radius": _def(str(id)).bloom_radius, "strength": s})
	return out


## Sends the nests' spots to the Bloom field when they changed.
func _sync_spots() -> void:
	var list: Array = spots()
	var sig: String = ",".join(list.map(func(s: Dictionary) -> String: return "%.1f:%.1f:%.2f" % [s["pos"].x, s["pos"].y, s["strength"]]))
	if sig == _spots_sig:
		return
	var b: Node = _bloom()
	if b == null or not b.has_method(&"set_spot_source"):
		return
	_spots_sig = sig
	b.call(&"set_spot_source", SPOT_SOURCE, list)


# --- The mat and where it may stand (TD-258) -------------------------------------------------------

## How far (m, from its centre) a nest's props reach on the ground, plus MAT_MARGIN: its felted mat,
## kept clear of vegetation, and its footprint for the placement check.
static func mat_radius(def: NestDef) -> float:
	var r: float = 0.0
	for e: Dictionary in def.props:
		var pd: PropDef = Content.get_def(&"prop", e["prop"]) as PropDef
		var half: float = (maxf(pd.size.x, pd.size.z) * 0.5 if pd != null else 1.0) * float(e.get("scale", 1.0))
		var off: Vector3 = e["offset"]
		r = maxf(r, Vector2(off.x, off.z).length() + half)
	return r + MAT_MARGIN


## Every placed nest's mat ([{pos: Vector2, r}]): clearings in the vegetation.
func clearings() -> Array:
	var out: Array = []
	var ids: Array = placements.keys()
	ids.sort()
	for id: Variant in ids:
		var def: NestDef = _def(str(id))
		if def == null:
			continue
		var p: Vector3 = placements[id]["pos"]
		out.append({"pos": Vector2(p.x, p.z), "r": mat_radius(def)})
	return out


## Sends the mats to the vegetation (VegetationManager.set_clearings) when they changed; tried each
## pass, so a vegetation module set up after this one still gets them.
func _sync_clearings() -> void:
	var list: Array = clearings()
	var sig: String = ",".join(list.map(func(c: Dictionary) -> String: return "%.1f:%.1f:%.1f" % [c["pos"].x, c["pos"].y, c["r"]]))
	if sig == _clear_sig:
		return
	var veg: Object = world.get(&"vegetation") as Object if world != null else null
	if veg == null or not veg.has_method(&"set_clearings"):
		return
	_clear_sig = sig
	veg.call(&"set_clearings", SPOT_SOURCE, list)


## What is wrong with a nest standing at `at` with mat radius `r` in `region` of `wdef`: on a road or
## path (world or region), in a river or a lake, or on a POI / framework pad (its footprint and
## skirt). Geometry from the data alone (no composed terrain), so it is a check, not the composer's
## exact masks. Empty when it is clear.
static func placement_problems(at: Vector2, r: float, region: Dictionary, wdef: WorldDef) -> PackedStringArray:
	var out := PackedStringArray()
	if wdef != null:
		for rd: Dictionary in wdef.roads:
			var d: float = (rd["line"] as Polyline2).closest(at).x
			if d < float(rd.get("width", 6.0)) * 0.5 + float(rd.get("shoulder", 1.0)) + r:
				out.append("on road %s (%.0f m from its line)" % [rd.get("id", "?"), d])
		for rv: Dictionary in wdef.rivers:
			var d2: float = (rv["line"] as Polyline2).closest(at).x
			# (A river's width may vary along it: [w, w, ...]; take its widest.)
			var wv: Variant = rv.get("width", 16.0)
			var w: float = float(wv) if not wv is Array else float((wv as Array).max())
			if d2 < w * 0.5 + float(rv.get("bank", 4.0)) + r:
				out.append("in river %s (%.0f m from its line)" % [rv.get("id", "?"), d2])
		for lk: Dictionary in wdef.lakes:
			if _near_polygon(at, lk["polygon"], r + float(lk.get("shore", 0.0))):
				out.append("in lake %s" % lk.get("id", "?"))
	for fv: Variant in region.get("features", []):
		if not fv is Dictionary:
			continue
		var f: Dictionary = fv
		var fid: String = str(f.get("id", f.get("poi", f.get("framework", "?"))))
		match str(f.get("type", "")):
			"road", "path":
				var line := Polyline2.from_array(f.get("points", []))
				var d3: float = line.closest(at).x
				if d3 < float(f.get("width", 3.0)) * 0.5 + float(f.get("shoulder", 0.5)) + r:
					out.append("on %s %s (%.0f m from its line)" % [f["type"], fid, d3])
			"lake":
				var reach: float = r + float(f.get("shore", 0.0))
				if f.has("ellipse"):
					var e: Array = f["ellipse"]
					var loc: Vector2 = (at - Vector2(float(e[0]), float(e[1]))).rotated(-deg_to_rad(float(e[4]) if e.size() > 4 else 0.0))
					var ex: float = float(e[2]) + reach
					var ez: float = float(e[3]) + reach
					if (loc.x * loc.x) / (ex * ex) + (loc.y * loc.y) / (ez * ez) < 1.0:
						out.append("in lake %s" % fid)
				elif f.has("polygon"):
					var poly := PackedVector2Array()
					for pt: Variant in f["polygon"]:
						poly.append(Vector2(float(pt[0]), float(pt[1])))
					if _near_polygon(at, poly, reach):
						out.append("in lake %s" % fid)
			"poi", "framework":
				var size := Vector2(40, 40)
				if f.has("size"):
					size = Vector2(float(f["size"][0]), float(f["size"][1]))
				elif str(f["type"]) == "framework":
					var fw: FrameworkDef = Content.get_def(&"framework", StringName(str(f.get("framework", "")))) as FrameworkDef
					if fw != null:
						size = Vector2(fw.size)
				else:
					var pd: PoiDef = Content.get_def(&"poi", StringName(str(f.get("poi", "")))) as PoiDef
					if pd != null:
						size = Vector2(pd.footprint)
				# The composer's pad: a rect from `origin` along +x/+z turned by `rotation`, plus its skirt.
				var o: Vector2 = Vector2(float(f["origin"][0]), float(f["origin"][1]))
				var lp: Vector2 = (at - o).rotated(-deg_to_rad(float(f.get("rotation", 0.0))))
				var g: float = float(f.get("skirt", 10.0)) + r
				if lp.x > -g and lp.y > -g and lp.x < size.x + g and lp.y < size.y + g:
					out.append("on the pad of %s %s" % [f["type"], fid])
	return out


static func _near_polygon(p: Vector2, poly: PackedVector2Array, reach: float) -> bool:
	if poly.size() < 3:
		return false
	if Geometry2D.is_point_in_polygon(p, poly):
		return true
	for i: int in poly.size():
		var q: Vector2 = Geometry2D.get_closest_point_to_segment(p, poly[i], poly[(i + 1) % poly.size()])
		if q.distance_to(p) < reach:
			return true
	return false


## The placement check over every region nest feature of a world (validate.gd): an unknown def, or
## a nest standing on a road, in water or on a pad. Region-feature nests only (the encounter scatter
## places its own on open forest ground).
static func placement_warnings(world_path: String) -> PackedStringArray:
	var out := PackedStringArray()
	var wdef: WorldDef = WorldDef.load_from(world_path)
	if wdef == null:
		return out
	var rids: Array = wdef.regions.keys()
	rids.sort()
	for rid: Variant in rids:
		var region: Dictionary = wdef.region_data(str(rid))
		for f: Dictionary in region_features(region):
			var def: NestDef = Content.get_def(&"nest", f["def"]) as NestDef
			if def == null:
				out.append("%s: unknown nest def '%s'" % [f["id"], f["def"]])
				continue
			for prob: String in placement_problems(f["at"], mat_radius(def), region, wdef):
				out.append("%s: %s" % [f["id"], prob])
	return out
