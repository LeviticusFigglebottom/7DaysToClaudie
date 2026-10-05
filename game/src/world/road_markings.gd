class_name RoadMarkings
extends Node3D
## Painted lines on two-lane asphalt roads (RegionTerrain.roads): a dashed yellow centre line and
## solid white edge lines, as decals laid along the composed road profile so they hug the graded
## surface. Gravel tracks, narrow lanes and bridge spans (the deck carries its own) get none. Each
## decal fades out with distance, so only the stretch around the player costs anything to draw.
## Without generated textures (before `make assets`) roads stay unmarked.

const MIN_WIDTH: float = 6.0
const DASH: float = 3.0
const DASH_GAP: float = 9.0
const EDGE_SEGMENT: float = 6.0
## Paint width; the texture's line fills the middle 70 % of its height (road_markings.py).
const LINE_WIDTH: float = 0.12
const EDGE_INSET: float = 0.4
const FADE_BEGIN: float = 55.0
const FADE_LENGTH: float = 25.0
const YELLOW := Color(0.95, 0.72, 0.2)
const WHITE := Color(0.9, 0.9, 0.86)
const TEXTURES: PackedStringArray = ["decal_road_line_a", "decal_road_line_b"]

var world: Node
## Decals placed (diagnostics, tests).
var count: int = 0
var _albedo: Array[Texture2D] = []
var _normal: Array[Texture2D] = []
## Bridge chords [{"from": Vector3, "to": Vector3, "width": float}]: no paint on the decks.
var _spans: Array[Dictionary] = []
## Quantised decal centres: the same road is recorded by every region it crosses.
var _placed: Dictionary = {}


func setup_world(w: Node) -> void:
	world = w
	for id: String in TEXTURES:
		var path: String = "res://assets/generated/textures/%s_albedo.png" % id
		if not ResourceLoader.exists(path):
			continue
		_albedo.append(load(path) as Texture2D)
		var npath: String = path.replace("_albedo.png", "_normal.png")
		_normal.append(load(npath) as Texture2D if ResourceLoader.exists(npath) else null)
	if _albedo.is_empty():
		return
	var terrain: TerrainManager = w.terrain
	for rid: String in terrain.regions:
		var rt: RegionTerrain = terrain.regions[rid]
		for b: Dictionary in rt.bridges:
			var f: Array = b["from"]
			var t: Array = b["to"]
			_spans.append({"from": Vector3(float(f[0]), 0.0, float(f[2])), "to": Vector3(float(t[0]), 0.0, float(t[2])),
				"width": float(b.get("width", 9.0))})
	for rid: String in terrain.regions:
		var rt: RegionTerrain = terrain.regions[rid]
		for r: Dictionary in rt.roads:
			if paints(r):
				_mark(r)


## Whether a road gets lines: two-lane asphalt, unless it opts out with "markings": false (lots,
## aprons, forecourts).
static func paints(road: Dictionary) -> bool:
	return str(road.get("surface", "")) == "asphalt" and float(road.get("width", 0.0)) >= MIN_WIDTH and bool(road.get("markings", true))


## Lays the lines of one road: dashes at a phase taken from its id (so towns' streets don't all
## start a dash at their junction), edge lines as short straight segments along the curve.
func _mark(road: Dictionary) -> void:
	var line: Array[Vector3] = []
	for p: Array in road["points"]:
		line.append(Vector3(float(p[0]), float(p[1]), float(p[2])))
	if line.size() < 2:
		return
	var cum := PackedFloat32Array([0.0])
	for i: int in range(1, line.size()):
		cum.append(cum[i - 1] + Vector2(line[i].x - line[i - 1].x, line[i].z - line[i - 1].z).length())
	var total: float = cum[cum.size() - 1]
	var s: float = float(absi(hash(str(road.get("id", "")))) % 1200) / 100.0
	while s + DASH <= total:
		_decal(_at(line, cum, s), _at(line, cum, s + DASH), 0.0, YELLOW)
		s += DASH + DASH_GAP
	var off: float = float(road["width"]) * 0.5 - EDGE_INSET
	s = 0.0
	while s < total - 0.5:
		var e: float = minf(s + EDGE_SEGMENT, total)
		var a: Vector3 = _at(line, cum, s)
		var b: Vector3 = _at(line, cum, e)
		_decal(a, b, -off, WHITE)
		_decal(a, b, off, WHITE)
		s = e


static func _at(line: Array[Vector3], cum: PackedFloat32Array, s: float) -> Vector3:
	var i: int = clampi(cum.bsearch(s) - 1, 0, line.size() - 2)
	var seg: float = cum[i + 1] - cum[i]
	return line[i].lerp(line[i + 1], clampf((s - cum[i]) / seg, 0.0, 1.0) if seg > 1e-4 else 0.0)


## One painted stripe from a to b (road centreline points), shifted sideways by `offset` metres.
func _decal(a: Vector3, b: Vector3, offset: float, col: Color) -> void:
	var dir := Vector3(b.x - a.x, 0.0, b.z - a.z)
	var length: float = dir.length()
	if length < 0.3:
		return
	dir /= length
	var side: Vector3 = dir.cross(Vector3.UP)
	var c: Vector3 = (a + b) * 0.5 + side * offset
	if _on_bridge(c):
		return
	var key := Vector3i(roundi(c.x * 2.0), roundi(offset), roundi(c.z * 2.0))
	if _placed.has(key):
		return
	_placed[key] = true
	var d := Decal.new()
	var k: int = count % _albedo.size()
	d.texture_albedo = _albedo[k]
	if _normal[k] != null:
		d.texture_normal = _normal[k]
	d.modulate = col
	# X along the stripe (a little overlap so edge segments join), Y the projection depth, Z across.
	d.size = Vector3(length + 0.08, 1.2, LINE_WIDTH / 0.7)
	d.transform = Transform3D(Basis(dir, Vector3.UP, side), c)
	d.upper_fade = 0.3
	d.lower_fade = 0.3
	d.normal_fade = 0.5
	d.distance_fade_enabled = true
	d.distance_fade_begin = FADE_BEGIN
	d.distance_fade_length = FADE_LENGTH
	add_child(d)
	count += 1


func _on_bridge(p: Vector3) -> bool:
	for sp: Dictionary in _spans:
		var a: Vector3 = sp["from"]
		var b: Vector3 = sp["to"]
		var ab := Vector2(b.x - a.x, b.z - a.z)
		var t: float = clampf(Vector2(p.x - a.x, p.z - a.z).dot(ab) / maxf(ab.length_squared(), 1e-4), 0.0, 1.0)
		if Vector2(p.x - a.x, p.z - a.z).distance_to(ab * t) < float(sp["width"]) * 0.5 + 1.0 and t > 0.0 and t < 1.0:
			return true
	return false
