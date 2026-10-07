extends Node
## Item icons for the trade screen (TD-148). An item's generated 2D icon (`ItemDef.icon`, under
## assets/generated/) when one exists; otherwise a thumbnail of the same model the salvage roll lays
## out (`ItemVisuals.make_model`, which itself falls back to a category-coloured block before
## `make assets`), rendered once into a small SubViewport. Thumbnails are cached per item for as
## long as the screen lives, so refreshing a list after every trade costs nothing.

const SIZE := 64

var _cache: Dictionary = {}  # StringName item id -> Texture2D


func texture(item_id: StringName) -> Texture2D:
	if _cache.has(item_id):
		return _cache[item_id]
	var tex: Texture2D = null
	var def: ItemDef = Content.item(item_id)
	if def != null and def.icon != "":
		var path: String = "res://assets/generated/%s.png" % def.icon
		if ResourceLoader.exists(path):
			tex = load(path) as Texture2D
	if tex == null:
		tex = _render(item_id)
	_cache[item_id] = tex
	return tex


## A one-shot render of the item's model: own world (no level light or fog leaks in), transparent
## background, an orthographic three-quarter view framed on the model's bounds.
func _render(item_id: StringName) -> Texture2D:
	var vp := SubViewport.new()
	vp.size = Vector2i(SIZE, SIZE)
	vp.own_world_3d = true
	vp.transparent_bg = true
	vp.render_target_update_mode = SubViewport.UPDATE_ONCE
	add_child(vp)
	var model: Node3D = ItemVisuals.make_model(item_id)
	vp.add_child(model)
	var aabb: AABB = _bounds(model)
	var center: Vector3 = aabb.get_center()
	var radius: float = maxf(0.01, aabb.size.length() * 0.5)
	var cam := Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.size = radius * 2.1
	cam.near = 0.01
	cam.far = radius * 8.0
	# Transform3D.looking_at rather than look_at(): the viewport may not be in the tree yet.
	cam.transform = Transform3D(Basis(), center + Vector3(0.8, 0.9, 1.0).normalized() * radius * 3.0).looking_at(center, Vector3.UP)
	cam.current = true
	vp.add_child(cam)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, 35, 0)
	vp.add_child(sun)
	var env := Environment.new()
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.85, 0.82, 0.75)
	env.ambient_light_energy = 0.6
	var we := WorldEnvironment.new()
	we.environment = env
	vp.add_child(we)
	return vp.get_texture()


## The model's bounds in its own space (nested meshes included).
static func _bounds(model: Node3D) -> AABB:
	var out := AABB()
	var first: bool = true
	for c: Node in model.find_children("*", "VisualInstance3D", true, false):
		var vi: VisualInstance3D = c
		var xf: Transform3D = vi.transform
		var n: Node = vi.get_parent()
		while n != model and n is Node3D:
			xf = (n as Node3D).transform * xf
			n = n.get_parent()
		var b: AABB = xf * vi.get_aabb()
		out = b if first else out.merge(b)
		first = false
	return out
