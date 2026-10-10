class_name MapMarkers
extends RefCounted
## Markers for what the player built (player report 5): the layers in data/config/map_markers.json,
## each marking the placed structures that provide one of its tags (a lean-to, a bedroll: where you
## can sleep, save or wake), read from what stands built (placed(): the live pieces, else the saved
## world state; never written here). Drawn on the full map (WorldMap) and the tether's minimap
## (Tether) while their layer is on; the full map's legend toggles a layer, saved in
## Settings.map_layers.


static func config() -> Dictionary:
	return Content.config(&"map_markers")


static func layers(cfg: Dictionary = {}) -> Array:
	var c: Dictionary = cfg if not cfg.is_empty() else config()
	return c.get("layers", [])


## Whether a layer shows: the player's choice, else the layer's default.
static func layer_on(layer: Dictionary) -> bool:
	return bool(Settings.map_layers.get(str(layer.get("id", "")), bool(layer.get("default", true))))


## Flips a layer and saves the choice.
static func toggle(layer: Dictionary) -> void:
	Settings.map_layers[str(layer["id"])] = not layer_on(layer)
	Settings.save()


## The first layer a structure with these `provides` tags belongs to ({} for none).
static func layer_for(provides: PackedStringArray, all_layers: Array) -> Dictionary:
	for l: Dictionary in all_layers:
		for want: String in l.get("provides", []):
			for tag: String in provides:
				if tag == want or (want.ends_with(":") and tag.begins_with(want)):
					return l
	return {}


## What stands built: [{def: StringName, pos: Vector3}]. The live pieces while a world runs (the
## world state only gets them when the game saves: a shelter built since wasn't marked), else the
## saved state.
static func placed(ws: WorldState = null) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var b: Node = Game.world.get(&"building") if Game.world != null else null
	if ws == null and b != null:
		for id: StringName in b.pieces:
			var piece: StructurePiece = b.pieces[id]
			if is_instance_valid(piece) and piece.def != null:
				out.append({"def": piece.def.id, "pos": piece.global_position})
		return out
	var st: WorldState = ws if ws != null else (Game.session.world if Game.session != null else null)
	if st == null:
		return out
	for k: Variant in st.structures:
		var e: Dictionary = st.structures[k]
		var p: Array = e.get("pos", [0, 0, 0])
		out.append({"def": StringName(str(e.get("def", ""))), "pos": Vector3(float(p[0]), float(p[1]), float(p[2]))})
	return out


## Every placed structure on a shown layer: [{pos: Vector3, layer: Dictionary, def: StringName}].
## `shown` overrides the settings (tests); null asks them.
static func marks(built: Array[Dictionary], all_layers: Array, shown: Variant = null) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for e: Dictionary in built:
		var def: StructureDef = Content.structure(e["def"])
		if def == null:
			continue
		var l: Dictionary = layer_for(def.provides, all_layers)
		if l.is_empty():
			continue
		var on: bool = layer_on(l) if shown == null else (shown as Array).has(str(l["id"]))
		if not on:
			continue
		out.append({"pos": e["pos"], "layer": l, "def": def.id})
	return out


static func color_of(layer: Dictionary) -> Color:
	return Color.from_string(str(layer.get("color", "#e8a33a")), Color(0.91, 0.64, 0.23))


## A shelter mark: a small house (a roof over a square), outlined so it reads on any ground.
static func draw_mark(ci: CanvasItem, at: Vector2, layer: Dictionary, s: float = 1.0) -> void:
	var col: Color = color_of(layer)
	var pts := PackedVector2Array([at + Vector2(-5, 5) * s, at + Vector2(-5, -1) * s, at + Vector2(0, -6) * s,
		at + Vector2(5, -1) * s, at + Vector2(5, 5) * s])
	ci.draw_colored_polygon(pts, col)
	var ring := pts.duplicate()
	ring.append(pts[0])
	ci.draw_polyline(ring, Color(0.08, 0.07, 0.05), 1.2 * s)


## What's wrong with the config (validate/tests): unknown provides tags, missing ids or labels.
static func problems(cfg: Dictionary = {}) -> PackedStringArray:
	var out: PackedStringArray = []
	var known: Dictionary = {}
	for d: StructureDef in Content.all(&"structure"):
		for tag: String in d.provides:
			known[tag] = true
	var ids: Dictionary = {}
	for l: Dictionary in layers(cfg):
		var id: String = str(l.get("id", ""))
		if id == "" or ids.has(id):
			out.append("map_markers: a layer needs a unique id (%s)" % id)
		ids[id] = true
		if str(l.get("label", "")) == "":
			out.append("map_markers: layer %s has no label" % id)
		for want: String in l.get("provides", []):
			var hit: bool = known.has(want)
			if want.ends_with(":"):
				for tag: String in known:
					hit = hit or tag.begins_with(want)
			if not hit:
				out.append("map_markers: layer %s wants '%s', which no structure provides" % [id, want])
	return out
