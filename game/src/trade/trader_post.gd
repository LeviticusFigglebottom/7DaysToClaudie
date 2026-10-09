class_name TraderPost
extends Node3D
## A Remand Program trader post in the world (ADR-0039): its set dressing (barriers, towers, the
## sign, floodlights), the trade counter and the contracts board the player uses, and the
## quartermaster behind the counter. Pure presentation rebuilt on every load: what it sells and
## what the board offers live in TraderManager / Contracts. Every prop falls back to a box of its
## size, and the quartermaster to a stand-in, before `make assets`.

## Turn rate (radians/s) and range of the quartermaster's attention.
const LOOK_RANGE: float = 9.0
const TURN_SPEED: float = 2.0

var manager: Node
var post_id: String = ""
var def: TraderDef
## Whether to raise the def's set dressing (its `props`): false for a post built into its building
## (TraderDef.in_poi), whose walls, towers and floodlights are the POI's.
var dress: bool = true
var counter_body: StaticBody3D
var board_body: StaticBody3D
var quartermaster: EnemyVisual
var _qm_yaw: float = 0.0
var _talk_t: float = 0.0
var _world: Node


## Raises the dressing on the ground under each piece.
func build(w: Node) -> void:
	_world = w
	if dress:
		for v: Variant in def.props:
			_prop(v as Dictionary)
	if not def.counter.is_empty():
		counter_body = _prop(def.counter, Station.new(self, "shop", "Trade with the quartermaster"))
	if not def.board.is_empty():
		board_body = _prop(def.board, Station.new(self, "board", "Read the contracts board"))
	_raise_quartermaster()


func _ground(local_xz: Vector2, dy: float) -> Vector3:
	var g: Vector3 = global_transform * Vector3(local_xz.x, 0.0, local_xz.y)
	if _world != null and _world.has_method(&"height_at"):
		g.y = float(_world.call(&"height_at", g.x, g.z))
	return g + Vector3.UP * dy


func _prop(d: Dictionary, handler: Object = null) -> StaticBody3D:
	var pid := StringName(str(d.get("prop", "")))
	var pd: PropDef = Content.get_def(&"prop", pid) as PropDef
	var model: String = pd.model_for(str(d.get("variant", "worn"))) if pd != null else "props/%s" % pid
	var off: Array = d.get("offset", [0.0, 0.0])
	var body := StaticBody3D.new()
	body.name = "%s_%d" % [pid, get_child_count()]
	add_child(body)
	body.global_transform = Transform3D(global_transform.basis * Basis(Vector3.UP, deg_to_rad(float(d.get("rot", 0.0)))),
		_ground(Vector2(float(off[0]), float(off[off.size() - 1])), float(d.get("y", 0.0))))
	var mi := MeshInstance3D.new()
	mi.mesh = ModelLibrary.mesh(model, "box")
	body.add_child(mi)
	var aabb: AABB = mi.mesh.get_aabb() if mi.mesh != null else AABB(Vector3(-0.5, 0, -0.5), Vector3.ONE)
	if pd != null and aabb.size.length() < 0.01:
		aabb = AABB(Vector3(-pd.size.x * 0.5, 0.0, -pd.size.z * 0.5), pd.size)
	# The model's own colliders when it ships them: the counter's leave the quartermaster's standing
	# space open, where one box of its size would wall him in. A box of its bounds otherwise.
	var own: Array = ModelLibrary.shapes(model)
	if pd != null and str(pd.get(&"collision")) == "none":
		pass
	elif not own.is_empty():
		for e: Variant in own:
			var cs := CollisionShape3D.new()
			cs.shape = (e as Dictionary)["shape"]
			cs.transform = (e as Dictionary)["transform"]
			body.add_child(cs)
	else:
		var shape := CollisionShape3D.new()
		var box := BoxShape3D.new()
		box.size = aabb.size.max(Vector3.ONE * 0.05)
		shape.shape = box
		shape.position = aabb.get_center()
		body.add_child(shape)
	if handler != null:
		body.set_meta(&"interactable", handler)
	return body


func _raise_quartermaster() -> void:
	var q: Dictionary = def.quartermaster
	if q.is_empty():
		return
	var off: Array = q.get("offset", [0.0, 0.0, 0.0])
	var at: Vector3 = _ground(Vector2(float(off[0]), float(off[2])), float(off[1]))
	var holder := Node3D.new()
	holder.name = "Quartermaster"
	add_child(holder)
	holder.global_position = at
	_qm_yaw = rotation.y + deg_to_rad(float(q.get("yaw", 0.0)))
	holder.global_rotation = Vector3(0.0, _qm_yaw, 0.0)
	quartermaster = EnemyVisual.new()
	holder.add_child(quartermaster)
	quartermaster.build(str(q.get("model", "characters/waystation_quartermaster")), 1.0)
	quartermaster.play(&"idle", 1.0, 0.25, [&"idle_b"])


func _process(delta: float) -> void:
	if quartermaster == null or _world == null:
		return
	var pl: Node3D = _world.get(&"player") as Node3D
	if pl == null:
		return
	var holder: Node3D = quartermaster.get_parent() as Node3D
	var to: Vector3 = pl.global_position - holder.global_position
	var near: bool = Vector2(to.x, to.z).length() < LOOK_RANGE
	# He turns to whoever comes to the hatch, within reason, and leans on the counter to talk.
	var want: float = atan2(to.x, to.z) if near else rotation.y + deg_to_rad(float(def.quartermaster.get("yaw", 0.0)))
	var base: float = rotation.y + deg_to_rad(float(def.quartermaster.get("yaw", 0.0)))
	want = base + clampf(wrapf(want - base, -PI, PI), -0.7, 0.7)
	holder.global_rotation.y = lerp_angle(holder.global_rotation.y, want, minf(1.0, delta * TURN_SPEED))
	_talk_t -= delta
	if _talk_t <= 0.0:
		_talk_t = randf_range(5.0, 9.0)
		quartermaster.play(&"idle_b" if near else &"idle", 1.0, 0.4, [&"idle"])


## Opens the trade screen from the counter or the board.
func use(tab: String) -> void:
	if manager != null:
		manager.call(&"open_screen", post_id, tab)
		if quartermaster != null and tab == "shop":
			quartermaster.play_once(&"talk", 1.0, [&"idle_b"])


## What the interaction ray finds on the counter and the board (PlayerInteraction duck type).
class Station:
	extends RefCounted
	var post: TraderPost
	var tab: String
	var text: String

	func _init(p: TraderPost, t: String, label: String) -> void:
		post = p
		tab = t
		text = label

	func interact_text(_player: Node) -> String:
		return text

	func interact(_player: Node) -> void:
		post.use(tab)
