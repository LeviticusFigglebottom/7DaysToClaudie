class_name ClimbMount
extends RefCounted
## Climbable structures (ADR-0057): a StructureDef that provides "climb" carries a
## PoiPieces.Ladder laid out by data/config/climbing.json (keyed by structure id), so Player climbs
## it exactly as it climbs a POI ladder (ADR-0051) and the climbing arms (ViewModelClimb) play.
## No movement code of its own.
##  * style "ladder" (the hunting stand): a fixed ladder inside the frame up to a hatch in the deck,
##    so its top landing is in front of the rails like a POI ladder's (walk into the hatch to climb
##    down). The piece's collision is always built here from `deck` (legs, the deck round its
##    hatch, rails), so the climb's clearances never depend on the generated model's colliders; the
##    visual is the generated model, or a procedural stand-in of the same layout.
##  * style "rope" (the climbing rope): set down at a ledge, it searches forward (the way the player
##    faced) for the edge and the ground below, then hangs a Ladder there (meta `climb_style`
##    "rope", so the arms take the rope hold) with the knotted rope drawn down to the ground. The
##    drop found is kept in the world flags (`climb:<piece id>`), so a reload hangs it the same
##    even before the terrain under it has loaded.

const CONFIG: StringName = &"climbing"
const TAG: String = "climb"
const SPAN_MODEL: String = "structures/climbing_rope_span"
## What a hanging rope looks for under its edge: terrain, structures, props.
const GROUND_MASK: int = (1 << 0) | (1 << 1) | (1 << 2)


static func handles(def: StructureDef) -> bool:
	return def != null and def.provides.has(TAG)


static func spec_for(id: StringName, cfg: Dictionary = {}) -> Dictionary:
	var c: Dictionary = cfg if not cfg.is_empty() else Content.config(CONFIG)
	var s: Variant = c.get(String(id), {})
	return s if s is Dictionary else {}


## Problems with the climbing data (validate.gd, tests): every structure that provides "climb" has
## a spec of a known style with what that style needs.
static func problems(content: Node) -> PackedStringArray:
	var out: PackedStringArray = []
	var cfg: Dictionary = content.call(&"config", CONFIG)
	for d: Variant in content.call(&"all", &"structure"):
		var def := d as StructureDef
		if not handles(def):
			continue
		var s: Dictionary = spec_for(def.id, cfg)
		match str(s.get("style", "")):
			"ladder":
				for k: String in ["foot", "face", "landing", "bottom"]:
					if not (s.get(k, null) is Array and (s[k] as Array).size() == 3):
						out.append("climbing: %s.%s must be [x, y, z]" % [def.id, k])
				if float(s.get("height", 0.0)) <= 0.5:
					out.append("climbing: %s.height must be over 0.5 m" % def.id)
			"rope":
				for k: String in ["step", "overhang_max", "min_drop", "max_drop"]:
					if float(s.get(k, 0.0)) <= 0.0:
						out.append("climbing: %s.%s must be positive" % [def.id, k])
				if float(s.get("max_drop", 0.0)) <= float(s.get("min_drop", 0.0)):
					out.append("climbing: %s.max_drop must exceed min_drop" % def.id)
			_:
				out.append("climbing: structure '%s' provides climb but has no ladder/rope spec in data/config/climbing.json" % def.id)
	return out


static func _v3(a: Variant, dflt: Vector3 = Vector3.ZERO) -> Vector3:
	if a is Array and (a as Array).size() == 3:
		return Vector3(float(a[0]), float(a[1]), float(a[2]))
	return dflt


# --- Building the piece --------------------------------------------------------------------------

## StructurePiece._build_visual for a climbable piece: its model (or a stand-in), and its ladder.
static func build(piece: StructurePiece, mesh: MeshInstance3D) -> void:
	var s: Dictionary = spec_for(piece.def.id)
	var rope: bool = str(s.get("style", "")) == "rope"
	piece.add_child(mesh)
	if ModelLibrary.has_model(piece.def.model):
		mesh.mesh = ModelLibrary.mesh(piece.def.model)
	elif rope:
		piece.add_child(_rope_anchor_stand_in())
	else:
		piece.add_child(_stand_stand_in(s))
	if rope:
		var hanger := RopeHanger.new()
		hanger.name = "RopeHanger"
		hanger.piece = piece
		hanger.spec = s
		piece.add_child(hanger)
	else:
		piece.add_child(make_ladder(s))


## StructurePiece._build_collision for a climbable piece.
static func build_collision(piece: StructurePiece) -> void:
	var s: Dictionary = spec_for(piece.def.id)
	if str(s.get("style", "")) == "rope":
		_box_shape(piece, Vector3(0.3, 0.25, 0.3), Vector3(0, 0.125, 0))
		return
	for b: Array in stand_boxes(s):
		_box_shape(piece, b[0], b[1])


## [size, centre] boxes (piece-local) of a stand: four legs, the deck round its hatch, rails.
static func stand_boxes(s: Dictionary) -> Array:
	var d: Dictionary = s.get("deck", {})
	var half: float = float(d.get("half", 1.2))
	var top: float = float(d.get("top", s.get("height", 3.0)))
	var th: float = float(d.get("thick", 0.14))
	var h: Array = d.get("hatch", [-0.45, 0.45, 0.25, 1.2])
	var rail: float = float(d.get("rail", 1.0))
	var leg: float = float(d.get("leg", half - 0.14))
	var x0: float = float(h[0])
	var x1: float = float(h[1])
	var z0: float = float(h[2])
	var z1: float = float(h[3])
	var yc: float = top - th * 0.5
	var out: Array = []
	for sx: float in [-1.0, 1.0]:
		for sz: float in [-1.0, 1.0]:
			out.append([Vector3(0.16, top - th, 0.16), Vector3(sx * leg, (top - th) * 0.5, sz * leg)])
	# The deck: behind the hatch, and either side of it.
	out.append([Vector3(half * 2.0, th, z0 + half), Vector3(0, yc, (z0 - half) * 0.5)])
	out.append([Vector3(x0 + half, th, half - z0), Vector3((x0 - half) * 0.5, yc, (z0 + half) * 0.5)])
	out.append([Vector3(half - x1, th, half - z0), Vector3((x1 + half) * 0.5, yc, (z0 + half) * 0.5)])
	# Rails round the deck (the front one above the hatch too: the climber comes up inside it).
	var ry: float = top + rail * 0.5
	out.append([Vector3(half * 2.0, rail, 0.06), Vector3(0, ry, -half + 0.03)])
	out.append([Vector3(half * 2.0, rail, 0.06), Vector3(0, ry, half - 0.03)])
	out.append([Vector3(0.06, rail, half * 2.0), Vector3(-half + 0.03, ry, 0)])
	out.append([Vector3(0.06, rail, half * 2.0), Vector3(half - 0.03, ry, 0)])
	var _unused: float = z1
	return out


static func _box_shape(parent: Node3D, size: Vector3, centre: Vector3) -> void:
	var cs := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = size
	cs.shape = box
	cs.position = centre
	parent.add_child(cs)


## The stand's ladder: a PoiPieces.Ladder at `foot`, turned so its +Z faces the climber, with its
## ends piece-local. No shape: it is climbed by walking into it (Player, ADR-0051).
static func make_ladder(s: Dictionary) -> PoiPieces.Ladder:
	var foot: Vector3 = _v3(s.get("foot", []))
	var face: Vector3 = _v3(s.get("face", []), Vector3.BACK)
	face.y = 0.0
	face = face.normalized() if face.length() > 0.01 else Vector3.BACK
	var height: float = float(s.get("height", 3.0))
	var lad := PoiPieces.Ladder.new()
	lad.name = "Ladder"
	lad.position = foot
	lad.basis = Basis.looking_at(-face, Vector3.UP)
	lad.top_local = _v3(s.get("landing", []), foot + Vector3.UP * height - face * 1.0)
	lad.bottom_local = _v3(s.get("bottom", []), foot + face * 0.6)
	lad.height = height
	return lad


# --- Procedural stand-ins (no `make assets`) -------------------------------------------------------

static func _mat(c: Color) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	m.roughness = 0.95
	return m


static func _stand_stand_in(s: Dictionary) -> Node3D:
	var root := Node3D.new()
	root.name = "StandIn"
	var wood: StandardMaterial3D = _mat(Color(0.42, 0.31, 0.2))
	for b: Array in stand_boxes(s):
		var mi := MeshInstance3D.new()
		var bm := BoxMesh.new()
		bm.size = b[0]
		bm.material = wood
		mi.mesh = bm
		mi.position = b[1]
		root.add_child(mi)
	# The ladder: two rails 0.09-0.16 m in front of its foot, rungs every 0.3 m.
	var foot: Vector3 = _v3(s.get("foot", []))
	var face: Vector3 = _v3(s.get("face", []), Vector3.BACK).normalized()
	var height: float = float(s.get("height", 3.0))
	var side: Vector3 = face.cross(Vector3.UP).normalized()
	var lb := Basis.looking_at(-face, Vector3.UP)
	var pole: StandardMaterial3D = _mat(Color(0.5, 0.38, 0.25))
	for sx: float in [-0.23, 0.23]:
		var r := MeshInstance3D.new()
		var rb := BoxMesh.new()
		rb.size = Vector3(0.05, height, 0.07)
		rb.material = pole
		r.mesh = rb
		r.transform = Transform3D(lb, foot + side * sx + face * 0.125 + Vector3.UP * height * 0.5)
		root.add_child(r)
	var y: float = 0.3
	while y < height - 0.1:
		var g := MeshInstance3D.new()
		var cm := CylinderMesh.new()
		cm.top_radius = 0.02
		cm.bottom_radius = 0.02
		cm.height = 0.46
		cm.radial_segments = 8
		cm.material = pole
		g.mesh = cm
		g.transform = Transform3D(Basis(face, PI * 0.5) * lb, foot + face * 0.125 + Vector3.UP * y)
		root.add_child(g)
		y += 0.3
	return root


static func _rope_anchor_stand_in() -> Node3D:
	var root := Node3D.new()
	root.name = "StandIn"
	var stake := MeshInstance3D.new()
	var cm := CylinderMesh.new()
	cm.top_radius = 0.03
	cm.bottom_radius = 0.02
	cm.height = 0.35
	cm.material = _mat(Color(0.45, 0.34, 0.22))
	stake.mesh = cm
	stake.position = Vector3(0, 0.12, 0.12)
	root.add_child(stake)
	return root


static func rope_material() -> Material:
	var path: String = "res://assets/generated/materials/item_rope.tres"
	if ResourceLoader.exists(path):
		return load(path) as Material
	return _mat(Color(0.55, 0.46, 0.32))


## The hanging rope from `a` to `b` (piece-local): the generated knotted span model repeated along
## it (each 1 m along its +Y), or a plain cylinder.
static func rope_visual(a: Vector3, b: Vector3) -> Node3D:
	var root := Node3D.new()
	root.name = "Rope"
	var d: Vector3 = b - a
	var length: float = d.length()
	if length < 0.01:
		return root
	var up: Vector3 = d / length
	var x: Vector3 = up.cross(Vector3.BACK if absf(up.dot(Vector3.BACK)) < 0.95 else Vector3.RIGHT).normalized()
	var basis := Basis(x, up, x.cross(up)).orthonormalized()
	var span: Mesh = ModelLibrary.generated_mesh(SPAN_MODEL)
	if span != null:
		var n: int = int(ceil(length))
		for i: int in n:
			var seg := MeshInstance3D.new()
			seg.mesh = span
			var l: float = minf(1.0, length - float(i))
			seg.transform = Transform3D(basis.scaled_local(Vector3(1.0, l, 1.0)), a + up * float(i))
			root.add_child(seg)
		return root
	var mi := MeshInstance3D.new()
	var cyl := CylinderMesh.new()
	cyl.top_radius = 0.012
	cyl.bottom_radius = 0.012
	cyl.height = length
	cyl.radial_segments = 6
	cyl.material = rope_material()
	mi.mesh = cyl
	mi.transform = Transform3D(basis, a + d * 0.5)
	root.add_child(mi)
	return root


# --- Ropes ------------------------------------------------------------------------------------------

## Where a rope set down at `anchor` (world) facing `fwd` hangs: {d: metres out from the anchor,
## ground: world y of what is below} or {} when there is no ledge within reach. `probe` answers a
## downward ray (from, to) -> hit position or null (tests pass their own).
static func find_drop(anchor: Vector3, fwd: Vector3, s: Dictionary, probe: Callable) -> Dictionary:
	var step: float = maxf(0.02, float(s.get("step", 0.1)))
	var reach: float = float(s.get("overhang_max", 1.4))
	var min_drop: float = float(s.get("min_drop", 1.5))
	var max_drop: float = float(s.get("max_drop", 14.0))
	fwd.y = 0.0
	fwd = fwd.normalized()
	var d: float = step
	while d <= reach + 0.001:
		var p: Vector3 = anchor + fwd * d
		var hit: Variant = probe.call(p + Vector3.UP * 0.3, p + Vector3.DOWN * (max_drop + 0.5))
		var gy: float = (hit as Vector3).y if hit is Vector3 else -INF
		if anchor.y - gy >= min_drop:
			if gy == -INF:
				return {}  # nothing below within max_drop: too high to hang
			return {"d": d + float(s.get("lip", 0.06)), "ground": gy}
		d += step
	return {}


## Hangs a rope piece's Ladder and visual from a drop found by find_drop (`d` out along the piece's
## -Z, `ground` world y). Returns the Ladder.
static func hang_rope(piece: Node3D, s: Dictionary, drop: Dictionary) -> PoiPieces.Ladder:
	var d: float = float(drop["d"])
	var gy_local: float = piece.to_local(Vector3(piece.global_position.x, float(drop["ground"]), piece.global_position.z)).y
	var face := Vector3.FORWARD  # piece-local: away from the anchor, toward the climber
	var rope_off: float = float(s.get("rope_off", 0.12))
	var rope_at := Vector3(0, gy_local, -d)
	var lad := PoiPieces.Ladder.new()
	lad.name = "Ladder"
	lad.position = rope_at - face * rope_off
	lad.basis = Basis.looking_at(-face, Vector3.UP)
	lad.top_local = Vector3(0, 0, float(s.get("landing_back", 0.35)))
	lad.bottom_local = lad.position + face * 0.6
	lad.height = -gy_local
	lad.set_meta(&"climb_style", "rope")
	piece.add_child(lad)
	# Over the lip from the stake, then straight down to a hand's breadth off the ground.
	piece.add_child(rope_visual(Vector3(0, 0.06, 0.05), Vector3(0, 0.03, -d)))
	var down: Node3D = rope_visual(Vector3(0, 0.03, -d), Vector3(0, gy_local + 0.15, -d))
	down.name = "RopeDown"
	piece.add_child(down)
	return lad


## Finds the drop over the next physics frames (the piece's transform is set after it enters the
## tree, and the terrain under it may still be loading) and hangs the rope; remembers the drop in
## the world flags.
class RopeHanger:
	extends Node
	var piece: StructurePiece
	var spec: Dictionary = {}
	var ladder: PoiPieces.Ladder = null
	var _frames: int = 0

	func _ready() -> void:
		set_physics_process(true)

	func _flag() -> String:
		return "climb:%s" % piece.piece_id

	func _physics_process(_delta: float) -> void:
		_frames += 1
		if piece == null or not piece.is_inside_tree() or _frames < 2:
			return
		var flags: Dictionary = Game.session.world.flags if Game.session != null else {}
		var drop: Dictionary = {}
		var saved: Variant = flags.get(_flag(), null)
		if saved is Array and (saved as Array).size() == 2:
			drop = {"d": float(saved[0]), "ground": piece.global_position.y - float(saved[1])}
		else:
			var space: PhysicsDirectSpaceState3D = piece.get_world_3d().direct_space_state
			var rid: RID = piece.get_rid()
			var probe := func(from: Vector3, to: Vector3) -> Variant:
				var q := PhysicsRayQueryParameters3D.create(from, to, GROUND_MASK, [rid])
				var hit: Dictionary = space.intersect_ray(q)
				return hit["position"] if not hit.is_empty() else null
			drop = ClimbMount.find_drop(piece.global_position, -piece.global_basis.z, spec, probe)
			if not drop.is_empty() and Game.session != null:
				flags[_flag()] = [float(drop["d"]), piece.global_position.y - float(drop["ground"])]
		if drop.is_empty():
			if _frames > int(spec.get("retry_frames", 240)):
				set_physics_process(false)  # no ledge: it stays a staked coil
			return
		ladder = ClimbMount.hang_rope(piece, spec, drop)
		set_physics_process(false)
