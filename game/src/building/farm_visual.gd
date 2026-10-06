class_name FarmVisual
extends Node3D
## What a garden bed or rain catcher shows (ADR-0049): a bed's plants, stage by stage, wilting and
## dead, and how wet its soil is; a catcher's water level. Generated models when they exist
## (crops/<crop>_s<n>, crops/dead_plant, the catcher's `water` part scaled to its level), stand-ins
## built from primitives otherwise, so it all works before `make assets`.
## StructurePiece makes one for every farm piece; FarmManager calls refresh() when its state changes.

const DEAD_MODEL: String = "crops/dead_plant"
## Soil surface below the top of a bed's size (the generated bed's soil sits just under its rim).
const SOIL_DROP: float = 0.03

var piece: StructurePiece
var _plots: Array[Node3D] = []
var _plot_keys: PackedStringArray = []
var _soil_mat: StandardMaterial3D = null
var _water: Node3D = null
var _water_full: float = 1.0

static var _mats: Dictionary = {}


static func handles(def: StructureDef) -> bool:
	return Farming.is_farm(def)


## Builds the piece's base visual into `base` (added to the piece) and attaches the farm visual.
static func attach(p: StructurePiece, base: MeshInstance3D) -> FarmVisual:
	var v := FarmVisual.new()
	v.name = "Farm"
	v.piece = p
	p.add_child(base)
	p.add_child(v)
	if Farming.catcher_capacity(p.def) > 0.0:
		v._build_catcher(base)
	else:
		v._build_bed(base)
	v.refresh()
	return v


## Where plot `i` of `n` sits on a bed of `size`: in a row along its length, on the soil.
static func plot_position(size: Vector3, i: int, n: int) -> Vector3:
	var x: float = (float(i) + 0.5) / float(maxi(n, 1)) - 0.5
	return Vector3(x * size.x * 0.88, size.y - SOIL_DROP, 0.0)


func _build_bed(base: MeshInstance3D) -> void:
	var def: StructureDef = piece.def
	if ModelLibrary.has_model(def.model):
		base.mesh = ModelLibrary.mesh(def.model)
	else:
		# Stand-in: a timber box and a soil slab whose colour darkens when it is wet.
		base.mesh = _box(Vector3(def.size.x, def.size.y - 0.04, def.size.z), _mat("bed_wood", Color(0.42, 0.31, 0.2)))
		base.position = Vector3(0, (def.size.y - 0.04) * 0.5, 0)
		var soil := MeshInstance3D.new()
		_soil_mat = StandardMaterial3D.new()
		_soil_mat.roughness = 0.95
		soil.mesh = _box(Vector3(def.size.x - 0.12, 0.05, def.size.z - 0.12), _soil_mat)
		soil.position = Vector3(0, def.size.y - SOIL_DROP - 0.025, 0)
		add_child(soil)
	var n: int = Farming.plots_of(def)
	for i: int in n:
		var holder := Node3D.new()
		holder.name = "Plot%d" % i
		holder.position = plot_position(def.size, i, n)
		# Each plot turned a little so a row of the same crop doesn't read as copies.
		holder.rotation.y = float(i) * 2.1
		add_child(holder)
		_plots.append(holder)
		_plot_keys.append("")


func _build_catcher(base: MeshInstance3D) -> void:
	var def: StructureDef = piece.def
	var split: Dictionary = ModelLibrary.parts(def.model, PackedStringArray(["water"]))
	if not split.is_empty() and split.get("base") != null:
		base.mesh = split["base"]
		for nm: String in (split["parts"] as Dictionary).keys():
			var part: Dictionary = split["parts"][nm]
			var mi := MeshInstance3D.new()
			mi.name = "Water"
			mi.mesh = part["mesh"]
			# The part's origin is the inside floor of the trough; it is modelled full and scaled
			# down to the level.
			_water = Node3D.new()
			_water.transform = part["xf"]
			_water.add_child(mi)
			add_child(_water)
			break
		return
	# Stand-in: a squat log barrel under a funnel, and a water disc that rises inside it.
	var wood: StandardMaterial3D = _mat("catcher_wood", Color(0.4, 0.3, 0.2))
	var barrel := CylinderMesh.new()
	barrel.top_radius = 0.38
	barrel.bottom_radius = 0.4
	barrel.height = 0.8
	barrel.material = wood
	base.mesh = barrel
	base.position = Vector3(0, 0.4, 0)
	var funnel := MeshInstance3D.new()
	var cone := CylinderMesh.new()
	cone.top_radius = def.size.x * 0.5
	cone.bottom_radius = 0.12
	cone.height = 0.5
	cone.material = _mat("catcher_cloth", Color(0.7, 0.66, 0.55))
	funnel.mesh = cone
	funnel.position = Vector3(0, def.size.y - 0.25, 0)
	add_child(funnel)
	for k: int in 3:
		var leg := MeshInstance3D.new()
		var cyl := CylinderMesh.new()
		cyl.top_radius = 0.025
		cyl.bottom_radius = 0.03
		cyl.height = def.size.y
		cyl.material = wood
		leg.mesh = cyl
		var a: float = TAU * float(k) / 3.0
		leg.position = Vector3(cos(a) * def.size.x * 0.45, def.size.y * 0.5, sin(a) * def.size.x * 0.45)
		add_child(leg)
	_water = Node3D.new()
	_water.position = Vector3(0, 0.08, 0)
	add_child(_water)
	var disc := MeshInstance3D.new()
	var c := CylinderMesh.new()
	c.top_radius = 0.36
	c.bottom_radius = 0.36
	c.height = 0.7
	c.material = _mat("catcher_water", Color(0.22, 0.27, 0.2))
	disc.mesh = c
	disc.position = Vector3(0, 0.35, 0)
	_water.add_child(disc)
	_water_full = 1.0


## Shows the piece's current state (cheap when nothing changed).
func refresh() -> void:
	if piece == null:
		return
	var st: Dictionary = FarmManager.peek(piece)
	if Farming.catcher_capacity(piece.def) > 0.0:
		var f: float = clampf(float(st.get("water", 0.0)) / Farming.catcher_capacity(piece.def), 0.0, 1.0)
		if _water != null:
			_water.visible = f > 0.01
			_water.scale = Vector3(1.0, maxf(0.02, f) * _water_full, 1.0)
		return
	if _soil_mat != null:
		var w: float = clampf(float(st.get("water", 0.0)) / Farming.soil_capacity(), 0.0, 1.0)
		_soil_mat.albedo_color = Color(0.36, 0.27, 0.19).lerp(Color(0.16, 0.11, 0.08), w)
	var plots: Array = st.get("plots", [])
	for i: int in _plots.size():
		var plot: Dictionary = plots[i] if i < plots.size() else {}
		var key: String = Farming.signature({"plots": [plot]})
		if key == _plot_keys[i]:
			continue
		_plot_keys[i] = key
		_show_plot(_plots[i], plot)


func _show_plot(holder: Node3D, plot: Dictionary) -> void:
	for c: Node in holder.get_children():
		holder.remove_child(c)
		c.free()
	if Farming.is_empty_plot(plot):
		return
	var crop: CropDef = Farming.crop(plot["crop"])
	if crop == null:
		return
	var dead: bool = Farming.is_dead(plot)
	var stage: int = Farming.stage_of(plot)
	var model: String = DEAD_MODEL if dead else crop.stage_model(stage)
	var m: Mesh = ModelLibrary.generated_mesh(model) if ModelLibrary.has_model(model) else null
	var plant := Node3D.new()
	holder.add_child(plant)
	if m != null:
		var mi := MeshInstance3D.new()
		mi.mesh = m
		plant.add_child(mi)
	else:
		_stand_in(plant, crop, stage, dead)
	if Farming.is_wilted(plot):
		# Wilting: it sags and leans.
		plant.scale = Vector3(1.0, 0.8, 1.0)
		plant.rotation = Vector3(deg_to_rad(14.0), 0.0, 0.0)


## A plant from primitives: a stem, a leafy crown that grows with the stage, the produce when ripe.
func _stand_in(plant: Node3D, crop: CropDef, stage: int, dead: bool) -> void:
	var t: float = float(stage + 1) / float(crop.stages)
	var h: float = crop.height * lerpf(0.25, 1.0, t)
	var leaf: Color = Color(0.42, 0.33, 0.2) if dead else crop.leaf_color
	var stem := MeshInstance3D.new()
	var cyl := CylinderMesh.new()
	cyl.top_radius = 0.008
	cyl.bottom_radius = 0.014
	cyl.height = h
	cyl.radial_segments = 6
	cyl.rings = 1
	cyl.material = _mat("leaf_%s" % leaf.to_html(false), leaf)
	stem.mesh = cyl
	stem.position = Vector3(0, h * 0.5, 0)
	plant.add_child(stem)
	var crown := MeshInstance3D.new()
	var s := SphereMesh.new()
	var r: float = clampf(crop.height * 0.35, 0.08, 0.3) * lerpf(0.35, 1.0, t)
	s.radius = r
	s.height = r * (2.4 if crop.height > 1.0 else 1.3)
	s.radial_segments = 8
	s.rings = 4
	s.material = cyl.material
	crown.mesh = s
	crown.position = Vector3(0, h - s.height * 0.4, 0)
	plant.add_child(crown)
	if dead or stage < crop.stages - 1:
		return
	var fruit_mat: StandardMaterial3D = _mat("fruit_%s" % crop.color.to_html(false), crop.color)
	for k: int in 4:
		var f := MeshInstance3D.new()
		var fs := SphereMesh.new()
		fs.radius = 0.035
		fs.height = 0.07
		fs.radial_segments = 6
		fs.rings = 3
		fs.material = fruit_mat
		f.mesh = fs
		var a: float = TAU * float(k) / 4.0 + 0.4
		f.position = crown.position + Vector3(cos(a) * r * 0.85, -r * 0.2, sin(a) * r * 0.85)
		plant.add_child(f)


static func _mat(key: String, c: Color) -> StandardMaterial3D:
	var m: StandardMaterial3D = _mats.get(key)
	if m == null:
		m = StandardMaterial3D.new()
		m.albedo_color = c
		m.roughness = 0.9
		_mats[key] = m
	return m


static func _box(size: Vector3, mat: Material) -> BoxMesh:
	var b := BoxMesh.new()
	b.size = size
	b.material = mat
	return b
